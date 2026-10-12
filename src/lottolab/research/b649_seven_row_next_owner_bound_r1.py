"""A full-profile incidence bound for 66655555555521000000; no donor imports.

Premises: 20 six-label tickets, 49 labels with 22 triple and 27 pair supports,
every ticket pair used at most once, triple degrees (6^3,5^9,2,1,0^6).
Thus the overlap graph G is simple, has 93 edges, and g_v=6+d_v.

The sole new inequality bounds A, the number of K4s containing a triple
support. Each K4 has at most one such support, since two distinct triples
in four vertices share a pair. Therefore A is exactly the sum, over the 22
supports S, of c(S)=|intersection_{v in S} N_G(v)|. For each v in S,
c(S)<=g_v-2=4+d_v (remove the other two vertices of S).

Let u be the unique d=2 vertex, v the unique d=1 vertex, e the indicator
that u and v share a support, and m the number of supports on three d=6
vertices. There are three such vertices, so 0<=m<=1; also 0<=e<=1.
Relative to the baseline 9 per support, the two supports through u cost
3 each, the one through v costs 4, their overlap refunds 3, and only an
all-six support can add 1. Consequently
  A <= sum_S (4+min_{x in S} d_x) <= 22*9-3*2-4+3e+m <= 192.
This counts every support of every realization of this profile. No witness,
graphical relaxation, sampling, or attainment claim is used in the proof.

The old relaxation averages the three degrees of each support instead of
taking their minimum: A<=floor(sum_v d_v*(4+d_v)/3)=floor(602/3)=200.
Frozen Route B: W=sum C(g,2)=832, C=sum C(g,3)=2356, g_max=12.
For T graph triangles, O=W-3T. Each nontriangle in G[N(v)] contains a
missing edge; that edge belongs to at most g_v-2 triples of N(v). Summing
over v gives 4*K4 >= C-10*O, so K=max(0,ceil((C-10*O)/4)) is a floor.
The local seven-label intersection counts are 448 for a K4 with a support
and 679 without. Hence S4>=max(112,679*K-231*min(K,192)).
S3=2800*(W-3T)+20272*(T-22)+7000*22 is exact. On any outcome at most
seven tickets win (their chosen hit triples use distinct pairs on seven
labels), so U<=S1-S2+S3-4*S4/7. We keep frozen conservative rounding:
U<=S1-S2+S3-floor(4*S4/7), and maximize over every integer 22<=T<=264.
T<=264 is the explicitly accepted frozen premise; its donor is not rerun.
The unchanged local counts give S1=20*18611432=372228640 and
S2=93*574000+97*107800=63838600. The old envelope with A<=200 peaks
at T=264, K=489, S4>=285831, S3=5171824, bound 313398532. With A<=192,
S4>=287679 at that same peak and the admissible bound becomes 313397476.

This executable uses only the standard library. Its intersection recount
chooses an unordered set of seven labels by selecting shared labels and
allocating private/outside labels; each set has seven special-label choices.
It never executes or imports any original research solver or donor function.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import resource
import sys
import unittest
from itertools import combinations, product
from math import comb
from pathlib import Path
from time import process_time_ns

TASK_ID = "B649_SEVEN_ROW_NEXT_OWNER_BOUND_R1"
PROFILE_ID = "66655555555521000000"
PROFILE = tuple(map(int, PROFILE_ID))
FROZEN_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
FROZEN_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
INPUT_PATH = "docs/research/matrix-native-results/b649-min-s2-next-owner-core-zero-t256-cert-r1-result.json"
INPUT_SHA256 = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"
RESULT_PATH = "docs/research/matrix-native-results/b649-seven-row-next-owner-bound-r1-result.json"
OLD_BOUND, NEXT_BOUND, INCUMBENT = 313398532, 313398248, 313263888
OLD_A_CAP, NEW_A_CAP, T_CAP = 200, 192, 264
ROOT = Path(__file__).resolve().parents[3]


def frozen_input(blob: bytes) -> dict:
    if hashlib.sha256(blob).hexdigest() != INPUT_SHA256:
        raise ValueError("frozen input SHA256 mismatch")
    authority = json.loads(blob)
    row = authority["NEW_OWNER_ROWS"][PROFILE_ID]
    if (row["bound"], row["cap"], row["s4_base"]) != (OLD_BOUND, T_CAP, 112):
        raise ValueError("frozen owner conditions mismatch")
    if (authority["FAMILY_BOUND_AFTER"], authority["NEXT_COMPETING_BOUND"],
        authority["INCUMBENT"], authority["NEXT_OWNER_IDS"]) != (
        OLD_BOUND, NEXT_BOUND, INCUMBENT, [PROFILE_ID]
    ):
        raise ValueError("frozen family facts mismatch")
    return authority


def local_penalty(degrees: tuple) -> int:
    """Per-support majorant; no vertex of triple degree zero is eligible."""
    if len(degrees) != 3 or any(type(d) is not int or d not in (1, 2, 5, 6) for d in degrees):
        raise ValueError("invalid local triple degrees")
    if degrees.count(1) > 1 or degrees.count(2) > 1:
        raise ValueError("only one vertex of each low degree exists")
    low2, low1 = int(2 in degrees), int(1 in degrees)
    return 9 + int(degrees == (6, 6, 6)) - 3 * low2 - 4 * low1 + 3 * low2 * low1


def incidence_cap(m: int, e: int) -> int:
    if type(m) is not int or type(e) is not int or m not in (0, 1) or e not in (0, 1):
        raise ValueError("support uniqueness requires binary m and e")
    return 22 * 9 - 3 * 2 - 4 + 3 * e + m


def envelope_term(t: int, a_cap: int) -> dict:
    if type(t) is not int or not 22 <= t <= T_CAP:
        raise ValueError("T outside frozen range")
    if type(a_cap) is not int or not 0 <= a_cap <= OLD_A_CAP:
        raise ValueError("invalid contained K4 cap")
    g = [6 + d for d in PROFILE]
    w, c = sum(comb(x, 2) for x in g), sum(comb(x, 3) for x in g)
    open_wedges = w - 3 * t
    excess = c - (max(g) - 2) * open_wedges
    k = max(0, (excess + 3) // 4)
    s4 = max(112, 448 * min(k, a_cap) + 679 * (k - min(k, a_cap)))
    s3 = 2800 * open_wedges + 20272 * (t - 22) + 7000 * 22
    return {"T": t, "OPEN_WEDGES": open_wedges, "EXCESS": excess, "K4_FLOOR": k,
            "A_CAP": a_cap, "S4_FLOOR": s4, "S3": s3,
            "BOUND": 372228640 - 63838600 + s3 - (4 * s4) // 7}


def intersection_count(n: int, shared: tuple) -> int:
    """Independent seven-set allocation, rather than special-label donor DP.

    Each shared mask denotes one distinct label. All other labels are private
    to one ticket or outside all tickets. This supports every local motif used.
    """
    if type(n) is not int or not 1 <= n <= 4:
        raise ValueError("local recount supports one to four tickets")
    if any(type(mask) is not int or not 0 < mask < (1 << n) or bin(mask).count("1") < 2
           for mask in shared):
        raise ValueError("invalid shared label")
    private = [6 - sum(bool(mask & (1 << v)) for mask in shared) for v in range(n)]
    if min(private) < 0:
        raise ValueError("ticket capacity exceeded")
    outside = 49 - len(shared) - sum(private)
    total = 0
    for choice in product((0, 1), repeat=len(shared)):
        selected = sum(choice)
        hits = [sum(c for c, mask in zip(choice, shared) if mask & (1 << v))
                for v in range(n)]
        ranges = [range(max(0, 3 - hit), min(size, 7 - selected) + 1)
                  for size, hit in zip(private, hits)]
        for take in product(*ranges):
            remaining = 7 - selected - sum(take)
            if 0 <= remaining <= outside:
                ways = comb(outside, remaining)
                for size, count in zip(private, take):
                    ways *= comb(size, count)
                total += ways
    return 7 * total


def local_counts() -> dict:
    return {
        "SINGLE": intersection_count(1, ()),
        "DISJOINT_PAIR": intersection_count(2, ()),
        "OVERLAP_PAIR": intersection_count(2, (3,)),
        "THREE_ONE_EDGE": intersection_count(3, (3,)),
        "THREE_WEDGE": intersection_count(3, (3, 5)),
        "THREE_PAIR_TRIANGLE": intersection_count(3, (3, 5, 6)),
        "THREE_SUPPORT_TRIANGLE": intersection_count(3, (7,)),
        "FOUR_FIVE_EDGES": intersection_count(4, (3, 5, 9, 6, 10)),
        "K4_PAIR_ONLY": intersection_count(4, (3, 5, 9, 6, 10, 12)),
        "K4_CONTAINED_TRIPLE": intersection_count(4, (7, 9, 10, 12)),
    }


def recount(realization: list) -> dict:
    if len(realization) != 2:
        raise ValueError("expected triple and pair supports")
    triples, pairs = realization
    if (len(triples), len(pairs)) != (22, 27):
        raise ValueError("support counts mismatch")
    d, labels, edges = [0] * 20, [0] * 20, set()
    for supports, size in ((triples, 3), (pairs, 2)):
        for support in supports:
            if (len(support) != size or len(set(support)) != size
                or any(type(v) is not int or not 0 <= v < 20 for v in support)):
                raise ValueError("invalid support")
            for v in support:
                labels[v] += 1
                d[v] += int(size == 3)
            for pair in combinations(sorted(support), 2):
                if pair in edges:
                    raise ValueError("pair reuse violates linearity")
                edges.add(pair)
    if tuple(sorted(d, reverse=True)) != PROFILE or labels != [6] * 20:
        raise ValueError("wrong profile or ticket capacities")
    adj = [{u for u in range(20) if tuple(sorted((u, v))) in edges} for v in range(20)]
    triangle_count = sum(all((a, b) in edges for a, b in combinations(q, 2))
                         for q in combinations(range(20), 3))
    common = [len(set.intersection(*(adj[v] for v in s))) for s in triples]
    actual_a, k4, five = 0, 0, 0
    support_sets = set(map(frozenset, triples))
    for q in combinations(range(20), 4):
        edge_count = sum((a, b) in edges for a, b in combinations(q, 2))
        contained = sum(frozenset(s) in support_sets for s in combinations(q, 3))
        if contained > 1:
            raise AssertionError("K4 support uniqueness failed")
        k4 += int(edge_count == 6)
        actual_a += int(edge_count == 6 and contained == 1)
        five += int(edge_count == 5 and contained == 0)
    low2, low1 = d.index(2), d.index(1)
    m = sum(all(d[v] == 6 for v in s) for s in triples)
    e = sum(low2 in s and low1 in s for s in triples)
    min_sum = sum(4 + min(d[v] for v in s) for s in triples)
    if not sum(common) == actual_a <= min_sum <= incidence_cap(m, e) <= NEW_A_CAP:
        raise AssertionError("incidence bound or independent A recount failed")
    exact_s4 = 112 * five + 448 * actual_a + 679 * (k4 - actual_a)
    at_t = envelope_term(triangle_count, NEW_A_CAP)
    if not (k4 >= at_t["K4_FLOOR"] and exact_s4 >= at_t["S4_FLOOR"]):
        raise AssertionError("frozen realization contradicts S4 lower bound")
    local_open = [sum(tuple(sorted((a, b))) not in edges for a, b in combinations(n, 2))
                  for n in adj]
    if sum(local_open) != 832 - 3 * triangle_count:
        raise AssertionError("open-wedge incidence identity failed")
    return {"T": triangle_count, "EDGES": len(edges), "K4": k4, "A": actual_a,
            "COMMON_NEIGHBORS_BY_SUPPORT": common, "MIN_DEGREE_SUM": min_sum,
            "M": m, "E": e, "A_CAP_FOR_THIS_REALIZATION": incidence_cap(m, e),
            "FIVE_EDGES_NO_TRIPLE": five, "EXACT_S4": exact_s4,
            "OPEN_WEDGES_BY_VERTEX": local_open, "S4_FLOOR": at_t["S4_FLOOR"],
            "ROLE": "SANITY_CHECK_ONLY_NOT_FULL_PROFILE_PROOF"}


def compute_result() -> dict:
    authority = frozen_input((ROOT / INPUT_PATH).read_bytes())
    old = [envelope_term(t, OLD_A_CAP) for t in range(22, T_CAP + 1)]
    new = [envelope_term(t, NEW_A_CAP) for t in range(22, T_CAP + 1)]
    old_peak, new_peak = max(old, key=lambda r: r["BOUND"]), max(new, key=lambda r: r["BOUND"])
    if old_peak["BOUND"] != OLD_BOUND or new_peak["BOUND"] != 313397476:
        raise AssertionError("independent envelope mismatch")
    return {
        "TASK_ID": TASK_ID, "TASK_STATUS": "STRICT_FULL_PROFILE_BOUND_REDUCTION_PROVED",
        "EVIDENCE_CLASS": "STRICT_PROOF_CONDITIONAL_ON_FROZEN_SCIENTIFIC_AUTHORITY",
        "JUDGE_MODE": "SELF_CHECK_ONLY", "PROOF_SCOPE": "FULL_PROFILE",
        "PROFILE_ID": PROFILE_ID, "FROZEN_PR": "https://github.com/kelvinhuang0327/MathStatisticalAnalysis/pull/365",
        "FROZEN_HEAD": FROZEN_HEAD, "FROZEN_TREE": FROZEN_TREE,
        "IDENTITY_VERIFICATION": "GIT_HEAD_AND_TREE_CHECKED_BY_LOCAL_RUN_HANDOFF",
        "INPUT_PATH": INPUT_PATH, "INPUT_SHA256": INPUT_SHA256, "INPUT_SHA256_VERIFIED": "YES",
        "ALL_ASSUMPTIONS_EXPLICIT": "YES", "INTEGER_ONLY": "YES",
        "ASSUMPTIONS": ["20 tickets, capacity six, all 49 labels have support two or three",
                        "22 distinct triple supports; 27 distinct pair supports; no reused ticket pair",
                        "triple degree multiset exactly (6^3,5^9,2,1,0^6)",
                        "accepted frozen admissible T<=264 and S4 base>=112; donor proof not rerun",
                        "frozen seven-row maximum, competing owners and accepted incumbent are authority inputs"],
        "INHERITED_AUTHORITY": "No upgrade of PR365 or its inherited certificate/judge caveats. Certificate F unchanged.",
        "UNPROVED_ASSUMPTIONS": [], "ATTAINMENT_ASSERTED": "NO",
        "PROOF": __doc__, "NEW_INEQUALITY": "A <= 188+m+3e <= 192",
        "OLD_CONTAINED_K4_CAP": OLD_A_CAP, "NEW_CONTAINED_K4_CAP": NEW_A_CAP,
        "INEQUALITY_DIRECTION_VERIFIED": "YES", "ROUNDING_VERIFIED": "YES",
        "T_CAP": T_CAP, "T_CAP_STATUS": "FROZEN_ACCEPTED_PREMISE_NOT_REPROVED",
        "S4_BASE": 112, "WEDGE_COUNT": 832, "NEIGHBOR_TRIPLE_SUM": 2356,
        "LOCAL_INTERSECTION_RECOUNT": local_counts(),
        "LOCAL_INCIDENCE_CASES": [{"M": m, "E": e, "CAP": incidence_cap(m, e)}
                                  for m, e in product((0, 1), repeat=2)],
        "FROZEN_REALIZATION_RECOUNT": recount(authority["NEW_OWNER_ROWS"][PROFILE_ID]["realization"]),
        "OLD_ADMISSIBLE_BOUND": OLD_BOUND, "OLD_OWNER_BOUND": OLD_BOUND,
        "NEXT_COMPETING_BOUND": NEXT_BOUND, "INCUMBENT": INCUMBENT,
        "OLD_ENVELOPE_PEAK": old_peak, "NEW_ENVELOPE_PEAK": new_peak,
        "NEW_ADMISSIBLE_BOUND": new_peak["BOUND"], "BOUND_DELTA": OLD_BOUND - new_peak["BOUND"],
        "STRICT_REDUCTION_PROVED": "YES", "FAMILY_BOUND_AFTER": max(NEXT_BOUND, new_peak["BOUND"]),
        "NEXT_OWNER_AFTER": authority["NEXT_COMPETING_OWNER_IDS"],
        "FAMILY_EFFECT": "DERIVED_CANDIDATE_ONLY_FORMAL_LEDGER_NOT_MUTATED",
        "T_TERMS_CHECKED": len(new), "NEW_ENVELOPE": new,
        "NEW_STRICT_WINNING_OUTCOMES": 0, "GLOBAL_OPTIMUM_PROVED": "NO", "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "HEAVY_SOLVER_STARTED": "NO", "SOLVER_CALLS": 0, "DONOR_IMPORTS": 0,
        "CPU_PROCESSES": 1, "CPU_BUDGET_SECONDS": 120,
        "REMOTE_PUSH": "NOT_RUN", "SOURCE_OUTSIDE_SCOPE_MUTATION": "NONE",
        "FROZEN_LEDGER_MUTATED": "NO", "CERTIFICATE_F_MUTATED": "NO",
        "LOCAL_COMMIT_HEAD_AND_TREE": "EXTERNAL_FINAL_HANDOFF_TO_AVOID_COMMIT_SELF_REFERENCE",
        "RESULT_SHA256": "EXTERNAL_FINAL_HANDOFF_HASH_OF_COMPLETE_RESULT_FILE",
        "MODEL_PROVENANCE": "Current worker; no model-selection API invoked; strongest-model designation not independently verified",
        "PRERESEARCH_LOOKUP": "NB result did not expose NB_CERTIFICATES at its top level; no donor run or research result inferred from it",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-result", action="store_true")
    args = parser.parse_args()
    # All computation and focused tests run in this one process.
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
    start = process_time_ns()
    test_path = ROOT / "tests/unit/test_b649_seven_row_next_owner_bound_r1.py"
    spec = importlib.util.spec_from_file_location("focused_owner_tests", test_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["b649_owner_candidate"] = sys.modules[__name__]
    spec.loader.exec_module(module)
    suite = unittest.defaultTestLoader.loadTestsFromModule(module)
    outcome = unittest.TextTestRunner(verbosity=2).run(suite)
    if not outcome.wasSuccessful():
        raise SystemExit(1)
    result = compute_result()
    result["FOCUSED_TESTS"] = {"STATUS": "PASS", "RUN": outcome.testsRun,
                               "FAILURES": len(outcome.failures), "ERRORS": len(outcome.errors)}
    result["NEGATIVE_CASES"] = ["wrong profile", "reused pair", "tampered input SHA256",
                                "nonbinary m/e", "out-of-range T", "fractional cap",
                                "191-cap claim fails at the admitted (m,e)=(1,1) local relaxation"]
    result["INDEPENDENT_RECOUNT"] = "Seven-label allocation; vertex/quartet incidence; all 243 T terms; integer quotient remainder checks"
    result["FALSIFIABILITY_CHECK"] = "PASS: controlled 191 cap mutation rejected; original restored in same process"
    elapsed = process_time_ns() - start
    result["CPU_NANOSECONDS"] = elapsed
    result["CPU_SECONDS"] = str(elapsed // 10**9) + "." + str(elapsed % 10**9).zfill(9)
    result["CPU_MEASUREMENT_SCOPE"] = "focused tests and result computation before serialization; RLIMIT_CPU bounds whole process at 120s"
    encoded = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    if args.write_result:
        (ROOT / RESULT_PATH).write_bytes(encoded)
    print(json.dumps({k: result[k] for k in ("TASK_STATUS", "NEW_ADMISSIBLE_BOUND", "BOUND_DELTA",
                                             "FAMILY_BOUND_AFTER", "NEXT_OWNER_AFTER", "CPU_SECONDS", "FOCUSED_TESTS")}))
    print("RESULT_SHA256=" + hashlib.sha256(encoded).hexdigest())


if __name__ == "__main__":
    main()
