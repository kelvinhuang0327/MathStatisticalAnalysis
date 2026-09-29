# pyright: reportPrivateUsage=false
"""Focused tests for the exact single-ticket best-response ascent (K-ticket, any K).

Small pools are checked against a brute-force oracle that scores every candidate through
the canonical ``evaluate_portfolio``; the real K10 baseline is checked at full scale
without running any sweep.
"""

from __future__ import annotations

import itertools
import json
import random
from fractions import Fraction
from math import comb
from pathlib import Path

import pytest

from lottolab.application.b649_sealed_geometry_portfolio import (
    SEALED_GEOMETRY_PORTFOLIOS,
    canonical_portfolio_sha256,
)
from lottolab.research import b649_exact_single_ticket_best_response as br
from lottolab.research.b649_official_any_prize_exact import (
    DrawMasks,
    all_main_draw_masks,
    evaluate_portfolio,
)

type Ticket = tuple[int, ...]

_K10_PINNED_COUNT = 176_345_645
_K10_PINNED_SHA = "13b1126d5b26ce44c9aba24670142eeab49f4a4b51aaf3bbabe7a7f1659ac673"
_DRAWS: dict[int, DrawMasks] = {}
_SPACES: dict[int, br.CandidateSpace] = {}


def _draws(pool: int) -> DrawMasks:
    if pool not in _DRAWS:
        _DRAWS[pool] = all_main_draw_masks(pool, 6)
    return _DRAWS[pool]


def _space(pool: int) -> br.CandidateSpace:
    if pool not in _SPACES:
        _SPACES[pool] = br.build_candidate_space(pool)
    return _SPACES[pool]


def _covered(portfolio: list[Ticket] | tuple[Ticket, ...], pool: int) -> int:
    return br.canonical_covered_sets(portfolio, pool_size=pool, draws=_draws(pool))


def _all_tickets(pool: int) -> list[Ticket]:
    return list(itertools.combinations(range(1, pool + 1), 6))


def _random_portfolio(pool: int, count: int, seed: int) -> br.Portfolio:
    rng = random.Random(seed)
    chosen: set[Ticket] = set()
    while len(chosen) < count:
        chosen.add(tuple(sorted(rng.sample(range(1, pool + 1), 6))))
    return br.canonical_portfolio(sorted(chosen))


def _oracle_neighbors(portfolio: br.Portfolio, pool: int) -> dict[tuple[int, Ticket], int]:
    """Canonical covered-7-set count of every single-ticket replacement."""

    retained = set(portfolio)
    neighbors: dict[tuple[int, Ticket], int] = {}
    for position in range(len(portfolio)):
        rest = [t for index, t in enumerate(portfolio) if index != position]
        for ticket in _all_tickets(pool):
            if ticket not in retained:
                neighbors[(position, ticket)] = _covered([*rest, ticket], pool)
    return neighbors


def test_candidate_space_is_complete_and_deterministic_colex_order() -> None:
    space = _space(10)
    expected = sorted(_all_tickets(10), key=lambda ticket: ticket[::-1])
    actual = [space.ticket_at(rank) for rank in range(space.candidate_count)]
    assert actual == expected
    assert len(set(actual)) == comb(10, 6)
    assert [br.ticket_rank(ticket) for ticket in actual] == list(range(len(actual)))
    rebuilt = br.build_candidate_space(10)
    assert [rebuilt.ticket_at(rank) for rank in range(rebuilt.candidate_count)] == actual


@pytest.mark.parametrize(
    "bad",
    [
        [],
        [(1, 2, 3, 4, 5)],
        [(1, 2, 3, 4, 5, 5)],
        [(1, 2, 3, 4, 5, 13)],
        [(0, 1, 2, 3, 4, 5)],
        [(1, 2, 3, 4, 5, 6), (6, 5, 4, 3, 2, 1)],
    ],
)
def test_illegal_or_duplicate_portfolios_are_rejected(bad: list[Ticket]) -> None:
    with pytest.raises(ValueError):
        br.validate_portfolio(bad, pool_size=12)


def test_validate_returns_the_repository_canonical_form() -> None:
    shuffled = [(12, 3, 4, 5, 6, 7), (1, 2, 3, 4, 5, 6)]
    assert br.validate_portfolio(shuffled, pool_size=12) == (
        (1, 2, 3, 4, 5, 6),
        (3, 4, 5, 6, 7, 12),
    )


@pytest.mark.parametrize(("pool", "count", "seed"), [(12, 3, 1), (12, 3, 7), (11, 4, 3)])
def test_every_candidate_gain_matches_the_canonical_evaluator(
    pool: int, count: int, seed: int
) -> None:
    portfolio = _random_portfolio(pool, count, seed)
    space = _space(pool)
    total = space.winning_set_count
    current = _covered(portfolio, pool)
    for position in range(count):
        rest = [t for index, t in enumerate(portfolio) if index != position]
        covered_without = _covered(rest, pool)
        gains, uncovered, identity = br.candidate_gains(space, portfolio, position)
        assert uncovered == total - covered_without
        assert covered_without + identity == current
        retained = {br.ticket_rank(t) for t in portfolio}
        for rank in range(space.candidate_count):
            if rank in retained:
                assert gains[rank] == -1
            else:
                ticket = space.ticket_at(rank)
                assert covered_without + int(gains[rank]) == _covered([*rest, ticket], pool)


def test_exact_objective_includes_special_number_rescue() -> None:
    pool = 12
    portfolio = _random_portfolio(pool, 3, 5)
    space = _space(pool)
    position = 1
    rest = [t for index, t in enumerate(portfolio) if index != position]
    gains, _uncovered, _identity = br.candidate_gains(space, portfolio, position)
    before = evaluate_portfolio(rest, pool_size=pool, draws=_draws(pool))
    special = pool - 6
    differs = 0
    for rank in range(space.candidate_count):
        if gains[rank] < 0:
            continue
        after = evaluate_portfolio(
            [*rest, space.ticket_at(rank)], pool_size=pool, draws=_draws(pool)
        )
        any_prize = after.official_any_prize_outcome_count - before.official_any_prize_outcome_count
        outright_only = (after.m3_plus_draw_count - before.m3_plus_draw_count) * special
        assert any_prize == 7 * int(gains[rank])
        differs += any_prize != outright_only
    assert differs > 0


@pytest.mark.parametrize(
    ("pool", "count", "seed"), [(12, 3, 2), (12, 4, 9), (11, 3, 4), (11, 5, 8)]
)
def test_step_picks_the_oracle_steepest_strict_move_with_canonical_tie_break(
    pool: int, count: int, seed: int
) -> None:
    portfolio = _random_portfolio(pool, count, seed)
    space = _space(pool)
    current = _covered(portfolio, pool)
    neighbors = _oracle_neighbors(portfolio, pool)
    best = max(neighbors.values())
    outcome = br.best_response_step(space, portfolio)
    assert outcome.covered_before == current
    if best <= current:
        assert outcome.move is None
        assert outcome.portfolio == portfolio
        return
    assert outcome.move is not None
    assert outcome.move.covered_after == best > current
    candidates = [
        br.canonical_portfolio(
            (*(t for index, t in enumerate(portfolio) if index != position), ticket)
        )
        for (position, ticket), value in neighbors.items()
        if value == best
    ]
    assert outcome.portfolio == min(candidates)
    assert outcome.move.tie_count == len(candidates)
    assert _covered(outcome.portfolio, pool) == best
    assert len(set(outcome.portfolio)) == count
    shuffled = list(portfolio)
    random.Random(seed).shuffle(shuffled)
    assert br.best_response_step(space, shuffled).portfolio == outcome.portfolio


def _sweep(
    space: br.CandidateSpace,
    position: int,
    removed: Ticket,
    *,
    covered_before: int,
    identity: int,
    best: int,
    ranks: tuple[int, ...],
) -> br.PositionSweep:
    return br.PositionSweep(
        position=position,
        removed=removed,
        uncovered_without=space.winning_set_count - covered_before + identity,
        identity_gain=identity,
        best_gain=best,
        best_count=len(ranks),
        best_ranks=ranks,
    )


def test_only_a_strict_improvement_is_accepted() -> None:
    space = _space(10)
    portfolio = _random_portfolio(10, 3, 0)
    ranks = tuple(
        rank
        for rank in range(space.candidate_count)
        if rank not in {br.ticket_rank(t) for t in portfolio}
    )

    def decide(bests: tuple[int, int, int]) -> br.AcceptedMove | None:
        sweeps = [
            _sweep(space, i, t, covered_before=60, identity=10 + i, best=bests[i], ranks=ranks[:1])
            for i, t in enumerate(portfolio)
        ]
        return br.choose_move(space, portfolio, sweeps, iteration=1)

    assert decide((10, 11, 12)) is None  # equal at every position
    assert decide((9, 5, 0)) is None  # worse everywhere
    improving = decide((10, 12, 12))  # +1 at position 1 only
    assert improving is not None
    assert (improving.position, improving.covered_after, improving.covered_before) == (1, 61, 60)
    assert decide((12, 11, 12)) is not None  # position 0 improves by 2


def test_cross_position_tie_resolves_to_the_smallest_resulting_portfolio() -> None:
    space = _space(10)
    portfolio = _random_portfolio(10, 3, 0)
    rank = next(
        r for r in range(space.candidate_count) if r not in {br.ticket_rank(t) for t in portfolio}
    )
    sweeps = [
        _sweep(space, i, t, covered_before=60, identity=10, best=11, ranks=(rank,))
        for i, t in enumerate(portfolio)
    ]
    move = br.choose_move(space, portfolio, sweeps, iteration=1)
    assert move is not None
    added = space.ticket_at(rank)
    options = [
        br.canonical_portfolio((*(t for j, t in enumerate(portfolio) if j != i), added))
        for i in range(3)
    ]
    rest = tuple(t for j, t in enumerate(portfolio) if j != move.position)
    assert br.canonical_portfolio((*rest, added)) == min(options)
    assert move.tie_count == 3


def test_disagreeing_current_counts_fail_closed() -> None:
    space = _space(10)
    portfolio = _random_portfolio(10, 2, 0)
    sweeps = [
        _sweep(space, 0, portfolio[0], covered_before=60, identity=10, best=12, ranks=(0,)),
        _sweep(space, 1, portfolio[1], covered_before=61, identity=10, best=12, ranks=(0,)),
    ]
    with pytest.raises(br.BestResponseGateError):
        br.choose_move(space, portfolio, sweeps, iteration=1)


def test_retained_tickets_are_never_replacement_candidates() -> None:
    pool = 8  # C(8, 6) = 28 tickets
    space = _space(pool)
    everything = _all_tickets(pool)
    full = br.canonical_portfolio(everything)
    exhausted = br.best_response_step(space, full)
    assert exhausted.move is None
    assert all(sweep.best_count == 0 for sweep in exhausted.sweeps)
    almost = br.canonical_portfolio(everything[:-1])
    outcome = br.best_response_step(space, almost)
    assert len(set(outcome.portfolio)) == len(almost)
    for sweep in outcome.sweeps:
        assert set(sweep.best_ranks) <= {br.ticket_rank(everything[-1])}
    portfolio = _random_portfolio(12, 4, 6)
    for position in range(4):
        gains, _, _ = br.candidate_gains(_space(12), portfolio, position)
        assert all(gains[br.ticket_rank(t)] == -1 for t in portfolio)


@pytest.mark.parametrize(("pool", "count", "seed"), [(11, 3, 12), (12, 3, 3), (11, 4, 1)])
def test_ascent_terminates_at_a_verified_single_replacement_local_optimum(
    pool: int, count: int, seed: int
) -> None:
    start = _random_portfolio(pool, count, seed)
    result = br.run_ascent(start, pool_size=pool, space=_space(pool))
    assert result.reached_local_optimum
    trajectory = [_covered(start, pool)]
    portfolio = start
    for move in result.moves:
        rest = tuple(t for t in portfolio if t != move.removed)
        portfolio = br.canonical_portfolio((*rest, move.added))
        trajectory.append(_covered(portfolio, pool))
        assert trajectory[-1] > trajectory[-2]
        assert move.covered_after == trajectory[-1]
    assert portfolio == result.terminal
    assert result.sweeps_completed == len(result.moves) + 1
    neighbors = _oracle_neighbors(result.terminal, pool)
    assert max(neighbors.values()) <= trajectory[-1]
    assert br.best_response_step(_space(pool), result.terminal).move is None


def test_ascent_improves_a_deliberately_poor_start_and_resume_is_consistent() -> None:
    pool = 12
    poor = ((1, 2, 3, 4, 5, 6), (1, 2, 3, 4, 5, 7), (1, 2, 3, 4, 5, 8))
    space = _space(pool)
    full = br.run_ascent(poor, pool_size=pool, space=space, verify_samples=2, seed=4)
    assert full.moves
    assert _covered(full.terminal, pool) > _covered(poor, pool)
    partial = br.run_ascent(poor, pool_size=pool, space=space, max_iterations=1)
    assert not partial.reached_local_optimum
    assert partial.sweeps_completed == 1
    resumed = br.run_ascent(poor, pool_size=pool, space=space, resume_moves=partial.moves)
    assert resumed.terminal == full.terminal
    assert resumed.moves == full.moves


@pytest.fixture(scope="module")
def space49() -> br.CandidateSpace:
    return br.build_candidate_space()


def test_big_lotto_candidate_space_has_every_ticket_once(space49: br.CandidateSpace) -> None:
    assert space49.candidate_count == comb(49, 6) == 13_983_816
    assert space49.ticket_at(0) == (1, 2, 3, 4, 5, 6)
    assert space49.ticket_at(space49.candidate_count - 1) == (44, 45, 46, 47, 48, 49)
    rng = random.Random(0)
    for rank in rng.sample(range(space49.candidate_count), 200):
        assert br.ticket_rank(space49.ticket_at(rank)) == rank


def test_pinned_k10_baseline_is_legal_and_reproduced_at_full_scale(
    space49: br.CandidateSpace,
) -> None:
    pinned = SEALED_GEOMETRY_PORTFOLIOS[10]
    tickets = br.validate_portfolio(pinned.tickets, pool_size=49)
    assert len(tickets) == 10
    assert canonical_portfolio_sha256(tickets) == _K10_PINNED_SHA == pinned.portfolio_sha256
    exact = evaluate_portfolio(tickets)
    assert exact.official_any_prize_outcome_count == _K10_PINNED_COUNT
    assert exact.official_any_prize == Fraction(536005, 1827672)
    # The engine's own tables (which also self-check exact divisibility) agree.
    tables = br._build_tables(space49, tickets)
    assert space49.winning_set_count - tables.uncovered == _K10_PINNED_COUNT // 7


def test_chunk_boundaries_do_not_change_any_result(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = 12
    portfolio = _random_portfolio(pool, 3, 11)
    space = _space(pool)
    reference = [br.candidate_gains(space, portfolio, position) for position in range(3)]
    monkeypatch.setattr(br, "_CHUNK_ROWS", 97)
    monkeypatch.setattr(br, "_SCATTER_ROWS", 61)
    for position, (gains, uncovered, identity) in enumerate(reference):
        small_gains, small_uncovered, small_identity = br.candidate_gains(
            space, portfolio, position
        )
        assert (small_gains == gains).all()
        assert (small_uncovered, small_identity) == (uncovered, identity)


def test_full_scale_gains_match_canonical_on_a_synthetic_portfolio(
    space49: br.CandidateSpace,
) -> None:
    """Production-scale gain path against the canonical evaluator (not the K10 portfolio)."""

    portfolio = _random_portfolio(49, 4, 20260929)
    position = 2
    rng = random.Random(3)
    retained = {br.ticket_rank(t) for t in portfolio}
    ranks = [r for r in rng.sample(range(space49.candidate_count), 40) if r not in retained][:24]
    sweep = br.sweep_position(space49, portfolio, position, sample_ranks=ranks)
    rest = [t for index, t in enumerate(portfolio) if index != position]
    draws = _draws(49)
    covered_without = br.canonical_covered_sets(rest, pool_size=49, draws=draws)
    assert space49.winning_set_count - sweep.uncovered_without == covered_without
    checks = [(rank, gain) for rank, gain in sweep.sampled_gains]
    checks.append((sweep.best_ranks[0], sweep.best_gain))
    checks.append((br.ticket_rank(portfolio[position]), sweep.identity_gain))
    for rank, gain in checks:
        ticket = space49.ticket_at(rank)
        after = br.canonical_covered_sets([*rest, ticket], pool_size=49, draws=draws)
        assert covered_without + gain == after
    assert sweep.best_gain >= max(gain for _rank, gain in sweep.sampled_gains)


def test_cli_baseline_path_writes_a_truthful_incomplete_summary(
    tmp_path: Path,
) -> None:
    """``--max-iterations 0`` exercises the CLI and pinned baseline without any sweep."""

    assert br.main(["--output-dir", str(tmp_path), "--max-iterations", "0"]) == 0
    summary = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    assert summary["baseline"]["portfolio_sha256"] == _K10_PINNED_SHA
    assert summary["baseline"]["official_any_prize_outcome_count"] == _K10_PINNED_COUNT
    assert summary["baseline"]["official_any_prize_probability"] == "536005/1827672"
    assert summary["sweeps_completed"] == 0
    assert summary["verdict"] == "INCOMPLETE"
    assert summary["local_optimum_claim"] == "NOT_REACHED"
    assert summary["global_optimum_claim"] == "NO"
    assert summary["predictive_edge_claim"] == "NO"
