"""Thin HTTP view of committed strategy-evidence and D3 availability."""

# pyright: reportUnusedFunction=false

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from lottolab.application.dto import StrategyEvidenceResponse
from lottolab.application.ports import StrategyEvidenceRegistryReader
from lottolab.application.strategy_evidence import StrategyEvidenceRegistryUnavailableError
from lottolab.application.use_cases.query_strategy_evidence import QueryStrategyEvidence
from lottolab.interfaces.api.draw_data import ApiErrorResponse
from lottolab.interfaces.api.strategy_catalog import API_PREFIX
from lottolab.strategies.catalog import StrategyCatalog


def create_strategy_evidence_router(
    catalog: StrategyCatalog,
    registry_reader: StrategyEvidenceRegistryReader,
) -> APIRouter:
    router = APIRouter(prefix=API_PREFIX, tags=["strategy-evidence"])
    query = QueryStrategyEvidence(catalog, registry_reader)

    @router.get(
        "/strategy-evidence",
        response_model=StrategyEvidenceResponse,
        responses={503: {"model": ApiErrorResponse}},
        operation_id="queryStrategyEvidence",
    )
    def strategy_evidence() -> StrategyEvidenceResponse | JSONResponse:
        try:
            return query.execute()
        except StrategyEvidenceRegistryUnavailableError:
            error = ApiErrorResponse(
                error_code="STRATEGY_EVIDENCE_REGISTRY_UNAVAILABLE",
                message="Canonical strategy evidence metadata is unavailable.",
            )
            return JSONResponse(
                status_code=503,
                content=error.model_dump(mode="json"),
            )

    return router
