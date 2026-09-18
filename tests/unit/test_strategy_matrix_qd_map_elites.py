"""Unit tests for the bounded, deterministic, single-generation native
MAP-Elites / Quality-Diversity portfolio explorer
(`STRATEGY_MATRIX_NATIVE_MAP_ELITES_QD_PROTOTYPE_R1`).

An independent brute-force oracle (`_brute_force_map_elites`, built from
plain `itertools`/`set` operations only -- never importing the coverage,
neighborhood, or descriptor primitives the module under test reuses)
re-derives the expected archive for every scenario below and is compared
field-by-field against `run_map_elites`'s real output. This cross-checks the
module's *wiring* of those already-separately-tested primitives, not their
own correctness.

Covers: deterministic result, one elite per cell, higher-quality
replacement, deterministic lexicographic tie-break, multiple cells
coexisting, the seed-cell snapshot occurring before exploration, exact
`new_descriptor_cell_count` semantics (a non-seed portfolio landing in an
already-seeded cell is NOT a new niche), the fixed evaluation-budget hard
stop with no automatic escalation, illegal/duplicate input failing closed,
and the absence of any outcome/replay/database dependency.
"""

from __future__ import annotations

import dataclasses
import inspect
import itertools
from collections.abc import Sequence
from fractions import Fraction

import pytest
from tools.run_strategy_matrix_qd_map_elites_prototype import classify_final_verdict

from lottolab.domain.lottery_rules import DAILY_539_RULE_CONTRACT
from lottolab.research import strategy_matrix_qd_map_elites as qd_module
from lottolab.research.strategy_matrix_qd_map_elites import (
    EliteEntry,
    MapElitesResult,
    portfolio_descriptor_cell,
    run_map_elites,
)

Ticket = tuple[int, ...]
Portfolio = tuple[Ticket, ...]
DescriptorCell = tuple[int, int]
OracleArchive = dict[DescriptorCell, tuple[Portfolio, Fraction, bool]]


@dataclasses.dataclass(frozen=True)
class OracleResult:
    seed_cells: frozenset[DescriptorCell]
    final_cells: frozenset[DescriptorCell]
    archive: OracleArchive
    evaluated: int
    budget_exhausted: bool


POOL_SIZE = 9
DRAW_SIZE = 3
TOY_RULES = dataclasses.replace(
    DAILY_539_RULE_CONTRACT, main_number_max=POOL_SIZE, main_number_count=DRAW_SIZE
)

SEED_DISJOINT: Portfolio = ((1, 2, 3), (4, 5, 6), (7, 8, 9))
SEED_OVERLAPPING: Portfolio = ((1, 2, 3), (1, 2, 4), (1, 2, 5))

FULL_WORKLOAD = 102  # both seeds' complete one-exchange neighborhoods, at k=3/draw_size=3/pool=9


# --- independent brute-force oracle (no shared code with the module) -------


def _brute_force_quality(
    pool_size: int, draw_size: int, minimum_matches: int, portfolio: Portfolio
) -> Fraction:
    draws = list(itertools.combinations(range(1, pool_size + 1), draw_size))
    covered = sum(
        1
        for draw in draws
        if any(len(set(draw) & set(ticket)) >= minimum_matches for ticket in portfolio)
    )
    return Fraction(covered, len(draws))


def _brute_force_descriptor(portfolio: Portfolio) -> DescriptorCell:
    pairs: list[tuple[Ticket, Ticket]] = list(itertools.combinations(portfolio, 2))
    overlaps: list[int] = [len(set(a) & set(b)) for a, b in pairs]
    max_overlap = max(overlaps, default=0)
    union: set[int] = set()
    for ticket in portfolio:
        union.update(ticket)
    return (max_overlap, len(union))


def _brute_force_one_exchange(pool_size: int, ticket: Ticket) -> list[Ticket]:
    ticket_set: set[int] = set(ticket)
    complement: list[int] = [n for n in range(1, pool_size + 1) if n not in ticket_set]
    mutations: list[Ticket] = []
    for removed in sorted(ticket_set):
        base: set[int] = ticket_set - {removed}
        for added in complement:
            mutations.append(tuple(sorted(base | {added})))
    return mutations


def _brute_force_map_elites(
    seeds: Sequence[Portfolio],
    pool_size: int,
    draw_size: int,
    minimum_matches: int,
    evaluation_budget: int,
) -> OracleResult:
    """Independent re-implementation of the exact algorithm documented in
    `strategy_matrix_qd_map_elites`: seed first, snapshot, then one
    deterministic wave of one-exchange neighbors per seed, budget-capped.
    """
    canonical_seeds: list[Portfolio] = [tuple(sorted(seed)) for seed in seeds]
    archive: OracleArchive = {}

    def consider(portfolio: Portfolio, quality: Fraction, is_seed: bool) -> None:
        cell = _brute_force_descriptor(portfolio)
        existing = archive.get(cell)
        if (
            existing is None
            or quality > existing[1]
            or (quality == existing[1] and portfolio < existing[0])
        ):
            archive[cell] = (portfolio, quality, is_seed)

    for seed in canonical_seeds:
        consider(seed, _brute_force_quality(pool_size, draw_size, minimum_matches, seed), True)

    seed_cells = frozenset(archive.keys())

    evaluated = 0
    budget_exhausted = False
    for seed in canonical_seeds:
        if budget_exhausted:
            break
        ticket_set = set(seed)
        for slot_index, original_ticket in enumerate(seed):
            if budget_exhausted:
                break
            remaining = seed[:slot_index] + seed[slot_index + 1 :]
            for mutated in _brute_force_one_exchange(pool_size, original_ticket):
                if mutated in ticket_set:
                    continue
                if evaluated >= evaluation_budget:
                    budget_exhausted = True
                    break
                neighbor: Portfolio = tuple(sorted((*remaining, mutated)))
                quality = _brute_force_quality(pool_size, draw_size, minimum_matches, neighbor)
                evaluated += 1
                consider(neighbor, quality, False)

    final_cells = frozenset(archive.keys())
    return OracleResult(
        seed_cells=seed_cells,
        final_cells=final_cells,
        archive=archive,
        evaluated=evaluated,
        budget_exhausted=budget_exhausted,
    )


def _assert_matches_oracle(result: MapElitesResult, oracle: OracleResult) -> None:
    assert result.seed_descriptor_cells == oracle.seed_cells
    assert result.final_descriptor_cells == oracle.final_cells
    assert result.evaluated_candidate_count == oracle.evaluated
    assert result.budget_exhausted == oracle.budget_exhausted
    assert set(result.archive.keys()) == set(oracle.archive.keys())
    for cell, (portfolio, quality, is_seed) in oracle.archive.items():
        entry = result.archive[cell]
        assert entry.portfolio == portfolio, f"cell {cell}: portfolio mismatch"
        assert entry.quality == quality, f"cell {cell}: quality mismatch"
        assert entry.is_seed == is_seed, f"cell {cell}: is_seed mismatch"


# --- A. oracle cross-check: quality-driven replacement, multiple cells,
#        new-cell-count, and the novelty rule ---------------------------


def test_a_full_expansion_matches_independent_oracle_under_real_quality() -> None:
    oracle = _brute_force_map_elites(
        (SEED_DISJOINT, SEED_OVERLAPPING), POOL_SIZE, DRAW_SIZE, minimum_matches=2,
        evaluation_budget=1000,
    )
    result = run_map_elites(
        (SEED_DISJOINT, SEED_OVERLAPPING), TOY_RULES, minimum_matches=2, evaluation_budget=1000
    )
    _assert_matches_oracle(result, oracle)

    # Multiple cells coexist.
    assert len(result.archive) == 4

    # NEW_DESCRIPTOR_CELL_COUNT: exactly the cells absent from the seed snapshot.
    assert result.new_descriptor_cell_count == 2
    assert result.non_seed_elite_count == 3

    # Novelty rule: cell (2, 5) was a SEED cell (SEED_OVERLAPPING's own
    # descriptor) that a strictly-higher-quality non-seed neighbor took over.
    # It must NOT be counted as a new niche even though its occupant changed.
    overlapping_cell = portfolio_descriptor_cell(tuple(sorted(SEED_OVERLAPPING)), TOY_RULES)
    assert overlapping_cell in result.seed_descriptor_cells
    assert overlapping_cell not in (result.final_descriptor_cells - result.seed_descriptor_cells)
    assert result.archive[overlapping_cell].is_seed is False
    assert result.archive[overlapping_cell].quality > _brute_force_quality(
        POOL_SIZE, DRAW_SIZE, 2, tuple(sorted(SEED_OVERLAPPING))
    )


def test_a_one_elite_per_cell_is_self_consistent() -> None:
    result = run_map_elites(
        (SEED_DISJOINT, SEED_OVERLAPPING), TOY_RULES, minimum_matches=2, evaluation_budget=1000
    )
    for cell, entry in result.archive.items():
        assert portfolio_descriptor_cell(entry.portfolio, TOY_RULES) == cell
    # Trivially true for a dict -- stated explicitly as the required property.
    assert len(result.archive) == len(set(result.archive.keys()))


# --- B. deterministic lexicographic tie-break -------------------------------


def test_b_tie_break_matches_oracle_when_every_candidate_ties() -> None:
    # minimum_matches=0 degrades every portfolio's exact coverage to 1/1
    # (see exact_coverage_fast_evaluator's own documented degenerate-case
    # behavior), so cell occupancy is decided purely by canonical
    # lexicographic portfolio order -- isolating the tie-break rule from
    # quality entirely.
    oracle = _brute_force_map_elites(
        (SEED_DISJOINT, SEED_OVERLAPPING), POOL_SIZE, DRAW_SIZE, minimum_matches=0,
        evaluation_budget=1000,
    )
    result = run_map_elites(
        (SEED_DISJOINT, SEED_OVERLAPPING), TOY_RULES, minimum_matches=0, evaluation_budget=1000
    )
    _assert_matches_oracle(result, oracle)

    for entry in result.archive.values():
        assert entry.quality == Fraction(1, 1)

    # Cell (2, 5) has 25 tied candidates (SEED_OVERLAPPING plus 24 of its
    # neighbors); the lexicographically smallest of all of them is
    # SEED_OVERLAPPING itself.
    overlapping_cell = portfolio_descriptor_cell(tuple(sorted(SEED_OVERLAPPING)), TOY_RULES)
    assert result.archive[overlapping_cell].portfolio == tuple(sorted(SEED_OVERLAPPING))
    assert result.archive[overlapping_cell].is_seed is True


# --- C. determinism ----------------------------------------------------------


def test_c_deterministic_across_repeated_runs() -> None:
    first = run_map_elites(
        (SEED_DISJOINT, SEED_OVERLAPPING), TOY_RULES, minimum_matches=2, evaluation_budget=1000
    )
    second = run_map_elites(
        (SEED_DISJOINT, SEED_OVERLAPPING), TOY_RULES, minimum_matches=2, evaluation_budget=1000
    )
    assert first.archive == second.archive
    assert first.seed_descriptor_cells == second.seed_descriptor_cells
    assert first.final_descriptor_cells == second.final_descriptor_cells
    assert first.evaluated_candidate_count == second.evaluated_candidate_count


# --- D. seed-cell snapshot occurs strictly before exploration ---------------


def test_d_seed_snapshot_reflects_only_input_seeds_not_neighbor_discoveries() -> None:
    result = run_map_elites(
        (SEED_DISJOINT, SEED_OVERLAPPING), TOY_RULES, minimum_matches=2, evaluation_budget=1000
    )
    expected_seed_cells = frozenset(
        {
            portfolio_descriptor_cell(tuple(sorted(SEED_DISJOINT)), TOY_RULES),
            portfolio_descriptor_cell(tuple(sorted(SEED_OVERLAPPING)), TOY_RULES),
        }
    )
    assert result.seed_descriptor_cells == expected_seed_cells
    assert len(result.seed_descriptor_cells) == 2
    # Exploration strictly grew the occupied-cell set beyond the snapshot.
    assert result.final_descriptor_cells > result.seed_descriptor_cells


def test_d_zero_budget_never_explores_and_final_equals_seed_cells() -> None:
    result = run_map_elites(
        (SEED_DISJOINT, SEED_OVERLAPPING), TOY_RULES, minimum_matches=2, evaluation_budget=0
    )
    assert result.evaluated_candidate_count == 0
    assert result.final_descriptor_cells == result.seed_descriptor_cells
    assert result.new_descriptor_cell_count == 0
    assert result.non_seed_elite_count == 0
    assert result.budget_exhausted is True


# --- E. fixed evaluation budget: hard stop, never escalated -----------------


def test_e_budget_hard_stop_is_exact() -> None:
    result = run_map_elites(
        (SEED_DISJOINT, SEED_OVERLAPPING), TOY_RULES, minimum_matches=2, evaluation_budget=1
    )
    assert result.evaluated_candidate_count == 1
    assert result.budget_exhausted is True


def test_e_generous_budget_never_exceeds_single_generation_workload() -> None:
    # "No automatic budget escalation": once both seeds' complete
    # one-exchange neighborhoods are exhausted, a far larger budget must not
    # manufacture a second generation -- evaluated count caps at the fixed,
    # already-known single-generation workload.
    result = run_map_elites(
        (SEED_DISJOINT, SEED_OVERLAPPING),
        TOY_RULES,
        minimum_matches=2,
        evaluation_budget=10_000_000,
    )
    assert result.evaluated_candidate_count == FULL_WORKLOAD
    assert result.budget_exhausted is False


# --- F. illegal/duplicate portfolio input fails closed ----------------------


def test_f_wrong_ticket_length_fails_closed() -> None:
    with pytest.raises(ValueError):
        run_map_elites(
            (((1, 2), (4, 5, 6), (7, 8, 9)),), TOY_RULES, minimum_matches=2, evaluation_budget=10
        )


def test_f_number_out_of_pool_range_fails_closed() -> None:
    with pytest.raises(ValueError):
        run_map_elites(
            (((1, 2, 99), (4, 5, 6), (7, 8, 9)),),
            TOY_RULES,
            minimum_matches=2,
            evaluation_budget=10,
        )


def test_f_non_integer_number_fails_closed() -> None:
    bad_portfolio = ((1.5, 2, 3), (4, 5, 6), (7, 8, 9))
    with pytest.raises(ValueError):
        run_map_elites((bad_portfolio,), TOY_RULES, minimum_matches=2, evaluation_budget=10)  # type: ignore[arg-type]


def test_f_duplicate_number_within_ticket_fails_closed() -> None:
    with pytest.raises(ValueError):
        run_map_elites(
            (((1, 1, 2), (4, 5, 6), (7, 8, 9)),), TOY_RULES, minimum_matches=2, evaluation_budget=10
        )


def test_f_duplicate_ticket_within_portfolio_fails_closed() -> None:
    with pytest.raises(ValueError):
        run_map_elites(
            (((1, 2, 3), (1, 2, 3), (7, 8, 9)),), TOY_RULES, minimum_matches=2, evaluation_budget=10
        )


def test_f_duplicate_seed_portfolios_across_seed_list_fails_closed() -> None:
    with pytest.raises(ValueError):
        run_map_elites(
            (SEED_DISJOINT, tuple(sorted(SEED_DISJOINT))),
            TOY_RULES,
            minimum_matches=2,
            evaluation_budget=10,
        )


def test_f_empty_seed_list_fails_closed() -> None:
    with pytest.raises(ValueError):
        run_map_elites((), TOY_RULES, minimum_matches=2, evaluation_budget=10)


def test_f_negative_budget_fails_closed() -> None:
    with pytest.raises(ValueError):
        run_map_elites((SEED_DISJOINT,), TOY_RULES, minimum_matches=2, evaluation_budget=-1)


# --- G. no outcome/replay/database dependency -------------------------------


def test_g_module_imports_no_outcome_replay_or_database_dependency() -> None:
    forbidden_substrings = (
        "sqlite3",
        "replay_research_session",
        "prize_evaluation",
        "lottolab.interfaces",
        "lottolab.domain.draws",
        "lottolab.infrastructure",
    )
    source = inspect.getsource(qd_module)
    for forbidden in forbidden_substrings:
        assert forbidden not in source


def test_g_result_and_entry_are_frozen_dataclasses() -> None:
    result = run_map_elites((SEED_DISJOINT,), TOY_RULES, minimum_matches=2, evaluation_budget=5)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.evaluated_candidate_count = 999  # type: ignore[misc]
    entry = next(iter(result.archive.values()))
    assert isinstance(entry, EliteEntry)
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.quality = Fraction(1, 1)  # type: ignore[misc]


def test_h_negative_exact_coverage_delta_cannot_produce_value_signal() -> None:
    strong_baseline_q = Fraction(54130, 582659)
    best_qd_exact_coverage = Fraction(46265, 499422)
    assert best_qd_exact_coverage - strong_baseline_q == Fraction(-925, 3495954)
    assert classify_final_verdict(
        evaluated_candidate_count=2580,
        new_descriptor_cell_count=4,
        best_qd_exact_coverage=best_qd_exact_coverage,
        strong_baseline_q=strong_baseline_q,
    ) == "QD_MORPHOLOGY_ONLY_NO_VALUE_SIGNAL"
