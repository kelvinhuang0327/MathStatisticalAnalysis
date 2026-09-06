# pyright: reportMissingTypeStubs=false, reportPrivateUsage=false

"""Focused contract tests for the research-only covering-design heuristic."""

from __future__ import annotations

import ast
import inspect
import itertools
import random
from collections.abc import Sequence
from typing import NoReturn

import pytest
from ortools.sat.python import cp_model

from lottolab.research import covering_design_lagrangian as lagrangian_module
from lottolab.research.covering_design_lagrangian import (
    CoveringDesignLagrangianConfig,
    CoveringDesignLagrangianStatus,
    LagrangianPrimalInfeasibleError,
    run_covering_design_lagrangian,
)
from lottolab.research.covering_design_setcover_ilp import UnsupportedSetCoverDomainError

type Block = tuple[int, ...]
type Multiplier = tuple[float, ...]


def _full_instance(v: int = 4, k: int = 3, t: int = 2) -> lagrangian_module._FullInstance:
    lagrangian_module.guard_setcover_domain(v, k, t)
    return lagrangian_module._build_full_instance(v, k, t)


def _core_instance(v: int = 4, k: int = 3, t: int = 2) -> lagrangian_module._CoreInstance:
    return lagrangian_module._build_core_instance(_full_instance(v, k, t))


def _identity_core(target_count: int = 2) -> lagrangian_module._CoreInstance:
    indices = tuple(range(target_count))
    return lagrangian_module._CoreInstance(
        fixed_candidate_indices=(),
        fixed_cost=0,
        core_candidate_full_indices=indices,
        core_target_full_indices=indices,
        core_covering_candidate_indices_by_target=tuple((index,) for index in indices),
        core_covering_target_indices_by_candidate=tuple((index,) for index in indices),
    )


def _one_candidate_core() -> lagrangian_module._CoreInstance:
    return lagrangian_module._CoreInstance(
        fixed_candidate_indices=(),
        fixed_cost=0,
        core_candidate_full_indices=(0,),
        core_target_full_indices=(0, 1),
        core_covering_candidate_indices_by_target=((0,), (0,)),
        core_covering_target_indices_by_candidate=((0, 1),),
    )


def _fast_config(
    seed: int = 1,
    *,
    max_outer_iterations: int = 1,
    outer_gap_threshold: float = 0.0,
    initial_stepsize: float = 0.1,
    multiplier_perturbation: float = 0.0,
    subgradient_steps_per_window: int = 1,
    subgradient_window_count: int = 1,
    subgradient_max_passes: int = 1,
    tracked_dual_regression_tolerance: float = 0.050,
) -> CoveringDesignLagrangianConfig:
    return CoveringDesignLagrangianConfig(
        seed=seed,
        max_outer_iterations=max_outer_iterations,
        subgradient_steps_per_window=subgradient_steps_per_window,
        subgradient_window_count=subgradient_window_count,
        subgradient_max_passes=subgradient_max_passes,
        initial_stepsize=initial_stepsize,
        multiplier_perturbation=multiplier_perturbation,
        outer_gap_threshold=outer_gap_threshold,
        tracked_dual_regression_tolerance=tracked_dual_regression_tolerance,
    )


def _observation(block_count: int) -> lagrangian_module._PrimalObservation:
    return lagrangian_module._PrimalObservation(
        core_selected=(),
        full_blocks=((0, 1, 2),),
        block_count=block_count,
    )


def _call_result(
    snapshots: tuple[tuple[Multiplier, float], ...],
    *,
    final_u: Multiplier | None = None,
    final_stepsize: float = 0.1,
) -> lagrangian_module._SubgradientCallResult:
    resolved_u = snapshots[-1][0] if final_u is None else final_u
    return lagrangian_module._SubgradientCallResult(
        snapshots=snapshots,
        final_u=resolved_u,
        final_stepsize=final_stepsize,
        passes_completed=1,
        termination="CONVERGED",
    )


def _independent_cover(v: int, t: int, blocks: Sequence[Block]) -> bool:
    return all(
        any(set(target).issubset(block) for block in blocks)
        for target in itertools.combinations(range(v), t)
    )


# ---------------------------------------------------------------------------
# Domain, canonical incidence, and fixed/core mapping
# ---------------------------------------------------------------------------


def test_config_defaults_preserve_the_frozen_iteration_shape() -> None:
    config = CoveringDesignLagrangianConfig(seed=2026)

    assert config.max_outer_iterations == 20
    assert config.subgradient_steps_per_window == 20
    assert config.subgradient_window_count == 15
    assert config.steps_per_pass == 300
    assert config.subgradient_max_passes == 100
    assert config.initial_stepsize == 0.1
    assert config.subgradient_max_fractional_change == 0.000020
    assert config.subgradient_max_absolute_change == 0.010
    assert config.adaptive_high_threshold == 0.06
    assert config.adaptive_low_threshold == 0.002
    assert config.multiplier_perturbation == 0.06
    assert config.outer_gap_threshold == 0.001
    assert config.tracked_dual_regression_tolerance == 0.050


@pytest.mark.parametrize(
    "bad_config",
    [
        dict(seed=True),
        dict(seed=1, max_outer_iterations=0),
        dict(seed=1, initial_stepsize=0.0),
        dict(seed=1, adaptive_low_threshold=0.06),
        dict(seed=1, multiplier_perturbation=-0.1),
    ],
)
def test_invalid_configuration_is_rejected(bad_config: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        CoveringDesignLagrangianConfig(**bad_config)  # type: ignore[arg-type]


def test_canonical_candidates_targets_and_incidence_are_lexicographic() -> None:
    full = _full_instance(5, 3, 2)

    assert full.candidates == tuple(itertools.combinations(range(5), 3))
    assert full.targets == tuple(itertools.combinations(range(5), 2))
    for target_index, target in enumerate(full.targets):
        expected = tuple(
            candidate_index
            for candidate_index, candidate in enumerate(full.candidates)
            if set(target).issubset(candidate)
        )
        assert full.covering_candidate_indices_by_target[target_index] == expected


def test_guard_runs_before_any_domain_materialization(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    real_guard = lagrangian_module.guard_setcover_domain

    def recording_guard(v: int, k: int, t: int) -> object:
        events.append("guard")
        return real_guard(v, k, t)

    def forbidden_materialization(v: int, k: int, t: int) -> NoReturn:
        del v, k, t
        events.append("materialize")
        raise AssertionError("enumeration must not run after a rejected guard")

    monkeypatch.setattr(lagrangian_module, "guard_setcover_domain", recording_guard)
    monkeypatch.setattr(lagrangian_module, "_build_full_instance", forbidden_materialization)

    with pytest.raises(UnsupportedSetCoverDomainError):
        run_covering_design_lagrangian(
            11,
            3,
            2,
            config=_fast_config(),
        )

    assert events == ["guard"]


def test_nontrivial_domain_has_no_fixed_columns_and_exact_identity_mapping() -> None:
    full = _full_instance(5, 3, 2)
    core = lagrangian_module._build_core_instance(full)

    assert core.fixed_candidate_indices == ()
    assert core.fixed_cost == 0
    assert core.core_candidate_full_indices == tuple(range(len(full.candidates)))
    assert core.core_target_full_indices == tuple(range(len(full.targets)))
    for core_target_index, full_target_index in enumerate(core.core_target_full_indices):
        expected = tuple(
            full_candidate_index
            for full_candidate_index in full.covering_candidate_indices_by_target[full_target_index]
        )
        assert core.core_covering_candidate_indices_by_target[core_target_index] == expected


def test_unique_coverers_become_immutable_fixed_blocks_and_remove_core_targets() -> None:
    full = _full_instance(4, 3, 3)
    core = lagrangian_module._build_core_instance(full)

    assert core.fixed_candidate_indices == tuple(range(len(full.candidates)))
    assert core.fixed_cost == len(full.candidates)
    assert core.core_candidate_full_indices == ()
    assert core.core_target_full_indices == ()


# ---------------------------------------------------------------------------
# Initial multipliers, reduced costs, Lagrangian, and subgradient equations
# ---------------------------------------------------------------------------


def test_default_and_random_initial_multipliers_are_contractual() -> None:
    core = _core_instance(4, 3, 2)

    assert lagrangian_module._default_initial_multiplier(core) == (1.0 / 3.0,) * 6
    expected_rng = random.Random(17)
    expected_random = tuple(expected_rng.random() for _ in core.core_target_full_indices)
    assert lagrangian_module._random_initial_multiplier(core, random.Random(17)) == expected_random


def test_reduced_cost_sign_and_strict_negative_relaxation() -> None:
    core = _identity_core()

    assert lagrangian_module._reduced_costs(core, (2.0, 2.0)) == (-1.0, -1.0)
    assert lagrangian_module._reduced_costs(core, (1.0, 0.0)) == (0.0, 1.0)
    assert lagrangian_module._relaxed_selected_indices((-1.0, 0.0, 0.5)) == (0,)


def test_lagrangian_value_is_sum_of_multipliers_and_strictly_negative_costs() -> None:
    core = _identity_core()
    u = (1.25, 1.25)
    reduced = lagrangian_module._reduced_costs(core, u)

    assert reduced == (-0.25, -0.25)
    assert lagrangian_module._core_lagrangian_value(u, reduced) == pytest.approx(2.0)


def test_subgradient_sign_norm_squared_ub_minus_l_and_projection() -> None:
    core = _identity_core()
    outcome = lagrangian_module._apply_subgradient_step(
        core,
        (0.75, 0.75),
        stepsize=1.0,
        ub_core=0.0,
    )

    # No relaxed column is selected, so g=(1,1), ||g||^2=2, and
    # u_next=max(0, .75 + (0-.?)/2*g)=0 after the negative step.
    assert outcome.u == (0.0, 0.0)
    assert outcome.was_stationary is False
    assert lagrangian_module._subgradient_vector(core, ()) == (1.0, 1.0)
    assert sum(component * component for component in (1.0, 1.0)) == 2.0


def test_subgradient_step_uses_ub_minus_l_with_expected_positive_direction() -> None:
    core = _identity_core()
    outcome = lagrangian_module._apply_subgradient_step(
        core,
        (0.0, 0.0),
        stepsize=1.0,
        ub_core=4.0,
    )

    assert outcome.u == (2.0, 2.0)
    assert outcome.lagrangian_value == pytest.approx(2.0)


def test_zero_subgradient_is_stationary_without_division() -> None:
    core = _one_candidate_core()
    outcome = lagrangian_module._apply_subgradient_step(
        core,
        (1.0, 1.0),
        stepsize=1.0,
        ub_core=5.0,
    )

    assert outcome.was_stationary is True
    assert outcome.u == (1.0, 1.0)
    assert outcome.lagrangian_value == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Perturbation, windows, adaptive stepsize, promotion, and convergence
# ---------------------------------------------------------------------------


def test_multiplier_perturbation_is_isolated_and_multiplicative() -> None:
    class ScriptedRandom(random.Random):
        def uniform(self, a: float, b: float) -> float:
            assert (a, b) == (-1.0, 1.0)
            return 0.5 if self._draws == 0 else -1.0

        _draws = 0

        def random(self) -> float:
            self._draws += 1
            return 0.5

    rng = ScriptedRandom()
    assert lagrangian_module._perturb_multiplier((2.0, 0.0), 0.06, rng) == (2.06, 0.0)


def _controlled_pass(
    monkeypatch: pytest.MonkeyPatch,
    lagrangian_values: Sequence[float],
    *,
    stepsize_start: float = 1.0,
    steps_per_window: int = 2,
    window_count: int = 1,
) -> tuple[lagrangian_module._PassOutcome, list[tuple[Multiplier, float]]]:
    core = _identity_core(1)
    scripted = iter(
        lagrangian_module._StepOutcome(
            u=(float(index + 1),), lagrangian_value=value, was_stationary=False
        )
        for index, value in enumerate(lagrangian_values)
    )
    seen: list[tuple[Multiplier, float]] = []

    def fake_step(
        _core: lagrangian_module._CoreInstance,
        u: Multiplier,
        stepsize: float,
        ub_core: float,
    ) -> lagrangian_module._StepOutcome:
        del _core, ub_core
        seen.append((u, stepsize))
        return next(scripted)

    monkeypatch.setattr(lagrangian_module, "_apply_subgradient_step", fake_step)
    config = CoveringDesignLagrangianConfig(
        seed=1,
        subgradient_steps_per_window=steps_per_window,
        subgradient_window_count=window_count,
        subgradient_max_passes=1,
        multiplier_perturbation=0.0,
    )
    outcome = lagrangian_module._run_subgradient_pass(
        core,
        (0.0,),
        stepsize_start,
        ub_core=10.0,
        config=config,
        rng=random.Random(1),
    )
    return outcome, seen


def test_adaptive_window_increases_stepsize_below_low_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcome, _ = _controlled_pass(monkeypatch, [1.0, 1.001])
    assert outcome.stepsize_after == pytest.approx(1.5)


def test_adaptive_window_decreases_stepsize_above_high_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcome, _ = _controlled_pass(monkeypatch, [1.0, 2.0])
    assert outcome.stepsize_after == pytest.approx(0.5)


def test_adaptive_stepsize_has_no_post_multiplication_clamp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcome, _ = _controlled_pass(monkeypatch, [1.0, 1.001], stepsize_start=1.4)
    assert outcome.stepsize_after == pytest.approx(2.1)


def test_best_in_window_promotes_the_best_multiplier_to_the_next_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcome, seen = _controlled_pass(
        monkeypatch,
        [1.0, 4.0, 2.0, 3.0],
        steps_per_window=2,
        window_count=2,
    )

    assert seen[2][0] == (2.0,)
    assert outcome.best_u == (2.0,)
    assert outcome.best_l == 4.0


def test_subgradient_call_requires_both_convergence_changes_to_be_small(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    core = _identity_core(1)
    values = iter([1000.0, 1000.02, 1000.020001])

    def fake_pass(
        _core: lagrangian_module._CoreInstance,
        u_start: Multiplier,
        stepsize_start: float,
        ub_core: float,
        config: CoveringDesignLagrangianConfig,
        rng: random.Random,
    ) -> lagrangian_module._PassOutcome:
        del _core, ub_core, config, rng
        value = next(values)
        return lagrangian_module._PassOutcome(
            snapshots=(((value,), value),),
            best_u=(value,),
            best_l=value,
            stepsize_after=stepsize_start,
        )

    monkeypatch.setattr(lagrangian_module, "_run_subgradient_pass", fake_pass)
    result = lagrangian_module._run_subgradient_call(
        core,
        (0.0,),
        0.1,
        ub_core=2.0,
        config=CoveringDesignLagrangianConfig(seed=1, subgradient_max_passes=5),
        rng=random.Random(1),
    )

    assert result.passes_completed == 3
    assert result.termination == "CONVERGED"


def test_subgradient_call_retains_every_snapshot_from_its_final_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    core = _identity_core(1)
    snapshots = (((1.0,), 1.0), ((2.0,), 2.0), ((3.0,), 3.0))

    def fake_pass(
        _core: lagrangian_module._CoreInstance,
        _u_start: Multiplier,
        stepsize_start: float,
        ub_core: float,
        config: CoveringDesignLagrangianConfig,
        rng: random.Random,
    ) -> lagrangian_module._PassOutcome:
        del _core, _u_start, ub_core, config, rng
        return lagrangian_module._PassOutcome(
            snapshots=snapshots,
            best_u=(3.0,),
            best_l=3.0,
            stepsize_after=stepsize_start,
        )

    monkeypatch.setattr(lagrangian_module, "_run_subgradient_pass", fake_pass)
    result = lagrangian_module._run_subgradient_call(
        core,
        (0.0,),
        0.1,
        ub_core=2.0,
        config=CoveringDesignLagrangianConfig(seed=1, subgradient_max_passes=1),
        rng=random.Random(1),
    )

    assert result.snapshots == snapshots


def test_subgradient_call_audits_the_maximum_pass_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    core = _identity_core(1)
    calls = 0

    def fake_pass(
        _core: lagrangian_module._CoreInstance,
        u_start: Multiplier,
        stepsize_start: float,
        ub_core: float,
        config: CoveringDesignLagrangianConfig,
        rng: random.Random,
    ) -> lagrangian_module._PassOutcome:
        nonlocal calls
        del _core, ub_core, config, rng
        calls += 1
        value = float(calls)
        return lagrangian_module._PassOutcome(
            snapshots=(((value,), value),),
            best_u=(value,),
            best_l=value,
            stepsize_after=stepsize_start,
        )

    monkeypatch.setattr(lagrangian_module, "_run_subgradient_pass", fake_pass)
    result = lagrangian_module._run_subgradient_call(
        core,
        (0.0,),
        0.1,
        ub_core=2.0,
        config=CoveringDesignLagrangianConfig(seed=1, subgradient_max_passes=2),
        rng=random.Random(1),
    )

    assert calls == 2
    assert result.passes_completed == 2
    assert result.termination == "MAX_PASSES_REACHED"


# ---------------------------------------------------------------------------
# Dual-guided greedy and independent primal feasibility
# ---------------------------------------------------------------------------


def test_greedy_score_uses_the_positive_and_negative_gamma_formulas() -> None:
    assert lagrangian_module._greedy_score(0.5, 2.0) == pytest.approx(0.25)
    assert lagrangian_module._greedy_score(-0.5, 2.0) == pytest.approx(-1.0)


def test_greedy_positive_gamma_prefers_more_newly_covered_targets() -> None:
    core = lagrangian_module._CoreInstance(
        fixed_candidate_indices=(),
        fixed_cost=0,
        core_candidate_full_indices=(0, 1),
        core_target_full_indices=(0, 1),
        core_covering_candidate_indices_by_target=((0, 1), (0,)),
        core_covering_target_indices_by_candidate=((0, 1), (0,)),
    )

    assert lagrangian_module._construct_greedy_primal(core, (0.0, 0.0), 2) == (0,)


def test_greedy_negative_gamma_multiplies_by_newly_covered_targets() -> None:
    core = lagrangian_module._CoreInstance(
        fixed_candidate_indices=(),
        fixed_cost=0,
        core_candidate_full_indices=(0, 1),
        core_target_full_indices=(0, 1),
        core_covering_candidate_indices_by_target=((0, 1), (0,)),
        core_covering_target_indices_by_candidate=((0, 1), (0,)),
    )

    assert lagrangian_module._construct_greedy_primal(core, (1.0, 1.0), 2) == (0,)


def test_greedy_ties_use_the_canonical_first_candidate_index() -> None:
    core = lagrangian_module._CoreInstance(
        fixed_candidate_indices=(),
        fixed_cost=0,
        core_candidate_full_indices=(0, 1),
        core_target_full_indices=(0,),
        core_covering_candidate_indices_by_target=((0, 1),),
        core_covering_target_indices_by_candidate=((0,), (0,)),
    )

    assert lagrangian_module._construct_greedy_primal(core, (0.0,), 2) == (0,)


def test_no_redundant_block_removal_is_performed_after_greedy_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    full = _full_instance(3, 2, 1)
    core = lagrangian_module._build_core_instance(full)
    assert core.fixed_candidate_indices == ()

    def redundant_selection(
        _core: lagrangian_module._CoreInstance,
        _u: Multiplier,
        _cap: int,
    ) -> tuple[int, ...]:
        return (0, 1)

    monkeypatch.setattr(lagrangian_module, "_construct_greedy_primal", redundant_selection)
    observation = lagrangian_module._observe_primal(full, core, (0.0, 0.0, 0.0), 3)

    assert observation.core_selected == (0, 1)
    assert observation.block_count == 2


def test_incomplete_greedy_primal_fails_closed() -> None:
    full = _full_instance(4, 3, 2)
    core = lagrangian_module._build_core_instance(full)

    with pytest.raises(LagrangianPrimalInfeasibleError):
        lagrangian_module._construct_greedy_primal(core, (0.0,) * 6, cap=1)


def test_full_cover_is_independently_verified_after_core_cover(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    full = _full_instance(4, 3, 2)
    core = lagrangian_module._build_core_instance(full)
    valid_core_selection = lagrangian_module._construct_greedy_primal(core, (0.0,) * 6, 6)

    def incomplete_blocks(
        _full: lagrangian_module._FullInstance,
        _core: lagrangian_module._CoreInstance,
        _selected: Sequence[int],
    ) -> tuple[Block, ...]:
        return (full.candidates[0],)

    monkeypatch.setattr(
        lagrangian_module,
        "_full_blocks_from_core_selection",
        incomplete_blocks,
    )
    with pytest.raises(LagrangianPrimalInfeasibleError, match="full primal"):
        lagrangian_module._observe_primal(full, core, (0.0,) * 6, 6)

    assert valid_core_selection


def test_snapshot_selection_is_cost_then_dual_then_earliest() -> None:
    assert lagrangian_module._select_best_snapshot_index([4, 3, 3], [1.0, 5.0, 5.0]) == 1


# ---------------------------------------------------------------------------
# Outer-loop state, two-call behavior, restarts, tracker/public separation
# ---------------------------------------------------------------------------


def test_outer_loop_calls_subgradient_exactly_twice_and_second_consumes_first_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    core = _core_instance()
    zero_u = (0.0,) * len(core.core_target_full_indices)
    entries: list[tuple[Multiplier, float]] = []

    def fake_call(
        _core: lagrangian_module._CoreInstance,
        u_entry: Multiplier,
        stepsize_entry: float,
        ub_core: float,
        config: CoveringDesignLagrangianConfig,
        rng: random.Random,
    ) -> lagrangian_module._SubgradientCallResult:
        del _core, ub_core, config, rng
        entries.append((u_entry, stepsize_entry))
        final_u = tuple(float(len(entries)) for _ in u_entry)
        return _call_result(((zero_u, 0.0),), final_u=final_u, final_stepsize=0.4)

    monkeypatch.setattr(lagrangian_module, "_run_subgradient_call", fake_call)
    result = run_covering_design_lagrangian(
        4,
        3,
        2,
        config=_fast_config(max_outer_iterations=1),
    )

    assert result.subgradient_call_count == 2
    assert len(entries) == 2
    assert entries[1][0] == (1.0,) * 6
    assert entries[1][1] == 0.4


def test_working_stepsize_persists_across_calls_outer_iterations_and_acceptance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    core = _core_instance()
    zero_u = (0.0,) * len(core.core_target_full_indices)
    entries: list[float] = []

    def fake_call(
        _core: lagrangian_module._CoreInstance,
        u_entry: Multiplier,
        stepsize_entry: float,
        ub_core: float,
        config: CoveringDesignLagrangianConfig,
        rng: random.Random,
    ) -> lagrangian_module._SubgradientCallResult:
        del _core, u_entry, ub_core, config, rng
        entries.append(stepsize_entry)
        return _call_result(((zero_u, 0.0),), final_u=zero_u, final_stepsize=stepsize_entry + 0.25)

    monkeypatch.setattr(lagrangian_module, "_run_subgradient_call", fake_call)
    result = run_covering_design_lagrangian(
        4,
        3,
        2,
        config=_fast_config(max_outer_iterations=2),
    )

    assert entries == pytest.approx([0.1, 0.35, 0.6, 0.85])
    assert result.working_stepsize_history == pytest.approx((0.1, 0.6, 1.1))


def test_outer_restart_parity_is_random_even_and_deterministic_odd(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    core = _core_instance()
    zero_u = (0.0,) * len(core.core_target_full_indices)
    first_call_entries: list[Multiplier] = []
    random_initial_calls = 0
    default_initial_calls = 0

    def fake_random_initial(
        _core: lagrangian_module._CoreInstance, _rng: random.Random
    ) -> Multiplier:
        nonlocal random_initial_calls
        random_initial_calls += 1
        return (10.0,) * 6

    def fake_default_initial(_core: lagrangian_module._CoreInstance) -> Multiplier:
        nonlocal default_initial_calls
        default_initial_calls += 1
        return (20.0,) * 6

    def fake_call(
        _core: lagrangian_module._CoreInstance,
        u_entry: Multiplier,
        stepsize_entry: float,
        ub_core: float,
        config: CoveringDesignLagrangianConfig,
        rng: random.Random,
    ) -> lagrangian_module._SubgradientCallResult:
        del _core, ub_core, config, rng
        if len(first_call_entries) % 2 == 0:
            first_call_entries.append(u_entry)
        else:
            first_call_entries.append(u_entry)
        return _call_result(((zero_u, 0.0),), final_u=zero_u, final_stepsize=stepsize_entry)

    monkeypatch.setattr(lagrangian_module, "_random_initial_multiplier", fake_random_initial)
    monkeypatch.setattr(lagrangian_module, "_default_initial_multiplier", fake_default_initial)
    monkeypatch.setattr(lagrangian_module, "_run_subgradient_call", fake_call)

    run_covering_design_lagrangian(
        4,
        3,
        2,
        config=_fast_config(max_outer_iterations=4),
    )

    assert random_initial_calls == 2
    assert default_initial_calls == 1  # the deterministic initializer is reused on odd iterations
    assert first_call_entries[::2] == [(10.0,) * 6, (20.0,) * 6, (10.0,) * 6, (20.0,) * 6]


def test_all_second_call_snapshots_are_evaluated_and_selected_by_cost_then_dual(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    core = _core_instance()
    zero_u = (0.0,) * len(core.core_target_full_indices)
    u1 = (1.0,) * 6
    u2 = (2.0,) * 6
    u3 = (3.0,) * 6
    observed: list[Multiplier] = []
    call_count = 0

    def fake_observe(
        _full: lagrangian_module._FullInstance,
        _core: lagrangian_module._CoreInstance,
        u: Multiplier,
        _cap: int,
    ) -> lagrangian_module._PrimalObservation:
        observed.append(u)
        if len(observed) == 1:
            return _observation(5)
        return {
            u1: _observation(4),
            u2: _observation(3),
            u3: _observation(3),
        }[u]

    def fake_call(
        _core: lagrangian_module._CoreInstance,
        _u_entry: Multiplier,
        stepsize_entry: float,
        ub_core: float,
        config: CoveringDesignLagrangianConfig,
        rng: random.Random,
    ) -> lagrangian_module._SubgradientCallResult:
        nonlocal call_count
        del _core, ub_core, config, rng
        call_count += 1
        if call_count == 1:
            return _call_result(((zero_u, 0.0),), final_u=u1, final_stepsize=stepsize_entry)
        return _call_result(
            ((u1, 1.0), (u2, 5.0), (u3, 5.0)),
            final_u=u3,
            final_stepsize=stepsize_entry,
        )

    monkeypatch.setattr(lagrangian_module, "_observe_primal", fake_observe)
    monkeypatch.setattr(lagrangian_module, "_run_subgradient_call", fake_call)

    result = run_covering_design_lagrangian(
        4,
        3,
        2,
        config=_fast_config(max_outer_iterations=1),
    )

    assert observed == [((1.0 / 3.0),) * 6, u1, u2, u3]
    assert result.primal_solutions_evaluated == 4
    assert result.best_block_count == 3
    assert result.tracked_accepted_dual_value == 5.0


def test_exact_outer_cap_and_gap_termination(monkeypatch: pytest.MonkeyPatch) -> None:
    core = _core_instance()
    zero_u = (0.0,) * len(core.core_target_full_indices)
    calls = 0

    def fake_call(
        _core: lagrangian_module._CoreInstance,
        _u_entry: Multiplier,
        stepsize_entry: float,
        ub_core: float,
        config: CoveringDesignLagrangianConfig,
        rng: random.Random,
    ) -> lagrangian_module._SubgradientCallResult:
        nonlocal calls
        del _core, ub_core, config, rng
        calls += 1
        return _call_result(((zero_u, 0.0),), final_u=zero_u, final_stepsize=stepsize_entry)

    monkeypatch.setattr(lagrangian_module, "_run_subgradient_call", fake_call)
    capped = run_covering_design_lagrangian(
        4,
        3,
        2,
        config=_fast_config(max_outer_iterations=3, outer_gap_threshold=0.0),
    )
    assert capped.outer_iterations_completed == 3
    assert capped.subgradient_call_count == 6
    assert calls == 6

    gap_closed = run_covering_design_lagrangian(
        4,
        3,
        2,
        config=_fast_config(max_outer_iterations=3, outer_gap_threshold=1.0),
    )
    assert gap_closed.outer_iterations_completed == 0
    assert gap_closed.subgradient_call_count == 0


def test_five_percent_tracker_rule_uses_absolute_tracked_dual() -> None:
    config = _fast_config(tracked_dual_regression_tolerance=0.05)

    assert lagrangian_module._dual_regressed_too_much(96.0, 100.0, config) is False
    assert lagrangian_module._dual_regressed_too_much(94.9, 100.0, config) is True
    assert lagrangian_module._dual_regressed_too_much(-104.0, -100.0, config) is False
    assert lagrangian_module._dual_regressed_too_much(-106.0, -100.0, config) is True


def test_accepted_dual_tracker_can_regress_within_the_five_percent_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    core = _core_instance()
    zero_u = (0.0,) * len(core.core_target_full_indices)
    call_count = 0

    def fake_call(
        _core: lagrangian_module._CoreInstance,
        _u_entry: Multiplier,
        stepsize_entry: float,
        ub_core: float,
        config: CoveringDesignLagrangianConfig,
        rng: random.Random,
    ) -> lagrangian_module._SubgradientCallResult:
        nonlocal call_count
        del _core, ub_core, config, rng
        call_count += 1
        value = 1.9 if call_count <= 2 else 1.7
        return _call_result(((zero_u, value),), final_u=zero_u, final_stepsize=stepsize_entry)

    monkeypatch.setattr(lagrangian_module, "_run_subgradient_call", fake_call)
    result = run_covering_design_lagrangian(
        4,
        3,
        2,
        config=_fast_config(max_outer_iterations=2),
    )

    assert result.tracked_dual_history == pytest.approx((2.0, 1.9, 1.9))
    assert result.tracked_accepted_dual_value == pytest.approx(1.9)


def test_public_best_primal_never_regresses_when_accepted_tracker_does(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed = 0
    zero_u = (0.0,) * 6

    def fake_observe(
        _full: lagrangian_module._FullInstance,
        _core: lagrangian_module._CoreInstance,
        _u: Multiplier,
        _cap: int,
    ) -> lagrangian_module._PrimalObservation:
        nonlocal observed
        observed += 1
        return _observation(2 if observed == 1 else 4)

    def fake_call(
        _core: lagrangian_module._CoreInstance,
        _u_entry: Multiplier,
        stepsize_entry: float,
        ub_core: float,
        config: CoveringDesignLagrangianConfig,
        rng: random.Random,
    ) -> lagrangian_module._SubgradientCallResult:
        del _core, _u_entry, ub_core, config, rng
        return _call_result(((zero_u, 0.0),), final_u=zero_u, final_stepsize=stepsize_entry)

    monkeypatch.setattr(lagrangian_module, "_observe_primal", fake_observe)
    monkeypatch.setattr(lagrangian_module, "_run_subgradient_call", fake_call)

    def zero_lagrangian(
        _u: Multiplier,
        _reduced_costs: Sequence[float],
    ) -> float:
        return 0.0

    monkeypatch.setattr(lagrangian_module, "_core_lagrangian_value", zero_lagrangian)
    result = run_covering_design_lagrangian(
        4,
        3,
        2,
        config=_fast_config(max_outer_iterations=2),
    )

    assert result.best_block_count == 2
    assert result.best_primal_history == (2, 4, 4)


# ---------------------------------------------------------------------------
# Public result, reproducibility, certification boundaries, and dependencies
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("domain", [(4, 3, 2), (5, 3, 2), (4, 3, 3)])
def test_public_result_is_reproducible_and_independently_feasible(
    domain: tuple[int, int, int],
) -> None:
    v, k, t = domain
    config = _fast_config(seed=2026, max_outer_iterations=1)
    first = run_covering_design_lagrangian(v, k, t, config=config)
    second = run_covering_design_lagrangian(v, k, t, config=config)

    assert first == second
    assert first.status is CoveringDesignLagrangianStatus.COMPLETED_HEURISTIC
    assert first.best_block_count == len(first.best_blocks)
    assert _independent_cover(v, t, first.best_blocks)


def test_fixed_case_reports_heuristic_result_without_false_certification() -> None:
    result = run_covering_design_lagrangian(
        4,
        3,
        3,
        config=CoveringDesignLagrangianConfig(seed=1),
    )

    assert result.status is CoveringDesignLagrangianStatus.COMPLETED_HEURISTIC
    assert result.fixed_block_count == 4
    assert result.core_candidate_count == 0
    assert result.core_target_count == 0
    assert result.outer_iterations_completed == 0
    assert result.subgradient_call_count == 0
    assert not hasattr(result, "certified_global_optimum")
    assert not hasattr(result, "global_bound")


def test_deterministic_configuration_identity_changes_with_configuration() -> None:
    first = run_covering_design_lagrangian(
        4,
        3,
        3,
        config=CoveringDesignLagrangianConfig(seed=1),
    )
    second = run_covering_design_lagrangian(
        4,
        3,
        3,
        config=CoveringDesignLagrangianConfig(seed=2),
    )

    assert first.deterministic_configuration_identity != second.deterministic_configuration_identity
    assert "seed=1" in first.deterministic_configuration_identity
    assert "core_candidate_count=0" in first.deterministic_configuration_identity


def test_no_cp_sat_solver_is_invoked(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_solver(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        raise AssertionError("CP-SAT must not be invoked by the heuristic")

    monkeypatch.setattr(cp_model, "CpSolver", fail_solver)
    result = run_covering_design_lagrangian(
        4,
        3,
        3,
        config=CoveringDesignLagrangianConfig(seed=1),
    )
    assert result.status is CoveringDesignLagrangianStatus.COMPLETED_HEURISTIC


def test_module_imports_no_numpy_or_scipy() -> None:
    tree = ast.parse(inspect.getsource(lagrangian_module))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module.split(".")[0])

    assert "numpy" not in imported_modules
    assert "scipy" not in imported_modules
