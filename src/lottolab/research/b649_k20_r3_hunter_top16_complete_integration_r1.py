"""Adopt two immutable State certificates into the complete R3 authority.

Donor source/result bytes come exclusively from pinned Git objects. Hunter
theorems, finite minima and Top-16 projection completeness are inherited from
those sealed certificates, not rerun. Only recorded members, arithmetic,
compression signatures, legal witnesses and the full family maximum are checked.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Sequence
from dataclasses import replace
from hashlib import sha256
from itertools import combinations
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_r3_joint_residual_envelope_r7 as r7
from lottolab.research import b649_k20_r3_tail_state_combined_authority_r1 as base

r24, tail = base.r24, base.tail
r14, r8, r6, r5 = r24.r14, base.state.r8, base.state.r6, base.state.r5
TASK_ID = "B649_K20_R3_HUNTER_TOP16_COMPLETE_INTEGRATION_R1"
TASK_BRANCH = "codex/b649-k20-r3-hunter-top16-complete-integration-r1"
BASE_HEAD = "9f3658eaae8db9bad68cee6eeb078418ddd370c0"
BASE_TREE = "8ad4e8f368846ebd8c111ca8a0575b329ace45f0"
HUNTER_DONOR_HEAD = "a351edac1c433cccabe81b422ee046d160efa3d8"
TOP16_DONOR_HEAD = "6733f1248788c70d4716e30b509b574787c71c4f"
R24_HEAD = "27614636ac4c20392619b3d9364d22bf2af9cff4"
R24_TREE = "cd99dee2289867b45bc6142baed87d5e0dbab96a"
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_RELATIVE = r24.RESULTS + "b649-k20-r3-hunter-top16-complete-integration-r1-result.json"
RESULT_PATH = REPO_ROOT / RESULT_RELATIVE
HUNTER_STATE = "state:s2-12692531-s3-681744"
TOP16_STATE = "state:s2-14122976-s3-1005536"
HUNTER_REGION = "132cef5c91f5d6cf4798c8d8f65dba98d3851f33ec3d45b5d37fb7f61145ef15"
# Seal all carried R24 bounds and multiplicities, in addition to the raw-region identity.
HUNTER_CARRIED_LEDGER_SHA256 = "e4723f5ca5107765f87e2f4d5b463f1074e50e5339d3e367bb1ffa6436512e5d"
TOP16_REGION = "785409687cbaca559e536cf63ff87fb0e5f972796025ef03743e13ba5a88555e"
TOP16_COMBINATION = "MAX(R7_APPLIED_CORRECTION, MIN_REPRESENTED_VECTOR_R14_CORRECTION)"
HUNTER_COMBINATION = "MAX_OF_VALID_LOWER_BOUNDS_NEVER_SUM"
SOURCE_STEMS = {
    "BASE": "b649-k20-r3-tail-state-combined-authority-r1",
    "HUNTER": "b649-k20-r3-hunter-class-split-ladder-r1",
    "TOP16": "b649-k20-r3-state-14122976-top16-exact-certificate-r1",
}
SOURCE_PINS = {
    "BASE": (
        BASE_HEAD,
        BASE_TREE,
        "51e4eadd911f5468e9beb9287d2230883c3b7a78ae98805af049966908f71226",
        "f7af7f348825a7bab7d21b294a2fdd90c1078cc948116cf06b150c9722be6326",
    ),
    "HUNTER": (
        HUNTER_DONOR_HEAD,
        "8bcc8f0a851fa2f9ce271a6bfd333ff091b61c0a",
        "83efa8299b46ef17fc4cf394fb229e7b1d400fccee65c85d1a2cb29a550edde0",
        "c999332532a37c8515a1201e499f14f3d908fdfa2843d2f5fecfcf3bfcc6147a",
    ),
    "TOP16": (
        TOP16_DONOR_HEAD,
        "05feed027d28ecb76ded91e272d96af4bf6467f0",
        "4713ceb26f54119a51f12711dd22e3a90918de2abd4f2a6640127dfa6f2cdc2b",
        "dc16a3fb46bce48dd0ae28c4a5b415ee4695fffe9ca6215612b1455432dcc4e7",
    ),
}
SIBLING_RELATIVE = r24.RESULTS + "b649-k20-r3-hunter-next-sibling-certificate-r1-result.json"
LADDER = tuple(
    [[0, 13], *([[5, 5 - k]] if k < 5 else []), *([[16, k]] if k else [])] for k in range(6)
)
CountVector = tuple[int, ...]


def git_bytes(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(REPO_ROOT), *args])


def object_bytes(head: str, relative: str) -> bytes:
    """Fail closed on missing Git objects; never fall back to a donor checkout."""

    try:
        return git_bytes("show", f"{head}:{relative}")
    except subprocess.CalledProcessError as error:
        raise AssertionError(f"missing immutable object: {head}:{relative}") from error


def read_object(head: str, relative: str, expected: str) -> dict[str, Any]:
    data = object_bytes(head, relative)
    if sha256(data).hexdigest() != expected:
        raise AssertionError(f"immutable source/result SHA mismatch: {relative}")
    return cast(dict[str, Any], json.loads(data))


def source_paths(name: str) -> tuple[str, str]:
    stem = SOURCE_STEMS[name]
    return (
        "src/lottolab/research/" + stem.replace("-", "_") + ".py",
        r24.RESULTS + stem + "-result.json",
    )


def verify_sources() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Bind donor bytes, their scientific inputs and the executing shared modules."""

    if git_bytes("rev-parse", f"{R24_HEAD}^{{tree}}").decode().strip() != R24_TREE:
        raise AssertionError("common R24 tree mismatch")
    if (
        git_bytes("merge-base", BASE_HEAD, HUNTER_DONOR_HEAD).decode().strip() != R24_HEAD
        or git_bytes("merge-base", BASE_HEAD, TOP16_DONOR_HEAD).decode().strip() != BASE_HEAD
    ):
        raise AssertionError("donor common ancestry mismatch")
    base.verify_sources()
    payloads: dict[str, dict[str, Any]] = {}
    identities: dict[str, Any] = {}
    for name, (head, tree, source_sha, result_sha) in SOURCE_PINS.items():
        if git_bytes("rev-parse", f"{head}^{{tree}}").decode().strip() != tree:
            raise AssertionError("donor commit/tree identity mismatch")
        module, relative = source_paths(name)
        source = object_bytes(head, module)
        if sha256(source).hexdigest() != source_sha:
            raise AssertionError("immutable donor source SHA mismatch")
        payloads[name] = read_object(head, relative, result_sha)
        if name == "BASE" and (
            (REPO_ROOT / module).read_bytes() != source
            or (REPO_ROOT / relative).read_bytes() != object_bytes(head, relative)
        ):
            raise AssertionError("executing base source/result mismatch")
        upstream = cast(
            dict[str, str],
            payloads[name].get(
                "UPSTREAM_SHA256", payloads[name].get("UPSTREAM_FINGERPRINTS_SHA256", {})
            ),
        )
        for path, expected in upstream.items():
            committed = object_bytes(head, path)
            if sha256(committed).hexdigest() != expected:
                raise AssertionError("donor upstream SHA mismatch")
            if "hunter" not in path and path != source_paths("BASE")[1]:
                # These are common R24 scientific objects, not sibling certificates.
                if committed != object_bytes(R24_HEAD, path):
                    raise AssertionError("donor common R24 scientific source mismatch")
                if (
                    committed != object_bytes(BASE_HEAD, path)
                    or (REPO_ROOT / path).read_bytes() != committed
                ):
                    raise AssertionError("executing scientific source/result mismatch")
        identities[name] = {
            "head": head,
            "tree": tree,
            "source_path": module,
            "source_sha256": source_sha,
            "result_path": relative,
            "result_sha256": result_sha,
            "upstream_sha256": upstream,
        }
    hunter, top = payloads["HUNTER"], payloads["TOP16"]
    if hunter["SOURCE_FINGERPRINT"] != {
        "MODULE": source_paths("HUNTER")[0],
        "MODULE_SHA256": SOURCE_PINS["HUNTER"][2],
    } or (top["BASE_HEAD"], top["BASE_TREE"], top["R24_SOURCE"], top["R24_TREE"]) != (
        BASE_HEAD,
        BASE_TREE,
        R24_HEAD,
        R24_TREE,
    ):
        raise AssertionError("donor recorded source provenance mismatch")
    payloads["SIBLING"] = read_object(
        HUNTER_DONOR_HEAD, SIBLING_RELATIVE, hunter["UPSTREAM_SHA256"][SIBLING_RELATIVE]
    )
    payloads["R24"] = read_object(
        R24_HEAD, tail.R24_RESULT_RELATIVE, tail.UPSTREAM_SHA256[tail.R24_RESULT_RELATIVE]
    )
    return identities, payloads


def dense(sparse: list[list[int]]) -> CountVector:
    counts = r24.dense(sparse)
    if len(counts) != 30 or sum(counts) != 18 or min(counts) < 0 or r24.sparse(counts) != sparse:
        raise AssertionError("member count vector identity mismatch")
    return counts


def member_id(sparse: list[list[int]]) -> str:
    return "".join(f"[{index},{count}]" for index, count in sparse)


def hunter_witness(sparse: list[list[int]], witness: dict[str, Any]) -> None:
    """Check the recorded legal portfolio, without tree minimization or enumeration."""

    residual = tuple(frozenset(int(label) for label in row) for row in witness["RESIDUAL_TICKETS"])
    anchors = (frozenset(range(1, 7)), frozenset((1, 2, 3, 7, 8, 9)))
    portfolio = (*anchors, *residual)
    if (
        len(residual) != 18
        or len(set(portfolio)) != 20
        or any(len(t) != 6 or not t <= frozenset(range(1, 50)) for t in portfolio)
        or max(len(a & b) for a, b in combinations(portfolio, 2)) != 3
    ):
        raise AssertionError("illegal Hunter portfolio witness")
    cells = tuple((p.shared, p.a_only, p.b_only, p.outside) for p in r5.anchor_incidence_profiles())
    classes = (anchors[0] & anchors[1], anchors[0] - anchors[1], anchors[1] - anchors[0])
    observed = [0] * len(cells)
    for ticket in residual:
        local = tuple(len(ticket & group) for group in classes)
        observed[cells.index((*local, 6 - sum(local)))] += 1
    if tuple(observed) != dense(sparse):
        raise AssertionError("Hunter witness member identity mismatch")
    outcome = frozenset(range(10, 17))
    if sum(len(t & outcome) >= 3 for t in residual) != 18:
        raise AssertionError("Hunter cap-17 counterexample was lost")


def hunter_bound(record: dict[str, Any], raw_union: int, prior: int) -> int:
    terms = record["CORRECTIONS"]
    values = [
        int(terms[key])
        for key in (
            "R6_PAIR_SUM",
            "R5_FOREST",
            "R14_RATIONAL",
            "HUNTER_HOMOGENEOUS",
            "HUNTER_CLASS_SPLIT",
        )
    ]
    correction = max(values)
    bound = raw_union - correction
    if (
        terms["COMBINATION"] != HUNTER_COMBINATION
        or int(terms["CERTIFIED_CORRECTION"]) != correction
        or prior != raw_union - max(values[:2])
        or int(record["CERTIFIED_MEMBER_BOUND"]) != bound
        or bound > prior
        or not correction
        <= int(record["WITNESS"]["CENSUS_OBJECTIVE"])
        <= int(record["WITNESS"]["PHI_TREE_WEIGHT"])
        <= int(record["WITNESS"]["EXACT_MAXIMUM_TREE_WEIGHT"])
    ):
        raise AssertionError("Hunter correction arithmetic or witness consistency mismatch")
    return bound


def adopt_hunter(
    donor: dict[str, Any], sibling: dict[str, Any], authority: dict[str, Any]
) -> dict[str, Any]:
    regions = [r for r in authority["STATE_REGION_CERTIFICATES"] if r["owner_id"] == HUNTER_STATE]
    if len(regions) != 1:
        raise AssertionError("Hunter complete R24 region missing")
    region = regions[0]
    rows = cast(list[dict[str, Any]], region["complete_region_members"])
    ledger = {dense(row["witness_counts"]): row for row in rows}
    fingerprint = r24.digest(tuple((dense(r["witness_counts"]), int(r["raw_bound"])) for r in rows))
    if (
        donor["STATE_ID"] != HUNTER_STATE
        or donor["REGION_SHA256"] != HUNTER_REGION
        or region["region_sha256"] != fingerprint
        or fingerprint != HUNTER_REGION
        or r24.digest(rows) != HUNTER_CARRIED_LEDGER_SHA256
        or len(rows) != len(ledger)
        or len(rows) != 582
        or sum(int(r["represented_vector_count"]) for r in rows) != 633
        or donor["REGION"]["COMPRESSED_MEMBERS"] != 582
        or donor["REGION"]["VECTORS"] != 633
        or donor["LADDER"] != [member_id(s) for s in LADDER]
        or donor["LADDER_MEMBER_COUNT"] != 6
        or set(donor["MEMBER_CERTIFICATES"])
        != {member_id(s) for i, s in enumerate(LADDER) if i != 1}
        or set(donor["CERTIFIED_MEMBER_BOUNDS"]) != {member_id(s) for s in LADDER}
        or max(int(r["final_bound"]) for r in rows) != donor["START_STATE_BOUND"]
    ):
        raise AssertionError("Hunter region/ladder identity or completeness mismatch")
    bounds = {key: int(row["final_bound"]) for key, row in ledger.items()}
    for index, sparse in enumerate(LADDER):
        key = dense(sparse)
        carried = ledger[key]
        if (
            carried["represented_vector_count"] != 1
            or carried["final_bound"] > carried["raw_bound"]
        ):
            raise AssertionError("Hunter ladder must be a valid single-vector member")
        record = sibling if index == 1 else donor["MEMBER_CERTIFICATES"][member_id(sparse)]
        if record["MEMBER_COUNTS"] != sparse or (
            index == 1
            and (record["STATE_ID"] != HUNTER_STATE or record["REGION_SHA256"] != HUNTER_REGION)
        ):
            raise AssertionError("Hunter member certificate identity mismatch")
        raw = (
            int(record["EVENT_DEFINITION"]["RAW_UNION_BOUND_NO_CORRECTION"])
            if index == 1
            else int(record["RAW_UNION_BOUND_NO_CORRECTION"])
        )
        bound = hunter_bound(record, raw, int(carried["final_bound"]))
        if bound != donor["CERTIFIED_MEMBER_BOUNDS"][member_id(sparse)]["BOUND"]:
            raise AssertionError("Hunter donor/member bound mismatch")
        hunter_witness(sparse, record["WITNESS"])
        bounds[key] = bound
    complete = [
        row
        | {
            "prior_valid_bound": row["final_bound"],
            "final_bound": bounds[dense(row["witness_counts"])],
        }
        for row in rows
    ]
    maximum = max(bounds.values())
    if maximum != donor["REFINED_STATE_BOUND"]:
        raise AssertionError("Hunter complete State maximum mismatch")
    compressed = [r for r in complete if r["represented_vector_count"] > 1]
    if (
        len(compressed) != 49
        or sum(r["represented_vector_count"] for r in compressed) != 100
        or any(r["final_bound"] != r["prior_valid_bound"] for r in compressed)
        or max(r["final_bound"] for r in compressed)
        != donor["REGION"]["MAX_COMPRESSED_MEMBER_BOUND"]
        or any(
            r["represented_vector_count"] < 1 or r["final_bound"] > r["raw_bound"] for r in complete
        )
    ):
        raise AssertionError("Hunter compressed member preservation mismatch")
    return {
        "state_id": HUNTER_STATE,
        "region_sha256": fingerprint,
        "compressed_members": len(rows),
        "represented_vectors": 633,
        "adopted_member_certificates": 6,
        "carried_members": len(rows) - 6,
        "legal_portfolio_witnesses_validated": 6,
        "bound": maximum,
        "complete_region_members": complete,
        "compressed_treatment": "UNCHANGED_R24_WEAKEST_VALID_MEMBER_BOUND",
    }


def effective_correction(applied: int, vector_corrections: Sequence[int]) -> int:
    """The weakest represented-vector certificate bounds the whole compressed member."""

    if not vector_corrections or min(applied, *vector_corrections) < 0:
        raise AssertionError("missing or invalid vector corrections")
    return max(applied, min(vector_corrections))


def validate_support(vector: CountVector, witness: dict[str, Any]) -> None:
    support = tuple(tuple(int(label) for label in row) for row in witness["support_witness"])
    if (
        witness["counts"] != r24.sparse(vector)
        or witness["support_sha256"] != r24.digest(support)
        or not r8.validate_support_assignment(vector, support)
    ):
        raise AssertionError("illegal Top-16 support witness")


def check_top16_certificate(record: dict[str, Any], row: dict[str, Any]) -> None:
    member = row["member"]
    vectors = row["represented_vectors"]
    moments = cast(list[dict[str, Any]], record["vector_certificates"])
    witnesses = cast(list[dict[str, Any]], record["support_witnesses"])
    if (
        record["member"] != member
        or record["represented_vectors"] != vectors
        or [m["counts"] for m in moments] != vectors
        or [w["counts"] for w in witnesses] != vectors
    ):
        raise AssertionError("Top-16 certificate vector/member coverage mismatch")
    for moment, witness in zip(moments, witnesses, strict=True):
        s2 = int(moment["residual_s2_lower_bound"])
        if (
            moment["multiplicity_cap"] != 18
            or moment["multiplicity_dual"] != [1, 9]
            or int(moment["correction_lower_bound"]) != -(-2 * s2 // 18)
        ):
            raise AssertionError("Top-16 rational dual arithmetic mismatch")
        validate_support(dense(moment["counts"]), witness)
    applied = max(
        int(member["residual_pair_union_penalty"]), int(member["complementary_forest_floor"])
    )
    rational = min(int(m["correction_lower_bound"]) for m in moments)
    correction = effective_correction(applied, [int(m["correction_lower_bound"]) for m in moments])
    uncorrected = (
        r14.joint_constant() - int(member["anchor_pair_s2"]) + int(member["anchor_triple_s3"])
    )
    if (
        member["applied_residual_union_penalty"] != applied
        or member["joint_s2"] != member["anchor_pair_s2"] + applied
        or member["raw_bound"] != uncorrected - applied
        or record["joint_constant"] != r14.joint_constant()
        or record["uncorrected_anchor_bound"] != uncorrected
        or record["prior_applied_correction"] != applied
        or record["minimum_vector_rational_correction"] != rational
        or record["member_certified_correction"] != correction
        or record["member_raw_bound"] != row["prior_valid_bound"]
        or record["member_prior_bound"] != row["prior_valid_bound"]
        or record["member_new_bound"] != uncorrected - correction
        or record["member_drop"] != correction - applied
        or record["correction_combination"] != TOP16_COMBINATION
        or record["region_sha256"] != TOP16_REGION
    ):
        raise AssertionError("Top-16 correction arithmetic/double credit mismatch")


def adopt_top16(donor: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    rows = cast(list[dict[str, Any]], donor["COMPLETE_REGION_MEMBERS"])
    records = cast(list[dict[str, Any]], donor["NEW_MEMBER_CERTIFICATES"])
    ledger = {dense(row["member"]["witness_counts"]): row for row in rows}
    vectors = [dense(v) for row in rows for v in row["represented_vectors"]]
    fingerprint = r24.digest(
        tuple((dense(r["member"]["witness_counts"]), int(r["prior_valid_bound"])) for r in rows)
    )
    if (
        donor["STATE_ID"] != TOP16_STATE
        or donor["REGION_SHA256"] != TOP16_REGION
        or fingerprint != TOP16_REGION
        or len(rows) != len(ledger)
        or len(rows) != 214
        or len(vectors) != len(set(vectors))
        or len(vectors) != 221
        or donor["COMPRESSED_MEMBER_COUNT"] != 214
        or donor["REPRESENTED_VECTOR_COUNT"] != 221
        or donor["REGION_VECTORS_SHA256"] != r24.digest(tuple(sorted(vectors)))
        or donor["BASE_STATE_TERMS"] != baseline["FINAL_STATE_TERMS"]
        or donor["BASE_CLASSIFIED_TERMS_SHA256"] != baseline["CLASSIFIED_TERMS_SHA256"]
        or donor["CANONICAL_PRIMITIVES"] != baseline["CANONICAL_PRIMITIVES"]
        or donor["CARRIED_CERTIFIED_MEMBER_COUNT"] != 0
        or donor["REMAINDER_MEMBER_COUNT"] != 198
        or donor["TOP_BAND_CERTIFIED_COUNT"] != 16
        or len(records) != 16
        or max(r["prior_valid_bound"] for r in rows) != donor["START_STATE_BOUND"]
    ):
        raise AssertionError("Top-16 complete region/source identity mismatch")
    # Only reconstruct recorded vectors; never enumerate or project the domain.
    profiles = r5.anchor_incidence_profiles()
    losses = r6.local_losses(profiles)
    constructor_api, signature_api = "_make_state", "_state_signature"
    constructor = getattr(r7, constructor_api)
    signature = getattr(r7, signature_api)
    for row in rows:
        member = row["member"]
        vs = row["represented_vectors"]
        states = [cast(r7.ResidualJointState, constructor(dense(v), profiles, losses)) for v in vs]
        rebuilt = replace(states[0], represented_vector_count=len(vs))
        if (
            len(vs) != member["represented_vector_count"]
            or r24.sparse(min(dense(v) for v in vs)) != member["witness_counts"]
            or row["prior_valid_bound"] != member["raw_bound"]
            or base.state.normalized(r24.member_record(rebuilt)) != member
            or any(signature(s) != signature(rebuilt) for s in states)
            or any(
                not 951_748 < s.joint_s3 <= 1_005_536
                or s.joint_s2 < 14_122_976
                or s.local_loss > r7.JOINT_LOCAL_LOSS_CUTOFF
                for s in states
            )
        ):
            raise AssertionError("Top-16 recorded vector/compression/domain mismatch")
    expected = [
        key for key, row in ledger.items() if row["prior_valid_bound"] > donor["TOP_THRESHOLD"]
    ]
    adopted = [dense(r["member"]["witness_counts"]) for r in records]
    if adopted != expected or len(set(adopted)) != 16:
        raise AssertionError("Top-16 16/16 certificate coverage mismatch")
    bounds = {key: int(row["prior_valid_bound"]) for key, row in ledger.items()}
    for key, record in zip(adopted, records, strict=True):
        check_top16_certificate(record, ledger[key])
        bounds[key] = int(record["member_new_bound"])
    if any(row["final_bound"] != bounds[key] for key, row in ledger.items()):
        raise AssertionError("Top-16 remainder preservation or member bound mismatch")
    maximum = max(bounds.values())
    if (
        maximum != donor["FINAL_CERTIFIED_STATE_BOUND"]
        or max(bounds[key] for key in bounds if key not in adopted) != donor["REMAINDER_MAX"]
    ):
        raise AssertionError("Top-16 complete State maximum mismatch")
    compressed = [r for r in rows if len(r["represented_vectors"]) > 1]
    if len(compressed) != 7 or any(r["final_bound"] != r["prior_valid_bound"] for r in compressed):
        raise AssertionError("Top-16 compressed remainder preservation mismatch")
    for row in donor["TWO_VECTOR_MEMBERS"]:
        key = dense(row["member"]["witness_counts"])
        if (
            row["member"] != ledger[key]["member"]
            or row["represented_vectors"] != ledger[key]["represented_vectors"]
        ):
            raise AssertionError("Top-16 compressed witness coverage mismatch")
        for vector, witness in zip(
            row["represented_vectors"], row["support_witnesses"], strict=True
        ):
            validate_support(dense(vector), witness)
    if [r["member"] for r in donor["TWO_VECTOR_MEMBERS"]] != [r["member"] for r in compressed]:
        raise AssertionError("Top-16 compressed witness completeness mismatch")
    return {
        "state_id": TOP16_STATE,
        "region_sha256": fingerprint,
        "compressed_members": len(rows),
        "represented_vectors": len(vectors),
        "adopted_member_certificates": len(records),
        "carried_members": 198,
        "support_witnesses_validated": sum(len(r["support_witnesses"]) for r in records) + 14,
        "bound": maximum,
        "complete_region_members": rows,
        "compressed_treatment": "MAX_PRIOR_CORRECTION_MIN_VECTOR_CORRECTION",
    }


def build_result() -> dict[str, Any]:
    identities, inputs = verify_sources()
    baseline, authority = inputs["BASE"], inputs["R24"]
    _, classified = tail.committed_terms()
    states = tuple((str(r["stable_id"]), int(r["bound"])) for r in baseline["FINAL_STATE_TERMS"])
    if (
        len(states) != 23
        or len(dict(states)) != 23
        or r24.digest(classified) != baseline["CLASSIFIED_TERMS_SHA256"]
    ):
        raise AssertionError("complete 23-State/classified catalog identity mismatch")
    certified_tail = int(baseline["TAIL_CERTIFIED_BOUND"])
    start = tail.family_maximum(certified_tail, states, classified)
    if start != baseline["FINAL_FAMILY_MAX_RECOMPUTATION"]:
        raise AssertionError("base complete family maximum mismatch")
    hunter = adopt_hunter(inputs["HUNTER"], inputs["SIBLING"], authority)
    top = adopt_top16(inputs["TOP16"], baseline)
    replacements = {HUNTER_STATE: int(hunter["bound"]), TOP16_STATE: int(top["bound"])}
    if (
        dict(states)[HUNTER_STATE] != inputs["HUNTER"]["START_STATE_BOUND"]
        or dict(states)[TOP16_STATE] != inputs["TOP16"]["START_STATE_BOUND"]
    ):
        raise AssertionError("donor starting State term mismatch")
    final_states = tuple((key, replacements.get(key, bound)) for key, bound in states)
    changed = [
        key
        for (key, before), (_, after) in zip(states, final_states, strict=True)
        if before != after
    ]
    if set(changed) != set(replacements):
        raise AssertionError("exactly two certified State terms must change")
    family = tail.family_maximum(certified_tail, final_states, classified)
    other = max(bound for key, bound in final_states if key not in replacements)
    if baseline["CANONICAL_PRIMITIVES"] != r24.canonical_primitives():
        raise AssertionError("canonical primitive mismatch")
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "SUCCESS_COMPLETE_INTEGRATION_SELF_CHECK_ONLY",
        "TASK_BRANCH": TASK_BRANCH,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "HUNTER_DONOR_HEAD": HUNTER_DONOR_HEAD,
        "TOP16_DONOR_HEAD": TOP16_DONOR_HEAD,
        "COMMON_R24_HEAD": R24_HEAD,
        "COMMON_R24_TREE": R24_TREE,
        "SOURCE_IDENTITIES": identities,
        "SOURCE_PROVENANCE_STATUS": "PASS_IMMUTABLE_GIT_OBJECTS",
        "CANONICAL_PRIMITIVES": baseline["CANONICAL_PRIMITIVES"],
        "HUNTER_ADOPTION": hunter,
        "TOP16_ADOPTION": top,
        "HUNTER_REGION_COVERAGE": "582/582_MEMBERS_633/633_VECTORS",
        "TOP16_REGION_COVERAGE": "214/214_MEMBERS_221/221_VECTORS_16/16_CERTIFICATES",
        "HUNTER_STATE_NEW_BOUND": hunter["bound"],
        "TOP16_STATE_NEW_BOUND": top["bound"],
        "START_STATE_TERMS": baseline["FINAL_STATE_TERMS"],
        "FINAL_STATE_TERMS": [{"stable_id": key, "bound": bound} for key, bound in final_states],
        "STATE_TERM_COUNT": len(final_states),
        "CHANGED_STATE_IDS": changed,
        "OTHER_STATE_TERMS_UNCHANGED": len(states) - len(replacements),
        "TAIL_BOUND": certified_tail,
        "CLASSIFIED_MAX": family["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"],
        "CLASSIFIED_TERM_COUNT": len(classified),
        "CLASSIFIED_TERMS_SHA256": r24.digest(classified),
        "CLASSIFIED_AGGREGATE": baseline["CLASSIFIED_AGGREGATE"],
        "CLASSIFIED_TERMS_UNCHANGED": True,
        "OTHER_STATE_MAX": other,
        "START_FAMILY_MAX_RECOMPUTATION": start,
        "FINAL_FAMILY_MAX_RECOMPUTATION": family,
        "START_COMPLETE_R3_UB": start["R3_BOUND"],
        "FINAL_COMPLETE_R3_UB": family["R3_BOUND"],
        "FINAL_OWNER_IDS": family["OWNER_IDS"],
        "OWNER_TRANSITION": {"before": start["OWNER_IDS"], "after": family["OWNER_IDS"]},
        "CURRENT_INCUMBENT": r24.INCUMBENT,
        "REMAINING_GAP": int(family["R3_BOUND"]) - r24.INCUMBENT,
        "NON_DUPLICATE_CREDIT_STATUS": "PASS_ABSOLUTE_MEMBER_BOUND_REPLACEMENT_MAX_NEVER_SUM",
        "DUPLICATE_CORRECTIONS": 0,
        "FULL_23_STATE_RECOMPUTATION": "PASS_23_OF_23_TWO_REPLACEMENTS",
        "WITNESS_SOUNDNESS_STATUS": "PASS_6_PORTFOLIOS_30_SUPPORT_WITNESSES",
        "HUNTER_THEOREM_REPROOF_CALLS": 0,
        "HUNTER_MINIMIZATION_CALLS": 0,
        "TOP16_PROJECTION_CALLS": 0,
        "NEW_CERTIFICATION_CALLS": 0,
        "R7_CENSUS_REBUILD_CALLS": 0,
        "R25_STARTED": "NO",
        "NEW_HEAVY_SOLVER_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "WORKTREE_DISPOSITION": "RETAIN",
    }


def encode(result: dict[str, Any]) -> str:
    return json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n"


def verify_result(result: dict[str, Any]) -> dict[str, str]:
    if encode(result) != encode(build_result()):
        raise AssertionError("complete integration result does not reproduce deterministically")
    return {"status": "PASS"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--verify", action="store_true")
    options = parser.parse_args()
    if options.verify:
        print(json.dumps(verify_result(cast(dict[str, Any], json.loads(RESULT_PATH.read_text())))))
        return
    result = build_result()
    if options.write:
        RESULT_PATH.write_text(encode(result), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if not isinstance(v, (dict, list))}))


if __name__ == "__main__":
    main()
