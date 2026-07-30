"""Frozen Core-Satellite and Zone Split native portfolio parity tests."""

from __future__ import annotations

import pytest

from lottolab.application.legacy_random_native_portfolios import (
    CORE_SATELLITE_METHOD_ID,
    DEFAULT_USER_SEED,
    RANDOM_NATIVE_PROTOCOL,
    ZONE_SPLIT_METHOD_ID,
    LegacyRandomNativeError,
    LegacyRandomNativeRequest,
    generate_legacy_random_native_portfolio,
)


@pytest.mark.parametrize(
    ("method_id", "expected"),
    [
        (
            CORE_SATELLITE_METHOD_ID,
            (
                (5, 7, 9, 32, 40, 48),
                (20, 24, 26, 32, 34, 40),
                (13, 17, 18, 31, 32, 40),
            ),
        ),
        (
            ZONE_SPLIT_METHOD_ID,
            (
                (2, 3, 6, 10, 11, 15),
                (16, 18, 20, 21, 26, 33),
                (32, 38, 42, 45, 48, 49),
            ),
        ),
    ],
)
def test_native_portfolio_has_frozen_three_ticket_order(
    method_id: str,
    expected: tuple[tuple[int, int, int, int, int, int], ...],
) -> None:
    result = generate_legacy_random_native_portfolio(
        LegacyRandomNativeRequest(
            legacy_method_id=method_id,
            target_draw_number="115000056",
        )
    )

    assert result.tickets == expected
    assert result.metadata.protocol == RANDOM_NATIVE_PROTOCOL
    assert result.metadata.native_ticket_count == 3
    assert result.metadata.native_ticket_order == "FROZEN_FACTORY_BET_ORDER"
    assert result.metadata.candidate_k is None
    assert result.metadata.combination_count is None
    assert DEFAULT_USER_SEED in result.metadata.seed_material


def test_same_request_is_deterministic_and_target_identity_changes_seed() -> None:
    request = LegacyRandomNativeRequest(
        legacy_method_id=ZONE_SPLIT_METHOD_ID,
        target_draw_number="115000056",
        user_seed="owner-seed",
    )

    first = generate_legacy_random_native_portfolio(request)
    second = generate_legacy_random_native_portfolio(request)
    changed = generate_legacy_random_native_portfolio(
        LegacyRandomNativeRequest(
            legacy_method_id=ZONE_SPLIT_METHOD_ID,
            target_draw_number="115000057",
            user_seed="owner-seed",
        )
    )

    assert first == second
    assert first.metadata.seed_digest != changed.metadata.seed_digest
    assert first.tickets != changed.tickets


@pytest.mark.parametrize(
    "native_request",
    [
        LegacyRandomNativeRequest("unknown.py", "1"),
        LegacyRandomNativeRequest(CORE_SATELLITE_METHOD_ID, ""),
        LegacyRandomNativeRequest(CORE_SATELLITE_METHOD_ID, "1", replicate_id=-1),
    ],
)
def test_invalid_identity_is_closed(
    native_request: LegacyRandomNativeRequest,
) -> None:
    with pytest.raises(LegacyRandomNativeError):
        generate_legacy_random_native_portfolio(native_request)
