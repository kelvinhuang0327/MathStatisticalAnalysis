"""Focused checks for the K20 r=4 joint residual S2/S3 proof."""

from __future__ import annotations

from functools import lru_cache
from itertools import product
from math import comb
from pathlib import Path
from time import monotonic
from typing import cast

from lottolab.research.b649_k20_r4_joint_residual_r10 import (
    EXPECTED_REALIZATIONS,
    analyze_joint_residual_envelope,
    frequency_mass_bitsets,
    load_r9_residual_classes,
    residual_s3_upper_bound,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
R9_RESULT_PATH = (
    REPOSITORY_ROOT
    / "docs/research/matrix-native-results/"
    "b649-k20-r4-dangerous-residual-union-r9-result.json"
)
GOOD = (0, 0, 0, 6)
SPECIAL_A = (0, 1, 0, 5)
SPECIAL_B = (0, 0, 1, 5)


@lru_cache(maxsize=1)
def _result() -> dict[str, object]:
    return analyze_joint_residual_envelope(R9_RESULT_PATH)


def test_loads_exact_r9_realizations_and_all_eighteen_classes() -> None:
    classes = load_r9_residual_classes(R9_RESULT_PATH)

    assert len(classes) == 18
    assert tuple(dict.fromkeys(row.vector_label for row in classes)) == (
        EXPECTED_REALIZATIONS
    )
    assert tuple(row.component_count for row in classes[:6]) == tuple(range(1, 7))
    assert tuple(row.component_count for row in classes[6:12]) == tuple(range(1, 7))
    assert tuple(row.component_count for row in classes[12:]) == tuple(range(1, 7))
    assert classes[0].type_counts == ((GOOD, 18),)
    assert classes[6].type_counts == ((GOOD, 17), (SPECIAL_B, 1))
    assert classes[12].type_counts == ((GOOD, 17), (SPECIAL_A, 1))
    assert [classes[index].residual_s1 for index in (0, 6, 12)] == [
        331_588_656,
        331_152_556,
        331_152_556,
    ]
    assert [classes[index].residual_s2_floor for index in (0, 6, 12)] == [
        59_850_000,
        58_870_000,
        58_870_000,
    ]


def test_label_frequency_bitsets_match_a_small_exact_oracle() -> None:
    deadline = monotonic() + 5
    label_count = 3
    incidence_total = 4
    maximum_mass = 6
    bitsets = frequency_mass_bitsets(
        label_count, incidence_total, maximum_mass, deadline
    )
    expected: dict[int, set[int]] = {incidences: set() for incidences in range(5)}
    for frequencies in product(range(5), repeat=label_count):
        incidences = sum(frequencies)
        if incidences <= incidence_total:
            expected[incidences].add(sum(comb(value, 2) for value in frequencies))
    actual = {
        incidences: {
            mass
            for mass in range(maximum_mass + 1)
            if bitsets[incidences] & (1 << mass)
        }
        for incidences in range(incidence_total + 1)
    }

    assert actual == {key: value for key, value in expected.items() if key <= 4}


def test_joint_s2_s3_toy_oracle_exhausts_small_event_systems() -> None:
    for multiplicity_cap in range(1, 8):
        for multiplicities in product(range(multiplicity_cap + 1), repeat=4):
            residual_s1 = sum(multiplicities)
            residual_s2 = sum(comb(value, 2) for value in multiplicities)
            residual_s3 = sum(comb(value, 3) for value in multiplicities)
            exact_union = sum(value > 0 for value in multiplicities)
            reduction = (2 * residual_s2 + multiplicity_cap - 1) // multiplicity_cap

            assert residual_s1 - reduction >= exact_union
            assert residual_s3_upper_bound(residual_s2, multiplicity_cap) >= residual_s3


def test_joint_frequency_cap_separates_minimum_s2_from_maximum_s3() -> None:
    result = _result()
    envelopes = cast(list[dict[str, object]], result["JOINT_RESIDUAL_ENVELOPE"])

    assert [row["MAXIMUM_SELECTED_SEVEN_FREQUENCY_AT_MASS_FLOOR"] for row in envelopes] == [
        21,
        21,
        21,
    ]
    assert [row["RESIDUAL_MULTIPLICITY_CAP_AT_MASS_FLOOR"] for row in envelopes] == [
        7,
        7,
        7,
    ]
    for row in envelopes:
        separation = cast(dict[str, object], row["S3_SEPARATION_PROOF"])
        assert separation["MINIMUM_S2_CANNOT_ATTAIN_GLOBAL_MAXIMUM"] is True
        assert cast(int, separation["MINIMUM_S2_S3_CAP"]) < cast(
            int, separation["SAME_MASS_MAXIMUM_S3_CAP"]
        )
        assert cast(int, separation["MINIMUM_S2_S3_CAP"]) < cast(
            int, separation["GLOBAL_MAXIMUM_S3_CAP"]
        )
        assert cast(dict[str, object], row["MAXIMUM_S3_ENVELOPE"])[
            "IS_EXACT_TRIPLE_TOTAL"
        ] is False


def test_joint_frontier_closes_r4_success_b_and_switches_family_a_bottleneck() -> None:
    result = _result()
    envelopes = cast(list[dict[str, object]], result["JOINT_RESIDUAL_ENVELOPE"])

    assert result["REALIZATION_COUNT"] == 3
    assert result["RESIDUAL_CLASS_COUNT"] == 18
    assert cast(int, result["JOINT_STATE_COUNT"]) > 0
    assert result["S2_S3_FRONTIER_SIZE"] == sum(
        cast(int, row["S2_S3_FRONTIER_SIZE"]) for row in envelopes
    )
    assert all(row["S2_S3_FRONTIER"] for row in envelopes)
    assert cast(int, result["R4_BOUND"]) < 351_483_978
    assert cast(int, result["R4_BOUND"]) < 353_379_315
    assert result["R4_STATUS"] == "TIGHTENED_OPEN_SUCCESS_B"
    assert result["FAMILY_A_RECOMPUTED_BOUND"] == 351_483_978
    assert result["FAMILY_A_BOTTLENECK_R"] == 3
    assert result["INCUMBENT"] == 313_239_661
