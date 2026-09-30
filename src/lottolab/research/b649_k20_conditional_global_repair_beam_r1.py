"""B649_K20_CONDITIONAL_GLOBAL_REPAIR_BEAM_R1: interaction-aware beam repair of the K20 incumbent.

Question: does ranking replacement tickets once and individually against the frozen remainder
``R`` (the global residual-pool pilot, commit b470fbf) miss tickets that only pay off next to
other replacements? Starting from the pinned 313239661 K20 portfolio and the SAME three destroy-4
and three destroy-5 sets as that pilot, the replacement slots are filled by a beam search whose
candidate generation is conditional: for every retained partial replacement set ``S`` the
complete legal universe (all C(49,6) = 13,983,816 tickets) is re-scored exactly against
``R + S``, and the 8 legal tickets with the largest conditional marginal become children.
Children are deduplicated as sets and the beam keeps the 8 states of largest exact union
coverage, ties to the lowest canonical state identity (the sorted replacement tickets).

Exactness. The conditional marginal is the residual marginal of the reused global scorer with
``R + S`` as the frozen tickets, so every expansion keeps that scorer's two exact identities
(``sum g6 = 7 |U|`` and ``sum m = K |U|``) with ``|U|`` taken from the state's chained coverage.
A child's coverage is its parent's plus the chosen ticket's conditional marginal; the chain is
recounted with the canonical evaluator for every retained state at every depth, and every final
best-count tie is recounted canonically.

The search is INTERACTION_AWARE (each slot is ranked given the slots already chosen) but
HEURISTIC: BEAM_WIDTH = 8 and 8 children per state bound it, so no N4 or N5 optimum is claimed.
There is no local-mutation prefilter and no random ticket sampling.
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
from dataclasses import dataclass, field
from math import comb
from pathlib import Path
from typing import Final, cast

import numpy as np

from lottolab.research import b649_k20_five_ticket_exact_repair_r1 as five_ticket
from lottolab.research import b649_k20_global_residual_pool_repair_r1 as global_pool
from lottolab.research.b649_k20_five_ticket_exact_repair_r1 import (
    PORTFOLIO_SIZE,
    START_COUNT,
    START_PORTFOLIO,
    START_SHA256,
    CanonicalRecounter,
    DestroyedPortfolio,
    Geometry,
    Portfolio,
    Ticket,
    canonical_json,
    destroy_positions,
    direct_marginals,
    normalize_portfolio,
    peak_memory_bytes,
    portfolio_sha256,
    record_progress,
    verify_pins,
    write_atomically,
)
from lottolab.research.b649_k20_global_residual_pool_repair_r1 import (
    GLOBAL_TOP_MARGINAL,
    OUTRIGHT,
    SUBSET_SIZE,
    TICKET_SIZE,
    TOTAL_TICKETS,
    ColexUniverse,
    CountArray,
    GlobalScores,
    IndexArray,
    ParityTally,
    StopConditionError,
    SubsetTable,
    brute_force_marginals,
    build_universe,
    check_score_identities,
    exact_global_rank,
    global_top,
    parity_destroy_sets,
    pilot_destroy_sets,
    reproduce_start,
    score_all_tickets,
    top_ticket_indices,
)

TASK_ID: Final = "B649_K20_CONDITIONAL_GLOBAL_REPAIR_BEAM_R1"
BEAM_WIDTH: Final = 8
EXPANSION_WIDTH: Final = 8
DESTROY_SIZES: Final = (4, 5)
SEARCH_CLASS: Final = "INTERACTION_AWARE"
OPTIMALITY_STATUS: Final = "HEURISTIC_BEAM_WIDTH_8"

REUSE_COMMIT: Final = "b470fbfd2eae74bc3c567408746951a8f27c306a"
REUSE_TASK_ID: Final = global_pool.TASK_ID
REUSE_ARTIFACT: Final = global_pool.RESULT_RELATIVE_PATH


def depth_for(destroy_size: int) -> int:
    """Beam depth of a destroy set: one level per removed ticket (4 or 5)."""

    if destroy_size not in DESTROY_SIZES:
        raise ValueError(f"unsupported destroy size {destroy_size}")
    return destroy_size


# ---------------------------------------------------------------------------------------------
# exact next-ticket selection over the complete universe
# ---------------------------------------------------------------------------------------------


def next_ticket_indices(
    marginals: CountArray,
    tickets: SubsetTable,
    frozen_indices: Sequence[int],
    count: int,
) -> IndexArray:
    """Colex indices of the ``count`` best LEGAL next tickets in rank order.

    Rank is the conditional marginal, highest first, ties to the lexicographically lowest ticket
    (the reused exact global ranking). A frozen ticket (in ``R`` or already in ``S``) is not a
    legal next ticket. The reused ranking returns the true top ``count + |frozen|`` of all tickets;
    dropping the frozen ones leaves the true top ``count`` of the legal tickets in the same order.
    """

    frozen = {int(index) for index in frozen_indices}
    total = int(marginals.size)
    if not 1 <= count <= total - len(frozen):
        raise ValueError("count must be within 1..number of legal tickets")
    ranked = top_ticket_indices(marginals, tickets, min(total, count + len(frozen)))
    chosen = [int(index) for index in ranked if int(index) not in frozen][:count]
    return np.array(chosen, dtype=np.int64)


@dataclass(frozen=True, slots=True)
class NextTicket:
    """One child ticket of an expansion: conditional marginal (7-subsets) and 1-based position."""

    ticket: Ticket
    index: int
    marginal: int
    position: int


@dataclass(frozen=True, slots=True)
class CutoffStats:
    """How many legal tickets beat or tie the last retained next ticket (diagnostic)."""

    threshold: int
    above: int
    tied: int


def cutoff_stats(
    marginals: CountArray, frozen_indices: Sequence[int], threshold: int
) -> CutoffStats:
    """Legal tickets strictly above and exactly at the expansion cutoff marginal."""

    frozen_values = [int(marginals[index]) for index in set(frozen_indices)]
    above = int(np.count_nonzero(marginals > threshold)) - sum(v > threshold for v in frozen_values)
    tied = int(np.count_nonzero(marginals == threshold)) - sum(
        v == threshold for v in frozen_values
    )
    return CutoffStats(threshold=threshold, above=above, tied=tied)


# ---------------------------------------------------------------------------------------------
# beam states, expansions and levels
# ---------------------------------------------------------------------------------------------


def canonical_state(tickets: Sequence[Sequence[int]]) -> Portfolio:
    """Canonical identity of a partial replacement set: its tickets sorted within and across."""

    return tuple(sorted(tuple(sorted(ticket)) for ticket in tickets))


@dataclass(frozen=True, slots=True)
class BeamState:
    """A partial replacement set ``S`` and the exact 7-subsets won by ``R + S``.

    ``parent``/``added`` record the first expansion that produced the state (expansion order is
    the parent beam's retention order, then child position), so provenance is deterministic.
    """

    tickets: Portfolio
    covered: int
    parent: Portfolio | None = None
    added: Ticket | None = None
    added_marginal: int = 0
    added_position: int = 0


def retention_key(state: BeamState) -> tuple[int, Portfolio]:
    """Beam order: exact union coverage descending, then the lowest canonical state identity."""

    return (-state.covered, state.tickets)


@dataclass(frozen=True, slots=True)
class Expansion:
    """One conditional enumeration: a retained parent state and its top legal next tickets."""

    level: int
    parent: BeamState
    residual_subsets: int
    identities: dict[str, object]
    children: tuple[NextTicket, ...]
    cutoff: CutoffStats
    seconds: float

    @property
    def conditional(self) -> bool:
        """True when the marginals are conditioned on at least one replacement ticket."""

        return bool(self.parent.tickets)

    @property
    def tickets_scored(self) -> int:
        return cast(int, self.identities["TICKETS_SCORED"])


@dataclass(frozen=True, slots=True)
class BeamLevel:
    """All unique children of one depth in retention order, and the ``beam_width`` it keeps."""

    level: int
    generated: int
    duplicates: int
    candidates: tuple[BeamState, ...]
    retained: tuple[BeamState, ...]

    @property
    def unique(self) -> int:
        return len(self.candidates)

    @property
    def cutoff_covered(self) -> int:
        return self.retained[-1].covered

    @property
    def candidates_tied_at_cutoff(self) -> int:
        return sum(1 for state in self.candidates if state.covered == self.cutoff_covered)

    @property
    def retained_tied_at_cutoff(self) -> int:
        return sum(1 for state in self.retained if state.covered == self.cutoff_covered)


@dataclass(frozen=True, slots=True)
class BeamRun:
    """A complete beam over one frozen remainder ``R``."""

    remaining: Portfolio
    base_covered: int
    depth: int
    beam_width: int
    expansion_width: int
    expansions: tuple[Expansion, ...]
    levels: tuple[BeamLevel, ...]

    @property
    def final(self) -> BeamLevel:
        return self.levels[-1]

    @property
    def best(self) -> BeamState:
        return self.final.retained[0]

    @property
    def enumerations(self) -> int:
        return len(self.expansions)

    @property
    def tickets_scored(self) -> int:
        return sum(expansion.tickets_scored for expansion in self.expansions)

    @property
    def generated(self) -> int:
        return sum(level.generated for level in self.levels)

    @property
    def unique(self) -> int:
        return sum(level.unique for level in self.levels)

    @property
    def duplicates(self) -> int:
        return sum(level.duplicates for level in self.levels)

    @property
    def retained(self) -> int:
        return sum(len(level.retained) for level in self.levels)

    def final_ties(self) -> tuple[BeamState, ...]:
        """Every unique final-depth state whose coverage equals the best final coverage."""

        return tuple(state for state in self.final.candidates if state.covered == self.best.covered)


type ExpansionHook = Callable[[Expansion, GlobalScores, Portfolio], None]


def run_beam(
    universe: ColexUniverse,
    remaining: Sequence[Ticket],
    depth: int,
    *,
    base_covered: int,
    beam_width: int = BEAM_WIDTH,
    expansion_width: int = EXPANSION_WIDTH,
    inspect: ExpansionHook | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> BeamRun:
    """Conditional beam: every retained state re-scores the whole universe against ``R + S``.

    ``base_covered`` is the exact number of 7-subsets won by ``R`` (the canonical count / 7); it
    seeds the coverage chain, which each expansion's identity check then verifies independently.
    ``inspect`` sees every expansion with its complete score table and the frozen tickets.
    """

    if depth < 1 or beam_width < 1 or expansion_width < 1:
        raise ValueError("depth, beam width and expansion width must be positive")
    remaining = tuple(remaining)
    subset_total = comb(universe.pool_size, SUBSET_SIZE)
    beam: tuple[BeamState, ...] = (BeamState((), base_covered),)
    expansions: list[Expansion] = []
    levels: list[BeamLevel] = []
    for level in range(1, depth + 1):
        children: dict[Portfolio, BeamState] = {}
        generated = 0
        duplicates = 0
        for parent in beam:
            started = clock()
            frozen: Portfolio = (*remaining, *parent.tickets)
            scores = score_all_tickets(universe, frozen)
            residual = subset_total - parent.covered
            try:
                identities = check_score_identities(scores, universe, residual)
            except AssertionError as error:
                raise StopConditionError(
                    "CONDITIONAL_ENUMERATION_IDENTITY_REFUTED", str(error)
                ) from error
            frozen_indices = [universe.index_of(ticket) for ticket in frozen]
            chosen = next_ticket_indices(
                scores.marginals, universe.tickets, frozen_indices, expansion_width
            )
            nexts = tuple(
                NextTicket(
                    universe.ticket_at(int(index)), int(index), int(scores.marginals[index]), place
                )
                for place, index in enumerate(chosen, start=1)
            )
            expansion = Expansion(
                level=level,
                parent=parent,
                residual_subsets=residual,
                identities=identities,
                children=nexts,
                cutoff=cutoff_stats(scores.marginals, frozen_indices, nexts[-1].marginal),
                seconds=clock() - started,
            )
            if inspect is not None:
                inspect(expansion, scores, frozen)
            expansions.append(expansion)
            for child in nexts:
                generated += 1
                tickets = canonical_state((*parent.tickets, child.ticket))
                covered = parent.covered + child.marginal
                existing = children.get(tickets)
                if existing is not None:
                    duplicates += 1
                    if existing.covered != covered:
                        raise StopConditionError(
                            "PARITY_MISMATCH",
                            f"a child reached from two parents has two coverages: {tickets}",
                        )
                    continue
                children[tickets] = BeamState(
                    tickets, covered, parent.tickets, child.ticket, child.marginal, child.position
                )
        candidates = tuple(sorted(children.values(), key=retention_key))
        beam = candidates[:beam_width]
        levels.append(BeamLevel(level, generated, duplicates, candidates, beam))
    return BeamRun(
        remaining=remaining,
        base_covered=base_covered,
        depth=depth,
        beam_width=beam_width,
        expansion_width=expansion_width,
        expansions=tuple(expansions),
        levels=tuple(levels),
    )


# ---------------------------------------------------------------------------------------------
# reuse binding: the same destroy sets and the one-shot global ranking of commit b470fbf
# ---------------------------------------------------------------------------------------------

REPO_ROOT: Final = Path(__file__).resolve().parents[3]

type DestroySets = dict[int, tuple[tuple[int, ...], ...]]
type SetKey = tuple[int, tuple[int, ...]]


def read_reuse_artifact(repo_root: Path = REPO_ROOT) -> dict[str, object]:
    """The one-shot global residual-pool result, read-only from its pinned commit."""

    target = f"{REUSE_COMMIT}:{REUSE_ARTIFACT}"
    probe = subprocess.run(
        ["git", "cat-file", "-e", target], cwd=repo_root, capture_output=True, check=False
    )
    if probe.returncode != 0:
        raise StopConditionError("MISSING_REUSE_COMMIT", target)
    shown = subprocess.run(["git", "show", target], cwd=repo_root, capture_output=True, check=True)
    document: object = json.loads(shown.stdout)
    if not isinstance(document, dict):
        raise StopConditionError("REUSE_ARTIFACT_MISMATCH", "the reuse artifact is not an object")
    return cast(dict[str, object], document)


@dataclass(frozen=True, slots=True)
class PriorRanked:
    """One entry of the one-shot global top 48 of a destroy set (outcomes, not 7-subsets)."""

    ticket: Ticket
    rank: int
    marginal_outcomes: int


@dataclass(frozen=True, slots=True)
class PriorSet:
    """What the one-shot pilot recorded for one destroy set."""

    size: int
    positions: tuple[int, ...]
    removed: Portfolio
    top: tuple[PriorRanked, ...]
    pool: frozenset[Ticket]
    best_count: int
    best_sha256: str

    @property
    def top_tickets(self) -> frozenset[Ticket]:
        return frozenset(entry.ticket for entry in self.top)


def _ticket(raw: object) -> Ticket:
    return tuple(sorted(cast(int, number) for number in cast(list[object], raw)))


def load_prior_sets(document: Mapping[str, object]) -> tuple[DestroySets, dict[SetKey, PriorSet]]:
    """Bind the destroy sets and per-set top 48 of the reuse artifact; any drift is a STOP."""

    expected = pilot_destroy_sets()
    sets: DestroySets = {
        4: tuple(tuple(cast(list[int], p)) for p in cast(list[object], document["DESTROY4_SETS"])),
        5: tuple(tuple(cast(list[int], p)) for p in cast(list[object], document["DESTROY5_SETS"])),
    }
    identity_ok = (
        document.get("TASK_ID") == REUSE_TASK_ID
        and document.get("START_COUNT") == START_COUNT
        and document.get("START_SHA256") == START_SHA256
        and sets == expected
    )
    if not identity_ok:
        raise StopConditionError(
            "REUSE_ARTIFACT_MISMATCH", "reuse artifact identity or destroy sets differ"
        )
    priors: dict[SetKey, PriorSet] = {}
    for raw in cast(list[dict[str, object]], document["PER_DESTROY_SET"]):
        size = cast(int, raw["DESTROY_SIZE"])
        positions = tuple(cast(list[int], raw["POSITIONS"]))
        removed = destroy_positions(START_PORTFOLIO, positions).removed
        top = tuple(
            PriorRanked(
                _ticket(entry["TICKET"]),
                cast(int, entry["RANK"]),
                cast(int, entry["RESIDUAL_MARGINAL_OUTCOMES"]),
            )
            for entry in cast(list[dict[str, object]], raw["GLOBAL_TOP"])
        )
        pool = frozenset(
            _ticket(member["TICKET"]) for member in cast(list[dict[str, object]], raw["POOL"])
        )
        if (
            [_ticket(t) for t in cast(list[object], raw["REMOVED_TICKETS"])] != list(removed)
            or len(top) != GLOBAL_TOP_MARGINAL
            or [entry.rank for entry in top] != list(range(1, GLOBAL_TOP_MARGINAL + 1))
        ):
            raise StopConditionError(
                "REUSE_ARTIFACT_MISMATCH", f"per-set record differs for {size}:{positions}"
            )
        priors[(size, positions)] = PriorSet(
            size=size,
            positions=positions,
            removed=removed,
            top=top,
            pool=pool,
            best_count=cast(int, raw["BEST_COUNT"]),
            best_sha256=cast(str, raw["BEST_PORTFOLIO_SHA256"]),
        )
    if set(priors) != {(size, p) for size, group in sets.items() for p in group}:
        raise StopConditionError("REUSE_ARTIFACT_MISMATCH", "per-set records do not match the sets")
    return sets, priors


def depth0_top_matches_prior(
    universe: ColexUniverse, scores: GlobalScores, prior: PriorSet
) -> bool:
    """The depth-0 enumeration (``S`` empty) re-derives the one-shot top 48 exactly."""

    recomputed = global_top(universe, scores, GLOBAL_TOP_MARGINAL)
    return [(e.ticket, e.rank, SUBSET_SIZE * e.marginal) for e in recomputed] == [
        (e.ticket, e.rank, e.marginal_outcomes) for e in prior.top
    ]


# ---------------------------------------------------------------------------------------------
# one destroy set end to end, with inline checks
# ---------------------------------------------------------------------------------------------


class CachedRecounter:
    """Canonical recounts keyed by the normalized portfolio, so no portfolio is counted twice."""

    def __init__(self, recounter: CanonicalRecounter, geometry: Geometry | None = None) -> None:
        self.recounter = recounter
        self.geometry = geometry or recounter.geometry
        self.cache: dict[Portfolio, int] = {}

    def count(self, portfolio: Sequence[Ticket]) -> int:
        key = normalize_portfolio(portfolio, geometry=self.geometry)
        if key not in self.cache:
            self.cache[key] = self.recounter.count(key)
        return self.cache[key]


@dataclass(frozen=True, slots=True)
class DestroySetBeam:
    """Everything recorded for one destroy set."""

    size: int
    destroyed: DestroyedPortfolio
    remaining_count: int
    run: BeamRun
    depth0_top_matches_prior: bool
    original_ranks: dict[Ticket, int]
    recounts: dict[Portfolio, int]
    best_portfolio: Portfolio
    seconds: dict[str, float] = field(default_factory=dict[str, float])

    def portfolio_of(self, state: BeamState) -> Portfolio:
        return normalize_portfolio((*self.destroyed.remaining, *state.tickets))

    def recount_of(self, state: BeamState) -> int:
        return self.recounts[self.portfolio_of(state)]

    @property
    def best_count(self) -> int:
        return SUBSET_SIZE * self.run.best.covered


def _stop_on(tally: ParityTally, family: str, ok: bool, detail: str) -> None:
    tally.check(family, ok)
    if not ok:
        raise StopConditionError("PARITY_MISMATCH", f"{family}: {detail}")


def beam_destroy_set(
    universe: ColexUniverse,
    size: int,
    positions: Sequence[int],
    *,
    recounter: CachedRecounter,
    tally: ParityTally,
    prior: PriorSet | None,
    direct_check: bool = True,
    beam_width: int = BEAM_WIDTH,
    expansion_width: int = EXPANSION_WIDTH,
    depth: int | None = None,
) -> DestroySetBeam:
    """Freeze START minus ``positions``, run the conditional beam and recount it canonically.

    Inline checks, every one fail-closed: the depth-0 top 48 equals the reuse artifact; every
    expansion's next-ticket marginals equal the brute-force residual count against ``R + S``; every
    retained state's chained coverage equals its canonical recount, so every retained child also
    checks its conditional marginal as a canonical difference to its (retained) parent; every final
    best-count tie is recounted canonically.
    """

    started = time.perf_counter()
    seconds: dict[str, float] = {}
    destroyed = destroy_positions(START_PORTFOLIO, positions)
    remaining = destroyed.remaining
    remaining_count = recounter.count(remaining)
    if remaining_count % SUBSET_SIZE:
        raise AssertionError("the canonical count of R is not a multiple of 7")
    depth0: dict[str, object] = {}
    direct_seconds = [0.0]

    def hook(expansion: Expansion, scores: GlobalScores, frozen: Portfolio) -> None:
        if not expansion.conditional:
            depth0["MARGINALS"] = scores.marginals
            if prior is not None:
                depth0["MATCH"] = depth0_top_matches_prior(universe, scores, prior)
                _stop_on(
                    tally,
                    "REUSE_DEPTH0_TOP48_EQUALS_PRIOR_ARTIFACT",
                    bool(depth0["MATCH"]),
                    f"{size}:{tuple(positions)}",
                )
        if direct_check:
            phase = time.perf_counter()
            direct = direct_marginals(frozen, [child.ticket for child in expansion.children])
            direct_seconds[0] += time.perf_counter() - phase
            family = (
                "PILOT_CONDITIONAL_MARGINAL_EQUALS_DIRECT"
                if expansion.conditional
                else "PILOT_ROOT_MARGINAL_EQUALS_DIRECT"
            )
            for child, value in zip(expansion.children, direct, strict=True):
                _stop_on(tally, family, child.marginal == value, f"{child.ticket} given {frozen}")

    run = run_beam(
        universe,
        remaining,
        depth_for(size) if depth is None else depth,
        base_covered=remaining_count // SUBSET_SIZE,
        beam_width=beam_width,
        expansion_width=expansion_width,
        inspect=hook,
    )
    seconds["BEAM"] = time.perf_counter() - started
    seconds["DIRECT_CHECKS"] = direct_seconds[0]
    tally.check(
        "PILOT_EVERY_EXPANSION_SCORED_THE_COMPLETE_UNIVERSE",
        all(expansion.tickets_scored == universe.tickets.shape[0] for expansion in run.expansions),
    )

    phase = time.perf_counter()
    recounts: dict[Portfolio, int] = {}

    def recount(state: BeamState) -> int:
        portfolio = normalize_portfolio((*remaining, *state.tickets))
        recounts[portfolio] = recounter.count(portfolio)
        return recounts[portfolio]

    previous: dict[Portfolio, int] = {(): remaining_count}
    for level in run.levels:
        current: dict[Portfolio, int] = {}
        for state in level.retained:
            value = recount(state)
            current[state.tickets] = value
            _stop_on(
                tally,
                "PILOT_RETAINED_STATE_COVERAGE_EQUALS_CANONICAL",
                value == SUBSET_SIZE * state.covered,
                f"{state.tickets}",
            )
            parent = cast(Portfolio, state.parent)
            family = (
                "PILOT_CONDITIONAL_MARGINAL_EQUALS_CANONICAL_DIFFERENCE"
                if parent
                else "PILOT_ROOT_MARGINAL_EQUALS_CANONICAL_DIFFERENCE"
            )
            _stop_on(
                tally,
                family,
                value - previous[parent] == SUBSET_SIZE * state.added_marginal,
                f"{state.added} given {parent}",
            )
        previous = current
    for state in run.final_ties():
        _stop_on(
            tally,
            "PILOT_FINAL_BEST_COUNT_TIE_EQUALS_CANONICAL",
            recount(state) == SUBSET_SIZE * state.covered,
            f"{state.tickets}",
        )
    seconds["RECOUNT"] = time.perf_counter() - phase

    phase = time.perf_counter()
    marginals = cast(CountArray, depth0["MARGINALS"])
    ranked_tickets = sorted({t for s in run.final.retained for t in s.tickets})
    original_ranks = {
        ticket: exact_global_rank(marginals, universe.tickets, universe.index_of(ticket))
        for ticket in ranked_tickets
    }
    seconds["ORIGINAL_RANKS"] = time.perf_counter() - phase
    seconds["TOTAL"] = time.perf_counter() - started
    return DestroySetBeam(
        size=size,
        destroyed=destroyed,
        remaining_count=remaining_count,
        run=run,
        depth0_top_matches_prior=bool(depth0.get("MATCH", False)),
        original_ranks=original_ranks,
        recounts=recounts,
        best_portfolio=normalize_portfolio((*remaining, *run.best.tickets)),
        seconds=seconds,
    )


# ---------------------------------------------------------------------------------------------
# pre-pilot parity: toy lotteries against a reference beam written from the Packet
# ---------------------------------------------------------------------------------------------

TOY_SEED: Final = 20261003
# below 14 numbers one added ticket already wins every 7-subset; 14..16 numbers with 1..3 frozen
# tickets span empty, partial and saturated residuals, so cuts, ties and merged children all occur
TOY_POOL_SIZES: Final = (14, 15, 16)
TOY_FROZEN_SIZES: Final = (1, 2, 3)
TOY_DEPTH: Final = 3
TOY_BEAM_WIDTH: Final = 3
TOY_EXPANSION_WIDTH: Final = 4

type ReferenceLevel = tuple[list[tuple[Portfolio, int]], list[tuple[Portfolio, int]], int]


def reference_beam(
    pool_size: int,
    remaining: Sequence[Ticket],
    depth: int,
    beam_width: int,
    expansion_width: int,
) -> list[ReferenceLevel]:
    """The Packet's beam spelled out with brute-force marginals; shares no code with ``run_beam``.

    Per level: every unique child ``(tickets, covered)`` in retention order, the retained prefix
    and the number of children generated before deduplication.
    """

    total = comb(pool_size, SUBSET_SIZE)
    _, residual = brute_force_marginals(pool_size, remaining)
    beam: list[tuple[Portfolio, int]] = [((), total - residual)]
    levels: list[ReferenceLevel] = []
    for _ in range(depth):
        children: dict[Portfolio, int] = {}
        generated = 0
        for tickets, covered in beam:
            frozen = [*remaining, *tickets]
            marginals, residual = brute_force_marginals(pool_size, frozen)
            if total - residual != covered:
                raise AssertionError("reference coverage chain broke")
            frozen_set = set(frozen)
            legal = sorted(
                (-value, ticket) for ticket, value in marginals.items() if ticket not in frozen_set
            )
            for negative, ticket in legal[:expansion_width]:
                generated += 1
                children.setdefault(tuple(sorted((*tickets, ticket))), covered - negative)
        ordered = sorted(children.items(), key=lambda item: (-item[1], item[0]))
        beam = ordered[:beam_width]
        levels.append((ordered, beam, generated))
    return levels


def toy_remaining(pool_size: int, frozen_size: int, seed: int = TOY_SEED) -> Portfolio:
    """The frozen tickets of one toy case, drawn from its own seeded generator."""

    rng = random.Random(seed + 100 * pool_size + frozen_size)
    every = list(itertools.combinations(range(1, pool_size + 1), TICKET_SIZE))
    geometry = Geometry(pool_size, TICKET_SIZE, OUTRIGHT)
    return normalize_portfolio(rng.sample(every, frozen_size), geometry=geometry)


def run_toy_parity(seed: int = TOY_SEED) -> ParityTally:
    """Module beam against the reference beam and the canonical evaluator on toy lotteries."""

    tally = ParityTally()
    distinct_cuts = 0
    deduplicated = 0
    cutoff_ties = 0
    for pool_size in TOY_POOL_SIZES:
        universe = build_universe(pool_size)
        geometry = Geometry(pool_size, TICKET_SIZE, OUTRIGHT)
        recounter = CachedRecounter(CanonicalRecounter(geometry), geometry)
        for frozen_size in TOY_FROZEN_SIZES:
            remaining = toy_remaining(pool_size, frozen_size, seed)
            base = recounter.count(remaining)
            run = run_beam(
                universe,
                remaining,
                TOY_DEPTH,
                base_covered=base // SUBSET_SIZE,
                beam_width=TOY_BEAM_WIDTH,
                expansion_width=TOY_EXPANSION_WIDTH,
            )
            reference = reference_beam(
                pool_size, remaining, TOY_DEPTH, TOY_BEAM_WIDTH, TOY_EXPANSION_WIDTH
            )
            for level, (ordered, kept, generated) in zip(run.levels, reference, strict=True):
                tally.check(
                    "TOY_BEAM_CANDIDATES_EQUAL_REFERENCE",
                    [(s.tickets, s.covered) for s in level.candidates] == ordered,
                )
                tally.check(
                    "TOY_BEAM_RETAINED_EQUAL_REFERENCE",
                    [(s.tickets, s.covered) for s in level.retained] == kept,
                )
                tally.check(
                    "TOY_BEAM_GENERATED_AND_DEDUPLICATED_EQUAL_REFERENCE",
                    level.generated == generated
                    and level.generated - level.duplicates == level.unique,
                )
                deduplicated += level.duplicates
            for state in run.final.candidates:
                tally.check(
                    "TOY_FINAL_STATE_COVERAGE_EQUALS_CANONICAL",
                    recounter.count((*remaining, *state.tickets)) == SUBSET_SIZE * state.covered,
                )
            distinct_cuts += sum(
                level.unique > len(level.retained)
                and len({state.covered for state in level.candidates}) > 1
                for level in run.levels
            )
            cutoff_ties += sum(e.cutoff.tied > 1 for e in run.expansions)
    # the toy families are not vacuous: they separate states, merge duplicates and cut on ties
    tally.check("TOY_SOME_RETENTION_CUT_SEPARATES_DISTINCT_COVERAGES", distinct_cuts > 0)
    tally.check("TOY_SOME_CHILD_WAS_DEDUPLICATED", deduplicated > 0)
    tally.check("TOY_SOME_EXPANSION_CUT_INSIDE_A_TIE", cutoff_ties > 0)
    return tally


# ---------------------------------------------------------------------------------------------
# pre-pilot parity: the real 49/20 space on the destroy sets that follow the pilot sample
# ---------------------------------------------------------------------------------------------

REAL_PARITY_DEPTH: Final = 2
REAL_PARITY_BEAM_WIDTH: Final = 2
REAL_HASHED_PROBES: Final = 6
MIN_REAL_CONDITIONAL_MARGINAL_CHECKS: Final = 100


def hashed_tickets(universe: ColexUniverse, tag: str, count: int) -> list[Ticket]:
    """Deterministic probe tickets: colex rank ``sha256(task:probe:tag:i) mod C(n,6)``."""

    total = int(universe.tickets.shape[0])
    chosen: list[Ticket] = []
    for i in range(count):
        digest = hashlib.sha256(f"{TASK_ID}:probe:{tag}:{i}".encode()).digest()
        chosen.append(universe.ticket_at(int.from_bytes(digest[:8], "big") % total))
    return chosen


def check_next_independently(
    universe: ColexUniverse,
    marginals: CountArray,
    frozen: Sequence[Ticket],
    expansion: Expansion,
    tally: ParityTally,
) -> None:
    """Re-derive the next tickets, their tie-break and the cutoff counts by a sort-based path."""

    legal = np.ones(marginals.size, dtype=np.bool_)
    for ticket in frozen:
        legal[universe.index_of(ticket)] = False
    count = len(expansion.children)
    largest = [int(v) for v in np.sort(marginals[legal])[::-1][:count]]
    tally.check(
        "REAL_NEXT_TICKET_VALUES_ARE_THE_LARGEST_LEGAL_MARGINALS",
        largest == [child.marginal for child in expansion.children],
    )
    threshold = expansion.children[-1].marginal
    stronger = sum(1 for child in expansion.children if child.marginal > threshold)
    tied = np.flatnonzero((marginals == threshold) & legal)
    order = np.lexsort(universe.tickets[tied].T[::-1])
    expected = [universe.ticket_at(int(i)) for i in tied[order][: count - stronger]]
    tally.check(
        "REAL_NEXT_TICKET_TIES_ARE_THE_LEXICOGRAPHICALLY_LOWEST",
        [c.ticket for c in expansion.children if c.marginal == threshold] == expected,
    )
    tally.check(
        "REAL_CUTOFF_COUNTS_EQUAL_DIRECT_COUNTS",
        expansion.cutoff.above == int(np.count_nonzero((marginals > threshold) & legal))
        and expansion.cutoff.tied == int(tied.size),
    )
    tally.check(
        "REAL_FROZEN_TICKETS_HAVE_ZERO_MARGINAL",
        all(int(marginals[universe.index_of(ticket)]) == 0 for ticket in frozen),
    )


def _ticket_tag(tickets: Sequence[Ticket]) -> str:
    return "|".join(",".join(map(str, ticket)) for ticket in tickets)


def run_real_parity(
    universe: ColexUniverse, recounter: CachedRecounter
) -> tuple[ParityTally, list[dict[str, object]]]:
    """Real conditional marginals against the canonical evaluator and a brute-force residual count.

    The destroy sets are the ones that follow the pilot sample in the reuse ranking, so no pilot set
    is scored before the gate passes. A depth-2, width-2 beam runs on each; every conditional
    expansion checks its 8 next tickets, the removed tickets and hashed probes three ways.
    """

    tally = ParityTally()
    global_pool.check_real_enumeration(universe, tally)
    records: list[dict[str, object]] = []
    for size, sets in parity_destroy_sets().items():
        for positions in sets:
            destroyed = destroy_positions(START_PORTFOLIO, positions)
            remaining = destroyed.remaining
            base = recounter.count(remaining)
            tag = f"{size}:{','.join(map(str, positions))}"
            probes_checked: list[dict[str, object]] = []

            def hook(
                expansion: Expansion,
                scores: GlobalScores,
                frozen: Portfolio,
                destroyed: DestroyedPortfolio = destroyed,
                tag: str = tag,
                probes_checked: list[dict[str, object]] = probes_checked,
            ) -> None:
                check_next_independently(universe, scores.marginals, frozen, expansion, tally)
                children = [child.ticket for child in expansion.children]
                if not expansion.conditional:
                    direct = direct_marginals(frozen, children)
                    for child, value in zip(expansion.children, direct, strict=True):
                        tally.check("REAL_ROOT_MARGINAL_EQUALS_DIRECT", child.marginal == value)
                    return
                parent_count = recounter.count(frozen)
                tally.check(
                    "REAL_PARENT_CHAINED_COVERAGE_EQUALS_CANONICAL",
                    parent_count == SUBSET_SIZE * expansion.parent.covered,
                )
                frozen_set = set(frozen)
                hashed = hashed_tickets(
                    universe, f"{tag}:{_ticket_tag(expansion.parent.tickets)}", REAL_HASHED_PROBES
                )
                probes = [
                    ticket
                    for ticket in dict.fromkeys((*children, *destroyed.removed, *hashed))
                    if ticket not in frozen_set
                ]
                direct = direct_marginals(frozen, probes)
                for ticket, value in zip(probes, direct, strict=True):
                    marginal = int(scores.marginals[universe.index_of(ticket)])
                    canonical = recounter.count((*frozen, ticket)) - parent_count
                    tally.check(
                        "REAL_CONDITIONAL_MARGINAL_EQUALS_CANONICAL_AND_DIRECT",
                        SUBSET_SIZE * marginal == canonical and marginal == value,
                    )
                    probes_checked.append(
                        {
                            "GIVEN": [list(t) for t in expansion.parent.tickets],
                            "TICKET": list(ticket),
                            "SCORER_OUTCOMES": SUBSET_SIZE * marginal,
                            "CANONICAL_DIFFERENCE": canonical,
                            "DIRECT_OUTCOMES": SUBSET_SIZE * value,
                        }
                    )

            run = run_beam(
                universe,
                remaining,
                REAL_PARITY_DEPTH,
                base_covered=base // SUBSET_SIZE,
                beam_width=REAL_PARITY_BEAM_WIDTH,
                expansion_width=EXPANSION_WIDTH,
                inspect=hook,
            )
            for state in run.final.candidates:
                tally.check(
                    "REAL_BEAM_CHILD_COVERAGE_EQUALS_CANONICAL",
                    recounter.count((*remaining, *state.tickets)) == SUBSET_SIZE * state.covered,
                )
            records.append(
                {
                    "DESTROY_SIZE": size,
                    "POSITIONS": list(positions),
                    "DEPTH": REAL_PARITY_DEPTH,
                    "BEAM_WIDTH": REAL_PARITY_BEAM_WIDTH,
                    "EXPANSION_WIDTH": EXPANSION_WIDTH,
                    "CONDITIONAL_ENUMERATIONS": run.enumerations,
                    "FINAL_CHILDREN_RECOUNTED": run.final.unique,
                    "CONDITIONAL_PROBES": probes_checked,
                }
            )
    return tally, records


def run_parity(universe: ColexUniverse, recounter: CachedRecounter) -> dict[str, object]:
    """All pre-pilot parity; ``PARITY_MISMATCHES`` must be zero before any pilot set is scored."""

    toy = run_toy_parity()
    real, records = run_real_parity(universe, recounter)
    families = cast(dict[str, dict[str, int]], real.detail())
    conditional = families["REAL_CONDITIONAL_MARGINAL_EQUALS_CANONICAL_AND_DIRECT"]
    return {
        "PARITY_SAMPLE_COUNT": toy.comparisons + real.comparisons,
        "PARITY_MISMATCHES": toy.mismatches + real.mismatches,
        "REAL_CONDITIONAL_MARGINAL_CHECKS": conditional["COMPARISONS"],
        "REAL_CONDITIONAL_MARGINAL_MISMATCHES": conditional["MISMATCHES"],
        "MIN_REAL_CONDITIONAL_MARGINAL_CHECKS": MIN_REAL_CONDITIONAL_MARGINAL_CHECKS,
        "COVERAGE_MEETS_PACKET_MINIMUM": (
            conditional["COMPARISONS"] >= MIN_REAL_CONDITIONAL_MARGINAL_CHECKS
        ),
        "TOY": {
            "COMPARISONS": toy.comparisons,
            "MISMATCHES": toy.mismatches,
            "POOL_SIZES": list(TOY_POOL_SIZES),
            "FROZEN_SIZES": list(TOY_FROZEN_SIZES),
            "CASES": len(TOY_POOL_SIZES) * len(TOY_FROZEN_SIZES),
            "DEPTH": TOY_DEPTH,
            "BEAM_WIDTH": TOY_BEAM_WIDTH,
            "EXPANSION_WIDTH": TOY_EXPANSION_WIDTH,
            "FAMILIES": toy.detail(),
        },
        "REAL": {
            "COMPARISONS": real.comparisons,
            "MISMATCHES": real.mismatches,
            "FAMILIES": real.detail(),
            "SETS": records,
        },
    }


# ---------------------------------------------------------------------------------------------
# result document
# ---------------------------------------------------------------------------------------------

MODULE_RELATIVE_PATH: Final = "src/lottolab/research/b649_k20_conditional_global_repair_beam_r1.py"
RESULT_RELATIVE_PATH: Final = (
    "docs/research/matrix-native-results/b649-k20-conditional-global-repair-beam-r1-result.json"
)
RESULT_IMPROVED: Final = "IMPROVED"
RESULT_NO_IMPROVEMENT: Final = "NO_IMPROVEMENT_IN_CONDITIONAL_GLOBAL_REPAIR_BEAM_PILOT"
SCIENTIFIC_SCOPE: Final = "3_DESTROY4_PLUS_3_DESTROY5_CONDITIONAL_GLOBAL_BEAM_WIDTH8_CHILDREN8"
FINDING_ESTABLISHED: Final = "ESTABLISHED"
FINDING_NOT_ESTABLISHED: Final = "NOT_ESTABLISHED"
NOT_CLAIMED: Final = (
    "complete N4 optimum",
    "complete N5 optimum",
    "optimality of any beam state (BEAM_WIDTH = 8 and 8 children per state are heuristic bounds)",
    "global K20 optimum",
    "superiority or equality relative to protected Lane 3",
)
LISTED_TIES_MAX: Final = 200


def _ticket_list(tickets: Sequence[Ticket]) -> list[list[int]]:
    return [list(ticket) for ticket in tickets]


def _yes_no(value: bool) -> str:
    return "YES" if value else "NO"


def classify_replacements(
    tickets: Sequence[Ticket], prior: PriorSet, original_ranks: Mapping[Ticket, int]
) -> list[dict[str, object]]:
    """Where each replacement ticket stood in the one-shot pilot for the same destroy set."""

    removed = set(prior.removed)
    return [
        {
            "TICKET": list(ticket),
            "ORIGINAL_GLOBAL_RANK": original_ranks.get(ticket),
            "IN_ORIGINAL_GLOBAL_TOP48": ticket in prior.top_tickets,
            "IN_ORIGINAL_REPAIR_POOL": ticket in prior.pool,
            "IS_REMOVED_INCUMBENT_TICKET": ticket in removed,
        }
        for ticket in tickets
    ]


def requires_ticket_outside_top48(tickets: Sequence[Ticket], prior: PriorSet) -> bool:
    """True when at least one replacement ticket is not in the one-shot global top 48."""

    return any(ticket not in prior.top_tickets for ticket in tickets)


def _state_record(beam: DestroySetBeam, state: BeamState) -> dict[str, object]:
    portfolio = beam.portfolio_of(state)
    return {
        "REPLACEMENT_TICKETS": _ticket_list(state.tickets),
        "OUTCOMES": SUBSET_SIZE * state.covered,
        "DELTA_VS_START": SUBSET_SIZE * state.covered - START_COUNT,
        "PORTFOLIO_SHA256": portfolio_sha256(portfolio),
        "CANONICAL_RECOUNT": beam.recounts.get(portfolio),
        "PARENT": None if state.parent is None else _ticket_list(state.parent),
        "ADDED_TICKET": None if state.added is None else list(state.added),
        "ADDED_CONDITIONAL_MARGINAL_OUTCOMES": SUBSET_SIZE * state.added_marginal,
        "ADDED_POSITION": state.added_position,
    }


def _expansion_record(expansion: Expansion, prior: PriorSet) -> dict[str, object]:
    removed = set(prior.removed)
    return {
        "LEVEL": expansion.level,
        "PARENT_TICKETS": _ticket_list(expansion.parent.tickets),
        "PARENT_OUTCOMES": SUBSET_SIZE * expansion.parent.covered,
        "RESIDUAL_SUBSETS": expansion.residual_subsets,
        "TICKETS_SCORED": expansion.tickets_scored,
        "IDENTITIES_PASS": expansion.identities["PASS"],
        "CUTOFF_MARGINAL_OUTCOMES": SUBSET_SIZE * expansion.cutoff.threshold,
        "LEGAL_TICKETS_ABOVE_CUTOFF": expansion.cutoff.above,
        "LEGAL_TICKETS_TIED_AT_CUTOFF": expansion.cutoff.tied,
        "SECONDS": round(expansion.seconds, 3),
        "NEXT_TICKETS": [
            {
                "POSITION": child.position,
                "TICKET": list(child.ticket),
                "CONDITIONAL_MARGINAL_OUTCOMES": SUBSET_SIZE * child.marginal,
                "IN_ORIGINAL_GLOBAL_TOP48": child.ticket in prior.top_tickets,
                "IN_ORIGINAL_REPAIR_POOL": child.ticket in prior.pool,
                "IS_REMOVED_INCUMBENT_TICKET": child.ticket in removed,
            }
            for child in expansion.children
        ],
    }


def ties_recounted(beam: DestroySetBeam) -> bool:
    """Every final best-count tie of the set was canonically recounted and matches."""

    return all(
        beam.recounts.get(beam.portfolio_of(state)) == SUBSET_SIZE * state.covered
        for state in beam.run.final_ties()
    )


def _set_record(beam: DestroySetBeam, prior: PriorSet) -> dict[str, object]:
    run, best = beam.run, beam.run.best
    ties = run.final_ties()
    start_state = canonical_state(beam.destroyed.removed)
    return {
        "DESTROY_SIZE": beam.size,
        "POSITIONS": list(beam.destroyed.positions),
        "REMOVED_TICKETS": _ticket_list(beam.destroyed.removed),
        "R_SIZE": len(beam.destroyed.remaining),
        "OUTCOMES_WON_BY_FROZEN_R": beam.remaining_count,
        "DEPTH": run.depth,
        "BEAM_WIDTH": run.beam_width,
        "EXPANSION_WIDTH": run.expansion_width,
        "CONDITIONAL_ENUMERATIONS": run.enumerations,
        "CONDITIONAL_ENUMERATIONS_WITH_NONEMPTY_S": sum(e.conditional for e in run.expansions),
        "GLOBAL_TICKETS_SCORED": run.tickets_scored,
        "BEAM_STATES_GENERATED": run.generated,
        "BEAM_STATES_UNIQUE": run.unique,
        "BEAM_STATES_DUPLICATE": run.duplicates,
        "BEAM_STATES_RETAINED": run.retained,
        "DEPTH0_TOP48_EQUALS_PRIOR_ARTIFACT": beam.depth0_top_matches_prior,
        "BEST_COUNT": beam.best_count,
        "BEST_DELTA": beam.best_count - START_COUNT,
        "BEST_REPLACEMENT_TICKETS": _ticket_list(best.tickets),
        "BEST_NEW_TICKETS": _ticket_list(sorted(set(beam.best_portfolio) - set(START_PORTFOLIO))),
        "BEST_PORTFOLIO_SHA256": portfolio_sha256(beam.best_portfolio),
        "BEST_CANONICAL_RECOUNT": beam.recount_of(best),
        "BEST_REPLACEMENTS_VS_ONE_SHOT": classify_replacements(
            best.tickets, prior, beam.original_ranks
        ),
        "BEST_REQUIRES_TICKET_OUTSIDE_ORIGINAL_GLOBAL_TOP48": _yes_no(
            requires_ticket_outside_top48(best.tickets, prior)
        ),
        "FINAL_BEST_COUNT_TIES": len(ties),
        "FINAL_BEST_COUNT_TIES_CANONICALLY_RECOUNTED": ties_recounted(beam),
        "FINAL_BEST_COUNT_TIES_LISTED": [_state_record(beam, s) for s in ties[:LISTED_TIES_MAX]],
        "FINAL_CANDIDATES_INCLUDE_START_REPLACEMENT_SET": any(
            state.tickets == start_state for state in run.final.candidates
        ),
        "PRIOR_ONE_SHOT_POOL_BEST_COUNT": prior.best_count,
        "PRIOR_ONE_SHOT_POOL_BEST_SHA256": prior.best_sha256,
        "BEAM_BEST_MINUS_PRIOR_ONE_SHOT_BEST": beam.best_count - prior.best_count,
        "LEVELS": [
            {
                "LEVEL": level.level,
                "GENERATED": level.generated,
                "UNIQUE": level.unique,
                "DUPLICATES": level.duplicates,
                "RETAINED_COUNT": len(level.retained),
                "BEST_OUTCOMES": SUBSET_SIZE * level.retained[0].covered,
                "CUTOFF_OUTCOMES": SUBSET_SIZE * level.cutoff_covered,
                "CANDIDATES_TIED_AT_CUTOFF": level.candidates_tied_at_cutoff,
                "RETAINED_TIED_AT_CUTOFF": level.retained_tied_at_cutoff,
                "RETAINED": [_state_record(beam, state) for state in level.retained],
            }
            for level in run.levels
        ],
        "EXPANSIONS": [_expansion_record(expansion, prior) for expansion in run.expansions],
        "SECONDS": {name: round(value, 3) for name, value in beam.seconds.items()},
    }


@dataclass(frozen=True, slots=True)
class GlobalBest:
    """The pilot winner: highest count, then lowest normalized portfolio SHA-256."""

    count: int
    sha256: str
    beam: DestroySetBeam
    state: BeamState
    ties: tuple[tuple[str, DestroySetBeam, BeamState], ...]


def select_global_best(beams: Sequence[DestroySetBeam]) -> GlobalBest:
    """Best over every final-depth state of every destroy set; ties by the lowest SHA-256."""

    entries = sorted(
        (
            (-SUBSET_SIZE * state.covered, portfolio_sha256(beam.portfolio_of(state)), place, rank)
            for place, beam in enumerate(beams)
            for rank, state in enumerate(beam.run.final.candidates)
        ),
    )
    if not entries:
        raise ValueError("no final beam states to choose from")
    count = -entries[0][0]
    ties = tuple(
        (sha, beams[place], beams[place].run.final.candidates[rank])
        for negative, sha, place, rank in entries
        if -negative == count
    )
    sha, winner, state = ties[0]
    return GlobalBest(count=count, sha256=sha, beam=winner, state=state, ties=ties)


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def build_result_document(
    *,
    sets: Mapping[int, Sequence[Sequence[int]]],
    priors: Mapping[SetKey, PriorSet],
    beams: Sequence[DestroySetBeam],
    start_record: Mapping[str, object],
    pins: Sequence[Mapping[str, object]],
    reuse_record: Mapping[str, object],
    parity: Mapping[str, object],
    pilot_tally: ParityTally,
    wall_seconds: float,
    peak_memory: int,
    run_identity: Mapping[str, str],
    module_sha256: str,
    runtime_modules: Mapping[str, str],
    phase_seconds: Mapping[str, float],
    thread_env: Mapping[str, str | None],
) -> dict[str, object]:
    """Assemble the pilot result from one beam per pre-registered destroy set."""

    expected = [(size, tuple(p)) for size in DESTROY_SIZES for p in sets[size]]
    if [(beam.size, beam.destroyed.positions) for beam in beams] != expected:
        raise ValueError("every pilot destroy set needs exactly one beam, in sample order")
    if any(len(beam.best_portfolio) != PORTFOLIO_SIZE for beam in beams):
        raise ValueError("every pilot beam must end in a 20-ticket portfolio")
    best = select_global_best(beams)
    prior = priors[(best.beam.size, best.beam.destroyed.positions)]
    best_portfolio = best.beam.portfolio_of(best.state)
    best_recount = best.beam.recount_of(best.state)
    global_ties_recounted = all(
        beam.recounts.get(beam.portfolio_of(state)) == best.count for _, beam, state in best.ties
    )
    recount_pass = (
        best_recount == best.count
        and global_ties_recounted
        and all(ties_recounted(beam) for beam in beams)
    )
    improved = best.count > START_COUNT
    result = RESULT_IMPROVED if improved and recount_pass else RESULT_NO_IMPROVEMENT
    outside = requires_ticket_outside_top48(best.state.tickets, prior)
    finding = (
        FINDING_ESTABLISHED if outside and improved and recount_pass else FINDING_NOT_ESTABLISHED
    )
    inline_mismatches = pilot_tally.mismatches
    records = [_set_record(beam, priors[(beam.size, beam.destroyed.positions)]) for beam in beams]
    enumeration_seconds = [e.seconds for beam in beams for e in beam.run.expansions]
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "COMPLETE",
        "SCIENTIFIC_RESULT": result,
        "NEW_STABLE_NON_LANE3_GAIN": _yes_no(result == RESULT_IMPROVED),
        "SCIENTIFIC_SCOPE": SCIENTIFIC_SCOPE,
        "SEARCH_CLASS": SEARCH_CLASS,
        "OPTIMALITY_STATUS": OPTIMALITY_STATUS,
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
        "REUSE": dict(reuse_record),
        "DESTROY4_SETS": [list(positions) for positions in sets[4]],
        "DESTROY5_SETS": [list(positions) for positions in sets[5]],
        "BEAM_DEFINITION": {
            "BEAM_WIDTH": BEAM_WIDTH,
            "CHILDREN_PER_STATE": EXPANSION_WIDTH,
            "DEPTH": {"DESTROY4": depth_for(4), "DESTROY5": depth_for(5)},
            "EXPANSION": (
                "for every retained partial state S, score all 13,983,816 legal tickets exactly "
                "against R + S (the reused global residual scorer) and take the 8 legal tickets "
                "of largest conditional marginal, ties to the lexicographically lowest ticket; "
                "tickets already in R + S are not legal"
            ),
            "DEDUPLICATION": "children are sets; the first expansion that reaches a set keeps it",
            "RETENTION": (
                "keep 8 states by exact union coverage of R + S descending, then the lowest "
                "canonical state identity (replacement tickets sorted within and across tickets)"
            ),
            "PREFILTER": "NONE",
            "RANDOM_TICKET_SAMPLING": "NONE",
        },
        "CONDITIONAL_ENUMERATIONS": sum(beam.run.enumerations for beam in beams),
        "CONDITIONAL_ENUMERATIONS_WITH_NONEMPTY_S": sum(
            e.conditional for beam in beams for e in beam.run.expansions
        ),
        "CONDITIONAL_ENUMERATIONS_DEFINITION": (
            "complete ticket-universe scorings in the pilot (one per retained state per depth, the "
            "empty depth-0 state included); parity-gate enumerations are counted in PARITY"
        ),
        "GLOBAL_TICKETS_SCORED": sum(beam.run.tickets_scored for beam in beams),
        "GLOBAL_TICKET_UNIVERSE_SIZE": TOTAL_TICKETS,
        "CONDITIONAL_ENUMERATION_WALL_SECONDS_MIN": round(min(enumeration_seconds), 3),
        "CONDITIONAL_ENUMERATION_WALL_SECONDS_MAX": round(max(enumeration_seconds), 3),
        "CONDITIONAL_ENUMERATION_WALL_SECONDS_MEAN": round(_mean(enumeration_seconds), 3),
        "BEAM_STATES_GENERATED": sum(beam.run.generated for beam in beams),
        "BEAM_STATES_UNIQUE": sum(beam.run.unique for beam in beams),
        "BEAM_STATES_DUPLICATE": sum(beam.run.duplicates for beam in beams),
        "BEAM_STATES_RETAINED": sum(beam.run.retained for beam in beams),
        "BEAM_STATES_DEFINITION": (
            "GENERATED: children produced before deduplication; UNIQUE: distinct child sets per "
            "depth; RETAINED: states kept by the beam, summed over depths 1..D (the empty root "
            "state excluded)"
        ),
        "PARITY_SAMPLE_COUNT": parity["PARITY_SAMPLE_COUNT"],
        "PARITY_MISMATCHES": cast(int, parity["PARITY_MISMATCHES"]) + inline_mismatches,
        "PRE_PILOT_PARITY_MISMATCHES": parity["PARITY_MISMATCHES"],
        "REAL_CONDITIONAL_MARGINAL_CHECKS": parity["REAL_CONDITIONAL_MARGINAL_CHECKS"],
        "PARITY": dict(parity),
        "PILOT_INLINE_CHECKS": {
            "COMPARISONS": pilot_tally.comparisons,
            "MISMATCHES": inline_mismatches,
            "FAMILIES": pilot_tally.detail(),
        },
        "BEST_COUNT": best.count,
        "BEST_DELTA": best.count - START_COUNT,
        "BEST_SHA256": best.sha256,
        "BEST_IS_START_PORTFOLIO": best.sha256 == START_SHA256,
        "BEST_DESTROY_SET": {
            "DESTROY_SIZE": best.beam.size,
            "POSITIONS": list(best.beam.destroyed.positions),
        },
        "BEST_REPLACEMENT_TICKETS": _ticket_list(best.state.tickets),
        "BEST_NEW_TICKETS": _ticket_list(sorted(set(best_portfolio) - set(START_PORTFOLIO))),
        "BEST_REPLACED_INDICES": [
            index for index, ticket in enumerate(START_PORTFOLIO) if ticket not in best_portfolio
        ],
        "BEST_PORTFOLIO": _ticket_list(best_portfolio),
        "BEST_CANONICAL_RECOUNT": best_recount,
        "CANONICAL_RECOUNT_STATUS": "PASS" if recount_pass else "FAIL",
        "BEST_COUNT_TIE_COUNT": len(best.ties),
        "BEST_COUNT_TIE_DISTINCT_PORTFOLIOS": len({sha for sha, _, _ in best.ties}),
        "BEST_COUNT_TIES_ALL_CANONICALLY_RECOUNTED": global_ties_recounted,
        "BEST_COUNT_TIES_LISTED": [
            {
                "DESTROY_SIZE": beam.size,
                "POSITIONS": list(beam.destroyed.positions),
                "SHA256": sha,
                "REPLACEMENT_TICKETS": _ticket_list(state.tickets),
                "CANONICAL_RECOUNT": beam.recounts.get(beam.portfolio_of(state)),
            }
            for sha, beam, state in best.ties[:LISTED_TIES_MAX]
        ],
        "TIE_BREAK": (
            "within a beam: coverage, then lowest canonical state identity; across destroy sets: "
            "max exact count, then lowest normalized portfolio sha256"
        ),
        "WINNER_REPLACEMENTS_VS_ONE_SHOT": classify_replacements(
            best.state.tickets, prior, best.beam.original_ranks
        ),
        "DID_WINNER_REQUIRE_TICKET_OUTSIDE_ORIGINAL_GLOBAL_TOP48": _yes_no(outside),
        "INTERACTION_AWARE_FINDING": finding,
        "INTERACTION_AWARE_FINDING_RULE": (
            "ESTABLISHED only if the winner uses a ticket outside the one-shot global top 48 of "
            "its destroy set AND BEST_COUNT > START_COUNT AND the canonical recount passes"
        ),
        "WALL_SECONDS": round(wall_seconds, 3),
        "PHASE_SECONDS": {name: round(seconds, 3) for name, seconds in phase_seconds.items()},
        "PEAK_MEMORY_BYTES": peak_memory,
        "PEAK_MEMORY_DEFINITION": "ru_maxrss of the single pilot process (one worker, no children)",
        "CPU_POLICY": {"PROCESSES": 1, "THREAD_ENV": dict(thread_env)},
        "PER_DESTROY_SET": records,
        "RUN_HEAD": run_identity["RUN_HEAD"],
        "RUN_TREE": run_identity["RUN_TREE"],
        "RUN_TRACKED_TREE_CLEAN": run_identity["RUN_TRACKED_TREE_CLEAN"],
        "RUNTIME_MODULE_FILES": dict(runtime_modules),
        "SOURCE_MODULE_PATH": MODULE_RELATIVE_PATH,
        "SOURCE_MODULE_SHA256": module_sha256,
        "RESULT_LOCATOR": RESULT_RELATIVE_PATH,
    }


# ---------------------------------------------------------------------------------------------
# pilot runner
# ---------------------------------------------------------------------------------------------

THREAD_ENV_KEYS: Final = global_pool.THREAD_ENV_KEYS


def _git_identity() -> dict[str, str]:
    def git(*args: str) -> str:
        completed = subprocess.run(
            ["git", *args], cwd=REPO_ROOT, check=True, capture_output=True, text=True
        )
        return completed.stdout.strip()

    return {
        "RUN_HEAD": git("rev-parse", "HEAD"),
        "RUN_TREE": git("rev-parse", "HEAD^{tree}"),
        "RUN_TRACKED_TREE_CLEAN": _yes_no(
            git("status", "--porcelain", "--untracked-files=no") == ""
        ),
    }


def runtime_module_files(repo_root: Path = REPO_ROOT) -> dict[str, str]:
    """The files the three research modules loaded from; all must sit in this checkout's ``src``."""

    source_root = (repo_root / "src").resolve()
    files = {
        name: str(Path(module.__file__ or "").resolve())
        for name, module in (
            ("CONDITIONAL_BEAM", sys.modules[__name__]),
            ("GLOBAL_RESIDUAL_POOL", global_pool),
            ("FIVE_TICKET_REPAIR", five_ticket),
        )
    }
    if any(not Path(path).is_relative_to(source_root) for path in files.values()):
        raise StopConditionError("RUNTIME_MODULE_RESOLUTION_MISMATCH", json.dumps(files))
    return files


def reuse_record(document: Mapping[str, object]) -> dict[str, object]:
    return {
        "REUSE_COMMIT": REUSE_COMMIT,
        "REUSE_ARTIFACT": REUSE_ARTIFACT,
        "REUSE_TASK_ID": document.get("TASK_ID"),
        "REUSE_SCIENTIFIC_RESULT": document.get("SCIENTIFIC_RESULT"),
        "REUSE_BEST_COUNT": document.get("BEST_COUNT"),
        "REUSE_SAMPLE_FILE_SHA256": document.get("SAMPLE_FILE_SHA256"),
        "REUSE_DESTROY_SETS_EQUAL_DETERMINISTIC_SETS": True,
        "CHANGED_MECHANISM": "candidate generation only (one-shot top 48 -> conditional beam)",
    }


def run_pilot(workdir: Path, output: Path) -> dict[str, object]:
    """Bind the reuse sets, reproduce the start, pass parity, run the six beams, write JSON."""

    wall_started = time.perf_counter()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    workdir.mkdir(parents=True, exist_ok=True)
    modules = runtime_module_files()
    universe = build_universe()
    canonical = CanonicalRecounter()
    recounter = CachedRecounter(canonical)
    phase_started = time.perf_counter()
    start_record = reproduce_start(canonical)
    pins = verify_pins(canonical)
    reuse = read_reuse_artifact()
    sets, priors = load_prior_sets(reuse)
    record_progress(
        workdir,
        {
            "EVENT": "BOUND",
            "START": start_record["CANONICAL_RECOUNT"],
            "REUSE_COMMIT": REUSE_COMMIT,
            "SETS": {str(size): [list(p) for p in group] for size, group in sets.items()},
        },
    )
    parity = run_parity(universe, recounter)
    parity_done = time.perf_counter()
    record_progress(
        workdir,
        {
            "EVENT": "PARITY_DONE",
            "COMPARISONS": parity["PARITY_SAMPLE_COUNT"],
            "MISMATCHES": parity["PARITY_MISMATCHES"],
            "REAL_CONDITIONAL_MARGINAL_CHECKS": parity["REAL_CONDITIONAL_MARGINAL_CHECKS"],
        },
    )
    if cast(int, parity["PARITY_MISMATCHES"]) != 0 or not parity["COVERAGE_MEETS_PACKET_MINIMUM"]:
        raise StopConditionError(
            "PARITY_MISMATCH", "pre-pilot parity failed; the pilot must not score"
        )
    tally = ParityTally()
    beams: list[DestroySetBeam] = []
    for size in DESTROY_SIZES:
        for positions in sets[size]:
            try:
                beam = beam_destroy_set(
                    universe,
                    size,
                    positions,
                    recounter=recounter,
                    tally=tally,
                    prior=priors[(size, positions)],
                )
            except MemoryError as error:
                raise StopConditionError("GLOBAL_ENUMERATION_NOT_FEASIBLE", str(error)) from error
            beams.append(beam)
            record_progress(
                workdir,
                {
                    "EVENT": "DESTROY_SET_DONE",
                    "DESTROY_SIZE": size,
                    "POSITIONS": list(positions),
                    "ENUMERATIONS": beam.run.enumerations,
                    "BEST_COUNT": beam.best_count,
                    "BEST_DELTA": beam.best_count - START_COUNT,
                    "FINAL_TIES": len(beam.run.final_ties()),
                    "SECONDS": round(beam.seconds["TOTAL"], 1),
                },
            )
    pilot_done = time.perf_counter()
    document = build_result_document(
        sets=sets,
        priors=priors,
        beams=beams,
        start_record=start_record,
        pins=pins,
        reuse_record=reuse_record(reuse),
        parity=parity,
        pilot_tally=tally,
        wall_seconds=time.perf_counter() - wall_started,
        peak_memory=peak_memory_bytes(),
        run_identity=_git_identity(),
        module_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        runtime_modules=modules,
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
        prog="b649_k20_conditional_global_repair_beam_r1", description=__doc__
    )
    commands = parser.add_subparsers(dest="command", required=True)
    pilot = commands.add_parser("pilot", help="run parity, then the six beams, and write JSON")
    pilot.add_argument("--workdir", type=Path, required=True)
    pilot.add_argument("--output", type=Path, required=True)
    commands.add_parser("parity", help="run only the pre-pilot parity checks")
    args = parser.parse_args(argv)
    try:
        if args.command == "pilot":
            document = run_pilot(args.workdir, args.output)
            print(
                f"result={document['SCIENTIFIC_RESULT']} best_count={document['BEST_COUNT']} "
                f"delta={document['BEST_DELTA']} "
                f"outside={document['DID_WINNER_REQUIRE_TICKET_OUTSIDE_ORIGINAL_GLOBAL_TOP48']} "
                f"wall_seconds={document['WALL_SECONDS']}",
                flush=True,
            )
            return 0
        parity = run_parity(build_universe(), CachedRecounter(CanonicalRecounter()))
        print(canonical_json(parity))
        return 0 if parity["PARITY_MISMATCHES"] == 0 else 1
    except StopConditionError as stop:
        print(f"STOP: {stop}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
