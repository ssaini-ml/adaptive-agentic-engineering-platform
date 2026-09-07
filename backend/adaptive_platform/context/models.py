from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID


class QueryClass(StrEnum):
    EXACT_SYMBOL = "EXACT_SYMBOL"
    STRUCTURAL = "STRUCTURAL"
    LOCATION = "LOCATION"
    GENERAL_STRUCTURAL = "GENERAL_STRUCTURAL"
    UNSUPPORTED = "UNSUPPORTED"


class QueryIntent(StrEnum):
    LOCATE_DEFINITION = "LOCATE_DEFINITION"
    FIND_IMPORTERS = "FIND_IMPORTERS"
    FIND_INHERITORS = "FIND_INHERITORS"
    LIST_ROUTES = "LIST_ROUTES"
    LOCATE_FRAMEWORK_CONSTRUCTION = "LOCATE_FRAMEWORK_CONSTRUCTION"
    FUNCTIONS_IN_MODULE = "FUNCTIONS_IN_MODULE"
    LIST_SYMBOLS = "LIST_SYMBOLS"
    UNSUPPORTED_RATIONALE = "UNSUPPORTED_RATIONALE"
    UNSUPPORTED_RUNTIME = "UNSUPPORTED_RUNTIME"
    UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"
    UNSUPPORTED_UNKNOWN = "UNSUPPORTED_UNKNOWN"


class RetrievalMethod(StrEnum):
    EXACT = "EXACT"
    GRAPH = "GRAPH"
    FULL_TEXT = "FULL_TEXT"


class SlotName(StrEnum):
    UNIQUE_TARGET = "unique_target"
    IMPORT_EDGES = "import_edges"
    INHERITANCE_EDGES = "inheritance_edges"
    ROUTE_SYMBOLS = "route_symbols"
    GRAPH_RELATIONSHIPS = "graph_relationships"
    FILE_CATEGORIES = "file_categories"
    FRAMEWORK_CONSTRUCTION = "framework_construction"
    CONTAINING_MODULE = "containing_module"
    UNIQUE_MODULE = "unique_module"
    FUNCTION_SYMBOLS = "function_symbols"
    FULL_TEXT_EVIDENCE = "full_text_evidence"
    RECORDED_DECISION = "recorded_decision"
    RUNTIME_OBSERVATION = "runtime_observation"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"

    # Compatibility spellings for pre-audit callers. Serialized contracts use the
    # corrected canonical values above.
    EXACT_SYMBOL = "unique_target"
    ROUTE_EDGES = "route_symbols"
    FRAMEWORK_EVIDENCE = "framework_construction"


class EvidenceStatus(StrEnum):
    RECORDED = "RECORDED"
    DERIVED = "DERIVED"
    GENERATED = "GENERATED"


class TrustClass(StrEnum):
    APPROVED_RULE = "APPROVED_RULE"
    EXACT_SYMBOL = "EXACT_SYMBOL"
    RESOLVED_GRAPH = "RESOLVED_GRAPH"
    HEURISTIC_GRAPH = "HEURISTIC_GRAPH"
    FULL_TEXT = "FULL_TEXT"
    DERIVED = "DERIVED"
    GENERATED = "GENERATED"


class EvidenceCompleteness(StrEnum):
    COMPLETE = "COMPLETE"
    EMPTY = "EMPTY"
    PARTIAL = "PARTIAL"
    AMBIGUOUS = "AMBIGUOUS"
    UNRESOLVED = "UNRESOLVED"


class SlotStatus(StrEnum):
    FILLED = "FILLED"
    FILLED_EMPTY = "FILLED_EMPTY"
    AMBIGUOUS = "AMBIGUOUS"
    UNFILLABLE = "UNFILLABLE"
    OMITTED_BUDGET = "OMITTED_BUDGET"

    # Compatibility alias. New packages never serialize MISSING.
    MISSING = "UNFILLABLE"


class OmissionReason(StrEnum):
    WRONG_SCAN = "WRONG_SCAN"
    UNKNOWN_SLOT = "UNKNOWN_SLOT"
    DUPLICATE = "DUPLICATE"
    ITEM_LIMIT = "ITEM_LIMIT"
    SLOT_TOKEN_BUDGET = "SLOT_TOKEN_BUDGET"
    TOTAL_TOKEN_BUDGET = "TOTAL_TOKEN_BUDGET"
    INSUFFICIENT_PROVENANCE = "INSUFFICIENT_PROVENANCE"


class CoverageDecision(StrEnum):
    READY = "READY"
    ABSTAIN = "ABSTAIN"


@dataclass(frozen=True, slots=True)
class ScanBinding:
    repository_id: UUID
    scan_id: UUID


@dataclass(frozen=True, slots=True)
class RetrievalStep:
    order: int
    method: RetrievalMethod
    fills_slot: SlotName
    query: str
    limit: int
    direction: str | None = None
    relationship_types: tuple[str, ...] = ()
    depends_on_slot: SlotName | None = None
    additional_slots: tuple[SlotName, ...] = ()
    constraints: tuple[tuple[str, str], ...] = ()
    reason: str = ""


@dataclass(frozen=True, slots=True)
class QueryContract:
    contract_version: str
    classifier_version: str
    binding: ScanBinding
    question: str
    canonical_question: str
    query_class: QueryClass
    intent: QueryIntent
    extracted_subject: str | None
    required_slots: tuple[SlotName, ...]
    retrieval_plan: tuple[RetrievalStep, ...]
    supported: bool
    classification_reason: str
    contract_hash: str


@dataclass(frozen=True, slots=True)
class EvidenceProvenance:
    scan_id: UUID
    source_kind: RetrievalMethod
    artifact_id: str
    file_id: UUID | None = None
    file_path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    producer: str | None = None
    producer_version: str | None = None
    resolution_status: str | None = None
    input_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EvidenceCandidate:
    item_id: str
    slot: SlotName
    content: str
    status: EvidenceStatus
    trust: TrustClass
    provenance: EvidenceProvenance
    retrieval_rank: int
    completeness: EvidenceCompleteness = EvidenceCompleteness.COMPLETE
    score: float | None = None
    selection_reason: str = ""


@dataclass(frozen=True, slots=True)
class ContextItem:
    item_id: str
    slot: SlotName
    content: str
    token_count: int
    status: EvidenceStatus
    trust: TrustClass
    provenance: EvidenceProvenance
    retrieval_rank: int
    completeness: EvidenceCompleteness
    score: float | None
    selection_reason: str


@dataclass(frozen=True, slots=True)
class ContextSlot:
    name: SlotName
    required: bool
    status: SlotStatus
    token_budget: int
    tokens_used: int
    items: tuple[ContextItem, ...]


@dataclass(frozen=True, slots=True)
class AssemblyOmission:
    item_id: str
    slot: SlotName
    reason: OmissionReason
    detail: str


@dataclass(frozen=True, slots=True)
class AssemblyBudget:
    max_tokens: int = 4096
    max_items: int = 40
    max_tokens_per_slot: int = 1024


@dataclass(frozen=True, slots=True)
class ContextPackage:
    package_version: str
    assembler_version: str
    query_contract: QueryContract
    slots: tuple[ContextSlot, ...]
    gaps: tuple[SlotName, ...]
    omissions: tuple[AssemblyOmission, ...]
    tokens_used: int
    item_count: int
    coverage_decision: CoverageDecision
    context_hash: str


CanonicalValue = str | int | float | bool | None | list[Any] | dict[str, Any]
