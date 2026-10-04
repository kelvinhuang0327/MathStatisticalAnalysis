"""Focused checks for the K20 r=4 residual-union certificate."""

from __future__ import annotations

from collections import Counter
from itertools import product
from math import comb
from pathlib import Path
from typing import cast

from lottolab.research.b649_k20_r4_dangerous_assignment_exact_r8 import (
    DANGEROUS_VECTOR_TYPES,
)
from lottolab.research.b649_k20_r4_dangerous_residual_union_r9 import (
    COMPRESSED_ASSIGNMENT_CLASS_COLUMNS,
    analyze_dangerous_residual_union,
    joint_residual_union_upper_bound,
    load_compressed_assignment_classes,
    maximum_residual_multiplicity,
    minimum_pair_mass_for_residual_multiplicity,
    residual_pair_cost_rows,
    residual_s3_upper_bound,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
R7_RESULT_PATH = (
    REPOSITORY_ROOT
    / "docs/research/matrix-native-results/"
    "b649-k20-r4-exact-anchor-realizability-r7-result.json"
)
R8_RESULT_PATH = (
    REPOSITORY_ROOT
    / "docs/research/matrix-native-results/"
    "b649-k20-r4-dangerous-assignment-exact-r8-result.json"
)

GOOD = (0, 0, 0, 6)
SPECIAL_A = (0, 1, 0, 5)
SPECIAL_B = (0, 0, 1, 5)
GOOD_GOOD_RESIDUAL_PAIRS = (
    107_800,
    574_000,
    1_691_956,
    3_453_079,
    6_178_984,
)
SPECIAL_GOOD_RESIDUAL_PAIRS = (
    107_800,
    571_200,
    1_680_112,
    3_430_525,
    6_149_892,
)


def test_exact_r7_vectors_reload_with_all_r8_component_strata() -> None:
    classes = load_compressed_assignment_classes(R7_RESULT_PATH, R8_RESULT_PATH)

    assert len(classes) == 18
    assert tuple(dict.fromkeys(type_counts for type_counts, _ in classes)) == (
        DANGEROUS_VECTOR_TYPES
    )
    assert tuple(component_count for _, component_count in classes[:6]) == tuple(
        range(1, 7)
    )
    assert tuple(type_counts for type_counts, _ in classes[::6]) == (
        DANGEROUS_VECTOR_TYPES
    )


def test_exact_residual_pair_tables_match_each_mirrored_class() -> None:
    good_rows = residual_pair_cost_rows(((GOOD, 18),))
    assert set(good_rows) == {GOOD_GOOD_RESIDUAL_PAIRS}

    for special in (SPECIAL_A, SPECIAL_B):
        mirrored_rows = residual_pair_cost_rows(((GOOD, 17), (special, 1)))
        assert Counter(mirrored_rows) == Counter(
            {
                GOOD_GOOD_RESIDUAL_PAIRS: comb(17, 2),
                SPECIAL_GOOD_RESIDUAL_PAIRS: 17,
            }
        )


def test_mass_budget_caps_simultaneous_residual_wins() -> None:
    assert minimum_pair_mass_for_residual_multiplicity(13) == 90
    assert minimum_pair_mass_for_residual_multiplicity(14) == 105
    assert maximum_residual_multiplicity(91) == 13
    assert maximum_residual_multiplicity(93) == 13
    assert maximum_residual_multiplicity(104) == 13
    assert maximum_residual_multiplicity(105) == 14


def test_joint_moment_oracle_exhausts_small_event_systems() -> None:
    for event_count in range(1, 6):
        event_masks = range(1 << event_count)
        for outcomes in product(event_masks, repeat=3):
            multiplicities = tuple(mask.bit_count() for mask in outcomes)
            residual_s1 = sum(multiplicities)
            residual_s2 = sum(comb(count, 2) for count in multiplicities)
            residual_s3 = sum(comb(count, 3) for count in multiplicities)
            exact_union = sum(count > 0 for count in multiplicities)

            assert joint_residual_union_upper_bound(
                residual_s1,
                residual_s2,
                event_count,
            ) >= exact_union
            assert residual_s3_upper_bound(residual_s2, event_count) >= residual_s3


def test_all_18_joint_envelopes_produce_a_strict_r4_improvement() -> None:
    result = analyze_dangerous_residual_union(R7_RESULT_PATH, R8_RESULT_PATH)
    vectors = cast(list[dict[str, object]], result["DANGEROUS_VECTOR_RESULTS"])
    classes = cast(list[list[object]], result["COMPRESSED_ASSIGNMENT_CLASSES"])
    columns = cast(list[str], result["COMPRESSED_ASSIGNMENT_CLASS_COLUMNS"])

    assert result["DANGEROUS_REALIZATION_COUNT"] == 3
    assert result["RESIDUAL_CLASS_COUNT"] == 18
    assert [row["RESIDUAL_S1"] for row in vectors] == [
        331_588_656,
        331_152_556,
        331_152_556,
    ]
    assert [row["RESIDUAL_S2_BOUND"] for row in vectors] == [
        59_850_000,
        58_870_000,
        58_870_000,
    ]
    assert [row["MAXIMUM_RESIDUAL_EVENT_MULTIPLICITY_AT_FLOOR"] for row in vectors] == [
        13,
        13,
        13,
    ]
    assert [row["MINIMUM_JOINT_UNION_REDUCTION"] for row in vectors] == [
        9_207_693,
        9_056_924,
        9_056_924,
    ]
    assert [row["R4_BOUND"] for row in vectors] == [
        353_379_315,
        353_093_984,
        353_093_984,
    ]
    assert len(classes) == 18
    assert tuple(columns) == COMPRESSED_ASSIGNMENT_CLASS_COLUMNS
    component_index = columns.index("COMPONENT_COUNT")
    assert [row[component_index] for row in classes[:6]] == list(range(1, 7))
    assert all(len(row) == len(columns) for row in classes)
    assert result["SUCCESS_B"] is True
    assert result["SUCCESS_A"] is False
    assert result["FAMILY_A_BOTTLENECK_R"] == 4
    assert result["SOLVER_STATUS"] == "EXACT_DYNAMIC_PROGRAM_OPTIMAL"


__all__ = [
    "test_all_18_joint_envelopes_produce_a_strict_r4_improvement",
    "test_exact_r7_vectors_reload_with_all_r8_component_strata",
    "test_exact_residual_pair_tables_match_each_mirrored_class",
    "test_joint_moment_oracle_exhausts_small_event_systems",
    "test_mass_budget_caps_simultaneous_residual_wins",
]
