"""Shared deterministic primitives for EH01/EH10 (B649 Track B, ordinal/temporal).

Implements exactly the null/seed/multiplicity mechanics locked by
`B649_TRACK_B_EH01_EH10_PARAMETER_LOCK_PROPOSAL_R1.md` sections 5 and 6: a
SHA-256 hash-sort permutation generator (no library-specific RNG), the
`ERA4` four-era assignment, the Monte Carlo raw p-value convention, and Holm
step-down multiplicity correction. Both EH01 and EH10 build their null
distributions on top of this module so the two hypotheses cannot silently
drift onto different permutation or correction mechanics.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

MASTER_SEED = 6490110
PERMUTATIONS_PER_POLICY = 999
GLOBAL_POLICY = "GLOBAL"
ERA4_POLICY = "ERA4"


def canonical_draw_id(draw_id: int) -> str:
    """ASCII base-10 rendering of ``draw_id``: no sign, no leading zeroes."""

    if type(draw_id) is not int:
        raise TypeError("draw_id must be an exact int")
    if draw_id < 0:
        raise ValueError("draw_id must not be negative")
    return str(draw_id)


def era4_assignment(n: int) -> tuple[int, ...]:
    """Return ``era(t)`` for ``t = 1..n`` per the locked ``ERA4`` formula.

    ``era(t) = min(4, floor(4 * (t - 1) / n) + 1)``. Eras are contiguous and
    differ in size by at most one draw.
    """

    if type(n) is not int or n <= 0:
        raise ValueError("n must be a positive int")
    return tuple(min(4, (4 * (t - 1)) // n + 1) for t in range(1, n + 1))


def era4_bounds(n: int) -> tuple[tuple[int, int], ...]:
    """Return 1-indexed ``(first, last)`` position bounds for each of the 4 eras."""

    eras = era4_assignment(n)
    bounds: list[tuple[int, int]] = []
    for era_number in (1, 2, 3, 4):
        positions = [t for t, e in enumerate(eras, start=1) if e == era_number]
        if not positions:
            raise ValueError(f"era {era_number} is empty for n={n}")
        bounds.append((positions[0], positions[-1]))
    return tuple(bounds)


def perm_key(policy: str, replicate: int, draw_id: int) -> bytes:
    """32-byte deterministic key: ``SHA256(seed|policy|zero_padded_b|canonical_draw_id)``."""

    if policy not in (GLOBAL_POLICY, ERA4_POLICY):
        raise ValueError(f"unknown permutation policy: {policy!r}")
    if type(replicate) is not int or not 0 <= replicate <= 998:
        raise ValueError("replicate must be an int in [0, 998]")
    zero_padded_b = f"{replicate:03d}"
    payload = f"{MASTER_SEED}|{policy}|{zero_padded_b}|{canonical_draw_id(draw_id)}"
    return hashlib.sha256(payload.encode("utf-8")).digest()


def hash_sort_permutation_indices(
    draw_ids: tuple[int, ...], policy: str, replicate: int
) -> tuple[int, ...]:
    """Return a 0-indexed permutation of ``range(len(draw_ids))``.

    Sorted ascending by ``perm_key``, with the canonical (integer) draw ID as
    the collision tie-break. Applying this permutation to a values array
    (``[values[i] for i in permutation]``) yields one GLOBAL-policy surrogate
    ordering, or -- when called once per era on that era's own draw-ID
    slice -- one within-era ERA4 ordering.
    """

    if len(set(draw_ids)) != len(draw_ids):
        raise ValueError("draw_ids must be unique for a well-defined permutation")
    keyed = [
        (perm_key(policy, replicate, draw_id), draw_id, index)
        for index, draw_id in enumerate(draw_ids)
    ]
    keyed.sort(key=lambda item: (item[0], item[1]))
    seen_keys = {item[0] for item in keyed}
    if len(seen_keys) != len(keyed):
        raise ValueError("STOP_PERMUTATION_LEDGER_MISMATCH: hash-sort key collision detected")
    return tuple(item[2] for item in keyed)


def global_surrogate_order(draw_ids: tuple[int, ...], replicate: int) -> tuple[int, ...]:
    """0-indexed permutation of the whole series under the ``GLOBAL`` policy."""

    return hash_sort_permutation_indices(draw_ids, GLOBAL_POLICY, replicate)


def era4_surrogate_order(draw_ids: tuple[int, ...], replicate: int) -> tuple[int, ...]:
    """0-indexed permutation of the whole series under the ``ERA4`` policy.

    Each era's draw IDs are permuted independently among themselves (their
    own hash-sort order), then the four eras are concatenated in their
    original position order -- era boundaries are fixed, only within-era
    content moves.
    """

    n = len(draw_ids)
    eras = era4_assignment(n)
    result = [0] * n
    for era_number in (1, 2, 3, 4):
        era_positions = [t - 1 for t, e in enumerate(eras, start=1) if e == era_number]
        era_draw_ids = tuple(draw_ids[p] for p in era_positions)
        local_order = hash_sort_permutation_indices(era_draw_ids, ERA4_POLICY, replicate)
        for slot, local_index in zip(era_positions, local_order, strict=True):
            result[slot] = era_positions[local_index]
    return tuple(result)


def apply_order(values: tuple[int, ...], order: tuple[int, ...]) -> tuple[int, ...]:
    """Reindex ``values`` by a permutation returned from the order functions above."""

    return tuple(values[i] for i in order)


def assert_distinct_permutations(orders: tuple[tuple[int, ...], ...], *, policy: str) -> None:
    """Stop if any two of the 999 replicate permutations for one policy are identical."""

    seen = set(orders)
    if len(seen) != len(orders):
        raise ValueError(
            f"STOP_PERMUTATION_LEDGER_MISMATCH: {policy} produced two identical replicate "
            "permutations"
        )


def permutation_ledger_digest(orders: tuple[tuple[int, ...], ...], *, policy: str) -> str:
    """SHA-256 over the exact sequence of generated index arrays, for provenance."""

    hasher = hashlib.sha256()
    hasher.update(f"{MASTER_SEED}|{policy}|{len(orders)}".encode())
    for order in orders:
        hasher.update(b"|")
        hasher.update(",".join(str(i) for i in order).encode())
    return hasher.hexdigest()


def raw_p_value(observed: float, surrogates: tuple[float, ...]) -> float:
    """``(B + 1) / (999 + 1)`` where ``B`` counts surrogates ``>= observed``."""

    if len(surrogates) != PERMUTATIONS_PER_POLICY:
        raise ValueError(
            f"STOP_PERMUTATION_LEDGER_MISMATCH: expected {PERMUTATIONS_PER_POLICY} surrogates, "
            f"got {len(surrogates)}"
        )
    exceed_count = sum(1 for value in surrogates if value >= observed)
    return (exceed_count + 1) / (PERMUTATIONS_PER_POLICY + 1)


@dataclass(frozen=True, slots=True)
class HolmResult:
    raw_p_values: tuple[float, ...]
    holm_adjusted_p_values: tuple[float, ...]


def holm_adjust(raw_p_values: tuple[float, ...]) -> HolmResult:
    """Step-down Holm correction, returned in the original endpoint order.

    ``p_holm,(r) = min(1, max_{j<=r} ((K - j + 1) * p_(j)))`` over p-values
    sorted ascending, then mapped back to their original positions.
    """

    k = len(raw_p_values)
    if k == 0:
        raise ValueError("raw_p_values must be non-empty")
    order = sorted(range(k), key=lambda i: raw_p_values[i])
    adjusted_sorted: list[float] = []
    running_max = 0.0
    for rank, original_index in enumerate(order, start=1):
        candidate = (k - rank + 1) * raw_p_values[original_index]
        running_max = max(running_max, candidate)
        adjusted_sorted.append(min(1.0, running_max))
    adjusted = [0.0] * k
    for rank_index, original_index in enumerate(order):
        adjusted[original_index] = adjusted_sorted[rank_index]
    return HolmResult(raw_p_values=raw_p_values, holm_adjusted_p_values=tuple(adjusted))


__all__ = [
    "ERA4_POLICY",
    "GLOBAL_POLICY",
    "MASTER_SEED",
    "PERMUTATIONS_PER_POLICY",
    "HolmResult",
    "apply_order",
    "assert_distinct_permutations",
    "canonical_draw_id",
    "era4_assignment",
    "era4_bounds",
    "era4_surrogate_order",
    "global_surrogate_order",
    "hash_sort_permutation_indices",
    "holm_adjust",
    "perm_key",
    "permutation_ledger_digest",
    "raw_p_value",
]
