from __future__ import annotations

import itertools
import random
from collections.abc import Iterable

import pytest

from lottolab.research.covering_design_tabu7 import (
    TabuSearch7RunConfig,
    _calculate_delta_conflict_value,  # pyright: ignore[reportPrivateUsage]
    _Candidate,  # pyright: ignore[reportPrivateUsage]
    _construct_initial_design,  # pyright: ignore[reportPrivateUsage]
    _CoveringDesign,  # pyright: ignore[reportPrivateUsage]
    _snapshot_blocks,  # pyright: ignore[reportPrivateUsage]
    _TabuListItem,  # pyright: ignore[reportPrivateUsage]
    _TabuSearch7,  # pyright: ignore[reportPrivateUsage]
    run_covering_design_tabu7,
)


def _brute_force_conflicts(
    v: int, t: int, blocks: Iterable[Iterable[int]]
) -> set[tuple[int, ...]]:
    normalized_blocks = [set(block) for block in blocks]
    return {
        subset
        for subset in itertools.combinations(range(v), t)
        if not any(set(subset).issubset(block) for block in normalized_blocks)
    }


def _block_lists(design: _CoveringDesign) -> list[tuple[int, ...]]:
    return [tuple(sorted(block.elements)) for block in design.blocks]


def _toy_search(
    v: int = 5,
    k: int = 3,
    t: int = 2,
    blocks: Iterable[Iterable[int]] = ((0, 1, 2), (0, 3, 4), (1, 3, 4)),
) -> _TabuSearch7:
    design = _CoveringDesign.from_blocks(v, k, t, blocks)
    return _TabuSearch7(design, random.Random(7))


@pytest.mark.parametrize(
    ("v", "k", "t"),
    [(3, 2, 2), (4, 4, 2), (4, 3, 3), (4, 3, 1), (2, 1, 0)],
)
def test_invalid_domain_configuration_is_rejected(v: int, k: int, t: int) -> None:
    config = TabuSearch7RunConfig(constructor_seed=1, search_seed=2, max_iterations=1)
    with pytest.raises(ValueError, match="v > k > t >= 2"):
        run_covering_design_tabu7(v, k, t, config=config)


def test_invalid_iteration_bound_is_rejected() -> None:
    with pytest.raises(ValueError, match="max_iterations"):
        TabuSearch7RunConfig(constructor_seed=1, search_seed=2, max_iterations=0)


def test_initial_blocks_are_full_and_have_unique_elements() -> None:
    design = _construct_initial_design(6, 4, 2, random.Random(11))
    assert design.blocks
    assert all(len(block.elements) == 4 for block in design.blocks)
    assert all(len(block.elements) == len(set(block.elements)) for block in design.blocks)


def test_exact_conflict_accounting_matches_brute_force_oracle() -> None:
    design = _CoveringDesign.from_blocks(
        5, 3, 2, ((0, 1, 2), (0, 3, 4), (1, 3, 4), (2, 3, 4))
    )
    assert set(design.uncovered_t_subsets) == _brute_force_conflicts(
        5, 2, _block_lists(design)
    )
    design.remove_block(design.blocks[0])
    assert set(design.uncovered_t_subsets) == _brute_force_conflicts(
        5, 2, _block_lists(design)
    )


def test_t_three_complete_covering_is_exact_all_t_subset_coverage() -> None:
    blocks = tuple(itertools.combinations(range(5), 4))
    design = _CoveringDesign.from_blocks(5, 4, 3, blocks)
    assert design.conflict_count() == 0
    assert not _brute_force_conflicts(5, 3, blocks)


def test_constructor_seed_reproduces_initial_construction() -> None:
    first = _construct_initial_design(6, 4, 2, random.Random(19))
    second = _construct_initial_design(6, 4, 2, random.Random(19))
    assert _block_lists(first) == _block_lists(second)
    assert first.uncovered_t_subsets == second.uncovered_t_subsets


def test_candidate_generation_has_one_out_one_in_from_uncovered_union() -> None:
    search = _toy_search()
    candidates = search.generate_candidates()
    assert candidates
    incoming_union: set[int] = set()
    for subset in search.design.uncovered_t_subsets:
        incoming_union.update(subset)
    for candidate in candidates:
        assert candidate.swapped_out_element in candidate.block.elements
        assert candidate.swapped_in_element not in candidate.block.elements
        assert candidate.swapped_in_element in incoming_union


def test_candidate_delta_matches_brute_force_recomputation() -> None:
    search = _toy_search()
    block = search.design.blocks[0]
    outgoing, incoming = 0, 3
    delta = _calculate_delta_conflict_value(search.design, block, outgoing, incoming)
    before = search.design.conflict_count()
    expected_design = _CoveringDesign.from_blocks(
        search.design.v,
        search.design.k,
        search.design.t,
        [
            (set(item.elements) - {outgoing}) | {incoming}
            if item is block
            else item.elements
            for item in search.design.blocks
        ],
    )
    assert before + delta == expected_design.conflict_count()


def test_tabu_in_and_out_directionality_is_block_local() -> None:
    search = _toy_search()
    block = search.design.blocks[0]
    candidate = _Candidate(block, 0, 3, 2, 2)

    search.tabu_list_out.append(_TabuListItem(block.identifier, 3))
    assert search.is_tabu(candidate)
    search.tabu_list_out.clear()
    search.tabu_list_in.append(_TabuListItem(block.identifier, 0))
    assert search.is_tabu(candidate)
    search.tabu_list_in.clear()
    search.tabu_list_out.append(_TabuListItem(block.identifier + 1, 3))
    assert not search.is_tabu(candidate)


def test_zero_conflict_candidate_has_aspiration_over_tabu() -> None:
    search = _toy_search()
    block = search.design.blocks[0]
    candidate = _Candidate(block, 0, 3, 0, 0)
    search.tabu_list_out.append(candidate.tabu_in)
    assert search.get_best_candidate([candidate]) is candidate


def test_block_removal_zero_damage_uses_first_canonical_block() -> None:
    search = _toy_search(
        blocks=((0, 1, 2), (0, 1, 2), (0, 3, 4), (1, 3, 4), (2, 3, 4))
    )
    removed = search.remove_block()
    assert tuple(sorted(removed.elements)) == (0, 1, 2)
    assert len(search.design.blocks) == 4


def test_block_removal_without_zero_damage_chooses_only_minimum_damage_family() -> None:
    search = _toy_search()
    damage = {
        tuple(sorted(block.elements)): search._calculate_delta_conflict_value_for_removal(  # pyright: ignore[reportPrivateUsage]
            block
        )
        for block in search.design.blocks
    }
    minimum = min(damage.values())
    removed = search.remove_block()
    assert damage[tuple(sorted(removed.elements))] == minimum
    assert len(search.design.blocks) == 2


def test_complete_covering_is_saved_then_one_block_removed() -> None:
    design = _CoveringDesign.from_blocks(5, 4, 3, itertools.combinations(range(5), 4))
    search = _TabuSearch7(design, random.Random(3))
    original = _snapshot_blocks(design.blocks)
    assert design.conflict_count() == 0
    search.save_solution_and_remove_block()
    assert search.solution == original
    assert len(design.blocks) == len(original) - 1
    assert search.lowest_conflicts == design.conflict_count()


def test_tabu_iterations_and_perturbation_trigger_use_donor_formula(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    search = _toy_search()
    expected = int(
        len(search.design.blocks)
        * (2 + 1 / search.design.t)
        * len(search.design.blocks) ** 0.6
    )
    assert search.tabu_iterations == expected

    calls: list[int] = []

    def fake_perturbate(current: _TabuSearch7) -> None:
        calls.append(current.count)

    monkeypatch.setattr(_TabuSearch7, "perturbate", fake_perturbate)
    search.count = 2 * search.tabu_iterations
    search.check_diversification()
    assert calls == [2 * search.tabu_iterations]


def test_perturbation_tie_condition_bug_is_preserved() -> None:
    search = _toy_search(
        v=6,
        k=3,
        t=2,
        blocks=((0, 1, 2), (0, 1, 3), (0, 2, 3)),
    )
    candidates = search.perturbation_block_candidates()
    # All three blocks tie at score 5.  Correct tie handling would retain all
    # three; donor-parity retains only the first because it compares the
    # constant covered-subset size (3) with the score (5).
    assert [block.identifier for block in candidates] == [0]


def test_full_config_is_reproducible_and_stops_at_iteration_limit() -> None:
    config = TabuSearch7RunConfig(constructor_seed=29, search_seed=31, max_iterations=8)
    first = run_covering_design_tabu7(6, 4, 2, config=config)
    second = run_covering_design_tabu7(6, 4, 2, config=config)
    assert first == second
    assert first.iterations == config.max_iterations
    assert first.termination_reason == "ITERATION_LIMIT"


def test_cutoff_keeps_last_complete_covering_separate_from_current_state() -> None:
    config = TabuSearch7RunConfig(constructor_seed=5, search_seed=7, max_iterations=1)
    result = run_covering_design_tabu7(6, 4, 3, config=config)
    assert result.best_complete_blocks
    assert not _brute_force_conflicts(6, 3, result.best_complete_blocks)
    assert result.final_conflicts == len(
        _brute_force_conflicts(6, 3, result.final_blocks)
    )
    assert result.final_conflicts > 0
    assert result.best_complete_blocks != result.final_blocks


def test_public_documentation_does_not_claim_java_python_trajectory_parity() -> None:
    from lottolab.research import covering_design_tabu7

    documentation = covering_design_tabu7.__doc__ or ""
    assert "JAVA_PYTHON_TRAJECTORY_PARITY: NOT_CLAIMED" in documentation
    assert "pair-specific" in documentation
