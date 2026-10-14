"""Full-profile triangle cap T<=236 for 66555555555522000000; no solver or family update.

Support premises: 20 tickets of capacity 6, 22 triple labels, 27 pair labels,
and distinct ticket pairs across all supports. Thus G has 93 edges and
deg_G(x)=6+d_x. The profile is (6^2,5^10,2^2,0^6), sum d=66, sum d^2=330.
H=complement(G) has degree 13-d and 97 edges. Counting triples by their H
edges gives t(G)+t(H)=1140-18*97+sum C(13-d,2)=1140-1746+900=294.
Independently, Goodman gives 1140-sum (6+d)(13-d)/2=1140-846=294.

Let K={d>0}, Z={d=0}, of sizes 14 and 6; M=H[K], Q=H[Z].
sigma_x=|N_G(x) intersect Z|, zeta_u=|N_G(u) intersect K|, and
r=sum sigma=sum zeta. Only pair labels reach Z: 0<=sigma_x<=6-d_x, so
sigma=0 at d=6, sigma<=1 at d=5 and sigma<=4 at d=2. A zero has six distinct
G neighbours and at most five of them are zeros, so q_u=deg_Q(u)=zeta_u-1>=0
and Q is a simple graph on six vertices. deg_M(x)=7-d_x+sigma_x,
|M|=(32+r)/2 and |Q|=(r-6)/2. Each mixed H triangle has exactly one
same-part edge. For xy in M its zero apices number
6-sigma_x-sigma_y+|N_G(x) intersect N_G(y) intersect Z|;
for uv in Q its core apices number
14-zeta_u-zeta_v+|N_G(u) intersect N_G(v) intersect K|. Therefore

 t(H)=54+11r-sum sigma_x(7-d_x+sigma_x)-sum zeta_u^2+P,
 P=t(M)+t(Q)+sum_M c_Z(xy)+sum_Q c_K(uv)>=0.

Write a for the number of d=5 vertices with sigma=1 and s_1,s_2 for the two
d=2 sigmas. Then r=a+s_1+s_2=6+2|Q| and zeta=q+1, so

 T=t(G)=234-6a+s_1(s_1-4)+s_2(s_2-4)+sum_u q_u^2-P.                (I)

The load-bearing inequality is the edge-sum lemma for Q. Since
sum_u q_u^2=sum_{uv in Q}(q_u+q_v), and q_u+q_v-1<=|Q| counts the distinct Q
edges meeting u or v, sum_u q_u^2<=|Q|(|Q|+1). Since s_i<=4, s_i(s_i-4)<=0
and 2|Q|=a+s_1+s_2-6<=a+2. With P>=0 this gives

 T<=234-6a+e(e+1), e=floor((a+2)/2), 0<=a<=10.

The maximum over a is 236, at a=0 and e=1 only.

Independent complete finite relaxation: a is 0..10, the sorted lows are in
[0,4]^2, and q is the sorted degree sequence of each of the 2^15 labelled
graphs on six vertices (102 sequences), with a+s_1+s_2=6+2|Q|. Every legal
support structure maps to this set, because sorting the lows or the zeros
leaves (I) unchanged. No cross-graph Gale-Ryser condition, realizability of
M, or joint compatibility is assumed; omitting them only enlarges the set.
The exact maximum of (I) at P=0 over the set is 236, uniquely at a=0,
s=(4,4), q=(1,1,0,0,0,0). Both arguments prove T<=236 for the full profile.
Attainment is not asserted: at that argmax both zeros of the Q edge see both
lows, so c_K>=2.

Route B is evaluated separately at every integer 22<=T<=cap. Its frozen
open-wedge K4 floor is ceil((U-(g_max-2)(W-3T))/4), truncated at zero.
U=2322, W=828, g_max=12. The contained-triple K4 cap is
floor(sum d(d+4)/3)=198. S4=max(112,679*K4-231*min(K4,198));
S3=2800*828+11872*(T-22)-30800. The integer union bound is
372228640-63838600+S3-floor(4*S4/7), the ceiling of its rational bound.
The old envelope reproduces the recorded 313395448 at 265. Cap 264 is the
largest cap that reduces the row strictly, and also the largest that reaches
the next competitor 313395344 and the cursor 313394584. The new envelope
peaks at 236 with 313135356. No other row is refined.
"""

from __future__ import annotations

import ast
import hashlib
import json
import resource
import subprocess
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from itertools import combinations, combinations_with_replacement, pairwise, product
from math import comb
from pathlib import Path
from time import process_time
from typing import Any

TASK_ID = "B649_NEW_FRONTIER_OWNER_B_BOUNDED_RESEARCH_R1"
FROZEN_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
FROZEN_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
FROZEN_RESULT = "b649-min-s2-next-owner-core-zero-t256-cert-r1-result.json"
FROZEN_SHA256 = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"
SIX_ROW_RESULT = "b649-min-s2-six-row-existing-s4-family-authority-r1-result.json"
NB_RESULT = "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json"
NB_SHA256 = "609d5f6bf96e8d6454918f747c764e479f88bbb0da94d3934c2969b8f6cc7f0f"
R30_RESULT = "b649-k20-min-s2-current-cursor-dynamic-family-max-r30-result.json"
R32_RESULT = "b649-k20-min-s2-route-b-current-owner-refinement-r32-result.json"
PROFILE_ID = "66555555555522000000"
PROFILE = tuple(map(int, PROFILE_ID))
TIED_PARTNER_ID = "66555555555441000000"
CURSOR_ID = "66544333333333332222"
OLD_CAP, NEW_CAP, S4_BASE = 265, 236, 112
OLD_BOUND, NEXT_BOUND, CURSOR_BOUND = 313_395_448, 313_395_344, 313_394_584
INCUMBENT, FROZEN_FAMILY_BOUND = 313_263_888, 313_398_532
R30_ATTEMPT, NB_INDEX = 3073, 1444
GOODMAN, IDENTITY_CONSTANT, LOW_CAP = 294, 234, 4
ROOT = Path(__file__).resolve().parents[3]
RESULT_DIR = "docs/research/matrix-native-results"
RESULT_PATH = ROOT / RESULT_DIR / "b649-new-frontier-owner-b-bounded-r1-result.json"
EDGES_6 = tuple(combinations(range(6), 2))
FOCUSED_COMMAND = (
    "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3.13 "
    "tests/unit/test_b649_new_frontier_owner_b_bounded_r1.py --write-result"
)
Term = tuple[int, int, int, int, int, int]
Support = tuple[str, str]

# Two legal supports (triples, pairs) from a seeded randomized construction in
# scratch, not a search for extremes. They test identity (I) end to end only.
REALIZATIONS: tuple[Support, ...] = (
    (
        "0.1.5 2.10.11 0.7.8 3.4.9 1.4.6 3.7.11 1.8.9 2.5.6 0.6.10 2.4.7 3.8.10 1.11.13 "
        "5.9.10 0.3.12 5.7.13 0.4.11 6.9.12 1.2.3 6.8.11 1.7.10 4.5.8 0.2.9",
        "15.18 14.17 16.19 17.19 14.16 12.15 17.18 13.16 15.19 14.18 12.19 16.18 13.17 "
        "14.15 13.15 14.19 12.16 6.17 7.18 8.19 10.18 2.17 11.12 3.16 4.14 9.13 5.15",
    ),
    (
        "0.1.11 4.6.10 2.5.7 0.3.9 1.8.9 4.5.11 3.6.7 0.8.10 1.2.10 3.4.8 0.5.6 1.4.7 "
        "2.9.11 2.8.12 0.7.13 1.6.13 3.10.11 5.9.12 6.8.11 0.2.4 1.3.5 7.9.10",
        "14.15 16.19 17.18 15.18 14.17 12.19 13.16 18.19 16.17 14.19 15.16 13.15 14.18 "
        "12.17 15.17 12.18 13.19 14.16 16.18 6.17 7.8 4.19 11.13 12.14 9.15 2.3 5.10",
    ),
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def profile_check(profile: tuple[int, ...]) -> None:
    require(
        len(profile) == 20 and all(type(d) is int and 0 <= d <= 6 for d in profile),
        "illegal degree sequence: twenty integer degrees in 0..6",
    )
    require(sum(profile) == 66, "illegal degree sequence: sum d must be 66")
    require(tuple(sorted(profile, reverse=True)) == profile, "illegal degree sequence: order")
    require(profile == PROFILE, "wrong full profile")
    require(
        Counter(profile) == {6: 2, 5: 10, 2: 2, 0: 6} and sum(d * d for d in profile) == 330,
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


def frozen_json(filename: str, digest: str) -> dict[str, Any]:
    raw = frozen_blob(f"{RESULT_DIR}/{filename}")
    require(hashlib.sha256(raw).hexdigest() == digest, f"supporting source pin: {filename}")
    return json.loads(raw)


def assigned_node(module: str, name: str) -> ast.expr:
    source = frozen_blob(f"src/lottolab/research/{module}.py")
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return node.value
    raise AssertionError(f"source constant missing: {name}")


def literal_constant(module: str, name: str) -> object:
    return ast.literal_eval(assigned_node(module, name))


def nb_cap(profile: tuple[int, ...]) -> int:
    """Only for mechanically recovering the source row's synthetic NB index."""
    g = [6 + d for d in profile]
    wedges = sum(comb(v, 2) for v in g)
    ow = sum(
        comb(v, 2)
        - sum(min(x - 1, v - 1) for x in sorted(g[:i] + g[i + 1 :], reverse=True)[:v]) // 2
        for i, v in enumerate(g)
    )
    return (wedges - ow) // 3


def source_check() -> dict[str, Any]:
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
    require(sealed["FAMILY_BOUND_AFTER"] == FROZEN_FAMILY_BOUND, "frozen family bound mismatch")
    six = frozen_json(SIX_ROW_RESULT, sealed["SIX_ROW_RESULT_SHA256"])
    rows: dict[str, int] = six["RESOLVED_ROW_BOUNDS"]
    require(rows[PROFILE_ID] == OLD_BOUND, "recorded row bound mismatch")
    require(
        PROFILE_ID not in sealed["ROWS_CHANGED_FROM_SIX_ROW"]
        and PROFILE_ID not in sealed["CERTIFICATE_PROFILE_IDS"],
        "target was changed by the frozen seven-row update",
    )
    require(
        sorted(p for p, v in rows.items() if v == OLD_BOUND) == [TIED_PARTNER_ID, PROFILE_ID],
        "tied row set mismatch",
    )
    require(max(v for v in rows.values() if v < OLD_BOUND) == NEXT_BOUND, "next competitor")
    cursor = {"BOUND": CURSOR_BOUND, "ID": CURSOR_ID}
    require(
        six["CURSOR"] == cursor == sealed["PRESERVED_SIX_ROW_STATUS"]["CURSOR"], "cursor mismatch"
    )
    nb = frozen_json(NB_RESULT, NB_SHA256)
    r32 = frozen_json(R32_RESULT, nb["R32_RESULT_SHA256"])
    r30_digest = literal_constant(
        "b649_k20_min_s2_route_b_current_owner_refinement_r32", "R30_SHA256"
    )
    require(type(r30_digest) is str, "R30 digest literal")
    r30 = frozen_json(R30_RESULT, str(r30_digest))
    attempt = r30["GROUP_ATTEMPTS"][R30_ATTEMPT]
    require(
        attempt["ATTEMPT_INDEX"] == R30_ATTEMPT
        and attempt["PROFILE_IDS"] == [PROFILE_ID]
        and attempt["STATUS"] == "INFEASIBLE"
        and attempt["ROUTE"] == "A_EXACT_SUPPORT_UNION_OPEN_WEDGE_REFUTATION"
        and attempt["REFUTED_GRAPH_TRIANGLE_COUNT"] == OLD_CAP + 1
        and attempt["TARGET_TRIANGLE_CAP"] == OLD_CAP
        and attempt["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"] == OLD_CAP
        and attempt["WEDGE_COUNT"] == 828,
        "catalog cap source mismatch",
    )
    pre_nb = [row for row in r32["FINAL_RESOLVED_LEDGER"] if row["PROFILE_ID"] == PROFILE_ID]
    require(
        pre_nb == [{"PROFILE_ID": PROFILE_ID, "CURRENT_BOUND": attempt["TARGET_BOUND"]}],
        "pre-NB ledger row does not cite the R30 cap",
    )
    caps = {"NB": nb_cap(PROFILE), "R18": (828 - 5) // 3, "CATALOG": OLD_CAP}
    require(caps == {"NB": 271, "R18": 274, "CATALOG": 265}, "source cap components")
    require(min(caps.values()) == OLD_CAP, "combined recorded T cap mismatch")
    require(PROFILE.count(0) == 6, "seven-zero S4 selector must not apply")
    constants = {
        ("b649_k20_min_s2_dangerous_core_realizability_r5", "K20_REUSED_S4_LOWER_BOUND"): S4_BASE,
        ("b649_k20_min_s2_next_distinct_plateau_r10", "SEVEN_INACTIVE_TICKET_S4_LOWER_BOUND"): 1680,
        ("b649_k20_min_s2_higher_order_closure_r2", "K20_S1"): 372_228_640,
        ("b649_k20_min_s2_higher_order_closure_r2", "K20_S2"): 63_838_600,
        ("b649_k20_min_s2_realizable_core_class_bound_r4", "K20_S3_WEDGE_COEFFICIENT"): 2_800,
    }
    for (module, name), value in constants.items():
        require(literal_constant(module, name) == value, f"source constant mismatch: {name}")
    weights = assigned_node("b649_k20_min_s2_route_b_current_owner_refinement_r32", "K4_WEIGHTS")
    require(ast.unparse(weights) == "{WITH_TRIPLE: 448, WITHOUT_TRIPLE: 679}", "K4 weights")
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
    # Recover NB_CERTIFICATES[index] without the catalog replay. The original cap is
    # min(NB,R18,catalog) <= this NB-only cap, so every NB-only adoption is an original
    # adoption (Route-B maxima are monotone in cap). Equal counts give equal sets.
    candidates: list[str] = []
    for row in sorted(r32["FINAL_RESOLVED_LEDGER"], key=lambda x: x["PROFILE_ID"], reverse=True):
        p = tuple(map(int, row["PROFILE_ID"]))
        base = 1680 if p.count(0) == 7 else S4_BASE
        bound = max(t[1] for t in route_terms(p, nb_cap(p), base))
        if bound < row["CURRENT_BOUND"]:
            candidates.append(row["PROFILE_ID"])
    require(len(candidates) == nb["ADOPTED_COUNT"] == 1790, "source adoption set incomplete")
    require(candidates.index(PROFILE_ID) == NB_INDEX, "synthetic source row index mismatch")
    old = route_terms(PROFILE, OLD_CAP, S4_BASE)
    require(max(t[1] for t in old) == OLD_BOUND < attempt["TARGET_BOUND"], "old row envelope")
    return {
        "FROZEN_HEAD": "MATCH",
        "FROZEN_TREE": "MATCH",
        "FROZEN_RESULT_SHA256": "MATCH",
        "HEAD": head,
        "TREE": tree,
        "RESULT_SHA256": FROZEN_SHA256,
        "FROZEN_FAMILY_BOUND": FROZEN_FAMILY_BOUND,
        "SOURCE_T_CAP": OLD_CAP,
        "SOURCE_S4_BASE": S4_BASE,
        "SOURCE_ROW_BOUND": OLD_BOUND,
        "SOURCE_LOCATOR": f"{NB_RESULT}:NB_CERTIFICATES[{NB_INDEX}]",
        "SOURCE_INDEX_RECOVERY": "NB-only candidate adoptions subset original; equal count 1790",
        "SOURCE_CAP_COMPONENTS": caps,
        "CATALOG_CAP_LOCATOR": (
            f"{R30_RESULT}:GROUP_ATTEMPTS[{R30_ATTEMPT}] (CP_SAT INFEASIBLE at T={OLD_CAP + 1})"
        ),
        "PRE_NB_BOUND": attempt["TARGET_BOUND"],
        "RECORDED_BOUND_LOCATOR": (
            f"{SIX_ROW_RESULT}:RESOLVED_ROW_BOUNDS[{PROFILE_ID}]; "
            "unchanged by frozen seven-row result"
        ),
        "TIED_ROW_IDS": [TIED_PARTNER_ID, PROFILE_ID],
        "NEXT_COMPETITOR_BOUND": NEXT_BOUND,
        "CURSOR": cursor,
        "OLD_ENVELOPE": max(old, key=lambda t: t[1]),
    }


def graph_degrees(mask: int) -> tuple[int, ...]:
    require(type(mask) is int and 0 <= mask < 1 << len(EDGES_6), "graph mask outside domain")
    degrees = [0] * 6
    for i, (u, v) in enumerate(EDGES_6):
        if mask >> i & 1:
            degrees[u] += 1
            degrees[v] += 1
    return tuple(degrees)


@cache
def zero_domain() -> frozenset[tuple[int, ...]]:
    """Sorted degree sequences of all 2^15 labelled graphs Q=H[Z] on six vertices."""
    return frozenset(tuple(sorted(graph_degrees(mask))) for mask in range(1 << len(EDGES_6)))


@dataclass(frozen=True)
class State:
    a: int
    low: tuple[int, ...]
    q: tuple[int, ...]


def validate_state(s: State, *, low_cap: int = LOW_CAP, require_graph: bool = True) -> None:
    require(type(s.a) is int and 0 <= s.a <= 10, "d5 cross range")
    require(
        len(s.low) == 2
        and all(type(x) is int and 0 <= x <= low_cap for x in s.low)
        and tuple(sorted(s.low)) == s.low,
        "low cross range or symmetry",
    )
    require(
        len(s.q) == 6
        and all(type(x) is int and 0 <= x <= 5 for x in s.q)
        and tuple(sorted(s.q)) == s.q,
        "zero degree range or symmetry",
    )
    require(sum(s.q) % 2 == 0, "zero degree parity")
    require(not require_graph or s.q in zero_domain(), "zero graph not graphical")
    require(s.a + sum(s.low) == 6 + sum(s.q), "cross sums unequal")


def objective(s: State, constant: int = IDENTITY_CONSTANT) -> int:
    """Identity (I) with P=0."""
    return constant - 6 * s.a + sum(x * (x - 4) for x in s.low) + sum(x * x for x in s.q)


def generic_objective(s: State, goodman: int = GOODMAN) -> int:
    """Goodman minus the bare mixed-triangle count, from per-vertex data only."""
    sigma = (0, 0) + (1,) * s.a + (0,) * (10 - s.a) + s.low
    h = tuple(7 - d + x for d, x in zip(PROFILE[:14], sigma, strict=True))
    zeta = tuple(x + 1 for x in s.q)
    require(sum(h) % 2 == sum(s.q) % 2 == 0, "split edge parity")
    return (
        goodman
        - 6 * (sum(h) // 2)
        - 14 * (sum(s.q) // 2)
        + sum(x * y for x, y in zip(sigma, h, strict=True))
        + sum(x * y for x, y in zip(zeta, s.q, strict=True))
    )


def analytic_bound(a: int) -> int:
    e = (a + 2) // 2
    return IDENTITY_CONSTANT - 6 * a + e * (e + 1)


def relaxation(
    *, low_cap: int = LOW_CAP, require_graph: bool = True, constant: int = IDENTITY_CONSTANT
) -> dict[str, Any]:
    """Exact maximum of (I) at P=0 over a proved superset; no realizability claim."""
    domain = (
        sorted(zero_domain())
        if require_graph
        else [q for q in combinations_with_replacement(range(6), 6) if sum(q) % 2 == 0]
    )
    count, peak = 0, -1
    argmax: list[State] = []
    histogram: Counter[int] = Counter()
    for a, low, q in product(
        range(11), combinations_with_replacement(range(low_cap + 1), 2), domain
    ):
        if a + sum(low) != 6 + sum(q):
            continue
        s = State(a, low, q)
        validate_state(s, low_cap=low_cap, require_graph=require_graph)
        value = objective(s, constant)
        shift = constant - IDENTITY_CONSTANT
        require(value - shift == generic_objective(s), "mixed-triangle identity")
        if low_cap <= LOW_CAP and require_graph:
            require(value - shift <= analytic_bound(a), "analytic chain")
        count += 1
        histogram[value] += 1
        if value > peak:
            peak, argmax = value, [s]
        elif value == peak:
            argmax.append(s)
    require(count > 0 and bool(argmax), "empty relaxation cannot certify")
    return {
        "STATE_COUNT": count,
        "EXACT_MAXIMUM": peak,
        "ARGMAX": [vars(s) for s in argmax],
        "ZERO_LABELLED_GRAPHS": 1 << len(EDGES_6),
        "ZERO_DEGREE_SIGNATURES": len(domain),
        "HISTOGRAM": dict(sorted(histogram.items())),
        "ATTAINMENT": "NOT_ASSERTED",
    }


def degree_square_lemma() -> dict[str, int]:
    """sum deg^2 <= e(e+1) on every labelled graph on six vertices (proved generally)."""
    equality = 0
    for mask in range(1 << len(EDGES_6)):
        degrees, edges = graph_degrees(mask), mask.bit_count()
        require(sum(d * d for d in degrees) <= edges * (edges + 1), "degree-square lemma")
        equality += sum(d * d for d in degrees) == edges * (edges + 1)
    return {"GRAPHS_CHECKED": 1 << len(EDGES_6), "EQUALITY_GRAPHS": equality}


def analytic_certificate() -> dict[str, Any]:
    table = [(a, (a + 2) // 2, analytic_bound(a)) for a in range(11)]
    peak = max(row[2] for row in table)
    require(peak == NEW_CAP and [r[0] for r in table if r[2] == peak] == [0], "analytic cap")
    return {
        "CHAIN": "T<=234-6a+sum s(s-4)+sum q^2<=234-6a+|Q|(|Q|+1)<=234-6a+e(e+1)<=236",
        "E_MAX": "e=floor((a+2)/2) from 2|Q|=a+s_1+s_2-6<=a+2",
        "PER_A_BOUND": table,
        "MAXIMUM": peak,
        "ARGMAX_A": 0,
        "DEGREE_SQUARE_LEMMA": degree_square_lemma(),
    }


def realization_check(support: Support) -> dict[str, Any]:
    """Legal support -> exact T, state, and four P summands; asserts (I) and the cap."""
    triples, pairs = ([tuple(map(int, b.split("."))) for b in part.split()] for part in support)
    require(
        len(triples) == 22
        and len(pairs) == 27
        and all(len(b) == 3 for b in triples)
        and all(len(b) == 2 for b in pairs),
        "support counts",
    )
    blocks = [tuple(sorted(b)) for b in (*triples, *pairs)]
    ticket_pairs = [p for b in blocks for p in combinations(b, 2)]
    require(len(ticket_pairs) == len(set(ticket_pairs)) == 93, "support linearity")
    require(
        [sum(v in b for b in triples) for v in range(20)] == list(PROFILE)
        and all(sum(v in b for b in blocks) == 6 for v in range(20)),
        "support profile",
    )
    adj = [{w for p in ticket_pairs if v in p for w in p if w != v} for v in range(20)]
    core, zero = set(range(14)), set(range(14, 20))

    def triangles(vertices: set[int], edge: Callable[[int, int], bool]) -> int:
        return sum(
            edge(x, y) and edge(x, z) and edge(y, z)
            for x, y, z in combinations(sorted(vertices), 3)
        )

    t = triangles(set(range(20)), lambda x, y: y in adj[x])
    sigma = [len(adj[x] & zero) for x in sorted(core)]
    m = [(x, y) for x, y in combinations(sorted(core), 2) if y not in adj[x]]
    q = [(u, v) for u, v in combinations(sorted(zero), 2) if v not in adj[u]]
    terms = (
        triangles(core, lambda x, y: y not in adj[x]),
        triangles(zero, lambda x, y: y not in adj[x]),
        sum(len(adj[x] & adj[y] & zero) for x, y in m),
        sum(len(adj[u] & adj[v] & core) for u, v in q),
    )
    require(all(sigma[i] <= 6 - PROFILE[i] for i in range(14)), "pair-label cross cap")
    s = State(
        sum(sigma[2:12]),
        tuple(sorted(sigma[12:])),
        tuple(sorted(sum(u in e for e in q) for u in sorted(zero))),
    )
    validate_state(s)
    require(t == objective(s) - sum(terms), "identity (I) on a legal support")
    require(t <= NEW_CAP, "legal support exceeds proved cap")
    return {"T": t, "STATE": vars(s), "F": objective(s), "P_TERMS": terms}


def route_terms(profile: tuple[int, ...], cap: int, base: int) -> list[Term]:
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
    terms: list[Term] = []
    for t in range(22, cap + 1):
        excess = u - (max(g) - 2) * (w - 3 * t)
        k4 = max(0, -(-excess // 4))
        contained = min(k4, a_max)
        s4 = max(base, 679 * k4 - 231 * contained)
        s3 = 2800 * w + 11872 * (t - 22) - 30800
        bound = 372_228_640 - 63_838_600 + s3 - 4 * s4 // 7
        terms.append((t, bound, k4, contained, s4, s3))
    return terms


def check_terms(terms: list[Term], cap: int) -> None:
    require([t[0] for t in terms] == list(range(22, cap + 1)), "incomplete integer T domain")
    for t, bound, k4, contained, s4, s3 in terms:
        # Fraction.__ceil__ is independent of the integer division implementation.
        k4_exact = max(0, Fraction(2322 - 10 * (828 - 3 * t), 4).__ceil__())
        a_exact = Fraction(330 + 4 * 66, 3).__floor__()
        c_exact = min(k4_exact, a_exact)
        s4_exact = max(S4_BASE, 448 * c_exact + 679 * (k4_exact - c_exact))
        s3_exact = 2800 * 828 + 11872 * (t - 22) - 30800
        rational = Fraction(372_228_640 - 63_838_600 + s3_exact) - Fraction(4 * s4_exact, 7)
        require(
            (k4, contained, s4, s3) == (k4_exact, c_exact, s4_exact, s3_exact)
            and bound == rational.__ceil__()
            and 0 <= bound - rational < 1,
            f"Route-B rounding/arithmetic mismatch at T={t}",
        )


def rounding_check(terms: list[Term]) -> dict[str, Any]:
    excess = {t: 2322 - 10 * (828 - 3 * t) for t, *_ in terms}
    strict = [t for t, e in excess.items() if e > 0 and e % 4]
    require(all(4 * x[4] % 7 == 0 for x in terms), "S4 credit is not an exact integer")
    require((330 + 4 * 66) % 3 == 0, "A_MAX is not an exact integer")
    return {
        "STATUS": "PASS_EXACT_RATIONAL_ALL_T",
        "K4_CEILING_STRICT_T_COUNT": len(strict),
        "K4_CEILING_STRICT_T_RANGE": [min(strict), max(strict)],
        "S4_CREDIT": "exact: 7 divides 112, 679 and 231, so floor(4*S4/7)=4*S4/7",
        "A_MAX": "exact: 594/3=198",
        "BOUND": "integer bound equals ceil(rational bound) at every T in 22..265",
    }


def largest_cap(terms: list[Term], limit: int, *, strict: bool) -> int:
    """Largest cap whose all-T envelope stays below (strict) or at most the limit."""
    best, running = 21, -1
    for t, bound, *_ in terms:
        running = max(running, bound)
        if running < limit or (not strict and running == limit):
            best = t
    return best


def negative_cases() -> dict[str, Any]:
    wide = relaxation(low_cap=6)
    loose = relaxation(require_graph=False)
    wrong = relaxation(constant=GOODMAN + 4 - 60)
    return {
        "OMIT_LOW_PAIR_LABEL_CAP": {
            "PREMISE": "sigma<=6-d at d=2 replaced by sigma<=|Z|=6",
            "BOUND": wide["EXACT_MAXIMUM"],
            "ARGMAX": wide["ARGMAX"],
        },
        "OMIT_ZERO_GRAPHICALITY": {
            "PREMISE": "q only even-sum in 0..5, not a graph degree sequence",
            "BOUND": loose["EXACT_MAXIMUM"],
            "ARGMAX": loose["ARGMAX"],
        },
        "WRONG_GOODMAN_298": {
            "PREMISE": "Goodman constant 298 (another profile) instead of 294",
            "BOUND": wrong["EXACT_MAXIMUM"],
        },
        "INTERPRETATION": (
            "Relaxation maxima without one premise; not legal-support counterexamples"
        ),
    }


def compute_result() -> dict[str, Any]:
    profile_check(PROFILE)
    source = source_check()
    g = [6 + d for d in PROFILE]
    goodman = Fraction(comb(20, 3)) - Fraction(sum(v * (19 - v) for v in g), 2)
    phi = comb(20, 3) - 18 * 97 + sum(comb(13 - d, 2) for d in PROFILE)
    require(phi == goodman == GOODMAN and sum(g) // 2 == 93, "Goodman or edge identity")
    require(GOODMAN - 54 - 6 == IDENTITY_CONSTANT, "identity constant 294-54-6")
    finite = relaxation()
    require(finite["EXACT_MAXIMUM"] == NEW_CAP, "full relaxation does not prove requested cap")
    analytic = analytic_certificate()
    old = route_terms(PROFILE, OLD_CAP, S4_BASE)
    new = route_terms(PROFILE, finite["EXACT_MAXIMUM"], S4_BASE)
    check_terms(old, OLD_CAP)
    check_terms(new, NEW_CAP)
    require(all(x[1] < y[1] for x, y in pairwise(old)), "old envelope not increasing")
    peak = max(new, key=lambda t: t[1])
    require(
        max(t[1] for t in old) == OLD_BOUND and new == old[: len(new)], "old row envelope mismatch"
    )
    require(peak[1] < OLD_BOUND and peak[1] <= NEXT_BOUND, "strict owner improvement missing")
    thresholds = {
        "STRICT_REDUCTION_THRESHOLD": largest_cap(old, OLD_BOUND, strict=True),
        "NEXT_COMPETITOR_THRESHOLD": largest_cap(old, NEXT_BOUND, strict=False),
        "CURSOR_THRESHOLD": largest_cap(old, CURSOR_BOUND, strict=False),
        "INCUMBENT_CLOSURE_THRESHOLD": largest_cap(old, INCUMBENT, strict=False),
    }
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "PASS_FULL_PROFILE_SELF_CHECK_ONLY",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "PUBLICATION": "LOCAL_COMMIT_ONLY",
        "SOURCE": source,
        "PROFILE_ID": PROFILE_ID,
        "DEGREE_PROFILE": "6^2,5^10,2^2,0^6",
        "DEGREE_SUM": 66,
        "DEGREE_SQUARE_SUM": 330,
        "SUPPORT_MODEL": {"TRIPLE_SUPPORTS": 22, "PAIR_SUPPORTS": 27, "PAIR_OVERLAP_MAX": 1},
        "PROOF_SCOPE": "FULL_PROFILE",
        "CORE_VERTICES": 14,
        "ZERO_VERTICES": 6,
        "GRAPH_EDGES": 93,
        "COMPLEMENT_EDGES": 97,
        "GOODMAN_CONSTANT": phi,
        "PROOF": __doc__,
        "EXACT_TRIANGLE_IDENTITY": (
            "T=294-t(H), t(H)=54+11r-sum sigma(7-d+sigma)-sum zeta^2+P; "
            "T=234-6a+s1(s1-4)+s2(s2-4)+sum_Z deg_Q^2-P"
        ),
        "SUPPORT_PREMISES": [
            "Exact full profile; linear 22-triple/27-pair support model; deg_G=6+d",
            "Only pair labels reach Z: 0<=sigma<=6-d (0 at d=6, <=1 at d=5, <=4 at d=2)",
            "Zeros have six distinct G neighbours: Q=H[Z] simple, deg_Q=zeta-1 in 0..5",
            "Cross sums equal: a+s1+s2=sum zeta=6+2|Q|",
        ],
        "NONNEGATIVE_REMAINDER": "P=t(M)+t(Q)+sum_M c_Z+sum_Q c_K; four nonnegative cardinalities",
        "LOAD_BEARING_INEQUALITY": (
            "sum_u deg_Q(u)^2<=|Q|(|Q|+1) (edge-sum lemma), with P>=0 and s(s-4)<=0"
        ),
        "LOAD_BEARING_PREMISES": [
            "Exact identity (I) with P>=0",
            "Low pair-label cap s<=4; omitting it gives 270>264",
            "Edge-sum lemma; or, independently, exhaustive six-vertex zero-graph domain",
        ],
        "ANALYTIC_CERTIFICATE": analytic,
        "RELAXATION_DOMAIN": (
            "a in 0..10; sorted lows in [0,4]^2; q=sorted degrees of all 2^15 labelled "
            "six-vertex graphs; a+s1+s2=6+2|Q|"
        ),
        "RELAXATION_COMPLETENESS": (
            "Every legal support maps to an enumerated state; omitted compatibility "
            "(cross Gale-Ryser, M realizability) only enlarges the domain"
        ),
        "RELAXATION": finite,
        "PROVED_T_CAP": NEW_CAP,
        "PROVED_T_CAP_MEANING": (
            "Triangle cap for every legal support of the profile; attainment not asserted"
        ),
        "REALIZATION_IDENTITY_CHECKS": [realization_check(s) for s in REALIZATIONS],
        "NEGATIVE_CASES": negative_cases(),
        "COUNTEREXAMPLE_STATUS": (
            "NONE: no relaxation state exceeds 236; seeded legal supports satisfy (I)"
        ),
        "UNPROVED_ASSUMPTIONS": [],
        **thresholds,
        "OLD_BOUND": OLD_BOUND,
        "NEW_ADMISSIBLE_BOUND": peak[1],
        "OWNER_BOUND_DELTA": peak[1] - OLD_BOUND,
        "NEXT_COMPETING_BOUND": NEXT_BOUND,
        "BELOW_NEXT_COMPETITOR_313395344": peak[1] <= NEXT_BOUND,
        "CURSOR_BOUND": CURSOR_BOUND,
        "BELOW_CURSOR": peak[1] <= CURSOR_BOUND,
        "INCUMBENT": INCUMBENT,
        "ROW_BOUND_AT_OR_BELOW_INCUMBENT": peak[1] <= INCUMBENT,
        "ROUTE_B_INTEGER_RECOUNT": "PASS",
        "EXACT_RATIONAL_CROSSCHECK": "PASS_ALL_T_22_TO_265",
        "ROUNDING_CHECK": rounding_check(old),
        "T_TERM_COUNT": len(new),
        "ARGMAX_TERM": peak,
        "TERM_COLUMNS": ["T", "BOUND", "K4", "CONTAINED", "S4", "S3"],
        "ALL_T_TERMS": new,
        "OLD_ARGMAX_TERM": max(old, key=lambda t: t[1]),
        "WEDGES": 828,
        "SUM_GRAPH_DEGREE_CHOOSE_3": 2322,
        "A_MAX": 198,
        "FAMILY_BOUND_GAIN_CLAIMED": 0,
        "FAMILY_NOTE": (
            "Tied row 66555555555441000000 keeps 313395448 in the frozen ledger; "
            "no family update is made here"
        ),
        "NEW_WINNING_OUTCOMES": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "FOCUSED_TEST_COMMAND": FOCUSED_COMMAND,
        "HEAVY_SOLVER_STARTED": "NO",
        "CPU_PROCESS_COUNT": 1,
        "CPU_PROCESS_COUNT_MEANING": "Maximum simultaneous CPU-bound task processes",
        "PRELIMINARY_CPU_ACCOUNTING": (
            "Sequential, one process at a time: seeded realization construction stopped at "
            "20 s process CPU (RLIMIT 40 s); relaxation/ablation prototypes under 5 s each; "
            "9 single-mutant focused-test runs of about 2 s each (all mutants killed)"
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


def write_result(result: dict[str, Any]) -> str:
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
    print(json.dumps({"NEW_ADMISSIBLE_BOUND": result["NEW_ADMISSIBLE_BOUND"]}))
