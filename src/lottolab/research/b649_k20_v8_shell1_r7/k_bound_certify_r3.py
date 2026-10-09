"""R3: certify the Shell-1 K/Q/N1 triangle bound with the repaired P_C quad term.

Run from this directory:  nice -n 15 <python> -B k_bound_certify_r3.py
Reads the four frozen R1 inputs plus k_bound_validation_r2.json (never writes them) and
writes k_bound_certification_r3.json. Single process, no CP-SAT, no profile enumeration:
coverage of the earlier floor(W/3) cap stage is certified by a generating-function count.
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import hashlib  # noqa: E402
import json  # noqa: E402
import resource  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402
from collections import Counter  # noqa: E402
from fractions import Fraction  # noqa: E402
from itertools import combinations, combinations_with_replacement  # noqa: E402
from math import comb  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import constants  # noqa: E402  frozen R1 source: co_win DP only
import profiles_k  # noqa: E402  frozen R1 source: kmax cross-check only

OUT = HERE / "k_bound_certification_r3.json"
FROZEN = {
    "constants.py": "7a04ce5f17f9e4c7422c601b5a884c2a2ecf97f412a0da9beaa7553e0151d251",
    "profiles.py": "f106f9c106d99d91b745bfdece1f07d44e955adba1d355daa93e73a479c63739",
    "profiles_k.py": "bb6927c10023df07a81dc514304dada433862693a942b694e03431d74b081312",
    "survivors.json": "c7287b11ba801f195372fb8db98e52a80c3b975e3cb478795cc95308457dfec2",
    "k_bound_validation_r2.json": "2ca0110a611938acfe30259baaf922c9fa802f424538c86e2539123cebe70c06",
}
INCUMBENT = 313_263_888
K20_SHA256 = "eaed652900d101881b678a1515d2a366bff9de6723dbec2ec9c82fe0d0d7844c"
S1_MINUS_S2 = 307_923_840
THRESH = INCUMBENT - S1_MINUS_S2
E = 94
TSTAR = {"P_A": 23, "P_C": 24}
NTRIP = {"P_A": 23, "P_C": 20}
EXPECTED = {
    "P_A": {"INPUT": 4605, "PRUNED": 3614, "REMAINING": 991},
    "P_C": {"INPUT": 53875, "PRUNED": 48025, "REMAINING": 5850},
}
EXPECTED_UNRESOLVED_SHA = "e1db41d1c1ea6fda0456f989b68ecab1fc4a26e2e14b020f576a14efc3f07d3b"


# ---- corrected bound (reusable) ---------------------------------------------------------

def degrees(kind: str, special, rest) -> list[int]:
    if kind == "P_A":
        return [5 + special[0]] + [6 + t for t in rest]
    return [8 + t for t in special] + [6 + t for t in rest]


def schonheim(k: int) -> int:
    """Elementary cap on a linear 3-graph on k points: each point lies in <= floor((k-1)/2)."""
    return (k * ((k - 1) // 2)) // 3


def packing(k: int) -> int:
    """Upper bound on D(k): Schonheim minus 1 when k = 5 mod 6 (parity; equals Spencer's exact D)."""
    return schonheim(k) - (k % 6 == 5)


def kmax(deg, t, ntrip, order=None, pack=packing) -> int:
    """Upper bound on K_trio; valid for any degree-descending order (prefix-dominating greedy)."""
    if order is None:
        order = sorted(range(len(deg)), key=lambda v: -deg[v])
    assert all(deg[order[i]] >= deg[order[i + 1]] for i in range(len(order) - 1))
    total = g = tsum = 0
    for r, v in enumerate(order):
        tsum += t[v]
        nxt = min(g + min(t[v], r // 2), pack(r + 1), tsum // 3, ntrip)
        assert nxt >= g
        total += (nxt - g) * (deg[v] - 2)
        g = nxt
    return total


def quad_term(quad_deg) -> int:
    """Upper bound on 3*K_quad + 8*Q: 8M + 3*floor((S - 4M)/3), a_i = deg_i - 3."""
    a = [d - 3 for d in quad_deg]
    m, s = min(a), sum(a)
    assert m >= 0 and s - 4 * m >= 0
    return 8 * m + 3 * ((s - 4 * m) // 3)


def kq_bound(kind: str, special, rest, pack=packing) -> int:
    """Integer B >= 3K + 8Q for every Shell-1 configuration with this profile."""
    deg = degrees(kind, special, rest)
    b = 3 * kmax(deg, list(special) + list(rest), NTRIP[kind], pack=pack)
    return b + quad_term(deg[:4]) if kind == "P_C" else b


def s3_ub(kind: str, w: int, b: int) -> int:
    """S3 = 2800W + 11872*T_true - 1400*Tstar with T_true <= floor((10E + B)/6)."""
    return 2800 * w + 11872 * ((10 * E + b) // 6) - 1400 * TSTAR[kind]


def s3_wedge(kind: str, w: int) -> int:
    """Earlier cap stage: T3 <= floor(W/3)."""
    return 2800 * w + 11872 * (w // 3) - 13272 * TSTAR[kind]


# ---- focused deterministic checks -------------------------------------------------------

def k12_k8() -> list[frozenset[int]]:
    """Legal P_A config: STS(13) minus a point on K12 (20 trios + 6 pairs), 3 trios on K8."""
    sts = {frozenset((x + a) % 13 for a in base) for x in range(13) for base in ((0, 1, 4), (0, 2, 7))}
    assert len(sts) == 26
    holders = [sorted(b - {12}) for b in sorted(sts, key=sorted)]
    k8 = [(0, 1, 2), (0, 3, 4), (5, 6, 7)]
    used = {p for tr in k8 for p in combinations(tr, 2)}
    holders += [[12 + i for i in tr] for tr in k8]
    holders += [[12 + i, 12 + j] for i, j in combinations(range(8), 2) if (i, j) not in used]
    holders.append([12])
    tickets: list[set[int]] = [set() for _ in range(20)]
    for label, hs in enumerate(holders, 1):
        for u in hs:
            tickets[u].add(label)
    return [frozenset(t) for t in tickets]


def analyze(tickets: list[frozenset[int]]) -> dict:
    """Brute-force T_true, K, Q, N1 on a legal config and check every inequality of the bound."""
    assert len(tickets) == 20 and all(len(t) == 6 and t <= set(range(1, 50)) for t in tickets)
    assert all(len(a & b) <= 1 for a, b in combinations(tickets, 2))
    hold = {y: [u for u, t in enumerate(tickets) if y in t] for y in range(1, 50)}
    hist = dict(Counter(len(h) for h in hold.values()))
    kind = {(1, 2, 3): "P_A", (2, 3, 4): "P_C"}[tuple(sorted(hist))]
    assert hist == ({1: 1, 2: 25, 3: 23} if kind == "P_A" else {2: 28, 3: 20, 4: 1})
    adj = [[u != v and len(tickets[u] & tickets[v]) == 1 for v in range(20)] for u in range(20)]
    deg = [sum(row) for row in adj]
    assert sum(deg) // 2 == E == sum(comb(len(h), 2) for h in hold.values())
    w = sum(comb(d, 2) for d in deg)
    paths = star = true = 0
    for a, b, c in combinations(range(20), 3):
        k = adj[a][b] + adj[a][c] + adj[b][c]
        if k == 2:
            paths += 1
        elif k == 3:
            if tickets[a] & tickets[b] & tickets[c]:
                star += 1
            else:
                true += 1
    assert star == TSTAR[kind] and paths == w - 3 * (star + true)
    s3 = 2800 * paths + 7000 * star + 20272 * true
    assert s3 == 2800 * w + 11872 * (star + true) - 13272 * star
    tally: Counter = Counter()
    apex_ok = True
    for y, h in hold.items():
        ms = [sum(adj[u][b] for b in h) for u in range(20) if u not in h]
        tally.update((len(h), m) for m in ms)
        if len(h) == 3:
            apex_ok &= ms.count(3) <= min(deg[b] for b in h) - 2
    k_trio, k_quad, q = tally[3, 3], tally[4, 3], tally[4, 4]
    n1 = sum(v for (_, m), v in tally.items() if m == 1)
    assert max(m for _, m in tally) <= 4
    t = [sum(len(hold[y]) == 3 for y in tk) for tk in tickets]
    spec = [hold[y] for y in hold if len(hold[y]) == (1 if kind == "P_A" else 4)][0]
    special = tuple(sorted((t[u] for u in spec), reverse=True))
    rest = tuple(sorted((t[u] for u in range(20) if u not in spec), reverse=True))
    assert sorted(degrees(kind, special, rest)) == sorted(deg)
    km_profile = kmax(degrees(kind, special, rest), list(special) + list(rest), NTRIP[kind])
    km_ties = [kmax(deg, t, NTRIP[kind], sorted(range(20), key=lambda v, s=s: (-deg[v], s * v))) for s in (1, -1)]
    b = kq_bound(kind, special, rest)
    out = {
        "KIND": kind, "SPECIAL": special, "REST": rest, "W": w, "T3": star + true, "TSTAR": star,
        "T_TRUE": true, "PATHS": paths, "S3_DIRECT": s3, "K_TRIO": k_trio, "K_QUAD": k_quad, "Q": q,
        "N1": n1, "KMAX_PROFILE_ORDER": km_profile, "KMAX_TIE_ORDERS": km_ties, "B": b,
        "S3_UB": s3_ub(kind, w, b),
        "IDENTITY_HOLDS": 6 * true == 10 * E + 3 * (k_trio + k_quad) + 8 * q - n1,
        "APEX_LEMMA_HOLDS": apex_ok,
        "KMAX_ADMISSIBLE": k_trio <= min([km_profile] + km_ties),
        "B_ADMISSIBLE": 3 * (k_trio + k_quad) + 8 * q <= b,
        "S3_UB_ADMISSIBLE": s3 <= s3_ub(kind, w, b),
    }
    if kind == "P_C":
        qd = [deg[u] for u in spec]
        out.update(TRUE_QUAD_CONTRIBUTION=3 * k_quad + 8 * q, OLD_QUAD_CONTRIBUTION=8 * (min(qd) - 3),
                   NEW_QUAD_TERM=quad_term(qd), QUAD_DEGREES=sorted(qd, reverse=True))
    return out


def quad_relax_max(a) -> int:
    """Exact max of 3*K_quad + 8*Q under the quad-local incidence constraints only (a relaxation)."""
    best = 0
    for q in range(min(a) + 1):
        r = [x - q for x in a]
        c = max(c for c in range(sum(r) // 3 + 1) if sum(max(0, c - x) for x in r) <= c)
        best = max(best, 8 * q + 3 * c)
    return best


def quad_exhaustive() -> dict:
    stats: Counter = Counter()
    worst = None
    for a in combinations_with_replacement(range(13), 4):
        f, rm = quad_term([x + 3 for x in a]), quad_relax_max(a)
        dom = all(5 <= x <= 10 for x in a)
        stats["ALL"] += 1
        stats["UNSAFE"] += rm > f
        stats["TIGHT"] += rm == f
        stats[f"RESIDUE_{(sum(a) - 4 * min(a)) % 3}"] += 1
        if dom:
            stats["DOMAIN"] += 1
            stats["DOMAIN_TIGHT"] += rm == f
            stats["DOMAIN_OLD_8M_UNDERCOUNTS"] += rm > 8 * min(a)
            if worst is None or rm - 8 * min(a) > worst[1]:
                worst = (list(a), rm - 8 * min(a))
    boundary = {
        "ALL_EQUAL_5555": [quad_term([8] * 4), quad_relax_max((5,) * 4)],
        "ALL_EQUAL_10_10_10_10": [quad_term([13] * 4), quad_relax_max((10,) * 4)],
        "CE_10_10_10_5": [quad_term([13, 13, 13, 8]), quad_relax_max((10, 10, 10, 5))],
        "Q0_FORCED_0_5_5_5": [quad_term([3, 8, 8, 8]), quad_relax_max((0, 5, 5, 5))],
    }
    return {"RANGE_A_I": [0, 12], "STATS": dict(stats), "MAX_OLD_UNDERCOUNT_IN_DOMAIN": worst,
            "BOUNDARY_FORMULA_VS_RELAXATION": boundary}


# ---- coverage of the earlier floor(W/3) cap stage ----------------------------------------

def w0(kind: str) -> int:
    """Smallest W whose wedge-cap S3 exceeds the threshold; s3_wedge is strictly increasing."""
    assert all(s3_wedge(kind, w + 1) > s3_wedge(kind, w) for w in range(1500))
    return next(w for w in range(1500) if s3_wedge(kind, w) > THRESH)


def profile_w_counts() -> dict[str, np.ndarray]:
    """#profiles by W for the full P_A/P_C domains, by multiset DP (no profile enumeration)."""
    n_max, s_max = 19, 69
    c = [comb(6 + v, 2) for v in range(7)]
    w_max = n_max * c[6]
    dp = np.zeros((n_max + 1, s_max + 1, w_max + 1), dtype=np.int64)
    dp[0, 0, 0] = 1
    for v in range(7):
        for n in range(1, n_max + 1):
            dp[n, v:, c[v]:] += dp[n - 1, : s_max + 1 - v, : w_max + 1 - c[v]]
    out = {k: np.zeros(w_max + 4 * comb(13, 2) + 1, dtype=np.int64) for k in ("P_A", "P_C")}
    for ts in range(6):
        ws = comb(5 + ts, 2)
        out["P_A"][ws : ws + w_max + 1] += dp[19, 69 - ts]
    for quad in combinations_with_replacement(range(6), 4):
        wq = sum(comb(8 + x, 2) for x in quad)
        out["P_C"][wq : wq + w_max + 1] += dp[16, 60 - sum(quad)]
    return out


def domain_sizes_by_partitions() -> dict[str, int]:
    """Second, numpy-free count of the profile domains (no W tracking)."""
    memo: dict[tuple[int, int, int], int] = {}

    def p(n: int, s: int, hi: int) -> int:
        if n == 0:
            return int(s == 0)
        if (n, s, hi) not in memo:
            memo[n, s, hi] = sum(p(n - 1, s - f, f) for f in range(min(hi, s), -1, -1) if f * n >= s)
        return memo[n, s, hi]

    return {"P_A": sum(p(19, 69 - ts, 6) for ts in range(6)),
            "P_C": sum(p(16, 60 - sum(q), 6) for q in combinations_with_replacement(range(6), 4))}


def in_domain(kind: str, sp: tuple, rest: tuple) -> bool:
    nonincr = all(x >= y for x, y in zip(rest, rest[1:])) and all(x >= y for x, y in zip(sp, sp[1:]))
    if kind == "P_A":
        return (len(sp) == 1 and 0 <= sp[0] <= 5 and len(rest) == 19 and nonincr
                and all(0 <= x <= 6 for x in rest) and sp[0] + sum(rest) == 69)
    return (kind == "P_C" and len(sp) == 4 and all(0 <= x <= 5 for x in sp) and len(rest) == 16
            and nonincr and all(0 <= x <= 6 for x in rest) and sum(sp) + sum(rest) == 60)


# ---- main ---------------------------------------------------------------------------------

def main() -> None:
    hashes = {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in FROZEN}
    frozen_ok = hashes == FROZEN
    assert frozen_ok, hashes
    r2 = json.loads((HERE / "k_bound_validation_r2.json").read_text())
    surv = json.loads((HERE / "survivors.json").read_text())

    weights = {
        "SINGLE": constants.co_win([frozenset(range(1, 7))]),
        "PAIR_OVERLAP0": constants.co_win([frozenset(range(1, 7)), frozenset(range(7, 13))]),
        "PAIR_OVERLAP1": constants.co_win([frozenset(range(1, 7)), frozenset([1, 7, 8, 9, 10, 11])]),
        "PATH": constants.co_win([frozenset(range(1, 7)), frozenset([1, 7, 8, 9, 10, 11]),
                                  frozenset([7, 13, 14, 15, 16, 17])]),
        "STAR": constants.co_win([frozenset(range(1, 7)), frozenset([1, 7, 8, 9, 10, 11]),
                                  frozenset([1, 13, 14, 15, 16, 17])]),
        "TRIANGLE": constants.co_win([frozenset(range(1, 7)), frozenset([1, 7, 8, 9, 10, 11]),
                                      frozenset([2, 7, 13, 14, 15, 16])]),
    }
    s1_s2 = 20 * weights["SINGLE"] - 190 * weights["PAIR_OVERLAP0"] - E * (
        weights["PAIR_OVERLAP1"] - weights["PAIR_OVERLAP0"])
    constants_ok = (s1_s2 == S1_MINUS_S2 and weights["PATH"] == 2800 and weights["STAR"] == 7000
                    and weights["TRIANGLE"] == 20272)

    ce_tickets = [frozenset(t) for t in r2["BOUND_ADMISSIBILITY"]["P_C_STEP_COUNTEREXAMPLE"]["tickets"]]
    configs = {"P_C_COUNTEREXAMPLE_R2": analyze(ce_tickets), "P_A_K12_K8_LIFT": analyze(k12_k8())}
    ce = configs["P_C_COUNTEREXAMPLE_R2"]
    quad = quad_exhaustive()
    pack_ok = (all(packing(k) == profiles_k.packing(k) for k in range(1, 21))
               and all(packing(k + 1) >= packing(k) for k in range(1, 20))
               and all(comb(k, 2) - 3 * schonheim(k) == 1 for k in range(5, 21, 6)))

    w0s = {k: w0(k) for k in TSTAR}
    wc = profile_w_counts()
    cover = {k: {"DOMAIN_PROFILES": int(wc[k].sum()), "W0": w0s[k],
                 "DOMAIN_W_GE_W0": int(wc[k][w0s[k]:].sum())} for k in TSTAR}
    sizes = domain_sizes_by_partitions()

    keys = set()
    acct = {k: Counter() for k in TSTAR}
    records_ok = kmax_match = True
    unresolved, top = [], []
    for i, r in enumerate(surv):
        kind, sp, rest = r["KIND"], tuple(r["SPECIAL"]), tuple(r["REST"])
        records_ok &= in_domain(kind, sp, rest) and (kind, sp, rest) not in keys
        keys.add((kind, sp, rest))
        deg, t = degrees(kind, sp, rest), list(sp) + list(rest)
        w = sum(comb(d, 2) for d in deg)
        records_ok &= w == r["W"] and w >= w0s[kind]
        km = kmax(deg, t, NTRIP[kind])
        kmax_match &= km == profiles_k.kmax(deg, t, NTRIP[kind])
        b = kq_bound(kind, sp, rest)
        ub = S1_MINUS_S2 + s3_ub(kind, w, b)
        a = acct[kind]
        a["INPUT"] += 1
        if ub <= INCUMBENT:
            a["PRUNED"] += 1
            a["PRUNED_AT_EQUALITY"] += ub == INCUMBENT
        else:
            a["REMAINING"] += 1
            unresolved.append(i)
            ub_combined = min(ub, S1_MINUS_S2 + s3_wedge(kind, w))
            top.append((ub_combined, ub, i, kind, list(sp), list(rest)))
        # Comparison only (never used for pruning): rational form, old coded bound, Schonheim-only D(k).
        a["REPAIRED_RATIONAL_PRUNED"] += 2800 * w + 11872 * Fraction(10 * E + b, 6) - 1400 * TSTAR[kind] <= THRESH
        old = 3 * km + (8 * (min(deg[:4]) - 3) if kind == "P_C" else 0)
        old_pruned = 2800 * w + 11872 * Fraction(10 * E + old, 6) - 1400 * TSTAR[kind] <= THRESH
        a["OLD_CODED_WOULD_PRUNE"] += old_pruned
        a["OLD_ONLY_PRUNE_REJECTED"] += old_pruned and ub > INCUMBENT
        a["SCHONHEIM_ONLY_PRUNED"] += S1_MINUS_S2 + s3_ub(kind, w, kq_bound(kind, sp, rest, schonheim)) <= INCUMBENT

    unresolved_sha = hashlib.sha256(",".join(map(str, unresolved)).encode()).hexdigest()
    top.sort(key=lambda x: (-x[0], x[2]))
    acct_out = {k: dict(sorted(v.items())) for k, v in acct.items()}
    accounting_ok = (all(acct[k][f] == EXPECTED[k][f] for k in EXPECTED for f in EXPECTED[k])
                     and unresolved_sha == EXPECTED_UNRESOLVED_SHA and len(surv) == 58480)
    coverage_ok = records_ok and all(cover[k]["DOMAIN_W_GE_W0"] == acct[k]["INPUT"]
                                     and cover[k]["DOMAIN_PROFILES"] == sizes[k] for k in TSTAR)
    excluded = sum(cover[k]["DOMAIN_PROFILES"] - cover[k]["DOMAIN_W_GE_W0"] for k in TSTAR)
    checks = {
        "FROZEN_INPUTS": frozen_ok,
        "CONSTANTS_REEVALUATED": constants_ok,
        "IDENTITY_ON_CONFIGS": all(c["IDENTITY_HOLDS"] for c in configs.values()),
        "APEX_LEMMA_ON_CONFIGS": all(c["APEX_LEMMA_HOLDS"] for c in configs.values()),
        "KMAX_ADMISSIBLE_ALL_TIE_ORDERS": all(c["KMAX_ADMISSIBLE"] for c in configs.values()),
        "B_AND_S3_UB_ADMISSIBLE": all(c["B_ADMISSIBLE"] and c["S3_UB_ADMISSIBLE"] for c in configs.values()),
        "OLD_UNDERCOUNT_REPRODUCED": ce["OLD_QUAD_CONTRIBUTION"] == 40 and ce["TRUE_QUAD_CONTRIBUTION"] == 55,
        "NEW_TERM_COVERS_COUNTEREXAMPLE": ce["NEW_QUAD_TERM"] >= ce["TRUE_QUAD_CONTRIBUTION"],
        "QUAD_TERM_GE_RELAXATION_EXHAUSTIVE": quad["STATS"]["UNSAFE"] == 0,
        "PACKING_TABLE_MATCHES_AND_MONOTONE": pack_ok,
        "KMAX_REIMPLEMENTATION_MATCHES_R1": kmax_match,
        "SURVIVOR_RECORDS_VALID_DISTINCT_W_GE_W0": records_ok,
        "ACCOUNTING_EXACT": accounting_ok,
        "CAP_STAGE_COVERAGE": coverage_ok,
    }
    bound_ok = all(v for k, v in checks.items() if k != "CAP_STAGE_COVERAGE")
    remaining = sum(acct[k]["REMAINING"] for k in TSTAR)
    if bound_ok and coverage_ok and remaining == 0:
        status = "PROVED_NO_GAIN_SHELL1"
    elif bound_ok:
        status = "CERTIFIED_POSTCAP_BOUND"
    else:
        status = "PARTIAL_BOUND_CERTIFIED"
    best = top[0] if top else None
    ru = resource.getrusage(resource.RUSAGE_SELF)
    result = {
        "TASK_ID": "B649_K20_V8_SHELL1_REPAIRED_K_BOUND_CERTIFICATION_R3",
        "CREATED": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "BASE": subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True,
                               text=True).stdout.strip(),
        "CANONICAL": {"K20_COUNT": INCUMBENT, "K20_SHA256": K20_SHA256, "S1_MINUS_S2_SHELL1": S1_MINUS_S2,
                      "S3_THRESHOLD": THRESH},
        "FROZEN_INPUTS_SHA256": hashes,
        "IMPLEMENTATION": {"PATH": Path(__file__).name,
                           "SHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        "FORMULA": {
            "IDENTITY": "6*T_true = 940 + 3K + 8Q - N1 (Shell-1, E = 94)",
            "B": "P_A: 3*kmax(deg,t,23);  P_C: 3*kmax(deg,t,20) + 8M + 3*floor((S-4M)/3), "
                 "M = min_i(deg_i-3), S = sum_i(deg_i-3) over the 4 quad tickets",
            "S3_UB": "2800*W + 11872*floor((940+B)/6) - 1400*Tstar  (Tstar: P_A 23, P_C 24)",
            "PRUNE": "307923840 + S3_UB <= 313263888 (equality = no strict gain)",
        },
        "PROOF": PROOF,
        "PROOF_ASSUMPTIONS": ASSUMPTIONS,
        "CONSTANTS_REEVALUATED_WITH_FROZEN_CO_WIN": {**weights, "S1_MINUS_S2": s1_s2},
        "OLD_COUNTEREXAMPLE": {
            "SOURCE": "k_bound_validation_r2.json BOUND_ADMISSIBILITY.P_C_STEP_COUNTEREXAMPLE.tickets",
            "OLD_QUAD_CONTRIBUTION": ce["OLD_QUAD_CONTRIBUTION"],
            "TRUE_QUAD_CONTRIBUTION": ce["TRUE_QUAD_CONTRIBUTION"],
            "NEW_QUAD_TERM": ce["NEW_QUAD_TERM"],
        },
        "DETERMINISTIC_CONFIG_CHECKS": configs,
        "QUAD_TERM_EXHAUSTIVE_RELAXATION_CHECK": quad,
        "PACKING_D_1_TO_20": [packing(k) for k in range(1, 21)],
        "CHECKS": checks,
        "ACCOUNTING": {
            "INPUT_CANDIDATES": len(surv),
            "BY_KIND": acct_out,
            "TOTAL_PRUNED": sum(acct[k]["PRUNED"] for k in TSTAR),
            "TOTAL_REMAINING": remaining,
            "NOTE": "Only PRUNED/REMAINING use the certified bound; REPAIRED_RATIONAL / OLD_CODED / "
                    "SCHONHEIM_ONLY are comparison counts. OLD_ONLY_PRUNE_REJECTED = records the unsafe "
                    "R1 P_C term would have pruned but the certified bound keeps.",
        },
        "UNRESOLVED_LOCATOR": {
            "SOURCE": "survivors.json 0-based array index; predicate 307923840 + S3_UB > 313263888",
            "COUNT": len(unresolved),
            "INDEX_LIST_SHA256": unresolved_sha,
            "INDEX_LIST_ENCODING": "sha256 of ascii comma-joined ascending indices",
            "TOP5_BY_UB": [{"index": x[2], "KIND": x[3], "SPECIAL": x[4], "REST": x[5],
                            "UB_K": x[1], "UB_MIN_K_WEDGE": x[0]} for x in top[:5]],
        },
        "BEST_VALID_UPPER_BOUND": best[0] if best else None,
        "BEST_K_ONLY_UPPER_BOUND": max(x[1] for x in top) if top else None,
        "GAP_VS_313263888": (best[0] - INCUMBENT) if best else None,
        "CAP_STAGE_COVERAGE": {
            "METHOD": "Multiset generating-function DP over the full profile domains (counts only, no "
                      "profile enumeration). Survivors are distinct, in-domain and have W >= W0; equal "
                      "cardinality => survivors.json == {domain profiles with W >= W0}, so every excluded "
                      "profile has W < W0 and is closed by T3 <= floor(W/3) alone.",
            "BY_KIND": cover,
            "TOTAL_DOMAIN_PROFILES": sum(cover[k]["DOMAIN_PROFILES"] for k in TSTAR),
            "DOMAIN_SIZES_BY_PARTITION_COUNT": sizes,
            "EXCLUDED_BEFORE_SURVIVORS": excluded,
            "PACKET_CLAIMED_EXCLUDED": 219712,
            "DELTA_VS_PACKET": excluded - 219712,
            "DELTA_NOTE": "Two independent counts of the profiles.py domain agree; the packet/R1-log figure "
                          "is short by this delta. Not a gap: coverage is proved for the whole counted "
                          "domain (every profile outside survivors.json has W < W0).",
            "STATUS": "CERTIFIED" if coverage_ok else "NOT_ESTABLISHED",
        },
        "REMAINING_PROOF_GAPS": [
            f"{remaining} survivor profiles (index-list sha {unresolved_sha[:12]}) have certified "
            f"UB > {INCUMBENT}; best UB {best[0] if best else None}. They need a closure method.",
            "Bonferroni constants (S1-S2, triple weights) rest on the frozen constants.co_win DP and R2's "
            "canonical-evaluator cross-check; R3 re-evaluates them with the same DP, not an independent one.",
            "Shell-1 only: overlap <= 1 and sum C(d,2) = 94. Other shells are out of scope.",
        ],
        "SCIENTIFIC_STATUS": status,
        "NO_CPSAT": True,
        "CPU_SECONDS": round(ru.ru_utime + ru.ru_stime, 2),
    }
    if checks["CAP_STAGE_COVERAGE"] and remaining:
        result["SHELL1_STATUS"] = "OPEN: only the remaining survivors are uncovered"
    OUT.write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps({"STATUS": status, "CHECKS": checks, "ACCOUNTING": acct_out, "COVER": cover,
                      "BEST": result["BEST_VALID_UPPER_BOUND"], "CPU": result["CPU_SECONDS"]}, indent=1))


PROOF = {
    "DEFINITIONS": {
        "G": "graph on the 20 tickets, u~v iff |u&v| = 1; E = 94 edges, deg_u = sum_{x in u}(d_x - 1)",
        "B_y, d_y": "tickets containing label y, d_y = |B_y|",
        "m_y(u)": "for u not in B_y: number of tickets in B_y adjacent to u",
        "T_true / Tstar": "graph triangles with 3 distinct edge labels / triples sharing one label; "
                          "T3 = T_true + Tstar, Tstar = sum_y C(d_y,3) = 23 (P_A), 24 (P_C)",
        "K, Q, N1": "#{(y,u): m_y(u) = 3}, = 4, = 1, over ALL labels y; K = K_trio (d_y=3) + K_quad (d_y=4)",
        "t_u": "number of frequency-3 labels in ticket u",
    },
    "HISTOGRAM": "n_d labels of frequency d: sum n_d = 49, sum d n_d = 120, sum d^2 n_d = 2*94 + 120 = 308 "
                 "=> sum (d-2)(d-3) n_d = 308 - 600 + 294 = 2. (d-2)(d-3) is 0 for d in {2,3}, 2 for d in "
                 "{1,4}, >= 6 otherwise, so exactly one label has d in {1,4}: P_A = 1^1 2^25 3^23 or "
                 "P_C = 2^28 3^20 4^1.",
    "PROFILE_DOMAIN": "P_A: deg_u = 6 + t_u - [u holds the singleton], singleton ticket t <= 5, others "
                      "t <= 6, sum t = 69. P_C: quad ticket deg = 3 + 2t + (5 - t) = 8 + t with t <= 5, "
                      "others deg = 6 + t with t <= 6, sum t = 60. Every legal configuration maps to one "
                      "(KIND, sorted SPECIAL, sorted REST) in this domain.",
    "IDENTITY": [
        "(i) If u not in B_y meets b, c in B_y, the labels u&b, u&c differ (a common one would lie in b&c "
        "= {y}, but y not in u), so {u,b,c} is a true triangle. A true triangle arises exactly from its 3 "
        "(edge label y, opposite vertex u) pairs, and the opposite vertex never holds y; star triples never "
        "arise (all three hold y). Hence 3*T_true = sum_y sum_{u notin B_y} C(m_y(u), 2).",
        "(ii) m_y(u) <= d_y <= 4, and for m in 0..4: 2*C(m,2) = m - [m=1] + 3[m=3] + 8[m=4] "
        "(values 0, 0, 2, 6, 12).",
        "(iii) sum_y sum_{u notin B_y} m_y(u) = sum_y sum_{b in B_y} (deg_b - (d_y - 1)) "
        "= 6*sum_b deg_b - sum_y d_y(d_y - 1) = 12E - 2E = 10E (|b| = 6; overlap <= 1 => E = sum C(d_y,2)).",
        "(iv) Doubling (i) and substituting (ii), (iii): 6*T_true = 10E + 3K + 8Q - N1 = 940 + 3K + 8Q - N1. "
        "Only d_y in {3,4} give m = 3, and only d_y = 4 gives m = 4 (Q = 0 in P_A).",
    ],
    "APEX_LEMMA": "For a trio label y = {b1,b2,b3}, each u with m_y(u) = 3 is a neighbour of every b_i outside "
                  "B_y, and b_i has exactly deg_{b_i} - 2 such neighbours, so #apexes(y) <= min_i deg_{b_i} - 2.",
    "KMAX_LEMMA": [
        "Fix any degree-descending order; charge each trio to its last vertex v (lowest degree), so its apex "
        "count is <= deg_v - 2 =: w_v; w is non-increasing and > 0 (deg >= 5). Let x_v = #trios charged to v.",
        "x_v <= t_v. Trios through v pairwise share only v (two shared tickets would share two labels), so "
        "their other pairs are disjoint pairs of earlier vertices: x_v <= floor(r_v/2).",
        "Prefix P_r = sum_{j<=r} x_j counts trios inside the first r+1 vertices: a linear 3-graph, so P_r <= "
        "D(r+1); each uses 3 trio incidences of the prefix, so P_r <= floor(T_r/3); and P_r <= ntrip.",
        "Greedy G_r = min(G_{r-1} + a_r, c_r) with a_r = min(t_r, floor(r/2)), c_r the prefix cap. By "
        "induction P_r <= min(P_{r-1} + a_r, c_r) <= G_r. Abel summation with w non-increasing, w >= 0: "
        "K_trio <= sum x_v w_v = sum_r P_r (w_r - w_{r+1}) <= sum_r G_r (w_r - w_{r+1}) = kmax.",
        "Caps are non-decreasing (asserted), so every greedy increment is >= 0.",
    ],
    "QUAD_LEMMA": [
        "Quad label q, B_q = {b1..b4}; a_i = deg_{b_i} - 3 = #neighbours of b_i outside B_q (the other three "
        "quad tickets are neighbours via q). Domain: t_i in 0..5 => a_i in 5..10.",
        "n_j = #{u notin B_q: m_q(u) = j}. Double counting B_q-to-outside edges: sum_j j*n_j = S, hence "
        "4Q + 3K_quad <= S. Every m = 4 ticket neighbours each b_i: Q <= M = min a_i.",
        "K_quad integer => 3K_quad + 8Q <= f(Q) = 8Q + 3*floor((S - 4Q)/3). f(Q+1) - f(Q) = 8 - 3j with "
        "j in {1,2}, i.e. 5 or 2 > 0, so f is maximised at Q = M (S - 4M >= 0): "
        "3K_quad + 8Q <= 8M + 3*floor((S - 4M)/3).",
        "The R1 term 8*qmax = 8M omits 3K_quad and is unsafe (counterexample 40 < 55).",
    ],
    "S3_BOUND": "B >= 3K + 8Q and N1 >= 0 => 6*T_true <= 940 + B; T_true integer => T_true <= "
                "floor((940+B)/6). S3 = 2800W + 11872*T3 - 13272*Tstar = 2800W + 11872*T_true - 1400*Tstar "
                "is increasing in T_true, so S3 <= S3_UB. Bonferroni-3: union <= S1 - S2 + S3.",
    "CAP_STAGE": "Each graph triangle owns its 3 wedges and a wedge determines its triple, so 3*T3 <= W. "
                 "s3_wedge(W) = 2800W + 11872*floor(W/3) - 13272*Tstar is strictly increasing, so the R1 "
                 "cap prunes exactly W < W0 (P_A 837, P_C 838). R1's extra edge cap is not needed.",
    "PACKING_UPPER_BOUND": "Only D(k) >= max linear triple systems on k points is needed. Schonheim: each point "
                           "lies in <= floor((k-1)/2) triples, so D <= floor(k*floor((k-1)/2)/3). For k = 5 "
                           "(mod 6), k-1 is even, so the leave (K_k minus the triangles) has all degrees even; "
                           "Schonheim-many triangles would leave exactly C(k,2) - 3*Schonheim = 1 edge (asserted "
                           "for k = 5, 11, 17), impossible for an even-degree graph, so D <= Schonheim - 1.",
}

ASSUMPTIONS = [
    "Shell-1 := 20 tickets of 6 labels from 1..49, pairwise overlap <= 1, sum_y C(d_y,2) = 94.",
    "Objective = OFFICIAL_ANY_PRIZE union count; Bonferroni-3 upper bound S1 - S2 + S3.",
    "S1 - S2 = 307923840 and triple weights PATH 2800 / STAR 7000 / TRIANGLE 20272 / <=1-edge 0 come from "
    "the frozen constants.co_win DP (re-evaluated here) and R2's canonical-evaluator cross-check.",
    "D(k) = Schonheim - [k = 5 mod 6] is used only as an upper bound, proved by PROOF.PACKING_UPPER_BOUND "
    "(no external theorem). The correction is load-bearing: see SCHONHEIM_ONLY_PRUNED.",
]


if __name__ == "__main__":
    main()
