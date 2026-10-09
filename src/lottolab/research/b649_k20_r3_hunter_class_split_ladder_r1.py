"""Hunter class-split certificates for the full K20 R3 state ladder (R1).

Scope is the six-member raw ladder of state ``state:s2-12692531-s3-681744`` in
the immutable R24 ledger: ``[0,13]`` plus ``[5,5-k][16,k]`` for k = 0..5.  The
committed certificates for k = 0 (homogeneous Hunter, 93cda125) and k = 1
(class-split Hunter, b479c242) are read by source identity, not redone.  This
module asks whether the class-split formula strictly improves k = 0, and
certifies k = 2..5 from each member's own ticket-type composition: exact R8
pair rows for every occurring type pair, class floors for type-0-incident and
core pairs, the forced label-collision mass, the class-specific forced masses,
the class threshold-tree rank floor and an exact finite census.  Corrections
combine by ``max``, never by a sum.

The state term is then recomputed over all 582 compressed R24 region members
(633 vectors): ladder members take their certified bounds and every other
member keeps its carried R24 final bound.  No portfolio search, solver or
outcome enumeration runs, no R3, R24 or R25 state is modified, and no R3 bound
is claimed.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from hashlib import sha256
from itertools import combinations
from math import comb
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_r3_anchor_incidence_bound_r5 as r5
from lottolab.research import b649_k20_r3_hunter_next_sibling_certificate_r1 as sibling
from lottolab.research import b649_k20_r3_hunter_tree_member_certificate_r1 as hunter
from lottolab.research import b649_k20_r3_state_tail_owner_chase_r14 as r14

TASK_ID = "B649_K20_R3_HUNTER_CLASS_SPLIT_LADDER_R1"
TASK_BRANCH = "codex/b649-k20-r3-hunter-class-split-ladder-r1"
BASE_HEAD = "b479c242dab9a57fa8a7608653307cb08d118c66"
BASE_TREE = "758b6857595336bb5245dd17b9468fd8de4a29e3"
REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_RELATIVE = "src/lottolab/research/b649_k20_r3_hunter_class_split_ladder_r1.py"
RESULT_RELATIVE = sibling.RESULTS + "b649-k20-r3-hunter-class-split-ladder-r1-result.json"
RESULT_PATH = REPO_ROOT / RESULT_RELATIVE
UPSTREAM_SHA256 = {
    sibling.MODULE_RELATIVE: "752d78c4e322f40a4cc79508df9c639ae8ba9b2da6d7c117975bdbe4ef45ced2",
    sibling.RESULT_RELATIVE: "1a43ce6689ca828dd33ef8f09fc31bb580bbef2d55620bc15ba5cd4ad9628269",
}
FIRST_MEMBER_COMMIT = "93cda12572b56aeba16cb057d4ff096386908e72"
CARRIED_MEMBER_COMMIT = BASE_HEAD

STATE_ID = hunter.STATE_ID
REGION_SHA256 = hunter.REGION_SHA256
REGION_COMPRESSED_MEMBERS = 582
REGION_VECTORS = 633
LADDER_TYPES = (sibling.OUTSIDE_TYPE, 5, 16)

Sparse = tuple[tuple[int, int], ...]
Cells = tuple[int, int, int, int]
Floors = tuple[int, int, int, int]
Nested = tuple[int, int, int]

LADDER: tuple[Sparse, ...] = (
    ((0, 13), (5, 5)),
    ((0, 13), (5, 4), (16, 1)),
    ((0, 13), (5, 3), (16, 2)),
    ((0, 13), (5, 2), (16, 3)),
    ((0, 13), (5, 1), (16, 4)),
    ((0, 13), (16, 5)),
)
FIRST_MEMBER = LADDER[0]
CARRIED_MEMBER = LADDER[1]
NEW_MEMBERS = LADDER[2:]
CERTIFIED_MEMBERS: tuple[Sparse, ...] = (FIRST_MEMBER, *NEW_MEMBERS)

# Packet values.  Each one is re-derived; none is an input to a certificate.
PACKET_REFERENCE = {
    "FIRST_MEMBER_HOMOGENEOUS_BOUND": 353_516_478,
    "SECOND_MEMBER_CLASS_SPLIT_BOUND": 353_098_158,
    "SECOND_MEMBER_CLASS_SPLIT_CORRECTION": 7_790_062,
    "R3_DURABLE_BOUND": 355_734_631,
    "NEXT_RAW_REGION_LEVEL": 355_274_920,
    "REGION_COMPRESSED_MEMBERS": REGION_COMPRESSED_MEMBERS,
    "REGION_VECTORS": REGION_VECTORS,
}

# Type-5 tickets of the committed [0,13][5,5] witness, replaced in this order by
# type-16 tickets; the first replacement is the committed sibling witness.
WITNESS_REPLACEMENTS: tuple[tuple[tuple[int, ...], tuple[int, ...]], ...] = (
    (sibling.WITNESS_REPLACED_TICKET, sibling.WITNESS_TYPE16_TICKET),
    ((4, 8, 11, 12, 14, 17), (1, 10, 11, 15, 16, 18)),
    ((6, 9, 11, 12, 13, 17), (1, 10, 12, 15, 19, 20)),
    ((5, 8, 10, 15, 16, 17), (1, 10, 12, 16, 21, 22)),
    ((4, 7, 10, 14, 16, 17), (1, 10, 13, 15, 21, 24)),
)


def file_sha256(relative: str) -> str:
    return sha256((REPO_ROOT / relative).read_bytes()).hexdigest()


@cache
def verify_upstream_fingerprints() -> dict[str, str]:
    if sibling.REPO_ROOT != REPO_ROOT or hunter.REPO_ROOT != REPO_ROOT:
        raise AssertionError("the Hunter primitives load from a different tree")
    sibling.verify_upstream_fingerprints()
    observed = {relative: file_sha256(relative) for relative in UPSTREAM_SHA256}
    if observed != UPSTREAM_SHA256:
        raise AssertionError(f"Hunter sibling fingerprint mismatch: {observed}")
    return observed


def member_id(sparse: Sequence[tuple[int, int]]) -> str:
    return "".join(f"[{index},{count}]" for index, count in sparse)


def type16_count(sparse: Sparse) -> int:
    return dict(sparse).get(16, 0)


def is_ladder_counts(counts: Sequence[int]) -> bool:
    """The R24 ladder predicate: 13 outside tickets, every other ticket type 5 or 16."""

    return counts[sibling.OUTSIDE_TYPE] == 13 and all(
        count == 0 for index, count in enumerate(counts) if index not in LADDER_TYPES
    )


@cache
def verify_ladder_identity() -> dict[int, Cells]:
    """The six members are exactly k = 0..5 and name the two committed members."""

    cells = sibling.member_type_cells()
    for k, sparse in enumerate(LADDER):
        counts = dict(sparse)
        if (
            counts.get(0) != 13
            or counts.get(5, 0) != 5 - k
            or counts.get(16, 0) != k
            or sum(counts.values()) != hunter.RESIDUAL_EVENT_COUNT
            or any(count <= 0 for count in counts.values())
            or list(sparse) != sorted(sparse)
            or not is_ladder_counts(hunter.dense_counts(sparse))
        ):
            raise AssertionError(f"ladder member {k} is not [0,13][5,{5 - k}][16,{k}]")
    if FIRST_MEMBER != hunter.MEMBER_SPARSE or CARRIED_MEMBER != sibling.MEMBER_SPARSE:
        raise AssertionError("the ladder does not name the two committed members")
    if CARRIED_MEMBER != hunter.SIBLING_SPARSE:
        raise AssertionError("the committed certificates disagree on the second member")
    return cells


def require_certified_here(sparse: Sparse) -> None:
    verify_ladder_identity()
    if sparse not in CERTIFIED_MEMBERS:
        raise hunter.CertificateScopeError(
            f"{member_id(sparse)} is not certified by the ladder module of {STATE_ID}"
        )


# ---------------------------------------------------------------- phase 1: pair tables


@cache
def member_rows(sparse: Sparse) -> tuple[hunter.PairRow, ...]:
    """Exact rows of every type pair the member realizes, each replayed against R8."""

    require_certified_here(sparse)
    return tuple(
        row
        for pair in sibling.occurring_type_pairs(sparse)
        for row in sibling.type_pair_rows(*pair)
    )


# ---------------------------------------------------------------- phase 2: collisions


def class_mass_floors(sparse: Sparse) -> tuple[int, int]:
    """Forced collision mass inside each edge class.

    For any ticket set S, sum_{i<j in S} t_ij = sum_x C(d_x^S, 2), at least the
    balanced per-cell floor.  Every pair of two type-0 tickets is
    outside-incident and every pair of two non-type-0 tickets is core.
    """

    outside = tuple(item for item in sparse if item[0] == sibling.OUTSIDE_TYPE)
    core = tuple(item for item in sparse if item[0] != sibling.OUTSIDE_TYPE)
    return (
        sum(hunter.cell_collision_floors(sibling.member_cell_incidences(outside))),
        sum(hunter.cell_collision_floors(sibling.member_cell_incidences(core))),
    )


def class_masses(counts: Sequence[Nested]) -> tuple[int, ...]:
    return tuple(sum(nested) for nested in counts)


def require_class_masses(
    counts: Sequence[Nested], floors: tuple[int, int], collision_floor: int
) -> None:
    """The census minimizer must carry every class-specific forced mass.

    Adding the class constraints shrinks the feasible set, so its minimum is at
    least the census minimum; the census minimizer is feasible for it, so the
    two minima are equal and the class constraints are non-binding.
    """

    if sum(floors) > collision_floor:
        raise AssertionError("the class-specific forced masses exceed the total floor")
    if any(mass < floor for mass, floor in zip(class_masses(counts), floors, strict=True)):
        raise AssertionError("the census minimizer violates a class-specific forced mass")


# ---------------------------------------------------------------- phase 3: certificates


@dataclass(frozen=True)
class LadderMemberCertificate:
    state_id: str
    region_sha256: str
    member_sparse: Sparse
    residual_event_count: int
    maximum_pair_overlap: int
    raw_union_bound: int
    pair_rows_sha256: str
    global_pair_floors: Floors
    class_edge_counts: tuple[int, int]
    class_pair_floors: tuple[Floors, Floors]
    cell_incidences: Cells
    cell_collision_floors: Cells
    collision_floor: int
    class_mass_floors: tuple[int, int]
    class_minimizer_counts: tuple[Nested, ...]
    homogeneous_hunter_correction: int
    class_hunter_correction: int
    pair_sum_correction: int
    forest_correction: int
    rational_correction: int
    certified_correction: int
    certified_member_bound: int


@cache
def rational_correction(sparse: Sparse) -> int:
    return int(r14.moment_certificate(hunter.dense_counts(sparse))["correction_lower_bound"])


@cache
def build_member_certificate(sparse: Sparse) -> LadderMemberCertificate:
    require_certified_here(sparse)
    verify_upstream_fingerprints()
    events = hunter.event_decomposition(sparse)
    rows = member_rows(sparse)
    global_floors = sibling.global_pair_floors(rows)
    floors = sibling.class_pair_floors(rows)
    sizes = sibling.class_edge_counts(sparse)
    incidences = sibling.member_cell_incidences(sparse)
    cell_floors = hunter.cell_collision_floors(incidences)
    collision_floor = sum(cell_floors)
    mass_floors = class_mass_floors(sparse)
    homogeneous = hunter.minimum_tree_correction(global_floors, collision_floor)
    split = sibling.minimum_class_tree_correction(
        sibling.member_edge_classes(sizes, floors), collision_floor
    )
    corrections = sibling.correction_terms(
        events, rational_correction(sparse), homogeneous.correction, split.correction
    )
    certified = hunter.combine_corrections(corrections)
    return LadderMemberCertificate(
        state_id=STATE_ID,
        region_sha256=REGION_SHA256,
        member_sparse=sparse,
        residual_event_count=hunter.RESIDUAL_EVENT_COUNT,
        maximum_pair_overlap=hunter.family_pair_overlap_ceiling(),
        raw_union_bound=events.raw_union_bound,
        pair_rows_sha256=sibling.rows_digest(rows),
        global_pair_floors=global_floors,
        class_edge_counts=sizes,
        class_pair_floors=floors,
        cell_incidences=incidences,
        cell_collision_floors=cell_floors,
        collision_floor=collision_floor,
        class_mass_floors=mass_floors,
        class_minimizer_counts=split.edge_counts,
        homogeneous_hunter_correction=homogeneous.correction,
        class_hunter_correction=split.correction,
        pair_sum_correction=corrections["R6_PAIR_SUM"],
        forest_correction=corrections["R5_FOREST"],
        rational_correction=corrections["R14_RATIONAL"],
        certified_correction=certified,
        certified_member_bound=events.raw_union_bound - certified,
    )


def verify_member_certificate(certificate: LadderMemberCertificate) -> None:
    """Recheck every certificate field from exact inputs; raise on any deviation."""

    sparse = certificate.member_sparse
    if (
        certificate.state_id != STATE_ID
        or certificate.region_sha256 != REGION_SHA256
        or sparse not in CERTIFIED_MEMBERS
    ):
        raise AssertionError("certificate source member differs from a pinned ladder member")
    residual_tickets = sum(count for _, count in sparse)
    if certificate.residual_event_count != hunter.RESIDUAL_EVENT_COUNT or (
        residual_tickets != hunter.RESIDUAL_EVENT_COUNT
    ):
        raise AssertionError("the member has exactly 18 residual events")
    if certificate.maximum_pair_overlap != hunter.family_pair_overlap_ceiling():
        raise AssertionError("R3 portfolios have pair overlaps 0..3 only")
    events = hunter.event_decomposition(sparse)
    if certificate.raw_union_bound != events.raw_union_bound:
        raise AssertionError("raw union bound differs from the exact event decomposition")
    rows = member_rows(sparse)
    if certificate.pair_rows_sha256 != sibling.rows_digest(rows):
        raise AssertionError("pair rows digest differs")
    hunter.require_safe_pair_floors(certificate.global_pair_floors, rows)
    if certificate.global_pair_floors != sibling.global_pair_floors(rows):
        raise AssertionError("global pair floors differ from the exact row minima")
    for floors, name in zip(certificate.class_pair_floors, sibling.CLASS_NAMES, strict=True):
        hunter.require_safe_pair_floors(floors, sibling.class_rows(rows, name))
    if certificate.class_pair_floors != sibling.class_pair_floors(rows):
        raise AssertionError("class pair floors differ from the exact class row minima")
    if certificate.class_edge_counts != sibling.class_edge_counts(sparse):
        raise AssertionError("class edge counts differ from the member type counts")
    if certificate.cell_incidences != sibling.member_cell_incidences(sparse):
        raise AssertionError("cell incidences differ from the member type counts")
    floors = hunter.cell_collision_floors(certificate.cell_incidences)
    if certificate.cell_collision_floors != floors or certificate.collision_floor != sum(floors):
        raise AssertionError("collision floor differs from the balanced per-cell minimum")
    if certificate.class_mass_floors != class_mass_floors(sparse):
        raise AssertionError("class-specific forced masses differ from the member tickets")
    sibling.tree_rank_regressions(certificate.class_pair_floors)
    classes = sibling.member_edge_classes(
        certificate.class_edge_counts, certificate.class_pair_floors
    )
    split = sibling.minimum_class_tree_correction(classes, certificate.collision_floor)
    if (
        certificate.class_hunter_correction != split.correction
        or certificate.class_minimizer_counts != split.edge_counts
    ):
        raise AssertionError("class Hunter correction differs from the finite census minimum")
    if sum(map(sum, certificate.class_minimizer_counts)) != certificate.collision_floor:
        raise AssertionError("the minimizer does not carry the forced collision mass")
    require_class_masses(
        certificate.class_minimizer_counts,
        certificate.class_mass_floors,
        certificate.collision_floor,
    )
    if certificate.class_hunter_correction != sibling.class_tree_weight_floor(
        classes, certificate.class_minimizer_counts
    ):
        raise AssertionError("class Hunter correction is not the tree weight floor")
    homogeneous = hunter.minimum_tree_correction(
        certificate.global_pair_floors, certificate.collision_floor
    )
    if certificate.homogeneous_hunter_correction != homogeneous.correction:
        raise AssertionError("homogeneous Hunter correction differs from its census")
    if certificate.class_hunter_correction < certificate.homogeneous_hunter_correction:
        raise AssertionError("class floors dominate global floors, so must their minimum")
    expected = sibling.correction_terms(
        events,
        rational_correction(sparse),
        certificate.homogeneous_hunter_correction,
        certificate.class_hunter_correction,
    )
    if (
        certificate.pair_sum_correction,
        certificate.forest_correction,
        certificate.rational_correction,
    ) != (expected["R6_PAIR_SUM"], expected["R5_FOREST"], expected["R14_RATIONAL"]):
        raise AssertionError("existing corrections differ from their committed sources")
    if certificate.certified_correction != hunter.combine_corrections(expected):
        raise AssertionError("corrections must be combined by max, never summed")
    if certificate.certified_member_bound != (
        certificate.raw_union_bound - certificate.certified_correction
    ):
        raise AssertionError("certified bound must subtract the combined correction once")


def certified_member_bound(state_id: str, counts: Sequence[int]) -> int:
    """Return a member bound only for the exact source state and a member certified here."""

    matches = [
        sparse for sparse in CERTIFIED_MEMBERS if hunter.dense_counts(sparse) == tuple(counts)
    ]
    if state_id != STATE_ID or len(matches) != 1:
        raise hunter.CertificateScopeError(
            f"the ladder certificates cover only {STATE_ID} members "
            + ", ".join(member_id(sparse) for sparse in CERTIFIED_MEMBERS)
        )
    certificate = build_member_certificate(matches[0])
    verify_member_certificate(certificate)
    return certificate.certified_member_bound


# ---------------------------------------------------------------- phase 4: committed members


def carried_record_from(stored: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the committed [0,13][5,4][16,1] record against the pinned member."""

    counts = hunter.dense_counts(
        (int(index), int(count)) for index, count in stored["MEMBER_COUNTS"]
    )
    corrections = cast(dict[str, Any], stored["CORRECTIONS"])
    events = cast(dict[str, Any], stored["EVENT_DEFINITION"])
    bound = int(stored["CERTIFIED_MEMBER_BOUND"])
    correction = int(corrections["CERTIFIED_CORRECTION"])
    if (
        stored["STATE_ID"] != STATE_ID
        or stored["REGION_SHA256"] != REGION_SHA256
        or stored["MEMBER_ID"] != member_id(CARRIED_MEMBER)
        or counts != hunter.dense_counts(CARRIED_MEMBER)
        or stored["BASE_HEAD"] != FIRST_MEMBER_COMMIT
        or corrections["COMBINATION"] != "MAX_OF_VALID_LOWER_BOUNDS_NEVER_SUM"
        or stored["R3_BOUND_CLAIM"] != "NONE"
    ):
        raise AssertionError("the committed sibling result is not the pinned second member")
    if bound != int(events["RAW_UNION_BOUND_NO_CORRECTION"]) - correction:
        raise AssertionError("the committed sibling bound does not subtract its correction once")
    return {
        "MEMBER_ID": stored["MEMBER_ID"],
        "CERTIFIED_MEMBER_BOUND": bound,
        "CERTIFIED_CORRECTION": correction,
        "HUNTER_CLASS_SPLIT": int(corrections["HUNTER_CLASS_SPLIT"]),
        "COMMIT": CARRIED_MEMBER_COMMIT,
        "RESULT_SHA256": UPSTREAM_SHA256[sibling.RESULT_RELATIVE],
        "ROUTE": "HUNTER_CLASS_SPLIT",
        "RECOMPUTED": False,
    }


@cache
def carried_member_record() -> dict[str, Any]:
    """The committed [0,13][5,4][16,1] certificate, read by source identity only."""

    verify_upstream_fingerprints()
    return carried_record_from(
        cast(
            dict[str, Any],
            json.loads((REPO_ROOT / sibling.RESULT_RELATIVE).read_text(encoding="utf-8")),
        )
    )


@cache
def first_member_class_split() -> dict[str, Any]:
    """Re-evaluate [0,13][5,5] under the class split; the committed bound is not redone."""

    committed = sibling.prior_member_record()
    certificate = build_member_certificate(FIRST_MEMBER)
    verify_member_certificate(certificate)
    committed_bound = int(committed["CERTIFIED_MEMBER_BOUND"])
    committed_correction = int(committed["HUNTER_CORRECTION"])
    if committed["MEMBER_ID"] != member_id(FIRST_MEMBER):
        raise AssertionError("the committed first certificate names a different member")
    if certificate.homogeneous_hunter_correction != committed_correction or (
        certificate.raw_union_bound - committed_correction != committed_bound
    ):
        raise AssertionError("the homogeneous replay differs from the committed first certificate")
    improvement = committed_bound - certificate.certified_member_bound
    if improvement < 0:
        raise AssertionError("a max-combined certificate cannot exceed a committed component")
    return {
        "MEMBER_ID": member_id(FIRST_MEMBER),
        "STATUS": "VALID_STRICT_IMPROVEMENT" if improvement > 0 else "NO_STRICT_IMPROVEMENT",
        "COMMITTED_COMMIT": FIRST_MEMBER_COMMIT,
        "COMMITTED_RESULT_SHA256": committed["RESULT_SHA256"],
        "COMMITTED_HOMOGENEOUS_CORRECTION": committed_correction,
        "COMMITTED_BOUND": committed_bound,
        "HOMOGENEOUS_REPLAY_EQUALS_COMMITTED": True,
        "CLASS_SPLIT_CORRECTION": certificate.class_hunter_correction,
        "CLASS_SPLIT_BOUND": certificate.certified_member_bound,
        "IMPROVEMENT": improvement,
    }


@cache
def ladder_bounds() -> dict[Sparse, int]:
    """Certified bound of every ladder member: five certified here, one carried."""

    bounds: dict[Sparse, int] = {}
    for sparse in CERTIFIED_MEMBERS:
        certificate = build_member_certificate(sparse)
        verify_member_certificate(certificate)
        bounds[sparse] = certificate.certified_member_bound
    bounds[CARRIED_MEMBER] = int(carried_member_record()["CERTIFIED_MEMBER_BOUND"])
    return {sparse: bounds[sparse] for sparse in LADDER}


# ---------------------------------------------------------------- phase 5: region maximum


@dataclass(frozen=True)
class RegionMember:
    sparse: Sparse
    represented_vector_count: int
    raw_bound: int
    final_bound: int


@dataclass(frozen=True)
class RegionLedger:
    """Immutable R24 view of the target region and the R3 terms around it."""

    state_term: int
    final_state_bound: int
    certified_member_count: int
    members: tuple[RegionMember, ...]
    r3_bound: int
    r3_formula: str
    unclassified_tail_bound: int
    max_classified_tail_vector_bound: int
    other_state_terms: tuple[tuple[str, int], ...]


def region_ledger_from(stored: Mapping[str, Any]) -> RegionLedger:
    """Validate the R24 record of the target region and the R3 terms around it."""

    regions = [
        region
        for region in cast(list[dict[str, Any]], stored["STATE_REGION_CERTIFICATES"])
        if region["owner_id"] == STATE_ID
    ]
    terms = cast(list[dict[str, Any]], stored["CURRENT_STATE_TERMS"])
    own_terms = [int(term["bound"]) for term in terms if term["stable_id"] == STATE_ID]
    if len(regions) != 1 or len(own_terms) != 1 or regions[0]["region_sha256"] != REGION_SHA256:
        raise AssertionError("the R24 ledger does not hold exactly one pinned target region")
    region = regions[0]
    members: list[RegionMember] = []
    for record in cast(list[dict[str, Any]], region["complete_region_members"]):
        sparse = tuple((int(index), int(count)) for index, count in record["witness_counts"])
        if list(sparse) != sorted(sparse) or any(count <= 0 for _, count in sparse):
            raise AssertionError("an R24 region member is not in canonical sparse form")
        members.append(
            RegionMember(
                sparse=sparse,
                represented_vector_count=int(record["represented_vector_count"]),
                raw_bound=int(record["raw_bound"]),
                final_bound=int(record["final_bound"]),
            )
        )
    if len({member.sparse for member in members}) != len(members):
        raise AssertionError("the R24 region repeats a member")
    if any(
        member.represented_vector_count < 1 or member.final_bound > member.raw_bound
        for member in members
    ):
        raise AssertionError("an R24 region member carries an invalid bound")
    final_state_bound = int(region["final_state_bound"])
    if not own_terms[0] == final_state_bound == max(member.final_bound for member in members):
        raise AssertionError("the R24 state term is not the maximum of its region members")
    return RegionLedger(
        state_term=own_terms[0],
        final_state_bound=final_state_bound,
        certified_member_count=int(region["certified_member_count"]),
        members=tuple(members),
        r3_bound=int(stored["R3_BOUND"]),
        r3_formula=str(stored["R3_FORMULA"]),
        unclassified_tail_bound=int(stored["UNCLASSIFIED_TAIL_BOUND"]),
        max_classified_tail_vector_bound=int(stored["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"]),
        other_state_terms=tuple(
            sorted(
                (str(term["stable_id"]), int(term["bound"]))
                for term in terms
                if term["stable_id"] != STATE_ID
            )
        ),
    )


@cache
def r24_region() -> RegionLedger:
    hunter.verify_upstream_fingerprints()
    return region_ledger_from(
        cast(
            dict[str, Any],
            json.loads((REPO_ROOT / hunter.R24_RESULT_RELATIVE).read_text(encoding="utf-8")),
        )
    )


@dataclass(frozen=True)
class RegionMaximum:
    start_state_bound: int
    refined_state_bound: int
    owners: tuple[RegionMember, ...]
    member_bounds: tuple[tuple[RegionMember, int], ...]
    covered_member_count: int
    covered_vector_count: int
    compressed_member_count: int
    compressed_vector_count: int
    max_compressed_bound: int


@cache
def region_maximum() -> RegionMaximum:
    """Max over every region member: certified ladder bounds, carried bounds elsewhere."""

    ledger = r24_region()
    certified = ladder_bounds()
    ladder_members = [
        member.sparse
        for member in ledger.members
        if is_ladder_counts(hunter.dense_counts(member.sparse))
    ]
    if sorted(ladder_members) != sorted(LADDER):
        raise AssertionError("the R24 region ladder differs from the six certified members")
    member_bounds: list[tuple[RegionMember, int]] = []
    for member in ledger.members:
        if member.sparse not in certified:
            member_bounds.append((member, member.final_bound))
            continue
        if member.represented_vector_count != 1:
            raise AssertionError("a single-vector certificate cannot cover a compressed member")
        events = hunter.event_decomposition(member.sparse)
        forest = max(events.r7_forest_floor, events.r7_pair_sum_penalty)
        if not member.final_bound == member.raw_bound == events.raw_union_bound - forest:
            raise AssertionError("the R24 ladder member is not its re-derived raw bound")
        if certified[member.sparse] > member.final_bound:
            raise AssertionError("a certificate may only lower a carried member bound")
        member_bounds.append((member, certified[member.sparse]))
    refined = max(bound for _, bound in member_bounds)
    if refined > ledger.state_term:
        raise AssertionError("the refined state term exceeds the R24 state term")
    compressed = [member for member in ledger.members if member.represented_vector_count > 1]
    covered_vectors = sum(member.represented_vector_count for member, _ in member_bounds)
    if len(member_bounds) != REGION_COMPRESSED_MEMBERS or covered_vectors != REGION_VECTORS:
        raise AssertionError("the region maximum does not cover every member and vector")
    return RegionMaximum(
        start_state_bound=ledger.state_term,
        refined_state_bound=refined,
        owners=tuple(
            sorted(
                (member for member, bound in member_bounds if bound == refined),
                key=lambda member: member.sparse,
            )
        ),
        member_bounds=tuple(member_bounds),
        covered_member_count=len(member_bounds),
        covered_vector_count=covered_vectors,
        compressed_member_count=len(compressed),
        compressed_vector_count=sum(member.represented_vector_count for member in compressed),
        max_compressed_bound=max(member.final_bound for member in compressed),
    )


def region_levels(limit: int = 4) -> list[dict[str, Any]]:
    """The highest distinct bounds of the refined region and their member counts."""

    maximum = region_maximum()
    levels = sorted({bound for _, bound in maximum.member_bounds}, reverse=True)[:limit]
    return [
        {
            "BOUND": level,
            "MEMBERS": sum(1 for _, bound in maximum.member_bounds if bound == level),
            "VECTORS": sum(
                member.represented_vector_count
                for member, bound in maximum.member_bounds
                if bound == level
            ),
        }
        for level in levels
    ]


# ---------------------------------------------------------------- phase 6: witnesses


@dataclass(frozen=True)
class LadderWitness:
    member_sparse: Sparse
    anchor_overlap: int
    maximum_pair_overlap: int
    residual_multiplicity: int
    anchor_hits_on_outcome_set: tuple[int, int]
    collision_mass: int
    label_collision_mass: int
    class_nested_counts: tuple[Nested, ...]
    census_objective: int
    floor_tree_weight: int
    exact_tree_weight: int
    exact_rows_match_table: bool


def witness_residual_tickets(sparse: Sparse) -> tuple[tuple[int, ...], ...]:
    tickets = list(hunter.CAP17_WITNESS_RESIDUAL_TICKETS)
    for replaced, inserted in WITNESS_REPLACEMENTS[: type16_count(sparse)]:
        tickets[tickets.index(replaced)] = inserted
    return tuple(tickets)


@cache
def witness_analysis(sparse: Sparse) -> LadderWitness:
    """Validate an explicit member portfolio and its exact residual pair structure."""

    certificate = build_member_certificate(sparse)
    residual = tuple(frozenset(ticket) for ticket in witness_residual_tickets(sparse))
    portfolio = (hunter.ANCHOR_A, hunter.ANCHOR_B, *residual)
    if len(portfolio) != 20 or len(set(portfolio)) != 20:
        raise AssertionError("witness must hold 20 distinct tickets")
    if any(
        len(ticket) != hunter.TICKET_SIZE
        or not all(1 <= label <= hunter.POOL_SIZE for label in ticket)
        for ticket in portfolio
    ):
        raise AssertionError("witness tickets must hold six labels from 1..49")
    overlaps_all = [len(left & right) for left, right in combinations(portfolio, 2)]
    anchor_overlap = len(hunter.ANCHOR_A & hunter.ANCHOR_B)
    if max(overlaps_all) != anchor_overlap or anchor_overlap != r5.ANCHOR_OVERLAP:
        raise AssertionError("witness is not an R3 portfolio anchored on a maximum pair")
    profiles = r5.anchor_incidence_profiles()
    index_by_cells = {
        (profile.shared, profile.a_only, profile.b_only, profile.outside): index
        for index, profile in enumerate(profiles)
    }
    types = [index_by_cells[hunter.ticket_cells(ticket)] for ticket in residual]
    observed = tuple(sorted((index, types.count(index)) for index in set(types)))
    if observed != sparse:
        raise AssertionError(f"witness types {observed} are not the member {member_id(sparse)}")
    outcome_set = hunter.CAP17_WITNESS_OUTCOME_SET
    anchor_hits = (len(hunter.ANCHOR_A & outcome_set), len(hunter.ANCHOR_B & outcome_set))
    if max(anchor_hits) >= hunter.WIN_HITS:
        raise AssertionError("the shared 7-set must lie outside both anchor events")
    multiplicity = sum(1 for ticket in residual if len(ticket & outcome_set) >= hunter.WIN_HITS)

    rows = member_rows(sparse)
    table = {(row.left_type, row.right_type, row.overlap): row for row in rows}
    floor_of = dict(zip(sibling.CLASS_NAMES, certificate.class_pair_floors, strict=True))
    pair_overlaps: dict[tuple[int, int], int] = {}
    pair_classes: dict[tuple[int, int], str] = {}
    floor_weights: dict[tuple[int, int], int] = {}
    exact_weights: dict[tuple[int, int], int] = {}
    rows_match = True
    for left, right in combinations(range(len(residual)), 2):
        overlap_cells = hunter.pair_cell_overlap(residual[left], residual[right])
        total = sum(overlap_cells)
        low, high = sorted((types[left], types[right]))
        name = sibling.edge_class(low, high)
        exact = hunter.outcome_count(
            (residual[left], residual[right]), (hunter.ANCHOR_A, hunter.ANCHOR_B)
        )
        pair_overlaps[(left, right)] = total
        pair_classes[(left, right)] = name
        floor_weights[(left, right)] = floor_of[name][total]
        exact_weights[(left, right)] = exact
        rows_match = rows_match and table[(low, high, overlap_cells)].residual_intersection == exact
    hunter.threshold_edge_counts(pair_overlaps.values())
    frequencies = [
        sum(1 for ticket in residual if label in ticket) for label in range(1, hunter.POOL_SIZE + 1)
    ]
    label_mass = sum(comb(value, 2) for value in frequencies)
    collision_mass = sum(pair_overlaps.values())
    if collision_mass != label_mass:
        raise AssertionError("witness collision identity failed")
    nested = tuple(
        cast(
            Nested,
            tuple(
                sum(
                    1
                    for edge, value in pair_overlaps.items()
                    if pair_classes[edge] == name and value >= level
                )
                for level in range(1, hunter.MAXIMUM_PAIR_OVERLAP + 1)
            ),
        )
        for name in sibling.CLASS_NAMES
    )
    classes = sibling.member_edge_classes(
        certificate.class_edge_counts, certificate.class_pair_floors
    )
    objective = sibling.class_tree_weight_floor(classes, nested)
    floor_tree = hunter.threshold_tree(len(residual), floor_weights)
    floor_weight = sum(floor_weights[edge] for edge in floor_tree)
    exact_tree = hunter.threshold_tree(len(residual), exact_weights)
    exact_weight = sum(exact_weights[edge] for edge in exact_tree)
    return LadderWitness(
        member_sparse=observed,
        anchor_overlap=anchor_overlap,
        maximum_pair_overlap=max(overlaps_all),
        residual_multiplicity=multiplicity,
        anchor_hits_on_outcome_set=anchor_hits,
        collision_mass=collision_mass,
        label_collision_mass=label_mass,
        class_nested_counts=nested,
        census_objective=objective,
        floor_tree_weight=floor_weight,
        exact_tree_weight=exact_weight,
        exact_rows_match_table=rows_match,
    )


def require_witness_consistency(sparse: Sparse) -> LadderWitness:
    """A legal member portfolio must satisfy every relaxation the certificate uses."""

    witness = witness_analysis(sparse)
    certificate = build_member_certificate(sparse)
    if not witness.exact_rows_match_table:
        raise AssertionError("witness pair intersections differ from the exact table rows")
    if witness.collision_mass < certificate.collision_floor:
        raise AssertionError("the witness violates the certified collision floor")
    if any(
        mass < floor
        for mass, floor in zip(
            class_masses(witness.class_nested_counts), certificate.class_mass_floors, strict=True
        )
    ):
        raise AssertionError("the witness violates a class-specific forced mass")
    if not (
        witness.exact_tree_weight
        >= witness.floor_tree_weight
        >= witness.census_objective
        >= certificate.class_hunter_correction
    ):
        raise AssertionError("the explicit member witness contradicts the certificate")
    return witness


# ---------------------------------------------------------------- result


def _sparse_text(sparse: Sequence[tuple[int, int]]) -> list[list[int]]:
    return [[index, count] for index, count in sparse]


def member_record(sparse: Sparse) -> dict[str, Any]:
    certificate = build_member_certificate(sparse)
    verify_member_certificate(certificate)
    rows = member_rows(sparse)
    events = hunter.event_decomposition(sparse)
    classes = sibling.member_edge_classes(
        certificate.class_edge_counts, certificate.class_pair_floors
    )
    split = sibling.minimum_class_tree_correction(classes, certificate.collision_floor)
    homogeneous = hunter.minimum_tree_correction(
        certificate.global_pair_floors, certificate.collision_floor
    )
    existing = {
        "R6_PAIR_SUM": certificate.pair_sum_correction,
        "R5_FOREST": certificate.forest_correction,
        "R14_RATIONAL": certificate.rational_correction,
    }
    corrections = {
        **existing,
        "HUNTER_HOMOGENEOUS": certificate.homogeneous_hunter_correction,
        "HUNTER_CLASS_SPLIT": certificate.class_hunter_correction,
    }
    raw_member_bound = certificate.raw_union_bound - max(
        certificate.forest_correction, certificate.pair_sum_correction
    )
    rational_bound = certificate.raw_union_bound - hunter.combine_corrections(existing)
    selected = sorted(
        name for name, value in corrections.items() if value == max(corrections.values())
    )
    witness = require_witness_consistency(sparse)
    return {
        "MEMBER_COUNTS": _sparse_text(sparse),
        "TYPE_CELLS": {
            str(index): list(cells)
            for index, cells in verify_ladder_identity().items()
            if index in dict(sparse)
        },
        "RESIDUAL_EVENT_SIZES": [list(row) for row in events.residual_event_sizes],
        "RAW_UNION_BOUND_NO_CORRECTION": certificate.raw_union_bound,
        "PAIR_TABLE": {
            "TYPE_PAIRS": [list(pair) for pair in sibling.occurring_type_pairs(sparse)],
            "TYPE_PAIR_EDGE_COUNTS": [
                [*pair, count] for pair, count in sibling.type_pair_edge_counts(sparse).items()
            ],
            "ROW_COUNT": len(rows),
            "ROWS": [
                [row.left_type, row.right_type, *row.overlap, row.residual_intersection]
                for row in rows
            ],
            "ROWS_SHA256": certificate.pair_rows_sha256,
            "GLOBAL_PAIR_FLOORS": list(certificate.global_pair_floors),
            "CLASS_EDGE_COUNTS": dict(
                zip(sibling.CLASS_NAMES, certificate.class_edge_counts, strict=True)
            ),
            "CLASS_PAIR_FLOORS": {
                name: list(floors)
                for name, floors in zip(
                    sibling.CLASS_NAMES, certificate.class_pair_floors, strict=True
                )
            },
            "FLOOR_SETTING_TYPE_PAIRS": sibling.floor_setting_type_pairs(rows),
        },
        "COLLISION_FLOOR": {
            "CELL_INCIDENCES": list(certificate.cell_incidences),
            "CELL_FLOORS": list(certificate.cell_collision_floors),
            "TOTAL": certificate.collision_floor,
            "CLASS_MASS_FLOORS": dict(
                zip(sibling.CLASS_NAMES, certificate.class_mass_floors, strict=True)
            ),
            "MINIMIZER_CLASS_MASSES": dict(
                zip(
                    sibling.CLASS_NAMES,
                    class_masses(certificate.class_minimizer_counts),
                    strict=True,
                )
            ),
            "CLASS_MASS_FLOORS_BINDING": False,
        },
        "TREE_MINIMUM": {
            "CENSUS_SIZE": split.census_size,
            "MINIMIZER_COUNTS": {
                name: list(counts)
                for name, counts in zip(sibling.CLASS_NAMES, split.edge_counts, strict=True)
            },
            "LEVELS": sibling.level_table(classes, split.edge_counts),
            "HOMOGENEOUS_CENSUS_SIZE": homogeneous.census_size,
            "HOMOGENEOUS_MINIMIZER_E": list(homogeneous.edge_counts),
        },
        "CORRECTIONS": {
            **corrections,
            "COMBINATION": "MAX_OF_VALID_LOWER_BOUNDS_NEVER_SUM",
            "SELECTED": selected,
            "CERTIFIED_CORRECTION": certificate.certified_correction,
        },
        "R24_LEDGER_BOUND": raw_member_bound,
        "RATIONAL_BOUND": rational_bound,
        "CERTIFIED_MEMBER_BOUND": certificate.certified_member_bound,
        "REDUCTION_VS_RATIONAL": rational_bound - certificate.certified_member_bound,
        "REDUCTION_FROM_R24_LEDGER": raw_member_bound - certificate.certified_member_bound,
        "WITNESS": {
            "RESIDUAL_TICKETS": [list(ticket) for ticket in witness_residual_tickets(sparse)],
            "TYPE16_REPLACEMENTS": [
                [list(replaced), list(inserted)]
                for replaced, inserted in WITNESS_REPLACEMENTS[: type16_count(sparse)]
            ],
            "MAXIMUM_PAIR_OVERLAP": witness.maximum_pair_overlap,
            "RESIDUAL_MULTIPLICITY_ON_OUTCOME_SET": witness.residual_multiplicity,
            "COLLISION_MASS": witness.collision_mass,
            "CLASS_MASSES": dict(
                zip(sibling.CLASS_NAMES, class_masses(witness.class_nested_counts), strict=True)
            ),
            "CENSUS_OBJECTIVE": witness.census_objective,
            "PHI_TREE_WEIGHT": witness.floor_tree_weight,
            "EXACT_MAXIMUM_TREE_WEIGHT": witness.exact_tree_weight,
            "EXACT_PAIRS_EQUAL_TABLE_ROWS": witness.exact_rows_match_table,
        },
    }


@cache
def build_result() -> dict[str, Any]:
    verify_upstream_fingerprints()
    verify_ladder_identity()
    ledger = r24_region()
    first = first_member_class_split()
    carried = carried_member_record()
    bounds = ladder_bounds()
    maximum = region_maximum()
    records = {member_id(sparse): member_record(sparse) for sparse in CERTIFIED_MEMBERS}
    regressions = {
        member_id(sparse): sibling.tree_rank_regressions(
            build_member_certificate(sparse).class_pair_floors
        )
        for sparse in CERTIFIED_MEMBERS
    }
    hunter_small = hunter.verify_hunter_exhaustively(4, 3) + hunter.verify_hunter_exhaustively(3, 4)
    try:
        hunter.require_multiplicity_cap(17)
    except hunter.MultiplicityCapRefuted:
        cap17_refuted = True
    else:
        cap17_refuted = False
    if not cap17_refuted or hunter.cap17_witness_analysis().residual_multiplicity != 18:
        raise AssertionError("the committed 18-winner counterexample was not preserved")
    next_raw_level = max(
        member.final_bound
        for member in ledger.members
        if not is_ladder_counts(hunter.dense_counts(member.sparse))
    )
    r3_with_refined_term = max(
        maximum.refined_state_bound,
        *(bound for _, bound in ledger.other_state_terms),
        ledger.unclassified_tail_bound,
        ledger.max_classified_tail_vector_bound,
    )
    derived = {
        "FIRST_MEMBER_HOMOGENEOUS_BOUND": first["COMMITTED_BOUND"],
        "SECOND_MEMBER_CLASS_SPLIT_BOUND": carried["CERTIFIED_MEMBER_BOUND"],
        "SECOND_MEMBER_CLASS_SPLIT_CORRECTION": carried["CERTIFIED_CORRECTION"],
        "R3_DURABLE_BOUND": ledger.r3_bound,
        "NEXT_RAW_REGION_LEVEL": next_raw_level,
        "REGION_COMPRESSED_MEMBERS": len(ledger.members),
        "REGION_VECTORS": sum(member.represented_vector_count for member in ledger.members),
    }
    if derived != PACKET_REFERENCE:
        raise AssertionError(f"re-derived values differ from the packet: {derived}")
    if r3_with_refined_term != ledger.r3_bound:
        raise AssertionError("the refined state term would move the R3 bound")
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "CERTIFIED_LADDER_CLASS_SPLIT_AND_REFINED_STATE_TERM",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_BRANCH": TASK_BRANCH,
        "SOURCE_FINGERPRINT": {
            "MODULE": MODULE_RELATIVE,
            "MODULE_SHA256": file_sha256(MODULE_RELATIVE),
        },
        "UPSTREAM_SHA256": {
            **hunter.UPSTREAM_SHA256,
            **sibling.UPSTREAM_SHA256,
            **verify_upstream_fingerprints(),
        },
        "STATE_ID": STATE_ID,
        "REGION_SHA256": REGION_SHA256,
        "LADDER_MEMBER_COUNT": len(LADDER),
        "LADDER": [member_id(sparse) for sparse in LADDER],
        "MEMBERS_ALREADY_CERTIFIED": [
            {
                "MEMBER_ID": first["MEMBER_ID"],
                "COMMIT": FIRST_MEMBER_COMMIT,
                "ROUTE": "HUNTER_HOMOGENEOUS",
                "CERTIFIED_MEMBER_BOUND": first["COMMITTED_BOUND"],
                "CERTIFIED_CORRECTION": first["COMMITTED_HOMOGENEOUS_CORRECTION"],
                "RESULT_SHA256": first["COMMITTED_RESULT_SHA256"],
                "RECOMPUTED": False,
            },
            {
                "MEMBER_ID": carried["MEMBER_ID"],
                "COMMIT": carried["COMMIT"],
                "ROUTE": carried["ROUTE"],
                "CERTIFIED_MEMBER_BOUND": carried["CERTIFIED_MEMBER_BOUND"],
                "CERTIFIED_CORRECTION": carried["CERTIFIED_CORRECTION"],
                "RESULT_SHA256": carried["RESULT_SHA256"],
                "RECOMPUTED": False,
            },
        ],
        "FIRST_MEMBER_CLASS_SPLIT_RESULT": first,
        "NEW_MEMBER_CERTIFICATES": [member_id(sparse) for sparse in NEW_MEMBERS],
        "MEMBER_CERTIFICATES": records,
        "PAIR_TABLE_STATUS": "VERIFIED_"
        + "_".join(str(len(member_rows(sparse))) for sparse in CERTIFIED_MEMBERS)
        + "_ROWS_INDEPENDENT_REPLAY_EQUALS_R8",
        "PAIR_OVERLAP_LIMITS": {
            "FAMILY_SOURCE_CEILING": hunter.family_pair_overlap_ceiling(),
            "CELL_RANGES": "max(0,c+d-capacity) <= x <= min(c,d) in each of 3,3,3,40 labels",
            "R6_OVERLAP_VECTORS_EQUAL": True,
        },
        "COLLISION_FLOOR_STATUS": "VERIFIED_"
        + "_".join(
            str(build_member_certificate(sparse).collision_floor) for sparse in CERTIFIED_MEMBERS
        )
        + "_CLASS_MASS_FLOORS_NON_BINDING",
        "TREE_RANK_STATUS": "PROVED_CLASS_THRESHOLD_TREE_WITH_EXHAUSTIVE_REGRESSION",
        "TREE_RANK_PROOF": {
            "SOURCE": "committed class threshold-tree lemma of " + sibling.MODULE_RELATIVE,
            "REGRESSIONS_BY_MEMBER": regressions,
            "HUNTER_EXHAUSTIVE_SMALL_FAMILY_TREE_CHECKS": hunter_small,
        },
        "FINITE_MINIMISATION_STATUS": "EXACT_CENSUS_REPRODUCED",
        "CERTIFIED_MEMBER_BOUNDS": {
            member_id(sparse): {
                "BOUND": bounds[sparse],
                "SOURCE": "CARRIED_COMMITTED" if sparse == CARRIED_MEMBER else "CERTIFIED_HERE",
            }
            for sparse in LADDER
        },
        "REGION": {
            "COMPRESSED_MEMBERS": maximum.covered_member_count,
            "VECTORS": maximum.covered_vector_count,
            "R24_CERTIFIED_MEMBER_COUNT": ledger.certified_member_count,
            "COMPRESSED_MEMBERS_WITH_MULTIPLE_VECTORS": maximum.compressed_member_count,
            "VECTORS_IN_COMPRESSED_MEMBERS": maximum.compressed_vector_count,
            "MAX_COMPRESSED_MEMBER_BOUND": maximum.max_compressed_bound,
            "COMPRESSED_TREATMENT": (
                "carried at the R24 final bound; the ladder certificates cover only "
                "single-vector members and refuse a compressed one"
            ),
            "LADDER_RULE": "certified bound <= carried R24 final bound for every ladder member",
            "NON_LADDER_RULE": "carried R24 final bound, unchanged",
            "TOP_LEVELS_AFTER_REFINEMENT": region_levels(),
            "NEXT_RAW_REGION_LEVEL": next_raw_level,
        },
        "START_STATE_BOUND": maximum.start_state_bound,
        "REFINED_STATE_BOUND": maximum.refined_state_bound,
        "STATE_TERM_DROP": maximum.start_state_bound - maximum.refined_state_bound,
        "NEXT_LOAD_BEARING_MEMBER": [
            {
                "MEMBER_ID": member_id(member.sparse),
                "REPRESENTED_VECTOR_COUNT": member.represented_vector_count,
                "BOUND": maximum.refined_state_bound,
                "CARRIED_R24_FINAL_BOUND": member.final_bound,
                "RAW": member.final_bound == member.raw_bound,
            }
            for member in maximum.owners
        ],
        "R3_DURABLE_BOUND": ledger.r3_bound,
        "R3_FORMULA": ledger.r3_formula,
        "R3_WITH_REFINED_STATE_TERM": r3_with_refined_term,
        "R3_GLOBAL_BOUND_UNCHANGED": True,
        "R3_BOUND_CLAIM": "NONE",
        "STATE_TERM_CLAIM": f"{STATE_ID} only, over all {REGION_COMPRESSED_MEMBERS} members",
        "CAP17_COUNTEREXAMPLE_STATUS": "PRESERVED_NU_18_CAP17_REFUTED",
        "NU_LE_17": "\u03bd <= 17 REFUTED",
        "WITNESS_SOUNDNESS_STATUS": "CONSISTENT",
        "WITNESS_OUTCOME_SET": sorted(hunter.CAP17_WITNESS_OUTCOME_SET),
        "WITNESS_MEANING": (
            "On a legal member portfolio: certificate <= census objective <= phi-tree "
            "weight <= exact maximum tree weight <= true union correction"
        ),
        "NEW_HEAVY_SOLVER_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "WORKTREE_DISPOSITION": "RETAIN",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write the committed result JSON")
    arguments = parser.parse_args(argv)
    text = hunter.encode(build_result())
    if arguments.write:
        RESULT_PATH.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
