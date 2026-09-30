"""Focused tests for the K20 five-ticket exact repair pilot (B649_K20_FIVE_TICKET_EXACT_REPAIR_R1).

Toy lotteries use the canonical evaluator and brute force as oracles; one non-sample real
destroy quintuple checks the residual kernel, the pool and the solver on the real 49/6 space.
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

import numpy as np
import numpy.typing as npt
import pytest

from lottolab.application.b649_sealed_geometry_portfolio import (
    SEALED_GEOMETRY_PORTFOLIOS,
    canonical_portfolio_sha256,
)
from lottolab.research import b649_k20_five_ticket_exact_repair_r1 as repair

# a real destroy set that is neither in the pilot sample nor in the parity sets
DEV_POSITIONS = (0, 4, 9, 13, 17)
TOY = repair.Geometry(14, 6, 4)
RESULT_PATH = repair.REPO_ROOT / repair.RESULT_RELATIVE_PATH


def _elites() -> list[repair.Portfolio]:
    return [pin.tickets for pin in repair.PINNED_ELITES]


def _random_instance(
    rng: np.random.Generator, pool: int, rows: int
) -> tuple[npt.NDArray[np.uint64], npt.NDArray[np.int64]]:
    masks = np.unique(rng.integers(1, 1 << pool, size=rows, dtype=np.uint64))
    weights = rng.integers(1, 1000, size=masks.size).astype(np.int64)
    return masks, weights


def _toy_case(
    seed: int,
) -> tuple[repair.DestroyedPortfolio, repair.Portfolio, repair.PoolHistogram]:
    """A toy destroy step with a 14-ticket pool: (destroyed, pool, residual histogram)."""

    rng = random.Random(seed)
    every = list(itertools.combinations(range(1, TOY.pool_size + 1), TOY.draw_size))
    start = repair.normalize_portfolio(rng.sample(every, 9), geometry=TOY)
    destroyed = repair.destroy_positions(start, sorted(rng.sample(range(9), 5)))
    others = [t for t in every if t not in set(start)]
    pool = tuple(sorted({*destroyed.removed, *rng.sample(others, 9)}))
    return destroyed, pool, repair.build_pool_histogram(destroyed.remaining, pool, geometry=TOY)


class _MiscountingRecounter(repair.CanonicalRecounter):
    """A recounter that is always off by one, to prove the recount guards fire."""

    def count(self, portfolio: Sequence[repair.Ticket]) -> int:
        return super().count(portfolio) + 1


# ------------------------------------------------------------------ identity, sample, destroy


def test_pin_verification_fails_loudly_on_any_identity_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(AssertionError, match="identity recount"):
        repair.verify_pins(_MiscountingRecounter())
    wrong_sha = dataclasses.replace(repair.PINNED_ELITES[0], sha256="0" * 64)
    monkeypatch.setattr(repair, "PINNED_ELITES", (wrong_sha, *repair.PINNED_ELITES[1:]))
    with pytest.raises(AssertionError, match="identity recount"):
        repair.verify_pins(repair.CanonicalRecounter())


def test_start_and_pinned_elites_have_recorded_identity() -> None:
    for pin in repair.PINNED_ELITES:
        assert len(pin.tickets) == repair.PORTFOLIO_SIZE
        assert list(pin.tickets) == sorted(pin.tickets)
        assert repair.portfolio_sha256(pin.tickets) == pin.sha256
        assert canonical_portfolio_sha256(pin.tickets) == pin.sha256
    v6 = SEALED_GEOMETRY_PORTFOLIOS[20]
    assert v6.tickets == repair.V6_PORTFOLIO
    assert repair.PINNED_ELITES[2].sha256 == repair.START_SHA256
    recounts = repair.verify_pins(repair.CanonicalRecounter())
    assert [r["CANONICAL_COUNT"] for r in recounts] == [312986016, 313239647, 313239661]
    assert repair.START_COUNT == 313239661


def test_start_matches_the_source_commit_artifact() -> None:
    target = f"{repair.SOURCE_COMMIT}:{repair.SOURCE_ARTIFACT}"
    probe = subprocess.run(
        ["git", "cat-file", "-e", target], cwd=repair.REPO_ROOT, capture_output=True, check=False
    )
    if probe.returncode != 0:
        pytest.skip("source commit is not available in this clone")
    shown = subprocess.run(
        ["git", "show", target], cwd=repair.REPO_ROOT, capture_output=True, check=True
    )
    artifact = json.loads(shown.stdout)
    assert tuple(tuple(t) for t in artifact["BEST_PORTFOLIO"]) == repair.START_PORTFOLIO
    assert artifact["BEST_PORTFOLIO_SHA256"] == repair.START_SHA256
    assert artifact["BEST_COUNT"] == repair.START_COUNT


def test_sample_is_deterministic_distinct_and_prefix_stable() -> None:
    sample = repair.sample_destroy_quintuples()
    assert sample == repair.sample_destroy_quintuples()
    assert len(sample) == len(set(sample)) == repair.DESTROY_QUINTUPLE_SAMPLE_COUNT == 8
    for positions in sample:
        assert positions == tuple(sorted(set(positions)))
        assert len(positions) == repair.DESTROY_SIZE
        assert all(0 <= p < repair.PORTFOLIO_SIZE for p in positions)
    longer = repair.sample_destroy_quintuples(count=11)
    assert longer[:8] == sample
    assert len(set(longer)) == 11
    assert repair.sample_destroy_quintuples(seed=1) != sample
    # independent re-derivation of the ranking rule
    ranked = sorted(
        (hashlib.sha256(f"{repair.PILOT_SEED}:{','.join(map(str, c))}".encode()).hexdigest(), c)
        for c in itertools.combinations(range(20), 5)
    )
    assert tuple(c for _, c in ranked[:8]) == sample
    assert len(ranked) == comb(20, 5) == 15504
    assert DEV_POSITIONS not in longer


def test_sample_is_persisted_and_verified_before_scoring(tmp_path: Path) -> None:
    sample = repair.sample_destroy_quintuples()
    path = tmp_path / "nested" / "destroy-sample.json"
    digest = repair.persist_destroy_sample(path, sample)
    assert digest == hashlib.sha256(path.read_bytes()).hexdigest()
    assert repair.load_persisted_sample(path) == sample
    document = json.loads(path.read_text(encoding="utf-8"))
    document["DESTROY_QUINTUPLES"][0] = [0, 1, 2, 3, 4]
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="differs"):
        repair.load_persisted_sample(path)
    with pytest.raises(FileNotFoundError):
        repair.load_persisted_sample(tmp_path / "missing.json")


def test_destroy_five_partitions_the_start_portfolio() -> None:
    for positions in repair.sample_destroy_quintuples():
        destroyed = repair.destroy_positions(repair.START_PORTFOLIO, positions)
        assert destroyed.positions == positions
        assert len(destroyed.removed) == repair.DESTROY_SIZE
        assert len(destroyed.remaining) == repair.R_SIZE == 15
        assert destroyed.removed == tuple(repair.START_PORTFOLIO[p] for p in positions)
        assert set(destroyed.removed).isdisjoint(destroyed.remaining)
        assert set(destroyed.removed) | set(destroyed.remaining) == set(repair.START_PORTFOLIO)
        kept = [t for i, t in enumerate(repair.START_PORTFOLIO) if i not in positions]
        assert list(destroyed.remaining) == kept
    for bad in [(0, 0, 1, 2, 3), (0, 1, 2, 3, 20), (-1, 0, 1, 2, 3)]:
        with pytest.raises(ValueError, match="illegal destroy positions"):
            repair.destroy_positions(repair.START_PORTFOLIO, bad)


# ------------------------------------------------------------------ exact kernels (toy oracles)


@pytest.mark.parametrize(
    ("pool_size", "subset_size"), [(9, 3), (10, 4), (12, 7), (13, 7), (16, 5), (20, 7)]
)
def test_subset_blocks_partition_the_space_exactly(pool_size: int, subset_size: int) -> None:
    blocks = list(repair.iter_subset_mask_blocks(pool_size, subset_size, target_block=50))
    produced = np.concatenate(blocks)
    expected = np.array(
        sorted(
            repair.ticket_mask(c)
            for c in itertools.combinations(range(1, pool_size + 1), subset_size)
        ),
        dtype=np.uint64,
    )
    assert produced.size == comb(pool_size, subset_size)
    assert np.array_equal(np.sort(produced), expected)


def test_real_subset_space_is_complete() -> None:
    total = 0
    checksum = 0
    for block in repair.iter_subset_mask_blocks(49, 7):
        total += int(block.size)
        checksum += int(block.sum(dtype=np.uint64))
        assert bool(np.all(np.bitwise_count(block) == 7))
    assert total == comb(49, 7) == 85_900_584
    assert checksum % (1 << 64) == comb(48, 6) * ((1 << 49) - 1) % (1 << 64)


@pytest.mark.parametrize("geometry", repair.TOY_GEOMETRIES)
def test_subset_identity_matches_the_canonical_evaluator(geometry: repair.Geometry) -> None:
    rng = random.Random(5)
    every = list(itertools.combinations(range(1, geometry.pool_size + 1), geometry.draw_size))
    recounter = repair.CanonicalRecounter(geometry)
    for size in (1, 3, 6, 9):
        portfolio = repair.normalize_portfolio(rng.sample(every, size), geometry=geometry)
        assert repair.outcome_count(portfolio, geometry=geometry) == recounter.count(portfolio)


def test_residual_score_matches_canonical_on_toy_lotteries() -> None:
    recounter = repair.CanonicalRecounter(TOY)
    for seed in range(4):
        destroyed, pool, histogram = _toy_case(seed)
        for subset in itertools.islice(itertools.combinations(range(len(pool)), 5), 0, 3003, 41):
            portfolio = (*destroyed.remaining, *(pool[i] for i in subset))
            assert histogram.outcome_count(subset) == recounter.count(portfolio)
            assert histogram.outcome_count(subset) == repair.outcome_count(portfolio, geometry=TOY)
        assert histogram.residual_subsets == int(histogram.weights.sum()) + histogram.dead_subsets
        assert bool(np.all(histogram.masks != 0))
        union = repair.covered_subset_count((*destroyed.remaining, *pool), geometry=TOY)
        assert histogram.dead_subsets == TOY.subset_count - union


def test_histogram_handles_a_frozen_set_that_wins_everything() -> None:
    geometry = repair.Geometry(9, 4, 2)
    every = list(itertools.combinations(range(1, 10), 4))
    frozen = tuple(every[:60])
    histogram = repair.build_pool_histogram(frozen, (every[70],), geometry=geometry)
    assert histogram.residual_subsets == 0
    assert histogram.masks.size == 0
    assert histogram.outcome_count((0,)) == geometry.subset_size * geometry.subset_count


def test_restricting_a_histogram_merges_rows_and_tolerates_an_empty_result() -> None:
    histogram = repair.PoolHistogram(
        geometry=TOY,
        pool=(),
        masks=np.array([0b01, 0b11, 0b100], dtype=np.uint64),
        weights=np.array([4, 6, 9], dtype=np.int64),
        total_subsets=100,
        covered_by_remaining=0,
        dead_subsets=0,
    )
    masks, weights = repair.restrict_histogram(histogram, [0])
    assert masks.tolist() == [1]
    assert weights.tolist() == [10]
    masks, weights = repair.restrict_histogram(histogram, [2, 0])
    assert masks.tolist() == [1, 2]
    assert weights.tolist() == [9, 4 + 6]
    masks, weights = repair.restrict_histogram(histogram, [3, 4])
    assert masks.size == weights.size == 0


def test_neighbour_scan_equals_direct_marginals_on_toy_lotteries() -> None:
    for seed in range(3):
        destroyed, _, _ = _toy_case(seed)
        scans = repair.scan_neighbors(destroyed.remaining, destroyed.removed, geometry=TOY)
        assert len(scans) == len(destroyed.removed)
        for base, scan in zip(destroyed.removed, scans, strict=True):
            tickets = sorted(scan)
            assert len(tickets) == TOY.draw_size * (TOY.pool_size - TOY.draw_size)
            assert base not in scan
            assert all(len(set(base) & set(t)) == TOY.draw_size - 1 for t in tickets)
            direct = repair.direct_marginals(destroyed.remaining, tickets, geometry=TOY)
            assert [scan[t] for t in tickets] == direct


# ------------------------------------------------------------------ candidate pool (toy)


def _toy_pool(pool_max: int) -> repair.PoolPlan:
    rng = random.Random(3)
    every = list(itertools.combinations(range(1, TOY.pool_size + 1), TOY.draw_size))
    start = repair.normalize_portfolio(rng.sample(every, 9), geometry=TOY)
    return repair.assemble_pool(
        start, (1, 3, 4, 6, 8), elites=[start], pool_max=pool_max, geometry=TOY
    )


def test_pool_is_legal_deduplicated_capped_and_never_repeats_frozen_tickets() -> None:
    plan = _toy_pool(pool_max=20)
    tickets = plan.tickets
    assert len(tickets) == len(set(tickets)) == 20
    assert list(tickets) == sorted(tickets)
    assert set(tickets).isdisjoint(plan.destroyed.remaining)
    for ticket in tickets:
        assert repair.normalize_portfolio([ticket], geometry=TOY) == (ticket,)
    assert plan.required_count == 5
    required = {m.ticket for m in plan.members if m.source == repair.SOURCE_REMOVED}
    assert required == set(plan.destroyed.removed)
    marginals = repair.direct_marginals(plan.destroyed.remaining, tickets, geometry=TOY)
    assert marginals == [member.marginal for member in plan.members]


def test_pool_never_repeats_a_frozen_or_required_ticket_reached_by_mutation() -> None:
    start = repair.normalize_portfolio(
        [
            (1, 2, 3, 4, 5, 6),
            (1, 2, 3, 4, 5, 7),
            (1, 2, 3, 4, 5, 8),
            (7, 8, 9, 10, 11, 12),
            (2, 4, 6, 8, 10, 12),
            (3, 5, 7, 9, 11, 13),
            (1, 3, 5, 7, 9, 11),
            (2, 3, 5, 8, 13, 14),
            (6, 9, 10, 12, 13, 14),
        ],
        geometry=TOY,
    )
    positions = (0, 2, 3, 5, 7)
    plan = repair.assemble_pool(start, positions, elites=[start], pool_max=25, geometry=TOY)
    frozen_neighbour = (1, 2, 3, 4, 5, 7)
    removed_neighbour = (1, 2, 3, 4, 5, 8)
    assert frozen_neighbour in plan.destroyed.remaining
    assert removed_neighbour in plan.destroyed.removed
    assert frozen_neighbour not in plan.tickets
    assert plan.excluded_frozen > 0
    assert plan.excluded_required > 0
    assert len(plan.tickets) == len(set(plan.tickets))
    assert set(plan.tickets).isdisjoint(plan.destroyed.remaining)
    assert [m.source for m in plan.members if m.ticket == removed_neighbour] == [
        repair.SOURCE_REMOVED
    ]


def test_pool_cap_keeps_required_first_then_highest_marginal_then_lowest_ticket() -> None:
    small, large = _toy_pool(pool_max=9), _toy_pool(pool_max=16)
    assert len(small.members) == 9
    assert len(large.members) == 16
    assert small.required_count == large.required_count == 5

    def optional(plan: repair.PoolPlan) -> list[repair.PoolMember]:
        return [m for m in plan.members if m.source != repair.SOURCE_REMOVED]

    small_tickets = {m.ticket for m in optional(small)}
    extra = [m for m in optional(large) if m.ticket not in small_tickets]
    assert small_tickets <= {m.ticket for m in optional(large)}
    assert len(small_tickets) == 4
    assert extra

    def rank(member: repair.PoolMember) -> tuple[int, repair.Ticket]:
        return (-member.marginal, member.ticket)

    assert max(rank(m) for m in optional(small)) < min(rank(m) for m in extra)
    assert {m.ticket for m in small.members if m.source == repair.SOURCE_REMOVED} == set(
        small.destroyed.removed
    )


def test_pool_assembly_is_deterministic_and_rejects_bad_requests() -> None:
    assert _toy_pool(pool_max=12) == _toy_pool(pool_max=12)
    plan = _toy_pool(pool_max=12)
    with pytest.raises(ValueError, match="cap"):
        repair.assemble_pool(
            repair.normalize_portfolio(
                [*plan.destroyed.remaining, *plan.destroyed.removed], geometry=TOY
            ),
            (0, 1, 2, 3, 4),
            elites=[plan.destroyed.remaining, plan.destroyed.removed],
            pool_max=3,
            geometry=TOY,
        )
    with pytest.raises(ValueError, match="pinned elite"):
        repair.assemble_pool(
            (*plan.destroyed.removed, *plan.destroyed.remaining),
            (0, 1, 2, 3, 4),
            elites=[plan.destroyed.remaining],
            pool_max=12,
            geometry=TOY,
        )


# ------------------------------------------------------------------ exact solver


@pytest.mark.parametrize("use_bound", [True, False])
def test_solver_equals_brute_force_on_random_weighted_instances(use_bound: bool) -> None:
    rng = np.random.default_rng(5)
    improved = 0
    for _ in range(60):
        pool = int(rng.integers(6, 13))
        pick = int(rng.integers(2, min(6, pool)))
        masks, weights = _random_instance(rng, pool, int(rng.integers(5, 60)))
        start = tuple(sorted(int(i) for i in rng.choice(pool, size=pick, replace=False)))
        best_value, _ = repair.brute_force_best(masks, weights, pool, pick)
        start_value = repair.evaluate_set(masks, weights, start)
        result = repair.solve_exact_repair(masks, weights, pool, pick, start, use_bound=use_bound)
        assert result.best_value == max(best_value, start_value)
        assert repair.evaluate_set(masks, weights, result.best_set) == result.best_value
        assert len(set(result.best_set)) == pick
        assert result.status == repair.OPTIMALITY_PROVEN
        assert result.improved == (best_value > start_value)
        assert result.leaf_quintuples_evaluated + result.quintuples_pruned == comb(pool, pick)
        assert result.unresolved_quintuples == 0
        improved += result.improved
    assert improved > 10


def test_solver_equals_brute_force_on_toy_lottery_pools() -> None:
    for seed in range(4):
        destroyed, pool, histogram = _toy_case(seed)
        start = tuple(pool.index(t) for t in destroyed.removed)
        best_value, _ = repair.brute_force_best(histogram.masks, histogram.weights, len(pool), 5)
        start_value = repair.evaluate_set(histogram.masks, histogram.weights, start)
        for use_bound in (True, False):
            result = repair.solve_exact_repair(
                histogram.masks, histogram.weights, len(pool), 5, start, use_bound=use_bound
            )
            assert result.best_value == max(best_value, start_value)
            assert result.unresolved_quintuples == 0


@pytest.mark.parametrize("use_bound", [True, False])
def test_single_ticket_pick_matches_brute_force(use_bound: bool) -> None:
    rng = np.random.default_rng(17)
    for _ in range(40):
        pool = int(rng.integers(2, 10))
        masks, weights = _random_instance(rng, pool, int(rng.integers(2, 30)))
        start = (int(rng.integers(0, pool)),)
        best_value, _ = repair.brute_force_best(masks, weights, pool, 1)
        start_value = repair.evaluate_set(masks, weights, start)
        result = repair.solve_exact_repair(masks, weights, pool, 1, start, use_bound=use_bound)
        assert result.best_value == max(best_value, start_value)
        assert result.status == repair.OPTIMALITY_PROVEN
        assert result.leaf_quintuples_evaluated + result.quintuples_pruned == pool


def test_toy_parity_family_has_zero_mismatches() -> None:
    report = repair.run_toy_parity()
    assert report.mismatches == 0
    assert report.comparisons > 300


def test_remaining_slot_bound_is_safe_and_not_vacuous() -> None:
    rng = np.random.default_rng(11)
    tight = 0
    for _ in range(120):
        pool = int(rng.integers(6, 11))
        masks, weights = _random_instance(rng, pool, 40)
        prefix = tuple(
            int(i) for i in rng.choice(pool, size=int(rng.integers(0, 3)), replace=False)
        )
        rest = [i for i in range(pool) if i not in prefix]
        slots = int(rng.integers(1, min(4, len(rest)) + 1))
        uncovered = (masks & np.uint64(sum(1 << i for i in prefix))) == 0
        gains = np.array(
            [
                weights[uncovered & (((masks >> np.uint64(i)) & np.uint64(1)) == 1)].sum()
                for i in rest
            ],
            dtype=np.float64,
        )
        bound = repair.remaining_slot_upper_bound(gains, slots)
        true_best = max(
            int(weights[uncovered & ((masks & np.uint64(sum(1 << i for i in chosen))) != 0)].sum())
            for chosen in itertools.combinations(rest, slots)
        )
        assert bound >= true_best
        tight += bound == true_best
    assert tight > 0
    assert repair.remaining_slot_upper_bound(np.array([5.0, 9.0, 2.0]), 2) == 14
    assert repair.remaining_slot_upper_bound(np.array([5.0, 9.0, 2.0]), 0) == 0
    assert repair.remaining_slot_upper_bound(np.array([5.0, 9.0]), 3) == 14


def test_an_unsafe_bound_is_caught_by_the_brute_force_comparison(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = repair.remaining_slot_upper_bound

    def unsafe(gains: npt.NDArray[np.float64], slots: int) -> int:
        return original(gains, slots) // 3

    monkeypatch.setattr(repair, "remaining_slot_upper_bound", unsafe)
    rng = np.random.default_rng(5)
    caught = 0
    for _ in range(60):
        pool = int(rng.integers(6, 13))
        pick = int(rng.integers(2, min(6, pool)))
        masks, weights = _random_instance(rng, pool, int(rng.integers(5, 60)))
        start = tuple(sorted(int(i) for i in rng.choice(pool, size=pick, replace=False)))
        best_value, _ = repair.brute_force_best(masks, weights, pool, pick)
        result = repair.solve_exact_repair(masks, weights, pool, pick, start)
        caught += result.best_value != max(best_value, result.start_value)
    assert caught > 0


def test_solver_result_is_deterministic_including_ties() -> None:
    # ticket 3 wins nothing, so (0, 3) is beatable, and (0, 1), (0, 2) and (1, 2) tie at 21
    masks = np.array([0b0011, 0b0101, 0b0110], dtype=np.uint64)
    weights = np.full(masks.size, 7, dtype=np.int64)
    first = repair.solve_exact_repair(masks, weights, 4, 2, (0, 3))
    second = repair.solve_exact_repair(masks, weights, 4, 2, (0, 3))
    assert first == dataclasses.replace(second, seconds=first.seconds)
    assert first.best_value == 21
    assert first.best_set in {(0, 1), (0, 2), (1, 2)}
    assert first.improved
    unbounded = repair.solve_exact_repair(masks, weights, 4, 2, (0, 3), use_bound=False)
    assert unbounded.best_value == 21


def test_expired_deadline_reports_feasible_only_and_never_proven() -> None:
    rng = np.random.default_rng(2)
    masks, weights = _random_instance(rng, 12, 80)
    ticks = iter(range(10_000))
    result = repair.solve_exact_repair(
        masks, weights, 12, 5, (0, 1, 2, 3, 4), deadline=-1.0, clock=lambda: float(next(ticks))
    )
    assert result.status == repair.OPTIMALITY_FEASIBLE != repair.OPTIMALITY_PROVEN
    assert result.best_set == (0, 1, 2, 3, 4)
    assert result.best_value == result.start_value
    assert result.unresolved_quintuples == result.total_quintuples == comb(12, 5)


def test_a_deadline_that_expires_mid_search_keeps_an_exact_incumbent() -> None:
    rng = np.random.default_rng(9)
    masks, weights = _random_instance(rng, 14, 200)
    start = (0, 1, 2, 3, 4)
    ticks = iter(range(10_000))
    partial = repair.solve_exact_repair(
        masks,
        weights,
        14,
        5,
        start,
        deadline=30.0,
        clock=lambda: float(next(ticks)),
        use_bound=False,
    )
    assert partial.status == repair.OPTIMALITY_FEASIBLE
    assert partial.unresolved_quintuples > 0
    assert repair.evaluate_set(masks, weights, partial.best_set) == partial.best_value
    assert partial.best_value >= partial.start_value
    full = repair.solve_exact_repair(masks, weights, 14, 5, start)
    assert full.status == repair.OPTIMALITY_PROVEN
    assert full.best_value >= partial.best_value
    assert full.best_value == repair.brute_force_best(masks, weights, 14, 5)[0]


# ---------------------------------------------------------- real 49/6 space (non-sample set)


@pytest.fixture(scope="module")
def recounter() -> repair.CanonicalRecounter:
    return repair.CanonicalRecounter()


@pytest.fixture(scope="module")
def dev_repair(recounter: repair.CanonicalRecounter) -> repair.QuintupleRepair:
    return repair.repair_destroy_quintuple(
        repair.START_PORTFOLIO,
        DEV_POSITIONS,
        elites=_elites(),
        recounter=recounter,
        expected_start_count=repair.START_COUNT,
    )


@pytest.fixture(scope="module")
def dev_histogram(dev_repair: repair.QuintupleRepair) -> repair.PoolHistogram:
    return repair.build_pool_histogram(dev_repair.plan.destroyed.remaining, dev_repair.plan.tickets)


def test_real_pool_composition_cap_and_legality(dev_repair: repair.QuintupleRepair) -> None:
    plan = dev_repair.plan
    assert len(plan.members) == repair.CANDIDATE_POOL_MAX == 48
    assert len(set(plan.tickets)) == 48
    assert list(plan.tickets) == sorted(plan.tickets)
    assert plan.required_count == 13
    counts = plan.source_counts()
    assert counts[repair.SOURCE_REMOVED] == 5
    assert counts[repair.SOURCE_ELITE] == 8
    assert sum(counts.values()) == 48
    assert set(plan.tickets).isdisjoint(plan.destroyed.remaining)
    elite_union = {t for pin in repair.PINNED_ELITES for t in pin.tickets}
    assert elite_union - set(plan.destroyed.remaining) <= set(plan.tickets)
    assert set(plan.destroyed.removed) <= set(plan.tickets)
    assert plan.universe_size >= 48 - plan.required_count
    for ticket in plan.tickets:
        assert repair.normalize_portfolio([ticket]) == (ticket,)


def test_real_pool_marginals_are_exact(dev_repair: repair.QuintupleRepair) -> None:
    plan = dev_repair.plan
    by_source: dict[str, list[repair.PoolMember]] = {}
    for member in plan.members:
        by_source.setdefault(member.source, []).append(member)
    picked = [
        by_source[repair.SOURCE_REMOVED][0],
        by_source[repair.SOURCE_ELITE][0],
        *by_source[repair.SOURCE_MUTATION_L1][:2],
        *by_source[repair.SOURCE_MUTATION_L2][:3],
    ]
    direct = repair.direct_marginals(plan.destroyed.remaining, [m.ticket for m in picked])
    assert direct == [m.marginal for m in picked]


def test_real_neighbour_scan_matches_direct_marginals(dev_repair: repair.QuintupleRepair) -> None:
    plan = dev_repair.plan
    scan = repair.scan_neighbors(plan.destroyed.remaining, [plan.destroyed.removed[0]])[0]
    assert len(scan) == 6 * 43
    tickets = sorted(scan)[::37]
    direct = repair.direct_marginals(plan.destroyed.remaining, tickets)
    assert [scan[t] for t in tickets] == direct


def test_real_residual_kernel_matches_the_canonical_evaluator(
    dev_repair: repair.QuintupleRepair,
    dev_histogram: repair.PoolHistogram,
    recounter: repair.CanonicalRecounter,
) -> None:
    plan = dev_repair.plan
    tickets = plan.tickets
    start = tuple(tickets.index(t) for t in plan.destroyed.removed)
    assert dev_histogram.outcome_count(start) == repair.START_COUNT == dev_repair.start_outcomes
    rng = random.Random(4)
    for _ in range(5):
        subset = tuple(sorted(rng.sample(range(len(tickets)), 5)))
        portfolio = repair.normalize_portfolio(
            (*plan.destroyed.remaining, *(tickets[i] for i in subset))
        )
        via_histogram = dev_histogram.outcome_count(subset)
        assert via_histogram == recounter.count(portfolio) == repair.outcome_count(portfolio)
    assert dev_histogram.total_subsets == comb(49, 7)
    residual = dev_histogram.residual_subsets
    assert residual == int(dev_histogram.weights.sum()) + dev_histogram.dead_subsets
    frozen_count = recounter.count(plan.destroyed.remaining)
    assert dev_histogram.remaining_outcome_count == frozen_count
    assert bool(np.all(dev_histogram.masks != 0))
    union = repair.covered_subset_count((*plan.destroyed.remaining, *plan.tickets))
    assert dev_histogram.dead_subsets == comb(49, 7) - union


def test_real_small_pool_solver_matches_brute_force_and_canonical(
    dev_repair: repair.QuintupleRepair,
    dev_histogram: repair.PoolHistogram,
    recounter: repair.CanonicalRecounter,
) -> None:
    plan = dev_repair.plan
    start = tuple(plan.tickets.index(t) for t in plan.destroyed.removed)
    others = [i for i in range(len(plan.tickets)) if i not in start]
    keep_including_start = sorted((*start, *others[:7]))
    cases = [
        (keep_including_start, tuple(keep_including_start.index(i) for i in start)),
        (list(range(repair.SMALL_POOL_SIZE)), (0, 1, 2, 3, 4)),
    ]
    for keep, incumbent in cases:
        masks, weights = repair.restrict_histogram(dev_histogram, keep)
        for subset in itertools.islice(itertools.combinations(range(len(keep)), 5), 0, 792, 97):
            restricted_value = repair.evaluate_set(masks, weights, subset)
            assert restricted_value == dev_histogram.subset_value([keep[i] for i in subset])
        brute_value, _ = repair.brute_force_best(masks, weights, len(keep), 5)
        result = repair.solve_exact_repair(masks, weights, len(keep), 5, incumbent)
        incumbent_value = repair.evaluate_set(masks, weights, incumbent)
        assert result.best_value == max(brute_value, incumbent_value)
        assert result.status == repair.OPTIMALITY_PROVEN
        best = tuple(keep[i] for i in result.best_set)
        portfolio = repair.normalize_portfolio(
            (*plan.destroyed.remaining, *(plan.tickets[i] for i in best))
        )
        assert recounter.count(portfolio) == dev_histogram.outcome_count(best)


def test_real_solve_is_proven_and_fully_accounted(dev_repair: repair.QuintupleRepair) -> None:
    solve = dev_repair.solve
    assert solve.status == repair.OPTIMALITY_PROVEN
    assert solve.total_quintuples == comb(48, 5)
    assert solve.leaf_quintuples_evaluated + solve.quintuples_pruned == solve.total_quintuples
    assert solve.unresolved_quintuples == 0
    assert solve.nodes_pruned > 0
    assert solve.quintuples_pruned > 0
    assert solve.best_value >= solve.start_value
    assert dev_repair.best_count >= repair.START_COUNT
    assert dev_repair.canonical_recount == dev_repair.best_count


def test_replacement_is_five_distinct_tickets_and_the_frozen_set_is_intact(
    dev_repair: repair.QuintupleRepair,
) -> None:
    plan = dev_repair.plan
    best = dev_repair.best_portfolio
    assert len(best) == repair.PORTFOLIO_SIZE == len(set(best))
    assert set(plan.destroyed.remaining) <= set(best)
    chosen_indices = dev_repair.solve.best_set
    assert len(chosen_indices) == len(set(chosen_indices)) == repair.DESTROY_SIZE
    chosen = {plan.tickets[i] for i in chosen_indices}
    assert set(best) == set(plan.destroyed.remaining) | chosen
    assert set(dev_repair.new_tickets).isdisjoint(plan.destroyed.remaining)
    assert set(dev_repair.new_tickets).isdisjoint(repair.START_PORTFOLIO)
    assert dev_repair.best_delta == dev_repair.best_count - repair.START_COUNT


# ------------------------------------------------------------------ result reporting


def _document(
    repairs: list[repair.QuintupleRepair], sample: list[tuple[int, ...]] | None = None
) -> dict[str, object]:
    return repair.build_result_document(
        sample=sample if sample is not None else [DEV_POSITIONS] * len(repairs),
        sample_sha256="sample-sha",
        sample_persisted_at="2026-09-30T00:00:00Z",
        pins=[],
        parity={"PARITY_SAMPLE_COUNT": 1, "PARITY_MISMATCHES": 0},
        repairs=repairs,
        start_recount=repair.START_COUNT,
        wall_seconds=1.0,
        peak_memory=1,
        run_identity={"RUN_HEAD": "head", "RUN_TREE": "tree"},
        module_sha256="module-sha",
        phase_seconds={"PINS_AND_PARITY": 1.0, "PILOT": 2.0},
    )


def test_result_document_reports_no_improvement_and_optimality_counts(
    dev_repair: repair.QuintupleRepair,
) -> None:
    document = _document([dev_repair])
    assert json.loads(repair.canonical_json(document)) == json.loads(json.dumps(document))
    assert document["PHASE_SECONDS"] == {"PINS_AND_PARITY": 1.0, "PILOT": 2.0}
    assert document["SCIENTIFIC_RESULT"] == repair.RESULT_NO_IMPROVEMENT
    assert document["NEW_STABLE_NON_LANE3_GAIN"] == "NO"
    assert document["BEST_COUNT"] == repair.START_COUNT
    assert document["BEST_DELTA"] == 0
    assert document["BEST_SHA256"] == repair.START_SHA256
    assert document["BEST_REPLACED_INDICES"] == []
    assert document["BEST_NEW_TICKETS"] == []
    assert document["COMPLETE_N5_OPTIMUM"] == "NOT_CLAIMED"
    assert document["GAIN_VS_PROTECTED_LANE_3"] == "NOT_EVALUATED"
    assert document["PROTECTED_LANE_3_TOUCHED"] == "NO"
    assert document["SCIENTIFIC_SCOPE"] == repair.SCIENTIFIC_SCOPE
    assert document["PROVEN_OPTIMAL_QUINTUPLES"] == 1
    feasible_solve = dataclasses.replace(dev_repair.solve, status=repair.OPTIMALITY_FEASIBLE)
    heuristic_solve = dataclasses.replace(dev_repair.solve, status=repair.OPTIMALITY_HEURISTIC)
    feasible = dataclasses.replace(dev_repair, solve=feasible_solve)
    heuristic = dataclasses.replace(dev_repair, solve=heuristic_solve)
    document = _document([dev_repair, dev_repair, feasible, heuristic, heuristic, heuristic])
    assert document["PROVEN_OPTIMAL_QUINTUPLES"] == 2
    assert document["FEASIBLE_ONLY_QUINTUPLES"] == 1
    assert document["HEURISTIC_QUINTUPLES"] == 3
    assert document["DESTROY_QUINTUPLES_TESTED"] == 6
    assert document["POOL_SIZE_MIN"] == document["POOL_SIZE_MAX"] == 48
    with pytest.raises(ValueError, match="exactly one repair record"):
        _document([dev_repair], sample=[DEV_POSITIONS, DEV_POSITIONS])


def test_an_improvement_is_reported_only_with_a_matching_canonical_recount(
    dev_repair: repair.QuintupleRepair,
) -> None:
    boosted = repair.START_COUNT + 14
    extra: repair.Ticket = (1, 2, 3, 4, 5, 6)
    portfolio = repair.normalize_portfolio((*repair.START_PORTFOLIO[:-1], extra))
    improved = dataclasses.replace(
        dev_repair,
        best_count=boosted,
        canonical_recount=boosted,
        best_portfolio=portfolio,
        replaced_positions=(19,),
        new_tickets=(extra,),
    )
    document = _document([dev_repair, improved])
    assert document["SCIENTIFIC_RESULT"] == repair.RESULT_IMPROVED
    assert document["NEW_STABLE_NON_LANE3_GAIN"] == "YES"
    assert document["BEST_COUNT"] == boosted
    assert document["BEST_DELTA"] == 14
    assert document["BEST_CANONICAL_RECOUNT_STATUS"] == "PASS"
    assert document["BEST_REPLACED_INDICES"] == [19]
    assert document["BEST_NEW_TICKETS"] == [[1, 2, 3, 4, 5, 6]]
    assert document["BEST_SHA256"] == repair.portfolio_sha256(portfolio)
    mismatched = dataclasses.replace(improved, canonical_recount=boosted - 1)
    document = _document([mismatched])
    assert document["SCIENTIFIC_RESULT"] == repair.RESULT_NO_IMPROVEMENT
    assert document["NEW_STABLE_NON_LANE3_GAIN"] == "NO"
    assert document["BEST_CANONICAL_RECOUNT_STATUS"] == "FAIL"


def test_global_best_ties_break_on_the_lowest_normalized_sha256(
    dev_repair: repair.QuintupleRepair,
) -> None:
    boosted = repair.START_COUNT + 5
    first, second = ((1, 2, 3, 4, 5, 6), (1, 2, 3, 4, 5, 7))
    variants = [
        dataclasses.replace(
            dev_repair,
            best_count=boosted,
            canonical_recount=boosted,
            best_portfolio=repair.normalize_portfolio((*repair.START_PORTFOLIO[:-1], extra)),
            new_tickets=(extra,),
        )
        for extra in (first, second)
    ]
    lowest = min(repair.portfolio_sha256(v.best_portfolio) for v in variants)
    forward = _document(variants)
    backward = _document(variants[::-1])
    assert forward["BEST_SHA256"] == backward["BEST_SHA256"] == lowest


# ------------------------------------------------------------------ guards and end to end (toy)


def test_portfolio_normalization_rejects_illegal_and_duplicate_tickets() -> None:
    legal = [(3, 2, 1, 6, 5, 4), (1, 2, 3, 4, 5, 7)]
    assert repair.normalize_portfolio(legal) == ((1, 2, 3, 4, 5, 6), (1, 2, 3, 4, 5, 7))
    bad_portfolios: list[list[tuple[int, ...]]] = [
        [(1, 2, 3, 4, 5)],
        [(1, 1, 2, 3, 4, 5)],
        [(0, 1, 2, 3, 4, 5)],
        [(1, 2, 3, 4, 5, 50)],
        [(1, 2, 3, 4, 5, 6), (6, 5, 4, 3, 2, 1)],
    ]
    for bad in bad_portfolios:
        with pytest.raises(ValueError):
            repair.normalize_portfolio(bad)
    assert repair.portfolio_sha256(legal) == repair.portfolio_sha256(legal[::-1])


def test_toy_pipeline_matches_brute_force_and_guards_its_recounts() -> None:
    rng = random.Random(21)
    every = list(itertools.combinations(range(1, TOY.pool_size + 1), TOY.draw_size))
    start = repair.normalize_portfolio(rng.sample(every, 9), geometry=TOY)
    recounter = repair.CanonicalRecounter(TOY)
    start_count = recounter.count(start)
    positions = (0, 2, 3, 6, 7)
    outcome = repair.repair_destroy_quintuple(
        start,
        positions,
        elites=[start],
        recounter=recounter,
        expected_start_count=start_count,
        pool_max=13,
        geometry=TOY,
    )
    pool = outcome.plan.tickets
    remaining = outcome.plan.destroyed.remaining
    best = max(
        recounter.count((*remaining, *(pool[i] for i in subset)))
        for subset in itertools.combinations(range(len(pool)), 5)
    )
    assert outcome.best_count == max(best, start_count)
    assert outcome.solve.status == repair.OPTIMALITY_PROVEN
    assert outcome.canonical_recount == outcome.best_count
    assert outcome.start_outcomes == start_count
    with pytest.raises(AssertionError, match="expected"):
        repair.repair_destroy_quintuple(
            start,
            positions,
            elites=[start],
            recounter=None,
            expected_start_count=start_count + 1,
            pool_max=13,
            geometry=TOY,
        )

    with pytest.raises(AssertionError, match="canonical recount"):
        repair.repair_destroy_quintuple(
            start,
            positions,
            elites=[start],
            recounter=_MiscountingRecounter(TOY),
            pool_max=13,
            geometry=TOY,
        )


def test_progress_events_append_and_results_are_written_atomically(tmp_path: Path) -> None:
    repair.record_progress(tmp_path, {"EVENT": "A"})
    repair.record_progress(tmp_path, {"EVENT": "B"})
    lines = (tmp_path / "progress.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["EVENT"] for line in lines] == ["A", "B"]
    assert all("AT" in json.loads(line) for line in lines)
    target = tmp_path / "out" / "result.json"
    repair.write_atomically(target, "payload")
    assert target.read_text(encoding="utf-8") == "payload"
    assert [p.name for p in target.parent.iterdir()] == ["result.json"]


def test_pilot_refuses_to_overwrite_an_existing_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def scoring_must_not_start() -> tuple[tuple[int, ...], ...]:
        raise RuntimeError("the pilot began despite an existing result")

    monkeypatch.setattr(repair, "sample_destroy_quintuples", scoring_must_not_start)
    output = tmp_path / "result.json"
    output.write_text("keep me", encoding="utf-8")
    with pytest.raises(FileExistsError):
        repair.run_pilot(tmp_path, output)
    assert output.read_text(encoding="utf-8") == "keep me"
    assert not (tmp_path / "destroy-sample.json").exists()


def test_solver_keeps_the_incumbent_when_it_is_already_optimal() -> None:
    rng = np.random.default_rng(31)
    for _ in range(80):
        pool = int(rng.integers(6, 11))
        masks, weights = _random_instance(rng, pool, int(rng.integers(3, 12)))
        pick = int(rng.integers(2, min(5, pool)))
        best_value, best_subset = repair.brute_force_best(masks, weights, pool, pick)
        result = repair.solve_exact_repair(masks, weights, pool, pick, best_subset)
        assert result.best_value == best_value
        assert not result.improved
        assert result.best_set == best_subset


# ------------------------------------------------------------------ committed result artifact


def test_result_artifact_is_self_consistent() -> None:
    document = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    module_bytes = (repair.REPO_ROOT / repair.MODULE_RELATIVE_PATH).read_bytes()
    assert document["TASK_ID"] == repair.TASK_ID
    assert document["TASK_STATUS"] == "COMPLETE"
    assert document["SOURCE_MODULE_PATH"] == repair.MODULE_RELATIVE_PATH
    assert document["SOURCE_MODULE_SHA256"] == hashlib.sha256(module_bytes).hexdigest()

    start = tuple(tuple(t) for t in document["START_PORTFOLIO"])
    assert start == repair.START_PORTFOLIO
    assert document["START_COUNT"] == document["START_CANONICAL_RECOUNT"] == repair.START_COUNT
    assert document["START_SHA256"] == repair.START_SHA256 == repair.portfolio_sha256(start)
    pin_counts = [pin["CANONICAL_COUNT"] for pin in document["PINNED_ELITES"]]
    assert pin_counts == [pin.outcome_count for pin in repair.PINNED_ELITES]
    assert document["START_SOURCE_COMMIT"] == repair.SOURCE_COMMIT

    sample = repair.sample_destroy_quintuples()
    records = document["PER_QUINTUPLE"]
    assert [tuple(p) for p in document["DESTROY_QUINTUPLES"]] == list(sample)
    assert [tuple(r["POSITIONS"]) for r in records] == list(sample)
    assert document["DESTROY_QUINTUPLES_TESTED"] == len(records) == 8
    assert document["PILOT_SEED"] == repair.PILOT_SEED == 20261001
    assert document["SAMPLE_PERSISTED_BEFORE_SCORING"] is True
    assert document["SAMPLING_METHOD"] == repair.sample_document(sample)["SAMPLING_METHOD"]
    assert document["CANDIDATE_POOL_MAX"] == 48

    for record, positions in zip(records, sample, strict=True):
        destroyed = repair.destroy_positions(repair.START_PORTFOLIO, positions)
        pool = [tuple(member["TICKET"]) for member in record["POOL"]]
        assert record["POOL_SIZE"] == len(pool) <= repair.CANDIDATE_POOL_MAX
        assert pool == sorted(pool)
        assert len(set(pool)) == len(pool)
        assert set(pool).isdisjoint(destroyed.remaining)
        assert set(destroyed.removed) <= set(pool)
        assert [tuple(t) for t in record["REMOVED_TICKETS"]] == list(destroyed.removed)
        assert sum(record["POOL_SOURCE_COUNTS"].values()) == record["POOL_SIZE"]
        assert record["START_OUTCOMES_VIA_KERNEL"] == repair.START_COUNT
        assert record["CANONICAL_MATCH"] is True
        assert record["CANONICAL_RECOUNT"] == record["BEST_COUNT"]
        assert record["BEST_DELTA"] == record["BEST_COUNT"] - repair.START_COUNT >= 0
        assert record["IMPROVED"] == (record["BEST_COUNT"] > repair.START_COUNT)
        assert record["OPTIMALITY_STATUS"] in {
            repair.OPTIMALITY_PROVEN,
            repair.OPTIMALITY_FEASIBLE,
            repair.OPTIMALITY_HEURISTIC,
        }
        assert record["TOTAL_QUINTUPLES"] == comb(record["POOL_SIZE"], repair.DESTROY_SIZE)
        accounted = record["LEAF_QUINTUPLES_EVALUATED"] + record["QUINTUPLES_ELIMINATED_BY_BOUND"]
        assert accounted + record["UNRESOLVED_QUINTUPLES"] == record["TOTAL_QUINTUPLES"]
        if record["OPTIMALITY_STATUS"] == repair.OPTIMALITY_PROVEN:
            assert record["UNRESOLVED_QUINTUPLES"] == 0
        chosen = record["BEST_POOL_INDICES"]
        assert len(set(chosen)) == len(chosen) == repair.DESTROY_SIZE
        assert all(0 <= index < len(pool) for index in chosen)

    sizes = [record["POOL_SIZE"] for record in records]
    assert document["POOL_SIZE_MIN"] == min(sizes)
    assert document["POOL_SIZE_MAX"] == max(sizes)
    assert document["POOL_SIZE_MEAN"] == round(sum(sizes) / len(sizes), 3)
    statuses = [record["OPTIMALITY_STATUS"] for record in records]
    assert document["PROVEN_OPTIMAL_QUINTUPLES"] == statuses.count(repair.OPTIMALITY_PROVEN)
    assert document["FEASIBLE_ONLY_QUINTUPLES"] == statuses.count(repair.OPTIMALITY_FEASIBLE)
    assert document["HEURISTIC_QUINTUPLES"] == statuses.count(repair.OPTIMALITY_HEURISTIC)
    for total_key, record_key in [
        ("NODES_EXPLORED", "NODES_EXPLORED"),
        ("NODES_PRUNED", "NODES_PRUNED"),
        ("LEAF_QUINTUPLES_EVALUATED", "LEAF_QUINTUPLES_EVALUATED"),
        ("QUINTUPLES_ELIMINATED_BY_BOUND", "QUINTUPLES_ELIMINATED_BY_BOUND"),
    ]:
        assert document[total_key] == sum(record[record_key] for record in records)
    scored = document["POOL_CANDIDATES_SCORED_EXACT"] + document["LEAF_QUINTUPLES_EVALUATED"]
    assert document["EXACT_CANDIDATES_SCORED"] == scored

    best_count = max([repair.START_COUNT, *(record["BEST_COUNT"] for record in records)])
    improved = best_count > repair.START_COUNT
    best = tuple(tuple(t) for t in document["BEST_PORTFOLIO"])
    assert document["BEST_COUNT"] == best_count
    assert document["BEST_DELTA"] == best_count - repair.START_COUNT
    assert document["BEST_SHA256"] == repair.portfolio_sha256(best)
    assert len(best) == repair.PORTFOLIO_SIZE
    assert repair.CanonicalRecounter().count(best) == document["BEST_COUNT"]
    assert document["BEST_CANONICAL_RECOUNT_STATUS"] == "PASS"
    assert document["BEST_CANONICAL_RECOUNT"] == document["BEST_COUNT"]
    expected_result = repair.RESULT_IMPROVED if improved else repair.RESULT_NO_IMPROVEMENT
    assert document["SCIENTIFIC_RESULT"] == expected_result
    assert document["NEW_STABLE_NON_LANE3_GAIN"] == ("YES" if improved else "NO")
    assert document["BEST_NEW_TICKETS"] == [list(t) for t in sorted(set(best) - set(start))]
    dropped = [i for i, ticket in enumerate(repair.START_PORTFOLIO) if ticket not in set(best)]
    assert document["BEST_REPLACED_INDICES"] == dropped
    if not improved:
        assert best == repair.START_PORTFOLIO
        assert document["BEST_SHA256"] == repair.START_SHA256
    assert document["COMPLETE_N5_OPTIMUM"] == "NOT_CLAIMED"
    assert document["GAIN_VS_PROTECTED_LANE_3"] == "NOT_EVALUATED"
    assert document["PROTECTED_LANE_3_TOUCHED"] == "NO"
    assert document["SCIENTIFIC_SCOPE"] == repair.SCIENTIFIC_SCOPE

    parity = document["PARITY"]
    assert document["PARITY_MISMATCHES"] == parity["TOY"]["MISMATCHES"] == 0
    assert parity["REAL"]["MISMATCHES"] == 0
    assert document["PARITY_SAMPLE_COUNT"] == (
        parity["TOY"]["COMPARISONS"] + parity["REAL"]["COMPARISONS"]
    )
    assert parity["REAL"]["CANONICAL_PORTFOLIO_COUNT"] >= 30
    assert all(entry["MATCH"] for entry in parity["REAL"]["PORTFOLIOS"])
    assert all(entry["MATCH"] for entry in parity["REAL"]["SMALL_POOL_CASES"])
    parity_sets = {tuple(p) for p in parity["REAL"]["PARITY_DESTROY_QUINTUPLES"]}
    assert parity_sets.isdisjoint(sample)
