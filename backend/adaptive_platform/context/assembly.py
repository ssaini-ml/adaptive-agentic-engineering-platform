from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict

from adaptive_platform.context.models import (
    AssemblyBudget,
    AssemblyOmission,
    ContextItem,
    ContextPackage,
    ContextSlot,
    CoverageDecision,
    EvidenceCandidate,
    EvidenceCompleteness,
    EvidenceStatus,
    OmissionReason,
    QueryContract,
    SlotName,
    SlotStatus,
    TrustClass,
)

ASSEMBLER_VERSION = "context-assembler-v1"
CONTEXT_PACKAGE_VERSION = "context-package-v1"

_TRUST_ORDER = {
    TrustClass.APPROVED_RULE: 0,
    TrustClass.EXACT_SYMBOL: 1,
    TrustClass.RESOLVED_GRAPH: 2,
    TrustClass.HEURISTIC_GRAPH: 3,
    TrustClass.FULL_TEXT: 4,
    TrustClass.DERIVED: 5,
    TrustClass.GENERATED: 6,
}
_EMPTY_ALLOWED = {
    SlotName.IMPORT_EDGES,
    SlotName.INHERITANCE_EDGES,
    SlotName.ROUTE_SYMBOLS,
    SlotName.GRAPH_RELATIONSHIPS,
    SlotName.FILE_CATEGORIES,
}


class ContextAssemblyError(ValueError):
    """The context request or budget is invalid."""


class ContextAssembler:
    """Selects a stable, bounded evidence projection without invoking a model."""

    def assemble(
        self,
        contract: QueryContract,
        candidates: Iterable[EvidenceCandidate],
        budget: AssemblyBudget | None = None,
    ) -> ContextPackage:
        budget = budget or AssemblyBudget()
        _validate_budget(budget)
        reserved_tokens = deterministic_token_count(contract.canonical_question) + 16
        if reserved_tokens >= budget.max_tokens:
            raise ContextAssemblyError("task frame and abstention rules exceed total token budget")

        accepted: dict[SlotName, list[ContextItem]] = defaultdict(list)
        omissions: list[AssemblyOmission] = []
        seen: set[str] = set()
        tokens_used = reserved_tokens
        item_count = 0
        known_slots = set(contract.required_slots)
        slot_order = {slot: index for index, slot in enumerate(contract.required_slots)}

        ordered = sorted(candidates, key=lambda item: _candidate_sort_key(item, slot_order))
        for candidate in ordered:
            omission = _candidate_precheck(contract, candidate, known_slots, seen)
            if omission is not None:
                omissions.append(omission)
                continue
            seen.add(candidate.item_id)
            token_count = deterministic_token_count(candidate.content)
            slot_tokens = sum(item.token_count for item in accepted[candidate.slot])
            if item_count >= budget.max_items:
                omissions.append(_omission(candidate, OmissionReason.ITEM_LIMIT, "item limit reached"))
                continue
            if slot_tokens + token_count > budget.max_tokens_per_slot:
                omissions.append(
                    _omission(
                        candidate,
                        OmissionReason.SLOT_TOKEN_BUDGET,
                        "candidate exceeds the slot token budget",
                    )
                )
                continue
            if tokens_used + token_count > budget.max_tokens:
                omissions.append(
                    _omission(
                        candidate,
                        OmissionReason.TOTAL_TOKEN_BUDGET,
                        "candidate exceeds the remaining total token budget",
                    )
                )
                continue
            item = ContextItem(
                item_id=candidate.item_id,
                slot=candidate.slot,
                content=candidate.content,
                token_count=token_count,
                status=candidate.status,
                trust=candidate.trust,
                provenance=candidate.provenance,
                retrieval_rank=candidate.retrieval_rank,
                completeness=_effective_completeness(candidate),
                score=candidate.score,
                selection_reason=candidate.selection_reason,
            )
            accepted[candidate.slot].append(item)
            item_count += 1
            tokens_used += token_count

        slots: list[ContextSlot] = []
        gaps: list[SlotName] = []
        for slot_name in contract.required_slots:
            items = tuple(accepted[slot_name])
            status = _slot_status(slot_name, items, omissions)
            if status not in {SlotStatus.FILLED, SlotStatus.FILLED_EMPTY}:
                gaps.append(slot_name)
            slots.append(
                ContextSlot(
                    name=slot_name,
                    required=True,
                    status=status,
                    token_budget=budget.max_tokens_per_slot,
                    tokens_used=sum(item.token_count for item in items),
                    items=items,
                )
            )

        decision = (
            CoverageDecision.READY
            if contract.supported and not gaps
            else CoverageDecision.ABSTAIN
        )
        canonical = {
            "package_version": CONTEXT_PACKAGE_VERSION,
            "assembler_version": ASSEMBLER_VERSION,
            "contract_hash": contract.contract_hash,
            "slots": [_canonical(slot) for slot in slots],
            "gaps": [gap.value for gap in gaps],
            "omissions": [_canonical(omission) for omission in omissions],
            "tokens_used": tokens_used,
            "item_count": item_count,
            "coverage_decision": decision.value,
        }
        context_hash = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()
        return ContextPackage(
            package_version=CONTEXT_PACKAGE_VERSION,
            assembler_version=ASSEMBLER_VERSION,
            query_contract=contract,
            slots=tuple(slots),
            gaps=tuple(gaps),
            omissions=tuple(omissions),
            tokens_used=tokens_used,
            item_count=item_count,
            coverage_decision=decision,
            context_hash=context_hash,
        )


def deterministic_token_count(text: str) -> int:
    """Provider-independent accounting used for deterministic admission budgets."""
    return len(re.findall(r"[A-Za-z0-9_]+|[^\w\s]", text, flags=re.UNICODE))


def _validate_budget(budget: AssemblyBudget) -> None:
    values = (budget.max_tokens, budget.max_items, budget.max_tokens_per_slot)
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 1 for value in values):
        raise ContextAssemblyError("all assembly budget values must be positive integers")
    if budget.max_tokens_per_slot > budget.max_tokens:
        raise ContextAssemblyError("per-slot token budget cannot exceed total token budget")


def _candidate_sort_key(
    candidate: EvidenceCandidate,
    slot_order: dict[SlotName, int],
) -> tuple[object, ...]:
    score = candidate.score if candidate.score is not None else 0.0
    provenance = candidate.provenance
    return (
        slot_order.get(candidate.slot, len(slot_order)),
        candidate.slot.value,
        _TRUST_ORDER[candidate.trust],
        candidate.retrieval_rank,
        -score,
        provenance.file_path or "",
        provenance.start_line or 0,
        candidate.item_id,
    )


def _candidate_precheck(
    contract: QueryContract,
    candidate: EvidenceCandidate,
    known_slots: set[SlotName],
    seen: set[str],
) -> AssemblyOmission | None:
    if candidate.provenance.scan_id != contract.binding.scan_id:
        return _omission(
            candidate,
            OmissionReason.WRONG_SCAN,
            "candidate provenance is bound to a different scan",
        )
    if candidate.slot not in known_slots:
        return _omission(
            candidate,
            OmissionReason.UNKNOWN_SLOT,
            "candidate does not fill a slot declared by the query contract",
        )
    if candidate.item_id in seen:
        return _omission(candidate, OmissionReason.DUPLICATE, "duplicate evidence item")
    if candidate.status is EvidenceStatus.DERIVED and not candidate.provenance.input_refs:
        return _omission(
            candidate,
            OmissionReason.INSUFFICIENT_PROVENANCE,
            "derived evidence must name its recorded input references",
        )
    return None


def _can_fill_required_slot(item: ContextItem) -> bool:
    if item.status is EvidenceStatus.RECORDED:
        return True
    return item.status is EvidenceStatus.DERIVED and bool(item.provenance.input_refs)


def _effective_completeness(candidate: EvidenceCandidate) -> EvidenceCompleteness:
    resolution_status = (candidate.provenance.resolution_status or "").upper()
    if resolution_status == "AMBIGUOUS":
        return EvidenceCompleteness.AMBIGUOUS
    if resolution_status == "UNRESOLVED":
        return EvidenceCompleteness.UNRESOLVED
    if resolution_status in {"PARTIALLY_RESOLVED", "HEURISTIC"}:
        return EvidenceCompleteness.PARTIAL
    if (
        candidate.completeness is EvidenceCompleteness.COMPLETE
        and candidate.trust is TrustClass.HEURISTIC_GRAPH
    ):
        return EvidenceCompleteness.PARTIAL
    return candidate.completeness


def _slot_status(
    slot_name: SlotName,
    items: tuple[ContextItem, ...],
    omissions: list[AssemblyOmission],
) -> SlotStatus:
    if not items:
        budget_reasons = {
            OmissionReason.ITEM_LIMIT,
            OmissionReason.SLOT_TOKEN_BUDGET,
            OmissionReason.TOTAL_TOKEN_BUDGET,
        }
        if any(item.slot is slot_name and item.reason in budget_reasons for item in omissions):
            return SlotStatus.OMITTED_BUDGET
        return SlotStatus.UNFILLABLE

    completeness = {item.completeness for item in items}
    if EvidenceCompleteness.AMBIGUOUS in completeness:
        return SlotStatus.AMBIGUOUS
    if slot_name is SlotName.UNIQUE_TARGET:
        complete_targets = [
            item
            for item in items
            if item.completeness is EvidenceCompleteness.COMPLETE
            and _can_fill_slot(slot_name, item)
        ]
        if len(complete_targets) > 1:
            return SlotStatus.AMBIGUOUS
    if completeness & {EvidenceCompleteness.PARTIAL, EvidenceCompleteness.UNRESOLVED}:
        return SlotStatus.UNFILLABLE
    if any(
        item.completeness is EvidenceCompleteness.COMPLETE and _can_fill_slot(slot_name, item)
        for item in items
    ):
        return SlotStatus.FILLED
    if slot_name in _EMPTY_ALLOWED and any(
        item.completeness is EvidenceCompleteness.EMPTY and _can_fill_slot(slot_name, item)
        for item in items
    ):
        return SlotStatus.FILLED_EMPTY
    return SlotStatus.UNFILLABLE


def _can_fill_slot(slot_name: SlotName, item: ContextItem) -> bool:
    if not _can_fill_required_slot(item):
        return False
    if slot_name is SlotName.UNIQUE_TARGET:
        return item.trust is TrustClass.EXACT_SYMBOL
    return item.trust is not TrustClass.GENERATED


def _omission(
    candidate: EvidenceCandidate,
    reason: OmissionReason,
    detail: str,
) -> AssemblyOmission:
    return AssemblyOmission(
        item_id=candidate.item_id,
        slot=candidate.slot,
        reason=reason,
        detail=detail,
    )


def _canonical(value: object) -> object:
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return {key: _canonical(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _canonical(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    return value
