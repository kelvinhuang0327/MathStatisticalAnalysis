"""Universal T<=257 certificate for the exact profile 66665555555321100000.

Frozen premises and identities. There are 20 tickets, six distinct labels on
 each, 22 triple supports and 27 pair supports. Pair-linearity makes the
 support shadow a simple graph G: each triple supplies three distinct edges,
 each pair one. Thus E(G)=93 and g_x=2d_x+(6-d_x)=6+d_x. The exact d is
 6^4,5^7,3,2,1^2,0^5, sum d=66, W=sum C(g,2)=830 and J=sum C(g,3)=2345.
For H=complement(G), every mixed-colour vertex triple contributes two to
 sum g(19-g); hence T(G)+T(H)=C(20,3)-sum g(19-g)/2=296.
Independently, inclusion-exclusion over the H-edges of each vertex triple
 gives T(G)=C(20,3)-18e(H)+sum C(13-d,2)-T(H), the same constant 296.

Exact core-zero decomposition, derived for this profile. Let K={d>0}, Z={d=0},
 |K|=15, |Z|=5, sigma_x=|N_G(x) intersect Z|, zeta_u=|N_G(u) intersect K|.
Since zeros lie in no triple support, every cross edge uses a pair label,
 so 0<=sigma_x<=min(5,6-d_x). A zero has six neighbours and at most four in Z,
 so 2<=zeta_u<=6. Both degree sums count the same cross edges: sum sigma=sum zeta=r.
Let M=H[K], N=H[Z]. Their degrees are m_x=14-(6+d_x-sigma_x)=8-d_x+sigma_x,
 n_u=4-(6-zeta_u)=zeta_u-2. Thus 2e(M)=54+r and 2e(N)=r-10.
An edge xy of M has 5-sigma_x-sigma_y+c_Z(x,y) H-neighbours in Z, where
 c_Z(x,y)=|N_G(x) intersect N_G(y) intersect Z|. An edge uv of N has
 15-zeta_u-zeta_v+c_K(u,v) H-neighbours in K. Each mixed H-triangle is
 counted exactly once by its unique same-shore edge. Consequently
 T(H)=5e(M)+15e(N)-sum sigma*m-sum zeta*n+P,
 P=T(M)+T(N)+sum_{xy in E(M)}c_Z(x,y)+sum_{uv in E(N)}c_K(u,v).
Every summand is a cardinality and nonnegative. Since 5e(M)+15e(N)=60+10r,
 T(G)=236-10r+sum sigma*m+sum zeta*n-P, exactly as required.
The core-apex mixed count C_K=sum_{E(N)}c_K=sum_x e(N[N_G(x) intersect Z]);
 the zero-apex mixed count C_Z=sum_{E(M)}c_Z=sum_u e(M[N_G(u) intersect K]).
These are two different disjoint classes of mixed H-triangles.

Remainder bounds. If F has degree list a, edge count e and a vertex subset A
 of size s, then sum_A a-e=e(F[A])-e(F[outside A])<=e(F[A]). Therefore every
 s-subset spans >=max(0,sum of the s smallest a-e) edges. Apply this to N
 for each of the 15 sigma values to lower-bound C_K, and to M for each of
 the five zeta values to lower-bound C_Z. Different apex contributions add.
For any edge ij of F, its common-neighbour count is >=max(0,a_i+a_j-n).
Summing over edges gives 3T(F)>=sum a_i^2-ne, the square bound. For the h
 largest-degree vertices L, cut(L,outside)<=sum_out min(h,a); hence at least
 ell=max(0,ceil((sum_L a-sum_out min(h,a))/2)) edges lie in L. The total
 common-neighbour count over these edges is at least the sum of the ell
 smallest nonnegative pair weights max(0,a_i+a_j-n) among all pairs in L.
It equals 3T(F[L])+the triangles with exactly two vertices in L, and is at
 most T(F)+2C(h,3). Thus T(F)>=weight_sum-2C(h,3). Take the maximum of 0,
 the square bound and all prefix bounds for each of M and N separately.
Subtract these two triangle floors and both mixed-count floors from the raw
 split score. No double counting of corrections occurs: the four terms of P
 have separate floors; alternative floors on the same term combine by max.

Complete finite-domain coverage. Within each equal-d class sort sigma, and
 sort the five zeros by zeta. These are vertex permutations preserving every
 premise, graph condition, correction and objective. The classes have
 (count,range)=(4,{0}),(7,{0,1}),(1,{0..3}),(1,{0..4}),(2,{0..5}). Their
 multiset product has 1*8*4*5*21=3360 signatures. All C(9,5)=126 sorted
 zeta lists in {2..6} are considered, including the full legal coordinate
 ranges; 31 have graphical G[Z] degrees 6-zeta. Every actual realization has
 graphical m on K and a bipartite cross graph with degrees (sigma,zeta).
For a descending degree prefix of size h, any simple graph satisfies
 sum_top a<=h(h-1)+sum_out min(h,a) and even degree sum (Erdos-Gallai).
For cross graphs, equal sums and sum_top_h sigma<=sum_u min(h,zeta_u)
 follow by counting edges into each zero (core-side Gale-Ryser). The zero-side
 inequalities follow symmetrically. These necessary restrictions cannot
 discard a legal realization; support realizability is never assumed from them.
Enumerator A uses multiset products, Erdos-Gallai, core-side Gale-Ryser and
 integer corrections. Enumerator B independently generates histograms,
 exhausts all 2^10=1024 labelled five-zero graphs, uses Havel-Hakimi on m,
 zero-side Gale-Ryser and separately written Fraction/cocomplement corrections.
Havel-Hakimi preserves graphicality: by degree-preserving two-edge switches,
 a maximum-degree vertex can be joined to the largest remaining degrees;
 deleting it reduces precisely those degrees. Repeating rejects no graph.
B never calls A's enumeration, predicates or correction functions. The entire
 keyed state set and every field must agree, with 2897 distinct retained
 states. Their maximum corrected score is 257 (raw maximum 280); hence
 every legal realization satisfies T(G)<=257. The argmax is a necessary-
 condition relaxation extremum. Legal support attainment is UNKNOWN.

Complete Route B. Each outcome is seven labels with a distinguished label.
By pair-linearity winners' selected three-subsets consume distinct label
 pairs, so at most floor(C(7,2)/3)=7 tickets win. For integer v=0..7,
 1[v>0]<=v-C(v,2)+C(v,3)-4C(v,4)/7 (checked exhaustively).
The pinned exact local weights, independently recounted from explicit small
 ticket patterns, are S1=372228640, S2=63838600, open-wedge 2800,
 pair-triangle 20272 and shared-triple 7000. Therefore
 S3(t)=2800(830-3t)+20272(t-22)+7000*22.
In each vertex neighbourhood a nonedge spoils at most gmax-2=10 triples.
Summing gives 4K4>=J-10(W-3t), so q(t)=max(0,ceil((2345-10(830-3t))/4)).
A K4 holds at most one support triple (two would share a ticket pair).
A triple abc has at most min(g_a-2,g_b-2,g_c-2) common outside neighbours,
 at most their average. Summing over all triple incidences gives a contained
 K4 allowance floor(sum_x d_x(g_x-2)/3)=199. K4 local weights are 448 with
 a triple and 679 without, so S4(t)>=max(112,679q-231min(q,199)). This is
 increasing in q. The coefficient on S4 is negative: subtract its LOWER bound.
The resulting UB(t)=ceil(S1-S2+S3(t)-4S4(t)/7) uses an outward ceiling.
All 243 old terms t=22..264 and all 236 new terms t=22..257 are reconstructed
 using the pinned exact evaluator and independent integer/Fraction arithmetic.
The old and new full-envelope maxima are 313391636 and 313329096, delta62540.
Endpoint S4 floors are 288099 and 252112. S5 is NOT_PINNED / NOT_USED.
Nearby artificial S4 floors test nonintegral rounding; they are not adopted.

Family projection only. Replay all 4647 resolved rows and all 197 cursor
 identities, bounds and coverage from immutable Base 9acea133. Replace only
 this exact profile in memory; all other 4646 rows and the full cursor remain
 equal. The projected maximum becomes 313391560, delta76, next owner
 65555555555432100000, incumbent gap127672 and 1515 still-open profiles.
The new profile UB remains above incumbent313263888: STRICT_GAIN_EXCLUDED=NO.
No shared Family Authority is written. Historical Base dispositions, pending
 Judge/solver/R15 caveats remain verbatim and are not upgraded by this task.
Fresh Judge, exact committed-tree identity, clean/released ownership and this
 task's R15 lifecycle accounting are external final gates, never inferred from
 the existence of this JSON. No solver, portfolio enumeration or remote write.

Implementation provenance: the two executable recounts specialize the existing
 general core-zero arithmetic pattern also used by the earlier A certificate
 at c4c83e6b. Its result is neither imported nor used as proof of this profile;
 the derivation, complete target domain, all corrections and maxima above are
 recomputed here. No A/B certificate or shared authority is changed.
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
TASK_ID = "B649_MIN_S2_666655555553211_T257_FORMAL_HANDOFF_R2"
OWNER_CONVERSATION_ID = "01a13f86-4fce-7130-a5e7-fe3345e894f3"
PROFILE = "66665555555321100000"
D = tuple(map(int, PROFILE))
CORE = D[:15]
GROUPS = ((6, 4, 0), (5, 7, 1), (3, 1, 3), (2, 1, 4), (1, 2, 5))
BASE_HEAD = "9acea1331e021a9623fa593997d90cfc89a69136"
BASE_TREE = "de577e8d6f3ccbe52e663c96ee1528c95a0ee7ec"
DIRECTORY = "docs/research/matrix-native-results/"
BASE_RESULT = DIRECTORY + "b649-min-s2-owner-ab-t249-t260k4-composition-r1-result.json"
BASE_SHA = "9fbe17d020573835cd69f16296fee224ff4f83aef8b3e7a644f2ffaabdfe92c9"
R30_RESULT = DIRECTORY + "b649-k20-min-s2-current-cursor-dynamic-family-max-r30-result.json"
R30_SHA = "9ed94532cc2bff5de1569f10561fb8340238ff3b1b1c3ae129e6a4929014f6fe"
STEM = "b649_min_s2_666655555553211_t257_formal_r2"
SOURCE = f"src/lottolab/research/{STEM}.py"
TEST = f"tests/unit/test_{STEM}.py"
RESULT = DIRECTORY + STEM.replace("_", "-") + "-result.json"
INCUMBENT = 313263888
OLD_BOUND = 313391636
MODEL = {"TICKETS": 20, "LABELS_PER_TICKET": 6, "TRIPLES": 22, "PAIRS": 27, "PAIR_LINEARITY": True}


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
    pending, pins = [route.__name__, local.__name__], dict[str, str]()
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
        value == {"SUM_D": 66, "E": 93, "W": 830, "J": 2345, "GOODMAN": 296, "A_MAX": 199},
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
def floors_a(ds: Degrees) -> tuple[int, int]:
    """Square and prefix triangle lower bounds, integer formulation."""
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
    return square, prefix


@cache
def floors_b(ds: Degrees) -> tuple[int, int]:
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
    return square, prefix


def validate_state(state: State) -> None:
    s, z = state
    require(len(s) == 15 and len(z) == 5, "wrong cross-degree lengths")
    require(all(type(x) is int for x in (*s, *z)), "noninteger cross degree")
    require(all(0 <= x <= min(5, 6 - d) for x, d in zip(s, CORE, strict=True)), "sigma range")
    require(all(2 <= x <= 6 for x in z) and tuple(sorted(z)) == z, "zeta range/order")
    start = 0
    for _, count, _ in GROUPS:
        part = s[start : start + count]
        require(tuple(sorted(part)) == part, "sigma class symmetry")
        start += count
    require(sum(s) == sum(z), "wrong cross-degree sums")
    require(graphical_eg(tuple(8 - d + x for d, x in zip(CORE, s, strict=True))), "M graphicality")
    require(graphical_eg(tuple(6 - x for x in z)), "zero graphicality")
    ordered = sorted(s, reverse=True)
    require(
        all(sum(ordered[:h]) <= sum(min(h, x) for x in z) for h in range(1, 16)), "cross Gale-Ryser"
    )


def record_a(state: State) -> Document:
    validate_state(state)
    s, z = state
    m = tuple(8 - d + x for d, x in zip(CORE, s, strict=True))
    n = tuple(x - 2 for x in z)
    raw = (
        236
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
        "UPPER": raw - ck - cz - max(fm) - max(fn),
    }


def record_b(state: State) -> Document:
    sigma, zeta = state
    md = tuple(15 - 1 - (6 + d - s) for d, s in zip(CORE, sigma, strict=True))
    nd = tuple(4 - (6 - z) for z in zeta)
    mixed = (5 * sum(md) + 15 * sum(nd)) // 2
    mixed -= sum(sigma[i] * md[i] for i in range(15))
    mixed -= sum(zeta[j] * nd[j] for j in range(5))
    raw = 296 - mixed
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
        "UPPER": raw - ck - cz - max(fm) - max(fn),
    }


def enumerate_a() -> list[tuple[State, Document]]:
    options = [tuple(combinations_with_replacement(range(u + 1), n)) for _, n, u in GROUPS]
    zero = [
        z
        for z in combinations_with_replacement(range(2, 7), 5)
        if graphical_eg(tuple(6 - x for x in z))
    ]
    require(len(tuple(combinations_with_replacement(range(2, 7), 5))) == 126, "raw zero domain")
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
    require(signatures == 3360, "sigma domain completeness")
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
    require(len(zero) == 31, "independent zero graph signatures")
    require(
        len(tuple(histograms(7, 1)))
        * len(tuple(histograms(1, 3)))
        * len(tuple(histograms(1, 4)))
        * len(tuple(histograms(2, 5)))
        == 3360,
        "independent histogram domain",
    )
    rows: list[tuple[State, Document]] = []
    for z in sorted(zero):
        for five in histograms(7, 1):
            for three in histograms(1, 3):
                for two in histograms(1, 4):
                    left = sum(z) - sum(five) - sum(three) - sum(two)
                    for one in histograms(2, 5):
                        if sum(one) != left:
                            continue
                        s = (0, 0, 0, 0, *five, *three, *two, *one)
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
    require(len(a) == len({s for s, _ in a}) == 2897, "finite domain completeness")
    states = [row for _, row in a]
    cap = max(integer(row["UPPER"]) for row in states)
    require(cap == 257, "wrong T cap or correction sign")
    return {
        "SIGMA_SIGNATURES": 3360,
        "RAW_ZETA_MULTISET_COUNT": 126,
        "ZETA_GRAPHICAL_COUNT": 31,
        "ZERO_GRAPHS_RECOUNTED": 1024,
        "RETAINED_STATES": len(states),
        "STATES_SHA256": sha(render(states)),
        "STATES": states,
        "CAP": cap,
        "ARGMAX": [s for s in states if s["UPPER"] == cap],
        "REALIZABILITY": "NECESSARY_CONDITION_RELAXATION; ATTAINMENT_NOT_ASSERTED",
        "COVERAGE_PROOF": __doc__,
    }


def current_authority(base: Document) -> Document:
    require(base["MODEL"] == MODEL and base["INCUMBENT"] == INCUMBENT, "frozen model")
    require(ledger(base["RESOLVED_ROW_BOUNDS"])[PROFILE] == OLD_BOUND, "target old bound")
    r30 = obj(json.loads(frozen(R30_RESULT, R30_SHA)))
    row = cast(list[Document], r30["GROUP_ATTEMPTS"])[3738]
    require(
        row["ATTEMPT_INDEX"] == 3738
        and row["PROFILE_IDS"] == [PROFILE]
        and row["STATUS"] == "INFEASIBLE"
        and row["REFUTED_GRAPH_TRIANGLE_COUNT"] == 265
        and row["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"] == 264,
        "historical cap source",
    )
    require(route.r28.r26.accepted_cap(row, (D,), 264) == 264, "historical cap binding")
    require(route.r28.profile_s4_floor(D) == 112, "S4 base floor")
    require(route.contained_triple_k4_cap(D) == 199, "contained K4 allowance")
    return {
        "CURRENT_T_CAP": 264,
        "SOURCE_ROW": row,
        "HISTORICAL_SOLVER_RERUN": False,
        "CURRENT_FULL_BOUND": OLD_BOUND,
        "S4_BASE": 112,
        "CONTAINMENT_ALLOWANCE": 199,
    }


def fraction_terms(cap: int, floor: int = 112) -> list[Term]:
    result: list[Term] = []
    for t in range(22, cap + 1):
        q = max(0, ceil(Fraction(2345 - 10 * (830 - 3 * t), 4)))
        contained = min(q, 199)
        s4 = max(floor, 448 * contained + 679 * (q - contained))
        s3 = 2800 * (830 - 3 * t) + 20272 * (t - 22) + 7000 * 22
        numerator = 7 * (372228640 - 63838600 + s3) - 4 * s4
        bound = ceil(Fraction(numerator, 7))
        require(7 * (bound - 1) < numerator <= 7 * bound, "exact rational ceiling")
        result.append((t, bound, q, contained, s4, s3))
    return result


def verify_terms(value: list[Term], cap: int) -> None:
    require(type(cap) is int and cap in (257, 264), "wrong cap")
    require([t[0] for t in value] == list(range(22, cap + 1)), "incomplete T range")
    require(value == fraction_terms(cap), "K4/containment/S3/S4 sign/rational rounding")


def envelope(cap: int) -> list[Term]:
    require(type(cap) is int and cap in (257, 264), "wrong cap")
    result = list(route.route_b_envelope(D, cap, 112))
    verify_terms(result, cap)
    return result


def arithmetic_audit() -> Document:
    # Actual floors are multiples of seven. Nearby artificial floors make a
    # ceiling-direction defect observable without changing adopted mathematics.
    for floor in (112, 113, 114):
        require(
            route.envelope_term(D, 22, floor, 199) == fraction_terms(22, floor)[0],
            "nonintegral ceiling probe",
        )
    return local.local_weights()


def family(rows: Mapping[str, int], cursor: Mapping[str, int]) -> Document:
    require(
        len(rows) == 4647 and len(cursor) == 197 and not set(rows) & set(cursor),
        "complete Family coverage",
    )
    entries = [*rows.items(), *cursor.items()]
    bound = max(b for _, b in entries)
    ordered = sorted(entries, key=lambda p: (-p[1], p[0]))
    owners = sorted(p for p, b in entries if b == bound)
    require(owners == [p for p, b in ordered if b == ordered[0][1]], "Family recount")
    return {
        "BOUND": bound,
        "OWNER_IDS": owners,
        "GAP": bound - INCUMBENT,
        "OPEN_COUNT": sum(b > INCUMBENT for _, b in entries),
    }


def projection(base: Document, bound: int) -> Document:
    require(base == load_base(), "immutable source/cursor mutation")
    require(type(bound) is int and bound == 313329096, "projected profile bound")
    rows = ledger(base["RESOLVED_ROW_BOUNDS"])
    cursor = obj(base["CURSOR"])
    cp = ledger(cursor["COARSE_BOUND_PROJECTION"])
    require(
        cursor["PROFILE_COUNT"] == 197 and set(cast(list[str], cursor["PROFILE_IDS"])) == set(cp),
        "cursor membership",
    )
    before = family(rows, cp)
    revised = dict(rows)
    revised[PROFILE] = bound
    require([p for p in rows if revised[p] != rows[p]] == [PROFILE], "single projected row")
    other = {p: b for p, b in rows.items() if p != PROFILE}
    require(other == {p: b for p, b in revised.items() if p != PROFILE}, "other 4646 rows")
    after = family(revised, cp)
    require(before["BOUND"] == OLD_BOUND and after["BOUND"] == 313391560, "Family projection")
    require(
        after["OWNER_IDS"] == ["65555555555432100000"]
        and after["GAP"] == 127672
        and after["OPEN_COUNT"] == 1515,
        "projected owner/gap/open",
    )
    return {
        "STATUS": "RESEARCH_PROJECTION_ONLY; NO_FAMILY_AUTHORITY_MUTATION",
        "BEFORE": before,
        "AFTER": after,
        "DELTA": integer(before["BOUND"]) - integer(after["BOUND"]),
        "RESOLVED_ROWS": 4647,
        "OTHER_ROWS_UNCHANGED": len(other),
        "OTHER_ROWS_SHA256": sha(render(other)),
        "CURSOR_SHA256": sha(render(cursor)),
        "PROJECTED_LEDGER_SHA256": sha(render(revised)),
        "CURSOR": cursor,
    }


def compute_result() -> Document:
    pins = source_closure()
    base = load_base()
    current = current_authority(base)
    constants = facts()
    weights = arithmetic_audit()
    domain = domain_certificate()
    old, new = envelope(264), envelope(integer(domain["CAP"]))
    bound = max(t[1] for t in new)
    require(max(t[1] for t in old) == OLD_BOUND and len(old) == 243, "old complete maximum")
    require(bound == 313329096 and len(new) == 236, "new complete maximum")
    require(old[-1][4] == 288099 and new[-1][4] == 252112, "endpoint S4 floors")
    return {
        "TASK_ID": TASK_ID,
        "OWNER_CONVERSATION_ID": OWNER_CONVERSATION_ID,
        "TASK_STATUS": "PROFILE_CERTIFICATE; FRESH_JUDGE_AND_LIFECYCLE_EXTERNAL",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_RESULT_SHA256": BASE_SHA,
        "BASE_JUDGE_OBSERVED_AT_PREFLIGHT": {
            "VERDICT": "VERIFIED_WITH_CAVEATS",
            "TREE": BASE_TREE,
            "REPORT_SHA256": "dbdc29b728fb98e232acfb106c34597c7bc06e1ed096b3255567a71b95614ec0",
            "BINDING": (
                "Observed external report copied into task evidence; not immutable Git authority"
            ),
        },
        "MODEL": MODEL,
        "TARGET_PROFILE": PROFILE,
        "FACTS": constants,
        "CURRENT_AUTHORITY": current,
        "PROOF": __doc__,
        "ENUMERATION": domain,
        "INDEPENDENT_RECOUNTS": 2,
        "PROVEN_T_CAP": integer(domain["CAP"]),
        "FULL_PROFILE_BOUND": bound,
        "PROFILE_DELTA": OLD_BOUND - bound,
        "INCUMBENT": INCUMBENT,
        "STRICT_GAIN_EXCLUDED": bound <= INCUMBENT,
        "TERM_COLUMNS": ["T", "BOUND", "K4_FLOOR", "CONTAINED_K4", "S4", "S3"],
        "OLD_T_TERMS": old,
        "NEW_T_TERMS": new,
        "S5": "NOT_PINNED / NOT_USED",
        "LOCAL_WEIGHT_RECOUNT": weights,
        "EVALUATOR_SOURCE_PINS": pins,
        "FAMILY_PROJECTION": projection(base, bound),
        "INHERITED_CAVEATS_AND_STATUS_VERBATIM": base["INHERITED_CAVEATS_AND_STATUS_VERBATIM"],
        "HISTORICAL_R15": "NOT_VERIFIED",
        "NEW_TASK_R15": "EXTERNAL_FINAL_LIFECYCLE_GATE",
        "SOURCE_SHA256": sha(working_bytes(SOURCE)),
        "TEST_SHA256": sha(working_bytes(TEST)),
        "LEGAL_ATTAINMENT": "UNKNOWN",
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "HEAVY_SOLVER_STARTED": "NO",
        "REMOTE_WRITE": "NO",
    }


def verify_result(candidate: Document) -> None:
    require(
        candidate == json.loads(render(compute_result())),
        "result/source/domain/correction mismatch",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-result", action="store_true")
    args = parser.parse_args()
    result = compute_result()
    raw = render(result)
    if args.write_result:
        (ROOT / RESULT).write_bytes(raw)
    else:
        require(working_bytes(RESULT) == raw, "deterministic result bytes")
    print(
        json.dumps(
            {
                "RESULT_SHA256": sha(raw),
                "T_CAP": result["PROVEN_T_CAP"],
                "FULL_PROFILE_BOUND": result["FULL_PROFILE_BOUND"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
