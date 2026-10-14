"""Replace the highest five members' credit with the universal eleven-event floor.

The sealed R24/Hunter-Top16 ledger supplies all 582 members. Recover its 633
vectors at their exact losses and compression signatures. Only the five top
members (six vectors) receive new credit; TS-106/H0-70 remain sealed inputs.

Reuse the existing exact integer eleven-event theorem: smoothing degrees proves
Q >= 26 for 66 incidences on 40 labels. Nested threshold graphs have forest rank
at least rho(e), since e <= sum C(r_j+1,2) <= C(sum r_j+1,2). Descending Kruskal
spans every threshold graph. All 30216 admissible triples yield a minimum tree
weight of 4341400. On an outcome in k events a tree induces at most k-1 edges,
so summation proves Hunter's inequality universally. Nonnegative intersections
extend the tree to eighteen events. Witnesses check legality, never universality.
Combine valid credits by MAX and subtract once; maximize over every vector and
then over the complete State/Classified/Tail Family. No census or solver runs.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import replace
from functools import cache
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_r3_hunter_top16_complete_integration_r1 as integration
from lottolab.research import b649_k20_r3_three_state_ts_106_member_certificate_r1 as prior

hunter, catalog, six, r24 = prior.hunter, prior.catalog, prior.six, prior.r24
LedgerMember = catalog.LedgerMember
type CountVector = tuple[int, ...]
dense, sparse, digest, member_id = prior.dense, prior.sparse, prior.digest, prior.member_id
TASK_ID = "B649_K20_R3_STATE_12692531_TOP_BAND_ELEVEN_EVENT_HUNTER_R1"
TASK_BRANCH = "codex/b649-k20-r3-state-12692531-top-band-eleven-event-hunter-r1"
BASE_HEAD = "e464631565f83e44b1ff6cbeeb1e9af64880939d"
BASE_TREE = "25174405e76eb4350eb045a0c02c4f04901b776e"
BASE_RESULT_SHA256 = "40cdc624da9eef931f122cce03f28d326ec6a8a931c3039e8b0235dffef4818a"
TARGET_STATE_ID = "state:s2-12692531-s3-681744"
REGION_SHA256 = "132cef5c91f5d6cf4798c8d8f65dba98d3851f33ec3d45b5d37fb7f61145ef15"
REMAINDER_SHA256 = "09b7371e67a6dbf3ae183b1701f3780ec2c901a4e385a5a9e3b8c39cc71b569e"
TARGET_VECTORS = tuple(
    dense(v)
    for v in (
        [[0, 11], [4, 2], [5, 4], [8, 1]],
        [[0, 11], [2, 1], [4, 2], [5, 4]],
        [[0, 11], [1, 1], [4, 1], [5, 4], [8, 1]],
        [[0, 11], [1, 1], [2, 1], [4, 1], [5, 4]],
        [[0, 11], [1, 2], [2, 1], [5, 4]],
    )
)
COMPRESSED_EXTRA_VECTOR = dense([[0, 11], [1, 2], [5, 4], [8, 1]])
TARGET_IDS = tuple(member_id(v) for v in TARGET_VECTORS)
EVENT_COUNT = 11
RESIDUAL_EVENT_DEFINITION = prior.RESIDUAL_EVENT_DEFINITION
CORRECTION_COMBINATION = "MAX(EXISTING_VALID_CREDITS, ELEVEN_EVENT_HUNTER); SUBTRACT_ONCE"
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_RELATIVE = (
    six.RESULTS + "b649-k20-r3-state-12692531-top-band-eleven-event-hunter-r1-result.json"
)
RESULT_PATH = REPO_ROOT / RESULT_RELATIVE


def source_paths() -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                *prior.source_paths(),
                str(Path(prior.__file__).resolve().relative_to(REPO_ROOT)),
                prior.RESULT_RELATIVE,
            }
        )
    )


def verify_source_authority() -> dict[str, Any]:
    """Uncached byte checks bind every executing primitive and sealed predecessor."""
    prefix = ["git", "-C", str(REPO_ROOT)]
    identity = subprocess.check_output(
        [*prefix, "show", "-s", "--format=%H %T", BASE_HEAD], text=True
    ).strip()
    blob = subprocess.check_output([*prefix, "show", f"{BASE_HEAD}:{prior.RESULT_RELATIVE}"])
    if identity != f"{BASE_HEAD} {BASE_TREE}" or sha256(blob).hexdigest() != BASE_RESULT_SHA256:
        raise AssertionError("immutable BASE_HEAD/TREE/result SHA authority failed")
    if subprocess.run([*prefix, "merge-base", "--is-ancestor", BASE_HEAD, "HEAD"]).returncode:
        raise AssertionError("checkout does not descend from the immutable base")
    fingerprints: dict[str, str] = {}
    for relative in source_paths():
        frozen = subprocess.check_output([*prefix, "show", f"{BASE_HEAD}:{relative}"])
        if (REPO_ROOT / relative).read_bytes() != frozen:
            raise AssertionError(f"immutable executing source or sealed input changed: {relative}")
        fingerprints[relative] = sha256(frozen).hexdigest()
    return {
        "HEAD": BASE_HEAD,
        "TREE": BASE_TREE,
        "RESULT_SHA256": BASE_RESULT_SHA256,
        "upstream_sha256": fingerprints,
    }


@cache
def source_authority() -> dict[str, Any]:
    """Adopt TS-106 unchanged and replay only the selected sealed region lineage."""
    verify_source_authority()
    authority = cast(dict[str, Any], json.loads(prior.RESULT_PATH.read_bytes()))
    sealed = cast(dict[str, Any], json.loads(integration.RESULT_PATH.read_bytes()))
    _, inputs = integration.verify_sources()
    region = integration.adopt_hunter(inputs["HUNTER"], inputs["SIBLING"], inputs["R24"])
    if (
        authority["TASK_ID"] != prior.TASK_ID
        or authority["TARGET_MEMBER_COUNT"] != 106
        or authority["TARGET_VECTOR_COUNT"] != 116
        or authority["FINAL_COMPLETE_R3_UB"] != 355274920
        or region != sealed["HUNTER_ADOPTION"]
        or region["state_id"] != TARGET_STATE_ID
        or region["region_sha256"] != REGION_SHA256
        or TARGET_STATE_ID in prior.REGION_SPECS
    ):
        raise AssertionError("immutable TS-106 or R24/Hunter-Top16 region authority failed")
    return {"TS106": authority, "REGION": region}


@cache
def region_members() -> tuple[LedgerMember, ...]:
    authority = source_authority()
    members = tuple(
        LedgerMember(
            dense(row["witness_counts"]),
            int(row["represented_vector_count"]),
            int(row["raw_bound"]),
            int(row["final_bound"]),
        )
        for row in authority["REGION"]["complete_region_members"]
    )
    terms = {row["stable_id"]: row["bound"] for row in authority["TS106"]["FINAL_STATE_TERMS"]}
    if (
        len(members) != 582
        or len({m.counts for m in members}) != 582
        or sum(m.represented_vector_count for m in members) != 633
        or catalog.region_fingerprint(members) != REGION_SHA256
        or max(m.final_bound for m in members) != terms[TARGET_STATE_ID]
        or any(m.final_bound > m.raw_bound or m.represented_vector_count < 1 for m in members)
    ):
        raise AssertionError("complete 582-member/633-vector region identity failed")
    return members


def target_members(members: tuple[LedgerMember, ...]) -> tuple[LedgerMember, ...]:
    maximum = max(m.final_bound for m in members)
    cohort = tuple(m for m in members if m.final_bound == maximum)
    if (
        len(cohort) != 5
        or {m.counts for m in cohort} != set(TARGET_VECTORS)
        or sum(m.represented_vector_count for m in cohort) != 6
        or any(m.final_bound != m.raw_bound or m.final_bound != 355274920 for m in cohort)
    ):
        raise AssertionError("exact five highest members/six represented vectors required")
    available = {m.counts: m for m in cohort}
    return tuple(available[v] for v in TARGET_VECTORS)


@cache
def represented_vectors() -> dict[CountVector, tuple[CountVector, ...]]:
    """Recover at exact losses using R17; never invoke the R7 census."""
    members = region_members()
    recovered = catalog.r17.represented_vectors(tuple(catalog.rebuild_member(m) for m in members))
    flat = [v for vs in recovered.values() for v in vs]
    if set(recovered) != {m.counts for m in members} or len(flat) != 633 or len(set(flat)) != 633:
        raise AssertionError("complete represented-vector recovery failed")
    for member in members:
        vectors = recovered[member.counts]
        signature = hunter.eleven.compression_signature(catalog.rebuild_member(member))
        if (
            len(vectors) != member.represented_vector_count
            or tuple(sorted(vectors)) != vectors
            or min(vectors) != member.counts
        ):
            raise AssertionError("compression cardinality or canonical vector failed")
        for vector in vectors:
            rebuilt = catalog.rebuild_member(
                replace(member, counts=vector, represented_vector_count=1)
            )
            if (
                len(vector) != 30
                or min(vector) < 0
                or sum(vector) != hunter.RESIDUAL_EVENT_COUNT
                or hunter.eleven.compression_signature(rebuilt) != signature
            ):
                raise AssertionError("represented-vector compression signature failed")
    expected = {
        v: tuple(sorted((v, COMPRESSED_EXTRA_VECTOR))) if v == TARGET_VECTORS[1] else (v,)
        for v in TARGET_VECTORS
    }
    if {m.counts: recovered[m.counts] for m in target_members(members)} != expected:
        raise AssertionError("exact six-vector compressed target coverage failed")
    return recovered


def eleven_event_proof() -> dict[str, Any]:
    """Reproduce the existing theorem with its exact counter and complete minimum."""
    if (
        EVENT_COUNT != 11
        or hunter.RESIDUAL_EVENT_DEFINITION != RESIDUAL_EVENT_DEFINITION
        or hunter.eleven.RESIDUAL_EVENT_DEFINITION != RESIDUAL_EVENT_DEFINITION
        or hunter.type_cells(0) != (0, 0, 0, 6)
    ):
        raise AssertionError("eleven type-0 residual event identity failed")
    proof = prior.h0.hunter_proof(EVENT_COUNT)
    if (
        proof["outside_label_count"] != 40
        or proof["outside_incidences"] != 66
        or proof["collision_mass_floor"] != 26
        or proof["pair_floors"] != [107800, 574000, 1691620, 3451651]
        or proof["all_admissible_threshold_cases"] != 30216
        or proof["integer_minimizer"] != {"edge_counts": [26, 0, 0], "rank_floors": [7, 0, 0]}
        or proof["hunter_floor"] != 4341400
    ):
        raise AssertionError("exact eleven-event collision/pair/threshold theorem failed")
    return proof


def certify_vector(
    member: LedgerMember, vector: CountVector, proof: dict[str, Any]
) -> dict[str, Any]:
    if (
        member not in target_members(region_members())
        or vector not in represented_vectors()[member.counts]
        or vector[0] != EVENT_COUNT
        or encode(proof) != encode(eleven_event_proof())
    ):
        raise AssertionError("represented vector or eleven-event applicability failed")
    state = catalog.rebuild_member(replace(member, counts=vector, represented_vector_count=1))
    types = tuple(i for i, count in enumerate(vector) for _ in range(count))
    if (
        len(types) != 18
        or types[:EVENT_COUNT] != (0,) * EVENT_COUNT
        or hunter.eleven.compression_signature(state)
        != hunter.eleven.compression_signature(catalog.rebuild_member(member))
    ):
        raise AssertionError("represented-vector event count or compression signature failed")
    uncorrected = hunter.r14.joint_constant() - state.anchor_pair_s2 + state.anchor_triple_s3
    residual_sum = sum(c * hunter.residual_event_size(i) for i, c in enumerate(vector))
    existing = uncorrected - member.final_bound
    # final == raw and replayed R7 credit exhaust the applied correction. The
    # sealed region has no additional applied R14/Hunter credit on this cohort.
    if (
        existing != state.applied_residual_union_penalty
        or member.final_bound != member.raw_bound
        or uncorrected != hunter.anchor_union_size() + residual_sum
        or uncorrected != 359292920
    ):
        raise AssertionError("existing credit or residual event arithmetic failed")
    credits = {
        "R6_PAIR": state.residual_pair_union_penalty,
        "FOREST": state.complementary_forest_floor,
        "SEALED_VALID": existing,
        "EXISTING_R14": 0,
        "EXISTING_HUNTER": 0,
        "ELEVEN_EVENT_HUNTER": int(proof["hunter_floor"]),
    }
    combined = hunter.combine_corrections(credits)
    bound = hunter.member_bound(uncorrected, combined)
    if (
        not 1822004 <= credits["R6_PAIR"] <= 1824711
        or credits["FOREST"] != existing
        or existing != 4018000
        or combined != max(credits.values())
        or bound != uncorrected - combined
        or bound != 354951520
    ):
        raise AssertionError("MAX-only single correction replacement failed")
    subset = tuple(EVENT_COUNT if i == 0 else 0 for i in range(30))
    witness = prior.witness_analysis(vector, subset, prior.subset_proof(subset))
    return catalog.normalized(
        {
            "vector_id": member_id(vector),
            "counts": sparse(vector),
            "compression_signature": hunter.eleven.compression_signature(state),
            "residual_event_definition": RESIDUAL_EVENT_DEFINITION,
            "type0_count": vector[0],
            "eleven_event_indices": witness["selected_event_indices"],
            "eleven_event_types": witness["selected_event_types"],
            "outside_incidences": vector[0] * hunter.type_cells(0)[3],
            "pair_overlap_ceiling": hunter.family_pair_overlap_ceiling(),
            "collision_mass_floor": proof["collision_mass_floor"],
            "anchor_union": hunter.anchor_union_size(),
            "residual_event_sum": residual_sum,
            "uncorrected_anchor_bound": uncorrected,
            "corrections": credits,
            "prior_applied_correction": existing,
            "combined_correction": combined,
            "vector_new_bound": bound,
            "support_witness": witness["support_witness"],
            "support_sha256": witness["support_sha256"],
            "witness_analysis": witness,
        }
    )


def certify_member(
    member: LedgerMember, vectors: tuple[CountVector, ...], proof: dict[str, Any]
) -> dict[str, Any]:
    if (
        member not in target_members(region_members())
        or vectors != represented_vectors()[member.counts]
    ):
        raise AssertionError("exact represented-vector member coverage failed")
    rows = [certify_vector(member, v, proof) for v in vectors]
    correction = hunter.member_correction(tuple(int(r["combined_correction"]) for r in rows))
    bound = max(int(r["vector_new_bound"]) for r in rows)
    if len(rows) != member.represented_vector_count or bound != 354951520:
        raise AssertionError("compressed member requires MAX over every represented vector")
    return {
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


def recompute_family(state_bound: int) -> dict[str, Any]:
    source = source_authority()["TS106"]
    states = tuple((str(r["stable_id"]), int(r["bound"])) for r in source["FINAL_STATE_TERMS"])
    classified = tuple(
        (str(r["stable_id"]), int(r["bound"]))
        for r in prior.source_results()["JOINT"]["FINAL_CLASSIFIED_TERMS"]
    )
    tail = six.sealed_tail_bound()
    start = six.tail.family_maximum(tail, states, classified)
    if (
        len(states) != len(dict(states))
        or len(states) != 23
        or TARGET_STATE_ID not in dict(states)
        or len(classified) != source["CLASSIFIED_TERM_COUNT"]
        or digest(classified) != source["CLASSIFIED_TERMS_SHA256"]
        or max(b for _, b in classified) != source["CLASSIFIED_MAX"]
        or source["CLASSIFIED_MAX"] != 355145504
        or tail != source["TAIL_BOUND"]
        or tail != 354039277
        or start != source["FINAL_FAMILY_MAX_RECOMPUTATION"]
    ):
        raise AssertionError("complete TS-106 State/Classified/Tail authority failed")
    updated = tuple((k, state_bound if k == TARGET_STATE_ID else b) for k, b in states)
    final = six.tail.family_maximum(tail, updated, classified)
    terms = (*updated, *classified, (r24.TAIL_ID, tail))
    maximum = max(b for _, b in terms)
    runner_up = max(b for _, b in terms if b < maximum)
    return {
        "start": start,
        "final": final,
        "start_states": states,
        "states": updated,
        "classified_count": len(classified),
        "classified_sha256": digest(classified),
        "classified_max": max(b for _, b in classified),
        "tail": tail,
        "runner_up": {"bound": runner_up, "owner_ids": [k for k, b in terms if b == runner_up]},
    }


def build_result() -> dict[str, Any]:
    authority = verify_source_authority()
    members, vectors = region_members(), represented_vectors()
    cohort = target_members(members)
    proof = eleven_event_proof()
    records = [certify_member(m, vectors[m.counts], proof) for m in cohort]
    priors = {m.counts: m.final_bound for m in members}
    bounds = six.replaced_bounds(priors, records)
    changed = {v for v in priors if bounds[v] != priors[v]}
    remainder = tuple(m for m in members if m.counts not in changed)
    preserved_digest = digest(tuple((m.counts, bounds[m.counts]) for m in remainder))
    if (
        changed != set(TARGET_VECTORS)
        or any(bounds[m.counts] != m.final_bound for m in remainder)
        or len(remainder) != 577
        or sum(len(vectors[m.counts]) for m in remainder) != 627
        or preserved_digest != REMAINDER_SHA256
        or max(bounds[m.counts] for m in remainder) != 355274472
    ):
        raise AssertionError("exact five replacements or preserved remainder failed")
    state_bound = max(bounds.values())
    family = recompute_family(state_bound)
    if (
        max(priors.values()) != dict(family["start_states"])[TARGET_STATE_ID]
        or family["start"]["R3_BOUND"] != 355274920
        or state_bound != family["final"]["R3_BOUND"]
        or family["final"]["R3_BOUND"] != 355274472
        or family["final"]["OWNER_IDS"] != [TARGET_STATE_ID]
        or family["runner_up"] != {"bound": 355274108, "owner_ids": ["state:s2-13169800-s3-789320"]}
        or r24.INCUMBENT != 313263888
    ):
        raise AssertionError("complete Family maximum, incumbent, owner or runner-up failed")
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
            "SOURCE_AUTHORITY_STATUS": "PASS_IMMUTABLE_OBJECTS_AND_EXECUTING_BYTES",
            "STATE_ID": TARGET_STATE_ID,
            "REGION_SHA256": catalog.region_fingerprint(members),
            "REGION_COVERAGE_STATUS": "PASS_582_MEMBERS_633_VECTORS_ALL_SIGNATURES",
            "REGION_COMPRESSED_MEMBER_COUNT": len(members),
            "REGION_REPRESENTED_VECTOR_COUNT": sum(len(v) for v in vectors.values()),
            "ALL_REPRESENTED_VECTORS_SHA256": digest(
                tuple((m.counts, vectors[m.counts]) for m in members)
            ),
            "TARGET_MEMBER_COUNT": len(records),
            "TARGET_VECTOR_COUNT": sum(r["represented_vector_count"] for r in records),
            "COMPRESSION_COVERAGE_STATUS": "PASS_ALL_SIX_VECTORS_INCLUDING_TWO_VECTOR_MEMBER",
            "ELEVEN_EVENT_PROOF": proof,
            "H11_PROOF_STATUS": "PASS_EXACT_INTEGER_UNIVERSAL_HUNTER_AND_TREE_EXTENSION",
            "COLLISION_Q_STATUS": "PASS_BALANCED_66_INCIDENCES_40_LABELS_Q_GE_26",
            "THRESHOLD_MINIMIZATION_STATUS": proof["threshold_minimization_status"],
            "HUNTER_FLOOR": proof["hunter_floor"],
            "MEMBER_CERTIFICATES": records,
            "TARGET_NEW_BOUNDS": [r["member_new_bound"] for r in records],
            "PRESERVED_MEMBER_COUNT": len(remainder),
            "PRESERVED_VECTOR_COUNT": sum(len(vectors[m.counts]) for m in remainder),
            "PRESERVED_REMAINDER_MAX": max(bounds[m.counts] for m in remainder),
            "PRESERVED_REMAINDER_SHA256": preserved_digest,
            "PRESERVATION_DIGEST_ENCODING": (
                "R24 digest: SHA256(repr(ordered tuple(counts, bound)).encode('ascii'))"
            ),
            "COMPLETE_UPDATED_BOUNDS_SHA256": digest(
                tuple((m.counts, bounds[m.counts]) for m in members)
            ),
            "TS106_PREDECESSOR_STATUS": "PASS_ENTIRE_BYTE_SEALED_CERTIFICATE_PRESERVED",
            "TS106_CERTIFICATE_SHA256": BASE_RESULT_SHA256,
            "ALL_CARRIED_CERTIFICATES_SHA256": {
                p: h for p, h in authority["upstream_sha256"].items() if p.endswith(".json")
            },
            "COMPLETE_REGION_MEMBERS": [
                {
                    **row,
                    "member_id": member_id(m.counts),
                    "represented_vectors": [sparse(v) for v in vectors[m.counts]],
                    "prior_bound": m.final_bound,
                    "final_bound": bounds[m.counts],
                }
                for m, row in zip(
                    members, source_authority()["REGION"]["complete_region_members"], strict=True
                )
            ],
            "START_STATE_BOUND": max(priors.values()),
            "FINAL_TARGET_STATE_UB": state_bound,
            "START_STATE_TERMS": [{"stable_id": k, "bound": b} for k, b in family["start_states"]],
            "FINAL_STATE_TERMS": [{"stable_id": k, "bound": b} for k, b in family["states"]],
            "STATE_TERM_COUNT": len(family["states"]),
            "FULL_FAMILY_RECOMPUTATION": "PASS_ALL_23_STATES_AND_ALL_CLASSIFIED_TERMS_AND_TAIL",
            "TAIL_BOUND": family["tail"],
            "CLASSIFIED_TERM_COUNT": family["classified_count"],
            "CLASSIFIED_TERMS_SHA256": family["classified_sha256"],
            "CLASSIFIED_MAX": family["classified_max"],
            "START_FAMILY_MAX_RECOMPUTATION": family["start"],
            "FINAL_FAMILY_MAX_RECOMPUTATION": family["final"],
            "START_COMPLETE_R3_UB": family["start"]["R3_BOUND"],
            "FINAL_COMPLETE_R3_UB": family["final"]["R3_BOUND"],
            "FINAL_OWNER_IDS": family["final"]["OWNER_IDS"],
            "RUNNER_UP": family["runner_up"],
            "CURRENT_INCUMBENT": r24.INCUMBENT,
            "REMAINING_GAP": family["final"]["R3_BOUND"] - r24.INCUMBENT,
            "STRICT_GAIN": family["start"]["R3_BOUND"] - family["final"]["R3_BOUND"],
            "CORRECTION_COMBINATION": CORRECTION_COMBINATION,
            "NO_DOUBLE_COUNT_STATUS": "PASS_MAX_SINGLE_SUBTRACTION",
            "WITNESS_SOUNDNESS_STATUS": "PASS_SIX_LEGAL_SUPPORTS_AND_FULL_TREE_EXTENSIONS",
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
    records = result["MEMBER_CERTIFICATES"]
    if [r["member_id"] for r in records] != list(TARGET_IDS):
        raise AssertionError("exact five member certificate coverage failed")
    for record, member in zip(records, target_members(region_members()), strict=True):
        vectors = represented_vectors()[member.counts]
        rows = record["vector_certificates"]
        if (
            record["represented_vectors"] != [sparse(v) for v in vectors]
            or len(rows) != len(vectors)
            or record["represented_vector_count"] != len(vectors)
        ):
            raise AssertionError("complete six-vector compressed coverage failed")
        for row, vector in zip(rows, vectors, strict=True):
            if row["counts"] != sparse(vector) or row["type0_count"] != EVENT_COUNT:
                raise AssertionError("represented-vector source event identity failed")
            if (
                row["combined_correction"] != max(row["corrections"].values())
                or row["vector_new_bound"]
                != row["uncorrected_anchor_bound"] - row["combined_correction"]
            ):
                raise AssertionError("corrections must use MAX and one subtraction, never SUM")
        if record["member_new_bound"] != max(r["vector_new_bound"] for r in rows):
            raise AssertionError("compressed member must maximize over all vectors")
    if encode(result) != encode(build_result()):
        raise AssertionError("stored result differs from complete exact certificate replay")
    return {
        "status": "PASS",
        "members": 5,
        "vectors": 6,
        "region_members": 582,
        "region_vectors": 633,
        "state_terms": 23,
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
    options = parser.parse_args()
    if options.verify:
        print(json.dumps(verify_stored_result(), sort_keys=True))
        return
    result = build_result()
    if options.write:
        RESULT_PATH.write_text(encode(result), encoding="utf-8")
    keys = (
        "TASK_STATUS",
        "TARGET_NEW_BOUNDS",
        "PRESERVED_REMAINDER_MAX",
        "FINAL_COMPLETE_R3_UB",
        "FINAL_OWNER_IDS",
        "RUNNER_UP",
        "REMAINING_GAP",
        "STRICT_GAIN",
    )
    print(json.dumps({k: result[k] for k in keys}, sort_keys=True))


if __name__ == "__main__":
    main()
