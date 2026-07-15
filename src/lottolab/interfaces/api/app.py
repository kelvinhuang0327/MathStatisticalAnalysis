"""FastAPI application factory.

Run locally:
    uv run uvicorn --factory lottolab.interfaces.api.app:create_app --reload
"""

# pyright: reportUnusedFunction=false
# (route handlers are registered by FastAPI decorators, not called by name)

from __future__ import annotations

from fastapi import FastAPI

from lottolab.interfaces.api.strategy_catalog import (
    API_VERSION,
    create_strategy_catalog_router,
)
from lottolab.strategies.catalog import StrategyCatalog, production_catalog


def create_app(catalog: StrategyCatalog | None = None) -> FastAPI:
    app = FastAPI(title="LottoLab API", version="0.1.0")
    resolved_catalog = catalog if catalog is not None else production_catalog()

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "api_version": API_VERSION}

    app.include_router(create_strategy_catalog_router(resolved_catalog))

    return app
