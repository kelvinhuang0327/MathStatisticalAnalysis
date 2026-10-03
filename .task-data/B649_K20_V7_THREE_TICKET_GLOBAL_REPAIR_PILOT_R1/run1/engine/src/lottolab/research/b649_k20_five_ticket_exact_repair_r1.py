"""B649_K20_FIVE_TICKET_EXACT_REPAIR_PILOT_R1: bounded exact five-ticket repair of K20.

Question: starting from the pinned 313239661 K20 portfolio, remove five complete tickets, freeze
the other fifteen (``R``) and choose five replacements so that OFFICIAL_ANY_PRIZE strictly exceeds
the start. The pilot samples a small, pre-persisted set of destroy quintuples, builds a capped
candidate pool per quintuple and solves the pool exactly. It is not a complete-N5 search: the claim
is limited to the sampled quintuples and their candidate pools.

Exactness. A ticket ``t`` wins outcome (main draw ``D``, special ``s``) when ``|t & D| >= m`` or
``|t & D| == m - 1`` and ``s in t``, which is exactly ``|t & (D | {s})| >= m``. A win therefore
depends only on the ``(draw_size + 1)``-subset ``E = D | {s}`` and each ``E`` stands for
``draw_size + 1`` outcomes (``C(n, d) * (n - d) == C(n, d + 1) * (d + 1)``). All ``C(49, 7)``
subsets ``E`` are enumerated as uint64 bitmasks: no sampling and no historical draws. Every count
is checked against ``b649_official_any_prize_exact.evaluate_portfolio``.

Residual scoring. Let ``R`` be the frozen tickets and ``P`` the candidate pool. The subsets ``E``
not won by ``R`` are grouped by the mask of pool tickets that win them, giving a histogram of
``(winner mask, weight)`` rows. The exact score of any replacement set ``S`` is
``covered_by_R + sum(weight for rows whose mask meets S)``.

Search. Branch and bound over the pool. The only pruning bound is the submodular remaining-slot
bound ``covered + sum of the r largest exact marginals``. The last two slots are solved by an exact
weighted Gram-matrix pair completion. An expired wall limit reports ``FEASIBLE_ONLY``;
``PROVEN_OPTIMAL`` is reported only when every quintuple was either evaluated exactly or eliminated
by the bound.
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
import sys
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from math import comb
from pathlib import Path
from typing import Final

import numpy as np
import numpy.typing as npt

from lottolab.research.b649_official_any_prize_exact import (
    BIG_LOTTO_DRAW_SIZE,
    BIG_LOTTO_OUTRIGHT_MATCHES,
    BIG_LOTTO_POOL_SIZE,
    all_main_draw_masks,
    evaluate_portfolio,
    ticket_mask,
)

type Ticket = tuple[int, ...]
type Portfolio = tuple[Ticket, ...]
type MaskArray = npt.NDArray[np.uint64]
type WeightArray = npt.NDArray[np.int64]
type FloatArray = npt.NDArray[np.float64]

TASK_ID: Final = "B649_K20_FIVE_TICKET_EXACT_REPAIR_PILOT_R1"
PILOT_SEED: Final = 20261001
PORTFOLIO_SIZE: Final = 20
DESTROY_SIZE: Final = 5
R_SIZE: Final = PORTFOLIO_SIZE - DESTROY_SIZE
DESTROY_QUINTUPLE_SAMPLE_COUNT: Final = 8
PARITY_QUINTUPLE_COUNT: Final = 3
PARITY_PORTFOLIOS_PER_QUINTUPLE: Final = 11
CANDIDATE_POOL_MAX: Final = 48
LEVEL2_BEAM_WIDTH: Final = 3
PER_QUINTUPLE_WALL_LIMIT_SECONDS: Final = 15 * 60

START_COUNT: Final = 313239661
START_SHA256: Final = "7ce41ff21d5c0821f1d5dda683e23114086f5024fc6d98d4e574df5306659b1e"
SOURCE_COMMIT: Final = "3655b0f4bc43450748b4fc87c641d0acd11a8509"
SOURCE_ARTIFACT: Final = (
    "docs/research/matrix-native-results/b649-k20-three-ticket-cycle-full-family-r1-result.json"
)

OPTIMALITY_PROVEN: Final = "PROVEN_OPTIMAL"
OPTIMALITY_FEASIBLE: Final = "FEASIBLE_ONLY"
OPTIMALITY_HEURISTIC: Final = "HEURISTIC"

RESULT_IMPROVED: Final = "IMPROVED"
RESULT_NO_IMPROVEMENT: Final = "NO_IMPROVEMENT_IN_BOUNDED_FIVE_TICKET_REPAIR_PILOT"
SCIENTIFIC_SCOPE: Final = "BOUNDED_8_QUINTUPLE_FIVE_TICKET_REPAIR_WITHIN_CANDIDATE_POOL"

# best portfolio of the exhaustive three-ticket single-number cycle scan (SOURCE_COMMIT artifact),
# in the positional order that the destroy positions refer to
START_PORTFOLIO: Final[Portfolio] = (
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

# sealed-geometry v5 K20 (commit 56c9715), OFFICIAL_ANY_PRIZE 312986016
V5_PORTFOLIO: Final[Portfolio] = (
    (1, 2, 34, 41, 42, 45),
    (1, 17, 22, 30, 33, 43),
    (2, 5, 33, 35, 40, 48),
    (3, 4, 10, 15, 26, 27),
    (3, 8, 13, 28, 31, 36),
    (3, 9, 12, 16, 29, 39),
    (4, 7, 36, 37, 39, 44),
    (4, 18, 20, 24, 28, 29),
    (5, 17, 25, 32, 41, 47),
    (6, 7, 9, 13, 18, 26),
    (6, 10, 11, 16, 24, 36),
    (6, 20, 31, 34, 38, 44),
    (7, 8, 10, 14, 19, 29),
    (8, 9, 11, 15, 20, 46),
    (11, 12, 14, 18, 23, 31),
    (12, 13, 15, 19, 24, 37),
    (16, 19, 23, 26, 28, 46),
    (21, 25, 30, 38, 45, 48),
    (21, 32, 40, 42, 43, 49),
    (22, 27, 35, 45, 47, 49),
)

# sealed-geometry v6 K20 (main 76085cc), OFFICIAL_ANY_PRIZE 313239647
V6_PORTFOLIO: Final[Portfolio] = (
    (1, 2, 34, 41, 42, 45),
    (1, 17, 22, 30, 33, 43),
    (2, 5, 33, 35, 40, 48),
    (3, 4, 10, 15, 26, 27),
    (3, 8, 13, 28, 31, 36),
    (3, 9, 12, 16, 29, 39),
    (4, 7, 36, 39, 46, 49),
    (4, 18, 20, 24, 28, 29),
    (5, 17, 25, 32, 41, 47),
    (6, 7, 9, 13, 18, 26),
    (6, 10, 11, 16, 24, 36),
    (6, 14, 20, 31, 37, 39),
    (7, 8, 10, 14, 19, 29),
    (8, 9, 11, 15, 20, 46),
    (11, 12, 18, 23, 27, 49),
    (12, 13, 15, 19, 24, 37),
    (16, 19, 23, 26, 28, 46),
    (21, 25, 30, 38, 45, 48),
    (21, 32, 40, 42, 43, 44),
    (22, 34, 35, 38, 44, 47),
)


@dataclass(frozen=True, slots=True)
class ElitePin:
    """One explicitly pinned stable elite portfolio and its recorded identity."""

    name: str
    tickets: Portfolio
    sha256: str
    outcome_count: int
    source: str


PINNED_ELITES: Final[tuple[ElitePin, ...]] = (
    ElitePin(
        "V5",
        V5_PORTFOLIO,
        "bc755e9b674e2ff37dac0fc8b52bb9f01bfd5a2bf90fc5f9f245dbb049c0ae86",
        312986016,
        "sealed-geometry v5 K20 (commit 56c9715)",
    ),
    ElitePin(
        "V6",
        V6_PORTFOLIO,
        "0c52a1f0bed90cd47d08bb031b13c9bf693317493f88e45da8e087bd4a0ab65b",
        313239647,
        "sealed-geometry v6 K20 (main 76085cc)",
    ),
    ElitePin(
        "CYCLE",
        START_PORTFOLIO,
        START_SHA256,
        START_COUNT,
        "three-ticket cycle full-family best (commit 3655b0f)",
    ),
)


@dataclass(frozen=True, slots=True)
class Geometry:
    """A lottery shape ``(pool_size, draw_size, outright)``; the pilot uses BIG_LOTTO."""

    pool_size: int = BIG_LOTTO_POOL_SIZE
    draw_size: int = BIG_LOTTO_DRAW_SIZE
    outright: int = BIG_LOTTO_OUTRIGHT_MATCHES

    def __post_init__(self) -> None:
        if not 1 <= self.outright <= self.draw_size:
            raise ValueError("outright must be within 1..draw_size")
        if not 2 <= self.draw_size + 1 <= self.pool_size <= 64:
            raise ValueError("geometry must satisfy 2 <= draw_size + 1 <= pool_size <= 64")

    @property
    def subset_size(self) -> int:
        """Size of ``E = D | {s}``; each ``E`` stands for this many outcomes."""

        return self.draw_size + 1

    @property
    def subset_count(self) -> int:
        return comb(self.pool_size, self.subset_size)


BIG_LOTTO_GEOMETRY: Final = Geometry()


# ---------------------------------------------------------------------------------------------
# portfolio identity, destroy step and deterministic sampling
# ---------------------------------------------------------------------------------------------


def normalize_portfolio(
    portfolio: Sequence[Sequence[int]], *, geometry: Geometry = BIG_LOTTO_GEOMETRY
) -> Portfolio:
    """Validate tickets and return them sorted within and across tickets."""

    tickets: list[Ticket] = []
    for raw in portfolio:
        ticket = tuple(sorted(raw))
        if (
            len(ticket) != geometry.draw_size
            or len(set(ticket)) != geometry.draw_size
            or any(type(n) is not int or not 1 <= n <= geometry.pool_size for n in ticket)
        ):
            raise ValueError(f"illegal ticket: {tuple(raw)}")
        tickets.append(ticket)
    if len(set(tickets)) != len(tickets):
        raise ValueError("a portfolio cannot contain duplicate tickets")
    return tuple(sorted(tickets))


def portfolio_sha256(portfolio: Sequence[Sequence[int]]) -> str:
    """Normalized portfolio identity: SHA-256 of the compact JSON of the sorted tickets."""

    payload = json.dumps([list(t) for t in normalize_portfolio(portfolio)], separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class DestroyedPortfolio:
    """A portfolio split into the frozen tickets ``R`` and the removed tickets."""

    positions: tuple[int, ...]
    remaining: Portfolio
    removed: Portfolio


def destroy_positions(portfolio: Portfolio, positions: Sequence[int]) -> DestroyedPortfolio:
    """Remove the tickets at ``positions``; both parts keep the portfolio's positional order."""

    chosen = tuple(sorted(positions))
    if len(set(chosen)) != len(chosen) or any(not 0 <= p < len(portfolio) for p in chosen):
        raise ValueError(f"illegal destroy positions: {tuple(positions)}")
    removed = tuple(portfolio[p] for p in chosen)
    remaining = tuple(t for index, t in enumerate(portfolio) if index not in set(chosen))
    return DestroyedPortfolio(chosen, remaining, removed)


def sample_destroy_quintuples(
    seed: int = PILOT_SEED,
    count: int = DESTROY_QUINTUPLE_SAMPLE_COUNT,
    *,
    portfolio_size: int = PORTFOLIO_SIZE,
    destroy_size: int = DESTROY_SIZE,
) -> tuple[tuple[int, ...], ...]:
    """The ``count`` distinct position sets with the smallest ``sha256(f"{seed}:{positions}")``.

    The rule uses no library RNG, so the sample does not depend on the Python or numpy version. The
    first ``count`` entries of a longer sample equal the shorter sample.
    """

    if not 0 <= count <= comb(portfolio_size, destroy_size):
        raise ValueError("cannot sample that many distinct destroy sets")
    ranked = sorted(
        (hashlib.sha256(f"{seed}:{','.join(map(str, c))}".encode()).hexdigest(), c)
        for c in itertools.combinations(range(portfolio_size), destroy_size)
    )
    return tuple(positions for _, positions in ranked[:count])


def sample_document(sample: Sequence[Sequence[int]]) -> dict[str, object]:
    """The exact document persisted before any scientific scoring."""

    return {
        "TASK_ID": TASK_ID,
        "PILOT_SEED": PILOT_SEED,
        "SAMPLING_METHOD": "smallest sha256(f'{seed}:{comma-joined positions}') over C(20,5)",
        "POPULATION": comb(PORTFOLIO_SIZE, DESTROY_SIZE),
        "DESTROY_QUINTUPLES": [list(positions) for positions in sample],
    }


def canonical_json(document: Mapping[str, object]) -> str:
    return json.dumps(document, indent=1, sort_keys=True) + "\n"


def persist_destroy_sample(path: Path, sample: Sequence[Sequence[int]]) -> str:
    """Write the sample document and return the SHA-256 of the bytes on disk."""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json(sample_document(sample)).encode("utf-8")
    path.write_bytes(payload)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_persisted_sample(path: Path) -> tuple[tuple[int, ...], ...]:
    """Read the persisted sample; it must equal the deterministic sample for the pilot seed."""

    document = json.loads(path.read_text(encoding="utf-8"))
    loaded = tuple(tuple(int(p) for p in positions) for positions in document["DESTROY_QUINTUPLES"])
    if loaded != sample_destroy_quintuples():
        raise ValueError("persisted destroy sample differs from the deterministic pilot sample")
    return loaded


# ---------------------------------------------------------------------------------------------
# exact subset-space enumeration and scoring kernels
# ---------------------------------------------------------------------------------------------


def colex_prefix_masks(size: int, universe: int) -> MaskArray:
    """Every ``size``-subset of ``1..universe`` as a bitmask, in colexicographic order."""

    levels: list[MaskArray] = [np.zeros(1, dtype=np.uint64)]
    levels.extend(np.empty(0, dtype=np.uint64) for _ in range(size))
    for number in range(1, universe + 1):
        bit = np.uint64(1 << (number - 1))
        for width in range(min(size, number), 0, -1):
            levels[width] = np.concatenate((levels[width], levels[width - 1] | bit))
    return levels[size]


def iter_subset_mask_blocks(
    pool_size: int, subset_size: int, *, target_block: int = 1 << 20
) -> Iterator[MaskArray]:
    """Partition all ``subset_size``-subsets of ``1..pool_size`` into bitmask blocks, once each.

    A subset is identified by its two largest numbers ``h1 < h2`` plus a ``subset_size - 2`` subset
    of ``1..h1-1``; in colex order the latter is a prefix, so no per-subset Python work is needed.
    """

    if not 2 <= subset_size <= pool_size <= 64:
        raise ValueError("subset space must satisfy 2 <= subset_size <= pool_size <= 64")
    rest = colex_prefix_masks(subset_size - 2, pool_size - 2)
    pending: list[MaskArray] = []
    pending_size = 0
    for high_one in range(subset_size - 1, pool_size):
        prefix_count = comb(high_one - 1, subset_size - 2)
        if prefix_count == 0:
            continue
        base = rest[:prefix_count] | np.uint64(1 << (high_one - 1))
        for high_two in range(high_one + 1, pool_size + 1):
            pending.append(base | np.uint64(1 << (high_two - 1)))
            pending_size += prefix_count
            if pending_size >= target_block:
                yield np.concatenate(pending)
                pending, pending_size = [], 0
    if pending:
        yield np.concatenate(pending)


def _masks(tickets: Sequence[Ticket]) -> list[np.uint64]:
    return [np.uint64(ticket_mask(ticket)) for ticket in tickets]


def _covered(block: MaskArray, masks: Sequence[np.uint64], outright: int) -> npt.NDArray[np.bool_]:
    """Which subsets in ``block`` are won by at least one of the tickets."""

    covered = np.zeros(block.size, dtype=np.bool_)
    for mask in masks:
        covered |= np.bitwise_count(block & mask) >= outright
    return covered


def covered_subset_count(
    portfolio: Sequence[Ticket], *, geometry: Geometry = BIG_LOTTO_GEOMETRY
) -> int:
    """Number of subsets ``E`` won by the portfolio (direct, no residual decomposition)."""

    masks = _masks(portfolio)
    total = 0
    for block in iter_subset_mask_blocks(geometry.pool_size, geometry.subset_size):
        total += int(np.count_nonzero(_covered(block, masks, geometry.outright)))
    return total


def outcome_count(portfolio: Sequence[Ticket], *, geometry: Geometry = BIG_LOTTO_GEOMETRY) -> int:
    """OFFICIAL_ANY_PRIZE outcome count of a portfolio through the subset identity."""

    return geometry.subset_size * covered_subset_count(portfolio, geometry=geometry)


@dataclass(frozen=True, slots=True)
class PoolHistogram:
    """Winner-mask histogram of the subsets not won by the frozen tickets.

    ``masks[i]`` has bit ``j`` set when pool ticket ``j`` wins ``weights[i]`` residual subsets; rows
    with an empty mask are counted in ``dead_subsets`` and dropped.
    """

    geometry: Geometry
    pool: Portfolio
    masks: MaskArray
    weights: WeightArray
    total_subsets: int
    covered_by_remaining: int
    dead_subsets: int

    @property
    def residual_subsets(self) -> int:
        return self.total_subsets - self.covered_by_remaining

    def subset_value(self, indices: Sequence[int]) -> int:
        """Residual subsets won by the pool tickets at ``indices``."""

        selector = np.uint64(sum(1 << index for index in indices))
        return int(self.weights[(self.masks & selector) != 0].sum())

    def outcome_count(self, indices: Sequence[int]) -> int:
        """OFFICIAL_ANY_PRIZE outcomes won by ``R`` plus the pool tickets at ``indices``."""

        covered = self.covered_by_remaining + self.subset_value(indices)
        return self.geometry.subset_size * covered

    @property
    def remaining_outcome_count(self) -> int:
        return self.geometry.subset_size * self.covered_by_remaining


def _merge_weighted_rows(keys: MaskArray, counts: WeightArray) -> tuple[MaskArray, WeightArray]:
    """Sum the counts of equal keys exactly (integer arithmetic); the result is sorted by key."""

    if keys.size == 0:
        return keys, counts
    order = np.argsort(keys, kind="stable")
    keys, counts = keys[order], counts[order]
    starts = np.concatenate(([0], np.flatnonzero(np.diff(keys)) + 1))
    return keys[starts], np.add.reduceat(counts, starts)


def build_pool_histogram(
    remaining: Sequence[Ticket],
    pool: Sequence[Ticket],
    *,
    geometry: Geometry = BIG_LOTTO_GEOMETRY,
) -> PoolHistogram:
    """One exact pass over all subsets: residual winner-mask histogram of ``pool`` against ``R``."""

    if len(pool) > 63:
        raise ValueError("a pool of more than 63 tickets does not fit a uint64 winner mask")
    remaining_masks = _masks(remaining)
    pool_masks = _masks(pool)
    partial_keys: list[MaskArray] = []
    partial_counts: list[WeightArray] = []
    total = 0
    covered_total = 0
    for block in iter_subset_mask_blocks(geometry.pool_size, geometry.subset_size):
        covered = _covered(block, remaining_masks, geometry.outright)
        residual = block[~covered]
        total += int(block.size)
        covered_total += int(block.size - residual.size)
        winners = np.zeros(residual.size, dtype=np.uint64)
        for index, mask in enumerate(pool_masks):
            wins = np.bitwise_count(residual & mask) >= geometry.outright
            winners |= wins.astype(np.uint64) << np.uint64(index)
        keys, counts = np.unique(winners, return_counts=True)
        partial_keys.append(keys)
        partial_counts.append(counts.astype(np.int64))
    if total != geometry.subset_count:
        raise AssertionError("subset enumeration did not cover the whole subset space")
    all_keys = np.concatenate(partial_keys)
    all_counts = np.concatenate(partial_counts)
    merged_keys, merged_counts = _merge_weighted_rows(all_keys, all_counts)
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


def direct_marginals(
    remaining: Sequence[Ticket],
    tickets: Sequence[Ticket],
    *,
    geometry: Geometry = BIG_LOTTO_GEOMETRY,
) -> list[int]:
    """Exact residual marginal of each ticket (won by it, not by ``R``), by brute force."""

    remaining_masks = _masks(remaining)
    ticket_masks = _masks(tickets)
    totals = [0] * len(tickets)
    for block in iter_subset_mask_blocks(geometry.pool_size, geometry.subset_size):
        residual = block[~_covered(block, remaining_masks, geometry.outright)]
        for index, mask in enumerate(ticket_masks):
            totals[index] += int(
                np.count_nonzero(np.bitwise_count(residual & mask) >= geometry.outright)
            )
    return totals


def scan_neighbors(
    remaining: Sequence[Ticket],
    bases: Sequence[Ticket],
    *,
    geometry: Geometry = BIG_LOTTO_GEOMETRY,
) -> list[dict[Ticket, int]]:
    """Exact residual marginal of every legal one-number mutation of each base ticket.

    A mutation ``t' = t - {a} + {b}`` wins subset ``E`` when
    ``|t' & E| = |p| - [a in p] + [b in E]`` reaches the outright threshold, where ``p = E & t``.
    One pass over the residual subsets tabulates, per base, the subsets by pattern ``p``
    (``|p| >= outright - 1``) and by pattern plus each outside number ``b``; every mutation's
    marginal then follows from those tables without further scoring.
    """

    need = geometry.outright - 1
    code_size = 1 << geometry.draw_size
    remaining_masks = _masks(remaining)
    base_masks = _masks(bases)
    pattern_tables = [np.zeros(code_size, dtype=np.int64) for _ in bases]
    number_tables = [np.zeros((code_size, 64), dtype=np.int64) for _ in bases]
    one = np.uint64(1)
    for block in iter_subset_mask_blocks(geometry.pool_size, geometry.subset_size):
        residual = block[~_covered(block, remaining_masks, geometry.outright)]
        for index, (base, base_mask) in enumerate(zip(bases, base_masks, strict=True)):
            relevant = residual[np.bitwise_count(residual & base_mask) >= need]
            if relevant.size == 0:
                continue
            code = np.zeros(relevant.size, dtype=np.int64)
            for position, number in enumerate(base):
                bit = ((relevant >> np.uint64(number - 1)) & one).astype(np.int64)
                code |= bit << position
            pattern_tables[index] += np.bincount(code, minlength=code_size)
            outside = relevant & ~base_mask
            for _ in range(geometry.subset_size - need):
                lowest = outside & (outside ^ (outside - one))
                present = lowest != 0
                if not present.any():
                    break
                positions = np.bitwise_count(lowest[present] - one).astype(np.int64)
                keys = code[present] * 64 + positions
                number_tables[index] += np.bincount(keys, minlength=code_size * 64).reshape(
                    code_size, 64
                )
                outside = outside & (outside - one)
    patterns = np.arange(code_size)
    pattern_size = np.array([int(p).bit_count() for p in range(code_size)], dtype=np.int64)
    results: list[dict[Ticket, int]] = []
    for base, pattern_table, number_table in zip(bases, pattern_tables, number_tables, strict=True):
        marginals: dict[Ticket, int] = {}
        for position, dropped in enumerate(base):
            kept = pattern_size - ((patterns >> position) & 1)
            with_number = kept >= need
            without_number = kept >= geometry.outright
            for number in range(1, geometry.pool_size + 1):
                if number in base:
                    continue
                containing = number_table[:, number - 1]
                value = int(
                    containing[with_number].sum()
                    + (pattern_table - containing)[without_number].sum()
                )
                mutation = tuple(sorted((set(base) - {dropped}) | {number}))
                marginals[mutation] = value
        results.append(marginals)
    return results


# ---------------------------------------------------------------------------------------------
# candidate pool
# ---------------------------------------------------------------------------------------------

SOURCE_REMOVED: Final = "REMOVED"
SOURCE_ELITE: Final = "ELITE"
SOURCE_MUTATION_L1: Final = "MUTATION_L1"
SOURCE_MUTATION_L2: Final = "MUTATION_L2"


@dataclass(frozen=True, slots=True)
class PoolMember:
    """One pool ticket, its source and its exact residual marginal against ``R``."""

    ticket: Ticket
    source: str
    marginal: int


@dataclass(frozen=True, slots=True)
class PoolPlan:
    """The capped candidate pool of one destroy quintuple, in canonical ticket order."""

    destroyed: DestroyedPortfolio
    members: tuple[PoolMember, ...]
    required_count: int
    universe_size: int
    level1_size: int
    level2_size: int
    excluded_frozen: int
    excluded_required: int

    @property
    def tickets(self) -> Portfolio:
        return tuple(member.ticket for member in self.members)

    def source_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for member in self.members:
            counts[member.source] = counts.get(member.source, 0) + 1
        return dict(sorted(counts.items()))


def _merge_marginal(store: dict[Ticket, int], ticket: Ticket, marginal: int) -> None:
    """Record a marginal; the same ticket reached from two bases must score identically."""

    if store.setdefault(ticket, marginal) != marginal:
        raise AssertionError(f"inconsistent exact marginals for {ticket}")


def assemble_pool(
    start: Portfolio,
    positions: Sequence[int],
    *,
    elites: Sequence[Portfolio],
    pool_max: int = CANDIDATE_POOL_MAX,
    beam_width: int = LEVEL2_BEAM_WIDTH,
    geometry: Geometry = BIG_LOTTO_GEOMETRY,
) -> PoolPlan:
    """Build the capped candidate pool for one destroy set.

    Required first: the removed tickets and every pinned-elite ticket not frozen in ``R``. The rest
    of the capacity goes to the highest exact residual marginal among the legal one-number mutations
    of the removed tickets (level 1) and of each removed ticket's ``beam_width`` best level-1
    mutations (level 2, a cheap two-number neighbourhood), ties to the lowest ticket.
    """

    destroyed = destroy_positions(start, positions)
    frozen = set(destroyed.remaining)
    elite_union = sorted({ticket for elite in elites for ticket in elite})
    required = [ticket for ticket in elite_union if ticket not in frozen]
    required_set = set(required)
    if not set(destroyed.removed) <= required_set:
        raise ValueError("the removed tickets must belong to a pinned elite")
    if len(required) > pool_max:
        raise ValueError("required tickets exceed the pool cap")

    excluded_frozen = 0
    excluded_required = 0

    def admissible(ticket: Ticket) -> bool:
        nonlocal excluded_frozen, excluded_required
        if ticket in frozen:
            excluded_frozen += 1
            return False
        if ticket in required_set:
            excluded_required += 1
            return False
        return True

    level1: dict[Ticket, int] = {}
    best_per_base: list[list[tuple[int, Ticket]]] = []
    for scan in scan_neighbors(destroyed.remaining, destroyed.removed, geometry=geometry):
        ranked: list[tuple[int, Ticket]] = []
        for ticket, marginal in scan.items():
            if admissible(ticket):
                _merge_marginal(level1, ticket, marginal)
                ranked.append((-marginal, ticket))
        best_per_base.append(sorted(ranked)[:beam_width])
    beam_bases = sorted({ticket for ranked in best_per_base for _, ticket in ranked})

    level2: dict[Ticket, int] = {}
    if beam_bases:
        for scan in scan_neighbors(destroyed.remaining, beam_bases, geometry=geometry):
            for ticket, marginal in scan.items():
                if ticket in level1:
                    _merge_marginal(level1, ticket, marginal)
                elif admissible(ticket):
                    _merge_marginal(level2, ticket, marginal)

    universe: dict[Ticket, tuple[str, int]] = {
        ticket: (SOURCE_MUTATION_L1, marginal) for ticket, marginal in level1.items()
    }
    universe.update({ticket: (SOURCE_MUTATION_L2, marginal) for ticket, marginal in level2.items()})
    ranked_universe = sorted(universe.items(), key=lambda item: (-item[1][1], item[0]))
    chosen = ranked_universe[: pool_max - len(required)]

    required_marginals = direct_marginals(destroyed.remaining, required, geometry=geometry)
    removed_set = set(destroyed.removed)
    members = [
        PoolMember(ticket, SOURCE_REMOVED if ticket in removed_set else SOURCE_ELITE, marginal)
        for ticket, marginal in zip(required, required_marginals, strict=True)
    ]
    members.extend(PoolMember(ticket, source, marginal) for ticket, (source, marginal) in chosen)
    members.sort(key=lambda member: member.ticket)
    return PoolPlan(
        destroyed=destroyed,
        members=tuple(members),
        required_count=len(required),
        universe_size=len(universe),
        level1_size=len(level1),
        level2_size=len(level2),
        excluded_frozen=excluded_frozen,
        excluded_required=excluded_required,
    )


# ---------------------------------------------------------------------------------------------
# exact branch and bound over the pool
# ---------------------------------------------------------------------------------------------


class _DeadlineExpiredError(Exception):
    """The per-quintuple wall limit ended the search before a proof."""


@dataclass(frozen=True, slots=True)
class SolveResult:
    """Outcome of one exact pool solve; values are residual subset counts."""

    status: str
    best_value: int
    best_set: tuple[int, ...]
    start_value: int
    nodes_explored: int
    nodes_pruned: int
    leaf_quintuples_evaluated: int
    quintuples_pruned: int
    total_quintuples: int
    seconds: float

    @property
    def improved(self) -> bool:
        return self.best_value > self.start_value

    @property
    def unresolved_quintuples(self) -> int:
        return self.total_quintuples - self.leaf_quintuples_evaluated - self.quintuples_pruned


def remaining_slot_upper_bound(gains: FloatArray, slots: int) -> int:
    """Safe bound on what ``slots`` more tickets add: the sum of the ``slots`` largest marginals.

    Coverage is a union over tickets, so the joint gain of any ``slots`` tickets never exceeds the
    sum of their individual exact marginals given the tickets already chosen.
    """

    if slots <= 0 or gains.size == 0:
        return 0
    if gains.size <= slots:
        return round(float(gains.sum()))
    top = np.partition(gains, gains.size - slots)[gains.size - slots :]
    return round(float(top.sum()))


def evaluate_set(masks: MaskArray, weights: WeightArray, indices: Sequence[int]) -> int:
    """Exact covered weight of a pool subset, straight from the histogram rows."""

    selector = np.uint64(sum(1 << index for index in indices))
    return int(weights[(masks & selector) != 0].sum())


class _Search:
    """Depth-first branch and bound in solver order (columns sorted by single marginal)."""

    def __init__(
        self,
        bits: FloatArray,
        weights: FloatArray,
        pick: int,
        start_value: int,
        start_set: tuple[int, ...],
        deadline: float | None,
        use_bound: bool,
        clock: Callable[[], float],
    ) -> None:
        self.pool_count = int(bits.shape[1])
        self.pick = pick
        self.deadline = deadline
        self.use_bound = use_bound
        self.clock = clock
        self.best_value = start_value
        self.best_set = start_set
        self.nodes_explored = 0
        self.nodes_pruned = 0
        self.leaves = 0
        self.pruned = 0
        self._root_bits = bits
        self._root_weights = weights

    def run(self) -> None:
        self._descend((), 0, self._root_bits, self._root_weights, 0)

    def _offer(self, value: int, chosen: tuple[int, ...]) -> None:
        if value > self.best_value:
            self.best_value = value
            self.best_set = chosen

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
            best = int(np.argmax(gains))
            self.leaves += width
            self._offer(covered + round(float(gains[best])), (*chosen, base + best))
            return
        if self.use_bound and covered + remaining_slot_upper_bound(gains, slots) <= self.best_value:
            self.nodes_pruned += 1
            self.pruned += comb(width, slots)
            return
        if slots == 2:
            weighted = bits * weights[:, None]
            overlap: FloatArray = weighted.T @ bits
            pair_total = gains[:, None] + gains[None, :] - overlap
            rows, cols = np.triu_indices(width, 1)
            values = pair_total[rows, cols]
            best = int(np.argmax(values))
            self.leaves += comb(width, 2)
            self._offer(
                covered + round(float(values[best])),
                (*chosen, base + int(rows[best]), base + int(cols[best])),
            )
            return
        for offset in range(width - slots + 1):
            gain = round(float(gains[offset]))
            if (
                self.use_bound
                and covered + gain + remaining_slot_upper_bound(gains[offset + 1 :], slots - 1)
                <= self.best_value
            ):
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


def solve_exact_repair(
    masks: MaskArray,
    weights: WeightArray,
    pool_count: int,
    pick: int,
    start_set: Sequence[int],
    *,
    deadline: float | None = None,
    use_bound: bool = True,
    clock: Callable[[], float] = time.perf_counter,
) -> SolveResult:
    """Best ``pick``-subset of the pool by covered weight, starting from ``start_set``.

    ``start_set`` is the incumbent (the removed tickets); only a strictly better set replaces it.
    ``deadline`` is a ``clock()`` value (``time.perf_counter`` by default); ``use_bound=False``
    disables pruning and is meant for tests. The result is ``PROVEN_OPTIMAL`` only when the search
    ran to completion.
    """

    if not 1 <= pick <= pool_count <= 63 or len(set(start_set)) != pick:
        raise ValueError("invalid pool or start set")
    started = clock()
    start = tuple(sorted(start_set))
    start_value = evaluate_set(masks, weights, start)
    shifts = np.arange(pool_count, dtype=np.uint64)
    raw_bits = ((masks[:, None] >> shifts[None, :]) & np.uint64(1)).astype(np.float64)
    raw_weights = weights.astype(np.float64)
    single = raw_weights @ raw_bits
    order = np.argsort(-single, kind="stable")
    search = _Search(
        raw_bits[:, order],
        raw_weights,
        pick,
        start_value,
        tuple(int(np.flatnonzero(order == index)[0]) for index in start),
        deadline,
        use_bound,
        clock,
    )
    status = OPTIMALITY_PROVEN
    try:
        search.run()
    except _DeadlineExpiredError:
        status = OPTIMALITY_FEASIBLE
    best_set = start
    if search.best_value > start_value:
        best_set = tuple(sorted(int(order[position]) for position in search.best_set))
    return SolveResult(
        status=status,
        best_value=search.best_value,
        best_set=best_set,
        start_value=start_value,
        nodes_explored=search.nodes_explored,
        nodes_pruned=search.nodes_pruned,
        leaf_quintuples_evaluated=search.leaves,
        quintuples_pruned=search.pruned,
        total_quintuples=comb(pool_count, pick),
        seconds=clock() - started,
    )


def brute_force_best(
    masks: MaskArray, weights: WeightArray, pool_count: int, pick: int
) -> tuple[int, tuple[int, ...]]:
    """Reference optimum by enumerating every ``pick``-subset (first maximiser, lexicographic)."""

    best_value = -1
    best_set: tuple[int, ...] = ()
    for subset in itertools.combinations(range(pool_count), pick):
        value = evaluate_set(masks, weights, subset)
        if value > best_value:
            best_value, best_set = value, subset
    return best_value, best_set


# ---------------------------------------------------------------------------------------------
# one destroy quintuple end to end
# ---------------------------------------------------------------------------------------------


class CanonicalRecounter:
    """Recount portfolios with the canonical outcome-space evaluator over one shared draw space."""

    def __init__(self, geometry: Geometry = BIG_LOTTO_GEOMETRY) -> None:
        self.geometry = geometry
        self.calls = 0
        self._draws: MaskArray | None = None

    def count(self, portfolio: Sequence[Ticket]) -> int:
        if self._draws is None:
            self._draws = all_main_draw_masks(self.geometry.pool_size, self.geometry.draw_size)
        self.calls += 1
        result = evaluate_portfolio(
            portfolio,
            pool_size=self.geometry.pool_size,
            draw_size=self.geometry.draw_size,
            outright_matches=self.geometry.outright,
            draws=self._draws,
        )
        return result.official_any_prize_outcome_count


def verify_pins(recounter: CanonicalRecounter) -> list[dict[str, object]]:
    """Canonically recount the START portfolio and every pinned elite; raise on any drift."""

    records: list[dict[str, object]] = []
    for pin in PINNED_ELITES:
        sha = portfolio_sha256(pin.tickets)
        recount = recounter.count(pin.tickets)
        record: dict[str, object] = {
            "NAME": pin.name,
            "SOURCE": pin.source,
            "TICKET_COUNT": len(pin.tickets),
            "SHA256": sha,
            "EXPECTED_SHA256": pin.sha256,
            "CANONICAL_COUNT": recount,
            "EXPECTED_COUNT": pin.outcome_count,
        }
        records.append(record)
        if len(pin.tickets) != PORTFOLIO_SIZE or sha != pin.sha256 or recount != pin.outcome_count:
            raise AssertionError(f"pinned elite {pin.name} failed its identity recount: {record}")
    return records


def restrict_histogram(
    histogram: PoolHistogram, keep: Sequence[int]
) -> tuple[MaskArray, WeightArray]:
    """Re-express the histogram over the sub-pool ``keep`` (new bit ``i`` is ticket ``keep[i]``)."""

    restricted = np.zeros(histogram.masks.size, dtype=np.uint64)
    for new_bit, old_bit in enumerate(keep):
        column = (histogram.masks >> np.uint64(old_bit)) & np.uint64(1)
        restricted |= column << np.uint64(new_bit)
    live = restricted != 0
    return _merge_weighted_rows(restricted[live], histogram.weights[live])


@dataclass(frozen=True, slots=True)
class QuintupleRepair:
    """Everything recorded for one destroy quintuple."""

    plan: PoolPlan
    histogram_rows: int
    residual_subsets: int
    dead_subsets: int
    remaining_outcomes: int
    start_outcomes: int
    solve: SolveResult
    best_portfolio: Portfolio
    best_count: int
    replaced_positions: tuple[int, ...]
    new_tickets: Portfolio
    canonical_recount: int | None
    plan_seconds: float
    histogram_seconds: float
    total_seconds: float

    @property
    def best_delta(self) -> int:
        return self.best_count - self.start_outcomes


def repair_destroy_quintuple(
    start: Portfolio,
    positions: Sequence[int],
    *,
    elites: Sequence[Portfolio],
    recounter: CanonicalRecounter | None,
    expected_start_count: int | None = None,
    pool_max: int = CANDIDATE_POOL_MAX,
    beam_width: int = LEVEL2_BEAM_WIDTH,
    wall_limit_seconds: float = PER_QUINTUPLE_WALL_LIMIT_SECONDS,
    geometry: Geometry = BIG_LOTTO_GEOMETRY,
) -> QuintupleRepair:
    """Destroy, build the pool, score exactly, solve within the wall limit and recount the best."""

    started = time.perf_counter()
    plan = assemble_pool(
        start, positions, elites=elites, pool_max=pool_max, beam_width=beam_width, geometry=geometry
    )
    planned = time.perf_counter()
    tickets = plan.tickets
    histogram = build_pool_histogram(plan.destroyed.remaining, tickets, geometry=geometry)
    histogram_done = time.perf_counter()
    start_indices = tuple(tickets.index(t) for t in plan.destroyed.removed)
    start_outcomes = histogram.outcome_count(start_indices)
    if expected_start_count is not None and start_outcomes != expected_start_count:
        raise AssertionError(
            f"residual kernel scored the removed tickets at {start_outcomes}, "
            f"expected {expected_start_count}"
        )
    solve = solve_exact_repair(
        histogram.masks,
        histogram.weights,
        len(tickets),
        len(plan.destroyed.positions),
        start_indices,
        deadline=started + wall_limit_seconds,
    )
    chosen = tuple(tickets[index] for index in solve.best_set)
    best_portfolio = normalize_portfolio((*plan.destroyed.remaining, *chosen), geometry=geometry)
    best_count = histogram.outcome_count(solve.best_set)
    removed = set(plan.destroyed.removed)
    recount = recounter.count(best_portfolio) if recounter is not None else None
    if recount is not None and recount != best_count:
        raise AssertionError(f"canonical recount {recount} differs from kernel {best_count}")
    return QuintupleRepair(
        plan=plan,
        histogram_rows=int(histogram.masks.size),
        residual_subsets=histogram.residual_subsets,
        dead_subsets=histogram.dead_subsets,
        remaining_outcomes=histogram.remaining_outcome_count,
        start_outcomes=start_outcomes,
        solve=solve,
        best_portfolio=best_portfolio,
        best_count=best_count,
        replaced_positions=tuple(p for p in plan.destroyed.positions if start[p] not in chosen),
        new_tickets=tuple(sorted(t for t in chosen if t not in removed)),
        canonical_recount=recount,
        plan_seconds=planned - started,
        histogram_seconds=histogram_done - planned,
        total_seconds=time.perf_counter() - started,
    )


# ---------------------------------------------------------------------------------------------
# pre-pilot parity
# ---------------------------------------------------------------------------------------------

TOY_GEOMETRIES: Final = (
    Geometry(13, 6, 3),
    Geometry(14, 6, 4),
    Geometry(16, 6, 4),
    Geometry(12, 5, 3),
    Geometry(10, 4, 2),
)
TOY_TRIALS_PER_GEOMETRY: Final = 4
TOY_SUBSETS_PER_TRIAL: Final = 12
SMALL_POOL_SIZE: Final = 12


@dataclass(frozen=True, slots=True)
class ParityReport:
    """Comparison count, mismatch count and the auditable detail of one parity family."""

    comparisons: int
    mismatches: int
    detail: dict[str, object]


def run_toy_parity(seed: int = PILOT_SEED) -> ParityReport:
    """Toy lotteries: subset kernel, neighbour scan and solver against canonical and brute force."""

    rng = random.Random(seed)
    comparisons = 0
    mismatches = 0
    for geometry in TOY_GEOMETRIES:
        recounter = CanonicalRecounter(geometry)
        every_ticket = list(
            itertools.combinations(range(1, geometry.pool_size + 1), geometry.draw_size)
        )
        for _ in range(TOY_TRIALS_PER_GEOMETRY):
            start = normalize_portfolio(rng.sample(every_ticket, 9), geometry=geometry)
            positions = tuple(sorted(rng.sample(range(len(start)), DESTROY_SIZE)))
            destroyed = destroy_positions(start, positions)
            comparisons += 1
            mismatches += outcome_count(start, geometry=geometry) != recounter.count(start)
            others = [t for t in every_ticket if t not in set(start)]
            pool = tuple(sorted({*destroyed.removed, *rng.sample(others, 9)}))
            histogram = build_pool_histogram(destroyed.remaining, pool, geometry=geometry)
            subsets = itertools.combinations(range(len(pool)), DESTROY_SIZE)
            for subset in rng.sample(list(subsets), TOY_SUBSETS_PER_TRIAL):
                portfolio = (*destroyed.remaining, *(pool[i] for i in subset))
                comparisons += 1
                mismatches += histogram.outcome_count(subset) != recounter.count(portfolio)
            bases = destroyed.removed[:2]
            scans = scan_neighbors(destroyed.remaining, bases, geometry=geometry)
            for scan in scans:
                tickets = sorted(scan)
                direct = direct_marginals(destroyed.remaining, tickets, geometry=geometry)
                comparisons += 1
                complete = len(tickets) == geometry.draw_size * (
                    geometry.pool_size - geometry.draw_size
                )
                mismatches += [scan[t] for t in tickets] != direct or not complete
            start_indices = [pool.index(t) for t in destroyed.removed]
            best_value, _ = brute_force_best(
                histogram.masks, histogram.weights, len(pool), DESTROY_SIZE
            )
            start_value = evaluate_set(histogram.masks, histogram.weights, start_indices)
            for use_bound in (True, False):
                result = solve_exact_repair(
                    histogram.masks,
                    histogram.weights,
                    len(pool),
                    DESTROY_SIZE,
                    start_indices,
                    use_bound=use_bound,
                )
                comparisons += 1
                mismatches += (
                    result.best_value != max(best_value, start_value)
                    or result.status != OPTIMALITY_PROVEN
                    or result.unresolved_quintuples != 0
                )
    return ParityReport(
        comparisons,
        mismatches,
        {
            "GEOMETRIES": [[g.pool_size, g.draw_size, g.outright] for g in TOY_GEOMETRIES],
            "TRIALS_PER_GEOMETRY": TOY_TRIALS_PER_GEOMETRY,
            "CHECKS": [
                "subset identity vs canonical",
                "residual decomposition vs canonical (random 5-subsets)",
                "neighbour scan vs direct marginals",
                "exact solver vs brute force, bound on and off",
            ],
        },
    )


def run_real_parity(recounter: CanonicalRecounter) -> ParityReport:
    """Real 49/20 candidate portfolios and small real pools against the canonical evaluator.

    Uses the three destroy sets that follow the pilot sample in the deterministic ranking, so no
    pilot quintuple is scored before the pilot itself.
    """

    total = DESTROY_QUINTUPLE_SAMPLE_COUNT + PARITY_QUINTUPLE_COUNT
    parity_sets = sample_destroy_quintuples(count=total)[DESTROY_QUINTUPLE_SAMPLE_COUNT:]
    elites = [pin.tickets for pin in PINNED_ELITES]
    portfolio_records: list[dict[str, object]] = []
    small_pool_records: list[dict[str, object]] = []
    comparisons = 0
    mismatches = 0
    for index, positions in enumerate(parity_sets):
        plan = assemble_pool(START_PORTFOLIO, positions, elites=elites)
        tickets = plan.tickets
        histogram = build_pool_histogram(plan.destroyed.remaining, tickets)
        start_indices = tuple(sorted(tickets.index(t) for t in plan.destroyed.removed))
        rng = random.Random(PILOT_SEED + index)
        subsets = [start_indices]
        while len(subsets) < 1 + PARITY_PORTFOLIOS_PER_QUINTUPLE:
            candidate = tuple(sorted(rng.sample(range(len(tickets)), DESTROY_SIZE)))
            if candidate not in subsets:
                subsets.append(candidate)
        for subset in subsets:
            portfolio = normalize_portfolio(
                (*plan.destroyed.remaining, *(tickets[i] for i in subset))
            )
            via_histogram = histogram.outcome_count(subset)
            direct = outcome_count(portfolio)
            canonical = recounter.count(portfolio)
            match = via_histogram == direct == canonical
            if subset == start_indices:
                match = match and canonical == START_COUNT
            comparisons += 1
            mismatches += not match
            portfolio_records.append(
                {
                    "POSITIONS": list(positions),
                    "POOL_INDICES": list(subset),
                    "SHA256": portfolio_sha256(portfolio),
                    "HISTOGRAM_COUNT": via_histogram,
                    "DIRECT_SUBSET_COUNT": direct,
                    "CANONICAL_COUNT": canonical,
                    "MATCH": match,
                }
            )
        others = [i for i in range(len(tickets)) if i not in start_indices]
        cases = {
            "START_INCLUDED": sorted((*start_indices, *others[: SMALL_POOL_SIZE - DESTROY_SIZE])),
            "ARBITRARY_INCUMBENT": list(range(SMALL_POOL_SIZE)),
        }
        for name, keep in cases.items():
            masks, weights = restrict_histogram(histogram, keep)
            if name == "START_INCLUDED":
                incumbent = tuple(keep.index(i) for i in start_indices)
            else:
                incumbent = tuple(range(DESTROY_SIZE))
            brute_value, _ = brute_force_best(masks, weights, len(keep), DESTROY_SIZE)
            result = solve_exact_repair(masks, weights, len(keep), DESTROY_SIZE, incumbent)
            expected = max(brute_value, evaluate_set(masks, weights, incumbent))
            pool_indices = tuple(keep[i] for i in result.best_set)
            best_portfolio = normalize_portfolio(
                (*plan.destroyed.remaining, *(tickets[i] for i in pool_indices))
            )
            canonical = recounter.count(best_portfolio)
            match = (
                result.best_value == expected
                and result.status == OPTIMALITY_PROVEN
                and result.unresolved_quintuples == 0
                and canonical == histogram.outcome_count(pool_indices)
            )
            comparisons += 1
            mismatches += not match
            small_pool_records.append(
                {
                    "POSITIONS": list(positions),
                    "CASE": name,
                    "POOL_SIZE": len(keep),
                    "BRUTE_FORCE_VALUE": brute_value,
                    "SOLVER_VALUE": result.best_value,
                    "IMPROVED_OVER_INCUMBENT": result.improved,
                    "CANONICAL_COUNT_OF_SOLVER_BEST": canonical,
                    "MATCH": match,
                }
            )
    return ParityReport(
        comparisons,
        mismatches,
        {
            "PARITY_DESTROY_QUINTUPLES": [list(p) for p in parity_sets],
            "CANONICAL_PORTFOLIO_COUNT": len(portfolio_records),
            "PORTFOLIOS": portfolio_records,
            "SMALL_POOL_CASES": small_pool_records,
        },
    )


def run_parity(recounter: CanonicalRecounter) -> dict[str, object]:
    """All pre-pilot parity families; ``PARITY_MISMATCHES`` must be zero before the pilot scores."""

    toy = run_toy_parity()
    real = run_real_parity(recounter)
    return {
        "PARITY_SAMPLE_COUNT": toy.comparisons + real.comparisons,
        "PARITY_MISMATCHES": toy.mismatches + real.mismatches,
        "TOY": {"COMPARISONS": toy.comparisons, "MISMATCHES": toy.mismatches, **toy.detail},
        "REAL": {"COMPARISONS": real.comparisons, "MISMATCHES": real.mismatches, **real.detail},
    }


# ---------------------------------------------------------------------------------------------
# result document
# ---------------------------------------------------------------------------------------------

REPO_ROOT: Final = Path(__file__).resolve().parents[3]
MODULE_RELATIVE_PATH: Final = "src/lottolab/research/b649_k20_five_ticket_exact_repair_r1.py"
RESULT_RELATIVE_PATH: Final = (
    "docs/research/matrix-native-results/b649-k20-five-ticket-exact-repair-pilot-r1-result.json"
)
THREAD_ENV_KEYS: Final = (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
)
NOT_CLAIMED: Final = (
    "complete N5 optimum",
    "optimality beyond the sampled destroy quintuples and their candidate pools",
    "global K20 optimum",
    "superiority or equality relative to protected Lane 3",
)
POOL_SOURCE_DEFINITIONS: Final = {
    "REMOVED": "the five removed tickets (always in the pool)",
    "ELITE": (
        "tickets of the pinned elites V5, V6 and CYCLE that are not frozen in R "
        "(always in the pool)"
    ),
    "MUTATION_L1": (
        "legal one-number mutations of the removed tickets, ranked by exact residual marginal"
    ),
    "MUTATION_L2": (
        "one-number mutations of each removed ticket's three best level-1 mutations (bounded "
        "two-number neighbourhood), ranked by exact residual marginal"
    ),
    "CAP_RULE": (
        "required tickets first; remaining capacity by highest exact residual marginal against R, "
        "ties to the lowest ticket; pool cap 48 is a heuristic"
    ),
}


def _as_int(value: object) -> int:
    if not isinstance(value, int):
        raise TypeError(f"expected an integer, got {type(value).__name__}")
    return value


def peak_memory_bytes() -> int:
    """Peak resident set size of this process (macOS reports bytes, Linux kilobytes)."""

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if sys.platform == "darwin" else peak * 1024


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _git_identity() -> dict[str, str]:
    def git(*args: str) -> str:
        completed = subprocess.run(
            ["git", *args], cwd=REPO_ROOT, check=True, capture_output=True, text=True
        )
        return completed.stdout.strip()

    return {"RUN_HEAD": git("rev-parse", "HEAD"), "RUN_TREE": git("rev-parse", "HEAD^{tree}")}


def _repair_record(repair: QuintupleRepair) -> dict[str, object]:
    plan, solve = repair.plan, repair.solve
    scale = BIG_LOTTO_GEOMETRY.subset_size
    return {
        "POSITIONS": list(plan.destroyed.positions),
        "REMOVED_TICKETS": [list(t) for t in plan.destroyed.removed],
        "POOL_SIZE": len(plan.members),
        "POOL_SOURCE_COUNTS": plan.source_counts(),
        "POOL_REQUIRED_COUNT": plan.required_count,
        "CANDIDATE_UNIVERSE_SIZE": plan.universe_size,
        "LEVEL1_CANDIDATES": plan.level1_size,
        "LEVEL2_CANDIDATES": plan.level2_size,
        "EXCLUDED_MUTATIONS_EQUAL_TO_FROZEN": plan.excluded_frozen,
        "EXCLUDED_MUTATIONS_EQUAL_TO_REQUIRED": plan.excluded_required,
        "POOL": [
            {
                "TICKET": list(member.ticket),
                "SOURCE": member.source,
                "RESIDUAL_MARGINAL_OUTCOMES": scale * member.marginal,
            }
            for member in plan.members
        ],
        "HISTOGRAM_ROWS": repair.histogram_rows,
        "RESIDUAL_SUBSETS": repair.residual_subsets,
        "DEAD_SUBSETS": repair.dead_subsets,
        "OUTCOMES_WON_BY_FROZEN_R": repair.remaining_outcomes,
        "START_OUTCOMES_VIA_KERNEL": repair.start_outcomes,
        "OPTIMALITY_STATUS": solve.status,
        "BEST_COUNT": repair.best_count,
        "BEST_DELTA": repair.best_delta,
        "IMPROVED": solve.improved,
        "BEST_POOL_INDICES": list(solve.best_set),
        "BEST_REPLACED_POSITIONS": list(repair.replaced_positions),
        "BEST_NEW_TICKETS": [list(t) for t in repair.new_tickets],
        "BEST_PORTFOLIO_SHA256": portfolio_sha256(repair.best_portfolio),
        "CANONICAL_RECOUNT": repair.canonical_recount,
        "CANONICAL_MATCH": repair.canonical_recount == repair.best_count,
        "NODES_EXPLORED": solve.nodes_explored,
        "NODES_PRUNED": solve.nodes_pruned,
        "LEAF_QUINTUPLES_EVALUATED": solve.leaf_quintuples_evaluated,
        "QUINTUPLES_ELIMINATED_BY_BOUND": solve.quintuples_pruned,
        "TOTAL_QUINTUPLES": solve.total_quintuples,
        "UNRESOLVED_QUINTUPLES": solve.unresolved_quintuples,
        "SECONDS": {
            "POOL": round(repair.plan_seconds, 3),
            "HISTOGRAM": round(repair.histogram_seconds, 3),
            "SOLVE": round(solve.seconds, 3),
            "TOTAL": round(repair.total_seconds, 3),
        },
    }


def build_result_document(
    *,
    sample: Sequence[Sequence[int]],
    sample_sha256: str,
    sample_persisted_at: str,
    pins: Sequence[Mapping[str, object]],
    parity: Mapping[str, object],
    repairs: Sequence[QuintupleRepair],
    start_recount: int,
    wall_seconds: float,
    peak_memory: int,
    run_identity: Mapping[str, str],
    module_sha256: str,
    phase_seconds: Mapping[str, float],
) -> dict[str, object]:
    """Assemble the pilot result; the global best is the highest count, then the lowest sha256."""

    if len(repairs) != len(sample):
        raise ValueError("every sampled destroy quintuple needs exactly one repair record")
    pool_sizes = [len(repair.plan.members) for repair in repairs]
    statuses = [repair.solve.status for repair in repairs]
    winner = min(repairs, key=lambda r: (-r.best_count, portfolio_sha256(r.best_portfolio)))
    improved = winner.best_count > START_COUNT
    if improved:
        best_portfolio = winner.best_portfolio
        best_count = winner.best_count
        best_replaced = list(winner.replaced_positions)
        best_new = [list(t) for t in winner.new_tickets]
        best_recount = winner.canonical_recount
        best_positions: list[int] | None = list(winner.plan.destroyed.positions)
    else:
        best_portfolio = normalize_portfolio(START_PORTFOLIO)
        best_count = START_COUNT
        best_replaced, best_new, best_recount = [], [], start_recount
        best_positions = None
    recount_pass = best_recount == best_count
    leaves = sum(r.solve.leaf_quintuples_evaluated for r in repairs)
    pool_scored = sum(r.plan.universe_size + r.plan.required_count for r in repairs)
    result = RESULT_IMPROVED if improved and recount_pass else RESULT_NO_IMPROVEMENT
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "COMPLETE",
        "SCIENTIFIC_RESULT": result,
        "NEW_STABLE_NON_LANE3_GAIN": "YES" if result == RESULT_IMPROVED else "NO",
        "SCIENTIFIC_SCOPE": SCIENTIFIC_SCOPE,
        "COMPLETE_N5_OPTIMUM": "NOT_CLAIMED",
        "GAIN_VS_PROTECTED_LANE_3": "NOT_EVALUATED",
        "PROTECTED_LANE_3_TOUCHED": "NO",
        "NOT_CLAIMED": list(NOT_CLAIMED),
        "START_COUNT": START_COUNT,
        "START_SHA256": START_SHA256,
        "START_CANONICAL_RECOUNT": start_recount,
        "START_PORTFOLIO": [list(t) for t in START_PORTFOLIO],
        "START_SOURCE_COMMIT": SOURCE_COMMIT,
        "START_SOURCE_ARTIFACT": SOURCE_ARTIFACT,
        "PINNED_ELITES": [dict(pin) for pin in pins],
        "PILOT_SEED": PILOT_SEED,
        "DESTROY_SIZE": DESTROY_SIZE,
        "R_SIZE": R_SIZE,
        "DESTROY_QUINTUPLE_SAMPLE_COUNT": DESTROY_QUINTUPLE_SAMPLE_COUNT,
        "DESTROY_QUINTUPLES": [list(positions) for positions in sample],
        "DESTROY_QUINTUPLES_TESTED": len(repairs),
        "SAMPLE_FILE_SHA256": sample_sha256,
        "SAMPLE_PERSISTED_AT": sample_persisted_at,
        "SAMPLE_PERSISTED_BEFORE_SCORING": True,
        "SAMPLING_METHOD": sample_document(sample)["SAMPLING_METHOD"],
        "CANDIDATE_POOL_MAX": CANDIDATE_POOL_MAX,
        "LEVEL2_BEAM_WIDTH": LEVEL2_BEAM_WIDTH,
        "POOL_SOURCE_DEFINITIONS": dict(POOL_SOURCE_DEFINITIONS),
        "POOL_SIZE_MIN": min(pool_sizes),
        "POOL_SIZE_MAX": max(pool_sizes),
        "POOL_SIZE_MEAN": round(sum(pool_sizes) / len(pool_sizes), 3),
        "SOLVER": "EXACT_BRANCH_AND_BOUND_NUMPY_GRAM_PAIR_COMPLETION",
        "SOLVER_DETAIL": (
            "DFS over pool tickets in descending single-marginal order; pruning only by the "
            "submodular remaining-slot bound (covered + sum of the r largest exact marginals); "
            "the last two slots are solved exactly by a weighted Gram matrix; strict-improvement "
            "incumbent starting at the removed tickets; no heuristic prunes"
        ),
        "PER_QUINTUPLE_WALL_LIMIT_SECONDS": PER_QUINTUPLE_WALL_LIMIT_SECONDS,
        "PROVEN_OPTIMAL_QUINTUPLES": statuses.count(OPTIMALITY_PROVEN),
        "FEASIBLE_ONLY_QUINTUPLES": statuses.count(OPTIMALITY_FEASIBLE),
        "HEURISTIC_QUINTUPLES": statuses.count(OPTIMALITY_HEURISTIC),
        "PARITY_SAMPLE_COUNT": parity["PARITY_SAMPLE_COUNT"],
        "PARITY_MISMATCHES": parity["PARITY_MISMATCHES"],
        "PARITY": dict(parity),
        "NODES_EXPLORED": sum(r.solve.nodes_explored for r in repairs),
        "NODES_PRUNED": sum(r.solve.nodes_pruned for r in repairs),
        "LEAF_QUINTUPLES_EVALUATED": leaves,
        "QUINTUPLES_ELIMINATED_BY_BOUND": sum(r.solve.quintuples_pruned for r in repairs),
        "POOL_CANDIDATES_SCORED_EXACT": pool_scored,
        "EXACT_CANDIDATES_SCORED": pool_scored + leaves,
        "EXACT_CANDIDATES_SCORED_DEFINITION": (
            "pool tickets scored by exact residual marginal (admissible universe plus required "
            "tickets) plus complete quintuples evaluated exactly at solver leaves"
        ),
        "WALL_SECONDS": round(wall_seconds, 3),
        "PHASE_SECONDS": {name: round(seconds, 3) for name, seconds in phase_seconds.items()},
        "PEAK_MEMORY_BYTES": peak_memory,
        "PEAK_MEMORY_DEFINITION": "ru_maxrss of the single pilot process (one worker, no children)",
        "CPU_POLICY": {
            "PROCESSES": 1,
            "THREAD_ENV": {key: os.environ.get(key) for key in THREAD_ENV_KEYS},
        },
        "BEST_COUNT": best_count,
        "BEST_DELTA": best_count - START_COUNT,
        "BEST_SHA256": portfolio_sha256(best_portfolio),
        "BEST_REPLACED_INDICES": best_replaced,
        "BEST_NEW_TICKETS": best_new,
        "BEST_PORTFOLIO": [list(t) for t in best_portfolio],
        "BEST_DESTROY_POSITIONS": best_positions,
        "BEST_CANONICAL_RECOUNT": best_recount,
        "BEST_CANONICAL_RECOUNT_STATUS": "PASS" if recount_pass else "FAIL",
        "TIE_BREAK": "max exact count, then lowest normalized portfolio sha256",
        "PER_QUINTUPLE": [_repair_record(repair) for repair in repairs],
        "RUN_HEAD": run_identity["RUN_HEAD"],
        "RUN_TREE": run_identity["RUN_TREE"],
        "SOURCE_MODULE_PATH": MODULE_RELATIVE_PATH,
        "SOURCE_MODULE_SHA256": module_sha256,
    }


def record_progress(workdir: Path, event: Mapping[str, object]) -> None:
    """Print one progress event and append it to ``progress.jsonl``.

    The protected launcher captures stdout only at completion, so the file is what a watcher can
    read while the pilot runs.
    """

    line = json.dumps({"AT": _utc_now(), **event}, sort_keys=True)
    print(line, flush=True)
    with (workdir / "progress.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def write_atomically(path: Path, text: str) -> None:
    """Write ``text`` beside ``path`` and rename it into place; a crash leaves no partial file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".partial")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def run_pilot(workdir: Path, output: Path) -> dict[str, object]:
    """Persist the sample, verify pins, run parity, score the sample and write the result JSON."""

    wall_started = time.perf_counter()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    sample = sample_destroy_quintuples()
    sample_path = workdir / "destroy-sample.json"
    sample_sha256 = persist_destroy_sample(sample_path, sample)
    persisted_at = _utc_now()
    record_progress(
        workdir, {"EVENT": "SAMPLE_PERSISTED", "SHA256": sample_sha256, "PATH": str(sample_path)}
    )
    scored_sample = load_persisted_sample(sample_path)
    recounter = CanonicalRecounter()
    phase_started = time.perf_counter()
    pins = verify_pins(recounter)
    record_progress(workdir, {"EVENT": "PINS_VERIFIED", "PINS": [str(pin["NAME"]) for pin in pins]})
    parity = run_parity(recounter)
    parity_done = time.perf_counter()
    record_progress(
        workdir,
        {
            "EVENT": "PARITY_DONE",
            "COMPARISONS": parity["PARITY_SAMPLE_COUNT"],
            "MISMATCHES": parity["PARITY_MISMATCHES"],
        },
    )
    if _as_int(parity["PARITY_MISMATCHES"]) != 0:
        raise AssertionError("pre-pilot parity found mismatches; the pilot must not score")
    elites = [pin.tickets for pin in PINNED_ELITES]
    repairs: list[QuintupleRepair] = []
    for positions in scored_sample:
        repair = repair_destroy_quintuple(
            START_PORTFOLIO,
            positions,
            elites=elites,
            recounter=recounter,
            expected_start_count=START_COUNT,
        )
        repairs.append(repair)
        record_progress(
            workdir,
            {
                "EVENT": "QUINTUPLE_DONE",
                "POSITIONS": list(positions),
                "POOL_SIZE": len(repair.plan.members),
                "STATUS": repair.solve.status,
                "BEST_DELTA": repair.best_delta,
                "SECONDS": round(repair.total_seconds, 1),
            },
        )
    pilot_done = time.perf_counter()
    document = build_result_document(
        sample=scored_sample,
        sample_sha256=sample_sha256,
        sample_persisted_at=persisted_at,
        pins=pins,
        parity=parity,
        repairs=repairs,
        start_recount=recounter.count(START_PORTFOLIO),
        wall_seconds=time.perf_counter() - wall_started,
        peak_memory=peak_memory_bytes(),
        run_identity=_git_identity(),
        module_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        phase_seconds={
            "PINS_AND_PARITY": parity_done - phase_started,
            "PILOT": pilot_done - parity_done,
        },
    )
    write_atomically(output, canonical_json(document))
    record_progress(workdir, {"EVENT": "RESULT_WRITTEN", "PATH": str(output)})
    return document


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="b649_k20_five_ticket_exact_repair_r1", description=__doc__
    )
    commands = parser.add_subparsers(dest="command", required=True)
    pilot = commands.add_parser("pilot", help="run parity, then the sampled pilot, and write JSON")
    pilot.add_argument("--workdir", type=Path, required=True)
    pilot.add_argument("--output", type=Path, required=True)
    commands.add_parser("parity", help="run only the pre-pilot parity checks")
    args = parser.parse_args(argv)
    if args.command == "pilot":
        document = run_pilot(args.workdir, args.output)
        print(
            f"result={document['SCIENTIFIC_RESULT']} best_count={document['BEST_COUNT']} "
            f"delta={document['BEST_DELTA']} wall_seconds={document['WALL_SECONDS']}",
            flush=True,
        )
        return 0
    parity = run_parity(CanonicalRecounter())
    print(canonical_json(parity))
    return 0 if parity["PARITY_MISMATCHES"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
