from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Protocol
from uuid import UUID

from adaptive_platform.extraction.models import ExtractedRelationship, ExtractedSymbol


class ExtractorStatus(StrEnum):
    SUPPORTED = "SUPPORTED"
    PARTIAL = "PARTIAL"
    UNSUPPORTED = "UNSUPPORTED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class ExtractorDescriptor:
    name: str
    version: str
    languages: tuple[str, ...]
    status: ExtractorStatus
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExtractionDocument:
    file_id: UUID
    path: PurePosixPath
    language: str
    content_hash: str
    content: str


@dataclass(frozen=True, slots=True)
class ExtractionRequest:
    repository_id: UUID
    scan_id: UUID
    documents: tuple[ExtractionDocument, ...]


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    status: ExtractorStatus
    symbols: tuple[ExtractedSymbol, ...] = ()
    relationships: tuple[ExtractedRelationship, ...] = ()
    diagnostics: tuple[str, ...] = ()


class ExtractorAdapter(Protocol):
    @property
    def descriptor(self) -> ExtractorDescriptor: ...

    def extract(self, request: ExtractionRequest) -> ExtractionResult: ...
