from __future__ import annotations

from pathlib import PurePosixPath

import pytest
from adaptive_platform.domain import RepositoryFile
from adaptive_platform.extraction import (
    ExtractorRegistry,
    ExtractorStatus,
    PythonAstExtractor,
)
from adaptive_platform.languages import (
    RepositoryType,
    detect_language,
    profile_repository_languages,
)


def repository_file(
    path: str,
    language: str | None,
    size: int,
    *,
    category: str = "SOURCE",
    generated: bool = False,
    vendored: bool = False,
) -> RepositoryFile:
    suffix = PurePosixPath(path).suffix
    return RepositoryFile(
        path=PurePosixPath(path),
        language=language,
        category=category,
        content_hash="0" * 64,
        size=size,
        is_generated=generated,
        is_vendored=vendored,
        detection_signal=f"extension:{suffix}" if suffix else "shebang:python",
    )


def test_polyglot_profile_separates_detection_from_support() -> None:
    files = (
        repository_file("web/app.ts", "TypeScript", 600),
        repository_file("service/app.py", "Python", 300),
        repository_file("tools/main.go", "Go", 100),
        repository_file("generated/client.ts", "TypeScript", 200, generated=True),
        repository_file("vendor/library.go", "Go", 400, vendored=True),
    )

    profile = profile_repository_languages(
        files,
        ExtractorRegistry((PythonAstExtractor(),)),
    )

    assert profile.repository_type is RepositoryType.POLYGLOT
    assert profile.primary_language == "TypeScript"
    assert profile.first_party_source_bytes == 1000
    statistics = {item.language: item for item in profile.languages}
    assert statistics["Python"].extractor_status is ExtractorStatus.SUPPORTED
    assert statistics["TypeScript"].extractor_status is ExtractorStatus.UNSUPPORTED
    assert statistics["Go"].extractor_status is ExtractorStatus.UNSUPPORTED
    assert statistics["TypeScript"].generated_bytes == 200
    assert statistics["Go"].vendored_bytes == 400


def test_unknown_profile_is_explicit() -> None:
    profile = profile_repository_languages(
        (repository_file("LICENSE", None, 20, category="OTHER"),),
        ExtractorRegistry(),
    )

    assert profile.repository_type is RepositoryType.UNKNOWN
    assert profile.primary_language is None
    assert profile.unprofiled_file_count == 1


def test_workspace_markers_preserve_small_polyglot_components() -> None:
    files = (
        repository_file("package.json", None, 20, category="DEPENDENCY"),
        repository_file("web/app.ts", "TypeScript", 999),
        repository_file("tools/go.mod", None, 20, category="DEPENDENCY"),
        repository_file("tools/main.go", "Go", 1),
    )

    profile = profile_repository_languages(files, ExtractorRegistry())

    assert profile.repository_type is RepositoryType.POLYGLOT
    statistics = {item.language: item for item in profile.languages}
    assert "marker:package.json" in statistics["TypeScript"].detection_signals
    assert "marker:tools/go.mod" in statistics["Go"].detection_signals


@pytest.mark.parametrize(
    ("path", "text", "expected"),
    [
        ("app.tsx", "", "TypeScript"),
        ("main.rs", "", "Rust"),
        ("tool", "#!/usr/bin/env python3\n", "Python"),
        ("script", "#!/bin/bash\n", "Shell"),
        ("README.md", "", None),
    ],
)
def test_language_detection_signals(path: str, text: str, expected: str | None) -> None:
    detection = detect_language(PurePosixPath(path), text)
    assert detection.language == expected


def test_registry_rejects_ambiguous_adapter_ownership() -> None:
    registry = ExtractorRegistry((PythonAstExtractor(),))

    with pytest.raises(ValueError, match="already registered"):
        registry.register(PythonAstExtractor())
