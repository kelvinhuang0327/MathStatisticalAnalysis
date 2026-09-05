# pyright: reportPrivateUsage=false

from __future__ import annotations

import inspect
import itertools
import math
import random
from dataclasses import FrozenInstanceError

import pytest

import lottolab.research.covering_design_aco as aco_module
from lottolab.research.covering_design_aco import (
    MAX_TOTAL_ANT_CONSTRUCTIONS,
    CoveringDesignACOConfig,
    CoveringDesignACOInvariantError,
    CoveringDesignACOResult,
    CoveringDesignACOStatus,
    UnsupportedSetCoverDomainError,
    _best_key,
    _build_problem,
    _Colony,
    _compute_dominance,
    _compute_mandatory,
    _construct_ant,
    _covers_all_rows,
    _independently_verify_cover,
    _local_search,
    _Problem,
    _selection_weight,
    _uncovered_gain_ratio,
    _weighted_roulette,
    run_covering_design_aco,
)

type Block = tuple[int, ...]

# candidate_count=10, target_count=10, covering number C(5,3,2)=4, no domination
V5K3T2 = (5, 3, 2)
# candidate_count=6, target_count=4, no domination
V4K2T1 = (4, 2, 1)
# candidate_count=3, target_count=1: candidates 0,1 dominated, candidate 2 (last) mandatory
V3K2T0 = (3, 2, 0)


def _brute_force_uncovered(v: int, t: int, blocks: tuple[Block, ...]) -> set[Block]:
    block_sets = [set(block) for block in blocks]
    return {
        target
        for target in itertools.combinations(range(v), t)
        if not any(set(target).issubset(block) for block in block_sets)
    }


def _stub_problem(candidate_count: int) -> _Problem:
    """A trivial v=k=t=1-shaped problem: candidate ``i`` covers only row ``i``."""

    candidates = tuple((index,) for index in range(candidate_count))
    return _Problem(
        v=candidate_count,
        k=1,
        t=1,
        candidates=candidates,
        targets=candidates,
        candidate_count=candidate_count,
        target_count=candidate_count,
        coverage_masks=tuple(1 << index for index in range(candidate_count)),
        all_rows_mask=(1 << candidate_count) - 1,
        guard_identity="stub",
    )


def _domain_with_one_dominated_candidate_and_no_mandatory() -> tuple[_Problem, tuple[bool, ...]]:
    """4 rows, 5 candidates: P, Q, X, Y are pairwise incomparable (none dominated,
    every row has 2 non-dominated coverers so nothing is mandatory), and Z is a
    genuine subset of P (dominated). Because mandatory is empty, the SROM loop
    genuinely runs and row 0 is a real stochastic draw where Z is eligible-by-
    coverage (excluded only by the dominance check).

    P={0,1}=0b0011  Q={0,2}=0b0101  X={1,3}=0b1010  Y={2,3}=0b1100  Z={0}=0b0001
    """

    candidates = ((0, 1), (0, 2), (1, 3), (2, 3), (0,))
    coverage_masks = (0b0011, 0b0101, 0b1010, 0b1100, 0b0001)
    problem = _Problem(
        v=4,
        k=2,
        t=1,
        candidates=candidates,
        targets=tuple((row,) for row in range(4)),
        candidate_count=5,
        target_count=4,
        coverage_masks=coverage_masks,
        all_rows_mask=0b1111,
        guard_identity="stub",
    )
    dominated = _compute_dominance(coverage_masks)
    assert dominated == (False, False, False, False, True)  # sanity: Z is the only one
    return problem, dominated


# ---------------------------------------------------------------------------
# 1. Config parameter validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"seed": True}, "seed must be an integer"),
        ({"seed": "1"}, "seed must be an integer"),
        ({"seed": 1, "alpha": -0.1}, "alpha must be a finite non-negative number"),
        ({"seed": 1, "alpha": float("nan")}, "alpha must be a finite non-negative number"),
        ({"seed": 1, "beta": -1.0}, "beta must be a finite non-negative number"),
        ({"seed": 1, "rho": -0.1}, "rho must be a finite non-negative number"),
        ({"seed": 1, "rho": 1.1}, "rho must be <= 1"),
        ({"seed": 1, "q": 0.0}, r"q must be > 0"),
        ({"seed": 1, "q": -1.0}, "q must be a finite non-negative number"),
        ({"seed": 1, "initial_pheromone": 0.0}, "initial_pheromone must be > 0"),
        ({"seed": 1, "ant_count": 0}, "ant_count must be >= 1"),
        ({"seed": 1, "ant_count": True}, "ant_count must be an integer"),
        ({"seed": 1, "colony_count": 0}, "colony_count must be >= 1"),
        ({"seed": 1, "iteration_count": 0}, "iteration_count must be >= 1"),
        (
            {"seed": 1, "ant_count": 20, "colony_count": 3, "iteration_count": 200},
            r"colony_count\*ant_count\*iteration_count must be <= 10000",
        ),
    ],
)
def test_config_parameter_validation_rejects_invalid_inputs(
    kwargs: dict[str, object], match: str
) -> None:
    with pytest.raises(ValueError, match=match):
        CoveringDesignACOConfig(**kwargs)  # pyright: ignore[reportCallIssue,reportArgumentType]


def test_config_accepts_donor_characterized_defaults() -> None:
    config = CoveringDesignACOConfig(seed=1)
    assert (config.alpha, config.beta, config.rho, config.q, config.initial_pheromone) == (
        1.0,
        5.0,
        0.8,
        1.0,
        1.0,
    )
    assert (config.ant_count, config.colony_count, config.iteration_count) == (20, 3, 150)
    assert config.colony_count * config.ant_count * config.iteration_count == 9000
    assert MAX_TOTAL_ANT_CONSTRUCTIONS >= 9000


# ---------------------------------------------------------------------------
# 2. v/k/t validation and prebuild guard reuse
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("v", "k", "t"),
    [
        (3, 4, 2),  # v < k
        (4, 2, 3),  # k < t
        (4, 3, -1),  # t < 0
    ],
)
def test_run_rejects_invalid_v_k_t(v: int, k: int, t: int) -> None:
    config = CoveringDesignACOConfig(seed=1, ant_count=1, colony_count=1, iteration_count=1)
    with pytest.raises(ValueError, match="must be >="):
        run_covering_design_aco(v, k, t, config=config)


def test_run_reuses_existing_setcover_guard_for_v_greater_than_ten() -> None:
    config = CoveringDesignACOConfig(seed=1, ant_count=1, colony_count=1, iteration_count=1)
    with pytest.raises(
        UnsupportedSetCoverDomainError,
        match="covering-design set-cover first port supports only v <= 10",
    ):
        run_covering_design_aco(11, 5, 2, config=config)


def test_guard_exception_is_the_shared_ilp_module_exception() -> None:
    from lottolab.research.covering_design_setcover_ilp import (
        UnsupportedSetCoverDomainError as ilp_error,
    )

    assert issubclass(UnsupportedSetCoverDomainError, ValueError)
    assert UnsupportedSetCoverDomainError is ilp_error


# ---------------------------------------------------------------------------
# 3. Total ant-construction budget guard
# ---------------------------------------------------------------------------


def test_budget_guard_rejects_before_any_search_runs() -> None:
    # 3 * 20 * 200 = 12000 > 10000
    with pytest.raises(ValueError, match="must be <= 10000"):
        CoveringDesignACOConfig(seed=1, ant_count=20, colony_count=3, iteration_count=200)


def test_budget_guard_accepts_donor_default_total_exactly() -> None:
    config = CoveringDesignACOConfig(seed=1)
    assert config.ant_count * config.colony_count * config.iteration_count == 9000


# ---------------------------------------------------------------------------
# 4. Canonical target/block universe
# ---------------------------------------------------------------------------


def test_build_problem_produces_canonical_lexicographic_universe() -> None:
    problem = _build_problem(*V5K3T2)
    assert problem.candidates == tuple(sorted(problem.candidates))
    assert problem.targets == tuple(sorted(problem.targets))
    assert problem.candidate_count == math.comb(5, 3)
    assert problem.target_count == math.comb(5, 2)
    assert all(len(block) == 3 for block in problem.candidates)
    assert all(len(target) == 2 for target in problem.targets)


def test_coverage_masks_match_brute_force_containment() -> None:
    problem = _build_problem(*V5K3T2)
    for index, candidate in enumerate(problem.candidates):
        expected = {target for target in problem.targets if set(target).issubset(candidate)}
        actual = {
            problem.targets[row]
            for row in range(problem.target_count)
            if (problem.coverage_masks[index] >> row) & 1
        }
        assert actual == expected


# ---------------------------------------------------------------------------
# 5 & 6. Deterministic dominance preprocessing; equal-coverage tie break
# ---------------------------------------------------------------------------


def test_dominance_strict_superset_marks_smaller_candidate() -> None:
    # candidate 0 covers {row0}; candidate 1 covers {row0, row1} (strict superset).
    masks = (0b01, 0b11)
    assert _compute_dominance(masks) == (True, False)


def test_dominance_incomparable_sets_mark_neither() -> None:
    masks = (0b01, 0b10)
    assert _compute_dominance(masks) == (False, False)


def test_dominance_equal_coverage_dominates_earlier_index_only() -> None:
    masks = (0b011, 0b011, 0b101)
    assert _compute_dominance(masks) == (True, False, False)


def test_dominance_never_physically_shrinks_the_array() -> None:
    masks = (0b01, 0b11, 0b10)
    assert len(_compute_dominance(masks)) == len(masks)


def test_generic_domain_v5k3t2_has_no_domination_or_mandatory_candidates() -> None:
    # Every candidate is a k-subset, so every candidate covers exactly comb(k, t)
    # rows: coverage cardinalities are always tied. For 1 <= t < k, a block is
    # recoverable from the union of its own t-subsets, so no two distinct
    # k-subsets can ever share an identical coverage set; hence no domination
    # (and, since every row has comb(v - t, k - t) >= 2 coverers here, no
    # mandatory candidate either).
    problem = _build_problem(*V5K3T2)
    dominated = _compute_dominance(problem.coverage_masks)
    assert sum(dominated) == 0
    assert _compute_mandatory(problem.coverage_masks, dominated, problem.target_count) == ()


def test_trivial_t_zero_domain_dominates_all_but_lexicographically_last() -> None:
    problem = _build_problem(*V3K2T0)
    assert _compute_dominance(problem.coverage_masks) == (True, True, False)


# ---------------------------------------------------------------------------
# 7. Mandatory-candidate detection
# ---------------------------------------------------------------------------


def test_mandatory_candidate_is_the_unique_non_dominated_coverer() -> None:
    masks = (0b01, 0b11)  # row0: candidates {0,1}; row1: candidate {1} only
    mandatory = _compute_mandatory(masks, dominated=(False, False), target_count=2)
    assert mandatory == (1,)


def test_mandatory_ignores_dominated_coverers() -> None:
    # candidate 0 covers row0 but is dominated; candidate 1 covers rows {0, 1}.
    masks = (0b01, 0b11)
    mandatory = _compute_mandatory(masks, dominated=(True, False), target_count=2)
    assert mandatory == (1,)


def test_mandatory_is_canonical_sorted_union_across_rows() -> None:
    # row0: candidates 0 and 1 (two coverers, not mandatory via row0)
    # row1: candidate 1 only -> mandatory
    # row2: candidate 2 only -> mandatory
    masks = (0b001, 0b011, 0b100)
    mandatory = _compute_mandatory(masks, dominated=(False, False, False), target_count=3)
    assert mandatory == (1, 2)
    assert mandatory == tuple(sorted(mandatory))


def test_mandatory_fails_closed_on_zero_non_dominated_coverers() -> None:
    with pytest.raises(CoveringDesignACOInvariantError, match="zero non-dominated coverers"):
        _compute_mandatory((0b01,), dominated=(True,), target_count=1)


def test_v3k2t0_mandatory_is_the_lexicographically_last_block() -> None:
    problem = _build_problem(*V3K2T0)
    dominated = _compute_dominance(problem.coverage_masks)
    mandatory = _compute_mandatory(problem.coverage_masks, dominated, problem.target_count)
    assert mandatory == (2,)
    assert problem.candidates[mandatory[0]] == (1, 2)


# ---------------------------------------------------------------------------
# 8 & 9. No physical reduction; pheromone includes dominated; initialization
# ---------------------------------------------------------------------------


def test_pheromone_vector_length_and_initial_value_include_dominated_candidates() -> None:
    problem = _build_problem(*V3K2T0)
    dominated = _compute_dominance(problem.coverage_masks)
    mandatory = _compute_mandatory(problem.coverage_masks, dominated, problem.target_count)
    assert sum(dominated) > 0  # sanity: this domain has genuinely dominated candidates
    config = CoveringDesignACOConfig(
        seed=1, initial_pheromone=2.5, ant_count=1, iteration_count=1, colony_count=1
    )
    colony = _Colony(problem, dominated, mandatory, config, random.Random(1))
    assert len(colony.pheromone) == problem.candidate_count
    assert colony.pheromone == [2.5] * problem.candidate_count


def test_result_arrays_stay_full_size_despite_domination() -> None:
    config = CoveringDesignACOConfig(seed=1, ant_count=2, colony_count=1, iteration_count=2)
    result = run_covering_design_aco(*V3K2T0, config=config)
    assert result.candidate_count == 3
    assert result.dominated_candidate_count == 2
    assert len(result.final_pheromone_vectors[0]) == 3


# ---------------------------------------------------------------------------
# 10, 11, 12. Ant init/preload, uniform canonical row draw, eligible filter
# ---------------------------------------------------------------------------


def test_mandatory_candidates_preload_every_fresh_ant_in_canonical_order() -> None:
    problem = _build_problem(*V3K2T0)
    dominated = _compute_dominance(problem.coverage_masks)
    mandatory = _compute_mandatory(problem.coverage_masks, dominated, problem.target_count)
    pheromone = tuple(1.0 for _ in range(problem.candidate_count))
    for seed in (1, 2, 3):
        constructed = _construct_ant(
            problem, dominated, pheromone, mandatory, 1.0, 5.0, random.Random(seed)
        )
        assert constructed[: len(mandatory)] == mandatory


def test_ant_state_does_not_leak_between_many_sequential_ants() -> None:
    # A mutable-default-argument-style leak would accumulate "visited" state
    # across calls; with enough sequential ants this would eventually starve
    # later ants of eligible candidates. All 30 must independently succeed.
    problem = _build_problem(*V4K2T1)
    dominated = _compute_dominance(problem.coverage_masks)
    pheromone = tuple(1.0 for _ in range(problem.candidate_count))
    rng = random.Random(7)
    for _ in range(30):
        constructed = _construct_ant(problem, dominated, pheromone, (), 1.0, 5.0, rng)
        assert _covers_all_rows(problem, constructed)


def test_uncovered_row_draw_is_seed_reproducible() -> None:
    problem = _build_problem(*V5K3T2)
    dominated = _compute_dominance(problem.coverage_masks)
    pheromone = tuple(1.0 for _ in range(problem.candidate_count))
    a = _construct_ant(problem, dominated, pheromone, (), 1.0, 5.0, random.Random(123))
    b = _construct_ant(problem, dominated, pheromone, (), 1.0, 5.0, random.Random(123))
    assert a == b


def test_mandatory_preload_alone_never_contains_a_dominated_candidate() -> None:
    # V3K2T0's mandatory preload alone already covers its single row, so this
    # only exercises the preload path, not the SROM stochastic loop below.
    problem = _build_problem(*V3K2T0)
    dominated = _compute_dominance(problem.coverage_masks)  # (True, True, False)
    mandatory = _compute_mandatory(problem.coverage_masks, dominated, problem.target_count)
    pheromone = tuple(1.0 for _ in range(problem.candidate_count))
    constructed = _construct_ant(
        problem, dominated, pheromone, mandatory, 1.0, 5.0, random.Random(1)
    )
    assert set(constructed) == {2}
    assert not dominated[2]


def test_eligible_candidates_in_the_srom_loop_exclude_dominated_candidates() -> None:
    # Unlike V3K2T0, this domain has an empty mandatory set, so every row is a
    # genuine stochastic draw and the dominated candidate Z (index 4) is
    # eligible-by-coverage for row 0 unless the dominance check excludes it.
    problem, dominated = _domain_with_one_dominated_candidate_and_no_mandatory()
    pheromone = tuple(1.0 for _ in range(problem.candidate_count))
    for seed in range(50):
        constructed = _construct_ant(
            problem, dominated, pheromone, (), 1.0, 5.0, random.Random(seed)
        )
        assert 4 not in constructed
        assert _covers_all_rows(problem, constructed)


def test_mutation_dominated_candidate_never_enters_construction_despite_high_pheromone() -> None:
    problem, dominated = _domain_with_one_dominated_candidate_and_no_mandatory()
    # Skew pheromone a millionfold so a buggy "dominated candidates are
    # eligible" implementation would select Z in roughly half of these 300
    # seeds (empirically confirmed: 156/300 under that exact mutation); ours
    # must select it in zero.
    pheromone = (0.01, 0.01, 0.01, 0.01, 1_000_000.0)
    for seed in range(300):
        constructed = _construct_ant(
            problem, dominated, pheromone, (), 1.0, 5.0, random.Random(seed)
        )
        assert 4 not in constructed


# ---------------------------------------------------------------------------
# 13 & 14. eta formula and exact alpha/beta weight equation
# ---------------------------------------------------------------------------


def test_selection_weight_exact_alpha_beta_equation() -> None:
    eta, pheromone_value, alpha, beta = 0.5, 2.0, 1.5, 3.0
    expected = eta**beta * pheromone_value**alpha
    assert _selection_weight(eta, pheromone_value, alpha, beta) == expected


def test_mutation_alpha_beta_swap_changes_the_weight() -> None:
    eta, pheromone_value, alpha, beta = 0.5, 2.0, 1.5, 3.0
    correct = _selection_weight(eta, pheromone_value, alpha, beta)
    swapped_mutant = eta**alpha * pheromone_value**beta
    assert correct != swapped_mutant


def test_eta_uses_total_row_count_not_current_uncovered_row_count() -> None:
    coverage_mask = 0b0011  # covers rows 0 and 1
    uncovered_mask = 0b0001  # only row 0 is still uncovered
    total_row_count = 4
    eta = _uncovered_gain_ratio(coverage_mask, uncovered_mask, total_row_count)
    assert eta == 1 / 4
    current_uncovered_count = bin(uncovered_mask).count("1")
    mutant_eta = (coverage_mask & uncovered_mask).bit_count() / current_uncovered_count
    assert eta != mutant_eta  # 1/4 != 1/1


def test_construct_ant_calls_selection_weight_with_alpha_then_beta_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # test_selection_weight_exact_alpha_beta_equation only checks the helper in
    # isolation with hand-picked literals; this observes what _construct_ant's
    # one real call site actually passes, catching an argument-order swap
    # (e.g. `_selection_weight(eta, pheromone[i], beta, alpha)`) at the call
    # site itself, not just inside the helper.
    problem = _build_problem(*V5K3T2)
    dominated = _compute_dominance(problem.coverage_masks)
    pheromone = tuple(1.0 for _ in range(problem.candidate_count))
    captured: list[tuple[float, float]] = []
    real_selection_weight = aco_module._selection_weight

    def _recording_selection_weight(
        eta: float, pheromone_value: float, alpha: float, beta: float
    ) -> float:
        captured.append((alpha, beta))
        return real_selection_weight(eta, pheromone_value, alpha, beta)

    monkeypatch.setattr(aco_module, "_selection_weight", _recording_selection_weight)
    _construct_ant(problem, dominated, pheromone, (), 2.0, 7.0, random.Random(1))
    assert captured  # sanity: the loop actually ran and called it at least once
    assert all(pair == (2.0, 7.0) for pair in captured)


def test_uncovered_row_population_is_canonical_ascending_before_every_draw(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Reproducibility tests only prove self-consistency (same seed twice); a
    # consistently-reversed population would still pass those. This directly
    # inspects the sequence handed to rng.choice on every stochastic row draw.
    problem = _build_problem(*V5K3T2)
    dominated = _compute_dominance(problem.coverage_masks)
    pheromone = tuple(1.0 for _ in range(problem.candidate_count))
    captured: list[tuple[int, ...]] = []
    real_choice = random.Random.choice

    def _recording_choice(self: random.Random, seq: list[int]) -> int:
        captured.append(tuple(seq))
        return real_choice(self, seq)

    monkeypatch.setattr(random.Random, "choice", _recording_choice)
    _construct_ant(problem, dominated, pheromone, (), 1.0, 5.0, random.Random(1))
    assert captured  # sanity: at least one row draw happened
    assert all(population == tuple(sorted(population)) for population in captured)


# ---------------------------------------------------------------------------
# 15. Weighted roulette
# ---------------------------------------------------------------------------


def test_weighted_roulette_respects_weights_and_avoids_zero() -> None:
    rng = random.Random(42)
    weights = (0.0, 5.0, 0.0)
    for _ in range(50):
        assert _weighted_roulette(weights, rng) == 1


def test_weighted_roulette_zero_total_fails_closed() -> None:
    with pytest.raises(CoveringDesignACOInvariantError, match="invalid roulette weight total"):
        _weighted_roulette((0.0, 0.0), random.Random(1))


def test_weighted_roulette_nan_or_infinite_total_fails_closed() -> None:
    with pytest.raises(CoveringDesignACOInvariantError, match="invalid roulette weight total"):
        _weighted_roulette((float("nan"), 1.0), random.Random(1))
    with pytest.raises(CoveringDesignACOInvariantError, match="invalid roulette weight total"):
        _weighted_roulette((float("inf"), 1.0), random.Random(1))


def test_weighted_roulette_roundoff_fallback_selects_final_positive_entry() -> None:
    class _ForceUpperBoundary(random.Random):
        def random(self) -> float:
            return 1.0  # threshold == total exactly; the loop never returns early

    weights = (1.0, 0.0, 2.0)
    result = _weighted_roulette(weights, _ForceUpperBoundary())
    assert result == 2
    assert weights[result] > 0


def test_weighted_roulette_is_seed_reproducible() -> None:
    weights = (1.0, 2.0, 3.0, 0.0)
    a = [_weighted_roulette(weights, random.Random(9)) for _ in range(20)]
    b = [_weighted_roulette(weights, random.Random(9)) for _ in range(20)]
    assert a == b
    assert all(weights[index] > 0 for index in a)


# ---------------------------------------------------------------------------
# 16. Ant construction terminates feasible
# ---------------------------------------------------------------------------


def test_ant_construction_terminates_with_full_feasible_coverage() -> None:
    problem = _build_problem(*V4K2T1)
    dominated = _compute_dominance(problem.coverage_masks)
    pheromone = tuple(1.0 for _ in range(problem.candidate_count))
    for seed in range(15):
        constructed = _construct_ant(
            problem, dominated, pheromone, (), 1.0, 5.0, random.Random(seed)
        )
        assert _covers_all_rows(problem, constructed)
        blocks = tuple(problem.candidates[index] for index in constructed)
        assert not _brute_force_uncovered(V4K2T1[0], V4K2T1[2], blocks)


# ---------------------------------------------------------------------------
# 17. One-pass local search
# ---------------------------------------------------------------------------


def test_local_search_removes_redundant_candidates_in_one_pass() -> None:
    # A={rows0,1}, B={rows1,2}, C={rows0,1,2}: C alone subsumes both A and B.
    problem = _Problem(
        v=3,
        k=1,
        t=1,
        candidates=((0,), (1,), (2,)),
        targets=((0,), (1,), (2,)),
        candidate_count=3,
        target_count=3,
        coverage_masks=(0b011, 0b110, 0b111),
        all_rows_mask=0b111,
        guard_identity="stub",
    )
    outcome = _local_search(problem, (0, 1, 2))
    assert outcome.kept == (2,)
    assert set(outcome.removed) == {0, 1}
    assert _covers_all_rows(problem, outcome.kept)


def test_local_search_previously_marked_cannot_justify_a_later_removal() -> None:
    # X covers {0} only; Y covers {0,1}; Z covers {1,2} (does NOT cover row0).
    # X is redundant (Y alone covers row0). Y must NOT also be marked redundant:
    # once X is excluded, only Z remains as an alternative for Y, and Z does not
    # cover row0, so Y is essential and must survive.
    problem = _Problem(
        v=3,
        k=1,
        t=1,
        candidates=((0,), (1,), (2,)),
        targets=((0,), (1,), (2,)),
        candidate_count=3,
        target_count=3,
        coverage_masks=(0b001, 0b011, 0b110),
        all_rows_mask=0b111,
        guard_identity="stub",
    )
    outcome = _local_search(problem, (0, 1, 2))
    assert outcome.removed == (0,)
    assert outcome.kept == (1, 2)
    assert _covers_all_rows(problem, outcome.kept)


def test_local_search_reaches_a_fixpoint_in_one_pass() -> None:
    # Reapplying local search to its own output must never remove anything
    # further: one correctly-implemented forward pass already reaches the
    # fixpoint for this redundancy rule (verified empirically as well).
    problem = _build_problem(*V5K3T2)
    dominated = _compute_dominance(problem.coverage_masks)
    pheromone = tuple(1.0 for _ in range(problem.candidate_count))
    for seed in range(10):
        constructed = _construct_ant(
            problem, dominated, pheromone, (), 1.0, 5.0, random.Random(seed)
        )
        first_pass = _local_search(problem, constructed)
        second_pass = _local_search(problem, first_pass.kept)
        assert second_pass.removed == ()
        assert second_pass.kept == first_pass.kept


def test_local_search_is_invoked_exactly_once_per_ant(monkeypatch: pytest.MonkeyPatch) -> None:
    # The fixpoint test above shows a second pass would be a no-op on this
    # suite's inputs; this directly proves _local_search is only ever called
    # once per ant, so a chained-second-pass mutation cannot hide behind that
    # coincidence.
    problem = _build_problem(*V5K3T2)
    dominated = _compute_dominance(problem.coverage_masks)
    config = CoveringDesignACOConfig(seed=1, ant_count=3, colony_count=1, iteration_count=2)
    call_count = 0
    real_local_search = aco_module._local_search

    def _counting_local_search(
        problem_arg: _Problem, constructed: tuple[int, ...]
    ) -> aco_module._AntOutcome:
        nonlocal call_count
        call_count += 1
        return real_local_search(problem_arg, constructed)

    monkeypatch.setattr(aco_module, "_local_search", _counting_local_search)
    colony = _Colony(problem, dominated, (), config, random.Random(1))
    colony.run_iteration()
    assert call_count == config.ant_count


def test_local_search_never_increases_cardinality() -> None:
    problem = _build_problem(*V4K2T1)
    dominated = _compute_dominance(problem.coverage_masks)
    pheromone = tuple(1.0 for _ in range(problem.candidate_count))
    for seed in range(15):
        constructed = _construct_ant(
            problem, dominated, pheromone, (), 1.0, 5.0, random.Random(seed)
        )
        outcome = _local_search(problem, constructed)
        assert len(outcome.kept) <= len(outcome.constructed)


def test_local_search_uses_list_order_not_a_resorted_list() -> None:
    problem = _Problem(
        v=3,
        k=1,
        t=1,
        candidates=((0,), (1,), (2,)),
        targets=((0,), (1,), (2,)),
        candidate_count=3,
        target_count=3,
        coverage_masks=(0b111, 0b011, 0b110),
        all_rows_mask=0b111,
        guard_identity="stub",
    )
    # Processing in construction order (2, 1, 0): candidate 2 is checked first
    # (subsumed by candidates 0+1 together) and marked; candidate 1 is checked
    # next with candidate 2 already excluded (subsumed by candidate 0 alone)
    # and marked too; candidate 0 is checked last with nothing left to make it
    # redundant, so it alone survives.
    in_construction_order = _local_search(problem, (2, 1, 0))
    assert in_construction_order.kept == (0,)

    # The identical SET, resorted by index (0, 1, 2), gives a DIFFERENT answer:
    # candidate 0 (checked first here) is marked redundant against {1, 2}
    # together, leaving 1 and 2 to both survive. A "resorted list" bug would
    # silently substitute this result for the order-preserving one above.
    resorted_mutant = _local_search(problem, (0, 1, 2))
    assert resorted_mutant.kept == (1, 2)
    assert in_construction_order.kept != resorted_mutant.kept


def test_mutation_missing_feasibility_check_would_accept_broken_state() -> None:
    problem = _build_problem(*V4K2T1)  # no single candidate covers all 4 rows
    assert not _covers_all_rows(problem, (0,))
    with pytest.raises(CoveringDesignACOInvariantError, match="feasibility failure"):
        _local_search(problem, (0,))


# ---------------------------------------------------------------------------
# 18, 19, 20. Reinforcement uses post-local-search kept set; evaporation
# ---------------------------------------------------------------------------


def test_one_iteration_pheromone_recurrence_oracle() -> None:
    # initial tau=1.0, rho=0.8, Q=1.0; one ready ant of final size 2 selects
    # candidate 0 (and 1); candidate 2 is never selected.
    # selected:   1.0*0.8 + 1.0/2 = 1.3
    # unselected: 1.0*0.8          = 0.8
    problem = _stub_problem(3)
    config = CoveringDesignACOConfig(
        seed=1,
        rho=0.8,
        q=1.0,
        initial_pheromone=1.0,
        ant_count=1,
        colony_count=1,
        iteration_count=1,
    )
    colony = _Colony(problem, (False, False, False), (), config, random.Random(1))
    outcome = aco_module._AntOutcome(constructed=(0, 1), kept=(0, 1), removed=())
    colony._evaporate()
    colony._reinforce((outcome,))
    assert colony.pheromone[0] == pytest.approx(1.3)
    assert colony.pheromone[1] == pytest.approx(1.3)
    assert colony.pheromone[2] == pytest.approx(0.8)


def test_evaporation_occurs_before_reinforcement() -> None:
    problem = _stub_problem(1)
    config = CoveringDesignACOConfig(
        seed=1,
        rho=0.5,
        q=1.0,
        initial_pheromone=1.0,
        ant_count=1,
        colony_count=1,
        iteration_count=1,
    )
    outcome = aco_module._AntOutcome(constructed=(0,), kept=(0,), removed=())

    correct_order = _Colony(problem, (False,), (), config, random.Random(1))
    correct_order._evaporate()
    correct_order._reinforce((outcome,))

    wrong_order = _Colony(problem, (False,), (), config, random.Random(1))
    wrong_order._reinforce((outcome,))
    wrong_order._evaporate()

    assert correct_order.pheromone[0] == pytest.approx(0.5 * 1.0 + 1.0)  # 1.5
    assert wrong_order.pheromone[0] == pytest.approx((1.0 + 1.0) * 0.5)  # 1.0
    assert correct_order.pheromone[0] != pytest.approx(wrong_order.pheromone[0])

    # The real run_iteration seam must match the correct order, not the wrong one.
    seam_colony = _Colony(problem, (False,), (), config, random.Random(1))
    seam_colony._construct_one_ant = lambda _snapshot: outcome  # type: ignore[method-assign]
    seam_colony.run_iteration()
    assert seam_colony.pheromone[0] == pytest.approx(correct_order.pheromone[0])


def test_mutation_rho_is_not_interpreted_as_one_minus_rho() -> None:
    problem = _stub_problem(1)
    config = CoveringDesignACOConfig(
        seed=1, rho=0.8, ant_count=1, colony_count=1, iteration_count=1
    )
    colony = _Colony(problem, (False,), (), config, random.Random(1))
    colony._evaporate()
    correct = 1.0 * 0.8
    mutant = 1.0 * (1 - 0.8)
    assert colony.pheromone[0] == pytest.approx(correct)
    assert colony.pheromone[0] != pytest.approx(mutant)


def test_evaporation_applies_to_every_pheromone_entry() -> None:
    problem = _stub_problem(4)
    config = CoveringDesignACOConfig(
        seed=1, rho=0.3, initial_pheromone=2.0, ant_count=1, colony_count=1, iteration_count=1
    )
    colony = _Colony(problem, (False, False, False, False), (), config, random.Random(1))
    colony._evaporate()
    assert colony.pheromone == [pytest.approx(0.6)] * 4


def test_reinforcement_uses_every_ready_ant_not_best_only() -> None:
    problem = _stub_problem(2)
    config = CoveringDesignACOConfig(
        seed=1, q=1.0, ant_count=2, colony_count=1, iteration_count=1
    )
    colony = _Colony(problem, (False, False), (), config, random.Random(1))
    colony.pheromone = [0.0, 0.0]
    outcome_a = aco_module._AntOutcome(constructed=(0,), kept=(0,), removed=())
    outcome_b = aco_module._AntOutcome(constructed=(1,), kept=(1,), removed=())
    colony._reinforce((outcome_a, outcome_b))
    # A best-only scheme would have left one of these at 0.0.
    assert colony.pheromone[0] == pytest.approx(1.0)
    assert colony.pheromone[1] == pytest.approx(1.0)


def test_reinforcement_uses_post_local_search_kept_not_raw_construction() -> None:
    problem = _stub_problem(2)
    config = CoveringDesignACOConfig(
        seed=1, q=1.0, ant_count=1, colony_count=1, iteration_count=1
    )
    colony = _Colony(problem, (False, False), (), config, random.Random(1))
    colony.pheromone = [0.0, 0.0]
    # Raw construction selected both 0 and 1; local search removed candidate 1.
    outcome = aco_module._AntOutcome(constructed=(0, 1), kept=(0,), removed=(1,))
    colony._reinforce((outcome,))
    assert colony.pheromone[0] == pytest.approx(1.0)  # deposited: in kept
    assert colony.pheromone[1] == pytest.approx(0.0)  # not deposited: removed


def test_reinforcement_deposits_accumulate_across_multiple_ants() -> None:
    problem = _stub_problem(1)
    config = CoveringDesignACOConfig(
        seed=1, q=1.0, ant_count=3, colony_count=1, iteration_count=1
    )
    colony = _Colony(problem, (False,), (), config, random.Random(1))
    colony.pheromone = [0.0]
    outcomes = tuple(
        aco_module._AntOutcome(constructed=(0,), kept=(0,), removed=()) for _ in range(3)
    )
    colony._reinforce(outcomes)
    assert colony.pheromone[0] == pytest.approx(3.0)


def test_exact_q_over_l_reinforcement_formula() -> None:
    problem = _stub_problem(3)
    config = CoveringDesignACOConfig(
        seed=1, q=2.0, ant_count=1, colony_count=1, iteration_count=1
    )
    colony = _Colony(problem, (False, False, False), (), config, random.Random(1))
    colony.pheromone = [0.0, 0.0, 0.0]
    outcome = aco_module._AntOutcome(constructed=(0, 1, 2), kept=(0, 1, 2), removed=())
    colony._reinforce((outcome,))
    expected = 2.0 / 3
    assert colony.pheromone == [pytest.approx(expected)] * 3


# ---------------------------------------------------------------------------
# 21. Colony isolation and deterministic cross-colony best selection
# ---------------------------------------------------------------------------


def test_colony_pheromone_vectors_are_independent_objects() -> None:
    problem = _build_problem(*V4K2T1)
    dominated = _compute_dominance(problem.coverage_masks)
    config = CoveringDesignACOConfig(seed=1, ant_count=2, colony_count=2, iteration_count=2)
    rng = random.Random(config.seed)
    colony_a = _Colony(problem, dominated, (), config, rng)
    colony_b = _Colony(problem, dominated, (), config, rng)
    assert colony_a.pheromone is not colony_b.pheromone
    colony_a.pheromone[0] = 999.0
    assert colony_b.pheromone[0] != 999.0


def test_best_key_orders_by_count_then_lexicographic_block_tuple() -> None:
    problem = _build_problem(*V5K3T2)
    idx_012 = problem.candidates.index((0, 1, 2))
    idx_013 = problem.candidates.index((0, 1, 3))

    # Fewer blocks always wins, regardless of content.
    fewer_blocks = _best_key(problem, (idx_012,))
    more_blocks = _best_key(problem, (idx_012, idx_013))
    assert fewer_blocks < more_blocks

    # Tied block count: the lexicographically smaller block tuple wins.
    tied_a = _best_key(problem, (idx_013,))
    tied_b = _best_key(problem, (idx_012,))
    assert tied_b < tied_a


def test_best_result_is_reported_in_canonical_lexicographic_block_order() -> None:
    config = CoveringDesignACOConfig(seed=5, ant_count=4, colony_count=2, iteration_count=5)
    result = run_covering_design_aco(*V5K3T2, config=config)
    assert result.best_blocks == tuple(sorted(result.best_blocks))


# ---------------------------------------------------------------------------
# 22. Exact generated-solution count and exactly configured iteration count
# ---------------------------------------------------------------------------


def test_generated_solution_count_is_exact() -> None:
    config = CoveringDesignACOConfig(seed=1, ant_count=4, colony_count=3, iteration_count=5)
    result = run_covering_design_aco(*V4K2T1, config=config)
    assert result.generated_solution_count == 4 * 3 * 5


@pytest.mark.parametrize(("ant_count", "colony_count", "iteration_count"), [(2, 1, 1), (3, 2, 4)])
def test_run_completes_exactly_the_configured_iteration_count(
    ant_count: int, colony_count: int, iteration_count: int
) -> None:
    config = CoveringDesignACOConfig(
        seed=1, ant_count=ant_count, colony_count=colony_count, iteration_count=iteration_count
    )
    result = run_covering_design_aco(*V4K2T1, config=config)
    assert result.status is CoveringDesignACOStatus.COMPLETED_HEURISTIC
    assert result.iteration_count == iteration_count
    assert result.colony_count == colony_count
    assert len(result.best_objective_history) == colony_count * iteration_count


# ---------------------------------------------------------------------------
# 23. Reproducibility
# ---------------------------------------------------------------------------


def test_same_seed_and_config_gives_identical_best_result() -> None:
    config = CoveringDesignACOConfig(seed=2026, ant_count=4, colony_count=2, iteration_count=5)
    r1 = run_covering_design_aco(*V5K3T2, config=config)
    r2 = run_covering_design_aco(*V5K3T2, config=config)
    assert r1.best_blocks == r2.best_blocks
    assert r1.best_block_count == r2.best_block_count
    assert r1.deterministic_configuration_identity == r2.deterministic_configuration_identity


def test_same_seed_and_config_gives_identical_auditable_pheromone_state_and_history() -> None:
    config = CoveringDesignACOConfig(seed=42, ant_count=4, colony_count=2, iteration_count=5)
    r1 = run_covering_design_aco(*V5K3T2, config=config)
    r2 = run_covering_design_aco(*V5K3T2, config=config)
    assert r1.final_pheromone_vectors == r2.final_pheromone_vectors
    assert r1.best_objective_history == r2.best_objective_history
    assert r1.generated_solution_count == r2.generated_solution_count


def test_different_seeds_may_diverge() -> None:
    config1 = CoveringDesignACOConfig(seed=1, ant_count=4, colony_count=2, iteration_count=5)
    config2 = CoveringDesignACOConfig(seed=99999, ant_count=4, colony_count=2, iteration_count=5)
    r1 = run_covering_design_aco(*V5K3T2, config=config1)
    r2 = run_covering_design_aco(*V5K3T2, config=config2)
    assert (
        r1.final_pheromone_vectors != r2.final_pheromone_vectors
        or r1.best_objective_history != r2.best_objective_history
        or r1.best_blocks != r2.best_blocks
    )


def test_no_module_global_rng_instance() -> None:
    assert not any(isinstance(value, random.Random) for value in vars(aco_module).values())


def test_source_never_imports_wall_clock_parallel_or_donor_dependencies() -> None:
    # These check actual import/API usage, not the docstring's donor citation
    # (which legitimately names Isula and the donor commit in prose).
    source = inspect.getsource(aco_module)
    for forbidden_import in (
        "import threading",
        "import multiprocessing",
        "import concurrent",
        "from concurrent",
        "import asyncio",
        "import isula",
        "from isula",
        "import numpy",
        "from numpy",
        "commons_math",
        "commons-math",
    ):
        assert forbidden_import not in source.lower()
    for wall_clock_api in ("time.time(", "time.monotonic(", "datetime.now("):
        assert wall_clock_api not in source


# ---------------------------------------------------------------------------
# 24, 25. Never claims exact/global optimum
# ---------------------------------------------------------------------------


def test_result_status_never_claims_global_optimum() -> None:
    config = CoveringDesignACOConfig(seed=1, ant_count=2, colony_count=1, iteration_count=2)
    result = run_covering_design_aco(*V4K2T1, config=config)
    assert result.status is CoveringDesignACOStatus.COMPLETED_HEURISTIC
    assert "CERTIFIED" not in str(result.status)
    assert "OPTIMUM" not in str(result.status)
    assert "OPTIMAL" not in [status.name for status in CoveringDesignACOStatus]


# ---------------------------------------------------------------------------
# 26. Independent cover verification
# ---------------------------------------------------------------------------


def test_independently_verify_cover_true_for_a_genuine_cover() -> None:
    blocks = ((0, 1, 2), (0, 1, 3), (0, 1, 4), (2, 3, 4))
    assert _independently_verify_cover(5, 2, blocks) is True


def test_independently_verify_cover_false_for_a_broken_cover() -> None:
    blocks = ((0, 1, 2),)  # cannot cover every pair of a 5-element ground set
    assert _independently_verify_cover(5, 2, blocks) is False


def test_run_fails_closed_when_independent_verification_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _always_false(v: int, t: int, blocks: tuple[Block, ...]) -> bool:
        del v, t, blocks
        return False

    monkeypatch.setattr(aco_module, "_independently_verify_cover", _always_false)
    config = CoveringDesignACOConfig(seed=1, ant_count=2, colony_count=1, iteration_count=2)
    with pytest.raises(
        CoveringDesignACOInvariantError, match="failed independent cover verification"
    ):
        run_covering_design_aco(*V4K2T1, config=config)


def test_fixed_seed_toy_run_preserves_a_valid_cover() -> None:
    config = CoveringDesignACOConfig(seed=12345, ant_count=6, colony_count=2, iteration_count=10)
    result = run_covering_design_aco(*V5K3T2, config=config)
    assert not _brute_force_uncovered(5, 2, result.best_blocks)
    # The covering number C(5, 3, 2) is 4.
    assert 4 <= result.best_block_count <= math.comb(5, 3)


# ---------------------------------------------------------------------------
# 27. Config identity
# ---------------------------------------------------------------------------


def test_config_identity_changes_when_load_bearing_config_changes() -> None:
    base = CoveringDesignACOConfig(seed=1, ant_count=2, colony_count=1, iteration_count=2)
    changed = CoveringDesignACOConfig(
        seed=1, alpha=2.0, ant_count=2, colony_count=1, iteration_count=2
    )
    result_base = run_covering_design_aco(*V4K2T1, config=base)
    result_changed = run_covering_design_aco(*V4K2T1, config=changed)
    assert (
        result_base.deterministic_configuration_identity
        != result_changed.deterministic_configuration_identity
    )


# ---------------------------------------------------------------------------
# 28. Immutability
# ---------------------------------------------------------------------------


def test_data_structures_are_immutable() -> None:
    config = CoveringDesignACOConfig(seed=1, ant_count=2, colony_count=1, iteration_count=2)
    with pytest.raises(FrozenInstanceError):
        config.seed = 2  # pyright: ignore[reportAttributeAccessIssue]

    result = run_covering_design_aco(*V4K2T1, config=config)
    assert isinstance(result, CoveringDesignACOResult)
    with pytest.raises(FrozenInstanceError):
        result.best_block_count = 0  # pyright: ignore[reportAttributeAccessIssue]

    outcome = aco_module._AntOutcome(constructed=(0,), kept=(0,), removed=())
    with pytest.raises(FrozenInstanceError):
        outcome.kept = ()  # pyright: ignore[reportAttributeAccessIssue]


# ---------------------------------------------------------------------------
# 29. Objective minimizes block count
# ---------------------------------------------------------------------------


def test_objective_is_block_count_cardinality() -> None:
    problem = _build_problem(*V4K2T1)
    key = _best_key(problem, (0, 1))
    assert key[0] == 2
