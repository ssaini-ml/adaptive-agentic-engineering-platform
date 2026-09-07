from __future__ import annotations

from collections import defaultdict

from adaptive_platform.domain.models import RepositoryFile
from adaptive_platform.extraction import ExtractorRegistry
from adaptive_platform.languages.models import (
    LanguageStatistic,
    RepositoryLanguageProfile,
    RepositoryType,
)

PROFILER_NAME = "repository-language-profiler"
PROFILER_VERSION = "1.0.0"
DEFAULT_POLYGLOT_THRESHOLD_PERCENT = 5.0

MARKER_LANGUAGES: dict[str, tuple[str, ...]] = {
    "Cargo.toml": ("Rust",),
    "go.mod": ("Go",),
    "package.json": ("JavaScript", "TypeScript"),
    "pom.xml": ("Java",),
    "pyproject.toml": ("Python",),
}


def profile_repository_languages(
    files: tuple[RepositoryFile, ...],
    registry: ExtractorRegistry,
    *,
    configuration_version: str = "language-profiler-v1",
    polyglot_threshold_percent: float = DEFAULT_POLYGLOT_THRESHOLD_PERCENT,
) -> RepositoryLanguageProfile:
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    signals: dict[str, set[str]] = defaultdict(set)
    source_files_by_language: dict[str, list[RepositoryFile]] = defaultdict(list)
    unprofiled = 0

    for item in files:
        if item.language is None:
            if item.category == "OTHER":
                unprofiled += 1
            continue
        language = item.language
        if item.detection_signal:
            signals[language].add(item.detection_signal)
        if item.is_generated:
            counts[language]["generated_file_count"] += 1
            counts[language]["generated_bytes"] += item.size
        elif item.is_vendored:
            counts[language]["vendored_file_count"] += 1
            counts[language]["vendored_bytes"] += item.size
        elif item.category in {"SOURCE", "TEST"}:
            counts[language]["source_file_count"] += 1
            counts[language]["source_bytes"] += item.size
            source_files_by_language[language].append(item)

    marker_component_languages: set[str] = set()
    for marker_file in files:
        marker_languages = MARKER_LANGUAGES.get(marker_file.path.name)
        if marker_languages is None:
            continue
        parent_parts = marker_file.path.parent.parts
        for language in marker_languages:
            component_files = source_files_by_language.get(language, [])
            if any(item.path.parts[: len(parent_parts)] == parent_parts for item in component_files):
                signals[language].add(f"marker:{marker_file.path.as_posix()}")
                marker_component_languages.add(language)

    total_files = sum(values["source_file_count"] for values in counts.values())
    total_bytes = sum(values["source_bytes"] for values in counts.values())
    statistics: list[LanguageStatistic] = []
    for language in sorted(counts):
        values = counts[language]
        descriptor = registry.descriptor_for(language)
        percentage = (values["source_bytes"] / total_bytes * 100.0) if total_bytes else 0.0
        statistics.append(
            LanguageStatistic(
                language=language,
                source_file_count=values["source_file_count"],
                source_bytes=values["source_bytes"],
                source_byte_percentage=round(percentage, 4),
                generated_file_count=values["generated_file_count"],
                generated_bytes=values["generated_bytes"],
                vendored_file_count=values["vendored_file_count"],
                vendored_bytes=values["vendored_bytes"],
                extractor_status=descriptor.status,
                extractor_name=None if descriptor.name == "none" else descriptor.name,
                extractor_version=None if descriptor.version == "none" else descriptor.version,
                detection_signals=tuple(sorted(signals[language])),
                diagnostics=descriptor.diagnostics,
            )
        )

    ranked = sorted(
        (item for item in statistics if item.source_bytes > 0),
        key=lambda item: (-item.source_bytes, item.language),
    )
    primary_language = ranked[0].language if ranked else None
    material_languages = [
        item
        for item in ranked
        if item.source_byte_percentage >= polyglot_threshold_percent
    ]
    if not ranked:
        repository_type = RepositoryType.UNKNOWN
    elif len(material_languages) >= 2 or len(marker_component_languages) >= 2:
        repository_type = RepositoryType.POLYGLOT
    else:
        repository_type = RepositoryType.SINGLE_LANGUAGE

    return RepositoryLanguageProfile(
        repository_type=repository_type,
        primary_language=primary_language,
        profiler_name=PROFILER_NAME,
        profiler_version=PROFILER_VERSION,
        configuration_version=configuration_version,
        first_party_source_files=total_files,
        first_party_source_bytes=total_bytes,
        unprofiled_file_count=unprofiled,
        languages=tuple(statistics),
    )
