from __future__ import annotations

import ast
import inspect
import itertools
import math
import random
from dataclasses import fields

import pytest

from lottolab.research import covering_design_setcover_sa
from lottolab.research.covering_design_setcover_sa import (
    _COOLING_RATE,  # pyright: ignore[reportPrivateUsage]
    _INITIAL_TEMPERATURE,  # pyright: ignore[reportPrivateUsage]
    _TEMPERATURE_FLOOR,  # pyright: ignore[reportPrivateUsage]
    Block,
    CoveringDesignSAConfig,
    CoveringDesignSAResult,
    _accept_neighbor,  # pyright: ignore[reportPrivateUsage]
    _build_problem,  # pyright: ignore[reportPrivateUsage]
    _generate_neighbor,  # pyright: ignore[reportPrivateUsage]
    _greedy_cover,  # pyright: ignore[reportPrivateUsage]
    _is_exact_cover,  # pyright: ignore[reportPrivateUsage]
    _SimulatedAnnealingSearch,  # pyright: ignore[reportPrivateUsage]
    run_covering_design_setcover_sa,
)


def _brute_force_covered(
    v: int, t: int, blocks: tuple[Block, ...]
) -> set[tuple[int, ...]]:
    block_sets = [set(block) for block in blocks]
    return {
        subset
        for subset in itertools.combinations(range(v), t)
        if any(set(subset).issubset(block) for block in block_sets)
    }


@pytest.mark.parametrize(
    ("v", "k", "t"),
    [
        (3, 2, 2),
        (4, 4, 2),
        (4, 3, 3),
        (4, 3, 0),
        (4, 2, 3),
        (True, 3, 2),
    ],
)
def test_invalid_v_k_t_is_rejected(v: int, k: int, t: int) -> None:
    config = CoveringDesignSAConfig(seed=1)
    with pytest.raises(ValueError, match=r"v > k > t >= 1|must be an integer"):
        run_covering_design_setcover_sa(v, k, t, config=config)


def test_r1_domain_guard_rejects_v_greater_than_twelve() -> None:
    with pytest.raises(ValueError, match="v <= 12"):
        run_covering_design_setcover_sa(13, 6, 2, config=CoveringDesignSAConfig(seed=1))


@pytest.mark.parametrize("limit", [0.0, -1.0, math.inf, math.nan, True])
def test_invalid_wall_clock_limit_is_rejected(limit: float) -> None:
    with pytest.raises(ValueError, match="time_limit_seconds"):
        CoveringDesignSAConfig(seed=1, time_limit_seconds=limit)


def test_selectable_blocks_are_exact_canonical_k_subsets() -> None:
    problem = _build_problem(6, 4, 2)
    assert problem.blocks == tuple(itertools.combinations(range(6), 4))
    assert all(len(block) == 4 and len(set(block)) == 4 for block in problem.blocks)


def test_universe_is_the_exact_set_of_t_subsets() -> None:
    problem = _build_problem(6, 4, 2)
    assert problem.universe == tuple(itertools.combinations(range(6), 2))


def test_one_block_covers_exactly_its_contained_t_subsets() -> None:
    problem = _build_problem(6, 4, 2)
    block = (0, 2, 4, 5)
    assert problem.covered_by_block[block] == frozenset(itertools.combinations(block, 2))


def test_greedy_initial_state_is_a_complete_exact_cover() -> None:
    problem = _build_problem(7, 4, 2)
    selected = _greedy_cover(problem)
    assert _is_exact_cover(problem, selected)


def test_each_greedy_step_matches_unit_cost_gain_oracle_with_lexicographic_ties() -> None:
    problem = _build_problem(7, 4, 2)
    actual_steps = _greedy_cover(problem)
    selected: set[Block] = set()
    uncovered = set(problem.universe)

    for actual in actual_steps:
        candidates: list[tuple[float, Block]] = []
        for block in problem.blocks:
            if block in selected:
                continue
            gain = len(uncovered.intersection(problem.covered_by_block[block]))
            if gain:
                candidates.append((1.0 / gain, block))
        expected = min(candidates)[1]
        assert actual == expected
        selected.add(actual)
        uncovered.difference_update(problem.covered_by_block[actual])

    assert not uncovered


def test_same_seed_and_input_without_time_limit_is_exactly_reproducible() -> None:
    config = CoveringDesignSAConfig(seed=2026)
    first = run_covering_design_setcover_sa(7, 4, 2, config=config)
    second = run_covering_design_setcover_sa(7, 4, 2, config=config)
    assert first == second


def test_different_seeds_can_take_different_neighbor_trajectories() -> None:
    problem = _build_problem(6, 3, 2)
    current = set(problem.blocks[:2])
    removed = _generate_neighbor(current, problem.blocks, random.Random(1))
    added = _generate_neighbor(current, problem.blocks, random.Random(2))
    assert len(removed) == len(current) - 1
    assert len(added) == len(current) + 1
    assert removed != added


def test_remove_move_removes_exactly_one_selected_block() -> None:
    problem = _build_problem(6, 3, 2)
    current = set(problem.blocks[:3])
    neighbor = _generate_neighbor(current, problem.blocks, random.Random(1))
    assert current - neighbor <= current
    assert len(current - neighbor) == 1
    assert not neighbor - current


def test_add_move_adds_exactly_one_canonically_ordered_unselected_block() -> None:
    problem = _build_problem(6, 3, 2)
    current = set(problem.blocks[:3])
    neighbor = _generate_neighbor(current, problem.blocks, random.Random(2))
    assert len(neighbor - current) == 1
    assert not current - neighbor
    assert next(iter(neighbor - current)) in problem.blocks


def test_neighbor_operator_never_swaps_blocks() -> None:
    problem = _build_problem(6, 3, 2)
    current = set(problem.blocks[:3])
    for seed in range(20):
        neighbor = _generate_neighbor(current, problem.blocks, random.Random(seed))
        assert len(current.symmetric_difference(neighbor)) <= 1


def test_random_selection_from_set_is_canonical_before_rng_choice() -> None:
    problem = _build_problem(6, 3, 2)
    forward = set(problem.blocks[:5])
    reverse: set[Block] = set()
    for block in reversed(problem.blocks[:5]):
        reverse.add(block)
    assert _generate_neighbor(forward, problem.blocks, random.Random(1)) == _generate_neighbor(
        reverse, problem.blocks, random.Random(1)
    )


def test_infeasible_neighbor_is_hard_rejected_and_still_cools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem = _build_problem(5, 3, 2)
    search = _SimulatedAnnealingSearch(problem, random.Random(5))
    original_current = search.current.copy()
    original_best = search.best.copy()

    def empty_neighbor(
        _current: set[Block], _blocks: tuple[Block, ...], _rng: random.Random
    ) -> set[Block]:
        return set()

    monkeypatch.setattr(covering_design_setcover_sa, "_generate_neighbor", empty_neighbor)
    search.attempt_neighbor()

    assert search.current == original_current
    assert search.best == original_best
    assert search.current_cost == len(original_current)
    assert search.temperature == 9.5
    assert search.temperature_steps == 1


def test_positive_delta_feasible_addition_uses_donor_metropolis_rule() -> None:
    problem = _build_problem(5, 3, 2)
    current = set(_greedy_cover(problem))
    added_block = next(block for block in problem.blocks if block not in current)
    neighbor = current | {added_block}
    delta = len(neighbor) - len(current)
    temperature = 0.75
    seed = 17
    expected = random.Random(seed).random() < math.exp(-delta / temperature)

    assert _is_exact_cover(problem, neighbor)
    assert delta > 0
    assert _accept_neighbor(delta, temperature, random.Random(seed)) is expected


def test_negative_delta_feasible_removal_is_always_accepted_without_rng_draw() -> None:
    class FailingRandom(random.Random):
        def random(self) -> float:
            raise AssertionError("negative delta must not draw for Metropolis acceptance")

    problem = _build_problem(5, 3, 2)
    current = set(problem.blocks)
    neighbor = current - {problem.blocks[0]}
    delta = len(neighbor) - len(current)

    assert _is_exact_cover(problem, neighbor)
    assert delta < 0
    assert _accept_neighbor(delta, 1.0, FailingRandom())


def test_zero_delta_uses_metropolis_branch_because_improvement_is_strict() -> None:
    class CountingRandom(random.Random):
        calls = 0

        def random(self) -> float:
            self.calls += 1
            return 0.999

    rng = CountingRandom()
    assert _accept_neighbor(0, 1.0, rng)
    assert rng.calls == 1


def test_best_state_changes_only_for_strictly_lower_cost() -> None:
    problem = _build_problem(5, 3, 2)
    search = _SimulatedAnnealingSearch(problem, random.Random(3))
    original_best = search.best.copy()
    same_cost = set(problem.blocks[-search.best_cost :])
    assert same_cost != original_best

    search.current = same_cost
    search.current_cost = search.best_cost
    search._update_best()  # pyright: ignore[reportPrivateUsage]
    assert search.best == original_best

    search.current = set(sorted(original_best)[:-1])
    search.current_cost = search.best_cost - 1
    search._update_best()  # pyright: ignore[reportPrivateUsage]
    assert search.best == search.current


def test_temperature_starts_at_ten_and_multiplies_per_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem = _build_problem(5, 3, 2)
    search = _SimulatedAnnealingSearch(problem, random.Random(9))
    assert search.temperature == 10.0 == _INITIAL_TEMPERATURE
    assert _COOLING_RATE == 0.95

    def same_neighbor(
        current: set[Block], _blocks: tuple[Block, ...], _rng: random.Random
    ) -> set[Block]:
        return current.copy()

    monkeypatch.setattr(covering_design_setcover_sa, "_generate_neighbor", same_neighbor)
    search.attempt_neighbor()
    search.attempt_neighbor()
    assert search.temperature == 10.0 * 0.95**2
    assert search.temperature_steps == 2


def test_no_time_limit_terminates_only_at_temperature_floor() -> None:
    assert _TEMPERATURE_FLOOR == 0.01
    result = run_covering_design_setcover_sa(
        6, 3, 2, config=CoveringDesignSAConfig(seed=41)
    )
    temperature = _INITIAL_TEMPERATURE
    expected_steps = 0
    while temperature > _TEMPERATURE_FLOOR:
        temperature *= _COOLING_RATE
        expected_steps += 1

    assert result.termination_reason == "TEMPERATURE_FLOOR"
    assert result.temperature_steps == expected_steps
    assert temperature <= _TEMPERATURE_FLOOR


def test_non_none_wall_clock_cutoff_reports_time_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timestamps = iter((100.0, 100.6))
    monkeypatch.setattr(covering_design_setcover_sa.time, "time", lambda: next(timestamps))
    result = run_covering_design_setcover_sa(
        5,
        3,
        2,
        config=CoveringDesignSAConfig(seed=43, time_limit_seconds=0.5),
    )
    assert result.termination_reason == "TIME_LIMIT"
    assert result.temperature_steps == 0
    assert result.coverage == 1.0


def test_returned_blocks_exactly_cover_the_t_subset_universe() -> None:
    v, k, t = 7, 4, 3
    result = run_covering_design_setcover_sa(
        v, k, t, config=CoveringDesignSAConfig(seed=73)
    )
    assert _brute_force_covered(v, t, result.selected_blocks) == set(
        itertools.combinations(range(v), t)
    )
    assert result.coverage == 1.0


def test_returned_block_count_matches_selected_cardinality() -> None:
    result = run_covering_design_setcover_sa(
        6, 3, 2, config=CoveringDesignSAConfig(seed=101)
    )
    assert result.block_count == len(result.selected_blocks)


def test_public_api_exposes_no_fixed_ticket_count_semantics() -> None:
    assert tuple(inspect.signature(run_covering_design_setcover_sa).parameters) == (
        "v",
        "k",
        "t",
        "config",
    )
    assert tuple(field.name for field in fields(CoveringDesignSAConfig)) == (
        "seed",
        "time_limit_seconds",
    )
    assert tuple(field.name for field in fields(CoveringDesignSAResult)) == (
        "selected_blocks",
        "block_count",
        "coverage",
        "temperature_steps",
        "termination_reason",
    )


def test_module_has_no_historical_data_or_database_dependency() -> None:
    source = inspect.getsource(covering_design_setcover_sa)
    tree = ast.parse(source)
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_roots.add(node.module.split(".", maxsplit=1)[0])

    assert imported_roots <= {
        "__future__",
        "collections",
        "dataclasses",
        "itertools",
        "math",
        "random",
        "time",
        "typing",
    }


def test_donor_provenance_mit_notice_and_reproducibility_boundary_are_present() -> None:
    documentation = covering_design_setcover_sa.__doc__ or ""
    assert "gojiplus/rowvoi" in documentation
    assert "64b921cf25f9a4a03787be1a73be679cfbece81f" in documentation
    assert "SetCoverProblem._simulated_annealing" in documentation
    assert "MIT License" in documentation
    assert "Copyright (c) 2025 goji+" in documentation
    assert "The above copyright notice and this permission notice" in documentation
    assert 'THE SOFTWARE IS PROVIDED "AS IS"' in documentation
    assert "PYTHON_PORT_REPRODUCIBLE: YES" in documentation
    assert "DONOR_EXACT_TRAJECTORY_PARITY: NOT_CLAIMED" in documentation
    assert "TIME_LIMIT_TRAJECTORY_REPRODUCIBILITY: NOT_CLAIMED" in documentation
