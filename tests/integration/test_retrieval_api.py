from __future__ import annotations

import subprocess
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from adaptive_platform.app import create_app
from adaptive_platform.config import Settings
from adaptive_platform.database import Base, create_database_engine
from adaptive_platform.database.models import ContextDocumentRecord, TraceEventRecord
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session


def git(root: Path, *arguments: str) -> None:
    subprocess.run(["git", "-C", str(root), *arguments], check=True, capture_output=True)


def create_repository(root: Path, *, marker: str = "primary") -> Path:
    root.mkdir()
    git(root, "init", "--quiet")
    git(root, "config", "user.email", "fixture@example.test")
    git(root, "config", "user.name", "Fixture")
    (root / "core.py").write_text(
        '"""Shared domain types."""\n\n'
        "class Entity:\n"
        f'    """Entity from {marker}."""\n'
        "\n"
        "    pass\n"
    )
    (root / "service.py").write_text(
        "import missing_package\n"
        "from core import Entity\n"
        "\n"
        "\n"
        "class Service(Entity):\n"
        "    def fetch(self) -> Entity:\n"
        "        return Entity()\n"
    )
    tests_directory = root / "tests"
    tests_directory.mkdir()
    (tests_directory / "test_service.py").write_text(
        "from service import Service\n"
        "\n"
        "\n"
        "def test_fetch() -> None:\n"
        "    assert isinstance(Service().fetch(), object)\n"
    )
    (root / "web.ts").write_text(
        "export function dashboardHealth(): string {\n"
        f'  return "{marker} dashboard healthy";\n'
        "}\n"
    )
    (root / "tool.go").write_text(
        "package main\n\n"
        "func RepositoryAudit() string {\n"
        f'    return "{marker} repository audit"\n'
        "}\n"
    )
    (root / "README.md").write_text(f"# {marker} operational playbook\n")
    (root / "settings.toml").write_text('api_key = "secret-example-value"\n')
    git(root, "add", ".")
    git(root, "commit", "--quiet", "-m", "retrieval fixture")
    return root


@pytest.fixture
def retrieval_client(tmp_path: Path):
    first_repository = create_repository(tmp_path / "first-repository")
    second_repository = create_repository(tmp_path / "second-repository", marker="secondary")
    database_path = tmp_path / "retrieval.db"
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{database_path}",
        allowed_repository_roots=str(tmp_path),
    )
    engine = create_database_engine(settings.database_url)
    Base.metadata.create_all(engine)
    app = create_app(settings, engine=engine)
    with TestClient(app) as client:
        first_repository_id = client.post(
            "/repositories", json={"path": str(first_repository)}
        ).json()["id"]
        second_repository_id = client.post(
            "/repositories", json={"path": str(second_repository)}
        ).json()["id"]
        first_scan_id = client.post(
            f"/repositories/{first_repository_id}/scans", json={}
        ).json()["id"]
        second_scan_id = client.post(
            f"/repositories/{second_repository_id}/scans", json={}
        ).json()["id"]
        yield client, {
            "database_url": settings.database_url,
            "first_repository_id": first_repository_id,
            "second_repository_id": second_repository_id,
            "first_scan_id": first_scan_id,
            "second_scan_id": second_scan_id,
        }


def exact_url(ids: dict[str, str], query: str, *, second: bool = False) -> str:
    prefix = "second" if second else "first"
    return (
        f"/repositories/{ids[f'{prefix}_repository_id']}"
        f"/scans/{ids[f'{prefix}_scan_id']}/retrieval/symbols?query={query}"
    )


def text_url(ids: dict[str, str], query: str, *, second: bool = False) -> str:
    prefix = "second" if second else "first"
    return (
        f"/repositories/{ids[f'{prefix}_repository_id']}"
        f"/scans/{ids[f'{prefix}_scan_id']}/retrieval/text?query={query}"
    )


def symbol_id(client: TestClient, ids: dict[str, str], query: str) -> str:
    response = client.get(exact_url(ids, query))
    assert response.status_code == 200
    hits = response.json()["hits"]
    assert len(hits) == 1
    return hits[0]["id"]


def neighbor_url(
    ids: dict[str, str],
    start_symbol_id: str,
    parameters: str = "",
) -> str:
    return (
        f"/repositories/{ids['first_repository_id']}"
        f"/scans/{ids['first_scan_id']}/symbols/{start_symbol_id}/neighbors{parameters}"
    )


def test_exact_symbol_retrieval_is_scan_bound_and_deterministic(retrieval_client) -> None:
    client, ids = retrieval_client
    url = exact_url(ids, "Service")

    first = client.get(url)
    repeated = client.get(url)

    assert first.status_code == 200
    assert first.json() == repeated.json()
    payload = first.json()
    assert payload["repository_id"] == ids["first_repository_id"]
    assert payload["scan_id"] == ids["first_scan_id"]
    assert payload["query"] == "Service"
    assert payload["count"] == 1
    assert payload["hits"][0]["qualified_name"] == "service.Service"
    assert payload["hits"][0]["file_path"] == "service.py"
    assert payload["hits"][0]["symbol_type"] == "CLASS"
    assert payload["hits"][0]["scan_id"] == ids["first_scan_id"]

    with Session(create_database_engine(ids["database_url"])) as session:
        events = list(
            session.scalars(
                select(TraceEventRecord)
                .where(TraceEventRecord.event_type == "exact_symbol_retrieval_completed")
                .order_by(TraceEventRecord.occurred_at)
            )
        )
    assert len(events) == 2
    assert all(event.category == "RETRIEVAL" for event in events)
    assert all(event.event_metadata["raw_query_retained"] is False for event in events)
    assert all("query" not in event.event_metadata for event in events)
    assert all(len(event.event_metadata["query_sha256"]) == 64 for event in events)

    qualified = client.get(exact_url(ids, "service.Service"))
    partial = client.get(exact_url(ids, "Serv"))
    assert qualified.json()["hits"] == payload["hits"]
    assert partial.json()["hits"] == []


def test_exact_symbol_retrieval_applies_all_filters(retrieval_client) -> None:
    client, ids = retrieval_client
    base_url = exact_url(ids, "Service")

    accepted = client.get(
        f"{base_url}&symbol_type=FUNCTION&symbol_type=CLASS"
        "&file_path=service.py&language=Python&limit=1"
    )
    wrong_type = client.get(f"{base_url}&symbol_type=FUNCTION")
    wrong_path = client.get(f"{base_url}&file_path=core.py")
    wrong_language = client.get(f"{base_url}&language=Go")

    assert accepted.status_code == 200
    assert accepted.json()["count"] == 1
    assert wrong_type.json()["hits"] == []
    assert wrong_path.json()["hits"] == []
    assert wrong_language.json()["hits"] == []


def test_full_text_retrieval_is_bounded_cited_and_language_neutral(retrieval_client) -> None:
    client, ids = retrieval_client
    search_url = text_url(ids, "dashboard+healthy")

    first = client.get(search_url)
    repeated = client.get(search_url)

    assert first.status_code == 200
    assert first.json() == repeated.json()
    payload = first.json()
    assert payload["repository_id"] == ids["first_repository_id"]
    assert payload["scan_id"] == ids["first_scan_id"]
    assert payload["retrieval_engine"] == "SQLITE_TEST_FALLBACK"
    assert payload["count"] >= 1
    assert {hit["file_path"] for hit in payload["hits"]} == {"web.ts"}
    assert all(hit["language"] == "TypeScript" for hit in payload["hits"])
    assert all(hit["start_line"] >= 1 for hit in payload["hits"])
    assert all(hit["end_line"] >= hit["start_line"] for hit in payload["hits"])
    assert all(len(hit["content_hash"]) == 64 for hit in payload["hits"])

    filtered = client.get(
        f"{search_url}&document_type=MODULE&category=SOURCE"
        "&language=TypeScript&file_path=web.ts&limit=1"
    )
    wrong_language = client.get(f"{search_url}&language=Python")
    unsupported_adapter_language = client.get(f"{text_url(ids, 'repository+audit')}&language=Go")
    documentation = client.get(text_url(ids, "operational+playbook"))
    secret = client.get(text_url(ids, "secret-example-value"))

    assert filtered.status_code == 200
    assert filtered.json()["count"] == 1
    assert wrong_language.json()["hits"] == []
    assert {hit["file_path"] for hit in unsupported_adapter_language.json()["hits"]} == {
        "tool.go"
    }
    assert {hit["document_type"] for hit in documentation.json()["hits"]} == {
        "DOCUMENTATION_SECTION"
    }
    assert secret.json()["hits"] == []

    with Session(create_database_engine(ids["database_url"])) as session:
        events = list(
            session.scalars(
                select(TraceEventRecord).where(
                    TraceEventRecord.event_type == "full_text_retrieval_completed"
                )
            )
        )
        secret_documents = list(
            session.scalars(
                select(ContextDocumentRecord).where(
                    ContextDocumentRecord.content.contains("secret-example-value")
                )
            )
        )
    assert events
    assert all(event.event_metadata["raw_query_retained"] is False for event in events)
    assert all("query" not in event.event_metadata for event in events)
    assert secret_documents == []

    with Session(create_database_engine(ids["database_url"])) as session:
        document = session.scalar(
            select(ContextDocumentRecord).where(
                ContextDocumentRecord.scan_id == UUID(ids["first_scan_id"])
            )
        )
        assert document is not None
        document.content = "changed"
        with pytest.raises(ValueError, match="immutable"):
            session.commit()


def test_full_text_retrieval_rejects_invalid_filters_bounds_and_scope(retrieval_client) -> None:
    client, ids = retrieval_client

    invalid_type = client.get(text_url(ids, "dashboard") + "&document_type=ROUTE")
    invalid_category = client.get(text_url(ids, "dashboard") + "&category=OTHER")
    invalid_limit = client.get(text_url(ids, "dashboard") + "&limit=101")
    oversized_query = client.get(text_url(ids, "x" * 257))
    mismatch = client.get(
        f"/repositories/{ids['first_repository_id']}"
        f"/scans/{ids['second_scan_id']}/retrieval/text?query=dashboard"
    )

    for response in (invalid_type, invalid_category, invalid_limit, oversized_query):
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INVALID_RETRIEVAL_ARGUMENT"
    assert mismatch.status_code == 409
    assert mismatch.json()["error"]["code"] == "SCAN_REPOSITORY_MISMATCH"


def test_outgoing_traversal_preserves_unresolved_targets_and_evidence(retrieval_client) -> None:
    client, ids = retrieval_client
    service_module_id = symbol_id(client, ids, "service")

    response = client.get(
        neighbor_url(
            ids,
            service_module_id,
            "?direction=OUTGOING&relationship_type=IMPORTS&max_depth=1",
        )
    )
    repeated = client.get(
        neighbor_url(
            ids,
            service_module_id,
            "?direction=OUTGOING&relationship_type=IMPORTS&max_depth=1",
        )
    )

    assert response.status_code == 200
    assert response.json() == repeated.json()
    payload = response.json()
    assert payload["start_symbol_id"] == service_module_id
    assert payload["direction"] == "OUTGOING"
    assert payload["max_depth"] == 1
    assert payload["count"] == 2
    assert [edge["depth"] for edge in payload["edges"]] == [1, 1]
    unresolved = next(edge for edge in payload["edges"] if edge["target"] is None)
    assert unresolved["unresolved_target"] == "missing_package"
    assert unresolved["resolution_status"] == "UNRESOLVED"
    assert unresolved["resolution_reason"] == "external_dependency"
    assert unresolved["evidence_file_path"] == "service.py"
    assert unresolved["evidence_start_line"] == 1
    assert unresolved["direction"] == "OUTGOING"
    assert unresolved["source"]["qualified_name"] == "service"
    assert all(edge["scan_id"] == ids["first_scan_id"] for edge in payload["edges"])
    assert all(node["scan_id"] == ids["first_scan_id"] for node in payload["nodes"])


def test_graph_direction_relationship_filter_depth_and_limit(retrieval_client) -> None:
    client, ids = retrieval_client
    entity_id = symbol_id(client, ids, "core.Entity")
    test_module_id = symbol_id(client, ids, "tests.test_service")

    incoming = client.get(neighbor_url(ids, entity_id, "?direction=INCOMING&max_depth=1"))
    inheritance = client.get(
        neighbor_url(
            ids,
            entity_id,
            "?direction=INCOMING&relationship_type=INHERITS&max_depth=1",
        )
    )
    two_hops = client.get(
        neighbor_url(ids, test_module_id, "?direction=OUTGOING&max_depth=2")
    )
    limited = client.get(
        neighbor_url(ids, entity_id, "?direction=INCOMING&max_depth=2&limit=1")
    )

    assert incoming.status_code == 200
    assert {edge["relationship_type"] for edge in incoming.json()["edges"]} == {
        "IMPORTS",
        "INHERITS",
    }
    assert all(edge["direction"] == "INCOMING" for edge in incoming.json()["edges"])
    assert inheritance.json()["count"] == 1
    assert inheritance.json()["edges"][0]["source"]["qualified_name"] == "service.Service"
    assert any(edge["depth"] == 2 for edge in two_hops.json()["edges"])
    assert limited.json()["count"] == 1


def test_retrieval_rejects_cross_repository_and_unknown_resources(retrieval_client) -> None:
    client, ids = retrieval_client
    mismatched = client.get(
        f"/repositories/{ids['first_repository_id']}"
        f"/scans/{ids['second_scan_id']}/retrieval/symbols?query=Service"
    )
    unknown_repository = client.get(
        f"/repositories/{uuid4()}/scans/{ids['first_scan_id']}"
        "/retrieval/symbols?query=Service"
    )
    unknown_scan = client.get(
        f"/repositories/{ids['first_repository_id']}/scans/{uuid4()}"
        "/retrieval/symbols?query=Service"
    )
    unknown_symbol = client.get(neighbor_url(ids, str(uuid4())))

    assert mismatched.status_code == 409
    assert mismatched.json()["error"]["code"] == "SCAN_REPOSITORY_MISMATCH"
    assert unknown_repository.status_code == 404
    assert unknown_repository.json()["error"]["code"] == "REPOSITORY_NOT_FOUND"
    assert unknown_scan.status_code == 404
    assert unknown_scan.json()["error"]["code"] == "SCAN_NOT_FOUND"
    assert unknown_symbol.status_code == 404
    assert unknown_symbol.json()["error"]["code"] == "SYMBOL_NOT_FOUND"


def test_retrieval_rejects_invalid_filters_and_bounds(retrieval_client) -> None:
    client, ids = retrieval_client
    service_id = symbol_id(client, ids, "service.Service")

    invalid_type = client.get(exact_url(ids, "Service") + "&symbol_type=PACKAGE")
    invalid_direction = client.get(neighbor_url(ids, service_id, "?direction=SIDEWAYS"))
    invalid_relationship = client.get(
        neighbor_url(ids, service_id, "?relationship_type=DEPENDS_ON")
    )
    invalid_depth = client.get(neighbor_url(ids, service_id, "?max_depth=0"))
    excessive_depth = client.get(neighbor_url(ids, service_id, "?max_depth=4"))
    excessive_limit = client.get(exact_url(ids, "Service") + "&limit=501")

    assert invalid_type.status_code == 422
    assert invalid_type.json()["error"]["code"] == "INVALID_RETRIEVAL_ARGUMENT"
    assert invalid_direction.status_code == 422
    assert invalid_direction.json()["error"]["code"] == "INVALID_RETRIEVAL_ARGUMENT"
    assert invalid_relationship.status_code == 422
    assert invalid_relationship.json()["error"]["code"] == "INVALID_RETRIEVAL_ARGUMENT"
    assert invalid_depth.status_code == 422
    assert invalid_depth.json()["error"]["code"] == "INVALID_RETRIEVAL_ARGUMENT"
    assert excessive_depth.status_code == 422
    assert excessive_depth.json()["error"]["code"] == "INVALID_RETRIEVAL_ARGUMENT"
    assert excessive_limit.status_code == 422
    assert excessive_limit.json()["error"]["code"] == "INVALID_RETRIEVAL_ARGUMENT"


def test_two_scans_of_same_repository_do_not_share_symbol_ids(retrieval_client) -> None:
    client, ids = retrieval_client
    repository_id = ids["first_repository_id"]
    second_scan_id = client.post(f"/repositories/{repository_id}/scans", json={}).json()["id"]

    first = client.get(exact_url(ids, "Service")).json()["hits"]
    second = client.get(
        f"/repositories/{repository_id}/scans/{second_scan_id}"
        "/retrieval/symbols?query=Service"
    ).json()["hits"]

    assert len(first) == len(second) == 1
    assert first[0]["scan_id"] == ids["first_scan_id"]
    assert second[0]["scan_id"] == second_scan_id
    assert UUID(first[0]["id"]) != UUID(second[0]["id"])
