"""EH10: causal rolling normalized permutation entropy (B649 Track B).

Implements `B649_TRACK_B_EH01_EH10_PARAMETER_LOCK_PROPOSAL_R1.md` section 4
exactly: unit-delay ordinal patterns of order ``d in {3,4,5}`` over a rolling
window of `124` draws, deterministic SHA-256 tie handling (section 4.3),
natural-log entropy normalized by ``ln(d!)`` (section 4.4), primary
endpoint ``T_PE,d = 1 - min(Hnorm_d)`` with earliest-tie window selection.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from itertools import permutations


class GeometryInsufficientError(ValueError):
    """A series/era cannot produce every required order/window endpoint.

    Maps to ``STOP_EH10_GEOMETRY_INSUFFICIENT``.
    """


_FACTORIAL_LN = {d: math.log(math.factorial(d)) for d in (3, 4, 5)}


def tie_key(draw_id: int) -> bytes:
    """``SHA256("6490110|EH10|TIE_V1|" + canonical_draw_id)``.

    Deterministic and outcome-independent.
    """

    if type(draw_id) is not int or draw_id < 0:
        raise ValueError("draw_id must be a non-negative int")
    payload = f"6490110|EH10|TIE_V1|{draw_id}"
    return hashlib.sha256(payload.encode("utf-8")).digest()


def precompute_tie_keys(draw_ids: tuple[int, ...]) -> tuple[bytes, ...]:
    """Tie keys aligned 1:1 with ``draw_ids``, computed once and reused everywhere."""

    return tuple(tie_key(draw_id) for draw_id in draw_ids)


def ordinal_pattern(
    values: tuple[int, ...], keys: tuple[bytes, ...], start: int, d: int
) -> tuple[int, ...]:
    """Rank pattern of ``d`` unit-delay values starting at 0-indexed ``start``.

    Ranked ascending by ``(value, tie_key)``; ties in value are broken by the
    deterministic hash key, never by temporal index. The returned tuple lists
    local positions ``0..d-1`` in ascending-rank order, one of ``d!`` distinct
    canonical patterns.
    """

    local = range(start, start + d)
    ordered = sorted(local, key=lambda pos: (values[pos], keys[pos]))
    return tuple(pos - start for pos in ordered)


@dataclass(frozen=True, slots=True)
class EntropyWindowDiagnostics:
    window_start: int
    occupancy_fraction: float
    missing_pattern_count: int


@dataclass(frozen=True, slots=True)
class EntropyProfileResult:
    order: int
    window: int
    eligible_window_count: int
    statistic: float
    min_hnorm: float
    min_window_start: int
    diagnostics_at_min: EntropyWindowDiagnostics

    @property
    def statistic_value(self) -> float:
        """``T_PE,d = 1 - Hmin_d``."""

        return self.statistic


def rolling_permutation_entropy(
    values: tuple[int, ...],
    draw_ids: tuple[int, ...],
    *,
    order: int,
    window: int,
    keys: tuple[bytes, ...] | None = None,
) -> EntropyProfileResult:
    """Direct rolling scan: every eligible window, every overlapping order-``d`` word.

    Matches the proposal's section 4.4 formula literally -- no incremental
    shortcut is needed since EH10's total cost is negligible next to EH01's.
    """

    if order not in (3, 4, 5):
        raise ValueError("order must be 3, 4, or 5")
    n = len(values)
    if len(draw_ids) != n:
        raise ValueError("values and draw_ids must be the same length")
    if window <= 0:
        raise ValueError("window must be positive")
    if keys is None:
        keys = precompute_tie_keys(draw_ids)

    words_per_window = window - order + 1
    if words_per_window <= 0:
        raise GeometryInsufficientError(
            f"order {order}: window {window} produces no overlapping words"
        )
    eligible_window_count = n - window + 1
    if eligible_window_count <= 0:
        raise GeometryInsufficientError(
            f"order {order}: series length {n} is shorter than window {window}"
        )

    ln_factorial = _FACTORIAL_LN[order]
    best_hnorm: float | None = None
    best_start = 0
    best_counts: dict[tuple[int, ...], int] = {}

    for window_start in range(eligible_window_count):
        counts: dict[tuple[int, ...], int] = {}
        for word_start in range(window_start, window_start + words_per_window):
            pattern = ordinal_pattern(values, keys, word_start, order)
            counts[pattern] = counts.get(pattern, 0) + 1

        entropy = 0.0
        for count in counts.values():
            p = count / words_per_window
            entropy -= p * math.log(p)
        hnorm = entropy / ln_factorial

        if best_hnorm is None or hnorm < best_hnorm:
            best_hnorm = hnorm
            best_start = window_start
            best_counts = counts

    if best_hnorm is None:
        raise GeometryInsufficientError(f"order {order}: no eligible rolling window")

    occupied = len(best_counts)
    total_patterns = math.factorial(order)
    diagnostics = EntropyWindowDiagnostics(
        window_start=best_start + 1,
        occupancy_fraction=occupied / total_patterns,
        missing_pattern_count=total_patterns - occupied,
    )

    return EntropyProfileResult(
        order=order,
        window=window,
        eligible_window_count=eligible_window_count,
        statistic=1.0 - best_hnorm,
        min_hnorm=best_hnorm,
        min_window_start=best_start + 1,
        diagnostics_at_min=diagnostics,
    )


def all_ordinal_patterns(order: int) -> tuple[tuple[int, ...], ...]:
    """All ``d!`` canonical patterns for ``order`` -- used only by tests."""

    return tuple(permutations(range(order)))


__all__ = [
    "EntropyProfileResult",
    "EntropyWindowDiagnostics",
    "GeometryInsufficientError",
    "all_ordinal_patterns",
    "ordinal_pattern",
    "precompute_tie_keys",
    "rolling_permutation_entropy",
    "tie_key",
]
