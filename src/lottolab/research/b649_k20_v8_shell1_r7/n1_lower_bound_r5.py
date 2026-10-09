"""R5: profile-level lower bound on N1, applied once to the 6515 Shell-1 profiles R4 left open.

Run from this directory:  OMP_NUM_THREADS=1 nice -n 15 <python> -B n1_lower_bound_r5.py
Reads the frozen R4 implementation/result and the R1-R3 inputs (never writes them) and writes
n1_lower_bound_r5.json. Single process, no CP-SAT, no multiprocessing, CPU rlimit 120 s.
The only change to the certified R4 bound is N1 >= 0  ->  N1 >= L(profile) = L_single + L_pair
(PROOF.N1_LOWER_BOUND). kmax, R(a), the identity, constants and the S3 formula are reused verbatim.
"""

from __future__ import annotations

import os
import sys

sys.dont_write_bytecode = True
for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_var] = "1"

import hashlib  # noqa: E402
import json  # noqa: E402
import random  # noqa: E402
import resource  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402
from collections import Counter  # noqa: E402
from itertools import combinations  # noqa: E402
from math import comb  # noqa: E402
from pathlib import Path  # noqa: E402

resource.setrlimit(resource.RLIMIT_CPU, (120, resource.getrlimit(resource.RLIMIT_CPU)[1]))

HERE = Path(__file__).resolve().parent
OUT = HERE / "n1_lower_bound_r5.json"
FROZEN = {
    "k_quad_exact_bound_r4.py": "e9d7f55cdb991f0f3c3a6dd8405375e30eaba152f969b351505d0098bd1c6f22",
    "k_quad_exact_bound_r4.json": "a243c8e99cb4c7e5a18e641f59b341e2c66147cf767fdb201665ce9faf3420fd",
    "k_bound_certify_r3.py": "12f59d58ec77b9e64df02524bb62c910c6ac75ddc7353541e7882ddf2f5091b0",
    "k_bound_certification_r3.json": "669d18a0395e5472dac7c8ec4f7d8fbd25070e3437d20c3e4449c774f5dbbc74",
    "constants.py": "7a04ce5f17f9e4c7422c601b5a884c2a2ecf97f412a0da9beaa7553e0151d251",
    "profiles.py": "f106f9c106d99d91b745bfdece1f07d44e955adba1d355daa93e73a479c63739",
    "profiles_k.py": "bb6927c10023df07a81dc514304dada433862693a942b694e03431d74b081312",
    "survivors.json": "c7287b11ba801f195372fb8db98e52a80c3b975e3cb478795cc95308457dfec2",
    "k_bound_validation_r2.json": "2ca0110a611938acfe30259baaf922c9fa802f424538c86e2539123cebe70c06",
}
HASHES = {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in FROZEN}
if HASHES != FROZEN:  # stop; never rebuild R1-R4
    raise SystemExit(f"FROZEN_INPUT_MISMATCH {json.dumps(HASHES)}")

sys.path.insert(0, str(HERE))
import k_quad_exact_bound_r4 as r4  # noqa: E402  frozen R4 (gates R1-R3 itself), imported after the hash gate

r3 = r4.r3
INCUMBENT, S1_MINUS_S2, E = r3.INCUMBENT, r3.S1_MINUS_S2, r3.E
R4_REMAINING = {"P_A": 991, "P_C": 5524}
R4_REMAINING_SHA = "348bb7cf9cda537e65f332863bc21e0d28a65f909b82cd39645f0cf90a6da573"
R4_MAX_UB = 313_445_776
NEAR_UNITS = (1, 2)
RANDOM_SEED, RANDOM_CONFIGS_PER_KIND = 20261008, 150


# ---- N1 lower bound -------------------------------------------------------------------------

def pair_stubs(kind: str, special, rest) -> list[int]:
    """h_u = number of frequency-2 labels on ticket u, in r3.degrees order (special tickets first)."""
    if kind == "P_A":
        return [5 - special[0]] + [6 - t for t in rest]
    return [5 - t for t in special] + [6 - t for t in rest]


def l_pair(kind: str, deg: list[int], h: list[int]) -> int:
    """Lower bound on sum over pair labels {b1,b2} of |deg b1 - deg b2| (PROOF.L_PAIR), by threshold cuts."""
    quad = [kind == "P_C" and i < 4 for i in range(len(deg))]

    def inside(xs: list[int]) -> int:  # >= 2 * (#pair edges inside xs)
        cap = sum(min(h[u], sum(v != u and h[v] > 0 and not (quad[u] and quad[v]) for v in xs)) for u in xs)
        if any(quad[u] for u in xs):  # no quad-quad edge: every inside edge uses a non-quad stub
            cap = min(cap, 2 * sum(h[u] for u in xs if not quad[u]))
        return cap

    vals = sorted(set(deg))
    total = 0
    for lo, hi in zip(vals, vals[1:]):
        up = [i for i in range(len(deg)) if deg[i] >= hi]
        down = [i for i in range(len(deg)) if deg[i] < hi]
        h_up, h_down = sum(h[i] for i in up), sum(h[i] for i in down)
        cross = max(0, h_up - inside(up), h_down - inside(down))
        cross += (cross - h_up) % 2  # cross = h_up - 2 e(up) has the parity of h_up
        total += (hi - lo) * cross
    return total


def n1_bound(kind: str, special, rest) -> tuple[int, int, int]:
    """(L, L_single, L_pair) with N1 >= L for every legal configuration with this profile."""
    deg = r3.degrees(kind, special, rest)
    h = pair_stubs(kind, special, rest)
    assert sum(h) == 2 * (25 if kind == "P_A" else 28) and min(h) >= 0
    single = deg[0] if kind == "P_A" else 0  # the frequency-1 label contributes exactly deg(b_s)
    pair = l_pair(kind, deg, h)
    return single + pair, single, pair


def s3_ub5(kind: str, w: int, b: int, low: int) -> int:
    """R4 S3_UB with N1 >= low: T_true <= floor((10E + B - low)/6)."""
    return 2800 * w + 11872 * ((10 * E + b - low) // 6) - 1400 * r3.TSTAR[kind]


# ---- relaxation consistency (sanity only, never used for pruning) ------------------------------

def realize_pairs(kind: str, deg: list[int], h: list[int], by_cost: bool):
    """Greedy simple graph with degrees h, no quad-quad edge; returns sum |deg diff| or None."""
    quad = [kind == "P_C" and i < 4 for i in range(len(deg))]
    rem, edges = list(h), set()
    while any(rem):
        u = max(range(len(rem)), key=lambda i: (rem[i], deg[i], -i))
        cand = [v for v in range(len(rem)) if v != u and rem[v] and frozenset((u, v)) not in edges
                and not (quad[u] and quad[v])]
        if len(cand) < rem[u]:
            return None
        key = (lambda v: (abs(deg[u] - deg[v]), -rem[v], v)) if by_cost else (lambda v: (-rem[v], v))
        for v in sorted(cand, key=key)[: rem[u]]:
            edges.add(frozenset((u, v)))
            rem[v] -= 1
        rem[u] = 0
    return sum(abs(deg[a] - deg[b]) for a, b in map(tuple, edges))


# ---- legal configurations (deterministic admissibility checks) ---------------------------------

def random_config(rng: random.Random, kind: str):
    """Random legal Shell-1 configuration (tickets as label sets) or None if the greedy gets stuck."""
    covered: set[frozenset[int]] = set()
    if kind == "P_A":
        spec = [rng.randrange(20)]
    else:
        spec = rng.sample(range(20), 4)
        covered.update(frozenset(p) for p in combinations(spec, 2))
    cap = [6 - (u in spec) for u in range(20)]
    tdeg = [0] * 20
    trips: list[tuple[int, ...]] = []
    core = rng.sample(range(20), rng.randint(7, 14))  # concentrate trios to reach bimodal profiles
    ntrip = r3.NTRIP[kind]
    for _ in range(6000):
        if len(trips) == ntrip:
            break
        tr = tuple(rng.sample(core if rng.random() < 0.8 else range(20), 3))
        if all(tdeg[u] < cap[u] for u in tr) and not any(frozenset(p) in covered for p in combinations(tr, 2)):
            trips.append(tr)
            covered.update(frozenset(p) for p in combinations(tr, 2))
            for u in tr:
                tdeg[u] += 1
    if len(trips) < ntrip:
        return None
    rem = [cap[u] - tdeg[u] for u in range(20)]
    pairs: list[tuple[int, int]] = []
    while any(rem):
        top = max(rem)
        u = rng.choice([i for i in range(20) if rem[i] == top])
        cand = [v for v in range(20) if v != u and rem[v] and frozenset((u, v)) not in covered]
        if len(cand) < rem[u]:
            return None
        rng.shuffle(cand)
        for v in sorted(cand, key=lambda v: -rem[v])[: rem[u]]:
            pairs.append((u, v))
            covered.add(frozenset((u, v)))
            rem[v] -= 1
        rem[u] = 0
    blocks = [tuple(spec)] + trips + pairs
    assert len(blocks) == 49
    tickets: list[set[int]] = [set() for _ in range(20)]
    for label, blk in enumerate(blocks, 1):
        for u in blk:
            tickets[u].add(label)
    return [frozenset(t) for t in tickets]


def check_config(tickets: list[frozenset[int]], table: dict) -> dict:
    """Brute-force N1 by label frequency on a legal config and test every inequality of the R5 bound."""
    base = r3.analyze(tickets)  # asserts legality, histogram, Tstar; recomputes T_true, K, Q, N1
    kind, sp, rest = base["KIND"], tuple(base["SPECIAL"]), tuple(base["REST"])
    hold = {y: [u for u, t in enumerate(tickets) if y in t] for y in range(1, 50)}
    adj = [[u != v and len(tickets[u] & tickets[v]) == 1 for v in range(20)] for u in range(20)]
    deg = [sum(row) for row in adj]
    n1_by_d: Counter = Counter()
    pair_gap = 0
    for hs in hold.values():
        n1_by_d[len(hs)] += sum(sum(adj[u][b] for b in hs) == 1 for u in range(20) if u not in hs)
        if len(hs) == 2:
            pair_gap += abs(deg[hs[0]] - deg[hs[1]])
    single_deg = next((deg[hs[0]] for hs in hold.values() if len(hs) == 1), 0)
    low, low_single, low_pair = n1_bound(kind, sp, rest)
    pdeg = r3.degrees(kind, sp, rest)
    km = r3.kmax(pdeg, list(sp) + list(rest), r3.NTRIP[kind])
    b4 = 3 * km + table[tuple(sorted(d - 3 for d in pdeg[:4]))] if kind == "P_C" else 3 * km
    s3_bound = s3_ub5(kind, base["W"], b4, low)
    return {
        "KIND": kind, "SPECIAL": list(sp), "REST": list(rest), "W": base["W"], "T_TRUE": base["T_TRUE"],
        "N1": base["N1"], "N1_BY_FREQ": {str(k): v for k, v in sorted(n1_by_d.items())},
        "PAIR_LABEL_DEG_GAP_SUM": pair_gap, "L_SINGLE": low_single, "L_PAIR": low_pair, "L": low,
        "B_R4": b4, "S3_DIRECT": base["S3_DIRECT"], "S3_UB_R5": s3_bound,
        "N1_PARTITION_OK": sum(n1_by_d.values()) == base["N1"],
        "SINGLE_EXACT": n1_by_d[1] == single_deg == low_single,
        "PAIR_CHAIN_OK": n1_by_d[2] >= pair_gap >= low_pair,
        "N1_GE_L": base["N1"] >= low,
        "B_R4_ADMISSIBLE": 3 * (base["K_TRIO"] + base["K_QUAD"]) + 8 * base["Q"] <= b4,
        "IDENTITY_HOLDS": base["IDENTITY_HOLDS"],
        "S3_UB_R5_ADMISSIBLE": base["S3_DIRECT"] <= s3_bound,
    }


CONFIG_KEYS = ("N1_PARTITION_OK", "SINGLE_EXACT", "PAIR_CHAIN_OK", "N1_GE_L", "B_R4_ADMISSIBLE",
               "IDENTITY_HOLDS", "S3_UB_R5_ADMISSIBLE")


def config_checks(table: dict) -> dict:
    r2 = json.loads((HERE / "k_bound_validation_r2.json").read_text())
    named = {"P_C_COUNTEREXAMPLE_R2": [frozenset(t) for t in
                                       r2["BOUND_ADMISSIBILITY"]["P_C_STEP_COUNTEREXAMPLE"]["tickets"]],
             "P_A_K12_K8_LIFT": r3.k12_k8()}
    named_out = {k: check_config(v, table) for k, v in named.items()}
    rng = random.Random(RANDOM_SEED)
    stats: Counter = Counter()
    for kind in ("P_A", "P_C"):
        made = 0
        while made < RANDOM_CONFIGS_PER_KIND:
            stats[kind, "ATTEMPTS"] += 1
            tickets = random_config(rng, kind)
            if tickets is None:
                continue
            made += 1
            c = check_config(tickets, table)
            assert c["KIND"] == kind
            stats[kind, "CONFIGS"] += 1
            stats[kind, "ALL_CHECKS_PASS"] += all(c[k] for k in CONFIG_KEYS)
            stats[kind, "L_POSITIVE"] += c["L"] > 0
            stats[kind, "L_PAIR_POSITIVE"] += c["L_PAIR"] > 0
            stats[kind, "L_EQ_N1"] += c["L"] == c["N1"]
            stats[kind, "L_PAIR_EQ_GAP_SUM"] += c["L_PAIR"] == c["PAIR_LABEL_DEG_GAP_SUM"]
            stats[kind, "W_GE_W0"] += c["W"] >= r3.w0(kind)
            stats[kind, "MAX_L"] = max(stats[kind, "MAX_L"], c["L"])
            stats[kind, "MIN_N1_MINUS_L"] = min(stats.get((kind, "MIN_N1_MINUS_L"), 10**9), c["N1"] - c["L"])
    return {"NAMED": named_out, "RANDOM_SEED": RANDOM_SEED,
            "RANDOM": {f"{k}:{f}": v for (k, f), v in sorted(stats.items())}}


# ---- main -----------------------------------------------------------------------------------

def main() -> None:
    r4_result = json.loads((HERE / "k_quad_exact_bound_r4.json").read_text())
    surv = json.loads((HERE / "survivors.json").read_text())
    r4_inherited = (r4_result["SCIENTIFIC_STATUS"] == "PARTIAL_BOUND_CERTIFIED"
                    and all(r4_result["CHECKS"].values())
                    and r4_result["UNRESOLVED_LOCATOR"]["INDEX_LIST_SHA256"] == R4_REMAINING_SHA
                    and r4_result["MAX_VALID_UPPER_BOUND"] == R4_MAX_UB)

    table, qstats, qrows = r4.quad_table()
    table_matches_r4 = qrows == [{k: v for k, v in row.items()} for row in r4_result["QUAD_EXACT_TABLE"]]

    cfg = config_checks(table)
    named_ok = all(all(c[k] for k in CONFIG_KEYS) for c in cfg["NAMED"].values())
    random_ok = all(cfg["RANDOM"][f"{k}:ALL_CHECKS_PASS"] == cfg["RANDOM"][f"{k}:CONFIGS"]
                    == RANDOM_CONFIGS_PER_KIND for k in ("P_A", "P_C"))
    nonvacuous = cfg["NAMED"]["P_A_K12_K8_LIFT"]["L"] == cfg["NAMED"]["P_A_K12_K8_LIFT"]["N1"]
    admissible = named_ok and random_ok and nonvacuous

    # Reconstruct R4's open set exactly, then apply L once: near-threshold first, the rest second.
    rows = []
    r4_units: Counter = Counter()
    for i, r in enumerate(surv):
        kind, sp, rest = r["KIND"], tuple(r["SPECIAL"]), tuple(r["REST"])
        deg, t = r3.degrees(kind, sp, rest), list(sp) + list(rest)
        w = sum(comb(d, 2) for d in deg)
        if S1_MINUS_S2 + r3.s3_ub(kind, w, r3.kq_bound(kind, sp, rest)) <= INCUMBENT:
            continue
        km = r3.kmax(deg, t, r3.NTRIP[kind])
        b4 = 3 * km + table[tuple(sorted(d - 3 for d in deg[:4]))] if kind == "P_C" else 3 * km
        ub4 = S1_MINUS_S2 + r3.s3_ub(kind, w, b4)
        if ub4 <= INCUMBENT:
            continue
        ubw = S1_MINUS_S2 + r3.s3_wedge(kind, w)
        units = -(-(min(ub4, ubw) - INCUMBENT) // 11872)  # R4 T_TRUE_UNITS_STILL_NEEDED definition
        r4_units[f"{kind}:{units}"] += 1
        rows.append((i, kind, sp, rest, deg, w, b4, ub4, ubw, units))
    r4_idx = [x[0] for x in rows]
    r4_sha = hashlib.sha256(",".join(map(str, r4_idx)).encode()).hexdigest()
    r4_set_ok = (r4_sha == R4_REMAINING_SHA and len(surv) == 58480
                 and all(sum(x[1] == k for x in rows) == R4_REMAINING[k] for k in R4_REMAINING)
                 and dict(r4_units) == r4_result["UNRESOLVED_LOCATOR"]["T_TRUE_UNITS_STILL_NEEDED"])

    acct = {k: Counter() for k in r3.TSTAR}
    remaining_idx, top, need, l_hist = [], [], Counter(), Counter()
    relax = Counter()
    monotone_ok = True
    for phase in ("NEAR", "REST"):
        for i, kind, sp, rest, deg, w, b4, ub4, ubw, units in rows:
            if (units in NEAR_UNITS) != (phase == "NEAR"):
                continue
            low, low_single, low_pair = n1_bound(kind, sp, rest)
            h = pair_stubs(kind, sp, rest)
            costs = [c for c in (realize_pairs(kind, deg, h, True), realize_pairs(kind, deg, h, False))
                     if c is not None]
            relax["REALIZED"] += bool(costs)
            relax["L_PAIR_LE_REALIZED"] += bool(costs) and low_pair <= min(costs)
            relax["L_PAIR_EQ_REALIZED"] += bool(costs) and low_pair == min(costs)
            ub5 = S1_MINUS_S2 + s3_ub5(kind, w, b4, low) if admissible else ub4
            monotone_ok &= ub5 <= ub4
            c = acct[kind]
            c[f"{phase}_INPUT"] += 1
            c["L_SINGLE_POSITIVE"] += low_single > 0
            c["L_PAIR_POSITIVE"] += low_pair > 0
            c["T_TRUE_CAP_LOWERED"] += ub5 < ub4
            l_hist[f"{kind}:{min(low, 30)}"] += 1
            if ub5 <= INCUMBENT:
                c[f"{phase}_NEWLY_PRUNED"] += 1
                c["NEWLY_PRUNED_AT_EQUALITY"] += ub5 == INCUMBENT
            else:
                c["REMAINING"] += 1
                remaining_idx.append(i)
                best = min(ub5, ubw)
                top.append((best, ub5, ub4, i, kind, list(sp), list(rest), low, low_single, low_pair))
                need[(kind, -(-(best - INCUMBENT) // 11872))] += 1

    remaining_idx.sort()
    rem_sha = hashlib.sha256(",".join(map(str, remaining_idx)).encode()).hexdigest()
    top.sort(key=lambda x: (-x[0], x[3]))
    near_in = sum(acct[k]["NEAR_INPUT"] for k in r3.TSTAR)
    near_pruned = sum(acct[k]["NEAR_NEWLY_PRUNED"] for k in r3.TSTAR)
    newly = near_pruned + sum(acct[k]["REST_NEWLY_PRUNED"] for k in r3.TSTAR)
    remaining = sum(acct[k]["REMAINING"] for k in r3.TSTAR)
    checks = {
        "FROZEN_INPUTS": HASHES == FROZEN,
        "R4_RESULT_INHERITED": r4_inherited,
        "R4_QUAD_TABLE_REPRODUCED": table_matches_r4 and qstats["DOMAIN"] == 126,
        "R4_OPEN_SET_AND_UNITS_REPRODUCED": r4_set_ok,
        "NAMED_CONFIGS_ALL_INEQUALITIES": named_ok,
        "RANDOM_LEGAL_CONFIGS_ALL_INEQUALITIES": random_ok,
        "K12_K8_L_EQUALS_N1_NONVACUOUS": nonvacuous,
        "L_PAIR_LE_EVERY_REALIZED_RELAXATION": relax["L_PAIR_LE_REALIZED"] == relax["REALIZED"],
        "UB_MONOTONE_VS_R4": monotone_ok,
        "ACCOUNTING_CLOSES": newly + remaining == len(rows) == 6515,
    }
    proved = all(checks.values())
    best = top[0] if top else None
    if not proved:
        status = "NOT_PROVED"
    elif newly == 0:
        status = "NO_USEFUL_N1_BOUND"
    else:  # FULL_SHELL1_CLOSED is withheld: profiles remain and the Bonferroni constants lack an independent authority
        status = "PARTIAL_BOUND_CERTIFIED"
    ru = resource.getrusage(resource.RUSAGE_SELF)
    by_kind = {k: {"INPUT": acct[k]["NEAR_INPUT"] + acct[k]["REST_INPUT"],
                   "NEAR_INPUT": acct[k]["NEAR_INPUT"], "NEAR_NEWLY_PRUNED": acct[k]["NEAR_NEWLY_PRUNED"],
                   "REST_INPUT": acct[k]["REST_INPUT"], "REST_NEWLY_PRUNED": acct[k]["REST_NEWLY_PRUNED"],
                   "NEWLY_PRUNED_AT_EQUALITY": acct[k]["NEWLY_PRUNED_AT_EQUALITY"],
                   "REMAINING": acct[k]["REMAINING"], "L_SINGLE_POSITIVE": acct[k]["L_SINGLE_POSITIVE"],
                   "L_PAIR_POSITIVE": acct[k]["L_PAIR_POSITIVE"],
                   "T_TRUE_CAP_LOWERED": acct[k]["T_TRUE_CAP_LOWERED"]} for k in r3.TSTAR}
    result = {
        "TASK_ID": "B649_K20_V8_SHELL1_N1_LOWER_BOUND_R5",
        "CREATED": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "BASE": subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True,
                               text=True).stdout.strip(),
        "CANONICAL": {"K20_COUNT": INCUMBENT, "K20_SHA256": r3.K20_SHA256, "S1_MINUS_S2_SHELL1": S1_MINUS_S2,
                      "S3_THRESHOLD": r3.THRESH},
        "FROZEN_INPUTS_SHA256": HASHES,
        "IMPLEMENTATION": {"PATH": Path(__file__).name,
                           "SHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        "N1_DEFINITION_FROM_R3": r3.PROOF["DEFINITIONS"]["K, Q, N1"] + "; m_y(u) for u not in B_y = "
                                 "#tickets in B_y adjacent to u (r3.analyze counts every label 1..49, "
                                 "multiplicity one per (label, ticket) pair)",
        "FORMULA": {
            "CHANGE_VS_R4": "N1 >= 0  ->  N1 >= L = L_single + L_pair",
            "L_SINGLE": "P_A: deg(b_s) = 5 + t_s (singleton ticket);  P_C: 0",
            "L_PAIR": "sum over consecutive distinct degree values lo < hi of (hi - lo) * c_hi, c_hi = max(0, "
                      "h(U) - cap(U), h(D) - cap(D)) raised to the parity of h(U); U = {deg >= hi}, D = {deg < hi}, "
                      "h_u = #frequency-2 labels on u, cap(X) = sum_{u in X} min(h_u, #{v in X - u : h_v >= 1, "
                      "not both quad}), and cap(X) <= 2 * h(non-quad part of X) when X holds a quad ticket",
            "S3_UB": "2800*W + 11872*floor((940 + B_R4 - L)/6) - 1400*Tstar  (B_R4 = 3*kmax + R(a), unchanged)",
            "PRUNE": "307923840 + S3_UB <= 313263888 (equality = no strict gain)",
        },
        "PROOF": PROOF,
        "PROOF_ASSUMPTIONS": r3.ASSUMPTIONS,
        "ADMISSIBILITY_CHECKS_ON_LEGAL_CONFIGS": cfg,
        "RELAXATION_CONSISTENCY": {
            "NOTE": "Sanity only: a greedy simple graph with degrees h and no quad-quad edge (trio exclusions "
                    "ignored) is a feasible point of the relaxation L_pair lower-bounds; never used for pruning.",
            **dict(relax),
        },
        "CHECKS": checks,
        "NEAR_THRESHOLD": {
            "DEFINITION": "R4 T_TRUE_UNITS_STILL_NEEDED in {1, 2}: ceil((min(UB_R4, UB_wedge) - 313263888)/11872)",
            "INPUT": near_in,
            "NEWLY_PRUNED": near_pruned,
            "PACKET_FIGURE": 2825,
            "PACKET_FIGURE_NOTE": "R4 JSON gives P_A 244+212 + P_C 1581+1099 = 3136 profiles at 1-2 units; the "
                                  "packet's 2825 is not reproducible from the frozen R4 locator. All 3136 are "
                                  "evaluated in the near phase.",
        },
        "ACCOUNTING": {
            "INPUT_CANDIDATES": len(rows),
            "INPUT_INDEX_LIST_SHA256": r4_sha,
            "BY_KIND": by_kind,
            "TOTAL_NEWLY_PRUNED": newly,
            "TOTAL_REMAINING": remaining,
            "L_HISTOGRAM_CAPPED_30": dict(sorted(l_hist.items(), key=lambda kv: (kv[0][:3], int(kv[0][4:])))),
            "NOTE": "Applied once to R4's open set only (R4-pruned profiles stay pruned: L >= 0). Near-threshold "
                    "phase first, then one deterministic pass over the rest.",
        },
        "UNRESOLVED_LOCATOR": {
            "SOURCE": "survivors.json 0-based array index; predicate 307923840 + S3_UB_R5 > 313263888",
            "COUNT": len(remaining_idx),
            "INDEX_LIST_SHA256": rem_sha,
            "INDEX_LIST_ENCODING": "sha256 of ascii comma-joined ascending indices",
            "T_TRUE_UNITS_STILL_NEEDED": {f"{k}:{n}": v for (k, n), v in sorted(need.items())},
            "TOP5_BY_UB": [{"index": x[3], "KIND": x[4], "SPECIAL": x[5], "REST": x[6], "UB_R5": x[1],
                            "UB_R4": x[2], "UB_MIN_R5_WEDGE": x[0], "L": x[7], "L_SINGLE": x[8],
                            "L_PAIR": x[9]} for x in top[:5]],
        },
        "MAX_VALID_UPPER_BOUND": best[0] if best else None,
        "GAP_VS_313263888": (best[0] - INCUMBENT) if best else None,
        "REMAINING_PROOF_GAPS": [
            f"{remaining} profiles (index-list sha {rem_sha[:12]}) still have certified UB > {INCUMBENT}; "
            f"best UB {best[0] if best else None}.",
            "Bonferroni constants (S1-S2, triple weights) rest on the frozen constants.co_win DP and R2's "
            "canonical-evaluator cross-check (inherited; no independent authority yet).",
            "Shell-1 only: overlap <= 1 and sum C(d,2) = 94.",
        ],
        "SCIENTIFIC_STATUS": status,
        "NO_CPSAT": True,
        "MULTIPROCESSING": False,
        "CPU_SECONDS": round(ru.ru_utime + ru.ru_stime, 2),
    }
    OUT.write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps({"STATUS": status, "CHECKS": checks, "BY_KIND": by_kind, "NEAR": [near_in, near_pruned],
                      "RELAX": dict(relax), "RANDOM": cfg["RANDOM"], "MAX_UB": result["MAX_VALID_UPPER_BOUND"],
                      "GAP": result["GAP_VS_313263888"], "REMAINING_SHA": rem_sha,
                      "CPU": result["CPU_SECONDS"]}, indent=1))


PROOF = {
    "N1_DECOMPOSITION": "N1 = sum_y N1_y with N1_y = #{u notin B_y : m_y(u) = 1} (R3 DEFINITIONS; r3.analyze sums "
                        "over every label 1..49). Every N1_y >= 0, so any lower bounds on a subset of labels add "
                        "up to a lower bound on N1. Frequency-3 and frequency-4 labels are bounded by 0 (no claim).",
    "L_SINGLE": "P_A has exactly one frequency-1 label s, B_s = {b_s}. For u != b_s, m_s(u) = [u ~ b_s] in {0, 1}, so "
                "N1_s = deg(b_s) = 5 + t_s exactly (b_s holds s, t_s trio labels and 5 - t_s pair labels: deg = "
                "0 + 2t_s + (5 - t_s)). Hence N1 >= 5 > 0 on every P_A configuration. P_C has no frequency-1 label.",
    "PAIR_LABEL": [
        "Let y be a frequency-2 label, B_y = {b1, b2}. b1 & b2 = {y} (overlap <= 1), so b2 is a neighbour of b1 "
        "and b1 has exactly deg(b1) - 1 neighbours outside B_y; likewise b2.",
        "For u notin B_y, m_y(u) = [u ~ b1] + [u ~ b2]. With c = #common neighbours outside B_y, "
        "N1_y = (deg b1 - 1 - c) + (deg b2 - 1 - c). Since c <= min(deg b1, deg b2) - 1, "
        "N1_y >= |deg b1 - deg b2|.",
    ],
    "L_PAIR": [
        "The frequency-2 labels form a simple graph H2 on the 20 tickets (two labels on one ticket pair would be "
        "overlap 2). deg_H2(u) = h_u is fixed by the profile: P_A singleton ticket 5 - t_s, P_C quad ticket "
        "5 - t, every other ticket 6 - t. sum h = 50 (P_A, 25 pair labels) or 56 (P_C, 28). Quad tickets pairwise "
        "share the quad label, so H2 has no quad-quad edge. deg(u) is fixed by the profile (r3.degrees).",
        "Line-metric decomposition: for distinct degree values v_1 < ... < v_k and U_j = {deg >= v_{j+1}}, "
        "sum_{e in H2} |deg u - deg v| = sum_j (v_{j+1} - v_j) * cross_j, cross_j = #H2 edges between U_j and "
        "its complement D_j (an edge with degrees lo < hi crosses exactly the cuts between them).",
        "cross_j = h(U_j) - 2 e(U_j) = h(D_j) - 2 e(D_j). H2 is simple and a ticket with h_v = 0 has no H2 edge, "
        "so u in X has at most min(h_u, #{v in X - u : h_v >= 1, not both quad}) H2-neighbours inside X; summing, "
        "2 e(X) <= cap(X). With no quad-quad edge every edge inside X has a non-quad endpoint, so e(X) <= "
        "h(non-quad part of X). Hence cross_j >= h(X) - cap(X) for X in {U_j, D_j}; cross_j >= 0; cross_j has "
        "the parity of h(U_j). The coded c_j is the least integer meeting all of these, so cross_j >= c_j.",
        "Therefore sum_{pair labels} N1_y >= sum_{e in H2} |deg u - deg v| >= sum_j (v_{j+1} - v_j) c_j = L_pair. "
        "This is a minimum over a relaxation (trio co-membership exclusions dropped), valid for every legal "
        "configuration with the profile; no degree configuration is excluded and no sampling is used.",
    ],
    "S3_BOUND": "6*T_true = 940 + 3K + 8Q - N1 (R3) with 3K + 8Q <= B_R4 (R4) and N1 >= L gives 6*T_true <= "
                "940 + B_R4 - L; T_true integer => T_true <= floor((940 + B_R4 - L)/6). S3 = 2800W + 11872*T_true "
                "- 1400*Tstar is increasing in T_true. Prune iff 307923840 + S3_UB <= 313263888; equality is a tie, "
                "never a strict gain.",
    "INHERITANCE": "L >= 0, so UB_R5 <= UB_R4 and every R4-pruned profile stays pruned; only R4's open set (6515, "
                   "sha 348bb7cf) is re-evaluated. kmax, R(a), the identity, the packing bound, the constants and "
                   "the S3 formula are reused verbatim from the hash-pinned R3/R4 modules.",
}


if __name__ == "__main__":
    main()
