# pyright: reportPrivateUsage=false
"""Contracts for the checkpointable K10 overlap-mass-12 screen."""

from __future__ import annotations

import itertools
from collections import Counter
from math import comb

import pytest

import lottolab.research.b649_k10_overlap_mass12_bonferroni_screen_r1 as research
from lottolab.research.b649_k10_overlap_mass12_bonferroni_screen_r1 import (
    _canonicalize_state,
    _iter_extensions,
    _owned_prefix_parents,
    _portfolio_from_state,
    _state_from_key,
    _state_key,
    exact_union_outcome_count,
    incumbent_outcome_count,
    prove_mass12_profiles,
    total_official_outcomes,
    u3_outcome_count,
)


def _family_b_state() -> tuple[int, tuple[int, ...], int]:
    pairs = tuple(itertools.combinations(range(10), 2))
    edge_pairs = ((0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 8), (0, 8))
    weights = tuple(int(pair in edge_pairs) for pair in pairs)
    return 10, weights, 0b0000000111


def _relabel_state(
    state: tuple[int, tuple[int, ...], int], new_to_old: tuple[int, ...]
) -> tuple[int, tuple[int, ...], int]:
    vertex_count, weights, triple_mask = state
    matrix = [[0] * vertex_count for _ in range(vertex_count)]
    cursor = 0
    for left in range(vertex_count):
        for right in range(left + 1, vertex_count):
            matrix[left][right] = weights[cursor]
            matrix[right][left] = weights[cursor]
            cursor += 1
    reordered_weights = tuple(
        matrix[new_to_old[left]][new_to_old[right]]
        for left in range(vertex_count)
        for right in range(left + 1, vertex_count)
    )
    reordered_mask = sum(
        1 << new_index
        for new_index, old_index in enumerate(new_to_old)
        if triple_mask & (1 << old_index)
    )
    return vertex_count, reordered_weights, reordered_mask


def _brute_orbit_key(
    state: tuple[int, tuple[int, ...], int],
) -> tuple[int, tuple[int, ...]]:
    vertex_count = state[0]
    return min(
        (reordered[2], reordered[1])
        for order in itertools.permutations(range(vertex_count))
        for reordered in (_relabel_state(state, order),)
    )


def test_mass12_profiles_are_exactly_the_two_proved_histograms() -> None:
    proof = prove_mass12_profiles()
    assert proof["profiles"] == {
        "A": {"1": 36, "2": 12},
        "B": {"1": 39, "2": 9, "3": 1},
    }
    assert proof["used_label_range"] == [48, 49]


def test_family_b_reconstructs_one_number_shared_by_exactly_three_tickets() -> None:
    portfolio = _portfolio_from_state(_family_b_state(), "B")
    frequencies = Counter(number for ticket in portfolio for number in ticket)
    triple_numbers = [number for number, frequency in frequencies.items() if frequency == 3]
    assert len(triple_numbers) == 1
    assert sum(triple_numbers[0] in ticket for ticket in portfolio) == 3
    assert sorted(Counter(frequencies.values()).items()) == [(1, 39), (2, 9), (3, 1)]


def test_triple_hyperedge_is_not_canonicalized_as_three_pair_edges() -> None:
    pairs = tuple(itertools.combinations(range(10), 2))
    triangle_weights = tuple(int(pair in {(0, 1), (0, 2), (1, 2)}) for pair in pairs)
    triple_state = (10, (0,) * len(pairs), 0b0000000111)
    pair_triangle_state = (10, triangle_weights, 0)
    assert _state_key(_canonicalize_state(triple_state)) != _state_key(
        _canonicalize_state(pair_triangle_state)
    )


def test_state_canonicalization_is_invariant_to_ticket_relabeling() -> None:
    state = _family_b_state()
    order = (6, 3, 8, 1, 9, 4, 0, 7, 2, 5)
    assert _canonicalize_state(state) == _canonicalize_state(_relabel_state(state, order))


def test_small_weighted_state_canonicalizer_matches_brute_force_orbits() -> None:
    vertex_count = 4
    edge_count = comb(vertex_count, 2)
    triple_masks = (0, 0b0111, 0b1011, 0b1101, 0b1110)
    observed_by_orbit: dict[tuple[int, tuple[int, ...]], tuple[int, tuple[int, ...], int]] = {}
    orbit_by_observed: dict[tuple[int, tuple[int, ...], int], tuple[int, tuple[int, ...]]] = {}
    for edge_bits in range(1 << edge_count):
        weights = tuple((edge_bits >> index) & 1 for index in range(edge_count))
        for triple_mask in triple_masks:
            state = (vertex_count, weights, triple_mask)
            oracle = _brute_orbit_key(state)
            canonical = _canonicalize_state(state)
            assert observed_by_orbit.setdefault(oracle, canonical) == canonical
            assert orbit_by_observed.setdefault(canonical, oracle) == oracle


def test_u3_is_invariant_to_ticket_and_number_permutations_for_family_b() -> None:
    portfolio = _portfolio_from_state(_family_b_state(), "B")
    ticket_permuted = tuple(reversed(portfolio))
    label_map = {number: ((number + 16) % 49) + 1 for number in range(1, 50)}
    label_permuted = tuple(
        tuple(sorted(label_map[number] for number in ticket)) for ticket in portfolio
    )
    original_bound = u3_outcome_count(portfolio)
    assert u3_outcome_count(ticket_permuted) == original_bound
    assert u3_outcome_count(label_permuted) == original_bound


def test_family_b_u3_dominates_exact_union_on_a_small_lottery() -> None:
    tickets = ((1, 4, 5), (1, 4, 6), (1, 5, 7))
    bound = u3_outcome_count(tickets, pool_size=7, draw_size=3)
    exact = exact_union_outcome_count(tickets, pool_size=7, draw_size=3)
    assert bound >= exact
    assert exact > 0


def test_incumbent_threshold_is_an_exact_integer_outcome_count() -> None:
    outcomes = total_official_outcomes()
    numerator = 536_005
    denominator = 1_827_672
    assert numerator * outcomes % denominator == 0
    assert incumbent_outcome_count(numerator, denominator) == (
        numerator * outcomes // denominator
    )
    assert outcomes == comb(49, 6) * 43


def test_deterministic_parent_shards_reproduce_a_small_full_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(research, "TICKET_COUNT", 4)

    def expand_one_stage(class_ids: set[str]) -> set[str]:
        return {
            _state_key(_canonicalize_state(child))
            for class_id in class_ids
            for child in _iter_extensions(
                _state_from_key(class_id), target_pair_mass=1, target_triples=0
            )
        }

    root_ids = {_state_key((0, (), 0))}
    split_parent_ids = expand_one_stage(expand_one_stage(root_ids))
    partitions = [
        _owned_prefix_parents(sorted(split_parent_ids), family="A", shard_index=index)
        for index in range(2)
    ]
    flattened = [class_id for partition in partitions for class_id in partition]
    assert len(flattened) == len(set(flattened))
    assert set(flattened) == split_parent_ids

    full_ids = split_parent_ids
    for _ in range(2):
        full_ids = expand_one_stage(full_ids)
    sharded_ids: set[str] = set()
    for partition in partitions:
        shard_ids = set(partition)
        for _ in range(2):
            shard_ids = expand_one_stage(shard_ids)
        sharded_ids.update(shard_ids)
    assert sharded_ids == full_ids
