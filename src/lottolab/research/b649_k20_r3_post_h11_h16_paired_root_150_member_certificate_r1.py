"""Adopt Paired Root for 150 sealed members, including all 170 vectors.

Every event is R_i = E_i minus (E_A union E_B). Pair counts below are
residual intersections, recounted by cell-count dynamic programming and
inclusion-exclusion; no official-outcome enumeration is needed.

For n type-0 events, 6n incidences occupy 40 outside labels. Smoothing
a>=b+2 to a-1,b+1 decreases sum C(d,2) by a-b-1. The balanced minimum Q
therefore bounds the collision mass e1+e2+e3. A graph with component ranks
r_j has e<=sum C(r_j+1,2)<=C(sum r_j+1,2), so rank>=rho(e).
Descending Kruskal spans all nested threshold graphs simultaneously.
One common core tree thus weighs at least
(n-1)phi0 + sum (phi_j-phi_{j-1})rho(e_j).

Select any core vertex as root and attach each omitted event once as a
new leaf. Core and attachment edges are disjoint; there are 18 vertices
and 17 distinct edges. Each legal residual root pair has its type-specific
floor, so core and leaf floors add ON THIS SAME TREE. For each outcome
with m present events, the induced tree is a forest with at most m-1
edges (zero if m=0). Consequently 1_union <= sum 1_R - sum_tree 1_pair
pointwise, proving the universal Hunter inequality by integration.

Different certificates combine by MAX, with one subtraction. Every
compressed member MAXes all represented-vector safe bounds. Predecessor
certificates are consumed as immutable data, never rebuilt or readopted.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import replace
from functools import cache
from hashlib import sha256
from itertools import combinations
from math import comb
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_r3_post_h13_two_state_h11_h16_14_member_r1 as prior
from lottolab.research import b649_k20_r3_preserved_eleven_hunter_certificate_r1 as hunter

catalog, h13, root65 = prior.catalog, prior.h13, prior.root65
dense, sparse, member_id = prior.dense, prior.sparse, prior.member_id
encode, digest, family_digest = prior.encode, prior.digest, prior.family_digest
type CountVector = tuple[int, ...]
type Edge = tuple[int, int]
type Terms = tuple[tuple[str, int], ...]
TASK_ID = "B649_K20_R3_POST_H11_H16_PAIRED_ROOT_150_MEMBER_ADOPTION_R1"
TASK_BRANCH = "codex/b649-k20-r3-post-h11-h16-paired-root-150-member-adoption-r1"
BASE_HEAD = "75e30e7b87cce7384ec1ba591061ae53b2e4c8a7"
BASE_TREE = "26479c39a0f23be7dc9e19282e68de4c013e7ced"
BASE_RESULT_SHA256 = "1f9ae1717c6770bb3d5fe5f1fb23cdcbecd82b31c4c6194d0fd4e3adc7697a1d"
REPO_ROOT = Path(__file__).resolve().parents[3]
BASE_RESULT = prior.RESULT_RELATIVE
SOURCE_RELATIVE = "src/lottolab/research/" + Path(__file__).name
TEST_RELATIVE = "tests/unit/test_" + Path(__file__).name
RESULT_RELATIVE = h13.RESULTS + (
    "b649-k20-r3-post-h11-h16-paired-root-150-member-certificate-r1-result.json"
)
RESULT_PATH = REPO_ROOT / RESULT_RELATIVE
STATE_A, STATE_B = h13.STATE_ID, prior.STATE_B
FINAL_OWNER = "state:s2-12692531-s3-681744"
# members, vectors, target members, target vectors, old bound, remainder max, target max.
SPECS = {
    STATE_A: (1427, 1543, 80, 90, 355110434, 355051410, 354142257),
    STATE_B: (1222, 1325, 70, 80, 355107928, 355060310, 354246046),
}
REGION_HASHES = {
    STATE_A: "1eed0fb9bc975d825d42413dd07ebfad5296d00185118850a38512c8a94e1f63",
    STATE_B: "46023fc93f2fd7d9b211d29494d05d8f6bfd4867992b0121cd8db0b7def5cd5b",
}
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
}
# collision floor, minimum forest rank at e1=Q, universal Hunter minimum.
CORE_SPECS = {
    10: (20, 6, 3767400),
    11: (26, 7, 4341400),
    12: (32, 8, 4915400),
    13: (38, 9, 5489400),
}
# compressed members, represented vectors, core size, root-extended credit.
COHORT_SPECS = {
    "A1": (10, 10, 12, 5558000),
    "A2": (35, 40, 10, 4627560),
    "A3": (35, 40, 10, 4627560),
    "B1": (40, 40, 10, 4627560),
    "B2": (18, 24, 11, 5091520),
    "B3": (12, 16, 13, 6026160),
}
EXPECTED_FAMILY_DIGEST = "37f97730c6f223ca1a9458a6f01822788ba0e81f57da6f71e4989b621857f1e7"


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
    """Predecessor's transitive import/data closure plus consumed test modules."""
    return tuple(
        sorted(
            {
                BASE_RESULT,
                prior.SOURCE_RELATIVE,
                prior.TEST_RELATIVE,
                h13.SOURCE_RELATIVE,
                h13.TEST_RELATIVE,
                root65.TEST_RELATIVE,
                "tests/unit/test_b649_k20_r3_state_14696976_universal_hunter_certificate_r1.py",
                "tests/unit/test_b649_k20_r3_ts153_four_state_wall_adoption_r2.py",
                *prior.source_paths(),
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
            vector({0: 12, 1: j, 4: 4 - j, c: 1, 20: 1}) for j in range(5) for c in (5, 16)
        ),
        "A2": tuple(
            vector({0: 10, 1: j, 4: 3 - j, 5: k, 16: 4 - k, a: 1})
            for j in range(4)
            for k in range(5)
            for a in (6, 9)
        ),
        "A3": tuple(
            vector({0: 10, 1: j, 4: 3 - j, 5: k, 16: 4 - k, t: 1})
            for j in range(4)
            for k in range(5)
            for t in (17, 19)
        ),
        "B1": tuple(
            vector({0: 10, 1: j, 4: 3 - j, 5: k, 16: 4 - k, a: 1})
            for j in range(4)
            for k in range(5)
            for a in (2, 8)
        ),
        "B2": tuple(
            vector({0: 11, 1: j, 4: 5 - j, a: 1, b: 1})
            for j in range(6)
            for a in (6, 9)
            for b in (17, 19)
        ),
        "B3": tuple(
            vector({0: 13, 1: j, 4: 1 - j, 5: k, 16: 3 - k, t: 1})
            for j in range(2)
            for k in range(4)
            for t in (17, 19)
        ),
    }
    flat = [v for vs in groups.values() for v in vs]
    if len(flat) != len(set(flat)) or len(flat) != 170:
        raise AssertionError("exact six disjoint parameterized families required")
    for name, vs in groups.items():
        if len(vs) != COHORT_SPECS[name][1]:
            raise AssertionError("exact cohort vector cardinality required")
        for v in vs:
            validate_counts(v, COHORT_SPECS[name][2])
    return groups


def validate_counts(v: CountVector, n: int) -> None:
    if (
        n not in CORE_SPECS
        or len(v) != 30
        or sum(v) != 18
        or v[0] != n
        or any(type(c) is not int or c < 0 for c in v)
        or any(c and i not in ROOT_FLOORS for i, c in enumerate(v))
    ):
        raise AssertionError("legal integer 18-event counts and type-0 core required")


@cache
def region_rows(state_id: str) -> tuple[dict[str, Any], ...]:
    if state_id == STATE_A:
        rows = tuple(
            cast(list[dict[str, Any]], sealed(h13.RESULT_RELATIVE)["COMPLETE_REGION_MEMBERS"])
        )
    elif state_id == STATE_B:
        regions = [r for r in sealed(BASE_RESULT)["REGIONS"] if r["state_id"] == state_id]
        if len(regions) != 1:
            raise AssertionError("one sealed complete State B region required")
        rows = tuple(cast(list[dict[str, Any]], regions[0]["complete_region_members"]))
    else:
        raise AssertionError("only the two authorized State regions")
    mc, vc, _, _, old, _, _ = SPECS[state_id]
    fingerprint = catalog.digest(tuple((dense(r["witness_counts"]), r["raw_bound"]) for r in rows))
    if (
        len(rows),
        len({r["member_id"] for r in rows}),
        sum(r["represented_vector_count"] for r in rows),
        max(r["final_bound"] for r in rows),
        fingerprint,
    ) != (mc, mc, vc, old, REGION_HASHES[state_id]):
        raise AssertionError("complete sealed region coverage/fingerprint failed")
    return rows


@cache
def vector_rows(state_id: str) -> dict[CountVector, dict[str, Any]]:
    rows = (
        sealed(h13.RESULT_RELATIVE)["COMPLETE_VECTOR_BOUNDS"]
        if state_id == STATE_A
        else [v for r in region_rows(state_id) for v in r["represented_vector_bounds"]]
    )
    found = {dense(r["counts"]): r for r in rows}
    if len(found) != len(rows) or len(found) != SPECS[state_id][1]:
        raise AssertionError("complete unique sealed vector bounds required")
    return found


@cache
def region_vectors(state_id: str) -> dict[CountVector, tuple[CountVector, ...]]:
    recovered: dict[CountVector, tuple[CountVector, ...]] = {}
    vr = vector_rows(state_id)
    for row in region_rows(state_id):
        v = dense(row["witness_counts"])
        member = catalog.LedgerMember(
            v, row["represented_vector_count"], row["raw_bound"], row["final_bound"]
        )
        state = catalog.rebuild_member(member)
        signature = hunter.eleven.compression_signature(state)
        vectors = tuple(dense(x) for x in row["represented_vectors"])
        if (
            not vectors
            or vectors != tuple(sorted(set(vectors)))
            or min(vectors) != v
            or len(vectors) != member.represented_vector_count
            or member_id(v) != row["member_id"]
            or catalog.normalized(signature) != row["compression_signature"]
            or max(vr[x]["final_bound"] for x in vectors) != member.final_bound
        ):
            raise AssertionError("canonical member/compression signature/MAX identity failed")
        for x in vectors:
            rebuilt = catalog.rebuild_member(replace(member, counts=x, represented_vector_count=1))
            if (
                len(x) != 30
                or sum(x) != 18
                or any(type(c) is not int or c < 0 for c in x)
                or hunter.eleven.compression_signature(rebuilt) != signature
                or hunter.r14.raw_bound(rebuilt) != member.raw_bound
                or vr[x]["final_bound"] > member.final_bound
            ):
                raise AssertionError("represented-vector signature or prior bound failed")
        recovered[v] = vectors
    flat = [v for vs in recovered.values() for v in vs]
    if len(flat) != len(set(flat)) or set(flat) != set(vr):
        raise AssertionError("complete represented-vector coverage failed")
    return recovered


def target_rows(state_id: str) -> tuple[dict[str, Any], ...]:
    recovered = region_vectors(state_id)
    expected = {
        v
        for name, vs in cohorts().items()
        if name[0] == ("A" if state_id == STATE_A else "B")
        for v in vs
    }
    rows = tuple(
        r
        for r in region_rows(state_id)
        if expected.intersection(recovered[dense(r["witness_counts"])])
    )
    actual = {v for r in rows for v in recovered[dense(r["witness_counts"])]}
    if (len(rows), len(actual)) != SPECS[state_id][2:4] or actual != expected:
        raise AssertionError("complete target members and every represented alias required")
    for name, vs in cohorts().items():
        if name[0] == ("A" if state_id == STATE_A else "B"):
            groups = [
                r for r in rows if set(vs).intersection(recovered[dense(r["witness_counts"])])
            ]
            if len(groups) != COHORT_SPECS[name][0] or any(
                not set(recovered[dense(r["witness_counts"])]).issubset(vs) for r in groups
            ):
                raise AssertionError("cohort canonical member identities/cardinalities failed")
    return rows


@cache
def alias_pairs() -> dict[str, tuple[tuple[CountVector, CountVector], ...]]:
    return {
        "A2": tuple(
            (
                vector({0: 10, 1: 1, 4: 2, 5: k, 16: 4 - k, 6: 1}),
                vector({0: 10, 1: 2, 4: 1, 5: k, 16: 4 - k, 9: 1}),
            )
            for k in range(5)
        ),
        "A3": tuple(
            (
                vector({0: 10, 1: 1, 4: 2, 5: k, 16: 4 - k, 17: 1}),
                vector({0: 10, 1: 2, 4: 1, 5: k, 16: 4 - k, 19: 1}),
            )
            for k in range(5)
        ),
        "B2": tuple(
            (
                vector({0: 11, 1: j, 4: 5 - j, 9: 1, 17: 1}),
                vector({0: 11, 1: j, 4: 5 - j, 6: 1, 19: 1}),
            )
            for j in range(6)
        ),
        "B3": tuple(
            (
                vector({0: 13, 4: 1, 5: k, 16: 3 - k, 17: 1}),
                vector({0: 13, 1: 1, 5: k, 16: 3 - k, 19: 1}),
            )
            for k in range(4)
        ),
    }


def verify_aliases() -> dict[str, Any]:
    records: dict[str, Any] = {}
    for name, pairs in alias_pairs().items():
        lookup = {
            v: canonical
            for canonical, vs in region_vectors(STATE_A if name[0] == "A" else STATE_B).items()
            for v in vs
        }
        for a, b in pairs:
            if a == b or lookup.get(a) != min(a, b) or lookup.get(b) != min(a, b):
                raise AssertionError("independently recovered alias/canonical identity failed")
        records[name] = [
            {"canonical": sparse(min(a, b)), "vectors": [sparse(a), sparse(b)]} for a, b in pairs
        ]
    if sum(map(len, records.values())) != 20:
        raise AssertionError("all twenty additional represented aliases required")
    return records


def validate_root_rows(rows: tuple[hunter.PairRow, ...], floors: dict[int, int]) -> None:
    keys = tuple((0, t, 0, 0, 0, z) for t in ROOT_FLOORS for z in range(4))
    if (
        len(rows) != 48
        or tuple(r[:6] for r in rows) != keys
        or floors != ROOT_FLOORS
        or tuple(r[6] for r in rows[:4]) != FLOORS
        or any(type(f) is not int or f < 0 for f in floors.values())
        or any(min(r[6] for r in rows if r[1] == t) != f for t, f in floors.items())
    ):
        raise AssertionError("48 exact residual rows/type-specific root floors required")


@cache
def root_pair_proof() -> dict[str, Any]:
    if hunter.type_cells(0) != (0, 0, 0, 6) or hunter.family_pair_overlap_ceiling() != 3:
        raise AssertionError("type-0 core incidence/overlap domain failed")
    rows = hunter.exact_pair_rows(tuple((0, t) for t in ROOT_FLOORS))
    validate_root_rows(rows, ROOT_FLOORS)
    recount: list[dict[str, Any]] = []
    for a, b, s, x, y, z, value in rows:
        cells = (s, x, y, z)
        tickets = hunter.realize_pair(hunter.type_cells(a), hunter.type_cells(b), cells)
        raw = hunter.outcome_count(tickets)
        ta = hunter.outcome_count((*tickets, hunter.ANCHOR_A))
        tb = hunter.outcome_count((*tickets, hunter.ANCHOR_B))
        quad = hunter.outcome_count((*tickets, hunter.ANCHOR_A, hunter.ANCHOR_B))
        residual = hunter.outcome_count(tickets, (hunter.ANCHOR_A, hunter.ANCHOR_B))
        if (
            raw - ta - tb + quad != value
            or residual != value
            or hunter.six.residual_pair_intersection(a, b, cells) != value
            or tuple(len(tickets[0] & tickets[1] & set(c)) for c in hunter.CELL_LABELS) != cells
        ):
            raise AssertionError("raw E cannot replace true residual R inclusion-exclusion")
        recount.append(
            {
                "types": (a, b),
                "cells": cells,
                "raw_E": raw,
                "triple_A": ta,
                "triple_B": tb,
                "quadruple": quad,
                "residual_R": residual,
            }
        )
    return {
        "rows": rows,
        "row_count": len(rows),
        "root_floors": ROOT_FLOORS,
        "core_floors": FLOORS,
        "recount": recount,
        "universal_argument": __doc__,
    }


@cache
def core_proof(n: int) -> dict[str, Any]:
    if n not in CORE_SPECS:
        raise AssertionError("only H10/H11/H12/H13 minima authorized")
    root_pair_proof()
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
    ) or minimum.correction != (n - 1) * FLOORS[0] + rank * (FLOORS[1] - FLOORS[0]):
        raise AssertionError("complete exact threshold Hunter minimum failed")
    hunter.verify_rank_floor_algebra(n)
    return {
        "event_count": n,
        "outside_labels": 40,
        "outside_incidences": 6 * n,
        "balanced_frequencies": ((q, 40 - r), (q + 1, r)),
        "collision_floor": collision,
        "threshold_cases": minimum.census_size,
        "minimizer": minimum.edge_counts,
        "ranks": minimum.rank_floors,
        "hunter_floor": minimum.correction,
        "rank_floor_table": [hunter.rank_floor(e) for e in range(comb(n, 2) + 1)],
        "universal_argument": __doc__,
    }


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
        raise AssertionError("disjoint core/attachment 18-vertex 17-edge tree required")
    return full


def root_credit(name: str, v: CountVector) -> int:
    _, _, n, expected = COHORT_SPECS[name]
    validate_counts(v, n)
    if v not in cohorts()[name]:
        raise AssertionError("exact cohort applicability required")
    credit = int(core_proof(n)["hunter_floor"]) + sum(
        c * ROOT_FLOORS[t] for t, c in enumerate(v) if t and c
    )
    if credit != expected:
        raise AssertionError("exact core plus leaf floor credit failed")
    return credit


@cache
def witness_analysis(v: CountVector) -> dict[str, Any]:
    n = v[0]
    validate_counts(v, n)
    support = h13.ts53.prior.legal_support(v)
    if not hunter.r8.validate_support_assignment(v, support):
        raise AssertionError("legal support witness failed")
    tickets = tuple(frozenset(t) for t in support)
    types = tuple(i for i, c in enumerate(v) for _ in range(c))
    overlaps = {(a, b): len(tickets[a] & tickets[b]) for a, b in combinations(range(n), 2)}
    core = hunter.threshold_tree(n, overlaps)
    attachments = tuple((0, j) for j in range(n, 18))
    full = validate_tree_extension(tuple(range(n)), core, attachments)
    values = {(r[0], r[1], tuple(r[2:6])): r[6] for r in root_pair_proof()["rows"]}
    costs: list[int] = []
    for a, b in full:
        cells = tuple(len(tickets[a] & tickets[b] & set(c)) for c in hunter.CELL_LABELS)
        cost = values[(types[a], types[b], cells)]
        if (a, b) in attachments and cost < ROOT_FLOORS[types[b]]:
            raise AssertionError("attachment residual floor failed")
        costs.append(cost)
    proof = core_proof(n)
    mass = sum(comb(sum(x in t for t in tickets[:n]), 2) for x in hunter.CELL_LABELS[3])
    e = tuple(sum(w >= k for w in overlaps.values()) for k in range(1, 4))
    ranks = tuple(
        hunter.graph_rank(n, (edge for edge, w in overlaps.items() if w >= k)) for k in range(1, 4)
    )
    root_floor = int(proof["hunter_floor"]) + sum(ROOT_FLOORS[t] for t in types[n:])
    if (
        mass != sum(overlaps.values())
        or mass != sum(e)
        or mass < proof["collision_floor"]
        or any(r < hunter.rank_floor(c) for r, c in zip(ranks, e, strict=True))
        or any(sum(overlaps[edge] >= k for edge in core) != ranks[k - 1] for k in range(1, 4))
        or sum(costs[: n - 1]) != hunter.tree_weight_floor(FLOORS, ranks, n)
        or sum(costs[: n - 1]) < proof["hunter_floor"]
        or sum(costs) < root_floor
    ):
        raise AssertionError("nested Kruskal/Hunter/same-tree addition failed")
    return {
        "support_witness": support,
        "support_sha256": digest(support),
        "core_indices": tuple(range(n)),
        "core_tree": core,
        "attachment_edges": attachments,
        "extended_tree": full,
        "edge_costs": costs,
        "collision_mass": mass,
        "threshold_edge_counts": e,
        "threshold_ranks": ranks,
        "core_exact_weight": sum(costs[: n - 1]),
        "extended_exact_weight": sum(costs),
        "universal_root_floor": root_floor,
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


def expected_bound(name: str, v: CountVector) -> int:
    return {
        "A1": 354141809 + 448 * int(v[5] > 0),
        "A2": 353891944 + 448 * v[5],
        "A3": 353925082 + 448 * v[5],
        "B1": 354220678 + 448 * v[5],
        "B2": 354034408,
        "B3": 354244702 + 448 * v[5],
    }[name]


def certify_vector(state_id: str, row: dict[str, Any], v: CountVector) -> dict[str, Any]:
    name = next(k for k, vs in cohorts().items() if v in vs)
    if name[0] != ("A" if state_id == STATE_A else "B"):
        raise AssertionError("cohort State ownership failed")
    state = catalog.rebuild_member(catalog.LedgerMember(v, 1, row["raw_bound"], row["final_bound"]))
    uncorrected = hunter.r14.joint_constant() - state.anchor_pair_s2 + state.anchor_triple_s3
    old = int(vector_rows(state_id)[v]["final_bound"])
    earlier = root65.sealed_vector_bounds().get(v, ())
    credits = {
        "R6_PAIR": state.residual_pair_union_penalty,
        "FOREST": state.complementary_forest_floor,
        "SEALED_MEMBER": uncorrected - row["final_bound"],
        "SEALED_VECTOR": uncorrected - old,
        **{f"SEALED:{path}": uncorrected - b for path, b in earlier},
    }
    existing = max(credits.values())
    credits["PAIRED_ROOT"] = root_credit(name, v)
    credit, bound = apply_credit(uncorrected, old, credits)
    residual = sum(c * hunter.residual_event_size(t) for t, c in enumerate(v))
    if (
        uncorrected != hunter.anchor_union_size() + residual
        or bound != expected_bound(name, v)
        or any(old > b for _, b in earlier)
        or credit != COHORT_SPECS[name][3]
    ):
        raise AssertionError("all existing credits/MAX-only/single subtraction/exact bound failed")
    return {
        "cohort": name,
        "counts": sparse(v),
        "uncorrected_bound": uncorrected,
        "anchor_union": hunter.anchor_union_size(),
        "residual_event_sum": residual,
        "vector_prior_bound": old,
        "existing_applied_credit": existing,
        "corrections": credits,
        "root_credit": credits["PAIRED_ROOT"],
        "new_credit": credit,
        "vector_new_bound": bound,
        "witness_analysis": witness_analysis(v),
    }


def update_region(state_id: str) -> dict[str, Any]:
    recovered = region_vectors(state_id)
    records: list[dict[str, Any]] = []
    for row in target_rows(state_id):
        vs = recovered[dense(row["witness_counts"])]
        certs = [certify_vector(state_id, row, v) for v in vs]
        records.append(
            {
                "member_id": row["member_id"],
                "counts": row["witness_counts"],
                "compression_signature": row["compression_signature"],
                "represented_vector_count": len(vs),
                "represented_vectors": [sparse(v) for v in vs],
                "cohort": certs[0]["cohort"],
                "member_prior_bound": row["final_bound"],
                "member_new_bound": member_bound(tuple(c["vector_new_bound"] for c in certs)),
                "vector_certificates": certs,
            }
        )
    replacements = {
        dense(c["counts"]): c["vector_new_bound"] for r in records for c in r["vector_certificates"]
    }
    updated: list[dict[str, Any]] = []
    for row in region_rows(state_id):
        vr = [
            {
                **vector_rows(state_id)[v],
                "prior_bound": vector_rows(state_id)[v]["final_bound"],
                "final_bound": replacements.get(v, vector_rows(state_id)[v]["final_bound"]),
            }
            for v in recovered[dense(row["witness_counts"])]
        ]
        updated.append(
            {
                **row,
                "prior_bound": row["final_bound"],
                "final_bound": member_bound(tuple(int(r["final_bound"]) for r in vr)),
                "represented_vector_bounds": vr,
            }
        )
    ids = {r["member_id"] for r in records}
    untouched = [r for r in updated if r["member_id"] not in ids]
    untouched_vectors = [v for r in untouched for v in r["represented_vector_bounds"]]
    mc, vc, tc, tv, _, remainder, target = SPECS[state_id]
    if (
        len(untouched),
        len(untouched_vectors),
        max(r["final_bound"] for r in untouched),
        max(r["member_new_bound"] for r in records),
        max(r["final_bound"] for r in updated),
    ) != (mc - tc, vc - tv, remainder, target, remainder) or any(
        r["final_bound"] != r["prior_bound"] for r in (*untouched, *untouched_vectors)
    ):
        raise AssertionError("all untouched bounds and State/target maxima required")
    return {
        "state_id": state_id,
        "region_sha256": REGION_HASHES[state_id],
        "region_member_count": mc,
        "region_vector_count": vc,
        "target_member_count": len(records),
        "target_vector_count": len(replacements),
        "member_certificates": records,
        "complete_region_members": updated,
        "all_represented_vectors_sha256": digest(tuple(recovered.items())),
        "preserved_member_count": len(untouched),
        "preserved_vector_count": len(untouched_vectors),
        "preserved_member_bounds_sha256": digest(untouched),
        "preserved_vector_bounds_sha256": digest(untouched_vectors),
        "target_cohort_max": target,
        "preserved_remainder_max": remainder,
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
    if (len(states), len(classified), len(terms), len(dict(terms)), max(b for _, b in terms)) != (
        23,
        56550,
        56574,
        56574,
        355110434,
    ) or family_digest(terms) != base["FAMILY_RECOMPUTATION"]["new_sha256"]:
        raise AssertionError("all 56574 sealed Family terms required")
    return terms


def recompute_family(terms: Terms, bounds: dict[str, int]) -> dict[str, Any]:
    if terms != family_terms() or set(bounds) != set(SPECS):
        raise AssertionError("all sealed State/Classified/Tail terms must be preserved")
    updated = tuple((k, min(b, bounds[k]) if k in bounds else b) for k, b in terms)
    ordered = sorted(updated, key=lambda r: (-r[1], r[0]))
    d = dict(updated)
    if (
        sum(a != b for a, b in zip(terms, updated, strict=True)) != 2
        or d[prior.STATE_A] != 355016928
        or d["state:s2-14696976-s3-1059324"] != 354603232
        or updated[23:] != terms[23:]
        or max(b for _, b in updated[23:-1]) != 354800665
        or updated[-1] != ("unclassified-tail", 354039277)
        or ordered[:2] != [(FINAL_OWNER, 355073068), (STATE_B, 355060310)]
        or family_digest(updated) != EXPECTED_FAMILY_DIGEST
    ):
        raise AssertionError("two State replacements/full Family max/owner/runner-up failed")
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


def predecessor_preservation() -> dict[str, Any]:
    base = sealed(BASE_RESULT)
    carried = [r for region in base["REGIONS"] for r in region["member_certificates"]]
    if len(carried) != 14 or base["CORE_PROOFS"]["H16"]["hunter_floor"] != 7211400:
        raise AssertionError("fourteen predecessor certificates/H16 credit required")
    return {
        "base_result_sha256": sha256(frozen_blob(BASE_RESULT)).hexdigest(),
        "carried_14_certificates_sha256": digest(carried),
        "carried_core_proofs_sha256": digest(base["CORE_PROOFS"]),
        "H16_credit": 7211400,
        "readoption_count": 0,
        "rebuild_count": 0,
    }


def build_result() -> dict[str, Any]:
    authority = verify_source_authority()
    regions = [update_region(s) for s in SPECS]
    aliases = verify_aliases()
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
        "ROOT_PAIR_PROOF": root_pair_proof(),
        "ROOT_PAIR_ROW_STATUS": "PASS_48_LEGAL_RESIDUAL_ROWS",
        "ROOT_RESIDUAL_FLOOR_STATUS": "PASS_TYPE_SPECIFIC_RESIDUAL_FLOORS_INCLUDING_TYPE20_103600",
        "CORE_PROOFS": {f"H{n}": core_proof(n) for n in CORE_SPECS},
        "CORE_HUNTER_MINIMA_STATUS": "PASS_H10_H11_H12_H13_COMPLETE_INTEGER_MINIMA",
        "TREE_EXTENSION_STATUS": "PASS_SAME_TREE_DISJOINT_CORE_AND_LEAVES_18_VERTICES_17_EDGES",
        "COMPRESSED_ALIASES": aliases,
        "COMPRESSED_ALIAS_COVERAGE": 20,
        "REGIONS": regions,
        "NEW_STATE_A_UB": regions[0]["new_state_bound"],
        "NEW_STATE_B_UB": regions[1]["new_state_bound"],
        "NO_DOUBLE_COUNT_STATUS": "PASS_MAX_ALL_VALID_CREDITS_SUBTRACT_ONCE_MEMBER_MAX",
        "PREDECESSOR_PRESERVATION": predecessor_preservation(),
        "FAMILY_RECOMPUTATION": family,
        "FINAL_STATE_TERMS": family["states"],
        "FULL_56574_FAMILY_RECOMPUTATION": "PASS_23_STATES_56550_CLASSIFIED_1_TAIL",
        "START_COMPLETE_R3_UB": family["start_max"],
        "FINAL_COMPLETE_R3_UB": family["final_max"],
        "FINAL_OWNER": family["owner"],
        "RUNNER_UP": family["runner_up"],
        "STRICT_GAIN": family["start_max"] - family["final_max"],
        "INCUMBENT": 313263888,
        "REMAINING_GAP": family["final_max"] - 313263888,
        "WITNESS_SOUNDNESS_STATUS": "PASS_ALL_170_VECTORS_LEGAL_SUPPORTS_AND_TREE_WEIGHTS",
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
    if (result["STRICT_GAIN"], result["REMAINING_GAP"]) != (37366, 41809180):
        raise AssertionError("strict Family gain/remaining gap failed")
    return cast(dict[str, Any], json.loads(encode(result)))


def verify_result(result: dict[str, Any]) -> dict[str, Any]:
    verify_source_authority()
    if result != build_result():
        raise AssertionError("result differs from deterministic replay/source binding")
    return {
        "status": "PASS",
        "members": 150,
        "vectors": 170,
        "aliases": 20,
        "region_members": 2649,
        "region_vectors": 2868,
        "root_pair_rows": 48,
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
