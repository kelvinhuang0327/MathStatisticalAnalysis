"""Focused verification of the native STRATEGY_MATRIX_PHASE5_LOW_OVERLAP_GEOMETRY_MECHANISM_V1
execution tool.

Runs only toy/synthetic-scale checks (no B649/T539/P638 winning space is
enumerated here -- that is the separate, real-scale ~16-20 minute
`tools/run_low_overlap_geometry_mechanism_v1.py` invocation). The central
cross-validation below feeds the same toy portfolio/pool used by
`tests/unit/test_low_overlap_geometry_mechanism.py` through the new
one-pass, multi-k, multi-arm `multiplicity_prefix_counts` +
`derive_multiplicity_identities` pipeline and asserts it reproduces
`exact_hit_multiplicity_decomposition`'s already-approved, independently
enumerated result exactly -- so a correct toy-scale match is real evidence
the faster native-scale algorithm computes the same quantities, not just
that it runs without error.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import math
from fractions import Fraction

import pytest
from tools.run_low_overlap_geometry_mechanism_v1 import (
    _moment_at,
    _parse_fraction,
    _portfolio_sha256,
    _rational,
    _ticket_bitmask,
    _validate_portfolio,
    build_per_k_cell,
    derive_multiplicity_identities,
    load_locked_parameters,
    load_sealed_q,
    multiplicity_prefix_counts,
)

from lottolab.research.low_overlap_geometry_mechanism import (
    exact_hit_multiplicity_decomposition,
    portfolio_geometry,
)

Ticket = tuple[int, ...]

TOY_POOL, TOY_DRAW, TOY_MIN_MATCHES = 7, 3, 2
TOY_PORTFOLIO: tuple[Ticket, ...] = ((1, 2, 3), (1, 4, 5), (2, 4, 6))


def test_multiplicity_prefix_counts_matches_reference_decomposition_at_every_prefix() -> None:
    masks = tuple(_ticket_bitmask(t) for t in TOY_PORTFOLIO)
    ladder = (1, 2, 3)
    n_sidon, n_armb = multiplicity_prefix_counts(
        TOY_POOL, TOY_DRAW, TOY_MIN_MATCHES, ladder, masks, masks
    )
    assert n_sidon == n_armb  # both arms given the identical portfolio here

    for k in ladder:
        native = derive_multiplicity_identities(n_sidon[k], TOY_POOL, TOY_DRAW, TOY_MIN_MATCHES)
        reference = exact_hit_multiplicity_decomposition(
            TOY_PORTFOLIO[:k], TOY_POOL, TOY_DRAW, TOY_MIN_MATCHES
        )
        assert native.total_winning_combinations == reference.total_winning_combinations
        assert native.hit_event_size_per_ticket == reference.hit_event_size_per_ticket
        assert native.total_hit_incidence == reference.total_hit_incidence
        assert native.multiplicity_counts == reference.multiplicity_counts
        assert native.covered == reference.covered
        assert native.redundancy == reference.redundancy
        assert native.collision_moments == reference.collision_moments
        assert native.inclusion_exclusion_covered == reference.inclusion_exclusion_covered
        assert native.q == Fraction(reference.covered, reference.total_winning_combinations)


def test_moment_at_returns_zero_beyond_ticket_count() -> None:
    identities = derive_multiplicity_identities([35], TOY_POOL, TOY_DRAW, TOY_MIN_MATCHES)
    assert identities.collision_moments == (35,)
    assert _moment_at(identities, 0) == 35
    assert _moment_at(identities, 1) == 0
    assert _moment_at(identities, 5) == 0


def test_build_per_k_cell_is_exactly_sufficient_when_arms_are_identical() -> None:
    identities = derive_multiplicity_identities(
        [7, 18, 9, 1], TOY_POOL, TOY_DRAW, TOY_MIN_MATCHES
    )
    geometry = portfolio_geometry(TOY_PORTFOLIO, TOY_POOL, TOY_DRAW)
    cell = build_per_k_cell(
        3,
        TOY_POOL,
        TOY_DRAW,
        TOY_MIN_MATCHES,
        identities,
        identities,
        geometry,
        geometry,
        identities.q,
        identities.q,
    )
    assert cell["comparison"]["delta_covered"] == 0
    assert cell["comparison"]["mechanism_descriptor"] == "PAIRWISE_COLLISION_EXACTLY_SUFFICIENT"
    assert cell["comparison"]["pairwise_absolute_contribution_share"] == (
        "NOT_APPLICABLE_ZERO_CHANGE"
    )
    assert cell["checks"]["q_sidon_matches_sealed"] is True
    assert cell["checks"]["q_arm_b_matches_sealed"] is True


def test_build_per_k_cell_does_not_assume_pairwise_explains_a_higher_order_difference() -> None:
    # Same synthetic counterexample as test_low_overlap_geometry_mechanism.py:
    # identical pair-intersection histograms (S2 equal) but one extra
    # triple-hit winner in the second portfolio, so pairwise is exactly zero
    # yet coverage still differs by one -- entirely a higher-order effect.
    no_triple: tuple[Ticket, ...] = ((1, 2, 3), (1, 4, 5), (1, 6, 7))
    one_triple: tuple[Ticket, ...] = ((1, 2, 3), (1, 4, 5), (2, 4, 6))

    masks_sidon = tuple(_ticket_bitmask(t) for t in no_triple)
    masks_armb = tuple(_ticket_bitmask(t) for t in one_triple)
    n_sidon, n_armb = multiplicity_prefix_counts(
        TOY_POOL, TOY_DRAW, TOY_MIN_MATCHES, (3,), masks_sidon, masks_armb
    )
    identities_sidon = derive_multiplicity_identities(
        n_sidon[3], TOY_POOL, TOY_DRAW, TOY_MIN_MATCHES
    )
    identities_armb = derive_multiplicity_identities(
        n_armb[3], TOY_POOL, TOY_DRAW, TOY_MIN_MATCHES
    )
    assert identities_sidon.covered == 27
    assert identities_armb.covered == 28
    assert identities_sidon.collision_moments[2] == identities_armb.collision_moments[2] == 12

    geometry_sidon = portfolio_geometry(no_triple, TOY_POOL, TOY_DRAW)
    geometry_armb = portfolio_geometry(one_triple, TOY_POOL, TOY_DRAW)
    cell = build_per_k_cell(
        3,
        TOY_POOL,
        TOY_DRAW,
        TOY_MIN_MATCHES,
        identities_sidon,
        identities_armb,
        geometry_sidon,
        geometry_armb,
        identities_sidon.q,
        identities_armb.q,
    )
    comparison = cell["comparison"]
    assert comparison["pairwise_component"] == 0
    assert comparison["delta_covered"] == 1
    assert comparison["higher_order_residual"] == 1
    assert comparison["mechanism_descriptor"] == (
        "HIGHER_ORDER_MULTIPLICITY_PRIMARY_OR_PAIRWISE_OPPOSING"
    )


def test_build_per_k_cell_rejects_a_sealed_q_mismatch() -> None:
    identities = derive_multiplicity_identities(
        [7, 18, 9, 1], TOY_POOL, TOY_DRAW, TOY_MIN_MATCHES
    )
    geometry = portfolio_geometry(TOY_PORTFOLIO, TOY_POOL, TOY_DRAW)
    with pytest.raises(ValueError, match="q_sidon_matches_sealed"):
        build_per_k_cell(
            3,
            TOY_POOL,
            TOY_DRAW,
            TOY_MIN_MATCHES,
            identities,
            identities,
            geometry,
            geometry,
            identities.q + 1,  # deliberately wrong sealed value
            identities.q,
        )


def test_build_per_k_cell_marks_k1_fields_not_applicable() -> None:
    sidon_ticket: tuple[Ticket, ...] = ((1, 2, 3),)
    armb_ticket: tuple[Ticket, ...] = ((4, 5, 6),)
    masks_sidon = tuple(_ticket_bitmask(t) for t in sidon_ticket)
    masks_armb = tuple(_ticket_bitmask(t) for t in armb_ticket)
    n_sidon, n_armb = multiplicity_prefix_counts(
        TOY_POOL, TOY_DRAW, TOY_MIN_MATCHES, (1,), masks_sidon, masks_armb
    )
    identities_sidon = derive_multiplicity_identities(
        n_sidon[1], TOY_POOL, TOY_DRAW, TOY_MIN_MATCHES
    )
    identities_armb = derive_multiplicity_identities(
        n_armb[1], TOY_POOL, TOY_DRAW, TOY_MIN_MATCHES
    )
    # Pool symmetry: every single ticket has identical coverage/redundancy.
    assert identities_sidon.covered == identities_armb.covered
    assert identities_sidon.redundancy == identities_armb.redundancy == 0

    geometry_sidon = portfolio_geometry(sidon_ticket, TOY_POOL, TOY_DRAW)
    geometry_armb = portfolio_geometry(armb_ticket, TOY_POOL, TOY_DRAW)
    cell = build_per_k_cell(
        1,
        TOY_POOL,
        TOY_DRAW,
        TOY_MIN_MATCHES,
        identities_sidon,
        identities_armb,
        geometry_sidon,
        geometry_armb,
        identities_sidon.q,
        identities_armb.q,
    )
    comparison = cell["comparison"]
    assert comparison["mechanism_descriptor"] == "NOT_APPLICABLE_K1"
    assert comparison["pairwise_absolute_contribution_share"] == "NOT_APPLICABLE_K1"
    assert comparison["gain_over_random_ratio_to_sidon"] == "NOT_APPLICABLE_K1"


def test_validate_portfolio_rejects_duplicates_and_malformed_tickets() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        _validate_portfolio(((1, 2, 3), (1, 2, 3)), TOY_POOL, TOY_DRAW)
    with pytest.raises(ValueError, match="distinct"):
        _validate_portfolio(((1, 1, 2),), TOY_POOL, TOY_DRAW)
    with pytest.raises(ValueError, match="ascending"):
        _validate_portfolio(((3, 2, 1),), TOY_POOL, TOY_DRAW)
    with pytest.raises(ValueError, match="pool_size"):
        _validate_portfolio(((1, 2, 8),), TOY_POOL, TOY_DRAW)


def test_portfolio_sha256_is_deterministic_and_order_sensitive() -> None:
    portfolio_a: tuple[Ticket, ...] = ((1, 2, 3), (4, 5, 6))
    portfolio_b: tuple[Ticket, ...] = ((4, 5, 6), (1, 2, 3))
    assert _portfolio_sha256(portfolio_a) == _portfolio_sha256(portfolio_a)
    assert _portfolio_sha256(portfolio_a) != _portfolio_sha256(portfolio_b)
    assert len(_portfolio_sha256(portfolio_a)) == 64


def test_rational_serializes_exact_fraction() -> None:
    assert _rational(Fraction(3, 4)) == {"numerator": 3, "denominator": 4, "exact": "3/4"}


def test_parse_fraction_round_trips_sealed_exact_strings() -> None:
    assert _parse_fraction("4654/249711") == Fraction(4654, 249711)


def test_locked_parameters_match_the_lock() -> None:
    locked = load_locked_parameters()
    assert locked["study_id"] == "STRATEGY_MATRIX_PHASE5_LOW_OVERLAP_GEOMETRY_MECHANISM_V1"
    assert locked["exposure_ladder"] == [1, 3, 5, 10, 15, 20]
    assert locked["primary_event_minimum_matches"] == 3
    assert locked["lotteries"]["big_lotto"]["pool_size"] == 49
    assert locked["lotteries"]["big_lotto"]["draw_size"] == 6
    assert locked["lotteries"]["daily_539"]["pool_size"] == 39
    assert locked["lotteries"]["daily_539"]["draw_size"] == 5
    assert locked["lotteries"]["power_lotto_zone1"]["pool_size"] == 38
    assert locked["lotteries"]["power_lotto_zone1"]["draw_size"] == 6


@pytest.mark.parametrize(
    ("lottery_key", "k", "expected_sidon", "expected_armb"),
    [
        ("BIG_LOTTO", 1, Fraction(4654, 249711), Fraction(4654, 249711)),
        ("DAILY_539", 1, Fraction(1927, 191919), Fraction(1927, 191919)),
        ("POWER_LOTTO_zone1", 1, Fraction(35611, 920227), Fraction(35611, 920227)),
    ],
)
def test_load_sealed_q_reads_the_real_sealed_cells_at_k1(
    lottery_key: str, k: int, expected_sidon: Fraction, expected_armb: Fraction
) -> None:
    sidon, armb = load_sealed_q(lottery_key)
    assert sidon[k] == expected_sidon
    assert armb[k] == expected_armb


def test_derive_multiplicity_identities_matches_qualifying_ticket_count_at_k1() -> None:
    # At k=1, hit_event_size_per_ticket = K(m) = 13 for this pool/draw/threshold
    # (independently confirmed by test_low_overlap_geometry_mechanism.py's own
    # 3-ticket fixture, which reports the identical K=13 for the same shape).
    identities = derive_multiplicity_identities([22, 13], TOY_POOL, TOY_DRAW, TOY_MIN_MATCHES)
    assert identities.hit_event_size_per_ticket == 13
    assert identities.total_winning_combinations == math.comb(TOY_POOL, TOY_DRAW) == 35
    assert identities.covered == 13
    assert identities.redundancy == 0
