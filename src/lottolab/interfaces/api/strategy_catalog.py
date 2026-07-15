"""DB-free HTTP adapter for the read-only Strategy Catalog capability."""

# pyright: reportUnusedFunction=false
# (route handlers are registered by FastAPI decorators, not called by name)

from __future__ import annotations

from fastapi import APIRouter

from lottolab.application.dto import StrategyView
from lottolab.application.use_cases.list_strategies import ListStrategies
from lottolab.strategies.catalog import StrategyCatalog

API_VERSION = "v1"
API_PREFIX = f"/api/{API_VERSION}"


def create_strategy_catalog_router(catalog: StrategyCatalog) -> APIRouter:
    """Bind the list use case without importing persistence or runtime adapters."""
    router = APIRouter(prefix=API_PREFIX, tags=["strategy-catalog"])
    list_strategies = ListStrategies(catalog)

    @router.get(
        "/strategies",
        response_model=list[StrategyView],
        operation_id="listStrategies",
    )
    def strategies() -> list[StrategyView]:
        return list(list_strategies.execute())

    return router
