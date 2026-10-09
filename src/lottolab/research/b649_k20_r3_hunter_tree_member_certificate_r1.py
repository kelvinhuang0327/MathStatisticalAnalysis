"""Hunter spanning-tree union certificate for one K20 R3 state member (R1).

Scope is exactly one R7 region member of the R24 ledger: state
``state:s2-12692531-s3-681744``, member ``[0,13][5,5]`` (13 fully outside
tickets and five tickets of anchor type (0,1,1,4)).  For every portfolio in
that member, the 18 residual events ``R_C = E_C minus (E_A union E_B)`` obey
Hunter's inequality

    |union R_C| <= sum |R_C| - sum_{(C,D) in T} |R_C intersect R_D|

for every spanning tree ``T``.  Exact R8 four-event pair floors, a
threshold-graph rank floor and the forced label-collision mass give a correction
that holds for every portfolio of the member, not only for one witness.  The
correction is combined with the existing forest, pair-sum and rational
corrections by ``max``, never by a sum.

Every event count is re-derived by an independent 7-set counter: an official
any-prize win is ``|T intersect (D union {s})| >= 3``, and ``(D, s)`` maps
7-to-1 onto 7-sets.  No portfolio search, solver or outcome enumeration runs,
and no R3, R24 or R25 state is modified.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from hashlib import sha256
from itertools import combinations, pairwise, product
from math import comb
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_heavy_pair_r3plus_global_bound_r3 as heavy_pair
from lottolab.research import b649_k20_outside_min_s2_global_penalty_bound_r1 as r1
from lottolab.research import b649_k20_r3_anchor_incidence_bound_r5 as r5
from lottolab.research import b649_k20_r3_exact_anchor_neighborhood_envelope_r6 as r6
from lottolab.research import b649_k20_r3_frontier_realizability_bound_r8 as r8
from lottolab.research import b649_k20_r3_joint_residual_envelope_r7 as r7
from lottolab.research import b649_k20_r3_state_tail_owner_chase_r14 as r14

TASK_ID = "B649_K20_R3_HUNTER_TREE_MEMBER_CERTIFICATE_R1"
TASK_BRANCH = "codex/b649-k20-r3-hunter-tree-member-certificate-r1"
BASE_HEAD = "27614636ac4c20392619b3d9364d22bf2af9cff4"
BASE_TREE = "cd99dee2289867b45bc6142baed87d5e0dbab96a"
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS = "docs/research/matrix-native-results/"
MODULE_RELATIVE = "src/lottolab/research/b649_k20_r3_hunter_tree_member_certificate_r1.py"
RESULT_RELATIVE = RESULTS + "b649-k20-r3-hunter-tree-member-certificate-r1-result.json"
RESULT_PATH = REPO_ROOT / RESULT_RELATIVE
R24_RESULT_RELATIVE = RESULTS + "b649-k20-r3-tail-crossover-state-dynamic-chase-r24-result.json"
_SOURCES = "src/lottolab/research/"
UPSTREAM_SHA256 = {
    _SOURCES + "b649_k20_outside_min_s2_global_penalty_bound_r1.py": (
        "7706e57e77df6e786e77c4824f3c72663fdae73b20aa5f6797192689f2b6ea62"
    ),
    _SOURCES + "b649_k20_heavy_pair_r3plus_global_bound_r3.py": (
        "379f55ef87c2f7ffddc00caf7a7b5756810e1a3490ba3eb0d32327684f111139"
    ),
    _SOURCES + "b649_k20_r3_anchor_incidence_bound_r5.py": (
        "569d525f1e9905d043fe0f6132c936d5b260ba3d4b3a376da6c961db8aa5c435"
    ),
    _SOURCES + "b649_k20_r3_exact_anchor_neighborhood_envelope_r6.py": (
        "a83f6f2a7091aedf034e0905d80993df5001382fedc297fdd503202665e6622c"
    ),
    _SOURCES + "b649_k20_r3_joint_residual_envelope_r7.py": (
        "f376899a25bc287e45b80c3f5d9116db97f4c09de31ec81d0ccd2badf4222c50"
    ),
    _SOURCES + "b649_k20_r3_frontier_realizability_bound_r8.py": (
        "14884faf5b2e66c1f30d4e04e453ba5838b7f95815d70d8b7d45be47c5e9bd2b"
    ),
    _SOURCES + "b649_k20_r3_state_tail_owner_chase_r14.py": (
        "b30f6420eca033bc051ef35457993fc2588ee2e26cc1041363ced5d2c775ce99"
    ),
    _SOURCES + "b649_k20_r3_tail_crossover_state_dynamic_chase_r24.py": (
        "2a5e57a7319bd215f8cbc7f4db26453308a74c3f540c25787c44604aa39c8fd7"
    ),
    R24_RESULT_RELATIVE: "32182a3c3c803d95b3a7aee448f8ade3fadb291771affc9dca8beaab8147fc71",
}

STATE_ID = "state:s2-12692531-s3-681744"
REGION_SHA256 = "132cef5c91f5d6cf4798c8d8f65dba98d3851f33ec3d45b5d37fb7f61145ef15"
MEMBER_ID = "[0,13][5,5]"
MEMBER_SPARSE: tuple[tuple[int, int], ...] = ((0, 13), (5, 5))
SIBLING_SPARSE: tuple[tuple[int, int], ...] = ((0, 13), (5, 4), (16, 1))
TYPE_COUNT = 30
MEMBER_TYPE_CELLS: dict[int, tuple[int, int, int, int]] = {0: (0, 0, 0, 6), 5: (0, 1, 1, 4)}
RESIDUAL_EVENT_COUNT = 18
MAXIMUM_PAIR_OVERLAP = 3

# Study values from the scratch research.  Each one is re-derived; none is an input.
STUDY_REFERENCE = {
    "RAW_MEMBER_BOUND": 355_722_668,
    "EXISTING_RATIONAL_BOUND": 355_405_421,
    "FOREST_CORRECTION": 5_166_000,
    "RATIONAL_CORRECTION": 5_483_247,
    "HUNTER_CORRECTION": 7_372_190,
    "REFINED_MEMBER_BOUND": 353_516_478,
    "SIBLING_BOUND": 355_308_650,
    "NEXT_RAW_REGION_LEVEL": 355_274_920,
    "CANONICAL_INCUMBENT": 313_263_888,
}
STUDY_PAIR_FLOORS = (102_536, 535_542, 1_588_965, 3_260_138)

# Independent official-outcome model.
POOL_SIZE = 49
TICKET_SIZE = 6
WIN_HITS = 3
OUTCOME_SET_SIZE = 7
OUTCOMES_PER_SET = 7
SHARED_LABELS = (1, 2, 3)
A_ONLY_LABELS = (4, 5, 6)
B_ONLY_LABELS = (7, 8, 9)
OUTSIDE_LABELS = tuple(range(10, POOL_SIZE + 1))
CELL_LABELS = (SHARED_LABELS, A_ONLY_LABELS, B_ONLY_LABELS, OUTSIDE_LABELS)
ANCHOR_A = frozenset(SHARED_LABELS + A_ONLY_LABELS)
ANCHOR_B = frozenset(SHARED_LABELS + B_ONLY_LABELS)

# An explicit member portfolio on which all 18 residual events share one 7-set.
CAP17_WITNESS_OUTCOME_SET = frozenset(range(10, 17))
CAP17_WITNESS_RESIDUAL_TICKETS: tuple[tuple[int, ...], ...] = (
    (10, 11, 12, 17, 18, 19),
    (10, 11, 13, 17, 20, 21),
    (10, 11, 14, 17, 22, 23),
    (10, 11, 15, 17, 24, 25),
    (10, 11, 16, 17, 26, 27),
    (10, 12, 13, 17, 22, 24),
    (10, 12, 14, 17, 20, 25),
    (10, 12, 15, 17, 21, 23),
    (10, 12, 16, 17, 28, 29),
    (10, 13, 14, 17, 18, 26),
    (10, 13, 15, 17, 19, 27),
    (10, 13, 16, 17, 23, 25),
    (10, 14, 15, 17, 28, 30),
    (4, 7, 10, 14, 16, 17),
    (5, 8, 10, 15, 16, 17),
    (6, 9, 11, 12, 13, 17),
    (4, 8, 11, 12, 14, 17),
    (5, 9, 11, 12, 15, 18),
)

Cells = tuple[int, int, int, int]
Ticket = frozenset[int]


class CertificateScopeError(ValueError):
    """The member certificate was requested for a different state or member."""


class MultiplicityCapRefuted(ValueError):
    """A residual multiplicity cap is contradicted by an explicit member portfolio."""


def digest(payload: object) -> str:
    return sha256(repr(payload).encode("ascii")).hexdigest()


def file_sha256(relative: str) -> str:
    return sha256((REPO_ROOT / relative).read_bytes()).hexdigest()


@cache
def verify_upstream_fingerprints() -> dict[str, str]:
    observed = {relative: file_sha256(relative) for relative in UPSTREAM_SHA256}
    if observed != UPSTREAM_SHA256:
        raise AssertionError(f"upstream fingerprint mismatch: {observed}")
    return observed


def dense_counts(sparse: Iterable[tuple[int, int]]) -> tuple[int, ...]:
    counts = [0] * TYPE_COUNT
    for index, count in sparse:
        counts[index] = count
    return tuple(counts)


def member_counts() -> tuple[int, ...]:
    return dense_counts(MEMBER_SPARSE)


# ---------------------------------------------------------------- outcome counter


def count_seven_sets(winners: Sequence[Ticket], losers: Sequence[Ticket]) -> int:
    """Count 7-subsets E of 1..49 with |W n E| >= 3 for winners, <= 2 for losers."""

    tickets = (*winners, *losers)
    for ticket in tickets:
        if len(ticket) != TICKET_SIZE or not all(1 <= label <= POOL_SIZE for label in ticket):
            raise ValueError("every ticket must hold six labels from 1..49")
    regions: dict[int, int] = {}
    for label in range(1, POOL_SIZE + 1):
        mask = sum(1 << index for index, ticket in enumerate(tickets) if label in ticket)
        regions[mask] = regions.get(mask, 0) + 1
    states: dict[tuple[int, ...], int] = {(0,) * (len(tickets) + 1): 1}
    for mask, size in regions.items():
        following: dict[tuple[int, ...], int] = {}
        for state, ways in states.items():
            for take in range(min(size, OUTCOME_SET_SIZE - state[0]) + 1):
                hits = tuple(
                    min(WIN_HITS, hit + (take if mask >> index & 1 else 0))
                    for index, hit in enumerate(state[1:])
                )
                key = (state[0] + take, *hits)
                following[key] = following.get(key, 0) + ways * comb(size, take)
        states = following
    total = 0
    for state, ways in states.items():
        hits = state[1:]
        if (
            state[0] == OUTCOME_SET_SIZE
            and all(hit >= WIN_HITS for hit in hits[: len(winners)])
            and all(hit < WIN_HITS for hit in hits[len(winners) :])
        ):
            total += ways
    return total


def outcome_count(winners: Sequence[Ticket], losers: Sequence[Ticket] = ()) -> int:
    return OUTCOMES_PER_SET * count_seven_sets(winners, losers)


def _overlapping_pair(overlap: int) -> tuple[Ticket, Ticket]:
    left = frozenset(range(10, 16))
    right = frozenset(range(16 - overlap, 22 - overlap))
    return left, right


@cache
def seven_set_lemma_check() -> dict[str, Any]:
    """Cross-check the 7-set counter against R1's outcome-level special-number logic."""

    single = outcome_count((frozenset(range(10, 16)),))
    pair_counts = tuple(outcome_count(_overlapping_pair(overlap)) for overlap in range(7))
    outcome_level = tuple(r1.pair_intersection_count(overlap) for overlap in range(7))
    canonical = r14.canonical_primitives()["SINGLE_TICKET_ANY_PRIZE"]
    if single != canonical or pair_counts != outcome_level or pair_counts[6] != single:
        raise AssertionError("the 7-set counter disagrees with the outcome-level counts")
    if r1.pair_intersection_table() != pair_counts:
        raise AssertionError("the pair-intersection table changed")
    return {
        "RULE": "any prize <=> |T n (D u {s})| >= 3; (D,s) -> D u {s} is 7-to-1 onto 7-sets",
        "SINGLE_TICKET_OUTCOMES": single,
        "PAIR_INTERSECTION_BY_OVERLAP": list(pair_counts),
        "OUTCOME_LEVEL_REPLAY": "R1 pair_intersection_count(0..6) matches exactly",
    }


# ---------------------------------------------------------------- phase 1: events


def realize_ticket(cells: Cells) -> Ticket:
    return realize_pair(cells, cells, cells)[0]


def realize_pair(left: Cells, right: Cells, overlap: Cells) -> tuple[Ticket, Ticket]:
    """Concrete tickets with the given anchor-cell counts and per-cell overlap."""

    left_labels: set[int] = set()
    right_labels: set[int] = set()
    for labels, left_count, right_count, both in zip(
        CELL_LABELS, left, right, overlap, strict=True
    ):
        if (
            not max(0, left_count + right_count - len(labels))
            <= both
            <= min(left_count, right_count)
        ):
            raise ValueError("cell overlap cannot be realized inside its cell")
        chosen = labels[:left_count]
        left_labels.update(chosen)
        right_labels.update(chosen[:both])
        right_labels.update(labels[left_count : left_count + right_count - both])
    if len(left_labels) != TICKET_SIZE or len(right_labels) != TICKET_SIZE:
        raise ValueError("cell counts must describe six-label tickets")
    return frozenset(left_labels), frozenset(right_labels)


def ticket_cells(ticket: Ticket) -> Cells:
    shared, a_only, b_only, outside = (len(ticket.intersection(labels)) for labels in CELL_LABELS)
    return shared, a_only, b_only, outside


def pair_cell_overlap(left: Ticket, right: Ticket) -> Cells:
    shared, a_only, b_only, outside = (
        len(left.intersection(right).intersection(labels)) for labels in CELL_LABELS
    )
    return shared, a_only, b_only, outside


def residual_event_size(cells: Cells) -> int:
    return outcome_count((realize_ticket(cells),), (ANCHOR_A, ANCHOR_B))


def residual_pair_intersection(left: Cells, right: Cells, overlap: Cells) -> int:
    pair = realize_pair(left, right, overlap)
    return outcome_count(pair, (ANCHOR_A, ANCHOR_B))


def anchor_union_size() -> int:
    total_sets = comb(POOL_SIZE, OUTCOME_SET_SIZE)
    return OUTCOMES_PER_SET * (total_sets - count_seven_sets((), (ANCHOR_A, ANCHOR_B)))


@dataclass(frozen=True)
class LedgerMember:
    """Immutable R24 ledger view of the target state, member and region thresholds."""

    state_term: int
    region_member_count: int
    region_type_vector_count: int
    member_raw_bound: int
    member_final_bound: int
    member_represented_vector_count: int
    sibling_raw_bound: int
    ladder_final_bounds: tuple[int, ...]
    next_raw_region_level: int
    next_raw_region_level_is_raw: bool


def _ladder_member(counts: tuple[int, ...]) -> bool:
    return counts[0] == 13 and all(
        count == 0 for index, count in enumerate(counts) if index not in (0, 5, 16)
    )


@cache
def r24_ledger_member() -> LedgerMember:
    verify_upstream_fingerprints()
    stored = cast(
        dict[str, Any],
        json.loads((REPO_ROOT / R24_RESULT_RELATIVE).read_text(encoding="utf-8")),
    )
    regions = [
        region
        for region in cast(list[dict[str, Any]], stored["STATE_REGION_CERTIFICATES"])
        if region["owner_id"] == STATE_ID
    ]
    terms = [
        int(term["bound"])
        for term in cast(list[dict[str, Any]], stored["CURRENT_STATE_TERMS"])
        if term["stable_id"] == STATE_ID
    ]
    if len(regions) != 1 or len(terms) != 1 or regions[0]["region_sha256"] != REGION_SHA256:
        raise AssertionError("the R24 ledger does not hold exactly one pinned target region")
    members = cast(list[dict[str, Any]], regions[0]["complete_region_members"])
    by_counts = {
        dense_counts((int(index), int(count)) for index, count in member["witness_counts"]): member
        for member in members
    }
    if len(by_counts) != len(members):
        raise AssertionError("the R24 region repeats a member")
    target = by_counts[member_counts()]
    sibling = by_counts[dense_counts(SIBLING_SPARSE)]
    ladder = sorted(
        (
            int(member["final_bound"])
            for counts, member in by_counts.items()
            if _ladder_member(counts)
        ),
        reverse=True,
    )
    below = [member for counts, member in by_counts.items() if not _ladder_member(counts)]
    next_member = max(below, key=lambda member: int(member["final_bound"]))
    return LedgerMember(
        state_term=terms[0],
        region_member_count=len(members),
        region_type_vector_count=sum(int(member["represented_vector_count"]) for member in members),
        member_raw_bound=int(target["raw_bound"]),
        member_final_bound=int(target["final_bound"]),
        member_represented_vector_count=int(target["represented_vector_count"]),
        sibling_raw_bound=int(sibling["raw_bound"]),
        ladder_final_bounds=tuple(ladder),
        next_raw_region_level=int(next_member["final_bound"]),
        next_raw_region_level_is_raw=(
            int(next_member["final_bound"]) == int(next_member["raw_bound"])
        ),
    )


@dataclass(frozen=True)
class EventDecomposition:
    """|union E| <= |E_A u E_B| + sum_C |R_C| - correction, with exact event sizes."""

    anchor_union: int
    residual_event_sizes: tuple[tuple[int, int], ...]
    residual_sum: int
    raw_union_bound: int
    anchor_pair_s2: int
    anchor_triple_s3: int
    r7_forest_floor: int
    r7_pair_sum_penalty: int


@cache
def event_decomposition(sparse: tuple[tuple[int, int], ...] = MEMBER_SPARSE) -> EventDecomposition:
    """Re-derive the raw member bound from residual events counted by the 7-set counter."""

    profiles = r5.anchor_incidence_profiles()
    single = seven_set_lemma_check()["SINGLE_TICKET_OUTCOMES"]
    sizes: list[tuple[int, int]] = []
    for type_index, _ in sparse:
        profile = profiles[type_index]
        cells = (profile.shared, profile.a_only, profile.b_only, profile.outside)
        size = residual_event_size(cells)
        if size != single - profile.pair_recovery_cost + profile.triple_recovery:
            raise AssertionError("residual event size disagrees with N - I(s+a) - I(s+b) + J")
        sizes.append((type_index, size))
    residual_sum = sum(dict(sparse)[type_index] * size for type_index, size in sizes)
    if sum(count for _, count in sparse) != RESIDUAL_EVENT_COUNT:
        raise AssertionError("a member must hold exactly 18 residual tickets")
    anchor_union = anchor_union_size()
    if anchor_union != 2 * single - r1.pair_intersection_count(r5.ANCHOR_OVERLAP):
        raise AssertionError("the anchor union is not 2N - I(3)")
    counts = dense_counts(sparse)
    state = r7._make_state(counts, profiles, r6.local_losses(profiles))  # pyright: ignore[reportPrivateUsage]
    raw = anchor_union + residual_sum
    if raw != r14.joint_constant() - state.anchor_pair_s2 + state.anchor_triple_s3:
        raise AssertionError("the 7-set decomposition disagrees with the R14 joint expression")
    if raw - state.applied_residual_union_penalty != r14.raw_bound(state):
        raise AssertionError("the R7 member bound is not raw minus its applied correction")
    return EventDecomposition(
        anchor_union=anchor_union,
        residual_event_sizes=tuple(sizes),
        residual_sum=residual_sum,
        raw_union_bound=raw,
        anchor_pair_s2=state.anchor_pair_s2,
        anchor_triple_s3=state.anchor_triple_s3,
        r7_forest_floor=state.complementary_forest_floor,
        r7_pair_sum_penalty=state.residual_pair_union_penalty,
    )


# ---------------------------------------------------------------- phase 2: pair table


@dataclass(frozen=True)
class PairRow:
    left_type: int
    right_type: int
    overlap: Cells
    residual_intersection: int

    @property
    def total_overlap(self) -> int:
        return sum(self.overlap)


def member_type_pairs() -> tuple[tuple[int, int], ...]:
    types = tuple(index for index, _ in MEMBER_SPARSE)
    return tuple((left, right) for left in types for right in types if left <= right)


def feasible_cell_overlaps(left: Cells, right: Cells) -> tuple[Cells, ...]:
    """Every physically realizable per-cell overlap at most the Family A ceiling."""

    ceiling = family_pair_overlap_ceiling()
    ranges = tuple(
        range(max(0, left_count + right_count - len(labels)), min(left_count, right_count) + 1)
        for labels, left_count, right_count in zip(CELL_LABELS, left, right, strict=True)
    )
    rows: list[Cells] = []
    for shared, a_only, b_only, outside in product(*ranges):
        if shared + a_only + b_only + outside <= ceiling:
            rows.append((shared, a_only, b_only, outside))
    return tuple(rows)


@cache
def independent_pair_rows() -> tuple[PairRow, ...]:
    """Recount all member type-pair rows and require exact equality with R8."""

    rows: list[PairRow] = []
    for left_type, right_type in member_type_pairs():
        left, right = MEMBER_TYPE_CELLS[left_type], MEMBER_TYPE_CELLS[right_type]
        overlaps = feasible_cell_overlaps(left, right)
        independent = {
            overlap: residual_pair_intersection(left, right, overlap) for overlap in overlaps
        }
        table = r8._pair_event_correction_table(left_type, right_type)  # pyright: ignore[reportPrivateUsage]
        committed = {(row[0], row[1], row[2], row[3]): row[4] for row in table}
        if committed != independent:
            raise AssertionError(f"R8 pair table differs for types {(left_type, right_type)}")
        r6_overlaps = set(r6.feasible_pair_overlap_vectors(left_type, right_type))
        if r6_overlaps != set(overlaps):
            raise AssertionError("R6 and the independent overlap enumeration disagree")
        rows.extend(
            PairRow(left_type, right_type, overlap, value)
            for overlap, value in sorted(independent.items())
        )
    return tuple(rows)


def pair_floor_by_overlap(rows: Sequence[PairRow]) -> tuple[int, int, int, int]:
    floors: list[int] = []
    for total in range(MAXIMUM_PAIR_OVERLAP + 1):
        values = [row.residual_intersection for row in rows if row.total_overlap == total]
        if not values:
            raise AssertionError(f"no pair row covers total overlap {total}")
        floors.append(min(values))
    return floors[0], floors[1], floors[2], floors[3]


def require_safe_pair_floors(floors: Sequence[int], rows: Sequence[PairRow]) -> None:
    """Every floor must be at most every exact row of its total, and nondecreasing."""

    if len(floors) != MAXIMUM_PAIR_OVERLAP + 1:
        raise AssertionError("one floor is required for each total overlap 0..3")
    for row in rows:
        if floors[row.total_overlap] > row.residual_intersection:
            raise AssertionError(f"pair floor {row.total_overlap} exceeds the exact row {row}")
    if any(low > high for low, high in pairwise(floors)):
        raise AssertionError("pair floors must be nondecreasing for threshold weights")
    if floors[0] < 0:
        raise AssertionError("pair floors must be nonnegative")


@cache
def family_pair_overlap_ceiling() -> int:
    """Return 3 only when Family A and the R5 record both exclude a larger overlap.

    Family A is partitioned by the exact portfolio maximum ``r``.  The R3 case
    is ``heavy_pair_case(3)``.  Profiles in that case keep every anchor overlap
    at most ``r``, and the R5 capacity record says every outside pair's four
    cell counts sum to at most 3.  A smaller Family A case is rejected by the
    source, so the ceiling is the family definition, not one example portfolio.
    """

    case = heavy_pair.heavy_pair_case(3)
    if case.maximum_pair_overlap != 3:
        raise AssertionError("Family A R3 is not the exact maximum-overlap 3 case")
    try:
        heavy_pair.heavy_pair_case(2)
    except ValueError:
        pass
    else:
        raise AssertionError("Family A must reject a maximum overlap below 3")
    profiles = heavy_pair.local_heavy_pair_profiles(case.maximum_pair_overlap)
    if not profiles or any(
        profile.left_overlap > case.maximum_pair_overlap
        or profile.right_overlap > case.maximum_pair_overlap
        for profile in profiles
    ):
        raise AssertionError("Family A profiles are not bounded by the case maximum")
    record = r5.family_a_result_record()
    constraints = cast(dict[str, Any], record["CAPACITY_CONSTRAINTS"])
    pairwise_rule = constraints["PAIRWISE_MAXIMUM_OVERLAP"]
    type_rules = constraints["TYPE_RULES"]
    if (
        not isinstance(pairwise_rule, str)
        or "at most 3" not in pairwise_rule
        or not isinstance(type_rules, str)
        or "s+a<=3" not in type_rules
        or "s+b<=3" not in type_rules
    ):
        raise AssertionError("the R5 record does not exclude pairwise overlap above 3")
    if case.maximum_pair_overlap != r5.ANCHOR_OVERLAP:
        raise AssertionError("the R5 anchor overlap is not the Family A R3 maximum")
    if case.maximum_pair_overlap != MAXIMUM_PAIR_OVERLAP:
        raise AssertionError("the certificate ceiling drifted from Family A")
    return case.maximum_pair_overlap


# ---------------------------------------------------------------- tree rank proof


@cache
def rank_floor(edge_count: int) -> int:
    """rho(e): the least forest rank r of a graph with e edges, C(r+1,2) >= e."""

    if edge_count < 0:
        raise ValueError("edge count must be nonnegative")
    rank = 0
    while comb(rank + 1, 2) < edge_count:
        rank += 1
    return rank


def graph_rank(vertex_count: int, edges: Iterable[tuple[int, int]]) -> int:
    parent = list(range(vertex_count))

    def find(vertex: int) -> int:
        while parent[vertex] != vertex:
            parent[vertex] = parent[parent[vertex]]
            vertex = parent[vertex]
        return vertex

    rank = 0
    for left, right in edges:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[left_root] = right_root
            rank += 1
    return rank


def threshold_tree(
    vertex_count: int, overlaps: Mapping[tuple[int, int], int]
) -> tuple[tuple[int, int], ...]:
    """Kruskal in decreasing overlap: a spanning tree nested over every G_k."""

    ordered = sorted(overlaps, key=lambda edge: (-overlaps[edge], edge))
    parent = list(range(vertex_count))

    def find(vertex: int) -> int:
        while parent[vertex] != vertex:
            parent[vertex] = parent[parent[vertex]]
            vertex = parent[vertex]
        return vertex

    tree: list[tuple[int, int]] = []
    for left, right in ordered:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[left_root] = right_root
            tree.append((left, right))
    return tuple(tree)


def verify_rank_floor_exhaustively(
    floor: Callable[[int], int] = rank_floor, vertex_count: int = 6
) -> int:
    """Check rank(G) >= floor(|E(G)|) on every labelled graph with this many vertices."""

    edges = tuple(combinations(range(vertex_count), 2))
    for mask in range(1 << len(edges)):
        chosen = [edge for index, edge in enumerate(edges) if mask >> index & 1]
        if graph_rank(vertex_count, chosen) < floor(len(chosen)):
            raise AssertionError(f"rank floor fails on {chosen}")
    return 1 << len(edges)


def verify_rank_floor_algebra(vertex_count: int = RESIDUAL_EVENT_COUNT) -> int:
    """The superadditivity step and rho's minimality, over every rank and edge count."""

    limit = vertex_count - 1
    for left in range(limit + 1):
        for right in range(limit + 1 - left):
            if comb(left + 1, 2) + comb(right + 1, 2) + left * right != comb(left + right + 1, 2):
                raise AssertionError("C(a+1,2)+C(b+1,2) <= C(a+b+1,2) identity failed")
    for edge_count in range(comb(vertex_count, 2) + 1):
        rho = rank_floor(edge_count)
        if comb(rho + 1, 2) < edge_count or (rho and comb(rho, 2) >= edge_count):
            raise AssertionError("rho is not the least feasible forest rank")
        if rho > limit:
            raise AssertionError("rho exceeds the spanning-tree rank")
    return comb(vertex_count, 2) + 1


def verify_threshold_tree_lemma(vertex_count: int = 4) -> int:
    """Every labelling of K_n by overlaps 0..3: the nested tree meets rank(G_k) per k."""

    edges = tuple(combinations(range(vertex_count), 2))
    checked = 0
    for labels in product(range(MAXIMUM_PAIR_OVERLAP + 1), repeat=len(edges)):
        overlaps = dict(zip(edges, labels, strict=True))
        tree = threshold_tree(vertex_count, overlaps)
        if len(tree) != vertex_count - 1:
            raise AssertionError("threshold tree does not span")
        for level in range(1, MAXIMUM_PAIR_OVERLAP + 1):
            in_tree = sum(1 for edge in tree if overlaps[edge] >= level)
            graph = [edge for edge in edges if overlaps[edge] >= level]
            if in_tree != graph_rank(vertex_count, graph):
                raise AssertionError("tree does not hold a spanning forest of G_k")
        checked += 1
    return checked


def _bit_count(value: int) -> int:
    return bin(value).count("1")


def verify_hunter_exhaustively(universe_size: int, event_count: int) -> int:
    """Hunter on every family of subsets of a small universe and every spanning tree."""

    vertices = range(event_count)
    trees = [
        tree
        for tree in combinations(combinations(vertices, 2), event_count - 1)
        if graph_rank(event_count, tree) == event_count - 1
    ]
    checked = 0
    for family in product(range(1 << universe_size), repeat=event_count):
        union = 0
        for event in family:
            union |= event
        total = sum(_bit_count(event) for event in family)
        for tree in trees:
            tree_weight = sum(_bit_count(family[left] & family[right]) for left, right in tree)
            if _bit_count(union) > total - tree_weight:
                raise AssertionError("Hunter's inequality failed")
            checked += 1
    return checked


# ---------------------------------------------------------------- phase 3: collisions


def balanced_collision_mass(incidences: int, labels: int) -> int:
    """min sum_x C(d_x, 2) over nonnegative integers d with sum d = incidences."""

    if incidences < 0 or labels <= 0:
        raise ValueError("incidences and label count must be valid")
    quotient, remainder = divmod(incidences, labels)
    return remainder * comb(quotient + 1, 2) + (labels - remainder) * comb(quotient, 2)


def verify_balanced_mass_exhaustively(maximum_total: int = 12, labels: int = 3) -> int:
    checked = 0
    for frequencies in product(range(maximum_total + 1), repeat=labels):
        total = sum(frequencies)
        if total > maximum_total:
            continue
        if sum(comb(value, 2) for value in frequencies) < balanced_collision_mass(total, labels):
            raise AssertionError("balanced collision mass is not a minimum")
        checked += 1
    return checked


def member_cell_incidences(sparse: Sequence[tuple[int, int]] = MEMBER_SPARSE) -> Cells:
    totals = [0, 0, 0, 0]
    for type_index, count in sparse:
        for cell, value in enumerate(MEMBER_TYPE_CELLS[type_index]):
            totals[cell] += count * value
    return totals[0], totals[1], totals[2], totals[3]


def cell_collision_floors(incidences: Cells) -> Cells:
    shared, a_only, b_only, outside = (
        balanced_collision_mass(total, len(labels))
        for total, labels in zip(incidences, CELL_LABELS, strict=True)
    )
    return shared, a_only, b_only, outside


def threshold_edge_counts(overlaps: Iterable[int]) -> tuple[int, int, int]:
    """e_k = #{pairs with overlap >= k}; overlaps above the family ceiling are rejected."""

    ceiling = family_pair_overlap_ceiling()
    edge_counts = [0, 0, 0]
    for overlap in overlaps:
        if not 0 <= overlap <= ceiling:
            raise ValueError(f"pair overlap {overlap} is outside the R3 range 0..{ceiling}")
        for level in range(1, overlap + 1):
            edge_counts[level - 1] += 1
    return edge_counts[0], edge_counts[1], edge_counts[2]


def tree_weight_floor(
    floors: Sequence[int], ranks: Sequence[int], vertex_count: int = RESIDUAL_EVENT_COUNT
) -> int:
    """(n-1) phi(0) + sum_k (phi(k) - phi(k-1)) * rank_k for nested threshold forests."""

    return (vertex_count - 1) * floors[0] + sum(
        (floors[level] - floors[level - 1]) * ranks[level - 1]
        for level in range(1, MAXIMUM_PAIR_OVERLAP + 1)
    )


@dataclass(frozen=True)
class TreeMinimum:
    correction: int
    edge_counts: tuple[int, int, int]
    rank_floors: tuple[int, int, int]
    census_size: int


@cache
def minimum_tree_correction(
    floors: tuple[int, int, int, int],
    collision_floor: int,
    vertex_count: int = RESIDUAL_EVENT_COUNT,
) -> TreeMinimum:
    """Exhaust e1 >= e2 >= e3 >= 0, e1 <= C(n,2), e1 + e2 + e3 >= Q."""

    edge_capacity = comb(vertex_count, 2)
    rho = [rank_floor(edge_count) for edge_count in range(edge_capacity + 1)]
    best: tuple[int, tuple[int, int, int]] | None = None
    census = 0
    for e1 in range(edge_capacity + 1):
        for e2 in range(e1 + 1):
            for e3 in range(e2 + 1):
                if e1 + e2 + e3 < collision_floor:
                    continue
                census += 1
                value = tree_weight_floor(floors, (rho[e1], rho[e2], rho[e3]), vertex_count)
                if best is None or value < best[0]:
                    best = (value, (e1, e2, e3))
    if best is None:
        raise AssertionError("the collision relaxation is infeasible")
    counts = best[1]
    return TreeMinimum(
        correction=best[0],
        edge_counts=counts,
        rank_floors=(rho[counts[0]], rho[counts[1]], rho[counts[2]]),
        census_size=census,
    )


# ---------------------------------------------------------------- phase 4: certificate


def combine_corrections(corrections: Mapping[str, int]) -> int:
    """Valid lower bounds on one union correction combine by max, never by sum."""

    if not corrections or any(value < 0 for value in corrections.values()):
        raise ValueError("corrections must be nonnegative and nonempty")
    return max(corrections.values())


@dataclass(frozen=True)
class HunterMemberCertificate:
    state_id: str
    region_sha256: str
    member_sparse: tuple[tuple[int, int], ...]
    residual_event_count: int
    maximum_pair_overlap: int
    raw_union_bound: int
    pair_floors: tuple[int, int, int, int]
    pair_rows_sha256: str
    cell_incidences: Cells
    cell_collision_floors: Cells
    collision_floor: int
    threshold_edge_counts: tuple[int, int, int]
    threshold_rank_floors: tuple[int, int, int]
    hunter_correction: int
    pair_sum_correction: int
    forest_correction: int
    rational_correction: int
    certified_correction: int
    certified_member_bound: int


def _rows_digest(rows: Sequence[PairRow]) -> str:
    payload = tuple(
        (row.left_type, row.right_type, row.overlap, row.residual_intersection) for row in rows
    )
    return digest(payload)


@cache
def rational_correction() -> int:
    return int(r14.moment_certificate(member_counts())["correction_lower_bound"])


@cache
def build_certificate() -> HunterMemberCertificate:
    verify_upstream_fingerprints()
    events = event_decomposition()
    rows = independent_pair_rows()
    floors = pair_floor_by_overlap(rows)
    incidences = member_cell_incidences()
    cell_floors = cell_collision_floors(incidences)
    collision_floor = sum(cell_floors)
    tree = minimum_tree_correction(floors, collision_floor)
    corrections = {
        "R6_PAIR_SUM": events.r7_pair_sum_penalty,
        "R5_FOREST": events.r7_forest_floor,
        "R14_RATIONAL": rational_correction(),
        "HUNTER_TREE": tree.correction,
    }
    certified = combine_corrections(corrections)
    return HunterMemberCertificate(
        state_id=STATE_ID,
        region_sha256=REGION_SHA256,
        member_sparse=MEMBER_SPARSE,
        residual_event_count=RESIDUAL_EVENT_COUNT,
        maximum_pair_overlap=MAXIMUM_PAIR_OVERLAP,
        raw_union_bound=events.raw_union_bound,
        pair_floors=floors,
        pair_rows_sha256=_rows_digest(rows),
        cell_incidences=incidences,
        cell_collision_floors=cell_floors,
        collision_floor=collision_floor,
        threshold_edge_counts=tree.edge_counts,
        threshold_rank_floors=tree.rank_floors,
        hunter_correction=tree.correction,
        pair_sum_correction=corrections["R6_PAIR_SUM"],
        forest_correction=corrections["R5_FOREST"],
        rational_correction=corrections["R14_RATIONAL"],
        certified_correction=certified,
        certified_member_bound=events.raw_union_bound - certified,
    )


def verify_certificate(certificate: HunterMemberCertificate) -> None:
    """Recheck every certificate field from exact inputs; raise on any deviation."""

    if (
        certificate.state_id != STATE_ID
        or certificate.region_sha256 != REGION_SHA256
        or certificate.member_sparse != MEMBER_SPARSE
    ):
        raise AssertionError("certificate source member differs from the pinned member")
    if certificate.residual_event_count != RESIDUAL_EVENT_COUNT:
        raise AssertionError("the member has exactly 18 residual events")
    if certificate.maximum_pair_overlap != family_pair_overlap_ceiling():
        raise AssertionError("R3 portfolios have pair overlaps 0..3 only")
    events = event_decomposition()
    if certificate.raw_union_bound != events.raw_union_bound:
        raise AssertionError("raw union bound differs from the exact event decomposition")
    rows = independent_pair_rows()
    require_safe_pair_floors(certificate.pair_floors, rows)
    if certificate.pair_floors != pair_floor_by_overlap(rows):
        raise AssertionError("pair floors differ from the exact row minima")
    if certificate.pair_rows_sha256 != _rows_digest(rows):
        raise AssertionError("pair rows digest differs")
    if certificate.cell_incidences != member_cell_incidences():
        raise AssertionError("cell incidences differ from the member type counts")
    floors = cell_collision_floors(certificate.cell_incidences)
    if certificate.cell_collision_floors != floors or certificate.collision_floor != sum(floors):
        raise AssertionError("collision floor differs from the balanced per-cell minimum")
    verify_rank_floor_algebra()
    verify_rank_floor_exhaustively(rank_floor)
    tree = minimum_tree_correction(certificate.pair_floors, certificate.collision_floor)
    if (
        certificate.hunter_correction != tree.correction
        or certificate.threshold_edge_counts != tree.edge_counts
        or certificate.threshold_rank_floors != tree.rank_floors
    ):
        raise AssertionError("Hunter correction differs from the finite rank minimum")
    e1, e2, e3 = certificate.threshold_edge_counts
    if not (comb(RESIDUAL_EVENT_COUNT, 2) >= e1 >= e2 >= e3 >= 0) or (
        e1 + e2 + e3 < certificate.collision_floor
    ):
        raise AssertionError("threshold edge counts are not feasible")
    if certificate.threshold_rank_floors != tuple(
        rank_floor(count) for count in certificate.threshold_edge_counts
    ):
        raise AssertionError("threshold rank floors are not rho(e_k)")
    if certificate.hunter_correction != tree_weight_floor(
        certificate.pair_floors, certificate.threshold_rank_floors
    ):
        raise AssertionError("Hunter correction is not the tree weight floor")
    expected = {
        "R6_PAIR_SUM": events.r7_pair_sum_penalty,
        "R5_FOREST": events.r7_forest_floor,
        "R14_RATIONAL": rational_correction(),
        "HUNTER_TREE": certificate.hunter_correction,
    }
    if (
        certificate.pair_sum_correction,
        certificate.forest_correction,
        certificate.rational_correction,
    ) != (expected["R6_PAIR_SUM"], expected["R5_FOREST"], expected["R14_RATIONAL"]):
        raise AssertionError("existing corrections differ from their committed sources")
    if certificate.certified_correction != combine_corrections(expected):
        raise AssertionError("corrections must be combined by max, never summed")
    if certificate.certified_member_bound != (
        certificate.raw_union_bound - certificate.certified_correction
    ):
        raise AssertionError("certified bound must subtract the combined correction once")


def certified_member_bound(state_id: str, counts: Sequence[int]) -> int:
    """Return the member bound only for the exact source state and member."""

    certificate = build_certificate()
    if state_id != certificate.state_id or tuple(counts) != dense_counts(certificate.member_sparse):
        raise CertificateScopeError(
            f"the Hunter certificate is valid only for {certificate.state_id} member {MEMBER_ID}"
        )
    verify_certificate(certificate)
    return certificate.certified_member_bound


def sibling_rational_bound() -> int:
    """The sibling [0,13][5,4][16,1] under the committed R14 rational route only."""

    counts = dense_counts(SIBLING_SPARSE)
    events = event_decomposition(SIBLING_SPARSE)
    rational = int(r14.moment_certificate(counts)["correction_lower_bound"])
    correction = max(events.r7_forest_floor, events.r7_pair_sum_penalty, rational)
    return events.raw_union_bound - correction


# ---------------------------------------------------------------- phase 5: witness


@dataclass(frozen=True)
class WitnessAnalysis:
    member_sparse: tuple[tuple[int, int], ...]
    anchor_overlap: int
    maximum_pair_overlap: int
    residual_multiplicity: int
    anchor_hits_on_outcome_set: tuple[int, int]
    overlap_histogram: tuple[int, int, int, int]
    collision_mass: int
    label_collision_mass: int
    edge_counts: tuple[int, int, int]
    graph_ranks: tuple[int, int, int]
    floor_tree_weight: int
    exact_tree_weight: int
    exact_rows_match_table: bool


def witness_tickets() -> tuple[Ticket, ...]:
    return (
        ANCHOR_A,
        ANCHOR_B,
        *(frozenset(ticket) for ticket in CAP17_WITNESS_RESIDUAL_TICKETS),
    )


@cache
def cap17_witness_analysis() -> WitnessAnalysis:
    """Validate the explicit member portfolio and its exact residual pair structure."""

    portfolio = witness_tickets()
    if len(portfolio) != 20 or len(set(portfolio)) != 20:
        raise AssertionError("witness must hold 20 distinct tickets")
    if any(
        len(ticket) != TICKET_SIZE or not all(1 <= label <= POOL_SIZE for label in ticket)
        for ticket in portfolio
    ):
        raise AssertionError("witness tickets must hold six labels from 1..49")
    overlaps_all = [len(left & right) for left, right in combinations(portfolio, 2)]
    anchor_overlap = len(ANCHOR_A & ANCHOR_B)
    if max(overlaps_all) != anchor_overlap or anchor_overlap != r5.ANCHOR_OVERLAP:
        raise AssertionError("witness is not an R3 portfolio anchored on a maximum pair")
    profiles = r5.anchor_incidence_profiles()
    index_by_cells = {
        (profile.shared, profile.a_only, profile.b_only, profile.outside): index
        for index, profile in enumerate(profiles)
    }
    residual = portfolio[2:]
    types = [index_by_cells[ticket_cells(ticket)] for ticket in residual]
    sparse = tuple(sorted((index, types.count(index)) for index in set(types)))
    if sparse != MEMBER_SPARSE:
        raise AssertionError(f"witness types {sparse} are not the target member")
    outcome_set = CAP17_WITNESS_OUTCOME_SET
    anchor_hits = (len(ANCHOR_A & outcome_set), len(ANCHOR_B & outcome_set))
    multiplicity = sum(1 for ticket in residual if len(ticket & outcome_set) >= WIN_HITS)
    if max(anchor_hits) >= WIN_HITS:
        raise AssertionError("the shared 7-set must lie outside both anchor events")

    table = {(row.left_type, row.right_type, row.overlap): row for row in independent_pair_rows()}
    floors = pair_floor_by_overlap(independent_pair_rows())
    pair_overlaps: dict[tuple[int, int], int] = {}
    exact_weights: dict[tuple[int, int], int] = {}
    rows_match = True
    for left, right in combinations(range(len(residual)), 2):
        overlap_cells = pair_cell_overlap(residual[left], residual[right])
        pair_overlaps[(left, right)] = sum(overlap_cells)
        low, high = sorted((types[left], types[right]))
        exact = outcome_count((residual[left], residual[right]), (ANCHOR_A, ANCHOR_B))
        exact_weights[(left, right)] = exact
        rows_match = rows_match and table[(low, high, overlap_cells)].residual_intersection == exact
    edge_counts = threshold_edge_counts(pair_overlaps.values())
    frequencies = [sum(1 for ticket in residual if label in ticket) for label in range(1, 50)]
    label_mass = sum(comb(value, 2) for value in frequencies)
    collision_mass = sum(pair_overlaps.values())
    if collision_mass != sum(edge_counts) or collision_mass != label_mass:
        raise AssertionError("witness collision identities failed")
    ranks = tuple(
        graph_rank(len(residual), (edge for edge, value in pair_overlaps.items() if value >= level))
        for level in range(1, MAXIMUM_PAIR_OVERLAP + 1)
    )
    floor_tree = threshold_tree(len(residual), pair_overlaps)
    floor_weight = sum(floors[pair_overlaps[edge]] for edge in floor_tree)
    if floor_weight != tree_weight_floor(floors, ranks, len(residual)):
        raise AssertionError("witness threshold tree does not attain the nested rank weight")
    exact_tree = threshold_tree(len(residual), exact_weights)
    exact_weight = sum(exact_weights[edge] for edge in exact_tree)
    histogram = tuple(
        sum(1 for value in pair_overlaps.values() if value == total)
        for total in range(MAXIMUM_PAIR_OVERLAP + 1)
    )
    return WitnessAnalysis(
        member_sparse=sparse,
        anchor_overlap=anchor_overlap,
        maximum_pair_overlap=max(overlaps_all),
        residual_multiplicity=multiplicity,
        anchor_hits_on_outcome_set=anchor_hits,
        overlap_histogram=(histogram[0], histogram[1], histogram[2], histogram[3]),
        collision_mass=collision_mass,
        label_collision_mass=label_mass,
        edge_counts=edge_counts,
        graph_ranks=(ranks[0], ranks[1], ranks[2]),
        floor_tree_weight=floor_weight,
        exact_tree_weight=exact_weight,
        exact_rows_match_table=rows_match,
    )


def require_multiplicity_cap(cap: int) -> int:
    """Accept a residual multiplicity cap only when it is proven for the member.

    The only proven cap is the residual ticket count 18.  The explicit witness
    attains 18, so every smaller cap (in particular 17) is refuted.
    """

    observed = cap17_witness_analysis().residual_multiplicity
    if cap < observed:
        raise MultiplicityCapRefuted(
            f"cap {cap} is refuted: a valid member portfolio has multiplicity {observed}"
        )
    if cap < RESIDUAL_EVENT_COUNT:
        raise ValueError(f"cap {cap} is below the residual ticket count and unproven")
    return cap


# ---------------------------------------------------------------- result


def _sparse_text(sparse: Sequence[tuple[int, int]]) -> list[list[int]]:
    return [[index, count] for index, count in sparse]


@cache
def build_result() -> dict[str, Any]:
    certificate = build_certificate()
    verify_certificate(certificate)
    ledger = r24_ledger_member()
    events = event_decomposition()
    rows = independent_pair_rows()
    witness = cap17_witness_analysis()
    lemma = seven_set_lemma_check()
    tree_rank_graphs = verify_rank_floor_exhaustively(rank_floor)
    rank_algebra_rows = verify_rank_floor_algebra()
    threshold_labellings = verify_threshold_tree_lemma()
    hunter_small = verify_hunter_exhaustively(4, 3) + verify_hunter_exhaustively(3, 4)
    balanced_rows = verify_balanced_mass_exhaustively()
    tree = minimum_tree_correction(certificate.pair_floors, certificate.collision_floor)
    sibling = sibling_rational_bound()
    rational_bound = events.raw_union_bound - combine_corrections(
        {
            "R6_PAIR_SUM": certificate.pair_sum_correction,
            "R5_FOREST": certificate.forest_correction,
            "R14_RATIONAL": certificate.rational_correction,
        }
    )
    forest_bound = events.raw_union_bound - max(
        certificate.forest_correction, certificate.pair_sum_correction
    )
    if (
        ledger.member_raw_bound != forest_bound
        or ledger.member_final_bound != ledger.member_raw_bound
        or ledger.member_represented_vector_count != 1
        or ledger.state_term != ledger.member_final_bound
    ):
        raise AssertionError("the R24 ledger member differs from the re-derived raw bound")
    if not witness.exact_rows_match_table or witness.exact_tree_weight < (
        certificate.hunter_correction
    ):
        raise AssertionError("the explicit member witness contradicts the certificate")
    if witness.floor_tree_weight < certificate.hunter_correction or witness.collision_mass < (
        certificate.collision_floor
    ):
        raise AssertionError("the witness violates the certified relaxation")
    derived = {
        "RAW_MEMBER_BOUND": ledger.member_raw_bound,
        "EXISTING_RATIONAL_BOUND": rational_bound,
        "FOREST_CORRECTION": certificate.forest_correction,
        "RATIONAL_CORRECTION": certificate.rational_correction,
        "HUNTER_CORRECTION": certificate.hunter_correction,
        "REFINED_MEMBER_BOUND": certificate.certified_member_bound,
        "SIBLING_BOUND": sibling,
        "NEXT_RAW_REGION_LEVEL": ledger.next_raw_region_level,
        "CANONICAL_INCUMBENT": STUDY_REFERENCE["CANONICAL_INCUMBENT"],
    }
    if derived != STUDY_REFERENCE or certificate.pair_floors != STUDY_PAIR_FLOORS:
        raise AssertionError(f"re-derived values differ from the study: {derived}")
    crosses_sibling = certificate.certified_member_bound < sibling
    crosses_next_level = certificate.certified_member_bound < ledger.next_raw_region_level
    if not (crosses_sibling and crosses_next_level and ledger.next_raw_region_level_is_raw):
        raise AssertionError("the refined member does not cross both thresholds")
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "CERTIFIED_SINGLE_MEMBER_HUNTER_TREE_BOUND",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_BRANCH": TASK_BRANCH,
        "SOURCE_FINGERPRINT": {
            "MODULE": MODULE_RELATIVE,
            "MODULE_SHA256": file_sha256(MODULE_RELATIVE),
        },
        "UPSTREAM_SHA256": verify_upstream_fingerprints(),
        "STATE_ID": STATE_ID,
        "REGION_SHA256": REGION_SHA256,
        "MEMBER_ID": MEMBER_ID,
        "MEMBER_COUNTS": _sparse_text(MEMBER_SPARSE),
        "MEMBER_TYPE_CELLS": {
            str(index): list(cells) for index, cells in MEMBER_TYPE_CELLS.items()
        },
        "R24_LEDGER": {
            "STATE_TERM": ledger.state_term,
            "REGION_COMPRESSED_MEMBERS": ledger.region_member_count,
            "REGION_TYPE_VECTORS": ledger.region_type_vector_count,
            "MEMBER_RAW_BOUND": ledger.member_raw_bound,
            "MEMBER_FINAL_BOUND": ledger.member_final_bound,
            "MEMBER_REPRESENTED_VECTOR_COUNT": ledger.member_represented_vector_count,
            "LADDER_FINAL_BOUNDS": list(ledger.ladder_final_bounds),
            "NEXT_RAW_REGION_LEVEL": ledger.next_raw_region_level,
        },
        "EVENT_DEFINITION_STATUS": "VERIFIED_EXACT_SAME_RESIDUAL_EVENTS",
        "EVENT_DEFINITION": {
            "OUTCOME_MODEL": lemma,
            "RESIDUAL_EVENT": (
                "R_C = E_C minus (E_A union E_B): 7-sets X with |C n X| >= 3, "
                "|A n X| <= 2 and |B n X| <= 2, times 7 outcomes"
            ),
            "ANCHOR_UNION": events.anchor_union,
            "RESIDUAL_EVENT_SIZES": [list(row) for row in events.residual_event_sizes],
            "RESIDUAL_SUM": events.residual_sum,
            "RAW_UNION_BOUND_NO_CORRECTION": events.raw_union_bound,
            "ANCHOR_PAIR_S2": events.anchor_pair_s2,
            "ANCHOR_TRIPLE_S3": events.anchor_triple_s3,
            "IDENTITY": (
                "|union E| = |E_A u E_B| + |union R_C|; |R_C| = N - I(s+a) - I(s+b) + J "
                "is recounted per type, and the sum equals R14 joint_constant - S2 + S3"
            ),
            "ANCHOR_TERMS_COUNTED_ONCE": (
                "Anchor intersections enter only |E_A u E_B| and each |R_C|; pair rows "
                "count |R_C n R_D| of the same anchor-excluded events (four-set "
                "inclusion-exclusion with the quadruple add-back); the tree subtracts "
                "only residual-residual overlaps"
            ),
        },
        "PAIR_TABLE_STATUS": "VERIFIED_20_ROWS_INDEPENDENT_REPLAY_EQUALS_R8",
        "PAIR_TABLE": {
            "TYPE_PAIRS": [list(pair) for pair in member_type_pairs()],
            "ROW_COUNT": len(rows),
            "ROWS": [
                [row.left_type, row.right_type, *row.overlap, row.residual_intersection]
                for row in rows
            ],
            "ROW_COLUMNS": ["left", "right", "shared", "a_only", "b_only", "outside", "value"],
            "ROWS_SHA256": certificate.pair_rows_sha256,
            "PAIR_FLOOR_BY_TOTAL_OVERLAP": list(certificate.pair_floors),
            "FLOOR_RULE": "phi(t) = min of every exact row with total overlap t",
        },
        "PAIR_OVERLAP_COVERAGE": {
            "COVERED_TOTALS": list(range(MAXIMUM_PAIR_OVERLAP + 1)),
            "CELL_RANGES": "max(0,c+d-capacity) <= x <= min(c,d) in each of 3,3,3,40 labels",
            "ABOVE_THREE": (
                "EXCLUDED_BY_FAMILY_DEFINITION: Family A splits by the exact portfolio "
                "maximum overlap r (heavy_pair_case); R3 is r = 3, so every pair, "
                "residual pairs included, overlaps in at most 3 labels (R5 "
                "PAIRWISE_MAXIMUM_OVERLAP); threshold_edge_counts rejects t > 3"
            ),
            "FAMILY_SOURCE_CEILING": family_pair_overlap_ceiling(),
            "R6_OVERLAP_VECTORS_EQUAL": True,
            "HEAVY_PAIR_R3_PROFILE_COUNT": len(heavy_pair.local_heavy_pair_profiles(3)),
        },
        "COLLISION_FLOOR_STATUS": "VERIFIED_80",
        "COLLISION_FLOOR": {
            "CELL_INCIDENCES": list(certificate.cell_incidences),
            "CELL_LABELS": [len(labels) for labels in CELL_LABELS],
            "CELL_FLOORS": list(certificate.cell_collision_floors),
            "TOTAL": certificate.collision_floor,
            "IDENTITY": (
                "sum_{i<j} t_ij = sum_x C(d_x,2) over all 49 labels; for t in 0..3, "
                "t = [t>=1]+[t>=2]+[t>=3], so the sum equals e1+e2+e3"
            ),
            "CONVEXITY": "balanced frequencies minimise sum C(d,2) for a fixed total",
            "BALANCED_MASS_EXHAUSTIVE_ROWS": balanced_rows,
        },
        "TREE_RANK_PROOF_STATUS": "PROVED_WITH_EXHAUSTIVE_SMALL_CASE_REGRESSION",
        "TREE_RANK_PROOF": {
            "HUNTER": (
                "Root T anywhere and order vertices so parents come first; "
                "|U R| = sum_i |R_i minus U_{j<i} R_j| <= |R_root| + "
                "sum_{i != root} |R_i minus R_parent(i)|"
            ),
            "NESTED_TREE": (
                "Extend a spanning forest of G_3 to one of G_2, G_1 and K_18; the tree "
                "holds rank(G_k) edges with overlap >= k, so its phi-weight is "
                "17 phi(0) + sum_k (phi(k)-phi(k-1)) rank(G_k), phi nondecreasing"
            ),
            "RANK_FLOOR": (
                "Components n_1..n_c with rank r = sum (n_i - 1) hold at most "
                "sum C(n_i,2) <= C(r+1,2) edges, as C(a+1,2)+C(b+1,2)+ab = C(a+b+1,2); "
                "so rank(G_t) >= rho(e_t), rho(e) = min{r : C(r+1,2) >= e}"
            ),
            "RANK_ALGEBRA_ROWS": rank_algebra_rows,
            "RANK_FLOOR_EXHAUSTIVE_GRAPHS_ON_6_VERTICES": tree_rank_graphs,
            "THRESHOLD_TREE_EXHAUSTIVE_K4_LABELLINGS": threshold_labellings,
            "HUNTER_EXHAUSTIVE_SMALL_FAMILY_TREE_CHECKS": hunter_small,
        },
        "TREE_MINIMUM": {
            "CENSUS": "153 >= e1 >= e2 >= e3 >= 0, e1 + e2 + e3 >= 80",
            "CENSUS_SIZE": tree.census_size,
            "MINIMIZER_E": list(tree.edge_counts),
            "MINIMIZER_RHO": list(tree.rank_floors),
            "FORMULA": "17*phi(0) + sum_k (phi(k) - phi(k-1)) * rho(e_k)",
        },
        "CORRECTIONS": {
            "R6_PAIR_SUM": certificate.pair_sum_correction,
            "R5_FOREST": certificate.forest_correction,
            "R14_RATIONAL": certificate.rational_correction,
            "HUNTER_TREE": certificate.hunter_correction,
            "COMBINATION": "MAX_OF_VALID_LOWER_BOUNDS_NEVER_SUM",
            "CERTIFIED_CORRECTION": certificate.certified_correction,
        },
        "HUNTER_CORRECTION": certificate.hunter_correction,
        "CERTIFIED_MEMBER_BOUND": certificate.certified_member_bound,
        "EXISTING_RATIONAL_BOUND": rational_bound,
        "ADDITIONAL_REDUCTION": rational_bound - certificate.certified_member_bound,
        "REDUCTION_FROM_R24_LEDGER": ledger.member_final_bound - certificate.certified_member_bound,
        "THRESHOLDS": {
            "SIBLING_ID": "[0,13][5,4][16,1]",
            "SIBLING_RATIONAL_BOUND": sibling,
            "CROSSES_SIBLING": crosses_sibling,
            "NEXT_RAW_REGION_LEVEL": ledger.next_raw_region_level,
            "CROSSES_NEXT_RAW_REGION_LEVEL": crosses_next_level,
        },
        "CAP17_COUNTEREXAMPLE_STATUS": "REPRODUCED_NU_18_CAP17_REFUTED",
        "NU_LE_17": "\u03bd <= 17 REFUTED",
        "CAP17_COUNTEREXAMPLE": {
            "ANCHORS": [sorted(ANCHOR_A), sorted(ANCHOR_B)],
            "OUTCOME_SET": sorted(CAP17_WITNESS_OUTCOME_SET),
            "RESIDUAL_TICKETS": [list(ticket) for ticket in CAP17_WITNESS_RESIDUAL_TICKETS],
            "MEMBER_COUNTS": _sparse_text(witness.member_sparse),
            "MAXIMUM_PAIR_OVERLAP": witness.maximum_pair_overlap,
            "ANCHOR_HITS_ON_OUTCOME_SET": list(witness.anchor_hits_on_outcome_set),
            "RESIDUAL_MULTIPLICITY": witness.residual_multiplicity,
        },
        "WITNESS_SOUNDNESS_STATUS": "CONSISTENT",
        "WITNESS_SOUNDNESS": {
            "OVERLAP_HISTOGRAM_0_TO_3": list(witness.overlap_histogram),
            "COLLISION_MASS": witness.collision_mass,
            "LABEL_COLLISION_MASS": witness.label_collision_mass,
            "EDGE_COUNTS": list(witness.edge_counts),
            "GRAPH_RANKS": list(witness.graph_ranks),
            "PHI_TREE_WEIGHT": witness.floor_tree_weight,
            "EXACT_MAXIMUM_TREE_WEIGHT": witness.exact_tree_weight,
            "EXACT_PAIRS_EQUAL_TABLE_ROWS": witness.exact_rows_match_table,
            "MEANING": (
                "On a real member portfolio: certificate <= phi-tree weight <= exact "
                "maximum tree weight <= true union correction"
            ),
        },
        "R3_BOUND_CLAIM": "NONE",
        "STATE_TERM_CLAIM": "NONE",
        "CERTIFICATE_SCOPE": f"{STATE_ID} member {MEMBER_ID} only",
        "NEW_HEAVY_SOLVER_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "WORKTREE_DISPOSITION": "RETAIN",
    }


def encode(result: Mapping[str, Any]) -> str:
    return json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write the committed result JSON")
    arguments = parser.parse_args(argv)
    text = encode(build_result())
    if arguments.write:
        RESULT_PATH.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
