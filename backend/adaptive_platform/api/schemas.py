from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from adaptive_platform.domain.models import DirtyTreePolicy


class RepositoryCreate(BaseModel):
    path: str = Field(min_length=1)
    name: str | None = Field(default=None, min_length=1, max_length=255)


class RepositoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    canonical_path: str
    default_branch: str | None
    created_at: datetime
    updated_at: datetime


class ScanCreate(BaseModel):
    dirty_tree_policy: DirtyTreePolicy | None = None


class ScanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    repository_id: UUID
    commit_hash: str | None
    is_dirty: bool | None
    working_tree_fingerprint: str | None
    status: str
    scanner_version: str
    configuration_version: str
    started_at: datetime
    completed_at: datetime | None
    failure_code: str | None
    failure_message: str | None
    file_count: int
    total_bytes: int


class RepositoryFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    repository_id: UUID
    scan_id: UUID
    path: str
    language: str | None
    category: str
    content_hash: str
    size: int
    encoding: str | None
    is_generated: bool
    is_vendored: bool
    detection_signal: str | None
    secret_finding_count: int


class LanguageStatisticResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    language: str
    source_file_count: int
    source_bytes: int
    source_byte_percentage: float
    generated_file_count: int
    generated_bytes: int
    vendored_file_count: int
    vendored_bytes: int
    extractor_status: str
    extractor_name: str | None
    extractor_version: str | None
    detection_signals: list[str]
    diagnostics: list[str]


class LanguageProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scan_id: UUID
    repository_type: str
    primary_language: str | None
    profiler_name: str
    profiler_version: str
    configuration_version: str
    first_party_source_files: int
    first_party_source_bytes: int
    unprofiled_file_count: int
    created_at: datetime
    languages: list[LanguageStatisticResponse]


class SymbolResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scan_id: UUID
    file_id: UUID
    parent_symbol_id: UUID | None
    name: str
    qualified_name: str
    symbol_type: str
    signature: str | None
    docstring: str | None
    start_line: int
    start_column: int
    end_line: int
    end_column: int
    extractor_name: str
    extractor_version: str
    extension_metadata: dict[str, object]


class RelationshipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scan_id: UUID
    source_kind: str
    source_id: UUID
    target_kind: str
    target_id: UUID | None
    unresolved_target: str | None
    relationship_type: str
    resolution_status: str
    resolution_reason: str | None
    confidence: float
    evidence_type: str
    provenance: str
    evidence_file_id: UUID
    evidence_start_line: int
    evidence_start_column: int
    evidence_end_line: int
    evidence_end_column: int
    extractor_name: str
    extractor_version: str
    extension_metadata: dict[str, object]


class RetrievalSymbolResponse(BaseModel):
    """One immutable symbol hit with its repository-relative source path."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scan_id: UUID
    file_id: UUID
    file_path: str
    parent_symbol_id: UUID | None
    name: str
    qualified_name: str
    symbol_type: str
    signature: str | None
    docstring: str | None
    start_line: int
    start_column: int
    end_line: int
    end_column: int
    extractor_name: str
    extractor_version: str
    extension_metadata: dict[str, object]


class ExactSymbolRetrievalResponse(BaseModel):
    repository_id: UUID
    scan_id: UUID
    query: str
    count: int
    hits: list[RetrievalSymbolResponse]


class TraversalEdgeResponse(BaseModel):
    """A directed view of one stored relationship reached during traversal."""

    model_config = ConfigDict(from_attributes=True)

    relationship_id: UUID
    scan_id: UUID
    depth: int
    direction: str
    source: RetrievalSymbolResponse
    target: RetrievalSymbolResponse | None
    unresolved_target: str | None
    relationship_type: str
    resolution_status: str
    resolution_reason: str | None
    confidence: float
    evidence_type: str
    provenance: str
    evidence_file_id: UUID
    evidence_file_path: str
    evidence_start_line: int
    evidence_start_column: int
    evidence_end_line: int
    evidence_end_column: int
    extractor_name: str
    extractor_version: str
    extension_metadata: dict[str, object]


class GraphTraversalResponse(BaseModel):
    repository_id: UUID
    scan_id: UUID
    start_symbol_id: UUID
    direction: str
    max_depth: int
    count: int
    nodes: list[RetrievalSymbolResponse]
    edges: list[TraversalEdgeResponse]


class FullTextHitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: UUID
    scan_id: UUID
    file_id: UUID
    file_path: str
    language: str | None
    category: str
    symbol_id: UUID | None
    document_type: str
    content: str
    content_hash: str
    start_line: int
    end_line: int
    score: float
    retrieval_engine: str
    document_metadata: dict[str, object]


class FullTextRetrievalResponse(BaseModel):
    repository_id: UUID
    scan_id: UUID
    query: str
    retrieval_engine: str
    count: int
    hits: list[FullTextHitResponse]


class QuestionCreate(BaseModel):
    question: str = Field(min_length=1, max_length=512)


class ClaimEvidenceResponse(BaseModel):
    ref_type: str
    evidence_ref: str
    path: str | None
    start_line: int | None
    end_line: int | None
    evidence_type: str
    provenance: str


class GroundedClaimResponse(BaseModel):
    text: str
    claim_type: str
    importance: str
    verdict: str
    evidence: list[ClaimEvidenceResponse]


class QuestionResponse(BaseModel):
    task_id: UUID
    repository_id: UUID
    scan_id: UUID
    question: str
    query_class: str
    query_intent: str
    status: str
    answer: str | None
    confidence: str
    context_hash: str | None
    claims: list[GroundedClaimResponse]
    gaps: list[str]
    cache_status: str
    trace_url: str


class TraceEventResponse(BaseModel):
    id: UUID
    task_id: str
    repository_id: UUID | None
    scan_id: UUID | None
    correlation_id: str | None
    correction_of: UUID | None
    category: str
    event_type: str
    actor_type: str
    occurred_at: datetime
    summary: str
    rationale_summary: str | None
    input_refs: list[str]
    output_refs: list[str]
    metadata: dict[str, object]


class HumanFeedbackCreate(BaseModel):
    summary: str = Field(min_length=1, max_length=2000)
    disposition: str = Field(min_length=1, max_length=64)
    author_role: str = Field(min_length=1, max_length=64)
    corrected_event_id: UUID | None = None


class AgentProfileResponse(BaseModel):
    profile_id: str
    version: str
    role: str
    status: str
    input_schema: str
    output_schema: str
    permissions: list[str]
    required_gates: list[str]
    max_model_calls: int
    direct_repository_access: bool
    command_access: bool
    source_write_access: bool
    secret_access: bool
    profile_hash: str


class AbstentionReviewItem(BaseModel):
    task_id: UUID
    repository_id: UUID
    scan_id: UUID
    question: str
    gaps: list[str]
    created_at: datetime


class UnresolvedReferenceReviewItem(BaseModel):
    relationship_id: UUID
    scan_id: UUID
    unresolved_target: str
    resolution_reason: str | None
    evidence_file_id: UUID
    start_line: int
    end_line: int


class ReviewQueueResponse(BaseModel):
    abstentions: list[AbstentionReviewItem]
    unresolved_references: list[UnresolvedReferenceReviewItem]
    candidate_rules_status: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, object] = Field(default_factory=dict)
    trace_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
