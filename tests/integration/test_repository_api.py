from __future__ import annotations

import subprocess
from pathlib import Path
from uuid import UUID

import pytest
from adaptive_platform.app import create_app
from adaptive_platform.config import Settings
from adaptive_platform.database import Base, TraceEventRecord, create_database_engine
from adaptive_platform.database.models import (
    RelationshipRecord,
    RepositoryFileRecord,
    RepositoryLanguageProfileRecord,
    RepositoryScanRecord,
    SymbolRecord,
)
from fastapi.testclient import TestClient
from sqlalchemy import func, select


def git(root: Path, *arguments: str) -> None:
    subprocess.run(["git", "-C", str(root), *arguments], check=True, capture_output=True)


@pytest.fixture
def source_repository(tmp_path: Path) -> Path:
    root = tmp_path / "source-repository"
    root.mkdir()
    git(root, "init", "--quiet")
    git(root, "config", "user.email", "fixture@example.test")
    git(root, "config", "user.name", "Fixture")
    (root / "app.py").write_text(
        "API_KEY = 'redacted-example-value'\n\ndef hello() -> str:\n    return 'hello'\n"
    )
    (root / "README.md").write_text("# API fixture\n")
    git(root, "add", ".")
    git(root, "commit", "--quiet", "-m", "fixture")
    return root


@pytest.fixture
def app_client(tmp_path: Path, source_repository: Path):
    database_path = tmp_path / "test.db"
    settings = Settings(
        database_url=f"sqlite+pysqlite:///{database_path}",
        allowed_repository_roots=str(tmp_path),
    )
    engine = create_database_engine(settings.database_url)
    Base.metadata.create_all(engine)
    app = create_app(settings, engine=engine)
    with TestClient(app) as client:
        yield client, app


def test_register_scan_and_list_immutable_files(app_client, source_repository: Path) -> None:
    client, app = app_client

    registered = client.post(
        "/repositories",
        json={"path": str(source_repository)},
    )
    assert registered.status_code == 201
    repository_id = registered.json()["id"]

    requested = client.post(f"/repositories/{repository_id}/scans", json={})
    assert requested.status_code == 202
    scan_id = requested.json()["id"]

    scan = client.get(f"/repositories/{repository_id}/scans/{scan_id}")
    assert scan.status_code == 200
    assert scan.json()["status"] == "COMPLETED"
    assert len(scan.json()["commit_hash"]) == 40
    assert len(scan.json()["working_tree_fingerprint"]) == 64

    files = client.get(f"/repositories/{repository_id}/scans/{scan_id}/files")
    assert files.status_code == 200
    assert {item["path"] for item in files.json()} == {"README.md", "app.py"}
    app_file = next(item for item in files.json() if item["path"] == "app.py")
    assert app_file["secret_finding_count"] == 1
    assert app_file["detection_signal"] == "extension:.py"

    languages = client.get(f"/repositories/{repository_id}/scans/{scan_id}/languages")
    assert languages.status_code == 200
    assert languages.json()["repository_type"] == "SINGLE_LANGUAGE"
    assert languages.json()["primary_language"] == "Python"
    assert languages.json()["languages"][0]["extractor_status"] == "SUPPORTED"

    symbols = client.get(f"/repositories/{repository_id}/scans/{scan_id}/symbols")
    assert symbols.status_code == 200
    assert {(item["qualified_name"], item["symbol_type"]) for item in symbols.json()} == {
        ("app", "MODULE"),
        ("app.API_KEY", "CONSTANT"),
        ("app.hello", "FUNCTION"),
    }
    relationships = client.get(f"/repositories/{repository_id}/scans/{scan_id}/relationships")
    assert relationships.status_code == 200
    assert relationships.json() == []

    with app.state.session_factory() as session:
        trace_count = session.scalar(select(func.count()).select_from(TraceEventRecord))
        assert trace_count >= 3
        persisted_scan = session.get(RepositoryScanRecord, UUID(scan_id))
        assert persisted_scan is not None
        persisted_scan.file_count += 1
        with pytest.raises(ValueError, match="immutable"):
            session.commit()

    with app.state.session_factory() as session:
        symbol = session.scalar(select(SymbolRecord).where(SymbolRecord.scan_id == UUID(scan_id)))
        assert symbol is not None
        symbol.name = "changed"
        with pytest.raises(ValueError, match="immutable"):
            session.commit()

    with app.state.session_factory() as session:
        symbol = session.scalar(select(SymbolRecord).where(SymbolRecord.scan_id == UUID(scan_id)))
        assert symbol is not None
        session.add(
            RelationshipRecord(
                scan_id=UUID(scan_id),
                source_kind="SYMBOL",
                source_id=symbol.id,
                target_kind="SYMBOL",
                target_id=None,
                unresolved_target="external.value",
                relationship_type="REFERENCES",
                resolution_status="UNRESOLVED",
                resolution_reason="late_test",
                confidence=1.0,
                evidence_type="SYNTAX_FACT",
                provenance="RECORDED",
                evidence_file_id=symbol.file_id,
                evidence_start_line=1,
                evidence_start_column=0,
                evidence_end_line=1,
                evidence_end_column=1,
                extractor_name="test",
                extractor_version="1",
                extension_metadata={},
            )
        )
        with pytest.raises(ValueError, match="immutable"):
            session.commit()

    with app.state.session_factory() as session:
        profile = session.scalar(
            select(RepositoryLanguageProfileRecord).where(
                RepositoryLanguageProfileRecord.scan_id == UUID(scan_id)
            )
        )
        assert profile is not None
        profile.primary_language = "TypeScript"
        with pytest.raises(ValueError, match="immutable"):
            session.commit()

    with app.state.session_factory() as session:
        session.add(
            RepositoryFileRecord(
                repository_id=UUID(repository_id),
                scan_id=UUID(scan_id),
                path="late.py",
                language="Python",
                category="SOURCE",
                content_hash="0" * 64,
                size=0,
                encoding="utf-8",
                is_generated=False,
                secret_finding_count=0,
            )
        )
        with pytest.raises(ValueError, match="immutable"):
            session.commit()


def test_dirty_tree_can_be_rejected(app_client, source_repository: Path) -> None:
    client, _ = app_client
    repository_id = client.post(
        "/repositories",
        json={"path": str(source_repository)},
    ).json()["id"]
    (source_repository / "app.py").write_text("value = 2\n")

    requested = client.post(
        f"/repositories/{repository_id}/scans",
        json={"dirty_tree_policy": "REJECT"},
    )
    scan_id = requested.json()["id"]
    scan = client.get(f"/repositories/{repository_id}/scans/{scan_id}")

    assert scan.json()["status"] == "FAILED"
    assert scan.json()["failure_code"] == "DIRTY_TREE_REJECTED"


def test_registration_rejects_path_outside_allowed_roots(tmp_path: Path) -> None:
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        allowed_repository_roots=str(tmp_path / "allowed"),
    )
    engine = create_database_engine(settings.database_url)
    Base.metadata.create_all(engine)
    app = create_app(settings, engine=engine)

    with TestClient(app) as client:
        response = client.post("/repositories", json={"path": str(tmp_path)})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PATH_NOT_ALLOWED"


def test_polyglot_repository_reports_all_languages_and_coverage(tmp_path: Path) -> None:
    root = tmp_path / "polyglot"
    root.mkdir()
    git(root, "init", "--quiet")
    git(root, "config", "user.email", "fixture@example.test")
    git(root, "config", "user.name", "Fixture")
    (root / "service.py").write_text("value = 'python'\n" * 8)
    (root / "web.ts").write_text("export const value = 'typescript';\n" * 12)
    (root / "main.go").write_text("package main\nfunc main() {}\n")
    git(root, "add", ".")
    git(root, "commit", "--quiet", "-m", "polyglot fixture")

    settings = Settings(
        database_url=f"sqlite+pysqlite:///{tmp_path / 'polyglot.db'}",
        allowed_repository_roots=str(tmp_path),
    )
    engine = create_database_engine(settings.database_url)
    Base.metadata.create_all(engine)
    with TestClient(create_app(settings, engine=engine)) as client:
        repository_id = client.post("/repositories", json={"path": str(root)}).json()["id"]
        scan_id = client.post(f"/repositories/{repository_id}/scans", json={}).json()["id"]
        response = client.get(f"/repositories/{repository_id}/scans/{scan_id}/languages")

    assert response.status_code == 200
    payload = response.json()
    assert payload["repository_type"] == "POLYGLOT"
    assert payload["primary_language"] == "TypeScript"
    coverage = {item["language"]: item["extractor_status"] for item in payload["languages"]}
    assert coverage == {"Go": "UNSUPPORTED", "Python": "SUPPORTED", "TypeScript": "UNSUPPORTED"}


def test_unknown_repository_completes_with_explicit_unknown_profile(tmp_path: Path) -> None:
    root = tmp_path / "unknown"
    root.mkdir()
    git(root, "init", "--quiet")
    git(root, "config", "user.email", "fixture@example.test")
    git(root, "config", "user.name", "Fixture")
    (root / "mystery.xyz").write_text("unrecognized source-like content\n")
    git(root, "add", ".")
    git(root, "commit", "--quiet", "-m", "unknown fixture")

    settings = Settings(
        database_url=f"sqlite+pysqlite:///{tmp_path / 'unknown.db'}",
        allowed_repository_roots=str(tmp_path),
    )
    engine = create_database_engine(settings.database_url)
    Base.metadata.create_all(engine)
    with TestClient(create_app(settings, engine=engine)) as client:
        repository_id = client.post("/repositories", json={"path": str(root)}).json()["id"]
        scan_id = client.post(f"/repositories/{repository_id}/scans", json={}).json()["id"]
        response = client.get(f"/repositories/{repository_id}/scans/{scan_id}/languages")

    assert response.status_code == 200
    assert response.json()["repository_type"] == "UNKNOWN"
    assert response.json()["languages"] == []
    assert response.json()["unprofiled_file_count"] == 1
