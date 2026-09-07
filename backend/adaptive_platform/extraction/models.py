from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID


class SymbolType(StrEnum):
    MODULE = "MODULE"
    CLASS = "CLASS"
    FUNCTION = "FUNCTION"
    METHOD = "METHOD"
    CONSTANT = "CONSTANT"
    ROUTE = "ROUTE"
    MODEL = "MODEL"


class RelationshipType(StrEnum):
    DEFINES = "DEFINES"
    IMPORTS = "IMPORTS"
    REFERENCES = "REFERENCES"
    INHERITS = "INHERITS"
    EXPOSES = "EXPOSES"
    TESTS = "TESTS"


class ResolutionStatus(StrEnum):
    RESOLVED = "RESOLVED"
    PARTIALLY_RESOLVED = "PARTIALLY_RESOLVED"
    HEURISTIC = "HEURISTIC"
    UNRESOLVED = "UNRESOLVED"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True, slots=True)
class ExtractedSymbol:
    file_id: UUID
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
    parent_qualified_name: str | None = None
    extension_metadata: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ExtractedRelationship:
    source_qualified_name: str
    relationship_type: RelationshipType
    evidence_file_id: UUID
    evidence_start_line: int
    evidence_start_column: int
    evidence_end_line: int
    evidence_end_column: int
    resolution_status: ResolutionStatus
    extractor_name: str
    extractor_version: str
    target_qualified_name: str | None = None
    unresolved_target: str | None = None
    resolution_reason: str | None = None
    confidence: float = 1.0
    evidence_type: str = "SYNTAX_FACT"
    provenance: str = "RECORDED"
    extension_metadata: dict[str, Any] | None = None
