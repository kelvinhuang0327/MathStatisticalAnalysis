"""Verification of the Strategy Matrix Phase 4 cross-lottery synthesis.

Independently re-derives the headline normalized numbers directly from the
three SEALED source result JSONs (not from the synthesis script's own
output), then cross-checks against `build_synthesis()` -- so a bug in the
synthesis script's arithmetic would fail this test even though the script
would happily report an internally-consistent-but-wrong number. Reads no
historical draw data and performs no new enumeration; all inputs are the
already-published `exact` fraction strings from Phases 1-3.
"""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
from tools.generate_strategy_matrix_phase4_synthesis import CELLS, LADDER, build_synthesis

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


def test_inputs_are_the_three_sealed_native_diversification_cells(
    synthesis: dict[str, Any],
) -> None:
    assert synthesis["inputs"] == {
        "BIG_LOTTO": "DIVERSIFICATION_COVERAGE_B649_V1__BIG_LOTTO",
        "DAILY_539": "DIVERSIFICATION_COVERAGE_T539_V1__DAILY_539",
        "POWER_LOTTO_zone1": "DIVERSIFICATION_COVERAGE_P638_ZONE1_V1__POWER_LOTTO_zone1",
    }
    assert synthesis["evidence_type"] == "EXACT_COMBINATORIAL"
    assert (
        synthesis["cross_lottery_synthesis_classification"]
        == "SUPPORTED_ACROSS_3_NATIVE_LOTTERY_STRUCTURES"
    )
    constructors = synthesis["constructor_invariant"]
    assert constructors["all_deterministic"] is True
    assert constructors["all_low_overlap"] is True
    assert constructors["maximum_pairwise_ticket_overlap"] == 1
    assert constructors["identical_ticket_sets_claimed"] is False


def test_relative_lift_pct_at_k20_independently_recomputed_from_raw_sources(
    synthesis: dict[str, Any], raw_sources: dict[str, dict[str, Any]]
) -> None:
    for lottery in CELLS:
        data = raw_sources[lottery]
        delta20 = Fraction(data["delta"]["3"]["20"]["exact"])
        qrand20 = Fraction(data["q_random"]["3"]["20"]["exact"])
        independent_pct = float(delta20 / qrand20) * 100
        reported_pct = synthesis["per_lottery"][lottery]["relative_lift_3_over_random_pct_at_k20"]
        assert independent_pct == pytest.approx(reported_pct, abs=1e-9)
        q_geometry20 = Fraction(data["q_sidon"]["3"]["20"]["exact"])
        cell = synthesis["per_lottery"][lottery]
        assert Fraction(cell["q_geometry_3"]["20"]["exact"]) == q_geometry20
        assert Fraction(cell["coverage_ratio_3_over_random"]["20"]["exact"]) == (
            q_geometry20 / qrand20
        )


def test_relative_lift_pct_at_k20_pinned_values(synthesis: dict[str, Any]) -> None:
    # Pins the actual normalized numbers so a future silent change to any
    # of the three sealed source files is caught here, not just downstream
    # in prose. B649's D_3(20) raw value (+0.01329487) is more than T539's
    # (+0.00929225) -- but that ordering flips once each delta is expressed
    # relative to its own lottery's random baseline.
    lift = {
        lottery: synthesis["per_lottery"][lottery]["relative_lift_3_over_random_pct_at_k20"]
        for lottery in CELLS
    }
    assert lift["BIG_LOTTO"] == pytest.approx(4.2397, abs=1e-3)
    assert lift["DAILY_539"] == pytest.approx(5.0842, abs=1e-3)
    assert lift["POWER_LOTTO_zone1"] == pytest.approx(10.9242, abs=1e-3)
    assert lift["DAILY_539"] > lift["BIG_LOTTO"]
    assert lift["POWER_LOTTO_zone1"] > lift["DAILY_539"] > lift["BIG_LOTTO"]
    ratio = {
        lottery: synthesis["per_lottery"][lottery]["coverage_ratio_3_over_random_at_k20"]
        for lottery in CELLS
    }
    assert ratio["BIG_LOTTO"] == pytest.approx(1.042397, abs=1e-6)
    assert ratio["DAILY_539"] == pytest.approx(1.050842, abs=1e-6)
    assert ratio["POWER_LOTTO_zone1"] == pytest.approx(1.109242, abs=1e-6)


def test_ranking_flips_between_raw_delta_and_relative_lift(synthesis: dict[str, Any]) -> None:
    assert synthesis["raw_d3_k20_ranking_descending"] == [
        "POWER_LOTTO_zone1",
        "BIG_LOTTO",
        "DAILY_539",
    ]
    assert synthesis["relative_lift_k20_ranking_descending"] == [
        "POWER_LOTTO_zone1",
        "DAILY_539",
        "BIG_LOTTO",
    ]
    assert synthesis["ranking_flips_under_normalization"] is True


def test_power_lotto_zone1_ranks_first_under_every_lens_tried(synthesis: dict[str, Any]) -> None:
    # The one ranking element that does NOT flip across raw delta,
    # relative lift, or the M4+ secondary threshold: P638 Zone-1 is first
    # in all three. Only the B649-vs-T539 ordering is lens-dependent.
    assert synthesis["raw_d3_k20_ranking_descending"][0] == "POWER_LOTTO_zone1"
    assert synthesis["relative_lift_k20_ranking_descending"][0] == "POWER_LOTTO_zone1"
    m4_lift = {
        lottery: synthesis["per_lottery"][lottery]["relative_lift_4_over_random_pct_at_k20"]
        for lottery in CELLS
    }
    assert max(m4_lift, key=lambda lot: m4_lift[lot]) == "POWER_LOTTO_zone1"


def test_m3_and_m4_signs_agree_across_all_three_lotteries(synthesis: dict[str, Any]) -> None:
    assert synthesis["m3_and_m4_signs_agree_at_k20"] is True
    assert synthesis["direction_consistency"]["positive_for_every_lottery_and_tested_k"] is True
    for lottery in CELLS:
        cell = synthesis["per_lottery"][lottery]
        assert cell["delta_3"]["20"]["float"] > 0
        assert cell["delta_4_at_k20"]["float"] > 0
        assert all(cell["delta_3"][str(k)]["float"] > 0 for k in LADDER if k > 1)


def test_delta_identity_holds_exactly_for_every_ladder_rung(
    synthesis: dict[str, Any], raw_sources: dict[str, dict[str, Any]]
) -> None:
    for lottery, data in raw_sources.items():
        for k in LADDER:
            delta = Fraction(data["delta"]["3"][str(k)]["exact"])
            q_sidon = Fraction(data["q_sidon"]["3"][str(k)]["exact"])
            q_random = Fraction(data["q_random"]["3"][str(k)]["exact"])
            assert q_sidon - q_random == delta, (lottery, k)
            cell = synthesis["per_lottery"][lottery]
            assert Fraction(cell["q_geometry_3"][str(k)]["exact"]) == q_sidon
            assert Fraction(cell["coverage_ratio_3_over_random"][str(k)]["exact"]) == (
                q_sidon / q_random
            )
            assert Fraction(cell["relative_lift_3_over_random"][str(k)]["exact"]) == (
                delta / q_random
            )


def test_exposure_fraction_k20_over_n_differs_across_lotteries(synthesis: dict[str, Any]) -> None:
    # Raw k=20 does not represent the same exposure fraction in each
    # lottery's own cyclic shift space (49 vs 39 vs 38 total shifts) --
    # recorded explicitly so raw-k comparisons are never read as
    # exposure-matched without this caveat available alongside them.
    frac = {
        lottery: synthesis["per_lottery"][lottery]["exposure_fraction_k_over_n"]["20"]["float"]
        for lottery in CELLS
    }
    assert frac["BIG_LOTTO"] == pytest.approx(20 / 49)
    assert frac["DAILY_539"] == pytest.approx(20 / 39)
    assert frac["POWER_LOTTO_zone1"] == pytest.approx(20 / 38)
    assert frac["BIG_LOTTO"] < frac["DAILY_539"] < frac["POWER_LOTTO_zone1"]
    shape = synthesis["exposure_shape_consistency"]
    assert shape["marginal_geometry_delta_strictly_increasing_for_every_lottery"] is True
    assert shape["classification"] == "WIDENS_IN_ALL_THREE_WITH_LOTTERY_SPECIFIC_GROWTH_MAGNITUDE"
    assert synthesis["zero_crossing_consistency"]["all_none"] is True
    for lottery in CELLS:
        cell = synthesis["per_lottery"][lottery]
        assert cell["marginal_geometry_delta"] == cell["marginal_rate"]
        assert cell["geometry_advantage_zero_crossing"] is None


def test_scope_makes_no_predictive_or_economic_claim(synthesis: dict[str, Any]) -> None:
    scope = synthesis["scope"]
    assert scope["predictive_advantage"] == "NOT_TESTED"
    assert scope["prize_value_advantage"] == "NOT_TESTED"
    assert scope["economic_optimality"] == "NOT_TESTED"
    assert scope["p638_zone2_touched"] == "NO"
    assert scope["new_enumeration_performed"] == "NO"
    assert scope["historical_draw_data_read"] == "NO"
    priority = synthesis["phase5_research_priority"]
    assert priority["mechanism_family"] == "DIVERSIFICATION"
    assert priority["priority"] == "HIGH_PRIORITY_FOR_GENERATION_2"
    assert priority["candidate_family"] == "DIVERSIFICATION_CONSTRUCTOR_FRONTIER"

    result_path = RESULTS_DIR / "strategy-matrix-phase4-cross-lottery-synthesis-v1-result.json"
    assert json.loads(result_path.read_text(encoding="utf-8")) == synthesis

    report_path = RESULTS_DIR / "strategy-matrix-phase4-cross-lottery-synthesis-v1-report.md"
    report = report_path.read_text(encoding="utf-8")
    for required in (
        "SUPPORTED_ACROSS_3_NATIVE_LOTTERY_STRUCTURES",
        "HIGH_PRIORITY_FOR_GENERATION_2",
        "DIVERSIFICATION_CONSTRUCTOR_FRONTIER",
        "COVERAGE_RATIO",
        "RELATIVE_COVERAGE_LIFT",
        "Q_geometry",
    ):
        assert required in report
    assert report.rstrip().endswith("Do not start Phase 5 in this task.")
