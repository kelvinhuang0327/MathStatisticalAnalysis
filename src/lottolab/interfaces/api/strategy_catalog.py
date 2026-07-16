"""DB-free HTTP adapter for the read-only Strategy Catalog capability."""

# pyright: reportUnusedFunction=false
# (route handlers are registered by FastAPI decorators, not called by name)

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field

from lottolab.application.dto import StrategyOverviewResponse, StrategyView
from lottolab.application.use_cases.list_strategies import ListStrategies
from lottolab.application.use_cases.query_strategy_overview import (
    MAX_STRATEGY_SEARCH_LENGTH,
    QueryStrategyOverview,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import LifecycleStatus
from lottolab.strategies.catalog import StrategyCatalog

API_VERSION = "v1"
API_PREFIX = f"/api/{API_VERSION}"


class StrategyOverviewQuery(BaseModel):
    """Bounded filters; extra query properties fail FastAPI validation."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    q: str | None = Field(default=None, min_length=1, max_length=MAX_STRATEGY_SEARCH_LENGTH)
    lottery_type: LotteryType | None = None
    lifecycle_status: LifecycleStatus | None = None
    executable: bool | None = None


def create_strategy_catalog_router(catalog: StrategyCatalog) -> APIRouter:
    """Bind the list use case without importing persistence or runtime adapters."""
    router = APIRouter(prefix=API_PREFIX, tags=["strategy-catalog"])
    list_strategies = ListStrategies(catalog)
    query_strategy_overview = QueryStrategyOverview(catalog)

    @router.get(
        "/strategies",
        response_model=list[StrategyView],
        operation_id="listStrategies",
    )
    def strategies() -> list[StrategyView]:
        return list(list_strategies.execute())

    @router.get(
        "/strategy-overview",
        response_model=StrategyOverviewResponse,
        operation_id="queryStrategyOverview",
    )
    def strategy_overview(
        query: Annotated[StrategyOverviewQuery, Query()],
    ) -> StrategyOverviewResponse:
        return query_strategy_overview.execute(
            q=query.q,
            lottery_type=query.lottery_type,
            lifecycle_status=query.lifecycle_status,
            executable=query.executable,
        )

    return router
