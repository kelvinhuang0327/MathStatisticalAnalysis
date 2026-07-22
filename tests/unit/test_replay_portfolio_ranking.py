"""Domain contract coverage for Replay strategy-portfolio ranking."""

from __future__ import annotations

import dataclasses

import pytest

from lottolab.domain.replay_portfolio_ranking import (
    MAX_TOP_K,
    MIN_TOP_K,
    PortfolioGroupStatus,
    PortfolioRankingGroup,
    PortfolioRankingResult,
    RankedPortfolioCandidate,
    build_ranked_portfolio_candidate,
    candidate_canonical_dict,
    portfolio_sort_key,
    recompute_candidate_sha256,
)


def _candidate(
    *,
    rank: int = 1,
    strategy_positions: tuple[int, ...] = (0,),
    first_prize_count: int = 0,
    second_prize_count: int = 0,
    third_prize_count: int = 0,
    fourth_prize_count: int = 0,
    fifth_prize_count: int = 0,
    sixth_prize_count: int = 0,
    seventh_prize_count: int = 0,
    general_prize_count: int = 0,
    no_prize_count: int = 3,
    history_closed_count: int = 0,
    prediction_closed_count: int = 0,
    target_outcome_not_found_count: int = 0,
    target_identity_mismatch_count: int = 0,
    target_count: int = 3,
    strategy_versions: tuple[str | None, ...] | None = None,
) -> RankedPortfolioCandidate:
    ticket_count = len(strategy_positions)
    tier_total = (
        first_prize_count
        + second_prize_count
        + third_prize_count
        + fourth_prize_count
        + fifth_prize_count
        + sixth_prize_count
        + seventh_prize_count
        + general_prize_count
    )
    scored_count = tier_total + no_prize_count
    closed_total = (
        history_closed_count
        + prediction_closed_count
        + target_outcome_not_found_count
        + target_identity_mismatch_count
    )
    total_ticket_count = target_count * ticket_count
    assert total_ticket_count == scored_count + closed_total
    return build_ranked_portfolio_candidate(
        rank=rank,
        ticket_count=ticket_count,
        strategy_positions=strategy_positions,
        strategy_ids=tuple(f"strategy_{position}" for position in strategy_positions),
        strategy_versions=strategy_versions or tuple("1.0.0" for _ in strategy_positions),
        target_count=target_count,
        total_ticket_count=total_ticket_count,
        scored_count=scored_count,
        history_closed_count=history_closed_count,
        prediction_closed_count=prediction_closed_count,
        target_outcome_not_found_count=target_outcome_not_found_count,
        target_identity_mismatch_count=target_identity_mismatch_count,
        first_prize_count=first_prize_count,
        second_prize_count=second_prize_count,
        third_prize_count=third_prize_count,
        fourth_prize_count=fourth_prize_count,
        fifth_prize_count=fifth_prize_count,
        sixth_prize_count=sixth_prize_count,
        seventh_prize_count=seventh_prize_count,
        general_prize_count=general_prize_count,
        no_prize_count=no_prize_count,
        winning_ticket_count=tier_total,
    )


def test_candidate_hash_is_stable_and_recomputable() -> None:
    candidate = _candidate(first_prize_count=1, no_prize_count=2)
    assert len(candidate.candidate_sha256) == 64
    assert recompute_candidate_sha256(candidate) == candidate.candidate_sha256
    again = _candidate(first_prize_count=1, no_prize_count=2)
    assert again.candidate_sha256 == candidate.candidate_sha256


def test_candidate_hash_changes_when_content_changes() -> None:
    baseline = _candidate(first_prize_count=1, no_prize_count=2)
    mutated = _candidate(first_prize_count=2, no_prize_count=1)
    assert baseline.candidate_sha256 != mutated.candidate_sha256


def test_candidate_tampering_is_detected() -> None:
    candidate = _candidate(first_prize_count=1, no_prize_count=2)
    with pytest.raises(ValueError, match="candidate_sha256 does not match"):
        dataclasses.replace(candidate, candidate_sha256="0" * 64)


def test_candidate_omits_null_strategy_version_from_canonical_dict() -> None:
    candidate = _candidate(strategy_versions=(None,))
    payload = candidate_canonical_dict(candidate)
    member = payload["members"][0]
    assert "strategy_version" not in member
    assert None not in payload.values()


def test_candidate_rejects_inconsistent_counters() -> None:
    with pytest.raises(ValueError, match="strategy_positions must be strictly ascending"):
        build_ranked_portfolio_candidate(
            rank=1,
            ticket_count=2,
            strategy_positions=(1, 0),
            strategy_ids=("a", "b"),
            strategy_versions=(None, None),
            target_count=1,
            total_ticket_count=2,
            scored_count=2,
            history_closed_count=0,
            prediction_closed_count=0,
            target_outcome_not_found_count=0,
            target_identity_mismatch_count=0,
            first_prize_count=0,
            second_prize_count=0,
            third_prize_count=0,
            fourth_prize_count=0,
            fifth_prize_count=0,
            sixth_prize_count=0,
            seventh_prize_count=0,
            general_prize_count=0,
            no_prize_count=2,
            winning_ticket_count=0,
        )


def test_sort_key_orders_tiers_before_scored_and_positions_break_final_ties() -> None:
    better = portfolio_sort_key(
        first_prize_count=1,
        second_prize_count=0,
        third_prize_count=0,
        fourth_prize_count=0,
        fifth_prize_count=0,
        sixth_prize_count=0,
        seventh_prize_count=0,
        general_prize_count=0,
        scored_count=1,
        target_identity_mismatch_count=0,
        target_outcome_not_found_count=0,
        history_closed_count=0,
        prediction_closed_count=0,
        strategy_positions=(5,),
    )
    worse = portfolio_sort_key(
        first_prize_count=0,
        second_prize_count=99,
        third_prize_count=99,
        fourth_prize_count=99,
        fifth_prize_count=99,
        sixth_prize_count=99,
        seventh_prize_count=99,
        general_prize_count=99,
        scored_count=99,
        target_identity_mismatch_count=0,
        target_outcome_not_found_count=0,
        history_closed_count=0,
        prediction_closed_count=0,
        strategy_positions=(0,),
    )
    assert better < worse

    tie_low_position = portfolio_sort_key(
        first_prize_count=1,
        second_prize_count=0,
        third_prize_count=0,
        fourth_prize_count=0,
        fifth_prize_count=0,
        sixth_prize_count=0,
        seventh_prize_count=0,
        general_prize_count=0,
        scored_count=1,
        target_identity_mismatch_count=0,
        target_outcome_not_found_count=0,
        history_closed_count=0,
        prediction_closed_count=0,
        strategy_positions=(0, 1),
    )
    tie_high_position = portfolio_sort_key(
        first_prize_count=1,
        second_prize_count=0,
        third_prize_count=0,
        fourth_prize_count=0,
        fifth_prize_count=0,
        sixth_prize_count=0,
        seventh_prize_count=0,
        general_prize_count=0,
        scored_count=1,
        target_identity_mismatch_count=0,
        target_outcome_not_found_count=0,
        history_closed_count=0,
        prediction_closed_count=0,
        strategy_positions=(0, 2),
    )
    assert tie_low_position < tie_high_position


def test_group_requires_contiguous_ranks_and_policy_sorted_order() -> None:
    first = _candidate(rank=1, strategy_positions=(0,), first_prize_count=1, no_prize_count=2)
    second = _candidate(rank=2, strategy_positions=(1,), no_prize_count=3)
    PortfolioRankingGroup(
        ticket_count=1,
        status=PortfolioGroupStatus.RANKED,
        total_candidate_count=2,
        candidates=(first, second),
    )
    with pytest.raises(ValueError, match="contiguous starting at 1"):
        PortfolioRankingGroup(
            ticket_count=1,
            status=PortfolioGroupStatus.RANKED,
            total_candidate_count=2,
            candidates=(
                first,
                _candidate(rank=3, strategy_positions=(1,), no_prize_count=3),
            ),
        )
    with pytest.raises(ValueError, match="sorted per the frozen ranking policy"):
        PortfolioRankingGroup(
            ticket_count=1,
            status=PortfolioGroupStatus.RANKED,
            total_candidate_count=2,
            candidates=(
                _candidate(rank=1, strategy_positions=(1,), no_prize_count=3),
                _candidate(
                    rank=2, strategy_positions=(0,), first_prize_count=1, no_prize_count=2
                ),
            ),
        )


def test_insufficient_strategies_group_must_be_empty() -> None:
    PortfolioRankingGroup(
        ticket_count=5,
        status=PortfolioGroupStatus.INSUFFICIENT_STRATEGIES,
        total_candidate_count=0,
        candidates=(),
    )
    with pytest.raises(ValueError, match="must carry zero candidates"):
        PortfolioRankingGroup(
            ticket_count=5,
            status=PortfolioGroupStatus.INSUFFICIENT_STRATEGIES,
            total_candidate_count=1,
            candidates=(
                _candidate(
                    rank=1, strategy_positions=(0, 1, 2, 3, 4), target_count=1, no_prize_count=5
                ),
            ),
        )


def test_result_requires_exactly_five_groups_in_order() -> None:
    groups = tuple(
        PortfolioRankingGroup(
            ticket_count=n,
            status=PortfolioGroupStatus.INSUFFICIENT_STRATEGIES,
            total_candidate_count=0,
            candidates=(),
        )
        for n in range(1, 6)
    )
    PortfolioRankingResult(strategy_count=0, target_count=3, top_k=10, groups=groups)

    with pytest.raises(ValueError, match="exactly five groups"):
        PortfolioRankingResult(strategy_count=0, target_count=3, top_k=10, groups=groups[:4])


def test_result_rejects_top_k_outside_bounds() -> None:
    groups = tuple(
        PortfolioRankingGroup(
            ticket_count=n,
            status=PortfolioGroupStatus.INSUFFICIENT_STRATEGIES,
            total_candidate_count=0,
            candidates=(),
        )
        for n in range(1, 6)
    )
    with pytest.raises(ValueError, match="top_k must fall within"):
        PortfolioRankingResult(strategy_count=0, target_count=3, top_k=MIN_TOP_K - 1, groups=groups)
    with pytest.raises(ValueError, match="top_k must fall within"):
        PortfolioRankingResult(strategy_count=0, target_count=3, top_k=MAX_TOP_K + 1, groups=groups)
