# pyright: reportPrivateUsage=false

"""Focused contract tests for the research-only GRASP + path-relinking heuristic."""

from __future__ import annotations

import ast
import dataclasses
import inspect
import itertools
import random
from collections.abc import Sequence
from typing import NoReturn

import pytest
from ortools.sat.python import cp_model

from lottolab.research import covering_design_grasp_pr as grasp_module
from lottolab.research.covering_design_grasp_pr import (
    MAX_TOTAL_EVALUATED_SOLUTIONS,
    CoveringDesignGraspPRConfig,
    CoveringDesignGraspPRInvariantError,
    CoveringDesignGraspPRStatus,
    UnsupportedSetCoverDomainError,
    _build_problem,
    _construct_solution,
    _distance,
    _eliminate_redundant_blocks,
    _ElitePool,
    _EvaluationBudget,
    _greedy_ratio,
    _marginal_gain,
    _rcl_threshold,
    _relink_forward,
    _restricted_candidate_list,
    _select_guide,
    _solution_key,
    run_covering_design_grasp_pr,
)

type Selection = tuple[int, ...]

V5K3T2 = (5, 3, 2)
V6K3T2 = (6, 3, 2)
V7K3T2 = (7, 3, 2)

# Path-relinking fixture on C(5,3,2), verified by hand. Candidate indices are
# lexicographic 3-subsets of range(5): 0=(0,1,2) 1=(0,1,3) 2=(0,1,4) 3=(0,2,3)
# 4=(0,2,4) 5=(0,3,4) 6=(1,2,3) 7=(1,2,4) 8=(1,3,4) 9=(2,3,4).
# Both endpoints cost 5, the single intermediate costs 4.
PATH_INIT: Selection = (0, 1, 2, 3, 9)
PATH_GUIDE: Selection = (0, 1, 2, 5, 9)
PATH_EXPECTED_BEST: Selection = (0, 1, 2, 9)


def _config(**overrides: object) -> CoveringDesignGraspPRConfig:
    base: dict[str, object] = {"seed": 7, "alpha": 0.3, "iteration_count": 12}
    base.update(overrides)
    return CoveringDesignGraspPRConfig(**base)  # pyright: ignore[reportArgumentType]


def _budget() -> _EvaluationBudget:
    return _EvaluationBudget(MAX_TOTAL_EVALUATED_SOLUTIONS)


def _mixed_gain_state(
    domain: tuple[int, int, int], picks: tuple[int, ...]
) -> tuple[grasp_module._Problem, Selection, int]:
    """A mid-construction state whose remaining marginal gains are not all equal."""

    problem = _build_problem(*domain)
    mask = problem.all_targets_mask
    for index in picks:
        mask &= ~problem.coverage_masks[index]
    available = tuple(i for i in range(problem.candidate_count) if i not in picks)
    return problem, available, mask


def _random_feasible_selections(
    problem: grasp_module._Problem, count: int, seed: int = 11
) -> list[Selection]:
    rng = random.Random(seed)
    found: set[Selection] = set()
    indices = list(range(problem.candidate_count))
    for _ in range(20_000):
        size = rng.randint(2, min(8, problem.candidate_count))
        selection = tuple(sorted(rng.sample(indices, size)))
        if grasp_module._covers_all_targets(problem, selection):
            found.add(selection)
        if len(found) >= count:
            break
    return sorted(found)


# ---------------------------------------------------------------------------
# 1. v/k/t validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("domain", [(3, 4, 2), (5, 2, 3), (-1, 1, 1), (5, 3, -1)])
def test_invalid_domain_parameters_are_rejected(domain: tuple[int, int, int]) -> None:
    with pytest.raises(ValueError):
        run_covering_design_grasp_pr(*domain, config=_config())


def test_domain_outside_guarded_envelope_is_rejected() -> None:
    with pytest.raises(UnsupportedSetCoverDomainError):
        run_covering_design_grasp_pr(11, 3, 2, config=_config())


# ---------------------------------------------------------------------------
# 2. Prebuild guard runs before enumeration
# ---------------------------------------------------------------------------


def test_guard_rejects_before_any_candidate_enumeration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # If enumeration ever ran first, this sabotaged combinations would raise
    # AssertionError instead of the guard's UnsupportedSetCoverDomainError.
    def _forbidden(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        raise AssertionError("enumeration ran before the prebuild guard")

    monkeypatch.setattr(grasp_module.itertools, "combinations", _forbidden)
    with pytest.raises(UnsupportedSetCoverDomainError):
        run_covering_design_grasp_pr(11, 3, 2, config=_config())


def test_guard_identity_is_recorded_on_the_built_problem() -> None:
    problem = _build_problem(*V5K3T2)
    assert "setcover-ilp-envelope" in problem.guard_identity


# ---------------------------------------------------------------------------
# 3. Canonical incidence
# ---------------------------------------------------------------------------


def test_candidates_and_targets_are_canonical_lexicographic() -> None:
    problem = _build_problem(*V5K3T2)
    assert problem.candidates == tuple(itertools.combinations(range(5), 3))
    assert problem.targets == tuple(itertools.combinations(range(5), 2))
    assert problem.candidate_count == 10
    assert problem.target_count == 10


def test_coverage_masks_match_independent_subset_enumeration() -> None:
    problem = _build_problem(*V5K3T2)
    for index, block in enumerate(problem.candidates):
        expected = 0
        for target_index, target in enumerate(problem.targets):
            if set(target) <= set(block):
                expected |= 1 << target_index
        assert problem.coverage_masks[index] == expected
    assert problem.all_targets_mask == (1 << problem.target_count) - 1


# ---------------------------------------------------------------------------
# 4. Config validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("alpha", [-0.001, 1.001, float("nan"), float("inf")])
def test_alpha_outside_unit_interval_is_rejected(alpha: float) -> None:
    with pytest.raises(ValueError, match="alpha"):
        _config(alpha=alpha)


@pytest.mark.parametrize("alpha", [0.0, 0.5, 1.0, 0, 1])
def test_alpha_inside_unit_interval_is_accepted(alpha: float) -> None:
    assert _config(alpha=alpha).alpha == alpha


def test_alpha_is_required_and_has_no_default() -> None:
    # Characterization found no donor or literature authority for a canonical
    # alpha, so the caller must state one; a default would be an invention.
    with pytest.raises(TypeError):
        CoveringDesignGraspPRConfig(seed=1)  # pyright: ignore[reportCallIssue]
    fields = grasp_module.CoveringDesignGraspPRConfig.__dataclass_fields__
    assert fields["alpha"].default is dataclasses.MISSING


@pytest.mark.parametrize(
    "overrides",
    [
        {"seed": 1.5},
        {"seed": True},
        {"iteration_count": 0},
        {"elite_size": 0},
        {"elite_diversity_threshold": 0},
        {"max_path_length": 0},
        {"iteration_count": 1.5},
        {"elite_size": True},
    ],
)
def test_invalid_configuration_is_rejected(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        _config(**overrides)


def test_documented_defaults_are_stable() -> None:
    config = CoveringDesignGraspPRConfig(seed=1, alpha=0.5)
    assert config.iteration_count == 100
    assert config.elite_size == 10
    assert config.elite_diversity_threshold == 1
    assert config.max_path_length == 64


# ---------------------------------------------------------------------------
# 5. Isolated RNG
# ---------------------------------------------------------------------------


def test_run_is_independent_of_global_random_state() -> None:
    config = _config()
    random.seed(1234)
    first = run_covering_design_grasp_pr(*V6K3T2, config=config)
    random.seed(999_999)
    [random.random() for _ in range(50)]
    second = run_covering_design_grasp_pr(*V6K3T2, config=config)
    assert first == second


def test_run_owns_exactly_one_random_instance_seeded_from_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seeds: list[object] = []
    real_random = random.Random

    class _RecordingRandom(real_random):
        def __init__(self, seed: object = None) -> None:
            seeds.append(seed)
            super().__init__(seed)  # pyright: ignore[reportArgumentType]

    monkeypatch.setattr(grasp_module.random, "Random", _RecordingRandom)
    run_covering_design_grasp_pr(*V5K3T2, config=_config(seed=4321))
    assert seeds == [4321]


def test_module_never_uses_the_module_global_rng() -> None:
    source = ast.parse(inspect.getsource(grasp_module))
    offenders: list[str] = []
    for node in ast.walk(source):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "random"
            and node.attr != "Random"
        ):
            offenders.append(node.attr)
    assert offenders == []


# ---------------------------------------------------------------------------
# 6. Same-seed reproducibility
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("domain", [V5K3T2, V6K3T2, V7K3T2])
def test_same_seed_reproduces_every_audit_field(domain: tuple[int, int, int]) -> None:
    config = _config(seed=99, alpha=0.4, iteration_count=15)
    first = run_covering_design_grasp_pr(*domain, config=config)
    second = run_covering_design_grasp_pr(*domain, config=config)
    assert first == second
    assert first.best_objective_history == second.best_objective_history
    assert first.deterministic_configuration_identity == (
        second.deterministic_configuration_identity
    )


def test_different_seeds_are_reachable_and_identity_tracks_configuration() -> None:
    a = run_covering_design_grasp_pr(*V6K3T2, config=_config(seed=1))
    b = run_covering_design_grasp_pr(*V6K3T2, config=_config(seed=2))
    assert a.deterministic_configuration_identity != b.deterministic_configuration_identity
    assert '"seed":1' in a.deterministic_configuration_identity


# ---------------------------------------------------------------------------
# 7. Exact marginal gain
# ---------------------------------------------------------------------------


def test_marginal_gain_counts_only_newly_covered_targets() -> None:
    problem = _build_problem(*V5K3T2)
    full = problem.all_targets_mask
    assert _marginal_gain(problem, 0, full) == 3
    after_zero = full & ~problem.coverage_masks[0]
    assert _marginal_gain(problem, 0, after_zero) == 0
    assert _marginal_gain(problem, 5, after_zero) == 3
    assert _marginal_gain(problem, 1, after_zero) == 2


# ---------------------------------------------------------------------------
# 8. Exact ratio
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("gain", "expected"), [(1, 1.0), (2, 0.5), (4, 0.25)])
def test_greedy_ratio_is_the_reciprocal_of_gain(gain: int, expected: float) -> None:
    assert _greedy_ratio(gain) == expected


@pytest.mark.parametrize("gain", [0, -1])
def test_greedy_ratio_fails_closed_on_non_positive_gain(gain: int) -> None:
    with pytest.raises(CoveringDesignGraspPRInvariantError):
        _greedy_ratio(gain)


# ---------------------------------------------------------------------------
# 9. RCL cutoff formula
# ---------------------------------------------------------------------------


def test_rcl_threshold_matches_the_frozen_convex_cutoff() -> None:
    c_min, c_max = 1.0 / 3.0, 1.0 / 1.0
    assert _rcl_threshold(c_min, c_max, 0.0) == c_min
    assert _rcl_threshold(c_min, c_max, 1.0) == c_max
    assert _rcl_threshold(c_min, c_max, 0.5) == pytest.approx(c_min + 0.5 * (c_max - c_min))
    assert _rcl_threshold(c_min, c_max, 0.25) == pytest.approx(c_min + 0.25 * (c_max - c_min))


def test_rcl_threshold_is_exact_at_endpoints_where_the_literal_form_is_not() -> None:
    # The literal `c_min + alpha*(c_max-c_min)` underflows below c_max for these
    # reciprocal ratios, which would silently drop the minimum-gain candidates
    # from the RCL at alpha=1. The convex form must not.
    c_min, c_max = 1.0 / 14.0, 1.0 / 3.0
    assert c_min + 1.0 * (c_max - c_min) < c_max
    assert _rcl_threshold(c_min, c_max, 1.0) == c_max
    assert _rcl_threshold(c_min, c_max, 0.0) == c_min


def test_rcl_threshold_never_leaves_the_ratio_interval() -> None:
    c_min, c_max = 1.0 / 7.0, 1.0 / 2.0
    for step in range(101):
        value = _rcl_threshold(c_min, c_max, step / 100)
        assert c_min <= value <= c_max


def test_rcl_cutoff_is_inclusive_at_the_threshold() -> None:
    # A `<` cutoff would return an empty RCL here, because at alpha=0 every
    # admitted ratio is exactly equal to the threshold.
    problem, available, mask = _mixed_gain_state(V5K3T2, (0,))
    rcl = _restricted_candidate_list(problem, available, mask, 0.0)
    ratios = [_greedy_ratio(_marginal_gain(problem, i, mask)) for i in rcl]
    threshold = _rcl_threshold(min(ratios), max(ratios), 0.0)
    assert rcl
    assert all(ratio == threshold for ratio in ratios)


def test_rcl_size_moves_with_alpha_on_a_three_level_state() -> None:
    # Gains 3/2/1 are all present here, so each alpha selects a different
    # prefix of the ratio ladder; removing or reversing the alpha term changes
    # at least one of these three sizes.
    problem, available, mask = _mixed_gain_state(V6K3T2, (0, 1))
    levels = {_marginal_gain(problem, i, mask) for i in available}
    assert {1, 2, 3} <= levels
    assert len(_restricted_candidate_list(problem, available, mask, 0.0)) == 6
    assert len(_restricted_candidate_list(problem, available, mask, 0.5)) == 16
    assert len(_restricted_candidate_list(problem, available, mask, 1.0)) == 18


# ---------------------------------------------------------------------------
# 10. alpha=0 admits every argmin tie
# ---------------------------------------------------------------------------


def test_alpha_zero_admits_all_minimum_ratio_ties() -> None:
    problem, available, mask = _mixed_gain_state(V5K3T2, (0,))
    gains = {i: _marginal_gain(problem, i, mask) for i in available}
    best_gain = max(gains.values())
    expected = tuple(sorted(i for i, gain in gains.items() if gain == best_gain))
    assert len(expected) > 1
    assert _restricted_candidate_list(problem, available, mask, 0.0) == expected


# ---------------------------------------------------------------------------
# 11. alpha=0 is not deterministic greedy
# ---------------------------------------------------------------------------


def test_alpha_zero_produces_multiple_distinct_constructions_across_seeds() -> None:
    # Characterization: alpha=0 is greedy PLUS uniform random tie-breaking, not
    # deterministic greedy. Bypassing the tie randomization collapses this set.
    problem = _build_problem(*V7K3T2)
    config = _config(alpha=0.0)
    seen = {
        _construct_solution(problem, config, random.Random(seed), _budget()) for seed in range(120)
    }
    assert len(seen) > 1


# ---------------------------------------------------------------------------
# 12. alpha=1 admits every positive-gain candidate
# ---------------------------------------------------------------------------


def test_alpha_one_admits_all_positive_gain_candidates() -> None:
    problem, available, mask = _mixed_gain_state(V5K3T2, (0,))
    expected = tuple(sorted(i for i in available if _marginal_gain(problem, i, mask) > 0))
    assert _restricted_candidate_list(problem, available, mask, 1.0) == expected
    assert len(expected) > len(_restricted_candidate_list(problem, available, mask, 0.0))


# ---------------------------------------------------------------------------
# 13. c_min == c_max degeneracy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("alpha", [0.0, 0.25, 0.5, 0.75, 1.0])
def test_equal_ratios_admit_all_positive_gain_candidates_at_every_alpha(
    alpha: float,
) -> None:
    # Every k-block covers exactly C(k,t) targets, so at construction step 1
    # all ratios coincide and alpha is inert. Reproduces the characterization's
    # |RCL| = 35/35 observation on C(7,3,2).
    problem = _build_problem(*V7K3T2)
    available = tuple(range(problem.candidate_count))
    rcl = _restricted_candidate_list(problem, available, problem.all_targets_mask, alpha)
    assert rcl == available
    assert len(rcl) == 35


# ---------------------------------------------------------------------------
# 14. Zero-gain exclusion
# ---------------------------------------------------------------------------


def test_zero_gain_candidates_never_enter_the_rcl() -> None:
    problem, available, mask = _mixed_gain_state(V5K3T2, ())
    mask &= ~problem.coverage_masks[0]
    zero_gain = tuple(i for i in available if _marginal_gain(problem, i, mask) == 0)
    assert zero_gain == (0,)
    for alpha in (0.0, 0.5, 1.0):
        assert not set(zero_gain) & set(_restricted_candidate_list(problem, available, mask, alpha))


# ---------------------------------------------------------------------------
# 15. Canonical RCL order precedes every random draw
# ---------------------------------------------------------------------------


def test_rcl_is_canonically_ordered_before_every_random_choice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Same-seed reproducibility alone would still pass with a consistently
    # reversed RCL; this inspects the exact sequence handed to rng.choice.
    captured: list[tuple[int, ...]] = []
    real_choice = random.Random.choice

    def _recording_choice(self: random.Random, seq: Sequence[int]) -> int:
        captured.append(tuple(seq))
        return real_choice(self, seq)

    monkeypatch.setattr(random.Random, "choice", _recording_choice)
    _construct_solution(_build_problem(*V6K3T2), _config(), random.Random(3), _budget())
    assert captured
    assert all(seq == tuple(sorted(seq)) for seq in captured)


# ---------------------------------------------------------------------------
# 16. Construction feasibility
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("domain", [V5K3T2, V6K3T2, V7K3T2, (4, 3, 3)])
@pytest.mark.parametrize("alpha", [0.0, 0.5, 1.0])
def test_construction_always_covers_every_target(
    domain: tuple[int, int, int], alpha: float
) -> None:
    problem = _build_problem(*domain)
    for seed in range(8):
        selection = _construct_solution(
            problem, _config(alpha=alpha), random.Random(seed), _budget()
        )
        assert grasp_module._covers_all_targets(problem, selection)
        assert selection == tuple(sorted(set(selection)))


# ---------------------------------------------------------------------------
# 17. Impossible construction fails closed
# ---------------------------------------------------------------------------


def test_construction_fails_closed_when_no_positive_gain_candidate_remains() -> None:
    unreachable = grasp_module._Problem(
        v=3,
        k=2,
        t=1,
        candidates=((0, 1),),
        targets=((0,), (1,)),
        candidate_count=1,
        target_count=2,
        coverage_masks=(0b01,),
        all_targets_mask=0b11,
        guard_identity="synthetic",
    )
    with pytest.raises(CoveringDesignGraspPRInvariantError, match="no positive-gain"):
        _construct_solution(unreachable, _config(), random.Random(0), _budget())


# ---------------------------------------------------------------------------
# 18. Repeated redundant-block elimination
# ---------------------------------------------------------------------------


def test_redundant_elimination_runs_repeated_passes_to_a_fixpoint() -> None:
    # A single pass cannot reach the 4-block fixpoint from this 10-block input:
    # it removes one block, then must restart a fresh canonical pass.
    problem = _build_problem(*V5K3T2)
    everything = tuple(range(problem.candidate_count))
    reduced = _eliminate_redundant_blocks(problem, everything, _budget())
    assert grasp_module._covers_all_targets(problem, reduced)
    assert len(reduced) < len(everything)
    assert _eliminate_redundant_blocks(problem, reduced, _budget()) == reduced


def test_redundant_elimination_removes_the_first_removable_in_canonical_order() -> None:
    problem = _build_problem(*V5K3T2)
    base = (0, 1, 2, 3, 9)
    removable = [
        index
        for index in base
        if grasp_module._covers_all_targets(
            problem, tuple(other for other in base if other != index)
        )
    ]
    assert len(removable) >= 1
    result = _eliminate_redundant_blocks(problem, base, _budget())
    assert removable[0] not in result


def test_redundant_elimination_terminates_when_nothing_is_removable() -> None:
    problem = _build_problem(*V5K3T2)
    minimal = _eliminate_redundant_blocks(problem, tuple(range(10)), _budget())
    budget = _budget()
    assert _eliminate_redundant_blocks(problem, minimal, budget) == minimal
    assert budget.count == 0


# ---------------------------------------------------------------------------
# 19. The dead donor swap operator is absent
# ---------------------------------------------------------------------------


def test_local_improvement_only_ever_removes_blocks() -> None:
    # A 1-for-1 swap would substitute a block not present in the input. The
    # donor's swap is provably dead under unit cost and is not ported.
    problem = _build_problem(*V6K3T2)
    checked = 0
    for selection in _random_feasible_selections(problem, 60):
        result = _eliminate_redundant_blocks(problem, selection, _budget())
        assert set(result) <= set(selection)
        assert len(result) <= len(selection)
        checked += 1
    assert checked >= 10


def test_module_defines_no_swap_or_exchange_operator() -> None:
    tree = ast.parse(inspect.getsource(grasp_module))
    names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert not any("swap" in name or "exchange" in name for name in names)


# ---------------------------------------------------------------------------
# 20-24. Elite pool
# ---------------------------------------------------------------------------


def _pool(max_size: int = 3, threshold: int = 1) -> _ElitePool:
    return _ElitePool(_build_problem(*V5K3T2), max_size, threshold)


def test_elite_pool_rejects_an_exact_duplicate() -> None:
    pool = _pool()
    assert pool.admit((0, 1, 2)) is True
    assert pool.admit((0, 1, 2)) is False
    assert pool.members == [(0, 1, 2)]


def test_elite_pool_never_exceeds_its_size_cap() -> None:
    pool = _pool(max_size=3)
    for selection in [(0, 1), (0, 2), (0, 3), (0, 4), (0, 5), (1, 2)]:
        pool.admit(selection)
        assert len(pool.members) <= 3
    assert len(pool.members) == 3


def test_configured_diversity_threshold_blocks_a_near_duplicate() -> None:
    # At threshold 1 the gate is inert (duplicates are already rejected); at
    # threshold 3 an equal-cost candidate one swap away must be refused.
    near: Selection = (0, 1, 9)
    permissive = _pool(max_size=2, threshold=1)
    strict = _pool(max_size=2, threshold=3)
    for pool in (permissive, strict):
        pool.admit((0, 1, 2))
        pool.admit((0, 1, 3))
    assert _distance(near, (0, 1, 2)) == 2
    assert permissive.admit(near) is True
    assert strict.admit(near) is False


def test_full_pool_admits_a_strictly_better_candidate_and_evicts_one() -> None:
    pool = _pool(max_size=2)
    pool.admit((0, 1, 2, 3))
    pool.admit((0, 1, 2, 4))
    assert pool.admit((5, 6)) is True
    assert (5, 6) in pool.members
    assert len(pool.members) == 2


def test_full_pool_rejects_a_strictly_worse_candidate() -> None:
    pool = _pool(max_size=2)
    pool.admit((0, 1))
    pool.admit((0, 2))
    assert pool.admit((3, 4, 5, 6, 7)) is False
    assert len(pool.members) == 2


def test_replacement_evicts_the_closest_member_no_cheaper_than_the_candidate() -> None:
    pool = _pool(max_size=2)
    pool.admit((0, 1, 2))
    pool.admit((5, 6, 7))
    candidate: Selection = (0, 1, 8)
    assert _distance(candidate, (0, 1, 2)) == 2
    assert _distance(candidate, (5, 6, 7)) == 6
    assert pool.admit(candidate) is True
    assert (0, 1, 2) not in pool.members
    assert (5, 6, 7) in pool.members


def test_replacement_breaks_a_distance_tie_on_the_canonical_solution_key() -> None:
    pool = _pool(max_size=2)
    pool.admit((0, 1, 2))
    pool.admit((0, 1, 3))
    candidate: Selection = (0, 4, 5)
    assert _distance(candidate, (0, 1, 2)) == _distance(candidate, (0, 1, 3)) == 4
    problem = _build_problem(*V5K3T2)
    assert _solution_key(problem, (0, 1, 2)) < _solution_key(problem, (0, 1, 3))
    assert pool.admit(candidate) is True
    assert (0, 1, 2) not in pool.members
    assert (0, 1, 3) in pool.members


def test_replacement_fails_closed_when_no_member_is_removable() -> None:
    pool = _pool(max_size=1)
    pool.members.append((0, 1))
    with pytest.raises(CoveringDesignGraspPRInvariantError, match="no member is removable"):
        pool._replace_with((0, 1, 2, 3))


# ---------------------------------------------------------------------------
# 25. Symmetric-difference distance
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [((0, 1), (0, 1), 0), ((0, 1), (0, 2), 2), ((0, 1), (2, 3), 4), ((0, 1, 2), (0, 1), 1)],
)
def test_distance_is_symmetric_difference_cardinality(
    left: Selection, right: Selection, expected: int
) -> None:
    assert _distance(left, right) == expected
    assert _distance(right, left) == expected


# ---------------------------------------------------------------------------
# 26. Guide selection
# ---------------------------------------------------------------------------


def test_guide_is_the_most_distant_eligible_elite() -> None:
    problem = _build_problem(*V5K3T2)
    pool = _pool(max_size=5)
    for selection in [(0, 1, 2), (0, 1, 3), (5, 6, 7, 8)]:
        pool.admit(selection)
    current: Selection = (0, 1, 2)
    distances = {member: _distance(member, current) for member in pool.members}
    assert max(distances.values()) == distances[(5, 6, 7, 8)]
    assert _select_guide(problem, pool, current) == (5, 6, 7, 8)


def test_guide_selection_breaks_a_distance_tie_on_the_canonical_key() -> None:
    problem = _build_problem(*V5K3T2)
    pool = _pool(max_size=5)
    pool.admit((3, 4))
    pool.admit((5, 6))
    current: Selection = (0, 1)
    assert _distance((3, 4), current) == _distance((5, 6), current) == 4
    assert _solution_key(problem, (3, 4)) < _solution_key(problem, (5, 6))
    assert _select_guide(problem, pool, current) == (3, 4)


def test_guide_selection_skips_zero_distance_members_and_may_be_absent() -> None:
    problem = _build_problem(*V5K3T2)
    empty = _pool()
    assert _select_guide(problem, empty, (0, 1, 2)) is None
    identical = _pool()
    identical.admit((0, 1, 2))
    assert _select_guide(problem, identical, (0, 1, 2)) is None


# ---------------------------------------------------------------------------
# 27-32. Path relinking trajectory
# ---------------------------------------------------------------------------


def _trace_path(
    problem: grasp_module._Problem, initiating: Selection, guide: Selection
) -> list[Selection]:
    """Re-run the documented move rule independently and record every state.

    This is an oracle, not the implementation. Every caller that relies on it
    also asserts that ``_relink_forward`` itself returns the best state of the
    trajectory recorded here, so a divergence between the two is a failure
    rather than a silently self-consistent reimplementation.
    """

    states: list[Selection] = []
    current = initiating
    while set(current) != set(guide):
        moves: list[tuple[int, int, Selection]] = []
        for index in sorted(set(current) ^ set(guide)):
            if index in current:
                trial = tuple(other for other in current if other != index)
                delta = -1
            else:
                trial = tuple(sorted((*current, index)))
                delta = 1
            if grasp_module._covers_all_targets(problem, trial):
                moves.append((delta, index, trial))
        assert moves
        moves.sort(key=lambda move: (move[0], move[1]))
        current = moves[0][2]
        states.append(current)
    return states


def test_relink_forward_agrees_with_the_independent_trajectory_oracle() -> None:
    # Binds the oracle above to the real implementation: the returned solution
    # must be the best state of the independently traced trajectory, including
    # both endpoints. Without this the trajectory tests would only prove the
    # oracle self-consistent.
    problem = _build_problem(*V6K3T2)
    selections = _random_feasible_selections(problem, 24)
    checked = 0
    for initiating, guide in itertools.combinations(selections, 2):
        if _distance(initiating, guide) == 0:
            continue
        traced = [initiating, *_trace_path(problem, initiating, guide)]
        expected = min(traced, key=lambda state: _solution_key(problem, state))
        assert _relink_forward(problem, initiating, guide, _budget()) == expected
        checked += 1
    assert checked >= 10


def test_every_move_is_a_single_toggle_from_the_symmetric_difference() -> None:
    problem = _build_problem(*V5K3T2)
    states = _trace_path(problem, PATH_INIT, PATH_GUIDE)
    previous = PATH_INIT
    assert states
    for state in states:
        assert _distance(previous, state) == 1
        changed = set(previous) ^ set(state)
        assert len(changed) == 1
        assert changed <= set(PATH_INIT) ^ set(PATH_GUIDE)
        previous = state


def test_every_intermediate_state_is_a_feasible_covering() -> None:
    problem = _build_problem(*V5K3T2)
    for state in _trace_path(problem, PATH_INIT, PATH_GUIDE):
        assert grasp_module._covers_all_targets(problem, state)


def test_infeasible_removals_are_excluded_from_the_move_universe() -> None:
    # Removing candidate 5 = (0,3,4) here loses target (3,4) entirely, so it
    # must never be selected even though it is in the symmetric difference.
    problem = _build_problem(*V5K3T2)
    current: Selection = (0, 1, 2, 3, 4, 5)
    guide: Selection = (0, 1, 2, 3, 4, 6, 7, 8)
    assert 5 in set(current) ^ set(guide)
    assert not grasp_module._covers_all_targets(
        problem, tuple(other for other in current if other != 5)
    )
    for state in _trace_path(problem, current, guide):
        assert grasp_module._covers_all_targets(problem, state)
    best = _relink_forward(problem, current, guide, _budget())
    assert grasp_module._covers_all_targets(problem, best)


def test_each_accepted_move_decreases_guide_distance_by_exactly_one() -> None:
    problem = _build_problem(*V5K3T2)
    for initiating, guide in [
        (PATH_INIT, PATH_GUIDE),
        ((0, 1, 2, 3, 4, 5), (0, 1, 2, 3, 4, 6, 7, 8)),
    ]:
        expected = _distance(initiating, guide)
        for state in _trace_path(problem, initiating, guide):
            expected -= 1
            assert _distance(state, guide) == expected
        assert expected == 0


def test_relinking_fails_closed_if_a_move_does_not_decrease_distance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem = _build_problem(*V5K3T2)
    calls: list[int] = []
    real_distance = grasp_module._distance

    def _sabotaged(left: Selection, right: Selection) -> int:
        calls.append(1)
        # Freeze the reported distance after the first measurement so no move
        # can ever appear to make progress.
        return (
            real_distance(PATH_INIT, PATH_GUIDE) if len(calls) > 1 else real_distance(left, right)
        )

    monkeypatch.setattr(grasp_module, "_distance", _sabotaged)
    with pytest.raises(CoveringDesignGraspPRInvariantError, match="decrease by exactly one"):
        _relink_forward(problem, PATH_INIT, PATH_GUIDE, _budget())
    assert len(calls) > 1


def test_relinking_fails_closed_when_no_feasible_toggle_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem = _build_problem(*V5K3T2)

    def _never_feasible(problem: grasp_module._Problem, selection: Selection) -> bool:
        del problem, selection
        return False

    monkeypatch.setattr(grasp_module, "_covers_all_targets", _never_feasible)
    with pytest.raises(
        CoveringDesignGraspPRInvariantError, match="no feasible single-block toggle"
    ):
        _relink_forward(problem, PATH_INIT, PATH_GUIDE, _budget())


def test_minimum_block_delta_move_is_chosen_over_the_first_feasible_move() -> None:
    # Symmetric difference {7, 8}: index 7 is an ADDITION (delta +1) and would
    # be taken first in canonical index order; index 8 is a feasible REMOVAL
    # (delta -1) and must win on minimum block-count delta.
    problem = _build_problem(*V5K3T2)
    initiating: Selection = (0, 1, 2, 3, 4, 5, 6, 8)
    guide: Selection = (0, 1, 2, 3, 4, 5, 6, 7)
    assert set(initiating) ^ set(guide) == {7, 8}
    removal = tuple(other for other in initiating if other != 8)
    assert grasp_module._covers_all_targets(problem, removal)
    first_state = _trace_path(problem, initiating, guide)[0]
    assert first_state == removal
    assert len(first_state) == len(initiating) - 1
    # Observed through the real function: taking the first feasible move (the
    # index-7 addition) instead would never reach this 7-block state, and the
    # returned best would be the 8-block initiating solution.
    assert _relink_forward(problem, initiating, guide, _budget()) == removal
    assert len(removal) == 7


def test_equal_delta_moves_break_ties_on_the_earlier_canonical_index() -> None:
    problem = _build_problem(*V5K3T2)
    initiating: Selection = (0, 1, 2, 9)
    guide: Selection = (0, 1, 2, 9, 4, 6)
    difference = sorted(set(initiating) ^ set(guide))
    assert difference == [4, 6]
    first_state = _trace_path(problem, initiating, guide)[0]
    assert set(first_state) - set(initiating) == {4}


def test_relinking_always_reaches_the_guide() -> None:
    problem = _build_problem(*V6K3T2)
    selections = _random_feasible_selections(problem, 24)
    checked = 0
    for initiating, guide in itertools.combinations(selections, 2):
        if _distance(initiating, guide) == 0:
            continue
        states = _trace_path(problem, initiating, guide)
        assert set(states[-1]) == set(guide)
        checked += 1
    assert checked >= 10


# ---------------------------------------------------------------------------
# 33. Over-long paths are skipped, never truncated
# ---------------------------------------------------------------------------


def test_over_long_paths_are_skipped_and_never_truncated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[int] = []
    real_relink = grasp_module._relink_forward

    def _recording_relink(
        problem: grasp_module._Problem,
        initiating: Selection,
        guide: Selection,
        budget: _EvaluationBudget,
    ) -> Selection:
        observed.append(_distance(initiating, guide))
        return real_relink(problem, initiating, guide, budget)

    monkeypatch.setattr(grasp_module, "_relink_forward", _recording_relink)
    config = _config(max_path_length=1, iteration_count=25, alpha=0.6)
    result = run_covering_design_grasp_pr(*V6K3T2, config=config)
    assert result.path_relinking_skipped_count > 0
    assert all(distance <= 1 for distance in observed)
    assert result.path_relinking_count == len(observed)


def test_a_generous_path_budget_admits_paths_a_tight_one_skips() -> None:
    tight = run_covering_design_grasp_pr(
        *V6K3T2, config=_config(max_path_length=1, iteration_count=25, alpha=0.6)
    )
    generous = run_covering_design_grasp_pr(
        *V6K3T2, config=_config(max_path_length=64, iteration_count=25, alpha=0.6)
    )
    assert generous.path_relinking_skipped_count == 0
    assert generous.path_relinking_count > tight.path_relinking_count


# ---------------------------------------------------------------------------
# 34-36. Path retention semantics
# ---------------------------------------------------------------------------


def test_best_intermediate_is_retained_over_both_endpoints() -> None:
    problem = _build_problem(*V5K3T2)
    best = _relink_forward(problem, PATH_INIT, PATH_GUIDE, _budget())
    assert best == PATH_EXPECTED_BEST
    assert grasp_module._covers_all_targets(problem, best)


def test_path_result_strictly_beats_both_endpoints_on_block_count() -> None:
    problem = _build_problem(*V5K3T2)
    assert len(PATH_INIT) == len(PATH_GUIDE) == 5
    best = _relink_forward(problem, PATH_INIT, PATH_GUIDE, _budget())
    assert len(best) == 4
    assert len(best) < len(PATH_INIT)
    assert len(best) < len(PATH_GUIDE)


def test_relinking_result_is_never_worse_than_the_better_endpoint() -> None:
    # A property check over the closed path, not a discriminator for the
    # donor seeding (see test_donor_running_cost_defect_is_structurally_
    # impossible: that seeding is an equivalent mutant here). What this does
    # pin is that the retained state is recomputed from the actual current
    # solution, so it can never be worse than the better endpoint.
    problem = _build_problem(*V6K3T2)
    selections = _random_feasible_selections(problem, 24)
    checked = 0
    for initiating, guide in itertools.combinations(selections, 2):
        if _distance(initiating, guide) == 0:
            continue
        best = _relink_forward(problem, initiating, guide, _budget())
        better = min(_solution_key(problem, initiating), _solution_key(problem, guide))
        assert _solution_key(problem, best) <= better
        assert grasp_module._covers_all_targets(problem, best)
        checked += 1
    assert checked >= 10


def test_relinking_endpoint_orientation_is_forward_from_the_initiating_solution() -> None:
    # FORWARD_ONLY: the initiating solution is always the current local
    # optimum and the guide is always the elite, regardless of their costs.
    # Swapping the endpoints is therefore observable.
    problem = _build_problem(*V5K3T2)
    forward = _relink_forward(problem, PATH_INIT, PATH_GUIDE, _budget())
    backward = _relink_forward(problem, PATH_GUIDE, PATH_INIT, _budget())
    assert len(PATH_INIT) == len(PATH_GUIDE)
    assert _trace_path(problem, PATH_INIT, PATH_GUIDE)[-1] == PATH_GUIDE
    assert _trace_path(problem, PATH_GUIDE, PATH_INIT)[-1] == PATH_INIT
    assert grasp_module._covers_all_targets(problem, forward)
    assert grasp_module._covers_all_targets(problem, backward)


def test_relinking_is_always_invoked_forward_from_the_local_optimum() -> None:
    # Call-site orientation, not just the operator's own direction: the
    # initiating argument is always this iteration's L and the guide argument
    # is always an elite drawn from the pre-admission pool. Because
    # _select_guide never returns a zero-distance member, swapping the two
    # endpoints is observable here even on iterations where it happens to
    # leave the reported best unchanged.
    selections: list[tuple[Selection, tuple[Selection, ...]]] = []
    calls: list[tuple[int, Selection, Selection]] = []
    real_select = grasp_module._select_guide
    real_relink = grasp_module._relink_forward

    def _recording_select(
        problem: grasp_module._Problem, pool: _ElitePool, current: Selection
    ) -> Selection | None:
        selections.append((tuple(current), tuple(pool.members)))
        return real_select(problem, pool, current)

    def _recording_relink(
        problem: grasp_module._Problem,
        initiating: Selection,
        guide: Selection,
        budget: _EvaluationBudget,
    ) -> Selection:
        calls.append((len(selections), tuple(initiating), tuple(guide)))
        return real_relink(problem, initiating, guide, budget)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(grasp_module, "_select_guide", _recording_select)
        patch.setattr(grasp_module, "_relink_forward", _recording_relink)
        result = run_covering_design_grasp_pr(
            *V6K3T2, config=_config(iteration_count=15, alpha=0.5)
        )

    assert result.path_relinking_count == len(calls) > 0
    for index, initiating, guide in calls:
        local_optimum, pool_members = selections[index - 1]
        assert initiating == local_optimum
        assert guide in pool_members
        assert guide != local_optimum


# ---------------------------------------------------------------------------
# 37. Public best never regresses
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("domain", [V5K3T2, V6K3T2, V7K3T2])
def test_best_objective_history_is_monotone_non_increasing(
    domain: tuple[int, int, int],
) -> None:
    result = run_covering_design_grasp_pr(*domain, config=_config(iteration_count=25))
    history = result.best_objective_history
    assert history
    assert all(later <= earlier for earlier, later in itertools.pairwise(history))
    assert history[-1] == result.best_block_count


def test_returned_best_is_feasible_and_matches_its_reported_count() -> None:
    result = run_covering_design_grasp_pr(*V6K3T2, config=_config(iteration_count=20))
    assert result.best_block_count == len(result.best_blocks)
    assert grasp_module._independently_verify_cover(6, 2, result.best_blocks)
    assert result.best_blocks == tuple(sorted(result.best_blocks))


def test_final_result_fails_closed_if_independent_verification_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    def _always_false(*args: object, **kwargs: object) -> bool:
        del args, kwargs
        calls.append(1)
        return False

    monkeypatch.setattr(grasp_module, "_independently_verify_cover", _always_false)
    with pytest.raises(CoveringDesignGraspPRInvariantError, match="independent cover verification"):
        run_covering_design_grasp_pr(*V5K3T2, config=_config())
    assert calls


# ---------------------------------------------------------------------------
# 38. Evaluated-solution cap
# ---------------------------------------------------------------------------


def test_derived_total_evaluation_bound_rejects_an_oversized_configuration() -> None:
    with pytest.raises(ValueError, match="derived total evaluation bound"):
        run_covering_design_grasp_pr(*V7K3T2, config=_config(iteration_count=100_000))


def test_evaluation_budget_fails_closed_when_exceeded() -> None:
    budget = _EvaluationBudget(2)
    budget.charge()
    budget.charge()
    with pytest.raises(CoveringDesignGraspPRInvariantError, match="budget exceeded"):
        budget.charge()


def test_reported_evaluated_count_stays_within_the_derived_bound() -> None:
    config = _config(iteration_count=20)
    problem = _build_problem(*V6K3T2)
    bound = grasp_module._derived_total_evaluation_bound(problem.candidate_count, config)
    result = run_covering_design_grasp_pr(*V6K3T2, config=config)
    assert 0 < result.evaluated_solution_count <= bound


# ---------------------------------------------------------------------------
# 39. Bounded histories and audit counters
# ---------------------------------------------------------------------------


def test_audit_counters_are_internally_consistent() -> None:
    config = _config(iteration_count=18, alpha=0.4)
    result = run_covering_design_grasp_pr(*V6K3T2, config=config)
    assert result.grasp_iterations_completed == config.iteration_count
    assert len(result.best_objective_history) == config.iteration_count
    assert result.constructed_solution_count == config.iteration_count
    assert result.local_improvement_count == (config.iteration_count + result.path_relinking_count)
    assert result.path_relinking_count + result.path_relinking_skipped_count <= (
        config.iteration_count
    )
    assert 0 < result.elite_pool_final_size <= config.elite_size
    assert result.candidate_count == 20
    assert result.target_count == 15
    assert result.seed == config.seed


# ---------------------------------------------------------------------------
# 40. No false certification
# ---------------------------------------------------------------------------


def test_status_is_heuristic_and_no_optimality_certificate_exists() -> None:
    result = run_covering_design_grasp_pr(*V6K3T2, config=_config())
    assert result.status is CoveringDesignGraspPRStatus.COMPLETED_HEURISTIC
    members = {member.value for member in CoveringDesignGraspPRStatus}
    assert members == {"COMPLETED_HEURISTIC", "UNKNOWN_NOT_COMPLETED"}
    assert not any("OPTIMAL" in member or "CERTIFIED" in member for member in members)
    assert not hasattr(result, "certificate_basis")
    assert "HEURISTIC" in result.deterministic_configuration_identity


# ---------------------------------------------------------------------------
# 41-42. Dependency and solver boundaries
# ---------------------------------------------------------------------------


def test_module_imports_no_numpy_or_scipy() -> None:
    tree = ast.parse(inspect.getsource(grasp_module))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module.split(".")[0])
    assert "numpy" not in imported
    assert "scipy" not in imported
    assert "ortools" not in imported


def test_no_cp_sat_solver_is_invoked(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        raise AssertionError("CP-SAT must not be invoked by the heuristic")

    monkeypatch.setattr(cp_model, "CpSolver", _fail)
    monkeypatch.setattr(cp_model, "CpModel", _fail)
    result = run_covering_design_grasp_pr(*V6K3T2, config=_config())
    assert result.status is CoveringDesignGraspPRStatus.COMPLETED_HEURISTIC


# ---------------------------------------------------------------------------
# Micro-semantics: per-iteration sequencing
# ---------------------------------------------------------------------------


def test_guide_comes_from_the_pool_as_it_stood_before_this_iteration() -> None:
    # Relinking must consume a PRE-EXISTING elite: if admission ran first, the
    # iteration's own retained solution could be selected as its own guide.
    observed: list[tuple[int, Selection]] = []
    real_select = grasp_module._select_guide

    def _recording_select(
        problem: grasp_module._Problem, pool: _ElitePool, current: Selection
    ) -> Selection | None:
        observed.append((len(pool.members), tuple(current)))
        return real_select(problem, pool, current)

    original_admit = _ElitePool.admit
    admissions: list[int] = []

    def _recording_admit(self: _ElitePool, candidate: Selection) -> bool:
        admissions.append(len(observed))
        return original_admit(self, candidate)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(grasp_module, "_select_guide", _recording_select)
        patch.setattr(_ElitePool, "admit", _recording_admit)
        result = run_covering_design_grasp_pr(*V6K3T2, config=_config(iteration_count=10))

    assert len(observed) == 10
    # Each admission is stamped with the number of guide selections already
    # made, so a stamp of i means "admitted during iteration i, after that
    # iteration's guide was chosen and before the next iteration's".
    assert admissions == sorted(admissions)
    assert set(admissions) == set(range(1, 11))
    # Step 8 offers L, plus R' on every iteration that completed a relinking.
    assert len(admissions) == 10 + result.path_relinking_count
    assert observed[0][0] == 0


def test_first_iteration_performs_no_relinking_and_seeds_the_pool() -> None:
    result = run_covering_design_grasp_pr(*V6K3T2, config=_config(iteration_count=1))
    assert result.path_relinking_count == 0
    assert result.path_relinking_skipped_count == 0
    assert result.elite_pool_final_size == 1
    assert result.local_improvement_count == 1


def test_retained_path_solution_is_improved_before_elite_admission() -> None:
    # Local improvement runs once per construction plus once per completed
    # relinking, and never after admission.
    config = _config(iteration_count=15, alpha=0.5)
    result = run_covering_design_grasp_pr(*V6K3T2, config=config)
    assert result.path_relinking_count > 0
    assert result.local_improvement_count == (config.iteration_count + result.path_relinking_count)


def test_elite_admission_offers_the_local_optimum_then_the_path_result() -> None:
    # Step 8 of the frozen sequence admits {L, R'} in that order. Both are
    # exactly the outputs of that iteration's redundant-block eliminations,
    # so the admission stream must equal the elimination stream.
    offered: list[Selection] = []
    eliminated: list[Selection] = []
    real_eliminate = grasp_module._eliminate_redundant_blocks
    original_admit = _ElitePool.admit

    def _recording_eliminate(
        problem: grasp_module._Problem, selection: Selection, budget: _EvaluationBudget
    ) -> Selection:
        produced = real_eliminate(problem, selection, budget)
        eliminated.append(produced)
        return produced

    def _recording_admit(self: _ElitePool, candidate: Selection) -> bool:
        offered.append(tuple(candidate))
        return original_admit(self, candidate)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(grasp_module, "_eliminate_redundant_blocks", _recording_eliminate)
        patch.setattr(_ElitePool, "admit", _recording_admit)
        result = run_covering_design_grasp_pr(
            *V6K3T2, config=_config(iteration_count=15, alpha=0.5)
        )

    assert result.path_relinking_count > 0
    assert len(offered) == result.grasp_iterations_completed + result.path_relinking_count
    assert offered == eliminated


def test_path_result_never_has_a_larger_key_than_its_initiating_solution() -> None:
    # Why step 3's incumbent update is subsumed by step 7 whenever relinking
    # runs: the retained path state is never worse than the initiating
    # endpoint, and eliminating redundant blocks from it cannot grow the key.
    # Step 3 still carries the incumbent on guideless and skipped iterations.
    problem = _build_problem(*V6K3T2)
    selections = _random_feasible_selections(problem, 24)
    checked = 0
    for initiating, guide in itertools.combinations(selections, 2):
        if _distance(initiating, guide) == 0:
            continue
        path_best = _relink_forward(problem, initiating, guide, _budget())
        path_result = _eliminate_redundant_blocks(problem, path_best, _budget())
        assert _solution_key(problem, path_result) <= _solution_key(problem, initiating)
        checked += 1
    assert checked >= 10


def test_incumbent_is_updated_from_the_path_result_not_only_from_the_local_optimum() -> None:
    # Step 7 of the frozen sequence. R' is frequently strictly better than the
    # L it came from, and step 7 is the only place that improvement reaches
    # the public best. On this fixture dropping it does not merely reshape the
    # history, it costs a whole block in the final answer -- the last two
    # assertions pin exactly that, so the step cannot be silently removed.
    config = _config(seed=2, alpha=0.0, iteration_count=15)
    events: list[tuple[str, Selection]] = []
    real_eliminate = grasp_module._eliminate_redundant_blocks
    real_select = grasp_module._select_guide
    real_relink = grasp_module._relink_forward

    def _recording_eliminate(
        problem: grasp_module._Problem, selection: Selection, budget: _EvaluationBudget
    ) -> Selection:
        produced = real_eliminate(problem, selection, budget)
        events.append(("eliminate", produced))
        return produced

    def _recording_select(
        problem: grasp_module._Problem, pool: _ElitePool, current: Selection
    ) -> Selection | None:
        events.append(("select", tuple(current)))
        return real_select(problem, pool, current)

    def _recording_relink(
        problem: grasp_module._Problem,
        initiating: Selection,
        guide: Selection,
        budget: _EvaluationBudget,
    ) -> Selection:
        events.append(("relink", tuple(initiating)))
        return real_relink(problem, initiating, guide, budget)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(grasp_module, "_eliminate_redundant_blocks", _recording_eliminate)
        patch.setattr(grasp_module, "_select_guide", _recording_select)
        patch.setattr(grasp_module, "_relink_forward", _recording_relink)
        result = run_covering_design_grasp_pr(*V6K3T2, config=config)

    # Each iteration emits eliminate(L), select(L), and -- only when relinking
    # actually ran -- relink then eliminate(R'), so the stream is unambiguous.
    iterations: list[tuple[Selection, Selection | None]] = []
    cursor = 0
    while cursor < len(events):
        assert events[cursor][0] == "eliminate"
        local_optimum = events[cursor][1]
        cursor += 1
        assert events[cursor][0] == "select"
        cursor += 1
        path_result: Selection | None = None
        if cursor < len(events) and events[cursor][0] == "relink":
            cursor += 1
            assert events[cursor][0] == "eliminate"
            path_result = events[cursor][1]
            cursor += 1
        iterations.append((local_optimum, path_result))

    assert len(iterations) == config.iteration_count
    problem = _build_problem(*V6K3T2)
    with_step_seven: list[int] = []
    without_step_seven: list[int] = []
    every: Selection | None = None
    local_only: Selection | None = None
    for local_optimum, path_result in iterations:
        for candidate in (local_optimum, path_result):
            if candidate is not None and (
                every is None or _solution_key(problem, candidate) < _solution_key(problem, every)
            ):
                every = candidate
        if local_only is None or _solution_key(problem, local_optimum) < _solution_key(
            problem, local_only
        ):
            local_only = local_optimum
        assert every is not None
        assert local_only is not None
        with_step_seven.append(len(every))
        without_step_seven.append(len(local_only))

    assert result.best_objective_history == tuple(with_step_seven)
    assert result.best_block_count == with_step_seven[-1]
    assert with_step_seven != without_step_seven
    assert with_step_seven[-1] < without_step_seven[-1]


def test_independent_cover_verification_rejects_an_incomplete_cover() -> None:
    # The end-of-run safety net. Every other test either monkeypatches it or
    # calls it on an already-valid cover, so pin both directions directly.
    verify = grasp_module._independently_verify_cover
    complete = ((0, 1, 2), (0, 3, 4), (1, 3, 4), (2, 3, 4))
    assert verify(5, 2, complete) is True
    assert verify(5, 2, complete[:3]) is False
    assert verify(5, 2, ((0, 1, 2),)) is False
    assert verify(5, 2, ()) is False


def test_redundant_elimination_probes_removals_in_canonical_ascending_order() -> None:
    # The fixpoint is order-independent, so only the probe sequence pins the
    # documented "walk ascending, remove the first removable" rule.
    problem = _build_problem(*V5K3T2)
    selection: Selection = tuple(range(10))
    probed: list[Selection] = []
    real_covers = grasp_module._covers_all_targets

    def _recording_covers(inner: grasp_module._Problem, candidate: Selection) -> bool:
        probed.append(tuple(candidate))
        return real_covers(inner, candidate)

    def _walk(ascending: bool) -> list[Selection]:
        sequence: list[Selection] = []
        current = tuple(sorted(selection))
        while True:
            order = current if ascending else tuple(reversed(current))
            for index in order:
                trial = tuple(other for other in current if other != index)
                sequence.append(trial)
                if real_covers(problem, trial):
                    current = trial
                    break
            else:
                return sequence

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(grasp_module, "_covers_all_targets", _recording_covers)
        _eliminate_redundant_blocks(problem, selection, _budget())

    assert probed == _walk(ascending=True)
    assert probed != _walk(ascending=False)


def test_construction_charges_the_evaluation_budget_once_per_solution() -> None:
    problem = _build_problem(*V6K3T2)
    config = _config()
    budget = _EvaluationBudget(1)
    rng = random.Random(config.seed)
    _construct_solution(problem, config, rng, budget)
    assert budget.count == 1
    with pytest.raises(CoveringDesignGraspPRInvariantError, match="budget exceeded"):
        _construct_solution(problem, config, rng, budget)


def test_configuration_identity_records_the_guard_identity() -> None:
    problem = _build_problem(*V6K3T2)
    identity = run_covering_design_grasp_pr(
        *V6K3T2, config=_config()
    ).deterministic_configuration_identity
    assert problem.guard_identity
    assert '"guard":' in identity
    assert problem.guard_identity in identity


def test_derived_bound_scales_with_the_configured_path_length() -> None:
    problem = _build_problem(*V6K3T2)
    short = grasp_module._derived_total_evaluation_bound(
        problem.candidate_count, _config(max_path_length=1)
    )
    generous = grasp_module._derived_total_evaluation_bound(
        problem.candidate_count, _config(max_path_length=64)
    )
    assert generous > short
    assert generous - short == _config().iteration_count * 63


def test_elite_pool_members_stay_in_canonical_solution_key_order() -> None:
    problem = _build_problem(*V5K3T2)
    pool = _pool(max_size=6)
    for selection in [(5, 6, 7, 8), (0, 1, 2), (3, 4), (0, 1, 3), (2, 9), (1, 4, 7)]:
        assert pool.admit(selection) is True
        keys = [_solution_key(problem, member) for member in pool.members]
        assert keys == sorted(keys)
    assert len(pool.members) == 6
    # Non-vacuous: the resort actually reorders, it does not just preserve
    # the admission order it was handed.
    assert pool.members != [(5, 6, 7, 8), (0, 1, 2), (3, 4), (0, 1, 3), (2, 9), (1, 4, 7)]


def test_alpha_default_absence_is_recorded_in_the_configuration_identity() -> None:
    a = run_covering_design_grasp_pr(*V5K3T2, config=_config(alpha=0.0))
    b = run_covering_design_grasp_pr(*V5K3T2, config=_config(alpha=1.0))
    assert '"alpha":0.0' in a.deterministic_configuration_identity
    assert '"alpha":1.0' in b.deterministic_configuration_identity


# ---------------------------------------------------------------------------
# Mutation / falsifiability: each check proves its seam actually executes
# ---------------------------------------------------------------------------


def test_mutation_strict_rcl_cutoff_would_empty_the_list_at_alpha_zero() -> None:
    problem, available, mask = _mixed_gain_state(V5K3T2, (0,))
    ratios = {
        index: _greedy_ratio(_marginal_gain(problem, index, mask))
        for index in available
        if _marginal_gain(problem, index, mask) > 0
    }
    threshold = _rcl_threshold(min(ratios.values()), max(ratios.values()), 0.0)
    inclusive = tuple(sorted(i for i, r in ratios.items() if r <= threshold))
    strict = tuple(sorted(i for i, r in ratios.items() if r < threshold))
    assert inclusive == _restricted_candidate_list(problem, available, mask, 0.0)
    assert strict == ()
    assert inclusive != strict


def test_mutation_dropping_the_alpha_term_changes_the_rcl() -> None:
    problem, available, mask = _mixed_gain_state(V6K3T2, (0, 1))
    real = _restricted_candidate_list(problem, available, mask, 1.0)
    ratios = [
        _greedy_ratio(_marginal_gain(problem, i, mask))
        for i in available
        if _marginal_gain(problem, i, mask) > 0
    ]
    without_alpha = tuple(
        sorted(
            i
            for i in available
            if _marginal_gain(problem, i, mask) > 0
            and _greedy_ratio(_marginal_gain(problem, i, mask)) <= min(ratios)
        )
    )
    assert len(real) == 18
    assert len(without_alpha) == 6
    assert real != without_alpha


def test_mutation_reversing_the_alpha_direction_changes_the_rcl() -> None:
    problem, available, mask = _mixed_gain_state(V6K3T2, (0, 1))
    forward = [
        len(_restricted_candidate_list(problem, available, mask, alpha))
        for alpha in (0.0, 0.5, 1.0)
    ]
    assert forward == [6, 16, 18]
    assert forward != list(reversed(forward))


def test_mutation_bypassing_alpha_zero_tie_randomization_is_detectable() -> None:
    # A deterministic argmin pick would return one construction for all seeds.
    problem = _build_problem(*V7K3T2)
    config = _config(alpha=0.0)
    constructions = [
        _construct_solution(problem, config, random.Random(seed), _budget()) for seed in range(60)
    ]
    assert len(set(constructions)) > 1
    assert len({c[0] for c in constructions}) > 1


def test_mutation_most_distant_guide_reversed_selects_a_different_elite() -> None:
    problem = _build_problem(*V5K3T2)
    pool = _pool(max_size=5)
    for selection in [(0, 1, 2), (0, 1, 3), (5, 6, 7, 8)]:
        pool.admit(selection)
    current: Selection = (0, 1, 2)
    farthest = _select_guide(problem, pool, current)
    nearest = min(
        (m for m in pool.members if _distance(m, current) > 0),
        key=lambda m: (_distance(m, current), _solution_key(problem, m)),
    )
    assert farthest == (5, 6, 7, 8)
    assert nearest == (0, 1, 3)
    assert farthest != nearest


def test_mutation_admitting_a_duplicate_would_change_the_pool() -> None:
    pool = _pool(max_size=3)
    assert pool.admit((0, 1, 2)) is True
    before = list(pool.members)
    assert pool.admit((0, 1, 2)) is False
    assert pool.members == before
    assert len(pool.members) == 1


def test_mutation_bypassing_the_diversity_gate_is_observable_at_threshold_two() -> None:
    near: Selection = (0, 1, 9)
    strict = _pool(max_size=2, threshold=3)
    for selection in [(0, 1, 2), (0, 1, 3)]:
        strict.admit(selection)
    minimum_distance = min(_distance(m, near) for m in strict.members)
    assert minimum_distance == 2
    assert minimum_distance < 3
    assert strict.admit(near) is False
    permissive = _pool(max_size=2, threshold=2)
    for selection in [(0, 1, 2), (0, 1, 3)]:
        permissive.admit(selection)
    assert permissive.admit(near) is True


def test_mutation_first_feasible_move_differs_from_minimum_delta_move() -> None:
    problem = _build_problem(*V5K3T2)
    initiating: Selection = (0, 1, 2, 3, 4, 5, 6, 8)
    guide: Selection = (0, 1, 2, 3, 4, 5, 6, 7)
    feasible: list[tuple[int, int, Selection]] = []
    for index in sorted(set(initiating) ^ set(guide)):
        if index in initiating:
            trial = tuple(o for o in initiating if o != index)
            delta = -1
        else:
            trial = tuple(sorted((*initiating, index)))
            delta = 1
        if grasp_module._covers_all_targets(problem, trial):
            feasible.append((delta, index, trial))
    assert len(feasible) == 2
    first_feasible = min(feasible, key=lambda move: move[1])
    minimum_delta = min(feasible, key=lambda move: (move[0], move[1]))
    assert first_feasible[1] == 7
    assert minimum_delta[1] == 8
    assert first_feasible != minimum_delta
    assert _trace_path(problem, initiating, guide)[0] == minimum_delta[2]
    returned = _relink_forward(problem, initiating, guide, _budget())
    assert returned == minimum_delta[2]
    assert len(returned) < len(first_feasible[2])
    assert len(returned) < len(initiating)


def test_donor_running_cost_defect_is_structurally_impossible() -> None:
    # NOT a discriminating mutation test, and deliberately not named as one:
    # seeding the running best with min(cost_init, cost_guide) is an
    # EQUIVALENT mutant here, because the path always terminates at the guide
    # and the guide is therefore always compared into the retained best, so
    # both accountings coincide. That is stronger than "the defect was not
    # ported" -- it cannot be expressed. This records the structural property
    # that makes it so: the reported count is read straight off the returned
    # blocks, with no running-cost accumulator that could desynchronize.
    problem = _build_problem(*V5K3T2)
    initiating: Selection = (0, 1, 2, 3, 9)
    guide: Selection = (1, 4, 7, 9)
    assert len(initiating) == 5
    assert len(guide) == 4
    best = _relink_forward(problem, initiating, guide, _budget())
    assert _solution_key(problem, best) <= _solution_key(problem, guide)
    assert len(best) <= len(guide)
    assert len(best) < len(initiating)
    assert grasp_module._covers_all_targets(problem, best)
    # No running-cost accumulator exists to desynchronize from the solution:
    # the reported count is read straight off the returned blocks.
    assert best != initiating


def test_mutation_admitting_only_the_retained_solution_would_change_the_pool() -> None:
    # The collapse this guards against: admitting only the iteration's last
    # candidate instead of {L, R'}. Replaying the real admission stream under
    # both policies yields different pools, so step 8 is not decorative.
    config = _config(iteration_count=20, alpha=0.5)
    stamped: list[tuple[int, Selection]] = []
    marks: list[int] = []
    real_select = grasp_module._select_guide
    original_admit = _ElitePool.admit

    def _counting_select(
        problem: grasp_module._Problem, pool: _ElitePool, current: Selection
    ) -> Selection | None:
        marks.append(1)
        return real_select(problem, pool, current)

    def _recording_admit(self: _ElitePool, candidate: Selection) -> bool:
        stamped.append((len(marks), tuple(candidate)))
        return original_admit(self, candidate)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(grasp_module, "_select_guide", _counting_select)
        patch.setattr(_ElitePool, "admit", _recording_admit)
        result = run_covering_design_grasp_pr(*V6K3T2, config=config)

    assert result.path_relinking_count > 0
    groups: dict[int, list[Selection]] = {}
    for iteration, candidate in stamped:
        groups.setdefault(iteration, []).append(candidate)
    assert any(len(group) == 2 for group in groups.values())

    problem = _build_problem(*V6K3T2)
    both = _ElitePool(problem, config.elite_size, config.elite_diversity_threshold)
    retained_only = _ElitePool(problem, config.elite_size, config.elite_diversity_threshold)
    for iteration in sorted(groups):
        for candidate in groups[iteration]:
            both.admit(candidate)
        retained_only.admit(groups[iteration][-1])

    # The replay reproduces the real pool, so the comparison is against the
    # implementation's actual behavior rather than against a private model.
    assert len(both.members) == result.elite_pool_final_size
    assert both.members != retained_only.members


def test_mutation_public_best_regression_would_break_history_monotonicity() -> None:
    result = run_covering_design_grasp_pr(*V7K3T2, config=_config(iteration_count=30))
    history = result.best_objective_history
    assert len(set(history)) > 1
    assert all(later <= earlier for earlier, later in itertools.pairwise(history))
    assert min(history) == history[-1] == result.best_block_count
