"""Three-ticket single-number cycle family with an exact 49/20 residual scorer.

The move replaces one number on each of three tickets and cycles those numbers
in either direction. It is outside N2, which changes at most two tickets.
It is not complete N3 and it is not full three-ticket joint replacement:
most ways to replace three tickets are not single-number cycles.

Raw attempts are C(K, 3) * 6**3 * 2, exactly 492480 at K=20. That is a raw
generation count, not a legal or deduplicated candidate count.

Two exact scorers exist. ``SmallUniverseScorer`` counts 7-sets and is refused
above v = 12. ``TripleResidual`` is a regrouping of the canonical
``evaluate_portfolio`` sum for any pool: with the other K - 3 tickets R fixed,
every candidate ticket lies inside W = Ti | Tj | Tk, so a draw D not already
won by R contributes a value that depends only on D & W and on R's rescue
specials. Draws are therefore aggregated once per triple by the pattern D & W,
and each candidate is scored over at most sum_{m<=6} C(|W|, m) patterns
instead of every draw. The total is identical to the canonical count, not an
estimate. The bounded pilot in this module scores 20 seeded triples only.

This module was ported from the out-of-repository producer
``b649-k20-three-ticket-single-number-cycle-r1/three_ticket_cycle.py``
(sha256 abd94a33…); the generator, dedup and 7-set scorer are unchanged.

Small universes saturate. At v <= 10 every ticket covers every 7-set. At v = 11
a 7-set is uncovered only if every ticket contains its 4-number complement,
and a cycle cannot move a number that every ticket holds, so no cycle strictly
improves. At v = 12 random portfolios, even K = 3, usually cover all 792
7-sets. Non-vacuous toy tests therefore use v = 12 portfolios whose tickets
concentrate on one 5-set; K is generic so they can also use K < 20.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import random
import resource
import subprocess
import time
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from math import comb
from pathlib import Path
from typing import cast

import numpy as np
import numpy.typing as npt

from lottolab.research.b649_official_any_prize_exact import (
    BIG_LOTTO_OUTRIGHT_MATCHES,
    BIG_LOTTO_POOL_SIZE,
    DrawMasks,
    all_main_draw_masks,
    evaluate_portfolio,
)

Ticket = tuple[int, ...]
Portfolio = tuple[Ticket, ...]
Direction = str

TICKET_SIZE = 6
K20 = 20
FORWARD = "forward"
REVERSE = "reverse"
DIRECTIONS = (FORWARD, REVERSE)
FAMILY_NAME = "THREE_TICKET_SINGLE_NUMBER_CYCLE"
K20_RAW_ATTEMPT_CAP = comb(K20, 3) * (TICKET_SIZE**3) * len(DIRECTIONS)
SMALL_UNIVERSE_POOL_MAX = 12
OUTCOME_MULTIPLIER = 7
SCAN_EXHAUSTIVE_FAMILY = "exhaustive_family"
SCAN_PARTIAL = "partial"
SCAN_TOP_L = "top_l"
DECISION_STRICT_FOUND = "STRICT_IMPROVEMENT_FOUND"
DECISION_FAMILY_NO_IMPROVEMENT = "CYCLE_FAMILY_EXHAUSTED_NO_STRICT_IMPROVEMENT"
DECISION_INCOMPLETE = "INCOMPLETE_NO_CLAIM"
DECISION_UNSCORED = "GENERATOR_ONLY_UNSCORED"

if K20_RAW_ATTEMPT_CAP != 492480:
    raise RuntimeError("K20 raw attempt cap drifted from C(20,3)*6**3*2")


class CycleError(ValueError):
    """A portfolio or scan contract was violated."""


def raw_attempt_cap(ticket_count: int) -> int:
    """C(K, 3) * 6**3 * 2 raw attempts. Not a legal or deduplicated count."""

    if ticket_count < 3:
        raise CycleError("a three-ticket cycle needs at least three tickets")
    return comb(ticket_count, 3) * (TICKET_SIZE**3) * len(DIRECTIONS)


def normalize_ticket(ticket: Sequence[int], *, pool_size: int) -> Ticket:
    """Sort one ticket and reject anything that is not a legal 6-subset."""

    if len(ticket) != TICKET_SIZE:
        raise CycleError(f"ticket must contain {TICKET_SIZE} numbers")
    numbers: list[int] = []
    for number in ticket:
        if type(number) is not int:
            raise CycleError("ticket numbers must be ints")
        if not 1 <= number <= pool_size:
            raise CycleError(f"ticket number {number} is outside 1..{pool_size}")
        numbers.append(number)
    if len(set(numbers)) != TICKET_SIZE:
        raise CycleError("ticket numbers must be distinct")
    return tuple(sorted(numbers))


def normalize_portfolio(
    portfolio: Sequence[Sequence[int]],
    *,
    pool_size: int,
    expected_ticket_count: int | None = None,
) -> Portfolio:
    """Canonical set identity: sorted tickets, sorted portfolio, no duplicates."""

    if expected_ticket_count is not None and len(portfolio) != expected_ticket_count:
        raise CycleError(f"portfolio must contain exactly {expected_ticket_count} tickets")
    normalized = [normalize_ticket(ticket, pool_size=pool_size) for ticket in portfolio]
    if len(set(normalized)) != len(normalized):
        raise CycleError("portfolio tickets must be distinct")
    return tuple(sorted(normalized))


def canonical_portfolio_json(portfolio: Sequence[Sequence[int]], *, pool_size: int) -> str:
    normalized = normalize_portfolio(portfolio, pool_size=pool_size)
    return json.dumps([list(ticket) for ticket in normalized], separators=(",", ":"))


def portfolio_sha256(portfolio: Sequence[Sequence[int]], *, pool_size: int) -> str:
    """SHA-256 of the normalized compact JSON. Slot order is not identity."""

    payload = canonical_portfolio_json(portfolio, pool_size=pool_size).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _require_normalized(portfolio: Portfolio, *, pool_size: int) -> Portfolio:
    normalized = normalize_portfolio(portfolio, pool_size=pool_size)
    if tuple(portfolio) != normalized:
        raise CycleError(
            "indices refer to normalize_portfolio(portfolio); pass the canonical portfolio"
        )
    return normalized


def _replace_number(ticket: Ticket, remove: int, add: int) -> Ticket | None:
    """Return the size-6 ticket obtained by swapping ``remove`` for ``add``.

    ``None`` means the image is not a 6-subset (the added number is already
    present). Returning the original ticket means this coordinate did not change.
    """

    if remove == add:
        return ticket
    numbers = set(ticket)
    if remove not in numbers or add in numbers:
        return None
    numbers.remove(remove)
    numbers.add(add)
    if len(numbers) != TICKET_SIZE:
        return None
    return tuple(sorted(numbers))


def cycled_tickets(
    first: Ticket,
    second: Ticket,
    third: Ticket,
    a: int,
    b: int,
    c: int,
    direction: Direction,
) -> tuple[Ticket, Ticket, Ticket] | None:
    """Apply one directed cycle. ``None`` if any image is not a 6-subset.

    Forward, as specified: Ti-a+c, Tj-b+a, Tk-c+b.
    Reverse: Ti-a+b, Tj-b+c, Tk-c+a.
    """

    if direction == FORWARD:
        images = (
            _replace_number(first, a, c),
            _replace_number(second, b, a),
            _replace_number(third, c, b),
        )
    elif direction == REVERSE:
        images = (
            _replace_number(first, a, b),
            _replace_number(second, b, c),
            _replace_number(third, c, a),
        )
    else:
        raise CycleError(f"unknown direction {direction}")
    if any(image is None for image in images):
        return None
    return images  # type: ignore[return-value]


def ticket_set_difference(
    old: Portfolio, new: Portfolio
) -> tuple[tuple[Ticket, ...], tuple[Ticket, ...]]:
    removed = tuple(sorted(set(old) - set(new)))
    added = tuple(sorted(set(new) - set(old)))
    return removed, added


def changes_exactly_three_tickets(old: Portfolio, new: Portfolio) -> bool:
    removed, added = ticket_set_difference(old, new)
    return len(removed) == 3 and len(added) == 3


def emit_cycle(
    portfolio: Portfolio,
    indices: tuple[int, int, int],
    numbers: tuple[int, int, int],
    direction: Direction,
    *,
    pool_size: int,
) -> Portfolio | None:
    """Return the normalized portfolio, or None if this direction degenerates.

    Dropped: illegal 6-subsets, duplicate tickets, an unchanged coordinate,
    the original set, and any set that changes fewer than three tickets.
    One dropped direction does not drop the other direction.
    """

    canonical = _require_normalized(portfolio, pool_size=pool_size)
    return _emit_normalized(canonical, indices, numbers, direction, pool_size=pool_size)


def _emit_normalized(
    canonical: Portfolio,
    indices: tuple[int, int, int],
    numbers: tuple[int, int, int],
    direction: Direction,
    *,
    pool_size: int,
) -> Portfolio | None:
    """``emit_cycle`` for a portfolio the caller has already normalized once."""

    i, j, k = indices
    if len({i, j, k}) != 3 or any(not 0 <= index < len(canonical) for index in indices):
        raise CycleError("cycle indices must be three distinct positions")
    a, b, c = numbers
    images = cycled_tickets(canonical[i], canonical[j], canonical[k], a, b, c, direction)
    if images is None:
        return None
    if any(image == canonical[index] for image, index in zip(images, indices, strict=True)):
        return None
    replaced = list(canonical)
    for index, image in zip(indices, images, strict=True):
        replaced[index] = image
    if len(set(replaced)) != len(replaced):
        return None
    try:
        emitted = normalize_portfolio(
            replaced, pool_size=pool_size, expected_ticket_count=len(canonical)
        )
    except CycleError:
        return None
    if emitted == canonical or not changes_exactly_three_tickets(canonical, emitted):
        return None
    return emitted


@dataclass(frozen=True, slots=True)
class RawCycleSpec:
    indices: tuple[int, int, int]
    numbers: tuple[int, int, int]
    direction: Direction


@dataclass(frozen=True, slots=True)
class EmittedCycle:
    portfolio: Portfolio
    sha256: str
    direction: Direction
    indices: tuple[int, int, int]
    numbers: tuple[int, int, int]
    removed: tuple[Ticket, ...]
    added: tuple[Ticket, ...]

    @property
    def tickets_changed(self) -> int:
        return len(self.removed)


def iter_raw_cycle_specs(portfolio: Portfolio, *, pool_size: int) -> Iterator[RawCycleSpec]:
    """Every single-number cycle attempt: raw_attempt_cap(K), 492480 at K=20.

    Ticket triples are combinations, so each unordered triple is oriented once
    by canonical index order. Both directions are then attempted. This generator
    does not score and does not allocate an incidence matrix.
    """

    canonical = _require_normalized(portfolio, pool_size=pool_size)
    count = len(canonical)
    cap = raw_attempt_cap(count)
    produced = 0
    for i, j, k in itertools.combinations(range(count), 3):
        first, second, third = canonical[i], canonical[j], canonical[k]
        for a in first:
            for b in second:
                for c in third:
                    for direction in DIRECTIONS:
                        if produced >= cap:
                            return
                        produced += 1
                        yield RawCycleSpec((i, j, k), (a, b, c), direction)


def emit_spec(portfolio: Portfolio, spec: RawCycleSpec, *, pool_size: int) -> EmittedCycle | None:
    canonical = _require_normalized(portfolio, pool_size=pool_size)
    return _emit_spec_normalized(canonical, spec, pool_size=pool_size)


def _emit_spec_normalized(
    canonical: Portfolio, spec: RawCycleSpec, *, pool_size: int
) -> EmittedCycle | None:
    emitted = _emit_normalized(
        canonical, spec.indices, spec.numbers, spec.direction, pool_size=pool_size
    )
    if emitted is None:
        return None
    removed, added = ticket_set_difference(canonical, emitted)
    return EmittedCycle(
        portfolio=emitted,
        sha256=portfolio_sha256(emitted, pool_size=pool_size),
        direction=spec.direction,
        indices=spec.indices,
        numbers=spec.numbers,
        removed=removed,
        added=added,
    )


def iter_emitted_cycles(
    portfolio: Portfolio,
    *,
    pool_size: int,
    max_raw_attempts: int | None = None,
) -> Iterator[tuple[int, EmittedCycle]]:
    """Legal, non-degenerate cycles in attempt order. Hashes are not deduped yet."""

    if max_raw_attempts is not None and max_raw_attempts < 0:
        raise CycleError("max_raw_attempts must be non-negative")
    canonical = _require_normalized(portfolio, pool_size=pool_size)
    for attempt_index, spec in enumerate(iter_raw_cycle_specs(canonical, pool_size=pool_size)):
        if max_raw_attempts is not None and attempt_index >= max_raw_attempts:
            return
        emitted = _emit_spec_normalized(canonical, spec, pool_size=pool_size)
        if emitted is not None:
            yield attempt_index, emitted


def deduped_emissions(
    emissions: Iterable[EmittedCycle],
) -> tuple[EmittedCycle, ...]:
    """First occurrence of each normalized portfolio hash wins."""

    seen: set[str] = set()
    unique: list[EmittedCycle] = []
    for emission in emissions:
        if emission.sha256 in seen:
            continue
        seen.add(emission.sha256)
        unique.append(emission)
    return tuple(unique)


def small_universe_start_portfolio(pool_size: int = SMALL_UNIVERSE_POOL_MAX) -> Portfolio:
    """Deterministic K=20 spread of 6-subsets. Not a 1..49 search seed."""

    if not 8 <= pool_size <= SMALL_UNIVERSE_POOL_MAX:
        raise CycleError("small-universe portfolios use 8 <= v <= 12")
    tickets = list(itertools.combinations(range(1, pool_size + 1), TICKET_SIZE))
    stride = len(tickets) // K20
    chosen = [tickets[index * stride] for index in range(K20)]
    return normalize_portfolio(chosen, pool_size=pool_size, expected_ticket_count=K20)


# A v=12 K=20 portfolio drawn (seed 4262) from the 112 tickets holding >= 4 of
# {8..12}, so some 7-sets stay uncovered and the cycle family has strict winners.
SMALL_UNIVERSE_WINNABLE_K20_V12: Portfolio = (
    (1, 2, 8, 9, 10, 12),
    (1, 3, 8, 10, 11, 12),
    (1, 4, 8, 9, 11, 12),
    (1, 4, 9, 10, 11, 12),
    (1, 5, 8, 9, 10, 12),
    (1, 6, 8, 9, 10, 11),
    (1, 6, 8, 9, 10, 12),
    (1, 6, 8, 10, 11, 12),
    (2, 3, 8, 10, 11, 12),
    (2, 5, 8, 9, 10, 12),
    (2, 5, 8, 10, 11, 12),
    (2, 7, 9, 10, 11, 12),
    (3, 4, 9, 10, 11, 12),
    (3, 5, 8, 9, 10, 12),
    (3, 6, 8, 10, 11, 12),
    (4, 6, 8, 9, 10, 12),
    (5, 7, 8, 10, 11, 12),
    (5, 7, 9, 10, 11, 12),
    (6, 7, 8, 10, 11, 12),
    (6, 7, 9, 10, 11, 12),
)


def _reject_large_residual_pool(pool_size: int) -> None:
    if not 8 <= pool_size <= SMALL_UNIVERSE_POOL_MAX:
        raise CycleError(
            "residual 7-set universe is only built for 8 <= v <= 12; "
            "refusing a global 6-subset incidence matrix"
        )


def _number_mask(numbers: Iterable[int]) -> int:
    mask = 0
    for number in numbers:
        mask |= 1 << (number - 1)
    return mask


class SmallUniverseScorer:
    """Exact v <= 12 coverage with one bit per 7-set.

    F(P) = 7 * #{7-sets U : some ticket T has len(T & U) >= 3}. For 6-number
    tickets, a special drawn outside the main draw and outright threshold 3
    this is the canonical OFFICIAL_ANY_PRIZE outcome count: outcome (D, s)
    wins iff some T has len(T & (D | {s})) >= 3, and each 7-set is D | {s} for
    exactly 7 outcomes.
    """

    def __init__(self, pool_size: int) -> None:
        _reject_large_residual_pool(pool_size)
        self.pool_size = pool_size
        self._seven_masks = tuple(
            _number_mask(seven) for seven in itertools.combinations(range(1, pool_size + 1), 7)
        )
        self._cover_cache: dict[Ticket, int] = {}

    @property
    def seven_set_count(self) -> int:
        return len(self._seven_masks)

    def cover(self, ticket: Ticket) -> int:
        cached = self._cover_cache.get(ticket)
        if cached is None:
            bits = _number_mask(ticket)
            cached = 0
            for index, seven in enumerate(self._seven_masks):
                if (bits & seven).bit_count() >= 3:
                    cached |= 1 << index
            self._cover_cache[ticket] = cached
        return cached

    def union_bits(self, tickets: Iterable[Ticket]) -> int:
        union = 0
        for ticket in tickets:
            union |= self.cover(ticket)
        return union

    def covered_seven_sets(self, portfolio: Iterable[Ticket]) -> int:
        """Direct whole-portfolio recompute, independent of any residual."""

        return self.union_bits(portfolio).bit_count()

    def outcome_count(self, portfolio: Iterable[Ticket]) -> int:
        return OUTCOME_MULTIPLIER * self.covered_seven_sets(portfolio)


def inclusion_exclusion_union_bits(first: int, second: int, third: int) -> int:
    """len(B1 | B2 | B3) by inclusion-exclusion on 7-set bitsets."""

    return (
        first.bit_count()
        + second.bit_count()
        + third.bit_count()
        - (first & second).bit_count()
        - (first & third).bit_count()
        - (second & third).bit_count()
        + (first & second & third).bit_count()
    )


def seven_sets(pool_size: int) -> tuple[frozenset[int], ...]:
    """Every 7-subset of 1..v. This is the small-universe outcome atom."""

    _reject_large_residual_pool(pool_size)
    return tuple(
        frozenset(numbers) for numbers in itertools.combinations(range(1, pool_size + 1), 7)
    )


def _covers(ticket: Ticket, seven: frozenset[int]) -> bool:
    return len(seven.intersection(ticket)) >= 3


def coverage_of_ticket(ticket: Ticket, universe: Sequence[frozenset[int]]) -> set[frozenset[int]]:
    return {seven for seven in universe if _covers(ticket, seven)}


def residual_sets(
    portfolio: Portfolio,
    indices: tuple[int, int, int],
    *,
    pool_size: int,
    universe: Sequence[frozenset[int]] | None = None,
    tickets_override: tuple[Ticket, Ticket, Ticket] | None = None,
) -> tuple[set[frozenset[int]], set[frozenset[int]], set[frozenset[int]]]:
    """B_R(t) for three tickets: 7-sets covered by t and by no ticket in R.

    ``R`` is the portfolio with those three positions removed. ``tickets_override``
    scores a candidate image of the same three positions against the same R.
    """

    canonical = _require_normalized(portfolio, pool_size=pool_size)
    _reject_large_residual_pool(pool_size)
    if universe is None:
        universe = seven_sets(pool_size)
    i, j, k = indices
    if tickets_override is None:
        chosen = (canonical[i], canonical[j], canonical[k])
    else:
        chosen = tickets_override
    rest_cover: set[frozenset[int]] = set()
    chosen_positions = set(indices)
    for position, ticket in enumerate(canonical):
        if position in chosen_positions:
            continue
        rest_cover.update(coverage_of_ticket(ticket, universe))
    residuals: list[set[frozenset[int]]] = []
    for ticket in chosen:
        residuals.append(coverage_of_ticket(ticket, universe) - rest_cover)
    return residuals[0], residuals[1], residuals[2]


def inclusion_exclusion_union_size(
    first: set[frozenset[int]],
    second: set[frozenset[int]],
    third: set[frozenset[int]],
) -> int:
    """len(B1 | B2 | B3) = sum len(Bi) - sum len(Bi & Bj) + len(B1 & B2 & B3)."""

    return (
        len(first)
        + len(second)
        + len(third)
        - len(first & second)
        - len(first & third)
        - len(second & third)
        + len(first & second & third)
    )


def sum_upper_bound(
    first: set[frozenset[int]],
    second: set[frozenset[int]],
    third: set[frozenset[int]],
) -> int:
    """Safe upper bound len(B1 | B2 | B3) <= len(B1) + len(B2) + len(B3).

    Each pairwise intersection contains the triple intersection, so
    inclusion-exclusion subtracts at least as much as it adds back.
    """

    return len(first) + len(second) + len(third)


def sum_bound_prunes(
    old_union: int,
    first: set[frozenset[int]],
    second: set[frozenset[int]],
    third: set[frozenset[int]],
) -> bool:
    """True only when the sum bound proves the candidate cannot strictly win.

    Pruning when the sum is merely smaller than some heuristic score is not
    allowed. A candidate whose sum exceeds ``old_union`` must be kept even if
    overlap later makes the exact union fail to improve.
    """

    return sum_upper_bound(first, second, third) <= old_union


def delta_f(old_union: int, new_union: int) -> int:
    """Exact outcome delta for the 6-number ticket / special-outside / threshold-3 event."""

    return OUTCOME_MULTIPLIER * (new_union - old_union)


def residual_union_size(
    portfolio: Portfolio,
    indices: tuple[int, int, int],
    *,
    pool_size: int,
    universe: Sequence[frozenset[int]] | None = None,
    tickets_override: tuple[Ticket, Ticket, Ticket] | None = None,
) -> int:
    residuals = residual_sets(
        portfolio,
        indices,
        pool_size=pool_size,
        universe=universe,
        tickets_override=tickets_override,
    )
    return inclusion_exclusion_union_size(*residuals)


def cycle_residual_delta(
    portfolio: Portfolio,
    emission: EmittedCycle,
    *,
    pool_size: int,
    universe: Sequence[frozenset[int]] | None = None,
) -> tuple[int, int, int]:
    """Return ``(old_union, new_union, delta_f)`` for one emitted cycle."""

    if universe is None:
        universe = seven_sets(pool_size)
    i, j, k = emission.indices
    old_union = residual_union_size(
        portfolio, emission.indices, pool_size=pool_size, universe=universe
    )
    canonical = _require_normalized(portfolio, pool_size=pool_size)
    images = cycled_tickets(
        canonical[i],
        canonical[j],
        canonical[k],
        emission.numbers[0],
        emission.numbers[1],
        emission.numbers[2],
        emission.direction,
    )
    if images is None:
        raise CycleError("emitted cycle no longer maps to legal tickets")
    new_union = residual_union_size(
        portfolio,
        emission.indices,
        pool_size=pool_size,
        universe=universe,
        tickets_override=images,
    )
    return old_union, new_union, delta_f(old_union, new_union)


def official_any_prize_outcome_count(
    portfolio: Sequence[Sequence[int]],
    *,
    pool_size: int,
    draws: DrawMasks | None = None,
) -> int:
    """Read-only call to the canonical scorer. This module does not reimplement it."""

    result = evaluate_portfolio(
        portfolio,
        pool_size=pool_size,
        draw_size=TICKET_SIZE,
        outright_matches=BIG_LOTTO_OUTRIGHT_MATCHES,
        draws=draws,
    )
    return int(result.official_any_prize_outcome_count)


def load_small_universe_draws(pool_size: int) -> DrawMasks:
    _reject_large_residual_pool(pool_size)
    return load_draws(pool_size)


def load_draws(pool_size: int) -> DrawMasks:
    """Complete canonical main-draw space; about 112 MB at v = 49."""

    return all_main_draw_masks(pool_size, TICKET_SIZE)


@dataclass(frozen=True, slots=True)
class StartBinding:
    """A fixed start whose hash and canonical count were both checked."""

    portfolio: Portfolio
    pool_size: int
    sha256: str
    outcome_count: int


def bind_start(
    portfolio: Sequence[Sequence[int]],
    *,
    pool_size: int,
    expected_sha256: str,
    expected_outcome_count: int,
    draws: DrawMasks | None = None,
) -> StartBinding:
    """Refuse a start unless its hash and canonical OFFICIAL_ANY_PRIZE count both match."""

    canonical = normalize_portfolio(portfolio, pool_size=pool_size)
    digest = portfolio_sha256(canonical, pool_size=pool_size)
    if digest != expected_sha256:
        raise CycleError(f"start hash {digest} != expected {expected_sha256}")
    count = official_any_prize_outcome_count(canonical, pool_size=pool_size, draws=draws)
    if count != expected_outcome_count:
        raise CycleError(f"start canonical count {count} != expected {expected_outcome_count}")
    return StartBinding(canonical, pool_size, digest, count)


def canonical_candidate_delta(
    start: StartBinding, candidate: EmittedCycle, *, draws: DrawMasks | None = None
) -> tuple[int, int]:
    """``(candidate canonical count, exact ΔF)`` from the canonical evaluator."""

    count = official_any_prize_outcome_count(
        candidate.portfolio, pool_size=start.pool_size, draws=draws
    )
    return count, count - start.outcome_count


@dataclass(frozen=True, slots=True)
class ScanReport:
    """Search status for this cycle family only.

    ``exhaustive_no_improvement`` can be true only for a finished, fully scored
    enumeration of this family (safe sum-bound pruning counts as scored).
    Partial, top-L and unscored reports cannot set it. No report proves that
    full N3, or full three-ticket joint replacement, has no strict gain.
    """

    family_name: str
    is_complete_n3: bool
    is_full_three_ticket_joint_replacement: bool
    scan_mode: str
    heuristic_restriction: str | None
    ticket_count: int
    raw_attempt_cap: int
    raw_attempts_executed: int
    legal_emissions: int
    unique_legal_portfolios: int
    sum_bound_pruning: bool
    pruned_by_sum_bound: int
    scored_candidates: int
    strict_improvements_seen: int | None
    best_delta_f: int | None
    best_candidate: EmittedCycle | None
    strict_winners: tuple[tuple[str, int], ...]
    exhaustive_no_improvement: bool
    proves_full_n3_no_gain: bool
    decision: str

    def __post_init__(self) -> None:
        if self.family_name != FAMILY_NAME:
            raise CycleError("family_name is the single-number cycle, not N3")
        if self.is_complete_n3 or self.is_full_three_ticket_joint_replacement:
            raise CycleError(
                "this family must not be labeled complete N3 or full joint replacement"
            )
        if self.proves_full_n3_no_gain:
            raise CycleError("a cycle-family scan never proves that full N3 has no gain")
        if self.scan_mode not in {SCAN_EXHAUSTIVE_FAMILY, SCAN_PARTIAL, SCAN_TOP_L}:
            raise CycleError(f"unknown scan mode {self.scan_mode}")
        if self.raw_attempt_cap != raw_attempt_cap(self.ticket_count):
            raise CycleError("raw_attempt_cap must be C(K,3)*6**3*2 for this K")
        if not 0 <= self.raw_attempts_executed <= self.raw_attempt_cap:
            raise CycleError("executed raw attempts must lie within the family cap")
        if not self.unique_legal_portfolios <= self.legal_emissions <= self.raw_attempts_executed:
            raise CycleError("unique <= legal <= executed accounting violated")
        if self.pruned_by_sum_bound + self.scored_candidates > self.unique_legal_portfolios:
            raise CycleError("pruned + scored cannot exceed the unique legal candidates")
        if self.pruned_by_sum_bound and not self.sum_bound_pruning:
            raise CycleError("pruned candidates reported without sum-bound pruning")
        if self.scan_mode == SCAN_EXHAUSTIVE_FAMILY:
            if self.heuristic_restriction:
                raise CycleError("exhaustive family report cannot also be a heuristic restriction")
        elif not self.heuristic_restriction:
            raise CycleError("partial or top-L scan must be labeled a heuristic restriction")
        if self.strict_improvements_seen is None:
            if self.strict_winners or self.best_delta_f is not None or self.scored_candidates:
                raise CycleError("an unscored report cannot carry scores")
        elif self.strict_improvements_seen != len(self.strict_winners):
            raise CycleError("strict_improvements_seen must equal the listed winners")
        if self.decision != self.expected_decision():
            raise CycleError(f"decision {self.decision} contradicts the scan accounting")
        if self.exhaustive_no_improvement != (self.decision == DECISION_FAMILY_NO_IMPROVEMENT):
            raise CycleError("exhaustive_no_improvement must match the decision")

    def expected_decision(self) -> str:
        if self.strict_improvements_seen is None:
            return DECISION_UNSCORED
        if self.strict_improvements_seen > 0:
            return DECISION_STRICT_FOUND
        complete = (
            self.scan_mode == SCAN_EXHAUSTIVE_FAMILY
            and self.raw_attempts_executed == self.raw_attempt_cap
            and self.pruned_by_sum_bound + self.scored_candidates == self.unique_legal_portfolios
        )
        return DECISION_FAMILY_NO_IMPROVEMENT if complete else DECISION_INCOMPLETE


def scan_cycle_family(
    portfolio: Portfolio,
    *,
    pool_size: int,
    mode: str,
    max_raw_attempts: int | None = None,
    top_l: int | None = None,
    prune_with_sum_bound: bool = False,
) -> ScanReport:
    """Scan this cycle family and score it exactly when v <= 12.

    ``exhaustive_family`` walks every raw attempt. ``partial`` stops at a raw
    budget strictly below the cap. ``top_l`` keeps the L best candidates by
    the residual sum upper bound, which is a heuristic restriction and not an
    exact ranking. ``prune_with_sum_bound`` skips a candidate only when
    |B1|+|B2|+|B3| <= old residual union, which proves it cannot strictly win.
    Above v = 12 nothing is scored here; use the canonical evaluator.
    """

    canonical = _require_normalized(portfolio, pool_size=pool_size)
    cap = raw_attempt_cap(len(canonical))
    restriction: str | None
    if mode == SCAN_EXHAUSTIVE_FAMILY:
        if max_raw_attempts is not None or top_l is not None:
            raise CycleError("exhaustive mode takes no raw budget and no top-L")
        budget = cap
        restriction = None
    elif mode == SCAN_PARTIAL:
        if max_raw_attempts is None or not 0 <= max_raw_attempts < cap:
            raise CycleError("partial mode requires a raw budget strictly below the family cap")
        budget = max_raw_attempts
        restriction = (
            f"partial raw-attempt budget {budget} of {cap}; "
            "not a proof that this family or full N3 has no strict gain"
        )
    elif mode == SCAN_TOP_L:
        if top_l is None or top_l < 1:
            raise CycleError("top-L mode requires top_l >= 1")
        if prune_with_sum_bound:
            raise CycleError("top-L already ranks by the sum bound; do not also prune")
        budget = cap if max_raw_attempts is None else max_raw_attempts
        if not 0 <= budget <= cap:
            raise CycleError("raw budget must lie within the family cap")
        restriction = (
            f"top-{top_l} shortlist by residual sum upper bound inside {budget} raw attempts; "
            "heuristic restriction, not an exact ranking and not a proof that full N3 "
            "has no strict gain"
        )
    else:
        raise CycleError(f"unknown scan mode {mode}")

    scorer: SmallUniverseScorer | None = None
    if pool_size <= SMALL_UNIVERSE_POOL_MAX:
        scorer = SmallUniverseScorer(pool_size)
    elif mode == SCAN_TOP_L:
        raise CycleError("top-L residual ranking is refused above v=12")

    executed = 0
    legal = 0
    seen: set[str] = set()
    pruned = 0
    scored: list[tuple[int, EmittedCycle]] = []
    shortlist: list[tuple[int, str, EmittedCycle, int, tuple[int, int, int]]] = []
    triple: tuple[int, int, int] | None = None
    rest = 0
    old_union = 0
    for spec in iter_raw_cycle_specs(canonical, pool_size=pool_size):
        if executed >= budget:
            break
        executed += 1
        emission = _emit_spec_normalized(canonical, spec, pool_size=pool_size)
        if emission is None:
            continue
        legal += 1
        if emission.sha256 in seen:
            continue
        seen.add(emission.sha256)
        if scorer is None:
            continue
        if spec.indices != triple:
            triple = spec.indices
            rest = scorer.union_bits(
                ticket for position, ticket in enumerate(canonical) if position not in triple
            )
            old_bits = scorer.union_bits(canonical[index] for index in triple) & ~rest
            old_union = old_bits.bit_count()
        first, second, third = (scorer.cover(ticket) & ~rest for ticket in emission.added)
        bound = first.bit_count() + second.bit_count() + third.bit_count()
        if mode == SCAN_TOP_L:
            shortlist.append((bound, emission.sha256, emission, old_union, (first, second, third)))
            continue
        if prune_with_sum_bound and bound <= old_union:
            pruned += 1
            continue
        new_union = inclusion_exclusion_union_bits(first, second, third)
        scored.append((delta_f(old_union, new_union), emission))

    if mode == SCAN_TOP_L:
        shortlist.sort(key=lambda item: (-item[0], item[1]))
        for _bound, _digest, emission, base, residuals in shortlist[:top_l]:
            scored.append((delta_f(base, inclusion_exclusion_union_bits(*residuals)), emission))

    strict_seen: int | None = None
    best_delta: int | None = None
    best_candidate: EmittedCycle | None = None
    winners: tuple[tuple[str, int], ...] = ()
    if scorer is not None:
        ordered = sorted(scored, key=lambda item: (-item[0], item[1].sha256))
        winners = tuple((emission.sha256, change) for change, emission in ordered if change > 0)
        strict_seen = len(winners)
        if ordered:
            best_delta, best_candidate = ordered[0]

    if strict_seen is None:
        decision = DECISION_UNSCORED
    elif strict_seen:
        decision = DECISION_STRICT_FOUND
    elif mode == SCAN_EXHAUSTIVE_FAMILY:
        decision = DECISION_FAMILY_NO_IMPROVEMENT
    else:
        decision = DECISION_INCOMPLETE
    # ScanReport re-derives the decision from the accounting and refuses a mismatch.
    return ScanReport(
        family_name=FAMILY_NAME,
        is_complete_n3=False,
        is_full_three_ticket_joint_replacement=False,
        scan_mode=mode,
        heuristic_restriction=restriction,
        ticket_count=len(canonical),
        raw_attempt_cap=cap,
        raw_attempts_executed=executed,
        legal_emissions=legal,
        unique_legal_portfolios=len(seen),
        sum_bound_pruning=prune_with_sum_bound,
        pruned_by_sum_bound=pruned,
        scored_candidates=len(scored),
        strict_improvements_seen=strict_seen,
        best_delta_f=best_delta,
        best_candidate=best_candidate,
        strict_winners=winners,
        exhaustive_no_improvement=decision == DECISION_FAMILY_NO_IMPROVEMENT,
        proves_full_n3_no_gain=False,
        decision=decision,
    )


def k20_generator_portfolio() -> Portfolio:
    """First 20 lexicographic 6-subsets of 1..49. Generator fixture only."""

    tickets = list(itertools.islice(itertools.combinations(range(1, 50), TICKET_SIZE), K20))
    return normalize_portfolio(tickets, pool_size=49, expected_ticket_count=K20)


def count_raw_cycle_specs(portfolio: Portfolio, *, pool_size: int) -> int:
    return sum(1 for _spec in iter_raw_cycle_specs(portfolio, pool_size=pool_size))


def first_legal_cycle(portfolio: Portfolio, *, pool_size: int) -> EmittedCycle:
    for _index, emission in iter_emitted_cycles(portfolio, pool_size=pool_size):
        return emission
    raise CycleError("no legal three-ticket single-number cycle in this portfolio")


# --- exact residual scorer (any pool) ------------------------------------------------

type PatternArray = npt.NDArray[np.uint32]
type CountArray = npt.NDArray[np.int64]

TRIPLE_RAW_ATTEMPTS = TICKET_SIZE**3 * len(DIRECTIONS)


@dataclass(frozen=True, slots=True)
class TripleResidual:
    """Canonical-exact count of R + {X, Y, Z} for X, Y, Z inside W = Ti | Tj | Tk.

    This regroups ``evaluate_portfolio``. A draw won outright by R always
    yields ``special_count`` winning specials. A draw D not won by R yields
    ``special_count`` if a new ticket reaches ``outright_matches`` in D, and
    otherwise ``len(rescue_R(D) | M)`` specials, where ``rescue_R(D)`` is R's
    rescue set minus D and M is the union of ``T - D`` over new tickets with
    ``outright_matches - 1`` hits. M lies inside W - D, so that size equals
    ``|rescue_R(D)| + sum_{w in M} [w not in rescue_R(D)]``. Hence, per pattern
    q = D & W, only the number of such draws, their summed ``|rescue_R(D)|``
    and, per number w in W, how many of them have w in ``rescue_R(D)`` are
    needed.
    """

    indices: tuple[int, int, int]
    pool_size: int
    special_count: int
    outright_matches: int
    universe_numbers: tuple[int, ...]
    rest_won_draws: int
    patterns: PatternArray
    pattern_draws: CountArray
    pattern_rescue: CountArray
    pattern_number_rescue: CountArray
    bit_of: dict[int, int] = field(repr=False, compare=False)
    shifts: PatternArray = field(repr=False, compare=False)

    @property
    def pattern_count(self) -> int:
        return int(self.patterns.size)

    def compress(self, ticket: Sequence[int]) -> int:
        """Ticket as a bitmask over W; refuses any number outside W."""

        mask = 0
        for number in ticket:
            bit = self.bit_of.get(number)
            if bit is None:
                raise CycleError(f"number {number} lies outside the triple universe W")
            mask |= 1 << bit
        return mask

    def outcome_count(self, tickets: Sequence[Sequence[int]]) -> int:
        """Exact canonical OFFICIAL_ANY_PRIZE count of R + ``tickets``."""

        if len(tickets) != 3:
            raise CycleError("a triple residual scores exactly three replacement tickets")
        patterns = self.patterns
        won = np.zeros(patterns.size, dtype=np.bool_)
        rescue = np.zeros(patterns.size, dtype=np.uint32)
        zero = np.uint32(0)
        for ticket in tickets:
            mask = np.uint32(self.compress(ticket))
            hits = np.bitwise_count(patterns & mask)
            won |= hits >= self.outright_matches
            rescue |= np.where(hits == self.outright_matches - 1, mask & ~patterns, zero)
        open_rows = ~won
        open_rescue = rescue[open_rows]
        carried = ((open_rescue[:, None] >> self.shifts) & np.uint32(1)).astype(np.bool_)
        already = np.where(carried, self.pattern_number_rescue[open_rows], 0).sum(axis=1)
        added = (
            np.bitwise_count(open_rescue).astype(np.int64) * self.pattern_draws[open_rows] - already
        )
        won_draws = self.rest_won_draws + int(self.pattern_draws[won].sum())
        return (
            self.special_count * won_draws
            + int(self.pattern_rescue[open_rows].sum())
            + int(added.sum())
        )


def build_triple_residual(
    portfolio: Portfolio,
    indices: tuple[int, int, int],
    *,
    pool_size: int,
    draws: DrawMasks,
    chunk_size: int = 1 << 21,
) -> TripleResidual:
    """Aggregate every draw not won by R = portfolio minus ``indices`` by D & W."""

    canonical = _require_normalized(portfolio, pool_size=pool_size)
    if len(set(indices)) != 3 or any(not 0 <= index < len(canonical) for index in indices):
        raise CycleError("cycle indices must be three distinct positions")
    if draws.size != comb(pool_size, TICKET_SIZE):
        raise CycleError("draws must be the complete main-draw space")
    chosen = set(indices)
    universe = tuple(sorted({number for index in indices for number in canonical[index]}))
    width = len(universe)
    size = 1 << width
    outright = BIG_LOTTO_OUTRIGHT_MATCHES
    rest_masks = [
        np.uint64(_number_mask(ticket))
        for position, ticket in enumerate(canonical)
        if position not in chosen
    ]
    shifts64 = [np.uint64(number - 1) for number in universe]
    one = np.uint64(1)
    zero = np.uint64(0)
    draw_counts = np.zeros(size, dtype=np.int64)
    rescue_counts = np.zeros(size, dtype=np.int64)
    number_counts = np.zeros((width, size), dtype=np.int64)
    rest_won = 0
    for start in range(0, draws.size, chunk_size):
        chunk = draws[start : start + chunk_size]
        won = np.zeros(chunk.size, dtype=np.bool_)
        rescue = np.zeros(chunk.size, dtype=np.uint64)
        for mask in rest_masks:
            hits = np.bitwise_count(chunk & mask)
            won |= hits >= outright
            rescue |= np.where(hits == outright - 1, mask, zero)
        rest_won += int(np.count_nonzero(won))
        open_draws = chunk[~won]
        open_rescue = rescue[~won] & ~open_draws
        pattern = np.zeros(open_draws.size, dtype=np.int64)
        for bit, shift in enumerate(shifts64):
            pattern |= ((open_draws >> shift) & one).astype(np.int64) << bit
        draw_counts += np.bincount(pattern, minlength=size)
        weighted = np.bincount(
            pattern, weights=np.bitwise_count(open_rescue).astype(np.float64), minlength=size
        )
        exact = weighted.astype(np.int64)
        if not np.array_equal(exact, weighted):
            raise CycleError("rescue aggregation lost integer exactness")
        rescue_counts += exact
        for bit, shift in enumerate(shifts64):
            carries = ((open_rescue >> shift) & one).astype(np.bool_)
            number_counts[bit] += np.bincount(pattern[carries], minlength=size)
    if rest_won + int(draw_counts.sum()) != draws.size:
        raise CycleError("residual draw accounting does not cover the draw space")
    present = np.flatnonzero(draw_counts)
    return TripleResidual(
        indices=indices,
        pool_size=pool_size,
        special_count=pool_size - TICKET_SIZE,
        outright_matches=outright,
        universe_numbers=universe,
        rest_won_draws=rest_won,
        patterns=present.astype(np.uint32),
        pattern_draws=draw_counts[present],
        pattern_rescue=rescue_counts[present],
        pattern_number_rescue=np.ascontiguousarray(number_counts[:, present].T),
        bit_of={number: bit for bit, number in enumerate(universe)},
        shifts=np.arange(width, dtype=np.uint32),
    )


def iter_triple_cycle_specs(
    portfolio: Portfolio, indices: tuple[int, int, int], *, pool_size: int
) -> Iterator[RawCycleSpec]:
    """The 6**3 * 2 attempts of one triple, in ``iter_raw_cycle_specs`` order."""

    canonical = _require_normalized(portfolio, pool_size=pool_size)
    i, j, k = indices
    if not 0 <= i < j < k < len(canonical):
        raise CycleError("a triple is oriented by increasing canonical index")
    for a in canonical[i]:
        for b in canonical[j]:
            for c in canonical[k]:
                for direction in DIRECTIONS:
                    yield RawCycleSpec(indices, (a, b, c), direction)


# --- bounded 49/20 pilot against the pinned v6 authority ------------------------------

TASK_ID = "B649_K20_THREE_TICKET_RESIDUAL_SCORER_PILOT_R1"
SCIENTIFIC_CLAIM_SCOPE = "BOUNDED_20_TRIPLE_THREE_TICKET_SINGLE_NUMBER_CYCLE_PILOT"
STARTING_SEALED_GEOMETRY_METHOD_VERSION = "6.0.0"
STARTING_COUNT = 313_239_647
STARTING_EXACT_PROBABILITY = "44748521/85900584"
STARTING_PORTFOLIO_SHA256 = "0c52a1f0bed90cd47d08bb031b13c9bf693317493f88e45da8e087bd4a0ab65b"
STARTING_DONOR_ARTIFACT = (
    "docs/research/matrix-native-results/b649-k20-two-ticket-joint-replacement-incumbent-r1.json"
)
STARTING_DONOR_SHA256 = "14f070a764a48a09007e18db212d491867a7c8dc59e775115391a02c8840f632"
TOTAL_OUTCOMES = comb(BIG_LOTTO_POOL_SIZE, TICKET_SIZE) * (BIG_LOTTO_POOL_SIZE - TICKET_SIZE)
PILOT_SEED = 20260929
PILOT_TRIPLE_COUNT = 20
PILOT_RAW_ATTEMPT_CEILING = PILOT_TRIPLE_COUNT * TRIPLE_RAW_ATTEMPTS
PARITY_SEED = PILOT_SEED
PARITY_PER_TRIPLE = 3
PARITY_MIN_SAMPLE = 50
RESULT_PATH = (
    "docs/research/matrix-native-results/b649-k20-three-ticket-residual-pilot-r1-result.json"
)
RUNTIME_DIR = ".task-data/B649_K20_THREE_TICKET_RESIDUAL_SCORER_PILOT_R1"
PRODUCER_ROOT = "/Users/kelvin/VibeCoding-WorkSpace/b649-k20-three-ticket-single-number-cycle-r1"
PRODUCER_SOURCE_SHA256 = "abd94a335490ec3970b637abbe84ac86c479dd8b41a560359008e132cb799cc5"
PRODUCER_TEST_SHA256 = "7c5714c41496cabd0ab9de0850a108a3349ec16cc41b445c9a2e5ae3164e44f0"
PRODUCER_RESULT_SHA256 = "f685ab4276fec48d9d96082f3deb94dfbc86d5c5cca97225c437d428281ef138"

if PILOT_RAW_ATTEMPT_CEILING != 8640 or TOTAL_OUTCOMES != 601_304_088:
    raise RuntimeError("pilot ceiling or outcome total drifted")


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    emission: EmittedCycle
    outcome_count: int


def select_pilot_triples(
    ticket_count: int = K20, *, seed: int = PILOT_SEED, count: int = PILOT_TRIPLE_COUNT
) -> tuple[tuple[int, int, int], ...]:
    """``count`` distinct index triples sampled once from all C(K, 3), in sampled order."""

    population = [(i, j, k) for i, j, k in itertools.combinations(range(ticket_count), 3)]
    return tuple(random.Random(seed).sample(population, count))


def is_better(candidate: ScoredCandidate, incumbent: ScoredCandidate | None) -> bool:
    """Higher exact count wins; equal counts go to the lower normalized portfolio sha256."""

    if incumbent is None:
        return True
    if candidate.outcome_count != incumbent.outcome_count:
        return candidate.outcome_count > incumbent.outcome_count
    return candidate.emission.sha256 < incumbent.emission.sha256


def _require_ticket_rows(value: object) -> list[list[int]]:
    if not isinstance(value, list):
        raise CycleError("donor TICKETS must be a list")
    rows: list[list[int]] = []
    for row in cast(list[object], value):
        if not isinstance(row, list):
            raise CycleError("donor ticket rows must be lists")
        numbers = [n for n in cast(list[object], row) if type(n) is int]
        if len(numbers) != len(cast(list[object], row)):
            raise CycleError("donor ticket rows must be integer lists")
        rows.append(numbers)
    return rows


def load_v6_authority(repo_root: Path, *, draws: DrawMasks) -> StartBinding:
    """Reproduce the pinned v6 K20 count and identity with the canonical evaluator."""

    raw = (repo_root / STARTING_DONOR_ARTIFACT).read_bytes()
    if hashlib.sha256(raw).hexdigest() != STARTING_DONOR_SHA256:
        raise CycleError("v6 donor artifact bytes do not match the pinned sha256")
    payload: object = json.loads(raw)
    if not isinstance(payload, dict):
        raise CycleError("v6 donor artifact must be a JSON object")
    fields = cast(dict[str, object], payload)
    if fields.get("PORTFOLIO_SHA256") != STARTING_PORTFOLIO_SHA256:
        raise CycleError("v6 donor artifact names a different portfolio")
    if fields.get("WINNING_OUTCOMES") != STARTING_COUNT:
        raise CycleError("v6 donor artifact names a different count")
    start = bind_start(
        _require_ticket_rows(fields.get("TICKETS")),
        pool_size=BIG_LOTTO_POOL_SIZE,
        expected_sha256=STARTING_PORTFOLIO_SHA256,
        expected_outcome_count=STARTING_COUNT,
        draws=draws,
    )
    if len(start.portfolio) != K20:
        raise CycleError("v6 authority is not a K=20 portfolio")
    if str(Fraction(start.outcome_count, TOTAL_OUTCOMES)) != STARTING_EXACT_PROBABILITY:
        raise CycleError("v6 exact probability does not reproduce")
    return start


def _emission_json(emission: EmittedCycle) -> dict[str, object]:
    return {
        "SHA256": emission.sha256,
        "INDICES": list(emission.indices),
        "NUMBERS": list(emission.numbers),
        "DIRECTION": emission.direction,
        "REMOVED": [list(ticket) for ticket in emission.removed],
        "ADDED": [list(ticket) for ticket in emission.added],
    }


def _peak_rss_bytes() -> int:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak) if os.uname().sysname == "Darwin" else int(peak) * 1024


def _git_identity(repo_root: Path) -> dict[str, str]:
    def rev(expression: str) -> str:
        return subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", expression],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    return {"RUN_HEAD": rev("HEAD"), "RUN_TREE": rev("HEAD^{tree}")}


def _write_json_atomically(path: Path, payload: dict[str, object]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    staging = path.with_name(path.name + ".tmp")
    staging.write_bytes(encoded)
    os.replace(staging, path)
    return hashlib.sha256(encoded).hexdigest()


def run_parity(
    start: StartBinding,
    residuals: dict[tuple[int, int, int], TripleResidual],
    triples: Sequence[tuple[int, int, int]],
    *,
    draws: DrawMasks,
    per_triple: int = PARITY_PER_TRIPLE,
) -> dict[str, object]:
    """Residual count vs full ``evaluate_portfolio`` on seeded legal candidates."""

    start_checks: list[dict[str, object]] = []
    samples: list[dict[str, object]] = []
    for triple in triples:
        residual = residuals[triple]
        origin = tuple(start.portfolio[index] for index in triple)
        origin_count = residual.outcome_count(origin)
        start_checks.append(
            {
                "INDICES": list(triple),
                "RESIDUAL_COUNT": origin_count,
                "MATCH": origin_count == start.outcome_count,
            }
        )
        legal = deduped_emissions(
            emission
            for spec in iter_triple_cycle_specs(start.portfolio, triple, pool_size=start.pool_size)
            if (emission := _emit_spec_normalized(start.portfolio, spec, pool_size=start.pool_size))
            is not None
        )
        rng = random.Random(f"parity:{PARITY_SEED}:{triple[0]}:{triple[1]}:{triple[2]}")
        for emission in rng.sample(list(legal), min(per_triple, len(legal))):
            residual_count = residual.outcome_count(emission.added)
            canonical_count = official_any_prize_outcome_count(
                emission.portfolio, pool_size=start.pool_size, draws=draws
            )
            record = _emission_json(emission)
            record.update(
                RESIDUAL_COUNT=residual_count,
                CANONICAL_COUNT=canonical_count,
                RESIDUAL_DELTA=residual_count - start.outcome_count,
                CANONICAL_DELTA=canonical_count - start.outcome_count,
                MATCH=residual_count == canonical_count,
            )
            samples.append(record)
    return {
        "SEED": PARITY_SEED,
        "STREAM": "random.Random('parity:<seed>:<i>:<j>:<k>').sample(unique legal, 3)",
        "TRIPLES": [list(triple) for triple in triples],
        "PER_TRIPLE": per_triple,
        "SAMPLE_COUNT": len(samples),
        "MISMATCHES": sum(1 for record in samples if not record["MATCH"]),
        "START_REPRODUCTION_CHECKS": len(start_checks),
        "START_REPRODUCTION_MISMATCHES": sum(1 for check in start_checks if not check["MATCH"]),
        "START_REPRODUCTION": start_checks,
        "SAMPLES": samples,
    }


def run_bounded_pilot(
    repo_root: Path, *, result_path: Path, runtime_dir: Path
) -> dict[str, object]:
    """Authority reproduction, >=50-candidate parity, then the 20-triple exact pilot."""

    started = time.perf_counter()
    source = Path(__file__).resolve()
    draws = load_draws(BIG_LOTTO_POOL_SIZE)
    start = load_v6_authority(repo_root, draws=draws)
    authority_seconds = time.perf_counter() - started
    triples = select_pilot_triples()
    if len(set(triples)) != PILOT_TRIPLE_COUNT:
        raise CycleError("pilot triples are not distinct")

    residuals: dict[tuple[int, int, int], TripleResidual] = {}
    precompute: dict[tuple[int, int, int], float] = {}
    for triple in triples:
        began = time.perf_counter()
        residuals[triple] = build_triple_residual(
            start.portfolio, triple, pool_size=start.pool_size, draws=draws
        )
        precompute[triple] = time.perf_counter() - began
    began = time.perf_counter()
    parity = run_parity(start, residuals, triples, draws=draws)
    parity_seconds = time.perf_counter() - began

    record: dict[str, object] = {
        "TASK_ID": TASK_ID,
        "FAMILY_NAME": FAMILY_NAME,
        "SCIENTIFIC_CLAIM_SCOPE": SCIENTIFIC_CLAIM_SCOPE,
        "SOURCE_MODULE_PATH": str(source.relative_to(repo_root.resolve())),
        "SOURCE_MODULE_SHA256": hashlib.sha256(source.read_bytes()).hexdigest(),
        **_git_identity(repo_root),
        "PRODUCER": {
            "ROOT": PRODUCER_ROOT,
            "SOURCE_SHA256": PRODUCER_SOURCE_SHA256,
            "TEST_SHA256": PRODUCER_TEST_SHA256,
            "RESULT_SHA256": PRODUCER_RESULT_SHA256,
        },
        "STARTING_AUTHORITY": {
            "SEALED_GEOMETRY_METHOD_VERSION": STARTING_SEALED_GEOMETRY_METHOD_VERSION,
            "DONOR_ARTIFACT": STARTING_DONOR_ARTIFACT,
            "DONOR_SHA256": STARTING_DONOR_SHA256,
            "PORTFOLIO_SHA256": start.sha256,
            "CANONICAL_COUNT": start.outcome_count,
            "EXACT_PROBABILITY": str(Fraction(start.outcome_count, TOTAL_OUTCOMES)),
            "TOTAL_OUTCOMES": TOTAL_OUTCOMES,
            "PORTFOLIO": [list(ticket) for ticket in start.portfolio],
            "CANONICAL_REPRODUCTION": "PASS",
        },
        "PARITY_49_20": parity,
        "GAIN_VS_PROTECTED_LANE_3": "NOT_EVALUATED",
        "PROTECTED_LANE_3_TOUCHED": "NO",
        "FULL_49_20_FAMILY_STARTED": "NO",
        "NOT_CLAIMED": [
            "complete N3",
            "complete three-ticket joint replacement",
            "N3 or cycle-family local optimality",
            "full cycle-family no-improvement",
            "overall current-best K20",
            "gain versus protected Lane 3",
        ],
    }
    parity_clean = parity["MISMATCHES"] == 0 and parity["START_REPRODUCTION_MISMATCHES"] == 0
    enough = isinstance(parity["SAMPLE_COUNT"], int) and parity["SAMPLE_COUNT"] >= PARITY_MIN_SAMPLE
    if not (parity_clean and enough):
        record.update(
            PILOT_STATUS="NOT_RUN_PARITY_UNRESOLVED",
            PILOT_GAIN_VS_V6="NOT_EVALUATED",
            NEW_B649_GAIN_ESTABLISHED="NO",
        )
        _write_json_atomically(result_path, record)
        return record

    runtime_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = runtime_dir / "pilot-candidates.jsonl"
    raw = legal = unique = scored = duplicates = improvements = 0
    seen: set[str] = set()
    best: ScoredCandidate | None = None
    ties: list[ScoredCandidate] = []
    per_triple: list[dict[str, object]] = []
    began = time.perf_counter()
    with ledger_path.open("w", encoding="utf-8") as ledger:
        for triple in triples:
            residual = residuals[triple]
            t_raw = t_legal = t_unique = 0
            t_best: int | None = None
            for spec in iter_triple_cycle_specs(start.portfolio, triple, pool_size=start.pool_size):
                raw += 1
                t_raw += 1
                emission = _emit_spec_normalized(start.portfolio, spec, pool_size=start.pool_size)
                if emission is None:
                    continue
                legal += 1
                t_legal += 1
                if emission.sha256 in seen:
                    duplicates += 1
                    continue
                seen.add(emission.sha256)
                unique += 1
                t_unique += 1
                candidate = ScoredCandidate(emission, residual.outcome_count(emission.added))
                scored += 1
                if candidate.outcome_count > start.outcome_count:
                    improvements += 1
                t_best = (
                    candidate.outcome_count
                    if t_best is None
                    else max(t_best, candidate.outcome_count)
                )
                if best is None or candidate.outcome_count > best.outcome_count:
                    ties = [candidate]
                elif candidate.outcome_count == best.outcome_count:
                    ties.append(candidate)
                if is_better(candidate, best):
                    best = candidate
                ledger.write(
                    json.dumps(
                        {
                            "SHA256": emission.sha256,
                            "INDICES": list(triple),
                            "NUMBERS": list(spec.numbers),
                            "DIRECTION": spec.direction,
                            "COUNT": candidate.outcome_count,
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
            per_triple.append(
                {
                    "INDICES": list(triple),
                    "TICKETS": [list(start.portfolio[index]) for index in triple],
                    "UNIVERSE_SIZE": len(residual.universe_numbers),
                    "PATTERNS": residual.pattern_count,
                    "PRECOMPUTE_SECONDS": round(precompute[triple], 3),
                    "RAW": t_raw,
                    "LEGAL": t_legal,
                    "UNIQUE": t_unique,
                    "BEST_COUNT": t_best,
                }
            )
    scoring_seconds = time.perf_counter() - began
    if raw > PILOT_RAW_ATTEMPT_CEILING or best is None:
        raise CycleError("pilot exceeded its raw ceiling or scored nothing")

    recount_targets = ties if best.outcome_count > start.outcome_count else [best]
    recounts: list[dict[str, object]] = []
    for candidate in sorted(recount_targets, key=lambda item: item.emission.sha256):
        canonical_count = official_any_prize_outcome_count(
            candidate.emission.portfolio, pool_size=start.pool_size, draws=draws
        )
        recounts.append(
            {
                "SHA256": candidate.emission.sha256,
                "RESIDUAL_COUNT": candidate.outcome_count,
                "CANONICAL_COUNT": canonical_count,
                "MATCH": canonical_count == candidate.outcome_count,
            }
        )
    recount_ok = all(entry["MATCH"] for entry in recounts)
    gain = best.outcome_count > start.outcome_count and recount_ok
    precompute_seconds = sum(precompute.values())
    pilot_seconds = precompute_seconds + scoring_seconds
    best_json = _emission_json(best.emission)
    best_json.update(
        PORTFOLIO=[list(ticket) for ticket in best.emission.portfolio],
        COUNT=best.outcome_count,
        EXACT_PROBABILITY=str(Fraction(best.outcome_count, TOTAL_OUTCOMES)),
        DELTA_VS_V6=best.outcome_count - start.outcome_count,
    )
    record.update(
        PILOT_STATUS="COMPLETE",
        PILOT={
            "SEED": PILOT_SEED,
            "SELECTION": "random.Random(seed).sample(all C(20,3) index triples, 20), sampled order",
            "TRIPLE_SAMPLE_COUNT": len(triples),
            "TRIPLES": per_triple,
            "RAW_ATTEMPT_CEILING": PILOT_RAW_ATTEMPT_CEILING,
            "RAW_ATTEMPTS": raw,
            "LEGAL": legal,
            "DEDUPLICATED": unique,
            "DUPLICATES": duplicates,
            "PRUNING": "NONE",
            "PRUNED": 0,
            "TOP_L": "NONE",
            "EXACT_SCORED": scored,
            "STRICT_IMPROVEMENTS_VS_V6": improvements,
            "BEST": best_json,
            "TIES_AT_BEST_COUNT": len(ties),
            "TIE_BREAK": "max exact count, then lowest normalized portfolio sha256",
            "CANONICAL_RECOUNT": recounts,
            "CANONICAL_RECOUNT_STATUS": "PASS" if recount_ok else "FAIL",
            "LEDGER": str(ledger_path.relative_to(repo_root.resolve())),
            "LEDGER_SHA256": hashlib.sha256(ledger_path.read_bytes()).hexdigest(),
        },
        TIMING={
            "AUTHORITY_REPRODUCTION_SECONDS": round(authority_seconds, 3),
            "PRECOMPUTE_SECONDS": round(precompute_seconds, 3),
            "PARITY_SECONDS": round(parity_seconds, 3),
            "PILOT_SCORING_SECONDS": round(scoring_seconds, 3),
            "PILOT_WALL_SECONDS": round(pilot_seconds, 3),
            "PILOT_CANDIDATES_PER_SECOND": round(scored / pilot_seconds, 2),
            "SCORING_ONLY_CANDIDATES_PER_SECOND": round(scored / scoring_seconds, 2),
            "TOTAL_RUN_SECONDS": round(time.perf_counter() - started, 3),
            "PILOT_WALL_DEFINITION": (
                "20 triple precomputes + exact scoring of every unique legal candidate"
            ),
        },
        PEAK_RSS_BYTES=_peak_rss_bytes(),
        PILOT_GAIN_VS_V6="YES" if gain else "NO",
        NEW_B649_GAIN_ESTABLISHED="YES" if gain else "NO",
    )
    _write_json_atomically(result_path, record)
    return record


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bounded 20-triple exact residual pilot (R1).")
    parser.add_argument("--repo-root", type=Path, required=True)
    args = parser.parse_args(argv)
    repo_root: Path = args.repo_root
    record = run_bounded_pilot(
        repo_root, result_path=repo_root / RESULT_PATH, runtime_dir=repo_root / RUNTIME_DIR
    )
    summary = {key: record[key] for key in ("PILOT_STATUS", "PILOT_GAIN_VS_V6")}
    print(json.dumps(summary, sort_keys=True))
    return 0 if record["PILOT_STATUS"] == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
