"""Focused checks for the frozen four-arm portfolio-geometry OOS replay."""

from __future__ import annotations

import random

import pytest

from lottolab.application.b649_k_dpp_portfolio_selector import (
    HISTORICAL_CAUSAL_REPLAY_V1,
    HISTORY_FINGERPRINT,
    MIN_OVERLAP_METHOD_ID,
    MIN_OVERLAP_METHOD_VERSION,
    CausalSourceIdentity,
    select_deterministic_min_overlap,
    select_kdpp,
    select_seeded_random_k,
)
from lottolab.application.b649_operational_portfolio_selector import (
    StrategyCandidate,
    build_portfolio,
)
from lottolab.research.b649_portfolio_geometry_four_arm_oos import (
    ARMS,
    CANDIDATE_ARMS,
    DIAGNOSTIC_K,
    INCUMBENT_ARM,
    PRIMARY_FAMILY_SIZE,
    PRIMARY_K,
    PRIMARY_METRIC,
    SourceDraw,
    arm_selections,
    arm_verdict,
    build_pool,
    geometry,
    score,
    summarize_pair,
)
from lottolab.strategies.adapters.base import CausalDrawRow

SOURCE = CausalSourceIdentity(
    source_mode=HISTORICAL_CAUSAL_REPLAY_V1,
    target_draw_number="115000088",
    target_draw_date="2026-09-15",
    history_cutoff_draw_number="115000087",
    history_cutoff_date="2026-09-12",
    history_identity_kind=HISTORY_FINGERPRINT,
    history_identity="a" * 64,
)


def discriminating_pool(size: int = 40) -> tuple[StrategyCandidate, ...]:
    """Half a lexicographically clustered block, half spread tickets.

    The clustered block is what the incumbent's lexical tie-break selects
    first, so the arms can actually diverge; a pool where every ticket shares
    the same five numbers makes all four arms identical and tests nothing.
    """

    rng = random.Random(7)
    tickets: list[tuple[int, ...]] = [tuple(sorted({1, 2, 3, 4, 5} | {6 + i})) for i in range(15)]
    while len(tickets) < size:
        ticket = tuple(sorted(rng.sample(range(1, 50), 6)))
        if ticket not in tickets:
            tickets.append(ticket)
    return tuple(StrategyCandidate(f"S{i}", (t,)) for i, t in enumerate(tickets))


def test_frozen_experiment_contract() -> None:
    assert INCUMBENT_ARM == "RAW_MAJORITY"
    assert CANDIDATE_ARMS == ("SEEDED_RANDOM_K", "KDPP", "MIN_OVERLAP")
    assert ARMS == ("RAW_MAJORITY", "SEEDED_RANDOM_K", "KDPP", "MIN_OVERLAP")
    assert PRIMARY_METRIC == "OFFICIAL_ANY_PRIZE"
    assert PRIMARY_K == (10, 20)
    assert DIAGNOSTIC_K == (5,)
    assert PRIMARY_FAMILY_SIZE == 6
    assert (MIN_OVERLAP_METHOD_ID, MIN_OVERLAP_METHOD_VERSION) == (
        "B649_DETERMINISTIC_MIN_OVERLAP",
        "1.0.0",
    )


def test_build_pool_rejects_history_reaching_the_target() -> None:
    """The no-leakage guard: the cutoff must strictly precede the target."""

    history = (CausalDrawRow("115000088", "2026-09-15", (1, 2, 3, 4, 5, 6)),)
    with pytest.raises(ValueError, match="PRE_DRAW_CUTOFF_VIOLATION"):
        build_pool(history, "115000088", "2026-09-15")


def test_build_pool_rejects_unordered_history() -> None:
    history = (
        CausalDrawRow("115000087", "2026-09-12", (1, 2, 3, 4, 5, 6)),
        CausalDrawRow("115000086", "2026-09-09", (7, 8, 9, 10, 11, 12)),
    )
    with pytest.raises(ValueError, match="PRE_DRAW_CUTOFF_VIOLATION"):
        build_pool(history, "115000088", "2026-09-15")


@pytest.mark.parametrize("k", [5, 10, 20])
def test_incumbent_arm_is_the_operational_selector_bucket(k: int) -> None:
    """RAW_MAJORITY equivalence proven by construction, not asserted by name."""

    pool = discriminating_pool()
    selected = arm_selections(pool, SOURCE, k)["RAW_MAJORITY"].tickets
    assert list(selected) == list(build_portfolio(pool, {}, bucket_sizes=(k,))[k])


@pytest.mark.parametrize("k", [5, 10, 20])
def test_all_arms_return_exactly_k_legal_distinct_tickets(k: int) -> None:
    pool = discriminating_pool()
    for arm, selection in arm_selections(pool, SOURCE, k).items():
        assert selection.feasibility_status == "FEASIBLE", arm
        assert len(selection.tickets) == k, arm
        assert len(set(selection.tickets)) == k, arm
        assert geometry(selection.tickets)["all_tickets_legal"] is True, arm
        assert geometry(selection.tickets)["duplicate_ticket_count"] == 0, arm


@pytest.mark.parametrize("k", [10, 20])
def test_min_overlap_is_deterministic(k: int) -> None:
    pool = discriminating_pool()
    first = select_deterministic_min_overlap(pool, source=SOURCE, k=k).tickets
    again = select_deterministic_min_overlap(pool, source=SOURCE, k=k).tickets
    reversed_order = select_deterministic_min_overlap(
        tuple(reversed(pool)), source=SOURCE, k=k
    ).tickets
    assert first == again
    assert first == reversed_order


def test_min_overlap_buckets_are_nested() -> None:
    pool = discriminating_pool()
    ten = set(select_deterministic_min_overlap(pool, source=SOURCE, k=10).tickets)
    twenty = set(select_deterministic_min_overlap(pool, source=SOURCE, k=20).tickets)
    assert ten <= twenty


@pytest.mark.parametrize("k", [10, 20])
def test_min_overlap_actually_reduces_redundancy(k: int) -> None:
    """Arm D must beat the incumbent on the quantity it optimizes."""

    selections = arm_selections(discriminating_pool(), SOURCE, k)
    incumbent = geometry(selections["RAW_MAJORITY"].tickets)
    arm_d = geometry(selections["MIN_OVERLAP"].tickets)
    arm_d_overlap, incumbent_overlap = (
        arm_d["mean_pairwise_overlap"],
        incumbent["mean_pairwise_overlap"],
    )
    arm_d_coverage, incumbent_coverage = (
        arm_d["unique_main_number_coverage"],
        incumbent["unique_main_number_coverage"],
    )
    assert isinstance(arm_d_overlap, float) and isinstance(incumbent_overlap, float)
    assert isinstance(arm_d_coverage, int) and isinstance(incumbent_coverage, int)
    assert arm_d_overlap < incumbent_overlap
    assert arm_d_coverage > incumbent_coverage


@pytest.mark.parametrize("k", [10, 20])
def test_seeded_random_and_kdpp_are_reproducible_under_fixed_source(k: int) -> None:
    pool = discriminating_pool()
    random_first = select_seeded_random_k(pool, source=SOURCE, k=k)
    random_again = select_seeded_random_k(pool, source=SOURCE, k=k)
    kdpp_first = select_kdpp(pool, source=SOURCE, k=k)
    kdpp_again = select_kdpp(pool, source=SOURCE, k=k)
    assert random_first.seed == random_again.seed
    assert random_first.tickets == random_again.tickets
    assert kdpp_first.seed == kdpp_again.seed
    assert kdpp_first.tickets == kdpp_again.tickets
    assert random_first.seed != kdpp_first.seed


def test_arms_are_infeasible_when_the_pool_is_smaller_than_k() -> None:
    pool = discriminating_pool(size=8)
    for arm, selection in arm_selections(pool, SOURCE, 20).items():
        assert selection.feasibility_status == "INFEASIBLE_CANDIDATE_COUNT", arm
        assert selection.tickets == ()


def test_geometry_diagnostics_are_exact() -> None:
    tickets = [(1, 2, 3, 4, 5, 6), (1, 2, 3, 7, 8, 9), (10, 11, 12, 13, 14, 15)]
    result = geometry(tickets)
    # pairs: (0,1)=3, (0,2)=0, (1,2)=0
    assert result["mean_pairwise_overlap"] == pytest.approx(1.0)
    assert result["max_pairwise_overlap"] == 3
    assert result["overlap_distribution"] == [2, 0, 0, 1, 0, 0, 0]
    assert result["unique_main_number_coverage"] == 15
    assert result["duplicate_ticket_count"] == 0
    assert result["all_tickets_legal"] is True


def test_score_matches_the_canonical_outcome_evaluator() -> None:
    outcome = SourceDraw("115000088", "2026-09-15", (1, 2, 3, 4, 5, 6), 7, "h" * 64)
    tickets = [(1, 2, 3, 4, 5, 6), (1, 2, 3, 4, 40, 41), (20, 21, 22, 23, 24, 25)]
    result = score(tickets, outcome, 3)
    assert result["ticket_hits"] == [6, 4, 0]
    assert result["max_hits"] == 6
    assert result["p_max_hits_ge_3"] == 1
    assert result["p_max_hits_ge_4"] == 1
    assert result["official_any_prize"] == 1
    assert int(str(result["winning_ticket_count"])) >= 1


def test_score_rejects_a_wrong_cardinality_portfolio() -> None:
    outcome = SourceDraw("115000088", "2026-09-15", (1, 2, 3, 4, 5, 6), 7, "h" * 64)
    with pytest.raises(ValueError, match="SAME_K_PAIRING_VIOLATION"):
        score([(1, 2, 3, 4, 5, 6)], outcome, 3)


def _row(reference: int, arm: int, same_tickets: bool) -> dict[str, object]:
    base = {
        "official_any_prize": reference,
        "p_max_hits_ge_3": 0,
        "p_max_hits_ge_4": 0,
        "max_hits": reference,
    }
    other = {
        "official_any_prize": arm,
        "p_max_hits_ge_3": 0,
        "p_max_hits_ge_4": 0,
        "max_hits": arm,
    }
    left = ((1, 2, 3, 4, 5, 6),)
    right = left if same_tickets else ((7, 8, 9, 10, 11, 12),)
    return {
        "scores": {"RAW_MAJORITY": base, "MIN_OVERLAP": other},
        "tickets": {"RAW_MAJORITY": left, "MIN_OVERLAP": right},
    }


def test_summarize_pair_counts_paired_deltas_and_changed_rate() -> None:
    rows = [_row(0, 1, False), _row(1, 1, False), _row(1, 0, True), _row(0, 0, True)]
    summary = summarize_pair(rows, "RAW_MAJORITY", "MIN_OVERLAP", family_alpha=0.05 / 6)
    primary = summary["official_any_prize"]
    assert isinstance(primary, dict)
    assert primary["reference_count_or_sum"] == 2
    assert primary["arm_count_or_sum"] == 2
    assert primary["absolute_delta"] == pytest.approx(0.0)
    assert summary["primary_discordant_draw_count"] == 2
    assert summary["primary_positive_discordant"] == 1
    assert summary["primary_negative_discordant"] == 1
    assert summary["ticket_set_changed_draws"] == 2
    assert summary["ticket_set_changed_rate"] == pytest.approx(0.5)


def test_arm_verdict_reports_no_lift_when_the_ticket_set_never_changes() -> None:
    rows = [_row(1, 1, True) for _ in range(40)]
    summary = summarize_pair(rows, "RAW_MAJORITY", "MIN_OVERLAP", family_alpha=0.05 / 6)
    assert arm_verdict(summary, 1.0) == "NO_LIFT"


def test_arm_verdict_requires_the_predeclared_discordance_floor() -> None:
    rows = [_row(0, 1, False)] * 5 + [_row(0, 0, False)] * 35
    summary = summarize_pair(rows, "RAW_MAJORITY", "MIN_OVERLAP", family_alpha=0.05 / 6)
    assert summary["primary_discordant_draw_count"] == 5
    assert arm_verdict(summary, 0.01) == "INSUFFICIENT_EVIDENCE"


def test_arm_verdict_validates_a_real_positive_lift() -> None:
    rows = [_row(0, 1, False)] * 30 + [_row(1, 1, False)] * 40
    summary = summarize_pair(rows, "RAW_MAJORITY", "MIN_OVERLAP", family_alpha=0.05 / 6)
    assert arm_verdict(summary, 0.0001) == "POSITIVE_LIFT_VALIDATED"


def test_arm_verdict_validates_a_real_negative_lift() -> None:
    rows = [_row(1, 0, False)] * 30 + [_row(1, 1, False)] * 40
    summary = summarize_pair(rows, "RAW_MAJORITY", "MIN_OVERLAP", family_alpha=0.05 / 6)
    assert arm_verdict(summary, 0.0001) == "NEGATIVE_LIFT"
