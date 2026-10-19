# pyright: reportMissingTypeStubs=false, reportPrivateUsage=false

"""Clean-room independent tests for the exact set-cover ILP constructor.

The brute-force oracle below is a genuinely separate implementation (plain
set/bitmask enumeration, no shared code with the production module) used to
cross-check every certified result on tiny hand-tractable domains.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from functools import cache

import ortools
import pytest
from ortools.sat.python import cp_model

from lottolab.research import covering_design_setcover_ilp as setcover_module
from lottolab.research.covering_design_gkp_bound import (
    covering_number_upper_bound,
    schoenheim_lower_bound,
)
from lottolab.research.covering_design_setcover_ilp import (
    CertificateBasis,
    SetCoverResultStatus,
    SolverStatus,
    UnsupportedSetCoverDomainError,
    guard_setcover_domain,
    solve_setcover_ilp,
)

type Block = tuple[int, ...]


def _mask(block: Block) -> int:
    bitmask = 0
    for number in block:
        bitmask |= 1 << number
    return bitmask


@dataclass(frozen=True)
class _OracleResult:
    block_count: int
    blocks: tuple[Block, ...]
    optimal_count_at_minimum: int


@cache
def _brute_force_minimum_cover(v: int, k: int, t: int) -> _OracleResult:
    """Independent tiny-domain oracle: exhaustive size-by-size search.

    ``itertools.combinations`` over increasing subset size, scanning index
    combinations in lexicographic order, means the first covering found at
    the minimum size is already the lexicographically smallest one.
    """

    candidates = tuple(itertools.combinations(range(v), k))
    targets = tuple(itertools.combinations(range(v), t))
    target_masks = tuple(_mask(target) for target in targets)
    candidate_masks = tuple(_mask(candidate) for candidate in candidates)

    for size in range(len(candidates) + 1):
        best_combo: tuple[int, ...] | None = None
        count_at_size = 0
        for combo in itertools.combinations(range(len(candidates)), size):
            selected_masks = [candidate_masks[index] for index in combo]
            if all(
                any(
                    (target_mask & selected_mask) == target_mask
                    for selected_mask in selected_masks
                )
                for target_mask in target_masks
            ):
                count_at_size += 1
                if best_combo is None:
                    best_combo = combo
        if best_combo is not None:
            return _OracleResult(
                block_count=size,
                blocks=tuple(candidates[index] for index in best_combo),
                optimal_count_at_minimum=count_at_size,
            )
    raise AssertionError("no covering found for valid v >= k >= t")


def _independent_cover_check(v: int, t: int, blocks: tuple[Block, ...]) -> bool:
    """Separate plain-set implementation, sharing no code with production."""

    for target in itertools.combinations(range(v), t):
        target_set = set(target)
        if not any(target_set.issubset(set(block)) for block in blocks):
            return False
    return True


class _ScriptedSolveDriver:
    def __init__(self, *observations: setcover_module._SolveObservation) -> None:
        self._observations = list(observations)
        self.phases: list[str] = []

    def solve(
        self, model: cp_model.CpModel, *, phase: str
    ) -> setcover_module._SolveObservation:
        del model
        self.phases.append(phase)
        if not self._observations:
            raise AssertionError("scripted solve observation exhausted")
        return self._observations.pop(0)


# ---------------------------------------------------------------------------
# 1. Parameter validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("v", "k", "t", "message"),
    [
        (3, 5, 2, "v must be"),
        (5, 2, 3, "k must be"),
        (5, 3, -1, "t must be"),
    ],
)
def test_invalid_parameter_ordering_raises(v: int, k: int, t: int, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        solve_setcover_ilp(v, k, t)


@pytest.mark.parametrize("bad", [2.0, "3", None, True, False])
def test_invalid_parameter_type_raises(bad: object) -> None:
    with pytest.raises(ValueError, match="must be an integer"):
        solve_setcover_ilp(bad, 3, 2)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 2. Prebuild guard rejects unsupported size before enumeration
# ---------------------------------------------------------------------------


def test_guard_accepts_supported_size_and_reports_exact_arithmetic() -> None:
    size = guard_setcover_domain(6, 3, 2)
    assert size.candidate_block_count == math.comb(6, 3)
    assert size.target_subset_count == math.comb(6, 2)
    assert size.coverage_incidence_count == math.comb(6, 2) * math.comb(4, 1)
    assert size.guard_identity == setcover_module.PREBUILD_GUARD_IDENTITY


def test_guard_rejects_v_above_ceiling() -> None:
    with pytest.raises(UnsupportedSetCoverDomainError, match="v <="):
        guard_setcover_domain(11, 3, 2)


def test_guard_rejects_size_exceeding_envelope_constants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(setcover_module, "MAX_CANDIDATE_BLOCK_COUNT", 1)
    with pytest.raises(UnsupportedSetCoverDomainError, match="prebuild size limit exceeded"):
        guard_setcover_domain(6, 3, 2)


def test_solve_rejects_unsupported_size_before_domain_materialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    materialized = False
    real_combinations = itertools.combinations

    def fail_if_called(*args: object, **kwargs: object) -> object:
        nonlocal materialized
        materialized = True
        raise AssertionError("must not enumerate candidates/targets for a rejected size")

    monkeypatch.setattr(itertools, "combinations", fail_if_called)
    try:
        with pytest.raises(UnsupportedSetCoverDomainError):
            solve_setcover_ilp(11, 3, 2)
    finally:
        assert itertools.combinations is fail_if_called
    monkeypatch.undo()
    assert itertools.combinations is real_combinations
    assert materialized is False


# ---------------------------------------------------------------------------
# 3. Trivial exact cases
# ---------------------------------------------------------------------------


def test_trivial_t_zero_returns_single_smallest_block() -> None:
    result = solve_setcover_ilp(6, 3, 0)
    assert result.status is SetCoverResultStatus.CERTIFIED_GLOBAL_OPTIMUM
    assert result.blocks == ((0, 1, 2),)
    assert result.block_count == 1
    assert result.certificate_basis is CertificateBasis.TRIVIAL_EXACT_CLOSED_FORM
    assert result.solver_status is SolverStatus.NOT_INVOKED
    assert result.lex_fixing_complete is True


def test_trivial_k_equals_v_returns_single_whole_block() -> None:
    result = solve_setcover_ilp(5, 5, 3)
    assert result.status is SetCoverResultStatus.CERTIFIED_GLOBAL_OPTIMUM
    assert result.blocks == ((0, 1, 2, 3, 4),)
    assert result.block_count == 1
    assert result.solver_status is SolverStatus.NOT_INVOKED


def test_trivial_t_equals_k_returns_every_k_subset() -> None:
    result = solve_setcover_ilp(6, 3, 3)
    assert result.status is SetCoverResultStatus.CERTIFIED_GLOBAL_OPTIMUM
    assert result.block_count == math.comb(6, 3)
    assert result.blocks == tuple(itertools.combinations(range(6), 3))
    assert result.solver_status is SolverStatus.NOT_INVOKED


def test_trivial_cases_never_invoke_the_solve_driver() -> None:
    class _ExplodingDriver:
        def solve(
            self, model: cp_model.CpModel, *, phase: str
        ) -> setcover_module._SolveObservation:
            del model, phase
            raise AssertionError("trivial closed-form path must not invoke CP-SAT")

    driver = _ExplodingDriver()
    for v, k, t in ((6, 3, 0), (5, 5, 3), (6, 3, 3)):
        result = solve_setcover_ilp(v, k, t, _solve_driver=driver)
        assert result.status is SetCoverResultStatus.CERTIFIED_GLOBAL_OPTIMUM
        assert result.solver_status is SolverStatus.NOT_INVOKED


# ---------------------------------------------------------------------------
# 4. Brute-force oracle comparison on multiple tiny domains
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("v", "k", "t"),
    [(4, 3, 2), (5, 3, 1), (5, 3, 2), (5, 4, 2), (6, 4, 2)],
)
def test_matches_independent_brute_force_oracle(v: int, k: int, t: int) -> None:
    oracle = _brute_force_minimum_cover(v, k, t)
    actual = solve_setcover_ilp(v, k, t)
    assert actual.status is SetCoverResultStatus.CERTIFIED_GLOBAL_OPTIMUM
    assert actual.block_count == oracle.block_count
    assert actual.blocks == oracle.blocks


# ---------------------------------------------------------------------------
# 5. Certified blocks independently cover every target subset
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("v", "k", "t"),
    [(4, 3, 2), (5, 3, 1), (5, 3, 2), (6, 3, 2), (5, 5, 2), (6, 3, 0), (6, 3, 3)],
)
def test_certified_blocks_independently_cover_every_target(v: int, k: int, t: int) -> None:
    result = solve_setcover_ilp(v, k, t)
    assert result.status is SetCoverResultStatus.CERTIFIED_GLOBAL_OPTIMUM
    assert result.blocks is not None
    assert _independent_cover_check(v, t, result.blocks)


# ---------------------------------------------------------------------------
# 6-7. Bound cross-checks (Schoenheim lower bound / GKP upper bound)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("v", "k", "t"),
    [(4, 3, 2), (5, 3, 1), (5, 3, 2), (6, 3, 2), (5, 5, 2), (6, 3, 0), (6, 3, 3)],
)
def test_optimum_satisfies_schoenheim_lower_bound(v: int, k: int, t: int) -> None:
    result = solve_setcover_ilp(v, k, t)
    assert result.status is SetCoverResultStatus.CERTIFIED_GLOBAL_OPTIMUM
    assert result.block_count is not None
    assert result.block_count >= schoenheim_lower_bound(v, k, t)


@pytest.mark.parametrize(
    ("v", "k", "t"),
    [(4, 3, 2), (5, 3, 1), (5, 3, 2), (6, 3, 2), (5, 5, 2), (6, 3, 0), (6, 3, 3)],
)
def test_optimum_does_not_exceed_gkp_upper_bound(v: int, k: int, t: int) -> None:
    result = solve_setcover_ilp(v, k, t)
    assert result.status is SetCoverResultStatus.CERTIFIED_GLOBAL_OPTIMUM
    upper = covering_number_upper_bound(v, k, t).upper_bound
    assert upper is not None
    assert result.block_count is not None
    assert result.block_count <= upper


# ---------------------------------------------------------------------------
# 8. Repeated certified solve is deterministic
# ---------------------------------------------------------------------------


def test_repeated_certified_solve_is_deterministic() -> None:
    first = solve_setcover_ilp(5, 3, 2)
    second = solve_setcover_ilp(5, 3, 2)
    assert first == second
    assert first.blocks == second.blocks


# ---------------------------------------------------------------------------
# 9. Multiple-optimum case exercises deterministic lexicographic tie-break
# ---------------------------------------------------------------------------


def test_multiple_optima_resolve_to_lexicographically_smallest() -> None:
    oracle = _brute_force_minimum_cover(4, 3, 2)
    assert oracle.optimal_count_at_minimum > 1
    actual = solve_setcover_ilp(4, 3, 2)
    assert actual.status is SetCoverResultStatus.CERTIFIED_GLOBAL_OPTIMUM
    assert actual.blocks == oracle.blocks


# ---------------------------------------------------------------------------
# 10-11. Simulated FEASIBLE / UNKNOWN / MODEL_INVALID never certified
# ---------------------------------------------------------------------------


def test_feasible_objective_incumbent_is_not_certified_or_exposed() -> None:
    driver = _ScriptedSolveDriver(
        setcover_module._SolveObservation(status=SolverStatus.FEASIBLE, objective_value=3.0)
    )
    result = solve_setcover_ilp(5, 3, 2, _solve_driver=driver)
    assert result.status is SetCoverResultStatus.UNKNOWN_NOT_CERTIFIED
    assert result.blocks is None
    assert result.block_count is None
    assert result.solver_status is SolverStatus.FEASIBLE
    assert result.lex_fixing_complete is False
    assert driver.phases == ["objective"]


@pytest.mark.parametrize("status", [SolverStatus.UNKNOWN, SolverStatus.MODEL_INVALID])
def test_unresolved_objective_status_returns_unknown_without_incumbent(
    status: SolverStatus,
) -> None:
    driver = _ScriptedSolveDriver(setcover_module._SolveObservation(status=status))
    result = solve_setcover_ilp(5, 3, 2, _solve_driver=driver)
    assert result.status is SetCoverResultStatus.UNKNOWN_NOT_CERTIFIED
    assert result.blocks is None
    assert result.lex_fixing_complete is False
    assert driver.phases == ["objective"]


def test_objective_resource_limit_fails_closed_even_with_optimal_status() -> None:
    driver = _ScriptedSolveDriver(
        setcover_module._SolveObservation(
            status=SolverStatus.OPTIMAL,
            objective_value=2.0,
            termination_was_limited=True,
        )
    )
    result = solve_setcover_ilp(5, 3, 2, _solve_driver=driver)
    assert result.status is SetCoverResultStatus.UNKNOWN_NOT_CERTIFIED
    assert result.blocks is None
    assert result.diagnostic_solver_status.endswith("RESOURCE_LIMITED")


def test_unexpected_infeasible_objective_fails_closed_with_distinct_diagnostic() -> None:
    driver = _ScriptedSolveDriver(
        setcover_module._SolveObservation(status=SolverStatus.INFEASIBLE)
    )
    result = solve_setcover_ilp(5, 3, 2, _solve_driver=driver)
    assert result.status is SetCoverResultStatus.UNKNOWN_NOT_CERTIFIED
    assert result.blocks is None
    assert (
        result.diagnostic_solver_status
        == "OBJECTIVE:INFEASIBLE:UNEXPECTED_FOR_COMPLETE_CANDIDATE_UNIVERSE"
    )


def test_non_integer_objective_fails_closed() -> None:
    driver = _ScriptedSolveDriver(
        setcover_module._SolveObservation(status=SolverStatus.OPTIMAL, objective_value=2.5)
    )
    result = solve_setcover_ilp(5, 3, 2, _solve_driver=driver)
    assert result.status is SetCoverResultStatus.UNKNOWN_NOT_CERTIFIED
    assert result.blocks is None
    assert result.diagnostic_solver_status == "OBJECTIVE:NON_INTEGER_OR_MISSING_VALUE"


# ---------------------------------------------------------------------------
# 12. Incomplete / unresolved lex fixing never certified
# ---------------------------------------------------------------------------


def test_lex_unknown_returns_unknown_without_optimal_blocks() -> None:
    oracle = _brute_force_minimum_cover(5, 3, 2)
    driver = _ScriptedSolveDriver(
        setcover_module._SolveObservation(
            status=SolverStatus.OPTIMAL, objective_value=float(oracle.block_count)
        ),
        setcover_module._SolveObservation(status=SolverStatus.UNKNOWN),
    )
    result = solve_setcover_ilp(5, 3, 2, _solve_driver=driver)
    assert result.status is SetCoverResultStatus.UNKNOWN_NOT_CERTIFIED
    assert result.blocks is None
    assert result.lex_fixing_complete is False
    assert result.lex_probe_statuses == (SolverStatus.UNKNOWN,)
    assert driver.phases == ["objective", "lex:0"]


def test_lex_resource_limit_fails_closed() -> None:
    oracle = _brute_force_minimum_cover(5, 3, 2)
    driver = _ScriptedSolveDriver(
        setcover_module._SolveObservation(
            status=SolverStatus.OPTIMAL, objective_value=float(oracle.block_count)
        ),
        setcover_module._SolveObservation(
            status=SolverStatus.FEASIBLE, termination_was_limited=True
        ),
    )
    result = solve_setcover_ilp(5, 3, 2, _solve_driver=driver)
    assert result.status is SetCoverResultStatus.UNKNOWN_NOT_CERTIFIED
    assert result.blocks is None
    assert result.diagnostic_solver_status.endswith("RESOURCE_LIMITED")


def test_incomplete_lex_selection_fails_closed() -> None:
    """Every lex probe scripted INFEASIBLE despite a claimed 2-block optimum.

    An internally inconsistent but well-formed sequence of solver
    observations (nothing ever gets fixed to 1) must not be certified.
    """

    candidate_count = math.comb(5, 3)
    driver = _ScriptedSolveDriver(
        setcover_module._SolveObservation(status=SolverStatus.OPTIMAL, objective_value=2.0),
        *(
            setcover_module._SolveObservation(status=SolverStatus.INFEASIBLE)
            for _ in range(candidate_count)
        ),
    )
    result = solve_setcover_ilp(5, 3, 2, _solve_driver=driver)
    assert result.status is SetCoverResultStatus.UNKNOWN_NOT_CERTIFIED
    assert result.blocks is None
    assert result.diagnostic_solver_status == "LEX:INCOMPLETE_SELECTION"


# ---------------------------------------------------------------------------
# 13. Objective-sense / coverage-constraint regression
# ---------------------------------------------------------------------------


def test_minimum_is_hand_verified_and_strictly_below_trivial_enumeration_c_4_3_2() -> None:
    """C(4,3,2)=3 (hand-derived; see covering_design_gkp_bound's own test file).

    Reversing minimize<->maximize would instead select all comb(4,3)=4
    candidate blocks; weakening/removing the coverage constraint would
    instead select 0 blocks. Both are far from the certified value of 3.
    """

    result = solve_setcover_ilp(4, 3, 2)
    assert result.status is SetCoverResultStatus.CERTIFIED_GLOBAL_OPTIMUM
    assert result.block_count == 3
    assert result.block_count < math.comb(4, 3)


def test_minimum_is_hand_verified_ceil_bound_c_5_3_1() -> None:
    """C(5,3,1) = ceil(5/3) = 2: covering every point with 3-blocks needs 2.

    Reversing minimize<->maximize would instead select all comb(5,3)=10
    candidate blocks; weakening/removing the coverage constraint would
    instead select 0 blocks.
    """

    result = solve_setcover_ilp(5, 3, 1)
    assert result.status is SetCoverResultStatus.CERTIFIED_GLOBAL_OPTIMUM
    assert result.block_count == 2
    assert result.block_count < math.comb(5, 3)


# ---------------------------------------------------------------------------
# 14. Model metadata / count arithmetic is exact
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("v", "k", "t"), [(6, 3, 2), (5, 3, 1), (8, 4, 2), (6, 3, 0)])
def test_model_metadata_arithmetic_is_exact(v: int, k: int, t: int) -> None:
    result = solve_setcover_ilp(v, k, t)
    metadata = result.model_metadata
    assert metadata.v == v
    assert metadata.k == k
    assert metadata.t == t
    assert metadata.candidate_block_count == math.comb(v, k)
    assert metadata.target_subset_count == math.comb(v, t)
    assert metadata.coverage_incidence_count == math.comb(v, t) * math.comb(v - t, k - t)
    assert metadata.block_selection_variable_count == metadata.candidate_block_count
    assert metadata.coverage_constraint_count == metadata.target_subset_count
    assert metadata.prebuild_guard_identity == setcover_module.PREBUILD_GUARD_IDENTITY


# ---------------------------------------------------------------------------
# Supporting: output canonicalization, deterministic solver configuration
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("v", "k", "t"), [(6, 3, 2), (5, 3, 1), (6, 3, 0), (5, 5, 2), (6, 3, 3)]
)
def test_output_blocks_are_canonical_sorted_and_distinct(v: int, k: int, t: int) -> None:
    result = solve_setcover_ilp(v, k, t)
    assert result.blocks is not None
    assert result.block_count == len(result.blocks)
    assert len(set(result.blocks)) == len(result.blocks)
    assert result.blocks == tuple(sorted(result.blocks))
    for block in result.blocks:
        assert len(block) == k
        assert len(set(block)) == k
        assert block == tuple(sorted(block))
        assert all(0 <= number < v for number in block)


def test_fixed_solver_configuration_is_frozen_and_identified() -> None:
    configured = setcover_module._build_deterministic_solver()
    assert configured.parameters.num_search_workers == 1
    assert configured.parameters.random_seed == 20260815
    assert configured.parameters.randomize_search is False
    assert configured.parameters.log_search_progress is False
    assert ortools.__version__ == setcover_module.ORTOOLS_LOCKED_VERSION
    identity = setcover_module.DETERMINISTIC_CONFIGURATION_IDENTITY
    assert "ortools=9.15.6755" in identity
    assert "random_seed=20260815" in identity
    assert "num_search_workers=1" in identity


def test_general_path_requires_locked_ortools_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(setcover_module.ortools, "__version__", "9.14.0000")
    with pytest.raises(RuntimeError, match="deterministic certification requires OR-Tools"):
        solve_setcover_ilp(5, 3, 2)


def test_earlier_lex_block_is_skipped_only_after_infeasible_proof() -> None:
    decisions = {
        status: setcover_module._classify_lex_probe(
            setcover_module._SolveObservation(status=status)
        )
        for status in SolverStatus
        if status is not SolverStatus.NOT_INVOKED
    }
    skipped = {
        status
        for status, decision in decisions.items()
        if decision is setcover_module._LexProbeDecision.FIX_SKIPPED
    }
    assert skipped == {SolverStatus.INFEASIBLE}
    assert (
        decisions[SolverStatus.FEASIBLE]
        is setcover_module._LexProbeDecision.FIX_SELECTED
    )
    assert (
        decisions[SolverStatus.OPTIMAL]
        is setcover_module._LexProbeDecision.FIX_SELECTED
    )
