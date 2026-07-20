"""Bounded, DB-free HTTP endpoint for the P605E live Zone Split multi-bet use case.

Intended for the existing local-runtime controller, which binds services to
127.0.0.1. No in-app authentication is added here, and no production
deployment or public exposure is claimed. Distinct from, and never routes
through, POST /api/v1/generate-bet or GenerateOneBet.
"""

# pyright: reportUnusedFunction=false
# (route handlers are registered by FastAPI decorators, not called by name)

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from lottolab.application.use_cases.generate_live_zone_split_bets import (
    GenerateLiveZoneSplitBets,
    GenerateLiveZoneSplitBetsInput,
    GenerateLiveZoneSplitBetsReason,
    GenerateLiveZoneSplitBetsStatus,
)
from lottolab.interfaces.api.draw_data import ApiValidationErrorResponse
from lottolab.interfaces.api.strategy_catalog import API_PREFIX

_STRICT_BODY = ConfigDict(extra="forbid")
_FROZEN_RESPONSE = ConfigDict(frozen=True)


class LiveZoneSplitRequest(BaseModel):
    model_config = _STRICT_BODY

    num_bets: StrictInt = Field(ge=1, le=10)


class LiveZoneSplitResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    status: GenerateLiveZoneSplitBetsStatus
    bets: list[list[int]] | None
    coverage_rate: float | None
    total_unique_numbers: int | None
    method: str | None
    philosophy: str | None
    reason_code: GenerateLiveZoneSplitBetsReason | None


def create_live_zone_split_router(
    generate_live_zone_split_bets: GenerateLiveZoneSplitBets,
) -> APIRouter:
    """Bind an already-composed GenerateLiveZoneSplitBets dependency; compose nothing here."""
    router = APIRouter(prefix=API_PREFIX, tags=["live-zone-split"])

    @router.post(
        "/live-zone-split-bets",
        response_model=LiveZoneSplitResponse,
        operation_id="generateLiveZoneSplitBets",
        responses={422: {"model": ApiValidationErrorResponse}},
    )
    def live_zone_split_bets(request: LiveZoneSplitRequest) -> LiveZoneSplitResponse:
        result = generate_live_zone_split_bets.execute(
            GenerateLiveZoneSplitBetsInput(num_bets=request.num_bets)
        )
        return LiveZoneSplitResponse(
            status=result.status,
            bets=[list(bet) for bet in result.bets] if result.bets is not None else None,
            coverage_rate=result.coverage_rate,
            total_unique_numbers=result.total_unique_numbers,
            method=result.method,
            philosophy=result.philosophy,
            reason_code=result.reason_code,
        )

    return router


__all__ = [
    "LiveZoneSplitRequest",
    "LiveZoneSplitResponse",
    "create_live_zone_split_router",
]
