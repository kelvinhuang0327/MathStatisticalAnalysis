"""GET-only API for one exact persisted Replay-scoring projection."""

# pyright: reportUnusedFunction=false
# (route handlers are registered by FastAPI decorators, not called by name)

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Path, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from lottolab.application.ports import ReplayScoringProjectionReaderFactory
from lottolab.application.use_cases.query_replay_scoring_projection import (
    QueryReplayScoringProjection,
    ReplayScoringQueryUnavailableError,
    ReplayScoringRunNotFoundError,
)
from lottolab.domain.replay_scoring_projection import (
    ReplayOverallAggregateProjection,
    ReplayScoredPredictionProjection,
    ReplayScoringRunProjection,
    ReplayStrategyAggregateProjection,
)
from lottolab.interfaces.api.draw_data import (
    ApiErrorResponse,
    ApiValidationErrorResponse,
)
from lottolab.interfaces.api.strategy_catalog import API_PREFIX

ScoringArtifactSha256 = Annotated[
    str,
    Path(
        pattern=r"^[0-9a-f]{64}$",
        description="Exact lowercase SHA-256 of the persisted Replay-scoring artifact.",
    ),
]
TargetDrawFilter = Annotated[str | None, Query(pattern=r"^[0-9]{1,32}$")]
StrategyIdFilter = Annotated[str | None, Query(min_length=1, max_length=100)]
StatusFilter = Annotated[str | None, Query(min_length=1, max_length=64)]
TierFilter = Annotated[str | None, Query(min_length=1, max_length=64)]

_FROZEN_RESPONSE = ConfigDict(frozen=True)


class ReplayScoringRunResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    scoring_artifact_schema_version: str
    scoring_artifact_payload_sha256: str
    source_replay_artifact_payload_sha256: str
    dataset_id: str
    dataset_version: str
    lottery_type: str
    target_count: int
    strategy_count: int
    scored_record_count: int
    overall_aggregate_sha256: str

    @classmethod
    def from_projection(cls, projection: ReplayScoringRunProjection) -> ReplayScoringRunResponse:
        return cls.model_validate(projection, from_attributes=True)


class ReplayScoredPredictionView(BaseModel):
    model_config = _FROZEN_RESPONSE

    run_payload_sha256: str
    ordinal: int
    source_snapshot_result_sha256: str
    scored_result_sha256: str
    target_draw_number: str
    target_draw_date: str
    strategy_id: str
    strategy_version: str | None = None
    source_history_status: str
    source_history_reason_code: str | None = None
    source_prediction_status: str | None = None
    source_prediction_reason_code: str | None = None
    scoring_status: str
    scoring_reason_code: str | None = None
    predicted_main_numbers: list[int] | None = None
    target_outcome_sha256: str | None = None
    main_number_hit_count: int | None = None
    special_number_hit: bool | None = None
    prize_tier_id: str | None = None
    prize_official_label: str | None = None
    no_prize_result: str | None = None

    @classmethod
    def from_projection(
        cls, projection: ReplayScoredPredictionProjection
    ) -> ReplayScoredPredictionView:
        return cls.model_validate(projection, from_attributes=True)


class ReplayStrategyAggregateView(BaseModel):
    model_config = _FROZEN_RESPONSE

    run_payload_sha256: str
    ordinal: int
    strategy_id: str
    strategy_version: str | None = None
    source_snapshot_count: int
    scored_count: int
    history_closed_count: int
    prediction_closed_count: int
    target_outcome_not_found_count: int
    target_identity_mismatch_count: int
    first_prize_count: int
    second_prize_count: int
    third_prize_count: int
    fourth_prize_count: int
    fifth_prize_count: int
    sixth_prize_count: int
    seventh_prize_count: int
    general_prize_count: int
    no_prize_count: int
    aggregate_sha256: str

    @classmethod
    def from_projection(
        cls, projection: ReplayStrategyAggregateProjection
    ) -> ReplayStrategyAggregateView:
        return cls.model_validate(projection, from_attributes=True)


class ReplayOverallAggregateResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    run_payload_sha256: str
    source_snapshot_count: int
    scored_count: int
    history_closed_count: int
    prediction_closed_count: int
    target_outcome_not_found_count: int
    target_identity_mismatch_count: int
    first_prize_count: int
    second_prize_count: int
    third_prize_count: int
    fourth_prize_count: int
    fifth_prize_count: int
    sixth_prize_count: int
    seventh_prize_count: int
    general_prize_count: int
    no_prize_count: int
    aggregate_sha256: str

    @classmethod
    def from_projection(
        cls, projection: ReplayOverallAggregateProjection
    ) -> ReplayOverallAggregateResponse:
        return cls.model_validate(projection, from_attributes=True)


def create_replay_scoring_projections_router(
    reader_factory: ReplayScoringProjectionReaderFactory | None,
) -> APIRouter:
    """Expose all four routes without invoking the optional factory at construction."""

    router = APIRouter(prefix=API_PREFIX, tags=["replay-scoring"])
    query = QueryReplayScoringProjection(reader_factory) if reader_factory is not None else None
    error_responses: dict[int | str, dict[str, Any]] = {
        404: {"model": ApiErrorResponse},
        422: {"model": ApiValidationErrorResponse},
        503: {"model": ApiErrorResponse},
    }

    @router.get(
        "/replay-scoring/{scoring_artifact_payload_sha256}",
        response_model=ReplayScoringRunResponse,
        responses=error_responses,
        operation_id="getReplayScoringRun",
    )
    def get_replay_scoring_run(
        scoring_artifact_payload_sha256: ScoringArtifactSha256,
    ) -> ReplayScoringRunResponse | JSONResponse:
        if query is None:
            return _not_configured_error()
        try:
            run = query.get_run(scoring_artifact_payload_sha256)
        except ReplayScoringRunNotFoundError:
            return _not_found_error()
        except Exception:
            return _unavailable_error()
        return ReplayScoringRunResponse.from_projection(run)

    @router.get(
        "/replay-scoring/{scoring_artifact_payload_sha256}/predictions",
        response_model=list[ReplayScoredPredictionView],
        responses=error_responses,
        operation_id="listReplayScoringPredictions",
    )
    def list_replay_scoring_predictions(
        scoring_artifact_payload_sha256: ScoringArtifactSha256,
        target_draw: TargetDrawFilter = None,
        strategy_id: StrategyIdFilter = None,
        status: StatusFilter = None,
        tier: TierFilter = None,
    ) -> list[ReplayScoredPredictionView] | JSONResponse:
        if query is None:
            return _not_configured_error()
        try:
            records = query.list_predictions(
                scoring_artifact_payload_sha256,
                target_draw=target_draw,
                strategy_id=strategy_id,
                status=status,
                tier=tier,
            )
        except ValueError:
            return _invalid_filter_error()
        except ReplayScoringRunNotFoundError:
            return _not_found_error()
        except Exception:
            return _unavailable_error()
        return [ReplayScoredPredictionView.from_projection(record) for record in records]

    @router.get(
        "/replay-scoring/{scoring_artifact_payload_sha256}/strategy-aggregates",
        response_model=list[ReplayStrategyAggregateView],
        responses=error_responses,
        operation_id="listReplayScoringStrategyAggregates",
    )
    def list_replay_scoring_strategy_aggregates(
        scoring_artifact_payload_sha256: ScoringArtifactSha256,
    ) -> list[ReplayStrategyAggregateView] | JSONResponse:
        if query is None:
            return _not_configured_error()
        try:
            aggregates = query.list_strategy_aggregates(scoring_artifact_payload_sha256)
        except ReplayScoringRunNotFoundError:
            return _not_found_error()
        except Exception:
            return _unavailable_error()
        return [ReplayStrategyAggregateView.from_projection(item) for item in aggregates]

    @router.get(
        "/replay-scoring/{scoring_artifact_payload_sha256}/overall-aggregate",
        response_model=ReplayOverallAggregateResponse,
        responses=error_responses,
        operation_id="getReplayScoringOverallAggregate",
    )
    def get_replay_scoring_overall_aggregate(
        scoring_artifact_payload_sha256: ScoringArtifactSha256,
    ) -> ReplayOverallAggregateResponse | JSONResponse:
        if query is None:
            return _not_configured_error()
        try:
            aggregate = query.get_overall_aggregate(scoring_artifact_payload_sha256)
        except ReplayScoringRunNotFoundError:
            return _not_found_error()
        except ReplayScoringQueryUnavailableError:
            return _unavailable_error()
        except Exception:
            return _unavailable_error()
        return ReplayOverallAggregateResponse.from_projection(aggregate)

    return router


def _not_configured_error() -> JSONResponse:
    return _error_response(
        503,
        "REPLAY_SCORING_QUERY_NOT_CONFIGURED",
        "Replay scoring query is not configured.",
    )


def _not_found_error() -> JSONResponse:
    return _error_response(
        404,
        "REPLAY_SCORING_RUN_NOT_FOUND",
        "Replay scoring run was not found.",
    )


def _unavailable_error() -> JSONResponse:
    return _error_response(
        503,
        "REPLAY_SCORING_QUERY_UNAVAILABLE",
        "Replay scoring query is unavailable.",
    )


def _invalid_filter_error() -> JSONResponse:
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
    "ReplayOverallAggregateResponse",
    "ReplayScoredPredictionView",
    "ReplayScoringRunResponse",
    "ReplayStrategyAggregateView",
    "create_replay_scoring_projections_router",
]
