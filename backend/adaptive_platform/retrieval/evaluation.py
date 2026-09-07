from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from adaptive_platform.database import Base, create_database_engine
from adaptive_platform.database.models import (
    RepositoryFileRecord,
    RepositoryRecord,
    RepositoryScanRecord,
    SymbolRecord,
)
from adaptive_platform.evaluation.loader import load_json
from adaptive_platform.evaluation.metrics import precision_recall
from adaptive_platform.extraction import ExtractionDocument, ExtractionRequest, PythonAstExtractor
from adaptive_platform.retrieval import RetrievalError, StructuralRetriever
from adaptive_platform.services.repositories import _persist_extraction_result
from adaptive_platform.traces import ActorType, JsonlTraceRecorder, TraceCategory, TraceEvent


def _now() -> datetime:
    return datetime.now(UTC)


def _fixture_session(repository: Path, fixture_id: str) -> tuple[Session, UUID, UUID]:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    repository_id = uuid5(NAMESPACE_URL, f"retrieval-repository:{fixture_id}")
    scan_id = uuid5(NAMESPACE_URL, f"retrieval-scan:{fixture_id}")
    session.add(
        RepositoryRecord(
            id=repository_id,
            name=fixture_id,
            canonical_path=str(repository.resolve()),
            default_branch=None,
            created_at=_now(),
            updated_at=_now(),
        )
    )
    scan = RepositoryScanRecord(
        id=scan_id,
        repository_id=repository_id,
        status="RUNNING",
        scanner_version="retrieval-evaluation",
        configuration_version="retrieval-evaluation-v1",
        started_at=_now(),
        file_count=0,
        total_bytes=0,
    )
    session.add(scan)
    documents: list[ExtractionDocument] = []
    total_bytes = 0
    for source in sorted(repository.rglob("*.py")):
        relative = source.relative_to(repository)
        content = source.read_bytes()
        total_bytes += len(content)
        file_id = uuid5(NAMESPACE_URL, f"retrieval-file:{fixture_id}:{relative.as_posix()}")
        digest = hashlib.sha256(content).hexdigest()
        session.add(
            RepositoryFileRecord(
                id=file_id,
                repository_id=repository_id,
                scan_id=scan_id,
                path=relative.as_posix(),
                language="Python",
                category="TEST" if relative.parts[0] == "tests" else "SOURCE",
                content_hash=digest,
                size=len(content),
                encoding="utf-8",
                is_generated=False,
                is_vendored=False,
                detection_signal="extension:.py",
                secret_finding_count=0,
            )
        )
        documents.append(
            ExtractionDocument(
                file_id=file_id,
                path=relative,
                language="Python",
                content_hash=digest,
                content=content.decode("utf-8"),
            )
        )
    session.flush()
    extraction = PythonAstExtractor().extract(
        ExtractionRequest(
            repository_id=repository_id,
            scan_id=scan_id,
            documents=tuple(documents),
        )
    )
    _persist_extraction_result(session, scan_id, extraction)
    session.flush()
    scan.file_count = len(documents)
    scan.total_bytes = total_bytes
    scan.commit_hash = hashlib.sha1(fixture_id.encode()).hexdigest()
    scan.working_tree_fingerprint = hashlib.sha256(fixture_id.encode()).hexdigest()
    scan.is_dirty = False
    scan.completed_at = _now()
    scan.status = "COMPLETED"
    session.commit()
    return session, repository_id, scan_id


def _edge_identity(edge: Any) -> tuple[str | None, str, str | None, str | None, int]:
    return (
        edge.source.qualified_name,
        edge.relationship_type.value,
        edge.target.qualified_name if edge.target else None,
        edge.unresolved_target,
        edge.depth,
    )


def build_report(project_root: Path) -> dict[str, Any]:
    cases = load_json(project_root / "evaluation" / "retrieval-cases.json")
    by_fixture: dict[str, tuple[Session, UUID, UUID]] = {}
    exact_results: list[dict[str, Any]] = []
    graph_results: list[dict[str, Any]] = []
    all_actual_edges: list[Any] = []
    deterministic = True
    isolation_rejected = True
    bounds_rejected = True
    citation_valid = True
    try:
        fixture_ids = {
            str(item["fixture"]) for kind in ("exact_cases", "graph_cases") for item in cases[kind]
        }
        for fixture_id in sorted(fixture_ids):
            repository = project_root / "evaluation" / "fixtures" / fixture_id / "repository"
            by_fixture[fixture_id] = _fixture_session(repository, fixture_id)

        for case in cases["exact_cases"]:
            session, repository_id, scan_id = by_fixture[case["fixture"]]
            retriever = StructuralRetriever(session)
            arguments = {
                "repository_id": repository_id,
                "scan_id": scan_id,
                "query": case["query"],
                "symbol_types": case.get("symbol_types") or (),
                "file_path": case.get("file_path"),
                "language": case.get("language"),
                "limit": 20,
            }
            first = retriever.exact_symbols(**arguments)
            second = retriever.exact_symbols(**arguments)
            deterministic = deterministic and first == second
            expected = set(case["expected_qualified_names"])
            actual = {item.qualified_name for item in first}
            exact_results.append(
                {
                    "id": case["id"],
                    "metrics": precision_recall(expected, actual).to_dict(),
                    "actual_qualified_names": sorted(actual),
                }
            )

        for case in cases["graph_cases"]:
            session, repository_id, scan_id = by_fixture[case["fixture"]]
            start_id = session.scalar(
                select(SymbolRecord.id).where(
                    SymbolRecord.scan_id == scan_id,
                    SymbolRecord.qualified_name == case["start_qualified_name"],
                )
            )
            if start_id is None:
                raise RuntimeError(f"Missing start symbol for {case['id']}")
            retriever = StructuralRetriever(session)
            arguments = {
                "repository_id": repository_id,
                "scan_id": scan_id,
                "start_symbol_id": start_id,
                "direction": case["direction"],
                "relationship_types": case["relationship_types"],
                "max_depth": case["max_depth"],
                "limit": 100,
            }
            first = retriever.traverse(**arguments)
            second = retriever.traverse(**arguments)
            deterministic = deterministic and first == second
            expected = {tuple(item) for item in case["expected_edges"]}
            actual = {_edge_identity(item) for item in first}
            all_actual_edges.extend(first)
            graph_results.append(
                {
                    "id": case["id"],
                    "metrics": precision_recall(expected, actual).to_dict(),
                    "actual_edges": [list(item) for item in sorted(actual, key=str)],
                }
            )

        first_session, _, first_scan_id = next(iter(by_fixture.values()))
        unrelated_repository_id = uuid4()
        first_session.add(
            RepositoryRecord(
                id=unrelated_repository_id,
                name="unrelated",
                canonical_path=f"/evaluation/unrelated/{unrelated_repository_id}",
                default_branch=None,
                created_at=_now(),
                updated_at=_now(),
            )
        )
        first_session.commit()
        try:
            StructuralRetriever(first_session).exact_symbols(
                unrelated_repository_id,
                first_scan_id,
                "anything",
            )
            isolation_rejected = False
        except RetrievalError as error:
            isolation_rejected = error.code == "SCAN_REPOSITORY_MISMATCH"

        try:
            session, repository_id, scan_id = by_fixture["fx-small"]
            start_id = session.scalar(
                select(SymbolRecord.id).where(
                    SymbolRecord.scan_id == scan_id,
                    SymbolRecord.qualified_name == "app",
                )
            )
            StructuralRetriever(session).traverse(
                repository_id,
                scan_id,
                start_id,
                max_depth=4,
            )
            bounds_rejected = False
        except RetrievalError as error:
            bounds_rejected = error.code == "INVALID_RETRIEVAL_ARGUMENT"

        session_by_scan = {scan_id: session for session, _, scan_id in by_fixture.values()}
        for edge in all_actual_edges:
            session = session_by_scan[edge.scan_id]
            file_record = session.get(RepositoryFileRecord, edge.evidence_file_id)
            if file_record is None:
                citation_valid = False
                continue
            source = Path(file_record.scan.repository.canonical_path) / file_record.path
            line_count = len(
                source.read_text(encoding=file_record.encoding or "utf-8").splitlines()
            )
            citation_valid = citation_valid and 1 <= edge.evidence_start_line <= line_count
    finally:
        for session, _, _ in by_fixture.values():
            session.close()

    gates: list[dict[str, Any]] = []
    for result in exact_results:
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
    for result in graph_results:
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
        ("deterministic_ordering", deterministic),
        ("scan_isolation", isolation_rejected),
        ("bound_enforcement", bounds_rejected),
        ("citation_validity", citation_valid),
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
        "milestone": "M3A_M3B_STRUCTURAL_RETRIEVAL",
        "technical_status": "PASS" if all(item["status"] == "PASS" for item in gates) else "FAIL",
        "human_label_review": review["status"],
        "exact_cases": exact_results,
        "graph_cases": graph_results,
        "gates": gates,
        "limits": {"max_traversal_depth": 3, "max_results": 500},
        "full_text_status": "DEFERRED_TO_M3C",
    }


def main() -> int:
    project_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description="Run M3A/M3B structural retrieval evaluation")
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root / "evaluation" / "baselines" / "milestone3ab.json",
    )
    parser.add_argument(
        "--trace-output",
        type=Path,
        default=project_root / "evaluation" / "baselines" / "milestone3ab.trace.jsonl",
    )
    args = parser.parse_args()
    report = build_report(project_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    recorder = JsonlTraceRecorder(args.trace_output)
    correlation_id = str(uuid4())
    task_id = f"evaluation:milestone3ab:{report['generated_at']}"
    recorder.append(
        TraceEvent(
            task_id=task_id,
            correlation_id=correlation_id,
            category=TraceCategory.EXECUTION,
            event_type="structural_retrieval_evaluation_started",
            actor_type=ActorType.SYSTEM,
            summary="Started M3A/M3B exact and graph retrieval evaluation.",
            input_refs=("evaluation/retrieval-cases.json", "evaluation/fixtures"),
        )
    )
    recorder.append(
        TraceEvent(
            task_id=task_id,
            correlation_id=correlation_id,
            category=TraceCategory.VERIFICATION,
            event_type="structural_retrieval_gates_evaluated",
            actor_type=ActorType.SYSTEM,
            summary="Evaluated exact lookup, graph traversal, isolation, bounds and citations.",
            output_refs=("evaluation/baselines/milestone3ab.json",),
            metadata={"technical_status": report["technical_status"], "gates": report["gates"]},
        )
    )
    print(
        f"evaluated {len(report['exact_cases'])} exact and {len(report['graph_cases'])} graph cases; "
        f"technical_status={report['technical_status']}; "
        f"human_review={report['human_label_review']}"
    )
    return 0 if report["technical_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
