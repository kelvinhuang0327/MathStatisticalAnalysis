"""Exact Hunter tree certificates for the preserved eleven current R3 State members.

The immutable next-eleven result leaves State ``s2-13548976-s3-951748`` at its
eleven preserved members (twelve vectors), whose bound still carries only the
forest correction.  In one portfolio the 18 residual events
``R_i = E_i minus (E_A union E_B)`` obey Hunter's inequality
``|union R_i| <= sum |R_i| - sum_{(i,j) in T} |R_i n R_j|`` for every spanning tree T.
An independent 7-set counter recounts every exact residual pair row of the
cohort's occupied type pairs; the row minima by total overlap are phi(0..3).
The balanced label-collision mass Q forces e1 + e2 + e3 >= Q threshold edges,
and the nested threshold tree with forest-rank floors rho(e) gives the small
integer relaxation H(Q).  The correction is the max of the R6 pair, forest, R14
and Hunter floors, never a sum; a compressed member takes its weakest vector.
The other 1,416 members (both earlier R14 batches included), Tail and
classified terms are preserved.  No solver, R7 census or outcome enumeration
runs.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from functools import cache
from hashlib import sha256
from itertools import combinations, pairwise, product
from math import comb
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_heavy_pair_r3plus_global_bound_r3 as heavy_pair
from lottolab.research import b649_k20_outside_min_s2_global_penalty_bound_r1 as r1
from lottolab.research import b649_k20_r3_current_state_next_eleven_r14_certificate_r1 as eleven
from lottolab.research import b649_k20_r3_exact_anchor_neighborhood_envelope_r6 as r6
from lottolab.research import b649_k20_r3_state_13548976_top_band_certificate_r1 as catalog

six = eleven.six
r5, r7, r8, r12, r14 = catalog.r5, eleven.r7, eleven.r8, eleven.r12, eleven.r14
CountVector = eleven.CountVector
dense, sparse, digest, member_id = eleven.dense, eleven.sparse, eleven.digest, eleven.member_id
member_bound = eleven.member_bound
TASK_ID = "B649_K20_R3_PRESERVED_ELEVEN_HUNTER_CERTIFICATE_R1"
TASK_BRANCH = "codex/b649-k20-r3-preserved-eleven-hunter-certificate-r1"
BASE_HEAD = "226bff9080b9be445bbeae487f9bddb5de504fe5"
BASE_TREE = "497946017b995296746f3a494af8d0d141323235"
ELEVEN_RESULT_SHA256 = "a210c8d0ff0d7d7b1e75c1f01436ebcc4b22e2ba3dcba35cc63196a519b39bfd"
TARGET_STATE_ID, REGION_SHA256 = eleven.TARGET_STATE_ID, eleven.REGION_SHA256
COHORT_MEMBER_COUNT, COHORT_VECTOR_COUNT = 11, 12
RESIDUAL_EVENT_DEFINITION = eleven.RESIDUAL_EVENT_DEFINITION
RESIDUAL_EVENT_COUNT = r8.OUTSIDE_TICKET_COUNT
MAXIMUM_PAIR_OVERLAP = 3
HUNTER_RULE = "(n-1)*phi(0) + SUM_k (phi(k)-phi(k-1))*rho(e_k), e1>=e2>=e3, e1+e2+e3>=Q"
CORRECTION_COMBINATION = "MAX(R6_PAIR, FOREST, R14_RATIONAL, HUNTER_TREE)"
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_RELATIVE = six.RESULTS + "b649-k20-r3-preserved-eleven-hunter-certificate-r1-result.json"
RESULT_PATH = REPO_ROOT / RESULT_RELATIVE
_SOURCES = "src/lottolab/research/"
UPSTREAM_SHA256 = {
    **eleven.UPSTREAM_SHA256,
    eleven.RESULT_RELATIVE: ELEVEN_RESULT_SHA256,
    _SOURCES + "b649_k20_r3_current_state_next_eleven_r14_certificate_r1.py": (
        "7a9d433efec9bba5e0cbdc4342edf1112787464b1da524c5e4c55fc0d12a7375"
    ),
    _SOURCES + "b649_k20_outside_min_s2_global_penalty_bound_r1.py": (
        "7706e57e77df6e786e77c4824f3c72663fdae73b20aa5f6797192689f2b6ea62"
    ),
    _SOURCES + "b649_k20_heavy_pair_r3plus_global_bound_r3.py": (
        "379f55ef87c2f7ffddc00caf7a7b5756810e1a3490ba3eb0d32327684f111139"
    ),
}
# Official outcome model: any prize iff |T n (D u {s})| >= 3; (D, s) -> 7-set is 7-to-1.
POOL_SIZE, TICKET_SIZE, WIN_HITS = r1.POOL_SIZE, 6, 3
OUTCOME_SET_SIZE = OUTCOMES_PER_SET = 7
# R8's support label space: shared 0..2, A-only 3..5, B-only 6..8, outside 9..48.
CELL_LABELS = (tuple(range(0, 3)), tuple(range(3, 6)), tuple(range(6, 9)), tuple(range(9, 49)))
ANCHOR_A = frozenset(CELL_LABELS[0] + CELL_LABELS[1])
ANCHOR_B = frozenset(CELL_LABELS[0] + CELL_LABELS[2])
# Regression references only; every floor, mass and bound is recomputed.
EXPECTED_START_UB = 355_630_198
EXPECTED_FINAL_UB = 355_629_750
EXPECTED_CERTIFIED_MAX = 351_996_806
EXPECTED_PAIR_FLOORS = (91_700, 503_741, 1_532_244, 3_162_411)
EXPECTED_HUNTER_BY_MASS = {76: 6_503_392, 77: 6_503_392, 79: 6_915_433}
EXPECTED_R14_FLOOR = 5_103_875
EXPECTED_TABLE_SHAPE = (24, 134)
EXPECTED_NEXT_STATE = ("state:s2-13169800-s3-789320", 355_628_469)
EXPECTED_REMAINING_GAP = 42_365_862
SUMMARY_FIELDS = (
    "TASK_STATUS",
    "REGION_SHA256",
    "COHORT_MEMBER_COUNT",
    "REPRESENTED_VECTOR_COUNT",
    "HUNTER_PAIR_FLOOR_STATUS",
    "COLLISION_MASS_STATUS",
    "CERTIFIED_COHORT_MAX",
    "PRESERVED_REMAINDER_MAX",
    "FINAL_STATE_BOUND",
    "START_COMPLETE_R3_UB",
    "FINAL_COMPLETE_R3_UB",
    "FINAL_OWNER_IDS",
    "REMAINING_GAP",
    "WITNESS_SOUNDNESS_STATUS",
    "NON_DUPLICATE_CREDIT_STATUS",
    "NEW_HEAVY_SOLVER_STARTED",
    "PRODUCTION_MUTATION",
)

Cells = tuple[int, int, int, int]
Ticket = frozenset[int]
PairRow = tuple[int, int, int, int, int, int, int]


def verify_upstream_fingerprints() -> dict[str, str]:
    observed = {
        relative: sha256((REPO_ROOT / relative).read_bytes()).hexdigest()
        for relative in UPSTREAM_SHA256
    }
    if observed != UPSTREAM_SHA256:
        raise AssertionError("immutable source fingerprint mismatch")
    return observed


@cache
def eleven_authority() -> dict[str, Any]:
    verify_upstream_fingerprints()
    stored = cast(dict[str, Any], json.loads((REPO_ROOT / eleven.RESULT_RELATIVE).read_text()))
    if stored["TASK_ID"] != eleven.TASK_ID or eleven.verify_result(stored)["status"] != "PASS":
        raise AssertionError("eleven-member source certificate failed replay")
    return stored


def current_member_bounds(members: tuple[catalog.LedgerMember, ...]) -> dict[CountVector, int]:
    """Replay the source catalog with both earlier R14 batches already applied."""

    authority = eleven_authority()
    priors = eleven.current_member_bounds(members)
    source_bounds = six.replaced_bounds(priors, authority["MEMBER_CERTIFICATES"])
    expected = [
        {
            "member_id": member_id(member.counts),
            "witness_counts": sparse(member.counts),
            "represented_vector_count": member.represented_vector_count,
            "raw_bound": member.raw_bound,
            "prior_bound": priors[member.counts],
            "final_bound": source_bounds[member.counts],
        }
        for member in members
    ]
    if authority["COMPLETE_REGION_MEMBERS"] != catalog.normalized(expected):
        raise AssertionError("eleven-member source catalog differs from its replay")
    return source_bounds


def earlier_certificates() -> dict[str, list[dict[str, Any]]]:
    authority = eleven_authority()
    return {
        "SIX_R14": authority["ORIGINAL_SIX_CERTIFICATES"],
        "ELEVEN_R14": authority["MEMBER_CERTIFICATES"],
    }


def preserved_eleven_members(
    members: tuple[catalog.LedgerMember, ...], priors: dict[CountVector, int]
) -> tuple[catalog.LedgerMember, ...]:
    authority = eleven_authority()
    maximum = max(priors.values())
    cohort = tuple(member for member in members if priors[member.counts] == maximum)
    previous = {
        dense(row["witness_counts"]) for rows in earlier_certificates().values() for row in rows
    } | set(six.sealed_top_band_bounds())
    if (
        set(priors) != {member.counts for member in members}
        or len(cohort) != COHORT_MEMBER_COUNT
        or sum(member.represented_vector_count for member in cohort) != COHORT_VECTOR_COUNT
        or any(member.counts in previous for member in cohort)
        or any(priors[member.counts] != member.raw_bound for member in cohort)
        or any(member.final_bound != member.raw_bound for member in cohort)
        or [member_id(member.counts) for member in cohort] != authority["PRESERVED_MAX_MEMBER_IDS"]
        or maximum != authority["PRESERVED_COHORT_MAX"]
    ):
        raise AssertionError(
            "preserved eleven-member coverage or unused correction identity failed"
        )
    return cohort


# ---------------------------------------------------------------- residual events


def count_seven_sets(winners: Sequence[Ticket], losers: Sequence[Ticket]) -> int:
    """7-sets X of the 49 labels with |W n X| >= 3 for every winner, <= 2 for every loser."""

    tickets = (*winners, *losers)
    for ticket in tickets:
        if len(ticket) != TICKET_SIZE or not all(0 <= label < POOL_SIZE for label in ticket):
            raise ValueError("every ticket must hold six labels from 0..48")
    regions: dict[int, int] = {}
    for label in range(POOL_SIZE):
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
                if any(hit >= WIN_HITS for hit in hits[len(winners) :]):
                    continue
                key = (state[0] + take, *hits)
                following[key] = following.get(key, 0) + ways * comb(size, take)
        states = following
    return sum(
        ways
        for state, ways in states.items()
        if state[0] == OUTCOME_SET_SIZE
        and all(hit >= WIN_HITS for hit in state[1 : len(winners) + 1])
    )


def outcome_count(winners: Sequence[Ticket], losers: Sequence[Ticket] = ()) -> int:
    return OUTCOMES_PER_SET * count_seven_sets(winners, losers)


@cache
def seven_set_lemma_check() -> dict[str, Any]:
    """Tie the counter to the official single-ticket and pair-overlap outcome counts."""

    outside = CELL_LABELS[3]
    single = outcome_count((frozenset(outside[:6]),))
    pairs = tuple(
        outcome_count((frozenset(outside[:6]), frozenset(outside[6 - overlap : 12 - overlap])))
        for overlap in range(TICKET_SIZE + 1)
    )
    if (
        single != r14.canonical_primitives()["SINGLE_TICKET_ANY_PRIZE"]
        or pairs != r1.pair_intersection_table()
        or pairs != tuple(r1.pair_intersection_count(overlap) for overlap in range(7))
        or tuple(len(labels) for labels in CELL_LABELS) != r8.ANCHOR_CELL_CAPACITIES
    ):
        raise AssertionError("the 7-set counter disagrees with the official outcome counts")
    return {
        "RULE": "any prize <=> |T n (D u {s})| >= 3; (D,s) -> D u {s} is 7-to-1 onto 7-sets",
        "SINGLE_TICKET_OUTCOMES": single,
        "PAIR_INTERSECTION_BY_OVERLAP": list(pairs),
    }


def type_cells(type_index: int) -> Cells:
    profile = r5.anchor_incidence_profiles()[type_index]
    return profile.shared, profile.a_only, profile.b_only, profile.outside


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
        left_labels.update(labels[:left_count])
        right_labels.update(labels[:both])
        right_labels.update(labels[left_count : left_count + right_count - both])
    if len(left_labels) != TICKET_SIZE or len(right_labels) != TICKET_SIZE:
        raise ValueError("cell counts must describe six-label tickets")
    return frozenset(left_labels), frozenset(right_labels)


@cache
def residual_event_size(type_index: int) -> int:
    profile = r5.anchor_incidence_profiles()[type_index]
    cells = type_cells(type_index)
    size = outcome_count(realize_pair(cells, cells, cells)[:1], (ANCHOR_A, ANCHOR_B))
    single = int(seven_set_lemma_check()["SINGLE_TICKET_OUTCOMES"])
    if size != single - profile.pair_recovery_cost + profile.triple_recovery:
        raise AssertionError("residual event size disagrees with N - I(s+a) - I(s+b) + J")
    return size


@cache
def anchor_union_size() -> int:
    excluded = count_seven_sets((), (ANCHOR_A, ANCHOR_B))
    union = OUTCOMES_PER_SET * (comb(POOL_SIZE, OUTCOME_SET_SIZE) - excluded)
    single = int(seven_set_lemma_check()["SINGLE_TICKET_OUTCOMES"])
    if union != 2 * single - r1.pair_intersection_count(r5.ANCHOR_OVERLAP):
        raise AssertionError("the anchor union is not 2N - I(3)")
    return union


@cache
def family_pair_overlap_ceiling() -> int:
    """Family A R3 is the exact maximum-overlap-3 case, so every pair shares at most 3."""

    case = heavy_pair.heavy_pair_case(MAXIMUM_PAIR_OVERLAP)
    try:
        heavy_pair.heavy_pair_case(MAXIMUM_PAIR_OVERLAP - 1)
    except ValueError:
        pass
    else:
        raise AssertionError("Family A must reject a maximum overlap below 3")
    profiles = heavy_pair.local_heavy_pair_profiles(case.maximum_pair_overlap)
    constraints = cast(dict[str, Any], r5.family_a_result_record()["CAPACITY_CONSTRAINTS"])
    pairwise_rule, type_rules = constraints["PAIRWISE_MAXIMUM_OVERLAP"], constraints["TYPE_RULES"]
    if (
        case.maximum_pair_overlap != MAXIMUM_PAIR_OVERLAP
        or case.maximum_pair_overlap != r5.ANCHOR_OVERLAP
        or not profiles
        or any(
            max(profile.left_overlap, profile.right_overlap) > case.maximum_pair_overlap
            for profile in profiles
        )
        or not isinstance(pairwise_rule, str)
        or "at most 3" not in pairwise_rule
        or not isinstance(type_rules, str)
        or "s+a<=3" not in type_rules
        or "s+b<=3" not in type_rules
    ):
        raise AssertionError("the R3 family does not exclude pair overlaps above 3")
    return case.maximum_pair_overlap


def feasible_cell_overlaps(left: Cells, right: Cells) -> tuple[Cells, ...]:
    ceiling = family_pair_overlap_ceiling()
    ranges = tuple(
        range(max(0, left_count + right_count - len(labels)), min(left_count, right_count) + 1)
        for labels, left_count, right_count in zip(CELL_LABELS, left, right, strict=True)
    )
    return tuple(
        (shared, a_only, b_only, outside)
        for shared, a_only, b_only, outside in product(*ranges)
        if shared + a_only + b_only + outside <= ceiling
    )


def occupied_type_pairs(vectors: Iterable[CountVector]) -> tuple[tuple[int, int], ...]:
    return tuple(sorted({pair for vector in vectors for pair in six.occupied_type_pairs(vector)}))


@cache
def exact_pair_rows(type_pairs: tuple[tuple[int, int], ...]) -> tuple[PairRow, ...]:
    """Recount every residual pair row of the occupied type pairs; require R8 equality."""

    table_api = "_pair_event_correction_table"
    rows: list[PairRow] = []
    for left_type, right_type in type_pairs:
        left, right = type_cells(left_type), type_cells(right_type)
        overlaps = feasible_cell_overlaps(left, right)
        independent = {
            overlap: outcome_count(realize_pair(left, right, overlap), (ANCHOR_A, ANCHOR_B))
            for overlap in overlaps
        }
        table = cast(tuple[tuple[int, ...], ...], getattr(r8, table_api)(left_type, right_type))
        committed = {(row[0], row[1], row[2], row[3]): int(row[4]) for row in table}
        if (
            left_type > right_type
            or not overlaps
            or committed != independent
            or set(r6.feasible_pair_overlap_vectors(left_type, right_type)) != set(overlaps)
        ):
            raise AssertionError(f"residual pair rows differ for types {(left_type, right_type)}")
        rows.extend(
            (left_type, right_type, *key, value) for key, value in sorted(independent.items())
        )
    return tuple(rows)


def pair_floors(rows: Sequence[PairRow]) -> Cells:
    floors: list[int] = []
    for total in range(MAXIMUM_PAIR_OVERLAP + 1):
        values = [row[6] for row in rows if sum(row[2:6]) == total]
        if not values:
            raise AssertionError(f"no exact pair row covers total overlap {total}")
        floors.append(min(values))
    return floors[0], floors[1], floors[2], floors[3]


def require_safe_pair_floors(floors: Sequence[int], rows: Sequence[PairRow]) -> None:
    if len(floors) != MAXIMUM_PAIR_OVERLAP + 1 or floors[0] < 0:
        raise AssertionError("one nonnegative floor is required for each total overlap 0..3")
    if any(floors[sum(row[2:6])] > row[6] for row in rows):
        raise AssertionError("a pair floor exceeds an exact row of its total overlap")
    if any(low > high for low, high in pairwise(floors)):
        raise AssertionError("pair floors must be nondecreasing for threshold weights")


# ---------------------------------------------------------------- Hunter tree relaxation


@cache
def rank_floor(edge_count: int) -> int:
    """rho(e): the least forest rank r of a graph with e edges, C(r+1,2) >= e."""

    if edge_count < 0:
        raise ValueError("edge count must be nonnegative")
    rank = 0
    while comb(rank + 1, 2) < edge_count:
        rank += 1
    return rank


def spanning_forest(
    vertex_count: int, ordered_edges: Iterable[tuple[int, int]]
) -> tuple[tuple[int, int], ...]:
    parent = list(range(vertex_count))

    def find(vertex: int) -> int:
        while parent[vertex] != vertex:
            parent[vertex] = parent[parent[vertex]]
            vertex = parent[vertex]
        return vertex

    forest: list[tuple[int, int]] = []
    for left, right in ordered_edges:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[left_root] = right_root
            forest.append((left, right))
    return tuple(forest)


def graph_rank(vertex_count: int, edges: Iterable[tuple[int, int]]) -> int:
    return len(spanning_forest(vertex_count, edges))


def threshold_tree(
    vertex_count: int, weights: Mapping[tuple[int, int], int]
) -> tuple[tuple[int, int], ...]:
    """Kruskal in decreasing weight: a maximum spanning tree nested over every G_k."""

    return spanning_forest(vertex_count, sorted(weights, key=lambda edge: (-weights[edge], edge)))


def verify_rank_floor_exhaustively(vertex_count: int = 6) -> int:
    edges = tuple(combinations(range(vertex_count), 2))
    for mask in range(1 << len(edges)):
        chosen = [edge for index, edge in enumerate(edges) if mask >> index & 1]
        if graph_rank(vertex_count, chosen) < rank_floor(len(chosen)):
            raise AssertionError(f"rank floor fails on {chosen}")
    return 1 << len(edges)


def verify_rank_floor_algebra(vertex_count: int = RESIDUAL_EVENT_COUNT) -> int:
    limit = vertex_count - 1
    for left in range(limit + 1):
        for right in range(limit + 1 - left):
            if comb(left + 1, 2) + comb(right + 1, 2) + left * right != comb(left + right + 1, 2):
                raise AssertionError("C(a+1,2)+C(b+1,2)+ab = C(a+b+1,2) failed")
    for edge_count in range(comb(vertex_count, 2) + 1):
        rho = rank_floor(edge_count)
        if comb(rho + 1, 2) < edge_count or (rho and comb(rho, 2) >= edge_count) or rho > limit:
            raise AssertionError("rho is not the least feasible forest rank")
    return comb(vertex_count, 2) + 1


def verify_threshold_tree_lemma(vertex_count: int = 4) -> int:
    edges = tuple(combinations(range(vertex_count), 2))
    checked = 0
    for labels in product(range(MAXIMUM_PAIR_OVERLAP + 1), repeat=len(edges)):
        overlaps = dict(zip(edges, labels, strict=True))
        tree = threshold_tree(vertex_count, overlaps)
        if len(tree) != vertex_count - 1 or any(
            sum(1 for edge in tree if overlaps[edge] >= level)
            != graph_rank(vertex_count, [edge for edge in edges if overlaps[edge] >= level])
            for level in range(1, MAXIMUM_PAIR_OVERLAP + 1)
        ):
            raise AssertionError("threshold tree does not hold a spanning forest of each G_k")
        checked += 1
    return checked


def verify_hunter_exhaustively(universe_size: int, event_count: int) -> int:
    """Hunter on every family of subsets of a small universe and every spanning tree."""

    trees = [
        tree
        for tree in combinations(combinations(range(event_count), 2), event_count - 1)
        if graph_rank(event_count, tree) == event_count - 1
    ]
    checked = 0
    for family in product(range(1 << universe_size), repeat=event_count):
        union = 0
        for event in family:
            union |= event
        total = sum(event.bit_count() for event in family)
        for tree in trees:
            weight = sum((family[left] & family[right]).bit_count() for left, right in tree)
            if union.bit_count() > total - weight:
                raise AssertionError("Hunter's inequality failed")
            checked += 1
    return checked


def balanced_collision_mass(incidences: int, labels: int) -> int:
    """min sum_x C(d_x, 2) over nonnegative integers d with sum d = incidences."""

    if incidences < 0 or labels <= 0:
        raise ValueError("incidences and label count must be valid")
    quotient, remainder = divmod(incidences, labels)
    return remainder * comb(quotient + 1, 2) + (labels - remainder) * comb(quotient, 2)


def verify_balanced_mass_exhaustively(maximum_total: int = 12, labels: int = 3) -> int:
    checked = 0
    for frequencies in product(range(maximum_total + 1), repeat=labels):
        if sum(frequencies) > maximum_total:
            continue
        if sum(comb(value, 2) for value in frequencies) < balanced_collision_mass(
            sum(frequencies), labels
        ):
            raise AssertionError("balanced collision mass is not a minimum")
        checked += 1
    return checked


@cache
def hunter_theorem_checks() -> dict[str, int]:
    return {
        "RANK_ALGEBRA_ROWS": verify_rank_floor_algebra(),
        "RANK_FLOOR_GRAPHS_ON_6_VERTICES": verify_rank_floor_exhaustively(),
        "THRESHOLD_TREE_K4_LABELLINGS": verify_threshold_tree_lemma(),
        "HUNTER_SMALL_FAMILY_TREE_CHECKS": (
            verify_hunter_exhaustively(4, 3) + verify_hunter_exhaustively(3, 4)
        ),
        "BALANCED_MASS_ROWS": verify_balanced_mass_exhaustively(),
    }


def cell_incidences(vector: CountVector) -> Cells:
    totals = [0, 0, 0, 0]
    for type_index, count in enumerate(vector):
        if not count:
            continue
        for cell, value in enumerate(type_cells(type_index)):
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
    counts = [0, 0, 0]
    for overlap in overlaps:
        if not 0 <= overlap <= ceiling:
            raise ValueError(f"pair overlap {overlap} is outside the R3 range 0..{ceiling}")
        for level in range(1, overlap + 1):
            counts[level - 1] += 1
    return counts[0], counts[1], counts[2]


def tree_weight_floor(
    floors: Sequence[int], ranks: Sequence[int], vertex_count: int = RESIDUAL_EVENT_COUNT
) -> int:
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
    floors: Cells, collision_floor: int, vertex_count: int = RESIDUAL_EVENT_COUNT
) -> TreeMinimum:
    """Exhaust C(n,2) >= e1 >= e2 >= e3 >= 0 with e1 + e2 + e3 >= Q."""

    capacity = comb(vertex_count, 2)
    rho = [rank_floor(edges) for edges in range(capacity + 1)]
    best: tuple[int, tuple[int, int, int]] | None = None
    census = 0
    for e1 in range(capacity + 1):
        for e2 in range(e1 + 1):
            for e3 in range(max(0, collision_floor - e1 - e2), e2 + 1):
                census += 1
                value = tree_weight_floor(floors, (rho[e1], rho[e2], rho[e3]), vertex_count)
                if best is None or value < best[0]:
                    best = (value, (e1, e2, e3))
    if best is None:
        raise AssertionError("the collision relaxation is infeasible")
    e1, e2, e3 = best[1]
    return TreeMinimum(best[0], best[1], (rho[e1], rho[e2], rho[e3]), census)


def combine_corrections(corrections: Mapping[str, int]) -> int:
    """Valid lower bounds on one union correction combine by max, never by sum."""

    if not corrections or min(corrections.values()) < 0:
        raise ValueError("corrections must be nonnegative and nonempty")
    return max(corrections.values())


def member_correction(vector_corrections: tuple[int, ...]) -> int:
    """A compressed member takes its weakest represented vector."""

    return eleven.compressed_correction(vector_corrections)


# ---------------------------------------------------------------- certificates


def witness_analysis(
    vector: CountVector,
    support: tuple[tuple[int, ...], ...],
    floors: Cells,
    row_values: Mapping[tuple[int, int, Cells], int],
) -> dict[str, Any]:
    """Exact pair structure of one concrete member portfolio against the relaxation."""

    types = tuple(index for index, count in enumerate(vector) for _ in range(count))
    tickets = tuple(frozenset(ticket) for ticket in support)
    overlaps: dict[tuple[int, int], int] = {}
    exact: dict[tuple[int, int], int] = {}
    for left, right in combinations(range(len(tickets)), 2):
        shared, a_only, b_only, outside = (
            len(tickets[left] & tickets[right] & set(labels)) for labels in CELL_LABELS
        )
        low, high = sorted((types[left], types[right]))
        overlaps[(left, right)] = shared + a_only + b_only + outside
        exact[(left, right)] = row_values[(low, high, (shared, a_only, b_only, outside))]
    edge_counts = threshold_edge_counts(overlaps.values())
    label_mass = sum(comb(sum(label in t for t in tickets), 2) for label in range(POOL_SIZE))
    ranks = tuple(
        graph_rank(len(tickets), (edge for edge, value in overlaps.items() if value >= level))
        for level in range(1, MAXIMUM_PAIR_OVERLAP + 1)
    )
    phi_tree = threshold_tree(len(tickets), overlaps)
    phi_weight = sum(floors[overlaps[edge]] for edge in phi_tree)
    exact_weight = sum(exact[edge] for edge in threshold_tree(len(tickets), exact))
    if (
        sum(overlaps.values()) != sum(edge_counts)
        or sum(overlaps.values()) != label_mass
        or phi_weight != tree_weight_floor(floors, ranks, len(tickets))
        or any(rank < rank_floor(count) for rank, count in zip(ranks, edge_counts, strict=True))
        or exact_weight < phi_weight
    ):
        raise AssertionError("witness collision, rank or tree-weight identity failed")
    return {
        "collision_mass": label_mass,
        "edge_counts": list(edge_counts),
        "graph_ranks": list(ranks),
        "phi_tree_weight": phi_weight,
        "exact_tree_weight": exact_weight,
        "exact_residual_pair_moment": sum(exact.values()),
    }


def certify_vector(
    member: catalog.LedgerMember,
    vector: CountVector,
    floors: Cells,
    row_values: Mapping[tuple[int, int, Cells], int],
) -> dict[str, Any]:
    state = catalog.rebuild_member(member)
    vector_state = catalog.rebuild_member(
        replace(member, counts=vector, represented_vector_count=1)
    )
    if eleven.compression_signature(vector_state) != eleven.compression_signature(state):
        raise AssertionError("represented vector has a different compression signature")
    incidences = cell_incidences(vector)
    if incidences != tuple(vector_state.cell_incidences):
        raise AssertionError("cell incidences differ from the R7 state")
    collision_cells = cell_collision_floors(incidences)
    tree = minimum_tree_correction(floors, sum(collision_cells))
    moment = eleven.exact_residual_pair_moment(vector)
    rational = eleven.ceiling_divide_by_9(moment)
    if rational != int(r14.moment_certificate(vector)["correction_lower_bound"]):
        raise AssertionError("R14 residual ceiling drifted from its moment certificate")
    r6_pair = vector_state.residual_pair_union_penalty
    forest = vector_state.complementary_forest_floor
    prior = vector_state.applied_residual_union_penalty
    if prior != max(r6_pair, forest):
        raise AssertionError("previous correction is not the R6/forest max")
    corrections = {
        "R6_PAIR": r6_pair,
        "FOREST": forest,
        "R14_RATIONAL": rational,
        "HUNTER_TREE": tree.correction,
    }
    combined = combine_corrections(corrections)
    uncorrected = r14.joint_constant() - vector_state.anchor_pair_s2 + vector_state.anchor_triple_s3
    residual_sum = sum(
        count * residual_event_size(index) for index, count in enumerate(vector) if count
    )
    if anchor_union_size() + residual_sum != uncorrected:
        raise AssertionError("event decomposition disagrees with the R14 joint expression")
    bound = member_bound(uncorrected, combined)
    if member.raw_bound != uncorrected - prior or bound >= member.raw_bound:
        raise AssertionError("Hunter does not replace the applied correction exactly once")
    support = r12.construct_support_witness(vector)
    if support is None or not r8.validate_support_assignment(vector, support):
        raise AssertionError("represented vector has no valid exact support witness")
    witness = witness_analysis(vector, support, floors, row_values)
    if (
        witness["collision_mass"] < sum(collision_cells)
        or witness["phi_tree_weight"] < tree.correction
        or witness["exact_residual_pair_moment"] != r8.witness_costs(vector, support)[0]
        or witness["exact_residual_pair_moment"] < moment
    ):
        raise AssertionError("exact support witness contradicts the Hunter relaxation")
    return {
        "vector_id": member_id(vector),
        "counts": sparse(vector),
        "residual_event_definition": RESIDUAL_EVENT_DEFINITION,
        "anchor_union": anchor_union_size(),
        "residual_event_sum": residual_sum,
        "uncorrected_anchor_bound": uncorrected,
        "cell_incidences": list(incidences),
        "cell_collision_floors": list(collision_cells),
        "collision_mass": sum(collision_cells),
        "hunter_edge_counts": list(tree.edge_counts),
        "hunter_rank_floors": list(tree.rank_floors),
        "hunter_correction": tree.correction,
        "residual_pair_moment": moment,
        "r14_correction": rational,
        "r6_pair_correction": r6_pair,
        "forest_correction": forest,
        "prior_applied_correction": prior,
        "combined_correction": combined,
        "correction_source": max(corrections, key=lambda name: corrections[name]),
        "vector_new_bound": bound,
        "support_witness": catalog.normalized(support),
        "support_sha256": digest(support),
        "witness_analysis": witness,
    }


def certify_member(
    member: catalog.LedgerMember,
    vectors: tuple[CountVector, ...],
    floors: Cells,
    row_values: Mapping[tuple[int, int, Cells], int],
) -> dict[str, Any]:
    if (
        len(vectors) != member.represented_vector_count
        or len(set(vectors)) != len(vectors)
        or tuple(sorted(vectors)) != vectors
        or min(vectors) != member.counts
    ):
        raise AssertionError("compressed member does not cover its exact represented vectors")
    records = [certify_vector(member, vector, floors, row_values) for vector in vectors]
    state = catalog.rebuild_member(member)
    correction = member_correction(tuple(row["combined_correction"] for row in records))
    uncorrected = r14.joint_constant() - state.anchor_pair_s2 + state.anchor_triple_s3
    bound = max(int(row["vector_new_bound"]) for row in records)
    if bound != member_bound(uncorrected, correction):
        raise AssertionError("compressed member did not take the weakest represented bound")
    return {
        "member_id": member_id(member.counts),
        "witness_counts": sparse(member.counts),
        "represented_vector_count": len(vectors),
        "represented_vectors": [sparse(vector) for vector in vectors],
        "compression_signature": catalog.normalized(eleven.compression_signature(state)),
        "vector_certificates": records,
        "prior_applied_correction": state.applied_residual_union_penalty,
        "member_certified_correction": correction,
        "uncorrected_anchor_bound": uncorrected,
        "member_prior_bound": member.raw_bound,
        "member_raw_bound": member.raw_bound,
        "member_new_bound": bound,
        "correction_combination": CORRECTION_COMBINATION,
        "hunter_correction_applied": True,
    }


def hunter_by_mass(floors: Cells, vectors: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """The exact relaxation minimum once per distinct collision mass Q."""

    rows: list[dict[str, Any]] = []
    for mass in sorted({int(row["collision_mass"]) for row in vectors}):
        tree = minimum_tree_correction(floors, mass)
        rows.append(
            {
                "collision_mass": mass,
                "hunter_correction": tree.correction,
                "minimizer_edge_counts": list(tree.edge_counts),
                "minimizer_rank_floors": list(tree.rank_floors),
                "census_size": tree.census_size,
                "vector_ids": [r["vector_id"] for r in vectors if r["collision_mass"] == mass],
            }
        )
    return rows


def recompute_family(state_bound: int) -> dict[str, Any]:
    authority = eleven_authority()
    terms = tuple(
        (str(row["stable_id"]), int(row["bound"])) for row in authority["FINAL_STATE_TERMS"]
    )
    if len(terms) != 23 or len(dict(terms)) != 23 or TARGET_STATE_ID not in dict(terms):
        raise AssertionError("complete 23-State family identity failed")
    classified = six.classified_terms()
    tail_bound = six.sealed_tail_bound()
    start = six.tail.family_maximum(tail_bound, terms, classified)
    if start != authority["FINAL_FAMILY_MAX_RECOMPUTATION"]:
        raise AssertionError("starting complete R3 family differs from the eleven-member source")
    replaced = tuple(
        (key, state_bound if key == TARGET_STATE_ID else bound) for key, bound in terms
    )
    final = six.tail.family_maximum(tail_bound, replaced, classified)
    aggregate = [
        {"stable_id": key, "bound": bound}
        for key, bound in classified
        if key == catalog.r24.AGGREGATE_ID
    ]
    if (
        aggregate != authority["CLASSIFIED_AGGREGATE"]
        or digest(classified) != authority["CLASSIFIED_TERMS_SHA256"]
        or tail_bound != authority["TAIL_BOUND"]
    ):
        raise AssertionError("preserved Tail or classified aggregate differs from the source")
    competitor = max((bound, key) for key, bound in replaced if key != TARGET_STATE_ID)
    return {
        "start": start,
        "final": final,
        "start_terms": terms,
        "terms": replaced,
        "competitor": {"stable_id": competitor[1], "bound": competitor[0]},
        "tail_bound": tail_bound,
        "classified_count": len(classified),
        "classified_sha256": digest(classified),
        "aggregate": aggregate,
    }


def check_regression(result: dict[str, Any]) -> None:
    hunter = {row["collision_mass"]: row["hunter_correction"] for row in result["HUNTER_BY_MASS"]}
    table = result["PAIR_TABLE"]
    if (
        result["START_COMPLETE_R3_UB"] != EXPECTED_START_UB
        or result["FINAL_COMPLETE_R3_UB"] != EXPECTED_FINAL_UB
        or result["PRESERVED_REMAINDER_MAX"] != EXPECTED_FINAL_UB
        or result["CERTIFIED_COHORT_MAX"] != EXPECTED_CERTIFIED_MAX
        or tuple(result["PAIR_FLOORS"]) != EXPECTED_PAIR_FLOORS
        or hunter != EXPECTED_HUNTER_BY_MASS
        or result["MINIMUM_R14_CORRECTION"] != EXPECTED_R14_FLOOR
        or (len(table["TYPE_PAIRS"]), table["ROW_COUNT"]) != EXPECTED_TABLE_SHAPE
        or tuple(result["NEXT_COMPETING_STATE"].values()) != EXPECTED_NEXT_STATE
        or result["REMAINING_GAP"] != EXPECTED_REMAINING_GAP
    ):
        raise AssertionError("recomputed certificate differs from the regression references")


def build_result() -> dict[str, Any]:
    fingerprints = verify_upstream_fingerprints()
    members = six.region_members()
    priors = current_member_bounds(members)
    cohort = preserved_eleven_members(members, priors)
    states = tuple(catalog.rebuild_member(member) for member in cohort)
    recovered = catalog.r17.represented_vectors(states)
    flat_vectors = [vector for vectors in recovered.values() for vector in vectors]
    if (
        len(recovered) != COHORT_MEMBER_COUNT
        or len(flat_vectors) != COHORT_VECTOR_COUNT
        or len(set(flat_vectors)) != len(flat_vectors)
        or set(recovered) != {member.counts for member in cohort}
    ):
        raise AssertionError("exact eleven-member/twelve-vector coverage failed")
    type_pairs = occupied_type_pairs(flat_vectors)
    rows = exact_pair_rows(type_pairs)
    floors = pair_floors(rows)
    require_safe_pair_floors(floors, rows)
    theorem = hunter_theorem_checks()
    row_values = {(row[0], row[1], (row[2], row[3], row[4], row[5])): row[6] for row in rows}
    records = [
        certify_member(member, recovered[member.counts], floors, row_values) for member in cohort
    ]
    vectors = [row for record in records for row in record["vector_certificates"]]
    bounds = six.replaced_bounds(priors, records)
    certified = {member.counts for member in cohort}
    preserved = {counts: bound for counts, bound in priors.items() if counts not in certified}
    if any(bounds[counts] != bound for counts, bound in preserved.items()):
        raise AssertionError("a preserved region member changed")
    earlier = [
        {"batch": batch, "member_id": row["member_id"], "member_new_bound": row["member_new_bound"]}
        for batch, batch_rows in earlier_certificates().items()
        for row in batch_rows
    ]
    sealed = six.sealed_top_band_bounds()
    final_state_bound = max(bounds.values())
    family = recompute_family(final_state_bound)
    if max(priors.values()) != dict(family["start_terms"])[TARGET_STATE_ID]:
        raise AssertionError("source region maximum differs from its State term")
    masses = sorted({int(row["collision_mass"]) for row in vectors})
    result: dict[str, Any] = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "SUCCESS",
        "TASK_BRANCH": TASK_BRANCH,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "ELEVEN_MEMBER_RESULT_SHA256": ELEVEN_RESULT_SHA256,
        "ELEVEN_MEMBER_VERIFY_STATUS": "PASS",
        "UPSTREAM_FINGERPRINTS_SHA256": fingerprints,
        "STATE_ID": TARGET_STATE_ID,
        "REGION_SHA256": catalog.region_fingerprint(members),
        "REGION_COMPRESSED_MEMBER_COUNT": len(members),
        "REGION_REPRESENTED_VECTOR_COUNT": sum(m.represented_vector_count for m in members),
        "COHORT_MEMBER_COUNT": len(records),
        "REPRESENTED_VECTOR_COUNT": len(vectors),
        "COVERAGE_STATUS": "PASS_11_EXACT_MEMBERS_12_DISTINCT_VECTORS",
        "RESIDUAL_EVENT_DEFINITION": RESIDUAL_EVENT_DEFINITION,
        "OUTCOME_MODEL": seven_set_lemma_check(),
        "ANCHOR_UNION": anchor_union_size(),
        "RESIDUAL_EVENT_SIZES": [
            [index, residual_event_size(index)]
            for index in sorted({p for q in type_pairs for p in q})
        ],
        "PAIR_OVERLAP_CEILING": family_pair_overlap_ceiling(),
        "PAIR_TABLE": {
            "TYPE_PAIRS": [list(pair) for pair in type_pairs],
            "ROW_COUNT": len(rows),
            "ROW_COLUMNS": ["left", "right", "shared", "a_only", "b_only", "outside", "value"],
            "ROWS": [list(row) for row in rows],
            "ROWS_SHA256": digest(rows),
            "RECOUNT": "INDEPENDENT_7_SET_COUNTER_EQUALS_R8_AND_R6_OVERLAP_COVERAGE",
        },
        "HUNTER_PAIR_FLOOR_STATUS": "PASS_24_TYPE_PAIRS_134_EXACT_ROWS_PHI_NONDECREASING",
        "PAIR_FLOORS": list(floors),
        "COLLISION_MASS_STATUS": "PASS_BALANCED_LABEL_MASS_" + "_".join(map(str, masses)),
        "HUNTER_THEOREM_CHECKS": theorem,
        "HUNTER_RULE": HUNTER_RULE,
        "HUNTER_BY_MASS": hunter_by_mass(floors, vectors),
        "CORRECTION_COMBINATION": CORRECTION_COMBINATION,
        "MEMBER_CERTIFICATES": records,
        "MINIMUM_HUNTER_CORRECTION": min(row["hunter_correction"] for row in vectors),
        "MINIMUM_R14_CORRECTION": min(row["r14_correction"] for row in vectors),
        "CORRECTION_FLOORS": [row["member_certified_correction"] for row in records],
        "CERTIFIED_COHORT_MAX": max(row["member_new_bound"] for row in records),
        "EARLIER_CERTIFICATES": earlier,
        "EARLIER_CERTIFICATES_PRESERVED": all(
            bounds[dense(row["witness_counts"])] == row["member_new_bound"]
            for batch_rows in earlier_certificates().values()
            for row in batch_rows
        )
        and all(bounds[counts] == bound for counts, bound in sealed.items()),
        "PRESERVED_MEMBER_COUNT": len(preserved),
        "PRESERVED_REMAINDER_MAX": max(preserved.values()),
        "PRESERVED_MAX_MEMBER_IDS": [
            member_id(c) for c, b in preserved.items() if b == max(preserved.values())
        ],
        "COMPLETE_REGION_MEMBERS": [
            {
                "member_id": member_id(member.counts),
                "witness_counts": sparse(member.counts),
                "represented_vector_count": member.represented_vector_count,
                "raw_bound": member.raw_bound,
                "prior_bound": priors[member.counts],
                "final_bound": bounds[member.counts],
            }
            for member in members
        ],
        "FINAL_STATE_BOUND": final_state_bound,
        "START_STATE_TERMS": [{"stable_id": key, "bound": b} for key, b in family["start_terms"]],
        "FINAL_STATE_TERMS": [{"stable_id": key, "bound": b} for key, b in family["terms"]],
        "STATE_TERM_COUNT": len(family["terms"]),
        "CHANGED_STATE_IDS": [
            key
            for (key, before), (_, after) in zip(
                family["start_terms"], family["terms"], strict=True
            )
            if before != after
        ],
        "NEXT_COMPETING_STATE": family["competitor"],
        "TAIL_BOUND": family["tail_bound"],
        "CLASSIFIED_TERM_COUNT": family["classified_count"],
        "CLASSIFIED_TERMS_SHA256": family["classified_sha256"],
        "CLASSIFIED_AGGREGATE": family["aggregate"],
        "CLASSIFIED_MAX": family["final"]["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"],
        "START_FAMILY_MAX_RECOMPUTATION": family["start"],
        "FINAL_FAMILY_MAX_RECOMPUTATION": family["final"],
        "START_COMPLETE_R3_UB": family["start"]["R3_BOUND"],
        "FINAL_COMPLETE_R3_UB": family["final"]["R3_BOUND"],
        "FINAL_OWNER_IDS": family["final"]["OWNER_IDS"],
        "CURRENT_INCUMBENT": catalog.r24.INCUMBENT,
        "REMAINING_GAP": int(family["final"]["R3_BOUND"]) - catalog.r24.INCUMBENT,
        "NON_DUPLICATE_CREDIT_STATUS": "PASS_MAX_R6_FOREST_R14_HUNTER_SINGLE_REPLACEMENT",
        "DUPLICATE_CORRECTIONS": 0,
        "WITNESS_SOUNDNESS_STATUS": "PASS_12_EXACT_SUPPORT_WITNESSES_PHI_TREE_GE_HUNTER",
        "FULL_STATE_CATALOG_STATUS": "PASS_1427_OF_1427_1416_UNCHANGED",
        "VECTOR_RECOVERY": "EXACT_SELECTED_LOSS_R17_COMPRESSION_SIGNATURE",
        "R7_CENSUS_REBUILD_CALLS": 0,
        "NEW_HEAVY_SOLVER_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "WORKTREE_DISPOSITION": "RETAIN",
    }
    if not result["EARLIER_CERTIFICATES_PRESERVED"] or result["CHANGED_STATE_IDS"] != [
        TARGET_STATE_ID
    ]:
        raise AssertionError("an earlier certificate or another State term changed")
    check_regression(result)
    return catalog.normalized(result)


def verify_result(result: dict[str, Any]) -> dict[str, Any]:
    """Validate stored supports independently, then replay every result field."""

    verify_upstream_fingerprints()
    for member in result["MEMBER_CERTIFICATES"]:
        for row in member["vector_certificates"]:
            counts = dense(row["counts"])
            support = tuple(tuple(int(label) for label in t) for t in row["support_witness"])
            if (
                not r8.validate_support_assignment(counts, support)
                or digest(support) != row["support_sha256"]
            ):
                raise AssertionError("stored support witness or its fingerprint is invalid")
    if result != build_result():
        raise AssertionError("stored certificate differs from the complete exact replay")
    return {"status": "PASS", "certificates": COHORT_MEMBER_COUNT, "vectors": COHORT_VECTOR_COUNT}


def encode(result: dict[str, Any]) -> str:
    return eleven.encode(result)


def summary(result: dict[str, Any]) -> dict[str, Any]:
    return {field: result[field] for field in SUMMARY_FIELDS}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--verify", action="store_true")
    options = parser.parse_args()
    if options.verify:
        stored = cast(dict[str, Any], json.loads(RESULT_PATH.read_text(encoding="utf-8")))
        print(json.dumps(verify_result(stored), sort_keys=True))
        return
    result = build_result()
    if options.write:
        RESULT_PATH.write_text(encode(result), encoding="utf-8")
    print(json.dumps(summary(result), sort_keys=True))


if __name__ == "__main__":
    main()
