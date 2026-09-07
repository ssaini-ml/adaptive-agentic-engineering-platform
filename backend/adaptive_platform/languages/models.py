from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from adaptive_platform.extraction import ExtractorStatus


class RepositoryType(StrEnum):
    SINGLE_LANGUAGE = "SINGLE_LANGUAGE"
    POLYGLOT = "POLYGLOT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class FileLanguageDetection:
    language: str | None
    signal: str | None


@dataclass(frozen=True, slots=True)
class LanguageStatistic:
    language: str
    source_file_count: int
    source_bytes: int
    source_byte_percentage: float
    generated_file_count: int
    generated_bytes: int
    vendored_file_count: int
    vendored_bytes: int
    extractor_status: ExtractorStatus
    extractor_name: str | None
    extractor_version: str | None
    detection_signals: tuple[str, ...]
    diagnostics: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RepositoryLanguageProfile:
    repository_type: RepositoryType
    primary_language: str | None
    profiler_name: str
    profiler_version: str
    configuration_version: str
    first_party_source_files: int
    first_party_source_bytes: int
    unprofiled_file_count: int
    languages: tuple[LanguageStatistic, ...]

