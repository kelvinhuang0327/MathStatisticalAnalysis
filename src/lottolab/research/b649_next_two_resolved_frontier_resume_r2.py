"""Universal triangle caps for exactly the two tied B649 resolved owners.

MODEL. Twenty six-label tickets use 22 triple labels (three tickets each)
and 27 pair labels (two tickets each): 20*6=66+54. Two tickets share at most
one label (pair-linearity). d_v counts the triple labels of ticket v and
p_v=6-d_v its pair labels. In the support graph G (tickets adjacent iff they
share a label) every edge carries exactly one label, so G is simple,
g_v=2d_v+p_v=6+d_v, sum g=186, e(G)=93, and the 22 triple labels are 22
edge-disjoint triangles: 22<=T(G)<=floor(W/3), W=sum C(g_v,2). Goodman:
every 3-set is a triangle of G, of H=complement(G), or contributes exactly
two to sum g(19-g), so T(G)+T(H)=B0=C(20,3)-sum g(19-g)/2.
  A=66655555555331100000: 6^3 5^8 3^2 1^2 0^5, W=827, B0=293, K/Z=15/5.
  B=66655555555411110000: 6^3 5^8 4^1 1^4 0^4, W=827, B0=293, K/Z=16/4.
Every fact is rederived from the profile string.

TWO-SHORE IDENTITY (any graph, any partition V=X+Y). x=|X|, y=|Y|, M=H[X],
N=H[Y]; s_v counts G-neighbours of v on the other shore; c=sum_X s=sum_Y s
is the number of crossing G-edges. deg_M(v)=x-1-g_v+s_v on X and
deg_N(v)=y-1-g_v+s_v on Y. For uv in E(M) exactly y-s_u-s_v+c_Y(uv)
vertices of Y are H-adjacent to both (inclusion-exclusion, c_Y(uv) counting
common G-neighbours in Y); symmetrically for E(N). Classifying H-triangles by
their shores, with 2e(M)=sum_X(x-1-g)+c, 2e(N)=sum_Y(y-1-g)+c and x+y=20:
  T(G)=B0-Q-10c+sum_X s(x-1-g+s)+sum_Y s(y-1-g+s)-P,                 (*)
  2Q=y sum_X(x-1-g)+x sum_Y(y-1-g),
  P=T(M)+T(N)+sum_E(M) c_Y+sum_E(N) c_X.
(*) is an equality. The four parts of P are cardinalities (triangle and
common-neighbour counts), so P>=0, and replacing P by any LOWER bound of P
can only raise the right-hand side.

REMAINDER LOWER BOUNDS (load-bearing for A only). (i) A simple graph F with
degrees a, e edges and any vertex set S, |S|=s, has e(F[S])>=I(a,s)=
max(0,e-sum of the |F|-s largest degrees): every edge not inside S has an
endpoint outside S. (ii) Double counting: sum_E(N) c_X=sum_{w in X}
e(N[N_G(w) cap Y])>=sum_X I(deg_N,s_w); symmetrically sum_E(M) c_Y>=
sum_Y I(deg_M,s_w). (iii) For an edge ij of F, |N(i) cap N(j)|>=a_i+a_j-|F|;
summing over E(F) gives 3T(F)>=sum a^2-|F|e. For the h largest degrees L at
most sum_{outside} min(h,a) edges leave L, so e(F[L])>=l=max(0,ceil((sum_L a-
sum_out min(h,a))/2)). Each edge inside L has at least max(0,a_i+a_j-|F|)
common neighbours, so their common-neighbour sum C is at least the l
smallest such pair weights; C=3T_3+T_2 (triangles with 3 or exactly 2
vertices in L), so T(F)>=C-2C(h,3). Take the maximum with 0 over all h.
(i)-(iii) bound four DIFFERENT summands of P, so their sum bounds P below.

PROFILE A: K/Z SPLIT. X=K={d>0}, k=15; Y=Z={d=0}, z=5. Variables:
sigma_v=|N_G(v) cap Z| on K, zeta_u=|N_G(u) cap K| on Z, r=sum sigma=c.
Ranges: a Z ticket lies in no triple label, so each K-Z edge is a pair label
of its K end: 0<=sigma_v<=min(z,6-d_v), i.e. d6:0, d5:0..1, d3:0..3,
d1:0..5 (z=5; the z=4 bound of B is not used). A Z ticket has g=6 and at most
z-1=4 Z-neighbours: 2=7-z<=zeta_u<=min(k,6)=6. Joint necessary conditions:
(a) sum sigma=sum zeta; (b) deg_M=8-d+sigma is graphical (Erdos-Gallai);
(c) the G[Z] degrees 6-zeta are graphical; (d) (sigma,zeta) is bigraphic
(Gale-Ryser, both directions): the K-Z edges form a simple bipartite graph.
Q=60 and deg_N=zeta-2, so (*) reads
  T=233-10r+sum_K sigma(8-d+sigma)+sum_Z zeta(zeta-2)-P.
Every condition, score and remainder bound depends only on the sigma multiset
inside each equal-d class and on the zeta multiset, so sorted multisets cover
every labelled state. Coverage: 1*9*10*21=1890 sigma signatures and 126 zeta
multisets in range; 6533 pairs have equal sums and 1661 pass (b)-(d). The
maximum over ALL 1661 retained states with P replaced by (i)+(ii)+(iii) is
253, uniquely at sigma=5 on both d=1 tickets, 0 elsewhere, zeta=2^5.
Ablations: no remainder 265; triangle remainders only 263; (ii) on E(N) only
259. Every legal A realization maps to a retained state, so T<=253.

PROFILE B: HI/LO SPLIT. X=HI={d>=4}: x=12 (6^3 5^8 4); Y=LO={d<=3}: y=8
(1^4 0^4); Q=16, B0-Q=277. Variables: each crossing edge carries one label;
b_v counts crossing edges at v carried by a triple label of v, q_v those
carried by a pair label of v, s_v=b_v+q_v; beta=sum_HI b=sum_LO b and
pi=sum_HI q=sum_LO q (each crossing edge has one end on each shore), c=
beta+pi. Ranges for v with own shore U and other shore O: 0<=q_v<=6-d_v;
0<=b_v<=2d_v (a triple label gives two edges at v); b_v<=|{w in O: d_w>0}|
(triple-label mates have d>0 and distinct edges reach distinct mates);
b_v+q_v<=|O|; complement degree |U|-1-g_v+s_v>=0. For B: HI d6 q=0, 1<=b<=4
(only four LO tickets have d>0; complement degree s-1>=0); HI d5 b<=4, q<=1;
HI d4 b<=4, q<=2; LO d1 b<=2, q<=5; LO d0 b=0, q<=6; hence beta<=8, pi<=10.
Drop P>=0 (no remainder is used). The objective
  277-10(beta+pi)+sum_HI s(s+5-d)+sum_LO s(s+1-d)
is separable per ticket given (beta,pi). Exact per-class maxima over every
multiset of per-ticket choices, indexed by (beta,pi), are convolved per
shore; the cells feasible on both shores cover every integer state. 66 cells
exist and the maximum is 260, at exactly (7,5) and (7,10). Every legal B
realization satisfies all listed conditions, so T<=260.

ADOPTION. The adopted split is fixed per profile (A K/Z, B HI/LO). The
other split is computed as a valid but weaker diagnostic (A HI/LO 285,
B K/Z 267), and the adopted cap must equal the minimum of both. No relaxation
state is asserted realizable: simultaneous realization, the triple
decomposition and further support constraints are omitted, which only
enlarges each relaxation. Legal realizations appear only as test fixtures.

FIXED BASE ROUTE B. Old caps come from the accepted R30 refutation, the NB
cap and the R18 class cap of the pinned Base (OLD_CAP=265 for both), never
from row bounds. At each t, o=W-3t; q>=ceil((J-(g_max-2)o)/4) with
J=sum C(g,3) (K4 CEILING), contained-triple K4 a<=A_max=floor(sum d(g-2)/3)
=197 (FLOOR) and a<=q, so S4>=679q-231min(q,A_max), combined with the Base
floor 112 by MAX, never ADD. No Base S4-by-t or adopted S5 certificate exists
for A or B; S5 is unused. S3=2800o+20272(t-22)+154000 and at most seven
tickets win on seven labels, so 1_{r>0}<=r-C(r,2)+C(r,3)-(4/7)C(r,4) gives
ceil(S1-S2+S3-4S4/7) with the exact Fraction rounded UP. Every integer t in
22..cap is evaluated with the pinned evaluator and checked by an independent
exact formula; all terms and all argmax are stored.

FAMILY. Replay the direct certificate, aggregate all 4647 resolved and 197
cursor rows, replace exactly A and B, and aggregate again. Cursor IDs and
bounds (including the W785/W784 improvements) and the 282 inherited
exclusions are preserved verbatim and not recertified. CONDITIONAL_PROJECTION
only: no canonical adoption, global optimum or prediction gain is claimed.
The fresh Judge verdict stays external to this self-hashed JSON.
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
direct: Any = import_module("lottolab.research.b649_w784_39_cursor_shared_bound_r1")
upstream: Any = direct.upstream
route: Any = direct.route
type Record = dict[str, Any]
type Term = tuple[int, int, int, int, int, int]
type Choice = tuple[int, int]

TASK_ID = "B649_NEXT_TWO_RESOLVED_FRONTIER_RESUME_R2"
ORIGINAL_TASK_ID = "B649_NEXT_TWO_RESOLVED_FRONTIER_BOUND_R1"
INPUT_HEAD = "93c263d187e4b0445ae465a5235c3a630f91396a"
INPUT_TREE = "94a5c7c9987d517a095c16a3730a3d911fda8463"
BASE_HEAD = "8d08e843b30300e8379f63e7dc9db401581e2e5e"
BASE_TREE = "231494ec0995981d2324cc5ef697ba4b1975b2f0"
INPUT_RESULT: str = direct.RESULT
INPUT_SHA = "5d0692d6153a38c4a4f1ff021041102d83cbd00ad4f4701ccdb672e1eb7f4b15"
BASE_RESULT: str = direct.BASE_RESULT
BASE_SHA: str = direct.BASE_SHA
R30_PATH: str = upstream.r2.R30_PATH
R30_SHA: str = upstream.r2.R30_SHA
PROFILE_A, PROFILE_B = "66655555555331100000", "66655555555411110000"
PROFILE_IDS = (PROFILE_A, PROFILE_B)
ADOPTED_SPLIT = {PROFILE_A: "K/Z", PROFILE_B: "HI/LO"}
EXPECTED_FAMILY_BEFORE = 313391740
EXPECTED_NEXT_BOUND = 313391636
STOPPING_CAP = 264
RESOLVED_COUNT, CURSOR_COUNT, EXCLUDED_COUNT, RAW_COUNT = 4647, 197, 282, 5126
HI_MIN_D = 4
S1_MINUS_S2 = 372228640 - 63838600
KZ_REJECTIONS = ("non-graphical M=H[K]", "non-graphical G[Z]", "bipartite crossing inequalities")
SOURCE = "src/lottolab/research/b649_next_two_resolved_frontier_resume_r2.py"
TEST = "tests/unit/test_b649_next_two_resolved_frontier_resume_r2.py"
RESULT = "docs/research/matrix-native-results/b649-next-two-resolved-frontier-resume-r2-result.json"
ROOT = Path(__file__).resolve().parents[3]
CODE_PINS = {
    direct.SOURCE: "77cf69b96178cbf82936146163f15f7e9d20fad495058e0cfb7b7f54f5586edd",
    direct.TEST: "ed39876a61c19efbb5c477e4be69f2e755f69848c20f627ee55e5b3ac3b62457",
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


def hilo_shores(pid: str) -> tuple[list[int], list[int]]:
    d = profile_facts(pid)["D"]
    return [v for v in d if v >= HI_MIN_D], [v for v in d if v < HI_MIN_D]


def hilo_premises(pid: str) -> Record:
    f = profile_facts(pid)
    hi, lo = hilo_shores(pid)
    q = split_constant([6 + v for v in hi], [6 + v for v in lo])
    ranges: Record = {}
    for shore, own, other in (("HI", hi, lo), ("LO", lo, hi)):
        ranges[shore] = {
            str(v): {
                "COUNT": n,
                "B_MAX": min(2 * v, sum(x > 0 for x in other)),
                "Q_MAX": min(6 - v, len(other)),
                "S_MAX": len(other),
                "OFFSET": len(own) - 1 - (6 + v),
            }
            for v, n in sorted(Counter(own).items(), reverse=True)
        }
    return {
        "PARTITION": f"X=HI={{d>={HI_MIN_D}}}; Y=LO={{d<{HI_MIN_D}}}",
        "HI_MIN_D": HI_MIN_D,
        "HI_D": hi,
        "LO_D": lo,
        "HI_SIZE": len(hi),
        "LO_SIZE": len(lo),
        "VARIABLES": {
            "B": "b_v=crossing G-edges at v carried by a triple label of v",
            "Q": "q_v=crossing G-edges at v carried by a pair label of v",
            "BETA": "beta=sum_HI b=sum_LO b",
            "PI": "pi=sum_HI q=sum_LO q",
        },
        "RANGES_BY_SHORE_AND_D": ranges,
        "JOINT_CONDITIONS": [
            "0<=q_v<=6-d_v",
            "0<=b_v<=min(2d_v, other-shore tickets with d>0)",
            "b_v+q_v<=|other shore|",
            "own-shore complement degree |own|-1-g_v+b_v+q_v>=0",
            "equal beta and equal pi on both shores",
        ],
        "Q": q,
        "UPPER_CONSTANT": f["GOODMAN"] - q,
        "REMAINDER_USED": "NONE; P>=0 DROPPED",
    }


def validate_hilo_premises(pid: str, claimed: Mapping[str, Any]) -> None:
    expected = hilo_premises(pid)
    require(
        (claimed.get("HI_D"), claimed.get("LO_D")) == (expected["HI_D"], expected["LO_D"]),
        "wrong Hi/Lo partition",
    )
    require(
        claimed.get("RANGES_BY_SHORE_AND_D") == expected["RANGES_BY_SHORE_AND_D"],
        "wrong Hi/Lo range",
    )
    require(render(dict(claimed)) == render(expected), "wrong Hi/Lo premises")


def hilo_choices(pid: str, shore: str, v: int) -> tuple[Choice, ...]:
    """All (block, pair) crossing-edge counts allowed for a d=v ticket."""
    hi, lo = hilo_shores(pid)
    own, other = (hi, lo) if shore == "HI" else (lo, hi)
    require(shore in ("HI", "LO") and v in own, "Hi/Lo shore membership")
    blockable = sum(x > 0 for x in other)
    result = tuple(
        (b, q)
        for b in range(min(2 * v, blockable) + 1)
        for q in range(min(6 - v, len(other)) + 1)
        if b + q <= len(other) and len(own) - 1 - (6 + v) + b + q >= 0
    )
    require(bool(result), "empty Hi/Lo choice set")
    return result


def validate_hilo_choice(pid: str, shore: str, v: int, b: int, q: int) -> None:
    hi, lo = hilo_shores(pid)
    own, other = (hi, lo) if shore == "HI" else (lo, hi)
    require(shore in ("HI", "LO") and v in own, "Hi/Lo shore membership")
    require(0 <= q <= 6 - v, "Hi/Lo pair-label range")
    require(0 <= b <= min(2 * v, sum(x > 0 for x in other)), "Hi/Lo block-label range")
    require(b + q <= len(other), "Hi/Lo other-shore size")
    require(len(own) - 1 - (6 + v) + b + q >= 0, "Hi/Lo complement degree")


def hilo_class_tables(pid: str, shore: str) -> list[Record]:
    hi, lo = hilo_shores(pid)
    own = hi if shore == "HI" else lo
    tables: list[Record] = []
    for v, count in sorted(Counter(own).items(), reverse=True):
        a = len(own) - 1 - (6 + v)
        choices = hilo_choices(pid, shore, v)
        best: dict[tuple[int, int], int] = {}
        witnesses: dict[tuple[int, int], list[tuple[Choice, ...]]] = {}
        for multiset in combinations_with_replacement(choices, count):
            key = (sum(b for b, _ in multiset), sum(q for _, q in multiset))
            score = sum((b + q) * (a + b + q) for b, q in multiset)
            if score > best.get(key, -(10**9)):
                best[key], witnesses[key] = score, [multiset]
            elif score == best[key]:
                witnesses[key].append(multiset)
        tables.append(
            {
                "D": v,
                "COUNT": count,
                "OFFSET": a,
                "CHOICES": choices,
                "BEST": best,
                "ARG": witnesses,
            }
        )
    return tables


def convolve(tables: Sequence[Record]) -> dict[tuple[int, int], int]:
    total = {(0, 0): 0}
    for table in tables:
        merged: dict[tuple[int, int], int] = {}
        for (b0, q0), s0 in total.items():
            for (b1, q1), s1 in table["BEST"].items():
                key = (b0 + b1, q0 + q1)
                merged[key] = max(merged.get(key, -(10**9)), s0 + s1)
        total = merged
    return total


def side_argmax(
    tables: Sequence[Record], cell: tuple[int, int], target: int
) -> list[list[list[Any]]]:
    found: list[list[list[Any]]] = []

    def visit(i: int, b: int, q: int, score: int, chosen: list[list[Any]]) -> None:
        if i == len(tables):
            if (b, q) == cell and score == target:
                found.append(chosen)
            return
        t = tables[i]
        for (b1, q1), s1 in t["BEST"].items():
            if b + b1 <= cell[0] and q + q1 <= cell[1]:
                for multiset in t["ARG"][(b1, q1)]:
                    visit(
                        i + 1,
                        b + b1,
                        q + q1,
                        score + s1,
                        [*chosen, [t["D"], [list(c) for c in multiset]]],
                    )

    visit(0, 0, 0, 0, [])
    return found


@cache
def hilo_relaxation(pid: str) -> Record:
    prem = hilo_premises(pid)
    constant = prem["UPPER_CONSTANT"]
    hi_tables, lo_tables = hilo_class_tables(pid, "HI"), hilo_class_tables(pid, "LO")
    hi_best, lo_best = convolve(hi_tables), convolve(lo_tables)
    cells = sorted(set(hi_best) & set(lo_best))
    require(bool(cells), "empty Hi/Lo relaxation")
    values = {c: constant - 10 * (c[0] + c[1]) + hi_best[c] + lo_best[c] for c in cells}
    cap = max(values.values())
    argmax: list[Record] = [
        {
            "BETA": c[0],
            "PI": c[1],
            "HI_SCORE": hi_best[c],
            "LO_SCORE": lo_best[c],
            "HI_STATES": side_argmax(hi_tables, c, hi_best[c]),
            "LO_STATES": side_argmax(lo_tables, c, lo_best[c]),
        }
        for c in cells
        if values[c] == cap
    ]
    return {
        "PARTITION": prem["PARTITION"],
        "PREMISES": prem,
        "CLASS_CHOICES": {
            side: [
                {"D": t["D"], "COUNT": t["COUNT"], "OFFSET": t["OFFSET"], "CHOICES": t["CHOICES"]}
                for t in tables
            ]
            for side, tables in (("HI", hi_tables), ("LO", lo_tables))
        },
        "CLASS_MULTISETS": {
            side: {
                str(t["D"]): comb(len(t["CHOICES"]) + t["COUNT"] - 1, t["COUNT"]) for t in tables
            }
            for side, tables in (("HI", hi_tables), ("LO", lo_tables))
        },
        "SHORE_CELL_COUNTS": {"HI": len(hi_best), "LO": len(lo_best)},
        "CELL_COUNT": len(cells),
        "ALL_CELLS": [[c[0], c[1], hi_best[c], lo_best[c], values[c]] for c in cells],
        "CAP": cap,
        "ALL_ARGMAX": argmax,
        "ARGMAX_STATE_COUNT": sum(len(a["HI_STATES"]) * len(a["LO_STATES"]) for a in argmax),
        "REALIZABILITY": "NOT_ASSERTED; NECESSARY_CONDITION_RELAXATION",
    }


def validate_hilo_coverage(pid: str, claimed: Mapping[str, Any]) -> None:
    expected = hilo_relaxation(pid)
    for key in ("SHORE_CELL_COUNTS", "CELL_COUNT", "ALL_CELLS", "CLASS_CHOICES"):
        require(
            render(claimed.get(key)) == render(expected[key]),
            "wrong Hi/Lo relaxation coverage: " + key,
        )
    require(render(claimed.get("ALL_ARGMAX")) == render(expected["ALL_ARGMAX"]), "Hi/Lo argmax")
    require(render(dict(claimed)) == render(expected), "wrong Hi/Lo certificate")


def certified_cap(pid: str) -> Record:
    kz, hilo = kz_relaxation(pid)["CAP"], hilo_relaxation(pid)["CAP"]
    adopted = ADOPTED_SPLIT[pid]
    cap = kz if adopted == "K/Z" else hilo
    require(cap == min(kz, hilo), "adopted split is not the strongest certificate")
    return {
        "ADOPTED_SPLIT": adopted,
        "CAP": cap,
        "K_Z_CAP": kz,
        "HI_LO_CAP": hilo,
        "DIAGNOSTIC_SPLIT": "HI/LO" if adopted == "K/Z" else "K/Z",
        "DIAGNOSTIC_CAP": hilo if adopted == "K/Z" else kz,
        "STOPPING_CAP": STOPPING_CAP,
        "MEETS_STOPPING_CAP": cap <= STOPPING_CAP,
    }


def validate_cap(pid: str, cap: object) -> None:
    require(type(cap) is int and cap == certified_cap(pid)["CAP"], "wrong triangle cap")


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


def replace_owners(
    resolved: Mapping[str, int], new: Mapping[str, int], owners: Sequence[str]
) -> dict[str, int]:
    require(
        len(resolved) == RESOLVED_COUNT and set(new) == set(owners) == set(PROFILE_IDS),
        "both maximum owners required",
    )
    require(
        all(type(b) is int and b < resolved[p] for p, b in new.items()), "strict owner tightening"
    )
    return {p: new.get(p, b) for p, b in resolved.items()}


def family_status(
    before: Mapping[str, Any], after: Mapping[str, Any], new: Mapping[str, int]
) -> str:
    strict = set(new) == set(PROFILE_IDS) and all(
        type(b) is int and b < before["MAXIMUM"] for b in new.values()
    )
    return (
        "PROVEN_FAMILY_GAIN"
        if strict and after["MAXIMUM"] < before["MAXIMUM"]
        else "NO_PROVEN_FAMILY_GAIN"
    )


def ledger_partition(
    resolved: Mapping[str, int], cursor: Mapping[str, int], fixed: Mapping[str, Any]
) -> Record:
    raw = {"".join(map(str, p)): upstream.wedges(p) for p in upstream.raw_histograms()}
    require(len(raw) == RAW_COUNT, "raw histogram census")
    require(cursor == fixed["CURSOR_ROW_BOUNDS_AFTER"], "cursor ledger")
    require(set(cursor) == {p for p, w in raw.items() if w <= 785}, "cursor ledger")
    w784 = fixed["PER_CURSOR"]
    require(all(cursor[p] == w784[p]["NEW_BOUND"] for p in fixed["OWNER_IDS"]), "cursor ledger")
    before = fixed["CURSOR_ROW_BOUNDS_BEFORE"]
    require(
        set(before) == set(cursor) and all(cursor[p] <= before[p] for p in cursor),
        "cursor non-regression",
    )
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
        "CURSOR_W784_IMPROVED_ROWS": len(fixed["OWNER_IDS"]),
        "CURSOR_ROWS_TIGHTER_THAN_INPUT_BEFORE": sum(cursor[p] < before[p] for p in cursor),
        "OWNER_W": {p: raw[p] for p in PROFILE_IDS},
    }


def profile_certificate(pid: str) -> Record:
    """The adopted certificate in full; the diagnostic split compactly."""
    kz, hilo = kz_relaxation(pid), hilo_relaxation(pid)
    if ADOPTED_SPLIT[pid] == "K/Z":
        return {"ADOPTED_K_Z_CERTIFICATE": kz, "DIAGNOSTIC_HI_LO_CERTIFICATE": hilo}
    compact = {k: v for k, v in kz.items() if k != "RETAINED_STATE_ROWS"}
    return {"ADOPTED_HI_LO_CERTIFICATE": hilo, "DIAGNOSTIC_K_Z_CERTIFICATE": compact}


def compute_result(candidate: str = "HEAD", repo: Path = ROOT) -> Record:
    mode = verify_identity(candidate, repo)
    fixed, base, r30 = replay_input(repo)
    source_pins = upstream.r2.source_pins()
    require(source_pins == fixed["EVALUATOR_SOURCE_PINS"], "Base evaluator closure pins")
    resolved = checked_rows(list(fixed["RESOLVED_ROWS"].items()), fixed["RESOLVED_ROWS"])
    cursor = checked_rows(
        list(fixed["CURSOR_ROW_BOUNDS_AFTER"].items()), fixed["CURSOR_ROW_BOUNDS_AFTER"]
    )
    before = family_summary(resolved, cursor)
    require(
        before == fixed["FAMILY_AFTER"]
        and before["MAXIMUM"] == EXPECTED_FAMILY_BEFORE
        and before["ALL_MAX_OWNERS"] == sorted(PROFILE_IDS)
        and before["NEXT_DISTINCT_BOUND"] == EXPECTED_NEXT_BOUND
        and fixed["ALL_NEW_MAX_OWNERS"] == sorted(PROFILE_IDS),
        "fixed complete family/owner frontier",
    )
    partition = ledger_partition(resolved, cursor, fixed)
    require((route.K20_S1, route.K20_S2) == (372228640, 63838600), "Base S1/S2")
    weights = route.r30.k4_quartet_weights()
    require(
        weights == route.K4_WEIGHTS == {route.WITH_TRIPLE: 448, route.WITHOUT_TRIPLE: 679},
        "Base K4 local weights",
    )
    profiles: Record = {}
    new_bounds: dict[str, int] = {}
    for pid in PROFILE_IDS:
        facts = profile_facts(pid)
        auth = base_authority(pid, r30)
        validate_s4_s5(pid, base, auth)
        floor = auth["S4_BASE"]
        old_cap = auth["OLD_CAP"]
        old_terms = envelope(pid, old_cap, floor)
        old_bound = max(t[1] for t in old_terms)
        require(
            old_bound
            == resolved[pid]
            == base["RESOLVED_ROW_BOUNDS"][pid]
            == EXPECTED_FAMILY_BEFORE,
            "old full Base envelope replay",
        )
        caps = certified_cap(pid)
        validate_cap(pid, caps["CAP"])
        require(caps["MEETS_STOPPING_CAP"] and caps["CAP"] < old_cap, "no proven cap improvement")
        new_cap = caps["CAP"]
        new_terms = envelope(pid, new_cap, floor)
        new_bound = max(t[1] for t in new_terms)
        zero_floor = max(t[1] for t in envelope(pid, new_cap, 0))
        new_bounds[pid] = new_bound
        profiles[pid] = {
            "FACTS": facts,
            **profile_certificate(pid),
            "CAP_DECISION": caps,
            "BASE_AUTHORITY": auth,
            "OLD_CAP": old_cap,
            "NEW_CAP": new_cap,
            "OLD_BOUND": old_bound,
            "NEW_BOUND": new_bound,
            "ROW_DELTA": old_bound - new_bound,
            "OLD_TERM_COUNT": len(old_terms),
            "NEW_TERM_COUNT": len(new_terms),
            "OLD_ALL_T_TERMS": old_terms,
            "NEW_ALL_T_TERMS": new_terms,
            "OLD_ALL_ARGMAX": [t for t in old_terms if t[1] == old_bound],
            "NEW_ALL_ARGMAX": [t for t in new_terms if t[1] == new_bound],
            "NEW_BOUND_WITH_S4_FLOOR_ZERO": zero_floor,
            "S4_BASE_LOAD_BEARING": zero_floor != new_bound,
            "FRACTIONAL_S4_CREDIT_TERMS": sum((4 * t[4]) % 7 != 0 for t in new_terms),
        }
    after_resolved = replace_owners(resolved, new_bounds, PROFILE_IDS)
    require(
        {p: b for p, b in after_resolved.items() if p not in PROFILE_IDS}
        == {p: b for p, b in resolved.items() if p not in PROFILE_IDS},
        "other 4645 resolved bounds",
    )
    after = family_summary(after_resolved, cursor)
    status = family_status(before, after, new_bounds)

    def code_bytes(path: str) -> bytes:
        return (
            (ROOT / path).read_bytes()
            if mode.startswith("INPUT_HEAD")
            else blob(candidate, path, repo)
        )

    return {
        "TASK_ID": TASK_ID,
        "ORIGINAL_TASK_ID": ORIGINAL_TASK_ID,
        "ORIGINAL_R1_REUSE": "READ_ONLY_METHOD_REUSE; R1 DRAFT NOT IMPORTED OR PINNED",
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
        "PROFILE_ORDER": list(PROFILE_IDS),
        "PROFILES": profiles,
        "SHARED_THEOREM": {
            "IDENTITY": "T(G)=B0-Q-10c+sum_X s(x-1-g+s)+sum_Y s(y-1-g+s)-P, P>=0",
            "ADOPTED_SPLITS": ADOPTED_SPLIT,
            "PER_PROFILE_CAPS": {p: profiles[p]["CAP_DECISION"] for p in PROFILE_IDS},
            "UNIVERSALITY": "ALL_LEGAL_REALIZATIONS_OF_EACH_EXACT_PROFILE",
            "RELAXATION_STATES_ASSERTED_REALIZABLE": False,
            "SAMPLED_REALIZATIONS_USED_FOR_BOUNDS": 0,
            "FULL_SUPPORT_GRAPHS_ENUMERATED": 0,
            "PORTFOLIOS_ENUMERATED": 0,
        },
        "TERM_COLUMNS": ["T", "BOUND", "K4_FLOOR", "CONTAINED_K4", "S4_FLOOR", "S3"],
        "FULL_ENVELOPE_TERM_COUNTS": {
            "OLD_PER_PROFILE": {p: profiles[p]["OLD_TERM_COUNT"] for p in PROFILE_IDS},
            "NEW_PER_PROFILE": {p: profiles[p]["NEW_TERM_COUNT"] for p in PROFILE_IDS},
            "OLD_T_RANGES": {p: [22, profiles[p]["OLD_CAP"]] for p in PROFILE_IDS},
            "NEW_T_RANGES": {p: [22, profiles[p]["NEW_CAP"]] for p in PROFILE_IDS},
            "OLD_TOTAL": sum(profiles[p]["OLD_TERM_COUNT"] for p in PROFILE_IDS),
            "NEW_TOTAL": sum(profiles[p]["NEW_TERM_COUNT"] for p in PROFILE_IDS),
        },
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
        "OTHER_RESOLVED_ROWS_UNCHANGED": RESOLVED_COUNT - len(PROFILE_IDS),
        "RESOLVED_4647_PRESERVED": set(after_resolved) == set(resolved),
        "CURSOR_197_PRESERVED": {"COUNT": len(cursor), "UNCHANGED": True, "ROW_BOUNDS": cursor},
        "INHERITED_EXCLUSION": fixed["INHERITED_EXCLUSION"],
        "INHERITED_CAVEATS_REFERENCE": fixed["INHERITED_CAVEATS_REFERENCE"],
        "HISTORICAL_CERTIFICATES_RECERTIFIED": False,
        "WORKER_ATTEMPT_HISTORY": [
            {
                "OBSERVED": "original R1 stopped while writing its certificate; no tests/result",
                "DISPOSITION": "R1 draft read only; method rederived and recomputed here",
            },
            {
                "OBSERVED": "K/Z relaxation with all four remainders gives B only T<=267",
                "DISPOSITION": "B adopts the HI/LO two-shore certificate T<=260",
            },
            {
                "OBSERVED": "scratch hill-climb built legal realizations (A T=243, B T=234)",
                "DISPOSITION": "legality-checked test fixtures only; no bound depends on them",
            },
        ],
        "PROJECTION_STATUS": "CONDITIONAL_PROJECTION; NOT_CANONICAL_ADOPTION",
        "GLOBAL_OPTIMUM": "UNKNOWN",
        "PREDICTION_GAIN_CLAIMED": False,
        "FRESH_JUDGE": "ONE_FRESH_FOCUSED_REVIEW_ON_FROZEN_TREE; VERDICT_EXTERNAL_TO_JSON",
        "SOLVER_CALLS": 0,
        "FULL_SUPPORT_GRAPHS_ENUMERATED": 0,
        "PORTFOLIOS_ENUMERATED": 0,
        "CANONICAL_AUTHORITY_CHANGED": "NO",
        "REMOTE_WRITE": "NONE",
        "PRODUCTION_MUTATION": "NONE",
        "REMAINING_TASK_MODEL": "最強模型(尚缺的數學證明); 強模型(已驗收成果的工程接合)",
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
    decode(data)  # Reject duplicate keys before comparing the exact byte representation.
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
            {k: result[k] for k in ("TASK_STATUS", "FAMILY_BEFORE", "FAMILY_AFTER", "FAMILY_DELTA")}
        )
    )


if __name__ == "__main__":
    main()
