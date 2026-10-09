"""Neighbourhood-capacity (NB) triangle cap and the W=809 frontier class (NB frontier R1).

Authority is the R32 result committed at 65f4e9e5, pinned by SHA-256. R32's own
zero-solve replay rebuilds the 1,795-row resolved ledger through R31 and R30,
re-derives every R32 Route-B certificate and asserts the sealed ledger digest.
Its family maximum 313,566,616 is owned by 74 resolved profiles, and the
unresolved ranked cursor 66666653222222222211 (W 809) sits at the coarse
313,556,760. R33 is not an input; this branch does not incorporate it.

Structural premises. A min-S2 portfolio has 20 tickets of six labels, pair
overlaps of at most one, and each of the 49 labels on two or three tickets, so
22 labels are triple supports and 27 are pair labels. The overlap graph joins
two tickets that share a label and is simple. A ticket meets every other ticket
in at most one label, so its neighbours through distinct labels are distinct:
a ticket of triple degree d has graph degree g = 6 + d. The graph has
3*22 + 27 = 93 edges and W = sum C(g, 2) = (1326 + sum d^2) / 2 wedges, so the
W=809 class is exactly the sum d^2 = 292 class.

NB lemma. Let u be a neighbour of v. N(u) and N(v) share neither v (v is in
N(u), not in N(v)) nor u, so u has at most min(g_u - 1, g_v - 1) neighbours in
N(v), and 2 e(N(v)) <= sum over u in N(v) of min(g_u - 1, g_v - 1). The summand
does not decrease with g_u, so the sum over any g_v vertices other than v is at
most M_v, the same sum over the g_v largest other degrees; equal degrees give
the same value in any order. Hence e(N(v)) <= floor(M_v / 2) <= C(g_v, 2). Each
closed wedge at v is an edge of N(v), so with
OW_NB = sum_v [C(g_v, 2) - floor(M_v / 2)],

    OW >= OW_NB    and    T = (W - OW) / 3 <= floor((W - OW_NB) / 3).

The bound uses only the degree multiset, so it holds for every simple graph
with those degrees, hence for every realization of the profile. A degree list
that no simple graph has is rejected instead of capped.

Caps and Route B. Three caps are valid, and the least is used. The first is the
NB cap. The second is R18's induced-P3 class cap: OW >= 5 for every profile,
rounded up to W mod 3. The third is the profile's catalog cap, accepted only
when it is re-verified against one of: the sealed R30 INFEASIBLE refutation at
cap + 1, the R18 closed form, or the pinned R25 R13 OPTIMAL relaxation row.
R32's Route B closed form is evaluated at every t in 22..cap with exact integer
floors and ceilings, and the profile bound is the maximum over t. A previous
certificate at least as strong is kept unchanged.

Phase 2 regresses the cursor. Phase 3 refines all 1,795 resolved profiles. It
then freezes the exact W=809 frontier class with R30's ranked plateau lookup,
cross-checks the membership against an independent enumeration, and certifies
each member separately. The cursor moves to the first W <= 808 profile, whose
coarse envelope bounds every remaining unresolved profile. No solver, census,
portfolio search or outcome enumeration is run.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, replace
from itertools import combinations, pairwise
from math import comb
from time import monotonic

from . import b649_k20_min_s2_route_b_current_owner_refinement_r32 as r32
from .b649_k20_min_s2_class_dominance_or_descent_r13 import (
    graph_triangle_upper_bound_from_open_wedges,
)
from .b649_k20_min_s2_cursor_plateau_closure_r18 import generic_open_wedge_floor
from .b649_k20_min_s2_dangerous_core_realizability_r5 import (
    residual_double_ticket_degrees,
    simple_graph_degree_sequence_is_graphical,
)
from .b649_k20_min_s2_load_bearing_plateau_descent_r16 import PlateauFrontier
from .b649_k20_min_s2_next_active_profile_exact_bound_r8 import (
    INHERITED_FOURTH_ORDER_CREDIT,
    coarse_profile_envelope,
    erdos_gallai_first_violation,
    profile_shadow_obstruction,
)
from .b649_k20_min_s2_realizable_core_class_bound_r4 import (
    K20_DOUBLE_SUPPORT_COUNT,
    K20_LABEL_COUNT,
    K20_S1,
    K20_S2,
    K20_TICKET_CAPACITY,
    K20_TICKET_COUNT,
    K20_TRIPLE_INCIDENCE_COUNT,
    K20_TRIPLE_SUPPORT_COUNT,
    linear_triple_degree_sequence_passes_pair_capacity,
    overlap_wedge_count,
)
from .b649_k20_min_s2_resolved_above_cursor_owner_chase_r20 import (
    Certificate,
    decode_profile,
    profile_id,
)

r28 = r32.r28
r29 = r32.r29
r30 = r32.r30
r31 = r32.r31
DegreeProfile = r32.DegreeProfile
Chase = r32.Chase
Term = r32.Term
Proofs = r32.Proofs
Refutations = dict[DegreeProfile, dict[int, int]]
Row = dict[str, object]

TASK_ID = "B649_K20_MIN_S2_NB_DEGREE_CAP_FRONTIER_R1"
TASK_BRANCH = "codex/b649-k20-min-s2-nb-degree-cap-frontier-r1"
WORKTREE_PATH = "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/" + TASK_ID
BASE_HEAD = "65f4e9e50d74db9a11e71b8bdef30b25e87bf15b"
BASE_TREE = "3876916d2185c9566642e4af8c7e9d576077d1cc"
R32_RESULT = r32.RESULT_FILENAME
R32_SHA256 = "f196262ea032eaccd1cc9e1f7bbc408023900d87fcdf33ad1d576de878057cd5"
R32_LEDGER_SHA256 = "bfe73326f5bb430446789288909480295cefee2044052e97fdfe3dad0b2d3f14"
R31_SHA256 = r32.R31_SHA256
R30_SHA256 = r32.R30_SHA256
R30_RESULT = r30.RESULT_FILENAME
R25_RESULT = r28.batch.R25_FILENAME
R25_SHA256 = r28.batch.R25_SHA256
LEDGER_COUNT = 1_795
START_BOUND = 313_566_616
START_OWNER_COUNT = 74
START_NEXT_BOUND = 313_566_504
CURSOR = r32.CURSOR
CURSOR_BOUND = r32.CURSOR_BOUND
CURSOR_WEDGES = 809
CURSOR_SQUARE_SUM = 292
INCUMBENT = r32.INCUMBENT
WITNESS_PROFILE = r32.WITNESS_PROFILE
WITNESS_UNION = r32.WITNESS_UNION
WITNESS_TRIANGLES = r32.WITNESS_TRIANGLES
EDGE_COUNT = 3 * K20_TRIPLE_SUPPORT_COUNT + K20_DOUBLE_SUPPORT_COUNT
WEDGE_OFFSET = sum(
    (K20_TICKET_CAPACITY + d) * (K20_TICKET_CAPACITY - 1 + d) - d * d for d in (0,)
) * K20_TICKET_COUNT + (2 * K20_TICKET_CAPACITY - 1) * K20_TRIPLE_INCIDENCE_COUNT
CURSOR_TARGETS: dict[str, int] = {
    "WEDGE_COUNT": 809,
    "SUM_GRAPH_DEGREE_CHOOSE_3": 2_199,
    "A_MAX": 185,
    "MAX_GRAPH_DEGREE": 12,
    "NB_OPEN_WEDGE_FLOOR": 80,
    "NB_TRIANGLE_CAP": 243,
    "K4_FLOOR_AT_CAP": 350,
    "S4_FLOOR_AT_CAP": 194_915,
    "ALL_T_MAX_BOUND": 313_136_772,
}
TARGET_W809_COUNT = 133
TARGET_W809_CLASS_MAX = 313_343_868
TARGET_RESOLVED_MAX = 313_494_896
TARGET_FRONTIER_BOUND = 313_553_960
TARGET_FAMILY_BOUND = 313_553_960
SMALL_GRAPH_VERTICES = 6
COVERAGE_SQUARE_SUMS = (294, 342)
CAP_NB = "NB_NEIGHBOURHOOD_CAPACITY"
CAP_R18 = "R18_INDUCED_P3_CLASS_CLOSED_FORM"
CAP_CATALOG = "VERIFIED_CATALOG_CERTIFICATE_CAP"
VERIFY_REFUTATION = "SEALED_R30_INFEASIBLE_REFUTATION_AT_CAP_PLUS_ONE"
VERIFY_R18 = "R18_CLOSED_FORM_AT_OR_BELOW_CATALOG_CAP"
VERIFY_R25 = "PINNED_R25_R13_OPTIMAL_RELAXATION_ROW"
VERIFIED = "VERIFIED"
UNVERIFIED = "UNVERIFIED_NOT_USED"
ROUTE_NB = "NB_DEGREE_CAP_ROUTE_B_ALL_T"
ADOPTED = "NB_ROUTE_B_ADOPTED"
RETAINED = "PREVIOUS_CERTIFICATE_RETAINED"
FRONTIER_CERTIFIED = "FRONTIER_NB_ROUTE_B_CERTIFIED"
FRONTIER_RESIDUAL = "FRONTIER_RESIDUAL_COARSE_ENVELOPE_KEPT"
REPLAY_SECONDS = 600.0
RESULT_DIRECTORY = r32.RESULT_DIRECTORY
RESULT_FILENAME = "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json"
SUCCESS_A = "SUCCESS_A_CERTIFIED_FAMILY_UPPER_BOUND_REDUCTION"
SUCCESS_B = "SUCCESS_B_NO_FAMILY_DROP"
BOUND_RULE = (
    "MAX_OVER_T_IN_22..MIN(NB,R18,VERIFIED_CATALOG)_CAP_OF_"
    "S1-S2+S3(T)-FLOOR(4*MAX(GLOBAL,679*K4(T)-231*MIN(K4(T),A_MAX))/7)"
)

object_row = r28.object_row
rows = r28.rows
integer = r28.integer


def r32_authority() -> tuple[dict[str, object], str]:
    """The R32 result at the base: exact tree, pinned digest, sealed facts."""

    if r31.git("rev-parse", f"{BASE_HEAD}^{{tree}}").decode().strip() != BASE_TREE:
        raise AssertionError("the base tree changed")
    blob = r31.git("show", f"{BASE_HEAD}:{RESULT_DIRECTORY}/{R32_RESULT}")
    digest = hashlib.sha256(blob).hexdigest()
    if digest != R32_SHA256:
        raise AssertionError("sealed R32 fingerprint changed")
    result = object_row(json.loads(blob))
    expected: dict[str, object] = {
        "TASK_ID": r32.TASK_ID,
        "TASK_STATUS": r32.SUCCESS_A,
        "FAMILY_UPPER_BOUND": START_BOUND,
        "NEXT_COMPETING_BOUND": START_NEXT_BOUND,
        "NEXT_ACTIVE_PROFILE": profile_id(CURSOR),
        "NEXT_ACTIVE_BOUND": CURSOR_BOUND,
        "RESOLVED_LEDGER_COUNT": LEDGER_COUNT,
        "FINAL_COMPLETE_LEDGER_SHA256": R32_LEDGER_SHA256,
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": START_BOUND - INCUMBENT,
    }
    for key, value in expected.items():
        if result.get(key) != value:
            raise AssertionError(f"R32 authority mismatch: {key}")
    fingerprint = object_row(result["AUTHORITY_FINGERPRINT"])
    for key, value in (("R31_RESULT_SHA256", R31_SHA256), ("R30_RESULT_SHA256", R30_SHA256)):
        if fingerprint.get(key) != value:
            raise AssertionError(f"R32 authority mismatch: {key}")
    if len(rows(result["FINAL_BOUND_OWNER_IDS"])) != START_OWNER_COUNT:
        raise AssertionError("R32 authority mismatch: FINAL_BOUND_OWNER_IDS")
    return result, digest


def start_chase(deadline: float) -> tuple[Chase, str, dict[str, object]]:
    """R32's zero-solve replay of its sealed result; assert owners, cursor and ledger."""

    result, digest = r32_authority()
    chase = r32.replay_result(result, deadline)
    family, owners = r28.family_state(chase)
    if (
        family != START_BOUND
        or list(map(profile_id, owners)) != result["FINAL_BOUND_OWNER_IDS"]
        or (chase.cursor, chase.cursor_bound) != (CURSOR, CURSOR_BOUND)
        or len(chase.bounds) != LEDGER_COUNT
        or r29.ledger_digest(chase) != R32_LEDGER_SHA256
        or r28.competing_bound(chase, owners) != START_NEXT_BOUND
    ):
        raise AssertionError("R32 owner, cursor or complete-ledger reconstruction failed")
    for log in (chase.attempts, chase.steps, chase.plateaus, chase.sequence, chase.nonvacuity):
        log.clear()
    chase.dispatched.clear()
    chase.failed.clear()
    chase.checked.clear()
    r30.record_owner(chase)
    return chase, digest, result


def structural_premises() -> dict[str, object]:
    """Counting identities behind g = 6 + d and W = (1326 + sum d^2) / 2."""

    incidences = K20_TICKET_COUNT * K20_TICKET_CAPACITY
    doubles = 3 * K20_LABEL_COUNT - incidences
    triples = K20_LABEL_COUNT - doubles
    if (
        (doubles, triples) != (K20_DOUBLE_SUPPORT_COUNT, K20_TRIPLE_SUPPORT_COUNT)
        or 2 * doubles + 3 * triples != incidences
        or incidences + K20_TRIPLE_INCIDENCE_COUNT != 2 * EDGE_COUNT
        or WEDGE_OFFSET != 1_326
    ):
        raise AssertionError("min-S2 counting premises changed")
    return {
        "TICKETS": K20_TICKET_COUNT,
        "TICKET_SIZE": K20_TICKET_CAPACITY,
        "LABELS": K20_LABEL_COUNT,
        "TRIPLE_SUPPORTS": triples,
        "PAIR_LABELS": doubles,
        "MAX_PAIR_OVERLAP": 1,
        "OVERLAP_GRAPH": "SIMPLE_TICKETS_ADJACENT_IFF_ONE_SHARED_LABEL",
        "GRAPH_DEGREE": "6_PLUS_TRIPLE_DEGREE_DISTINCT_LABELS_GIVE_DISTINCT_NEIGHBOURS",
        "EDGES": EDGE_COUNT,
        "WEDGE_IDENTITY": "2W = 1326 + SUM_D_SQUARED",
        "TRIANGLE_IDENTITY": "W = OW + 3T",
    }


def graph_degree_list(degrees: Sequence[int]) -> tuple[int, ...]:
    """A validated simple-graph degree list; a list no simple graph has is rejected."""

    values = tuple(degrees)
    if any(type(g) is not int or g < 0 for g in values):
        raise ValueError("graph degrees must be non-negative integers")
    if any(g >= len(values) for g in values):
        raise ValueError("impossible degree sequence: a degree exceeds the other vertices")
    if sum(values) % 2 or erdos_gallai_first_violation(values) is not None:
        raise ValueError("impossible degree sequence: not graphical")
    return values


def neighbourhood_capacity(degrees: Sequence[int], vertex: int) -> int:
    """M_v: over the g_v largest other degrees g_u, the sum of min(g_u - 1, g_v - 1)."""

    own = degrees[vertex]
    others = sorted((g for i, g in enumerate(degrees) if i != vertex), reverse=True)
    chosen = others[:own]
    if len(chosen) != own or (own > 0 and chosen[-1] < 1):
        raise ValueError("impossible degree sequence: too few possible neighbours")
    return sum(min(g - 1, own - 1) for g in chosen)


def nb_vertex_terms(degrees: Sequence[int]) -> list[tuple[int, int, int, int]]:
    """(g_v, M_v, floor(M_v / 2), C(g_v, 2) - floor(M_v / 2)) for every vertex."""

    values = graph_degree_list(degrees)
    terms: list[tuple[int, int, int, int]] = []
    for vertex, own in enumerate(values):
        capacity = neighbourhood_capacity(values, vertex)
        closed = capacity // 2
        if not 2 * closed <= capacity < 2 * closed + 2:
            raise AssertionError("NB neighbourhood edge cap is not the exact floor")
        if closed > comb(own, 2):
            raise AssertionError("NB neighbourhood edge cap exceeds C(g, 2)")
        terms.append((own, capacity, closed, comb(own, 2) - closed))
    return terms


def nb_open_wedge_floor(degrees: Sequence[int]) -> int:
    """OW_NB = sum_v [C(g_v, 2) - floor(M_v / 2)]."""

    return sum(term[3] for term in nb_vertex_terms(degrees))


def nb_triangle_cap(degrees: Sequence[int]) -> tuple[int, int, int]:
    """(W, OW_NB, cap): the largest T with W - 3T >= OW_NB."""

    values = graph_degree_list(degrees)
    wedges = sum(comb(g, 2) for g in values)
    floor = nb_open_wedge_floor(values)
    if not 0 <= floor <= wedges:
        raise AssertionError("NB open-wedge floor outside 0..W")
    cap = (wedges - floor) // 3
    slack = wedges - 3 * cap
    if not floor <= slack < floor + 3 or (slack - wedges) % 3:
        raise AssertionError("NB triangle cap violates the wedge congruence")
    return wedges, floor, cap


def nb_class_rows(degrees: Sequence[int]) -> list[dict[str, int]]:
    """The NB terms grouped by graph degree; equal degrees have equal terms."""

    counts = Counter(nb_vertex_terms(degrees))
    if len({term[0] for term in counts}) != len(counts):
        raise AssertionError("equal degrees produced different NB terms")
    return [
        {
            "GRAPH_DEGREE": g,
            "VERTICES": n,
            "NEIGHBOURHOOD_CAPACITY": m,
            "MAX_NEIGHBOURHOOD_EDGES": c,
            "OPEN_WEDGE_FLOOR_PER_VERTEX": o,
        }
        for (g, m, c, o), n in sorted(counts.items(), reverse=True)
    ]


def graph_nb_rows(neighbours: Sequence[Collection[int]]) -> list[tuple[int, int, int]]:
    """(g_v, e(N(v)), M_v) of an explicit simple graph; asserts the NB inequality."""

    size = len(neighbours)
    sets = [frozenset(n) for n in neighbours]
    asymmetric = any(
        v in neighbours_of or any(not 0 <= u < size or v not in sets[u] for u in neighbours_of)
        for v, neighbours_of in enumerate(sets)
    )
    if asymmetric:
        raise AssertionError("adjacency is not a simple undirected graph")
    degrees = [len(s) for s in sets]
    out: list[tuple[int, int, int]] = []
    for v, s in enumerate(sets):
        inside = sum(b in sets[a] for a, b in combinations(sorted(s), 2))
        capacity = neighbourhood_capacity(degrees, v)
        if 2 * inside > capacity:
            raise AssertionError("NB inequality fails on an explicit graph")
        out.append((degrees[v], inside, capacity))
    return out


def small_graph_soundness(max_vertices: int = SMALL_GRAPH_VERTICES) -> dict[str, object]:
    """Every labelled simple graph on 1..max_vertices vertices satisfies the NB caps."""

    graphs = vertices_checked = tight = 0
    for size in range(1, max_vertices + 1):
        pairs = list(combinations(range(size), 2))
        for mask in range(1 << len(pairs)):
            neighbours: list[set[int]] = [set() for _ in range(size)]
            for bit, (a, b) in enumerate(pairs):
                if mask >> bit & 1:
                    neighbours[a].add(b)
                    neighbours[b].add(a)
            local = graph_nb_rows(neighbours)
            degrees = [g for g, _, _ in local]
            wedges, floor, cap = nb_triangle_cap(degrees)
            open_wedges = sum(comb(g, 2) - inside for g, inside, _ in local)
            triangles = sum(inside for _, inside, _ in local) // 3
            if open_wedges < floor or triangles > cap or wedges != open_wedges + 3 * triangles:
                raise AssertionError("NB open-wedge or triangle cap fails on a small graph")
            graphs += 1
            vertices_checked += size
            tight += any(2 * inside >= capacity - 1 for g, inside, capacity in local if g)
    return {
        "STATUS": "PASS",
        "MAX_VERTICES": max_vertices,
        "LABELLED_GRAPHS_CHECKED": graphs,
        "VERTICES_CHECKED": vertices_checked,
        "GRAPHS_WITH_A_TIGHT_VERTEX": tight,
    }


def profile_degrees(profile: DegreeProfile) -> tuple[int, ...]:
    return tuple(K20_TICKET_CAPACITY + d for d in profile)


def profile_nb_cap(profile: DegreeProfile) -> tuple[int, int, int]:
    """(W, OW_NB, NB cap) of one min-S2 triple-degree profile."""

    if r32.structural_failures(profile):
        raise AssertionError("profile outside the min-S2 family")
    wedges, floor, cap = nb_triangle_cap(profile_degrees(profile))
    if wedges != overlap_wedge_count(profile) or 2 * wedges != WEDGE_OFFSET + sum(
        d * d for d in profile
    ):
        raise AssertionError("wedge identity W = (1326 + sum d^2) / 2 failed")
    if cap < K20_TRIPLE_SUPPORT_COUNT:
        raise AssertionError("NB cap below the 22 core triangles")
    return wedges, floor, cap


def r18_cap(profile: DegreeProfile) -> int:
    """R18's induced-P3 class cap, valid for every min-S2 profile."""

    floor = generic_open_wedge_floor(
        K20_TICKET_COUNT, EDGE_COUNT, K20_TICKET_CAPACITY, 2 * K20_TICKET_CAPACITY
    )
    envelope = graph_triangle_upper_bound_from_open_wedges(profile_degrees(profile), floor)
    return integer(envelope["GRAPH_TRIANGLE_UPPER_BOUND"])


# NB_MODULE_PART_2

R19_RESULT = "b649-k20-min-s2-dual-owner-refinement-r19-result.json"
R19_SHA256 = "e6f085cdc57c8c91f1ef02e1f847d5015b04aad17cb9c426866fb68ff32ea671"
R31_RESULT = r31.RESULT_FILENAME
PINNED_R25 = "PINNED_R25_R13_OPTIMUM_NO_RERUN"
SUMMARY_KEYS = (
    "TASK_STATUS",
    "NB_LEMMA_STATUS",
    "CURSOR_CERTIFIED_BOUND",
    "W809_CLASS_MAX",
    "W809_CLASS_COUNT",
    "RESOLVED_LEDGER_MAX",
    "FINAL_FAMILY_UPPER_BOUND",
    "FINAL_OWNER_CLASS",
    "REMAINING_GAP",
    "CAP_SOURCE_COUNTS",
    "INHERITED_R10_SCOPE_STATUS",
)


@dataclass(frozen=True)
class CapAuthorities:
    """Pinned certificate rows. Callers may tamper a copy; load never solves."""

    proofs: list[dict[str, object]]
    steps: list[dict[str, object]]
    plateaus: list[dict[str, object]]
    route4: list[dict[str, object]]
    route_b: list[dict[str, object]]
    cheap: list[dict[str, object]]
    inherited: dict[str, object]
    witness: dict[str, object]


def _pinned(filename: str, digest: str, label: str) -> dict[str, object]:
    blob = r31.git("show", f"{BASE_HEAD}:{RESULT_DIRECTORY}/{filename}")
    if hashlib.sha256(blob).hexdigest() != digest:
        raise AssertionError(f"sealed {label} fingerprint changed")
    return object_row(json.loads(blob))


def _table(result: Mapping[str, object], key: str) -> list[dict[str, object]]:
    return [object_row(raw) for raw in rows(result[key])]


def load_cap_authorities() -> CapAuthorities:
    """R30, R31, R32, R25 and the twelve-profile R19 scope, from pinned git blobs."""

    r30_result, _digest = r31.r30_authority()
    r31_result = _pinned(R31_RESULT, R31_SHA256, "R31")
    r32_result = _pinned(R32_RESULT, R32_SHA256, "R32")
    r25_result = _pinned(R25_RESULT, R25_SHA256, "R25")
    r19_result = _pinned(R19_RESULT, R19_SHA256, "R19")
    return CapAuthorities(
        proofs=_table(r30_result, "GROUP_ATTEMPTS"),
        steps=_table(r30_result, "REFINEMENT_STEPS"),
        plateaus=_table(r30_result, "PLATEAU_CERTIFICATES"),
        route4=_table(r31_result, "ROUTE4_CERTIFICATES"),
        route_b=_table(r32_result, "ROUTE_B_CERTIFICATES"),
        cheap=_table(r25_result, "CHEAP_CERTIFICATES"),
        inherited=r19_result,
        witness=object_row(r31_result["SOUNDNESS_WITNESS"]),
    )


def text(raw: object) -> str:
    if type(raw) is not str:
        raise AssertionError("certificate source field is not text")
    return raw


def bracket_index(row: str, prefix: str) -> int | None:
    if not (row.startswith(prefix) and row.endswith("]")):
        return None
    body = row[len(prefix) : -1]
    if not body.isdecimal():
        return None
    return int(body)


def row_at(items: Sequence[Mapping[str, object]], index: int, label: str) -> Mapping[str, object]:
    if index < 0 or index >= len(items):
        raise AssertionError(f"{label} index out of range")
    return items[index]


def _retarget_group(attempt: int, authorities: CapAuthorities) -> tuple[str, str, str]:
    proof = row_at(authorities.proofs, attempt, "GROUP_ATTEMPTS")
    if proof.get("ATTEMPT_INDEX") != attempt:
        raise AssertionError("SOURCE_PROOF_IDENTITY_MISMATCH")
    return R30_RESULT, f"GROUP_ATTEMPTS[{attempt}]", text(proof.get("ROUTE"))


def unwrap_certificate_source(
    profile: DegreeProfile, cap: int, cert: Certificate, authorities: CapAuthorities
) -> tuple[str, str, str]:
    """Follow Route-B, Route-4 and motif wrappers back to the cap's own row."""

    source, row, relaxation = cert.source_result, cert.source_row, cert.relaxation
    for _depth in range(6):
        route_b = bracket_index(row, "ROUTE_B_CERTIFICATES[")
        if source == R32_RESULT and route_b is not None:
            sealed = row_at(authorities.route_b, route_b, "ROUTE_B_CERTIFICATES")
            if text(sealed.get("PROFILE_ID")) != profile_id(profile):
                raise AssertionError("certificate source profile mismatch")
            if integer(sealed.get("CERTIFIED_TRIANGLE_CAP")) != cap:
                raise AssertionError("certificate source cap mismatch")
            inner = object_row(sealed["CERTIFICATE_SOURCE"])
            source = text(inner.get("SOURCE_RESULT"))
            row = text(inner.get("SOURCE_ROW"))
            relaxation = text(inner.get("SOURCE_RELAXATION"))
            continue
        route4 = bracket_index(row, "ROUTE4_CERTIFICATES[")
        if source == R31_RESULT and route4 is not None:
            sealed = row_at(authorities.route4, route4, "ROUTE4_CERTIFICATES")
            if text(sealed.get("PROFILE_ID")) != profile_id(profile):
                raise AssertionError("certificate source profile mismatch")
            if integer(sealed.get("TRIANGLE_CAP")) != cap:
                raise AssertionError("certificate source cap mismatch")
            source = text(sealed.get("SOURCE_RESULT"))
            row = text(sealed.get("SOURCE_ROW"))
            relaxation = text(sealed.get("SOURCE_RELAXATION"))
            continue
        break
    step_index = bracket_index(row, "REFINEMENT_STEPS[")
    if source == R30_RESULT and step_index is not None:
        step = row_at(authorities.steps, step_index, "REFINEMENT_STEPS")
        kind = text(step.get("KIND"))
        same_profile = text(step.get("PROFILE_ID")) == profile_id(profile)
        same_cap = integer(step.get("TRIANGLE_CAP")) == cap
        if not same_profile or not same_cap:
            raise AssertionError("motif step identity mismatch")
        if kind == r30.KIND_REFUTATION:
            return _retarget_group(integer(step.get("ATTEMPT_INDEX")), authorities)
        if kind != r30.KIND_MOTIF:
            raise AssertionError("UNVERIFIED catalog certificate")
        found: Mapping[str, object] | None = None
        for earlier in authorities.steps[:step_index]:
            if (
                earlier.get("KIND") == r30.KIND_REFUTATION
                and earlier.get("PROFILE_ID") == profile_id(profile)
                and integer(earlier.get("TRIANGLE_CAP")) == cap
            ):
                found = earlier
        if found is not None:
            return _retarget_group(integer(found.get("ATTEMPT_INDEX")), authorities)
    return source, row, relaxation


def _classify_refutation(
    profile: DegreeProfile, cap: int, index: int, relaxation: str, authorities: CapAuthorities
) -> str:
    proof = row_at(authorities.proofs, index, "GROUP_ATTEMPTS")
    if proof.get("ATTEMPT_INDEX") != index or text(proof.get("ROUTE")) != relaxation:
        raise AssertionError("SOURCE_PROOF_IDENTITY_MISMATCH")
    try:
        accepted = r28.r26.accepted_cap(proof, (profile,), cap)
    except AssertionError as exc:
        raise AssertionError("SOURCE_PROOF_IDENTITY_MISMATCH") from exc
    if accepted != cap:
        raise AssertionError("SOURCE_PROOF_NOT_INFEASIBLE")
    return VERIFY_REFUTATION


def _classify_r25(
    profile: DegreeProfile, cap: int, index: int, relaxation: str, authorities: CapAuthorities
) -> str:
    if relaxation != PINNED_R25:
        raise AssertionError("UNVERIFIED catalog certificate")
    row = row_at(authorities.cheap, index, "CHEAP_CERTIFICATES")
    if text(row.get("PROFILE_ID")) != profile_id(profile):
        raise AssertionError("pinned R25 row does not match the profile")
    envelope = object_row(row["PROFILE_ENVELOPE"])
    relaxation_row = object_row(row["R13_RELAXATION"])
    if text(relaxation_row.get("SOLVER_STATUS")) != "OPTIMAL":
        raise AssertionError("pinned R25 relaxation is not OPTIMAL")
    if integer(envelope.get("GRAPH_TRIANGLE_UPPER_BOUND")) != cap:
        raise AssertionError("pinned R25 row does not match the catalog cap")
    return VERIFY_R25


def _classify_plateau(
    profile: DegreeProfile, cap: int, index: int, relaxation: str, authorities: CapAuthorities
) -> str:
    if relaxation != r28.ROUTE_CLASS:
        raise AssertionError("UNVERIFIED catalog certificate")
    row = row_at(authorities.plateaus, index, "PLATEAU_CERTIFICATES")
    identities = [text(item) for item in rows(row["PLATEAU_PROFILE_IDS"])]
    if profile_id(profile) not in identities:
        raise AssertionError("plateau certificate does not contain the profile")
    if integer(row.get("GRAPH_TRIANGLE_UPPER_BOUND")) != cap:
        raise AssertionError("plateau cap mismatch")
    if text(row.get("CLASS_CERTIFICATE_KIND")) != r28.ROUTE_CLASS:
        raise AssertionError("plateau class kind mismatch")
    if r18_cap(profile) > cap:
        raise AssertionError("R18 cap exceeds the catalog cap")
    return VERIFY_R18


def _classify_motif_r18(
    profile: DegreeProfile, cap: int, index: int, authorities: CapAuthorities
) -> str:
    step = row_at(authorities.steps, index, "REFINEMENT_STEPS")
    if text(step.get("KIND")) != r30.KIND_MOTIF:
        raise AssertionError("UNVERIFIED catalog certificate")
    same_profile = text(step.get("PROFILE_ID")) == profile_id(profile)
    same_cap = integer(step.get("TRIANGLE_CAP")) == cap
    if not same_profile or not same_cap:
        raise AssertionError("motif step identity mismatch")
    if r18_cap(profile) > cap:
        raise AssertionError("R18 cap exceeds the catalog cap")
    return VERIFY_R18


def classify_catalog_source(
    profile: DegreeProfile, cert: Certificate, authorities: CapAuthorities
) -> str:
    """Accept a catalog cap only from an R30 refutation, an R18 row, or a pinned R25 row."""

    cap = cert.triangle_cap
    if cert.profile != profile or cap is None:
        raise AssertionError("UNVERIFIED catalog certificate")
    source, row, relaxation = unwrap_certificate_source(profile, cap, cert, authorities)
    group = bracket_index(row, "GROUP_ATTEMPTS[")
    if source == R30_RESULT and group is not None:
        return _classify_refutation(profile, cap, group, relaxation, authorities)
    cheap = bracket_index(row, "CHEAP_CERTIFICATES[")
    if source == R25_RESULT and cheap is not None:
        return _classify_r25(profile, cap, cheap, relaxation, authorities)
    plateau = bracket_index(row, "PLATEAU_CERTIFICATES[")
    if source == R30_RESULT and plateau is not None:
        return _classify_plateau(profile, cap, plateau, relaxation, authorities)
    step = bracket_index(row, "REFINEMENT_STEPS[")
    if source == R30_RESULT and step is not None:
        return _classify_motif_r18(profile, cap, step, authorities)
    raise AssertionError("UNVERIFIED catalog certificate")


def classify_ledger(
    chase: Chase, authorities: CapAuthorities
) -> dict[DegreeProfile, str]:
    kinds: dict[DegreeProfile, str] = {}
    for profile, cert in chase.catalog.items():
        try:
            kinds[profile] = classify_catalog_source(profile, cert, authorities)
        except AssertionError as exc:
            raise AssertionError(f"{profile_id(profile)}: {exc}") from exc
    if len(kinds) != LEDGER_COUNT or set(kinds) != set(chase.catalog):
        raise AssertionError("catalog source partition is incomplete")
    return kinds


def catalog_source_counts(chase: Chase, authorities: CapAuthorities) -> dict[str, int]:
    counts = Counter(classify_ledger(chase, authorities).values())
    if sum(counts.values()) != LEDGER_COUNT:
        raise AssertionError("catalog source partition is incomplete")
    return {kind: counts[kind] for kind in sorted(counts)}


def inherited_r10_scope(
    chase: Chase, authorities: CapAuthorities, kinds: Mapping[DegreeProfile, str]
) -> dict[str, object]:
    """Validate the twelve R19 profiles already in the ledger. Do not rebuild the census."""

    if authorities.inherited.get("FULL_4850_PROFILE_CENSUS_REBUILT") is not False:
        raise AssertionError("inherited R10 scope rebuilt a census")
    covered: list[dict[str, object]] = []
    profiles: list[DegreeProfile] = []
    for raw in rows(authorities.inherited["RESOLVED_PROFILES_ABOVE_CURSOR_OUTSIDE_OWNER_SET"]):
        row = object_row(raw)
        identity = text(row.get("PROFILE"))
        profile = decode_profile(identity)
        if profile not in chase.catalog or profile not in kinds:
            raise AssertionError("inherited R10 profile missing from the ledger")
        kind = kinds[profile]
        if kind not in (VERIFY_REFUTATION, VERIFY_R18, VERIFY_R25):
            raise AssertionError("inherited R10 profile has no verified cap source")
        profiles.append(profile)
        covered.append(
            {
                "PROFILE_ID": identity,
                "CAP_SOURCE": kind,
                "CATALOG_TRIANGLE_CAP": chase.catalog[profile].triangle_cap,
                "R19_CERTIFICATE_SOURCE": text(row.get("CERTIFICATE_SOURCE")),
                "R19_FAMILY_UPPER_BOUND": integer(row.get("FAMILY_UPPER_BOUND")),
            }
        )
    if len(covered) != 12 or len(set(profiles)) != 12:
        raise AssertionError("inherited R10 scope is not the twelve-profile set")
    return {
        "STATUS": "PASS",
        "PROFILE_COUNT": 12,
        "CENSUS_REBUILT": False,
        "COVERAGE_SQUARE_SUMS_ARE_NOT_THE_R10_SCOPE": list(COVERAGE_SQUARE_SUMS),
        "PROFILES": covered,
    }


def assert_nb_capacity(degrees: Sequence[int]) -> None:
    """Recompute M_v from the degree list and reject a capacity that is not that sum."""

    values = graph_degree_list(degrees)
    for vertex, own in enumerate(values):
        others = sorted(
            (degree for index, degree in enumerate(values) if index != vertex), reverse=True
        )
        chosen = others[:own]
        if len(chosen) != own or (own > 0 and chosen[-1] < 1):
            raise ValueError("impossible degree sequence: too few possible neighbours")
        expected = sum(min(degree - 1, own - 1) for degree in chosen)
        actual = neighbourhood_capacity(values, vertex)
        if actual != expected:
            if own > 0 and actual == 0:
                raise ValueError("impossible degree sequence: too few possible neighbours")
            raise AssertionError("NB neighbourhood capacity disagrees with the closed form")
        closed = actual // 2
        if not 2 * closed <= actual < 2 * closed + 2 or closed > comb(own, 2):
            raise AssertionError("NB neighbourhood edge cap is not the exact floor")


def combined_triangle_cap(nb_cap: int, class_cap: int, catalog_cap: int | None = None) -> int:
    """The strongest of the NB cap, the R18 class cap, and a verified catalog cap."""

    caps = [nb_cap, class_cap] if catalog_cap is None else [nb_cap, class_cap, catalog_cap]
    if any(type(cap) is not int or cap < K20_TRIPLE_SUPPORT_COUNT for cap in caps):
        raise AssertionError("triangle cap below the 22 core triangles")
    return min(caps)


def profile_route_b(profile: DegreeProfile, cap: int) -> tuple[int, int, int, bool]:
    """All-t Route B. Returns (bound, s3, argmax triangle count, strictly increasing)."""

    if cap < K20_TRIPLE_SUPPORT_COUNT:
        raise AssertionError("triangle cap below the 22 core triangles")
    terms = r32.route_b_envelope(profile, cap, r28.profile_s4_floor(profile))
    if not terms:
        raise AssertionError("empty Route-B envelope")
    increasing = all(left[1] < right[1] for left, right in pairwise(terms))
    chosen = max(terms, key=lambda term: (term[1], term[0]))
    return chosen[1], chosen[5], chosen[0], increasing


def cursor_certificate(profile: DegreeProfile = CURSOR) -> dict[str, object]:
    """Closed-form NB plus Route B for one profile. The cursor must keep OW >= 80 and T <= 243."""

    wedges, floor, nb_cap = profile_nb_cap(profile)
    if profile == CURSOR and (
        floor < CURSOR_TARGETS["NB_OPEN_WEDGE_FLOOR"] or nb_cap > CURSOR_TARGETS["NB_TRIANGLE_CAP"]
    ):
        raise AssertionError("cursor NB regression")
    assert_nb_capacity(profile_degrees(profile))
    class_cap = r18_cap(profile)
    cap = combined_triangle_cap(nb_cap, class_cap)
    bound, s3, argmax, increasing = profile_route_b(profile, cap)
    if profile == CURSOR and (not increasing or argmax != cap):
        raise AssertionError("cursor Route-B envelope is not maximized at the cap")
    coarse = coarse_profile_envelope(profile)
    if coarse.fourth_order_credit != INHERITED_FOURTH_ORDER_CREDIT:
        raise AssertionError("coarse fourth-order credit changed")
    if bound > coarse.family_upper_bound:
        raise AssertionError("Route B exceeds the coarse envelope")
    return {
        "PROFILE_ID": profile_id(profile),
        "WEDGE_COUNT": wedges,
        "NB_OPEN_WEDGE_FLOOR": floor,
        "NB_TRIANGLE_CAP": nb_cap,
        "R18_TRIANGLE_CAP": class_cap,
        "TRIANGLE_CAP": cap,
        "ALL_T_MAX_BOUND": bound,
        "S3_AT_MAXIMUM": s3,
        "ENVELOPE_MAXIMIZED_AT_TRIANGLES": argmax,
        "ENVELOPE_STRICTLY_INCREASING_IN_T": increasing,
        "COARSE_FAMILY_UPPER_BOUND": coarse.family_upper_bound,
        "S1": K20_S1,
        "S2": K20_S2,
    }


def enumerate_degree_square_class(square_sum: int) -> tuple[DegreeProfile, ...]:
    """Histograms with sum d = 66 and sum d^2 fixed, screened without ranked lookup."""

    if type(square_sum) is not int or square_sum < 0:
        raise ValueError("square sum must be a non-negative integer")
    found: list[DegreeProfile] = []
    counts = [0] * (K20_TICKET_CAPACITY + 1)

    def visit(degree: int, slots: int, total: int, squares: int) -> None:
        if degree < 0:
            if slots == total == squares == 0:
                profile = tuple(
                    value
                    for value in range(K20_TICKET_CAPACITY, -1, -1)
                    for _repeat in range(counts[value])
                )
                if len(profile) != K20_TICKET_COUNT:
                    raise AssertionError("degree histogram lost a ticket")
                if not linear_triple_degree_sequence_passes_pair_capacity(
                    profile, K20_TRIPLE_SUPPORT_COUNT
                ):
                    return
                residual = residual_double_ticket_degrees(profile)
                if not simple_graph_degree_sequence_is_graphical(residual):
                    return
                if profile_shadow_obstruction(profile) is not None:
                    return
                found.append(profile)
            return
        if degree == 0:
            if total == 0 and squares == 0:
                counts[0] = slots
                visit(-1, 0, 0, 0)
                counts[0] = 0
            return
        for count in range(slots, -1, -1):
            used = count * degree
            used_squares = used * degree
            if used > total or used_squares > squares:
                continue
            rest_slots = slots - count
            rest_total = total - used
            rest_squares = squares - used_squares
            square_room = rest_slots * (degree - 1) ** 2
            if rest_total > rest_slots * (degree - 1) or rest_squares > square_room:
                continue
            counts[degree] = count
            visit(degree - 1, rest_slots, rest_total, rest_squares)
        counts[degree] = 0

    visit(K20_TICKET_CAPACITY, K20_TICKET_COUNT, K20_TRIPLE_INCIDENCE_COUNT, square_sum)
    ordered = tuple(sorted(found, reverse=True))
    if len(set(ordered)) != len(ordered):
        raise AssertionError("degree class enumeration duplicated a profile")
    return ordered


def assert_w809_membership(chase: Chase, plateau: PlateauFrontier) -> tuple[DegreeProfile, ...]:
    """The ranked plateau is exactly the unresolved eligible suffix of sum d^2 = 292."""

    if chase.cursor is None:
        raise AssertionError("missing cursor")
    eligible = enumerate_degree_square_class(CURSOR_SQUARE_SUM)
    cursor = chase.cursor
    if any(profile > cursor and profile not in chase.bounds for profile in eligible):
        raise AssertionError("unresolved profile ranks above the cursor")
    if any(profile <= cursor and profile in chase.bounds for profile in eligible):
        raise AssertionError("resolved profile is inside the active square-sum frontier")
    expected = tuple(profile for profile in eligible if profile <= cursor)
    if expected != tuple(plateau.profiles) or not expected or expected[0] != CURSOR:
        raise AssertionError("W=809 plateau disagrees with the independent degree class")
    return eligible


def witness_soundness(witness: Mapping[str, object]) -> dict[str, object]:
    """STS(13) from the sealed graph. Route B must not undercut the sealed union."""

    report = r32.witness_route_b(witness)
    union = integer(report.get("EXACT_ANY_PRIZE_UNION"))
    if report.get("STATUS") != "PASS" or union != WITNESS_UNION:
        raise AssertionError("STS(13) witness structure differs from the sealed witness")
    if integer(report.get("ROUTE_B_BOUND_AT_REALIZED_CAP")) < WITNESS_UNION:
        raise AssertionError("Route B fell below the realized witness portfolio")
    return report


def _route_bound(profile: DegreeProfile, cap: int) -> tuple[int, int]:
    bound, s3, _argmax, _increasing = profile_route_b(profile, cap)
    if profile == WITNESS_PROFILE and bound < WITNESS_UNION:
        raise AssertionError("Route B fell below the realized witness portfolio")
    coarse = coarse_profile_envelope(profile)
    if coarse.fourth_order_credit != INHERITED_FOURTH_ORDER_CREDIT:
        raise AssertionError("coarse fourth-order credit changed")
    if bound > coarse.family_upper_bound:
        raise AssertionError("Route B exceeds the coarse envelope")
    return bound, s3


def refine_resolved(chase: Chase) -> tuple[int, int]:
    """Adopt a Route-B bound only when it is strictly stronger than the stored certificate."""

    adoptions: list[tuple[DegreeProfile, int, int, int]] = []
    retained = 0
    for profile in sorted(chase.catalog, reverse=True):
        cert = chase.catalog[profile]
        catalog_cap = cert.triangle_cap
        if catalog_cap is None:
            raise AssertionError("UNVERIFIED catalog certificate")
        _wedges, _floor, nb_cap = profile_nb_cap(profile)
        assert_nb_capacity(profile_degrees(profile))
        cap = combined_triangle_cap(nb_cap, r18_cap(profile), catalog_cap)
        s4 = r28.profile_s4_floor(profile)
        if cert.s4 != s4:
            raise AssertionError("S4 is not the global profile floor")
        bound, s3 = _route_bound(profile, cap)
        if bound < cert.bound:
            adoptions.append((profile, bound, s3, cap))
        else:
            retained += 1
    for index, (profile, bound, s3, cap) in enumerate(adoptions):
        cert = chase.catalog[profile]
        chase.bounds[profile] = bound
        chase.catalog[profile] = replace(
            cert,
            bound=bound,
            s3=s3,
            triangle_cap=cap,
            source_result=RESULT_FILENAME,
            source_row=f"NB_CERTIFICATES[{index}]",
            relaxation=ROUTE_NB,
        )
    if len(adoptions) + retained != LEDGER_COUNT:
        raise AssertionError("resolved ledger refinement dropped a profile")
    return len(adoptions), retained


def _member_bound(profile: DegreeProfile) -> tuple[DegreeProfile, int, int, int]:
    wedges, floor, nb_cap = profile_nb_cap(profile)
    if wedges != CURSOR_WEDGES or sum(degree * degree for degree in profile) != CURSOR_SQUARE_SUM:
        raise AssertionError("frontier member left the W=809 class")
    if profile == CURSOR and (
        floor < CURSOR_TARGETS["NB_OPEN_WEDGE_FLOOR"] or nb_cap > CURSOR_TARGETS["NB_TRIANGLE_CAP"]
    ):
        raise AssertionError("cursor NB regression")
    assert_nb_capacity(profile_degrees(profile))
    cap = combined_triangle_cap(nb_cap, r18_cap(profile))
    bound, s3 = _route_bound(profile, cap)
    return profile, bound, s3, cap


def install_frontier(
    chase: Chase,
    plateau: PlateauFrontier,
    member_rows: Sequence[tuple[DegreeProfile, int, int, int]],
) -> DegreeProfile:
    """Point the cursor at the next class before the certified members enter the ledger."""

    nxt, nxt_bound = plateau.next_profile, plateau.next_bound
    if nxt is None or nxt_bound is None or nxt in chase.bounds:
        raise AssertionError("the W=809 frontier did not end at a lower unresolved class")
    if sum(degree * degree for degree in nxt) >= CURSOR_SQUARE_SUM:
        raise AssertionError("next frontier is not a lower square-sum class")
    coarse = coarse_profile_envelope(nxt)
    if (
        coarse.family_upper_bound != nxt_bound
        or coarse.fourth_order_credit != INHERITED_FOURTH_ORDER_CREDIT
    ):
        raise AssertionError("next cursor coarse envelope disagrees with the plateau")
    chase.cursor, chase.cursor_bound = nxt, nxt_bound
    for index, (profile, bound, s3, cap) in enumerate(member_rows):
        if profile in chase.bounds or profile == chase.cursor:
            raise AssertionError("frontier member collides with the ledger or the cursor")
        chase.bounds[profile] = bound
        chase.catalog[profile] = Certificate(
            profile,
            bound,
            RESULT_FILENAME,
            f"W809_CERTIFICATES[{index}]",
            "CLASS_ENVELOPE_ONLY",
            s3,
            r28.profile_s4_floor(profile),
            cap,
            ROUTE_NB,
        )
    return nxt


def assert_family_agreement(chase: Chase) -> tuple[int, tuple[DegreeProfile, ...]]:
    family, owners = r28.family_state(chase)
    terms = list(chase.bounds.values())
    if chase.cursor_bound is not None:
        terms.append(chase.cursor_bound)
    if not terms or family != max(terms):
        raise AssertionError("family recompute disagreement")
    if family < WITNESS_UNION:
        raise AssertionError("family bound fell below a realized min-S2 portfolio")
    return family, owners


def certify_family(chase: Chase, authorities: CapAuthorities, deadline: float) -> dict[str, object]:
    """Classify, refine the resolved ledger, certify W=809, and recompute the family maximum."""

    primitives = r28.canonical_primitive_preflight()
    if primitives["STATUS"] != "PASS" or primitives.get("K20_S1") != K20_S1:
        raise AssertionError("canonical primitive gate failed")
    witness_report = witness_soundness(authorities.witness)
    graphs = small_graph_soundness()
    if graphs["STATUS"] != "PASS" or graphs["MAX_VERTICES"] != SMALL_GRAPH_VERTICES:
        raise AssertionError("NB small-graph gate failed")
    kinds = classify_ledger(chase, authorities)
    counts = {kind: count for kind, count in sorted(Counter(kinds.values()).items())}
    inherited = inherited_r10_scope(chase, authorities, kinds)
    cursor_row = cursor_certificate(CURSOR)
    if (chase.cursor, chase.cursor_bound) != (CURSOR, CURSOR_BOUND) or CURSOR in chase.bounds:
        raise AssertionError("R32 cursor moved before the frontier freeze")
    adopted, retained = refine_resolved(chase)
    original = set(chase.bounds)
    active = chase.cursor_bound
    if chase.cursor is None or active is None:
        raise AssertionError("missing cursor")
    plateau = r30.freeze_plateau(chase.cursor, active, chase.bounds, deadline)
    if type(plateau) is not PlateauFrontier:
        raise AssertionError("plateau freeze returned an unexpected frontier")
    eligible = assert_w809_membership(chase, plateau)
    member_rows = tuple(_member_bound(profile) for profile in plateau.profiles)
    cursor_bound = integer(cursor_row["ALL_T_MAX_BOUND"])
    member_cursor = next(bound for profile, bound, _s3, _cap in member_rows if profile == CURSOR)
    if member_cursor != cursor_bound:
        raise AssertionError("cursor certificate disagrees with the frontier member")
    nxt = install_frontier(chase, plateau, member_rows)
    r30.record_owner(chase)
    family, owners = assert_family_agreement(chase)
    resolved_max = max(chase.bounds[profile] for profile in original)
    class_max = max(bound for _profile, bound, _s3, _cap in member_rows)
    status = SUCCESS_A if family < START_BOUND else SUCCESS_B
    if owners and owners[0] == nxt:
        owner_class = profile_id(nxt)
    else:
        owner_class = ",".join(map(profile_id, owners))
    return {
        "TASK_ID": TASK_ID,
        "TASK_BRANCH": TASK_BRANCH,
        "WORKTREE_PATH": WORKTREE_PATH,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_STATUS": status,
        "NB_LEMMA_STATUS": "PROVED_CLOSED_FORM",
        "CURSOR_PROFILE": profile_id(CURSOR),
        "CURSOR_CERTIFIED_BOUND": cursor_bound,
        "CURSOR_OPEN_WEDGE_FLOOR": cursor_row["NB_OPEN_WEDGE_FLOOR"],
        "CURSOR_TRIANGLE_CAP": cursor_row["TRIANGLE_CAP"],
        "W809_CLASS_COUNT": len(member_rows),
        "W809_CLASS_MAX": class_max,
        "W809_PROFILE_IDS": [profile_id(profile) for profile, _bound, _s3, _cap in member_rows],
        "W809_ELIGIBLE_COUNT": len(eligible),
        "RESOLVED_LEDGER_COUNT": len(original),
        "RESOLVED_LEDGER_MAX": resolved_max,
        "FAMILY_UPPER_BOUND": family,
        "FINAL_FAMILY_UPPER_BOUND": family,
        "FINAL_OWNER_CLASS": owner_class,
        "FINAL_BOUND_OWNER_IDS": list(map(profile_id, owners)),
        "NEXT_CURSOR_PROFILE": profile_id(nxt),
        "NEXT_CURSOR_BOUND": chase.cursor_bound,
        "NEXT_CURSOR_SQUARE_SUM": sum(degree * degree for degree in nxt),
        "CAP_SOURCE_COUNTS": counts,
        "INHERITED_R10_SCOPE_STATUS": inherited["STATUS"],
        "INHERITED_R10_PROFILES": inherited["PROFILES"],
        "ADOPTED_COUNT": adopted,
        "RETAINED_COUNT": retained,
        "INCUMBENT": INCUMBENT,
        "CURRENT_INCUMBENT": INCUMBENT,
        "REMAINING_GAP": family - INCUMBENT,
        "CANONICAL_PRIMITIVE_STATUS": primitives["STATUS"],
        "CANONICAL_PRIMITIVES": primitives,
        "WITNESS_SOUNDNESS_STATUS": witness_report["STATUS"],
        "ROUTE_B_ON_WITNESS": witness_report,
        "SMALL_GRAPH_SOUNDNESS": graphs,
        "S1": K20_S1,
        "S2": K20_S2,
        "BOUND_RULE": BOUND_RULE,
        "SOLVER_CALLS": 0,
        "OUTCOME_ENUMERATIONS": 0,
        "NEW_HEAVY_SOLVER_STARTED": "NO",
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "FULL_CENSUS_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "R32_RESULT_SHA256": R32_SHA256,
        "R32_LEDGER_SHA256": R32_LEDGER_SHA256,
        "R19_RESULT_SHA256": R19_SHA256,
    }


def result_path() -> object:
    return r28.repo_root() / RESULT_DIRECTORY / RESULT_FILENAME


def same_result(left: Mapping[str, object], right: Mapping[str, object]) -> bool:
    return json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True)


def write_result(result: Mapping[str, object]) -> str:
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    target = r28.repo_root() / RESULT_DIRECTORY / RESULT_FILENAME
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, target)
    return hashlib.sha256(payload.encode()).hexdigest()


def compute_result(deadline: float | None = None) -> dict[str, object]:
    limit = monotonic() + REPLAY_SECONDS if deadline is None else deadline
    chase, _digest, _sealed = start_chase(limit)
    result = certify_family(chase, load_cap_authorities(), limit)
    write_result(result)
    return result


def replay_result(deadline: float | None = None) -> dict[str, object]:
    """Re-derive the family twice and require the written bytes to match both."""

    limit = monotonic() + REPLAY_SECONDS if deadline is None else deadline
    first_chase, _digest, _sealed = start_chase(limit)
    first = certify_family(first_chase, load_cap_authorities(), limit)
    second_chase, _digest, _sealed = start_chase(limit)
    second = certify_family(second_chase, load_cap_authorities(), limit)
    if not same_result(first, second):
        raise AssertionError("family replay diverged")
    digest = write_result(second)
    written = (r28.repo_root() / RESULT_DIRECTORY / RESULT_FILENAME).read_text(encoding="utf-8")
    loaded = object_row(json.loads(written))
    if not same_result(loaded, first):
        raise AssertionError("written family result diverged from the replay")
    file_digest = hashlib.sha256(
        (r28.repo_root() / RESULT_DIRECTORY / RESULT_FILENAME).read_bytes()
    ).hexdigest()
    if file_digest != digest:
        raise AssertionError("written family result digest changed")
    return second


def main() -> None:
    result = compute_result()
    print(json.dumps({key: result[key] for key in SUMMARY_KEYS}), flush=True)


if __name__ == "__main__":
    main()
