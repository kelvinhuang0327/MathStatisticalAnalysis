"""Focused tests for the K20 global residual-pool repair pilot.

Toy pools use brute force written from the definition, and the canonical evaluator, as oracles.
Two non-pilot, non-parity real destroy sets exercise the real 49/6 space end to end.
"""

from __future__ import annotations

import dataclasses
import hashlib
import itertools
import json
import random
import subprocess
from collections.abc import Sequence
from math import comb
from pathlib import Path
from typing import cast

import numpy as np
import numpy.typing as npt
import pytest

from lottolab.research import b649_k20_five_ticket_exact_repair_r1 as five
from lottolab.research import b649_k20_global_residual_pool_repair_r1 as repair

# real destroy sets that are neither in the pilot sample nor in the parity sets
DEV4 = (7, 11, 12, 14)
DEV5 = (3, 5, 8, 15, 19)
RESULT_PATH = repair.REPO_ROOT / repair.RESULT_RELATIVE_PATH


def _elites() -> list[five.Portfolio]:
    return [pin.tickets for pin in five.PINNED_ELITES]


def _sha_key(chosen: tuple[int, ...]) -> str:
    return hashlib.sha256(",".join(map(str, chosen)).encode()).hexdigest()


def _instance(
    generator: np.random.Generator, pool: int, rows: int
) -> tuple[npt.NDArray[np.uint64], npt.NDArray[np.int64]]:
    """Random winner-mask rows; a bit is set with probability 0.3, so the top bit is exercised."""

    masks = np.zeros(rows, dtype=np.uint64)
    for bit in range(pool):
        masks |= (generator.random(rows) < 0.3).astype(np.uint64) << np.uint64(bit)
    masks = np.unique(masks[masks != 0])
    weights = generator.integers(1, 40, size=masks.size).astype(np.int64)
    return masks, weights


class _MiscountingRecounter(five.CanonicalRecounter):
    """A recounter that is always off by one, to prove the recount guards fire."""

    def count(self, portfolio: Sequence[five.Ticket]) -> int:
        return super().count(portfolio) + 1


@pytest.fixture(scope="module")
def universe49() -> repair.ColexUniverse:
    return repair.build_universe()


@pytest.fixture(scope="module")
def recounter() -> five.CanonicalRecounter:
    return five.CanonicalRecounter()


# ------------------------------------------------------------------ constants, sets, start


def test_residual_coefficients_are_the_moebius_weights_and_the_hit_constant_is_direct() -> None:
    assert repair.RESIDUAL_COEFFICIENTS == {3: 1, 4: -3, 5: 6, 6: -10}
    assert repair.tickets_hitting_each_subset(49) == 432_824
    for pool in (8, 10, 13):
        direct = sum(
            1
            for ticket in itertools.combinations(range(pool), 6)
            if len(set(ticket) & set(range(7))) >= 3
        )
        assert repair.tickets_hitting_each_subset(pool) == direct


def test_destroy_sets_are_deterministic_distinct_prefix_stable_and_disjoint_from_parity() -> None:
    pilot = repair.pilot_destroy_sets()
    assert pilot == {
        4: ((12, 13, 17, 19), (0, 1, 14, 19), (1, 9, 15, 16)),
        5: ((2, 3, 4, 10, 11), (1, 7, 15, 16, 19), (5, 9, 10, 14, 17)),
    }
    parity = repair.parity_destroy_sets()
    assert parity == {
        4: ((7, 8, 11, 15), (1, 3, 5, 13)),
        5: ((1, 2, 7, 8, 17), (3, 6, 7, 8, 14)),
    }
    for size in (4, 5):
        assert len(set(pilot[size])) == repair.PILOT_SETS_PER_SIZE
        assert set(pilot[size]).isdisjoint(parity[size])
        assert DEV4 not in pilot[size] + parity[size]
        assert DEV5 not in pilot[size] + parity[size]
    longer = repair.ranked_destroy_sets(8)
    assert all(longer[size][:3] == pilot[size] for size in (4, 5))
    # the rule is a plain sha256 ranking, independent of any library RNG
    expected = sorted(
        itertools.combinations(range(20), 4),
        key=lambda c: hashlib.sha256(f"20261002:{','.join(map(str, c))}".encode()).hexdigest(),
    )[:3]
    assert list(pilot[4]) == expected


def test_sets_are_persisted_before_scoring_and_tampering_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "destroy-samples.json"
    sha = repair.persist_destroy_samples(path, repair.pilot_destroy_sets())
    assert sha == hashlib.sha256(path.read_bytes()).hexdigest()
    assert repair.persist_destroy_samples(path, repair.pilot_destroy_sets()) == sha
    assert repair.load_persisted_samples(path) == repair.pilot_destroy_sets()
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["PILOT_SEED"] == 20261002
    assert document["POPULATION"] == {"4": comb(20, 4), "5": comb(20, 5)}
    assert document["DESTROY4_SETS"] == [[12, 13, 17, 19], [0, 1, 14, 19], [1, 9, 15, 16]]
    document["DESTROY4_SETS"][0][0] = 11
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="differ"):
        repair.load_persisted_samples(path)
    with pytest.raises(ValueError, match="differ"):
        repair.persist_destroy_samples(path, repair.pilot_destroy_sets())


def _source_commit_available() -> bool:
    probe = subprocess.run(
        ["git", "cat-file", "-e", f"{repair.SOURCE_COMMIT}:{repair.SOURCE_ARTIFACT}"],
        cwd=repair.REPO_ROOT,
        capture_output=True,
        check=False,
    )
    return probe.returncode == 0


def test_start_is_reproduced_from_its_source_commit_and_recounted(
    recounter: five.CanonicalRecounter,
) -> None:
    if not _source_commit_available():
        pytest.skip("source commit is not available in this clone")
    record = repair.reproduce_start(recounter)
    assert record["MATCH"] is True
    assert record["CANONICAL_RECOUNT"] == record["SOURCE_ARTIFACT_BEST_COUNT"] == 313239661
    assert record["EMBEDDED_SHA256"] == record["SOURCE_PORTFOLIO_SHA256"] == repair.START_SHA256
    assert repair.START_SHA256 == (
        "7ce41ff21d5c0821f1d5dda683e23114086f5024fc6d98d4e574df5306659b1e"
    )


def test_start_reproduction_stops_on_any_baseline_drift() -> None:
    if not _source_commit_available():
        pytest.skip("source commit is not available in this clone")
    with pytest.raises(repair.StopConditionError) as drift:
        repair.reproduce_start(_MiscountingRecounter())
    assert drift.value.code == "START_BASELINE_MISMATCH"


def test_a_missing_source_commit_is_its_own_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(repair, "SOURCE_COMMIT", "0" * 40)
    with pytest.raises(repair.StopConditionError) as missing:
        repair.read_source_artifact()
    assert missing.value.code == "MISSING_SOURCE_COMMIT"


# ------------------------------------------------------------------ colex tables


@pytest.mark.parametrize(("pool", "size"), [(7, 3), (9, 4), (10, 6), (13, 5), (49, 3), (49, 4)])
def test_colex_subsets_are_complete_ascending_and_ranked(pool: int, size: int) -> None:
    table = repair.colex_subsets(pool, size)
    assert table.shape == (comb(pool, size), size)
    expected = sorted(itertools.combinations(range(pool), size), key=lambda c: c[::-1])
    assert [tuple(int(v) for v in row) for row in table] == expected
    ranks = repair.colex_rank(repair.build_universe(pool).binomial, table)
    assert np.array_equal(ranks, np.arange(table.shape[0], dtype=np.int64))


def test_universe_indexing_round_trips_and_rejects_illegal_tickets() -> None:
    universe = repair.build_universe(12)
    for index in range(0, universe.tickets.shape[0], 37):
        assert universe.index_of(universe.ticket_at(index)) == index
    assert universe.index_of((6, 5, 4, 3, 2, 1)) == universe.index_of((1, 2, 3, 4, 5, 6)) == 0
    for bad in [(1, 2, 3, 4, 5), (1, 1, 2, 3, 4, 5), (0, 1, 2, 3, 4, 5), (1, 2, 3, 4, 5, 13)]:
        with pytest.raises(ValueError, match="ticket"):
            universe.index_of(bad)
    for pool in (6, 65):
        with pytest.raises(ValueError, match="pool"):
            repair.build_universe(pool)


def test_real_ticket_universe_is_exactly_c_49_6(universe49: repair.ColexUniverse) -> None:
    tally = repair.ParityTally()
    repair.check_real_enumeration(universe49, tally)
    assert universe49.tickets.shape[0] == repair.TOTAL_TICKETS == 13_983_816
    assert tally.comparisons == 3
    assert tally.mismatches == 0


# ------------------------------------------------------------------ the global scorer


@pytest.mark.parametrize("pool", [8, 9, 10, 11, 12])
def test_scorer_equals_the_definition_on_toy_pools(pool: int) -> None:
    rng = random.Random(pool)
    universe = repair.build_universe(pool)
    every = list(itertools.combinations(range(1, pool + 1), 6))
    for size in (0, 1, 2, 5, 9):
        remaining = tuple(rng.sample(every, min(size, len(every))))
        expected, residual = repair.brute_force_marginals(pool, remaining)
        scores = repair.score_all_tickets(universe, remaining)
        assert scores.tickets_scored == len(every)
        got = {universe.ticket_at(i): int(scores.marginals[i]) for i in range(len(every))}
        assert got == expected
        repair.check_score_identities(scores, universe, residual)
        assert all(got[ticket] == 0 for ticket in remaining)


def test_a_frozen_set_that_wins_everything_leaves_no_marginal_anywhere() -> None:
    universe = repair.build_universe(9)
    every = tuple(itertools.combinations(range(1, 10), 6))
    scores = repair.score_all_tickets(universe, every)
    assert int(scores.marginals.max()) == 0
    repair.check_score_identities(scores, universe, 0)


def test_the_identity_check_refuses_an_incomplete_or_corrupted_scoring() -> None:
    universe = repair.build_universe(10)
    remaining = tuple(itertools.islice(itertools.combinations(range(1, 11), 6), 0, 40, 9))
    expected, residual = repair.brute_force_marginals(10, remaining)
    del expected
    scores = repair.score_all_tickets(universe, remaining)
    repair.check_score_identities(scores, universe, residual)
    bad_sum = dataclasses.replace(scores, sum_marginals=scores.sum_marginals + 1)
    bad_top = dataclasses.replace(scores, sum_top_counts=scores.sum_top_counts - 1)
    partial = dataclasses.replace(scores, tickets_scored=scores.tickets_scored - 1)
    for corrupted in (bad_sum, bad_top, partial):
        with pytest.raises(AssertionError, match="identities"):
            repair.check_score_identities(corrupted, universe, residual)
    with pytest.raises(AssertionError, match="identities"):
        repair.check_score_identities(scores, universe, residual + 1)
    with pytest.raises(AssertionError, match="complete"):
        repair.global_top(universe, partial, 5)


# ------------------------------------------------------------------ global ranking


@pytest.mark.parametrize("pool", [11, 12, 13])
def test_top_selection_and_exact_ranks_equal_brute_force_including_ties(pool: int) -> None:
    rng = random.Random(100 + pool)
    universe = repair.build_universe(pool)
    every = list(itertools.combinations(range(1, pool + 1), 6))
    remaining = tuple(rng.sample(every, 1))
    expected, _ = repair.brute_force_marginals(pool, remaining)
    scores = repair.score_all_tickets(universe, remaining)
    ranking = sorted(expected, key=lambda ticket: (-expected[ticket], ticket))
    spread = len(set(expected.values()))
    assert 2 <= spread < len(expected) // 2, "a spread of marginals with many exact ties"
    counts = repair.toy_top_counts(expected, len(ranking))
    cuts = [
        c for c in counts if c < len(ranking) and expected[ranking[c - 1]] == expected[ranking[c]]
    ]
    assert any(expected[ranking[0]] > expected[ranking[c - 1]] for c in cuts), (
        "a cut inside a tie group that has strictly better tickets above it"
    )
    assert len(ranking) in counts
    for count in counts:
        indices = repair.top_ticket_indices(scores.marginals, universe.tickets, count)
        assert [universe.ticket_at(int(i)) for i in indices] == ranking[:count]
    for position, ticket in enumerate(ranking, start=1):
        index = universe.index_of(ticket)
        assert repair.exact_global_rank(scores.marginals, universe.tickets, index) == position
    top = repair.global_top(universe, scores, 7)
    assert [entry.ticket for entry in top] == ranking[:7]
    assert [entry.rank for entry in top] == list(range(1, 8))
    assert [entry.marginal for entry in top] == [expected[t] for t in ranking[:7]]
    assert repair.ranked(universe, scores, ranking[20]).rank == 21


def test_top_selection_rejects_impossible_counts() -> None:
    universe = repair.build_universe(8)
    scores = repair.score_all_tickets(universe, ())
    for bad in (0, -1, universe.tickets.shape[0] + 1):
        with pytest.raises(ValueError, match="count"):
            repair.top_ticket_indices(scores.marginals, universe.tickets, bad)


def test_ties_are_broken_by_the_lexicographically_lowest_ticket() -> None:
    universe = repair.build_universe(9)
    scores = repair.score_all_tickets(universe, ())
    assert len(set(scores.marginals.tolist())) == 1, "an empty R makes every ticket tie"
    top = repair.global_top(universe, scores, 5)
    assert [entry.ticket for entry in top] == list(
        itertools.islice(itertools.combinations(range(1, 10), 6), 5)
    )


# ------------------------------------------------------------------ repair pool


def _toy_setup(
    seed: int,
) -> tuple[
    repair.ColexUniverse,
    repair.GlobalScores,
    five.Portfolio,
    five.DestroyedPortfolio,
    random.Random,
    list[five.Ticket],
]:
    rng = random.Random(seed)
    geometry = five.Geometry(13, 6, 3)
    universe = repair.build_universe(13)
    every = list(itertools.combinations(range(1, 14), 6))
    start = five.normalize_portfolio(rng.sample(every, 5), geometry=geometry)
    destroyed = five.destroy_positions(start, sorted(rng.sample(range(5), 3)))
    scores = repair.score_all_tickets(universe, destroyed.remaining)
    return universe, scores, start, destroyed, rng, every


def test_pool_keeps_groups_in_order_and_the_cap_drops_only_the_tail_of_the_global_group() -> None:
    universe, scores, start, destroyed, rng, every = _toy_setup(1)
    outsiders = [t for t in every if t not in set(start)]
    extra: five.Portfolio = tuple(sorted(rng.sample(outsiders, 2)))
    elites = [start, extra]
    full = repair.assemble_global_pool(
        universe, scores, destroyed, elites=elites, top_count=8, pool_max=64
    )
    frozen = set(destroyed.remaining)
    removed = list(destroyed.removed)
    ordered: list[five.Ticket] = []
    for ticket in (*removed, *sorted(set(extra)), *(e.ticket for e in full.top)):
        if ticket not in frozen and ticket not in ordered:
            ordered.append(ticket)
    assert full.union_size == len(full.members) == len(ordered)
    assert not full.dropped
    capped = repair.assemble_global_pool(
        universe, scores, destroyed, elites=elites, top_count=8, pool_max=7
    )
    assert capped.union_size == len(ordered) > 7
    assert set(capped.tickets) == set(ordered[:7])
    assert capped.dropped == tuple(ordered[7:])
    sources = {member.ticket: member.source for member in capped.members}
    assert all(sources[t] == repair.SOURCE_REMOVED for t in removed)
    assert all(sources[t] == repair.SOURCE_ELITE for t in extra if t in sources)
    assert set(removed) | set(extra) <= set(capped.tickets), "A and B are never cut before C"
    assert capped.tickets == tuple(sorted(capped.tickets))
    assert set(capped.tickets).isdisjoint(frozen)


def test_a_removed_ticket_that_is_also_globally_top_ranked_appears_once_as_removed() -> None:
    rng = random.Random(3)
    universe = repair.build_universe(13)
    every = list(itertools.combinations(range(1, 14), 6))
    frozen: five.Portfolio = tuple(sorted(rng.sample(every, 5)))
    scores = repair.score_all_tickets(universe, frozen)
    best = repair.global_top(universe, scores, 8)[0]
    others = [t for t in every if t not in set(frozen) and t != best.ticket]
    removed: five.Portfolio = tuple(sorted((best.ticket, *rng.sample(others, 2))))
    destroyed = five.DestroyedPortfolio(positions=(0, 1, 2), remaining=frozen, removed=removed)
    plan = repair.assemble_global_pool(
        universe, scores, destroyed, elites=[(*frozen, *removed)], top_count=8, pool_max=64
    )
    member = {m.ticket: m for m in plan.members}[best.ticket]
    assert (member.source, member.in_global_top, member.global_rank) == (
        repair.SOURCE_REMOVED,
        True,
        1,
    )
    assert plan.tickets.count(best.ticket) == 1
    assert plan.union_size == len(plan.members) < 3 + 8


def test_a_frozen_ticket_never_joins_the_pool_even_when_it_ties_into_the_global_top() -> None:
    universe = repair.build_universe(9)
    every = list(itertools.combinations(range(1, 10), 6))
    frozen: five.Portfolio = tuple(every[:70])
    scores = repair.score_all_tickets(universe, frozen)
    top = repair.global_top(universe, scores, 48)
    assert any(entry.ticket in set(frozen) for entry in top), "zero-marginal frozen tickets rank"
    removed: five.Portfolio = tuple(every[70:72])
    destroyed = five.DestroyedPortfolio(positions=(0, 1), remaining=frozen, removed=removed)
    plan = repair.assemble_global_pool(
        universe, scores, destroyed, elites=[(*frozen, *removed)], top_count=48
    )
    assert set(plan.tickets).isdisjoint(frozen)
    assert set(plan.tickets) <= set(every[70:])
    assert set(removed) <= set(plan.tickets)


def test_pair_links_are_symmetric_and_equal_the_definition() -> None:
    rng = random.Random(21)
    every = list(itertools.combinations(range(1, 14), 6))
    remaining = tuple(rng.sample(every, 5))
    links = repair.build_pair_links(remaining, 13)
    triples = {triple for ticket in remaining for triple in itertools.combinations(ticket, 3)}
    for a in range(1, 14):
        for b in range(1, 14):
            expected = 0
            if a != b:
                for x in range(1, 14):
                    if x not in (a, b) and tuple(sorted((a, b, x))) in triples:
                        expected |= 1 << (x - 1)
            assert int(links[a - 1, b - 1]) == expected
    assert repair.build_pair_links((), 13).sum() == 0


# ------------------------------------------------------------------ histogram over 64 tickets


def test_histogram_takes_64_tickets_reads_the_top_bit_and_rejects_65_or_none() -> None:
    geometry = five.Geometry(13, 6, 3)
    universe = repair.build_universe(13)
    tickets = list(itertools.combinations(range(1, 14), 6))
    remaining = tuple(tickets[:3])
    pool = tuple(tickets[3:67])
    assert len(pool) == 64 == repair.REPAIR_POOL_MAX
    histogram = repair.build_repair_histogram(remaining, pool, geometry=geometry)
    scores = repair.score_all_tickets(universe, remaining)
    assert histogram.residual_subsets == comb(13, 7) - histogram.covered_by_remaining
    for index in (0, 1, 31, 32, 62, 63):
        expected = int(scores.marginals[universe.index_of(pool[index])])
        assert histogram.subset_value([index]) == expected
    assert int(np.bitwise_count(histogram.masks >> np.uint64(63)).sum()) > 0, "bit 63 is used"
    with pytest.raises(ValueError, match="between 1 and 64"):
        repair.build_repair_histogram(remaining, tickets[3:68], geometry=geometry)
    with pytest.raises(ValueError, match="between 1 and 64"):
        repair.build_repair_histogram(remaining, (), geometry=geometry)


# ------------------------------------------------------------------ exact solver


@pytest.mark.parametrize("use_bound", [True, False])
def test_solver_equals_brute_force_optimal_sets_and_accounts_for_every_set(
    use_bound: bool,
) -> None:
    generator = np.random.default_rng(7)
    ties_seen = 0
    for _ in range(80):
        pool = int(generator.integers(5, 14))
        pick = int(generator.integers(1, min(6, pool) + 1))
        masks, weights = _instance(generator, pool, int(generator.integers(4, 60)))
        values = {
            chosen: five.evaluate_set(masks, weights, chosen)
            for chosen in itertools.combinations(range(pool), pick)
        }
        best = max(values.values())
        optimal = sorted((c for c, v in values.items() if v == best), key=_sha_key)
        ties_seen += len(optimal) > 1
        start = tuple(sorted(int(i) for i in generator.choice(pool, size=pick, replace=False)))
        result = repair.solve_pool_exact(
            masks, weights, pool, pick, start, _sha_key, use_bound=use_bound
        )
        assert result.status == five.OPTIMALITY_PROVEN
        assert result.best_value == best
        assert list(result.optimal_sets) == optimal
        assert result.best_set == optimal[0]
        assert result.leaf_sets_evaluated + result.sets_pruned == comb(pool, pick)
        assert result.unresolved_sets == 0 and result.total_sets == comb(pool, pick)
        assert result.improved == (best > result.start_value)
    assert ties_seen > 5, "the instances must contain exact ties"


def test_solver_keeps_every_tied_set_and_refuses_to_truncate_them() -> None:
    # columns 0 and 1 win exactly the same rows, so {0, 2} and {1, 2} tie for the optimum
    masks = np.array([0b000011, 0b000100, 0b001000, 0b010000, 0b100000], dtype=np.uint64)
    weights = np.array([10, 5, 4, 3, 2], dtype=np.int64)
    result = repair.solve_pool_exact(masks, weights, 6, 2, (4, 5), _sha_key)
    assert result.best_value == 15
    assert set(result.optimal_sets) == {(0, 2), (1, 2)}
    assert list(result.optimal_sets) == sorted(result.optimal_sets, key=_sha_key)
    with pytest.raises(repair.TieLimitExceededError):
        repair.solve_pool_exact(masks, weights, 6, 2, (4, 5), _sha_key, tie_limit=1)


def test_solver_handles_a_64_ticket_pool_and_its_top_bit() -> None:
    generator = np.random.default_rng(11)
    masks, weights = _instance(generator, 64, 300)
    assert int(np.count_nonzero((masks >> np.uint64(63)) & np.uint64(1))) > 0
    values = {c: five.evaluate_set(masks, weights, c) for c in itertools.combinations(range(64), 2)}
    best = max(values.values())
    optimal = sorted((c for c, v in values.items() if v == best), key=_sha_key)
    result = repair.solve_pool_exact(masks, weights, 64, 2, (0, 1), _sha_key)
    assert result.status == five.OPTIMALITY_PROVEN
    assert result.best_value == best
    assert list(result.optimal_sets) == optimal
    assert result.leaf_sets_evaluated + result.sets_pruned == comb(64, 2)


def test_expired_deadline_reports_feasible_only_and_never_proven() -> None:
    generator = np.random.default_rng(5)
    masks, weights = _instance(generator, 12, 60)
    result = repair.solve_pool_exact(
        masks, weights, 12, 4, (0, 1, 2, 3), _sha_key, deadline=-1.0, clock=lambda: 0.0
    )
    assert result.status == five.OPTIMALITY_FEASIBLE
    assert result.unresolved_sets > 0
    assert result.best_set == (0, 1, 2, 3)
    assert result.best_value == result.start_value


def test_an_unsafe_bound_is_caught_by_the_brute_force_comparison(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = repair.remaining_slot_upper_bound

    def unsafe(gains: npt.NDArray[np.float64], slots: int) -> int:
        return original(gains, slots) // 3

    monkeypatch.setattr(repair, "remaining_slot_upper_bound", unsafe)
    generator = np.random.default_rng(5)
    caught = 0
    for _ in range(60):
        pool = int(generator.integers(6, 13))
        pick = int(generator.integers(3, min(6, pool)))
        masks, weights = _instance(generator, pool, int(generator.integers(5, 60)))
        best = max(
            five.evaluate_set(masks, weights, c) for c in itertools.combinations(range(pool), pick)
        )
        start = tuple(sorted(int(i) for i in generator.choice(pool, size=pick, replace=False)))
        try:
            result = repair.solve_pool_exact(masks, weights, pool, pick, start, _sha_key)
        except AssertionError:
            # the search pruned the incumbent's own branch: the internal invariant caught it
            caught += 1
            continue
        caught += result.best_value != best
    assert caught > 0


def test_solver_value_equals_the_reused_five_ticket_solver() -> None:
    generator = np.random.default_rng(9)
    for _ in range(40):
        pool = int(generator.integers(6, 20))
        pick = int(generator.integers(2, min(6, pool)))
        masks, weights = _instance(generator, pool, int(generator.integers(10, 120)))
        start = tuple(sorted(int(i) for i in generator.choice(pool, size=pick, replace=False)))
        reused = five.solve_exact_repair(masks, weights, pool, pick, start)
        mine = repair.solve_pool_exact(masks, weights, pool, pick, start, _sha_key)
        assert reused.status == mine.status == five.OPTIMALITY_PROVEN
        assert reused.best_value == mine.best_value


def test_solver_rejects_invalid_pools_and_start_sets() -> None:
    masks = np.array([1, 2, 3], dtype=np.uint64)
    weights = np.array([1, 1, 1], dtype=np.int64)
    for pool, pick, start in [(65, 2, (0, 1)), (4, 0, ()), (4, 5, (0, 1, 2, 3, 3)), (4, 2, (1, 1))]:
        with pytest.raises(ValueError, match="invalid"):
            repair.solve_pool_exact(masks, weights, pool, pick, start, _sha_key)


# ------------------------------------------------------------------ toy driver end to end

TOY = five.Geometry(25, 6, 3)


def _toy_driver_case(seed: int) -> tuple[five.Portfolio, tuple[int, ...]]:
    rng = random.Random(seed)
    every = list(itertools.combinations(range(1, 26), 6))
    start = five.normalize_portfolio(rng.sample(every, 20), geometry=TOY)
    return start, tuple(sorted(rng.sample(range(20), 3)))


def test_toy_driver_equals_a_canonical_brute_force_over_its_pool() -> None:
    universe = repair.build_universe(25)
    recounter = five.CanonicalRecounter(TOY)
    start, positions = _toy_driver_case(4)
    result = repair.repair_destroy_set(
        universe,
        start,
        positions,
        elites=[start],
        recounter=recounter,
        expected_start_count=recounter.count(start),
        compare_local=False,
        geometry=TOY,
    )
    pool, remaining = result.plan.tickets, result.destroyed.remaining
    histogram = repair.build_repair_histogram(remaining, pool, geometry=TOY)
    values = {
        chosen: five.evaluate_set(histogram.masks, histogram.weights, chosen)
        for chosen in itertools.combinations(range(len(pool)), 3)
    }
    best = max(values.values())
    assert histogram.masks.size > 0 and len(set(values.values())) > 1, "non-degenerate residual"
    assert result.solve.status == five.OPTIMALITY_PROVEN
    assert result.solve.best_value == best
    assert set(result.solve.optimal_sets) == {c for c, v in values.items() if v == best}
    assert result.best_count == histogram.outcome_count(result.solve.best_set)
    assert result.canonical_recounts == result.optimal_counts
    assert recounter.count(result.best_portfolio) == result.best_count
    assert result.solve.leaf_sets_evaluated + result.solve.sets_pruned == comb(len(pool), 3)
    sampled = random.Random(0).sample(sorted(values), 25)
    for chosen in sampled:
        portfolio = five.normalize_portfolio((*remaining, *(pool[i] for i in chosen)), geometry=TOY)
        assert histogram.outcome_count(chosen) == recounter.count(portfolio)


def test_toy_driver_guards_fire_on_a_wrong_baseline_or_a_wrong_recount() -> None:
    class InflatingRecounter(five.CanonicalRecounter):
        def count(self, portfolio: Sequence[five.Ticket]) -> int:
            return super().count(portfolio) + (7 if len(portfolio) == 20 else 0)

    universe = repair.build_universe(25)
    start, positions = _toy_driver_case(4)
    exact = five.CanonicalRecounter(TOY)
    with pytest.raises(repair.StopConditionError) as baseline:
        repair.repair_destroy_set(
            universe,
            start,
            positions,
            elites=[start],
            recounter=exact,
            expected_start_count=exact.count(start) + 7,
            compare_local=False,
            geometry=TOY,
        )
    assert baseline.value.code == "START_BASELINE_MISMATCH"
    with pytest.raises(repair.StopConditionError) as refuted:
        repair.repair_destroy_set(
            universe,
            start,
            positions,
            elites=[start],
            recounter=InflatingRecounter(TOY),
            expected_start_count=exact.count(start),
            compare_local=False,
            geometry=TOY,
        )
    assert refuted.value.code == "REPAIR_SOLVER_CORRECTNESS_REFUTED"


def test_the_inspect_hook_sees_the_scored_universe_the_pool_and_the_histogram() -> None:
    universe = repair.build_universe(25)
    recounter = five.CanonicalRecounter(TOY)
    start, positions = _toy_driver_case(6)
    seen: list[tuple[int, int, int]] = []

    def hook(
        _: repair.ColexUniverse,
        scores: repair.GlobalScores,
        plan: repair.GlobalPoolPlan,
        histogram: five.PoolHistogram,
    ) -> None:
        seen.append((scores.tickets_scored, len(plan.members), len(histogram.pool)))

    result = repair.repair_destroy_set(
        universe,
        start,
        positions,
        elites=[start],
        recounter=recounter,
        expected_start_count=recounter.count(start),
        compare_local=False,
        geometry=TOY,
        inspect=hook,
    )
    assert seen == [(comb(25, 6), len(result.plan.members), len(result.plan.members))]


def test_toy_parity_family_has_zero_mismatches_and_every_family_ran() -> None:
    report = repair.run_toy_parity()
    assert report.mismatches == 0
    families = cast(dict[str, dict[str, int]], report.detail["FAMILIES"])
    assert len(families) >= 10
    assert all(entry["COMPARISONS"] > 0 and entry["MISMATCHES"] == 0 for entry in families.values())


# ------------------------------------------------------------------ real 49/6 space (dev sets)


@pytest.fixture(scope="module")
def dev4(
    universe49: repair.ColexUniverse, recounter: five.CanonicalRecounter
) -> repair.DestroySetRepair:
    return repair.repair_destroy_set(
        universe49, five.START_PORTFOLIO, DEV4, elites=_elites(), recounter=recounter
    )


@pytest.fixture(scope="module")
def dev5(
    universe49: repair.ColexUniverse, recounter: five.CanonicalRecounter
) -> repair.DestroySetRepair:
    return repair.repair_destroy_set(
        universe49, five.START_PORTFOLIO, DEV5, elites=_elites(), recounter=recounter
    )


def test_real_scoring_is_complete_and_both_global_identities_hold(
    dev4: repair.DestroySetRepair,
) -> None:
    assert dev4.identities["PASS"] is True
    assert dev4.identities["TICKETS_SCORED"] == 13_983_816
    assert dev4.remaining_count == 260_837_584
    assert dev4.residual_subsets == 48_638_072 == comb(49, 7) - dev4.remaining_count // 7


def test_real_pool_composition_cap_and_legality(dev4: repair.DestroySetRepair) -> None:
    plan = dev4.plan
    frozen = set(dev4.destroyed.remaining)
    assert [entry.rank for entry in plan.top] == list(range(1, 49))
    assert [entry.marginal for entry in plan.top] == sorted(
        (entry.marginal for entry in plan.top), reverse=True
    )
    assert plan.tickets == tuple(sorted(plan.tickets))
    assert len(set(plan.tickets)) == len(plan.tickets) <= repair.REPAIR_POOL_MAX
    assert set(plan.tickets).isdisjoint(frozen)
    assert set(dev4.destroyed.removed) <= set(plan.tickets)
    assert plan.source_counts() == {"A_REMOVED": 4, "B_ELITE": 8, "C_GLOBAL": 48}
    elite_union = {t for pin in five.PINNED_ELITES for t in pin.tickets}
    extras = elite_union - frozen - set(dev4.destroyed.removed)
    assert {m.ticket for m in plan.members if m.source == repair.SOURCE_ELITE} == extras
    top_tickets = {entry.ticket for entry in plan.top}
    assert {m.ticket for m in plan.members if m.source == repair.SOURCE_GLOBAL} <= top_tickets
    assert all(m.in_global_top == (m.ticket in top_tickets) for m in plan.members)
    assert not plan.dropped and plan.union_size == len(plan.members)


def test_real_global_marginals_equal_the_canonical_evaluator(
    universe49: repair.ColexUniverse,
    recounter: five.CanonicalRecounter,
    dev4: repair.DestroySetRepair,
) -> None:
    remaining = dev4.destroyed.remaining
    scores = repair.score_all_tickets(universe49, remaining)
    assert scores.tickets_scored == repair.TOTAL_TICKETS
    repair.check_score_identities(scores, universe49, dev4.residual_subsets)
    assert repair.global_top(universe49, scores) == dev4.plan.top
    base = recounter.count(remaining)
    probes = [
        *dev4.destroyed.removed,
        dev4.plan.top[0].ticket,
        dev4.plan.top[-1].ticket,
        remaining[0],
        (1, 2, 3, 4, 5, 6),
        (44, 45, 46, 47, 48, 49),
    ]
    for ticket in probes:
        expected = recounter.count((*remaining, ticket)) - base
        assert 7 * int(scores.marginals[universe49.index_of(ticket)]) == expected
    assert int(scores.marginals[universe49.index_of(remaining[0])]) == 0


def test_real_solve_is_proven_fully_accounted_recounted_and_a_legal_portfolio(
    dev4: repair.DestroySetRepair,
) -> None:
    solve = dev4.solve
    assert solve.status == five.OPTIMALITY_PROVEN
    assert solve.total_sets == comb(len(dev4.plan.members), 4)
    assert solve.leaf_sets_evaluated + solve.sets_pruned == solve.total_sets
    assert solve.unresolved_sets == 0
    assert dev4.canonical_recounts == dev4.optimal_counts
    assert len(dev4.best_portfolio) == 20 == len(set(dev4.best_portfolio))
    assert set(dev4.destroyed.remaining) <= set(dev4.best_portfolio)
    shas = [five.portfolio_sha256(p) for p in dev4.optimal_portfolios]
    assert shas == sorted(shas)
    assert dev4.best_portfolio == dev4.optimal_portfolios[0]
    # regression pin: the removed set is the pool optimum of this dev set
    assert dev4.best_count == five.START_COUNT == dev4.start_outcomes
    assert dev4.best_delta == 0 and dev4.new_tickets == ()


def test_real_tied_optima_form_a_plateau_of_equal_count_portfolios(
    dev5: repair.DestroySetRepair,
) -> None:
    assert dev5.solve.status == five.OPTIMALITY_PROVEN
    assert len(dev5.solve.optimal_sets) == 16  # regression pin
    shas = [five.portfolio_sha256(p) for p in dev5.optimal_portfolios]
    assert shas == sorted(shas) and len(set(shas)) == 16
    assert set(dev5.canonical_recounts) == {five.START_COUNT} == set(dev5.optimal_counts)
    assert dev5.best_portfolio == dev5.optimal_portfolios[0]
    for portfolio in dev5.optimal_portfolios:
        assert len(portfolio) == 20 == len(set(portfolio))
        assert set(dev5.destroyed.remaining) <= set(portfolio)
    assert dev5.best_delta == 0
    assert len(dev5.optimum_members) == 5


def test_real_local_pool_comparison_is_consistent_with_the_reused_generator(
    dev4: repair.DestroySetRepair,
) -> None:
    local = dev4.local
    assert local is not None
    assert local.local_pool_size == local.marginals_cross_checked == 48
    assert local.top_in_local + len(local.top_not_in_local) == 48
    assert sum(local.top_distance_histogram.values()) == 48
    assert local.top_beyond_two_numbers == sum(
        count for distance, count in local.top_distance_histogram.items() if distance > 2
    )
    old = five.assemble_pool(five.START_PORTFOLIO, DEV4, elites=_elites())
    outside = {entry.ticket for entry in local.top_not_in_local}
    assert outside == {entry.ticket for entry in dev4.plan.top} - set(old.tickets)
    assert local.local_best_global_rank >= 1


# ------------------------------------------------------------------ result document


def _document(
    repairs: Sequence[repair.PilotRepair],
    sets: dict[int, tuple[tuple[int, ...], ...]] | None = None,
) -> dict[str, object]:
    return repair.build_result_document(
        sets=sets or {4: (DEV4,), 5: (DEV5,)},
        sample_sha256="0" * 64,
        sample_persisted_at="2026-09-30T00:00:00Z",
        sample_persisted_before_scoring=True,
        start_record={"MATCH": True},
        pins=[{"NAME": "X"}],
        parity={"PARITY_SAMPLE_COUNT": 10, "PARITY_MISMATCHES": 0},
        repairs=repairs,
        wall_seconds=1.0,
        peak_memory=2,
        peak_memory_after_first_set=1,
        run_identity={"RUN_HEAD": "h", "RUN_TREE": "t"},
        module_sha256="m",
        phase_seconds={"PILOT": 1.0},
        thread_env={"OMP_NUM_THREADS": "1"},
    )


def test_result_document_reports_no_improvement_and_exact_totals(
    dev4: repair.DestroySetRepair, dev5: repair.DestroySetRepair
) -> None:
    document = _document([(4, DEV4, dev4), (5, DEV5, dev5)])
    assert document["SCIENTIFIC_RESULT"] == repair.RESULT_NO_IMPROVEMENT
    assert document["NEW_STABLE_NON_LANE3_GAIN"] == "NO"
    assert document["BEST_COUNT"] == five.START_COUNT and document["BEST_DELTA"] == 0
    shas = sorted(five.portfolio_sha256(p) for r in (dev4, dev5) for p in r.optimal_portfolios)
    assert document["BEST_SHA256"] == shas[0]
    assert document["BEST_COUNT_TIE_COUNT"] == len(shas) == 17
    assert document["BEST_IS_START_PORTFOLIO"] == (shas[0] == five.START_SHA256)
    assert document["BEST_CANONICAL_RECOUNT_STATUS"] == "PASS"
    assert document["BEST_COUNT_TIES_ALL_CANONICALLY_RECOUNTED"] is True
    assert document["PROVEN_OPTIMAL_REPAIR_SETS"] == 2
    assert document["FEASIBLE_ONLY_REPAIR_SETS"] == 0
    assert document["DESTROY4_SETS_TESTED"] == document["DESTROY5_SETS_TESTED"] == 1
    assert document["GLOBAL_ENUMERATION_COMPLETE_SETS"] == 2
    assert document["GLOBAL_TICKET_UNIVERSE_SIZE"] == 13_983_816
    assert document["NODES_EXPLORED"] == dev4.solve.nodes_explored + dev5.solve.nodes_explored
    assert document["LEAVES_SCORED"] == (
        dev4.solve.leaf_sets_evaluated + dev5.solve.leaf_sets_evaluated
    )
    for key in ("COMPLETE_N4_OPTIMUM", "COMPLETE_N5_OPTIMUM", "GLOBAL_K20_OPTIMUM"):
        assert document[key] == "NOT_CLAIMED"
    assert document["GAIN_VS_PROTECTED_LANE_3"] == "NOT_EVALUATED"
    assert document["PROTECTED_LANE_3_TOUCHED"] == "NO"
    outside = document["GLOBAL_TOP48_NOT_IN_LOCAL_MUTATION_POOL"]
    assert isinstance(outside, dict)
    assert dev4.local is not None and dev5.local is not None
    assert outside["TOTAL"] == len(dev4.local.top_not_in_local) + len(dev5.local.top_not_in_local)
    assert json.loads(five.canonical_json(document)) == json.loads(five.canonical_json(document))


def test_an_improvement_is_reported_only_with_a_matching_canonical_recount(
    dev4: repair.DestroySetRepair, dev5: repair.DestroySetRepair
) -> None:
    better = five.START_COUNT + 7
    count = len(dev5.optimal_portfolios)
    improved = dataclasses.replace(
        dev5, optimal_counts=(better,) * count, canonical_recounts=(better,) * count
    )
    document = _document([(4, DEV4, dev4), (5, DEV5, improved)])
    assert document["SCIENTIFIC_RESULT"] == repair.RESULT_IMPROVED
    assert document["NEW_STABLE_NON_LANE3_GAIN"] == "YES"
    assert document["BEST_COUNT"] == better and document["BEST_DELTA"] == 7
    assert document["BEST_DESTROY_SIZE"] == 5 and document["BEST_DESTROY_INDICES"] == list(DEV5)
    assert document["BEST_COUNT_TIE_COUNT"] == count
    wrong_best = dataclasses.replace(
        dev5, optimal_counts=(better,) * count, canonical_recounts=(better + 1,) * count
    )
    one_wrong_tie = dataclasses.replace(
        dev5,
        optimal_counts=(better,) * count,
        canonical_recounts=(better,) * (count - 1) + (better + 1,),
    )
    for broken in (wrong_best, one_wrong_tie):
        document = _document([(4, DEV4, dev4), (5, DEV5, broken)])
        assert document["SCIENTIFIC_RESULT"] == repair.RESULT_NO_IMPROVEMENT
        assert document["NEW_STABLE_NON_LANE3_GAIN"] == "NO"
        assert document["BEST_CANONICAL_RECOUNT_STATUS"] == "FAIL"


def test_result_document_needs_exactly_one_repair_per_pilot_set(
    dev4: repair.DestroySetRepair,
) -> None:
    with pytest.raises(ValueError, match="exactly one"):
        _document([(4, DEV4, dev4)])


# ------------------------------------------------------------------ runner and command line


def test_pilot_refuses_to_overwrite_and_persists_nothing_when_it_refuses(tmp_path: Path) -> None:
    output = tmp_path / "result.json"
    output.write_text("{}", encoding="utf-8")
    with pytest.raises(FileExistsError):
        repair.run_pilot(tmp_path / "work", output)
    assert not (tmp_path / "work").exists()


def test_pilot_stops_before_scoring_when_parity_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not _source_commit_available():
        pytest.skip("source commit is not available in this clone")

    def failing_parity(*_: object) -> dict[str, object]:
        return {
            "PARITY_SAMPLE_COUNT": 1,
            "PARITY_MISMATCHES": 1,
            "COVERAGE_MEETS_PACKET_MINIMUMS": True,
        }

    def forbidden(*_: object, **__: object) -> None:
        raise AssertionError("a destroy set was scored although parity failed")

    monkeypatch.setattr(repair, "run_parity", failing_parity)
    monkeypatch.setattr(repair, "repair_destroy_set", forbidden)
    output = tmp_path / "result.json"
    with pytest.raises(repair.StopConditionError) as stop:
        repair.run_pilot(tmp_path / "work", output)
    assert stop.value.code == "PARITY_MISMATCH"
    assert not output.exists()
    assert (tmp_path / "work" / "destroy-samples.json").exists(), "sets persist before parity"


def test_command_line_reports_a_stop_condition_with_exit_code_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    def stop(*_: object) -> dict[str, object]:
        raise repair.StopConditionError("PARITY_MISMATCH", "toy")

    monkeypatch.setattr(repair, "run_pilot", stop)
    code = repair.main(["pilot", "--workdir", str(tmp_path), "--output", str(tmp_path / "o.json")])
    assert code == 2
    assert "STOP: PARITY_MISMATCH: toy" in capsys.readouterr().err


def test_parity_command_exit_code_follows_the_mismatch_count(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    original = repair.build_universe
    monkeypatch.setattr(repair, "build_universe", lambda: original(8))
    for mismatches, expected in ((0, 0), (2, 1)):

        def fake_parity(*_: object, count: int = mismatches) -> dict[str, object]:
            return {"PARITY_MISMATCHES": count}

        monkeypatch.setattr(repair, "run_parity", fake_parity)
        assert repair.main(["parity"]) == expected
        capsys.readouterr()


# ------------------------------------------------------------------ committed result artifact


def test_result_artifact_is_self_consistent() -> None:
    document = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    module_bytes = (repair.REPO_ROOT / repair.MODULE_RELATIVE_PATH).read_bytes()
    assert document["TASK_ID"] == repair.TASK_ID
    assert document["TASK_STATUS"] == "COMPLETE"
    assert document["RESULT_LOCATOR"] == repair.RESULT_RELATIVE_PATH
    assert document["SOURCE_MODULE_PATH"] == repair.MODULE_RELATIVE_PATH
    assert document["SOURCE_MODULE_SHA256"] == hashlib.sha256(module_bytes).hexdigest()

    start = tuple(tuple(t) for t in document["START_PORTFOLIO"])
    assert start == five.START_PORTFOLIO
    assert document["START_COUNT"] == five.START_COUNT == 313239661
    assert document["START_SHA256"] == five.START_SHA256 == five.portfolio_sha256(start)
    assert document["START_REPRODUCTION"]["MATCH"] is True
    assert document["START_REPRODUCTION"]["CANONICAL_RECOUNT"] == five.START_COUNT

    pilot = repair.pilot_destroy_sets()
    assert document["PILOT_SEED"] == repair.PILOT_SEED == 20261002
    assert [tuple(p) for p in document["DESTROY4_SETS"]] == list(pilot[4])
    assert [tuple(p) for p in document["DESTROY5_SETS"]] == list(pilot[5])
    assert document["SAMPLE_PERSISTED_BEFORE_SCORING"] is True
    assert document["DESTROY4_SETS_TESTED"] == document["DESTROY5_SETS_TESTED"] == 3
    records = document["PER_DESTROY_SET"]
    assert [(r["DESTROY_SIZE"], tuple(r["POSITIONS"])) for r in records] == [
        *((4, p) for p in pilot[4]),
        *((5, p) for p in pilot[5]),
    ]
    assert document["GLOBAL_TICKET_UNIVERSE_SIZE"] == 13_983_816
    assert document["GLOBAL_ENUMERATION_COMPLETE_SETS"] == len(records) == 6
    assert document["GLOBAL_TOP_MARGINAL"] == 48 and document["REPAIR_POOL_MAX"] == 64

    for record in records:
        size = record["DESTROY_SIZE"]
        destroyed = five.destroy_positions(five.START_PORTFOLIO, record["POSITIONS"])
        pool: list[five.Ticket] = [
            tuple(int(n) for n in member["TICKET"]) for member in record["POOL"]
        ]
        assert record["POOL_SIZE"] == len(pool) <= repair.REPAIR_POOL_MAX
        assert pool == sorted(pool) and len(set(pool)) == len(pool)
        assert set(pool).isdisjoint(destroyed.remaining)
        assert set(destroyed.removed) <= set(pool)
        assert [tuple(t) for t in record["REMOVED_TICKETS"]] == list(destroyed.removed)
        assert sum(record["POOL_SOURCE_COUNTS"].values()) == record["POOL_SIZE"]
        dropped = len(record["POOL_DROPPED_BY_CAP"])
        assert record["POOL_UNION_SIZE_BEFORE_CAP"] == record["POOL_SIZE"] + dropped
        assert record["GLOBAL_ENUMERATION_COMPLETE"] == "YES"
        assert record["TICKETS_SCORED"] == 13_983_816
        identities = record["GLOBAL_IDENTITIES"]
        assert identities["PASS"] is True
        assert identities["TICKETS_SCORED"] == identities["TICKETS_EXPECTED"] == 13_983_816
        assert identities["RESIDUAL_SUBSETS"] == record["RESIDUAL_SUBSETS"]
        assert 7 * (comb(49, 7) - record["RESIDUAL_SUBSETS"]) == record["OUTCOMES_WON_BY_FROZEN_R"]

        top = record["GLOBAL_TOP"]
        assert len(top) == record["GLOBAL_TOP_MARGINAL"] == 48
        assert [entry["RANK"] for entry in top] == list(range(1, 49))
        for above, below in itertools.pairwise(top):
            ordered = above["RESIDUAL_MARGINAL_OUTCOMES"] > below["RESIDUAL_MARGINAL_OUTCOMES"]
            tied_in_order = above["RESIDUAL_MARGINAL_OUTCOMES"] == below[
                "RESIDUAL_MARGINAL_OUTCOMES"
            ] and tuple(above["TICKET"]) < tuple(below["TICKET"])
            assert ordered or tied_in_order
        assert all(
            entry["IN_REPAIR_POOL"] == (tuple(entry["TICKET"]) in set(pool)) for entry in top
        )

        assert record["TOTAL_SETS"] == comb(record["POOL_SIZE"], size)
        accounted = record["LEAVES_SCORED"] + record["SETS_ELIMINATED_BY_BOUND"]
        assert accounted + record["UNRESOLVED_SETS"] == record["TOTAL_SETS"]
        assert record["POOL_OPTIMALITY_STATUS"] in {
            five.OPTIMALITY_PROVEN,
            five.OPTIMALITY_FEASIBLE,
        }
        if record["POOL_OPTIMALITY_STATUS"] == five.OPTIMALITY_PROVEN:
            assert record["UNRESOLVED_SETS"] == 0
        assert record["OPTIMAL_SETS_CANONICAL_MATCH"] is True
        assert record["BEST_DELTA"] == record["BEST_COUNT"] - five.START_COUNT >= 0
        assert record["IMPROVED"] == (record["BEST_COUNT"] > five.START_COUNT)
        chosen: list[int] = [int(index) for index in record["BEST_POOL_INDICES"]]
        assert len(chosen) == len(set(chosen)) == size
        assert all(0 <= index < len(pool) for index in chosen)
        optimum = record["OPTIMUM_TICKETS"]
        assert [tuple(t["TICKET"]) for t in optimum] == [pool[i] for i in chosen]
        ranks = [t["GLOBAL_RANK"] for t in optimum]
        assert record["BEST_GLOBAL_TICKET_RANK_USED_BY_OPTIMUM"] == min(ranks)
        assert record["WORST_GLOBAL_TICKET_RANK_USED_BY_OPTIMUM"] == max(ranks)
        assert record["GLOBAL_TOP48_TICKETS_USED_BY_OPTIMUM"] == sum(
            1 for t in optimum if t["IN_GLOBAL_TOP48"]
        )
        best = five.normalize_portfolio((*destroyed.remaining, *(pool[i] for i in chosen)))
        assert five.portfolio_sha256(best) == record["BEST_PORTFOLIO_SHA256"]
        outside = record["GLOBAL_TOP48_NOT_IN_LOCAL_MUTATION_POOL"]
        assert outside == len(record["GLOBAL_TOP48_NOT_IN_LOCAL_MUTATION_POOL_TICKETS"])
        assert outside + record["GLOBAL_TOP48_IN_LOCAL_MUTATION_POOL"] == 48
        assert record["LOCAL_POOL_MARGINALS_CROSS_CHECKED"] == record["LOCAL_MUTATION_POOL_SIZE"]

    sizes = [record["POOL_SIZE"] for record in records]
    assert document["REPAIR_POOL_SIZE_MIN"] == min(sizes)
    assert document["REPAIR_POOL_SIZE_MAX"] == max(sizes)
    assert document["REPAIR_POOL_SIZE_MEAN"] == round(sum(sizes) / len(sizes), 3)
    seconds = [record["SECONDS"]["SCORE"] for record in records]
    assert abs(document["GLOBAL_ENUMERATION_WALL_SECONDS_MIN"] - min(seconds)) < 0.002
    assert abs(document["GLOBAL_ENUMERATION_WALL_SECONDS_MAX"] - max(seconds)) < 0.002
    assert abs(document["GLOBAL_ENUMERATION_WALL_SECONDS_MEAN"] - sum(seconds) / 6) < 0.002
    statuses = [record["POOL_OPTIMALITY_STATUS"] for record in records]
    assert document["PROVEN_OPTIMAL_REPAIR_SETS"] == statuses.count(five.OPTIMALITY_PROVEN)
    assert document["FEASIBLE_ONLY_REPAIR_SETS"] == statuses.count(five.OPTIMALITY_FEASIBLE)
    for total_key in (
        "NODES_EXPLORED",
        "NODES_PRUNED",
        "LEAVES_SCORED",
        "SETS_ELIMINATED_BY_BOUND",
    ):
        assert document[total_key] == sum(record[total_key] for record in records)
    assert document["EXACT_REPAIR_CANDIDATES_SCORED"] == document["LEAVES_SCORED"]
    assert document["GLOBAL_TICKETS_SCORED_TOTAL"] == 6 * 13_983_816
    outside_total = document["GLOBAL_TOP48_NOT_IN_LOCAL_MUTATION_POOL"]["TOTAL"]
    assert outside_total == sum(r["GLOBAL_TOP48_NOT_IN_LOCAL_MUTATION_POOL"] for r in records)

    best_count = max(record["BEST_COUNT"] for record in records)
    improved = best_count > five.START_COUNT
    best = tuple(tuple(t) for t in document["BEST_PORTFOLIO"])
    assert document["BEST_COUNT"] == best_count
    assert document["BEST_DELTA"] == best_count - five.START_COUNT
    assert document["BEST_SHA256"] == five.portfolio_sha256(best)
    assert document["BEST_IS_START_PORTFOLIO"] == (document["BEST_SHA256"] == five.START_SHA256)
    assert len(best) == 20 == len(set(best))
    assert five.CanonicalRecounter().count(best) == document["BEST_COUNT"]
    assert document["BEST_CANONICAL_RECOUNT_STATUS"] == "PASS"
    assert document["BEST_CANONICAL_RECOUNT"] == document["BEST_COUNT"]
    assert document["BEST_COUNT_TIES_ALL_CANONICALLY_RECOUNTED"] is True
    tie_shas = [tie["SHA256"] for tie in document["BEST_COUNT_TIES_LISTED"]]
    assert document["BEST_SHA256"] == min(tie_shas)
    assert all(tie["CANONICAL_RECOUNT"] == best_count for tie in document["BEST_COUNT_TIES_LISTED"])
    assert document["BEST_COUNT_TIE_COUNT"] >= len(tie_shas) >= 1
    assert document["BEST_NEW_TICKETS"] == [list(t) for t in sorted(set(best) - set(start))]
    dropped_positions = [i for i, t in enumerate(five.START_PORTFOLIO) if t not in set(best)]
    assert document["BEST_REPLACED_INDICES"] == dropped_positions
    expected_result = repair.RESULT_IMPROVED if improved else repair.RESULT_NO_IMPROVEMENT
    assert document["SCIENTIFIC_RESULT"] == expected_result
    assert document["NEW_STABLE_NON_LANE3_GAIN"] == ("YES" if improved else "NO")
    assert document["SCIENTIFIC_SCOPE"] == repair.SCIENTIFIC_SCOPE
    for key in ("COMPLETE_N4_OPTIMUM", "COMPLETE_N5_OPTIMUM", "GLOBAL_K20_OPTIMUM"):
        assert document[key] == "NOT_CLAIMED"
    assert document["GAIN_VS_PROTECTED_LANE_3"] == "NOT_EVALUATED"
    assert document["PROTECTED_LANE_3_TOUCHED"] == "NO"
    assert document["PROJECT_MEMORY_WRITTEN"] == "NO"
    assert (document["PUSH"], document["PR"], document["PRODUCTION_CHANGE"]) == (
        "NO",
        "NOT_CREATED",
        "NONE",
    )

    parity = document["PARITY"]
    assert document["PARITY_MISMATCHES"] == parity["PARITY_MISMATCHES"] == 0
    assert parity["TOY"]["MISMATCHES"] == parity["REAL"]["MISMATCHES"] == 0
    assert parity["COVERAGE_MEETS_PACKET_MINIMUMS"] is True
    assert parity["REAL_MARGINAL_COMPARISONS"] >= 100
    assert parity["REAL_REPAIRED_PORTFOLIOS"] >= 20
    assert document["PARITY_SAMPLE_COUNT"] == (
        parity["TOY"]["COMPARISONS"] + parity["REAL"]["COMPARISONS"]
    )
    parity_sets = {tuple(entry["POSITIONS"]) for entry in parity["REAL"]["SETS"]}
    assert parity_sets.isdisjoint({tuple(r["POSITIONS"]) for r in records})
