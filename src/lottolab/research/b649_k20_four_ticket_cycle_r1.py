"""Four-ticket single-number 4-cycle family with an exact 49/20 residual scorer.

A move picks four distinct ticket positions i < j < k < l of the normalized
portfolio (slots 0, 1, 2, 3), one number from each (a, b, c, d), and moves
every selected number to another ticket of the four along one 4-cycle. Each
ticket loses its own selected number and gains the selected number of its
predecessor on the cycle, so a legal move changes exactly four ticket sets. The
family is outside N2 and N3. It is not complete N4 and it is not full
four-ticket joint replacement: most ways to replace four tickets are not
single-number 4-cycles.

Frozen permutation family. ``ORIENTATIONS`` holds the six permutations of the
four slots that are one 4-cycle: the three cyclic orders of the slots, each in
both orientations. ``(0 1 2 3)`` is the specified forward move
(Ti-a+d, Tj-b+a, Tk-c+b, Tl-d+c) and ``(0 3 2 1)`` its reverse
(Ti-a+b, Tj-b+c, Tk-c+d, Tl-d+a). The three double transpositions
``(0 1)(2 3)``, ``(0 2)(1 3)`` and ``(0 3)(1 2)`` are two independent
two-ticket swaps; they are classified separately and never generated. Every
other permutation fixes a slot and so cannot change four tickets.

Raw attempts are C(K, 4) * 6**4 * 6: 7776 per quadruple and 37674720 at K=20.
That is a raw generation count, not a legal or deduplicated candidate count.

``SubsetResidual`` is the ``TripleResidual`` regrouping of the canonical
``evaluate_portfolio`` sum for any number of replaced positions: with the
other tickets R fixed, every candidate ticket lies inside W, the union of the
replaced tickets, so a draw D not already won by R contributes a value that
depends only on D & W and on R's rescue specials. With four tickets W can hold
24 numbers, so patterns are compacted to the at most sum_{m<=6} C(|W|, m)
subsets that a 6-number draw can meet instead of 2**|W| dense cells. The total
is identical to the canonical count, not an estimate.

The bounded pilot scores the complete declared family of 24 seeded quadruples
only. It never runs the full 4845-quadruple family.
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import heapq
import itertools
import json
import multiprocessing as mp
import os
import random
import resource
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from fractions import Fraction
from math import comb
from pathlib import Path
from typing import cast

import numpy as np
import numpy.typing as npt

from lottolab.research import b649_k20_three_ticket_single_number_cycle_r1 as ttc
from lottolab.research.b649_official_any_prize_exact import (
    BIG_LOTTO_OUTRIGHT_MATCHES,
    BIG_LOTTO_POOL_SIZE,
    DrawMasks,
    ticket_mask,
)

Ticket = ttc.Ticket
Portfolio = ttc.Portfolio
CycleError = ttc.CycleError
StartBinding = ttc.StartBinding

TICKET_SIZE = ttc.TICKET_SIZE
K20 = ttc.K20
QUADRUPLE_SIZE = 4
FAMILY_NAME = "FOUR_TICKET_SINGLE_NUMBER_4_CYCLE"


@dataclass(frozen=True, slots=True)
class Orientation:
    """One 4-cycle of the quadruple slots.

    ``successor[s]`` is the slot whose ticket receives slot ``s``'s selected
    number. Slot ``p``'s image is ``T_p - x_p + x_q`` with ``successor[q] == p``.
    """

    name: str
    successor: tuple[int, int, int, int]

    @property
    def predecessor(self) -> tuple[int, int, int, int]:
        inverse = [0, 0, 0, 0]
        for slot, target in enumerate(self.successor):
            inverse[target] = slot
        return (inverse[0], inverse[1], inverse[2], inverse[3])


ORIENTATIONS: tuple[Orientation, ...] = (
    Orientation("(0 1 2 3)", (1, 2, 3, 0)),
    Orientation("(0 3 2 1)", (3, 0, 1, 2)),
    Orientation("(0 1 3 2)", (1, 3, 0, 2)),
    Orientation("(0 2 3 1)", (2, 0, 3, 1)),
    Orientation("(0 2 1 3)", (2, 3, 1, 0)),
    Orientation("(0 3 1 2)", (3, 2, 0, 1)),
)
FORWARD = ORIENTATIONS[0]
REVERSE = ORIENTATIONS[1]
ORIENTATION_BY_NAME = {orientation.name: orientation for orientation in ORIENTATIONS}
EXCLUDED_DOUBLE_TRANSPOSITIONS: tuple[tuple[str, tuple[int, int, int, int]], ...] = (
    ("(0 1)(2 3)", (1, 0, 3, 2)),
    ("(0 2)(1 3)", (2, 3, 0, 1)),
    ("(0 3)(1 2)", (3, 2, 1, 0)),
)
CYCLE_ORIENTATIONS = len(ORIENTATIONS)
NUMBER_SELECTIONS_PER_QUADRUPLE = TICKET_SIZE**QUADRUPLE_SIZE
QUADRUPLE_RAW_ATTEMPTS = NUMBER_SELECTIONS_PER_QUADRUPLE * CYCLE_ORIENTATIONS
K20_TICKET_QUADRUPLES = comb(K20, QUADRUPLE_SIZE)
K20_RAW_FULL_FAMILY_SIZE = K20_TICKET_QUADRUPLES * QUADRUPLE_RAW_ATTEMPTS

REJECT_ILLEGAL_TICKET = "ILLEGAL_TICKET"
REJECT_UNCHANGED_TICKET = "UNCHANGED_TICKET"
REJECT_DUPLICATE_TICKET = "DUPLICATE_TICKET"
REJECT_FEWER_THAN_FOUR_CHANGED = "FEWER_THAN_FOUR_CHANGED"
REJECT_REASONS = (
    REJECT_ILLEGAL_TICKET,
    REJECT_UNCHANGED_TICKET,
    REJECT_DUPLICATE_TICKET,
    REJECT_FEWER_THAN_FOUR_CHANGED,
)


def rejection_counts_match(left: Mapping[str, int], right: Mapping[str, int]) -> bool:
    """Compare all rejection categories, treating absent zero-count keys as zero."""

    allowed = set(REJECT_REASONS)
    return (
        set(left).issubset(allowed)
        and set(right).issubset(allowed)
        and all(left.get(reason, 0) == right.get(reason, 0) for reason in REJECT_REASONS)
    )


if (
    CYCLE_ORIENTATIONS != 6
    or QUADRUPLE_RAW_ATTEMPTS != 7776
    or K20_TICKET_QUADRUPLES != 4845
    or K20_RAW_FULL_FAMILY_SIZE != 37_674_720
):
    raise RuntimeError("four-ticket cycle family size constants drifted")


def raw_attempt_cap(ticket_count: int) -> int:
    """C(K, 4) * 6**4 * 6 raw attempts. Not a legal or deduplicated count."""

    if ticket_count < QUADRUPLE_SIZE:
        raise CycleError("a four-ticket cycle needs at least four tickets")
    return comb(ticket_count, QUADRUPLE_SIZE) * QUADRUPLE_RAW_ATTEMPTS


def _require_normalized(portfolio: Portfolio, *, pool_size: int) -> Portfolio:
    normalized = ttc.normalize_portfolio(portfolio, pool_size=pool_size)
    if tuple(portfolio) != normalized:
        raise CycleError(
            "indices refer to normalize_portfolio(portfolio); pass the canonical portfolio"
        )
    return normalized


def _require_quadruple(quadruple: Sequence[int], ticket_count: int) -> tuple[int, int, int, int]:
    if len(quadruple) != QUADRUPLE_SIZE:
        raise CycleError("a quadruple names exactly four positions")
    i, j, k, fourth = quadruple
    if not 0 <= i < j < k < fourth < ticket_count:
        raise CycleError("a quadruple is four distinct positions in increasing canonical order")
    return (i, j, k, fourth)


def _replace_number(ticket: Ticket, remove: int, add: int) -> Ticket | None:
    """``ticket - {remove} + {add}``; ``None`` if that is not a 6-subset.

    Returning the original ticket means the coordinate did not change.
    """

    if remove == add:
        return ticket
    numbers = set(ticket)
    if remove not in numbers or add in numbers:
        return None
    numbers.remove(remove)
    numbers.add(add)
    return tuple(sorted(numbers))


def four_cycle_images(
    tickets: Sequence[Ticket], numbers: Sequence[int], orientation: Orientation
) -> tuple[Ticket, ...] | None:
    """Slot images ``T_p - x_p + x_pred(p)``; ``None`` if any is not a 6-subset."""

    predecessor = orientation.predecessor
    images: list[Ticket] = []
    for slot in range(QUADRUPLE_SIZE):
        image = _replace_number(tickets[slot], numbers[slot], numbers[predecessor[slot]])
        if image is None:
            return None
        images.append(image)
    return tuple(images)


@dataclass(frozen=True, slots=True)
class RawFourCycleSpec:
    quadruple: tuple[int, int, int, int]
    numbers: tuple[int, int, int, int]
    orientation: str


@dataclass(frozen=True, slots=True)
class EmittedFourCycle:
    portfolio: Portfolio
    sha256: str
    spec: RawFourCycleSpec
    removed: tuple[Ticket, ...]
    added: tuple[Ticket, ...]

    @property
    def tickets_changed(self) -> int:
        return len(self.removed)


def classify_attempt(
    canonical: Portfolio, spec: RawFourCycleSpec, *, pool_size: int
) -> EmittedFourCycle | str:
    """The emitted portfolio, or the first rejection reason in ``REJECT_REASONS`` order.

    ``canonical`` must already be normalized; ``spec.quadruple`` indexes it.
    """

    quadruple = _require_quadruple(spec.quadruple, len(canonical))
    orientation = ORIENTATION_BY_NAME.get(spec.orientation)
    if orientation is None:
        raise CycleError(f"orientation {spec.orientation} is not in the frozen family")
    origin = tuple(canonical[index] for index in quadruple)
    if any(number not in ticket for number, ticket in zip(spec.numbers, origin, strict=True)):
        raise CycleError("each selected number must come from its own slot's ticket")
    images = four_cycle_images(origin, spec.numbers, orientation)
    if images is None:
        return REJECT_ILLEGAL_TICKET
    if any(image == ticket for image, ticket in zip(images, origin, strict=True)):
        return REJECT_UNCHANGED_TICKET
    replaced = list(canonical)
    for index, image in zip(quadruple, images, strict=True):
        replaced[index] = image
    if len(set(replaced)) != len(replaced):
        return REJECT_DUPLICATE_TICKET
    emitted = ttc.normalize_portfolio(
        replaced, pool_size=pool_size, expected_ticket_count=len(canonical)
    )
    removed, added = ttc.ticket_set_difference(canonical, emitted)
    if len(removed) != QUADRUPLE_SIZE or len(added) != QUADRUPLE_SIZE:
        return REJECT_FEWER_THAN_FOUR_CHANGED
    return EmittedFourCycle(
        portfolio=emitted,
        sha256=ttc.portfolio_sha256(emitted, pool_size=pool_size),
        spec=spec,
        removed=removed,
        added=added,
    )


def emit_spec(
    portfolio: Portfolio, spec: RawFourCycleSpec, *, pool_size: int
) -> EmittedFourCycle | None:
    canonical = _require_normalized(portfolio, pool_size=pool_size)
    result = classify_attempt(canonical, spec, pool_size=pool_size)
    return result if isinstance(result, EmittedFourCycle) else None


def iter_quadruple_specs(
    portfolio: Portfolio, quadruple: Sequence[int], *, pool_size: int
) -> Iterator[RawFourCycleSpec]:
    """The 6**4 * 6 attempts of one quadruple: numbers a, b, c, d, then orientation."""

    canonical = _require_normalized(portfolio, pool_size=pool_size)
    fixed = _require_quadruple(quadruple, len(canonical))
    first, second, third, fourth = (canonical[index] for index in fixed)
    for a in first:
        for b in second:
            for c in third:
                for d in fourth:
                    for orientation in ORIENTATIONS:
                        yield RawFourCycleSpec(fixed, (a, b, c, d), orientation.name)


def iter_raw_specs(portfolio: Portfolio, *, pool_size: int) -> Iterator[RawFourCycleSpec]:
    """Every attempt of the declared family: raw_attempt_cap(K), 37674720 at K=20."""

    canonical = _require_normalized(portfolio, pool_size=pool_size)
    for quadruple in itertools.combinations(range(len(canonical)), QUADRUPLE_SIZE):
        yield from iter_quadruple_specs(canonical, quadruple, pool_size=pool_size)


def deduped_emissions(emissions: Iterable[EmittedFourCycle]) -> tuple[EmittedFourCycle, ...]:
    """First occurrence of each normalized portfolio hash wins."""

    seen: set[str] = set()
    unique: list[EmittedFourCycle] = []
    for emission in emissions:
        if emission.sha256 in seen:
            continue
        seen.add(emission.sha256)
        unique.append(emission)
    return tuple(unique)


# --- exact residual scorer (any pool, any number of replaced positions) ----------------

type PatternArray = npt.NDArray[np.uint32]
type CountArray = npt.NDArray[np.int64]
type IndexArray = npt.NDArray[np.int32]

MAX_UNIVERSE_WIDTH = QUADRUPLE_SIZE * TICKET_SIZE


@functools.lru_cache(maxsize=2)
def _pattern_index(width: int, draw_size: int) -> tuple[PatternArray, IndexArray]:
    """Every subset of ``width`` bits with at most ``draw_size`` members, and its index table."""

    if not 1 <= width <= MAX_UNIVERSE_WIDTH:
        raise CycleError(f"universe width {width} is outside 1..{MAX_UNIVERSE_WIDTH}")
    masks = np.fromiter(
        (
            sum(1 << bit for bit in bits)
            for size in range(min(width, draw_size) + 1)
            for bits in itertools.combinations(range(width), size)
        ),
        dtype=np.uint32,
    )
    index_of = np.full(1 << width, -1, dtype=np.int32)
    index_of[masks] = np.arange(masks.size, dtype=np.int32)
    return masks, index_of


@dataclass(frozen=True, slots=True)
class SubsetResidual:
    """Canonical-exact count of R + replacement tickets that all lie inside W.

    ``R`` is the portfolio without ``indices`` and W is the union of the
    replaced tickets. A draw won outright by R always yields ``special_count``
    winning specials. A draw D not won by R yields ``special_count`` if a new
    ticket reaches ``outright_matches`` in D, and otherwise
    ``len(rescue_R(D) | M)``, where ``rescue_R(D)`` is R's rescue set minus D
    and M is the union of ``T - D`` over new tickets with ``outright_matches - 1``
    hits. M lies inside W - D, so that size is
    ``|rescue_R(D)| + sum_{w in M} [w not in rescue_R(D)]``. Per pattern
    q = D & W only the number of such draws, their summed ``|rescue_R(D)|`` and,
    per w in W, how many of them lack w from ``rescue_R(D)`` are kept.
    """

    indices: tuple[int, ...]
    pool_size: int
    special_count: int
    outright_matches: int
    universe_numbers: tuple[int, ...]
    rest_won_draws: int
    patterns: PatternArray
    pattern_draws: CountArray
    pattern_rescue: CountArray
    fresh_by_number: CountArray
    bit_of: dict[int, int] = field(repr=False, compare=False)

    @property
    def pattern_count(self) -> int:
        return int(self.patterns.size)

    def compress(self, ticket: Sequence[int]) -> int:
        """Ticket as a bitmask over W; refuses any number outside W."""

        mask = 0
        for number in ticket:
            bit = self.bit_of.get(number)
            if bit is None:
                raise CycleError(f"number {number} lies outside the residual universe W")
            mask |= 1 << bit
        return mask

    def outcome_count(self, tickets: Sequence[Sequence[int]]) -> int:
        """Exact canonical OFFICIAL_ANY_PRIZE count of R + ``tickets``."""

        if len(tickets) != len(self.indices):
            raise CycleError(f"this residual scores exactly {len(self.indices)} tickets")
        patterns = self.patterns
        zero = np.uint32(0)
        won = np.zeros(patterns.size, dtype=np.bool_)
        rescue = np.zeros(patterns.size, dtype=np.uint32)
        for ticket in tickets:
            mask = np.uint32(self.compress(ticket))
            hits = np.bitwise_count(patterns & mask)
            won |= hits >= self.outright_matches
            rescue |= np.where(hits == self.outright_matches - 1, mask & ~patterns, zero)
        rescue[won] = zero
        width = len(self.universe_numbers)
        carried = np.unpackbits(
            rescue.view(np.uint8).reshape(patterns.size, 4), axis=1, bitorder="little"
        )[:, :width]
        added = int(np.einsum("ij,ij->", carried, self.fresh_by_number, dtype=np.int64))
        open_rows = ~won
        won_draws = self.rest_won_draws + int(self.pattern_draws[won].sum())
        return self.special_count * won_draws + int(self.pattern_rescue[open_rows].sum()) + added


def build_subset_residual(
    portfolio: Portfolio,
    indices: Sequence[int],
    *,
    pool_size: int,
    draws: DrawMasks,
    chunk_size: int = 1 << 21,
) -> SubsetResidual:
    """Aggregate every draw not won by R = portfolio minus ``indices`` by D & W."""

    canonical = _require_normalized(portfolio, pool_size=pool_size)
    chosen = tuple(indices)
    if (
        not chosen
        or len(set(chosen)) != len(chosen)
        or any(not 0 <= index < len(canonical) for index in chosen)
    ):
        raise CycleError("residual indices must be distinct positions of the portfolio")
    if draws.size != comb(pool_size, TICKET_SIZE):
        raise CycleError("draws must be the complete main-draw space")
    if sys.byteorder != "little":
        raise CycleError("the rescue bit unpacking assumes a little-endian host")
    excluded = set(chosen)
    universe = tuple(sorted({number for index in chosen for number in canonical[index]}))
    width = len(universe)
    subset_masks, index_of = _pattern_index(width, TICKET_SIZE)
    subset_count = int(subset_masks.size)
    outright = BIG_LOTTO_OUTRIGHT_MATCHES
    rest_masks = [
        np.uint64(ticket_mask(ticket))
        for position, ticket in enumerate(canonical)
        if position not in excluded
    ]
    shifts64 = [np.uint64(number - 1) for number in universe]
    one = np.uint64(1)
    zero = np.uint64(0)
    draw_counts = np.zeros(subset_count, dtype=np.int64)
    rescue_counts = np.zeros(subset_count, dtype=np.int64)
    number_counts = np.zeros((width, subset_count), dtype=np.int64)
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
        compact = index_of[pattern]
        if compact.size and int(compact.min()) < 0:
            raise CycleError("a draw met W in more numbers than a draw holds")
        draw_counts += np.bincount(compact, minlength=subset_count)
        weighted = np.bincount(
            compact,
            weights=np.bitwise_count(open_rescue).astype(np.float64),
            minlength=subset_count,
        )
        exact = weighted.astype(np.int64)
        if not np.array_equal(exact, weighted):
            raise CycleError("rescue aggregation lost integer exactness")
        rescue_counts += exact
        for bit, shift in enumerate(shifts64):
            carries = ((open_rescue >> shift) & one).astype(np.bool_)
            number_counts[bit] += np.bincount(compact[carries], minlength=subset_count)
    if rest_won + int(draw_counts.sum()) != draws.size:
        raise CycleError("residual draw accounting does not cover the draw space")
    present = np.flatnonzero(draw_counts)
    pattern_draws = draw_counts[present]
    fresh = pattern_draws[:, None] - number_counts[:, present].T
    if fresh.size and int(fresh.min()) < 0:
        raise CycleError("a number is carried by more draws than its pattern holds")
    return SubsetResidual(
        indices=chosen,
        pool_size=pool_size,
        special_count=pool_size - TICKET_SIZE,
        outright_matches=outright,
        universe_numbers=universe,
        rest_won_draws=rest_won,
        patterns=subset_masks[present],
        pattern_draws=pattern_draws,
        pattern_rescue=rescue_counts[present],
        fresh_by_number=np.ascontiguousarray(fresh),
        bit_of={number: bit for bit, number in enumerate(universe)},
    )


# --- starts, pilot selection and tie-break ---------------------------------------------

TASK_ID = "B649_K20_V7_FOUR_TICKET_RUNNER_COMPAT_AND_PILOT_R1"
SCIENTIFIC_SCOPE = "BOUNDED_FOUR_TICKET_CYCLE_PILOT_FROM_V7"
TOTAL_OUTCOMES = ttc.TOTAL_OUTCOMES
V6_REFERENCE_HEAD = "76085ccc8f226c8752cc7df28390e27009d21746"
V7_BASELINE_TASK_ID = "B649_K20_V7_THREE_TICKET_GLOBAL_REPAIR_PILOT_R1"
V7_BASELINE_OUTCOMES = 313_239_661
V7_BASELINE_SHA256 = "0045ac8837fc82e9a585d812173341ac12e05c5de201af7f8fedeacafa19e1ff"
V7_BASELINE_EXACT_PROBABILITY = "44748523/85900584"
HISTORICAL_START_COUNT = 313_239_661
HISTORICAL_START_SHA256 = "7ce41ff21d5c0821f1d5dda683e23114086f5024fc6d98d4e574df5306659b1e"
CONTROL_START_COUNT = ttc.STARTING_COUNT
CONTROL_START_SHA256 = ttc.STARTING_PORTFOLIO_SHA256
GAIN_THRESHOLD_COUNT = V7_BASELINE_OUTCOMES
START_PRIMARY = "PRIMARY"
START_CONTROL = "CONTROL"
PILOT_SEED = 20260930
QUADRUPLE_SAMPLE_COUNT = 24
PILOT_RAW_ATTEMPT_CEILING = QUADRUPLE_SAMPLE_COUNT * QUADRUPLE_RAW_ATTEMPTS
PARITY_SEED = PILOT_SEED
PARITY_PER_QUADRUPLE = 3
PARITY_MIN_SAMPLE = 60
WORKERS = 2
TOP_N = 25
CONTROL_WALL_BUDGET_SECONDS = 1800.0
OWNER_RECORD_PATH = f".fable/checkpoints/{TASK_ID}/owner.json"
EXECUTION_RECORD_PATH = f".fable/checkpoints/{TASK_ID}/executions/run1.json"
TIE_BREAK = "max exact count, then lowest normalized portfolio sha256"

if PILOT_RAW_ATTEMPT_CEILING != 186_624 or TOTAL_OUTCOMES != 601_304_088:
    raise RuntimeError("pilot ceiling or outcome total drifted")


def bind_explicit_incumbent(
    portfolio: Sequence[Sequence[int]],
    *,
    expected_sha256: str,
    expected_outcome_count: int,
    draws: DrawMasks,
) -> StartBinding:
    """Bind an explicitly named portfolio and recompute its canonical identity and count."""

    if len(expected_sha256) != 64 or any(c not in "0123456789abcdef" for c in expected_sha256):
        raise CycleError("incumbent sha256 must be a lowercase 64-character digest")
    if type(expected_outcome_count) is not int or expected_outcome_count < 0:
        raise CycleError("incumbent outcomes must be a non-negative integer")
    start = ttc.bind_start(
        portfolio,
        pool_size=BIG_LOTTO_POOL_SIZE,
        expected_sha256=expected_sha256,
        expected_outcome_count=expected_outcome_count,
        draws=draws,
    )
    if len(start.portfolio) != K20:
        raise CycleError("incumbent is not a K=20 portfolio")
    if start.sha256 != expected_sha256 or start.outcome_count != expected_outcome_count:
        raise CycleError("recomputed incumbent identity does not match the explicit expectation")
    return start


def load_current_v7_start(
    repo_root: Path, incumbent_artifact: Path | None, *, draws: DrawMasks
) -> StartBinding:
    """Load only the exact v7 incumbent; missing or mismatched inputs fail closed."""

    if incumbent_artifact is None:
        raise CycleError("an explicit current-v7 incumbent artifact is required")
    root = repo_root.resolve()
    artifact = incumbent_artifact if incumbent_artifact.is_absolute() else root / incumbent_artifact
    try:
        artifact = artifact.resolve(strict=True)
        raw = artifact.read_bytes()
    except OSError as error:
        raise CycleError(
            f"current-v7 incumbent artifact is unavailable: {incumbent_artifact}"
        ) from error
    if not artifact.is_relative_to(root):
        raise CycleError("current-v7 incumbent artifact must be inside the repository")
    try:
        payload: object = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CycleError("current-v7 incumbent artifact is not valid JSON") from error
    if not isinstance(payload, dict):
        raise CycleError("current-v7 incumbent artifact must be a JSON object")
    fields = cast(dict[str, object], payload)
    if fields.get("TASK_ID") != V7_BASELINE_TASK_ID:
        raise CycleError("incumbent artifact is not the selected v7 authority")
    if fields.get("BEST_COUNT") != V7_BASELINE_OUTCOMES:
        raise CycleError("incumbent artifact outcome count does not match the v7 baseline")
    if fields.get("BEST_SHA256") != V7_BASELINE_SHA256:
        raise CycleError("incumbent artifact portfolio sha256 does not match the v7 baseline")
    rows = fields.get("BEST_PORTFOLIO")
    if not isinstance(rows, list):
        raise CycleError("current-v7 BEST_PORTFOLIO must be a list")
    tickets: list[list[int]] = []
    for row in cast(list[object], rows):
        if not isinstance(row, list):
            raise CycleError("current-v7 tickets must be lists of integers")
        ticket = cast(list[object], row)
        if any(type(number) is not int for number in ticket):
            raise CycleError("current-v7 tickets must be lists of integers")
        tickets.append(cast(list[int], ticket))
    start = bind_explicit_incumbent(
        tickets,
        expected_sha256=V7_BASELINE_SHA256,
        expected_outcome_count=V7_BASELINE_OUTCOMES,
        draws=draws,
    )
    if str(Fraction(start.outcome_count, TOTAL_OUTCOMES)) != V7_BASELINE_EXACT_PROBABILITY:
        raise CycleError("current-v7 baseline exact probability does not reproduce")
    return start


def load_start(
    label: str,
    repo_root: Path,
    *,
    draws: DrawMasks,
    incumbent_artifact: Path | None = None,
) -> StartBinding:
    if label == START_PRIMARY:
        return load_current_v7_start(repo_root, incumbent_artifact, draws=draws)
    if label == START_CONTROL:
        return ttc.load_v6_authority(repo_root, draws=draws)
    raise CycleError(f"unknown start {label}")


def select_pilot_quadruples(
    ticket_count: int = K20, *, seed: int = PILOT_SEED, count: int = QUADRUPLE_SAMPLE_COUNT
) -> tuple[tuple[int, int, int, int], ...]:
    """``count`` distinct position quadruples sampled once from all C(K, 4), in sampled order."""

    population = list(itertools.combinations(range(ticket_count), QUADRUPLE_SIZE))
    return tuple(random.Random(seed).sample(population, count))


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    sha256: str
    outcome_count: int


def is_better(candidate: ScoredCandidate, incumbent: ScoredCandidate | None) -> bool:
    """Higher exact count wins; equal counts go to the lower normalized portfolio sha256."""

    if incumbent is None:
        return True
    if candidate.outcome_count != incumbent.outcome_count:
        return candidate.outcome_count > incumbent.outcome_count
    return candidate.sha256 < incumbent.sha256


# --- worker tasks ---------------------------------------------------------------------

_STATE: dict[str, object] = {}


def _peak_rss_bytes() -> int:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak) if os.uname().sysname == "Darwin" else int(peak) * 1024


def _worker_init(start: StartBinding) -> None:
    draws = ttc.load_draws(BIG_LOTTO_POOL_SIZE)
    _STATE["draws"] = draws
    _STATE["start"] = start


def _worker_state() -> tuple[StartBinding, DrawMasks]:
    start = _STATE["start"]
    draws = _STATE["draws"]
    if not isinstance(start, StartBinding) or not isinstance(draws, np.ndarray):
        raise CycleError("worker state was not initialized")
    return start, cast(DrawMasks, draws)


def _emission_json(emission: EmittedFourCycle) -> dict[str, object]:
    return {
        "SHA256": emission.sha256,
        "QUADRUPLE": list(emission.spec.quadruple),
        "NUMBERS": list(emission.spec.numbers),
        "ORIENTATION": emission.spec.orientation,
        "REMOVED": [list(ticket) for ticket in emission.removed],
        "ADDED": [list(ticket) for ticket in emission.added],
    }


def _unique_legal(start: StartBinding, quadruple: Sequence[int]) -> list[EmittedFourCycle]:
    unique: list[EmittedFourCycle] = []
    seen: set[str] = set()
    for spec in iter_quadruple_specs(start.portfolio, quadruple, pool_size=start.pool_size):
        result = classify_attempt(start.portfolio, spec, pool_size=start.pool_size)
        if isinstance(result, EmittedFourCycle) and result.sha256 not in seen:
            seen.add(result.sha256)
            unique.append(result)
    return unique


def parity_quadruple(
    start: StartBinding,
    residual: SubsetResidual,
    quadruple: tuple[int, int, int, int],
    *,
    draws: DrawMasks,
    per_quadruple: int = PARITY_PER_QUADRUPLE,
) -> dict[str, object]:
    """Residual vs full ``evaluate_portfolio`` on seeded legal candidates of one quadruple."""

    origin = tuple(start.portfolio[index] for index in quadruple)
    origin_count = residual.outcome_count(origin)
    legal = _unique_legal(start, quadruple)
    rng = random.Random(f"parity:{PARITY_SEED}:{':'.join(map(str, quadruple))}")
    samples: list[dict[str, object]] = []
    for emission in rng.sample(legal, min(per_quadruple, len(legal))):
        residual_count = residual.outcome_count(emission.added)
        canonical_count = ttc.official_any_prize_outcome_count(
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
        "QUADRUPLE": list(quadruple),
        "START_RESIDUAL_COUNT": origin_count,
        "START_MATCH": origin_count == start.outcome_count,
        "SAMPLES": samples,
    }


def parity_task(quadruple: tuple[int, int, int, int]) -> dict[str, object]:
    start, draws = _worker_state()
    residual = build_subset_residual(
        start.portfolio, quadruple, pool_size=start.pool_size, draws=draws
    )
    return parity_quadruple(start, residual, quadruple, draws=draws)


type CandidateRow = tuple[str, tuple[int, int, int, int], str, int]


def scan_quadruple(
    start: StartBinding, residual: SubsetResidual, quadruple: tuple[int, int, int, int]
) -> dict[str, object]:
    """Complete declared family of one quadruple, every unique legal candidate scored exactly."""

    began = time.perf_counter()
    rebind = residual.outcome_count(tuple(start.portfolio[index] for index in quadruple))
    raw = legal = local_duplicates = 0
    rejected: Counter[str] = Counter()
    seen: set[str] = set()
    rows: list[CandidateRow] = []
    for spec in iter_quadruple_specs(start.portfolio, quadruple, pool_size=start.pool_size):
        raw += 1
        result = classify_attempt(start.portfolio, spec, pool_size=start.pool_size)
        if isinstance(result, str):
            rejected[result] += 1
            continue
        legal += 1
        if result.sha256 in seen:
            local_duplicates += 1
            continue
        seen.add(result.sha256)
        rows.append(
            (result.sha256, spec.numbers, spec.orientation, residual.outcome_count(result.added))
        )
    return {
        "QUADRUPLE": quadruple,
        "RAW": raw,
        "LEGAL": legal,
        "REJECTED": {reason: rejected[reason] for reason in REJECT_REASONS},
        "LOCAL_DUPLICATES": local_duplicates,
        "REBIND_COUNT": rebind,
        "UNIVERSE_SIZE": len(residual.universe_numbers),
        "PATTERNS": residual.pattern_count,
        "SCORING_SECONDS": time.perf_counter() - began,
        "ROWS": rows,
    }


def scan_task(quadruple: tuple[int, int, int, int]) -> dict[str, object]:
    start, draws = _worker_state()
    began = time.perf_counter()
    residual = build_subset_residual(
        start.portfolio, quadruple, pool_size=start.pool_size, draws=draws
    )
    precompute = time.perf_counter() - began
    result = scan_quadruple(start, residual, quadruple)
    result.update(PRECOMPUTE_SECONDS=precompute, WORKER_PEAK_RSS=_peak_rss_bytes())
    return result


# --- pilot driver ---------------------------------------------------------------------


def _git(repo_root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _write_json_atomically(path: Path, payload: dict[str, object]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    staging = path.with_name(path.name + ".tmp")
    staging.write_bytes(encoded)
    os.replace(staging, path)
    return hashlib.sha256(encoded).hexdigest()


_SHA_INVERT = str.maketrans("0123456789abcdef", "fedcba9876543210")


def _int(value: object) -> int:
    if type(value) is not int:
        raise CycleError(f"expected an int, got {value!r}")
    return value


def _float(value: object) -> float:
    if not isinstance(value, float):
        raise CycleError(f"expected a float, got {value!r}")
    return value


def summarize_parity(results: Sequence[dict[str, object]]) -> dict[str, object]:
    samples = [
        sample for result in results for sample in cast(list[dict[str, object]], result["SAMPLES"])
    ]
    return {
        "SEED": PARITY_SEED,
        "STREAM": "random.Random('parity:<seed>:<i>:<j>:<k>:<l>').sample(unique legal, 3)",
        "PER_QUADRUPLE": PARITY_PER_QUADRUPLE,
        "MIN_SAMPLE": PARITY_MIN_SAMPLE,
        "SAMPLE_COUNT": len(samples),
        "MISMATCHES": sum(1 for sample in samples if not sample["MATCH"]),
        "START_REPRODUCTION_CHECKS": len(results),
        "START_REPRODUCTION_MISMATCHES": sum(1 for result in results if not result["START_MATCH"]),
        "START_REPRODUCTION": [
            {
                "QUADRUPLE": result["QUADRUPLE"],
                "RESIDUAL_COUNT": result["START_RESIDUAL_COUNT"],
                "MATCH": result["START_MATCH"],
            }
            for result in results
        ],
        "SAMPLES": samples,
    }


def parity_passes(parity: dict[str, object]) -> bool:
    return (
        parity["MISMATCHES"] == 0
        and parity["START_REPRODUCTION_MISMATCHES"] == 0
        and _int(parity["SAMPLE_COUNT"]) >= PARITY_MIN_SAMPLE
    )


def aggregate_scan(
    start: StartBinding,
    quadruples: Sequence[tuple[int, int, int, int]],
    results: Sequence[dict[str, object]],
    *,
    draws: DrawMasks,
    ledger_path: Path,
) -> dict[str, object]:
    """Global dedup, best, ties, canonical recount and accounting checks for one start."""

    raw = legal = local_duplicates = cross_duplicates = scored = 0
    improvements = equal_to_start = rebind_mismatches = 0
    rejected: Counter[str] = Counter()
    seen: set[str] = set()
    order_digest = hashlib.sha256()
    best: ScoredCandidate | None = None
    ties: list[tuple[str, tuple[int, int, int, int], tuple[int, int, int, int], str, int]] = []
    top: list[tuple[tuple[int, str], dict[str, object]]] = []
    per_quadruple: list[dict[str, object]] = []
    precompute_total = scoring_total = 0.0
    worker_peak = 0
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("w", encoding="utf-8") as ledger:
        for result in results:
            quadruple = cast(tuple[int, int, int, int], result["QUADRUPLE"])
            raw += _int(result["RAW"])
            legal += _int(result["LEGAL"])
            local_duplicates += _int(result["LOCAL_DUPLICATES"])
            for reason, count in cast(dict[str, int], result["REJECTED"]).items():
                rejected[reason] += count
            rebind_ok = result["REBIND_COUNT"] == start.outcome_count
            rebind_mismatches += not rebind_ok
            precompute_total += _float(result["PRECOMPUTE_SECONDS"])
            scoring_total += _float(result["SCORING_SECONDS"])
            worker_peak = max(worker_peak, _int(result["WORKER_PEAK_RSS"]))
            q_unique = q_improvements = 0
            q_best: int | None = None
            for sha, numbers, orientation, count in cast(list[CandidateRow], result["ROWS"]):
                scored += 1
                if sha in seen:
                    cross_duplicates += 1
                    continue
                seen.add(sha)
                order_digest.update(sha.encode() + b"\n")
                q_unique += 1
                improvements += count > start.outcome_count
                q_improvements += count > start.outcome_count
                equal_to_start += count == start.outcome_count
                q_best = count if q_best is None else max(q_best, count)
                candidate = ScoredCandidate(sha, count)
                if best is None or count > best.outcome_count:
                    ties = []
                if is_better(candidate, best):
                    best = candidate
                if best is not None and count == best.outcome_count:
                    ties.append((sha, quadruple, numbers, orientation, count))
                entry: dict[str, object] = {
                    "SHA256": sha,
                    "QUADRUPLE": list(quadruple),
                    "NUMBERS": list(numbers),
                    "ORIENTATION": orientation,
                    "COUNT": count,
                }
                key = (count, sha.translate(_SHA_INVERT))
                if len(top) < TOP_N:
                    heapq.heappush(top, (key, entry))
                elif key > top[0][0]:
                    heapq.heapreplace(top, (key, entry))
                ledger.write(json.dumps(entry, sort_keys=True) + "\n")
            per_quadruple.append(
                {
                    "QUADRUPLE": list(quadruple),
                    "TICKETS": [list(start.portfolio[index]) for index in quadruple],
                    "UNIVERSE_SIZE": result["UNIVERSE_SIZE"],
                    "PATTERNS": result["PATTERNS"],
                    "RAW": result["RAW"],
                    "LEGAL": result["LEGAL"],
                    "REJECTED": result["REJECTED"],
                    "UNIQUE": q_unique,
                    "STRICT_IMPROVEMENTS": q_improvements,
                    "BEST_COUNT": q_best,
                    "REBIND_MATCH": rebind_ok,
                    "PRECOMPUTE_SECONDS": round(_float(result["PRECOMPUTE_SECONDS"]), 3),
                    "SCORING_SECONDS": round(_float(result["SCORING_SECONDS"]), 3),
                }
            )
    if best is None:
        raise CycleError("the pilot scored nothing")
    ties = [tie for tie in ties if tie[4] == best.outcome_count]
    unique = len(seen)

    # Independent accounting: re-walk the same quadruples in-process with the generator.
    generator_raw = generator_legal = 0
    generator_rejected: Counter[str] = Counter()
    generator_seen: set[str] = set()
    generator_digest = hashlib.sha256()
    for quadruple in quadruples:
        for spec in iter_quadruple_specs(start.portfolio, quadruple, pool_size=start.pool_size):
            generator_raw += 1
            outcome = classify_attempt(start.portfolio, spec, pool_size=start.pool_size)
            if isinstance(outcome, str):
                generator_rejected[outcome] += 1
                continue
            generator_legal += 1
            if outcome.sha256 not in generator_seen:
                generator_seen.add(outcome.sha256)
                generator_digest.update(outcome.sha256.encode() + b"\n")

    recount_targets = ties
    recounts: list[dict[str, object]] = []
    best_emission: EmittedFourCycle | None = None
    for sha, quadruple, numbers, orientation, count in sorted(recount_targets):
        emission = emit_spec(
            start.portfolio,
            RawFourCycleSpec(quadruple, numbers, orientation),
            pool_size=start.pool_size,
        )
        if emission is None or emission.sha256 != sha:
            raise CycleError(f"cannot re-emit tied candidate {sha}")
        if sha == best.sha256:
            best_emission = emission
        canonical_count = ttc.official_any_prize_outcome_count(
            emission.portfolio, pool_size=start.pool_size, draws=draws
        )
        recounts.append(
            {
                "SHA256": sha,
                "RESIDUAL_COUNT": count,
                "CANONICAL_COUNT": canonical_count,
                "MATCH": canonical_count == count,
            }
        )
    if best_emission is None:
        raise CycleError("best candidate was not recounted")
    recount_ok = bool(recounts) and all(entry["MATCH"] for entry in recounts)
    checks = {
        "QUADRUPLES_COMPLETE": [tuple(cast(Sequence[int], q["QUADRUPLE"])) for q in per_quadruple]
        == list(quadruples),
        "RAW_EQUALS_CEILING": raw == len(quadruples) * QUADRUPLE_RAW_ATTEMPTS,
        "PER_QUADRUPLE_RAW_7776": all(q["RAW"] == QUADRUPLE_RAW_ATTEMPTS for q in per_quadruple),
        "RAW_EQUALS_LEGAL_PLUS_REJECTED": raw == legal + sum(rejected.values()),
        "RAW_EQUALS_GENERATOR": raw == generator_raw,
        "LEGAL_EQUALS_GENERATOR": legal == generator_legal,
        "REJECTED_EQUALS_GENERATOR": rejection_counts_match(rejected, generator_rejected),
        "UNIQUE_EQUALS_GENERATOR": unique == len(generator_seen),
        "UNIQUE_ORDER_EQUALS_GENERATOR": order_digest.hexdigest() == generator_digest.hexdigest(),
        "LEGAL_EQUALS_UNIQUE_PLUS_DUPLICATES": legal
        == unique + local_duplicates + cross_duplicates,
        "SCORED_EQUALS_LEGAL_MINUS_LOCAL_DUPLICATES": scored == legal - local_duplicates,
        "PER_QUADRUPLE_START_REBIND": rebind_mismatches == 0,
        "BEST_CANONICAL_RECOUNT": recount_ok,
    }
    best_json = _emission_json(best_emission)
    best_json.update(
        PORTFOLIO=[list(ticket) for ticket in best_emission.portfolio],
        COUNT=best.outcome_count,
        DELTA_VS_START=best.outcome_count - start.outcome_count,
        EXACT_PROBABILITY=str(Fraction(best.outcome_count, TOTAL_OUTCOMES)),
        QUADRUPLE_TICKETS=[list(start.portfolio[index]) for index in best_emission.spec.quadruple],
    )
    return {
        "START_COUNT": start.outcome_count,
        "START_SHA256": start.sha256,
        "START_EXACT_PROBABILITY": str(Fraction(start.outcome_count, TOTAL_OUTCOMES)),
        "START_PORTFOLIO": [list(ticket) for ticket in start.portfolio],
        "START_CANONICAL_REPRODUCTION": "PASS",
        "RAW_ATTEMPTS": raw,
        "LEGAL": legal,
        "REJECTED": {reason: rejected[reason] for reason in REJECT_REASONS},
        "WITHIN_QUADRUPLE_DUPLICATES": local_duplicates,
        "CROSS_QUADRUPLE_DUPLICATES": cross_duplicates,
        "DEDUPLICATED": unique,
        "EXACT_SCORED": scored,
        "PRUNING": "NONE",
        "TOP_L": "NONE",
        "INNER_SAMPLING": "NONE",
        "STRICT_IMPROVEMENTS_VS_START": improvements,
        "CANDIDATES_EQUAL_TO_START": equal_to_start,
        "BEST": best_json,
        "BEST_TIE_COUNT": len(ties),
        "TIE_BREAK": TIE_BREAK,
        "BEST_CANONICAL_RECOUNT": recounts,
        "BEST_CANONICAL_RECOUNT_STATUS": "PASS" if recount_ok else "FAIL",
        "TOP_CANDIDATES": [entry for _key, entry in sorted(top, reverse=True)],
        "PRECOMPUTE_CPU_SECONDS": round(precompute_total, 3),
        "SCORING_CPU_SECONDS": round(scoring_total, 3),
        "WORKER_PEAK_RSS_BYTES": worker_peak,
        "ACCOUNTING": {
            "GENERATOR_RAW": generator_raw,
            "GENERATOR_LEGAL": generator_legal,
            "GENERATOR_REJECTED": {reason: generator_rejected[reason] for reason in REJECT_REASONS},
            "GENERATOR_UNIQUE": len(generator_seen),
            "GENERATOR_UNIQUE_ORDER_SHA256": generator_digest.hexdigest(),
            "SCAN_UNIQUE_ORDER_SHA256": order_digest.hexdigest(),
        },
        "CHECKS": checks,
        "LEDGER_SHA256": hashlib.sha256(ledger_path.read_bytes()).hexdigest(),
        "PER_QUADRUPLE": per_quadruple,
    }


def run_start(
    label: str,
    repo_root: Path,
    quadruples: Sequence[tuple[int, int, int, int]],
    *,
    draws: DrawMasks,
    runtime_dir: Path,
    workers: int,
    with_parity: bool,
    incumbent_artifact: Path | None = None,
) -> dict[str, object]:
    """Optional parity phase, then the pilot scan of one start on ``workers`` processes."""

    start = load_start(label, repo_root, draws=draws, incumbent_artifact=incumbent_artifact)
    ledger_path = runtime_dir / f"{label.lower()}-candidates.jsonl"
    context = mp.get_context("spawn")
    with ProcessPoolExecutor(
        max_workers=workers,
        mp_context=context,
        initializer=_worker_init,
        initargs=(start,),
    ) as pool:
        parity: dict[str, object] | None = None
        parity_seconds = 0.0
        if with_parity:
            began = time.perf_counter()
            parity = summarize_parity(list(pool.map(parity_task, quadruples, chunksize=1)))
            parity_seconds = time.perf_counter() - began
            if not parity_passes(parity):
                return {
                    "START_LABEL": label,
                    "STATUS": "NOT_RUN_PARITY_REFUTED",
                    "PARITY": parity,
                    "PARITY_SECONDS": round(parity_seconds, 3),
                }
        began = time.perf_counter()
        results = list(pool.map(scan_task, quadruples, chunksize=1))
        wall = time.perf_counter() - began
    summary = aggregate_scan(start, quadruples, results, draws=draws, ledger_path=ledger_path)
    checks = cast(dict[str, bool], summary["CHECKS"])
    summary.update(
        START_LABEL=label,
        STATUS="COMPLETE" if all(checks.values()) else "ACCOUNTING_OR_PARITY_CHECK_FAILED",
        LEDGER=str(ledger_path.relative_to(repo_root.resolve())),
        PILOT_WALL_SECONDS=round(wall, 3),
        PILOT_WALL_DEFINITION=(
            f"{workers}-worker wall of {len(quadruples)} quadruple precomputes + exact scoring "
            "of every unique legal candidate (worker start-up and parity excluded)"
        ),
        CANDIDATES_PER_SECOND=round(_int(summary["EXACT_SCORED"]) / wall, 2),
    )
    if parity is not None:
        summary.update(PARITY=parity, PARITY_SECONDS=round(parity_seconds, 3))
    return summary


def full_family_estimate(primary: dict[str, object], *, workers: int) -> dict[str, object]:
    """Scale the measured per-quadruple CPU cost to all C(20,4) quadruples. Not executed."""

    sampled = len(cast(list[object], primary["PER_QUADRUPLE"]))
    cpu = _float(primary["PRECOMPUTE_CPU_SECONDS"]) + _float(primary["SCORING_CPU_SECONDS"])
    per_quadruple = cpu / sampled
    estimate = per_quadruple * K20_TICKET_QUADRUPLES / workers
    wall_scaled = _float(primary["PILOT_WALL_SECONDS"]) * K20_TICKET_QUADRUPLES / sampled
    return {
        "STATUS": "ESTIMATE_NOT_MEASURED_EXECUTION",
        "FULL_FAMILY_ESTIMATED_WALL_SECONDS": round(estimate),
        "DEFINITION": (
            "mean measured per-quadruple worker CPU (precompute + exact scoring) over the "
            f"{sampled} pilot quadruples * {K20_TICKET_QUADRUPLES} quadruples / {workers} workers"
        ),
        "MEAN_QUADRUPLE_CPU_SECONDS": round(per_quadruple, 3),
        "SINGLE_CORE_CPU_SECONDS": round(per_quadruple * K20_TICKET_QUADRUPLES),
        "PILOT_WALL_SCALED_SECONDS": round(wall_scaled),
        "RAW_FULL_FAMILY_SIZE": K20_RAW_FULL_FAMILY_SIZE,
        "WORKERS_ASSUMED": workers,
        "CAVEAT": (
            "host load, per-quadruple legality and |W| vary; the full family was not started"
        ),
    }


def run_pilot(
    repo_root: Path,
    *,
    incumbent_artifact: Path,
    result_path: Path,
    runtime_dir: Path,
    workers: int = WORKERS,
    control_wall_budget_seconds: float = CONTROL_WALL_BUDGET_SECONDS,
) -> dict[str, object]:
    started = time.perf_counter()
    source = Path(__file__).resolve()
    if not source.is_relative_to(repo_root.resolve() / "src"):
        raise CycleError(f"module resolved outside this checkout: {source}")
    if not 1 <= workers <= WORKERS:
        raise CycleError(f"workers must lie in 1..{WORKERS} on the shared workstation")
    quadruples = select_pilot_quadruples()
    if len(set(quadruples)) != QUADRUPLE_SAMPLE_COUNT:
        raise CycleError("pilot quadruples are not distinct")
    runtime_dir.mkdir(parents=True, exist_ok=True)
    draws = ttc.load_draws(BIG_LOTTO_POOL_SIZE)
    primary = run_start(
        START_PRIMARY,
        repo_root,
        quadruples,
        draws=draws,
        runtime_dir=runtime_dir,
        workers=workers,
        with_parity=True,
        incumbent_artifact=incumbent_artifact,
    )
    resolved_artifact = (
        incumbent_artifact
        if incumbent_artifact.is_absolute()
        else repo_root.resolve() / incumbent_artifact
    ).resolve()
    record: dict[str, object] = {
        "TASK_ID": TASK_ID,
        "FAMILY_NAME": FAMILY_NAME,
        "SCIENTIFIC_SCOPE": SCIENTIFIC_SCOPE,
        "EVENT": "OFFICIAL_ANY_PRIZE",
        "PROMOTION_AUTHORITY": "OFFICIAL_ANY_PRIZE",
        "BASELINE_OUTCOMES": V7_BASELINE_OUTCOMES,
        "BASELINE_SHA": V7_BASELINE_SHA256,
        "INCUMBENT_ARTIFACT": str(resolved_artifact.relative_to(repo_root.resolve())),
        "INCUMBENT_ARTIFACT_SHA256": hashlib.sha256(resolved_artifact.read_bytes()).hexdigest(),
        "RESULT_LOCATOR": str(result_path.resolve().relative_to(repo_root.resolve())),
        "RUNNER_HEAD": _git(repo_root, "rev-parse", "HEAD"),
        "RUNNER_TREE": _git(repo_root, "rev-parse", "HEAD^{tree}"),
        "RUN_HEAD": _git(repo_root, "rev-parse", "HEAD"),
        "RUN_TREE": _git(repo_root, "rev-parse", "HEAD^{tree}"),
        "V6_REFERENCE_HEAD": V6_REFERENCE_HEAD,
        "SOURCE_MODULE_PATH": str(source.relative_to(repo_root.resolve())),
        "SOURCE_MODULE_SHA256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "PERMUTATION_FAMILY": {
            "SLOTS": "0,1,2,3 = quadruple positions i<j<k<l of the start's normalized portfolio",
            "IMAGE_RULE": "slot p becomes T_p - x_p + x_q where successor[q] == p",
            "ORIENTATIONS": [
                {"NAME": o.name, "SUCCESSOR": list(o.successor)} for o in ORIENTATIONS
            ],
            "FORWARD": FORWARD.name,
            "REVERSE": REVERSE.name,
            "CYCLE_ORIENTATIONS": CYCLE_ORIENTATIONS,
            "DEFINITION": "every permutation of four slots that is a single 4-cycle",
            "EXCLUDED_DOUBLE_TRANSPOSITIONS": [
                {"NAME": name, "SUCCESSOR": list(successor)}
                for name, successor in EXCLUDED_DOUBLE_TRANSPOSITIONS
            ],
            "EXCLUDED_NOTE": (
                "double transpositions are two independent two-ticket swaps; classified "
                "separately and never generated"
            ),
        },
        "SEARCH_SCOPE": {
            "TICKET_QUADRUPLES": K20_TICKET_QUADRUPLES,
            "NUMBER_SELECTIONS_PER_QUADRUPLE": NUMBER_SELECTIONS_PER_QUADRUPLE,
            "CYCLE_ORIENTATIONS": CYCLE_ORIENTATIONS,
            "RAW_ATTEMPTS_PER_QUADRUPLE": QUADRUPLE_RAW_ATTEMPTS,
            "RAW_FULL_FAMILY_SIZE": K20_RAW_FULL_FAMILY_SIZE,
            "IS_COMPLETE_N4": False,
            "IS_FULL_FOUR_TICKET_JOINT_REPLACEMENT": False,
            "NOTE": "the declared four-ticket single-number 4-cycle family only",
        },
        "PILOT_SEED": PILOT_SEED,
        "QUADRUPLE_SELECTION": (
            "random.Random(seed).sample(all C(20,4) position quadruples, 24), sampled order"
        ),
        "QUADRUPLE_SAMPLE_COUNT": len(quadruples),
        "PILOT_QUADRUPLES": [list(quadruple) for quadruple in quadruples],
        "PILOT_RAW_ATTEMPT_CEILING": PILOT_RAW_ATTEMPT_CEILING,
        "CYCLE_ORIENTATIONS": CYCLE_ORIENTATIONS,
        "WORKERS": workers,
        "PRIMARY": primary,
        "FULL_FOUR_TICKET_FAMILY_STARTED": "NO",
        "GAIN_VS_PROTECTED_LANE_3": "NOT_EVALUATED",
        "PROTECTED_LANE_3_TOUCHED": "NO",
        "NOT_CLAIMED": [
            "complete N4",
            "complete four-ticket joint replacement",
            "four-ticket cycle-family local optimality",
            "full four-ticket cycle-family no-improvement",
            "overall current-best K20",
            "gain versus protected Lane 3",
        ],
    }
    primary_complete = primary.get("STATUS") == "COMPLETE"
    control: dict[str, object] | str = "NOT_RUN"
    if primary_complete:
        primary_wall = _float(primary["PILOT_WALL_SECONDS"])
        record["CONTROL_POLICY"] = (
            f"run the v6 control on the same quadruples iff the primary pilot wall "
            f"<= {control_wall_budget_seconds:.0f} s"
        )
        if primary_wall <= control_wall_budget_seconds:
            control = run_start(
                START_CONTROL,
                repo_root,
                quadruples,
                draws=draws,
                runtime_dir=runtime_dir,
                workers=workers,
                with_parity=False,
            )
        else:
            control = "NOT_RUN_PRIMARY_WALL_ABOVE_BUDGET"
        record["FULL_FAMILY_ESTIMATE"] = full_family_estimate(primary, workers=workers)
    record["CONTROL"] = control

    gain = False
    if primary_complete:
        best = cast(dict[str, object], primary["BEST"])
        parity = cast(dict[str, object], primary["PARITY"])
        estimate = cast(dict[str, object], record["FULL_FAMILY_ESTIMATE"])
        gain = _int(best["COUNT"]) > GAIN_THRESHOLD_COUNT
        record.update(
            TASK_STATUS="COMPLETE",
            SCIENTIFIC_RESULT="STRICT_GAIN" if gain else "TERMINAL_NO_STRICT_GAIN",
            START_COUNT=primary["START_COUNT"],
            START_SHA256=primary["START_SHA256"],
            PARITY_SAMPLE_COUNT=parity["SAMPLE_COUNT"],
            PARITY_MISMATCHES=parity["MISMATCHES"],
            QUADRUPLES_COMPLETED=len(cast(list[object], primary["PER_QUADRUPLE"])),
            RAW_ATTEMPTS=primary["RAW_ATTEMPTS"],
            LEGAL=primary["LEGAL"],
            DEDUPLICATED=primary["DEDUPLICATED"],
            EXACT_SCORED=primary["EXACT_SCORED"],
            WALL_SECONDS=primary["PILOT_WALL_SECONDS"],
            CANDIDATES_PER_SECOND=primary["CANDIDATES_PER_SECOND"],
            BEST_COUNT=best["COUNT"],
            BEST_DELTA=best["DELTA_VS_START"],
            BEST_EXACT_OUTCOMES=best["COUNT"],
            DELTA=best["DELTA_VS_START"],
            BEST_EXACT_PROBABILITY=best["EXACT_PROBABILITY"],
            BEST_SHA256=best["SHA256"],
            BEST_PORTFOLIO_SHA=best["SHA256"],
            PROPOSALS_COMPLETED=primary["EXACT_SCORED"],
            STRICT_GAIN="YES" if gain else "NO",
            BEST_QUADRUPLE=best["QUADRUPLE"],
            BEST_MOVE={
                "NUMBERS": best["NUMBERS"],
                "ORIENTATION": best["ORIENTATION"],
                "REMOVED": best["REMOVED"],
                "ADDED": best["ADDED"],
            },
            BEST_TIE_COUNT=primary["BEST_TIE_COUNT"],
            BEST_CANONICAL_RECOUNT_STATUS=primary["BEST_CANONICAL_RECOUNT_STATUS"],
            FULL_FAMILY_ESTIMATED_WALL_SECONDS=estimate["FULL_FAMILY_ESTIMATED_WALL_SECONDS"],
            NEW_STABLE_NON_LANE3_GAIN="YES" if gain else "NO",
            DECISION="STRICT_GAIN" if gain else "TERMINAL_NO_STRICT_GAIN",
        )
    else:
        record.update(
            TASK_STATUS=str(primary.get("STATUS")),
            NEW_STABLE_NON_LANE3_GAIN="NO",
            STRICT_GAIN="NOT_ESTABLISHED",
            DECISION="NOT_ESTABLISHED",
        )
    peaks = [_peak_rss_bytes(), int(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)]
    for section in (primary, control):
        if isinstance(section, dict) and "WORKER_PEAK_RSS_BYTES" in section:
            peaks.append(_int(section["WORKER_PEAK_RSS_BYTES"]))
    record.update(
        PEAK_MEMORY_BYTES=max(peaks),
        PEAK_MEMORY_DEFINITION="max per-process peak RSS over main and workers",
        TOTAL_RUN_SECONDS=round(time.perf_counter() - started, 3),
    )
    _write_json_atomically(result_path, record)
    return record


def _repo_path(repo_root: Path, value: Path, *, label: str) -> Path:
    root = repo_root.resolve()
    resolved = (root / value if not value.is_absolute() else value).resolve()
    if not resolved.is_relative_to(root):
        raise CycleError(f"{label} must be inside the repository")
    return resolved


def _write_json_durably(path: Path, payload: dict[str, object]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    staging = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    with staging.open("xb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(staging, path)
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    return hashlib.sha256(encoded).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bounded 24-quadruple four-ticket cycle pilot.")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--incumbent-artifact", type=Path, required=True)
    parser.add_argument("--result-path", type=Path, required=True)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    parser.add_argument("--owner-conversation-id", required=True)
    parser.add_argument("--workers", type=int, default=WORKERS)
    parser.add_argument(
        "--control-wall-budget-seconds", type=float, default=CONTROL_WALL_BUDGET_SECONDS
    )
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    incumbent_artifact = _repo_path(repo_root, args.incumbent_artifact, label="incumbent artifact")
    result_path = _repo_path(repo_root, args.result_path, label="result path")
    runtime_dir = _repo_path(repo_root, args.runtime_dir, label="runtime directory")
    owner_path = _repo_path(repo_root, Path(OWNER_RECORD_PATH), label="owner record")
    if not incumbent_artifact.is_file():
        raise CycleError(f"incumbent artifact is missing: {incumbent_artifact}")
    if owner_path.exists():
        raise CycleError(f"owner record already exists; reconcile before resuming: {owner_path}")
    if result_path.exists() or runtime_dir.exists():
        raise CycleError(
            "result or runtime path already exists; refusing to overwrite prior evidence"
        )
    if not args.owner_conversation_id.strip():
        raise CycleError("owner conversation id is required")

    owner_record: dict[str, object] = {
        "OWNER_CONVERSATION_ID": args.owner_conversation_id,
        "TASK_ID": TASK_ID,
        "RUNNER_HEAD": _git(repo_root, "rev-parse", "HEAD"),
        "RUNNER_TREE": _git(repo_root, "rev-parse", "HEAD^{tree}"),
        "PID": os.getpid(),
        "PROTECTED_SUPERVISOR_PID": os.getppid(),
        "CHECKPOINT_LOCATOR": EXECUTION_RECORD_PATH,
        "OWNER_RECORD_LOCATOR": OWNER_RECORD_PATH,
        "RESULT_LOCATOR": str(result_path.relative_to(repo_root)),
        "WRITE_OWNERSHIP": "RETAINED",
        "RESUME_AUTHORITY": (
            f".fable/packets/{TASK_ID}.md and owner conversation "
            f"{args.owner_conversation_id}; reconcile the protected run record before any resume"
        ),
        "BASELINE_OUTCOMES": V7_BASELINE_OUTCOMES,
        "BASELINE_SHA": V7_BASELINE_SHA256,
        "INCUMBENT_ARTIFACT": str(incumbent_artifact.relative_to(repo_root)),
        "INCUMBENT_ARTIFACT_SHA256": hashlib.sha256(incumbent_artifact.read_bytes()).hexdigest(),
        "RUN_STATUS": "STARTING",
        "STARTED_AT_UTC": datetime.now(UTC).isoformat(),
    }
    _write_json_durably(owner_path, owner_record)
    try:
        record = run_pilot(
            repo_root,
            incumbent_artifact=incumbent_artifact,
            result_path=result_path,
            runtime_dir=runtime_dir,
            workers=args.workers,
            control_wall_budget_seconds=args.control_wall_budget_seconds,
        )
    except BaseException as error:
        owner_record.update(
            RUN_STATUS="FAILED",
            WRITE_OWNERSHIP="RELEASED",
            FAILURE=f"{type(error).__name__}: {error}",
            ENDED_AT_UTC=datetime.now(UTC).isoformat(),
        )
        _write_json_durably(owner_path, owner_record)
        raise
    digest = hashlib.sha256(result_path.read_bytes()).hexdigest()
    owner_record.update(
        RUN_STATUS=record.get("TASK_STATUS"),
        STRICT_GAIN=record.get("STRICT_GAIN", "NOT_ESTABLISHED"),
        RESULT_SHA256=digest,
        WRITE_OWNERSHIP="RELEASED",
        ENDED_AT_UTC=datetime.now(UTC).isoformat(),
    )
    _write_json_durably(owner_path, owner_record)
    summary = {
        key: record.get(key)
        for key in (
            "TASK_STATUS",
            "DECISION",
            "STRICT_GAIN",
            "PROPOSALS_COMPLETED",
            "BEST_EXACT_OUTCOMES",
            "DELTA",
            "BEST_PORTFOLIO_SHA",
        )
    }
    summary["RESULT_SHA256"] = digest
    print(json.dumps(summary, sort_keys=True))
    return 0 if record["TASK_STATUS"] == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
