from __future__ import annotations

from collections.abc import Iterable

from adaptive_platform.grounding.models import (
    AnswerDecision,
    ClaimImportance,
    ClaimVerdict,
    ContextSlot,
    ContextSlotRequirement,
    CoverageResult,
    GroundingDecision,
    NamedGap,
    ValidatedClaim,
)


def evaluate_coverage(
    requirements: tuple[ContextSlotRequirement, ...],
    slots: tuple[ContextSlot, ...],
) -> CoverageResult:
    duplicate_requirements = _duplicates(item.name for item in requirements)
    duplicate_slots = _duplicates(item.name for item in slots)
    if duplicate_requirements or duplicate_slots:
        duplicates = sorted(duplicate_requirements | duplicate_slots)
        raise ValueError(f"Context slot names must be unique: {', '.join(duplicates)}")

    slot_by_name = {slot.name: slot for slot in slots}
    filled = tuple(
        requirement.name
        for requirement in requirements
        if slot_by_name.get(requirement.name) is not None
        and slot_by_name[requirement.name].filled
    )
    missing = tuple(requirement for requirement in requirements if requirement.name not in filled)
    gaps = tuple(
        NamedGap(
            name=requirement.name,
            code="MISSING_ESSENTIAL_SLOT" if requirement.essential else "MISSING_OPTIONAL_SLOT",
        )
        for requirement in missing
    )
    if any(requirement.essential for requirement in missing):
        decision = AnswerDecision.ABSTAIN
    elif missing:
        decision = AnswerDecision.PARTIAL
    else:
        decision = AnswerDecision.ANSWERED
    return CoverageResult(decision=decision, filled_slots=filled, gaps=gaps)


def decide_answer(
    coverage: CoverageResult,
    claims: tuple[ValidatedClaim, ...],
) -> GroundingDecision:
    if coverage.decision == AnswerDecision.ABSTAIN:
        return GroundingDecision(
            decision=AnswerDecision.ABSTAIN,
            claims=(),
            gaps=coverage.gaps,
        )

    failed_essential = tuple(
        claim
        for claim in claims
        if claim.claim.importance == ClaimImportance.ESSENTIAL
        and claim.verdict in {ClaimVerdict.UNSUPPORTED, ClaimVerdict.CONFLICTING}
    )
    claim_gaps = tuple(gap for claim in claims for gap in claim.gaps)
    if failed_essential:
        return GroundingDecision(
            decision=AnswerDecision.ABSTAIN,
            claims=(),
            gaps=_deduplicate_gaps((*coverage.gaps, *claim_gaps)),
        )

    retained = tuple(
        claim
        for claim in claims
        if claim.verdict in {ClaimVerdict.SUPPORTED, ClaimVerdict.INFERENCE}
    )
    if not retained:
        return GroundingDecision(
            decision=AnswerDecision.ABSTAIN,
            claims=(),
            gaps=_deduplicate_gaps(
                (*coverage.gaps, *claim_gaps, NamedGap("answer", "NO_SUPPORTED_CLAIMS"))
            ),
        )

    gaps = _deduplicate_gaps((*coverage.gaps, *claim_gaps))
    decision = AnswerDecision.PARTIAL if gaps else AnswerDecision.ANSWERED
    return GroundingDecision(decision=decision, claims=retained, gaps=gaps)


def _duplicates(values: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def _deduplicate_gaps(gaps: tuple[NamedGap, ...]) -> tuple[NamedGap, ...]:
    unique = {(gap.name, gap.code, gap.claim_id): gap for gap in gaps}
    ordered_keys = sorted(unique, key=lambda item: (item[0], item[1], item[2] or ""))
    return tuple(unique[key] for key in ordered_keys)
