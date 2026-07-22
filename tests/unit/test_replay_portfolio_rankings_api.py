"""API contract coverage for the read-only optimal-replay-portfolio-ranking endpoint."""

# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
# (starlette TestClient is partially untyped under the httpx v1 compatibility shim)

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Never, cast

from fastapi.testclient import TestClient

from lottolab.application.use_cases.score_replay_artifact import ScoreReplayArtifact
from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_predictions import ReplayTarget
from lottolab.domain.replay_scoring import (
    ReplayTargetOutcome,
    ReplayTargetOutcomeReadReason,
    ReplayTargetOutcomeReadResult,
)
from lottolab.evidence.replay_artifact import (
    build_replay_artifact,
    build_replay_prediction_snapshot,
)
from lottolab.evidence.replay_scoring_artifact import (
    ReplayScoringArtifact,
    build_replay_scoring_artifact,
)
from lottolab.interfaces.api.app import create_app

_WINNING_MAIN = (1, 2, 3, 4, 5, 6)
_WINNING_SPECIAL = 7
_LOSING = (11, 12, 13, 14, 15, 16)


class _Reader:
    def __init__(self, outcomes: dict[str, ReplayTargetOutcome]) -> None:
        self.outcomes = outcomes

    def load_target_outcome(self, lottery_type: LotteryType, target_draw_number: str):
        assert lottery_type is LotteryType.BIG_LOTTO
        outcome = self.outcomes.get(target_draw_number)
        if outcome is None:
            return ReplayTargetOutcomeReadResult.not_found(
                ReplayTargetOutcomeReadReason.TARGET_OUTCOME_NOT_FOUND
            )
        return ReplayTargetOutcomeReadResult.found(outcome)


def _fixture_scoring_artifact() -> ReplayScoringArtifact:
    targets = tuple(
        ReplayTarget(str(500 + index), date(2026, 5, 1) + timedelta(days=index))
        for index in range(2)
    )
    strategy_predictions = {"a": (_WINNING_MAIN, _LOSING), "b": (_LOSING, _LOSING)}
    strategy_ids = tuple(strategy_predictions)
    snapshots = tuple(
        build_replay_prediction_snapshot(
            dataset_id="dataset",
            dataset_version="1",
            lottery_type=LotteryType.BIG_LOTTO,
            target=target,
            strategy_id=strategy_id,
            strategy_identity=(strategy_id, f"{strategy_id} name", "1.0.0"),
            history_status="OK",
            history_reason_code=None,
            causal_history=(),
            prediction_status="OK",
            prediction_reason_code=None,
            predicted_main_numbers=strategy_predictions[strategy_id][index],
        )
        for index, target in enumerate(targets)
        for strategy_id in strategy_ids
    )
    source = build_replay_artifact(
        dataset_id="dataset",
        dataset_version="1",
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_ids=strategy_ids,
        targets=targets,
        snapshots=snapshots,
    )
    outcomes = {
        target.draw_number: ReplayTargetOutcome.create(
            lottery_type=LotteryType.BIG_LOTTO,
            target_draw_number=target.draw_number,
            target_draw_date=target.draw_date,
            winning_main_numbers=_WINNING_MAIN,
            winning_special_number=_WINNING_SPECIAL,
        )
        for target in targets
    }
    scored = ScoreReplayArtifact(_Reader(outcomes)).execute(source)
    return build_replay_scoring_artifact(
        source_artifact=source,
        scored_predictions=scored.scored_predictions,
        strategy_aggregates=scored.strategy_aggregates,
        overall_aggregate=scored.overall_aggregate,
    )


def test_returns_five_groups_with_the_expected_shape() -> None:
    client = TestClient(
        create_app(scoring_artifact_provider=_fixture_scoring_artifact)
    )
    response = client.get("/api/v1/replay-rankings/optimal")
    assert response.status_code == 200
    payload = cast(dict[str, Any], response.json())
    assert payload["ranking_policy_id"] == "BIG_LOTTO_TIER_LEXICOGRAPHIC_COUNTS_V1"
    assert payload["strategy_count"] == 2
    assert payload["target_count"] == 2
    assert payload["top_k"] == 10
    assert [group["ticket_count"] for group in payload["groups"]] == [1, 2, 3, 4, 5]
    assert payload["groups"][0]["candidates"][0]["members"][0]["strategy_id"] == "a"
    assert payload["groups"][2]["status"] == "INSUFFICIENT_STRATEGIES"


def test_honors_the_requested_top_k() -> None:
    client = TestClient(
        create_app(scoring_artifact_provider=_fixture_scoring_artifact)
    )
    response = client.get("/api/v1/replay-rankings/optimal", params={"top_k": 1})
    assert response.status_code == 200
    payload = cast(dict[str, Any], response.json())
    assert payload["top_k"] == 1
    assert len(payload["groups"][1]["candidates"]) == 1


def test_rejects_top_k_outside_the_allowed_bounds() -> None:
    client = TestClient(
        create_app(scoring_artifact_provider=_fixture_scoring_artifact)
    )
    for value in (0, 51):
        response = client.get("/api/v1/replay-rankings/optimal", params={"top_k": value})
        assert response.status_code == 422


def test_default_app_has_no_provider_and_returns_sanitized_503() -> None:
    client = TestClient(create_app())
    response = client.get("/api/v1/replay-rankings/optimal")
    assert response.status_code == 503
    assert response.json() == {
        "error_code": "REPLAY_RANKING_NOT_CONFIGURED",
        "message": "Replay portfolio ranking is not configured.",
    }


def test_provider_exception_returns_sanitized_unavailable_503() -> None:
    def _failing_provider() -> Never:
        raise RuntimeError("boom")

    client = TestClient(create_app(scoring_artifact_provider=_failing_provider))
    response = client.get("/api/v1/replay-rankings/optimal")
    assert response.status_code == 503
    assert response.json() == {
        "error_code": "REPLAY_RANKING_UNAVAILABLE",
        "message": "Replay portfolio ranking is unavailable.",
    }


def test_search_space_overflow_returns_sanitized_422() -> None:
    targets = (ReplayTarget("600", date(2026, 6, 1)),)
    strategy_count = 60
    strategy_predictions = {f"s{i}": (_LOSING,) for i in range(strategy_count)}
    strategy_ids = tuple(strategy_predictions)
    snapshots = tuple(
        build_replay_prediction_snapshot(
            dataset_id="dataset",
            dataset_version="1",
            lottery_type=LotteryType.BIG_LOTTO,
            target=targets[0],
            strategy_id=strategy_id,
            strategy_identity=(strategy_id, f"{strategy_id} name", "1.0.0"),
            history_status="OK",
            history_reason_code=None,
            causal_history=(),
            prediction_status="OK",
            prediction_reason_code=None,
            predicted_main_numbers=_LOSING,
        )
        for strategy_id in strategy_ids
    )
    source = build_replay_artifact(
        dataset_id="dataset",
        dataset_version="1",
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_ids=strategy_ids,
        targets=targets,
        snapshots=snapshots,
    )
    outcome = ReplayTargetOutcome.create(
        lottery_type=LotteryType.BIG_LOTTO,
        target_draw_number=targets[0].draw_number,
        target_draw_date=targets[0].draw_date,
        winning_main_numbers=_WINNING_MAIN,
        winning_special_number=_WINNING_SPECIAL,
    )
    scored = ScoreReplayArtifact(_Reader({targets[0].draw_number: outcome})).execute(source)
    artifact = build_replay_scoring_artifact(
        source_artifact=source,
        scored_predictions=scored.scored_predictions,
        strategy_aggregates=scored.strategy_aggregates,
        overall_aggregate=scored.overall_aggregate,
    )

    client = TestClient(create_app(scoring_artifact_provider=lambda: artifact))
    response = client.get("/api/v1/replay-rankings/optimal")
    assert response.status_code == 422
    assert response.json() == {
        "error_code": "REPLAY_RANKING_SEARCH_SPACE_EXCEEDED",
        "message": (
            "The complete N=1..5 portfolio search space exceeds the exhaustive-search cap."
        ),
    }


def test_provider_is_called_exactly_once_per_request() -> None:
    calls: list[int] = []

    def _counting_provider() -> ReplayScoringArtifact:
        calls.append(1)
        return _fixture_scoring_artifact()

    client = TestClient(create_app(scoring_artifact_provider=_counting_provider))
    response = client.get("/api/v1/replay-rankings/optimal")
    assert response.status_code == 200
    assert len(calls) == 1


def test_provider_is_never_called_during_app_construction_or_openapi_generation() -> None:
    calls: list[int] = []

    def _counting_provider() -> ReplayScoringArtifact:
        calls.append(1)
        return _fixture_scoring_artifact()

    app = create_app(scoring_artifact_provider=_counting_provider)
    app.openapi()
    assert calls == []


def test_response_does_not_expose_payout_probability_or_recommendation_fields() -> None:
    client = TestClient(
        create_app(scoring_artifact_provider=_fixture_scoring_artifact)
    )
    response = client.get("/api/v1/replay-rankings/optimal")
    payload = cast(dict[str, Any], response.json())
    forbidden = {"payout", "probability", "ev", "roi", "recommendation", "recommended"}
    for group in payload["groups"]:
        for candidate in group["candidates"]:
            assert not (forbidden & set(candidate))
