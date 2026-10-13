"""Full-profile T<=261 certificate for 66665555554421100000 (self-check only).

Model. There are twenty six-label tickets, 22 triple supports and 27 pair supports.
All support pairs are distinct. Thus the simple overlap graph G has 93 edges and
degree 6+d_i. Triple supports avoid the five vertices with d_i=0. Write K for the
15 positive-degree vertices and Z for these five zeros; H is the complement of G.
The actual d multiset has sum 66 and square sum 332, so Goodman's identity gives
 t(G)+t(H) = C(20,3)-sum_i (6+d_i)(13-d_i)/2 = 1140-1690/2 = 295.

Split. Let sigma_i=|N_G(i) intersect Z|, zeta_u=|N_G(u) intersect K| and
r=sum sigma=sum zeta. Pair capacity gives 0<=sigma_i<=6-d_i. A zero has degree
six and only four possible zero neighbours, so 2<=zeta_u<=6. The internal
complement graphs M=H[K] and Q=H[Z] have degrees h_i=8-d_i+sigma_i and
a_u=zeta_u-2. Hence |M|=(54+r)/2 and |Q|=(r-10)/2. Counting mixed H triangles
across their unique same-part edge gives the exact identity
 t(H)=5|M|+15|Q|-sum sigma_i*h_i-sum zeta_u*a_u+P,
 P=t(M)+t(Q)+sum_{ij in M} c_Z(ij)+sum_{uv in Q} c_K(uv)>=0.
Here c_Z and c_K count common G neighbours in the indicated opposite part.
Consequently
 T=t(G)=235+sum_i sigma_i*(sigma_i-d_i-2)+sum_u zeta_u*(zeta_u-2)-P = F-P.

One additional restriction: P>=L_K+L_Z. On an M edge ij,
c_Z(ij)>=max(0,sigma_i+sigma_j-5). For each i, its h_i neighbours form an
h_i-subset of the other 14 core vertices. Let ell_i be the sum of the h_i
smallest such weights. Double-counting M edges proves
 L_K=ceil(sum ell_i/2)<=sum_M c_Z.
Let q be the number of core vertices with sigma_i>0. Every G core neighbour
of a zero lies in this q-set. Thus c_K(uv)>=max(0,zeta_u+zeta_v-q). For an
actual zero complement graph Q, its contribution is at least
 t(Q)+sum_{uv in Q} max(0,zeta_u+zeta_v-q).
L_Z is the minimum of this quantity over ALL labelled graphs on five vertices
with degree multiset zeta-2. This minimum is computed by all 2^10=1024 masks.
The two floors concern disjoint terms of P; t(M)>=0 is discarded.

Completeness. Sort sigma only within equal-d classes, and sort zeta within Z.
Both F and the two floors are invariant under these permutations. All class
multisets over the entire pair-capacity ranges give 1*7*6*5*21=4410 sigma
vectors. All 1024 zero graphs give 31 degree shapes. Every equal-sum pair is
included, yielding 3779 configurations. We impose NO core graphicality,
residual graphicality, bipartite graphicality, or support realizability filter.
Thus every legal realization maps into this finite superset. Its exact maximum
of F-L_K-L_Z is 261 (five maximizers); none is asserted realizable. This is a
complete relaxation certificate, not a graph-realization search or an optimum.

Route B. The frozen row has cap 265, S4 base 112, source NB_CERTIFICATES[883].
W=829, sum C(6+d,3)=2336, A_max=floor(596/3)=198. At each 22<=T<=cap,
 K4=max(0,ceil((2336-10*(829-3T))/4)); A=min(K4,198);
 S4=max(112,448*A+679*(K4-A)); S3=2800*829+11872*(T-22)-30800;
 U(T)=372228640-63838600+S3-floor(4*S4/7).
Every integer term is checked with independently arranged exact rationals and
the two frozen integer/rational functions, extracted without importing their
research pipelines. All prefix maxima, ceilings, floors and maximizing T are
checked. Cap 261 gives 313362012 versus 313397860, a reduction of 35848.
The maximum sufficient cap for strict reduction is 264; strict incumbent
closure needs 250. Owner exclusion is not proved. Family gain is not claimed.
"""

from __future__ import annotations

import ast
import hashlib
import json
import resource
import subprocess
import sys
import unittest
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from fractions import Fraction
from functools import cache
from itertools import combinations, combinations_with_replacement, product
from math import comb
from pathlib import Path
from time import process_time
from types import SimpleNamespace
from typing import Any

TASK_ID = "B649_NEXT_FAMILY_OWNER_66665555554421100000_R1"
PROFILE_ID = "66665555554421100000"
PROFILE = tuple(map(int, PROFILE_ID))
CORE = tuple(d for d in PROFILE if d)
FROZEN_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
FROZEN_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
ROOT = Path(__file__).resolve().parents[3]
RESULT_DIR = "docs/research/matrix-native-results/"
SOURCE_DIR = "src/lottolab/research/"
SEVEN = RESULT_DIR + "b649-min-s2-next-owner-core-zero-t256-cert-r1-result.json"
SIX = RESULT_DIR + "b649-min-s2-six-row-existing-s4-family-authority-r1-result.json"
ARCHIVE = RESULT_DIR + "b649-min-s2-six-row-existing-s4-family-authority-r1-sources/s4-result.json"
SPLIT = SOURCE_DIR + "b649_k20_min_s2_topw12_split_cap_certificate_r1.py"
W808 = SOURCE_DIR + "b649_k20_min_s2_nb_w808_frontier_r1.py"
R4 = SOURCE_DIR + "b649_k20_min_s2_realizable_core_class_bound_r4.py"
R5 = SOURCE_DIR + "b649_k20_min_s2_dangerous_core_realizability_r5.py"
R10 = SOURCE_DIR + "b649_k20_min_s2_next_distinct_plateau_r10.py"
R28 = SOURCE_DIR + "b649_k20_min_s2_current_cursor_class_owner_chase_r28.py"
NB = SOURCE_DIR + "b649_k20_min_s2_nb_degree_cap_frontier_r1.py"
FROZEN_HASHES = {
    SEVEN: "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743",
    SIX: "1f94b064ab7392b88cf4c18ca4d3cb164305601ea9bc2b0f2174c0cddb185e5f",
    ARCHIVE: "e376c3c15a767bdc75fe937f8ad36adf2ae94cc705628caccfab7f655c55852c",
    SPLIT: "dd31017a685c809f494b359b7eece3fb3d832aef7f55699f7872dec53e25f784",
    W808: "0715cea1fd5fafa3006a0bc10715840764e41213448f9353042fe51a64412a42",
    R4: "cbc57debfcc037b8be605f9c3e157dba9029fbbcca50fa05dcff99390066edec",
    R5: "ad2c524bcdb716af1f1f744435576376499e3f39c3a744aec613542c41964487",
    R10: "7a5dab79591f1fa59c2012a55ab89d3711ec4fc93ddfeb05245260c0bbd92ffb",
    R28: "72d7462a4cf32ed6932e81c6e62819e351e4b289246fd0644e5696b70b832fb0",
    NB: "0084c857032a1a4f469659562a5e22cb3159c5e81d099cb4ceb87b01d663ca07",
}
OLD_CAP = 265
S4_BASE = 112
OLD_BOUND = 313_397_860
INCUMBENT = 313_263_888
ROW_SOURCE = "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:NB_CERTIFICATES[883]"
RESULT_PATH = ROOT / RESULT_DIR / "b649-next-family-owner-66665555554421100000-r1-result.json"
TEST_FILE = "test_b649_next_family_owner_66665555554421100000_r1.py"
FOCUSED_COMMAND = (
    "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src "
    "/opt/homebrew/opt/python@3.13/bin/python3.13 -B -m "
    "lottolab.research.b649_next_family_owner_66665555554421100000_r1 --self-check"
)
ZERO_EDGES = tuple(combinations(range(5), 2))
Term = tuple[int, int, int, int, int, int]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def check_frozen_bytes(path: str, data: bytes) -> None:
    require(
        path in FROZEN_HASHES and digest(data) == FROZEN_HASHES[path],
        f"wrong frozen source: {path}",
    )


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def check_source_row(row: Mapping[str, object], base: int) -> None:
    require(
        (row.get("PROFILE_ID"), row.get("BOUND"), row.get("TRIANGLE_CAP"), row.get("SOURCE"), base)
        == (PROFILE_ID, OLD_BOUND, OLD_CAP, ROW_SOURCE, S4_BASE),
        "frozen Profile/Row/cap/S4/source mismatch",
    )


def literal(source: bytes, name: str) -> Any:
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"frozen literal absent: {name}")


def extract_functions(source: bytes, names: Sequence[str], namespace: dict[str, Any]) -> None:
    """Execute only named, pinned pure arithmetic functions, never a module/import."""
    definitions = [
        node
        for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    require({node.name for node in definitions} == set(names), "frozen function absent")
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    tree = ast.fix_missing_locations(ast.Module(body=[future, *definitions], type_ignores=[]))
    exec(compile(tree, "<pinned-pure-arithmetic>", "exec"), namespace)


@cache
def frozen_authority() -> dict[str, Any]:
    require(
        git("show", "-s", "--format=%H", FROZEN_HEAD).decode().strip() == FROZEN_HEAD,
        "frozen HEAD mismatch",
    )
    require(
        git("rev-parse", FROZEN_HEAD + "^{tree}").decode().strip() == FROZEN_TREE,
        "frozen TREE mismatch",
    )
    require(
        git("remote", "get-url", "origin").decode().strip()
        == "https://github.com/kelvinhuang0327/MathStatisticalAnalysis.git",
        "wrong repository",
    )
    blobs = {}
    for path in FROZEN_HASHES:
        blob = git("show", FROZEN_HEAD + ":" + path)
        check_frozen_bytes(path, blob)
        require((ROOT / path).read_bytes() == blob, f"working frozen bytes changed: {path}")
        blobs[path] = blob
    seven, six, archive = (json.loads(blobs[p]) for p in (SEVEN, SIX, ARCHIVE))
    row = next(
        r for r in archive["FINAL_FAMILY"]["ROWS_ABOVE_CURSOR"] if r["PROFILE_ID"] == PROFILE_ID
    )
    base = literal(blobs[R5], "K20_REUSED_S4_LOWER_BOUND")
    scope: dict[str, Any] = {
        "K20_REUSED_S4_LOWER_BOUND": base,
        "SEVEN_INACTIVE_TICKET_S4_LOWER_BOUND": literal(
            blobs[R10], "SEVEN_INACTIVE_TICKET_S4_LOWER_BOUND"
        ),
    }
    extract_functions(blobs[R28], ("profile_s4_floor",), scope)
    require(scope["profile_s4_floor"](PROFILE) == base, "S4 base not frozen profile floor")
    check_source_row(row, base)
    require(
        six["RESOLVED_ROW_BOUNDS"][PROFILE_ID] == OLD_BOUND
        and PROFILE_ID not in seven["CERTIFICATE_PROFILE_IDS"]
        and set(six["CERTIFICATE_PROFILE_IDS"]).issubset(seven["CERTIFICATE_PROFILE_IDS"])
        and seven["ROWS_CHANGED_FROM_SIX_ROW"] == ["66555555555540000000"]
        and seven["ROW_UPDATE"]["PROFILE_ID"] == "66555555555540000000",
        "seven-row authority changed the target",
    )
    require(six["INCUMBENT"] == seven["INCUMBENT"] == INCUMBENT, "frozen incumbent changed")
    return {
        "BLOBS": blobs,
        "ROW": row,
        "SOURCE_S4_BASE": base,
        "SCOPE": "TARGET_ONLY_LOOKUP_NO_4647_ROW_REPLAY",
        "HASHES": dict(FROZEN_HASHES),
    }


def premises(
    profile: Sequence[int] = PROFILE,
    *,
    capacity: int = 6,
    triple_count: int = 22,
    pair_count: int = 27,
    linear: bool = True,
) -> dict[str, Any]:
    require(
        all(type(d) is int for d in profile) and tuple(sorted(profile, reverse=True)) == PROFILE,
        "wrong degree profile premise",
    )
    require(
        capacity == 6 and triple_count == 22 and pair_count == 27 and linear,
        "six-label linear 22-triple/27-pair premise required",
    )
    g = tuple(capacity + d for d in profile)
    h = tuple(19 - v for v in g)
    edges = sum(g) // 2
    goodman = Fraction(comb(20, 3)) - Fraction(sum(x * y for x, y in zip(g, h, strict=True)), 2)
    other = comb(20, 3) - 18 * (comb(20, 2) - edges) + sum(comb(v, 2) for v in h)
    k, z = len(CORE), PROFILE.count(0)
    h0 = sum(13 - z - d for d in CORE)
    a0 = z * (z - 7)
    constant = goodman - Fraction(z * h0 + k * a0, 2)
    require(
        (sum(profile), sum(d * d for d in profile), k, z, edges, goodman, other, constant)
        == (66, 332, 15, 5, 93, 295, 295, 235),
        "degree/Goodman/split recount failed",
    )
    return {
        "DEGREE_SUM": sum(profile),
        "DEGREE_SQUARE_SUM": sum(d * d for d in profile),
        "DEGREE_COUNTS": dict(sorted(Counter(profile).items(), reverse=True)),
        "CORE_COUNT": k,
        "ZERO_COUNT": z,
        "G_EDGES": edges,
        "H_EDGES": 190 - edges,
        "GOODMAN_CONSTANT": int(goodman),
        "COMPLEMENT_CHOOSE2_SUM": sum(comb(v, 2) for v in h),
        "G_DEGREES": g,
        "H_DEGREES": h,
        "CORE_H_DEGREE_BASE_SUM": h0,
        "ZERO_H_DEGREE_BASE_SUM": a0,
        "F_CONSTANT": int(constant),
        "SUPPORT_PREMISES": "20 six-label tickets; 22 triples; 27 pairs; every support pair unique",
    }


def check_domains(sigma_domains: Mapping[int, Sequence[int]], zeta_domain: Sequence[int]) -> None:
    expected = {d: tuple(range(7 - d)) for d in set(CORE)}
    require(
        {d: tuple(v) for d, v in sigma_domains.items()} == expected
        and tuple(zeta_domain) == tuple(range(2, 7)),
        "incomplete or invalid full-profile domains",
    )


def sigma_vectors() -> Iterable[tuple[int, ...]]:
    groups = sorted(Counter(CORE).items(), reverse=True)
    options = [tuple(combinations_with_replacement(range(7 - d), n)) for d, n in groups]
    for pieces in product(*options):
        yield tuple(x for piece in pieces for x in piece)


def zero_graph(mask: int) -> tuple[tuple[int, ...], tuple[tuple[int, int], ...], int]:
    require(type(mask) is int and 0 <= mask < 1024, "invalid five-point graph mask")
    edges = tuple(e for i, e in enumerate(ZERO_EDGES) if mask & (1 << i))
    degrees = tuple(sum(v in e for e in edges) for v in range(5))
    edge_set = set(edges)
    triangles = sum(
        all(e in edge_set for e in combinations(tri, 2)) for tri in combinations(range(5), 3)
    )
    return tuple(a + 2 for a in degrees), edges, triangles


def zero_table(masks: Iterable[int] = range(1024)) -> tuple[dict[Any, Any], Counter[Any]]:
    masks = tuple(masks)
    require(
        len(masks) == 1024 and set(masks) == set(range(1024)),
        "zero relaxation must cover all 1024 masks exactly once",
    )
    table: dict[Any, Any] = {}
    counts: Counter[Any] = Counter()
    for mask in sorted(masks):
        zeta, edges, triangles = zero_graph(mask)
        shape = tuple(sorted(zeta))
        counts[shape] += 1
        for q in range(12):
            cost = triangles + sum(max(0, zeta[u] + zeta[v] - q) for u, v in edges)
            key = shape, q
            table[key] = min(table.get(key, (cost, mask)), (cost, mask))
    require(sum(counts.values()) == 1024 and len(counts) == 31, "zero graph coverage mismatch")
    return table, counts


def core_floor(sigma: Sequence[int]) -> tuple[int, int]:
    require(
        len(sigma) == 15
        and all(type(s) is int and 0 <= s <= 6 - d for s, d in zip(sigma, CORE, strict=True)),
        "invalid core pair capacity",
    )
    total = 0
    for i, (s, d) in enumerate(zip(sigma, CORE, strict=True)):
        h = 8 - d + s
        weights = sorted(max(0, s + other - 5) for j, other in enumerate(sigma) if j != i)
        require(0 <= h <= len(weights), "core complement degree out of range")
        total += sum(weights[:h])
    return (total + 1) // 2, total


@dataclass(frozen=True)
class RelaxedRow:
    sigma: tuple[int, ...]
    zeta: tuple[int, ...]
    f: int
    core_floor: int
    directed_weight_sum: int
    zero_floor: int
    zero_minimizer_mask: int
    q: int
    bound: int


@cache
def relaxation() -> tuple[tuple[RelaxedRow, ...], dict[str, Any]]:
    data = premises()
    check_domains({d: range(7 - d) for d in set(CORE)}, range(2, 7))
    table, counts = zero_table()
    by_sum: dict[int, list[tuple[int, ...]]] = defaultdict(list)
    for shape in sorted(counts):
        by_sum[sum(shape)].append(shape)
    rows = []
    vectors = tuple(sigma_vectors())
    count_formula = 1
    for d, n in Counter(CORE).items():
        count_formula *= comb(6 - d + n, n)
    product_count = len(vectors)
    require(product_count == count_formula == 4410, "core symmetry coverage mismatch")
    for sigma in vectors:
        r, q = sum(sigma), sum(s > 0 for s in sigma)
        pk, directed = core_floor(sigma)
        h = tuple(8 - d + s for d, s in zip(CORE, sigma, strict=True))
        for zeta in by_sum.get(r, []):
            a = tuple(v - 2 for v in zeta)
            f = (
                data["F_CONSTANT"]
                + sum(s * (s - d - 2) for d, s in zip(CORE, sigma, strict=True))
                + sum(v * (v - 2) for v in zeta)
            )
            raw = (
                Fraction(data["GOODMAN_CONSTANT"])
                - Fraction(5 * sum(h) + 15 * sum(a), 2)
                + sum(s * v for s, v in zip(sigma, h, strict=True))
                + sum(s * v for s, v in zip(zeta, a, strict=True))
            )
            require(
                raw == f and sum(h) == 54 + r and sum(a) == r - 10,
                "exact split identity integer/rational mismatch",
            )
            pz, mask = table[zeta, q]
            rows.append(RelaxedRow(sigma, zeta, f, pk, directed, pz, mask, q, f - pk - pz))
    require(len(rows) == 3779, "balanced relaxation coverage mismatch")
    cap = max(row.bound for row in rows)
    report = {
        "CORE_VECTOR_COUNT": product_count,
        "ZERO_MASK_COUNT": sum(counts.values()),
        "ZERO_DEGREE_SHAPE_COUNT": len(counts),
        "BALANCED_CONFIGURATION_COUNT": len(rows),
        "MAX_F_WITH_P0": max(row.f for row in rows),
        "CAP_WITHOUT_CORE_FLOOR": max(row.f - row.zero_floor for row in rows),
        "CAP_WITHOUT_ZERO_FLOOR": max(row.f - row.core_floor for row in rows),
        "CAP": cap,
        "MAXIMIZERS": [asdict(row) for row in rows if row.bound == cap],
        "ALL_CONFIGURATION_SHA256": digest(canonical([asdict(row) for row in rows])),
        "BOUND_HISTOGRAM": dict(sorted(Counter(row.bound for row in rows).items())),
        "ZERO_MINIMUM_TABLE": [
            {
                "ZETA": shape,
                "LABELLED_GRAPH_COUNT": counts[shape],
                "COST_AND_MINIMIZER_MASK_BY_Q_0_TO_11": [table[shape, q] for q in range(12)],
            }
            for shape in sorted(counts)
        ],
        "FILTERS_OMITTED": [
            "core graphicality",
            "residual graphicality",
            "bipartite graphicality",
            "support realizability",
        ],
        "COMPLETENESS": "Every legal realization maps to one enumerated balanced configuration.",
        "ATTAINABILITY": "UNKNOWN; relaxation maximizers are not realization witnesses",
    }
    require(cap == 261, "new relaxation maximum changed")
    return tuple(rows), report


def check_cap_claim(cap: int, rows: Sequence[RelaxedRow]) -> None:
    require(type(cap) is int and len(rows) == 3779, "incomplete cap certificate")
    require(all(row.bound <= cap for row in rows), "cap below a relaxation configuration")


def nb_recount() -> tuple[int, int, int]:
    g = tuple(6 + d for d in PROFILE)
    w = sum(comb(v, 2) for v in g)
    floor = 0
    for i, v in enumerate(g):
        neighbours = sorted((u for j, u in enumerate(g) if j != i), reverse=True)[:v]
        m = sum(min(u - 1, v - 1) for u in neighbours)
        floor += comb(v, 2) - m // 2
    return w, floor, (w - floor) // 3


def route_term(t: int, *, base: int = S4_BASE) -> Term:
    require(type(t) is int and 22 <= t <= OLD_CAP, "T outside frozen envelope")
    g = tuple(6 + d for d in PROFILE)
    w, u = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g)
    outside = sum(d * (v - 2) for d, v in zip(PROFILE, g, strict=True))
    k4 = max(0, -(-(u - (max(g) - 2) * (w - 3 * t)) // 4))
    contained = min(k4, outside // 3)
    s4 = max(base, 448 * contained + 679 * (k4 - contained))
    s3 = 2800 * w + 11872 * (t - 22) - 30800
    return t, 372228640 - 63838600 + s3 - 4 * s4 // 7, k4, contained, s4, s3


def rational_term(t: int, *, base: int = S4_BASE) -> Term:
    require(type(t) is int and 22 <= t <= OLD_CAP, "T outside frozen envelope")
    g = tuple(6 + d for d in PROFILE)
    w = Fraction(sum(v * (v - 1) for v in g), 2)
    u = sum(Fraction(v * (v - 1) * (v - 2), 6) for v in g)
    a = Fraction(sum(d * (v - 2) for d, v in zip(PROFILE, g, strict=True)), 3).__floor__()
    k4 = max(0, ((u - (max(g) - 2) * (w - 3 * t)) / 4).__ceil__())
    contained = min(k4, a)
    s4 = max(base, 679 * k4 - 231 * contained)
    # Expanded local motif identity, independent of the collected integer form.
    s3 = 2800 * (w - 3 * t) + 20272 * (t - 22) + 7000 * 22
    exact = Fraction(372228640 - 63838600) + s3 - Fraction(4 * s4, 7)
    require(s3.denominator == 1, "noninteger S3")
    return t, exact.__ceil__(), k4, contained, s4, int(s3)


def check_route_term(term: Term) -> None:
    require(term == rational_term(term[0]), "Route-B rounding/arithmetic mismatch")


def frozen_route_terms(blobs: Mapping[str, bytes]) -> list[Term]:
    namespace: dict[str, Any] = {"Fraction": Fraction, "comb": comb}
    for name in (
        "K20_TICKET_CAPACITY",
        "K20_TRIPLE_SUPPORT_COUNT",
        "K20_S1",
        "K20_S2",
        "K20_S3_WEDGE_COEFFICIENT",
    ):
        namespace[name] = literal(blobs[R4], name)
    for name in ("K4_LIGHT", "K4_HEAVY"):
        namespace[name] = literal(blobs[W808], name)
    extract_functions(blobs[R4], ("s3_sum_from_wedges_and_triangles",), namespace)
    extract_functions(
        blobs[W808], ("ceil_fraction", "floor_fraction", "exact_route_b_terms"), namespace
    )
    rational = namespace["exact_route_b_terms"]
    namespace["prior"] = SimpleNamespace(w8=SimpleNamespace(exact_route_b_terms=rational))
    extract_functions(blobs[SPLIT], ("route_b_terms",), namespace)
    integers = namespace["route_b_terms"](PROFILE, OLD_CAP, S4_BASE)
    require(integers == rational(PROFILE, OLD_CAP, S4_BASE), "frozen Route-B functions differ")
    return integers


def thresholds(terms: Sequence[Term]) -> tuple[int, int]:
    require([row[0] for row in terms] == list(range(22, OLD_CAP + 1)), "missing T term")
    prefix_max, strict, closure = -1, -1, -1
    for t, bound, *_ in terms:
        prefix_max = max(prefix_max, bound)
        if prefix_max < OLD_BOUND:
            strict = t
        if prefix_max < INCUMBENT:
            closure = t
    return strict, closure


def negative_checks(authority: Mapping[str, Any], rows: Sequence[RelaxedRow]) -> dict[str, str]:
    """Actual fixture/seam mutations, each required to raise the intended guard."""
    cases = {
        "WRONG_CAP_260": lambda: check_cap_claim(260, rows),
        "MISSING_ZERO_MASK": lambda: zero_table(range(1023)),
        "MISSING_CORE_DOMAIN_ENDPOINT": lambda: check_domains(
            {d: range(7 - d) if d != 1 else range(5) for d in set(CORE)}, range(2, 7)
        ),
        "WRONG_ZERO_LOWER_BOUND": lambda: check_domains(
            {d: range(7 - d) for d in set(CORE)}, range(1, 7)
        ),
        "NONLINEAR_SUPPORT_PREMISE": lambda: premises(linear=False),
        "WRONG_DEGREE_PROFILE": lambda: premises(
            (6,) * 4 + (5,) * 6 + (4,) * 2 + (3,) + (1,) + (0,) * 6
        ),
        "WRONG_SOURCE_ROW_CAP": lambda: check_source_row(
            {**authority["ROW"], "TRIANGLE_CAP": 266}, S4_BASE
        ),
        "WRONG_SOURCE_S4_BASE": lambda: check_source_row(authority["ROW"], 1680),
        "WRONG_SOURCE_LOCATOR": lambda: check_source_row(
            {**authority["ROW"], "SOURCE": ROW_SOURCE.replace("883", "882")}, S4_BASE
        ),
        "WRONG_FROZEN_RESULT": lambda: check_frozen_bytes(SEVEN, authority["BLOBS"][SEVEN] + b" "),
        "WRONG_FROZEN_FORMULA": lambda: check_frozen_bytes(
            SPLIT, authority["BLOBS"][SPLIT].replace(b"679", b"678", 1)
        ),
        "K4_FLOOR_INSTEAD_OF_CEIL": lambda: check_route_term(
            (200, *route_term(200)[1:2], route_term(200)[2] - 1, *route_term(200)[3:])
        ),
        "BOUND_OFF_BY_ONE": lambda: check_route_term(
            (261, route_term(261)[1] - 1, *route_term(261)[2:])
        ),
    }
    output = {}
    for name, action in cases.items():
        try:
            action()
        except AssertionError as error:
            output[name] = "PASS_REJECTED: " + str(error)
        else:
            raise AssertionError(f"negative case accepted: {name}")
    return output


@cache
def compute_result() -> dict[str, Any]:
    authority = frozen_authority()
    data = premises()
    rows, report = relaxation()
    cap = report["CAP"]
    check_cap_claim(cap, rows)
    old = [route_term(t) for t in range(22, OLD_CAP + 1)]
    for term in old:
        check_route_term(term)
    require(old == frozen_route_terms(authority["BLOBS"]), "new/frozen all-T terms differ")
    new = [route_term(t) for t in range(22, cap + 1)]
    require(new == old[: len(new)], "new envelope not original prefix")
    old_best = max(old, key=lambda term: (term[1], term[0]))
    best = max(new, key=lambda term: (term[1], term[0]))
    strict, closure = thresholds(old)
    require(
        nb_recount() == (829, 34, OLD_CAP) and old_best[1] == OLD_BOUND,
        "source NB cap/original bound recount differs",
    )
    require(best[1] < OLD_BOUND and (strict, closure) == (264, 250), "strict gain not proved")
    negatives = negative_checks(authority, rows)
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "STRICT_OWNER_BOUND_REDUCTION_PROVED",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "INDEPENDENT_JUDGE": "NOT_RUN",
        "FROZEN_HEAD": FROZEN_HEAD,
        "FROZEN_TREE": FROZEN_TREE,
        "FROZEN_RESULT_SHA256": FROZEN_HASHES[SEVEN],
        "FROZEN_HEAD_VERIFIED": True,
        "FROZEN_TREE_VERIFIED": True,
        "FROZEN_RESULT_SHA256_VERIFIED": True,
        "FROZEN_SOURCE_HASHES": authority["HASHES"],
        "SOURCE_ROW": authority["ROW"],
        "AUTHORITY_LOOKUP_SCOPE": authority["SCOPE"],
        "PROFILE_ID": PROFILE_ID,
        "DEGREE_PROFILE": "6^4,5^6,4^2,2^1,1^2,0^5",
        **data,
        "SOURCE_T_CAP": OLD_CAP,
        "SOURCE_S4_BASE": S4_BASE,
        "SOURCE": ROW_SOURCE,
        "OLD_BOUND": OLD_BOUND,
        "INCUMBENT": INCUMBENT,
        "PROOF": __doc__,
        "EXACT_TRIANGLE_IDENTITY": "T=235+sum sigma_i(sigma_i-d_i-2)+sum zeta_u(zeta_u-2)-P",
        "NONNEGATIVE_REMAINDER": "P=t(M)+t(Q)+sum_M c_Z+sum_Q c_K>=L_K+L_Z>=0",
        "LOAD_BEARING_PREMISES": [
            data["SUPPORT_PREMISES"],
            "exact target degree multiset",
            "sigma_i<=6-d_i",
            "2<=zeta_u<=6",
            "equal cross-edge sums",
            "h_i=8-d_i+sigma_i",
            "Q degree=zeta-2",
            "zero core neighbours lie in the q active core vertices",
            "all 1024 zero graphs and all 4410 core degree multisets included",
        ],
        "RELAXATION_COMPLETENESS": "PASS_FULL_PROFILE_SUPERSET",
        "PROOF_SCOPE": "FULL_PROFILE",
        "RELAXATION": report,
        "PROVED_T_CAP": cap,
        "NEW_ADMISSIBLE_BOUND": best[1],
        "OWNER_BOUND_REDUCTION": OLD_BOUND - best[1],
        "STRICT_REDUCTION_THRESHOLD": strict,
        "INCUMBENT_CLOSURE_THRESHOLD": closure,
        "OWNER_EXCLUSION_PROVED": best[1] < INCUMBENT,
        "GAP_ABOVE_INCUMBENT": best[1] - INCUMBENT,
        "ROUTE_B_INTEGER_RECOUNT": "PASS_EVERY_T",
        "EXACT_RATIONAL_CROSSCHECK": "PASS_EVERY_T",
        "T_TERM_COUNT": len(new),
        "UNIQUE_T_TERMS_CHECKED": len(old),
        "ALL_T_TERMS": new,
        "ORIGINAL_ALL_T_TERMS": old,
        "ARGMAX_T": [term[0] for term in new if term[1] == best[1]],
        "PEAK_TERM": best,
        "ORIGINAL_PEAK_TERM": old_best,
        "ROUNDING_CHECK": {
            "K4": "ceil(excess/4); half-integer excesses retained",
            "A_MAX": "floor(596/3)=198",
            "S4_CREDIT": "floor(4*S4/7); all actual S4 terms here are divisible by 7",
            "BOUND": "ceil(exact rational upper bound)",
            "PREFIX_MAXIMA": "all 244 prefix maxima evaluated, no monotonicity assumed",
        },
        "NEGATIVE_CASE_RESULTS": negatives,
        "FAMILY_BOUND_GAIN_CLAIMED": 0,
        "NEW_WINNING_OUTCOMES": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "HEAVY_SOLVER_STARTED": "NO",
        "FULL_4647_ROW_PIPELINE": "NOT_RUN",
        "SOLVER_CALLS": 0,
        "CPU_PROCESS_COUNT": 1,
        "CPU_PROCESS_COUNT_SCOPE": "maximum concurrent CPU-bound processes",
        "PUSH": "NOT_RUN",
        "MERGE": "NOT_RUN",
        "PRODUCTION_MUTATION": "NONE",
        "CLEANUP_DISPOSITION": "RETAIN",
    }


def check_result_bytes(payload: bytes, expected: Mapping[str, Any]) -> dict[str, Any]:
    """Reproduce every scientific field; wall/CPU measurements are historical receipts."""
    stored = json.loads(payload)
    normalized = json.loads(canonical(expected))
    require(
        isinstance(stored, dict) and {key: stored.get(key) for key in normalized} == normalized,
        "stored scientific result differs from exact recount",
    )
    return stored


def main() -> None:
    require(sys.argv[1:] == ["--self-check"], "use the focused --self-check entrypoint")
    start = process_time()
    # Reserve 15 seconds for earlier bounded exploration and ordinary command overhead.
    resource.setrlimit(resource.RLIMIT_CPU, (105, 106))
    scientific = compute_result()
    result = dict(scientific)
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests/unit"), pattern=TEST_FILE)
    outcome = unittest.TextTestRunner(verbosity=2).run(suite)
    require(outcome.wasSuccessful(), "focused tests failed; result not written")
    cpu = process_time() - start
    require(cpu + 15 < 120, "cumulative reserved CPU budget exceeded")
    result.update(
        {
            "FOCUSED_TEST_COMMAND": FOCUSED_COMMAND,
            "FOCUSED_TEST_EXIT_CODE": 0,
            "FOCUSED_TEST_COUNT": outcome.testsRun,
            "CPU_SECONDS": round(cpu, 6),
            "CPU_SECONDS_SCOPE": "measured focused acceptance process (research plus tests)",
            "EARLIER_BOUNDED_EXPLORATION_CPU_RESERVED_SECONDS": 15,
            "CPU_SECONDS_LIMIT": 120,
            "ACCEPTANCE_PROCESS_CPU_LIMIT": 105,
            "PRIOR_EXPLORATION": [
                {
                    "STATUS": "ARITHMETIC_DISPLAY_INDEX_ERROR_AFTER_RELAXATION_COMPLETED",
                    "F_CAP": 275,
                    "CORE_FLOOR_CAP": 269,
                    "MEASURED_CPU_SECONDS": 0.172545,
                },
                {
                    "STATUS": "SUPERSEDED_GRAPHICAL_RELAXATION",
                    "COUNT": 2743,
                    "CAP": 261,
                    "MEASURED_CPU_SECONDS": 0.210624,
                },
                {
                    "STATUS": "SIMPLIFIED_COMPLETE_RELAXATION_CONFIRMED",
                    "COUNT": 3779,
                    "CAP": 261,
                    "MEASURED_CPU_SECONDS": 0.175941,
                },
            ],
            "RESULT_SHA256": "EXTERNAL_GIT_HANDOFF: hashing this field into itself is undefined",
            "LOCAL_COMMIT_HEAD": "EXTERNAL_GIT_HANDOFF: commit cannot contain its own Git identity",
            "LOCAL_COMMIT_TREE": "EXTERNAL_GIT_HANDOFF: observed after the sole authorized commit",
            "WORKTREE_CLEAN": "EXTERNAL_GIT_HANDOFF: observed after commit",
        }
    )
    if RESULT_PATH.exists():
        payload = RESULT_PATH.read_bytes()
        stored = check_result_bytes(payload, scientific)
        require(
            stored["FOCUSED_TEST_COMMAND"] == FOCUSED_COMMAND
            and stored["FOCUSED_TEST_EXIT_CODE"] == 0
            and stored["FOCUSED_TEST_COUNT"] == outcome.testsRun,
            "stored focused-test receipt differs",
        )
    else:
        payload = canonical(result)
        with RESULT_PATH.open("xb") as output:
            output.write(payload)
    print(
        json.dumps(
            {
                "TASK_STATUS": result["TASK_STATUS"],
                "PROVED_T_CAP": result["PROVED_T_CAP"],
                "NEW_ADMISSIBLE_BOUND": result["NEW_ADMISSIBLE_BOUND"],
                "OWNER_BOUND_REDUCTION": result["OWNER_BOUND_REDUCTION"],
                "CPU_SECONDS_THIS_VERIFICATION": round(cpu, 6),
                "RESULT_SHA256": digest(payload),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
