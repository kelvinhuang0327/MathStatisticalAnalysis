"""EH01: causal z-normalized matrix-profile motif/discord (B649 Track B).

Implements `B649_TRACK_B_EH01_EH10_PARAMETER_LOCK_PROPOSAL_R1.md` section 3
exactly: strict-left, non-overlapping candidate admissibility (no
query/future-overlap), population (``ddof=0``) z-normalization, unscaled
Euclidean profile distance, motif = negative global profile minimum,
discord = global profile maximum, earliest-index tie-breaks.

Two independent implementations are provided on purpose:

- :func:`causal_profile_bruteforce` evaluates the distance formula directly
  from its literal definition for every admissible pair -- ``O(n^2 * m)``,
  intended only for small synthetic fixtures, not real-scale execution.
- :func:`causal_profile` is the optimized ``O(n^2)`` incremental-dot-product
  (STOMP-family) implementation used for real execution. It is restricted to
  the causal lower-triangular admissible region, so it never computes the
  symmetric/future half a general-purpose matrix profile would.

The proposal's own `synthetic_fixture_check` requirement (section 10.3,
`STOP_SYNTHETIC_FIXTURE_FAIL`) is satisfied by
`tests/unit/test_b649_eh01_matrix_profile.py`, which asserts the two
implementations agree exactly on multiple small synthetic series before the
optimized path is trusted against real B649 history.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import accumulate


class GeometryInsufficientError(ValueError):
    """A series/era cannot produce every required finite profile endpoint.

    Maps to ``STOP_EH01_GEOMETRY_INSUFFICIENT``.
    """


@dataclass(frozen=True, slots=True)
class WindowStats:
    """Rolling population mean/std/validity for every window start of one length."""

    mean: tuple[float, ...]
    std: tuple[float, ...]
    valid: tuple[bool, ...]


def compute_window_stats(series: tuple[int, ...], m: int) -> WindowStats:
    """Rolling population (``ddof=0``) mean/std for every 0-indexed window start ``k``."""

    n = len(series)
    num_windows = n - m + 1
    if num_windows <= 0:
        raise GeometryInsufficientError(f"series length {n} is shorter than window length {m}")

    prefix = (0, *accumulate(series))
    prefix_sq = (0, *accumulate(v * v for v in series))

    means: list[float] = []
    stds: list[float] = []
    valids: list[bool] = []
    for k in range(num_windows):
        total = prefix[k + m] - prefix[k]
        total_sq = prefix_sq[k + m] - prefix_sq[k]
        mean = total / m
        variance = total_sq / m - mean * mean
        if variance < 0.0:
            variance = 0.0
        std = math.sqrt(variance)
        means.append(mean)
        stds.append(std)
        valids.append(std > 0.0)
    return WindowStats(mean=tuple(means), std=tuple(stds), valid=tuple(valids))


@dataclass(frozen=True, slots=True)
class CausalProfileResult:
    """One length's locked EH01 endpoints, 1-indexed window-start positions."""

    length: int
    eligible_query_count: int
    motif_distance: float
    motif_query_index: int
    motif_neighbor_index: int
    motif_support_count: int
    discord_distance: float
    discord_query_index: int
    discord_neighbor_index: int

    @property
    def motif_statistic(self) -> float:
        """``T_motif,m = -M_m`` -- larger is more motif-like."""

        return -self.motif_distance

    @property
    def discord_statistic(self) -> float:
        """``T_discord,m = D_m`` -- larger is more discord-like."""

        return self.discord_distance


def _direct_distance_sq(
    series: tuple[int, ...], m: int, i: int, j: int, stats: WindowStats
) -> float:
    """Literal ``sum((z(a)_k - z(c)_k)^2)`` for 1-indexed window starts ``i``, ``j``."""

    mu_i, sd_i = stats.mean[i - 1], stats.std[i - 1]
    mu_j, sd_j = stats.mean[j - 1], stats.std[j - 1]
    total = 0.0
    for t in range(m):
        za = (series[i - 1 + t] - mu_i) / sd_i
        zc = (series[j - 1 + t] - mu_j) / sd_j
        diff = za - zc
        total += diff * diff
    return total


def causal_profile_bruteforce(series: tuple[int, ...], m: int) -> CausalProfileResult:
    """Reference implementation: literal formula, every admissible pair, ``O(n^2 m)``.

    Intended only for small synthetic fixtures (correctness ground truth for
    :func:`causal_profile`), never for real B649-scale execution.
    """

    if m <= 0:
        raise ValueError("m must be positive")
    stats = compute_window_stats(series, m)
    num_windows = len(stats.mean)
    if num_windows < 2 * m:
        raise GeometryInsufficientError(
            f"length {m}: only {num_windows} windows, need >= {2 * m} for one eligible query"
        )

    row_best_sq: dict[int, float] = {}
    row_best_j: dict[int, int] = {}
    for i in range(2 * m, num_windows + 1):
        if not stats.valid[i - 1]:
            continue
        best_sq: float | None = None
        best_j = 0
        for j in range(1, i - m + 1):
            if not stats.valid[j - 1]:
                continue
            d_sq = _direct_distance_sq(series, m, i, j, stats)
            if best_sq is None or d_sq < best_sq:
                best_sq = d_sq
                best_j = j
        if best_sq is not None:
            row_best_sq[i] = best_sq
            row_best_j[i] = best_j

    eligible_query_count = sum(
        1 for i in range(2 * m, num_windows + 1) if stats.valid[i - 1]
    )
    if not row_best_sq or len(row_best_sq) != eligible_query_count:
        raise GeometryInsufficientError(
            f"length {m}: an eligible valid query had zero valid admissible candidates"
        )

    motif_i = min(row_best_sq, key=lambda i: (row_best_sq[i], i))
    motif_sq = row_best_sq[motif_i]
    motif_j = row_best_j[motif_i]

    discord_i = max(row_best_sq, key=lambda i: (row_best_sq[i], -i))
    discord_sq = row_best_sq[discord_i]
    discord_j = row_best_j[discord_i]

    support_count = 0
    for i in range(2 * m, num_windows + 1):
        if not stats.valid[i - 1]:
            continue
        for j in range(1, i - m + 1):
            if not stats.valid[j - 1]:
                continue
            if _direct_distance_sq(series, m, i, j, stats) == motif_sq:
                support_count += 1

    return CausalProfileResult(
        length=m,
        eligible_query_count=eligible_query_count,
        motif_distance=math.sqrt(motif_sq),
        motif_query_index=motif_i,
        motif_neighbor_index=motif_j,
        motif_support_count=support_count,
        discord_distance=math.sqrt(discord_sq),
        discord_query_index=discord_i,
        discord_neighbor_index=discord_j,
    )


def causal_profile(series: tuple[int, ...], m: int) -> CausalProfileResult:
    """Optimized ``O(n^2)`` causal profile via incremental diagonal dot products.

    Restricted to the strict-left, non-overlapping admissible region (diagonal
    offset ``i - j >= m``). Must agree exactly with
    :func:`causal_profile_bruteforce` on every synthetic fixture -- verified by
    `tests/unit/test_b649_eh01_matrix_profile.py`.
    """

    if m <= 0:
        raise ValueError("m must be positive")
    stats = compute_window_stats(series, m)
    num_windows = len(stats.mean)
    if num_windows < 2 * m:
        raise GeometryInsufficientError(
            f"length {m}: only {num_windows} windows, need >= {2 * m} for one eligible query"
        )

    x = series
    mean = stats.mean
    std = stats.std
    valid = stats.valid
    two_m = 2 * m
    inf = math.inf

    row_best_sq = [inf] * (num_windows + 1)
    row_best_j = [0] * (num_windows + 1)
    global_min_sq = inf
    global_min_support = 0

    for g in range(m, num_windows):
        i = two_m if two_m > g + 1 else g + 1
        if i > num_windows:
            continue
        j = i - g

        qt = 0
        base_i = i - 1
        base_j = j - 1
        for t in range(m):
            qt += x[base_i + t] * x[base_j + t]

        while True:
            if valid[i - 1] and valid[j - 1]:
                mu_i = mean[i - 1]
                sd_i = std[i - 1]
                mu_j = mean[j - 1]
                sd_j = std[j - 1]
                cov = (qt - m * mu_i * mu_j) / m
                d_sq = two_m * (1.0 - cov / (sd_i * sd_j))
                if d_sq < 0.0:
                    d_sq = 0.0

                if d_sq < global_min_sq:
                    global_min_sq = d_sq
                    global_min_support = 1
                elif d_sq == global_min_sq:
                    global_min_support += 1

                current = row_best_sq[i]
                if d_sq < current or (d_sq == current and j < row_best_j[i]):
                    row_best_sq[i] = d_sq
                    row_best_j[i] = j

            if i == num_windows:
                break
            qt = qt - x[i - 1] * x[j - 1] + x[i - 1 + m] * x[j - 1 + m]
            i += 1
            j += 1

    finite_rows = [row for row in range(two_m, num_windows + 1) if valid[row - 1]]
    if not finite_rows:
        raise GeometryInsufficientError(f"length {m}: no eligible valid query")
    for row in finite_rows:
        if row_best_sq[row] == inf:
            raise GeometryInsufficientError(
                f"length {m}: eligible valid query {row} has no valid admissible candidate"
            )

    motif_i = min(finite_rows, key=lambda row: (row_best_sq[row], row))
    motif_j = row_best_j[motif_i]

    discord_i = max(finite_rows, key=lambda row: (row_best_sq[row], -row))
    discord_j = row_best_j[discord_i]

    # The incremental covariance-shortcut formula above is exact in its QT
    # accumulation (plain Python int arithmetic) but loses precision in its
    # final small-difference-of-close-floats step whenever the true
    # distance is near zero (classic cancellation) -- immaterial to which
    # pair wins the argmin/argmax search (a ~1e-7 wobble never flips a
    # ranking against real B649-scale spread), but it would misreport the
    # handful of actually-published extremal distance values. Recompute
    # just those two (O(m), negligible cost) with the literal formula so
    # the reported numbers match `causal_profile_bruteforce` to full
    # float64 precision, not just to argmin/argmax agreement.
    motif_sq = _direct_distance_sq(series, m, motif_i, motif_j, stats)
    discord_sq = _direct_distance_sq(series, m, discord_i, discord_j, stats)

    return CausalProfileResult(
        length=m,
        eligible_query_count=len(finite_rows),
        motif_distance=math.sqrt(motif_sq),
        motif_query_index=motif_i,
        motif_neighbor_index=motif_j,
        motif_support_count=global_min_support,
        discord_distance=math.sqrt(discord_sq),
        discord_query_index=discord_i,
        discord_neighbor_index=discord_j,
    )


__all__ = [
    "CausalProfileResult",
    "GeometryInsufficientError",
    "WindowStats",
    "causal_profile",
    "causal_profile_bruteforce",
    "compute_window_stats",
]
