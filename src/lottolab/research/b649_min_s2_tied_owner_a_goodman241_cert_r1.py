"""Goodman T<=241 for the single profile 66555555555531000000.

Pinned r5 semantics: 20 tickets, six labels per ticket, 22 triple supports,
27 pair supports, and no repeated ticket pair in any support. Thus the overlap
graph G is simple, E=66+27=93, deg_G(i)=6+d_i and W=sum C(6+d_i,2)=829.
If N_j counts three-vertex sets with j edges, W=N_2+3T and
18E=N_1+2N_2+3T. Consequently I+T=C(20,3)-18E+W=295. I is the
number of independent triples of G, equivalently triangles of its complement.

Let C={d>0}, |C|=14, and Z={d=0}, |Z|=6. All 22 triple supports lie
in C. For i in C, r_i=6-d_i is its pair-label capacity, b_i its cross
degree, a_i=r_i-b_i its C-internal pair degree. Put m=sum(a_i)/2.
sum(r)=18 gives sum(b)=18-2m. Zero degrees give |E(G[Z])|=9+m.
For the nonedge graphs H on C and F on Z, |H|=25-m, |F|=6-m,
h_i=deg_H(i)=7-d_i+b_i. Hence 0<=m<=6; a and h must be graphical.
Every legal realization maps into this necessary degree domain. Permuting
the ten d=5 tickets leaves every inequality invariant, so the 264 class-sorted
vectors cover all 24,576 labelled b vectors, with weights C(10,n5).

CCZ: an H edge ij has at least 6-b_i-b_j common non-neighbours in Z.
Thus I_CCZ>=max(0,6|H|-sum h_i*b_i).
CZZ: if f_z=deg_F(z), the cross degree from z is c_z=1+f_z. An F
edge zw has at least 14-c_z-c_w=12-f_z-f_w non-neighbours in C.
Thus I_CZZ>=12|F|-sum f_z^2, and I_ZZZ=t(F). All C(15,L) graphs
with L=0..6 edges are checked exactly; no support realization is searched.
CCC: outside N_H(i) and i are 13-h_i vertices. Edges not touching i
number |H|-h_i. At most the sum of the largest 13-h_i other degrees
can touch those outside vertices, so l_i=max(0,|H|-h_i-top_sum)
is a lower bound on triangles through i. Therefore
I_CCC>=max(max_i l_i,ceil(sum_i l_i/3)). The four types are disjoint.
The minimum of the summed lower bounds over the necessary domain is 54;
therefore every legal target realization satisfies T<=295-54=241.

Route B uses the pinned R32 theorem at every integer T=22..241, exact
ceilings and floors; its full envelope is 313183160. T denotes ALL graph
triangles, including the 22 support triangles. Cap attainment is not asserted.

Ledger replay uses the committed six-row BOUNDS snapshot and the two recorded
T256/T248 updates, asserting each bound digest. This recovers exactly the
4,647-row T248 bounds projection, plus its three complete owner rows. Only
owner A is replaced, in memory. Other row bounds and both other complete owner
rows are unchanged; the unresolved cursor and inherited statuses are retained.
No full-row digest is claimed for the bounds projection. Historical Goodman
code supplied the theorem only, and is neither executed nor adopted as authority.
"""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations, product
from math import comb
from pathlib import Path
from typing import cast

TASK_ID = "B649_MIN_S2_TIED_OWNER_A_GOODMAN241_FORMAL_CERT_R1"
BASE_HEAD = "8d2411474c721264697438428b09a2ff00ea6802"
BASE_TREE = "e7b2717e4f31d40bc213d6918a58b86a486f0375"
TARGET_PROFILE = "66555555555531000000"
OTHER_OWNERS = ("66655555554441000000", "66655555555422000000")
PROFILE = tuple(map(int, TARGET_PROFILE))
CORE = PROFILE[:14]
CURRENT_CAP = 265
CERTIFIED_CAP = 241
GOODMAN_CONSTANT = 295
INDEPENDENT_FLOOR = 54
CURRENT_BOUND = 313_398_248
PROFILE_BOUND = 313_183_160
INCUMBENT = 313_263_888
S4_BASE = 112
ROOT = Path(__file__).resolve().parents[3]
RESULT_DIRECTORY = "docs/research/matrix-native-results"
RESULT_FILENAME = "b649-min-s2-tied-owner-a-goodman241-cert-r1-result.json"
RESULT_PATH = ROOT / RESULT_DIRECTORY / RESULT_FILENAME
T248_FILENAME = "b649-min-s2-post-t256-next-owner-cap248-cert-r1-result.json"
T256_FILENAME = "b649-min-s2-next-owner-core-zero-t256-cert-r1-result.json"
SIX_FILENAME = "b649-min-s2-six-row-existing-s4-family-authority-r1-result.json"
RESULT_PINS = {
    T248_FILENAME: "28fe692403cb193ee908708c7775b45bd80a2e4cf731b4d4e015d71c5558aabe",
    T256_FILENAME: "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743",
    SIX_FILENAME: "1f94b064ab7392b88cf4c18ca4d3cb164305601ea9bc2b0f2174c0cddb185e5f",
}
SOURCE_PINS = {
    "b649_k20_min_s2_realizable_core_class_bound_r4": (
        "cbc57debfcc037b8be605f9c3e157dba9029fbbcca50fa05dcff99390066edec"
    ),
    "b649_k20_min_s2_dangerous_core_realizability_r5": (
        "ad2c524bcdb716af1f1f744435576376499e3f39c3a744aec613542c41964487"
    ),
    "b649_k20_min_s2_route_b_current_owner_refinement_r32": (
        "d2bd52eaa53825fc138b95f42d06ec6152757ae25a70212b0674bf8ea311dc1d"
    ),
    "b649_k20_min_s2_resolved_above_cursor_owner_chase_r20": (
        "b63081af598a6366ab9989f00f3e269052e8edbc41956a0771941dc03891b74e"
    ),
}
HISTORICAL_SOURCE = (
    "/Users/kelvin/.codex/worktrees/b649-k20-goodman-next-three-r1/"
    "MathStatisticalAnalysis/goodman_next_three_verifier.py"
)
HISTORICAL_SHA256 = "870cf988362d710dae048cabd807823de65ab48bd7736c20aac146a1119c2c02"
type Edge = tuple[int, int]
type Term = tuple[int, int, int, int, int, int]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def obj(value: object) -> dict[str, object]:
    require(isinstance(value, dict), "expected JSON object")
    out = cast(dict[object, object], value)
    require(all(isinstance(k, str) for k in out), "JSON keys must be strings")
    return cast(dict[str, object], out)


def items(value: object) -> list[object]:
    require(isinstance(value, list), "expected JSON array")
    return cast(list[object], value)


def integer(value: object) -> int:
    require(type(value) is int, "expected exact integer")
    return cast(int, value)


def render(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def pinned(path: str, digest: str) -> bytes:
    metadata = git("ls-tree", BASE_HEAD, "--", path).decode().split()
    require(len(metadata) == 4 and metadata[:2] == ["100644", "blob"], "unsafe pinned path")
    raw = git("show", f"{BASE_HEAD}:{path}")
    local = ROOT / path
    require(not local.is_symlink() and local.is_file(), "unsafe local pinned path")
    require(sha(raw) == digest and local.read_bytes() == raw, f"pin mismatch: {path}")
    return raw


def support_model() -> dict[str, object]:
    """Pin r5/r4 semantics and independently check their constants and graph consequences."""
    sources = {
        name: pinned(f"src/lottolab/research/{name}.py", digest)
        for name, digest in SOURCE_PINS.items()
    }
    constants: dict[str, int] = {}
    for statement in ast.parse(sources["b649_k20_min_s2_realizable_core_class_bound_r4"]).body:
        if isinstance(statement, ast.Assign) and isinstance(statement.value, ast.Constant):
            for target in statement.targets:
                if isinstance(target, ast.Name) and type(statement.value.value) is int:
                    constants[target.id] = statement.value.value
    expected = {
        "K20_TICKET_COUNT": 20,
        "K20_TICKET_CAPACITY": 6,
        "K20_LABEL_COUNT": 49,
        "K20_TRIPLE_SUPPORT_COUNT": 22,
        "K20_DOUBLE_SUPPORT_COUNT": 27,
        "K20_S1": 372_228_640,
        "K20_S2": 63_838_600,
        "K20_S3_WEDGE_COEFFICIENT": 2800,
        "K20_S3_TRIANGLE_COEFFICIENT": 11872,
        "K20_S3_CONSTANT": 30800,
    }
    require(all(constants.get(k) == v for k, v in expected.items()), "support constants drift")
    require(22 + 27 == 49 and 3 * 22 + 2 * 27 == 20 * 6, "support incidence semantics")
    require(PROFILE == (6,) * 2 + (5,) * 10 + (3, 1) + (0,) * 6, "wrong target profile")
    require(sum(PROFILE) == 66 and sum(6 - d for d in CORE) == 18, "core capacities")
    return {
        "STATUS": "PASS",
        "CONSTANTS": expected,
        "PINNED_SOURCES": {f"src/lottolab/research/{n}.py": h for n, h in SOURCE_PINS.items()},
        "PAIR_UNIQUENESS": "EVERY_2_SUBSET_OF_EVERY_SUPPORT_OCCURS_ONCE",
        "GRAPH_DEGREE_RULE": "2*d+(6-d)=6+d",
        "T_COUNTS": "ALL_GRAPH_TRIANGLES",
    }


def validate_supports(
    triples: Sequence[Sequence[int]], pairs: Sequence[Sequence[int]], expected: Sequence[int]
) -> tuple[tuple[int, ...], frozenset[Edge]]:
    """Independent implementation of the pinned r5 legal-support premises; no search."""
    require(len(triples) == 22 and len(pairs) == 27, "support counts")
    require(len(expected) == 20 and all(type(v) is int for v in expected), "expected degrees")
    require(all(0 <= v <= 6 for v in expected) and sum(expected) == 66, "expected profile")
    degrees, capacities, edges = [0] * 20, [0] * 20, set[Edge]()
    for supports, size in ((triples, 3), (pairs, 2)):
        for support in supports:
            require(len(support) == size and len(set(support)) == size, "support arity")
            require(all(type(v) is int and 0 <= v < 20 for v in support), "support vertices")
            for v in support:
                capacities[v] += 1
                degrees[v] += int(size == 3)
            for u, v in combinations(sorted(support), 2):
                require((u, v) not in edges, "repeated ticket pair")
                edges.add((u, v))
    require(tuple(degrees) == tuple(expected), "support degree mismatch")
    require(capacities == [6] * 20, "ticket capacity mismatch")
    require(len(edges) == 93, "graph edge count")
    require(
        [sum(v in edge for edge in edges) for v in range(20)] == [6 + d for d in degrees],
        "graph degree semantics",
    )
    return tuple(degrees), frozenset(edges)


def goodman_identity() -> dict[str, object]:
    degrees = [6 + d for d in PROFILE]
    edges = sum(degrees) // 2
    wedges = sum(comb(v, 2) for v in degrees)
    identity = comb(20, 3) - 18 * edges + wedges
    second = Fraction(comb(20, 3)) - Fraction(sum(v * (19 - v) for v in degrees), 2)
    require((edges, wedges, identity) == (93, 829, GOODMAN_CONSTANT), "Goodman identity")
    require(second == identity == 295, "Goodman complement identity")
    return {"STATUS": "PASS", "E": edges, "W": wedges, "T_PLUS_I": identity}


def graphical(degrees: Sequence[int]) -> bool:
    """Erdos-Gallai, all k=1..n; only impossible simple-graph degree lists are removed."""
    d = sorted(degrees, reverse=True)
    n = len(d)
    return (
        all(type(v) is int and 0 <= v < n for v in d)
        and sum(d) % 2 == 0
        and all(sum(d[:k]) <= k * (k - 1) + sum(min(k, v) for v in d[k:]) for k in range(1, n + 1))
    )


def ccc_floor(h: Sequence[int], edge_count: int) -> int:
    lower = [
        max(0, edge_count - hi - sum(sorted((*h[:i], *h[i + 1 :]), reverse=True)[: 13 - hi]))
        for i, hi in enumerate(h)
    ]
    return max(max(lower), (sum(lower) + 2) // 3)


def ccz_floor(h: Sequence[int], b: Sequence[int], edge_count: int) -> int:
    return max(0, 6 * edge_count - sum(hi * bi for hi, bi in zip(h, b, strict=True)))


def zero_floor(degrees: Sequence[int], edge_count: int, triangles: int) -> int:
    return 12 * edge_count - sum(v * v for v in degrees) + triangles


def zero_graphs() -> dict[str, object]:
    """All labelled F on six vertices with 0..6 edges, streamed once."""
    slots = tuple(combinations(range(6), 2))
    floors, counts = [10**9] * 7, [0] * 7
    witnesses: list[dict[str, object]] = [{} for _ in range(7)]
    for size in range(7):
        m = 6 - size
        for selected in combinations(range(15), size):
            adj, degree = [0] * 6, [0] * 6
            for index in selected:
                u, v = slots[index]
                adj[u] |= 1 << v
                adj[v] |= 1 << u
                degree[u] += 1
                degree[v] += 1
            triangles = sum(
                (adj[u] >> v) & (adj[u] >> w) & (adj[v] >> w) & 1
                for u, v, w in combinations(range(6), 3)
            )
            require(graphical(degree) and sum(degree) == 2 * size, "F graph semantics")
            value = zero_floor(degree, size, triangles)
            counts[m] += 1
            if value < floors[m]:
                floors[m] = value
                witnesses[m] = {
                    "EDGES": [list(slots[i]) for i in selected],
                    "DEGREES": degree,
                    "TRIANGLES": triangles,
                }
    require(counts == [comb(15, 6 - m) for m in range(7)], "F domain incomplete")
    return {
        "FLOORS_BY_M": floors,
        "COUNTS_BY_M": counts,
        "MINIMIZERS_BY_M": witnesses,
        "GRAPHS_CHECKED": sum(counts),
    }


def independent_bound(z_floors: Sequence[int]) -> dict[str, object]:
    """Symmetry quotient of the exact product b_i in 0..6-d_i; a superset of legal supports."""
    require(len(z_floors) == 7, "F floor domain")
    floors, counts, weighted_counts = [10**9] * 7, [0] * 7, [0] * 7
    witnesses: list[dict[str, object]] = [{} for _ in range(7)]
    raw = 0
    for n5, b3, b1 in product(range(11), range(4), range(6)):
        weight = comb(10, n5)
        raw += weight
        b = [0] * 2 + [0] * (10 - n5) + [1] * n5 + [b3, b1]
        cross = sum(b)
        if not 6 <= cross <= 18 or cross % 2:
            continue
        m = (18 - cross) // 2
        a = [6 - d - bi for d, bi in zip(CORE, b, strict=True)]
        h = [7 - d + bi for d, bi in zip(CORE, b, strict=True)]
        if not graphical(a) or not graphical(h):
            continue
        edges = 25 - m
        require(sum(a) == 2 * m and sum(h) == 2 * edges, "core degree relations")
        ccz, ccc = ccz_floor(h, b, edges), ccc_floor(h, edges)
        value = ccz + ccc + z_floors[m]
        counts[m] += 1
        weighted_counts[m] += weight
        if value < floors[m]:
            floors[m] = value
            witnesses[m] = {
                "B": b,
                "A": a,
                "H_DEGREES": h,
                "CCZ": ccz,
                "CCC": ccc,
                "CZZ_PLUS_ZZZ": z_floors[m],
            }
    require(raw == 24576 == 2**10 * 4 * 6 and all(counts), "core degree domain incomplete")
    return {
        "FLOORS_BY_M": floors,
        "CLASS_SORTED_VECTORS": 264,
        "LABELLED_VECTORS_COVERED": raw,
        "ADMISSIBLE_CLASSES_BY_M": counts,
        "ADMISSIBLE_LABELLED_COUNTS_BY_M": weighted_counts,
        "MINIMIZERS_BY_M": witnesses,
        "INDEPENDENT_TRIPLE_FLOOR": min(floors),
    }


def cap_theorem() -> dict[str, object]:
    goodman = goodman_identity()
    zero = zero_graphs()
    floors = [integer(v) for v in items(zero["FLOORS_BY_M"])]
    independent = independent_bound(floors)
    floor = integer(independent["INDEPENDENT_TRIPLE_FLOOR"])
    require(floor == INDEPENDENT_FLOOR == 54, "independent triple bound below 54 or drift")
    require(integer(goodman["T_PLUS_I"]) - floor == CERTIFIED_CAP == 241, "cap derivation")
    return {
        "GOODMAN_IDENTITY": goodman,
        "ZERO_GRAPHS": zero,
        "CORE_DOMAIN": independent,
        "OPEN_WEDGE_BOUND": "PASS",
        "CERTIFIED_T_CAP": CERTIFIED_CAP,
        "ATTAINMENT": "NOT_ASSERTED",
        "STATUS": "PROVEN",
    }


def route_b(cap: int, base: int = S4_BASE) -> list[Term]:
    """Pinned R32 formula, every T, exact integer and independent rational rounding checks."""
    require(type(cap) is int and 22 <= cap <= 829 // 3, "invalid Route-B cap")
    require(type(base) is int and base >= 0, "invalid S4 floor")
    degrees = [6 + d for d in PROFILE]
    wedges, choose3 = sum(comb(g, 2) for g in degrees), sum(comb(g, 3) for g in degrees)
    a_max = sum(d * (g - 2) for d, g in zip(PROFILE, degrees, strict=True)) // 3
    terms: list[Term] = []
    for t in range(22, cap + 1):
        excess = choose3 - (max(degrees) - 2) * (wedges - 3 * t)
        k4 = max(0, -((-excess) // 4))
        contained = min(k4, a_max)
        s4 = max(base, 679 * k4 - 231 * contained)
        s3 = 2800 * wedges + 11872 * (t - 22) - 30800
        bound = 372_228_640 - 63_838_600 + s3 - (4 * s4) // 7
        rational = 372_228_640 - 63_838_600 + s3 - Fraction(4 * s4, 7)
        require(
            (k4 == 0 and excess <= 0) or (k4 > 0 and 4 * (k4 - 1) < excess <= 4 * k4),
            "K4 ceiling",
        )
        require(s4 >= 448 * contained + 679 * (k4 - contained), "K4 split")
        require(0 <= bound - rational < 1, "Route-B rounding")
        terms.append((t, bound, k4, contained, s4, s3))
    return terms


def bounds_digest(bounds: Mapping[str, int]) -> str:
    rows = [{"PROFILE_ID": p, "CURRENT_BOUND": bounds[p]} for p in sorted(bounds)]
    return sha(json.dumps(rows, sort_keys=True).encode())


@dataclass(frozen=True)
class LedgerView:
    """Complete bounds projection and the three complete T248 owner rows."""

    bounds: dict[str, int]
    owner_rows: dict[str, dict[str, object]]
    cursor: dict[str, object]
    status: dict[str, object]


def family(view: LedgerView) -> tuple[int, list[str]]:
    cursor_bound = integer(view.cursor["BOUND"])
    maximum = max(max(view.bounds.values()), cursor_bound)
    owners = [p for p, v in view.bounds.items() if v == maximum]
    if cursor_bound == maximum:
        owners.append(str(view.cursor["ID"]))
    return maximum, sorted(owners)


def base_authority() -> tuple[LedgerView, dict[str, object]]:
    require(
        git("rev-parse", f"{BASE_HEAD}^{{tree}}").decode().strip() == BASE_TREE,
        "base tree mismatch",
    )
    git("merge-base", "--is-ancestor", BASE_HEAD, "HEAD")
    results = {
        name: obj(json.loads(pinned(f"{RESULT_DIRECTORY}/{name}", digest)))
        for name, digest in RESULT_PINS.items()
    }
    six, t256, t248 = results[SIX_FILENAME], results[T256_FILENAME], results[T248_FILENAME]
    bounds = {p: integer(v) for p, v in obj(six["RESOLVED_ROW_BOUNDS"]).items()}
    require(bounds_digest(bounds) == six["BOUNDS_SHA256_AFTER"], "six-row bounds digest")
    for previous in (t256, t248):
        require(bounds_digest(bounds) == previous["BOUNDS_SHA256_BEFORE"], "prior digest chain")
        update = obj(previous["ROW_UPDATE"])
        pid = str(update["PROFILE_ID"])
        require(bounds[pid] == obj(update["BEFORE"])["bound"], "prior row binding")
        bounds[pid] = integer(obj(update["AFTER"])["bound"])
        require(bounds_digest(bounds) == previous["BOUNDS_SHA256_AFTER"], "T248 bounds digest")
    owner_rows = {p: dict(obj(v)) for p, v in obj(t248["NEW_OWNER_ROWS"]).items()}
    require(sorted(owner_rows) == sorted((TARGET_PROFILE, *OTHER_OWNERS)), "T248 tied owners")
    for pid, index in zip((TARGET_PROFILE, *OTHER_OWNERS), (1443, 1215, 1202), strict=True):
        require(
            owner_rows[pid]
            == {
                "bound": CURRENT_BOUND,
                "cap": CURRENT_CAP,
                "s4_base": S4_BASE,
                "source": "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:"
                f"NB_CERTIFICATES[{index}]",
                "realization": None,
            }
            and bounds[pid] == CURRENT_BOUND,
            "T248 complete owner row mismatch",
        )
    cursor = dict(obj(six["CURSOR"]))
    require(cursor == {"BOUND": 313394584, "ID": "66544333333333332222"}, "cursor mismatch")
    view = LedgerView(bounds, owner_rows, cursor, obj(t248["PRESERVED_T256_STATUS"]))
    require(len(bounds) == t248["LEDGER_ROWS"] == 4647, "T248 ledger count")
    require(family(view) == (CURRENT_BOUND, sorted(owner_rows)), "T248 family mismatch")
    require(
        t248["FAMILY_BOUND_AFTER"] == CURRENT_BOUND and t248["INCUMBENT"] == INCUMBENT,
        "T248 sealed result mismatch",
    )
    return view, {
        "RESULT_PINS": RESULT_PINS,
        "BOUNDS_SHA256": bounds_digest(bounds),
        "T248_TASK_STATUS": t248["TASK_STATUS"],
    }


def replace_owner(view: LedgerView, bound: int, cap: int) -> LedgerView:
    """One memory-only replacement; exact owner metadata, every other bound preserved."""
    require(type(bound) is int and type(cap) is int, "update needs exact integers")
    require((bound, cap) == (PROFILE_BOUND, CERTIFIED_CAP), "uncertified replacement")
    old = view.owner_rows[TARGET_PROFILE]
    require(
        (view.bounds[TARGET_PROFILE], old["bound"], old["cap"], old["s4_base"])
        == (CURRENT_BOUND, CURRENT_BOUND, CURRENT_CAP, S4_BASE),
        "double or mismatched update",
    )
    require(
        family(view) == (CURRENT_BOUND, sorted((TARGET_PROFILE, *OTHER_OWNERS))),
        "pre-update owner drift",
    )
    before = render(
        {
            "bounds": view.bounds,
            "owners": view.owner_rows,
            "cursor": view.cursor,
            "status": view.status,
        }
    )
    bounds, owners = dict(view.bounds), dict(view.owner_rows)
    bounds[TARGET_PROFILE] = bound
    owners[TARGET_PROFILE] = {
        **old,
        "bound": bound,
        "cap": cap,
        "source": f"{TASK_ID}:GOODMAN_T241_THEOREM",
    }
    after = LedgerView(bounds, owners, dict(view.cursor), dict(view.status))
    require(
        [p for p in bounds if bounds[p] != view.bounds[p]] == [TARGET_PROFILE],
        "more than one bound replaced",
    )
    require(
        [p for p in owners if owners[p] != view.owner_rows[p]] == [TARGET_PROFILE],
        "another complete owner row changed",
    )
    require(
        render(
            {
                "bounds": view.bounds,
                "owners": view.owner_rows,
                "cursor": view.cursor,
                "status": view.status,
            }
        )
        == before,
        "input ledger mutated",
    )
    require(
        all(after.owner_rows[p] == view.owner_rows[p] for p in OTHER_OWNERS),
        "other tied owners changed",
    )
    require(family(after) == (CURRENT_BOUND, sorted(OTHER_OWNERS)), "family replay mismatch")
    return after


def compute_result() -> dict[str, object]:
    model = support_model()
    before, authority = base_authority()
    theorem = cap_theorem()
    old_terms, terms = route_b(CURRENT_CAP), route_b(CERTIFIED_CAP)
    peak = max(terms, key=lambda term: (term[1], term[0]))
    require(max(t[1] for t in old_terms) == CURRENT_BOUND, "old Route-B row not reproduced")
    require(terms == old_terms[: len(terms)] and len(terms) == 220, "all-T domain incomplete")
    require(peak[1] == PROFILE_BOUND and peak[0] == CERTIFIED_CAP, "full profile bound")
    require(PROFILE_BOUND < INCUMBENT, "strict gain not excluded")
    after = replace_owner(before, peak[1], CERTIFIED_CAP)
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "CERTIFIED_OWNER_A_RESULT",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TARGET_PROFILE": TARGET_PROFILE,
        "PROOF": __doc__,
        "SUPPORT_MODEL": model,
        "BASE_AUTHORITY": authority,
        "HISTORICAL_THEOREM_SOURCE": {
            "PATH": HISTORICAL_SOURCE,
            "OBSERVED_SHA256": HISTORICAL_SHA256,
            "DISPOSITION": "SCIENTIFIC_PASS_RESOURCE_CONFORMANCE_FAIL",
            "USE": "THEOREM_SOURCE_ONLY_NOT_EXECUTED_NOT_ADOPTED_AS_AUTHORITY",
        },
        "THEOREM": theorem,
        "GOODMAN_IDENTITY": "PASS",
        "OPEN_WEDGE_BOUND": "PASS",
        "CERTIFIED_T_CAP": CERTIFIED_CAP,
        "PROFILE_BOUND": peak[1],
        "STRICT_GAIN_EXCLUDED": "YES",
        "INCUMBENT": INCUMBENT,
        "PROFILE_MARGIN_TO_INCUMBENT": INCUMBENT - peak[1],
        "ROUTE_B": {
            "MIN_T": 22,
            "MAX_T": CERTIFIED_CAP,
            "TERM_COUNT": len(terms),
            "ALL_T_TERMS": [list(t) for t in terms],
            "ARGMAX_TERM": list(peak),
            "ORIGINAL_CAP": CURRENT_CAP,
            "ORIGINAL_BOUND": max(t[1] for t in old_terms),
            "A_MAX": sum(d * (4 + d) for d in PROFILE) // 3,
            "BOUND_RULE": "S1-S2+S3(T)-FLOOR(4*MAX(112,679*K4(T)-231*MIN(K4(T),A_MAX))/7)",
            "STATUS": "PASS_EXACT_INTEGER_AND_RATIONAL",
        },
        "LEDGER_REPLAY_VIEW": "COMPLETE_BOUNDS_PROJECTION_PLUS_THREE_COMPLETE_OWNER_ROWS",
        "LEDGER_ROWS": len(before.bounds),
        "ROWS_REPLACED": [TARGET_PROFILE],
        "ROW_UPDATE": {
            "BEFORE": before.owner_rows[TARGET_PROFILE],
            "AFTER": after.owner_rows[TARGET_PROFILE],
        },
        "BOUNDS_SHA256_BEFORE": bounds_digest(before.bounds),
        "BOUNDS_SHA256_AFTER": bounds_digest(after.bounds),
        "FAMILY_BOUND_BEFORE": family(before)[0],
        "FAMILY_BOUND_AFTER_SINGLE_ROW_UPDATE": family(after)[0],
        "FAMILY_DELTA": 0,
        "FAMILY_OWNER_IDS_AFTER": family(after)[1],
        "OTHER_TIED_OWNERS_PRESERVED": "YES",
        "OTHER_TIED_OWNER_ROWS": {p: after.owner_rows[p] for p in OTHER_OWNERS},
        "CURSOR": before.cursor,
        "INHERITED_STATUS_PRESERVED_VERBATIM": before.status,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "LEDGER_PERSISTENCE": "MEMORY_ONLY",
        "SOURCE_CHANGED_ONLY_IN_ISOLATED_WORKTREE": "YES",
        "HEAVY_SOLVER_STARTED": "NO",
        "SOLVER_CALLS": 0,
        "PORTFOLIO_SEARCH_STARTED": "NO",
        "REMOTE_WRITE": "NO",
        "RUN1_MUTATED": "NO",
        "FABLE_MUTATED": "NO",
        "SHARED_LEDGER_MUTATED": "NO",
        "NEXT_ACTION": "END_WITH_CERTIFIED_OWNER_A_RESULT",
    }


def main() -> None:
    require(sys.argv[1:] in ([], ["--check"]), "expected no arguments or --check")
    result = compute_result()
    payload = render(result)
    if sys.argv[1:] == ["--check"] or RESULT_PATH.exists():
        require(RESULT_PATH.read_bytes() == payload, "result JSON differs from recomputation")
    else:
        with RESULT_PATH.open("xb") as output:
            output.write(payload)
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "TASK_STATUS",
                    "CERTIFIED_T_CAP",
                    "PROFILE_BOUND",
                    "FAMILY_BOUND_AFTER_SINGLE_ROW_UPDATE",
                    "FAMILY_DELTA",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
