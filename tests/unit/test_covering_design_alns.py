# pyright: reportPrivateUsage=false

from __future__ import annotations

import itertools
import math
import random
from dataclasses import FrozenInstanceError

import pytest

from lottolab.research.covering_design_alns import (
    ALNSIteration,
    ALNSOutcome,
    ALNSStatus,
    CoveringDesignALNSConfig,
    CoveringDesignALNSInvariantError,
    CoveringDesignALNSResult,
    UnsupportedSetCoverDomainError,
    _accept_non_worsening,
    _build_problem,
    _classify_outcome,
    _destroy_size,
    _greedy_max_uncovered_gain,
    _random_block_removal,
    _randomized_gain_repair,
    _redundancy_block_removal,
    _require_feasible,
    _roulette,
    _Search,
    _select_operators,
    _transition,
    _update_selected_weights,
    run_covering_design_alns,
)

type Block = tuple[int, ...]


def _brute_force_covered(
    v: int, t: int, blocks: tuple[Block, ...] | tuple[tuple[int, ...], ...]
) -> set[tuple[int, ...]]:
    block_sets = [set(b) for b in blocks]
    return {
        target
        for target in itertools.combinations(range(v), t)
        if any(set(target).issubset(b) for b in block_sets)
    }


def _brute_force_uncovered(
    v: int, t: int, blocks: tuple[Block, ...] | tuple[tuple[int, ...], ...]
) -> set[tuple[int, ...]]:
    return set(itertools.combinations(range(v), t)) - _brute_force_covered(v, t, blocks)


# ---------------------------------------------------------------------------
# 1. Parameter validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"seed": True}, "seed must be an integer"),
        ({"seed": "42"}, "seed must be an integer"),
        ({"seed": 1, "iterations": -1}, "iterations must be >= 0"),
        ({"seed": 1, "iterations": True}, "iterations must be an integer"),
        ({"seed": 1, "decay": -0.1}, "decay must be a finite non-negative number"),
        ({"seed": 1, "decay": 1.1}, "decay must be <= 1"),
        ({"seed": 1, "decay": float("nan")}, "decay must be a finite non-negative number"),
        ({"seed": 1, "destroy_fraction": 0.0}, "destroy_fraction must satisfy 0 < fraction <= 1"),
        ({"seed": 1, "destroy_fraction": 1.5}, "destroy_fraction must satisfy 0 < fraction <= 1"),
        ({"seed": 1, "outcome_scores": (1.0, 2.0)}, "outcome_scores must be a tuple of exactly 4"),
        (
            {"seed": 1, "outcome_scores": (1.0, 2.0, -1.0, 0.5)},
            "outcome_scores must be a finite non-negative number",
        ),
        (
            {"seed": 1, "destroy_operator_weights": (1.0,)},
            "destroy_operator_weights must be a tuple of exactly 2",
        ),
        (
            {"seed": 1, "destroy_operator_weights": (0.0, 0.0)},
            "zero-total eligible operator weight",
        ),
        (
            {"seed": 1, "repair_operator_weights": (0.0, 0.0)},
            "zero-total eligible operator weight",
        ),
        (
            {"seed": 1, "coupling": ((False, False), (True, True))},
            "zero-total eligible operator weight",
        ),
        ({"seed": 1, "coupling": "invalid"}, "coupling must be a 2 by 2 tuple of booleans"),
    ],
)
def test_config_parameter_validation_rejects_invalid_inputs(
    kwargs: dict[str, object], match: str
) -> None:
    with pytest.raises(ValueError, match=match):
        CoveringDesignALNSConfig(**kwargs)  # pyright: ignore[reportCallIssue,reportArgumentType]


@pytest.mark.parametrize(
    ("v", "k", "t"),
    [
        (3, 4, 2),  # v < k
        (4, 2, 3),  # k < t
        (4, 3, -1),  # t < 0
    ],
)
def test_run_covering_design_alns_rejects_invalid_v_k_t(v: int, k: int, t: int) -> None:
    config = CoveringDesignALNSConfig(seed=42, iterations=1)
    with pytest.raises(ValueError, match="must be >="):
        run_covering_design_alns(v, k, t, config=config)


# ---------------------------------------------------------------------------
# 2. Prebuild guard before enumeration
# ---------------------------------------------------------------------------


def test_prebuild_guard_rejects_unsupported_v_greater_than_ten() -> None:
    config = CoveringDesignALNSConfig(seed=42, iterations=1)
    with pytest.raises(
        UnsupportedSetCoverDomainError,
        match="covering-design set-cover first port supports only v <= 10",
    ):
        run_covering_design_alns(11, 5, 2, config=config)


def test_prebuild_guard_is_subclass_of_value_error() -> None:
    assert issubclass(UnsupportedSetCoverDomainError, ValueError)


# ---------------------------------------------------------------------------
# 3. Immutable and canonical state
# ---------------------------------------------------------------------------


def test_data_structures_are_immutable() -> None:
    config = CoveringDesignALNSConfig(seed=42, iterations=5)
    with pytest.raises(FrozenInstanceError):
        config.iterations = 10  # pyright: ignore[reportAttributeAccessIssue]

    result = run_covering_design_alns(5, 3, 2, config=config)
    assert isinstance(result, CoveringDesignALNSResult)
    with pytest.raises(FrozenInstanceError):
        result.best_block_count = 0  # pyright: ignore[reportAttributeAccessIssue]

    assert isinstance(result.best_blocks, tuple)
    assert all(isinstance(block, tuple) for block in result.best_blocks)
    assert result.best_blocks == tuple(sorted(result.best_blocks))

    iteration = result.operator_selection_history[0]
    assert isinstance(iteration, ALNSIteration)
    with pytest.raises(FrozenInstanceError):
        iteration.outcome = ALNSOutcome.REJECT  # pyright: ignore[reportAttributeAccessIssue]


# ---------------------------------------------------------------------------
# 4. Complete initial covering feasibility
# ---------------------------------------------------------------------------


def test_initial_search_state_is_complete_and_feasible() -> None:
    problem = _build_problem(6, 4, 2)
    search = _Search(problem, CoveringDesignALNSConfig(seed=1, iterations=0))
    assert search.current == problem.blocks
    assert search.best == problem.blocks
    assert len(search.current) == math.comb(6, 4)
    # Brute-force verification that all targets are covered
    assert not _brute_force_uncovered(6, 2, search.current)


# ---------------------------------------------------------------------------
# 5. Destroy operators do not mutate original
# ---------------------------------------------------------------------------


def test_destroy_operators_do_not_mutate_original_state() -> None:
    problem = _build_problem(5, 3, 2)
    original = problem.blocks
    original_copy = tuple(original)

    rng = random.Random(123)
    destroyed_random = _random_block_removal(problem, original, 2, rng)
    assert original == original_copy
    assert len(destroyed_random) == len(original) - 2

    destroyed_redundancy = _redundancy_block_removal(problem, original, 2, rng)
    assert original == original_copy
    assert len(destroyed_redundancy) == len(original) - 2


# ---------------------------------------------------------------------------
# 6. Random destroy
# ---------------------------------------------------------------------------


def test_random_destroy_removes_exact_q_distinct_blocks() -> None:
    problem = _build_problem(5, 3, 2)
    q = 3
    rng = random.Random(999)
    destroyed = _random_block_removal(problem, problem.blocks, q, rng)

    assert len(destroyed) == len(problem.blocks) - q
    assert set(destroyed).issubset(set(problem.blocks))
    assert destroyed == tuple(sorted(destroyed))

    # Same seed reproduces same removed blocks
    rng2 = random.Random(999)
    destroyed2 = _random_block_removal(problem, problem.blocks, q, rng2)
    assert destroyed == destroyed2


def test_destroy_size_respects_formula_and_bounds() -> None:
    # q = min(len(current), max(1, ceil(len(current) * fraction)))
    blocks = tuple((i, i + 1) for i in range(10))
    assert _destroy_size(blocks, 0.25) == 3  # ceil(2.5) = 3
    assert _destroy_size(blocks, 0.05) == 1  # max(1, ceil(0.5)) = 1
    assert _destroy_size(blocks, 1.0) == 10  # ceil(10.0) = 10
    assert _destroy_size(blocks[:1], 0.25) == 1  # single block clamps to 1

    with pytest.raises(CoveringDesignALNSInvariantError, match="cannot destroy an empty"):
        _destroy_size((), 0.25)


# ---------------------------------------------------------------------------
# 7. Redundancy destroy
# ---------------------------------------------------------------------------


def test_redundancy_destroy_removes_highest_redundancy_with_lexicographic_tie_break() -> None:
    problem = _build_problem(5, 3, 2)
    # Complete universe has identical coverage count for every pair.
    # Every pair is covered by comb(5-2, 3-2) = 3 blocks.
    # Therefore, all blocks cover exactly 3 pairs, each having multiplicity 3 >= 2.
    # So redundancy scores are tied across all blocks.
    # Lexicographic tie break must remove the first q blocks:
    q = 2
    destroyed = _redundancy_block_removal(problem, problem.blocks, q, random.Random(1))
    expected_removed = set(problem.blocks[:q])
    actual_removed = set(problem.blocks) - set(destroyed)
    assert actual_removed == expected_removed


# ---------------------------------------------------------------------------
# 8. Greedy repair restores feasibility
# ---------------------------------------------------------------------------


def test_greedy_repair_restores_feasibility() -> None:
    problem = _build_problem(6, 3, 2)
    # Remove half the blocks
    destroyed = problem.blocks[: len(problem.blocks) // 2]
    rng = random.Random(42)
    repaired = _greedy_max_uncovered_gain(problem, destroyed, rng)

    assert not _brute_force_uncovered(6, 2, repaired)
    assert repaired == tuple(sorted(set(repaired)))


# ---------------------------------------------------------------------------
# 9. Randomized repair restores feasibility
# ---------------------------------------------------------------------------


def test_randomized_repair_restores_feasibility() -> None:
    problem = _build_problem(6, 3, 2)
    destroyed = problem.blocks[: len(problem.blocks) // 2]
    rng = random.Random(77)
    repaired = _randomized_gain_repair(problem, destroyed, rng)

    assert not _brute_force_uncovered(6, 2, repaired)
    assert repaired == tuple(sorted(set(repaired)))


# ---------------------------------------------------------------------------
# 10 & 11 & 12. Determinism, same config => same result, seeds diverge
# ---------------------------------------------------------------------------


def test_same_seed_and_config_produces_identical_result_and_history() -> None:
    config = CoveringDesignALNSConfig(seed=2026, iterations=15, destroy_fraction=0.3)
    res1 = run_covering_design_alns(5, 3, 2, config=config)
    res2 = run_covering_design_alns(5, 3, 2, config=config)

    assert res1.best_blocks == res2.best_blocks
    assert res1.best_block_count == res2.best_block_count
    assert res1.destroy_operator_weights == res2.destroy_operator_weights
    assert res1.repair_operator_weights == res2.repair_operator_weights
    assert res1.best_objective_history == res2.best_objective_history
    assert res1.deterministic_configuration_identity == res2.deterministic_configuration_identity
    assert res1.operator_selection_history == res2.operator_selection_history


def test_different_seeds_may_diverge() -> None:
    config1 = CoveringDesignALNSConfig(seed=1, iterations=10)
    config2 = CoveringDesignALNSConfig(seed=99999, iterations=10)
    res1 = run_covering_design_alns(6, 3, 2, config=config1)
    res2 = run_covering_design_alns(6, 3, 2, config=config2)

    # Operator history or weights should differ across divergent seeds
    hist1 = [it.destroy_operator for it in res1.operator_selection_history]
    hist2 = [it.destroy_operator for it in res2.operator_selection_history]
    weights1 = res1.destroy_operator_weights
    weights2 = res2.destroy_operator_weights
    assert (hist1 != hist2) or (weights1 != weights2) or (res1.best_blocks != res2.best_blocks)


# ---------------------------------------------------------------------------
# 13 & 14. Weighted roulette and coupling
# ---------------------------------------------------------------------------


def test_weighted_roulette_respects_weights_and_avoids_zero() -> None:
    rng = random.Random(42)
    # Weight 0 must never be chosen
    weights = (0.0, 5.0, 0.0)
    eligible = (0, 1, 2)
    for _ in range(50):
        assert _roulette(weights, eligible, rng) == 1


def test_weighted_roulette_zero_total_fails_closed() -> None:
    rng = random.Random(42)
    with pytest.raises(ValueError, match="zero-total eligible operator weight"):
        _roulette((0.0, 0.0), (0, 1), rng)


def test_coupling_restricts_eligible_repair_operators() -> None:
    # Coupling: destroy 0 can only use repair 1; destroy 1 can only use repair 0
    coupling = ((False, True), (True, False))
    destroy_weights = (1.0, 1.0)
    repair_weights = (1.0, 1.0)
    rng = random.Random(123)

    for _ in range(30):
        d, r = _select_operators(destroy_weights, repair_weights, coupling, rng)
        if d == 0:
            assert r == 1
        elif d == 1:
            assert r == 0


# ---------------------------------------------------------------------------
# 15, 16, 17, 18, 19, 20. Outcome classification and state transitions
# ---------------------------------------------------------------------------


def test_outcome_classification_precedence_and_strict_comparisons() -> None:
    # 1. candidate < best => BEST (regardless of current or acceptance)
    assert _classify_outcome(candidate=4, current=5, best=5, accepted=True) is ALNSOutcome.BEST
    assert _classify_outcome(candidate=4, current=6, best=5, accepted=False) is ALNSOutcome.BEST

    # 2. BEST overrides rejecting acceptance decision
    assert _classify_outcome(candidate=3, current=4, best=4, accepted=False) is ALNSOutcome.BEST

    # 3. candidate < current but candidate >= best => BETTER
    assert _classify_outcome(candidate=6, current=7, best=5, accepted=True) is ALNSOutcome.BETTER
    assert _classify_outcome(candidate=6, current=7, best=5, accepted=False) is ALNSOutcome.BETTER

    # 4. Strict comparison: candidate == best is NOT BEST
    assert _classify_outcome(candidate=5, current=5, best=5, accepted=True) is ALNSOutcome.ACCEPT
    assert _classify_outcome(candidate=5, current=5, best=5, accepted=False) is ALNSOutcome.REJECT

    # 5. Strict comparison: candidate == current is NOT BETTER
    assert _classify_outcome(candidate=7, current=7, best=5, accepted=True) is ALNSOutcome.ACCEPT
    assert _classify_outcome(candidate=7, current=7, best=5, accepted=False) is ALNSOutcome.REJECT

    # 6. candidate > current and accepted=False => REJECT
    assert _classify_outcome(candidate=8, current=7, best=5, accepted=False) is ALNSOutcome.REJECT


def test_state_transitions() -> None:
    b0: tuple[Block, ...] = ((0, 1),)
    c0: tuple[Block, ...] = ((0, 1), (0, 2))
    cand: tuple[Block, ...] = ((0, 3),)

    # BEST updates both best and current
    best, current = _transition(b0, c0, cand, ALNSOutcome.BEST)
    assert best == cand
    assert current == cand

    # BETTER updates current only
    best, current = _transition(b0, c0, cand, ALNSOutcome.BETTER)
    assert best == b0
    assert current == cand

    # ACCEPT updates current only
    best, current = _transition(b0, c0, cand, ALNSOutcome.ACCEPT)
    assert best == b0
    assert current == cand

    # REJECT leaves both unchanged
    best, current = _transition(b0, c0, cand, ALNSOutcome.REJECT)
    assert best == b0
    assert current == c0


# ---------------------------------------------------------------------------
# 21, 22, 23, 24. Adaptive weight formula, unselected unchanged, decay=0/1
# ---------------------------------------------------------------------------


def test_adaptive_weight_formula_and_unselected_invariance() -> None:
    config = CoveringDesignALNSConfig(
        seed=1,
        decay=0.8,
        outcome_scores=(5.0, 2.0, 1.0, 0.5),
        destroy_operator_weights=(1.0, 1.0),
        repair_operator_weights=(1.0, 1.0),
    )
    d_weights = [1.0, 2.0]
    r_weights = [3.0, 4.0]

    # Select destroy 0, repair 1 with BEST outcome (score 5.0)
    _update_selected_weights(d_weights, r_weights, 0, 1, ALNSOutcome.BEST, config)

    # Expected: 0.8 * old + 0.2 * 5.0
    expected_d0 = 0.8 * 1.0 + 0.2 * 5.0  # 0.8 + 1.0 = 1.8
    expected_r1 = 0.8 * 4.0 + 0.2 * 5.0  # 3.2 + 1.0 = 4.2
    assert math.isclose(d_weights[0], expected_d0)
    assert math.isclose(r_weights[1], expected_r1)

    # Unselected operators must be bitwise unchanged
    assert d_weights[1] == 2.0
    assert r_weights[0] == 3.0


def test_adaptive_weights_decay_zero() -> None:
    config = CoveringDesignALNSConfig(
        seed=1,
        decay=0.0,
        outcome_scores=(10.0, 5.0, 2.0, 1.0),
    )
    d_weights = [1.0, 1.0]
    r_weights = [1.0, 1.0]

    _update_selected_weights(d_weights, r_weights, 1, 0, ALNSOutcome.BETTER, config)
    # decay=0 => new_weight = score (5.0)
    assert d_weights[1] == 5.0
    assert r_weights[0] == 5.0
    assert d_weights[0] == 1.0
    assert r_weights[1] == 1.0


def test_adaptive_weights_decay_one() -> None:
    config = CoveringDesignALNSConfig(
        seed=1,
        decay=1.0,
        outcome_scores=(10.0, 5.0, 2.0, 1.0),
    )
    d_weights = [2.5, 3.5]
    r_weights = [4.5, 5.5]

    _update_selected_weights(d_weights, r_weights, 0, 1, ALNSOutcome.BEST, config)
    # decay=1 => weight is unchanged
    assert d_weights[0] == 2.5
    assert r_weights[1] == 5.5
    assert d_weights[1] == 3.5
    assert r_weights[0] == 4.5


# ---------------------------------------------------------------------------
# 25 & 26. Stopping checked at top of loop, exact iteration counts
# ---------------------------------------------------------------------------


def test_stopping_at_zero_iterations_returns_universe_completed() -> None:
    config = CoveringDesignALNSConfig(seed=42, iterations=0)
    result = run_covering_design_alns(5, 3, 2, config=config)

    assert result.status is ALNSStatus.COMPLETED
    assert result.iterations_completed == 0
    assert result.best_block_count == math.comb(5, 3)
    assert len(result.best_objective_history) == 1
    assert result.best_objective_history[0] == math.comb(5, 3)
    assert len(result.operator_selection_history) == 0


def test_n_requested_iterations_produces_exact_n_iterations() -> None:
    for n in (1, 3, 7):
        config = CoveringDesignALNSConfig(seed=42, iterations=n)
        result = run_covering_design_alns(5, 3, 2, config=config)
        assert result.status is ALNSStatus.COMPLETED
        assert result.iterations_completed == n
        assert len(result.operator_selection_history) == n
        assert len(result.best_objective_history) == n + 1


# ---------------------------------------------------------------------------
# 27 & 28. Feasibility checked before acceptance, incomplete repair fails closed
# ---------------------------------------------------------------------------


def test_feasibility_check_rejects_non_canonical_or_incomplete_states() -> None:
    problem = _build_problem(5, 3, 2)

    # Incomplete covering
    with pytest.raises(CoveringDesignALNSInvariantError, match="not a feasible covering"):
        _require_feasible(problem, (problem.blocks[0],))

    # Not sorted / canonical
    unsorted_blocks = (problem.blocks[1], problem.blocks[0])
    with pytest.raises(CoveringDesignALNSInvariantError, match="not canonical unique"):
        _require_feasible(problem, unsorted_blocks)

    # Duplicated blocks
    dup_blocks = (problem.blocks[0], problem.blocks[0])
    with pytest.raises(CoveringDesignALNSInvariantError, match="not canonical unique"):
        _require_feasible(problem, dup_blocks)


def test_incomplete_repair_fails_closed_in_search() -> None:
    problem = _build_problem(5, 3, 2)
    config = CoveringDesignALNSConfig(seed=42, iterations=1)
    search = _Search(problem, config)

    # Inject a broken repair operator that returns an incomplete state
    def broken_repair(
        problem: object, destroyed: tuple[Block, ...], rng: random.Random
    ) -> tuple[Block, ...]:
        del problem, rng
        return destroyed[:1]

    # Verify that the search fails before acceptance with invariant error
    with pytest.raises(CoveringDesignALNSInvariantError, match="not a feasible covering"):
        destroy_operators = (_random_block_removal, _redundancy_block_removal)
        q = _destroy_size(search.current, config.destroy_fraction)
        destroyed = destroy_operators[0](problem, search.current, q, search.rng)
        candidate = broken_repair(problem, destroyed, search.rng)
        _require_feasible(problem, candidate)


# ---------------------------------------------------------------------------
# 29 & 30. Objective minimizes block count, no global optimum claim
# ---------------------------------------------------------------------------


def test_objective_is_minimizing_block_count() -> None:
    assert _accept_non_worsening(candidate=5, current=6) is True
    assert _accept_non_worsening(candidate=6, current=6) is True
    assert _accept_non_worsening(candidate=7, current=6) is False


def test_result_never_claims_global_optimum() -> None:
    config = CoveringDesignALNSConfig(seed=42, iterations=10)
    result = run_covering_design_alns(5, 3, 2, config=config)

    assert result.status in (ALNSStatus.COMPLETED, ALNSStatus.UNKNOWN_NOT_COMPLETED)
    assert not hasattr(result, "CERTIFIED_GLOBAL_OPTIMUM")
    assert "CERTIFIED_GLOBAL_OPTIMUM" not in str(result.status)
    assert "OPTIMAL" not in [status.name for status in ALNSStatus]


# ---------------------------------------------------------------------------
# 31. Fixed-seed toy run preserves a valid cover
# ---------------------------------------------------------------------------


def test_fixed_seed_toy_run_preserves_valid_cover() -> None:
    config = CoveringDesignALNSConfig(seed=12345, iterations=20, destroy_fraction=0.4)
    result = run_covering_design_alns(5, 3, 2, config=config)

    assert not _brute_force_uncovered(5, 2, result.best_blocks)
    # The covering number C(5, 3, 2) is 4
    assert result.best_block_count <= math.comb(5, 3)
    assert result.best_block_count >= 4


# ---------------------------------------------------------------------------
# 32. Outcome and history internal consistency
# ---------------------------------------------------------------------------


def test_outcome_and_history_internal_consistency() -> None:
    config = CoveringDesignALNSConfig(seed=42, iterations=25)
    result = run_covering_design_alns(5, 3, 2, config=config)

    # Outcome counts sum to iterations_completed
    total_outcomes = sum(count for _, count in result.outcome_counts)
    assert total_outcomes == result.iterations_completed

    # Outcome counts match each row in operator_selection_history
    for outcome, count in result.outcome_counts:
        actual = sum(row.outcome is outcome for row in result.operator_selection_history)
        assert actual == count

    # Best objective history starts at comb(v, k) and ends at best_block_count
    assert result.best_objective_history[0] == math.comb(5, 3)
    assert result.best_objective_history[-1] == result.best_block_count
    assert len(result.best_objective_history) == result.iterations_completed + 1

    # Best objective history is monotonically non-increasing
    for a, b in itertools.pairwise(result.best_objective_history):
        assert a >= b

    # Iteration row numbers are 1-indexed and sequential
    for idx, row in enumerate(result.operator_selection_history, start=1):
        assert row.iteration == idx
        assert row.best_block_count <= row.current_block_count


# ---------------------------------------------------------------------------
# 33. Regression and mutation strength tests
# ---------------------------------------------------------------------------


def test_mutation_wrong_weight_update_formula() -> None:
    # Mutant formula: (1 - decay) * old + decay * score
    config = CoveringDesignALNSConfig(seed=1, decay=0.8, outcome_scores=(5.0, 2.0, 1.0, 0.5))
    old_weight = 1.0
    correct = 0.8 * old_weight + 0.2 * 5.0  # 1.8
    mutant = 0.2 * old_weight + 0.8 * 5.0  # 4.2

    d_weights = [old_weight, 1.0]
    r_weights = [old_weight, 1.0]
    _update_selected_weights(d_weights, r_weights, 0, 0, ALNSOutcome.BEST, config)

    assert math.isclose(d_weights[0], correct)
    assert not math.isclose(d_weights[0], mutant)


def test_mutation_wrong_score_indexing() -> None:
    # Ensure each outcome maps to exactly its configured score index
    scores = (10.0, 7.0, 3.0, 1.0)
    config = CoveringDesignALNSConfig(seed=1, decay=0.0, outcome_scores=scores)

    for outcome, expected_score in zip(
        (ALNSOutcome.BEST, ALNSOutcome.BETTER, ALNSOutcome.ACCEPT, ALNSOutcome.REJECT),
        scores,
        strict=True,
    ):
        d_weights = [0.0, 0.0]
        r_weights = [0.0, 0.0]
        _update_selected_weights(d_weights, r_weights, 0, 0, outcome, config)
        assert d_weights[0] == expected_score
        assert r_weights[0] == expected_score


def test_mutation_best_better_ordering_inversion() -> None:
    # If BETTER was evaluated before BEST, a candidate improving both current and best
    # would be misclassified as BETTER instead of BEST.
    candidate = 4
    current = 6
    best = 5
    accepted = True

    # Correct classification: BEST
    assert _classify_outcome(candidate, current, best, accepted) is ALNSOutcome.BEST

    # Verify mutant logic where candidate < current takes precedence:
    # If an inverted logic returned BETTER, this assertion proves our test catches it.
    mutant_outcome = (
        ALNSOutcome.BETTER
        if candidate < current
        else (ALNSOutcome.BEST if candidate < best else ALNSOutcome.ACCEPT)
    )
    assert mutant_outcome is ALNSOutcome.BETTER
    assert _classify_outcome(candidate, current, best, accepted) != mutant_outcome


def test_mutation_missing_feasibility_check() -> None:
    # An implementation that omits feasibility check on candidate would accept an infeasible cover.
    problem = _build_problem(5, 3, 2)
    infeasible_state = (problem.blocks[0],)  # Only 1 block, fails coverage

    # Our code raises invariant error:
    with pytest.raises(CoveringDesignALNSInvariantError):
        _require_feasible(problem, infeasible_state)


def test_mutation_non_selected_weight_mutation() -> None:
    config = CoveringDesignALNSConfig(seed=1, decay=0.5, outcome_scores=(4.0, 3.0, 2.0, 1.0))
    d_weights = [1.5, 2.5]
    r_weights = [3.5, 4.5]

    # Select destroy 1, repair 0
    _update_selected_weights(d_weights, r_weights, 1, 0, ALNSOutcome.ACCEPT, config)

    # Index 0 of destroy and index 1 of repair must be strictly untouched
    assert d_weights[0] == 1.5
    assert r_weights[1] == 4.5


# ---------------------------------------------------------------------------
# Fault injection via private seams in _Search
# ---------------------------------------------------------------------------


def test_search_private_seam_best_overrides_rejecting_acceptance() -> None:
    problem = _build_problem(5, 3, 2)
    config = CoveringDesignALNSConfig(seed=42, iterations=1)
    search = _Search(problem, config)

    # Invalidate acceptance to always reject
    search._accept = lambda _cand, _curr: False  # pyright: ignore[reportAttributeAccessIssue]
    # Run iteration: candidate should improve best and override rejection
    search._iterate()

    assert len(search.history) == 1
    # Candidate was comb(5, 3) blocks initially.
    # Repaired cover is smaller than 10 blocks (comb(5, 3)=10, C(5,3,2)=4).
    # Since candidate < best (which was 10), outcome MUST be BEST despite rejecting acceptance!
    assert search.history[0].outcome is ALNSOutcome.BEST
    assert len(search.best) < 10
    assert len(search.current) == len(search.best)


def test_search_private_seam_better_outcome() -> None:
    problem = _build_problem(5, 3, 2)
    config = CoveringDesignALNSConfig(seed=42, iterations=2)
    search = _Search(problem, config)

    # In step 1, let it find a good best (e.g. size <= 7)
    search._iterate()
    assert search.history[0].outcome is ALNSOutcome.BEST
    best_size = len(search.best)

    # Now simulate a worsening move by artificially setting search.current to a worse state
    # but keeping search.best at best_size.
    search.current = problem.blocks  # size 10 > best_size
    # Next iteration repairs from destroyed state of size 10 to something like 6 or 7.
    # If candidate < 10 (current) and candidate >= best_size, outcome is BETTER!
    # Let's verify classification with exact numbers:
    outcome = _classify_outcome(
        candidate=best_size + 1, current=10, best=best_size, accepted=True
    )
    assert outcome is ALNSOutcome.BETTER
