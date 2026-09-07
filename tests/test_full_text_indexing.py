from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from adaptive_platform.database import Base, create_database_engine
from adaptive_platform.database.models import RepositoryRecord, RepositoryScanRecord, SymbolRecord
from adaptive_platform.extraction import SourceSnapshotError
from adaptive_platform.retrieval import (
    MAX_DOCUMENT_CHARACTERS,
    MAX_DOCUMENT_LINES,
    ContextDocumentType,
    FullTextRetriever,
    RetrievalError,
    build_context_documents,
)
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class FileFixture:
    id: UUID
    path: str
    language: str | None
    category: str
    content_hash: str
    encoding: str | None = "utf-8"
    is_generated: bool = False
    is_vendored: bool = False
    secret_finding_count: int = 0


def _file(path: str, content: str, **overrides) -> FileFixture:
    return FileFixture(
        id=uuid4(),
        path=path,
        language=overrides.pop("language", "Python"),
        category=overrides.pop("category", "SOURCE"),
        content_hash=hashlib.sha256(content.encode()).hexdigest(),
        **overrides,
    )


def test_context_documents_are_deterministic_bounded_and_symbol_linked(tmp_path: Path) -> None:
    source = "".join(f"value_{line} = {line}\n" for line in range(1, 205)) + "x" * 25_000
    (tmp_path / "module.py").write_text(source)
    file = _file("module.py", source)
    symbol = SymbolRecord(
        id=uuid4(),
        scan_id=uuid4(),
        file_id=file.id,
        parent_symbol_id=None,
        name="Example",
        qualified_name="module.Example",
        symbol_type="CLASS",
        signature="class Example",
        docstring=None,
        start_line=2,
        start_column=0,
        end_line=3,
        end_column=10,
        extractor_name="test",
        extractor_version="1",
        extension_metadata={},
    )
    scan_id = uuid4()

    first = build_context_documents(tmp_path, scan_id, [file], [symbol])
    second = build_context_documents(tmp_path, scan_id, [file], [symbol])

    assert first == second
    assert first.documents
    assert all(len(item.content) <= MAX_DOCUMENT_CHARACTERS for item in first.documents)
    assert all(item.end_line - item.start_line + 1 <= MAX_DOCUMENT_LINES for item in first.documents)
    assert all(len(item.content_hash) == 64 for item in first.documents)
    symbol_documents = [item for item in first.documents if item.symbol_id == symbol.id]
    assert len(symbol_documents) == 1
    assert symbol_documents[0].document_type is ContextDocumentType.CLASS
    assert (symbol_documents[0].start_line, symbol_documents[0].end_line) == (2, 3)


def test_context_index_excludes_unapproved_generated_vendored_and_secret_files(
    tmp_path: Path,
) -> None:
    files = [
        _file("generated/client.ts", "generated", is_generated=True),
        _file("vendor/helper.go", "vendored", language="Go", is_vendored=True),
        _file("settings.toml", "token", language=None, category="CONFIGURATION", secret_finding_count=1),
        _file("image.note", "other", language=None, category="OTHER"),
    ]

    build = build_context_documents(tmp_path, uuid4(), files, [])

    assert build.documents == ()
    assert build.exclusions == {
        "GENERATED": 1,
        "SECRET_FLAGGED": 1,
        "UNAPPROVED_CATEGORY": 1,
        "VENDORED": 1,
    }


def test_context_index_rejects_content_that_changed_after_inventory(tmp_path: Path) -> None:
    (tmp_path / "service.py").write_text("value = 2\n")
    file = _file("service.py", "value = 1\n")

    with pytest.raises(SourceSnapshotError) as error:
        build_context_documents(tmp_path, uuid4(), [file], [])

    assert error.value.code == "SOURCE_CHANGED_DURING_INDEXING"


def test_full_text_retrieval_rejects_scans_created_before_m3c() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    with Session(engine) as session:
        repository = RepositoryRecord(
            name="legacy",
            canonical_path="/fixtures/legacy",
            default_branch=None,
            created_at=now,
            updated_at=now,
        )
        session.add(repository)
        session.flush()
        scan = RepositoryScanRecord(
            repository_id=repository.id,
            status="COMPLETED",
            scanner_version="pre-m3c",
            configuration_version="pre-m3c",
            started_at=now,
            completed_at=now,
            file_count=0,
            total_bytes=0,
        )
        session.add(scan)
        session.commit()

        with pytest.raises(RetrievalError) as error:
            FullTextRetriever(session).search(repository.id, scan.id, "anything")

    assert error.value.code == "FULL_TEXT_INDEX_UNAVAILABLE"
    assert error.value.status_code == 409
