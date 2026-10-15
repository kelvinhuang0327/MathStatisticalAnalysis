"""Full-profile certificate T<=252 (hence T<=265), at frozen 6569a966.

Model: 20 tickets, six labels per ticket, 22 triple supports, 27 pair supports,
and pair-linearity (no ticket pair occurs in two supports). The overlap graph G
is simple with 93 edges and degree 6+d. Only d=(6,5^10,4^2,2,0^6) is treated.
Let K={d>0}, Z={d=0}, so |K|=14, |Z|=6. Triple supports lie entirely in K.
For x in K let sigma_x=|N_G(x) intersect Z|; for u in Z let
zeta_u=|N_G(u) intersect K|. Pair capacity gives 0<=sigma_x<=6-d_x;
the zero degree and |Z|=6 give 1<=zeta_u<=6. Both sums equal r.

For H=complement(G), |H|=97 and deg_H=13-d. Goodman gives
T+t(H)=C(20,3)-sum (6+d)(13-d)/2=290. Independently, inclusion-exclusion
on each vertex triple gives T=1140-18*97+sum C(13-d,2)-t(H)=290-t(H).
Put M=H[K], L=H[Z]. Their degrees are h=7-d+sigma and a=zeta-1,
so |M|=(32+r)/2 and |L|=(r-6)/2. Over xy in M the number of Z apices
of H-triangles is 6-sigma_x-sigma_y+|N_G(x) intersect N_G(y) intersect Z|;
over uw in L it is 14-zeta_u-zeta_w+|N_G(u) intersect N_G(w) intersect K|.
Thus, exactly,
 t(H)=6|M|+14|L|-sum sigma*h-sum zeta*a+P,
 P=t(M)+t(L)+sum_M common_G_Z+sum_L common_G_K >= 0.
Substitution and sum sigma=sum zeta yield
 T=236+sum_K sigma(sigma+2-d)+sum_Z zeta(zeta-6)-P.

The ONE load-bearing inequality is that the two sums are <=16. For d=6 the
core coordinate is zero; for d=5 it is 0 or -2; for d=4 it is 0,-1,0;
for the unique d=2 it is sigma^2<=16. Every zero coordinate is nonpositive.
Consequently T<=236+16-P<=252. This proves the entire profile, without
graphicality assumptions, support enumeration, or attainment claims.
The rectangular coordinate relaxation even omits cross-sum equality, parity,
graphicality and support decomposability when maximizing the final separable
expression; it is a complete necessary-condition superset, not a sample.

Prior art: the frozen generic split identity supplies the same F-P framework;
its cited R30 row refutes T>=267. No frozen certificate for this profile proves
252 or 265. The inherited NB_CERTIFICATES[1620] Row.source is a synthetic
replay-catalog locator, NOT a JSON array in the NB result. Its independently
verified cap authority is R30 GROUP_ATTEMPTS[3038]. No new family integration
or family gain is claimed. All imported helpers are frozen, and no solver is run.
"""

from __future__ import annotations

import json
import resource
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from fractions import Fraction
from itertools import combinations
from math import comb
from pathlib import Path
from time import process_time

from . import b649_min_s2_next_owner_core_zero_t256_cert_r1 as frozen

TASK_ID = "B649_NEXT_TIED_OWNER_65555555555442000000_R1"
BASE_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
BASE_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
BASE_RESULT_SHA256 = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"
PROFILE_ID = "65555555555442000000"
PROFILE = tuple(map(int, PROFILE_ID))
CAP = 252
OLD_BOUND = 313_392_232
S4_BASE = 112
NEXT_COMPETITOR = 313_392_128
CORE_SHIFT = 2
ZERO_SHIFT = 6
ROOT = frozen.ROOT
RESULT_PATH = (
    ROOT
    / frozen.two.RESULT_DIRECTORY
    / ("b649-next-tied-owner-65555555555442000000-r1-result.json")
)
require = frozen.require
Term = tuple[int, int, int, int, int, int]


def separable(sigma: Sequence[int], zeta: Sequence[int]) -> int:
    """The exact T+P on the legal equal-cross-sum domain."""
    core = [d for d in PROFILE if d]
    return (
        236
        + sum(s * (s + CORE_SHIFT - d) for d, s in zip(core, sigma, strict=True))
        + sum(v * (v - ZERO_SHIFT) for v in zeta)
    )


def certify_coordinates(
    sigma_ranges: Mapping[int, Sequence[int]], zeta_range: Sequence[int]
) -> dict[str, object]:
    """Check the actual inequality on every value of each coordinate domain."""
    require(set(sigma_ranges) == {6, 5, 4, 2}, "core classes changed")
    core_terms = {
        d: [s * (s + CORE_SHIFT - d) for s in values] for d, values in sigma_ranges.items()
    }
    zero_terms = [v * (v - ZERO_SHIFT) for v in zeta_range]
    require(
        all(core_terms[d] and max(core_terms[d]) <= 0 for d in (6, 5, 4)),
        "high-core inequality fails",
    )
    require(core_terms[2] and max(core_terms[2]) <= 16, "low-core square exceeds 16")
    require(zero_terms and max(zero_terms) <= 0, "zero coordinate is positive")
    counts = Counter(d for d in PROFILE if d)
    bound = 236 + sum(counts[d] * max(v) for d, v in core_terms.items())
    bound += 6 * max(zero_terms)
    require(bound == CAP, "separable cap changed")
    return {
        "SIGMA_RANGES": {str(d): list(v) for d, v in sigma_ranges.items()},
        "ZETA_RANGE": list(zeta_range),
        "CORE_TERMS": {str(d): v for d, v in core_terms.items()},
        "ZERO_TERMS": zero_terms,
        "RECTANGULAR_MAXIMUM": bound,
    }


def theorem() -> dict[str, object]:
    """Analytic all-realizations certificate; coordinate checks are finite algebra."""
    require(
        Counter(PROFILE) == {6: 1, 5: 10, 4: 2, 2: 1, 0: 6}
        and sum(PROFILE) == 66
        and sum(d * d for d in PROFILE) == 322,
        "profile premises changed",
    )
    goodman = Fraction(comb(20, 3)) - Fraction(sum((6 + d) * (13 - d) for d in PROFILE), 2)
    complement = comb(20, 3) - 18 * 97 + sum(comb(13 - d, 2) for d in PROFILE)
    require(goodman == complement == 290, "Goodman constant changed")
    require(6 * 16 - 14 * 3 == 54 and 290 - 54 == 236, "split constant changed")
    # Both sides are separable quadratics: 0,e_i,2e_i determine every coefficient.
    points = frozen.three.identity_points(14, 6)
    for s, z in points:
        require(
            frozen.three.split_objective(PROFILE, s, z) == separable(s, z) + 2 * (sum(s) - sum(z)),
            "frozen F polynomial differs from the derived identity",
        )
    coordinates = certify_coordinates({d: range(7 - d) for d in (6, 5, 4, 2)}, range(1, 7))
    # A nonempty equal-sum, graphical necessary relaxation, not an attainment claim.
    sigma = (0, *([0] * 4), *([1] * 6), 0, 0, 0)
    zeta = (1,) * 6
    c = frozen.split.configuration(PROFILE, sigma, zeta)
    require(c.f == separable(sigma, zeta) == 194, "nonempty relaxation check changed")
    return {
        "GOODMAN_CONSTANT": int(goodman),
        "CORE_COUNT": 14,
        "ZERO_COUNT": 6,
        "EXACT_TRIANGLE_IDENTITY": "T=290-t(H)=236+sum sigma(sigma+2-d)+sum zeta(zeta-6)-P",
        "NONNEGATIVE_REMAINDER": "P=t(H[K])+t(H[Z])+sum_H[K] common_G_Z+sum_H[Z] common_G_K>=0",
        "LOAD_BEARING_PREMISES": [
            "22 triple and 27 pair supports on 20 tickets, each with exactly six labels",
            "pair-linearity; exact degree histogram 6^1,5^10,4^2,2^1,0^6",
            "all triples lie in K; 0<=sigma<=6-d; 1<=zeta<=6",
            "sum sigma=sum zeta; P is a sum of four nonnegative cardinalities",
        ],
        "LOAD_BEARING_INEQUALITY": "sum sigma(sigma+2-d)+sum zeta(zeta-6)<=16",
        "PROOF_SCOPE": "FULL_PROFILE",
        "PROVED_T_CAP": CAP,
        "RELAXATION_SUPERSET_COMPLETENESS": (
            "Every legal support maps into these coordinate ranges; the final maximum"
            " drops equality, parity, graphicality and support-decomposition constraints."
        ),
        "IDENTITY_POINTS_CHECKED": len(points),
        "NONEMPTY_NECESSARY_RELAXATION": {"SIGMA": list(sigma), "ZETA": list(zeta), "F": c.f},
        "ATTAINMENT": "NOT_ASSERTED",
        "UNPROVED_ASSUMPTIONS": [],
        "COUNTEREXAMPLE_STATUS": "EXCLUDED_UNDER_STATED_PREMISES_BY_ANALYTIC_PROOF",
        **coordinates,
    }


def validate_terms(terms: Sequence[Term], cap: int) -> None:
    """Independent exact rational arithmetic for every integer envelope term."""
    require([t[0] for t in terms] == list(range(22, cap + 1)), "triangle domain differs")
    g = [6 + d for d in PROFILE]
    w, u = sum(comb(d, 2) for d in g), sum(comb(d, 3) for d in g)
    allowance = Fraction(sum(d * (v - 2) for d, v in zip(PROFILE, g, strict=True)), 3)
    require((w, u, allowance) == (824, 2286, Fraction(586, 3)), "Route-B premises changed")
    for t, bound, k4, contained, s4, s3 in terms:
        excess = Fraction(u - (max(g) - 2) * (w - 3 * t), 4)
        expected_k4 = max(0, -((-excess.numerator) // excess.denominator))
        expected_contained = min(expected_k4, allowance.numerator // allowance.denominator)
        expected_s4 = max(
            S4_BASE, 448 * expected_contained + 679 * (expected_k4 - expected_contained)
        )
        expected_s3 = 2800 * w + 11872 * (t - 22) - 30800
        exact = 372_228_640 - 63_838_600 + expected_s3 - Fraction(4 * expected_s4, 7)
        require(
            (k4, contained, s4, s3) == (expected_k4, expected_contained, expected_s4, expected_s3),
            "Route-B integer terms differ",
        )
        require(0 <= bound - exact < 1, "exact rational rounding differs")


def route_b(cap: int) -> list[Term]:
    terms = frozen.r32.route_b_envelope(PROFILE, cap, S4_BASE)
    require(terms == frozen.split.route_b_terms(PROFILE, cap, S4_BASE), "frozen evaluators differ")
    validate_terms(terms, cap)
    return terms


def witness() -> tuple[tuple[tuple[int, ...], ...], tuple[tuple[int, ...], ...]]:
    """Explicit non-vacuity witness, not an optimization or enumeration."""
    triples = {
        tuple(sorted((v + i) % 13 for v in b))
        for b in frozen.three.STS13_BASE_BLOCKS
        for i in range(13)
    } - set(frozen.three.REMOVED_BLOCKS)
    # Move two incidences from degree-six vertices to a new degree-two vertex.
    triples -= {(1, 6, 12), (2, 8, 10)}
    triples |= {(1, 12, 13), (2, 10, 13)}
    pairs = (
        (0, 1),
        (0, 4),
        (3, 5),
        (3, 9),
        (6, 13),
        (8, 13),
        (2, 14),
        (7, 15),
        (10, 16),
        (11, 17),
        (13, 18),
        (13, 19),
        *combinations(range(14, 20), 2),
    )
    return tuple(sorted(triples)), pairs


def check_realization(
    triples: Sequence[tuple[int, ...]], pairs: Sequence[tuple[int, ...]]
) -> dict[str, object]:
    """Independent support checks and a direct graph recount of every P summand."""
    degrees = frozen.three.legal_degrees(triples, pairs)
    frozen.r5.validate_k20_support_realization(triples, pairs, degrees)
    require(tuple(sorted(degrees, reverse=True)) == PROFILE, "realization profile differs")
    g = {frozen.edge(x, y) for s in (*triples, *pairs) for x, y in combinations(s, 2)}
    k = [v for v, d in enumerate(degrees) if d]
    z = [v for v, d in enumerate(degrees) if not d]
    recounted = frozen.complement_split(k, z, g)
    sigma = [frozen.integer(v) for v in frozen.rows(recounted["SIGMA"])]
    zeta = [frozen.integer(v) for v in frozen.rows(recounted["ZETA"])]
    core = [degrees[v] for v in k]
    f = 236 + sum(s * (s + 2 - d) for s, d in zip(sigma, core, strict=True))
    f += sum(v * (v - 6) for v in zeta)
    p, t = frozen.integer(recounted["P"]), frozen.integer(recounted["T_G"])
    require(
        len(g) == 93
        and sum(sigma) == sum(zeta)
        and all(0 <= s <= 6 - d for s, d in zip(sigma, core, strict=True))
        and all(1 <= v <= 6 for v in zeta)
        and frozen.rows(recounted["H_CORE"])
        == [7 - d + s for d, s in zip(core, sigma, strict=True)]
        and frozen.rows(recounted["A_ZERO"]) == [v - 1 for v in zeta]
        and t == 290 - frozen.integer(recounted["T_H"]) == f - p <= CAP,
        "realization violates the derived identity or capacity premises",
    )
    return {"DEGREES": list(degrees), "F": f, **recounted}


def authority() -> dict[str, object]:
    """Use the existing ledger loader, then reproduce the sealed frozen ledger."""
    require(frozen.three.git_tree(BASE_HEAD) == BASE_TREE, "frozen tree mismatch")
    relative = frozen.RESULT_PATH.relative_to(ROOT).as_posix()
    raw = frozen.two.blob(BASE_HEAD, relative, BASE_RESULT_SHA256)
    require(frozen.RESULT_PATH.read_bytes() == raw, "frozen result changed")
    result = frozen.object_row(json.loads(raw))
    provenance = frozen.module_provenance()
    source = Path(frozen.__file__).resolve()
    relative_source = source.relative_to(ROOT).as_posix()
    require(
        source.read_bytes() == frozen.chase.git("show", f"{BASE_HEAD}:{relative_source}"),
        "frozen loader changed",
    )
    provenance[relative_source] = frozen.sha256(source.read_bytes())
    _prior, ledger = frozen.six_row_authority()
    after_row = frozen.object_row(frozen.object_row(result["ROW_UPDATE"])["AFTER"])
    ledger = frozen.apply_seventh(
        ledger, frozen.integer(result["PROFILE_BOUND_AFTER"]), 256, frozen.text(after_row["source"])
    )
    require(
        len(ledger) == 4647
        and frozen.two.full_digest(ledger) == result["FULL_ROWS_SHA256_AFTER"]
        and frozen.two.bounds_digest(ledger) == result["BOUNDS_SHA256_AFTER"],
        "frozen ledger reconstruction mismatch",
    )
    row = ledger[PROFILE_ID]
    require((row.cap, row.s4_base, row.bound) == (266, 112, OLD_BOUND), "source row mismatch")
    require(
        row.source == "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:NB_CERTIFICATES[1620]",
        "source catalog locator changed",
    )
    require(
        PROFILE_ID not in frozen.rows(result["CERTIFICATE_PROFILE_IDS"]),
        "profile already independently certified",
    )
    r30_path = f"{frozen.two.RESULT_DIRECTORY}/{frozen.r32.CAP_SOURCE_RESULT}"
    raw_r30 = frozen.two.blob(BASE_HEAD, r30_path, frozen.r32.R30_SHA256)
    r30 = frozen.object_row(json.loads(raw_r30))
    proof = frozen.object_row(frozen.rows(r30["GROUP_ATTEMPTS"])[3038])
    validate_cap_authority(proof)
    return {
        "FROZEN_HEAD_TREE": "MATCH",
        "FROZEN_RESULT_SHA256": "MATCH",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_RESULT_SHA256": BASE_RESULT_SHA256,
        "SOURCE_ROW": asdict(row),
        "SOURCE_T_CAP": row.cap,
        "SOURCE_S4_BASE": row.s4_base,
        "SOURCE_ROW_BOUND": row.bound,
        "ROW_SOURCE_LOCATOR_KIND": "SYNTHETIC_REPLAY_CATALOG_NOT_SERIALIZED_JSON_ARRAY",
        "SOURCE_PROOF_LOCATOR": f"{BASE_HEAD}:{r30_path}:GROUP_ATTEMPTS[3038]",
        "R30_RESULT_SHA256": frozen.r32.R30_SHA256,
        "R30_CAP_AUTHORITY": proof,
        "FROZEN_LEDGER_SHA256": frozen.two.full_digest(ledger),
        "MODULE_PROVENANCE": provenance,
        "PRIOR_ART": "Frozen generic F-P identity reused; target R30 caps 269,268,267,266."
        " No same-profile T<=265 theorem in the frozen certificate set.",
        "RECORDED_ROW_REALIZATION": "NONE_IN_FROZEN_ROW; PROOF_DOES_NOT_REQUIRE_ONE",
    }


def validate_cap_authority(proof: Mapping[str, object]) -> None:
    require(
        proof.get("ATTEMPT_INDEX") == 3038
        and proof.get("PROFILE_IDS") == [PROFILE_ID]
        and proof.get("TARGET_TRIANGLE_CAP") == 266
        and proof.get("REFUTED_GRAPH_TRIANGLE_COUNT") == 267
        and proof.get("CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND") == 266
        and proof.get("ROUTE") == frozen.r32.CAP_SOURCE_ROUTE
        and proof.get("STATUS") == "INFEASIBLE"
        and proof.get("CERTIFICATE_KIND") == "CP_SAT_INFEASIBLE",
        "R30 cap authority mismatch",
    )
    require(
        frozen.r32.r28.r26.accepted_cap(proof, (PROFILE,), 266) == 266,
        "frozen cap validator rejected the source",
    )


def compute_result() -> dict[str, object]:
    inputs = authority()
    proof = theorem()
    terms = route_b(266)
    peak_old = max(terms, key=lambda t: (t[1], t[0]))
    peak265 = max(terms[: 265 - 21], key=lambda t: (t[1], t[0]))
    new = terms[: CAP - 21]
    peak = max(new, key=lambda t: (t[1], t[0]))
    require(
        peak_old[1] == OLD_BOUND and peak265[1] == 313_383_464,
        "frozen Route-B numerical targets differ",
    )
    require(peak == (252, 313_266_764, 402, 195, 227_913, 5_006_960), "new argmax differs")
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "FULL_PROFILE_PROVED_SELF_CHECKED_LOCAL_ONLY",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "PROFILE_ID": PROFILE_ID,
        "DEGREE_DISTRIBUTION": "6^1,5^10,4^2,2^1,0^6",
        **inputs,
        **proof,
        "PROOF": __doc__,
        "EXPLICIT_LEGAL_NONVACUITY_WITNESS": check_realization(*witness()),
        "SOURCE_CAP": 266,
        "TARGET_T_CAP": 265,
        "OLD_BOUND": OLD_BOUND,
        "EXPECTED_CAP265_BOUND": peak265[1],
        "NEW_ADMISSIBLE_BOUND": peak[1],
        "NEW_BOUND": peak[1],
        "OWNER_DELTA": OLD_BOUND - peak[1],
        "NEXT_COMPETITOR": NEXT_COMPETITOR,
        "BELOW_NEXT_COMPETITOR": peak[1] < NEXT_COMPETITOR,
        "ROUTE_B_INTEGER_RECOUNT": "PASS_ALL_245_TERMS_T22_TO_266",
        "EXACT_RATIONAL_CHECK": "PASS",
        "ROUNDING_CHECK": "PASS_CEILING_OF_RATIONAL_BOUND",
        "ARGMAX_TERM": list(peak),
        "CAP266_ARGMAX": list(peak_old),
        "CAP265_ARGMAX": list(peak265),
        "ALL_T_TERMS": [list(t) for t in new],
        "NEGATIVE_CASES": [
            "LOW_CORE_RANGE",
            "HIGH_CORE_RANGE",
            "ZERO_RANGE",
            "IDENTITY_COEFFICIENT",
            "R30_STATUS",
            "R30_PROFILE",
            "K4_CEILING",
            "CONTAINED_ALLOWANCE",
            "S4_CREDIT",
            "ROUNDING",
            "PAIR_LINEARITY",
            "TICKET_CAPACITY",
        ],
        "CPU_PROCESS_COUNT": 1,
        "CPU_LIMIT_SECONDS_PER_INVOCATION": 120,
        "FAMILY_GAIN_CLAIMED": 0,
        "NEW_WINNING_OUTCOMES": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "HEAVY_SOLVER_STARTED": "NO",
        "PUSH": "NOT_RUN",
        "MERGE": "NOT_RUN",
        "PRODUCTION_MUTATION": "NONE",
    }


def main() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
    start = process_time()
    payload = frozen.two.render(compute_result())
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
                "CPU_SECONDS": process_time() - start,
            }
        )
    )


if __name__ == "__main__":
    main()
