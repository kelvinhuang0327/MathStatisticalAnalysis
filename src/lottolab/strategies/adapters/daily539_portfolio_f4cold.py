"""Dependency-free DAILY_539 F4Cold native portfolio adapters.

The frozen donor algorithm ranks each number by the strongest positive
frequency in a Fourier transform of its hit indicator over the latest 500
draws, then appends a 100-draw cold-number ticket after excluding the first
four ranked tickets.  The donor used ``numpy.fft.fft`` and
``numpy.fft.fftfreq``; this module computes the same non-zero positive DFT
coefficients with the standard library only.

For a non-zero frequency, subtracting the indicator's mean changes no DFT
coefficient: the transform of a constant is zero away from frequency zero.
Therefore the implementation sums the complex exponentials at hit positions
only.  Positive ``numpy.fft.fftfreq(width, 1)`` bins are exactly
``k / width`` for ``k = 1 .. (width - 1) // 2``; the first maximum is retained
to match ``numpy.argmax``.  Number ranking is stable from ascending dictionary
insertion order, matching the donor's ``sorted(scores, key=-score)`` ties.

The donor's script is intentionally not imported or executed here.  These
adapters accept only causal ``CausalDrawRow`` tuples, perform no I/O, and
preserve the native ticket positions.  The two strategy identities expose
the first three or all five tickets from the same complete portfolio.
"""

from __future__ import annotations

from math import cos, hypot, pi, sin
from typing import cast

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)

_POOL = 39
_PICK = 5
_MIN_HISTORY = 100
_FOURIER_WINDOW = 500
_COLD_WINDOW = 100
_NATIVE_TICKET_COUNT = 5


def _validated_daily539_numbers(
    numbers: object,
    strategy_id: str,
    context: str,
    *,
    require_sorted: bool,
) -> tuple[int, ...]:
    """Validate one exact DAILY_539 ticket or history row."""

    if type(numbers) is not tuple:
        raise InvalidOutput(f"{strategy_id}: {context} expected a number tuple")
    raw_numbers = cast(tuple[object, ...], numbers)
    if len(raw_numbers) != _PICK:
        raise InvalidOutput(
            f"{strategy_id}: {context} expected {_PICK} numbers, got {len(raw_numbers)}"
        )
    if not all(type(number) is int for number in raw_numbers):
        raise InvalidOutput(f"{strategy_id}: {context} numbers must be exact built-in integers")
    validated = cast(tuple[int, ...], raw_numbers)
    if not all(1 <= number <= _POOL for number in validated):
        raise InvalidOutput(f"{strategy_id}: {context} numbers out of range [1..{_POOL}]")
    if len(set(validated)) != _PICK:
        raise InvalidOutput(f"{strategy_id}: {context} duplicate numbers")
    if require_sorted and validated != tuple(sorted(validated)):
        raise InvalidOutput(f"{strategy_id}: {context} numbers must be ascending")
    return tuple(sorted(validated))


def _validated_history(history: object, strategy_id: str) -> tuple[CausalDrawRow, ...]:
    """Validate the immutable, strictly causal history boundary."""

    if type(history) is not tuple:
        raise InvalidOutput(f"{strategy_id}: expected a history tuple")
    raw_rows = cast(tuple[object, ...], history)
    validated: list[CausalDrawRow] = []
    for index, candidate in enumerate(raw_rows):
        if type(candidate) is not CausalDrawRow:
            raise InvalidOutput(f"{strategy_id}: history row {index} is not a CausalDrawRow")
        row = candidate
        if type(row.draw) is not str or not row.draw:
            raise InvalidOutput(
                f"{strategy_id}: history row {index} draw must be a non-empty string"
            )
        if type(row.date) is not str or not row.date:
            raise InvalidOutput(
                f"{strategy_id}: history row {index} date must be a non-empty string"
            )
        validated.append(
            CausalDrawRow(
                draw=row.draw,
                date=row.date,
                numbers=_validated_daily539_numbers(
                    row.numbers,
                    strategy_id,
                    f"history row {index}",
                    require_sorted=False,
                ),
            )
        )
    return tuple(validated)


def _fourier_scores(history: tuple[CausalDrawRow, ...]) -> dict[int, float]:
    """Return donor-equivalent Fourier recurrence scores for numbers 1..39."""

    recent = history[-_FOURIER_WINDOW:] if len(history) >= _FOURIER_WINDOW else history
    width = len(recent)
    scores: dict[int, float] = {}
    max_positive_bin = (width - 1) // 2

    for number in range(1, _POOL + 1):
        hit_positions = tuple(index for index, row in enumerate(recent) if number in row.numbers)
        if len(hit_positions) < 2 or max_positive_bin < 1:
            scores[number] = 0.0
            continue

        best_magnitude = -1.0
        best_frequency = 0.0
        for frequency_bin in range(1, max_positive_bin + 1):
            # DFT convention is exp(-2*pi*i*k*j/width).  The sign of the
            # imaginary component does not affect its magnitude.
            angle_scale = 2.0 * pi * frequency_bin / width
            real = 0.0
            imaginary = 0.0
            for position in hit_positions:
                angle = angle_scale * position
                real += cos(angle)
                imaginary += sin(angle)
            magnitude = hypot(real, imaginary)
            # Strict comparison preserves the lowest frequency on an exact
            # tie, matching numpy.argmax's first-index behavior.
            if magnitude > best_magnitude:
                best_magnitude = magnitude
                best_frequency = frequency_bin / width

        if best_frequency == 0.0:
            scores[number] = 0.0
            continue
        last_hit = hit_positions[-1]
        gap = (width - 1) - last_hit
        period = 1.0 / best_frequency
        scores[number] = 1.0 / (abs(gap - period) + 1.0)

    return scores


def _predict_f4cold_all(history: tuple[CausalDrawRow, ...]) -> tuple[tuple[int, ...], ...]:
    """Generate and validate the complete five-ticket native portfolio."""

    scores = _fourier_scores(history)
    ranked = sorted(
        (number for number in range(1, _POOL + 1) if scores[number] > 0.0),
        key=lambda number: -scores[number],
    )
    if len(ranked) < 4 * _PICK:
        raise InvalidOutput(
            "F4Cold: Fourier ranking produced fewer than 20 positive-ranked numbers"
        )

    first_four = tuple(
        tuple(sorted(ranked[index * _PICK : (index + 1) * _PICK])) for index in range(4)
    )
    excluded = {number for ticket in first_four for number in ticket}

    frequencies = [0] * (_POOL + 1)
    for row in history[-_COLD_WINDOW:]:
        for number in row.numbers:
            frequencies[number] += 1
    cold_sorted = sorted(range(1, _POOL + 1), key=lambda number: frequencies[number])
    cold_candidates = [number for number in cold_sorted if number not in excluded]
    if len(cold_candidates) < _PICK:
        raise InvalidOutput("F4Cold: cold ranking produced fewer than five available numbers")
    all_bets = (*first_four, tuple(sorted(cold_candidates[:_PICK])))

    if type(all_bets) is not tuple or len(all_bets) != _NATIVE_TICKET_COUNT:
        raise InvalidOutput("F4Cold: malformed native portfolio")
    return tuple(
        _validated_daily539_numbers(
            ticket,
            "F4Cold",
            f"native ticket {index + 1}",
            require_sorted=True,
        )
        for index, ticket in enumerate(all_bets)
    )


def _validated_native_portfolio(
    raw_portfolio: object, strategy_id: str
) -> tuple[tuple[int, ...], ...]:
    """Fail closed if the producer ever returns a malformed native portfolio."""

    if type(raw_portfolio) is not tuple:
        raise InvalidOutput(f"{strategy_id}: expected a tuple of native tickets")
    raw_tickets = cast(tuple[object, ...], raw_portfolio)
    if len(raw_tickets) != _NATIVE_TICKET_COUNT:
        raise InvalidOutput(
            f"{strategy_id}: expected {_NATIVE_TICKET_COUNT} native tickets, got {len(raw_tickets)}"
        )
    return tuple(
        _validated_daily539_numbers(
            ticket,
            strategy_id,
            f"native ticket {index + 1}",
            require_sorted=True,
        )
        for index, ticket in enumerate(raw_tickets)
    )


def _get_bets(
    history: object,
    lottery_type: LotteryType,
    strategy_id: str,
    native_ticket_count: int,
) -> tuple[tuple[int, ...], ...]:
    """Apply the common fail-closed gates and return an ordered ticket slice."""

    if type(lottery_type) is not LotteryType or lottery_type is not LotteryType.DAILY_539:
        raise UnsupportedLotteryType(f"{strategy_id} does not support the requested lottery type")
    canonical_history = _validated_history(history, strategy_id)
    if len(canonical_history) < _MIN_HISTORY:
        raise InsufficientHistory(
            f"{strategy_id}: needs {_MIN_HISTORY} draws, got {len(canonical_history)}"
        )

    all_bets = _validated_native_portfolio(
        _predict_f4cold_all(canonical_history),
        strategy_id,
    )
    selected = all_bets[:native_ticket_count]
    if len(selected) != native_ticket_count:
        raise InvalidOutput(f"{strategy_id}: malformed native ticket slice")
    return tuple(selected)


class Daily539F4Cold3BetAdapter:
    """The first three tickets of the native F4Cold portfolio."""

    strategy_id = "daily539_f4cold_3bet"
    strategy_name = "今彩539 F4Cold 3注"
    strategy_version = "v0.1"
    min_history = _MIN_HISTORY
    supported_lottery_types = (LotteryType.DAILY_539,)
    native_ticket_count = 3

    def get_bets(
        self,
        history: object,
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return _get_bets(history, lottery_type, self.strategy_id, self.native_ticket_count)


class Daily539F4Cold5BetAdapter:
    """All five tickets of the native F4Cold portfolio."""

    strategy_id = "daily539_f4cold_5bet"
    strategy_name = "今彩539 F4Cold 5注"
    strategy_version = "v0.1"
    min_history = _MIN_HISTORY
    supported_lottery_types = (LotteryType.DAILY_539,)
    native_ticket_count = 5

    def get_bets(
        self,
        history: object,
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return _get_bets(history, lottery_type, self.strategy_id, self.native_ticket_count)


__all__ = ["Daily539F4Cold3BetAdapter", "Daily539F4Cold5BetAdapter"]
