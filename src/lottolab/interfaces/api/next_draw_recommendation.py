"""API for the Next-Draw Recommendation product surface (P2).

Serves ``NEXT_DRAW_ROBUSTNESS_V1`` rankings composed from one already-built
:class:`NextDrawRecommendationEvidenceArtifact` (a FRESH_UNREVIEWED backtest
snapshot -- see that module's docstring), and never reinterprets
``replay_portfolio_ranking``'s or the B649 multi-ticket records' descriptive
rankings as its own evidence.

The ranking itself generates no numbers. Separately, for at most the top
``TOP_N`` ranked candidates, this route executes each strategy's own shipped
adapter against the current real causal history (every draw up to the
latest completed one) to show its native ticket(s) "as of right now" --
using the exact same adapter contract the backtest evidence was computed
with, never a separate re-implementation. This is a live execution, not a
future-performance claim: it shows what the strategy would bet today, not
what it will win.

Both the evidence-artifact factory and the causal-history factory are
called at most once per request and never at app construction or
OpenAPI-generation time.
"""

# pyright: reportUnusedFunction=false
# (route handlers are registered by FastAPI decorators, not called by name)

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from lottolab.application.use_cases.build_next_draw_recommendation import (
    BuildNextDrawRecommendationBucket,
)
from lottolab.application.use_cases.generate_next_draw_top_tickets import (
    GenerateNextDrawTopTickets,
    GeneratedTicketSet,
    TicketGenerationStatus,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.next_draw_recommendation import (
    NATIVE_TICKET_COUNT_BUCKETS,
    RECOMMENDATION_POLICY_ID,
    TOP_N,
    RecommendationBucketView,
)
from lottolab.evidence.next_draw_recommendation_evidence import (
    NextDrawRecommendationEvidenceArtifact,
)
from lottolab.interfaces.api.draw_data import ApiErrorResponse
from lottolab.interfaces.api.strategy_catalog import API_PREFIX
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.catalog import StrategyCatalog

NextDrawEvidenceArtifactFactory = Callable[[], NextDrawRecommendationEvidenceArtifact | None]
CausalHistoryFactory = Callable[[LotteryType], tuple[CausalDrawRow, ...]]

NativeTicketCount = Annotated[
    int,
    Query(description=f"One of {NATIVE_TICKET_COUNT_BUCKETS}."),
]

_FROZEN_RESPONSE = ConfigDict(frozen=True)


class RecommendationWindowMetricView(BaseModel):
    model_config = _FROZEN_RESPONSE

    window_kind: str
    eligible_draw_count: int
    window_complete: bool
    observed_rate: float | None
    random_baseline_rate: float | None
    delta_vs_random: float | None


class RecommendationCandidateView(BaseModel):
    model_config = _FROZEN_RESPONSE

    rank: int
    strategy_id: str
    strategy_name: str
    native_ticket_count: int
    windows: list[RecommendationWindowMetricView]
    cross_window_rank_sum: int | None
    highest_historical_prize_label: str | None
    ticket_generation_status: str | None
    tickets: list[list[int]] | None
    ticket_generation_detail: str


class RecommendationExclusionView(BaseModel):
    model_config = _FROZEN_RESPONSE

    strategy_id: str
    reason: str
    detail: str


class NextDrawRecommendationResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    ranking_policy_id: str
    lottery_type: str
    native_ticket_count: int
    availability: str
    total_candidate_count: int
    ranked: list[RecommendationCandidateView]
    excluded: list[RecommendationExclusionView]
    hit_tier_id: str
    evidence_computation_status: str
    evidence_artifact_sha256: str
    evidence_last_causal_draw_id: str


def _window_view(
    windows: tuple, window_kind: str
) -> RecommendationWindowMetricView | None:
    for window in windows:
        if window.window_kind == window_kind:
            return RecommendationWindowMetricView(
                window_kind=window.window_kind,
                eligible_draw_count=window.eligible_draw_count,
                window_complete=window.window_complete,
                observed_rate=None if window.observed_rate is None else float(window.observed_rate),
                random_baseline_rate=(
                    None if window.random_baseline_rate is None else float(window.random_baseline_rate)
                ),
                delta_vs_random=(
                    None if window.delta_vs_random is None else float(window.delta_vs_random)
                ),
            )
    return None


def _bucket_view_to_response(
    view: RecommendationBucketView,
    *,
    lottery_type: LotteryType,
    hit_tier_id: str,
    evidence: NextDrawRecommendationEvidenceArtifact,
    tickets_by_strategy_id: dict[str, GeneratedTicketSet],
) -> NextDrawRecommendationResponse:
    return NextDrawRecommendationResponse(
        ranking_policy_id=RECOMMENDATION_POLICY_ID,
        lottery_type=lottery_type.value,
        native_ticket_count=view.native_ticket_count,
        availability=view.availability.value,
        total_candidate_count=view.total_candidate_count,
        ranked=[
            _candidate_view(candidate, tickets_by_strategy_id.get(candidate.strategy_id))
            for candidate in view.ranked
        ],
        excluded=[
            RecommendationExclusionView(
                strategy_id=exclusion.strategy_id,
                reason=exclusion.reason.value,
                detail=exclusion.detail,
            )
            for exclusion in view.excluded
        ],
        hit_tier_id=hit_tier_id,
        evidence_computation_status=evidence.computation_status.value,
        evidence_artifact_sha256=evidence.artifact_sha256,
        evidence_last_causal_draw_id=evidence.last_causal_draw_id,
    )


def _candidate_view(
    candidate: object, ticket_set: GeneratedTicketSet | None
) -> RecommendationCandidateView:
    return RecommendationCandidateView(
        rank=candidate.rank,  # type: ignore[attr-defined]
        strategy_id=candidate.strategy_id,  # type: ignore[attr-defined]
        strategy_name=candidate.strategy_name,  # type: ignore[attr-defined]
        native_ticket_count=candidate.native_ticket_count,  # type: ignore[attr-defined]
        windows=[
            window_view
            for window_kind in ("WINDOW_50", "WINDOW_300", "WINDOW_750")
            if (window_view := _window_view(candidate.windows, window_kind))  # type: ignore[attr-defined]
            is not None
        ],
        cross_window_rank_sum=candidate.cross_window_rank_sum,  # type: ignore[attr-defined]
        highest_historical_prize_label=candidate.highest_historical_prize_label,  # type: ignore[attr-defined]
        ticket_generation_status=None if ticket_set is None else ticket_set.status.value,
        tickets=(
            None
            if ticket_set is None or ticket_set.status is not TicketGenerationStatus.OK
            else [list(ticket) for ticket in ticket_set.tickets]
        ),
        ticket_generation_detail="" if ticket_set is None else ticket_set.detail,
    )


def create_next_draw_recommendation_router(
    catalog: StrategyCatalog,
    evidence_factory: NextDrawEvidenceArtifactFactory,
    causal_history_factory: CausalHistoryFactory,
) -> APIRouter:
    router = APIRouter(prefix=API_PREFIX, tags=["next-draw-recommendation"])
    ticket_use_case = GenerateNextDrawTopTickets(catalog=catalog)

    @router.get(
        "/next-draw-recommendation",
        response_model=NextDrawRecommendationResponse,
        responses={503: {"model": ApiErrorResponse}, 422: {"model": ApiErrorResponse}},
    )
    def get_next_draw_recommendation(
        native_ticket_count: NativeTicketCount,
    ) -> NextDrawRecommendationResponse | JSONResponse:
        if native_ticket_count not in NATIVE_TICKET_COUNT_BUCKETS:
            return _json_response(
                422,
                ApiErrorResponse(
                    error_code="NEXT_DRAW_RECOMMENDATION_INVALID_TICKET_COUNT",
                    message=f"native_ticket_count must be one of {NATIVE_TICKET_COUNT_BUCKETS}.",
                ),
            )
        evidence = evidence_factory()
        if evidence is None:
            return _json_response(
                503,
                ApiErrorResponse(
                    error_code="NEXT_DRAW_RECOMMENDATION_EVIDENCE_UNAVAILABLE",
                    message="No Next-Draw Recommendation evidence artifact is configured.",
                ),
            )
        use_case = BuildNextDrawRecommendationBucket(catalog=catalog, evidence=evidence)
        view = use_case.execute(
            lottery_type=LotteryType.BIG_LOTTO, native_ticket_count=native_ticket_count
        )
        top_strategy_ids = tuple(candidate.strategy_id for candidate in view.ranked[:TOP_N])
        tickets_by_strategy_id: dict[str, GeneratedTicketSet] = {}
        if top_strategy_ids:
            causal_history = causal_history_factory(LotteryType.BIG_LOTTO)
            ticket_sets = ticket_use_case.execute(
                top_strategy_ids,
                lottery_type=LotteryType.BIG_LOTTO,
                causal_history=causal_history,
            )
            tickets_by_strategy_id = {
                ticket_set.strategy_id: ticket_set for ticket_set in ticket_sets
            }
        return _bucket_view_to_response(
            view,
            tickets_by_strategy_id=tickets_by_strategy_id,
            lottery_type=LotteryType.BIG_LOTTO,
            hit_tier_id=evidence.hit_tier_id,
            evidence=evidence,
        )

    return router


def _json_response(status_code: int, model: BaseModel) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=model.model_dump(mode="json"))


__all__ = [
    "NextDrawEvidenceArtifactFactory",
    "NextDrawRecommendationResponse",
    "RecommendationCandidateView",
    "RecommendationExclusionView",
    "RecommendationWindowMetricView",
    "create_next_draw_recommendation_router",
]
