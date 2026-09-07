from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from adaptive_platform.evaluation.loader import discover_fixture_dirs, load_json, validate_fixture
from adaptive_platform.evaluation.metrics import precision_recall
from adaptive_platform.traces import ActorType, JsonlTraceRecorder, TraceCategory, TraceEvent


def _identity(item: dict[str, Any], kind: str) -> tuple[Any, ...]:
    if kind == "symbols":
        return (
            item.get("qualified_name"),
            item.get("type"),
            item.get("path"),
            item.get("start_line"),
            item.get("end_line"),
        )
    if kind == "imports":
        return (
            item.get("source_unit"),
            item.get("imported_name"),
            item.get("alias"),
            item.get("path"),
            item.get("line"),
        )
    if kind == "routes":
        return (item.get("method"), item.get("path"), item.get("handler"))
    if kind == "exposes":
        return (
            item.get("source_unit"),
            item.get("target"),
            item.get("path"),
            item.get("line"),
        )
    if kind == "unresolved":
        return (
            item.get("source_unit"),
            item.get("expression"),
            item.get("reason"),
            item.get("path"),
            item.get("line"),
        )
    if kind == "inherits":
        return (
            item.get("source"),
            item.get("target"),
            item.get("path"),
            item.get("line"),
        )
    raise ValueError(f"Unsupported prediction kind: {kind}")


def evaluate_predictions(golden: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for kind in ("symbols", "imports", "routes", "exposes", "unresolved", "inherits"):
        if kind in {"exposes", "unresolved", "inherits"} and golden.get(kind) is None:
            results[kind] = {"status": "NOT_LABELED"}
            continue
        expected_items = golden.get(kind) or []
        if kind == "imports":
            expected_items = [item for item in expected_items if not item.get("type_checking")]
            actual_items = [
                item for item in (actual.get(kind) or []) if not item.get("type_checking")
            ]
        else:
            actual_items = actual.get(kind) or []
        score = precision_recall(
            (_identity(item, kind) for item in expected_items),
            (_identity(item, kind) for item in actual_items),
        )
        results[kind] = score.to_dict()
    return results


def build_report(evaluation_root: Path, actual_dir: Path | None = None) -> dict[str, Any]:
    fixtures: list[dict[str, Any]] = []
    predictions: dict[str, Any] = {}
    fixture_root = evaluation_root / "fixtures"

    for fixture_dir in discover_fixture_dirs(fixture_root):
        fixture_id = fixture_dir.name
        summary = validate_fixture(fixture_dir)
        fixtures.append(summary.to_dict())
        if actual_dir is not None:
            actual_path = actual_dir / f"{fixture_id}.json"
            if actual_path.exists():
                golden = load_json(fixture_dir / "golden.json")
                predictions[fixture_id] = evaluate_predictions(golden, load_json(actual_path))
            else:
                predictions[fixture_id] = {"status": "MISSING_PREDICTIONS"}

    review = load_json(evaluation_root / "review.json")
    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "milestone": "M0_EVALUATION_FOUNDATION",
        "technical_status": "PASS",
        "human_label_review": review["status"],
        "fixtures": fixtures,
        "prediction_metrics": predictions if actual_dir is not None else {"status": "NOT_RUN"},
        "v0_1_release_gates": {
            "status": "NOT_RUN",
            "reason": "Product extraction and Q&A outputs are implemented in later milestones.",
        },
        "holdout": {
            "status": "POLICY_DEFINED_SELECTION_PENDING",
            "policy": "HOLDOUT_POLICY.md",
        },
    }


def main() -> int:
    project_root = Path(__file__).resolve().parents[3]

    def trace_ref(path: Path) -> str:
        try:
            return path.resolve().relative_to(project_root.resolve()).as_posix()
        except ValueError:
            return str(path.resolve())

    parser = argparse.ArgumentParser(description="Validate fixtures and build evaluation report")
    parser.add_argument(
        "--evaluation-root",
        type=Path,
        default=project_root / "evaluation",
    )
    parser.add_argument("--actual-dir", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root / "evaluation" / "baselines" / "milestone0.json",
    )
    parser.add_argument(
        "--trace-output",
        type=Path,
        default=project_root / "evaluation" / "baselines" / "milestone0.trace.jsonl",
    )
    args = parser.parse_args()

    report = build_report(args.evaluation_root, args.actual_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    correlation_id = str(uuid4())
    task_id = f"evaluation:{report['generated_at']}"
    recorder = JsonlTraceRecorder(args.trace_output)
    recorder.append(
        TraceEvent(
            task_id=task_id,
            correlation_id=correlation_id,
            category=TraceCategory.EXECUTION,
            event_type="evaluation_started",
            actor_type=ActorType.SYSTEM,
            summary="Started Milestone 0 fixture and baseline evaluation.",
            input_refs=(trace_ref(args.evaluation_root),),
            metadata={"actual_predictions_supplied": args.actual_dir is not None},
        )
    )
    for fixture in report["fixtures"]:
        recorder.append(
            TraceEvent(
                task_id=task_id,
                correlation_id=correlation_id,
                category=TraceCategory.VERIFICATION,
                event_type="fixture_integrity_verified",
                actor_type=ActorType.SYSTEM,
                summary=f"Verified fixture {fixture['fixture_id']}.",
                input_refs=(f"evaluation/fixtures/{fixture['fixture_id']}",),
                metadata={
                    "languages": fixture["languages"],
                    "evaluator_profile": fixture["evaluator_profile"],
                    "content_fingerprint": fixture["content_fingerprint"],
                },
            )
        )
    if args.actual_dir is None:
        recorder.append(
            TraceEvent(
                task_id=task_id,
                correlation_id=correlation_id,
                category=TraceCategory.DECISION,
                event_type="product_gates_not_run",
                actor_type=ActorType.SYSTEM,
                summary="Did not calculate product extraction gates.",
                rationale_summary="No extractor prediction directory was supplied.",
                output_refs=(trace_ref(args.output),),
                metadata={"gate_status": "NOT_RUN"},
            )
        )
    recorder.append(
        TraceEvent(
            task_id=task_id,
            correlation_id=correlation_id,
            category=TraceCategory.EXECUTION,
            event_type="evaluation_completed",
            actor_type=ActorType.SYSTEM,
            summary="Completed Milestone 0 evaluation.",
            output_refs=(trace_ref(args.output), trace_ref(args.trace_output)),
            metadata={
                "technical_status": report["technical_status"],
                "human_label_review": report["human_label_review"],
            },
        )
    )
    print(
        f"validated {len(report['fixtures'])} fixtures; "
        f"technical_status={report['technical_status']}; "
        f"human_review={report['human_label_review']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
