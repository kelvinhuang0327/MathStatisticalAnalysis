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

Every response is explicitly bound as a PREVIEW: ``recommendation_status``
is ``PREVIEW`` and ``target_binding`` is ``UNBOUND_AS_OF_NOW``. This route
deliberately exposes no ``target_draw_id``: the tickets are generated from
current causal history and are not sealed against any future draw.
``evidence_last_causal_draw_id`` is evidence provenance only -- it names the
last draw the evidence saw, never a target these tickets are bound to.

Both the evidence-artifact factory and the causal-history factory are
called at most once per request and never at app construction or
OpenAPI-generation time.
"""

# pyright: reportUnusedFunction=false
# (route handlers are registered by FastAPI decorators, not called by name)

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from lottolab.application.use_cases.build_next_draw_recommendation import (
    BuildNextDrawRecommendationBucket,
)
from lottolab.application.use_cases.generate_next_draw_top_tickets import (
    GeneratedTicketSet,
    GenerateNextDrawTopTickets,
    TicketGenerationStatus,
)
from lottolab.application.use_cases.get_next_draw_recommendation_lifecycle import (
    GetNextDrawRecommendationLifecycle,
    NextDrawRecommendationLifecycleView,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.next_draw_recommendation import (
    NATIVE_TICKET_COUNT_BUCKETS,
    RECOMMENDATION_POLICY_ID,
    TOP_N,
    RecommendationBucketView,
)
from lottolab.domain.next_draw_recommendation_seal import (
    NextDrawRecommendationLifecycleState,
    NextDrawRecommendationSeal,
    SealedRecommendationBucket,
    SealedStrategyTickets,
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
NextDrawRecommendationLifecycleReaderFactory = Callable[
    [], GetNextDrawRecommendationLifecycle | None
]

NativeTicketCount = Annotated[
    int,
    Query(description=f"One of {NATIVE_TICKET_COUNT_BUCKETS}."),
]

_FROZEN_RESPONSE = ConfigDict(frozen=True)

# This stage claims no canonical evidence, no bound target, and no sealed
# pre-draw prediction; both values are frozen literals, never derived state.
RECOMMENDATION_STATUS_PREVIEW = "PREVIEW"
TARGET_BINDING_UNBOUND = "UNBOUND_AS_OF_NOW"


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
    recommendation_status: str
    target_binding: str
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


class SealedTicketSetView(BaseModel):
    model_config = _FROZEN_RESPONSE

    rank: int
    strategy_id: str
    strategy_name: str
    status: str
    tickets: list[list[int]]
    detail: str


class SealedBucketView(BaseModel):
    model_config = _FROZEN_RESPONSE

    native_ticket_count: int
    availability: str
    total_candidate_count: int
    ranked_strategy_ids: list[str]
    sealed_tickets: list[SealedTicketSetView]


class NextDrawRecommendationLifecycleResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    lifecycle_state: str
    lottery_type: str
    ranking_policy_id: str
    target_draw_number: str | None
    target_draw_date: str | None
    target_scheduled_at: str | None
    sealed_at: str | None
    target_registration_digest: str | None
    evidence_artifact_sha256: str | None
    sealed_buckets: list[SealedBucketView]


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
        recommendation_status=RECOMMENDATION_STATUS_PREVIEW,
        target_binding=TARGET_BINDING_UNBOUND,
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
        ticket_generation_status=None if ticket_set is None else ticket_set.status.value,
        tickets=(
            None
            if ticket_set is None or ticket_set.status is not TicketGenerationStatus.OK
            else [list(ticket) for ticket in ticket_set.tickets]
        ),
        ticket_generation_detail="" if ticket_set is None else ticket_set.detail,
    )


def _sealed_ticket_set_view(ticket: SealedStrategyTickets) -> SealedTicketSetView:
    return SealedTicketSetView(
        rank=ticket.rank,
        strategy_id=ticket.strategy_id,
        strategy_name=ticket.strategy_name,
        status=ticket.status.value,
        tickets=[list(ticket_numbers) for ticket_numbers in ticket.tickets],
        detail=ticket.detail,
    )


def _sealed_bucket_view(bucket: SealedRecommendationBucket) -> SealedBucketView:
    return SealedBucketView(
        native_ticket_count=bucket.native_ticket_count,
        availability=bucket.availability,
        total_candidate_count=bucket.total_candidate_count,
        ranked_strategy_ids=list(bucket.ranked_strategy_ids),
        sealed_tickets=[_sealed_ticket_set_view(ticket) for ticket in bucket.sealed_tickets],
    )


def _lifecycle_view_to_response(
    view: NextDrawRecommendationLifecycleView,
    *,
    lottery_type: LotteryType,
) -> NextDrawRecommendationLifecycleResponse:
    seal: NextDrawRecommendationSeal | None = view.seal
    is_sealed = seal is not None and view.state in {
        NextDrawRecommendationLifecycleState.PREDICTIONS_SEALED,
        NextDrawRecommendationLifecycleState.OUTCOME_AVAILABLE,
    }
    return NextDrawRecommendationLifecycleResponse(
        lifecycle_state=view.state.value,
        lottery_type=lottery_type.value,
        ranking_policy_id=RECOMMENDATION_POLICY_ID,
        target_draw_number=view.target.draw_number if view.target is not None else None,
        target_draw_date=view.target.draw_date.isoformat() if view.target is not None else None,
        target_scheduled_at=(_utc_text(seal.target_scheduled_at) if is_sealed and seal else None),
        sealed_at=(_utc_text(seal.sealed_at) if is_sealed and seal else None),
        target_registration_digest=(
            seal.target_registration_digest if is_sealed and seal else None
        ),
        evidence_artifact_sha256=(seal.evidence_artifact_sha256 if is_sealed and seal else None),
        sealed_buckets=(
            [_sealed_bucket_view(bucket) for bucket in seal.buckets] if is_sealed and seal else []
        ),
    )


def create_next_draw_recommendation_router(
    catalog: StrategyCatalog,
    evidence_factory: NextDrawEvidenceArtifactFactory,
    causal_history_factory: CausalHistoryFactory,
    lifecycle_reader_factory: NextDrawRecommendationLifecycleReaderFactory | None = None,
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

    @router.get(
        "/next-draw-recommendation/lifecycle",
        response_model=NextDrawRecommendationLifecycleResponse,
        responses={503: {"model": ApiErrorResponse}},
    )
    def get_next_draw_recommendation_lifecycle() -> (
        NextDrawRecommendationLifecycleResponse | JSONResponse
    ):
        # Read-only: resolves target/seal/outcome state without registering a
        # target, generating tickets, or writing a seal. See
        # GetNextDrawRecommendationLifecycle's own module docstring.
        lifecycle_reader = lifecycle_reader_factory() if lifecycle_reader_factory else None
        if lifecycle_reader is None:
            return _json_response(
                503,
                ApiErrorResponse(
                    error_code="NEXT_DRAW_RECOMMENDATION_LIFECYCLE_UNAVAILABLE",
                    message="No Next-Draw Recommendation lifecycle reader is configured.",
                ),
            )
        view = lifecycle_reader.execute(LotteryType.BIG_LOTTO)
        return _lifecycle_view_to_response(view, lottery_type=LotteryType.BIG_LOTTO)

    return router


def _json_response(status_code: int, model: BaseModel) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=model.model_dump(mode="json"))


def _utc_text(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


__all__ = [
    "RECOMMENDATION_STATUS_PREVIEW",
    "TARGET_BINDING_UNBOUND",
    "NextDrawEvidenceArtifactFactory",
    "NextDrawRecommendationLifecycleReaderFactory",
    "NextDrawRecommendationLifecycleResponse",
    "NextDrawRecommendationResponse",
    "RecommendationCandidateView",
    "RecommendationExclusionView",
    "RecommendationWindowMetricView",
    "SealedBucketView",
    "SealedTicketSetView",
    "create_next_draw_recommendation_router",
]
