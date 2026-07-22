"""Read-only API for deterministic, post-hoc Replay strategy-portfolio ranking.

Ranks 1-5-strategy portfolios drawn from one already-validated
``ReplayScoringArtifact`` under the frozen
``BIG_LOTTO_TIER_LEXICOGRAPHIC_COUNTS_V1`` descriptive policy. "Optimal" means
rank 1 under that frozen policy only: this is a historical, descriptive
result. It carries no payout, probability, EV, ROI, recommendation, or
future-performance claim, generates no numbers, executes no strategy, and
persists nothing. The injected reader factory and exact artifact read are each
called exactly once per valid request and never at app construction or
OpenAPI-generation time.
"""

# pyright: reportUnusedFunction=false
# (route handlers are registered by FastAPI decorators, not called by name)

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from lottolab.application.ports import ReplayScoringProjectionReaderFactory
from lottolab.application.use_cases.query_replay_scoring_projection import (
    QueryReplayScoringProjection,
    ReplayScoringRunNotFoundError,
)
from lottolab.application.use_cases.rank_replay_strategy_portfolios import (
    RankReplayStrategyPortfolios,
)
from lottolab.domain.replay_portfolio_ranking import (
    DEFAULT_TOP_K,
    MAX_TOP_K,
    MIN_TOP_K,
    PortfolioSearchSpaceExceededError,
)
from lottolab.evidence.replay_portfolio_ranking_artifact import (
    build_replay_portfolio_ranking_artifact,
    portfolio_ranking_artifact_view,
)
from lottolab.interfaces.api.draw_data import ApiErrorResponse, ApiValidationErrorResponse
from lottolab.interfaces.api.strategy_catalog import API_PREFIX

TopK = Annotated[int, Query(ge=MIN_TOP_K, le=MAX_TOP_K)]
ScoringArtifactSha256 = Annotated[
    str,
    Query(
        pattern=r"^[0-9a-f]{64}$",
        description="Exact lowercase SHA-256 of the persisted Replay-scoring artifact.",
    ),
]

_FROZEN_RESPONSE = ConfigDict(frozen=True)


class ReplayPortfolioRankingMemberView(BaseModel):
    model_config = _FROZEN_RESPONSE

    source_position: int
    strategy_id: str
    strategy_version: str | None = None


class ReplayPortfolioRankingCandidateView(BaseModel):
    model_config = _FROZEN_RESPONSE

    rank: int
    ticket_count: int
    members: list[ReplayPortfolioRankingMemberView]
    target_count: int
    total_ticket_count: int
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
    winning_ticket_count: int
    candidate_sha256: str


class ReplayPortfolioRankingGroupView(BaseModel):
    model_config = _FROZEN_RESPONSE

    ticket_count: int
    status: str
    total_candidate_count: int
    candidates: list[ReplayPortfolioRankingCandidateView]


class ReplayPortfolioRankingResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    artifact_schema_version: str
    ranking_policy_id: str
    source_scoring_artifact_payload_sha256: str
    source_replay_artifact_payload_sha256: str
    dataset_id: str
    dataset_version: str
    lottery_type: str
    target_count: int
    strategy_count: int
    top_k: int
    groups: list[ReplayPortfolioRankingGroupView]
    artifact_sha256: str


def create_replay_portfolio_rankings_router(
    reader_factory: ReplayScoringProjectionReaderFactory | None,
) -> APIRouter:
    """Expose the route without invoking the optional factory at construction."""

    router = APIRouter(prefix=API_PREFIX, tags=["replay-rankings"])
    query = QueryReplayScoringProjection(reader_factory) if reader_factory is not None else None
    use_case = RankReplayStrategyPortfolios()

    @router.get(
        "/replay-rankings/optimal",
        response_model=ReplayPortfolioRankingResponse,
        responses={
            404: {"model": ApiErrorResponse},
            422: {"model": ApiErrorResponse | ApiValidationErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="getOptimalReplayPortfolioRankings",
    )
    def get_optimal_replay_portfolio_rankings(
        scoring_artifact_payload_sha256: ScoringArtifactSha256,
        top_k: TopK = DEFAULT_TOP_K,
    ) -> ReplayPortfolioRankingResponse | JSONResponse:
        if query is None:
            return _not_configured_error()
        try:
            artifact = query.get_artifact(scoring_artifact_payload_sha256)
        except ReplayScoringRunNotFoundError:
            return _not_found_error()
        except Exception:
            return _unavailable_error()
        try:
            result = use_case.execute(artifact, top_k=top_k)
        except PortfolioSearchSpaceExceededError:
            return _search_space_exceeded_error()

        ranking_artifact = build_replay_portfolio_ranking_artifact(
            source_scoring_artifact_payload_sha256=artifact.payload_sha256,
            source_replay_artifact_payload_sha256=(
                artifact.source_replay_artifact_payload_sha256
            ),
            dataset_id=artifact.dataset_id,
            dataset_version=artifact.dataset_version,
            lottery_type=artifact.lottery_type,
            result=result,
        )
        view = portfolio_ranking_artifact_view(ranking_artifact)
        return ReplayPortfolioRankingResponse.model_validate(view)

    return router


def _not_configured_error() -> JSONResponse:
    return _json_response(
        503,
        ApiErrorResponse(
            error_code="REPLAY_RANKING_NOT_CONFIGURED",
            message="Replay portfolio ranking is not configured.",
        ),
    )


def _unavailable_error() -> JSONResponse:
    return _json_response(
        503,
        ApiErrorResponse(
            error_code="REPLAY_RANKING_UNAVAILABLE",
            message="Replay portfolio ranking is unavailable.",
        ),
    )


def _not_found_error() -> JSONResponse:
    return _json_response(
        404,
        ApiErrorResponse(
            error_code="REPLAY_RANKING_SOURCE_NOT_FOUND",
            message="Replay portfolio ranking source was not found.",
        ),
    )


def _search_space_exceeded_error() -> JSONResponse:
    return _json_response(
        422,
        ApiErrorResponse(
            error_code="REPLAY_RANKING_SEARCH_SPACE_EXCEEDED",
            message="The complete N=1..5 portfolio search space exceeds the exhaustive-search cap.",
        ),
    )


def _json_response(status_code: int, model: BaseModel) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=model.model_dump(mode="json"))


__all__ = [
    "ReplayPortfolioRankingCandidateView",
    "ReplayPortfolioRankingGroupView",
    "ReplayPortfolioRankingMemberView",
    "ReplayPortfolioRankingResponse",
    "create_replay_portfolio_rankings_router",
]
