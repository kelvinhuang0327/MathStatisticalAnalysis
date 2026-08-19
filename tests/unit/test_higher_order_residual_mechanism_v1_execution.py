"""Focused verification of the native STRATEGY_MATRIX_PHASE6_HIGHER_ORDER_RESIDUAL_MECHANISM_V1
execution tool.

Runs only toy/synthetic-scale checks plus cheap reads of the already-sealed
Phase-5 result file (no B649/T539/P638 portfolio is regenerated here --
that is the separate, real-scale ~16-minute
`tools/run_higher_order_residual_mechanism_v1.py` invocation). The central
cross-validation below feeds toy portfolios through `compute_triple_cell`
and asserts it reproduces `exact_hit_multiplicity_decomposition`'s
already-approved, independently enumerated `S3` exactly -- so a correct
toy-scale match is real evidence the faster geometry-route algorithm
computes the same quantity, not just that it runs without error.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import math
from fractions import Fraction

import pytest
from tools.run_higher_order_residual_mechanism_v1 import (
    _portfolio_sha256,
    _rational,
    _shape_key,
    _validate_portfolio,
    compute_triple_cell,
    load_locked_parameters,
    load_sealed_phase5_result,
)

from lottolab.research.low_overlap_geometry_mechanism import exact_hit_multiplicity_decomposition

Ticket = tuple[int, ...]

# Identical toy fixtures to tests/unit/test_higher_order_residual_mechanism.py:
# STAR shares all pairwise numbers at one shared point (s=1); CHAIN uses three
# distinct shared numbers (s=0); both have pairwise histogram {r=1: 3 pairs}
# at BIG_LOTTO/POWER_LOTTO_zone1's own (m=3, d=6) shape, but only CHAIN's
# triple survives the Necessary Mass Bound Lemma boundary (S3=64 vs 0).
STAR_M3_D6: tuple[Ticket, ...] = ((1, 2, 3, 4, 5, 6), (1, 7, 8, 9, 10, 11), (1, 12, 13, 14, 15, 16))
CHAIN_M3_D6: tuple[Ticket, ...] = ((1, 2, 3, 4, 5, 6), (1, 7, 8, 9, 10, 11), (2, 7, 12, 13, 14, 15))
DISJOINT_M3_D6: tuple[Ticket, ...] = (
    (1, 2, 3, 4, 5, 6),
    (7, 8, 9, 10, 11, 12),
    (13, 14, 15, 16, 17, 18),
)
# DAILY_539's own shape (d=5, m=3): the identical boundary triple is instead
# forced to S3=0 (Necessary Mass Bound Lemma, design doc S5).
CHAIN_M3_D5: tuple[Ticket, ...] = ((1, 2, 3, 4, 5), (1, 6, 7, 8, 9), (2, 6, 10, 11, 12))


def _fake_sealed_arm_k(s3_multiplicity: int, max_pairwise_overlap: int = 1) -> dict[str, object]:
    return {
        "collision_moments": {"3": s3_multiplicity},
        "geometry": {"max_pairwise_overlap": max_pairwise_overlap},
    }


def test_locked_parameters_match_the_lock() -> None:
    locked = load_locked_parameters()
    assert locked["study_id"] == "STRATEGY_MATRIX_PHASE6_HIGHER_ORDER_RESIDUAL_MECHANISM_V1"
    assert locked["exposure_ladder"] == [1, 3, 5, 10, 15, 20]
    assert locked["primary_event_minimum_matches"] == 3
    assert locked["p638_zone2"] == "out_of_scope"
    assert locked["arm_c"] == "out_of_scope"
    assert locked["j4_geometry"] == "out_of_scope"
    assert locked["lotteries"]["big_lotto"]["pool_size"] == 49
    assert locked["lotteries"]["big_lotto"]["draw_size"] == 6
    assert locked["lotteries"]["daily_539"]["pool_size"] == 39
    assert locked["lotteries"]["daily_539"]["draw_size"] == 5
    assert locked["lotteries"]["power_lotto_zone1"]["pool_size"] == 38
    assert locked["lotteries"]["power_lotto_zone1"]["draw_size"] == 6


def test_load_sealed_phase5_result_reads_the_real_sealed_k3_cells() -> None:
    locked = load_locked_parameters()
    sealed_result = load_sealed_phase5_result(locked)
    big_lotto_k3 = sealed_result["per_lottery"]["BIG_LOTTO"]["per_k"]["3"]["arms"]
    assert big_lotto_k3["SIDON"]["collision_moments"]["3"] == 64
    assert big_lotto_k3["ARM_B"]["collision_moments"]["3"] == 0
    daily_539_k3 = sealed_result["per_lottery"]["DAILY_539"]["per_k"]["3"]["arms"]
    assert daily_539_k3["SIDON"]["collision_moments"]["3"] == 0
    assert daily_539_k3["ARM_B"]["collision_moments"]["3"] == 0
    power_k3 = sealed_result["per_lottery"]["POWER_LOTTO_zone1"]["per_k"]["3"]["arms"]
    assert power_k3["SIDON"]["collision_moments"]["3"] == 64
    assert power_k3["ARM_B"]["collision_moments"]["3"] == 0


def test_load_sealed_phase5_result_rejects_a_tampered_meta_hash() -> None:
    locked = load_locked_parameters()
    tampered = {
        **locked,
        "sealed_phase5": {**locked["sealed_phase5"], "preregistration_hash_sha256": "0" * 64},
    }
    with pytest.raises(ValueError, match="STOP_PHASE6_SEALED_INPUT_DRIFT"):
        load_sealed_phase5_result(tampered)


def test_portfolio_sha256_is_deterministic_and_order_sensitive() -> None:
    portfolio_a: tuple[Ticket, ...] = ((1, 2, 3), (4, 5, 6))
    portfolio_b: tuple[Ticket, ...] = ((4, 5, 6), (1, 2, 3))
    assert _portfolio_sha256(portfolio_a) == _portfolio_sha256(portfolio_a)
    assert _portfolio_sha256(portfolio_a) != _portfolio_sha256(portfolio_b)
    assert len(_portfolio_sha256(portfolio_a)) == 64


def test_validate_portfolio_rejects_duplicates_and_malformed_tickets() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        _validate_portfolio(((1, 2, 3), (1, 2, 3)), 7, 3)
    with pytest.raises(ValueError, match="distinct"):
        _validate_portfolio(((1, 1, 2),), 7, 3)
    with pytest.raises(ValueError, match="ascending"):
        _validate_portfolio(((3, 2, 1),), 7, 3)
    with pytest.raises(ValueError, match="pool_size"):
        _validate_portfolio(((1, 2, 8),), 7, 3)


def test_rational_serializes_exact_fraction() -> None:
    assert _rational(Fraction(3, 4)) == {"numerator": 3, "denominator": 4, "exact": "3/4"}


def test_shape_key_formats_canonical_shape_as_comma_joined_string() -> None:
    assert _shape_key((1, 1, 1, 0)) == "1,1,1,0"
    assert _shape_key((0, 0, 0, 0)) == "0,0,0,0"


@pytest.mark.parametrize(
    ("portfolio", "pool_size", "expected_saturated"),
    [(STAR_M3_D6, 16, 0), (CHAIN_M3_D6, 16, 1), (DISJOINT_M3_D6, 18, 0)],
    ids=["star", "chain", "disjoint"],
)
def test_compute_triple_cell_matches_multiplicity_route(
    portfolio: tuple[Ticket, ...], pool_size: int, expected_saturated: int
) -> None:
    reference = exact_hit_multiplicity_decomposition(
        portfolio, pool_size=pool_size, draw_size=6, minimum_matches=3
    )
    sealed_arm_k = _fake_sealed_arm_k(reference.collision_moments[3])
    cell = compute_triple_cell(portfolio, pool_size, 6, 3, sealed_arm_k)
    assert cell["s3_geometry"] == reference.collision_moments[3]
    assert cell["s3_geometry_identity"] is True
    assert cell["saturated_triple_count"] == expected_saturated
    assert sum(cell["ticket_triple_intersection_histogram"].values()) == math.comb(3, 3)


def test_compute_triple_cell_daily539_shape_forces_zero_and_saturated_zero() -> None:
    # DAILY_539's own (d=5, m=3) shape: the identical CHAIN-style boundary
    # triple that gives S3=64 at d=6 is forced to S3=0 at d=5 (Necessary Mass
    # Bound Lemma), and the triple never even reaches the saturated-mass
    # threshold at this draw size (required_mass = 3*3-5 = 4 > mass = 3).
    reference = exact_hit_multiplicity_decomposition(
        CHAIN_M3_D5, pool_size=12, draw_size=5, minimum_matches=3
    )
    assert reference.collision_moments[3] == 0
    sealed_arm_k = _fake_sealed_arm_k(0)
    cell = compute_triple_cell(CHAIN_M3_D5, 12, 5, 3, sealed_arm_k)
    assert cell["s3_geometry"] == 0
    assert cell["saturated_triple_count"] == 0
    assert cell["mass_bound_prediction_correct"] is True


def test_compute_triple_cell_raises_on_s3_multiplicity_mismatch() -> None:
    sealed_arm_k = _fake_sealed_arm_k(63)  # deliberately wrong: real value is 64
    with pytest.raises(ArithmeticError, match="STOP_PHASE6_S3_GEOMETRY_IDENTITY_FAILED"):
        compute_triple_cell(CHAIN_M3_D6, 16, 6, 3, sealed_arm_k)


def test_compute_triple_cell_raises_on_k_prefix_mismatch() -> None:
    # k=5 implies C(5,3)=10 triples, but a 3-ticket prefix only has C(3,3)=1.
    sealed_arm_k = _fake_sealed_arm_k(0)
    with pytest.raises(ArithmeticError, match="triple_histogram_total_identity"):
        compute_triple_cell(CHAIN_M3_D6, 16, 6, 5, sealed_arm_k)


def test_compute_triple_cell_mass_bound_prediction_correct_when_boundary_realized() -> None:
    reference = exact_hit_multiplicity_decomposition(
        CHAIN_M3_D6, pool_size=16, draw_size=6, minimum_matches=3
    )
    sealed_arm_k = _fake_sealed_arm_k(reference.collision_moments[3])
    cell = compute_triple_cell(CHAIN_M3_D6, 16, 6, 3, sealed_arm_k)
    # mass_bound_prediction_correct checks (all triples impossible) == (S3==0);
    # here S3=64!=0 and the triple is not impossible, so the biconditional holds.
    assert cell["mass_bound_prediction_correct"] is True
