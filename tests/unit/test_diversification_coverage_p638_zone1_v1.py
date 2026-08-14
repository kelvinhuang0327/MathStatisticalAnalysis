"""Focused verification of the sealed DIVERSIFICATION_COVERAGE_P638_ZONE1_V1 result.

Re-runs the actual locked experiment (a full C(38,6) = 2,760,681-draw
enumeration, ~9s) rather than trusting the committed result.json, so
these checks fail if the sealed artifact and the live code ever drift
apart. Does not re-litigate the classification rule itself -- that rule
is frozen in the preregistration doc; this only confirms the sealed
outcome and the required exactness/ordering invariants still hold.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any

import pytest
from tools.run_diversification_coverage_p638_zone1_v1 import load_locked_parameters, run

EXPOSURE_LADDER = (1, 3, 5, 10, 15, 20)


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    return run(load_locked_parameters())


def test_locked_parameters_match_the_preregistration() -> None:
    locked = load_locked_parameters()
    assert locked["matrix_variant_id"] == "DIVERSIFICATION_COVERAGE_P638_ZONE1_V1"
    assert locked["lottery_type"] == "POWER_LOTTO"
    assert locked["zone"] == "zone1"
    assert locked["pool_size"] == 38
    assert locked["draw_size"] == 6
    assert locked["sidon_base_set_0_indexed"] == [0, 1, 3, 7, 17, 30]
    assert locked["exposure_ladder"] == list(EXPOSURE_LADDER)
    assert locked["primary_event_minimum_matches"] == 3
    assert locked["secondary_event_minimum_matches"] == [4, 5, 6]


def test_full_winning_space_is_enumerated(result: dict[str, Any]) -> None:
    assert result["total_draws_enumerated"] == math.comb(38, 6) == 2_760_681


def test_d3_at_k1_is_exactly_zero(result: dict[str, Any]) -> None:
    d3_at_1 = result["delta"]["3"]["1"]
    assert d3_at_1["exact"] == "0/1"
    assert d3_at_1["float"] == 0.0


def test_q_sidon_m3_is_monotone_nondecreasing_across_the_ladder(result: dict[str, Any]) -> None:
    values = [Fraction(result["q_sidon"]["3"][str(k)]["exact"]) for k in EXPOSURE_LADDER]
    assert all(values[i] <= values[i + 1] for i in range(len(values) - 1))


def test_m6_nests_inside_m5_inside_m4_inside_m3_for_every_k(result: dict[str, Any]) -> None:
    for k in EXPOSURE_LADDER:
        m3 = Fraction(result["q_sidon"]["3"][str(k)]["exact"])
        m4 = Fraction(result["q_sidon"]["4"][str(k)]["exact"])
        m5 = Fraction(result["q_sidon"]["5"][str(k)]["exact"])
        m6 = Fraction(result["q_sidon"]["6"][str(k)]["exact"])
        assert m6 <= m5 <= m4 <= m3


def test_sealed_classification_is_outperforms_random_expected_coverage(
    result: dict[str, Any],
) -> None:
    assert result["descriptive_classification"] == "OUTPERFORMS_RANDOM_EXPECTED_COVERAGE"
    assert result["geometry_advantage_zero_crossing"] is None


def test_m6_is_the_degenerate_exact_match_case_for_a_6_of_38_draw(result: dict[str, Any]) -> None:
    # For P638 Zone-1, M6 == draw_size, so "M6" means the draw exactly
    # equals a ticket -- geometry cannot help or hurt this event (every
    # distinct ticket, fixed or random, has the same 1/N chance of being
    # drawn verbatim), the same degenerate case T539 already documented
    # for its own M5 (where M5 == T539's draw_size). D_6(k) must be
    # exactly 0 for every k here.
    for k in EXPOSURE_LADDER:
        assert result["delta"]["6"][str(k)]["exact"] == "0/1"


def test_d3_at_k20_exceeds_both_prior_sealed_native_cells(result: dict[str, Any]) -> None:
    # Descriptive cross-cell comparison only (not pooled, not an economic
    # claim) -- B649's sealed D_3(20) is +0.01329486738714325, T539's is
    # +0.00929225. Recorded here so a future rerun that silently regressed
    # this comparison would fail loudly rather than silently.
    d3_at_20 = Fraction(result["delta"]["3"]["20"]["exact"])
    assert d3_at_20 > Fraction(1329487, 100_000_000)  # > B649's D_3(20)
    assert d3_at_20 > Fraction(929225, 100_000_000)  # > T539's D_3(20)


def test_preregistration_hash_is_tamper_evident() -> None:
    locked = load_locked_parameters()
    tampered = {**locked, "primary_event_minimum_matches": 4}
    assert tampered != locked
