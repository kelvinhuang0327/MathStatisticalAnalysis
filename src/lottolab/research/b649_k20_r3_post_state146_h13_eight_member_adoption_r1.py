"""Adopt one universal H13 core certificate for eight sealed State13548976 members.

All intersections are residual: R_i = E_i minus (E_A union E_B). Thirteen
type-0 tickets have 78 incidences on 40 outside labels. Smoothing integer
frequencies gives Q>=38. For a threshold graph with component ranks r_j,
e<=sum C(r_j+1,2)<=C(sum r_j+1,2), so its rank is at least rho(e).
Descending Kruskal simultaneously spans all three nested threshold graphs.
Consequently one core tree weighs at least the complete threshold minimum.

For every outcome with m present vertices, a tree induces a forest with at
most m-1 edges (zero when m=0). Thus 1_union <= sum 1_R - sum 1_pair
pointwise. Integration proves Hunter's inequality for every realization.
Attach each of the other five events as a leaf with nonnegative residual
intersection; the full 18-event tree retains the core credit without needing
positive attachment credit. Legal witnesses illustrate, never prove, this
universal statement. No official outcome enumeration or solver is used.

Use MAX of existing valid credits and H13, subtract once, preserve all other
member/vector bounds, and remaximize all 56574 sealed Family terms.
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
from functools import cache
from hashlib import sha256
from itertools import combinations
from math import comb
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_r3_preserved_eleven_hunter_certificate_r1 as hunter
from lottolab.research import b649_k20_r3_state_13548976_fifty_three_subset_hunter_r1 as ts53

catalog = ts53.catalog
dense, sparse, member_id = ts53.dense, ts53.sparse, ts53.member_id
type CountVector = tuple[int, ...]
type Terms = tuple[tuple[str, int], ...]
type Edge = tuple[int, int]
TASK_ID = "B649_K20_R3_POST_STATE146_H13_EIGHT_MEMBER_ADOPTION_R1"
TASK_BRANCH = "codex/b649-k20-r3-post-state146-h13-eight-member-adoption-r1"
BASE_HEAD = "c7a8b87bd844afa87893d588b76de71096750a76"
BASE_TREE = "7ca8d8f8840bad846e3f5fbca4c948e6f499d5ce"
BASE_RESULT_SHA256 = "2680e9b1f396991336690ee7660998c4a010c6f14efef40c77e601e3d3280834"
TS53_DONOR_HEAD = "3212e448cbe0a9a150d9705ae95dc68669a3106a"
TS53_DONOR_TREE = "ac60557c255a88e933502c8ed2ded6d84062752e"
TS53_RESULT_SHA256 = "3c9583835d5e9f72c21d1ecf09065b1e89bda0e4bd5e18e798b9eb7645d20e31"
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS = "docs/research/matrix-native-results/"
BASE_RESULT = RESULTS + "b649-k20-r3-state-14696976-universal-hunter-certificate-r1-result.json"
SOURCE_RELATIVE = "src/lottolab/research/" + Path(__file__).name
TEST_RELATIVE = "tests/unit/test_" + Path(__file__).name
RESULT_RELATIVE = RESULTS + "b649-k20-r3-post-state146-h13-eight-member-adoption-r1-result.json"
RESULT_PATH = REPO_ROOT / RESULT_RELATIVE
STATE_ID = "state:s2-13548976-s3-951748"
TARGET_CUTOFF = 355112590
CORE = (13, *([0] * 29))
FLOORS = (107800, 574000, 1691620, 3451651)
EXPECTED_IDS = {
    f"[0,13]{middle}[{last},1][25,1]"
    for last in (5, 16)
    for middle in ("[1,1][4,2]", "[1,2][4,1]", "[1,3]", "[4,3]")
}


def encode(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def digest(value: object) -> str:
    return sha256(json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def family_digest(terms: Terms) -> str:
    return sha256(repr(terms).encode("ascii")).hexdigest()


def git_bytes(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(REPO_ROOT), *args])


@cache
def frozen_blob(head: str, relative: str) -> bytes:
    return git_bytes("show", f"{head}:{relative}")


@cache
def source_paths() -> tuple[str, ...]:
    """Bind the actual transitive local imports as well as all consumed ledgers."""
    paths = {BASE_RESULT, ts53.RESULT_RELATIVE, "src/lottolab/__init__.py", *ts53.source_paths()}
    pending = [ts53.__name__]
    visited: set[str] = set()
    while pending:
        name = pending.pop()
        if name in visited:
            continue
        visited.add(name)
        relative = "src/" + name.replace(".", "/") + ".py"
        if not (REPO_ROOT / relative).is_file():
            relative = "src/" + name.replace(".", "/") + "/__init__.py"
        if not (REPO_ROOT / relative).is_file():
            continue
        paths.add(relative)
        tree = ast.parse(frozen_blob(BASE_HEAD, relative))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("lottolab"):
                    pending.append(node.module)
                    pending.extend(node.module + "." + a.name for a in node.names)
            elif isinstance(node, ast.Import):
                pending.extend(a.name for a in node.names if a.name.startswith("lottolab"))
    return tuple(sorted(paths))


def verify_source_authority() -> dict[str, Any]:
    """Check live bytes even after all mathematical/data caches are warm."""
    identities: dict[str, Any] = {}
    for label, head, tree, relative, expected in (
        ("BASE", BASE_HEAD, BASE_TREE, BASE_RESULT, BASE_RESULT_SHA256),
        ("TS53_DONOR", TS53_DONOR_HEAD, TS53_DONOR_TREE, ts53.RESULT_RELATIVE, TS53_RESULT_SHA256),
    ):
        if git_bytes("show", "-s", "--format=%H %T", head).decode().strip() != f"{head} {tree}":
            raise AssertionError("pinned HEAD/TREE identity mismatch")
        data = frozen_blob(head, relative)
        if sha256(data).hexdigest() != expected or (REPO_ROOT / relative).read_bytes() != data:
            raise AssertionError("pinned result SHA/byte identity mismatch")
        identities[label] = {"HEAD": head, "TREE": tree, "RESULT_SHA256": expected}
    if subprocess.run(
        ["git", "-C", str(REPO_ROOT), "merge-base", "--is-ancestor", BASE_HEAD, "HEAD"],
        check=False,
    ).returncode:
        raise AssertionError("checkout must descend from pinned BASE_HEAD")
    upstream: dict[str, str] = {}
    for relative in source_paths():
        frozen = frozen_blob(BASE_HEAD, relative)
        if (REPO_ROOT / relative).read_bytes() != frozen:
            raise AssertionError(
                f"immutable executing source/input byte identity failed: {relative}"
            )
        upstream[relative] = sha256(frozen).hexdigest()
    return {
        **identities,
        "upstream_sha256": upstream,
        "implementation_sha256": {
            p: sha256((REPO_ROOT / p).read_bytes()).hexdigest()
            for p in (SOURCE_RELATIVE, TEST_RELATIVE)
        },
    }


@cache
def sealed(relative: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(frozen_blob(BASE_HEAD, relative)))


@cache
def region_rows() -> tuple[dict[str, Any], ...]:
    rows = tuple(
        cast(list[dict[str, Any]], sealed(ts53.RESULT_RELATIVE)["COMPLETE_REGION_MEMBERS"])
    )
    if (
        len(rows) != 1427
        or len({r["member_id"] for r in rows}) != 1427
        or sum(r["represented_vector_count"] for r in rows) != 1543
        or max(r["final_bound"] for r in rows) != 355116818
        or sealed(BASE_RESULT)["FINAL_COMPLETE_R3_UB"] != 355116818
    ):
        raise AssertionError("complete current sealed 1427/1543 region identity failed")
    return rows


@cache
def region_vectors() -> dict[CountVector, tuple[CountVector, ...]]:
    recovered = ts53.represented_vectors()
    if len(recovered) != 1427 or sum(map(len, recovered.values())) != 1543:
        raise AssertionError("complete represented-vector coverage failed")
    for row in region_rows():
        v = dense(row["witness_counts"])
        member = catalog.LedgerMember(
            v, row["represented_vector_count"], row["raw_bound"], row["final_bound"]
        )
        signature = hunter.eleven.compression_signature(catalog.rebuild_member(member))
        vectors = recovered[v]
        if (
            row["member_id"] != member_id(v)
            or vectors != tuple(dense(x) for x in row["represented_vectors"])
            or min(vectors) != v
            or len(vectors) != row["represented_vector_count"]
            or catalog.normalized(signature) != row["compression_signature"]
        ):
            raise AssertionError("canonical identity/vector/compression signature mismatch")
    return recovered


def target_rows() -> tuple[dict[str, Any], ...]:
    targets = tuple(r for r in region_rows() if r["final_bound"] > TARGET_CUTOFF)
    if (
        TARGET_CUTOFF != 355112590
        or len(targets) != 8
        or {r["member_id"] for r in targets} != EXPECTED_IDS
        or any(r["represented_vector_count"] != 1 for r in targets)
        or any(
            region_vectors()[dense(r["witness_counts"])] != (dense(r["witness_counts"]),)
            for r in targets
        )
    ):
        raise AssertionError("exact eight single-vector target identities/coverage failed")
    return targets


def validate_h13_subset(v: CountVector, u: CountVector) -> None:
    """Task-bounded applicability; deliberately never call TS53 validate_subset."""
    if (
        len(v) != 30
        or len(u) != 30
        or any(type(c) is not int or c < 0 for c in (*v, *u))
        or sum(v) != 18
        or sum(u) != 13
        or u != CORE
        or any(a > b for a, b in zip(u, v, strict=True))
    ):
        raise AssertionError("H13 requires integer 0<=u<=v, u0=13, all other ui=0")


def validate_pair_floors(floors: hunter.Cells, rows: tuple[hunter.PairRow, ...]) -> None:
    expected_keys = tuple((0, 0, 0, 0, 0, z) for z in range(4))
    if tuple(r[:6] for r in rows) != expected_keys or floors != FLOORS:
        raise AssertionError("complete four exact type-0 residual floors required")
    hunter.require_safe_pair_floors(floors, rows)
    if tuple(r[6] for r in rows) != floors:
        raise AssertionError("exact residual pair floor recount failed")


def validate_tree_extension(
    indices: tuple[int, ...], core: tuple[Edge, ...], attachments: tuple[Edge, ...]
) -> tuple[Edge, ...]:
    chosen = set(indices)
    full = (*core, *attachments)
    if (
        len(indices) != 13
        or len(chosen) != 13
        or not chosen <= set(range(18))
        or len(core) != 12
        or any(a not in chosen or b not in chosen or a == b for a, b in core)
        or hunter.graph_rank(18, core) != 12
        or len(attachments) != 5
        or set(attachments) != {(indices[0], j) for j in range(18) if j not in chosen}
        or len({frozenset(e) for e in full}) != 17
        or hunter.graph_rank(18, full) != 17
    ):
        raise AssertionError("one connected acyclic 18-vertex 17-edge tree required")
    return full


@cache
def h13_proof() -> dict[str, Any]:
    if hunter.type_cells(0) != (0, 0, 0, 6) or hunter.family_pair_overlap_ceiling() != 3:
        raise AssertionError("type0/core overlap domain changed")
    rows = hunter.exact_pair_rows(((0, 0),))
    validate_pair_floors(FLOORS, rows)
    recount: list[dict[str, int]] = []
    for a, b, s, x, y, z, residual in rows:
        tickets = hunter.realize_pair(hunter.type_cells(a), hunter.type_cells(b), (s, x, y, z))
        raw = hunter.outcome_count(tickets)
        ta = hunter.outcome_count((*tickets, hunter.ANCHOR_A))
        tb = hunter.outcome_count((*tickets, hunter.ANCHOR_B))
        quad = hunter.outcome_count((*tickets, hunter.ANCHOR_A, hunter.ANCHOR_B))
        if raw - ta - tb + quad != residual:
            raise AssertionError("raw E intersection cannot substitute for residual R intersection")
        recount.append(
            {
                "outside_overlap": z,
                "raw_E": raw,
                "triple_A": ta,
                "triple_B": tb,
                "quadruple": quad,
                "residual_R": residual,
            }
        )
    q, r = divmod(78, 40)
    collision = (40 - r) * comb(q, 2) + r * comb(q + 1, 2)
    if collision != 38 or hunter.balanced_collision_mass(78, 40) != collision:
        raise AssertionError("balanced Q>=38 collision floor failed")
    minimum = hunter.minimum_tree_correction(FLOORS, collision, 13)
    if (minimum.census_size, minimum.edge_counts, minimum.rank_floors, minimum.correction) != (
        83479,
        (38, 0, 0),
        (9, 0, 0),
        5489400,
    ) or minimum.correction != 12 * FLOORS[0] + 9 * (FLOORS[1] - FLOORS[0]):
        raise AssertionError("complete H13 threshold cases/minimizer/ranks/minimum failed")
    indices = tuple(range(13))
    core = tuple((j - 1, j) for j in range(1, 13))
    attachments = tuple((0, j) for j in range(13, 18))
    validate_tree_extension(indices, core, attachments)
    return {
        "residual_definition": "Ri=Ei\\(EA union EB)",
        "subset_counts": sparse(CORE),
        "event_count": 13,
        "pair_rows": rows,
        "pair_floors": FLOORS,
        "pair_recount": recount,
        "outside_labels": 40,
        "outside_incidences": 78,
        "balanced_frequencies": ((q, 40 - r), (q + 1, r)),
        "collision_floor": collision,
        "collision_argument": "Smoothing a>=b+2 to a-1,b+1 reduces sum C(d,2) by a-b-1; "
        "38 frequencies are 2 and two are 1; double counting gives "
        "sum pair overlaps=sum C(d,2)=e1+e2+e3>=38.",
        "threshold_domain": "78>=e1>=e2>=e3>=0; e1+e2+e3>=38",
        "threshold_cases": minimum.census_size,
        "minimizer": minimum.edge_counts,
        "ranks": minimum.rank_floors,
        "hunter_floor": minimum.correction,
        "rank_floor_table": [hunter.rank_floor(e) for e in range(79)],
        "universal_hunter_argument": __doc__,
        "attachment_credit": 0,
        "tree_core": core,
        "tree_attachments": attachments,
        "tree_extension_argument": "For ANY core tree, attach each omitted event once to "
        "its first vertex; five new leaves, disjoint edges, "
        "18 vertices and 17 edges. Residual weights are >=0.",
    }


@cache
def existing_vector_bounds() -> dict[CountVector, tuple[int, ...]]:
    found: dict[CountVector, list[int]] = {}

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            row = cast(dict[str, Any], value)
            if "counts" in row and "vector_new_bound" in row:
                found.setdefault(dense(row["counts"]), []).append(int(row["vector_new_bound"]))
            for child in row.values():
                visit(child)
        elif isinstance(value, list):
            for child in cast(list[Any], value):
                visit(child)

    for relative in source_paths():
        if relative.endswith(".json"):
            visit(sealed(relative))
    return {v: tuple(bounds) for v, bounds in found.items()}


def apply_credit(uncorrected: int, prior_bound: int, credits: dict[str, int]) -> tuple[int, int]:
    if not credits or any(type(c) is not int or c < 0 for c in credits.values()):
        raise AssertionError("existing valid nonnegative integer credits required")
    new_credit = max(credits.values())
    return new_credit, min(prior_bound, uncorrected - new_credit)


def witness_analysis(v: CountVector, proof: dict[str, Any]) -> dict[str, Any]:
    support = ts53.prior.legal_support(v)
    if not hunter.r8.validate_support_assignment(v, support):
        raise AssertionError("legal support witness soundness failed")
    # Tickets in the support validator's type order put the 13 type-0 events first.
    selected = support[:13]
    values = {(r[0], r[1], tuple(r[2:6])): r[6] for r in proof["pair_rows"]}
    observed = hunter.witness_analysis(CORE, selected, FLOORS, values)
    tickets = tuple(frozenset(t) for t in selected)
    overlaps = {(a, b): len(tickets[a] & tickets[b]) for a, b in combinations(range(13), 2)}
    core = hunter.threshold_tree(13, overlaps)
    attachments = tuple((0, j) for j in range(13, 18))
    validate_tree_extension(tuple(range(13)), core, attachments)
    weight = sum(FLOORS[overlaps[e]] for e in core)
    if observed["collision_mass"] < 38 or weight < proof["hunter_floor"]:
        raise AssertionError("legal witness violates the universal H13 certificate")
    carried = ts53.prior.sealed_vector_rows().get(v, ())
    for row in carried:
        old = tuple(tuple(int(x) for x in t) for t in row["support_witness"])
        if not hunter.r8.validate_support_assignment(v, old):
            raise AssertionError("carried legal support witness failed")
    return {
        "support_witness": support,
        "observed": observed,
        "tree_core": core,
        "tree_attachments": attachments,
        "carried_legal_witness_count": len(carried),
    }


def certify_target(row: dict[str, Any]) -> dict[str, Any]:
    v = dense(row["witness_counts"])
    validate_h13_subset(v, CORE)
    member = catalog.LedgerMember(v, 1, row["raw_bound"], row["final_bound"])
    state = catalog.rebuild_member(member)
    uncorrected = hunter.r14.joint_constant() - state.anchor_pair_s2 + state.anchor_triple_s3
    prior = min((member.final_bound, *existing_vector_bounds().get(v, ())))
    credits = {
        "R6_PAIR": state.residual_pair_union_penalty,
        "FOREST": state.complementary_forest_floor,
        "SEALED_MEMBER": uncorrected - member.final_bound,
        "SEALED_VECTOR": uncorrected - prior,
    }
    existing = max(credits.values())
    proof = h13_proof()
    credits["H13_CORE"] = int(proof["hunter_floor"])
    new_credit, bound = apply_credit(uncorrected, prior, credits)
    residual = sum(c * hunter.residual_event_size(i) for i, c in enumerate(v))
    expected = 354793418 if v[5] else 354792970
    if (
        uncorrected != hunter.anchor_union_size() + residual
        or existing != 5166000
        or uncorrected - prior != existing
        or new_credit != 5489400
        or new_credit != max(credits.values())
        or bound != min(prior, uncorrected - new_credit)
        or bound != expected
    ):
        raise AssertionError("MAX-only existing credit/single replacement/target bound failed")
    return {
        "member_id": row["member_id"],
        "counts": sparse(v),
        "represented_vector_count": 1,
        "represented_vectors": [sparse(v)],
        "compression_signature": row["compression_signature"],
        "selected_subset_counts": sparse(CORE),
        "uncorrected_bound": uncorrected,
        "anchor_union": hunter.anchor_union_size(),
        "residual_event_sum": residual,
        "vector_prior_bound": prior,
        "existing_applied_credit": existing,
        "corrections": credits,
        "new_credit": new_credit,
        "vector_new_bound": bound,
        "member_prior_bound": member.final_bound,
        "member_new_bound": bound,
        "witness_analysis": witness_analysis(v, proof),
    }


def family_terms() -> Terms:
    source = sealed(BASE_RESULT)
    terms = tuple(
        (str(r["stable_id"]), int(r["bound"]))
        for r in (*source["FINAL_STATE_TERMS"], *source["FINAL_CLASSIFIED_TERMS"])
    )
    terms = (*terms, ("unclassified-tail", int(source["TAIL_BOUND"])))
    if (
        len(source["FINAL_STATE_TERMS"]) != 23
        or len(terms) != 56574
        or len(dict(terms)) != 56574
        or family_digest(terms) != source["NEW_FAMILY_TERMS_SHA256"]
        or max(b for _, b in terms) != 355116818
    ):
        raise AssertionError("complete sealed 56574 Family terms identity failed")
    return terms


def recompute_family(terms: Terms, state_bound: int) -> dict[str, Any]:
    if terms != family_terms():
        raise AssertionError("all sealed State/Classified/Tail terms must be preserved")
    updated = tuple((k, min(b, state_bound) if k == STATE_ID else b) for k, b in terms)
    ordered = sorted(updated, key=lambda r: (-r[1], r[0]))
    if (
        sum(a != b for a, b in zip(terms, updated, strict=True)) != 1
        or dict(updated)["state:s2-14696976-s3-1059324"] != 354603232
        or max(b for _, b in updated[23:-1]) != 354800665
        or updated[-1] != ("unclassified-tail", 354039277)
        or ordered[:2]
        != [("state:s2-13169800-s3-789320", 355112590), ("state:s2-12695020-s3-735532", 355111939)]
    ):
        raise AssertionError("single State replacement/full Family max/owner/runner-up failed")
    return {
        "term_count": len(updated),
        "preserved_terms": 56573,
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
    vectors, rows, targets = region_vectors(), region_rows(), target_rows()
    records = [certify_target(row) for row in targets]
    replacement = {r["member_id"]: r["member_new_bound"] for r in records}
    updated = [
        {
            **row,
            "prior_bound": row["final_bound"],
            "final_bound": replacement.get(row["member_id"], row["final_bound"]),
        }
        for row in rows
    ]
    vector_rows: list[dict[str, Any]] = []
    for row in rows:
        for v in vectors[dense(row["witness_counts"])]:
            prior = min((int(row["final_bound"]), *existing_vector_bounds().get(v, ())))
            vector_rows.append(
                {
                    "member_id": row["member_id"],
                    "counts": sparse(v),
                    "prior_bound": prior,
                    "final_bound": replacement.get(row["member_id"], prior),
                }
            )
    remainder = [r for r in updated if r["member_id"] not in replacement]
    untouched_vectors = [r for r in vector_rows if r["member_id"] not in replacement]
    bound = max(r["final_bound"] for r in updated)
    if (
        len(remainder) != 1419
        or len(untouched_vectors) != 1535
        or any(r["final_bound"] != r["prior_bound"] for r in (*remainder, *untouched_vectors))
        or sum(r["final_bound"] != r["prior_bound"] for r in updated) != 8
        or sum(r["final_bound"] != r["prior_bound"] for r in vector_rows) != 8
        or max(r["final_bound"] for r in remainder) != 355110434
        or max(replacement.values()) != 354793418
        or bound != 355110434
    ):
        raise AssertionError("untouched member/vector bounds or recomputed State max failed")
    family = recompute_family(family_terms(), bound)
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
        "SOURCE_AUTHORITY_STATUS": "PASS_IMMUTABLE_OBJECTS_AND_EXECUTING_BYTES",
        "TS53_DONOR_STATUS": "PASS_HEAD_TREE_RESULT_SHA_AND_BYTES",
        "STATE_ID": STATE_ID,
        "REGION_MEMBER_COVERAGE": len(rows),
        "REGION_VECTOR_COVERAGE": len(vector_rows),
        "TARGET_SELECTION": "current member bound > 355112590; complete sealed region ledger",
        "TARGET_MEMBER_COVERAGE": len(records),
        "TARGET_VECTOR_COVERAGE": len(records),
        "ALL_REPRESENTED_VECTORS_SHA256": digest(tuple((k, v) for k, v in vectors.items())),
        "H13_SUBSET_STATUS": "PASS_INTEGER_0_LE_U_LE_V_13_TYPE0_EVENTS",
        "H13_PROOF": h13_proof(),
        "PAIR_FLOOR_STATUS": "PASS_EXACT_RESIDUAL_RECOUNT",
        "COLLISION_FLOOR_STATUS": "PASS_BALANCED_Q_GE_38",
        "HUNTER_THRESHOLD_STATUS": "PASS_83479_CASES_5489400_MINIMUM",
        "TREE_EXTENSION_STATUS": "PASS_UNIVERSAL_CORE_TREE_PLUS_FIVE_NONNEGATIVE_LEAVES",
        "MEMBER_CERTIFICATES": records,
        "COMPLETE_REGION_MEMBERS": updated,
        "COMPLETE_VECTOR_BOUNDS": vector_rows,
        "PRESERVED_MEMBERS": len(remainder),
        "PRESERVED_VECTORS": len(untouched_vectors),
        "PRESERVED_MEMBER_BOUNDS_SHA256": digest(remainder),
        "PRESERVED_VECTOR_BOUNDS_SHA256": digest(untouched_vectors),
        "NO_DOUBLE_COUNT_STATUS": "PASS_MAX_ALL_EXISTING_VALID_CREDITS_SUBTRACT_ONCE",
        "UNTOUCHED_BOUNDS_STATUS": "PASS_ALL_1419_MEMBERS_1535_VECTORS_UNCHANGED",
        "NEW_TARGET_BOUNDS": {r["member_id"]: r["member_new_bound"] for r in records},
        "NEW_TARGET_COHORT_MAX": max(replacement.values()),
        "PRESERVED_REMAINDER_MAX": max(r["final_bound"] for r in remainder),
        "NEW_STATE_13548976_UB": bound,
        "NEW_STATE_14696976_UB": 354603232,
        "FAMILY_RECOMPUTATION": family,
        "FINAL_STATE_TERMS": family["states"],
        "FULL_FAMILY_RECOMPUTATION": "PASS_ALL_56574_TERMS_23_STATES_CLASSIFIED_TAIL",
        "START_COMPLETE_R3_UB": family["start_max"],
        "FINAL_COMPLETE_R3_UB": family["final_max"],
        "FINAL_OWNER": family["owner"],
        "RUNNER_UP": family["runner_up"],
        "STRICT_GAIN": family["start_max"] - family["final_max"],
        "INCUMBENT": 313263888,
        "REMAINING_GAP": family["final_max"] - 313263888,
        "WITNESS_SOUNDNESS_STATUS": "PASS_EIGHT_LEGAL_SUPPORTS_AND_CARRIED_WITNESSES",
        "OWNER_REGION_CALLS": 0,
        "R7_CENSUS_CALLS": 0,
        "HEAVY_SOLVER_USED": False,
        "OFFICIAL_OUTCOME_ENUMERATION_USED": False,
        "PRODUCTION_MUTATION": "NONE",
        "PUSH_PR_MERGE": "NONE",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "WORKTREE_DISPOSITION": "RETAIN",
    }
    if (result["STRICT_GAIN"], result["REMAINING_GAP"]) != (4228, 41848702):
        raise AssertionError("strict Family gain/remaining gap failed")
    return cast(dict[str, Any], json.loads(encode(result)))


def verify_result(result: dict[str, Any]) -> dict[str, Any]:
    verify_source_authority()
    records = result["MEMBER_CERTIFICATES"]
    if [r["member_id"] for r in records] != [r["member_id"] for r in target_rows()]:
        raise AssertionError("exact target member coverage failed")
    for record, row in zip(records, target_rows(), strict=True):
        v = dense(row["witness_counts"])
        validate_h13_subset(v, dense(record["selected_subset_counts"]))
        if (
            record["represented_vector_count"] != 1
            or record["represented_vectors"] != [sparse(v)]
            or record["counts"] != sparse(v)
        ):
            raise AssertionError("complete target represented-vector coverage failed")
        credit, bound = apply_credit(
            record["uncorrected_bound"], record["vector_prior_bound"], record["corrections"]
        )
        if record["new_credit"] != credit or record["vector_new_bound"] != bound:
            raise AssertionError("credits must combine by MAX and one subtraction, never SUM")
    if result != build_result():
        raise AssertionError("result differs from deterministic certificate replay/source binding")
    return {
        "status": "PASS",
        "members": 8,
        "vectors": 8,
        "region_members": 1427,
        "region_vectors": 1543,
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
                    "NEW_STATE_13548976_UB",
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
