"""Complete 47-member F/G Hunter certificate for State 13169800.

Replay the immutable 989-member / 1072-vector region, preserve all carried
certificates, and certify exactly F(t,k,j), j in {6,9}, and G(t). Integer
threshold enumeration proves universal ten/twelve-event floors, independent
of concrete support witnesses. Combine valid corrections by MAX and subtract
once. Replay all 23 State terms and retain the standalone complete R3 bound.
No solver, census, heavy refinement or official-outcome enumeration is used.
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
from typing import Any, cast

from lottolab.research import b649_k20_r3_state_13169800_four_band_ten_event_hunter_r1 as prior

hunter, catalog, six, r24, region = prior.hunter, prior.catalog, prior.six, prior.r24, prior.region
LedgerMember = catalog.LedgerMember
type CountVector = tuple[int, ...]
dense, sparse, digest, member_id = prior.dense, prior.sparse, prior.digest, prior.member_id
TASK_ID = "B649_K20_R3_STATE_13169800_FORTY_SEVEN_SHARED_HUNTER_CERTIFICATE_R1"
TASK_BRANCH = "codex/b649-k20-r3-state-13169800-forty-seven-shared-hunter-certificate-r1"
BASE_HEAD = "5cfacd03b1026274577f6647083684b53b00bcae"
BASE_TREE = "fd5a8b3cf7aafe4617afad620ccfce196ee9b8ca"
BASE_RESULT_SHA256 = "f059ab046a75a3c7790ae979a84ff323d44a8e7e605ee1a6042e206b6d34c06a"
BASE_MODULE_RELATIVE = (
    "src/lottolab/research/b649_k20_r3_state_13169800_four_band_ten_event_hunter_r1.py"
)
BASE_MODULE_SHA256 = "4305d1b22d63dd93c5e3267ef420751457cfe087ea052204aee40a7f1dd5e736"
TARGET_STATE_ID = "state:s2-13169800-s3-789320"
REGION_SHA256 = "c183f8d2f93d3a695fcae3e2d2d280d40ffb1de3527eb43e61ce5321569dcde1"
REGION_MEMBER_COUNT, REGION_VECTOR_COUNT = 989, 1072
PAIR_COSTS = (107800, 574000, 1691620, 3451651)
# n: (outside incidences, collision floor, exact threshold cases, Hunter floor)
THEOREM = {10: (60, 20, 16982, 3767400), 12: (72, 32, 51257, 4915400)}
EXPECTED_BOUNDS_DIGEST = "9a32444dcdde9badb8896e23a4ea2c466757818d8e61d7892cad2f3a7551987d"
RESIDUAL_EVENT_DEFINITION = prior.RESIDUAL_EVENT_DEFINITION
CORRECTION_COMBINATION = "MAX(EXISTING_VALID_CORRECTIONS, NEW_APPLICABLE_HUNTER)"
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_RELATIVE = (
    six.RESULTS + "b649-k20-r3-state-13169800-forty-seven-shared-hunter-certificate-r1-result.json"
)
RESULT_PATH = REPO_ROOT / RESULT_RELATIVE
UPSTREAM_SHA256 = {
    **prior.UPSTREAM_SHA256,
    prior.RESULT_RELATIVE: BASE_RESULT_SHA256,
    BASE_MODULE_RELATIVE: BASE_MODULE_SHA256,
}


def json_digest(payload: object) -> str:
    """Canonical digest for certificates containing Unicode residual-set notation."""

    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def verify_upstream_fingerprints() -> dict[str, str]:
    """Recheck executing sources and sealed results even with warm caches."""

    observed = {p: sha256((REPO_ROOT / p).read_bytes()).hexdigest() for p in UPSTREAM_SHA256}
    if observed != UPSTREAM_SHA256:
        raise AssertionError("immutable source fingerprint mismatch")
    return observed


def verify_base_authority() -> dict[str, str]:
    prefix = ["git", "-C", str(REPO_ROOT)]
    head = subprocess.check_output([*prefix, "rev-parse", BASE_HEAD], text=True).strip()
    tree = subprocess.check_output([*prefix, "rev-parse", f"{BASE_HEAD}^{{tree}}"], text=True)
    if head != BASE_HEAD or tree.strip() != BASE_TREE:
        raise AssertionError("immutable base HEAD/TREE identity failed")
    for path, expected in (
        (prior.RESULT_RELATIVE, BASE_RESULT_SHA256),
        (BASE_MODULE_RELATIVE, BASE_MODULE_SHA256),
    ):
        blob = subprocess.check_output([*prefix, "show", f"{BASE_HEAD}:{path}"])
        if sha256(blob).hexdigest() != expected:
            raise AssertionError("immutable base certificate object failed")
    return {"HEAD": head, "TREE": tree.strip(), "RESULT_SHA256": BASE_RESULT_SHA256}


@cache
def source_authority() -> dict[str, Any]:
    verify_base_authority()
    verify_upstream_fingerprints()
    stored = cast(dict[str, Any], json.loads(prior.RESULT_PATH.read_text()))
    if (
        stored["TASK_ID"] != prior.TASK_ID
        or stored["STATE_ID"] != TARGET_STATE_ID
        or stored["REGION_SHA256"] != REGION_SHA256
        or len(stored["MEMBER_CERTIFICATES"]) != 40
        or prior.verify_stored_result()["status"] != "PASS"
    ):
        raise AssertionError("immutable predecessor identity or byte replay failed")
    return stored


@cache
def region_members() -> tuple[LedgerMember, ...]:
    """Adopt only the bounds reproduced from the immutable complete region."""

    source = source_authority()
    members = prior.region_members()
    bounds = six.replaced_bounds(
        {m.counts: m.final_bound for m in members}, source["MEMBER_CERTIFICATES"]
    )
    replay = tuple(replace(m, final_bound=bounds[m.counts]) for m in members)
    rows = source["COMPLETE_REGION_MEMBERS"]
    if (
        len(replay) != REGION_MEMBER_COUNT
        or len({m.counts for m in replay}) != REGION_MEMBER_COUNT
        or sum(m.represented_vector_count for m in replay) != REGION_VECTOR_COUNT
        or catalog.region_fingerprint(replay) != REGION_SHA256
        or len(rows) != len(replay)
        or max(bounds.values()) != source["FINAL_TARGET_STATE_UB"]
        or any(
            row["member_id"] != member_id(m.counts)
            or dense(row["witness_counts"]) != m.counts
            or row["represented_vector_count"] != m.represented_vector_count
            or row["raw_bound"] != m.raw_bound
            or row["final_bound"] != m.final_bound
            or m.final_bound > m.raw_bound
            for m, row in zip(replay, rows, strict=True)
        )
        or digest(tuple((m.counts, m.final_bound) for m in replay))
        != source["COMPLETE_UPDATED_BOUNDS_SHA256"]
    ):
        raise AssertionError("complete target region or current bound replay failed")
    return replay


@cache
def represented_vectors() -> dict[CountVector, tuple[CountVector, ...]]:
    """Recover every vector at the immutable catalog's exact losses and signatures."""

    members = region_members()
    recovered = catalog.r17.represented_vectors(tuple(catalog.rebuild_member(m) for m in members))
    flat = [v for vectors in recovered.values() for v in vectors]
    if (
        set(recovered) != {m.counts for m in members}
        or len(flat) != REGION_VECTOR_COUNT
        or len(set(flat)) != REGION_VECTOR_COUNT
        or any(len(recovered[m.counts]) != m.represented_vector_count for m in members)
    ):
        raise AssertionError("complete represented-vector coverage failed")
    for member in members:
        vectors = recovered[member.counts]
        if tuple(sorted(vectors)) != vectors or min(vectors) != member.counts:
            raise AssertionError("represented-vector canonical identity failed")
        signature = hunter.eleven.compression_signature(catalog.rebuild_member(member))
        for vector in vectors:
            rebuilt = catalog.rebuild_member(
                replace(member, counts=vector, represented_vector_count=1)
            )
            if (
                hunter.eleven.compression_signature(rebuilt) != signature
                or len(vector) != 30
                or sum(vector) != hunter.RESIDUAL_EVENT_COUNT
                or min(vector) < 0
            ):
                raise AssertionError("represented-vector compression signature failed")
    if recovered != region.region_vectors() or any(
        tuple(dense(v["counts"]) for v in row["vector_certificates"])
        != recovered[dense(row["witness_counts"])]
        for row in prior.region_authority()["MEMBER_CERTIFICATES"]
    ):
        raise AssertionError("represented-vector source replay failed")
    for member, row in zip(members, source_authority()["COMPLETE_REGION_MEMBERS"], strict=True):
        if (
            tuple(dense(v) for v in row["represented_vectors"]) != recovered[member.counts]
            or catalog.normalized(
                hunter.eleven.compression_signature(catalog.rebuild_member(member))
            )
            != row["compression_signature"]
        ):
            raise AssertionError("immutable complete compression coverage failed")
    return recovered


def target_families(
    members: tuple[LedgerMember, ...],
) -> dict[str, tuple[LedgerMember, ...]]:
    """Recover catalog members first; parameter formulas only check identity."""

    expected_f: set[CountVector] = set()
    expected_g: set[CountVector] = set()
    for t in range(4):
        for k in range(5):
            for j in (6, 9):
                vector = [0] * 30
                vector[0], vector[1], vector[4] = 10, k, 4 - k
                vector[5], vector[16], vector[j] = 3 - t, t, 1
                expected_f.add(tuple(vector))
    for t in range(7):
        vector = [0] * 30
        vector[0], vector[5], vector[16] = 12, 6 - t, t
        expected_g.add(tuple(vector))
    families = {
        "F": tuple(m for m in members if m.counts in expected_f),
        "G": tuple(m for m in members if m.counts in expected_g),
    }
    if (
        len(families["F"]) != 40
        or len(families["G"]) != 7
        or {m.counts for m in families["F"]} != expected_f
        or {m.counts for m in families["G"]} != expected_g
        or expected_f & expected_g
        or any(m.represented_vector_count != 1 for rows in families.values() for m in rows)
    ):
        raise AssertionError("exact F/G 47-member/47-vector identity or coverage failed")
    return families


@cache
def hunter_proof(event_count: int) -> dict[str, Any]:
    """Full integer minimum over C(n,2) >= e1 >= e2 >= e3 >= 0, sum e >= Q.

    For each outcome in k events, a tree induces at most k-1 edges. Summation
    proves Hunter's inequality for residual events. Descending Kruskal retains
    a spanning forest of every nested G_k={ij: overlap>=k}. Component ranks r_j
    imply e_k <= sum C(r_j+1,2) <= C(sum r_j+1,2), so rank(G_k)>=rho(e_k).
    Balancing outside frequencies minimizes sum_x C(d_x,2); overlap<=3 gives
    Q=e1+e2+e3. Enumerate every feasible threshold triple independently of the
    donor minimizer. The floor is the exact minimum of this relaxation, never
    the weaker three-case shortcut. Nonnegative edges extend the subset tree
    to all eighteen residual events without claiming additional correction.
    """

    if event_count not in THEOREM:
        raise AssertionError("unsupported Hunter event count")
    expected_incidences, expected_mass, expected_cases, expected_floor = THEOREM[event_count]
    if (
        hunter.RESIDUAL_EVENT_DEFINITION != RESIDUAL_EVENT_DEFINITION
        or hunter.eleven.RESIDUAL_EVENT_DEFINITION != RESIDUAL_EVENT_DEFINITION
        or hunter.type_cells(0) != (0, 0, 0, hunter.TICKET_SIZE)
    ):
        raise AssertionError("source residual-event definition or type-0 identity failed")
    rows = hunter.exact_pair_rows(((0, 0),))
    ceiling = hunter.family_pair_overlap_ceiling()
    if (
        ceiling != 3
        or len(rows) != ceiling + 1
        or {r[2:6] for r in rows} != {(0, 0, 0, k) for k in range(ceiling + 1)}
    ):
        raise AssertionError("exact type-0 pair row coverage failed")
    for row in rows:
        cells = (row[2], row[3], row[4], row[5])
        if (
            row[:2] != (0, 0)
            or six.residual_pair_intersection(0, 0, cells) != row[6]
            or hunter.outcome_count(
                hunter.realize_pair(hunter.type_cells(0), hunter.type_cells(0), cells),
                (hunter.ANCHOR_A, hunter.ANCHOR_B),
            )
            != row[6]
        ):
            raise AssertionError("exact residual pair inclusion/exclusion failed")
    floors = hunter.pair_floors(rows)
    hunter.require_safe_pair_floors(floors, rows)
    if tuple(floors) != PAIR_COSTS:
        raise AssertionError("exact type-0 pair costs failed")
    outside = set(range(hunter.POOL_SIZE)) - set(hunter.ANCHOR_A | hunter.ANCHOR_B)
    incidences, labels = event_count * hunter.type_cells(0)[3], len(outside)
    if outside != set(hunter.CELL_LABELS[3]) or labels != 40:
        raise AssertionError("outside universe differs from the anchor complement")
    quotient, remainder = divmod(incidences, labels)
    mass = hunter.balanced_collision_mass(incidences, labels)
    if (
        mass != (labels - remainder) * comb(quotient, 2) + remainder * comb(quotient + 1, 2)
        or mass != incidences - labels
        or mass != expected_mass
        or incidences != expected_incidences
    ):
        raise AssertionError("balanced outside collision floor failed")
    capacity = comb(event_count, 2)
    ranks = tuple(
        next(r for r in range(event_count) if comb(r + 1, 2) >= e) for e in range(capacity + 1)
    )
    rank_rows = hunter.verify_rank_floor_algebra(event_count)
    if rank_rows != capacity + 1 or any(hunter.rank_floor(e) != r for e, r in enumerate(ranks)):
        raise AssertionError("independent least forest-rank identity failed")
    best: tuple[int, tuple[int, int, int]] | None = None
    cases = 0
    case_counts = [0, 0, 0]
    for e1 in range(capacity + 1):
        for e2 in range(e1 + 1):
            for e3 in range(e2 + 1):
                if e1 + e2 + e3 < mass:
                    continue
                rho = tuple(ranks[e] for e in (e1, e2, e3))
                value = (event_count - 1) * floors[0] + sum(
                    (floors[k + 1] - floors[k]) * rho[k] for k in range(ceiling)
                )
                if value != hunter.tree_weight_floor(floors, rho, event_count):
                    raise AssertionError("independent nested-threshold weight identity failed")
                candidate = (value, (e1, e2, e3))
                if best is None or candidate < best:
                    best = candidate
                cases += 1
                case_counts[2 if e3 else int(e2 > 0)] += 1
    relaxation = hunter.minimum_tree_correction(floors, mass, event_count)
    edge_counts = cast(tuple[int, int, int], relaxation.edge_counts)
    if (
        best != (relaxation.correction, edge_counts)
        or relaxation.correction != expected_floor
        or cases != expected_cases
        or cases != relaxation.census_size
        or tuple(ranks[e] for e in edge_counts) != relaxation.rank_floors
        or sum(case_counts) != cases
        or not all(case_counts)
    ):
        raise AssertionError("complete exact threshold integer minimization failed")
    return {
        "event_count": event_count,
        "type_index": 0,
        "type_cells": list(hunter.type_cells(0)),
        "residual_event_definition": RESIDUAL_EVENT_DEFINITION,
        "residual_event_size": hunter.residual_event_size(0),
        "outside_labels": sorted(outside),
        "outside_incidences": incidences,
        "outside_label_count": labels,
        "balanced_frequencies": [[quotient, labels - remainder], [quotient + 1, remainder]],
        "collision_mass_floor": mass,
        "collision_identity": "Q = sum_x C(d_x,2) = e1+e2+e3",
        "pair_rows": [list(r) for r in rows],
        "pair_floors": list(floors),
        "pair_overlap_ceiling": ceiling,
        "rank_algebra_rows": rank_rows,
        "hunter_floor": relaxation.correction,
        "all_admissible_threshold_cases": cases,
        "admissible_case_counts": case_counts,
        "admissible_threshold_status": "PASS_COMPLETE_EXACT_INTEGER_MINIMIZATION",
        "integer_minimizer": {
            "edge_counts": list(relaxation.edge_counts),
            "rank_floors": list(relaxation.rank_floors),
            "feasible_threshold_triples": relaxation.census_size,
        },
        "floor_method": "FULL_EXACT_INTEGER_MINIMIZATION",
        "nested_threshold_inequality": "(n-1)*phi0 + sum_k rank(G_k)*(phi_k-phi_(k-1))",
        "rank_inequality": "e_k <= C(rank(G_k)+1,2); rank(G_k) >= rho(e_k)",
        "hunter_inequality": "|union R_i| <= sum_i |R_i| - sum_(ij in T) |R_i intersect R_j|",
        "extension_rule": "Extend the subset tree with nonnegative residual-pair edges",
    }


@cache
def carried_vectors() -> dict[CountVector, dict[str, Any]]:
    rows = [
        v for m in prior.region_authority()["MEMBER_CERTIFICATES"] for v in m["vector_certificates"]
    ]
    recovered = {dense(v["counts"]): v for v in rows}
    if len(rows) != len(recovered) or len(rows) != REGION_VECTOR_COUNT:
        raise AssertionError("carried vector certificate coverage failed")
    for member in source_authority()["MEMBER_CERTIFICATES"]:
        for row in member["vector_certificates"]:
            vector = dense(row["counts"])
            if vector not in recovered:
                raise AssertionError("predecessor vector is outside immutable region")
            recovered[vector] = row
    return recovered


@cache
def support_witness(vector: CountVector) -> tuple[tuple[int, ...], ...]:
    support = prior.support_witness(vector)
    sealed = carried_vectors()[vector]
    if (
        catalog.normalized(support) != sealed["support_witness"]
        or digest(support) != sealed["support_sha256"]
        or not hunter.r8.validate_support_assignment(vector, support)
    ):
        raise AssertionError("existing legal support witness changed")
    return support


def certify_vector(
    member: LedgerMember, vector: CountVector, proof: dict[str, Any]
) -> dict[str, Any]:
    event_count = int(proof["event_count"])
    families = target_families(region_members())
    targets = (*families["F"], *families["G"])
    family = "F" if member in families["F"] else "G"
    expected_events = 10 if family == "F" else 12
    if (
        member not in targets
        or vector not in represented_vectors()[member.counts]
        or vector[0] != event_count
        or event_count != expected_events
        or proof != hunter_proof(expected_events)
    ):
        raise AssertionError("represented vector or F/G event-count applicability failed")
    state = catalog.rebuild_member(replace(member, counts=vector, represented_vector_count=1))
    signature = hunter.eleven.compression_signature(state)
    types = tuple(i for i, n in enumerate(vector) for _ in range(n))
    ceiling = hunter.family_pair_overlap_ceiling()
    if (
        signature != hunter.eleven.compression_signature(catalog.rebuild_member(member))
        or len(types) != hunter.RESIDUAL_EVENT_COUNT
        or types[:event_count] != (0,) * event_count
    ):
        raise AssertionError("represented vector compression signature or event identity failed")
    for index in set(types):
        s, a, b, outside = hunter.type_cells(index)
        if s + a + b + outside != hunter.TICKET_SIZE or max(s + a, s + b) > ceiling:
            raise AssertionError("residual event type violates source anchor identity")
    uncorrected = hunter.r14.joint_constant() - state.anchor_pair_s2 + state.anchor_triple_s3
    residual_sum = sum(n * hunter.residual_event_size(i) for i, n in enumerate(vector) if n)
    carried = carried_vectors()[vector]
    corrections = {str(k): int(v) for k, v in carried["corrections"].items()}
    if (
        carried["uncorrected_anchor_bound"] != uncorrected
        or carried["vector_new_bound"] != member.final_bound
        or carried["combined_correction"] != max(corrections.values())
        or corrections["R6_PAIR"] != state.residual_pair_union_penalty
        or corrections["FOREST"] != state.complementary_forest_floor
    ):
        raise AssertionError("existing valid vector correction replay failed")
    # Keep every sealed correction, including nine/eleven-event and R14 credit.
    corrections["NEW_HUNTER"] = max(corrections.get("NEW_HUNTER", 0), int(proof["hunter_floor"]))
    existing = hunter.combine_corrections(
        {k: v for k, v in corrections.items() if k != "NEW_HUNTER"}
    )
    combined = hunter.combine_corrections(corrections)
    bound = hunter.member_bound(uncorrected, combined)
    if (
        hunter.anchor_union_size() + residual_sum != uncorrected
        or state.applied_residual_union_penalty
        != max(corrections["R6_PAIR"], corrections["FOREST"])
        or uncorrected - state.applied_residual_union_penalty != member.raw_bound
        or existing != uncorrected - member.final_bound
        or combined != max(corrections.values())
        or corrections["NEW_HUNTER"] <= existing
        or bound != uncorrected - combined
        or bound >= member.final_bound
    ):
        raise AssertionError("event arithmetic or max single correction replacement failed")
    support = support_witness(vector)
    witness = region.prior.prior.witness_analysis(vector, support, proof)
    subset = tuple(frozenset(t) for t in support[:event_count])
    mass = sum(comb(sum(x in t for t in subset), 2) for x in hunter.CELL_LABELS[3])
    full_weight = 0
    tree = cast(tuple[tuple[int, int], ...], witness["extended_tree"])
    for left, right in tree:
        cells = tuple(
            len(set(support[left]) & set(support[right]) & set(c)) for c in hunter.CELL_LABELS
        )
        cost = six.residual_pair_intersection(
            types[left], types[right], cast(tuple[int, int, int, int], cells)
        )
        if cost < 0:
            raise AssertionError("tree extension has a negative residual edge")
        full_weight += cost
    if (
        not hunter.r8.validate_support_assignment(vector, support)
        or any(not t <= set(hunter.CELL_LABELS[3]) for t in subset)
        or mass != sum(len(a & b) for a, b in combinations(subset, 2))
        or mass != witness["collision_mass"]
        or mass < proof["collision_mass_floor"]
        or full_weight < witness["phi_tree_weight"]
        or witness["phi_tree_weight"] < combined
    ):
        raise AssertionError("support collision or full Hunter tree extension failed")
    return {
        "family": family,
        "vector_id": member_id(vector),
        "counts": sparse(vector),
        "compression_signature": signature,
        "residual_event_definition": RESIDUAL_EVENT_DEFINITION,
        "type0_count": vector[0],
        "event_count": event_count,
        "applicability_status": "PASS",
        "selected_event_indices": list(range(event_count)),
        "selected_event_types": list(types[:event_count]),
        "outside_incidences": event_count * hunter.type_cells(0)[3],
        "collision_mass_floor": proof["collision_mass_floor"],
        "pair_overlap_ceiling": ceiling,
        "anchor_union": hunter.anchor_union_size(),
        "residual_event_sum": residual_sum,
        "uncorrected_anchor_bound": uncorrected,
        "corrections": corrections,
        "prior_applied_correction": existing,
        "combined_correction": combined,
        "vector_new_bound": bound,
        "support_witness": support,
        "support_sha256": digest(support),
        "witness_analysis": {**witness, "extended_tree_exact_weight": full_weight},
    }


def certify_member(
    member: LedgerMember, vectors: tuple[CountVector, ...], proof: dict[str, Any]
) -> dict[str, Any]:
    if (
        vectors != represented_vectors()[member.counts]
        or len(vectors) != member.represented_vector_count
    ):
        raise AssertionError("exact represented-vector member coverage failed")
    rows = [certify_vector(member, v, proof) for v in vectors]
    correction = hunter.member_correction(tuple(int(r["combined_correction"]) for r in rows))
    bound = max(int(r["vector_new_bound"]) for r in rows)
    if (
        correction != min(r["combined_correction"] for r in rows)
        or len({r["uncorrected_anchor_bound"] for r in rows}) != 1
        or bound != hunter.member_bound(int(rows[0]["uncorrected_anchor_bound"]), correction)
    ):
        raise AssertionError("compressed member did not use its weakest vector correction")
    return catalog.normalized(
        {
            "family": rows[0]["family"],
            "member_id": member_id(member.counts),
            "witness_counts": sparse(member.counts),
            "represented_vector_count": len(vectors),
            "represented_vectors": [sparse(v) for v in vectors],
            "compression_signature": hunter.eleven.compression_signature(
                catalog.rebuild_member(member)
            ),
            "vector_certificates": rows,
            "member_prior_bound": member.final_bound,
            "member_raw_bound": member.raw_bound,
            "member_certified_correction": correction,
            "member_new_bound": bound,
            "correction_combination": CORRECTION_COMBINATION,
        }
    )


def recompute_family(state_bound: int) -> dict[str, Any]:
    authority = source_authority()
    terms = tuple((str(r["stable_id"]), int(r["bound"])) for r in authority["FINAL_STATE_TERMS"])
    classified, tail = six.classified_terms(), six.sealed_tail_bound()
    aggregate = [{"stable_id": k, "bound": b} for k, b in classified if k == r24.AGGREGATE_ID]
    start = six.tail.family_maximum(tail, terms, classified)
    if (
        len(terms) != 23
        or len(dict(terms)) != 23
        or TARGET_STATE_ID not in dict(terms)
        or len(classified) != authority["CLASSIFIED_TERM_COUNT"]
        or digest(classified) != authority["CLASSIFIED_TERMS_SHA256"]
        or aggregate != authority["CLASSIFIED_AGGREGATE"]
        or tail != authority["TAIL_BOUND"]
        or start != authority["FINAL_FAMILY_MAX_RECOMPUTATION"]
    ):
        raise AssertionError("complete 23-State, classified aggregate or Tail source replay failed")
    replaced = tuple((k, state_bound if k == TARGET_STATE_ID else b) for k, b in terms)
    final = six.tail.family_maximum(tail, replaced, classified)
    all_terms = (*replaced, (r24.TAIL_ID, tail), *classified)
    maximum = max(b for _, b in all_terms)
    owners = sorted(k for k, b in all_terms if b == maximum)
    if (
        final["STATE_MAX_BOUND"] != max(b for _, b in replaced)
        or final["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"] != max(b for _, b in classified)
        or final["R3_BOUND"] != maximum
        or final["OWNER_IDS"] != owners
    ):
        raise AssertionError("independent full Family maximum or owner recomputation failed")
    return {
        "start": start,
        "final": final,
        "start_terms": terms,
        "terms": replaced,
        "tail_bound": tail,
        "classified_count": len(classified),
        "classified_sha256": digest(classified),
        "aggregate": aggregate,
    }


def build_result() -> dict[str, Any]:
    fingerprints, identity = verify_upstream_fingerprints(), verify_base_authority()
    source = source_authority()
    members, vectors = region_members(), represented_vectors()
    families = target_families(members)
    proofs = {"F": hunter_proof(10), "G": hunter_proof(12)}
    records = [
        certify_member(m, vectors[m.counts], proofs[key])
        for key, rows in families.items()
        for m in rows
    ]
    targets = {m.counts for rows in families.values() for m in rows}
    priors = {m.counts: m.final_bound for m in members}
    bounds = six.replaced_bounds(priors, records)
    remainder = tuple(m for m in members if m.counts not in targets)
    target_max = max(bounds[v] for v in targets)
    remainder_max = max(bounds[m.counts] for m in remainder)
    state_bound = max(bounds.values())
    bounds_digest = digest(tuple((m.counts, bounds[m.counts]) for m in members))
    if (
        len(records) != 47
        or sum(r["represented_vector_count"] for r in records) != 47
        or {v for v in priors if bounds[v] != priors[v]} != targets
        or len(remainder) != 942
        or sum(len(vectors[m.counts]) for m in remainder) != 1025
        or any(bounds[m.counts] != m.final_bound for m in remainder)
        or target_max != 355142998
        or remainder_max != 355368426
        or state_bound != max(target_max, remainder_max)
        or state_bound != 355368426
        or bounds_digest != EXPECTED_BOUNDS_DIGEST
    ):
        raise AssertionError(
            "complete 47-target State maximum, remainder or source-encoded digest failed"
        )
    family = recompute_family(state_bound)
    if (
        max(priors.values()) != dict(family["start_terms"])[TARGET_STATE_ID]
        or family["start"]["R3_BOUND"] != 355497359
        or family["final"]["R3_BOUND"] != 355497359
        or any(
            b != dict(family["start_terms"])[k] for k, b in family["terms"] if k != TARGET_STATE_ID
        )
    ):
        raise AssertionError("standalone Family accounting or untouched State changed")
    previous = {
        "NINE_EVENT": prior.region_authority()["MEMBER_CERTIFICATES"],
        "ELEVEN_EVENT": prior.region.source_authority()["MEMBER_CERTIFICATES"],
        "TEN_EVENT": source["MEMBER_CERTIFICATES"],
    }
    if len(previous["NINE_EVENT"]) != 989 or len(previous["ELEVEN_EVENT"]) != 7:
        raise AssertionError("previous nine/eleven-event certificate coverage failed")
    return catalog.normalized(
        {
            "TASK_ID": TASK_ID,
            "TASK_STATUS": "SUCCESS",
            "REMAINING_TASK_MODEL": "最強模型",
            "TASK_BRANCH": TASK_BRANCH,
            "BASE_HEAD": BASE_HEAD,
            "BASE_TREE": BASE_TREE,
            "BASE_RESULT_SHA256": BASE_RESULT_SHA256,
            "BASE_MODULE_SHA256": BASE_MODULE_SHA256,
            "IMMUTABLE_BASE_VERIFICATION": identity,
            "SOURCE_AUTHORITY_STATUS": "PASS_IMMUTABLE_OBJECTS_FINGERPRINTS_AND_BYTE_REPLAY",
            "UPSTREAM_FINGERPRINTS_SHA256": fingerprints,
            "STATE_ID": TARGET_STATE_ID,
            "REGION_SHA256": REGION_SHA256,
            "REGION_IDENTITY": catalog.region_fingerprint(members),
            "REGION_COMPRESSED_MEMBER_COUNT": len(members),
            "REGION_REPRESENTED_VECTOR_COUNT": sum(len(v) for v in vectors.values()),
            "REGION_COVERAGE_STATUS": "PASS_989_MEMBERS_1072_DISTINCT_VECTORS_REPLAYED",
            "ALL_REPRESENTED_VECTORS_SHA256": digest(
                tuple((m.counts, vectors[m.counts]) for m in members)
            ),
            "FAMILY_F_MEMBER_COUNT": len(families["F"]),
            "FAMILY_G_MEMBER_COUNT": len(families["G"]),
            "TARGET_MEMBER_COUNT": len(records),
            "TARGET_VECTOR_COUNT": sum(r["represented_vector_count"] for r in records),
            "FAMILY_MEMBER_IDS": {
                k: [member_id(m.counts) for m in rows] for k, rows in families.items()
            },
            "REPRESENTED_VECTOR_COVERAGE": "PASS_47_TARGET_AND_1072_REGION_VECTORS",
            "TEN_EVENT_PROOF": proofs["F"],
            "TWELVE_EVENT_PROOF": proofs["G"],
            "TEN_EVENT_FLOOR": proofs["F"]["hunter_floor"],
            "TWELVE_EVENT_FLOOR": proofs["G"]["hunter_floor"],
            "THRESHOLD_PROOF_STATUS": "PASS_COMPLETE_16982_AND_51257_TRIPLES",
            "TEN_EVENT_APPLICABILITY_STATUS": "PASS_ALL_40_F_VECTORS",
            "TWELVE_EVENT_APPLICABILITY_STATUS": "PASS_ALL_7_G_VECTORS",
            "EXACT_PAIR_COST_STATUS": "PASS_FOUR_RESIDUAL_PAIR_COSTS",
            "MEMBER_CERTIFICATES": records,
            "PREVIOUS_CERTIFICATES_PRESERVED": "PASS_NINE_ELEVEN_AND_PRIOR_TEN_EVENT_CERTIFICATES",
            "PREVIOUS_CERTIFICATE_COUNTS": {k: len(rows) for k, rows in previous.items()},
            "PREVIOUS_CERTIFICATES_SHA256": {k: json_digest(rows) for k, rows in previous.items()},
            "PREDECESSOR_MEMBER_CERTIFICATES": source["MEMBER_CERTIFICATES"],
            "PREDECESSOR_REGION_BOUNDS_SHA256": source["COMPLETE_UPDATED_BOUNDS_SHA256"],
            "ALL_CARRIED_CERTIFICATES_SHA256": {
                path: value for path, value in fingerprints.items() if path.endswith(".json")
            },
            "PRESERVED_MEMBER_COUNT": len(remainder),
            "PRESERVED_VECTOR_COUNT": sum(len(vectors[m.counts]) for m in remainder),
            "PRESERVED_REMAINDER_MAX": remainder_max,
            "PRESERVED_MEMBER_BOUNDS_SHA256": digest(
                tuple(
                    (m.counts, m.represented_vector_count, m.raw_bound, bounds[m.counts])
                    for m in remainder
                )
            ),
            "COMPLETE_UPDATED_BOUNDS_SHA256": bounds_digest,
            "COMPLETE_REGION_MEMBERS": [
                {
                    "member_id": member_id(m.counts),
                    "witness_counts": sparse(m.counts),
                    "represented_vector_count": len(vectors[m.counts]),
                    "represented_vectors": [sparse(v) for v in vectors[m.counts]],
                    "compression_signature": hunter.eleven.compression_signature(
                        catalog.rebuild_member(m)
                    ),
                    "raw_bound": m.raw_bound,
                    "prior_bound": priors[m.counts],
                    "final_bound": bounds[m.counts],
                }
                for m in members
            ],
            "START_STATE_BOUND": max(priors.values()),
            "TARGET_NEW_MEMBER_MAX": target_max,
            "FINAL_TARGET_STATE_BOUND": state_bound,
            "FINAL_TARGET_STATE_UB": state_bound,
            "FINAL_STATE_MEMBER_IDS": [member_id(v) for v, b in bounds.items() if b == state_bound],
            "START_STATE_TERMS": [{"stable_id": k, "bound": b} for k, b in family["start_terms"]],
            "FINAL_STATE_TERMS": [{"stable_id": k, "bound": b} for k, b in family["terms"]],
            "STATE_TERM_COUNT": len(family["terms"]),
            "FULL_23_STATE_RECOMPUTATION": "PASS",
            "TAIL_BOUND": family["tail_bound"],
            "CLASSIFIED_TERM_COUNT": family["classified_count"],
            "CLASSIFIED_TERMS_SHA256": family["classified_sha256"],
            "CLASSIFIED_AGGREGATE": family["aggregate"],
            "CLASSIFIED_MAX": family["final"]["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"],
            "START_FAMILY_MAX_RECOMPUTATION": family["start"],
            "FINAL_FAMILY_MAX_RECOMPUTATION": family["final"],
            "START_COMPLETE_R3_UB": family["start"]["R3_BOUND"],
            "FINAL_STANDALONE_COMPLETE_R3_UB": family["final"]["R3_BOUND"],
            "FINAL_COMPLETE_R3_UB": family["final"]["R3_BOUND"],
            "FINAL_OWNER_IDS": family["final"]["OWNER_IDS"],
            "CURRENT_INCUMBENT": r24.INCUMBENT,
            "REMAINING_GAP": int(family["final"]["R3_BOUND"]) - r24.INCUMBENT,
            "CORRECTION_COMBINATION": CORRECTION_COMBINATION,
            "NON_DUPLICATE_CORRECTION_STATUS": "PASS_MAX_SINGLE_REPLACEMENT",
            "DUPLICATE_CORRECTIONS": sum(
                row["uncorrected_anchor_bound"] - row["vector_new_bound"]
                != max(row["corrections"].values())
                for r in records
                for row in r["vector_certificates"]
            ),
            "WITNESS_SOUNDNESS_STATUS": "PASS_47_PRESERVED_LEGAL_SUPPORTS_AND_FULL_TREE_EXTENSIONS",
            "RECORDED_WITNESSES_SHA256": digest(
                tuple(
                    (row["counts"], row["support_witness"])
                    for r in records
                    for row in r["vector_certificates"]
                )
            ),
            "R7_CENSUS_REBUILD_CALLS": 0,
            "OUTCOME_ENUMERATION_USED": False,
            "NEW_HEAVY_SOLVER_STARTED": "NO",
            "PRODUCTION_MUTATION": "NONE",
            "PUSH_PR_MERGE": "NONE",
            "WORKTREE_DISPOSITION": "RETAIN",
        }
    )


def verify_result(result: dict[str, Any]) -> dict[str, Any]:
    verify_upstream_fingerprints()
    for member in result["MEMBER_CERTIFICATES"]:
        for row in member["vector_certificates"]:
            vector = dense(row["counts"])
            support = tuple(tuple(int(x) for x in t) for t in row["support_witness"])
            if (
                not hunter.r8.validate_support_assignment(vector, support)
                or digest(support) != row["support_sha256"]
            ):
                raise AssertionError("stored support witness or fingerprint is invalid")
    if result != build_result():
        raise AssertionError("stored certificate differs from complete exact replay")
    return {
        "status": "PASS",
        "members": 47,
        "vectors": 47,
        "region_members": REGION_MEMBER_COUNT,
        "region_vectors": REGION_VECTOR_COUNT,
    }


def encode(result: dict[str, Any]) -> str:
    return hunter.encode(result)


def verify_stored_result() -> dict[str, Any]:
    stored = RESULT_PATH.read_bytes()
    status = verify_result(cast(dict[str, Any], json.loads(stored)))
    if stored != encode(build_result()).encode():
        raise AssertionError("stored result bytes differ from encoded replay")
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
        "FAMILY_F_MEMBER_COUNT",
        "FAMILY_G_MEMBER_COUNT",
        "TEN_EVENT_FLOOR",
        "TWELVE_EVENT_FLOOR",
        "TARGET_NEW_MEMBER_MAX",
        "PRESERVED_REMAINDER_MAX",
        "FINAL_TARGET_STATE_UB",
        "FINAL_STANDALONE_COMPLETE_R3_UB",
        "COMPLETE_UPDATED_BOUNDS_SHA256",
    )
    print(json.dumps({k: result[k] for k in keys}, sort_keys=True))


if __name__ == "__main__":
    main()
