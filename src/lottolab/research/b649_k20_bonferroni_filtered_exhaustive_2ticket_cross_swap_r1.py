"""Exhaustive K20 two-ticket cross-swaps with a safe third-order bound.

The incumbent is loaded from its pinned Git object. Candidate portfolios are
held fixed to that origin throughout the sweep. U3 is an upper bound used only
to reject candidates; every survivor is scored by the canonical exact arbiter.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import subprocess
import tempfile
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from math import comb
from pathlib import Path
from typing import cast

from lottolab.research.b649_official_any_prize_exact import (
    BIG_LOTTO_DRAW_SIZE,
    BIG_LOTTO_OUTRIGHT_MATCHES,
    BIG_LOTTO_POOL_SIZE,
    DrawMasks,
    ExactPortfolioProbability,
    all_main_draw_masks,
    evaluate_portfolio,
)

type Ticket = tuple[int, ...]
type Portfolio = tuple[Ticket, ...]

TASK_ID = "B649_K20_BONFERRONI_FILTERED_EXHAUSTIVE_2TICKET_CROSS_SWAP_R1"
EXECUTION_ID = "B649_K20_2TICKET_CROSS_SWAP_LOCAL_R1"
SEARCH_DEFINITION_VERSION = "b649-two-ticket-cross-swap-u3-v1"
INCUMBENT_SOURCE_COMMIT = "03fadab9d88ad83372e45f19b6c5097e9132c1f1"
INCUMBENT_SOURCE_PATH = (
    "docs/research/matrix-native-results/"
    "b649-sealed-v2-direct-official-any-prize-k20-terminal-r1.json"
)
EXPECTED_INCUMBENT_FRACTION = "7448829/14316764"
EXPECTED_INCUMBENT_OUTCOME_COUNT = 312_850_818
EXPECTED_TOTAL_OUTCOMES = 601_304_088
TOTAL_OFFICIAL_OUTCOMES = comb(BIG_LOTTO_POOL_SIZE, BIG_LOTTO_DRAW_SIZE) * (
    BIG_LOTTO_POOL_SIZE - BIG_LOTTO_DRAW_SIZE
)


@dataclass(frozen=True, slots=True)
class Incumbent:
    portfolio: Portfolio
    portfolio_sha256: str
    exact_fraction: str
    outcome_count: int
    source_commit: str
    source_path: str
    method: str


@dataclass(frozen=True, slots=True)
class CrossSwapMove:
    pair_index: int
    move_index: int
    ticket_a_index: int
    ticket_b_index: int
    number_from_a: int
    number_from_b: int


@dataclass(frozen=True, slots=True)
class CrossSwapCandidate:
    portfolio: Portfolio
    old_changed_tickets: tuple[Ticket, Ticket]
    new_changed_tickets: tuple[Ticket, Ticket]


@dataclass(frozen=True, slots=True)
class U3Components:
    s1: int
    s2: int
    s3: int

    @property
    def u3(self) -> int:
        return self.s1 - self.s2 + self.s3


@dataclass(frozen=True, slots=True)
class ExactCandidateRecord:
    portfolio: Portfolio
    portfolio_sha256: str
    u3_outcome_count: int
    exact_outcome_count: int
    exact_fraction: str
    delta_outcomes: int


@dataclass(slots=True)
class SweepState:
    task_id: str
    search_definition_version: str
    incumbent_sha256: str
    incumbent_outcome_count: int
    ticket_pair_index: int
    move_index: int
    raw_move_count: int
    illegal_move_count: int
    legal_move_count: int
    duplicate_result_count: int
    unique_legal_portfolio_count: int
    bonferroni_pruned_count: int
    survivor_count: int
    exact_scored_count: int
    seen_portfolio_hashes: set[str]
    exact_records: list[ExactCandidateRecord]
    best_exact_count: int
    best_portfolio_sha256: str
    best_portfolio: Portfolio
    audit_digest: str
    complete: bool = False


class PortfolioDeduplicator:
    """Deduplicate portfolios by the same canonical bytes used by the seal."""

    def __init__(self, hashes: Iterable[str] = ()) -> None:
        self._hashes = set(hashes)

    def add(self, portfolio: Sequence[Sequence[int]]) -> bool:
        """Return true once for each normalized portfolio identity."""

        digest = portfolio_sha256(portfolio)
        if digest in self._hashes:
            return False
        self._hashes.add(digest)
        return True

    @property
    def hashes(self) -> set[str]:
        return set(self._hashes)


def normalize_portfolio(
    portfolio: Sequence[Sequence[int]], *, expected_ticket_count: int | None = None
) -> Portfolio:
    """Validate and canonicalize a portfolio for equality and hashing."""

    if expected_ticket_count is not None and len(portfolio) != expected_ticket_count:
        raise ValueError(f"portfolio must contain exactly {expected_ticket_count} tickets")
    normalized_tickets: list[Ticket] = []
    for raw_ticket in portfolio:
        if len(raw_ticket) != BIG_LOTTO_DRAW_SIZE:
            raise ValueError("every ticket must contain exactly six numbers")
        if any(type(number) is not int for number in raw_ticket):
            raise ValueError("ticket numbers must be integers")
        ticket = tuple(sorted(raw_ticket))
        if len(set(ticket)) != BIG_LOTTO_DRAW_SIZE:
            raise ValueError("a ticket cannot contain duplicate numbers")
        if any(not 1 <= number <= BIG_LOTTO_POOL_SIZE for number in ticket):
            raise ValueError("ticket numbers must be within 1..49")
        normalized_tickets.append(ticket)
    if len(set(normalized_tickets)) != len(normalized_tickets):
        raise ValueError("a portfolio cannot contain duplicate tickets")
    return tuple(sorted(normalized_tickets))


def _ticket_mask(ticket: Sequence[int]) -> int:
    mask = 0
    for number in ticket:
        mask |= 1 << (number - 1)
    return mask


def canonical_portfolio_bytes(portfolio: Sequence[Sequence[int]]) -> bytes:
    normalized = normalize_portfolio(portfolio)
    return json.dumps(normalized, separators=(",", ":")).encode("utf-8")


def portfolio_sha256(portfolio: Sequence[Sequence[int]]) -> str:
    return hashlib.sha256(canonical_portfolio_bytes(portfolio)).hexdigest()


def load_pinned_incumbent(
    repository: Path,
    *,
    source_commit: str = INCUMBENT_SOURCE_COMMIT,
    source_path: str = INCUMBENT_SOURCE_PATH,
) -> Incumbent:
    """Read and validate the incumbent directly from the pinned Git object."""

    if source_commit != INCUMBENT_SOURCE_COMMIT or source_path != INCUMBENT_SOURCE_PATH:
        raise ValueError("incumbent locator differs from the authorized pinned source")
    commit = subprocess.run(
        ["git", "-C", str(repository), "cat-file", "-e", f"{source_commit}^{{commit}}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if commit.returncode != 0:
        raise ValueError("pinned incumbent commit is unavailable")
    artifact_object = f"{source_commit}:{source_path}"
    artifact_check = subprocess.run(
        ["git", "-C", str(repository), "cat-file", "-e", artifact_object],
        check=False,
        capture_output=True,
        text=True,
    )
    if artifact_check.returncode != 0:
        raise ValueError("pinned incumbent artifact is unavailable")
    raw = subprocess.run(
        ["git", "-C", str(repository), "show", artifact_object],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    artifact = json.loads(raw)
    if artifact.get("SCIENTIFIC_OBJECTIVE") != "OFFICIAL_ANY_PRIZE":
        raise ValueError("pinned incumbent objective is not OFFICIAL_ANY_PRIZE")
    portfolio = normalize_portfolio(artifact["TERMINAL_TICKETS"], expected_ticket_count=20)
    fraction_text = artifact["TERMINAL_K20_EXACT_PROBABILITY"]
    outcome_count = artifact["TERMINAL_K20_OUTCOME_COUNT"]
    expected_sha = artifact["TERMINAL_K20_PORTFOLIO_SHA256"]
    total = comb(BIG_LOTTO_POOL_SIZE, BIG_LOTTO_DRAW_SIZE) * (
        BIG_LOTTO_POOL_SIZE - BIG_LOTTO_DRAW_SIZE
    )
    if type(outcome_count) is not int or type(expected_sha) is not str:
        raise ValueError("pinned incumbent outcome fields have invalid types")
    if fraction_text != EXPECTED_INCUMBENT_FRACTION:
        raise ValueError("pinned incumbent exact fraction disagrees with the task packet")
    if outcome_count != EXPECTED_INCUMBENT_OUTCOME_COUNT or total != EXPECTED_TOTAL_OUTCOMES:
        raise ValueError("pinned incumbent outcome counts disagree with the task packet")
    if Fraction(outcome_count, total) != Fraction(fraction_text):
        raise ValueError("pinned incumbent fraction does not match its exact counts")
    if outcome_count != 7_448_829 * 42 or total != 14_316_764 * 42:
        raise ValueError("pinned incumbent arithmetic identity failed")
    actual_sha = portfolio_sha256(portfolio)
    if actual_sha != expected_sha:
        raise ValueError("pinned incumbent portfolio SHA-256 mismatch")
    return Incumbent(
        portfolio=portfolio,
        portfolio_sha256=actual_sha,
        exact_fraction=fraction_text,
        outcome_count=outcome_count,
        source_commit=source_commit,
        source_path=source_path,
        method=artifact["INCUMBENT_METHOD_ID"],
    )


def generate_move_groups(
    portfolio: Sequence[Sequence[int]],
) -> tuple[tuple[CrossSwapMove, ...], ...]:
    """Generate every legal-form cross-swap identity in canonical pair order."""

    origin = normalize_portfolio(portfolio)
    groups: list[tuple[CrossSwapMove, ...]] = []
    for pair_index, (ticket_a_index, ticket_b_index) in enumerate(
        itertools.combinations(range(len(origin)), 2)
    ):
        ticket_a = origin[ticket_a_index]
        ticket_b = origin[ticket_b_index]
        numbers_a = sorted(set(ticket_a) - set(ticket_b))
        numbers_b = sorted(set(ticket_b) - set(ticket_a))
        moves = tuple(
            CrossSwapMove(
                pair_index=pair_index,
                move_index=move_index,
                ticket_a_index=ticket_a_index,
                ticket_b_index=ticket_b_index,
                number_from_a=number_from_a,
                number_from_b=number_from_b,
            )
            for move_index, (number_from_a, number_from_b) in enumerate(
                itertools.product(numbers_a, numbers_b)
            )
        )
        groups.append(moves)
    return tuple(groups)


def move_count(portfolio: Sequence[Sequence[int]]) -> int:
    return sum(map(len, generate_move_groups(portfolio)))


def apply_cross_swap(portfolio: Sequence[Sequence[int]], move: CrossSwapMove) -> CrossSwapCandidate:
    """Apply one move and reject all portfolio-level legality violations."""

    origin = normalize_portfolio(portfolio)
    if not 0 <= move.ticket_a_index < len(origin) or not 0 <= move.ticket_b_index < len(origin):
        raise ValueError("cross-swap ticket index is outside the portfolio")
    if move.ticket_a_index >= move.ticket_b_index:
        raise ValueError("cross-swap pair must be an unordered ascending pair")
    old_a = origin[move.ticket_a_index]
    old_b = origin[move.ticket_b_index]
    if move.number_from_a not in old_a or move.number_from_a in old_b:
        raise ValueError("removed number from ticket A must be in A and absent from B")
    if move.number_from_b not in old_b or move.number_from_b in old_a:
        raise ValueError("removed number from ticket B must be in B and absent from A")
    new_a = tuple(sorted((set(old_a) - {move.number_from_a}) | {move.number_from_b}))
    new_b = tuple(sorted((set(old_b) - {move.number_from_b}) | {move.number_from_a}))
    updated = list(origin)
    updated[move.ticket_a_index] = new_a
    updated[move.ticket_b_index] = new_b
    candidate = normalize_portfolio(updated, expected_ticket_count=len(origin))
    return CrossSwapCandidate(
        portfolio=candidate,
        old_changed_tickets=(old_a, old_b),
        new_changed_tickets=(new_a, new_b),
    )


def _allocation_vectors(
    atom_sizes: tuple[int, ...], draw_size: int
) -> Iterator[tuple[tuple[int, ...], int]]:
    counts = [0] * len(atom_sizes)

    def visit(index: int, remaining: int, weight: int) -> Iterator[tuple[tuple[int, ...], int]]:
        if index == len(atom_sizes) - 1:
            if remaining <= atom_sizes[index]:
                counts[index] = remaining
                yield tuple(counts), weight * comb(atom_sizes[index], remaining)
            return
        for selected in range(min(atom_sizes[index], remaining) + 1):
            counts[index] = selected
            yield from visit(
                index + 1,
                remaining - selected,
                weight * comb(atom_sizes[index], selected),
            )

    yield from visit(0, draw_size, 1)


def _event_intersection_for_atoms(
    atom_sizes: tuple[int, ...],
    ticket_count: int,
    pair_overlaps: tuple[int, ...],
    triple_overlap: int,
) -> int:
    total = 0
    for selected_by_atom, draw_multiplicity in _allocation_vectors(atom_sizes, BIG_LOTTO_DRAW_SIZE):
        hits = [0] * ticket_count
        for atom_mask, selected in enumerate(selected_by_atom):
            for ticket_index in range(ticket_count):
                if atom_mask & (1 << ticket_index):
                    hits[ticket_index] += selected
        if min(hits) < BIG_LOTTO_OUTRIGHT_MATCHES - 1:
            continue
        if min(hits) >= BIG_LOTTO_OUTRIGHT_MATCHES:
            total += draw_multiplicity * (BIG_LOTTO_POOL_SIZE - BIG_LOTTO_DRAW_SIZE)
            continue
        exact_two = tuple(index for index, hit_count in enumerate(hits) if hit_count == 2)
        required_mask = sum(1 << index for index in exact_two)
        selected_intersection = sum(
            selected
            for atom_mask, selected in enumerate(selected_by_atom)
            if required_mask & atom_mask == required_mask
        )
        if len(exact_two) == 1:
            intersection_size = BIG_LOTTO_DRAW_SIZE
        elif len(exact_two) == 2:
            pair_index = {(0, 1): 0, (0, 2): 1, (1, 2): 2}[exact_two]
            intersection_size = pair_overlaps[pair_index]
        elif len(exact_two) == 3:
            intersection_size = triple_overlap
        else:
            raise AssertionError("unexpected exact-two event geometry")
        special_intersection = intersection_size - selected_intersection
        if special_intersection < 0:
            raise AssertionError("selected draw exceeds a ticket intersection")
        total += draw_multiplicity * special_intersection
    return total


@cache
def _single_ticket_event_count() -> int:
    return sum(
        comb(BIG_LOTTO_DRAW_SIZE, hits)
        * comb(BIG_LOTTO_POOL_SIZE - BIG_LOTTO_DRAW_SIZE, BIG_LOTTO_DRAW_SIZE - hits)
        * (
            BIG_LOTTO_POOL_SIZE - BIG_LOTTO_DRAW_SIZE
            if hits >= BIG_LOTTO_OUTRIGHT_MATCHES
            else BIG_LOTTO_DRAW_SIZE - hits
            if hits == BIG_LOTTO_OUTRIGHT_MATCHES - 1
            else 0
        )
        for hits in range(BIG_LOTTO_DRAW_SIZE + 1)
    )


@cache
def _pair_event_intersection(overlap: int) -> int:
    if not 0 <= overlap <= BIG_LOTTO_DRAW_SIZE:
        raise ValueError("ticket overlap must be within 0..6")
    atom_sizes = (
        BIG_LOTTO_POOL_SIZE - 2 * BIG_LOTTO_DRAW_SIZE + overlap,
        BIG_LOTTO_DRAW_SIZE - overlap,
        BIG_LOTTO_DRAW_SIZE - overlap,
        overlap,
    )
    return _event_intersection_for_atoms(atom_sizes, 2, (overlap, 0, 0), 0)


@cache
def _triple_event_intersection(
    overlap_ab: int, overlap_ac: int, overlap_bc: int, triple_overlap: int
) -> int:
    cell_sizes = {
        0: BIG_LOTTO_POOL_SIZE
        - 3 * BIG_LOTTO_DRAW_SIZE
        + overlap_ab
        + overlap_ac
        + overlap_bc
        - triple_overlap,
        1: BIG_LOTTO_DRAW_SIZE - overlap_ab - overlap_ac + triple_overlap,
        2: BIG_LOTTO_DRAW_SIZE - overlap_ab - overlap_bc + triple_overlap,
        3: overlap_ab - triple_overlap,
        4: BIG_LOTTO_DRAW_SIZE - overlap_ac - overlap_bc + triple_overlap,
        5: overlap_ac - triple_overlap,
        6: overlap_bc - triple_overlap,
        7: triple_overlap,
    }
    if min(cell_sizes.values()) < 0 or sum(cell_sizes.values()) != BIG_LOTTO_POOL_SIZE:
        raise ValueError("infeasible three-ticket overlap geometry")
    pair_overlaps = (overlap_ab, overlap_ac, overlap_bc)
    return _event_intersection_for_atoms(
        tuple(cell_sizes[index] for index in range(8)), 3, pair_overlaps, triple_overlap
    )


def _event_intersection_for_masks(ticket_masks: tuple[int, ...]) -> int:
    if not 1 <= len(ticket_masks) <= 3:
        raise ValueError("event intersections are defined for one to three tickets")
    if len(ticket_masks) == 1:
        return _single_ticket_event_count()
    if len(ticket_masks) == 2:
        return _pair_event_intersection((ticket_masks[0] & ticket_masks[1]).bit_count())
    first, second, third = ticket_masks
    return _triple_event_intersection(
        (first & second).bit_count(),
        (first & third).bit_count(),
        (second & third).bit_count(),
        (first & second & third).bit_count(),
    )


def event_intersection_count(tickets: Sequence[Sequence[int]]) -> int:
    """Count official outcomes in the intersection of one, two, or three events."""

    if not 1 <= len(tickets) <= 3:
        raise ValueError("event intersections are defined for one to three tickets")
    normalized = normalize_portfolio(tickets)
    return _event_intersection_for_masks(tuple(_ticket_mask(ticket) for ticket in normalized))


def full_u3_components(portfolio: Sequence[Sequence[int]]) -> U3Components:
    """Recompute S1, S2, and S3 from scratch using exact event intersections."""

    normalized = normalize_portfolio(portfolio)
    masks = tuple(_ticket_mask(ticket) for ticket in normalized)
    s1 = len(normalized) * _single_ticket_event_count()
    s2 = sum(_event_intersection_for_masks(pair) for pair in itertools.combinations(masks, 2))
    s3 = sum(_event_intersection_for_masks(triple) for triple in itertools.combinations(masks, 3))
    return U3Components(s1=s1, s2=s2, s3=s3)


def _affected_indices(
    ticket_count: int, changed: frozenset[int], order: int
) -> Iterator[tuple[int, ...]]:
    for indices in itertools.combinations(range(ticket_count), order):
        if changed.intersection(indices):
            yield indices


def _affected_sum(portfolio: Portfolio, changed_indices: frozenset[int], order: int) -> int:
    masks = tuple(_ticket_mask(ticket) for ticket in portfolio)
    return sum(
        _event_intersection_for_masks(tuple(masks[index] for index in indices))
        for indices in _affected_indices(len(portfolio), changed_indices, order)
    )


def incremental_u3_components(
    old_portfolio: Sequence[Sequence[int]],
    new_portfolio: Sequence[Sequence[int]],
    old_components: U3Components,
    old_changed_tickets: Sequence[Sequence[int]],
    new_changed_tickets: Sequence[Sequence[int]],
) -> U3Components:
    """Update affected terms as old total minus old terms plus new terms."""

    old = normalize_portfolio(old_portfolio)
    new = normalize_portfolio(new_portfolio, expected_ticket_count=len(old))
    old_indices = frozenset(old.index(tuple(sorted(ticket))) for ticket in old_changed_tickets)
    new_indices = frozenset(new.index(tuple(sorted(ticket))) for ticket in new_changed_tickets)
    if len(old_indices) != 2 or len(new_indices) != 2:
        raise ValueError("exactly two distinct tickets must change")
    s1 = old_components.s1 - _affected_sum(old, old_indices, 1) + _affected_sum(new, new_indices, 1)
    s2 = old_components.s2 - _affected_sum(old, old_indices, 2) + _affected_sum(new, new_indices, 2)
    s3 = old_components.s3 - _affected_sum(old, old_indices, 3) + _affected_sum(new, new_indices, 3)
    return U3Components(s1=s1, s2=s2, s3=s3)


def _changed_pair_overlap_directions(
    origin: Portfolio, candidate: CrossSwapCandidate
) -> tuple[bool, bool]:
    changed_old = set(candidate.old_changed_tickets)
    unaffected = tuple(ticket for ticket in origin if ticket not in changed_old)
    increases = False
    decreases = False
    for old_ticket, new_ticket in zip(
        candidate.old_changed_tickets, candidate.new_changed_tickets, strict=True
    ):
        for other in unaffected:
            old_overlap = len(set(old_ticket) & set(other))
            new_overlap = len(set(new_ticket) & set(other))
            increases |= new_overlap > old_overlap
            decreases |= new_overlap < old_overlap
    return increases, decreases


def _portfolio_candidate_for_move(
    origin: Portfolio, move: CrossSwapMove
) -> CrossSwapCandidate | None:
    try:
        return apply_cross_swap(origin, move)
    except ValueError:
        return None


def select_bound_fixtures(incumbent: Portfolio) -> dict[str, CrossSwapCandidate]:
    """Select deterministic legal moves covering the required fixture classes."""

    origin = normalize_portfolio(incumbent, expected_ticket_count=20)
    base_components = full_u3_components(origin)
    selected: dict[str, CrossSwapCandidate] = {}
    for group in generate_move_groups(origin):
        for move in group:
            candidate = _portfolio_candidate_for_move(origin, move)
            if candidate is None:
                continue
            pair = (origin[move.ticket_a_index], origin[move.ticket_b_index])
            pair_overlap = len(set(pair[0]) & set(pair[1]))
            if pair_overlap == 0:
                selected.setdefault("DISJOINT_PAIR", candidate)
            else:
                selected.setdefault("OVERLAPPING_PAIR", candidate)
            overlap_increases, overlap_decreases = _changed_pair_overlap_directions(
                origin, candidate
            )
            if overlap_increases:
                selected.setdefault("INCREASED_PAIR_OVERLAP", candidate)
            if overlap_decreases:
                selected.setdefault("DECREASED_PAIR_OVERLAP", candidate)
            incremental = incremental_u3_components(
                origin,
                candidate.portfolio,
                base_components,
                candidate.old_changed_tickets,
                candidate.new_changed_tickets,
            )
            full = full_u3_components(candidate.portfolio)
            if incremental != full:
                raise AssertionError("incremental U3 differs from full U3 on a bound fixture")
            if incremental.s3 != base_components.s3:
                selected.setdefault("CHANGED_TRIPLE_INTERSECTIONS", candidate)
            if len(selected) == 5:
                break
        if len(selected) == 5:
            break
    required_labels = {
        "DISJOINT_PAIR",
        "OVERLAPPING_PAIR",
        "INCREASED_PAIR_OVERLAP",
        "DECREASED_PAIR_OVERLAP",
        "CHANGED_TRIPLE_INTERSECTIONS",
    }
    if set(selected) != required_labels:
        missing = sorted(required_labels - set(selected))
        raise AssertionError(f"required bound fixture classes missing: {missing}")
    return selected


def validate_bound_fixtures(
    incumbent: Portfolio,
    *,
    draws: DrawMasks | None = None,
    exact_scorer: Callable[[Portfolio], ExactPortfolioProbability] | None = None,
    known_incumbent_exact: ExactPortfolioProbability | None = None,
) -> tuple[str, ...]:
    """Check required fixture classes before incremental pruning is trusted."""

    origin = normalize_portfolio(incumbent, expected_ticket_count=20)

    def canonical_scorer(candidate: Portfolio) -> ExactPortfolioProbability:
        return evaluate_portfolio(candidate, draws=draws)

    scorer = exact_scorer if exact_scorer is not None else canonical_scorer
    base_components = full_u3_components(origin)
    selected = select_bound_fixtures(origin)

    fixture_hashes = {portfolio_sha256(candidate.portfolio) for candidate in selected.values()}
    special_sensitive_verified = False
    if known_incumbent_exact is not None:
        base_u3 = base_components.u3
        if base_u3 < known_incumbent_exact.official_any_prize_outcome_count:
            raise AssertionError("incumbent U3 is below its canonical exact outcome count")
    unique_candidates = {
        portfolio_sha256(candidate.portfolio): candidate for candidate in selected.values()
    }
    for digest, candidate in unique_candidates.items():
        exact = scorer(candidate.portfolio)
        components = full_u3_components(candidate.portfolio)
        if components.u3 < exact.official_any_prize_outcome_count:
            raise AssertionError(f"U3 is below canonical exact count for fixture {digest}")
        if exact.official_any_prize_outcome_count > (
            exact.m3_plus_draw_count * (BIG_LOTTO_POOL_SIZE - BIG_LOTTO_DRAW_SIZE)
        ):
            special_sensitive_verified = True
    if not special_sensitive_verified:
        raise AssertionError("no validated fixture exercised special-number rescue outcomes")
    return tuple(sorted(fixture_hashes))


def _initial_audit_digest(incumbent_sha256: str, outcome_count: int) -> str:
    seed = f"{SEARCH_DEFINITION_VERSION}:{incumbent_sha256}:{outcome_count}".encode("ascii")
    return hashlib.sha256(seed).hexdigest()


def _advance_audit_digest(previous: str, record: dict[str, object]) -> str:
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(bytes.fromhex(previous) + canonical).hexdigest()


def should_safe_prune(u3_outcome_count: int, incumbent_outcome_count: int) -> bool:
    """Return true only for the packet's safe upper-bound rejection condition."""

    return u3_outcome_count <= incumbent_outcome_count


def _record_to_json(record: ExactCandidateRecord) -> dict[str, object]:
    return {
        "portfolio": record.portfolio,
        "portfolio_sha256": record.portfolio_sha256,
        "u3_outcome_count": record.u3_outcome_count,
        "exact_outcome_count": record.exact_outcome_count,
        "exact_fraction": record.exact_fraction,
        "delta_outcomes": record.delta_outcomes,
    }


def _state_to_json(state: SweepState) -> dict[str, object]:
    return {
        "schema_version": 1,
        "task_id": state.task_id,
        "incumbent_sha256": state.incumbent_sha256,
        "incumbent_outcome_count": state.incumbent_outcome_count,
        "search_definition_version": state.search_definition_version,
        "ticket_pair_index": state.ticket_pair_index,
        "move_index": state.move_index,
        "raw_move_count": state.raw_move_count,
        "illegal_move_count": state.illegal_move_count,
        "legal_move_count": state.legal_move_count,
        "duplicate_result_count": state.duplicate_result_count,
        "unique_legal_portfolio_count": state.unique_legal_portfolio_count,
        "bonferroni_pruned_count": state.bonferroni_pruned_count,
        "survivor_count": state.survivor_count,
        "exact_scored_count": state.exact_scored_count,
        "seen_portfolio_hashes": sorted(state.seen_portfolio_hashes),
        "exact_records": [_record_to_json(record) for record in state.exact_records],
        "best_exact_count": state.best_exact_count,
        "best_portfolio_sha256": state.best_portfolio_sha256,
        "best_portfolio": state.best_portfolio,
        "audit_digest": state.audit_digest,
        "complete": state.complete,
    }


def _require_json_object(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a JSON object")
    result: dict[str, object] = {}
    for key, item in cast(dict[object, object], value).items():
        if not isinstance(key, str):
            raise ValueError(f"{context} keys must be strings")
        result[key] = item
    return result


def _require_json_portfolio(value: object, ticket_count: int) -> Portfolio:
    if not isinstance(value, list):
        raise ValueError("checkpoint portfolio must be a JSON array")
    tickets: list[list[int]] = []
    for raw_ticket in cast(list[object], value):
        if not isinstance(raw_ticket, list):
            raise ValueError("checkpoint ticket must be a JSON array")
        ticket: list[int] = []
        for number in cast(list[object], raw_ticket):
            if type(number) is not int:
                raise ValueError("checkpoint ticket numbers must be integers")
            ticket.append(number)
        tickets.append(ticket)
    return normalize_portfolio(tickets, expected_ticket_count=ticket_count)


def _require_json_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if type(value) is not int:
        raise ValueError(f"checkpoint field {key} must be an integer")
    return value


def _state_from_json(
    payload: dict[str, object],
    incumbent: Portfolio,
    incumbent_outcome_count: int,
    task_id: str,
) -> SweepState:
    schema_version = payload.get("schema_version")
    if type(schema_version) is not int or schema_version != 1:
        raise ValueError("unsupported checkpoint schema")
    incumbent_sha256 = portfolio_sha256(incumbent)
    if payload.get("task_id") != task_id:
        raise ValueError("checkpoint task identity mismatch")
    if payload.get("search_definition_version") != SEARCH_DEFINITION_VERSION:
        raise ValueError("checkpoint search-definition version mismatch")
    if payload.get("incumbent_sha256") != incumbent_sha256:
        raise ValueError("checkpoint incumbent identity mismatch")
    incumbent_count = _require_json_int(payload, "incumbent_outcome_count")
    if incumbent_count != incumbent_outcome_count:
        raise ValueError("checkpoint incumbent outcome-count mismatch")
    raw_hashes = payload.get("seen_portfolio_hashes")
    if not isinstance(raw_hashes, list):
        raise ValueError("checkpoint seen-portfolio hashes are malformed")
    hashes: list[str] = []
    for value in cast(list[object], raw_hashes):
        if not isinstance(value, str):
            raise ValueError("checkpoint seen-portfolio hashes are malformed")
        hashes.append(value)
    if any(
        len(value) != 64 or any(character not in "0123456789abcdef" for character in value)
        for value in hashes
    ):
        raise ValueError("checkpoint contains an invalid portfolio hash")
    seen = set(hashes)
    if len(seen) != len(hashes):
        raise ValueError("checkpoint contains duplicate seen-portfolio hashes")
    ticket_count = len(incumbent)
    best_portfolio = _require_json_portfolio(payload.get("best_portfolio"), ticket_count)
    best_sha = payload.get("best_portfolio_sha256")
    if not isinstance(best_sha, str) or portfolio_sha256(best_portfolio) != best_sha:
        raise ValueError("checkpoint best-portfolio identity mismatch")
    records_json = payload.get("exact_records")
    if not isinstance(records_json, list):
        raise ValueError("checkpoint exact records are malformed")
    records: list[ExactCandidateRecord] = []
    for raw_record in cast(list[object], records_json):
        record_payload = _require_json_object(raw_record, "checkpoint exact record")
        record_portfolio = _require_json_portfolio(record_payload.get("portfolio"), ticket_count)
        record_sha = record_payload.get("portfolio_sha256")
        fraction_text = record_payload.get("exact_fraction")
        if not isinstance(record_sha, str) or portfolio_sha256(record_portfolio) != record_sha:
            raise ValueError("checkpoint exact-record portfolio identity mismatch")
        if not isinstance(fraction_text, str):
            raise ValueError("checkpoint exact-record fraction is malformed")
        exact_count = _require_json_int(record_payload, "exact_outcome_count")
        u3_count = _require_json_int(record_payload, "u3_outcome_count")
        delta = _require_json_int(record_payload, "delta_outcomes")
        if not 0 <= exact_count <= TOTAL_OFFICIAL_OUTCOMES:
            raise ValueError("checkpoint exact-record outcome count is outside the outcome space")
        if Fraction(exact_count, TOTAL_OFFICIAL_OUTCOMES) != Fraction(fraction_text):
            raise ValueError("checkpoint exact-record fraction mismatch")
        if exact_count - incumbent_count != delta or u3_count <= incumbent_count:
            raise ValueError("checkpoint exact-record decision fields mismatch")
        if u3_count < exact_count:
            raise ValueError("checkpoint exact record exceeds its Bonferroni upper bound")
        if record_sha not in seen:
            raise ValueError("checkpoint exact record is missing from seen portfolios")
        records.append(
            ExactCandidateRecord(
                portfolio=record_portfolio,
                portfolio_sha256=record_sha,
                u3_outcome_count=u3_count,
                exact_outcome_count=exact_count,
                exact_fraction=fraction_text,
                delta_outcomes=delta,
            )
        )
    complete = payload.get("complete")
    if type(complete) is not bool:
        raise ValueError("checkpoint completion flag is malformed")
    audit_digest = payload.get("audit_digest")
    if not isinstance(audit_digest, str):
        raise ValueError("checkpoint audit digest is malformed")
    state = SweepState(
        task_id=task_id,
        search_definition_version=SEARCH_DEFINITION_VERSION,
        incumbent_sha256=incumbent_sha256,
        incumbent_outcome_count=incumbent_count,
        ticket_pair_index=_require_json_int(payload, "ticket_pair_index"),
        move_index=_require_json_int(payload, "move_index"),
        raw_move_count=_require_json_int(payload, "raw_move_count"),
        illegal_move_count=_require_json_int(payload, "illegal_move_count"),
        legal_move_count=_require_json_int(payload, "legal_move_count"),
        duplicate_result_count=_require_json_int(payload, "duplicate_result_count"),
        unique_legal_portfolio_count=_require_json_int(payload, "unique_legal_portfolio_count"),
        bonferroni_pruned_count=_require_json_int(payload, "bonferroni_pruned_count"),
        survivor_count=_require_json_int(payload, "survivor_count"),
        exact_scored_count=_require_json_int(payload, "exact_scored_count"),
        seen_portfolio_hashes=seen,
        exact_records=records,
        best_exact_count=_require_json_int(payload, "best_exact_count"),
        best_portfolio_sha256=best_sha,
        best_portfolio=best_portfolio,
        audit_digest=audit_digest,
        complete=complete,
    )
    _validate_state_accounting(state)
    if state.exact_scored_count != len(state.exact_records):
        raise ValueError("checkpoint exact-scored count does not match its exact records")
    if state.best_exact_count != max(
        [incumbent_count, *(record.exact_outcome_count for record in state.exact_records)]
    ):
        raise ValueError("checkpoint best count does not match its exact-score records")
    if len({record.portfolio_sha256 for record in state.exact_records}) != len(state.exact_records):
        raise ValueError("checkpoint contains duplicate exact-scored portfolios")
    if not incumbent_count <= state.best_exact_count <= TOTAL_OFFICIAL_OUTCOMES:
        raise ValueError("checkpoint best exact count is outside the valid range")
    if state.best_exact_count == incumbent_count:
        if state.best_portfolio_sha256 != incumbent_sha256 or state.best_portfolio != incumbent:
            raise ValueError("checkpoint baseline champion is not the incumbent")
    else:
        best_records = [
            record
            for record in state.exact_records
            if record.exact_outcome_count == state.best_exact_count
        ]
        if not best_records:
            raise ValueError("checkpoint champion has no exact-score record")
        expected_best = min(best_records, key=lambda record: record.portfolio_sha256)
        if (
            state.best_portfolio_sha256 != expected_best.portfolio_sha256
            or state.best_portfolio != expected_best.portfolio
        ):
            raise ValueError("checkpoint champion does not match its exact-score records")
    try:
        if len(bytes.fromhex(state.audit_digest)) != 32:
            raise ValueError("checkpoint audit digest is malformed")
    except ValueError as error:
        raise ValueError("checkpoint audit digest is malformed") from error
    if len(state.audit_digest) != 64:
        raise ValueError("checkpoint audit digest is malformed")
    return state


def _validate_state_accounting(state: SweepState) -> None:
    counts = (
        state.ticket_pair_index,
        state.move_index,
        state.raw_move_count,
        state.illegal_move_count,
        state.legal_move_count,
        state.duplicate_result_count,
        state.unique_legal_portfolio_count,
        state.bonferroni_pruned_count,
        state.survivor_count,
        state.exact_scored_count,
    )
    if any(value < 0 for value in counts):
        raise ValueError("checkpoint counters cannot be negative")
    if state.raw_move_count != state.illegal_move_count + state.legal_move_count:
        raise ValueError("checkpoint raw-move accounting identity failed")
    if state.legal_move_count != state.duplicate_result_count + state.unique_legal_portfolio_count:
        raise ValueError("checkpoint legal-portfolio accounting identity failed")
    if state.unique_legal_portfolio_count != state.bonferroni_pruned_count + state.survivor_count:
        raise ValueError("checkpoint Bonferroni accounting identity failed")
    if state.survivor_count != state.exact_scored_count:
        raise ValueError("checkpoint survivor exact-scoring identity failed")
    if len(state.seen_portfolio_hashes) != state.unique_legal_portfolio_count:
        raise ValueError("checkpoint unique portfolio count does not match its identities")


def _write_json_atomically(path: Path, payload: dict[str, object]) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n").encode(
        "utf-8"
    )
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False
        ) as temporary_file:
            temporary_path = temporary_file.name
            temporary_file.write(encoded)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary_path is not None and os.path.exists(temporary_path):
            os.unlink(temporary_path)
    return encoded


def _save_checkpoint(path: Path, state: SweepState) -> bytes:
    _validate_state_accounting(state)
    return _write_json_atomically(path, _state_to_json(state))


def _load_checkpoint(
    path: Path, incumbent: Portfolio, incumbent_outcome_count: int, task_id: str
) -> tuple[SweepState, bytes]:
    raw = path.read_bytes()
    payload = _require_json_object(json.loads(raw), "checkpoint root")
    return _state_from_json(payload, incumbent, incumbent_outcome_count, task_id), raw


def _cursor_after(
    pair_index: int,
    move_index: int,
    groups: tuple[tuple[CrossSwapMove, ...], ...],
) -> tuple[int, int]:
    pair_index, move_index = pair_index, move_index + 1
    while pair_index < len(groups) and move_index >= len(groups[pair_index]):
        pair_index += 1
        move_index = 0
    while pair_index < len(groups) and not groups[pair_index]:
        pair_index += 1
    return pair_index, move_index


def _raw_moves_before_cursor(
    groups: tuple[tuple[CrossSwapMove, ...], ...], pair_index: int, move_index: int
) -> int:
    if not 0 <= pair_index <= len(groups):
        raise ValueError("checkpoint ticket-pair cursor is outside the move list")
    if pair_index == len(groups):
        if move_index != 0:
            raise ValueError("terminal checkpoint move cursor must be zero")
        return sum(map(len, groups))
    if not 0 <= move_index < len(groups[pair_index]):
        raise ValueError("checkpoint move cursor is outside its ticket pair")
    return sum(len(group) for group in groups[:pair_index]) + move_index


def run_cross_swap_sweep(
    incumbent: Sequence[Sequence[int]],
    incumbent_outcome_count: int,
    *,
    checkpoint_path: Path,
    exact_scorer: Callable[[Portfolio], ExactPortfolioProbability],
    task_id: str = TASK_ID,
    resume: bool = False,
    checkpoint_every: int = 25,
    max_raw_moves: int | None = None,
    expected_ticket_count: int | None = None,
) -> SweepState:
    """Run or resume one fixed-origin exhaustive neighborhood sweep."""

    if checkpoint_every <= 0:
        raise ValueError("checkpoint interval must be positive")
    origin = normalize_portfolio(incumbent, expected_ticket_count=expected_ticket_count)
    origin_sha = portfolio_sha256(origin)
    groups = generate_move_groups(origin)
    if resume:
        if not checkpoint_path.is_file():
            raise ValueError("resume requested but checkpoint does not exist")
        state, expected_checkpoint_bytes = _load_checkpoint(
            checkpoint_path, origin, incumbent_outcome_count, task_id
        )
    else:
        if checkpoint_path.exists():
            raise ValueError("checkpoint already exists; resume explicitly or select a new path")
        state = SweepState(
            task_id=task_id,
            search_definition_version=SEARCH_DEFINITION_VERSION,
            incumbent_sha256=origin_sha,
            incumbent_outcome_count=incumbent_outcome_count,
            ticket_pair_index=0,
            move_index=0,
            raw_move_count=0,
            illegal_move_count=0,
            legal_move_count=0,
            duplicate_result_count=0,
            unique_legal_portfolio_count=0,
            bonferroni_pruned_count=0,
            survivor_count=0,
            exact_scored_count=0,
            seen_portfolio_hashes=set(),
            exact_records=[],
            best_exact_count=incumbent_outcome_count,
            best_portfolio_sha256=origin_sha,
            best_portfolio=origin,
            audit_digest=_initial_audit_digest(origin_sha, incumbent_outcome_count),
        )
        expected_checkpoint_bytes = _save_checkpoint(checkpoint_path, state)
    if (
        state.incumbent_sha256 != origin_sha
        or state.incumbent_outcome_count != incumbent_outcome_count
        or state.task_id != task_id
        or state.search_definition_version != SEARCH_DEFINITION_VERSION
    ):
        raise ValueError("checkpoint identity does not match the requested sweep")
    processed_at_entry = state.raw_move_count
    if (
        _raw_moves_before_cursor(groups, state.ticket_pair_index, state.move_index)
        != state.raw_move_count
    ):
        raise ValueError("checkpoint cursor does not match its raw move count")
    if state.complete:
        if state.ticket_pair_index != len(groups):
            raise ValueError("completed checkpoint has a nonterminal move cursor")
        return state
    full_components = full_u3_components(origin)
    seen = PortfolioDeduplicator(state.seen_portfolio_hashes)
    last_saved_hash = hashlib.sha256(expected_checkpoint_bytes).hexdigest()
    moves_since_save = 0
    stop_after = None if max_raw_moves is None else processed_at_entry + max_raw_moves
    pair_index = state.ticket_pair_index
    move_index = state.move_index
    while pair_index < len(groups):
        group = groups[pair_index]
        if move_index >= len(group):
            pair_index, move_index = _cursor_after(pair_index, move_index - 1, groups)
            state.ticket_pair_index, state.move_index = pair_index, move_index
            continue
        if stop_after is not None and state.raw_move_count >= stop_after:
            break
        move = group[move_index]
        state.raw_move_count += 1
        candidate = _portfolio_candidate_for_move(origin, move)
        record: dict[str, object] = {
            "pair_index": pair_index,
            "move_index": move_index,
            "status": "ILLEGAL",
        }
        if candidate is None:
            state.illegal_move_count += 1
        else:
            state.legal_move_count += 1
            digest = portfolio_sha256(candidate.portfolio)
            record["candidate_sha256"] = digest
            if not seen.add(candidate.portfolio):
                state.duplicate_result_count += 1
                record["status"] = "DUPLICATE_RESULT"
            else:
                state.seen_portfolio_hashes.add(digest)
                state.unique_legal_portfolio_count += 1
                components = incremental_u3_components(
                    origin,
                    candidate.portfolio,
                    full_components,
                    candidate.old_changed_tickets,
                    candidate.new_changed_tickets,
                )
                record["u3_outcome_count"] = components.u3
                if should_safe_prune(components.u3, incumbent_outcome_count):
                    state.bonferroni_pruned_count += 1
                    record["status"] = "SAFE_PRUNE"
                else:
                    exact = exact_scorer(candidate.portfolio)
                    exact_count = exact.official_any_prize_outcome_count
                    exact_total = exact.main_draw_count * exact.special_count
                    if exact_total != TOTAL_OFFICIAL_OUTCOMES:
                        raise ValueError("canonical exact scorer returned a non-B649 outcome space")
                    if exact_count < 0 or exact_count > TOTAL_OFFICIAL_OUTCOMES:
                        raise ValueError("canonical exact scorer returned an invalid outcome count")
                    if components.u3 < exact_count:
                        raise AssertionError("Bonferroni U3 is below the canonical exact score")
                    exact_fraction = str(exact.official_any_prize)
                    delta = exact_count - incumbent_outcome_count
                    state.survivor_count += 1
                    state.exact_scored_count += 1
                    state.exact_records.append(
                        ExactCandidateRecord(
                            portfolio=candidate.portfolio,
                            portfolio_sha256=digest,
                            u3_outcome_count=components.u3,
                            exact_outcome_count=exact_count,
                            exact_fraction=exact_fraction,
                            delta_outcomes=delta,
                        )
                    )
                    record["status"] = "EXACT_SCORED"
                    record["exact_outcome_count"] = exact_count
                    if exact_count > state.best_exact_count or (
                        exact_count == state.best_exact_count
                        and exact_count > incumbent_outcome_count
                        and digest < state.best_portfolio_sha256
                    ):
                        state.best_exact_count = exact_count
                        state.best_portfolio_sha256 = digest
                        state.best_portfolio = candidate.portfolio
        state.audit_digest = _advance_audit_digest(state.audit_digest, record)
        pair_index, move_index = _cursor_after(pair_index, move_index, groups)
        state.ticket_pair_index, state.move_index = pair_index, move_index
        moves_since_save += 1
        if moves_since_save >= checkpoint_every:
            if hashlib.sha256(checkpoint_path.read_bytes()).hexdigest() != last_saved_hash:
                raise ValueError("checkpoint changed outside this sweep")
            expected_checkpoint_bytes = _save_checkpoint(checkpoint_path, state)
            last_saved_hash = hashlib.sha256(expected_checkpoint_bytes).hexdigest()
            moves_since_save = 0
    if pair_index >= len(groups):
        state.complete = True
    if hashlib.sha256(checkpoint_path.read_bytes()).hexdigest() != last_saved_hash:
        raise ValueError("checkpoint changed outside this sweep")
    expected_checkpoint_bytes = _save_checkpoint(checkpoint_path, state)
    del expected_checkpoint_bytes
    return state


def verify_incumbent_exact(
    incumbent: Incumbent, *, draws: DrawMasks | None = None
) -> ExactPortfolioProbability:
    exact = evaluate_portfolio(incumbent.portfolio, draws=draws)
    if exact.official_any_prize_outcome_count != incumbent.outcome_count:
        raise ValueError("canonical exact arbiter disagrees with the pinned incumbent count")
    if str(exact.official_any_prize) != incumbent.exact_fraction:
        raise ValueError("canonical exact arbiter disagrees with the pinned incumbent fraction")
    return exact


def _report(state: SweepState, *, fixture_exact_evaluations: int) -> dict[str, object]:
    pair_count = comb(len(state.best_portfolio), 2)
    raw = state.raw_move_count
    legal = state.legal_move_count
    unique = state.unique_legal_portfolio_count
    prune_rate = Fraction(state.bonferroni_pruned_count, unique) if unique else Fraction(0, 1)
    best_fraction = Fraction(state.best_exact_count, TOTAL_OFFICIAL_OUTCOMES)
    strict = state.best_exact_count > state.incumbent_outcome_count
    complete = state.complete and raw == state.illegal_move_count + legal
    if complete:
        _validate_state_accounting(state)
    decision = (
        "BOUNDED_INCOMPLETE"
        if not complete
        else "STRICT_IMPROVEMENT_FOUND"
        if strict
        else "NO_STRICT_IMPROVEMENT_IN_EXHAUSTED_2TICKET_CROSS_SWAP_NEIGHBORHOOD"
    )
    return {
        "TASK_STATUS": "COMPLETE" if complete else "IN_PROGRESS",
        "TASK_ID": state.task_id,
        "INCUMBENT_SOURCE_COMMIT": INCUMBENT_SOURCE_COMMIT,
        "INCUMBENT_SOURCE_PATH": INCUMBENT_SOURCE_PATH,
        "INCUMBENT_PORTFOLIO_SHA256": state.incumbent_sha256,
        "INCUMBENT_EXACT_FRACTION": EXPECTED_INCUMBENT_FRACTION,
        "INCUMBENT_OUTCOME_COUNT": state.incumbent_outcome_count,
        "TICKET_PAIR_COUNT": pair_count,
        "RAW_MOVE_COUNT": raw,
        "ILLEGAL_MOVE_COUNT": state.illegal_move_count,
        "LEGAL_MOVE_COUNT": legal,
        "DUPLICATE_RESULT_COUNT": state.duplicate_result_count,
        "UNIQUE_LEGAL_PORTFOLIO_COUNT": unique,
        "BONFERRONI_PRUNED_COUNT": state.bonferroni_pruned_count,
        "BONFERRONI_SURVIVOR_COUNT": state.survivor_count,
        "BONFERRONI_PRUNE_RATE": str(prune_rate),
        "EXACT_EVALUATION_COUNT": state.exact_scored_count,
        "BOUND_FIXTURE_EXACT_EVALUATIONS": fixture_exact_evaluations,
        "BEST_NEIGHBOR_EXACT_OUTCOME_COUNT": state.best_exact_count,
        "BEST_NEIGHBOR_EXACT_FRACTION": str(best_fraction),
        "BEST_NEIGHBOR_DELTA": state.best_exact_count - state.incumbent_outcome_count,
        "BEST_NEIGHBOR_PORTFOLIO": state.best_portfolio,
        "BEST_NEIGHBOR_PORTFOLIO_SHA256": state.best_portfolio_sha256,
        "EXACT_SURVIVOR_RECORDS": [_record_to_json(record) for record in state.exact_records],
        "SEARCH_AUDIT_DIGEST": state.audit_digest,
        "NEIGHBORHOOD_COMPLETENESS": "PROVEN" if complete else "NOT_PROVEN",
        "FINAL_DECISION": decision,
        "K20_2TICKET_CROSS_SWAP_STATUS": (
            "PROVEN_LOCAL_OPTIMUM_FOR_DEFINED_NEIGHBORHOOD"
            if complete and not strict
            else "STRICT_IMPROVEMENT_FOUND"
            if complete and strict
            else "BOUNDED_INCOMPLETE"
        ),
        "GLOBAL_K20_OPTIMUM_STATUS": "UNKNOWN",
        "SINGLE_NEXT_RESEARCH_TASK": (
            "Repeat the identical exhaustive neighborhood sweep from the new champion."
            if strict
            else "Run a bounded Filmus-Ward non-oblivious experiment."
        ),
        "NEXT_TASK_STARTED": "NO",
        "PUSH": "NOT RUN",
        "PR": "NOT CREATED",
    }


def run_task(
    repository: Path,
    checkpoint_path: Path,
    *,
    result_path: Path,
    incumbent_commit: str,
    incumbent_path: str,
    resume: bool,
    checkpoint_every: int,
) -> dict[str, object]:
    incumbent = load_pinned_incumbent(
        repository, source_commit=incumbent_commit, source_path=incumbent_path
    )
    draws = all_main_draw_masks(BIG_LOTTO_POOL_SIZE, BIG_LOTTO_DRAW_SIZE)
    incumbent_exact = verify_incumbent_exact(incumbent, draws=draws)
    fixture_hashes = validate_bound_fixtures(
        incumbent.portfolio,
        draws=draws,
        known_incumbent_exact=incumbent_exact,
    )
    state = run_cross_swap_sweep(
        incumbent.portfolio,
        incumbent.outcome_count,
        checkpoint_path=checkpoint_path,
        exact_scorer=lambda candidate: evaluate_portfolio(candidate, draws=draws),
        resume=resume,
        checkpoint_every=checkpoint_every,
        expected_ticket_count=20,
    )
    report = _report(state, fixture_exact_evaluations=len(fixture_hashes))
    report["INCUMBENT_METHOD"] = incumbent.method
    report["INCUMBENT_PORTFOLIO"] = incumbent.portfolio
    report["EXECUTION_ID"] = EXECUTION_ID
    _write_json_atomically(result_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--incumbent-commit", required=True)
    parser.add_argument("--incumbent-path", required=True)
    parser.add_argument("--checkpoint-path", type=Path, required=True)
    parser.add_argument("--result-path", type=Path, required=True)
    parser.add_argument(
        "--resume",
        action="store_true",
        required=True,
        help="resume the checkpoint if present, or initialize it when absent",
    )
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[3]
    checkpoint_path = args.checkpoint_path
    result_path = args.result_path
    if not checkpoint_path.is_absolute():
        checkpoint_path = repository / checkpoint_path
    if not result_path.is_absolute():
        result_path = repository / result_path
    report = run_task(
        repository,
        checkpoint_path,
        result_path=result_path,
        incumbent_commit=args.incumbent_commit,
        incumbent_path=args.incumbent_path,
        resume=args.resume and checkpoint_path.is_file(),
        checkpoint_every=25,
    )
    print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
