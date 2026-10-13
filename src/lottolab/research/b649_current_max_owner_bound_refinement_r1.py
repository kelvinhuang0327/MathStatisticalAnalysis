"""Full-profile zero/core remainder refinement; no solver or portfolio search.

Proof, with all graph degrees referring to the simple overlap graph G:
Each of 20 tickets has six labels, each label supports two or three tickets,
and no ticket pair is reused. There are 22 triple and 27 pair supports,
g_v=6+d_v, |G|=93. For d=(6^3,5^9,2,1,0^6), K={d>0} has 14 vertices
and Z has six. All triple supports lie in K. Write sigma_x=|N_G(x) intersect Z|
and zeta_u=|N_G(u) intersect K|. Thus sigma is 0 on d=6, binary on d=5,
q in 0..4 on the unique d=2 vertex and p in 0..5 on the d=1 vertex.
A zero has degree six but only five other zero vertices, so 1<=zeta<=6.
Both sums count the cross edges: r=a+q+p=sum zeta, where a=sum_{d=5} sigma.

Let H=complement G, M=H[K], L=H[Z]. Then deg_M(x)=7-d_x+sigma_x,
deg_L(u)=zeta_u-1, |M|=(32+r)/2 and |L|=(r-6)/2. In particular r is even.
Goodman's identity gives T+t(H)=C(20,3)-sum g_v*(19-g_v)/2=298;
independently inclusion/exclusion in H gives 1140-18*97+904=298.

For an M edge xy the number of zero apices of an H triangle is
6-sigma_x-sigma_y+c_Z(xy), c_Z=|N_G(x) intersect N_G(y) intersect Z|.
For an L edge uw the core apices number 14-zeta_u-zeta_w+c_K(uw).
Every mixed triangle has exactly one same-part edge. Hence exactly
 t(H)=6|M|+14|L|-sum sigma*deg_M-sum zeta*deg_L+P
     =54+11r-(3a+5q+q^2+6p+p^2)-sum zeta^2+P,
 P=t(M)+t(L)+sum_{xy in M} c_Z(xy)+sum_{uw in L} c_K(uw)>=0.
Therefore
 T=244-8a-6q+q^2-5p+p^2+sum zeta^2-P.

Enumerating a=0..9, q=0..4, p=0..5 and every sorted six-tuple zeta in
1..6 with sum zeta=a+q+p even gives 874 necessary-condition states.
Their maximum after dropping P is 258. Every legal realization maps into
this set: binary sigma on the nine degree-five vertices is represented by
its sum a; sorting zeta preserves every constraint and the objective. No
graphicality, support reachability, or attainability filter is imposed.
The unique maximizing relaxed state is (a,q,p)=(1,4,5), zeta=(1^5,5).
It need not be realizable. Thus T<=258 universally, also independently
implying the inherited T<=264 premise without replaying its solver proof.

The inherited A<=192 is checked separately: for a triple support S,
c(S)<=4+min d_v. Relative to 22*9, two supports through d=2 lose 3 each,
the support through d=1 loses 4, a shared support restores 3e, and the sole
possible all-d=6 support adds m. Pair-linearity makes e,m binary and each
K4 contains at most one triple support. A<=188+3e+m<=192 on the full profile.

Only this Owner's Route-B terms are recomputed, by integer arithmetic,
Fraction arithmetic, and both unchanged legacy implementations. The old
243-term envelope is reproduced; the new 237-term envelope uses T<=258.
The eight-row BLOCKED_UNVERIFIABLE caveat is preserved, not upgraded.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import resource
import subprocess
import sys
import time
import unittest
from collections import Counter
from fractions import Fraction
from itertools import combinations, combinations_with_replacement, product
from math import comb
from pathlib import Path

TASK_ID = "B649_CURRENT_MAX_OWNER_BOUND_REFINEMENT_R1"
PROFILE = "66655555555521000000"
ROOT = Path(__file__).resolve().parents[3]
DONOR_ROOT = ROOT.parent / "B649_EIGHT_ROW_FAMILY_AUTHORITY_R1"
FROZEN_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
FROZEN_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
DONOR_HEAD = "c00cdb14cdfb7d0e0d57a4019c0306a0f5b29b7d"
DONOR_TREE = "5ee9ef8c5ccd418bc9b1dcae97f169bf996a0b66"
RESULT_DIR = "docs/research/matrix-native-results/"
FROZEN_RESULT = RESULT_DIR + "b649-min-s2-next-owner-core-zero-t256-cert-r1-result.json"
FROZEN_SHA = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"
DONOR_RESULT = RESULT_DIR + "b649-eight-row-family-authority-r1-result.json"
DONOR_SHA = "404600c87162bbb1db4d82eefe1c07a925ba88ad204662d2e2a00a44f8ffc3f0"
RESULT_PATH = ROOT / (RESULT_DIR + "b649-current-max-owner-bound-refinement-r1-result.json")
TEST_PATH = ROOT / "tests/unit/test_b649_current_max_owner_bound_refinement_r1.py"
FOCUSED_COMMAND = (
    "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src "
    "/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.venv/bin/python "
    "-m lottolab.research.b649_current_max_owner_bound_refinement_r1 --self-check"
)
REQUIRED_PREMISES = {
    "TICKETS": 20,
    "TICKET_CAPACITY": 6,
    "LABELS": 49,
    "TRIPLE_SUPPORTS": 22,
    "PAIR_SUPPORTS": 27,
    "PAIR_LINEARITY": True,
    "ALL_LABEL_MULTIPLICITIES_IN_2_3": True,
    "ALL_TRIPLES_IN_CORE": True,
    "CROSS_EDGE_BALANCE": True,
    "ZERO_CROSS_DEGREE_AT_LEAST_ONE": True,
    "NONNEGATIVE_REMAINDER": True,
}


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(root), *args])


def validate_profile(profile: str = PROFILE) -> tuple[int, ...]:
    require(type(profile) is str and profile == PROFILE, "wrong full profile")
    values = tuple(map(int, profile))
    require(Counter(values) == {6: 3, 5: 9, 2: 1, 1: 1, 0: 6}, "wrong degrees")
    require(sum(values) == 66, "wrong incidence sum")
    return values


def validate_premises(premises: dict) -> None:
    require(set(premises) == set(REQUIRED_PREMISES), "missing or extra necessary premise")
    require(
        all(
            type(premises[k]) is type(v) and premises[k] == v for k, v in REQUIRED_PREMISES.items()
        ),
        "invalid necessary premise",
    )


def validate_source_bytes(frozen: bytes, donor: bytes) -> tuple[dict, dict]:
    require(sha256(frozen) == FROZEN_SHA, "modified frozen certificate source")
    require(sha256(donor) == DONOR_SHA, "modified eight-row certificate source")
    f, d = json.loads(frozen), json.loads(donor)
    require(
        d["PROFILE_ID"] == PROFILE and d["PROOF_SCOPE"] == "FULL_PROFILE",
        "source proof applicability mismatch",
    )
    require(
        d["NEW_A_CAP"] == 192 and d["T_CAP"] == 264 and d["NEW_OWNER_BOUND"] == 313397476,
        "source bound mismatch",
    )
    require(
        d["A_PROOF"]["PROOF_SCOPE"] == "FULL_PROFILE" and bool(d["A_PROOF"]["PROOF"].strip()),
        "missing full-profile A proof",
    )
    require(f["NEW_OWNER_ROWS"][PROFILE]["cap"] == 264, "frozen T premise mismatch")
    return f, d


def verify_source_file(relative: str, blob: bytes, root: Path = ROOT) -> str:
    expected = git(root, "show", f"{DONOR_HEAD}:{relative}")
    require(blob == expected, f"modified Route-B source bytes: {relative}")
    return sha256(blob)


def load_sources() -> tuple[dict, dict, dict]:
    require(
        git(ROOT, "rev-parse", f"{FROZEN_HEAD}^{{tree}}").decode().strip() == FROZEN_TREE,
        "frozen HEAD/TREE mismatch",
    )
    require(
        git(DONOR_ROOT, "rev-parse", "HEAD").decode().strip() == DONOR_HEAD
        and git(DONOR_ROOT, "rev-parse", "HEAD^{tree}").decode().strip() == DONOR_TREE,
        "eight-row donor HEAD/TREE mismatch",
    )
    frozen = git(ROOT, "show", f"{FROZEN_HEAD}:{FROZEN_RESULT}")
    donor = git(ROOT, "show", f"{DONOR_HEAD}:{DONOR_RESULT}")
    require(
        (ROOT / FROZEN_RESULT).read_bytes() == frozen
        and (ROOT / DONOR_RESULT).read_bytes() == donor
        and (DONOR_ROOT / DONOR_RESULT).read_bytes() == donor,
        "working source bytes differ from pinned objects",
    )
    f, d = validate_source_bytes(frozen, donor)
    return (
        f,
        d,
        {
            "FROZEN_HEAD": FROZEN_HEAD,
            "FROZEN_TREE": FROZEN_TREE,
            "FROZEN_RESULT_SHA256": sha256(frozen),
            "EIGHT_ROW_HEAD": DONOR_HEAD,
            "EIGHT_ROW_TREE": DONOR_TREE,
            "EIGHT_ROW_RESULT_SHA256": sha256(donor),
            "WORKING_BYTES_EQUAL_COMMITTED_BYTES": True,
        },
    )


def profile_constants(profile: str = PROFILE) -> dict:
    d = validate_profile(profile)
    g = tuple(6 + x for x in d)
    h = tuple(19 - x for x in g)
    phi = Fraction(comb(20, 3)) - Fraction(sum(x * y for x, y in zip(g, h, strict=True)), 2)
    ie = comb(20, 3) - 18 * 97 + sum(comb(x, 2) for x in h)
    require(phi == ie == 298 and sum(g) == 186, "Goodman identity mismatch")
    return {
        "DEGREE_DISTRIBUTION": {str(k): v for k, v in sorted(Counter(d).items())},
        "CORE": 14,
        "ZERO": 6,
        "DEGREE_SUM": sum(d),
        "G_EDGES": 93,
        "H_EDGES": 97,
        "GOODMAN_PHI": int(phi),
        "H_IE_PHI": ie,
        "H_DEGREE_CHOOSE_2_SUM": sum(comb(x, 2) for x in h),
        "WEDGE_COUNT": sum(comb(x, 2) for x in g),
        "NEIGHBOUR_TRIPLE_SUM": sum(comb(x, 3) for x in g),
    }


def relaxed_states(zero_min: int = 1, balance: bool = True, parity: bool = True):
    """Sorted zeta symmetry quotient; optional weakenings are only for negative tests."""
    require(zero_min in (0, 1), "invalid relaxed zero range")
    zeros = list(combinations_with_replacement(range(zero_min, 7), 6))
    for a, q, p in product(range(10), range(5), range(6)):
        r = a + q + p
        if parity and r % 2:
            continue
        for zeta in zeros:
            if balance and sum(zeta) != r:
                continue
            value = 244 - 8 * a - 6 * q + q * q - 5 * p + p * p + sum(x * x for x in zeta)
            yield {"a": a, "q": q, "p": p, "r": r, "zeta": list(zeta), "T_UPPER": value}


def prove_cap(
    profile: str = PROFILE, premises: dict | None = None, claimed_cap: int | None = None
) -> dict:
    validate_profile(profile)
    validate_premises(REQUIRED_PREMISES if premises is None else premises)
    states = list(relaxed_states())
    cap = max(row["T_UPPER"] for row in states)
    require(
        type(claimed_cap) is int and claimed_cap >= cap if claimed_cap is not None else True,
        "cap is below the complete relaxation maximum",
    )
    return {
        "CAP": cap,
        "STATE_COUNT": len(states),
        "ARGMAX_STATES": [row for row in states if row["T_UPPER"] == cap],
        "STATE_SHA256": sha256(json.dumps(states, sort_keys=True).encode()),
        "DOMAIN": "a=0..9,q=0..4,p=0..5; 1<=zeta_1<=...<=zeta_6<=6; "
        "sum(zeta)=a+q+p even; P>=0 dropped",
        "COMPLETENESS": "Every legal support realization maps to a domain state. "
        "No graphicality or reachability filters; "
        "maximum not an existence claim.",
    }


def ceil_fraction(value: Fraction) -> int:
    return -(-value.numerator // value.denominator)


def route_term(t: int, weights: dict, a_cap: int = 192) -> dict:
    require(type(t) is int and 22 <= t <= 264, "T outside source domain")
    require(type(a_cap) is int and 0 <= a_cap <= 192, "unproved A cap")
    c = profile_constants()
    ow = c["WEDGE_COUNT"] - 3 * t
    excess = c["NEIGHBOUR_TRIPLE_SUM"] - 10 * ow
    k4 = max(0, (excess + 3) // 4)
    rational_k4 = max(0, ceil_fraction(Fraction(excess, 4)))
    contained = min(k4, a_cap)
    s4 = max(
        112, weights["K4_CONTAINED_TRIPLE"] * contained + weights["K4_PAIR_ONLY"] * (k4 - contained)
    )
    s1 = 20 * weights["SINGLE"]
    s2 = 93 * weights["OVERLAP_PAIR"] + 97 * weights["DISJOINT_PAIR"]
    s3 = (
        weights["THREE_WEDGE"] * ow
        + weights["THREE_PAIR_TRIANGLE"] * (t - 22)
        + weights["THREE_SUPPORT_TRIANGLE"] * 22
    )
    exact = Fraction(s1 - s2 + s3) - Fraction(4 * s4, 7)
    bound = s1 - s2 + s3 - (4 * s4) // 7
    require(k4 == rational_k4 and bound == ceil_fraction(exact), "rounding mismatch")
    return {
        "T": t,
        "OPEN_WEDGES": ow,
        "K4_LOWER_BOUND": k4,
        "A_CAP": a_cap,
        "S4_FLOOR": s4,
        "S3": s3,
        "BOUND": bound,
        "ROUNDING_REMAINDER": (4 * s4) % 7,
        "EXACT_BOUND_NUMERATOR": exact.numerator,
        "EXACT_BOUND_DENOMINATOR": exact.denominator,
    }


def validate_rounding(row: dict) -> None:
    excess = 2356 - 10 * row["OPEN_WEDGES"]
    require(
        row["K4_LOWER_BOUND"] == max(0, ceil_fraction(Fraction(excess, 4))), "incorrect K4 rounding"
    )
    exact = Fraction(row["EXACT_BOUND_NUMERATOR"], row["EXACT_BOUND_DENOMINATOR"])
    require(row["BOUND"] == ceil_fraction(exact), "incorrect final rounding")


def decomposition_check(adjacency: list[set[int]], core: set[int]) -> dict:
    """Observe the exact four nonnegative remainder counts for any simple graph."""
    n = len(adjacency)
    require(
        all(
            v not in adj and all(0 <= u < n and v in adjacency[u] for u in adj)
            for v, adj in enumerate(adjacency)
        ),
        "not a simple undirected graph",
    )
    zero = set(range(n)) - core
    h = [set(range(n)) - {v} - adj for v, adj in enumerate(adjacency)]
    m = [(x, y) for x, y in combinations(sorted(core), 2) if y in h[x]]
    zero_edges = [(x, y) for x, y in combinations(sorted(zero), 2) if y in h[x]]
    sigma = {x: len(adjacency[x] & zero) for x in core}
    zeta = {u: len(adjacency[u] & core) for u in zero}

    def triangles(graph, vertices):
        return sum(
            y in graph[x] and z in graph[x] and z in graph[y]
            for x, y, z in combinations(sorted(vertices), 3)
        )

    parts = [
        triangles(h, core),
        triangles(h, zero),
        sum(len(adjacency[x] & adjacency[y] & zero) for x, y in m),
        sum(len(adjacency[x] & adjacency[y] & core) for x, y in zero_edges),
    ]
    th = triangles(h, set(range(n)))
    base = (
        len(zero) * len(m)
        + len(core) * len(zero_edges)
        - sum(sigma[x] * len(h[x] & core) for x in core)
        - sum(zeta[u] * len(h[u] & zero) for u in zero)
    )
    tg = triangles(adjacency, set(range(n)))
    phi = Fraction(comb(n, 3)) - Fraction(sum(len(adjacency[v]) * len(h[v]) for v in range(n)), 2)
    require(th == base + sum(parts) and tg + th == phi, "decomposition identity fails")
    require(sum(sigma.values()) == sum(zeta.values()), "cross-edge balance fails")
    return {
        "T": tg,
        "H_TRIANGLES": th,
        "REMAINDER_PARTS": parts,
        "P": sum(parts),
        "BASE": base,
        "SIGMA": sigma,
        "ZETA": zeta,
        "GOODMAN_PHI": int(phi),
    }


def legacy_modules():
    relative = "src/lottolab/research/b649_eight_row_family_authority_r1.py"
    verify_source_file(relative, (ROOT / relative).read_bytes())
    eight = importlib.import_module("lottolab.research.b649_eight_row_family_authority_r1")
    provenance = {}
    # Bind the entire actually imported legacy research closure, not just wrappers.
    for name, module in sorted(sys.modules.copy().items()):
        if name.startswith("lottolab.research.b649_") and module.__file__:
            source = Path(module.__file__).resolve()
            if source == Path(__file__).resolve():
                continue
            relative = source.relative_to(ROOT).as_posix()
            provenance[relative] = verify_source_file(relative, source.read_bytes())
    return eight, eight.seven.r32, provenance


def compute_result() -> dict:
    frozen, donor, source = load_sources()
    constants = profile_constants()
    proof = prove_cap()
    eight, r32, module_bytes = legacy_modules()
    a_proof = eight.prove_a_cap()
    require(a_proof == donor["A_PROOF"], "full-profile A proof mismatch")
    weights = eight.local_intersection_weights()
    old = [route_term(t, weights) for t in range(22, 265)]
    legacy = eight.envelope_terms(264, 192, 112, weights)
    require(
        [{k: row[k] for k in legacy[0]} for row in old] == legacy == donor["NEW_ENVELOPE_TERMS"],
        "old Route-B envelope mismatch",
    )
    profile = validate_profile()
    for row in old:
        validate_rounding(row)
        require(
            r32.envelope_term(profile, row["T"], 112, 192)
            == (
                row["T"],
                row["BOUND"],
                row["K4_LOWER_BOUND"],
                min(row["K4_LOWER_BOUND"], 192),
                row["S4_FLOOR"],
                row["S3"],
            ),
            "independent R32 Route-B recount mismatch",
        )
    old_peak = max(old, key=lambda row: row["BOUND"])
    require(old_peak["BOUND"] == 313397476, "old bound not reproduced")
    prefix_max = []
    running = -1
    for row in old:
        running = max(running, row["BOUND"])
        prefix_max.append({"CAP": row["T"], "MAX_BOUND": running})
    sufficient = max(row["CAP"] for row in prefix_max if row["MAX_BOUND"] <= 313396120)
    new = old[: proof["CAP"] - 22 + 1]
    peak = max(new, key=lambda row: row["BOUND"])
    require(peak["BOUND"] < old_peak["BOUND"], "no strict provable gain")
    realization = frozen["NEW_OWNER_ROWS"][PROFILE]["realization"]
    eight.validate_realization(realization)
    graph = [set() for _ in range(20)]
    triple_degrees = [0] * 20
    for group in realization:
        for support in group:
            if len(support) == 3:
                for x in support:
                    triple_degrees[x] += 1
            for x, y in combinations(support, 2):
                graph[x].add(y)
                graph[y].add(x)
    core = {v for v, d in enumerate(triple_degrees) if d}
    observed = decomposition_check(graph, core)
    sigma, zeta = observed["SIGMA"], observed["ZETA"]
    a = sum(sigma[v] for v in core if triple_degrees[v] == 5)
    q = next(sigma[v] for v in core if triple_degrees[v] == 2)
    p = next(sigma[v] for v in core if triple_degrees[v] == 1)
    rhs = (
        244
        - 8 * a
        - 6 * q
        + q * q
        - 5 * p
        + p * p
        + sum(x * x for x in zeta.values())
        - observed["P"]
    )
    require(observed["T"] == rhs <= proof["CAP"], "pinned decomposition fails")
    observed.update({"a": a, "q": q, "p": p, "CHECK_SCOPE": "ONE_REALIZATION_SANITY_ONLY"})
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "STRICT_FULL_PROFILE_OWNER_GAIN_SELF_CHECKED",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "SOURCE_JUDGE_CAVEAT": "BLOCKED_UNVERIFIABLE",
        "JUDGE_UPGRADE": "NONE",
        "FROZEN_HEAD_TREE": "MATCH",
        "EIGHT_ROW_DONOR_HEAD_TREE": "MATCH",
        "EIGHT_ROW_RESULT_SHA256": "MATCH",
        "SOURCE_AUTHORITY": source,
        "LEGACY_MODULE_BYTES": module_bytes,
        "PROFILE": PROFILE,
        **constants,
        "SOURCE_T_CAP": 264,
        "SOURCE_OWNER_BOUND": old_peak["BOUND"],
        "SOURCE_T_CAP_APPLICABILITY": (
            "Inherited frozen cap; independently implied by the new full-profile T<=258 proof. "
            "Original CP-SAT certificate not rerun or upgraded."
        ),
        "EXISTING_A_LE_192_APPLICABILITY": a_proof,
        "NEW_LOAD_BEARING_INEQUALITY": "T=244-8a-6q+q^2-5p+p^2+sum(zeta^2)-P<=258",
        "PROOF_SCOPE": "FULL_PROFILE",
        "PROOF": __doc__,
        "GOODMAN_IDENTITY": "T+t(H)=298; independently 1140-18*97+904=298",
        "CORE_ZERO_DECOMPOSITION": "t(H)=54+11r-(3a+5q+q^2+6p+p^2)-sum(zeta^2)+P",
        "NONNEGATIVE_REMAINDER": "P=t(H[K])+t(H[Z])+sum_M c_Z+sum_L c_K>=0",
        "RELAXATION_COMPLETENESS": proof,
        "REQUIRED_PREMISES": REQUIRED_PREMISES,
        "NEW_T_CAP": proof["CAP"],
        "MAX_SUFFICIENT_T_CAP": sufficient,
        "SUFFICIENT_CAP_BOUND": prefix_max[sufficient - 22]["MAX_BOUND"],
        "NEXT_CAP_BOUND": prefix_max[sufficient - 21]["MAX_BOUND"],
        "OLD_BOUND": old_peak["BOUND"],
        "NEW_ADMISSIBLE_BOUND": peak["BOUND"],
        "OWNER_BOUND_DELTA": old_peak["BOUND"] - peak["BOUND"],
        "NEXT_COMPETING_BOUND": 313396120,
        "REQUIRED_BOUND_REDUCTION": 1356,
        "NEXT_COMPETITOR_REACHED": "YES" if peak["BOUND"] <= 313396120 else "NO",
        "INDEPENDENT_ROUTE_B_RECOUNT": "PASS: integer, Fraction, eight-row implementation, R32",
        "LOCAL_INTERSECTION_RECOUNT": weights,
        "T_TERM_COUNT": len(new),
        "OLD_T_TERM_COUNT": len(old),
        "ROUNDING_CHECK": "PASS_EVERY_TERM",
        "ARGMAX_TERM": peak,
        "NEW_ENVELOPE_TERMS": new,
        "OLD_ENVELOPE_PEAK": old_peak,
        "PINNED_REALIZATION_CHECK": observed,
        "HEAVY_SOLVER_STARTED": "NO",
        "CPU_PROCESS_COUNT": 1,
        "CPU_LIMIT_SECONDS": 120,
        "FAMILY_BOUND_GAIN_CLAIMED": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "NEW_WINNING_OUTCOMES": 0,
        "PUSH": "NOT_RUN",
        "MERGE": "NOT_RUN",
        "PRODUCTION_MUTATION": "NONE",
        "FORMAL_LEDGER_MUTATED": "NO",
        "EIGHT_ROW_CERTIFICATE_MUTATED": "NO",
        "PROSPECTIVE_PROJECTION_MUTATED": "NO",
        "CLEANUP_DISPOSITION": "RETAIN",
        "UNPROVED_ASSUMPTIONS": [],
        "POST_COMMIT_SEAL": "Result SHA256, local commit HEAD/TREE, and clean status are "
        "observed externally after the sole commit; no self-referential hash.",
    }


def validate_result_replay(saved: dict, current: dict) -> None:
    """Compare every scientific claim; runtime/test observations are separate."""
    runtime_fields = {
        "CPU_SECONDS",
        "CHILD_CPU_SECONDS",
        "FOCUSED_TEST_COMMAND",
        "FOCUSED_TEST_EXIT_CODE",
        "FOCUSED_TEST_COUNT",
        "NEGATIVE_CASES",
    }
    # JSON normalizes integer vertex keys in the observed sigma/zeta maps.
    normalized = json.loads(json.dumps(current))
    require(
        {k: v for k, v in saved.items() if k not in runtime_fields}
        == {k: v for k, v in normalized.items() if k not in runtime_fields},
        "saved result scientific claims differ from exact recount",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--write-result", action="store_true")
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
    started = time.process_time()
    result = compute_result()
    if args.self_check:
        suite = unittest.defaultTestLoader.discover(str(TEST_PATH.parent), pattern=TEST_PATH.name)
        run = unittest.TextTestRunner(verbosity=2).run(suite)
        if not run.wasSuccessful():
            return 1
        result.update(
            {
                "FOCUSED_TEST_COMMAND": FOCUSED_COMMAND,
                "FOCUSED_TEST_EXIT_CODE": 0,
                "FOCUSED_TEST_COUNT": run.testsRun,
                "NEGATIVE_CASES": [
                    "each missing/false necessary premise",
                    "wrong cap",
                    "wrong profile",
                    "incorrect K4/final rounding",
                    "modified frozen/eight-row/Route-B source bytes",
                    "weakened zero range",
                    "removed cross-edge balance",
                ],
            }
        )
    require(not args.write_result or args.self_check, "result write requires focused checks")
    result["CPU_SECONDS"] = round(time.process_time() - started, 6)
    result["CHILD_CPU_SECONDS"] = round(
        resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime
        + resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime,
        6,
    )
    require(result["CPU_SECONDS"] + result["CHILD_CPU_SECONDS"] < 120, "CPU budget exceeded")
    if RESULT_PATH.exists():
        validate_result_replay(json.loads(RESULT_PATH.read_bytes()), result)
    if args.write_result:
        RESULT_PATH.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "TASK_STATUS",
                    "NEW_T_CAP",
                    "NEW_ADMISSIBLE_BOUND",
                    "OWNER_BOUND_DELTA",
                    "T_TERM_COUNT",
                    "CPU_SECONDS",
                    "CHILD_CPU_SECONDS",
                )
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
