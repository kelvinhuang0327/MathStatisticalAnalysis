"""Exactly evaluate the defined 11+9 single-bridge STS(13) family for the B649 K=20 portfolio.

A side: delete an unordered pair {p, q} from one of the two STS(13) designs. The 11 remaining
points are tickets; every surviving triple and every uncovered pair is one number. Slot a, the
third point of the deleted pair's triple, is left with five numbers.

B side: the nine edges of K3,3 or the triangular prism are tickets. Every vertex is one number on
its three edges, and every disjoint edge pair except the marked pair {b, c} is one number.

One bridge number joins slots a, b and c. Raw constructions are quotiented by verified design and
graph automorphisms; every raw construction is matched to its orbit representative through an
explicit number relabeling, and only representatives are scored by the official exact evaluator.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import subprocess
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from math import comb
from pathlib import Path
from typing import cast

import lottolab.research.b649_official_any_prize_exact as official_exact
from lottolab.research.b649_official_any_prize_exact import (
    all_main_draw_masks,
    evaluate_portfolio,
)

TASK_ID = "B649_K20_11_9_SINGLE_BRIDGE_STS13_FAMILY_EXACT_R1"
SCHEMA_VERSION = "B649_K20_11_9_SINGLE_BRIDGE_STS13_FAMILY_EXACT_R1_V1"
POINT_COUNT = 13
GRAPH_VERTEX_COUNT = 6
TICKET_SIZE = 6
NUMBER_COUNT = 49
PORTFOLIO_SIZE = 20
A_SLOT_COUNT = 11
DISJOINT_EDGE_PAIR_COUNT = 18
REPO_ROOT = Path(__file__).resolve().parents[3]
RECORD_PATH = (
    REPO_ROOT / "docs/research/matrix-native-results/"
    "b649-k20-11-9-single-bridge-sts13-family-exact-r1-result.json"
)

BASELINE_AUTHORITY_TASK_ID = "B649_K20_12_8_WINNER_TWO_TICKET_ASCENT_R1"
BASELINE_AUTHORITY_PATH = Path(
    "/Users/kelvin/.codex/worktrees/b649-k20-12-8-winner-two-ticket-ascent-r1/"
    "MathStatisticalAnalysis/docs/research/matrix-native-results/"
    "b649-k20-12-8-winner-two-ticket-ascent-r1-result.json"
)
BASELINE_AUTHORITY_FILE_SHA256 = "3d5d3f8f2389b66a9b2c45b0e345b81a0d9dc59d08ca9223519be70a055e5a00"
BASELINE_COUNT = 313_263_888
BASELINE_NORMALIZED_SHA256 = "eaed652900d101881b678a1515d2a366bff9de6723dbec2ec9c82fe0d0d7844c"

type Pair = tuple[int, int]
type Block = tuple[int, int, int]
type Design = tuple[Block, ...]
type Edge = tuple[int, int]
type MarkedPair = tuple[Edge, Edge]
type Permutation = tuple[int, ...]
type Ticket = tuple[int, ...]
type Portfolio = tuple[Ticket, ...]
type SlotKey = tuple[str, tuple[int, ...]]
type BlockKey = tuple[str, tuple[int, ...]]

# Both designs are copied verbatim from build_sts13_classes() of the validated 12+8 family.
STS13_SOURCE: dict[str, str] = {
    "TASK_ID": "B649_K20_OVERLAP_BLOCK_REPARTITION_12_8_EXHAUSTIVE_R1",
    "COMMIT": "82e88ada111bf6d0999ac9c0c167a160a6ae5df8",
    "PATH": "src/lottolab/research/b649_k20_overlap_block_repartition_12_8_exhaustive_r1.py",
    "BLOB": "b5d9dd41481762bad815e14119c6e7c39ce1d8e3",
    "FUNCTION": "build_sts13_classes",
}
STS13_DESIGNS_SHA256 = "ab9438ef501f32f186490c7ff9adf388f7672a55e7d013bde0ae0ea1bd03acca"
STS13_DESIGNS: dict[str, Design] = {
    "CYCLIC": (
        (0, 1, 4), (0, 2, 7), (0, 3, 12), (0, 5, 11), (0, 6, 8), (0, 9, 10), (1, 2, 5),
        (1, 3, 8), (1, 6, 12), (1, 7, 9), (1, 10, 11), (2, 3, 6), (2, 4, 9), (2, 8, 10),
        (2, 11, 12), (3, 4, 7), (3, 5, 10), (3, 9, 11), (4, 5, 8), (4, 6, 11), (4, 10, 12),
        (5, 6, 9), (5, 7, 12), (6, 7, 10), (7, 8, 11), (8, 9, 12),
    ),
    "NONCYCLIC": (
        (0, 1, 7), (0, 2, 4), (0, 3, 12), (0, 5, 11), (0, 6, 8), (0, 9, 10), (1, 2, 5),
        (1, 3, 8), (1, 4, 9), (1, 6, 12), (1, 10, 11), (2, 3, 6), (2, 7, 9), (2, 8, 10),
        (2, 11, 12), (3, 4, 7), (3, 5, 10), (3, 9, 11), (4, 5, 8), (4, 6, 11), (4, 10, 12),
        (5, 6, 9), (5, 7, 12), (6, 7, 10), (7, 8, 11), (8, 9, 12),
    ),
}  # fmt: skip
GRAPH_TEMPLATES: dict[str, tuple[Edge, ...]] = {
    "K3_3": tuple((left, right) for left in range(3) for right in range(3, 6)),
    "TRIANGULAR_PRISM": (
        (0, 1), (0, 2), (0, 3), (1, 2), (1, 4), (2, 5), (3, 4), (3, 5), (4, 5),
    ),
}  # fmt: skip
CTO_SCRATCH_REFERENCE: dict[str, object] = {
    "A_DELETED_PAIR_ORBITS": {"CYCLIC": 2, "NONCYCLIC": 17},
    "B_MARKED_PAIR_ORBITS": {"K3_3": 1, "TRIANGULAR_PRISM": 4},
    "REPRESENTATIVES_AT_MOST": 95,
}
EXPECTED_INVARIANTS: dict[str, object] = {
    "TICKET_COUNT": 20,
    "LEGAL_DISTINCT_TICKETS": True,
    "USED_NUMBER_COUNT": 49,
    "FREQUENCY_PROFILE": {"2": 27, "3": 22},
    "PAIRWISE_OVERLAP_HISTOGRAM": {"0": 97, "1": 93},
    "MAXIMUM_PAIRWISE_OVERLAP": 1,
    "CROSS_GROUP_OVERLAP_PAIRS": 2,
}
EXPECTED_BLOCK_KIND_COUNTS: dict[str, int] = {
    "A_TRIPLE": 15,
    "A_PAIR": 10,
    "B_VERTEX": 6,
    "B_PAIR": 17,
    "BRIDGE": 1,
}
_BLOCK_KIND_ORDER = {kind: rank for rank, kind in enumerate(EXPECTED_BLOCK_KIND_COUNTS)}


class RecordMismatchError(ValueError):
    """Raised when a written result record does not round-trip to the computed record."""


def _pair(left: int, right: int) -> Pair:
    return (left, right) if left < right else (right, left)


def _sha256_json(value: object) -> str:
    payload = json.dumps(value, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sts13_designs_sha256() -> str:
    """Hash the designs with the convention used to pin them to the 12+8 source."""

    return _sha256_json(
        {name: [list(block) for block in design] for name, design in STS13_DESIGNS.items()}
    )


def normalized_portfolio_sha256(portfolio: Sequence[Sequence[int]]) -> str:
    """Hash compact JSON of sorted tickets in sorted order."""

    return _sha256_json(sorted(sorted(ticket) for ticket in portfolio))


def is_valid_sts13(design: Sequence[Block]) -> bool:
    """Return whether the blocks form a Steiner triple system on 0..12."""

    if len(design) != 26 or len(set(design)) != 26:
        return False
    if any(
        len(block) != 3
        or tuple(sorted(block)) != block
        or len(set(block)) != 3
        or any(point < 0 or point >= POINT_COUNT for point in block)
        for block in design
    ):
        return False
    pair_counts = Counter(pair for block in design for pair in itertools.combinations(block, 2))
    return len(pair_counts) == comb(POINT_COUNT, 2) and all(
        count == 1 for count in pair_counts.values()
    )


def pasch_count(design: Design) -> int:
    """Count four-block Pasch configurations."""

    count = 0
    for selected in itertools.combinations(design, 4):
        point_counts = Counter(point for block in selected for point in block)
        if len(point_counts) == 6 and all(value == 2 for value in point_counts.values()):
            count += 1
    return count


def third_point_table(design: Design) -> dict[Pair, int]:
    table: dict[Pair, int] = {}
    for block in design:
        for left, right in itertools.combinations(block, 2):
            table[(left, right)] = next(point for point in block if point not in (left, right))
    return table


def _compose(left: Permutation, right: Permutation) -> Permutation:
    """Return the permutation applying right first, then left."""

    return tuple(left[point] for point in right)


def _verify_group(elements: Sequence[Permutation], degree: int) -> None:
    members = set(elements)
    if len(members) != len(elements):
        raise ValueError("automorphism list contains duplicates")
    if any(sorted(element) != list(range(degree)) for element in elements):
        raise ValueError("automorphism is not a permutation")
    if tuple(range(degree)) not in members:
        raise ValueError("automorphism set lacks the identity")
    if any(_compose(left, right) not in members for left in elements for right in elements):
        raise ValueError("automorphism set is not closed under composition")


def _close_point_map(third: Mapping[Pair, int], seed: Mapping[int, int]) -> Permutation | None:
    mapping = dict(seed)
    if len(set(mapping.values())) != len(mapping):
        return None
    changed = True
    while changed:
        changed = False
        for left, right in itertools.combinations(sorted(mapping), 2):
            source = third[(left, right)]
            image = third[_pair(mapping[left], mapping[right])]
            if source in mapping:
                if mapping[source] != image:
                    return None
            elif image in mapping.values():
                return None
            else:
                mapping[source] = image
                changed = True
    if len(mapping) != POINT_COUNT:
        raise ValueError("generating triple did not close onto all 13 points")
    return tuple(mapping[point] for point in range(POINT_COUNT))


def sts13_automorphisms(design: Design) -> tuple[Permutation, ...]:
    """Enumerate the full automorphism group of an STS(13).

    Three non-collinear points generate the whole design, so an automorphism is determined by
    the images of one such triple. Every image triple is closed and kept only when the closed
    point map sends the block set onto itself.
    """

    if not is_valid_sts13(design):
        raise ValueError("automorphisms require a valid STS(13)")
    third = third_point_table(design)
    blocks = set(design)
    x, y = 0, 1
    z = next(point for point in range(POINT_COUNT) if point not in (x, y, third[(x, y)]))
    automorphisms: list[Permutation] = []
    for x_image, y_image in itertools.permutations(range(POINT_COUNT), 2):
        collinear = third[_pair(x_image, y_image)]
        for z_image in range(POINT_COUNT):
            if z_image in (x_image, y_image, collinear):
                continue
            permutation = _close_point_map(third, {x: x_image, y: y_image, z: z_image})
            if (
                permutation is not None
                and {
                    cast(Block, tuple(sorted(permutation[point] for point in block)))
                    for block in design
                }
                == blocks
            ):
                automorphisms.append(permutation)
    group = tuple(sorted(automorphisms))
    _verify_group(group, POINT_COUNT)
    return group


def validate_cubic_template(edges: Sequence[Edge]) -> None:
    if len(edges) != 9 or len(set(edges)) != 9:
        raise ValueError("cubic template must have nine distinct edges")
    if any(not 0 <= left < right < GRAPH_VERTEX_COUNT for left, right in edges):
        raise ValueError("template edges must be sorted vertex pairs on 0..5")
    degrees = Counter(vertex for edge in edges for vertex in edge)
    if any(degrees[vertex] != 3 for vertex in range(GRAPH_VERTEX_COUNT)):
        raise ValueError("template must be 3-regular on six vertices")


def triangle_count(edges: Sequence[Edge]) -> int:
    edge_set = set(edges)
    return sum(
        all(pair in edge_set for pair in itertools.combinations(triple, 2))
        for triple in itertools.combinations(range(GRAPH_VERTEX_COUNT), 3)
    )


def graph_automorphisms(edges: Sequence[Edge]) -> tuple[Permutation, ...]:
    """Enumerate every vertex permutation that maps the edge set onto itself."""

    validate_cubic_template(edges)
    edge_set = set(edges)
    group = tuple(
        permutation
        for permutation in itertools.permutations(range(GRAPH_VERTEX_COUNT))
        if {_pair(permutation[left], permutation[right]) for left, right in edges} == edge_set
    )
    _verify_group(group, GRAPH_VERTEX_COUNT)
    return group


def disjoint_edge_pairs(edges: Sequence[Edge]) -> tuple[MarkedPair, ...]:
    return tuple(
        (left, right)
        for left, right in itertools.combinations(sorted(edges), 2)
        if not set(left).intersection(right)
    )


def act_on_pair(permutation: Permutation, pair: Pair) -> Pair:
    return _pair(permutation[pair[0]], permutation[pair[1]])


def act_on_marked_pair(permutation: Permutation, marked: MarkedPair) -> MarkedPair:
    first = act_on_pair(permutation, marked[0])
    second = act_on_pair(permutation, marked[1])
    return (first, second) if first < second else (second, first)


@dataclass(frozen=True, slots=True)
class Orbit[T: (Pair, MarkedPair)]:
    representative: T
    members: tuple[T, ...]
    witnesses: tuple[Permutation, ...]  # witnesses[i] maps members[i] onto the representative


def orbit_partition[T: (Pair, MarkedPair)](
    items: Sequence[T],
    group: Sequence[Permutation],
    act: Callable[[Permutation, T], T],
) -> tuple[Orbit[T], ...]:
    """Partition items into group orbits with one verified mapping witness per member."""

    universe = set(items)
    if len(universe) != len(items):
        raise ValueError("orbit items must be distinct")
    assigned: set[T] = set()
    orbits: list[Orbit[T]] = []
    for item in sorted(universe):
        if item in assigned:
            continue
        members = tuple(sorted({act(element, item) for element in group}))
        if not universe.issuperset(members) or assigned.intersection(members):
            raise ValueError("orbit leaves the item set or overlaps another orbit")
        representative = members[0]
        witnesses: list[Permutation] = []
        for member in members:
            witness = next(
                (element for element in group if act(element, member) == representative), None
            )
            if witness is None:
                raise ValueError("orbit member has no witness onto its representative")
            witnesses.append(witness)
        orbits.append(Orbit(representative, members, tuple(witnesses)))
        assigned.update(members)
    if assigned != universe:
        raise ValueError("orbits do not cover every item")
    return tuple(orbits)


@dataclass(frozen=True, slots=True)
class Construction:
    sts_class: str
    deleted_pair: Pair
    bridge_a: int
    template: str
    marked_pair: MarkedPair
    slots: tuple[SlotKey, ...]
    blocks: tuple[BlockKey, ...]  # blocks[i] is number i + 1
    tickets: Portfolio  # tickets[i] belongs to slots[i]


def build_construction(
    sts_class: str,
    deleted_pair: Pair,
    template: str,
    marked_pair: MarkedPair,
) -> Construction:
    """Build one labeled 11+9 single-bridge portfolio exactly as the Packet defines it."""

    design = STS13_DESIGNS[sts_class]
    edges = GRAPH_TEMPLATES[template]
    third = third_point_table(design)
    if not 0 <= deleted_pair[0] < deleted_pair[1] < POINT_COUNT:
        raise ValueError("deleted pair must be a sorted pair of design points")
    if marked_pair not in disjoint_edge_pairs(edges):
        raise ValueError("marked pair must be two disjoint template edges")
    bridge_a = third[deleted_pair]

    incidence: dict[BlockKey, tuple[SlotKey, ...]] = {}

    def add(key: BlockKey, slots: tuple[SlotKey, ...]) -> None:
        if key in incidence:
            raise ValueError(f"duplicate number block {key}")
        incidence[key] = slots

    for block in design:
        survivors = tuple(point for point in block if point not in deleted_pair)
        if len(survivors) == 3:
            add(("A_TRIPLE", block), tuple(("A", (point,)) for point in block))
        elif len(survivors) == 2:
            add(("A_PAIR", survivors), tuple(("A", (point,)) for point in survivors))
    for vertex in range(GRAPH_VERTEX_COUNT):
        add(("B_VERTEX", (vertex,)), tuple(("B", edge) for edge in edges if vertex in edge))
    for first, second in disjoint_edge_pairs(edges):
        if (first, second) != marked_pair:
            add(("B_PAIR", first + second), (("B", first), ("B", second)))
    bridge_slots: tuple[SlotKey, ...] = (
        ("A", (bridge_a,)),
        ("B", marked_pair[0]),
        ("B", marked_pair[1]),
    )
    add(("BRIDGE", ()), bridge_slots)

    if dict(Counter(kind for kind, _ in incidence)) != EXPECTED_BLOCK_KIND_COUNTS:
        raise ValueError("number block kind counts differ from 15/10/6/17/1")
    slots: tuple[SlotKey, ...] = tuple(
        ("A", (point,)) for point in range(POINT_COUNT) if point not in deleted_pair
    ) + tuple(("B", edge) for edge in edges)
    blocks = tuple(sorted(incidence, key=lambda key: (_BLOCK_KIND_ORDER[key[0]], key[1])))
    members: dict[SlotKey, list[int]] = {slot: [] for slot in slots}
    for label, block in enumerate(blocks, start=1):
        for slot in incidence[block]:
            members[slot].append(label)
    for slot in slots:
        pre_bridge = len(members[slot]) - (slot in bridge_slots)
        if pre_bridge != (5 if slot in bridge_slots else 6):
            raise ValueError(f"slot {slot} has {pre_bridge} numbers before the bridge")
    return Construction(
        sts_class=sts_class,
        deleted_pair=deleted_pair,
        bridge_a=bridge_a,
        template=template,
        marked_pair=marked_pair,
        slots=slots,
        blocks=blocks,
        tickets=tuple(tuple(sorted(members[slot])) for slot in slots),
    )


def structural_invariants(portfolio: Portfolio) -> dict[str, object]:
    legal_distinct = (
        len(portfolio) == PORTFOLIO_SIZE
        and len(set(portfolio)) == PORTFOLIO_SIZE
        and all(
            len(ticket) == TICKET_SIZE
            and len(set(ticket)) == TICKET_SIZE
            and all(type(number) is int and 1 <= number <= NUMBER_COUNT for number in ticket)
            for ticket in portfolio
        )
    )
    frequency = Counter(number for ticket in portfolio for number in ticket)
    frequency_profile = Counter(frequency.values())
    overlaps = Counter(
        len(set(left).intersection(right)) for left, right in itertools.combinations(portfolio, 2)
    )
    cross_group = sum(
        bool(set(portfolio[left]).intersection(portfolio[right]))
        for left in range(min(A_SLOT_COUNT, len(portfolio)))
        for right in range(A_SLOT_COUNT, len(portfolio))
    )
    return {
        "TICKET_COUNT": len(portfolio),
        "LEGAL_DISTINCT_TICKETS": legal_distinct,
        "USED_NUMBER_COUNT": len(frequency),
        "FREQUENCY_PROFILE": {
            str(key): frequency_profile[key] for key in sorted(frequency_profile)
        },
        "PAIRWISE_OVERLAP_HISTOGRAM": {str(key): overlaps[key] for key in sorted(overlaps)},
        "MAXIMUM_PAIRWISE_OVERLAP": max(overlaps, default=0),
        "CROSS_GROUP_OVERLAP_PAIRS": cross_group,
    }


def _image_block_key(key: BlockKey, sigma: Permutation, tau: Permutation) -> BlockKey:
    kind, payload = key
    if kind in ("A_TRIPLE", "A_PAIR"):
        return (kind, tuple(sorted(sigma[point] for point in payload)))
    if kind == "B_VERTEX":
        return (kind, (tau[payload[0]],))
    if kind == "B_PAIR":
        first, second = act_on_marked_pair(
            tau, ((payload[0], payload[1]), (payload[2], payload[3]))
        )
        return (kind, first + second)
    if kind == "BRIDGE":
        return key
    raise ValueError(f"unknown number block kind {kind}")


def relabeling_witness(
    raw: Construction,
    representative: Construction,
    sigma: Permutation,
    tau: Permutation,
) -> dict[int, int] | None:
    """Return the number bijection induced by (sigma, tau) iff it maps raw tickets onto the
    representative's tickets; otherwise return None."""

    target = {block: label for label, block in enumerate(representative.blocks, start=1)}
    number_map: dict[int, int] = {}
    for label, block in enumerate(raw.blocks, start=1):
        image = target.get(_image_block_key(block, sigma, tau))
        if image is None:
            return None
        number_map[label] = image
    if sorted(number_map.values()) != list(range(1, NUMBER_COUNT + 1)):
        return None
    mapped = sorted(
        tuple(sorted(number_map[number] for number in ticket)) for ticket in raw.tickets
    )
    if mapped != sorted(representative.tickets):
        return None
    return number_map


@dataclass(frozen=True, slots=True)
class RepresentativeClass:
    construction: Construction
    a_orbit: Orbit[Pair]
    b_orbit: Orbit[MarkedPair]

    @property
    def weight(self) -> int:
        return len(self.a_orbit.members) * len(self.b_orbit.members)


@dataclass(frozen=True, slots=True)
class FamilyQuotient:
    representatives: tuple[RepresentativeClass, ...]
    sts_groups: dict[str, tuple[Permutation, ...]]
    graph_groups: dict[str, tuple[Permutation, ...]]
    a_orbits: dict[str, tuple[Orbit[Pair], ...]]
    b_orbits: dict[str, tuple[Orbit[MarkedPair], ...]]
    raw_construction_count: int
    raw_keys_equal_full_product: bool
    structural_invariant_passes: int
    relabeling_witnesses_verified: int


def expected_raw_construction_count() -> int:
    return (
        len(STS13_DESIGNS) * comb(POINT_COUNT, 2) * len(GRAPH_TEMPLATES) * DISJOINT_EDGE_PAIR_COUNT
    )


@lru_cache(maxsize=1)
def build_family_quotient() -> FamilyQuotient:
    """Quotient all raw constructions by verified automorphisms and prove each orbit member
    equivalent to its representative under an explicit number relabeling."""

    if sts13_designs_sha256() != STS13_DESIGNS_SHA256:
        raise ValueError("STS(13) designs differ from the validated 12+8 family source")
    if not all(is_valid_sts13(design) for design in STS13_DESIGNS.values()):
        raise ValueError("STS(13) input is not a valid design")
    for edges in GRAPH_TEMPLATES.values():
        if len(disjoint_edge_pairs(edges)) != DISJOINT_EDGE_PAIR_COUNT:
            raise ValueError("cubic template does not have 18 disjoint edge pairs")
    sts_groups = {name: sts13_automorphisms(design) for name, design in STS13_DESIGNS.items()}
    graph_groups = {name: graph_automorphisms(edges) for name, edges in GRAPH_TEMPLATES.items()}
    all_pairs = tuple(itertools.combinations(range(POINT_COUNT), 2))
    a_orbits = {
        name: orbit_partition(all_pairs, group, act_on_pair) for name, group in sts_groups.items()
    }
    b_orbits = {
        name: orbit_partition(disjoint_edge_pairs(GRAPH_TEMPLATES[name]), group, act_on_marked_pair)
        for name, group in graph_groups.items()
    }

    representatives: list[RepresentativeClass] = []
    raw_keys: list[tuple[str, Pair, str, MarkedPair]] = []
    invariant_passes = 0
    witnesses_verified = 0
    for sts_class in STS13_DESIGNS:
        for template in GRAPH_TEMPLATES:
            for a_orbit in a_orbits[sts_class]:
                for b_orbit in b_orbits[template]:
                    representative = build_construction(
                        sts_class, a_orbit.representative, template, b_orbit.representative
                    )
                    representatives.append(RepresentativeClass(representative, a_orbit, b_orbit))
                    for pair, sigma in zip(a_orbit.members, a_orbit.witnesses, strict=True):
                        for marked, tau in zip(b_orbit.members, b_orbit.witnesses, strict=True):
                            raw = build_construction(sts_class, pair, template, marked)
                            raw_keys.append((sts_class, pair, template, marked))
                            if structural_invariants(raw.tickets) != EXPECTED_INVARIANTS:
                                raise ValueError(f"raw construction fails invariants: {raw}")
                            invariant_passes += 1
                            if relabeling_witness(raw, representative, sigma, tau) is None:
                                raise ValueError(f"no relabeling witness for raw {raw}")
                            witnesses_verified += 1

    full_product = {
        (sts_class, pair, template, marked)
        for sts_class in STS13_DESIGNS
        for pair in all_pairs
        for template, edges in GRAPH_TEMPLATES.items()
        for marked in disjoint_edge_pairs(edges)
    }
    raw_keys_equal_full_product = len(raw_keys) == len(set(raw_keys)) and set(raw_keys) == (
        full_product
    )
    expected_raw = expected_raw_construction_count()
    if (
        not raw_keys_equal_full_product
        or len(raw_keys) != expected_raw
        or sum(row.weight for row in representatives) != expected_raw
        or invariant_passes != expected_raw
        or witnesses_verified != expected_raw
    ):
        raise ValueError("ORBIT_COVERAGE_UNRESOLVED")
    return FamilyQuotient(
        representatives=tuple(representatives),
        sts_groups=sts_groups,
        graph_groups=graph_groups,
        a_orbits=a_orbits,
        b_orbits=b_orbits,
        raw_construction_count=len(raw_keys),
        raw_keys_equal_full_product=raw_keys_equal_full_product,
        structural_invariant_passes=invariant_passes,
        relabeling_witnesses_verified=witnesses_verified,
    )


@dataclass(frozen=True, slots=True)
class ScoredRepresentative:
    representative: RepresentativeClass
    normalized_sha256: str
    official_any_prize_outcome_count: int


def _identity_key(construction: Construction) -> tuple[str, Pair, str, MarkedPair]:
    return (
        construction.sts_class,
        construction.deleted_pair,
        construction.template,
        construction.marked_pair,
    )


def select_best(scored: Sequence[ScoredRepresentative]) -> ScoredRepresentative:
    """Highest count, then smallest normalized SHA, then construction identity."""

    if not scored:
        raise ValueError("cannot select a best representative from no scores")
    return min(
        scored,
        key=lambda row: (
            -row.official_any_prize_outcome_count,
            row.normalized_sha256,
            _identity_key(row.representative.construction),
        ),
    )


def load_baseline(
    path: Path,
    *,
    expected_file_sha256: str = BASELINE_AUTHORITY_FILE_SHA256,
) -> Portfolio:
    """Load the handoff baseline after checking file and normalized portfolio identities."""

    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_file_sha256:
        raise ValueError("BASELINE_AUTHORITY_FILE_SHA256_MISMATCH")
    record = cast(dict[str, object], json.loads(data))
    if record.get("FINAL_COUNT") != BASELINE_COUNT:
        raise ValueError("BASELINE_AUTHORITY_COUNT_MISMATCH")
    if record.get("FINAL_SHA256") != BASELINE_NORMALIZED_SHA256:
        raise ValueError("BASELINE_AUTHORITY_PORTFOLIO_SHA_MISMATCH")
    raw_tickets = cast(list[list[int]], record.get("FINAL_TICKETS"))
    portfolio = tuple(tuple(int(number) for number in ticket) for ticket in raw_tickets)
    if len(portfolio) != PORTFOLIO_SIZE or any(len(ticket) != TICKET_SIZE for ticket in portfolio):
        raise ValueError("BASELINE_PORTFOLIO_SHAPE_MISMATCH")
    if normalized_portfolio_sha256(portfolio) != BASELINE_NORMALIZED_SHA256:
        raise ValueError("BASELINE_NORMALIZED_PORTFOLIO_SHA_MISMATCH")
    return portfolio


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _evaluator_path() -> Path:
    path = Path(official_exact.__file__).resolve()
    if not path.is_relative_to(REPO_ROOT):
        raise ValueError(f"official evaluator resolved outside this worktree: {path}")
    return path


def _git_head() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _marked_json(marked: MarkedPair) -> list[list[int]]:
    return [list(marked[0]), list(marked[1])]


def _orbit_coverage(quotient: FamilyQuotient) -> dict[str, object]:
    a_orbit_counts = {name: len(orbits) for name, orbits in quotient.a_orbits.items()}
    b_orbit_counts = {name: len(orbits) for name, orbits in quotient.b_orbits.items()}
    computed_reference = {
        "A_DELETED_PAIR_ORBITS": a_orbit_counts,
        "B_MARKED_PAIR_ORBITS": b_orbit_counts,
        "REPRESENTATIVES_AT_MOST": sum(a_orbit_counts.values()) * sum(b_orbit_counts.values()),
    }
    return {
        "STATUS": "PASS",
        "RAW_CONSTRUCTIONS_EXPECTED": expected_raw_construction_count(),
        "RAW_CONSTRUCTIONS_ENUMERATED": quotient.raw_construction_count,
        "RAW_CONSTRUCTION_KEYS_EQUAL_FULL_PRODUCT": quotient.raw_keys_equal_full_product,
        "REPRESENTATIVES": len(quotient.representatives),
        "ORBIT_WEIGHT_SUM": sum(row.weight for row in quotient.representatives),
        "STRUCTURAL_INVARIANT_PASSES_RAW": quotient.structural_invariant_passes,
        "EXPLICIT_RELABELING_WITNESSES_VERIFIED": quotient.relabeling_witnesses_verified,
        "QUOTIENT_GROUP": "Aut(STS13) x Aut(cubic template), each enumerated and group-verified",
        "STS13_AUTOMORPHISM_GROUP_ORDERS": {
            name: len(group) for name, group in quotient.sts_groups.items()
        },
        "GRAPH_AUTOMORPHISM_GROUP_ORDERS": {
            name: len(group) for name, group in quotient.graph_groups.items()
        },
        "A_DELETED_PAIR_ORBITS": {
            name: [
                {
                    "REPRESENTATIVE_PAIR": list(orbit.representative),
                    "BRIDGE_POINT_A": third_point_table(STS13_DESIGNS[name])[orbit.representative],
                    "SIZE": len(orbit.members),
                }
                for orbit in orbits
            ]
            for name, orbits in quotient.a_orbits.items()
        },
        "B_MARKED_PAIR_ORBITS": {
            name: [
                {
                    "REPRESENTATIVE_MARKED_PAIR": _marked_json(orbit.representative),
                    "SIZE": len(orbit.members),
                }
                for orbit in orbits
            ]
            for name, orbits in quotient.b_orbits.items()
        },
        "CTO_SCRATCH_REFERENCE": CTO_SCRATCH_REFERENCE,
        "CTO_SCRATCH_REFERENCE_MATCH": computed_reference == CTO_SCRATCH_REFERENCE,
    }


def _candidate_row(row: ScoredRepresentative) -> dict[str, object]:
    construction = row.representative.construction
    return {
        "STS_CLASS": construction.sts_class,
        "DELETED_PAIR": list(construction.deleted_pair),
        "BRIDGE_POINT_A": construction.bridge_a,
        "TEMPLATE": construction.template,
        "MARKED_EDGE_PAIR": _marked_json(construction.marked_pair),
        "A_ORBIT_SIZE": len(row.representative.a_orbit.members),
        "B_ORBIT_SIZE": len(row.representative.b_orbit.members),
        "ORBIT_WEIGHT": row.representative.weight,
        "NORMALIZED_PORTFOLIO_SHA256": row.normalized_sha256,
        "OFFICIAL_ANY_PRIZE_OUTCOME_COUNT": row.official_any_prize_outcome_count,
        "DELTA_VS_BASELINE": row.official_any_prize_outcome_count - BASELINE_COUNT,
    }


def _relabeling_invariance_spot_checks(
    quotient: FamilyQuotient,
    scored: Sequence[ScoredRepresentative],
    evaluate: Callable[[Portfolio], int],
) -> list[dict[str, object]]:
    """Score one non-representative raw member per (design, template) block."""

    checks: list[dict[str, object]] = []
    for sts_class in STS13_DESIGNS:
        for template in GRAPH_TEMPLATES:
            row = next(
                (
                    candidate
                    for candidate in scored
                    if candidate.representative.construction.sts_class == sts_class
                    and candidate.representative.construction.template == template
                    and candidate.representative.weight > 1
                ),
                None,
            )
            if row is None:
                continue
            raw = build_construction(
                sts_class,
                row.representative.a_orbit.members[-1],
                template,
                row.representative.b_orbit.members[-1],
            )
            raw_count = evaluate(raw.tickets)
            raw_sha = normalized_portfolio_sha256(raw.tickets)
            checks.append(
                {
                    "STS_CLASS": sts_class,
                    "TEMPLATE": template,
                    "RAW_DELETED_PAIR": list(raw.deleted_pair),
                    "RAW_MARKED_EDGE_PAIR": _marked_json(raw.marked_pair),
                    "RAW_NORMALIZED_PORTFOLIO_SHA256": raw_sha,
                    "REPRESENTATIVE_NORMALIZED_PORTFOLIO_SHA256": row.normalized_sha256,
                    "RAW_DIFFERS_FROM_REPRESENTATIVE_AS_LABELED": raw_sha != row.normalized_sha256,
                    "RAW_COUNT": raw_count,
                    "REPRESENTATIVE_COUNT": row.official_any_prize_outcome_count,
                    "STATUS": (
                        "PASS" if raw_count == row.official_any_prize_outcome_count else "FAIL"
                    ),
                }
            )
    if any(check["STATUS"] != "PASS" for check in checks):
        raise ValueError(f"RELABELING_INVARIANCE_SPOT_CHECK_FAILED: {checks}")
    return checks


def run_family(
    output_path: Path = RECORD_PATH,
    baseline_path: Path = BASELINE_AUTHORITY_PATH,
) -> dict[str, object]:
    if output_path.exists():
        raise FileExistsError(f"result already exists; refusing a second writer: {output_path}")
    evaluator_path = _evaluator_path()
    quotient = build_family_quotient()
    baseline = load_baseline(baseline_path)

    draws = all_main_draw_masks(NUMBER_COUNT, TICKET_SIZE)
    evaluations = 0

    def evaluate(portfolio: Portfolio) -> int:
        nonlocal evaluations
        evaluations += 1
        return evaluate_portfolio(portfolio, draws=draws).official_any_prize_outcome_count

    baseline_recount = evaluate(baseline)
    if baseline_recount != BASELINE_COUNT:
        raise ValueError(f"BASELINE_CANONICAL_RECOUNT_MISMATCH: {baseline_recount}")
    scored = tuple(
        ScoredRepresentative(
            representative=row,
            normalized_sha256=normalized_portfolio_sha256(row.construction.tickets),
            official_any_prize_outcome_count=evaluate(row.construction.tickets),
        )
        for row in quotient.representatives
    )
    representative_evaluations = len(scored)
    spot_checks = _relabeling_invariance_spot_checks(quotient, scored, evaluate)
    best = select_best(scored)
    # Fresh recount through a separately built draw space.
    fresh_recount = evaluate_portfolio(
        best.representative.construction.tickets
    ).official_any_prize_outcome_count
    evaluations += 1
    if fresh_recount != best.official_any_prize_outcome_count:
        raise ValueError("BEST_FRESH_CANONICAL_RECOUNT_MISMATCH")
    strict_gain = best.official_any_prize_outcome_count > BASELINE_COUNT
    best_construction = best.representative.construction

    record: dict[str, object] = {
        "SCHEMA_VERSION": SCHEMA_VERSION,
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "COMPLETE",
        "SOURCE_AUTHORITY": {
            "SOURCE_HEAD": _git_head(),
            "DRIVER_PATH": str(Path(__file__).resolve().relative_to(REPO_ROOT)),
            "DRIVER_SHA256": _file_sha256(Path(__file__).resolve()),
            "EVALUATOR_PATH": str(evaluator_path.relative_to(REPO_ROOT)),
            "EVALUATOR_SHA256": _file_sha256(evaluator_path),
            "EVALUATOR_FUNCTION": "evaluate_portfolio(...).official_any_prize_outcome_count",
        },
        "BASELINE": {
            "AUTHORITY_TASK_ID": BASELINE_AUTHORITY_TASK_ID,
            "AUTHORITY_PATH": str(baseline_path),
            "AUTHORITY_FILE_SHA256": BASELINE_AUTHORITY_FILE_SHA256,
            "COUNT": BASELINE_COUNT,
            "NORMALIZED_PORTFOLIO_SHA256": BASELINE_NORMALIZED_SHA256,
            "CANONICAL_RECOUNT": baseline_recount,
            "CANONICAL_RECOUNT_STATUS": "PASS",
        },
        "STS13_INPUTS": {
            "SOURCE": STS13_SOURCE,
            "DESIGNS_SHA256": sts13_designs_sha256(),
            "PASCH_COUNTS": {name: pasch_count(design) for name, design in STS13_DESIGNS.items()},
        },
        "GRAPH_TEMPLATES": {
            name: {"EDGES": [list(edge) for edge in edges], "TRIANGLES": triangle_count(edges)}
            for name, edges in GRAPH_TEMPLATES.items()
        },
        "STRUCTURAL_INVARIANTS": {
            "STATUS": "PASS",
            "RAW_CONSTRUCTIONS_CHECKED": quotient.structural_invariant_passes,
            "EXPECTED": EXPECTED_INVARIANTS,
            "BLOCK_KIND_COUNTS": EXPECTED_BLOCK_KIND_COUNTS,
        },
        "ORBIT_COVERAGE": _orbit_coverage(quotient),
        "REPRESENTATIVES_EVALUATED": representative_evaluations,
        "CANDIDATE_COUNTS": [_candidate_row(row) for row in scored],
        "RELABELING_INVARIANCE_SPOT_CHECKS": spot_checks,
        "BEST_COUNT": best.official_any_prize_outcome_count,
        "BEST_DELTA_VS_BASELINE": best.official_any_prize_outcome_count - BASELINE_COUNT,
        "BEST_NORMALIZED_PORTFOLIO_SHA256": best.normalized_sha256,
        "BEST_IDENTITY": {
            "STS_CLASS": best_construction.sts_class,
            "DELETED_PAIR": list(best_construction.deleted_pair),
            "BRIDGE_POINT_A": best_construction.bridge_a,
            "TEMPLATE": best_construction.template,
            "MARKED_EDGE_PAIR": _marked_json(best_construction.marked_pair),
        },
        "BEST_PORTFOLIO": [list(ticket) for ticket in best_construction.tickets],
        "BEST_FRESH_CANONICAL_RECOUNT": fresh_recount,
        "CANONICAL_RESCORE": "PASS",
        "CANONICAL_EVALUATIONS": {
            "BASELINE_RECOUNT": 1,
            "REPRESENTATIVES": representative_evaluations,
            "RELABELING_SPOT_CHECKS": len(spot_checks),
            "BEST_FRESH_RECOUNT": 1,
            "TOTAL": evaluations,
        },
        "FAMILY_COVERAGE_STATUS": "COMPLETE_FOR_DEFINED_FAMILY",
        "STRICT_GAIN": "YES" if strict_gain else "NO",
        "FAMILY_RESULT": "STRICT_GAIN_FOUND"
        if strict_gain
        else "NO_STRICT_GAIN_FOR_DEFINED_FAMILY",
        "READY_FOR_N1_ASCENT": "YES" if strict_gain else "NO",
        "CLAIM_SCOPE": (
            "Only the defined 11+9 single-bridge STS(13) family; not all 11+9 structures; "
            "global K20 optimality is not claimed."
        ),
        "PUSH": "NOT RUN",
        "PR": "NOT CREATED",
        "PRODUCTION_MUTATION": "NONE",
        "GLOBAL_K20_OPTIMUM_STATUS": "UNKNOWN",
    }
    write_and_verify_record(output_path, record)
    return record


def _json_normalized(value: object) -> object:
    return json.loads(json.dumps(value))


def _candidate_row_key(row: object) -> str:
    if not isinstance(row, dict):
        raise RecordMismatchError("candidate row is not an object")
    fields = cast(dict[str, object], row)
    return json.dumps(
        [
            fields.get("STS_CLASS"),
            fields.get("DELETED_PAIR"),
            fields.get("TEMPLATE"),
            fields.get("MARKED_EDGE_PAIR"),
        ],
        separators=(",", ":"),
    )


def _candidate_rows(record: Mapping[str, object]) -> list[object]:
    rows = record.get("CANDIDATE_COUNTS")
    if not isinstance(rows, list):
        raise RecordMismatchError("CANDIDATE_COUNTS is missing or not a list")
    return cast(list[object], rows)


def verify_record_round_trip(expected: Mapping[str, object], loaded: object) -> None:
    """Fail on any missing, duplicate, or changed value after tuple/list normalization."""

    normalized = cast(dict[str, object], _json_normalized(dict(expected)))
    if not isinstance(loaded, dict):
        raise RecordMismatchError("loaded record is not an object")
    loaded_record = cast(dict[str, object], loaded)

    expected_rows = _candidate_rows(normalized)
    loaded_rows = _candidate_rows(loaded_record)
    loaded_keys = [_candidate_row_key(row) for row in loaded_rows]
    duplicates = sorted(key for key, count in Counter(loaded_keys).items() if count > 1)
    if duplicates:
        raise RecordMismatchError(f"duplicate candidate rows: {duplicates}")
    expected_by_key = {_candidate_row_key(row): row for row in expected_rows}
    missing = sorted(set(expected_by_key) - set(loaded_keys))
    if missing:
        raise RecordMismatchError(f"missing candidate rows: {missing}")
    unexpected = sorted(set(loaded_keys) - set(expected_by_key))
    if unexpected:
        raise RecordMismatchError(f"unexpected candidate rows: {unexpected}")
    changed = sorted(
        key
        for key, row in zip(loaded_keys, loaded_rows, strict=True)
        if expected_by_key[key] != row
    )
    if changed:
        raise RecordMismatchError(f"changed candidate rows: {changed}")
    differing = sorted(
        field
        for field in set(normalized) | set(loaded_record)
        if normalized.get(field, KeyError) != loaded_record.get(field, KeyError)
    )
    if differing:
        raise RecordMismatchError(f"record fields differ after round trip: {differing}")

    counts = [
        cast(dict[str, object], row)["OFFICIAL_ANY_PRIZE_OUTCOME_COUNT"] for row in loaded_rows
    ]
    weights = [cast(dict[str, object], row)["ORBIT_WEIGHT"] for row in loaded_rows]
    coverage = cast(dict[str, object], loaded_record["ORBIT_COVERAGE"])
    if (
        len(loaded_rows) != loaded_record["REPRESENTATIVES_EVALUATED"]
        or sum(cast(list[int], weights)) != coverage["RAW_CONSTRUCTIONS_EXPECTED"]
        or max(cast(list[int], counts)) != loaded_record["BEST_COUNT"]
        or (loaded_record["STRICT_GAIN"] == "YES")
        != (cast(int, loaded_record["BEST_COUNT"]) > BASELINE_COUNT)
    ):
        raise RecordMismatchError("record is not internally consistent")


def write_and_verify_record(path: Path, record: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    verify_record_round_trip(record, json.loads(path.read_text(encoding="utf-8")))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=RECORD_PATH)
    parser.add_argument("--baseline", type=Path, default=BASELINE_AUTHORITY_PATH)
    args = parser.parse_args(argv)
    record = run_family(output_path=args.output, baseline_path=args.baseline)
    summary_fields = (
        "TASK_STATUS",
        "REPRESENTATIVES_EVALUATED",
        "BEST_COUNT",
        "BEST_DELTA_VS_BASELINE",
        "BEST_NORMALIZED_PORTFOLIO_SHA256",
        "BEST_IDENTITY",
        "BEST_FRESH_CANONICAL_RECOUNT",
        "CANONICAL_EVALUATIONS",
        "FAMILY_COVERAGE_STATUS",
        "STRICT_GAIN",
        "FAMILY_RESULT",
    )
    print(json.dumps({field: record[field] for field in summary_fields}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
