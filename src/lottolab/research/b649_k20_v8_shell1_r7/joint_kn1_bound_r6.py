"""R6: one joint bound on 3K + 8Q - N1, applied once to the 2791 Shell-1 profiles R5 left open.

Run from this directory:  OMP_NUM_THREADS=1 nice -n 15 <python> -B joint_kn1_bound_r6.py
Reads the frozen R1-R5 sources/results (never writes them) and writes joint_kn1_bound_r6.json.
Single process, no CP-SAT, no multiprocessing, CPU rlimit 120 s (set by the imported, hash-pinned R5 module).
Change vs R5: the separate pieces 3K + 8Q <= B_R4 (3*kmax + R(a)) and N1 >= L are replaced by one bound on
sum_y (3K_y + 8Q_y - N1_y): every trio/quad label is bounded together with its own N1_y (PROOF.LABEL_TERM), the
unknown trio labels are aggregated over degree level sets (PROOF.TRIO_LEVELS), and the pair/singleton labels keep
R5's L_pair/L_single verbatim. Identity, constants and the S3 formula are reused from the pinned R3 module.
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
from functools import lru_cache  # noqa: E402
from itertools import combinations, combinations_with_replacement  # noqa: E402
from math import comb  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "joint_kn1_bound_r6.json"
FROZEN = {
    "n1_lower_bound_r5.py": "e7e708b68fb8f10282874260399ea22f11001cf3e606d36a540ab93995836700",
    "n1_lower_bound_r5.json": "8ce144b1ec78eb1f868c8d6f76814a54dad232e1c9750c21de22df7466c97ed9",
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
if HASHES != FROZEN:  # stop; never rebuild R1-R5
    raise SystemExit(f"FROZEN_INPUT_MISMATCH {json.dumps(HASHES)}")

sys.path.insert(0, str(HERE))
import n1_lower_bound_r5 as r5  # noqa: E402  frozen R5 (gates R1-R4 itself, sets RLIMIT_CPU 120 s)

r4, r3 = r5.r4, r5.r3
INCUMBENT, S1_MINUS_S2, E = r3.INCUMBENT, r3.S1_MINUS_S2, r3.E
R5_REMAINING = {"P_A": 311, "P_C": 2480}
R5_REMAINING_SHA = "a53ea5b2db9e0eb983ba6023bef0d51c91e7556cc246e4c6629cc34944c8c5e1"
R5_MAX_UB = 313_433_904
R5_TOP5 = [462, 565, 251, 105, 460]
TOP_FIRST = 25
RANDOM_SEED, RANDOM_CONFIGS_PER_KIND, DESIGN_CONFIGS_PER_KIND = 20261009, 120, 160
MUTANTS = ("J_MINUS_6", "CAPE_MINUS_1", "AVAIL_MINUS_1", "G_MINUS_1", "TRIO_LAMBDA_MINUS_1", "QUAD_TERM_MINUS_1")


# ---- per-label joint term -------------------------------------------------------------------

def label_lambda(a) -> int:
    """2 * sum over pairs of min(a_b, a_b') - sum a_b  >=  3K_y + 8Q_y - N1_y  (PROOF.LABEL_TERM)."""
    return 2 * sum(min(x, y) for x, y in combinations(a, 2)) - sum(a)


def quad_joint(quad_deg, table) -> int:
    """Quad label: min(lambda, R4's R(a)), a = deg - 3 of the four quad tickets (both are valid bounds)."""
    a = [d - 3 for d in quad_deg]
    return min(label_lambda(a), table[tuple(sorted(a))])


# ---- trio labels aggregated over degree level sets ---------------------------------------------

def levels(deg) -> list[tuple[int, int, list[int], list[int]]]:
    """(hi, weight, U, D): U = {deg >= hi} for each distinct degree hi (descending); weight = hi - next (2 last)."""
    vals = sorted(set(deg), reverse=True)
    out = []
    for j, hi in enumerate(vals):
        nxt = vals[j + 1] if j + 1 < len(vals) else 2
        out.append((hi, hi - nxt, [v for v in range(len(deg)) if deg[v] >= hi],
                    [v for v in range(len(deg)) if deg[v] < hi]))
    return out


def prefix_caps(deg, t, ntrip) -> list[int]:
    """R3 kmax's G_r (#trios inside the first r+1 vertices <= G_r, R3 KMAX_LEMMA), same order as r3.kmax."""
    order = sorted(range(len(deg)), key=lambda v: -deg[v])
    g = tsum = 0
    caps = []
    for r, v in enumerate(order):
        tsum += t[v]
        g = min(g + min(t[v], r // 2), r3.packing(r + 1), tsum // 3, ntrip)
        caps.append(g)
    return caps


def avail(v, xs, t, quad) -> int:
    """Possible trio partners of v inside xs: t_w >= 1 and not a quad-mate (PROOF.TRIO_LEVELS (b))."""
    return sum(w != v and t[w] >= 1 and not (quad[v] and quad[w]) for w in xs)


def level_program(U, D, t, quad, g, mut=frozenset()):
    """Max e_F(U) = 3*T3 + T2 subject to the level constraints, exhaustively; best is None if infeasible."""
    tu, td = sum(t[v] for v in U), sum(t[v] for v in D)
    da = int("AVAIL_MINUS_1" in mut)
    av = {v: max(0, avail(v, xs, t, quad) - da) for xs in (U, D) for v in xs}
    dc = int("CAPE_MINUS_1" in mut and bool(D))  # strengthening mutants act on proper cuts only
    cap_u = sum(min(2 * t[v], av[v]) for v in U) // 2 - dc
    cap_d = sum(min(2 * t[v], av[v]) for v in D) // 2 - dc
    in3 = sum(min(t[v], av[v] // 2) for v in U) // 3
    g3 = min(g - int("G_MINUS_1" in mut and bool(D)), in3)
    best = None
    for t3 in range(g3 + 1):
        for t2 in range((tu - 3 * t3) // 2 + 1):
            t1 = tu - 3 * t3 - 2 * t2
            rem = td - 2 * t1 - t2
            if rem < 0:
                continue
            assert rem % 3 == 0  # t(U) + t(D) = 3 * ntrip
            t0 = rem // 3
            e_u, e_d = 3 * t3 + t2, 3 * t0 + t1
            if e_u <= cap_u and e_d <= cap_d and (best is None or e_u > best[0]):
                best = (e_u, t3, t2, t1, t0)
    return best, {"T_U": tu, "T_D": td, "G": g, "IN3": in3, "CAP_U": cap_u, "CAP_D": cap_d}


def global_partner_violation(t, quad) -> bool:
    """Some ticket needs 2t_v distinct trio partners but fewer than 2t_v eligible tickets exist."""
    return any(t[v] and 2 * t[v] > avail(v, range(len(t)), t, quad) for v in range(len(t)))


def trio_joint(kind, deg, t, mut=frozenset()):
    """(Lambda_trio, rows) with sum over trio labels of (3K_y - N1_y) <= Lambda_trio; (None, reason) if empty."""
    quad = [kind == "P_C" and i < 4 for i in range(len(deg))]
    caps = prefix_caps(deg, t, r3.NTRIP[kind])
    total, rows = 0, []
    for hi, wgt, U, D in levels(deg):
        best, info = level_program(U, D, t, quad, caps[len(U) - 1], mut)
        if best is None:
            reason = "GLOBAL_PARTNER" if global_partner_violation(t, quad) else "LEVEL_CUT"
            return None, {"REASON": reason, "LEVEL_DEG": hi, "SIZE_U": len(U), **info}
        phi = 2 * best[0] - info["T_U"]
        rows.append({"DEG": hi, "WEIGHT": wgt, "SIZE_U": len(U), **info, "E_U_MAX": best[0], "PHI": phi,
                     "OLD_3G": 3 * info["G"]})
        total += wgt * phi
    return total, rows


def joint_bound(kind, sp, rest, table, mut=frozenset()) -> dict:
    """J >= 3K + 8Q - N1 for every legal configuration with this profile; J is None if there is none."""
    deg, t = r3.degrees(kind, sp, rest), list(sp) + list(rest)
    trio, rows = trio_joint(kind, deg, t, mut)
    low, low_single, low_pair = r5.n1_bound(kind, sp, rest)
    quad = quad_joint(deg[:4], table) - int("QUAD_TERM_MINUS_1" in mut) if kind == "P_C" else 0
    out = {"TRIO": trio, "QUAD": quad, "L_SINGLE": low_single, "L_PAIR": low_pair}
    if trio is None:
        out.update(J=None, NO_LEGAL=rows)
        return out
    out.update(J=trio + quad - low - 6 * int("J_MINUS_6" in mut), LEVELS=rows)
    return out


# ---- local exactness of the per-label term (not needed for validity) ---------------------------

def trio_local_exhaustive() -> dict:
    """Exact max of 3K - N1 for one trio label over all local incidence vectors, a in 0..11, <= 17 outside."""
    g = np.stack(np.meshgrid(*[np.arange(12)] * 4, indexing="ij"), -1).reshape(-1, 4)
    k, n12, n13, n23 = g.T
    stats: Counter = Counter()
    for a in combinations_with_replacement(range(12), 3):
        n1, n2, n3 = a[0] - k - n12 - n13, a[1] - k - n12 - n23, a[2] - k - n13 - n23
        ok = (n1 >= 0) & (n2 >= 0) & (n3 >= 0)
        val = 3 * k - n1 - n2 - n3
        capped = ok & (k + n12 + n13 + n23 + n1 + n2 + n3 <= 17)
        stats["VECTORS"] += 1
        stats["EXACT_EQ_LAMBDA"] += int(val[ok].max()) == label_lambda(a)
        stats["EXACT_WITH_17_CAP_EQ_LAMBDA"] += int(val[capped].max()) == label_lambda(a)
        stats["LAMBDA_LE_3_MIN"] += label_lambda(a) <= 3 * min(a)
    return dict(stats)


@lru_cache(maxsize=None)
def _pairs_max(k: int, r: tuple[int, ...]) -> int:
    """Max number of |N_u| = 2 tickets (multi-edges of K4) inside capacities r, edges k..5, by exhaustion."""
    if k == 6:
        return 0
    i, j = list(combinations(range(4), 2))[k]
    best = 0
    for y in range(min(r[i], r[j]) + 1):
        nr = list(r)
        nr[i] -= y
        nr[j] -= y
        best = max(best, y + _pairs_max(k + 1, tuple(nr)))
    return best


def quad_local_exhaustive(table) -> dict:
    """Exact max of 3K + 8Q - N1 for the quad label over all incidence vectors (R4 grid + exhaustive pairs)."""
    m = np.zeros((11,) * 4, dtype=np.int64)
    classic = 0
    for r in np.ndindex(*(11,) * 4):
        m[r] = _pairs_max(0, tuple(int(x) for x in r))
        classic += m[r] == min(sum(r) // 2, sum(r) - max(r))
    grid, gx = r4._GRID, r4._GRID_X
    stats: Counter = Counter({"PAIRS_TABLE_EQ_CLASSIC_FORMULA": int(classic) == 11 ** 4})
    for a in combinations_with_replacement(range(5, 11), 4):
        av = np.asarray(a)
        best = best16 = None
        for q in range(min(a) + 1):
            res = av - (q + gx[:, None] - grid)
            ok = (res >= 0).all(1)
            rs = np.where(ok[:, None], res, 0)
            mm = m[rs[:, 0], rs[:, 1], rs[:, 2], rs[:, 3]]
            val = 8 * q + 3 * gx - rs.sum(1) + 2 * mm
            used = q + gx + rs.sum(1) - mm
            v = val[ok].max() if ok.any() else None
            v16 = val[ok & (used <= 16)].max() if (ok & (used <= 16)).any() else None
            best = v if best is None or (v is not None and v > best) else best
            best16 = v16 if best16 is None or (v16 is not None and v16 > best16) else best16
        lam = label_lambda(list(a))
        stats["VECTORS"] += 1
        stats["EXACT_EQ_LAMBDA"] += int(best) == lam
        stats["EXACT_WITH_16_CAP_EQ_LAMBDA"] += int(best16) == lam
        stats["LAMBDA_LE_R4_R"] += lam <= table[a]
        stats["LAMBDA_LT_R4_R"] += lam < table[a]
    return dict(stats)


# ---- legal configurations (admissibility checks; never used for pruning) ------------------------

def _designs() -> dict[str, list[tuple[int, ...]]]:
    """Linear triple systems used to build trio-concentrated (high-W) legal configurations."""
    ag = {frozenset(((x + k * dx) % 3) * 3 + (y + k * dy) % 3 for k in range(3))
          for x in range(3) for y in range(3) for dx, dy in ((1, 0), (0, 1), (1, 1), (1, 2))}
    sts13 = {frozenset((x + a) % 13 for a in base) for x in range(13) for base in ((0, 1, 4), (0, 2, 7))}
    pg = {frozenset((a - 1, b - 1, (a ^ b) - 1)) for a in range(1, 16) for b in range(a + 1, 16) if (a ^ b) > b}
    out = {"STS9": ag, "STS13": sts13, "STS15": pg}
    assert {k: len(v) for k, v in out.items()} == {"STS9": 12, "STS13": 26, "STS15": 35}
    return {k: sorted(tuple(sorted(b)) for b in v) for k, v in out.items()}


DESIGNS = _designs()


def design_config(rng: random.Random, kind: str):
    """Legal config whose trios come mostly from a relabelled STS(9/13/15); pairs filled as in R5."""
    name = rng.choice(sorted(DESIGNS))
    perm = rng.sample(range(20), 20)
    spec = [rng.randrange(20)] if kind == "P_A" else rng.sample(range(20), 4)
    covered = {frozenset(p) for p in combinations(spec, 2)} if kind == "P_C" else set()
    cap = [6 - (u in spec) for u in range(20)]
    tdeg = [0] * 20
    trips: list[tuple[int, ...]] = []
    blocks = [tuple(perm[p] for p in b) for b in DESIGNS[name]]
    rng.shuffle(blocks)
    ntrip = r3.NTRIP[kind]

    def take(tr) -> None:
        if (len(trips) < ntrip and all(tdeg[u] < cap[u] for u in tr)
                and not any(frozenset(p) in covered for p in combinations(tr, 2))):
            trips.append(tr)
            covered.update(frozenset(p) for p in combinations(tr, 2))
            for u in tr:
                tdeg[u] += 1

    for tr in blocks:
        take(tr)
    for _ in range(6000):
        if len(trips) == ntrip:
            break
        take(tuple(rng.sample(range(20), 3)))
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
    blks = [tuple(spec)] + trips + pairs
    assert len(blks) == 49
    tickets: list[set[int]] = [set() for _ in range(20)]
    for label, blk in enumerate(blks, 1):
        for u in blk:
            tickets[u].add(label)
    return [frozenset(tk) for tk in tickets]


def check_config(tickets: list[frozenset[int]], table: dict) -> dict:
    """Brute-force every label term and every level quantity on a legal config; test each R6 inequality."""
    base = r3.analyze(tickets)  # asserts legality, histogram, Tstar; recomputes T_true, K, Q, N1, S3
    kind, sp, rest = base["KIND"], tuple(base["SPECIAL"]), tuple(base["REST"])
    hold = {y: [u for u, tk in enumerate(tickets) if y in tk] for y in range(1, 50)}
    spec = next(h for h in hold.values() if len(h) == (1 if kind == "P_A" else 4))
    tcount = [sum(len(hold[y]) == 3 for y in tk) for tk in tickets]
    # relabel tickets into profile order (special first, then rest; each by t descending)
    perm = (sorted(spec, key=lambda u: -tcount[u])
            + sorted((u for u in range(20) if u not in spec), key=lambda u: -tcount[u]))
    pos = {u: i for i, u in enumerate(perm)}
    tk2 = [tickets[u] for u in perm]
    hold = {y: sorted(pos[u] for u in h) for y, h in hold.items()}
    adj = [[u != v and len(tk2[u] & tk2[v]) == 1 for v in range(20)] for u in range(20)]
    deg = [sum(row) for row in adj]
    t = [tcount[u] for u in perm]
    assert deg == r3.degrees(kind, sp, rest) and t == list(sp) + list(rest)
    quad = [kind == "P_C" and i < 4 for i in range(20)]
    total = trio_lambda = 0
    label_ok = identity_ok = True
    tight: Counter = Counter()
    for hs in hold.values():
        d = len(hs)
        ms = [sum(adj[u][b] for b in hs) for u in range(20) if u not in hs]
        term = 3 * ms.count(3) + 8 * ms.count(4) - ms.count(1)
        a = [deg[b] - (d - 1) for b in hs]
        identity_ok &= term == 2 * sum(comb(m, 2) for m in ms) - sum(ms) and sum(ms) == sum(a)
        lam = label_lambda(a)
        if d == 1:
            bound = -deg[hs[0]]  # R5 L_single (exact)
        elif d == 2:
            bound = -abs(deg[hs[0]] - deg[hs[1]])  # R5 pair-label bound
        else:
            bound = lam if d == 3 else min(lam, table[tuple(sorted(a))])
        label_ok &= term <= bound and (d != 1 or term == bound)
        tight[f"D{d}_AT_BOUND"] += term == bound
        tight[f"D{d}_LABELS"] += 1
        trio_lambda += lam if d == 3 else 0
        total += term
    true_sum = 3 * (base["K_TRIO"] + base["K_QUAD"]) + 8 * base["Q"] - base["N1"]
    trios = [hs for hs in hold.values() if len(hs) == 3]
    caps = prefix_caps(deg, t, r3.NTRIP[kind])
    level_ok, decomp = True, 0
    for hi, wgt, U, D in levels(deg):
        us = set(U)
        cnt = Counter(sum(b in us for b in tr) for tr in trios)
        e_u, e_d = 3 * cnt[3] + cnt[2], 3 * cnt[0] + cnt[1]
        best, info = level_program(U, D, t, quad, caps[len(U) - 1])
        level_ok &= (best is not None and cnt[3] <= min(info["G"], info["IN3"]) and e_u <= info["CAP_U"]
                     and e_d <= info["CAP_D"] and e_u <= best[0])
        decomp += wgt * (2 * e_u - info["T_U"])
    jb = joint_bound(kind, sp, rest, table)
    s3_6 = r3.s3_ub(kind, base["W"], jb["J"]) if jb["J"] is not None else None
    out = {
        "KIND": kind, "SPECIAL": list(sp), "REST": list(rest), "W": base["W"], "T_TRUE": base["T_TRUE"],
        "SUM_TERMS": total, "J": jb["J"], "SLACK": None if jb["J"] is None else jb["J"] - total,
        "TIGHT": dict(tight),
        "LABEL_TERM_IDENTITY": identity_ok and total == true_sum == 6 * base["T_TRUE"] - 10 * E,
        "LABEL_BOUNDS_HOLD": label_ok,
        "LEVEL_DECOMPOSITION_EXACT": decomp == trio_lambda,
        "LEVEL_CONSTRAINTS_HOLD": level_ok,
        "PROFILE_FEASIBLE": jb["J"] is not None,
        "J_ADMISSIBLE": jb["J"] is not None and true_sum <= jb["J"],
        "S3_UB6_ADMISSIBLE": s3_6 is not None and base["S3_DIRECT"] <= s3_6,
        "BONFERRONI3_VALUE": S1_MINUS_S2 + base["S3_DIRECT"],
    }
    caught = {}
    for m in MUTANTS:
        if m == "TRIO_LAMBDA_MINUS_1":
            caught[m] = tight["D3_AT_BOUND"] > 0
        elif m == "QUAD_TERM_MINUS_1":
            caught[m] = tight["D4_AT_BOUND"] > 0
        else:
            jm = joint_bound(kind, sp, rest, table, frozenset([m]))["J"]
            caught[m] = jm is None or jm < true_sum
    out["MUTANTS_CAUGHT"] = caught
    return out


CONFIG_KEYS = ("LABEL_TERM_IDENTITY", "LABEL_BOUNDS_HOLD", "LEVEL_DECOMPOSITION_EXACT", "LEVEL_CONSTRAINTS_HOLD",
               "PROFILE_FEASIBLE", "J_ADMISSIBLE", "S3_UB6_ADMISSIBLE")


def config_checks(table: dict, open_keys: set, surv_keys: set, rem_keys: set) -> dict:
    r2 = json.loads((HERE / "k_bound_validation_r2.json").read_text())
    named = {"P_C_COUNTEREXAMPLE_R2": [frozenset(tk) for tk in
                                       r2["BOUND_ADMISSIBILITY"]["P_C_STEP_COUNTEREXAMPLE"]["tickets"]],
             "P_A_K12_K8_LIFT": r3.k12_k8()}
    named_out = {k: check_config(v, table) for k, v in named.items()}
    rng = random.Random(RANDOM_SEED)
    stats: Counter = Counter()
    mut: Counter = Counter()
    for gen, n_per in (("RANDOM_R5", RANDOM_CONFIGS_PER_KIND), ("DESIGN", DESIGN_CONFIGS_PER_KIND)):
        for kind in ("P_A", "P_C"):
            made = 0
            while made < n_per:
                stats[gen, kind, "ATTEMPTS"] += 1
                tickets = r5.random_config(rng, kind) if gen == "RANDOM_R5" else design_config(rng, kind)
                if tickets is None:
                    continue
                made += 1
                c = check_config(tickets, table)
                assert c["KIND"] == kind
                key = (kind, tuple(c["SPECIAL"]), tuple(c["REST"]))
                s = (gen, kind)
                stats[s + ("CONFIGS",)] += 1
                stats[s + ("ALL_CHECKS_PASS",)] += all(c[k] for k in CONFIG_KEYS)
                stats[s + ("W_GE_W0",)] += c["W"] >= r3.w0(kind)
                stats[s + ("PROFILE_IN_SURVIVORS",)] += key in surv_keys
                stats[s + ("PROFILE_IN_R5_OPEN_SET",)] += key in open_keys
                stats[s + ("PROFILE_IN_R6_REMAINING",)] += key in rem_keys
                if key in rem_keys:
                    stats[s + ("MIN_SLACK_IN_R6_REMAINING",)] = min(
                        stats.get(s + ("MIN_SLACK_IN_R6_REMAINING",), 10 ** 9), c["SLACK"])
                stats[s + ("BONFERRONI3_GT_INCUMBENT",)] += c["BONFERRONI3_VALUE"] > INCUMBENT
                stats[s + ("MAX_BONFERRONI3_VALUE",)] = max(stats[s + ("MAX_BONFERRONI3_VALUE",)],
                                                            c["BONFERRONI3_VALUE"])
                stats[s + ("SLACK_LT_6",)] += c["SLACK"] is not None and c["SLACK"] < 6
                stats[s + ("MIN_SLACK",)] = min(stats.get(s + ("MIN_SLACK",), 10 ** 9), c["SLACK"] or 0)
                for m, hit in c["MUTANTS_CAUGHT"].items():
                    mut[m] += hit
    for c in named_out.values():
        for m, hit in c["MUTANTS_CAUGHT"].items():
            mut[m] += hit
    return {"NAMED": named_out, "RANDOM_SEED": RANDOM_SEED,
            "GENERATED": {":".join(k): v for k, v in sorted(stats.items())},
            "MUTANTS_CAUGHT_BY_ANY_LEGAL_CONFIG": {m: mut[m] for m in MUTANTS}}


# ---- main -----------------------------------------------------------------------------------

def r5_open_rows(surv: list, table: dict) -> list[dict]:
    """R5's open set, rebuilt with the pinned R3/R4/R5 functions exactly as R5 did."""
    rows = []
    for i, r in enumerate(surv):
        kind, sp, rest = r["KIND"], tuple(r["SPECIAL"]), tuple(r["REST"])
        deg, t = r3.degrees(kind, sp, rest), list(sp) + list(rest)
        w = sum(comb(d, 2) for d in deg)
        if S1_MINUS_S2 + r3.s3_ub(kind, w, r3.kq_bound(kind, sp, rest)) <= INCUMBENT:
            continue
        km = r3.kmax(deg, t, r3.NTRIP[kind])
        b4 = 3 * km + table[tuple(sorted(d - 3 for d in deg[:4]))] if kind == "P_C" else 3 * km
        if S1_MINUS_S2 + r3.s3_ub(kind, w, b4) <= INCUMBENT:
            continue
        low = r5.n1_bound(kind, sp, rest)[0]
        ub5 = S1_MINUS_S2 + r5.s3_ub5(kind, w, b4, low)
        if ub5 <= INCUMBENT:
            continue
        ubw = S1_MINUS_S2 + r3.s3_wedge(kind, w)
        rows.append({"i": i, "kind": kind, "sp": sp, "rest": rest, "deg": deg, "t": t, "w": w, "km": km,
                     "b4": b4, "low": low, "ub5": min(ub5, ubw)})
    return rows


def evaluate(x: dict, table: dict) -> dict:
    kind, deg, t = x["kind"], x["deg"], x["t"]
    jb = joint_bound(kind, x["sp"], x["rest"], table)
    caps = prefix_caps(deg, t, r3.NTRIP[kind])
    rec = {"index": x["i"], "KIND": kind, "SPECIAL": list(x["sp"]), "REST": list(x["rest"]), "W": x["w"],
           "UB_R5": x["ub5"], "TRIO_OLD_3KMAX": 3 * x["km"], "TRIO_JOINT": jb["TRIO"], "QUAD_JOINT": jb["QUAD"],
           "QUAD_OLD_R": x["b4"] - 3 * x["km"], "L_SINGLE": jb["L_SINGLE"], "L_PAIR": jb["L_PAIR"],
           "J_OLD_R5": x["b4"] - x["low"], "J": jb["J"],
           "KMAX_ABEL_OK": sum(wgt * caps[len(U) - 1] for _, wgt, U, _ in levels(deg)) == x["km"]}
    if jb["J"] is None:
        rec.update(STATUS="NO_LEGAL_TRIO_SYSTEM", REASON=jb["NO_LEGAL"]["REASON"], NO_LEGAL=jb["NO_LEGAL"],
                   UB_R6=None, UB=None, MONOTONE=True)
        return rec
    ub6 = S1_MINUS_S2 + r3.s3_ub(kind, x["w"], jb["J"])
    ub = min(ub6, x["ub5"])
    rec.update(UB_R6=ub6, UB=ub, LEVELS=jb["LEVELS"],
               MONOTONE=(jb["TRIO"] <= 3 * x["km"] and jb["QUAD"] <= x["b4"] - 3 * x["km"]
                         and jb["J"] <= x["b4"] - x["low"] and ub6 <= S1_MINUS_S2 + r5.s3_ub5(
                             kind, x["w"], x["b4"], x["low"])),
               STATUS="BOUND_PRUNED" if ub <= INCUMBENT else "REMAINING")
    return rec


def main() -> None:
    r5_result = json.loads((HERE / "n1_lower_bound_r5.json").read_text())
    r4_result = json.loads((HERE / "k_quad_exact_bound_r4.json").read_text())
    surv = json.loads((HERE / "survivors.json").read_text())
    r5_inherited = (r5_result["SCIENTIFIC_STATUS"] == "PARTIAL_BOUND_CERTIFIED"
                    and all(r5_result["CHECKS"].values())
                    and r5_result["UNRESOLVED_LOCATOR"]["INDEX_LIST_SHA256"] == R5_REMAINING_SHA
                    and r5_result["MAX_VALID_UPPER_BOUND"] == R5_MAX_UB)
    table, qstats, qrows = r4.quad_table()
    table_ok = qrows == r4_result["QUAD_EXACT_TABLE"] and qstats["DOMAIN"] == 126

    rows = r5_open_rows(surv, table)
    idx = [x["i"] for x in rows]
    in_sha = hashlib.sha256(",".join(map(str, idx)).encode()).hexdigest()
    by_ub5 = sorted(rows, key=lambda x: (-x["ub5"], x["i"]))
    r5_set_ok = (in_sha == R5_REMAINING_SHA and len(surv) == 58480 and len(rows) == 2791
                 and all(sum(x["kind"] == k for x in rows) == R5_REMAINING[k] for k in R5_REMAINING)
                 and by_ub5[0]["ub5"] == R5_MAX_UB and [x["i"] for x in by_ub5[:5]] == R5_TOP5)
    open_keys = {(x["kind"], x["sp"], x["rest"]) for x in rows}
    surv_keys = {(r["KIND"], tuple(r["SPECIAL"]), tuple(r["REST"])) for r in surv}

    trio_loc = trio_local_exhaustive()
    quad_loc = quad_local_exhaustive(table)
    trio_loc_ok = (trio_loc["VECTORS"] == 364 and trio_loc["EXACT_EQ_LAMBDA"] == 364
                   and trio_loc["EXACT_WITH_17_CAP_EQ_LAMBDA"] == 364 and trio_loc["LAMBDA_LE_3_MIN"] == 364)
    quad_loc_ok = (quad_loc["VECTORS"] == 126 and quad_loc["EXACT_EQ_LAMBDA"] == 126
                   and quad_loc["EXACT_WITH_16_CAP_EQ_LAMBDA"] == 126 and quad_loc["LAMBDA_LE_R4_R"] == 126
                   and quad_loc["PAIRS_TABLE_EQ_CLASSIC_FORMULA"])

    # Phase 2: highest R5 upper bounds first, then every other R5 survivor; each profile evaluated once.
    recs = {}
    for x in by_ub5[:TOP_FIRST]:
        recs[x["i"]] = evaluate(x, table)
    top_first = [recs[x["i"]] for x in by_ub5[:TOP_FIRST]]
    for x in rows:
        if x["i"] not in recs:
            recs[x["i"]] = evaluate(x, table)
    assert len(recs) == len(rows)

    acct = {k: Counter() for k in r3.TSTAR}
    remaining, need = [], Counter()
    for x in rows:
        rec, c = recs[x["i"]], acct[x["kind"]]
        c["INPUT"] += 1
        if rec["STATUS"] == "NO_LEGAL_TRIO_SYSTEM":
            c["NEWLY_PRUNED"] += 1
            c[f"NO_LEGAL_TRIO_SYSTEM_{rec['REASON']}"] += 1
            continue
        c["UB_LOWERED"] += rec["UB"] < x["ub5"]
        if rec["UB"] <= INCUMBENT:
            c["NEWLY_PRUNED"] += 1
            c["BOUND_PRUNED"] += 1
            c["BOUND_PRUNED_AT_EQUALITY"] += rec["UB"] == INCUMBENT
        else:
            c["REMAINING"] += 1
            remaining.append(rec)
            need[(x["kind"], -(-(rec["UB"] - INCUMBENT) // 11872))] += 1
    remaining.sort(key=lambda r: (-r["UB"], r["index"]))
    rem_idx = sorted(r["index"] for r in remaining)
    rem_sha = hashlib.sha256(",".join(map(str, rem_idx)).encode()).hexdigest()
    cfg = config_checks(table, open_keys, surv_keys,
                        {(r["KIND"], tuple(r["SPECIAL"]), tuple(r["REST"])) for r in remaining})
    named_ok = all(all(c[k] for k in CONFIG_KEYS) for c in cfg["NAMED"].values())
    gen = cfg["GENERATED"]
    gen_ok = all(gen[f"{g}:{k}:ALL_CHECKS_PASS"] == gen[f"{g}:{k}:CONFIGS"] == n
                 for g, n in (("RANDOM_R5", RANDOM_CONFIGS_PER_KIND), ("DESIGN", DESIGN_CONFIGS_PER_KIND))
                 for k in ("P_A", "P_C"))
    newly = sum(acct[k]["NEWLY_PRUNED"] for k in r3.TSTAR)
    n_rem = sum(acct[k]["REMAINING"] for k in r3.TSTAR)
    best = remaining[0]["UB"] if remaining else None
    checks = {
        "FROZEN_INPUTS": HASHES == FROZEN,
        "R5_RESULT_INHERITED": r5_inherited,
        "R4_QUAD_TABLE_REPRODUCED": table_ok,
        "R5_OPEN_SET_REPRODUCED": r5_set_ok,
        "TRIO_LABEL_LAMBDA_EXACT_LOCAL_MAX": trio_loc_ok,
        "QUAD_LABEL_LAMBDA_EXACT_LOCAL_MAX_AND_LE_R": quad_loc_ok,
        "KMAX_ABEL_FORM_REPRODUCED_ALL_PROFILES": all(r["KMAX_ABEL_OK"] for r in recs.values()),
        "NEW_TERMS_MONOTONE_VS_R5": all(r["MONOTONE"] for r in recs.values()),
        "NAMED_CONFIGS_ALL_INEQUALITIES": named_ok,
        "GENERATED_LEGAL_CONFIGS_ALL_INEQUALITIES": gen_ok,
        "ACCOUNTING_CLOSES": newly + n_rem == len(rows) == 2791,
    }
    proved = all(checks.values())
    if not proved:
        status = "NOT_PROVED"
    elif newly == 0:
        status = "NO_IMPROVEMENT"
    elif n_rem == 0:
        status = "FULL_SHELL1_CLOSED"
    else:
        status = "PARTIAL_BOUND_CERTIFIED"
    by_kind = {k: {f: acct[k][f] for f in ("INPUT", "NEWLY_PRUNED", "NO_LEGAL_TRIO_SYSTEM_GLOBAL_PARTNER",
                                         "NO_LEGAL_TRIO_SYSTEM_LEVEL_CUT", "BOUND_PRUNED",
                                         "BOUND_PRUNED_AT_EQUALITY", "REMAINING", "UB_LOWERED")}
               for k in r3.TSTAR}
    slim = ("index", "KIND", "SPECIAL", "REST", "W", "UB_R5", "UB_R6", "UB", "STATUS", "TRIO_OLD_3KMAX",
            "TRIO_JOINT", "QUAD_OLD_R", "QUAD_JOINT", "L_SINGLE", "L_PAIR", "J_OLD_R5", "J")
    ru = resource.getrusage(resource.RUSAGE_SELF)
    result = {
        "TASK_ID": "B649_K20_V8_SHELL1_JOINT_K_N1_BOUND_R6",
        "CREATED": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "BASE": subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True,
                               text=True).stdout.strip(),
        "CANONICAL": {"K20_COUNT": INCUMBENT, "K20_SHA256": r3.K20_SHA256, "S1_MINUS_S2_SHELL1": S1_MINUS_S2,
                      "S3_THRESHOLD": r3.THRESH},
        "FROZEN_INPUTS_SHA256": HASHES,
        "IMPLEMENTATION": {"PATH": Path(__file__).name,
                           "SHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        "FORMULA": {
            "CHANGE_VS_R5": "3K + 8Q <= 3*kmax + R(a) and N1 >= L_single + L_pair  ->  3K + 8Q - N1 <= J",
            "LAMBDA": "label y, a_b = deg b - (d_y - 1): lambda(y) = 2*sum_{pairs in B_y} min(a_b, a_b') - sum_b a_b",
            "J": "Lambda_trio + [P_C] min(lambda(quad), R(a)) - L_pair - L_single",
            "LAMBDA_TRIO": "sum over distinct degrees hi (desc) of (hi - next lower, 2 last) * phi({deg >= hi})",
            "PHI": "max 2*(3T3 + T2) - t(U) s.t. t(U) = 3T3+2T2+T1, t(D) = 3T0+2T1+T2, T_i >= 0, T3 <= G(U), "
                   "3T3 <= sum_U min(t_v, floor(avail_U(v)/2)), 3T3+T2 <= cap(U), 3T0+T1 <= cap(D); "
                   "cap(X) = floor(sum_X min(2t_v, avail_X(v))/2); infeasible => NO_LEGAL_TRIO_SYSTEM",
            "S3_UB": "2800*W + 11872*floor((940 + J)/6) - 1400*Tstar  (r3.s3_ub with B := J)",
            "UB": "min(UB_R5, UB_wedge, 307923840 + S3_UB); prune iff UB <= 313263888 (equality = tie)",
        },
        "PROOF": PROOF,
        "PROOF_ASSUMPTIONS": r3.ASSUMPTIONS + [
            "R5 L_single/L_pair are reused verbatim (r5.n1_bound); R4 R(a) via r4.quad_table; R3 kmax prefix "
            "caps, packing bound, identity, constants and S3 formula via the pinned r3 module."],
        "LOCAL_EXACTNESS": {"TRIO_LABEL": trio_loc, "QUAD_LABEL": quad_loc},
        "ADMISSIBILITY_CHECKS_ON_LEGAL_CONFIGS": cfg,
        "CHECKS": checks,
        "TOP_FIRST": {
            "RULE": f"the {TOP_FIRST} R5 survivors with the highest R5 upper bound, evaluated before the rest",
            "R5_REPORTED_TOP5": R5_TOP5,
            "ROWS": [{k: r.get(k) for k in slim} | ({"NO_LEGAL": r["NO_LEGAL"]} if "NO_LEGAL" in r else {})
                     for r in top_first],
            "IMPROVED": sum(r["UB"] is None or r["UB"] < r["UB_R5"] for r in top_first),
            "STATUS_COUNTS": dict(Counter(r["STATUS"] for r in top_first)),
            "R5_TOP5_STATUS": {r["index"]: [r["STATUS"], r.get("REASON")] for r in top_first
                               if r["index"] in R5_TOP5},
        },
        "ACCOUNTING": {
            "INPUT_PROFILES": len(rows),
            "INPUT_INDEX_LIST_SHA256": in_sha,
            "BY_KIND": by_kind,
            "P_A_NEWLY_PRUNED": acct["P_A"]["NEWLY_PRUNED"], "P_A_REMAINING": acct["P_A"]["REMAINING"],
            "P_C_NEWLY_PRUNED": acct["P_C"]["NEWLY_PRUNED"], "P_C_REMAINING": acct["P_C"]["REMAINING"],
            "TOTAL_NEWLY_PRUNED": newly, "TOTAL_REMAINING": n_rem,
            "PREVIOUS_MAX_BOUND": R5_MAX_UB,
            "NOTE": "Applied once to R5's open set (R5-pruned profiles stay pruned). NEWLY_PRUNED = "
                    "NO_LEGAL_TRIO_SYSTEM (profile has no legal configuration) + BOUND_PRUNED (UB <= incumbent).",
        },
        "UNRESOLVED_LOCATOR": {
            "SOURCE": "survivors.json 0-based array index; predicate min(UB_R5, UB_R6) > 313263888",
            "COUNT": len(rem_idx),
            "INDEX_LIST_SHA256": rem_sha,
            "INDEX_LIST_ENCODING": "sha256 of ascii comma-joined ascending indices",
            "INDICES": rem_idx,
            "T_TRUE_UNITS_STILL_NEEDED": {f"{k}:{n}": v for (k, n), v in sorted(need.items())},
            "TOP10_BY_UB": [{k: r.get(k) for k in slim} | {"LEVELS": r["LEVELS"]} for r in remaining[:10]],
        },
        "MAX_VALID_UPPER_BOUND": best,
        "GAP_VS_313263888": (best - INCUMBENT) if best is not None else None,
        "REMAINING_PROOF_GAPS": [
            f"{n_rem} profiles (index-list sha {rem_sha[:12]}) still have certified UB > {INCUMBENT}; best UB {best}.",
            "Remaining slack is the per-pair common-neighbour cap c_bb' <= min(a_b, a_b'): it is attained only when "
            "every outside neighbour of the lower-degree ticket is also adjacent to the other (K12+K8: J slack 0); "
            "legal configs realised on still-open profiles show J slack >= MIN_SLACK_IN_R6_REMAINING (GENERATED).",
            "Bonferroni-3 is an upper bound on the union: a remaining profile is not a candidate until an exact "
            "canonical recount of a concrete portfolio beats 313263888.",
            "Shell-1 only: overlap <= 1 and sum C(d,2) = 94.",
        ],
        "SCIENTIFIC_STATUS": status,
        "JOINT_BOUND_ADMISSIBILITY": "PROVED" if proved else "NOT_PROVED",
        "NO_CPSAT": True,
        "MULTIPROCESSING": False,
        "CPU_SECONDS": round(ru.ru_utime + ru.ru_stime, 2),
    }
    OUT.write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps({"STATUS": status, "ADMISSIBILITY": result["JOINT_BOUND_ADMISSIBILITY"], "CHECKS": checks,
                      "BY_KIND": by_kind, "MAX_UB": best, "GAP": result["GAP_VS_313263888"],
                      "REMAINING_SHA": rem_sha, "TOP_FIRST_IMPROVED": result["TOP_FIRST"]["IMPROVED"],
                      "GENERATED": gen, "MUTANTS": cfg["MUTANTS_CAUGHT_BY_ANY_LEGAL_CONFIG"],
                      "LOCAL": result["LOCAL_EXACTNESS"], "CPU": result["CPU_SECONDS"]}, indent=1))


PROOF = {
    "LABEL_TERM": [
        "Fix a legal Shell-1 configuration and a label y; B_y = tickets holding y, d_y = |B_y| in 1..4. For u not in "
        "B_y, m_y(u) = #{b in B_y : u ~ b}; K_y, Q_y, N1_y count those u with m_y(u) = 3, 4, 1, and K, Q, N1 are the "
        "sums over ALL labels (R3 DEFINITIONS). term_y := 3K_y + 8Q_y - N1_y, so 3K + 8Q - N1 = sum_y term_y.",
        "R3 IDENTITY (ii): 2*C(m,2) = m - [m=1] + 3[m=3] + 8[m=4] for m in 0..4. Summing over u not in B_y: "
        "term_y = 2*P_y - A_y with P_y = sum_u C(m_y(u), 2) and A_y = sum_u m_y(u).",
        "A_y = sum_{b in B_y} a_b with a_b := deg b - (d_y - 1): b is adjacent to the other d_y - 1 members of B_y "
        "(via y only, overlap <= 1), all its other neighbours lie outside B_y, and deg b counts neighbours.",
        "P_y = sum over pairs {b, b'} in B_y of c_bb', c_bb' := #{u not in B_y : u ~ b and u ~ b'} (u contributes one "
        "per pair of its B_y-neighbours). Those u are outside neighbours of b and of b', so c_bb' <= min(a_b, a_b').",
        "Hence term_y <= lambda(y) := 2*sum_{pairs} min(a_b, a_b') - sum_b a_b on every legal configuration. "
        "d_y = 1: lambda = -deg b_s = -L_single (R5, exact). d_y = 2: lambda = -|deg b1 - deg b2| (R5 PAIR_LABEL). "
        "d_y = 3, a1 >= a2 >= a3: lambda = 3*a3 - (a1 - a2), whereas the separate R3-R5 pieces give 3*a3 - 0: a trio "
        "label at its apex cap K_y = a3 is forced to N1_y >= a1 - a2. d_y = 4 (a = deg - 3, sorted descending): "
        "lambda = 5*a4 + 3*a3 + a2 - a1.",
        "Local exactness (not needed for validity): lambda is the exact maximum of term_y over every local incidence "
        "vector (counts n_S of outside tickets with B_y-neighbour set S, column sums a, at most 20 - d_y of them). "
        "Witness: a_min tickets with S = B_y, then nested sets on the sorted residuals. Checked exhaustively for "
        "trio a in 0..11 (364 vectors) and quad a in 5..10 (126 vectors: R4 grid plus exhaustive pair matching).",
    ],
    "QUAD": "term_q <= min(lambda(q), R(a)): R4 proves 3K_q + 8Q_q <= R(a) and N1_q >= 0. lambda <= R(a) on all 126 "
            "domain vectors (checked); the min is taken anyway.",
    "TRIO_LEVELS": [
        "Trio labels are not fixed by the profile. F := graph on the tickets, u ~_F v iff u, v share a trio label. F is "
        "simple (overlap <= 1); deg_F(v) = 2*t_v (two partners per trio label, all distinct since two tickets share "
        "at most one label); every F-neighbour w of v has t_w >= 1 and is not a quad-mate of v (a quad-mate already "
        "shares the quad label with v).",
        "Layer cake with a_v = deg_v - 2: min(a_u, a_v) = sum_{theta>=1} [a_u >= theta][a_v >= theta] and a_v = "
        "sum_{theta>=1} [a_v >= theta], so sum_{trio y} lambda(y) = 2*sum_{F edges} min(a_u, a_v) - sum_v t_v*a_v = "
        "sum_{theta>=1} (2*e_F(U_theta) - t(U_theta)), U_theta = {deg >= theta + 2}. U_theta only changes at the "
        "distinct degree values hi; level hi has weight hi - (next lower degree, or 2 below the minimum).",
        "For a level set U with complement D let T_i = #trio labels with exactly i members in U. These are "
        "non-negative integers with t(U) = 3T3 + 2T2 + T1, t(D) = 3T0 + 2T1 + T2, e_F(U) = 3T3 + T2, "
        "e_F(D) = 3T0 + T1. Every legal configuration also satisfies (a)-(c):",
        "(a) T3 <= G(U): U is the prefix of size |U| of the degree-descending order and R3 KMAX_LEMMA proves "
        "#trios inside the first r+1 vertices <= G_r for that greedy (valid for any tie order).",
        "(b) 3*T3 <= sum_{v in U} min(t_v, floor(avail_U(v)/2)), avail_X(v) = #{w in X - v : t_w >= 1, not both "
        "quad}: each trio inside U through v uses two eligible members of U - v, distinct across v's trios.",
        "(c) e_F(X) <= floor(sum_{v in X} min(2*t_v, avail_X(v)) / 2) for X in {U, D}: v has at most "
        "min(2*t_v, avail_X(v)) F-neighbours in X and each F-edge inside X is counted at both ends.",
        "phi(U) := max (2*e_F(U) - t(U)) over integer (T0..T3) meeting the identities and (a)-(c). level_program "
        "enumerates T3 in 0..min((a), (b)) and T2 in 0..floor((t(U) - 3T3)/2); T1 and T0 are then determined, so "
        "the maximum is exact. If no point is feasible, no legal configuration has the profile "
        "(NO_LEGAL_TRIO_SYSTEM; such a profile is pruned outright). At the last level U = all tickets, t(D) = 0 "
        "forces T3 = ntrip and (b) then needs 2*t_v <= avail(v) for every ticket; GLOBAL_PARTNER marks profiles "
        "where some ticket violates this, LEVEL_CUT the others.",
        "So sum_{trio y} term_y <= sum_{trio y} lambda(y) <= Lambda_trio := sum_levels weight * phi(U). As "
        "2*e_F(U) - t(U) = 3T3 - T1 <= 3*G(U), Lambda_trio <= sum_levels weight * 3G(U) = 3*kmax (the Abel form of "
        "R3 kmax; reproduced for every profile), so the trio part is never weaker than R3-R5's.",
    ],
    "BOUND": "3K + 8Q - N1 = sum_y term_y, each label counted once and each N1_y only inside its own label's term: "
             "trio labels <= Lambda_trio, the quad label <= min(lambda, R(a)), pair labels <= -L_pair (R5: sum of "
             "-|deg b1 - deg b2| >= ... >= L_pair), the singleton = -L_single (R5, exact). Each inequality holds on "
             "every legal configuration with the profile, so their sum J does; nothing else is combined. R3: "
             "6*T_true = 940 + 3K + 8Q - N1 <= 940 + J; T_true integer => T_true <= floor((940 + J)/6); "
             "S3 <= r3.s3_ub(kind, W, J). Prune iff min(UB_R5, UB_wedge, 307923840 + S3_UB) <= 313263888; "
             "equality is a tie, never a strict gain.",
    "INHERITANCE": "Lambda_trio <= 3*kmax and min(lambda, R) <= R(a), so J <= B_R4 - L and UB_R6 <= UB_R5 (checked on "
                   "every profile); every R1-R5-pruned profile stays pruned and only R5's open set (2791, sha "
                   "a53ea5b2) is re-evaluated. kmax prefix caps, packing bound, R(a), L_single, L_pair, the identity, "
                   "the constants and the S3 formula are reused from the hash-pinned R3/R4/R5 modules.",
}


if __name__ == "__main__":
    main()
