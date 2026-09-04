"""Research-only exact-integer upper-bound core for covering numbers C(v, k, t).

Clean-room implementation from independently published mathematical sources
only. There is no donor code dependence of any kind.

Published authority
--------------------

* D. M. Gordon, G. Kuperberg, O. Patashnik, "New constructions for covering
  designs," Journal of Combinatorial Designs 3 (1995), 269-284
  (arXiv:math/9502238). Section V, "Combining Smaller Coverings," defines,
  for a split v = v1 + v2, the quantity c_{i,j} (0 <= i <= j <= t) as the
  number of blocks required to cover any t-subset with between i and j of
  its elements in the v1-part (and correspondingly between t-j and t-i in
  the v2-part), and gives the recurrence

      c_{i,j} <= min(
          min_ell C(v1, ell, j) * C(v2, k - ell, t - i),
          min_{i <= r < j} (c_{i,r} + c_{r+1,j}),
      )

  with C(v1 + v2, k, t) <= c_{0,t}. The "direct combination" term multiplies
  two independently recursively-available covering bounds; the "interval
  split" term unions two disjoint sub-coverings. This module implements
  exactly that recurrence (see ``_gkp_section5_upper_bound``).

* J. Schoenheim, "On coverings," Pacific Journal of Mathematics 14 (1964),
  1405-1411. Publishes the classical recursive LOWER bound on C(v, k, t).
  It is used here only as an independent sanity check on the upper bounds
  this module computes (see ``schoenheim_lower_bound``); it is never used
  as an upper-bound construction rule.

Scope boundary
--------------

This is a bound-only core: it returns integer upper bounds on C(v, k, t),
never materialized blocks. There is no LJCR/Zenodo dataset dependence, no
cached covering designs, no SQLite, no network access, and no donor code of
any kind. Reduction-step naming follows the published rule names above
(e.g. "TRIVIAL_T_ZERO", "GKP_SECTION5_INTERVAL_DP") rather than any
donor-specific terminology for elementary parameter reductions.

This module is not a production lottery strategy, a fixed-ticket strategy,
a prediction method, a replay method, a ranking candidate, or a Matrix
method.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum


class CoveringBoundClassification(StrEnum):
    """Exactness classification for a computed covering-number result."""

    TRIVIAL_EXACT = "TRIVIAL_EXACT"
    CONSTRUCTIVE_UPPER_BOUND = "CONSTRUCTIVE_UPPER_BOUND"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True, slots=True)
class CoveringNumberBound:
    """An integer upper bound on C(v, k, t), with deterministic provenance.

    ``upper_bound`` is only ``None`` for ``UNRESOLVED``. The trivial
    complete-block enumeration math.comb(v, k) is always a valid covering
    (every t-subset with t <= k <= v is contained in at least one k-subset),
    so every valid (v, k, t) in scope resolves to a bound; ``UNRESOLVED`` is
    reserved by the typed contract for a future rule set that is not
    exercised by the rules implemented in this module.
    """

    v: int
    k: int
    t: int
    upper_bound: int | None
    classification: CoveringBoundClassification
    rule: str
    provenance: tuple[str, ...] = field(default_factory=tuple)


def _require_int(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer, got {value!r}")


def _validate_parameters(v: int, k: int, t: int) -> None:
    _require_int("v", v)
    _require_int("k", k)
    _require_int("t", t)
    if t < 0:
        raise ValueError("t must be >= 0")
    if k < t:
        raise ValueError("k must be >= t")
    if v < k:
        raise ValueError("v must be >= k")


def _ceil_div(numerator: int, denominator: int) -> int:
    return -(-numerator // denominator)


_BOUND_CACHE: dict[tuple[int, int, int], CoveringNumberBound] = {}


def clear_cache() -> None:
    """Clear the memoized (v, k, t) -> bound cache.

    The cache is unbounded in principle (keyed by every distinct (v, k, t)
    triple visited by the recursive construction), so callers running many
    independent parameter sweeps should call this between runs.
    """

    _BOUND_CACHE.clear()


def covering_number_upper_bound(v: int, k: int, t: int) -> CoveringNumberBound:
    """Return a deterministic integer upper bound on the covering number C(v, k, t).

    Requires ``v >= k >= t >= 0``; raises ``ValueError`` otherwise.
    """

    _validate_parameters(v, k, t)
    key = (v, k, t)
    cached = _BOUND_CACHE.get(key)
    if cached is not None:
        return cached
    result = _compute_bound(v, k, t)
    _BOUND_CACHE[key] = result
    return result


def _compute_bound(v: int, k: int, t: int) -> CoveringNumberBound:
    if t == 0:
        # The only 0-subset (the empty set) is contained in every block;
        # exactly one block is necessary and sufficient.
        return CoveringNumberBound(
            v, k, t, 1, CoveringBoundClassification.TRIVIAL_EXACT, "TRIVIAL_T_ZERO"
        )
    if k == v:
        # The single k-subset (the whole ground set) contains every t-subset.
        return CoveringNumberBound(
            v, k, t, 1, CoveringBoundClassification.TRIVIAL_EXACT, "TRIVIAL_K_EQUALS_V"
        )
    if t == 1:
        # Covering every point with k-sized blocks: exactly ceil(v / k).
        return CoveringNumberBound(
            v,
            k,
            t,
            _ceil_div(v, k),
            CoveringBoundClassification.TRIVIAL_EXACT,
            "TRIVIAL_T_EQUALS_ONE",
        )
    if t == k:
        # Every k-subset is itself the only k-subset containing it as a
        # t-subset, so every k-subset must be its own block.
        return CoveringNumberBound(
            v,
            k,
            t,
            math.comb(v, k),
            CoveringBoundClassification.TRIVIAL_EXACT,
            "TRIVIAL_T_EQUALS_K",
        )

    # General case: 2 <= t < k < v. The complete enumeration of all
    # k-subsets is always a valid (if wasteful) covering, since t <= k <= v
    # guarantees every t-subset is contained in at least one k-subset. The
    # GKP Section V interval-DP construction is combined with it, and the
    # smallest valid candidate wins.
    best_bound = math.comb(v, k)
    best_rule = "TRIVIAL_COMPLETE_ENUMERATION"
    best_provenance: tuple[str, ...] = ()

    for v1 in range(t, v - t + 1):
        v2 = v - v1
        candidate = _gkp_section5_upper_bound(v1, v2, k, t)
        if candidate is not None and candidate < best_bound:
            best_bound = candidate
            best_rule = "GKP_SECTION5_INTERVAL_DP"
            best_provenance = (f"split_v1={v1}", f"split_v2={v2}")

    return CoveringNumberBound(
        v,
        k,
        t,
        best_bound,
        CoveringBoundClassification.CONSTRUCTIVE_UPPER_BOUND,
        best_rule,
        best_provenance,
    )


def _direct_combination_candidate(
    v1: int, v2: int, k: int, t: int, i: int, j: int
) -> int | None:
    """GKP direct-combination candidate for c_{i,j}: min_ell C(v1,ell,j)*C(v2,k-ell,t-i).

    ``ell`` (the v1-side block size) must leave a valid (v1, ell, j) covering
    and a valid (v2, k - ell, t - i) covering, i.e. j <= ell <= v1 and
    t - i <= k - ell <= v2. Returns ``None`` when no such ``ell`` exists.
    """

    ell_lo = max(j, k - v2)
    ell_hi = min(k - t + i, v1, k)
    best: int | None = None
    for ell in range(ell_lo, ell_hi + 1):
        left = covering_number_upper_bound(v1, ell, j).upper_bound
        right = covering_number_upper_bound(v2, k - ell, t - i).upper_bound
        if left is None or right is None:
            continue
        product = left * right
        if best is None or product < best:
            best = product
    return best


def _gkp_section5_upper_bound(v1: int, v2: int, k: int, t: int) -> int | None:
    """Compute c_{0,t} for a fixed split v = v1 + v2, per GKP Section V.

    Returns ``None`` when this split admits no valid candidate at all.
    """

    table: dict[tuple[int, int], int | None] = {}
    for i in range(t + 1):
        table[(i, i)] = _direct_combination_candidate(v1, v2, k, t, i, i)

    for width in range(1, t + 1):
        for i in range(0, t + 1 - width):
            j = i + width
            candidates: list[int] = []
            direct_value = _direct_combination_candidate(v1, v2, k, t, i, j)
            if direct_value is not None:
                candidates.append(direct_value)
            for r in range(i, j):
                left = table[(i, r)]
                right = table[(r + 1, j)]
                if left is not None and right is not None:
                    candidates.append(left + right)
            table[(i, j)] = min(candidates) if candidates else None

    return table[(0, t)]


def _schoenheim_lower_bound_unchecked(v: int, k: int, t: int) -> int:
    if t == 0:
        return 1
    inner = _schoenheim_lower_bound_unchecked(v - 1, k - 1, t - 1)
    return _ceil_div(v * inner, k)


def schoenheim_lower_bound(v: int, k: int, t: int) -> int:
    """Published LOWER bound on C(v, k, t) (Schoenheim, 1964).

    Provided only for independent sanity-checking of the upper bounds this
    module computes; it is never used as an upper-bound construction rule.
    """

    _validate_parameters(v, k, t)
    return _schoenheim_lower_bound_unchecked(v, k, t)
