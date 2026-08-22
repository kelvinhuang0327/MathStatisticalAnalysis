"""Exact CUSUM (cumulative sum) change-point statistics.

Pure, dependency-free implementations of the cumulative-sum path and the
trimmed max-absolute-CUSUM statistic used to test whether a chronological
sequence departs from a fixed null mean at some unknown point in time. No
fitting, no optimization, no randomness -- a single deterministic pass over
the sequence.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass


def cusum_path(values: Sequence[float], null_mean: float) -> tuple[float, ...]:
    """C_t = sum_{i=1}^{t} (values[i-1] - null_mean) for t = 1..len(values)."""

    if not values:
        raise ValueError("values must be non-empty")
    path: list[float] = []
    running = 0.0
    for value in values:
        running += value - null_mean
        path.append(running)
    return tuple(path)


def trimmed_split_points(
    n: int, trim_fraction_numerator: int, trim_fraction_denominator: int
) -> tuple[int, ...]:
    """1-indexed candidate split points `t` with at least the trim fraction

    of draws on both sides (the point `t` itself counts toward the "before"
    side, matching `cusum_path`'s 1-indexing).
    """

    if n <= 0:
        raise ValueError("n must be positive")
    if not 0 <= trim_fraction_numerator < trim_fraction_denominator:
        raise ValueError("trim fraction must lie in [0, 1)")
    low = max(1, math.ceil(n * trim_fraction_numerator / trim_fraction_denominator))
    high = min(n, n - low)
    if low > high:
        raise ValueError("trim fraction leaves no eligible split points for this n")
    return tuple(range(low, high + 1))


@dataclass(frozen=True, slots=True)
class MaxCusumResult:
    statistic: float
    argmax_split_point: int


def max_abs_cusum(
    values: Sequence[float],
    null_mean: float,
    *,
    trim_fraction_numerator: int,
    trim_fraction_denominator: int,
) -> MaxCusumResult:
    """The trimmed max-|CUSUM| statistic and the split point that attains it.

    Ties (equal |C_t|) resolve to the earliest such `t` -- deterministic,
    stated here so behavior never depends on iteration/dict order.
    """

    path = cusum_path(values, null_mean)
    candidates = trimmed_split_points(
        len(values), trim_fraction_numerator, trim_fraction_denominator
    )
    best_t = candidates[0]
    best_value = abs(path[best_t - 1])
    for t in candidates[1:]:
        current = abs(path[t - 1])
        if current > best_value:
            best_value = current
            best_t = t
    return MaxCusumResult(statistic=best_value, argmax_split_point=best_t)
