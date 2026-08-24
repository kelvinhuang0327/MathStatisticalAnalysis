"""Target-native port of the legacy Big Lotto Fourier30/Markov30 hedge.

The donor is ``LotteryNewMeraged/tools/biglotto_2bet_hedging.py``.  Its
default CLI mode reads an oldest-first Big Lotto history from SQLite, builds a
weighted-frequency ticket and a raw adjacent-draw transition ticket from the
latest 30 draws, then applies the default maximum-overlap-three hedge using
the latest 50 draws.  The database loader and reporting code are outside this
adapter; the source's pure ticket functions are reproduced against caller-
supplied causal history.

The donor's optional ``--diversified`` CLI flag is a separate caller-selected
variant.  This canonical identity freezes the donor's default
``--diversified``-absent behavior (``max_overlap=3``).
"""

from __future__ import annotations

from collections import Counter
from typing import ClassVar, Final

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter

_STRATEGY_ID: Final = "legacy_biglotto__biglotto_2bet_hedging__07a3aa455074"
_MIN_NUMBER: Final = 1
_MAX_NUMBER: Final = 49
_PICK_COUNT: Final = 6
_MODEL_WINDOW: Final = 30
_DIVERSIFICATION_WINDOW: Final = 50
_DEFAULT_MAX_OVERLAP: Final = 3
_MAX_NUMBERS_PER_ZONE: Final = 2


def _recent_history(
    history: tuple[CausalDrawRow, ...],
    window: int,
) -> tuple[CausalDrawRow, ...]:
    """Return the donor's trailing window without reversing causal order."""

    return history[-window:] if len(history) >= window else history


def _weighted_frequency_ticket(
    history: tuple[CausalDrawRow, ...],
) -> tuple[int, ...]:
    """Port ``bet1_fourier30`` with its source insertion-order tie behavior."""

    recent = _recent_history(history, _MODEL_WINDOW)
    weighted_frequency: dict[int, float] = {}
    size = len(recent)
    for index, row in enumerate(recent):
        weight = 1.0 + 2.0 * (index / size)
        for number in row.numbers:
            weighted_frequency[number] = weighted_frequency.get(number, 0.0) + weight

    # Stable dict sorting preserves first-seen order for equal weights; only the
    # source's final ticket sort is ascending.
    return tuple(
        sorted(
            number
            for number, _score in sorted(
                weighted_frequency.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:_PICK_COUNT]
        )
    )


def _markov_transition_ticket(
    history: tuple[CausalDrawRow, ...],
) -> tuple[int, ...]:
    """Port ``bet2_markov30``'s raw transition counts and frequency fallback."""

    recent = _recent_history(history, _MODEL_WINDOW)
    transitions: Counter[tuple[int, int]] = Counter()
    for index in range(len(recent) - 1):
        previous_numbers = set(recent[index].numbers)
        current_numbers = recent[index + 1].numbers
        for previous_number in previous_numbers:
            for current_number in current_numbers:
                transitions[(previous_number, current_number)] += 1

    if not recent:
        return tuple(range(_MIN_NUMBER, _MIN_NUMBER + _PICK_COUNT))

    last_draw = recent[-1].numbers
    scores: Counter[int] = Counter()
    for number in last_draw:
        for (previous_number, current_number), count in transitions.items():
            if previous_number == number:
                scores[current_number] += count

    result = [number for number, _score in scores.most_common(_PICK_COUNT)]

    if len(result) < _PICK_COUNT:
        all_numbers = [number for row in recent for number in row.numbers]
        frequency = Counter(all_numbers)
        for number, _count in frequency.most_common():
            if number not in result and len(result) < _PICK_COUNT:
                result.append(number)

    return tuple(sorted(result[:_PICK_COUNT]))


def _zone(number: int) -> int:
    """Port the donor's five ten-number zones for hedge filling."""

    if 1 <= number <= 10:
        return 1
    if 11 <= number <= 20:
        return 2
    if 21 <= number <= 30:
        return 3
    if 31 <= number <= 40:
        return 4
    return 5


def _diversify_tickets(
    first_ticket: tuple[int, ...],
    second_ticket: tuple[int, ...],
    history: tuple[CausalDrawRow, ...],
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Port default ``diversify_bets(..., max_overlap=3)`` exactly."""

    overlap = set(first_ticket) & set(second_ticket)
    if len(overlap) <= _DEFAULT_MAX_OVERLAP:
        return first_ticket, second_ticket

    recent = _recent_history(history, _DIVERSIFICATION_WINDOW)
    last_seen = {
        number: len(recent) for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
    }
    for index, row in enumerate(recent):
        gap = len(recent) - 1 - index
        for number in row.numbers:
            if gap < last_seen[number]:
                last_seen[number] = gap

    new_second_ticket = [
        number for number in second_ticket if number not in overlap
    ][:_DEFAULT_MAX_OVERLAP]
    cold_numbers = sorted(last_seen.items(), key=lambda item: -item[1])
    zones_used: Counter[int] = Counter(_zone(number) for number in new_second_ticket)

    for number, _gap in cold_numbers:
        if (
            number not in first_ticket
            and number not in new_second_ticket
            and len(new_second_ticket) < _PICK_COUNT
        ):
            zone = _zone(number)
            if zones_used[zone] < _MAX_NUMBERS_PER_ZONE:
                new_second_ticket.append(number)
                zones_used[zone] += 1

    for number, _gap in cold_numbers:
        if (
            number not in first_ticket
            and number not in new_second_ticket
            and len(new_second_ticket) < _PICK_COUNT
        ):
            new_second_ticket.append(number)

    return first_ticket, tuple(sorted(new_second_ticket[:_PICK_COUNT]))


class BigLotto2BetHedgingAdapter(PortfolioBetAdapter):
    """Default two-ticket Fourier30/Markov30 Big Lotto hedge."""

    strategy_id: ClassVar[str] = _STRATEGY_ID
    strategy_name: ClassVar[str] = "大樂透 Fourier30 + Markov30 對沖 2注"
    strategy_version: ClassVar[str] = "v0.1"
    min_history: ClassVar[int] = 1
    supported_lottery_types: ClassVar[tuple[LotteryType, ...]] = (LotteryType.BIG_LOTTO,)
    native_ticket_count: ClassVar[int] = 2

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        del lottery_type
        first_ticket = _weighted_frequency_ticket(history)
        second_ticket = _markov_transition_ticket(history)
        return _diversify_tickets(first_ticket, second_ticket, history)


__all__ = ["BigLotto2BetHedgingAdapter"]
