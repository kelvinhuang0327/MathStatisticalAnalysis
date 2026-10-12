"""Apply the inherited eleven-event Hunter theorem to the two current R3 owners.

Replay the immutable complete ledger and all represented vectors at their exact
loss/signature. Only the two t=6 members receive new credit. Recount the type-0
residual pairs and collision floor, check threshold forest ranks, and extend the
eleven-event tree to eighteen events with nonnegative edges. A single maximum
replaces the existing correction. Replay all 23 State and 56550 classified terms.
No census, solver, official-outcome enumeration, or additional R14 work runs.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import replace
from functools import cache
from hashlib import sha256
from math import comb
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_r3_state_13548976_multiband_shared_certificate_r1 as prior

hunter, catalog, six = prior.hunter, prior.catalog, prior.six
region, theorem = prior.region, prior.base.prior
type CountVector = tuple[int, ...]
LedgerMember = catalog.LedgerMember
dense, sparse, digest, member_id = prior.dense, prior.sparse, prior.digest, prior.member_id
TASK_ID = "B649_K20_R3_T6_TWO_MEMBER_ELEVEN_EVENT_HUNTER_R1"
TASK_BRANCH = "codex/b649-k20-r3-t6-two-member-eleven-event-hunter-r1"
BASE_HEAD = "90bf41bc87500763f764c09cd1c90c0ea82e2023"
BASE_TREE = "a62938a80bbda1e2be33cd4631ba8599495579a4"
BASE_RESULT_SHA256 = "60e44a40b5bcd6fb37256cd791e10c1c9c5d35cdd9bec5f5520ecaa5f35ba3df"
BASE_MODULE_SHA256 = "df4ebcaeedce13310ea0d83d9f3e256b60a65da7db9375f60c92413920065a61"
TARGET_STATE_ID = prior.TARGET_STATE_ID
REGION_SHA256 = "1eed0fb9bc975d825d42413dd07ebfad5296d00185118850a38512c8a94e1f63"
TARGET_VECTORS = tuple(dense([[0, 11], [j, 1], [16, 6]]) for j in (4, 1))
TARGET_IDS = tuple(member_id(v) for v in TARGET_VECTORS)
EVENT_COUNT = 11
RESIDUAL_EVENT_DEFINITION = "R_i = E_i \\ (E_A \u222a E_B)"
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_RELATIVE = six.RESULTS + "b649-k20-r3-t6-two-member-eleven-event-hunter-r1-result.json"
RESULT_PATH = REPO_ROOT / RESULT_RELATIVE
BASE_MODULE_RELATIVE = (
    "src/lottolab/research/b649_k20_r3_state_13548976_multiband_shared_certificate_r1.py"
)
UPSTREAM_SHA256 = {
    **prior.UPSTREAM_SHA256,
    prior.RESULT_RELATIVE: BASE_RESULT_SHA256,
    BASE_MODULE_RELATIVE: BASE_MODULE_SHA256,
}
CORRECTION_COMBINATION = "MAX(R6_PAIR, FOREST, EXISTING_HUNTER, ELEVEN_EVENT_HUNTER)"


def verify_upstream_fingerprints() -> dict[str, str]:
    """Recheck every donor even when mathematical/authority caches are warm."""

    observed = {p: sha256((REPO_ROOT / p).read_bytes()).hexdigest() for p in UPSTREAM_SHA256}
    if observed != UPSTREAM_SHA256:
        raise AssertionError("immutable source fingerprint mismatch")
    return observed


def verify_base_authority() -> dict[str, str]:
    """Verify the exact immutable Git objects, independently of the working HEAD."""

    prefix = ["git", "-C", str(REPO_ROOT)]
    tree = subprocess.check_output([*prefix, "rev-parse", f"{BASE_HEAD}^{{tree}}"], text=True)
    if tree.strip() != BASE_TREE:
        raise AssertionError("immutable base HEAD/TREE identity failed")
    for relative, expected in (
        (prior.RESULT_RELATIVE, BASE_RESULT_SHA256),
        (BASE_MODULE_RELATIVE, BASE_MODULE_SHA256),
    ):
        blob = subprocess.check_output([*prefix, "show", f"{BASE_HEAD}:{relative}"])
        if sha256(blob).hexdigest() != expected:
            raise AssertionError("immutable base certificate object failed")
    return {"HEAD": BASE_HEAD, "TREE": BASE_TREE, "RESULT_SHA256": BASE_RESULT_SHA256}


@cache
def source_authority() -> dict[str, Any]:
    verify_base_authority()
    verify_upstream_fingerprints()
    stored = cast(dict[str, Any], json.loads((REPO_ROOT / prior.RESULT_RELATIVE).read_text()))
    if (
        stored["TASK_ID"] != prior.TASK_ID
        or stored["STATE_ID"] != TARGET_STATE_ID
        or stored["REGION_SHA256"] != REGION_SHA256
        or stored["FINAL_OWNER_IDS"] != [TARGET_STATE_ID]
        or tuple(stored["FINAL_STATE_MEMBER_IDS"]) != TARGET_IDS
        or prior.verify_stored_result()["status"] != "PASS"
    ):
        raise AssertionError("immutable predecessor certificate identity or byte replay failed")
    return stored


@cache
def region_members() -> tuple[LedgerMember, ...]:
    """Rebuild all raw members and replay every previous certificate replacement."""

    authority = source_authority()
    members = six.region_members()
    earlier = prior.current_member_bounds(members)
    bounds = six.replaced_bounds(earlier, authority["MEMBER_CERTIFICATES"])
    replay = [
        {
            "member_id": member_id(m.counts),
            "witness_counts": sparse(m.counts),
            "represented_vector_count": m.represented_vector_count,
            "raw_bound": m.raw_bound,
            "prior_bound": earlier[m.counts],
            "final_bound": bounds[m.counts],
        }
        for m in members
    ]
    if (
        len(members) != 1427
        or len(bounds) != len(members)
        or sum(m.represented_vector_count for m in members) != 1543
        or catalog.region_fingerprint(members) != REGION_SHA256
        or catalog.normalized(replay) != authority["COMPLETE_REGION_MEMBERS"]
        or max(bounds.values()) != authority["FINAL_STATE_BOUND"]
    ):
        raise AssertionError("complete region identity, coverage or prior bound replay failed")
    return tuple(replace(m, final_bound=bounds[m.counts]) for m in members)


def target_members(members: tuple[LedgerMember, ...]) -> tuple[LedgerMember, ...]:
    """Discover the entire highest tie, then require the two authorized identities."""

    maximum = max(m.final_bound for m in members)
    cohort = tuple(m for m in members if m.final_bound == maximum)
    if (
        len(cohort) != 2
        or {m.counts for m in cohort} != set(TARGET_VECTORS)
        or any(m.represented_vector_count != 1 or m.final_bound != m.raw_bound for m in cohort)
    ):
        raise AssertionError("exact two highest tied member identities or coverage failed")
    available = {m.counts: m for m in cohort}
    return tuple(available[v] for v in TARGET_VECTORS)


@cache
def represented_vectors() -> dict[CountVector, tuple[CountVector, ...]]:
    """Recover and verify all 1543 vectors without rebuilding an R7 census."""

    members = region_members()
    recovered = catalog.r17.represented_vectors(tuple(catalog.rebuild_member(m) for m in members))
    flat = [v for vectors in recovered.values() for v in vectors]
    if (
        set(recovered) != {m.counts for m in members}
        or len(flat) != 1543
        or len(set(flat)) != len(flat)
        or any(len(recovered[m.counts]) != m.represented_vector_count for m in members)
    ):
        raise AssertionError("complete represented-vector coverage failed")
    for member in members:
        vectors = recovered[member.counts]
        if tuple(sorted(vectors)) != vectors or min(vectors) != member.counts:
            raise AssertionError("represented-vector canonical identity failed")
        signature = hunter.eleven.compression_signature(catalog.rebuild_member(member))
        for vector in vectors:
            state = catalog.rebuild_member(
                replace(member, counts=vector, represented_vector_count=1)
            )
            if (
                hunter.eleven.compression_signature(state) != signature
                or sum(vector) != hunter.RESIDUAL_EVENT_COUNT
                or any(n < 0 for n in vector)
            ):
                raise AssertionError("represented vector compression signature failed")
    return recovered


def eleven_event_proof() -> dict[str, Any]:
    """Re-derive the inherited theorem from exact pairs, collisions and forest ranks."""

    if (
        hunter.RESIDUAL_EVENT_DEFINITION != RESIDUAL_EVENT_DEFINITION
        or hunter.eleven.RESIDUAL_EVENT_DEFINITION != RESIDUAL_EVENT_DEFINITION
        or hunter.type_cells(0) != (0, 0, 0, hunter.TICKET_SIZE)
    ):
        raise AssertionError("source residual-event definition or type-0 identity failed")
    rows = hunter.exact_pair_rows(((0, 0),))
    ceiling = hunter.family_pair_overlap_ceiling()
    if len(rows) != ceiling + 1 or {row[2:6] for row in rows} != {
        (0, 0, 0, overlap) for overlap in range(ceiling + 1)
    }:
        raise AssertionError("exact type-0 pair row coverage failed")
    for row in rows:
        overlap = (row[2], row[3], row[4], row[5])
        if (
            row[:2] != (0, 0)
            or six.residual_pair_intersection(0, 0, overlap) != row[6]
            or hunter.outcome_count(
                hunter.realize_pair(hunter.type_cells(0), hunter.type_cells(0), overlap),
                (hunter.ANCHOR_A, hunter.ANCHOR_B),
            )
            != row[6]
        ):
            raise AssertionError("exact residual pair inclusion/exclusion failed")
    floors = hunter.pair_floors(rows)
    hunter.require_safe_pair_floors(floors, rows)
    incidences = EVENT_COUNT * hunter.type_cells(0)[3]
    labels = len(hunter.CELL_LABELS[3])
    quotient, remainder = divmod(incidences, labels)
    mass = hunter.balanced_collision_mass(incidences, labels)
    if mass != (labels - remainder) * comb(quotient, 2) + remainder * comb(quotient + 1, 2):
        raise AssertionError("balanced outside collision floor failed")
    rank_rows = hunter.verify_rank_floor_algebra(EVENT_COUNT)
    cases = theorem.prior.threshold_cases(floors, mass, EVENT_COUNT)
    floor = min(int(row["hunter_floor"]) for row in cases)
    relaxation = hunter.minimum_tree_correction(floors, mass, EVENT_COUNT)
    if floor != relaxation.correction:
        raise AssertionError("threshold forest-rank Hunter inequality failed")
    proof = {
        "event_count": EVENT_COUNT,
        "type_index": 0,
        "type_cells": list(hunter.type_cells(0)),
        "residual_event_definition": RESIDUAL_EVENT_DEFINITION,
        "residual_event_size": hunter.residual_event_size(0),
        "outside_incidences": incidences,
        "outside_label_count": labels,
        "balanced_frequencies": [[quotient, labels - remainder], [quotient + 1, remainder]],
        "collision_mass_floor": mass,
        "pair_rows": [list(row) for row in rows],
        "pair_floors": list(floors),
        "rank_rule": "rho(e) = min{r: C(r+1,2) >= e}; e1+e2+e3 >= Q",
        "rank_algebra_rows": rank_rows,
        "threshold_cases": cases,
        "hunter_floor": floor,
        "integer_minimizer": {
            "edge_counts": list(relaxation.edge_counts),
            "rank_floors": list(relaxation.rank_floors),
            "feasible_threshold_triples": relaxation.census_size,
        },
        "theorem_source": hunter.TASK_ID,
        "hunter_rule": hunter.HUNTER_RULE,
        "extension_rule": "Extend subset tree to all residual events with nonnegative edges",
    }
    if proof != theorem.eleven_event_proof():
        raise AssertionError("inherited eleven-event certificate source differs from derivation")
    return proof


def certify_vector(
    member: LedgerMember, vector: CountVector, proof: dict[str, Any]
) -> dict[str, Any]:
    """Only an exactly recovered vector with the inherited event identity is eligible."""

    if (
        member not in target_members(region_members())
        or vector not in represented_vectors()[member.counts]
        or vector[0] != EVENT_COUNT
        or proof != eleven_event_proof()
    ):
        raise AssertionError("represented vector or source event identity failed")
    state = catalog.rebuild_member(replace(member, counts=vector, represented_vector_count=1))
    signature = hunter.eleven.compression_signature(state)
    types = tuple(i for i, n in enumerate(vector) for _ in range(n))
    if (
        signature != hunter.eleven.compression_signature(catalog.rebuild_member(member))
        or len(types) != hunter.RESIDUAL_EVENT_COUNT
        or types[:EVENT_COUNT] != (0,) * EVENT_COUNT
    ):
        raise AssertionError("represented vector compression signature or event identity failed")
    for type_index in set(types):
        s, a, b, outside = hunter.type_cells(type_index)
        if (
            s + a + b + outside != hunter.TICKET_SIZE
            or max(s + a, s + b) > hunter.family_pair_overlap_ceiling()
        ):
            raise AssertionError("residual event type violates source anchor identity")
    nine = prior.base.nine_event_proof()
    existing_hunter = int(nine["hunter_floor"]) if vector[0] >= int(nine["event_count"]) else 0
    corrections = {
        "R6_PAIR": state.residual_pair_union_penalty,
        "FOREST": state.complementary_forest_floor,
        "EXISTING_HUNTER": existing_hunter,
        "ELEVEN_EVENT_HUNTER": int(proof["hunter_floor"]),
    }
    existing = hunter.combine_corrections(
        {k: v for k, v in corrections.items() if k != "ELEVEN_EVENT_HUNTER"}
    )
    uncorrected = hunter.r14.joint_constant() - state.anchor_pair_s2 + state.anchor_triple_s3
    residual_sum = sum(n * hunter.residual_event_size(i) for i, n in enumerate(vector) if n)
    combined = hunter.combine_corrections(corrections)
    bound = hunter.member_bound(uncorrected, combined)
    if (
        hunter.anchor_union_size() + residual_sum != uncorrected
        or existing != state.applied_residual_union_penalty
        or uncorrected - existing != member.final_bound
        or combined != max(corrections.values())
        or bound != uncorrected - combined
        or bound >= member.final_bound
    ):
        raise AssertionError("event arithmetic or max single correction replacement failed")
    support = hunter.r12.construct_support_witness(vector)
    if support is None or not hunter.r8.validate_support_assignment(vector, support):
        raise AssertionError("represented vector has no valid support witness")
    witness = region.witness_analysis(vector, support, proof)
    return {
        "vector_id": member_id(vector),
        "counts": sparse(vector),
        "compression_signature": signature,
        "residual_event_definition": RESIDUAL_EVENT_DEFINITION,
        "type0_count": vector[0],
        "eleven_event_indices": list(range(EVENT_COUNT)),
        "eleven_event_types": list(types[:EVENT_COUNT]),
        "outside_incidences": EVENT_COUNT * hunter.type_cells(0)[3],
        "collision_mass_floor": proof["collision_mass_floor"],
        "pair_overlap_ceiling": hunter.family_pair_overlap_ceiling(),
        "anchor_union": hunter.anchor_union_size(),
        "residual_event_sum": residual_sum,
        "uncorrected_anchor_bound": uncorrected,
        "corrections": corrections,
        "prior_applied_correction": existing,
        "combined_correction": combined,
        "vector_new_bound": bound,
        "support_witness": support,
        "support_sha256": digest(support),
        "witness_analysis": witness,
    }


def certify_member(
    member: LedgerMember, vectors: tuple[CountVector, ...], proof: dict[str, Any]
) -> dict[str, Any]:
    if member.counts not in TARGET_VECTORS or vectors != represented_vectors()[member.counts]:
        raise AssertionError("exact represented-vector member coverage failed")
    rows = [certify_vector(member, vector, proof) for vector in vectors]
    correction = hunter.member_correction(tuple(int(r["combined_correction"]) for r in rows))
    bound = max(int(r["vector_new_bound"]) for r in rows)
    if (
        len(rows) != member.represented_vector_count
        or correction != min(r["combined_correction"] for r in rows)
        or bound != hunter.member_bound(int(rows[0]["uncorrected_anchor_bound"]), correction)
    ):
        raise AssertionError("compressed member did not use its weakest vector correction")
    return catalog.normalized(
        {
            "member_id": member_id(member.counts),
            "witness_counts": sparse(member.counts),
            "represented_vector_count": len(vectors),
            "represented_vectors": [sparse(v) for v in vectors],
            "vector_certificates": rows,
            "member_prior_bound": member.final_bound,
            "member_raw_bound": member.raw_bound,
            "member_certified_correction": correction,
            "member_new_bound": bound,
            "correction_combination": CORRECTION_COMBINATION,
        }
    )


def recompute_family(state_bound: int) -> dict[str, Any]:
    """Re-evaluate every sealed State and classified term, including the aggregate."""

    authority = source_authority()
    terms = tuple((str(r["stable_id"]), int(r["bound"])) for r in authority["FINAL_STATE_TERMS"])
    classified, tail = six.classified_terms(), six.sealed_tail_bound()
    aggregate = [
        {"stable_id": k, "bound": b} for k, b in classified if k == catalog.r24.AGGREGATE_ID
    ]
    start = six.tail.family_maximum(tail, terms, classified)
    if (
        len(terms) != 23
        or len(dict(terms)) != 23
        or TARGET_STATE_ID not in dict(terms)
        or len(classified) != 56550
        or len(classified) != authority["CLASSIFIED_TERM_COUNT"]
        or digest(classified) != authority["CLASSIFIED_TERMS_SHA256"]
        or aggregate != authority["CLASSIFIED_AGGREGATE"]
        or tail != authority["TAIL_BOUND"]
        or start != authority["FINAL_FAMILY_MAX_RECOMPUTATION"]
    ):
        raise AssertionError("complete 23-State, classified aggregate or Tail source replay failed")
    replaced = tuple((k, state_bound if k == TARGET_STATE_ID else b) for k, b in terms)
    return {
        "start": start,
        "final": six.tail.family_maximum(tail, replaced, classified),
        "start_terms": terms,
        "terms": replaced,
        "tail_bound": tail,
        "classified_count": len(classified),
        "classified_sha256": digest(classified),
        "aggregate": aggregate,
    }


def build_result() -> dict[str, Any]:
    fingerprints = verify_upstream_fingerprints()
    base_identity = verify_base_authority()
    authority = source_authority()
    members = region_members()
    cohort = target_members(members)
    vectors = represented_vectors()
    proof = eleven_event_proof()
    records = [certify_member(m, vectors[m.counts], proof) for m in cohort]
    priors = {m.counts: m.final_bound for m in members}
    bounds = six.replaced_bounds(priors, records)
    changed = {v for v in priors if bounds[v] != priors[v]}
    if changed != set(TARGET_VECTORS):
        raise AssertionError("exactly two member replacements required")
    remainder = tuple(m for m in members if m.counts not in changed)
    if any(bounds[m.counts] != m.final_bound for m in remainder):
        raise AssertionError("a preserved remainder member changed")
    final_state = max(bounds.values())
    family = recompute_family(final_state)
    if max(priors.values()) != dict(family["start_terms"])[TARGET_STATE_ID]:
        raise AssertionError("complete source region maximum differs from State term")
    rows = [r["vector_certificates"][0] for r in records]
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
            "IMMUTABLE_BASE_VERIFICATION": base_identity,
            "SOURCE_AUTHORITY_STATUS": "PASS_IMMUTABLE_OBJECTS_FINGERPRINTS_AND_BYTE_REPLAY",
            "UPSTREAM_FINGERPRINTS_SHA256": fingerprints,
            "STATE_ID": TARGET_STATE_ID,
            "REGION_SHA256": catalog.region_fingerprint(members),
            "REGION_COMPRESSED_MEMBER_COUNT": len(members),
            "REGION_REPRESENTED_VECTOR_COUNT": sum(len(v) for v in vectors.values()),
            "REGION_COVERAGE_STATUS": "PASS_1427_MEMBERS_1543_VECTORS_REPLAYED",
            "TIED_MEMBER_IDS": [r["member_id"] for r in records],
            "REPRESENTED_VECTOR_COVERAGE": [r["represented_vector_count"] for r in records],
            "REPRESENTED_VECTOR_COVERAGE_STATUS": "PASS_2_OF_2",
            "ALL_REPRESENTED_VECTORS_SHA256": digest(
                tuple((m.counts, vectors[m.counts]) for m in members)
            ),
            "ELEVEN_EVENT_PROOF": proof,
            "ELEVEN_EVENT_PROOF_STATUS": "PASS_EXACT_INHERITED_RESIDUAL_EVENT_THEOREM",
            "COLLISION_MASS_STATUS": "PASS_66_INCIDENCES_40_LABELS_FLOOR_26",
            "HUNTER_FLOOR": proof["hunter_floor"],
            "MEMBER_CERTIFICATES": records,
            "NEW_MEMBER_BOUNDS": [r["member_new_bound"] for r in records],
            "PREVIOUS_MEMBER_CERTIFICATES_SHA256": prior.json_digest(
                authority["MEMBER_CERTIFICATES"]
            ),
            "PREVIOUS_REGION_CERTIFICATES_SHA256": authority["PREVIOUS_REGION_CERTIFICATES_SHA256"],
            "PREVIOUS_NINE_ELEVEN_CERTIFICATES_SHA256": authority[
                "PREVIOUS_NINE_ELEVEN_CERTIFICATES_SHA256"
            ],
            "PREVIOUS_CERTIFICATE_STATUS": "PASS_EXACT_SOURCE_REPLAY_AND_PRESERVATION",
            "ALL_CARRIED_CERTIFICATES_SHA256": {
                p: h for p, h in fingerprints.items() if p.endswith(".json")
            },
            "PRESERVED_MEMBER_COUNT": len(remainder),
            "PRESERVED_VECTOR_COUNT": sum(len(vectors[m.counts]) for m in remainder),
            "PRESERVED_REMAINDER_MAX": max(bounds[m.counts] for m in remainder),
            "PRESERVED_REMAINDER_SHA256": digest(
                tuple(
                    (m.counts, m.represented_vector_count, m.raw_bound, m.final_bound)
                    for m in remainder
                )
            ),
            "PRESERVED_MEMBER_BOUNDS_SHA256": prior.preserved_bounds_sha256(
                members, bounds, changed
            ),
            "COMPLETE_UPDATED_BOUNDS_SHA256": prior.preserved_bounds_sha256(members, bounds, set()),
            "COMPLETE_REGION_MEMBERS": [
                {
                    "member_id": member_id(m.counts),
                    "witness_counts": sparse(m.counts),
                    "represented_vector_count": len(vectors[m.counts]),
                    "represented_vectors": [sparse(v) for v in vectors[m.counts]],
                    "raw_bound": m.raw_bound,
                    "prior_bound": priors[m.counts],
                    "final_bound": bounds[m.counts],
                }
                for m in members
            ],
            "START_STATE_BOUND": max(priors.values()),
            "FINAL_TARGET_STATE_BOUND": final_state,
            "FINAL_STATE_MEMBER_IDS": [member_id(c) for c, b in bounds.items() if b == final_state],
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
            "CURRENT_INCUMBENT": catalog.r24.INCUMBENT,
            "REMAINING_GAP": int(family["final"]["R3_BOUND"]) - catalog.r24.INCUMBENT,
            "CORRECTION_COMBINATION": CORRECTION_COMBINATION,
            "NO_DOUBLE_COUNT_STATUS": "PASS_MAX_SINGLE_REPLACEMENT",
            "DUPLICATE_CORRECTIONS": sum(
                row["uncorrected_anchor_bound"] - row["vector_new_bound"]
                != max(row["corrections"].values())
                for row in rows
            ),
            "WITNESS_SOUNDNESS_STATUS": "PASS_TWO_EXACT_SUPPORTS_AND_FULL_TREE_EXTENSIONS",
            "R7_CENSUS_REBUILD_CALLS": 0,
            "OUTCOME_ENUMERATION_USED": False,
            "NEW_HEAVY_SOLVER_STARTED": "NO",
            "PRODUCTION_MUTATION": "NONE",
            "PUSH_PR_MERGE": "NONE",
            "WORKTREE_DISPOSITION": "RETAIN",
        }
    )


def verify_result(result: dict[str, Any]) -> dict[str, Any]:
    """Reject mathematical, coverage and source tampering before the final replay."""

    verify_upstream_fingerprints()
    identity = {
        "TASK_ID": TASK_ID,
        "TASK_BRANCH": TASK_BRANCH,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_RESULT_SHA256": BASE_RESULT_SHA256,
        "BASE_MODULE_SHA256": BASE_MODULE_SHA256,
        "STATE_ID": TARGET_STATE_ID,
        "REGION_SHA256": REGION_SHA256,
    }
    if any(result.get(k) != v for k, v in identity.items()):
        raise AssertionError("certificate source identity failed")
    records = result["MEMBER_CERTIFICATES"]
    if tuple(r["member_id"] for r in records) != TARGET_IDS:
        raise AssertionError("exact two member certificate coverage failed")
    proof = eleven_event_proof()
    if result["ELEVEN_EVENT_PROOF"] != proof:
        raise AssertionError("eleven-event pair, collision or forest-rank proof replay failed")
    members = {m.counts: m for m in target_members(region_members())}
    for record in records:
        vector = dense(record["witness_counts"])
        expected = certify_member(members[vector], represented_vectors()[vector], proof)
        if (
            record["represented_vectors"] != expected["represented_vectors"]
            or len(record["vector_certificates"]) != record["represented_vector_count"]
        ):
            raise AssertionError("represented-vector certificate coverage failed")
        for row, replay in zip(
            record["vector_certificates"], expected["vector_certificates"], strict=True
        ):
            if any(
                row[k] != replay[k]
                for k in (
                    "counts",
                    "compression_signature",
                    "residual_event_definition",
                    "type0_count",
                    "eleven_event_indices",
                    "eleven_event_types",
                    "outside_incidences",
                    "collision_mass_floor",
                    "pair_overlap_ceiling",
                )
            ):
                raise AssertionError("represented-vector signature or source event identity failed")
            if any(
                row[k] != replay[k]
                for k in (
                    "corrections",
                    "combined_correction",
                    "prior_applied_correction",
                    "uncorrected_anchor_bound",
                    "vector_new_bound",
                )
            ):
                raise AssertionError("max single correction replacement replay failed")
            support = tuple(tuple(int(label) for label in t) for t in row["support_witness"])
            if not hunter.r8.validate_support_assignment(vector, support):
                raise AssertionError("stored support witness is invalid")
            if digest(support) != row["support_sha256"]:
                raise AssertionError("stored support witness fingerprint failed")
        if record != expected:
            raise AssertionError("member certificate or witness arithmetic differs from replay")
    replay_result = build_result()
    if any(
        result[k] != replay_result[k]
        for k in (
            "COMPLETE_REGION_MEMBERS",
            "ALL_REPRESENTED_VECTORS_SHA256",
            "PRESERVED_MEMBER_COUNT",
            "PRESERVED_VECTOR_COUNT",
            "PRESERVED_REMAINDER_MAX",
            "PRESERVED_REMAINDER_SHA256",
            "PRESERVED_MEMBER_BOUNDS_SHA256",
            "COMPLETE_UPDATED_BOUNDS_SHA256",
            "PREVIOUS_MEMBER_CERTIFICATES_SHA256",
            "ALL_CARRIED_CERTIFICATES_SHA256",
        )
    ):
        raise AssertionError("complete region or preserved remainder replay failed")
    if any(
        result[k] != replay_result[k]
        for k in (
            "START_STATE_TERMS",
            "FINAL_STATE_TERMS",
            "FINAL_STATE_MEMBER_IDS",
            "TAIL_BOUND",
            "CLASSIFIED_TERM_COUNT",
            "CLASSIFIED_TERMS_SHA256",
            "CLASSIFIED_AGGREGATE",
            "FINAL_FAMILY_MAX_RECOMPUTATION",
            "FINAL_COMPLETE_R3_UB",
            "FINAL_OWNER_IDS",
        )
    ):
        raise AssertionError("complete 23-State Family, Tail or aggregate replay failed")
    if result != replay_result:
        raise AssertionError("stored result differs from complete exact replay")
    return {
        "status": "PASS",
        "members": 2,
        "vectors": 2,
        "region_members": 1427,
        "region_vectors": 1543,
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
    options = parser.parse_args()
    if options.verify:
        print(json.dumps(verify_stored_result(), sort_keys=True))
        return
    result = build_result()
    if options.write:
        RESULT_PATH.write_text(encode(result), encoding="utf-8")
    keys = (
        "TASK_STATUS",
        "TIED_MEMBER_IDS",
        "HUNTER_FLOOR",
        "NEW_MEMBER_BOUNDS",
        "PRESERVED_REMAINDER_MAX",
        "FINAL_TARGET_STATE_BOUND",
        "START_COMPLETE_R3_UB",
        "FINAL_COMPLETE_R3_UB",
        "FINAL_OWNER_IDS",
        "REMAINING_GAP",
    )
    print(json.dumps({k: result[k] for k in keys}, sort_keys=True))


if __name__ == "__main__":
    main()
