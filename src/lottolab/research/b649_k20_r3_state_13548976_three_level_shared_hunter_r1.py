"""Three shared Hunter certificates for State s2-13548976-s3-951748.

Recover the immutable 1427-member/1543-vector region and compression signatures.
Certify only three highest levels (21 members/21 vectors), using the full
nested-threshold integer relaxation for nine or thirteen type-0 residual events.
Replace one correction by max, preserve all other bounds and the predecessor's
fourteen ten-event certificates, and recompute every State, classified term and
Tail. No census, heavy solver or full outcome enumeration runs.
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

from lottolab.research import b649_k20_r3_state_14122976_two_band_ten_event_hunter_r1 as prior

hunter, catalog, six, r24 = prior.hunter, prior.catalog, prior.six, prior.r24
region = prior.prior.prior
LedgerMember = catalog.LedgerMember
type CountVector = tuple[int, ...]
dense, sparse, digest, member_id = prior.dense, prior.sparse, prior.digest, prior.member_id
TASK_ID = "B649_K20_R3_STATE_13548976_THREE_LEVEL_SHARED_HUNTER_R1"
TASK_BRANCH = "codex/b649-k20-r3-state-13548976-three-level-shared-hunter-r1"
BASE_HEAD = "33e715faaad4ed0e13873705e5a01590ee4b70ec"
BASE_TREE = "3eafa630733297de427f3290433cc9024ea4b7f5"
BASE_RESULT_SHA256 = "2c62c25a8ebc324cea35cac6e5e7ac85a016b67b2c6bf136b8e81be6c06820fa"
BASE_MODULE_RELATIVE = (
    "src/lottolab/research/b649_k20_r3_state_14122976_two_band_ten_event_hunter_r1.py"
)
BASE_MODULE_SHA256 = "7e1006da7cc9c03dbd9df48932a34b3afd5679af3cacb95bada51dbfe1878a11"
TARGET_STATE_ID = "state:s2-13548976-s3-951748"
REGION_SHA256 = "1eed0fb9bc975d825d42413dd07ebfad5296d00185118850a38512c8a94e1f63"
REGION_MEMBER_COUNT, REGION_VECTOR_COUNT, LEVEL_COUNT = 1427, 1543, 3
RESIDUAL_EVENT_DEFINITION = "R_i = E_i \\ (E_A \u222a E_B)"
CORRECTION_COMBINATION = "MAX(R6_PAIR, FOREST, EXISTING_R14, EXISTING_HUNTER, NEW_HUNTER)"
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_RELATIVE = (
    six.RESULTS + "b649-k20-r3-state-13548976-three-level-shared-hunter-r1-result.json"
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
    stored = cast(dict[str, Any], json.loads((REPO_ROOT / prior.RESULT_RELATIVE).read_text()))
    if (
        stored["TASK_ID"] != prior.TASK_ID
        or stored["FINAL_OWNER_IDS"] != [TARGET_STATE_ID]
        or len(stored["MEMBER_CERTIFICATES"]) != 14
        or prior.verify_stored_result()["status"] != "PASS"
    ):
        raise AssertionError("immutable predecessor identity or byte replay failed")
    return stored


@cache
def region_authority() -> dict[str, Any]:
    """Last certificate on this State; subsequent certificates concern other States."""

    verify_upstream_fingerprints()
    stored = cast(dict[str, Any], json.loads(region.RESULT_PATH.read_text()))
    authority = source_authority()
    if (
        stored["TASK_ID"] != region.TASK_ID
        or stored["STATE_ID"] != TARGET_STATE_ID
        or stored["REGION_SHA256"] != REGION_SHA256
        or region.verify_stored_result()["status"] != "PASS"
        or stored["FINAL_TARGET_STATE_BOUND"]
        != dict((r["stable_id"], r["bound"]) for r in authority["FINAL_STATE_TERMS"])[
            TARGET_STATE_ID
        ]
    ):
        raise AssertionError("immutable target-region predecessor identity or replay failed")
    return stored


@cache
def region_members() -> tuple[LedgerMember, ...]:
    """Rebuild the ledger and replay every carried replacement exactly once."""

    verify_upstream_fingerprints()
    source = region_authority()
    members = region.region_members()
    vectors = region.represented_vectors()
    priors = {m.counts: m.final_bound for m in members}
    bounds = six.replaced_bounds(priors, source["MEMBER_CERTIFICATES"])
    replay = [
        {
            "member_id": member_id(m.counts),
            "witness_counts": sparse(m.counts),
            "represented_vector_count": m.represented_vector_count,
            "represented_vectors": [sparse(v) for v in vectors[m.counts]],
            "raw_bound": m.raw_bound,
            "prior_bound": m.final_bound,
            "final_bound": bounds[m.counts],
        }
        for m in members
    ]
    if (
        len(members) != REGION_MEMBER_COUNT
        or len(bounds) != REGION_MEMBER_COUNT
        or len({m.counts for m in members}) != REGION_MEMBER_COUNT
        or sum(m.represented_vector_count for m in members) != REGION_VECTOR_COUNT
        or catalog.region_fingerprint(members) != REGION_SHA256
        or catalog.normalized(replay) != source["COMPLETE_REGION_MEMBERS"]
        or any(m.represented_vector_count < 1 or bounds[m.counts] > m.raw_bound for m in members)
        or max(bounds.values()) != source["FINAL_TARGET_STATE_BOUND"]
    ):
        raise AssertionError("complete target region identity, coverage or carried bounds failed")
    return tuple(replace(m, final_bound=bounds[m.counts]) for m in members)


@cache
def represented_vectors() -> dict[CountVector, tuple[CountVector, ...]]:
    """Recover vectors at the immutable ledger's exact losses and signatures."""

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
    if recovered != region.represented_vectors():
        raise AssertionError("represented-vector source replay failed")
    return recovered


def target_levels(
    members: tuple[LedgerMember, ...],
) -> tuple[tuple[int, tuple[LedgerMember, ...]], ...]:
    """Discover all three highest ties before checking the Packet's exact cohorts."""

    levels = sorted({m.final_bound for m in members}, reverse=True)[:LEVEL_COUNT]
    cohorts = tuple((b, tuple(m for m in members if m.final_bound == b)) for b in levels)
    if len(cohorts) != LEVEL_COUNT:
        raise AssertionError("exact three-level coverage failed")
    for level, (_, rows) in enumerate(cohorts):
        expected: set[CountVector] = set()
        for j in range(5 if level == 0 else 8):
            counts = [0] * 30
            counts[0], counts[1], counts[4] = (13, j, 4 - j) if level == 0 else (9, j, 7 - j)
            if level == 0:
                counts[25] = 1
            else:
                counts[5 if level == 1 else 16], counts[20] = 1, 1
            expected.add(tuple(counts))
        if (
            {m.counts for m in rows} != expected
            or len(rows) != len(expected)
            or any(m.represented_vector_count != 1 or m.final_bound != m.raw_bound for m in rows)
        ):
            raise AssertionError("exact three-level 21-member/21-vector applicability failed")
    return cohorts


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

    if event_count not in (9, 13):
        raise ValueError("only nine- and thirteen-event proofs are authorized")
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
    outside = set(range(hunter.POOL_SIZE)) - set(hunter.ANCHOR_A | hunter.ANCHOR_B)
    incidences, labels = event_count * hunter.type_cells(0)[3], len(outside)
    if outside != set(hunter.CELL_LABELS[3]) or labels != 40:
        raise AssertionError("outside universe differs from the anchor complement")
    quotient, remainder = divmod(incidences, labels)
    mass = hunter.balanced_collision_mass(incidences, labels)
    if (
        mass != (labels - remainder) * comb(quotient, 2) + remainder * comb(quotient + 1, 2)
        or mass != incidences - labels
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
def support_witness(vector: CountVector) -> tuple[tuple[int, ...], ...]:
    return prior.support_witness(vector)


def certify_vector(
    member: LedgerMember, vector: CountVector, proof: dict[str, Any]
) -> dict[str, Any]:
    event_count = int(proof["event_count"])
    targets = tuple(m for _, rows in target_levels(region_members()) for m in rows)
    if (
        member not in targets
        or member.final_bound != member.raw_bound
        or vector not in represented_vectors()[member.counts]
        or vector[0] != event_count
        or proof != hunter_proof(event_count)
    ):
        raise AssertionError("represented vector or nine- or thirteen-event applicability failed")
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
    corrections = {
        "R6_PAIR": state.residual_pair_union_penalty,
        "FOREST": state.complementary_forest_floor,
        # All three discovered cohorts retain their raw bounds: no carried R14 credit.
        "EXISTING_R14": 0,
        "EXISTING_HUNTER": max(
            int(prior.prior.nine_event_proof()["hunter_floor"]),
            int(region.theorem.eleven_event_proof()["hunter_floor"]) if event_count >= 11 else 0,
        ),
        "NEW_HUNTER": int(proof["hunter_floor"]),
    }
    existing = uncorrected - member.final_bound
    combined = hunter.combine_corrections(corrections)
    bound = hunter.member_bound(uncorrected, combined)
    if (
        hunter.anchor_union_size() + residual_sum != uncorrected
        or state.applied_residual_union_penalty
        != max(corrections["R6_PAIR"], corrections["FOREST"])
        or uncorrected - state.applied_residual_union_penalty != member.raw_bound
        or existing != state.applied_residual_union_penalty
        or combined != max(corrections.values())
        or corrections["NEW_HUNTER"] <= existing
        or bound != uncorrected - combined
        or bound >= member.final_bound
    ):
        raise AssertionError("event arithmetic or max single correction replacement failed")
    support = support_witness(vector)
    witness = prior.prior.shared.prior.prior.witness_analysis(vector, support, proof)
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
    members, vectors = region_members(), represented_vectors()
    proofs = {n: hunter_proof(n) for n in (9, 13)}
    bands = target_levels(members)
    records = [
        certify_member(m, vectors[m.counts], proofs[m.counts[0]]) for _, rows in bands for m in rows
    ]
    priors = {m.counts: m.final_bound for m in members}
    bounds = six.replaced_bounds(priors, records)
    targets = {m.counts for _, rows in bands for m in rows}
    if {v for v in priors if bounds[v] != priors[v]} != targets:
        raise AssertionError("exactly the three-level member bounds must change")
    remainder = tuple(m for m in members if m.counts not in targets)
    if any(bounds[m.counts] != m.final_bound for m in remainder):
        raise AssertionError("preserved remainder certificate changed")
    state_bound = max(bounds.values())
    if state_bound != max(
        [*(int(r["member_new_bound"]) for r in records), *(m.final_bound for m in remainder)]
    ):
        raise AssertionError("independent complete State maximum failed")
    family = recompute_family(state_bound)
    if max(priors.values()) != dict(family["start_terms"])[TARGET_STATE_ID]:
        raise AssertionError("source region maximum differs from State term")
    band_rows = [
        {
            "prior_bound": b,
            "member_ids": [member_id(m.counts) for m in rows],
            "member_count": len(rows),
            "vector_count": sum(len(vectors[m.counts]) for m in rows),
            "new_bound": max(bounds[m.counts] for m in rows),
        }
        for b, rows in bands
    ]
    predecessor = source_authority()
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
            "PREDECESSOR_STATE_ID": prior.TARGET_STATE_ID,
            "STATE_ID": TARGET_STATE_ID,
            "REGION_IDENTITY": catalog.region_fingerprint(members),
            "REGION_SHA256": REGION_SHA256,
            "REGION_COMPRESSED_MEMBER_COUNT": len(members),
            "REGION_REPRESENTED_VECTOR_COUNT": sum(len(v) for v in vectors.values()),
            "REGION_COVERAGE_STATUS": "PASS_1427_MEMBERS_1543_DISTINCT_VECTORS_REPLAYED",
            "ALL_REPRESENTED_VECTORS_SHA256": digest(
                tuple((m.counts, vectors[m.counts]) for m in members)
            ),
            "THREE_LEVELS": band_rows,
            "THREE_LEVEL_MEMBER_IDS": [r["member_id"] for r in records],
            "THREE_LEVEL_MEMBER_COUNT": len(records),
            "THREE_LEVEL_VECTOR_COUNT": sum(r["represented_vector_count"] for r in records),
            "REPRESENTED_VECTOR_COVERAGE": "PASS_21_TARGET_AND_1543_REGION_VECTORS",
            "HUNTER_PROOFS": {str(n): p for n, p in proofs.items()},
            "HUNTER_N9_FLOOR": proofs[9]["hunter_floor"],
            "HUNTER_N13_FLOOR": proofs[13]["hunter_floor"],
            "THRESHOLD_PROOF_STATUS": "PASS_COMPLETE_N9_AND_N13_INTEGER_MINIMIZATION",
            "THREE_LEVEL_APPLICABILITY_STATUS": "PASS_ALL_21_VECTORS",
            "THREE_LEVEL_VECTOR_COUNTS": [r["vector_count"] for r in band_rows],
            "COLLISION_MASS_STATUS": "PASS_BALANCED_OUTSIDE_FLOOR_AND_WITNESS_IDENTITY",
            "EXACT_PAIR_COST_STATUS": "PASS_FOUR_RESIDUAL_PAIR_COSTS",
            "HUNTER_FLOOR_STATUS": "PASS_ALL_ADMISSIBLE_NESTED_THRESHOLD_CASES",
            "MEMBER_CERTIFICATES": records,
            "NEW_LEVEL_BOUNDS": [r["new_bound"] for r in band_rows],
            "PREDECESSOR_MEMBER_COUNT": len(predecessor["MEMBER_CERTIFICATES"]),
            "PREDECESSOR_MEMBER_CERTIFICATES": predecessor["MEMBER_CERTIFICATES"],
            "PREDECESSOR_CERTIFICATES_SHA256": json_digest(predecessor["MEMBER_CERTIFICATES"]),
            "PREDECESSOR_REGION_BOUNDS_SHA256": predecessor["COMPLETE_UPDATED_BOUNDS_SHA256"],
            "PREDECESSOR_STATE_BOUND": dict(family["terms"])[prior.TARGET_STATE_ID],
            "PREDECESSOR_CERTIFICATE_STATUS": "PASS_14_CERTIFICATES_AND_STATE_BOUND_PRESERVED",
            "ALL_CARRIED_CERTIFICATES_SHA256": {
                p: h for p, h in fingerprints.items() if p.endswith(".json")
            },
            "PRESERVED_MEMBER_COUNT": len(remainder),
            "PRESERVED_VECTOR_COUNT": sum(len(vectors[m.counts]) for m in remainder),
            "PRESERVED_REMAINDER_MAX": max(bounds[m.counts] for m in remainder),
            "PRESERVED_MEMBER_BOUNDS_SHA256": digest(
                tuple(
                    (m.counts, m.represented_vector_count, m.raw_bound, bounds[m.counts])
                    for m in remainder
                )
            ),
            "COMPLETE_UPDATED_BOUNDS_SHA256": digest(
                tuple((m.counts, bounds[m.counts]) for m in members)
            ),
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
            "FINAL_COMPLETE_R3_UB": family["final"]["R3_BOUND"],
            "FINAL_OWNER_IDS": family["final"]["OWNER_IDS"],
            "CURRENT_INCUMBENT": r24.INCUMBENT,
            "REMAINING_GAP": int(family["final"]["R3_BOUND"]) - r24.INCUMBENT,
            "CORRECTION_COMBINATION": CORRECTION_COMBINATION,
            "NO_DOUBLE_COUNT_STATUS": "PASS_MAX_SINGLE_REPLACEMENT",
            "DUPLICATE_CORRECTIONS": sum(
                row["uncorrected_anchor_bound"] - row["vector_new_bound"]
                != max(row["corrections"].values())
                for r in records
                for row in r["vector_certificates"]
            ),
            "WITNESS_SOUNDNESS_STATUS": "PASS_21_LEGAL_SUPPORTS_AND_FULL_HUNTER_TREE_EXTENSIONS",
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
        "members": 21,
        "vectors": 21,
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
        "THREE_LEVEL_MEMBER_IDS",
        "THREE_LEVEL_VECTOR_COUNTS",
        "HUNTER_N9_FLOOR",
        "HUNTER_N13_FLOOR",
        "NEW_LEVEL_BOUNDS",
        "PRESERVED_REMAINDER_MAX",
        "FINAL_TARGET_STATE_UB",
        "FINAL_COMPLETE_R3_UB",
        "FINAL_OWNER_IDS",
        "REMAINING_GAP",
    )
    print(json.dumps({k: result[k] for k in keys}, sort_keys=True))


if __name__ == "__main__":
    main()
