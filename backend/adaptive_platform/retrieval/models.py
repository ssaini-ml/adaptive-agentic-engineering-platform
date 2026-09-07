from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID

from adaptive_platform.extraction.models import (
    RelationshipType,
    ResolutionStatus,
    SymbolType,
)


class TraversalDirection(StrEnum):
    INCOMING = "INCOMING"
    OUTGOING = "OUTGOING"
    BOTH = "BOTH"


class ContextDocumentType(StrEnum):
    MODULE = "MODULE"
    CLASS = "CLASS"
    FUNCTION = "FUNCTION"
    METHOD = "METHOD"
    TEST = "TEST"
    DOCUMENTATION_SECTION = "DOCUMENTATION_SECTION"
    CONFIGURATION_SECTION = "CONFIGURATION_SECTION"


class FullTextEngine(StrEnum):
    POSTGRESQL = "POSTGRESQL_FULL_TEXT"
    SQLITE_TEST_FALLBACK = "SQLITE_TEST_FALLBACK"


@dataclass(frozen=True, slots=True)
class SymbolResult:
    id: UUID
    scan_id: UUID
    file_id: UUID
    file_path: str
    parent_symbol_id: UUID | None
    name: str
    qualified_name: str
    symbol_type: SymbolType
    signature: str | None
    docstring: str | None
    start_line: int
    start_column: int
    end_line: int
    end_column: int
    extractor_name: str
    extractor_version: str
    extension_metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class TraversalEdge:
    relationship_id: UUID
    scan_id: UUID
    depth: int
    direction: TraversalDirection
    source: SymbolResult
    target: SymbolResult | None
    unresolved_target: str | None
    relationship_type: RelationshipType
    resolution_status: ResolutionStatus
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
    extension_metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class FullTextHit:
    document_id: UUID
    scan_id: UUID
    file_id: UUID
    file_path: str
    language: str | None
    category: str
    symbol_id: UUID | None
    document_type: ContextDocumentType
    content: str
    content_hash: str
    start_line: int
    end_line: int
    score: float
    retrieval_engine: FullTextEngine
    document_metadata: dict[str, Any]
