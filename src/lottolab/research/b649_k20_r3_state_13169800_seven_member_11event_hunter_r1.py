"""Seal the eleven-event Hunter floor on seven members of the current R3 State.

Read the complete R24 ledger, rebuild its raw members, and replay its carried
certificates without rebuilding a census. Only the seven current owners receive
new credit. Their eleven type-0 residual events have 66 incidences on 40 labels.
Convexity forces Q >= 26. Exact residual pair counts and nested threshold forest
ranks give a common subset-tree correction, extended to all eighteen events by
nonnegative edges. Combine existing corrections by max and replace them once.
The remaining ledger members and the other 22 State terms stay sealed.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from functools import cache
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_r3_next_two_layers_shared_hunter_certificate_r1 as prior

hunter = prior.prior
catalog, r24 = hunter.catalog, hunter.catalog.r24
CountVector = hunter.CountVector
LedgerMember = catalog.LedgerMember
TASK_ID = "B649_K20_R3_STATE_13169800_SEVEN_MEMBER_11EVENT_HUNTER_R1"
TASK_BRANCH = "codex/b649-k20-r3-state-13169800-seven-member-11event-hunter-r1"
BASE_HEAD = "7ee823ca367076b483f93f1cc8c4d6da89aaa3e2"
BASE_TREE = "f0f6d5f1e0ee8617c7630863f9099c25d5753ecb"
BASE_RESULT_SHA256 = "cbc291d98438e515f9b53f58dd6174bdb9eba88c123842bdd5f63a8aedd173e7"
TARGET_STATE_ID = "state:s2-13169800-s3-789320"
EVENT_COUNT = 11
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_RELATIVE = (
    hunter.six.RESULTS + "b649-k20-r3-state-13169800-seven-member-11event-hunter-r1-result.json"
)
RESULT_PATH = REPO_ROOT / RESULT_RELATIVE
UPSTREAM_SHA256 = {
    **prior.UPSTREAM_SHA256,
    **r24.UPSTREAM_SHA256,
    **r24.CARRIED_SHA256,
    prior.RESULT_RELATIVE: BASE_RESULT_SHA256,
    "src/lottolab/research/b649_k20_r3_next_two_layers_shared_hunter_certificate_r1.py": (
        "3e46a5be17a24ee934e5489cd40c5544656a2d92192e585e74ed78d90f63ddc0"
    ),
}
CORRECTION_COMBINATION = "MAX(R6_PAIR, FOREST, EXISTING_R14, ELEVEN_EVENT_HUNTER)"


def verify_upstream_fingerprints() -> dict[str, str]:
    observed = {
        name: sha256((REPO_ROOT / name).read_bytes()).hexdigest() for name in UPSTREAM_SHA256
    }
    if observed != UPSTREAM_SHA256:
        raise AssertionError("immutable source fingerprint mismatch")
    return observed


@cache
def source_authority() -> dict[str, Any]:
    verify_upstream_fingerprints()
    stored = cast(dict[str, Any], json.loads((REPO_ROOT / prior.RESULT_RELATIVE).read_text()))
    if (
        stored["TASK_ID"] != prior.TASK_ID
        or stored["FINAL_OWNER_IDS"] != [TARGET_STATE_ID]
        or prior.verify_result(stored)["status"] != "PASS"
    ):
        raise AssertionError("immutable complete R3 source certificate failed replay")
    return stored


@cache
def region_members() -> tuple[LedgerMember, ...]:
    """Replay the ledger's raw bounds and every existing sealed replacement."""

    authority = source_authority()
    stored = catalog.r24_authority()
    regions = [r for r in stored["STATE_REGION_CERTIFICATES"] if r["owner_id"] == TARGET_STATE_ID]
    carried = [
        r for r in stored["CARRIED_OWNER_REGION_CERTIFICATES"] if r["owner_id"] == TARGET_STATE_ID
    ]
    if len(regions) != 1 or len(carried) != 1:
        raise AssertionError("target State has no unique complete source region")
    region, entry = regions[0], carried[0]
    members = tuple(
        LedgerMember(
            hunter.dense(row["witness_counts"]),
            int(row["represented_vector_count"]),
            int(row["raw_bound"]),
            int(row["final_bound"]),
        )
        for row in region["complete_region_members"]
    )
    fingerprint = catalog.region_fingerprint(members)
    if (
        len(members) != 989
        or len({m.counts for m in members}) != len(members)
        or sum(m.represented_vector_count for m in members) != 1072
        or entry["region_compressed_member_count"] != len(members)
        or entry["region_type_vector_count"] != sum(m.represented_vector_count for m in members)
        or region["region_sha256"] != fingerprint
        or entry["region_sha256"] != fingerprint
        or any(m.represented_vector_count < 1 or m.final_bound > m.raw_bound for m in members)
    ):
        raise AssertionError("complete region fingerprint or coverage failed")
    # _make_state is a single-vector constructor, never joint_residual_census.
    raw = {m.counts: hunter.r14.raw_bound(catalog.rebuild_member(m)) for m in members}
    bounds = dict(raw)
    for label, counts, bound, source_region in r24.carried_member_certificates(TARGET_STATE_ID):
        if source_region != fingerprint or counts not in raw or bound > raw[counts]:
            raise AssertionError(f"carried {label} certificate is outside the source region")
        bounds[counts] = min(bounds[counts], bound)
    for row in stored["STATE_OWNER_CERTIFICATES"]:
        if row["owner_id"] != TARGET_STATE_ID:
            continue
        counts = hunter.dense(row["member"]["witness_counts"])
        if (
            counts not in raw
            or row["region_sha256"] != fingerprint
            or int(row["member_new_bound"]) > raw[counts]
        ):
            raise AssertionError("R24 member certificate is outside the source region")
        bounds[counts] = min(bounds[counts], int(row["member_new_bound"]))
    source_term = next(
        int(row["bound"])
        for row in authority["FINAL_STATE_TERMS"]
        if row["stable_id"] == TARGET_STATE_ID
    )
    if (
        any(bounds[m.counts] != m.final_bound for m in members)
        or sum(m.final_bound != m.raw_bound for m in members) != region["certified_member_count"]
        or max(bounds.values()) != region["final_state_bound"]
        or max(bounds.values()) != source_term
    ):
        raise AssertionError("sealed source member bounds differ from complete ledger replay")
    return members


def seven_members(members: tuple[LedgerMember, ...]) -> tuple[LedgerMember, ...]:
    """Require both the exact named family and the source's full maximizing set."""

    expected = {
        hunter.dense([[i, n] for i, n in ((0, EVENT_COUNT), (1, a), (4, 6 - a), (20, 1)) if n])
        for a in range(7)
    }
    maximum = max(m.final_bound for m in members)
    cohort = tuple(m for m in members if m.final_bound == maximum)
    if (
        {m.counts for m in cohort} != expected
        or len(cohort) != len(expected)
        or any(m.represented_vector_count != 1 or m.final_bound != m.raw_bound for m in cohort)
    ):
        raise AssertionError("seven-member coverage or existing correction identity failed")
    return cohort


@cache
def eleven_event_proof() -> dict[str, Any]:
    cells = hunter.type_cells(0)
    if cells != (0, 0, 0, hunter.TICKET_SIZE):
        raise AssertionError("type-0 residual events are not entirely outside anchors")
    rows = hunter.exact_pair_rows(((0, 0),))
    floors = hunter.pair_floors(rows)
    hunter.require_safe_pair_floors(floors, rows)
    if len(rows) != hunter.family_pair_overlap_ceiling() + 1 or any(
        hunter.six.residual_pair_intersection(row[0], row[1], row[2:6]) != row[6] for row in rows
    ):
        raise AssertionError("exact type-0 residual pair identity failed")
    incidences = EVENT_COUNT * cells[3]
    labels = len(hunter.CELL_LABELS[3])
    quotient, remainder = divmod(incidences, labels)
    mass = hunter.balanced_collision_mass(incidences, labels)
    cases = prior.threshold_cases(floors, mass, EVENT_COUNT)
    floor = min(int(row["hunter_floor"]) for row in cases)
    relaxation = hunter.minimum_tree_correction(floors, mass, EVENT_COUNT)
    if floor != relaxation.correction:
        raise AssertionError("threshold cases differ from the exact integer Hunter relaxation")
    return {
        "event_count": EVENT_COUNT,
        "type_index": 0,
        "type_cells": list(cells),
        "residual_event_definition": hunter.RESIDUAL_EVENT_DEFINITION,
        "residual_event_size": hunter.residual_event_size(0),
        "outside_incidences": incidences,
        "outside_label_count": labels,
        "balanced_frequencies": [[quotient, labels - remainder], [quotient + 1, remainder]],
        "collision_mass_floor": mass,
        "pair_rows": [list(row) for row in rows],
        "pair_floors": list(floors),
        "rank_rule": "rho(e) = min{r: C(r+1,2) >= e}; e1+e2+e3 >= Q",
        "rank_algebra_rows": hunter.verify_rank_floor_algebra(EVENT_COUNT),
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


def certify_vector(
    member: LedgerMember, vector: CountVector, proof: dict[str, Any]
) -> dict[str, Any]:
    state = catalog.rebuild_member(replace(member, counts=vector, represented_vector_count=1))
    if (
        hunter.eleven.compression_signature(state)
        != hunter.eleven.compression_signature(catalog.rebuild_member(member))
        or vector[0] != proof["event_count"]
        or sum(vector) != hunter.RESIDUAL_EVENT_COUNT
        or member.final_bound != member.raw_bound
    ):
        raise AssertionError("represented vector compression or eleven-event identity failed")
    # These source owners have no additional R14 credit: final == raw and the
    # complete carried-certificate replay above reproduces that equality.
    corrections = {
        "R6_PAIR": state.residual_pair_union_penalty,
        "FOREST": state.complementary_forest_floor,
        "EXISTING_R14": 0,
        "ELEVEN_EVENT_HUNTER": int(proof["hunter_floor"]),
    }
    existing = hunter.combine_corrections(
        {k: v for k, v in corrections.items() if k != "ELEVEN_EVENT_HUNTER"}
    )
    uncorrected = hunter.r14.joint_constant() - state.anchor_pair_s2 + state.anchor_triple_s3
    residual_sum = sum(
        count * hunter.residual_event_size(i) for i, count in enumerate(vector) if count
    )
    combined = hunter.combine_corrections(corrections)
    bound = hunter.member_bound(uncorrected, combined)
    if (
        hunter.anchor_union_size() + residual_sum != uncorrected
        or existing != state.applied_residual_union_penalty
        or uncorrected - existing != member.final_bound
        or bound >= member.final_bound
    ):
        raise AssertionError("residual identity or max single replacement failed")
    support = hunter.r12.construct_support_witness(vector)
    if support is None:
        raise AssertionError("represented vector has no exact support witness")
    witness = prior.witness_analysis(vector, support, proof)
    return {
        "vector_id": hunter.member_id(vector),
        "counts": hunter.sparse(vector),
        "eleven_event_indices": list(range(int(proof["event_count"]))),
        "eleven_event_types": [0] * int(proof["event_count"]),
        "outside_incidences": vector[0] * hunter.type_cells(0)[3],
        "collision_mass_floor": proof["collision_mass_floor"],
        "anchor_union": hunter.anchor_union_size(),
        "residual_event_sum": residual_sum,
        "uncorrected_anchor_bound": uncorrected,
        "corrections": corrections,
        "prior_applied_correction": existing,
        "combined_correction": combined,
        "vector_new_bound": bound,
        "support_witness": support,
        "support_sha256": hunter.digest(support),
        "witness_analysis": witness,
    }


def certify_member(
    member: LedgerMember, vectors: tuple[CountVector, ...], proof: dict[str, Any]
) -> dict[str, Any]:
    if (
        len(vectors) != member.represented_vector_count
        or len(set(vectors)) != len(vectors)
        or tuple(sorted(vectors)) != vectors
        or min(vectors) != member.counts
    ):
        raise AssertionError("compressed member does not cover its exact represented vectors")
    records = [certify_vector(member, vector, proof) for vector in vectors]
    correction = hunter.member_correction(tuple(int(r["combined_correction"]) for r in records))
    bound = max(int(r["vector_new_bound"]) for r in records)
    if bound != hunter.member_bound(int(records[0]["uncorrected_anchor_bound"]), correction):
        raise AssertionError("compressed member did not use its weakest vector correction")
    return {
        "member_id": hunter.member_id(member.counts),
        "witness_counts": hunter.sparse(member.counts),
        "represented_vector_count": len(vectors),
        "represented_vectors": [hunter.sparse(v) for v in vectors],
        "vector_certificates": records,
        "member_prior_bound": member.final_bound,
        "member_raw_bound": member.raw_bound,
        "member_certified_correction": correction,
        "member_new_bound": bound,
        "correction_combination": CORRECTION_COMBINATION,
    }


def recompute_family(state_bound: int) -> dict[str, Any]:
    authority = source_authority()
    terms = tuple((str(r["stable_id"]), int(r["bound"])) for r in authority["FINAL_STATE_TERMS"])
    if len(terms) != 23 or len(dict(terms)) != 23 or TARGET_STATE_ID not in dict(terms):
        raise AssertionError("complete 23-State family identity failed")
    classified = hunter.six.classified_terms()
    tail = hunter.six.sealed_tail_bound()
    start = hunter.six.tail.family_maximum(tail, terms, classified)
    aggregate = [
        {"stable_id": key, "bound": bound} for key, bound in classified if key == r24.AGGREGATE_ID
    ]
    if (
        start != authority["FINAL_FAMILY_MAX_RECOMPUTATION"]
        or hunter.digest(classified) != authority["CLASSIFIED_TERMS_SHA256"]
        or tail != authority["TAIL_BOUND"]
        or aggregate != authority["CLASSIFIED_AGGREGATE"]
    ):
        raise AssertionError("source complete family, Tail or aggregate differs from replay")
    replaced = tuple((key, state_bound if key == TARGET_STATE_ID else b) for key, b in terms)
    final = hunter.six.tail.family_maximum(tail, replaced, classified)
    return {
        "start": start,
        "final": final,
        "start_terms": terms,
        "terms": replaced,
        "tail_bound": tail,
        "classified_count": len(classified),
        "classified_sha256": hunter.digest(classified),
        "aggregate": aggregate,
    }


def build_result() -> dict[str, Any]:
    fingerprints = verify_upstream_fingerprints()
    members = region_members()
    cohort = seven_members(members)
    recovered = catalog.r17.represented_vectors(tuple(catalog.rebuild_member(m) for m in cohort))
    flat = [v for vectors in recovered.values() for v in vectors]
    if (
        set(recovered) != {m.counts for m in cohort}
        or len(flat) != len(cohort)
        or len(set(flat)) != len(flat)
    ):
        raise AssertionError("exact seven-member/seven-vector coverage failed")
    proof = eleven_event_proof()
    records = [certify_member(m, recovered[m.counts], proof) for m in cohort]
    priors = {m.counts: m.final_bound for m in members}
    bounds = hunter.six.replaced_bounds(priors, records)
    certified = set(recovered)
    remainder = tuple(m for m in members if m.counts not in certified)
    if any(bounds[m.counts] != m.final_bound for m in remainder):
        raise AssertionError("a preserved remainder member changed")
    family = recompute_family(max(bounds.values()))
    if max(priors.values()) != dict(family["start_terms"])[TARGET_STATE_ID]:
        raise AssertionError("complete source region maximum differs from its State term")
    return catalog.normalized(
        {
            "TASK_ID": TASK_ID,
            "TASK_STATUS": "SUCCESS",
            "REMAINING_TASK_MODEL": "最強模型",
            "TASK_BRANCH": TASK_BRANCH,
            "BASE_HEAD": BASE_HEAD,
            "BASE_TREE": BASE_TREE,
            "BASE_RESULT_SHA256": BASE_RESULT_SHA256,
            "UPSTREAM_FINGERPRINTS_SHA256": fingerprints,
            "STATE_ID": TARGET_STATE_ID,
            "REGION_SHA256": catalog.region_fingerprint(members),
            "REGION_COMPRESSED_MEMBER_COUNT": len(members),
            "REGION_REPRESENTED_VECTOR_COUNT": sum(m.represented_vector_count for m in members),
            "SEVEN_MEMBER_COVERAGE": [len(records), len(flat)],
            "ELEVEN_EVENT_PROOF": proof,
            "COLLISION_MASS_STATUS": "PASS",
            "HUNTER_FLOOR": proof["hunter_floor"],
            "MEMBER_CERTIFICATES": records,
            "NEW_SEVEN_MEMBER_MAX": max(int(r["member_new_bound"]) for r in records),
            "PRESERVED_MEMBER_COUNT": len(remainder),
            "PRESERVED_VECTOR_COUNT": sum(m.represented_vector_count for m in remainder),
            "PRESERVED_REMAINDER_MAX": max(bounds[m.counts] for m in remainder),
            "PRESERVED_REMAINDER_SHA256": hunter.digest(
                tuple(
                    (m.counts, m.represented_vector_count, m.raw_bound, m.final_bound)
                    for m in remainder
                )
            ),
            "COMPLETE_REGION_MEMBERS": [
                {
                    "member_id": hunter.member_id(m.counts),
                    "witness_counts": hunter.sparse(m.counts),
                    "represented_vector_count": m.represented_vector_count,
                    "raw_bound": m.raw_bound,
                    "prior_bound": m.final_bound,
                    "final_bound": bounds[m.counts],
                }
                for m in members
            ],
            "FINAL_STATE_BOUND": max(bounds.values()),
            "START_STATE_TERMS": [{"stable_id": k, "bound": b} for k, b in family["start_terms"]],
            "FINAL_STATE_TERMS": [{"stable_id": k, "bound": b} for k, b in family["terms"]],
            "STATE_TERM_COUNT": len(family["terms"]),
            "TAIL_BOUND": family["tail_bound"],
            "CLASSIFIED_TERM_COUNT": family["classified_count"],
            "CLASSIFIED_TERMS_SHA256": family["classified_sha256"],
            "CLASSIFIED_AGGREGATE": family["aggregate"],
            "CLASSIFIED_MAX": family["final"]["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"],
            "START_FAMILY_MAX_RECOMPUTATION": family["start"],
            "FINAL_FAMILY_MAX_RECOMPUTATION": family["final"],
            "START_R3_UB": family["start"]["R3_BOUND"],
            "FINAL_R3_UB": family["final"]["R3_BOUND"],
            "FINAL_OWNER_IDS": family["final"]["OWNER_IDS"],
            "CURRENT_INCUMBENT": r24.INCUMBENT,
            "REMAINING_GAP": int(family["final"]["R3_BOUND"]) - r24.INCUMBENT,
            "CORRECTION_COMBINATION": CORRECTION_COMBINATION,
            "DUPLICATE_CORRECTIONS": 0,
            "NON_DUPLICATE_CREDIT_STATUS": "PASS_MAX_SINGLE_REPLACEMENT",
            "WITNESS_SOUNDNESS_STATUS": "PASS_7_EXACT_SUPPORT_WITNESSES",
            "VECTOR_RECOVERY": "R17_EXACT_SELECTED_LOSS_AND_COMPRESSION_SIGNATURE",
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
            vector = hunter.dense(row["counts"])
            support = tuple(tuple(int(label) for label in t) for t in row["support_witness"])
            if (
                not hunter.r8.validate_support_assignment(vector, support)
                or hunter.digest(support) != row["support_sha256"]
            ):
                raise AssertionError("stored support witness or fingerprint is invalid")
    if result != build_result():
        raise AssertionError("stored certificate differs from complete exact replay")
    return {"status": "PASS", "certificates": 7, "vectors": 7}


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
        RESULT_PATH.write_text(hunter.encode(result), encoding="utf-8")
    keys = (
        "TASK_STATUS",
        "HUNTER_FLOOR",
        "NEW_SEVEN_MEMBER_MAX",
        "PRESERVED_REMAINDER_MAX",
        "START_R3_UB",
        "FINAL_R3_UB",
        "FINAL_OWNER_IDS",
        "REMAINING_GAP",
    )
    print(json.dumps({k: result[k] for k in keys}, sort_keys=True))


if __name__ == "__main__":
    main()
