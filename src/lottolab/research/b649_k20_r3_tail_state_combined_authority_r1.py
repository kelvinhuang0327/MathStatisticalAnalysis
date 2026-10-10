"""Combine immutable Tail/State certificates without spending a correction twice.

The complete R24 catalog is authoritative, including its 355,722,668 competing
state. Research projections are reported separately and never select the maximum.
No Tail minimization, new State certification, census or solver is dispatched.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_r3_state_13548976_top_band_certificate_r1 as state
from lottolab.research import b649_k20_r3_tail_seven_class_uniform_r6_certificate_r1 as tail

r24 = tail.r24
TASK_ID = "B649_K20_R3_TAIL_STATE_COMBINED_AUTHORITY_R1"
TASK_BRANCH = "codex/b649-k20-r3-tail-state-combined-authority-r1"
BASE_HEAD = "74eca8d81d0ebb5d6d9c5a28ec5a307ee255c635"
BASE_TREE = "5d1b70817351d24d70b7ab9af6ead5ea6b6852f8"
STATE_DONOR_HEAD = "3f9b4947c8582648b27751ec4f0fdf1538fb0287"
STATE_DONOR_TREE = "401cc73993c0b7acfc141a37cf2d28969e916a0a"
COMMON_ANCESTOR = "27614636ac4c20392619b3d9364d22bf2af9cff4"
COMMON_TREE = "cd99dee2289867b45bc6142baed87d5e0dbab96a"
RESEARCH_EXPECTED_BOUND = 355_641_258
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_PATH = REPO_ROOT / (r24.RESULTS + "b649-k20-r3-tail-state-combined-authority-r1-result.json")
SOURCE_PINS = {
    "TAIL": {
        "head": BASE_HEAD,
        "tree": BASE_TREE,
        "files": {
            r24.RESULTS + "b649-k20-r3-tail-seven-class-uniform-r6-certificate-r1-result.json": (
                "77d22715fa003c35ae764aafe0ee44c3368f404d8e71ca499fb6ef6b5ab988f2"
            ),
            "src/lottolab/research/b649_k20_r3_tail_seven_class_uniform_r6_certificate_r1.py": (
                "efb43c77c6e5cae4c5989c6334402f774dd17a83025f5462f4f2f01f3760e820"
            ),
            "tests/unit/test_b649_k20_r3_tail_seven_class_uniform_r6_certificate_r1.py": (
                "340cd58d6c53c0b4a2d4f79773804cac68c2b3ae97b4408a6859831ec8b63810"
            ),
        },
    },
    "STATE": {
        "head": STATE_DONOR_HEAD,
        "tree": STATE_DONOR_TREE,
        "files": {
            r24.RESULTS + "b649-k20-r3-state-13548976-top-band-certificate-r1-result.json": (
                "eb0f8f0fc4fb68d1fe05bcef9d899c4ef67726bfcf6d6182dac6f2ef05f359db"
            ),
            "src/lottolab/research/b649_k20_r3_state_13548976_top_band_certificate_r1.py": (
                "ef881a099bdb5c402612273c9e7f054be4f4306a2869d8535980750dab8db203"
            ),
            "tests/unit/test_b649_k20_r3_state_13548976_top_band_certificate_r1.py": (
                "2dd43e499db00296eafda32ab2e937bb9e33682d30ca5dbc9b14a54eb0480497"
            ),
        },
    },
}


def git_bytes(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(REPO_ROOT), *args])


def verify_sources() -> dict[str, Any]:
    """Verify frozen local objects, exact common ancestry and unchanged working bytes."""

    if (
        git_bytes("rev-parse", f"{COMMON_ANCESTOR}^{{tree}}").decode().strip() != COMMON_TREE
        or git_bytes("merge-base", BASE_HEAD, STATE_DONOR_HEAD).decode().strip() != COMMON_ANCESTOR
    ):
        raise AssertionError("source common ancestry mismatch")
    changed: list[set[str]] = []
    identities: dict[str, Any] = {}
    for name, pin in SOURCE_PINS.items():
        head, tree = str(pin["head"]), str(pin["tree"])
        files = cast(dict[str, str], pin["files"])
        if git_bytes("show", "-s", "--format=%H %T", head).decode().strip() != f"{head} {tree}":
            raise AssertionError("source commit/tree identity mismatch")
        git_bytes("merge-base", "--is-ancestor", COMMON_ANCESTOR, head)
        paths = set(git_bytes("diff", "--name-only", COMMON_ANCESTOR, head).decode().splitlines())
        if paths != set(files):
            raise AssertionError("unexpected source change scope")
        changed.append(paths)
        for relative, expected in files.items():
            committed = git_bytes("show", f"{head}:{relative}")
            if (
                sha256(committed).hexdigest() != expected
                or (REPO_ROOT / relative).read_bytes() != committed
            ):
                raise AssertionError(f"source/result identity mismatch: {relative}")
        identities[name] = {"head": head, "tree": tree, "files_sha256": files}
    if changed[0] & changed[1]:
        raise AssertionError("source changes overlap")
    tail.verify_upstream_fingerprints()
    state.verify_upstream_fingerprints()
    return identities


def stored(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def adopt_state_certificate(donor: dict[str, Any]) -> dict[str, Any]:
    """Check existing arithmetic/witnesses and overlay exactly the 21 certified members."""

    members = state.target_region_ledger()
    carried = state.carried_member_certificates()
    ledger = {member.counts: member for member in members}
    records = cast(list[dict[str, Any]], donor["NEW_MEMBER_CERTIFICATES"])
    expected = [
        member.counts
        for _, rows in state.top_band(members)
        for member in rows
        if member.counts not in carried
    ]
    if (
        donor["TASK_ID"] != state.TASK_ID
        or donor["BASE_HEAD"] != COMMON_ANCESTOR
        or donor["BASE_TREE"] != COMMON_TREE
        or donor["STATE_ID"] != state.TARGET_STATE_ID
        or donor["REGION_SHA256"] != state.region_fingerprint(members)
        or donor["REGION_MEMBER_COUNT"] != len(members)
        or donor["REPRESENTED_VECTOR_COUNT"]
        != sum(member.represented_vector_count for member in members)
        or donor["TOP_BAND_MEMBER_COUNT"] != state.TOP_BAND_MEMBER_COUNT
        or donor["NEW_MEMBER_CERTIFICATE_COUNT"] != len(records)
        or len(records) != state.TOP_BAND_MEMBER_COUNT
        or [state.dense(row["member"]["witness_counts"]) for row in records] != expected
    ):
        raise AssertionError("State certificate/region identity or completeness mismatch")
    witness_count = 0
    for record in records:
        state.check_certificate_arithmetic(record)
        member = ledger[state.dense(record["member"]["witness_counts"])]
        if (
            record["joint_constant"] != state.r14.joint_constant()
            or record["member_raw_bound"] != member.raw_bound
            or record["member_prior_bound"] != member.final_bound
            or record["member"]["represented_vector_count"] != member.represented_vector_count
        ):
            raise AssertionError("State certificate differs from its carried member")
        for witness in record["support_witnesses"]:
            counts = state.dense(witness["counts"])
            support = tuple(
                tuple(int(label) for label in row) for row in witness["support_witness"]
            )
            if not state.r8.validate_support_assignment(counts, support):
                raise AssertionError("stored State witness is not legal")
            witness_count += 1
    bounds = state.recompute_state(members, records)
    complete = [
        {
            "witness_counts": state.sparse(member.counts),
            "represented_vector_count": member.represented_vector_count,
            "raw_bound": member.raw_bound,
            "r24_final_bound": member.final_bound,
            "final_bound": bounds[member.counts],
        }
        for member in members
    ]
    final = max(bounds.values())
    if donor["COMPLETE_REGION_MEMBERS"] != complete or donor["FINAL_STATE_BOUND"] != final:
        raise AssertionError("complete State region recomputation mismatch")
    return {
        "state_id": state.TARGET_STATE_ID,
        "region_sha256": state.region_fingerprint(members),
        "compressed_members": len(members),
        "represented_vectors": sum(member.represented_vector_count for member in members),
        "adopted_certificates": len(records),
        "carried_certificates": len(carried),
        "stored_witnesses_validated": witness_count,
        "complete_region_members_sha256": r24.digest(complete),
        "bound": final,
    }


def validate_tail_witnesses(certificate: dict[str, Any]) -> int:
    """Reconstruct only the two recorded witnesses, never minimize their Tail region."""

    checked = 0
    for row in certificate["MINIMIZER_REALIZATION"]:
        vectors = tuple(state.dense(vector) for vector in row["argmin_vectors"])
        witnesses = tuple(tail.r12.construct_support_witness(vector) for vector in vectors)
        if r24.digest(witnesses) != row["argmin_support_witness_sha256"] or any(
            witness is None or not tail.r8.validate_support_assignment(vector, witness)
            for vector, witness in zip(vectors, witnesses, strict=True)
        ):
            raise AssertionError("committed Tail witness identity or legality mismatch")
        checked += len(witnesses)
    return checked


def build_result() -> dict[str, Any]:
    identities = verify_sources()
    tail_result, donor = stored(tail.RESULT_PATH), stored(state.RESULT_PATH)
    states, classified = tail.committed_terms()
    if len(states) != 23 or len({key for key, _ in states}) != len(states):
        raise AssertionError("the complete 23-state catalog is required")
    authority = tail.r24_authority()
    # Each materialized R24 region must reproduce its catalog term. The other
    # states are carried verbatim from the same immutable sealed catalog.
    for region in authority["STATE_REGION_CERTIFICATES"]:
        maximum = max(int(row["final_bound"]) for row in region["complete_region_members"])
        if maximum != region["final_state_bound"] or dict(states)[region["owner_id"]] != maximum:
            raise AssertionError("R24 region/catalog maximum mismatch")
    canonical = r24.canonical_primitives()
    if (
        canonical != tail_result["CANONICAL_PRIMITIVES"]
        or canonical != donor["CANONICAL_PRIMITIVES"]
    ):
        raise AssertionError("canonical primitives differ between certificates")
    region = adopt_state_certificate(donor)
    certified_tail = int(tail_result["FINAL_TAIL_BOUND"])
    if certified_tail != r24.canonical_baseline() - tail.TAIL_START_LOSS - int(
        tail_result["UNIFORM_CORRECTION"]
    ):
        raise AssertionError("Tail correction must be applied exactly once")
    start = tail.family_maximum(certified_tail, states, classified)
    if start != tail_result["FAMILY_MAX_RECOMPUTATION"]:
        raise AssertionError("durable Tail family maximum mismatch")
    replacement = tuple(
        (key, int(region["bound"]) if key == state.TARGET_STATE_ID else bound)
        for key, bound in states
    )
    changed = [
        key
        for (key, before), (_, after) in zip(states, replacement, strict=True)
        if before != after
    ]
    if changed != [state.TARGET_STATE_ID]:
        raise AssertionError("exactly the certified target State must change")
    family = tail.family_maximum(certified_tail, replacement, classified)
    other_max = max(bound for key, bound in states if key != state.TARGET_STATE_ID)
    tail_witness_count = validate_tail_witnesses(tail_result)
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "SUCCESS_COMBINED_AUTHORITY",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_BRANCH": TASK_BRANCH,
        "COMMON_ANCESTOR": COMMON_ANCESTOR,
        "COMMON_TREE": COMMON_TREE,
        "SOURCE_IDENTITIES": identities,
        "SOURCE_ANCESTRY_STATUS": "PASS",
        "SOURCE_CHANGED_PATHS_DISJOINT": True,
        "R24_RESULT_SHA256": tail.UPSTREAM_SHA256[tail.R24_RESULT_RELATIVE],
        "CANONICAL_PRIMITIVES": canonical,
        "TARGET_STATE_ADOPTION": region,
        "STATE_TERM_COUNT": len(replacement),
        "START_STATE_TERMS": [{"stable_id": key, "bound": bound} for key, bound in states],
        "FINAL_STATE_TERMS": [{"stable_id": key, "bound": bound} for key, bound in replacement],
        "CHANGED_STATE_IDS": changed,
        "CLASSIFIED_TERM_COUNT": len(classified),
        "CLASSIFIED_TERMS_SHA256": r24.digest(classified),
        "CLASSIFIED_AGGREGATE": [
            {"stable_id": key, "bound": bound}
            for key, bound in classified
            if key == r24.AGGREGATE_ID
        ],
        "CLASSIFIED_TERMS_UNCHANGED": True,
        "OTHER_STATE_MAX": other_max,
        "CLASSIFIED_MAX": family["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"],
        "TAIL_CERTIFIED_BOUND": certified_tail,
        "STATE_CERTIFIED_BOUND": region["bound"],
        "START_FAMILY_MAX_RECOMPUTATION": start,
        "FINAL_FAMILY_MAX_RECOMPUTATION": family,
        "START_R3_FAMILY_BOUND": start["R3_BOUND"],
        "FINAL_R3_FAMILY_BOUND": family["R3_BOUND"],
        "FINAL_OWNER_IDS": family["OWNER_IDS"],
        "OWNER_TRANSITION": {"before": start["OWNER_IDS"], "after": family["OWNER_IDS"]},
        "CURRENT_INCUMBENT": r24.INCUMBENT,
        "REMAINING_GAP": int(family["R3_BOUND"]) - r24.INCUMBENT,
        "RESEARCH_EXPECTED_COMBINED_R3_UB": RESEARCH_EXPECTED_BOUND,
        "RESEARCH_EXPECTATION_MATCH": family["R3_BOUND"] == RESEARCH_EXPECTED_BOUND,
        "PROJECTION_DIFFERENCE": int(family["R3_BOUND"]) - RESEARCH_EXPECTED_BOUND,
        "PROJECTION_MISMATCH_REASON": "SEALED_R24_COMPETING_STATE_RETAINED"
        if family["R3_BOUND"] != RESEARCH_EXPECTED_BOUND
        else None,
        "DUPLICATE_CREDIT_STATUS": "PASS_R6_TAIL_ONCE_R14_REPLACEMENT_BY_MAX",
        "DUPLICATE_CORRECTIONS": 0,
        "FULL_STATE_CATALOG_RECOMPUTATION": "PASS_23_OF_23_EXACTLY_ONE_REPLACEMENT",
        "WITNESS_SOUNDNESS_STATUS": "PASS",
        "TAIL_RECORDED_WITNESSES_VALIDATED": tail_witness_count,
        "TAIL_MINIMIZATION_CALLS": 0,
        "NEW_STATE_CERTIFICATION_CALLS": 0,
        "R7_CENSUS_REBUILD_CALLS": 0,
        "NEW_HEAVY_SOLVER_STARTED": "NO",
        "OUTCOME_ENUMERATION_USED": False,
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "WORKTREE_DISPOSITION": "RETAIN",
    }


def encode(result: dict[str, Any]) -> str:
    return json.dumps(result, separators=(",", ":")) + "\n"


def verify_result(result: dict[str, Any]) -> dict[str, str]:
    if encode(result) != encode(build_result()):
        raise AssertionError("combined result is not completely reproducible")
    return {"status": "PASS"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--verify", action="store_true")
    options = parser.parse_args()
    if options.verify:
        print(json.dumps(verify_result(stored(RESULT_PATH))))
        return
    result = build_result()
    if not options.no_write:
        RESULT_PATH.write_text(encode(result), encoding="utf-8")
    print(
        json.dumps(
            {key: value for key, value in result.items() if not isinstance(value, (dict, list))},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
