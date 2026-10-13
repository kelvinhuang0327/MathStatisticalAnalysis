"""Full-profile certificate for 66665555555411100000; no solver or family update.

Support premises: 20 tickets of capacity 6, 22 triple labels, 27 pair labels,
and distinct ticket pairs across all supports. Thus G has 93 edges and
deg_G(x)=6+d_x. The profile is (6^4,5^7,4,1^3,0^5), sum d=66,
sum d^2=338. H=complement(G) has degree 13-d and 97 edges. Counting triples
by their H edges gives t(G)+t(H)=1140-18*97+sum C(13-d,2)=298.
Independently, Goodman gives 1140-sum (6+d)(13-d)/2=298.

Let K={d>0}, Z={d=0}, of sizes 15 and 5; M=H[K], Q=H[Z].
sigma_x=|N_G(x) intersect Z|, zeta_u=|N_G(u) intersect K|, and
r=sum sigma=sum zeta. Only pair labels reach Z: 0<=sigma_x<=6-d_x.
A zero has G degree 6 and at most four zero neighbours: 2<=zeta_u<=6.
Consequently h_x=deg_M(x)=8-d_x+sigma_x and deg_Q(u)=zeta_u-2.
|M|=(54+r)/2, |Q|=(r-10)/2. Each mixed H triangle has exactly one
same-part edge. For xy in M its zero apices number
5-sigma_x-sigma_y+|N_G(x) intersect N_G(y) intersect Z|;
for uv in Q its core apices number
15-zeta_u-zeta_v+|N_G(u) intersect N_G(v) intersect K|. Therefore

 t(H)=60+12r-sum sigma_x(8-d_x+sigma_x)-sum zeta_u^2+P,
 P=t(M)+t(Q)+sum_M c_Z(xy)+sum_Q c_K(uv)>=0,
 T=t(G)=238+sum sigma_x(sigma_x+2-d_x)+sum zeta_u(zeta_u-6)-P.

The additional, load-bearing inequality uses L={d=1}, |L|=3, and
D=K\\L, |D|=12. Write J=M[L], ell_i=deg_J(i), s_i=sigma_i,
b_i=7+s_i-ell_i=|N_M(i) intersect D|. Every vertex of D meets at most
min(3,h_x) vertices of L. This sum is 4*2+7*3+3=32, regardless of
the d=5 cross choices and the d=4 cross choice. Hence
 sum b_i=21+sum s_i-2|J|<=32, or 2|J|>=sum s_i-11.
For each ij in J there are at least max(0,b_i+b_j-12) common M neighbours
in D and at least max(0,s_i+s_j-5) common G neighbours in Z. Triangles
with two vertices in L and one in D are counted once, by their unique
L edge; t(J) counts the all-L triangles. These and the c_Z terms are
different summands of P, so

 P >= t(J)+sum_{ij in J}[max(0,b_i+b_j-12)+max(0,s_i+s_j-5)].

Complete finite relaxation: a=sum sigma at the seven d=5 vertices is
0..7, q=sigma at d=4 is 0..2, and the three s_i are sorted in 0..5.
The four d=6 cross degrees vanish. Enumerate every labelled graph J
on three vertices (8 masks) and every sorted zeta obtained from a graph
Q on five vertices (all 1024 masks, with zeta=deg_Q+2). Require equal
cross sums and the capacity inequality above. Every legal support
structure maps to this set: sorting L just permutes the exhaustively
enumerated J; sorting Z preserves F and these lower bounds. No joint
realizability, graphicality of M/residual pairs, or full cross Gale-Ryser
condition is assumed. Omitting them enlarges the set. Max(F-P_floor)
over the entire relaxation is 262. This proves T<=262 for the full
profile. A relaxation maximizer is not claimed to be realizable or to
attain the cap. The old cap 264 is not a premise of this proof.

Route B is evaluated separately at every integer 22<=T<=cap. Its frozen
open-wedge K4 floor is ceil((U-(g_max-2)(W-3T))/4), truncated at zero.
U=2360, W=832, g_max=12. The contained-triple K4 cap is
floor(sum d(d+4)/3)=200. S4=max(112,679*K4-231*min(K4,200));
S3=2800*832+11872*(T-22)-30800. The integer union bound is
372228640-63838600+S3-floor(4*S4/7), the ceiling of its rational bound.
The complete old envelope reproduces the recorded 313398144 at 264;
the new envelope peaks at 262 with 313380220. No other owner is refined.
"""

from __future__ import annotations

import ast
import hashlib
import json
import resource
import subprocess
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from itertools import combinations, combinations_with_replacement, product
from math import comb
from pathlib import Path
from time import process_time

TASK_ID = "B649_FRONTIER_OWNER_B_EXACT_BOUND_R1"
FROZEN_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
FROZEN_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
FROZEN_RESULT = "b649-min-s2-next-owner-core-zero-t256-cert-r1-result.json"
FROZEN_SHA256 = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"
PROFILE_ID = "66665555555411100000"
PROFILE = tuple(map(int, PROFILE_ID))
OLD_CAP, NEW_CAP, S4_BASE = 264, 262, 112
OLD_BOUND, NEXT_BOUND, INCUMBENT = 313_398_144, 313_397_860, 313_263_888
ROOT = Path(__file__).resolve().parents[3]
RESULT_DIR = "docs/research/matrix-native-results"
RESULT_PATH = ROOT / RESULT_DIR / "b649-frontier-owner-b-exact-bound-r1-result.json"
EDGES_3 = tuple(combinations(range(3), 2))
EDGES_5 = tuple(combinations(range(5), 2))
FOCUSED_COMMAND = (
    "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3.13 "
    "tests/unit/test_b649_frontier_owner_b_exact_bound_r1.py --write-result"
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def profile_check(profile: tuple[int, ...]) -> None:
    require(
        len(profile) == 20 and all(type(d) is int for d in profile) and profile == PROFILE,
        "wrong full profile",
    )
    require(
        Counter(profile) == {6: 4, 5: 7, 4: 1, 1: 3, 0: 5}
        and sum(profile) == 66
        and sum(d * d for d in profile) == 338,
        "degree identities",
    )


def validate_pin(head: str, tree: str, raw: bytes) -> None:
    require(head == FROZEN_HEAD, "frozen HEAD mismatch")
    require(tree == FROZEN_TREE, "full frozen tree mismatch")
    require(hashlib.sha256(raw).hexdigest() == FROZEN_SHA256, "frozen result SHA256 mismatch")


def frozen_blob(path: str) -> bytes:
    raw = subprocess.check_output(["git", "show", f"{FROZEN_HEAD}:{path}"], cwd=ROOT)
    require((ROOT / path).read_bytes() == raw, f"working source differs from frozen blob: {path}")
    return raw


def frozen_json(filename: str, digest: str) -> dict:
    raw = frozen_blob(f"{RESULT_DIR}/{filename}")
    require(hashlib.sha256(raw).hexdigest() == digest, f"supporting source pin: {filename}")
    return json.loads(raw)


def literal_constant(module: str, name: str) -> int:
    source = frozen_blob(f"src/lottolab/research/{module}.py")
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            value = ast.literal_eval(node.value)
            require(type(value) is int, "source constant must be integer")
            return value
    raise AssertionError(f"source constant missing: {name}")


def nb_cap(profile: tuple[int, ...]) -> int:
    """Only for mechanically recovering the inherited row's synthetic source index."""
    g = [6 + d for d in profile]
    wedges = sum(comb(v, 2) for v in g)
    ow = sum(
        comb(v, 2)
        - sum(min(x - 1, v - 1) for x in sorted(g[:i] + g[i + 1 :], reverse=True)[:v]) // 2
        for i, v in enumerate(g)
    )
    return (wedges - ow) // 3


def source_check() -> dict:
    """Read-only source recovery; never replay the family or call a solver."""
    head = subprocess.check_output(["git", "rev-parse", FROZEN_HEAD], cwd=ROOT).decode().strip()
    tree = (
        subprocess.check_output(["git", "rev-parse", f"{FROZEN_HEAD}^{{tree}}"], cwd=ROOT)
        .decode()
        .strip()
    )
    raw = frozen_blob(f"{RESULT_DIR}/{FROZEN_RESULT}")
    validate_pin(head, tree, raw)
    sealed = json.loads(raw)
    six = frozen_json(
        "b649-min-s2-six-row-existing-s4-family-authority-r1-result.json",
        sealed["SIX_ROW_RESULT_SHA256"],
    )
    require(six["RESOLVED_ROW_BOUNDS"][PROFILE_ID] == OLD_BOUND, "formal row bound mismatch")
    require(
        PROFILE_ID not in sealed["ROWS_CHANGED_FROM_SIX_ROW"]
        and PROFILE_ID not in sealed["CERTIFICATE_PROFILE_IDS"],
        "target was changed by the frozen seven-row update",
    )
    nb = frozen_json(
        "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json",
        "609d5f6bf96e8d6454918f747c764e479f88bbb0da94d3934c2969b8f6cc7f0f",
    )
    inherited = nb["INHERITED_R10_PROFILES"][1]
    require(
        inherited["PROFILE_ID"] == PROFILE_ID
        and inherited["CATALOG_TRIANGLE_CAP"] == OLD_CAP
        and inherited["CAP_SOURCE"] == "SEALED_R30_INFEASIBLE_REFUTATION_AT_CAP_PLUS_ONE",
        "inherited source cap mismatch",
    )
    require(nb_cap(PROFILE) == 265, "source NB cap mismatch")
    # R18's induced-P3 floor is 5 here: clique components have sizes 7..13;
    # with twenty vertices only two components fit, and none has 93 edges.
    clique_totals = {comb(k, 2) + comb(20 - k, 2) for k in range(7, 11)}
    require(93 not in clique_totals, "R18 clique partition exclusion")
    require(
        min(nb_cap(PROFILE), (832 - 5) // 3, inherited["CATALOG_TRIANGLE_CAP"]) == OLD_CAP,
        "combined recorded T cap mismatch",
    )
    require(
        literal_constant(
            "b649_k20_min_s2_dangerous_core_realizability_r5", "K20_REUSED_S4_LOWER_BOUND"
        )
        == S4_BASE,
        "source S4 base mismatch",
    )
    require(
        literal_constant(
            "b649_k20_min_s2_next_distinct_plateau_r10",
            "SEVEN_INACTIVE_TICKET_S4_LOWER_BOUND",
        )
        == 1680,
        "source seven-zero S4 selector constant",
    )
    require(
        literal_constant("b649_k20_min_s2_higher_order_closure_r2", "K20_S1") == 372_228_640
        and literal_constant("b649_k20_min_s2_higher_order_closure_r2", "K20_S2") == 63_838_600,
        "source S1/S2 mismatch",
    )
    # Validate the frozen default S4 selector, without importing the research/solver chain.
    selector = frozen_blob(
        "src/lottolab/research/b649_k20_min_s2_current_cursor_class_owner_chase_r28.py"
    )
    node = next(
        n
        for n in ast.parse(selector).body
        if isinstance(n, ast.FunctionDef) and n.name == "profile_s4_floor"
    )
    require(
        ast.unparse(node.body[-1])
        == (
            "return max(K20_REUSED_S4_LOWER_BOUND, "
            "SEVEN_INACTIVE_TICKET_S4_LOWER_BOUND if profile.count(0) == 7 else 0)"
        ),
        "source S4 selector mismatch",
    )
    r32 = frozen_json(
        "b649-k20-min-s2-route-b-current-owner-refinement-r32-result.json",
        nb["R32_RESULT_SHA256"],
    )
    # Recover NB_CERTIFICATES[index] without the expensive catalog replay. The original
    # cap is min(NB,R18,catalog), hence <= this NB-only candidate cap. Every candidate
    # adoption must be an original adoption (Route-B maxima are monotone in cap).
    # Equal cardinalities with the sealed adoption count prove identical membership.
    candidates = []
    for row in sorted(r32["FINAL_RESOLVED_LEDGER"], key=lambda x: x["PROFILE_ID"], reverse=True):
        p = tuple(map(int, row["PROFILE_ID"]))
        base = 1680 if p.count(0) == 7 else S4_BASE
        cap = nb_cap(p)
        bound = max(t[1] for t in route_terms(p, cap, base))
        if bound < row["CURRENT_BOUND"]:
            candidates.append(row["PROFILE_ID"])
    require(len(candidates) == nb["ADOPTED_COUNT"] == 1790, "source adoption set incomplete")
    source_index = candidates.index(PROFILE_ID)
    require(source_index == 871, "synthetic source row index mismatch")
    return {
        "FROZEN_HEAD": "MATCH",
        "FROZEN_TREE": "MATCH",
        "FROZEN_RESULT_SHA256": "MATCH",
        "HEAD": head,
        "TREE": tree,
        "RESULT_SHA256": FROZEN_SHA256,
        "SOURCE_T_CAP": OLD_CAP,
        "SOURCE_S4_BASE": S4_BASE,
        "SOURCE_ROW_BOUND": OLD_BOUND,
        "SOURCE_LOCATOR": (
            "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:NB_CERTIFICATES[871]"
        ),
        "SOURCE_INDEX_RECOVERY": (
            "NB-only candidate adoptions subset original; equal sealed count 1790"
        ),
        "SOURCE_CAP_COMPONENTS": {"NB": 265, "R18": 275, "CATALOG": 264},
        "RECORDED_BOUND_LOCATOR": (
            "b649-min-s2-six-row-existing-s4-family-authority-r1-result.json:"
            f"RESOLVED_ROW_BOUNDS[{PROFILE_ID}]; unchanged by frozen seven-row result"
        ),
        "CATALOG_CAP_LOCATOR": (
            "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:INHERITED_R10_PROFILES[1]"
        ),
        "OLD_ENVELOPE": max(route_terms(PROFILE, OLD_CAP, S4_BASE), key=lambda t: t[1]),
    }


def graph_edges(mask: int, edges: tuple) -> tuple:
    require(type(mask) is int and 0 <= mask < 1 << len(edges), "graph mask outside exact domain")
    return tuple(e for i, e in enumerate(edges) if mask >> i & 1)


@cache
def zero_domain() -> frozenset[tuple[int, ...]]:
    """All five-vertex zero graphs, exhaustively projected to deg_H[Z]+2."""
    return frozenset(
        tuple(sorted(2 + sum(v in e for e in graph_edges(mask, EDGES_5)) for v in range(5)))
        for mask in range(1 << len(EDGES_5))
    )


@dataclass(frozen=True)
class State:
    a: int
    q: int
    low: tuple[int, int, int]
    zeta: tuple[int, int, int, int, int]
    mask: int


def validate_state(s: State, *, require_zero: bool = True, require_capacity: bool = True) -> None:
    require(type(s.a) is int and 0 <= s.a <= 7, "d5 cross range")
    require(type(s.q) is int and 0 <= s.q <= 2, "d4 cross range")
    require(
        len(s.low) == 3
        and all(type(x) is int and 0 <= x <= 5 for x in s.low)
        and tuple(sorted(s.low)) == s.low,
        "low cross range or symmetry",
    )
    require(
        len(s.zeta) == 5
        and all(type(x) is int and 2 <= x <= 6 for x in s.zeta)
        and tuple(sorted(s.zeta)) == s.zeta,
        "zero cross range or symmetry",
    )
    require(s.a + s.q + sum(s.low) == sum(s.zeta), "cross sums unequal")
    edges = graph_edges(s.mask, EDGES_3)
    require(not require_zero or s.zeta in zero_domain(), "zero graph not graphical")
    require(
        not require_capacity or 2 * len(edges) >= sum(s.low) - 11,
        "low-to-high complement capacity",
    )


def objective(s: State) -> int:
    return (
        238
        - 2 * s.a
        + s.q * (s.q - 2)
        + sum(x * (x + 1) for x in s.low)
        + sum(x * (x - 6) for x in s.zeta)
    )


def remainder_floor(s: State, *, use_triangles: bool = True, use_common_zeros: bool = True) -> int:
    edges = graph_edges(s.mask, EDGES_3)
    ell = [sum(i in e for e in edges) for i in range(3)]
    b = [7 + s.low[i] - ell[i] for i in range(3)]
    triangles = int(s.mask == 7) + sum(max(0, b[i] + b[j] - 12) for i, j in edges)
    common_zeros = sum(max(0, s.low[i] + s.low[j] - 5) for i, j in edges)
    return (triangles if use_triangles else 0) + (common_zeros if use_common_zeros else 0)


def relaxation() -> dict:
    """Exact maximum of a proved superset; no claim of support realizability."""
    count, peak, argmax = 0, -1, None
    histogram: Counter[int] = Counter()
    for a, q, low, zeta, mask in product(
        range(8),
        range(3),
        combinations_with_replacement(range(6), 3),
        sorted(zero_domain()),
        range(8),
    ):
        if a + q + sum(low) != sum(zeta) or 2 * mask.bit_count() < sum(low) - 11:
            continue
        s = State(a, q, low, zeta, mask)
        validate_state(s)
        sigma = (0,) * 4 + (0,) * (7 - a) + (1,) * a + (q,) + low
        h = tuple(8 - d + x for d, x in zip(PROFILE[:15], sigma, strict=True))
        zero_degrees = tuple(x - 2 for x in zeta)
        require(sum(h) % 2 == sum(zero_degrees) % 2 == 0, "split edge parity")
        generic_f = (
            298
            - 5 * (sum(h) // 2)
            - 15 * (sum(zero_degrees) // 2)
            + sum(x * y for x, y in zip(sigma, h, strict=True))
            + sum(x * y for x, y in zip(zeta, zero_degrees, strict=True))
        )
        require(objective(s) == generic_f, "specialized mixed-triangle identity")
        bound = objective(s) - remainder_floor(s)
        count += 1
        histogram[bound] += 1
        if bound > peak:
            peak, argmax = bound, s
    require(count > 0 and argmax is not None, "empty relaxation cannot certify")
    require(peak == NEW_CAP, "full relaxation does not prove requested cap")
    return {
        "STATE_COUNT": count,
        "EXACT_MAXIMUM": peak,
        "ARGMAX": vars(argmax),
        "ARGMAX_F": objective(argmax),
        "ARGMAX_P_FLOOR": remainder_floor(argmax),
        "ZERO_LABELLED_GRAPHS": 1024,
        "ZERO_DEGREE_SIGNATURES": len(zero_domain()),
        "LOW_LABELLED_GRAPHS": 8,
        "HISTOGRAM": dict(sorted(histogram.items())),
        "ATTAINMENT": "NOT_ASSERTED",
    }


def route_terms(profile: tuple[int, ...], cap: int, base: int) -> list[tuple[int, ...]]:
    require(
        len(profile) == 20
        and sum(profile) == 66
        and all(type(v) is int and 0 <= v <= 6 for v in profile),
        "Route-B profile range",
    )
    g = [6 + d for d in profile]
    w, u = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g)
    require(type(cap) is int and 22 <= cap <= w // 3, "Route-B cap range")
    require(type(base) is int and base >= 0, "Route-B S4 base range")
    a_max = sum(d * (d + 4) for d in profile) // 3
    terms = []
    for t in range(22, cap + 1):
        excess = u - (max(g) - 2) * (w - 3 * t)
        k4 = max(0, -(-excess // 4))
        contained = min(k4, a_max)
        s4 = max(base, 679 * k4 - 231 * contained)
        s3 = 2800 * w + 11872 * (t - 22) - 30800
        bound = 372_228_640 - 63_838_600 + s3 - 4 * s4 // 7
        terms.append((t, bound, k4, contained, s4, s3))
    return terms


def check_terms(terms: list[tuple[int, ...]], cap: int) -> None:
    require([t[0] for t in terms] == list(range(22, cap + 1)), "incomplete integer T domain")
    for t, bound, k4, contained, s4, s3 in terms:
        # Fraction.__ceil__ is independent of the integer division implementation.
        k4_exact = max(0, Fraction(2360 - 10 * (832 - 3 * t), 4).__ceil__())
        a_exact = Fraction(338 + 4 * 66, 3).__floor__()
        c_exact = min(k4_exact, a_exact)
        s4_exact = max(S4_BASE, 448 * c_exact + 679 * (k4_exact - c_exact))
        s3_exact = 2800 * 832 + 11872 * (t - 22) - 30800
        rational = Fraction(372_228_640 - 63_838_600 + s3_exact) - Fraction(4 * s4_exact, 7)
        require(
            (k4, contained, s4, s3) == (k4_exact, c_exact, s4_exact, s3_exact)
            and bound == rational.__ceil__()
            and 0 <= bound - rational < 1,
            f"Route-B rounding/arithmetic mismatch at T={t}",
        )


def counterexamples() -> dict:
    strict = State(1, 2, (5, 5, 5), (3, 3, 3, 3, 6), 3)
    no_zero = State(1, 2, (5, 5, 5), (2, 2, 2, 6, 6), 3)
    no_capacity = State(1, 2, (5, 5, 5), (3, 3, 3, 3, 6), 0)
    validate_state(strict)
    validate_state(no_zero, require_zero=False)
    validate_state(no_capacity, require_capacity=False)
    return {
        "OMIT_ZERO_GRAPH": {
            "STATE": vars(no_zero),
            "BOUND": objective(no_zero) - remainder_floor(no_zero),
        },
        "OMIT_LOW_CAPACITY": {
            "STATE": vars(no_capacity),
            "BOUND": objective(no_capacity) - remainder_floor(no_capacity),
        },
        "OMIT_COMMON_ZERO_TERM": {
            "STATE": vars(strict),
            "BOUND": objective(strict) - remainder_floor(strict, use_common_zeros=False),
        },
        "OMIT_LOW_TRIANGLE_TERM": {
            "STATE": vars(strict),
            "BOUND": objective(strict) - remainder_floor(strict, use_triangles=False),
        },
        "INTERPRETATION": (
            "Relaxation counterexamples to omitted premises; not legal-support counterexamples"
        ),
    }


def compute_result() -> dict:
    profile_check(PROFILE)
    source = source_check()
    g = [6 + d for d in PROFILE]
    goodman = Fraction(comb(20, 3)) - Fraction(sum(v * (19 - v) for v in g), 2)
    phi = comb(20, 3) - 18 * 97 + sum(comb(13 - d, 2) for d in PROFILE)
    require(phi == goodman == 298 and sum(g) // 2 == 93, "Goodman or edge identity")
    finite = relaxation()
    old = route_terms(PROFILE, OLD_CAP, S4_BASE)
    new = route_terms(PROFILE, finite["EXACT_MAXIMUM"], S4_BASE)
    check_terms(old, OLD_CAP)
    check_terms(new, NEW_CAP)
    peak = max(new, key=lambda t: t[1])
    require(
        max(t[1] for t in old) == OLD_BOUND and new == old[: len(new)], "old row envelope mismatch"
    )
    require(peak[1] < OLD_BOUND and peak[1] <= NEXT_BOUND, "strict owner improvement missing")
    closure = max(t[0] for t in old if t[1] <= INCUMBENT)
    competitor_closure = max(t[0] for t in old if t[1] <= NEXT_BOUND)
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "PASS_FULL_PROFILE_SELF_CHECK_ONLY",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "PUBLICATION": "LOCAL_COMMIT_ONLY",
        "SOURCE": source,
        "PROFILE_ID": PROFILE_ID,
        "DEGREE_PROFILE": "6^4,5^7,4^1,1^3,0^5",
        "DEGREE_SUM": 66,
        "DEGREE_SQUARE_SUM": 338,
        "SUPPORT_MODEL": {"TRIPLE_SUPPORTS": 22, "PAIR_SUPPORTS": 27, "PAIR_OVERLAP_MAX": 1},
        "PROOF_SCOPE": "FULL_PROFILE",
        "CORE_VERTICES": 15,
        "ZERO_VERTICES": 5,
        "GRAPH_EDGES": 93,
        "COMPLEMENT_EDGES": 97,
        "GOODMAN_CONSTANT": phi,
        "PROOF": __doc__,
        "MIXED_TRIANGLE_IDENTITY": "t(H)=60+12r-sum sigma*(8-d+sigma)-sum zeta^2+P",
        "ZERO_GRAPH_DOMAIN": "All 1024 simple labelled graphs on five vertices; zeta=degree+2",
        "CROSS_EDGE_DEGREES": (
            "sigma<=6-d; 2<=zeta<=6; sum sigma=sum zeta; h=8-d+sigma; degree_Q=zeta-2"
        ),
        "NONNEGATIVE_REMAINDER": "P=t(M)+t(Q)+sum_M c_Z+sum_Q c_K; four nonnegative cardinalities",
        "LOAD_BEARING_INEQUALITY": "P>=t(J)+sum_J(max(0,b_i+b_j-12)+max(0,s_i+s_j-5))",
        "LOAD_BEARING_PREMISES": [
            "Exact full profile and linear triple/pair support model",
            "sigma ranges; zeta ranges and simple five-vertex zero graph domain",
            "Cross sums equal; all eight three-vertex low complement graphs",
            "2*edges(J)>=sum low sigma-11 from high-to-low complement capacity 32",
            "Low-low-high triangles and common-zero counts are distinct summands of P",
        ],
        "RELAXATION_COMPLETENESS": (
            "Every legal support maps to an enumerated state; "
            "omitted compatibility enlarges the domain"
        ),
        "RELAXATION": finite,
        "EXACT_UPPER_BOUND": NEW_CAP,
        "EXACT_UPPER_BOUND_MEANING": (
            "Triangle cap from exact maximum of necessary relaxation; attainment not asserted"
        ),
        "NEGATIVE_CASES": counterexamples(),
        "COUNTEREXAMPLE_RESULT": "No state in complete relaxation exceeds 262",
        "UNPROVED_ASSUMPTIONS": [],
        "OLD_BOUND": OLD_BOUND,
        "NEW_ADMISSIBLE_BOUND": peak[1],
        "OWNER_BOUND_REDUCTION": OLD_BOUND - peak[1],
        "NEXT_COMPETING_BOUND": NEXT_BOUND,
        "BOUND_BELOW_NEXT_COMPETITOR": peak[1] < NEXT_BOUND,
        "INCUMBENT": INCUMBENT,
        "OWNER_EXCLUSION_PROVED": peak[1] <= INCUMBENT,
        "CLOSURE_T_CAP": closure,
        "CLOSURE_T_CAP_MEANING": "Largest T cap sufficient for incumbent exclusion",
        "NEXT_COMPETITOR_SUFFICIENT_T_CAP": competitor_closure,
        "ROUTE_B_INTEGER_RECOUNT": "PASS",
        "T_TERM_COUNT": len(new),
        "ROUNDING_CHECK": "PASS_EXACT_RATIONAL_ALL_T",
        "ARGMAX_TERM": peak,
        "TERM_COLUMNS": ["T", "BOUND", "K4", "CONTAINED", "S4", "S3"],
        "ALL_T_TERMS": new,
        "OLD_ARGMAX_TERM": max(old, key=lambda t: t[1]),
        "WEDGES": 832,
        "SUM_GRAPH_DEGREE_CHOOSE_3": 2360,
        "A_MAX": 200,
        "FAMILY_BOUND_REDUCTION_CLAIMED": 0,
        "NEW_WINNING_OUTCOMES": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "FOCUSED_TEST_COMMAND": FOCUSED_COMMAND,
        "HEAVY_SOLVER_STARTED": "NO",
        "CPU_PROCESS_COUNT": 1,
        "CPU_PROCESS_COUNT_MEANING": "Maximum simultaneous CPU-bound task processes",
        "PRELIMINARY_SOURCE_REPLAY": (
            "Stopped by its 30-second RLIMIT_CPU; superseded by targeted source recovery"
        ),
        "PRELIMINARY_CPU_ACCOUNTING": (
            "Exact aggregate unavailable; source replay limited to 30s; "
            "other sequential prototypes under 5s"
        ),
        "CPU_BUDGET_SECONDS": 120,
        "PUSH": "NOT_RUN",
        "MERGE": "NOT_RUN",
        "PRODUCTION_MUTATION": "NONE",
        "LOCAL_COMMIT_IDENTITY_LOCATION": (
            "Final handoff (embedding the containing commit/tree would be self-referential)"
        ),
        "RESULT_SHA256_LOCATION": "Final handoff (a file cannot embed its own SHA256)",
        "WORKTREE_DISPOSITION": "RETAIN",
    }


def write_result(result: dict) -> str:
    payload = (json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()
    require(not RESULT_PATH.exists(), "result already exists; no silent overwrite")
    with RESULT_PATH.open("xb") as out:
        out.write(payload)
    return hashlib.sha256(payload).hexdigest()


if __name__ == "__main__":
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
    started = process_time()
    result = compute_result()
    result["CPU_SECONDS"] = process_time() - started
    print(
        json.dumps(
            {
                "NEW_ADMISSIBLE_BOUND": result["NEW_ADMISSIBLE_BOUND"],
                "RESULT_SHA256": write_result(result),
            }
        )
    )
