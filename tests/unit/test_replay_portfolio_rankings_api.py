"""API contract coverage for persisted optimal Replay-portfolio ranking."""

# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
# (Starlette TestClient is partially untyped under the httpx v1 compatibility shim.)

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Never, cast

import pytest
from fastapi.testclient import TestClient

from lottolab.application.ports import ReplayScoringProjectionReader
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


class _OutcomeReader:
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


class _ArtifactReader:
    def __init__(
        self,
        artifacts: dict[str, ReplayScoringArtifact],
        *,
        failure: str | None = None,
    ) -> None:
        self.artifacts = artifacts
        self.failure = failure
        self.requested_shas: list[str] = []

    def get_replay_scoring_artifact(
        self, scoring_artifact_payload_sha256: str
    ) -> ReplayScoringArtifact | None:
        self.requested_shas.append(scoring_artifact_payload_sha256)
        if self.failure is not None:
            raise RuntimeError(self.failure)
        return self.artifacts.get(scoring_artifact_payload_sha256)

    def get_run(self, scoring_artifact_payload_sha256: str) -> Never:
        raise AssertionError(scoring_artifact_payload_sha256)

    def list_scored_predictions(
        self,
        scoring_artifact_payload_sha256: str,
        *,
        target_draw_number: str | None = None,
        strategy_id: str | None = None,
    ) -> Never:
        raise AssertionError(
            (scoring_artifact_payload_sha256, target_draw_number, strategy_id)
        )

    def list_strategy_aggregates(self, scoring_artifact_payload_sha256: str) -> Never:
        raise AssertionError(scoring_artifact_payload_sha256)

    def get_overall_aggregate(self, scoring_artifact_payload_sha256: str) -> Never:
        raise AssertionError(scoring_artifact_payload_sha256)


class _Factory:
    def __init__(self, reader: _ArtifactReader, *, failure: str | None = None) -> None:
        self.reader = reader
        self.failure = failure
        self.calls = 0

    def __call__(self) -> ReplayScoringProjectionReader:
        self.calls += 1
        if self.failure is not None:
            raise RuntimeError(self.failure)
        return self.reader


def _fixture_scoring_artifact(*, dataset_version: str = "1") -> ReplayScoringArtifact:
    targets = tuple(
        ReplayTarget(str(500 + index), date(2026, 5, 1) + timedelta(days=index))
        for index in range(2)
    )
    strategy_predictions = {"a": (_WINNING_MAIN, _LOSING), "b": (_LOSING, _LOSING)}
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


def _client_for(*artifacts: ReplayScoringArtifact) -> tuple[TestClient, _Factory]:
    reader = _ArtifactReader({artifact.payload_sha256: artifact for artifact in artifacts})
    factory = _Factory(reader)
    return (
        TestClient(create_app(replay_scoring_projection_reader_factory=factory)),
        factory,
    )


def _ranking_path(sha: str) -> str:
    return f"/api/v1/replay-rankings/optimal?scoring_artifact_sha256={sha}"


def test_returns_five_groups_with_existing_ranking_shape_and_provenance() -> None:
    artifact = _fixture_scoring_artifact()
    client, factory = _client_for(artifact)

    response = client.get(_ranking_path(artifact.payload_sha256))

    assert response.status_code == 200
    payload = cast(dict[str, Any], response.json())
    assert payload["ranking_policy_id"] == "BIG_LOTTO_TIER_LEXICOGRAPHIC_COUNTS_V1"
    assert payload["source_scoring_artifact_payload_sha256"] == artifact.payload_sha256
    assert payload["strategy_count"] == 2
    assert payload["target_count"] == 2
    assert payload["top_k"] == 10
    assert [group["ticket_count"] for group in payload["groups"]] == [1, 2, 3, 4, 5]
    assert payload["groups"][0]["candidates"][0]["members"][0]["strategy_id"] == "a"
    assert payload["groups"][2]["status"] == "INSUFFICIENT_STRATEGIES"
    assert factory.calls == 1
    assert factory.reader.requested_shas == [artifact.payload_sha256]


def test_honors_top_k_without_changing_ranking_order() -> None:
    artifact = _fixture_scoring_artifact()
    client, _ = _client_for(artifact)
    full = client.get(_ranking_path(artifact.payload_sha256)).json()

    response = client.get(_ranking_path(artifact.payload_sha256) + "&top_k=1")

    assert response.status_code == 200
    payload = cast(dict[str, Any], response.json())
    assert payload["top_k"] == 1
    assert len(payload["groups"][1]["candidates"]) == 1
    assert payload["groups"][1]["candidates"] == full["groups"][1]["candidates"][:1]


def test_rejects_top_k_outside_the_allowed_bounds_without_loading_storage() -> None:
    artifact = _fixture_scoring_artifact()
    client, factory = _client_for(artifact)

    for value in (0, 51):
        response = client.get(_ranking_path(artifact.payload_sha256) + f"&top_k={value}")
        assert response.status_code == 422

    assert factory.calls == 0


@pytest.mark.parametrize(
    "selector",
    ["A" * 64, "a" * 63, "a" * 65, "g" * 64, f"{'a' * 64}%20"],
)
def test_rejects_malformed_selector_before_reader_factory(selector: str) -> None:
    artifact = _fixture_scoring_artifact()
    client, factory = _client_for(artifact)

    response = client.get(_ranking_path(selector))

    assert response.status_code == 422
    assert response.json()["error_code"] == "REQUEST_VALIDATION_FAILED"
    assert factory.calls == 0


def test_missing_selector_is_422_before_reader_factory() -> None:
    artifact = _fixture_scoring_artifact()
    client, factory = _client_for(artifact)

    response = client.get("/api/v1/replay-rankings/optimal")

    assert response.status_code == 422
    assert factory.calls == 0


def test_default_app_returns_not_configured_503_for_valid_selector() -> None:
    sha = "a" * 64
    response = TestClient(create_app()).get(_ranking_path(sha))

    assert response.status_code == 503
    assert response.json() == {
        "error_code": "REPLAY_RANKING_NOT_CONFIGURED",
        "message": "Replay portfolio ranking is not configured.",
    }


def test_absent_exact_artifact_is_404_without_fallback() -> None:
    artifact = _fixture_scoring_artifact()
    client, factory = _client_for(artifact)
    missing_sha = "0" * 64

    response = client.get(_ranking_path(missing_sha))

    assert response.status_code == 404
    assert response.json()["error_code"] == "REPLAY_RANKING_ARTIFACT_NOT_FOUND"
    assert factory.calls == 1
    assert factory.reader.requested_shas == [missing_sha]


def test_storage_failure_returns_sanitized_unavailable_503() -> None:
    private_detail = "private storage path /tmp/secret.db"
    factory = _Factory(_ArtifactReader({}, failure=private_detail))
    client = TestClient(create_app(replay_scoring_projection_reader_factory=factory))

    response = client.get(_ranking_path("a" * 64))

    assert response.status_code == 503
    assert response.json() == {
        "error_code": "REPLAY_RANKING_UNAVAILABLE",
        "message": "Replay portfolio ranking is unavailable.",
    }
    assert private_detail not in response.text


def test_factory_failure_returns_sanitized_unavailable_503() -> None:
    private_detail = "private database /tmp/secret.db"
    factory = _Factory(_ArtifactReader({}), failure=private_detail)
    client = TestClient(create_app(replay_scoring_projection_reader_factory=factory))

    response = client.get(_ranking_path("a" * 64))

    assert response.status_code == 503
    assert private_detail not in response.text
    assert factory.calls == 1


def test_two_persisted_artifacts_cannot_substitute_for_each_other() -> None:
    first = _fixture_scoring_artifact(dataset_version="1")
    second = _fixture_scoring_artifact(dataset_version="2")
    assert first.payload_sha256 != second.payload_sha256
    client, factory = _client_for(first, second)

    response = client.get(_ranking_path(second.payload_sha256))

    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset_version"] == "2"
    assert payload["source_scoring_artifact_payload_sha256"] == second.payload_sha256
    assert payload["source_scoring_artifact_payload_sha256"] != first.payload_sha256
    assert factory.reader.requested_shas == [second.payload_sha256]


def test_search_space_overflow_returns_sanitized_422() -> None:
    targets = (ReplayTarget("600", date(2026, 6, 1)),)
    strategy_ids = tuple(f"s{i}" for i in range(60))
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
    scored = ScoreReplayArtifact(_OutcomeReader({targets[0].draw_number: outcome})).execute(source)
    artifact = build_replay_scoring_artifact(
        source_artifact=source,
        scored_predictions=scored.scored_predictions,
        strategy_aggregates=scored.strategy_aggregates,
        overall_aggregate=scored.overall_aggregate,
    )
    client, _ = _client_for(artifact)

    response = client.get(_ranking_path(artifact.payload_sha256))

    assert response.status_code == 422
    assert response.json()["error_code"] == "REPLAY_RANKING_SEARCH_SPACE_EXCEEDED"


def test_factory_is_not_called_during_app_construction_or_openapi_generation() -> None:
    artifact = _fixture_scoring_artifact()
    factory = _Factory(_ArtifactReader({artifact.payload_sha256: artifact}))

    app = create_app(replay_scoring_projection_reader_factory=factory)
    app.openapi()

    assert factory.calls == 0


def test_response_does_not_expose_payout_probability_or_recommendation_fields() -> None:
    artifact = _fixture_scoring_artifact()
    client, _ = _client_for(artifact)
    payload = cast(dict[str, Any], client.get(_ranking_path(artifact.payload_sha256)).json())
    forbidden = {"payout", "probability", "ev", "roi", "recommendation", "recommended"}

    for group in payload["groups"]:
        for candidate in group["candidates"]:
            assert not (forbidden & set(candidate))
