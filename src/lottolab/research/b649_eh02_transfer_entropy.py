"""EH02 (B649 Track B cross-lottery transfer-entropy) core primitives.

Implements exactly the design locked in
`B649_TRACK_B_EH02_PARAMETER_LOCK_PROPOSAL_R1.md` (off-repo, SHA-256
`69e03026ce40962cfed8a8295336918edc6f6db8d3d6f0f3f5a487a1bfc9262b`) Sec.
2-9, applied to the dataset identities resolved in
`B649_TRACK_B_EH02_DATA_AUTHORITY_AND_PARAMETER_LOCK_RESOLUTION_R1.md`
(off-repo, SHA-256
`76aef07bedb10d51ab0446170c116bf9b5ffee8fc3b5c36ad8e13c14f46daae7`). Both are
pinned by the canonical preregistration
(`docs/research/matrix-native-results/eh02-b649-cross-lottery-transfer-entropy-v1-preregistration.md`).

Deliberately does NOT reuse the EH01/EH10 shared module's `perm_key` /
`hash_sort_permutation_indices` (`b649_eh01_eh10_shared`): the EH02 proposal
(Sec. 5.3) salts every permutation key with the literal hypothesis tag
``"EH02"`` and an ``EDGE_ID``, and indexes by *eligible-index position*
(an integer position within one edge's own eligible sequence), not by raw
``draw_id`` -- so the two hypotheses' permutation families can never
silently collide or be swapped. Holm correction, ``ERA4`` era assignment,
and the raw-p formula are the *same* mathematics for both hypotheses and
are imported directly from ``b649_eh01_eh10_shared`` rather than
re-implemented a second time.

Implementation notes pinned before any real data is read (Sec. 12 rationale
classes apply; each is a ``PROJECT_CONVENTION``/``STANDARD_STATISTICAL_
CONVENTION`` operationalization of prose the proposal does not reduce to an
exact formula, not a free scientific parameter):

- **Per-series discretization, computed once.** "Each of the three scalar
  series ... is independently discretized" (proposal Sec. 3.1) is read as
  *one* causal expanding-window tertile pass per physical series (B649,
  T539, P638 Zone-1), each over that series' own complete chronological
  history. The resulting bin labels are reused identically whether the
  series is acting as target or as source (forward vs. reverse direction);
  Sec. 7.1's "bin edges recomputed causally on each series in its new role"
  is read as reaffirming the causal *mechanism*, not a second, role-specific
  discretization pass.
- **Tie-break edge_context** is the coarse structural role named in Sec.
  3.3 ("B649 target ties, or source ties"): ``"TARGET_SELF"`` for B649 in
  every edge, ``"SOURCE"`` for T539/P638 Zone-1 in every edge. Per-lottery
  separation is already provided by the ``lottery`` argument.
- **Tertile cutpoints** at causal position i (0-indexed, with ``m = i``
  strictly-prior observations) use order-statistic ranks
  ``m // 3`` and ``(2 * m) // 3`` over the tie-broken-ascending prior
  sample. The first two positions (``m < 2``) cannot form two interior
  cutpoints and are assigned the middle bin (``1``) by convention; both
  fall inside every edge's 200-observation burn-in, so this convention
  never reaches an analyzed (post-burn-in) row.
- **ERA4 permutation key material** uses each position's *global* 1-indexed
  eligible-index position (not a per-era-local renumbering), mirroring the
  EH01/EH10 shared module's own choice to key by a global identifier rather
  than a locally-renumbered one -- this keeps every one of the four eras'
  keys structurally distinct even though the ``perm_key`` payload has no
  separate era-number field.
"""

from __future__ import annotations

import bisect
import hashlib
import math
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta

from lottolab.research.b649_eh01_eh10_shared import (
    ERA4_POLICY,
    GLOBAL_POLICY,
    MASTER_SEED,
    era4_assignment,
)

HYPOTHESIS_TAG = "EH02"
BIN_COUNT = 3
ALTERNATE_BIN_COUNT = 2
BURN_IN_OBSERVATIONS = 200
GEOMETRY_FLOOR_TOTAL = 800
GEOMETRY_FLOOR_PER_ERA = 30
STALE_DAYS = 28
PERMUTATIONS_PER_POLICY = 999

EDGE_T539_TO_B649 = "T539_TO_B649"
EDGE_P638Z1_TO_B649 = "P638Z1_TO_B649"
EDGE_B649_TO_T539_REVERSE = "B649_TO_T539_REVERSE"
EDGE_B649_TO_P638Z1_REVERSE = "B649_TO_P638Z1_REVERSE"
ALL_EDGE_IDS = (
    EDGE_T539_TO_B649,
    EDGE_P638Z1_TO_B649,
    EDGE_B649_TO_T539_REVERSE,
    EDGE_B649_TO_P638Z1_REVERSE,
)

TARGET_SELF_CONTEXT = "TARGET_SELF"
SOURCE_CONTEXT = "SOURCE"


class Eh02DesignError(ValueError):
    """An EH02 computation violated a locked invariant (fail-closed)."""


# ---------------------------------------------------------------------------
# Tie-break and causal discretization (proposal Sec. 3.1-3.3)
# ---------------------------------------------------------------------------


def tie_key(edge_context: str, lottery: str, draw_id: int) -> bytes:
    """``SHA256(6490110|EH02|TIE_V1|edge_context|lottery|canonical_draw_id)``."""

    if edge_context not in (TARGET_SELF_CONTEXT, SOURCE_CONTEXT):
        raise ValueError(f"unknown tie edge_context: {edge_context!r}")
    if type(draw_id) is not int or draw_id < 0:
        raise ValueError("draw_id must be a non-negative int")
    payload = f"{MASTER_SEED}|{HYPOTHESIS_TAG}|TIE_V1|{edge_context}|{lottery}|{draw_id}"
    return hashlib.sha256(payload.encode("utf-8")).digest()


def causal_tertile_bins(
    values: tuple[int, ...],
    draw_ids: tuple[int, ...],
    *,
    edge_context: str,
    lottery: str,
    bin_count: int = BIN_COUNT,
) -> tuple[int, ...]:
    """Bin each ``values[i]`` causally into ``{0, ..., bin_count - 1}``.

    Position ``i``'s bin edges come only from ``values[:i]`` (strictly prior
    observations), tie-broken by ``tie_key`` before ranking, never from
    ``values[i]`` itself or anything later. See module docstring for the
    exact cutpoint-index and early-position conventions.
    """

    if bin_count < 2:
        raise ValueError("bin_count must be >= 2")
    n = len(values)
    if len(draw_ids) != n:
        raise ValueError("values and draw_ids must be the same length")

    middle_bin = bin_count // 2
    bins: list[int] = []
    for i in range(n):
        if i < 2:
            bins.append(middle_bin)
            continue
        prior_values = values[:i]
        prior_draw_ids = draw_ids[:i]
        ordered = sorted(
            zip(prior_values, prior_draw_ids, strict=True),
            key=lambda item: (item[0], tie_key(edge_context, lottery, item[1])),
        )
        ordered_values = [item[0] for item in ordered]
        m = len(ordered_values)
        cutpoints = [ordered_values[(k * m) // bin_count] for k in range(1, bin_count)]
        value = values[i]
        bin_index = bin_count - 1
        for edge_index, cutpoint in enumerate(cutpoints):
            if value < cutpoint:
                bin_index = edge_index
                break
        bins.append(bin_index)
    return tuple(bins)


# ---------------------------------------------------------------------------
# Discrete plug-in transfer entropy (Schreiber 2000) and MI comparator
# (proposal Sec. 3.4-3.5)
# ---------------------------------------------------------------------------


def discrete_transfer_entropy(
    x_next: tuple[int, ...], x_prev: tuple[int, ...], y_prior: tuple[int, ...]
) -> float:
    """``sum p(x',x,y) * ln( p(x'|x,y) / p(x'|x) )`` over observed triples only.

    Terms with ``p(x,y) = 0`` cannot occur (only observed triples are
    summed); a term with ``p(x,y) > 0`` and ``p(x',x,y) = 0`` is never
    visited and so contributes the standard ``0`` by construction.
    """

    n = len(x_next)
    if not (len(x_prev) == n and len(y_prior) == n):
        raise ValueError("x_next, x_prev, and y_prior must be the same length")
    if n == 0:
        raise Eh02DesignError("STOP_NONFINITE_ENDPOINT: empty eligible sample")

    triple_counts: Counter[tuple[int, int, int]] = Counter(
        zip(x_next, x_prev, y_prior, strict=True)
    )
    pair_xy_counts: Counter[tuple[int, int]] = Counter(zip(x_prev, y_prior, strict=True))
    pair_x1x_counts: Counter[tuple[int, int]] = Counter(zip(x_next, x_prev, strict=True))
    single_x_counts: Counter[int] = Counter(x_prev)

    total = 0.0
    for (xp, x, y), count_xyz in triple_counts.items():
        count_xy = pair_xy_counts[(x, y)]
        count_x1x = pair_x1x_counts[(xp, x)]
        count_x = single_x_counts[x]
        p_xyz = count_xyz / n
        ratio = (count_xyz * count_x) / (count_xy * count_x1x)
        total += p_xyz * math.log(ratio)
    return total


def lagged_mutual_information(x_next: tuple[int, ...], y_prior: tuple[int, ...]) -> float:
    """``sum p(x',y) * ln( p(x',y) / (p(x') * p(y)) )`` over observed pairs only."""

    n = len(x_next)
    if len(y_prior) != n:
        raise ValueError("x_next and y_prior must be the same length")
    if n == 0:
        raise Eh02DesignError("STOP_NONFINITE_ENDPOINT: empty eligible sample")

    pair_counts: Counter[tuple[int, int]] = Counter(zip(x_next, y_prior, strict=True))
    x_counts: Counter[int] = Counter(x_next)
    y_counts: Counter[int] = Counter(y_prior)

    total = 0.0
    for (xp, y), count_xy in pair_counts.items():
        p_xy = count_xy / n
        ratio = (count_xy * n) / (x_counts[xp] * y_counts[y])
        total += p_xy * math.log(ratio)
    return total


# ---------------------------------------------------------------------------
# Deterministic, EDGE_ID-salted permutation generator (proposal Sec. 5.3)
# ---------------------------------------------------------------------------


def perm_key(edge_id: str, policy: str, replicate: int, index: int) -> bytes:
    """``SHA256(6490110|EH02|EDGE_ID|policy|zero_padded_b|i)``, ``i`` 1-indexed."""

    if edge_id not in ALL_EDGE_IDS:
        raise ValueError(f"unknown EH02 edge_id: {edge_id!r}")
    if policy not in (GLOBAL_POLICY, ERA4_POLICY):
        raise ValueError(f"unknown permutation policy: {policy!r}")
    if type(replicate) is not int or not 0 <= replicate <= 998:
        raise ValueError("replicate must be an int in [0, 998]")
    if type(index) is not int or index < 1:
        raise ValueError("index must be a positive int (1-indexed eligible position)")
    zero_padded_b = f"{replicate:03d}"
    payload = f"{MASTER_SEED}|{HYPOTHESIS_TAG}|{edge_id}|{policy}|{zero_padded_b}|{index}"
    return hashlib.sha256(payload.encode("utf-8")).digest()


def _hash_sort_order(
    edge_id: str, policy: str, replicate: int, positions: tuple[int, ...]
) -> tuple[int, ...]:
    """Sort ``positions`` (each a 1-indexed global eligible-index) by their ``perm_key``.

    Returns the same positions reordered; a hash collision among the given
    positions raises ``STOP_PERMUTATION_LEDGER_MISMATCH``.
    """

    keyed = [(perm_key(edge_id, policy, replicate, position), position) for position in positions]
    keyed.sort(key=lambda item: item[0])
    if len({item[0] for item in keyed}) != len(keyed):
        raise Eh02DesignError(
            "STOP_PERMUTATION_LEDGER_MISMATCH: hash-sort key collision detected"
        )
    return tuple(item[1] for item in keyed)


def global_surrogate_order(edge_id: str, replicate: int, n: int) -> tuple[int, ...]:
    """0-indexed permutation of ``range(n)`` under the ``GLOBAL`` policy for ``edge_id``."""

    if n <= 0:
        raise ValueError("n must be a positive int")
    positions = tuple(range(1, n + 1))
    sorted_positions = _hash_sort_order(edge_id, GLOBAL_POLICY, replicate, positions)
    return tuple(position - 1 for position in sorted_positions)


def era4_surrogate_order(edge_id: str, replicate: int, n: int) -> tuple[int, ...]:
    """0-indexed permutation of ``range(n)`` under the ``ERA4`` policy for ``edge_id``.

    Each of the four contiguous eligibility-ordered eras (``era4_assignment``)
    is permuted independently among its own (global-position-keyed) members;
    era boundaries never move.
    """

    if n <= 0:
        raise ValueError("n must be a positive int")
    eras = era4_assignment(n)
    result = [0] * n
    for era_number in (1, 2, 3, 4):
        era_positions_0idx = tuple(t - 1 for t, e in enumerate(eras, start=1) if e == era_number)
        global_positions = tuple(pos0 + 1 for pos0 in era_positions_0idx)
        sorted_global_positions = _hash_sort_order(
            edge_id, ERA4_POLICY, replicate, global_positions
        )
        for slot_0idx, source_global_position in zip(
            era_positions_0idx, sorted_global_positions, strict=True
        ):
            result[slot_0idx] = source_global_position - 1
    return tuple(result)


def apply_order(values: tuple[int, ...], order: tuple[int, ...]) -> tuple[int, ...]:
    """Reindex ``values`` by a permutation returned from the order functions above."""

    return tuple(values[i] for i in order)


def assert_distinct_permutations(
    orders: tuple[tuple[int, ...], ...], *, edge_id: str, policy: str
) -> None:
    if len(set(orders)) != len(orders):
        raise Eh02DesignError(
            f"STOP_PERMUTATION_LEDGER_MISMATCH: {edge_id}/{policy} produced two identical "
            "replicate permutations"
        )


def permutation_ledger_digest(
    orders: tuple[tuple[int, ...], ...], *, edge_id: str, policy: str
) -> str:
    hasher = hashlib.sha256()
    hasher.update(f"{MASTER_SEED}|{HYPOTHESIS_TAG}|{edge_id}|{policy}|{len(orders)}".encode())
    for order in orders:
        hasher.update(b"|")
        hasher.update(",".join(str(i) for i in order).encode())
    return hasher.hexdigest()


# ---------------------------------------------------------------------------
# Causal cross-series alignment (proposal Sec. 2.3-2.4, 6.1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class QualifyingSet:
    """Chronologically-ordered ``(target_index, source_index)`` pairs for one edge.

    Indices are 0-indexed positions into the target's and source's own
    ``draw_ids``/``draw_dates``/values arrays. ``target_index`` values are
    strictly ascending (built by iterating the target series in order).
    """

    target_indices: tuple[int, ...]
    source_indices: tuple[int, ...]
    same_day_excluded_count: int
    no_prior_count: int


def _last_index_strictly_before(sorted_dates: tuple[str, ...], cutoff_date: str) -> int | None:
    position = bisect.bisect_left(sorted_dates, cutoff_date)
    return position - 1 if position > 0 else None


def _last_index_at_or_before(sorted_dates: tuple[str, ...], cutoff_date: str) -> int | None:
    position = bisect.bisect_right(sorted_dates, cutoff_date)
    return position - 1 if position > 0 else None


def build_qualifying_set(
    target_dates: tuple[str, ...], source_dates: tuple[str, ...]
) -> QualifyingSet:
    """Targets ``t`` (0-indexed, ``t >= 1``) with a strictly-prior source draw.

    ``prior_L(t)``: the source draw with the maximum date strictly less than
    ``target_dates[t]`` (same-day excluded, date-only granularity). Mirrors
    proposal Sec. 2.3 exactly; used for both directions by swapping which
    series is passed as ``target_dates``/``source_dates``.
    """

    target_indices: list[int] = []
    source_indices: list[int] = []
    same_day_excluded = 0
    no_prior = 0
    for t in range(1, len(target_dates)):
        prior_index = _last_index_strictly_before(source_dates, target_dates[t])
        if prior_index is None:
            no_prior += 1
            continue
        if prior_index + 1 < len(source_dates) and source_dates[prior_index + 1] == target_dates[t]:
            same_day_excluded += 1
        target_indices.append(t)
        source_indices.append(prior_index)
    return QualifyingSet(
        target_indices=tuple(target_indices),
        source_indices=tuple(source_indices),
        same_day_excluded_count=same_day_excluded,
        no_prior_count=no_prior,
    )


def stale_source_indices(
    target_dates: tuple[str, ...],
    source_dates: tuple[str, ...],
    target_indices: tuple[int, ...],
    *,
    stale_days: int = STALE_DAYS,
) -> tuple[int | None, ...]:
    """``stale_prior_L(t)`` for each ``t`` in ``target_indices`` (Sec. 6.1).

    Last source draw with date ``<= target_date - stale_days``; ``None``
    where no such draw exists (that target is dropped from the timing
    control only, per Sec. 6.1's "restricted to targets where
    stale_prior_L(t) also exists").
    """

    results: list[int | None] = []
    for t in target_indices:
        target_date = date.fromisoformat(target_dates[t])
        cutoff = (target_date - timedelta(days=stale_days)).isoformat()
        results.append(_last_index_at_or_before(source_dates, cutoff))
    return tuple(results)


__all__ = [
    "ALL_EDGE_IDS",
    "ALTERNATE_BIN_COUNT",
    "BIN_COUNT",
    "BURN_IN_OBSERVATIONS",
    "EDGE_B649_TO_P638Z1_REVERSE",
    "EDGE_B649_TO_T539_REVERSE",
    "EDGE_P638Z1_TO_B649",
    "EDGE_T539_TO_B649",
    "GEOMETRY_FLOOR_PER_ERA",
    "GEOMETRY_FLOOR_TOTAL",
    "HYPOTHESIS_TAG",
    "PERMUTATIONS_PER_POLICY",
    "SOURCE_CONTEXT",
    "STALE_DAYS",
    "TARGET_SELF_CONTEXT",
    "Eh02DesignError",
    "QualifyingSet",
    "apply_order",
    "assert_distinct_permutations",
    "build_qualifying_set",
    "causal_tertile_bins",
    "discrete_transfer_entropy",
    "era4_surrogate_order",
    "global_surrogate_order",
    "lagged_mutual_information",
    "perm_key",
    "permutation_ledger_digest",
    "stale_source_indices",
    "tie_key",
]
