"""FastAPI application factory.

Run locally:
    uv run uvicorn --factory lottolab.interfaces.api.app:create_app --reload
"""

# pyright: reportUnusedFunction=false
# (route handlers are registered by FastAPI decorators, not called by name)

from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataPaths,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.repositories import SQLiteDrawDataRepository
from lottolab.interfaces.api.draw_data import (
    ApiValidationErrorResponse,
    RequestValidationIssueView,
    create_draw_data_router,
)
from lottolab.interfaces.api.strategy_catalog import (
    API_VERSION,
    create_strategy_catalog_router,
)
from lottolab.strategies.catalog import StrategyCatalog, production_catalog

LocalDataPathsProvider = Callable[[], LocalDataPaths]


def create_app(
    catalog: StrategyCatalog | None = None,
    data_paths_provider: LocalDataPathsProvider | None = None,
) -> FastAPI:
    app = FastAPI(title="LottoLab API", version="0.1.0")
    resolved_catalog = catalog if catalog is not None else production_catalog()
    resolved_paths_provider = (
        data_paths_provider if data_paths_provider is not None else resolve_local_data_paths
    )

    def repository_factory() -> SQLiteDrawDataRepository:
        return SQLiteDrawDataRepository(resolved_paths_provider())

    @app.exception_handler(RequestValidationError)
    async def sanitized_validation_error(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        del request
        fields = [
            RequestValidationIssueView(
                location=".".join(str(part) for part in issue.get("loc", ())),
                type=str(issue.get("type", "validation_error")),
            )
            for issue in error.errors()
        ]
        response = ApiValidationErrorResponse(
            error_code="REQUEST_VALIDATION_FAILED",
            message="Request validation failed.",
            fields=fields,
        )
        return JSONResponse(
            status_code=422,
            content=response.model_dump(mode="json"),
        )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "api_version": API_VERSION}

    app.include_router(create_strategy_catalog_router(resolved_catalog))
    app.include_router(create_draw_data_router(repository_factory))

    return app
