"""Canonical serialization and tamper checks for ReplayPortfolioRankingArtifact."""

from __future__ import annotations

import dataclasses
import json
from datetime import date, timedelta
from typing import Any, cast

import pytest

from lottolab.application.use_cases.rank_replay_strategy_portfolios import (
    RankReplayStrategyPortfolios,
)
from lottolab.application.use_cases.score_replay_artifact import ScoreReplayArtifact
from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_portfolio_ranking import RANKING_POLICY_ID
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
from lottolab.evidence.replay_portfolio_ranking_artifact import (
    ReplayPortfolioRankingArtifact,
    ReplayPortfolioRankingArtifactTamperError,
    build_replay_portfolio_ranking_artifact,
    recompute_ranking_artifact_sha256,
    serialize_replay_portfolio_ranking_artifact,
)
from lottolab.evidence.replay_scoring_artifact import build_replay_scoring_artifact

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


def _build_ranking_artifact() -> ReplayPortfolioRankingArtifact:
    targets = tuple(
        ReplayTarget(str(400 + index), date(2026, 4, 1) + timedelta(days=index))
        for index in range(2)
    )
    strategy_predictions = {"a": (_WINNING_MAIN, _LOSING), "b": (_LOSING, _WINNING_MAIN)}
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
    scoring_artifact = build_replay_scoring_artifact(
        source_artifact=source,
        scored_predictions=scored.scored_predictions,
        strategy_aggregates=scored.strategy_aggregates,
        overall_aggregate=scored.overall_aggregate,
    )
    result = RankReplayStrategyPortfolios().execute(scoring_artifact, top_k=10)
    return build_replay_portfolio_ranking_artifact(
        source_scoring_artifact_payload_sha256=scoring_artifact.payload_sha256,
        source_replay_artifact_payload_sha256=scoring_artifact.source_replay_artifact_payload_sha256,
        dataset_id=scoring_artifact.dataset_id,
        dataset_version=scoring_artifact.dataset_version,
        lottery_type=scoring_artifact.lottery_type,
        result=result,
    )


def _parsed(data: bytes) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(data))


def test_artifact_hash_is_stable_and_recomputable() -> None:
    artifact = _build_ranking_artifact()
    assert len(artifact.artifact_sha256) == 64
    assert recompute_ranking_artifact_sha256(artifact) == artifact.artifact_sha256
    assert artifact.ranking_policy_id == RANKING_POLICY_ID


def test_identical_inputs_produce_the_same_artifact_hash() -> None:
    first = _build_ranking_artifact()
    second = _build_ranking_artifact()
    assert first == second
    assert first.artifact_sha256 == second.artifact_sha256


def test_serialization_round_trips_and_is_byte_stable() -> None:
    artifact = _build_ranking_artifact()
    first_bytes = serialize_replay_portfolio_ranking_artifact(artifact)
    second_bytes = serialize_replay_portfolio_ranking_artifact(artifact)
    assert first_bytes == second_bytes
    parsed = _parsed(first_bytes)
    assert parsed["artifact_sha256"] == artifact.artifact_sha256
    assert len(parsed["groups"]) == 5


def test_top_level_tampering_is_detected() -> None:
    artifact = _build_ranking_artifact()
    with pytest.raises(ReplayPortfolioRankingArtifactTamperError):
        dataclasses.replace(artifact, top_k=9)


def test_nested_candidate_tampering_is_detected() -> None:
    """A candidate self-validates its own hash at construction time, so a
    tampered candidate can never even come into existence -- the strongest
    form of tamper-evidence: there is no valid Python object to embed."""
    artifact = _build_ranking_artifact()
    first_ranked_group = next(group for group in artifact.groups if group.candidates)
    with pytest.raises(ValueError, match="candidate_sha256 does not match"):
        dataclasses.replace(first_ranked_group.candidates[0], candidate_sha256="0" * 64)


def test_artifact_contains_no_floats_nulls_timestamps_or_uuids() -> None:
    artifact = _build_ranking_artifact()
    data = serialize_replay_portfolio_ranking_artifact(artifact)
    text = data.decode("utf-8")
    assert "null" not in text
    parsed = _parsed(data)

    def _walk(value: object) -> None:
        if isinstance(value, dict):
            mapping = cast("dict[str, object]", value)
            for item in mapping.values():
                _walk(item)
        elif isinstance(value, list):
            items = cast("list[object]", value)
            for item in items:
                _walk(item)
        else:
            assert not isinstance(value, float)
            assert value is not None

    _walk(parsed)


def test_wrong_policy_id_is_rejected() -> None:
    artifact = _build_ranking_artifact()
    with pytest.raises(ValueError, match="unsupported ranking policy id"):
        dataclasses.replace(artifact, ranking_policy_id="SOME_OTHER_POLICY")


def test_non_big_lotto_lottery_type_is_rejected() -> None:
    artifact = _build_ranking_artifact()
    with pytest.raises(ValueError, match="BIG_LOTTO only"):
        dataclasses.replace(artifact, lottery_type=LotteryType.DAILY_539)
