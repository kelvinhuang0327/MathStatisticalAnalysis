"""Read-only HTTP surface for sealed B649 Strategy-K and combination evidence."""

# pyright: reportUnusedFunction=false

from __future__ import annotations

from enum import IntEnum
from typing import Annotated, Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from lottolab.application.b649_strategy_k_combinations import (
    B649CombinationCriterion,
    B649CombinationProxyMode,
    B649CombinationQuery,
    B649CombinationSort,
    B649CombinationWindow,
    B649StrategyAvailability,
    B649StrategyKCriterion,
    B649StrategyKQuery,
    B649StrategyKSort,
    B649StrategyKWindowKind,
    B649WindowRole,
)
from lottolab.application.ports import (
    B649AnalyticsArtifactReader,
    B649AnalyticsArtifactReaderFactory,
)
from lottolab.interfaces.api.draw_data import ApiValidationErrorResponse
from lottolab.interfaces.api.strategy_catalog import API_PREFIX


class B649MemberCount(IntEnum):
    PAIR = 2
    TRIPLE = 3


class B649WindowOptionView(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    window_kind: str
    window_role: B649WindowRole
    requested_draw_count: int | None
    default_emphasis: bool


class B649StrategyAvailabilityView(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    strategy_id: str
    strategy_version: str
    availability: B649StrategyAvailability
    availability_reason: str
    response_shape: str
    native_ticket_count: int


class B649StrategyKSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    authority_task_tree: str
    authority_full_output_tree: str
    matrix_row_count: int
    supported_k_values: list[int]
    supported_criteria: list[B649StrategyKCriterion]
    windows: list[B649WindowOptionView]
    strategies: list[B649StrategyAvailabilityView]
    current_executable_strategy_count: int
    matrix_available_strategy_count: int
    matrix_unavailable_strategy_count: int
    historical_accounted_identity_count: int
    measurement_mode: str
    window_policy_version: str
    duplicate_handling_policy: str
    nested_windows_independent: bool
    predictive_advantage_claimed: bool
    research_disclaimer: str


class B649EffectiveUniqueKCountView(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    effective_unique_k: int
    observation_count: int


class B649StrategyKRecordView(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    strategy_id: str
    strategy_version: str
    requested_k: int
    effective_unique_k_counts: list[B649EffectiveUniqueKCountView]
    criterion: B649StrategyKCriterion
    window_kind: B649StrategyKWindowKind
    window_role: B649WindowRole
    requested_draw_count: int | None
    source_observation_count: int
    eligible_observation_count: int
    excluded_observation_count: int
    success_numerator: int
    success_denominator: int
    random_baseline_numerator: int
    random_baseline_denominator: int
    observed_minus_baseline: str
    first_target_draw: str
    last_target_draw: str
    evaluation_status: str
    measurement_mode: str
    window_policy_version: str
    nested_windows_independent: bool


class B649StrategyKPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    items: list[B649StrategyKRecordView]
    total: int
    limit: int
    offset: int
    requested_k: int
    window_kind: B649StrategyKWindowKind
    window_role: B649WindowRole
    criterion: B649StrategyKCriterion
    sort: B649StrategyKSort
    ranking_label: str
    measurement_mode: str
    research_disclaimer: str


class B649CombinationProxyOptionView(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    proxy_mode: B649CombinationProxyMode
    proxy_label: str


class B649CombinationSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    authority_task_tree: str
    sealed_top_candidate_count: int
    proxy_modes: list[B649CombinationProxyOptionView]
    member_counts: list[int]
    windows: list[B649WindowOptionView]
    supported_criteria: list[B649CombinationCriterion]
    source_scope: str
    full_projection_sent_to_browser: bool
    predictive_advantage_claimed: bool
    research_disclaimer: str


class B649CombinationRecordView(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    proxy_mode: B649CombinationProxyMode
    proxy_label: str
    member_count: int
    member_strategy_ids: list[str]
    combination_id: str
    evaluation_window: B649CombinationWindow
    criterion: B649CombinationCriterion
    sealed_rank: int
    eligible_draws: int
    success_numerator: int
    success_denominator: int
    observed_rate: str
    exact_random_baseline_numerator: int
    exact_random_baseline_denominator: int
    random_baseline_rate: str
    descriptive_delta: str
    evaluation_status: str
    evaluation_reason: str
    long_delta_sign: str | None
    mid_delta_sign: str | None
    short_delta_sign: str | None
    positive_window_count: int
    minimum_delta: str | None
    delta_range: str | None
    cross_window_stable_positive: bool
    historical_search_only: bool
    predictive_advantage_claimed: bool
    prospective_validation_required: bool
    candidate_disposition: str


class B649CombinationPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    items: list[B649CombinationRecordView]
    total: int
    limit: int
    offset: int
    proxy_mode: B649CombinationProxyMode
    member_count: int
    window: B649CombinationWindow
    window_role: B649WindowRole
    criterion: B649CombinationCriterion
    sort: B649CombinationSort
    ranking_label: str
    source_scope: str
    research_disclaimer: str


class B649EvidenceStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    observer_task_tree: str
    historical_evidence_status: str
    pre_freeze_date_unseen_holdout_count: int
    post_freeze_date_prospective_count: int
    observation_count: int
    observation_start_draw: str
    latest_observed_draw: str | None
    checkpoints: list[int]
    checkpoints_reached: list[int]
    primary_outcome: str
    c_forward_status: str
    c_forward_reason: str
    holdout_used_to_rerank_historical_results: bool
    predictive_advantage_claimed: bool


class B649AnalyticsApiErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_code: str
    message: str


class B649StrategyKQueryView(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    requested_k: int = Field(ge=1, le=49)
    window_kind: B649StrategyKWindowKind
    criterion: B649StrategyKCriterion
    q: str | None = Field(default=None, min_length=1, max_length=200)
    sort: B649StrategyKSort = B649StrategyKSort.STRATEGY_ID_ASC
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=10_000)


class B649CombinationQueryView(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    proxy_mode: B649CombinationProxyMode
    member_count: B649MemberCount
    window: B649CombinationWindow
    criterion: B649CombinationCriterion
    member_search: str | None = Field(default=None, min_length=1, max_length=200)
    sort: B649CombinationSort = B649CombinationSort.SEALED_RANK_ASC
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=10_000)


def create_b649_strategy_k_combinations_router(
    reader_factory: B649AnalyticsArtifactReaderFactory | None,
) -> APIRouter:
    """Expose independent, lazy, read-only views over the three authorities."""

    router = APIRouter(prefix=API_PREFIX, tags=["b649-strategy-k-combinations"])
    common_errors: dict[int | str, dict[str, Any]] = {
        422: {"model": ApiValidationErrorResponse},
        503: {"model": B649AnalyticsApiErrorResponse},
    }

    @router.get(
        "/b649-strategy-k-combinations/strategy-k/summary",
        response_model=B649StrategyKSummaryResponse,
        responses={503: {"model": B649AnalyticsApiErrorResponse}},
        operation_id="getB649StrategyKSummary",
    )
    def strategy_k_summary() -> B649StrategyKSummaryResponse | JSONResponse:
        try:
            summary = _reader(reader_factory).strategy_k_summary()
        except Exception:
            return _unavailable("STRATEGY_K")
        return B649StrategyKSummaryResponse.model_validate(summary, from_attributes=True)

    @router.get(
        "/b649-strategy-k-combinations/strategy-k",
        response_model=B649StrategyKPageResponse,
        responses=common_errors,
        operation_id="listB649StrategyKRecords",
    )
    def strategy_k(
        query: Annotated[B649StrategyKQueryView, Query()],
    ) -> B649StrategyKPageResponse | JSONResponse:
        application_query = B649StrategyKQuery(
            requested_k=query.requested_k,
            window_kind=query.window_kind,
            criterion=query.criterion,
            q=query.q,
            sort=query.sort,
            limit=query.limit,
            offset=query.offset,
        )
        try:
            page = _reader(reader_factory).query_strategy_k(application_query)
        except ValueError as exc:
            return _invalid_query(str(exc))
        except Exception:
            return _unavailable("STRATEGY_K")
        return B649StrategyKPageResponse.model_validate(page, from_attributes=True)

    @router.get(
        "/b649-strategy-k-combinations/combinations/summary",
        response_model=B649CombinationSummaryResponse,
        responses={503: {"model": B649AnalyticsApiErrorResponse}},
        operation_id="getB649CombinationSummary",
    )
    def combination_summary() -> B649CombinationSummaryResponse | JSONResponse:
        try:
            summary = _reader(reader_factory).combination_summary()
        except Exception:
            return _unavailable("COMBINATIONS")
        return B649CombinationSummaryResponse.model_validate(summary, from_attributes=True)

    @router.get(
        "/b649-strategy-k-combinations/combinations",
        response_model=B649CombinationPageResponse,
        responses=common_errors,
        operation_id="listB649Combinations",
    )
    def combinations(
        query: Annotated[B649CombinationQueryView, Query()],
    ) -> B649CombinationPageResponse | JSONResponse:
        application_query = B649CombinationQuery(
            proxy_mode=query.proxy_mode,
            member_count=int(query.member_count),
            window=query.window,
            criterion=query.criterion,
            member_search=query.member_search,
            sort=query.sort,
            limit=query.limit,
            offset=query.offset,
        )
        try:
            page = _reader(reader_factory).query_combinations(application_query)
        except ValueError as exc:
            return _invalid_query(str(exc))
        except Exception:
            return _unavailable("COMBINATIONS")
        return B649CombinationPageResponse.model_validate(page, from_attributes=True)

    @router.get(
        "/b649-strategy-k-combinations/evidence-status",
        response_model=B649EvidenceStatusResponse,
        responses={503: {"model": B649AnalyticsApiErrorResponse}},
        operation_id="getB649CombinationEvidenceStatus",
    )
    def evidence_status() -> B649EvidenceStatusResponse | JSONResponse:
        try:
            status = _reader(reader_factory).evidence_status()
        except Exception:
            return _unavailable("OBSERVER")
        return B649EvidenceStatusResponse.model_validate(status, from_attributes=True)

    return router


def _reader(
    factory: B649AnalyticsArtifactReaderFactory | None,
) -> B649AnalyticsArtifactReader:
    if factory is None:
        raise RuntimeError("B649 analytics authority reader is not configured")
    return factory()


def _unavailable(surface: str) -> JSONResponse:
    response = B649AnalyticsApiErrorResponse(
        error_code=f"B649_{surface}_AUTHORITY_UNAVAILABLE",
        message=f"The sealed B649 {surface.lower()} authority is unavailable.",
    )
    return JSONResponse(status_code=503, content=response.model_dump(mode="json"))


def _invalid_query(message: str) -> JSONResponse:
    response = B649AnalyticsApiErrorResponse(
        error_code="B649_ANALYTICS_QUERY_INVALID",
        message=message,
    )
    return JSONResponse(status_code=422, content=response.model_dump(mode="json"))


__all__ = [
    "B649AnalyticsApiErrorResponse",
    "B649CombinationPageResponse",
    "B649CombinationSummaryResponse",
    "B649EvidenceStatusResponse",
    "B649StrategyKPageResponse",
    "B649StrategyKSummaryResponse",
    "create_b649_strategy_k_combinations_router",
]
