"""Bounded, DB-free HTTP execution for the three ONLINE BIG_LOTTO strategies.

Intended for the existing local-runtime controller, which binds services to
127.0.0.1. No in-app authentication is added here, and no production
deployment or public exposure is claimed.
"""

# pyright: reportUnusedFunction=false
# (route handlers are registered by FastAPI decorators, not called by name)

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from lottolab.application.use_cases.generate_bet import (
    GenerateOneBet,
    GenerateOneBetInput,
    GenerateOneBetReason,
    GenerateOneBetStatus,
)
from lottolab.domain.draws import LotteryType
from lottolab.interfaces.api.draw_data import ApiValidationErrorResponse
from lottolab.interfaces.api.strategy_catalog import API_PREFIX
from lottolab.strategies.adapters.base import CausalDrawRow

_STRICT_BODY = ConfigDict(extra="forbid", str_strip_whitespace=True)
_FROZEN_RESPONSE = ConfigDict(frozen=True)


class GenerateBetHistoryRow(BaseModel):
    model_config = _STRICT_BODY

    draw: str = Field(min_length=1, max_length=64)
    date: str = Field(min_length=1, max_length=64)
    numbers: list[StrictInt] = Field(max_length=20)


class GenerateBetRequest(BaseModel):
    model_config = _STRICT_BODY

    strategy_id: str = Field(min_length=1, max_length=100)
    seed: StrictInt = Field(ge=0)
    history: list[GenerateBetHistoryRow] = Field(max_length=5000)


class GenerateBetResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    strategy_id: str
    lottery_type: LotteryType
    seed: int
    status: GenerateOneBetStatus
    numbers: list[int] | None
    reason_code: GenerateOneBetReason | None


def create_generate_bet_router(generate_one_bet: GenerateOneBet) -> APIRouter:
    """Bind an already-composed GenerateOneBet dependency; compose nothing here."""
    router = APIRouter(prefix=API_PREFIX, tags=["generate-bet"])

    @router.post(
        "/generate-bet",
        response_model=GenerateBetResponse,
        operation_id="generateOneBet",
        responses={422: {"model": ApiValidationErrorResponse}},
    )
    def generate_bet(request: GenerateBetRequest) -> GenerateBetResponse:
        history = tuple(
            CausalDrawRow(draw=row.draw, date=row.date, numbers=tuple(row.numbers))
            for row in request.history
        )
        result = generate_one_bet.execute(
            GenerateOneBetInput(
                strategy_id=request.strategy_id,
                lottery_type=LotteryType.BIG_LOTTO,
                history=history,
            )
        )
        return GenerateBetResponse(
            strategy_id=request.strategy_id,
            lottery_type=LotteryType.BIG_LOTTO,
            seed=request.seed,
            status=result.status,
            numbers=list(result.numbers) if result.numbers is not None else None,
            reason_code=result.reason_code,
        )

    return router


__all__ = [
    "GenerateBetHistoryRow",
    "GenerateBetRequest",
    "GenerateBetResponse",
    "create_generate_bet_router",
]
