"""Universal range-only K/Z triangle cap for exactly 65555555555432100000.

MODEL. Twenty six-label tickets use 22 labels of multiplicity three and 27
of multiplicity two: 20*6=22*3+27*2. Pair-linearity means two tickets share
at most one label. The simple support graph G joins tickets sharing a label.
If d_v is its triple-label incidence, its pair incidence is 6-d_v and its
support degree is g_v=2*d_v+(6-d_v)=6+d_v. The exact profile independently
gives 6^1,5^10,4^1,3^1,2^1,1^1,0^5, sum d=66, sum d^2=316,
sum g=186, e(G)=93, W=sum C(g,2)=821 and J=sum C(g,3)=2265. The 22
triple labels give edge-disjoint triangles, so T>=22. For H=complement(G),
each nonmonochromatic vertex triple contributes two mixed wedges. Hence
 T(G)+T(H)=C(20,3)-sum_v g_v*(19-g_v)/2=287.
K={d>0}, Z={d=0} have sizes 15,5. None of these constants is imported
from the previous W830/Goodman296 profile.

EXACT SPLIT IDENTITY. For any partition X,Y, x=|X|, y=|Y|, M=H[X], N=H[Y],
let s_v count G-neighbours on the other shore and r=sum_X s=sum_Y s.
The within-shore complement degrees are a_v=x-1-g_v+s_v on X and
b_v=y-1-g_v+s_v on Y. For uv in E(M), inclusion-exclusion counts exactly
 y-s_u-s_v+c_Y(uv)
common H-neighbours on Y, with c_Y(uv) the common G-neighbours on Y.
The symmetric formula holds for E(N). Summing and using
2e(M)=sum_X(x-1-g_v)+r, 2e(N)=sum_Y(y-1-g_v)+r, x+y=20 gives
 T(G)=287-Q-10*r+sum_X s_v*a_v+sum_Y s_v*b_v-P,
 2Q=y*sum_X(x-1-g_v)+x*sum_Y(y-1-g_v),
 P=T(M)+T(N)+sum_{uv in E(M)}c_Y(uv)+sum_{uv in E(N)}c_X(uv).
Each of the four remainders is a cardinality and individually nonnegative.
They count the four types of H-triangles in the preceding expansion;
there is no subtraction of overlapping lower bounds. For X=K,Y=Z, the
derived Q is 60, a=8-d+sigma, b=zeta-2, and therefore
 T(G)=227-10*r+sum_K sigma*(8-d+sigma)+sum_Z zeta*(zeta-2)-P.       (*)

RANGES, CROSSING CONSISTENCY AND GRAPHICALITY. Define sigma_v=s_v on K,
zeta_u=s_u on Z. Z tickets have no triple labels, so every K-Z edge uses
one pair label at its K endpoint: 0<=sigma_v<=min(5,6-d_v). The class
ranges are d6:{0}, d5:0..1, d4:0..2, d3:0..3, d2:0..4, d1:0..5.
Every Z ticket has degree 6 and at most 4 neighbours on Z, so 2<=zeta<=6.
Each crossing edge is counted once on both shores: sum sigma=sum zeta=r.
In every legal realization a is graphical on K, 6-zeta is graphical on Z,
b is its complement degree list, and (sigma,zeta) is a simple bipartite
graph. Degree range, even sum and top-h edge-count inequalities follow
by counting internal and crossing edges. These graphicality conditions,
simultaneous compatibility, triple packing and all further support
constraints are deliberately OMITTED from the adopted relaxation. Omitting
necessary conditions only enlarges the domain; no legal realization is
removed. Graphicality diagnostics of argmax states are not exclusion gates.

CLOSED ANALYTIC BOUND. On 2<=u<=6,
 u*(u-2)<=6*u-12,
with exact slack (u-2)*(6-u)>=0. Substituting this secant into (*) and using
crossing-sum equality gives
 T(G)<=167+sum_K sigma*(sigma+4-d)-P.
Each quadratic is convex on its stated interval, so its maximum occurs
at an endpoint. For d=6,5,4,3,2,1 the per-vertex maxima are respectively
0,0,4,12,24,40. There are ten d5 vertices and one of every other positive
class, so T(G)<=167+0+10*0+4+12+24+40=247. More precisely,
 247-T(G)=P+sum_Z (zeta-2)*(6-zeta)
            +sum_K [class_max(d)-sigma*(sigma+4-d)],
an exact identity of nonnegative terms. This proves universality without
sampling, a solver result or realizability of any relaxation state.

FINITE COVERAGE AND ALL ARGMAX. Sorted sigma multisets independently inside
each equal-d class and a sorted zeta multiset cover every labelled legal
realization: the ranges, crossing sums, score and slack identity are
invariant under those permutations. The complete product has
1*11*3*4*5*6=3960 sigma signatures and C(9,5)=126 zeta multisets. Exactly
13911 pairs have equal crossing sums; every such pair is retained. The
finite raw maximum is also 247. Equality in the secant requires zeta in
{2,6}; equality in class bounds requires sigma=2,3,4,5 on d4,d3,d2,d1,
zero on d6, and arbitrary zero/one on d5. If n is the number of d5 ones
and j the number of zeta sixes, crossing equality is 14+n=10+4*j. Thus
(n,j)=(0,1),(4,2),(8,3), exactly three sorted argmax states. All retained
states and all argmax are stored. Their G[Z] degree lists are non-graphical;
this does not affect the upper bound over a superset. Cap 247 already
exposes the requested next family level; no deeper cap is pursued.

FIXED BASE ROUTE B AND ROUNDING. Accepted R30 refutations, the NB cap and
class cap are checked in the pinned Mathematical Base; their minimum is
old cap 267. For each t, o=821-3*t>=0. In N_G(v), an open wedge spoils at
most g_v-2 neighbour triples, so 4*q>=J-(g_max-2)*o and the K4 LOWER bound
is L=max(0,ceil((2265-10*o)/4)). Pair-linearity forbids two contained triple
supports in a K4. The common outside neighbours of a triple support S
are <=min_{v in S}(g_v-2), hence <=their average. Summing gives the
contained-triple K4 upper bound A_max=floor(sum d_v*(g_v-2)/3)=floor(580/3)
=193. The fixed Base's re-executed local K4 weights are 448 with and 679
without a contained triple. Non-K4 quartet contributions are nonnegative.
For true q,a, S4>=679*q-231*a>=f(q), f(q)=679*q-231*min(q,193). Its
increments are 448 then 679, so S4>=f(L). Combine this with the pinned
Base S4 floor 112 by MAX, never ADD. There is no S4-by-t or adopted S5
certificate for this exact profile in the fixed Base; S5 remains unused.
The fixed exact local triple intersections give
 S3=2800*o+20272*(t-22)+154000.
On a seven-label outcome each winning ticket supplies a distinct three-hit
subset; pair-linearity makes their pairs disjoint. Thus 3*r<=C(7,2), r<=7.
For every integer 0<=r<=7,
 1_{r>0}<=r-C(r,2)+C(r,3)-(4/7)*C(r,4).
Summing gives the exact Fraction CEILING of S1-S2+S3-4*S4/7, with the
negative S4 coefficient and S1=372228640,S2=63838600. Every t in old
22..267 and new 22..247 is evaluated by the pinned Base Route B and
independently checked; all terms and all argmax are stored.

FULL FAMILY AND CAVEATS. Completely replay the pinned direct result and
source/evaluator closure. Aggregate all 4647 resolved and 197 cursor rows,
update only this exact profile, then aggregate again. Family delta comes
only from that complete aggregation, not from row delta. All cursor IDs,
bounds and 282 inherited exclusions/caveats are preserved, without
recertifying historical exclusions. CONDITIONAL_PROJECTION only; canonical
authority, global optimum and actual prediction gains are not established.
No solver, support-graph or portfolio enumeration is used. Tests of the
identity are diagnostics, not the universal proof. The fresh Judge verdict
is external to this self-hashed result and frozen candidate tree.
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
from itertools import combinations_with_replacement, product
from math import comb
from pathlib import Path
from typing import Any, cast

# The frozen upstream modules are dynamically typed; isolate them at this boundary.
direct: Any = import_module("lottolab.research.b649_next_unique_max_owner_w830_bound_r1")
upstream: Any = direct.upstream
route: Any = direct.route
type Record = dict[str, Any]
type Term = tuple[int, int, int, int, int, int]

TASK_ID = "B649_NEXT_UNIQUE_MAX_OWNER_W821_BOUND_R1"
INPUT_HEAD = "ac3501aa204eb7cc241909e58d0c24b9da81972e"
INPUT_TREE = "d0548f8c3005b82c7a7647bf3801e8ccf4ec1b08"
BASE_HEAD = "8d08e843b30300e8379f63e7dc9db401581e2e5e"
BASE_TREE = "231494ec0995981d2324cc5ef697ba4b1975b2f0"
INPUT_RESULT: str = direct.RESULT
INPUT_SHA = "c27eb1d3ae49e872ef3587577cf383e44f4baa90a0f5357644550355e62c4bc7"
BASE_RESULT: str = direct.BASE_RESULT
BASE_SHA: str = direct.BASE_SHA
R30_PATH: str = direct.R30_PATH
R30_SHA: str = direct.R30_SHA
PROFILE = "65555555555432100000"
PROFILE_IDS = (PROFILE,)
EXPECTED_FAMILY_BEFORE = 313391560
EXPECTED_NEXT_BOUND = 313391172
RESOLVED_COUNT, CURSOR_COUNT, EXCLUDED_COUNT, RAW_COUNT = 4647, 197, 282, 5126
S1_MINUS_S2 = 372228640 - 63838600
SOURCE = "src/lottolab/research/b649_next_unique_max_owner_w821_bound_r1.py"
TEST = "tests/unit/test_b649_next_unique_max_owner_w821_bound_r1.py"
RESULT = "docs/research/matrix-native-results/b649-next-unique-max-owner-w821-bound-r1-result.json"
ROOT = Path(__file__).resolve().parents[3]
CODE_PINS = {
    direct.SOURCE: "8ca162db349df59685f2f9161e6e95c88c83846bc72d2b784de5eb191e0d03a0",
    direct.TEST: "0abe27adce3a64fb6ef6b82d8cbe3ee0376d0564ae03bdc659155fa57bc49782",
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


def split_constant(g_x: Sequence[int], g_y: Sequence[int]) -> int:
    x, y = len(g_x), len(g_y)
    require(x + y == 20 and x > 0 and y > 0, "two-shore partition")
    twice = y * sum(x - 1 - v for v in g_x) + x * sum(y - 1 - v for v in g_y)
    require(twice % 2 == 0, "two-shore constant parity")
    return twice // 2


def kz_premises(pid: str) -> Record:
    f = profile_facts(pid)
    d, k, z = f["D"], f["K"], f["Z"]
    q = split_constant([6 + x for x in d if x > 0], [6] * z)
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
        "RETAINED_JOINT_CONDITION": "sum sigma == sum zeta",
        "OMITTED_NECESSARY_CONDITIONS": [
            "deg_M=k-7-d+sigma graphical on K",
            "G[Z] degrees 6-zeta graphical on Z; N is its complement",
            "(sigma,zeta) a simple bipartite graph",
            "simultaneous realization and triple-label decomposition",
        ],
        "OMISSION_DIRECTION": "SUPERSET_OF_ALL_LEGAL_REALIZATIONS",
        "M_DEGREE": f"{k - 7}-d+sigma",
        "N_DEGREE": f"zeta{z - 7:+d}",
        "M_EDGE_SUM": f"{k * (k - 7) - 66}+r",
        "N_EDGE_SUM": f"r{z * (z - 7):+d}",
        "Q": q,
        "UPPER_CONSTANT": f["GOODMAN"] - q,
        "CROSSING_COEFFICIENT": f["VERTICES"] // 2,
    }


def validate_kz_premises(pid: str, claimed: Mapping[str, Any]) -> None:
    expected = kz_premises(pid)
    require(
        (claimed.get("K"), claimed.get("Z")) == (expected["K"], expected["Z"]), "wrong K/Z split"
    )
    require(claimed.get("SIGMA_RANGE_BY_D") == expected["SIGMA_RANGE_BY_D"], "wrong sigma range")
    require(claimed.get("ZETA_RANGE") == expected["ZETA_RANGE"], "wrong zeta range")
    require(render(dict(claimed)) == render(expected), "wrong K/Z premises")


@cache
def analytic_certificate(pid: str) -> Record:
    """Derive the secant and convex class bounds, without enumerating any graph."""
    f, prem = profile_facts(pid), kz_premises(pid)
    lo, hi = prem["ZETA_RANGE"]
    slope = lo + hi + prem["Z"] - 7
    constant = prem["UPPER_CONSTANT"] - prem["Z"] * lo * hi
    classes: list[Record] = []
    for d, count in sorted(Counter(x for x in f["D"] if x > 0).items(), reverse=True):
        low, high = prem["SIGMA_RANGE_BY_D"][str(d)]
        linear = prem["K"] - 7 - d + slope - prem["CROSSING_COEFFICIENT"]
        value = max(low * (low + linear), high * (high + linear))
        values = {s: s * (s + linear) for s in range(low, high + 1)}
        require(all(v <= value for v in values.values()), "convex class bound")
        classes.append(
            {
                "D": d,
                "COUNT": count,
                "LOW": low,
                "HIGH": high,
                "QUADRATIC_LINEAR_COEFFICIENT": linear,
                "MAXIMUM_PER_VERTEX": value,
                "ALL_ARGMAX": [s for s, v in values.items() if v == value],
            }
        )
    return {
        "ZETA_SECANT_SLOPE": slope,
        "ZETA_SECANT_INTERCEPT": -lo * hi,
        "ZETA_SLACK": "(zeta-low)*(high-zeta)",
        "REDUCED_CONSTANT": constant,
        "CLASS_BOUNDS": classes,
        "CAP": constant + sum(c["COUNT"] * c["MAXIMUM_PER_VERTEX"] for c in classes),
        "LOSS_IDENTITY": "CAP-T=P+ZETA_SECANT_SLACK+SIGMA_CLASS_SLACK",
        "REMAINDER_FLOORS": {"T_M": 0, "T_N": 0, "C_Y_ON_E_M": 0, "C_X_ON_E_N": 0},
        "GRAPHICALITY_SCREENS_APPLIED": False,
    }


def validate_analytic_certificate(pid: str, claimed: Mapping[str, Any]) -> None:
    require(render(claimed) == render(analytic_certificate(pid)), "wrong analytic certificate")


def kz_state(
    pid: str, sigma_by_d: Sequence[tuple[int, Sequence[int]]], zeta: Sequence[int]
) -> Record:
    """One sorted range state. Graphicality is deliberately not a rejection gate."""
    f, prem, analytic = profile_facts(pid), kz_premises(pid), analytic_certificate(pid)
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
        require(list(values) == sorted(values), "sigma canonical order")
    zlow, zhigh = prem["ZETA_RANGE"]
    require(
        len(zeta) == z and all(type(s) is int and zlow <= s <= zhigh for s in zeta), "zeta range"
    )
    require(list(zeta) == sorted(zeta), "zeta canonical order")
    pairs = [(v, s) for v, values in sigma_by_d for s in values]
    sigma = [s for _, s in pairs]
    r = sum(sigma)
    require(r == sum(zeta), "crossing sums")
    m = tuple(k - 7 - v + s for v, s in pairs)
    n = tuple(z - 7 + s for s in zeta)
    raw = (
        prem["UPPER_CONSTANT"]
        - prem["CROSSING_COEFFICIENT"] * r
        + sum(s * a for s, a in zip(sigma, m, strict=True))
        + sum(s * a for s, a in zip(zeta, n, strict=True))
    )
    zeta_slack = sum((s - zlow) * (zhigh - s) for s in zeta)
    per_class = {c["D"]: c for c in analytic["CLASS_BOUNDS"]}
    sigma_slack = sum(
        per_class[v]["MAXIMUM_PER_VERTEX"] - s * (s + per_class[v]["QUADRATIC_LINEAR_COEFFICIENT"])
        for v, s in pairs
    )
    require(zeta_slack >= 0 and sigma_slack >= 0, "nonnegative analytic slacks")
    require(analytic["CAP"] - raw == zeta_slack + sigma_slack, "analytic loss identity")
    return {
        "R": r,
        "SIGMA_BY_D": [[v, list(values)] for v, values in sigma_by_d],
        "ZETA": list(zeta),
        "M_DEGREES": list(m),
        "N_DEGREES": list(n),
        "WITHOUT_REMAINDER": raw,
        "UPPER": raw,
        "ZETA_SECANT_SLACK": zeta_slack,
        "SIGMA_CLASS_SLACK": sigma_slack,
    }


def kz_state_row(state: Mapping[str, Any]) -> str:
    sigma = ",".join(f"{v}:" + "".join(map(str, s)) for v, s in state["SIGMA_BY_D"])
    return (
        f"r={state['R']};sigma={sigma};zeta={''.join(map(str, state['ZETA']))};"
        f"zeta_slack={state['ZETA_SECANT_SLACK']};sigma_slack={state['SIGMA_CLASS_SLACK']};"
        f"upper={state['UPPER']}"
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
    states: list[Record] = []
    signatures = 0
    for parts in product(*choices):
        signatures += 1
        sigma_by_d = [(v, part) for (v, _), part in zip(groups, parts, strict=True)]
        r = sum(s for _, part in sigma_by_d for s in part)
        for zeta in zetas:
            if sum(zeta) == r:
                states.append(kz_state(pid, sigma_by_d, zeta))
    require(bool(states), "empty K/Z relaxation")
    cap = max(s["UPPER"] for s in states)
    analytic = analytic_certificate(pid)
    require(cap == analytic["CAP"], "analytic and full range maxima differ")
    rows = [kz_state_row(s) for s in states]
    maxima = [s for s in states if s["UPPER"] == cap]
    diagnostics: list[Record] = []
    for s in maxima:
        sigma = [v for _, part in s["SIGMA_BY_D"] for v in part]
        diagnostics.append(
            {
                "R": s["R"],
                "M_GRAPHICAL": graphical(s["M_DEGREES"]),
                "G_Z_GRAPHICAL": graphical([6 - v for v in s["ZETA"]]),
                "CROSSING_BIGRAPHICAL": bipartite_necessary(sigma, s["ZETA"]),
            }
        )
    return {
        "PARTITION": prem["PARTITION"],
        "PREMISES": prem,
        "ANALYTIC_CERTIFICATE": analytic,
        "CAP": cap,
        "SIGMA_SIGNATURES": signatures,
        "ZETA_MULTISETS_IN_RANGE": len(zetas),
        "RANGE_STATES_WITH_EQUAL_CROSSING_SUMS": len(states),
        "RETAINED_STATE_COUNT": len(states),
        "REJECTED_GRAPHICALITY_STATES": 0,
        "RETAINED_STATES_SHA256": sha(render(rows)),
        "PER_R_MAXIMUM": {
            str(r): max(s["UPPER"] for s in states if s["R"] == r)
            for r in sorted({s["R"] for s in states})
        },
        "ALL_ARGMAX": maxima,
        "ARGMAX_GRAPHICALITY_DIAGNOSTICS_ONLY": diagnostics,
        "REALIZABILITY": "NOT_ASSERTED; RANGE_ONLY_SUPERSET; GRAPHICALITY_NOT_SCREENED",
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
    require(auth["S4_BY_T"] == {}, "S4 authority")
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
        "REMAINDER_NONNEGATIVITY": "FOUR_CARDINALITIES; EACH_AT_LEAST_ZERO",
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
        "REMAINING_TASK_MODEL": "最強模型: 新數學證明; 強模型: 已驗收結果整合",
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
