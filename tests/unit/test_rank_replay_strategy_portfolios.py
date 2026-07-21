"""Use-case coverage for deterministic post-hoc Replay portfolio ranking."""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from lottolab.application.use_cases.rank_replay_strategy_portfolios import (
    RankReplayStrategyPortfolios,
)
from lottolab.application.use_cases.score_replay_artifact import ScoreReplayArtifact
from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_portfolio_ranking import (
    MAX_EXHAUSTIVE_PORTFOLIO_CANDIDATES,
    PortfolioGroupStatus,
    PortfolioSearchSpaceExceededError,
)
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

_WINNING_MAIN = (1, 2, 3, 4, 5, 6)
_WINNING_SPECIAL = 7
_LOSING = (11, 12, 13, 14, 15, 16)


class _Reader:
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


def _targets(count: int) -> tuple[ReplayTarget, ...]:
    return tuple(
        ReplayTarget(str(300 + index), date(2026, 3, 1) + timedelta(days=index))
        for index in range(count)
    )


def _build_scoring_artifact(
    strategy_predictions: dict[str, tuple[tuple[int, ...], ...]],
    targets: tuple[ReplayTarget, ...],
) -> ReplayScoringArtifact:
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
    result = ScoreReplayArtifact(_Reader(outcomes)).execute(source)
    return build_replay_scoring_artifact(
        source_artifact=source,
        scored_predictions=result.scored_predictions,
        strategy_aggregates=result.strategy_aggregates,
        overall_aggregate=result.overall_aggregate,
    )


def test_always_produces_five_groups_one_through_five() -> None:
    targets = _targets(2)
    artifact = _build_scoring_artifact(
        {"a": (_WINNING_MAIN, _LOSING), "b": (_LOSING, _LOSING)}, targets
    )
    result = RankReplayStrategyPortfolios().execute(artifact, top_k=10)
    assert [group.ticket_count for group in result.groups] == [1, 2, 3, 4, 5]
    assert result.strategy_count == 2
    assert result.target_count == 2


def test_groups_beyond_strategy_count_report_insufficient_strategies() -> None:
    targets = _targets(1)
    artifact = _build_scoring_artifact({"a": (_WINNING_MAIN,), "b": (_LOSING,)}, targets)
    result = RankReplayStrategyPortfolios().execute(artifact, top_k=10)
    assert result.groups[0].status is PortfolioGroupStatus.RANKED
    assert result.groups[1].status is PortfolioGroupStatus.RANKED
    for group in result.groups[2:]:
        assert group.status is PortfolioGroupStatus.INSUFFICIENT_STRATEGIES
        assert group.total_candidate_count == 0
        assert group.candidates == ()


def test_ranks_the_strictly_better_strategy_first() -> None:
    targets = _targets(1)
    artifact = _build_scoring_artifact({"winner": (_WINNING_MAIN,), "loser": (_LOSING,)}, targets)
    result = RankReplayStrategyPortfolios().execute(artifact, top_k=10)
    single_group = result.groups[0]
    assert single_group.total_candidate_count == 2
    assert [candidate.strategy_ids for candidate in single_group.candidates] == [
        ("winner",),
        ("loser",),
    ]
    assert single_group.candidates[0].first_prize_count == 1
    assert single_group.candidates[0].rank == 1
    assert single_group.candidates[1].rank == 2


def test_ties_break_by_ascending_source_strategy_position() -> None:
    targets = _targets(1)
    artifact = _build_scoring_artifact(
        {"a": (_LOSING,), "b": (_LOSING,), "c": (_LOSING,)}, targets
    )
    result = RankReplayStrategyPortfolios().execute(artifact, top_k=10)
    single_group = result.groups[0]
    assert [candidate.strategy_ids for candidate in single_group.candidates] == [
        ("a",),
        ("b",),
        ("c",),
    ]


def test_top_k_truncates_but_total_candidate_count_reports_the_full_space() -> None:
    targets = _targets(1)
    artifact = _build_scoring_artifact(
        {name: (_LOSING,) for name in ("a", "b", "c", "d")}, targets
    )
    result = RankReplayStrategyPortfolios().execute(artifact, top_k=2)
    pair_group = result.groups[1]
    assert pair_group.total_candidate_count == math.comb(4, 2)
    assert len(pair_group.candidates) == 2
    assert [candidate.rank for candidate in pair_group.candidates] == [1, 2]


def test_portfolio_counters_sum_across_member_strategies() -> None:
    targets = _targets(1)
    artifact = _build_scoring_artifact({"a": (_WINNING_MAIN,), "b": (_WINNING_MAIN,)}, targets)
    result = RankReplayStrategyPortfolios().execute(artifact, top_k=10)
    pair_group = result.groups[1]
    combined = pair_group.candidates[0]
    assert combined.first_prize_count == 2
    assert combined.scored_count == 2
    assert combined.total_ticket_count == 2
    assert combined.winning_ticket_count == 2


def test_search_space_overflow_fails_closed_before_enumeration() -> None:
    targets = _targets(1)
    strategy_count = 60  # sum(comb(60, n) for n in 1..5) exceeds the 100_000 cap
    predictions: dict[str, tuple[tuple[int, ...], ...]] = {
        f"s{i}": (_LOSING,) for i in range(strategy_count)
    }
    artifact = _build_scoring_artifact(predictions, targets)
    total_space = sum(math.comb(strategy_count, n) for n in range(1, 6))
    assert total_space > MAX_EXHAUSTIVE_PORTFOLIO_CANDIDATES
    with pytest.raises(PortfolioSearchSpaceExceededError):
        RankReplayStrategyPortfolios().execute(artifact, top_k=10)


def test_repeated_execution_is_byte_identical() -> None:
    targets = _targets(2)
    artifact = _build_scoring_artifact(
        {"a": (_WINNING_MAIN, _LOSING), "b": (_LOSING, _WINNING_MAIN)}, targets
    )
    use_case = RankReplayStrategyPortfolios()
    first = use_case.execute(artifact, top_k=10)
    second = use_case.execute(artifact, top_k=10)
    assert first == second
