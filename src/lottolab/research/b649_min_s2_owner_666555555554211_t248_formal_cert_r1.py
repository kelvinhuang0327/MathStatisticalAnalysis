"""Universal T<=248 certificate for exactly 66655555555421100000.

Model: 20 tickets carry six distinct labels; 22 labels have triple supports,
27 have pair supports. Pair-linearity makes all 3*22+27=93 support edges
distinct. If d counts triple incidences, deg_G=2d+(6-d)=6+d. This profile
is 6^3,5^8,4,2,1^2,0^5, has sum d=66 and W=sum C(6+d,2)=828.
Complement inclusion-exclusion gives T(G)+T(H)=C(20,3)-18*97+
sum C(13-d,2)=294, equivalently Goodman via sum g(19-g)/2.

Let K={d>0}, Z={d=0}, M=H[K], N=H[Z]; |K|=15, |Z|=5.
Write sigma_x=|N_G(x)&Z|, zeta_u=|N_G(u)&K|. Cross edges are pair
labels, so 0<=sigma<=6-d. A zero has six neighbours, at most four in Z,
so 2<=zeta<=6. Both sums equal r. Internal complement degrees are
h=8-d+sigma and a=zeta-2; e(M)=(54+r)/2, e(N)=(r-10)/2.
Mixed H triangles over xy in M have 5-sigma_x-sigma_y+c_Z(xy)
zero apices; those over uv in N have 15-zeta_u-zeta_v+c_K(uv).
Each mixed triangle has exactly one same-part edge. Therefore
 T(H)=5e(M)+15e(N)-sum sigma*h-sum zeta*a+P,
 P=T(M)+T(N)+sum_M c_Z+sum_N c_K >=0.
Every summand is an explicitly defined cardinality, hence nonnegative.
Since the first two terms are 60+10r, substitution proves
 T(G)=234+sum_K sigma(sigma-d-4)+sum_Z zeta^2-P = F-P.
Parity and cross capacities give r in {10,12,...,24}.

Shadow theorem (shared companion only). Let x,y be the two d=1 vertices
and c the d=2 vertex. Every d=6 vertex has 12 distinct shadow neighbours
among the other 14 core vertices. In a common triple {x,y,c}, such a hub
cannot shadow-adjoin x or y, so must adjoin c. Then c has x,y and all three
hubs as shadow neighbours: at least five, contradicting 2d_c=4.
In distinct triples {x,c,p},{y,c,q}, linearity implies p!=q. A hub equal
to p or q already adjoins c; any other hub misses x,y and must adjoin c.
Again c has both lows and all three hubs, violating capacity four.
A degree-two vertex in only ONE companion pair is NOT excluded.

Relabel within equal-d classes so sigma is ascending in each class, and
let alpha=sigma_x<=beta=sigma_y. This is a bijection on legal supports;
companion candidates remain labelled after this relabeling.
A: beta<5. Drop P, using only P>=0.
B: alpha<beta=5. y has exactly two core G neighbours, its unique triple
companions. Thus either the lows share a triple or xy is an M edge.
For xy in M, codeg_M(xy)>=h_x+h_y-15=4+alpha; c_Z(xy)=alpha,
so P>=4+2alpha. These count different P parts.
For common triple {x,y,c}, put R=K\\{x,y,c}. All 12 vertices of R
are M neighbours of y. Removing the three pairwise G-adjacent vertices
from M gives e_R=r/2+d_c-alpha-sigma_c. Every v in R has at most
three M neighbours outside R, so e_R>=max_R(h_v-3) is necessary.
Triangles with apex y number e_R; cross correction edges yv in M
contribute sum_R sigma=r-alpha-5-sigma_c. Hence
P>=e_R+r-alpha-5-sigma_c. Use the MINIMUM over the distinct relaxation
and every retained common companion, never a maximum across alternatives.
C: alpha=beta=5. In a common triple the two apex triangle sets are
disjoint, even when their base edge agrees; the multiplier is TWO.
Here e_R=r/2+d_c-sigma_c-5, so P>=2e_R+2(r-10-sigma_c).
In distinct triples let A,B be the two companion pairs in the remaining
13 vertices R. Pair-linearity gives k=|A&B|<=1; a shared c of degree two
is excluded by the shadow theorem. xy is an M edge and e(M[R])=4+r/2.
Pairs A and B are G edges. Their residual M degrees are
h_v-1[v notin A]-1[v notin B]. Consequently the EXACT base-edge counts
 tau1=e_R-sum_A h+2-k, tau2=e_R-sum_B h+2-k
must be nonnegative. The common low-edge triangle count is 9+k.
The cross correction over the two low-to-R M stars and xy is
2r-15-sum_A sigma-sum_B sigma. The shared companion is subtracted
twice because its two star edges are distinct. Therefore
P>=tau1+tau2+9+k+2r-15-sum_A sigma-sum_B sigma.
If tau12 counts M edges outside A union B, inclusion-exclusion gives
|X union Y|=tau1+tau2-tau12, where X,Y are the two base-edge sets.
Triangle counts use DIFFERENT apices, so tau12 is counted TWICE in
tau1+tau2 and must NOT be subtracted. The edgewise audit below verifies
these identities, all shared-vertex subtractions, and tau12, for every
potential residual edge. No realizability of this relaxation is claimed.

Coverage: the core domain is 1*9*3*5*21=2835; parity and 10<=r<=24 retain
1087 (705/314/68). Enumerate all 2^10=1024 labelled G[Z] graphs, retaining
the exact maximum sum zeta^2 at each r. Core and zero conditions are relaxed
independently, so every legal structure remains covered. Companion tests
discard only the necessary conditions proved above; stronger graphical,
pair-graph or bipartite tests are deliberately not imposed. Same-triple
domain: 382*13=4966, exclusions 382/11, retained 4573. Distinct domain:
68*78^2=413712, exclusions 5304/8976/1452, retained 397980.
Two different generators and two algebraic correction evaluations agree
on all 1087 complete records and all exclusions. Maxima for increasing r
are 246,248,248,246,246,244,246,228. Thus universally T<=248.
Neither a maximizing degree state nor T248 is asserted legally attainable.

Route B: sum C(g,3)=2326, max g=12, A_max=floor(sum d(g-2)/3)=198.
The excess is 2326-10(828-3t)=30t-5954; q is its nonnegative ceiling /4.
S4=max(112,679q-231min(q,198)); final ceiling is base-floor(4S4/7).
Every old T22..265 and new T22..248 term is checked with exact Fractions
and the pinned official evaluator. Only the target row is replaced in a
conditional R2+T223 projection; no canonical family authority is adopted.
Historical dispositions and R14_NOT_VERIFIED are preserved. The legacy
research hash has no available serialization; the Owner authorizes a new
fully specified canonical records digest, independently regenerated.
"""

from __future__ import annotations

import argparse
import ast
import json
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from fractions import Fraction
from itertools import combinations, combinations_with_replacement, product
from math import comb
from pathlib import Path

from . import b649_k20_min_s2_topw12_split_cap_certificate_r1 as split
from . import b649_min_s2_owner_ab_exact_family_composition_r1 as inherited

ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "B649_MIN_S2_OWNER_666555555554211_T248_FORMAL_CERT_R1"
OWNER = "01a138ba-cea9-7342-a231-57ee09245a66"
TARGET = "66655555555421100000"
D = tuple(map(int, TARGET))
BASE_HEAD = "b1145036c33230d09de0f9c29f831ab1053188a2"
BASE_TREE = "12490e36b382081b7ec07be84676644cd0897a3d"
BASE_SHA = "f86b27c0481dda62ef25ff390ba2f4b58987faf7aa2d8b4c4a8302cb83ddb643"
R2_HEAD = "ef69e3fb4a2fdb171c4bc6944a3672706506beac"
R2_TREE = "bb8615cfe4af6d78bf55756b37a3f8530b05a304"
R2_SHA = "dc28b0f4e3bfb14be8a39a3d3148f1d27aadf3e060c89a8e6e695dfea55babcc"
T223_HEAD = "e3c650d1b298f3df7f2ecaeccca63305653b3bba"
T223_TREE = "fe1d00b3b842cdd9494af7e6a4082f0dcf580f91"
T223_SHA = "7425b8826e8eddb3d4b930a9f8b1579fc96dbfbdd9c2014a0a34aaf2ef69c48d"
DIRECTORY = "docs/research/matrix-native-results"
BASE_RESULT = f"{DIRECTORY}/b649-min-s2-owner-ab-exact-family-composition-r1-result-{BASE_SHA}.json"
R2_RESULT = f"{DIRECTORY}/b649-three-max-profiles-shared-certificate-r2-result.json"
T223_RESULT = f"{DIRECTORY}/b649-min-s2-owner-t223-formal-cert-r1-result.json"
STEM = "b649_min_s2_owner_666555555554211_t248_formal_cert_r1"
SOURCE = f"src/lottolab/research/{STEM}.py"
TEST = f"tests/unit/test_{STEM}.py"
RESULT = f"{DIRECTORY}/b649-min-s2-owner-666555555554211-t248-formal-cert-r1-result.json"
LEGACY_SHA = "1bc95413d36a88dec3ef5e8ea61eebfb72a6d60ba276aaa59c3f576495978230"
R_VALUES = tuple(range(10, 25, 2))
EXPECTED_MAXIMA = (246, 248, 248, 246, 246, 244, 246, 228)
MODEL = {"TICKETS": 20, "LABELS_PER_TICKET": 6, "TRIPLES": 22, "PAIRS": 27, "PAIR_LINEARITY": True}
require, obj, integer = inherited.require, inherited.obj, inherited.integer
sha, render, git = inherited.sha, inherited.render, inherited.git
type Degrees = tuple[int, ...]
type Pair = tuple[int, int]
type Record = tuple[Degrees, int, int, int, int, str]
type Term = tuple[int, int, int, int, int, int]
type Document = dict[str, object]


def model_facts(pid: str = TARGET, model: Mapping[str, object] = MODEL) -> Document:
    require(pid == TARGET and dict(model) == MODEL, "wrong profile/model")
    require(model["PAIR_LINEARITY"] is True, "missing linearity")
    require(all(type(model[k]) is int for k in MODEL if k != "PAIR_LINEARITY"), "model types")
    g = tuple(6 + d for d in D)
    require(Counter(D) == {6: 3, 5: 8, 4: 1, 2: 1, 1: 2, 0: 5}, "wrong degrees")
    goodman = Fraction(comb(20, 3)) - Fraction(sum(v * (19 - v) for v in g), 2)
    phi = comb(20, 3) - 18 * 97 + sum(comb(13 - d, 2) for d in D)
    require(sum(D) == 66 and sum(g) == 186 and phi == goodman == 294, "graph identities")
    return {
        "MODEL": dict(model),
        "D": list(D),
        "CORE": 15,
        "ZERO": 5,
        "EDGES": 93,
        "W": sum(comb(v, 2) for v in g),
        "GOODMAN": phi,
        "CHOOSE3": sum(comb(v, 3) for v in g),
        "A_MAX": sum(d * (4 + d) for d in D) // 3,
    }


def canonical_sigmas(independent: bool = False) -> list[Degrees]:
    if not independent:
        return [
            (0,) * 3 + s + (c, d, a, b)
            for s, c, d, (a, b) in product(
                combinations_with_replacement(range(2), 8),
                range(3),
                range(5),
                combinations_with_replacement(range(6), 2),
            )
        ]

    def visit(prefix: Degrees) -> Iterator[Degrees]:
        i = len(prefix)
        if i == 15:
            yield prefix
            return
        low = prefix[-1] if i and D[i] == D[i - 1] else 0
        for value in range(low, 7 - D[i]):
            yield from visit((*prefix, value))

    return list(visit(()))


def zero_maxima(independent: bool = False) -> dict[int, int]:
    edges = list(combinations(range(5), 2))
    maxima: dict[int, int] = {}
    for mask in range(1024):
        if independent:
            # Complement N degrees; bit order reversed, independently of G degrees.
            a = [0] * 5
            for i, (x, y) in enumerate(reversed(edges)):
                if mask & (1 << i):
                    a[x] += 1
                    a[y] += 1
            zeta = [2 + v for v in a]
        else:
            zeta = [
                6 - sum(bool(mask & (1 << i)) for i, e in enumerate(edges) if v in e)
                for v in range(5)
            ]
        r = sum(zeta)
        maxima[r] = max(maxima.get(r, 0), sum(v * v for v in zeta))
    return maxima


def split_f(sigma: Degrees, zeta: Degrees) -> int:
    require(len(sigma) == 15 and len(zeta) == 5, "cross lengths")
    require(all(type(v) is int for v in (*sigma, *zeta)), "cross types")
    require(all(0 <= s <= 6 - d for s, d in zip(sigma, D, strict=False)), "sigma capacity")
    require(all(2 <= z <= 6 for z in zeta) and sum(sigma) == sum(zeta), "zeta/cross sum")
    h = [8 - d + s for d, s in zip(D[:15], sigma, strict=True)]
    a = [z - 2 for z in zeta]
    general = Fraction(294) - Fraction(5 * sum(h) + 15 * sum(a), 2)
    general += sum(s * v for s, v in zip(sigma, h, strict=True))
    general += sum(z * v for z, v in zip(zeta, a, strict=True))
    f = 234 + sum(s * (s - d - 4) for s, d in zip(sigma, D[:15], strict=True))
    f += sum(z * z for z in zeta)
    require(f == general, "core-zero polynomial/sign")
    return f


def shared_companion_allowed(c: int) -> bool:
    require(type(c) is int and 0 <= c < 13, "companion domain")
    return D[c] != 2


def shadow_audit() -> Document:
    hubs = set(range(3))
    checked = 0
    for p, q in product(range(13), repeat=2):
        if p == 12 or q == 12 or p == q:
            continue
        # In the distinct case all hubs are either explicit c neighbours or
        # miss both lows, forcing c as a neighbour to reach shadow degree 12.
        explicit = hubs.intersection((p, q))
        forced = hubs - explicit
        require(len({13, 14} | explicit | forced) == 5 > 2 * D[12], "shadow contradiction")
        checked += 1
    require(checked == 132 and 2 + len(hubs) > 4, "common shadow contradiction")
    return {
        "COMMON_MIN_NEIGHBOURS": 5,
        "DISTINCT_MIN_NEIGHBOURS": 5,
        "CAPACITY": 4,
        "DISTINCT_CASES": checked,
        "SCOPE": "COMMON THIRD OR DISTINCT SHARED COMPANION ONLY",
    }


def overlap_audit() -> Document:
    checks = 0
    # Membership types suffice: all residual edges contribute linearly to these
    # identities. Checking each permissible basis edge proves every edge sum.
    for a, b in (((0, 1), (2, 3)), ((0, 1), (1, 2))):
        u = set(a) | set(b)
        k = len(set(a) & set(b))
        for edge in combinations(range(13), 2):
            if edge in (a, b):
                continue
            degrees = [int(v in edge) for v in range(13)]
            x = int(not set(edge).intersection(a))
            y = int(not set(edge).intersection(b))
            xy = int(not set(edge).intersection(u))
            require(x == 1 - sum(degrees[v] for v in a), "tau1 overlap sign")
            require(y == 1 - sum(degrees[v] for v in b), "tau2 overlap sign")
            internal = int(set(edge).issubset(u))
            require(xy == 1 - sum(degrees[v] for v in u) + internal, "tau12 subtraction")
            require(x + y - xy == int(bool(x or y)), "union subtraction")
            require(x + y == int(x) + int(y), "distinct apex multiplicity")
            # Low-to-R adjacency counts that turn residual degrees into h.
            low_edges = [int(v not in a) + int(v not in b) for v in range(13)]
            require(sum(low_edges[v] for v in a) == 2 - k, "A shared vertex correction")
            require(sum(low_edges[v] for v in u) == 4 - 2 * k, "union shared correction")
            checks += 1
    return {
        "EDGE_BASIS_CHECKS": checks,
        "TAU12_SUBTRACTED_FROM_UNION": True,
        "TAU12_SUBTRACTED_FROM_DISTINCT_APEX_TRIANGLES": False,
    }


def corrections(s: Degrees, independent: bool = False) -> tuple[int, Counter[str]]:
    r, alpha, beta = sum(s), s[13], s[14]
    h = [8 - d + v for d, v in zip(D[:15], s, strict=True)]
    e_m = sum(h) // 2
    counts: Counter[str] = Counter()
    if beta < 5:
        return 0, counts
    values = [4 + 2 * alpha] if alpha < 5 else []
    for c in range(13):
        counts["SAME_CANDIDATES"] += 1
        if not shared_companion_allowed(c):
            counts["SAME_D2"] += 1
            continue
        residual = [v for v in range(13) if v != c]
        e_r = e_m - h[13] - h[14] - h[c] if independent else r // 2 + D[c] - alpha - s[c]
        require(e_r == r // 2 + D[c] - alpha - s[c], "common e_R identity")
        if e_r < max(h[v] - 3 for v in residual):
            counts["SAME_DEGREE"] += 1
            continue
        counts["SAME_RETAINED"] += 1
        contribution = sum(s[v] for v in residual)
        values.append((2 if alpha == 5 else 1) * (e_r + contribution))
    if alpha < 5:
        return min(values), counts
    pairs = (
        [
            (i, j)
            for mask in range(1 << 13)
            if mask.bit_count() == 2
            for i, j in [tuple(v for v in range(13) if mask & (1 << v))]
        ]
        if independent
        else list(combinations(range(13), 2))
    )
    for a, b in product(pairs, repeat=2):
        counts["DIFFERENT_CANDIDATES"] += 1
        k = len(set(a) & set(b))
        if k == 2:
            counts["DIFFERENT_IDENTICAL"] += 1
            continue
        if 12 in a and 12 in b:
            counts["DIFFERENT_D2"] += 1
            continue
        e_r = e_m - 12 - 12 + 1 if independent else 4 + r // 2
        if independent:
            m = [h[v] - int(v not in a) - int(v not in b) for v in range(13)]
            tau1, tau2 = (e_r - sum(m[v] for v in p) for p in (a, b))
            cross = 5 + sum(s[v] for v in range(13) if v not in a)
            cross += sum(s[v] for v in range(13) if v not in b)
            both = sum(v not in a and v not in b for v in range(13))
        else:
            tau1, tau2 = (e_r - sum(h[v] for v in p) + 2 - k for p in (a, b))
            cross = 2 * r - 15 - sum(s[v] for v in a) - sum(s[v] for v in b)
            both = 9 + k
        if min(tau1, tau2) < 0:
            counts["DIFFERENT_TAU"] += 1
            continue
        counts["DIFFERENT_RETAINED"] += 1
        values.append(tau1 + tau2 + both + cross)
    require(bool(values) and min(values) >= 0, "no retained branch/negative correction")
    return min(values), counts


def records_bytes(records: Sequence[Record]) -> bytes:
    """Schema-v1 tuples encode as JSON arrays; compact separators, UTF-8, one LF."""
    return (json.dumps(records, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def enumerate_records(independent: bool = False) -> tuple[list[Record], Counter[str]]:
    raw = canonical_sigmas(independent)
    require(len(raw) == len(set(raw)) == 2835, "incomplete raw domain")
    zero = zero_maxima(independent)
    kept = sorted(s for s in raw if sum(s) in R_VALUES)
    require(len(kept) == 1087, "incomplete filtered domain")
    records: list[Record] = []
    totals: Counter[str] = Counter()
    for s in kept:
        r = sum(s)
        branch = "A" if s[14] < 5 else "B" if s[13] < 5 else "C"
        totals[branch] += 1
        penalty, counts = corrections(s, independent)
        totals.update(counts)
        core = (
            sum(v * (v - d - 4) for v, d in zip(s, D[:15], strict=True)) + 234
            if not independent
            else 294
            - 5 * (54 + r) // 2
            - 15 * (r - 10) // 2
            + sum(v * (8 - d + v) for v, d in zip(s, D[:15], strict=True))
            - 2 * r
        )
        records.append((s, r, zero[r], penalty, core + zero[r] - penalty, branch))
    return records, totals


def enumeration() -> Document:
    first, counts = enumerate_records()
    second, recount = enumerate_records(True)
    require(first == second and counts == recount, "independent domain/correction recount")
    expected = {
        "A": 705,
        "B": 314,
        "C": 68,
        "SAME_CANDIDATES": 4966,
        "SAME_D2": 382,
        "SAME_DEGREE": 11,
        "SAME_RETAINED": 4573,
        "DIFFERENT_CANDIDATES": 413712,
        "DIFFERENT_IDENTICAL": 5304,
        "DIFFERENT_D2": 8976,
        "DIFFERENT_TAU": 1452,
        "DIFFERENT_RETAINED": 397980,
    }
    require(dict(counts) == expected, "finite-domain exclusion counts")
    maxima = [max(row[4] for row in first if row[1] == r) for r in R_VALUES]
    require(tuple(maxima) == EXPECTED_MAXIMA and max(maxima) == 248, "r maxima/T248")
    payload = records_bytes(first)
    require(payload == records_bytes(second), "independent canonical bytes")
    return {
        "RAW_CANONICAL_SIGMA": 2835,
        "RETAINED_SIGMA": len(first),
        "ZERO_GRAPHS": 1024,
        "COUNTS": dict(counts),
        "R_VALUES": list(R_VALUES),
        "R_MAXIMA": maxima,
        "ZERO_MAXIMA": {str(r): v for r, v in sorted(zero_maxima().items())},
        "RECORD_SCHEMA": [
            "SIGMA[15]",
            "R",
            "MAX_SUM_ZETA_SQUARED",
            "MIN_P_CORRECTION",
            "T_UPPER_BOUND",
            "BRANCH_A_B_C",
        ],
        "SERIALIZATION": "v1: lexicographic SIGMA order; JSON arrays; decimal exact integers; "
        "ASCII branch strings; compact comma/colon separators; UTF-8; one LF",
        "RECORDS": first,
        "RECORDS_SHA256": sha(payload),
        "INDEPENDENT_RECOUNT": "PASS_RECORD_FOR_RECORD_AND_BYTE_FOR_BYTE",
        "COVERAGE": "EVERY_LEGAL_REALIZATION_MAPS_TO_NECESSARY_CONDITION_SUPERSET",
        "LEGACY_RESEARCH_DIGEST": LEGACY_SHA,
        "LEGACY_DIGEST_MATCH": "NOT_VERIFIED",
        "LEGACY_REASON": "Original serialization unavailable; Owner authorized schema-v1 digest",
        "LEGAL_T248_ATTAINMENT": "NOT_ASSERTED",
    }


def route_terms(pid: str, cap: int, floor: int = 112, constant: int = 5954) -> list[Term]:
    d = inherited.profile(pid)
    require(type(cap) is int and 22 <= cap <= 275 and type(floor) is int, "envelope domain")
    g = [6 + v for v in d]
    w, u, a = (
        sum(comb(v, 2) for v in g),
        sum(comb(v, 3) for v in g),
        sum(v * (4 + v) for v in d) // 3,
    )
    terms: list[Term] = []
    for t in range(22, cap + 1):
        excess = u - (max(g) - 2) * (w - 3 * t)
        q = max(0, -(-excess // 4))
        c = min(q, a)
        s4 = max(floor, 679 * q - 231 * c)
        s3 = 2800 * w + 11872 * (t - 22) - 30800
        total = 372_228_640 - 63_838_600 + s3
        bound = total - 4 * s4 // 7
        fraction_q = max(Fraction(0), Fraction(excess, 4))
        exact = Fraction(total) - Fraction(4 * s4, 7)
        require(q - 1 < fraction_q <= q and bound - 1 < exact <= bound, "ceil/floor directions")
        if pid == TARGET:
            require(
                excess == 30 * t - constant and constant == 5954 and (w, u, a) == (828, 2326, 198),
                "5954 profile identity",
            )
        terms.append((t, bound, q, c, s4, s3))
    require(terms == split.route_b_terms(d, cap, floor), "official Route-B differs")
    return terms


def verify_result(document: Document) -> None:
    require(render(document) == render(compute_result()), "incomplete or tampered result")


def source_pins() -> dict[str, str]:
    pending = [
        inherited.SOURCE,
        "src/lottolab/research/b649_k20_min_s2_topw12_split_cap_certificate_r1.py",
    ]
    pins: dict[str, str] = {}
    while pending:
        path = pending.pop()
        if path in pins:
            continue
        raw = git("cat-file", "blob", f"{BASE_HEAD}:{path}")
        inherited.checked_blob(BASE_HEAD, path, sha(raw))
        require((ROOT / path).read_bytes() == raw, f"tampered reused source {path}")
        pins[path] = sha(raw)
        for node in ast.walk(ast.parse(raw)):
            if isinstance(node, ast.ImportFrom) and node.level:
                require(node.level == 1, "relative import depth")
                names = [node.module] if node.module else [a.name for a in node.names]
                pending.extend(f"src/lottolab/research/{name}.py" for name in names)
    return dict(sorted(pins.items()))


def load_inputs() -> tuple[Document, Document, Document]:
    out: list[Document] = []
    for head, tree, path, digest in (
        (BASE_HEAD, BASE_TREE, BASE_RESULT, BASE_SHA),
        (R2_HEAD, R2_TREE, R2_RESULT, R2_SHA),
        (T223_HEAD, T223_TREE, T223_RESULT, T223_SHA),
    ):
        require(git("rev-parse", f"{head}^{{tree}}").decode().strip() == tree, "pinned tree")
        raw = inherited.checked_blob(head, path, digest)
        out.append(inherited.decode(raw))
    return out[0], out[1], out[2]


def comparison(base: Document, r2: Document, t223: Document) -> tuple[dict[str, int], Document]:
    require(
        sha(render(base)) == BASE_SHA
        and sha(render(r2)) == R2_SHA
        and sha(render(t223)) == T223_SHA,
        "tampered immutable result/cursor",
    )
    before = {p: integer(v) for p, v in obj(base["RESOLVED_ROW_BOUNDS"]).items()}
    require(
        len(before) == 4647 and sha(inherited.projection(before)) == base["BOUNDS_SHA256_AFTER"],
        "incomplete base ledger",
    )
    require(before == obj(r2["RESOLVED_ROW_BOUNDS_BEFORE"]), "R2 base projection")
    cursor = obj(base["CURSOR"])
    coarse = obj(cursor["COARSE_BOUND_PROJECTION"])
    require(
        cursor == r2["CURSOR"] == t223["CURSOR"]
        and len(coarse) == 197
        and set(coarse) == set(inherited.items(cursor["PROFILE_IDS"]))
        and sha(render(cursor)) == base["CURSOR_SHA256"],
        "cursor drift/coverage",
    )
    for pid, bound in coarse.items():
        w = sum(comb(6 + d, 2) for d in inherited.profile(pid))
        require(bound == split.prior.w8.coarse_bound_at_wedges(w), "cursor replay")
    projected = dict(before)
    for value in inherited.items(r2["CERTIFICATES"]):
        certificate = obj(value)
        pid = inherited.string(certificate["PROFILE_ID"])
        old = route_terms(pid, integer(certificate["OLD_T_CAP"]))
        new = route_terms(pid, integer(certificate["NEW_T_CAP"]))
        require(
            [list(t) for t in old] == certificate["OLD_ALL_T_TERMS"]
            and [list(t) for t in new] == certificate["NEW_ALL_T_TERMS"],
            "R2 full envelopes",
        )
        require(before[pid] == max(t[1] for t in old), "R2 old row")
        projected[pid] = max(t[1] for t in new)
    require(projected == obj(r2["RESOLVED_ROW_BOUNDS_AFTER"]), "R2 changed rows")
    pid = inherited.string(t223["TARGET_PROFILE"])
    require(pid == "66555555554442000000" and t223["NEW_PROVEN_T_CAP"] == 223, "T223 scope")
    projected[pid] = max(t[1] for t in route_terms(pid, 223))
    require(projected[pid] == t223["FULL_PROFILE_BOUND_AFTER"], "T223 projected row")
    require(
        inherited.family(projected, cursor)[0] == 313_395_060 and projected[TARGET] == 313_395_060,
        "comparison family",
    )
    return projected, cursor


def audit_graph(edges: set[Pair], sigma_sign: int = -1) -> Document:
    require(sigma_sign == -1, "wrong correction sign")
    require(
        all(type(x) is int and type(y) is int and 0 <= x < y < 20 for x, y in edges), "simple graph"
    )
    nb = [{y if x == v else x for x, y in edges if v in (x, y)} for v in range(20)]
    require(tuple(map(len, nb)) == tuple(6 + d for d in D), "wrong graph degrees")
    core, zero = tuple(range(15)), tuple(range(15, 20))
    m, n = set(combinations(core, 2)) - edges, set(combinations(zero, 2)) - edges
    s = tuple(len(nb[v].intersection(zero)) for v in core)
    z = tuple(len(nb[v].intersection(core)) for v in zero)
    parts = (
        split.triangle_count(core, m),
        split.triangle_count(zero, n),
        sum(len(nb[x].intersection(nb[y], zero)) for x, y in m),
        sum(len(nb[x].intersection(nb[y], core)) for x, y in n),
    )
    t = split.triangle_count(tuple(range(20)), edges)
    th = split.triangle_count(tuple(range(20)), set(combinations(range(20), 2)) - edges)
    require(min(parts) >= 0 and t + th == 294 and t == split_f(s, z) - sum(parts), "graph identity")
    return {
        "T": t,
        "P_TERMS": list(parts),
        "SIGMA": s,
        "ZETA": z,
        "SUPPORT_ATTAINMENT": "NOT_ASSERTED",
    }


def compute_result() -> Document:
    facts = model_facts()
    require((facts["W"], facts["CHOOSE3"], facts["A_MAX"]) == (828, 2326, 198), "profile constants")
    pins = source_pins()
    base, r2, t223 = load_inputs()
    before, cursor = comparison(base, r2, t223)
    enum = enumeration()
    old, new = route_terms(TARGET, 265), route_terms(TARGET, 248)
    require(len(old) == 244 and len(new) == 227 and new == old[:227], "complete old/new terms")
    bound = max(t[1] for t in new)
    require(
        max(t[1] for t in old) == before[TARGET] == 313_395_060
        and new[-1] == (248, 313_242_512, 372, 198, 206850, 4970672),
        "profile bound",
    )
    after = {**before, TARGET: bound}
    require([p for p in before if before[p] != after[p]] == [TARGET], "one-row scope")
    family_before, owners_before = inherited.family(before, cursor)
    family_after, owners_after = inherited.family(after, cursor)
    require(
        family_before == family_after == 313_395_060
        and "66655555555332000000" in owners_after
        and bound <= 313_263_888,
        "family/incumbent",
    )
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "SEALED_PENDING_FRESH_JUDGE_AND_LIFECYCLE",
        "OWNER_CONVERSATION_ID": OWNER,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_RESULT_SHA256": BASE_SHA,
        "R2_HEAD": R2_HEAD,
        "R2_TREE": R2_TREE,
        "R2_RESULT_SHA256": R2_SHA,
        "T223_PROJECTION_INPUT": {
            "HEAD": T223_HEAD,
            "TREE": T223_TREE,
            "RESULT_SHA256": T223_SHA,
            "STATUS": t223["TASK_STATUS"],
        },
        "SOURCE_PINS": pins,
        "SOURCE_SHA256": sha((ROOT / SOURCE).read_bytes()),
        "TEST_SHA256": sha((ROOT / TEST).read_bytes()),
        "PROOF": __doc__,
        "MODEL_FACTS": facts,
        "TARGET_PROFILE": TARGET,
        "CURRENT_T_CAP": 265,
        "NEW_PROVEN_T_CAP": 248,
        "CORE_ZERO_IDENTITY": "T=234+sum sigma(sigma-d-4)+sum zeta^2-P",
        "NONNEGATIVE_CORRECTION": "FOUR_EXPLICIT_CARDINALITY_SUMS",
        "SHADOW_COMPANION_PROOF": shadow_audit(),
        "OVERLAP_AUDIT": overlap_audit(),
        "ENUMERATION": enum,
        "CURRENT_S4_FLOOR": 112,
        "S5_ADOPTED": False,
        "K4_FORMULA": "max(0,ceil((30t-5954)/4))",
        "OLD_T_TERMS": old,
        "NEW_T_TERMS": new,
        "FULL_PROFILE_BOUND": bound,
        "PROFILE_DELTA": before[TARGET] - bound,
        "STRICT_GAIN_EXCLUDED": "YES",
        "INCUMBENT": 313_263_888,
        "PROJECTION_STATUS": "CONDITIONAL_THREE_ROW_R2_PLUS_T223; NOT_CANONICAL_ADOPTION",
        "RESOLVED_ROW_BOUNDS_BEFORE": before,
        "RESOLVED_ROW_BOUNDS_AFTER": after,
        "ROWS_CHANGED": [TARGET],
        "CURSOR": cursor,
        "CURSOR_SHA256": sha(render(cursor)),
        "OTHER_4646_ROWS_SHA256": sha(
            inherited.projection({p: b for p, b in before.items() if p != TARGET})
        ),
        "SINGLE_ROW_FAMILY_BOUND": family_after,
        "SINGLE_ROW_FAMILY_DELTA": family_before - family_after,
        "FAMILY_OWNERS_BEFORE": owners_before,
        "FAMILY_OWNERS_AFTER": owners_after,
        "INHERITED_CAVEATS_AND_STATUS_VERBATIM": base["INHERITED_CAVEATS_AND_STATUS_VERBATIM"],
        "BASE_SOURCE_STATUS_VERBATIM": base["SOURCE_STATUS_VERBATIM"],
        "R2_SOURCE_STATUS_VERBATIM": r2["TASK_STATUS"],
        "R14_HISTORICAL_DISPOSITION": (
            "R14_NOT_VERIFIED_SHARED_REFS_CHANGED_DURING_PARALLEL_ACTIVITY"
        ),
        "SHARED_REPOSITORY_IMMUTABILITY": "NOT_CLAIMED; TASK_OWNED_REFS_AUDITED_SEPARATELY",
        "G01_TO_G18_AT_SEAL": {f"G{i:02}": "NOT_VERIFIED" for i in range(1, 19)},
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "HEAVY_SOLVER_STARTED": "NO",
        "SOLVER_CALLS": 0,
        "PORTFOLIOS_ENUMERATED": 0,
        "REMOTE_WRITE": "NO",
        "SHARED_LEDGER_MUTATED": "NO",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = compute_result()
    path = ROOT / RESULT
    if args.write:
        with path.open("xb") as output:
            output.write(render(result))
    else:
        require(path.read_bytes() == render(result), "exact result replay")
    print(
        json.dumps(
            {
                "T_CAP": 248,
                "PROFILE_BOUND": result["FULL_PROFILE_BOUND"],
                "RECORDS_SHA256": obj(result["ENUMERATION"])["RECORDS_SHA256"],
                "RESULT_SHA256": sha(path.read_bytes()),
            }
        )
    )


if __name__ == "__main__":
    main()
