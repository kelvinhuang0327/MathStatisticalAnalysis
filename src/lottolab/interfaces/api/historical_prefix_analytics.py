"""GET-only API views over one injected historical-prefix analytics result.

The interface forwards one immutable, already-computed result into the merged
application query use cases. It does not read storage, execute strategies,
recompute metrics, rerank candidates, or make predictive claims.
"""

# pyright: reportUnusedFunction=false
# (route handlers are registered by FastAPI decorators, not called by name)

from __future__ import annotations

from collections.abc import Callable
from enum import IntEnum
from typing import Annotated

from fastapi import APIRouter, Path, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from lottolab.application.historical_prefix_queries import (
    DEFAULT_PAGE_LIMIT,
    DEFAULT_PAGE_OFFSET,
    DEFAULT_TOP_K,
    MAX_PAGE_LIMIT,
    MAX_TOP_K,
    MIN_PAGE_LIMIT,
    MIN_TOP_K,
    HistoricalPrefixBestRankings,
    HistoricalPrefixQueryContractError,
    HistoricalPrefixQueryMetadata,
    HistoricalPrefixReplayPage,
    HistoricalPrefixStrategyKey,
    HistoricalPrefixStrategyOverview,
)
from lottolab.application.use_cases.query_historical_prefix_analytics import (
    GetHistoricalPrefixBestRankings,
    ListHistoricalPrefixReplay,
    ListHistoricalPrefixStrategyOverview,
)
from lottolab.domain.historical_prefix_analytics import (
    ExactRatio,
    HistoricalDrawIdentity,
    HistoricalPerDrawPrefixMetrics,
    HistoricalPrefixAnalyticsResult,
    HistoricalPrefixRankingCandidate,
    HistoricalStrategyIdentity,
    HistoricalStrategyPrefixSummary,
)
from lottolab.interfaces.api.draw_data import (
    ApiErrorResponse,
    ApiValidationErrorResponse,
)
from lottolab.interfaces.api.strategy_catalog import API_PREFIX

HistoricalPrefixAnalyticsResultProvider = Callable[[], HistoricalPrefixAnalyticsResult]

TopK = Annotated[int, Query(ge=MIN_TOP_K, le=MAX_TOP_K)]


class OverviewPrefixCount(IntEnum):
    TEN = 10
    FIFTEEN = 15
    TWENTY = 20


class ReplayPrefixCount(IntEnum):
    ONE = 1
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    TEN = 10
    FIFTEEN = 15
    TWENTY = 20
StrategyId = Annotated[
    str,
    Path(min_length=1, max_length=200, pattern=r"^\S(?:.*\S)?$"),
]
StrategyVersion = Annotated[
    str,
    Path(min_length=1, max_length=200, pattern=r"^\S(?:.*\S)?$"),
]
Replicate = Annotated[int, Path(ge=1)]
Limit = Annotated[int, Query(ge=MIN_PAGE_LIMIT, le=MAX_PAGE_LIMIT)]
Offset = Annotated[int, Query(ge=DEFAULT_PAGE_OFFSET)]

_FROZEN_RESPONSE = ConfigDict(frozen=True)


class HistoricalPrefixMetadataView(BaseModel):
    model_config = _FROZEN_RESPONSE

    result_schema_version: str
    source_import_identity_sha256: str
    source_manifest_sha256: str
    source_artifact_sha256: str
    dataset_identity: str
    dataset_sha256: str
    lottery_type: str
    ranking_policy_id: str
    historical_only_disclaimer_id: str

    @classmethod
    def from_metadata(
        cls, metadata: HistoricalPrefixQueryMetadata
    ) -> HistoricalPrefixMetadataView:
        return cls.model_validate(metadata, from_attributes=True)


class ExactRatioView(BaseModel):
    model_config = _FROZEN_RESPONSE

    numerator: int
    denominator: int
    is_available: bool

    @classmethod
    def from_ratio(cls, ratio: ExactRatio) -> ExactRatioView:
        return cls(
            numerator=ratio.numerator,
            denominator=ratio.denominator,
            is_available=ratio.is_available,
        )


class HistoricalPrefixStrategyIdentityView(BaseModel):
    model_config = _FROZEN_RESPONSE

    strategy_id: str
    effective_strategy_id: str
    strategy_version: str
    replicate: int
    identity_kind: str
    governance_status: str
    alias_of_strategy_id: str | None
    equivalence_group: str | None
    nested_prefix_supported: bool

    @classmethod
    def from_identity(
        cls, identity: HistoricalStrategyIdentity
    ) -> HistoricalPrefixStrategyIdentityView:
        return cls(
            strategy_id=identity.strategy_id,
            effective_strategy_id=identity.effective_strategy_id,
            strategy_version=identity.strategy_version,
            replicate=identity.replicate,
            identity_kind=identity.identity_kind.value,
            governance_status=identity.governance_status.value,
            alias_of_strategy_id=identity.alias_of_strategy_id,
            equivalence_group=identity.equivalence_group,
            nested_prefix_supported=identity.nested_prefix_supported,
        )


class HistoricalPrefixDrawIdentityView(BaseModel):
    model_config = _FROZEN_RESPONSE

    draw_number: int
    draw_date: str
    draw_sha256: str

    @classmethod
    def from_identity(
        cls, identity: HistoricalDrawIdentity
    ) -> HistoricalPrefixDrawIdentityView:
        return cls.model_validate(identity, from_attributes=True)


class HistoricalPrefixStrategySummaryView(BaseModel):
    model_config = _FROZEN_RESPONSE

    identity: HistoricalPrefixStrategyIdentityView
    prefix_count: int
    status: str
    distinct_draw_count: int
    replay_ticket_count: int
    portfolio_success_count: int
    portfolio_success_rate: ExactRatioView
    sum_best_main_hit_count: int
    average_best_main_hit_count: ExactRatioView
    sum_total_main_hit_count: int
    average_total_main_hit_count: ExactRatioView
    max_single_main_hit_count: int
    max_portfolio_total_main_hit_count: int
    max_hit_target: HistoricalPrefixDrawIdentityView | None
    m3plus_draw_count: int
    m4plus_draw_count: int
    m5plus_draw_count: int
    m6_draw_count: int
    special_hit_draw_count: int
    special_hit_ticket_count: int
    winning_draw_count: int
    winning_ticket_count: int
    no_prize_ticket_count: int
    first_prize_ticket_count: int
    second_prize_ticket_count: int
    third_prize_ticket_count: int
    fourth_prize_ticket_count: int
    fifth_prize_ticket_count: int
    sixth_prize_ticket_count: int
    seventh_prize_ticket_count: int
    general_prize_ticket_count: int
    ranking_eligible: bool
    ranking_exclusion_reason: str | None

    @classmethod
    def from_summary(
        cls, summary: HistoricalStrategyPrefixSummary
    ) -> HistoricalPrefixStrategySummaryView:
        return cls(
            identity=HistoricalPrefixStrategyIdentityView.from_identity(summary.identity),
            prefix_count=summary.prefix_count,
            status=summary.status.value,
            distinct_draw_count=summary.distinct_draw_count,
            replay_ticket_count=summary.replay_ticket_count,
            portfolio_success_count=summary.portfolio_success_count,
            portfolio_success_rate=ExactRatioView.from_ratio(summary.portfolio_success_rate),
            sum_best_main_hit_count=summary.sum_best_main_hit_count,
            average_best_main_hit_count=ExactRatioView.from_ratio(
                summary.average_best_main_hit_count
            ),
            sum_total_main_hit_count=summary.sum_total_main_hit_count,
            average_total_main_hit_count=ExactRatioView.from_ratio(
                summary.average_total_main_hit_count
            ),
            max_single_main_hit_count=summary.max_single_main_hit_count,
            max_portfolio_total_main_hit_count=summary.max_portfolio_total_main_hit_count,
            max_hit_target=(
                HistoricalPrefixDrawIdentityView.from_identity(summary.max_hit_target)
                if summary.max_hit_target is not None
                else None
            ),
            m3plus_draw_count=summary.m3plus_draw_count,
            m4plus_draw_count=summary.m4plus_draw_count,
            m5plus_draw_count=summary.m5plus_draw_count,
            m6_draw_count=summary.m6_draw_count,
            special_hit_draw_count=summary.special_hit_draw_count,
            special_hit_ticket_count=summary.special_hit_ticket_count,
            winning_draw_count=summary.winning_draw_count,
            winning_ticket_count=summary.winning_ticket_count,
            no_prize_ticket_count=summary.no_prize_ticket_count,
            first_prize_ticket_count=summary.first_prize_ticket_count,
            second_prize_ticket_count=summary.second_prize_ticket_count,
            third_prize_ticket_count=summary.third_prize_ticket_count,
            fourth_prize_ticket_count=summary.fourth_prize_ticket_count,
            fifth_prize_ticket_count=summary.fifth_prize_ticket_count,
            sixth_prize_ticket_count=summary.sixth_prize_ticket_count,
            seventh_prize_ticket_count=summary.seventh_prize_ticket_count,
            general_prize_ticket_count=summary.general_prize_ticket_count,
            ranking_eligible=summary.ranking_eligible,
            ranking_exclusion_reason=(
                summary.ranking_exclusion_reason.value
                if summary.ranking_exclusion_reason is not None
                else None
            ),
        )


class HistoricalPrefixRankingCandidateView(BaseModel):
    model_config = _FROZEN_RESPONSE

    rank: int
    identity: HistoricalPrefixStrategyIdentityView
    summary: HistoricalPrefixStrategySummaryView
    tie_break_provenance: list[str]

    @classmethod
    def from_candidate(
        cls, candidate: HistoricalPrefixRankingCandidate
    ) -> HistoricalPrefixRankingCandidateView:
        return cls(
            rank=candidate.rank,
            identity=HistoricalPrefixStrategyIdentityView.from_identity(candidate.identity),
            summary=HistoricalPrefixStrategySummaryView.from_summary(candidate.summary),
            tie_break_provenance=list(candidate.tie_break_provenance),
        )


class HistoricalPrefixRankingGroupView(BaseModel):
    model_config = _FROZEN_RESPONSE

    prefix_count: int
    status: str
    total_candidate_count: int
    requested_top_k: int
    candidates: list[HistoricalPrefixRankingCandidateView]


class HistoricalPrefixRankingsResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    metadata: HistoricalPrefixMetadataView
    top_k: int
    groups: list[HistoricalPrefixRankingGroupView]

    @classmethod
    def from_rankings(
        cls, rankings: HistoricalPrefixBestRankings
    ) -> HistoricalPrefixRankingsResponse:
        return cls(
            metadata=HistoricalPrefixMetadataView.from_metadata(rankings.metadata),
            top_k=rankings.top_k,
            groups=[
                HistoricalPrefixRankingGroupView(
                    prefix_count=group.prefix_count,
                    status=group.status.value,
                    total_candidate_count=group.total_candidate_count,
                    requested_top_k=group.requested_top_k,
                    candidates=[
                        HistoricalPrefixRankingCandidateView.from_candidate(candidate)
                        for candidate in group.candidates
                    ],
                )
                for group in rankings.groups
            ],
        )


class HistoricalPrefixStrategyOverviewResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    metadata: HistoricalPrefixMetadataView
    prefix_count: int
    summaries: list[HistoricalPrefixStrategySummaryView]
    total_count: int

    @classmethod
    def from_overview(
        cls, overview: HistoricalPrefixStrategyOverview
    ) -> HistoricalPrefixStrategyOverviewResponse:
        return cls(
            metadata=HistoricalPrefixMetadataView.from_metadata(overview.metadata),
            prefix_count=overview.prefix_count,
            summaries=[
                HistoricalPrefixStrategySummaryView.from_summary(summary)
                for summary in overview.summaries
            ],
            total_count=overview.total_count,
        )


class HistoricalPerDrawPrefixMetricsView(BaseModel):
    model_config = _FROZEN_RESPONSE

    identity: HistoricalPrefixStrategyIdentityView
    prefix_count: int
    prefix_ticket_count: int
    included_ticket_positions: list[int]
    best_single_main_hit_count: int
    best_single_ticket_position: int
    total_main_hit_count: int
    portfolio_success: bool
    m3plus: bool
    m4plus: bool
    m5plus: bool
    m6: bool
    special_hit: bool
    special_hit_ticket_count: int
    winning_ticket_count: int
    no_prize_ticket_count: int
    first_prize_ticket_count: int
    second_prize_ticket_count: int
    third_prize_ticket_count: int
    fourth_prize_ticket_count: int
    fifth_prize_ticket_count: int
    sixth_prize_ticket_count: int
    seventh_prize_ticket_count: int
    general_prize_ticket_count: int
    strongest_winning_tier: str
    target: HistoricalPrefixDrawIdentityView
    cutoff: HistoricalPrefixDrawIdentityView

    @classmethod
    def from_metric(
        cls, metric: HistoricalPerDrawPrefixMetrics
    ) -> HistoricalPerDrawPrefixMetricsView:
        return cls(
            identity=HistoricalPrefixStrategyIdentityView.from_identity(metric.identity),
            prefix_count=metric.prefix_count,
            prefix_ticket_count=metric.prefix_ticket_count,
            included_ticket_positions=list(metric.included_ticket_positions),
            best_single_main_hit_count=metric.best_single_main_hit_count,
            best_single_ticket_position=metric.best_single_ticket_position,
            total_main_hit_count=metric.total_main_hit_count,
            portfolio_success=metric.portfolio_success,
            m3plus=metric.m3plus,
            m4plus=metric.m4plus,
            m5plus=metric.m5plus,
            m6=metric.m6,
            special_hit=metric.special_hit,
            special_hit_ticket_count=metric.special_hit_ticket_count,
            winning_ticket_count=metric.winning_ticket_count,
            no_prize_ticket_count=metric.no_prize_ticket_count,
            first_prize_ticket_count=metric.first_prize_ticket_count,
            second_prize_ticket_count=metric.second_prize_ticket_count,
            third_prize_ticket_count=metric.third_prize_ticket_count,
            fourth_prize_ticket_count=metric.fourth_prize_ticket_count,
            fifth_prize_ticket_count=metric.fifth_prize_ticket_count,
            sixth_prize_ticket_count=metric.sixth_prize_ticket_count,
            seventh_prize_ticket_count=metric.seventh_prize_ticket_count,
            general_prize_ticket_count=metric.general_prize_ticket_count,
            strongest_winning_tier=metric.strongest_winning_tier.value,
            target=HistoricalPrefixDrawIdentityView.from_identity(metric.target),
            cutoff=HistoricalPrefixDrawIdentityView.from_identity(metric.cutoff),
        )


class HistoricalPrefixReplayPageResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    metadata: HistoricalPrefixMetadataView
    strategy: HistoricalPrefixStrategyIdentityView
    prefix_count: int
    items: list[HistoricalPerDrawPrefixMetricsView]
    total_count: int
    limit: int
    offset: int

    @classmethod
    def from_page(
        cls,
        page: HistoricalPrefixReplayPage,
        *,
        strategy_identity: HistoricalStrategyIdentity,
    ) -> HistoricalPrefixReplayPageResponse:
        return cls(
            metadata=HistoricalPrefixMetadataView.from_metadata(page.metadata),
            strategy=HistoricalPrefixStrategyIdentityView.from_identity(strategy_identity),
            prefix_count=page.prefix_count,
            items=[HistoricalPerDrawPrefixMetricsView.from_metric(item) for item in page.items],
            total_count=page.total_count,
            limit=page.limit,
            offset=page.offset,
        )


def create_historical_prefix_analytics_router(
    result_provider: HistoricalPrefixAnalyticsResultProvider | None,
) -> APIRouter:
    """Expose all routes without invoking the optional provider at construction."""

    router = APIRouter(prefix=API_PREFIX, tags=["historical-prefix-analytics"])
    rankings_query = GetHistoricalPrefixBestRankings()
    overview_query = ListHistoricalPrefixStrategyOverview()
    replay_query = ListHistoricalPrefixReplay()

    @router.get(
        "/historical-prefix-analytics/rankings",
        response_model=HistoricalPrefixRankingsResponse,
        responses={
            422: {"model": ApiValidationErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="getHistoricalPrefixRankings",
    )
    def get_historical_prefix_rankings(
        top_k: TopK = DEFAULT_TOP_K,
    ) -> HistoricalPrefixRankingsResponse | JSONResponse:
        if result_provider is None:
            return _not_configured_error()
        try:
            result = result_provider()
            rankings = rankings_query.execute(result, top_k=top_k)
            return HistoricalPrefixRankingsResponse.from_rankings(rankings)
        except Exception:
            return _unavailable_error()

    @router.get(
        "/historical-prefix-analytics/strategies",
        response_model=HistoricalPrefixStrategyOverviewResponse,
        responses={
            422: {"model": ApiValidationErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="listHistoricalPrefixStrategies",
    )
    def list_historical_prefix_strategies(
        prefix_count: OverviewPrefixCount,
    ) -> HistoricalPrefixStrategyOverviewResponse | JSONResponse:
        if result_provider is None:
            return _not_configured_error()
        try:
            result = result_provider()
            overview = overview_query.execute(result, prefix_count=int(prefix_count))
            return HistoricalPrefixStrategyOverviewResponse.from_overview(overview)
        except Exception:
            return _unavailable_error()

    @router.get(
        (
            "/historical-prefix-analytics/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}/replay"
        ),
        response_model=HistoricalPrefixReplayPageResponse,
        responses={
            404: {"model": ApiErrorResponse},
            422: {"model": ApiValidationErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="listHistoricalPrefixStrategyReplay",
    )
    def list_historical_prefix_strategy_replay(
        strategy_id: StrategyId,
        strategy_version: StrategyVersion,
        replicate: Replicate,
        prefix_count: ReplayPrefixCount,
        limit: Limit = DEFAULT_PAGE_LIMIT,
        offset: Offset = DEFAULT_PAGE_OFFSET,
    ) -> HistoricalPrefixReplayPageResponse | JSONResponse:
        if result_provider is None:
            return _not_configured_error()
        try:
            result = result_provider()
            strategy = HistoricalPrefixStrategyKey(
                strategy_id=strategy_id,
                strategy_version=strategy_version,
                replicate=replicate,
            )
            page = replay_query.execute(
                result,
                strategy=strategy,
                prefix_count=int(prefix_count),
                limit=limit,
                offset=offset,
            )
            if page is None:
                return _strategy_not_found_error()
            return HistoricalPrefixReplayPageResponse.from_page(
                page,
                strategy_identity=_exact_strategy_identity(result, page.strategy),
            )
        except HistoricalPrefixQueryContractError:
            return _unavailable_error()
        except Exception:
            return _unavailable_error()

    return router


def _exact_strategy_identity(
    result: HistoricalPrefixAnalyticsResult,
    strategy: HistoricalPrefixStrategyKey,
) -> HistoricalStrategyIdentity:
    return next(
        summary.identity
        for summary in result.all_strategy_summaries
        if summary.identity.strategy_id == strategy.strategy_id
        and summary.identity.strategy_version == strategy.strategy_version
        and summary.identity.replicate == strategy.replicate
    )


def _not_configured_error() -> JSONResponse:
    return _error_response(
        503,
        "HISTORICAL_PREFIX_ANALYTICS_NOT_CONFIGURED",
        "Historical prefix analytics is not configured.",
    )


def _unavailable_error() -> JSONResponse:
    return _error_response(
        503,
        "HISTORICAL_PREFIX_ANALYTICS_UNAVAILABLE",
        "Historical prefix analytics is unavailable.",
    )


def _strategy_not_found_error() -> JSONResponse:
    return _error_response(
        404,
        "HISTORICAL_PREFIX_STRATEGY_NOT_FOUND",
        "Historical prefix strategy was not found.",
    )


def _error_response(status_code: int, error_code: str, message: str) -> JSONResponse:
    model = ApiErrorResponse(error_code=error_code, message=message)
    return JSONResponse(status_code=status_code, content=model.model_dump(mode="json"))


__all__ = [
    "ExactRatioView",
    "HistoricalPerDrawPrefixMetricsView",
    "HistoricalPrefixAnalyticsResultProvider",
    "HistoricalPrefixDrawIdentityView",
    "HistoricalPrefixMetadataView",
    "HistoricalPrefixRankingCandidateView",
    "HistoricalPrefixRankingGroupView",
    "HistoricalPrefixRankingsResponse",
    "HistoricalPrefixReplayPageResponse",
    "HistoricalPrefixStrategyIdentityView",
    "HistoricalPrefixStrategyOverviewResponse",
    "HistoricalPrefixStrategySummaryView",
    "create_historical_prefix_analytics_router",
]
