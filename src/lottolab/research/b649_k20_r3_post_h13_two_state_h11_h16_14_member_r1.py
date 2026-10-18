"""Adopt H11/H16 for fourteen members after the sealed H13 adoption.

Events are residual: R_i = E_i minus (E_A union E_B). For n type-0
events the 6n outside incidences occupy 40 labels. Smoothing a>=b+2 to
a-1,b+1 decreases sum C(d,2) by a-b-1, proving the balanced collision
floor for every support. Double counting gives sum C(d,2)=e1+e2+e3.
For threshold-graph component ranks r_j, e<=sum C(r_j+1,2)
<=C(sum r_j+1,2); hence rank>=rho(e). Descending Kruskal spans each
nested threshold graph simultaneously, giving ONE common core tree with
weight >= (n-1)phi0 + sum_j (phi_j-phi_{j-1})rho(e_j).

For any outcome with m present events, the induced subgraph of a tree is
a forest with at most m-1 edges (zero for m=0). Thus
1_union <= sum 1_R - sum_tree 1_intersection pointwise for all supports.
Integrating proves Hunter. Attach each omitted event once as a new leaf
to a core root: n-1 + 18-n = 17 distinct edges on 18 vertices. Every
residual intersection is a set cardinality and nonnegative. Only the core
credit is used; no positive attachment floor is assumed.

Existing credits combine by MAX and are subtracted once. Compressed
members MAX all represented-vector bounds. All other sealed bounds and
all Classified/Tail terms survive unchanged. No predecessor construction,
census, solver, or official-outcome enumeration is invoked.
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
from dataclasses import replace
from functools import cache
from hashlib import sha256
from itertools import combinations
from math import comb
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_r3_post_state146_h13_eight_member_adoption_r1 as h13
from lottolab.research import b649_k20_r3_preserved_eleven_hunter_certificate_r1 as hunter
from lottolab.research import b649_k20_r3_r12_root65_joint_certificate_r1 as root65

catalog = h13.catalog
dense, sparse, member_id = h13.dense, h13.sparse, h13.member_id
encode, digest, family_digest = h13.encode, h13.digest, h13.family_digest
type CountVector = tuple[int, ...]
type Edge = tuple[int, int]
type Terms = tuple[tuple[str, int], ...]
TASK_ID = "B649_K20_R3_POST_H13_H11_H16_14_MEMBER_ADOPTION_R1"
TASK_BRANCH = "codex/b649-k20-r3-post-h13-h11-h16-14-member-adoption-r1"
BASE_HEAD = "15d1630c1c096efe63897b7094b75c31b888cb2a"
BASE_TREE = "c1cc447e2e0e658f351e432da4052704c178ef71"
BASE_RESULT_SHA256 = "a22b87d1954f92f4ffef90c45dae51ee7ff74a093244bfe37c831166f5e47adb"
REPO_ROOT = Path(__file__).resolve().parents[3]
BASE_RESULT = h13.RESULT_RELATIVE
SOURCE_RELATIVE = "src/lottolab/research/" + Path(__file__).name
TEST_RELATIVE = "tests/unit/test_" + Path(__file__).name
RESULT_RELATIVE = h13.RESULTS + "b649-k20-r3-post-h13-two-state-h11-h16-14-member-r1-result.json"
RESULT_PATH = REPO_ROOT / RESULT_RELATIVE
STATE_A, STATE_B = root65.STATE_A, root65.STATE_B
# members, vectors, targets, core size, old state bound, untouched maximum.
SPECS = {
    STATE_A: (989, 1072, 2, 16, 355112590, 355016928),
    STATE_B: (1222, 1325, 12, 11, 355111939, 355107928),
}
FLOORS = (107800, 574000, 1691620, 3451651)
# incidences, balanced collision floor, threshold cases, rank, Hunter minimum.
CORE_SPECS = {11: (66, 26, 30216, 7, 4341400), 16: (96, 72, 291143, 12, 7211400)}


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
    """Bind consumed ledgers and the actual transitive local import closure."""
    paths = {
        BASE_RESULT,
        root65.RESULT_RELATIVE,
        root65.r12.RESULT_RELATIVE,
        "src/lottolab/__init__.py",
        *h13.source_paths(),
        *root65.r12.source_paths(),
    }
    pending = [h13.__name__, root65.__name__]
    visited: set[str] = set()
    while pending:
        name = pending.pop()
        if name in visited:
            continue
        visited.add(name)
        path = "src/" + name.replace(".", "/") + ".py"
        if not (REPO_ROOT / path).is_file():
            path = "src/" + name.replace(".", "/") + "/__init__.py"
        if not (REPO_ROOT / path).is_file():
            continue
        paths.add(path)
        for node in ast.walk(ast.parse(frozen_blob(path))):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("lottolab"):
                    pending.append(node.module)
                    pending.extend(node.module + "." + a.name for a in node.names)
            elif isinstance(node, ast.Import):
                pending.extend(a.name for a in node.names if a.name.startswith("lottolab"))
    return tuple(sorted(paths))


def verify_source_authority() -> dict[str, Any]:
    if (
        git_bytes("show", "-s", "--format=%H %T", BASE_HEAD).decode().strip()
        != (f"{BASE_HEAD} {BASE_TREE}")
        or sha256(frozen_blob(BASE_RESULT)).hexdigest() != BASE_RESULT_SHA256
    ):
        raise AssertionError("immutable BASE HEAD/TREE/result SHA identity failed")
    if subprocess.run(
        ["git", "-C", str(REPO_ROOT), "merge-base", "--is-ancestor", BASE_HEAD, "HEAD"],
        check=False,
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


def expected_vectors(state_id: str) -> set[CountVector]:
    if state_id == STATE_A:
        return {dense([[0, 16], [t, 1], [25, 1]]) for t in (1, 4)}
    if state_id == STATE_B:
        return {
            tuple({0: 11, 1: j, 4: 5 - j, 10: 1, t: 1}.get(i, 0) for i in range(30))
            for t in (5, 16)
            for j in range(6)
        }
    raise AssertionError("only the two authorized States are applicable")


@cache
def region_rows(state_id: str) -> tuple[dict[str, Any], ...]:
    regions = [r for r in sealed(root65.RESULT_RELATIVE)["REGIONS"] if r["state_id"] == state_id]
    if state_id not in SPECS or len(regions) != 1:
        raise AssertionError("exact complete sealed State region required")
    rows = tuple(cast(list[dict[str, Any]], regions[0]["complete_region_members"]))
    mc, vc, _, _, bound, _ = SPECS[state_id]
    if (
        len(rows),
        len({r["member_id"] for r in rows}),
        sum(r["represented_vector_count"] for r in rows),
        max(r["final_bound"] for r in rows),
    ) != (mc, mc, vc, bound):
        raise AssertionError("full sealed member/vector region coverage failed")
    return rows


@cache
def region_vectors(state_id: str) -> dict[CountVector, tuple[CountVector, ...]]:
    recovered: dict[CountVector, tuple[CountVector, ...]] = {}
    for row in region_rows(state_id):
        v = dense(row["witness_counts"])
        member = catalog.LedgerMember(
            v, row["represented_vector_count"], row["raw_bound"], row["final_bound"]
        )
        signature = hunter.eleven.compression_signature(catalog.rebuild_member(member))
        vectors = tuple(dense(x) for x in row["represented_vectors"])
        vr = row["represented_vector_bounds"]
        if (
            not vectors
            or min(vectors) != v
            or tuple(sorted(vectors)) != vectors
            or len(vectors) != member.represented_vector_count
            or member_id(v) != row["member_id"]
            or catalog.normalized(signature) != row["compression_signature"]
            or vectors != tuple(dense(r["counts"]) for r in vr)
            or member.final_bound != member_bound(tuple(int(r["final_bound"]) for r in vr))
        ):
            raise AssertionError("canonical compressed member/alias/MAX identity failed")
        for vector, vector_row in zip(vectors, vr, strict=True):
            state = catalog.rebuild_member(
                replace(member, counts=vector, represented_vector_count=1)
            )
            earlier = root65.sealed_vector_bounds().get(vector, ())
            if (
                len(vector) != 30
                or any(type(c) is not int or c < 0 for c in vector)
                or sum(vector) != 18
                or hunter.eleven.compression_signature(state) != signature
                or hunter.r14.raw_bound(state) != member.raw_bound
                or any(vector_row["final_bound"] > b for _, b in earlier)
            ):
                raise AssertionError(
                    "represented-vector signature or prior bound preservation failed"
                )
        recovered[v] = vectors
    flat = [v for vs in recovered.values() for v in vs]
    if len(flat) != len(set(flat)) or len(flat) != SPECS[state_id][1]:
        raise AssertionError("complete unique represented-vector coverage failed")
    return recovered


def target_rows(state_id: str) -> tuple[dict[str, Any], ...]:
    expected = expected_vectors(state_id)
    rows = tuple(r for r in region_rows(state_id) if dense(r["witness_counts"]) in expected)
    if (
        len(rows) != SPECS[state_id][2]
        or {dense(r["witness_counts"]) for r in rows} != expected
        or any(
            r["represented_vector_count"] != 1
            or region_vectors(state_id)[dense(r["witness_counts"])] != (dense(r["witness_counts"]),)
            for r in rows
        )
    ):
        raise AssertionError("exact single-vector target identities/coverage failed")
    return rows


def validate_subset(v: CountVector, u: CountVector, n: int) -> None:
    if (
        n not in CORE_SPECS
        or len(v) != 30
        or len(u) != 30
        or any(type(c) is not int or c < 0 for c in (*v, *u))
        or sum(v) != 18
        or u != (n, *([0] * 29))
        or any(a > b for a, b in zip(u, v, strict=True))
    ):
        raise AssertionError("H11/H16 require integer 0<=u<=v with only type-0 events")


def validate_pair_floors(floors: hunter.Cells, rows: tuple[hunter.PairRow, ...]) -> None:
    if floors != FLOORS or tuple(r[:6] for r in rows) != tuple(
        (0, 0, 0, 0, 0, z) for z in range(4)
    ):
        raise AssertionError(
            "four exact type-0/type-0 residual floors required; mixed pairs forbidden"
        )
    hunter.require_safe_pair_floors(floors, rows)
    if tuple(r[6] for r in rows) != floors:
        raise AssertionError("exact residual pair floor recount failed")


@cache
def pair_proof() -> dict[str, Any]:
    if hunter.type_cells(0) != (0, 0, 0, 6) or hunter.family_pair_overlap_ceiling() != 3:
        raise AssertionError("type-0 incidence/overlap domain failed")
    rows = hunter.exact_pair_rows(((0, 0),))
    validate_pair_floors(FLOORS, rows)
    recount: list[dict[str, int]] = []
    for a, b, s, x, y, z, residual in rows:
        tickets = hunter.realize_pair(hunter.type_cells(a), hunter.type_cells(b), (s, x, y, z))
        raw = hunter.outcome_count(tickets)
        ta = hunter.outcome_count((*tickets, hunter.ANCHOR_A))
        tb = hunter.outcome_count((*tickets, hunter.ANCHOR_B))
        quad = hunter.outcome_count((*tickets, hunter.ANCHOR_A, hunter.ANCHOR_B))
        if (
            raw - ta - tb + quad != residual
            or hunter.six.residual_pair_intersection(a, b, (s, x, y, z)) != residual
        ):
            raise AssertionError("raw E-event floors cannot replace exact residual R intersections")
        recount.append(
            {
                "overlap": z,
                "raw_E": raw,
                "triple_A": ta,
                "triple_B": tb,
                "quadruple": quad,
                "residual_R": residual,
            }
        )
    return {"pair_rows": rows, "pair_floors": FLOORS, "recount": recount}


def validate_tree_extension(
    indices: tuple[int, ...], core: tuple[Edge, ...], attachments: tuple[Edge, ...]
) -> tuple[Edge, ...]:
    n, chosen = len(indices), set(indices)
    full = (*core, *attachments)
    if (
        n not in CORE_SPECS
        or len(chosen) != n
        or not chosen <= set(range(18))
        or len(core) != n - 1
        or any(a not in chosen or b not in chosen or a == b for a, b in core)
        or hunter.graph_rank(18, core) != n - 1
        or len(attachments) != 18 - n
        or set(attachments) != {(indices[0], j) for j in range(18) if j not in chosen}
        or len({frozenset(e) for e in full}) != 17
        or hunter.graph_rank(18, full) != 17
    ):
        raise AssertionError("one connected acyclic 18-vertex/17-edge tree required")
    return full


@cache
def core_proof(n: int) -> dict[str, Any]:
    if n not in CORE_SPECS:
        raise AssertionError("only H11/H16 core proofs authorized")
    incidences, expected_q, cases, rank, floor = CORE_SPECS[n]
    pair_proof()
    q, r = divmod(6 * n, 40)
    collision = (40 - r) * comb(q, 2) + r * comb(q + 1, 2)
    if (
        incidences != 6 * n
        or collision != expected_q
        or hunter.balanced_collision_mass(6 * n, 40) != collision
    ):
        raise AssertionError("balanced collision floor failed")
    minimum = hunter.minimum_tree_correction(FLOORS, collision, n)
    if (minimum.census_size, minimum.edge_counts, minimum.rank_floors, minimum.correction) != (
        cases,
        (collision, 0, 0),
        (rank, 0, 0),
        floor,
    ) or minimum.correction != (n - 1) * FLOORS[0] + rank * (FLOORS[1] - FLOORS[0]):
        raise AssertionError("complete exact threshold minimum/ranks/cases failed")
    hunter.verify_rank_floor_algebra(n)
    core = tuple((j - 1, j) for j in range(1, n))
    attachments = tuple((0, j) for j in range(n, 18))
    validate_tree_extension(tuple(range(n)), core, attachments)
    return {
        "event_count": n,
        "outside_labels": 40,
        "outside_incidences": incidences,
        "balanced_frequencies": ((q, 40 - r), (q + 1, r)),
        "collision_floor": collision,
        "threshold_cases": minimum.census_size,
        "minimizer": minimum.edge_counts,
        "ranks": minimum.rank_floors,
        "hunter_floor": minimum.correction,
        "rank_floor_table": [hunter.rank_floor(e) for e in range(comb(n, 2) + 1)],
        "universal_argument": __doc__,
        "attachment_credit": 0,
        "tree_core": core,
        "tree_attachments": attachments,
    }


def apply_credit(uncorrected: int, prior_bound: int, credits: dict[str, int]) -> tuple[int, int]:
    if not credits or any(type(c) is not int or c < 0 for c in credits.values()):
        raise AssertionError("nonnegative integer existing valid credits required")
    credit = max(credits.values())
    return credit, min(prior_bound, uncorrected - credit)


def member_bound(bounds: tuple[int, ...]) -> int:
    if not bounds:
        raise AssertionError("all represented-vector bounds required")
    return max(bounds)


def witness_analysis(v: CountVector, n: int) -> dict[str, Any]:
    proof = core_proof(n)
    support = h13.ts53.prior.legal_support(v)
    if not hunter.r8.validate_support_assignment(v, support):
        raise AssertionError("legal support witness failed")
    types = tuple(i for i, c in enumerate(v) for _ in range(c))
    if types[:n] != (0,) * n:
        raise AssertionError("selected events must all have type zero")
    tickets = tuple(frozenset(t) for t in support[:n])
    overlaps = {(a, b): len(tickets[a] & tickets[b]) for a, b in combinations(range(n), 2)}
    core = hunter.threshold_tree(n, overlaps)
    attachments = tuple((0, j) for j in range(n, 18))
    validate_tree_extension(tuple(range(n)), core, attachments)
    values = {(r[0], r[1], tuple(r[2:6])): r[6] for r in pair_proof()["pair_rows"]}
    observed = hunter.witness_analysis((n, *([0] * 29)), support[:n], FLOORS, values)
    if (
        observed["collision_mass"] < proof["collision_floor"]
        or sum(FLOORS[overlaps[e]] for e in core) < proof["hunter_floor"]
    ):
        raise AssertionError("witness violates universal core certificate")
    carried = h13.ts53.prior.sealed_vector_rows().get(v, ())
    for row in carried:
        old = tuple(tuple(int(x) for x in t) for t in row["support_witness"])
        if not hunter.r8.validate_support_assignment(v, old):
            raise AssertionError("carried legal witness failed")
    return {
        "support_witness": support,
        "observed": observed,
        "tree_core": core,
        "tree_attachments": attachments,
        "carried_witness_count": len(carried),
    }


def certify_target(state_id: str, row: dict[str, Any]) -> dict[str, Any]:
    v, n = dense(row["witness_counts"]), SPECS[state_id][3]
    u = (n, *([0] * 29))
    validate_subset(v, u, n)
    state = catalog.rebuild_member(catalog.LedgerMember(v, 1, row["raw_bound"], row["final_bound"]))
    uncorrected = hunter.r14.joint_constant() - state.anchor_pair_s2 + state.anchor_triple_s3
    prior = int(row["represented_vector_bounds"][0]["final_bound"])
    earlier = root65.sealed_vector_bounds().get(v, ())
    credits = {
        "R6_PAIR": state.residual_pair_union_penalty,
        "FOREST": state.complementary_forest_floor,
        "SEALED_MEMBER": uncorrected - row["final_bound"],
        "SEALED_VECTOR": uncorrected - prior,
        **{f"SEALED:{path}": uncorrected - b for path, b in earlier},
    }
    existing = max(credits.values())
    credits[f"H{n}_CORE"] = int(core_proof(n)["hunter_floor"])
    credit, bound = apply_credit(uncorrected, prior, credits)
    expected_raw = 362000590 if state_id == STATE_A else (359129939 if v[5] else 359129491)
    expected = 354789190 if state_id == STATE_A else (354788539 if v[5] else 354788091)
    residual = sum(c * hunter.residual_event_size(i) for i, c in enumerate(v))
    if (
        uncorrected != expected_raw
        or uncorrected != hunter.anchor_union_size() + residual
        or existing != (6888000 if state_id == STATE_A else 4018000)
        or existing != uncorrected - prior
        or bound != expected
    ):
        raise AssertionError("MAX-only existing credits/single replacement/target bound failed")
    return {
        "state_id": state_id,
        "member_id": row["member_id"],
        "counts": sparse(v),
        "represented_vector_count": 1,
        "represented_vectors": [sparse(v)],
        "compression_signature": row["compression_signature"],
        "selected_subset_counts": sparse(u),
        "uncorrected_bound": uncorrected,
        "anchor_union": hunter.anchor_union_size(),
        "residual_event_sum": residual,
        "vector_prior_bound": prior,
        "existing_applied_credit": existing,
        "corrections": credits,
        "new_credit": credit,
        "vector_new_bound": bound,
        "member_new_bound": member_bound((bound,)),
        "witness_analysis": witness_analysis(v, n),
    }


def update_region(state_id: str) -> dict[str, Any]:
    vectors = region_vectors(state_id)
    records = [certify_target(state_id, row) for row in target_rows(state_id)]
    replacements = {r["member_id"]: r["vector_new_bound"] for r in records}
    updated: list[dict[str, Any]] = []
    for row in region_rows(state_id):
        vr = [
            {
                **r,
                "prior_bound": r["final_bound"],
                "final_bound": replacements.get(row["member_id"], r["final_bound"]),
            }
            for r in row["represented_vector_bounds"]
        ]
        updated.append(
            {
                **row,
                "prior_bound": row["final_bound"],
                "final_bound": member_bound(tuple(int(r["final_bound"]) for r in vr)),
                "represented_vector_bounds": vr,
            }
        )
    untouched = [r for r in updated if r["member_id"] not in replacements]
    untouched_vectors = [v for r in untouched for v in r["represented_vector_bounds"]]
    mc, vc, tc, _, _, remainder = SPECS[state_id]
    if (
        len(untouched) != mc - tc
        or len(untouched_vectors) != vc - tc
        or any(r["final_bound"] != r["prior_bound"] for r in (*untouched, *untouched_vectors))
        or max(r["final_bound"] for r in untouched) != remainder
        or max(r["final_bound"] for r in updated) != remainder
        or sum(r["final_bound"] != r["prior_bound"] for r in updated) != tc
    ):
        raise AssertionError("untouched bounds or recomputed State maximum failed")
    return {
        "state_id": state_id,
        "region_member_count": mc,
        "region_vector_count": vc,
        "target_member_count": len(records),
        "target_vector_count": len(records),
        "all_represented_vectors_sha256": digest(tuple(vectors.items())),
        "member_certificates": records,
        "complete_region_members": updated,
        "preserved_member_count": len(untouched),
        "preserved_vector_count": len(untouched_vectors),
        "preserved_member_bounds_sha256": digest(untouched),
        "preserved_vector_bounds_sha256": digest(untouched_vectors),
        "preserved_remainder_max": max(r["final_bound"] for r in untouched),
        "new_state_bound": max(r["final_bound"] for r in updated),
    }


@cache
def family_terms() -> Terms:
    base, full = sealed(BASE_RESULT), sealed(h13.BASE_RESULT)
    states = tuple((str(r["stable_id"]), int(r["bound"])) for r in base["FINAL_STATE_TERMS"])
    classified = tuple(
        (str(r["stable_id"]), int(r["bound"])) for r in full["FINAL_CLASSIFIED_TERMS"]
    )
    terms = (*states, *classified, ("unclassified-tail", int(full["TAIL_BOUND"])))
    if (
        len(states) != 23
        or len(classified) != 56550
        or len(dict(terms)) != 56574
        or family_digest(terms) != base["FAMILY_RECOMPUTATION"]["new_sha256"]
        or max(b for _, b in terms) != 355112590
    ):
        raise AssertionError("complete sealed 56574 Family terms identity failed")
    return terms


def recompute_family(terms: Terms, bounds: dict[str, int]) -> dict[str, Any]:
    if terms != family_terms() or set(bounds) != set(SPECS):
        raise AssertionError("all sealed State/Classified/Tail terms must be preserved")
    updated = tuple((k, min(b, bounds[k]) if k in bounds else b) for k, b in terms)
    ordered = sorted(updated, key=lambda r: (-r[1], r[0]))
    if (
        sum(a != b for a, b in zip(terms, updated, strict=True)) != 2
        or dict(updated)[h13.STATE_ID] != 355110434
        or dict(updated)["state:s2-14696976-s3-1059324"] != 354603232
        or updated[23:] != terms[23:]
        or max(b for _, b in updated[23:-1]) != 354800665
        or updated[-1] != ("unclassified-tail", 354039277)
        or ordered[:2] != [(h13.STATE_ID, 355110434), (STATE_B, 355107928)]
    ):
        raise AssertionError("two State replacements/Family max/owner/runner-up failed")
    return {
        "term_count": len(updated),
        "preserved_terms": 56572,
        "old_sha256": family_digest(terms),
        "new_sha256": family_digest(updated),
        "states": [{"stable_id": k, "bound": b} for k, b in updated[:23]],
        "classified_count": len(updated[23:-1]),
        "classified_sha256": family_digest(updated[23:-1]),
        "classified_max": max(b for _, b in updated[23:-1]),
        "tail": updated[-1][1],
        "start_max": max(b for _, b in terms),
        "final_max": max(b for _, b in updated),
        "owner": ordered[0][0],
        "runner_up": {"stable_id": ordered[1][0], "bound": ordered[1][1]},
    }


def build_result() -> dict[str, Any]:
    authority = verify_source_authority()
    regions = [update_region(s) for s in SPECS]
    family = recompute_family(
        family_terms(), {r["state_id"]: r["new_state_bound"] for r in regions}
    )
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
        "PAIR_PROOF": pair_proof(),
        "CORE_PROOFS": {f"H{n}": core_proof(n) for n in CORE_SPECS},
        "H11_PROOF_STATUS": "PASS_30216_CASES_4341400",
        "H16_PROOF_STATUS": "PASS_291143_CASES_7211400",
        "PAIR_FLOOR_STATUS": "PASS_EXACT_TYPE0_RESIDUAL_RECOUNT",
        "COLLISION_FLOOR_STATUS": "PASS_Q11_26_Q16_72",
        "TREE_EXTENSION_STATUS": "PASS_UNIVERSAL_18_VERTICES_17_EDGES_NONNEGATIVE_LEAVES",
        "REGIONS": regions,
        "NEW_STATE_A_UB": regions[0]["new_state_bound"],
        "NEW_STATE_B_UB": regions[1]["new_state_bound"],
        "NO_DOUBLE_COUNT_STATUS": "PASS_MAX_ALL_VALID_CREDITS_SUBTRACT_ONCE_MEMBER_MAX",
        "PREDECESSOR_PRESERVATION": "PASS_H13_STATE146_TS53_TS153_R12_ROOT65_TS106_H0",
        "FAMILY_RECOMPUTATION": family,
        "FINAL_STATE_TERMS": family["states"],
        "FULL_FAMILY_RECOMPUTATION": "PASS_56574_TERMS_23_STATES_56550_CLASSIFIED_TAIL",
        "START_COMPLETE_R3_UB": family["start_max"],
        "FINAL_COMPLETE_R3_UB": family["final_max"],
        "FINAL_OWNER": family["owner"],
        "RUNNER_UP": family["runner_up"],
        "STRICT_GAIN": family["start_max"] - family["final_max"],
        "INCUMBENT": 313263888,
        "REMAINING_GAP": family["final_max"] - 313263888,
        "WITNESS_SOUNDNESS_STATUS": "PASS_14_LEGAL_SUPPORTS_AND_CARRIED_WITNESSES",
        "OWNER_REGION_CALLS": 0,
        "R7_CENSUS_CALLS": 0,
        "NEW_HEAVY_SOLVER_STARTED": False,
        "STATE146_CERTIFICATE_REBUILD_CALLS": 0,
        "OFFICIAL_OUTCOME_ENUMERATION_USED": False,
        "PRODUCTION_MUTATION": "NONE",
        "PUSH_PR_MERGE": "NONE",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "WORKTREE_DISPOSITION": "RETAIN",
    }
    if (result["STRICT_GAIN"], result["REMAINING_GAP"]) != (2156, 41846546):
        raise AssertionError("strict Family gain/remaining gap failed")
    return cast(dict[str, Any], json.loads(encode(result)))


def verify_result(result: dict[str, Any]) -> dict[str, Any]:
    verify_source_authority()
    if result != build_result():
        raise AssertionError("result differs from deterministic replay/source binding")
    return {
        "status": "PASS",
        "members": 14,
        "vectors": 14,
        "region_members": 2211,
        "region_vectors": 2397,
        "state_terms": 23,
        "family_terms": 56574,
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
                    "STRICT_GAIN",
                    "REMAINING_GAP",
                )
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
