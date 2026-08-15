"""Verification of the Strategy Matrix Phase 5 non-Sidon low-overlap
cross-lottery synthesis.

Independently re-derives the headline exact numbers directly from the three
SEALED source result JSONs (not from the synthesis script's own output),
then cross-checks against `build_synthesis()` -- so a bug in the synthesis
script's arithmetic would fail this test even though the script would
happily report an internally-consistent-but-wrong number. Reads no
historical draw data and performs no new enumeration; all inputs are the
already-published `exact` fraction strings from the three sealed arm-B
cells.
"""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
from tools.generate_strategy_matrix_phase5_non_sidon_low_overlap_synthesis import (
    CELLS,
    LADDER,
    NONTRIVIAL_LADDER,
    build_synthesis,
)

RESULTS_DIR = Path("docs/research/matrix-native-results")


@pytest.fixture(scope="module")
def synthesis() -> dict[str, Any]:
    return build_synthesis()


@pytest.fixture(scope="module")
def raw_sources() -> dict[str, dict[str, Any]]:
    return {
        lottery: json.loads(spec["source_path"].read_text(encoding="utf-8"))
        for lottery, spec in CELLS.items()
    }


def _raw_q_and_deltas(lottery: str, data: dict[str, Any]) -> dict[str, dict[int, Fraction]]:
    """Independent extraction straight from each raw source, bypassing the
    generator's own `_extract_*` helpers entirely."""
    if lottery == "BIG_LOTTO":
        q_b = {k: Fraction(data["q"]["b"]["3"][str(k)]["exact"]) for k in LADDER}
        q_sidon = {k: Fraction(data["q"]["a"]["3"][str(k)]["exact"]) for k in LADDER}
        q_random = {k: Fraction(data["q"]["d"]["3"][str(k)]["exact"]) for k in LADDER}
    else:
        q_b = {k: Fraction(data["q"]["b"]["3"][str(k)]["exact"]) for k in LADDER}
        q_sidon = {k: Fraction(data["q"]["a"]["3"][str(k)]["exact"]) for k in LADDER}
        q_random = {k: Fraction(data["q"]["c"]["3"][str(k)]["exact"]) for k in LADDER}
    return {
        "q_arm_b": q_b,
        "q_sidon": q_sidon,
        "q_random": q_random,
        "delta_random_b": {k: q_b[k] - q_random[k] for k in LADDER},
        "delta_sidon": {k: q_b[k] - q_sidon[k] for k in LADDER},
        "delta_random_sidon": {k: q_sidon[k] - q_random[k] for k in LADDER},
    }


def test_inputs_are_the_three_sealed_arm_b_cells(synthesis: dict[str, Any]) -> None:
    assert set(synthesis["inputs"]) == {"BIG_LOTTO", "DAILY_539", "POWER_LOTTO_zone1"}
    assert synthesis["evidence_type"] == "EXACT_COMBINATORIAL"
    assert synthesis["hypothesis_family_id"] == "DIVERSIFICATION"
    assert synthesis["mechanism_family"] == "NON_SIDON_LOW_OVERLAP"
    assert synthesis["ladder"] == [1, 3, 5, 10, 15, 20]
    assert (
        synthesis["cross_lottery_classification"]
        == "NON_SIDON_LOW_OVERLAP_SUPPORTED_ACROSS_3_NATIVE_LOTTERY_STRUCTURES"
    )
    # B649's arm-B id is embedded under a differently-named frontier cell;
    # T539/P638 Zone-1's cells ARE arm B, so their two ids coincide.
    assert (
        synthesis["inputs"]["BIG_LOTTO"]["source_matrix_variant_id"]
        != synthesis["inputs"]["BIG_LOTTO"]["arm_b_constructor_id"]
    )
    assert synthesis["inputs"]["BIG_LOTTO"]["arm_b_constructor_id"] == (
        "GREEDY_MIN_OVERLAP_CONSTRUCTOR_B649_V1"
    )
    for lot in ("DAILY_539", "POWER_LOTTO_zone1"):
        assert (
            synthesis["inputs"][lot]["source_matrix_variant_id"]
            == synthesis["inputs"][lot]["arm_b_constructor_id"]
        )


def test_delta_random_b_and_delta_sidon_independently_recomputed_from_raw_sources(
    synthesis: dict[str, Any], raw_sources: dict[str, dict[str, Any]]
) -> None:
    for lottery, data in raw_sources.items():
        independent = _raw_q_and_deltas(lottery, data)
        cell = synthesis["per_lottery"][lottery]
        for k in LADDER:
            assert Fraction(cell["q_arm_b"][str(k)]["exact"]) == independent["q_arm_b"][k]
            assert Fraction(cell["q_sidon"][str(k)]["exact"]) == independent["q_sidon"][k]
            assert (
                Fraction(cell["q_random_expected"][str(k)]["exact"]) == independent["q_random"][k]
            )
            assert (
                Fraction(cell["delta_random_b"][str(k)]["exact"])
                == independent["delta_random_b"][k]
            )
            assert Fraction(cell["delta_sidon"][str(k)]["exact"]) == independent["delta_sidon"][k]
            assert (
                Fraction(cell["delta_random_sidon"][str(k)]["exact"])
                == independent["delta_random_sidon"][k]
            )
        # k=1 must be exactly zero in every one of the three raw deltas.
        assert independent["delta_random_b"][1] == 0
        assert independent["delta_sidon"][1] == 0
        assert independent["delta_random_sidon"][1] == 0


def test_q1_q2_q3_hold_for_all_three(synthesis: dict[str, Any]) -> None:
    assert synthesis["q1_arm_b_beats_random_every_k_gt_1"]["holds_for_all_three"] is True
    assert synthesis["q2_arm_b_beats_sidon_every_k_gt_1"]["holds_for_all_three"] is True
    assert synthesis["q3_direction_consistent_across_all_three"] is True
    for lottery in CELLS:
        assert synthesis["q1_arm_b_beats_random_every_k_gt_1"]["per_lottery"][lottery] is True
        assert synthesis["q2_arm_b_beats_sidon_every_k_gt_1"]["per_lottery"][lottery] is True


def test_delta_sidon_shape_pinned_values(synthesis: dict[str, Any]) -> None:
    # Pins the actual peak locations so a future silent change to any of the
    # three sealed source files is caught here, not just downstream in prose.
    peak_k = synthesis["delta_sidon_shape_comparison"]["per_lottery_peak_k"]
    assert peak_k == {"BIG_LOTTO": 15, "DAILY_539": 15, "POWER_LOTTO_zone1": 5}
    shapes = synthesis["delta_sidon_shape_comparison"]["per_lottery_shape"]
    assert shapes["BIG_LOTTO"] == "PEAKING_AT_K15"
    assert shapes["DAILY_539"] == "PEAKING_AT_K15"
    assert shapes["POWER_LOTTO_zone1"] == "PEAKING_AT_K5"
    # DELTA_SIDON must still be strictly positive at every tested k>1 despite
    # the non-monotonic shape (Q2 requires positivity, not monotonicity).
    for lottery in CELLS:
        cell = synthesis["per_lottery"][lottery]
        assert all(cell["delta_sidon"][str(k)]["float"] > 0 for k in NONTRIVIAL_LADDER)


def test_relative_gain_over_sidon_peaks_at_k5_in_all_three(synthesis: dict[str, Any]) -> None:
    peak_k = synthesis["relative_gain_over_sidon_shape_comparison"]["per_lottery_peak_k"]
    assert peak_k == {"BIG_LOTTO": 5, "DAILY_539": 5, "POWER_LOTTO_zone1": 5}
    assert synthesis["common_geometry_invariants"][
        "relative_gain_over_sidon_peaks_at_k5_in_every_lottery"
    ] is True
    gain = {
        lottery: synthesis["per_lottery"][lottery]["relative_gain_over_sidon"]
        for lottery in CELLS
    }
    assert gain["BIG_LOTTO"]["1"] == "NOT_APPLICABLE_K1"
    assert gain["BIG_LOTTO"]["3"]["float"] == pytest.approx(5.9145, abs=1e-3)
    assert gain["BIG_LOTTO"]["5"]["float"] == pytest.approx(6.0765, abs=1e-3)
    assert gain["BIG_LOTTO"]["20"]["float"] == pytest.approx(1.6383, abs=1e-3)
    assert gain["DAILY_539"]["5"]["float"] == pytest.approx(2.6779, abs=1e-3)
    assert gain["POWER_LOTTO_zone1"]["5"]["float"] == pytest.approx(3.4786, abs=1e-3)
    # Peak strictly greater than both neighbours in every lottery.
    for lottery in CELLS:
        g = synthesis["per_lottery"][lottery]["relative_gain_over_sidon"]
        assert g["5"]["float"] > g["3"]["float"]
        assert g["5"]["float"] > g["10"]["float"]


def test_relative_lift_random_monotonic_and_k20_pinned(synthesis: dict[str, Any]) -> None:
    assert (
        synthesis["common_geometry_invariants"][
            "relative_lift_random_monotonic_nondecreasing_in_every_lottery"
        ]
        is True
    )
    lift20 = {
        lottery: synthesis["per_lottery"][lottery]["relative_lift_random_pct"]["20"]
        for lottery in CELLS
    }
    assert lift20["BIG_LOTTO"] == pytest.approx(6.9461, abs=1e-3)
    assert lift20["DAILY_539"] == pytest.approx(5.8710, abs=1e-3)
    assert lift20["POWER_LOTTO_zone1"] == pytest.approx(11.8876, abs=1e-3)
    assert lift20["POWER_LOTTO_zone1"] > lift20["BIG_LOTTO"] > lift20["DAILY_539"]


def test_common_geometry_invariants(synthesis: dict[str, Any]) -> None:
    inv = synthesis["common_geometry_invariants"]
    assert inv["max_pairwise_overlap_never_exceeds_1_in_any_lottery"] is True
    assert inv["zero_duplicate_tickets_in_any_lottery_at_any_k"] is True
    assert inv["overlap_profile_keys_subset_of_0_1_in_every_lottery"] is True
    for lottery in CELLS:
        cell = synthesis["per_lottery"][lottery]
        for k in LADDER:
            g = cell["geometry"][str(k)]
            assert g["max_pairwise_overlap"] <= 1
            assert g["duplicate_tickets"] == 0
            assert set(g["overlap_profile"]) <= {"0", "1"}
        assert cell["geometry"]["1"]["max_pairwise_overlap"] == 0
        assert cell["geometry"]["20"]["max_pairwise_overlap"] == 1


def test_lottery_specific_full_pool_coverage_differs(synthesis: dict[str, Any]) -> None:
    coverage = synthesis["lottery_specific_differences"][
        "reaches_full_pool_unique_number_coverage_by_k20_by_lottery"
    ]
    assert coverage == {"BIG_LOTTO": False, "DAILY_539": True, "POWER_LOTTO_zone1": True}
    big_lotto_geom20 = synthesis["per_lottery"]["BIG_LOTTO"]["geometry"]["20"]
    assert big_lotto_geom20["unique_number_coverage"] == 48
    assert big_lotto_geom20["unique_number_coverage_over_pool_size"] == "48/49"
    for lottery in ("DAILY_539", "POWER_LOTTO_zone1"):
        geom20 = synthesis["per_lottery"][lottery]["geometry"]["20"]
        assert geom20["unique_number_coverage"] == synthesis["per_lottery"][lottery]["pool_size"]
    assert (
        synthesis["lottery_specific_differences"][
            "delta_sidon_peak_k_shared_by_big_lotto_and_daily_539_only"
        ]
        is True
    )


def test_claim_boundary_and_phase5_priority_not_executed(synthesis: dict[str, Any]) -> None:
    claim = synthesis["claim_boundary"]
    assert claim["predictive_advantage"] == "NOT_TESTED"
    assert claim["profitability"] == "NOT_TESTED"
    assert claim["prize_value_advantage"] == "NOT_TESTED"
    assert claim["economic_optimality"] == "NOT_TESTED"
    assert claim["all_low_overlap_constructors_equivalent"] == "NOT_CLAIMED"
    assert claim["global_optimum"] == "NOT_CLAIMED"
    assert claim["p638_zone2_or_full_ticket_behavior"] == "NOT_TESTED"
    assert claim["arm_c_bounded_optimizer_replication_to_t539_p638"] == "NOT_RUN"
    assert claim["new_lottery_execution"] == "NONE"

    scope = synthesis["scope"]
    assert scope["new_enumeration_performed"] == "NO"
    assert scope["historical_draw_data_read"] == "NO"
    assert scope["p638_zone2_touched"] == "NO"
    assert scope["arm_a_arm_c_arm_d_mutated"] == "NO"

    priority = synthesis["phase5_priority_decision"]
    assert priority["recommendation"] == "B_STUDY_LOW_OVERLAP_GEOMETRY_MECHANISM_FIRST"
    assert priority["executed"] is False
    assert priority["authorization"] == "NOT_AUTHORIZED_BY_THIS_TASK"
    assert len(priority["options_considered"]) == 2


def test_result_json_matches_generated_synthesis_and_report_contains_required_strings(
    synthesis: dict[str, Any],
) -> None:
    result_path = (
        RESULTS_DIR
        / "strategy-matrix-phase5-non-sidon-low-overlap-cross-lottery-synthesis-v1-result.json"
    )
    assert json.loads(result_path.read_text(encoding="utf-8")) == synthesis

    report_path = (
        RESULTS_DIR
        / "strategy-matrix-phase5-non-sidon-low-overlap-cross-lottery-synthesis-v1-report.md"
    )
    report = report_path.read_text(encoding="utf-8")
    for required in (
        "NON_SIDON_LOW_OVERLAP_SUPPORTED_ACROSS_3_NATIVE_LOTTERY_STRUCTURES",
        "PEAKING_AT_K15",
        "PEAKING_AT_K5",
        "REL_GAIN_OVER_SIDON",
        "DELTA_SIDON",
        "RECOMMENDATION: B",
        "NOT_AUTHORIZED_BY_THIS_TASK",
    ):
        assert required in report
    assert report.rstrip().endswith(
        "Do not start Arm-C replication or another Phase-5 mechanism in this task."
    )
