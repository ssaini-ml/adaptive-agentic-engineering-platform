from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

from adaptive_platform.evaluation.models import FixtureSummary


class FixtureValidationError(ValueError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FixtureValidationError(f"Cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise FixtureValidationError(f"{path} must contain a JSON object")
    return value


def content_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(path for path in root.rglob("*") if path.is_file() and ".git" not in path.parts)
    for path in files:
        relative = path.relative_to(root).as_posix().encode()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        content = path.read_bytes()
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def discover_fixture_dirs(fixtures_root: Path) -> tuple[Path, ...]:
    """Discover enabled fixtures without assuming a programming language."""
    if not fixtures_root.is_dir():
        raise FixtureValidationError(f"Missing fixtures directory: {fixtures_root}")
    discovered: list[Path] = []
    for candidate in sorted(path for path in fixtures_root.iterdir() if path.is_dir()):
        manifest_path = candidate / "manifest.json"
        if not manifest_path.is_file():
            continue
        manifest = load_json(manifest_path)
        if manifest.get("enabled", True):
            discovered.append(candidate)
    if not discovered:
        raise FixtureValidationError(f"No enabled fixtures found in {fixtures_root}")
    return tuple(discovered)


def _safe_source_path(repository: Path, raw_path: str) -> Path:
    relative = PurePosixPath(raw_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise FixtureValidationError(f"Unsafe fixture source path: {raw_path}")
    source = repository.joinpath(*relative.parts)
    if not source.is_file():
        raise FixtureValidationError(f"Missing labelled source file: {raw_path}")
    return source


def _validate_line(repository: Path, item: dict[str, Any], line_key: str = "start_line") -> None:
    raw_path = item.get("source_path") or item.get("path")
    if not isinstance(raw_path, str):
        raise FixtureValidationError("Label is missing a source path")
    line = item.get(line_key) or item.get("line") or item.get("decorator_line")
    if not isinstance(line, int) or line < 1:
        raise FixtureValidationError(f"Invalid line for {raw_path}")
    source = _safe_source_path(repository, raw_path)
    line_count = len(source.read_text(encoding="utf-8").splitlines()) or 1
    if line > line_count:
        raise FixtureValidationError(f"Line {line} is outside {raw_path} ({line_count} lines)")


def _unique(items: list[dict[str, Any]], keys: tuple[str, ...], label: str) -> None:
    identities = [tuple(item.get(key) for key in keys) for item in items]
    if len(identities) != len(set(identities)):
        raise FixtureValidationError(f"Duplicate {label} labels")


def validate_fixture(fixture_dir: Path) -> FixtureSummary:
    manifest = load_json(fixture_dir / "manifest.json")
    golden = load_json(fixture_dir / manifest.get("golden_file", "golden.json"))
    repository = fixture_dir / manifest.get("source_root", "repository")
    if not repository.is_dir():
        raise FixtureValidationError(f"Missing fixture repository: {repository}")

    fixture_id = manifest.get("fixture_id")
    if fixture_id != fixture_dir.name:
        raise FixtureValidationError(f"Fixture ID mismatch for {fixture_dir}")

    languages = manifest.get("languages")
    if not isinstance(languages, list) or not languages or not all(
        isinstance(language, str) and language for language in languages
    ):
        raise FixtureValidationError(f"Fixture {fixture_id} must declare languages")
    evaluator_profile = manifest.get("evaluator_profile")
    if not isinstance(evaluator_profile, str) or not evaluator_profile:
        raise FixtureValidationError(f"Fixture {fixture_id} must declare evaluator_profile")

    symbols = golden.get("symbols")
    imports = golden.get("imports")
    routes = golden.get("routes")
    questions = golden.get("questions")
    if not all(isinstance(value, list) for value in (symbols, imports, routes, questions)):
        raise FixtureValidationError(f"{fixture_id} golden lists are incomplete")
    language_profile = golden.get("language_profile")
    if not isinstance(language_profile, dict):
        raise FixtureValidationError(f"{fixture_id} lacks language_profile labels")
    language_files = language_profile.get("files")
    extractor_status = language_profile.get("extractor_status")
    if not isinstance(language_files, list) or not isinstance(extractor_status, dict):
        raise FixtureValidationError(f"{fixture_id} language profile labels are incomplete")
    if language_profile.get("repository_type") not in {
        "SINGLE_LANGUAGE",
        "POLYGLOT",
        "UNKNOWN",
    }:
        raise FixtureValidationError(f"{fixture_id} has invalid repository_type label")
    if language_profile.get("primary_language") not in {*languages, None}:
        raise FixtureValidationError(f"{fixture_id} has invalid primary_language label")
    _unique(language_files, ("path",), "language file")
    for item in language_files:
        _safe_source_path(repository, str(item.get("path", "")))
        if item.get("language") not in languages:
            raise FixtureValidationError(f"{fixture_id} has invalid file language label")
        if not isinstance(item.get("is_generated"), bool) or not isinstance(
            item.get("is_vendored"), bool
        ):
            raise FixtureValidationError(f"{fixture_id} lacks file classification labels")
    if set(extractor_status) != set(languages):
        raise FixtureValidationError(f"{fixture_id} extractor status labels do not match languages")
    if any(
        status not in {"SUPPORTED", "PARTIAL", "UNSUPPORTED", "FAILED"}
        for status in extractor_status.values()
    ):
        raise FixtureValidationError(f"{fixture_id} has invalid extractor status label")

    _unique(symbols, ("qualified_name", "type", "path", "start_line"), "symbol")
    _unique(imports, ("source_module", "imported_name", "path", "line"), "import")
    _unique(routes, ("method", "path", "handler"), "route")
    _unique(questions, ("id",), "question")

    for symbol in symbols:
        _validate_line(repository, symbol)
        if symbol.get("end_line", 0) < symbol.get("start_line", 1):
            raise FixtureValidationError(f"Invalid symbol span: {symbol}")
    for edge in imports:
        _validate_line(repository, edge, "line")
    for route in routes:
        _validate_line(repository, route, "handler_line")

    if len(languages) > 1:
        for symbol in symbols:
            if symbol.get("language") not in languages:
                raise FixtureValidationError(
                    f"Polyglot symbol {symbol.get('qualified_name')} lacks valid language"
                )
        for edge in imports:
            if edge.get("source_language") not in languages:
                raise FixtureValidationError("Polyglot import lacks valid source_language")
            if edge.get("target_language") not in languages:
                raise FixtureValidationError("Polyglot import lacks valid target_language")

    for question in questions:
        if not isinstance(question.get("answerable"), bool):
            raise FixtureValidationError(f"Question {question.get('id')} lacks answerable boolean")
        if not question.get("required_slots"):
            raise FixtureValidationError(f"Question {question.get('id')} lacks required slots")
        if question["answerable"] and not question.get("essential_claims"):
            raise FixtureValidationError(f"Answerable question {question.get('id')} has no essential claim")

    fingerprint = content_fingerprint(repository)
    if fingerprint != manifest.get("content_fingerprint"):
        raise FixtureValidationError(f"Fixture {fixture_id} content fingerprint does not match manifest")

    files = [path for path in repository.rglob("*") if path.is_file() and ".git" not in path.parts]
    return FixtureSummary(
        fixture_id=fixture_id,
        fixture_version=str(manifest["fixture_version"]),
        languages=tuple(languages),
        evaluator_profile=evaluator_profile,
        pinned_revision=str(manifest["pinned_revision"]),
        content_fingerprint=fingerprint,
        file_count=len(files),
        language_file_labels=len(language_files),
        symbol_labels=len(symbols),
        import_labels=len(imports),
        route_labels=len(routes),
        question_labels=len(questions),
        answerable_questions=sum(bool(item["answerable"]) for item in questions),
        unanswerable_questions=sum(not bool(item["answerable"]) for item in questions),
        label_status=str(golden["label_status"]),
    )
