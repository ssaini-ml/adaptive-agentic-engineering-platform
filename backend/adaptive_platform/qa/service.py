from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from adaptive_platform.context import (
    ASSEMBLER_VERSION,
    AssemblyBudget,
    ContextAssembler,
    CoverageDecision,
    EvidenceCandidate,
    EvidenceCompleteness,
    EvidenceProvenance,
    EvidenceStatus,
    QueryClassifier,
    QueryIntent,
    RetrievalMethod,
    ScanBinding,
    SlotName,
    TrustClass,
)
from adaptive_platform.database.models import (
    AnswerRecord,
    ClaimEvidenceRecord,
    ClaimRecord,
    ContextPackageRecord,
    QuestionTaskRecord,
    RelationshipRecord,
    RepositoryFileRecord,
    RepositoryRecord,
    RepositoryScanRecord,
    SymbolRecord,
    TraceEventRecord,
)
from adaptive_platform.grounding import (
    AnswerDecision,
    Citation,
    ClaimDraft,
    ClaimImportance,
    ClaimVerdict,
    ContextSlotRequirement,
    DeterministicClaimValidator,
    EvidenceSpan,
    StructuralAssertion,
    StructuralEvidence,
    decide_answer,
    evaluate_coverage,
)
from adaptive_platform.grounding import (
    ContextSlot as GroundingSlot,
)
from adaptive_platform.retrieval import FullTextRetriever, StructuralRetriever
from adaptive_platform.services.repositories import ServiceError

VALIDATOR_VERSION = "deterministic-claim-validator-v1"
ASSEMBLY_BUDGET = AssemblyBudget(max_tokens=6000, max_items=100, max_tokens_per_slot=3000)
_CACHE_VERSION = "grounded-qa-v1"


class QuestionService:
    """Synchronous, deterministic M4 read path over one immutable scan."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def ask(self, repository_id: UUID, scan_id: UUID, question: str) -> QuestionTaskRecord:
        scan = self._completed_scan(repository_id, scan_id)
        contract = QueryClassifier().classify(ScanBinding(repository_id, scan_id), question)
        cache_key = _stable_hash(
            {
                "version": _CACHE_VERSION,
                "scan_id": str(scan_id),
                "fingerprint": scan.working_tree_fingerprint,
                "question": contract.canonical_question,
                "classifier": contract.classifier_version,
                "assembler": ASSEMBLER_VERSION,
                "validator": VALIDATOR_VERSION,
            }
        )
        cached = self.session.scalar(
            select(QuestionTaskRecord)
            .where(
                QuestionTaskRecord.cache_key == cache_key,
                QuestionTaskRecord.status.in_(("ANSWERED", "PARTIAL", "ABSTAINED")),
            )
            .order_by(QuestionTaskRecord.created_at, QuestionTaskRecord.id)
        )
        if cached is not None:
            self._trace(
                cached,
                "DECISION",
                "cache_hit",
                "Returned the original immutable grounded response for this scan and question.",
                metadata={"cache_key": cache_key, "cached_task_id": str(cached.id)},
            )
            self.session.commit()
            return cached

        now = datetime.now(UTC)
        task = QuestionTaskRecord(
            id=uuid4(),
            repository_id=repository_id,
            scan_id=scan_id,
            question=question,
            canonical_question=contract.canonical_question,
            query_class=contract.query_class.value,
            query_intent=contract.intent.value,
            status="RUNNING",
            created_at=now,
            cache_key=cache_key,
            cache_status="MISS",
            classifier_version=contract.classifier_version,
            assembler_version=ASSEMBLER_VERSION,
            validator_version=VALIDATOR_VERSION,
            task_metadata={
                "contract_hash": contract.contract_hash,
                "working_tree_fingerprint": scan.working_tree_fingerprint,
                "required_slots": [slot.value for slot in contract.required_slots],
            },
        )
        self.session.add(task)
        self.session.flush()
        self._trace(task, "DECISION", "question_received", "Accepted a scan-bound question.")
        self._trace(
            task,
            "DECISION",
            "task_classified",
            "Classified the question with the deterministic M4 grammar.",
            rationale=contract.classification_reason,
            metadata={
                "query_class": contract.query_class.value,
                "query_intent": contract.intent.value,
                "classifier_version": contract.classifier_version,
                "contract_hash": contract.contract_hash,
            },
        )
        self._trace(
            task,
            "DECISION",
            "cache_miss",
            "No immutable response matched the complete cache identity.",
            metadata={"cache_key": cache_key},
        )

        candidates = self._retrieve(task, contract)
        package = ContextAssembler().assemble(contract, candidates, ASSEMBLY_BUDGET)
        task.context_hash = package.context_hash
        self._persist_package(task, package)
        self._trace(
            task,
            "DECISION",
            "context_assembled",
            "Assembled a deterministic typed context package.",
            metadata={
                "context_hash": package.context_hash,
                "item_count": package.item_count,
                "token_count": package.tokens_used,
                "omissions": [item.reason.value for item in package.omissions],
            },
        )

        if package.coverage_decision is CoverageDecision.ABSTAIN:
            gaps = [f"MISSING_ESSENTIAL_SLOT:{slot.value}" for slot in package.gaps]
            self._trace(
                task,
                "DECISION",
                "coverage_failed",
                "Coverage gate abstained before any model-agent call.",
                metadata={"gaps": gaps, "model_call_count": 0},
            )
            self._finalize(task, "ABSTAINED", None, "NONE", gaps, ())
            return task

        self._trace(
            task,
            "DECISION",
            "coverage_passed",
            "Every essential context slot is filled by admitted scan evidence.",
            metadata={"model_call_count": 0},
        )
        drafts, spans, structural = self._render_deterministic(contract.intent, package)
        validator = DeterministicClaimValidator(
            selected_scan_id=scan_id,
            evidence_spans=tuple(spans.values()),
            structural_evidence=tuple(structural),
        )
        requirements = tuple(ContextSlotRequirement(slot.value) for slot in contract.required_slots)
        coverage = evaluate_coverage(
            requirements,
            tuple(
                GroundingSlot(
                    slot.name.value,
                    tuple(item.item_id for item in slot.items)
                    or (
                        (f"empty:{slot.name.value}",) if slot.status.value == "FILLED_EMPTY" else ()
                    ),
                )
                for slot in package.slots
            ),
        )
        validated = tuple(validator.validate(draft) for draft in drafts)
        decision = decide_answer(coverage, validated)
        self._trace(
            task,
            "VERIFICATION",
            "claims_validated",
            "Ran deterministic citation, structural, lexical and qualifier checks.",
            metadata={
                "validator_version": VALIDATOR_VERSION,
                "claim_verdicts": [item.verdict.value for item in validated],
                "model_reviewer_call_count": 0,
            },
        )
        gaps = [f"{gap.code}:{gap.name}" for gap in decision.gaps]
        if decision.decision is AnswerDecision.ABSTAIN:
            status = "ABSTAINED"
            answer_text = None
            confidence = "NONE"
        else:
            status = decision.decision.value
            answer_text = "\n".join(item.claim.text for item in decision.claims)
            confidence = "DETERMINISTIC"
        self._finalize(task, status, answer_text, confidence, gaps, decision.claims, spans)
        return task

    def get(self, task_id: UUID) -> QuestionTaskRecord:
        task = self.session.get(QuestionTaskRecord, task_id)
        if task is None:
            raise ServiceError("TASK_NOT_FOUND", "Question task was not found", 404)
        return task

    def trace(self, task_id: UUID) -> list[TraceEventRecord]:
        self.get(task_id)
        return list(
            self.session.scalars(
                select(TraceEventRecord)
                .where(TraceEventRecord.task_id == str(task_id))
                .order_by(TraceEventRecord.occurred_at, TraceEventRecord.id)
            )
        )

    def _completed_scan(self, repository_id: UUID, scan_id: UUID) -> RepositoryScanRecord:
        if self.session.get(RepositoryRecord, repository_id) is None:
            raise ServiceError("REPOSITORY_NOT_FOUND", "Repository was not found", 404)
        scan = self.session.get(RepositoryScanRecord, scan_id)
        if scan is None:
            raise ServiceError("SCAN_NOT_FOUND", "Repository scan was not found", 404)
        if scan.repository_id != repository_id:
            raise ServiceError(
                "SCAN_REPOSITORY_MISMATCH",
                "Repository scan does not belong to the requested repository",
                409,
            )
        if scan.status != "COMPLETED":
            raise ServiceError("SCAN_NOT_COMPLETED", "Questions require a completed scan", 409)
        return scan

    def _retrieve(self, task: QuestionTaskRecord, contract: Any) -> list[EvidenceCandidate]:
        self._trace(
            task,
            "RETRIEVAL",
            "retrieval_planned",
            "Bounded retrieval steps were frozen before execution.",
            metadata={"steps": [_jsonable(step) for step in contract.retrieval_plan]},
        )
        if not contract.supported:
            return []
        if contract.intent is QueryIntent.LIST_ROUTES:
            return self._route_candidates(task)
        if contract.intent is QueryIntent.LOCATE_FRAMEWORK_CONSTRUCTION:
            return self._framework_candidates(task, contract.extracted_subject or "FastAPI")
        if contract.intent is QueryIntent.FUNCTIONS_IN_MODULE:
            return self._function_candidates(task, contract.extracted_subject or "")
        if contract.intent is QueryIntent.LIST_SYMBOLS:
            return self._general_symbol_candidates(task, contract.extracted_subject)

        subject = contract.extracted_subject or ""
        symbols = StructuralRetriever(self.session).exact_symbols(
            task.repository_id, task.scan_id, subject, limit=20
        )
        candidates = [
            self._symbol_candidate(item, SlotName.UNIQUE_TARGET, rank)
            for rank, item in enumerate(symbols, 1)
        ]
        self._trace(
            task,
            "RETRIEVAL",
            "exact_retrieval_completed",
            "Completed case-sensitive exact-symbol retrieval.",
            metadata={"query_sha256": _sha(subject), "result_count": len(symbols)},
        )
        if contract.intent is QueryIntent.LOCATE_DEFINITION or len(symbols) != 1:
            return candidates

        relationship_type = (
            "IMPORTS" if contract.intent is QueryIntent.FIND_IMPORTERS else "INHERITS"
        )
        edge_slot = (
            SlotName.IMPORT_EDGES
            if contract.intent is QueryIntent.FIND_IMPORTERS
            else SlotName.INHERITANCE_EDGES
        )
        edges = StructuralRetriever(self.session).traverse(
            task.repository_id,
            task.scan_id,
            symbols[0].id,
            direction="INCOMING",
            relationship_types=(relationship_type,),
            max_depth=1,
            limit=100,
        )
        alias = _requested_alias(contract.canonical_question)
        if alias is not None:
            edges = tuple(edge for edge in edges if edge.extension_metadata.get("alias") == alias)
        for rank, edge in enumerate(edges, 1):
            trust = (
                TrustClass.RESOLVED_GRAPH
                if edge.resolution_status.value == "RESOLVED"
                else TrustClass.HEURISTIC_GRAPH
            )
            completeness = (
                EvidenceCompleteness.COMPLETE
                if edge.resolution_status.value == "RESOLVED"
                else EvidenceCompleteness.PARTIAL
            )
            content = (
                f"{edge.source.qualified_name} {relationship_type} "
                f"{edge.target.qualified_name if edge.target else edge.unresolved_target} "
                f"in {edge.evidence_file_path} at line {edge.evidence_start_line}"
            )
            candidate = EvidenceCandidate(
                item_id=f"relationship:{edge.relationship_id}",
                slot=edge_slot,
                content=content,
                status=EvidenceStatus.RECORDED,
                trust=trust,
                completeness=completeness,
                provenance=EvidenceProvenance(
                    scan_id=task.scan_id,
                    source_kind=RetrievalMethod.GRAPH,
                    artifact_id=str(edge.relationship_id),
                    file_id=edge.evidence_file_id,
                    file_path=edge.evidence_file_path,
                    start_line=edge.evidence_start_line,
                    end_line=edge.evidence_end_line,
                    producer=edge.extractor_name,
                    producer_version=edge.extractor_version,
                    resolution_status=edge.resolution_status.value,
                    input_refs=(f"symbol:{symbols[0].id}",),
                ),
                retrieval_rank=rank,
                selection_reason="Incoming recorded structural edge.",
            )
            candidates.append(candidate)
            if SlotName.FILE_CATEGORIES in contract.required_slots:
                source_file = self.session.get(RepositoryFileRecord, edge.evidence_file_id)
                if source_file is not None:
                    candidates.append(
                        EvidenceCandidate(
                            item_id=f"file-category:{source_file.id}",
                            slot=SlotName.FILE_CATEGORIES,
                            content=f"{source_file.path} has category {source_file.category}",
                            status=EvidenceStatus.DERIVED,
                            trust=TrustClass.DERIVED,
                            completeness=EvidenceCompleteness.COMPLETE,
                            provenance=EvidenceProvenance(
                                scan_id=task.scan_id,
                                source_kind=RetrievalMethod.GRAPH,
                                artifact_id=str(source_file.id),
                                file_id=source_file.id,
                                file_path=source_file.path,
                                start_line=edge.evidence_start_line,
                                end_line=edge.evidence_end_line,
                                producer="question-service",
                                producer_version=_CACHE_VERSION,
                                input_refs=(f"relationship:{edge.relationship_id}",),
                            ),
                            retrieval_rank=rank,
                            selection_reason="Category of a file containing an admitted edge.",
                        )
                    )
        self._trace(
            task,
            "RETRIEVAL",
            "graph_retrieval_completed",
            "Completed bounded incoming graph traversal.",
            metadata={
                "relationship_type": relationship_type,
                "result_count": len(edges),
                "alias_constraint": alias,
            },
        )
        return candidates

    def _symbol_candidate(self, symbol: Any, slot: SlotName, rank: int) -> EvidenceCandidate:
        return EvidenceCandidate(
            item_id=f"symbol:{symbol.id}",
            slot=slot,
            content=(
                f"{symbol.qualified_name} {symbol.symbol_type.value} is defined in "
                f"{symbol.file_path} at lines {symbol.start_line}-{symbol.end_line}"
            ),
            status=EvidenceStatus.RECORDED,
            trust=TrustClass.EXACT_SYMBOL,
            completeness=EvidenceCompleteness.COMPLETE,
            provenance=EvidenceProvenance(
                scan_id=symbol.scan_id,
                source_kind=RetrievalMethod.EXACT,
                artifact_id=str(symbol.id),
                file_id=symbol.file_id,
                file_path=symbol.file_path,
                start_line=symbol.start_line,
                end_line=symbol.end_line,
                producer=symbol.extractor_name,
                producer_version=symbol.extractor_version,
                resolution_status="RESOLVED",
            ),
            retrieval_rank=rank,
            selection_reason="Case-sensitive exact symbol identity.",
        )

    def _route_candidates(self, task: QuestionTaskRecord) -> list[EvidenceCandidate]:
        rows = self.session.execute(
            select(SymbolRecord, RepositoryFileRecord.path)
            .join(RepositoryFileRecord, RepositoryFileRecord.id == SymbolRecord.file_id)
            .where(SymbolRecord.scan_id == task.scan_id, SymbolRecord.symbol_type == "ROUTE")
            .order_by(RepositoryFileRecord.path, SymbolRecord.start_line, SymbolRecord.id)
            .limit(100)
        )
        candidates = []
        for rank, (symbol, path) in enumerate(rows, 1):
            candidates.append(
                EvidenceCandidate(
                    item_id=f"symbol:{symbol.id}",
                    slot=SlotName.ROUTE_SYMBOLS,
                    content=f"{symbol.name} route is defined in {path} at line {symbol.start_line}",
                    status=EvidenceStatus.RECORDED,
                    trust=TrustClass.EXACT_SYMBOL,
                    completeness=EvidenceCompleteness.COMPLETE,
                    provenance=EvidenceProvenance(
                        scan_id=task.scan_id,
                        source_kind=RetrievalMethod.EXACT,
                        artifact_id=str(symbol.id),
                        file_id=symbol.file_id,
                        file_path=path,
                        start_line=symbol.start_line,
                        end_line=symbol.end_line,
                        producer=symbol.extractor_name,
                        producer_version=symbol.extractor_version,
                        resolution_status="RESOLVED",
                    ),
                    retrieval_rank=rank,
                    selection_reason="Recorded ROUTE symbol.",
                )
            )
        self._trace(
            task,
            "RETRIEVAL",
            "exact_retrieval_completed",
            "Retrieved recorded ROUTE symbols by type.",
            metadata={"symbol_type": "ROUTE", "result_count": len(candidates)},
        )
        return candidates

    def _framework_candidates(
        self, task: QuestionTaskRecord, framework: str
    ) -> list[EvidenceCandidate]:
        hits = FullTextRetriever(self.session).search(
            task.repository_id, task.scan_id, framework, limit=20
        )
        candidates: list[EvidenceCandidate] = []
        pattern = re.compile(rf"\b[A-Za-z_]\w*\s*=\s*{re.escape(framework)}\s*\(")
        for hit in hits:
            match = pattern.search(hit.content)
            if match is None or hit.category != "SOURCE":
                continue
            offset = hit.content[: match.start()].count("\n")
            line_number = hit.start_line + offset
            source_line = hit.content.splitlines()[offset]
            candidates.append(
                EvidenceCandidate(
                    item_id=f"context-document:{hit.document_id}:construction",
                    slot=SlotName.FRAMEWORK_CONSTRUCTION,
                    content=f"{source_line.strip()} in {hit.file_path}",
                    status=EvidenceStatus.RECORDED,
                    trust=TrustClass.FULL_TEXT,
                    completeness=EvidenceCompleteness.COMPLETE,
                    provenance=EvidenceProvenance(
                        scan_id=task.scan_id,
                        source_kind=RetrievalMethod.FULL_TEXT,
                        artifact_id=str(hit.document_id),
                        file_id=hit.file_id,
                        file_path=hit.file_path,
                        start_line=line_number,
                        end_line=line_number,
                        producer="postgresql-full-text",
                        producer_version="m3c-v1",
                    ),
                    retrieval_rank=len(candidates) + 1,
                    score=hit.score,
                    selection_reason="Lexical candidate passed framework-construction syntax check.",
                )
            )
            module = self.session.scalar(
                select(SymbolRecord).where(
                    SymbolRecord.scan_id == task.scan_id,
                    SymbolRecord.file_id == hit.file_id,
                    SymbolRecord.symbol_type == "MODULE",
                )
            )
            if module is not None:
                candidates.append(
                    EvidenceCandidate(
                        item_id=f"symbol:{module.id}:containing-module",
                        slot=SlotName.CONTAINING_MODULE,
                        content=f"{module.qualified_name} contains {source_line.strip()}",
                        status=EvidenceStatus.RECORDED,
                        trust=TrustClass.EXACT_SYMBOL,
                        completeness=EvidenceCompleteness.COMPLETE,
                        provenance=EvidenceProvenance(
                            scan_id=task.scan_id,
                            source_kind=RetrievalMethod.EXACT,
                            artifact_id=str(module.id),
                            file_id=hit.file_id,
                            file_path=hit.file_path,
                            start_line=line_number,
                            end_line=line_number,
                            producer=module.extractor_name,
                            producer_version=module.extractor_version,
                        ),
                        retrieval_rank=len(candidates) + 1,
                        selection_reason="Containing recorded module for construction span.",
                    )
                )
            break
        self._trace(
            task,
            "RETRIEVAL",
            "full_text_retrieval_completed",
            "Retrieved bounded lexical candidates and checked construction syntax.",
            metadata={"query_sha256": _sha(framework), "result_count": len(hits)},
        )
        return candidates

    def _general_symbol_candidates(
        self, task: QuestionTaskRecord, subject: str | None
    ) -> list[EvidenceCandidate]:
        statement = (
            select(SymbolRecord, RepositoryFileRecord.path)
            .join(RepositoryFileRecord, RepositoryFileRecord.id == SymbolRecord.file_id)
            .where(SymbolRecord.scan_id == task.scan_id)
            .order_by(RepositoryFileRecord.path, SymbolRecord.start_line, SymbolRecord.id)
            .limit(100)
        )
        rows = self.session.execute(statement)
        candidates = []
        for rank, (symbol, path) in enumerate(rows, 1):
            if subject and subject not in symbol.qualified_name:
                continue
            candidates.append(
                EvidenceCandidate(
                    item_id=f"symbol:{symbol.id}",
                    slot=SlotName.FULL_TEXT_EVIDENCE,
                    content=f"{symbol.qualified_name} {symbol.symbol_type} {path}:{symbol.start_line}",
                    status=EvidenceStatus.RECORDED,
                    trust=TrustClass.EXACT_SYMBOL,
                    completeness=EvidenceCompleteness.COMPLETE,
                    provenance=EvidenceProvenance(
                        scan_id=task.scan_id,
                        source_kind=RetrievalMethod.EXACT,
                        artifact_id=str(symbol.id),
                        file_id=symbol.file_id,
                        file_path=path,
                        start_line=symbol.start_line,
                        end_line=symbol.end_line,
                        producer=symbol.extractor_name,
                        producer_version=symbol.extractor_version,
                    ),
                    retrieval_rank=rank,
                    selection_reason="Recorded symbol inventory entry.",
                )
            )
        return candidates

    def _function_candidates(
        self, task: QuestionTaskRecord, module_name: str
    ) -> list[EvidenceCandidate]:
        module_row = self.session.execute(
            select(SymbolRecord, RepositoryFileRecord.path)
            .join(RepositoryFileRecord, RepositoryFileRecord.id == SymbolRecord.file_id)
            .where(
                SymbolRecord.scan_id == task.scan_id,
                SymbolRecord.qualified_name == module_name,
                SymbolRecord.symbol_type == "MODULE",
            )
            .order_by(RepositoryFileRecord.path, SymbolRecord.id)
        ).first()
        if module_row is None:
            return []
        module, path = module_row
        candidates = [
            EvidenceCandidate(
                item_id=f"symbol:{module.id}",
                slot=SlotName.UNIQUE_MODULE,
                content=f"{module.qualified_name} MODULE is defined in {path}",
                status=EvidenceStatus.RECORDED,
                trust=TrustClass.EXACT_SYMBOL,
                completeness=EvidenceCompleteness.COMPLETE,
                provenance=EvidenceProvenance(
                    scan_id=task.scan_id,
                    source_kind=RetrievalMethod.EXACT,
                    artifact_id=str(module.id),
                    file_id=module.file_id,
                    file_path=path,
                    start_line=module.start_line,
                    end_line=module.end_line,
                    producer=module.extractor_name,
                    producer_version=module.extractor_version,
                ),
                retrieval_rank=1,
                selection_reason="Case-sensitive exact MODULE identity.",
            )
        ]
        rows = self.session.execute(
            select(SymbolRecord, RepositoryFileRecord.path)
            .join(RepositoryFileRecord, RepositoryFileRecord.id == SymbolRecord.file_id)
            .where(
                SymbolRecord.scan_id == task.scan_id,
                SymbolRecord.parent_symbol_id == module.id,
                SymbolRecord.symbol_type == "FUNCTION",
            )
            .order_by(SymbolRecord.qualified_name, SymbolRecord.start_line, SymbolRecord.id)
            .limit(100)
        )
        functions = list(rows)
        for rank, (symbol, function_path) in enumerate(functions, 1):
            candidates.append(
                EvidenceCandidate(
                    item_id=f"symbol:{symbol.id}",
                    slot=SlotName.FUNCTION_SYMBOLS,
                    content=(
                        f"{symbol.qualified_name} FUNCTION is defined in "
                        f"{function_path} at line {symbol.start_line}"
                    ),
                    status=EvidenceStatus.RECORDED,
                    trust=TrustClass.EXACT_SYMBOL,
                    completeness=EvidenceCompleteness.COMPLETE,
                    provenance=EvidenceProvenance(
                        scan_id=task.scan_id,
                        source_kind=RetrievalMethod.EXACT,
                        artifact_id=str(symbol.id),
                        file_id=symbol.file_id,
                        file_path=function_path,
                        start_line=symbol.start_line,
                        end_line=symbol.end_line,
                        producer=symbol.extractor_name,
                        producer_version=symbol.extractor_version,
                        input_refs=(f"symbol:{module.id}",),
                    ),
                    retrieval_rank=rank,
                    selection_reason="Direct FUNCTION child of the exact module.",
                )
            )
        self._trace(
            task,
            "RETRIEVAL",
            "exact_retrieval_completed",
            "Retrieved an exact module and its direct FUNCTION children.",
            metadata={"module": module_name, "result_count": len(functions)},
        )
        return candidates

    def _persist_package(self, task: QuestionTaskRecord, package: Any) -> None:
        canonical = _jsonable(package)
        self.session.add(
            ContextPackageRecord(
                task_id=task.id,
                repository_id=task.repository_id,
                scan_id=task.scan_id,
                slots=canonical["slots"],
                unfillable=[slot.value for slot in package.gaps],
                assembly_log=canonical["omissions"],
                canonical_package=canonical,
                item_count=package.item_count,
                token_count=package.tokens_used,
                token_budget=ASSEMBLY_BUDGET.max_tokens,
                render_strategy="DETERMINISTIC_STRUCTURAL",
                context_hash=package.context_hash,
                assembler_version=package.assembler_version,
                created_at=datetime.now(UTC),
            )
        )
        self.session.flush()

    def _render_deterministic(
        self, intent: QueryIntent, package: Any
    ) -> tuple[list[ClaimDraft], dict[str, EvidenceSpan], list[StructuralEvidence]]:
        items = [item for slot in package.slots for item in slot.items]
        spans = {
            item.item_id: EvidenceSpan(
                span_id=item.item_id,
                scan_id=package.query_contract.binding.scan_id,
                path=item.provenance.file_path or "<scan-evidence>",
                start_line=item.provenance.start_line or 1,
                end_line=item.provenance.end_line or item.provenance.start_line or 1,
                text=item.content,
            )
            for item in items
        }
        drafts: list[ClaimDraft] = []
        structural: list[StructuralEvidence] = []
        relevant = items
        if intent is QueryIntent.LOCATE_DEFINITION:
            relevant = [item for item in items if item.slot is SlotName.UNIQUE_TARGET]
        elif intent in {QueryIntent.FIND_IMPORTERS, QueryIntent.FIND_INHERITORS}:
            slot = (
                SlotName.IMPORT_EDGES
                if intent is QueryIntent.FIND_IMPORTERS
                else SlotName.INHERITANCE_EDGES
            )
            relevant = [item for item in items if item.slot is slot]
        elif intent is QueryIntent.LIST_ROUTES:
            relevant = [item for item in items if item.slot is SlotName.ROUTE_SYMBOLS]
        elif intent is QueryIntent.LOCATE_FRAMEWORK_CONSTRUCTION:
            relevant = [item for item in items if item.slot is SlotName.FRAMEWORK_CONSTRUCTION]
        elif intent is QueryIntent.FUNCTIONS_IN_MODULE:
            relevant = [item for item in items if item.slot is SlotName.FUNCTION_SYMBOLS]

        for position, item in enumerate(relevant):
            span = spans[item.item_id]
            citation = Citation(
                scan_id=span.scan_id,
                path=span.path,
                start_line=span.start_line,
                end_line=span.end_line,
                evidence_span_id=item.item_id,
            )
            assertion = None
            claim_type = "SYMBOL_IN_MODULE"
            if intent is QueryIntent.LOCATE_DEFINITION:
                subject = package.query_contract.extracted_subject or "symbol"
                text = f"{subject} is defined in {span.path} at line {span.start_line}."
                entities = (subject, span.path)
                claim_type = "DEFINED_AT"
            elif intent in {QueryIntent.FIND_IMPORTERS, QueryIntent.FIND_INHERITORS}:
                relationship_id = item.provenance.artifact_id
                relation = self.session.get(RelationshipRecord, UUID(relationship_id))
                if relation is None:
                    continue
                source = self.session.get(SymbolRecord, relation.source_id)
                target = (
                    self.session.get(SymbolRecord, relation.target_id)
                    if relation.target_id
                    else None
                )
                relation_word = (
                    "imports" if intent is QueryIntent.FIND_IMPORTERS else "inherits from"
                )
                target_name = (
                    target.qualified_name if target else relation.unresolved_target or "unknown"
                )
                text = f"{span.path} {relation_word} {package.query_contract.extracted_subject} at line {span.start_line}."
                entities = (span.path, package.query_contract.extracted_subject or target_name)
                assertion = StructuralAssertion(
                    source=source.qualified_name if source else "unknown",
                    relationship_type=relation.relationship_type,
                    target=target_name,
                )
                structural.append(
                    StructuralEvidence(
                        scan_id=span.scan_id,
                        assertion=assertion,
                        supports=relation.resolution_status == "RESOLVED",
                        evidence_span_id=item.item_id,
                    )
                )
                claim_type = "IMPORTS" if intent is QueryIntent.FIND_IMPORTERS else "INHERITS"
            elif intent is QueryIntent.LIST_ROUTES:
                route_name = item.content.split(" route is defined", 1)[0]
                text = f"{route_name} is defined in {span.path} at line {span.start_line}."
                entities = (route_name, span.path)
                claim_type = "ROUTE_DEFINED"
            elif intent is QueryIntent.LOCATE_FRAMEWORK_CONSTRUCTION:
                framework = package.query_contract.extracted_subject or "application"
                text = f"The {framework} application is created in {span.path} at line {span.start_line}."
                entities = (framework, span.path)
                claim_type = "FRAMEWORK_CONSTRUCTION"
            elif intent is QueryIntent.FUNCTIONS_IN_MODULE:
                function_name = item.content.split(" FUNCTION is defined", 1)[0]
                text = (
                    f"{function_name} is a function in "
                    f"{package.query_contract.extracted_subject} at line {span.start_line}."
                )
                entities = (
                    function_name,
                    package.query_contract.extracted_subject or "module",
                )
                claim_type = "SYMBOL_IN_MODULE"
            else:
                text = item.content
                entities = tuple(part for part in (item.provenance.file_path,) if part)
            drafts.append(
                ClaimDraft(
                    claim_id=f"{claim_type.lower()}-{position}",
                    text=text,
                    importance=ClaimImportance.ESSENTIAL,
                    citations=(citation,),
                    entities=entities,
                    structural_assertion=assertion,
                    requested_verdict=ClaimVerdict.SUPPORTED,
                )
            )
        return drafts, spans, structural

    def _finalize(
        self,
        task: QuestionTaskRecord,
        status: str,
        answer_text: str | None,
        confidence: str,
        gaps: list[str],
        claims: tuple[Any, ...],
        spans: dict[str, EvidenceSpan] | None = None,
    ) -> None:
        answer = AnswerRecord(
            task_id=task.id,
            answer_text=answer_text,
            confidence=confidence,
            status=status,
            validator_version=VALIDATOR_VERSION,
            gaps=gaps,
            response_hash=_stable_hash(
                {"status": status, "answer": answer_text, "confidence": confidence, "gaps": gaps}
            ),
            created_at=datetime.now(UTC),
        )
        self.session.add(answer)
        self.session.flush()
        span_map = spans or {}
        for position, validated in enumerate(claims):
            claim_type = validated.claim.claim_id.rsplit("-", 1)[0].upper()
            record = ClaimRecord(
                answer_id=answer.id,
                position=position,
                text=validated.claim.text,
                claim_type=claim_type,
                importance=validated.claim.importance.value,
                verdict=validated.verdict.value,
                qualifier_metadata={
                    "checks": [_jsonable(item) for item in validated.checks],
                    "inference_labeled_inline": validated.claim.inference_labeled_inline,
                },
            )
            self.session.add(record)
            self.session.flush()
            for span_id in validated.evidence_span_ids:
                span = span_map[span_id]
                item = next(
                    item
                    for slot in task.context_package.canonical_package["slots"]
                    for item in slot["items"]
                    if item["item_id"] == span_id
                )
                provenance = item["provenance"]
                self.session.add(
                    ClaimEvidenceRecord(
                        claim_id=record.id,
                        file_id=UUID(provenance["file_id"]) if provenance.get("file_id") else None,
                        ref_type=_ref_type(span_id),
                        evidence_ref=span_id,
                        evidence_type=provenance["source_kind"],
                        provenance=item["status"],
                        start_line=span.start_line,
                        end_line=span.end_line,
                    )
                )
        task.status = status
        task.completed_at = datetime.now(UTC)
        self._trace(
            task,
            "DECISION",
            f"question_{status.casefold()}",
            f"Finalized the question task as {status}.",
            metadata={
                "answer_id": str(answer.id),
                "response_hash": answer.response_hash,
                "confidence": confidence,
                "gaps": gaps,
                "model_call_count": 0,
            },
        )
        self.session.commit()

    def _trace(
        self,
        task: QuestionTaskRecord,
        category: str,
        event_type: str,
        summary: str,
        *,
        rationale: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.session.add(
            TraceEventRecord(
                task_id=str(task.id),
                repository_id=task.repository_id,
                scan_id=task.scan_id,
                correlation_id=str(task.id),
                category=category,
                event_type=event_type,
                actor_type="SYSTEM",
                occurred_at=datetime.now(UTC),
                summary=summary,
                rationale_summary=rationale,
                input_refs=[f"scan:{task.scan_id}"],
                output_refs=[],
                event_metadata=metadata or {},
            )
        )


def _requested_alias(question: str) -> str | None:
    match = re.search(r"\bas\s+([A-Za-z_][A-Za-z0-9_]*)\b", question)
    return match.group(1) if match else None


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, UUID):
        return str(value)
    if hasattr(value, "__dataclass_fields__"):
        return {key: _jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _ref_type(item_id: str) -> str:
    if item_id.startswith("symbol:"):
        return "SYMBOL"
    if item_id.startswith("relationship:"):
        return "RELATIONSHIP"
    if item_id.startswith("context-document:"):
        return "CONTEXT_DOCUMENT"
    return "RETRIEVAL_RESULT"
