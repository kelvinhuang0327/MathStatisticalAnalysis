"""FastAPI application factory.

Run locally:
    uv run uvicorn --factory quantlab.interfaces.api.app:create_app --reload
"""

# pyright: reportUnusedFunction=false
# (route handlers are registered by FastAPI decorators, not called by name)

from __future__ import annotations

from fastapi import FastAPI

from quantlab.application.dto import StrategyView
from quantlab.application.use_cases.list_strategies import ListStrategies
from quantlab.strategies.catalog import StrategyCatalog, production_catalog

API_VERSION = "v1"


def create_app(catalog: StrategyCatalog | None = None) -> FastAPI:
    app = FastAPI(title="QuantLab API", version="0.1.0")
    list_strategies = ListStrategies(catalog if catalog is not None else production_catalog())

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "api_version": API_VERSION}

    @app.get("/api/strategies", response_model=list[StrategyView])
    def strategies() -> list[StrategyView]:
        return list(list_strategies.execute())

    return app
