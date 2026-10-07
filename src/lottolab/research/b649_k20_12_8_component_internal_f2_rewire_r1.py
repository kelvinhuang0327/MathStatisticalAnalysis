"""Exact frozen-F3 F2-support rewires inside each component of the K20 12+8 champion.

The N2-closed champion splits into two ticket components (12 and 8 tickets)
with disjoint number sets. A number's *support* is the set of ticket slots that
contain it. Every frequency-3 support is frozen; only the frequency-2 supports
inside one component at a time are rewired:

* Family A (12-side): every perfect matching of the 12 slots becomes the six
  F2 supports.
* Family B (8-side): every simple 21-edge F2 graph on the 8 slots with the
  baseline F2 degree sequence, quotiented exactly by the slot permutations that
  preserve the frozen F3 structure, with one relabeling witness per graph.

F2 number labels are assigned deterministically (ascending labels to sorted
supports); any other assignment is a global lottery-number relabeling and
cannot change an exact count. Every scored portfolio is scored by the
canonical exact evaluator over one shared complete draw space, and an
independent two-component decomposition of the same outcome space must agree.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import platform
import subprocess
import time
from collections import Counter
from collections.abc import Generator, Iterable, Mapping, Sequence
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from math import comb, prod
from multiprocessing import get_context
from multiprocessing.shared_memory import SharedMemory
from pathlib import Path
from typing import cast

import numpy as np

from lottolab.research.b649_official_any_prize_exact import (
    BIG_LOTTO_DRAW_SIZE,
    BIG_LOTTO_OUTRIGHT_MATCHES,
    BIG_LOTTO_POOL_SIZE,
    DrawMasks,
    all_main_draw_masks,
    evaluate_portfolio,
    ticket_mask,
)

type Ticket = tuple[int, ...]
type Portfolio = tuple[Ticket, ...]
type Pair = tuple[int, int]
type Triple = tuple[int, int, int]
type Permutation = tuple[int, ...]
type ScoreJob = tuple[str, int, str, Portfolio]
type ScoreReply = tuple[str, int, str, int, int, int, int]

TASK_ID = "B649_K20_12_8_COMPONENT_INTERNAL_F2_REWIRE_EXHAUSTIVE_R1"
SEARCH_DEFINITION_VERSION = "b649-k20-12-8-component-internal-f2-rewire-v1"
AUTHORITY_RESULT_PATH = (
    "docs/research/matrix-native-results/b649-k20-12-8-winner-two-ticket-ascent-r1-result.json"
)
EVALUATOR_PATH = "src/lottolab/research/b649_official_any_prize_exact.py"
RESULT_PATH = (
    "docs/research/matrix-native-results/b649-k20-12-8-component-internal-f2-rewire-r1-result.json"
)
EXPECTED_AUTHORITY_TASK_ID = "B649_K20_12_8_WINNER_TWO_TICKET_ASCENT_R1"
EXPECTED_BASELINE_COUNT = 313_263_888
EXPECTED_BASELINE_SHA256 = "eaed652900d101881b678a1515d2a366bff9de6723dbec2ec9c82fe0d0d7844c"
SCORING_FUNCTION = "evaluate_portfolio(...).official_any_prize_outcome_count"

TICKET_COUNT = 20
COMPONENT_SIZES = (12, 8)
FREQUENCY_PROFILE = {3: 22, 2: 27}
SPECIAL_COUNT = BIG_LOTTO_POOL_SIZE - BIG_LOTTO_DRAW_SIZE
FAMILY_A = "FAMILY_A_12_SIDE"
FAMILY_B = "FAMILY_B_8_SIDE"
FAMILY_ORDER = (FAMILY_A, FAMILY_B)
NO_GAIN_STATUS = "NO_STRICT_GAIN_FOR_DEFINED_SINGLE_COMPONENT_F2_REWIRE_FAMILIES"
GAIN_STATUS = "STRICT_GAIN_FOUND_IN_DEFINED_SINGLE_COMPONENT_F2_REWIRE_FAMILIES"
CLAIM_SCOPE = (
    "Closes only frozen-F3 twelve-side perfect-matching F2 rewires and frozen-F3 "
    "eight-side degree-constrained F2 rewires of the N2-closed 12+8 champion. No claim "
    "about all pairwise-overlap>1 designs or global K20 optimality."
)
_PARTNER_DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"
_FSYNC_EVERY = 25
_PROGRESS_EVERY = 500


class StopError(RuntimeError):
    """A Packet stop condition; ``token`` is the Packet STOP token."""

    token = "STOP"

    def __init__(self, detail: str) -> None:
        super().__init__(f"STOP: {self.token}: {detail}")


class SourceAuthorityDriftError(StopError):
    token = "SOURCE_AUTHORITY_DRIFT"


class ComponentIdentityMismatchError(StopError):
    token = "BASELINE_COMPONENT_IDENTITY_MISMATCH"


class QuotientUnresolvedError(StopError):
    token = "EIGHT_SIDE_QUOTIENT_UNRESOLVED"


class ScoreCrossCheckError(StopError):
    token = "EXACT_SCORE_CROSSCHECK_MISMATCH"


class CheckpointIdentityError(StopError):
    token = "CHECKPOINT_IDENTITY_MISMATCH"


class CandidateInvariantError(ValueError):
    """A constructed portfolio violates a Packet candidate invariant."""


# --- portfolio primitives ---------------------------------------------------------------


def normalize_portfolio(portfolio: Sequence[Sequence[int]]) -> Portfolio:
    """Validate legality and return sorted tickets in sorted order."""

    tickets: list[Ticket] = []
    for raw_ticket in portfolio:
        ticket = tuple(sorted(raw_ticket))
        if (
            len(ticket) != BIG_LOTTO_DRAW_SIZE
            or len(set(ticket)) != BIG_LOTTO_DRAW_SIZE
            or any(
                type(number) is not int or not 1 <= number <= BIG_LOTTO_POOL_SIZE
                for number in ticket
            )
        ):
            raise CandidateInvariantError(f"illegal ticket: {ticket}")
        tickets.append(ticket)
    if len(set(tickets)) != len(tickets):
        raise CandidateInvariantError("portfolio contains duplicate tickets")
    return tuple(sorted(tickets))


def portfolio_sha256(portfolio: Sequence[Sequence[int]]) -> str:
    """SHA-256 of the compact JSON of the normalized portfolio (authority convention)."""

    payload = json.dumps(normalize_portfolio(portfolio), separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def number_supports(portfolio: Sequence[Sequence[int]]) -> dict[int, tuple[int, ...]]:
    """Map every used number to the ascending slot indices of the tickets containing it."""

    supports: dict[int, list[int]] = {}
    for slot, ticket in enumerate(portfolio):
        for number in ticket:
            supports.setdefault(number, []).append(slot)
    return {number: tuple(slots) for number, slots in sorted(supports.items())}


def ticket_components(portfolio: Sequence[Sequence[int]]) -> tuple[tuple[int, ...], ...]:
    """Connected ticket-slot components under shared-number adjacency, largest first."""

    parent = list(range(len(portfolio)))

    def find(slot: int) -> int:
        while parent[slot] != slot:
            parent[slot] = parent[parent[slot]]
            slot = parent[slot]
        return slot

    for slots in number_supports(portfolio).values():
        for slot in slots[1:]:
            parent[find(slot)] = find(slots[0])
    groups: dict[int, list[int]] = {}
    for slot in range(len(portfolio)):
        groups.setdefault(find(slot), []).append(slot)
    return tuple(sorted((tuple(group) for group in groups.values()), key=lambda g: (-len(g), g)))


@dataclass(frozen=True, slots=True)
class OverlapProfile:
    max_overlap: int
    overlap_0: int
    overlap_1: int
    overlap_2_plus: int

    def histogram(self) -> dict[str, int]:
        return {"0": self.overlap_0, "1": self.overlap_1, "2_PLUS": self.overlap_2_plus}


def pair_overlap_profile(portfolio: Sequence[Sequence[int]]) -> OverlapProfile:
    sets = [frozenset(ticket) for ticket in portfolio]
    overlaps = [len(first & second) for first, second in itertools.combinations(sets, 2)]
    return OverlapProfile(
        max_overlap=max(overlaps),
        overlap_0=overlaps.count(0),
        overlap_1=overlaps.count(1),
        overlap_2_plus=sum(1 for overlap in overlaps if overlap >= 2),
    )


# --- source authority and component identity --------------------------------------------


@dataclass(frozen=True, slots=True)
class Authority:
    portfolio: Portfolio
    count: int
    sha256: str
    file_sha256: str
    task_id: str


def _portfolio_from_json(value: object) -> Portfolio:
    if not isinstance(value, list):
        raise SourceAuthorityDriftError("FINAL_TICKETS is not a list")
    tickets: list[Ticket] = []
    for raw_ticket in cast(list[object], value):
        if not isinstance(raw_ticket, list):
            raise SourceAuthorityDriftError("FINAL_TICKETS contains a non-list ticket")
        numbers = cast(list[object], raw_ticket)
        if any(type(number) is not int for number in numbers):
            raise SourceAuthorityDriftError("FINAL_TICKETS contains a non-integer number")
        tickets.append(tuple(cast(list[int], numbers)))
    return tuple(tickets)


def load_authority(repo_root: Path) -> Authority:
    """Load the N2 champion and require it to reproduce the Packet identity exactly."""

    path = repo_root / AUTHORITY_RESULT_PATH
    data = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
    raw = _portfolio_from_json(data.get("FINAL_TICKETS"))
    try:
        portfolio = normalize_portfolio(raw)
    except CandidateInvariantError as error:
        raise SourceAuthorityDriftError(f"authority portfolio is illegal: {error}") from error
    checks = {
        "TASK_ID": data.get("TASK_ID") == EXPECTED_AUTHORITY_TASK_ID,
        "FINAL_COUNT": data.get("FINAL_COUNT") == EXPECTED_BASELINE_COUNT,
        "FINAL_SHA256": data.get("FINAL_SHA256") == EXPECTED_BASELINE_SHA256,
        "FINAL_ENGINE_NORMALIZED_SHA256": (
            data.get("FINAL_ENGINE_NORMALIZED_SHA256") == EXPECTED_BASELINE_SHA256
        ),
        "TICKET_COUNT": len(portfolio) == TICKET_COUNT,
        "NORMALIZED_ORDER": portfolio == raw,
        "RECOMPUTED_SHA256": portfolio_sha256(portfolio) == EXPECTED_BASELINE_SHA256,
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise SourceAuthorityDriftError(f"authority checks failed: {failed}")
    return Authority(
        portfolio=portfolio,
        count=EXPECTED_BASELINE_COUNT,
        sha256=EXPECTED_BASELINE_SHA256,
        file_sha256=file_sha256(path),
        task_id=EXPECTED_AUTHORITY_TASK_ID,
    )


@dataclass(frozen=True, slots=True)
class ComponentSide:
    """One ticket component; local slot ``k`` is global slot ``slots[k]``."""

    slots: tuple[int, ...]
    numbers: tuple[int, ...]
    f3_supports: tuple[tuple[int, Triple], ...]
    f2_labels: tuple[int, ...]
    baseline_f2_edges: tuple[Pair, ...]

    @property
    def f3_bearing_slots(self) -> tuple[int, ...]:
        return tuple(sorted({slot for _, triple in self.f3_supports for slot in triple}))


@dataclass(frozen=True, slots=True)
class Structure:
    baseline: Portfolio
    twelve: ComponentSide
    eight: ComponentSide
    eight_non_f3_slots: Pair
    eight_f2_degree_targets: tuple[int, ...]
    baseline_f3_supports: tuple[tuple[int, tuple[int, ...]], ...]


def _component_side(
    supports: Mapping[int, tuple[int, ...]], slots: tuple[int, ...]
) -> ComponentSide:
    local = {slot: index for index, slot in enumerate(slots)}
    numbers = tuple(number for number, support in supports.items() if support[0] in local)
    if any(slot not in local for number in numbers for slot in supports[number]):
        raise ComponentIdentityMismatchError("a number support crosses the component boundary")
    f3_supports: list[tuple[int, Triple]] = []
    f2_items: list[tuple[int, Pair]] = []
    for number in numbers:
        support = tuple(local[slot] for slot in supports[number])
        if len(support) == 3:
            f3_supports.append((number, (support[0], support[1], support[2])))
        elif len(support) == 2:
            f2_items.append((number, (support[0], support[1])))
        else:
            raise ComponentIdentityMismatchError(f"number {number} has frequency {len(support)}")
    return ComponentSide(
        slots=slots,
        numbers=numbers,
        f3_supports=tuple(f3_supports),
        f2_labels=tuple(number for number, _ in f2_items),
        baseline_f2_edges=tuple(sorted(edge for _, edge in f2_items)),
    )


def f2_degrees(vertex_count: int, edges: Iterable[Pair]) -> tuple[int, ...]:
    degrees = [0] * vertex_count
    for first, second in edges:
        degrees[first] += 1
        degrees[second] += 1
    return tuple(degrees)


def derive_structure(baseline: Portfolio) -> Structure:
    """Derive the 12+8 support hypergraph identity from supports, not ticket order."""

    supports = number_supports(baseline)
    if len(supports) != BIG_LOTTO_POOL_SIZE:
        raise ComponentIdentityMismatchError(f"{len(supports)} numbers used, expected 49")
    profile = Counter(len(support) for support in supports.values())
    if profile != Counter(FREQUENCY_PROFILE):
        raise ComponentIdentityMismatchError(f"frequency profile {dict(profile)}")
    components = ticket_components(baseline)
    if tuple(len(component) for component in components) != COMPONENT_SIZES:
        raise ComponentIdentityMismatchError(
            f"component sizes {[len(component) for component in components]}"
        )
    twelve = _component_side(supports, components[0])
    eight = _component_side(supports, components[1])
    if set(twelve.numbers) & set(eight.numbers):
        raise ComponentIdentityMismatchError("components share a number")

    twelve_f3_degree = Counter(slot for _, triple in twelve.f3_supports for slot in triple)
    twelve_f2_degree = f2_degrees(12, twelve.baseline_f2_edges)
    if (
        len(twelve.f3_supports) != 20
        or len(twelve.f2_labels) != 6
        or any(twelve_f3_degree[slot] != 5 for slot in range(12))
        or twelve_f2_degree != (1,) * 12
    ):
        raise ComponentIdentityMismatchError("12-side support inventory mismatch")

    triples = [set(triple) for _, triple in eight.f3_supports]
    bearing = eight.f3_bearing_slots
    non_f3 = tuple(slot for slot in range(8) if slot not in bearing)
    eight_f2_degree = f2_degrees(8, eight.baseline_f2_edges)
    targets = tuple(6 if slot in non_f3 else 5 for slot in range(8))
    if (
        len(eight.f3_supports) != 2
        or triples[0] & triples[1]
        or len(eight.f2_labels) != 21
        or len(set(eight.baseline_f2_edges)) != 21
        or len(bearing) != 6
        or len(non_f3) != 2
        or eight_f2_degree != targets
    ):
        raise ComponentIdentityMismatchError("8-side support inventory mismatch")

    return Structure(
        baseline=baseline,
        twelve=twelve,
        eight=eight,
        eight_non_f3_slots=(non_f3[0], non_f3[1]),
        eight_f2_degree_targets=targets,
        baseline_f3_supports=tuple(
            (number, support) for number, support in supports.items() if len(support) == 3
        ),
    )


# --- candidate construction and invariants ----------------------------------------------


def side_for(structure: Structure, family: str) -> ComponentSide:
    if family == FAMILY_A:
        return structure.twelve
    if family == FAMILY_B:
        return structure.eight
    raise ValueError(f"unknown family {family!r}")


def side_tickets(side: ComponentSide, f2_edges: Sequence[Pair]) -> tuple[Ticket, ...]:
    """Local-slot tickets: frozen F3 numbers plus ascending F2 labels on sorted edges."""

    edges = sorted(f2_edges)
    if len(edges) != len(side.f2_labels) or len(set(edges)) != len(edges):
        raise CandidateInvariantError("F2 edge list does not match the F2 label inventory")
    numbers: list[list[int]] = [[] for _ in side.slots]
    for number, triple in side.f3_supports:
        for slot in triple:
            numbers[slot].append(number)
    for label, (first, second) in zip(side.f2_labels, edges, strict=True):
        if not 0 <= first < second < len(side.slots):
            raise CandidateInvariantError(f"illegal F2 support {(first, second)}")
        numbers[first].append(label)
        numbers[second].append(label)
    return tuple(tuple(sorted(ticket)) for ticket in numbers)


def build_candidate(structure: Structure, family: str, f2_edges: Sequence[Pair]) -> Portfolio:
    """Global-slot-order portfolio with one component's F2 supports replaced."""

    side = side_for(structure, family)
    tickets = list(structure.baseline)
    for local, ticket in enumerate(side_tickets(side, f2_edges)):
        tickets[side.slots[local]] = ticket
    return tuple(tickets)


def check_candidate(structure: Structure, family: str, candidate: Portfolio) -> OverlapProfile:
    """Enforce every Packet candidate invariant; return the pairwise-overlap profile."""

    if len(candidate) != TICKET_COUNT:
        raise CandidateInvariantError(f"{len(candidate)} tickets, expected {TICKET_COUNT}")
    normalize_portfolio(candidate)
    supports = number_supports(candidate)
    if len(supports) != BIG_LOTTO_POOL_SIZE:
        raise CandidateInvariantError(f"{len(supports)} numbers used, expected 49")
    if Counter(len(support) for support in supports.values()) != Counter(FREQUENCY_PROFILE):
        raise CandidateInvariantError("frequency profile is not 22x3 + 27x2")
    twelve_numbers = {number for slot in structure.twelve.slots for number in candidate[slot]}
    eight_numbers = {number for slot in structure.eight.slots for number in candidate[slot]}
    if twelve_numbers & eight_numbers:
        raise CandidateInvariantError("a number is shared across the 12/8 component boundary")
    if twelve_numbers != set(structure.twelve.numbers) or eight_numbers != set(
        structure.eight.numbers
    ):
        raise CandidateInvariantError("component number labels changed")
    f3_supports = tuple(
        (number, support) for number, support in supports.items() if len(support) == 3
    )
    if f3_supports != structure.baseline_f3_supports:
        raise CandidateInvariantError("a frozen F3 support changed")
    frozen = structure.eight if family == FAMILY_A else structure.twelve
    if any(candidate[slot] != structure.baseline[slot] for slot in frozen.slots):
        raise CandidateInvariantError("the frozen component changed")
    return pair_overlap_profile(candidate)


# --- Family A: 12-side perfect matchings --------------------------------------------------


def enumerate_perfect_matchings(vertex_count: int) -> tuple[tuple[Pair, ...], ...]:
    """Every perfect matching, in lexicographic recursion order (lowest free vertex first)."""

    matchings: list[tuple[Pair, ...]] = []

    def extend(unmatched: tuple[int, ...], edges: tuple[Pair, ...]) -> None:
        if not unmatched:
            matchings.append(edges)
            return
        first, rest = unmatched[0], unmatched[1:]
        for position, partner in enumerate(rest):
            extend(rest[:position] + rest[position + 1 :], (*edges, (first, partner)))

    if vertex_count % 2:
        raise ValueError("a perfect matching needs an even vertex count")
    extend(tuple(range(vertex_count)), ())
    return tuple(matchings)


def odd_double_factorial(vertex_count: int) -> int:
    """``(vertex_count - 1)!!``: the closed-form perfect-matching count of K_n."""

    return prod(range(vertex_count - 1, 0, -2))


def matching_partner_code(matching: Sequence[Pair]) -> str:
    partners = [0] * (2 * len(matching))
    for first, second in matching:
        partners[first] = second
        partners[second] = first
    return "".join(_PARTNER_DIGITS[partner] for partner in partners)


def retained_edge_count(edges: Iterable[Pair], baseline_edges: Iterable[Pair]) -> int:
    return len(set(edges) & set(baseline_edges))


# --- Family B: 8-side degree-constrained F2 graphs ---------------------------------------


def vertex_pairs(vertex_count: int) -> tuple[Pair, ...]:
    return tuple(
        (first, second) for first, second in itertools.combinations(range(vertex_count), 2)
    )


def edges_to_mask(edges: Iterable[Pair], vertex_count: int) -> int:
    index = {pair: position for position, pair in enumerate(vertex_pairs(vertex_count))}
    mask = 0
    for first, second in edges:
        mask |= 1 << index[(min(first, second), max(first, second))]
    return mask


def mask_to_edges(mask: int, vertex_count: int) -> tuple[Pair, ...]:
    return tuple(
        pair for position, pair in enumerate(vertex_pairs(vertex_count)) if mask >> position & 1
    )


def enumerate_degree_graphs(targets: Sequence[int]) -> tuple[int, ...]:
    """Every simple graph with exact degree ``targets`` (backtracking), as ascending masks."""

    vertex_count = len(targets)
    pairs = vertex_pairs(vertex_count)
    remaining_incident = [[0] * vertex_count for _ in range(len(pairs) + 1)]
    for position in range(len(pairs) - 1, -1, -1):
        remaining_incident[position] = list(remaining_incident[position + 1])
        for vertex in pairs[position]:
            remaining_incident[position][vertex] += 1
    degrees = [0] * vertex_count
    graphs: list[int] = []

    def extend(position: int, mask: int) -> None:
        if any(
            targets[v] - degrees[v] > remaining_incident[position][v] for v in range(vertex_count)
        ):
            return
        if position == len(pairs):
            graphs.append(mask)
            return
        first, second = pairs[position]
        if degrees[first] < targets[first] and degrees[second] < targets[second]:
            degrees[first] += 1
            degrees[second] += 1
            extend(position + 1, mask | 1 << position)
            degrees[first] -= 1
            degrees[second] -= 1
        extend(position + 1, mask)

    extend(0, 0)
    return tuple(sorted(graphs))


def count_degree_graphs_by_complement(targets: Sequence[int]) -> int:
    """Independent brute-force count over every complement edge set of the right size."""

    vertex_count = len(targets)
    pairs = vertex_pairs(vertex_count)
    complement_degrees = [vertex_count - 1 - target for target in targets]
    if sum(complement_degrees) % 2:
        return 0
    count = 0
    for chosen in itertools.combinations(pairs, sum(complement_degrees) // 2):
        degrees = [0] * vertex_count
        for first, second in chosen:
            degrees[first] += 1
            degrees[second] += 1
        count += degrees == complement_degrees
    return count


def compose(first: Permutation, second: Permutation) -> Permutation:
    """``first`` after ``second``."""

    return tuple(first[vertex] for vertex in second)


def invert(permutation: Permutation) -> Permutation:
    inverse = [0] * len(permutation)
    for vertex, image in enumerate(permutation):
        inverse[image] = vertex
    return tuple(inverse)


def _preserves_structure(
    permutation: Permutation, triples: Sequence[Triple], fixed_pair: Pair
) -> bool:
    triple_sets = {frozenset(triple) for triple in triples}
    images = {frozenset(permutation[vertex] for vertex in triple) for triple in triples}
    pair_image = frozenset(permutation[vertex] for vertex in fixed_pair)
    return images == triple_sets and pair_image == frozenset(fixed_pair)


def slot_symmetry_group(
    vertex_count: int, triples: Sequence[Triple], fixed_pair: Pair
) -> tuple[Permutation, ...]:
    """All slot permutations preserving the unordered F3 triple pair and the non-F3 pair."""

    return tuple(
        permutation
        for permutation in itertools.permutations(range(vertex_count))
        if _preserves_structure(permutation, triples, fixed_pair)
    )


def verify_group(
    group: Sequence[Permutation], vertex_count: int, triples: Sequence[Triple], fixed_pair: Pair
) -> None:
    members = set(group)
    identity = tuple(range(vertex_count))
    if len(members) != len(group) or identity not in members:
        raise QuotientUnresolvedError("group has duplicates or lacks the identity")
    for permutation in group:
        if sorted(permutation) != list(identity):
            raise QuotientUnresolvedError(f"{permutation} is not a slot permutation")
        if not _preserves_structure(permutation, triples, fixed_pair):
            raise QuotientUnresolvedError(f"{permutation} breaks the frozen F3 structure")
        if invert(permutation) not in members:
            raise QuotientUnresolvedError(f"{permutation} has no inverse in the group")
    for first in group:
        for second in group:
            if compose(first, second) not in members:
                raise QuotientUnresolvedError("group is not closed under composition")


def permutation_pair_bits(permutation: Permutation, vertex_count: int) -> tuple[int, ...]:
    """For each pair position, the bit of its image pair under ``permutation``."""

    index = {pair: position for position, pair in enumerate(vertex_pairs(vertex_count))}
    bits: list[int] = []
    for first, second in vertex_pairs(vertex_count):
        image = (permutation[first], permutation[second])
        bits.append(1 << index[(min(image), max(image))])
    return tuple(bits)


def permute_mask(pair_bits: Sequence[int], mask: int) -> int:
    image = 0
    position = 0
    while mask:
        if mask & 1:
            image |= pair_bits[position]
        mask >>= 1
        position += 1
    return image


@dataclass(frozen=True, slots=True)
class Quotient:
    """Orbit representatives (ascending masks) and one witness per raw graph."""

    representatives: tuple[int, ...]
    assignments: tuple[tuple[int, int, Permutation], ...]
    orbit_sizes: tuple[int, ...]


def build_quotient(
    graphs: Sequence[int], group: Sequence[Permutation], vertex_count: int
) -> Quotient:
    """Representative = least image mask; witness = first group element reaching it."""

    pair_bits = [permutation_pair_bits(permutation, vertex_count) for permutation in group]
    canonical: list[tuple[int, Permutation]] = []
    for graph in graphs:
        images = [permute_mask(bits, graph) for bits in pair_bits]
        least = min(images)
        canonical.append((least, group[images.index(least)]))
    representatives = tuple(sorted({least for least, _ in canonical}))
    orbit_of = {representative: index for index, representative in enumerate(representatives)}
    sizes = Counter(orbit_of[least] for least, _ in canonical)
    return Quotient(
        representatives=representatives,
        assignments=tuple(
            (graph, orbit_of[least], witness)
            for graph, (least, witness) in zip(graphs, canonical, strict=True)
        ),
        orbit_sizes=tuple(sizes[index] for index in range(len(representatives))),
    )


def verify_quotient(
    graphs: Sequence[int],
    group: Sequence[Permutation],
    quotient: Quotient,
    vertex_count: int,
) -> int:
    """Prove exact orbit coverage with witnesses; return the Burnside orbit count."""

    graph_set = set(graphs)
    if len(graph_set) != len(graphs):
        raise QuotientUnresolvedError("raw graph list has duplicates")
    if [assignment[0] for assignment in quotient.assignments] != list(graphs):
        raise QuotientUnresolvedError("assignments do not cover the raw graphs in order")
    members = set(group)
    pair_bits = [permutation_pair_bits(permutation, vertex_count) for permutation in group]
    assigned: dict[int, set[int]] = {}
    for graph, orbit, witness in quotient.assignments:
        if witness not in members:
            raise QuotientUnresolvedError(f"witness {witness} is not a group element")
        if not 0 <= orbit < len(quotient.representatives):
            raise QuotientUnresolvedError(f"orbit index {orbit} out of range")
        image = permute_mask(permutation_pair_bits(witness, vertex_count), graph)
        if image != quotient.representatives[orbit]:
            raise QuotientUnresolvedError(f"witness does not map graph {graph:#x} to its rep")
        assigned.setdefault(orbit, set()).add(graph)
    covered: set[int] = set()
    for index, representative in enumerate(quotient.representatives):
        orbit = {permute_mask(bits, representative) for bits in pair_bits}
        if not orbit <= graph_set:
            raise QuotientUnresolvedError("the raw family is not closed under the group")
        if assigned.get(index, set()) != orbit:
            raise QuotientUnresolvedError(f"orbit {index} membership is not its full orbit")
        if covered & orbit:
            raise QuotientUnresolvedError(f"orbit {index} overlaps an earlier orbit")
        if len(group) % len(orbit) or quotient.orbit_sizes[index] != len(orbit):
            raise QuotientUnresolvedError(f"orbit {index} size violates orbit-stabilizer")
        covered |= orbit
    if covered != graph_set:
        raise QuotientUnresolvedError("orbits do not cover the raw family")
    fixed_points = sum(
        1 for bits in pair_bits for graph in graphs if permute_mask(bits, graph) == graph
    )
    if fixed_points % len(group) or fixed_points // len(group) != len(quotient.representatives):
        raise QuotientUnresolvedError("Burnside orbit count disagrees with the quotient")
    return fixed_points // len(group)


def verify_portfolio_witness(
    structure: Structure, graph: int, representative: int, witness: Permutation
) -> None:
    """Exhibit the global number relabeling that carries graph's portfolio onto the rep's."""

    side = structure.eight
    vertex_count = len(side.slots)
    graph_edges = mask_to_edges(graph, vertex_count)
    rep_edges = mask_to_edges(representative, vertex_count)
    graph_label = dict(zip(graph_edges, side.f2_labels, strict=True))
    rep_label = dict(zip(rep_edges, side.f2_labels, strict=True))
    mapping = {number: number for number in structure.twelve.numbers}
    f3_by_triple = {frozenset(triple): number for number, triple in side.f3_supports}
    for number, triple in side.f3_supports:
        image = frozenset(witness[vertex] for vertex in triple)
        if image not in f3_by_triple:
            raise QuotientUnresolvedError("witness does not preserve the F3 triples")
        mapping[number] = f3_by_triple[image]
    for (first, second), label in graph_label.items():
        image = (min(witness[first], witness[second]), max(witness[first], witness[second]))
        if image not in rep_label:
            raise QuotientUnresolvedError("witness does not carry an F2 support to the rep")
        mapping[label] = rep_label[image]
    if sorted(mapping) != list(range(1, BIG_LOTTO_POOL_SIZE + 1)) or sorted(
        mapping.values()
    ) != list(range(1, BIG_LOTTO_POOL_SIZE + 1)):
        raise QuotientUnresolvedError("number relabeling is not a bijection of 1..49")
    graph_portfolio = build_candidate(structure, FAMILY_B, graph_edges)
    rep_portfolio = build_candidate(structure, FAMILY_B, rep_edges)
    for local in range(vertex_count):
        source = graph_portfolio[side.slots[local]]
        target = rep_portfolio[side.slots[witness[local]]]
        if tuple(sorted(mapping[number] for number in source)) != target:
            raise QuotientUnresolvedError(f"slot {local} does not relabel onto its image slot")
    mapped = normalize_portfolio([[mapping[number] for number in t] for t in graph_portfolio])
    if mapped != normalize_portfolio(rep_portfolio):
        raise QuotientUnresolvedError("relabeled portfolio differs from the representative")


# --- family spaces ------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FamilyACandidate:
    index: int
    matching: tuple[Pair, ...]
    code: str
    portfolio: Portfolio
    profile: OverlapProfile
    retained: int


@dataclass(frozen=True, slots=True)
class FamilyASpace:
    raw_count: int
    closed_form_count: int
    legal: tuple[FamilyACandidate, ...]
    illegal_indices: tuple[int, ...]
    baseline_index: int


def build_family_a(structure: Structure) -> FamilyASpace:
    side = structure.twelve
    matchings = enumerate_perfect_matchings(len(side.slots))
    closed_form = odd_double_factorial(len(side.slots))
    if len(set(matchings)) != len(matchings) or len(matchings) != closed_form:
        raise ValueError("perfect-matching enumeration disagrees with (n-1)!!")
    legal: list[FamilyACandidate] = []
    illegal: list[int] = []
    for index, matching in enumerate(matchings):
        portfolio = build_candidate(structure, FAMILY_A, matching)
        try:
            profile = check_candidate(structure, FAMILY_A, portfolio)
        except CandidateInvariantError:
            illegal.append(index)
            continue
        legal.append(
            FamilyACandidate(
                index=index,
                matching=matching,
                code=matching_partner_code(matching),
                portfolio=portfolio,
                profile=profile,
                retained=retained_edge_count(matching, side.baseline_f2_edges),
            )
        )
    if side.baseline_f2_edges not in matchings:
        raise ComponentIdentityMismatchError("baseline 12-side F2 matching is not in Family A")
    return FamilyASpace(
        raw_count=len(matchings),
        closed_form_count=closed_form,
        legal=tuple(legal),
        illegal_indices=tuple(illegal),
        baseline_index=matchings.index(side.baseline_f2_edges),
    )


@dataclass(frozen=True, slots=True)
class FamilyBSpace:
    graphs: tuple[int, ...]
    brute_force_count: int
    group: tuple[Permutation, ...]
    quotient: Quotient
    burnside_orbit_count: int
    baseline_graph: int
    legal_raw_count: int


def build_family_b(structure: Structure) -> FamilyBSpace:
    side = structure.eight
    vertex_count = len(side.slots)
    graphs = enumerate_degree_graphs(structure.eight_f2_degree_targets)
    brute_force = count_degree_graphs_by_complement(structure.eight_f2_degree_targets)
    if brute_force != len(graphs):
        raise QuotientUnresolvedError("backtracking and brute-force graph counts disagree")
    triples = tuple(triple for _, triple in side.f3_supports)
    group = slot_symmetry_group(vertex_count, triples, structure.eight_non_f3_slots)
    verify_group(group, vertex_count, triples, structure.eight_non_f3_slots)
    quotient = build_quotient(graphs, group, vertex_count)
    burnside = verify_quotient(graphs, group, quotient, vertex_count)
    for graph, orbit, witness in quotient.assignments:
        verify_portfolio_witness(structure, graph, quotient.representatives[orbit], witness)
    baseline_graph = edges_to_mask(side.baseline_f2_edges, vertex_count)
    if baseline_graph not in set(graphs):
        raise ComponentIdentityMismatchError("baseline 8-side F2 graph is not in Family B")
    legal = 0
    for graph in graphs:
        try:
            check_candidate(
                structure, FAMILY_B, build_candidate(structure, FAMILY_B, mask_to_edges(graph, 8))
            )
        except CandidateInvariantError:
            continue
        legal += 1
    return FamilyBSpace(
        graphs=graphs,
        brute_force_count=brute_force,
        group=group,
        quotient=quotient,
        burnside_orbit_count=burnside,
        baseline_graph=baseline_graph,
        legal_raw_count=legal,
    )


# --- independent two-component decomposition of the exact outcome space ------------------


@dataclass(frozen=True, slots=True)
class ComponentStats:
    """Per subset size ``a`` of the component's numbers: non-winning count and rescue sum."""

    number_count: int
    non_won: tuple[int, ...]
    rescue_sum: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class DecompositionTables:
    twelve_numbers: frozenset[int]
    twelve_subsets: tuple[DrawMasks, ...]
    eight_numbers: frozenset[int]
    eight_subsets: tuple[DrawMasks, ...]


def subset_masks_by_size(numbers: Sequence[int]) -> tuple[DrawMasks, ...]:
    return tuple(
        np.array(
            [ticket_mask(subset) for subset in itertools.combinations(numbers, size)],
            dtype=np.uint64,
        )
        for size in range(BIG_LOTTO_DRAW_SIZE + 1)
    )


def decomposition_tables(
    twelve_numbers: Sequence[int], eight_numbers: Sequence[int]
) -> DecompositionTables:
    if set(twelve_numbers) & set(eight_numbers) or set(twelve_numbers) | set(eight_numbers) != set(
        range(1, BIG_LOTTO_POOL_SIZE + 1)
    ):
        raise ValueError("component number sets must partition 1..49")
    return DecompositionTables(
        twelve_numbers=frozenset(twelve_numbers),
        twelve_subsets=subset_masks_by_size(sorted(twelve_numbers)),
        eight_numbers=frozenset(eight_numbers),
        eight_subsets=subset_masks_by_size(sorted(eight_numbers)),
    )


def component_stats(
    tickets: Sequence[Ticket], subsets_by_size: Sequence[DrawMasks], number_count: int
) -> ComponentStats:
    masks = [np.uint64(ticket_mask(ticket)) for ticket in tickets]
    zero = np.uint64(0)
    non_won: list[int] = []
    rescue_sum: list[int] = []
    for subsets in subsets_by_size:
        won = np.zeros(subsets.size, dtype=np.bool_)
        rescue = np.zeros(subsets.size, dtype=np.uint64)
        for mask in masks:
            hits = np.bitwise_count(subsets & mask)
            won |= hits >= BIG_LOTTO_OUTRIGHT_MATCHES
            rescue |= np.where(hits == BIG_LOTTO_OUTRIGHT_MATCHES - 1, mask, zero)
        rescue &= ~subsets
        alive = ~won
        non_won.append(int(np.count_nonzero(alive)))
        rescue_sum.append(int(np.bitwise_count(rescue[alive]).sum(dtype=np.int64)))
    return ComponentStats(number_count, tuple(non_won), tuple(rescue_sum))


def combine_component_stats(first: ComponentStats, second: ComponentStats) -> tuple[int, int]:
    """Exact (OFFICIAL_ANY_PRIZE count, M3+ draw count) of the disjoint-number union.

    A main draw splits as ``a`` numbers of the first component and ``6 - a`` of
    the second. It is an M3+ draw unless both parts are non-winning; otherwise
    its rescued specials are the disjoint union of the two components' rescues.
    """

    if first.number_count + second.number_count != BIG_LOTTO_POOL_SIZE:
        raise ValueError("components must cover the whole number pool")
    count = 0
    m3_plus = 0
    for size in range(BIG_LOTTO_DRAW_SIZE + 1):
        other = BIG_LOTTO_DRAW_SIZE - size
        total = comb(first.number_count, size) * comb(second.number_count, other)
        lost = first.non_won[size] * second.non_won[other]
        m3_plus += total - lost
        count += (
            SPECIAL_COUNT * (total - lost)
            + first.non_won[size] * second.rescue_sum[other]
            + first.rescue_sum[size] * second.non_won[other]
        )
    return count, m3_plus


def decomposed_score(portfolio: Sequence[Ticket], tables: DecompositionTables) -> tuple[int, int]:
    twelve = [ticket for ticket in portfolio if set(ticket) <= tables.twelve_numbers]
    eight = [ticket for ticket in portfolio if set(ticket) <= tables.eight_numbers]
    if len(twelve) + len(eight) != len(portfolio):
        raise CandidateInvariantError("a ticket crosses the component boundary")
    return combine_component_stats(
        component_stats(twelve, tables.twelve_subsets, len(tables.twelve_numbers)),
        component_stats(eight, tables.eight_subsets, len(tables.eight_numbers)),
    )


# --- resumable single-writer score checkpoint ---------------------------------------------


@dataclass(frozen=True, slots=True)
class ScoreRow:
    family: str
    index: int
    code: str
    count: int
    m3_plus: int


class ScoreCheckpoint:
    """Append-only JSONL: one identity header, then one exact score per candidate."""

    def __init__(self, path: Path, header: Mapping[str, object]) -> None:
        self.path = path
        self.header: dict[str, object] = {"kind": "header", **header}
        self._pending_sync = 0

    def load(self) -> dict[tuple[str, int], ScoreRow]:
        raw = self.path.read_bytes() if self.path.exists() else b""
        if not raw.endswith(b"\n"):
            cut = raw.rfind(b"\n") + 1
            raw = raw[:cut]
            if self.path.exists():
                with self.path.open("r+b") as handle:
                    handle.truncate(cut)
        if not raw:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._write_line(json.dumps(self.header, sort_keys=True), sync=True)
            return {}
        lines = raw.decode("utf-8").splitlines()
        if json.loads(lines[0]) != self.header:
            raise CheckpointIdentityError(f"{self.path} header does not match this search")
        rows: dict[tuple[str, int], ScoreRow] = {}
        for line in lines[1:]:
            data = cast(dict[str, object], json.loads(line))
            family, index, code = data.get("f"), data.get("i"), data.get("k")
            count, m3_plus = data.get("c"), data.get("m3")
            if not (
                isinstance(family, str)
                and isinstance(code, str)
                and type(index) is int
                and type(count) is int
                and type(m3_plus) is int
            ):
                raise CheckpointIdentityError(f"malformed checkpoint row: {line}")
            row = ScoreRow(family, index, code, count, m3_plus)
            if rows.get((family, index), row) != row:
                raise CheckpointIdentityError(f"conflicting rows for {(family, index)}")
            rows[(family, index)] = row
        return rows

    def append(self, row: ScoreRow) -> None:
        payload = {"f": row.family, "i": row.index, "k": row.code, "c": row.count}
        payload["m3"] = row.m3_plus
        self._pending_sync += 1
        self._write_line(json.dumps(payload), sync=self._pending_sync >= _FSYNC_EVERY)

    def sync(self) -> None:
        self._write_line(None, sync=True)

    def _write_line(self, line: str | None, *, sync: bool) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            if line is not None:
                handle.write(line + "\n")
            handle.flush()
            if sync:
                os.fsync(handle.fileno())
                self._pending_sync = 0


@dataclass(slots=True)
class _WorkerContext:
    memory: SharedMemory
    draws: DrawMasks
    tables: DecompositionTables


_worker_context: _WorkerContext | None = None


def _attach_draws(memory: SharedMemory, draw_count: int) -> DrawMasks:
    buffer = memory.buf
    if buffer is None:
        raise RuntimeError("shared draw-space buffer is unavailable")
    draws: DrawMasks = np.frombuffer(buffer, dtype=np.uint64, count=draw_count)
    return draws


def _init_worker(
    memory_name: str,
    draw_count: int,
    twelve_numbers: tuple[int, ...],
    eight_numbers: tuple[int, ...],
) -> None:
    global _worker_context
    memory = SharedMemory(name=memory_name, track=False)
    draws = _attach_draws(memory, draw_count)
    _worker_context = _WorkerContext(
        memory, draws, decomposition_tables(twelve_numbers, eight_numbers)
    )


def _score_job(job: ScoreJob) -> ScoreReply:
    if _worker_context is None:
        raise RuntimeError("worker draw space is not attached")
    family, index, code, portfolio = job
    exact = evaluate_portfolio(portfolio, draws=_worker_context.draws)
    count, m3_plus = decomposed_score(portfolio, _worker_context.tables)
    return (
        family,
        index,
        code,
        exact.official_any_prize_outcome_count,
        exact.m3_plus_draw_count,
        count,
        m3_plus,
    )


@contextmanager
def shared_draw_space() -> Generator[tuple[SharedMemory, DrawMasks]]:
    """One complete main-draw space in shared memory, attached read-only by every worker."""

    draws = all_main_draw_masks(BIG_LOTTO_POOL_SIZE, BIG_LOTTO_DRAW_SIZE)
    memory = SharedMemory(create=True, size=draws.nbytes)
    try:
        view = _attach_draws(memory, draws.size)
        view[:] = draws
        del draws
        view.flags.writeable = False
        yield memory, view
    finally:
        with suppress(BufferError):
            memory.close()
        memory.unlink()


def _score_pending(
    pending: Sequence[ScoreJob],
    *,
    memory_name: str,
    structure: Structure,
    workers: int,
    checkpoint: ScoreCheckpoint,
    completed: dict[tuple[str, int], ScoreRow],
) -> int:
    if not pending:
        return 0
    started = time.monotonic()
    scored = 0
    draw_count = comb(BIG_LOTTO_POOL_SIZE, BIG_LOTTO_DRAW_SIZE)
    with get_context("spawn").Pool(
        processes=workers,
        initializer=_init_worker,
        initargs=(memory_name, draw_count, structure.twelve.numbers, structure.eight.numbers),
    ) as pool:
        for reply in pool.imap_unordered(_score_job, pending, chunksize=2):
            family, index, code, count, m3_plus, decomposed_count, decomposed_m3 = reply
            if (count, m3_plus) != (decomposed_count, decomposed_m3):
                raise ScoreCrossCheckError(
                    f"{family}[{index}] evaluator {count}/{m3_plus} != "
                    f"decomposition {decomposed_count}/{decomposed_m3}"
                )
            row = ScoreRow(family, index, code, count, m3_plus)
            checkpoint.append(row)
            completed[(family, index)] = row
            scored += 1
            if scored % _PROGRESS_EVERY == 0 or scored == len(pending):
                elapsed = time.monotonic() - started
                print(f"[{elapsed:.0f}s] scored {scored}/{len(pending)} pending", flush=True)
    checkpoint.sync()
    return scored


# --- result assembly ----------------------------------------------------------------------


def source_identity(repo_root: Path) -> dict[str, object]:
    def git(*arguments: str) -> str:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), *arguments],
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()

    if git("status", "--porcelain", "--", AUTHORITY_RESULT_PATH, EVALUATOR_PATH):
        raise SourceAuthorityDriftError("authority or evaluator differs from the source commit")
    return {
        "SOURCE_HEAD": git("rev-parse", "HEAD"),
        "SOURCE_TREE": git("rev-parse", "HEAD^{tree}"),
        "AUTHORITY_AND_EVALUATOR_CLEAN_AT_SOURCE_HEAD": True,
    }


def orbit_constant_crosscheck(
    structure: Structure, space: FamilyBSpace, tables: DecompositionTables
) -> dict[int, tuple[int, int]]:
    """Decomposition count of every raw 8-side graph; must be constant on each orbit."""

    twelve_tickets = [structure.baseline[slot] for slot in structure.twelve.slots]
    twelve_stats = component_stats(
        twelve_tickets, tables.twelve_subsets, len(tables.twelve_numbers)
    )
    per_orbit: dict[int, tuple[int, int]] = {}
    for graph, orbit, _ in space.quotient.assignments:
        candidate = build_candidate(structure, FAMILY_B, mask_to_edges(graph, 8))
        eight_tickets = [candidate[slot] for slot in structure.eight.slots]
        value = combine_component_stats(
            twelve_stats,
            component_stats(eight_tickets, tables.eight_subsets, len(tables.eight_numbers)),
        )
        if per_orbit.setdefault(orbit, value) != value:
            raise QuotientUnresolvedError(f"decomposition count is not constant on orbit {orbit}")
    return per_orbit


def candidate_record(
    family: str,
    index: int,
    portfolio: Portfolio,
    row: ScoreRow,
    baseline_count: int,
    profile: OverlapProfile,
) -> dict[str, object]:
    normalized = normalize_portfolio(portfolio)
    return {
        "FAMILY": family,
        "INDEX": index,
        "CODE": row.code,
        "OFFICIAL_ANY_PRIZE_OUTCOME_COUNT": row.count,
        "DELTA_VS_BASELINE": row.count - baseline_count,
        "M3_PLUS_DRAW_COUNT": row.m3_plus,
        "SPECIAL_RESCUE_OUTCOMES": row.count - SPECIAL_COUNT * row.m3_plus,
        "MAX_TICKET_PAIR_OVERLAP": profile.max_overlap,
        "PAIR_OVERLAP_HISTOGRAM": profile.histogram(),
        "NORMALIZED_SHA256": portfolio_sha256(normalized),
        "TICKETS": [list(ticket) for ticket in normalized],
    }


def _baseline_comparison(counts: Sequence[int], baseline_count: int) -> dict[str, int]:
    return {
        "ABOVE_BASELINE": sum(1 for count in counts if count > baseline_count),
        "EQUAL_BASELINE": sum(1 for count in counts if count == baseline_count),
        "BELOW_BASELINE": sum(1 for count in counts if count < baseline_count),
    }


def ledger_sha256(ledger: Sequence[Sequence[object]]) -> str:
    return hashlib.sha256(json.dumps(ledger, separators=(",", ":")).encode()).hexdigest()


def component_identity_section(structure: Structure) -> dict[str, object]:
    twelve, eight = structure.twelve, structure.eight
    return {
        "STATUS": "PASS",
        "COMPONENT_SIZES": [len(twelve.slots), len(eight.slots)],
        "USED_NUMBERS": len(twelve.numbers) + len(eight.numbers),
        "FREQUENCY_PROFILE": {"3": FREQUENCY_PROFILE[3], "2": FREQUENCY_PROFILE[2]},
        "LOCAL_SLOT_CONVENTION": (
            "local slot k of a component is its k-th ticket in normalized baseline order"
        ),
        "TWELVE_SIDE": {
            "GLOBAL_SLOTS": list(twelve.slots),
            "NUMBERS": list(twelve.numbers),
            "F3_SUPPORT_COUNT": len(twelve.f3_supports),
            "F2_SUPPORT_COUNT": len(twelve.f2_labels),
            "F3_SUPPORTS_PER_SLOT": 5,
            "F2_SUPPORTS_PER_SLOT": 1,
            "F2_SUPPORTS_FORM_PERFECT_MATCHING": True,
            "F3_SUPPORTS": [[number, list(triple)] for number, triple in twelve.f3_supports],
            "F2_LABELS": list(twelve.f2_labels),
            "BASELINE_F2_MATCHING": [list(edge) for edge in twelve.baseline_f2_edges],
        },
        "EIGHT_SIDE": {
            "GLOBAL_SLOTS": list(eight.slots),
            "NUMBERS": list(eight.numbers),
            "F3_SUPPORT_COUNT": len(eight.f3_supports),
            "F3_SUPPORTS_DISJOINT": True,
            "F2_SUPPORT_COUNT": len(eight.f2_labels),
            "F3_BEARING_SLOTS": list(eight.f3_bearing_slots),
            "NON_F3_SLOTS": list(structure.eight_non_f3_slots),
            "F2_DEGREE_TARGETS": list(structure.eight_f2_degree_targets),
            "F3_SUPPORTS": [[number, list(triple)] for number, triple in eight.f3_supports],
            "F2_LABELS": list(eight.f2_labels),
            "BASELINE_F2_EDGES": [list(edge) for edge in eight.baseline_f2_edges],
        },
    }


def family_a_section(
    space: FamilyASpace, rows: Mapping[int, ScoreRow], baseline_count: int
) -> tuple[dict[str, object], dict[str, object]]:
    best = min(space.legal, key=lambda candidate: (-rows[candidate.index].count, candidate.index))
    best_record = candidate_record(
        FAMILY_A, best.index, best.portfolio, rows[best.index], baseline_count, best.profile
    )
    best_record["RETAINED_BASELINE_MATCHING_EDGES"] = best.retained
    best_record["F2_MATCHING"] = [list(edge) for edge in best.matching]
    counts = [rows[candidate.index].count for candidate in space.legal]
    groups: list[dict[str, object]] = []
    for retained in sorted({candidate.retained for candidate in space.legal}):
        members = [candidate for candidate in space.legal if candidate.retained == retained]
        member_counts = [rows[candidate.index].count for candidate in members]
        leader = min(members, key=lambda candidate: (-rows[candidate.index].count, candidate.index))
        groups.append(
            {
                "RETAINED_BASELINE_MATCHING_EDGES": retained,
                "CANDIDATES": len(members),
                "BEST_COUNT": max(member_counts),
                "BEST_DELTA": max(member_counts) - baseline_count,
                "BEST_INDEX": leader.index,
                "WORST_COUNT": min(member_counts),
                "COUNT_SUM": sum(member_counts),
                **_baseline_comparison(member_counts, baseline_count),
            }
        )
    ledger: list[list[object]] = [
        [
            candidate.index,
            candidate.code,
            rows[candidate.index].count,
            rows[candidate.index].m3_plus,
            candidate.retained,
            candidate.profile.max_overlap,
            candidate.profile.overlap_0,
            candidate.profile.overlap_1,
            candidate.profile.overlap_2_plus,
        ]
        for candidate in space.legal
    ]
    max_overlaps = Counter(candidate.profile.max_overlap for candidate in space.legal)
    section: dict[str, object] = {
        "DEFINITION": (
            "Freeze all 20 twelve-side F3 supports and the whole 8-side component; the six "
            "twelve-side F2 supports range over every perfect matching of the 12 slots."
        ),
        "LABEL_ASSIGNMENT": "ascending F2 labels to lexicographically sorted matching edges",
        "RAW_MATCHINGS": space.raw_count,
        "CLOSED_FORM_ODD_DOUBLE_FACTORIAL": space.closed_form_count,
        "LEGAL": len(space.legal),
        "ILLEGAL": len(space.illegal_indices),
        "ILLEGAL_INDICES": list(space.illegal_indices),
        "SCORED": len(space.legal),
        "BASELINE_MATCHING_INDEX": space.baseline_index,
        "BASELINE_MATCHING_COUNT": rows[space.baseline_index].count,
        "BEST_COUNT": best_record["OFFICIAL_ANY_PRIZE_OUTCOME_COUNT"],
        "BEST_DELTA": best_record["DELTA_VS_BASELINE"],
        "BEST_SHA256": best_record["NORMALIZED_SHA256"],
        "BEST_TIE_COUNT": counts.count(max(counts)),
        "WORST_COUNT": min(counts),
        **_baseline_comparison(counts, baseline_count),
        "MAX_TICKET_PAIR_OVERLAP_DISTRIBUTION": {
            str(overlap): max_overlaps[overlap] for overlap in sorted(max_overlaps)
        },
        "BEST": best_record,
        "GROUPS_BY_RETAINED_BASELINE_MATCHING_EDGES": groups,
        "LEDGER_COLUMNS": [
            "INDEX",
            "PARTNER_CODE",
            "OFFICIAL_ANY_PRIZE_OUTCOME_COUNT",
            "M3_PLUS_DRAW_COUNT",
            "RETAINED_BASELINE_MATCHING_EDGES",
            "MAX_TICKET_PAIR_OVERLAP",
            "COUNT_PAIR_OVERLAP_0",
            "COUNT_PAIR_OVERLAP_1",
            "COUNT_PAIR_OVERLAP_2_PLUS",
        ],
        "PARTNER_CODE_CONVENTION": "character k is the base-36 local partner slot of local slot k",
        "LEDGER_SHA256": ledger_sha256(ledger),
        "LEDGER": ledger,
    }
    return section, best_record


def family_b_section(
    structure: Structure,
    space: FamilyBSpace,
    rows: Mapping[int, ScoreRow],
    profiles: Mapping[int, OverlapProfile],
    baseline_count: int,
) -> tuple[dict[str, object], dict[str, object]]:
    quotient = space.quotient
    baseline_orbit = quotient.assignments[space.graphs.index(space.baseline_graph)][1]
    portfolios = {
        orbit: build_candidate(
            structure, FAMILY_B, mask_to_edges(quotient.representatives[orbit], 8)
        )
        for orbit in profiles
    }
    orbits: list[dict[str, object]] = []
    for orbit, representative in enumerate(quotient.representatives):
        entry: dict[str, object] = {
            "ORBIT_INDEX": orbit,
            "REPRESENTATIVE_MASK": f"{representative:07x}",
            "REPRESENTATIVE_F2_EDGES": [list(edge) for edge in mask_to_edges(representative, 8)],
            "ORBIT_SIZE": quotient.orbit_sizes[orbit],
            "STABILIZER_ORDER": len(space.group) // quotient.orbit_sizes[orbit],
            "CONTAINS_BASELINE_GRAPH": orbit == baseline_orbit,
            "LEGAL": orbit in profiles,
        }
        if orbit in profiles:
            record = candidate_record(
                FAMILY_B, orbit, portfolios[orbit], rows[orbit], baseline_count, profiles[orbit]
            )
            entry.update({key: value for key, value in record.items() if key != "TICKETS"})
        orbits.append(entry)
    best = min(profiles, key=lambda orbit: (-rows[orbit].count, orbit))
    best_record = candidate_record(
        FAMILY_B, best, portfolios[best], rows[best], baseline_count, profiles[best]
    )
    best_record["F2_EDGES"] = [
        list(edge) for edge in mask_to_edges(quotient.representatives[best], 8)
    ]
    best_record["ORBIT_SIZE"] = quotient.orbit_sizes[best]
    counts = [rows[orbit].count for orbit in profiles]
    witnesses: list[list[object]] = [
        [position, f"{graph:07x}", orbit, "".join(str(vertex) for vertex in witness)]
        for position, (graph, orbit, witness) in enumerate(quotient.assignments)
    ]
    section: dict[str, object] = {
        "DEFINITION": (
            "Freeze both eight-side F3 supports and the whole 12-side component; the 21 "
            "eight-side F2 supports range over every simple graph on the 8 slots whose "
            "F3-bearing slots have degree 5 and non-F3 slots have degree 6."
        ),
        "LABEL_ASSIGNMENT": "ascending F2 labels to lexicographically sorted graph edges",
        "MASK_CONVENTION": "bit k is the k-th lexicographic pair of local slots 0..7",
        "RAW_GRAPHS": len(space.graphs),
        "RAW_GRAPHS_BRUTE_FORCE_COMPLEMENT_COUNT": space.brute_force_count,
        "LEGAL_RAW_GRAPHS": space.legal_raw_count,
        "AUTOMORPHISM_GROUP_DEFINITION": (
            "all permutations of the 8 local slots preserving the unordered pair of disjoint "
            "F3 triples and the unordered pair of non-F3 slots (filtered from all 8!)"
        ),
        "AUTOMORPHISM_GROUP_ORDER": len(space.group),
        "AUTOMORPHISM_GROUP_CLOSURE": "PASS",
        "ORBIT_REPRESENTATIVES": len(quotient.representatives),
        "BURNSIDE_ORBIT_COUNT": space.burnside_orbit_count,
        "ORBIT_COVERAGE": "PASS",
        "GRAPH_RELABEL_WITNESSES": "PASS",
        "PORTFOLIO_RELABEL_WITNESSES": "PASS",
        "ORBIT_CONSTANT_COMPONENT_DECOMPOSITION": "PASS",
        "REPRESENTATIVE_RULE": "least edge mask in the orbit; witness = first group element",
        "BASELINE_GRAPH_MASK": f"{space.baseline_graph:07x}",
        "BASELINE_ORBIT_INDEX": baseline_orbit,
        "BASELINE_ORBIT_COUNT": rows[baseline_orbit].count,
        "SCORED_REPRESENTATIVES": len(profiles),
        "BEST_COUNT": best_record["OFFICIAL_ANY_PRIZE_OUTCOME_COUNT"],
        "BEST_DELTA": best_record["DELTA_VS_BASELINE"],
        "BEST_SHA256": best_record["NORMALIZED_SHA256"],
        "BEST_TIE_COUNT": counts.count(max(counts)),
        "WORST_COUNT": min(counts),
        **_baseline_comparison(counts, baseline_count),
        "BEST": best_record,
        "ORBITS": orbits,
        "WITNESS_COLUMNS": ["GRAPH_INDEX", "GRAPH_MASK", "ORBIT_INDEX", "SLOT_PERMUTATION"],
        "SLOT_PERMUTATION_CONVENTION": "character v is the image of local slot v",
        "WITNESSES_SHA256": ledger_sha256(witnesses),
        "WITNESSES": witnesses,
    }
    return section, best_record


def render_json(value: object, indent: int = 0) -> str:
    """Indented JSON whose scalar-only lists stay on one line."""

    pad = "  " * indent
    inner = "  " * (indent + 1)
    if isinstance(value, dict):
        items = cast(dict[str, object], value)
        if not items:
            return "{}"
        body = ",\n".join(
            f"{inner}{json.dumps(key)}: {render_json(item, indent + 1)}"
            for key, item in items.items()
        )
        return "{\n" + body + "\n" + pad + "}"
    if isinstance(value, list):
        elements = cast(list[object], value)
        if all(not isinstance(element, dict | list) for element in elements):
            return json.dumps(elements, separators=(",", ":"))
        body = ",\n".join(inner + render_json(element, indent + 1) for element in elements)
        return "[\n" + body + "\n" + pad + "]"
    return json.dumps(value)


def run(
    repo_root: Path, checkpoint_dir: Path, workers: int, execution_id: str
) -> dict[str, object]:
    started = time.monotonic()
    output = repo_root / RESULT_PATH
    if output.exists():
        raise FileExistsError(f"{output} exists; refusing to overwrite a result")
    authority = load_authority(repo_root)
    source = source_identity(repo_root)
    evaluator_sha256 = file_sha256(repo_root / EVALUATOR_PATH)
    structure = derive_structure(authority.portfolio)
    family_a = build_family_a(structure)
    family_b = build_family_b(structure)
    tables = decomposition_tables(structure.twelve.numbers, structure.eight.numbers)
    orbit_decomposition = orbit_constant_crosscheck(structure, family_b, tables)
    print(
        f"family A matchings={family_a.raw_count} legal={len(family_a.legal)}; family B "
        f"graphs={len(family_b.graphs)} group={len(family_b.group)} "
        f"orbits={len(family_b.quotient.representatives)}",
        flush=True,
    )

    representatives = family_b.quotient.representatives
    b_profiles: dict[int, OverlapProfile] = {}
    jobs: list[ScoreJob] = []
    for orbit, representative in enumerate(representatives):
        portfolio = build_candidate(structure, FAMILY_B, mask_to_edges(representative, 8))
        try:
            b_profiles[orbit] = check_candidate(structure, FAMILY_B, portfolio)
        except CandidateInvariantError:
            continue
        jobs.append((FAMILY_B, orbit, f"{representative:07x}", normalize_portfolio(portfolio)))
    jobs.extend(
        (FAMILY_A, candidate.index, candidate.code, normalize_portfolio(candidate.portfolio))
        for candidate in family_a.legal
    )
    expected_codes = {(family, index): code for family, index, code, _ in jobs}

    with shared_draw_space() as (memory, draws):
        draw_space_sha256 = hashlib.sha256(draws.tobytes()).hexdigest()
        baseline_exact = evaluate_portfolio(authority.portfolio, draws=draws)
        del draws
        if baseline_exact.official_any_prize_outcome_count != authority.count:
            raise SourceAuthorityDriftError("canonical rescore does not reproduce the baseline")
        baseline_pair = (
            baseline_exact.official_any_prize_outcome_count,
            baseline_exact.m3_plus_draw_count,
        )
        if decomposed_score(authority.portfolio, tables) != baseline_pair:
            raise ScoreCrossCheckError("baseline component decomposition disagrees")
        jobs_digest = ledger_sha256([[family, index, code] for family, index, code, _ in jobs])
        checkpoint = ScoreCheckpoint(
            checkpoint_dir / "family-scores.jsonl",
            {
                "task_id": TASK_ID,
                "search_definition_version": SEARCH_DEFINITION_VERSION,
                "baseline_sha256": authority.sha256,
                "authority_file_sha256": authority.file_sha256,
                "evaluator_sha256": evaluator_sha256,
                "draw_space_sha256": draw_space_sha256,
                "jobs_sha256": jobs_digest,
            },
        )
        completed = checkpoint.load()
        for key, row in completed.items():
            if expected_codes.get(key) != row.code:
                raise CheckpointIdentityError(f"checkpoint row {key} is not a job of this search")
        reused = len(completed)
        pending = [job for job in jobs if (job[0], job[1]) not in completed]
        print(f"jobs={len(jobs)} reused={reused} pending={len(pending)}", flush=True)
        scored = _score_pending(
            pending,
            memory_name=memory.name,
            structure=structure,
            workers=workers,
            checkpoint=checkpoint,
            completed=completed,
        )
    if set(completed) != set(expected_codes):
        raise CheckpointIdentityError("scored rows do not cover every job exactly")

    baseline_count = authority.count
    a_rows = {index: row for (family, index), row in completed.items() if family == FAMILY_A}
    b_rows = {index: row for (family, index), row in completed.items() if family == FAMILY_B}
    for orbit, row in b_rows.items():
        if orbit_decomposition[orbit] != (row.count, row.m3_plus):
            raise ScoreCrossCheckError(f"orbit {orbit} decomposition disagrees with its score")
    a_section, a_best = family_a_section(family_a, a_rows, baseline_count)
    b_section, b_best = family_b_section(structure, family_b, b_rows, b_profiles, baseline_count)
    if a_section["BASELINE_MATCHING_COUNT"] != baseline_count:
        raise ScoreCrossCheckError("baseline matching does not reproduce the baseline count")
    if b_section["BASELINE_ORBIT_COUNT"] != baseline_count:
        raise ScoreCrossCheckError("baseline orbit does not reproduce the baseline count")

    overall = min(
        (a_best, b_best),
        key=lambda record: (
            -cast(int, record["OFFICIAL_ANY_PRIZE_OUTCOME_COUNT"]),
            FAMILY_ORDER.index(cast(str, record["FAMILY"])),
        ),
    )
    winner = normalize_portfolio(cast(list[list[int]], overall["TICKETS"]))
    fresh = evaluate_portfolio(winner)
    if (fresh.official_any_prize_outcome_count, fresh.m3_plus_draw_count) != (
        overall["OFFICIAL_ANY_PRIZE_OUTCOME_COUNT"],
        overall["M3_PLUS_DRAW_COUNT"],
    ):
        raise ScoreCrossCheckError("winner fresh canonical recount disagrees")
    best_count = cast(int, overall["OFFICIAL_ANY_PRIZE_OUTCOME_COUNT"])
    strict_gain = best_count > baseline_count
    baseline_profile = pair_overlap_profile(authority.portfolio)

    result: dict[str, object] = {
        "SCHEMA_VERSION": 1,
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "COMPLETE",
        "SEARCH_DEFINITION_VERSION": SEARCH_DEFINITION_VERSION,
        "SOURCE_AUTHORITY": {
            **source,
            "AUTHORITY_RESULT_PATH": AUTHORITY_RESULT_PATH,
            "AUTHORITY_RESULT_FILE_SHA256": authority.file_sha256,
            "AUTHORITY_TASK_ID": authority.task_id,
            "AUTHORITY_FINAL_COUNT": authority.count,
            "AUTHORITY_FINAL_SHA256": authority.sha256,
            "EVALUATOR_PATH": EVALUATOR_PATH,
            "EVALUATOR_SHA256": evaluator_sha256,
            "SCORING_FUNCTION": SCORING_FUNCTION,
        },
        "DRAW_SPACE": {
            "MAIN_DRAW_COUNT": baseline_exact.main_draw_count,
            "SPECIAL_COUNT": baseline_exact.special_count,
            "TOTAL_OUTCOMES": baseline_exact.main_draw_count * baseline_exact.special_count,
            "SHA256": draw_space_sha256,
            "CONSTRUCTION": "all_main_draw_masks(49, 6) once, shared read-only by every worker",
        },
        "BASELINE": {
            "OFFICIAL_ANY_PRIZE_OUTCOME_COUNT": baseline_count,
            "NORMALIZED_SHA256": authority.sha256,
            "M3_PLUS_DRAW_COUNT": baseline_exact.m3_plus_draw_count,
            "SPECIAL_RESCUE_OUTCOMES": baseline_count
            - SPECIAL_COUNT * baseline_exact.m3_plus_draw_count,
            "CANONICAL_RESCORE": "PASS",
            "MAX_TICKET_PAIR_OVERLAP": baseline_profile.max_overlap,
            "PAIR_OVERLAP_HISTOGRAM": baseline_profile.histogram(),
            "TICKETS": [list(ticket) for ticket in authority.portfolio],
        },
        "COMPONENT_IDENTITY": component_identity_section(structure),
        "FAMILY_A_12_SIDE": a_section,
        "FAMILY_B_8_SIDE": b_section,
        "OVERALL_BEST": overall,
        "WINNER_FRESH_RECOUNT": {
            "STATUS": "PASS",
            "OFFICIAL_ANY_PRIZE_OUTCOME_COUNT": fresh.official_any_prize_outcome_count,
            "M3_PLUS_DRAW_COUNT": fresh.m3_plus_draw_count,
            "DRAW_SPACE": "freshly constructed by evaluate_portfolio(draws=None)",
        },
        "COMPONENT_DECOMPOSITION_CROSSCHECK": {
            "STATUS": "PASS",
            "METHOD": (
                "split every main draw into its 12-side and 8-side numbers and combine exact "
                "per-component non-winning counts and rescue sums"
            ),
            "SCORED_CANDIDATES_CHECKED": len(jobs),
            "BASELINE_CHECKED": True,
            "FAMILY_B_RAW_GRAPHS_CHECKED": len(family_b.graphs),
        },
        "STRICT_GAIN": "YES" if strict_gain else "NO",
        "FAMILY_STATUS": GAIN_STATUS if strict_gain else NO_GAIN_STATUS,
        "READY_FOR_N1_ASCENT": "YES" if strict_gain else "NO",
        "CLAIM_SCOPE": CLAIM_SCOPE,
        "EXECUTION": {
            "EXECUTION_ID": execution_id,
            "WORKERS": workers,
            "PYTHON": platform.python_version(),
            "NUMPY": np.__version__,
            "DRIVER_SHA256": file_sha256(Path(__file__)),
            "CHECKPOINT_FILE": str(checkpoint.path),
            "CHECKPOINT_ROWS_REUSED": reused,
            "CHECKPOINT_ROWS_SCORED_THIS_RUN": scored,
            "WALL_SECONDS_THIS_RUN": round(time.monotonic() - started),
        },
        "PUSH": "NOT RUN",
        "PR": "NOT CREATED",
        "PRODUCTION_MUTATION": "NONE",
        "GLOBAL_K20_OPTIMUM_STATUS": "UNKNOWN",
    }
    text = render_json(result) + "\n"
    if json.loads(text) != result:
        raise RuntimeError("result JSON does not round-trip")
    output.write_text(text, encoding="utf-8")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="B649 K20 12+8 component-internal F2 rewire")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--checkpoint-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--execution-id", default="")
    args = parser.parse_args(argv)
    try:
        result = run(
            Path(args.repo_root).resolve(),
            Path(args.checkpoint_dir).resolve(),
            int(args.workers),
            str(args.execution_id),
        )
    except StopError as error:
        print(error, flush=True)
        return 3
    family_a = cast(dict[str, object], result["FAMILY_A_12_SIDE"])
    family_b = cast(dict[str, object], result["FAMILY_B_8_SIDE"])
    overall = cast(dict[str, object], result["OVERALL_BEST"])
    for label, value in (
        ("FAMILY_A_BEST_COUNT", family_a["BEST_COUNT"]),
        ("FAMILY_A_BEST_DELTA", family_a["BEST_DELTA"]),
        ("FAMILY_B_BEST_COUNT", family_b["BEST_COUNT"]),
        ("FAMILY_B_BEST_DELTA", family_b["BEST_DELTA"]),
        ("OVERALL_BEST_COUNT", overall["OFFICIAL_ANY_PRIZE_OUTCOME_COUNT"]),
        ("OVERALL_BEST_DELTA", overall["DELTA_VS_BASELINE"]),
        ("STRICT_GAIN", result["STRICT_GAIN"]),
        ("FAMILY_STATUS", result["FAMILY_STATUS"]),
    ):
        print(f"{label}: {value}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
