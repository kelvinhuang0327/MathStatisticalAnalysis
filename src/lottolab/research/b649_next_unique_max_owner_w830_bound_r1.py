"""Universal W830 triangle cap for exactly 66665555555321100000.

MODEL AND ORACLE RE-DERIVATION. There are twenty six-label tickets, 22
triple labels and 27 pair labels (20*6=3*22+2*27), with pair-linearity.
d_v counts triple labels at ticket v; p_v=6-d_v counts pair labels. The
simple support graph G joins tickets that share a label; every triple gives
an edge-disjoint triangle. Thus g_v=2d_v+p_v=6+d_v, e(G)=93 and T>=22.
Reading the exact profile gives 6^4,5^7,3^1,2^1,1^2,0^5; sum d=66,
sum d^2=334, sum g=186, W=sum C(g,2)=830, J=sum C(g,3)=2345.
For H=complement(G), every nonmonochromatic vertex triple contributes two
mixed wedges: T(G)+T(H)=C(20,3)-sum g_v(19-g_v)/2=296 (Goodman).
K={d>0}, Z={d=0} have sizes 15,5. These constants are computed from this
profile, never imported from the preceding W827/Goodman293 profiles.

TWO-SHORE IDENTITY. Write X=K,Y=Z, x=15,y=5, M=H[X], N=H[Y]. Let s_v
count G-neighbours on the other shore, c=sum_X s=sum_Y s, a_v=x-1-g_v+s_v
on X and b_v=y-1-g_v+s_v on Y. For uv in M, the number of H-common
neighbours on Y is y-s_u-s_v+c_Y(uv), where c_Y counts G-common neighbours
on Y. The symmetric count holds for edges of N. Summing each edge count
and the within-shore triangles gives
 T(H)=T(M)+T(N)+y*e(M)+x*e(N)-sum_X a_v*s_v-sum_Y b_v*s_v
       +sum_E(M)c_Y+sum_E(N)c_X.
Since 2e(M)=sum_X(x-1-g_v)+c and similarly for N, define
 2Q=y*sum_X(x-1-g_v)+x*sum_Y(y-1-g_v), here Q=60.
Consequently the EXACT identity is
 T(G)=296-Q-10c+sum_X s_v*a_v+sum_Y s_v*b_v-P,
 P=T(M)+T(N)+sum_E(M)c_Y+sum_E(N)c_X >= 0.
Each summand of P counts triangles or common neighbours and is nonnegative.
Replacing P by a valid lower bound raises this upper-bound expression.

VARIABLES AND NECESSARY CONDITIONS. sigma_v=s_v on K; zeta_u=s_u on Z;
r=c=sum sigma=sum zeta. Every K-Z edge uses a pair label (Z has no triple
label), so 0<=sigma_v<=min(5,6-d_v): d6:0, d5:0..1, d3:0..3,
d2:0..4, d1:0..5. Each Z vertex has g=6 and at most four Z neighbours,
so 2<=zeta_u<=6. M degrees are 8-d_v+sigma_v, N degrees zeta_u-2;
G[Z] degrees are 6-zeta_u. The M and G[Z] degree sequences must satisfy
all Erdos-Gallai inequalities, parity and simple-graph degree ranges.
The crossing graph is bipartite: both Gale-Ryser directions and equal sums
are necessary. A graphical G[Z] has graphical complement N. These screens
cannot reject any legal realization. Simultaneous compatibility, triple
packing and further support constraints are omitted, enlarging the set.

REMAINDER FLOORS. For a graph F with degree list a, n vertices and e edges,
any size-h vertex subset S has
 I(a,h)=max(0,e-sum(the n-h largest degrees)) <= e(F[S]):
each edge outside S has an endpoint outside S. Hence double counting gives
 sum_E(N)c_X=sum_{v in K}e(N[N_G(v) cap Z])>=sum_K I(b,sigma_v),
 sum_E(M)c_Y>=sum_Z I(a,zeta_u).
For any edge ij of F, its endpoints' neighbour sets are subsets of n
vertices, so |N(i) cap N(j)|>=max(0,a_i+a_j-n). Summing the untruncated
inequality over edges gives 3T(F)>=sum a_i^2-n*e; take its ceiling over 3
and MAX with zero. A second floor takes L, the h largest-degree vertices.
At most sum_{outside}min(h,a_i) edges cross from L, so
 ell=max(0,ceil((sum_L a_i-sum_out min(h,a_i))/2))<=e(F[L]).
Each of those edges has the nonnegative pair weight max(0,a_i+a_j-n),
so their common-neighbour sum C is >= the sum of the ell smallest weights
among all pairs in L. Exactly C=3*T_3+T_2, where T_j counts F-triangles
with j vertices in L. Thus T(F)>=C-2*C(h,3). Take MAX over h, the first
floor and zero. The four floors concern FOUR DISTINCT summands of P;
their sum is a lower bound on P, without double subtraction.

FINITE RELAXATION AND COVERAGE. The identity becomes
 T=236-10r+sum_K sigma*(8-d+sigma)+sum_Z zeta*(zeta-2)-P.
Enumerate sorted sigma multisets independently inside each equal-d class
and a sorted zeta multiset. Any labelled realization maps to one such
signature: all tests, scores and floors are invariant under these within-
class/shore permutations; no claim of simultaneous realizability is made.
The full product has 1*8*4*5*21=3360 sigma signatures and C(9,5)=126
zeta multisets. Exactly 11410 pairs have equal crossing sums; first-failure
screens reject 5385 for M, 3120 for G[Z], and 8 for crossing bigraphicality.
All 2897 retained states and all maximizing states are stored. Subtracting
the four floors gives maximum 257. Its unique sorted argmax has d5 sigmas
0^5,1^2, d3 sigma 0, d2 sigma 4, d1 sigmas 5,5 (d6 zero), zeta=2,3,3,3,5.
At that state raw=268, floors (T_M,T_N,C_K,C_Z)=(5,0,6,0).
Every legal realization is covered, so T<=257 universally. This is a
sufficient stopping certificate; minimal possible triangle cap is not sought.

FIXED BASE ROUTE B AND ROUNDING. The accepted exact R30 cap, NB and class
cap are checked in the pinned Mathematical Base; their minimum is old 264.
At each t, o=830-3t>=0. In N_G(v), each open wedge spoils at most g_v-2
neighbour triples, so 4*q>=J-(g_max-2)*o and
 L=max(0,ceil((2345-10*o)/4)) is a K4 LOWER bound. Overcounting spoiled
triples only weakens this bound. Pair-linearity forbids two contained triple
supports in one K4. For each triple support S, its common outside neighbours
are <=min_{v in S}(g_v-2), hence <=their average; summing over supports
bounds contained-triple K4 by A_max=floor(sum d_v*(g_v-2)/3)=floor(598/3)=199.
The Base exact quartet weights (re-executed) are 448 with a contained triple
and 679 without. All other quartet terms are nonnegative. For actual q,a,
 S4>=679*q-231*a>=f(q)=679*q-231*min(q,199)>=f(L),
since f increases by 448 up to 199 and 679 thereafter. Combine with the
Base exact S4 floor 112 by MAX, never ADD. No S4-by-t or adopted S5 authority
for this exact profile exists in the fixed Base; S5 is not used.
The Base exact local intersections give S3=2800*o+20272*(t-22)+154000:
open wedges weigh 2800; non-support triangles 20272; 22 supports weigh 7000.
For a seven-label outcome, each winning ticket supplies a three-hit subset;
pair-linearity makes all their pairs distinct, so 3*r<=C(7,2) and r<=7.
For integer 0<=r<=7, 1_{r>0}<=r-C(r,2)+C(r,3)-(4/7)*C(r,4).
Summing and using the negative coefficient of S4 yields the exact Fraction
CEILING of S1-S2+S3-4*S4/7, S1=372228640,S2=63838600. Every t in old
22..264 and new 22..257 is retained, evaluated by the pinned Route B and
independently checked; all terms and ALL argmax are stored.

FULL FAMILY AND CAVEATS. Replay the complete pinned input result and its
code/evaluator closure, aggregate 4647 resolved and 197 cursor rows, update
ONLY this profile, and aggregate again. The gain is computed from the whole
ledger, never from the target delta 76. All cursor IDs/bounds and all 282
historical exclusions and caveats are preserved, without recertification.
CONDITIONAL_PROJECTION only; no canonical adoption, global optimum or actual
prediction gain. No solver, support graph or portfolio enumeration is used.
Fresh Judge verdict is external to this self-hashed result and frozen tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from fractions import Fraction
from functools import cache
from importlib import import_module
from itertools import combinations, combinations_with_replacement, product
from math import comb
from pathlib import Path
from typing import Any, cast

# The frozen upstream modules are dynamically typed; isolate them at this boundary.
direct: Any = import_module("lottolab.research.b649_next_two_resolved_frontier_resume_r2")
upstream: Any = direct.upstream
route: Any = direct.route
type Record = dict[str, Any]
type Term = tuple[int, int, int, int, int, int]

TASK_ID = "B649_NEXT_UNIQUE_MAX_OWNER_W830_BOUND_R1"
INPUT_HEAD = "1300ae2728497f7ec86b8ccae076c95b1327b133"
INPUT_TREE = "dfba56c976d76f48666d50b8c60a511d0366d7db"
BASE_HEAD = "8d08e843b30300e8379f63e7dc9db401581e2e5e"
BASE_TREE = "231494ec0995981d2324cc5ef697ba4b1975b2f0"
INPUT_RESULT: str = direct.RESULT
INPUT_SHA = "af220b94e81bbf42ec88bcb18acea2ac7df2c5f226e86a9f61ff45eb8c1e2272"
BASE_RESULT: str = direct.BASE_RESULT
BASE_SHA: str = direct.BASE_SHA
R30_PATH: str = direct.R30_PATH
R30_SHA: str = direct.R30_SHA
PROFILE = "66665555555321100000"
PROFILE_IDS = (PROFILE,)
EXPECTED_FAMILY_BEFORE = 313391636
EXPECTED_NEXT_BOUND = 313391560
RESOLVED_COUNT, CURSOR_COUNT, EXCLUDED_COUNT, RAW_COUNT = 4647, 197, 282, 5126
S1_MINUS_S2 = 372228640 - 63838600
KZ_REJECTIONS = ("non-graphical M=H[K]", "non-graphical G[Z]", "bipartite crossing inequalities")
SOURCE = "src/lottolab/research/b649_next_unique_max_owner_w830_bound_r1.py"
TEST = "tests/unit/test_b649_next_unique_max_owner_w830_bound_r1.py"
RESULT = "docs/research/matrix-native-results/b649-next-unique-max-owner-w830-bound-r1-result.json"
ROOT = Path(__file__).resolve().parents[3]
CODE_PINS = {
    direct.SOURCE: "6e6e086aa8e02ea9b8e93f6d13e0841ec33d69c41917f716041492cfe26afd0d",
    direct.TEST: "c620a08b32d0845aecd578095a99982293430695ba788c534349bb4c203a12ef",
}


def require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def render(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def unique_object(pairs: list[tuple[str, Any]]) -> Record:
    require(len(pairs) == len({k for k, _ in pairs}), "duplicate JSON/ledger row")
    return dict(pairs)


def decode(raw: bytes) -> Record:
    return cast(Record, json.loads(raw, object_pairs_hook=unique_object))


def git(*args: str, repo: Path = ROOT) -> str:
    return subprocess.check_output(["git", *args], cwd=repo).decode().strip()


def blob(head: str, path: str, repo: Path = ROOT) -> bytes:
    return subprocess.check_output(["git", "show", f"{head}:{path}"], cwd=repo)


def pinned_blob(head: str, path: str, digest: str, repo: Path = ROOT) -> bytes:
    data = blob(head, path, repo)
    require(sha(data) == digest, "result/source SHA pin: " + path)
    return data


def ceil_div(numerator: int, denominator: int) -> int:
    require(type(numerator) is int and type(denominator) is int and denominator > 0, "ceil")
    return -(-numerator // denominator)


def verify_identity(candidate: str = "HEAD", repo: Path = ROOT) -> str:
    require(sys.version_info[:2] == (3, 13), "Python 3.13 required")
    for head, tree in ((INPUT_HEAD, INPUT_TREE), (BASE_HEAD, BASE_TREE)):
        require(git("rev-parse", head + "^{tree}", repo=repo) == tree, "Git TREE pin")
    head = git("rev-parse", candidate, repo=repo)
    if head == INPUT_HEAD:
        return "INPUT_HEAD_WITH_WORKING_CANDIDATE"
    require(
        git("rev-list", "--parents", "-n", "1", head, repo=repo).split()[1:] == [INPUT_HEAD],
        "direct single-parent child required",
    )
    paths = git("diff-tree", "--no-commit-id", "--name-status", "-r", head, repo=repo)
    require(
        sorted(paths.splitlines()) == sorted(f"A\t{p}" for p in (SOURCE, TEST, RESULT)),
        "exactly three authorized additions required",
    )
    for path in (SOURCE, TEST):
        require((ROOT / path).read_bytes() == blob(head, path, repo), "runtime candidate identity")
    return "FIXED_DIRECT_CHILD"


def replay_input(repo: Path = ROOT) -> tuple[Record, Record, Record]:
    for path, digest in CODE_PINS.items():
        require(
            (ROOT / path).read_bytes() == pinned_blob(INPUT_HEAD, path, digest, repo),
            "direct runtime source identity",
        )
    direct.verify_result(INPUT_HEAD, repo)  # complete recomputation and byte replay
    fixed = decode(pinned_blob(INPUT_HEAD, INPUT_RESULT, INPUT_SHA, repo))
    require(sha((ROOT / INPUT_RESULT).read_bytes()) == INPUT_SHA, "working result SHA pin")
    require(
        fixed["SOURCE_SHA256"] == CODE_PINS[direct.SOURCE]
        and fixed["TEST_SHA256"] == CODE_PINS[direct.TEST],
        "direct certificate code pins",
    )
    base = decode(pinned_blob(BASE_HEAD, BASE_RESULT, BASE_SHA, repo))
    r30 = decode(pinned_blob(BASE_HEAD, R30_PATH, R30_SHA, repo))
    return fixed, base, r30


@cache
def profile_facts(pid: str) -> Record:
    require(pid in PROFILE_IDS, "wrong exact profile")
    d = tuple(map(int, pid))
    require(len(d) == 20 and tuple(sorted(d, reverse=True)) == d, "histogram order/size")
    require(all(0 <= x <= 6 for x in d) and sum(d) == 66, "triple degree histogram")
    g = tuple(6 + x for x in d)
    numerator = sum(x * (19 - x) for x in g)
    require(sum(g) == 186 and sum(g) // 2 == 93 and numerator % 2 == 0, "degree/Goodman model")
    k, z = sum(x > 0 for x in d), d.count(0)
    return {
        "PROFILE_ID": pid,
        "D": list(d),
        "G": list(g),
        "D_HISTOGRAM": {str(x): n for x, n in sorted(Counter(d).items(), reverse=True)},
        "VERTICES": len(d),
        "DEGREE_SUM_D": sum(d),
        "SUM_D_SQUARED": sum(x * x for x in d),
        "DEGREE_SUM_G": sum(g),
        "EDGES": sum(g) // 2,
        "WEDGES": sum(comb(x, 2) for x in g),
        "GOODMAN": comb(20, 3) - numerator // 2,
        "K": k,
        "Z": z,
        "J": sum(comb(x, 3) for x in g),
        "G_MAX": max(g),
        "A_MAX_NUMERATOR": sum(x * (x + 4) for x in d),
        "A_MAX": sum(x * (x + 4) for x in d) // 3,
        "PAIR_DEGREES": [6 - x for x in d],
        "WEDGE_TRIANGLE_CAP": sum(comb(x, 2) for x in g) // 3,
        "ASSUMPTIONS": {
            "TICKETS": 20,
            "LABELS_PER_TICKET": 6,
            "LABELS": 49,
            "TRIPLE_LABELS": 22,
            "PAIR_LABELS": 27,
            "PAIR_LINEARITY": True,
        },
    }


def validate_facts(pid: str, claimed: Mapping[str, Any]) -> None:
    expected = profile_facts(pid)
    require(set(claimed) == set(expected), "profile facts keys")
    for key, value in expected.items():
        require(render(claimed[key]) == render(value), "wrong profile fact: " + key)


def graphical(degrees: Sequence[int]) -> bool:
    """Erdos-Gallai: range, parity and every top-k edge-count inequality."""
    d = sorted(degrees, reverse=True)
    n = len(d)
    return (
        all(type(x) is int and 0 <= x < n for x in d)
        and sum(d) % 2 == 0
        and all(sum(d[:k]) <= k * (k - 1) + sum(min(k, x) for x in d[k:]) for k in range(1, n + 1))
    )


def bipartite_necessary(left: Sequence[int], right: Sequence[int]) -> bool:
    """Gale-Ryser conditions in both directions plus equal sums."""
    a, b = sorted(left, reverse=True), sorted(right, reverse=True)
    return (
        sum(a) == sum(b)
        and all(sum(a[:h]) <= sum(min(h, x) for x in b) for h in range(1, len(a) + 1))
        and all(sum(b[:h]) <= sum(min(h, x) for x in a) for h in range(1, len(b) + 1))
    )


def subset_edge_lower(degrees: Sequence[int], size: int) -> int:
    """Remainder bound (i): edges inside any `size`-subset of a graph with these degrees."""
    require(type(size) is int and 0 <= size <= len(degrees), "subset size")
    d = sorted(degrees, reverse=True)
    require(sum(d) % 2 == 0, "degree parity")
    return max(0, sum(d) // 2 - sum(d[: len(d) - size]))


@cache
def triangle_lower(degrees: tuple[int, ...]) -> int:
    """Remainder bound (iii): triangles of any graph with these degrees."""
    d = sorted(degrees, reverse=True)
    n, e = len(d), sum(d) // 2
    lower = max(0, ceil_div(sum(x * x for x in d) - n * e, 3))
    for h in range(1, n + 1):
        ell = max(0, ceil_div(sum(d[:h]) - sum(min(h, x) for x in d[h:]), 2))
        weights = sorted(max(0, a + b - n) for a, b in combinations(d[:h], 2))
        require(ell <= len(weights), "impossible necessary degree sequence")
        lower = max(lower, sum(weights[:ell]) - 2 * comb(h, 3))
    return lower


def split_constant(g_x: Sequence[int], g_y: Sequence[int]) -> int:
    x, y = len(g_x), len(g_y)
    require(x + y == 20 and x > 0 and y > 0, "two-shore partition")
    twice = y * sum(x - 1 - v for v in g_x) + x * sum(y - 1 - v for v in g_y)
    require(twice % 2 == 0, "two-shore constant parity")
    return twice // 2


def kz_premises(pid: str) -> Record:
    f = profile_facts(pid)
    d = f["D"]
    k, z = f["K"], f["Z"]
    q = split_constant([6 + x for x in d if x > 0], [6] * z)
    require(q == 3 * z * (k - 11), "K/Z constant")
    return {
        "PARTITION": "X=K={d>0}; Y=Z={d=0}",
        "K": k,
        "Z": z,
        "VARIABLES": {
            "SIGMA": "sigma_v=|N_G(v) cap Z| for v in K",
            "ZETA": "zeta_u=|N_G(u) cap K| for u in Z",
            "R": "r=sum_K sigma=sum_Z zeta=crossing G-edges",
        },
        "SIGMA_RANGE_BY_D": {
            str(v): [0, min(z, 6 - v)] for v in sorted({x for x in d if x > 0}, reverse=True)
        },
        "ZETA_RANGE": [max(0, 7 - z), min(k, 6)],
        "JOINT_CONDITIONS": [
            "sum sigma == sum zeta",
            "deg_M=k-7-d+sigma graphical on K",
            "G[Z] degrees 6-zeta graphical on Z",
            "(sigma,zeta) bigraphic (Gale-Ryser both directions)",
        ],
        "M_DEGREE": f"{k - 7}-d+sigma",
        "N_DEGREE": f"zeta{z - 7:+d}",
        "M_EDGE_SUM": f"{k * (k - 7) - 66}+r",
        "N_EDGE_SUM": f"r{z * (z - 7):+d}",
        "Q": q,
        "UPPER_CONSTANT": f["GOODMAN"] - q,
    }


def validate_kz_premises(pid: str, claimed: Mapping[str, Any]) -> None:
    expected = kz_premises(pid)
    require(
        (claimed.get("K"), claimed.get("Z")) == (expected["K"], expected["Z"]), "wrong K/Z split"
    )
    require(claimed.get("SIGMA_RANGE_BY_D") == expected["SIGMA_RANGE_BY_D"], "wrong sigma range")
    require(claimed.get("ZETA_RANGE") == expected["ZETA_RANGE"], "wrong zeta range")
    require(render(dict(claimed)) == render(expected), "wrong K/Z premises")


def kz_state(
    pid: str, sigma_by_d: Sequence[tuple[int, Sequence[int]]], zeta: Sequence[int]
) -> Record:
    """One sorted state; raises with the first violated necessary condition."""
    f, prem = profile_facts(pid), kz_premises(pid)
    k, z = prem["K"], prem["Z"]
    classes = Counter(x for x in f["D"] if x > 0)
    require(
        [v for v, _ in sigma_by_d] == sorted(classes, reverse=True)
        and all(len(s) == classes[v] for v, s in sigma_by_d),
        "sigma degree classes",
    )
    for v, values in sigma_by_d:
        low, high = prem["SIGMA_RANGE_BY_D"][str(v)]
        require(all(type(s) is int and low <= s <= high for s in values), "sigma range")
    zlow, zhigh = prem["ZETA_RANGE"]
    require(
        len(zeta) == z and all(type(s) is int and zlow <= s <= zhigh for s in zeta), "zeta range"
    )
    pairs = [(v, s) for v, values in sigma_by_d for s in values]
    sigma = [s for _, s in pairs]
    r = sum(sigma)
    require(r == sum(zeta), "crossing sums")
    m = tuple(k - 7 - v + s for v, s in pairs)
    n = tuple(z - 7 + s for s in zeta)
    require(graphical(m), KZ_REJECTIONS[0])
    require(graphical(tuple(6 - s for s in zeta)), KZ_REJECTIONS[1])
    require(bipartite_necessary(sigma, zeta), KZ_REJECTIONS[2])
    raw = (
        prem["UPPER_CONSTANT"]
        - 10 * r
        + sum(s * a for s, a in zip(sigma, m, strict=True))
        + sum(s * a for s, a in zip(zeta, n, strict=True))
    )
    lower = {
        "T_M": triangle_lower(m),
        "T_N": triangle_lower(n),
        "C_K": sum(subset_edge_lower(n, s) for s in sigma),
        "C_Z": sum(subset_edge_lower(m, s) for s in zeta),
    }
    return {
        "R": r,
        "SIGMA_BY_D": [[v, list(values)] for v, values in sigma_by_d],
        "ZETA": list(zeta),
        "M_DEGREES": list(m),
        "N_DEGREES": list(n),
        "WITHOUT_REMAINDER": raw,
        "REMAINDER_LOWER": lower,
        "UPPER": raw - sum(lower.values()),
    }


def kz_state_row(state: Mapping[str, Any]) -> str:
    """Compact, exactly reproducible text row of one retained K/Z state."""
    sigma = ",".join(f"{v}:" + "".join(map(str, s)) for v, s in state["SIGMA_BY_D"])
    low = state["REMAINDER_LOWER"]
    return (
        f"r={state['R']};sigma={sigma};zeta={''.join(map(str, state['ZETA']))};"
        f"raw={state['WITHOUT_REMAINDER']};T_M={low['T_M']};T_N={low['T_N']};"
        f"C_K={low['C_K']};C_Z={low['C_Z']};upper={state['UPPER']}"
    )


@cache
def kz_relaxation(pid: str) -> Record:
    f, prem = profile_facts(pid), kz_premises(pid)
    groups = sorted(Counter(x for x in f["D"] if x > 0).items(), reverse=True)
    choices = [
        tuple(combinations_with_replacement(range(prem["SIGMA_RANGE_BY_D"][str(v)][1] + 1), n))
        for v, n in groups
    ]
    zlow, zhigh = cast(list[int], prem["ZETA_RANGE"])
    z: int = prem["Z"]
    zetas = tuple(combinations_with_replacement(range(zlow, zhigh + 1), z))
    graphical_zetas = [s for s in zetas if graphical(tuple(6 - x for x in s))]
    states: list[Record] = []
    rejected = Counter[str]()
    signatures = range_only = 0
    range_cap = -(10**9)
    for parts in product(*choices):
        signatures += 1
        sigma_by_d = [(v, part) for (v, _), part in zip(groups, parts, strict=True)]
        pairs = [(v, s) for v, part in sigma_by_d for s in part]
        r = sum(s for _, s in pairs)
        score = sum(s * (prem["K"] - 7 - v + s) for v, s in pairs)
        for zeta in zetas:
            if sum(zeta) != r:
                continue
            range_only += 1
            raw = (
                prem["UPPER_CONSTANT"] - 10 * r + score + sum(s * (prem["Z"] - 7 + s) for s in zeta)
            )
            range_cap = max(range_cap, raw)
            try:
                states.append(kz_state(pid, sigma_by_d, zeta))
            except ValueError as error:
                require(str(error) in KZ_REJECTIONS, "unexpected K/Z state rejection")
                rejected[str(error)] += 1
    require(bool(states), "empty K/Z relaxation")
    require(len(states) + rejected.total() == range_only, "K/Z state accounting")
    cap = max(s["UPPER"] for s in states)

    def ablation(drop: Sequence[str]) -> int:
        return max(s["UPPER"] + sum(s["REMAINDER_LOWER"][key] for key in drop) for s in states)

    rows = [kz_state_row(s) for s in states]
    return {
        "PARTITION": prem["PARTITION"],
        "PREMISES": prem,
        "CAP": cap,
        "SIGMA_SIGNATURES": signatures,
        "ZETA_MULTISETS_IN_RANGE": len(zetas),
        "GRAPHICAL_ZETA_MULTISETS": len(graphical_zetas),
        "RANGE_STATES_WITH_EQUAL_CROSSING_SUMS": range_only,
        "REJECTED_BY_FIRST_FAILED_CONDITION": dict(sorted(rejected.items())),
        "RETAINED_STATE_COUNT": len(states),
        "RETAINED_STATES_SHA256": sha(render(rows)),
        "PER_R_MAXIMUM": {
            str(r): max(s["UPPER"] for s in states if s["R"] == r)
            for r in sorted({s["R"] for s in states})
        },
        "ALL_ARGMAX": [s for s in states if s["UPPER"] == cap],
        "ABLATION_CAPS": {
            "RANGE_AND_CROSSING_SUM_ONLY": range_cap,
            "NECESSARY_CONDITIONS_NO_REMAINDER": ablation(("T_M", "T_N", "C_K", "C_Z")),
            "ONLY_C_K_REMAINDER": ablation(("T_M", "T_N", "C_Z")),
            "ONLY_C_Z_REMAINDER": ablation(("T_M", "T_N", "C_K")),
            "ONLY_TRIANGLE_REMAINDERS": ablation(("C_K", "C_Z")),
            "ALL_FOUR_REMAINDERS": cap,
        },
        "REALIZABILITY": "NOT_ASSERTED; NECESSARY_CONDITION_RELAXATION",
        "RETAINED_STATE_ROWS": rows,
    }


def validate_kz_coverage(pid: str, claimed: Mapping[str, Any]) -> None:
    expected = kz_relaxation(pid)
    for key in (
        "SIGMA_SIGNATURES",
        "ZETA_MULTISETS_IN_RANGE",
        "RANGE_STATES_WITH_EQUAL_CROSSING_SUMS",
        "RETAINED_STATE_COUNT",
    ):
        require(claimed.get(key) == expected[key], "wrong K/Z relaxation coverage: " + key)
    rows = claimed.get("RETAINED_STATE_ROWS")
    require(
        rows == expected["RETAINED_STATE_ROWS"]
        and claimed.get("RETAINED_STATES_SHA256") == sha(render(rows)),
        "wrong K/Z relaxation coverage: states",
    )
    require(render(claimed.get("ALL_ARGMAX")) == render(expected["ALL_ARGMAX"]), "K/Z argmax")
    require(render(dict(claimed)) == render(expected), "wrong K/Z certificate")


def base_authority(pid: str, r30: Mapping[str, Any]) -> Record:
    d = tuple(map(int, pid))
    records = [
        a
        for a in r30["GROUP_ATTEMPTS"]
        if a.get("PROFILE_IDS") == [pid] and a.get("STATUS") == "INFEASIBLE"
    ]
    require(bool(records), "missing exact-profile R30 authority")
    ref = min(records, key=lambda a: a["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"])
    accepted = ref["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"]
    require(route.r28.r26.accepted_cap(ref, (d,), accepted) == accepted, "Base rejected R30 cap")
    nb, cls = upstream.r2.nb.profile_nb_cap(d)[2], upstream.r2.nb.r18_cap(d)
    return {
        "ACCEPTED_R30_CAP": accepted,
        "R30_ATTEMPT": ref,
        "R30_EXACT_PROFILE_ATTEMPTS": len(records),
        "R30_RESULT_SHA256": R30_SHA,
        "NB_CAP": nb,
        "CLASS_CAP": cls,
        "OLD_CAP": min(accepted, nb, cls),
        "S4_BASE": route.r28.profile_s4_floor(d),
        "S4_BY_T": {},
        "S5_USED": False,
    }


def validate_s4_s5(pid: str, base: Mapping[str, Any], auth: Mapping[str, Any]) -> None:
    require(auth["S4_BASE"] == route.r28.profile_s4_floor(tuple(map(int, pid))), "S4 authority")
    require(auth["S4_BASE"] == 112 and auth["S4_BY_T"] == {}, "S4 authority")
    adopted = (
        pid in base["CERTIFICATES_ADOPTED"]
        or pid in base["PROFILE_CERTIFICATES"]
        or base["INHERITED_TARGET_BONFERRONI_5"]["PROFILE_ID"] == pid
    )
    require(base["ALL_T_BONFERRONI_5_ADOPTION"] == "NOT_VERIFIED" and not adopted, "S5 authority")
    require(auth["S5_USED"] is False, "S5 authority")


def exact_term(pid: str, t: int, floor: int) -> Term:
    f = profile_facts(pid)
    opened = f["WEDGES"] - 3 * t
    require(opened >= 0 and floor >= 0, "nonnegative premises")
    k4 = max(0, ceil_div(f["J"] - (f["G_MAX"] - 2) * opened, 4))
    contained = min(k4, f["A_MAX"])
    s4 = max(floor, 448 * contained + 679 * (k4 - contained))
    s3 = 2800 * opened + 20272 * (t - 22) + 154000
    exact = Fraction(S1_MINUS_S2 + s3) - Fraction(4 * s4, 7)
    return t, ceil_div(exact.numerator, exact.denominator), k4, contained, s4, s3


def validate_envelope(pid: str, cap: int, floor: int, terms: Sequence[Sequence[int]]) -> None:
    f = profile_facts(pid)
    require(type(cap) is int and 22 <= cap <= f["WEDGE_TRIANGLE_CAP"], "T cap range")
    require(type(floor) is int and floor >= 0, "S4 floor premise")
    require([row[0] for row in terms] == list(range(22, cap + 1)), "incomplete envelope")
    for row in terms:
        require(len(row) == 6 and all(type(x) is int for x in row), "term shape/integrality")
        expected = exact_term(pid, row[0], floor)
        for at, message in (
            (2, "K4 ceiling"),
            (3, "A_max contained-K4"),
            (4, "S4 MAX floor"),
            (5, "S3 identity"),
            (1, "Fraction ceiling"),
        ):
            require(row[at] == expected[at], message)


def envelope(pid: str, cap: int, floor: int) -> list[Term]:
    d = tuple(profile_facts(pid)["D"])
    a_max = route.contained_triple_k4_cap(d)
    require(a_max == profile_facts(pid)["A_MAX"], "Base A_max")
    terms = [cast(Term, tuple(route.envelope_term(d, t, floor, a_max))) for t in range(22, cap + 1)]
    validate_envelope(pid, cap, floor, terms)
    return terms


def checked_rows(rows: Sequence[tuple[str, int]], expected: Mapping[str, int]) -> dict[str, int]:
    require(len(rows) == len(expected) == len({p for p, _ in rows}), "ledger row count/duplicate")
    require(
        all(type(b) is int for _, b in rows) and dict(rows) == expected, "ledger row identity/bound"
    )
    return dict(rows)


def family_summary(resolved: Mapping[str, int], cursor: Mapping[str, int]) -> Record:
    require(len(resolved) == RESOLVED_COUNT and len(cursor) == CURSOR_COUNT, "family row count")
    require(not resolved.keys() & cursor.keys(), "family ledger overlap")
    require(all(type(b) is int for b in (*resolved.values(), *cursor.values())), "ledger integers")
    rows = dict(resolved) | dict(cursor)
    levels = sorted(set(rows.values()), reverse=True)
    return {
        "MAXIMUM": levels[0],
        "ALL_MAX_OWNERS": sorted(p for p, b in rows.items() if b == levels[0]),
        "NEXT_DISTINCT_BOUND": levels[1],
        "ALL_NEXT_DISTINCT_OWNERS": sorted(p for p, b in rows.items() if b == levels[1]),
        "CURSOR_MAXIMUM": max(cursor.values()),
        "RESOLVED_MAXIMUM": max(resolved.values()),
        "CURSOR_ROWS_SCANNED": len(cursor),
        "RESOLVED_ROWS_SCANNED": len(resolved),
        "TOTAL_PROJECTED_ROWS": len(rows),
    }


def validate_cap(pid: str, cap: object) -> None:
    require(type(cap) is int and cap == kz_relaxation(pid)["CAP"], "wrong triangle cap")


def replace_owner(
    resolved: Mapping[str, int], new: Mapping[str, int], owners: Sequence[str]
) -> dict[str, int]:
    require(
        len(resolved) == RESOLVED_COUNT and list(owners) == [PROFILE] and set(new) == {PROFILE},
        "complete unique maximum owner required",
    )
    require(
        type(new[PROFILE]) is int and new[PROFILE] < resolved[PROFILE], "strict owner tightening"
    )
    return {p: new.get(p, b) for p, b in resolved.items()}


def validate_family(
    resolved: Mapping[str, int], cursor: Mapping[str, int], claimed: Mapping[str, Any]
) -> None:
    require(render(claimed) == render(family_summary(resolved, cursor)), "wrong family aggregation")


def ledger_partition(
    resolved: Mapping[str, int], cursor: Mapping[str, int], fixed: Mapping[str, Any]
) -> Record:
    raw = {"".join(map(str, p)): upstream.wedges(p) for p in upstream.raw_histograms()}
    require(len(raw) == RAW_COUNT, "raw histogram census")
    require(cursor == fixed["CURSOR_197_PRESERVED"]["ROW_BOUNDS"], "cursor ledger")
    require(set(cursor) == {p for p, w in raw.items() if w <= 785}, "cursor partition")
    require(set(resolved) <= raw.keys() and not set(resolved) & set(cursor), "resolved partition")
    excluded = sorted(raw.keys() - set(cursor) - set(resolved), reverse=True)
    inherited = fixed["INHERITED_EXCLUSION"]["ORIGINAL_CONDITIONS_VERBATIM"]
    require(
        len(excluded) == EXCLUDED_COUNT == inherited["COUNT"]
        and upstream.ids_digest(excluded) == inherited["IDS_SHA256"]
        and [min(raw[p] for p in excluded), max(raw[p] for p in excluded)] == inherited["W_RANGE"],
        "inherited exclusion partition",
    )
    return {
        "RAW_HISTOGRAMS": len(raw),
        "RESOLVED_COUNT": len(resolved),
        "CURSOR_COUNT": len(cursor),
        "EXCLUDED_COUNT": len(excluded),
        "EXCLUDED_IDS_SHA256": upstream.ids_digest(excluded),
        "CURSOR_W_HISTOGRAM": {
            str(w): n for w, n in sorted(Counter(raw[p] for p in cursor).items())
        },
        "OWNER_W": {PROFILE: raw[PROFILE]},
    }


def compute_result(candidate: str = "HEAD", repo: Path = ROOT) -> Record:
    mode = verify_identity(candidate, repo)
    fixed, base, r30 = replay_input(repo)
    source_pins = upstream.r2.source_pins()
    require(source_pins == fixed["EVALUATOR_SOURCE_PINS"], "Base evaluator closure pins")
    resolved = checked_rows(
        list(fixed["RESOLVED_ROWS_AFTER"].items()), fixed["RESOLVED_ROWS_AFTER"]
    )
    fixed_cursor = fixed["CURSOR_197_PRESERVED"]["ROW_BOUNDS"]
    cursor = checked_rows(list(fixed_cursor.items()), fixed_cursor)
    before = family_summary(resolved, cursor)
    require(
        before == fixed["FAMILY_AFTER"]
        and before["MAXIMUM"] == EXPECTED_FAMILY_BEFORE
        and before["ALL_MAX_OWNERS"] == [PROFILE]
        and before["NEXT_DISTINCT_BOUND"] == EXPECTED_NEXT_BOUND
        and fixed["ALL_NEW_MAX_OWNERS"] == [PROFILE],
        "fixed complete family/owner frontier",
    )
    partition = ledger_partition(resolved, cursor, fixed)
    facts = profile_facts(PROFILE)
    auth = base_authority(PROFILE, r30)
    validate_s4_s5(PROFILE, base, auth)
    require((route.K20_S1, route.K20_S2) == (372228640, 63838600), "Base S1/S2")
    weights = route.r30.k4_quartet_weights()
    require(
        weights == route.K4_WEIGHTS == {route.WITH_TRIPLE: 448, route.WITHOUT_TRIPLE: 679},
        "Base K4 local weights",
    )
    old_cap, floor = auth["OLD_CAP"], auth["S4_BASE"]
    old_terms = envelope(PROFILE, old_cap, floor)
    old_bound = max(t[1] for t in old_terms)
    require(
        old_bound == resolved[PROFILE] == base["RESOLVED_ROW_BOUNDS"][PROFILE],
        "old full Base envelope replay",
    )
    relaxation = kz_relaxation(PROFILE)
    new_cap = relaxation["CAP"]
    validate_cap(PROFILE, new_cap)
    require(22 <= new_cap < old_cap, "no proven cap improvement")
    new_terms = envelope(PROFILE, new_cap, floor)
    new_bound = max(t[1] for t in new_terms)
    zero_floor = max(t[1] for t in envelope(PROFILE, new_cap, 0))
    after_resolved = replace_owner(resolved, {PROFILE: new_bound}, before["ALL_MAX_OWNERS"])
    require(
        {p: b for p, b in after_resolved.items() if p != PROFILE}
        == {p: b for p, b in resolved.items() if p != PROFILE},
        "other 4646 resolved bounds",
    )
    after = family_summary(after_resolved, cursor)
    status = (
        "PROVEN_FAMILY_GAIN"
        if new_bound < old_bound and after["MAXIMUM"] < before["MAXIMUM"]
        else "NO_PROVEN_FAMILY_GAIN"
    )

    def code_bytes(path: str) -> bytes:
        return (
            (ROOT / path).read_bytes()
            if mode.startswith("INPUT_HEAD")
            else blob(candidate, path, repo)
        )

    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": status,
        "INPUT_CERTIFICATE": {
            "HEAD": INPUT_HEAD,
            "TREE": INPUT_TREE,
            "PATH": INPUT_RESULT,
            "SHA256": INPUT_SHA,
            "REPLAY": "COMPLETE_RECOMPUTATION_AND_BYTE_REPLAY",
        },
        "MATHEMATICAL_BASE": {
            "HEAD": BASE_HEAD,
            "TREE": BASE_TREE,
            "PATH": BASE_RESULT,
            "SHA256": BASE_SHA,
            "R30_PATH": R30_PATH,
            "R30_SHA256": R30_SHA,
        },
        "SOURCE_SHA256": sha(code_bytes(SOURCE)),
        "TEST_SHA256": sha(code_bytes(TEST)),
        "DIRECT_CODE_PINS": CODE_PINS,
        "EVALUATOR_SOURCE_PINS": source_pins,
        "PROOF": __doc__,
        "PROFILE_ID": PROFILE,
        "FACTS": facts,
        "K_Z_CERTIFICATE": relaxation,
        "OLD_CAP": old_cap,
        "NEW_CAP": new_cap,
        "BASE_AUTHORITY": auth,
        "UNIVERSALITY": "ALL_LEGAL_REALIZATIONS_OF_THE_EXACT_PROFILE",
        "RELAXATION_STATES_ASSERTED_REALIZABLE": False,
        "REMAINDER_NONNEGATIVITY": "FOUR_CARDINALITIES; SEPARATE_LOWER_BOUNDS_SUMMED",
        "OLD_BOUND": old_bound,
        "NEW_BOUND": new_bound,
        "ROW_DELTA": old_bound - new_bound,
        "FULL_ENVELOPE_TERM_COUNTS": {
            "OLD": len(old_terms),
            "NEW": len(new_terms),
            "OLD_T_RANGE": [22, old_cap],
            "NEW_T_RANGE": [22, new_cap],
        },
        "TERM_COLUMNS": ["T", "BOUND", "K4_FLOOR", "CONTAINED_K4", "S4_FLOOR", "S3"],
        "OLD_ALL_T_TERMS": old_terms,
        "NEW_ALL_T_TERMS": new_terms,
        "OLD_ALL_ARGMAX": [t for t in old_terms if t[1] == old_bound],
        "NEW_ALL_ARGMAX": [t for t in new_terms if t[1] == new_bound],
        "NEW_BOUND_WITH_S4_FLOOR_ZERO": zero_floor,
        "S4_BASE_LOAD_BEARING": zero_floor != new_bound,
        "FRACTIONAL_S4_CREDIT_TERMS": sum((4 * t[4]) % 7 != 0 for t in new_terms),
        "S4_S5_AUTHORITY": {
            "S4_FUNCTION": "b649_k20_min_s2_current_cursor_class_owner_chase_r28.profile_s4_floor",
            "S4_RULE": "MAX(BASE,679*K4-231*MIN(K4,A_MAX)); NEVER ADD",
            "K4_WEIGHTS_REEXECUTED": weights,
            "S5_ALL_T_ADOPTION": base["ALL_T_BONFERRONI_5_ADOPTION"],
            "S5_ADOPTED_CERTIFICATES": base["CERTIFICATES_ADOPTED"],
            "S5_INHERITED_TARGET": base["INHERITED_TARGET_BONFERRONI_5"],
            "S5_USED": False,
        },
        "EXACT_ARITHMETIC_AND_ROUNDING": "K4_CEILING; A_MAX_FLOOR; S4_MAX; FRACTION_CEILING",
        "FAMILY_BEFORE": before,
        "FAMILY_AFTER": after,
        "FAMILY_DELTA": before["MAXIMUM"] - after["MAXIMUM"],
        "ALL_NEW_MAX_OWNERS": after["ALL_MAX_OWNERS"],
        "NEXT_DISTINCT_BOUND": after["NEXT_DISTINCT_BOUND"],
        "INCUMBENT": fixed["INCUMBENT"],
        "GAP_TO_INCUMBENT": after["MAXIMUM"] - fixed["INCUMBENT"],
        "LEDGER_PARTITION": partition,
        "RESOLVED_ROWS_BEFORE": resolved,
        "RESOLVED_ROWS_AFTER": after_resolved,
        "RESOLVED_ROWS_CHANGED": sorted(p for p in resolved if resolved[p] != after_resolved[p]),
        "OTHER_RESOLVED_ROWS_UNCHANGED": RESOLVED_COUNT - 1,
        "RESOLVED_4647_PRESERVED": set(after_resolved) == set(resolved),
        "CURSOR_197_PRESERVED": {"COUNT": len(cursor), "UNCHANGED": True, "ROW_BOUNDS": cursor},
        "INHERITED_EXCLUSION": fixed["INHERITED_EXCLUSION"],
        "INHERITED_CAVEATS_REFERENCE": fixed["INHERITED_CAVEATS_REFERENCE"],
        "INHERITED_CAVEATS_AND_STATUS_VERBATIM": base["INHERITED_CAVEATS_AND_STATUS_VERBATIM"],
        "HISTORICAL_CERTIFICATES_RECERTIFIED": False,
        "PROJECTION_STATUS": "CONDITIONAL_PROJECTION; NOT_CANONICAL_ADOPTION",
        "GLOBAL_OPTIMUM": "UNKNOWN",
        "PREDICTION_GAIN_CLAIMED": False,
        "FRESH_JUDGE": "ONE_FRESH_FOCUSED_REVIEW_ON_FROZEN_TREE; VERDICT_EXTERNAL_TO_JSON",
        "SOLVER_CALLS": 0,
        "FULL_SUPPORT_GRAPHS_ENUMERATED": 0,
        "PORTFOLIOS_ENUMERATED": 0,
        "SAMPLED_REALIZATIONS_USED_FOR_BOUNDS": 0,
        "CANONICAL_AUTHORITY_CHANGED": "NO",
        "REMOTE_WRITE": "NONE",
        "PRODUCTION_MUTATION": "NONE",
        "REMAINING_TASK_MODEL": "最強模型: 新數學證明; 強模型: 已驗收結果接合",
    }


def validate_payload(payload: object, expected: object) -> None:
    require(render(payload) == render(expected), "result differs from complete recomputation")


def verify_result(candidate: str = "HEAD", repo: Path = ROOT) -> None:
    expected = compute_result(candidate, repo)
    data = (
        (ROOT / RESULT).read_bytes()
        if git("rev-parse", candidate, repo=repo) == INPUT_HEAD
        else blob(candidate, RESULT, repo)
    )
    decode(data)
    require(data == render(expected), "stored result differs from complete recomputation")


def main() -> None:
    parser = argparse.ArgumentParser(description=TASK_ID)
    parser.add_argument("--write-result", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = compute_result()
    if args.write_result:
        require(not (ROOT / RESULT).exists(), "result already exists")
        (ROOT / RESULT).write_bytes(render(result))
    if args.verify:
        verify_result()
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "TASK_STATUS",
                    "OLD_CAP",
                    "NEW_CAP",
                    "FAMILY_BEFORE",
                    "FAMILY_AFTER",
                    "FAMILY_DELTA",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
