from __future__ import annotations

import re
from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import func, literal_column, select
from sqlalchemy.orm import Session

from adaptive_platform.database.models import (
    ContextDocumentRecord,
    RepositoryFileRecord,
    RepositoryRecord,
    RepositoryScanRecord,
    TraceEventRecord,
)
from adaptive_platform.retrieval.errors import RetrievalError
from adaptive_platform.retrieval.models import (
    ContextDocumentType,
    FullTextEngine,
    FullTextHit,
)

MAX_FULL_TEXT_RESULTS = 100
MAX_FULL_TEXT_QUERY_CHARACTERS = 256
SEARCHABLE_CATEGORIES = frozenset(
    {"SOURCE", "TEST", "DOCUMENTATION", "CONFIGURATION", "DEPENDENCY"}
)


class FullTextRetriever:
    """Bounded lexical retrieval over immutable scan-bound context documents."""

    def __init__(self, session: Session) -> None:
        self.session = session

    @property
    def engine(self) -> FullTextEngine:
        if self.session.get_bind().dialect.name == "postgresql":
            return FullTextEngine.POSTGRESQL
        return FullTextEngine.SQLITE_TEST_FALLBACK

    def search(
        self,
        repository_id: UUID,
        scan_id: UUID,
        query: str,
        *,
        document_types: Iterable[ContextDocumentType | str] = (),
        categories: Iterable[str] = (),
        file_path: str | None = None,
        language: str | None = None,
        limit: int = 20,
    ) -> tuple[FullTextHit, ...]:
        normalized_query = _validate_query(query)
        _validate_limit(limit)
        normalized_types = _normalize_document_types(document_types)
        normalized_categories = _normalize_categories(categories)
        self._completed_scan(repository_id, scan_id)

        if self.engine is FullTextEngine.POSTGRESQL:
            return self._search_postgresql(
                scan_id,
                normalized_query,
                normalized_types,
                normalized_categories,
                file_path,
                language,
                limit,
            )
        return self._search_sqlite_fallback(
            scan_id,
            normalized_query,
            normalized_types,
            normalized_categories,
            file_path,
            language,
            limit,
        )

    def _search_postgresql(
        self,
        scan_id: UUID,
        query: str,
        document_types: tuple[str, ...],
        categories: tuple[str, ...],
        file_path: str | None,
        language: str | None,
        limit: int,
    ) -> tuple[FullTextHit, ...]:
        tsquery = func.websearch_to_tsquery(literal_column("'simple'::regconfig"), query)
        rank = func.ts_rank_cd(ContextDocumentRecord.search_vector, tsquery)
        statement = self._base_statement(scan_id, document_types, categories, file_path, language)
        statement = (
            statement.add_columns(rank.label("score"))
            .where(ContextDocumentRecord.search_vector.op("@@")(tsquery))
            .order_by(
                rank.desc(),
                RepositoryFileRecord.path,
                ContextDocumentRecord.start_line,
                ContextDocumentRecord.end_line,
                ContextDocumentRecord.document_type,
                ContextDocumentRecord.id,
            )
            .limit(limit)
        )
        return tuple(
            _hit(document, file, float(score), self.engine)
            for document, file, score in self.session.execute(statement)
        )

    def _search_sqlite_fallback(
        self,
        scan_id: UUID,
        query: str,
        document_types: tuple[str, ...],
        categories: tuple[str, ...],
        file_path: str | None,
        language: str | None,
        limit: int,
    ) -> tuple[FullTextHit, ...]:
        terms = tuple(re.findall(r"[A-Za-z0-9_]+", query.casefold()))
        if not terms:
            raise RetrievalError(
                "INVALID_RETRIEVAL_ARGUMENT",
                "Full-text query must contain at least one searchable token",
                422,
            )
        rows = self.session.execute(
            self._base_statement(scan_id, document_types, categories, file_path, language)
        )
        ranked: list[FullTextHit] = []
        for document, file in rows:
            tokens = (document.search_vector or "").split()
            if not all(term in tokens for term in terms):
                continue
            score = sum(tokens.count(term) for term in terms) / max(1, len(tokens))
            ranked.append(_hit(document, file, score, self.engine))
        ranked.sort(
            key=lambda item: (
                -item.score,
                item.file_path,
                item.start_line,
                item.end_line,
                item.document_type.value,
                str(item.document_id),
            )
        )
        return tuple(ranked[:limit])

    def _base_statement(
        self,
        scan_id: UUID,
        document_types: tuple[str, ...],
        categories: tuple[str, ...],
        file_path: str | None,
        language: str | None,
    ):
        statement = (
            select(ContextDocumentRecord, RepositoryFileRecord)
            .join(RepositoryFileRecord, RepositoryFileRecord.id == ContextDocumentRecord.file_id)
            .where(
                ContextDocumentRecord.scan_id == scan_id,
                RepositoryFileRecord.scan_id == scan_id,
            )
        )
        if document_types:
            statement = statement.where(
                ContextDocumentRecord.document_type.in_(document_types)
            )
        if categories:
            statement = statement.where(RepositoryFileRecord.category.in_(categories))
        if file_path is not None:
            statement = statement.where(RepositoryFileRecord.path == file_path)
        if language is not None:
            statement = statement.where(RepositoryFileRecord.language == language)
        return statement

    def _completed_scan(self, repository_id: UUID, scan_id: UUID) -> None:
        repository_exists = self.session.scalar(
            select(RepositoryRecord.id).where(RepositoryRecord.id == repository_id)
        )
        if repository_exists is None:
            raise RetrievalError("REPOSITORY_NOT_FOUND", "Repository was not found", 404)
        scan = self.session.scalar(
            select(RepositoryScanRecord).where(RepositoryScanRecord.id == scan_id)
        )
        if scan is None:
            raise RetrievalError("SCAN_NOT_FOUND", "Repository scan was not found", 404)
        if scan.repository_id != repository_id:
            raise RetrievalError(
                "SCAN_REPOSITORY_MISMATCH",
                "Repository scan does not belong to the requested repository",
                409,
            )
        if scan.status != "COMPLETED":
            raise RetrievalError(
                "SCAN_NOT_COMPLETED",
                "Full-text retrieval requires a completed repository scan",
                409,
            )
        index_marker = self.session.scalar(
            select(TraceEventRecord.id).where(
                TraceEventRecord.scan_id == scan_id,
                TraceEventRecord.event_type == "context_documents_created",
            )
        )
        if index_marker is None:
            raise RetrievalError(
                "FULL_TEXT_INDEX_UNAVAILABLE",
                "The scan predates M3C full-text indexing; create a new scan",
                409,
            )


def _validate_query(query: str) -> str:
    if not query or not query.strip():
        raise RetrievalError(
            "INVALID_RETRIEVAL_ARGUMENT", "Full-text query must not be empty", 422
        )
    if len(query) > MAX_FULL_TEXT_QUERY_CHARACTERS:
        raise RetrievalError(
            "INVALID_RETRIEVAL_ARGUMENT",
            f"Full-text query must be at most {MAX_FULL_TEXT_QUERY_CHARACTERS} characters",
            422,
        )
    if "\x00" in query:
        raise RetrievalError(
            "INVALID_RETRIEVAL_ARGUMENT", "Full-text query contains an invalid character", 422
        )
    return query.strip()


def _validate_limit(limit: int) -> None:
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_FULL_TEXT_RESULTS:
        raise RetrievalError(
            "INVALID_RETRIEVAL_ARGUMENT",
            f"limit must be between 1 and {MAX_FULL_TEXT_RESULTS}",
            422,
        )


def _normalize_document_types(
    values: Iterable[ContextDocumentType | str],
) -> tuple[str, ...]:
    raw_values = (values,) if isinstance(values, str) else values
    try:
        return tuple(sorted({ContextDocumentType(value).value for value in raw_values}))
    except (TypeError, ValueError) as error:
        raise RetrievalError(
            "INVALID_RETRIEVAL_ARGUMENT",
            "document_types contains an unsupported value",
            422,
        ) from error


def _normalize_categories(values: Iterable[str]) -> tuple[str, ...]:
    raw_values = (values,) if isinstance(values, str) else values
    normalized = tuple(sorted(set(raw_values)))
    if any(value not in SEARCHABLE_CATEGORIES for value in normalized):
        raise RetrievalError(
            "INVALID_RETRIEVAL_ARGUMENT",
            "categories contains an unsupported value",
            422,
        )
    return normalized


def _hit(
    document: ContextDocumentRecord,
    file: RepositoryFileRecord,
    score: float,
    engine: FullTextEngine,
) -> FullTextHit:
    return FullTextHit(
        document_id=document.id,
        scan_id=document.scan_id,
        file_id=document.file_id,
        file_path=file.path,
        language=file.language,
        category=file.category,
        symbol_id=document.symbol_id,
        document_type=ContextDocumentType(document.document_type),
        content=document.content,
        content_hash=document.content_hash,
        start_line=document.start_line,
        end_line=document.end_line,
        score=score,
        retrieval_engine=engine,
        document_metadata=dict(document.document_metadata or {}),
    )
