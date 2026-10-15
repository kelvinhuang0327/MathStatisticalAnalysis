"""Joint adoption of the immutable R12 donor and 65 root-extended Hunter trees.

All events below are residual: R_i = E_i minus (E_A union E_B). A type-0
core has 54 (66) incidences on 40 outside labels. Smoothing gives collision
mass at least 14 (26). Each nested overlap graph has rank at least rho(e),
since e <= sum C(r_i+1,2) <= C(sum r_i+1,2). Descending Kruskal spans all
these graphs at once. The exact small integer relaxations give H9 and H11.

Select one core vertex as root; attach every omitted vertex once as a leaf.
The 36 exact residual pair rows give 105560 on every attachment. These edges
are disjoint from the core edges, so their floors add on this SAME tree.
Pointwise, a tree on k present events induces at most k-1 edges, proving the
Hunter union bound. A legal witness checks applicability, never universality.

Existing union corrections combine by MAX, never SUM. Every represented
vector retains its strongest sealed bound; compressed members take MAX.
Recover the complete sealed ledgers and remaximize all 56574 Family terms.
No TS153 threshold replay, census, theorem search, or heavy solver is used.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from functools import cache
from hashlib import sha256
from itertools import combinations
from math import comb
from typing import Any, cast

from lottolab.research import (
    b649_k20_r3_classified_r12_five_level_ten_event_certificate_r1 as r12,
)

ts153, hunter, catalog, six = r12.ts153, r12.hunter, r12.catalog, r12.six
dense, sparse, digest = r12.dense, r12.sparse, r12.digest
type CountVector = tuple[int, ...]
type Cells = tuple[int, int, int, int]
type Edge = tuple[int, int]
type Terms = tuple[tuple[str, int], ...]
LedgerMember = catalog.LedgerMember
TASK_ID = "B649_K20_R3_R12_ROOT65_JOINT_ADOPTION_R1"
TASK_BRANCH = "codex/b649-k20-r3-r12-root65-joint-adoption-r1"
BASE_HEAD, BASE_TREE, BASE_RESULT_SHA256 = r12.BASE_HEAD, r12.BASE_TREE, r12.BASE_RESULT_SHA256
DONOR_HEAD = "88f7347f84c4497267c8f7871c9da9a09292c728"
DONOR_TREE = "88a874df8fb8817b48e8c770772b01c9bd09bde9"
DONOR_RESULT_SHA256 = "e38e08887221616ce11db5f819941f73a8df267d2758769ff62b78b161cd4659"
REPO_ROOT = r12.REPO_ROOT
SOURCE_RELATIVE = "src/lottolab/research/b649_k20_r3_r12_root65_joint_certificate_r1.py"
TEST_RELATIVE = "tests/unit/test_b649_k20_r3_r12_root65_joint_certificate_r1.py"
RESULT_RELATIVE = six.RESULTS + "b649-k20-r3-r12-root65-joint-certificate-r1-result.json"
RESULT_PATH = REPO_ROOT / RESULT_RELATIVE
DONOR_BLOBS = {
    "src/lottolab/research/b649_k20_r3_classified_r12_five_level_ten_event_certificate_r1.py": (
        "1ce715ef5728502ea2aab6a575b542e5be0e1163"
    ),
    "tests/unit/test_b649_k20_r3_classified_r12_five_level_ten_event_certificate_r1.py": (
        "d1a3c3c7f7bddf5d3a8b8735f92a1aeca3a051b4"
    ),
    r12.RESULT_RELATIVE: "35bbcf1a0a291e664d354565157d4d92a77f0121",
}
STATE_A, STATE_B = ts153.STATE_13169800, ts153.STATE_12695020
# members, vectors, target members, preserved members/vectors, target/remainder maxima.
REGION_SPECS = {
    STATE_A: (989, 1072, 47, 942, 1025, 354976356, 355112590),
    STATE_B: (1222, 1325, 18, 1204, 1307, 355015626, 355111939),
}
ROOT_TYPES = (0, 1, 4, 5, 6, 9, 16, 17, 19)
ROOT_FLOOR = 105560
ROOT_PAIR_COSTS = (
    (107800, 574000, 1691620, 3451651),
    (107800, 571200, 1679692, 3428908),
    (107800, 571200, 1679692, 3428908),
    (107800, 568610, 1667932, 3406165),
    (105560, 557200, 1649508, 3383814),
    (105560, 557200, 1649508, 3383814),
    (107800, 568680, 1669066, 3408685),
    (105560, 557480, 1650810, 3386334),
    (105560, 557480, 1650810, 3386334),
)
CORE_SPECS = {9: (54, 14, 9016, 3193400), 11: (66, 26, 30216, 4341400)}
COHORT_SPECS = {"A40": (40, 9, 3767400), "A7": (7, 11, 4915400), "B18": (18, 9, 4018000)}
CORRECTION_COMBINATION = "MAX(ALL_EXISTING_VALID_CREDITS, ROOT_EXTENDED_HUNTER); SUBTRACT_ONCE"


def verify_source_authority() -> dict[str, Any]:
    """Uncached live bytes, pinned Git blobs, lineage, and implementation binding."""
    base = r12.verify_source_authority()
    identity = r12.git_bytes("show", "-s", "--format=%H %T %P", DONOR_HEAD).decode().strip()
    if identity != f"{DONOR_HEAD} {DONOR_TREE} {BASE_HEAD}":
        raise AssertionError("immutable R12 donor HEAD/TREE/parent failed")
    blobs: dict[str, Any] = {}
    for relative, expected in DONOR_BLOBS.items():
        frozen = r12.git_bytes("show", f"{DONOR_HEAD}:{relative}")
        blob = r12.git_bytes("rev-parse", f"{DONOR_HEAD}:{relative}").decode().strip()
        if blob != expected or (REPO_ROOT / relative).read_bytes() != frozen:
            raise AssertionError(f"donor blob byte identity failed: {relative}")
        blobs[relative] = {"git_blob": blob, "sha256": sha256(frozen).hexdigest()}
    if blobs[r12.RESULT_RELATIVE]["sha256"] != DONOR_RESULT_SHA256:
        raise AssertionError("donor result SHA256 failed")
    return {
        "base": base,
        "donor_head": DONOR_HEAD,
        "donor_tree": DONOR_TREE,
        "donor_parent": BASE_HEAD,
        "donor_blobs": blobs,
        "implementation_sha256": {
            p: sha256((REPO_ROOT / p).read_bytes()).hexdigest()
            for p in (SOURCE_RELATIVE, TEST_RELATIVE)
        },
        "donor_judge_status": "NOT_PROVIDED; SELF_CHECK_PASS_ONLY",
    }


@cache
def base_result() -> dict[str, Any]:
    return r12.sealed(ts153.RESULT_RELATIVE)


@cache
def adopted_r12() -> dict[str, Any]:
    """Replay this donor only, never a historical or TS153 certificate."""
    r12.verify_stored_result()
    result = cast(dict[str, Any], json.loads((REPO_ROOT / r12.RESULT_RELATIVE).read_bytes()))
    if (
        result["AGGREGATE_LEVEL_COVERAGE"] != 29
        or result["AGGREGATE_VECTOR_COVERAGE"] != 183
        or result["TARGET_LEVEL_COVERAGE"] != 5
        or result["TARGET_VECTOR_COVERAGE"] != 15
        or result["TEN_EVENT_PROOF"]["hunter_floor"] != 3750600
        or result["NEW_AGGREGATE_MAX"] != 354588304
        or result["NEW_CLASSIFIED_MAX"] != 354800665
        or result["NEW_CLASSIFIED_DIGEST"] != r12.CLASSIFIED_DIGEST
        or result["FINAL_COMPLETE_R3_UB"] != 355142998
    ):
        raise AssertionError("complete R12 replay acceptance failed")
    return result


def cohort_vectors() -> dict[str, tuple[CountVector, ...]]:
    def vector(values: dict[int, int]) -> CountVector:
        return tuple(values.get(i, 0) for i in range(30))

    return {
        "A40": tuple(
            sorted(
                vector({0: 10, 1: j, 4: 4 - j, 5: 3 - k, 16: k, t: 1})
                for j in range(5)
                for k in range(4)
                for t in (6, 9)
            )
        ),
        "A7": tuple(sorted(vector({0: 12, 5: 6 - k, 16: k}) for k in range(7))),
        "B18": tuple(
            sorted(
                vector({0: 11, 1: j, 4: 5 - j, 17: k, 19: 2 - k})
                for j in range(6)
                for k in range(3)
            )
        ),
    }


def source_region(state_id: str) -> dict[str, Any]:
    rows = [r for r in base_result()["REGIONS"] if r["state_id"] == state_id]
    if state_id not in REGION_SPECS or len(rows) != 1:
        raise AssertionError("one sealed complete A/B region required")
    return cast(dict[str, Any], rows[0])


@cache
def complete_members(state_id: str) -> tuple[LedgerMember, ...]:
    region = source_region(state_id)
    rows = region["complete_region_members"]
    members = tuple(
        LedgerMember(
            dense(r["witness_counts"]),
            int(r["represented_vector_count"]),
            int(r["raw_bound"]),
            int(r["final_bound"]),
        )
        for r in rows
    )
    recovered = ts153.represented_vectors(state_id)
    mc, vc, *_ = REGION_SPECS[state_id]
    if (
        len(members) != mc
        or len({m.counts for m in members}) != mc
        or sum(m.represented_vector_count for m in members) != vc
        or digest(tuple((m.counts, m.final_bound) for m in members))
        != region["complete_updated_bounds_sha256"]
        or digest(tuple((m.counts, recovered[m.counts]) for m in members))
        != region["all_represented_vectors_sha256"]
        or max(m.final_bound for m in members) != dict(base_states())[state_id]
    ):
        raise AssertionError("complete sealed member/vector identity failed")
    for m, row in zip(members, rows, strict=True):
        vectors = recovered[m.counts]
        signature = hunter.eleven.compression_signature(catalog.rebuild_member(m))
        if (
            row["member_id"] != six.member_id(m.counts)
            or row["represented_vectors"] != [sparse(v) for v in vectors]
            or len(vectors) != m.represented_vector_count
            or min(vectors) != m.counts
            or row["compression_signature"] != catalog.normalized(signature)
            or m.final_bound > min(m.raw_bound, int(row["prior_bound"]))
        ):
            raise AssertionError("complete canonical member/alias identity failed")
        for v in vectors:
            state = catalog.rebuild_member(replace(m, counts=v, represented_vector_count=1))
            if (
                hunter.eleven.compression_signature(state) != signature
                or hunter.r14.raw_bound(state) != m.raw_bound
            ):
                raise AssertionError("compressed represented-vector identity failed")
    return members


def target_members(state_id: str) -> tuple[LedgerMember, ...]:
    """Intersect the actual complete ledger with all deterministic cohort identities."""
    cohorts = cohort_vectors()
    names = ("A40", "A7") if state_id == STATE_A else ("B18",)
    expected = {v for name in names for v in cohorts[name]}
    members = complete_members(state_id)
    recovered = ts153.represented_vectors(state_id)
    targets = tuple(m for m in members if any(v in expected for v in recovered[m.counts]))
    actual = [v for m in targets for v in recovered[m.counts]]
    if (
        len(targets) != REGION_SPECS[state_id][2]
        or len(actual) != len(set(actual))
        or set(actual) != expected
        or any(
            m.represented_vector_count != 1 or recovered[m.counts] != (m.counts,) for m in targets
        )
        or any(len(cohorts[n]) != COHORT_SPECS[n][0] for n in names)
    ):
        raise AssertionError("complete Root65 target member/vector identities required")
    return targets


@cache
def sealed_vector_bounds() -> dict[CountVector, tuple[tuple[str, int], ...]]:
    found = {v: set(rows) for v, rows in ts153.sealed_vector_bounds().items()}
    # The TS153 module's helper excludes its own output. Include these later,
    # stronger per-vector certificates explicitly, especially compressed aliases.
    for region in base_result()["REGIONS"]:
        for member in region["member_certificates"]:
            for row in member["vector_certificates"]:
                found.setdefault(dense(row["counts"]), set()).add(
                    (ts153.RESULT_RELATIVE, int(row["vector_new_bound"]))
                )
    return {v: tuple(sorted(rows)) for v, rows in found.items()}


def vector_prior_bound(member: LedgerMember, v: CountVector) -> int:
    return min((member.final_bound, *(b for _, b in sealed_vector_bounds().get(v, ()))))


def require_root_floor(floor: int, rows: tuple[tuple[int, ...], ...]) -> None:
    if type(floor) is not int or floor < 0 or not rows or any(r[6] < floor for r in rows):
        raise AssertionError("root floor exceeds a true residual intersection")


@cache
def root_pair_proof() -> dict[str, Any]:
    rows = hunter.exact_pair_rows(tuple((0, t) for t in ROOT_TYPES))
    expected = tuple(
        (0, t, 0, 0, 0, k, costs[k])
        for t, costs in zip(ROOT_TYPES, ROOT_PAIR_COSTS, strict=True)
        for k in range(4)
    )
    if rows != expected or len(rows) != 36:
        raise AssertionError("all 36 legal root residual pair rows required")
    counts: list[dict[str, Any]] = []
    for a, b, s, x, y, z, value in rows:
        cells = (s, x, y, z)
        tickets = hunter.realize_pair(hunter.type_cells(a), hunter.type_cells(b), cells)
        raw = hunter.outcome_count(tickets)
        triple_a = hunter.outcome_count((*tickets, hunter.ANCHOR_A))
        triple_b = hunter.outcome_count((*tickets, hunter.ANCHOR_B))
        quadruple = hunter.outcome_count((*tickets, hunter.ANCHOR_A, hunter.ANCHOR_B))
        residual = hunter.outcome_count(tickets, (hunter.ANCHOR_A, hunter.ANCHOR_B))
        if (
            tuple(len(tickets[0] & tickets[1] & set(c)) for c in hunter.CELL_LABELS) != cells
            or sum(cells) > hunter.family_pair_overlap_ceiling()
            or raw - triple_a - triple_b + quadruple != value
            or residual != value
            or six.residual_pair_intersection(a, b, cells) != value
            or value < 0
        ):
            raise AssertionError("legal realization/residual inclusion-exclusion recount failed")
        counts.append(
            {
                "types": [a, b],
                "cells": cells,
                "raw_E_pair": raw,
                "triple_A": triple_a,
                "triple_B": triple_b,
                "quadruple": quadruple,
                "residual_R_pair": residual,
                "seven_set_count": residual // hunter.OUTCOMES_PER_SET,
            }
        )
    require_root_floor(ROOT_FLOOR, rows)
    special = next(r for r in counts if r["types"] == [0, 6] and r["cells"] == (0, 0, 0, 0))
    if special["raw_E_pair"] != 107800 or special["residual_R_pair"] != 105560:
        raise AssertionError("raw E pair must not substitute for residual R pair")
    return catalog.normalized(
        {
            "rows": rows,
            "row_counts": counts,
            "row_count": len(rows),
            "common_residual_floor": ROOT_FLOOR,
            "special_type0_type6_overlap0": special,
        }
    )


@cache
def core_proof(n: int) -> dict[str, Any]:
    if n not in CORE_SPECS:
        raise AssertionError("only the nine/eleven type-0 cores are authorized")
    incidences, mass, cases, floor = CORE_SPECS[n]
    phi = ROOT_PAIR_COSTS[0]
    rows = tuple(tuple(r) for r in root_pair_proof()["rows"] if r[1] == 0)
    hunter.require_safe_pair_floors(phi, rows)
    q, rem = divmod(incidences, len(hunter.CELL_LABELS[3]))
    balanced = (40 - rem) * comb(q, 2) + rem * comb(q + 1, 2)
    ranks = tuple(hunter.rank_floor(e) for e in range(comb(n, 2) + 1))
    minimum = hunter.minimum_tree_correction(phi, balanced, n)
    if (
        hunter.type_cells(0) != (0, 0, 0, 6)
        or incidences != n * 6
        or len(hunter.CELL_LABELS[3]) != 40
        or balanced != mass
        or hunter.balanced_collision_mass(incidences, 40) != mass
        or hunter.verify_rank_floor_algebra(n) != comb(n, 2) + 1
        or minimum.census_size != cases
        or minimum.correction != floor
        or any(comb(r + 1, 2) < e or (r and comb(r, 2) >= e) for e, r in enumerate(ranks))
    ):
        raise AssertionError("exact core collision/forest-rank/Hunter minimum failed")
    return catalog.normalized(
        {
            "event_count": n,
            "type": 0,
            "outside_incidences": incidences,
            "collision_mass_floor": mass,
            "pair_floors": phi,
            "balanced_frequencies": ((q, 40 - rem), (q + 1, rem)),
            "rank_floor_table": ranks,
            "threshold_cases": cases,
            "minimizer_edges": minimum.edge_counts,
            "minimizer_ranks": minimum.rank_floors,
            "hunter_floor": floor,
            "universal_argument": "SMOOTHING; NESTED_RANK; KRUSKAL; HUNTER",
        }
    )


def validate_tree_extension(
    indices: tuple[int, ...], core: tuple[Edge, ...], attachments: tuple[Edge, ...]
) -> tuple[Edge, ...]:
    if not indices:
        raise AssertionError("core/attachment edges must form one disjoint 18-event tree")
    chosen = set(indices)
    root = indices[0]
    full = (*core, *attachments)
    if (
        len(indices) not in CORE_SPECS
        or len(chosen) != len(indices)
        or not chosen <= set(range(18))
        or len(core) != len(indices) - 1
        or any(a not in chosen or b not in chosen or a == b for a, b in core)
        or hunter.graph_rank(18, core) != len(core)
        or set(attachments) != {(root, j) for j in range(18) if j not in chosen}
        or len(attachments) != 18 - len(indices)
        or len({frozenset(e) for e in full}) != len(full)
        or len(full) != 17
        or hunter.graph_rank(18, full) != 17
    ):
        raise AssertionError("core/attachment edges must form one disjoint 18-event tree")
    return full


def witness_analysis(
    v: CountVector, n: int, support: tuple[tuple[int, ...], ...]
) -> dict[str, Any]:
    if not hunter.r8.validate_support_assignment(v, support):
        raise AssertionError("illegal Root65 support witness")
    types = tuple(i for i, c in enumerate(v) for _ in range(c))
    indices = tuple(j for j, t in enumerate(types) if t == 0)[:n]
    tickets = tuple(frozenset(t) for t in support)
    overlaps = {
        (a, b): len(tickets[indices[a]] & tickets[indices[b]]) for a, b in combinations(range(n), 2)
    }
    core_local = cast(tuple[Edge, ...], hunter.threshold_tree(n, overlaps))
    core = tuple((indices[a], indices[b]) for a, b in core_local)
    attachments = tuple((indices[0], j) for j in range(18) if j not in indices)
    full = validate_tree_extension(indices, core, attachments)
    proof = core_proof(n)
    phi = proof["pair_floors"]
    mass = sum(comb(sum(x in tickets[j] for j in indices), 2) for x in hunter.CELL_LABELS[3])
    e = tuple(sum(w >= k for w in overlaps.values()) for k in range(1, 4))
    ranks = tuple(
        hunter.graph_rank(n, (edge for edge, w in overlaps.items() if w >= k)) for k in range(1, 4)
    )
    phi_weight = sum(phi[overlaps[edge]] for edge in core_local)
    costs: list[int] = []
    for a, b in full:
        cells = cast(
            Cells, tuple(len(tickets[a] & tickets[b] & set(c)) for c in hunter.CELL_LABELS)
        )
        cost = six.residual_pair_intersection(*sorted((types[a], types[b])), cells)
        if (a, b) in attachments and cost < ROOT_FLOOR:
            raise AssertionError("attachment residual intersection below certified floor")
        costs.append(cost)
    if (
        len(indices) != n
        or any(types[j] != 0 for j in indices)
        or mass != sum(overlaps.values())
        or mass != sum(e)
        or mass < proof["collision_mass_floor"]
        or any(r < hunter.rank_floor(c) for r, c in zip(ranks, e, strict=True))
        or any(sum(overlaps[edge] >= k for edge in core_local) != ranks[k - 1] for k in range(1, 4))
        or phi_weight != hunter.tree_weight_floor(phi, ranks, n)
        or sum(costs[: n - 1]) != phi_weight
        or phi_weight < proof["hunter_floor"]
        or sum(costs) < proof["hunter_floor"] + (18 - n) * ROOT_FLOOR
    ):
        raise AssertionError("nested thresholds or same-tree edge-floor addition failed")
    return catalog.normalized(
        {
            "support_witness": support,
            "support_sha256": digest(support),
            "core_indices": indices,
            "core_tree": core,
            "attachment_edges": attachments,
            "extended_tree": full,
            "edge_costs": costs,
            "collision_mass": mass,
            "threshold_edge_counts": e,
            "threshold_ranks": ranks,
            "core_exact_weight": phi_weight,
            "extended_exact_weight": sum(costs),
        }
    )


def cohort_name(state_id: str, v: CountVector) -> str:
    matches = [
        name
        for name, vs in cohort_vectors().items()
        if v in vs and (name.startswith("A") == (state_id == STATE_A))
    ]
    if len(matches) != 1:
        raise AssertionError("one deterministic Root65 cohort required")
    return matches[0]


def certify_vector(state_id: str, member: LedgerMember, v: CountVector) -> dict[str, Any]:
    if member not in target_members(state_id) or v != member.counts:
        raise AssertionError("actual single-vector target membership required")
    name = cohort_name(state_id, v)
    _, n, old_credit = COHORT_SPECS[name]
    proof = core_proof(n)
    require_root_floor(ROOT_FLOOR, tuple(tuple(r) for r in root_pair_proof()["rows"]))
    state = catalog.rebuild_member(replace(member, counts=v, represented_vector_count=1))
    uncorrected = hunter.r14.joint_constant() - state.anchor_pair_s2 + state.anchor_triple_s3
    prior = vector_prior_bound(member, v)
    credits = {
        "R6_PAIR": state.residual_pair_union_penalty,
        "FOREST": state.complementary_forest_floor,
        "SEALED_MEMBER": uncorrected - member.final_bound,
        "SEALED_VECTOR": uncorrected - prior,
    }
    existing = hunter.combine_corrections(credits)
    extension_floor = int(proof["hunter_floor"]) + (18 - n) * ROOT_FLOOR
    credits["ROOT_EXTENDED_HUNTER"] = extension_floor
    combined = hunter.combine_corrections(credits)
    bound = min(prior, uncorrected - combined)
    if (
        uncorrected
        != hunter.anchor_union_size()
        + sum(c * hunter.residual_event_size(i) for i, c in enumerate(v) if c)
        or existing != uncorrected - prior
        or credits["SEALED_MEMBER"] != old_credit
        or existing != max(c for k, c in credits.items() if k != "ROOT_EXTENDED_HUNTER")
        or combined != max(credits.values())
        or bound != uncorrected - combined
        or bound >= prior
        or min(credits.values()) < 0
        or extension_floor != (5080320 if name == "A7" else 4143440)
    ):
        raise AssertionError("existing credit preservation/MAX-only single replacement failed")
    support = ts153.prior.legal_support(v)
    witness = witness_analysis(v, n, support)
    return catalog.normalized(
        {
            "counts": sparse(v),
            "vector_id": six.member_id(v),
            "cohort": name,
            "uncorrected_anchor_bound": uncorrected,
            "sealed_vector_bounds": sealed_vector_bounds().get(v, ()),
            "vector_prior_bound": prior,
            "corrections": credits,
            "prior_applied_correction": existing,
            "combined_correction": combined,
            "vector_new_bound": bound,
            "core_event_count": n,
            "core_floor": proof["hunter_floor"],
            "attachment_count": 18 - n,
            "attachment_floor": ROOT_FLOOR,
            "tree_floor": extension_floor,
            "witness_analysis": witness,
        }
    )


def compressed_bound(bounds: tuple[int, ...]) -> int:
    if not bounds or any(type(b) is not int for b in bounds):
        raise AssertionError("all represented-vector safe bounds required")
    return max(bounds)


@cache
def region_certificate(state_id: str) -> dict[str, Any]:
    members = complete_members(state_id)
    targets = target_members(state_id)
    records = [certify_vector(state_id, m, m.counts) for m in targets]
    changed = {dense(r["counts"]): int(r["vector_new_bound"]) for r in records}
    if len(changed) != len(targets):
        raise AssertionError("each target vector must be updated exactly once")
    recovered = ts153.represented_vectors(state_id)
    complete: list[dict[str, Any]] = []
    untouched: list[tuple[CountVector, int, tuple[tuple[CountVector, int], ...]]] = []
    for member, old in zip(
        members, source_region(state_id)["complete_region_members"], strict=True
    ):
        vectors = recovered[member.counts]
        priors = tuple(vector_prior_bound(member, v) for v in vectors)
        bounds = tuple(changed.get(v, p) for v, p in zip(vectors, priors, strict=True))
        bound = compressed_bound(bounds)
        if (
            bound > member.final_bound
            or any(b > p for b, p in zip(bounds, priors, strict=True))
            or (member not in targets and (bounds != priors or bound != member.final_bound))
        ):
            raise AssertionError("untouched member/vector bound preservation failed")
        if member not in targets:
            untouched.append((member.counts, bound, tuple(zip(vectors, bounds, strict=True))))
        complete.append(
            {
                **old,
                "prior_bound": member.final_bound,
                "final_bound": bound,
                "represented_vector_bounds": [
                    {"counts": sparse(v), "prior_bound": p, "final_bound": b}
                    for v, p, b in zip(vectors, priors, bounds, strict=True)
                ],
            }
        )
    mc, vc, tc, pm, pv, target_max, remainder_max = REGION_SPECS[state_id]
    actual_target = max(changed.values())
    actual_remainder = max(r[1] for r in untouched)
    maximum = max(r["final_bound"] for r in complete)
    if (
        (len(members), sum(len(v) for v in recovered.values()), len(records)) != (mc, vc, tc)
        or (len(untouched), sum(len(r[2]) for r in untouched)) != (pm, pv)
        or actual_target != target_max
        or actual_remainder != remainder_max
        or maximum != max(actual_target, actual_remainder)
    ):
        raise AssertionError("complete Root65 region coverage/maxima failed")
    return catalog.normalized(
        {
            "state_id": state_id,
            "region_member_count": mc,
            "region_vector_count": vc,
            "target_member_count": tc,
            "target_vector_count": len(records),
            "preserved_member_count": pm,
            "preserved_vector_count": pv,
            "target_cohort_max": actual_target,
            "preserved_remainder_max": actual_remainder,
            "new_state_bound": maximum,
            "target_identity_sha256": digest(
                tuple((m.counts, recovered[m.counts]) for m in targets)
            ),
            "all_represented_vectors_sha256": digest(
                tuple((m.counts, recovered[m.counts]) for m in members)
            ),
            "preserved_member_vector_bounds_sha256": digest(tuple(untouched)),
            "member_certificates": records,
            "complete_region_members": complete,
        }
    )


def base_states() -> Terms:
    return tuple((str(r["stable_id"]), int(r["bound"])) for r in base_result()["FINAL_STATE_TERMS"])


def family_inputs() -> tuple[Terms, Terms, Terms, int]:
    source, donor = base_result(), adopted_r12()
    states = base_states()
    classified = ts153.classified_terms()
    updated = tuple((str(r["stable_id"]), int(r["bound"])) for r in donor["FINAL_CLASSIFIED_TERMS"])
    tail = six.sealed_tail_bound()
    if (
        len(states) != len(dict(states))
        or len(states) != 23
        or len(classified) != len(dict(classified))
        or len(classified) != 56550
        or len(updated) != len(dict(updated))
        or len(updated) != 56550
        or digest(classified) != source["CLASSIFIED_TERMS_SHA256"]
        or digest(updated) != r12.CLASSIFIED_DIGEST
        or updated != r12.nine.replace_aggregate(classified, donor["NEW_AGGREGATE_MAX"])
        or tail != source["TAIL_BOUND"]
        or tail != 354039277
    ):
        raise AssertionError("complete Classified/State/Tail term coverage or digest failed")
    return states, classified, updated, tail


def family_maximum(states: Terms, classified: Terms, tail: int) -> dict[str, Any]:
    terms = (*states, *classified, (r12.r24.TAIL_ID, tail))
    if (
        len(states) != 23
        or len(classified) != 56550
        or len(terms) != len(dict(terms))
        or len(terms) != 56574
    ):
        raise AssertionError("complete 56574 Family terms required")
    maximum = max(b for _, b in terms)
    runner = max(b for _, b in terms if b < maximum)
    check = six.tail.family_maximum(tail, states, classified)
    owners = sorted(k for k, b in terms if b == maximum)
    if check["R3_BOUND"] != maximum or check["OWNER_IDS"] != owners:
        raise AssertionError("independent Family maximum/owner recomputation failed")
    return {
        "term_count": len(terms),
        "terms_sha256": digest(terms),
        "maximum": maximum,
        "owner_ids": owners,
        "runner_up": {"bound": runner, "owner_ids": sorted(k for k, b in terms if b == runner)},
        "classified_max": max(b for _, b in classified),
        "tail": tail,
    }


def build_result() -> dict[str, Any]:
    authority = verify_source_authority()
    donor = adopted_r12()
    root = root_pair_proof()
    cores = [core_proof(n) for n in CORE_SPECS]
    regions = [region_certificate(s) for s in REGION_SPECS]
    states, classified, updated, tail = family_inputs()
    changes = {r["state_id"]: r["new_state_bound"] for r in regions}
    new_states = tuple((k, changes.get(k, b)) for k, b in states)
    start = family_maximum(states, classified, tail)
    root_only = family_maximum(new_states, classified, tail)
    r12_only = family_maximum(states, updated, tail)
    joint = family_maximum(new_states, updated, tail)
    if (
        sum(r["region_member_count"] for r in regions) != 2211
        or sum(r["region_vector_count"] for r in regions) != 2397
        or sum(r["target_member_count"] for r in regions) != 65
        or sum(r["target_vector_count"] for r in regions) != 65
        or start["maximum"] != 355145504
        or root_only["maximum"] != 355145504
        or r12_only["maximum"] != 355142998
        or joint["maximum"] != 355121046
        or joint["owner_ids"] != ["state:s2-14696976-s3-1059324"]
        or joint["runner_up"] != {"bound": 355116818, "owner_ids": ["state:s2-13548976-s3-951748"]}
        or {k for k, b in new_states if b != dict(states)[k]} != set(REGION_SPECS)
    ):
        raise AssertionError("joint adoption/three complete Family scenarios failed")
    return catalog.normalized(
        {
            "TASK_ID": TASK_ID,
            "TASK_STATUS": "SUCCESS",
            "TASK_BRANCH": TASK_BRANCH,
            "MODEL": "最強模型",
            "REMAINING_TASK_MODEL": "最強模型",
            "MODEL_LABEL_SOURCE": "OWNER_REQUEST; NOT_A_RUNTIME_MODEL_ATTESTATION",
            "BASE_HEAD": BASE_HEAD,
            "BASE_TREE": BASE_TREE,
            "BASE_RESULT_SHA256": BASE_RESULT_SHA256,
            "R12_DONOR_HEAD": DONOR_HEAD,
            "R12_DONOR_TREE": DONOR_TREE,
            "SOURCE_AUTHORITY": authority,
            "DONOR_BYTE_IDENTITY": "PASS_ALL_THREE_GIT_BLOBS_AND_BYTES",
            "R12_LEVEL_COVERAGE": 29,
            "R12_VECTOR_COVERAGE": 183,
            "R12_TARGET_LEVELS": list(r12.TARGET_ORDINALS),
            "R12_TARGET_VECTOR_COUNT": 15,
            "R12_H10": donor["TEN_EVENT_PROOF"]["hunter_floor"],
            "R12_CLASSIFIED_MAX": donor["NEW_CLASSIFIED_MAX"],
            "R12_CLASSIFIED_DIGEST": digest(updated),
            "R12_REPLAY_STATUS": "PASS_BYTE_EXACT_REPLAY",
            "RESIDUAL_EVENT_DEFINITION": r12.RESIDUAL_EVENT_DEFINITION,
            "ROOT65_TARGET_MEMBER_COUNT": 65,
            "ROOT65_TARGET_VECTOR_COUNT": 65,
            "ROOT_PAIR_PROOF": root,
            "ROOT_RESIDUAL_PAIR_ROW_STATUS": "PASS_36_EXACT_RESIDUAL_ROWS",
            "ROOT_RESIDUAL_FLOOR": root["common_residual_floor"],
            "CORE_PROOFS": cores,
            "H9_STATUS": "PASS_9016_CASES_H9_3193400",
            "H11_STATUS": "PASS_30216_CASES_H11_4341400",
            "TREE_EXTENSION_STATUS": (
                "PASS_SAME_TREE_DISJOINT_CORE_AND_ATTACHMENTS_18_VERTICES_17_EDGES"
            ),
            "REGIONS": regions,
            "CORRECTION_COMBINATION": CORRECTION_COMBINATION,
            "NO_DOUBLE_COUNT_STATUS": "PASS_MAX_ONLY_SINGLE_REPLACEMENT",
            "UNTOUCHED_BOUND_PRESERVATION": "PASS_ALL_MEMBER_AND_STRONGEST_SEALED_VECTOR_BOUNDS",
            "STATE_A_NEW_UB": changes[STATE_A],
            "STATE_B_NEW_UB": changes[STATE_B],
            "SCENARIOS": {"ROOT65_ONLY": root_only, "R12_ONLY": r12_only, "JOINT": joint},
            "START_COMPLETE_R3_UB": start["maximum"],
            "FINAL_COMPLETE_R3_UB": joint["maximum"],
            "ROOT_ONLY_FAMILY_GAIN": start["maximum"] - root_only["maximum"],
            "STRICT_GAIN_FROM_BASE": start["maximum"] - joint["maximum"],
            "STRICT_GAIN_VS_R12_DONOR": r12_only["maximum"] - joint["maximum"],
            "INCUMBENT": r12.r24.INCUMBENT,
            "REMAINING_GAP": joint["maximum"] - r12.r24.INCUMBENT,
            "FINAL_OWNER": joint["owner_ids"][0],
            "FINAL_RUNNER_UP": joint["runner_up"],
            "FINAL_STATE_TERMS": [{"stable_id": k, "bound": b} for k, b in new_states],
            "FINAL_CLASSIFIED_TERMS": donor["FINAL_CLASSIFIED_TERMS"],
            "TAIL_BOUND": tail,
            "FULL_56574_FAMILY_RECOMPUTATION": joint,
            "WITNESS_SOUNDNESS_STATUS": "PASS_65_LEGAL_SUPPORTS_AND_TREES_PLUS_15_R12_SUPPORTS",
            "PREDECESSOR_THRESHOLD_REBUILD_CALLS": 0,
            "NEW_HEAVY_SOLVER_STARTED": "NO",
            "OUTCOME_ENUMERATION_USED": False,
            "PRODUCTION_MUTATION": "NONE",
            "PUSH_PR_MERGE": "NONE",
            "WORKTREE_DISPOSITION": "RETAIN",
            "JUDGE_MODE": "SELF_CHECK_ONLY",
        }
    )


def encode(result: dict[str, Any]) -> str:
    return hunter.encode(result)


def verify_result(result: dict[str, Any]) -> dict[str, Any]:
    if result != build_result():
        raise AssertionError(
            "certificate differs from complete deterministic replay/source binding"
        )
    return {"status": "PASS", "target_members": 65, "target_vectors": 65, "family_terms": 56574}


def verify_stored_result() -> dict[str, Any]:
    stored = RESULT_PATH.read_bytes()
    result = cast(dict[str, Any], json.loads(stored))
    status = verify_result(result)
    if stored != encode(result).encode():
        raise AssertionError("result differs from byte-for-byte replay")
    return status


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(verify_stored_result(), sort_keys=True))
        return
    result = build_result()
    if args.write:
        RESULT_PATH.write_text(encode(result), encoding="utf-8")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "TASK_STATUS",
                    "FINAL_COMPLETE_R3_UB",
                    "STRICT_GAIN_FROM_BASE",
                    "REMAINING_GAP",
                )
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
