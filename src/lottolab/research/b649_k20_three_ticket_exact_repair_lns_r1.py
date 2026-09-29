"""Three-ticket exact repair inside a bounded candidate pool, with a 24-triple 49/20 pilot.

Destroy three complete tickets of a K-ticket portfolio, freeze the other K - 3 as
R and rebuild three distinct replacements from a bounded candidate pool. Inside
the pool the repair is exact and complete: every 3-subset of the pool is scored
with an exact integer count, so the best is proven (EXACT_IN_POOL). The pool is a
heuristic restriction: no gain in the pool is not no gain in complete N3.

Exactness uses the 7-set form of OFFICIAL_ANY_PRIZE. For 6-number tickets, a
special drawn outside the main draw and outright threshold 3, outcome (D, s)
wins iff some ticket t has ``|t & (D | {s})| >= 3``, and each 7-set U is
``D | {s}`` for exactly 7 outcomes. The canonical count is therefore
7 * |covered 7-sets| and, with R fixed,

    F(R + {a, b, c}) = 7 * (|C(R)| + |B(a) | B(b) | B(c)|),

where C(R) is the set of 7-sets R covers and B(t) = cover(t) - C(R) is the
residual of t. |C(R)| comes from the canonical evaluator (``evaluate_portfolio``
of R, divided by 7). The union is inclusion-exclusion over |B(a)|,
|B(a) & B(b)| and |B(a) & B(b) & B(c)|, all exact integers.

B(t) is never materialized against a global 7-set index. Every U in cover(t)
splits uniquely into A = U & t (3..6 numbers) and B = U - t (the rest, outside
t), and ``|U & x| = |A & x| + |B & x|`` for any ticket x. So cover(t) is 42
blocks, one per A, each over the C(v - 6, 7 - |A|) choices of B. R-coverage of
a block is an AND of packed per-R-ticket threshold bitsets; pool membership of
its uncovered rows is a threshold on ``|B & c|``; and all pairwise and three-way
intersections are one 0/1 Gram product per block, exact in float32 because a
block has fewer than 2**24 rows.

The residual pattern scorer of ``b649_k20_three_ticket_single_number_cycle_r1``
(branch commit 3655b0f, not on main) aggregates draws by ``D & W`` for W the
union of the three destroyed tickets. Pool candidates here are arbitrary
tickets outside W, so that aggregation does not apply; its normalization and
portfolio hash conventions are kept unchanged.
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import itertools
import json
import multiprocessing
import os
import random
import resource
import subprocess
import time
from collections.abc import Iterator, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
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
    ticket_mask,
)

type Ticket = tuple[int, ...]
type Portfolio = tuple[Ticket, ...]
type Triple = tuple[int, int, int]
type Masks = npt.NDArray[np.uint64]
type Packed = npt.NDArray[np.uint8]
type Counts = npt.NDArray[np.int64]

TICKET_SIZE = 6
OUTCOME_SET_SIZE = 7
OUTRIGHT = BIG_LOTTO_OUTRIGHT_MATCHES
DESTROY_SIZE = 3
K20 = 20
_FLOAT32_EXACT_ROWS = 1 << 24

SOURCE_REMOVED = "REMOVED_INCUMBENT"
SOURCE_ELITE = "STABLE_ELITE"
SOURCE_ONE_NUMBER = "ONE_NUMBER_REPLACEMENT"
SOURCE_GUIDED = "RESIDUAL_GUIDED_TWO_NUMBER_REPLACEMENT"
POOL_OPTIMALITY_EXACT = "EXACT_IN_POOL"
REPAIR_SOLVER = "DIRECT_ENUMERATION_EXACT_INCLUSION_EXCLUSION"


class RepairError(ValueError):
    """A portfolio, pool or repair contract was violated."""


# --- identity (same convention as the cycle module and the sealed geometry) ----------


def normalize_ticket(ticket: Sequence[int], *, pool_size: int) -> Ticket:
    if len(ticket) != TICKET_SIZE:
        raise RepairError(f"ticket must contain {TICKET_SIZE} numbers")
    if any(type(number) is not int or not 1 <= number <= pool_size for number in ticket):
        raise RepairError(f"ticket numbers must be ints in 1..{pool_size}: {tuple(ticket)}")
    if len(set(ticket)) != TICKET_SIZE:
        raise RepairError(f"ticket numbers must be distinct: {tuple(ticket)}")
    return tuple(sorted(ticket))


def normalize_portfolio(
    portfolio: Sequence[Sequence[int]], *, pool_size: int, expected_ticket_count: int | None = None
) -> Portfolio:
    if expected_ticket_count is not None and len(portfolio) != expected_ticket_count:
        raise RepairError(f"portfolio must contain exactly {expected_ticket_count} tickets")
    normalized = [normalize_ticket(ticket, pool_size=pool_size) for ticket in portfolio]
    if len(set(normalized)) != len(normalized):
        raise RepairError("portfolio tickets must be distinct")
    return tuple(sorted(normalized))


def portfolio_sha256(portfolio: Sequence[Sequence[int]], *, pool_size: int) -> str:
    """SHA-256 of the compact JSON of the normalized portfolio. Slot order is not identity."""

    normalized = normalize_portfolio(portfolio, pool_size=pool_size)
    payload = json.dumps([list(ticket) for ticket in normalized], separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonical_outcome_count(
    portfolio: Sequence[Sequence[int]], *, pool_size: int, draws: DrawMasks | None = None
) -> int:
    """Read-only call to the canonical evaluator."""

    result = evaluate_portfolio(
        portfolio,
        pool_size=pool_size,
        draw_size=TICKET_SIZE,
        outright_matches=OUTRIGHT,
        draws=draws,
    )
    return int(result.official_any_prize_outcome_count)


def covered_seven_sets(
    rest: Sequence[Sequence[int]], *, pool_size: int, draws: DrawMasks | None = None
) -> int:
    """|C(R)| = canonical count of R / 7. An empty R covers nothing."""

    if not rest:
        return 0
    count = canonical_outcome_count(rest, pool_size=pool_size, draws=draws)
    covered, remainder = divmod(count, OUTCOME_SET_SIZE)
    if remainder:
        raise RepairError("canonical count is not 7 * covered 7-sets; the identity does not hold")
    return covered


# --- exact residual coverage of one fixed R ------------------------------------------


@functools.cache
def _combination_table(n: int, m: int) -> npt.NDArray[np.intp]:
    rows = list(itertools.combinations(range(n), m))
    return np.array(rows, dtype=np.intp).reshape(len(rows), m)


@dataclass(frozen=True, slots=True)
class _Block:
    """7-sets U with U & t == A: one row per B = U - t of size 7 - |A|."""

    a_size: int
    a_mask: int
    b_masks: Masks
    uncovered: Packed


class ResidualCoverage:
    """The 7-sets not covered by a fixed R, queried per candidate ticket."""

    def __init__(self, rest: Sequence[Sequence[int]], *, pool_size: int) -> None:
        if pool_size < OUTCOME_SET_SIZE or pool_size > 64:
            raise RepairError("pool size must satisfy 7 <= v <= 64")
        self.pool_size = pool_size
        self.rest: Portfolio = normalize_portfolio(rest, pool_size=pool_size) if rest else ()
        self._rest = np.array([ticket_mask(ticket) for ticket in self.rest], dtype=np.uint64)

    def blocks(self, ticket: Sequence[int]) -> Iterator[_Block]:
        """Every block of cover(ticket) that R does not cover completely."""

        canonical = normalize_ticket(ticket, pool_size=self.pool_size)
        inside = set(canonical)
        outside = np.array(
            [1 << (n - 1) for n in range(1, self.pool_size + 1) if n not in inside],
            dtype=np.uint64,
        )
        rest = self._rest
        rest_index = np.arange(rest.size)
        for k in range(OUTRIGHT, TICKET_SIZE + 1):
            m = OUTCOME_SET_SIZE - k
            table = _combination_table(outside.size, m)
            if table.shape[0] == 0:
                continue
            b_masks = np.bitwise_or.reduce(outside[table], axis=1)
            if rest.size:
                hits = np.bitwise_count(b_masks[None, :] & rest[:, None])
                # at_most[r, s] = packed [|B & r| <= s] for s = 0..OUTRIGHT-1.
                at_most = np.stack(
                    [np.packbits(hits <= s, axis=1, bitorder="little") for s in range(OUTRIGHT)],
                    axis=1,
                )
            else:
                at_most = None
            for subset in itertools.combinations(canonical, k):
                a_mask = ticket_mask(subset)
                if at_most is None:
                    uncovered = np.packbits(
                        np.ones(b_masks.size, dtype=np.bool_), bitorder="little"
                    )
                else:
                    a_hits = np.bitwise_count(rest & np.uint64(a_mask)).astype(np.intp)
                    if int(a_hits.max()) >= OUTRIGHT:
                        continue
                    allowed = (OUTRIGHT - 1) - a_hits
                    uncovered = np.bitwise_and.reduce(at_most[rest_index, allowed], axis=0)
                yield _Block(k, a_mask, b_masks, uncovered)

    def marginal(self, ticket: Sequence[int]) -> int:
        """|B(ticket)|: 7-sets the ticket covers that R does not."""

        return sum(int(np.bitwise_count(block.uncovered).sum()) for block in self.blocks(ticket))


@dataclass(frozen=True, slots=True)
class PoolIntersections:
    """Exact residual sizes and intersections for an ordered pool.

    ``sizes[a] = |B(a)|``; ``pairs[a, b] = |B(a) & B(b)|`` (symmetric);
    ``triples[a, b, c] = |B(a) & B(b) & B(c)|`` filled for a < b < c.
    """

    sizes: Counts
    pairs: Counts
    triples: Counts


def pool_intersections(
    residual: ResidualCoverage, pool: Sequence[Sequence[int]]
) -> PoolIntersections:
    tickets = [normalize_ticket(ticket, pool_size=residual.pool_size) for ticket in pool]
    if len(set(tickets)) != len(tickets):
        raise RepairError("pool tickets must be distinct")
    n = len(tickets)
    masks = np.array([ticket_mask(ticket) for ticket in tickets], dtype=np.uint64)
    sizes = np.zeros(n, dtype=np.int64)
    pairs = np.zeros((n, n), dtype=np.int64)
    triples = np.zeros((n, n, n), dtype=np.int64)
    for a, ticket in enumerate(tickets):
        later = masks[a + 1 :]
        gram = np.zeros((later.size, later.size), dtype=np.int64)
        later_hits: dict[int, npt.NDArray[np.uint8]] = {}
        total = 0
        for block in residual.blocks(ticket):
            rows = np.flatnonzero(
                np.unpackbits(block.uncovered, count=block.b_masks.size, bitorder="little")
            )
            if rows.size == 0:
                continue
            if rows.size >= _FLOAT32_EXACT_ROWS:
                raise RepairError("block too large for an exact float32 Gram product")
            total += int(rows.size)
            if later.size == 0:
                continue
            hits = later_hits.get(block.a_size)
            if hits is None:
                hits = np.bitwise_count(block.b_masks[None, :] & later[:, None])
                later_hits[block.a_size] = hits
            need = OUTRIGHT - np.bitwise_count(later & np.uint64(block.a_mask)).astype(np.intp)
            member = (hits[:, rows] >= need[:, None]).astype(np.float32)
            product = member @ member.T
            exact = product.astype(np.int64)
            if not np.array_equal(exact, product):
                raise RepairError("Gram product lost integer exactness")
            gram += exact
        sizes[a] = total
        pairs[a, a + 1 :] = np.diagonal(gram)
        pairs[a + 1 :, a] = np.diagonal(gram)
        triples[a, a + 1 :, a + 1 :] = gram
    return PoolIntersections(sizes=sizes, pairs=pairs, triples=triples)


def union_of_three(intersections: PoolIntersections, a: int, b: int, c: int) -> int:
    if not a < b < c:
        raise RepairError("pool indices must satisfy a < b < c")
    s, p, t = intersections.sizes, intersections.pairs, intersections.triples
    return int(s[a] + s[b] + s[c] - p[a, b] - p[a, c] - p[b, c] + t[a, b, c])


# --- exact repair inside the pool ----------------------------------------------------


@dataclass(frozen=True, slots=True)
class RepairSolution:
    """The proven best 3-subset of the pool against a fixed R."""

    pool: Portfolio
    combinations: int
    exact_scored: int
    best_indices: Triple
    best_union: int
    best_portfolio: Portfolio
    best_sha256: str
    tie_count: int
    tied_sha256: tuple[str, ...]
    reference_union: int | None
    strict_improvements: int | None
    optimality_status: str


def repair_portfolio(
    rest: Portfolio, pool: Portfolio, indices: Triple, *, pool_size: int
) -> Portfolio:
    chosen = [pool[index] for index in indices]
    if len(set(chosen)) != DESTROY_SIZE:
        raise RepairError("replacement tickets must be distinct")
    if set(chosen) & set(rest):
        raise RepairError("a replacement ticket is already in the fixed rest")
    return normalize_portfolio(
        [*rest, *chosen], pool_size=pool_size, expected_ticket_count=len(rest) + DESTROY_SIZE
    )


def solve_exact_in_pool(
    intersections: PoolIntersections,
    pool: Portfolio,
    rest: Portfolio,
    *,
    pool_size: int,
    reference: Triple | None = None,
) -> RepairSolution:
    """Score every 3-subset of the pool exactly; max union, then lowest portfolio sha256."""

    n = len(pool)
    if n < DESTROY_SIZE:
        raise RepairError("the pool needs at least three tickets")
    if intersections.sizes.size != n:
        raise RepairError("intersections do not belong to this pool")
    if set(pool) & set(rest):
        raise RepairError("the pool contains a ticket of the fixed rest")
    combos = np.array(list(itertools.combinations(range(n), DESTROY_SIZE)), dtype=np.intp)
    a, b, c = combos[:, 0], combos[:, 1], combos[:, 2]
    s, p, t = intersections.sizes, intersections.pairs, intersections.triples
    unions = s[a] + s[b] + s[c] - p[a, b] - p[a, c] - p[b, c] + t[a, b, c]
    best_union = int(unions.max())
    tied = sorted(
        (
            portfolio_sha256(
                repair_portfolio(rest, pool, (int(x), int(y), int(z)), pool_size=pool_size),
                pool_size=pool_size,
            ),
            (int(x), int(y), int(z)),
        )
        for x, y, z in combos[unions == best_union]
    )
    best_sha, best_indices = tied[0]
    reference_union: int | None = None
    strict: int | None = None
    if reference is not None:
        reference_union = union_of_three(intersections, *reference)
        strict = int(np.count_nonzero(unions > reference_union))
    return RepairSolution(
        pool=pool,
        combinations=comb(n, DESTROY_SIZE),
        exact_scored=int(unions.size),
        best_indices=best_indices,
        best_union=best_union,
        best_portfolio=repair_portfolio(rest, pool, best_indices, pool_size=pool_size),
        best_sha256=best_sha,
        tie_count=len(tied),
        tied_sha256=tuple(sha for sha, _indices in tied),
        reference_union=reference_union,
        strict_improvements=strict,
        optimality_status=POOL_OPTIMALITY_EXACT,
    )


# --- bounded candidate pool ----------------------------------------------------------


def one_number_replacements(ticket: Sequence[int], *, pool_size: int) -> tuple[Ticket, ...]:
    """All 6 * (v - 6) legal tickets that differ from ``ticket`` in exactly one number."""

    canonical = normalize_ticket(ticket, pool_size=pool_size)
    inside = set(canonical)
    images: list[Ticket] = []
    for removed in canonical:
        kept = inside - {removed}
        for added in range(1, pool_size + 1):
            if added not in inside:
                images.append(tuple(sorted(kept | {added})))
    return tuple(images)


@dataclass(frozen=True, slots=True)
class CandidatePool:
    tickets: Portfolio
    sources: tuple[str, ...]
    marginals: tuple[int, ...]
    removed: Portfolio
    rest: Portfolio
    mandatory_count: int
    accounting: dict[str, int]

    @property
    def removed_indices(self) -> Triple:
        positions = sorted(self.tickets.index(ticket) for ticket in self.removed)
        return positions[0], positions[1], positions[2]

    @property
    def sha256(self) -> str:
        payload = json.dumps([list(ticket) for ticket in self.tickets], separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def split_start(portfolio: Portfolio, indices: Triple) -> tuple[Portfolio, Portfolio]:
    """(removed tickets, fixed rest R) for three distinct canonical positions."""

    if len(set(indices)) != DESTROY_SIZE or any(not 0 <= i < len(portfolio) for i in indices):
        raise RepairError("destroy indices must be three distinct positions")
    removed = tuple(sorted(portfolio[i] for i in indices))
    rest = tuple(ticket for i, ticket in enumerate(portfolio) if i not in indices)
    return removed, rest


def build_candidate_pool(
    start: Portfolio,
    indices: Triple,
    *,
    pool_size: int,
    residual: ResidualCoverage,
    elite: Sequence[Sequence[int]],
    pool_max: int,
    guided_top_l: int,
) -> CandidatePool:
    """Removed + elite are mandatory; the rest of the pool is the top exact residual marginals.

    Generated optional candidates: every one-number replacement of each removed
    ticket, then every one-number replacement of each removed ticket's
    ``guided_top_l`` best one-number replacements (a bounded subset of its
    two-number replacements). Tickets of R are never candidates. Optional
    candidates are ranked by exact marginal |B(t)| against R, descending, then
    by lowest ticket, and cut at ``pool_max`` minus the mandatory count.
    """

    canonical = normalize_portfolio(start, pool_size=pool_size)
    removed, rest = split_start(canonical, indices)
    if residual.rest != rest:
        raise RepairError("the residual scorer is bound to a different fixed rest")
    rest_set = set(rest)
    source: dict[Ticket, str] = {}
    counts = {
        "ELITE_DISTINCT": 0,
        "ELITE_IN_REST_EXCLUDED": 0,
        "ONE_NUMBER_GENERATED": 0,
        "GUIDED_GENERATED": 0,
        "IN_REST_EXCLUDED": 0,
        "DUPLICATES_MERGED": 0,
    }

    def offer(ticket: Ticket, tag: str) -> bool:
        if ticket in rest_set:
            counts["IN_REST_EXCLUDED"] += 1
            return False
        if ticket in source:
            counts["DUPLICATES_MERGED"] += 1
            return False
        source[ticket] = tag
        return True

    for ticket in removed:
        offer(ticket, SOURCE_REMOVED)
    elite_distinct = sorted({normalize_ticket(ticket, pool_size=pool_size) for ticket in elite})
    counts["ELITE_DISTINCT"] = len(elite_distinct)
    for ticket in elite_distinct:
        if ticket in rest_set:
            counts["ELITE_IN_REST_EXCLUDED"] += 1
        elif ticket not in source:
            source[ticket] = SOURCE_ELITE
    mandatory = set(source)
    if len(mandatory) > pool_max:
        raise RepairError(f"{len(mandatory)} mandatory tickets exceed the pool bound {pool_max}")

    marginal: dict[Ticket, int] = {}

    def score(ticket: Ticket) -> int:
        value = marginal.get(ticket)
        if value is None:
            value = residual.marginal(ticket)
            marginal[ticket] = value
        return value

    first_step: dict[Ticket, list[Ticket]] = {}
    for ticket in removed:
        images = one_number_replacements(ticket, pool_size=pool_size)
        counts["ONE_NUMBER_GENERATED"] += len(images)
        first_step[ticket] = [image for image in images if image not in rest_set]
        for image in images:
            offer(image, SOURCE_ONE_NUMBER)
    for ticket in removed:
        ranked = sorted(first_step[ticket], key=lambda image: (-score(image), image))
        for seed in ranked[:guided_top_l]:
            images = one_number_replacements(seed, pool_size=pool_size)
            counts["GUIDED_GENERATED"] += len(images)
            for image in images:
                offer(image, SOURCE_GUIDED)

    for ticket in source:
        score(ticket)
    optional = sorted(
        (ticket for ticket in source if ticket not in mandatory),
        key=lambda ticket: (-marginal[ticket], ticket),
    )
    retained = optional[: pool_max - len(mandatory)]
    tickets = tuple(sorted(mandatory | set(retained)))
    counts.update(
        CANDIDATES_DISTINCT=len(source),
        EXACT_MARGINALS_SCORED=len(marginal),
        MANDATORY=len(mandatory),
        OPTIONAL_DISTINCT=len(optional),
        OPTIONAL_RETAINED=len(retained),
        POOL_SIZE=len(tickets),
    )
    return CandidatePool(
        tickets=tickets,
        sources=tuple(source[ticket] for ticket in tickets),
        marginals=tuple(marginal[ticket] for ticket in tickets),
        removed=removed,
        rest=rest,
        mandatory_count=len(mandatory),
        accounting=counts,
    )


# --- pinned 49/20 authorities --------------------------------------------------------

TASK_ID = "B649_K20_THREE_TICKET_EXACT_REPAIR_LNS_PILOT_R1"
SCIENTIFIC_SCOPE = "BOUNDED_24_TRIPLE_THREE_TICKET_EXACT_REPAIR_WITHIN_CANDIDATE_POOL"
REFERENCE_MAIN_HEAD = "76085ccc8f226c8752cc7df28390e27009d21746"
REFERENCE_MAIN_TREE = "a2bd43ed9019e4cf2f330eb7d0dfa498d7904b43"
TOTAL_OUTCOMES = comb(BIG_LOTTO_POOL_SIZE, TICKET_SIZE) * (BIG_LOTTO_POOL_SIZE - TICKET_SIZE)
DESTROY_TRIPLE_SEED = 20260930
DESTROY_TRIPLE_SAMPLE_COUNT = 24
CANDIDATE_POOL_MAX = 96
GUIDED_TOP_L = 4
PARITY_PER_REPAIR = 1
PARITY_MIN_SAMPLE = 30
RESULT_PATH = (
    "docs/research/matrix-native-results/"
    "b649-k20-three-ticket-exact-repair-lns-pilot-r1-result.json"
)

V6_LOCATOR = (
    "docs/research/matrix-native-results/b649-k20-two-ticket-joint-replacement-incumbent-r1.json"
)
V6_FILE_SHA256 = "14f070a764a48a09007e18db212d491867a7c8dc59e775115391a02c8840f632"
V6_COUNT = 313_239_647
V6_EXACT_PROBABILITY = "44748521/85900584"
V6_PORTFOLIO_SHA256 = "0c52a1f0bed90cd47d08bb031b13c9bf693317493f88e45da8e087bd4a0ab65b"

V5_LOCATOR = "docs/research/matrix-native-results/b649-k20-cross-swap-champion-r1.json"
V5_FILE_SHA256 = "2deb616dc0c69dc0d6d41bc3d815f834f065c056b668a2e8db07b3a5064c05ea"
V5_COUNT = 312_986_016
V5_PORTFOLIO_SHA256 = "bc755e9b674e2ff37dac0fc8b52bb9f01bfd5a2bf90fc5f9f245dbb049c0ae86"

CYCLE_RESULT_COMMIT = "3655b0f4bc43450748b4fc87c641d0acd11a8509"
CYCLE_RESULT_TREE = "faa67081c8dd77563d1d8f1aba95a30b19d2f543"
CYCLE_RESULT_LOCATOR = (
    "docs/research/matrix-native-results/b649-k20-three-ticket-cycle-full-family-r1-result.json"
)
CYCLE_RESULT_BLOB = "69155cc61d67f5890573b4113773dbd3c8ee83a4"
CYCLE_RESULT_FILE_SHA256 = "2ba9308faa96518b8a75bb1ee8b1ddcf62e7cd66258c8f36999e48f68c676266"
CYCLE_COUNT = 313_239_661
CYCLE_PORTFOLIO_SHA256 = "7ce41ff21d5c0821f1d5dda683e23114086f5024fc6d98d4e574df5306659b1e"
# BEST_PORTFOLIO of the cycle result above; bound at run time to that blob and to a recount.
CYCLE_PORTFOLIO: Portfolio = (
    (1, 2, 34, 41, 42, 45),
    (1, 17, 22, 30, 33, 43),
    (2, 5, 33, 35, 40, 48),
    (3, 4, 10, 15, 26, 27),
    (3, 8, 13, 28, 31, 36),
    (3, 9, 16, 23, 29, 39),
    (4, 7, 12, 36, 39, 46),
    (4, 18, 20, 24, 28, 29),
    (5, 17, 25, 32, 41, 47),
    (6, 7, 9, 13, 18, 26),
    (6, 10, 11, 16, 24, 36),
    (6, 14, 20, 31, 37, 39),
    (7, 8, 10, 14, 19, 29),
    (8, 9, 11, 15, 20, 46),
    (11, 12, 18, 23, 27, 49),
    (12, 13, 15, 19, 24, 37),
    (16, 19, 26, 28, 46, 49),
    (21, 25, 30, 38, 45, 48),
    (21, 32, 40, 42, 43, 44),
    (22, 34, 35, 38, 44, 47),
)

if TOTAL_OUTCOMES != 601_304_088 or comb(K20, DESTROY_SIZE) != 1140:
    raise RuntimeError("outcome total or triple population drifted")


@dataclass(frozen=True, slots=True)
class BoundPortfolio:
    """A portfolio whose identity and canonical count were both reproduced."""

    name: str
    portfolio: Portfolio
    sha256: str
    outcome_count: int
    provenance: dict[str, object]


def _json_object(raw: bytes) -> dict[str, object]:
    payload: object = json.loads(raw)
    if not isinstance(payload, dict):
        raise RepairError("authority artifact must be a JSON object")
    return cast(dict[str, object], payload)


def _ticket_rows(value: object) -> list[list[int]]:
    if not isinstance(value, list):
        raise RepairError("ticket list must be a JSON list")
    rows: list[list[int]] = []
    for row in cast(list[object], value):
        if not isinstance(row, list):
            raise RepairError("ticket rows must be lists")
        numbers = [number for number in cast(list[object], row) if type(number) is int]
        if len(numbers) != len(cast(list[object], row)):
            raise RepairError("ticket rows must be integer lists")
        rows.append(numbers)
    return rows


def _bind(
    name: str,
    tickets: Sequence[Sequence[int]],
    *,
    expected_sha256: str,
    expected_count: int,
    draws: DrawMasks,
    provenance: dict[str, object],
) -> BoundPortfolio:
    portfolio = normalize_portfolio(
        tickets, pool_size=BIG_LOTTO_POOL_SIZE, expected_ticket_count=K20
    )
    digest = portfolio_sha256(portfolio, pool_size=BIG_LOTTO_POOL_SIZE)
    if digest != expected_sha256:
        raise RepairError(f"{name} hash {digest} != expected {expected_sha256}")
    count = canonical_outcome_count(portfolio, pool_size=BIG_LOTTO_POOL_SIZE, draws=draws)
    if count != expected_count:
        raise RepairError(f"{name} canonical count {count} != expected {expected_count}")
    return BoundPortfolio(name, portfolio, digest, count, provenance)


def _committed_artifact(repo_root: Path, locator: str, expected_sha256: str) -> dict[str, object]:
    raw = (repo_root / locator).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise RepairError(f"{locator} bytes do not match the pinned sha256")
    return _json_object(raw)


def bind_v6(repo_root: Path, *, draws: DrawMasks) -> BoundPortfolio:
    fields = _committed_artifact(repo_root, V6_LOCATOR, V6_FILE_SHA256)
    if fields.get("PORTFOLIO_SHA256") != V6_PORTFOLIO_SHA256:
        raise RepairError("v6 artifact names a different portfolio")
    if fields.get("WINNING_OUTCOMES") != V6_COUNT:
        raise RepairError("v6 artifact names a different count")
    bound = _bind(
        "v6",
        _ticket_rows(fields.get("TICKETS")),
        expected_sha256=V6_PORTFOLIO_SHA256,
        expected_count=V6_COUNT,
        draws=draws,
        provenance={"LOCATOR": V6_LOCATOR, "FILE_SHA256": V6_FILE_SHA256},
    )
    if str(Fraction(bound.outcome_count, TOTAL_OUTCOMES)) != V6_EXACT_PROBABILITY:
        raise RepairError("v6 exact probability does not reproduce")
    return bound


def bind_v5(repo_root: Path, *, draws: DrawMasks) -> BoundPortfolio:
    fields = _committed_artifact(repo_root, V5_LOCATOR, V5_FILE_SHA256)
    if fields.get("TERMINAL_K20_PORTFOLIO_SHA256") != V5_PORTFOLIO_SHA256:
        raise RepairError("v5 artifact names a different portfolio")
    if fields.get("TERMINAL_K20_OUTCOME_COUNT") != V5_COUNT:
        raise RepairError("v5 artifact names a different count")
    return _bind(
        "v5",
        _ticket_rows(fields.get("TERMINAL_TICKETS")),
        expected_sha256=V5_PORTFOLIO_SHA256,
        expected_count=V5_COUNT,
        draws=draws,
        provenance={"LOCATOR": V5_LOCATOR, "FILE_SHA256": V5_FILE_SHA256},
    )


def _git(repo_root: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args], check=True, capture_output=True
    ).stdout


def verify_cycle_blob(repo_root: Path) -> dict[str, object]:
    """Bind the embedded cycle portfolio to the committed 3655b0f result blob."""

    tree = _git(repo_root, "rev-parse", f"{CYCLE_RESULT_COMMIT}^{{tree}}").decode().strip()
    if tree != CYCLE_RESULT_TREE:
        raise RepairError("cycle result commit resolves to a different tree")
    blob = _git(repo_root, "rev-parse", f"{CYCLE_RESULT_COMMIT}:{CYCLE_RESULT_LOCATOR}")
    if blob.decode().strip() != CYCLE_RESULT_BLOB:
        raise RepairError("cycle result locator resolves to a different blob")
    raw = _git(repo_root, "cat-file", "blob", CYCLE_RESULT_BLOB)
    if hashlib.sha256(raw).hexdigest() != CYCLE_RESULT_FILE_SHA256:
        raise RepairError("cycle result blob bytes do not match the pinned sha256")
    fields = _json_object(raw)
    recorded = normalize_portfolio(
        _ticket_rows(fields.get("BEST_PORTFOLIO")), pool_size=BIG_LOTTO_POOL_SIZE
    )
    if recorded != CYCLE_PORTFOLIO:
        raise RepairError("embedded cycle portfolio differs from the committed result")
    if (
        fields.get("BEST_PORTFOLIO_SHA256") != CYCLE_PORTFOLIO_SHA256
        or fields.get("BEST_COUNT") != CYCLE_COUNT
        or fields.get("BEST_CANONICAL_RECOUNT_STATUS") != "PASS"
    ):
        raise RepairError("committed cycle result names a different best")
    return {
        "RESULT_COMMIT": CYCLE_RESULT_COMMIT,
        "RESULT_TREE": CYCLE_RESULT_TREE,
        "RESULT_LOCATOR": CYCLE_RESULT_LOCATOR,
        "RESULT_BLOB": CYCLE_RESULT_BLOB,
        "RESULT_FILE_SHA256": CYCLE_RESULT_FILE_SHA256,
        "BLOB_BINDING": "PASS",
    }


def bind_cycle(repo_root: Path, *, draws: DrawMasks) -> BoundPortfolio:
    return _bind(
        "three_ticket_cycle",
        CYCLE_PORTFOLIO,
        expected_sha256=CYCLE_PORTFOLIO_SHA256,
        expected_count=CYCLE_COUNT,
        draws=draws,
        provenance=verify_cycle_blob(repo_root),
    )


def select_destroy_triples(
    ticket_count: int = K20,
    *,
    seed: int = DESTROY_TRIPLE_SEED,
    count: int = DESTROY_TRIPLE_SAMPLE_COUNT,
) -> tuple[Triple, ...]:
    """``count`` distinct index triples sampled once from all C(K, 3), in sampled order."""

    population = list(itertools.combinations(range(ticket_count), DESTROY_SIZE))
    return tuple(random.Random(seed).sample(population, count))


# --- pilot orchestration -------------------------------------------------------------


def _peak_rss_bytes() -> int:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak) if os.uname().sysname == "Darwin" else int(peak) * 1024


def _tickets_json(tickets: Sequence[Ticket]) -> list[list[int]]:
    return [list(ticket) for ticket in tickets]


def _write_json_atomically(path: Path, payload: dict[str, object]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    staging = path.with_name(path.name + ".tmp")
    staging.write_bytes(encoded)
    os.replace(staging, path)
    return hashlib.sha256(encoded).hexdigest()


def parity_indices(pool_len: int, removed: Triple, *, stream: str) -> tuple[Triple, ...]:
    """Deterministic in-pool triples other than the removed triple, for canonical parity."""

    population = [
        triple
        for triple in itertools.combinations(range(pool_len), DESTROY_SIZE)
        if triple != removed
    ]
    rng = random.Random(stream)
    return tuple(rng.sample(population, min(PARITY_PER_REPAIR, len(population))))


def repair_one(
    start: BoundPortfolio,
    indices: Triple,
    *,
    elite: Sequence[Ticket],
    draws: DrawMasks,
    pool_max: int = CANDIDATE_POOL_MAX,
    guided_top_l: int = GUIDED_TOP_L,
) -> dict[str, object]:
    """One destroyed triple: pool, exact in-pool repair, reproduction, recount and parity."""

    pool_size = BIG_LOTTO_POOL_SIZE
    began = time.perf_counter()
    removed, rest = split_start(start.portfolio, indices)
    covered = covered_seven_sets(rest, pool_size=pool_size, draws=draws)
    residual = ResidualCoverage(rest, pool_size=pool_size)
    pool = build_candidate_pool(
        start.portfolio,
        indices,
        pool_size=pool_size,
        residual=residual,
        elite=elite,
        pool_max=pool_max,
        guided_top_l=guided_top_l,
    )
    pool_seconds = time.perf_counter() - began
    mark = time.perf_counter()
    intersections = pool_intersections(residual, pool.tickets)
    if tuple(int(size) for size in intersections.sizes) != pool.marginals:
        raise RepairError("pool marginals disagree with the intersection pass")
    solution = solve_exact_in_pool(
        intersections, pool.tickets, rest, pool_size=pool_size, reference=pool.removed_indices
    )
    solve_seconds = time.perf_counter() - mark

    def predicted(union: int) -> int:
        return OUTCOME_SET_SIZE * (covered + union)

    if solution.reference_union is None:
        raise RepairError("the removed triple was not scored")
    start_reproduced = predicted(solution.reference_union)
    if start_reproduced != start.outcome_count:
        raise RepairError(
            f"residual start reproduction {start_reproduced} != canonical {start.outcome_count}"
        )
    best_count = predicted(solution.best_union)
    mark = time.perf_counter()
    best_canonical = canonical_outcome_count(
        solution.best_portfolio, pool_size=pool_size, draws=draws
    )
    parity: list[dict[str, object]] = []
    stream = f"parity:{DESTROY_TRIPLE_SEED}:{start.name}:{indices[0]}:{indices[1]}:{indices[2]}"
    for triple in parity_indices(len(pool.tickets), pool.removed_indices, stream=stream):
        candidate = repair_portfolio(rest, pool.tickets, triple, pool_size=pool_size)
        residual_count = predicted(union_of_three(intersections, *triple))
        canonical_count = canonical_outcome_count(candidate, pool_size=pool_size, draws=draws)
        parity.append(
            {
                "POOL_INDICES": list(triple),
                "SHA256": portfolio_sha256(candidate, pool_size=pool_size),
                "RESIDUAL_COUNT": residual_count,
                "CANONICAL_COUNT": canonical_count,
                "MATCH": residual_count == canonical_count,
            }
        )
    recount_seconds = time.perf_counter() - mark
    added = sorted(set(solution.best_portfolio) - set(start.portfolio))
    dropped = sorted(set(start.portfolio) - set(solution.best_portfolio))
    sources = sorted(pool.sources[i] for i in solution.best_indices)
    return {
        "START": start.name,
        "DESTROY_INDICES": list(indices),
        "REMOVED_TICKETS": _tickets_json(removed),
        "REST_COVERED_SEVEN_SETS": covered,
        "POOL_SIZE": len(pool.tickets),
        "POOL_SHA256": pool.sha256,
        "POOL_SOURCES": {
            tag: pool.sources.count(tag)
            for tag in (SOURCE_REMOVED, SOURCE_ELITE, SOURCE_ONE_NUMBER, SOURCE_GUIDED)
        },
        "POOL_MARGINAL_MIN": min(pool.marginals),
        "POOL_MARGINAL_MAX": max(pool.marginals),
        "POOL_ACCOUNTING": pool.accounting,
        "COMBINATIONS_CONSIDERED": solution.combinations,
        "EXACT_TRIPLES_SCORED": solution.exact_scored,
        "POOL_OPTIMALITY_STATUS": solution.optimality_status,
        "START_UNION": solution.reference_union,
        "START_REPRODUCTION": "PASS",
        "STRICT_IMPROVEMENTS_IN_POOL": solution.strict_improvements,
        "BEST_UNION": solution.best_union,
        "BEST_COUNT": best_count,
        "BEST_DELTA": best_count - start.outcome_count,
        "BEST_SHA256": solution.best_sha256,
        "BEST_TIE_COUNT": solution.tie_count,
        "BEST_REPLACEMENT_SOURCES": sources,
        "BEST_TICKETS_ADDED": _tickets_json(added),
        "BEST_TICKETS_DROPPED": _tickets_json(dropped),
        "BEST_CANONICAL_COUNT": best_canonical,
        "BEST_CANONICAL_RECOUNT": "PASS" if best_canonical == best_count else "FAIL",
        "PARITY": parity,
        "SECONDS": {
            "POOL": round(pool_seconds, 3),
            "EXACT_REPAIR": round(solve_seconds, 3),
            "CANONICAL_CHECKS": round(recount_seconds, 3),
            "TOTAL": round(time.perf_counter() - began, 3),
        },
        "_BEST_PORTFOLIO": _tickets_json(solution.best_portfolio),
    }


def _git_identity(repo_root: Path) -> dict[str, str]:
    def rev(expression: str) -> str:
        return _git(repo_root, "rev-parse", expression).decode().strip()

    return {"RUN_HEAD": rev("HEAD"), "RUN_TREE": rev("HEAD^{tree}")}


def _pick_best(records: Sequence[dict[str, object]]) -> dict[str, object]:
    return min(records, key=lambda r: (-cast(int, r["BEST_COUNT"]), cast(str, r["BEST_SHA256"])))


@dataclass(frozen=True, slots=True)
class _StartRun:
    records: list[dict[str, object]]
    wall_seconds: float
    peak_rss_bytes: int


def _run_start(
    start: BoundPortfolio, triples: Sequence[Triple], elite: Sequence[Ticket]
) -> _StartRun:
    """Worker body: every destroyed triple of one start, in sampled order."""

    began = time.perf_counter()
    draws = all_main_draw_masks(BIG_LOTTO_POOL_SIZE, TICKET_SIZE)
    records = [repair_one(start, triple, elite=elite, draws=draws) for triple in triples]
    return _StartRun(records, time.perf_counter() - began, _peak_rss_bytes())


def run_pilot(repo_root: Path, *, result_path: Path, workers: int = 2) -> dict[str, object]:
    if workers not in (1, 2):
        raise RepairError("the shared-workstation budget allows one or two workers")
    started = time.perf_counter()
    source = Path(__file__).resolve()
    draws = all_main_draw_masks(BIG_LOTTO_POOL_SIZE, TICKET_SIZE)
    v6 = bind_v6(repo_root, draws=draws)
    v5 = bind_v5(repo_root, draws=draws)
    cycle = bind_cycle(repo_root, draws=draws)
    del draws
    elite = tuple(sorted({*v5.portfolio, *v6.portfolio, *cycle.portfolio}))
    triples = select_destroy_triples()
    if len(set(triples)) != DESTROY_TRIPLE_SAMPLE_COUNT:
        raise RepairError("destroy triples are not distinct")
    binding_seconds = time.perf_counter() - started

    starts = (v6, cycle)
    mark = time.perf_counter()
    if workers == 1:
        runs = [_run_start(start, triples, elite) for start in starts]
    else:
        context = multiprocessing.get_context("spawn")
        with ProcessPoolExecutor(max_workers=workers, mp_context=context) as executor:
            futures = [executor.submit(_run_start, start, triples, elite) for start in starts]
            runs = [future.result() for future in futures]
    repair_wall_seconds = time.perf_counter() - mark

    per_start: dict[str, dict[str, object]] = {}
    records: list[dict[str, object]] = []
    for start, run in zip(starts, runs, strict=True):
        start_records = run.records
        records.extend(start_records)
        best = _pick_best(start_records)
        best_count = cast(int, best["BEST_COUNT"])
        recounted = best["BEST_CANONICAL_RECOUNT"] == "PASS"
        per_start[start.name] = {
            "START_COUNT": start.outcome_count,
            "START_SHA256": start.sha256,
            "TRIPLES_TESTED": len(start_records),
            "BEST_FINAL_COUNT": best_count,
            "BEST_DELTA": best_count - start.outcome_count,
            "BEST_EXACT_PROBABILITY": str(Fraction(best_count, TOTAL_OUTCOMES)),
            "BEST_PORTFOLIO_SHA256": best["BEST_SHA256"],
            "BEST_PORTFOLIO": best["_BEST_PORTFOLIO"],
            "BEST_DESTROY_INDICES": best["DESTROY_INDICES"],
            "BEST_CANONICAL_RECOUNT_STATUS": "PASS" if recounted else "FAIL",
            "TRIPLES_WITH_STRICT_GAIN": sum(
                1 for r in start_records if cast(int, r["BEST_DELTA"]) > 0
            ),
            "GAIN_ESTABLISHED_VS_START": (
                "YES" if best_count > start.outcome_count and recounted else "NO"
            ),
            "WALL_SECONDS": round(run.wall_seconds, 3),
            "PEAK_RSS_BYTES": run.peak_rss_bytes,
        }
    for record in records:
        record.pop("_BEST_PORTFOLIO")

    parity = [
        entry for record in records for entry in cast(list[dict[str, object]], record["PARITY"])
    ]
    parity_mismatches = sum(1 for entry in parity if not entry["MATCH"])
    recount_failures = sum(1 for r in records if r["BEST_CANONICAL_RECOUNT"] != "PASS")
    overall_name = min(
        per_start,
        key=lambda name: (
            -cast(int, per_start[name]["BEST_FINAL_COUNT"]),
            cast(str, per_start[name]["BEST_PORTFOLIO_SHA256"]),
        ),
    )
    overall = per_start[overall_name]
    overall_count = cast(int, overall["BEST_FINAL_COUNT"])
    clean = parity_mismatches == 0 and recount_failures == 0 and len(parity) >= PARITY_MIN_SAMPLE
    pool_sizes = [cast(int, r["POOL_SIZE"]) for r in records]
    record_out: dict[str, object] = {
        "TASK_ID": TASK_ID,
        "SCIENTIFIC_SCOPE": SCIENTIFIC_SCOPE,
        "SOURCE_MODULE_PATH": str(source.relative_to(repo_root.resolve())),
        "SOURCE_MODULE_SHA256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "REFERENCE_MAIN_HEAD": REFERENCE_MAIN_HEAD,
        "REFERENCE_MAIN_TREE": REFERENCE_MAIN_TREE,
        **_git_identity(repo_root),
        "STARTS": {
            bound.name: {
                "PORTFOLIO_SHA256": bound.sha256,
                "CANONICAL_COUNT": bound.outcome_count,
                "EXACT_PROBABILITY": str(Fraction(bound.outcome_count, TOTAL_OUTCOMES)),
                "CANONICAL_REPRODUCTION": "PASS",
                "PROVENANCE": bound.provenance,
            }
            for bound in (v6, cycle)
        },
        "ELITE_SOURCES": {
            "v5": {
                "PORTFOLIO_SHA256": v5.sha256,
                "CANONICAL_COUNT": v5.outcome_count,
                **v5.provenance,
            },
            "v6": {"PORTFOLIO_SHA256": v6.sha256},
            "three_ticket_cycle": {"PORTFOLIO_SHA256": cycle.sha256},
            "DISTINCT_ELITE_TICKETS": len(elite),
        },
        "DESTROY": {
            "DESTROY_SIZE": DESTROY_SIZE,
            "SEED": DESTROY_TRIPLE_SEED,
            "SAMPLE_COUNT": len(triples),
            "SELECTION": "random.Random(seed).sample(all C(20,3) index triples, 24), sampled order",
            "INDEX_BASIS": "positions in each start's normalized (sorted) portfolio",
            "TRIPLES": [list(t) for t in triples],
        },
        "POOL_POLICY": {
            "CANDIDATE_POOL_MAX": CANDIDATE_POOL_MAX,
            "MANDATORY": "removed incumbent tickets + distinct elite tickets not in R",
            "ONE_NUMBER_REPLACEMENTS": "all 6*43 per removed ticket",
            "TWO_NUMBER_REPLACEMENTS": (
                f"BOUNDED_GUIDED_SUBSET: one-number replacements of each removed ticket's top "
                f"{GUIDED_TOP_L} one-number replacements by exact residual marginal; the full "
                "15*903 two-number family per ticket is not generated"
            ),
            "RANKING": "exact residual marginal |B(t)| vs R descending, then lowest ticket",
            "EXCLUDED": "tickets of R",
            "RESTRICTION": "HEURISTIC_SEARCH_RESTRICTION",
        },
        "REPAIR_SOLVER": REPAIR_SOLVER,
        "POOL_OPTIMALITY_STATUS": POOL_OPTIMALITY_EXACT,
        "POOL_SIZE_MIN": min(pool_sizes),
        "POOL_SIZE_MAX": max(pool_sizes),
        "POOL_SIZE_MEAN": round(sum(pool_sizes) / len(pool_sizes), 3),
        "EXACT_CANDIDATES_SCORED": sum(cast(int, r["EXACT_TRIPLES_SCORED"]) for r in records),
        "EXACT_CANDIDATES_SCORED_DEFINITION": (
            "repaired K20 portfolios (in-pool 3-subsets) scored with an exact integer count"
        ),
        "EXACT_MARGINALS_SCORED": sum(
            cast(dict[str, int], r["POOL_ACCOUNTING"])["EXACT_MARGINALS_SCORED"] for r in records
        ),
        "PARITY_49_20": {
            "SAMPLE_COUNT": len(parity),
            "MISMATCHES": parity_mismatches,
            "STREAM": (
                "random.Random('parity:<seed>:<start>:<i>:<j>:<k>')"
                ".sample(non-start in-pool triples, 1)"
            ),
        },
        "START_REPRODUCTION_CHECKS": len(records),
        "BEST_CANONICAL_RECOUNT_FAILURES": recount_failures,
        "PER_START": per_start,
        "OVERALL_BEST": {"START": overall_name, **overall},
        "BEST_START_COUNT": overall["START_COUNT"],
        "BEST_FINAL_COUNT": overall_count,
        "BEST_DELTA": overall["BEST_DELTA"],
        "BEST_PORTFOLIO_SHA256": overall["BEST_PORTFOLIO_SHA256"],
        "BEST_CANONICAL_RECOUNT_STATUS": overall["BEST_CANONICAL_RECOUNT_STATUS"],
        "GAIN_VS_V6": overall_count - V6_COUNT,
        "GAIN_VS_THREE_TICKET_CYCLE_CANDIDATE": overall_count - CYCLE_COUNT,
        "NEW_BEST_STABLE_NON_LANE3_CANDIDATE": (
            "YES" if overall_count > CYCLE_COUNT and clean else "NO"
        ),
        "GAIN_VS_PROTECTED_LANE_3": "NOT_EVALUATED",
        "PROTECTED_LANE_3_TOUCHED": "NO",
        "FULL_N3_OPTIMUM": "NOT_CLAIMED",
        "NOT_CLAIMED": [
            "complete N3 optimality",
            "no gain in complete N3 when the pool has none",
            "gain versus protected Lane 3",
            "overall current-best K20",
        ],
        "RECORDS": records,
        "TIMING": {
            "BINDING_SECONDS": round(binding_seconds, 3),
            "REPAIR_WALL_SECONDS": round(repair_wall_seconds, 3),
            "TOTAL_RUN_SECONDS": round(time.perf_counter() - started, 3),
            "WORKERS": workers,
            "VECLIB_MAXIMUM_THREADS": os.environ.get("VECLIB_MAXIMUM_THREADS", "UNSET"),
        },
        "PEAK_RSS_BYTES": max(_peak_rss_bytes(), *(run.peak_rss_bytes for run in runs)),
        "PEAK_RSS_DEFINITION": "max per-process peak RSS over the main process and workers",
        "TASK_STATUS": "COMPLETE" if clean else "PARITY_OR_RECOUNT_FAILED",
    }
    _write_json_atomically(result_path, record_out)
    return record_out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bounded 24-triple exact repair pilot (R1).")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--workers", type=int, choices=(1, 2), default=2)
    args = parser.parse_args(argv)
    repo_root: Path = args.repo_root
    record = run_pilot(repo_root, result_path=repo_root / RESULT_PATH, workers=args.workers)
    keys = ("TASK_STATUS", "BEST_FINAL_COUNT", "GAIN_VS_V6", "NEW_BEST_STABLE_NON_LANE3_CANDIDATE")
    summary = {key: record[key] for key in keys}
    print(json.dumps(summary, sort_keys=True))
    return 0 if record["TASK_STATUS"] == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
