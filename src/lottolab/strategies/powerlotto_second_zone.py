"""P638 POWER_LOTTO second-zone single source of truth.

This module is deliberately self-contained.  It contains the one second-zone
rule that Wave 1 strategies may use and does not import a donor predictor,
perform persistence, inspect process state, or consult the clock.

Authority decision
------------------
The selected algorithm is the deterministic frequency mean-reversion rule
shared by the statically reviewed ``_special_predict`` implementations in
the P47 and P56 donor adapters.  For the most recent 100 causal draws, the
number whose observed frequency is closest to the uniform expectation wins;
ties are resolved by the lower number.  P47 is the selected algorithmic
authority and P56 is corroborating evidence because the implementations are
identical.

The P335A donor ``power_lotto_second_zone.py`` is the contract-level
corroborating source for forward-only use, a 1..8 result, and the 30-draw
minimum.  Its primary fused predictor is intentionally blocked here: it has
an unpinned transitive ``special_predictor`` dependency that is outside this
card's read/write scope.  The blocked alternative is recorded below rather
than silently mixed with the selected rule.

Callers must pass only draws strictly before the target.  The API accepts the
small ``{"special": int}`` donor-shaped mapping used by the frozen adapters
and the repository's immutable :class:`~lottolab.domain.draws.Draw` entity.
There is no target argument, future-row lookup, database access, filesystem
access, environment access, network access, or clock access in this module;
the supplied history is the complete causal input.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final, cast

from lottolab.domain.draws import Draw, LotteryType

SPECIAL_MIN: Final = 1
SPECIAL_MAX: Final = 8
SPECIAL_POOL_SIZE: Final = SPECIAL_MAX - SPECIAL_MIN + 1
SECOND_ZONE_WINDOW: Final = 100
MIN_HISTORY: Final = 30

CONTRACT_VERSION: Final = "p638-powerlotto-second-zone-v1"
ALGORITHM_VERSION: Final = "p47-p56-frequency-mean-reversion-v1"
DONOR_ARCHIVE_SHA256: Final = "a867d33c130daa8de00363df5ee52ca926385a8ef2c17f03b161a8b6726adf43"
SELECTED_DONOR_AUTHORITY: Final = (
    "LotteryNewMeraged/lottery_api/models/p47_wave4_powerlotto_adapters.py::_special_predict"
)
CORROBORATING_DONOR_AUTHORITY: Final = (
    "LotteryNewMeraged/lottery_api/models/p56_wave5_powerlotto_adapters.py::_special_predict"
)

# This immutable metadata is emitted by the later replay runner as provenance.
# Keep the alternative explicit: changing the model requires a new contract
# version and an owner-reviewed provenance decision.
SECOND_ZONE_PROVENANCE: Final = MappingProxyType(
    {
        "contract_version": CONTRACT_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "lottery_type": LotteryType.POWER_LOTTO.value,
        "selected_authority": SELECTED_DONOR_AUTHORITY,
        "corroborating_authority": CORROBORATING_DONOR_AUTHORITY,
        "donor_archive_sha256": DONOR_ARCHIVE_SHA256,
        "selected_rule": (
            "last 100 causal second-zone values; choose the value whose count "
            "is closest to len(window)/8; tie-break by ascending value"
        ),
        "blocked_alternatives": (
            "LotteryNewMeraged/lottery_api/models/power_lotto_second_zone.py::"
            "second_zone_predict fused PowerLottoSpecialPredictor path; blocked "
            "because its transitive special_predictor implementation is not "
            "pinned within this card's permitted donor scope",
            "P47/P56 no-history fallbacks; blocked because short or malformed "
            "history must fail closed under the P638 contract",
        ),
    }
)

# Stable integration names for adapters and replay metadata.  The descriptive
# aliases above remain public so provenance readers can use either vocabulary
# without creating a second contract object.
SSOT_VERSION: Final = CONTRACT_VERSION
SSOT_PROVENANCE: Final = SECOND_ZONE_PROVENANCE


class PowerLottoSecondZoneError(ValueError):
    """Base class for fail-closed second-zone contract violations."""


class MalformedHistoryError(PowerLottoSecondZoneError):
    """Raised when a history container or row is not a valid POWER_LOTTO row."""


class InsufficientHistoryError(PowerLottoSecondZoneError):
    """Raised when valid causal history is shorter than :data:`MIN_HISTORY`."""


class InvalidPowerLottoTicketError(PowerLottoSecondZoneError):
    """Raised when a complete POWER_LOTTO ticket is not legal."""


_MISSING: Final = object()


def _history_specials(history: object) -> tuple[int, ...]:
    """Validate history shape and return only its causal second-zone values."""

    if type(history) not in (list, tuple):
        raise MalformedHistoryError("history must be an exact list or tuple of POWER_LOTTO rows")

    rows = cast(list[object] | tuple[object, ...], history)
    specials: list[int] = []
    for index, row in enumerate(rows):
        if type(row) is Draw:
            if row.lottery_type is not LotteryType.POWER_LOTTO:
                raise MalformedHistoryError(
                    f"history row {index} must have lottery_type POWER_LOTTO"
                )
            candidate: object = row.special
        elif isinstance(row, Mapping):
            raw_row = cast(Mapping[object, object], row)
            lottery_type = raw_row.get("lottery_type", LotteryType.POWER_LOTTO)
            if lottery_type is not LotteryType.POWER_LOTTO and not (
                type(lottery_type) is str and lottery_type == LotteryType.POWER_LOTTO.value
            ):
                raise MalformedHistoryError(
                    f"history row {index} must have lottery_type POWER_LOTTO"
                )
            candidate = raw_row.get("special", _MISSING)
        else:
            raise MalformedHistoryError(f"history row {index} must be a Draw or a special mapping")

        if type(candidate) is not int or not SPECIAL_MIN <= candidate <= SPECIAL_MAX:
            raise MalformedHistoryError(
                f"history row {index} special must be an integer in [{SPECIAL_MIN}..{SPECIAL_MAX}]"
            )
        specials.append(candidate)

    return tuple(specials)


def validate_powerlotto_second_zone_history(history: object) -> tuple[int, ...]:
    """Return validated causal second-zone values without predicting.

    This helper intentionally does not sort, truncate, or infer rows.  The
    caller owns the causal ordering; :func:`second_zone_predict` only applies
    the fixed recent-window rule after this validation succeeds.
    """

    return _history_specials(history)


def second_zone_predict(history: object) -> int:
    """Predict one POWER_LOTTO second-zone value from strictly prior history.

    The function is deterministic for identical history and returns an exact
    built-in integer in ``1..8``.  It raises :class:`MalformedHistoryError`
    before any prediction for malformed rows and
    :class:`InsufficientHistoryError` for valid history shorter than
    :data:`MIN_HISTORY`.
    """

    specials = _history_specials(history)
    if len(specials) < MIN_HISTORY:
        raise InsufficientHistoryError(
            f"second_zone_predict needs >= {MIN_HISTORY} causal draws, got {len(specials)}"
        )

    recent = specials[-SECOND_ZONE_WINDOW:]
    expected = len(recent) / SPECIAL_POOL_SIZE
    counts = [0] * (SPECIAL_MAX + 1)
    for special in recent:
        counts[special] += 1

    # The second key is the explicit lower-number tie-break from P47/P56.
    return min(
        range(SPECIAL_MIN, SPECIAL_MAX + 1),
        key=lambda value: (abs(counts[value] - expected), value),
    )


def validate_power_lotto_ticket(
    main_numbers: object,
    second_zone: object,
) -> tuple[tuple[int, ...], int]:
    """Validate and return a complete legal POWER_LOTTO ticket.

    The first zone must contain six distinct exact integers in ascending
    ``1..38`` order.  The second zone must be one exact integer in ``1..8``.
    Cross-zone overlap is allowed by POWER_LOTTO mechanics.  This helper
    validates; it never sorts, deduplicates, clamps, or fills missing values.
    """

    if type(main_numbers) not in (list, tuple):
        raise InvalidPowerLottoTicketError(
            "main_numbers must be an exact list or tuple of six integers"
        )
    raw_main = tuple(cast(list[object] | tuple[object, ...], main_numbers))
    if len(raw_main) != 6:
        raise InvalidPowerLottoTicketError("main_numbers must contain exactly 6 values")
    if any(type(number) is not int for number in raw_main):
        raise InvalidPowerLottoTicketError("main_numbers must contain exact integers")
    validated_main = cast(tuple[int, ...], raw_main)
    if any(not 1 <= number <= 38 for number in validated_main):
        raise InvalidPowerLottoTicketError("main_numbers must be in [1..38]")
    if len(set(validated_main)) != 6:
        raise InvalidPowerLottoTicketError("main_numbers must be distinct")
    if validated_main != tuple(sorted(validated_main)):
        raise InvalidPowerLottoTicketError("main_numbers must be ascending")
    if type(second_zone) is not int or not SPECIAL_MIN <= second_zone <= SPECIAL_MAX:
        raise InvalidPowerLottoTicketError("second_zone must be an exact integer in [1..8]")
    return validated_main, second_zone


__all__ = [
    "ALGORITHM_VERSION",
    "CONTRACT_VERSION",
    "CORROBORATING_DONOR_AUTHORITY",
    "DONOR_ARCHIVE_SHA256",
    "MIN_HISTORY",
    "SECOND_ZONE_PROVENANCE",
    "SECOND_ZONE_WINDOW",
    "SELECTED_DONOR_AUTHORITY",
    "SPECIAL_MAX",
    "SPECIAL_MIN",
    "SSOT_PROVENANCE",
    "SSOT_VERSION",
    "InsufficientHistoryError",
    "InvalidPowerLottoTicketError",
    "MalformedHistoryError",
    "PowerLottoSecondZoneError",
    "second_zone_predict",
    "validate_power_lotto_ticket",
    "validate_powerlotto_second_zone_history",
]
