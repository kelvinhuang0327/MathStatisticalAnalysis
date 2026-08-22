"""Strictly-prior recency conditional-state features for H04-conditional.

Frozen per `docs/research/phase0-h04-conditional-preregistration.md` §3: for
each number in one zone's pool, at each chronological draw position, compute
(a) whether the number was drawn at the immediately preceding position and
(b) the number of draws since it was last drawn (capped). Both features use
only draw positions strictly before the target position -- position 0 has
no strictly-prior draw and is excluded entirely, not merely excluded from
training.
"""

from __future__ import annotations

from dataclasses import dataclass

LAST_SEEN_GAP_CAP = 60


@dataclass(frozen=True, slots=True)
class ZoneObservation:
    draw_index: int
    number: int
    was_in_previous_draw: int
    last_seen_gap: int
    outcome: int


def compute_zone_observations(
    draw_number_sets: list[frozenset[int]], pool_size: int
) -> tuple[ZoneObservation, ...]:
    """`draw_number_sets[i]` holds one zone's drawn numbers at chronological

    position `i` (0-indexed, already sorted ascending in time by the
    caller). Returns one observation per `(draw_index >= 1, number in
    1..pool_size)` pair.
    """

    if pool_size <= 0:
        raise ValueError("pool_size must be positive")
    if not draw_number_sets:
        raise ValueError("draw_number_sets must be non-empty")

    last_seen_at: dict[int, int] = {}
    observations: list[ZoneObservation] = []

    for draw_index, current_set in enumerate(draw_number_sets):
        if draw_index >= 1:
            previous_set = draw_number_sets[draw_index - 1]
            for number in range(1, pool_size + 1):
                was_in_previous = 1 if number in previous_set else 0
                last_seen = last_seen_at.get(number)
                raw_gap = draw_index - last_seen if last_seen is not None else LAST_SEEN_GAP_CAP
                gap = min(raw_gap, LAST_SEEN_GAP_CAP)
                outcome = 1 if number in current_set else 0
                observations.append(
                    ZoneObservation(draw_index, number, was_in_previous, gap, outcome)
                )
        for number in current_set:
            last_seen_at[number] = draw_index

    return tuple(observations)
