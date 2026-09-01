# pyright: reportPrivateUsage=false
"""Seed-derivation exactness and process-global independence for the fixed-13 RNG seam."""

from __future__ import annotations

import hashlib
import random

import pytest

from lottolab.application.fixed13_prospective_producer import (
    RNG_DOMAIN_TAG,
    RNG_REQUIRED_STRATEGY_IDS,
    _derive_target_bound_seed_bytes,
    produce_fixed13_member,
)
from lottolab.strategies.adapters.base import CausalDrawRow

_FREEZE_SHA256 = "61beff4d35f7b0d10502fe0d1f36cc39e5a240128499061eac2599132019154b"
_TEST_DRAW_IDENTITY = "999999999"
_ALTERNATE_DRAW_IDENTITY = "999999998"


def _reference_seed_bytes(strategy_id: str, official_draw_identity: str) -> bytes:
    """Independent re-implementation of the frozen TARGET_BOUND_DETERMINISTIC_V1 formula.

    Written from the Owner packet's literal formula text, not by calling the
    production helper, so a divergence here would catch an implementation bug.
    """

    return hashlib.sha256(
        b"LOTTOLAB_FIXED13_PROSPECTIVE_RNG_V1"
        + b"\x1f"
        + b"61beff4d35f7b0d10502fe0d1f36cc39e5a240128499061eac2599132019154b"
        + b"\x1f"
        + strategy_id.encode("utf-8")
        + b"\x1f"
        + b"BIG_LOTTO"
        + b"\x1f"
        + official_draw_identity.encode("utf-8")
    ).digest()


def _synthetic_causal_240_stride8_v1() -> tuple[CausalDrawRow, ...]:
    """SYNTHETIC_CAUSAL_240_STRIDE8_V1 from the pinned reachability authority."""

    return tuple(
        CausalDrawRow(
            draw=f"SYNTHETIC-{index + 1:06d}",
            date="2020-01-01",
            numbers=tuple(sorted(((index + offset * 8) % 49) + 1 for offset in range(6))),
        )
        for index in range(240)
    )


def test_domain_tag_matches_the_frozen_contract() -> None:
    assert RNG_DOMAIN_TAG == "LOTTOLAB_FIXED13_PROSPECTIVE_RNG_V1"


def test_rng_required_set_has_exactly_the_three_wiring_gap_members() -> None:
    assert {
        "legacy_biglotto__frontend_auto_optimize_strategy__a121d28125c6",
        "legacy_biglotto__frontend_ml_features__3a4324bc2aa9",
        "legacy_biglotto__frontend_ml_genetic__3a4324bc2aa9",
    } == RNG_REQUIRED_STRATEGY_IDS


@pytest.mark.parametrize("strategy_id", sorted(RNG_REQUIRED_STRATEGY_IDS))
def test_seed_matches_an_independent_reference_implementation(strategy_id: str) -> None:
    expected = _reference_seed_bytes(strategy_id, _TEST_DRAW_IDENTITY)
    actual = _derive_target_bound_seed_bytes(
        strategy_id=strategy_id,
        official_draw_identity=_TEST_DRAW_IDENTITY,
    )
    assert actual == expected


def test_seed_bytes_round_trip_the_full_256_bit_integer_with_no_truncation() -> None:
    seed_bytes = _derive_target_bound_seed_bytes(
        strategy_id="legacy_biglotto__frontend_auto_optimize_strategy__a121d28125c6",
        official_draw_identity=_TEST_DRAW_IDENTITY,
    )
    assert len(seed_bytes) == 32
    seed_int = int.from_bytes(seed_bytes, "big")
    # A lossy truncation (e.g. to 32/64 bits) could not round-trip back to
    # the exact original 32 bytes through a fixed-width big-endian encoding.
    assert seed_int.to_bytes(32, "big") == seed_bytes


def test_same_strategy_and_draw_yield_the_same_seed() -> None:
    first = _derive_target_bound_seed_bytes(
        strategy_id="legacy_biglotto__frontend_ml_features__3a4324bc2aa9",
        official_draw_identity=_TEST_DRAW_IDENTITY,
    )
    second = _derive_target_bound_seed_bytes(
        strategy_id="legacy_biglotto__frontend_ml_features__3a4324bc2aa9",
        official_draw_identity=_TEST_DRAW_IDENTITY,
    )
    assert first == second


def test_different_strategy_yields_a_different_seed() -> None:
    a = _derive_target_bound_seed_bytes(
        strategy_id="legacy_biglotto__frontend_ml_features__3a4324bc2aa9",
        official_draw_identity=_TEST_DRAW_IDENTITY,
    )
    b = _derive_target_bound_seed_bytes(
        strategy_id="legacy_biglotto__frontend_ml_genetic__3a4324bc2aa9",
        official_draw_identity=_TEST_DRAW_IDENTITY,
    )
    assert a != b


def test_different_draw_yields_a_different_seed() -> None:
    a = _derive_target_bound_seed_bytes(
        strategy_id="legacy_biglotto__frontend_ml_features__3a4324bc2aa9",
        official_draw_identity=_TEST_DRAW_IDENTITY,
    )
    b = _derive_target_bound_seed_bytes(
        strategy_id="legacy_biglotto__frontend_ml_features__3a4324bc2aa9",
        official_draw_identity=_ALTERNATE_DRAW_IDENTITY,
    )
    assert a != b


@pytest.mark.parametrize("strategy_id", sorted(RNG_REQUIRED_STRATEGY_IDS))
def test_process_global_reseed_does_not_change_the_emitted_ticket(strategy_id: str) -> None:
    history = _synthetic_causal_240_stride8_v1()

    random.seed(20260901)
    first = produce_fixed13_member(
        strategy_id=strategy_id,
        official_draw_identity=_TEST_DRAW_IDENTITY,
        freeze_sha256_hex=_FREEZE_SHA256,
        causal_history=history,
    )
    random.seed(20260902)
    second = produce_fixed13_member(
        strategy_id=strategy_id,
        official_draw_identity=_TEST_DRAW_IDENTITY,
        freeze_sha256_hex=_FREEZE_SHA256,
        causal_history=history,
    )
    assert first.execution.legal_main_numbers == second.execution.legal_main_numbers
    assert first.per_member_rng_seed_sha256_hex == second.per_member_rng_seed_sha256_hex


@pytest.mark.parametrize("strategy_id", sorted(RNG_REQUIRED_STRATEGY_IDS))
def test_two_fresh_constructions_with_no_reseed_match(strategy_id: str) -> None:
    history = _synthetic_causal_240_stride8_v1()
    first = produce_fixed13_member(
        strategy_id=strategy_id,
        official_draw_identity=_TEST_DRAW_IDENTITY,
        freeze_sha256_hex=_FREEZE_SHA256,
        causal_history=history,
    )
    second = produce_fixed13_member(
        strategy_id=strategy_id,
        official_draw_identity=_TEST_DRAW_IDENTITY,
        freeze_sha256_hex=_FREEZE_SHA256,
        causal_history=history,
    )
    assert first.execution.legal_main_numbers == second.execution.legal_main_numbers
