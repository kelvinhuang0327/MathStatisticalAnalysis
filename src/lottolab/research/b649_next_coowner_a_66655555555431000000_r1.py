"""Full-profile T<=248 certificate for 66655555555431000000; no family integration.

Model. There are 20 tickets of capacity six, 22 triple supports and 27 pair
supports. Pair-linearity means every ticket pair occurs in at most one support.
Consequently the overlap graph G is simple, has 93 edges and deg_G(v)=6+d_v.
Its 22 support triangles are distinct, so 22<=T=t(G). The profile is exactly
d=(6^3,5^8,4,3,1,0^6), with sum d=66 and sum d^2=334.

Goodman. For H=complement(G), deg_H=13-d and |E(H)|=97. Counting mixed
vertex triples gives t(G)+t(H)=C(20,3)-sum deg_G*deg_H/2=296.
Independently, inclusion-exclusion gives C(20,3)-18*97+sum C(13-d,2)=296.

Split. K={d>0}, |K|=14, and Z={d=0}, |Z|=6. Let sigma_x=|N_G(x)&Z|,
zeta_u=|N_G(u)&K|, and r=sum sigma=sum zeta. Triples lie entirely in K;
only the 6-d_x pair labels can reach Z, so 0<=sigma_x<=6-d_x. Each zero
has degree six but only five possible neighbours in Z: 1<=zeta_u<=6.
For M=H[K], MZ=H[Z], deg_M(x)=7-d_x+sigma_x and deg_MZ(u)=zeta_u-1.
Thus |M|=16+r/2, |MZ|=(r-6)/2; in particular 6<=r<=18 and r is even.

Exact remainder. A mixed H triangle has one same-part edge. The number of
Z apices above xy in M is 6-sigma_x-sigma_y+c_Z(xy), where c_Z counts
common G-neighbours in Z. The K-apex formula above uw in MZ is analogous.
Therefore t(H)=6|M|+14|MZ|-sum sigma*(7-d+sigma)-sum zeta*(zeta-1)+P,
where P=t(M)+t(MZ)+sum_M c_Z+sum_MZ c_K >= 0 is a sum of cardinalities.
Substitution gives the exact identity
 T=F-P, F=242-11r+sum sigma*(7-d+sigma)+sum zeta^2.

Finite certificate. At d=6, sigma=0. The eight d=5 coordinates are binary;
let a be their sum. Let q,b,c denote sigma at d=4,3,1 respectively.
Then a in 0..8, q in 0..2, b in 0..3, c in 0..5, r=a+q+b+c, and
 F=242-11r+3a+q(3+q)+b(4+b)+c(6+c)+sum zeta^2.
Enumerate every such tuple and every sorted six-tuple zeta in 1..6, keeping
equal sums and even r. Every legal realization projects into this domain:
aggregation loses only permutations of binary d=5 coordinates, sorting loses
only zero-vertex names, and no graphicality or support-extension restriction
is imposed. The 1,798 states are consequently a complete relaxation superset.
Their maximum F is 248, at (a,q,b,c,zeta)=(0,2,3,5,(1,1,1,1,1,5)). Thus
T=F-P<=248 for the FULL PROFILE. This relaxed maximizer is not a realizability
claim (its MZ degree sequence is non-graphical). We conservatively retain 248;
the exact profile maximum is not established here.
As an independent coarser check, zeta^2<=7*zeta-6 gives
 F<=206+sum sigma*(sigma+3-d)<=206+2+9+35=252<263.

Arithmetic. Every T=22..264 is checked against the frozen R32 engine using
independent integer and Fraction arithmetic. W=830, sum C(g,3)=2339,
g_max=12, A_MAX=floor(598/3)=199. K4>=max(0,ceil((30T-5961)/4));
S4>=max(112,448*min(K4,199)+679*(K4-min(K4,199))). The S3 expression is
2800W+11872(T-22)-30800. The union bound uses floor(4*S4/7), equivalently
the ceiling of S1-S2+S3-4*S4/7. Cap 264 reproduces 313392412, cap 263
gives 313383256, and cap 248 gives 313249020. All maxima are at their caps.

Authority. The frozen seven-row result and its own six-row ledger loader are
replayed without solving; the sealed seventh update is applied only to rebuild
the frozen ledger and its digests. The target Row is retained unchanged.
R30 attempt 3741 supplies the inherited cap 264; it is read, never re-solved.
The new certificate neither depends on that cap for T<=248 nor changes any
ledger, cursor, family result, production state or remote. SELF_CHECK_ONLY.
"""

from __future__ import annotations

import json
import resource
from collections.abc import Iterator, Sequence
from dataclasses import asdict
from fractions import Fraction
from itertools import combinations, combinations_with_replacement, product
from math import comb
from time import process_time

from . import b649_min_s2_next_owner_core_zero_t256_cert_r1 as frozen

TASK_ID = "B649_NEXT_COOWNER_A_66655555555431000000_R1"
BASE_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
BASE_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
FROZEN_RESULT_SHA256 = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"
PROFILE_ID = "66655555555431000000"
PROFILE = tuple(map(int, PROFILE_ID))
CORE = tuple(d for d in PROFILE if d)
PROVED_CAP = 248
S4_BASE = 112
OLD_BOUND = 313_392_412
NEXT_COMPETITOR = 313_392_308
RESULT_STEM = "b649-next-coowner-a-66655555555431000000-r1"
RESULT_PATH = frozen.ROOT / frozen.two.RESULT_DIRECTORY / f"{RESULT_STEM}-result.json"
State = tuple[int, int, int, int, tuple[int, ...]]
Support = tuple[int, ...]
Term = tuple[int, int, int, int, int, int]
require = frozen.require


def raw_f(core: Sequence[int], sigma: Sequence[int], zeta: Sequence[int]) -> int:
    """Exact F on balanced cross degrees; no rounding or omitted remainder terms."""
    return (
        242
        - 11 * sum(sigma)
        + sum(s * (7 - d + s) for d, s in zip(core, sigma, strict=True))
        + sum(v * v for v in zeta)
    )


def objective(state: State) -> int:
    a, q, b, c, zeta = state
    return (
        242
        - 11 * (a + q + b + c)
        + 3 * a
        + q * (3 + q)
        + b * (4 + b)
        + c * (6 + c)
        + sum(v * v for v in zeta)
    )


def states(*, zero_min: int = 1, balanced: bool = True, even: bool = True) -> Iterator[State]:
    """Full Cartesian domain, modulo precisely the two proved permutation symmetries."""
    by_sum: dict[int, list[tuple[int, ...]]] = {}
    for zeta in combinations_with_replacement(range(zero_min, 7), 6):
        by_sum.setdefault(sum(zeta), []).append(zeta)
    all_zeros = [z for group in by_sum.values() for z in group]
    for a, q, b, c in product(range(9), range(3), range(4), range(6)):
        r = a + q + b + c
        if even and r % 2:
            continue
        for zeta in by_sum.get(r, []) if balanced else all_zeros:
            yield a, q, b, c, zeta


def project(degrees: Sequence[int], sigma: Sequence[int], zeta: Sequence[int]) -> State:
    """Check every premise used to map a legal structure to the finite relaxation."""
    require(tuple(sorted(degrees, reverse=True)) == PROFILE, "wrong profile")
    core = [d for d in degrees if d]
    require(len(sigma) == 14 and len(zeta) == 6, "wrong cross-degree dimensions")
    require(all(type(v) is int for v in (*sigma, *zeta)), "noninteger cross degree")
    require(
        all(0 <= s <= 6 - d for d, s in zip(core, sigma, strict=True)),
        "support capacity fails",
    )
    require(all(1 <= v <= 6 for v in zeta), "zero cross-degree range fails")
    r = sum(sigma)
    require(r == sum(zeta), "cross-edge balance fails")
    require(r % 2 == 0, "zero-part handshake parity fails")
    a, q, b, c = (sum(s for d, s in zip(core, sigma, strict=True) if d == t) for t in (5, 4, 3, 1))
    state = a, q, b, c, tuple(sorted(zeta))
    require(objective(state) == raw_f(core, sigma, zeta), "aggregation loses a term")
    return state


def theorem() -> dict[str, object]:
    """Analytic identities plus a complete, exact, finite relaxation certificate."""
    g, h = [6 + d for d in PROFILE], [13 - d for d in PROFILE]
    goodman = Fraction(comb(20, 3)) - Fraction(sum(x * y for x, y in zip(g, h, strict=True)), 2)
    inclusion = comb(20, 3) - 18 * 97 + sum(comb(v, 2) for v in h)
    require(
        len(CORE) == 14
        and PROFILE.count(0) == 6
        and sum(PROFILE) == 66
        and sum(d * d for d in PROFILE) == 334
        and sum(g) == 186
        and sum(h) == 194
        and goodman == inclusion == 296
        and sum(7 - d for d in CORE) == 32,
        "profile or Goodman premises fail",
    )
    # Both sides are separable quadratics; 0, e_i, 2e_i determine all coefficients.
    for sigma, zeta in frozen.three.identity_points(14, 6):
        generic = frozen.three.split_objective(PROFILE, sigma, zeta)
        require(
            generic == raw_f(CORE, sigma, zeta) + 8 * (sum(sigma) - sum(zeta)),
            "independent split polynomial fails",
        )
    table: list[tuple[State, int]] = []
    for state in states():
        a, q, b, c, zeta = state
        sigma = (0,) * 3 + (1,) * a + (0,) * (8 - a) + (q, b, c)
        require(project(PROFILE, sigma, zeta) == state, "state projection fails")
        require(
            frozen.three.split_objective(PROFILE, sigma, zeta) == objective(state),
            "generic objective disagrees on a legal relaxed state",
        )
        table.append((state, objective(state)))
    maximum = max(v for _, v in table)
    argmax = [s for s, v in table if v == maximum]
    require(len(table) == 1798 and maximum == PROVED_CAP == 248, "T248 certificate fails")
    require(argmax == [(0, 2, 3, 5, (1, 1, 1, 1, 1, 5))], "relaxed equality set changed")
    core_max = sum(max(s * (s + 3 - d) for s in range(7 - d)) for d in CORE)
    require(
        all(v * v <= 7 * v - 6 for v in range(1, 7)) and 206 + core_max == 252,
        "independent analytic T252 check fails",
    )
    return {
        "GOODMAN_CONSTANT": int(goodman),
        "G_EDGES": 93,
        "H_EDGES": 97,
        "EXACT_TRIANGLE_IDENTITY": "T=296-t(H)=242-11r+sum sigma(7-d+sigma)+sum zeta^2-P",
        "NONNEGATIVE_REMAINDER": "P=t(M)+t(MZ)+sum_M c_Z+sum_MZ c_K>=0",
        "LOAD_BEARING_PREMISES": [
            "22 linear triple supports, 27 pair supports, six labels per ticket",
            "simple G with degrees 6+d; all triples lie in the 14-vertex core",
            "0<=sigma_x<=6-d_x; 1<=zeta_u<=6",
            "sum sigma=sum zeta=r; r even by 2|E(H[Z])|=r-6",
            "exact mixed-triangle counting and nonnegative cardinality remainder",
        ],
        "PROOF_SCOPE": "FULL_PROFILE",
        "PROVED_T_CAP": maximum,
        "RELAXATION_SUPERSET_COMPLETENESS": "PROVED_BY_PROJECTION_IN_SOURCE_DOCSTRING",
        "RELAXATION_STATE_COUNT": len(table),
        "RELAXATION_TABLE_SHA256": frozen.sha256(frozen.two.render(table)),
        "RELAXATION_ARGMAX": argmax,
        "INDEPENDENT_ANALYTIC_CAP": 252,
        "POLYNOMIAL_IDENTITY_POINTS": 41,
        "COUNTEREXAMPLE_STATUS": "NONE_TO_CAP_248;_RELAXED_MAXIMIZER_NOT_A_REALIZATION",
        "EXACT_PROFILE_MAXIMUM": "UNKNOWN",
        "UNPROVED_ASSUMPTIONS": [],
    }


def witness() -> tuple[tuple[Support, ...], tuple[Support, ...]]:
    """One explicit legal realization, used only for non-vacuity and premise checks."""
    blocks = {
        tuple(sorted((v + s) % 13 for v in base))
        for base in ((0, 1, 4), (0, 2, 7))
        for s in range(13)
    }
    removed = {(0, 1, 4), (0, 2, 7), (3, 5, 10), (3, 9, 11), (0, 9, 10)}
    triples = tuple(sorted((blocks - removed) | {(9, 10, 13)}))
    pairs = (
        (1, 4),
        (0, 2),
        (0, 7),
        (5, 10),
        (3, 9),
        (3, 11),
        *combinations(range(14, 20), 2),
        *((13, v) for v in range(14, 19)),
        (0, 19),
    )
    return triples, pairs


def check_realization(triples: Sequence[Support], pairs: Sequence[Support]) -> dict[str, object]:
    degrees = tuple(sum(v in t for t in triples) for v in range(20))
    frozen.r5.validate_k20_support_realization(triples, pairs, degrees)
    require(tuple(sorted(degrees, reverse=True)) == PROFILE, "wrong profile")
    graph = {(min(x, y), max(x, y)) for s in (*triples, *pairs) for x, y in combinations(s, 2)}
    core, zero = (
        [v for v in range(20) if bool(degrees[v]) == positive] for positive in (True, False)
    )
    seen = frozen.complement_split(core, zero, graph)
    sigma = [frozen.integer(v) for v in frozen.rows(seen["SIGMA"])]
    zeta = [frozen.integer(v) for v in frozen.rows(seen["ZETA"])]
    state = project(degrees, sigma, zeta)
    r, p = sum(sigma), frozen.integer(seen["P"])
    require(
        len(graph) == 93
        and [sum(v in e for e in graph) for v in range(20)] == [6 + d for d in degrees]
        and seen["H_CORE"] == [7 - degrees[v] + s for v, s in zip(core, sigma, strict=True)]
        and seen["A_ZERO"] == [v - 1 for v in zeta]
        and seen["M_EDGES"] == 16 + r // 2
        and seen["MZ_EDGES"] == (r - 6) // 2
        and seen["T_G"] == 296 - frozen.integer(seen["T_H"]) == objective(state) - p
        and p >= 0
        and objective(state) - p <= PROVED_CAP,
        "realization violates a load-bearing identity",
    )
    return {
        "TRIPLES": triples,
        "PAIRS": pairs,
        "DEGREES": degrees,
        "STATE": state,
        "F": objective(state),
        **seen,
    }


def negative_domains() -> dict[str, int]:
    """These strictly exceed 248, demonstrating that the corresponding premises matter."""
    result = {
        "ALLOW_ZERO_ZETA": max(map(objective, states(zero_min=0))),
        "OMIT_EQUAL_SUMS": max(map(objective, states(balanced=False))),
        "OMIT_PARITY": max(map(objective, states(even=False))),
        "ALLOW_P_MINUS_ONE_AT_RELAXED_MAXIMUM": objective((0, 2, 3, 5, (1, 1, 1, 1, 1, 5))) + 1,
    }
    require(all(v > PROVED_CAP for v in result.values()), "negative domain test is vacuous")
    return result


def authority() -> tuple[dict[str, object], frozen.Row]:
    """Use the frozen ledger loader; rebuild its sealed update, never install ours."""
    require(frozen.three.git_tree(BASE_HEAD) == BASE_TREE, "frozen tree mismatch")
    relative = frozen.RESULT_PATH.relative_to(frozen.ROOT).as_posix()
    raw = frozen.two.blob(BASE_HEAD, relative, FROZEN_RESULT_SHA256)
    require(frozen.RESULT_PATH.read_bytes() == raw, "frozen result differs locally")
    sealed = frozen.object_row(json.loads(raw))
    _, before = frozen.six_row_authority()
    update = frozen.object_row(frozen.object_row(sealed["ROW_UPDATE"])["AFTER"])
    ledger = frozen.apply_seventh(
        before,
        frozen.integer(update["bound"]),
        frozen.integer(update["cap"]),
        frozen.text(update["source"]),
    )
    require(
        frozen.two.full_digest(ledger) == sealed["FULL_ROWS_SHA256_AFTER"]
        and frozen.two.bounds_digest(ledger) == sealed["BOUNDS_SHA256_AFTER"],
        "frozen complete ledger mismatch",
    )
    row = ledger[PROFILE_ID]
    require(
        (row.cap, row.s4_base, row.bound) == (264, S4_BASE, OLD_BOUND), "frozen target row changed"
    )
    proof = frozen.r32.r30_proofs()[3741]
    require(
        proof["ATTEMPT_INDEX"] == 3741
        and proof["PROFILE_IDS"] == [PROFILE_ID]
        and proof["STATUS"] == "INFEASIBLE"
        and proof["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"] == 264,
        "R30 inherited cap authority mismatch",
    )
    # Every already imported research dependency must still equal its frozen blob.
    import sys

    provenance: dict[str, str] = {}
    for name, module in sorted(sys.modules.items()):
        if not name.startswith("lottolab.research.") or name == __name__:
            continue
        filename = getattr(module, "__file__", None)
        if filename is None:
            continue
        path = frozen.Path(filename).resolve()
        path_relative = path.relative_to(frozen.ROOT).as_posix()
        blob = frozen.chase.git("show", f"{BASE_HEAD}:{path_relative}")
        require(path.read_bytes() == blob, f"frozen dependency changed: {path_relative}")
        provenance[path_relative] = frozen.sha256(blob)
    inventory = frozen.chase.git(
        "grep",
        "-l",
        PROFILE_ID,
        BASE_HEAD,
        "--",
        "src/lottolab/research",
        "tests/unit",
        "docs/research",
    )
    return {
        "FROZEN_HEAD": BASE_HEAD,
        "FROZEN_TREE": BASE_TREE,
        "FROZEN_HEAD_TREE": "MATCH",
        "FROZEN_RESULT_PATH": relative,
        "FROZEN_RESULT_SHA256": FROZEN_RESULT_SHA256,
        "FROZEN_RESULT_SHA256_CHECK": "MATCH",
        "SOURCE_ROW": asdict(row),
        "SOURCE_T_CAP": row.cap,
        "SOURCE_S4_BASE": row.s4_base,
        "SOURCE_ROW_BOUND": row.bound,
        "SOURCE_PROOF_LOCATOR": row.source,
        "R30_CAP_AUTHORITY": proof,
        "LEDGER_ROWS": len(ledger),
        "FROZEN_LEDGER_SHA256": frozen.two.full_digest(ledger),
        "PRIOR_SAME_PROFILE_INVENTORY": inventory.decode().splitlines(),
        "NOVELTY": "New application of zero lower bound and finite relaxation; prior caps retained",
        "MODULE_PROVENANCE": provenance,
        "FROZEN_LEDGER_MUTATED": False,
    }, row


def route_b(cap: int, s4_base: int) -> tuple[list[Term], int]:
    require(
        frozen.r32.r30.k4_quartet_weights()
        == {"SIX_EDGES_WITH_CONTAINED_TRIPLE": 448, "SIX_EDGES_WITHOUT_CONTAINED_TRIPLE": 679},
        "exact four-ticket DP weights differ",
    )
    terms = frozen.r32.route_b_envelope(PROFILE, cap, s4_base)
    g = [6 + d for d in PROFILE]
    w, choose3 = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g)
    outside = sum(d * (v - 2) for d, v in zip(PROFILE, g, strict=True))
    require(
        (w, choose3, max(g), outside, outside // 3) == (830, 2339, 12, 598, 199),
        "Route-B structural premises differ",
    )
    require([t[0] for t in terms] == list(range(22, cap + 1)), "missing triangle term")
    for t, bound, k4, contained, s4, s3 in terms:
        excess = Fraction(choose3 - (max(g) - 2) * (w - 3 * t), 4)
        ceiling = max(0, -((-excess.numerator) // excess.denominator))
        a = min(ceiling, outside // 3)
        exact_s4 = max(s4_base, 448 * a + 679 * (ceiling - a))
        exact_s3 = 2800 * w + 11872 * (t - 22) - 30800
        credit = 4 * exact_s4 // 7
        exact = 372_228_640 - 63_838_600 + exact_s3 - Fraction(4 * exact_s4, 7)
        exact_ceiling = -((-exact.numerator) // exact.denominator)
        require(
            (k4, contained, s4, s3) == (ceiling, a, exact_s4, exact_s3)
            and bound == 372_228_640 - 63_838_600 + exact_s3 - credit == exact_ceiling
            and 0 <= bound - exact < 1,
            f"Route-B exact rounding fails at T={t}",
        )
    return terms, max(t[1] for t in terms)


def compute_result() -> dict[str, object]:
    source, row = authority()
    certificate = theorem()
    old_terms, old = route_b(row.cap, row.s4_base)
    target_terms, threshold = route_b(263, row.s4_base)
    new_terms, new = route_b(PROVED_CAP, row.s4_base)
    require(
        (old, threshold, new) == (OLD_BOUND, 313_383_256, 313_249_020)
        and target_terms == old_terms[: len(target_terms)]
        and new_terms == old_terms[: len(new_terms)],
        "Route-B recount mismatch",
    )
    peak = max(new_terms, key=lambda t: (t[1], t[0]))
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "FULL_PROFILE_CERTIFICATE_SELF_CHECKED",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "PROOF": __doc__,
        "PROFILE_ID": PROFILE_ID,
        "DEGREE_DISTRIBUTION": "6^3,5^8,4^1,3^1,1^1,0^6",
        **source,
        **certificate,
        "TARGET_T_CAP": 263,
        "OLD_BOUND": old,
        "EXPECTED_BOUND_AT_CAP_263": threshold,
        "NEW_ADMISSIBLE_BOUND": new,
        "OWNER_DELTA": old - new,
        "NEXT_COMPETITOR": NEXT_COMPETITOR,
        "BELOW_NEXT_COMPETITOR": new < NEXT_COMPETITOR,
        "NEGATIVE_CASE_RESULTS": negative_domains(),
        "NONVACUITY_REALIZATION": check_realization(*witness()),
        "ROUTE_B_INTEGER_RECOUNT": "PASS_ALL_T_22_TO_264",
        "EXACT_RATIONAL_CHECK": "PASS",
        "ROUNDING_CHECK": "PASS",
        "ARGMAX_TERM": peak,
        "ALL_T_TERMS_THROUGH_SOURCE_CAP": old_terms,
        "CAP_263_ARGMAX": max(target_terms, key=lambda t: (t[1], t[0])),
        "CERTIFIED_TERM_COUNT": len(new_terms),
        "FAMILY_GAIN_CLAIMED": 0,
        "NEW_WINNING_OUTCOMES": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "HEAVY_SOLVER_STARTED": "NO",
        "SOLVER_CALLS": 0,
        "CPU_PROCESS_COUNT": 1,
        "CPU_LIMIT_SECONDS_PER_RUN": 120,
        "PUSH": "NOT_RUN",
        "MERGE": "NOT_RUN",
        "PRODUCTION_MUTATION": "NONE",
        "FAMILY_INTEGRATION": "NOT_RUN",
    }


def main() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
    start = process_time()
    result = compute_result()
    payload = frozen.two.render(result)
    if RESULT_PATH.exists():
        require(RESULT_PATH.read_bytes() == payload, "existing result differs")
    else:
        with RESULT_PATH.open("xb") as output:
            output.write(payload)
    print(
        json.dumps(
            {
                "RESULT": str(RESULT_PATH),
                "SHA256": frozen.sha256(payload),
                "PROVED_T_CAP": PROVED_CAP,
                "NEW_ADMISSIBLE_BOUND": result["NEW_ADMISSIBLE_BOUND"],
                "CPU_SECONDS": process_time() - start,
            }
        )
    )


if __name__ == "__main__":
    main()
