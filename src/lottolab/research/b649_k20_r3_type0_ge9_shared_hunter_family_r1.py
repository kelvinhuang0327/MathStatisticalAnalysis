"""Universal nine-event Hunter credit over the complete immutable R3 region.

Recover every represented vector at the ledger's exact loss/signature, without
a census or solver. Any nine type-0 tickets have 54 incidences on 40 labels,
so Q >= 14. Exact residual pair costs and nested threshold forest ranks give
one universal correction, extended to all 18 residual events. Concrete supports
check applicability but never supply extra credit. Keep all carried R14 and
eleven-event Hunter credit by max; a compressed member takes its weakest vector.
Replay the complete 989-member region and the sealed 23-State family.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from functools import cache
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_r3_state_13169800_seven_member_11event_hunter_r1 as prior
from lottolab.research.b649_k20_r3_state_13548976_top_band_certificate_r1 import (
    LedgerMember as LedgerMember,
)

hunter, catalog, r24 = prior.hunter, prior.catalog, prior.r24
type CountVector = tuple[int, ...]
TASK_ID = "B649_K20_R3_TYPE0_GE9_SHARED_HUNTER_FAMILY_R1"
TASK_BRANCH = "codex/b649-k20-r3-type0-ge9-shared-hunter-family-r1"
BASE_HEAD = "9117673c98aa0a1a1dfb959fcd8b9f208258c91f"
BASE_TREE = "dfc51590ea19dccdccfc164af83baeede467678e"
BASE_RESULT_SHA256 = "62989e8481d07290a6f63e9affb5fdc32dee4c799a1921c8d124dd6a2323930c"
TARGET_STATE_ID = prior.TARGET_STATE_ID
REGION_SHA256 = "c183f8d2f93d3a695fcae3e2d2d280d40ffb1de3527eb43e61ce5321569dcde1"
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_RELATIVE = hunter.six.RESULTS + "b649-k20-r3-type0-ge9-shared-hunter-family-r1-result.json"
RESULT_PATH = REPO_ROOT / RESULT_RELATIVE
UPSTREAM_SHA256 = {
    **prior.UPSTREAM_SHA256,
    prior.RESULT_RELATIVE: BASE_RESULT_SHA256,
    "src/lottolab/research/b649_k20_r3_state_13169800_seven_member_11event_hunter_r1.py": (
        "ac9a5236dc79c31382348b76414b3008dde86f9c228a5d48314eeac055f51965"
    ),
}
CORRECTION_COMBINATION = "MAX(R6_PAIR, FOREST, EXISTING_R14, EXISTING_HUNTER, NINE_EVENT_HUNTER)"


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
        or stored["REGION_SHA256"] != REGION_SHA256
        or prior.verify_result(stored)["status"] != "PASS"
    ):
        raise AssertionError("immutable complete R3 source failed replay")
    return stored


@cache
def region_members() -> tuple[LedgerMember, ...]:
    members = prior.region_members()
    authority = source_authority()
    bounds = hunter.six.replaced_bounds(
        {m.counts: m.final_bound for m in members}, authority["MEMBER_CERTIFICATES"]
    )
    replay = [
        {
            "member_id": hunter.member_id(m.counts),
            "witness_counts": hunter.sparse(m.counts),
            "represented_vector_count": m.represented_vector_count,
            "raw_bound": m.raw_bound,
            "prior_bound": m.final_bound,
            "final_bound": bounds[m.counts],
        }
        for m in members
    ]
    if (
        len(members) != 989
        or sum(m.represented_vector_count for m in members) != 1072
        or catalog.region_fingerprint(members) != REGION_SHA256
        or catalog.normalized(replay) != authority["COMPLETE_REGION_MEMBERS"]
        or max(bounds.values()) != authority["FINAL_STATE_BOUND"]
    ):
        raise AssertionError("complete source region or current bounds differ from replay")
    return members


@cache
def region_vectors() -> dict[CountVector, tuple[CountVector, ...]]:
    members = region_members()
    recovered = catalog.r17.represented_vectors(tuple(catalog.rebuild_member(m) for m in members))
    flat = [v for vectors in recovered.values() for v in vectors]
    if (
        set(recovered) != {m.counts for m in members}
        or len(flat) != 1072
        or len(set(flat)) != len(flat)
        or any(len(recovered[m.counts]) != m.represented_vector_count for m in members)
    ):
        raise AssertionError("complete represented-vector recovery failed")
    return recovered


@cache
def nine_event_proof() -> dict[str, Any]:
    # The pinned counter recounts the four rows and compares independent R8
    # and residual inclusion/exclusion counts. It also solves the small integer
    # threshold relaxation, not a support optimization or an outcome census.
    proof = prior.prior.nine_event_proof()
    n, incidences, labels = (
        int(proof[key]) for key in ("event_count", "outside_incidences", "outside_label_count")
    )
    floors = proof["pair_floors"]
    mass = hunter.balanced_collision_mass(incidences, labels)
    if (
        n != 9
        or incidences != n * hunter.TICKET_SIZE
        or labels != len(hunter.CELL_LABELS[3])
        or mass != incidences - labels
        or proof["collision_mass_floor"] != mass
        or proof["hunter_floor"]
        != (n - 1) * floors[0] + hunter.rank_floor(mass) * (floors[1] - floors[0])
        or any(row["hunter_floor"] < proof["hunter_floor"] for row in proof["threshold_cases"])
    ):
        raise AssertionError("universal nine-event collision or threshold proof failed")
    return {
        **proof,
        "scope": "Every R3 support with at least nine type-0 tickets; select any nine",
        "pair_overlap_ceiling": hunter.family_pair_overlap_ceiling(),
        "collision_rule": "SUM_x C(d_x,2) >= SUM_x(d_x-1) = 54-40 = 14",
        "rank_rule": "rho(e) = min{r: C(r+1,2) >= e}; e1+e2+e3 = Q >= 14",
        "rank_algebra_rows": hunter.verify_rank_floor_algebra(n),
        "hunter_rule": hunter.HUNTER_RULE,
        "pointwise_hunter_proof": (
            "For each outcome present in k>=1 events, the induced subgraph of a tree has "
            "at most k-1 edges. Sum this inequality over outcomes."
        ),
        "threshold_tree_proof": (
            "Descending Kruskal retains a spanning forest of each nested G_k; "
            "rank(G_k) >= rho(e_k) since SUM C(r_j+1,2) <= C(SUM r_j+1,2)."
        ),
        "floor_algebra": [
            (n - 1) * floors[0],
            hunter.rank_floor(mass),
            floors[1] - floors[0],
            proof["hunter_floor"],
        ],
    }


@cache
def support_witness(vector: CountVector) -> tuple[tuple[int, ...], ...]:
    support = hunter.r12.construct_support_witness(vector)
    if support is None or not hunter.r8.validate_support_assignment(vector, support):
        raise AssertionError("represented vector has no validated support witness")
    return support


def certify_vector(
    member: LedgerMember, vector: CountVector, prior_bound: int, proof: dict[str, Any]
) -> dict[str, Any]:
    state = catalog.rebuild_member(replace(member, counts=vector, represented_vector_count=1))
    if (
        vector not in region_vectors()[member.counts]
        or hunter.eleven.compression_signature(state)
        != hunter.eleven.compression_signature(catalog.rebuild_member(member))
        or sum(vector) != hunter.RESIDUAL_EVENT_COUNT
        or any(count < 0 for count in vector)
    ):
        raise AssertionError("represented vector compression or residual identity failed")
    ceiling = hunter.family_pair_overlap_ceiling()
    types = tuple(i for i, count in enumerate(vector) for _ in range(count))
    for type_index in set(types):
        s, a, b, outside = hunter.type_cells(type_index)
        if s + a + b + outside != hunter.TICKET_SIZE or max(s + a, s + b) > ceiling:
            raise AssertionError("residual ticket type violates fixed R3 anchor definition")
    uncorrected = hunter.r14.joint_constant() - state.anchor_pair_s2 + state.anchor_triple_s3
    residual_sum = sum(count * hunter.residual_event_size(i) for i, count in enumerate(vector))
    # The complete source replay proves these carried R14 member bounds for
    # every represented vector. Translate their bound into the same residual
    # correction; redundant R6/forest credit is harmless under max.
    carried_r14 = uncorrected - member.final_bound if member.final_bound < member.raw_bound else 0
    existing_hunter = {
        hunter.dense(row["witness_counts"]): int(row["member_certified_correction"])
        for row in source_authority()["MEMBER_CERTIFICATES"]
    }.get(member.counts, 0)
    corrections = {
        "R6_PAIR": state.residual_pair_union_penalty,
        "FOREST": state.complementary_forest_floor,
        "EXISTING_R14": carried_r14,
        "EXISTING_HUNTER": existing_hunter,
    }
    existing = hunter.combine_corrections(corrections)
    n = int(proof["event_count"])
    eligible = vector[0] >= n
    if eligible and (
        types[:n] != (0,) * n
        or hunter.type_cells(0) != (0, 0, 0, hunter.TICKET_SIZE)
        or n * hunter.type_cells(0)[3] != proof["outside_incidences"]
        or ceiling != proof["pair_overlap_ceiling"]
    ):
        raise AssertionError("selected nine residual events violate applicability")
    corrections["NINE_EVENT_HUNTER"] = int(proof["hunter_floor"]) if eligible else 0
    combined = hunter.combine_corrections(corrections)
    bound = hunter.member_bound(uncorrected, combined)
    if (
        hunter.anchor_union_size() + residual_sum != uncorrected
        or uncorrected - existing != prior_bound
        or bound > prior_bound
        or (not eligible and bound != prior_bound)
    ):
        raise AssertionError("event identity or max single replacement failed")
    record = {
        "vector_id": hunter.member_id(vector),
        "counts": hunter.sparse(vector),
        "type0_count": vector[0],
        "eligible": eligible,
        "applicability_status": "PASS" if eligible else "UNCHANGED_FEWER_THAN_NINE_TYPE0",
        "nine_event_indices": list(range(n)) if eligible else [],
        "nine_event_types": list(types[:n]) if eligible else [],
        "outside_incidences": proof["outside_incidences"] if eligible else 0,
        "collision_mass_floor": proof["collision_mass_floor"] if eligible else 0,
        "pair_overlap_ceiling": ceiling,
        "anchor_union": hunter.anchor_union_size(),
        "residual_event_sum": residual_sum,
        "uncorrected_anchor_bound": uncorrected,
        "corrections": corrections,
        "prior_applied_correction": existing,
        "combined_correction": combined,
        "vector_prior_bound": prior_bound,
        "vector_new_bound": bound,
        "improved": bound < prior_bound,
    }
    if eligible:
        support = support_witness(vector)
        witness = prior.prior.witness_analysis(vector, support, proof)
        record.update(
            support_witness=support,
            support_sha256=hunter.digest(support),
            witness_analysis=witness,
        )
    return record


def certify_member(
    member: LedgerMember, vectors: tuple[CountVector, ...], prior_bound: int, proof: dict[str, Any]
) -> dict[str, Any]:
    if (
        vectors != region_vectors()[member.counts]
        or len(vectors) != member.represented_vector_count
    ):
        raise AssertionError("compressed member must cover all exact represented vectors")
    records = [certify_vector(member, v, prior_bound, proof) for v in vectors]
    correction = hunter.member_correction(tuple(int(r["combined_correction"]) for r in records))
    bound = max(int(r["vector_new_bound"]) for r in records)
    if bound != hunter.member_bound(int(records[0]["uncorrected_anchor_bound"]), correction):
        raise AssertionError("compressed member must take its weakest vector correction")
    return {
        "member_id": hunter.member_id(member.counts),
        "witness_counts": hunter.sparse(member.counts),
        "represented_vector_count": len(vectors),
        "vector_certificates": records,
        "eligible": all(r["eligible"] for r in records),
        "member_prior_bound": prior_bound,
        "member_raw_bound": member.raw_bound,
        "member_certified_correction": correction,
        "member_new_bound": bound,
        "improved": bound < prior_bound,
    }


def recompute_family(state_bound: int) -> dict[str, Any]:
    authority = source_authority()
    family = prior.recompute_family(state_bound)
    terms = tuple((str(r["stable_id"]), int(r["bound"])) for r in authority["FINAL_STATE_TERMS"])
    classified = hunter.six.classified_terms()
    start = hunter.six.tail.family_maximum(family["tail_bound"], terms, classified)
    replaced = tuple((key, state_bound if key == TARGET_STATE_ID else b) for key, b in terms)
    final = hunter.six.tail.family_maximum(family["tail_bound"], replaced, classified)
    if (
        len(terms) != 23
        or len(dict(terms)) != 23
        or TARGET_STATE_ID not in dict(terms)
        or start != authority["FINAL_FAMILY_MAX_RECOMPUTATION"]
        or final != family["final"]
    ):
        raise AssertionError("complete 23-State source/final family differs from replay")
    competitor = max((b, key) for key, b in terms if key != TARGET_STATE_ID)
    return {
        **family,
        "start": start,
        "start_terms": terms,
        "terms": replaced,
        "competitor": {"stable_id": competitor[1], "bound": competitor[0]},
    }


def build_result() -> dict[str, Any]:
    fingerprints = verify_upstream_fingerprints()
    authority = source_authority()
    members, recovered, proof = region_members(), region_vectors(), nine_event_proof()
    priors = {
        hunter.dense(r["witness_counts"]): int(r["final_bound"])
        for r in authority["COMPLETE_REGION_MEMBERS"]
    }
    records = [certify_member(m, recovered[m.counts], priors[m.counts], proof) for m in members]
    vectors = [v for row in records for v in row["vector_certificates"]]
    bounds = {hunter.dense(r["witness_counts"]): int(r["member_new_bound"]) for r in records}
    family = recompute_family(max(bounds.values()))
    if max(priors.values()) != dict(family["start_terms"])[TARGET_STATE_ID]:
        raise AssertionError("source region maximum differs from source State term")
    preserved_seven = authority["MEMBER_CERTIFICATES"]
    if any(
        bounds[hunter.dense(r["witness_counts"])] != int(r["member_new_bound"])
        for r in preserved_seven
    ):
        raise AssertionError("stronger seven-member Hunter credit was not preserved")
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
            "REGION_COMPRESSED_MEMBER_COUNT": len(records),
            "REGION_REPRESENTED_VECTOR_COUNT": len(vectors),
            "VECTOR_RECOVERY": "R17_EXACT_SELECTED_LOSS_AND_COMPRESSION_SIGNATURE",
            "NINE_EVENT_PROOF": proof,
            "UNIVERSAL_NINE_EVENT_PROOF_STATUS": "PASS",
            "CORRECTION_FLOOR": proof["hunter_floor"],
            "ELIGIBLE_MEMBER_COUNT": sum(r["eligible"] for r in records),
            "ELIGIBLE_VECTOR_COUNT": sum(v["eligible"] for v in vectors),
            "CHANGED_MEMBER_COUNT": sum(r["improved"] for r in records),
            "CHANGED_VECTOR_COUNT": sum(v["improved"] for v in vectors),
            "UNCHANGED_MEMBER_COUNT": sum(not r["improved"] for r in records),
            "UNCHANGED_VECTOR_COUNT": sum(not v["improved"] for v in vectors),
            "MEMBER_CERTIFICATES": records,
            "PRESERVED_SEVEN_CERTIFICATES_SHA256": hunter.digest(preserved_seven),
            "PRESERVED_SEVEN_MEMBER_COUNT": len(preserved_seven),
            "PRESERVED_SEVEN_CORRECTION_FLOOR": authority["HUNTER_FLOOR"],
            "COMPRESSED_MEMBER_STATUS": "PASS_ALL_REPRESENTED_VECTORS_WEAKEST_CORRECTION",
            "CORRECTION_COMBINATION": CORRECTION_COMBINATION,
            "NON_DUPLICATE_CREDIT_STATUS": "PASS_MAX_SINGLE_REPLACEMENT",
            "DUPLICATE_CORRECTIONS": 0,
            "FINAL_STATE_BOUND": max(bounds.values()),
            "START_STATE_TERMS": [{"stable_id": k, "bound": b} for k, b in family["start_terms"]],
            "FINAL_STATE_TERMS": [{"stable_id": k, "bound": b} for k, b in family["terms"]],
            "STATE_TERM_COUNT": len(family["terms"]),
            "FULL_23_STATE_RECOMPUTATION": "PASS",
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
            "CURRENT_INCUMBENT": r24.INCUMBENT,
            "REMAINING_GAP": int(family["final"]["R3_BOUND"]) - r24.INCUMBENT,
            "WITNESS_SOUNDNESS_STATUS": "PASS_ALL_ELIGIBLE_SUPPORTS_AND_UNIVERSAL_APPLICABILITY",
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
            if not row["eligible"]:
                continue
            vector = hunter.dense(row["counts"])
            support = tuple(tuple(int(x) for x in ticket) for ticket in row["support_witness"])
            if (
                not hunter.r8.validate_support_assignment(vector, support)
                or hunter.digest(support) != row["support_sha256"]
            ):
                raise AssertionError("stored support witness or fingerprint is invalid")
    if result != build_result():
        raise AssertionError("stored certificate differs from complete exact replay")
    return {"status": "PASS", "members": 989, "vectors": 1072}


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
        "CORRECTION_FLOOR",
        "ELIGIBLE_MEMBER_COUNT",
        "ELIGIBLE_VECTOR_COUNT",
        "CHANGED_MEMBER_COUNT",
        "CHANGED_VECTOR_COUNT",
        "FINAL_STATE_BOUND",
        "FINAL_COMPLETE_R3_UB",
        "FINAL_OWNER_IDS",
        "REMAINING_GAP",
    )
    print(json.dumps({k: result[k] for k in keys}, sort_keys=True))


if __name__ == "__main__":
    main()
