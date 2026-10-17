"""Universal Z=3 triangle certificate for exactly 65555555555511111000.

MODEL AND SCOPE. Twenty six-label tickets use 22 labels of multiplicity
three and 27 of multiplicity two. Pair-linearity means any two tickets
share at most one label. In their simple support graph G, d_v triple labels
and 6-d_v pair labels give g_v=6+d_v distinct neighbours. The exact word
gives d histogram 6^1,5^11,1^5,0^3, sum d=66, sum d^2=316, sum g=186,
93 edges, W=sum C(g,2)=821 and J=sum C(g,3)=2270. The 22 triple labels
give edge-disjoint triangles, hence T>=22. For H=complement(G), each
nonmonochromatic vertex triple has two mixed wedges, proving
 T(G)+T(H)=C(20,3)-sum_v g_v*(19-g_v)/2=287.
This certificate concerns all legal realizations of this exact profile.
It does not assert that any maximizing relaxation state is realizable.

EXACT SPLIT DERIVATION. Write K={d>0}, |K|=17, Z={d=0}, |Z|=3,
M=H[K], N=H[Z], sigma_v=|N_G(v) intersect Z| for v in K,
zeta_u=|N_G(u) intersect K| for u in Z. Every crossing G-edge is counted
once on each shore, so r=sum sigma=sum zeta. The complement degrees are
a_v=16-g_v+sigma_v=10-d_v+sigma_v, b_u=2-6+zeta_u=zeta_u-4.
Thus 2e(M)=104+r and 2e(N)=r-12. For uv in E(M), exactly
3-sigma_u-sigma_v+c_Z(uv) vertices of Z are common H-neighbours,
where c_Z counts common G-neighbours on Z. The symmetric expression on
E(N) is 17-zeta_u-zeta_v+c_K(uv). These count the two mixed triangle
types of H. Summing gives, with Q=(3*104+17*(-12))/2=54,
 T(G)=233-10*r+sum sigma*a+sum zeta*b-P = E-P,
 P=T(M)+T(N)+C_Y+C_X,
 C_Y=sum_{uv in E(M)} c_Z(uv), C_X=sum_{uv in E(N)} c_K(uv).
All four summands of P are cardinalities and individually nonnegative.

RANGES AND COVERAGE. A crossing edge incident to a zero vertex uses a
pair label at its K endpoint, since a zero ticket contains no triple
label. There are 6-d such labels and only three zero vertices, proving
0<=sigma<=min(3,6-d). On Z, support degree 6 and at most two internal
neighbours prove 4<=zeta<=6. These ranges are derived anew for Z=3.
Let m count sigma=1 among the eleven d5 vertices, and n_j count sigma=j
among the five d1 vertices. Then 0<=m<=11, sum_j n_j=5, and the d6 vertex
has sigma=0. There are 12*C(8,3)=672 signatures. Sorting within equal-d
classes loses no state: the variables, bounds and objective are invariant.
Enumerating the eight graphs on Z, then sorting by zeta=6-deg_G[Z], gives
four patterns: 444,455,556,666, with multiplicities 1,3,3,1. Each has a
unique complement edge set after this relabeling. Crossing equality
m+n1+2*n2+3*n3=sum zeta leaves 181 signature/pattern states. ALL 181 are
retained. Direct expansion of E gives
 E=233-4*m+2*n2+6*n3+sum_Z zeta*(zeta-4).
Necessary conditions include graphicality of a on K, of 6-zeta on Z,
and simple bipartite graphicality of (sigma,zeta), plus compatibility
with triple-label packing. The Z graph is exact; M graphicality and
global compatibility are omitted. Omitting necessary constraints enlarges
the domain. Every legal realization therefore maps into a retained state.

C_X FLOOR. Let S be the n3 vertices of sigma 3; they meet all of Z.
For the n2 vertices of sigma 2 let x01,x02,x12 count their zero pairs.
These are nonnegative integers with sum n2 and loads
(x01+x02,x01+x12,x02+x12)<=zeta-n3 componentwise. The remaining loads
are filled by the m+n1 singleton vertices: their sum is exactly m+n1
by crossing equality. Each feasible pair-count vector can be filled this
way, and every legal crossing graph supplies such a vector. For each
edge ij of N its G-codegree in K is n3+xij. Minimize their sum over all
these vectors to obtain L_X. Hence C_X-L_X>=0 by counting, independently
of M. T(N) is computed exactly from the three zero vertices.

C_Y FLOOR. Each vertex of S has g_K=7-3=4 neighbours in G[K]. Put U=K-S,
e=e_G(S), and let c_u=|N_G(u) intersect S| for u in U. Counting degrees
in S gives sum_U c_u=4*n3-2*e. Since a_u is the complement degree on K,
 max(0,n3-a_u)<=c_u<=min(n3,6+d_u-sigma_u).
For any integer e in 0..C(n3,2), retain every integral c in these boxes
with that sum. This is a relaxation: no internal graphicality or per-S
degree matching is imposed. Its maximum weighted cut is
 W_e=max sum_U sigma_u*c_u.
Start at all lower bounds and fill remaining units in descending sigma
order up to the upper bounds. An exchange from a smaller weight to an
available larger weight never decreases the score, proving this greedy
maximum exactly; an empty box/sum has no legal realization for that e.
Every complement S-S edge contributes 3 to C_Y; every complement S-U
edge contributes sigma_u. These disjoint edge sets yield
 C_Y >= 3*(C(n3,2)-e)+n3*sum_U sigma_u-sum_U sigma_u*c_u.
Discarded U-U contributions are nonnegative. Therefore
 L_Y=max(0,min_e [3*(C(n3,2)-e)+n3*sum_U sigma_u-W_e]) <= C_Y.
This minimum includes every e possible in a legal realization. All 181
states have nonempty residual and cut domains; none is silently removed.

FINITE UNIVERSAL CERTIFICATE. For every retained state set
U_state=E-L_X-T(N)-L_Y. Its full finite maximum is 264. The four pattern
maxima are respectively 257,264,264,254. There are exactly two sorted
argmax states: (m,n0,n1,n2,n3,zeta)=(0,0,0,1,4,455) and
(1,0,0,0,5,556), with (E,L_X,T(N),L_Y)=(269,5,0,0) and (281,10,0,7).
For every legal realization the exact loss identity is
 264-T=(264-U_state)+(C_X-L_X)+(C_Y-L_Y)+T(M).
Each term is nonnegative by the finite maximum or the preceding counting
arguments. Thus T<=264 universally. No solver status, timeout, sample,
or unverified scratch number supplies this bound. The interrupted draft
was a read-only reference; this source recomputes the certificate.

FIXED BASE ROUTE B. Re-execute the pinned Base's accepted R30/NB/class
minimum (old cap 267), S4 floor and all local evaluator weights. An open
wedge in N_G(v) spoils at most g_v-2 neighbour triples, so, writing
o=821-3*t, 4*q>=J-10*o and q>=L=max(0,ceil((J-10*o)/4)). Pair-linearity
forbids two contained triple supports in one K4. A triple support's
common outside neighbours number at most min(g_v-2), hence at most their
average. Summing over the 22 triple supports gives
A_max=floor(sum d_v*(g_v-2)/3)=floor(580/3)=193. The Base K4 local weights
are 448 with and 679 without a contained triple. Other quartet terms are
nonnegative. Thus S4>=679*q-231*min(q,193), an increasing function of q,
so S4>=max(inherited_floor,679*L-231*min(L,193)); never ADD the floors.
There is no adopted exact-profile S5 certificate in this Base: S5 is unused.
The fixed triple intersections give S3=2800*o+20272*(t-22)+154000.
For a seven-label outcome, winning tickets supply distinct three-subsets
with disjoint pairs by pair-linearity, so 3*r<=C(7,2) and r<=7. For every
integer r in 0..7, 1_{r>0}<=r-C(r,2)+C(r,3)-(4/7)*C(r,4).
Summing gives a valid upper bound via the exact Fraction CEILING of
372228640-63838600+S3-4*S4/7. Every t in 22..267 and 22..264 is evaluated
by Base Route B and checked independently, including all argmax values.

FULL FAMILY. Replay the fixed direct result and evaluator source closure.
Reaggregate all 4647 resolved and 197 cursor rows before and after changing
only this exact profile. Preserve all cursor IDs/bounds and 282 inherited
exclusions and caveats, without recertifying historical exclusions. Stop
at this first proved cap exposing the next frontier: no deeper search.
CONDITIONAL_PROJECTION only, not global optimum, canonical adoption, or
improved actual prediction hit rate. No solver, portfolio or full support
graph enumeration is used. The one fresh Judge verdict stays outside this
self-hashed result and its frozen tree.
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
from itertools import combinations_with_replacement
from math import comb
from pathlib import Path
from typing import Any, cast

direct: Any = import_module("lottolab.research.b649_next_unique_max_owner_w821_bound_r1")
upstream: Any = direct.upstream
route: Any = direct.route
type Record = dict[str, Any]
type Term = tuple[int, int, int, int, int, int]

TASK_ID = "B649_NEXT_UNIQUE_MAX_OWNER_W821_Z3_RESUME_R2"
INPUT_HEAD = "1f8c3334bd27ca5fb37a5dd7958437d15d901e73"
INPUT_TREE = "dc3cc48f934c627ff4ec041f1b21cbb48458ba52"
BASE_HEAD = "8d08e843b30300e8379f63e7dc9db401581e2e5e"
BASE_TREE = "231494ec0995981d2324cc5ef697ba4b1975b2f0"
INPUT_RESULT: str = direct.RESULT
INPUT_SHA = "75446b3de43b36265a57c669fd48eae897706ef420af4a8074b87143b3c6d6c6"
BASE_RESULT: str = direct.BASE_RESULT
BASE_SHA: str = direct.BASE_SHA
R30_PATH: str = direct.R30_PATH
R30_SHA: str = direct.R30_SHA
PROFILE = "65555555555511111000"
PROFILE_IDS = (PROFILE,)
EXPECTED_FAMILY_BEFORE = 313391172
EXPECTED_NEXT_BOUND = 313390396
EXPECTED_NEXT_OWNER = "55555555555443000000"
RESOLVED_COUNT, CURSOR_COUNT, EXCLUDED_COUNT, RAW_COUNT = 4647, 197, 282, 5126
S1_MINUS_S2 = 372228640 - 63838600
SOURCE = "src/lottolab/research/b649_next_unique_max_owner_w821_z3_resume_r2.py"
TEST = "tests/unit/test_b649_next_unique_max_owner_w821_z3_resume_r2.py"
RESULT = (
    "docs/research/matrix-native-results/b649-next-unique-max-owner-w821-z3-resume-r2-result.json"
)
ROOT = Path(__file__).resolve().parents[3]
CODE_PINS = {
    direct.SOURCE: "05d82f93347398ed8a20a6007112cb47b73f86fe5da4564bfb5965a596787a1e",
    direct.TEST: "b2d73b4e6a0f5c4a18f24caae4d426c5ee25882366920a5f6e986cca0f76a33e",
}
Z_PAIRS = ((0, 1), (0, 2), (1, 2))


def require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def render(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def unique_object(pairs: list[tuple[str, Any]]) -> Record:
    require(len(pairs) == len({key for key, _ in pairs}), "duplicate JSON/ledger row")
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
    direct.verify_result(INPUT_HEAD, repo)
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
    degrees = tuple(map(int, pid))
    require(
        len(degrees) == 20 and tuple(sorted(degrees, reverse=True)) == degrees,
        "histogram order/size",
    )
    require(
        all(0 <= value <= 6 for value in degrees) and sum(degrees) == 66, "triple degree histogram"
    )
    support = tuple(6 + value for value in degrees)
    numerator = sum(value * (19 - value) for value in support)
    require(
        sum(support) == 186 and sum(support) // 2 == 93 and numerator % 2 == 0,
        "degree/Goodman model",
    )
    positive = sum(value > 0 for value in degrees)
    zeros = degrees.count(0)
    require((positive, zeros) == (17, 3), "wrong K/Z")
    return {
        "PROFILE_ID": pid,
        "D": list(degrees),
        "G": list(support),
        "D_HISTOGRAM": {
            str(value): count for value, count in sorted(Counter(degrees).items(), reverse=True)
        },
        "VERTICES": len(degrees),
        "DEGREE_SUM_D": sum(degrees),
        "SUM_D_SQUARED": sum(value * value for value in degrees),
        "DEGREE_SUM_G": sum(support),
        "EDGES": sum(support) // 2,
        "WEDGES": sum(comb(value, 2) for value in support),
        "GOODMAN": comb(20, 3) - numerator // 2,
        "K": positive,
        "Z": zeros,
        "J": sum(comb(value, 3) for value in support),
        "G_MAX": max(support),
        "A_MAX_NUMERATOR": sum(value * (value + 4) for value in degrees),
        "A_MAX": sum(value * (value + 4) for value in degrees) // 3,
        "PAIR_DEGREES": [6 - value for value in degrees],
        "WEDGE_TRIANGLE_CAP": sum(comb(value, 2) for value in support) // 3,
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
    ordered = sorted(degrees, reverse=True)
    size = len(ordered)
    return (
        all(type(value) is int and 0 <= value < size for value in ordered)
        and sum(ordered) % 2 == 0
        and all(
            sum(ordered[:k]) <= k * (k - 1) + sum(min(k, value) for value in ordered[k:])
            for k in range(1, size + 1)
        )
    )


def bipartite_necessary(left: Sequence[int], right: Sequence[int]) -> bool:
    first, second = sorted(left, reverse=True), sorted(right, reverse=True)
    return (
        sum(first) == sum(second)
        and all(
            sum(first[:h]) <= sum(min(h, value) for value in second)
            for h in range(1, len(first) + 1)
        )
        and all(
            sum(second[:h]) <= sum(min(h, value) for value in first)
            for h in range(1, len(second) + 1)
        )
    )


def split_constant(support_x: Sequence[int], support_y: Sequence[int]) -> int:
    width, height = len(support_x), len(support_y)
    require(width + height == 20 and width > 0 and height > 0, "two-shore partition")
    twice = height * sum(width - 1 - value for value in support_x) + width * sum(
        height - 1 - value for value in support_y
    )
    require(twice % 2 == 0, "two-shore constant parity")
    return twice // 2


def kz_premises(pid: str) -> Record:
    facts = profile_facts(pid)
    degrees, positive, zeros = facts["D"], facts["K"], facts["Z"]
    quotient = split_constant([6 + value for value in degrees if value > 0], [6] * zeros)
    sigma_range = {
        str(value): [0, min(zeros, 6 - value)]
        for value in sorted({item for item in degrees if item > 0}, reverse=True)
    }
    # Z=5 used min(5, 6-d) and zeta starting at 2. Those intervals are not derived here.
    require(sigma_range == {"6": [0, 0], "5": [0, 1], "1": [0, 3]}, "wrong sigma range")
    require(min(zeros, 6 - 1) == 3 and max(0, 7 - zeros) == 4, "wrong Z=3 range derivation")
    return {
        "PARTITION": "X=K={d>0}; Y=Z={d=0}",
        "K": positive,
        "Z": zeros,
        "VARIABLES": {
            "SIGMA": "sigma_v=|N_G(v) cap Z| for v in K",
            "ZETA": "zeta_u=|N_G(u) cap K| for u in Z",
            "R": "r=sum_K sigma=sum_Z zeta=crossing G-edges",
        },
        "SIGMA_RANGE_BY_D": sigma_range,
        "ZETA_RANGE": [max(0, 7 - zeros), min(positive, 6)],
        "REJECTED_Z5_SIGMA_UPPER": "min(5,6-d)",
        "REJECTED_Z5_ZETA_LOWER": 2,
        "RETAINED_JOINT_CONDITION": (
            "sum sigma == sum zeta AND zeta arises from one of 8 graphs on Z"
        ),
        "OMITTED_NECESSARY_CONDITIONS": [
            "deg_M graphical on K",
            "full Gale-Ryser beyond the sigma=3 residual placement",
            "simultaneous realization and triple-label decomposition",
        ],
        "OMISSION_DIRECTION": "SUPERSET_OF_ALL_LEGAL_REALIZATIONS",
        "M_DEGREE": f"{positive - 7}-d+sigma",
        "N_DEGREE": f"zeta{zeros - 7:+d}",
        "Q": quotient,
        "UPPER_CONSTANT": facts["GOODMAN"] - quotient,
        "CROSSING_COEFFICIENT": facts["VERTICES"] // 2,
    }


def validate_kz_premises(pid: str, claimed: Mapping[str, Any]) -> None:
    expected = kz_premises(pid)
    require(
        (claimed.get("K"), claimed.get("Z")) == (expected["K"], expected["Z"]), "wrong K/Z split"
    )
    require(claimed.get("SIGMA_RANGE_BY_D") == expected["SIGMA_RANGE_BY_D"], "wrong sigma range")
    require(claimed.get("ZETA_RANGE") == expected["ZETA_RANGE"], "wrong zeta range")
    require(claimed.get("ZETA_RANGE") != [2, 6], "wrong zeta range")
    require(render(dict(claimed)) == render(expected), "wrong K/Z premises")


@cache
def z_patterns() -> tuple[Record, ...]:
    """All 8 simple graphs on Z, grouped by the unique sorted complement edge set."""

    grouped: dict[tuple[int, ...], set[frozenset[tuple[int, int]]]] = {}
    masks: dict[tuple[int, ...], list[int]] = {}
    for mask in range(8):
        degree = [0, 0, 0]
        edges: list[tuple[int, int]] = []
        for bit, pair in enumerate(Z_PAIRS):
            if mask >> bit & 1:
                degree[pair[0]] += 1
                degree[pair[1]] += 1
                edges.append(pair)
        order = sorted(range(3), key=lambda vertex: (6 - degree[vertex], vertex))
        rank = {old: new for new, old in enumerate(order)}
        zeta = tuple(6 - degree[old] for old in order)
        present = {tuple(sorted((rank[left], rank[right]))) for left, right in edges}
        missing = frozenset(set(Z_PAIRS) - present)
        grouped.setdefault(zeta, set()).add(missing)
        masks.setdefault(zeta, []).append(mask)
    rows: list[Record] = []
    for zeta in sorted(grouped):
        require(len(grouped[zeta]) == 1, "G[Z] complement edges are not unique")
        hedges = tuple(sorted(next(iter(grouped[zeta]))))
        rows.append(
            {
                "ZETA": list(zeta),
                "H_EDGES": [list(edge) for edge in hedges],
                "T_N": 1 if len(hedges) == 3 else 0,
                "MASKS": masks[zeta],
                "GRAPH_COUNT": len(masks[zeta]),
            }
        )
    require(sum(row["GRAPH_COUNT"] for row in rows) == 8, "Z graph catalogue")
    require(
        [row["ZETA"] for row in rows] == [[4, 4, 4], [4, 5, 5], [5, 5, 6], [6, 6, 6]],
        "Z graph catalogue",
    )
    return tuple(rows)


def pattern_for(zeta: Sequence[int]) -> Record | None:
    for row in z_patterns():
        if row["ZETA"] == list(zeta):
            return row
    return None


def shore_vertices(n3: int, m1: int, n2: int, n1: int, n0: int) -> list[tuple[int, int, int]]:
    """(sigma, complement degree a, support degree inside K) on U=K\\S."""

    rows = [(0, 4, 12)]
    rows += [(1, 6, 10)] * m1
    rows += [(0, 5, 11)] * (11 - m1)
    rows += [(2, 11, 5)] * n2
    rows += [(1, 10, 6)] * n1
    rows += [(0, 9, 7)] * n0
    require(len(rows) == 17 - n3, "U shore size")
    return rows


def max_cut_weight(
    sigmas: Sequence[int], lows: Sequence[int], highs: Sequence[int], total: int
) -> int | None:
    """Maximum sigma-weighted cut with each endpoint inside its degree box."""

    require(len(sigmas) == len(lows) == len(highs), "cut box dimensions")
    if any(low > high for low, high in zip(lows, highs, strict=True)):
        return None
    if not sum(lows) <= total <= sum(highs):
        return None
    extra = total - sum(lows)
    weight = sum(low * sigma for low, sigma in zip(lows, sigmas, strict=True))
    for index in sorted(range(len(sigmas)), key=lambda i: sigmas[i], reverse=True):
        take = min(extra, highs[index] - lows[index])
        extra -= take
        weight += take * sigmas[index]
    require(extra == 0, "greedy cut coverage")
    return weight


def codegree_floor(
    n3: int, n2: int, singles: int, pattern: Mapping[str, Any]
) -> tuple[int, int] | None:
    zeta = [int(value) for value in pattern["ZETA"]]
    residual = [value - n3 for value in zeta]
    if any(value < 0 for value in residual) or sum(residual) != singles + 2 * n2:
        return None
    hedges = {tuple(edge) for edge in pattern["H_EDGES"]}
    best: int | None = None
    for on_01 in range(n2 + 1):
        for on_02 in range(n2 - on_01 + 1):
            on_12 = n2 - on_01 - on_02
            load = [on_01 + on_02, on_01 + on_12, on_02 + on_12]
            if any(load[index] > residual[index] for index in range(3)):
                continue
            codegree = {(0, 1): n3 + on_01, (0, 2): n3 + on_02, (1, 2): n3 + on_12}
            value = sum(codegree[edge] for edge in hedges)
            if best is None or value < best:
                best = value
    if best is None:
        return None
    return best, int(pattern["T_N"])


def complement_edge_floor(n3: int, shore: Sequence[tuple[int, int, int]]) -> int | None:
    """Minimum of the proved C_Y expressions. None means the degree box is empty."""

    if n3 == 0:
        return 0
    sigmas = [sigma for sigma, _, _ in shore]
    lows = [max(0, n3 - complement) for _, complement, _ in shore]
    highs = [min(n3, inside) for _, _, inside in shore]
    if any(low > high for low, high in zip(lows, highs, strict=True)):
        return None
    residual_sum = sum(sigmas)
    pair_cap = comb(n3, 2)
    best: int | None = None
    for edges in range(pair_cap + 1):
        cut = 4 * n3 - 2 * edges
        weight = max_cut_weight(sigmas, lows, highs, cut)
        if weight is None:
            continue
        value = 3 * (pair_cap - edges) + n3 * residual_sum - weight
        if best is None or value < best:
            best = value
    if best is None:
        return None
    return max(0, best)


def sigma_lists(m1: int, n0: int, n1: int, n2: int, n3: int) -> list[list[Any]]:
    return [
        [6, [0]],
        [5, [0] * (11 - m1) + [1] * m1],
        [1, [0] * n0 + [1] * n1 + [2] * n2 + [3] * n3],
    ]


def raw_split(m1: int, n2: int, n3: int, zeta: Sequence[int]) -> int:
    """233 + sum sigma*(sigma-d) + sum zeta*(zeta-4). Sigma 1 on degree 1 contributes 0."""

    return 233 - 4 * m1 + 2 * n2 + 6 * n3 + sum(value * (value - 4) for value in zeta)


@cache
def kz_relaxation(pid: str) -> Record:
    """Score every Z-graph state. The cap is that maximum."""

    premises = kz_premises(pid)
    require(premises["Q"] == 54 and premises["UPPER_CONSTANT"] == 233, "split constants")
    patterns = z_patterns()
    states: list[Record] = []
    signatures = 0
    crossing_pairs = 0
    for m1 in range(12):
        for n0 in range(6):
            for n1 in range(6 - n0):
                for n2 in range(6 - n0 - n1):
                    n3 = 5 - n0 - n1 - n2
                    signatures += 1
                    shore = shore_vertices(n3, m1, n2, n1, n0)
                    for pattern in patterns:
                        zeta = tuple(int(value) for value in pattern["ZETA"])
                        crossing = m1 + n1 + 2 * n2 + 3 * n3
                        if sum(zeta) != crossing:
                            continue
                        crossing_pairs += 1
                        floor_y = complement_edge_floor(n3, shore)
                        require(floor_y is not None, "empty cut domain; no silent state deletion")
                        scored = codegree_floor(n3, n2, m1 + n1, pattern)
                        require(
                            scored is not None, "empty crossing domain; no silent state deletion"
                        )
                        assert scored is not None and floor_y is not None
                        floor_x, triangles_n = scored
                        exact = raw_split(m1, n2, n3, zeta)
                        require(sum(zeta) == crossing, "crossing equality")
                        expanded = (
                            233
                            - 10 * crossing
                            + m1 * 1 * (10 - 5 + 1)
                            + n1 * 1 * (10 - 1 + 1)
                            + n2 * 2 * (10 - 1 + 2)
                            + n3 * 3 * (10 - 1 + 3)
                            + sum(value * (value - 4) for value in zeta)
                        )
                        require(exact == expanded, "split algebra")
                        upper = exact - floor_x - triangles_n - floor_y
                        require(floor_x >= 0 and triangles_n >= 0 and floor_y >= 0, "floors")
                        states.append(
                            {
                                "R": sum(zeta),
                                "SIGMA_BY_D": sigma_lists(m1, n0, n1, n2, n3),
                                "ZETA": list(zeta),
                                "E": exact,
                                "C_X_FLOOR": floor_x,
                                "T_N": triangles_n,
                                "C_Y_FLOOR": floor_y,
                                "T_M_FLOOR": 0,
                                "UPPER": upper,
                                "COUNTS": {"M1": m1, "N0": n0, "N1": n1, "N2": n2, "N3": n3},
                            }
                        )
    require(signatures == 12 * 56, "sigma signatures")
    require(crossing_pairs == len(states), "complete crossing-domain retention")
    require(bool(states), "empty K/Z relaxation")
    cap = max(state["UPPER"] for state in states)
    rows = [state_row(state) for state in sorted(states, key=state_key)]
    maxima = sorted((state for state in states if state["UPPER"] == cap), key=state_key)
    diagnostics: list[Record] = []
    for state in maxima:
        sigma = [value for _, values in state["SIGMA_BY_D"] for value in values]
        classes = state["COUNTS"]
        shore = shore_vertices(
            classes["N3"], classes["M1"], classes["N2"], classes["N1"], classes["N0"]
        )
        complement_degrees = [10 - 1 + 3] * classes["N3"] + [degree for _, degree, _ in shore]
        diagnostics.append(
            {
                "R": state["R"],
                "ZETA": state["ZETA"],
                "M_GRAPHICAL_DIAGNOSTIC_ONLY": graphical(complement_degrees),
                "G_Z_GRAPHICAL_DIAGNOSTIC_ONLY": graphical([6 - value for value in state["ZETA"]]),
                "CROSSING_BIGRAPHICAL_DIAGNOSTIC_ONLY": bipartite_necessary(sigma, state["ZETA"]),
                "ASSERTED_REALIZABLE": False,
            }
        )
    return {
        "PARTITION": premises["PARTITION"],
        "PREMISES": premises,
        "Z_GRAPH_PATTERNS": list(patterns),
        "RAW_RANGE_PAIR_COUNT_NOT_SCORED": raw_range_pairs(pid),
        "SECANT_CAP_NOT_ADOPTED": secant_cap(pid),
        "CAP": cap,
        "SIGMA_SIGNATURES": signatures,
        "Z_GRAPHS_ENUMERATED": 8,
        "Z_GRAPH_SIGNATURE_PAIRS": signatures * len(patterns),
        "PAIRS_WITH_EQUAL_CROSSING_SUMS": crossing_pairs,
        "RETAINED_STATE_COUNT": len(states),
        "REJECTED_BEFORE_SCORING": 0,
        "REJECTED_AFTER_SCORING": 0,
        "RETAINED_STATES_SHA256": sha(render(rows)),
        "PER_R_MAXIMUM": {
            str(crossing): max(state["UPPER"] for state in states if state["R"] == crossing)
            for crossing in sorted({state["R"] for state in states})
        },
        "PER_ZETA_MAXIMUM": {
            "".join(map(str, pattern["ZETA"])): max(
                state["UPPER"] for state in states if state["ZETA"] == pattern["ZETA"]
            )
            for pattern in patterns
        },
        "ALL_ARGMAX": maxima,
        "ARGMAX_GRAPHICALITY_DIAGNOSTICS_ONLY": diagnostics,
        "REALIZABILITY": "NOT_ASSERTED; Z_GRAPH_DOMAIN; M_GRAPHICALITY_NOT_SCREENED",
        "LOSS_IDENTITY": "CAP-T=(CAP-UPPER)+(C_X-C_X_FLOOR)+(C_Y-C_Y_FLOOR)+T_M",
        "RETAINED_STATE_ROWS": rows,
    }


def state_key(state: Mapping[str, Any]) -> tuple[Any, ...]:
    counts = state["COUNTS"]
    return (
        -int(state["UPPER"]),
        int(state["R"]),
        tuple(int(value) for value in state["ZETA"]),
        counts["M1"],
        counts["N3"],
        counts["N2"],
        counts["N1"],
        counts["N0"],
    )


def state_row(state: Mapping[str, Any]) -> str:
    counts = state["COUNTS"]
    return (
        f"r={state['R']};m1={counts['M1']};n={counts['N0']}{counts['N1']}{counts['N2']}{counts['N3']};"
        f"zeta={''.join(map(str, state['ZETA']))};E={state['E']};cx={state['C_X_FLOOR']};"
        f"tn={state['T_N']};cy={state['C_Y_FLOOR']};upper={state['UPPER']}"
    )


def raw_range_pairs(pid: str) -> int:
    """Diagnostic size of the unscreened box. It is not the scored domain."""

    premises = kz_premises(pid)
    low, high = premises["ZETA_RANGE"]
    count = 0
    for m1 in range(12):
        for n0 in range(6):
            for n1 in range(6 - n0):
                for n2 in range(6 - n0 - n1):
                    n3 = 5 - n0 - n1 - n2
                    crossing = m1 + n1 + 2 * n2 + 3 * n3
                    for zeta in combinations_with_replacement(range(low, high + 1), 3):
                        if sum(zeta) == crossing:
                            count += 1
    return count


def secant_cap(pid: str) -> int:
    """Closed secant bound. It is valid and strictly weaker than the adopted cap."""

    premises = kz_premises(pid)
    low, high = premises["ZETA_RANGE"]
    slope = low + high + premises["Z"] - 7
    constant = premises["UPPER_CONSTANT"] - premises["Z"] * low * high
    total = constant
    facts = profile_facts(pid)
    for degree, count in sorted(
        Counter(value for value in facts["D"] if value > 0).items(), reverse=True
    ):
        floor, ceiling = premises["SIGMA_RANGE_BY_D"][str(degree)]
        linear = premises["K"] - 7 - degree + slope - premises["CROSSING_COEFFICIENT"]
        total += count * max(value * (value + linear) for value in range(floor, ceiling + 1))
    return total


def validate_kz_coverage(pid: str, claimed: Mapping[str, Any]) -> None:
    expected = kz_relaxation(pid)
    for key in ("SIGMA_SIGNATURES", "Z_GRAPHS_ENUMERATED", "RETAINED_STATE_COUNT", "CAP"):
        require(claimed.get(key) == expected[key], "wrong K/Z relaxation coverage: " + key)
    rows = claimed.get("RETAINED_STATE_ROWS")
    require(
        rows == expected["RETAINED_STATE_ROWS"]
        and claimed.get("RETAINED_STATES_SHA256") == sha(render(rows)),
        "wrong K/Z relaxation coverage: states",
    )
    require(render(claimed.get("ALL_ARGMAX")) == render(expected["ALL_ARGMAX"]), "K/Z argmax")
    require(int(expected["CAP"]) < int(expected["SECANT_CAP_NOT_ADOPTED"]), "secant was adopted")
    require(render(dict(claimed)) == render(expected), "wrong K/Z certificate")


def base_authority(pid: str, r30: Mapping[str, Any]) -> Record:
    degrees = tuple(map(int, pid))
    records = [
        attempt
        for attempt in r30["GROUP_ATTEMPTS"]
        if attempt.get("PROFILE_IDS") == [pid] and attempt.get("STATUS") == "INFEASIBLE"
    ]
    require(bool(records), "missing exact-profile R30 authority")
    chosen = min(records, key=lambda attempt: attempt["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"])
    accepted = chosen["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"]
    require(
        route.r28.r26.accepted_cap(chosen, (degrees,), accepted) == accepted,
        "Base rejected R30 cap",
    )
    nb_cap, class_cap = upstream.r2.nb.profile_nb_cap(degrees)[2], upstream.r2.nb.r18_cap(degrees)
    return {
        "ACCEPTED_R30_CAP": accepted,
        "R30_ATTEMPT": chosen,
        "R30_EXACT_PROFILE_ATTEMPTS": len(records),
        "R30_RESULT_SHA256": R30_SHA,
        "NB_CAP": nb_cap,
        "CLASS_CAP": class_cap,
        "OLD_CAP": min(accepted, nb_cap, class_cap),
        "S4_BASE": route.r28.profile_s4_floor(degrees),
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


def exact_term(pid: str, triangles: int, floor: int) -> Term:
    facts = profile_facts(pid)
    opened = facts["WEDGES"] - 3 * triangles
    require(opened >= 0 and floor >= 0, "nonnegative premises")
    k4 = max(0, ceil_div(facts["J"] - (facts["G_MAX"] - 2) * opened, 4))
    contained = min(k4, facts["A_MAX"])
    s4 = max(floor, 448 * contained + 679 * (k4 - contained))
    s3 = 2800 * opened + 20272 * (triangles - 22) + 154000
    exact = Fraction(S1_MINUS_S2 + s3) - Fraction(4 * s4, 7)
    return triangles, ceil_div(exact.numerator, exact.denominator), k4, contained, s4, s3


def fraction_record(term: Term) -> Record:
    exact = Fraction(S1_MINUS_S2 + term[5]) - Fraction(4 * term[4], 7)
    require(ceil_div(exact.numerator, exact.denominator) == term[1], "Fraction ceiling")
    return {
        "T": term[0],
        "NUMERATOR": exact.numerator,
        "DENOMINATOR": exact.denominator,
        "CEILING": term[1],
    }


def validate_envelope(pid: str, cap: int, floor: int, terms: Sequence[Sequence[int]]) -> None:
    facts = profile_facts(pid)
    require(type(cap) is int and 22 <= cap <= facts["WEDGE_TRIANGLE_CAP"], "T cap range")
    require(type(floor) is int and floor >= 0, "S4 floor premise")
    require([row[0] for row in terms] == list(range(22, cap + 1)), "incomplete envelope")
    for row in terms:
        require(
            len(row) == 6 and all(type(value) is int for value in row), "term shape/integrality"
        )
        expected = exact_term(pid, row[0], floor)
        for index, message in (
            (2, "K4 ceiling"),
            (3, "A_max contained-K4"),
            (4, "S4 MAX floor"),
            (5, "S3 identity"),
            (1, "Fraction ceiling"),
        ):
            require(row[index] == expected[index], message)


def envelope(pid: str, cap: int, floor: int) -> list[Term]:
    degrees = tuple(profile_facts(pid)["D"])
    a_max = route.contained_triple_k4_cap(degrees)
    require(a_max == profile_facts(pid)["A_MAX"], "Base A_max")
    terms = [
        cast(Term, tuple(route.envelope_term(degrees, triangles, floor, a_max)))
        for triangles in range(22, cap + 1)
    ]
    validate_envelope(pid, cap, floor, terms)
    return terms


def checked_rows(rows: Sequence[tuple[str, int]], expected: Mapping[str, int]) -> dict[str, int]:
    require(
        len(rows) == len(expected) == len({profile for profile, _ in rows}),
        "ledger row count/duplicate",
    )
    require(
        all(type(bound) is int for _, bound in rows) and dict(rows) == expected,
        "ledger row identity/bound",
    )
    return dict(rows)


def family_summary(resolved: Mapping[str, int], cursor: Mapping[str, int]) -> Record:
    require(len(resolved) == RESOLVED_COUNT and len(cursor) == CURSOR_COUNT, "family row count")
    require(not resolved.keys() & cursor.keys(), "family ledger overlap")
    require(
        all(type(bound) is int for bound in (*resolved.values(), *cursor.values())),
        "ledger integers",
    )
    rows = dict(resolved) | dict(cursor)
    levels = sorted(set(rows.values()), reverse=True)
    return {
        "MAXIMUM": levels[0],
        "ALL_MAX_OWNERS": sorted(profile for profile, bound in rows.items() if bound == levels[0]),
        "NEXT_DISTINCT_BOUND": levels[1],
        "ALL_NEXT_DISTINCT_OWNERS": sorted(
            profile for profile, bound in rows.items() if bound == levels[1]
        ),
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
    return {profile: new.get(profile, bound) for profile, bound in resolved.items()}


def validate_family(
    resolved: Mapping[str, int], cursor: Mapping[str, int], claimed: Mapping[str, Any]
) -> None:
    require(render(claimed) == render(family_summary(resolved, cursor)), "wrong family aggregation")


def ledger_partition(
    resolved: Mapping[str, int], cursor: Mapping[str, int], fixed: Mapping[str, Any]
) -> Record:
    raw = {
        "".join(map(str, profile)): upstream.wedges(profile)
        for profile in upstream.raw_histograms()
    }
    require(len(raw) == RAW_COUNT, "raw histogram census")
    require(cursor == fixed["CURSOR_197_PRESERVED"]["ROW_BOUNDS"], "cursor ledger")
    require(
        set(cursor) == {profile for profile, wedge in raw.items() if wedge <= 785},
        "cursor partition",
    )
    require(set(resolved) <= raw.keys() and not set(resolved) & set(cursor), "resolved partition")
    excluded = sorted(raw.keys() - set(cursor) - set(resolved), reverse=True)
    inherited = fixed["INHERITED_EXCLUSION"]["ORIGINAL_CONDITIONS_VERBATIM"]
    require(
        len(excluded) == EXCLUDED_COUNT == inherited["COUNT"]
        and upstream.ids_digest(excluded) == inherited["IDS_SHA256"]
        and [min(raw[profile] for profile in excluded), max(raw[profile] for profile in excluded)]
        == inherited["W_RANGE"],
        "inherited exclusion partition",
    )
    return {
        "RAW_HISTOGRAMS": len(raw),
        "RESOLVED_COUNT": len(resolved),
        "CURSOR_COUNT": len(cursor),
        "EXCLUDED_COUNT": len(excluded),
        "EXCLUDED_IDS_SHA256": upstream.ids_digest(excluded),
        "CURSOR_W_HISTOGRAM": {
            str(wedge): count
            for wedge, count in sorted(Counter(raw[profile] for profile in cursor).items())
        },
        "OWNER_W": {PROFILE: raw[PROFILE]},
    }


def check_sigma_zeta(pid: str, sigma_by_d: Sequence[Sequence[Any]], zeta: Sequence[int]) -> None:
    """Reject a labelled state outside the Z=3 ranges or the Z-graph domain."""

    premises = kz_premises(pid)
    require([row[0] for row in sigma_by_d] == [6, 5, 1], "sigma degree classes")
    expected_lengths = {6: 1, 5: 11, 1: 5}
    for degree, values in sigma_by_d:
        low, high = premises["SIGMA_RANGE_BY_D"][str(degree)]
        require(len(values) == expected_lengths[degree], "sigma degree classes")
        require(all(type(value) is int and low <= value <= high for value in values), "sigma range")
        require(list(values) == sorted(values), "sigma canonical order")
    z_low, z_high = premises["ZETA_RANGE"]
    require(
        len(zeta) == 3 and all(type(value) is int and z_low <= value <= z_high for value in zeta),
        "zeta range",
    )
    require(list(zeta) == sorted(zeta), "zeta canonical order")
    sigma = [value for _, values in sigma_by_d for value in values]
    require(sum(sigma) == sum(zeta), "crossing sums")
    require(pattern_for(zeta) is not None, "zeta outside the 8 graphs on Z")


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
        and before["ALL_NEXT_DISTINCT_OWNERS"] == [EXPECTED_NEXT_OWNER]
        and fixed["ALL_NEW_MAX_OWNERS"] == [PROFILE],
        "fixed complete family/owner frontier",
    )
    partition = ledger_partition(resolved, cursor, fixed)
    facts = profile_facts(PROFILE)
    require(
        facts["D_HISTOGRAM"] == {"6": 1, "5": 11, "1": 5, "0": 3}
        and facts["WEDGES"] == 821
        and facts["GOODMAN"] == 287
        and (facts["K"], facts["Z"]) == (17, 3),
        "profile structure",
    )
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
    old_bound = max(term[1] for term in old_terms)
    require(
        old_bound == resolved[PROFILE] == base["RESOLVED_ROW_BOUNDS"][PROFILE],
        "old full Base envelope replay",
    )
    relaxation = kz_relaxation(PROFILE)
    new_cap = relaxation["CAP"]
    validate_cap(PROFILE, new_cap)
    require(22 <= new_cap < old_cap, "no proven cap improvement")
    new_terms = envelope(PROFILE, new_cap, floor)
    new_bound = max(term[1] for term in new_terms)
    zero_floor = max(term[1] for term in envelope(PROFILE, new_cap, 0))
    after_resolved = replace_owner(resolved, {PROFILE: new_bound}, before["ALL_MAX_OWNERS"])
    require(
        {profile: bound for profile, bound in after_resolved.items() if profile != PROFILE}
        == {profile: bound for profile, bound in resolved.items() if profile != PROFILE},
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
        "REMAINDER_NONNEGATIVITY": (
            "T_M>=0; C_X>=C_X_FLOOR; C_Y>=C_Y_FLOOR; T_N EXACT ON EACH Z GRAPH"
        ),
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
        "OLD_ALL_ARGMAX": [term for term in old_terms if term[1] == old_bound],
        "NEW_ALL_ARGMAX": [term for term in new_terms if term[1] == new_bound],
        "OLD_ARGMAX_EXACT_FRACTIONS": [
            fraction_record(term) for term in old_terms if term[1] == old_bound
        ],
        "NEW_ARGMAX_EXACT_FRACTIONS": [
            fraction_record(term) for term in new_terms if term[1] == new_bound
        ],
        "NEW_BOUND_WITH_S4_FLOOR_ZERO": zero_floor,
        "S4_BASE_LOAD_BEARING": zero_floor != new_bound,
        "FRACTIONAL_S4_CREDIT_TERMS": sum((4 * term[4]) % 7 != 0 for term in new_terms),
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
        "RESOLVED_ROWS_CHANGED": sorted(
            profile for profile in resolved if resolved[profile] != after_resolved[profile]
        ),
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
    summary = {
        key: result[key]
        for key in (
            "TASK_STATUS",
            "OLD_CAP",
            "NEW_CAP",
            "OLD_BOUND",
            "NEW_BOUND",
            "FAMILY_DELTA",
            "GAP_TO_INCUMBENT",
        )
    }
    summary["FAMILY_BEFORE"] = result["FAMILY_BEFORE"]["MAXIMUM"]
    summary["FAMILY_AFTER"] = result["FAMILY_AFTER"]["MAXIMUM"]
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
