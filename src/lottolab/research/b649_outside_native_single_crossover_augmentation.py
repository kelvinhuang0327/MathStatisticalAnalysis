"""Deterministic single-number crossover augmentation of the frozen K10 pool.

For each frozen MIN_OVERLAP K10 ticket ``s`` and each native PRE_DRAW ticket
``o`` lying outside the prior pruned 20-ticket pool, generates every
one-number swap child ``sorted((s - {x}) | {y})`` for ``x in s - o`` and
``y in o - s``. Every generated number is already present in some parent
ticket; no arbitrary number is introduced. Selection and exact evaluation
reuse the unchanged local-refinement search and scorer from
:mod:`lottolab.research.b649_min_overlap_full_union_local_refinement`; this
module only changes candidate-pool construction.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

BIG_LOTTO_POOL_SIZE: Final = 49
BIG_LOTTO_DRAW_SIZE: Final = 6
AUGMENTATION_ID: Final = "B649_OUTSIDE_NATIVE_SINGLE_CROSSOVER_AUGMENTATION_R1"

type Ticket = tuple[int, ...]


def _canonical_ticket(
    candidate: Sequence[int],
    *,
    pool_size: int,
    draw_size: int,
) -> Ticket:
    ticket = tuple(candidate)
    if (
        len(ticket) != draw_size
        or len(set(ticket)) != draw_size
        or any(type(number) is not int or not 1 <= number <= pool_size for number in ticket)
    ):
        raise ValueError(f"illegal ticket: {tuple(candidate)}")
    return tuple(sorted(ticket))


def generate_single_crossover_children(
    baseline_k10: Sequence[Sequence[int]],
    outside_native: Sequence[Sequence[int]],
    *,
    pool_size: int = BIG_LOTTO_POOL_SIZE,
    draw_size: int = BIG_LOTTO_DRAW_SIZE,
) -> tuple[Ticket, ...]:
    """Deterministic one-number crossovers between K10 tickets and outside-native tickets.

    Enumeration order is ``baseline_k10`` position, then ``outside_native``
    position, then ascending ``x`` (removed), then ascending ``y`` (added);
    duplicate children are dropped at first occurrence. An empty
    ``outside_native`` returns an empty tuple, so the augmented pool
    (``full_union union children``) is then exactly the native full union.
    """

    baseline = tuple(
        _canonical_ticket(ticket, pool_size=pool_size, draw_size=draw_size)
        for ticket in baseline_k10
    )
    outside = tuple(
        _canonical_ticket(ticket, pool_size=pool_size, draw_size=draw_size)
        for ticket in outside_native
    )
    children: dict[Ticket, None] = {}
    for s in baseline:
        s_set = set(s)
        for o in outside:
            o_set = set(o)
            removable = sorted(s_set - o_set)
            addable = sorted(o_set - s_set)
            for x in removable:
                remainder = s_set - {x}
                for y in addable:
                    child = tuple(sorted(remainder | {y}))
                    if len(child) != draw_size or not set(child) <= (s_set | o_set):
                        raise AssertionError(
                            "crossover child violated the six-number parent-only contract"
                        )
                    children.setdefault(child, None)
    return tuple(children.keys())


__all__ = [
    "AUGMENTATION_ID",
    "BIG_LOTTO_DRAW_SIZE",
    "BIG_LOTTO_POOL_SIZE",
    "generate_single_crossover_children",
]
