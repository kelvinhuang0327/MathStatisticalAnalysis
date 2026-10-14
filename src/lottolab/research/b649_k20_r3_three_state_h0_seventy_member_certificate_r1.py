"""Universal type-0 Hunter floors and seventy replacements in three R3 States.

If d_a >= d_b+2, moving one incidence a -> b reduces the collision sum by
d_a-d_b-1 > 0. Iteration terminates at balanced frequencies, proving the exact
integer minimum Q. For nested G_k={ij: overlap>=k}, descending Kruskal spans
each G_k. A graph of forest rank r has at most C(r+1,2) edges: its component
ranks r_j satisfy sum C(r_j+1,2) <= C(sum r_j+1,2). Thus rank(G_k)>=rho(e_k).
Every admissible threshold triple is minimized below, yielding a universal
tree weight. For each outcome belonging to k events, a tree induces at most
k-1 edges on those events. Summing this pointwise inequality proves Hunter's
union bound for every support. Nonnegative intersections extend the selected
type-0 tree to all eighteen residual events. Existing sealed credits and this
floor combine by MAX once. Legal witnesses illustrate, but do not replace,
the universal proof. No solver, census or outcome enumeration is used.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import replace
from functools import cache
from hashlib import sha256
from itertools import combinations
from math import comb
from pathlib import Path
from types import ModuleType
from typing import Any, cast

from lottolab.research import b649_k20_r3_state_13548976_three_level_shared_hunter_r1 as s135
from lottolab.research import b649_k20_r3_state_14122976_two_band_ten_event_hunter_r1 as s141
from lottolab.research import b649_k20_r3_three_component_joint_certificate_r1 as joint

hunter, catalog, six, r24 = joint.hunter, joint.catalog, joint.six, joint.r24
LedgerMember = catalog.LedgerMember
type CountVector = tuple[int, ...]
dense, sparse, digest, member_id = joint.dense, joint.sparse, joint.digest, joint.member_id
TASK_ID = "B649_K20_R3_THREE_STATE_H0_SEVENTY_MEMBER_CERTIFICATE_R1"
TASK_BRANCH = "codex/b649-k20-r3-three-state-h0-seventy-member-certificate-r1"
BASE_HEAD = "561983514cb3cfd9b9bab03ed13c0e4722dd747b"
BASE_TREE = "0cd09e9ab6b2a223b6d6c0a0263a9203c362f5db"
BASE_RESULT_SHA256 = "5cfcc058fa5bedaebf9f136491ff55961009fd28f800c59495a6f5b1858bff95"
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_RELATIVE = (
    six.RESULTS + "b649-k20-r3-three-state-h0-seventy-member-certificate-r1-result.json"
)
RESULT_PATH = REPO_ROOT / RESULT_RELATIVE
PAIR_FLOORS = (107800, 574000, 1691620, 3451651)
THEOREMS = {10: (20, 16982, 3767400), 11: (26, 30216, 4341400), 14: (48, 130472, 6063400)}
REGION_SPECS = {
    joint.TARGET_STATE_ID: (1222, 1325, 40, joint.REGION_SHA256),
    s141.TARGET_STATE_ID: (214, 221, 12, s141.REGION_SHA256),
    s135.TARGET_STATE_ID: (1427, 1543, 18, s135.REGION_SHA256),
}
SOURCE_MODULES = (joint, s141, s135)
RESIDUAL_EVENT_DEFINITION = joint.RESIDUAL_EVENT_DEFINITION
CORRECTION_COMBINATION = "MAX(EXISTING_VALID_CREDITS, APPLICABLE_TYPE0_HUNTER_FLOOR)"


def source_paths() -> tuple[str, ...]:
    """Executing predecessor closure plus every referenced sealed input."""

    pending = list(SOURCE_MODULES)
    seen: set[str] = set()
    paths: set[str] = set()
    while pending:
        module = pending.pop()
        if module.__name__ in seen:
            continue
        seen.add(module.__name__)
        if module.__file__ is not None:
            paths.add(str(Path(module.__file__).resolve().relative_to(REPO_ROOT)))
        for key in ("UPSTREAM_SHA256", "SOURCE_FILES"):
            paths.update(getattr(module, key, {}))
        for value in vars(module).values():
            if isinstance(value, ModuleType) and value.__name__.startswith("lottolab.research"):
                pending.append(value)
    paths.update(module.RESULT_RELATIVE for module in SOURCE_MODULES)
    return tuple(sorted(paths))


def verify_source_authority() -> dict[str, Any]:
    """Uncached Git object/working-byte checks protect even warm replay caches."""

    prefix = ["git", "-C", str(REPO_ROOT)]
    observed = subprocess.check_output(
        [*prefix, "show", "-s", "--format=%H %T", BASE_HEAD], text=True
    ).strip()
    blob = subprocess.check_output([*prefix, "show", f"{BASE_HEAD}:{joint.RESULT_RELATIVE}"])
    if observed != f"{BASE_HEAD} {BASE_TREE}" or sha256(blob).hexdigest() != BASE_RESULT_SHA256:
        raise AssertionError("immutable BASE_HEAD/TREE/result SHA authority failed")
    if subprocess.run([*prefix, "merge-base", "--is-ancestor", BASE_HEAD, "HEAD"]).returncode:
        raise AssertionError("checkout does not descend from exact immutable base")
    fingerprints: dict[str, str] = {}
    for path in source_paths():
        immutable = subprocess.check_output([*prefix, "show", f"{BASE_HEAD}:{path}"])
        if (REPO_ROOT / path).read_bytes() != immutable:
            raise AssertionError(f"immutable executing source or sealed input changed: {path}")
        fingerprints[path] = sha256(immutable).hexdigest()
    joint.verify_source_authority()
    return {
        "HEAD": BASE_HEAD,
        "TREE": BASE_TREE,
        "RESULT_SHA256": BASE_RESULT_SHA256,
        "upstream_sha256": fingerprints,
    }


@cache
def source_results() -> dict[str, dict[str, Any]]:
    verify_source_authority()
    results: dict[str, dict[str, Any]] = {}
    for module in SOURCE_MODULES:
        replay = module.build_result()
        if module.RESULT_PATH.read_bytes() != module.encode(replay).encode():
            raise AssertionError("immutable predecessor complete byte replay failed")
        results[module.TARGET_STATE_ID] = replay
    return results


@cache
def region_members(state_id: str) -> tuple[LedgerMember, ...]:
    """Recover the latest sealed member bounds, without a new ledger census."""

    source = source_results()[state_id]
    rows = source["COMPLETE_REGION_MEMBERS"]
    members = tuple(
        LedgerMember(
            dense(row["witness_counts"]),
            int(row["represented_vector_count"]),
            int(row["raw_bound"]),
            int(row["final_bound"]),
        )
        for row in rows
    )
    member_count, vector_count, _, fingerprint = REGION_SPECS[state_id]
    terms = {
        r["stable_id"]: r["bound"]
        for r in source_results()[joint.TARGET_STATE_ID]["FINAL_STATE_TERMS"]
    }
    if (
        len(members) != member_count
        or len({m.counts for m in members}) != member_count
        or sum(m.represented_vector_count for m in members) != vector_count
        or catalog.region_fingerprint(members) != fingerprint
        or max(m.final_bound for m in members) != terms[state_id]
        or any(m.final_bound > m.raw_bound or m.represented_vector_count < 1 for m in members)
    ):
        raise AssertionError("complete State region identity or sealed bound recovery failed")
    return members


@cache
def represented_vectors(state_id: str) -> dict[CountVector, tuple[CountVector, ...]]:
    members = region_members(state_id)
    recovered = catalog.r17.represented_vectors(tuple(catalog.rebuild_member(m) for m in members))
    flat = [v for vectors in recovered.values() for v in vectors]
    if (
        set(recovered) != {m.counts for m in members}
        or len(flat) != REGION_SPECS[state_id][1]
        or len(set(flat)) != len(flat)
    ):
        raise AssertionError("complete represented-vector coverage failed")
    for m, row in zip(members, source_results()[state_id]["COMPLETE_REGION_MEMBERS"], strict=True):
        vectors = recovered[m.counts]
        signature = hunter.eleven.compression_signature(catalog.rebuild_member(m))
        if (
            len(vectors) != m.represented_vector_count
            or tuple(sorted(vectors)) != vectors
            or min(vectors) != m.counts
            or tuple(dense(v) for v in row["represented_vectors"]) != vectors
        ):
            raise AssertionError("immutable vector list or compression cardinality failed")
        for vector in vectors:
            rebuilt = catalog.rebuild_member(replace(m, counts=vector, represented_vector_count=1))
            if (
                len(vector) != 30
                or min(vector) < 0
                or sum(vector) != hunter.RESIDUAL_EVENT_COUNT
                or hunter.eleven.compression_signature(rebuilt) != signature
            ):
                raise AssertionError("represented-vector compression signature failed")
    return recovered


def target_vectors(state_id: str) -> frozenset[CountVector]:
    expected: set[CountVector] = set()
    if state_id == joint.TARGET_STATE_ID:
        for extra in (2, 8):
            for j in range(4):
                for t in range(5):
                    v = [0] * 30
                    v[0], v[1], v[4], v[5], v[16], v[extra] = 10, j, 3 - j, 4 - t, t, 1
                    expected.add(tuple(v))
    elif state_id == s141.TARGET_STATE_ID:
        for extra in (5, 16):
            for j in range(6):
                v = [0] * 30
                v[0], v[1], v[4], v[extra], v[25] = 11, j, 5 - j, 1, 1
                expected.add(tuple(v))
    elif state_id == s135.TARGET_STATE_ID:
        for j in range(4):
            v = [0] * 30
            v[0], v[1], v[4], v[25] = 14, j, 3 - j, 1
            expected.add(tuple(v))
        for extra in (5, 16):
            for j in range(7):
                v = [0] * 30
                v[0], v[1], v[4], v[extra], v[20] = 10, j, 6 - j, 1, 1
                expected.add(tuple(v))
    else:
        raise ValueError("unknown target State")
    if len(expected) != REGION_SPECS[state_id][2]:
        raise AssertionError("target specification cardinality failed")
    return frozenset(expected)


def target_members(state_id: str, members: tuple[LedgerMember, ...]) -> tuple[LedgerMember, ...]:
    expected = target_vectors(state_id)
    targets = tuple(m for m in members if m.counts in expected)
    if (
        len(targets) != len(expected)
        or {m.counts for m in targets} != set(expected)
        or any(m.represented_vector_count != 1 for m in targets)
    ):
        raise AssertionError("exact target member coverage failed")
    return targets


@cache
def hunter_proof(n: int) -> dict[str, Any]:
    """Full integer threshold minimum using the common immutable Hunter theorem."""

    if n not in THEOREMS:
        raise ValueError("unsupported type-0 event count")
    mass_expected, cases_expected, floor_expected = THEOREMS[n]
    if (
        hunter.RESIDUAL_EVENT_DEFINITION != RESIDUAL_EVENT_DEFINITION
        or hunter.eleven.RESIDUAL_EVENT_DEFINITION != RESIDUAL_EVENT_DEFINITION
        or hunter.type_cells(0) != (0, 0, 0, hunter.TICKET_SIZE)
        or hunter.family_pair_overlap_ceiling() != 3
    ):
        raise AssertionError("type-0 residual-event identity or overlap ceiling failed")
    rows = hunter.exact_pair_rows(((0, 0),))
    if tuple(rows) != tuple((0, 0, 0, 0, 0, k, cost) for k, cost in enumerate(PAIR_FLOORS)):
        raise AssertionError("exact residual pair costs or coverage failed")
    for row in rows:
        cells = (row[2], row[3], row[4], row[5])
        if (
            six.residual_pair_intersection(0, 0, cells) != row[6]
            or hunter.outcome_count(
                hunter.realize_pair(hunter.type_cells(0), hunter.type_cells(0), cells),
                (hunter.ANCHOR_A, hunter.ANCHOR_B),
            )
            != row[6]
        ):
            raise AssertionError("independent residual pair inclusion/exclusion failed")
    floors = hunter.pair_floors(rows)
    hunter.require_safe_pair_floors(floors, rows)
    outside = set(range(hunter.POOL_SIZE)) - (hunter.ANCHOR_A | hunter.ANCHOR_B)
    labels, incidences = len(outside), n * hunter.type_cells(0)[3]
    if labels != 40 or outside != set(hunter.CELL_LABELS[3]):
        raise AssertionError("outside-label universe failed")
    quotient, remainder = divmod(incidences, labels)
    mass = (labels - remainder) * comb(quotient, 2) + remainder * comb(quotient + 1, 2)
    if mass != hunter.balanced_collision_mass(incidences, labels) or mass != mass_expected:
        raise AssertionError("balanced collision floor failed; n=14 requires Q=48")
    smoothing_cases = 0
    for high in range(2, n + 1):
        for low in range(high - 1):
            decrease = comb(high, 2) + comb(low, 2) - comb(high - 1, 2) - comb(low + 1, 2)
            if decrease != high - low - 1 or decrease <= 0:
                raise AssertionError("balanced collision smoothing algebra failed")
            smoothing_cases += 1
    capacity = comb(n, 2)
    ranks = tuple(next(r for r in range(n) if comb(r + 1, 2) >= e) for e in range(capacity + 1))
    if hunter.verify_rank_floor_algebra(n) != capacity + 1 or any(
        hunter.rank_floor(e) != r for e, r in enumerate(ranks)
    ):
        raise AssertionError("universal forest-rank algebra failed")
    best: tuple[int, tuple[int, int, int]] | None = None
    cases, case_counts = 0, [0, 0, 0]
    for e1 in range(capacity + 1):
        for e2 in range(e1 + 1):
            for e3 in range(e2 + 1):
                if e1 + e2 + e3 < mass:
                    continue
                rho = (ranks[e1], ranks[e2], ranks[e3])
                value = (n - 1) * floors[0] + sum(
                    (floors[k + 1] - floors[k]) * rho[k] for k in range(3)
                )
                if value != hunter.tree_weight_floor(floors, rho, n):
                    raise AssertionError("nested threshold weight identity failed")
                candidate = value, (e1, e2, e3)
                best = candidate if best is None else min(best, candidate)
                cases += 1
                case_counts[2 if e3 else int(e2 > 0)] += 1
    relaxation = hunter.minimum_tree_correction(floors, mass, n)
    if (
        best != (relaxation.correction, relaxation.edge_counts)
        or cases != relaxation.census_size
        or cases != cases_expected
        or relaxation.correction != floor_expected
        or not all(case_counts)
    ):
        raise AssertionError("complete threshold integer minimization failed")
    return {
        "event_count": n,
        "type_index": 0,
        "type_cells": list(hunter.type_cells(0)),
        "residual_event_definition": RESIDUAL_EVENT_DEFINITION,
        "residual_event_size": hunter.residual_event_size(0),
        "outside_labels": sorted(outside),
        "outside_label_count": labels,
        "outside_incidences": incidences,
        "balanced_frequencies": [[quotient, labels - remainder], [quotient + 1, remainder]],
        "collision_mass_floor": mass,
        "simple_incidence_minus_labels": incidences - labels,
        "balanced_collision_proof": "Smoothing high>=low+2 reduces Q by high-low-1>0",
        "smoothing_algebra_cases": smoothing_cases,
        "collision_identity": "Q=sum_x C(d_x,2)=e1+e2+e3",
        "pair_rows": [list(r) for r in rows],
        "pair_floors": list(floors),
        "pair_overlap_ceiling": 3,
        "rank_algebra_rows": capacity + 1,
        "hunter_floor": relaxation.correction,
        "all_admissible_threshold_cases": cases,
        "admissible_case_counts": case_counts,
        "integer_minimizer": {
            "edge_counts": list(relaxation.edge_counts),
            "rank_floors": list(relaxation.rank_floors),
        },
        "nested_threshold_proof": "Descending Kruskal spans each nested G_k",
        "rank_proof": "e_k<=sum_j C(r_j+1,2)<=C(sum_j r_j+1,2); rank(G_k)>=rho(e_k)",
        "hunter_inequality": "|union R_i|<=sum_i |R_i|-sum_(ij in T) |R_i intersect R_j|",
        "pointwise_hunter_proof": "A tree induces at most k-1 edges on any k>=1 event vertices",
        "extension_rule": "Extend subset tree to eighteen events with nonnegative intersections",
        "threshold_minimization_status": "PASS_COMPLETE_EXACT_INTEGER_MINIMUM",
    }


@cache
def support_witness(vector: CountVector) -> tuple[tuple[int, ...], ...]:
    support = joint.nine.support_witness(vector)
    if not hunter.r8.validate_support_assignment(vector, support):
        raise AssertionError("legal support witness failed")
    return support


def existing_corrections(state_id: str, member: LedgerMember) -> dict[str, int]:
    """Translate the fully replayed sealed bound into the same residual credit."""

    state = catalog.rebuild_member(member)
    uncorrected = hunter.r14.joint_constant() - state.anchor_pair_s2 + state.anchor_triple_s3
    prior_rows = source_results()[state_id]["MEMBER_CERTIFICATES"]
    matches = [r for r in prior_rows if dense(r["witness_counts"]) == member.counts]
    credits = {
        "R6_PAIR": state.residual_pair_union_penalty,
        "FOREST": state.complementary_forest_floor,
        "SEALED_VALID": uncorrected - member.final_bound,
        "SEALED_CERTIFICATE": max(
            (int(r["member_certified_correction"]) for r in matches), default=0
        ),
    }
    if (
        member not in region_members(state_id)
        or min(credits.values()) < 0
        or state.applied_residual_union_penalty != max(credits["R6_PAIR"], credits["FOREST"])
        or uncorrected - state.applied_residual_union_penalty != member.raw_bound
        or hunter.combine_corrections(credits) != uncorrected - member.final_bound
    ):
        raise AssertionError("existing valid correction recovery failed")
    return credits


def certify_member(
    state_id: str, member: LedgerMember, vectors: tuple[CountVector, ...], proof: dict[str, Any]
) -> dict[str, Any]:
    if (
        member not in target_members(state_id, region_members(state_id))
        or vectors != represented_vectors(state_id)[member.counts]
        or vectors != (member.counts,)
        or proof != hunter_proof(member.counts[0])
    ):
        raise AssertionError("exact target represented-vector or proof applicability failed")
    vector = vectors[0]
    n = int(proof["event_count"])
    types = tuple(i for i, count in enumerate(vector) for _ in range(count))
    if len(types) != 18 or vector[0] != n or types[:n] != (0,) * n:
        raise AssertionError("individual type-0 residual event count failed")
    state = catalog.rebuild_member(member)
    uncorrected = hunter.r14.joint_constant() - state.anchor_pair_s2 + state.anchor_triple_s3
    residual_sum = sum(count * hunter.residual_event_size(i) for i, count in enumerate(vector))
    corrections = existing_corrections(state_id, member)
    existing = hunter.combine_corrections(corrections)
    corrections["TYPE0_HUNTER"] = int(proof["hunter_floor"])
    combined = hunter.combine_corrections(corrections)
    bound = min(member.final_bound, uncorrected - combined)
    if (
        uncorrected != hunter.anchor_union_size() + residual_sum
        or existing != uncorrected - member.final_bound
        or combined != max(corrections.values())
        or bound != min(member.final_bound, hunter.member_bound(uncorrected, combined))
        or bound >= member.final_bound
    ):
        raise AssertionError("MAX single replacement or additive-credit mutation failed")
    support = support_witness(vector)
    witness = joint.nine.shared.prior.prior.witness_analysis(vector, support, proof)
    subset = tuple(frozenset(t) for t in support[:n])
    mass = sum(comb(sum(x in t for t in subset), 2) for x in hunter.CELL_LABELS[3])
    tree = cast(tuple[tuple[int, int], ...], witness["extended_tree"])
    exact_weight = 0
    for left, right in tree:
        cells = tuple(
            len(set(support[left]) & set(support[right]) & set(c)) for c in hunter.CELL_LABELS
        )
        cost = six.residual_pair_intersection(
            types[left], types[right], cast(tuple[int, int, int, int], cells)
        )
        if cost < 0:
            raise AssertionError("negative residual edge prevents Hunter extension")
        exact_weight += cost
    if (
        any(not t <= set(proof["outside_labels"]) for t in subset)
        or mass != sum(len(a & b) for a, b in combinations(subset, 2))
        or mass != witness["collision_mass"]
        or mass < proof["collision_mass_floor"]
        or len(tree) != hunter.graph_rank(18, tree)
        or len(tree) != 17
        or exact_weight < witness["phi_tree_weight"]
        or witness["phi_tree_weight"] < proof["hunter_floor"]
    ):
        raise AssertionError("witness collision or full Hunter tree extension failed")
    row = {
        "counts": sparse(vector),
        "type0_count": vector[0],
        "event_count": n,
        "residual_event_definition": RESIDUAL_EVENT_DEFINITION,
        "selected_event_indices": list(range(n)),
        "selected_event_types": list(types[:n]),
        "anchor_union": hunter.anchor_union_size(),
        "residual_event_sum": residual_sum,
        "uncorrected_anchor_bound": uncorrected,
        "corrections": corrections,
        "prior_applied_correction": existing,
        "combined_correction": combined,
        "vector_prior_bound": member.final_bound,
        "vector_new_bound": bound,
        "support_witness": support,
        "support_sha256": digest(support),
        "witness_analysis": {**witness, "extended_tree_exact_weight": exact_weight},
    }
    return catalog.normalized(
        {
            "member_id": member_id(vector),
            "witness_counts": sparse(vector),
            "represented_vector_count": len(vectors),
            "represented_vectors": [sparse(v) for v in vectors],
            "member_prior_bound": member.final_bound,
            "member_raw_bound": member.raw_bound,
            "member_certified_correction": hunter.member_correction((combined,)),
            "member_new_bound": bound,
            "vector_certificates": [row],
            "correction_combination": CORRECTION_COMBINATION,
        }
    )


@cache
def certify_region(state_id: str) -> dict[str, Any]:
    members, vectors = region_members(state_id), represented_vectors(state_id)
    targets = target_members(state_id, members)
    records = [
        certify_member(state_id, m, vectors[m.counts], hunter_proof(m.counts[0])) for m in targets
    ]
    priors = {m.counts: m.final_bound for m in members}
    bounds = six.replaced_bounds(priors, records)
    target_counts = {m.counts for m in targets}
    remainder = tuple(m for m in members if m.counts not in target_counts)
    if (
        {v for v in priors if bounds[v] != priors[v]} != target_counts
        or len(records) != REGION_SPECS[state_id][2]
        or any(bounds[m.counts] != m.final_bound for m in remainder)
    ):
        raise AssertionError("target replacements or non-target preservation failed")
    return {
        "state_id": state_id,
        "region_sha256": catalog.region_fingerprint(members),
        "region_member_count": len(members),
        "region_vector_count": sum(len(v) for v in vectors.values()),
        "target_member_count": len(records),
        "target_vector_count": sum(r["represented_vector_count"] for r in records),
        "member_certificates": records,
        "preserved_member_count": len(remainder),
        "preserved_vector_count": sum(len(vectors[m.counts]) for m in remainder),
        "preserved_member_bounds_sha256": digest(
            tuple((m.counts, m.final_bound) for m in remainder)
        ),
        "complete_updated_bounds_sha256": digest(
            tuple((m.counts, bounds[m.counts]) for m in members)
        ),
        "complete_region_members": [
            {
                "member_id": member_id(m.counts),
                "witness_counts": sparse(m.counts),
                "represented_vector_count": len(vectors[m.counts]),
                "represented_vectors": [sparse(v) for v in vectors[m.counts]],
                "compression_signature": hunter.eleven.compression_signature(
                    catalog.rebuild_member(m)
                ),
                "raw_bound": m.raw_bound,
                "prior_bound": m.final_bound,
                "final_bound": bounds[m.counts],
            }
            for m in members
        ],
        "start_state_bound": max(priors.values()),
        "final_state_bound": max(bounds.values()),
        "final_state_member_ids": [
            member_id(v) for v, b in bounds.items() if b == max(bounds.values())
        ],
    }


def recompute_family(regions: list[dict[str, Any]]) -> dict[str, Any]:
    source = source_results()[joint.TARGET_STATE_ID]
    states = tuple((str(r["stable_id"]), int(r["bound"])) for r in source["FINAL_STATE_TERMS"])
    classified = tuple(
        (str(r["stable_id"]), int(r["bound"])) for r in source["FINAL_CLASSIFIED_TERMS"]
    )
    tail = six.sealed_tail_bound()
    replay = joint.recompute_family(int(source["SIX_MEMBER_STATE_UB"]))
    if (
        len(states) != len(dict(states))
        or len(states) != 23
        or classified != replay["classified"]
        or states != replay["states"]
        or len(classified) != source["CLASSIFIED_TERM_COUNT"]
        or digest(classified) != source["CLASSIFIED_TERMS_SHA256"]
        or tail != source["TAIL_BOUND"]
    ):
        raise AssertionError("complete State/classified/Tail source replay failed")
    start = six.tail.family_maximum(tail, states, classified)
    if start != source["FINAL_FAMILY_MAX_RECOMPUTATION"]:
        raise AssertionError("complete starting Family replay failed")
    replacements = {str(r["state_id"]): int(r["final_state_bound"]) for r in regions}
    if len(replacements) != 3 or set(replacements) != set(REGION_SPECS):
        raise AssertionError("exact three-State replacement coverage failed")
    updated = tuple((k, replacements.get(k, b)) for k, b in states)
    final = six.tail.family_maximum(tail, updated, classified)
    all_terms = (*updated, (r24.TAIL_ID, tail), *classified)
    maximum = max(b for _, b in all_terms)
    if (
        final["R3_BOUND"] != maximum
        or final["OWNER_IDS"] != sorted(k for k, b in all_terms if b == maximum)
        or any(b != dict(states)[k] for k, b in updated if k not in replacements)
    ):
        raise AssertionError("complete Family maximum or preserved State terms failed")
    return {
        "start": start,
        "final": final,
        "start_states": states,
        "states": updated,
        "classified": classified,
        "tail": tail,
    }


def build_result() -> dict[str, Any]:
    authority = verify_source_authority()
    proofs = [hunter_proof(n) for n in THEOREMS]
    regions = [certify_region(state_id) for state_id in REGION_SPECS]
    family = recompute_family(regions)
    return catalog.normalized(
        {
            "TASK_ID": TASK_ID,
            "TASK_STATUS": "SUCCESS",
            "REMAINING_TASK_MODEL": "最強模型",
            "TASK_BRANCH": TASK_BRANCH,
            "BASE_HEAD": BASE_HEAD,
            "BASE_TREE": BASE_TREE,
            "BASE_RESULT_SHA256": BASE_RESULT_SHA256,
            "SOURCE_AUTHORITY": authority,
            "SOURCE_AUTHORITY_STATUS": "PASS_IMMUTABLE_OBJECTS_EXECUTING_BYTES_AND_COMPLETE_REPLAY",
            "TYPE0_HUNTER_PROOFS": proofs,
            "BALANCED_COLLISION_STATUS": "PASS_N10_Q20_N11_Q26_N14_Q48",
            "THRESHOLD_MINIMIZATION_STATUS": "PASS_ALL_THREE_COMPLETE_INTEGER_MINIMA",
            "REGIONS": regions,
            "TARGET_MEMBER_COUNT": sum(r["target_member_count"] for r in regions),
            "TARGET_VECTOR_COUNT": sum(r["target_vector_count"] for r in regions),
            "NEW_STATE_BOUNDS": {r["state_id"]: r["final_state_bound"] for r in regions},
            "PRESERVED_REMAINDER_STATUS": "PASS_EVERY_NON_TARGET_MEMBER_AND_REPRESENTED_VECTOR",
            "CORRECTION_COMBINATION": CORRECTION_COMBINATION,
            "NO_DOUBLE_COUNT_STATUS": "PASS_MAX_SINGLE_REPLACEMENT",
            "WITNESS_SOUNDNESS_STATUS": "PASS_70_LEGAL_SUPPORTS_AND_UNIVERSAL_HUNTER_PROOF",
            "START_STATE_TERMS": [{"stable_id": k, "bound": b} for k, b in family["start_states"]],
            "FINAL_STATE_TERMS": [{"stable_id": k, "bound": b} for k, b in family["states"]],
            "STATE_TERM_COUNT": len(family["states"]),
            "FULL_FAMILY_RECOMPUTATION": "PASS",
            "CLASSIFIED_TERM_COUNT": len(family["classified"]),
            "CLASSIFIED_TERMS_SHA256": digest(family["classified"]),
            "CLASSIFIED_MAX": family["final"]["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"],
            "TAIL_BOUND": family["tail"],
            "START_FAMILY_MAX_RECOMPUTATION": family["start"],
            "FINAL_FAMILY_MAX_RECOMPUTATION": family["final"],
            "START_COMPLETE_R3_UB": family["start"]["R3_BOUND"],
            "FINAL_COMPLETE_R3_UB": family["final"]["R3_BOUND"],
            "FINAL_OWNER_IDS": family["final"]["OWNER_IDS"],
            "CURRENT_INCUMBENT": r24.INCUMBENT,
            "REMAINING_GAP": int(family["final"]["R3_BOUND"]) - r24.INCUMBENT,
            "STRICT_GAIN": int(family["start"]["R3_BOUND"]) - int(family["final"]["R3_BOUND"]),
            "R7_CENSUS_REBUILD_CALLS": 0,
            "OUTCOME_ENUMERATION_USED": False,
            "NEW_HEAVY_SOLVER_STARTED": "NO",
            "PRODUCTION_MUTATION": "NONE",
            "PUSH_PR_MERGE": "NONE",
            "WORKTREE_DISPOSITION": "RETAIN",
        }
    )


def verify_result(result: dict[str, Any]) -> dict[str, Any]:
    verify_source_authority()
    if result["TYPE0_HUNTER_PROOFS"] != [hunter_proof(n) for n in THEOREMS]:
        raise AssertionError("balanced collision or threshold proof differs from replay")
    if [r["state_id"] for r in result["REGIONS"]] != list(REGION_SPECS):
        raise AssertionError("exact three-State coverage failed")
    for region in result["REGIONS"]:
        state_id = str(region["state_id"])
        targets = target_members(state_id, region_members(state_id))
        records = region["member_certificates"]
        if [r["member_id"] for r in records] != [member_id(m.counts) for m in targets]:
            raise AssertionError("exact seventy target member coverage failed")
        for record, m in zip(records, targets, strict=True):
            if (
                record["represented_vectors"]
                != [sparse(v) for v in represented_vectors(state_id)[m.counts]]
                or record["represented_vector_count"] != 1
                or len(record["vector_certificates"]) != 1
            ):
                raise AssertionError("target represented-vector coverage failed")
            row = record["vector_certificates"][0]
            if row["counts"] != sparse(m.counts) or row["type0_count"] != m.counts[0]:
                raise AssertionError("individual type-0 vector/event identity failed")
            expected = existing_corrections(state_id, m)
            expected["TYPE0_HUNTER"] = int(hunter_proof(m.counts[0])["hunter_floor"])
            state = catalog.rebuild_member(m)
            uncorrected = (
                hunter.r14.joint_constant() - state.anchor_pair_s2 + state.anchor_triple_s3
            )
            combined = max(expected.values())
            bound = min(m.final_bound, uncorrected - combined)
            if (
                row["corrections"] != expected
                or row["combined_correction"] != combined
                or row["uncorrected_anchor_bound"] != uncorrected
                or row["vector_new_bound"] != bound
                or record["member_new_bound"] != bound
            ):
                raise AssertionError("MAX single replacement or additive-credit mutation failed")
            support = tuple(tuple(int(x) for x in t) for t in row["support_witness"])
            if (
                not hunter.r8.validate_support_assignment(m.counts, support)
                or digest(support) != row["support_sha256"]
            ):
                raise AssertionError("stored legal support witness or fingerprint failed")
    replay = build_result()
    for actual, expected_region in zip(result["REGIONS"], replay["REGIONS"], strict=True):
        if actual["complete_region_members"] != expected_region["complete_region_members"]:
            raise AssertionError(
                "complete region preservation or represented-vector coverage failed"
            )
    if result != replay:
        raise AssertionError("stored result differs from complete exact Family replay")
    return {
        "status": "PASS",
        "members": 70,
        "vectors": 70,
        "region_members": 2863,
        "region_vectors": 3089,
    }


def encode(result: dict[str, Any]) -> str:
    return hunter.encode(result)


def verify_stored_result() -> dict[str, Any]:
    stored = RESULT_PATH.read_bytes()
    status = verify_result(cast(dict[str, Any], json.loads(stored)))
    if stored != encode(build_result()).encode():
        raise AssertionError("stored result bytes differ from byte-exact replay")
    return status


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(verify_stored_result(), sort_keys=True))
        return
    result = build_result()
    if args.write:
        RESULT_PATH.write_text(encode(result), encoding="utf-8")
    keys = (
        "TASK_STATUS",
        "NEW_STATE_BOUNDS",
        "FINAL_COMPLETE_R3_UB",
        "FINAL_OWNER_IDS",
        "STRICT_GAIN",
        "REMAINING_GAP",
    )
    print(json.dumps({k: result[k] for k in keys}, sort_keys=True))


if __name__ == "__main__":
    main()
