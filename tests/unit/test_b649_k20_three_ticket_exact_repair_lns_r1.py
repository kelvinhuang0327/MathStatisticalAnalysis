"""Focused tests for the three-ticket exact repair inside a bounded candidate pool.

Every check compares the module with an oracle written here: explicit 7-set
arithmetic on v = 16 toy universes, brute force over every 3-subset of a pool
scored by the canonical evaluator, and the canonical evaluator on seeded 49/20
repaired candidates. Toy portfolios concentrate on {11..16} so R leaves 7-sets
uncovered and the repair has strict winners and ties.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import random
from collections.abc import Sequence
from dataclasses import dataclass
from math import comb
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import b649_k20_three_ticket_exact_repair_lns_r1 as lns
from lottolab.research import b649_official_any_prize_exact as canonical
from lottolab.research.b649_official_any_prize_exact import DrawMasks

ROOT = Path(__file__).resolve().parents[2]
V = 16
HOT = frozenset(range(11, V + 1))
BASE: tuple[lns.Ticket, ...] = tuple(
    ticket for ticket in itertools.combinations(range(1, V + 1), 6) if len(HOT & set(ticket)) >= 4
)
SEVEN_SETS: tuple[frozenset[int], ...] = tuple(
    frozenset(seven) for seven in itertools.combinations(range(1, V + 1), 7)
)
TOY_INDICES: lns.Triple = (1, 3, 5)
TOY_POOL_MAX = 14
TOY_GUIDED_TOP_L = 2
TIE_SEED = 26


@dataclass(frozen=True)
class ToyCase:
    start: lns.Portfolio
    removed: lns.Portfolio
    rest: lns.Portfolio
    elite: tuple[lns.Ticket, ...]
    residual: lns.ResidualCoverage
    pool: lns.CandidatePool


def _toy_case(seed: int) -> ToyCase:
    rng = random.Random(seed)
    start = lns.normalize_portfolio(rng.sample(BASE, 7), pool_size=V)
    removed, rest = lns.split_start(start, TOY_INDICES)
    elite = (*rng.sample(BASE, 4), rest[0])  # the last one is already in R
    residual = lns.ResidualCoverage(rest, pool_size=V)
    pool = lns.build_candidate_pool(
        start,
        TOY_INDICES,
        pool_size=V,
        residual=residual,
        elite=elite,
        pool_max=TOY_POOL_MAX,
        guided_top_l=TOY_GUIDED_TOP_L,
    )
    return ToyCase(start, removed, rest, elite, residual, pool)


# --- independent oracles -------------------------------------------------------------


def cover(ticket: Sequence[int]) -> frozenset[frozenset[int]]:
    numbers = set(ticket)
    return frozenset(seven for seven in SEVEN_SETS if len(seven & numbers) >= 3)


def covered(portfolio: Sequence[Sequence[int]]) -> set[frozenset[int]]:
    union: set[frozenset[int]] = set()
    for ticket in portfolio:
        union |= cover(ticket)
    return union


def one_number_neighbors(ticket: Sequence[int]) -> set[lns.Ticket]:
    return {
        candidate
        for candidate in itertools.combinations(range(1, V + 1), 6)
        if len(set(candidate) & set(ticket)) == 5
    }


def canonical_count(portfolio: Sequence[Sequence[int]], draws: DrawMasks, pool_size: int) -> int:
    result = canonical.evaluate_portfolio(portfolio, pool_size=pool_size, draws=draws)
    return int(result.official_any_prize_outcome_count)


def brute_force_repair(
    case: ToyCase, draws: DrawMasks
) -> tuple[int, str, list[str], dict[lns.Triple, int]]:
    """(best count, best sha, tied shas, count per pool triple) by full canonical recounts."""

    counts: dict[lns.Triple, int] = {}
    keyed: list[tuple[int, str]] = []
    for triple in itertools.combinations(range(len(case.pool.tickets)), 3):
        portfolio = [*case.rest, *(case.pool.tickets[i] for i in triple)]
        count = canonical_count(portfolio, draws, V)
        counts[(triple[0], triple[1], triple[2])] = count
        keyed.append((-count, lns.portfolio_sha256(portfolio, pool_size=V)))
    keyed.sort()
    best = -keyed[0][0]
    tied = [sha for negative, sha in keyed if -negative == best]
    return best, keyed[0][1], tied, counts


@pytest.fixture(scope="module")
def draws16() -> DrawMasks:
    return canonical.all_main_draw_masks(V, 6)


@pytest.fixture(scope="module")
def draws49() -> DrawMasks:
    return canonical.all_main_draw_masks(49, 6)


# --- toy-universe exactness ----------------------------------------------------------


def test_modules_resolve_to_this_checkout() -> None:
    assert Path(lns.__file__).resolve().is_relative_to(ROOT / "src")
    assert Path(canonical.__file__).resolve().is_relative_to(ROOT / "src")


def test_seven_set_identity_matches_the_canonical_count(draws16: DrawMasks) -> None:
    rng = random.Random(3)
    for size in (1, 3, 5):
        portfolio = rng.sample(BASE, size)
        assert canonical_count(portfolio, draws16, V) == 7 * len(covered(portfolio))
        rest = lns.normalize_portfolio(portfolio, pool_size=V)
        assert lns.covered_seven_sets(rest, pool_size=V, draws=draws16) == len(covered(rest))
    assert lns.covered_seven_sets((), pool_size=V) == 0


@pytest.mark.parametrize("seed", [0, 2, 9, TIE_SEED])
def test_marginal_equals_the_seven_set_oracle(seed: int) -> None:
    case = _toy_case(seed)
    rest_cover = covered(case.rest)
    probes = [*case.pool.tickets, *random.Random(seed).sample(BASE, 6)]
    for ticket in probes:
        assert case.residual.marginal(ticket) == len(cover(ticket) - rest_cover)
    empty = lns.ResidualCoverage((), pool_size=V)
    assert empty.marginal(case.removed[0]) == len(cover(case.removed[0]))


def test_one_number_replacements_are_every_legal_neighbor_once() -> None:
    ticket = (2, 5, 11, 12, 14, 16)
    images = lns.one_number_replacements(ticket, pool_size=V)
    assert len(images) == len(set(images)) == 6 * (V - 6)
    assert set(images) == one_number_neighbors(ticket)
    assert len(lns.one_number_replacements((1, 2, 3, 4, 5, 6), pool_size=49)) == 258


@pytest.mark.parametrize("seed", [0, 2, 9, TIE_SEED])
def test_candidate_pool_is_legal_distinct_bounded_and_excludes_rest(seed: int) -> None:
    case = _toy_case(seed)
    tickets = case.pool.tickets
    assert tickets == tuple(sorted(tickets))
    assert len(set(tickets)) == len(tickets) <= TOY_POOL_MAX
    assert all(lns.normalize_ticket(ticket, pool_size=V) == ticket for ticket in tickets)
    assert not set(tickets) & set(case.rest)
    rest_cover = covered(case.rest)
    assert case.pool.marginals == tuple(len(cover(t) - rest_cover) for t in tickets)
    assert case.pool.accounting["POOL_SIZE"] == len(tickets)
    with pytest.raises(lns.RepairError):
        lns.pool_intersections(case.residual, [*tickets, tickets[0]])


def test_rest_tickets_generated_as_neighbors_are_excluded() -> None:
    removed_ticket = (1, 11, 12, 13, 14, 15)
    neighbor = (2, 11, 12, 13, 14, 15)  # a one-number replacement of removed_ticket, kept in R
    others = [t for t in random.Random(5).sample(BASE, 8) if t not in (removed_ticket, neighbor)]
    start = lns.normalize_portfolio([removed_ticket, neighbor, *others[:5]], pool_size=V)
    positions = sorted(start.index(t) for t in (removed_ticket, *others[:2]))
    indices = (positions[0], positions[1], positions[2])
    _removed, rest = lns.split_start(start, indices)
    assert neighbor in rest
    residual = lns.ResidualCoverage(rest, pool_size=V)
    pool = lns.build_candidate_pool(
        start,
        indices,
        pool_size=V,
        residual=residual,
        elite=(),
        pool_max=10_000,  # no cut: every generated candidate would be retained
        guided_top_l=2,
    )
    assert pool.accounting["OPTIONAL_RETAINED"] == pool.accounting["OPTIONAL_DISTINCT"]
    assert neighbor not in pool.tickets
    assert not set(pool.tickets) & set(rest)
    assert pool.accounting["IN_REST_EXCLUDED"] >= 1


@pytest.mark.parametrize("seed", [0, 2, 9, TIE_SEED])
def test_removed_tickets_are_in_the_pool(seed: int) -> None:
    case = _toy_case(seed)
    assert case.removed == tuple(case.start[i] for i in TOY_INDICES)
    positions = case.pool.removed_indices
    assert tuple(case.pool.tickets[i] for i in positions) == case.removed
    assert all(case.pool.sources[i] == lns.SOURCE_REMOVED for i in positions)


@pytest.mark.parametrize("seed", [0, 2, 9, TIE_SEED])
def test_elite_tickets_are_incorporated_and_the_rest_is_the_top_marginals(seed: int) -> None:
    case = _toy_case(seed)
    rest = set(case.rest)
    elite = {tuple(sorted(ticket)) for ticket in case.elite}
    mandatory = set(case.removed) | (elite - rest)
    source = dict(zip(case.pool.tickets, case.pool.sources, strict=True))
    assert mandatory <= set(case.pool.tickets)
    assert all(source[t] == lns.SOURCE_ELITE for t in elite - rest - set(case.removed))
    assert case.pool.accounting["ELITE_IN_REST_EXCLUDED"] == len(elite & rest) >= 1
    assert case.pool.mandatory_count == len(mandatory)

    rest_cover = covered(case.rest)

    def marginal(ticket: lns.Ticket) -> int:
        return len(cover(ticket) - rest_cover)

    first = {t: one_number_neighbors(t) - rest for t in case.removed}
    generated: set[lns.Ticket] = set()
    for images in first.values():
        generated |= images
    for ticket in case.removed:
        seeds = sorted(first[ticket], key=lambda t: (-marginal(t), t))[:TOY_GUIDED_TOP_L]
        for seed_ticket in seeds:
            generated |= one_number_neighbors(seed_ticket) - rest
    optional = sorted(generated - mandatory, key=lambda t: (-marginal(t), t))
    expected = set(optional[: TOY_POOL_MAX - len(mandatory)])
    assert set(case.pool.tickets) - mandatory == expected


@pytest.mark.parametrize("seed", [0, TIE_SEED])
def test_exact_residual_repair_equals_direct_full_portfolio_recount(
    seed: int, draws16: DrawMasks
) -> None:
    case = _toy_case(seed)
    intersections = lns.pool_intersections(case.residual, case.pool.tickets)
    rest_cover = covered(case.rest)
    base = lns.covered_seven_sets(case.rest, pool_size=V, draws=draws16)
    assert base == len(rest_cover)
    for triple in itertools.combinations(range(len(case.pool.tickets)), 3):
        chosen = [case.pool.tickets[i] for i in triple]
        union = lns.union_of_three(intersections, *triple)
        direct = len(covered([*case.rest, *chosen]))
        assert union == direct - base
        assert 7 * (base + union) == canonical_count([*case.rest, *chosen], draws16, V)


@pytest.mark.parametrize("seed", [0, 2, 9, TIE_SEED])
def test_exact_in_pool_solver_agrees_with_brute_force(seed: int, draws16: DrawMasks) -> None:
    case = _toy_case(seed)
    intersections = lns.pool_intersections(case.residual, case.pool.tickets)
    solution = lns.solve_exact_in_pool(
        intersections,
        case.pool.tickets,
        case.rest,
        pool_size=V,
        reference=case.pool.removed_indices,
    )
    best, best_sha, tied, counts = brute_force_repair(case, draws16)
    base = lns.covered_seven_sets(case.rest, pool_size=V, draws=draws16)
    start_count = canonical_count(case.start, draws16, V)
    assert solution.optimality_status == lns.POOL_OPTIMALITY_EXACT
    assert solution.combinations == solution.exact_scored == comb(len(case.pool.tickets), 3)
    assert 7 * (base + solution.best_union) == best
    assert solution.best_sha256 == best_sha
    assert canonical_count(solution.best_portfolio, draws16, V) == best
    assert 7 * (base + cast(int, solution.reference_union)) == start_count
    assert solution.strict_improvements == sum(1 for c in counts.values() if c > start_count)
    assert solution.strict_improvements and best > start_count  # non-vacuous fixture
    assert solution.tie_count == len(tied)


def test_tie_break_is_lowest_sha_and_independent_of_pool_order(draws16: DrawMasks) -> None:
    case = _toy_case(TIE_SEED)
    intersections = lns.pool_intersections(case.residual, case.pool.tickets)
    first = lns.solve_exact_in_pool(intersections, case.pool.tickets, case.rest, pool_size=V)
    again = lns.solve_exact_in_pool(intersections, case.pool.tickets, case.rest, pool_size=V)
    assert first == again
    _best, best_sha, tied, _counts = brute_force_repair(case, draws16)
    assert first.tie_count == len(tied) > 1  # the fixture really has ties
    assert first.tied_sha256 == tuple(sorted(tied))
    assert first.best_sha256 == best_sha == min(tied)

    reordered = tuple(reversed(case.pool.tickets))
    reversed_intersections = lns.pool_intersections(case.residual, reordered)
    flipped = lns.solve_exact_in_pool(reversed_intersections, reordered, case.rest, pool_size=V)
    assert flipped.best_sha256 == first.best_sha256
    assert flipped.best_portfolio == first.best_portfolio
    assert flipped.tied_sha256 == first.tied_sha256


def test_repair_refuses_rest_tickets_and_repeated_replacements() -> None:
    case = _toy_case(0)
    with pytest.raises(lns.RepairError):
        lns.repair_portfolio(
            case.rest, (case.rest[0], *case.pool.tickets[:2]), (0, 1, 2), pool_size=V
        )
    with pytest.raises(lns.RepairError):
        lns.repair_portfolio(case.rest, case.pool.tickets, (0, 0, 1), pool_size=V)
    polluted = tuple(sorted((*case.pool.tickets[:5], case.rest[0])))
    with pytest.raises(lns.RepairError):
        lns.solve_exact_in_pool(
            lns.pool_intersections(case.residual, polluted), polluted, case.rest, pool_size=V
        )


# --- 49/20 authorities, destroy selection and canonical parity -----------------------


def test_destroy_triples_are_24_distinct_seeded_and_reproducible() -> None:
    triples = lns.select_destroy_triples()
    population = list(itertools.combinations(range(20), 3))
    assert triples == tuple(random.Random(20260930).sample(population, 24))
    assert len(set(triples)) == lns.DESTROY_TRIPLE_SAMPLE_COUNT == 24
    assert all(0 <= i < j < k < 20 for i, j, k in triples)
    assert lns.select_destroy_triples() == triples


def test_cycle_constant_is_the_pinned_candidate_three_tickets_from_v6() -> None:
    assert lns.portfolio_sha256(lns.CYCLE_PORTFOLIO, pool_size=49) == lns.CYCLE_PORTFOLIO_SHA256
    raw = (ROOT / lns.V6_LOCATOR).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == lns.V6_FILE_SHA256
    v6 = lns.normalize_portfolio(json.loads(raw)["TICKETS"], pool_size=49)
    assert lns.portfolio_sha256(v6, pool_size=49) == lns.V6_PORTFOLIO_SHA256
    assert len(set(lns.CYCLE_PORTFOLIO) - set(v6)) == 3


def test_starts_and_elite_reproduce_their_canonical_counts(draws49: DrawMasks) -> None:
    v6 = lns.bind_v6(ROOT, draws=draws49)
    cycle = lns.bind_cycle(ROOT, draws=draws49)
    v5 = lns.bind_v5(ROOT, draws=draws49)
    assert (v6.outcome_count, cycle.outcome_count, v5.outcome_count) == (
        313_239_647,
        313_239_661,
        312_986_016,
    )
    assert cycle.provenance["BLOB_BINDING"] == "PASS"
    assert len({*v5.portfolio, *v6.portfolio, *cycle.portfolio}) == 28


def test_49_20_repaired_candidates_agree_with_the_canonical_evaluator(
    draws49: DrawMasks,
) -> None:
    start = lns.bind_v6(ROOT, draws=draws49)
    samples = 0
    mismatches = 0
    for indices in lns.select_destroy_triples()[:2]:
        _removed, rest = lns.split_start(start.portfolio, indices)
        residual = lns.ResidualCoverage(rest, pool_size=49)
        pool = lns.build_candidate_pool(
            start.portfolio,
            indices,
            pool_size=49,
            residual=residual,
            elite=start.portfolio,
            pool_max=16,
            guided_top_l=0,
        )
        intersections = lns.pool_intersections(residual, pool.tickets)
        base = lns.covered_seven_sets(rest, pool_size=49, draws=draws49)
        start_union = lns.union_of_three(intersections, *pool.removed_indices)
        assert 7 * (base + start_union) == start.outcome_count
        population = list(itertools.combinations(range(len(pool.tickets)), 3))
        for i, j, k in random.Random(f"test:{indices}").sample(population, 15):
            candidate = lns.repair_portfolio(rest, pool.tickets, (i, j, k), pool_size=49)
            assert len(candidate) == 20
            predicted = 7 * (base + lns.union_of_three(intersections, i, j, k))
            samples += 1
            mismatches += predicted != canonical_count(candidate, draws49, 49)
    assert samples >= 30
    assert mismatches == 0
