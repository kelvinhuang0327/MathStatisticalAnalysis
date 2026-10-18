"""Exact R14 certificates for the next eleven members of the current R3 State.

The immutable six-member result supplies the starting 1,427-member catalog and
23 State terms. Only its eleven tied current owners are replaced. R17 recovers
their twelve vectors at their exact loss, without a full R7 census. Every vector
replays its compression signature, R6/forest penalty, residual pair moment,
multiplicity dual, and concrete support witness. Each compressed member takes
the weakest vector bound; the correction replaces the old penalty once by max.
The other 1,416 members (including the six original certificates), Tail, and
classified terms are preserved. No solver or official outcome enumeration runs.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from functools import cache
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_r3_current_owner_six_member_r14_certificate_r1 as six
from lottolab.research import b649_k20_r3_joint_residual_envelope_r7 as r7
from lottolab.research import b649_k20_r3_state_13548976_top_band_certificate_r1 as catalog

r14, r12, r8 = six.r14, six.r12, six.r8
CountVector = six.CountVector
dense, sparse, digest, member_id = six.dense, six.sparse, six.digest, six.member_id
ceiling_divide_by_9, combine_corrections = six.ceiling_divide_by_9, six.combine_corrections
member_bound, exact_residual_pair_moment = six.member_bound, six.exact_residual_pair_moment
TASK_ID = "B649_K20_R3_CURRENT_STATE_NEXT_ELEVEN_R14_CERTIFICATE_R1"
TASK_BRANCH = "codex/b649-k20-r3-current-state-next-eleven-r14-certificate-r1"
BASE_HEAD = "f969d737baa79ea08815b598df15bd04e8e9cd06"
BASE_TREE = "c7361905fd93e7ac34b5d79d8d8cbd0b6aebaf89"
SIX_RESULT_SHA256 = "b2461360ca3fb0b426477d7ded14aa50935a7925f8c7c13f3ec26e03f5622484"
TARGET_STATE_ID, REGION_SHA256 = six.TARGET_STATE_ID, six.REGION_SHA256
REGION_MEMBER_COUNT, REGION_VECTOR_COUNT = six.REGION_MEMBER_COUNT, six.REPRESENTED_VECTOR_COUNT
COHORT_MEMBER_COUNT, COHORT_VECTOR_COUNT = 11, 12
RESIDUAL_EVENT_DEFINITION = six.RESIDUAL_EVENT_DEFINITION
R14_CORRECTION_RULE, CORRECTION_COMBINATION = six.R14_CORRECTION_RULE, six.CORRECTION_COMBINATION
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_RELATIVE = (
    six.RESULTS + "b649-k20-r3-current-state-next-eleven-r14-certificate-r1-result.json"
)
RESULT_PATH = REPO_ROOT / RESULT_RELATIVE
_SOURCES = "src/lottolab/research/"
UPSTREAM_SHA256 = {
    **catalog.UPSTREAM_SHA256,
    **six.UPSTREAM_SHA256,
    six.RESULT_RELATIVE: SIX_RESULT_SHA256,
    _SOURCES + "b649_k20_r3_current_owner_six_member_r14_certificate_r1.py": (
        "971668a9c858b6b055398ec41fcfd63c870674f17efe9f6747932234c19c3177"
    ),
    _SOURCES + "b649_k20_r3_anchor_incidence_bound_r5.py": (
        "569d525f1e9905d043fe0f6132c936d5b260ba3d4b3a376da6c961db8aa5c435"
    ),
    _SOURCES + "b649_k20_r3_exact_anchor_neighborhood_envelope_r6.py": (
        "a83f6f2a7091aedf034e0905d80993df5001382fedc297fdd503202665e6622c"
    ),
    _SOURCES + "b649_k20_r3_tail_state_owner_chase_r16.py": (
        "7296c471b63e728e8d873878d96bf3ab84a78a951a288d4dd87aeea1cd882b9f"
    ),
    _SOURCES + "b649_k20_r3_hunter_top16_complete_integration_r1.py": (
        "670b1531498bbf741faacc5a57442eafe5caa5d9f39d6c12ef5daaf60b4c1e6f"
    ),
}
# Regression references only; all bounds and correction floors are recomputed.
EXPECTED_START_UB = 355_630_646
EXPECTED_FINAL_UB = 355_630_198
EXPECTED_CORRECTION_FLOOR = 5_012_214
EXPECTED_CERTIFIED_MAX = 353_488_432
EXPECTED_REMAINING_GAP = 42_366_310
SUMMARY_FIELDS = (
    "TASK_STATUS",
    "REGION_IDENTITY",
    "NEXT_ELEVEN_MEMBER_COUNT",
    "REPRESENTED_VECTOR_COUNT",
    "COVERAGE_STATUS",
    "CORRECTION_FLOORS",
    "CERTIFIED_MEMBER_MAX",
    "PRESERVED_COHORT_MAX",
    "START_R3_FAMILY_UB",
    "FINAL_R3_FAMILY_UB",
    "FINAL_OWNER_IDS",
    "REMAINING_GAP",
    "NEW_HEAVY_SOLVER_STARTED",
    "PRODUCTION_MUTATION",
)


def verify_upstream_fingerprints() -> dict[str, str]:
    observed = {
        relative: sha256((REPO_ROOT / relative).read_bytes()).hexdigest()
        for relative in UPSTREAM_SHA256
    }
    if observed != UPSTREAM_SHA256:
        raise AssertionError("immutable source fingerprint mismatch")
    return observed


@cache
def six_authority() -> dict[str, Any]:
    verify_upstream_fingerprints()
    stored = cast(dict[str, Any], json.loads((REPO_ROOT / six.RESULT_RELATIVE).read_text()))
    if stored["TASK_ID"] != six.TASK_ID or six.verify_result(stored)["status"] != "PASS":
        raise AssertionError("six-member source certificate failed replay")
    return stored


def current_member_bounds(members: tuple[catalog.LedgerMember, ...]) -> dict[CountVector, int]:
    """Replay the entire source catalog, including its six replaced bounds."""

    authority = six_authority()
    priors = six.current_member_bounds(members)
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
        raise AssertionError("six-member source catalog differs from its replay")
    return source_bounds


def next_eleven_members(
    members: tuple[catalog.LedgerMember, ...], priors: dict[CountVector, int]
) -> tuple[catalog.LedgerMember, ...]:
    maximum = max(priors.values())
    cohort = tuple(member for member in members if priors[member.counts] == maximum)
    previous = {
        dense(row["witness_counts"]) for row in six_authority()["MEMBER_CERTIFICATES"]
    } | set(six.sealed_top_band_bounds())
    if (
        set(priors) != {member.counts for member in members}
        or len(cohort) != COHORT_MEMBER_COUNT
        or sum(member.represented_vector_count for member in cohort) != COHORT_VECTOR_COUNT
        or any(member.counts in previous for member in cohort)
        or any(priors[member.counts] != member.raw_bound for member in cohort)
        or any(member.final_bound != member.raw_bound for member in cohort)
    ):
        raise AssertionError("next eleven-member coverage or unused correction identity failed")
    return cohort


def compression_signature(state: r7.ResidualJointState) -> tuple[object, ...]:
    signature_api = "_state_signature"
    return cast(tuple[object, ...], getattr(r7, signature_api)(state))


def compressed_correction(corrections: tuple[int, ...]) -> int:
    """Use the weakest correction, including when represented floors differ."""

    if not corrections or min(corrections) < 0:
        raise ValueError("compressed correction requires non-negative vector floors")
    return min(corrections)


def certify_member(
    member: catalog.LedgerMember, vectors: tuple[CountVector, ...]
) -> dict[str, Any]:
    state = catalog.rebuild_member(member)
    if (
        len(vectors) != member.represented_vector_count
        or len(set(vectors)) != len(vectors)
        or tuple(sorted(vectors)) != vectors
        or min(vectors) != member.counts
    ):
        raise AssertionError("compressed member does not cover its exact represented vectors")
    records: list[dict[str, Any]] = []
    for vector in vectors:
        vector_state = catalog.rebuild_member(
            replace(member, counts=vector, represented_vector_count=1)
        )
        if compression_signature(vector_state) != compression_signature(state):
            raise AssertionError("represented vector has a different compression signature")
        moment_row = r14.moment_certificate(vector)
        moment = exact_residual_pair_moment(vector)
        rational = ceiling_divide_by_9(moment)
        if (
            moment != int(moment_row["residual_s2_lower_bound"])
            or rational != int(moment_row["correction_lower_bound"])
            or moment_row["multiplicity_cap"] != r12.OUTSIDE_TICKET_COUNT
            or moment_row["multiplicity_dual"] != [1, 9]
        ):
            raise AssertionError("R14 residual event, multiplicity dual, or exact ceiling drifted")
        r6_pair = vector_state.residual_pair_union_penalty
        forest = vector_state.complementary_forest_floor
        prior = vector_state.applied_residual_union_penalty
        if prior != max(r6_pair, forest):
            raise AssertionError("previous correction is not the R6/forest max")
        combined = combine_corrections(r6_pair, forest, rational)
        uncorrected = (
            r14.joint_constant() - vector_state.anchor_pair_s2 + vector_state.anchor_triple_s3
        )
        bound = member_bound(uncorrected, combined)
        if member.raw_bound != uncorrected - prior or bound >= member.raw_bound:
            raise AssertionError("R14 does not replace the applied correction exactly once")
        support = r12.construct_support_witness(vector)
        if support is None or not r8.validate_support_assignment(vector, support):
            raise AssertionError("represented vector has no valid exact support witness")
        residual_cost, s4_cost = r8.witness_costs(vector, support)
        if residual_cost < moment or s4_cost < int(moment_row["s4_pairwise_lower_bound"]):
            raise AssertionError("exact support witness violates its pair-moment floor")
        records.append(
            {
                "vector_id": member_id(vector),
                "counts": sparse(vector),
                "residual_event_definition": RESIDUAL_EVENT_DEFINITION,
                "residual_pair_moment": moment,
                "r14_correction": rational,
                "r6_pair_correction": r6_pair,
                "forest_correction": forest,
                "prior_applied_correction": prior,
                "combined_correction": combined,
                "uncorrected_anchor_bound": uncorrected,
                "vector_new_bound": bound,
                "moment_certificate": catalog.normalized(moment_row),
                "support_witness": catalog.normalized(support),
                "support_sha256": digest(support),
                "support_residual_pair_moment": residual_cost,
                "support_s4_pair_moment": s4_cost,
            }
        )
    rational_floor = compressed_correction(tuple(row["r14_correction"] for row in records))
    correction = combine_corrections(
        state.residual_pair_union_penalty, state.complementary_forest_floor, rational_floor
    )
    bound = max(int(row["vector_new_bound"]) for row in records)
    uncorrected = r14.joint_constant() - state.anchor_pair_s2 + state.anchor_triple_s3
    if bound != member_bound(uncorrected, correction):
        raise AssertionError("compressed member did not take the weakest represented bound")
    return {
        "member_id": member_id(member.counts),
        "witness_counts": sparse(member.counts),
        "represented_vector_count": len(vectors),
        "represented_vectors": [sparse(vector) for vector in vectors],
        "compression_signature": catalog.normalized(compression_signature(state)),
        "vector_certificates": records,
        "r6_pair_correction": state.residual_pair_union_penalty,
        "forest_correction": state.complementary_forest_floor,
        "prior_applied_correction": state.applied_residual_union_penalty,
        "minimum_vector_r14_correction": rational_floor,
        "member_certified_correction": correction,
        "uncorrected_anchor_bound": uncorrected,
        "member_prior_bound": member.raw_bound,
        "member_raw_bound": member.raw_bound,
        "member_new_bound": bound,
        "correction_combination": CORRECTION_COMBINATION,
        "hunter_correction_applied": False,
    }


def recompute_family(state_bound: int) -> dict[str, Any]:
    authority = six_authority()
    terms = tuple(
        (str(row["stable_id"]), int(row["bound"])) for row in authority["FINAL_STATE_TERMS"]
    )
    if len(terms) != 23 or len(dict(terms)) != 23 or TARGET_STATE_ID not in dict(terms):
        raise AssertionError("complete 23-State family identity failed")
    classified = six.classified_terms()
    tail_bound = six.sealed_tail_bound()
    start = six.tail.family_maximum(tail_bound, terms, classified)
    if start != authority["FINAL_FAMILY_MAX_RECOMPUTATION"]:
        raise AssertionError("starting complete R3 family differs from the six-member source")
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
    return {
        "start": start,
        "final": final,
        "start_terms": terms,
        "terms": replaced,
        "tail_bound": tail_bound,
        "classified_count": len(classified),
        "classified_sha256": digest(classified),
        "aggregate": aggregate,
    }


def check_regression(result: dict[str, Any]) -> None:
    if (
        result["START_R3_FAMILY_UB"] != EXPECTED_START_UB
        or result["FINAL_R3_FAMILY_UB"] != EXPECTED_FINAL_UB
        or result["PRESERVED_COHORT_MAX"] != EXPECTED_FINAL_UB
        or min(result["CORRECTION_FLOORS"]) != EXPECTED_CORRECTION_FLOOR
        or result["CERTIFIED_MEMBER_MAX"] != EXPECTED_CERTIFIED_MAX
        or result["REMAINING_GAP"] != EXPECTED_REMAINING_GAP
    ):
        raise AssertionError("recomputed certificate differs from the regression references")


def build_result() -> dict[str, Any]:
    fingerprints = verify_upstream_fingerprints()
    authority = six_authority()
    members = six.region_members()
    priors = current_member_bounds(members)
    cohort = next_eleven_members(members, priors)
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
    records = [certify_member(member, recovered[member.counts]) for member in cohort]
    bounds = six.replaced_bounds(priors, records)
    certified = {member.counts for member in cohort}
    preserved = {counts: bound for counts, bound in priors.items() if counts not in certified}
    if any(bounds[counts] != bound for counts, bound in preserved.items()):
        raise AssertionError("a preserved region member changed")
    final_state_bound = max(bounds.values())
    family = recompute_family(final_state_bound)
    if max(priors.values()) != dict(family["start_terms"])[TARGET_STATE_ID]:
        raise AssertionError("source region maximum differs from its State term")
    result: dict[str, Any] = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "SUCCESS",
        "TASK_BRANCH": TASK_BRANCH,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "SIX_MEMBER_SOURCE_HEAD": BASE_HEAD,
        "SIX_MEMBER_SOURCE_TREE": BASE_TREE,
        "SIX_MEMBER_RESULT_SHA256": SIX_RESULT_SHA256,
        "SIX_MEMBER_VERIFY_STATUS": "PASS",
        "UPSTREAM_FINGERPRINTS_SHA256": fingerprints,
        "STATE_ID": TARGET_STATE_ID,
        "REGION_IDENTITY": catalog.region_fingerprint(members),
        "REGION_COMPRESSED_MEMBER_COUNT": len(members),
        "REGION_REPRESENTED_VECTOR_COUNT": sum(m.represented_vector_count for m in members),
        "NEXT_ELEVEN_MEMBER_COUNT": len(records),
        "REPRESENTED_VECTOR_COUNT": len(flat_vectors),
        "COVERAGE_STATUS": "PASS_11_EXACT_MEMBERS_12_DISTINCT_VECTORS",
        "RESIDUAL_EVENT_DEFINITION": RESIDUAL_EVENT_DEFINITION,
        "R14_CORRECTION_RULE": R14_CORRECTION_RULE,
        "CORRECTION_COMBINATION": CORRECTION_COMBINATION,
        "MEMBER_CERTIFICATES": records,
        "CORRECTION_FLOORS": [row["member_certified_correction"] for row in records],
        "CERTIFIED_MEMBER_MAX": max(row["member_new_bound"] for row in records),
        "ORIGINAL_SIX_CERTIFICATES": authority["MEMBER_CERTIFICATES"],
        "ORIGINAL_SIX_CERTIFICATES_PRESERVED": all(
            bounds[dense(row["witness_counts"])] == row["member_new_bound"]
            for row in authority["MEMBER_CERTIFICATES"]
        ),
        "PRESERVED_MEMBER_COUNT": len(preserved),
        "PRESERVED_COHORT_MAX": max(preserved.values()),
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
        "TAIL_BOUND": family["tail_bound"],
        "CLASSIFIED_TERM_COUNT": family["classified_count"],
        "CLASSIFIED_TERMS_SHA256": family["classified_sha256"],
        "CLASSIFIED_AGGREGATE": family["aggregate"],
        "CLASSIFIED_MAX": family["final"]["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"],
        "START_FAMILY_MAX_RECOMPUTATION": family["start"],
        "FINAL_FAMILY_MAX_RECOMPUTATION": family["final"],
        "START_R3_FAMILY_UB": family["start"]["R3_BOUND"],
        "FINAL_R3_FAMILY_UB": family["final"]["R3_BOUND"],
        "FINAL_OWNER_IDS": family["final"]["OWNER_IDS"],
        "CURRENT_INCUMBENT": catalog.r24.INCUMBENT,
        "REMAINING_GAP": int(family["final"]["R3_BOUND"]) - catalog.r24.INCUMBENT,
        "NON_DUPLICATE_CREDIT_STATUS": "PASS_MAX_R6_FOREST_R14_SINGLE_REPLACEMENT",
        "DUPLICATE_CORRECTIONS": 0,
        "WITNESS_SOUNDNESS_STATUS": "PASS_12_EXACT_SUPPORT_WITNESSES",
        "FULL_STATE_CATALOG_STATUS": "PASS_1427_OF_1427_1416_UNCHANGED",
        "VECTOR_RECOVERY": "EXACT_SELECTED_LOSS_R17_COMPRESSION_SIGNATURE",
        "R7_CENSUS_REBUILD_CALLS": 0,
        "NEW_HEAVY_SOLVER_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "WORKTREE_DISPOSITION": "RETAIN",
    }
    if not result["ORIGINAL_SIX_CERTIFICATES_PRESERVED"]:
        raise AssertionError("an original six-member certificate changed")
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
    return six.encode(result)


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
