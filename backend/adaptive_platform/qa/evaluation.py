from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from adaptive_platform.config import Settings
from adaptive_platform.database import Base, TraceEventRecord, create_database_engine
from adaptive_platform.database.models import RepositoryFileRecord
from adaptive_platform.database.session import create_session_factory
from adaptive_platform.evaluation.loader import discover_fixture_dirs, load_json
from adaptive_platform.qa import QuestionService
from adaptive_platform.services import RepositoryService, ScanService
from adaptive_platform.traces import ActorType, JsonlTraceRecorder, TraceCategory, TraceEvent


def _git(root: Path, *arguments: str) -> None:
    subprocess.run(["git", "-C", str(root), *arguments], check=True, capture_output=True)


def build_report(evaluation_root: Path) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="aaep-m4-eval-") as temporary:
        workspace = Path(temporary)
        engine = create_database_engine(f"sqlite+pysqlite:///{workspace / 'evaluation.db'}")
        Base.metadata.create_all(engine)
        factory = create_session_factory(engine)
        settings = Settings(
            database_url=str(engine.url),
            allowed_repository_roots=str(workspace),
        )

        for fixture_dir in discover_fixture_dirs(evaluation_root / "fixtures"):
            fixture_id = fixture_dir.name
            repository_root = workspace / fixture_id
            shutil.copytree(fixture_dir / "repository", repository_root)
            _git(repository_root, "init", "--quiet")
            _git(repository_root, "config", "user.email", "fixture@example.test")
            _git(repository_root, "config", "user.name", "Fixture")
            _git(repository_root, "add", ".")
            _git(repository_root, "commit", "--quiet", "-m", "M4 evaluation fixture")

            with factory() as session:
                repository = RepositoryService(session, settings).register(str(repository_root))
                requested = ScanService(session, settings).request(repository.id)
                scan = ScanService(session, settings).execute(requested.id)
                if scan.status != "COMPLETED":
                    raise RuntimeError(f"Fixture scan failed: {fixture_id}:{scan.failure_code}")
                golden = load_json(fixture_dir / "golden.json")
                for expected in golden["questions"]:
                    task = QuestionService(session).ask(
                        repository.id, scan.id, expected["question"]
                    )
                    answer = task.answer
                    actual_resources = sorted(
                        {
                            session.get(RepositoryFileRecord, link.file_id).path
                            for claim in (answer.claims if answer else ())
                            for link in claim.evidence_links
                            if link.file_id is not None
                        }
                    )
                    expected_status = "ANSWERED" if expected["answerable"] else "ABSTAINED"
                    trace = list(
                        session.scalars(
                            select(TraceEventRecord).where(
                                TraceEventRecord.task_id == str(task.id)
                            )
                        )
                    )
                    case = {
                        "fixture_id": fixture_id,
                        "question_id": expected["id"],
                        "query_class_expected": expected["query_class"],
                        "query_class_actual": task.query_class,
                        "status_expected": expected_status,
                        "status_actual": task.status,
                        "required_slots_expected": expected["required_slots"],
                        "required_slots_actual": task.task_metadata["required_slots"],
                        "expected_resources": sorted(expected["expected_resources"]),
                        "actual_resources": actual_resources,
                        "citation_valid": all(
                            link.start_line is not None
                            and link.end_line is not None
                            and link.start_line >= 1
                            and link.end_line >= link.start_line
                            for claim in (answer.claims if answer else ())
                            for link in claim.evidence_links
                        ),
                        "false_confident": bool(
                            task.status == "ANSWERED"
                            and answer is not None
                            and answer.confidence != "NONE"
                            and any(claim.verdict != "SUPPORTED" for claim in answer.claims)
                        ),
                        "pre_gate_model_calls": sum(
                            1
                            for event in trace
                            if event.category == "MODEL_INTERACTION"
                            and event.event_type.startswith("model_")
                        ),
                    }
                    case["passed"] = bool(
                        case["query_class_actual"] == case["query_class_expected"]
                        and case["status_actual"] == case["status_expected"]
                        and case["required_slots_actual"] == case["required_slots_expected"]
                        and (
                            expected_status == "ABSTAINED"
                            or set(case["expected_resources"]) <= set(case["actual_resources"])
                        )
                        and case["citation_valid"]
                        and not case["false_confident"]
                        and case["pre_gate_model_calls"] == 0
                    )
                    cases.append(case)

    count = len(cases)
    passed = sum(bool(case["passed"]) for case in cases)
    answerable = [case for case in cases if case["status_expected"] == "ANSWERED"]
    unsupported = [case for case in cases if case["status_expected"] == "ABSTAINED"]
    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "milestone": "M4_ASSEMBLY_AND_GROUNDED_QA",
        "technical_status": "PASS" if passed == count else "FAIL",
        "human_label_review": load_json(evaluation_root / "review.json")["status"],
        "engine": "SQLITE_TEST_HARNESS",
        "production_dependency_gate": "M3C_POSTGRESQL_REQUIRED",
        "cases": cases,
        "metrics": {
            "case_count": count,
            "case_pass_rate": passed / count if count else 0.0,
            "classifier_accuracy": sum(
                case["query_class_actual"] == case["query_class_expected"] for case in cases
            )
            / count,
            "slot_map_accuracy": sum(
                case["required_slots_actual"] == case["required_slots_expected"] for case in cases
            )
            / count,
            "answer_coverage": sum(case["status_actual"] == "ANSWERED" for case in answerable)
            / len(answerable),
            "abstention_recall": sum(
                case["status_actual"] == "ABSTAINED" for case in unsupported
            )
            / len(unsupported),
            "citation_validity": sum(bool(case["citation_valid"]) for case in cases) / count,
            "false_confident_answer_rate": sum(
                bool(case["false_confident"]) for case in cases
            )
            / count,
            "pre_gate_model_call_count": sum(
                int(case["pre_gate_model_calls"]) for case in cases
            ),
        },
    }


def main() -> int:
    project_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description="Run Milestone 4 grounded-Q&A gates")
    parser.add_argument("--evaluation-root", type=Path, default=project_root / "evaluation")
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root / "evaluation" / "baselines" / "milestone4.json",
    )
    parser.add_argument(
        "--trace-output",
        type=Path,
        default=project_root / "evaluation" / "baselines" / "milestone4.trace.jsonl",
    )
    args = parser.parse_args()
    report = build_report(args.evaluation_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.trace_output.write_text("", encoding="utf-8")
    recorder = JsonlTraceRecorder(args.trace_output)
    task_id = f"evaluation-m4:{uuid4()}"
    correlation_id = str(uuid4())
    recorder.append(
        TraceEvent(
            task_id=task_id,
            correlation_id=correlation_id,
            category=TraceCategory.EXECUTION,
            event_type="m4_evaluation_started",
            actor_type=ActorType.SYSTEM,
            summary="Started deterministic Milestone 4 grounded-Q&A evaluation.",
            input_refs=("evaluation/fixtures",),
        )
    )
    for case in report["cases"]:
        recorder.append(
            TraceEvent(
                task_id=task_id,
                correlation_id=correlation_id,
                category=TraceCategory.VERIFICATION,
                event_type="m4_question_case_evaluated",
                actor_type=ActorType.SYSTEM,
                summary=f"Evaluated {case['fixture_id']}:{case['question_id']}.",
                metadata={"passed": case["passed"]},
            )
        )
    recorder.append(
        TraceEvent(
            task_id=task_id,
            correlation_id=correlation_id,
            category=TraceCategory.VERIFICATION,
            event_type="m4_evaluation_completed",
            actor_type=ActorType.SYSTEM,
            summary="Completed Milestone 4 grounded-Q&A evaluation.",
            output_refs=("evaluation/baselines/milestone4.json",),
            metadata={
                "technical_status": report["technical_status"],
                "human_label_review": report["human_label_review"],
                **report["metrics"],
            },
        )
    )
    print(
        f"evaluated {report['metrics']['case_count']} M4 questions; "
        f"technical_status={report['technical_status']}; "
        f"human_review={report['human_label_review']}"
    )
    return 0 if report["technical_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
