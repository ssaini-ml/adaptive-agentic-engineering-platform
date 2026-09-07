from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    inspect,
    select,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.engine import Connection
from sqlalchemy.orm import DeclarativeBase, Mapped, Mapper, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class RepositoryRecord(Base):
    __tablename__ = "repositories"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    canonical_path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    default_branch: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    scans: Mapped[list[RepositoryScanRecord]] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
    )


class RepositoryScanRecord(Base):
    __tablename__ = "repository_scans"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')",
            name="ck_repository_scans_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    repository_id: Mapped[UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    commit_hash: Mapped[str | None] = mapped_column(String(64))
    is_dirty: Mapped[bool | None] = mapped_column(Boolean)
    working_tree_fingerprint: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    scanner_version: Mapped[str] = mapped_column(String(64), nullable=False)
    configuration_version: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(64))
    failure_message: Mapped[str | None] = mapped_column(Text)
    file_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    repository: Mapped[RepositoryRecord] = relationship(back_populates="scans")
    files: Mapped[list[RepositoryFileRecord]] = relationship(
        back_populates="scan",
        cascade="all, delete-orphan",
    )
    language_profile: Mapped[RepositoryLanguageProfileRecord | None] = relationship(
        back_populates="scan",
        cascade="all, delete-orphan",
        uselist=False,
    )
    symbols: Mapped[list[SymbolRecord]] = relationship(
        back_populates="scan",
        cascade="all, delete-orphan",
    )
    evidence_relationships: Mapped[list[RelationshipRecord]] = relationship(
        back_populates="scan",
        cascade="all, delete-orphan",
    )
    context_documents: Mapped[list[ContextDocumentRecord]] = relationship(
        back_populates="scan",
        cascade="all, delete-orphan",
    )
    question_tasks: Mapped[list[QuestionTaskRecord]] = relationship(
        back_populates="scan",
        cascade="all, delete-orphan",
    )

    def ensure_mutable(self) -> None:
        state = inspect(self)
        history = state.attrs.status.history
        was_completed = bool(history.deleted and history.deleted[0] == "COMPLETED")
        unchanged_completed = not history.has_changes() and self.status == "COMPLETED"
        if was_completed or unchanged_completed:
            raise ValueError("Completed repository scans are immutable")


class RepositoryFileRecord(Base):
    __tablename__ = "repository_files"
    __table_args__ = (
        UniqueConstraint("scan_id", "path", name="uq_repository_files_scan_path"),
        CheckConstraint("size >= 0", name="ck_repository_files_size"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    repository_id: Mapped[UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scan_id: Mapped[UUID] = mapped_column(
        ForeignKey("repository_scans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    path: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    encoding: Mapped[str | None] = mapped_column(String(64))
    is_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_vendored: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    detection_signal: Mapped[str | None] = mapped_column(String(255))
    secret_finding_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    scan: Mapped[RepositoryScanRecord] = relationship(back_populates="files")


class RepositoryLanguageProfileRecord(Base):
    __tablename__ = "repository_language_profiles"
    __table_args__ = (
        CheckConstraint(
            "repository_type IN ('SINGLE_LANGUAGE', 'POLYGLOT', 'UNKNOWN')",
            name="ck_language_profiles_repository_type",
        ),
        CheckConstraint(
            "first_party_source_files >= 0",
            name="ck_language_profiles_source_files",
        ),
        CheckConstraint(
            "first_party_source_bytes >= 0",
            name="ck_language_profiles_source_bytes",
        ),
        CheckConstraint(
            "unprofiled_file_count >= 0",
            name="ck_language_profiles_unprofiled_files",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    scan_id: Mapped[UUID] = mapped_column(
        ForeignKey("repository_scans.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    repository_type: Mapped[str] = mapped_column(String(32), nullable=False)
    primary_language: Mapped[str | None] = mapped_column(String(64))
    profiler_name: Mapped[str] = mapped_column(String(128), nullable=False)
    profiler_version: Mapped[str] = mapped_column(String(64), nullable=False)
    configuration_version: Mapped[str] = mapped_column(String(64), nullable=False)
    first_party_source_files: Mapped[int] = mapped_column(Integer, nullable=False)
    first_party_source_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    unprofiled_file_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    scan: Mapped[RepositoryScanRecord] = relationship(back_populates="language_profile")
    languages: Mapped[list[RepositoryLanguageStatisticRecord]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
    )


class RepositoryLanguageStatisticRecord(Base):
    __tablename__ = "repository_language_statistics"
    __table_args__ = (
        UniqueConstraint("profile_id", "language", name="uq_language_statistics_profile_language"),
        CheckConstraint(
            "extractor_status IN ('SUPPORTED', 'PARTIAL', 'UNSUPPORTED', 'FAILED')",
            name="ck_language_statistics_extractor_status",
        ),
        CheckConstraint(
            "source_file_count >= 0 AND source_bytes >= 0 "
            "AND generated_file_count >= 0 AND generated_bytes >= 0 "
            "AND vendored_file_count >= 0 AND vendored_bytes >= 0",
            name="ck_language_statistics_nonnegative_counts",
        ),
        CheckConstraint(
            "source_byte_percentage >= 0 AND source_byte_percentage <= 100",
            name="ck_language_statistics_percentage",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("repository_language_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    language: Mapped[str] = mapped_column(String(64), nullable=False)
    source_file_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_byte_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    generated_file_count: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    vendored_file_count: Mapped[int] = mapped_column(Integer, nullable=False)
    vendored_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    extractor_status: Mapped[str] = mapped_column(String(16), nullable=False)
    extractor_name: Mapped[str | None] = mapped_column(String(128))
    extractor_version: Mapped[str | None] = mapped_column(String(64))
    detection_signals: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    diagnostics: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    profile: Mapped[RepositoryLanguageProfileRecord] = relationship(back_populates="languages")


class SymbolRecord(Base):
    __tablename__ = "symbols"
    __table_args__ = (
        UniqueConstraint(
            "scan_id",
            "qualified_name",
            "symbol_type",
            "file_id",
            "start_line",
            name="uq_symbols_scan_identity",
        ),
        CheckConstraint(
            "symbol_type IN ('MODULE', 'CLASS', 'FUNCTION', 'METHOD', 'CONSTANT', 'ROUTE', 'MODEL')",
            name="ck_symbols_type",
        ),
        CheckConstraint(
            "start_line >= 1 AND end_line >= start_line AND start_column >= 0 AND end_column >= 0",
            name="ck_symbols_span",
        ),
        Index("ix_symbols_scan_qualified_name", "scan_id", "qualified_name"),
        Index("ix_symbols_scan_name", "scan_id", "name"),
        Index("ix_symbols_scan_type", "scan_id", "symbol_type"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    scan_id: Mapped[UUID] = mapped_column(
        ForeignKey("repository_scans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_id: Mapped[UUID] = mapped_column(
        ForeignKey("repository_files.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_symbol_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("symbols.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    qualified_name: Mapped[str] = mapped_column(Text, nullable=False)
    symbol_type: Mapped[str] = mapped_column(String(32), nullable=False)
    signature: Mapped[str | None] = mapped_column(Text)
    docstring: Mapped[str | None] = mapped_column(Text)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    start_column: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_column: Mapped[int] = mapped_column(Integer, nullable=False)
    extractor_name: Mapped[str] = mapped_column(String(128), nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(64), nullable=False)
    extension_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    scan: Mapped[RepositoryScanRecord] = relationship(back_populates="symbols")


class RelationshipRecord(Base):
    __tablename__ = "relationships"
    __table_args__ = (
        CheckConstraint("source_kind = 'SYMBOL'", name="ck_relationships_source_kind"),
        CheckConstraint("target_kind = 'SYMBOL'", name="ck_relationships_target_kind"),
        CheckConstraint(
            "relationship_type IN ('DEFINES', 'IMPORTS', 'REFERENCES', 'INHERITS', 'EXPOSES', 'TESTS')",
            name="ck_relationships_type",
        ),
        CheckConstraint(
            "resolution_status IN ('RESOLVED', 'PARTIALLY_RESOLVED', 'HEURISTIC', 'UNRESOLVED', 'AMBIGUOUS')",
            name="ck_relationships_resolution_status",
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_relationships_confidence"),
        CheckConstraint(
            "evidence_start_line >= 1 AND evidence_end_line >= evidence_start_line "
            "AND evidence_start_column >= 0 AND evidence_end_column >= 0",
            name="ck_relationships_span",
        ),
        CheckConstraint(
            "(target_id IS NOT NULL AND unresolved_target IS NULL) OR "
            "(target_id IS NULL AND unresolved_target IS NOT NULL)",
            name="ck_relationships_target_xor_unresolved",
        ),
        CheckConstraint(
            "resolution_status != 'UNRESOLVED' OR resolution_reason IS NOT NULL",
            name="ck_relationships_unresolved_reason",
        ),
        Index(
            "ix_relationships_scan_source_type",
            "scan_id",
            "source_id",
            "relationship_type",
        ),
        Index(
            "ix_relationships_scan_target_type",
            "scan_id",
            "target_id",
            "relationship_type",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    scan_id: Mapped[UUID] = mapped_column(
        ForeignKey("repository_scans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="SYMBOL")
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("symbols.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="SYMBOL")
    target_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("symbols.id", ondelete="SET NULL"), index=True
    )
    unresolved_target: Mapped[str | None] = mapped_column(Text)
    relationship_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resolution_status: Mapped[str] = mapped_column(String(32), nullable=False)
    resolution_reason: Mapped[str | None] = mapped_column(String(128))
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    provenance: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_file_id: Mapped[UUID] = mapped_column(
        ForeignKey("repository_files.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evidence_start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_start_column: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_end_column: Mapped[int] = mapped_column(Integer, nullable=False)
    extractor_name: Mapped[str] = mapped_column(String(128), nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(64), nullable=False)
    extension_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    scan: Mapped[RepositoryScanRecord] = relationship(back_populates="evidence_relationships")


class ContextDocumentRecord(Base):
    __tablename__ = "context_documents"
    __table_args__ = (
        CheckConstraint(
            "document_type IN ('MODULE', 'CLASS', 'FUNCTION', 'METHOD', 'TEST', "
            "'DOCUMENTATION_SECTION', 'CONFIGURATION_SECTION')",
            name="ck_context_documents_type",
        ),
        CheckConstraint(
            "start_line >= 1 AND end_line >= start_line",
            name="ck_context_documents_span",
        ),
        Index("ix_context_documents_scan_type", "scan_id", "document_type"),
        Index("ix_context_documents_scan_file", "scan_id", "file_id"),
        Index(
            "ix_context_documents_search_vector",
            "search_vector",
            postgresql_using="gin",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    scan_id: Mapped[UUID] = mapped_column(
        ForeignKey("repository_scans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_id: Mapped[UUID] = mapped_column(
        ForeignKey("repository_files.id", ondelete="CASCADE"), nullable=False, index=True
    )
    symbol_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("symbols.id", ondelete="SET NULL"), index=True
    )
    document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR().with_variant(Text(), "sqlite"),
    )
    document_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)

    scan: Mapped[RepositoryScanRecord] = relationship(back_populates="context_documents")


class QuestionTaskRecord(Base):
    __tablename__ = "question_tasks"
    __table_args__ = (
        CheckConstraint(
            "query_class IN ('EXACT_SYMBOL', 'STRUCTURAL', 'LOCATION', "
            "'GENERAL_STRUCTURAL', 'UNSUPPORTED')",
            name="ck_question_tasks_query_class",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'ANSWERED', 'PARTIAL', 'ABSTAINED', 'FAILED')",
            name="ck_question_tasks_status",
        ),
        CheckConstraint(
            "cache_status IN ('MISS', 'HIT', 'NOT_CACHEABLE')",
            name="ck_question_tasks_cache_status",
        ),
        Index("ix_question_tasks_scan_canonical", "scan_id", "canonical_question"),
        Index("ix_question_tasks_cache_key", "cache_key"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    repository_id: Mapped[UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scan_id: Mapped[UUID] = mapped_column(
        ForeignKey("repository_scans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_question: Mapped[str] = mapped_column(Text, nullable=False)
    query_class: Mapped[str] = mapped_column(String(32), nullable=False)
    query_intent: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    context_hash: Mapped[str | None] = mapped_column(String(64))
    cache_key: Mapped[str] = mapped_column(String(64), nullable=False)
    cache_status: Mapped[str] = mapped_column(String(16), nullable=False)
    cached_from_task_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("question_tasks.id", ondelete="SET NULL"), index=True
    )
    classifier_version: Mapped[str] = mapped_column(String(64), nullable=False)
    assembler_version: Mapped[str] = mapped_column(String(64), nullable=False)
    validator_version: Mapped[str] = mapped_column(String(64), nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(64))
    failure_message: Mapped[str | None] = mapped_column(Text)
    task_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )

    scan: Mapped[RepositoryScanRecord] = relationship(back_populates="question_tasks")
    context_package: Mapped[ContextPackageRecord | None] = relationship(
        back_populates="task", cascade="all, delete-orphan", uselist=False
    )
    answer: Mapped[AnswerRecord | None] = relationship(
        back_populates="task", cascade="all, delete-orphan", uselist=False
    )


class ContextPackageRecord(Base):
    __tablename__ = "context_packages"
    __table_args__ = (
        CheckConstraint("item_count >= 0", name="ck_context_packages_item_count"),
        CheckConstraint(
            "token_count >= 0 AND token_budget > 0",
            name="ck_context_packages_token_budget",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("question_tasks.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    repository_id: Mapped[UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scan_id: Mapped[UUID] = mapped_column(
        ForeignKey("repository_scans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slots: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    unfillable: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    assembly_log: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    canonical_package: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    token_budget: Mapped[int] = mapped_column(Integer, nullable=False)
    render_strategy: Mapped[str] = mapped_column(String(32), nullable=False)
    context_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    assembler_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    task: Mapped[QuestionTaskRecord] = relationship(back_populates="context_package")


class AnswerRecord(Base):
    __tablename__ = "answers"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ANSWERED', 'PARTIAL', 'ABSTAINED', 'FAILED')",
            name="ck_answers_status",
        ),
        CheckConstraint(
            "confidence IN ('DETERMINISTIC', 'HIGH', 'MEDIUM', 'LOW', 'NONE')",
            name="ck_answers_confidence",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("question_tasks.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    answer_text: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    validator_version: Mapped[str] = mapped_column(String(64), nullable=False)
    gaps: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    response_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    task: Mapped[QuestionTaskRecord] = relationship(back_populates="answer")
    claims: Mapped[list[ClaimRecord]] = relationship(
        back_populates="answer", cascade="all, delete-orphan"
    )


class ClaimRecord(Base):
    __tablename__ = "claims"
    __table_args__ = (
        UniqueConstraint("answer_id", "position", name="uq_claims_answer_position"),
        CheckConstraint(
            "importance IN ('ESSENTIAL', 'OPTIONAL')", name="ck_claims_importance"
        ),
        CheckConstraint(
            "verdict IN ('SUPPORTED', 'INFERENCE', 'UNSUPPORTED', 'CONFLICTING')",
            name="ck_claims_verdict",
        ),
        CheckConstraint("position >= 0", name="ck_claims_position"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    answer_id: Mapped[UUID] = mapped_column(
        ForeignKey("answers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[str] = mapped_column(String(64), nullable=False)
    importance: Mapped[str] = mapped_column(String(16), nullable=False)
    verdict: Mapped[str] = mapped_column(String(16), nullable=False)
    qualifier_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )

    answer: Mapped[AnswerRecord] = relationship(back_populates="claims")
    evidence_links: Mapped[list[ClaimEvidenceRecord]] = relationship(
        back_populates="claim", cascade="all, delete-orphan"
    )


class ClaimEvidenceRecord(Base):
    __tablename__ = "claim_evidence"
    __table_args__ = (
        CheckConstraint(
            "ref_type IN ('SOURCE_SPAN', 'SYMBOL', 'RELATIONSHIP', 'CONTEXT_DOCUMENT', "
            "'SCAN_FACT', 'LANGUAGE_PROFILE', 'RETRIEVAL_RESULT')",
            name="ck_claim_evidence_ref_type",
        ),
        CheckConstraint(
            "(start_line IS NULL AND end_line IS NULL) OR "
            "(start_line >= 1 AND end_line >= start_line)",
            name="ck_claim_evidence_span",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    claim_id: Mapped[UUID] = mapped_column(
        ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("repository_files.id", ondelete="CASCADE"), index=True
    )
    ref_type: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    provenance: Mapped[str] = mapped_column(String(32), nullable=False)
    start_line: Mapped[int | None] = mapped_column(Integer)
    end_line: Mapped[int | None] = mapped_column(Integer)

    claim: Mapped[ClaimRecord] = relationship(back_populates="evidence_links")


class TraceEventRecord(Base):
    __tablename__ = "trace_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    task_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    repository_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        index=True,
    )
    scan_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("repository_scans.id", ondelete="CASCADE"),
        index=True,
    )
    parent_event_id: Mapped[UUID | None] = mapped_column(ForeignKey("trace_events.id"))
    correlation_id: Mapped[str | None] = mapped_column(String(255), index=True)
    correction_of: Mapped[UUID | None] = mapped_column(ForeignKey("trace_events.id"))
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    rationale_summary: Mapped[str | None] = mapped_column(Text)
    input_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    output_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )


@event.listens_for(RepositoryScanRecord, "before_update")
@event.listens_for(RepositoryScanRecord, "before_delete")
def prevent_completed_scan_update(
    mapper: Mapper[RepositoryScanRecord],
    connection: Connection,
    target: RepositoryScanRecord,
) -> None:
    del mapper, connection
    target.ensure_mutable()


def _ensure_parent_scan_mutable(connection: Connection, scan_id: UUID) -> None:
    status = connection.execute(
        select(RepositoryScanRecord.status).where(RepositoryScanRecord.id == scan_id)
    ).scalar_one()
    if status == "COMPLETED":
        raise ValueError("Files belonging to a completed scan are immutable")


@event.listens_for(RepositoryFileRecord, "before_insert")
@event.listens_for(RepositoryFileRecord, "before_update")
@event.listens_for(RepositoryFileRecord, "before_delete")
def prevent_completed_file_mutation(
    mapper: Mapper[RepositoryFileRecord],
    connection: Connection,
    target: RepositoryFileRecord,
) -> None:
    del mapper
    _ensure_parent_scan_mutable(connection, target.scan_id)


@event.listens_for(RepositoryLanguageProfileRecord, "before_insert")
@event.listens_for(RepositoryLanguageProfileRecord, "before_update")
@event.listens_for(RepositoryLanguageProfileRecord, "before_delete")
def prevent_completed_profile_mutation(
    mapper: Mapper[RepositoryLanguageProfileRecord],
    connection: Connection,
    target: RepositoryLanguageProfileRecord,
) -> None:
    del mapper
    _ensure_parent_scan_mutable(connection, target.scan_id)


def _ensure_statistic_parent_scan_mutable(connection: Connection, profile_id: UUID) -> None:
    status = connection.execute(
        select(RepositoryScanRecord.status)
        .join(
            RepositoryLanguageProfileRecord,
            RepositoryLanguageProfileRecord.scan_id == RepositoryScanRecord.id,
        )
        .where(RepositoryLanguageProfileRecord.id == profile_id)
    ).scalar_one()
    if status == "COMPLETED":
        raise ValueError("Language statistics belonging to a completed scan are immutable")


@event.listens_for(RepositoryLanguageStatisticRecord, "before_insert")
@event.listens_for(RepositoryLanguageStatisticRecord, "before_update")
@event.listens_for(RepositoryLanguageStatisticRecord, "before_delete")
def prevent_completed_statistic_mutation(
    mapper: Mapper[RepositoryLanguageStatisticRecord],
    connection: Connection,
    target: RepositoryLanguageStatisticRecord,
) -> None:
    del mapper
    _ensure_statistic_parent_scan_mutable(connection, target.profile_id)


@event.listens_for(SymbolRecord, "before_insert")
@event.listens_for(SymbolRecord, "before_update")
@event.listens_for(SymbolRecord, "before_delete")
@event.listens_for(RelationshipRecord, "before_insert")
@event.listens_for(RelationshipRecord, "before_update")
@event.listens_for(RelationshipRecord, "before_delete")
@event.listens_for(ContextDocumentRecord, "before_insert")
@event.listens_for(ContextDocumentRecord, "before_update")
@event.listens_for(ContextDocumentRecord, "before_delete")
def prevent_completed_evidence_mutation(
    mapper: Mapper[SymbolRecord | RelationshipRecord | ContextDocumentRecord],
    connection: Connection,
    target: SymbolRecord | RelationshipRecord | ContextDocumentRecord,
) -> None:
    del mapper
    _ensure_parent_scan_mutable(connection, target.scan_id)


@event.listens_for(ContextPackageRecord, "before_update")
@event.listens_for(ContextPackageRecord, "before_delete")
@event.listens_for(AnswerRecord, "before_update")
@event.listens_for(AnswerRecord, "before_delete")
@event.listens_for(ClaimRecord, "before_update")
@event.listens_for(ClaimRecord, "before_delete")
@event.listens_for(ClaimEvidenceRecord, "before_update")
@event.listens_for(ClaimEvidenceRecord, "before_delete")
def prevent_grounded_artifact_mutation(
    mapper: Mapper[
        ContextPackageRecord | AnswerRecord | ClaimRecord | ClaimEvidenceRecord
    ],
    connection: Connection,
    target: ContextPackageRecord | AnswerRecord | ClaimRecord | ClaimEvidenceRecord,
) -> None:
    del mapper, connection, target
    raise ValueError("Grounded answer artifacts are immutable")


@event.listens_for(TraceEventRecord, "before_update")
@event.listens_for(TraceEventRecord, "before_delete")
def prevent_trace_mutation(
    mapper: Mapper[TraceEventRecord],
    connection: Connection,
    target: TraceEventRecord,
) -> None:
    del mapper, connection, target
    raise ValueError("Trace events are append-only")
