"""B649_K20_CONDITIONAL_GLOBAL_DIVERSITY_BEAM_R2 (width 24, signature-first diversity).

Question: R1 (commit bf8f41d7) ran a conditional global repair beam of width 8 and saw 32-64 way
equal-coverage ties at the retention cutoff, which its lowest-identity tie-break collapsed by
sorted ticket order alone. This variant keeps R1's candidate generation untouched (every retained
partial replacement set ``S`` exact-scores all C(49,6) = 13,983,816 tickets against ``R + S`` and
its 8 largest conditional marginals become children) and changes only the retention rule: the beam
keeps 24 states ranked by exact coverage of ``R + S``, and the tie group that straddles the cutoff
is thinned by deterministic maximin diversity instead of by ticket order.

Diversity distance. The residual-coverage signature of ``S`` is the set of 7-subsets of 1..49 that
``R + S`` does not win (a ticket wins a 7-subset ``E`` when ``|ticket & E| >= 3``; each ``E`` stands
for 7 official outcomes). The primary distance of two states is the symmetric difference of their
signatures, computed exactly on bitmaps and cross-checked against the canonical evaluator through
``|A xor B| = 2 |won(R + S_A + S_B)| - |won(R + S_A)| - |won(R + S_B)|``.

The search is INTERACTION_AWARE but HEURISTIC: BEAM_WIDTH = 24 and 8 children per state bound it,
so no N4 or N5 optimum is claimed. There is no local-mutation prefilter and no random sampling.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from math import comb
from pathlib import Path
from typing import Final, cast

import numpy as np
import numpy.typing as npt

from lottolab.research import b649_k20_conditional_global_repair_beam_r1 as r1
from lottolab.research import b649_k20_five_ticket_exact_repair_r1 as five_ticket
from lottolab.research import b649_k20_global_residual_pool_repair_r1 as global_pool
from lottolab.research.b649_k20_five_ticket_exact_repair_r1 import (
    BIG_LOTTO_GEOMETRY,
    PORTFOLIO_SIZE,
    START_COUNT,
    START_PORTFOLIO,
    START_SHA256,
    CanonicalRecounter,
    Geometry,
    Portfolio,
    Ticket,
    canonical_json,
    destroy_positions,
    direct_marginals,
    iter_subset_mask_blocks,
    normalize_portfolio,
    peak_memory_bytes,
    portfolio_sha256,
    record_progress,
    verify_pins,
    write_atomically,
)
from lottolab.research.b649_k20_global_residual_pool_repair_r1 import (
    OUTRIGHT,
    SUBSET_SIZE,
    TICKET_SIZE,
    TOTAL_TICKETS,
    ColexUniverse,
    CountArray,
    GlobalScores,
    ParityTally,
    StopConditionError,
    brute_force_marginals,
    build_universe,
    check_score_identities,
    exact_global_rank,
    reproduce_start,
)
from lottolab.research.b649_official_any_prize_exact import ticket_mask

type PackedBits = npt.NDArray[np.uint8]
type MaskArray = npt.NDArray[np.uint64]

TASK_ID: Final = "B649_K20_CONDITIONAL_GLOBAL_DIVERSITY_BEAM_R2"
VARIANT: Final = "W24_SIGNATURE_FIRST"
BEAM_WIDTH: Final = 24
EXPANSION_WIDTH: Final = 8
CONTROL_BEAM_WIDTH: Final = 8
CONTROL_DESTROY_SIZE: Final = 4
CONTROL_POSITIONS: Final = (12, 13, 17, 19)
DESTROY_SIZES: Final = (4, 5)
SEARCH_CLASS: Final = "INTERACTION_AWARE_HEURISTIC_DIVERSITY_BEAM"
OPTIMALITY_STATUS: Final = "HEURISTIC_BEAM_WIDTH_24_CHILDREN_8"

POLICY_LOWEST_IDENTITY: Final = "LOWEST_IDENTITY"
POLICY_DIVERSITY: Final = "DIVERSITY"

R1_COMMIT: Final = "bf8f41d72750f881f5a68188eb7cb3bab7b3c108"
R1_RESULT_COMMIT: Final = "3cab702fc65235a9b0fa6b98ba29edfad11899b3"
R1_RESULT_SHA256: Final = "0a59ff5227e99cfe394085bf64685adb2bdf5d26a8707f5dc124408852fdb736"
PRIOR_R2_RESULT_SHA256: Final = "e6b2c652047c57b7ca7a12614013d2bb203d2ab32d1b141f1eeaab59fd73c72c"

RULE_TEXT: Final = """\
B649_K20_CONDITIONAL_GLOBAL_DIVERSITY_BEAM_R2 / W24_SIGNATURE_FIRST: frozen retention rule

1. Candidate generation is the R1 rule, unchanged. Every retained partial replacement set S
   conditions on R + S, exact-scores all 13,983,816 legal tickets, and its 8 largest conditional
   marginals (ties to the lexicographically lowest ticket; tickets already in R + S are illegal)
   become children. Children are deduplicated as canonical replacement-ticket sets and the first
   expansion that reaches a set owns its provenance.
2. BEAM_WIDTH is 24. The PRIMARY RANK is the exact coverage of R + S, higher first.
3. A coverage group whose states all fit in the remaining beam slots is retained whole, ordered by
   lowest canonical state SHA-256. Only the one group that straddles the cutoff (more states than
   remaining slots) is a diversity group. A strictly lower coverage group is never retained
   instead of a higher one.
4. A diversity group of g tied states retaining s < g of them is not cut by lowest identity.
   (A) retain the tied state with the lowest canonical state SHA-256 first.
   (B) repeat until s tied states are retained: retain the not-yet-retained tied state whose
       minimum distance to the already-retained states OF THE SAME TIE GROUP is largest.
   (C) The primary distance is the residual-coverage signature symmetric difference
       |U(R+S1) xor U(R+S2)|, where U(R+S) is the set of 7-subsets of 1..49 not won by R+S.
   (D) The secondary distance, compared only when the primary minimum ties, is the
       replacement-ticket-set symmetric difference |S1 xor S2|.
   (E) Any remaining tie goes to the lowest canonical state SHA-256.
   Canonical state SHA-256 is the SHA-256 of the compact JSON (separators "," and ":") of the
   state's replacement tickets, each sorted ascending and the tickets sorted ascending.
5. The selection order inside a diversity group is the beam order of its states.
6. Depth is 4 for a destroy-4 set and 5 for a destroy-5 set. The six destroy sets are the R1 sets.
7. CONTROL: before any scientific beam runs, the first R1 destroy-4 set is rerun at BEAM_WIDTH 8
   with R1's lowest-identity retention (coverage descending, then ascending sorted ticket tuple);
   every retained state of every level and the terminal best must equal R1's recorded result.
8. The search is heuristic. No complete N4 optimum, complete N5 optimum or global K20 optimum is
   claimed.
"""
RULE_SHA256: Final = hashlib.sha256(RULE_TEXT.encode("utf-8")).hexdigest()

PREREGISTRATION_RELATIVE_PATH: Final = (
    "docs/research/matrix-native-results/b649-k20-conditional-global-diversity-beam-r2-w24-"
    "preregistration.md"
)
MODULE_RELATIVE_PATH: Final = (
    "src/lottolab/research/b649_k20_conditional_global_diversity_beam_r2_w24.py"
)
RESULT_RELATIVE_PATH: Final = (
    "docs/research/matrix-native-results/b649-k20-conditional-global-diversity-beam-r2-w24-"
    "result.json"
)

REPO_ROOT: Final = Path(__file__).resolve().parents[3]
CHUNK_ROWS: Final = 1 << 22
CANONICAL_PAIR_CHECKS_PER_GROUP: Final = 2


# ---------------------------------------------------------------------------------------------
# state identity and distances
# ---------------------------------------------------------------------------------------------


def state_sha256(tickets: Sequence[Sequence[int]]) -> str:
    """Canonical state SHA-256: compact JSON of the sorted replacement tickets."""

    return portfolio_sha256(r1.canonical_state(tickets))


def ticket_set_distance(first: Sequence[Ticket], second: Sequence[Ticket]) -> int:
    """Secondary distance: size of the symmetric difference of two replacement-ticket sets."""

    return len(set(first) ^ set(second))


class SignatureEngine:
    """Exact residual-coverage signatures of partial states over one frozen remainder ``R``.

    The region is every ``(draw_size + 1)``-subset that ``R`` does not win. The signature of a
    state is the bitmap of region subsets that its replacement tickets win, so the signature of
    ``R + S`` is the region minus that bitmap and the two signatures of two states differ in
    exactly the positions where their bitmaps differ.
    """

    def __init__(self, remaining: Sequence[Ticket], geometry: Geometry = BIG_LOTTO_GEOMETRY):
        self.geometry = geometry
        masks = [np.uint64(ticket_mask(ticket)) for ticket in remaining]
        parts: list[MaskArray] = []
        for block in iter_subset_mask_blocks(geometry.pool_size, geometry.subset_size):
            won = np.zeros(block.size, dtype=np.bool_)
            for mask in masks:
                won |= np.bitwise_count(block & mask) >= geometry.outright
            parts.append(block[~won])
        self.region: MaskArray = np.concatenate(parts) if parts else np.empty(0, dtype=np.uint64)
        self.won_by_remaining = geometry.subset_count - int(self.region.size)

    def signature(self, tickets: Sequence[Ticket]) -> PackedBits:
        """Packed bitmap of the region subsets won by ``tickets``."""

        masks = [np.uint64(ticket_mask(ticket)) for ticket in tickets]
        won = np.zeros(self.region.size, dtype=np.bool_)
        for start in range(0, int(self.region.size), CHUNK_ROWS):
            chunk = self.region[start : start + CHUNK_ROWS]
            piece = won[start : start + chunk.size]
            for mask in masks:
                piece |= np.bitwise_count(chunk & mask) >= self.geometry.outright
        return np.packbits(won)


def bitmap_distance(first: PackedBits, second: PackedBits) -> int:
    """Number of positions at which two packed bitmaps differ."""

    return int(np.bitwise_count(first ^ second).sum(dtype=np.int64))


type DistanceFn = Callable[[r1.BeamState, r1.BeamState], tuple[int, int]]


class SignatureDistance:
    """``(primary, secondary)`` distances of two beam states over one frozen remainder."""

    def __init__(self, remaining: Sequence[Ticket], geometry: Geometry = BIG_LOTTO_GEOMETRY):
        self.remaining = tuple(remaining)
        self.engine = SignatureEngine(remaining, geometry)
        self.cache: dict[Portfolio, PackedBits] = {}
        self.signatures_built = 0
        self.distances_taken = 0

    def signature(self, state: r1.BeamState) -> PackedBits:
        if state.tickets not in self.cache:
            self.cache[state.tickets] = self.engine.signature(state.tickets)
            self.signatures_built += 1
        return self.cache[state.tickets]

    def __call__(self, first: r1.BeamState, second: r1.BeamState) -> tuple[int, int]:
        self.distances_taken += 1
        return (
            bitmap_distance(self.signature(first), self.signature(second)),
            ticket_set_distance(first.tickets, second.tickets),
        )

    def release(self) -> None:
        """Drop the cached signatures (one tie group's worth) to bound memory."""

        self.cache.clear()


def canonical_signature_distance(
    recounter: r1.CachedRecounter,
    remaining: Sequence[Ticket],
    first: r1.BeamState,
    second: r1.BeamState,
) -> int:
    """The same primary distance through the canonical evaluator on ``R + S_A + S_B``."""

    union = tuple(sorted(set(remaining) | set(first.tickets) | set(second.tickets)))
    outcomes = recounter.count(union)
    if outcomes % SUBSET_SIZE:
        raise AssertionError("the canonical count of a union portfolio is not a multiple of 7")
    return 2 * (outcomes // SUBSET_SIZE) - first.covered - second.covered


# ---------------------------------------------------------------------------------------------
# diversity selection of one tie group
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DiverseSelection:
    """``slots`` states of a tie group in selection order with their selection distances."""

    selected: tuple[r1.BeamState, ...]
    min_signature: tuple[int | None, ...]
    min_ticket: tuple[int | None, ...]
    pair_signature: tuple[int, ...]
    pair_ticket: tuple[int, ...]


def select_diverse(
    group: Sequence[r1.BeamState], slots: int, distance: DistanceFn
) -> DiverseSelection:
    """Rule 4: lowest SHA first, then repeated maximin on (signature, ticket-set) distance."""

    if not 1 <= slots < len(group):
        raise ValueError("a diversity group retains between 1 and len(group) - 1 states")
    if len({state.covered for state in group}) != 1:
        raise ValueError("a diversity group holds states of one exact coverage")
    ordered = sorted(group, key=lambda state: (state_sha256(state.tickets), state.tickets))
    pending = ordered[1:]
    running: list[tuple[int, int] | None] = [None] * len(pending)
    taken: dict[tuple[int, int], tuple[int, int]] = {}
    chosen = [ordered[0]]
    alive = list(range(len(pending)))
    min_signature: list[int | None] = [None]
    min_ticket: list[int | None] = [None]
    pair_signature: list[int] = []
    pair_ticket: list[int] = []

    def preference(index: int) -> tuple[int, int, int]:
        value = running[index]
        assert value is not None
        return (value[0], value[1], -index)

    while len(chosen) < slots:
        newest = len(chosen) - 1
        for index in alive:
            sig, tkt = distance(pending[index], chosen[newest])
            taken[(index, newest)] = (sig, tkt)
            current = running[index]
            running[index] = (
                (sig, tkt) if current is None else (min(current[0], sig), min(current[1], tkt))
            )
        pick = max(alive, key=preference)
        value = cast(tuple[int, int], running[pick])
        min_signature.append(value[0])
        min_ticket.append(value[1])
        for earlier in range(len(chosen)):
            sig, tkt = taken[(pick, earlier)]
            pair_signature.append(sig)
            pair_ticket.append(tkt)
        chosen.append(pending[pick])
        alive.remove(pick)
    return DiverseSelection(
        selected=tuple(chosen),
        min_signature=tuple(min_signature),
        min_ticket=tuple(min_ticket),
        pair_signature=tuple(pair_signature),
        pair_ticket=tuple(pair_ticket),
    )


# ---------------------------------------------------------------------------------------------
# retention policies and the policy beam
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TieSelection:
    """The one diversity group of a level: who was retained, at what distance, and what R1 keeps."""

    level: int
    covered: int
    group_size: int
    slots: int
    selected: tuple[Portfolio, ...]
    selected_sha256: tuple[str, ...]
    min_signature: tuple[int | None, ...]
    min_ticket: tuple[int | None, ...]
    pair_signature: tuple[int, ...]
    pair_ticket: tuple[int, ...]
    r1_rule_keeps: tuple[Portfolio, ...]

    @property
    def saved(self) -> tuple[Portfolio, ...]:
        """Retained by diversity although R1's lowest-identity cut would have dropped them."""

        return tuple(state for state in self.selected if state not in set(self.r1_rule_keeps))

    @property
    def dropped_that_r1_keeps(self) -> tuple[Portfolio, ...]:
        """Kept by R1's lowest-identity cut although diversity dropped them."""

        return tuple(state for state in self.r1_rule_keeps if state not in set(self.selected))


@dataclass(frozen=True, slots=True)
class LevelTies:
    """Tie statistics of one level's unique candidates and the diversity group, if any."""

    level: int
    tie_groups: int
    max_group_size: int
    tied_states: int
    cutoff_group_size: int
    cutoff_slots: int
    selection: TieSelection | None


def retain_states(
    level: int,
    candidates: Sequence[r1.BeamState],
    beam_width: int,
    policy: str,
    distance: DistanceFn | None,
) -> tuple[tuple[r1.BeamState, ...], LevelTies]:
    """Beam retention of one level from candidates ordered by coverage descending.

    ``LOWEST_IDENTITY`` is R1's cut (the first ``beam_width`` candidates in R1's order);
    ``DIVERSITY`` is rule 3 and rule 4 of the frozen rule text.
    """

    if policy not in (POLICY_LOWEST_IDENTITY, POLICY_DIVERSITY):
        raise ValueError(f"unknown retention policy {policy}")
    groups = [list(group) for _, group in itertools.groupby(candidates, key=lambda s: s.covered)]
    tied = [group for group in groups if len(group) > 1]
    cutoff_size, cutoff_slots, taken = 0, 0, 0
    for group in groups:
        room = beam_width - taken
        if room <= 0:
            break
        if len(group) > room:
            cutoff_size, cutoff_slots = len(group), room
            break
        taken += len(group)
    ties = LevelTies(
        level=level,
        tie_groups=len(tied),
        max_group_size=max((len(group) for group in groups), default=0),
        tied_states=sum(len(group) for group in tied),
        cutoff_group_size=cutoff_size,
        cutoff_slots=cutoff_slots,
        selection=None,
    )
    if policy == POLICY_LOWEST_IDENTITY:
        return tuple(candidates[:beam_width]), ties
    retained: list[r1.BeamState] = []
    selection: TieSelection | None = None
    for group in groups:
        room = beam_width - len(retained)
        if room <= 0:
            break
        if len(group) <= room:
            retained.extend(sorted(group, key=lambda s: (state_sha256(s.tickets), s.tickets)))
            continue
        if distance is None:
            raise ValueError("the diversity policy needs a distance function")
        chosen = select_diverse(group, room, distance)
        r1_keeps = tuple(state.tickets for state in group[:room])
        selection = TieSelection(
            level=level,
            covered=group[0].covered,
            group_size=len(group),
            slots=room,
            selected=tuple(state.tickets for state in chosen.selected),
            selected_sha256=tuple(state_sha256(state.tickets) for state in chosen.selected),
            min_signature=chosen.min_signature,
            min_ticket=chosen.min_ticket,
            pair_signature=chosen.pair_signature,
            pair_ticket=chosen.pair_ticket,
            r1_rule_keeps=r1_keeps,
        )
        retained.extend(chosen.selected)
        break
    return tuple(retained), replace(ties, selection=selection)


@dataclass(frozen=True, slots=True)
class PolicyBeam:
    """An R1-shaped beam run plus the tie statistics of each of its levels."""

    run: r1.BeamRun
    ties: tuple[LevelTies, ...]


def run_policy_beam(
    universe: ColexUniverse,
    remaining: Sequence[Ticket],
    depth: int,
    *,
    base_covered: int,
    beam_width: int,
    expansion_width: int,
    policy: str,
    distance: DistanceFn | None = None,
    inspect: r1.ExpansionHook | None = None,
    release: Callable[[], None] | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> PolicyBeam:
    """R1's conditional beam with a pluggable retention policy.

    Candidate generation is a line-for-line copy of ``r1.run_beam``; only the cut differs. With
    ``LOWEST_IDENTITY`` the result equals ``r1.run_beam`` exactly.
    """

    if depth < 1 or beam_width < 1 or expansion_width < 1:
        raise ValueError("depth, beam width and expansion width must be positive")
    remaining = tuple(remaining)
    subset_total = comb(universe.pool_size, SUBSET_SIZE)
    beam: tuple[r1.BeamState, ...] = (r1.BeamState((), base_covered),)
    expansions: list[r1.Expansion] = []
    levels: list[r1.BeamLevel] = []
    level_ties: list[LevelTies] = []
    for level in range(1, depth + 1):
        children: dict[Portfolio, r1.BeamState] = {}
        generated = 0
        duplicates = 0
        for parent in beam:
            started = clock()
            frozen: Portfolio = (*remaining, *parent.tickets)
            scores = global_pool.score_all_tickets(universe, frozen)
            residual = subset_total - parent.covered
            try:
                identities = check_score_identities(scores, universe, residual)
            except AssertionError as error:
                raise StopConditionError(
                    "CONDITIONAL_ENUMERATION_IDENTITY_REFUTED", str(error)
                ) from error
            frozen_indices = [universe.index_of(ticket) for ticket in frozen]
            chosen = r1.next_ticket_indices(
                scores.marginals, universe.tickets, frozen_indices, expansion_width
            )
            nexts = tuple(
                r1.NextTicket(
                    universe.ticket_at(int(index)), int(index), int(scores.marginals[index]), place
                )
                for place, index in enumerate(chosen, start=1)
            )
            expansion = r1.Expansion(
                level=level,
                parent=parent,
                residual_subsets=residual,
                identities=identities,
                children=nexts,
                cutoff=r1.cutoff_stats(scores.marginals, frozen_indices, nexts[-1].marginal),
                seconds=clock() - started,
            )
            if inspect is not None:
                inspect(expansion, scores, frozen)
            expansions.append(expansion)
            for child in nexts:
                generated += 1
                tickets = r1.canonical_state((*parent.tickets, child.ticket))
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
                children[tickets] = r1.BeamState(
                    tickets, covered, parent.tickets, child.ticket, child.marginal, child.position
                )
        candidates = tuple(sorted(children.values(), key=r1.retention_key))
        beam, ties = retain_states(level, candidates, beam_width, policy, distance)
        if release is not None:
            release()
        level_ties.append(ties)
        levels.append(r1.BeamLevel(level, generated, duplicates, candidates, beam))
    run = r1.BeamRun(
        remaining=remaining,
        base_covered=base_covered,
        depth=depth,
        beam_width=beam_width,
        expansion_width=expansion_width,
        expansions=tuple(expansions),
        levels=tuple(levels),
    )
    return PolicyBeam(run=run, ties=tuple(level_ties))


# ---------------------------------------------------------------------------------------------
# one destroy set end to end, with inline checks
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DiversityBeam:
    """The R1-shaped destroy-set record plus tie statistics and signature parity."""

    beam: r1.DestroySetBeam
    ties: tuple[LevelTies, ...]
    policy: str
    signature_checks: tuple[dict[str, object], ...]
    signatures_built: int
    distances_taken: int


def _stop_on(tally: ParityTally, family: str, ok: bool, detail: str) -> None:
    tally.check(family, ok)
    if not ok:
        raise StopConditionError("PARITY_MISMATCH", f"{family}: {detail}")


def _pair_order(selection: TieSelection, size: int) -> list[tuple[int, int]]:
    """Deterministic pairs of selected states to cross-check against the canonical evaluator."""

    pairs = list(itertools.combinations(range(len(selection.selected)), 2))
    pairs.sort(
        key=lambda pair: hashlib.sha256(
            f"{TASK_ID}:{VARIANT}:pairs:{size}:{selection.level}:{pair}".encode()
        ).digest()
    )
    return pairs[:CANONICAL_PAIR_CHECKS_PER_GROUP]


def diversity_destroy_set(
    universe: ColexUniverse,
    size: int,
    positions: Sequence[int],
    *,
    recounter: r1.CachedRecounter,
    tally: ParityTally,
    prior: r1.PriorSet | None,
    policy: str,
    beam_width: int,
    expansion_width: int = EXPANSION_WIDTH,
    direct_check: bool = True,
    depth: int | None = None,
) -> DiversityBeam:
    """Freeze START minus ``positions``, run the policy beam and recount it canonically.

    The inline checks are R1's, every one fail-closed: the depth-0 top 48 equals the reuse
    artifact; every expansion's next-ticket marginals equal the brute-force residual count against
    ``R + S``; every retained state's chained coverage equals its canonical recount (so every
    retained child also checks its conditional marginal as a canonical difference to its retained
    parent); every final best-count tie is recounted canonically. On top, the signature distance of
    sampled selected pairs of each diversity group equals the canonical union-formula distance.
    """

    started = time.perf_counter()
    seconds: dict[str, float] = {}
    destroyed = destroy_positions(START_PORTFOLIO, positions)
    remaining = destroyed.remaining
    remaining_count = recounter.count(remaining)
    if remaining_count % SUBSET_SIZE:
        raise AssertionError("the canonical count of R is not a multiple of 7")
    phase = time.perf_counter()
    distance = SignatureDistance(remaining) if policy == POLICY_DIVERSITY else None
    seconds["SIGNATURE_REGION"] = time.perf_counter() - phase
    if distance is not None:
        _stop_on(
            tally,
            "SIGNATURE_REGION_EQUALS_UNWON_SUBSETS_OF_R",
            distance.engine.won_by_remaining * SUBSET_SIZE == remaining_count,
            f"{size}:{tuple(positions)}",
        )
    depth0: dict[str, object] = {}
    direct_seconds = [0.0]

    def hook(expansion: r1.Expansion, scores: GlobalScores, frozen: Portfolio) -> None:
        if not expansion.conditional:
            depth0["MARGINALS"] = scores.marginals
            if prior is not None:
                depth0["MATCH"] = r1.depth0_top_matches_prior(universe, scores, prior)
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

    policy_beam = run_policy_beam(
        universe,
        remaining,
        r1.depth_for(size) if depth is None else depth,
        base_covered=remaining_count // SUBSET_SIZE,
        beam_width=beam_width,
        expansion_width=expansion_width,
        policy=policy,
        distance=distance,
        inspect=hook,
        release=None if distance is None else distance.release,
    )
    run = policy_beam.run
    seconds["BEAM"] = time.perf_counter() - started
    seconds["DIRECT_CHECKS"] = direct_seconds[0]
    tally.check(
        "PILOT_EVERY_EXPANSION_SCORED_THE_COMPLETE_UNIVERSE",
        all(expansion.tickets_scored == universe.tickets.shape[0] for expansion in run.expansions),
    )

    phase = time.perf_counter()
    recounts: dict[Portfolio, int] = {}

    def recount(state: r1.BeamState) -> int:
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
    signature_checks: list[dict[str, object]] = []
    if distance is not None:
        by_tickets = {state.tickets: state for level in run.levels for state in level.candidates}
        for ties in policy_beam.ties:
            selection = ties.selection
            if selection is None or len(selection.selected) < 2:
                continue
            for first, second in _pair_order(selection, size):
                a, b = by_tickets[selection.selected[first]], by_tickets[selection.selected[second]]
                fast = distance(a, b)[0]
                canonical = canonical_signature_distance(recounter, remaining, a, b)
                _stop_on(
                    tally,
                    "RUN_SIGNATURE_DISTANCE_EQUALS_CANONICAL_UNION_FORMULA",
                    fast == canonical,
                    f"{a.tickets} vs {b.tickets}: {fast} != {canonical}",
                )
                signature_checks.append(
                    {
                        "LEVEL": selection.level,
                        "FIRST": [list(t) for t in a.tickets],
                        "SECOND": [list(t) for t in b.tickets],
                        "SIGNATURE_DISTANCE": fast,
                        "CANONICAL_UNION_FORMULA_DISTANCE": canonical,
                    }
                )
        distance.release()
    seconds["SIGNATURE_PARITY"] = time.perf_counter() - phase

    phase = time.perf_counter()
    marginals = cast(CountArray, depth0["MARGINALS"])
    ranked_tickets = sorted({t for s in run.final.retained for t in s.tickets})
    original_ranks = {
        ticket: exact_global_rank(marginals, universe.tickets, universe.index_of(ticket))
        for ticket in ranked_tickets
    }
    seconds["ORIGINAL_RANKS"] = time.perf_counter() - phase
    seconds["TOTAL"] = time.perf_counter() - started
    beam = r1.DestroySetBeam(
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
    return DiversityBeam(
        beam=beam,
        ties=policy_beam.ties,
        policy=policy,
        signature_checks=tuple(signature_checks),
        signatures_built=0 if distance is None else distance.signatures_built,
        distances_taken=0 if distance is None else distance.distances_taken,
    )


# ---------------------------------------------------------------------------------------------
# parity: a reference diversity beam written from the rule text, and the signature distance
# ---------------------------------------------------------------------------------------------

TOY_POOL_SIZES: Final = (14, 15, 16)
TOY_FROZEN_SIZES: Final = (1, 2, 3)
TOY_DEPTH: Final = 3
# (beam width, expansion width): narrow beams over wide expansions cut inside equal-coverage ties
TOY_SHAPES: Final = ((2, 6), (3, 6), (4, 8))
REAL_SIGNATURE_STATES: Final = 8
REAL_SIGNATURE_PAIRS: Final = 14
MIN_REAL_SIGNATURE_CHECKS: Final = 40

type ReferenceLevel = tuple[list[tuple[Portfolio, int]], list[tuple[Portfolio, int]], int]


def _reference_sha(tickets: Sequence[Ticket]) -> str:
    payload = json.dumps([list(ticket) for ticket in sorted(tickets)], separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def reference_diversity_beam(
    pool_size: int,
    remaining: Sequence[Ticket],
    depth: int,
    beam_width: int,
    expansion_width: int,
    policy: str,
) -> list[ReferenceLevel]:
    """The frozen rule spelled out with brute-force marginals and explicit signature sets.

    Shares no code with ``run_policy_beam``, the signature engine or ``select_diverse``. Per level:
    every unique child ``(tickets, covered)`` in coverage-then-identity order, the retained states
    in beam order and the number of children generated before deduplication.
    """

    total = comb(pool_size, SUBSET_SIZE)
    subsets = [
        sum(1 << i for i in chosen) for chosen in itertools.combinations(range(pool_size), 7)
    ]
    masks_r = [sum(1 << (number - 1) for number in ticket) for ticket in remaining]

    def unwon(state: Portfolio) -> frozenset[int]:
        masks = [*masks_r, *(sum(1 << (number - 1) for number in ticket) for ticket in state)]
        return frozenset(
            subset
            for subset in subsets
            if not any((subset & mask).bit_count() >= OUTRIGHT for mask in masks)
        )

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
        if policy == POLICY_LOWEST_IDENTITY:
            retained = ordered[:beam_width]
        else:
            retained: list[tuple[Portfolio, int]] = []
            by_coverage: dict[int, list[tuple[Portfolio, int]]] = {}
            for item in ordered:
                by_coverage.setdefault(item[1], []).append(item)
            for coverage in sorted(by_coverage, reverse=True):
                group = sorted(by_coverage[coverage], key=lambda item: _reference_sha(item[0]))
                room = beam_width - len(retained)
                if room <= 0:
                    break
                if len(group) <= room:
                    retained.extend(group)
                    continue
                signatures = {item[0]: unwon(item[0]) for item in group}
                chosen = [group[0]]
                rest = group[1:]
                while len(chosen) < room:
                    best: tuple[Portfolio, int] | None = None
                    best_score: tuple[int, int] | None = None
                    for item in rest:
                        score = (
                            min(len(signatures[item[0]] ^ signatures[c[0]]) for c in chosen),
                            min(len(set(item[0]) ^ set(c[0])) for c in chosen),
                        )
                        if best_score is None or score > best_score:
                            best, best_score = item, score
                    assert best is not None
                    chosen.append(best)
                    rest.remove(best)
                retained.extend(chosen)
                break
        beam = retained
        levels.append((ordered, retained, generated))
    return levels


def run_toy_parity() -> tuple[ParityTally, dict[str, int]]:
    """Module beam against the reference beam, R1's beam and the canonical evaluator on toys."""

    tally = ParityTally()
    seen = {"DIVERSITY_GROUPS": 0, "STATES_SAVED_FROM_R1_CUT": 0, "LARGEST_DIVERSITY_GROUP": 0}
    for pool_size in TOY_POOL_SIZES:
        universe = build_universe(pool_size)
        geometry = Geometry(pool_size, TICKET_SIZE, OUTRIGHT)
        recounter = r1.CachedRecounter(CanonicalRecounter(geometry), geometry)
        for frozen_size in TOY_FROZEN_SIZES:
            remaining = r1.toy_remaining(pool_size, frozen_size)
            base = recounter.count(remaining) // SUBSET_SIZE
            for beam_width, expansion_width in TOY_SHAPES:
                distance = SignatureDistance(remaining, geometry)
                diverse = run_policy_beam(
                    universe,
                    remaining,
                    TOY_DEPTH,
                    base_covered=base,
                    beam_width=beam_width,
                    expansion_width=expansion_width,
                    policy=POLICY_DIVERSITY,
                    distance=distance,
                )
                plain = run_policy_beam(
                    universe,
                    remaining,
                    TOY_DEPTH,
                    base_covered=base,
                    beam_width=beam_width,
                    expansion_width=expansion_width,
                    policy=POLICY_LOWEST_IDENTITY,
                )
                original = r1.run_beam(
                    universe,
                    remaining,
                    TOY_DEPTH,
                    base_covered=base,
                    beam_width=beam_width,
                    expansion_width=expansion_width,
                )
                for ours, theirs in zip(plain.run.levels, original.levels, strict=True):
                    tally.check(
                        "TOY_LOWEST_IDENTITY_POLICY_EQUALS_R1_BEAM",
                        [(s.tickets, s.covered, s.parent) for s in ours.candidates]
                        == [(s.tickets, s.covered, s.parent) for s in theirs.candidates]
                        and [(s.tickets, s.covered) for s in ours.retained]
                        == [(s.tickets, s.covered) for s in theirs.retained]
                        and (ours.generated, ours.duplicates)
                        == (theirs.generated, theirs.duplicates),
                    )
                for policy, ran in (
                    (POLICY_DIVERSITY, diverse),
                    (POLICY_LOWEST_IDENTITY, plain),
                ):
                    reference = reference_diversity_beam(
                        pool_size, remaining, TOY_DEPTH, beam_width, expansion_width, policy
                    )
                    for level, (ordered, kept, generated) in zip(
                        ran.run.levels, reference, strict=True
                    ):
                        tally.check(
                            f"TOY_{policy}_CANDIDATES_EQUAL_REFERENCE",
                            [(s.tickets, s.covered) for s in level.candidates] == ordered,
                        )
                        tally.check(
                            f"TOY_{policy}_RETAINED_ORDER_EQUALS_REFERENCE",
                            [(s.tickets, s.covered) for s in level.retained] == kept,
                        )
                        tally.check(
                            f"TOY_{policy}_GENERATED_EQUALS_REFERENCE",
                            level.generated == generated
                            and level.generated - level.duplicates == level.unique,
                        )
                for level in diverse.run.levels:
                    for state in level.retained:
                        tally.check(
                            "TOY_RETAINED_STATE_COVERAGE_EQUALS_CANONICAL",
                            recounter.count((*remaining, *state.tickets))
                            == SUBSET_SIZE * state.covered,
                        )
                for ties in diverse.ties:
                    selection = ties.selection
                    if selection is None:
                        continue
                    seen["DIVERSITY_GROUPS"] += 1
                    seen["STATES_SAVED_FROM_R1_CUT"] += len(selection.saved)
                    seen["LARGEST_DIVERSITY_GROUP"] = max(
                        seen["LARGEST_DIVERSITY_GROUP"], selection.group_size
                    )
                    states = [r1.BeamState(t, selection.covered) for t in selection.selected]
                    for first, second in itertools.combinations(states, 2):
                        canonical = canonical_signature_distance(
                            recounter, remaining, first, second
                        )
                        tally.check(
                            "TOY_SIGNATURE_DISTANCE_EQUALS_CANONICAL_UNION_FORMULA",
                            distance(first, second)[0] == canonical,
                        )
    tally.check("TOY_SOME_TIE_GROUP_WAS_THINNED_BY_DIVERSITY", seen["DIVERSITY_GROUPS"] > 0)
    tally.check("TOY_SOME_STATE_WAS_SAVED_FROM_THE_R1_CUT", seen["STATES_SAVED_FROM_R1_CUT"] > 0)
    return tally, seen


def run_real_signature_parity(
    universe: ColexUniverse, recounter: r1.CachedRecounter
) -> tuple[ParityTally, list[dict[str, object]]]:
    """Real 49/6 signature distances against the canonical evaluator on the parity destroy sets.

    The states are deterministic partial sets of hashed tickets (sizes 1..4 plus one state that
    extends another), not beam states, so the distance engine is exercised on overlapping and
    disjoint unions before any pilot set is scored.
    """

    tally = ParityTally()
    records: list[dict[str, object]] = []
    for size, sets in global_pool.parity_destroy_sets().items():
        for positions in sets:
            remaining = destroy_positions(START_PORTFOLIO, positions).remaining
            distance = SignatureDistance(remaining)
            tag = f"signature:{size}:{','.join(map(str, positions))}"
            sizes = [1 + index % 3 for index in range(REAL_SIGNATURE_STATES)]
            pool = r1.hashed_tickets(universe, tag, sum(sizes) + 1)
            states: list[r1.BeamState] = []
            cursor = 0
            for width in sizes:
                tickets = r1.canonical_state(pool[cursor : cursor + width])
                cursor += width
                covered = recounter.count((*remaining, *tickets)) // SUBSET_SIZE
                states.append(r1.BeamState(tickets, covered))
            extended = r1.canonical_state((*states[1].tickets, pool[-1]))
            states.append(
                r1.BeamState(extended, recounter.count((*remaining, *extended)) // SUBSET_SIZE)
            )
            tally.check(
                "REAL_SIGNATURE_REGION_EQUALS_UNWON_SUBSETS_OF_R",
                distance.engine.won_by_remaining * SUBSET_SIZE == recounter.count(remaining),
            )
            order = list(itertools.combinations(range(len(states)), 2))
            order.sort(key=lambda pair: hashlib.sha256(f"{tag}:{pair}".encode()).digest())
            checked: list[dict[str, object]] = []
            for first, second in [(0, 0), *order[: REAL_SIGNATURE_PAIRS - 1]]:
                a, b = states[first], states[second]
                fast = distance(a, b)[0]
                canonical = canonical_signature_distance(recounter, remaining, a, b)
                tally.check(
                    "REAL_SIGNATURE_DISTANCE_EQUALS_CANONICAL_UNION_FORMULA", fast == canonical
                )
                checked.append(
                    {
                        "FIRST": [list(t) for t in a.tickets],
                        "SECOND": [list(t) for t in b.tickets],
                        "SIGNATURE_DISTANCE": fast,
                        "CANONICAL_UNION_FORMULA_DISTANCE": canonical,
                    }
                )
            records.append({"DESTROY_SIZE": size, "POSITIONS": list(positions), "PAIRS": checked})
            distance.release()
    return tally, records


def run_signature_parity(
    universe: ColexUniverse, recounter: r1.CachedRecounter
) -> dict[str, object]:
    """All pre-pilot parity of the new retention and distance code."""

    toy, seen = run_toy_parity()
    real, records = run_real_signature_parity(universe, recounter)
    families = cast(dict[str, dict[str, int]], real.detail())
    signature = families["REAL_SIGNATURE_DISTANCE_EQUALS_CANONICAL_UNION_FORMULA"]
    return {
        "PARITY_SAMPLE_COUNT": toy.comparisons + real.comparisons,
        "PARITY_MISMATCHES": toy.mismatches + real.mismatches,
        "REAL_SIGNATURE_CHECKS": signature["COMPARISONS"],
        "MIN_REAL_SIGNATURE_CHECKS": MIN_REAL_SIGNATURE_CHECKS,
        "COVERAGE_MEETS_MINIMUM": signature["COMPARISONS"] >= MIN_REAL_SIGNATURE_CHECKS,
        "TOY": {
            "COMPARISONS": toy.comparisons,
            "MISMATCHES": toy.mismatches,
            "SHAPES": [list(shape) for shape in TOY_SHAPES],
            "SEEN": seen,
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
# control: R1 reproduced at width 8 with its original tie-break
# ---------------------------------------------------------------------------------------------


def read_r1_result(repo_root: Path = REPO_ROOT) -> tuple[dict[str, object], str]:
    """R1's committed result document and the SHA-256 of its bytes (a pinned identity)."""

    path = repo_root / r1.RESULT_RELATIVE_PATH
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != R1_RESULT_SHA256:
        raise StopConditionError("R1_RESULT_IDENTITY_MISMATCH", f"{path}: {digest}")
    document: object = json.loads(data)
    if not isinstance(document, dict):
        raise StopConditionError("R1_RESULT_IDENTITY_MISMATCH", "the R1 result is not an object")
    return cast(dict[str, object], document), digest


def _record_tickets(record: Mapping[str, object], key: str) -> Portfolio:
    return tuple(tuple(ticket) for ticket in cast(list[list[int]], record[key]))


def control_matches_r1(control: DiversityBeam, r1_set: Mapping[str, object]) -> dict[str, object]:
    """Compare every retained state of every level and the terminal best with R1's record."""

    r1_levels = cast(list[dict[str, object]], r1_set["LEVELS"])
    levels_ok: list[bool] = []
    for ours, theirs in zip(control.beam.run.levels, r1_levels, strict=False):
        ours_rows = [(s.tickets, SUBSET_SIZE * s.covered) for s in ours.retained]
        theirs_rows = [
            (_record_tickets(row, "REPLACEMENT_TICKETS"), cast(int, row["OUTCOMES"]))
            for row in cast(list[dict[str, object]], theirs["RETAINED"])
        ]
        levels_ok.append(ours_rows == theirs_rows)
    run = control.beam.run
    checks = {
        "RETAINED_STATES_EQUAL_PER_LEVEL": all(levels_ok)
        and len(levels_ok) == len(r1_levels) == run.depth,
        "BEST_COUNT_EQUAL": control.beam.best_count == r1_set["BEST_COUNT"],
        "BEST_PORTFOLIO_SHA256_EQUAL": portfolio_sha256(control.beam.best_portfolio)
        == r1_set["BEST_PORTFOLIO_SHA256"],
        "BEST_REPLACEMENT_TICKETS_EQUAL": run.best.tickets
        == _record_tickets(r1_set, "BEST_REPLACEMENT_TICKETS"),
        "FINAL_BEST_COUNT_TIES_EQUAL": len(run.final_ties()) == r1_set["FINAL_BEST_COUNT_TIES"],
        "CONDITIONAL_ENUMERATIONS_EQUAL": run.enumerations == r1_set["CONDITIONAL_ENUMERATIONS"],
        "BEAM_STATES_GENERATED_EQUAL": run.generated == r1_set["BEAM_STATES_GENERATED"],
        "BEAM_STATES_RETAINED_EQUAL": run.retained == r1_set["BEAM_STATES_RETAINED"],
    }
    return {"PER_LEVEL_RETAINED_EQUAL": levels_ok, **checks, "MATCH": all(checks.values())}


def run_control(
    universe: ColexUniverse,
    recounter: r1.CachedRecounter,
    priors: Mapping[r1.SetKey, r1.PriorSet],
    r1_document: Mapping[str, object],
    tally: ParityTally,
) -> tuple[DiversityBeam, dict[str, object]]:
    """Rerun one R1 destroy-4 set at width 8 with R1's tie-break; STOP unless it equals R1."""

    key = (CONTROL_DESTROY_SIZE, CONTROL_POSITIONS)
    control = diversity_destroy_set(
        universe,
        CONTROL_DESTROY_SIZE,
        CONTROL_POSITIONS,
        recounter=recounter,
        tally=tally,
        prior=priors[key],
        policy=POLICY_LOWEST_IDENTITY,
        beam_width=CONTROL_BEAM_WIDTH,
    )
    r1_sets = [
        record
        for record in cast(list[dict[str, object]], r1_document["PER_DESTROY_SET"])
        if (record["DESTROY_SIZE"], tuple(cast(list[int], record["POSITIONS"]))) == key
    ]
    if len(r1_sets) != 1:
        raise StopConditionError("CONTROL_R1_MISMATCH", "R1 has no record of the control set")
    comparison = control_matches_r1(control, r1_sets[0])
    if not comparison["MATCH"]:
        raise StopConditionError("CONTROL_R1_MISMATCH", json.dumps(comparison, sort_keys=True))
    record: dict[str, object] = {
        "CONTROL_ROLE": "first R1 destroy-4 set rerun at width 8 with R1's lowest-identity cut",
        "DESTROY_SIZE": CONTROL_DESTROY_SIZE,
        "POSITIONS": list(CONTROL_POSITIONS),
        "BEAM_WIDTH": CONTROL_BEAM_WIDTH,
        "CHILDREN_PER_STATE": EXPANSION_WIDTH,
        "BEST_COUNT": control.beam.best_count,
        "BEST_PORTFOLIO_SHA256": portfolio_sha256(control.beam.best_portfolio),
        "CANONICAL_RECOUNT": control.beam.recount_of(control.beam.run.best),
        "CONDITIONAL_ENUMERATIONS": control.beam.run.enumerations,
        "BEAM_STATES_GENERATED": control.beam.run.generated,
        "BEAM_STATES_RETAINED": control.beam.run.retained,
        "TIE_GROUPS_TOTAL": sum(t.tie_groups for t in control.ties),
        "MAX_TIE_GROUP_SIZE": max(t.max_group_size for t in control.ties),
        "R1_RESULT_SHA256": R1_RESULT_SHA256,
        "COMPARISON_WITH_R1": comparison,
        "STATUS": "PASS",
    }
    return control, record


# ---------------------------------------------------------------------------------------------
# result records
# ---------------------------------------------------------------------------------------------

RESULT_IMPROVED: Final = "IMPROVED"
RESULT_NO_IMPROVEMENT: Final = "NO_IMPROVEMENT"
SCIENTIFIC_SCOPE: Final = "3_DESTROY4_PLUS_3_DESTROY5_CONDITIONAL_GLOBAL_DIVERSITY_BEAM_WIDTH24"
NOT_CLAIMED: Final = (
    "complete N4 optimum",
    "complete N5 optimum",
    "optimality of any beam state (BEAM_WIDTH = 24 and 8 children per state are heuristic bounds)",
    "global K20 optimum",
    "superiority or equality relative to protected Lane 3",
)
LISTED_TIES_MAX: Final = 200
PRIOR_R2_PUBLICATION_COMMIT: Final = "8073551372c9d6c8b83b9434bf8e4e52f0d46e8e"
PRIOR_R2_RESULT_PATH: Final = (
    "docs/research/matrix-native-results/b649-k20-conditional-global-diversity-beam-r2-result.json"
)
THREAD_ENV_KEYS: Final = global_pool.THREAD_ENV_KEYS


def _ticket_list(tickets: Sequence[Ticket]) -> list[list[int]]:
    return [list(ticket) for ticket in tickets]


def _yes_no(value: bool) -> str:
    return "YES" if value else "NO"


def _mean(values: Sequence[int | float]) -> float | None:
    return None if not values else sum(values) / len(values)


def state_record(beam: r1.DestroySetBeam, state: r1.BeamState) -> dict[str, object]:
    portfolio = beam.portfolio_of(state)
    return {
        "REPLACEMENT_TICKETS": _ticket_list(state.tickets),
        "OUTCOMES": SUBSET_SIZE * state.covered,
        "DELTA_VS_START": SUBSET_SIZE * state.covered - START_COUNT,
        "STATE_SHA256": state_sha256(state.tickets),
        "PORTFOLIO_SHA256": portfolio_sha256(portfolio),
        "CANONICAL_RECOUNT": beam.recounts.get(portfolio),
        "PARENT": None if state.parent is None else _ticket_list(state.parent),
        "ADDED_TICKET": None if state.added is None else list(state.added),
        "ADDED_CONDITIONAL_MARGINAL_OUTCOMES": SUBSET_SIZE * state.added_marginal,
        "ADDED_POSITION": state.added_position,
    }


def expansion_record(expansion: r1.Expansion, prior: r1.PriorSet) -> dict[str, object]:
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


def selection_record(selection: TieSelection | None) -> dict[str, object] | None:
    if selection is None:
        return None
    saved = set(selection.saved)
    return {
        "COVERED_OUTCOMES": SUBSET_SIZE * selection.covered,
        "TIE_GROUP_SIZE": selection.group_size,
        "SLOTS": selection.slots,
        "SELECTED_IN_SELECTION_ORDER": [
            {
                "REPLACEMENT_TICKETS": _ticket_list(state),
                "STATE_SHA256": sha,
                "MIN_SIGNATURE_DISTANCE_AT_SELECTION": min_signature,
                "MIN_TICKET_SET_DISTANCE_AT_SELECTION": min_ticket,
                "SAVED_FROM_R1_CUT": state in saved,
            }
            for state, sha, min_signature, min_ticket in zip(
                selection.selected,
                selection.selected_sha256,
                selection.min_signature,
                selection.min_ticket,
                strict=True,
            )
        ],
        "R1_LOWEST_IDENTITY_CUT_WOULD_KEEP": [_ticket_list(s) for s in selection.r1_rule_keeps],
        "SAVED_FROM_R1_CUT": [_ticket_list(s) for s in selection.saved],
        "DROPPED_THAT_R1_CUT_KEEPS": [_ticket_list(s) for s in selection.dropped_that_r1_keeps],
        "PAIR_SIGNATURE_DISTANCES": list(selection.pair_signature),
        "PAIR_TICKET_SET_DISTANCES": list(selection.pair_ticket),
    }


def set_record(dbeam: DiversityBeam, prior: r1.PriorSet) -> dict[str, object]:
    beam = dbeam.beam
    run, best = beam.run, beam.run.best
    ties = run.final_ties()
    start_state = r1.canonical_state(beam.destroyed.removed)
    return {
        "DESTROY_SIZE": beam.size,
        "POSITIONS": list(beam.destroyed.positions),
        "REMOVED_TICKETS": _ticket_list(beam.destroyed.removed),
        "R_SIZE": len(beam.destroyed.remaining),
        "OUTCOMES_WON_BY_FROZEN_R": beam.remaining_count,
        "RETENTION_POLICY": dbeam.policy,
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
        "BEST_REPLACEMENTS_VS_ONE_SHOT": r1.classify_replacements(
            best.tickets, prior, beam.original_ranks
        ),
        "BEST_REQUIRES_TICKET_OUTSIDE_ORIGINAL_GLOBAL_TOP48": _yes_no(
            r1.requires_ticket_outside_top48(best.tickets, prior)
        ),
        "FINAL_BEST_COUNT_TIES": len(ties),
        "FINAL_BEST_COUNT_TIES_CANONICALLY_RECOUNTED": r1.ties_recounted(beam),
        "FINAL_BEST_COUNT_TIES_LISTED": [state_record(beam, s) for s in ties[:LISTED_TIES_MAX]],
        "FINAL_CANDIDATES_INCLUDE_START_REPLACEMENT_SET": any(
            state.tickets == start_state for state in run.final.candidates
        ),
        "PRIOR_ONE_SHOT_POOL_BEST_COUNT": prior.best_count,
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
                "TIE_GROUPS": tie.tie_groups,
                "MAX_TIE_GROUP_SIZE": tie.max_group_size,
                "TIED_STATES_IN_TIE_GROUPS": tie.tied_states,
                "CUTOFF_TIE_GROUP_SIZE": tie.cutoff_group_size,
                "CUTOFF_TIE_GROUP_SLOTS": tie.cutoff_slots,
                "DIVERSITY_SELECTION": selection_record(tie.selection),
                "RETAINED": [state_record(beam, state) for state in level.retained],
            }
            for level, tie in zip(run.levels, dbeam.ties, strict=True)
        ],
        "EXPANSIONS": [expansion_record(expansion, prior) for expansion in run.expansions],
        "SIGNATURE_CHECKS": list(dbeam.signature_checks),
        "SIGNATURES_BUILT": dbeam.signatures_built,
        "SIGNATURE_DISTANCES_TAKEN": dbeam.distances_taken,
        "SECONDS": {name: round(value, 3) for name, value in beam.seconds.items()},
    }


def tie_statistics(dbeams: Sequence[DiversityBeam]) -> dict[str, object]:
    """Tie-group statistics of the scientific beams (the control is not included)."""

    levels = [tie for dbeam in dbeams for tie in dbeam.ties]
    selections = [tie.selection for tie in levels if tie.selection is not None]
    min_signature = [v for s in selections for v in s.min_signature if v is not None]
    min_ticket = [v for s in selections for v in s.min_ticket if v is not None]
    pair_signature = [v for s in selections for v in s.pair_signature]
    pair_ticket = [v for s in selections for v in s.pair_ticket]
    saved = sum(len(s.saved) for s in selections)
    return {
        "TIE_GROUPS_TOTAL": sum(tie.tie_groups for tie in levels),
        "TIE_GROUPS_TOTAL_DEFINITION": (
            "groups of two or more unique candidate states of equal exact coverage, summed over "
            "every level of every scientific destroy-set beam"
        ),
        "MAX_TIE_GROUP_SIZE": max((tie.max_group_size for tie in levels), default=0),
        "TIED_STATES_IN_ALL_TIE_GROUPS": sum(tie.tied_states for tie in levels),
        "TIE_GROUPS_AT_CUTOFF": len(selections),
        "TIED_STATES_CONSIDERED": sum(s.group_size for s in selections),
        "TIED_STATES_CONSIDERED_DEFINITION": (
            "states of the tie groups that straddled a retention cutoff and went through the "
            "diversity selection (one such group at most per level)"
        ),
        "TIED_STATES_RETAINED_BY_DIVERSITY": sum(s.slots for s in selections),
        "TIED_STATES_DROPPED_BY_DIVERSITY": sum(s.group_size - s.slots for s in selections),
        "AVERAGE_COVERAGE_SIGNATURE_DISTANCE": _mean(min_signature),
        "AVERAGE_TICKET_SET_DISTANCE": _mean(min_ticket),
        "AVERAGE_DISTANCE_DEFINITION": (
            "mean, over every state retained by diversity after the first of its group, of its "
            "minimum distance to the already-retained states of the same group at the moment "
            "of its selection; the first (lowest-SHA) state of each group has no distance"
        ),
        "AVERAGE_PAIRWISE_COVERAGE_SIGNATURE_DISTANCE_AMONG_RETAINED": _mean(pair_signature),
        "AVERAGE_PAIRWISE_TICKET_SET_DISTANCE_AMONG_RETAINED": _mean(pair_ticket),
        "DISTANCE_OBSERVATIONS_PER_GROUP_SELECTION": [len(s.selected) - 1 for s in selections],
        "DIVERSITY_SAVED_STATES": saved,
        "DIVERSITY_SAVED_STATES_DEFINITION": (
            "states retained by diversity that R1's lowest-identity cut (coverage descending, then "
            "ascending sorted ticket tuple) would have dropped from the same candidates at the "
            "same width"
        ),
    }


def best_path(beam: r1.DestroySetBeam, state: r1.BeamState) -> tuple[Portfolio, ...]:
    """The recorded provenance chain of a final state, level 1 first."""

    by_level = [{s.tickets: s for s in level.candidates} for level in beam.run.levels]
    path = [state.tickets]
    current = state
    for depth in range(len(by_level) - 1, 0, -1):
        current = by_level[depth - 1][cast(Portfolio, current.parent)]
        path.append(current.tickets)
    return tuple(reversed(path))


def r1_best_path(document: Mapping[str, object]) -> tuple[Portfolio, ...] | None:
    """R1's winning provenance chain from its committed records, or ``None`` if unrecoverable."""

    winner = cast(dict[str, object], document["BEST_DESTROY_SET"])
    key = (winner["DESTROY_SIZE"], tuple(cast(list[int], winner["POSITIONS"])))
    sets = [
        record
        for record in cast(list[dict[str, object]], document["PER_DESTROY_SET"])
        if (record["DESTROY_SIZE"], tuple(cast(list[int], record["POSITIONS"]))) == key
    ]
    if len(sets) != 1:
        return None
    record = sets[0]
    levels = cast(list[dict[str, object]], record["LEVELS"])
    rows = {
        level: {
            _record_tickets(row, "REPLACEMENT_TICKETS"): row
            for row in cast(list[dict[str, object]], levels[level]["RETAINED"])
        }
        for level in range(len(levels))
    }
    final_rows = {
        _record_tickets(row, "REPLACEMENT_TICKETS"): row
        for row in cast(list[dict[str, object]], record["FINAL_BEST_COUNT_TIES_LISTED"])
    }
    best = _record_tickets(document, "BEST_REPLACEMENT_TICKETS")
    row = final_rows.get(best) or rows[len(levels) - 1].get(best)
    if row is None:
        return None
    path = [best]
    for level in range(len(levels) - 2, -1, -1):
        parent = _record_tickets(row, "PARENT")
        row = rows[level].get(parent)
        if row is None:
            return None
        path.append(parent)
    return tuple(reversed(path))


def read_prior_r2(repo_root: Path = REPO_ROOT) -> dict[str, object]:
    """The earlier width-16 R2 result, read-only from its publication commit if it is present."""

    target = f"{PRIOR_R2_PUBLICATION_COMMIT}:{PRIOR_R2_RESULT_PATH}"
    shown = subprocess.run(["git", "show", target], cwd=repo_root, capture_output=True, check=False)
    if shown.returncode != 0:
        return {"AVAILABLE": False, "COMMIT": PRIOR_R2_PUBLICATION_COMMIT}
    document = cast(dict[str, object], json.loads(shown.stdout))
    beam = cast(dict[str, object], document["BEAM_DEFINITION"])
    return {
        "AVAILABLE": True,
        "COMMIT": PRIOR_R2_PUBLICATION_COMMIT,
        "PATH": PRIOR_R2_RESULT_PATH,
        "BLOB_SHA256": hashlib.sha256(shown.stdout).hexdigest(),
        "BEAM_WIDTH": beam["BEAM_WIDTH"],
        "TIE_RETENTION": beam["TIE_RETENTION"],
        "BEST_COUNT": document["BEST_COUNT"],
        "BEST_SHA256": document["BEST_SHA256"],
        "SCIENTIFIC_RESULT": document["SCIENTIFIC_RESULT"],
        "DIFFERENCE_FROM_THIS_VARIANT": (
            "beam width 16 (here 24) and the replacement-ticket-set distance ranked before the "
            "residual-signature distance (here the signature distance is primary); this variant "
            "does not reuse or overwrite that result"
        ),
    }


def verify_preregistration(repo_root: Path = REPO_ROOT) -> dict[str, object]:
    """The frozen rule file must hold this module's rule text and be committed and clean."""

    path = repo_root / PREREGISTRATION_RELATIVE_PATH
    text = path.read_text(encoding="utf-8")
    if RULE_TEXT not in text:
        raise StopConditionError("PREREGISTRATION_RULE_MISMATCH", str(path))

    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=repo_root, capture_output=True, text=True, check=False
        )

    tracked = git("ls-files", "--error-unmatch", PREREGISTRATION_RELATIVE_PATH)
    dirty = git("status", "--porcelain", "--", PREREGISTRATION_RELATIVE_PATH)
    if tracked.returncode != 0 or dirty.stdout.strip():
        raise StopConditionError("PREREGISTRATION_NOT_COMMITTED", str(path))
    commit = git("log", "-1", "--format=%H", "--", PREREGISTRATION_RELATIVE_PATH).stdout.strip()
    return {
        "RULE_SHA256": RULE_SHA256,
        "PREREGISTRATION_PATH": PREREGISTRATION_RELATIVE_PATH,
        "PREREGISTRATION_FILE_SHA256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "PREREGISTRATION_COMMIT": commit,
        "PREREGISTRATION_COMMITTED_AND_CLEAN_BEFORE_EXECUTION": True,
    }


def build_result_document(
    *,
    sets: Mapping[int, Sequence[Sequence[int]]],
    priors: Mapping[r1.SetKey, r1.PriorSet],
    beams: Sequence[DiversityBeam],
    start_record: Mapping[str, object],
    pins: Sequence[Mapping[str, object]],
    r1_document: Mapping[str, object],
    freeze: Mapping[str, object],
    control: Mapping[str, object],
    r1_parity: Mapping[str, object],
    signature_parity: Mapping[str, object],
    pilot_tally: ParityTally,
    prior_r2: Mapping[str, object],
    wall_seconds: float,
    peak_memory: int,
    run_identity: Mapping[str, str],
    module_sha256: str,
    runtime_modules: Mapping[str, str],
    phase_seconds: Mapping[str, float],
    thread_env: Mapping[str, str | None],
) -> dict[str, object]:
    """Assemble the result from one diversity beam per pre-registered destroy set."""

    expected = [(size, tuple(p)) for size in DESTROY_SIZES for p in sets[size]]
    if [(d.beam.size, d.beam.destroyed.positions) for d in beams] != expected:
        raise ValueError("every pilot destroy set needs exactly one beam, in sample order")
    if any(len(d.beam.best_portfolio) != PORTFOLIO_SIZE for d in beams):
        raise ValueError("every pilot beam must end in a 20-ticket portfolio")
    plain = [d.beam for d in beams]
    best = r1.select_global_best(plain)
    prior = priors[(best.beam.size, best.beam.destroyed.positions)]
    best_portfolio = best.beam.portfolio_of(best.state)
    best_recount = best.beam.recount_of(best.state)
    global_ties_recounted = all(
        beam.recounts.get(beam.portfolio_of(state)) == best.count for _, beam, state in best.ties
    )
    recount_pass = (
        best_recount == best.count
        and global_ties_recounted
        and all(r1.ties_recounted(beam) for beam in plain)
    )
    improved = best.count > START_COUNT
    result = RESULT_IMPROVED if improved and recount_pass else RESULT_NO_IMPROVEMENT
    best_dbeam = next(d for d in beams if d.beam is best.beam)

    mine_path = best_path(best.beam, best.state)
    theirs_path = r1_best_path(r1_document)
    r1_winner = cast(dict[str, object], r1_document["BEST_DESTROY_SET"])
    same_set = (best.beam.size, list(best.beam.destroyed.positions)) == (
        r1_winner["DESTROY_SIZE"],
        r1_winner["POSITIONS"],
    )
    r1_final = _record_tickets(r1_document, "BEST_REPLACEMENT_TICKETS")
    if theirs_path is None:
        differs = not same_set or best.state.tickets != r1_final
    else:
        differs = not same_set or mine_path != theirs_path
    saved_by_level: dict[int, set[Portfolio]] = {}
    for tie in best_dbeam.ties:
        if tie.selection is not None:
            saved_by_level[tie.selection.level] = set(tie.selection.saved)
    path_uses_saved = any(
        state in saved_by_level.get(level, set()) for level, state in enumerate(mine_path, start=1)
    )
    r1_winner_set = next(
        record
        for record in cast(list[dict[str, object]], r1_document["PER_DESTROY_SET"])
        if (record["DESTROY_SIZE"], tuple(cast(list[int], record["POSITIONS"])))
        == (best.beam.size, best.beam.destroyed.positions)
    )
    r1_retained: dict[int, set[Portfolio]] = {}
    for level_record in cast(list[dict[str, object]], r1_winner_set["LEVELS"]):
        r1_retained[cast(int, level_record["LEVEL"])] = {
            _record_tickets(row, "REPLACEMENT_TICKETS")
            for row in cast(list[dict[str, object]], level_record["RETAINED"])
        }
    stats = tie_statistics(beams)
    inline_mismatches = pilot_tally.mismatches
    parity_mismatches = (
        cast(int, r1_parity["PARITY_MISMATCHES"])
        + cast(int, signature_parity["PARITY_MISMATCHES"])
        + cast(int, control["PARITY_MISMATCHES"])
        + inline_mismatches
    )
    enumeration_seconds = [e.seconds for d in beams for e in d.beam.run.expansions]
    return {
        "TASK_ID": TASK_ID,
        "VARIANT": VARIANT,
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
        "MERGE": "NO",
        "PRODUCTION_CHANGE": "NONE",
        "RUNTIME_TRANSITION_OCCURRED": "NO",
        "NOT_CLAIMED": list(NOT_CLAIMED),
        "START_COUNT": START_COUNT,
        "START_SHA256": START_SHA256,
        "START_PORTFOLIO": _ticket_list(START_PORTFOLIO),
        "START_REPRODUCTION": dict(start_record),
        "PINNED_ELITES": [dict(pin) for pin in pins],
        "FROZEN_RULE": dict(freeze),
        "FROZEN_RULE_TEXT": RULE_TEXT,
        "R1_REUSE": {
            "IMPLEMENTATION_COMMIT": R1_COMMIT,
            "RESULT_COMMIT": R1_RESULT_COMMIT,
            "RESULT_PATH": r1.RESULT_RELATIVE_PATH,
            "RESULT_FILE_SHA256": R1_RESULT_SHA256,
            "R1_SCIENTIFIC_RESULT": r1_document["SCIENTIFIC_RESULT"],
            "R1_BEST_COUNT": r1_document["BEST_COUNT"],
            "R1_BEST_SHA256": r1_document["BEST_SHA256"],
            "SAME_SIX_DESTROY_SETS": True,
            "CHANGED_MECHANISM": "retention cut only (lowest identity -> deterministic diversity)",
        },
        "PRIOR_R2_WIDTH16_RESULT": dict(prior_r2),
        "DESTROY4_SETS": [list(positions) for positions in sets[4]],
        "DESTROY5_SETS": [list(positions) for positions in sets[5]],
        "BEAM_DEFINITION": {
            "BEAM_WIDTH": BEAM_WIDTH,
            "CHILDREN_PER_STATE": EXPANSION_WIDTH,
            "DEPTH": {"DESTROY4": r1.depth_for(4), "DESTROY5": r1.depth_for(5)},
            "PRIMARY_RANK": "higher exact coverage of R + S",
            "TIE_RETENTION": (
                "lowest-SHA tied state first, then repeated maximin on residual-signature "
                "symmetric difference, then replacement-ticket-set symmetric difference, then "
                "lowest canonical state SHA-256; applied only to the tie group straddling the "
                "cutoff"
            ),
            "EXPANSION": (
                "for every retained partial state S, score all 13,983,816 legal tickets exactly "
                "against R + S and take the 8 legal tickets of largest conditional marginal, ties "
                "to the lexicographically lowest ticket; tickets already in R + S are not legal"
            ),
            "DEDUPLICATION": "children are sets; the first expansion that reaches a set keeps it",
            "PREFILTER": "NONE",
            "RANDOM_TICKET_SAMPLING": "NONE",
        },
        "CONTROL_R1_WIDTH8": dict(control),
        **stats,
        "CONDITIONAL_ENUMERATIONS": sum(d.beam.run.enumerations for d in beams),
        "CONDITIONAL_ENUMERATIONS_WITH_NONEMPTY_S": sum(
            e.conditional for d in beams for e in d.beam.run.expansions
        ),
        "CONDITIONAL_ENUMERATIONS_DEFINITION": (
            "complete ticket-universe scorings in the six scientific beams (one per retained "
            "state per depth, the empty depth-0 state included); control and parity-gate "
            "enumerations are reported separately"
        ),
        "GLOBAL_TICKETS_SCORED": sum(d.beam.run.tickets_scored for d in beams),
        "GLOBAL_TICKET_UNIVERSE_SIZE": TOTAL_TICKETS,
        "CONDITIONAL_ENUMERATION_WALL_SECONDS_MIN": round(min(enumeration_seconds), 3),
        "CONDITIONAL_ENUMERATION_WALL_SECONDS_MAX": round(max(enumeration_seconds), 3),
        "CONDITIONAL_ENUMERATION_WALL_SECONDS_MEAN": round(
            sum(enumeration_seconds) / len(enumeration_seconds), 3
        ),
        "BEAM_STATES_GENERATED": sum(d.beam.run.generated for d in beams),
        "BEAM_STATES_UNIQUE": sum(d.beam.run.unique for d in beams),
        "BEAM_STATES_DUPLICATE": sum(d.beam.run.duplicates for d in beams),
        "BEAM_STATES_RETAINED": sum(d.beam.run.retained for d in beams),
        "PARITY_SAMPLE_COUNT": (
            cast(int, r1_parity["PARITY_SAMPLE_COUNT"])
            + cast(int, signature_parity["PARITY_SAMPLE_COUNT"])
        ),
        "PARITY_MISMATCHES": parity_mismatches,
        "PRE_PILOT_PARITY_MISMATCHES": (
            cast(int, r1_parity["PARITY_MISMATCHES"])
            + cast(int, signature_parity["PARITY_MISMATCHES"])
        ),
        "REAL_CONDITIONAL_MARGINAL_CHECKS": r1_parity["REAL_CONDITIONAL_MARGINAL_CHECKS"],
        "REAL_CONDITIONAL_MARGINAL_MISMATCHES": r1_parity["REAL_CONDITIONAL_MARGINAL_MISMATCHES"],
        "REAL_SIGNATURE_CHECKS": signature_parity["REAL_SIGNATURE_CHECKS"],
        "PARITY": {
            "R1_SCORER_AND_BEAM": dict(r1_parity),
            "RETENTION_AND_SIGNATURE": dict(signature_parity),
        },
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
        "BEST_CANONICAL_RECOUNT_STATUS": "PASS" if recount_pass else "FAIL",
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
            "within a beam: coverage, then the frozen diversity rule; across destroy sets: max "
            "exact count, then lowest normalized portfolio sha256"
        ),
        "BEST_PATH": [_ticket_list(state) for state in mine_path],
        "R1_BEST_PATH": None if theirs_path is None else [_ticket_list(s) for s in theirs_path],
        "R1_BEST_DESTROY_SET": r1_winner,
        "R1_BEST_REPLACEMENT_TICKETS": _ticket_list(r1_final),
        "BEST_PATH_STATES_IN_R1_RETAINED_LISTS": [
            state in r1_retained.get(level, set()) for level, state in enumerate(mine_path, start=1)
        ],
        "BEST_PATH_USES_A_STATE_SAVED_FROM_THE_R1_CUT": _yes_no(path_uses_saved),
        "DID_BEST_PATH_DIFFER_FROM_R1": _yes_no(differs),
        "DID_BEST_PATH_DIFFER_FROM_R1_DEFINITION": (
            "YES when the winning destroy set differs from R1's winner or the winning provenance "
            "chain (partial replacement set per level) differs from R1's recorded winning chain; "
            "if R1's chain is not recoverable the final replacement sets are compared"
        ),
        "DID_DIVERSITY_SAVE_A_STATE_R1_WOULD_DROP": _yes_no(
            cast(int, stats["DIVERSITY_SAVED_STATES"]) > 0
        ),
        "WINNER_REPLACEMENTS_VS_ONE_SHOT": r1.classify_replacements(
            best.state.tickets, prior, best.beam.original_ranks
        ),
        "DID_WINNER_REQUIRE_TICKET_OUTSIDE_ORIGINAL_GLOBAL_TOP48": _yes_no(
            r1.requires_ticket_outside_top48(best.state.tickets, prior)
        ),
        "WALL_SECONDS": round(wall_seconds, 3),
        "PHASE_SECONDS": {name: round(seconds, 3) for name, seconds in phase_seconds.items()},
        "PEAK_MEMORY_BYTES": peak_memory,
        "PEAK_MEMORY_DEFINITION": "ru_maxrss of the single pilot process (one worker, no children)",
        "CPU_POLICY": {"PROCESSES": 1, "THREAD_ENV": dict(thread_env)},
        "PER_DESTROY_SET": [
            set_record(d, priors[(d.beam.size, d.beam.destroyed.positions)]) for d in beams
        ],
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
    """The files the four research modules loaded from; all must sit in this checkout's ``src``."""

    source_root = (repo_root / "src").resolve()
    files = {
        name: str(Path(module.__file__ or "").resolve())
        for name, module in (
            ("DIVERSITY_BEAM", sys.modules[__name__]),
            ("CONDITIONAL_BEAM_R1", r1),
            ("GLOBAL_RESIDUAL_POOL", global_pool),
            ("FIVE_TICKET_REPAIR", five_ticket),
        )
    }
    if any(not Path(path).is_relative_to(source_root) for path in files.values()):
        raise StopConditionError("RUNTIME_MODULE_RESOLUTION_MISMATCH", json.dumps(files))
    return files


def _gate(r1_parity: Mapping[str, object], signature_parity: Mapping[str, object]) -> None:
    """Parity must be zero-mismatch with the packet's coverage before any beam is scored."""

    if (
        cast(int, r1_parity["PARITY_MISMATCHES"]) != 0
        or cast(int, signature_parity["PARITY_MISMATCHES"]) != 0
        or not r1_parity["COVERAGE_MEETS_PACKET_MINIMUM"]
        or not signature_parity["COVERAGE_MEETS_MINIMUM"]
    ):
        raise StopConditionError(
            "PARITY_MISMATCH", "pre-pilot parity failed; the pilot must not score"
        )


def run_pilot(workdir: Path, output: Path) -> dict[str, object]:
    """Bind the sets, reproduce the start, pass parity and control, run six beams, write JSON."""

    wall_started = time.perf_counter()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    workdir.mkdir(parents=True, exist_ok=True)
    modules = runtime_module_files()
    identity = _git_identity()
    if identity["RUN_TRACKED_TREE_CLEAN"] != "YES":
        raise StopConditionError("RUN_TREE_DIRTY", "the tracked tree must be clean before the run")
    freeze = verify_preregistration()
    r1_document, _ = read_r1_result()
    universe = build_universe()
    canonical = CanonicalRecounter()
    recounter = r1.CachedRecounter(canonical)
    phase_started = time.perf_counter()
    start_record = reproduce_start(canonical)
    pins = verify_pins(canonical)
    reuse = r1.read_reuse_artifact()
    sets, priors = r1.load_prior_sets(reuse)
    record_progress(
        workdir,
        {
            "EVENT": "BOUND",
            "VARIANT": VARIANT,
            "START": start_record["CANONICAL_RECOUNT"],
            "RULE_SHA256": RULE_SHA256,
            "RUN_HEAD": identity["RUN_HEAD"],
            "SETS": {str(size): [list(p) for p in group] for size, group in sets.items()},
        },
    )
    r1_parity = r1.run_parity(universe, recounter)
    signature_parity = run_signature_parity(universe, recounter)
    parity_done = time.perf_counter()
    record_progress(
        workdir,
        {
            "EVENT": "PARITY_DONE",
            "COMPARISONS": cast(int, r1_parity["PARITY_SAMPLE_COUNT"])
            + cast(int, signature_parity["PARITY_SAMPLE_COUNT"]),
            "MISMATCHES": cast(int, r1_parity["PARITY_MISMATCHES"])
            + cast(int, signature_parity["PARITY_MISMATCHES"]),
            "REAL_CONDITIONAL_MARGINAL_CHECKS": r1_parity["REAL_CONDITIONAL_MARGINAL_CHECKS"],
            "REAL_SIGNATURE_CHECKS": signature_parity["REAL_SIGNATURE_CHECKS"],
        },
    )
    _gate(r1_parity, signature_parity)
    control_tally = ParityTally()
    _, control = run_control(universe, recounter, priors, r1_document, control_tally)
    control["PARITY_MISMATCHES"] = control_tally.mismatches
    control["INLINE_CHECKS"] = control_tally.detail()
    control_done = time.perf_counter()
    record_progress(
        workdir,
        {
            "EVENT": "CONTROL_DONE",
            "STATUS": control["STATUS"],
            "BEST_COUNT": control["BEST_COUNT"],
            "BEST_PORTFOLIO_SHA256": control["BEST_PORTFOLIO_SHA256"],
            "MISMATCHES": control_tally.mismatches,
        },
    )
    tally = ParityTally()
    beams: list[DiversityBeam] = []
    for size in DESTROY_SIZES:
        for positions in sets[size]:
            try:
                dbeam = diversity_destroy_set(
                    universe,
                    size,
                    positions,
                    recounter=recounter,
                    tally=tally,
                    prior=priors[(size, positions)],
                    policy=POLICY_DIVERSITY,
                    beam_width=BEAM_WIDTH,
                )
            except MemoryError as error:
                raise StopConditionError("GLOBAL_ENUMERATION_NOT_FEASIBLE", str(error)) from error
            beams.append(dbeam)
            record_progress(
                workdir,
                {
                    "EVENT": "DESTROY_SET_DONE",
                    "DESTROY_SIZE": size,
                    "POSITIONS": list(positions),
                    "ENUMERATIONS": dbeam.beam.run.enumerations,
                    "BEST_COUNT": dbeam.beam.best_count,
                    "BEST_DELTA": dbeam.beam.best_count - START_COUNT,
                    "FINAL_TIES": len(dbeam.beam.run.final_ties()),
                    "DIVERSITY_GROUPS": sum(t.selection is not None for t in dbeam.ties),
                    "SECONDS": round(dbeam.beam.seconds["TOTAL"], 1),
                },
            )
    pilot_done = time.perf_counter()
    document = build_result_document(
        sets=sets,
        priors=priors,
        beams=beams,
        start_record=start_record,
        pins=pins,
        r1_document=r1_document,
        freeze=freeze,
        control=control,
        r1_parity=r1_parity,
        signature_parity=signature_parity,
        pilot_tally=tally,
        prior_r2=read_prior_r2(),
        wall_seconds=time.perf_counter() - wall_started,
        peak_memory=peak_memory_bytes(),
        run_identity=identity,
        module_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        runtime_modules=modules,
        phase_seconds={
            "START_AND_PARITY": parity_done - phase_started,
            "CONTROL": control_done - parity_done,
            "PILOT": pilot_done - control_done,
        },
        thread_env={key: os.environ.get(key) for key in THREAD_ENV_KEYS},
    )
    write_atomically(output, canonical_json(document))
    record_progress(workdir, {"EVENT": "RESULT_WRITTEN", "PATH": str(output)})
    return document


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="b649_k20_conditional_global_diversity_beam_r2_w24", description=__doc__
    )
    commands = parser.add_subparsers(dest="command", required=True)
    pilot = commands.add_parser("pilot", help="run parity, control, then the six beams; write JSON")
    pilot.add_argument("--workdir", type=Path, required=True)
    pilot.add_argument("--output", type=Path, required=True)
    commands.add_parser("parity", help="run only the pre-pilot parity checks")
    commands.add_parser("control", help="run only the width-8 R1 control")
    args = parser.parse_args(argv)
    try:
        if args.command == "pilot":
            document = run_pilot(args.workdir, args.output)
            print(
                f"result={document['SCIENTIFIC_RESULT']} best_count={document['BEST_COUNT']} "
                f"delta={document['BEST_DELTA']} parity_mismatches={document['PARITY_MISMATCHES']} "
                f"wall_seconds={document['WALL_SECONDS']}",
                flush=True,
            )
            return 0
        universe = build_universe()
        recounter = r1.CachedRecounter(CanonicalRecounter())
        if args.command == "parity":
            r1_parity = r1.run_parity(universe, recounter)
            signature_parity = run_signature_parity(universe, recounter)
            print(canonical_json({"R1": r1_parity, "SIGNATURE": signature_parity}))
            clean = (
                r1_parity["PARITY_MISMATCHES"] == 0 and signature_parity["PARITY_MISMATCHES"] == 0
            )
            return 0 if clean else 1
        document, _ = read_r1_result()
        _, priors = r1.load_prior_sets(r1.read_reuse_artifact())
        tally = ParityTally()
        _, record = run_control(universe, recounter, priors, document, tally)
        print(canonical_json({**record, "INLINE_CHECKS": tally.detail()}))
        return 0
    except StopConditionError as stop:
        print(f"STOP: {stop}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
