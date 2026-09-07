from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class IndexDocument:
    id: str
    repository_id: str
    scan_id: str
    content: str
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    document_id: str
    score: float
    retrieval_type: str
    reason: str
    metadata: dict[str, Any]


class RetrievalIndex(Protocol):
    """Provider boundary for PostgreSQL now and optional Milvus in V0.3."""

    def index(self, documents: list[IndexDocument]) -> None: ...

    def delete_scan(self, scan_id: str) -> None: ...

    def search(
        self,
        *,
        query: str,
        repository_id: str,
        scan_id: str,
        limit: int,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievalHit]: ...

