"""Target-native port of the frozen BIG_LOTTO Quad Strike donor.

The donor is ``tools/predict_biglotto_quad_strike.py`` at legacy commit
``49a25effa62fc24f40789c16be6f11bdfb41a4a9`` (recorded blob
``c3416cb8ae787276a020ab4eeb2f7402612381ae``, SHA-256
``e202e664208faf3f998f93f4992a8e2595fe17f2179345bba8d4587deff48a36``).

The donor emits four native positional tickets of six numbers each, computed
in a fixed order with cumulative exclusion so the portfolio always covers
twenty-four distinct numbers:

1. Fourier Rhythm over the trailing 500 draws.
2. Cold Numbers over the trailing 100 draws, excluding ticket 1.
3. Tail Balance over the trailing 100 draws, excluding tickets 1-2.
4. Gray Zone Gap over the trailing 50 draws, excluding tickets 1-3.

Frozen donor semantics retained exactly: every history window, the Fourier
score formula, candidate exclusion sequencing, each fallback branch, and the
four-by-six ticket cardinality. Ticket 4 deliberately keeps the donor's
asymmetry between its fifty-draw frequency window and its full-history gap
scan. The donor draws no random values anywhere; its module-level
``numpy.random.seed(42)`` is dead code, is not migrated, and no RNG
abstraction replaces it.

Ticket 1 preserves the donor's NumPy 1.26.2 default float ``argsort``
ordering, including its unstable equal-score permutation. The small pure
Python index sorter below ports that pinned median-of-three quicksort,
insertion-sort cutoff, and heapsort fallback without adding NumPy to the
target runtime.

Numerics are stdlib-only. The donor's SciPy transform is replaced by the
existing dependency-free ``bluestein_dft``, which produces the same frequency
bins for an arbitrary window length.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import cast

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InvalidOutput,
    PortfolioBetAdapter,
)
from lottolab.strategies.adapters.powerlotto_wave1 import bluestein_dft

_STRATEGY_ID = "legacy_biglotto__predict_biglotto_quad_strike__e202e664208f"
_MIN_NUMBER = 1
_MAX_NUMBER = 49
_PICK_COUNT = 6
_NATIVE_TICKET_COUNT = 4
_TICKET1_WINDOW = 500
_TICKET2_WINDOW = 100
_TICKET3_WINDOW = 100
_TICKET4_WINDOW = 50
_TICKET4_FALLBACK_WINDOW = 100
_GRAY_ZONE_DEVIATION = 1.5
_TAIL_MODULUS = 10
_TAIL_ROUND_LIMIT = 10
_MIN_HISTORY = 1


def _all_numbers() -> range:
    """Return the donor's fixed 1..49 candidate domain in ascending order."""

    return range(_MIN_NUMBER, _MAX_NUMBER + 1)


def _trailing(
    history: tuple[CausalDrawRow, ...],
    window: int,
) -> tuple[CausalDrawRow, ...]:
    """Return the donor's trailing slice, which shortens rather than pads."""

    return history[-window:] if len(history) >= window else history


def _frequencies(rows: Sequence[CausalDrawRow]) -> Counter[int]:
    """Count appearances exactly as the donor's ``Counter`` over a window does."""

    return Counter(number for row in rows for number in row.numbers)


def _legacy_numpy_argsort(scores: tuple[float, ...]) -> tuple[int, ...]:
    """Reproduce NumPy 1.26.2's default float ``argsort`` index order.

    The donor calls ``np.argsort`` without a ``kind`` or tie-break key. Its
    pinned runtime therefore exposes the legacy introsort implementation:
    median-of-three partitioning, insertion sort for partitions of at most
    sixteen elements, and heapsort after the introsort depth limit. Equality
    is intentionally never resolved by value or original index.
    """

    indices = list(range(len(scores)))
    if len(indices) < 2:
        return tuple(indices)

    def heapsort(start: int, end: int) -> None:
        heap = [0, *indices[start : end + 1]]
        size = len(heap) - 1

        for root in range(size >> 1, 0, -1):
            saved = heap[root]
            child = root << 1
            while child <= size:
                if child < size and scores[heap[child]] < scores[heap[child + 1]]:
                    child += 1
                if scores[saved] < scores[heap[child]]:
                    heap[root] = heap[child]
                    root = child
                    child <<= 1
                else:
                    break
            heap[root] = saved

        remaining = size
        while remaining > 1:
            saved = heap[remaining]
            heap[remaining] = heap[1]
            remaining -= 1
            root = 1
            child = root << 1
            while child <= remaining:
                if (
                    child < remaining
                    and scores[heap[child]] < scores[heap[child + 1]]
                ):
                    child += 1
                if scores[saved] < scores[heap[child]]:
                    heap[root] = heap[child]
                    root = child
                    child <<= 1
                else:
                    break
            heap[root] = saved

        indices[start : end + 1] = heap[1:]

    stack: list[tuple[int, int, int]] = []
    lower = 0
    upper = len(indices) - 1
    depth = (len(indices).bit_length() - 1) * 2

    while True:
        if depth < 0:
            heapsort(lower, upper)
            if not stack:
                break
            lower, upper, depth = stack.pop()
            continue

        while upper - lower > 15:
            middle = lower + ((upper - lower) >> 1)
            if scores[indices[middle]] < scores[indices[lower]]:
                indices[middle], indices[lower] = indices[lower], indices[middle]
            if scores[indices[upper]] < scores[indices[middle]]:
                indices[upper], indices[middle] = indices[middle], indices[upper]
            if scores[indices[middle]] < scores[indices[lower]]:
                indices[middle], indices[lower] = indices[lower], indices[middle]

            pivot = scores[indices[middle]]
            left = lower
            right = upper - 1
            indices[middle], indices[right] = indices[right], indices[middle]
            while True:
                left += 1
                while scores[indices[left]] < pivot:
                    left += 1
                right -= 1
                while pivot < scores[indices[right]]:
                    right -= 1
                if left >= right:
                    break
                indices[left], indices[right] = indices[right], indices[left]

            indices[left], indices[upper - 1] = indices[upper - 1], indices[left]
            next_depth = depth - 1
            if left - lower < upper - left:
                stack.append((left + 1, upper, next_depth))
                upper = left - 1
            else:
                stack.append((lower, left - 1, next_depth))
                lower = left + 1
            depth = next_depth

        for position in range(lower + 1, upper + 1):
            saved_index = indices[position]
            saved_score = scores[saved_index]
            insertion_position = position
            previous = position - 1
            while (
                insertion_position > lower
                and saved_score < scores[indices[previous]]
            ):
                indices[insertion_position] = indices[previous]
                insertion_position -= 1
                previous -= 1
            indices[insertion_position] = saved_index

        if not stack:
            break
        lower, upper, depth = stack.pop()

    return tuple(indices)


def _fourier_rhythm_score(
    series: tuple[float, ...],
    positive_bins: range,
) -> float:
    """Score one number's appearance series with the donor's rhythm formula."""

    width = len(series)
    appearances = sum(series)
    if appearances < 2:
        return 0.0
    mean = appearances / width
    spectrum = bluestein_dft(tuple(value - mean for value in series))
    dominant_bin = positive_bins.start
    dominant_magnitude = abs(spectrum[dominant_bin])
    for candidate_bin in positive_bins:
        candidate_magnitude = abs(spectrum[candidate_bin])
        if candidate_magnitude > dominant_magnitude:
            dominant_bin = candidate_bin
            dominant_magnitude = candidate_magnitude
    frequency = dominant_bin / width
    period = 1.0 / frequency
    if not 2 < period < width / 2:
        return 0.0
    last_hit = max(index for index, value in enumerate(series) if value)
    gap = (width - 1) - last_hit
    return 1.0 / (abs(gap - period) + 1.0)


def _fourier_rhythm_scores(history: tuple[CausalDrawRow, ...]) -> dict[int, float]:
    """Score every number over the donor's trailing, variable-length window."""

    window = _trailing(history, _TICKET1_WINDOW)
    width = len(window)
    scores = {number: 0.0 for number in _all_numbers()}
    positive_bins = range(1, (width - 1) // 2 + 1)
    if width == 0 or len(positive_bins) == 0:
        return scores
    for number in _all_numbers():
        series = tuple(1.0 if number in row.numbers else 0.0 for row in window)
        scores[number] = _fourier_rhythm_score(series, positive_bins)
    return scores


def _fourier_rhythm_ticket(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    """Ticket 1: descending donor score rank with donor tie ordering."""

    scores = _fourier_rhythm_scores(history)
    score_values = tuple(scores[number] for number in _all_numbers())
    ranked_indices = _legacy_numpy_argsort(score_values)
    ranked_numbers = tuple(
        index + _MIN_NUMBER for index in reversed(ranked_indices)
    )
    return tuple(sorted(ranked_numbers[:_PICK_COUNT]))


def _cold_numbers_ticket(
    history: tuple[CausalDrawRow, ...],
    exclude: frozenset[int],
) -> tuple[int, ...]:
    """Ticket 2: the six least frequent eligible numbers over the trailing window."""

    frequencies = _frequencies(_trailing(history, _TICKET2_WINDOW))
    candidates = [number for number in _all_numbers() if number not in exclude]
    coldest = sorted(candidates, key=lambda number: frequencies.get(number, 0))
    return tuple(sorted(coldest[:_PICK_COUNT]))


def _tail_balance_ticket(
    history: tuple[CausalDrawRow, ...],
    exclude: frozenset[int],
) -> tuple[int, ...]:
    """Ticket 3: round-robin across last-digit groups ordered by their hottest member."""

    frequencies = _frequencies(_trailing(history, _TICKET3_WINDOW))
    tail_groups: dict[int, list[tuple[int, int]]] = {
        tail: [] for tail in range(_TAIL_MODULUS)
    }
    for number in _all_numbers():
        if number not in exclude:
            tail_groups[number % _TAIL_MODULUS].append((number, frequencies.get(number, 0)))
    for group in tail_groups.values():
        group.sort(key=lambda entry: entry[1], reverse=True)

    available_tails = [tail for tail in range(_TAIL_MODULUS) if tail_groups[tail]]
    available_tails.sort(key=lambda tail: tail_groups[tail][0][1], reverse=True)

    selected: list[int] = []
    group_cursor = {tail: 0 for tail in range(_TAIL_MODULUS)}
    completed_rounds = 0
    while len(selected) < _PICK_COUNT:
        for tail in available_tails:
            if len(selected) >= _PICK_COUNT:
                break
            group = tail_groups[tail]
            cursor = group_cursor[tail]
            if cursor < len(group):
                number = group[cursor][0]
                if number not in selected:
                    selected.append(number)
                    group_cursor[tail] += 1
        completed_rounds += 1
        if completed_rounds > _TAIL_ROUND_LIMIT:
            break

    if len(selected) < _PICK_COUNT:
        remaining = [
            number
            for number in _all_numbers()
            if number not in selected and number not in exclude
        ]
        remaining.sort(key=lambda number: frequencies.get(number, 0), reverse=True)
        selected.extend(remaining[: _PICK_COUNT - len(selected)])

    return tuple(sorted(selected[:_PICK_COUNT]))


def _full_history_gap(history: tuple[CausalDrawRow, ...], number: int) -> int:
    """Return the donor's gap, which scans the full history, not ticket 4's window."""

    for index in range(len(history) - 1, -1, -1):
        if number in history[index].numbers:
            return len(history) - 1 - index
    return len(history)


def _is_gray_zone_deviation(deviation: float) -> bool:
    """Preserve the donor's inclusive gray-zone threshold."""

    return -_GRAY_ZONE_DEVIATION <= deviation <= _GRAY_ZONE_DEVIATION


def _gray_zone_gap_ticket(
    history: tuple[CausalDrawRow, ...],
    exclude: frozenset[int],
) -> tuple[int, ...]:
    """Ticket 4: longest-absent numbers whose recent frequency sits near expectation."""

    window = _trailing(history, _TICKET4_WINDOW)
    expected = len(window) * _PICK_COUNT / (_MAX_NUMBER - _MIN_NUMBER + 1)
    frequencies = _frequencies(window)

    gray_candidates: list[tuple[int, int]] = []
    for number in _all_numbers():
        if number in exclude:
            continue
        deviation = frequencies.get(number, 0) - expected
        if _is_gray_zone_deviation(deviation):
            gray_candidates.append((number, _full_history_gap(history, number)))
    gray_candidates.sort(key=lambda entry: entry[1], reverse=True)
    selected = [number for number, _ in gray_candidates[:_PICK_COUNT]]

    if len(selected) < _PICK_COUNT:
        remaining = [
            number
            for number in _all_numbers()
            if number not in selected and number not in exclude
        ]
        fallback_frequencies = _frequencies(_trailing(history, _TICKET4_FALLBACK_WINDOW))
        remaining.sort(key=lambda number: fallback_frequencies.get(number, 0), reverse=True)
        selected.extend(remaining[: _PICK_COUNT - len(selected)])

    return tuple(sorted(selected[:_PICK_COUNT]))


def quad_strike_tickets(
    history: tuple[CausalDrawRow, ...],
) -> tuple[tuple[int, ...], ...]:
    """Build the donor's four positional tickets under cumulative exclusion."""

    ticket1 = _fourier_rhythm_ticket(history)
    exclude1 = frozenset(ticket1)
    ticket2 = _cold_numbers_ticket(history, exclude1)
    exclude2 = exclude1 | frozenset(ticket2)
    ticket3 = _tail_balance_ticket(history, exclude2)
    exclude3 = exclude2 | frozenset(ticket3)
    ticket4 = _gray_zone_gap_ticket(history, exclude3)
    return (ticket1, ticket2, ticket3, ticket4)


class BigLottoQuadStrikeAdapter(PortfolioBetAdapter):
    """Deterministic four-ticket portfolio with cumulative cross-ticket exclusion."""

    strategy_id = _STRATEGY_ID
    strategy_name = "大樂透 Quad Strike 4注（Fourier + Cold + Tail + Gray Gap）"  # noqa: RUF001
    strategy_version = "v0.1"
    min_history = _MIN_HISTORY
    supported_lottery_types = (cast(LotteryType, LotteryType.BIG_LOTTO),)
    native_ticket_count = _NATIVE_TICKET_COUNT
    minimum_native_ticket_count = _NATIVE_TICKET_COUNT
    maximum_native_ticket_count = _NATIVE_TICKET_COUNT

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        del lottery_type
        if len({row.draw for row in history}) != len(history):
            raise InvalidOutput(f"{self.strategy_id}: causal draw identities must be unique")
        tickets = quad_strike_tickets(history)
        flattened = tuple(number for ticket in tickets for number in ticket)
        if (
            len(tickets) != _NATIVE_TICKET_COUNT
            or any(
                len(ticket) != _PICK_COUNT
                or len(set(ticket)) != _PICK_COUNT
                or any(not _MIN_NUMBER <= number <= _MAX_NUMBER for number in ticket)
                for ticket in tickets
            )
            or len(set(flattened)) != _NATIVE_TICKET_COUNT * _PICK_COUNT
        ):
            raise InvalidOutput(f"{self.strategy_id}: invalid Quad Strike portfolio")
        return tickets


__all__ = ["BigLottoQuadStrikeAdapter", "quad_strike_tickets"]
