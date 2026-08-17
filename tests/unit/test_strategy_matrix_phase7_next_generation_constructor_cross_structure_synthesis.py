"""Verification of the Strategy Matrix Phase 7 next-generation-constructor
cross-structure synthesis.

Independently re-derives the headline exact numbers directly from the three
pinned SEALED source commits (not from the synthesis script's own
extraction helpers), then cross-checks against `build_synthesis()` -- so a
bug in the synthesis script's own arithmetic would fail this test even
though the script would happily report an internally-consistent-but-wrong
number. Reads no historical draw data and performs no new enumeration; all
inputs are the already-published `exact` fraction strings from the three
sealed Phase-7 cells, read via `git show <pinned-commit>:<path>` exactly as
the generator itself does (local `main` does not contain any of the three
files -- see the generator module's own docstring and the report's §7).
"""

from __future__ import annotations

import json
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
from tools.generate_strategy_matrix_phase7_next_generation_constructor_cross_structure_synthesis import (  # noqa: E501
    CONSTRUCTOR_ID,
    LADDER,
    OUTPUT_PATH,
    REPO_ROOT,
    STRUCTURES,
    build_synthesis,
)

REPORT_PATH = (
    Path("docs/research/matrix-native-results")
    / "strategy-matrix-phase7-next-generation-constructor-cross-structure-synthesis-v1-report.md"
)

SUPERIORITY_K = (10, 15, 20)
TIE_K = (1, 3, 5)


@pytest.fixture(scope="module")
def synthesis() -> dict[str, Any]:
    return build_synthesis()


def _independent_read(commit: str, path: Path) -> dict[str, Any]:
    """Bypasses the module's own `_read_pinned_blob`/`load_source` entirely."""
    proc = subprocess.run(
        ["git", "show", f"{commit}:{path.as_posix()}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


@pytest.fixture(scope="module")
def raw_sources() -> dict[str, dict[str, Any]]:
    return {
        key: _independent_read(spec["commit"], spec["result_path"])
        for key, spec in STRUCTURES.items()
    }


def test_determinism_two_independent_builds_are_identical() -> None:
    first = build_synthesis()
    second = build_synthesis()
    assert first == second


def test_inputs_are_the_three_sealed_structures(synthesis: dict[str, Any]) -> None:
    assert set(synthesis["inputs"]) == {
        "STRUCTURE_A_B649",
        "STRUCTURE_B_T539",
        "STRUCTURE_C_P638_ZONE1",
    }
    assert synthesis["constructor_id"] == CONSTRUCTOR_ID == "GREEDY_MINMAX_THEN_SUM_OVERLAP_V1"
    assert synthesis["global_optimum_status"] == "UNKNOWN"
    assert synthesis["ladder"] == [1, 3, 5, 10, 15, 20]
    assert (
        synthesis["synthesis_classification"]
        == "NEXT_GEN_CONSTRUCTOR_SUPPORTED_IN_3_NATIVE_STRUCTURES"
    )
    assert synthesis["synthesis_classification_matches_structure_c_sealed_field"] is True
    assert synthesis["inputs"]["STRUCTURE_A_B649"]["role"] == "DISCOVERY_ADVANCE"
    assert synthesis["inputs"]["STRUCTURE_B_T539"]["role"] == "NATIVE_REPLICATION_1"
    assert synthesis["inputs"]["STRUCTURE_C_P638_ZONE1"]["role"] == "NATIVE_REPLICATION_2_FINAL"


def test_pinned_commits_are_full_sha1_and_reachable(raw_sources: dict[str, dict[str, Any]]) -> None:
    for key, spec in STRUCTURES.items():
        assert len(spec["commit"]) == 40
        assert all(c in "0123456789abcdef" for c in spec["commit"])
        assert raw_sources[key]["study_id"] == spec["study_id"]
        assert raw_sources[key]["constructor_id"] == CONSTRUCTOR_ID
        assert raw_sources[key]["exposure_ladder"] == list(LADDER)


def test_q_e_q_ref_q_random_and_deltas_independently_recomputed(
    synthesis: dict[str, Any], raw_sources: dict[str, dict[str, Any]]
) -> None:
    for key, data in raw_sources.items():
        cell_out = synthesis["per_structure"][key]["per_k"]
        for k in LADDER:
            raw = data["per_k"][str(k)]
            q_e = Fraction(raw["q_e"]["numerator"], raw["q_e"]["denominator"])
            q_ref = Fraction(raw["q_b"]["numerator"], raw["q_b"]["denominator"])
            q_rand = Fraction(raw["q_d"]["numerator"], raw["q_d"]["denominator"])
            assert Fraction(cell_out[str(k)]["q_e"]["exact"]) == q_e
            assert Fraction(cell_out[str(k)]["q_previous_reference"]["exact"]) == q_ref
            assert Fraction(cell_out[str(k)]["q_random_expected"]["exact"]) == q_rand

            delta_ref = q_e - q_ref
            delta_rand = q_e - q_rand
            assert Fraction(cell_out[str(k)]["delta_e_vs_reference"]["exact"]) == delta_ref
            assert Fraction(cell_out[str(k)]["delta_e_vs_random"]["exact"]) == delta_rand
            # Cross-check against each source's own already-sealed delta fields.
            sealed_delta_ref = Fraction(
                raw["delta_e_vs_b"]["numerator"], raw["delta_e_vs_b"]["denominator"]
            )
            sealed_delta_rand = Fraction(
                raw["delta_e_vs_d"]["numerator"], raw["delta_e_vs_d"]["denominator"]
            )
            assert delta_ref == sealed_delta_ref
            assert delta_rand == sealed_delta_rand

        # k=1 must tie exactly (zero delta both ways) in every structure.
        assert Fraction(cell_out["1"]["delta_e_vs_reference"]["exact"]) == 0
        assert Fraction(cell_out["1"]["delta_e_vs_random"]["exact"]) == 0


def test_e_ties_reference_exactly_at_k_1_3_5_in_all_three(synthesis: dict[str, Any]) -> None:
    for key in STRUCTURES:
        for k in TIE_K:
            cell = synthesis["per_structure"][key]["per_k"][str(k)]
            assert Fraction(cell["delta_e_vs_reference"]["exact"]) == 0
            if k == 1:
                assert cell["relative_lift_reference"] == "NOT_APPLICABLE_K1"
            else:
                assert Fraction(cell["relative_lift_reference"]["exact"]) == 0


def test_q1_q2_q3_hold_for_all_three(synthesis: dict[str, Any]) -> None:
    q = synthesis["cross_structure_questions"]
    assert q["q1_e_beats_random_every_k_gt_1"]["holds_for_all_three"] is True
    assert q["q2_e_ge_reference_every_k_gt_1"]["holds_for_all_three"] is True
    assert q["q3_e_gt_reference_at_k_10_15_20"]["holds_for_all_three"] is True
    for key in STRUCTURES:
        assert q["q1_e_beats_random_every_k_gt_1"]["per_structure"][key] is True
        assert q["q2_e_ge_reference_every_k_gt_1"]["per_structure"][key] is True
        assert q["q3_e_gt_reference_at_k_10_15_20"]["per_structure"][key] is True


def test_q4_q6_geometry_pinned_sum_values(synthesis: dict[str, Any]) -> None:
    q = synthesis["cross_structure_questions"]
    assert q["q4_geometry_consistent_with_locked_mechanism"]["holds_for_all_three"] is True
    assert (
        q["q6_reduced_geometry_accompanies_coverage_gain"][
            "holds_for_all_three_at_every_superiority_k"
        ]
        is True
    )
    expected_sum_e = {
        "STRUCTURE_A_B649": {10: 11, 15: 43, 20: 93},
        "STRUCTURE_B_T539": {10: 11, 15: 40, 20: 83},
        "STRUCTURE_C_P638_ZONE1": {10: 22, 15: 66, 20: 132},
    }
    expected_sum_ref = {
        "STRUCTURE_A_B649": {10: 13, 15: 62, 20: 126},
        "STRUCTURE_B_T539": {10: 18, 15: 61, 20: 117},
        "STRUCTURE_C_P638_ZONE1": {10: 30, 15: 85, 20: 157},
    }
    per_cell = q["q4_geometry_consistent_with_locked_mechanism"]["per_structure_per_k"]
    for key in STRUCTURES:
        for k in SUPERIORITY_K:
            cell = per_cell[f"{key}_k{k}"]
            assert cell["max_tied"] is True
            assert cell["max_e"] == cell["max_reference"] == 1
            assert cell["sum_strictly_reduced"] is True
            assert cell["sum_e"] == expected_sum_e[key][k]
            assert cell["sum_reference"] == expected_sum_ref[key][k]
            assert cell["sum_e"] < cell["sum_reference"]


def test_structure_a_sum_pairwise_overlap_is_derived_not_native(synthesis: dict[str, Any]) -> None:
    for k in LADDER:
        geo = synthesis["per_structure"]["STRUCTURE_A_B649"]["per_k"][str(k)]["geometry_e"]
        assert (
            geo["sum_pairwise_overlap_derivation"] == "DERIVED_FROM_OVERLAP_ONE_PAIR_COUNT_MAX_LE_1"
        )
        assert geo["max_pairwise_overlap"] <= 1
        assert geo["sum_pairwise_overlap"] == geo["overlap_one_pair_count"]


def test_structures_b_and_c_sum_pairwise_overlap_is_native(synthesis: dict[str, Any]) -> None:
    for key in ("STRUCTURE_B_T539", "STRUCTURE_C_P638_ZONE1"):
        for k in LADDER:
            geo = synthesis["per_structure"][key]["per_k"][str(k)]["geometry_e"]
            assert geo["sum_pairwise_overlap_derivation"] == "NATIVE_FIELD"


def test_structure_c_relative_lift_reference_peaks_at_k15_not_k20(
    synthesis: dict[str, Any],
) -> None:
    q5 = synthesis["cross_structure_questions"]["q5_improvement_patterns"]
    monotonic = q5["structure_specific"][
        "relative_lift_reference_monotonic_nondecreasing_through_k20"
    ]
    assert monotonic["STRUCTURE_A_B649"] is True
    assert monotonic["STRUCTURE_B_T539"] is True
    assert monotonic["STRUCTURE_C_P638_ZONE1"] is False

    c_cells = synthesis["per_structure"]["STRUCTURE_C_P638_ZONE1"]["per_k"]
    lift15 = Fraction(c_cells["15"]["relative_lift_reference"]["exact"])
    lift20 = Fraction(c_cells["20"]["relative_lift_reference"]["exact"])
    assert lift15 > lift20 > 0
    assert float(lift15) == pytest.approx(0.030716, abs=1e-5)
    assert float(lift20) == pytest.approx(0.028775, abs=1e-5)


def test_sealed_frontier_only_on_structure_a_and_exceeds_only_at_k20(
    synthesis: dict[str, Any],
) -> None:
    frontier = synthesis["sealed_frontier_comparison"]
    assert frontier["applies_to"] == "STRUCTURE_A_B649"
    assert set(frontier["structures_without_a_sealed_frontier"]) == {
        "STRUCTURE_B_T539",
        "STRUCTURE_C_P638_ZONE1",
    }
    assert frontier["no_frontier_invented_for_those_structures"] is True
    assert frontier["global_optimum_status"] == "UNKNOWN"
    assert frontier["exceeds_sealed_bounded_search_reference_at_k"] == [20]
    assert frontier["e_vs_sealed_frontier_by_k"] == {
        "1": "TIES_SEALED_BOUNDED_SEARCH_REFERENCE",
        "3": "TIES_SEALED_BOUNDED_SEARCH_REFERENCE",
        "5": "TIES_SEALED_BOUNDED_SEARCH_REFERENCE",
        "10": "BELOW_SEALED_BOUNDED_SEARCH_REFERENCE",
        "15": "BELOW_SEALED_BOUNDED_SEARCH_REFERENCE",
        "20": "EXCEEDS_SEALED_BOUNDED_SEARCH_REFERENCE",
    }

    for key in ("STRUCTURE_B_T539", "STRUCTURE_C_P638_ZONE1"):
        for k in LADDER:
            assert "sealed_frontier" not in synthesis["per_structure"][key]["per_k"][str(k)]
    for k in LADDER:
        assert "sealed_frontier" in synthesis["per_structure"]["STRUCTURE_A_B649"]["per_k"][str(k)]

    # Independent direct exact-fraction re-check of the k=20 exceeds claim,
    # bypassing the generator's own comparison.
    cell20 = synthesis["per_structure"]["STRUCTURE_A_B649"]["per_k"]["20"]
    q_e = Fraction(cell20["q_e"]["exact"])
    q_c_sealed = Fraction(cell20["sealed_frontier"]["q_c_sealed"]["exact"])
    assert q_e > q_c_sealed
    assert q_e == Fraction(17379, 50666)
    assert q_c_sealed == Fraction(4788733, 13983816)


def test_reference_promotion_assessment(synthesis: dict[str, Any]) -> None:
    rec = synthesis["reference_promotion_assessment"]
    assert rec["recommendation"] == "PROMOTE_TO_NEXT_REFERENCE_CONSTRUCTOR"
    assert rec["not_a_global_optimum_claim"] is True
    assert "k>=10" in rec["recommendation_scope"]
    for factor in (
        "replication_breadth",
        "determinism",
        "geometry_mechanism_consistency",
        "runtime_practicality",
        "absence_of_parameter_rescue",
    ):
        assert factor in rec["factors"]
        assert isinstance(rec["factors"][factor], str) and rec["factors"][factor]


def test_claim_boundary_and_scope_not_executed(synthesis: dict[str, Any]) -> None:
    claim = synthesis["claim_boundary"]
    assert claim["predictive_advantage"] == "NOT_TESTED"
    assert claim["profitability"] == "NOT_TESTED"
    assert claim["prize_economic_value"] == "NOT_TESTED"
    assert claim["universal_portability"] == "NOT_CLAIMED"
    assert claim["global_optimality"] == "NOT_CLAIMED"

    scope = synthesis["scope"]
    assert scope["new_native_experiment"] == "NONE"
    assert scope["new_matrix_native_cell"] == "NONE"
    assert scope["reran_any_structure"] == "NO"
    assert scope["reran_bounded_search_reference"] == "NO"
    assert scope["changed_constructor_or_tie_breaking"] == "NO"
    assert scope["added_new_structure"] == "NO"
    assert scope["used_historical_outcomes"] == "NO"


def test_result_json_matches_generated_synthesis_and_report_contains_required_strings(
    synthesis: dict[str, Any],
) -> None:
    assert json.loads(OUTPUT_PATH.read_text(encoding="utf-8")) == synthesis

    report = REPORT_PATH.read_text(encoding="utf-8")
    for required in (
        "NEXT_GEN_CONSTRUCTOR_SUPPORTED_IN_3_NATIVE_STRUCTURES",
        "EXCEEDS_SEALED_BOUNDED_SEARCH_REFERENCE",
        "GLOBAL_OPTIMUM_STATUS: UNKNOWN",
        "PROMOTE_TO_NEXT_REFERENCE_CONSTRUCTOR",
        "RECOMMENDATION: PROMOTE_TO_NEXT_REFERENCE_CONSTRUCTOR",
        "DERIVED_FROM_OVERLAP_ONE_PAIR_COUNT_MAX_LE_1",
    ):
        assert required in report
    assert report.rstrip().endswith(
        "Do not start a new Phase-7 structure, a fourth native structure, or any\n"
        "runtime/production promotion in this task."
    )
