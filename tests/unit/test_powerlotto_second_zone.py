"""Focused acceptance tests for the P638 POWER_LOTTO second-zone SSOT."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from lottolab.domain.draws import Draw, LotteryType
from lottolab.strategies.powerlotto_second_zone import (
    ALGORITHM_VERSION,
    CONTRACT_VERSION,
    MIN_HISTORY,
    SECOND_ZONE_PROVENANCE,
    SSOT_PROVENANCE,
    SSOT_VERSION,
    InsufficientHistoryError,
    InvalidPowerLottoTicketError,
    MalformedHistoryError,
    second_zone_predict,
    validate_power_lotto_ticket,
    validate_powerlotto_second_zone_history,
)


def _history(values: list[int]) -> list[dict[str, object]]:
    return [{"lottery_type": "POWER_LOTTO", "special": value} for value in values]


def test_contract_is_versioned_and_provenance_bearing() -> None:
    assert CONTRACT_VERSION == "p638-powerlotto-second-zone-v1"
    assert ALGORITHM_VERSION == "p47-p56-frequency-mean-reversion-v1"
    assert SECOND_ZONE_PROVENANCE["selected_authority"]
    assert SECOND_ZONE_PROVENANCE["corroborating_authority"]
    assert SECOND_ZONE_PROVENANCE["blocked_alternatives"]
    assert SECOND_ZONE_PROVENANCE["donor_archive_sha256"] == (
        "a867d33c130daa8de00363df5ee52ca926385a8ef2c17f03b161a8b6726adf43"
    )
    assert SSOT_VERSION == CONTRACT_VERSION
    assert SSOT_PROVENANCE is SECOND_ZONE_PROVENANCE


def test_min_history_is_explicit_and_short_history_fails_closed() -> None:
    with pytest.raises(InsufficientHistoryError, match=r">= 30.*got 29"):
        second_zone_predict(_history([1] * (MIN_HISTORY - 1)))


@pytest.mark.parametrize(
    "bad_history, message",
    [
        (None, "exact list or tuple"),
        ({"special": 1}, "exact list or tuple"),
        ([{"special": "1"}] * MIN_HISTORY, "special must be an integer"),
        ([{"special": 9}] * MIN_HISTORY, "special must be an integer"),
        ([{"lottery_type": "BIG_LOTTO", "special": 1}] * MIN_HISTORY, "lottery_type"),
        ([object()] * MIN_HISTORY, "must be a Draw or a special mapping"),
    ],
)
def test_malformed_history_fails_closed(bad_history: object, message: str) -> None:
    with pytest.raises(MalformedHistoryError, match=message):
        second_zone_predict(bad_history)


def test_draw_entities_are_valid_history_rows() -> None:
    history = [
        Draw(LotteryType.POWER_LOTTO, str(index + 1), (1, 2, 3, 4, 5, 6), value)
        for index, value in enumerate([1] * MIN_HISTORY)
    ]
    assert validate_powerlotto_second_zone_history(history) == (1,) * MIN_HISTORY
    assert second_zone_predict(history) == 2


def test_immutable_mapping_rows_are_accepted() -> None:
    history = tuple(
        MappingProxyType({"lottery_type": "POWER_LOTTO", "special": 4}) for _ in range(MIN_HISTORY)
    )
    assert second_zone_predict(history) == 1


def test_selected_frequency_mean_reversion_and_tie_break_are_deterministic() -> None:
    # Thirty occurrences of 1 make 1 the coldest?  The selected rule chooses
    # the count nearest 30/8 = 3.75, so every zero-count value ties and 2 wins.
    history = _history([1] * MIN_HISTORY)
    first = second_zone_predict(history)
    second = second_zone_predict(history.copy())
    assert first == second == 2


def test_recent_window_is_used_without_lookahead() -> None:
    prefix = [1] * 30
    history = _history(prefix + [2] * 70)
    assert second_zone_predict(history) == 3

    # A value after the caller's causal cutoff is not hidden or read from
    # elsewhere. It affects the result only when explicitly supplied.
    extended = history + _history([8])
    assert second_zone_predict(extended) == 8
    assert len(history) == 100
    assert validate_powerlotto_second_zone_history(history) == tuple(prefix + [2] * 70)


@pytest.mark.parametrize(
    "main_numbers, second_zone, message",
    [
        ((1, 2, 3, 4, 5), 1, "exactly 6"),
        ((1, 2, 3, 4, 5, 5), 1, "distinct"),
        ((1, 2, 3, 4, 5, 39), 1, "\\[1..38\\]"),
        ((1, 2, 3, 4, 6, 5), 1, "ascending"),
        ((1, 2, 3, 4, 5, 6), 0, "\\[1..8\\]"),
        ((1, 2, 3, 4, 5, 6), True, "exact integer"),
    ],
)
def test_full_ticket_validation_is_fail_closed(
    main_numbers: object,
    second_zone: object,
    message: str,
) -> None:
    with pytest.raises(InvalidPowerLottoTicketError, match=message):
        validate_power_lotto_ticket(main_numbers, second_zone)


def test_full_ticket_validation_allows_cross_zone_overlap_and_preserves_order() -> None:
    ticket = validate_power_lotto_ticket((1, 2, 3, 4, 5, 6), 6)
    assert ticket == ((1, 2, 3, 4, 5, 6), 6)
