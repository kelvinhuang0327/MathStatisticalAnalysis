"""R4: exact worst-case quad term, applied once to the 6841 Shell-1 profiles R3 left open.

Run from this directory:  nice -n 15 <python> -B k_quad_exact_bound_r4.py
Reads the frozen R3 implementation/result and the R1/R2 inputs (never writes them) and writes
k_quad_exact_bound_r4.json. Single process, no CP-SAT, no multiprocessing.
The only change to the certified R3 bound is the P_C quad term: 8M + 3*floor((S - 4M)/3) is replaced by
R(a), the exact maximum of 3*K_quad + 8*Q over the quad-local incidence relaxation (PROOF.QUAD_EXACT).
Everything else (identity, kmax, packing, constants, S3 formula) is reused verbatim from the hash-pinned R3.
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
from itertools import combinations_with_replacement  # noqa: E402
from math import comb  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "k_quad_exact_bound_r4.json"
FROZEN = {
    "k_bound_certify_r3.py": "12f59d58ec77b9e64df02524bb62c910c6ac75ddc7353541e7882ddf2f5091b0",
    "k_bound_certification_r3.json": "669d18a0395e5472dac7c8ec4f7d8fbd25070e3437d20c3e4449c774f5dbbc74",
    "constants.py": "7a04ce5f17f9e4c7422c601b5a884c2a2ecf97f412a0da9beaa7553e0151d251",
    "profiles.py": "f106f9c106d99d91b745bfdece1f07d44e955adba1d355daa93e73a479c63739",
    "profiles_k.py": "bb6927c10023df07a81dc514304dada433862693a942b694e03431d74b081312",
    "survivors.json": "c7287b11ba801f195372fb8db98e52a80c3b975e3cb478795cc95308457dfec2",
    "k_bound_validation_r2.json": "2ca0110a611938acfe30259baaf922c9fa802f424538c86e2539123cebe70c06",
}
HASHES = {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in FROZEN}
if HASHES != FROZEN:  # stop; never rebuild R3
    raise SystemExit(f"FROZEN_INPUT_MISMATCH {json.dumps(HASHES)}")

sys.path.insert(0, str(HERE))
import k_bound_certify_r3 as r3  # noqa: E402  frozen R3 bound pieces, imported only after the hash gate

INCUMBENT, S1_MINUS_S2, E = r3.INCUMBENT, r3.S1_MINUS_S2, r3.E
A_DOMAIN = range(5, 11)  # a_i = deg_i - 3 = 5 + t_i, t_i in 0..5 for the four quad tickets
R3_OPEN = {"P_A": 991, "P_C": 5850}

# Box for the exhaustive IP: x_j <= X - x_i <= a_i - q <= 10 for any i != j, and q <= min(a) <= 10.
_GRID = np.stack(np.meshgrid(*[np.arange(11)] * 4, indexing="ij"), -1).reshape(-1, 4)
_GRID_X = _GRID.sum(1)


# ---- exact quad term ------------------------------------------------------------------------

def quad_exact(a, cap16: bool = False) -> int:
    """max 8q + 3X over integers q, x_1..x_4 >= 0 with q + X - x_i <= a_i (X = sum x), exhaustively.

    cap16 adds the necessary condition q + X + pads <= 16 outside tickets, pads >= max(max s, ceil(sum s/2))
    for column slack s; it is a diagnostic only (never used for pruning).
    """
    av = np.asarray(a)
    assert av.shape == (4,) and av.max() <= 10 and av.min() >= 0
    best = 0
    for q in range(int(av.min()) + 1):
        use = q + _GRID_X[:, None] - _GRID
        ok = (use <= av).all(1)
        if cap16:
            s = av - use
            ok &= q + _GRID_X + np.maximum(s.max(1), (s.sum(1) + 1) // 2) <= 16
        if ok.any():
            best = max(best, int((8 * q + 3 * _GRID_X[ok]).max()))
    return best


def quad_table() -> tuple[dict, dict, list]:
    """R(a) on every reachable sorted a-vector, cross-checked against R3's e_i formulation."""
    table, stats, rows = {}, Counter(), []
    for a in combinations_with_replacement(A_DOMAIN, 4):
        bf, rel, cf = quad_exact(a), r3.quad_relax_max(a), r3.quad_term([x + 3 for x in a])
        c16 = quad_exact(a, cap16=True)
        table[a] = bf
        stats["DOMAIN"] += 1
        stats["BRUTEFORCE_EQ_R3_RELAX"] += bf == rel
        stats["EXACT_LE_CLOSED_FORM"] += bf <= cf
        stats["TIGHTER_THAN_CLOSED_FORM"] += bf < cf
        stats["EQUAL_TO_CLOSED_FORM"] += bf == cf
        stats["CAP16_BINDS"] += c16 < bf
        stats[f"CLOSED_FORM_MINUS_EXACT_{cf - bf}"] += 1
        rows.append({"a": list(a), "EXACT": bf, "CLOSED_FORM": cf})
    return table, dict(sorted(stats.items())), rows


# ---- deterministic legal-config check ---------------------------------------------------------

def quad_incidence(tickets: list[frozenset[int]], table: dict) -> dict:
    """On a legal P_C config: build N_u for every outside ticket and check the IP constraints directly."""
    hold = {y: [u for u, t in enumerate(tickets) if y in t] for y in range(1, 50)}
    (bq,) = [h for h in hold.values() if len(h) == 4]
    adj = [[u != v and len(tickets[u] & tickets[v]) == 1 for v in range(20)] for u in range(20)]
    deg = [sum(row) for row in adj]
    a = [deg[b] - 3 for b in bq]
    outside = [u for u in range(20) if u not in bq]
    nsets = [frozenset(i for i, b in enumerate(bq) if adj[u][b]) for u in outside]
    cols = [sum(i in n for n in nsets) for i in range(4)]
    q = sum(len(n) == 4 for n in nsets)
    x = [sum(n == frozenset(range(4)) - {i} for n in nsets) for i in range(4)]
    feasible = all(q + sum(x) - x[i] <= a[i] for i in range(4))
    true = 3 * sum(x) + 8 * q
    exact = table[tuple(sorted(a))]
    return {"A": a, "COLUMN_SUMS": cols, "COLUMN_SUMS_EQ_A": cols == a, "Q": q, "X": x, "IP_FEASIBLE": feasible,
            "TRUE_QUAD_CONTRIBUTION": true, "EXACT_TERM": exact, "CLOSED_FORM_TERM": r3.quad_term([d + 3 for d in a]),
            "ADMISSIBLE": feasible and cols == a and true <= exact}


# ---- main -----------------------------------------------------------------------------------

def main() -> None:
    r3_result = json.loads((HERE / "k_bound_certification_r3.json").read_text())
    r2 = json.loads((HERE / "k_bound_validation_r2.json").read_text())
    surv = json.loads((HERE / "survivors.json").read_text())
    r3_inherited = (r3_result["SCIENTIFIC_STATUS"] == "CERTIFIED_POSTCAP_BOUND"
                    and all(r3_result["CHECKS"].values())
                    and r3_result["UNRESOLVED_LOCATOR"]["INDEX_LIST_SHA256"] == r3.EXPECTED_UNRESOLVED_SHA
                    and r3_result["BEST_VALID_UPPER_BOUND"] == 313_445_776)

    table, qstats, qrows = quad_table()

    ce_tickets = [frozenset(t) for t in r2["BOUND_ADMISSIBILITY"]["P_C_STEP_COUNTEREXAMPLE"]["tickets"]]
    ce = quad_incidence(ce_tickets, table)
    ce_r3 = r3.analyze(ce_tickets)
    ce_ok = ce["ADMISSIBLE"] and ce["TRUE_QUAD_CONTRIBUTION"] == ce_r3["TRUE_QUAD_CONTRIBUTION"] == 55

    r3_acct = {k: Counter() for k in r3.TSTAR}
    acct = {k: Counter() for k in r3.TSTAR}
    open_idx, remaining_idx, top, need = [], [], [], Counter()
    domain_ok = monotone_ok = r3_formula_ok = True
    for i, r in enumerate(surv):
        kind, sp, rest = r["KIND"], tuple(r["SPECIAL"]), tuple(r["REST"])
        deg, t = r3.degrees(kind, sp, rest), list(sp) + list(rest)
        w = sum(comb(d, 2) for d in deg)
        km = r3.kmax(deg, t, r3.NTRIP[kind])
        b3 = r3.kq_bound(kind, sp, rest)
        if kind == "P_C":
            a = tuple(sorted(d - 3 for d in deg[:4]))
            domain_ok &= a in table
            r3_formula_ok &= b3 == 3 * km + r3.quad_term(deg[:4])
        ub3 = S1_MINUS_S2 + r3.s3_ub(kind, w, b3)
        r3_acct[kind]["PRUNED" if ub3 <= INCUMBENT else "REMAINING"] += 1
        if ub3 <= INCUMBENT:
            continue
        open_idx.append(i)
        b4 = 3 * km + table[a] if kind == "P_C" else b3  # P_A: Q = K_quad = 0, B unchanged
        ub4 = S1_MINUS_S2 + r3.s3_ub(kind, w, b4)
        monotone_ok &= b4 <= b3 and ub4 <= ub3
        c = acct[kind]
        c["INPUT"] += 1
        c["QUAD_TERM_TIGHTENED"] += b4 < b3
        c["T_TRUE_CAP_LOWERED"] += (10 * E + b4) // 6 < (10 * E + b3) // 6
        if ub4 <= INCUMBENT:
            c["NEWLY_PRUNED"] += 1
            c["NEWLY_PRUNED_AT_EQUALITY"] += ub4 == INCUMBENT
        else:
            c["REMAINING"] += 1
            remaining_idx.append(i)
            ubw = S1_MINUS_S2 + r3.s3_wedge(kind, w)
            top.append((min(ub4, ubw), ub4, ub3, i, kind, list(sp), list(rest)))
            need[(kind, -(-(min(ub4, ubw) - INCUMBENT) // 11872))] += 1

    open_sha = hashlib.sha256(",".join(map(str, open_idx)).encode()).hexdigest()
    rem_sha = hashlib.sha256(",".join(map(str, remaining_idx)).encode()).hexdigest()
    top.sort(key=lambda x: (-x[0], x[3]))
    p_c_all = r3_acct["P_C"]["PRUNED"] + r3_acct["P_C"]["REMAINING"]
    checks = {
        "FROZEN_INPUTS": HASHES == FROZEN,
        "R3_RESULT_INHERITED": r3_inherited,
        "R3_OPEN_SET_REPRODUCED": (open_sha == r3.EXPECTED_UNRESOLVED_SHA and len(surv) == 58480
                                   and all(r3_acct[k]["REMAINING"] == R3_OPEN[k] for k in R3_OPEN)
                                   and all(acct[k]["INPUT"] == R3_OPEN[k] for k in R3_OPEN)),
        "R3_P_C_FORMULA_REPRODUCED": r3_formula_ok,
        "QUAD_DOMAIN_IS_126": qstats["DOMAIN"] == comb(9, 4) == 126,
        "EVERY_P_C_SURVIVOR_A_IN_DOMAIN": domain_ok and p_c_all == 53875,
        "BRUTEFORCE_EQ_R3_RELAX_ALL_DOMAIN": qstats["BRUTEFORCE_EQ_R3_RELAX"] == 126,
        "EXACT_LE_CLOSED_FORM_ALL_DOMAIN": qstats["EXACT_LE_CLOSED_FORM"] == 126,
        "R3_TIGHTER_COUNT_65_REPRODUCED": qstats["TIGHTER_THAN_CLOSED_FORM"] == 65 and qstats["EQUAL_TO_CLOSED_FORM"] == 61,
        "CAP16_NONBINDING": qstats["CAP16_BINDS"] == 0,
        "CE_CONFIG_ADMISSIBLE": ce_ok,
        "UB_MONOTONE_VS_R3": monotone_ok,
        "P_A_UNCHANGED": acct["P_A"]["QUAD_TERM_TIGHTENED"] == 0,
    }
    proved = all(checks.values())
    remaining = sum(acct[k]["REMAINING"] for k in r3.TSTAR)
    newly = sum(acct[k]["NEWLY_PRUNED"] for k in r3.TSTAR)
    best = top[0] if top else None
    if not proved:
        status = "NOT_PROVED"
    else:  # FULL_SHELL1_CLOSED is withheld: the Bonferroni constants still lack an independent authority
        status = "PARTIAL_BOUND_CERTIFIED"
    ru = resource.getrusage(resource.RUSAGE_SELF)
    by_kind = {k: {"INPUT": acct[k]["INPUT"], "NEWLY_PRUNED": acct[k]["NEWLY_PRUNED"],
                   "NEWLY_PRUNED_AT_EQUALITY": acct[k]["NEWLY_PRUNED_AT_EQUALITY"],
                   "REMAINING": acct[k]["REMAINING"], "QUAD_TERM_TIGHTENED": acct[k]["QUAD_TERM_TIGHTENED"],
                   "T_TRUE_CAP_LOWERED": acct[k]["T_TRUE_CAP_LOWERED"]} for k in r3.TSTAR}
    result = {
        "TASK_ID": "B649_K20_V8_SHELL1_EXACT_QUAD_BOUND_TIGHTENING_R4",
        "CREATED": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "BASE": subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True,
                               text=True).stdout.strip(),
        "CANONICAL": {"K20_COUNT": INCUMBENT, "K20_SHA256": r3.K20_SHA256, "S1_MINUS_S2_SHELL1": S1_MINUS_S2,
                      "S3_THRESHOLD": r3.THRESH},
        "FROZEN_INPUTS_SHA256": HASHES,
        "IMPLEMENTATION": {"PATH": Path(__file__).name,
                           "SHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        "FORMULA": {
            "CHANGE_VS_R3": "P_C only: quad term 8M + 3*floor((S-4M)/3)  ->  R(a), a = sorted(deg_i - 3) of the "
                            "4 quad tickets",
            "R": "R(a) = max 8q + 3*(x1+x2+x3+x4) s.t. q + X - x_i <= a_i (i = 1..4), q, x_i >= 0 integers",
            "B": "P_A: 3*kmax(deg,t,23) (unchanged);  P_C: 3*kmax(deg,t,20) + R(a)",
            "S3_UB": "2800*W + 11872*floor((940+B)/6) - 1400*Tstar  (R3, unchanged)",
            "PRUNE": "307923840 + S3_UB <= 313263888 (equality = no strict gain)",
        },
        "PROOF": PROOF,
        "PROOF_ASSUMPTIONS": r3.ASSUMPTIONS,
        "QUAD_EXACT_TABLE_STATS": qstats,
        "QUAD_EXACT_TABLE": qrows,
        "DETERMINISTIC_CONFIG_CHECK_R2_COUNTEREXAMPLE": ce,
        "CHECKS": checks,
        "ACCOUNTING": {
            "INPUT_CANDIDATES": len(open_idx),
            "INPUT_INDEX_LIST_SHA256": open_sha,
            "BY_KIND": by_kind,
            "TOTAL_NEWLY_PRUNED": newly,
            "TOTAL_REMAINING": remaining,
            "R3_FULL_REPRODUCTION": {k: dict(sorted(v.items())) for k, v in r3_acct.items()},
            "NOTE": "Applied once to R3's open set only. Every R3-pruned profile stays pruned (UB_R4 <= UB_R3). "
                    "QUAD_TERM_TIGHTENED = R(a) < closed form; T_TRUE_CAP_LOWERED = floor((940+B)/6) dropped.",
        },
        "UNRESOLVED_LOCATOR": {
            "SOURCE": "survivors.json 0-based array index; predicate 307923840 + S3_UB_R4 > 313263888",
            "COUNT": len(remaining_idx),
            "INDEX_LIST_SHA256": rem_sha,
            "INDEX_LIST_ENCODING": "sha256 of ascii comma-joined ascending indices",
            "T_TRUE_UNITS_STILL_NEEDED": {f"{k}:{n}": v for (k, n), v in sorted(need.items())},
            "T_TRUE_UNITS_NOTE": "ceil((min(UB_R4, UB_wedge) - 313263888) / 11872): how many fewer true triangles "
                                 "each remaining profile must be shown to have.",
            "TOP5_BY_UB": [{"index": x[3], "KIND": x[4], "SPECIAL": x[5], "REST": x[6], "UB_R4": x[1],
                            "UB_R3": x[2], "UB_MIN_R4_WEDGE": x[0]} for x in top[:5]],
        },
        "MAX_VALID_UPPER_BOUND": best[0] if best else None,
        "GAP_VS_313263888": (best[0] - INCUMBENT) if best else None,
        "REMAINING_PROOF_GAPS": [
            f"{remaining} profiles (index-list sha {rem_sha[:12]}) still have certified UB > {INCUMBENT}; "
            f"best UB {best[0] if best else None}.",
            "Bonferroni constants (S1-S2, triple weights) rest on the frozen constants.co_win DP and R2's "
            "canonical-evaluator cross-check (inherited from R3; no independent authority yet).",
            "Shell-1 only: overlap <= 1 and sum C(d,2) = 94.",
        ],
        "SCIENTIFIC_STATUS": status,
        "NO_CPSAT": True,
        "MULTIPROCESSING": False,
        "CPU_SECONDS": round(ru.ru_utime + ru.ru_stime, 2),
    }
    OUT.write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps({"STATUS": status, "CHECKS": checks, "BY_KIND": by_kind, "QSTATS": qstats,
                      "MAX_UB": result["MAX_VALID_UPPER_BOUND"], "GAP": result["GAP_VS_313263888"],
                      "REMAINING_SHA": rem_sha, "CPU": result["CPU_SECONDS"]}, indent=1))


PROOF = {
    "QUAD_EXACT": [
        "Fix a legal P_C configuration, quad label q, B_q = {b1..b4}. b_i & b_j = {q}, so the three other quad "
        "tickets are neighbours of b_i via q only, and every other neighbour shares exactly one label with b_i: "
        "a_i := deg(b_i) - 3 is exactly the number of neighbours of b_i outside B_q (R3 QUAD_LEMMA).",
        "For u not in B_q let N_u = {i : u ~ b_i}, so m_q(u) = |N_u|. Column sums: sum_u [i in N_u] = a_i.",
        "Let Q = #{u : |N_u| = 4}, x_i = #{u : N_u = [4] - {i}}, K_quad = X = sum x_i. Tickets with |N_u| <= 2 "
        "add >= 0 to every column, so Q + X - x_i <= a_i for each i; all quantities are non-negative integers.",
        "Hence (Q, x) is feasible for IP(a) and 3*K_quad + 8*Q = 8Q + 3X <= R(a). This is a statement about "
        "every legal configuration with this quad vector; no sampling is involved.",
        "Exhaustiveness: q <= a_i - (X - x_i) <= min(a) and, for i != j, x_j <= X - x_i <= a_i - q <= 10. "
        "quad_exact enumerates q in 0..min(a) and x in 0..10^4, which contains every feasible point, so R(a) "
        "is computed exactly.",
        "Second formulation (R3 quad_relax_max): for fixed q, c = X is feasible iff some x >= 0 with sum c has "
        "x_i >= c - r_i (r_i = a_i - q), i.e. sum_i max(0, c - r_i) <= c. Both evaluations agree on all 126 "
        "domain vectors.",
        "Tightness (not needed for validity): any IP-feasible point is realised by an abstract incidence "
        "system with column sums a (pad slack with |N_u| <= 2 tickets). Adding the necessary condition "
        "'at most 16 outside tickets' (pads >= max(max slack, ceil(sum slack / 2))) lowers R on 0 of the 126 "
        "vectors, so R is the exact worst case under that constraint as well.",
    ],
    "DOMAIN": "P_C quad ticket = q (freq 4) + 5 labels of freq 2 or 3 (P_C has no other freq-1/4 label), so "
              "deg = 3 + 2t + (5 - t) = 8 + t, t in 0..5, a_i in 5..10. Sorted a-vectors: C(6+3, 4) = 126. "
              "R depends only on the multiset of a (the IP is symmetric under index permutation). Every P_C "
              "record in survivors.json maps into this table (checked for all 53875, not only the open 5850).",
    "INHERITANCE": "R(a) <= 8M + 3*floor((S-4M)/3) on all 126 vectors, so B_R4 <= B_R3 and UB_R4 <= UB_R3: every "
                   "R3-pruned profile stays pruned and only R3's open set needs re-evaluation. The identity "
                   "6*T_true = 940 + 3K + 8Q - N1, the apex/kmax lemma, the packing bound, the constants and the "
                   "S3 formula are reused verbatim from the hash-pinned R3 module.",
    "S3_BOUND": "3*kmax >= 3*K_trio and R(a) >= 3*K_quad + 8*Q give B_R4 >= 3K + 8Q; N1 >= 0 => 6*T_true <= "
                "940 + B_R4; T_true integer => T_true <= floor((940 + B_R4)/6). S3 is increasing in T_true, so "
                "S3 <= S3_UB. Prune iff 307923840 + S3_UB <= 313263888; equality is a tie, never a strict gain.",
    "P_A": "P_A has no frequency-4 label, so Q = K_quad = 0, B is unchanged and P_A_NEWLY_PRUNED = 0 by "
           "construction.",
}


if __name__ == "__main__":
    main()
