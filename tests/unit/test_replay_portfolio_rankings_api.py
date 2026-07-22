"""API contract coverage for persisted Replay portfolio ranking."""

# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
# (starlette TestClient is partially untyped under the httpx v1 compatibility shim)

from __future__ import annotations

from collections import Counter
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
from lottolab.domain.replay_scoring_projection import (
    ReplayOverallAggregateProjection,
    ReplayScoredPredictionProjection,
    ReplayScoringRunProjection,
    ReplayStrategyAggregateProjection,
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
_UNKNOWN_SHA = "f" * 64


class _OutcomeReader:
    def __init__(self, outcomes: dict[str, ReplayTargetOutcome]) -> None:
        self.outcomes = outcomes

    def load_target_outcome(
        self, lottery_type: LotteryType, target_draw_number: str
    ) -> ReplayTargetOutcomeReadResult:
        assert lottery_type is LotteryType.BIG_LOTTO
        outcome = self.outcomes.get(target_draw_number)
        if outcome is None:
            return ReplayTargetOutcomeReadResult.not_found(
                ReplayTargetOutcomeReadReason.TARGET_OUTCOME_NOT_FOUND
            )
        return ReplayTargetOutcomeReadResult.found(outcome)


class _ProjectionReader:
    def __init__(self, artifacts: dict[str, ReplayScoringArtifact]) -> None:
        self.artifacts = artifacts
        self.calls: Counter[str] = Counter()

    def get_replay_scoring_artifact(
        self, scoring_artifact_payload_sha256: str
    ) -> ReplayScoringArtifact | None:
        self.calls[scoring_artifact_payload_sha256] += 1
        return self.artifacts.get(scoring_artifact_payload_sha256)

    def get_run(
        self, scoring_artifact_payload_sha256: str
    ) -> ReplayScoringRunProjection | None:
        return None

    def list_scored_predictions(
        self,
        scoring_artifact_payload_sha256: str,
        *,
        target_draw_number: str | None = None,
        strategy_id: str | None = None,
    ) -> tuple[ReplayScoredPredictionProjection, ...]:
        return ()

    def list_strategy_aggregates(
        self, scoring_artifact_payload_sha256: str
    ) -> tuple[ReplayStrategyAggregateProjection, ...]:
        return ()

    def get_overall_aggregate(
        self, scoring_artifact_payload_sha256: str
    ) -> ReplayOverallAggregateProjection | None:
        return None


class _ProjectionFactory:
    def __init__(
        self, reader: _ProjectionReader, *, fail: bool = False
    ) -> None:
        self.reader = reader
        self.fail = fail
        self.calls = 0

    def __call__(self) -> _ProjectionReader:
        self.calls += 1
        if self.fail:
            raise RuntimeError("private storage path /tmp/secret.db")
        return self.reader


def _fixture_scoring_artifact(
    *, winning_strategy: str = "a", dataset_version: str = "1"
) -> ReplayScoringArtifact:
    targets = tuple(
        ReplayTarget(str(500 + index), date(2026, 5, 1) + timedelta(days=index))
        for index in range(2)
    )
    strategy_predictions = {
        "a": (_WINNING_MAIN if winning_strategy == "a" else _LOSING, _LOSING),
        "b": (_WINNING_MAIN if winning_strategy == "b" else _LOSING, _LOSING),
    }
    strategy_ids = tuple(strategy_predictions)
    snapshots = tuple(
        build_replay_prediction_snapshot(
            dataset_id="dataset",
            dataset_version=dataset_version,
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
        dataset_version=dataset_version,
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
    scored = ScoreReplayArtifact(_OutcomeReader(outcomes)).execute(source)
    return build_replay_scoring_artifact(
        source_artifact=source,
        scored_predictions=scored.scored_predictions,
        strategy_aggregates=scored.strategy_aggregates,
        overall_aggregate=scored.overall_aggregate,
    )


def _client_for(
    *artifacts: ReplayScoringArtifact,
) -> tuple[TestClient, _ProjectionFactory, _ProjectionReader]:
    reader = _ProjectionReader({artifact.payload_sha256: artifact for artifact in artifacts})
    factory = _ProjectionFactory(reader)
    return (
        TestClient(create_app(replay_scoring_projection_reader_factory=factory)),
        factory,
        reader,
    )


def _selector(artifact: ReplayScoringArtifact, *, top_k: int | None = None) -> dict[str, str | int]:
    params: dict[str, str | int] = {
        "scoring_artifact_payload_sha256": artifact.payload_sha256
    }
    if top_k is not None:
        params["top_k"] = top_k
    return params


def test_returns_five_groups_from_the_exact_selected_artifact() -> None:
    artifact = _fixture_scoring_artifact()
    client, _, _ = _client_for(artifact)

    response = client.get("/api/v1/replay-rankings/optimal", params=_selector(artifact))

    assert response.status_code == 200
    payload = cast(dict[str, Any], response.json())
    assert payload["source_scoring_artifact_payload_sha256"] == artifact.payload_sha256
    assert payload["ranking_policy_id"] == "BIG_LOTTO_TIER_LEXICOGRAPHIC_COUNTS_V1"
    assert payload["strategy_count"] == 2
    assert payload["target_count"] == 2
    assert payload["top_k"] == 10
    assert [group["ticket_count"] for group in payload["groups"]] == [1, 2, 3, 4, 5]
    assert payload["groups"][0]["candidates"][0]["members"][0]["strategy_id"] == "a"
    assert payload["groups"][2]["status"] == "INSUFFICIENT_STRATEGIES"


def test_different_exact_shas_cannot_substitute_artifacts() -> None:
    artifact_a = _fixture_scoring_artifact(winning_strategy="a", dataset_version="a")
    artifact_b = _fixture_scoring_artifact(winning_strategy="b", dataset_version="b")
    client, factory, reader = _client_for(artifact_a, artifact_b)

    response_a = client.get("/api/v1/replay-rankings/optimal", params=_selector(artifact_a))
    response_b = client.get("/api/v1/replay-rankings/optimal", params=_selector(artifact_b))

    assert response_a.status_code == response_b.status_code == 200
    assert response_a.json()["groups"][0]["candidates"][0]["members"][0]["strategy_id"] == "a"
    assert response_b.json()["groups"][0]["candidates"][0]["members"][0]["strategy_id"] == "b"
    assert response_a.json()["source_scoring_artifact_payload_sha256"] == artifact_a.payload_sha256
    assert response_b.json()["source_scoring_artifact_payload_sha256"] == artifact_b.payload_sha256
    assert factory.calls == 2
    assert reader.calls == Counter({artifact_a.payload_sha256: 1, artifact_b.payload_sha256: 1})


def test_honors_the_requested_top_k() -> None:
    artifact = _fixture_scoring_artifact()
    client, _, _ = _client_for(artifact)

    response = client.get("/api/v1/replay-rankings/optimal", params=_selector(artifact, top_k=1))

    assert response.status_code == 200
    payload = cast(dict[str, Any], response.json())
    assert payload["top_k"] == 1
    assert len(payload["groups"][1]["candidates"]) == 1


def test_missing_and_invalid_selector_are_rejected_before_factory() -> None:
    artifact = _fixture_scoring_artifact()
    client, factory, reader = _client_for(artifact)

    for params in ({}, {"scoring_artifact_payload_sha256": "A" * 64}):
        response = client.get("/api/v1/replay-rankings/optimal", params=params)
        assert response.status_code == 422
        assert response.json()["error_code"] == "REQUEST_VALIDATION_FAILED"

    assert factory.calls == 0
    assert reader.calls == Counter()


def test_rejects_top_k_outside_the_allowed_bounds_before_factory() -> None:
    artifact = _fixture_scoring_artifact()
    client, factory, _ = _client_for(artifact)

    for value in (0, 51):
        response = client.get(
            "/api/v1/replay-rankings/optimal", params=_selector(artifact, top_k=value)
        )
        assert response.status_code == 422

    assert factory.calls == 0


def test_default_app_with_valid_selector_returns_sanitized_503() -> None:
    response = TestClient(create_app()).get(
        "/api/v1/replay-rankings/optimal",
        params={"scoring_artifact_payload_sha256": _UNKNOWN_SHA},
    )

    assert response.status_code == 503
    assert response.json() == {
        "error_code": "REPLAY_RANKING_NOT_CONFIGURED",
        "message": "Replay portfolio ranking is not configured.",
    }


def test_unknown_exact_selector_returns_sanitized_404_without_fallback() -> None:
    artifact = _fixture_scoring_artifact()
    client, factory, reader = _client_for(artifact)

    response = client.get(
        "/api/v1/replay-rankings/optimal",
        params={"scoring_artifact_payload_sha256": _UNKNOWN_SHA},
    )

    assert response.status_code == 404
    assert response.json() == {
        "error_code": "REPLAY_RANKING_SOURCE_NOT_FOUND",
        "message": "Replay portfolio ranking source was not found.",
    }
    assert factory.calls == 1
    assert reader.calls == Counter({_UNKNOWN_SHA: 1})


def test_factory_exception_returns_sanitized_unavailable_503() -> None:
    factory = _ProjectionFactory(_ProjectionReader({}), fail=True)
    client = TestClient(create_app(replay_scoring_projection_reader_factory=factory))

    response = client.get(
        "/api/v1/replay-rankings/optimal",
        params={"scoring_artifact_payload_sha256": _UNKNOWN_SHA},
    )

    assert response.status_code == 503
    assert response.json() == {
        "error_code": "REPLAY_RANKING_UNAVAILABLE",
        "message": "Replay portfolio ranking is unavailable.",
    }


def test_search_space_overflow_returns_sanitized_422() -> None:
    targets = (ReplayTarget("600", date(2026, 6, 1)),)
    strategy_ids = tuple(f"s{i}" for i in range(60))
    snapshots = tuple(
        build_replay_prediction_snapshot(
            dataset_id="dataset",
            dataset_version="overflow",
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
        dataset_version="overflow",
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
    scored = ScoreReplayArtifact(_OutcomeReader({targets[0].draw_number: outcome})).execute(source)
    artifact = build_replay_scoring_artifact(
        source_artifact=source,
        scored_predictions=scored.scored_predictions,
        strategy_aggregates=scored.strategy_aggregates,
        overall_aggregate=scored.overall_aggregate,
    )
    client, _, _ = _client_for(artifact)

    response = client.get("/api/v1/replay-rankings/optimal", params=_selector(artifact))

    assert response.status_code == 422
    assert response.json() == {
        "error_code": "REPLAY_RANKING_SEARCH_SPACE_EXCEEDED",
        "message": "The complete N=1..5 portfolio search space exceeds the exhaustive-search cap.",
    }


def test_factory_and_artifact_read_are_each_called_once_per_valid_request() -> None:
    artifact = _fixture_scoring_artifact()
    client, factory, reader = _client_for(artifact)

    response = client.get("/api/v1/replay-rankings/optimal", params=_selector(artifact))

    assert response.status_code == 200
    assert factory.calls == 1
    assert reader.calls == Counter({artifact.payload_sha256: 1})


def test_factory_is_never_called_during_app_construction_or_openapi_generation() -> None:
    artifact = _fixture_scoring_artifact()
    reader = _ProjectionReader({artifact.payload_sha256: artifact})
    factory = _ProjectionFactory(reader)

    app = create_app(replay_scoring_projection_reader_factory=factory)
    app.openapi()

    assert factory.calls == 0
    assert reader.calls == Counter()


def test_response_does_not_expose_payout_probability_or_recommendation_fields() -> None:
    artifact = _fixture_scoring_artifact()
    client, _, _ = _client_for(artifact)
    response = client.get("/api/v1/replay-rankings/optimal", params=_selector(artifact))
    payload = cast(dict[str, Any], response.json())
    forbidden = {"payout", "probability", "ev", "roi", "recommendation", "recommended"}
    for group in payload["groups"]:
        for candidate in group["candidates"]:
            assert not (forbidden & set(candidate))
