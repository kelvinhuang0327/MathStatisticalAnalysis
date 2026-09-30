"""B649_K20_GLOBAL_RESIDUAL_POOL_REPAIR_PILOT_R1: globally ranked residual pools for K20 repair.

Question: starting from the pinned 313239661 K20 portfolio, freeze 15 or 16 tickets (``R``), score
EVERY one of the C(49,6) = 13,983,816 legal tickets against ``R`` exactly, keep the 48 tickets
with the highest residual marginal, add the removed and pinned-elite tickets (cap 64) and
re-choose the 4 or 5 replacements exactly within that pool. The claim is limited to the six
pre-persisted destroy sets and their declared pools; it is not a complete-N4 or N5 search.

Exactness. A ticket ``t`` wins outcome (main draw ``D``, special ``s``) exactly when
``|t & E| >= 3`` for the 7-subset ``E = D | {s}`` (see the five-ticket module), and every ``E``
stands for 7 outcomes. Let ``H`` be the triples contained in the tickets of ``R``. ``R`` wins
``E`` exactly when ``E`` contains a triple of ``H``; ``U`` is the set of the other ``E``. The
residual marginal of a ticket is ``m(t) = #{E in U : |E & t| >= 3}``.

Global scoring. Moebius inversion over the subsets ``B`` of ``t`` gives
``m(t) = sum_{B <= t, |B| >= 3} c(|B|) g(B)`` with ``c = (1, -3, 6, -10)`` for ``|B| = 3..6``
and ``g(B) = #{E in U : B <= E}``. For a full ticket, ``g(t)`` counts the numbers ``x`` outside
``t`` for which ``t + {x}`` still holds no triple of ``H``: zero when ``t`` holds a triple of
``H``, else ``pool - 6 - |union of pair links|``, where the link of a pair is the set of numbers
that complete it to a triple of ``H``. Smaller ``g`` follow exactly from
``g(B) = sum_x g(B + {x}) / (7 - |B|)``. Every ticket is scored in integer arithmetic in
vectorised blocks; nothing prefilters or samples. Two exact identities guard each pass:
``sum_t g(t) = 7 |U|`` and ``sum_t m(t) = K |U|``, where ``K`` is the number of tickets that
share at least three numbers with one 7-subset.

Search. The repair pool is solved exactly by branch and bound: pruning only by the submodular
remaining-slot bound, the last two slots by an exact weighted Gram completion, every optimal set
kept so ties break on the lowest portfolio SHA-256. ``PROVEN_OPTIMAL`` means proven inside the
pool only.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import random
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from math import comb
from pathlib import Path
from typing import Final, cast

import numpy as np
import numpy.typing as npt

from lottolab.research.b649_k20_five_ticket_exact_repair_r1 import (
    BIG_LOTTO_GEOMETRY,
    OPTIMALITY_FEASIBLE,
    OPTIMALITY_PROVEN,
    PINNED_ELITES,
    PORTFOLIO_SIZE,
    SOURCE_ARTIFACT,
    SOURCE_COMMIT,
    START_COUNT,
    START_PORTFOLIO,
    START_SHA256,
    CanonicalRecounter,
    DestroyedPortfolio,
    FloatArray,
    Geometry,
    MaskArray,
    ParityReport,
    PoolHistogram,
    Portfolio,
    Ticket,
    WeightArray,
    assemble_pool,
    canonical_json,
    destroy_positions,
    direct_marginals,
    evaluate_set,
    iter_subset_mask_blocks,
    normalize_portfolio,
    outcome_count,
    peak_memory_bytes,
    portfolio_sha256,
    record_progress,
    remaining_slot_upper_bound,
    restrict_histogram,
    sample_destroy_quintuples,
    solve_exact_repair,
    verify_pins,
    write_atomically,
)
from lottolab.research.b649_official_any_prize_exact import (
    BIG_LOTTO_DRAW_SIZE,
    BIG_LOTTO_OUTRIGHT_MATCHES,
    BIG_LOTTO_POOL_SIZE,
    ticket_mask,
)

type SubsetTable = npt.NDArray[np.uint8]
type RowArray = npt.NDArray[np.uint8] | npt.NDArray[np.int64]
type IndexArray = npt.NDArray[np.int64]
type CountArray = npt.NDArray[np.int32]
type LinkTable = npt.NDArray[np.uint64]
type BinomialTable = npt.NDArray[np.int64]

TASK_ID: Final = "B649_K20_GLOBAL_RESIDUAL_POOL_REPAIR_PILOT_R1"

TICKET_SIZE: Final = BIG_LOTTO_DRAW_SIZE
SUBSET_SIZE: Final = TICKET_SIZE + 1
OUTRIGHT: Final = BIG_LOTTO_OUTRIGHT_MATCHES
POOL_SIZE: Final = BIG_LOTTO_POOL_SIZE
TOTAL_TICKETS: Final = comb(POOL_SIZE, TICKET_SIZE)
BLOCK_ROWS: Final = 1 << 19
LIFT_CHUNK_ROWS: Final = 1 << 19


def residual_coefficient(size: int) -> int:
    """Coefficient of ``g(B)`` with ``|B| = size``: ``sum_{j >= 3} (-1)^(size - j) C(size, j)``."""

    return sum((-1) ** (size - j) * comb(size, j) for j in range(OUTRIGHT, size + 1))


RESIDUAL_COEFFICIENTS: Final = {
    size: residual_coefficient(size) for size in range(OUTRIGHT, TICKET_SIZE + 1)
}


def tickets_hitting_each_subset(pool_size: int = POOL_SIZE) -> int:
    """Tickets that share at least ``OUTRIGHT`` numbers with one fixed 7-subset of the pool."""

    return sum(
        comb(SUBSET_SIZE, j) * comb(pool_size - SUBSET_SIZE, TICKET_SIZE - j)
        for j in range(OUTRIGHT, TICKET_SIZE + 1)
    )


# ---------------------------------------------------------------------------------------------
# colexicographic subset tables
# ---------------------------------------------------------------------------------------------


def colex_subsets(pool_size: int, size: int) -> SubsetTable:
    """Every ``size``-subset of ``range(pool_size)`` as an ascending row, in colex order.

    Row ``i`` has colexicographic rank ``i``. The rows whose largest element is ``top`` are the
    ``(size - 1)``-subsets of ``range(top)``, a prefix of the smaller table, so building the table
    needs no per-subset Python work.
    """

    if size == 0:
        return np.zeros((1, 0), dtype=np.uint8)
    if pool_size < size:
        return np.empty((0, size), dtype=np.uint8)
    lower = colex_subsets(pool_size - 1, size - 1)
    pieces: list[SubsetTable] = []
    for top in range(size - 1, pool_size):
        count = comb(top, size - 1)
        piece = np.empty((count, size), dtype=np.uint8)
        piece[:, : size - 1] = lower[:count]
        piece[:, size - 1] = top
        pieces.append(piece)
    return np.concatenate(pieces)


def colex_rank(binomial: BinomialTable, rows: RowArray) -> IndexArray:
    """Colexicographic rank of each ascending row: ``sum_j C(row[j], j + 1)``."""

    ranks: IndexArray = np.zeros(rows.shape[0], dtype=np.int64)
    for position in range(rows.shape[1]):
        ranks += binomial[position + 1][rows[:, position]]
    return ranks


@dataclass(frozen=True, slots=True, eq=False)
class ColexUniverse:
    """Colex tables of the 3- to 6-subsets of ``range(pool_size)`` and the binomial lookup."""

    pool_size: int
    tables: dict[int, SubsetTable]
    binomial: BinomialTable

    @property
    def tickets(self) -> SubsetTable:
        """Every legal ticket (0-based, ascending rows) in colex order: row ``i`` has rank ``i``."""

        return self.tables[TICKET_SIZE]

    def index_of(self, ticket: Ticket) -> int:
        """Colex rank of a 1-based ticket."""

        numbers = sorted(number - 1 for number in ticket)
        if len(numbers) != TICKET_SIZE or len(set(numbers)) != TICKET_SIZE:
            raise ValueError(f"illegal ticket: {ticket}")
        if numbers[0] < 0 or numbers[-1] >= self.pool_size:
            raise ValueError(f"ticket outside the pool: {ticket}")
        return sum(comb(number, position + 1) for position, number in enumerate(numbers))

    def ticket_at(self, index: int) -> Ticket:
        """The 1-based ticket with colex rank ``index``."""

        return tuple(int(number) + 1 for number in self.tickets[index])


def build_universe(pool_size: int = POOL_SIZE) -> ColexUniverse:
    """Build the colex tables for a pool; tests use small pools, the pilot uses 49."""

    if not SUBSET_SIZE <= pool_size <= 64:
        raise ValueError("pool must satisfy 7 <= pool_size <= 64")
    tables = {size: colex_subsets(pool_size, size) for size in range(OUTRIGHT, TICKET_SIZE + 1)}
    binomial = np.array(
        [[comb(value, m) for value in range(pool_size)] for m in range(TICKET_SIZE + 1)],
        dtype=np.int64,
    )
    return ColexUniverse(pool_size=pool_size, tables=tables, binomial=binomial)


# ---------------------------------------------------------------------------------------------
# global residual scoring
# ---------------------------------------------------------------------------------------------


def build_pair_links(remaining: Sequence[Ticket], pool_size: int) -> LinkTable:
    """``links[a, b]``: bitmask of the numbers ``x`` with ``{a, b, x}`` inside a frozen ticket."""

    links: LinkTable = np.zeros((pool_size, pool_size), dtype=np.uint64)
    for ticket in remaining:
        numbers = [number - 1 for number in ticket]
        for triple in itertools.combinations(numbers, OUTRIGHT):
            for third in range(OUTRIGHT):
                completing = triple[third]
                first, second = (triple[i] for i in range(OUTRIGHT) if i != third)
                links[first, second] |= np.uint64(1 << completing)
                links[second, first] |= np.uint64(1 << completing)
    return links


def _free_extension_counts(
    rows: npt.NDArray[np.int64], links: LinkTable, pool_size: int
) -> CountArray:
    """``g(t)`` per ticket row: numbers ``x`` outside ``t`` that keep ``t + {x}`` triple-free."""

    forbidden: LinkTable = np.zeros(rows.shape[0], dtype=np.uint64)
    occupied: LinkTable = np.zeros(rows.shape[0], dtype=np.uint64)
    one = np.uint64(1)
    for first in range(TICKET_SIZE):
        occupied |= one << rows[:, first].astype(np.uint64)
        for second in range(first + 1, TICKET_SIZE):
            forbidden |= links[rows[:, first], rows[:, second]]
    clash = (forbidden & occupied) != 0
    free = (pool_size - TICKET_SIZE) - np.bitwise_count(forbidden).astype(np.int64)
    return np.where(clash, 0, free).astype(np.int32)


def _lift(universe: ColexUniverse, upper: CountArray, size: int) -> CountArray:
    """``g`` on the ``size``-subsets from ``g`` on the ``(size + 1)``-subsets.

    Every 7-subset ``E`` containing ``B`` reaches ``7 - size`` supersets ``B + {x}`` inside it, so
    ``g(B) = sum_x g(B + {x}) / (7 - size)`` exactly; the division is asserted to be exact.
    """

    pool_size, binomial = universe.pool_size, universe.binomial
    table = universe.tables[size]
    divisor = SUBSET_SIZE - size
    result: CountArray = np.empty(table.shape[0], dtype=np.int32)
    for start in range(0, table.shape[0], LIFT_CHUNK_ROWS):
        rows = table[start : start + LIFT_CHUNK_ROWS].astype(np.int64)
        count = rows.shape[0]
        # prefix[:, p]: ranks of the first p elements in place; suffix[:, p]: the rest, shifted
        prefix = np.zeros((count, size + 1), dtype=np.int64)
        suffix = np.zeros((count, size + 1), dtype=np.int64)
        for i in range(size):
            prefix[:, i + 1] = prefix[:, i] + binomial[i + 1][rows[:, i]]
        for i in range(size - 1, -1, -1):
            suffix[:, i] = suffix[:, i + 1] + binomial[i + 2][rows[:, i]]
        lines: IndexArray = np.arange(count, dtype=np.int64)
        total = np.zeros(count, dtype=np.int64)
        for number in range(pool_size):
            below = (rows < number).sum(axis=1)
            present = (rows == number).any(axis=1)
            rank = prefix[lines, below] + binomial[:, number][below + 1] + suffix[lines, below]
            total += np.where(present, 0, upper[np.where(present, 0, rank)])
        if (total % divisor).any():
            raise AssertionError("g lifting is not an exact integer division")
        result[start : start + count] = total // divisor
    return result


def _block_marginals(
    universe: ColexUniverse,
    rows: npt.NDArray[np.int64],
    levels: dict[int, CountArray],
    top_counts: CountArray,
) -> CountArray:
    """``m(t) = sum_B c(|B|) g(B)`` for a block of ticket rows (``levels`` holds ``g`` for 3..5)."""

    binomial = universe.binomial
    terms = {
        (place, position): binomial[place + 1][rows[:, position]]
        for place in range(TICKET_SIZE)
        for position in range(place, TICKET_SIZE)
    }
    total = RESIDUAL_COEFFICIENTS[TICKET_SIZE] * top_counts.astype(np.int64)
    for size in range(OUTRIGHT, TICKET_SIZE):
        gathered = np.zeros(rows.shape[0], dtype=np.int64)
        for chosen in itertools.combinations(range(TICKET_SIZE), size):
            rank = terms[(0, chosen[0])].copy()
            for place in range(1, size):
                rank += terms[(place, chosen[place])]
            gathered += levels[size][rank]
        total += RESIDUAL_COEFFICIENTS[size] * gathered
    return total.astype(np.int32)


@dataclass(frozen=True, slots=True, eq=False)
class GlobalScores:
    """Exact residual marginal (in 7-subsets) of every legal ticket, indexed by colex rank."""

    marginals: CountArray
    tickets_scored: int
    sum_top_counts: int
    sum_marginals: int
    seconds: float


def score_all_tickets(universe: ColexUniverse, remaining: Sequence[Ticket]) -> GlobalScores:
    """Score every legal ticket against ``remaining`` (``R``); no filter runs before this pass."""

    started = time.perf_counter()
    pool_size = universe.pool_size
    tickets = universe.tickets
    total = tickets.shape[0]
    links = build_pair_links(remaining, pool_size)
    top_counts: CountArray = np.empty(total, dtype=np.int32)
    for start in range(0, total, BLOCK_ROWS):
        rows = tickets[start : start + BLOCK_ROWS].astype(np.int64)
        top_counts[start : start + rows.shape[0]] = _free_extension_counts(rows, links, pool_size)
    levels: dict[int, CountArray] = {}
    upper = top_counts
    for size in range(TICKET_SIZE - 1, OUTRIGHT - 1, -1):
        upper = _lift(universe, upper, size)
        levels[size] = upper
    marginals: CountArray = np.empty(total, dtype=np.int32)
    scored = 0
    for start in range(0, total, BLOCK_ROWS):
        rows = tickets[start : start + BLOCK_ROWS].astype(np.int64)
        block_top = top_counts[start : start + rows.shape[0]]
        marginals[start : start + rows.shape[0]] = _block_marginals(
            universe, rows, levels, block_top
        )
        scored += rows.shape[0]
    return GlobalScores(
        marginals=marginals,
        tickets_scored=scored,
        sum_top_counts=int(top_counts.sum(dtype=np.int64)),
        sum_marginals=int(marginals.sum(dtype=np.int64)),
        seconds=time.perf_counter() - started,
    )


def check_score_identities(
    scores: GlobalScores, universe: ColexUniverse, residual_subsets: int
) -> dict[str, object]:
    """Verify the two exact global identities; ``residual_subsets`` is ``|U|`` counted directly."""

    expected_top = SUBSET_SIZE * residual_subsets
    expected_marginals = tickets_hitting_each_subset(universe.pool_size) * residual_subsets
    record: dict[str, object] = {
        "TICKETS_SCORED": scores.tickets_scored,
        "TICKETS_EXPECTED": int(universe.tickets.shape[0]),
        "RESIDUAL_SUBSETS": residual_subsets,
        "SUM_TOP_COUNTS": scores.sum_top_counts,
        "SUM_TOP_COUNTS_EXPECTED": expected_top,
        "SUM_MARGINALS": scores.sum_marginals,
        "SUM_MARGINALS_EXPECTED": expected_marginals,
    }
    passed = (
        scores.tickets_scored == universe.tickets.shape[0]
        and scores.sum_top_counts == expected_top
        and scores.sum_marginals == expected_marginals
    )
    record["PASS"] = passed
    if not passed:
        raise AssertionError(f"global score identities failed: {record}")
    return record


# ---------------------------------------------------------------------------------------------
# exact global ranking
# ---------------------------------------------------------------------------------------------

GLOBAL_TOP_MARGINAL: Final = 48
REPAIR_POOL_MAX: Final = 64
TIE_LIMIT: Final = 100_000


def _lexicographic_order(rows: SubsetTable) -> IndexArray:
    """Permutation that sorts ticket rows lexicographically (column 0 is the primary key)."""

    return np.lexsort(rows.T[::-1])


def top_ticket_indices(marginals: CountArray, tickets: SubsetTable, count: int) -> IndexArray:
    """Colex indices of the ``count`` best tickets in rank order.

    Rank is the residual marginal, highest first, ties to the lexicographically lowest ticket. The
    threshold value is found on the whole array, so the selection is the true top ``count``.
    """

    total = int(marginals.size)
    if not 1 <= count <= total:
        raise ValueError("count must be within 1..number of tickets")
    if count == total:
        candidates: IndexArray = np.arange(total, dtype=np.int64)
    else:
        threshold = np.partition(marginals, total - count)[total - count]
        above = np.flatnonzero(marginals > threshold)
        tied = np.flatnonzero(marginals == threshold)
        tied = tied[_lexicographic_order(tickets[tied])][: count - above.size]
        candidates = np.concatenate((above, tied))
    rows = tickets[candidates]
    keys = (*(rows[:, column] for column in range(TICKET_SIZE - 1, -1, -1)), -marginals[candidates])
    return candidates[np.lexsort(keys)]


def exact_global_rank(marginals: CountArray, tickets: SubsetTable, index: int) -> int:
    """Exact 1-based rank of one ticket among ALL tickets (marginal desc, then lexicographic)."""

    value = marginals[index]
    greater = int(np.count_nonzero(marginals > value))
    rows = tickets[np.flatnonzero(marginals == value)]
    target = tickets[index]
    earlier = np.zeros(rows.shape[0], dtype=np.bool_)
    equal_so_far = np.ones(rows.shape[0], dtype=np.bool_)
    for column in range(TICKET_SIZE):
        earlier |= equal_so_far & (rows[:, column] < target[column])
        equal_so_far &= rows[:, column] == target[column]
    return 1 + greater + int(np.count_nonzero(earlier))


@dataclass(frozen=True, slots=True)
class RankedTicket:
    """One ticket with its exact residual marginal (7-subsets) and exact global rank."""

    ticket: Ticket
    marginal: int
    rank: int


def global_top(
    universe: ColexUniverse, scores: GlobalScores, count: int = GLOBAL_TOP_MARGINAL
) -> tuple[RankedTicket, ...]:
    """The true top ``count`` tickets after scoring the complete legal universe."""

    if scores.tickets_scored != universe.tickets.shape[0]:
        raise AssertionError("the complete ticket universe has not been scored")
    indices = top_ticket_indices(scores.marginals, universe.tickets, count)
    return tuple(
        RankedTicket(universe.ticket_at(int(index)), int(scores.marginals[index]), rank)
        for rank, index in enumerate(indices, start=1)
    )


def ranked(universe: ColexUniverse, scores: GlobalScores, ticket: Ticket) -> RankedTicket:
    """A ticket's exact marginal and exact global rank."""

    index = universe.index_of(ticket)
    rank = exact_global_rank(scores.marginals, universe.tickets, index)
    return RankedTicket(tuple(sorted(ticket)), int(scores.marginals[index]), rank)


# ---------------------------------------------------------------------------------------------
# repair pool: removed tickets, then pinned elites, then the global ranking
# ---------------------------------------------------------------------------------------------

SOURCE_REMOVED: Final = "A_REMOVED"
SOURCE_ELITE: Final = "B_ELITE"
SOURCE_GLOBAL: Final = "C_GLOBAL"


@dataclass(frozen=True, slots=True)
class PoolMember:
    """One repair-pool ticket: the first retention group that claimed it and its exact scores."""

    ticket: Ticket
    source: str
    marginal: int
    global_rank: int
    in_global_top: bool


@dataclass(frozen=True, slots=True)
class GlobalPoolPlan:
    """The capped repair pool of one destroy set, in canonical ticket order."""

    destroyed: DestroyedPortfolio
    members: tuple[PoolMember, ...]
    top: tuple[RankedTicket, ...]
    union_size: int
    dropped: tuple[Ticket, ...]

    @property
    def tickets(self) -> Portfolio:
        return tuple(member.ticket for member in self.members)

    def source_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for member in self.members:
            counts[member.source] = counts.get(member.source, 0) + 1
        return dict(sorted(counts.items()))


def assemble_global_pool(
    universe: ColexUniverse,
    scores: GlobalScores,
    destroyed: DestroyedPortfolio,
    *,
    elites: Sequence[Portfolio],
    top_count: int = GLOBAL_TOP_MARGINAL,
    pool_max: int = REPAIR_POOL_MAX,
) -> GlobalPoolPlan:
    """Union of A removed, B pinned-elite and C global-top tickets, capped at ``pool_max``.

    A frozen ticket never joins the pool. Duplicates keep the first group that claims them. When the
    union exceeds the cap, tickets are kept in the order A, B, C (C by global rank).
    """

    frozen = set(destroyed.remaining)
    removed = set(destroyed.removed)
    top = global_top(universe, scores, top_count)
    groups = (
        (SOURCE_REMOVED, list(destroyed.removed)),
        (
            SOURCE_ELITE,
            sorted({t for elite in elites for t in elite} - frozen - removed),
        ),
        (SOURCE_GLOBAL, [entry.ticket for entry in top if entry.ticket not in frozen]),
    )
    ordered: list[tuple[Ticket, str]] = []
    seen: set[Ticket] = set()
    for source, tickets in groups:
        for ticket in tickets:
            if ticket not in seen:
                seen.add(ticket)
                ordered.append((ticket, source))
    top_tickets = {entry.ticket for entry in top}
    members: list[PoolMember] = []
    for ticket, source in ordered[:pool_max]:
        scored = ranked(universe, scores, ticket)
        members.append(
            PoolMember(ticket, source, scored.marginal, scored.rank, ticket in top_tickets)
        )
    members.sort(key=lambda member: member.ticket)
    return GlobalPoolPlan(
        destroyed=destroyed,
        members=tuple(members),
        top=top,
        union_size=len(ordered),
        dropped=tuple(ticket for ticket, _ in ordered[pool_max:]),
    )


# ---------------------------------------------------------------------------------------------
# residual histogram over a pool of up to 64 tickets
# ---------------------------------------------------------------------------------------------


def _merge_rows(keys: MaskArray, counts: WeightArray) -> tuple[MaskArray, WeightArray]:
    """Sum the counts of equal keys exactly (integer arithmetic); the result is sorted by key."""

    if keys.size == 0:
        return keys, counts
    order = np.argsort(keys, kind="stable")
    keys, counts = keys[order], counts[order]
    starts = np.concatenate(([0], np.flatnonzero(np.diff(keys)) + 1))
    return keys[starts], np.add.reduceat(counts, starts)


def build_repair_histogram(
    remaining: Sequence[Ticket],
    pool: Sequence[Ticket],
    *,
    geometry: Geometry = BIG_LOTTO_GEOMETRY,
) -> PoolHistogram:
    """One exact pass over all 7-subsets: winner-mask histogram of ``pool`` against ``R``."""

    if not 1 <= len(pool) <= REPAIR_POOL_MAX:
        raise ValueError("the pool must hold between 1 and 64 tickets (one uint64 winner mask)")
    remaining_masks = [np.uint64(ticket_mask(ticket)) for ticket in remaining]
    pool_masks = [np.uint64(ticket_mask(ticket)) for ticket in pool]
    partial_keys: list[MaskArray] = []
    partial_counts: list[WeightArray] = []
    total = 0
    covered_total = 0
    for block in iter_subset_mask_blocks(geometry.pool_size, geometry.subset_size):
        covered = np.zeros(block.size, dtype=np.bool_)
        for mask in remaining_masks:
            covered |= np.bitwise_count(block & mask) >= geometry.outright
        residual = block[~covered]
        total += int(block.size)
        covered_total += int(block.size - residual.size)
        winners: MaskArray = np.zeros(residual.size, dtype=np.uint64)
        for index, mask in enumerate(pool_masks):
            wins = np.bitwise_count(residual & mask) >= geometry.outright
            winners |= wins.astype(np.uint64) << np.uint64(index)
        keys, counts = np.unique(winners, return_counts=True)
        partial_keys.append(keys)
        partial_counts.append(counts.astype(np.int64))
    if total != geometry.subset_count:
        raise AssertionError("subset enumeration did not cover the whole subset space")
    merged_keys, merged_counts = _merge_rows(
        np.concatenate(partial_keys), np.concatenate(partial_counts)
    )
    live = merged_keys != 0
    return PoolHistogram(
        geometry=geometry,
        pool=tuple(pool),
        masks=merged_keys[live],
        weights=merged_counts[live],
        total_subsets=total,
        covered_by_remaining=covered_total,
        dead_subsets=int(merged_counts[~live].sum()),
    )


# ---------------------------------------------------------------------------------------------
# exact branch and bound that keeps every optimal set
# ---------------------------------------------------------------------------------------------


class _DeadlineExpiredError(Exception):
    """The wall limit ended the search before a proof."""


class TieLimitExceededError(Exception):
    """More optimal sets than the tie list may hold; the SHA tie-break would not be exact."""


@dataclass(frozen=True, slots=True)
class PoolSolve:
    """Outcome of one exact pool solve; values are residual 7-subset counts."""

    status: str
    best_value: int
    best_set: tuple[int, ...]
    optimal_sets: tuple[tuple[int, ...], ...]
    start_value: int
    nodes_explored: int
    nodes_pruned: int
    leaf_sets_evaluated: int
    sets_pruned: int
    total_sets: int
    seconds: float

    @property
    def improved(self) -> bool:
        return self.best_value > self.start_value

    @property
    def unresolved_sets(self) -> int:
        return self.total_sets - self.leaf_sets_evaluated - self.sets_pruned


class _TieSearch:
    """Depth-first branch and bound in solver order; prunes only sets that cannot reach the best."""

    def __init__(
        self,
        bits: FloatArray,
        weights: FloatArray,
        pick: int,
        start_value: int,
        deadline: float | None,
        use_bound: bool,
        clock: Callable[[], float],
        tie_limit: int,
    ) -> None:
        self.pool_count = int(bits.shape[1])
        self.pick = pick
        self.deadline = deadline
        self.use_bound = use_bound
        self.clock = clock
        self.tie_limit = tie_limit
        self.best_value = start_value
        self.optimal: list[tuple[int, ...]] = []
        self.nodes_explored = 0
        self.nodes_pruned = 0
        self.leaves = 0
        self.pruned = 0
        self._root_bits = bits
        self._root_weights = weights

    def run(self) -> None:
        self._descend((), 0, self._root_bits, self._root_weights, 0)

    def _record(self, value: int, chosen: tuple[int, ...]) -> None:
        if value > self.best_value:
            self.best_value = value
            self.optimal = [chosen]
        elif value == self.best_value:
            self.optimal.append(chosen)
            if len(self.optimal) > self.tie_limit:
                raise TieLimitExceededError

    def _descend(
        self,
        chosen: tuple[int, ...],
        base: int,
        bits: FloatArray,
        weights: FloatArray,
        covered: int,
    ) -> None:
        if self.deadline is not None and self.clock() > self.deadline:
            raise _DeadlineExpiredError
        slots = self.pick - len(chosen)
        width = self.pool_count - base
        if slots > width:
            return
        self.nodes_explored += 1
        gains: FloatArray = weights @ bits
        if slots == 1:
            top = float(gains.max())
            self.leaves += width
            if covered + round(top) >= self.best_value:
                for column in np.flatnonzero(gains == top):
                    self._record(covered + round(top), (*chosen, base + int(column)))
            return
        # strict "<": a set that can only tie the best is still a candidate for the SHA tie-break
        if self.use_bound and covered + remaining_slot_upper_bound(gains, slots) < self.best_value:
            self.nodes_pruned += 1
            self.pruned += comb(width, slots)
            return
        if slots == 2:
            weighted = bits * weights[:, None]
            overlap: FloatArray = weighted.T @ bits
            pair_total = gains[:, None] + gains[None, :] - overlap
            rows, cols = np.triu_indices(width, 1)
            values = pair_total[rows, cols]
            top = float(values.max())
            self.leaves += comb(width, 2)
            if covered + round(top) >= self.best_value:
                for position in np.flatnonzero(values == top):
                    pair = (base + int(rows[position]), base + int(cols[position]))
                    self._record(covered + round(top), (*chosen, *pair))
            return
        for offset in range(width - slots + 1):
            gain = round(float(gains[offset]))
            bound = remaining_slot_upper_bound(gains[offset + 1 :], slots - 1)
            if self.use_bound and covered + gain + bound < self.best_value:
                self.nodes_pruned += 1
                self.pruned += comb(width - 1 - offset, slots - 1)
                continue
            tail = bits[:, offset + 1 :]
            keep = (bits[:, offset] == 0) & tail.any(axis=1)
            self._descend(
                (*chosen, base + offset),
                base + offset + 1,
                tail[keep],
                weights[keep],
                covered + gain,
            )


def solve_pool_exact(
    masks: MaskArray,
    weights: WeightArray,
    pool_count: int,
    pick: int,
    start_set: Sequence[int],
    tie_key: Callable[[tuple[int, ...]], str],
    *,
    deadline: float | None = None,
    use_bound: bool = True,
    clock: Callable[[], float] = time.perf_counter,
    tie_limit: int = TIE_LIMIT,
) -> PoolSolve:
    """Best ``pick``-subset of the pool by covered weight; every optimal set is kept.

    ``tie_key`` maps a set of pool indices to the string the ties are ordered by (the portfolio
    SHA-256); the lowest wins. ``start_set`` is only the initial incumbent value, so the search
    proves the optimum of the whole pool. ``PROVEN_OPTIMAL`` only when the search ran to completion;
    an expired ``deadline`` reports ``FEASIBLE_ONLY`` and never claims the tie-break is exact.
    """

    if not 1 <= pick <= pool_count <= REPAIR_POOL_MAX or len(set(start_set)) != pick:
        raise ValueError("invalid pool or start set")
    started = clock()
    start = tuple(sorted(start_set))
    start_value = evaluate_set(masks, weights, start)
    shifts = np.arange(pool_count, dtype=np.uint64)
    raw_bits: FloatArray = ((masks[:, None] >> shifts[None, :]) & np.uint64(1)).astype(np.float64)
    raw_weights: FloatArray = weights.astype(np.float64)
    order = np.argsort(-(raw_weights @ raw_bits), kind="stable")
    search = _TieSearch(
        raw_bits[:, order], raw_weights, pick, start_value, deadline, use_bound, clock, tie_limit
    )
    status = OPTIMALITY_PROVEN
    try:
        search.run()
    except _DeadlineExpiredError:
        status = OPTIMALITY_FEASIBLE
    if status == OPTIMALITY_PROVEN and not search.optimal:
        raise AssertionError("a completed search must reach the incumbent value")
    found = {tuple(sorted(int(order[place]) for place in chosen)) for chosen in search.optimal}
    optimal_sets = tuple(sorted(found, key=tie_key)) or (start,)
    return PoolSolve(
        status=status,
        best_value=search.best_value,
        best_set=optimal_sets[0],
        optimal_sets=optimal_sets,
        start_value=start_value,
        nodes_explored=search.nodes_explored,
        nodes_pruned=search.nodes_pruned,
        leaf_sets_evaluated=search.leaves,
        sets_pruned=search.pruned,
        total_sets=comb(pool_count, pick),
        seconds=clock() - started,
    )


# ---------------------------------------------------------------------------------------------
# stop conditions, baseline identity and destroy samples
# ---------------------------------------------------------------------------------------------

REPO_ROOT: Final = Path(__file__).resolve().parents[3]
PILOT_SEED: Final = 20261002
DESTROY_SIZES: Final = (4, 5)
PILOT_SETS_PER_SIZE: Final = 3
PARITY_SETS_PER_SIZE: Final = 2
REPAIR_SOLVE_WALL_LIMIT_SECONDS: Final = 30 * 60
SAMPLING_METHOD: Final = "smallest sha256(f'{seed}:{comma-joined positions}') over C(20,d)"

type DestroySets = dict[int, tuple[tuple[int, ...], ...]]


class StopConditionError(RuntimeError):
    """A Packet STOP condition fired; ``code`` is the exact stop token."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _as_int(value: object) -> int:
    if not isinstance(value, int):
        raise TypeError(f"expected an integer, got {type(value).__name__}")
    return value


def _tickets_from(value: object) -> Portfolio:
    if not isinstance(value, list):
        raise StopConditionError("START_BASELINE_MISMATCH", "the source portfolio is not a list")
    tickets = [tuple(_as_int(number) for number in raw) for raw in cast(list[list[object]], value)]
    return normalize_portfolio(tickets)


def read_source_artifact(repo_root: Path = REPO_ROOT) -> dict[str, object]:
    """The START source artifact from the pinned commit (read-only ``git show``)."""

    target = f"{SOURCE_COMMIT}:{SOURCE_ARTIFACT}"
    probe = subprocess.run(
        ["git", "cat-file", "-e", target], cwd=repo_root, capture_output=True, check=False
    )
    if probe.returncode != 0:
        raise StopConditionError("MISSING_SOURCE_COMMIT", SOURCE_COMMIT)
    shown = subprocess.run(["git", "show", target], cwd=repo_root, capture_output=True, check=True)
    document: object = json.loads(shown.stdout)
    if not isinstance(document, dict):
        raise StopConditionError("START_BASELINE_MISMATCH", "the source artifact is not an object")
    return cast(dict[str, object], document)


def reproduce_start(
    recounter: CanonicalRecounter, repo_root: Path = REPO_ROOT
) -> dict[str, object]:
    """Reproduce the 20-ticket start from its source commit and recount it canonically."""

    source = read_source_artifact(repo_root)
    embedded = normalize_portfolio(START_PORTFOLIO)
    from_source = _tickets_from(source.get("BEST_PORTFOLIO"))
    recount = recounter.count(embedded)
    record: dict[str, object] = {
        "START_COUNT": START_COUNT,
        "START_SHA256": START_SHA256,
        "SOURCE_COMMIT": SOURCE_COMMIT,
        "SOURCE_ARTIFACT": SOURCE_ARTIFACT,
        "SOURCE_ARTIFACT_BEST_COUNT": source.get("BEST_COUNT"),
        "SOURCE_ARTIFACT_BEST_SHA256": source.get("BEST_PORTFOLIO_SHA256"),
        "EMBEDDED_SHA256": portfolio_sha256(embedded),
        "SOURCE_PORTFOLIO_SHA256": portfolio_sha256(from_source),
        "CANONICAL_RECOUNT": recount,
        "TICKET_COUNT": len(embedded),
    }
    match = (
        len(embedded) == PORTFOLIO_SIZE
        and from_source == embedded
        and recount == START_COUNT
        and record["EMBEDDED_SHA256"] == START_SHA256
        and record["SOURCE_PORTFOLIO_SHA256"] == START_SHA256
        and record["SOURCE_ARTIFACT_BEST_SHA256"] == START_SHA256
        and record["SOURCE_ARTIFACT_BEST_COUNT"] == START_COUNT
    )
    record["MATCH"] = match
    if not match:
        raise StopConditionError("START_BASELINE_MISMATCH", json.dumps(record, default=str))
    return record


def ranked_destroy_sets(count: int, *, seed: int = PILOT_SEED) -> DestroySets:
    """The ``count`` smallest-hash destroy sets per size; prefixes are stable across counts."""

    return {
        size: sample_destroy_quintuples(
            seed, count, portfolio_size=PORTFOLIO_SIZE, destroy_size=size
        )
        for size in DESTROY_SIZES
    }


def pilot_destroy_sets() -> DestroySets:
    """The three destroy-4 and three destroy-5 sets the pilot scores."""

    return ranked_destroy_sets(PILOT_SETS_PER_SIZE)


def parity_destroy_sets() -> DestroySets:
    """The sets that follow the pilot sample in the ranking, so no pilot set is scored early."""

    both = ranked_destroy_sets(PILOT_SETS_PER_SIZE + PARITY_SETS_PER_SIZE)
    return {size: sets[PILOT_SETS_PER_SIZE:] for size, sets in both.items()}


def sample_document(sets: Mapping[int, Sequence[Sequence[int]]]) -> dict[str, object]:
    """The exact document persisted before any scientific scoring."""

    return {
        "TASK_ID": TASK_ID,
        "PILOT_SEED": PILOT_SEED,
        "SAMPLING_METHOD": SAMPLING_METHOD,
        "POPULATION": {str(size): comb(PORTFOLIO_SIZE, size) for size in DESTROY_SIZES},
        "DESTROY4_SETS": [list(positions) for positions in sets[4]],
        "DESTROY5_SETS": [list(positions) for positions in sets[5]],
    }


def persist_destroy_samples(path: Path, sets: Mapping[int, Sequence[Sequence[int]]]) -> str:
    """Write the sample document once and return the SHA-256 of the bytes on disk."""

    payload = canonical_json(sample_document(sets)).encode("utf-8")
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError("persisted destroy samples differ from the deterministic samples")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_persisted_samples(path: Path) -> DestroySets:
    """Read the persisted sets; they must equal the deterministic pilot sets."""

    document = cast(dict[str, list[list[int]]], json.loads(path.read_text(encoding="utf-8")))
    loaded: DestroySets = {
        4: tuple(tuple(positions) for positions in document["DESTROY4_SETS"]),
        5: tuple(tuple(positions) for positions in document["DESTROY5_SETS"]),
    }
    if loaded != pilot_destroy_sets():
        raise ValueError("persisted destroy sets differ from the deterministic pilot sets")
    return loaded


# ---------------------------------------------------------------------------------------------
# one destroy set end to end
# ---------------------------------------------------------------------------------------------


def _distance_to_removed(ticket: Ticket, removed: Sequence[Ticket]) -> int:
    """Numbers that must change to turn the nearest removed ticket into ``ticket``."""

    return TICKET_SIZE - max(len(set(ticket) & set(other)) for other in removed)


@dataclass(frozen=True, slots=True)
class LocalPoolComparison:
    """The previous local candidate-generation pool against the global top (diagnostic only)."""

    local_pool_size: int
    marginals_cross_checked: int
    top_in_local: int
    top_not_in_local: tuple[RankedTicket, ...]
    top_distance_histogram: dict[int, int]
    top_beyond_two_numbers: int
    local_best_global_rank: int
    local_best_marginal: int


def compare_with_local_pool(
    universe: ColexUniverse,
    scores: GlobalScores,
    plan: GlobalPoolPlan,
    start: Portfolio,
    positions: Sequence[int],
    elites: Sequence[Portfolio],
) -> LocalPoolComparison:
    """Rebuild the five-ticket pilot's pool for the same destroy set and compare it to the top.

    Every marginal the old scan produced is also checked against the global scorer, an
    independent exact path. Nothing here changes the search; it only measures how much the local
    generator missed.
    """

    local = assemble_pool(start, positions, elites=elites)
    for member in local.members:
        expected = int(scores.marginals[universe.index_of(member.ticket)])
        if member.marginal != expected:
            raise StopConditionError(
                "PARITY_MISMATCH",
                f"local pool marginal {member.marginal} != global {expected} for {member.ticket}",
            )
    local_tickets = set(local.tickets)
    removed = plan.destroyed.removed
    outside = tuple(entry for entry in plan.top if entry.ticket not in local_tickets)
    distances = [_distance_to_removed(entry.ticket, removed) for entry in plan.top]
    histogram = {distance: distances.count(distance) for distance in sorted(set(distances))}
    local_ranked = [ranked(universe, scores, member.ticket) for member in local.members]
    return LocalPoolComparison(
        local_pool_size=len(local.members),
        marginals_cross_checked=len(local.members),
        top_in_local=len(plan.top) - len(outside),
        top_not_in_local=outside,
        top_distance_histogram=histogram,
        top_beyond_two_numbers=sum(1 for distance in distances if distance > 2),
        local_best_global_rank=min(entry.rank for entry in local_ranked),
        local_best_marginal=max(entry.marginal for entry in local_ranked),
    )


type InspectHook = Callable[[ColexUniverse, GlobalScores, GlobalPoolPlan, PoolHistogram], None]


@dataclass(frozen=True, slots=True)
class DestroySetRepair:
    """Everything recorded for one destroy set."""

    destroyed: DestroyedPortfolio
    remaining_count: int
    residual_subsets: int
    identities: dict[str, object]
    plan: GlobalPoolPlan
    local: LocalPoolComparison | None
    histogram_rows: int
    dead_subsets: int
    start_outcomes: int
    solve: PoolSolve
    optimal_portfolios: tuple[Portfolio, ...]
    optimal_counts: tuple[int, ...]
    canonical_recounts: tuple[int, ...]
    best_portfolio: Portfolio
    best_count: int
    new_tickets: Portfolio
    replaced_positions: tuple[int, ...]
    optimum_members: tuple[PoolMember, ...]
    seconds: dict[str, float]

    @property
    def best_delta(self) -> int:
        return self.best_count - self.start_outcomes


def repair_destroy_set(
    universe: ColexUniverse,
    start: Portfolio,
    positions: Sequence[int],
    *,
    elites: Sequence[Portfolio],
    recounter: CanonicalRecounter,
    expected_start_count: int = START_COUNT,
    compare_local: bool = True,
    wall_limit_seconds: float = REPAIR_SOLVE_WALL_LIMIT_SECONDS,
    inspect: InspectHook | None = None,
    geometry: Geometry = BIG_LOTTO_GEOMETRY,
) -> DestroySetRepair:
    """Freeze ``start`` minus ``positions``, score the whole universe, pool, solve and recount."""

    started = time.perf_counter()
    seconds: dict[str, float] = {}
    destroyed = destroy_positions(start, positions)
    remaining_count = recounter.count(destroyed.remaining)
    if remaining_count % geometry.subset_size:
        raise AssertionError("the canonical count of R is not a multiple of 7")
    residual = geometry.subset_count - remaining_count // geometry.subset_size

    scores = score_all_tickets(universe, destroyed.remaining)
    seconds["SCORE"] = scores.seconds
    try:
        identities = check_score_identities(scores, universe, residual)
    except AssertionError as error:
        raise StopConditionError("GLOBAL_TOP_L_COMPLETENESS_REFUTED", str(error)) from error
    phase = time.perf_counter()
    plan = assemble_global_pool(universe, scores, destroyed, elites=elites)
    seconds["TOP_AND_POOL"] = time.perf_counter() - phase
    phase = time.perf_counter()
    local = (
        compare_with_local_pool(universe, scores, plan, start, positions, elites)
        if compare_local
        else None
    )
    seconds["LOCAL_POOL_COMPARISON"] = time.perf_counter() - phase

    phase = time.perf_counter()
    pool = plan.tickets
    histogram = build_repair_histogram(destroyed.remaining, pool, geometry=geometry)
    seconds["HISTOGRAM"] = time.perf_counter() - phase
    if histogram.residual_subsets != residual:
        raise StopConditionError(
            "PARITY_MISMATCH",
            f"histogram residual {histogram.residual_subsets} != scorer residual {residual}",
        )
    for index, member in enumerate(plan.members):
        if histogram.subset_value([index]) != member.marginal:
            raise StopConditionError(
                "PARITY_MISMATCH", f"histogram marginal differs from the scorer for {member.ticket}"
            )
    if inspect is not None:
        inspect(universe, scores, plan, histogram)

    start_indices = tuple(pool.index(ticket) for ticket in destroyed.removed)
    start_outcomes = histogram.outcome_count(start_indices)
    if start_outcomes != expected_start_count:
        raise StopConditionError(
            "START_BASELINE_MISMATCH",
            f"residual kernel scored the removed tickets at {start_outcomes}",
        )

    def portfolio_of(chosen: Sequence[int]) -> Portfolio:
        return normalize_portfolio(
            (*destroyed.remaining, *(pool[i] for i in chosen)), geometry=geometry
        )

    def tie_key(chosen: tuple[int, ...]) -> str:
        return portfolio_sha256(portfolio_of(chosen))

    phase = time.perf_counter()
    solve = solve_pool_exact(
        histogram.masks,
        histogram.weights,
        len(pool),
        len(destroyed.positions),
        start_indices,
        tie_key,
        deadline=phase + wall_limit_seconds,
    )
    seconds["SOLVE"] = solve.seconds

    phase = time.perf_counter()
    portfolios = tuple(portfolio_of(chosen) for chosen in solve.optimal_sets)
    counts = tuple(histogram.outcome_count(chosen) for chosen in solve.optimal_sets)
    recounts = tuple(recounter.count(portfolio) for portfolio in portfolios)
    seconds["RECOUNT"] = time.perf_counter() - phase
    for portfolio, count, recount in zip(portfolios, counts, recounts, strict=True):
        if len(portfolio) != PORTFOLIO_SIZE or recount != count:
            raise StopConditionError(
                "REPAIR_SOLVER_CORRECTNESS_REFUTED",
                f"kernel {count} vs canonical {recount} for {portfolio_sha256(portfolio)}",
            )
    best_set = solve.best_set
    removed = set(destroyed.removed)
    chosen_tickets = tuple(pool[i] for i in best_set)
    seconds["TOTAL"] = time.perf_counter() - started
    return DestroySetRepair(
        destroyed=destroyed,
        remaining_count=remaining_count,
        residual_subsets=residual,
        identities=identities,
        plan=plan,
        local=local,
        histogram_rows=int(histogram.masks.size),
        dead_subsets=histogram.dead_subsets,
        start_outcomes=start_outcomes,
        solve=solve,
        optimal_portfolios=portfolios,
        optimal_counts=counts,
        canonical_recounts=recounts,
        best_portfolio=portfolios[0],
        best_count=counts[0],
        new_tickets=tuple(sorted(t for t in chosen_tickets if t not in removed)),
        replaced_positions=tuple(p for p in destroyed.positions if start[p] not in chosen_tickets),
        optimum_members=tuple(plan.members[i] for i in best_set),
        seconds=seconds,
    )


# ---------------------------------------------------------------------------------------------
# pre-pilot parity: toy pools
# ---------------------------------------------------------------------------------------------

TOY_POOL_SIZES: Final = (8, 9, 10, 11, 12, 13)
# frozen-set sizes of the toy cases: one ticket leaves a large residual with a spread of
# marginals; larger sets cover nearly every subset of these small pools (the all-tied regime)
TOY_FROZEN_SIZES: Final = (1, 2, 5)
TOY_TOP_COUNTS: Final = (1, 5, 10, GLOBAL_TOP_MARGINAL)
TOY_SOLVER_INSTANCES: Final = 60
TOY_END_TO_END_POOLS: Final = (16, 18)


class ParityTally:
    """Comparison and mismatch counts per named parity family."""

    def __init__(self) -> None:
        self.families: dict[str, list[int]] = {}

    def check(self, family: str, ok: bool) -> None:
        entry = self.families.setdefault(family, [0, 0])
        entry[0] += 1
        entry[1] += 0 if ok else 1

    @property
    def comparisons(self) -> int:
        return sum(entry[0] for entry in self.families.values())

    @property
    def mismatches(self) -> int:
        return sum(entry[1] for entry in self.families.values())

    def detail(self) -> dict[str, object]:
        return {
            name: {"COMPARISONS": entry[0], "MISMATCHES": entry[1]}
            for name, entry in sorted(self.families.items())
        }


def brute_force_marginals(
    pool_size: int, remaining: Sequence[Ticket]
) -> tuple[dict[Ticket, int], int]:
    """Residual marginals straight from the definition; shares no code with the fast scorer."""

    frozen = [sum(1 << (number - 1) for number in ticket) for ticket in remaining]
    subsets = [
        sum(1 << i for i in chosen) for chosen in itertools.combinations(range(pool_size), 7)
    ]
    residual = [
        subset
        for subset in subsets
        if not any((subset & mask).bit_count() >= OUTRIGHT for mask in frozen)
    ]
    marginals: dict[Ticket, int] = {}
    for ticket in itertools.combinations(range(1, pool_size + 1), TICKET_SIZE):
        mask = sum(1 << (number - 1) for number in ticket)
        marginals[ticket] = sum(1 for subset in residual if (subset & mask).bit_count() >= OUTRIGHT)
    return marginals, len(residual)


def toy_top_counts(marginals: Mapping[Ticket, int], total: int) -> list[int]:
    """Fixed counts, the whole ranking, and one cut two tickets into every marginal group.

    A cut inside a group of tied tickets that has strictly better tickets above it puts the
    selection threshold on a tie, the case the lexicographic tie-break must resolve.
    """

    counts = {min(count, total) for count in TOY_TOP_COUNTS} | {total}
    running = 0
    for value in sorted(set(marginals.values()), reverse=True):
        group = sum(1 for other in marginals.values() if other == value)
        counts.add(min(running + min(2, group), total))
        running += group
    return sorted(count for count in counts if count >= 1)


def _toy_scorer_families(rng: random.Random, tally: ParityTally) -> None:
    for pool_size in TOY_POOL_SIZES:
        universe = build_universe(pool_size)
        row_ranks = colex_rank(universe.binomial, universe.tickets)
        total = universe.tickets.shape[0]
        tally.check("ENUMERATION_COUNT_IS_C_N_6", total == comb(pool_size, TICKET_SIZE))
        tally.check(
            "ENUMERATION_COLEX_RANK_IS_ROW_INDEX",
            np.array_equal(row_ranks, np.arange(total, dtype=np.int64)),
        )
        every = list(itertools.combinations(range(1, pool_size + 1), TICKET_SIZE))
        for frozen_size in TOY_FROZEN_SIZES:
            remaining = tuple(rng.sample(every, frozen_size))
            expected, residual = brute_force_marginals(pool_size, remaining)
            scores = score_all_tickets(universe, remaining)
            ranking = sorted(expected, key=lambda ticket: (-expected[ticket], ticket))
            if frozen_size == 1 and pool_size >= 11:
                # guards against a vacuous ranking check: below 11 numbers one ticket covers
                # every subset, so the marginals only split into classes from 11 upward
                tally.check(
                    "TOY_RANKING_MIXES_DISTINCT_MARGINALS", len(set(expected.values())) >= 2
                )
            for index in range(total):
                ticket = universe.ticket_at(index)
                tally.check(
                    "SCORER_EQUALS_BRUTE_FORCE_MARGINAL",
                    int(scores.marginals[index]) == expected[ticket],
                )
            for count in toy_top_counts(expected, total):
                indices = top_ticket_indices(scores.marginals, universe.tickets, count)
                chosen = [universe.ticket_at(int(index)) for index in indices]
                tally.check("GLOBAL_TOP_L_EQUALS_BRUTE_FORCE_RANKING", chosen == ranking[:count])
            for position, ticket in enumerate(ranking, start=1):
                rank = exact_global_rank(
                    scores.marginals, universe.tickets, universe.index_of(ticket)
                )
                tally.check("EXACT_RANK_EQUALS_BRUTE_FORCE_POSITION", rank == position)
            try:
                check_score_identities(scores, universe, residual)
                identities_hold = True
            except AssertionError:
                identities_hold = False
            tally.check("GLOBAL_IDENTITIES_HOLD", identities_hold)


def _toy_solver_family(seed: int, tally: ParityTally) -> None:
    generator = np.random.default_rng(seed)

    def key(chosen: tuple[int, ...]) -> str:
        return hashlib.sha256(",".join(map(str, chosen)).encode()).hexdigest()

    for _ in range(TOY_SOLVER_INSTANCES):
        pool = int(generator.integers(5, 14))
        pick = int(generator.integers(1, min(6, pool) + 1))
        masks = np.unique(
            generator.integers(1, 1 << pool, size=int(generator.integers(4, 50)), dtype=np.uint64)
        )
        weights = generator.integers(1, 40, size=masks.size).astype(np.int64)
        values = {
            chosen: evaluate_set(masks, weights, chosen)
            for chosen in itertools.combinations(range(pool), pick)
        }
        best = max(values.values())
        optimal = sorted((chosen for chosen, v in values.items() if v == best), key=key)
        start = tuple(sorted(int(i) for i in generator.choice(pool, size=pick, replace=False)))
        for use_bound in (True, False):
            result = solve_pool_exact(masks, weights, pool, pick, start, key, use_bound=use_bound)
            tally.check(
                "SOLVER_EQUALS_BRUTE_FORCE_OPTIMAL_SETS",
                result.status == OPTIMALITY_PROVEN
                and result.best_value == best
                and list(result.optimal_sets) == optimal
                and result.unresolved_sets == 0,
            )


def _toy_end_to_end_family(rng: random.Random, tally: ParityTally) -> None:
    """Global pool, histogram and solver against the canonical evaluator on toy lotteries."""

    for pool_size in TOY_END_TO_END_POOLS:
        geometry = Geometry(pool_size, TICKET_SIZE, OUTRIGHT)
        universe = build_universe(pool_size)
        recounter = CanonicalRecounter(geometry)
        every = list(itertools.combinations(range(1, pool_size + 1), TICKET_SIZE))
        start = normalize_portfolio(rng.sample(every, 4), geometry=geometry)
        destroyed = destroy_positions(start, sorted(rng.sample(range(4), 3)))
        scores = score_all_tickets(universe, destroyed.remaining)
        plan = assemble_global_pool(
            universe, scores, destroyed, elites=[start], top_count=8, pool_max=10
        )
        pool = plan.tickets
        histogram = build_repair_histogram(destroyed.remaining, pool, geometry=geometry)

        def portfolio_of(
            chosen: Sequence[int],
            remaining: Portfolio = destroyed.remaining,
            pool: Portfolio = pool,
            geometry: Geometry = geometry,
        ) -> Portfolio:
            return normalize_portfolio((*remaining, *(pool[i] for i in chosen)), geometry=geometry)

        canonical = {
            chosen: recounter.count(portfolio_of(chosen))
            for chosen in itertools.combinations(range(len(pool)), 3)
        }
        for chosen, count in canonical.items():
            tally.check(
                "TOY_RESIDUAL_TOTAL_EQUALS_CANONICAL", histogram.outcome_count(chosen) == count
            )
        start_indices = tuple(pool.index(ticket) for ticket in destroyed.removed)
        solve = solve_pool_exact(
            histogram.masks,
            histogram.weights,
            len(pool),
            3,
            start_indices,
            lambda chosen: portfolio_sha256(portfolio_of(chosen)),
        )
        best = max(canonical.values())
        tally.check("TOY_POOL_VALUES_ARE_NOT_ALL_EQUAL", len(set(canonical.values())) > 1)
        tally.check(
            "TOY_POOL_OPTIMUM_EQUALS_CANONICAL_BRUTE_FORCE",
            solve.status == OPTIMALITY_PROVEN
            and histogram.outcome_count(solve.best_set) == best
            and set(solve.optimal_sets) == {c for c, v in canonical.items() if v == best},
        )
        tally.check(
            "TOY_POOL_CAP_KEEPS_REMOVED_THEN_TOP",
            len(pool) == min(10, plan.union_size) and set(destroyed.removed) <= set(pool),
        )


def run_toy_parity(seed: int = PILOT_SEED) -> ParityReport:
    """Toy lotteries: global scorer, top-L, exact ranks, enumeration, solver and pipeline."""

    rng = random.Random(seed)
    tally = ParityTally()
    _toy_scorer_families(rng, tally)
    _toy_solver_family(seed, tally)
    _toy_end_to_end_family(rng, tally)
    return ParityReport(
        tally.comparisons,
        tally.mismatches,
        {
            "POOL_SIZES": list(TOY_POOL_SIZES),
            "FROZEN_SIZES": list(TOY_FROZEN_SIZES),
            "TOP_COUNTS": list(TOY_TOP_COUNTS),
            "FAMILIES": tally.detail(),
        },
    )


# ---------------------------------------------------------------------------------------------
# pre-pilot parity: the real 49/20 space (destroy sets that follow the pilot sample)
# ---------------------------------------------------------------------------------------------

REAL_REPAIRED_SUBSETS_PER_SET: Final = 6
REAL_DIRECT_KERNEL_SUBSETS_PER_SET: Final = 2
REAL_RANDOM_PROBES_PER_SET: Final = 18
SMALL_POOL_SIZE: Final = 12
FIVE_TICKET_SOLVER_POOL_SIZE: Final = 48
MIN_REAL_MARGINAL_COMPARISONS: Final = 100
MIN_REAL_REPAIRED_PORTFOLIOS: Final = 20


def check_real_enumeration(universe: ColexUniverse, tally: ParityTally) -> None:
    """The real ticket table is exactly C(49,6) distinct ascending rows, row ``i`` of rank ``i``."""

    tickets = universe.tickets
    tally.check("REAL_ENUMERATION_COUNT_IS_13983816", int(tickets.shape[0]) == TOTAL_TICKETS)
    ranks = colex_rank(universe.binomial, tickets)
    tally.check(
        "REAL_ENUMERATION_COLEX_RANK_IS_ROW_INDEX",
        np.array_equal(ranks, np.arange(TOTAL_TICKETS, dtype=np.int64)),
    )
    steps = np.diff(tickets.astype(np.int16), axis=1)
    tally.check(
        "REAL_ENUMERATION_ROWS_ASCENDING_IN_POOL",
        bool(np.all(steps > 0)) and int(tickets.max()) == universe.pool_size - 1,
    )


def _hashed_choice(tag: str, size: int, count: int) -> tuple[int, ...]:
    """The ``count`` indices below ``size`` with the smallest ``sha256(seed:tag:index)``."""

    ranked_indices = sorted(
        range(size), key=lambda i: hashlib.sha256(f"{PILOT_SEED}:{tag}:{i}".encode()).hexdigest()
    )
    return tuple(sorted(ranked_indices[:count]))


def probe_tickets(universe: ColexUniverse, plan: GlobalPoolPlan, tag: str) -> tuple[Ticket, ...]:
    """Deterministic tickets to compare: removed, top ranks, frozen, extremes and hashed picks."""

    destroyed = plan.destroyed
    chosen: list[Ticket] = list(destroyed.removed)
    chosen.extend(plan.top[i].ticket for i in (0, 1, 2, len(plan.top) // 2 - 1, len(plan.top) - 1))
    chosen.extend(destroyed.remaining[:3])
    chosen.extend((universe.ticket_at(0), universe.ticket_at(TOTAL_TICKETS - 1)))
    for i in range(REAL_RANDOM_PROBES_PER_SET):
        digest = hashlib.sha256(f"{PILOT_SEED}:probe:{tag}:{i}".encode()).digest()
        chosen.append(universe.ticket_at(int.from_bytes(digest[:8], "big") % TOTAL_TICKETS))
    return tuple(dict.fromkeys(chosen))


def _check_top_independently(
    scores: GlobalScores, plan: GlobalPoolPlan, tally: ParityTally
) -> None:
    """Re-derive the top values and the boundary tie set with a sort-based path."""

    values = [entry.marginal for entry in plan.top]
    largest = [int(v) for v in np.sort(scores.marginals)[::-1][: len(values)]]
    tally.check("REAL_TOP_L_VALUES_ARE_THE_LARGEST_MARGINALS", largest == values)
    threshold = values[-1]
    stronger = int(np.count_nonzero(scores.marginals > threshold))
    tally.check(
        "REAL_TOP_L_HAS_NO_STRONGER_OUTSIDER", stronger == sum(1 for v in values if v > threshold)
    )


def _real_hook(
    recounter: CanonicalRecounter, tally: ParityTally, tag: str, sink: dict[str, object]
) -> InspectHook:
    def hook(
        universe: ColexUniverse,
        scores: GlobalScores,
        plan: GlobalPoolPlan,
        histogram: PoolHistogram,
    ) -> None:
        destroyed = plan.destroyed
        remaining, pool = destroyed.remaining, plan.tickets
        pick = len(destroyed.positions)
        base = recounter.count(remaining)
        probes = probe_tickets(universe, plan, tag)
        direct = direct_marginals(remaining, probes)
        probe_records: list[dict[str, object]] = []
        for ticket, direct_value in zip(probes, direct, strict=True):
            value = int(scores.marginals[universe.index_of(ticket)])
            canonical = recounter.count((*remaining, ticket)) - base
            match = SUBSET_SIZE * value == canonical and value == direct_value
            tally.check("REAL_GLOBAL_MARGINAL_EQUALS_CANONICAL_AND_DIRECT", match)
            probe_records.append(
                {"TICKET": list(ticket), "GLOBAL": SUBSET_SIZE * value, "CANONICAL": canonical}
            )
        _check_top_independently(scores, plan, tally)

        start_indices = tuple(pool.index(ticket) for ticket in destroyed.removed)
        subsets = [start_indices]
        for i in range(REAL_REPAIRED_SUBSETS_PER_SET - 1):
            subsets.append(_hashed_choice(f"repair:{tag}:{i}", len(pool), pick))
        repaired: list[dict[str, object]] = []
        for place, subset in enumerate(subsets):
            portfolio = normalize_portfolio((*remaining, *(pool[i] for i in subset)))
            canonical_count = recounter.count(portfolio)
            via_histogram = histogram.outcome_count(subset)
            match = via_histogram == canonical_count
            if place < REAL_DIRECT_KERNEL_SUBSETS_PER_SET:
                match = match and outcome_count(portfolio) == canonical_count
            if subset == start_indices:
                match = match and canonical_count == START_COUNT
            tally.check("REAL_REPAIRED_PORTFOLIO_RESIDUAL_TOTAL_EQUALS_CANONICAL", match)
            repaired.append({"SHA256": portfolio_sha256(portfolio), "CANONICAL": canonical_count})

        others = [i for i in range(len(pool)) if i not in start_indices]
        small_cases = {
            "START_INCLUDED": sorted((*start_indices, *others[: SMALL_POOL_SIZE - pick])),
            "ARBITRARY_INCUMBENT": list(range(SMALL_POOL_SIZE)),
        }
        for name, keep in small_cases.items():
            masks, weights = restrict_histogram(histogram, keep)
            incumbent = (
                tuple(keep.index(i) for i in start_indices)
                if name == "START_INCLUDED"
                else tuple(range(pick))
            )

            def small_key(chosen: tuple[int, ...], keep: list[int] = keep) -> str:
                return portfolio_sha256(
                    normalize_portfolio((*remaining, *(pool[keep[i]] for i in chosen)))
                )

            values = {
                chosen: evaluate_set(masks, weights, chosen)
                for chosen in itertools.combinations(range(len(keep)), pick)
            }
            best = max(values.values())
            optimal = sorted((c for c, v in values.items() if v == best), key=small_key)
            solved = solve_pool_exact(masks, weights, len(keep), pick, incumbent, small_key)
            tally.check(
                "REAL_SMALL_POOL_SOLVER_EQUALS_BRUTE_FORCE",
                solved.status == OPTIMALITY_PROVEN
                and list(solved.optimal_sets) == optimal
                and solved.unresolved_sets == 0,
            )
            chosen_pool = tuple(keep[i] for i in solved.best_set)
            best_portfolio = normalize_portfolio((*remaining, *(pool[i] for i in chosen_pool)))
            tally.check(
                "REAL_SMALL_POOL_OPTIMUM_EQUALS_CANONICAL",
                recounter.count(best_portfolio) == histogram.outcome_count(chosen_pool),
            )

        wide = sorted((*start_indices, *others[: FIVE_TICKET_SOLVER_POOL_SIZE - pick]))
        wide_masks, wide_weights = restrict_histogram(histogram, wide)
        wide_start = tuple(wide.index(i) for i in start_indices)
        reused = solve_exact_repair(wide_masks, wide_weights, len(wide), pick, wide_start)
        mine = solve_pool_exact(
            wide_masks, wide_weights, len(wide), pick, wide_start, lambda chosen: repr(chosen)
        )
        tally.check(
            "REAL_48_POOL_SOLVER_EQUALS_REUSED_FIVE_TICKET_SOLVER",
            reused.status == OPTIMALITY_PROVEN
            and mine.status == OPTIMALITY_PROVEN
            and reused.best_value == mine.best_value,
        )
        sink.update({"PROBES": probe_records, "REPAIRED_PORTFOLIOS": repaired, "BASE_COUNT": base})

    return hook


def run_real_parity(universe: ColexUniverse, recounter: CanonicalRecounter) -> ParityReport:
    """Real 49/20 parity on the destroy sets that follow the pilot sample in the ranking."""

    tally = ParityTally()
    check_real_enumeration(universe, tally)
    elites = [pin.tickets for pin in PINNED_ELITES]
    records: list[dict[str, object]] = []
    for size, sets in parity_destroy_sets().items():
        for positions in sets:
            tag = f"{size}:{','.join(map(str, positions))}"
            sink: dict[str, object] = {}
            repair = repair_destroy_set(
                universe,
                START_PORTFOLIO,
                positions,
                elites=elites,
                recounter=recounter,
                inspect=_real_hook(recounter, tally, tag, sink),
            )
            tally.check("REAL_GLOBAL_IDENTITIES_HOLD", bool(repair.identities["PASS"]))
            for _ in repair.plan.members:
                tally.check("REAL_HISTOGRAM_SINGLE_EQUALS_GLOBAL_SCORER", True)
            if repair.local is not None:
                for _ in range(repair.local.marginals_cross_checked):
                    tally.check("REAL_LOCAL_SCAN_MARGINAL_EQUALS_GLOBAL_SCORER", True)
            tally.check(
                "REAL_PARITY_SET_POOL_SOLVED_EXACTLY",
                repair.solve.status == OPTIMALITY_PROVEN and repair.solve.unresolved_sets == 0,
            )
            records.append(
                {
                    "DESTROY_SIZE": size,
                    "POSITIONS": list(positions),
                    "POOL_SIZE": len(repair.plan.members),
                    "IDENTITIES": repair.identities,
                    "OPTIMALITY_STATUS": repair.solve.status,
                    "BEST_DELTA": repair.best_delta,
                    **sink,
                }
            )
    return ParityReport(
        tally.comparisons,
        tally.mismatches,
        {"FAMILIES": tally.detail(), "SETS": records},
    )


def run_parity(universe: ColexUniverse, recounter: CanonicalRecounter) -> dict[str, object]:
    """All pre-pilot parity families; ``PARITY_MISMATCHES`` must be zero before the pilot scores."""

    toy = run_toy_parity()
    real = run_real_parity(universe, recounter)
    families = cast(dict[str, dict[str, int]], real.detail["FAMILIES"])
    marginal = families["REAL_GLOBAL_MARGINAL_EQUALS_CANONICAL_AND_DIRECT"]["COMPARISONS"]
    repaired = families["REAL_REPAIRED_PORTFOLIO_RESIDUAL_TOTAL_EQUALS_CANONICAL"]["COMPARISONS"]
    return {
        "PARITY_SAMPLE_COUNT": toy.comparisons + real.comparisons,
        "PARITY_MISMATCHES": toy.mismatches + real.mismatches,
        "REAL_MARGINAL_COMPARISONS": marginal,
        "REAL_REPAIRED_PORTFOLIOS": repaired,
        "COVERAGE_MEETS_PACKET_MINIMUMS": (
            marginal >= MIN_REAL_MARGINAL_COMPARISONS and repaired >= MIN_REAL_REPAIRED_PORTFOLIOS
        ),
        "TOY": {"COMPARISONS": toy.comparisons, "MISMATCHES": toy.mismatches, **toy.detail},
        "REAL": {"COMPARISONS": real.comparisons, "MISMATCHES": real.mismatches, **real.detail},
    }


# ---------------------------------------------------------------------------------------------
# result document
# ---------------------------------------------------------------------------------------------

MODULE_RELATIVE_PATH: Final = "src/lottolab/research/b649_k20_global_residual_pool_repair_r1.py"
RESULT_RELATIVE_PATH: Final = (
    "docs/research/matrix-native-results/b649-k20-global-residual-pool-repair-pilot-r1-result.json"
)
RESULT_IMPROVED: Final = "IMPROVED"
RESULT_NO_IMPROVEMENT: Final = "NO_IMPROVEMENT_IN_BOUNDED_GLOBAL_RESIDUAL_POOL_REPAIR_PILOT"
SCIENTIFIC_SCOPE: Final = "3_DESTROY4_PLUS_3_DESTROY5_GLOBAL_RESIDUAL_TOP48_REPAIR_PILOT"
NOT_CLAIMED: Final = (
    "complete N4 optimum",
    "complete N5 optimum",
    "optimality beyond the six sampled destroy sets and their declared global pools",
    "global K20 optimum",
    "superiority or equality relative to protected Lane 3",
)
POOL_DEFINITION: Final = {
    SOURCE_REMOVED: "the removed incumbent tickets (always retained first)",
    SOURCE_ELITE: (
        "distinct tickets of the pinned V5, V6 and 313239661 portfolios that are not frozen in R "
        "(retained second)"
    ),
    SOURCE_GLOBAL: (
        "the true top 48 of all 13,983,816 tickets by exact residual marginal, ties to the "
        "lexicographically lowest ticket (retained last, in global rank order)"
    ),
    "CAP_RULE": "A, then B, then C until 64 tickets; a frozen ticket never joins the pool",
}
LISTED_TIES_MAX: Final = 200


def _ticket_list(tickets: Sequence[Ticket]) -> list[list[int]]:
    return [list(ticket) for ticket in tickets]


def _repair_record(size: int, repair: DestroySetRepair) -> dict[str, object]:
    plan, solve, scale = repair.plan, repair.solve, SUBSET_SIZE
    local = repair.local
    outside: set[Ticket] = (
        {entry.ticket for entry in local.top_not_in_local} if local is not None else set()
    )
    pool_tickets = set(plan.tickets)
    optimum_ranks = [member.global_rank for member in repair.optimum_members]
    record: dict[str, object] = {
        "DESTROY_SIZE": size,
        "POSITIONS": list(repair.destroyed.positions),
        "REMOVED_TICKETS": _ticket_list(repair.destroyed.removed),
        "R_SIZE": len(repair.destroyed.remaining),
        "GLOBAL_ENUMERATION_COMPLETE": "YES",
        "TICKETS_SCORED": repair.identities["TICKETS_SCORED"],
        "GLOBAL_IDENTITIES": repair.identities,
        "OUTCOMES_WON_BY_FROZEN_R": repair.remaining_count,
        "RESIDUAL_SUBSETS": repair.residual_subsets,
        "GLOBAL_TOP_MARGINAL": len(plan.top),
        "GLOBAL_TOP": [
            {
                "RANK": entry.rank,
                "TICKET": list(entry.ticket),
                "RESIDUAL_MARGINAL_OUTCOMES": scale * entry.marginal,
                "DISTANCE_TO_NEAREST_REMOVED": _distance_to_removed(
                    entry.ticket, repair.destroyed.removed
                ),
                "IN_LOCAL_MUTATION_POOL": None if local is None else entry.ticket not in outside,
                "IN_REPAIR_POOL": entry.ticket in pool_tickets,
            }
            for entry in plan.top
        ],
        "POOL_SIZE": len(plan.members),
        "POOL_UNION_SIZE_BEFORE_CAP": plan.union_size,
        "POOL_DROPPED_BY_CAP": _ticket_list(plan.dropped),
        "POOL_SOURCE_COUNTS": plan.source_counts(),
        "POOL": [
            {
                "TICKET": list(member.ticket),
                "SOURCE": member.source,
                "IN_GLOBAL_TOP": member.in_global_top,
                "GLOBAL_RANK": member.global_rank,
                "RESIDUAL_MARGINAL_OUTCOMES": scale * member.marginal,
            }
            for member in plan.members
        ],
        "HISTOGRAM_ROWS": repair.histogram_rows,
        "DEAD_SUBSETS": repair.dead_subsets,
        "START_OUTCOMES_VIA_KERNEL": repair.start_outcomes,
        "POOL_OPTIMALITY_STATUS": solve.status,
        "NODES_EXPLORED": solve.nodes_explored,
        "NODES_PRUNED": solve.nodes_pruned,
        "LEAVES_SCORED": solve.leaf_sets_evaluated,
        "SETS_ELIMINATED_BY_BOUND": solve.sets_pruned,
        "TOTAL_SETS": solve.total_sets,
        "UNRESOLVED_SETS": solve.unresolved_sets,
        "BEST_COUNT": repair.best_count,
        "BEST_DELTA": repair.best_delta,
        "IMPROVED": repair.best_count > START_COUNT,
        "BEST_POOL_INDICES": list(solve.best_set),
        "BEST_NEW_TICKETS": _ticket_list(repair.new_tickets),
        "BEST_REPLACED_POSITIONS": list(repair.replaced_positions),
        "BEST_PORTFOLIO_SHA256": portfolio_sha256(repair.best_portfolio),
        "OPTIMAL_SET_COUNT": len(solve.optimal_sets),
        "OPTIMAL_SETS_CANONICALLY_RECOUNTED": len(repair.canonical_recounts),
        "OPTIMAL_SETS_CANONICAL_MATCH": all(
            recount == count
            for recount, count in zip(repair.canonical_recounts, repair.optimal_counts, strict=True)
        ),
        "OPTIMAL_SETS_LISTED": [
            {
                "POOL_INDICES": list(chosen),
                "SHA256": portfolio_sha256(portfolio),
                "CANONICAL_RECOUNT": recount,
            }
            for chosen, portfolio, recount in zip(
                solve.optimal_sets[:LISTED_TIES_MAX],
                repair.optimal_portfolios,
                repair.canonical_recounts,
                strict=False,
            )
        ],
        "OPTIMUM_TICKETS": [
            {
                "TICKET": list(member.ticket),
                "SOURCE": member.source,
                "GLOBAL_RANK": member.global_rank,
                "IN_GLOBAL_TOP48": member.in_global_top,
            }
            for member in repair.optimum_members
        ],
        "BEST_GLOBAL_TICKET_RANK_USED_BY_OPTIMUM": min(optimum_ranks),
        "WORST_GLOBAL_TICKET_RANK_USED_BY_OPTIMUM": max(optimum_ranks),
        "GLOBAL_TOP48_TICKETS_USED_BY_OPTIMUM": sum(
            1 for member in repair.optimum_members if member.in_global_top
        ),
        "SECONDS": {name: round(value, 3) for name, value in repair.seconds.items()},
    }
    if local is not None:
        record.update(
            {
                "LOCAL_MUTATION_POOL_SIZE": local.local_pool_size,
                "LOCAL_POOL_MARGINALS_CROSS_CHECKED": local.marginals_cross_checked,
                "GLOBAL_TOP48_IN_LOCAL_MUTATION_POOL": local.top_in_local,
                "GLOBAL_TOP48_NOT_IN_LOCAL_MUTATION_POOL": len(local.top_not_in_local),
                "GLOBAL_TOP48_NOT_IN_LOCAL_MUTATION_POOL_TICKETS": [
                    {
                        "RANK": entry.rank,
                        "TICKET": list(entry.ticket),
                        "RESIDUAL_MARGINAL_OUTCOMES": scale * entry.marginal,
                    }
                    for entry in local.top_not_in_local
                ],
                "GLOBAL_TOP48_DISTANCE_TO_NEAREST_REMOVED": {
                    str(distance): count
                    for distance, count in sorted(local.top_distance_histogram.items())
                },
                "GLOBAL_TOP48_BEYOND_TWO_NUMBER_MUTATION": local.top_beyond_two_numbers,
                "LOCAL_POOL_BEST_GLOBAL_RANK": local.local_best_global_rank,
                "LOCAL_POOL_MAX_RESIDUAL_MARGINAL_OUTCOMES": scale * local.local_best_marginal,
            }
        )
    return record


type PilotRepair = tuple[int, tuple[int, ...], DestroySetRepair]


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def build_result_document(
    *,
    sets: Mapping[int, Sequence[Sequence[int]]],
    sample_sha256: str,
    sample_persisted_at: str,
    sample_persisted_before_scoring: bool,
    start_record: Mapping[str, object],
    pins: Sequence[Mapping[str, object]],
    parity: Mapping[str, object],
    repairs: Sequence[PilotRepair],
    wall_seconds: float,
    peak_memory: int,
    peak_memory_after_first_set: int,
    run_identity: Mapping[str, str],
    module_sha256: str,
    phase_seconds: Mapping[str, float],
    thread_env: Mapping[str, str | None],
) -> dict[str, object]:
    """Assemble the pilot result; the global best is the highest count, then the lowest SHA-256."""

    if len(repairs) != sum(len(group) for group in sets.values()):
        raise ValueError("every pilot destroy set needs exactly one repair record")
    candidates = sorted(
        (-repair.optimal_counts[place], portfolio_sha256(portfolio), index, place)
        for index, (_, _, repair) in enumerate(repairs)
        for place, portfolio in enumerate(repair.optimal_portfolios)
    )
    best_count = -candidates[0][0]
    ties = [entry for entry in candidates if -entry[0] == best_count]
    _, best_sha, best_index, best_place = candidates[0]
    best_size, best_positions, best_repair = repairs[best_index]
    best_portfolio = best_repair.optimal_portfolios[best_place]
    best_recount = best_repair.canonical_recounts[best_place]
    ties_recounted = all(
        repairs[index][2].canonical_recounts[place] == best_count for _, _, index, place in ties
    )
    recount_pass = best_recount == best_count and ties_recounted
    improved = best_count > START_COUNT
    result = RESULT_IMPROVED if improved and recount_pass else RESULT_NO_IMPROVEMENT
    records = [_repair_record(size, repair) for size, _, repair in repairs]
    statuses = [repair.solve.status for _, _, repair in repairs]
    pool_sizes = [len(repair.plan.members) for _, _, repair in repairs]
    enumeration = [repair.seconds["SCORE"] for _, _, repair in repairs]
    solving = [repair.seconds["SOLVE"] for _, _, repair in repairs]
    leaves = sum(repair.solve.leaf_sets_evaluated for _, _, repair in repairs)
    outside = [
        (
            record["DESTROY_SIZE"],
            record["POSITIONS"],
            record["GLOBAL_TOP48_NOT_IN_LOCAL_MUTATION_POOL"],
        )
        for record in records
    ]
    optimum_ranks = [
        (
            record["DESTROY_SIZE"],
            record["POSITIONS"],
            record["BEST_GLOBAL_TICKET_RANK_USED_BY_OPTIMUM"],
        )
        for record in records
    ]
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "COMPLETE",
        "SCIENTIFIC_RESULT": result,
        "NEW_STABLE_NON_LANE3_GAIN": "YES" if result == RESULT_IMPROVED else "NO",
        "SCIENTIFIC_SCOPE": SCIENTIFIC_SCOPE,
        "COMPLETE_N4_OPTIMUM": "NOT_CLAIMED",
        "COMPLETE_N5_OPTIMUM": "NOT_CLAIMED",
        "GLOBAL_K20_OPTIMUM": "NOT_CLAIMED",
        "GAIN_VS_PROTECTED_LANE_3": "NOT_EVALUATED",
        "PROTECTED_LANE_3_TOUCHED": "NO",
        "PROJECT_MEMORY_WRITTEN": "NO",
        "PUSH": "NO",
        "PR": "NOT_CREATED",
        "PRODUCTION_CHANGE": "NONE",
        "NOT_CLAIMED": list(NOT_CLAIMED),
        "START_COUNT": START_COUNT,
        "START_SHA256": START_SHA256,
        "START_PORTFOLIO": _ticket_list(START_PORTFOLIO),
        "START_REPRODUCTION": dict(start_record),
        "PINNED_ELITES": [dict(pin) for pin in pins],
        "PILOT_SEED": PILOT_SEED,
        "SAMPLING_METHOD": SAMPLING_METHOD,
        "DESTROY4_SETS": [list(positions) for positions in sets[4]],
        "DESTROY5_SETS": [list(positions) for positions in sets[5]],
        "DESTROY4_SETS_TESTED": sum(1 for size, _, _ in repairs if size == 4),
        "DESTROY5_SETS_TESTED": sum(1 for size, _, _ in repairs if size == 5),
        "SAMPLE_FILE_SHA256": sample_sha256,
        "SAMPLE_PERSISTED_AT": sample_persisted_at,
        "SAMPLE_PERSISTED_BEFORE_SCORING": sample_persisted_before_scoring,
        "GLOBAL_TICKET_UNIVERSE_SIZE": TOTAL_TICKETS,
        "GLOBAL_ENUMERATION_COMPLETE_SETS": len(repairs),
        "GLOBAL_ENUMERATION_WALL_SECONDS_MIN": round(min(enumeration), 3),
        "GLOBAL_ENUMERATION_WALL_SECONDS_MAX": round(max(enumeration), 3),
        "GLOBAL_ENUMERATION_WALL_SECONDS_MEAN": round(_mean(enumeration), 3),
        "GLOBAL_ENUMERATION_WALL_DEFINITION": (
            "wall time of the scoring pass over all 13,983,816 tickets (pair links, triple-free "
            "extension counts, exact lifting, marginals); top-48 selection, pool assembly, the "
            "local-pool comparison, the histogram and the solve are reported separately"
        ),
        "GLOBAL_TICKETS_SCORED_TOTAL": sum(_as_int(record["TICKETS_SCORED"]) for record in records),
        "GLOBAL_TOP_MARGINAL": GLOBAL_TOP_MARGINAL,
        "REPAIR_POOL_MAX": REPAIR_POOL_MAX,
        "POOL_DEFINITION": dict(POOL_DEFINITION),
        "REPAIR_POOL_SIZE_MIN": min(pool_sizes),
        "REPAIR_POOL_SIZE_MAX": max(pool_sizes),
        "REPAIR_POOL_SIZE_MEAN": round(_mean(pool_sizes), 3),
        "REPAIR_SOLVE_WALL_SECONDS_TOTAL": round(sum(solving), 3),
        "REPAIR_SOLVE_WALL_SECONDS_MAX": round(max(solving), 3),
        "REPAIR_SOLVE_WALL_LIMIT_SECONDS": REPAIR_SOLVE_WALL_LIMIT_SECONDS,
        "PARITY_SAMPLE_COUNT": parity["PARITY_SAMPLE_COUNT"],
        "PARITY_MISMATCHES": parity["PARITY_MISMATCHES"],
        "PARITY": dict(parity),
        "PROVEN_OPTIMAL_REPAIR_SETS": statuses.count(OPTIMALITY_PROVEN),
        "FEASIBLE_ONLY_REPAIR_SETS": statuses.count(OPTIMALITY_FEASIBLE),
        "SOLVER": "EXACT_BRANCH_AND_BOUND_NUMPY_GRAM_PAIR_COMPLETION_ALL_OPTIMA",
        "SOLVER_DETAIL": (
            "DFS over pool tickets in descending single-marginal order; pruning only by the "
            "submodular remaining-slot bound (covered + sum of the r largest exact marginals) with "
            "a strict comparison so tied sets survive; the last two slots are solved exactly by a "
            "weighted Gram matrix; every optimal set is kept and ties break on the lowest "
            "normalized portfolio SHA-256; no heuristic prunes"
        ),
        "NODES_EXPLORED": sum(repair.solve.nodes_explored for _, _, repair in repairs),
        "NODES_PRUNED": sum(repair.solve.nodes_pruned for _, _, repair in repairs),
        "LEAVES_SCORED": leaves,
        "SETS_ELIMINATED_BY_BOUND": sum(repair.solve.sets_pruned for _, _, repair in repairs),
        "EXACT_REPAIR_CANDIDATES_SCORED": leaves,
        "EXACT_REPAIR_CANDIDATES_SCORED_DEFINITION": (
            "complete replacement sets scored exactly at solver leaves (each is one of the "
            "C(pool, r) candidates; the rest were eliminated by the safe bound)"
        ),
        "BEST_COUNT": best_count,
        "BEST_DELTA": best_count - START_COUNT,
        "BEST_SHA256": best_sha,
        "BEST_IS_START_PORTFOLIO": best_sha == START_SHA256,
        "BEST_DESTROY_SIZE": best_size,
        "BEST_DESTROY_INDICES": list(best_positions),
        "BEST_NEW_TICKETS": _ticket_list(sorted(set(best_portfolio) - set(START_PORTFOLIO))),
        "BEST_REPLACED_INDICES": [
            index
            for index, ticket in enumerate(START_PORTFOLIO)
            if ticket not in set(best_portfolio)
        ],
        "BEST_PORTFOLIO": _ticket_list(best_portfolio),
        "BEST_CANONICAL_RECOUNT": best_recount,
        "BEST_CANONICAL_RECOUNT_STATUS": "PASS" if recount_pass else "FAIL",
        "BEST_COUNT_TIE_COUNT": len(ties),
        "BEST_COUNT_TIES_ALL_CANONICALLY_RECOUNTED": ties_recounted,
        "BEST_COUNT_TIES_LISTED": [
            {
                "DESTROY_SIZE": repairs[index][0],
                "POSITIONS": list(repairs[index][1]),
                "SHA256": sha,
                "CANONICAL_RECOUNT": repairs[index][2].canonical_recounts[place],
            }
            for _, sha, index, place in ties[:LISTED_TIES_MAX]
        ],
        "TIE_BREAK": "max exact count, then lowest normalized portfolio sha256",
        "GLOBAL_TOP48_NOT_IN_LOCAL_MUTATION_POOL": {
            "PER_DESTROY_SET": [
                {"DESTROY_SIZE": size, "POSITIONS": positions, "COUNT": count}
                for size, positions, count in outside
            ],
            "TOTAL": sum(_as_int(count) for _, _, count in outside),
            "DEFINITION": (
                "global top-48 tickets absent from the five-ticket pilot's capped local pool "
                "(removed + pinned elites + exact-marginal one- and two-number mutations) built "
                "for the same destroy set; diagnostic only"
            ),
        },
        "BEST_GLOBAL_TICKET_RANK_USED_BY_OPTIMUM": {
            "PILOT_BEST_DESTROY_SET": min(
                member.global_rank for member in best_repair.optimum_members
            ),
            "PER_DESTROY_SET": [
                {"DESTROY_SIZE": size, "POSITIONS": positions, "BEST_RANK": rank}
                for size, positions, rank in optimum_ranks
            ],
            "DEFINITION": (
                "smallest exact global rank (1 = best of 13,983,816) among the tickets of the "
                "pool optimum (lowest-SHA optimal set); diagnostic only"
            ),
        },
        "WALL_SECONDS": round(wall_seconds, 3),
        "PHASE_SECONDS": {name: round(seconds, 3) for name, seconds in phase_seconds.items()},
        "PEAK_MEMORY_BYTES": peak_memory,
        "PEAK_MEMORY_BYTES_AFTER_FIRST_PILOT_SET": peak_memory_after_first_set,
        "PEAK_MEMORY_DEFINITION": "ru_maxrss of the single pilot process (one worker, no children)",
        "CPU_POLICY": {"PROCESSES": 1, "THREAD_ENV": dict(thread_env)},
        "PER_DESTROY_SET": records,
        "RUN_HEAD": run_identity["RUN_HEAD"],
        "RUN_TREE": run_identity["RUN_TREE"],
        "SOURCE_MODULE_PATH": MODULE_RELATIVE_PATH,
        "SOURCE_MODULE_SHA256": module_sha256,
        "RESULT_LOCATOR": RESULT_RELATIVE_PATH,
    }


# ---------------------------------------------------------------------------------------------
# pilot runner
# ---------------------------------------------------------------------------------------------

THREAD_ENV_KEYS: Final = (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
)


def _git_identity() -> dict[str, str]:
    def git(*args: str) -> str:
        completed = subprocess.run(
            ["git", *args], cwd=REPO_ROOT, check=True, capture_output=True, text=True
        )
        return completed.stdout.strip()

    return {"RUN_HEAD": git("rev-parse", "HEAD"), "RUN_TREE": git("rev-parse", "HEAD^{tree}")}


def run_pilot(workdir: Path, output: Path) -> dict[str, object]:
    """Persist the sets, reproduce the start, run parity, score the six sets, write the result."""

    wall_started = time.perf_counter()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    sample_path = workdir / "destroy-samples.json"
    sample_sha256 = persist_destroy_samples(sample_path, pilot_destroy_sets())
    persisted_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(sample_path.stat().st_mtime))
    record_progress(
        workdir, {"EVENT": "SAMPLE_PERSISTED", "SHA256": sample_sha256, "PATH": str(sample_path)}
    )
    sets = load_persisted_samples(sample_path)
    universe = build_universe()
    recounter = CanonicalRecounter()
    phase_started = time.perf_counter()
    start_record = reproduce_start(recounter)
    pins = verify_pins(recounter)
    record_progress(
        workdir, {"EVENT": "START_REPRODUCED", "CANONICAL": start_record["CANONICAL_RECOUNT"]}
    )
    parity = run_parity(universe, recounter)
    parity_done = time.perf_counter()
    record_progress(
        workdir,
        {
            "EVENT": "PARITY_DONE",
            "COMPARISONS": parity["PARITY_SAMPLE_COUNT"],
            "MISMATCHES": parity["PARITY_MISMATCHES"],
        },
    )
    if _as_int(parity["PARITY_MISMATCHES"]) != 0 or not parity["COVERAGE_MEETS_PACKET_MINIMUMS"]:
        raise StopConditionError(
            "PARITY_MISMATCH", "pre-pilot parity failed; the pilot must not score"
        )
    scoring_started_at = time.time()
    elites = [pin.tickets for pin in PINNED_ELITES]
    repairs: list[PilotRepair] = []
    peak_after_first = 0
    for size in DESTROY_SIZES:
        for positions in sets[size]:
            try:
                repair = repair_destroy_set(
                    universe, START_PORTFOLIO, positions, elites=elites, recounter=recounter
                )
            except MemoryError as error:
                raise StopConditionError("GLOBAL_ENUMERATION_NOT_FEASIBLE", str(error)) from error
            repairs.append((size, positions, repair))
            peak_after_first = peak_after_first or peak_memory_bytes()
            record_progress(
                workdir,
                {
                    "EVENT": "DESTROY_SET_DONE",
                    "DESTROY_SIZE": size,
                    "POSITIONS": list(positions),
                    "POOL_SIZE": len(repair.plan.members),
                    "STATUS": repair.solve.status,
                    "BEST_DELTA": repair.best_delta,
                    "OPTIMAL_SETS": len(repair.solve.optimal_sets),
                    "SECONDS": round(repair.seconds["TOTAL"], 1),
                },
            )
    pilot_done = time.perf_counter()
    document = build_result_document(
        sets=sets,
        sample_sha256=sample_sha256,
        sample_persisted_at=persisted_at,
        sample_persisted_before_scoring=sample_path.stat().st_mtime <= scoring_started_at,
        start_record=start_record,
        pins=pins,
        parity=parity,
        repairs=repairs,
        wall_seconds=time.perf_counter() - wall_started,
        peak_memory=peak_memory_bytes(),
        peak_memory_after_first_set=peak_after_first,
        run_identity=_git_identity(),
        module_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        phase_seconds={
            "START_AND_PARITY": parity_done - phase_started,
            "PILOT": pilot_done - parity_done,
        },
        thread_env={key: os.environ.get(key) for key in THREAD_ENV_KEYS},
    )
    write_atomically(output, canonical_json(document))
    record_progress(workdir, {"EVENT": "RESULT_WRITTEN", "PATH": str(output)})
    return document


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="b649_k20_global_residual_pool_repair_r1", description=__doc__
    )
    commands = parser.add_subparsers(dest="command", required=True)
    pilot = commands.add_parser("pilot", help="run parity, then the six sets, and write JSON")
    pilot.add_argument("--workdir", type=Path, required=True)
    pilot.add_argument("--output", type=Path, required=True)
    commands.add_parser("parity", help="run only the pre-pilot parity checks")
    args = parser.parse_args(argv)
    try:
        if args.command == "pilot":
            document = run_pilot(args.workdir, args.output)
            print(
                f"result={document['SCIENTIFIC_RESULT']} best_count={document['BEST_COUNT']} "
                f"delta={document['BEST_DELTA']} wall_seconds={document['WALL_SECONDS']}",
                flush=True,
            )
            return 0
        parity = run_parity(build_universe(), CanonicalRecounter())
        print(canonical_json(parity))
        return 0 if parity["PARITY_MISMATCHES"] == 0 else 1
    except StopConditionError as stop:
        print(f"STOP: {stop}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
