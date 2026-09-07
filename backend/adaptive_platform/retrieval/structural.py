from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from adaptive_platform.database.models import (
    RelationshipRecord,
    RepositoryFileRecord,
    RepositoryRecord,
    RepositoryScanRecord,
    SymbolRecord,
)
from adaptive_platform.extraction.models import RelationshipType, ResolutionStatus, SymbolType
from adaptive_platform.retrieval.errors import RetrievalError
from adaptive_platform.retrieval.models import SymbolResult, TraversalDirection, TraversalEdge

MAX_EXACT_RESULTS = 500
MAX_TRAVERSAL_DEPTH = 3
MAX_TRAVERSAL_RESULTS = 500


class StructuralRetriever:
    """Scan-bound exact symbol lookup and bounded evidence-graph traversal."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def exact_symbols(
        self,
        repository_id: UUID,
        scan_id: UUID,
        query: str,
        symbol_types: Iterable[SymbolType | str] = (),
        file_path: str | None = None,
        language: str | None = None,
        limit: int = 20,
    ) -> tuple[SymbolResult, ...]:
        self._validate_limit(limit, MAX_EXACT_RESULTS)
        if not query or not query.strip():
            raise RetrievalError(
                "INVALID_RETRIEVAL_ARGUMENT",
                "Exact symbol query must not be empty",
                422,
            )
        normalized_types = _normalize_enum_values(symbol_types, SymbolType, "symbol_types")
        self._completed_scan(repository_id, scan_id)

        statement = (
            select(SymbolRecord, RepositoryFileRecord.path)
            .join(RepositoryFileRecord, RepositoryFileRecord.id == SymbolRecord.file_id)
            .where(
                SymbolRecord.scan_id == scan_id,
                RepositoryFileRecord.scan_id == scan_id,
                or_(SymbolRecord.name == query, SymbolRecord.qualified_name == query),
            )
        )
        if normalized_types:
            statement = statement.where(SymbolRecord.symbol_type.in_(normalized_types))
        if file_path is not None:
            statement = statement.where(RepositoryFileRecord.path == file_path)
        if language is not None:
            statement = statement.where(RepositoryFileRecord.language == language)
        statement = statement.order_by(
            SymbolRecord.qualified_name,
            SymbolRecord.symbol_type,
            RepositoryFileRecord.path,
            SymbolRecord.start_line,
            SymbolRecord.id,
        ).limit(limit)

        return tuple(_symbol_result(symbol, path) for symbol, path in self.session.execute(statement))

    def traverse(
        self,
        repository_id: UUID,
        scan_id: UUID,
        start_symbol_id: UUID,
        direction: TraversalDirection | str = TraversalDirection.BOTH,
        relationship_types: Iterable[RelationshipType | str] = (),
        max_depth: int = 1,
        limit: int = 100,
    ) -> tuple[TraversalEdge, ...]:
        normalized_direction = _normalize_direction(direction)
        normalized_types = _normalize_enum_values(
            relationship_types,
            RelationshipType,
            "relationship_types",
        )
        if not isinstance(max_depth, int) or isinstance(max_depth, bool):
            raise RetrievalError(
                "INVALID_RETRIEVAL_ARGUMENT", "max_depth must be an integer", 422
            )
        if not 1 <= max_depth <= MAX_TRAVERSAL_DEPTH:
            raise RetrievalError(
                "INVALID_RETRIEVAL_ARGUMENT",
                f"max_depth must be between 1 and {MAX_TRAVERSAL_DEPTH}",
                422,
            )
        self._validate_limit(limit, MAX_TRAVERSAL_RESULTS)
        self._completed_scan(repository_id, scan_id)
        start = self.session.scalar(
            select(SymbolRecord).where(
                SymbolRecord.id == start_symbol_id,
                SymbolRecord.scan_id == scan_id,
            )
        )
        if start is None:
            raise RetrievalError(
                "SYMBOL_NOT_FOUND",
                "The start symbol was not found in the requested scan",
                404,
            )

        frontier = {start_symbol_id}
        visited_nodes = {start_symbol_id}
        visited_relationships: set[UUID] = set()
        results: list[TraversalEdge] = []

        for depth in range(1, max_depth + 1):
            if not frontier or len(results) >= limit:
                break
            relationships = self._relationships_for_frontier(
                scan_id,
                frontier,
                normalized_direction,
                normalized_types,
            )
            candidates: list[tuple[RelationshipRecord, TraversalDirection, UUID | None]] = []
            for relationship in relationships:
                if relationship.id in visited_relationships:
                    continue
                edge_direction, adjacent_id = _edge_direction(
                    relationship,
                    frontier,
                    normalized_direction,
                )
                candidates.append((relationship, edge_direction, adjacent_id))

            materialized = self._materialize_edges(scan_id, depth, candidates)
            next_frontier: set[UUID] = set()
            for relationship, edge, adjacent_id in materialized:
                if len(results) >= limit:
                    break
                visited_relationships.add(relationship.id)
                results.append(edge)
                if adjacent_id is not None and adjacent_id not in visited_nodes:
                    next_frontier.add(adjacent_id)

            visited_nodes.update(next_frontier)
            frontier = next_frontier

        return tuple(results)

    def _completed_scan(self, repository_id: UUID, scan_id: UUID) -> RepositoryScanRecord:
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
                "Structural retrieval requires a completed repository scan",
                409,
            )
        return scan

    def _validate_limit(self, limit: int, maximum: int) -> None:
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= maximum:
            raise RetrievalError(
                "INVALID_RETRIEVAL_ARGUMENT",
                f"limit must be between 1 and {maximum}",
                422,
            )

    def _relationships_for_frontier(
        self,
        scan_id: UUID,
        frontier: set[UUID],
        direction: TraversalDirection,
        relationship_types: tuple[str, ...],
    ) -> list[RelationshipRecord]:
        if direction is TraversalDirection.OUTGOING:
            adjacency = RelationshipRecord.source_id.in_(frontier)
        elif direction is TraversalDirection.INCOMING:
            adjacency = RelationshipRecord.target_id.in_(frontier)
        else:
            adjacency = or_(
                RelationshipRecord.source_id.in_(frontier),
                RelationshipRecord.target_id.in_(frontier),
            )
        statement: Select[tuple[RelationshipRecord]] = select(RelationshipRecord).where(
            RelationshipRecord.scan_id == scan_id,
            adjacency,
        )
        if relationship_types:
            statement = statement.where(
                RelationshipRecord.relationship_type.in_(relationship_types)
            )
        return list(self.session.scalars(statement.order_by(RelationshipRecord.id)))

    def _materialize_edges(
        self,
        scan_id: UUID,
        depth: int,
        candidates: list[tuple[RelationshipRecord, TraversalDirection, UUID | None]],
    ) -> list[tuple[RelationshipRecord, TraversalEdge, UUID | None]]:
        if not candidates:
            return []
        symbol_ids = {
            symbol_id
            for relationship, _, _ in candidates
            for symbol_id in (relationship.source_id, relationship.target_id)
            if symbol_id is not None
        }
        symbol_rows = self.session.execute(
            select(SymbolRecord, RepositoryFileRecord.path)
            .join(RepositoryFileRecord, RepositoryFileRecord.id == SymbolRecord.file_id)
            .where(SymbolRecord.scan_id == scan_id, SymbolRecord.id.in_(symbol_ids))
        )
        symbols = {symbol.id: _symbol_result(symbol, path) for symbol, path in symbol_rows}
        evidence_file_ids = {item[0].evidence_file_id for item in candidates}
        evidence_paths = {
            file_id: path
            for file_id, path in self.session.execute(
                select(RepositoryFileRecord.id, RepositoryFileRecord.path).where(
                    RepositoryFileRecord.scan_id == scan_id,
                    RepositoryFileRecord.id.in_(evidence_file_ids),
                )
            )
        }

        materialized: list[tuple[RelationshipRecord, TraversalEdge, UUID | None]] = []
        for relationship, direction, adjacent_id in candidates:
            source = symbols.get(relationship.source_id)
            target = symbols.get(relationship.target_id) if relationship.target_id else None
            evidence_path = evidence_paths.get(relationship.evidence_file_id)
            if source is None or (relationship.target_id is not None and target is None):
                raise RetrievalError(
                    "EVIDENCE_INTEGRITY_ERROR",
                    "A relationship refers to a symbol outside its scan",
                    500,
                )
            if evidence_path is None:
                raise RetrievalError(
                    "EVIDENCE_INTEGRITY_ERROR",
                    "A relationship evidence file is outside its scan",
                    500,
                )
            materialized.append(
                (
                    relationship,
                    TraversalEdge(
                        relationship_id=relationship.id,
                        scan_id=relationship.scan_id,
                        depth=depth,
                        direction=direction,
                        source=source,
                        target=target,
                        unresolved_target=relationship.unresolved_target,
                        relationship_type=RelationshipType(relationship.relationship_type),
                        resolution_status=ResolutionStatus(relationship.resolution_status),
                        resolution_reason=relationship.resolution_reason,
                        confidence=relationship.confidence,
                        evidence_type=relationship.evidence_type,
                        provenance=relationship.provenance,
                        evidence_file_id=relationship.evidence_file_id,
                        evidence_file_path=evidence_path,
                        evidence_start_line=relationship.evidence_start_line,
                        evidence_start_column=relationship.evidence_start_column,
                        evidence_end_line=relationship.evidence_end_line,
                        evidence_end_column=relationship.evidence_end_column,
                        extractor_name=relationship.extractor_name,
                        extractor_version=relationship.extractor_version,
                        extension_metadata=dict(relationship.extension_metadata or {}),
                    ),
                    adjacent_id,
                )
            )
        return sorted(materialized, key=_edge_sort_key)


def _normalize_direction(value: TraversalDirection | str) -> TraversalDirection:
    try:
        return TraversalDirection(value)
    except (TypeError, ValueError) as error:
        raise RetrievalError(
            "INVALID_RETRIEVAL_ARGUMENT",
            "direction must be INCOMING, OUTGOING, or BOTH",
            422,
        ) from error


def _normalize_enum_values(
    values: Iterable[SymbolType | RelationshipType | str],
    enum_type: type[SymbolType | RelationshipType],
    field_name: str,
) -> tuple[str, ...]:
    raw_values = (values,) if isinstance(values, str) else values
    try:
        return tuple(sorted({enum_type(value).value for value in raw_values}))
    except (TypeError, ValueError) as error:
        raise RetrievalError(
            "INVALID_RETRIEVAL_ARGUMENT",
            f"{field_name} contains an unsupported value",
            422,
        ) from error


def _edge_direction(
    relationship: RelationshipRecord,
    frontier: set[UUID],
    requested: TraversalDirection,
) -> tuple[TraversalDirection, UUID | None]:
    if requested is not TraversalDirection.INCOMING and relationship.source_id in frontier:
        return TraversalDirection.OUTGOING, relationship.target_id
    return TraversalDirection.INCOMING, relationship.source_id


def _symbol_result(symbol: SymbolRecord, file_path: str) -> SymbolResult:
    return SymbolResult(
        id=symbol.id,
        scan_id=symbol.scan_id,
        file_id=symbol.file_id,
        file_path=file_path,
        parent_symbol_id=symbol.parent_symbol_id,
        name=symbol.name,
        qualified_name=symbol.qualified_name,
        symbol_type=SymbolType(symbol.symbol_type),
        signature=symbol.signature,
        docstring=symbol.docstring,
        start_line=symbol.start_line,
        start_column=symbol.start_column,
        end_line=symbol.end_line,
        end_column=symbol.end_column,
        extractor_name=symbol.extractor_name,
        extractor_version=symbol.extractor_version,
        extension_metadata=dict(symbol.extension_metadata or {}),
    )


def _edge_sort_key(
    item: tuple[RelationshipRecord, TraversalEdge, UUID | None],
) -> tuple[object, ...]:
    relationship, edge, _ = item
    return (
        edge.depth,
        0 if edge.direction is TraversalDirection.OUTGOING else 1,
        edge.relationship_type.value,
        edge.source.qualified_name,
        edge.target.qualified_name if edge.target else edge.unresolved_target or "",
        edge.evidence_file_path,
        edge.evidence_start_line,
        edge.evidence_start_column,
        str(relationship.id),
    )
