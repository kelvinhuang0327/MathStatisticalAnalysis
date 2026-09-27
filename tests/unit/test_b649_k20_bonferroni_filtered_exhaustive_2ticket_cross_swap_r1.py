"""Focused correctness tests for the exhaustive K20 cross-swap search."""

from __future__ import annotations

import hashlib
import itertools
from fractions import Fraction
from math import comb
from pathlib import Path

import pytest

from lottolab.research.b649_k20_bonferroni_filtered_exhaustive_2ticket_cross_swap_r1 import (
    EXPECTED_INCUMBENT_FRACTION,
    EXPECTED_INCUMBENT_OUTCOME_COUNT,
    TOTAL_OFFICIAL_OUTCOMES,
    CrossSwapMove,
    Incumbent,
    Portfolio,
    PortfolioDeduplicator,
    U3Components,
    apply_cross_swap,
    event_intersection_count,
    full_u3_components,
    generate_move_groups,
    incremental_u3_components,
    load_pinned_incumbent,
    move_count,
    portfolio_sha256,
    run_cross_swap_sweep,
    select_bound_fixtures,
    should_safe_prune,
    validate_bound_fixtures,
    verify_incumbent_exact,
)
from lottolab.research.b649_official_any_prize_exact import (
    BIG_LOTTO_DRAW_SIZE,
    BIG_LOTTO_POOL_SIZE,
    ExactPortfolioProbability,
    all_main_draw_masks,
    evaluate_portfolio,
)


@pytest.fixture(scope="module")
def incumbent() -> Incumbent:
    repository = Path(__file__).resolve().parents[2]
    return load_pinned_incumbent(repository)


def test_pinned_incumbent_identity_and_expected_exact_fraction(
    incumbent: Incumbent,
) -> None:
    assert len(incumbent.portfolio) == 20
    assert all(len(ticket) == 6 for ticket in incumbent.portfolio)
    assert all(1 <= number <= 49 for ticket in incumbent.portfolio for number in ticket)
    assert len(set(incumbent.portfolio)) == 20
    assert incumbent.exact_fraction == EXPECTED_INCUMBENT_FRACTION
    assert incumbent.outcome_count == EXPECTED_INCUMBENT_OUTCOME_COUNT
    assert incumbent.portfolio_sha256 == portfolio_sha256(incumbent.portfolio)
    assert incumbent.portfolio_sha256 == (
        "242a04c1236f53d74a939f24495868287a4ad63d63b20903fc91d5987b14a9bd"
    )
    assert incumbent.outcome_count == 7_448_829 * 42
    assert TOTAL_OFFICIAL_OUTCOMES == 14_316_764 * 42


def test_move_generator_is_complete_and_legality_accounting_balances(
    incumbent: Incumbent,
) -> None:
    groups = generate_move_groups(incumbent.portfolio)
    assert len(groups) == comb(20, 2)
    observed = sum(len(group) for group in groups)
    independently_counted = sum(
        len(set(first) - set(second)) * len(set(second) - set(first))
        for first, second in itertools.combinations(incumbent.portfolio, 2)
    )
    assert observed == independently_counted == move_count(incumbent.portfolio)

    legal = 0
    illegal = 0
    for group in groups:
        for move in group:
            try:
                candidate = apply_cross_swap(incumbent.portfolio, move)
            except ValueError:
                illegal += 1
                continue
            legal += 1
            assert len(candidate.portfolio) == 20
            assert len(set(candidate.portfolio)) == 20
            assert all(len(ticket) == 6 and len(set(ticket)) == 6 for ticket in candidate.portfolio)
            assert all(1 <= number <= 49 for ticket in candidate.portfolio for number in ticket)
    assert observed == illegal + legal


def test_pair_order_and_ticket_order_do_not_change_move_neighborhood(
    incumbent: Incumbent,
) -> None:
    original = {
        portfolio_sha256(apply_cross_swap(incumbent.portfolio, move).portfolio)
        for group in generate_move_groups(incumbent.portfolio)
        for move in group
        if _is_legal(incumbent.portfolio, move)
    }
    reversed_input = tuple(tuple(reversed(ticket)) for ticket in reversed(incumbent.portfolio))
    reordered = {
        portfolio_sha256(apply_cross_swap(reversed_input, move).portfolio)
        for group in generate_move_groups(reversed_input)
        for move in group
        if _is_legal(reversed_input, move)
    }
    assert reordered == original


def _is_legal(portfolio: Portfolio, move: CrossSwapMove) -> bool:
    try:
        apply_cross_swap(portfolio, move)
    except ValueError:
        return False
    return True


def test_canonical_portfolio_deduplication_ignores_ticket_and_number_order(
    incumbent: Incumbent,
) -> None:
    deduplicator = PortfolioDeduplicator()
    reordered = tuple(tuple(reversed(ticket)) for ticket in reversed(incumbent.portfolio))
    assert deduplicator.add(incumbent.portfolio)
    assert not deduplicator.add(reordered)
    assert deduplicator.hashes == {incumbent.portfolio_sha256}


def test_incremental_s1_s2_s3_and_u3_equal_full_recomputation(
    incumbent: Incumbent,
) -> None:
    origin = incumbent.portfolio
    base = full_u3_components(origin)
    fixtures = select_bound_fixtures(origin)
    assert {"DISJOINT_PAIR", "OVERLAPPING_PAIR"} <= set(fixtures)
    assert {"INCREASED_PAIR_OVERLAP", "DECREASED_PAIR_OVERLAP"} <= set(fixtures)
    assert "CHANGED_TRIPLE_INTERSECTIONS" in fixtures

    for candidate in fixtures.values():
        incremental = incremental_u3_components(
            origin,
            candidate.portfolio,
            base,
            candidate.old_changed_tickets,
            candidate.new_changed_tickets,
        )
        complete = full_u3_components(candidate.portfolio)
        assert incremental.s1 == complete.s1
        assert incremental.s2 == complete.s2
        assert incremental.s3 == complete.s3
        assert incremental.u3 == complete.u3


def test_single_ticket_event_count_matches_exact_arbiter() -> None:
    draws = all_main_draw_masks(BIG_LOTTO_POOL_SIZE, BIG_LOTTO_DRAW_SIZE)
    ticket = (1, 2, 3, 4, 5, 6)
    assert (
        event_intersection_count((ticket,))
        == evaluate_portfolio([ticket], draws=draws).official_any_prize_outcome_count
    )


def test_pair_and_triple_event_intersections_match_exact_inclusion_exclusion() -> None:
    draws = all_main_draw_masks(BIG_LOTTO_POOL_SIZE, BIG_LOTTO_DRAW_SIZE)
    tickets = (
        (1, 2, 3, 4, 5, 6),
        (1, 2, 7, 8, 9, 10),
        (1, 3, 7, 11, 12, 13),
    )
    single_counts = tuple(
        evaluate_portfolio([ticket], draws=draws).official_any_prize_outcome_count
        for ticket in tickets
    )
    pair_unions = {
        pair: evaluate_portfolio(pair, draws=draws).official_any_prize_outcome_count
        for pair in itertools.combinations(tickets, 2)
    }
    pair_intersections = {
        pair: sum(single_counts[index] for index, ticket in enumerate(tickets) if ticket in pair)
        - union_count
        for pair, union_count in pair_unions.items()
    }
    for pair, exact_intersection in pair_intersections.items():
        assert event_intersection_count(pair) == exact_intersection

    triple_union = evaluate_portfolio(tickets, draws=draws).official_any_prize_outcome_count
    exact_triple_intersection = triple_union - sum(single_counts) + sum(pair_intersections.values())
    assert event_intersection_count(tickets) == exact_triple_intersection


def test_u3_dominates_exact_outcomes_on_required_special_sensitive_fixtures(
    incumbent: Incumbent,
) -> None:
    draws = all_main_draw_masks(BIG_LOTTO_POOL_SIZE, BIG_LOTTO_DRAW_SIZE)
    incumbent_exact = verify_incumbent_exact(incumbent, draws=draws)
    hashes = validate_bound_fixtures(
        incumbent.portfolio,
        draws=draws,
        known_incumbent_exact=incumbent_exact,
    )
    assert hashes


def test_safe_pruning_and_exact_scoring_cover_only_their_required_candidates(
    tmp_path: Path,
) -> None:
    origin = (
        (1, 2, 3, 4, 5, 6),
        (7, 8, 9, 10, 11, 12),
        (13, 14, 15, 16, 17, 18),
    )
    total = TOTAL_OFFICIAL_OUTCOMES
    exact_calls: list[str] = []

    def scorer(portfolio: Portfolio) -> ExactPortfolioProbability:
        digest = portfolio_sha256(portfolio)
        exact_calls.append(digest)
        outcome_count = 1_000_000 + int(digest[:6], 16)
        return ExactPortfolioProbability(
            main_draw_count=comb(49, 6),
            special_count=43,
            m3_plus_draw_count=0,
            official_any_prize_outcome_count=outcome_count,
        )

    pruned = run_cross_swap_sweep(
        origin,
        total,
        checkpoint_path=tmp_path / "pruned.json",
        exact_scorer=scorer,
        expected_ticket_count=3,
        checkpoint_every=7,
    )
    assert pruned.complete
    assert pruned.unique_legal_portfolio_count == pruned.bonferroni_pruned_count
    assert pruned.survivor_count == pruned.exact_scored_count == 0
    assert not exact_calls
    assert should_safe_prune(total, total)
    assert not should_safe_prune(total + 1, total)

    scored = run_cross_swap_sweep(
        origin,
        0,
        checkpoint_path=tmp_path / "scored.json",
        exact_scorer=scorer,
        expected_ticket_count=3,
        checkpoint_every=7,
    )
    assert scored.complete
    assert scored.survivor_count == scored.exact_scored_count == len(scored.exact_records)
    assert len(exact_calls) == scored.exact_scored_count
    assert len(exact_calls) == len(set(exact_calls))


def test_checkpoint_resume_has_identical_full_enumeration_digest(tmp_path: Path) -> None:
    origin = (
        (1, 2, 3, 4, 5, 6),
        (7, 8, 9, 10, 11, 12),
        (13, 14, 15, 16, 17, 18),
        (19, 20, 21, 22, 23, 24),
    )

    def scorer(portfolio: Portfolio) -> ExactPortfolioProbability:
        digest = hashlib.sha256(str(portfolio).encode()).hexdigest()
        outcome_count = 50_000_000 + int(digest[:6], 16)
        return ExactPortfolioProbability(
            main_draw_count=comb(49, 6),
            special_count=43,
            m3_plus_draw_count=0,
            official_any_prize_outcome_count=outcome_count,
        )

    uninterrupted = run_cross_swap_sweep(
        origin,
        0,
        checkpoint_path=tmp_path / "whole.json",
        exact_scorer=scorer,
        expected_ticket_count=4,
        checkpoint_every=5,
    )
    partial = run_cross_swap_sweep(
        origin,
        0,
        checkpoint_path=tmp_path / "resumed.json",
        exact_scorer=scorer,
        expected_ticket_count=4,
        checkpoint_every=3,
        max_raw_moves=11,
    )
    assert not partial.complete
    resumed = run_cross_swap_sweep(
        origin,
        0,
        checkpoint_path=tmp_path / "resumed.json",
        exact_scorer=scorer,
        expected_ticket_count=4,
        checkpoint_every=4,
        resume=True,
    )
    assert resumed.complete
    assert resumed.audit_digest == uninterrupted.audit_digest
    assert resumed.raw_move_count == uninterrupted.raw_move_count
    assert resumed.illegal_move_count == uninterrupted.illegal_move_count
    assert resumed.legal_move_count == uninterrupted.legal_move_count
    assert resumed.unique_legal_portfolio_count == uninterrupted.unique_legal_portfolio_count
    assert resumed.bonferroni_pruned_count == uninterrupted.bonferroni_pruned_count
    assert resumed.survivor_count == uninterrupted.survivor_count
    assert resumed.exact_records == uninterrupted.exact_records
    assert resumed.best_portfolio_sha256 == uninterrupted.best_portfolio_sha256


def test_checkpoint_resume_fails_closed_on_task_identity_mismatch(tmp_path: Path) -> None:
    origin = (
        (1, 2, 3, 4, 5, 6),
        (7, 8, 9, 10, 11, 12),
    )
    checkpoint = tmp_path / "checkpoint.json"

    def scorer(_portfolio: Portfolio) -> ExactPortfolioProbability:
        return ExactPortfolioProbability(
            main_draw_count=comb(49, 6),
            special_count=43,
            m3_plus_draw_count=0,
            official_any_prize_outcome_count=1,
        )

    partial = run_cross_swap_sweep(
        origin,
        0,
        checkpoint_path=checkpoint,
        exact_scorer=scorer,
        expected_ticket_count=2,
        task_id="test-task-a",
        max_raw_moves=1,
    )
    assert not partial.complete
    with pytest.raises(ValueError, match="task identity mismatch"):
        run_cross_swap_sweep(
            origin,
            0,
            checkpoint_path=checkpoint,
            exact_scorer=scorer,
            expected_ticket_count=2,
            task_id="test-task-b",
            resume=True,
        )


def test_cross_swap_preserves_ticket_pair_overlap(incumbent: Incumbent) -> None:
    for group in generate_move_groups(incumbent.portfolio):
        for move in group:
            if not _is_legal(incumbent.portfolio, move):
                continue
            candidate = apply_cross_swap(incumbent.portfolio, move)
            before = len(
                set(incumbent.portfolio[move.ticket_a_index])
                & set(incumbent.portfolio[move.ticket_b_index])
            )
            after = len(
                set(candidate.new_changed_tickets[0]) & set(candidate.new_changed_tickets[1])
            )
            assert before == after


def test_u3_component_identity_is_exact_integer_arithmetic() -> None:
    assert U3Components(s1=100, s2=25, s3=4).u3 == 79
    assert isinstance(U3Components(s1=100, s2=25, s3=4).u3, int)
    assert Fraction(EXPECTED_INCUMBENT_OUTCOME_COUNT, TOTAL_OFFICIAL_OUTCOMES) == Fraction(
        EXPECTED_INCUMBENT_FRACTION
    )


def test_safe_prune_uses_the_strict_improvement_boundary() -> None:
    assert should_safe_prune(EXPECTED_INCUMBENT_OUTCOME_COUNT, EXPECTED_INCUMBENT_OUTCOME_COUNT)
    assert not should_safe_prune(
        EXPECTED_INCUMBENT_OUTCOME_COUNT + 1, EXPECTED_INCUMBENT_OUTCOME_COUNT
    )
