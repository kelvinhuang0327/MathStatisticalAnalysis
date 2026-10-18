"""Adopt the sealed 153-member / 159-vector Four-State Classified Wall.

Recover the latest complete ledgers at BASE_HEAD; targets are every member
above the preserved Family maximum. Reuse TS53/TS106 exact integer primitives
for full-event or delete-one subsets, ranked deterministically. Smoothing
minimizes each cell collision sum. For every threshold graph, edge count is
at most C(rank+1, 2); descending Kruskal spans all nested graphs. A tree induces
at most k-1 edges on k present events, proving Hunter pointwise. Attach omitted
events using nonnegative intersections. These universal arguments apply to all
supports; carried legal witnesses check applicability only.

Adopt all previous certificates unchanged. Combine credits by MAX, subtract
once, and MAX all compressed aliases and all 56574 Family terms. No predecessor
certificate rebuild, new census, global subset search or solver is used.
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

from lottolab.research import b649_k20_r3_post_r14_ts_61_member_two_state_certificate_r1 as ts61

joint = ts61.joint

ts53, prior, h11 = joint.ts53, joint.prior, joint.h11
hunter, catalog, six, r24 = joint.hunter, joint.catalog, joint.six, joint.r24
LedgerMember = catalog.LedgerMember
type CountVector = tuple[int, ...]
dense, sparse, digest, member_id = joint.dense, joint.sparse, joint.digest, joint.member_id
TASK_ID = "B649_K20_R3_TS153_FOUR_STATE_WALL_ADOPTION_R2"
TASK_BRANCH = "codex/b649-k20-r3-ts153-four-state-wall-adoption-r2"
BASE_HEAD = "116f6a84d18b540931fb733c522ba5a72e6d7eb9"
BASE_TREE = "d4d190632737c86ea62335da0f5dde2d790d6590"
BASE_RESULT_SHA256 = "4fbcb5733c7a0a3035dbcc8eff30d8d93d6fd6d2124dc86734aff6f0fa174816"
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_RELATIVE = six.RESULTS + "b649-k20-r3-ts153-four-state-wall-adoption-r2-result.json"
RESULT_PATH = REPO_ROOT / RESULT_RELATIVE
STATE_12692531 = ts61.OWNER_STATE
STATE_12695020 = ts61.STATE_12695020
STATE_14122976 = prior.h0.s141.TARGET_STATE_ID
STATE_13169800 = ts61.STATE_13169800
# Immutable region fingerprint, members, vectors, targets, target vectors, compressed targets.
REGION_SPECS = {
    STATE_12692531: (
        "132cef5c91f5d6cf4798c8d8f65dba98d3851f33ec3d45b5d37fb7f61145ef15",
        582,
        633,
        24,
        25,
        1,
    ),
    STATE_12695020: (
        "46023fc93f2fd7d9b211d29494d05d8f6bfd4867992b0121cd8db0b7def5cd5b",
        1222,
        1325,
        75,
        80,
        5,
    ),
    STATE_14122976: (
        "785409687cbaca559e536cf63ff87fb0e5f972796025ef03743e13ba5a88555e",
        214,
        221,
        14,
        14,
        0,
    ),
    STATE_13169800: (
        "c183f8d2f93d3a695fcae3e2d2d280d40ffb1de3527eb43e61ce5321569dcde1",
        989,
        1072,
        40,
        40,
        0,
    ),
}
EXPECTED_STATE_BOUNDS = {
    STATE_12692531: 355073068,
    STATE_12695020: 355141066,
    STATE_14122976: 355055638,
    STATE_13169800: 355142998,
}
EXPECTED_TARGET_IDENTITY_DIGEST = "9da34a57b1437a7afc1e80bbb2d5660db59cd3a3d73ee6902105724d6e0d1815"
EXPECTED_MEMBER_NEW_BOUND_DIGEST = (
    "90ead161f289b98611c15da2e77e9c4a480213e1aa64512fafda79ff97d15bcc"
)
RESIDUAL_EVENT_DEFINITION = ts53.RESIDUAL_EVENT_DEFINITION
CORRECTION_COMBINATION = "MAX(EXISTING_VALID_CREDITS, SEALED_VECTOR, SUBSET_HUNTER); SUBTRACT_ONCE"


def source_paths() -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                *ts61.source_paths(),
                ts61.RESULT_RELATIVE,
                str(Path(ts61.__file__).resolve().relative_to(REPO_ROOT)),
            }
        )
    )


def git_bytes(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(REPO_ROOT), *args])


def verify_source_authority() -> dict[str, Any]:
    """Uncached immutable objects, lineage and every executing donor byte."""
    upstream = ts61.verify_source_authority()
    identity = git_bytes("show", "-s", "--format=%H %T", BASE_HEAD).decode().strip()
    blob = git_bytes("show", f"{BASE_HEAD}:{ts61.RESULT_RELATIVE}")
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
        "upstream_objects": upstream,
        "donor_sha256": fingerprints,
    }


@cache
def source_results() -> dict[str, dict[str, Any]]:
    """Adopt immutable certificates; no predecessor certificate is rebuilt."""
    verify_source_authority()
    results = {
        name: cast(dict[str, Any], json.loads(module.RESULT_PATH.read_bytes()))
        for name, module in (("TS61", ts61), ("JOINT", joint), ("H0", prior.h0))
    }
    current = results["TS61"]
    if (
        current["TASK_ID"] != ts61.TASK_ID
        or current["TASK_STATUS"] != "SUCCESS"
        or current["FINAL_COMPLETE_R3_UB"] != 355235139
        or current["FINAL_OWNER_IDS"] != [STATE_12692531]
    ):
        raise AssertionError("sealed TS61 predecessor identity failed")
    return results


def state_terms() -> tuple[tuple[str, int], ...]:
    return tuple(
        (str(r["stable_id"]), int(r["bound"]))
        for r in source_results()["TS61"]["FINAL_STATE_TERMS"]
    )


def classified_terms() -> tuple[tuple[str, int], ...]:
    return tuple(
        (str(r["stable_id"]), int(r["bound"]))
        for r in prior.source_results()["JOINT"]["FINAL_CLASSIFIED_TERMS"]
    )


def ledger_authority() -> dict[str, str]:
    """Latest complete ledgers at BASE_HEAD, with each State maximum checked."""
    return {
        STATE_12692531: joint.RESULT_RELATIVE,
        STATE_12695020: ts61.RESULT_RELATIVE,
        STATE_14122976: prior.h0.RESULT_RELATIVE,
        STATE_13169800: ts61.RESULT_RELATIVE,
    }


def region_rows(state_id: str) -> list[dict[str, Any]]:
    relative = ledger_authority().get(state_id)
    if relative is None:
        raise AssertionError("unknown target State")
    sources = {
        joint.RESULT_RELATIVE: "JOINT",
        ts61.RESULT_RELATIVE: "TS61",
        prior.h0.RESULT_RELATIVE: "H0",
    }
    regions = [
        r for r in source_results()[sources[relative]]["REGIONS"] if r["state_id"] == state_id
    ]
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
            or (
                state_id != STATE_12692531
                and row["compression_signature"] != catalog.normalized(signature)
            )
        ):
            raise AssertionError("sealed canonical/compression identity failed")
        for v in vs:
            state = catalog.rebuild_member(replace(m, counts=v, represented_vector_count=1))
            if (
                state.joint_s2 < int(state_id.split("-s3-")[0].split("s2-")[1])
                or state.joint_s3 > int(state_id.split("-s3-")[1])
                or len(v) != 30
                or sum(v) != 18
                or any(type(c) is not int or c < 0 for c in v)
                or hunter.eleven.compression_signature(state) != signature
                or hunter.r14.raw_bound(state) != m.raw_bound
            ):
                raise AssertionError("represented-vector compression signature failed")
    # H11 seals this region's signatures via its complete represented-vector digest.
    if (
        state_id == STATE_12692531
        and digest(tuple((m.counts, recovered[m.counts]) for m in members))
        != json.loads(h11.RESULT_PATH.read_bytes())["ALL_REPRESENTED_VECTORS_SHA256"]
    ):
        raise AssertionError("sealed whole-region compression identity failed")
    return recovered


@cache
def target_cutoff() -> int:
    """The largest Family term that this certificate cannot change."""
    others = [b for k, b in state_terms() if k not in REGION_SPECS]
    classified = classified_terms()
    if len(others) != 19 or len(classified) != 56550:
        raise AssertionError("complete untouched Family term coverage failed")
    return max(*others, max(b for _, b in classified), six.sealed_tail_bound())


def expected_aliases(state_id: str) -> tuple[tuple[CountVector, ...], ...]:
    """All compressed targets are recovered, then bound by the global identity digest."""
    vectors = represented_vectors(state_id)
    cutoff = target_cutoff()
    return tuple(
        sorted(
            vectors[m.counts]
            for m in region_members(state_id)
            if m.final_bound > cutoff and len(vectors[m.counts]) > 1
        )
    )


def target_members(state_id: str) -> tuple[LedgerMember, ...]:
    """Recover targets from the complete ledger, with no handwritten ID filter."""
    members, vectors = region_members(state_id), represented_vectors(state_id)
    cutoff = target_cutoff()
    targets = tuple(m for m in members if m.final_bound > cutoff)
    _, _, _, tc, tv, compressed = REGION_SPECS[state_id]
    aliases = tuple(vectors[m.counts] for m in targets if len(vectors[m.counts]) > 1)
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
    if (
        vectors != represented_vectors(state_id)[member.counts]
        or len(rows) != member.represented_vector_count
        or bound >= member.final_bound
    ):
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
                {
                    **row,
                    "prior_bound": m.final_bound,
                    "final_bound": bounds[m.counts],
                    "compression_signature": catalog.normalized(
                        hunter.eleven.compression_signature(catalog.rebuild_member(m))
                    ),
                }
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
    source = source_results()["TS61"]
    states, classified = state_terms(), classified_terms()
    tail = six.sealed_tail_bound()
    start = six.tail.family_maximum(tail, states, classified)
    replacements = {str(r["state_id"]): int(r["new_state_bound"]) for r in regions}
    if (
        len(states) != 23
        or len(dict(states)) != 23
        or not set(REGION_SPECS) <= dict(states).keys()
        or set(replacements) != set(REGION_SPECS)
        or len(regions) != 4
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


def target_identity_digest() -> str:
    return digest(
        tuple(
            sorted(
                (sid, m.counts, tuple(sorted(represented_vectors(sid)[m.counts])))
                for sid in REGION_SPECS
                for m in target_members(sid)
            )
        )
    )


def build_result() -> dict[str, Any]:
    authority = verify_source_authority()
    regions = [region_certificate(sid) for sid in REGION_SPECS]
    family = recompute_family(regions)
    rows = [v for r in regions for m in r["member_certificates"] for v in m["vector_certificates"]]
    subsets = {dense(v["selected_subset_counts"]) for v in rows}
    proofs = [ts53.subset_proof(u) for u in sorted(subsets)]
    # Count the complete target catalog, including deleted events and attachments.
    # Each subset takes its own applicable floors from the exact rows it occupies.
    pairs = tuple(
        sorted({p for row in rows for p in six.occupied_type_pairs(dense(row["counts"]))})
    )
    pair_rows = tuple(row for pair in pairs for row in prior.verified_pair_rows(pair))
    selected_rows = {tuple(row) for proof in proofs for row in proof["pair_rows"]}
    if not selected_rows <= set(pair_rows) or len(set(pair_rows)) != len(pair_rows):
        raise AssertionError("selected pair rows must belong to the full target catalog")
    groups = {
        (tuple(p["pair_floors"]), p["collision_mass_floor"], p["event_count"]): p for p in proofs
    }
    cases = sum(p["all_admissible_threshold_cases"] for p in groups.values())
    identity = target_identity_digest()
    member_digest = digest(
        tuple(
            sorted(
                (r["state_id"], dense(m["witness_counts"]), m["member_new_bound"])
                for r in regions
                for m in r["member_certificates"]
            )
        )
    )
    coverage = (
        sum(r["region_member_count"] for r in regions),
        sum(r["region_vector_count"] for r in regions),
    )
    target_coverage = (
        sum(r["target_member_count"] for r in regions),
        sum(r["target_vector_count"] for r in regions),
    )
    remainder = (
        sum(r["preserved_member_count"] for r in regions),
        sum(r["preserved_vector_count"] for r in regions),
    )
    compressed = sum(r["compressed_target_count"] for r in regions)
    full = sum(sum(dense(v["selected_subset_counts"])) == 18 for v in rows)
    states = dict(family["states"])
    if (
        coverage != (3007, 3251)
        or target_coverage != (153, 159)
        or remainder != (2854, 3092)
        or compressed != 6
        or identity != EXPECTED_TARGET_IDENTITY_DIGEST
        or member_digest != EXPECTED_MEMBER_NEW_BOUND_DIGEST
        or full != 70
        or len(rows) - full != 89
        or len(subsets) != 140
        or len(groups) != 40
        or len(pairs) != 56
        or len(pair_rows) != 330
        or cases != 19933125
        or {k: states[k] for k in REGION_SPECS} != EXPECTED_STATE_BOUNDS
        or family["classified_sha256"]
        != "8974cda817f7f03f24bb6bd03ed6c59f1bb95ede70aa1a678fc05d99adf533d3"
        or family["classified_max"] != 355145504
        or family["tail"] != 354039277
        or family["start"]["R3_BOUND"] != 355235139
        or family["final"]["R3_BOUND"] != 355145504
        or family["final"]["OWNER_IDS"] != ["carried-r12-other-levels"]
        or family["runner_up"] != {"bound": 355142998, "owner_ids": [STATE_13169800]}
        or r24.INCUMBENT != 313263888
    ):
        raise AssertionError("four-State coverage/digest/Hunter/complete Family acceptance failed")
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
            "TARGET_SELECTION": "member.final_bound > max(preserved Family terms)",
            "TARGET_CUTOFF": target_cutoff(),
            "REGION_MEMBER_COUNT": coverage[0],
            "REGION_VECTOR_COUNT": coverage[1],
            "TARGET_MEMBER_COUNT": target_coverage[0],
            "TARGET_VECTOR_COUNT": target_coverage[1],
            "COMPRESSED_TARGET_COUNT": compressed,
            "TARGET_IDENTITY_DIGEST": identity,
            "NEW_MEMBER_BOUND_DIGEST": member_digest,
            "PRESERVED_MEMBER_COUNT": remainder[0],
            "PRESERVED_VECTOR_COUNT": remainder[1],
            "SUBSET_SELECTION_RULE": "min((-rank_minimum, event_count, dense_count_tuple))",
            "FULL_18_SELECTION_COUNT": full,
            "DELETE_ONE_SELECTION_COUNT": len(rows) - full,
            "DISTINCT_SUBSET_COUNT": len(subsets),
            "THRESHOLD_GROUP_COUNT": len(groups),
            "ADMISSIBLE_THRESHOLD_CASES": cases,
            "TYPE_PAIR_COUNT": len(pairs),
            "LEGAL_PAIR_ROW_COUNT": len(pair_rows),
            "FULL_TARGET_TYPE_PAIRS": pairs,
            "FULL_TARGET_PAIR_ROWS": pair_rows,
            "SUBSET_PROOFS": proofs,
            "REGIONS": regions,
            "SUBSET_VALIDITY_STATUS": "PASS_INTEGER_COMPONENTWISE_17_OR_18",
            "PAIR_FLOOR_STATUS": "PASS_COMPLETE_LEGAL_ROWS_EXACT_TYPE_APPLICABLE_FLOORS",
            "COLLISION_FLOOR_STATUS": "PASS_FOUR_CELL_BALANCED_INTEGER_MINIMA_BY_SMOOTHING",
            "HUNTER_MINIMUM_STATUS": "PASS_ALL_40_NESTED_THRESHOLD_PROBLEMS",
            "UNIVERSAL_HUNTER_STATUS": "PASS_GRAPH_RANK_KRUSKAL_POINTWISE_TREE_INEQUALITY",
            "TREE_EXTENSION_STATUS": "PASS_18_EVENT_SPANNING_TREE_NONNEGATIVE_ATTACHMENTS",
            "PREDECESSOR_PRESERVATION": "PASS_ALL_SEALED_INPUT_BYTES_AND_VALID_VECTOR_CREDITS",
            "CORRECTION_COMBINATION": CORRECTION_COMBINATION,
            "NO_DOUBLE_COUNT_STATUS": "PASS_MAX_SUBTRACT_ONCE_MEMBER_MAX",
            "UNTOUCHED_REMAINDER_STATUS": "PASS_ALL_2854_MEMBERS_3092_VECTORS",
            "NEW_FOUR_STATE_BOUNDS": {k: states[k] for k in REGION_SPECS},
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
            "FAMILY_TERM_COUNT": len(family["states"]) + family["classified_count"] + 1,
            "CLASSIFIED_TERM_COUNT": family["classified_count"],
            "CLASSIFIED_TERMS_SHA256": family["classified_sha256"],
            "CLASSIFIED_MAX": family["classified_max"],
            "TAIL_BOUND": family["tail"],
            "CLASSIFIED_PRESERVATION": "PASS_ALL_56550_TERMS_UNCHANGED",
            "TAIL_PRESERVATION": "PASS_SEALED_FORMULA_UNCHANGED",
            "WITNESS_SOUNDNESS_STATUS": "PASS_ALL_159_LEGAL_SUPPORTS_AND_CARRIED_WITNESSES",
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
        raise AssertionError("exact four-State coverage failed")
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
        "NEW_FOUR_STATE_BOUNDS",
        "FINAL_COMPLETE_R3_UB",
        "FINAL_OWNER_IDS",
        "RUNNER_UP",
        "STRICT_GAIN",
        "REMAINING_GAP",
    )
    print(json.dumps({k: result[k] for k in keys}, sort_keys=True))


if __name__ == "__main__":
    main()
