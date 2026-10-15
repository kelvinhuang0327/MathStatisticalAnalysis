"""Full-profile certificate T <= 255 for 66666555554411100000 (self-check only).

Model. In the frozen minimum-S2 family there are 22 triple labels and 27 pair
labels on 20 tickets, six labels per ticket. Pair-linearity means that no ticket
pair occurs in two supports. The overlap graph G therefore has 93 edges and
degree 6+d_v. Its complement H has 97 edges and degree 13-d_v. For this profile,
sum d=66, sum d^2=340. Inclusion-exclusion on each vertex triple gives
 T=t(G)=C(20,3)-18*97+sum C(13-d_v,2)-t(H)=299-t(H).
Goodman's identity independently gives 1140-sum(6+d_v)(13-d_v)/2=299.

Core-zero split. K={d>0} has 15 vertices and Z has five. Put sigma_x=|N_G(x)&Z|
and zeta_u=|N_G(u)&K|. Triples avoid Z; hence 0<=sigma_x<=6-d_x. Each zero has
six distinct G-neighbours, at most four in Z: 2<=zeta_u<=6. Both sums equal the
cross-edge count r. If M=H[K], N=H[Z], their degrees are h_x=8-d_x+sigma_x and
a_u=zeta_u-2. Thus |M|=(54+r)/2, |N|=(r-10)/2, so r>=10 and r is even.

Exact remainder. A mixed H triangle has one same-part edge. For xy in M its Z
apices number 5-sigma_x-sigma_y+c_Z(xy), where c_Z is the number of common G
neighbours in Z. For uv in N the analogous count is 15-zeta_u-zeta_v+c_K(uv).
Consequently
 t(H)=5|M|+15|N|-sum sigma*h-sum zeta*a+P,
 P=t(M)+t(N)+sum_M c_Z+sum_N c_K >= 0,
 T=F-P,
 F=239+sum_K sigma_x(sigma_x+2-d_x)+sum_Z zeta_u(zeta_u-6).
The constant is 299-5*54/2+15*10/2=239. The alternative expression is
F=239-12r+sum sigma(8-d+sigma)+sum zeta^2, using cross-edge balance.

The three degree-one vertices L have no triple edge between them. Proof: each
of the five degree-six vertices has twelve distinct triple neighbours in K,
only eleven of which can be outside L; hence at least five hub-L shadow edges
are required. If two L vertices shared a triple, those two would each have at
most one hub neighbour, and the third at most two: at most four, a contradiction.
Thus every G edge inside L is a pair label. This uses only linearity, capacity,
and the specified profile; it imposes no unproved realizability condition.

Load-bearing inequality. Write q_i=sigma at the three L vertices, and let E be
the edges of H[L], with degrees l_i. Pair capacity requires 2-l_i<=5-q_i.
For ij in E, their H-neighbour sets outside L (a set of size twelve) intersect
in at least max(0,2+q_i+q_j-l_i-l_j) vertices. Their G-neighbour sets in Z
intersect in at least max(0,q_i+q_j-5). These are disjoint terms of P. Therefore
 P >= p(q,E) = 1_{E=K3} + sum_{ij in E} [
       max(0,2+q_i+q_j-l_i-l_j) + max(0,q_i+q_j-5)].
In particular all three q_i=5 force E=K3 and P>=25+15=40.

Finite superset and completeness. Exhaust all 2^10 simple graphs N on five
labelled zeros, form sorted zeta=2+deg(N), and retain the 31 distinct sequences.
This is a constructive exhaustive graph list, not a graphicality oracle.
Independently exhaust class-sorted sigma: 6 choices for five d=5 coordinates,
6 for two d=4 coordinates, 56 for three d=1 coordinates; d=6 coordinates are
zero. Retain only equal cross-edge sums and even r. Independently exhaust all
eight E masks, retaining only the proved pair-capacity inequality. Every legal
support structure maps to one such case after sorting within equal-d classes
and sorting the zeros: all E masks are present after any relabelling. No core
graphicality, cross graphicality, triple decomposition, or matching restriction
is added. Dropping these restrictions enlarges the set. All 1,755 degree cases
and 6,117 E branches satisfy F-p<=255. This proves T<=255 for the full profile,
and excludes both T=263 and T=264. Relaxation maximizers need not be realizable;
no attainment or global K20 optimum is claimed. No solver is used.

Authority and arithmetic. Reuse the existing complete 4,647-row loader and
recorded updates; do not create a family engine or update a ledger. Match the
frozen complete-row and bound digests, and extract only this row. Its source
cap is 264, S4 base 112, bound 313391920. The existing source improves S4 only
at T264 to 309183, making T263 the old argmax. Recount every integer and rational
Route-B term with the frozen R32 and split evaluators: W=833, U=2370,
A_max=floor((4*66+340)/3)=201, K4=max(0,ceil((2370-10(833-3T))/4)),
S4=max(112,679*K4-231*min(K4,201)), S3=2800*833+11872*(T-22)-30800.
The upper bound is ceil(372228640-63838600+S3-4*S4/7), equivalently subtracting
floor(4*S4/7) from the integer part. All T=22..255 are checked, giving argmax
(T,bound,K4,contained,S4,S3)=(255,313320224,423,201,240786,5067776).
T262 and T263 reproduce 313383152 and 313391920. Only this profile is certified;
family gain and new winning outcomes are zero. Prior Judge statuses are not upgraded.
"""

from __future__ import annotations

import hashlib
import json
import resource
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict
from fractions import Fraction
from functools import lru_cache
from itertools import combinations, combinations_with_replacement, product
from math import comb
from pathlib import Path

from . import b649_min_s2_next_owner_core_zero_t256_cert_r1 as frozen

TASK_ID = "B649_NEXT_RESOLVED_OWNER_66666555554411100000_R1"
PROFILE_ID = "66666555554411100000"
FROZEN_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
FROZEN_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
FROZEN_RESULT_SHA256 = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"
ROOT = Path(__file__).resolve().parents[3]
RESULT_PATH = (
    ROOT
    / "docs/research/matrix-native-results"
    / ("b649-next-resolved-owner-66666555554411100000-r1-result.json")
)
PROFILE = tuple(map(int, PROFILE_ID))
CORE = PROFILE[:15]
LOW_EDGES = tuple(combinations(range(3), 2))
ZERO_EDGES = tuple(combinations(range(5), 2))
PROVED_CAP = 255
Term = tuple[int, int, int, int, int, int]
require, integer, rows, object_row = frozen.require, frozen.integer, frozen.rows, frozen.object_row


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def premises() -> dict[str, object]:
    g = [6 + d for d in PROFILE]
    phi = comb(20, 3) - 18 * 97 + sum(comb(13 - d, 2) for d in PROFILE)
    goodman = Fraction(1140) - Fraction(sum(v * (19 - v) for v in g), 2)
    require(
        Counter(PROFILE) == {6: 5, 5: 5, 4: 2, 1: 3, 0: 5}
        and sum(PROFILE) == 66
        and sum(d * d for d in PROFILE) == 340
        and sum(g) == 186
        and phi == goodman == 299
        and sum(8 - d for d in CORE) == 54
        and phi - Fraction(5 * 54, 2) + Fraction(15 * 10, 2) == 239,
        "profile/complement premises changed",
    )
    require(5 * (12 - 11) > 2 * 1 + 2, "low-low triple obstruction fails")
    require(6 - (5 - 1) == 2, "zeta lower bound fails")
    return {
        "DEGREE_SUM": 66,
        "DEGREE_SQUARE_SUM": 340,
        "CORE_COUNT": 15,
        "ZERO_COUNT": 5,
        "G_EDGES": 93,
        "H_EDGES": 97,
        "GOODMAN_CONSTANT": phi,
        "GOODMAN_RATIONAL": str(goodman),
        "F_CONSTANT": 239,
        "ZETA_GE_2": "VERIFIED",
        "LOW_LOW_TRIPLE": "IMPOSSIBLE_BY_5_GT_4",
        "EXACT_TRIANGLE_IDENTITY": "T=299-t(H)=F-P",
        "NONNEGATIVE_REMAINDER": "P=t(M)+t(N)+sum_M c_Z+sum_N c_K>=0",
        "LOAD_BEARING_PREMISES": [
            "PAIR_LINEARITY",
            "TICKET_CAPACITY_6",
            "22_TRIPLE_27_PAIR_LABELS",
            "EXACT_PROFILE",
            "CROSS_EDGE_BALANCE",
            "EVEN_R_GE_10",
            "ZETA=2+DEG_OF_SIMPLE_GRAPH_ON_5",
            "NO_LOW_LOW_TRIPLE",
            "P_GE_p(q,E)",
        ],
    }


def zero_sequences() -> tuple[tuple[int, ...], ...]:
    """Complete constructive list: every one of the 1,024 labelled zero graphs."""
    sequences: set[tuple[int, ...]] = set()
    for mask in range(1 << len(ZERO_EDGES)):
        degree = [0] * 5
        for index, (u, v) in enumerate(ZERO_EDGES):
            if mask & (1 << index):
                degree[u] += 1
                degree[v] += 1
        sequences.add(tuple(sorted(2 + d for d in degree)))
    return tuple(sorted(sequences))


def low_floor(q: Sequence[int], mask: int, *, capacity: bool = True) -> int | None:
    require(len(q) == 3 and all(type(v) is int and 0 <= v <= 5 for v in q), "q range")
    require(type(mask) is int and 0 <= mask < 8, "low graph mask")
    edges = [e for index, e in enumerate(LOW_EDGES) if mask & (1 << index)]
    degree = [sum(v in e for e in edges) for v in range(3)]
    if capacity and any(2 - degree[i] > 5 - q[i] for i in range(3)):
        return None
    return int(mask == 7) + sum(
        max(0, 2 + q[i] + q[j] - degree[i] - degree[j]) + max(0, q[i] + q[j] - 5) for i, j in edges
    )


def objective(sigma: Sequence[int], zeta: Sequence[int]) -> int:
    require(len(sigma) == 15 and len(zeta) == 5, "split lengths")
    require(
        all(type(s) is int and 0 <= s <= 6 - d for d, s in zip(CORE, sigma, strict=True))
        and all(type(v) is int and 2 <= v <= 6 for v in zeta),
        "cross degree capacity",
    )
    r = sum(sigma)
    require(r == sum(zeta) and r >= 10 and r % 2 == 0, "cross balance/parity")
    f = 239 + sum(s * (s + 2 - d) for s, d in zip(sigma, CORE, strict=True))
    f += sum(v * (v - 6) for v in zeta)
    raw = 239 - 12 * r + sum(s * (8 - d + s) for s, d in zip(sigma, CORE, strict=True))
    raw += sum(v * v for v in zeta)
    require(f == raw, "exact F identity")
    return f


def finite_superset(
    zero: Sequence[tuple[int, ...]] | None = None,
    *,
    capacity: bool = True,
    remainder: bool = True,
) -> dict[str, object]:
    """Only explicit proved filters; zero/capacity/remainder seams support ablation tests."""
    zs = zero_sequences() if zero is None else tuple(sorted(set(zero)))
    by_sum: dict[int, list[tuple[int, ...]]] = {}
    for zeta in zs:
        by_sum.setdefault(sum(zeta), []).append(zeta)
    case_count = branch_count = 0
    peak = raw_peak = -10_000
    maxima: list[dict[str, object]] = []
    histogram: Counter[int] = Counter()
    evidence: list[object] = []
    for a, b, q in product(
        combinations_with_replacement(range(2), 5),
        combinations_with_replacement(range(3), 2),
        combinations_with_replacement(range(6), 3),
    ):
        sigma = (0,) * 5 + a + b + q
        if sum(sigma) % 2:
            continue
        floors = [(m, low_floor(q, m, capacity=capacity)) for m in range(8)]
        valid = [(m, v) for m, v in floors if v is not None]
        if not valid:
            continue
        p = min(v for _, v in valid) if remainder else 0
        for zeta in by_sum.get(sum(sigma), []):
            f = objective(sigma, zeta)
            upper = f - p
            case_count += 1
            branch_count += len(valid)
            raw_peak = max(raw_peak, f)
            histogram[upper] += 1
            evidence.append([sigma, zeta, f, valid, upper])
            item: dict[str, object] = {
                "SIGMA": list(sigma),
                "ZETA": list(zeta),
                "F": f,
                "P_FLOOR": p,
                "UPPER": upper,
                "MINIMIZING_LOW_MASKS": [m for m, v in valid if v == p],
            }
            if upper > peak:
                peak, maxima = upper, [item]
            elif upper == peak:
                maxima.append(item)
    return {
        "ZERO_GRAPH_MASKS": 1024,
        "ZERO_SEQUENCES": [list(z) for z in zs],
        "DEGREE_CASES": case_count,
        "LOW_GRAPH_BRANCHES": branch_count,
        "RAW_F_MAX": raw_peak,
        "MAX_UPPER": peak,
        "MAXIMIZERS": maxima,
        "HISTOGRAM": {str(k): v for k, v in sorted(histogram.items())},
        "COMPLETE_CASES_SHA256": digest(evidence),
    }


@lru_cache(maxsize=1)
def frozen_authority() -> tuple[dict[str, object], frozen.Row, dict[str, object]]:
    """Existing complete-ledger replay, matched against the exact frozen result."""
    require(frozen.three.git_tree(FROZEN_HEAD) == FROZEN_TREE, "frozen tree mismatch")
    path = frozen.RESULT_PATH.relative_to(ROOT).as_posix()
    raw = frozen.chase.git("show", f"{FROZEN_HEAD}:{path}")
    require(
        hashlib.sha256(raw).hexdigest() == FROZEN_RESULT_SHA256
        and frozen.RESULT_PATH.read_bytes() == raw,
        "frozen result mismatch",
    )
    sealed = object_row(json.loads(raw))
    six_result, ledger = frozen.six_row_authority()
    prior_update = object_row(object_row(sealed["ROW_UPDATE"])["AFTER"])
    ledger = frozen.apply_seventh(
        ledger,
        integer(prior_update["bound"]),
        integer(prior_update["cap"]),
        frozen.text(prior_update["source"]),
    )
    require(
        len(ledger) == sealed["LEDGER_ROWS"] == 4647
        and frozen.two.full_digest(ledger) == sealed["FULL_ROWS_SHA256_AFTER"]
        and frozen.two.bounds_digest(ledger) == sealed["BOUNDS_SHA256_AFTER"],
        "complete frozen ledger mismatch",
    )
    row = ledger[PROFILE_ID]
    expected = object_row(object_row(six_result["ROW_UPDATE"])["AFTER"])
    require(json.loads(json.dumps(asdict(row))) == expected, "source row mismatch")
    require((row.cap, row.s4_base, row.bound) == (264, 112, 313_391_920), "row constants")
    provenance: dict[str, str] = {}
    for module in (
        frozen,
        frozen.three,
        frozen.two,
        frozen.six,
        frozen.six.five,
        frozen.six.five.four,
        frozen.chase,
        frozen.split,
        frozen.r32,
        frozen.r5,
    ):
        require(module.__file__ is not None, "missing dependency source")
        source = Path(frozen.text(module.__file__)).resolve()
        relative = source.relative_to(ROOT).as_posix()
        blob = frozen.chase.git("show", f"{FROZEN_HEAD}:{relative}")
        require(source.read_bytes() == blob, "frozen dependency changed")
        provenance[relative] = hashlib.sha256(blob).hexdigest()
    authority: dict[str, object] = {
        "FROZEN_HEAD_TREE": "MATCH",
        "FROZEN_RESULT_SHA256": "MATCH",
        "FROZEN_HEAD": FROZEN_HEAD,
        "FROZEN_TREE": FROZEN_TREE,
        "FROZEN_RESULT_DIGEST": FROZEN_RESULT_SHA256,
        "LEDGER_ROWS": len(ledger),
        "FULL_ROWS_SHA256": sealed["FULL_ROWS_SHA256_AFTER"],
        "BOUNDS_SHA256": sealed["BOUNDS_SHA256_AFTER"],
        "ROW": asdict(row),
        "MODULE_PROVENANCE": provenance,
        "PRIOR_AUTHORITY_JUDGE_STATUS": six_result["AUTHORITY_JUDGE_STATUS"],
        "PRIOR_DONOR_JUDGE_STATUS": six_result["DONOR_JUDGE_STATUS"],
        "PRIOR_SCOPE": "READ_ONLY_EXISTING_T264_S4_CERTIFICATE_NO_STATUS_UPGRADE",
    }
    return authority, row, object_row(six_result["CERTIFICATE_F"])


def route_terms(cap: int, base: int) -> list[Term]:
    terms = frozen.r32.route_b_envelope(PROFILE, cap, base)
    require(terms == frozen.split.route_b_terms(PROFILE, cap, base), "evaluator disagreement")
    g = [6 + d for d in PROFILE]
    w, u = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g)
    a_exact = Fraction(sum(d * (v - 2) for d, v in zip(PROFILE, g, strict=True)), 3)
    a_max = a_exact.numerator // a_exact.denominator
    require((w, u, a_max, max(g)) == (833, 2370, 201, 12), "Route-B premises")
    require([t[0] for t in terms] == list(range(22, cap + 1)), "full envelope domain")
    for t, bound, k4, contained, s4, s3 in terms:
        excess = Fraction(u - (max(g) - 2) * (w - 3 * t), 4)
        ceiling = max(0, -((-excess.numerator) // excess.denominator))
        ca = min(ceiling, a_max)
        s4_exact = max(base, 448 * ca + 679 * (ceiling - ca))
        s3_exact = 2800 * w + 11872 * (t - 22) - 30800
        exact = 372_228_640 - 63_838_600 + s3_exact - Fraction(4 * s4_exact, 7)
        exact_bound = -((-exact.numerator) // exact.denominator)
        require(
            (k4, contained, s4, s3, bound) == (ceiling, ca, s4_exact, s3_exact, exact_bound)
            and 0 <= bound - exact < 1,
            f"Route-B exact rounding at T={t}",
        )
    return terms


def realization(row: frozen.Row) -> dict[str, object]:
    require(row.realization is not None, "source realization missing")
    if row.realization is None:
        raise AssertionError("source realization missing")
    triples, pairs = row.realization
    d = frozen.three.legal_degrees(triples, pairs)
    frozen.r5.validate_k20_support_realization(triples, pairs, d)
    require(tuple(sorted(d, reverse=True)) == PROFILE, "realization wrong profile")
    core, zero = [v for v in range(20) if d[v]], [v for v in range(20) if not d[v]]
    g = {frozen.edge(x, y) for s in (*triples, *pairs) for x, y in combinations(s, 2)}
    seen = frozen.complement_split(core, zero, g)
    sigma = tuple(integer(v) for v in rows(seen["SIGMA"]))
    zeta = tuple(integer(v) for v in rows(seen["ZETA"]))
    sigma_sorted = tuple(
        s
        for _, s in sorted(
            zip((d[v] for v in core), sigma, strict=True), key=lambda pair: (-pair[0], pair[1])
        )
    )
    low = [v for v in core if d[v] == 1]
    q = [len({u for u in zero if frozen.edge(v, u) in g}) for v in low]
    mask = sum(1 << i for i, (u, v) in enumerate(LOW_EDGES) if frozen.edge(low[u], low[v]) not in g)
    p_floor = low_floor(q, mask)
    require(p_floor is not None and integer(seen["P"]) >= p_floor, "observed P floor")
    require(all(len(set(s) & set(low)) <= 1 for s in triples), "low-low triple")
    f = objective(sigma_sorted, zeta)
    require(
        tuple(sorted(zeta)) in zero_sequences()
        and rows(seen["H_CORE"]) == [8 - d[v] + s for v, s in zip(core, sigma, strict=True)]
        and rows(seen["A_ZERO"]) == [z - 2 for z in zeta]
        and integer(seen["T_G"]) == 299 - integer(seen["T_H"]) == f - integer(seen["P"])
        and integer(seen["T_G"]) <= PROVED_CAP,
        "source witness identities",
    )
    return {**seen, "F": f, "LOW_MASK": mask, "LOW_P_FLOOR": p_floor}


def compute_result() -> dict[str, object]:
    premise = premises()
    authority, row, prior = frozen_authority()
    finite = finite_superset()
    require(
        len(zero_sequences()) == 31
        and finite["DEGREE_CASES"] == 1755
        and finite["LOW_GRAPH_BRANCHES"] == 6117
        and finite["MAX_UPPER"] == PROVED_CAP,
        "full finite superset certificate",
    )
    full = route_terms(264, row.s4_base)
    old = [tuple(integer(v) for v in rows(t)) for t in rows(prior["ALL_T_TERMS"])]
    require(
        old[:-1] == full[:-1]
        and old[-1] == (264, 313387988, 490, 201, 309183, 5174624)
        and frozen.chase.r20.bound_from_cap(PROFILE, 264, old[-1][4]) == (old[-1][5], old[-1][1])
        and max(old, key=lambda t: t[1]) == full[-2]
        and full[-2][1] == row.bound,
        "recorded source envelope mismatch",
    )
    new = route_terms(PROVED_CAP, row.s4_base)
    peak = max(new, key=lambda t: t[1])
    require(
        new == old[: len(new)]
        and peak == (255, 313320224, 423, 201, 240786, 5067776)
        and full[-3][1] == 313383152
        and peak[1] < 313391844,
        "new bound/target recount",
    )
    relaxed_zeros = tuple(combinations_with_replacement(range(2, 7), 5))
    ablations = {
        "DROP_P_FLOOR": finite_superset(remainder=False)["MAX_UPPER"],
        "DROP_LOW_PAIR_CAPACITY": finite_superset(capacity=False)["MAX_UPPER"],
        "ALLOW_ALL_RANGE_AND_PARITY_ZERO_LISTS": finite_superset(relaxed_zeros)["MAX_UPPER"],
    }
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "COMPLETE_SELF_CHECK_ONLY",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "PROFILE_ID": PROFILE_ID,
        "PROOF": __doc__,
        "AUTHORITY": authority,
        "SOURCE_T_CAP": row.cap,
        "SOURCE_S4_BASE": row.s4_base,
        "SOURCE_ROW_BOUND": row.bound,
        "SOURCE_ROW_SOURCE": row.source,
        **premise,
        "MATHEMATICAL_THEOREM": "FOR_EVERY_LEGAL_STRUCTURE_OF_THIS_PROFILE_T_LE_255",
        "LOAD_BEARING_INEQUALITY": "T=F-P<=F-p(q,E)<=255",
        "PROOF_SCOPE": "FULL_PROFILE",
        "TARGET_T_CAP": 262,
        "PROVED_T_CAP": PROVED_CAP,
        "RELAXATION_SUPERSET_COMPLETENESS": "PROVED_IN_SOURCE_DOCSTRING",
        "RELAXATION_COMPLETENESS": "EVERY_LEGAL_SUPPORT_MAPS_TO_AN_ENUMERATED_BRANCH",
        "FINITE_SUPERSET": finite,
        "COUNTEREXAMPLE_STATUS": "NONE_IN_COMPLETE_SUPERSET_T_GE_256",
        "ATTAINMENT": "NOT_ASSERTED",
        "UNPROVED_ASSUMPTIONS": [],
        "RECORDED_REALIZATION": realization(row),
        "OLD_BOUND": row.bound,
        "EXPECTED_T262_BOUND": full[-3][1],
        "NEW_ADMISSIBLE_BOUND": peak[1],
        "OWNER_BOUND_DELTA": row.bound - peak[1],
        "ROUTE_B_INTEGER_RECOUNT": "PASS",
        "EXACT_RATIONAL_CHECK": "PASS",
        "ROUNDING_CHECK": "PASS",
        "ROUTE_B": {
            "W": 833,
            "U": 2370,
            "A_MAX": 201,
            "S4_BASE": row.s4_base,
            "ALL_T_TERMS": new,
            "ARGMAX_TERM": peak,
            "OLD_ARGMAX_TERM": full[-2],
            "T262_TERM": full[-3],
            "PRIOR_T264_TERM": old[-1],
        },
        "NEGATIVE_CASE_RESULTS": ablations,
        "FAMILY_GAIN_CLAIMED": 0,
        "NEW_WINNING_OUTCOMES": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "HEAVY_SOLVER_STARTED": "NO",
        "SOLVER_CALLS": 0,
        "CPU_PROCESS_COUNT": 1,
        "CPU_LIMIT_SECONDS_PER_RUN": 120,
        "FROZEN_LEDGER_MUTATED": "NO",
        "PUSH": "NOT_RUN",
        "MERGE": "NOT_RUN",
        "PRODUCTION_MUTATION": "NONE",
    }


def main() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
    result = compute_result()
    RESULT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "TASK_STATUS",
                    "PROOF_SCOPE",
                    "PROVED_T_CAP",
                    "NEW_ADMISSIBLE_BOUND",
                    "OWNER_BOUND_DELTA",
                )
            }
        )
    )
    print("RESULT_SHA256", hashlib.sha256(RESULT_PATH.read_bytes()).hexdigest())
    print(
        "CPU_SECONDS",
        resource.getrusage(resource.RUSAGE_SELF).ru_utime
        + resource.getrusage(resource.RUSAGE_SELF).ru_stime,
    )


if __name__ == "__main__":
    main()
