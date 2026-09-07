from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from adaptive_platform.database.models import (
    Base,
    RelationshipRecord,
    RepositoryFileRecord,
    RepositoryRecord,
    RepositoryScanRecord,
    SymbolRecord,
)
from adaptive_platform.database.session import create_database_engine, create_session_factory
from adaptive_platform.extraction import RelationshipType, SymbolType
from adaptive_platform.retrieval import (
    RetrievalError,
    StructuralRetriever,
    TraversalDirection,
)
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class EvidenceGraph:
    repository_id: UUID
    scan_id: UUID
    other_repository_id: UUID
    other_scan_id: UUID
    symbols: dict[str, UUID]


@pytest.fixture
def session() -> Session:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as database_session:
        yield database_session
    engine.dispose()


@pytest.fixture
def graph(session: Session) -> EvidenceGraph:
    now = datetime.now(UTC)
    repository = RepositoryRecord(
        name="example",
        canonical_path="/fixtures/example",
        created_at=now,
        updated_at=now,
    )
    other_repository = RepositoryRecord(
        name="other",
        canonical_path="/fixtures/other",
        created_at=now,
        updated_at=now,
    )
    session.add_all([repository, other_repository])
    session.flush()
    scan = _scan(repository.id, "RUNNING", now)
    other_scan = _scan(other_repository.id, "RUNNING", now)
    session.add_all([scan, other_scan])
    session.flush()

    files = {
        "a": _file(repository.id, scan.id, "pkg/a.py", "Python"),
        "b": _file(repository.id, scan.id, "pkg/b.py", "Python"),
        "c": _file(repository.id, scan.id, "pkg/c.ts", "TypeScript"),
        "other": _file(other_repository.id, other_scan.id, "pkg/a.py", "Python"),
    }
    session.add_all(files.values())
    session.flush()
    records = {
        "a": _symbol(scan.id, files["a"].id, "run", "pkg.a.run", "FUNCTION", 10),
        "b": _symbol(scan.id, files["b"].id, "run", "pkg.b.run", "METHOD", 20),
        "c": _symbol(scan.id, files["c"].id, "Run", "pkg.c.Run", "FUNCTION", 30),
        "other": _symbol(
            other_scan.id,
            files["other"].id,
            "run",
            "pkg.a.run",
            "FUNCTION",
            10,
        ),
    }
    session.add_all(records.values())
    session.flush()
    session.add_all(
        [
            _relationship(scan.id, records["a"].id, records["b"].id, files["a"].id, "IMPORTS", 11),
            _relationship(
                scan.id,
                records["a"].id,
                None,
                files["a"].id,
                "INHERITS",
                12,
                unresolved_target="external.Base",
            ),
            _relationship(scan.id, records["b"].id, records["c"].id, files["b"].id, "REFERENCES", 21),
            _relationship(scan.id, records["c"].id, records["a"].id, files["c"].id, "TESTS", 31),
        ]
    )
    session.flush()
    scan.status = "COMPLETED"
    scan.completed_at = now
    other_scan.status = "COMPLETED"
    other_scan.completed_at = now
    session.commit()
    return EvidenceGraph(
        repository_id=repository.id,
        scan_id=scan.id,
        other_repository_id=other_repository.id,
        other_scan_id=other_scan.id,
        symbols={name: record.id for name, record in records.items()},
    )


def test_exact_lookup_is_case_sensitive_scan_bound_and_deterministic(
    session: Session,
    graph: EvidenceGraph,
) -> None:
    retriever = StructuralRetriever(session)

    first = retriever.exact_symbols(graph.repository_id, graph.scan_id, "run")
    second = retriever.exact_symbols(graph.repository_id, graph.scan_id, "run")

    assert first == second
    assert [item.qualified_name for item in first] == ["pkg.a.run", "pkg.b.run"]
    assert {item.scan_id for item in first} == {graph.scan_id}
    assert retriever.exact_symbols(graph.repository_id, graph.scan_id, "RUN") == ()
    assert retriever.exact_symbols(graph.repository_id, graph.scan_id, "pkg.a.run")[0].id == graph.symbols["a"]


def test_exact_lookup_supports_type_path_language_and_limit_filters(
    session: Session,
    graph: EvidenceGraph,
) -> None:
    retriever = StructuralRetriever(session)

    functions = retriever.exact_symbols(
        graph.repository_id,
        graph.scan_id,
        "run",
        symbol_types=(SymbolType.FUNCTION,),
    )
    method = retriever.exact_symbols(
        graph.repository_id,
        graph.scan_id,
        "run",
        symbol_types=("METHOD",),
        file_path="pkg/b.py",
        language="Python",
    )

    assert [item.id for item in functions] == [graph.symbols["a"]]
    assert [item.id for item in method] == [graph.symbols["b"]]
    assert retriever.exact_symbols(
        graph.repository_id,
        graph.scan_id,
        "run",
        language="TypeScript",
    ) == ()
    assert len(retriever.exact_symbols(graph.repository_id, graph.scan_id, "run", limit=1)) == 1


def test_outgoing_traversal_is_breadth_first_cycle_safe_and_preserves_unresolved(
    session: Session,
    graph: EvidenceGraph,
) -> None:
    results = StructuralRetriever(session).traverse(
        graph.repository_id,
        graph.scan_id,
        graph.symbols["a"],
        direction="OUTGOING",
        max_depth=3,
    )

    assert len(results) == 4
    assert len({item.relationship_id for item in results}) == 4
    assert [item.depth for item in results] == [1, 1, 2, 3]
    assert all(item.direction is TraversalDirection.OUTGOING for item in results)
    unresolved = next(item for item in results if item.unresolved_target)
    assert unresolved.target is None
    assert unresolved.unresolved_target == "external.Base"
    assert unresolved.resolution_status == "UNRESOLVED"
    assert unresolved.resolution_reason == "external_dependency"
    assert unresolved.evidence_file_path == "pkg/a.py"
    assert results[-1].target is not None
    assert results[-1].target.id == graph.symbols["a"]


def test_incoming_and_both_traversal_report_actual_edge_direction(
    session: Session,
    graph: EvidenceGraph,
) -> None:
    retriever = StructuralRetriever(session)
    incoming = retriever.traverse(
        graph.repository_id,
        graph.scan_id,
        graph.symbols["a"],
        direction=TraversalDirection.INCOMING,
        max_depth=2,
    )
    both = retriever.traverse(
        graph.repository_id,
        graph.scan_id,
        graph.symbols["a"],
        direction=TraversalDirection.BOTH,
        max_depth=1,
    )

    assert [(item.depth, item.source.id) for item in incoming] == [
        (1, graph.symbols["c"]),
        (2, graph.symbols["b"]),
    ]
    assert all(item.direction is TraversalDirection.INCOMING for item in incoming)
    assert {item.direction for item in both} == {
        TraversalDirection.INCOMING,
        TraversalDirection.OUTGOING,
    }
    assert {item.relationship_type for item in both} == {
        RelationshipType.IMPORTS,
        RelationshipType.INHERITS,
        RelationshipType.TESTS,
    }


def test_traversal_filters_relationships_and_obeys_result_limit(
    session: Session,
    graph: EvidenceGraph,
) -> None:
    retriever = StructuralRetriever(session)
    imports = retriever.traverse(
        graph.repository_id,
        graph.scan_id,
        graph.symbols["a"],
        direction="OUTGOING",
        relationship_types=(RelationshipType.IMPORTS,),
        max_depth=3,
    )
    limited = retriever.traverse(
        graph.repository_id,
        graph.scan_id,
        graph.symbols["a"],
        direction="BOTH",
        max_depth=3,
        limit=2,
    )

    assert len(imports) == 1
    assert imports[0].relationship_type is RelationshipType.IMPORTS
    assert len(limited) == 2
    assert limited == retriever.traverse(
        graph.repository_id,
        graph.scan_id,
        graph.symbols["a"],
        direction="BOTH",
        max_depth=3,
        limit=2,
    )


def test_retrieval_validates_repository_scan_and_start_symbol(
    session: Session,
    graph: EvidenceGraph,
) -> None:
    retriever = StructuralRetriever(session)

    with pytest.raises(RetrievalError, match="does not belong") as mismatch:
        retriever.exact_symbols(graph.repository_id, graph.other_scan_id, "run")
    assert mismatch.value.code == "SCAN_REPOSITORY_MISMATCH"
    assert mismatch.value.status_code == 409

    with pytest.raises(RetrievalError) as missing_symbol:
        retriever.traverse(graph.repository_id, graph.scan_id, uuid4())
    assert missing_symbol.value.code == "SYMBOL_NOT_FOUND"
    assert missing_symbol.value.status_code == 404

    with pytest.raises(RetrievalError) as missing_repository:
        retriever.exact_symbols(uuid4(), graph.scan_id, "run")
    assert missing_repository.value.code == "REPOSITORY_NOT_FOUND"

    with pytest.raises(RetrievalError) as missing_scan:
        retriever.exact_symbols(graph.repository_id, uuid4(), "run")
    assert missing_scan.value.code == "SCAN_NOT_FOUND"


def test_retrieval_rejects_incomplete_scans(session: Session) -> None:
    now = datetime.now(UTC)
    repository = RepositoryRecord(
        name="incomplete",
        canonical_path="/fixtures/incomplete",
        created_at=now,
        updated_at=now,
    )
    session.add(repository)
    session.flush()
    scan = _scan(repository.id, "RUNNING", now)
    session.add(scan)
    session.commit()

    with pytest.raises(RetrievalError) as error:
        StructuralRetriever(session).exact_symbols(repository.id, scan.id, "anything")

    assert error.value.code == "SCAN_NOT_COMPLETED"
    assert error.value.status_code == 409


@pytest.mark.parametrize("limit", [0, -1, 501, True, 1.5])
def test_invalid_limits_are_rejected(
    session: Session,
    graph: EvidenceGraph,
    limit: object,
) -> None:
    with pytest.raises(RetrievalError) as error:
        StructuralRetriever(session).exact_symbols(
            graph.repository_id,
            graph.scan_id,
            "run",
            limit=limit,  # type: ignore[arg-type]
        )
    assert error.value.code == "INVALID_RETRIEVAL_ARGUMENT"


@pytest.mark.parametrize("max_depth", [0, 4, True, 1.5])
def test_invalid_depth_and_filter_values_are_rejected(
    session: Session,
    graph: EvidenceGraph,
    max_depth: object,
) -> None:
    retriever = StructuralRetriever(session)
    with pytest.raises(RetrievalError) as error:
        retriever.traverse(
            graph.repository_id,
            graph.scan_id,
            graph.symbols["a"],
            max_depth=max_depth,  # type: ignore[arg-type]
        )
    assert error.value.code == "INVALID_RETRIEVAL_ARGUMENT"

    with pytest.raises(RetrievalError):
        retriever.traverse(
            graph.repository_id,
            graph.scan_id,
            graph.symbols["a"],
            relationship_types=("CALLS",),
        )
    with pytest.raises(RetrievalError):
        retriever.exact_symbols(
            graph.repository_id,
            graph.scan_id,
            "run",
            symbol_types=("VARIABLE",),
        )
    with pytest.raises(RetrievalError):
        retriever.traverse(
            graph.repository_id,
            graph.scan_id,
            graph.symbols["a"],
            direction="SIDEWAYS",
        )
    with pytest.raises(RetrievalError):
        retriever.traverse(
            graph.repository_id,
            graph.scan_id,
            graph.symbols["a"],
            limit=501,
        )


def _scan(repository_id: UUID, status: str, now: datetime) -> RepositoryScanRecord:
    return RepositoryScanRecord(
        repository_id=repository_id,
        status=status,
        scanner_version="test",
        configuration_version="test",
        started_at=now,
    )


def _file(
    repository_id: UUID,
    scan_id: UUID,
    path: str,
    language: str,
) -> RepositoryFileRecord:
    return RepositoryFileRecord(
        repository_id=repository_id,
        scan_id=scan_id,
        path=path,
        language=language,
        category="SOURCE",
        content_hash="a" * 64,
        size=10,
        encoding="utf-8",
        is_generated=False,
        is_vendored=False,
    )


def _symbol(
    scan_id: UUID,
    file_id: UUID,
    name: str,
    qualified_name: str,
    symbol_type: str,
    line: int,
) -> SymbolRecord:
    return SymbolRecord(
        scan_id=scan_id,
        file_id=file_id,
        name=name,
        qualified_name=qualified_name,
        symbol_type=symbol_type,
        start_line=line,
        start_column=0,
        end_line=line,
        end_column=10,
        extractor_name="fixture",
        extractor_version="1",
        extension_metadata={},
    )


def _relationship(
    scan_id: UUID,
    source_id: UUID,
    target_id: UUID | None,
    evidence_file_id: UUID,
    relationship_type: str,
    line: int,
    unresolved_target: str | None = None,
) -> RelationshipRecord:
    unresolved = target_id is None
    return RelationshipRecord(
        scan_id=scan_id,
        source_kind="SYMBOL",
        source_id=source_id,
        target_kind="SYMBOL",
        target_id=target_id,
        unresolved_target=unresolved_target,
        relationship_type=relationship_type,
        resolution_status="UNRESOLVED" if unresolved else "RESOLVED",
        resolution_reason="external_dependency" if unresolved else None,
        confidence=0.5 if unresolved else 1.0,
        evidence_type="SYNTAX_FACT",
        provenance="RECORDED",
        evidence_file_id=evidence_file_id,
        evidence_start_line=line,
        evidence_start_column=0,
        evidence_end_line=line,
        evidence_end_column=10,
        extractor_name="fixture",
        extractor_version="1",
        extension_metadata={},
    )
