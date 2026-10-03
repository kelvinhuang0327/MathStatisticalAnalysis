from __future__ import annotations

import itertools
from collections import Counter
from math import comb

from lottolab.research.b649_k10_profile_42_3_4_exact_closure_r1 import (
    INCUMBENT_OUTCOME_COUNT,
    OVERLAP_MASS,
    collision_bound_rows,
    combine_profile_upper_bound,
    linear_core_bound,
    materialize_profile_hypergraph,
    pair_event_counts,
)
from lottolab.research.b649_official_any_prize_exact import evaluate_portfolio

LINEAR_SUPPORTS = (
    (0, 1, 2),
    (3, 4, 5),
    (6, 7, 8),
    (0, 3, 6),
    (0, 4),
    (1, 5),
    (2, 9),
)


def _direct_pair_outcome_count(
    *, pool_size: int, draw_size: int, outright_matches: int, shared: int
) -> int:
    first = set(range(draw_size))
    second = set(range(shared)) | set(range(draw_size, 2 * draw_size - shared))
    labels = set(range(pool_size))
    outcomes = 0
    for main in itertools.combinations(labels, draw_size):
        main_set = set(main)
        for special in labels - main_set:
            winning_set = main_set | {special}
            if all(
                len(ticket & winning_set) >= outright_matches
                for ticket in (first, second)
            ):
                outcomes += 1
    return outcomes


def test_pair_intersection_formula_matches_independent_small_enumeration() -> None:
    pool_size = 8
    draw_size = 3
    outright_matches = 2
    formula = pair_event_counts(
        pool_size=pool_size,
        draw_size=draw_size,
        outright_matches=outright_matches,
    )

    for shared, formula_count in enumerate(formula[:draw_size]):
        assert formula_count == _direct_pair_outcome_count(
            pool_size=pool_size,
            draw_size=draw_size,
            outright_matches=outright_matches,
            shared=shared,
        )


def test_collision_sensitive_s2_closes_the_three_pair_family() -> None:
    rows = collision_bound_rows()

    assert pair_event_counts() == (
        107_800,
        574_000,
        1_695_988,
        3_469_942,
        6_224_512,
        10_776_332,
    )
    assert OVERLAP_MASS == 15
    assert rows[0].occupied_pairs == 3
    assert rows[0].pair_intersection_lower_bound == 36_856_596
    assert rows[0].outcome_upper_bound == 173_828_788
    assert rows[0].outcome_upper_bound < INCUMBENT_OUTCOME_COUNT
    assert rows[1].occupied_pairs == 4
    assert rows[1].pair_intersection_lower_bound == 26_563_278
    assert rows[1].outcome_upper_bound == 177_259_894
    assert rows[-2].occupied_pairs == 14
    assert rows[-2].pair_intersection_lower_bound == 12_499_788
    assert rows[-2].outcome_upper_bound == 181_947_724
    assert rows[-1].pair_intersection_lower_bound == 11_844_000
    assert rows[-1].outcome_upper_bound == 182_166_320
    assert combine_profile_upper_bound(183_875_720) == 181_947_724
    assert combine_profile_upper_bound() == 181_947_724


def test_linear_core_triple_intersections_give_a_strict_profile_bound() -> None:
    result = linear_core_bound()

    assert result.pair_intersection_sum == 11_844_000
    assert result.triple_intersection_counts == (0, 0, 2_800, 20_272, 7_000)
    assert result.wedge_upper_bound == 120
    assert result.graph_triangle_upper_bound == comb(10, 3)
    assert result.triple_intersection_sum_upper_bound == 1_707_552
    assert result.outcome_upper_bound == 175_977_872
    assert result.outcome_upper_bound < INCUMBENT_OUTCOME_COUNT


def test_materialization_and_singleton_relabeling_preserve_exact_coverage() -> None:
    portfolio = materialize_profile_hypergraph(LINEAR_SUPPORTS)

    assert len(portfolio) == 10
    assert len(set(portfolio)) == 10
    assert all(len(ticket) == 6 and len(set(ticket)) == 6 for ticket in portfolio)
    label_multiplicities = Counter(
        sum(label in ticket for ticket in portfolio) for label in range(1, 50)
    )
    assert label_multiplicities == Counter({1: 42, 2: 3, 3: 4})

    actual_repeated_supports = Counter(
        tuple(vertex for vertex, ticket in enumerate(portfolio) if label in ticket)
        for label in range(1, 8)
    )
    expected_repeated_supports = Counter(tuple(sorted(support)) for support in LINEAR_SUPPORTS)
    assert actual_repeated_supports == expected_repeated_supports

    singleton_permutation = {label: 57 - label for label in range(8, 50)}
    relabeled = tuple(
        tuple(sorted(singleton_permutation.get(label, label) for label in ticket))
        for ticket in portfolio
    )
    before = evaluate_portfolio(portfolio).official_any_prize_outcome_count
    after = evaluate_portfolio(relabeled).official_any_prize_outcome_count
    assert before == after
    assert before <= linear_core_bound().outcome_upper_bound
