from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from adaptive_platform.api.repositories import router as repository_router
from adaptive_platform.api.review_ui import router as review_ui_router
from adaptive_platform.api.tasks import router as task_router
from adaptive_platform.config import Settings, get_settings
from adaptive_platform.database import create_database_engine, create_session_factory
from adaptive_platform.extraction import ExtractorRegistry, default_extractor_registry
from adaptive_platform.repository import RepositoryValidationError
from adaptive_platform.services import ServiceError


def create_app(
    settings: Settings | None = None,
    *,
    engine: Engine | None = None,
    session_factory: sessionmaker[Session] | None = None,
    extractor_registry: ExtractorRegistry | None = None,
) -> FastAPI:
    selected_settings = settings or get_settings()
    selected_engine = engine or create_database_engine(selected_settings.database_url)
    selected_factory = session_factory or create_session_factory(selected_engine)
    selected_registry = extractor_registry or default_extractor_registry()

    application = FastAPI(
        title="Adaptive Agentic Engineering Platform",
        version="0.1.0",
    )
    application.state.settings = selected_settings
    application.state.engine = selected_engine
    application.state.session_factory = selected_factory
    application.state.extractor_registry = selected_registry
    application.include_router(repository_router)
    application.include_router(task_router)
    application.include_router(review_ui_router)

    @application.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.exception_handler(ServiceError)
    async def service_error_handler(request: Request, exc: ServiceError) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": str(exc), "details": {}}},
        )

    @application.exception_handler(RepositoryValidationError)
    async def repository_error_handler(
        request: Request,
        exc: RepositoryValidationError,
    ) -> JSONResponse:
        del request
        status_code = 403 if exc.code == "PATH_NOT_ALLOWED" else 422
        return JSONResponse(
            status_code=status_code,
            content={"error": {"code": exc.code, "message": str(exc), "details": {}}},
        )

    return application
