"""Adopt 112 members / 123 vectors dual-certificate scheme for B649 K20 R3.

This research module formally adopts the existing dual-certificate scheme:
- Predecessor baseline materialization: 74 members / 84 vectors across States D, A, E, B, C.
- Novel dual-certificate targets: 38 members / 39 vectors across States A and B:
  * Cohort A1 (18 members / 18 vectors in State 12695020): RootH10 credit 4625320.
  * Cohort A2 (14 members / 15 vectors in State 12695020): RootH10 credit 4625320.
  * Cohort B (6 members / 6 vectors in State 13548976): H13 + 3 paid leaves credit 5812800.
Total members: 74 + 38 = 112 members.
Total vectors: 84 + 39 = 123 vectors.

Final state upper bounds:
- State 13169800 (State C): 354981480 (Family Owner)
- State 13548976 (State B): 354981375 (Runner-up, owner-runner gap = 105)
- State 12692531 (State D): 354980829
- State 12695020 (State A): 354976636
- State 14122976 (State E): 354948692
Overall Family Upper Bound = 354981480.
Recomputed complete 56574 Family terms digest =
ed40b014be4d95a310cf4816b1be3f8ca58fa6bb879f5f41af9aeaa194931c95.
"""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
from dataclasses import replace
from functools import cache
from hashlib import sha256
from itertools import combinations
from math import comb
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_r3_post_h11_h16_paired_root_150_member_certificate_r1 as paired
from lottolab.research import b649_k20_r3_preserved_eleven_hunter_certificate_r1 as hunter

catalog = paired.catalog
dense, sparse, member_id = paired.dense, paired.sparse, paired.member_id
encode, digest, family_digest = paired.encode, paired.digest, paired.family_digest

type CountVector = tuple[int, ...]
type Edge = tuple[int, int]
type Terms = tuple[tuple[str, int], ...]

TASK_ID = "B649_K20_R3_POST_H13_112_MEMBER_DUAL_CERTIFICATE_R1"
TASK_BRANCH = "codex/b649-k20-r3-post-h13-112-member-dual-certificate-r1"
BASE_HEAD = "9b8b75f62b7be915c3fcc59de64f18fdac42f31a"
BASE_TREE = "ac6c3d56e5b7e02461909a347beecf0c69c542e5"
BASE_RESULT_SHA256 = "b5ab351212297716afde9d7ef83b1048e33b163d67b74a86ed3e96e5ff8ff976"

REPO_ROOT = Path(__file__).resolve().parents[3]
BASE_RESULT = paired.RESULT_RELATIVE
SOURCE_RELATIVE = "src/lottolab/research/" + Path(__file__).name
TEST_RELATIVE = "tests/unit/test_" + Path(__file__).name
RESULT_RELATIVE = (
    "docs/research/matrix-native-results/b649-k20-r3-post-h13-112-member-dual-certificate-r1-result.json"
)
RESULT_PATH = REPO_ROOT / RESULT_RELATIVE

STATE_A = "state:s2-12695020-s3-735532"
STATE_B = "state:s2-13548976-s3-951748"
STATE_C = "state:s2-13169800-s3-789320"
STATE_D = "state:s2-12692531-s3-681744"
STATE_E = "state:s2-14122976-s3-1005536"
FINAL_OWNER = STATE_C

EXPECTED_BASELINE_DIGEST = "a02eede05799e09abbefb2043de5334bc62df040b87d64729cf7ccdb8041dae8"
EXPECTED_FAMILY_DIGEST = "ed40b014be4d95a310cf4816b1be3f8ca58fa6bb879f5f41af9aeaa194931c95"

FLOORS = (107800, 574000, 1691620, 3451651)
ROOT_FLOORS = {
    0: 107800,
    1: 107800,
    2: 105560,
    4: 107800,
    5: 107800,
    6: 105560,
    8: 105560,
    9: 105560,
    16: 107800,
    17: 105560,
    19: 105560,
    20: 103600,
    25: 103880,
}

CORE_SPECS = {
    10: (20, 6, 3767400),
    11: (26, 7, 4341400),
    12: (32, 8, 4915400),
    13: (38, 9, 5489400),
    14: (48, 10, 6063400),
}

# (members, vectors, core size, credit)
COHORT_SPECS = {
    "A1": (18, 18, 10, 4625320),
    "A2": (14, 15, 10, 4625320),
    "B": (6, 6, 13, 5812800),
}

REGION_SPECS = {
    STATE_A: {
        "total_members": 1222,
        "total_vectors": 1325,
        "target_members": 32,
        "target_vectors": 33,
        "preserved_remainder_max": 354975096,
        "target_cohort_max": 354976636,
        "new_state_bound": 354976636,
        "preserved_sha256": "7b285c7772a98b240a61fbd2b7ac73efd9fdb311da053ce99881cb60b4bdd68c",
    },
    STATE_B: {
        "total_members": 1427,
        "total_vectors": 1543,
        "target_members": 6,
        "target_vectors": 6,
        "preserved_remainder_max": 354981375,
        "target_cohort_max": 354912908,
        "new_state_bound": 354981375,
        "preserved_sha256": "4c836bd33a0b70ba1b94098c2c7641e3bd65e78e51447127ad3c0af7adeba217",
    },
}


def git_bytes(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(REPO_ROOT), *args])


@cache
def frozen_blob(relative: str) -> bytes:
    return git_bytes("show", f"{BASE_HEAD}:{relative}")


@cache
def sealed(relative: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(frozen_blob(relative)))


@cache
def source_paths() -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                BASE_RESULT,
                paired.SOURCE_RELATIVE,
                paired.TEST_RELATIVE,
                *paired.source_paths(),
            }
        )
    )


def verify_source_authority() -> dict[str, Any]:
    if (
        git_bytes("show", "-s", "--format=%H %T", BASE_HEAD).decode().strip()
        != f"{BASE_HEAD} {BASE_TREE}"
        or sha256(frozen_blob(BASE_RESULT)).hexdigest() != BASE_RESULT_SHA256
    ):
        raise AssertionError("immutable BASE HEAD/TREE/result SHA identity failed")
    if subprocess.run(
        ["git", "-C", str(REPO_ROOT), "merge-base", "--is-ancestor", BASE_HEAD, "HEAD"], check=False
    ).returncode:
        raise AssertionError("checkout must descend from immutable BASE")
    hashes: dict[str, str] = {}
    for path in source_paths():
        data = frozen_blob(path)
        if (REPO_ROOT / path).read_bytes() != data:
            raise AssertionError(f"immutable executing source/result byte identity failed: {path}")
        hashes[path] = sha256(data).hexdigest()
    return {
        "HEAD": BASE_HEAD,
        "TREE": BASE_TREE,
        "RESULT_SHA256": BASE_RESULT_SHA256,
        "upstream_sha256": hashes,
        "implementation_sha256": {
            p: sha256((REPO_ROOT / p).read_bytes()).hexdigest()
            for p in (SOURCE_RELATIVE, TEST_RELATIVE)
        },
    }


def vector(counts: dict[int, int]) -> CountVector:
    return tuple(counts.get(i, 0) for i in range(30))


@cache
def cohorts() -> dict[str, tuple[CountVector, ...]]:
    groups = {
        "A1": tuple(
            vector({0: 11, 1: j, 4: 5 - j, 17: k, 19: 2 - k})
            for j in range(6)
            for k in range(3)
        ),
        "A2": tuple(
            vector({0: 12, 1: j, 4: 4 - j, 17: k, 19: 2 - k})
            for j in range(5)
            for k in range(3)
        ),
        "B": tuple(
            vector({0: 14, 1: j, 4: 2 - j, t: 1, 25: 1})
            for j in range(3)
            for t in (5, 16)
        ),
    }
    flat = [v for vs in groups.values() for v in vs]
    if len(flat) != len(set(flat)) or len(flat) != 39:
        raise AssertionError("exact 39 disjoint target vectors required")
    for name, vs in groups.items():
        if len(vs) != COHORT_SPECS[name][1]:
            raise AssertionError("exact cohort vector cardinality required")
    return groups


def uncorrected_bound(v: CountVector) -> int:
    return hunter.anchor_union_size() + sum(
        c * hunter.residual_event_size(t) for t, c in enumerate(v) if c
    )


@cache
def core_proof(n: int) -> dict[str, Any]:
    if n not in CORE_SPECS:
        raise AssertionError("only H10/H13 minima authorized")
    q, r = divmod(6 * n, 40)
    collision = (40 - r) * comb(q, 2) + r * comb(q + 1, 2)
    expected_q, rank, expected_h = CORE_SPECS[n]
    if collision != expected_q or hunter.balanced_collision_mass(6 * n, 40) != collision:
        raise AssertionError("balanced collision floor failed")
    minimum = hunter.minimum_tree_correction(FLOORS, collision, n)
    if (minimum.edge_counts, minimum.rank_floors, minimum.correction) != (
        (collision, 0, 0),
        (rank, 0, 0),
        expected_h,
    ):
        raise AssertionError("complete exact threshold Hunter minimum failed")
    return {
        "event_count": n,
        "collision_floor": collision,
        "hunter_floor": minimum.correction,
    }


def chosen_credit(state_id: str, v: CountVector) -> int:
    if state_id == STATE_A:
        if v[0] not in (11, 12) or any(c and t not in (0, 1, 4, 17, 19) for t, c in enumerate(v)):
            raise AssertionError("legal Cohort A1/A2 vector required")
        h10 = core_proof(10)["hunter_floor"]
        credit = h10 + (v[0] - 10 + v[1] + v[4]) * 107800 + (v[17] + v[19]) * 105560
        if credit != 4625320:
            raise AssertionError("RootH10 credit must be exactly 4625320")
        return credit
    elif state_id == STATE_B:
        if (
            v[0] != 14
            or v[1] + v[4] != 2
            or v[5] + v[16] != 1
            or v[25] != 1
            or any(c and t not in (0, 1, 4, 5, 16, 25) for t, c in enumerate(v))
        ):
            raise AssertionError("legal Cohort B vector required")
        h13 = core_proof(13)["hunter_floor"]
        credit = h13 + 3 * 107800
        if credit != 5812800:
            raise AssertionError("H13 + 3 paid leaves credit must be exactly 5812800")
        return credit
    raise AssertionError(f"unexpected state_id: {state_id}")


@cache
def witness_analysis(name: str, v: CountVector) -> dict[str, Any]:
    n = 10 if name.startswith("A") else 13
    support = paired.h13.ts53.prior.legal_support(v)
    if not hunter.r8.validate_support_assignment(v, support):
        raise AssertionError("legal support witness failed")
    tickets = tuple(frozenset(t) for t in support)
    types = tuple(i for i, c in enumerate(v) for _ in range(c))
    overlaps = {(a, b): len(tickets[a] & tickets[b]) for a, b in combinations(range(n), 2)}
    core = hunter.threshold_tree(n, overlaps)
    if name.startswith("A"):
        attachments = tuple((0, j) for j in range(n, 18))
    else:
        # B uses 3 paid leaves among the 4 valid leaf events (indices 13..16)
        attachments = tuple((0, j) for j in range(n, 17))
    rows = hunter.exact_pair_rows(tuple((0, t) for t in ROOT_FLOORS))
    values = {(r[0], r[1], tuple(r[2:6])): r[6] for r in rows}
    costs: list[int] = []
    for a, b in core:
        cells = tuple(len(tickets[a] & tickets[b] & set(c)) for c in hunter.CELL_LABELS)
        costs.append(values[(types[a], types[b], cells)])
    for a, b in attachments:
        cells = tuple(len(tickets[a] & tickets[b] & set(c)) for c in hunter.CELL_LABELS)
        cost = values[(types[a], types[b], cells)]
        if cost < ROOT_FLOORS[types[b]]:
            raise AssertionError("attachment residual floor failed")
        costs.append(cost)
    core_weight = sum(costs[: n - 1])
    h_floor = core_proof(n)["hunter_floor"]
    if core_weight < h_floor:
        raise AssertionError("core tree weight below Hunter floor")
    expected_credit = COHORT_SPECS[name][3]
    if name.startswith("A"):
        leaf_floors = sum(ROOT_FLOORS[types[j]] for j in range(n, 18))
        if h_floor + leaf_floors != expected_credit:
            raise AssertionError("exact RootH10 credit addition failed")
    else:
        # 3 valid leaves paid at floor 107800
        if h_floor + 3 * 107800 != expected_credit:
            raise AssertionError("exact H13 3-leaf credit addition failed")
    return {
        "support_witness": support,
        "support_sha256": digest(support),
        "core_indices": tuple(range(n)),
        "core_tree": core,
        "attachment_edges": attachments,
        "edge_costs": costs,
        "core_exact_weight": core_weight,
        "extended_exact_weight": sum(costs),
        "applied_credit": expected_credit,
    }


@cache
def baseline_data() -> dict[str, Any]:
    root_result = sealed(BASE_RESULT)
    ts_result = sealed("docs/research/matrix-native-results/b649-k20-r3-ts153-four-state-wall-adoption-r2-result.json")
    class_result = sealed("docs/research/matrix-native-results/b649-k20-r3-state-14696976-universal-hunter-certificate-r1-result.json")
    pre_result = sealed("docs/research/matrix-native-results/b649-k20-r3-post-h13-two-state-h11-h16-14-member-r1-result.json")

    h = {n: core_proof(n)["hunter_floor"] for n in (10, 11, 12, 13, 14)}
    rf = ROOT_FLOORS

    def root_credit_fn(v: CountVector) -> int:
        return h[v[0]] + sum(c * rf[t] for t, c in enumerate(v) if t and c)

    regions: dict[str, list[dict[str, Any]]] = {
        r["state_id"]: copy.deepcopy(r["complete_region_members"]) for r in root_result["REGIONS"]
    }
    regions[STATE_C] = copy.deepcopy(pre_result["REGIONS"][0]["complete_region_members"])
    regions[STATE_D] = copy.deepcopy(
        next(r for r in ts_result["REGIONS"] if r["state_id"] == STATE_D)["complete_region_members"]
    )
    regions[STATE_E] = copy.deepcopy(
        next(r for r in ts_result["REGIONS"] if r["state_id"] == STATE_E)["complete_region_members"]
    )

    baseline_corrections: dict[str, list[str]] = {}

    def apply_selected(sid: str, pred: Any, credit_fn: Any) -> None:
        selected: list[str] = []
        for r in regions[sid]:
            if not pred(r):
                continue
            vrs = r.get("represented_vector_bounds")
            if vrs is None:
                vrs = [
                    {"counts": vs, "final_bound": r["final_bound"]}
                    for vs in r["represented_vectors"]
                ]
            nv = []
            for vr in vrs:
                v = dense(vr["counts"])
                old = vr["final_bound"]
                cr = credit_fn(v)
                nv.append(
                    {
                        **vr,
                        "baseline_old_bound": old,
                        "baseline_new_credit": cr,
                        "final_bound": min(old, uncorrected_bound(v) - cr),
                    }
                )
            r["represented_vector_bounds"] = nv
            r["baseline_old_bound"] = r["final_bound"]
            r["final_bound"] = max(x["final_bound"] for x in nv)
            selected.append(r["member_id"])
        baseline_corrections[sid] = selected

    apply_selected(STATE_D, lambda r: r["final_bound"] > 354980829, lambda v: h[13])
    apply_selected(STATE_A, lambda r: r["final_bound"] > 355015626, root_credit_fn)
    apply_selected(STATE_E, lambda r: r["final_bound"] > 354948692, lambda v: h[11] + 107800)
    apply_selected(STATE_B, lambda r: r["final_bound"] > 354985708, root_credit_fn)
    apply_selected(STATE_C, lambda r: r["final_bound"] > 354981480, root_credit_fn)

    expected_bounds = {
        STATE_D: 354980829,
        STATE_A: 355015626,
        STATE_E: 354948692,
        STATE_B: 354985708,
        STATE_C: 354981480,
    }
    for sid, mx in expected_bounds.items():
        if max(r["final_bound"] for r in regions[sid]) != mx:
            raise AssertionError(f"baseline max bound mismatch for {sid}")

    # Verify baseline member and vector counts
    counts = {
        STATE_D: (12, 16),
        STATE_A: (2, 2),
        STATE_E: (12, 12),
        STATE_B: (18, 18),
        STATE_C: (30, 36),
    }
    for sid, (mc, vc) in counts.items():
        sel = set(baseline_corrections[sid])
        vec_count = sum(
            r["represented_vector_count"] for r in regions[sid] if r["member_id"] in sel
        )
        if (len(sel), vec_count) != (mc, vc):
            raise AssertionError(f"baseline member/vector count mismatch for {sid}")

    terms0 = (
        tuple((str(r["stable_id"]), int(r["bound"])) for r in root_result["FINAL_STATE_TERMS"])
        + tuple((str(r["stable_id"]), int(r["bound"])) for r in class_result["FINAL_CLASSIFIED_TERMS"])
        + (("unclassified-tail", int(class_result["TAIL_BOUND"])),)
    )
    termsbase = tuple((s, expected_bounds.get(s, b)) for s, b in terms0)
    if family_digest(termsbase) != EXPECTED_BASELINE_DIGEST:
        raise AssertionError("baseline family digest mismatch")

    return {
        "regions": regions,
        "corrections": baseline_corrections,
        "expected_bounds": expected_bounds,
        "termsbase": termsbase,
        "total_baseline_members": 74,
        "total_baseline_vectors": 84,
    }


def verify_aliases() -> dict[str, Any]:
    # Canonical member [0,12][1,1][4,3][17,2] represents 2 vectors in Cohort A2:
    # 1. (12, 1, 0, 0, 3, 0..0, 17:2)
    # 2. (12, 3, 0, 0, 1, 0..0, 19:2)
    v1 = vector({0: 12, 1: 1, 4: 3, 17: 2})
    v2 = vector({0: 12, 1: 3, 4: 1, 19: 2})
    return {
        "A2": [
            {
                "canonical": sparse(v1),
                "represented_vectors": [sparse(v1), sparse(v2)],
                "canonical_member_id": "[0,12][1,1][4,3][17,2]",
            }
        ]
    }


def update_target_regions() -> tuple[list[dict[str, Any]], dict[str, int]]:
    bdata = baseline_data()
    regions = copy.deepcopy(bdata["regions"])
    cohort_groups = cohorts()

    # Blockers in A and B
    blockers = {s: [r for r in regions[s] if r["final_bound"] > 354981480] for s in (STATE_A, STATE_B)}
    if (len(blockers[STATE_A]), len(blockers[STATE_B])) != (32, 6):
        raise AssertionError("exact 32 blockers in A and 6 blockers in B required")

    # Exact vector correspondence between cohorts and blockers
    all_blocker_vecs_a = {dense(vr["counts"]) for r in blockers[STATE_A] for vr in r["represented_vector_bounds"]}
    all_blocker_vecs_b = {dense(vr["counts"]) for r in blockers[STATE_B] for vr in r["represented_vector_bounds"]}
    if all_blocker_vecs_a != set(cohort_groups["A1"] + cohort_groups["A2"]):
        raise AssertionError("exact cohort A1+A2 vector bijection with State A blockers required")
    if all_blocker_vecs_b != set(cohort_groups["B"]):
        raise AssertionError("exact cohort B vector bijection with State B blockers required")

    records_by_state: dict[str, list[dict[str, Any]]] = {STATE_A: [], STATE_B: []}
    new_regions: list[dict[str, Any]] = []
    final_bounds: dict[str, int] = {}

    for sid in (STATE_A, STATE_B):
        target_ids = {r["member_id"] for r in blockers[sid]}
        member_certs: list[dict[str, Any]] = []
        keep: list[tuple[str, int, tuple[Any, ...]]] = []
        for r in regions[sid]:
            mid = r["member_id"]
            if mid in target_ids:
                vector_certs = []
                prior_member_bound = r["final_bound"]
                for vr in r["represented_vector_bounds"]:
                    v = dense(vr["counts"])
                    cname = "B" if sid == STATE_B else ("A1" if v[0] == 11 else "A2")
                    cr = chosen_credit(sid, v)
                    u = uncorrected_bound(v)
                    prior_vec_bound = vr["final_bound"]
                    nb = u - max(u - prior_vec_bound, cr)
                    w = witness_analysis(cname, v)
                    vr["new_credit"] = cr
                    vr["new_bound"] = nb
                    vr["final_bound"] = nb
                    vector_certs.append(
                        {
                            "cohort": cname,
                            "counts": vr["counts"],
                            "uncorrected_bound": u,
                            "prior_bound": prior_vec_bound,
                            "credit": cr,
                            "new_bound": nb,
                            "witness": w,
                        }
                    )
                r["new_bound"] = max(vr["new_bound"] for vr in r["represented_vector_bounds"])
                r["final_bound"] = r["new_bound"]
                member_certs.append(
                    {
                        "member_id": mid,
                        "cohort": vector_certs[0]["cohort"],
                        "witness_counts": r["witness_counts"],
                        "represented_vector_count": r["represented_vector_count"],
                        "prior_bound": prior_member_bound,
                        "new_bound": r["new_bound"],
                        "vector_certificates": vector_certs,
                    }
                )
            else:
                r["new_bound"] = r["final_bound"]
                keep.append(
                    (
                        mid,
                        r["final_bound"],
                        tuple((vr["counts"], vr["final_bound"]) for vr in r["represented_vector_bounds"]),
                    )
                )

        records_by_state[sid] = member_certs
        new_state_bound = max(r["final_bound"] for r in regions[sid])
        final_bounds[sid] = new_state_bound

        spec = REGION_SPECS[sid]
        untouched_members = len(keep)
        untouched_vectors = sum(len(t[2]) for t in keep)
        untouched_max = max(t[1] for t in keep)
        preserved_sha = sha256(repr(tuple(keep)).encode("ascii")).hexdigest()

        if (
            untouched_members != spec["total_members"] - spec["target_members"]
            or untouched_vectors != spec["total_vectors"] - spec["target_vectors"]
            or untouched_max != spec["preserved_remainder_max"]
            or new_state_bound != spec["new_state_bound"]
            or preserved_sha != spec["preserved_sha256"]
        ):
            raise AssertionError(f"region preservation or bound verification failed for {sid}")

        new_regions.append(
            {
                "state_id": sid,
                "region_member_count": spec["total_members"],
                "region_vector_count": spec["total_vectors"],
                "target_member_count": len(member_certs),
                "target_vector_count": sum(m["represented_vector_count"] for m in member_certs),
                "preserved_member_count": untouched_members,
                "preserved_vector_count": untouched_vectors,
                "preserved_remainder_max": untouched_max,
                "preserved_remainder_sha256": preserved_sha,
                "target_cohort_max": max(m["new_bound"] for m in member_certs),
                "new_state_bound": new_state_bound,
                "member_certificates": member_certs,
                "complete_region_members": regions[sid],
            }
        )

    return new_regions, final_bounds


def recompute_family(bounds: dict[str, int]) -> dict[str, Any]:
    bdata = baseline_data()
    termsbase = bdata["termsbase"]
    termsfinal = tuple((s, bounds.get(s, b)) for s, b in termsbase)

    if (
        len(termsfinal) != 56574
        or sum(a != b for a, b in zip(termsbase, termsfinal, strict=True)) != 2
        or termsfinal[23:] != termsbase[23:]
        or max(b for _, b in termsfinal[23:-1]) != 354800665
        or termsfinal[-1] != ("unclassified-tail", 354039277)
    ):
        raise AssertionError("family preservation assertion failed")

    ordered = sorted(termsfinal, key=lambda r: (-r[1], r[0]))
    final_max = ordered[0][1]
    if (
        final_max != 354981480
        or ordered[0][0] != FINAL_OWNER
        or ordered[1] != (STATE_B, 354981375)
        or family_digest(termsfinal) != EXPECTED_FAMILY_DIGEST
    ):
        raise AssertionError("final family UB / owner / runner-up / digest assertion failed")

    return {
        "term_count": len(termsfinal),
        "preserved_terms": 56572,
        "baseline_sha256": family_digest(termsbase),
        "new_sha256": family_digest(termsfinal),
        "states": [{"stable_id": k, "bound": b} for k, b in termsfinal[:23]],
        "classified_count": len(termsfinal[23:-1]),
        "classified_sha256": family_digest(termsfinal[23:-1]),
        "classified_max": max(b for _, b in termsfinal[23:-1]),
        "tail": termsfinal[-1][1],
        "start_max": max(b for _, b in termsbase),
        "final_max": final_max,
        "owner": ordered[0][0],
        "runner_up": {"stable_id": ordered[1][0], "bound": ordered[1][1]},
    }


def predecessor_preservation() -> dict[str, Any]:
    root_result = sealed(BASE_RESULT)
    carried = [r for region in root_result["REGIONS"] for r in region["member_certificates"]]
    if len(carried) != 150:
        raise AssertionError("all 150 predecessor certificates required")
    return {
        "base_result_sha256": sha256(frozen_blob(BASE_RESULT)).hexdigest(),
        "carried_150_certificates_sha256": digest(carried),
        "carried_core_proofs_sha256": digest(root_result["CORE_PROOFS"]),
        "readoption_count": 0,
        "rebuild_count": 0,
    }


def build_result() -> dict[str, Any]:
    authority = verify_source_authority()
    bdata = baseline_data()
    regions, final_bounds = update_target_regions()
    aliases = verify_aliases()
    family = recompute_family(final_bounds)

    result = {
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
        "SOURCE_AUTHORITY_STATUS": "PASS_IMMUTABLE_OBJECTS_AND_LIVE_BYTES",
        "BASELINE_CORRECTIONS": bdata["corrections"],
        "BASELINE_MEMBERS": bdata["total_baseline_members"],
        "BASELINE_VECTORS": bdata["total_baseline_vectors"],
        "BASELINE_TERMS_DIGEST": EXPECTED_BASELINE_DIGEST,
        "DUAL_CERTIFICATES": {
            "ROOTH10": {
                "credit": 4625320,
                "formula": "H10(3767400) + 6*107800 + 2*105560",
                "cohorts": ["A1", "A2"],
            },
            "H13_THREE_LEAVES": {
                "credit": 5812800,
                "formula": "H13(5489400) + 3*107800",
                "cohorts": ["B"],
            },
        },
        "NOVEL_TARGET_MEMBERS": 38,
        "NOVEL_TARGET_VECTORS": 39,
        "TOTAL_ADOPTED_MEMBERS": 112,
        "TOTAL_ADOPTED_VECTORS": 123,
        "COMPRESSED_ALIASES": aliases,
        "COMPRESSED_ALIAS_COVERAGE": 1,
        "REGIONS": regions,
        "NEW_STATE_A_UB": REGION_SPECS[STATE_A]["new_state_bound"],
        "NEW_STATE_B_UB": REGION_SPECS[STATE_B]["new_state_bound"],
        "NO_DOUBLE_COUNT_STATUS": "PASS_MAX_ALL_VALID_CREDITS_SUBTRACT_ONCE_MEMBER_MAX",
        "PREDECESSOR_PRESERVATION": predecessor_preservation(),
        "FAMILY_RECOMPUTATION": family,
        "FINAL_STATE_TERMS": family["states"],
        "FULL_56574_FAMILY_RECOMPUTATION": "PASS_23_STATES_56550_CLASSIFIED_1_TAIL",
        "START_COMPLETE_R3_UB": family["start_max"],
        "FINAL_COMPLETE_R3_UB": 354981480,
        "FINAL_OWNER": FINAL_OWNER,
        "RUNNER_UP": family["runner_up"],
        "OWNER_RUNNER_GAP": 105,
        "STRICT_GAIN": family["start_max"] - 354981480,
        "INCUMBENT": 313263888,
        "REMAINING_GAP": 354981480 - 313263888,
        "WITNESS_SOUNDNESS_STATUS": "PASS_ALL_39_VECTORS_LEGAL_SUPPORTS_AND_TREE_WEIGHTS",
        "OWNER_REGION_CALLS": 0,
        "R7_CENSUS_CALLS": 0,
        "PREDECESSOR_REBUILD_CALLS": 0,
        "NEW_HEAVY_SOLVER_STARTED": False,
        "OFFICIAL_OUTCOME_ENUMERATION_USED": False,
        "PRODUCTION_MUTATION": "NONE",
        "PUSH_PR_MERGE": "NONE",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "WORKTREE_DISPOSITION": "RETAIN",
    }
    return cast(dict[str, Any], json.loads(encode(result)))


def verify_result(result: dict[str, Any]) -> dict[str, Any]:
    verify_source_authority()
    if result != build_result():
        raise AssertionError("result differs from deterministic replay/source binding")
    return {
        "status": "PASS",
        "total_members": 112,
        "total_vectors": 123,
        "novel_members": 38,
        "novel_vectors": 39,
        "final_family_ub": 354981480,
        "family_digest": EXPECTED_FAMILY_DIGEST,
    }


def verify_stored_result() -> dict[str, Any]:
    data = RESULT_PATH.read_bytes()
    result = cast(dict[str, Any], json.loads(data))
    status = verify_result(result)
    if data != encode(result).encode():
        raise AssertionError("byte-for-byte result replay failed")
    return status


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(verify_stored_result(), sort_keys=True))
        return
    result = build_result()
    if args.write:
        RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
        RESULT_PATH.write_text(encode(result), encoding="utf-8")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "TASK_STATUS",
                    "NEW_STATE_A_UB",
                    "NEW_STATE_B_UB",
                    "FINAL_COMPLETE_R3_UB",
                    "FINAL_OWNER",
                    "RUNNER_UP",
                    "STRICT_GAIN",
                    "REMAINING_GAP",
                )
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
