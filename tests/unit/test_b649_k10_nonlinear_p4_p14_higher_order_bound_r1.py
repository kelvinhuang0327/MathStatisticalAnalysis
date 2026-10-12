from __future__ import annotations

import copy
import itertools
import json
from fractions import Fraction
from pathlib import Path
from typing import cast

import pytest

from lottolab.research.b649_k10_nonlinear_p4_p14_higher_order_bound_r1 import (
    INCUMBENT_OUTCOME_COUNT,
    S1,
    minimum_s2_rows,
    pair_multiplicity_histograms,
    verify_bound_artifact,
    verify_histogram_certificate,
)
from lottolab.research.b649_k10_overlap_mass12_bonferroni_screen_r1 import (
    _joint_count_from_regions,  # pyright: ignore[reportPrivateUsage]
)

ARTIFACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs/research/matrix-native-results/"
    / "b649-k10-nonlinear-p4-p14-higher-order-bound-r1.json"
)
EXPECTED_P_FAMILY_UPPER_BOUNDS = (
    166_606_321,
    172_924_626,
    173_710_649,
    173_920_210,
    174_074_789,
    174_209_597,
    174_359_364,
    174_468_396,
    174_618_854,
    174_724_433,
    174_876_272,
)


def _read_artifact() -> dict[str, object]:
    value = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def test_convex_s2_minima_and_pair_histograms_cover_each_p_family() -> None:
    assert tuple(row["minimum_s2"] for row in minimum_s2_rows()) == (
        26_563_278,
        21_661_710,
        19_701_990,
        17_742_270,
        16_434_516,
        15_778_728,
        15_122_940,
        14_467_152,
        13_811_364,
        13_155_576,
        12_499_788,
    )
    assert tuple(
        len(pair_multiplicity_histograms(occupied)) for occupied in range(4, 15)
    ) == (5, 12, 14, 14, 11, 9, 6, 5, 3, 2, 1)
    for occupied in range(4, 15):
        for histogram in pair_multiplicity_histograms(occupied):
            assert len(histogram) == 6
            assert sum(histogram) == 45
            assert sum(multiplicity * count for multiplicity, count in enumerate(histogram)) == 15
            assert sum(histogram[1:]) == occupied


def test_exact_duals_close_every_nonlinear_histogram_and_p_family() -> None:
    artifact = _read_artifact()
    rows = verify_bound_artifact(artifact)

    assert tuple(row["maximum_u3_upper"] for row in rows) == EXPECTED_P_FAMILY_UPPER_BOUNDS
    assert all(row["closed_at_incumbent"] is True for row in rows)
    assert cast(
        tuple[int, ...],
        rows[-1]["maximizing_pair_multiplicity_histogram_n0_to_n5"],
    ) == (31, 13, 1, 0, 0, 0)
    assert INCUMBENT_OUTCOME_COUNT - EXPECTED_P_FAMILY_UPPER_BOUNDS[-1] == 1_469_373
    assert artifact["global_optimum_status"] == "PROVEN"
    assert artifact["remaining_gap"] == 0
    assert artifact["optional_s4"] == "NOT_NEEDED_SUCCESS_A"


def test_certificate_verifier_rejects_a_corrupted_dual() -> None:
    artifact = _read_artifact()
    certificates = cast(list[dict[str, object]], artifact["histogram_certificates"])
    certificate = copy.deepcopy(certificates[0])
    dual = cast(dict[str, object], certificate["dual_certificate"])
    dual["row_count"] = str(Fraction(cast(str, dual["row_count"])) - 1_000_000_000)
    corrupted_s3 = (
        Fraction(cast(str, certificate["s3_upper_rational"])) - 120_000_000_000
    )
    corrupted_s3_upper = corrupted_s3.numerator // corrupted_s3.denominator
    certificate["s3_upper_rational"] = str(corrupted_s3)
    certificate["s3_integer_upper"] = corrupted_s3_upper
    certificate["u3_upper"] = S1 - cast(int, certificate["s2"]) + corrupted_s3_upper

    with pytest.raises(ValueError, match="degree-conditioned local event row"):
        verify_histogram_certificate(certificate)


def test_small_brute_force_matches_the_three_ticket_venn_count() -> None:
    tickets = (
        frozenset((0, 1, 2)),
        frozenset((0, 3, 4)),
        frozenset((2, 5, 6)),
    )
    brute_force = 0
    labels = set(range(8))
    for main in itertools.combinations(labels, 3):
        main_set = set(main)
        for special in labels - main_set:
            winning_set = main_set | {special}
            if all(len(ticket & winning_set) >= 2 for ticket in tickets):
                brute_force += 1

    formula = _joint_count_from_regions((1, 2, 1, 2, 1, 0, 0), 3, 8, 3, 2)
    assert formula == brute_force
