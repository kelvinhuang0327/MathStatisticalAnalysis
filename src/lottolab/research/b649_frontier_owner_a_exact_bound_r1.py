"""Full-profile analytic T<=261 for 66665555555331000000 (no solver).

Legal supports: 22 triples and 27 pairs on 20 tickets, six labels per ticket,
and no ticket pair occurs in two supports. If d counts triple incidences,
the shadow-plus-pair graph G has 93 edges and degree 6+d; H=complement(G)
has 97 edges and degree 13-d. Here d=(6^4,5^7,3^2,1,0^6), sum d=66,
sum d^2=338. Counting nonmonochromatic triples at their two unlike-edge
vertices proves Goodman: t(G)+t(H)=C(20,3)-sum (6+d)(13-d)/2=298.
Equivalently, inclusion-exclusion gives 1140-18*97+904=298.

Let K={d>0}, |K|=14, Z={d=0}, |Z|=6. Triples cannot meet Z. Consequently
sigma_x=|N_G(x) intersect Z|<=6-d_x, while 1<=zeta_u=|N_G(u) intersect K|<=6:
a zero has six G-neighbours and at most five in Z. Both sums equal r.
For M=H[K], MZ=H[Z], h_x=7-d_x+sigma_x and a_u=zeta_u-1. Thus
|M|=(32+r)/2, |MZ|=(r-6)/2, and 6|M|+14|MZ|=54+10r.

Each mixed H triangle has one same-part edge. For xy in M its Z apices
number 6-sigma_x-sigma_y+|N_G(x) intersect N_G(y) intersect Z|. For uw in
MZ its K apices number 14-zeta_u-zeta_w+|N_G(u) intersect N_G(w) intersect K|.
Therefore t(H)=54+11r-sum sigma(7-d+sigma)-sum zeta^2+P, where
P=t(M)+t(MZ)+sum_M common_G_Z+sum_MZ common_G_K>=0, a sum of four
cardinalities. Eliminating r yields the exact identity
T=t(G)=244+sum_K sigma(sigma+2-d)+sum_Z zeta(zeta-6)-P.

Write A=sum sigma over the seven d=5 vertices, Q=sum sigma over the two
d=3 vertices, L=sigma at the d=1 vertex. The four d=6 sigmas are zero,
r=A+Q+L, A>=0, Q<=6, L<=5. On the entire legal unary ranges,
sigma(sigma+2-d)<=-2sigma (d=5), <=2sigma (d=3), <=6sigma (d=1).
Since (zeta-1)(zeta-6)<=0, zeta(zeta-6)<=zeta-6. Summing proves
T<=244-2A+2Q+6L+r-36-P=208-A+3Q+7L-P<=261.
This is analytic and covers every legal support realization. No graphicality,
seeded sample, witness, donor cap, or solver is a proof premise. The complete
class-sorted range/equal-sum relaxation is only a supplemental check: its
2,539 points also peak at 261. Attainment by a legal support is not asserted.

Route B independently uses integers throughout. The weakest sufficient
integer cap is 263 (264 fails); the proved cap 261 gives 313371452. The
certificate does not update the ledger, claim a family gain, exclude this
owner relative to the incumbent, or settle global K20 optimality.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from contextlib import ExitStack
from dataclasses import asdict
from functools import lru_cache
from itertools import combinations, combinations_with_replacement, product
from math import comb
from unittest.mock import patch

from . import b649_min_s2_next_owner_core_zero_t256_cert_r1 as frozen

TASK_ID = "B649_FRONTIER_OWNER_A_EXACT_BOUND_R1"
HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
FROZEN_SHA256 = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"
PROFILE = "66665555555331000000"
CAP = 261
OLD_BOUND = 313_398_144
COMPETITOR = 313_397_860
ROOT = frozen.ROOT
DIRECTORY = frozen.two.RESULT_DIRECTORY
RESULT = ROOT / DIRECTORY / "b649-frontier-owner-a-exact-bound-r1-result.json"
require = frozen.require
ZERO_RANGE = range(1, 7)


@lru_cache(maxsize=1)
def authority():
    """Replay all frozen rows; cache exact pure functions, skip no verification."""
    require(frozen.three.git_tree(HEAD) == TREE, "frozen tree mismatch")
    raw = frozen.two.blob(HEAD, f"{DIRECTORY}/{frozen.RESULT_STEM}-result.json", FROZEN_SHA256)
    require(frozen.RESULT_PATH.read_bytes() == raw, "frozen result changed")
    result = json.loads(raw)
    modules = [m for n, m in sys.modules.items() if n.startswith("lottolab.research.")]
    names = (
        "coarse_profile_envelope",
        "profile_s4_floor",
        "r18_cap",
        "overlap_wedge_count",
        "bound_from_cap",
        "route_b_envelope",
        "profile_nb_cap",
    )
    functions = {getattr(m, n) for m in modules for n in names if hasattr(m, n)}
    with ExitStack() as stack:
        for function in functions:
            cached = lru_cache(maxsize=None)(function)
            for module in modules:
                for name, value in list(vars(module).items()):
                    if value is function:
                        stack.enter_context(patch.object(module, name, cached))
        frozen.module_provenance()
        source = ROOT / "src/lottolab/research/b649_min_s2_next_owner_core_zero_t256_cert_r1.py"
        require(
            source.read_bytes() == frozen.chase.git("show", f"{HEAD}:{source.relative_to(ROOT)}"),
            "seven-row source changed",
        )
        _six_result, six = frozen.six_row_authority()
        update = result["ROW_UPDATE"]
        require(
            json.loads(json.dumps(asdict(six[frozen.TARGET_PROFILE]))) == update["BEFORE"],
            "seventh row before mismatch",
        )
        after = update["AFTER"]
        ledger = frozen.apply_seventh(six, after["bound"], after["cap"], after["source"])
    require(
        len(ledger) == result["LEDGER_ROWS"] == 4647
        and frozen.two.full_digest(ledger) == result["FULL_ROWS_SHA256_AFTER"]
        and frozen.two.bounds_digest(ledger) == result["BOUNDS_SHA256_AFTER"],
        "full frozen ledger mismatch",
    )
    row = ledger[PROFILE]
    require(
        (row.cap, row.s4_base, row.bound, row.source)
        == (
            264,
            112,
            OLD_BOUND,
            "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:NB_CERTIFICATES[872]",
        ),
        "frozen owner row mismatch",
    )
    return result, ledger


def theorem(profile=PROFILE, zero_range=ZERO_RANGE, coefficients=(-2, 2, 6)):
    d = tuple(map(int, profile))
    require(
        Counter(d) == {6: 4, 5: 7, 3: 2, 1: 1, 0: 6}
        and len(d) == 20
        and sum(d) == 66
        and sum(v * v for v in d) == 338,
        "profile premises fail",
    )
    phi2 = 2 * comb(20, 3) - sum((6 + v) * (13 - v) for v in d)
    phi = comb(20, 3) - 18 * 97 + sum(comb(13 - v, 2) for v in d)
    require(phi2 == 2 * phi == 596, "Goodman constant mismatch")
    tables = {
        v: {s: [s * (s + 2 - v), b * s] for s in range(7 - v)}
        for v, b in zip((5, 3, 1), coefficients, strict=True)
    }
    require(
        all(left <= right for table in tables.values() for left, right in table.values()),
        "core inequality fails",
    )
    require(coefficients == (-2, 2, 6), "unsupported coefficient chain")
    zero = {v: [v * (v - 6), v - 6] for v in zero_range}
    require(set(zero) >= set(range(1, 7)), "incomplete zero range")
    require(all(left <= right for left, right in zero.values()), "zero chord fails")
    constant = phi - 6 * (sum(7 - v for v in d if v)) // 2 + 14 * 6 // 2
    cap = constant - 36 + 3 * 6 + 7 * 5
    require(constant == 244 and cap == CAP, "analytic constant mismatch")
    return {
        "PROOF_SCOPE": "FULL_PROFILE",
        "GOODMAN_CONSTANT": phi,
        "CORE_VERTICES": 14,
        "ZERO_VERTICES": 6,
        "CORE_H_BASE_SUM": 32,
        "EXACT_TRIANGLE_IDENTITY": "T=244+sum_K sigma(sigma+2-d)+sum_Z zeta(zeta-6)-P",
        "NONNEGATIVE_REMAINDER": "P=t(M)+t(MZ)+sum_M common_G_Z+sum_MZ common_G_K>=0",
        "LOAD_BEARING_PREMISES": [
            "22 linear triples; 27 unused pairs; six labels/ticket",
            "sigma<=6-d; 1<=zeta<=6; sum sigma=sum zeta",
            "P>=0",
        ],
        "CORE_INEQUALITIES": tables,
        "ZERO_CHORD": zero,
        "CAP_CHAIN": "T<=208-A+3Q+7L-P<=208+18+35=261",
        "ANALYTIC_CAP": cap,
        "ATTAINMENT": "NOT_ASSERTED",
        "UNPROVED_ASSUMPTIONS": [],
        "COUNTEREXAMPLE_STATUS": "NONE_IN_COMPLETE_RELAXATION",
    }


def relaxed_value(sigma, zeta):
    d = tuple(map(int, PROFILE))[:14]
    require(len(sigma) == 14 and len(zeta) == 6, "cross-degree lengths")
    require(
        all(type(s) is int and 0 <= s <= 6 - v for s, v in zip(sigma, d, strict=True))
        and all(type(v) is int and 1 <= v <= 6 for v in zeta),
        "cross-degree ranges",
    )
    require(sum(sigma) == sum(zeta), "cross-degree sums")
    return (
        244
        + sum(s * (s + 2 - v) for s, v in zip(sigma, d, strict=True))
        + sum(v * (v - 6) for v in zeta)
    )


def relaxation():
    """Complete superset: sort only equal-d sigmas and zero-side zetas."""
    by_sum = {}
    for zeta in combinations_with_replacement(range(1, 7), 6):
        by_sum.setdefault(sum(zeta), []).append(zeta)
    count, maximum, top = 0, -1, []
    for a, q, low in product(range(8), combinations_with_replacement(range(4), 2), range(6)):
        sigma = (0,) * 4 + (0,) * (7 - a) + (1,) * a + q + (low,)
        for zeta in by_sum.get(sum(sigma), []):
            f = relaxed_value(sigma, zeta)
            count += 1
            if f > maximum:
                maximum, top = f, []
            if f == maximum:
                top.append([list(sigma), list(zeta)])
    require(count == 2539 and maximum == CAP, "complete relaxation changed")
    return {
        "RELAXATION_DOMAIN": "full legal unary ranges and equal sums; no graphicality",
        "RELAXATION_COMPLETENESS": "permutations inside equal-degree classes and Z preserve F",
        "COUNT": count,
        "MAXIMUM": maximum,
        "ARGMAX": top,
        "ROLE": "SUPPLEMENTAL_TO_ANALYTIC_PROOF",
    }


def support_check(triples, pairs):
    """Independent support, graph, mixed-triangle and exact-remainder recount."""
    supports = (*triples, *pairs)
    require(
        len(triples) == 22
        and len(pairs) == 27
        and all(len(s) == 3 for s in triples)
        and all(len(s) == 2 for s in pairs),
        "support counts",
    )
    require(
        all(
            len(set(s)) == len(s) and all(type(v) is int and 0 <= v < 20 for v in s)
            for s in supports
        ),
        "support vertices",
    )
    shadow = [tuple(sorted(e)) for s in supports for e in combinations(s, 2)]
    require(len(shadow) == len(set(shadow)) == 93, "support pair-linearity")
    require(all(sum(v in s for s in supports) == 6 for v in range(20)), "ticket capacity")
    d = tuple(sum(v in s for s in triples) for v in range(20))
    require("".join(map(str, sorted(d, reverse=True))) == PROFILE, "wrong profile")
    g, every = set(shadow), set(combinations(range(20), 2))
    h = every - g
    k, z = {v for v in range(20) if d[v]}, {v for v in range(20) if not d[v]}
    nb = {v: {w for w in range(20) if tuple(sorted((v, w))) in g} for v in range(20)}
    m = {e for e in h if set(e) <= k}
    mz = {e for e in h if set(e) <= z}
    sigma = {v: len(nb[v] & z) for v in k}
    zeta = [len(nb[v] & k) for v in sorted(z)]

    def triangles(vertices, edges):
        return sum(
            all(e in edges for e in combinations(t, 2)) for t in combinations(sorted(vertices), 3)
        )

    parts = [
        triangles(k, m),
        triangles(z, mz),
        sum(len(nb[x] & nb[y] & z) for x, y in m),
        sum(len(nb[x] & nb[y] & k) for x, y in mz),
    ]
    t, th, r = triangles(range(20), g), triangles(range(20), h), sum(sigma.values())
    f = 244 + sum(s * (s + 2 - d[v]) for v, s in sigma.items()) + sum(v * (v - 6) for v in zeta)
    require(
        all(0 <= s <= 6 - d[v] for v, s in sigma.items())
        and all(1 <= v <= 6 for v in zeta)
        and r == sum(zeta),
        "cross-edge premises",
    )
    require(2 * len(m) == 32 + r and 2 * len(mz) == r - 6, "part edge counts")
    a = sum(s for v, s in sigma.items() if d[v] == 5)
    q = sum(s for v, s in sigma.items() if d[v] == 3)
    low = sum(s for v, s in sigma.items() if d[v] == 1)
    require(
        t + th == 298
        and t == f - sum(parts)
        and t <= 208 - a + 3 * q + 7 * low - sum(parts) <= CAP,
        "exact decomposition",
    )
    return {
        "TRIANGLES": t,
        "COMPLEMENT_TRIANGLES": th,
        "F": f,
        "P_TERMS": parts,
        "P": sum(parts),
        "R": r,
        "A": a,
        "Q": q,
        "L": low,
        "SIGMA": [sigma[v] for v in sorted(k)],
        "ZETA": zeta,
    }


def route_b(cap, base=112):
    require(
        type(cap) is int and 22 <= cap <= 264 and type(base) is int and base >= 0,
        "integer Route-B domain",
    )
    d = tuple(map(int, PROFILE))
    g = [6 + v for v in d]
    w, j, b = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g), sum(v * (v + 4) for v in d)
    terms = []
    for t in range(22, cap + 1):
        numerator = j - (max(g) - 2) * (w - 3 * t)
        k4 = max(0, -((-numerator) // 4))
        contained = min(k4, b // 3)
        s4 = max(base, 679 * k4 - 231 * contained)
        s3 = 2800 * w + 11872 * (t - 22) - 30800
        bound = 372228640 - 63838600 + s3 - (4 * s4) // 7
        terms.append((t, bound, k4, contained, s4, s3))
    require(
        terms
        == frozen.r32.route_b_envelope(d, cap, base)
        == frozen.split.route_b_terms(d, cap, base),
        "independent Route-B mismatch",
    )
    return terms


def duplicate_check():
    """Inspect every frozen result JSON containing the exact profile id."""
    matches, certificates = [], []
    for path in sorted((ROOT / DIRECTORY).rglob("*.json")):
        if path == RESULT:
            continue
        raw = path.read_bytes()
        if PROFILE.encode() not in raw:
            continue
        relative = path.relative_to(ROOT).as_posix()
        require(raw == frozen.chase.git("show", f"{HEAD}:{relative}"), "unfrozen duplicate input")
        matches.append(relative)

        def visit(value, location, relative=relative):
            if isinstance(value, dict):
                if any(value.get(key) == PROFILE for key in ("PROFILE_ID", "TARGET_PROFILE")):
                    cap = value.get(
                        "ANALYTIC_CAP",
                        value.get(
                            "SPLIT_TRIANGLE_CAP",
                            value.get("TRIANGLE_CAP", value.get("CERTIFIED_T_CAP")),
                        ),
                    )
                    if type(cap) is int and cap <= CAP:
                        certificates.append([relative, location, cap])
                for key, item in value.items():
                    visit(item, f"{location}.{key}")
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    visit(item, f"{location}[{index}]")

        visit(json.loads(raw), "$")
    require(not certificates, "existing target cap certificate; do not duplicate")
    return {
        "STATUS": "NO_EXISTING_TARGET_CAP_CERTIFICATE",
        "MATCHED_FROZEN_RESULTS": matches,
        "EXISTING_GENERIC_SPLIT_IDENTITY": "PRESENT; independently derived here",
        "EXISTING_TARGET_CAPS_LE_261": certificates,
    }


@lru_cache(maxsize=1)
def compute_result():
    frozen_result, ledger = authority()
    before = frozen.two.full_digest(ledger)
    row = ledger[PROFILE]
    proof, supplemental = theorem(), relaxation()
    terms, old = route_b(CAP, row.s4_base), route_b(row.cap, row.s4_base)
    peak = max(terms, key=lambda t: (t[1], t[0]))
    threshold = max(t[0] for t in old if max(x[1] for x in old[: t[0] - 21]) <= COMPETITOR)
    require(
        max(t[1] for t in old) == row.bound
        and terms == old[: len(terms)]
        and peak[1] < OLD_BOUND
        and threshold == 263,
        "old row or threshold mismatch",
    )
    require(row.realization is not None, "recorded support missing")
    recorded = support_check(*row.realization)
    duplicate = duplicate_check()
    require(frozen.two.full_digest(ledger) == before, "frozen ledger mutated")
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "STRICT_OWNER_BOUND_REDUCTION_PROVED",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "PROOF": __doc__,
        "SOURCE": {
            "FROZEN_HEAD": HEAD,
            "FROZEN_TREE": TREE,
            "FROZEN_RESULT_SHA256": FROZEN_SHA256,
            "IDENTITY_STATUS": "MATCH",
            "PROFILE_ID": PROFILE,
            "DEGREE_PROFILE": "6^4,5^7,3^2,1^1,0^6",
            "VERTICES": 20,
            "DEGREE_SUM": 66,
            "DEGREE_SQUARE_SUM": 338,
            "ORIGINAL_T_CAP": row.cap,
            "ORIGINAL_S4_BASE": row.s4_base,
            "ORIGINAL_ROW_BOUND": row.bound,
            "ROW_SOURCE_IDENTITY": row.source,
            "ROW": asdict(row),
            "LEDGER_ROWS": len(ledger),
            "FULL_ROWS_SHA256": before,
            "BOUNDS_SHA256": frozen_result["BOUNDS_SHA256_AFTER"],
        },
        "MATHEMATICS": proof | supplemental,
        "RECORDED_SUPPORT_CHECK": recorded,
        "DUPLICATE_CHECK": duplicate,
        "OPTIMIZATION": {
            "OLD_BOUND": OLD_BOUND,
            "NEW_ADMISSIBLE_BOUND": peak[1],
            "STRICT_OWNER_BOUND_DELTA": OLD_BOUND - peak[1],
            "NEXT_COMPETING_BOUND": COMPETITOR,
            "BOUND_BELOW_NEXT_COMPETITOR": peak[1] <= COMPETITOR,
            "MINIMUM_SUFFICIENT_T_CAP": threshold,
            "MINIMUM_REQUIRED_CAP_REDUCTION": row.cap - threshold,
            "THRESHOLD_TERM": list(old[threshold - 22]),
            "FAILED_WEAKER_CAP_TERM": list(old[-1]),
            "INCUMBENT": frozen.INCUMBENT,
            "OWNER_EXCLUSION_PROVED": peak[1] <= frozen.INCUMBENT,
            "INDEPENDENT_ROUTE_B_RECOUNT": "PASS_PURE_INTEGERS_AND_TWO_FROZEN_IMPLEMENTATIONS",
            "T_TERM_COUNT": len(terms),
            "ALL_T_TERMS": terms,
            "ARGMAX_TERM": peak,
            "INTEGER_ROUNDING": "ceil numerator/4; floor B/3; floor 4*S4/7",
            "FAMILY_BOUND_GAIN_CLAIMED": 0,
            "NEW_WINNING_OUTCOMES": 0,
            "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        },
        "EXECUTION_POLICY": {
            "CPU_PROCESS_COUNT": 1,
            "CPU_SECONDS_LIMIT": 120,
            "HEAVY_SOLVER_STARTED": "NO",
            "LEDGER_MUTATED": "NO",
            "PUSH": "NOT_RUN",
            "MERGE": "NOT_RUN",
            "PRODUCTION_MUTATION": "NONE",
            "WORKTREE": str(ROOT),
        },
    }


def render(result):
    return (json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


def main():
    result = compute_result()
    payload = render(result)
    if RESULT.exists():
        require(RESULT.read_bytes() == payload, "existing result differs")
    else:
        with RESULT.open("xb") as output:
            output.write(payload)
    print(
        json.dumps(
            {
                "RESULT": str(RESULT),
                "SHA256": frozen.sha256(payload),
                "STATUS": result["TASK_STATUS"],
                **result["OPTIMIZATION"],
            }
            | {"ALL_T_TERMS": "IN_RESULT"}
        )
    )


if __name__ == "__main__":
    main()
