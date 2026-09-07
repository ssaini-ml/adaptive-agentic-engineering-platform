from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4

from adaptive_platform.domain import RepositoryFile
from adaptive_platform.evaluation.loader import discover_fixture_dirs, load_json, validate_fixture
from adaptive_platform.evaluation.metrics import precision_recall
from adaptive_platform.extraction import default_extractor_registry
from adaptive_platform.languages.detector import (
    detect_language,
    is_generated_path,
    is_vendored_path,
)
from adaptive_platform.languages.profiler import profile_repository_languages
from adaptive_platform.traces import ActorType, JsonlTraceRecorder, TraceCategory, TraceEvent

DOCUMENTATION_SUFFIXES = frozenset({".md", ".mdx", ".rst", ".txt"})
CONFIGURATION_SUFFIXES = frozenset({".ini", ".json", ".toml", ".yaml", ".yml"})
DEPENDENCY_FILES = frozenset(
    {"Cargo.lock", "Cargo.toml", "go.mod", "go.sum", "package.json", "package-lock.json", "pyproject.toml"}
)


def _category(path: PurePosixPath, language: str | None) -> str:
    lowered_parts = {part.lower() for part in path.parts}
    if path.name in DEPENDENCY_FILES:
        return "DEPENDENCY"
    if language is not None and ("tests" in lowered_parts or "test" in path.name.lower()):
        return "TEST"
    if language is not None:
        return "SOURCE"
    if path.suffix.lower() in DOCUMENTATION_SUFFIXES:
        return "DOCUMENTATION"
    if path.suffix.lower() in CONFIGURATION_SUFFIXES:
        return "CONFIGURATION"
    return "OTHER"


def inventory_fixture(repository: Path) -> tuple[RepositoryFile, ...]:
    records: list[RepositoryFile] = []
    for path in sorted(item for item in repository.rglob("*") if item.is_file()):
        relative = PurePosixPath(path.relative_to(repository).as_posix())
        content = path.read_bytes()
        if b"\x00" in content[:8192]:
            continue
        text = content.decode("utf-8", errors="replace")
        detection = detect_language(relative, text)
        records.append(
            RepositoryFile(
                path=relative,
                language=detection.language,
                category=_category(relative, detection.language),
                content_hash=hashlib.sha256(content).hexdigest(),
                size=len(content),
                encoding="utf-8",
                is_generated=is_generated_path(relative),
                is_vendored=is_vendored_path(relative),
                detection_signal=detection.signal,
            )
        )
    return tuple(records)


def evaluate_fixture_language_profile(fixture_dir: Path) -> dict[str, Any]:
    validate_fixture(fixture_dir)
    manifest = load_json(fixture_dir / "manifest.json")
    golden = load_json(fixture_dir / manifest.get("golden_file", "golden.json"))
    expected = golden["language_profile"]
    repository = fixture_dir / manifest.get("source_root", "repository")
    inventory = inventory_fixture(repository)
    profile = profile_repository_languages(inventory, default_extractor_registry())

    expected_files = {
        (item["path"], item["language"])
        for item in expected["files"]
    }
    labelled_paths = {item["path"] for item in expected["files"]}
    actual_files = {
        (item.path.as_posix(), item.language)
        for item in inventory
        if item.path.as_posix() in labelled_paths and item.language is not None
    }
    file_score = precision_recall(expected_files, actual_files)
    expected_classifications = {
        (item["path"], item["is_generated"], item["is_vendored"])
        for item in expected["files"]
    }
    actual_classifications = {
        (item.path.as_posix(), item.is_generated, item.is_vendored)
        for item in inventory
        if item.path.as_posix() in labelled_paths
    }
    classification_score = precision_recall(expected_classifications, actual_classifications)
    actual_status = {item.language: item.extractor_status.value for item in profile.languages}
    expected_status = expected["extractor_status"]
    routing_correct = actual_status == expected_status
    expected_unsupported = {
        language for language, status in expected_status.items() if status == "UNSUPPORTED"
    }
    actual_unsupported = {
        language for language, status in actual_status.items() if status == "UNSUPPORTED"
    }
    unsupported_score = precision_recall(expected_unsupported, actual_unsupported)

    return {
        "fixture_id": fixture_dir.name,
        "expected": {
            "repository_type": expected["repository_type"],
            "primary_language": expected["primary_language"],
            "extractor_status": expected_status,
        },
        "actual": {
            "repository_type": profile.repository_type.value,
            "primary_language": profile.primary_language,
            "extractor_status": actual_status,
        },
        "language_files": file_score.to_dict(),
        "classification": classification_score.to_dict(),
        "primary_language_correct": profile.primary_language == expected["primary_language"],
        "repository_type_correct": profile.repository_type.value == expected["repository_type"],
        "extractor_routing_correct": routing_correct,
        "unsupported_reporting": unsupported_score.to_dict(),
    }


def build_language_report(evaluation_root: Path) -> dict[str, Any]:
    results = [
        evaluate_fixture_language_profile(fixture)
        for fixture in discover_fixture_dirs(evaluation_root / "fixtures")
    ]
    language_precision = min(item["language_files"]["precision"] for item in results)
    language_recall = min(item["language_files"]["recall"] for item in results)
    unsupported_recall = min(item["unsupported_reporting"]["recall"] for item in results)
    gates = {
        "language_file_precision": {
            "value": language_precision,
            "threshold": 0.99,
            "passed": language_precision >= 0.99,
        },
        "language_file_recall": {
            "value": language_recall,
            "threshold": 0.99,
            "passed": language_recall >= 0.99,
        },
        "primary_language_accuracy": {
            "value": sum(item["primary_language_correct"] for item in results) / len(results),
            "threshold": 1.0,
            "passed": all(item["primary_language_correct"] for item in results),
        },
        "repository_type_accuracy": {
            "value": sum(item["repository_type_correct"] for item in results) / len(results),
            "threshold": 1.0,
            "passed": all(item["repository_type_correct"] for item in results),
        },
        "extractor_routing_accuracy": {
            "value": sum(item["extractor_routing_correct"] for item in results) / len(results),
            "threshold": 1.0,
            "passed": all(item["extractor_routing_correct"] for item in results),
        },
        "unsupported_language_reporting_recall": {
            "value": unsupported_recall,
            "threshold": 1.0,
            "passed": unsupported_recall == 1.0,
        },
    }
    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "milestone": "M2A_LANGUAGE_PROFILING",
        "technical_status": "PASS" if all(item["passed"] for item in gates.values()) else "FAIL",
        "human_label_review": load_json(evaluation_root / "review.json")["status"],
        "fixtures": results,
        "gates": gates,
    }


def main() -> int:
    project_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description="Evaluate Milestone 2A language profiling")
    parser.add_argument("--evaluation-root", type=Path, default=project_root / "evaluation")
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root / "evaluation" / "baselines" / "milestone2a.json",
    )
    parser.add_argument(
        "--trace-output",
        type=Path,
        default=project_root / "evaluation" / "baselines" / "milestone2a.trace.jsonl",
    )
    args = parser.parse_args()
    report = build_language_report(args.evaluation_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    correlation_id = str(uuid4())
    task_id = f"evaluation:milestone2a:{report['generated_at']}"
    recorder = JsonlTraceRecorder(args.trace_output)
    recorder.append(
        TraceEvent(
            task_id=task_id,
            correlation_id=correlation_id,
            category=TraceCategory.EXECUTION,
            event_type="language_profile_evaluation_started",
            actor_type=ActorType.SYSTEM,
            summary="Started Milestone 2A language-profile evaluation.",
        )
    )
    for fixture in report["fixtures"]:
        recorder.append(
            TraceEvent(
                task_id=task_id,
                correlation_id=correlation_id,
                category=TraceCategory.VERIFICATION,
                event_type="language_profile_fixture_evaluated",
                actor_type=ActorType.SYSTEM,
                summary=f"Evaluated language profile for {fixture['fixture_id']}.",
                input_refs=(f"evaluation/fixtures/{fixture['fixture_id']}",),
                metadata={
                    "repository_type": fixture["actual"]["repository_type"],
                    "primary_language": fixture["actual"]["primary_language"],
                    "extractor_status": fixture["actual"]["extractor_status"],
                },
            )
        )
    recorder.append(
        TraceEvent(
            task_id=task_id,
            correlation_id=correlation_id,
            category=TraceCategory.VERIFICATION,
            event_type="language_profile_evaluation_completed",
            actor_type=ActorType.SYSTEM,
            summary="Completed Milestone 2A language-profile evaluation.",
            output_refs=("evaluation/baselines/milestone2a.json",),
            metadata={"technical_status": report["technical_status"], "gates": report["gates"]},
        )
    )
    print(
        f"evaluated {len(report['fixtures'])} fixtures; "
        f"technical_status={report['technical_status']}; "
        f"human_review={report['human_label_review']}"
    )
    return 0 if report["technical_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
