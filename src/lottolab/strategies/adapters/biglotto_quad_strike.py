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

Numerics are stdlib-only. The donor passes a real-valued bitstream to
``scipy.fft.fft``; SciPy routes that input through pocketfft's real-input
``r2c`` path rather than its complex-input path. The compact scalar
FFTPACK/pocketfft port below preserves that implementation path without
adding NumPy or SciPy.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from typing import cast

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InvalidOutput,
    PortfolioBetAdapter,
)

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


def _pocketfft_sincos_table(length: int) -> tuple[tuple[float, float], ...]:
    """Build pocketfft's quadrant-factorized ``exp(2j*pi*k/length)`` table."""

    pi = 3.141592653589793238462643383279502884197
    angle = 0.25 * pi / length
    nvalue = (length + 2) // 2
    shift = 1
    while (1 << shift) * (1 << shift) < nvalue:
        shift += 1
    mask = (1 << shift) - 1

    def calculate(index: int) -> tuple[float, float]:
        index <<= 3
        if index < 4 * length:
            if index < 2 * length:
                if index < length:
                    return math.cos(index * angle), math.sin(index * angle)
                return (
                    math.sin((2 * length - index) * angle),
                    math.cos((2 * length - index) * angle),
                )
            index -= 2 * length
            if index < length:
                return -math.sin(index * angle), math.cos(index * angle)
            return (
                -math.cos((2 * length - index) * angle),
                math.sin((2 * length - index) * angle),
            )

        index = 8 * length - index
        if index < 2 * length:
            if index < length:
                return math.cos(index * angle), -math.sin(index * angle)
            return (
                math.sin((2 * length - index) * angle),
                -math.cos((2 * length - index) * angle),
            )
        index -= 2 * length
        if index < length:
            return -math.sin(index * angle), -math.cos(index * angle)
        return (
            -math.cos((2 * length - index) * angle),
            -math.sin((2 * length - index) * angle),
        )

    first = [(1.0, 0.0)]
    first.extend(calculate(index) for index in range(1, mask + 1))
    second = [(1.0, 0.0)]
    second.extend(
        calculate(index * (mask + 1))
        for index in range(1, (nvalue + mask) // (mask + 1))
    )

    table: list[tuple[float, float]] = []
    for index in range(length + 1):
        if 2 * index <= length:
            left = first[index & mask]
            right = second[index >> shift]
            table.append(
                (
                    left[0] * right[0] - left[1] * right[1],
                    left[0] * right[1] + left[1] * right[0],
                )
            )
        else:
            reflected = length - index
            left = first[reflected & mask]
            right = second[reflected >> shift]
            table.append(
                (
                    left[0] * right[0] - left[1] * right[1],
                    -(left[0] * right[1] + left[1] * right[0]),
                )
            )
    return tuple(table)


def _pocketfft_factorize(length: int) -> tuple[int, ...]:
    """Match pocketfft's real-transform factor ordering."""

    factors: list[int] = []
    remaining = length
    while remaining % 4 == 0:
        factors.append(4)
        remaining >>= 2
    if remaining % 2 == 0:
        remaining >>= 1
        factors.append(2)
        factors[0], factors[-1] = factors[-1], factors[0]
    divisor = 3
    while divisor * divisor <= remaining:
        while remaining % divisor == 0:
            factors.append(divisor)
            remaining //= divisor
        divisor += 2
    if remaining > 1:
        factors.append(remaining)
    return tuple(factors)


def _pocketfft_real_twiddles(
    length: int,
    factors: tuple[int, ...],
) -> tuple[tuple[list[float], list[float]], ...]:
    """Compile the real FFTPACK stages' twiddle storage layout."""

    table = _pocketfft_sincos_table(length)
    compiled: list[tuple[list[float], list[float]]] = []
    l1 = 1
    for factor_index, factor in enumerate(factors):
        inner_length = length // (l1 * factor)
        twiddle = [0.0] * ((factor - 1) * (inner_length - 1))
        if factor_index < len(factors) - 1:
            for j in range(1, factor):
                for i in range(1, (inner_length - 1) // 2 + 1):
                    value = table[j * l1 * i]
                    offset = (j - 1) * (inner_length - 1) + 2 * i - 2
                    twiddle[offset] = value[0]
                    twiddle[offset + 1] = value[1]

        special = [0.0] * (2 * factor)
        if factor > 5:
            special[0] = 1.0
            for i in range(2, 2 * factor, 2):
                conjugate_offset = 2 * factor - i
                if i > conjugate_offset:
                    break
                value = table[(i // 2) * (length // factor)]
                special[i] = value[0]
                special[i + 1] = value[1]
                special[conjugate_offset] = value[0]
                special[conjugate_offset + 1] = -value[1]
        compiled.append((twiddle, special))
        l1 *= factor
    return tuple(compiled)


def _pocketfft_radf2(
    inner_length: int,
    group_count: int,
    source: list[float],
    target: list[float],
    twiddle: Sequence[float],
) -> None:
    def source_at(a: int, b: int, c: int) -> float:
        return source[a + inner_length * (b + group_count * c)]

    def target_set(a: int, b: int, c: int, value: float) -> None:
        target[a + inner_length * (b + 2 * c)] = value

    for group in range(group_count):
        target_set(
            0,
            0,
            group,
            source_at(0, group, 0) + source_at(0, group, 1),
        )
        target[inner_length - 1 + inner_length * (1 + 2 * group)] = (
            source_at(0, group, 0) - source_at(0, group, 1)
        )
    if inner_length % 2 == 0:
        for group in range(group_count):
            target_set(0, 1, group, -source_at(inner_length - 1, group, 1))
            target_set(
                inner_length - 1,
                0,
                group,
                source_at(inner_length - 1, group, 0),
            )
    if inner_length <= 2:
        return

    def multiply_pair(
        real_twiddle: float,
        imaginary_twiddle: float,
        real_value: float,
        imaginary_value: float,
    ) -> tuple[float, float]:
        return (
            real_twiddle * real_value + imaginary_twiddle * imaginary_value,
            real_twiddle * imaginary_value - imaginary_twiddle * real_value,
        )

    for group in range(group_count):
        for index in range(2, inner_length, 2):
            conjugate_index = inner_length - index
            offset = index - 2
            real_twiddle = twiddle[offset]
            imaginary_twiddle = twiddle[offset + 1]
            tr2, ti2 = multiply_pair(
                real_twiddle,
                imaginary_twiddle,
                source_at(index - 1, group, 1),
                source_at(index, group, 1),
            )
            target_set(
                index - 1,
                0,
                group,
                source_at(index - 1, group, 0) + tr2,
            )
            target_set(
                conjugate_index - 1,
                1,
                group,
                source_at(index - 1, group, 0) - tr2,
            )
            target_set(index, 0, group, ti2 + source_at(index, group, 0))
            target_set(
                conjugate_index,
                1,
                group,
                ti2 - source_at(index, group, 0),
            )


def _pocketfft_radf3(
    inner_length: int,
    group_count: int,
    source: list[float],
    target: list[float],
    twiddle: Sequence[float],
) -> None:
    taur = -0.5
    taui = 0.8660254037844386467637231707529362

    def source_at(a: int, b: int, c: int) -> float:
        return source[a + inner_length * (b + group_count * c)]

    def target_set(a: int, b: int, c: int, value: float) -> None:
        target[a + inner_length * (b + 3 * c)] = value

    for group in range(group_count):
        cr2 = source_at(0, group, 1) + source_at(0, group, 2)
        target_set(0, 0, group, source_at(0, group, 0) + cr2)
        target_set(
            0,
            2,
            group,
            taui * (source_at(0, group, 2) - source_at(0, group, 1)),
        )
        target_set(
            inner_length - 1,
            1,
            group,
            source_at(0, group, 0) + taur * cr2,
        )
    if inner_length == 1:
        return

    def multiply_pair(
        real_twiddle: float,
        imaginary_twiddle: float,
        real_value: float,
        imaginary_value: float,
    ) -> tuple[float, float]:
        return (
            real_twiddle * real_value + imaginary_twiddle * imaginary_value,
            real_twiddle * imaginary_value - imaginary_twiddle * real_value,
        )

    for group in range(group_count):
        for index in range(2, inner_length, 2):
            conjugate_index = inner_length - index
            dr2, di2 = multiply_pair(
                twiddle[index - 2],
                twiddle[index - 1],
                source_at(index - 1, group, 1),
                source_at(index, group, 1),
            )
            offset = inner_length - 1
            dr3, di3 = multiply_pair(
                twiddle[offset + index - 2],
                twiddle[offset + index - 1],
                source_at(index - 1, group, 2),
                source_at(index, group, 2),
            )
            old_dr2, old_di2, old_dr3, old_di3 = dr2, di2, dr3, di3
            dr2 = old_dr2 + old_dr3
            di2 = old_di2 + old_di3
            dr3 = old_di2 - old_di3
            di3 = old_dr3 - old_dr2
            target_set(
                index - 1,
                0,
                group,
                source_at(index - 1, group, 0) + dr2,
            )
            target_set(index, 0, group, source_at(index, group, 0) + di2)
            tr2 = source_at(index - 1, group, 0) + taur * dr2
            ti2 = source_at(index, group, 0) + taur * di2
            tr3 = taui * dr3
            ti3 = taui * di3
            target_set(index - 1, 2, group, tr2 + tr3)
            target_set(conjugate_index - 1, 1, group, tr2 - tr3)
            target_set(index, 2, group, ti3 + ti2)
            target_set(conjugate_index, 1, group, ti3 - ti2)


def _pocketfft_radf4(
    inner_length: int,
    group_count: int,
    source: list[float],
    target: list[float],
    twiddle: Sequence[float],
) -> None:
    hsqt2 = 0.707106781186547524400844362104849

    def source_at(a: int, b: int, c: int) -> float:
        return source[a + inner_length * (b + group_count * c)]

    def target_set(a: int, b: int, c: int, value: float) -> None:
        target[a + inner_length * (b + 4 * c)] = value

    for group in range(group_count):
        tr1, target_2 = (
            source_at(0, group, 3) + source_at(0, group, 1),
            source_at(0, group, 3) - source_at(0, group, 1),
        )
        tr2, target_1 = (
            source_at(0, group, 0) + source_at(0, group, 2),
            source_at(0, group, 0) - source_at(0, group, 2),
        )
        target_set(0, 0, group, tr2 + tr1)
        target_set(inner_length - 1, 3, group, tr2 - tr1)
        target_set(0, 2, group, target_2)
        target_set(inner_length - 1, 1, group, target_1)
    if inner_length % 2 == 0:
        for group in range(group_count):
            ti1 = -hsqt2 * (
                source_at(inner_length - 1, group, 1)
                + source_at(inner_length - 1, group, 3)
            )
            tr1 = hsqt2 * (
                source_at(inner_length - 1, group, 1)
                - source_at(inner_length - 1, group, 3)
            )
            target_set(
                inner_length - 1,
                0,
                group,
                source_at(inner_length - 1, group, 0) + tr1,
            )
            target_set(
                inner_length - 1,
                2,
                group,
                source_at(inner_length - 1, group, 0) - tr1,
            )
            target_set(
                0,
                3,
                group,
                ti1 + source_at(inner_length - 1, group, 2),
            )
            target_set(
                0,
                1,
                group,
                ti1 - source_at(inner_length - 1, group, 2),
            )
    if inner_length <= 2:
        return

    def multiply_pair(
        real_twiddle: float,
        imaginary_twiddle: float,
        real_value: float,
        imaginary_value: float,
    ) -> tuple[float, float]:
        return (
            real_twiddle * real_value + imaginary_twiddle * imaginary_value,
            real_twiddle * imaginary_value - imaginary_twiddle * real_value,
        )

    for group in range(group_count):
        for index in range(2, inner_length, 2):
            conjugate_index = inner_length - index
            cr2, ci2 = multiply_pair(
                twiddle[index - 2],
                twiddle[index - 1],
                source_at(index - 1, group, 1),
                source_at(index, group, 1),
            )
            offset = inner_length - 1
            cr3, ci3 = multiply_pair(
                twiddle[offset + index - 2],
                twiddle[offset + index - 1],
                source_at(index - 1, group, 2),
                source_at(index, group, 2),
            )
            offset *= 2
            cr4, ci4 = multiply_pair(
                twiddle[offset + index - 2],
                twiddle[offset + index - 1],
                source_at(index - 1, group, 3),
                source_at(index, group, 3),
            )
            tr1, tr4 = cr4 + cr2, cr4 - cr2
            ti1, ti4 = ci2 + ci4, ci2 - ci4
            tr2, tr3 = source_at(index - 1, group, 0) + cr3, source_at(
                index - 1, group, 0
            ) - cr3
            ti2, ti3 = source_at(index, group, 0) + ci3, source_at(index, group, 0) - ci3
            target_set(index - 1, 0, group, tr2 + tr1)
            target_set(conjugate_index - 1, 3, group, tr2 - tr1)
            target_set(index, 0, group, ti1 + ti2)
            target_set(conjugate_index, 3, group, ti1 - ti2)
            target_set(index - 1, 2, group, tr3 + ti4)
            target_set(conjugate_index - 1, 1, group, tr3 - ti4)
            target_set(index, 2, group, tr4 + ti3)
            target_set(conjugate_index, 1, group, tr4 - ti3)


def _pocketfft_radf5(
    inner_length: int,
    group_count: int,
    source: list[float],
    target: list[float],
    twiddle: Sequence[float],
) -> None:
    tr11 = 0.3090169943749474241022934171828191
    ti11 = 0.9510565162951535721164393333793821
    tr12 = -0.8090169943749474241022934171828191
    ti12 = 0.5877852522924731291687059546390728

    def source_at(a: int, b: int, c: int) -> float:
        return source[a + inner_length * (b + group_count * c)]

    def target_set(a: int, b: int, c: int, value: float) -> None:
        target[a + inner_length * (b + 5 * c)] = value

    for group in range(group_count):
        cr2, ci5 = (
            source_at(0, group, 4) + source_at(0, group, 1),
            source_at(0, group, 4) - source_at(0, group, 1),
        )
        cr3, ci4 = (
            source_at(0, group, 3) + source_at(0, group, 2),
            source_at(0, group, 3) - source_at(0, group, 2),
        )
        target_set(0, 0, group, source_at(0, group, 0) + cr2 + cr3)
        target_set(
            inner_length - 1,
            1,
            group,
            source_at(0, group, 0) + tr11 * cr2 + tr12 * cr3,
        )
        target_set(0, 2, group, ti11 * ci5 + ti12 * ci4)
        target_set(
            inner_length - 1,
            3,
            group,
            source_at(0, group, 0) + tr12 * cr2 + tr11 * cr3,
        )
        target_set(0, 4, group, ti12 * ci5 - ti11 * ci4)
    if inner_length == 1:
        return

    def multiply_pair(
        real_twiddle: float,
        imaginary_twiddle: float,
        real_value: float,
        imaginary_value: float,
    ) -> tuple[float, float]:
        return (
            real_twiddle * real_value + imaginary_twiddle * imaginary_value,
            real_twiddle * imaginary_value - imaginary_twiddle * real_value,
        )

    for group in range(group_count):
        for index in range(2, inner_length, 2):
            conjugate_index = inner_length - index
            values: list[tuple[float, float]] = []
            for factor in range(4):
                offset = factor * (inner_length - 1)
                values.append(
                    multiply_pair(
                        twiddle[offset + index - 2],
                        twiddle[offset + index - 1],
                        source_at(index - 1, group, factor + 1),
                        source_at(index, group, factor + 1),
                    )
                )
            (dr2, di2), (dr3, di3), (dr4, di4), (dr5, di5) = values
            old_dr2, old_di2, old_dr5, old_di5 = dr2, di2, dr5, di5
            dr2 = old_dr2 + old_dr5
            di2 = old_di2 + old_di5
            dr5 = old_di2 - old_di5
            di5 = old_dr5 - old_dr2
            old_dr3, old_di3, old_dr4, old_di4 = dr3, di3, dr4, di4
            dr3 = old_dr3 + old_dr4
            di3 = old_di3 + old_di4
            dr4 = old_di3 - old_di4
            di4 = old_dr4 - old_dr3
            tr2 = source_at(index - 1, group, 0) + tr11 * dr2 + tr12 * dr3
            ti2 = source_at(index, group, 0) + tr11 * di2 + tr12 * di3
            tr3 = source_at(index - 1, group, 0) + tr12 * dr2 + tr11 * dr3
            ti3 = source_at(index, group, 0) + tr12 * di2 + tr11 * di3
            tr5 = ti11 * dr5 + ti12 * dr4
            ti5 = ti11 * di5 + ti12 * di4
            tr4 = ti12 * dr5 - ti11 * dr4
            ti4 = ti12 * di5 - ti11 * di4
            target_set(
                index - 1,
                0,
                group,
                source_at(index - 1, group, 0) + dr2 + dr3,
            )
            target_set(index, 0, group, source_at(index, group, 0) + di2 + di3)
            target_set(index - 1, 2, group, tr2 + tr5)
            target_set(conjugate_index - 1, 1, group, tr2 - tr5)
            target_set(index, 2, group, ti5 + ti2)
            target_set(conjugate_index, 1, group, ti5 - ti2)
            target_set(index - 1, 4, group, tr3 + tr4)
            target_set(conjugate_index - 1, 3, group, tr3 - tr4)
            target_set(index, 4, group, ti4 + ti3)
            target_set(conjugate_index, 3, group, ti4 - ti3)


def _pocketfft_radfg(
    inner_length: int,
    factor: int,
    group_count: int,
    source: list[float],
    target: list[float],
    twiddle: Sequence[float],
    special: Sequence[float],
) -> None:
    half_factor = (factor + 1) // 2
    flattened_group = inner_length * group_count

    def source_group_at(a: int, b: int) -> float:
        return source[a + flattened_group * b]

    if inner_length > 1:
        for j in range(1, half_factor):
            conjugate_j = factor - j
            offset = (j - 1) * (inner_length - 1)
            conjugate_offset = (conjugate_j - 1) * (inner_length - 1)
            for group in range(group_count):
                twiddle_offset = offset
                conjugate_twiddle_offset = conjugate_offset
                for index in range(1, inner_length - 1, 2):
                    t1 = source[index + inner_length * (group + group_count * j)]
                    t2 = source[index + 1 + inner_length * (group + group_count * j)]
                    t3 = source[index + inner_length * (group + group_count * conjugate_j)]
                    t4 = source[index + 1 + inner_length * (group + group_count * conjugate_j)]
                    x1 = twiddle[twiddle_offset] * t1 + twiddle[twiddle_offset + 1] * t2
                    x2 = twiddle[twiddle_offset] * t2 - twiddle[twiddle_offset + 1] * t1
                    x3 = (
                        twiddle[conjugate_twiddle_offset] * t3
                        + twiddle[conjugate_twiddle_offset + 1] * t4
                    )
                    x4 = (
                        twiddle[conjugate_twiddle_offset] * t4
                        - twiddle[conjugate_twiddle_offset + 1] * t3
                    )
                    source[index + inner_length * (group + group_count * j)] = x3 + x1
                    source[index + 1 + inner_length * (group + group_count * conjugate_j)] = x3 - x1
                    source[index + 1 + inner_length * (group + group_count * j)] = x2 + x4
                    source[index + inner_length * (group + group_count * conjugate_j)] = x2 - x4
                    twiddle_offset += 2
                    conjugate_twiddle_offset += 2

    for j in range(1, half_factor):
        conjugate_j = factor - j
        for group in range(group_count):
            first = inner_length * (group + group_count * conjugate_j)
            second = inner_length * (group + group_count * j)
            if first != second:
                first_value = source[first]
                second_value = source[second]
                source[first] = first_value - second_value
                source[second] = first_value + second_value

    for stage in range(1, half_factor):
        conjugate_l = factor - stage
        for index in range(flattened_group):
            target[index + flattened_group * stage] = (
                source_group_at(index, 0)
                + special[2 * stage] * source_group_at(index, 1)
                + special[4 * stage] * source_group_at(index, 2)
            )
            target[index + flattened_group * conjugate_l] = (
                special[2 * stage + 1] * source_group_at(index, factor - 1)
                + special[4 * stage + 1] * source_group_at(index, factor - 2)
            )
        angle_index = 2 * stage
        j = 3
        conjugate_j = factor - 3
        while j < half_factor - 3:
            angle_index += stage
            if angle_index >= factor:
                angle_index -= factor
            ar1, ai1 = special[2 * angle_index], special[2 * angle_index + 1]
            angle_index += stage
            if angle_index >= factor:
                angle_index -= factor
            ar2, ai2 = special[2 * angle_index], special[2 * angle_index + 1]
            angle_index += stage
            if angle_index >= factor:
                angle_index -= factor
            ar3, ai3 = special[2 * angle_index], special[2 * angle_index + 1]
            angle_index += stage
            if angle_index >= factor:
                angle_index -= factor
            ar4, ai4 = special[2 * angle_index], special[2 * angle_index + 1]
            for index in range(flattened_group):
                target[index + flattened_group * stage] += (
                    ar1 * source_group_at(index, j)
                    + ar2 * source_group_at(index, j + 1)
                    + ar3 * source_group_at(index, j + 2)
                    + ar4 * source_group_at(index, j + 3)
                )
                target[index + flattened_group * conjugate_l] += (
                    ai1 * source_group_at(index, conjugate_j)
                    + ai2 * source_group_at(index, conjugate_j - 1)
                    + ai3 * source_group_at(index, conjugate_j - 2)
                    + ai4 * source_group_at(index, conjugate_j - 3)
                )
            j += 4
            conjugate_j -= 4
        while j < half_factor - 1:
            angle_index += stage
            if angle_index >= factor:
                angle_index -= factor
            ar1, ai1 = special[2 * angle_index], special[2 * angle_index + 1]
            angle_index += stage
            if angle_index >= factor:
                angle_index -= factor
            ar2, ai2 = special[2 * angle_index], special[2 * angle_index + 1]
            for index in range(flattened_group):
                target[index + flattened_group * stage] += (
                    ar1 * source_group_at(index, j)
                    + ar2 * source_group_at(index, j + 1)
                )
                target[index + flattened_group * conjugate_l] += (
                    ai1 * source_group_at(index, conjugate_j)
                    + ai2 * source_group_at(index, conjugate_j - 1)
                )
            j += 2
            conjugate_j -= 2
        while j < half_factor:
            angle_index += stage
            if angle_index >= factor:
                angle_index -= factor
            ar, ai = special[2 * angle_index], special[2 * angle_index + 1]
            for index in range(flattened_group):
                target[index + flattened_group * stage] += ar * source_group_at(index, j)
                target[index + flattened_group * conjugate_l] += ai * source_group_at(
                    index, conjugate_j
                )
            j += 1
            conjugate_j -= 1

    for index in range(flattened_group):
        target[index] = source_group_at(index, 0)
        for j in range(1, half_factor):
            target[index] += source_group_at(index, j)

    for group in range(group_count):
        for index in range(inner_length):
            source[index + inner_length * (0 + factor * group)] = target[
                index + inner_length * (group + group_count * 0)
            ]
    for j in range(1, half_factor):
        conjugate_j = factor - j
        output_pair = 2 * j - 1
        for group in range(group_count):
            source[inner_length - 1 + inner_length * (output_pair + factor * group)] = target[
                inner_length * (group + group_count * j)
            ]
            source[inner_length * (output_pair + 1 + factor * group)] = target[
                inner_length * (group + group_count * conjugate_j)
            ]
    if inner_length == 1:
        return
    for j in range(1, half_factor):
        conjugate_j = factor - j
        output_pair = 2 * j - 1
        for group in range(group_count):
            for index in range(1, inner_length - 1, 2):
                reflected = inner_length - index - 2
                source[index + inner_length * (output_pair + 1 + factor * group)] = (
                    target[index + inner_length * (group + group_count * j)]
                    + target[index + inner_length * (group + group_count * conjugate_j)]
                )
                source[reflected + inner_length * (output_pair + factor * group)] = (
                    target[index + inner_length * (group + group_count * j)]
                    - target[index + inner_length * (group + group_count * conjugate_j)]
                )
                source[index + 1 + inner_length * (output_pair + 1 + factor * group)] = (
                    target[index + 1 + inner_length * (group + group_count * j)]
                    + target[index + 1 + inner_length * (group + group_count * conjugate_j)]
                )
                source[reflected + 1 + inner_length * (output_pair + factor * group)] = (
                    target[index + 1 + inner_length * (group + group_count * conjugate_j)]
                    - target[index + 1 + inner_length * (group + group_count * j)]
                )


def _pocketfft_real_packed(signal: tuple[float, ...]) -> tuple[float, ...]:
    """Return pocketfft's packed real FFT output for one causal bitstream."""

    length = len(signal)
    if length <= 1:
        return signal
    factors = _pocketfft_factorize(length)
    compiled = _pocketfft_real_twiddles(length, factors)
    first = list(signal)
    second = [0.0] * length
    group_length = length
    for factor_index in range(len(factors)):
        factor_position = len(factors) - factor_index - 1
        factor = factors[factor_position]
        inner_length = length // group_length
        group_length //= factor
        twiddle, special = compiled[factor_position]
        if factor == 4:
            _pocketfft_radf4(inner_length, group_length, first, second, twiddle)
        elif factor == 2:
            _pocketfft_radf2(inner_length, group_length, first, second, twiddle)
        elif factor == 3:
            _pocketfft_radf3(inner_length, group_length, first, second, twiddle)
        elif factor == 5:
            _pocketfft_radf5(inner_length, group_length, first, second, twiddle)
        else:
            _pocketfft_radfg(
                inner_length,
                factor,
                group_length,
                first,
                second,
                twiddle,
                special,
            )
            first, second = second, first
        first, second = second, first
    return tuple(first)


def _legacy_complex_magnitude(real: float, imaginary: float) -> float:
    """Match the donor runtime's two-term complex-magnitude arithmetic."""

    larger = abs(real)
    smaller = abs(imaginary)
    if larger < smaller:
        larger, smaller = smaller, larger
    if larger == 0.0:
        return 0.0
    ratio = smaller / larger
    return larger * math.sqrt(1.0 + ratio * ratio)


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
    packed_spectrum = _pocketfft_real_packed(
        tuple(value - mean for value in series)
    )
    dominant_bin = positive_bins.start
    dominant_real = packed_spectrum[2 * dominant_bin - 1]
    dominant_imaginary = packed_spectrum[2 * dominant_bin]
    dominant_magnitude = _legacy_complex_magnitude(
        dominant_real,
        dominant_imaginary,
    )
    for candidate_bin in positive_bins:
        candidate_real = packed_spectrum[2 * candidate_bin - 1]
        candidate_imaginary = packed_spectrum[2 * candidate_bin]
        candidate_magnitude = _legacy_complex_magnitude(
            candidate_real,
            candidate_imaginary,
        )
        if candidate_magnitude > dominant_magnitude:
            dominant_bin = candidate_bin
            dominant_magnitude = candidate_magnitude
    # ``scipy.fft.fftfreq(width, 1)`` builds its positive grid from the
    # reciprocal ``1 / width`` and then multiplies by each bin index.  Keep
    # that operation order so the donor's pinned IEEE-754 values are retained.
    frequency = dominant_bin * (1.0 / width)
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
