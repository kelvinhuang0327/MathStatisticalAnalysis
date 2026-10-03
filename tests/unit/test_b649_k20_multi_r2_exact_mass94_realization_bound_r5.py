"""Focused checks for the exact K20 mass-94 realization bound."""

from __future__ import annotations

from itertools import combinations
from math import comb

import pytest

from lottolab.research.b649_k20_heavy_pair_defect_global_bound_r2 import (
    triple_intersection_count,
)
from lottolab.research.b649_k20_multi_r2_exact_mass94_realization_bound_r5 import (
    enumerate_multiplicity_profiles_dynamic,
    enumerate_multiplicity_profiles_recursive,
    exact_mass_94_s2,
    result_record,
    support_common_triples,
    support_pair_weights,
    ticket_overlap_degree_cap,
    triangle_common_linear_certificate,
    weighted_wedge_certificate,
)
from lottolab.research.b649_k20_outside_min_s2_global_penalty_bound_r1 import INCUMBENT


def test_independent_profile_enumerators_find_the_two_exact_profiles() -> None:
    recursive = enumerate_multiplicity_profiles_recursive()
    dynamic = enumerate_multiplicity_profiles_dynamic()

    assert recursive == dynamic
    assert len(recursive) == 2
    assert [
        {m: profile.count(m) for m in range(1, 5) if profile.count(m)} for profile in recursive
    ] == [{2: 28, 3: 20, 4: 1}, {1: 1, 2: 25, 3: 23}]
    assert [profile.shared_triple_mass for profile in recursive] == [24, 23]
    assert all(
        (profile.label_count, profile.incidence_count, profile.pair_mass) == (49, 120, 94)
        for profile in recursive
    )


def test_support_classes_add_pair_cliques_and_common_triple_counts() -> None:
    supports = ((0, 1, 2), (0, 1, 3), (2, 3))

    assert support_pair_weights(supports, vertex_count=4) == {
        (0, 1): 2,
        (0, 2): 1,
        (0, 3): 1,
        (1, 2): 1,
        (1, 3): 1,
        (2, 3): 1,
    }
    common = support_common_triples(supports, vertex_count=4)
    assert common == {(0, 1, 2): 1, (0, 1, 3): 1}
    assert sum(common.values()) == 2

    weights = support_pair_weights(supports, vertex_count=4)
    for left, middle, right in combinations(range(4), 3):
        overlaps = (
            weights.get((left, middle), 0),
            weights.get((left, right), 0),
            weights.get((middle, right), 0),
        )
        common_count = common.get((left, middle, right), 0)
        assert triple_intersection_count(overlaps, common_count) >= 0

    with pytest.raises(ValueError, match="greater than two"):
        support_pair_weights(((0, 1, 2), (0, 1, 3), (0, 1, 4)), vertex_count=5)


def test_pair_and_triple_contributions_match_the_exact_tables() -> None:
    assert exact_mass_94_s2() == 93_815_260
    assert ticket_overlap_degree_cap() == 13
    assert triangle_common_linear_certificate() == (206_843, 77_455)

    base, bonus = triangle_common_linear_certificate()
    for left in (1, 2):
        for middle in (1, 2):
            for right in (1, 2):
                overlaps: tuple[int, int, int] = (left, middle, right)
                for common in range(min(overlaps) + 1):
                    try:
                        contribution = triple_intersection_count(overlaps, common)
                    except ValueError:
                        continue
                    assert contribution <= base + bonus * common


def test_wedge_toy_and_result_close_every_mass_94_profile() -> None:
    weights = support_pair_weights(((0, 1, 2), (0, 1, 3), (2, 3)), vertex_count=4)
    heavy_degrees = [0] * 4
    light_degrees = [0] * 4
    for (left, right), weight in weights.items():
        degrees = heavy_degrees if weight == 2 else light_degrees
        degrees[left] += 1
        degrees[right] += 1
    toy_wedges = sum(
        comb(heavy, 2) + heavy * light + comb(light, 2)
        for heavy, light in zip(heavy_degrees, light_degrees, strict=True)
    )
    assert toy_wedges == 12
    assert len(tuple(combinations(range(4), 3))) == 4

    certificate = weighted_wedge_certificate()
    assert (
        certificate.heavy_heavy_wedges,
        certificate.heavy_light_wedges,
        certificate.light_light_wedges,
        certificate.triangle_count,
    ) == (225, 48, 28, 100)

    record = result_record()
    family_bound = record["FAMILY_B_BOUND"]
    assert isinstance(family_bound, int)
    assert record["S1"] == 364_421_560
    assert record["S2"] == 93_815_260
    assert record["S3_BOUND"] == 32_612_580
    assert family_bound == 303_218_880
    assert family_bound <= INCUMBENT
    assert record["COVERAGE_BOUND_METHOD"] == "Bonferroni upper bound S1 - S2 + S3"
    assert record["FAMILY_B_STATUS"] == "CLOSED"
    assert record["MULTIPLICITY_PROFILE_COUNT"] == 2
    assert record["PAIR_GRAPH_REALIZABLE"] == "NOT_CLASSIFIED"
    assert record["SOLVER_STATUS"] == "NOT_RUN"
