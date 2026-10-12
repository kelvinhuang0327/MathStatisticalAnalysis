"""Refine the two R3 owners left by the two-member refinement with exact R14 credit.

Replay the sealed two-member result, then re-derive every member tied at the
State maximum from the complete 1,427-member catalog. Rebuild each owner's own
exact residual-pair moment, derive the outside-frequency dual and the integer
multiplicity ceiling per represented vector, and combine all valid R6, forest,
R14 and Hunter floors by max, subtracting once. Preserve every other member,
State term, Tail and classified aggregate. No census or solver is invoked.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from functools import cache
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_r3_current_state_two_member_r14_refinement_r1 as prior

base, region, hunter = prior.base, prior.region, prior.hunter
six, catalog, r14, r8 = prior.six, prior.catalog, prior.r14, prior.r8
type CountVector = tuple[int, ...]
LedgerMember = catalog.LedgerMember
dense, sparse, digest, member_id = prior.dense, prior.sparse, prior.digest, prior.member_id
TASK_ID = "B649_K20_R3_STATE_13548976_NEXT_TWO_R14_CERTIFICATE_R1"
TASK_BRANCH = "codex/b649-k20-r3-state-13548976-next-two-r14-certificate-r1"
BASE_HEAD = "2935eeba8ffd476575820a3be69f1c42a0132798"
BASE_TREE = "00fd9da1e20e419e7f3e589ef992d0267ed7993b"
BASE_RESULT_SHA256 = "d34f27530cda179d6b1461cbdffcf2539ccee2eb21dd8f2a4c6745f7df92b70b"
BASE_MODULE_SHA256 = "2f2709213026e6aa80f4cccd4f19e9d1bdd39e693e103ab812dd4145e6ec6f99"
TARGET_STATE_ID = prior.TARGET_STATE_ID
REGION_SHA256 = prior.REGION_SHA256
TARGET_IDS = ("[0,11][4,1][5,5][16,1]", "[0,11][1,1][5,5][16,1]")
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_RELATIVE = six.RESULTS + "b649-k20-r3-state-13548976-next-two-r14-certificate-r1-result.json"
RESULT_PATH = REPO_ROOT / RESULT_RELATIVE
UPSTREAM_SHA256 = {
    **prior.UPSTREAM_SHA256,
    prior.RESULT_RELATIVE: BASE_RESULT_SHA256,
    "src/lottolab/research/b649_k20_r3_current_state_two_member_r14_refinement_r1.py": (
        BASE_MODULE_SHA256
    ),
}
CORRECTION_COMBINATION = prior.CORRECTION_COMBINATION


def json_digest(payload: object) -> str:
    """Digest of stored certificates, whose definitions carry non-ASCII set symbols."""

    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def verify_upstream_fingerprints() -> dict[str, str]:
    observed = {p: sha256((REPO_ROOT / p).read_bytes()).hexdigest() for p in UPSTREAM_SHA256}
    if observed != UPSTREAM_SHA256:
        raise AssertionError("immutable source fingerprint mismatch")
    return observed


@cache
def prior_authority() -> dict[str, Any]:
    verify_upstream_fingerprints()
    stored = cast(dict[str, Any], json.loads((REPO_ROOT / prior.RESULT_RELATIVE).read_text()))
    if (
        stored["TASK_ID"] != prior.TASK_ID
        or stored["FINAL_OWNER_IDS"] != [TARGET_STATE_ID]
        or stored["FINAL_STATE_MEMBER_IDS"] != list(TARGET_IDS)
        or prior.verify_result(stored)["status"] != "PASS"
    ):
        raise AssertionError("immutable two-member source identity or replay failed")
    return stored


def current_member_bounds(members: tuple[LedgerMember, ...]) -> dict[CountVector, int]:
    authority = prior_authority()
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
        or len(set(bounds)) != 1427
        or sum(m.represented_vector_count for m in members) != 1543
        or catalog.region_fingerprint(members) != REGION_SHA256
        or catalog.normalized(replay) != authority["COMPLETE_REGION_MEMBERS"]
    ):
        raise AssertionError("complete region coverage or source bounds failed")
    return bounds


def target_members(
    members: tuple[LedgerMember, ...], bounds: dict[CountVector, int]
) -> tuple[LedgerMember, ...]:
    """Every member tied at the current State maximum, read from the whole catalog."""

    if set(bounds) != {m.counts for m in members}:
        raise AssertionError("target member coverage failed")
    cohort = tuple(m for m in members if bounds[m.counts] == max(bounds.values()))
    if tuple(member_id(m.counts) for m in cohort) != TARGET_IDS or any(
        m.represented_vector_count != 1 or bounds[m.counts] != m.raw_bound for m in cohort
    ):
        raise AssertionError("exact two current target member identities failed")
    return cohort


@cache
def represented_vectors() -> dict[CountVector, tuple[CountVector, ...]]:
    members = six.region_members()
    cohort = target_members(members, current_member_bounds(members))
    recovered = catalog.r17.represented_vectors(tuple(catalog.rebuild_member(m) for m in cohort))
    if recovered != {m.counts: (m.counts,) for m in cohort}:
        raise AssertionError("exact target represented-vector coverage failed")
    return recovered


def certify_member(
    member: LedgerMember, vectors: tuple[CountVector, ...], prior_bound: int
) -> dict[str, Any]:
    if (
        member_id(member.counts) not in TARGET_IDS
        or vectors != represented_vectors()[member.counts]
        or prior_bound != member.raw_bound
    ):
        raise AssertionError("target represented-vector coverage or prior bound failed")
    state = catalog.rebuild_member(member)
    records: list[dict[str, Any]] = []
    for vector in vectors:
        current = catalog.rebuild_member(replace(member, counts=vector, represented_vector_count=1))
        signature = hunter.eleven.compression_signature(current)
        if signature != hunter.eleven.compression_signature(state):
            raise AssertionError("represented vector compression signature failed")
        moment = prior.exact_moment_certificate(vector)
        floor = int(moment["residual_s2_lower_bound"])
        if int(moment["correction_lower_bound"]) != (floor + 8) // 9:
            raise AssertionError("exact integer ceiling of the residual moment failed")
        nine, eleven = base.nine_event_proof(), base.prior.eleven_event_proof()
        if vector[0] < max(nine["event_count"], eleven["event_count"]):
            raise AssertionError("Hunter selected residual events applicability failed")
        corrections = {
            "R6_PAIR": current.residual_pair_union_penalty,
            "FOREST": current.complementary_forest_floor,
            "R14": int(moment["correction_lower_bound"]),
            "NINE_EVENT_HUNTER": int(nine["hunter_floor"]),
            "ELEVEN_EVENT_HUNTER": int(eleven["hunter_floor"]),
        }
        applied = max(corrections["R6_PAIR"], corrections["FOREST"])
        combined = hunter.combine_corrections(corrections)
        uncorrected = r14.joint_constant() - current.anchor_pair_s2 + current.anchor_triple_s3
        residual_sum = sum(n * hunter.residual_event_size(i) for i, n in enumerate(vector))
        bound = hunter.member_bound(uncorrected, combined)
        if (
            applied != current.applied_residual_union_penalty
            or prior_bound != uncorrected - applied
            or hunter.anchor_union_size() + residual_sum != uncorrected
            or combined != max(corrections.values())
            or bound != uncorrected - combined
            or bound >= prior_bound
        ):
            raise AssertionError("max single correction replacement failed")
        support = hunter.r12.construct_support_witness(vector)
        if support is None or not r8.validate_support_assignment(vector, support):
            raise AssertionError("exact support witness failed")
        residual_cost, s4_cost = r8.witness_costs(vector, support)
        if (
            residual_cost < moment["residual_s2_lower_bound"]
            or s4_cost < moment["s4_pairwise_lower_bound"]
        ):
            raise AssertionError("support witness violates the exact moment floor")
        records.append(
            {
                "vector_id": member_id(vector),
                "counts": sparse(vector),
                "compression_signature": signature,
                "moment_certificate": moment,
                "moment_sha256": digest(moment),
                "residual_event_definition": hunter.RESIDUAL_EVENT_DEFINITION,
                "residual_pair_moment": moment["residual_s2_lower_bound"],
                "r14_correction": corrections["R14"],
                "corrections": corrections,
                "prior_applied_correction": applied,
                "combined_correction": combined,
                "anchor_union": hunter.anchor_union_size(),
                "residual_event_sum": residual_sum,
                "uncorrected_anchor_bound": uncorrected,
                "vector_new_bound": bound,
                "support_witness": support,
                "support_sha256": digest(support),
                "support_residual_pair_moment": residual_cost,
                "support_s4_pair_moment": s4_cost,
                "nine_event_witness_analysis": region.witness_analysis(vector, support, nine),
                "eleven_event_witness_analysis": region.witness_analysis(vector, support, eleven),
            }
        )
    return catalog.normalized(
        {
            "member_id": member_id(member.counts),
            "witness_counts": sparse(member.counts),
            "represented_vector_count": len(vectors),
            "represented_vectors": [sparse(v) for v in vectors],
            "vector_certificates": records,
            "member_prior_bound": prior_bound,
            "member_raw_bound": member.raw_bound,
            "member_certified_correction": min(r["combined_correction"] for r in records),
            "member_new_bound": max(r["vector_new_bound"] for r in records),
            "correction_combination": CORRECTION_COMBINATION,
        }
    )


def preserved_bounds_sha256(
    members: tuple[LedgerMember, ...], bounds: dict[CountVector, int], changed: set[CountVector]
) -> str:
    """The ordered (witness vector, bound) pairs of every member left untouched."""

    return digest(tuple((m.counts, bounds[m.counts]) for m in members if m.counts not in changed))


def recompute_family(state_bound: int) -> dict[str, Any]:
    authority = prior_authority()
    terms = tuple((str(r["stable_id"]), int(r["bound"])) for r in authority["FINAL_STATE_TERMS"])
    if len(terms) != 23 or len(dict(terms)) != 23 or TARGET_STATE_ID not in dict(terms):
        raise AssertionError("complete 23-State identity failed")
    classified, tail = six.classified_terms(), six.sealed_tail_bound()
    if (
        tail != authority["TAIL_BOUND"]
        or digest(classified) != authority["CLASSIFIED_TERMS_SHA256"]
        or len(classified) != authority["CLASSIFIED_TERM_COUNT"]
        or [{"stable_id": k, "bound": b} for k, b in classified if k == catalog.r24.AGGREGATE_ID]
        != authority["CLASSIFIED_AGGREGATE"]
    ):
        raise AssertionError("preserved classified aggregate or Tail failed")
    start = six.tail.family_maximum(tail, terms, classified)
    if start != authority["FINAL_FAMILY_MAX_RECOMPUTATION"]:
        raise AssertionError("starting complete family differs from source")
    replaced = tuple((k, state_bound if k == TARGET_STATE_ID else b) for k, b in terms)
    return {
        "start": start,
        "final": six.tail.family_maximum(tail, replaced, classified),
        "start_terms": terms,
        "terms": replaced,
        "tail_bound": tail,
        "classified_count": len(classified),
        "classified_sha256": digest(classified),
    }


def build_result() -> dict[str, Any]:
    fingerprints = verify_upstream_fingerprints()
    authority = prior_authority()
    members = six.region_members()
    priors = current_member_bounds(members)
    cohort = target_members(members, priors)
    records = [certify_member(m, represented_vectors()[m.counts], priors[m.counts]) for m in cohort]
    bounds = six.replaced_bounds(priors, records)
    changed = {c for c in priors if priors[c] != bounds[c]}
    if changed != {m.counts for m in cohort}:
        raise AssertionError("exactly two member replacements required")
    final = max(bounds.values())
    family = recompute_family(final)
    if max(priors.values()) != dict(family["start_terms"])[TARGET_STATE_ID]:
        raise AssertionError("target State bound differs from complete region maximum")
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
            "UPSTREAM_FINGERPRINTS_SHA256": fingerprints,
            "DONOR_SOURCE_IDENTITIES": {
                **authority["DONOR_SOURCE_IDENTITIES"],
                "TWO_MEMBER_REFINEMENT": {
                    "task_id": prior.TASK_ID,
                    "result_sha256": BASE_RESULT_SHA256,
                    "module_sha256": BASE_MODULE_SHA256,
                },
            },
            "STATE_ID": TARGET_STATE_ID,
            "REGION_SHA256": catalog.region_fingerprint(members),
            "REGION_COMPRESSED_MEMBER_COUNT": len(members),
            "REGION_REPRESENTED_VECTOR_COUNT": sum(m.represented_vector_count for m in members),
            "TWO_MEMBER_IDS": [r["member_id"] for r in records],
            "REPRESENTED_VECTOR_COVERAGE": [r["represented_vector_count"] for r in records],
            "REGION_COVERAGE_STATUS": "PASS_1427_MEMBERS_1543_VECTORS_UNCHANGED",
            "MEMBER_CERTIFICATES": records,
            "RESIDUAL_MOMENT_FLOORS": [row["residual_pair_moment"] for row in rows],
            "R14_CORRECTIONS": [row["r14_correction"] for row in rows],
            "EXACT_MOMENT_DIGESTS": [row["moment_sha256"] for row in rows],
            "SUPPORT_DIGESTS": [row["support_sha256"] for row in rows],
            "NEW_MEMBER_BOUNDS": [r["member_new_bound"] for r in records],
            "PRESERVED_MEMBER_COUNT": len(members) - len(changed),
            "PRESERVED_MEMBER_BOUNDS_SHA256": preserved_bounds_sha256(members, bounds, changed),
            "PRESERVED_MEMBER_BOUNDS_STATUS": "PASS_1425_MEMBER_BOUNDS_UNCHANGED",
            "PREVIOUS_TWO_MEMBER_CERTIFICATES_SHA256": json_digest(
                authority["MEMBER_CERTIFICATES"]
            ),
            "PREVIOUS_REGION_CERTIFICATES_SHA256": json_digest(
                authority["PREVIOUS_REGION_CERTIFICATES"]
            ),
            "PREVIOUS_NINE_ELEVEN_CERTIFICATES_SHA256": digest(
                prior.source_authority()["MEMBER_CERTIFICATES"]
            ),
            "PREVIOUS_CERTIFICATE_STATUS": "PASS_EXACT_SOURCE_REPLAY_AND_PRESERVATION",
            "COMPLETE_REGION_MEMBERS": [
                {
                    "member_id": member_id(m.counts),
                    "witness_counts": sparse(m.counts),
                    "represented_vector_count": m.represented_vector_count,
                    "raw_bound": m.raw_bound,
                    "prior_bound": priors[m.counts],
                    "final_bound": bounds[m.counts],
                }
                for m in members
            ],
            "START_STATE_BOUND": max(priors.values()),
            "FINAL_STATE_BOUND": final,
            "FINAL_STATE_MEMBER_IDS": [member_id(c) for c, b in bounds.items() if b == final],
            "START_STATE_TERMS": [{"stable_id": k, "bound": b} for k, b in family["start_terms"]],
            "FINAL_STATE_TERMS": [{"stable_id": k, "bound": b} for k, b in family["terms"]],
            "STATE_TERM_COUNT": len(family["terms"]),
            "FULL_23_STATE_RECOMPUTATION": "PASS",
            "TAIL_BOUND": family["tail_bound"],
            "CLASSIFIED_TERM_COUNT": family["classified_count"],
            "CLASSIFIED_TERMS_SHA256": family["classified_sha256"],
            "CLASSIFIED_AGGREGATE": authority["CLASSIFIED_AGGREGATE"],
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
            "WITNESS_SOUNDNESS_STATUS": "PASS_TWO_EXACT_SUPPORTS_AND_HUNTER_APPLICABILITY",
            "R7_CENSUS_REBUILD_CALLS": 0,
            "OUTCOME_ENUMERATION_USED": False,
            "NEW_HEAVY_SOLVER_STARTED": "NO",
            "PRODUCTION_MUTATION": "NONE",
            "PUSH_PR_MERGE": "NONE",
            "WORKTREE_DISPOSITION": "RETAIN",
        }
    )


def verify_result(result: dict[str, Any]) -> dict[str, Any]:
    """Reject mathematical tampering semantically before the final full replay."""

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
        raise AssertionError("source identity failed")
    records = result["MEMBER_CERTIFICATES"]
    if tuple(r["member_id"] for r in records) != TARGET_IDS:
        raise AssertionError("exact two member certificate coverage failed")
    members = {m.counts: m for m in six.region_members()}
    priors = current_member_bounds(tuple(members.values()))
    for record in records:
        vector = dense(record["witness_counts"])
        expected = certify_member(members[vector], represented_vectors()[vector], priors[vector])
        if (
            record["represented_vectors"] != expected["represented_vectors"]
            or len(record["vector_certificates"]) != record["represented_vector_count"]
        ):
            raise AssertionError("represented-vector certificate coverage failed")
        for row, replay in zip(
            record["vector_certificates"], expected["vector_certificates"], strict=True
        ):
            if (
                row["counts"] != replay["counts"]
                or row["compression_signature"] != replay["compression_signature"]
            ):
                raise AssertionError("represented-vector identity or compression failed")
            if any(
                row[k] != replay[k]
                for k in (
                    "moment_certificate",
                    "moment_sha256",
                    "residual_pair_moment",
                    "r14_correction",
                    "residual_event_definition",
                )
            ):
                raise AssertionError("exact residual moment or integer ceiling failed")
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
                raise AssertionError("max single correction replacement failed")
            support = tuple(tuple(int(x) for x in t) for t in row["support_witness"])
            if not r8.validate_support_assignment(vector, support):
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
            "PRESERVED_MEMBER_COUNT",
            "PRESERVED_MEMBER_BOUNDS_SHA256",
        )
    ):
        raise AssertionError("complete region preservation or member coverage failed")
    if any(
        result[k] != replay_result[k]
        for k in (
            "START_STATE_TERMS",
            "FINAL_STATE_TERMS",
            "FINAL_STATE_MEMBER_IDS",
            "FINAL_FAMILY_MAX_RECOMPUTATION",
            "FINAL_COMPLETE_R3_UB",
            "FINAL_OWNER_IDS",
            "TAIL_BOUND",
            "CLASSIFIED_AGGREGATE",
        )
    ):
        raise AssertionError("complete 23-State family or Tail/aggregate replay failed")
    if result != replay_result:
        raise AssertionError("stored result differs from complete exact replay")
    return {"status": "PASS", "members": 2, "vectors": 2, "region_members": 1427}


def encode(result: dict[str, Any]) -> str:
    return hunter.encode(result)


def verify_stored_result() -> dict[str, Any]:
    """Semantic verification plus byte identity of the stored file."""

    stored_bytes = RESULT_PATH.read_bytes()
    status = verify_result(cast(dict[str, Any], json.loads(stored_bytes)))
    if stored_bytes != encode(build_result()).encode():
        raise AssertionError("stored result bytes differ from the encoded replay")
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
        "TWO_MEMBER_IDS",
        "R14_CORRECTIONS",
        "NEW_MEMBER_BOUNDS",
        "FINAL_STATE_BOUND",
        "FINAL_COMPLETE_R3_UB",
        "FINAL_OWNER_IDS",
        "REMAINING_GAP",
    )
    print(json.dumps({k: result[k] for k in keys}, sort_keys=True))


if __name__ == "__main__":
    main()
