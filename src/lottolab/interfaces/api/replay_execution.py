"""Thin HTTP transport for the existing ReplayHistoricalPredictions use case.

Translates one HTTP request into one
:class:`~lottolab.application.use_cases.replay_historical_predictions.ReplayHistoricalPredictionsInput`,
calls the injected executor, and serializes its closed result. No prediction,
scoring, ranking, or persistence happens here -- see
:mod:`lottolab.application.use_cases.replay_historical_predictions` for the
use case this only adapts. The injected executor is called at most once per
request and never at app construction or OpenAPI-generation time.
"""

# pyright: reportUnusedFunction=false
# (route handlers are registered by FastAPI decorators, not called by name)

from __future__ import annotations

from datetime import date
from typing import Annotated, Protocol

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from lottolab.application.use_cases.replay_historical_predictions import (
    ReplayHistoricalPredictionsInput,
    ReplayHistoricalPredictionsResult,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_predictions import ReplaySourceMode, ReplayTarget
from lottolab.interfaces.api.draw_data import ApiErrorResponse, ApiValidationErrorResponse
from lottolab.interfaces.api.strategy_catalog import API_PREFIX

_STRICT_BODY = ConfigDict(extra="forbid")
_FROZEN_RESPONSE = ConfigDict(frozen=True)

_MAX_TARGETS = 500
_MAX_STRATEGY_IDS = 100

_StrategyId = Annotated[str, Field(min_length=1, max_length=100)]


class ReplayExecutor(Protocol):
    """Structural boundary: anything shaped like ReplayHistoricalPredictions.execute()."""

    def execute(
        self, request: ReplayHistoricalPredictionsInput
    ) -> ReplayHistoricalPredictionsResult: ...


class ReplayExecutionTargetRequest(BaseModel):
    model_config = _STRICT_BODY

    draw_number: str = Field(min_length=1, max_length=64)
    draw_date: date


class ReplayExecutionRequest(BaseModel):
    model_config = _STRICT_BODY

    lottery_type: LotteryType
    dataset_id: str = Field(min_length=1, max_length=200)
    dataset_version: str = Field(min_length=1, max_length=200)
    targets: list[ReplayExecutionTargetRequest] = Field(min_length=1, max_length=_MAX_TARGETS)
    strategy_ids: list[_StrategyId] = Field(min_length=1, max_length=_MAX_STRATEGY_IDS)
    # No numeric floor here: BuildCausalHistory treats an out-of-range bound as
    # its own closed INVALID_BOUNDS result, not a request error -- narrowing
    # this would silently pre-empt that existing contract.
    maximum_history_draws: int | None = None
    minimum_history_draws: int | None = None


class ReplayExecutionSnapshotView(BaseModel):
    model_config = _FROZEN_RESPONSE

    snapshot_schema_version: str
    dataset_id: str
    dataset_version: str
    lottery_type: LotteryType
    source_mode: ReplaySourceMode
    target_draw_number: str
    target_draw_date: date
    cutoff_draw_number: str | None = None
    cutoff_draw_date: date | None = None
    strategy_id: str
    strategy_version: str | None = None
    adapter_strategy_id: str | None = None
    adapter_strategy_name: str | None = None
    adapter_strategy_version: str | None = None
    history_status: str
    history_reason_code: str | None = None
    causal_history_count: int | None = None
    causal_history_sha256: str | None = None
    prediction_status: str | None = None
    prediction_reason_code: str | None = None
    predicted_main_numbers: list[int] | None = None
    result_sha256: str


class ReplayExecutionResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    snapshots: list[ReplayExecutionSnapshotView]

    @classmethod
    def from_result(cls, result: ReplayHistoricalPredictionsResult) -> ReplayExecutionResponse:
        return cls(
            snapshots=[
                ReplayExecutionSnapshotView.model_validate(snapshot, from_attributes=True)
                for snapshot in result.snapshots
            ]
        )


def create_replay_execution_router(executor: ReplayExecutor | None) -> APIRouter:
    """Bind an already-composed ReplayHistoricalPredictions-compatible executor.

    Always exposes the route without requiring the executor at construction,
    mirroring the other replay read routers.
    """

    router = APIRouter(prefix=API_PREFIX, tags=["replay-execution"])

    @router.post(
        "/replay-execution",
        response_model=ReplayExecutionResponse,
        responses={
            422: {"model": ApiValidationErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="executeReplayHistoricalPredictions",
    )
    def execute_replay(
        request: ReplayExecutionRequest,
    ) -> ReplayExecutionResponse | JSONResponse:
        if executor is None:
            return _not_configured_error()

        try:
            use_case_input = ReplayHistoricalPredictionsInput(
                lottery_type=request.lottery_type,
                dataset_id=request.dataset_id,
                dataset_version=request.dataset_version,
                targets=tuple(
                    ReplayTarget(draw_number=target.draw_number, draw_date=target.draw_date)
                    for target in request.targets
                ),
                strategy_ids=tuple(request.strategy_ids),
                maximum_history_draws=request.maximum_history_draws,
                minimum_history_draws=request.minimum_history_draws,
            )
        except ValueError:
            # Covers DuplicateReplayTargetError/DuplicateReplayStrategyError,
            # both ValueError subclasses raised by the use case's own
            # __post_init__ -- never re-derived here.
            return _invalid_request_error()

        try:
            result = executor.execute(use_case_input)
        except Exception:
            return _unavailable_error()

        return ReplayExecutionResponse.from_result(result)

    return router


def _not_configured_error() -> JSONResponse:
    return _error_response(
        503,
        "REPLAY_EXECUTION_NOT_CONFIGURED",
        "Replay execution is not configured.",
    )


def _unavailable_error() -> JSONResponse:
    return _error_response(
        503,
        "REPLAY_EXECUTION_UNAVAILABLE",
        "Replay execution is unavailable.",
    )


def _invalid_request_error() -> JSONResponse:
    model = ApiValidationErrorResponse(
        error_code="REQUEST_VALIDATION_FAILED",
        message="Request validation failed.",
        fields=[],
    )
    return JSONResponse(status_code=422, content=model.model_dump(mode="json"))


def _error_response(status_code: int, error_code: str, message: str) -> JSONResponse:
    model = ApiErrorResponse(error_code=error_code, message=message)
    return JSONResponse(status_code=status_code, content=model.model_dump(mode="json"))


__all__ = [
    "ReplayExecutionRequest",
    "ReplayExecutionResponse",
    "ReplayExecutionSnapshotView",
    "ReplayExecutionTargetRequest",
    "ReplayExecutor",
    "create_replay_execution_router",
]
