from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import inspect, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from adaptive_platform.config import get_settings
from adaptive_platform.database import create_database_engine
from adaptive_platform.database.models import (
    ContextDocumentRecord,
    RepositoryFileRecord,
    RepositoryRecord,
    RepositoryScanRecord,
    TraceEventRecord,
)
from adaptive_platform.evaluation.loader import load_json
from adaptive_platform.evaluation.metrics import precision_recall
from adaptive_platform.languages import detect_language, is_generated_path, is_vendored_path
from adaptive_platform.retrieval import FullTextEngine, FullTextRetriever, RetrievalError
from adaptive_platform.retrieval.indexing import persist_context_documents
from adaptive_platform.traces import ActorType, JsonlTraceRecorder, TraceCategory, TraceEvent

DEPENDENCY_FILES = frozenset(
    {"package.json", "pyproject.toml", "go.mod", "Cargo.toml", "pom.xml"}
)
DOCUMENTATION_SUFFIXES = frozenset({".md", ".mdx", ".rst", ".txt"})
CONFIGURATION_SUFFIXES = frozenset({".ini", ".json", ".toml", ".yaml", ".yml"})


def _now() -> datetime:
    return datetime.now(UTC)


def _category(path: PurePosixPath, language: str | None) -> str:
    if path.name in DEPENDENCY_FILES:
        return "DEPENDENCY"
    if "test" in path.name.lower() or "tests" in {part.lower() for part in path.parts}:
        return "TEST"
    if language is not None:
        return "SOURCE"
    if path.suffix.lower() in DOCUMENTATION_SUFFIXES:
        return "DOCUMENTATION"
    if path.suffix.lower() in CONFIGURATION_SUFFIXES:
        return "CONFIGURATION"
    return "OTHER"


def _load_fixture(
    session: Session,
    repository_root: Path,
    fixture_id: str,
) -> tuple[UUID, UUID, int]:
    repository_id = uuid4()
    scan_id = uuid4()
    now = _now()
    session.add(
        RepositoryRecord(
            id=repository_id,
            name=fixture_id,
            canonical_path=str(repository_root.resolve()),
            default_branch=None,
            created_at=now,
            updated_at=now,
        )
    )
    scan = RepositoryScanRecord(
        id=scan_id,
        repository_id=repository_id,
        status="RUNNING",
        scanner_version="m3c-evaluation",
        configuration_version="m3c-evaluation-v1",
        started_at=now,
        file_count=0,
        total_bytes=0,
    )
    session.add(scan)
    files: list[RepositoryFileRecord] = []
    total_bytes = 0
    for source in sorted(repository_root.rglob("*")):
        if not source.is_file():
            continue
        relative = PurePosixPath(source.relative_to(repository_root).as_posix())
        raw = source.read_bytes()
        if b"\x00" in raw[:8192]:
            continue
        content = raw.decode("utf-8")
        detection = detect_language(relative, content)
        total_bytes += len(raw)
        record = RepositoryFileRecord(
            id=uuid5(NAMESPACE_URL, f"m3c:{fixture_id}:{relative.as_posix()}"),
            repository_id=repository_id,
            scan_id=scan_id,
            path=relative.as_posix(),
            language=detection.language,
            category=_category(relative, detection.language),
            content_hash=hashlib.sha256(raw).hexdigest(),
            size=len(raw),
            encoding="utf-8",
            is_generated=is_generated_path(relative),
            is_vendored=is_vendored_path(relative),
            detection_signal=detection.signal,
            secret_finding_count=0,
        )
        session.add(record)
        files.append(record)
    session.flush()
    build = persist_context_documents(
        session,
        repository_root=repository_root,
        scan_id=scan_id,
        files=files,
    )
    session.add(
        TraceEventRecord(
            task_id=f"m3c-evaluation:{scan_id}",
            repository_id=repository_id,
            scan_id=scan_id,
            category="VERIFICATION",
            event_type="context_documents_created",
            actor_type="SYSTEM",
            occurred_at=_now(),
            summary="Created M3C evaluation context documents.",
            input_refs=[],
            output_refs=[],
            event_metadata={"document_count": len(build.documents)},
        )
    )
    scan.commit_hash = hashlib.sha1(fixture_id.encode()).hexdigest()
    scan.working_tree_fingerprint = hashlib.sha256(fixture_id.encode()).hexdigest()
    scan.is_dirty = False
    scan.file_count = len(files)
    scan.total_bytes = total_bytes
    scan.completed_at = _now()
    scan.status = "COMPLETED"
    session.flush()
    return repository_id, scan_id, len(build.documents)


def build_report(project_root: Path, database_url: str) -> dict[str, Any]:
    engine = create_database_engine(database_url)
    if engine.dialect.name != "postgresql":
        engine.dispose()
        raise RuntimeError("M3C evaluation requires PostgreSQL")
    if not inspect(engine).has_table("context_documents"):
        engine.dispose()
        raise RuntimeError("M3C migration is required; run alembic upgrade head")

    cases = load_json(project_root / "evaluation" / "full-text-cases.json")
    results: list[dict[str, Any]] = []
    deterministic = True
    citations_valid = True
    isolation_rejected = True
    bounds_rejected = True
    exclusions_hold = True
    engine_verified = True
    immutability_rejected = True
    vectors_populated = True
    fixture_scope: dict[str, tuple[UUID, UUID, int]] = {}
    session = Session(engine)
    try:
        fixtures = {
            str(item["fixture"])
            for group in (cases["cases"], cases["excluded_queries"])
            for item in group
        }
        for fixture_id in sorted(fixtures):
            root = project_root / "evaluation" / "fixtures" / fixture_id / "repository"
            fixture_scope[fixture_id] = _load_fixture(session, root, fixture_id)

        for case in cases["cases"]:
            repository_id, scan_id, _ = fixture_scope[case["fixture"]]
            retriever = FullTextRetriever(session)
            first = retriever.search(
                repository_id,
                scan_id,
                case["query"],
                **case.get("filters", {}),
            )
            second = retriever.search(
                repository_id,
                scan_id,
                case["query"],
                **case.get("filters", {}),
            )
            deterministic = deterministic and first == second
            engine_verified = engine_verified and all(
                item.retrieval_engine is FullTextEngine.POSTGRESQL for item in first
            )
            expected = set(case["expected_paths"])
            actual = {item.file_path for item in first}
            metrics = precision_recall(expected, actual).to_dict()
            results.append(
                {
                    "id": case["id"],
                    "metrics": metrics,
                    "actual_paths": sorted(actual),
                    "hit_count": len(first),
                }
            )
            repository_root = (
                project_root / "evaluation" / "fixtures" / case["fixture"] / "repository"
            )
            for hit in first:
                path = repository_root / hit.file_path
                line_count = len(path.read_text(encoding="utf-8").splitlines())
                citations_valid = citations_valid and (
                    1 <= hit.start_line <= hit.end_line <= max(1, line_count)
                )

        for case in cases["excluded_queries"]:
            repository_id, scan_id, _ = fixture_scope[case["fixture"]]
            excluded = FullTextRetriever(session).search(
                repository_id,
                scan_id,
                case["query"],
            )
            exclusions_hold = exclusions_hold and not excluded

        first_fixture, second_fixture = sorted(fixture_scope)[:2]
        _, first_scan_id, _ = fixture_scope[first_fixture]
        second_repository_id, _, _ = fixture_scope[second_fixture]
        try:
            FullTextRetriever(session).search(
                second_repository_id,
                first_scan_id,
                "anything",
            )
            isolation_rejected = False
        except RetrievalError as error:
            isolation_rejected = error.code == "SCAN_REPOSITORY_MISMATCH"

        repository_id, scan_id, _ = fixture_scope[first_fixture]
        try:
            FullTextRetriever(session).search(repository_id, scan_id, "anything", limit=101)
            bounds_rejected = False
        except RetrievalError as error:
            bounds_rejected = error.code == "INVALID_RETRIEVAL_ARGUMENT"

        gin_definition = session.scalar(
            text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE schemaname = current_schema() "
                "AND indexname = 'ix_context_documents_search_vector'"
            )
        )
        gin_verified = bool(gin_definition and "USING gin" in gin_definition)
        vectors_populated = (
            session.scalar(
                text("SELECT count(*) FROM context_documents WHERE search_vector IS NULL")
            )
            == 0
        )
        try:
            with session.begin_nested():
                session.execute(
                    update(ContextDocumentRecord)
                    .where(ContextDocumentRecord.scan_id == scan_id)
                    .values(content="forbidden completed-scan mutation")
                )
            immutability_rejected = False
        except DBAPIError:
            session.expire_all()
    finally:
        session.rollback()
        session.close()
        engine.dispose()

    polyglot_results = [item for item in results if item["id"].startswith("fx-polyglot-")]
    polyglot_verified = len(polyglot_results) == 2 and all(
        item["metrics"]["precision"] == 1.0 and item["metrics"]["recall"] == 1.0
        for item in polyglot_results
    )
    gates: list[dict[str, Any]] = []
    for result in results:
        for metric in ("precision", "recall"):
            value = result["metrics"][metric]
            gates.append(
                {
                    "gate": f"{result['id']}.{metric}",
                    "value": value,
                    "threshold": 1.0,
                    "status": "PASS" if value == 1.0 else "FAIL",
                }
            )
    for name, value in (
        ("postgresql_engine", engine_verified),
        ("gin_index", gin_verified),
        ("search_vectors_populated", vectors_populated),
        ("postgresql_immutability_trigger", immutability_rejected),
        ("deterministic_ordering", deterministic),
        ("scan_isolation", isolation_rejected),
        ("bound_enforcement", bounds_rejected),
        ("citation_validity", citations_valid),
        ("generated_and_vendored_exclusion", exclusions_hold),
        ("polyglot_language_coverage", polyglot_verified),
    ):
        gates.append(
            {
                "gate": name,
                "value": 1.0 if value else 0.0,
                "threshold": 1.0,
                "status": "PASS" if value else "FAIL",
            }
        )
    review = load_json(project_root / "evaluation" / "review.json")
    return {
        "schema_version": "1.0.0",
        "generated_at": _now().isoformat(),
        "milestone": "M3C_POSTGRESQL_FULL_TEXT_RETRIEVAL",
        "technical_status": "PASS" if all(item["status"] == "PASS" for item in gates) else "FAIL",
        "human_label_review": review["status"],
        "retrieval_engine": FullTextEngine.POSTGRESQL.value,
        "search_configuration": "simple",
        "cases": results,
        "gates": gates,
        "limits": {"max_query_characters": 256, "max_results": 100},
        "document_counts": {
            fixture: count for fixture, (_, _, count) in sorted(fixture_scope.items())
        },
    }


def main() -> int:
    project_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description="Run M3C PostgreSQL full-text evaluation")
    parser.add_argument("--database-url", default=get_settings().database_url)
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root / "evaluation" / "baselines" / "milestone3c.json",
    )
    parser.add_argument(
        "--trace-output",
        type=Path,
        default=project_root / "evaluation" / "baselines" / "milestone3c.trace.jsonl",
    )
    args = parser.parse_args()
    report = build_report(project_root, args.database_url)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    recorder = JsonlTraceRecorder(args.trace_output)
    correlation_id = str(uuid4())
    task_id = f"evaluation:milestone3c:{report['generated_at']}"
    recorder.append(
        TraceEvent(
            task_id=task_id,
            correlation_id=correlation_id,
            category=TraceCategory.EXECUTION,
            event_type="postgresql_full_text_evaluation_started",
            actor_type=ActorType.SYSTEM,
            summary="Started M3C PostgreSQL lexical retrieval evaluation.",
            input_refs=("evaluation/full-text-cases.json", "evaluation/fixtures"),
        )
    )
    recorder.append(
        TraceEvent(
            task_id=task_id,
            correlation_id=correlation_id,
            category=TraceCategory.VERIFICATION,
            event_type="postgresql_full_text_gates_evaluated",
            actor_type=ActorType.SYSTEM,
            summary="Evaluated M3C ranking, scope, safety, citations, limits, and polyglot coverage.",
            output_refs=("evaluation/baselines/milestone3c.json",),
            metadata={"technical_status": report["technical_status"], "gates": report["gates"]},
        )
    )
    print(
        f"evaluated {len(report['cases'])} PostgreSQL full-text cases; "
        f"technical_status={report['technical_status']}; "
        f"human_review={report['human_label_review']}"
    )
    return 0 if report["technical_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
