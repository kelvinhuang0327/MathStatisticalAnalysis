"""Focused contract checks for the bounded zero-gain plateau pilot."""

from __future__ import annotations

import itertools
from math import comb
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import b649_k20_three_ticket_single_number_cycle_r1 as cycle
from lottolab.research import b649_k20_zero_gain_plateau_escape_r1 as pilot

ROOT = Path(__file__).resolve().parents[2]
V = 12
SYNTHETIC_ROOT: cycle.Portfolio = (
    (1, 7, 8, 9, 10, 11),
    (1, 7, 8, 9, 10, 12),
    (5, 6, 8, 9, 10, 12),
    (5, 6, 9, 10, 11, 12),
)
SYNTHETIC_ROOT_SHA = "37ae6181aa4d05e00b5cdf7dfcdac001ded50d52d7ee091b68b7ee0b4be44884"
SYNTHETIC_ZERO_SHA = "02b64691c3245035f55c224b1aaa6107195c85f58848410d5767fa2afc1809c7"
SYNTHETIC_EXIT_SHA = "1bca217cbe5e9e027ec441ebddf67075758db3226a4addef9ab98dddf3cfb6b1"


@pytest.fixture(scope="module")
def draws12() -> cycle.DrawMasks:
    return cycle.load_draws(V)


@pytest.fixture(scope="module")
def synthetic_start(draws12: cycle.DrawMasks) -> cycle.StartBinding:
    return cycle.bind_start(
        SYNTHETIC_ROOT,
        pool_size=V,
        expected_sha256=SYNTHETIC_ROOT_SHA,
        expected_outcome_count=5537,
        draws=draws12,
    )


def test_state_sampling_depends_only_on_frozen_seed_and_state_sha() -> None:
    first = pilot.sample_triples(pilot.ROOT_SHA256, 20)
    again = pilot.sample_triples(pilot.ROOT_SHA256, 20)
    different = pilot.sample_triples(SYNTHETIC_ROOT_SHA, 20)
    assert first == again
    assert first != different
    assert len(first) == len(set(first)) == 64
    assert list(first) == sorted(first)
    assert all(0 <= i < j < k < 20 for i, j, k in first)
    assert pilot.sample_triples(SYNTHETIC_ROOT_SHA, 4) == tuple(itertools.combinations(range(4), 3))
    assert pilot.SearchConfig(3, 32, 96, 64, 20260930) == pilot.FROZEN_CONFIG
    with pytest.raises(ValueError):
        pilot.sample_triples("bad", 20)


def _zero_emissions(start: cycle.StartBinding, draws: cycle.DrawMasks) -> list[cycle.EmittedCycle]:
    family = cycle.deduped_emissions(
        emission for _, emission in cycle.iter_emitted_cycles(start.portfolio, pool_size=V)
    )
    return [
        emission
        for emission in family
        if cycle.official_any_prize_outcome_count(emission.portfolio, pool_size=V, draws=draws)
        == start.outcome_count
    ]


def test_zero_only_frontier_visited_and_all_three_caps(
    synthetic_start: cycle.StartBinding, draws12: cycle.DrawMasks
) -> None:
    zeros = _zero_emissions(synthetic_start, draws12)
    assert len(zeros) == 16
    config = pilot.SearchConfig(1, 2, 3, 4, 20260930)
    visited = {synthetic_start.sha256}
    root = pilot.PlateauState(synthetic_start.portfolio, synthetic_start.sha256, 0, ())
    layer1 = pilot.ZeroCollector(config, synthetic_start.outcome_count, visited, 0, 1)
    for index, emission in enumerate(zeros):
        assert layer1.consider(
            root,
            emission.indices,
            pilot.ScoredRow(
                emission.sha256, synthetic_start.outcome_count, emission.numbers, emission.direction
            ),
            V,
        ) is (index < 2)
    retained = layer1.finish()
    assert len(retained) == 2
    assert layer1.generated == 16
    assert all(state.depth == 1 for state in retained)
    assert all(state.sha256 in visited for state in retained)
    assert all(
        cycle.official_any_prize_outcome_count(state.portfolio, pool_size=V, draws=draws12)
        == synthetic_start.outcome_count
        for state in retained
    )
    layer2 = pilot.ZeroCollector(config, synthetic_start.outcome_count, visited, 2, 1)
    for emission in zeros:
        layer2.consider(
            root,
            emission.indices,
            pilot.ScoredRow(
                emission.sha256, synthetic_start.outcome_count, emission.numbers, emission.direction
            ),
            V,
        )
    assert len(layer2.finish()) == 1  # total-state cap 3
    cycle_guard = pilot.ZeroCollector(config, synthetic_start.outcome_count, visited, 3, 1)
    assert not cycle_guard.consider(
        retained[0],
        zeros[0].indices,
        pilot.ScoredRow(
            synthetic_start.sha256,
            synthetic_start.outcome_count,
            zeros[0].numbers,
            zeros[0].direction,
        ),
        V,
    )
    assert cycle_guard.deduplicated == 1  # root SHA cannot re-enter
    too_deep = pilot.ZeroCollector(config, synthetic_start.outcome_count, visited, 0, 2)
    assert not too_deep.consider(
        root,
        zeros[2].indices,
        pilot.ScoredRow(
            zeros[2].sha256, synthetic_start.outcome_count, zeros[2].numbers, zeros[2].direction
        ),
        V,
    )
    assert not too_deep.states


@pytest.mark.parametrize("kind", ["negative", "positive"])
def test_nonzero_state_rejected_without_duplicate_or_capacity_guard(
    kind: str, synthetic_start: cycle.StartBinding, draws12: cycle.DrawMasks
) -> None:
    portfolio = synthetic_start.portfolio
    depth = 0
    if kind == "positive":
        zero = cycle.emit_spec(
            portfolio, cycle.RawCycleSpec((1, 2, 3), (7, 5, 11), "reverse"), pool_size=V
        )
        assert zero is not None and zero.sha256 == SYNTHETIC_ZERO_SHA
        portfolio = zero.portfolio
        depth = 1
        emission = cycle.emit_spec(
            portfolio, cycle.RawCycleSpec((1, 2, 3), (8, 7, 6), "forward"), pool_size=V
        )
        assert emission is not None and emission.sha256 == SYNTHETIC_EXIT_SHA
    else:
        emission = next(
            candidate
            for _, candidate in cycle.iter_emitted_cycles(portfolio, pool_size=V)
            if cycle.official_any_prize_outcome_count(
                candidate.portfolio, pool_size=V, draws=draws12
            )
            < synthetic_start.outcome_count
        )
    count = cycle.official_any_prize_outcome_count(emission.portfolio, pool_size=V, draws=draws12)
    assert (
        (count < synthetic_start.outcome_count)
        if kind == "negative"
        else (count > synthetic_start.outcome_count)
    )
    parent = pilot.PlateauState(
        portfolio, cycle.portfolio_sha256(portfolio, pool_size=V), depth, ()
    )
    collector = pilot.ZeroCollector(
        pilot.FROZEN_CONFIG,
        synthetic_start.outcome_count,
        {synthetic_start.sha256, parent.sha256},
        0,
        depth + 1,
    )
    assert emission.sha256 not in collector.visited
    assert not collector.consider(
        parent,
        emission.indices,
        pilot.ScoredRow(emission.sha256, count, emission.numbers, emission.direction),
        V,
    )
    assert not collector.states
    assert collector.generated == collector.deduplicated == 0


def test_best_ever_is_monotone_and_direct_is_separate(synthetic_start: cycle.StartBinding) -> None:
    tracker = pilot.BestTracker(
        synthetic_start.outcome_count, synthetic_start.sha256, synthetic_start.portfolio
    )
    tracker.consider(pilot.BestCandidate(synthetic_start.portfolio, "f" * 64, 5544, ()), 0)
    tracker.consider(pilot.BestCandidate(synthetic_start.portfolio, "e" * 64, 5530, ()), 1)
    tracker.consider(pilot.BestCandidate(synthetic_start.portfolio, "d" * 64, 5540, ()), 1)
    tracker.consider(pilot.BestCandidate(synthetic_start.portfolio, "c" * 64, 5551, ()), 1)
    assert tracker.direct is not None and tracker.direct.count == 5544
    assert tracker.plateau is not None and tracker.plateau.count == 5551
    assert tracker.history == [5537, 5544, 5551]
    assert tracker.global_best.count == 5551


def test_nonvacuous_synthetic_plateau_escape(
    synthetic_start: cycle.StartBinding, draws12: cycle.DrawMasks
) -> None:
    report = pilot.run_search(
        synthetic_start,
        draws=draws12,
        config=pilot.SearchConfig(1, 16, 16, 4, 20260930),
        workers=1,
    )
    assert report["ROOT_FAMILY_LEGAL"] == 20
    assert report["ROOT_NEGATIVE_COUNT"] == 4
    assert report["ROOT_ZERO_COUNT"] == 16
    assert report["ROOT_POSITIVE_COUNT"] == 0
    assert report["DIRECT_ROOT_IMPROVEMENT"] == "NO"
    assert report["PLATEAU_ESCAPE_ESTABLISHED"] == "YES"
    assert report["SCIENTIFIC_RESULT"] == "PLATEAU_ESCAPE"
    assert report["PLATEAU_DEPTH_REACHED"] == 1
    assert report["PLATEAU_STATES_RETAINED"] == 16
    assert report["ESCAPE_PROBES"] == 16 * comb(4, 3)
    assert cast(int, report["BEST_COUNT"]) > synthetic_start.outcome_count
    assert report["ESCAPE_PATH_LENGTH"] == 2
    deltas = cast(list[int], report["ESCAPE_PATH_DELTAS"])
    assert deltas[0:2] == [0, 0]
    assert deltas[2] > 0
    assert report["BEST_CANONICAL_RECOUNT_STATUS"] == "PASS"
    assert report["PLATEAU_CANONICAL_RECOUNTS"] == 16
    history = cast(list[int], report["BEST_EVER_HISTORY"])
    assert all(history[i] <= history[i + 1] for i in range(len(history) - 1))
    # Preserve the original discovered root -> zero -> positive witness.
    root = synthetic_start.portfolio
    zero = cycle.emit_spec(root, cycle.RawCycleSpec((1, 2, 3), (7, 5, 11), "reverse"), pool_size=V)
    assert zero is not None and zero.sha256 == SYNTHETIC_ZERO_SHA
    assert (
        cycle.official_any_prize_outcome_count(zero.portfolio, pool_size=V, draws=draws12) == 5537
    )
    exit_move = cycle.emit_spec(
        zero.portfolio, cycle.RawCycleSpec((1, 2, 3), (8, 7, 6), "forward"), pool_size=V
    )
    assert exit_move is not None and exit_move.sha256 == SYNTHETIC_EXIT_SHA
    assert (
        cycle.official_any_prize_outcome_count(exit_move.portfolio, pool_size=V, draws=draws12)
        == 5544
    )


def test_parallel_scoring_matches_sequential_on_synthetic_fixture(
    synthetic_start: cycle.StartBinding, draws12: cycle.DrawMasks
) -> None:
    config = pilot.SearchConfig(1, 16, 16, 4, 20260930)
    sequential = pilot.run_search(synthetic_start, draws=draws12, config=config, workers=1)
    parallel = pilot.run_search(synthetic_start, draws=draws12, config=config, workers=2)
    assert parallel == sequential


@pytest.fixture(scope="module")
def draws49() -> cycle.DrawMasks:
    return cycle.load_draws(49)


def test_root_and_sampled_49_20_states_canonical_parity(draws49: cycle.DrawMasks) -> None:
    start = pilot.load_root(ROOT, draws49)
    assert start.outcome_count == pilot.ROOT_COUNT
    assert start.sha256 == pilot.ROOT_SHA256
    triples = pilot.sample_triples(start.sha256, 20)[:2]
    for triple in triples:
        result = pilot.score_triple(start.portfolio, start.outcome_count, triple, 49, draws49)
        assert result.raw_attempts == cycle.TRIPLE_RAW_ATTEMPTS
        for row in result.rows[:3]:
            parent = pilot.PlateauState(start.portfolio, start.sha256, 0, ())
            emission = pilot.reconstruct_emission(parent, triple, row, 49)
            assert (
                cycle.official_any_prize_outcome_count(
                    emission.portfolio, pool_size=49, draws=draws49
                )
                == row.count
            )
