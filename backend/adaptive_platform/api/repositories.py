from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status
from sqlalchemy.orm import Session

from adaptive_platform.api.dependencies import get_session
from adaptive_platform.api.schemas import (
    ExactSymbolRetrievalResponse,
    FullTextHitResponse,
    FullTextRetrievalResponse,
    GraphTraversalResponse,
    LanguageProfileResponse,
    QuestionCreate,
    QuestionResponse,
    RelationshipResponse,
    RepositoryCreate,
    RepositoryFileResponse,
    RepositoryResponse,
    RetrievalSymbolResponse,
    ScanCreate,
    ScanResponse,
    SymbolResponse,
    TraversalEdgeResponse,
)
from adaptive_platform.api.tasks import question_response
from adaptive_platform.context import QueryClassificationError
from adaptive_platform.database.models import TraceEventRecord
from adaptive_platform.qa import QuestionService
from adaptive_platform.retrieval import FullTextRetriever, RetrievalError, StructuralRetriever
from adaptive_platform.services import (
    RepositoryService,
    ScanService,
    ServiceError,
    execute_scan_task,
)

router = APIRouter(prefix="/repositories", tags=["repositories"])
DatabaseSession = Annotated[Session, Depends(get_session)]


@router.post(
    "/{repository_id}/scans/{scan_id}/questions",
    response_model=QuestionResponse,
)
def ask_repository_question(
    repository_id: UUID,
    scan_id: UUID,
    body: QuestionCreate,
    session: DatabaseSession,
) -> QuestionResponse:
    try:
        task = QuestionService(session).ask(repository_id, scan_id, body.question)
    except QueryClassificationError as error:
        raise ServiceError("INVALID_QUERY", str(error), 422) from error
    return question_response(session, task)


def _raise_service_error(error: RetrievalError) -> None:
    raise ServiceError(error.code, str(error), error.status_code) from error


def _record_retrieval_trace(
    session: Session,
    *,
    repository_id: UUID,
    scan_id: UUID,
    event_type: str,
    summary: str,
    input_metadata: dict[str, object],
    output_refs: list[str],
) -> None:
    event_id = uuid4()
    session.add(
        TraceEventRecord(
            id=event_id,
            task_id=f"retrieval:{event_id}",
            repository_id=repository_id,
            scan_id=scan_id,
            correlation_id=str(event_id),
            category="RETRIEVAL",
            event_type=event_type,
            actor_type="SYSTEM",
            occurred_at=datetime.now(UTC),
            summary=summary,
            rationale_summary="Deterministic scan-bound structural retrieval.",
            input_refs=[f"scan:{scan_id}"],
            output_refs=output_refs,
            event_metadata={**input_metadata, "raw_query_retained": False},
        )
    )
    session.commit()


@router.post("", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
def register_repository(
    body: RepositoryCreate,
    request: Request,
    session: DatabaseSession,
) -> RepositoryResponse:
    record = RepositoryService(session, request.app.state.settings).register(body.path, body.name)
    return RepositoryResponse.model_validate(record)


@router.get("/{repository_id}", response_model=RepositoryResponse)
def get_repository(
    repository_id: UUID,
    request: Request,
    session: DatabaseSession,
) -> RepositoryResponse:
    record = RepositoryService(session, request.app.state.settings).get(repository_id)
    return RepositoryResponse.model_validate(record)


@router.post(
    "/{repository_id}/scans",
    response_model=ScanResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def request_scan(
    repository_id: UUID,
    body: ScanCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    session: DatabaseSession,
) -> ScanResponse:
    scan = ScanService(session, request.app.state.settings).request(repository_id)
    background_tasks.add_task(
        execute_scan_task,
        request.app.state.session_factory,
        request.app.state.settings,
        scan.id,
        body.dirty_tree_policy,
        request.app.state.extractor_registry,
    )
    return ScanResponse.model_validate(scan)


@router.get("/{repository_id}/scans", response_model=list[ScanResponse])
def list_scans(
    repository_id: UUID,
    request: Request,
    session: DatabaseSession,
) -> list[ScanResponse]:
    scans = ScanService(session, request.app.state.settings).list(repository_id)
    return [ScanResponse.model_validate(scan) for scan in scans]


@router.get("/{repository_id}/scans/{scan_id}", response_model=ScanResponse)
def get_scan(
    repository_id: UUID,
    scan_id: UUID,
    request: Request,
    session: DatabaseSession,
) -> ScanResponse:
    scan = ScanService(session, request.app.state.settings).get(repository_id, scan_id)
    return ScanResponse.model_validate(scan)


@router.get(
    "/{repository_id}/scans/{scan_id}/files",
    response_model=list[RepositoryFileResponse],
)
def list_scan_files(
    repository_id: UUID,
    scan_id: UUID,
    request: Request,
    session: DatabaseSession,
) -> list[RepositoryFileResponse]:
    files = ScanService(session, request.app.state.settings).files(repository_id, scan_id)
    return [RepositoryFileResponse.model_validate(item) for item in files]


@router.get(
    "/{repository_id}/scans/{scan_id}/languages",
    response_model=LanguageProfileResponse,
)
def get_scan_language_profile(
    repository_id: UUID,
    scan_id: UUID,
    request: Request,
    session: DatabaseSession,
) -> LanguageProfileResponse:
    profile = ScanService(session, request.app.state.settings).language_profile(
        repository_id,
        scan_id,
    )
    return LanguageProfileResponse.model_validate(profile)


@router.get(
    "/{repository_id}/scans/{scan_id}/symbols",
    response_model=list[SymbolResponse],
)
def list_scan_symbols(
    repository_id: UUID,
    scan_id: UUID,
    request: Request,
    session: DatabaseSession,
) -> list[SymbolResponse]:
    symbols = ScanService(session, request.app.state.settings).symbols(repository_id, scan_id)
    return [SymbolResponse.model_validate(item) for item in symbols]


@router.get(
    "/{repository_id}/scans/{scan_id}/relationships",
    response_model=list[RelationshipResponse],
)
def list_scan_relationships(
    repository_id: UUID,
    scan_id: UUID,
    request: Request,
    session: DatabaseSession,
) -> list[RelationshipResponse]:
    relationships = ScanService(session, request.app.state.settings).relationships(
        repository_id,
        scan_id,
    )
    return [RelationshipResponse.model_validate(item) for item in relationships]


@router.get(
    "/{repository_id}/scans/{scan_id}/retrieval/symbols",
    response_model=ExactSymbolRetrievalResponse,
)
def retrieve_exact_symbols(
    repository_id: UUID,
    scan_id: UUID,
    session: DatabaseSession,
    query: str,
    symbol_type: Annotated[list[str] | None, Query()] = None,
    file_path: str | None = None,
    language: str | None = None,
    limit: int = 20,
) -> ExactSymbolRetrievalResponse:
    retriever = StructuralRetriever(session)
    try:
        results = retriever.exact_symbols(
            repository_id,
            scan_id,
            query,
            symbol_types=tuple(symbol_type or ()),
            file_path=file_path,
            language=language,
            limit=limit,
        )
    except RetrievalError as error:
        _raise_service_error(error)

    hits = [RetrievalSymbolResponse.model_validate(item) for item in results]
    _record_retrieval_trace(
        session,
        repository_id=repository_id,
        scan_id=scan_id,
        event_type="exact_symbol_retrieval_completed",
        summary="Completed exact symbol retrieval against an immutable scan.",
        input_metadata={
            "query_sha256": hashlib.sha256(query.encode()).hexdigest(),
            "symbol_types": list(symbol_type or ()),
            "file_path": file_path,
            "language": language,
            "limit": limit,
            "result_count": len(hits),
        },
        output_refs=[f"symbol:{item.id}" for item in hits],
    )
    return ExactSymbolRetrievalResponse(
        repository_id=repository_id,
        scan_id=scan_id,
        query=query,
        count=len(hits),
        hits=hits,
    )


@router.get(
    "/{repository_id}/scans/{scan_id}/retrieval/text",
    response_model=FullTextRetrievalResponse,
)
def retrieve_full_text(
    repository_id: UUID,
    scan_id: UUID,
    session: DatabaseSession,
    query: str,
    document_type: Annotated[list[str] | None, Query()] = None,
    category: Annotated[list[str] | None, Query()] = None,
    file_path: str | None = None,
    language: str | None = None,
    limit: int = 20,
) -> FullTextRetrievalResponse:
    retriever = FullTextRetriever(session)
    try:
        results = retriever.search(
            repository_id,
            scan_id,
            query,
            document_types=tuple(document_type or ()),
            categories=tuple(category or ()),
            file_path=file_path,
            language=language,
            limit=limit,
        )
    except RetrievalError as error:
        _raise_service_error(error)

    hits = [FullTextHitResponse.model_validate(item) for item in results]
    _record_retrieval_trace(
        session,
        repository_id=repository_id,
        scan_id=scan_id,
        event_type="full_text_retrieval_completed",
        summary="Completed bounded lexical retrieval against an immutable scan.",
        input_metadata={
            "query_sha256": hashlib.sha256(query.encode()).hexdigest(),
            "document_types": list(document_type or ()),
            "categories": list(category or ()),
            "file_path": file_path,
            "language": language,
            "limit": limit,
            "retrieval_engine": retriever.engine.value,
            "result_count": len(hits),
        },
        output_refs=[f"context-document:{item.document_id}" for item in hits],
    )
    return FullTextRetrievalResponse(
        repository_id=repository_id,
        scan_id=scan_id,
        query=query,
        retrieval_engine=retriever.engine.value,
        count=len(hits),
        hits=hits,
    )


@router.get(
    "/{repository_id}/scans/{scan_id}/symbols/{symbol_id}/neighbors",
    response_model=GraphTraversalResponse,
)
def traverse_symbol_neighbors(
    repository_id: UUID,
    scan_id: UUID,
    symbol_id: UUID,
    session: DatabaseSession,
    direction: str = "BOTH",
    relationship_type: Annotated[list[str] | None, Query()] = None,
    max_depth: int = 1,
    limit: int = 100,
) -> GraphTraversalResponse:
    retriever = StructuralRetriever(session)
    try:
        results = retriever.traverse(
            repository_id,
            scan_id,
            symbol_id,
            direction=direction,
            relationship_types=tuple(relationship_type or ()),
            max_depth=max_depth,
            limit=limit,
        )
    except RetrievalError as error:
        _raise_service_error(error)

    edges = [TraversalEdgeResponse.model_validate(item) for item in results]
    nodes_by_id = {}
    for edge in edges:
        nodes_by_id[edge.source.id] = edge.source
        if edge.target is not None:
            nodes_by_id[edge.target.id] = edge.target
    nodes = sorted(
        nodes_by_id.values(),
        key=lambda item: (
            item.qualified_name,
            item.symbol_type,
            item.file_path,
            item.start_line,
            str(item.id),
        ),
    )
    _record_retrieval_trace(
        session,
        repository_id=repository_id,
        scan_id=scan_id,
        event_type="graph_traversal_completed",
        summary="Completed bounded traversal of the immutable evidence graph.",
        input_metadata={
            "start_symbol_id": str(symbol_id),
            "direction": direction.upper(),
            "relationship_types": list(relationship_type or ()),
            "max_depth": max_depth,
            "limit": limit,
            "edge_count": len(edges),
        },
        output_refs=[f"relationship:{item.relationship_id}" for item in edges],
    )
    return GraphTraversalResponse(
        repository_id=repository_id,
        scan_id=scan_id,
        start_symbol_id=symbol_id,
        direction=direction.upper(),
        max_depth=max_depth,
        count=len(edges),
        nodes=nodes,
        edges=edges,
    )
