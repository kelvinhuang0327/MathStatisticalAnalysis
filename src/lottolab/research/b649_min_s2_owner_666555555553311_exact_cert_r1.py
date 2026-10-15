"""Universal exact-profile certificate for 66655555555331100000.

Scope and coverage. Assume precisely twenty tickets, six distinct labels per
ticket, 22 labels on triples and 27 on pairs, and at most one shared label
per ticket pair. The 66 triple incidences have degrees d=6^3,5^8,3^2,1^2,0^5.
Every triple supplies three distinct edges and every pair one, so G is simple,
g=6+d, E=93, W=827, J=sum C(g,3)=2318. Counting mixed vertex triples gives
T(G)+T(H)=C(20,3)-sum g(19-g)/2=293, H=complement(G).

Exact split identity. Put K={d>0}, Z={d=0}, |K|=15, |Z|=5. Write
sigma_x=|N_G(x) intersect Z|, zeta_u=|N_G(u) intersect K|, r=sum sigma=sum zeta,
M=H[K], N=H[Z], m_x=8-d_x+sigma_x, n_u=zeta_u-2. A cross edge uses a
pair support, hence 0<=sigma_x<=min(5,6-d_x); a zero vertex has six
G-neighbours, hence 2<=zeta_u<=6. M,N are simple; G[Z] has degree 6-zeta.
Every legal realization therefore has graphical m and 6-zeta, and a
bipartite cross graph of degree (sigma,zeta). These are necessary conditions,
not sufficient support-realizability conditions. Sorting sigma only within
each equal-d class, and sorting the zero vertices, preserves every condition
and score. All 1890 sigma multisets and all 126 zeta multisets are considered;
31 zeta multisets are graphical, and 1661 combined states survive.

For each M edge xy, its cross-shore H triangle count is
5-sigma_x-sigma_y+c_Z(x,y); for each N edge uv it is
15-zeta_u-zeta_v+c_K(u,v), where c counts common G-neighbours. Thus exactly
 T(H)=60+10r-sum sigma*m-sum zeta*n+P,
 P=T(M)+T(N)+sum_{E(M)}c_Z+sum_{E(N)}c_K.
Here 5e(M)+15e(N)=60+10r, since 2e(M)=54+r, 2e(N)=r-10.
All four terms in P are nonnegative counts. The common-neighbour sums equal
sum_u e(M[N_G(u) intersect K]) and sum_x e(N[N_G(x) intersect Z]).
For degrees a and e=sum a/2, every s-subset spans at least
max(0, sum of the s smallest a-e) edges: sum degrees on that subset is at
most e plus its internal edge count. This bounds both common-neighbour sums.

Triangle lower bounds. For a simple graph F with n vertices and degrees a:
(i) 3T>=sum a^2-ne, by summing |N(i) intersect N(j)|>=a_i+a_j-n over edges.
(ii) For the h largest degrees, at least
ell=max(0,ceil((sum_top a-sum_out min(h,a))/2)) edges lie within the prefix.
Their common-neighbour counts total at least the ell smallest pair weights
max(0,a_i+a_j-n). A triangle entirely in the prefix is counted three times,
and one with two prefix vertices once; subtracting 2*C(h,3) gives a valid
lower bound on all triangles. Maxima, not sums, combine bounds on T(F).
(iii) New pair-case bound: fix u,v of degrees a,b. If uv is an edge, at least
max(0,a+b-n) triangles contain it. If uv is absent, R=F-{u,v} has e-a-b
edges; u has all a neighbours in R. Edges not induced by N(u) touch the
n-2-a excluded vertices. Their degrees in R are at most their degrees in F,
whose sum is at most the sum of the n-2-a largest remaining degrees. Hence
e(F[N(u)])>=max(0,e-a-b-largest_sum(n-2-a)), and likewise for v.
With uv absent the triangles through u and through v are disjoint, so these
two lower bounds add. Take the minimum of the two cases and then the maximum
over pairs. A case is discarded only if degrees zero rule out an edge, or
max(a,b)>n-2 / e<a+b rule out a nonedge. Every possible case is retained.
No assertion about the two d=1 triple shadows, and no d=2 lemma, is used.

Subtract the four independently valid remainder floors from the exact split
score. Exhausting the entire necessary-condition domain yields T(G)<=249.
The state maximum is a relaxation extremum, not a legal attainment claim.
Enumerator A uses products/Erdos-Gallai/core-side Gale-Ryser and integer
arithmetic. B uses histogram recursion, all 1024 labelled zero graphs,
Havel-Hakimi/zero-side Gale-Ryser, and separate Fraction formulas. Full state
records, including every correction, must agree; neither calls the other.

Route B is the immutable r32 evaluator, without S5. At each integer t,
q=max(0,ceil((J-(gmax-2)(W-3t))/4)) bounds K4 count: every nonedge in a
neighbourhood spoils at most gmax-2 neighbour triples; summing gives 4q.
A K4 contains at most one triple support. Summing d(g-2)/3 bounds contained
K4s by 197. Exact local S4 weights are 448 with a triple and 679 without, so
S4>=max(112,679q-231min(q,197)). The expression increases with q. Exact
S3=2800(W-3t)+20272(t-22)+7000*22. Pair-linearity bounds winners on seven
labels by 7; for r=0..7, 1[r>0]<=r-C(r,2)+C(r,3)-4*C(r,4)/7. Therefore
UB(t)=ceil(372228640-63838600+S3-4*S4/7). The negative S4 coefficient
requires a lower floor. Full old t=22..265 and new t=22..249 domains are
recomputed term by term with the pinned evaluator and independent Fractions.
Exactly one resolved bound changes; the full cursor and other rows are kept.
Historical solver/R15/Judge caveats remain pinned and are never upgraded.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import json
import os
import subprocess
import sys
from collections.abc import Iterator, Mapping
from fractions import Fraction
from functools import cache
from itertools import combinations, combinations_with_replacement, product
from math import ceil, comb
from pathlib import Path
from typing import cast

from . import b649_k20_min_s2_route_b_current_owner_refinement_r32 as route
from . import b649_min_s2_advanced_11row_exact_adoption_r1 as local

type Document = dict[str, object]
type Degrees = tuple[int, ...]
type State = tuple[Degrees, Degrees]
type Term = tuple[int, int, int, int, int, int]

ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "B649_MIN_S2_OWNER_666555555553311_EXACT_CERT_R1"
OWNER_CONVERSATION_ID = "01a13d88-1e28-7662-afd7-5141268673a8"
PROFILE = "66655555555331100000"
D = tuple(map(int, PROFILE))
CORE = D[:15]
GROUPS = ((6, 3, 0), (5, 8, 1), (3, 2, 3), (1, 2, 5))
BASE_HEAD = "bee6acaaf9d2781e2aae560138d8be99fb4789ed"
BASE_TREE = "7b382a405d8d734763b477aa88efafeba2e1ed9b"
DIRECTORY = "docs/research/matrix-native-results/"
BASE_RESULT = DIRECTORY + "b649-min-s2-w784-39-goodman-exact-authority-r1-result.json"
BASE_SHA = "bca4ad19aebb9808c952259d677a4a07381aa43392c38715c8265427960fe6f6"
R30_RESULT = DIRECTORY + "b649-k20-min-s2-current-cursor-dynamic-family-max-r30-result.json"
R30_SHA = "9ed94532cc2bff5de1569f10561fb8340238ff3b1b1c3ae129e6a4929014f6fe"
STEM = "b649_min_s2_owner_666555555553311_exact_cert_r1"
SOURCE = f"src/lottolab/research/{STEM}.py"
TEST = f"tests/unit/test_{STEM}.py"
RESULT = DIRECTORY + STEM.replace("_", "-") + "-result.json"
INCUMBENT = 313263888
OLD_BOUND = 313391740
MODEL = {"TICKETS": 20, "LABELS_PER_TICKET": 6, "TRIPLES": 22, "PAIRS": 27, "PAIR_LINEARITY": True}
PRIOR_TASK = "B649_MIN_S2_NEXT_RESOLVED_666555555553311_RESEARCH_R1"


def require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def render(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()


def obj(value: object) -> Document:
    require(isinstance(value, dict), "expected object")
    return cast(Document, value)


def integer(value: object) -> int:
    require(type(value) is int, "expected integer")
    return cast(int, value)


def ledger(value: object) -> dict[str, int]:
    return {k: integer(v) for k, v in obj(value).items()}


def git(*args: str) -> bytes:
    return subprocess.check_output(
        ["git", "-c", "core.fsmonitor=false", *args],
        cwd=ROOT,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )


def working_bytes(path: str) -> bytes:
    p = ROOT / path
    require(p.is_file() and not p.is_symlink(), "unsafe working source")
    return p.read_bytes()


def frozen(path: str, digest: str | None = None) -> bytes:
    meta = git("ls-tree", BASE_HEAD, "--", path).decode().strip().split("\t")
    require(len(meta) == 2 and meta[0].startswith("100644 blob ") and meta[1] == path, "blob mode")
    raw = git("cat-file", "blob", f"{BASE_HEAD}:{path}")
    require(digest is None or sha(raw) == digest, "immutable source SHA256")
    require(working_bytes(path) == raw, "working source mismatch")
    return raw


def load_base() -> Document:
    require(git("rev-parse", BASE_HEAD + "^{tree}").decode().strip() == BASE_TREE, "Base tree")
    return obj(json.loads(frozen(BASE_RESULT, BASE_SHA)))


def source_closure() -> dict[str, str]:
    pending, pins = [route.__name__], dict[str, str]()
    while pending:
        module = pending.pop()
        relative = "src/" + module.replace(".", "/") + ".py"
        if relative in pins:
            continue
        raw = frozen(relative)
        imported = importlib.import_module(module)
        filename = imported.__file__
        if filename is None:
            raise ValueError("import source missing")
        require(Path(filename).resolve() == ROOT / relative, "import source root")
        pins[relative] = sha(raw)
        package = module.rsplit(".", 1)[0]
        for node in ast.walk(ast.parse(raw)):
            if isinstance(node, ast.ImportFrom):
                prefix = node.module or ""
                if node.level:
                    parts = package.split(".")
                    head = ".".join(parts[: len(parts) + 1 - node.level])
                    prefix = head + ("." + prefix if prefix else "")
                if prefix.startswith("lottolab"):
                    pending.extend(
                        [prefix] if node.module else [prefix + "." + a.name for a in node.names]
                    )
            elif isinstance(node, ast.Import):
                pending.extend(a.name for a in node.names if a.name.startswith("lottolab"))
    require(not any(m.startswith("ortools") for m in sys.modules), "heavy solver loaded")
    return dict(sorted(pins.items()))


def facts(pid: str = PROFILE) -> Document:
    require(pid == PROFILE, "wrong profile")
    ds = tuple(map(int, pid))
    g = tuple(6 + x for x in ds)
    value = {
        "SUM_D": sum(ds),
        "E": sum(g) // 2,
        "W": sum(comb(x, 2) for x in g),
        "J": sum(comb(x, 3) for x in g),
        "GOODMAN": comb(20, 3) - sum(x * (19 - x) for x in g) // 2,
        "A_MAX": sum(x * (x + 4) for x in ds) // 3,
    }
    require(
        value == {"SUM_D": 66, "E": 93, "W": 827, "J": 2318, "GOODMAN": 293, "A_MAX": 197},
        "frozen degree facts",
    )
    return {"PROFILE": pid, "D": list(ds), "G": list(g), **value}


def graphical_eg(ds: Degrees) -> bool:
    a = sorted(ds, reverse=True)
    return (
        all(0 <= x < len(a) for x in a)
        and sum(a) % 2 == 0
        and all(
            sum(a[:h]) <= h * (h - 1) + sum(min(h, x) for x in a[h:]) for h in range(1, len(a) + 1)
        )
    )


def graphical_hh(ds: Degrees) -> bool:
    a = list(ds)
    if any(x < 0 or x >= len(a) for x in a):
        return False
    while a:
        a.sort(reverse=True)
        d = a.pop(0)
        if d > len(a):
            return False
        for i in range(d):
            a[i] -= 1
            if a[i] < 0:
                return False
    return True


@cache
def floors_a(ds: Degrees) -> tuple[int, int, int]:
    """Square, prefix and pair-case triangle lower bounds, integer formulation."""
    require(graphical_eg(ds), "invalid theorem assumption: simple graph degrees")
    n, e = len(ds), sum(ds) // 2
    square = max(0, -(-(sum(x * x for x in ds) - n * e) // 3))
    a = sorted(ds, reverse=True)
    prefix = square
    for h in range(1, n + 1):
        ell = max(0, -(-(sum(a[:h]) - sum(min(h, x) for x in a[h:])) // 2))
        weights = sorted(max(0, x + y - n) for x, y in combinations(a[:h], 2))
        require(ell <= len(weights), "invalid graphical prefix")
        prefix = max(prefix, sum(weights[:ell]) - 2 * comb(h, 3))
    pair = 0
    for i, j in combinations(range(n), 2):
        x, y = ds[i], ds[j]
        rest = sorted((ds[v] for v in range(n) if v not in (i, j)), reverse=True)
        cases: list[int] = []
        if x and y:
            cases.append(max(0, x + y - n))
        if max(x, y) <= n - 2 and e >= x + y:
            cases.append(
                max(0, e - x - y - sum(rest[: n - 2 - x]))
                + max(0, e - x - y - sum(rest[: n - 2 - y]))
            )
        require(cases, "invalid theorem assumption: no adjacency case")
        pair = max(pair, min(cases))
    return square, prefix, pair


@cache
def floors_b(ds: Degrees) -> tuple[int, int, int]:
    """Independent Fraction and excluded-set formulation; no call to floors_a."""
    require(graphical_hh(ds), "invalid theorem assumption: reference simple graph degrees")
    ordered = sorted(ds)
    count = len(ordered)
    edges = sum(ordered) // 2
    square = max(0, ceil(Fraction(sum(x * x for x in ordered) - count * edges, 3)))
    prefix = square
    for outside in range(count):
        inside = ordered[outside:]
        h = len(inside)
        forced = max(0, ceil(Fraction(sum(inside) - sum(min(h, x) for x in ordered[:outside]), 2)))
        weights = [max(0, inside[i] + inside[j] - count) for i in range(h) for j in range(i)]
        weights.sort()
        prefix = max(prefix, sum(weights[:forced]) - h * (h - 1) * (h - 2) // 3)
    pair = 0
    for j in range(count):
        for i in range(j):
            a, b = ordered[i], ordered[j]
            others = [v for k, v in enumerate(ordered) if k != i and k != j]
            candidates: list[int] = []
            if a > 0 and b > 0:
                candidates.append(max(0, a + b - count))
            if a < count - 1 and b < count - 1 and edges - a - b >= 0:
                # Sum of the excluded largest degrees, via the retained smallest.
                ua = sum(others) - sum(others[:a])
                ub = sum(others) - sum(others[:b])
                candidates.append(max(0, edges - a - b - ua) + max(0, edges - a - b - ub))
            require(candidates, "invalid theorem assumption: reference cases")
            pair = max(pair, min(candidates))
    return square, prefix, pair


def record_a(state: State) -> Document:
    s, z = state
    m = tuple(8 - d + x for d, x in zip(CORE, s, strict=True))
    n = tuple(x - 2 for x in z)
    raw = (
        233
        - 10 * sum(s)
        + sum(x * y for x, y in zip(s, m, strict=True))
        + sum(x * y for x, y in zip(z, n, strict=True))
    )
    ck = sum(max(0, sum(sorted(n)[:x]) - sum(n) // 2) for x in s)
    cz = sum(max(0, sum(sorted(m)[:x]) - sum(m) // 2) for x in z)
    fm, fn = floors_a(m), floors_a(n)
    return {
        "SIGMA": list(s),
        "ZETA": list(z),
        "R": sum(s),
        "M": list(m),
        "N": list(n),
        "RAW": raw,
        "C_K": ck,
        "C_Z": cz,
        "T_M_FLOORS": list(fm),
        "T_N_FLOORS": list(fn),
        "UPPER_WITHOUT_PAIR": raw - ck - cz - fm[1] - fn[1],
        "UPPER": raw - ck - cz - max(fm) - max(fn),
    }


def record_b(state: State) -> Document:
    sigma, zeta = state
    md = tuple(15 - 1 - (6 + d - s) for d, s in zip(CORE, sigma, strict=True))
    nd = tuple(4 - (6 - z) for z in zeta)
    mixed = (5 * sum(md) + 15 * sum(nd)) // 2
    mixed -= sum(sigma[i] * md[i] for i in range(15))
    mixed -= sum(zeta[j] * nd[j] for j in range(5))
    raw = 293 - mixed
    ck = sum(max(0, sum(nd) // 2 - sum(sorted(nd, reverse=True)[: 5 - s])) for s in sigma)
    cz = sum(max(0, sum(md) // 2 - sum(sorted(md, reverse=True)[: 15 - z])) for z in zeta)
    fm, fn = floors_b(md), floors_b(nd)
    return {
        "SIGMA": list(sigma),
        "ZETA": list(zeta),
        "R": sum(zeta),
        "M": list(md),
        "N": list(nd),
        "RAW": raw,
        "C_K": ck,
        "C_Z": cz,
        "T_M_FLOORS": list(fm),
        "T_N_FLOORS": list(fn),
        "UPPER_WITHOUT_PAIR": raw - ck - cz - fm[1] - fn[1],
        "UPPER": raw - ck - cz - max(fm) - max(fn),
    }


def enumerate_a() -> list[tuple[State, Document]]:
    options = [tuple(combinations_with_replacement(range(u + 1), n)) for _, n, u in GROUPS]
    zero = [
        z
        for z in combinations_with_replacement(range(2, 7), 5)
        if graphical_eg(tuple(6 - x for x in z))
    ]
    require(len(zero) == 31, "zero domain completeness")
    rows: list[tuple[State, Document]] = []
    signatures = 0
    for parts in product(*options):
        signatures += 1
        s = tuple(x for part in parts for x in part)
        m = tuple(8 - d + x for d, x in zip(CORE, s, strict=True))
        if not graphical_eg(m):
            continue
        for z in zero:
            if sum(s) != sum(z):
                continue
            desc = sorted(s, reverse=True)
            if all(sum(desc[:h]) <= sum(min(h, x) for x in z) for h in range(1, 16)):
                state = (s, z)
                rows.append((state, record_a(state)))
    require(signatures == 1890, "sigma domain completeness")
    return sorted(rows)


def histograms(n: int, upper: int, value: int = 0, prefix: Degrees = ()) -> Iterator[Degrees]:
    if value == upper:
        yield prefix + (value,) * n
    else:
        for count in range(n + 1):
            yield from histograms(n - count, upper, value + 1, prefix + (value,) * count)


def enumerate_b() -> list[tuple[State, Document]]:
    zero: set[Degrees] = set()
    edges = list(combinations(range(5), 2))
    for mask in range(1024):
        degrees = [0] * 5
        for bit, (i, j) in enumerate(edges):
            if mask & (1 << bit):
                degrees[i] += 1
                degrees[j] += 1
        zero.add(tuple(sorted(6 - d for d in degrees)))
    rows: list[tuple[State, Document]] = []
    for z in sorted(zero):
        for five in histograms(8, 1):
            for three in histograms(2, 3):
                left = sum(z) - sum(five) - sum(three)
                for one in histograms(2, 5):
                    if sum(one) != left:
                        continue
                    s = (0, 0, 0, *five, *three, *one)
                    m = tuple(8 - d + x for d, x in zip(CORE, s, strict=True))
                    if not graphical_hh(m):
                        continue
                    if not all(
                        sum(sorted(z, reverse=True)[:j]) <= sum(min(j, x) for x in s)
                        for j in range(1, 6)
                    ):
                        continue
                    state = (s, z)
                    rows.append((state, record_b(state)))
    return sorted(rows)


def domain_certificate() -> Document:
    a, b = enumerate_a(), enumerate_b()
    require(a == b, "independent enumeration/remainder disagreement or missing states")
    require(len(a) == len({s for s, _ in a}) == 1661, "finite domain completeness")
    states = [row for _, row in a]
    cap = max(integer(row["UPPER"]) for row in states)
    require(cap == 249, "wrong T cap or correction sign")
    require(max(integer(row["UPPER_WITHOUT_PAIR"]) for row in states) == 253, "prior split cap")
    return {
        "SIGMA_SIGNATURES": 1890,
        "RAW_ZETA_MULTISET_COUNT": 126,
        "ZETA_GRAPHICAL_COUNT": 31,
        "ZERO_GRAPHS_RECOUNTED": 1024,
        "RETAINED_STATES": len(states),
        "STATES_SHA256": sha(render(states)),
        "STATES": states,
        "CAP": cap,
        "WITHOUT_PAIR_CAP": 253,
        "ARGMAX": [s for s in states if s["UPPER"] == cap],
        "REALIZABILITY": "NECESSARY_CONDITION_RELAXATION; ATTAINMENT_NOT_ASSERTED",
        "COVERAGE_PROOF": __doc__,
    }


def current_authority(base: Document) -> Document:
    require(base["MODEL"] == MODEL, "invalid theorem assumption: frozen support model")
    rows = ledger(base["RESOLVED_ROW_BOUNDS"])
    require(rows.get(PROFILE) == OLD_BOUND, "target old bound")
    r30 = obj(json.loads(frozen(R30_RESULT, R30_SHA)))
    attempts = cast(list[Document], r30["GROUP_ATTEMPTS"])
    row = attempts[3394]
    require(
        row["ATTEMPT_INDEX"] == 3394
        and row["PROFILE_IDS"] == [PROFILE]
        and row["STATUS"] == "INFEASIBLE"
        and row["REFUTED_GRAPH_TRIANGLE_COUNT"] == 266
        and row["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"] == 265,
        "old cap source",
    )
    require(route.r28.r26.accepted_cap(row, (D,), 265) == 265, "old cap rejected")
    require(route.r28.profile_s4_floor(D) == 112, "S4 source floor")
    require(route.contained_triple_k4_cap(D) == 197, "contained K4 allowance")
    return {
        "CURRENT_T_CAP": 265,
        "CURRENT_T_SOURCE": R30_RESULT + ":GROUP_ATTEMPTS[3394]",
        "CURRENT_CAP_ROW": row,
        "CURRENT_S4_SOURCE": "pinned r28.profile_s4_floor=112 and r32 Route-B contained K4 split",
        "CURRENT_S5_SOURCE": "NOT_ADOPTED; no S5 term",
        "CURRENT_FULL_BOUND": OLD_BOUND,
    }


def fraction_terms(cap: int, floor: int = 112) -> list[Term]:
    terms: list[Term] = []
    for t in range(22, cap + 1):
        q = max(0, ceil(Fraction(2318 - 10 * (827 - 3 * t), 4)))
        contained = min(q, 197)
        s4 = max(floor, 448 * contained + 679 * (q - contained))
        s3 = 2800 * (827 - 3 * t) + 20272 * (t - 22) + 7000 * 22
        exact = Fraction(372228640 - 63838600 + s3) - Fraction(4 * s4, 7)
        terms.append((t, ceil(exact), q, contained, s4, s3))
    return terms


def envelope(cap: int) -> list[Term]:
    require(type(cap) is int and 22 <= cap <= 265, "wrong T cap domain")
    a = list(route.route_b_envelope(D, cap, 112))
    b = fraction_terms(cap)
    require([x[0] for x in a] == list(range(22, cap + 1)), "incomplete envelope")
    require(a == b, "envelope Fraction/rounding/sign disagreement")
    return a


def arithmetic_audit() -> Document:
    for r in range(8):
        require(
            Fraction(r - comb(r, 2) + comb(r, 3)) - Fraction(4 * comb(r, 4), 7) >= int(r > 0),
            "multiplicity polynomial",
        )
    # Nonintegral probes distinguish ceiling direction; actual S4 terms are divisible by 7.
    for floor in (112, 113, 114):
        a = route.envelope_term(D, 22, floor, 197)
        require(a == fraction_terms(22, floor)[0], "nonintegral rational ceiling")
    return local.local_weights()


def family(rows: Mapping[str, int], cursor: Mapping[str, int]) -> Document:
    require(
        len(rows) == 4647 and len(cursor) == 197 and not set(rows) & set(cursor), "family coverage"
    )
    pairs = [*rows.items(), *cursor.items()]
    top = max(b for _, b in pairs)
    best = sorted(p for p, b in pairs if b == top)
    descending = sorted(pairs, key=lambda x: (-x[1], x[0]))
    require(
        best == [p for p, b in descending if b == descending[0][1]], "independent family owners"
    )
    opened = sum(b > INCUMBENT for _, b in pairs)
    require(opened == len([1 for _, b in descending if b > INCUMBENT]), "independent open count")
    return {
        "BOUND": top,
        "OWNER_IDS": best,
        "GAP_TO_INCUMBENT": top - INCUMBENT,
        "OPEN_COUNT": opened,
        "RESOLVED_MAXIMUM": max(rows.values()),
        "CURSOR_MAXIMUM": max(cursor.values()),
    }


def replay(base: Document, bound: int) -> Document:
    # Independent reload makes in-memory cursor/source mutations observable.
    immutable = load_base()
    require(base == immutable, "cursor/source mutation")
    rows = ledger(base["RESOLVED_ROW_BOUNDS"])
    cursor = obj(base["CURSOR"])
    projection = ledger(cursor["COARSE_BOUND_PROJECTION"])
    before = family(rows, projection)
    updated = dict(rows)
    updated[PROFILE] = bound
    require([p for p in rows if rows[p] != updated[p]] == [PROFILE], "single-row scope")
    other = {p: b for p, b in rows.items() if p != PROFILE}
    require(other == {p: b for p, b in updated.items() if p != PROFILE}, "other rows mutated")
    after = family(updated, projection)
    require(before["OWNER_IDS"] == [PROFILE, "66655555555411110000"], "old tied owners")
    require(after["OWNER_IDS"] == ["66655555555411110000"], "new tied owners")
    require(before["BOUND"] == after["BOUND"] == OLD_BOUND, "profile delta is not Family delta")
    require(before["OPEN_COUNT"] == 1516 and after["OPEN_COUNT"] == 1515, "complete open replay")
    return {
        "BEFORE": before,
        "AFTER": after,
        "DELTA": 0,
        "OTHER_ROWS_UNCHANGED": 4646,
        "OTHER_ROWS_SHA256": sha(render(other)),
        "CURSOR_SHA256": sha(render(cursor)),
        "CURSOR": cursor,
        "RESOLVED_ROW_BOUNDS": updated,
    }


def compute_result() -> Document:
    pins = source_closure()
    base = load_base()
    constants = facts()
    current = current_authority(base)
    local_path = "src/lottolab/research/b649_min_s2_advanced_11row_exact_adoption_r1.py"
    pins[local_path] = sha(frozen(local_path))
    require(
        Path(local.__file__).resolve() == ROOT / local_path,
        "local count source root",
    )
    weights = arithmetic_audit()
    domain = domain_certificate()
    old = envelope(integer(current["CURRENT_T_CAP"]))
    require(max(t[1] for t in old) == OLD_BOUND, "old envelope authority mismatch")
    cap = integer(domain["CAP"])
    require(cap == 249, "wrong T cap")
    new = envelope(cap)
    bound = max(t[1] for t in new)
    require(bound <= 313391739, "no strict profile improvement")
    return {
        "TASK_ID": TASK_ID,
        "OWNER_CONVERSATION_ID": OWNER_CONVERSATION_ID,
        "TASK_STATUS": "PROVEN_PROFILE_BOUND; FRESH_JUDGE_AND_LIFECYCLE_EXTERNAL",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_RESULT_SHA256": BASE_SHA,
        "MODEL": MODEL,
        "FACTS": constants,
        "CURRENT_AUTHORITY": current,
        "SELECTED_THEOREM": (
            "Exact K15/Z5 split with subset, prefix and pair-case triangle remainder floors"
        ),
        "THEOREM_ASSUMPTIONS": (
            "Frozen model and exact degrees only; no d=1 shadow lemma and no d=2 companion lemma"
        ),
        "PROOF": __doc__,
        "ENUMERATION": domain,
        "NEW_PROVEN_T_CAP": cap,
        "NEW_PROVEN_S4": "T-dependent Route-B lower floor, recorded in every term",
        "NEW_PROVEN_S5": "NOT_USED",
        "NEW_FULL_PROFILE_BOUND": bound,
        "PROFILE_DELTA": OLD_BOUND - bound,
        "STRICT_GAIN_EXCLUDED": bound <= INCUMBENT,
        "TERM_COLUMNS": [
            "T",
            "CEIL_BOUND",
            "K4_FLOOR",
            "CONTAINED_ALLOWANCE_USED",
            "S4_LOWER",
            "S3",
        ],
        "OLD_T_TERMS": [list(t) for t in old],
        "NEW_T_TERMS": [list(t) for t in new],
        "OLD_TERM_COUNT": len(old),
        "NEW_TERM_COUNT": len(new),
        "FAMILY": replay(base, bound),
        "RESOLVED_ROWS": 4647,
        "CURSOR_PROFILES": 197,
        "INCUMBENT": INCUMBENT,
        "EVALUATOR_SOURCE_PINS": pins,
        "EXACT_LOCAL_EVENT_WEIGHTS": weights,
        "SOURCE_SHA256": sha(working_bytes(SOURCE)),
        "TEST_SHA256": sha(working_bytes(TEST)),
        "PRIOR_ART": {
            "TASK_ID": PRIOR_TASK,
            "STATUS": "USER_CONFIRMED_READ_ONLY_CANDIDATE; NOT_CERTIFIED_AUTHORITY",
            "USER_CONTINUATION": (
                "Continue independent proof; do not search unknown Chat ID "
                "or block on missing prior artifacts"
            ),
            "CANDIDATE_T_CAP": 253,
            "CANDIDATE_BOUND": 313284196,
            "CANDIDATE_BASE_PREFIX": "b280d90",
            "MISSING": [
                "Chat ID",
                "immutable result",
                "commit",
                "proof artifact",
                "full state enumeration",
                "term arrays",
                "fresh Judge",
            ],
            "ADOPTED_AS_AUTHORITY": False,
            "KNOWN_SPLIT_METHOD_SOURCE": (
                "src/lottolab/research/b649_min_s2_advanced_11row_exact_adoption_r1.py"
            ),
            "KNOWN_SPLIT_METHOD_SHA256": sha(
                frozen("src/lottolab/research/b649_min_s2_advanced_11row_exact_adoption_r1.py")
            ),
            "OWNERSHIP_TAKEN_OVER": False,
        },
        "INHERITED_AUTHORITY_VERBATIM": base["INHERITED_AUTHORITY_VERBATIM"],
        "INHERITED_BASE_FRESH_JUDGE": base["BASE_FRESH_JUDGE"],
        "BASE_JUDGE_REPORT_SHA256": (
            "2b9862592db047e4c65e8f1fa708841c1dc29ba041aa1921a87c28458123b300"
        ),
        "BASE_JUDGE_CAVEATS": (
            "See SHA-pinned Base report; J1 index administrative drift, no unique attribution"
        ),
        "HISTORICAL_R15": "NOT_VERIFIED",
        "LEGAL_ATTAINMENT": "UNKNOWN",
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "HEAVY_SOLVER_STARTED": "NO",
        "REMOTE_WRITE": "NO",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-result", action="store_true")
    args = parser.parse_args()
    result = compute_result()
    payload = render(result)
    if args.write_result:
        path = ROOT / RESULT
        require(not path.exists(), "result already exists; inspect before replacement")
        path.write_bytes(payload)
    else:
        require(working_bytes(RESULT) == payload, "sealed result mismatch")
    print(
        json.dumps(
            {
                "RESULT_SHA256": sha(payload),
                "T_CAP": result["NEW_PROVEN_T_CAP"],
                "PROFILE_BOUND": result["NEW_FULL_PROFILE_BOUND"],
                "FAMILY": obj(result["FAMILY"])["AFTER"],
            }
        )
    )


if __name__ == "__main__":
    main()
