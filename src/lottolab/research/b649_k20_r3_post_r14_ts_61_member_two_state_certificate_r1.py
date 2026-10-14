"""Certify the 61 post-R14 members that block the next R3 Family term.

Adopt the joint R14-89/TS53 result at 935a582e unchanged. The latest complete
ledgers are the joint certificate for State13169800 and TS-106 for
State12695020; no later sealed certificate changes the second one. The target
cutoff is the largest Family term outside these two States (21 States, every
Classified term and the Tail), so it is derived rather than chosen. Every
member above it is a target, including every represented vector of each
compressed member.

Each vector uses the TS-106 rule restricted to its full multiset or one-event
deletions. The TS53 subset proof checks complete occupied type pairs, exact
residual pair rows, type-applicable safe floors, balanced four-cell collision
floors and the complete nested-threshold Hunter minimum. Every omitted event
attaches to the first selected event, which extends the subset tree to a
spanning tree on all eighteen residual events. Each attachment row over all
legal overlaps is a nonnegative intersection, so Hunter's pointwise inequality
keeps H(u) for every support. Concrete legal witnesses show applicability only.

Credits combine by MAX with every sealed per-vector bound and are subtracted
once; a compressed member takes the MAX of its represented-vector bounds. No
census, solver, chase or official-outcome enumeration runs.
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

from lottolab.research import b649_k20_r3_r14_89_ts53_joint_certificate_r1 as joint

ts53, prior, h11 = joint.ts53, joint.prior, joint.h11
hunter, catalog, six, r24 = joint.hunter, joint.catalog, joint.six, joint.r24
LedgerMember = catalog.LedgerMember
type CountVector = tuple[int, ...]
dense, sparse, digest, member_id = joint.dense, joint.sparse, joint.digest, joint.member_id
TASK_ID = "B649_K20_R3_POST_R14_TS_61_MEMBER_TWO_STATE_CERTIFICATE_R1"
TASK_BRANCH = "codex/b649-k20-r3-post-r14-ts-61-member-two-state-certificate-r1"
BASE_HEAD = "935a582edfefa8b4405c34499e7f30daa9d24e22"
BASE_TREE = "dd9e1e52ef7da0eab21157af5df587efb04a644e"
BASE_RESULT_SHA256 = "300044f832661c5fd43d06c5c458c2450984351b643498eb4e0d3e79058d8a0c"
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_RELATIVE = (
    six.RESULTS + "b649-k20-r3-post-r14-ts-61-member-two-state-certificate-r1-result.json"
)
RESULT_PATH = REPO_ROOT / RESULT_RELATIVE
STATE_13169800 = "state:s2-13169800-s3-789320"
STATE_12695020 = "state:s2-12695020-s3-735532"
OWNER_STATE = "state:s2-12692531-s3-681744"
# Region fingerprint, members, vectors, target members, target vectors, compressed targets.
REGION_SPECS = {
    STATE_13169800: (
        "c183f8d2f93d3a695fcae3e2d2d280d40ffb1de3527eb43e61ce5321569dcde1",
        989,
        1072,
        3,
        3,
        0,
    ),
    STATE_12695020: (
        "46023fc93f2fd7d9b211d29494d05d8f6bfd4867992b0121cd8db0b7def5cd5b",
        1222,
        1325,
        58,
        66,
        8,
    ),
}
RESIDUAL_EVENT_DEFINITION = ts53.RESIDUAL_EVENT_DEFINITION
CORRECTION_COMBINATION = "MAX(EXISTING_VALID_CREDITS, SEALED_VECTOR, SUBSET_HUNTER); SUBTRACT_ONCE"


def source_paths() -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                *ts53.source_paths(),
                *joint.DONOR_PATHS,
                str(Path(joint.__file__).resolve().relative_to(REPO_ROOT)),
                joint.RESULT_RELATIVE,
            }
        )
    )


def git_bytes(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(REPO_ROOT), *args])


def verify_source_authority() -> dict[str, Any]:
    """Uncached immutable objects, lineage and every executing donor byte."""
    upstream = joint.verify_source_authority()
    identity = git_bytes("show", "-s", "--format=%H %T", BASE_HEAD).decode().strip()
    blob = git_bytes("show", f"{BASE_HEAD}:{joint.RESULT_RELATIVE}")
    if identity != f"{BASE_HEAD} {BASE_TREE}" or sha256(blob).hexdigest() != BASE_RESULT_SHA256:
        raise AssertionError("immutable BASE_HEAD/TREE/result SHA authority failed")
    if subprocess.run(
        ["git", "-C", str(REPO_ROOT), "merge-base", "--is-ancestor", BASE_HEAD, "HEAD"],
        check=False,
    ).returncode:
        raise AssertionError("checkout does not descend from the immutable base")
    fingerprints: dict[str, str] = {}
    for relative in source_paths():
        frozen = git_bytes("show", f"{BASE_HEAD}:{relative}")
        if (REPO_ROOT / relative).read_bytes() != frozen:
            raise AssertionError(f"immutable donor source or sealed input changed: {relative}")
        fingerprints[relative] = sha256(frozen).hexdigest()
    return {
        "HEAD": BASE_HEAD,
        "TREE": BASE_TREE,
        "RESULT_SHA256": BASE_RESULT_SHA256,
        "upstream_objects": upstream["objects"],
        "donor_sha256": fingerprints,
    }


@cache
def source_results() -> dict[str, dict[str, Any]]:
    """Adopt sealed predecessors byte-exactly; never rebuild their certificates."""
    verify_source_authority()
    results = {
        name: cast(dict[str, Any], json.loads(module.RESULT_PATH.read_bytes()))
        for name, module in (("JOINT", joint), ("TS53", ts53), ("H11", h11), ("TS106", prior))
    }
    current = results["JOINT"]
    if (
        current["TASK_ID"] != joint.TASK_ID
        or current["TASK_STATUS"] != "SUCCESS"
        or current["FINAL_COMPLETE_R3_UB"] != 355243700
        or current["FINAL_OWNER_IDS"] != [STATE_13169800]
        or joint.STATE_B != STATE_13169800
        or joint.STATE_A != OWNER_STATE
        or prior.h0.joint.TARGET_STATE_ID != STATE_12695020
        or results["TS106"]["TASK_ID"] != prior.TASK_ID
    ):
        raise AssertionError("sealed joint R14/TS53 predecessor identity failed")
    return results


def state_terms() -> tuple[tuple[str, int], ...]:
    return tuple(
        (str(r["stable_id"]), int(r["bound"]))
        for r in source_results()["JOINT"]["FINAL_STATE_TERMS"]
    )


def classified_terms() -> tuple[tuple[str, int], ...]:
    return tuple(
        (str(r["stable_id"]), int(r["bound"]))
        for r in prior.source_results()["JOINT"]["FINAL_CLASSIFIED_TERMS"]
    )


def ledger_authority() -> dict[str, str]:
    """Name the latest sealed complete ledger of each target State."""
    results = source_results()
    joint_states = [r["state_id"] for r in results["JOINT"]["REGIONS"]]
    ts106_states = [r["state_id"] for r in results["TS106"]["REGIONS"]]
    start = dict(
        (str(r["stable_id"]), int(r["bound"])) for r in results["JOINT"]["START_STATE_TERMS"]
    )
    ts106_final = {r["state_id"]: r["final_state_bound"] for r in results["TS106"]["REGIONS"]}
    if (
        joint_states != [OWNER_STATE, STATE_13169800]
        or STATE_12695020 not in ts106_states
        or results["TS53"]["STATE_ID"] == STATE_12695020
        or results["H11"]["STATE_ID"] == STATE_12695020
        or start[STATE_12695020] != dict(state_terms())[STATE_12695020]
        or ts106_final[STATE_12695020] != start[STATE_12695020]
    ):
        raise AssertionError("latest complete-ledger authority failed")
    return {
        STATE_13169800: joint.RESULT_RELATIVE,
        STATE_12695020: prior.RESULT_RELATIVE,
    }


def region_rows(state_id: str) -> list[dict[str, Any]]:
    authority = ledger_authority()
    if state_id not in authority:
        raise AssertionError("unknown target State")
    name = "JOINT" if authority[state_id] == joint.RESULT_RELATIVE else "TS106"
    regions = [r for r in source_results()[name]["REGIONS"] if r["state_id"] == state_id]
    if len(regions) != 1:
        raise AssertionError("exactly one sealed ledger per target State required")
    return cast(list[dict[str, Any]], regions[0]["complete_region_members"])


@cache
def region_members(state_id: str) -> tuple[LedgerMember, ...]:
    rows = region_rows(state_id)
    members = tuple(
        LedgerMember(
            dense(r["witness_counts"]),
            int(r["represented_vector_count"]),
            int(r["raw_bound"]),
            int(r["final_bound"]),
        )
        for r in rows
    )
    fingerprint, mc, vc, _, _, _ = REGION_SPECS[state_id]
    if (
        len(members) != mc
        or len({m.counts for m in members}) != mc
        or sum(m.represented_vector_count for m in members) != vc
        or catalog.region_fingerprint(members) != fingerprint
        or max(m.final_bound for m in members) != dict(state_terms())[state_id]
        or any(
            m.represented_vector_count < 1
            or m.final_bound > m.raw_bound
            or m.final_bound > int(r["prior_bound"])
            or r["member_id"] != member_id(m.counts)
            for m, r in zip(members, rows, strict=True)
        )
    ):
        raise AssertionError("complete latest region identity failed")
    return members


@cache
def represented_vectors(state_id: str) -> dict[CountVector, tuple[CountVector, ...]]:
    """Recover every represented vector independently of the sealed lists."""
    members = region_members(state_id)
    recovered = catalog.r17.represented_vectors(tuple(catalog.rebuild_member(m) for m in members))
    flat = [v for vs in recovered.values() for v in vs]
    if (
        set(recovered) != {m.counts for m in members}
        or len(flat) != len(set(flat))
        or len(flat) != REGION_SPECS[state_id][2]
    ):
        raise AssertionError("complete represented-vector region coverage failed")
    for m, row in zip(members, region_rows(state_id), strict=True):
        vs = recovered[m.counts]
        signature = hunter.eleven.compression_signature(catalog.rebuild_member(m))
        if (
            len(vs) != m.represented_vector_count
            or vs != tuple(sorted(vs))
            or min(vs) != m.counts
            or row["represented_vectors"] != [sparse(v) for v in vs]
            or row["compression_signature"] != catalog.normalized(signature)
        ):
            raise AssertionError("sealed canonical/compression identity failed")
        for v in vs:
            state = catalog.rebuild_member(replace(m, counts=v, represented_vector_count=1))
            if (
                len(v) != 30
                or sum(v) != 18
                or any(type(c) is not int or c < 0 for c in v)
                or hunter.eleven.compression_signature(state) != signature
                or hunter.r14.raw_bound(state) != m.raw_bound
            ):
                raise AssertionError("represented-vector compression signature failed")
    return recovered


def target_cutoff() -> int:
    """The largest Family term that this certificate cannot change."""
    others = [b for k, b in state_terms() if k not in REGION_SPECS]
    classified = classified_terms()
    if len(others) != 21 or len(classified) != 56550:
        raise AssertionError("complete untouched Family term coverage failed")
    return max(*others, max(b for _, b in classified), six.sealed_tail_bound())


def expected_aliases(state_id: str) -> tuple[tuple[CountVector, CountVector], ...]:
    if state_id == STATE_13169800:
        return ()
    if state_id != STATE_12695020:
        raise AssertionError("unknown alias State")

    def vector(j: int, a: int, b: int) -> CountVector:
        return joint.parameter_vector({0: 10, 1: j, 4: 6 - j, a: 1, b: 1})

    pairs = (
        *((vector(j, 9, 17), vector(j, 6, 19)) for j in range(7)),
        (
            vector(2, 6, 17),
            vector(4, 9, 19),
        ),
    )
    return tuple(sorted((min(a, b), max(a, b)) for a, b in pairs))


def target_members(state_id: str) -> tuple[LedgerMember, ...]:
    """Recover targets from the complete ledger, with no handwritten ID filter."""
    members, vectors = region_members(state_id), represented_vectors(state_id)
    cutoff = target_cutoff()
    targets = tuple(m for m in members if m.final_bound > cutoff)
    _, _, _, tc, tv, compressed = REGION_SPECS[state_id]
    aliases = tuple(
        cast(tuple[CountVector, CountVector], vectors[m.counts])
        for m in targets
        if len(vectors[m.counts]) > 1
    )
    if (
        len(targets) != tc
        or sum(len(vectors[m.counts]) for m in targets) != tv
        or sum(m.represented_vector_count for m in targets) != tv
        or len(aliases) != compressed
        or any(len(a) != 2 for a in aliases)
        or tuple(sorted(aliases)) != expected_aliases(state_id)
    ):
        raise AssertionError("exact target member/vector/alias coverage failed")
    return targets


def tree_extension_proof(v: CountVector, u: CountVector) -> dict[str, Any]:
    """Attach each omitted event to the first selected event, for every support."""
    ts53.validate_subset(v, u)
    root = next(i for i, c in enumerate(u) if c)
    omitted = tuple(i for i in range(30) for _ in range(v[i] - u[i]))
    attachments: list[dict[str, Any]] = []
    for t in omitted:
        pair = (min(root, t), max(root, t))
        rows = prior.verified_pair_rows(pair)
        if not rows or min(r[6] for r in rows) < 0:
            raise AssertionError("an attachment edge can have negative intersection weight")
        attachments.append(
            {
                "omitted_type": t,
                "attach_type": root,
                "legal_row_count": len(rows),
                "minimum_intersection": min(r[6] for r in rows),
            }
        )
    if sum(u) - 1 + len(omitted) != 17 or sum(u) + len(omitted) != 18:
        raise AssertionError("extended tree must span all eighteen residual events")
    return {
        "subset_tree_edges": sum(u) - 1,
        "attachment_edges": attachments,
        "extended_tree_edges": 17,
        "rule": "subset tree + omitted events attached to the first selected event",
    }


@cache
def sealed_vector_bounds() -> dict[CountVector, tuple[tuple[str, int], ...]]:
    """Every immutable per-vector bound, including R14, TS, H0 and H11 results."""
    found: dict[CountVector, set[tuple[str, int]]] = {}

    def visit(value: Any, source: str) -> None:
        if isinstance(value, dict):
            row = cast(dict[str, Any], value)
            if "counts" in row and "vector_new_bound" in row:
                found.setdefault(dense(row["counts"]), set()).add(
                    (source, int(row["vector_new_bound"]))
                )
            for child in row.values():
                visit(child, source)
        elif isinstance(value, list):
            for child in cast(list[Any], value):
                visit(child, source)

    for relative in source_paths():
        if relative.endswith(".json"):
            visit(json.loads((REPO_ROOT / relative).read_bytes()), relative)
    return {v: tuple(sorted(rows)) for v, rows in found.items()}


def certify_vector(state_id: str, member: LedgerMember, v: CountVector) -> dict[str, Any]:
    if (
        member not in target_members(state_id)
        or v not in represented_vectors(state_id)[member.counts]
    ):
        raise AssertionError("target member or represented-vector membership failed")
    u = ts53.select_subset(v)
    proof = ts53.subset_proof(u)
    extension = tree_extension_proof(v, u)
    state = catalog.rebuild_member(replace(member, counts=v, represented_vector_count=1))
    uncorrected = hunter.r14.joint_constant() - state.anchor_pair_s2 + state.anchor_triple_s3
    residual = sum(c * hunter.residual_event_size(i) for i, c in enumerate(v))
    sealed = sealed_vector_bounds().get(v, ())
    prior_bound = min((member.final_bound, *(b for _, b in sealed)))
    credits = {
        "R6_PAIR": state.residual_pair_union_penalty,
        "FOREST": state.complementary_forest_floor,
        "SEALED_MEMBER": uncorrected - member.final_bound,
        "SEALED_VECTOR": uncorrected - prior_bound,
    }
    existing = hunter.combine_corrections(credits)
    credits["SUBSET_HUNTER"] = int(proof["hunter_floor"])
    combined = hunter.combine_corrections(credits)
    bound = min(prior_bound, uncorrected - combined)
    if (
        uncorrected != hunter.anchor_union_size() + residual
        or min(credits.values()) < 0
        or existing != uncorrected - prior_bound
        or combined != max(credits.values())
        or bound != hunter.member_bound(uncorrected, combined)
        or bound >= member.final_bound
    ):
        raise AssertionError("MAX-only single replacement or existing credit preservation failed")
    for support in joint.carried_supports().get(v, ()):
        if not hunter.r8.validate_support_assignment(v, support):
            raise AssertionError("applicable carried legal witness is unsound")
    return catalog.normalized(
        {
            "vector_id": member_id(v),
            "counts": sparse(v),
            "selected_subset_counts": sparse(u),
            "deleted_event_types": [i for i in range(30) for _ in range(v[i] - u[i])],
            "proof_id": digest(u),
            "anchor_union": hunter.anchor_union_size(),
            "residual_event_sum": residual,
            "uncorrected_anchor_bound": uncorrected,
            "sealed_vector_bounds": sealed,
            "corrections": credits,
            "prior_applied_correction": existing,
            "combined_correction": combined,
            "vector_prior_bound": prior_bound,
            "vector_new_bound": bound,
            "tree_extension": extension,
            "witness_analysis": prior.witness_analysis(v, u, proof),
        }
    )


def certify_member(state_id: str, member: LedgerMember) -> dict[str, Any]:
    vectors = represented_vectors(state_id)[member.counts]
    rows = [certify_vector(state_id, member, v) for v in vectors]
    bound = max(int(r["vector_new_bound"]) for r in rows)
    if len(rows) != member.represented_vector_count or bound >= member.final_bound:
        raise AssertionError("compressed member must MAX all represented-vector safe bounds")
    return {
        "member_id": member_id(member.counts),
        "witness_counts": sparse(member.counts),
        "represented_vector_count": len(vectors),
        "represented_vectors": [sparse(v) for v in vectors],
        "member_prior_bound": member.final_bound,
        "member_raw_bound": member.raw_bound,
        "member_new_bound": bound,
        "vector_certificates": rows,
        "correction_combination": CORRECTION_COMBINATION,
    }


@cache
def region_certificate(state_id: str) -> dict[str, Any]:
    members, vectors = region_members(state_id), represented_vectors(state_id)
    targets = target_members(state_id)
    records = [certify_member(state_id, m) for m in targets]
    priors = {m.counts: m.final_bound for m in members}
    bounds = six.replaced_bounds(priors, records)
    target_counts = {m.counts for m in targets}
    remainder = tuple(m for m in members if m.counts not in target_counts)
    if {c for c in priors if bounds[c] != priors[c]} != target_counts or any(
        bounds[m.counts] != m.final_bound for m in remainder
    ):
        raise AssertionError("untouched non-target bounds changed")
    return catalog.normalized(
        {
            "state_id": state_id,
            "ledger_source": ledger_authority()[state_id],
            "region_sha256": catalog.region_fingerprint(members),
            "region_member_count": len(members),
            "region_vector_count": sum(len(v) for v in vectors.values()),
            "all_represented_vectors_sha256": digest(
                tuple((m.counts, vectors[m.counts]) for m in members)
            ),
            "target_member_count": len(records),
            "target_vector_count": sum(r["represented_vector_count"] for r in records),
            "compressed_target_count": sum(r["represented_vector_count"] > 1 for r in records),
            "compression_aliases": [
                [sparse(v) for v in pair] for pair in expected_aliases(state_id)
            ],
            "member_certificates": records,
            "target_cohort_max": max(r["member_new_bound"] for r in records),
            "preserved_member_count": len(remainder),
            "preserved_vector_count": sum(len(vectors[m.counts]) for m in remainder),
            "preserved_remainder_max": max(m.final_bound for m in remainder),
            "preserved_bounds_sha256": digest(tuple((m.counts, m.final_bound) for m in remainder)),
            "complete_updated_bounds_sha256": digest(
                tuple((m.counts, bounds[m.counts]) for m in members)
            ),
            "complete_region_members": [
                {**row, "prior_bound": m.final_bound, "final_bound": bounds[m.counts]}
                for m, row in zip(members, region_rows(state_id), strict=True)
            ],
            "start_state_bound": max(priors.values()),
            "new_state_bound": max(bounds.values()),
            "new_state_member_ids": [
                member_id(c) for c, b in bounds.items() if b == max(bounds.values())
            ],
        }
    )


def recompute_family(regions: list[dict[str, Any]]) -> dict[str, Any]:
    source = source_results()["JOINT"]
    states, classified = state_terms(), classified_terms()
    tail = six.sealed_tail_bound()
    start = six.tail.family_maximum(tail, states, classified)
    replacements = {str(r["state_id"]): int(r["new_state_bound"]) for r in regions}
    if (
        len(states) != 23
        or len(dict(states)) != 23
        or not set(REGION_SPECS) <= dict(states).keys()
        or set(replacements) != set(REGION_SPECS)
        or len(regions) != 2
        or len(classified) != 56550
        or len(dict(classified)) != 56550
        or digest(classified) != source["CLASSIFIED_TERMS_SHA256"]
        or max(b for _, b in classified) != source["CLASSIFIED_MAX"]
        or tail != source["TAIL_BOUND"]
        or start != source["FINAL_FAMILY_MAX_RECOMPUTATION"]
        or start["R3_BOUND"] != source["FINAL_COMPLETE_R3_UB"]
    ):
        raise AssertionError("complete 23-State/Classified/Tail recomputation failed")
    updated = tuple((k, replacements.get(k, b)) for k, b in states)
    final = six.tail.family_maximum(tail, updated, classified)
    terms = (*updated, *classified, (r24.TAIL_ID, tail))
    maximum = max(b for _, b in terms)
    runner = max(b for _, b in terms if b < maximum)
    if final["R3_BOUND"] != maximum or final["OWNER_IDS"] != [k for k, b in terms if b == maximum]:
        raise AssertionError("independent Family maximum or owner recount failed")
    return {
        "start": start,
        "final": final,
        "start_states": states,
        "states": updated,
        "classified_count": len(classified),
        "classified_sha256": digest(classified),
        "classified_max": max(b for _, b in classified),
        "tail": tail,
        "runner_up": {"bound": runner, "owner_ids": [k for k, b in terms if b == runner]},
    }


def build_result() -> dict[str, Any]:
    authority = verify_source_authority()
    cutoff = target_cutoff()
    regions = [region_certificate(sid) for sid in REGION_SPECS]
    family = recompute_family(regions)
    states = dict(family["states"])
    a, b = regions
    subsets = {
        dense(row["selected_subset_counts"])
        for region in regions
        for record in region["member_certificates"]
        for row in record["vector_certificates"]
    }
    r14_vectors = {v for sid in joint.REGION_SPECS for v in joint.target_parameters(sid)}
    target_vectors = {
        dense(row["counts"])
        for region in regions
        for record in region["member_certificates"]
        for row in record["vector_certificates"]
    }
    if (
        cutoff != 355235139
        or (a["state_id"], b["state_id"]) != (STATE_13169800, STATE_12695020)
        or (a["target_cohort_max"], b["target_cohort_max"]) != (354044236, 352913883)
        or (a["preserved_member_count"], a["preserved_vector_count"]) != (986, 1069)
        or (b["preserved_member_count"], b["preserved_vector_count"]) != (1164, 1259)
        or (a["preserved_remainder_max"], b["preserved_remainder_max"]) != (355176136, 355213740)
        or states[STATE_13169800] != 355176136
        or states[STATE_12695020] != 355213740
        or states[OWNER_STATE] != 355235139
        or states[ts53.TARGET_STATE_ID] != 355116818
        or family["classified_max"] != 355145504
        or family["tail"] != 354039277
        or family["start"]["R3_BOUND"] != 355243700
        or family["final"]["R3_BOUND"] != 355235139
        or family["final"]["OWNER_IDS"] != [OWNER_STATE]
        or family["runner_up"] != {"bound": 355213740, "owner_ids": [STATE_12695020]}
        or len(target_vectors) != 69
        or r14_vectors & target_vectors
        or r24.INCUMBENT != 313263888
    ):
        raise AssertionError("recomputed State/Family owner/runner-up acceptance failed")
    return catalog.normalized(
        {
            "TASK_ID": TASK_ID,
            "TASK_STATUS": "SUCCESS",
            "TASK_BRANCH": TASK_BRANCH,
            "MODEL": "最強模型",
            "REMAINING_TASK_MODEL": "最強模型",
            "MODEL_LABEL_SOURCE": "OWNER_REQUEST; NOT_A_RUNTIME_MODEL_ATTESTATION",
            "BASE_HEAD": BASE_HEAD,
            "BASE_TREE": BASE_TREE,
            "BASE_RESULT_SHA256": BASE_RESULT_SHA256,
            "SOURCE_AUTHORITY": authority,
            "SOURCE_AUTHORITY_STATUS": "PASS_OBJECTS_LINEAGE_AND_EXECUTING_DONOR_BYTES",
            "LEDGER_AUTHORITY": ledger_authority(),
            "TARGET_SELECTION": "current_final_bound > max(untouched Family terms)",
            "TARGET_CUTOFF": cutoff,
            "SUBSET_SELECTION_RULE": (
                "TS106_RULE_ON_FULL_VECTOR_OR_DELETE_ONE_EVENT; GLOBAL_BEST_NOT_REQUIRED"
            ),
            "SUBSET_PROOFS": [ts53.subset_proof(u) for u in sorted(subsets)],
            "REGIONS": regions,
            "TARGET_MEMBER_COUNT": sum(r["target_member_count"] for r in regions),
            "TARGET_VECTOR_COUNT": sum(r["target_vector_count"] for r in regions),
            "COMPRESSED_TARGET_COUNT": sum(r["compressed_target_count"] for r in regions),
            "R14_TARGET_OVERLAP": len(r14_vectors & target_vectors),
            "SELECTED_SUBSET_VALIDITY": "PASS_INTEGER_0_LE_U_LE_V_17_OR_18_EVENTS",
            "PAIR_FLOOR_STATUS": "PASS_COMPLETE_TYPE_PAIRS_EXACT_ROWS_TYPE_APPLICABLE_FLOORS",
            "COLLISION_FLOOR_STATUS": "PASS_BALANCED_INTEGER_FREQUENCIES_IN_ALL_FOUR_CELLS",
            "HUNTER_THRESHOLD_STATUS": "PASS_COMPLETE_NESTED_THRESHOLD_INTEGER_MINIMA",
            "SUBSET_TREE_EXTENSION_STATUS": "PASS_SPANNING_18_EVENT_NONNEGATIVE_ATTACHMENTS",
            "CURRENT_CREDIT_STATUS": "PASS_R6_FOREST_SEALED_MEMBER_AND_ALL_SEALED_VECTOR_BOUNDS",
            "CORRECTION_COMBINATION": CORRECTION_COMBINATION,
            "NO_DOUBLE_COUNT_STATUS": "PASS_MAX_SUBTRACT_ONCE_MEMBER_MAX",
            "PRESERVED_REMAINDER_STATUS": "PASS_EVERY_UNTOUCHED_MEMBER_AND_VECTOR",
            "NEW_STATE_13169800_UB": states[STATE_13169800],
            "NEW_STATE_12695020_UB": states[STATE_12695020],
            "START_STATE_TERMS": [{"stable_id": k, "bound": v} for k, v in family["start_states"]],
            "FINAL_STATE_TERMS": [{"stable_id": k, "bound": v} for k, v in family["states"]],
            "START_FAMILY_MAX_RECOMPUTATION": family["start"],
            "FINAL_FAMILY_MAX_RECOMPUTATION": family["final"],
            "START_COMPLETE_R3_UB": family["start"]["R3_BOUND"],
            "FINAL_COMPLETE_R3_UB": family["final"]["R3_BOUND"],
            "FINAL_OWNER_IDS": family["final"]["OWNER_IDS"],
            "RUNNER_UP": family["runner_up"],
            "STRICT_GAIN": family["start"]["R3_BOUND"] - family["final"]["R3_BOUND"],
            "CURRENT_INCUMBENT": r24.INCUMBENT,
            "REMAINING_GAP": family["final"]["R3_BOUND"] - r24.INCUMBENT,
            "FULL_23_STATE_RECOMPUTATION": "PASS_ALL_23_UNIQUE_TERMS",
            "CLASSIFIED_TERM_COUNT": family["classified_count"],
            "CLASSIFIED_TERMS_SHA256": family["classified_sha256"],
            "CLASSIFIED_MAX": family["classified_max"],
            "TAIL_BOUND": family["tail"],
            "CLASSIFIED_RECOMPUTATION": "PASS_ALL_56550_TERMS_UNCHANGED",
            "TAIL_RECOMPUTATION": "PASS_SEALED_FORMULA_SINGLE_CORRECTION",
            "WITNESS_SOUNDNESS_STATUS": "PASS_69_LEGAL_SUPPORTS_AND_ALL_CARRIED_SUPPORTS",
            "R7_CENSUS_REBUILD_CALLS": 0,
            "OUTCOME_ENUMERATION_USED": False,
            "NEW_HEAVY_SOLVER_STARTED": "NO",
            "PRODUCTION_MUTATION": "NONE",
            "PUSH_PR_MERGE": "NONE",
            "WORKTREE_DISPOSITION": "RETAIN",
        }
    )


def encode(result: dict[str, Any]) -> str:
    return hunter.encode(result)


def verify_result(result: dict[str, Any]) -> dict[str, Any]:
    verify_source_authority()
    regions = result["REGIONS"]
    if [r["state_id"] for r in regions] != list(REGION_SPECS):
        raise AssertionError("exact two-State coverage failed")
    proofs = {p["proof_id"]: p for p in result["SUBSET_PROOFS"]}
    for region in regions:
        sid = str(region["state_id"])
        targets = target_members(sid)
        records = region["member_certificates"]
        if [r["member_id"] for r in records] != [member_id(m.counts) for m in targets]:
            raise AssertionError("complete target member coverage failed")
        for record, member in zip(records, targets, strict=True):
            vectors = represented_vectors(sid)[member.counts]
            rows = record["vector_certificates"]
            if (
                record["represented_vectors"] != [sparse(v) for v in vectors]
                or len(rows) != len(vectors)
                or record["represented_vector_count"] != len(vectors)
            ):
                raise AssertionError("complete represented-vector coverage failed")
            for row, v in zip(rows, vectors, strict=True):
                u = dense(row["selected_subset_counts"])
                ts53.validate_subset(v, u)
                if row["counts"] != sparse(v) or u != ts53.select_subset(v):
                    raise AssertionError("represented-vector or selected subset identity failed")
                if row["proof_id"] not in proofs or encode(proofs[row["proof_id"]]) != encode(
                    ts53.subset_proof(u)
                ):
                    raise AssertionError("exact pair/collision/Hunter proof replay failed")
                if row["combined_correction"] != max(row["corrections"].values()) or row[
                    "vector_new_bound"
                ] != min(
                    row["vector_prior_bound"],
                    row["uncorrected_anchor_bound"] - row["combined_correction"],
                ):
                    raise AssertionError("corrections must use MAX and one subtraction, never SUM")
            if record["member_new_bound"] != max(r["vector_new_bound"] for r in rows):
                raise AssertionError("compressed member must MAX all represented-vector bounds")
    if encode(result) != encode(build_result()):
        raise AssertionError("stored result differs from complete exact certificate replay")
    return {
        "status": "PASS",
        "members": result["TARGET_MEMBER_COUNT"],
        "vectors": result["TARGET_VECTOR_COUNT"],
        "state_terms": len(result["FINAL_STATE_TERMS"]),
        "classified_terms": result["CLASSIFIED_TERM_COUNT"],
        "complete_r3": result["FINAL_COMPLETE_R3_UB"],
    }


def verify_stored_result() -> dict[str, Any]:
    stored = RESULT_PATH.read_bytes()
    status = verify_result(cast(dict[str, Any], json.loads(stored)))
    if stored != encode(build_result()).encode():
        raise AssertionError("stored result bytes differ from deterministic replay")
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
        "TARGET_MEMBER_COUNT",
        "TARGET_VECTOR_COUNT",
        "NEW_STATE_13169800_UB",
        "NEW_STATE_12695020_UB",
        "FINAL_COMPLETE_R3_UB",
        "FINAL_OWNER_IDS",
        "RUNNER_UP",
        "STRICT_GAIN",
        "REMAINING_GAP",
    )
    print(json.dumps({k: result[k] for k in keys}, sort_keys=True))


if __name__ == "__main__":
    main()
