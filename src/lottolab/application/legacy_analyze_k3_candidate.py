"""Research port of the frozen analyze_prediction 14-ticket source.

The original source uses NumPy's unspecified indirect ordering for tied
Fourier scores. This candidate fixes that ordering to the existing legacy
introsort port. Historical agreement does not establish equivalence for all
possible histories or establish that a prediction was made before a draw.
Use the guarded entry point for prospective research.
"""

from __future__ import annotations

from collections import Counter
from itertools import pairwise

from lottolab.application.legacy_history_native_portfolios import legacy_numpy_argsort
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.adapters.biglotto_batch16 import (
    _fourier_rhythm_scores,
    _tail_balance_bet,
)
from lottolab.strategies.adapters.biglotto_selected import _p0_hot_echo_2bets

ANALYZE_K3_CANDIDATE_PROTOCOL = "legacy-analyze-14-prefix3-dedup-greedy-v2"
ANALYZE_DONOR_SHA256 = "021e1c5ede7bd1e89772d61744ea867616ee0af7f8fd441d92c3b4e0eb53d643"
ANALYZE_MINIMUM_HISTORY = 500


def _markov(history: tuple[CausalDrawRow, ...], excluded: frozenset[int]) -> tuple[int, ...]:
    recent = history[-30:]
    transitions: Counter[tuple[int, int]] = Counter(
        (previous, following)
        for before, after in pairwise(recent)
        for previous in before.numbers
        for following in after.numbers
    )
    scores = {
        number: sum(transitions.get((previous, number), 0) for previous in history[-1].numbers)
        for number in range(1, 50)
        if number not in excluded
    }
    ranked = sorted(scores, key=lambda number: -scores[number])
    return tuple(sorted(ranked[:6]))


def analyze_native_14(
    history: tuple[CausalDrawRow, ...],
) -> tuple[tuple[int, ...], ...]:
    """Produce the ordered 2 + 3 + 4 + 5 native donor positions."""
    if len(history) < ANALYZE_MINIMUM_HISTORY:
        raise ValueError("analyze K3 candidate requires at least 500 historical draws")
    scores = _fourier_rhythm_scores(history)
    order = legacy_numpy_argsort([scores[number] for number in range(1, 50)])
    fourier = tuple(sorted(index + 1 for index in order[-6:]))
    recent = history[-100:]
    frequency = Counter(number for row in recent for number in row.numbers)
    cold = tuple(
        sorted(
            sorted((n for n in range(1, 50) if n not in fourier), key=lambda n: frequency[n])[:6]
        )
    )
    tail = _tail_balance_bet(history, frozenset(fourier) | frozenset(cold))
    triple = (fourier, cold, tail)
    used = frozenset(number for ticket in triple for number in ticket)
    markov = _markov(history, used)
    frequency200 = Counter(number for row in history[-200:] for number in row.numbers)
    excluded = used | frozenset(markov)
    freq = tuple(
        sorted(
            sorted((n for n in range(1, 50) if n not in excluded), key=lambda n: -frequency200[n])[
                :6
            ]
        )
    )
    p0 = _p0_hot_echo_2bets(history)
    return (*p0, *triple, *triple, markov, *triple, markov, freq)


def deduplicate_native_prefix(
    tickets: tuple[tuple[int, ...], ...], *, k: int = 3
) -> tuple[tuple[tuple[int, ...], ...], tuple[int, ...]]:
    """Canonicalize and deduplicate the first K positions, preserving order."""
    if type(k) is not int or k < 1 or len(tickets) < k:
        raise ValueError("native prefix must contain K positions")
    unique: list[tuple[int, ...]] = []
    positions: list[int] = []
    for position, ticket in enumerate(tickets[:k], start=1):
        if (
            type(ticket) is not tuple
            or len(ticket) != 6
            or any(type(number) is not int or not 1 <= number <= 49 for number in ticket)
            or len(set(ticket)) != 6
        ):
            raise ValueError("invalid native ticket")
        canonical = tuple(sorted(ticket))
        if canonical not in unique:
            unique.append(canonical)
            positions.append(position)
    return tuple(unique), tuple(positions)


def analyze_k3_candidate(history: tuple[CausalDrawRow, ...]) -> tuple[tuple[int, ...], ...]:
    """Unique first-three prefix; use the guarded caller for Greedy completion."""
    return deduplicate_native_prefix(analyze_native_14(history))[0]


def deduplicate_all_then_k3(
    tickets: tuple[tuple[int, ...], ...],
) -> tuple[tuple[tuple[int, ...], ...], tuple[int, ...]]:
    """Exploratory alternative: deduplicate all 14 before taking three.

    This is a different policy from the historical prefix-three-plus-Greedy
    policy used by the guarded entry point.
    """
    if len(tickets) != 14:
        raise ValueError("analyze source must return 14 native positions")
    unique, positions = deduplicate_native_prefix(tickets, k=14)
    if len(unique) < 3:
        raise ValueError("fewer than three unique native tickets")
    return unique[:3], positions[:3]
