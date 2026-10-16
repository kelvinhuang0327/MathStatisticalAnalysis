"""Universal State14696976 certificate, without recovering any region ledger.

The sealed R7 frontier is strictly increasing in both coordinates. R14 assigns
each aggregate-feasible state to its first dominator. At frontier rank 13 this
is exactly S2>=14696976 and 1005536<S3<=1059324, within the unchanged R7
loss-cutoff domain. All claims quantify over legal realizations in that domain;
no maximizing frontier witness is assumed to represent its other members.

Recount all 30 anchor types. Type29 alone exceeds the S3 ceiling. The other
28 nonzero types obey an integer dual inequality. Summing it, with the strict
integer S3 floor, excludes k<=8; k=18 has insufficient S3. Thus 9<=k<=17.

For the k type-0 residual events, smoothing outside-label frequencies gives Q.
Each overlap threshold graph with e edges has rank at least rho(e): if its
component ranks are r_i, e<=sum C(r_i+1,2)<=C(sum r_i+1,2). Descending
Kruskal simultaneously spans every nested threshold graph. The exhaustive
integer threshold relaxation therefore bounds the weight of one core tree.
Attach each other event once to a chosen type-0 root. All 105 legal root pair
rows are counted as RESIDUAL intersections by seven-set incidence DP, giving
88830 per attachment. These disjoint edges form the same 18-vertex tree.
Pointwise, the tree induced on m present events has at most m-1 edges, proving
Hunter's union bound after integration over outcomes. No independent credits
are added. Adopt MIN(sealed State bound, universal State bound), replace that
term once, and MAX every one of the 56574 sealed Family terms.
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
from collections.abc import Mapping
from functools import cache
from hashlib import sha256
from itertools import pairwise
from math import comb
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_r3_preserved_eleven_hunter_certificate_r1 as hunter

type Terms = tuple[tuple[str, int], ...]
type Edge = tuple[int, int]
type ScalarRow = tuple[int, int, int, int, int, int]
type Coefficients = tuple[tuple[int, int], ...]

TASK_ID = "B649_K20_R3_STATE_14696976_UNIVERSAL_HUNTER_CERTIFICATE_R1"
TASK_BRANCH = "codex/b649-k20-r3-state-14696976-universal-hunter-certificate-r1"
BASE_HEAD = "155ad9f242a14d3e004ac527022219fb30ee5adb"
BASE_TREE = "c420fc8f0679fec55d6ce2bb5a26cab1f669f4bd"
BASE_RESULT_SHA256 = "e36fbc441614b04abd1343f1c82948fc8176db779756190e46c2f0d7a760d075"
R10_HEAD = "b662fe93f2eeb3cac95163b85f82c92dff763ef3"
R10_TREE = "29a0b83293c326073b313e334533e3ca4647c226"
R10_RESULT_SHA256 = "0bf89147aae019ed12961580cb3338ac6a034d88ccf4fcd61caf92907c942db0"
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS = "docs/research/matrix-native-results/"
BASE_RESULT = RESULTS + "b649-k20-r3-r12-root65-joint-certificate-r1-result.json"
R10_RESULT = RESULTS + "b649-k20-r3-canonical-primitive-authority-repair-r10-result.json"
R7_RESULT = RESULTS + "b649-k20-r3-joint-residual-envelope-r7-result.json"
R14_RESULT = RESULTS + "b649-k20-r3-state-tail-owner-chase-r14-result.json"
SOURCE_RELATIVE = "src/lottolab/research/" + Path(__file__).name
TEST_RELATIVE = "tests/unit/test_" + Path(__file__).name
RESULT_RELATIVE = RESULTS + "b649-k20-r3-state-14696976-universal-hunter-certificate-r1-result.json"
RESULT_PATH = REPO_ROOT / RESULT_RELATIVE
STATE_ID = "state:s2-14696976-s3-1059324"
TAIL_ID = "unclassified-tail"
S3_BASE = 18 * 9485
S3_MIN, S3_MAX = 1005537, 1059324
LOSS_CUTOFF = 6695798
DUAL = (39137, 13733226360, 154447)
ROOT_FLOOR = 88830
CORE_FLOORS = (107800, 574000, 1691620, 3451651)
KS = tuple(range(9, 18))
EXPECTED_SCALARS = (
    (9, 14, 6452526, 3193400, 3992870, 354603232),
    (10, 20, 6101624, 3767400, 4478040, 354468964),
    (11, 26, 5750723, 4341400, 4963210, 354334695),
    (12, 32, 5399822, 4915400, 5448380, 354200426),
    (13, 38, 5048920, 5489400, 5933550, 354066158),
    (14, 48, 4698019, 6063400, 6418720, 353931889),
    (15, 60, 4347117, 6637400, 6903890, 353797621),
    (16, 72, 3996216, 7211400, 7389060, 353663352),
    (17, 84, 3645315, 7785400, 7874230, 353529083),
)
FINGERPRINTS = {
    "type_coefficients": "056b4da95a65c093638d1711cc60ac33a8f9ed56f9fd181ab52ca5da9cd80eee",
    "root_rows": "962b184bee791461a3cba3cd2b0f658d5d19e1329e874b0c2c8d5d3206e01242",
    "scalar_rows": "35dd483398035cc0f43871fa9d0f13d1c2782ddd9fbe6ba4828d6e4c6ac6cd5d",
    "existing_family": "be3d4030e2d06dfdb2cf0c5f854be2e1bac80d6fb6cd17b500511c200ea05334",
    "new_family": "a718de0aabe0020d3df831d9891d80c6c7242e8d57d8b14334bb56748f492635",
}


def compact_digest(rows: object) -> str:
    """ASCII compact JSON arrays, no newline; field orders are sealed below."""
    data = json.dumps(rows, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return sha256(data).hexdigest()


def family_digest(terms: Terms) -> str:
    """Predecessor convention: ASCII repr(tuple((stable_id, bound), ...))."""
    return sha256(repr(terms).encode("ascii")).hexdigest()


def git_bytes(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(REPO_ROOT), *args])


@cache
def frozen_blob(head: str, path: str) -> bytes:
    return git_bytes("show", f"{head}:{path}")


def sealed(path: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(frozen_blob(BASE_HEAD, path)))


def verify_source_authority() -> dict[str, Any]:
    identities: dict[str, Any] = {}
    for label, head, tree, path, expected in (
        ("BASE", BASE_HEAD, BASE_TREE, BASE_RESULT, BASE_RESULT_SHA256),
        ("R10", R10_HEAD, R10_TREE, R10_RESULT, R10_RESULT_SHA256),
    ):
        if git_bytes("show", "-s", "--format=%H %T", head).decode().strip() != f"{head} {tree}":
            raise AssertionError("pinned HEAD/TREE mismatch")
        data = frozen_blob(head, path)
        if sha256(data).hexdigest() != expected or (REPO_ROOT / path).read_bytes() != data:
            raise AssertionError("pinned result SHA/byte identity mismatch")
        identities[label] = {"HEAD": head, "TREE": tree, "RESULT_SHA256": expected}
    if subprocess.run(
        ["git", "-C", str(REPO_ROOT), "merge-base", "--is-ancestor", BASE_HEAD, "HEAD"],
        check=False,
    ).returncode:
        raise AssertionError("checkout must descend from BASE")
    # Bind the executed local import closure, not merely predecessor result labels.
    pending = ["lottolab.research.b649_k20_r3_preserved_eleven_hunter_certificate_r1"]
    paths = {BASE_RESULT, R10_RESULT, R7_RESULT, R14_RESULT, *hunter.UPSTREAM_SHA256}
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
        tree = ast.parse(frozen_blob(BASE_HEAD, path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("lottolab"):
                    pending.append(node.module)
                    pending.extend(node.module + "." + a.name for a in node.names)
            elif isinstance(node, ast.Import):
                pending.extend(a.name for a in node.names if a.name.startswith("lottolab"))
    fingerprints: dict[str, str] = {}
    for path in sorted(paths):
        data = frozen_blob(BASE_HEAD, path)
        if (REPO_ROOT / path).read_bytes() != data:
            raise AssertionError(f"immutable predecessor byte identity failed: {path}")
        fingerprints[path] = sha256(data).hexdigest()
    return {
        **identities,
        "predecessor_sha256": fingerprints,
        "implementation_sha256": {
            p: sha256((REPO_ROOT / p).read_bytes()).hexdigest()
            for p in (SOURCE_RELATIVE, TEST_RELATIVE)
        },
    }


def first_dominator(frontier: tuple[tuple[int, int], ...], s2: int, s3: int) -> int:
    return next((i for i, (x, y) in enumerate(frontier) if x <= s2 and y >= s3), -1)


def membership_proof() -> dict[str, Any]:
    source, donor = sealed(R7_RESULT), sealed(R10_RESULT)
    frontier = tuple((r["JOINT_S2"], r["MAXIMUM_JOINT_S3"]) for r in source["S2_S3_FRONTIER"])
    corrected = donor["CORRECTED_LOAD_BEARING_FRONTIER"]
    row = corrected[12]
    if (
        len(frontier) != 23
        or any(a[0] >= b[0] or a[1] >= b[1] for a, b in pairwise(frontier))
        or frontier[11:13] != ((14122976, 1005536), (14696976, S3_MAX))
        or tuple(sorted((r["joint_s2"], r["maximum_joint_s3"]) for r in corrected)) != frontier
        or row["canonical_frontier_rank"] != 13
        or row["refinement_source"] != "R7_EXACT_S2_S3_FRONTIER"
        or row["certified_state_r3_upper_bound"] != 355121046
        or frontier[11][1] + 1 != S3_MIN
        or S3_MIN - S3_BASE != 834807
        or hunter.r7.JOINT_LOCAL_LOSS_CUTOFF != LOSS_CUTOFF
        or source["LOCAL_LOSS_CENSUS_CUTOFF"] != LOSS_CUTOFF
        or hunter.r5.ANCHOR_OVERLAP != 3
        or hunter.family_pair_overlap_ceiling() != 3
    ):
        raise AssertionError("sealed R7/R14 full State membership or strict S3 lower bound failed")
    return {
        "state_id": STATE_ID,
        "frontier": frontier,
        "rank": 13,
        "source_label": row["refinement_source"],
        "rule": "FIRST_DOMINATOR_IN_INCREASING_S2_ORDER",
        "joint_s2_min_inclusive": 14696976,
        "joint_s3_min_inclusive": S3_MIN,
        "joint_s3_max_inclusive": S3_MAX,
        "local_loss_max_inclusive": LOSS_CUTOFF,
        "unchanged_domain_constraints": [
            "R7 aggregate_count_vector_is_feasible(counts)",
            "30 nonnegative integer type counts summing to 18 residual events",
            "anchor overlap=3; all ticket pair overlaps<=3; anchor cells=(3,3,3,40)",
        ],
        "coverage_argument": (
            "At S2>=target.S2 every earlier frontier point is eligible in S2. "
            "Their largest S3 is previous.S3, so first ownership is equivalent to "
            "previous.S3<S3<=target.S3 within the unchanged R7 feasible domain."
        ),
        "complete_region_ledger_used": False,
    }


def ceil_div(numerator: int, denominator: int) -> int:
    if type(numerator) is not int or type(denominator) is not int or denominator <= 0:
        raise ValueError("exact integers and a positive denominator required")
    return -(-numerator // denominator)


def loss_floor(k: int) -> int:
    a, b, c = DUAL
    return ceil_div((18 - k) * b + c * (S3_MIN - S3_BASE), a)


def validate_coefficients(
    coefficients: Coefficients, exclude_type29: bool = True
) -> tuple[int, ...]:
    if len(coefficients) != 30 or not exclude_type29:
        raise AssertionError("all 30 types and type29 exclusion required")
    if coefficients[0] != (0, 0) or any(x < 0 or ell < 0 for x, ell in coefficients):
        raise AssertionError("type0 baseline/nonnegative coefficients failed")
    if coefficients[29][0] != 1576204 or S3_BASE + coefficients[29][0] <= S3_MAX:
        raise AssertionError("type29 must exceed the formal State S3 ceiling")
    if DUAL != (39137, 13733226360, 154447):
        raise AssertionError("loss dual coefficients changed")
    a, b, c = DUAL
    slacks = tuple(a * ell - b - c * x for x, ell in coefficients[1:29])
    if len(slacks) != 28 or min(slacks) < 0:
        raise AssertionError("a nonzero type violates the universal loss dual")
    if compact_digest(coefficients) != FINGERPRINTS["type_coefficients"]:
        raise AssertionError("type coefficient digest failed")
    return slacks


def type_proof() -> dict[str, Any]:
    profiles = hunter.r5.anchor_incidence_profiles()
    coefficients = tuple(
        (p.triple_recovery - 9485, p.pair_recovery_cost - p.triple_recovery - 206115)
        for p in profiles
    )
    slacks = validate_coefficients(coefficients)
    recounted: list[dict[str, Any]] = []
    for i, p in enumerate(profiles):
        cells = hunter.type_cells(i)
        ticket = hunter.realize_pair(cells, cells, cells)[0]
        triple = hunter.outcome_count((ticket, hunter.ANCHOR_A, hunter.ANCHOR_B))
        pair_cost = sum(
            hunter.outcome_count((ticket, a)) for a in (hunter.ANCHOR_A, hunter.ANCHOR_B)
        )
        if triple != p.triple_recovery or pair_cost != p.pair_recovery_cost:
            raise AssertionError("30 type coefficient incidence-DP recount failed")
        recounted.append({"type": i, "cells": cells, "j": triple, "anchor_pair_cost": pair_cost})
    excluded = tuple((k, loss_floor(k)) for k in range(9))
    if any(floor <= LOSS_CUTOFF for _, floor in excluded) or S3_BASE >= S3_MIN:
        raise AssertionError("k<=8 loss contradiction or k=18 S3 contradiction failed")
    return {
        "coefficient_fields": ["x", "ell"],
        "coefficients": coefficients,
        "coefficient_sha256": compact_digest(coefficients),
        "recounted_types": recounted,
        "dual": DUAL,
        "dual_slacks_types_1_through_28": slacks,
        "type29_minimum_S3": S3_BASE + coefficients[29][0],
        "type29_excluded": True,
        "S3_baseline": S3_BASE,
        "required_x_sum": S3_MIN - S3_BASE,
        "excluded_k_loss_floors": excluded,
        "k18_S3": S3_BASE,
        "universal_k_range": KS,
        "coverage_argument": (
            "All legal counts have type29=0. Summing all 28 dual inequalities "
            "gives the exact ceil loss floor for every k. k<=8 exceeds the R7 "
            "cutoff; k=18 misses the strict S3 floor. Hence every realization has 9<=k<=17."
        ),
    }


def require_root_floor(floor: int, rows: tuple[hunter.PairRow, ...]) -> None:
    if type(floor) is not int or floor < 0 or len(rows) != 105 or min(r[6] for r in rows) < floor:
        raise AssertionError("unsafe residual root floor or incomplete 105-row coverage")


def root_pair_proof() -> dict[str, Any]:
    rows = hunter.exact_pair_rows(tuple((0, i) for i in range(30)))
    expected_keys = tuple(
        (0, i, *cells)
        for i in range(30)
        for cells in hunter.feasible_cell_overlaps(hunter.type_cells(0), hunter.type_cells(i))
    )
    if tuple(r[:6] for r in rows) != expected_keys:
        raise AssertionError("complete legal root type/cell-overlap coverage failed")
    require_root_floor(ROOT_FLOOR, rows)
    packed = tuple((r[1], r[5], r[6]) for r in rows)
    if compact_digest(packed) != FINGERPRINTS["root_rows"]:
        raise AssertionError("root row digest failed")
    counts: list[dict[str, Any]] = []
    for a, b, s, x, y, z, value in rows:
        cells = (s, x, y, z)
        tickets = hunter.realize_pair(hunter.type_cells(a), hunter.type_cells(b), cells)
        raw = hunter.outcome_count(tickets)
        ta = hunter.outcome_count((*tickets, hunter.ANCHOR_A))
        tb = hunter.outcome_count((*tickets, hunter.ANCHOR_B))
        quad = hunter.outcome_count((*tickets, hunter.ANCHOR_A, hunter.ANCHOR_B))
        residual = hunter.outcome_count(tickets, (hunter.ANCHOR_A, hunter.ANCHOR_B))
        if (
            raw - ta - tb + quad != residual
            or residual != value
            or hunter.six.residual_pair_intersection(a, b, cells) != value
            or (s, x, y) != (0, 0, 0)
        ):
            raise AssertionError("raw E pair cannot replace the recounted residual R intersection")
        counts.append(
            {
                "type": b,
                "outside_overlap": z,
                "raw_E": raw,
                "triple_A": ta,
                "triple_B": tb,
                "quadruple": quad,
                "residual_R": residual,
            }
        )
    core_rows = tuple(r for r in rows if r[1] == 0)
    if tuple(r[6] for r in core_rows) != CORE_FLOORS:
        raise AssertionError("type0 core residual pair floors changed")
    hunter.require_safe_pair_floors(CORE_FLOORS, core_rows)
    return {
        "fields": ["type", "outside_overlap", "residual_R_pair"],
        "rows": packed,
        "full_rows": rows,
        "row_counts": counts,
        "row_count": len(rows),
        "type_count": 30,
        "rows_sha256": compact_digest(packed),
        "root_residual_floor": ROOT_FLOOR,
        "core_residual_floors": CORE_FLOORS,
    }


def validate_tree_extension(
    indices: tuple[int, ...], core: tuple[Edge, ...], attachments: tuple[Edge, ...]
) -> tuple[Edge, ...]:
    chosen = set(indices)
    full = (*core, *attachments)
    if (
        len(indices) not in KS
        or len(chosen) != len(indices)
        or not chosen <= set(range(18))
        or len(core) != len(indices) - 1
        or any(a not in chosen or b not in chosen or a == b for a, b in core)
        or hunter.graph_rank(18, core) != len(core)
        or len(attachments) != 18 - len(indices)
        or set(attachments) != {(indices[0], j) for j in range(18) if j not in chosen}
        or len({frozenset(e) for e in full}) != 17
        or hunter.graph_rank(18, full) != 17
    ):
        raise AssertionError("one disjoint connected acyclic 18-vertex 17-edge tree required")
    return full


def scalar_proof() -> dict[str, Any]:
    if tuple(range(9, 18)) != KS:
        raise AssertionError("all nine legal k values required")
    single = hunter.r14.canonical_primitives()["SINGLE_TICKET_ANY_PRIZE"]
    constant = hunter.r14.joint_constant() - 18 * 206115
    if single != 18611432 or constant != 365048628:
        raise AssertionError("canonical loss baseline failed")
    rows: list[ScalarRow] = []
    cores: list[dict[str, Any]] = []
    for k in KS:
        q, r = divmod(6 * k, 40)
        mass = (40 - r) * comb(q, 2) + r * comb(q + 1, 2)
        if mass != hunter.balanced_collision_mass(6 * k, 40):
            raise AssertionError("balanced collision floor failed")
        minimum = hunter.minimum_tree_correction(CORE_FLOORS, mass, k)
        loss = loss_floor(k)
        correction = minimum.correction + (18 - k) * ROOT_FLOOR
        rows.append((k, mass, loss, minimum.correction, correction, constant - loss - correction))
        indices = tuple(range(k))
        core = tuple((j - 1, j) for j in range(1, k))
        attachments = tuple((0, j) for j in range(k, 18))
        validate_tree_extension(indices, core, attachments)
        ranks = tuple(hunter.rank_floor(e) for e in range(comb(k, 2) + 1))
        if any(
            comb(rank + 1, 2) < e or (rank and comb(rank, 2) >= e) for e, rank in enumerate(ranks)
        ):
            raise AssertionError("exact rank floor failed")
        cores.append(
            {
                "k": k,
                "outside_incidences": 6 * k,
                "outside_label_capacity": 40,
                "balanced_frequencies": ((q, 40 - r), (q + 1, r)),
                "Q": mass,
                "threshold_case_count": minimum.census_size,
                "all_nested_case_count": comb(comb(k, 2) + 3, 3),
                "rejected_collision_case_count": comb(comb(k, 2) + 3, 3) - minimum.census_size,
                "minimizer_edges": minimum.edge_counts,
                "minimizer_ranks": minimum.rank_floors,
                "rank_floor_table": ranks,
                "H": minimum.correction,
                "attachment_count": 18 - k,
                "C": correction,
                "extension_topology_example": {"core": core, "attachments": attachments},
                "witness_scope": "TOPOLOGY_ONLY; NOT_A_REALIZATION_OR_A_UNIVERSALITY_PREMISE",
            }
        )
    packed = tuple(rows)
    if packed != EXPECTED_SCALARS or compact_digest(packed) != FINGERPRINTS["scalar_rows"]:
        raise AssertionError("all nine exact loss/Hunter/correction/bound rows required")
    all_nested = sum(p["all_nested_case_count"] for p in cores)
    admissible = sum(p["threshold_case_count"] for p in cores)
    if (all_nested, admissible) != (1273815, 1229966):
        raise AssertionError("pre-filter versus admissible threshold case accounting failed")
    return {
        "fields": ["k", "Q", "L", "H", "C", "state_upper_bound"],
        "rows": packed,
        "rows_sha256": compact_digest(packed),
        "cores": cores,
        "case_count_audit": {
            "all_nested_domain": "C(k,2)>=e1>=e2>=e3>=0; no collision-sum filter",
            "all_nested_count_formula": "SUM_k C(C(k,2)+3,3), k=9..17",
            "all_nested_count": all_nested,
            "admissible_domain": "all_nested_domain AND e1+e2+e3>=Q_k",
            "admissible_count": admissible,
            "rejected_by_collision_sum": all_nested - admissible,
            "reported_research_count": 1273815,
            "arithmetic_status": "VERIFIED_BOTH_DOMAINS; REPORTED_COUNT_EQUALS_PRE_FILTER_COUNT",
            "historical_script_status": "UNAVAILABLE; HISTORICAL_COUNTING_METHOD_NOT_ATTESTED",
        },
        "constant": constant,
        "universal_state_bound": max(r[5] for r in rows),
        "tree_argument": (
            "Descending Kruskal supplies a core tree attaining all nested threshold ranks. "
            "For ANY such core tree and chosen type0 root, every omitted vertex is a new "
            "leaf. Core/attachment edges are disjoint, connected, acyclic: 18 vertices, "
            "17 edges. H+(18-k)*88830 sums floors on this single residual-event tree."
        ),
    }


def combine_corrections(credits: Mapping[str, int]) -> int:
    if not credits or any(type(c) is not int or c < 0 for c in credits.values()):
        raise ValueError("nonempty nonnegative integer credits required")
    return max(credits.values())


def adopt_state_bound(existing: int, universal: int) -> int:
    return min(existing, universal)


def family_terms() -> Terms:
    source = sealed(BASE_RESULT)
    states = tuple((str(r["stable_id"]), int(r["bound"])) for r in source["FINAL_STATE_TERMS"])
    classified = tuple(
        (str(r["stable_id"]), int(r["bound"])) for r in source["FINAL_CLASSIFIED_TERMS"]
    )
    terms = (*states, *classified, (TAIL_ID, int(source["TAIL_BOUND"])))
    if (len(states), len(classified), len(terms), len(dict(terms))) != (23, 56550, 56574, 56574):
        raise AssertionError("all 56574 distinct State/Classified/Tail terms required")
    if family_digest(terms) != FINGERPRINTS["existing_family"]:
        raise AssertionError("sealed existing Family digest failed")
    return terms


def replace_state(terms: Terms, universal: int) -> Terms:
    sealed_terms = family_terms()
    if terms != sealed_terms:
        raise AssertionError("non-target State/Classified/Tail terms must remain unchanged")
    existing = dict(terms)[STATE_ID]
    adopted = adopt_state_bound(existing, universal)
    if adopted != min(existing, universal):
        raise AssertionError("State-bound MIN required; independent certificates cannot SUM")
    updated = tuple((key, adopted if key == STATE_ID else bound) for key, bound in terms)
    if sum(a != b for a, b in zip(terms, updated, strict=True)) != 1:
        raise AssertionError("replace exactly one target State term")
    if family_digest(updated) != FINGERPRINTS["new_family"]:
        raise AssertionError("new Family digest failed")
    return updated


def build_result() -> dict[str, Any]:
    authority = verify_source_authority()
    membership = membership_proof()
    coefficients = type_proof()
    root = root_pair_proof()
    scalar = scalar_proof()
    universal = int(scalar["universal_state_bound"])
    terms = family_terms()
    updated = replace_state(terms, universal)
    ordered = sorted(updated, key=lambda r: (-r[1], r[0]))
    owner, maximum = ordered[0]
    runner, runner_bound = ordered[1]
    prior = max(b for _, b in terms)
    if (universal, maximum, prior - maximum, maximum - 313263888) != (
        354603232,
        355116818,
        4228,
        41852930,
    ) or (owner, runner, runner_bound) != (
        "state:s2-13548976-s3-951748",
        "state:s2-13169800-s3-789320",
        355112590,
    ):
        raise AssertionError("complete Family maximum/owner/runner-up failed")
    return cast(
        dict[str, Any],
        json.loads(
            json.dumps(
                {
                    "TASK_ID": TASK_ID,
                    "TASK_STATUS": "SUCCESS",
                    "TASK_BRANCH": TASK_BRANCH,
                    "MODEL": "最強模型",
                    "REMAINING_TASK_MODEL": "最強模型",
                    "MODEL_LABEL_SOURCE": "OWNER_REQUEST; NOT_A_RUNTIME_MODEL_ATTESTATION",
                    "BASE_HEAD": BASE_HEAD,
                    "BASE_TREE": BASE_TREE,
                    "R10_HEAD": R10_HEAD,
                    "R10_TREE": R10_TREE,
                    "SOURCE_AUTHORITY": authority,
                    "STATE_MEMBERSHIP_PROOF": membership,
                    "TYPE_COEFFICIENT_PROOF": coefficients,
                    "ROOT_PAIR_PROOF": root,
                    "HUNTER_NINE_ROW_PROOF": scalar,
                    "NEW_STATE_14696976_UB": universal,
                    "SEALED_EXISTING_STATE_BOUND": dict(terms)[STATE_ID],
                    "ADOPTED_STATE_BOUND": dict(updated)[STATE_ID],
                    "CORRECTION_COMBINATION": "MAX_ONLY; STATE_BOUND_MIN; REPLACE_TARGET_ONCE",
                    "NO_DOUBLE_COUNT_STATUS": "PASS; NO_MEMBER_CREDIT_RECORDS_CREATED",
                    "PRESERVED_FAMILY_TERMS": 56573,
                    "FAMILY_TERM_COUNT": len(updated),
                    "EXISTING_FAMILY_TERMS_SHA256": family_digest(terms),
                    "NEW_FAMILY_TERMS_SHA256": family_digest(updated),
                    "FINAL_STATE_TERMS": [{"stable_id": k, "bound": b} for k, b in updated[:23]],
                    "FINAL_CLASSIFIED_TERMS": [
                        {"stable_id": k, "bound": b} for k, b in updated[23:-1]
                    ],
                    "CLASSIFIED_MAX": max(b for _, b in updated[23:-1]),
                    "TAIL_BOUND": updated[-1][1],
                    "START_COMPLETE_R3_UB": prior,
                    "FINAL_COMPLETE_R3_UB": maximum,
                    "FINAL_OWNER": owner,
                    "RUNNER_UP": {"stable_id": runner, "bound": runner_bound},
                    "STRICT_GAIN": prior - maximum,
                    "INCUMBENT": 313263888,
                    "REMAINING_GAP": maximum - 313263888,
                    "RESEARCH_FINGERPRINTS": FINGERPRINTS,
                    "CANONICAL_SERIALIZATION": {
                        "research": "ASCII JSON compact arrays; separators=(',',':'); no newline",
                        "type_fields": ["x", "ell"],
                        "root_fields": ["type", "outside_overlap", "residual_R_pair"],
                        "scalar_fields": ["k", "Q", "L", "H", "C", "state_upper_bound"],
                        "family": "ASCII repr(tuple((stable_id, bound), ...)); sealed ordering",
                        "result": (
                            "UTF8 JSON sort_keys=True indent=2 ensure_ascii=False plus newline"
                        ),
                    },
                    "WITNESS_APPLICABILITY": "NO_REALIZATION_WITNESS_USED; UNIVERSAL_DOMAIN_PROOF",
                    "COMPLETE_REGION_LEDGER_USED": False,
                    "OWNER_REGION_CALLS": 0,
                    "R7_CENSUS_CALLS": 0,
                    "NEW_HEAVY_SOLVER_STARTED": False,
                    "OFFICIAL_OUTCOME_ENUMERATION_USED": False,
                    "PRODUCTION_MUTATION": "NONE",
                    "PUSH_PR_MERGE": "NONE",
                    "JUDGE_MODE": "SELF_CHECK_ONLY",
                    "WORKTREE_DISPOSITION": "RETAIN",
                }
            )
        ),
    )


def encode(result: dict[str, Any]) -> str:
    return json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def verify_result(result: dict[str, Any]) -> dict[str, Any]:
    if result != build_result():
        raise AssertionError("certificate differs from deterministic replay/source binding")
    return {"status": "PASS", "family_terms": 56574, "root_rows": 105, "k_rows": 9}


def verify_stored_result() -> dict[str, Any]:
    stored = RESULT_PATH.read_bytes()
    result = cast(dict[str, Any], json.loads(stored))
    status = verify_result(result)
    if stored != encode(result).encode():
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
                key: result[key]
                for key in (
                    "TASK_STATUS",
                    "NEW_STATE_14696976_UB",
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
