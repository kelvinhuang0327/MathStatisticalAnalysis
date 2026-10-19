"""R7: edge-class true-triangle bound (common-neighbour capacity), applied once to the 69 Shell-1 profiles R6 left open.

Run from this directory:  OMP_NUM_THREADS=1 nice -n 15 <python> -B common_neighbour_capacity_r7.py
Reads the frozen R1-R6 sources/results (never writes them) and writes common_neighbour_capacity_r7.json.
Single process, no CP-SAT, no multiprocessing, CPU rlimit 120 s (set by the imported, hash-pinned R5 module).
Change vs R6: instead of bounding 3K + 8Q - N1 label by label, R7 bounds T_true directly. True triangles are split
by edge class (F = trio-label edge, R = any other edge) and by core/Z location, every class is counted exactly or
capped by a cherry/complement count (PROOF), and the per-ticket split of R-edges between core and Z is maximised
exhaustively under necessary realisability conditions. R6's level program is reused on NON-prefix ticket sets, with
R6's degree-prefix cap G(U) replaced by g_any(U) (PROOF.ARBITRARY_SUBSET_LEVEL_PROGRAM).
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
from itertools import combinations, combinations_with_replacement, product  # noqa: E402
from math import comb  # noqa: E402
from pathlib import Path  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "common_neighbour_capacity_r7.json"
FROZEN = {
    "joint_kn1_bound_r6.py": "a68da9d322da16de83b5c95cb2a6ec621e5631765f94236b344c9c49fa8d124f",
    "joint_kn1_bound_r6.json": "a156cb2fe90af2068029c49d82a113e243ed53a73ce4072a2e05f3fa2dbffc78",
    "n1_lower_bound_r5.py": "e7e708b68fb8f10282874260399ea22f11001cf3e606d36a540ab93995836700",
    "n1_lower_bound_r5.json": "8ce144b1ec78eb1f868c8d6f76814a54dad232e1c9750c21de22df7466c97ed9",
    "k_quad_exact_bound_r4.py": "e9d7f55cdb991f0f3c3a6dd8405375e30eaba152f969b351505d0098bd1c6f22",
    "k_quad_exact_bound_r4.json": "a243c8e99cb4c7e5a18e641f59b341e2c66147cf767fdb201665ce9faf3420fd",
    "k_bound_certify_r3.py": "12f59d58ec77b9e64df02524bb62c910c6ac75ddc7353541e7882ddf2f5091b0",
    "k_bound_certification_r3.json": "669d18a0395e5472dac7c8ec4f7d8fbd25070e3437d20c3e4449c774f5dbbc74",
    "k_bound_validation_r2.json": "2ca0110a611938acfe30259baaf922c9fa802f424538c86e2539123cebe70c06",
    "constants.py": "7a04ce5f17f9e4c7422c601b5a884c2a2ecf97f412a0da9beaa7553e0151d251",
    "profiles.py": "f106f9c106d99d91b745bfdece1f07d44e955adba1d355daa93e73a479c63739",
    "profiles_k.py": "bb6927c10023df07a81dc514304dada433862693a942b694e03431d74b081312",
    "survivors.json": "c7287b11ba801f195372fb8db98e52a80c3b975e3cb478795cc95308457dfec2",
}
HASHES = {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in FROZEN}
if HASHES != FROZEN:  # fail closed before any frozen module is imported
    raise SystemExit(f"FROZEN INPUT MISMATCH: {[n for n in FROZEN if HASHES[n] != FROZEN[n]]}")

sys.path.insert(0, str(HERE))
import constants as cst  # noqa: E402  frozen first-principles co_win DP
import joint_kn1_bound_r6 as r6  # noqa: E402  frozen R6 (imports R5 -> R4 -> R3; R5 sets RLIMIT_CPU 120 s)

r3, r4, r5 = r6.r3, r6.r4, r6.r5
INCUMBENT, S1_MINUS_S2 = r3.INCUMBENT, r3.S1_MINUS_S2
R6_INDEX_SHA = "72488acae13dd5cd9e17995a722ca6cd8753cdc99a31973b1517e12df8300f5b"
R6_COUNTS = {"P_A": 28, "P_C": 41}
R6_MAX_UB = 313_324_200
FOCUS = (2607, 4129, 4060, 2606)
SEED, CONFIGS_PER_CELL, T7_COST_CAP = 20261010, 120, 5000
SMALL_N_MAX = 6
MUTANTS = ("T7_MINUS_1", "FFF0_MINUS_1", "A_MINUS_1", "BZ_MINUS_1", "BEDGE_MINUS_1", "CIND_MINUS_1", "D_MINUS_1")
# K13 minus the 9-cycle 4-5-...-12-4, decomposed into 23 triangles (trio labels of the C9 configuration).
C9_BLOCKS = ((0, 1, 2), (0, 3, 4), (0, 5, 7), (0, 6, 8), (0, 9, 11), (0, 10, 12), (1, 3, 5), (1, 4, 9), (1, 6, 10),
             (1, 7, 11), (1, 8, 12), (2, 3, 10), (2, 4, 8), (2, 5, 11), (2, 6, 9), (2, 7, 12), (3, 6, 12), (3, 7, 9),
             (3, 8, 11), (4, 6, 11), (4, 7, 10), (5, 8, 10), (5, 9, 12))


# ---- elementary necessary conditions ----------------------------------------------------------------

def erdos_gallai(d) -> bool:
    """Necessary for a simple graph with degrees d: even sum and, for every k, the k largest degrees sum to at
    most k(k-1) + sum_{rest} min(d, k) (edges inside the top k count twice, each other vertex gives <= min(d, k))."""
    s = sorted(d, reverse=True)
    if sum(s) % 2:
        return False
    acc = 0
    for k in range(1, len(s) + 1):
        acc += s[k - 1]
        if acc > k * (k - 1) + sum(min(x, k) for x in s[k:]):
            return False
    return True


def gale_ryser_nec(a, b) -> bool:
    """Necessary for a simple bipartite graph with left degrees a, right degrees b: equal sums and, for every k,
    the k largest left degrees sum to at most sum_right min(b, k)."""
    if sum(a) != sum(b):
        return False
    s = sorted(a, reverse=True)
    acc = 0
    for k in range(1, len(s) + 1):
        acc += s[k - 1]
        if acc > sum(min(x, k) for x in b):
            return False
    return True


# ---- the R7 bound ---------------------------------------------------------------------------------

def g_any(U, t, ntrip) -> int:
    """#trio labels with all members in an ARBITRARY ticket set U: a linear 3-graph on |U| points, 3T3 <= t(U)."""
    return min(r3.packing(len(U)), ntrip, sum(t[v] for v in U) // 3)


class Profile:
    """Profile-level data in r3.degrees order (special tickets first)."""

    def __init__(self, kind, sp, rest):
        self.kind, self.sp, self.rest = kind, tuple(sp), tuple(rest)
        self.t = list(sp) + list(rest)
        self.deg = r3.degrees(kind, sp, rest)
        n = len(self.t)
        self.quad = [kind == "P_C" and i < 4 for i in range(n)]
        self.r = [self.deg[i] - 2 * self.t[i] for i in range(n)]      # R-degree
        self.p = [self.r[i] - 3 * self.quad[i] for i in range(n)]      # pair-label degree
        self.C = [i for i in range(n) if self.t[i] >= 1]
        self.Z = [i for i in range(n) if self.t[i] == 0]
        self.nc, self.nz = len(self.C), len(self.Z)
        self.ntrip = r3.NTRIP[kind]
        self.qC = sum(self.quad[i] for i in self.C)
        self.qZ = sum(self.quad[i] for i in self.Z)
        self.ell = {v: self.nc - 1 - 2 * self.t[v] for v in self.C}
        self.qc = {v: (self.qC - 1) if self.quad[v] else 0 for v in self.C}
        n_l = comb(self.nc, 2) - 3 * self.ntrip
        self.fff0 = (comb(self.nc, 3) - n_l * (self.nc - 2) + sum(comb(x, 2) for x in self.ell.values())
                     - self.ntrip)
        self.w = sum(comb(d, 2) for d in self.deg)
        self._ef: dict = {}

    def ef(self, U):
        """Max e_F(U) under R6's level constraints with g := g_any(U) (None if infeasible); cached by the
        (t, quad) multiset of U, on which level_program depends."""
        key = tuple(sorted((self.t[v], self.quad[v]) for v in U))
        if key not in self._ef:
            us = set(U)
            best, _ = r6.level_program(list(U), [v for v in range(len(self.t)) if v not in us], self.t, self.quad,
                                       g_any(U, self.t, self.ntrip))
            self._ef[key] = None if best is None else best[0]
        return self._ef[key]


def b_edge(C, rC, rZ, ef_of, t, mut=frozenset()) -> int:
    """sum_theta min(EF(U) + ER(U), C(|U|,2)), U = {v in C : rZ_v >= theta} (PROOF.B)."""
    total = 0
    for th in range(1, max((rZ[v] for v in C), default=0) + 1):
        U = [v for v in C if rZ[v] >= th]
        ef = ef_of(U)
        if ef is None:  # level constraints infeasible => no legal configuration; keep a weaker valid cap anyway
            ef = sum(min(2 * t[v], len(U) - 1) for v in U) // 2
        er = sum(min(rC[v], len(U) - 1) for v in U) // 2
        total += min(ef + er, comb(len(U), 2))
    return total - ("BEDGE_MINUS_1" in mut)


def c_zz(C, nz, rZ, dint, cind=True, mut=frozenset()):
    """sum_{v in C} cap on #edges inside N_Z(v) (PROOF.C); None if some rZ_v > |Z|."""
    ez = sum(dint) // 2
    pre = [0]
    for x in sorted(dint):
        pre.append(pre[-1] + x)
    total = 0
    for v in C:
        s = rZ[v]
        if s > nz:
            return None
        c = comb(s, 2)
        if cind:
            m = nz - s
            c = min(c, max(0, ez - pre[m] + comb(m, 2) - ("CIND_MINUS_1" in mut)))
        total += c
    return total


def d_zzz(nz, dint, mut=frozenset()) -> int:
    """#triangles of a graph on Z with degrees dint <= C(nz,3) - |M|(nz-2) + sum C(mu,2) (PROOF.D)."""
    mu = [nz - 1 - d for d in dint]
    return comb(nz, 3) - (sum(mu) // 2) * (nz - 2) + sum(comb(m, 2) for m in mu) - ("D_MINUS_1" in mut)


def r7_bound(kind, sp, rest, mut=frozenset(), cost_cap=None, use_eg=True, use_bedge=True, use_cind=True):
    """(T7, argmax, Profile): T_true <= T7 on every legal configuration with the profile; T7 None + reason if the
    relaxation is empty (no legal configuration), out of scope, or skipped for cost (tests only)."""
    P = Profile(kind, sp, rest)
    if P.qZ:
        return None, "OUT_OF_SCOPE:QUAD_TICKET_WITH_T0", P
    if min(P.ell.values()) < 0:
        return None, "NO_LEGAL:ELL_NEGATIVE", P
    cls: dict = {}
    for v in P.C:
        cls.setdefault((P.t[v], P.p[v], P.quad[v]), []).append(v)
    ckeys = sorted(cls)
    copts = []
    for key in ckeys:
        v0 = cls[key][0]
        lo, hi = max(0, P.p[v0] - P.nz), min(P.p[v0], P.ell[v0] - P.qc[v0])
        if hi < lo:
            return None, "NO_LEGAL:CORE_RANGE_EMPTY", P
        copts.append(list(combinations_with_replacement(range(lo, hi + 1), len(cls[key]))))
    zcls: dict = {}
    for z in P.Z:
        zcls.setdefault(P.r[z], []).append(z)
    zkeys = sorted(zcls)
    zopts = []
    for r in zkeys:
        lo, hi = max(0, r - (P.nz - 1)), min(r, P.nc)
        if hi < lo:
            return None, "NO_LEGAL:Z_RANGE_EMPTY", P
        zopts.append(list(combinations_with_replacement(range(lo, hi + 1), len(zcls[r]))))
    ncore = nzc = 1
    for o in copts:
        ncore *= len(o)
    for o in zopts:
        nzc *= len(o)
    if cost_cap is not None and max(ncore, nzc) > cost_cap:
        return None, f"COST_SKIPPED:{ncore}x{nzc}", P
    zby: dict = {}
    for combo in product(*zopts):
        k = {z: x for r, ms in zip(zkeys, combo) for z, x in zip(zcls[r], ms)}
        dint = [P.r[z] - k[z] for z in P.Z]
        if sum(dint) % 2 or (use_eg and not erdos_gallai(dint)):
            continue
        bz = sum(comb(k[z], 2) for z in P.Z) - ("BZ_MINUS_1" in mut)
        zby.setdefault(sum(k.values()), []).append((combo, list(k.values()), dint, d_zzz(P.nz, dint, mut), bz))
    best = arg = None
    for combo in product(*copts):
        j = {v: x for key, ms in zip(ckeys, combo) for v, x in zip(cls[key], ms)}
        if sum(j.values()) % 2 or (use_eg and not erdos_gallai(list(j.values()))):
            continue
        rC = {v: j[v] + P.qc[v] for v in P.C}
        rZ = {v: P.p[v] - j[v] for v in P.C}
        w2 = sum(rC[v] * (P.nc - 2 * P.ell[v]) for v in P.C)
        a = sum(comb(rC[v], 2) for v in P.C) - comb(P.qC, 3) - ("A_MINUS_1" in mut)
        be = b_edge(P.C, rC, rZ, P.ef, P.t, mut) if use_bedge else None
        for zc, ks, dint, dz, bz in zby.get(sum(rZ.values()), ()):
            if not gale_ryser_nec([rZ[v] for v in P.C], ks):
                continue
            cz = c_zz(P.C, P.nz, rZ, dint, use_cind, mut)
            if cz is None:
                continue
            bb = bz if be is None else min(bz, be)
            val2 = 2 * (P.fff0 - ("FFF0_MINUS_1" in mut)) + w2 + 2 * (a + bb + cz + dz)
            if best is None or val2 > best:
                best = val2
                arg = {"J_BY_CORE_CLASS_T_P_QUAD": {f"{kk[0]},{kk[1]},{int(kk[2])}": list(ms)
                                                    for kk, ms in zip(ckeys, combo)},
                       "K_BY_Z_CLASS_R": {str(r): list(ms) for r, ms in zip(zkeys, zc)},
                       "FFF0": P.fff0, "W_R": w2 // 2, "A": a, "B_Z": bz, "B_EDGE": be, "C_ZZ": cz, "D_ZZZ": dz}
    if best is None:
        return None, "NO_LEGAL:RELAXATION_EMPTY", P
    return best // 2 - ("T7_MINUS_1" in mut), arg, P


def ub_from_t(kind: str, w: int, t_true: int) -> int:
    return S1_MINUS_S2 + 2800 * w + 11872 * t_true - 1400 * r3.TSTAR[kind]


# ---- legal configurations: brute-force edge-class decomposition (tests only, never used for pruning) -------

def tickets_from(blocks) -> list[frozenset[int]]:
    assert len(blocks) == 49
    tk: list[set[int]] = [set() for _ in range(20)]
    for label, blk in enumerate(blocks, 1):
        for u in blk:
            tk[u].add(label)
    return [frozenset(x) for x in tk]


def c9_config() -> list[frozenset[int]]:
    """Legal P_A config on profile 2607: 23 trios = K13 minus a 9-cycle, 5 pairs, K7 minus one edge on Z, singleton."""
    cyc = {frozenset((4 + i, 4 + (i + 1) % 9)) for i in range(9)}
    cover = Counter(frozenset(p) for b in C9_BLOCKS for p in combinations(b, 2))
    assert set(cover) == {frozenset(p) for p in combinations(range(13), 2)} - cyc and set(cover.values()) == {1}
    zs = range(13, 20)
    return tickets_from([(19,)] + list(C9_BLOCKS) + [(4, 5), (6, 7), (8, 9), (10, 11), (12, 13)]
                        + [p for p in combinations(zs, 2) if p != (13, 19)])


def k12_e_config() -> list[frozenset[int]]:
    """Legal P_A config on profile 2606 where B_EDGE and the CIND cap both bind: the 20 trios of STS(13) minus
    point 12 on tickets 0..11 (leave = a 1-factor); three leave pairs become E-trios with tickets 12, 13, 14 (t = 1),
    three stay pair labels; each E ticket meets all of Z = 15..19 (15 = singleton); G[Z] = K5 minus 3 edges."""
    sts = {frozenset((x + a) % 13 for a in base) for x in range(13) for base in ((0, 1, 4), (0, 2, 7))}
    trios = [tuple(sorted(b)) for b in sts if 12 not in b]
    leave = sorted(tuple(sorted(b - {12})) for b in sts if 12 in b)
    assert len(trios) == 20 and sorted(u for pr in leave for u in pr) == list(range(12))
    e_trios = [leave[i] + (12 + i,) for i in range(3)]
    zs = range(15, 20)
    z_pairs = [p for p in combinations(zs, 2) if p not in ((15, 16), (15, 17), (18, 19))]
    return tickets_from([(15,)] + sorted(trios) + e_trios + leave[3:] + [(e, z) for e in (12, 13, 14) for z in zs]
                        + z_pairs)


def decompose(tk: list[frozenset[int]], mut=frozenset()) -> dict:
    """Count true triangles by edge class on a legal config; evaluate every PROOF identity/inequality on it."""
    base = r3.analyze(tk)  # asserts legality, the Shell-1 histogram, T_true and the S3 formula
    kind, n = base["KIND"], 20
    hold = {y: [u for u in range(n) if y in tk[u]] for y in range(1, 50)}
    size = {y: len(h) for y, h in hold.items()}
    lab = {frozenset(p): y for y, h in hold.items() for p in combinations(h, 2)}
    t = [sum(size[y] == 3 for y in tk[u]) for u in range(n)]
    quad = [any(size[y] == 4 for y in tk[u]) for u in range(n)]
    cls = {e: ("F" if size[y] == 3 else "R") for e, y in lab.items()}

    def ec(a, b):
        return cls.get(frozenset((a, b)))

    C = [v for v in range(n) if t[v] >= 1]
    Z = [v for v in range(n) if t[v] == 0]
    cs = set(C)
    nc, nz = len(C), len(Z)
    out = {"KIND": kind, "SPECIAL": list(base["SPECIAL"]), "REST": list(base["REST"]), "W": base["W"],
           "T_TRUE": base["T_TRUE"]}
    if any(quad[z] for z in Z):
        out["SCOPE"] = "OUT_OF_SCOPE:QUAD_TICKET_WITH_T0"
        return out
    ty: Counter = Counter()
    for a, b, c in combinations(range(n), 3):
        es = [ec(a, b), ec(a, c), ec(b, c)]
        if None in es or len({lab[frozenset((a, b))], lab[frozenset((a, c))], lab[frozenset((b, c))]}) == 1:
            continue
        nf, zc = es.count("F"), sum(v not in cs for v in (a, b, c))
        if nf == 3:
            ty["FFF"] += 1
        elif nf == 2:
            ty["FFR"] += 1
        elif nf == 1:
            apex = c if es[0] == "F" else (b if es[1] == "F" else a)
            ty["FRR_C" if apex in cs else "FRR_Z"] += 1
        else:
            ty["RRR_" + "C" * (3 - zc) + "Z" * zc] += 1
    tt = sum(ty.values())
    L = {frozenset(p) for p in combinations(C, 2) if ec(*p) != "F"}
    ell = {v: sum(v in e for e in L) for v in C}
    t_l = sum(1 for a, b, c in combinations(C, 3)
              if frozenset((a, b)) in L and frozenset((a, c)) in L and frozenset((b, c)) in L)
    rn = {v: [u for u in range(n) if u != v and ec(u, v) == "R"] for v in range(n)}
    rC = {v: sum(u in cs for u in rn[v]) for v in range(n)}
    rZ = {v: len(rn[v]) - rC[v] for v in range(n)}
    deg_z = {v: sum(1 for u in Z if u != v and frozenset((u, v)) in lab) for v in range(n)}
    qC = sum(quad[v] for v in C)
    rcc = [e for e in L if cls.get(e) == "R"]
    lam = {e: sum(1 for x in C if x not in e and all(frozenset((x, u)) in L for u in e)) for e in rcc}
    P = Profile(kind, base["SPECIAL"], base["REST"])
    w_r = sum(nc - ell[u] - ell[v] for u, v in map(tuple, rcc))
    j = {v: rC[v] - (qC - 1 if quad[v] else 0) for v in C}
    k = {z: rC[z] for z in Z}
    dint = [rZ[z] for z in Z]
    pv = {v: len(rn[v]) - 3 * quad[v] for v in range(n)}
    ok = {
        "T_TRUE_CLASS_SUM": tt == base["T_TRUE"],
        "ELL": all(ell[v] == nc - 1 - 2 * t[v] for v in C),
        "Z_EDGES_ARE_R": all(deg_z[v] == rZ[v] for v in C),
        "FFF_EXACT": ty["FFF"] == P.fff0 - t_l,
        "FFR_EXACT": ty["FFR"] == w_r + sum(lam.values()),
        "W_R_FORMULA": 2 * w_r == sum(rC[v] * (nc - 2 * ell[v]) for v in C),
        # the relaxation's filters hold on the actual assignment
        "J_RANGE": all(max(0, pv[v] - nz) <= j[v] <= min(pv[v], ell[v] - (qC - 1 if quad[v] else 0)) for v in C),
        "K_RANGE": all(max(0, len(rn[z]) - (nz - 1)) <= k[z] <= min(len(rn[z]), nc) for z in Z),
        "J_PARITY_EG": erdos_gallai(list(j.values())),
        "DINT_PARITY_EG": erdos_gallai(dint),
        "GALE_RYSER": gale_ryser_nec([rZ[v] for v in C], list(k.values())),
    }
    lhs_a = sum(lam.values()) - t_l + ty["FRR_C"] + ty["RRR_CCC"]
    rhs_a = sum(comb(rC[v], 2) for v in C) - comb(qC, 3) - ("A_MINUS_1" in mut)
    indep = sum(1 for a, b, c in combinations(C, 3)
                if not (frozenset((a, b)) in lab or frozenset((a, c)) in lab or frozenset((b, c)) in lab))
    lhs_b = ty["FRR_Z"] + ty["RRR_CCZ"]
    bz = sum(comb(k[z], 2) for z in Z) - ("BZ_MINUS_1" in mut)
    lev_ok = {"IDENTITIES": True, "G_ANY": True, "IN3": True, "CAP_U": True, "CAP_D": True, "EF_LE_LP_MAX": True,
              "ER_LE_CAP": True}
    naive, lp_tight = [], 0
    caps = r6.prefix_caps(P.deg, P.t, P.ntrip)

    def ef_actual(U):
        nonlocal naive, lp_tight
        us = set(U)
        D = [v for v in range(n) if v not in us]
        T = Counter(sum(u in us for u in hold[y]) for y in hold if size[y] == 3)
        ef_u = sum(ec(a, b) == "F" for a, b in combinations(U, 2))
        ef_d = sum(ec(a, b) == "F" for a, b in combinations(D, 2))
        av = {v: r6.avail(v, U if v in us else D, t, quad) for v in range(n)}
        g = g_any(U, t, r3.NTRIP[kind])
        lev_ok["IDENTITIES"] &= (sum(t[v] for v in U) == 3 * T[3] + 2 * T[2] + T[1]
                                 and sum(t[v] for v in D) == 3 * T[0] + 2 * T[1] + T[2]
                                 and ef_u == 3 * T[3] + T[2] and ef_d == 3 * T[0] + T[1])
        lev_ok["G_ANY"] &= T[3] <= g
        lev_ok["IN3"] &= 3 * T[3] <= sum(min(t[v], av[v] // 2) for v in U)
        lev_ok["CAP_U"] &= ef_u <= sum(min(2 * t[v], av[v]) for v in U) // 2
        lev_ok["CAP_D"] &= ef_d <= sum(min(2 * t[v], av[v]) for v in D) // 2
        best, _ = r6.level_program(U, D, t, quad, g)
        lev_ok["EF_LE_LP_MAX"] &= best is not None and ef_u <= best[0]
        lp_tight += best is not None and ef_u == best[0]
        lev_ok["ER_LE_CAP"] &= (sum(ec(a, b) == "R" for a, b in combinations(U, 2))
                                <= sum(min(rC[v], len(U) - 1) for v in U) // 2)
        if T[3] > caps[len(U) - 1]:  # R6's degree-prefix cap applied (wrongly) to a non-prefix set
            naive.append((len(U), T[3], caps[len(U) - 1]))
        return None if best is None else best[0]

    be = b_edge(C, rC, rZ, ef_actual, t, mut)
    cz = c_zz(C, nz, rZ, dint, True, mut)
    dz = d_zzz(nz, dint, mut)
    psi = P.fff0 - ("FFF0_MINUS_1" in mut) + w_r + rhs_a + min(bz, be) + (cz if cz is not None else -10**9) + dz
    edge_side = sum(min(rZ[u], rZ[v]) for u, v in combinations(C, 2) if frozenset((u, v)) in lab)
    ok.update({
        "A": lhs_a <= rhs_a,
        "A_SLACK_EQ_INDEPENDENT_CORE_TRIPLES": "A_MINUS_1" in mut or rhs_a - lhs_a == indep,
        "B_Z": lhs_b <= bz,
        "B_EDGE_COUNT": lhs_b <= edge_side <= be,
        "C": cz is not None and ty["RRR_CZZ"] <= cz,
        "D": ty["RRR_ZZZ"] <= dz,
        **{"LEVEL_" + key: val for key, val in lev_ok.items()},
        "T_TRUE_LE_PSI": tt <= psi,
    })
    out.update(SCOPE="IN_SCOPE", TYPES=dict(ty), PSI=psi, OK=ok,
               TIGHT={"A": lhs_a == rhs_a, "B": lhs_b == min(bz, be), "C": ty["RRR_CZZ"] == cz,
                      "C_WITH_CIND_BINDING": ty["RRR_CZZ"] == cz and cz < sum(comb(rZ[v], 2) for v in C),
                      "B_WITH_BEDGE_BINDING": lhs_b == be < bz, "D": ty["RRR_ZZZ"] == dz, "PSI": tt == psi},
               LP_LEVELS_TIGHT=lp_tight, NAIVE_PREFIX_CAP_VIOLATIONS=naive)
    return out


# ---- smallest-counterexample search for the generalized level constraints ----------------------------------

def small_level_search(n_max: int) -> dict:
    """Every linear 3-graph H on n <= n_max labelled points (t = H-degree), every quad marking Q (|Q| in 0, 2..4,
    no trio holding two Q points), every U: identities + (a') g_any + (b) + (c) for U and D, and level_program
    (with g_any) >= e_F(U). The first failure, if any, is the smallest counterexample."""
    st: Counter = Counter()
    first = None
    for n in range(3, n_max + 1):
        trs = list(combinations(range(n), 3))
        systems: list = []

        def rec(i, cur, used):
            if cur:
                systems.append(list(cur))
            for x in range(i, len(trs)):
                ps = [frozenset(p) for p in combinations(trs[x], 2)]
                if not any(p in used for p in ps):
                    cur.append(trs[x])
                    rec(x + 1, cur, used | set(ps))
                    cur.pop()

        rec(0, [], frozenset())
        st[f"LINEAR_3_GRAPHS_N{n}"] = len(systems)
        for H in systems:
            t = [sum(v in h for h in H) for v in range(n)]
            pairs = {frozenset(p) for h in H for p in combinations(h, 2)}
            qs = [()] + [q for s in (2, 3, 4) for q in combinations(range(n), s)
                         if not any(frozenset(p) in pairs for p in combinations(q, 2))]
            for Q in qs:
                quad = [v in Q for v in range(n)]
                for mask in range(1 << n):
                    U = [v for v in range(n) if mask >> v & 1]
                    D = [v for v in range(n) if not mask >> v & 1]
                    us = set(U)
                    T = Counter(sum(v in us for v in h) for h in H)
                    av = {v: r6.avail(v, U if v in us else D, t, quad) for v in range(n)}
                    g = min(r3.packing(len(U)), len(H), sum(t[v] for v in U) // 3)
                    ef_u = 3 * T[3] + T[2]
                    good = (T[3] <= g and 3 * T[3] <= sum(min(t[v], av[v] // 2) for v in U)
                            and ef_u <= sum(min(2 * t[v], av[v]) for v in U) // 2
                            and 3 * T[0] + T[1] <= sum(min(2 * t[v], av[v]) for v in D) // 2)
                    best, _ = r6.level_program(U, D, t, quad, g)
                    good &= best is not None and best[0] >= ef_u
                    st["CASES"] += 1
                    if not good:
                        st["FAILURES"] += 1
                        first = first or {"N": n, "TRIOS": H, "QUAD": list(Q), "U": U}
    return {"N_MAX": n_max, **dict(st), "FAILURES": st["FAILURES"], "SMALLEST_COUNTEREXAMPLE": first}


def constants_reevaluated() -> dict:
    """S1 - S2 on the shell and the S3 triple weights from the frozen first-principles co_win DP."""
    a = frozenset(range(1, 7))
    single = cst.co_win([a])
    q0 = cst.co_win([a, frozenset(range(7, 13))])
    q1 = cst.co_win([a, frozenset([1] + list(range(7, 12)))])
    path = cst.co_win([a, frozenset([1, 7, 8, 9, 10, 11]), frozenset([7, 13, 14, 15, 16, 17])])
    star = cst.co_win([a, frozenset([1, 7, 8, 9, 10, 11]), frozenset([1, 13, 14, 15, 16, 17])])
    tri = cst.co_win([a, frozenset([1, 7, 8, 9, 10, 11]), frozenset([2, 7, 13, 14, 15, 16])])
    s12 = 20 * single - (190 - r3.E) * q0 - r3.E * q1
    return {"SINGLE": single, "Q0": q0, "Q1": q1, "PATH": path, "STAR": star, "TRIANGLE": tri,
            "S1_MINUS_S2": s12, "S3_WEDGE_COEF": path, "S3_TRUE_COEF": tri - 3 * path, "S3_STAR_COEF": star - 3 * path,
            "S3_FORMULA": "S3 = PATH*paths + STAR*stars + TRIANGLE*true, paths = W - 3*(stars + true)"
                          " => S3 = 2800*W + 11872*T_true - 1400*Tstar",
            "MATCHES_R3": (s12 == S1_MINUS_S2 and path == 2800 and tri - 3 * path == 11872
                           and star - 3 * path == -1400)}


# ---- driver ---------------------------------------------------------------------------------------------

def profile_key(kind, sp, rest):
    return kind, tuple(sp), tuple(rest)


def evaluate(i: int, row: dict, table: dict) -> dict:
    kind, sp, rest = row["KIND"], tuple(row["SPECIAL"]), tuple(row["REST"])
    deg, t = r3.degrees(kind, sp, rest), list(sp) + list(rest)
    w = sum(comb(d, 2) for d in deg)
    # R6's certified UB, recomputed exactly as R6.evaluate: min(UB_R6, UB_R5) with UB_R5 = min(ub5, ub_wedge)
    km = r3.kmax(deg, t, r3.NTRIP[kind])
    b4 = 3 * km + table[tuple(sorted(d - 3 for d in deg[:4]))] if kind == "P_C" else 3 * km
    ub5 = min(S1_MINUS_S2 + r5.s3_ub5(kind, w, b4, r5.n1_bound(kind, sp, rest)[0]),
              S1_MINUS_S2 + r3.s3_wedge(kind, w))
    jb = r6.joint_bound(kind, sp, rest, table)
    ub_r6 = min(S1_MINUS_S2 + r3.s3_ub(kind, w, jb["J"]), ub5) if jb["J"] is not None else None
    t_max = (INCUMBENT - ub_from_t(kind, w, 0)) // 11872
    t7, arg, prof = r7_bound(kind, sp, rest)
    rec = {"index": i, "KIND": kind, "SPECIAL": list(sp), "REST": list(rest), "W": w, "NC": prof.nc, "NZ": prof.nz,
           "UB_R6": ub_r6, "T_MAX_FOR_NO_GAIN": t_max, "R6_T_TRUE_CAP": (940 + jb["J"]) // 6 if jb["J"] is not None else None,
           "T7": t7, "T7_NO_EG": r7_bound(kind, sp, rest, use_eg=False)[0],
           "T7_NO_BEDGE": r7_bound(kind, sp, rest, use_bedge=False)[0],
           "T7_NO_CIND": r7_bound(kind, sp, rest, use_cind=False)[0]}
    if t7 is None:
        rec.update(UB_R7=None, UB=ub_r6, REASON=arg,
                   STATUS="NO_LEGAL_CONFIGURATION" if arg.startswith("NO_LEGAL") else "REMAINING")
        return rec
    ub7 = ub_from_t(kind, w, t7)
    ub = min(ub7, ub_r6)
    rec.update(UB_R7=ub7, UB=ub, T_UNITS_BELOW_THRESHOLD=t_max - t7, ARGMAX=arg,
               STATUS="BOUND_PRUNED" if ub <= INCUMBENT else "REMAINING")
    return rec


def generated_configs(rng: random.Random):
    for gen in ("RANDOM_R5", "DESIGN_R6"):
        for kind in ("P_A", "P_C"):
            made = 0
            while made < CONFIGS_PER_CELL:
                tk = r5.random_config(rng, kind) if gen == "RANDOM_R5" else r6.design_config(rng, kind)
                if tk is not None:
                    made += 1
                    yield f"{gen}:{kind}", tk


def main() -> None:
    r6_res = json.loads((HERE / "joint_kn1_bound_r6.json").read_text())
    surv = json.loads((HERE / "survivors.json").read_text())
    idx = sorted(r6_res["UNRESOLVED_LOCATOR"]["INDICES"])
    idx_sha = hashlib.sha256(",".join(map(str, idx)).encode()).hexdigest()
    r6_ok = (r6_res["SCIENTIFIC_STATUS"] == "PARTIAL_BOUND_CERTIFIED" and r6_res["JOINT_BOUND_ADMISSIBILITY"] == "PROVED"
             and all(r6_res["CHECKS"].values()) and idx_sha == R6_INDEX_SHA and len(idx) == 69
             and r6_res["MAX_VALID_UPPER_BOUND"] == R6_MAX_UB and len(surv) == 58480)
    table = r4.quad_table()[0]
    consts = constants_reevaluated()

    recs = [evaluate(i, surv[i], table) for i in idx]
    by_ub6 = sorted(recs, key=lambda r: (-r["UB_R6"], r["index"]))
    r6_reproduced = (all(r["UB_R6"] is not None and r["UB_R6"] > INCUMBENT for r in recs)
                     and by_ub6[0]["UB_R6"] == R6_MAX_UB and by_ub6[0]["index"] == 2607
                     and all(sum(r["KIND"] == k for r in recs) == n for k, n in R6_COUNTS.items()))
    scope_ok = all(Profile(r["KIND"], r["SPECIAL"], r["REST"]).qZ == 0 for r in recs)

    acct = {k: Counter() for k in R6_COUNTS}
    for r in recs:
        c = acct[r["KIND"]]
        c["INPUT"] += 1
        if r["STATUS"] == "REMAINING":
            c["REMAINING"] += 1
        else:
            c["NEWLY_PRUNED"] += 1
            c[r["STATUS"]] += 1
            c["BOUND_PRUNED_AT_EQUALITY"] += r["STATUS"] == "BOUND_PRUNED" and r["UB"] == INCUMBENT
        c["PRUNED_WITHOUT_EG"] += r["T7_NO_EG"] is not None and r["T7_NO_EG"] <= r["T_MAX_FOR_NO_GAIN"]
        c["PRUNED_WITHOUT_BEDGE"] += r["T7_NO_BEDGE"] is not None and r["T7_NO_BEDGE"] <= r["T_MAX_FOR_NO_GAIN"]
        c["PRUNED_WITHOUT_CIND"] += r["T7_NO_CIND"] is not None and r["T7_NO_CIND"] <= r["T_MAX_FOR_NO_GAIN"]
    remaining = sorted((r for r in recs if r["STATUS"] == "REMAINING"), key=lambda r: (-r["UB"], r["index"]))
    rem_idx = sorted(r["index"] for r in remaining)
    with_ub = [r for r in recs if r["UB"] is not None]
    top = max(with_ub, key=lambda r: (r["UB"], -r["index"]))
    max_ub = top["UB"]

    # ---- falsification -------------------------------------------------------------------------
    surv_idx = {profile_key(r["KIND"], r["SPECIAL"], r["REST"]): i for i, r in enumerate(surv)}
    open69 = {profile_key(r["KIND"], r["SPECIAL"], r["REST"]): r["index"] for r in recs}
    r2 = json.loads((HERE / "k_bound_validation_r2.json").read_text())
    named = {"K12_K8_LIFT": r3.k12_k8(), "C9_ON_PROFILE_2607": c9_config(), "K12_E_ON_PROFILE_2606": k12_e_config(),
             "R2_P_C_STEP_COUNTEREXAMPLE": [frozenset(x) for x in
                                            r2["BOUND_ADMISSIBILITY"]["P_C_STEP_COUNTEREXAMPLE"]["tickets"]]}
    named_out, named_ok, equality = {}, True, {}
    gen: Counter = Counter()
    for name, tk in named.items():
        d = decompose(tk)
        key = profile_key(d["KIND"], d["SPECIAL"], d["REST"])
        rec = {k: d[k] for k in ("KIND", "SPECIAL", "REST", "W", "T_TRUE", "SCOPE")}
        rec.update(SURVIVORS_INDEX=surv_idx.get(key), IN_R6_REMAINING_69=key in open69)
        if d["SCOPE"] == "IN_SCOPE":
            t7, arg, _ = r7_bound(*key)
            rec.update(TYPES=d["TYPES"], PSI_AT_ACTUAL_ASSIGNMENT=d["PSI"], T7=t7,
                       T7_NO_EG=r7_bound(*key, use_eg=False)[0], ALL_CHECKS_PASS=all(d["OK"].values()),
                       FAILED=[k for k, v in d["OK"].items() if not v], TIGHT=d["TIGHT"],
                       EQUALITY_T_TRUE_EQ_T7=t7 == d["T_TRUE"], NAIVE_PREFIX_CAP_VIOLATIONS=d["NAIVE_PREFIX_CAP_VIOLATIONS"])
            named_ok &= rec["ALL_CHECKS_PASS"] and t7 is not None and d["T_TRUE"] <= t7
            equality[name] = (key, d["T_TRUE"]) if t7 == d["T_TRUE"] else None
            for k, v in d["TIGHT"].items():
                gen[f"NAMED:TIGHT:{k}"] += v
        named_out[name] = rec

    min_slack: dict = {}
    naive_examples: list = []
    focus_hits: dict = {str(f): [] for f in FOCUS}
    t7_cache: dict = {}
    for cell, tk in generated_configs(random.Random(SEED)):
        d = decompose(tk)
        gen[f"{cell}:CONFIGS"] += 1
        if d["SCOPE"] != "IN_SCOPE":
            gen[f"{cell}:OUT_OF_SCOPE_QUAD_T0"] += 1
            continue
        gen[f"{cell}:IN_SCOPE"] += 1
        gen[f"{cell}:ALL_CHECKS_PASS"] += all(d["OK"].values())
        for k, v in d["OK"].items():
            gen[f"{cell}:FAIL:{k}"] += not v
        for k, v in d["TIGHT"].items():
            gen[f"{cell}:TIGHT:{k}"] += v
        gen[f"{cell}:LP_LEVELS_TIGHT"] += d["LP_LEVELS_TIGHT"]
        if d["NAIVE_PREFIX_CAP_VIOLATIONS"]:
            gen[f"{cell}:NAIVE_PREFIX_CAP_VIOLATED"] += 1
            naive_examples.append({"CELL": cell, "PROFILE": [d["KIND"], d["SPECIAL"], d["REST"]],
                                   "U_SIZE_T3_GPREFIX": min(d["NAIVE_PREFIX_CAP_VIOLATIONS"])})
        key = profile_key(d["KIND"], d["SPECIAL"], d["REST"])
        gen[f"{cell}:IN_SURVIVORS"] += key in surv_idx
        gen[f"{cell}:IN_R6_REMAINING_69"] += key in open69
        if key in open69 and str(open69[key]) in focus_hits:
            focus_hits[str(open69[key])].append(d["T_TRUE"])
        if key not in t7_cache:
            t7_cache[key] = r7_bound(*key, cost_cap=T7_COST_CAP)[:2]
        t7, why = t7_cache[key]
        if t7 is None:
            gen[f"{cell}:T7_{why.split(':')[0]}"] += 1
            continue
        gen[f"{cell}:T7_EVALUATED"] += 1
        gen[f"{cell}:PSI_LE_T7"] += d["PSI"] <= t7
        gen[f"{cell}:T_TRUE_LE_T7"] += d["T_TRUE"] <= t7
        min_slack[cell] = min(min_slack.get(cell, 10**9), t7 - d["T_TRUE"])
    cells = sorted({k.rsplit(":", 1)[0] for k in gen if k.endswith(":CONFIGS")})
    gen_ok = all(gen[f"{c}:ALL_CHECKS_PASS"] == gen[f"{c}:IN_SCOPE"] and gen[f"{c}:T7_NO_LEGAL"] == 0
                 and gen[f"{c}:PSI_LE_T7"] == gen[f"{c}:T_TRUE_LE_T7"] == gen[f"{c}:T7_EVALUATED"] for c in cells)

    mutants = {}
    for m in MUTANTS:
        caught = []
        for name, eq in equality.items():
            if eq is None:
                continue
            key, tt = eq
            tm = r7_bound(*key, mut=frozenset({m}))[0]
            if tm is not None and tm < tt:
                caught.append(name)
        mutants[m] = {"CAUGHT_BY_EQUALITY_CONFIGS": caught,
                      "COMPONENT_TIGHT_ON_LEGAL_CONFIGS": sum(
                          gen[f"{c}:TIGHT:{x}"] for c in cells + ["NAMED"] for x in
                          {"A_MINUS_1": ["A"], "BZ_MINUS_1": ["B"], "BEDGE_MINUS_1": ["B_WITH_BEDGE_BINDING"],
                           "CIND_MINUS_1": ["C_WITH_CIND_BINDING"],
                           "D_MINUS_1": ["D"], "T7_MINUS_1": ["PSI"], "FFF0_MINUS_1": ["PSI"]}[m])}
    small = small_level_search(SMALL_N_MAX)

    focus = {}
    for f in FOCUS:
        r = next(x for x in recs if x["index"] == f)
        focus[str(f)] = {k: r.get(k) for k in ("KIND", "SPECIAL", "REST", "W", "NC", "NZ", "UB_R6", "R6_T_TRUE_CAP",
                                               "T_MAX_FOR_NO_GAIN", "T7", "T7_NO_EG", "T7_NO_BEDGE", "T7_NO_CIND",
                                               "UB_R7", "UB", "STATUS", "ARGMAX")}
        focus[str(f)]["GENERATED_LEGAL_CONFIGS_ON_PROFILE_T_TRUE"] = sorted(focus_hits[str(f)], reverse=True)
    focus["2607"]["NAMED_CONFIG"] = "C9_ON_PROFILE_2607: T_TRUE 239 = T7 239 (EG on): equality"
    focus["2606"]["NAMED_CONFIG"] = ("K12_E_ON_PROFILE_2606: T_TRUE 223 <= Psi = T7 248; B_EDGE and the CIND cap bind"
                                     " and are tight; the 25-unit gap is A's slack (edgeless core triples)")

    n_rem = len(remaining)
    checks = {
        "FROZEN_INPUTS": HASHES == FROZEN,
        "R6_RESULT_INHERITED": r6_ok,
        "R6_UB_REPRODUCED_ON_69": r6_reproduced,
        "CONSTANTS_REEVALUATED": consts["MATCHES_R3"],
        "SCOPE_ALL_QUAD_TICKETS_IN_CORE_ON_69": scope_ok,
        "NAMED_CONFIGS_ALL_INEQUALITIES": named_ok,
        "K12_E_EXERCISES_BINDING_BEDGE_AND_CIND": named_out["K12_E_ON_PROFILE_2606"]["IN_R6_REMAINING_69"]
        and named_out["K12_E_ON_PROFILE_2606"]["TIGHT"]["B_WITH_BEDGE_BINDING"]
        and named_out["K12_E_ON_PROFILE_2606"]["TIGHT"]["C_WITH_CIND_BINDING"],
        "EQUALITY_K12_K8_AND_C9": equality.get("K12_K8_LIFT") is not None
                                 and equality.get("C9_ON_PROFILE_2607") is not None,
        "GENERATED_CONFIGS_ALL_INEQUALITIES_AND_T_LE_T7": gen_ok,
        "SMALL_LEVEL_SEARCH_NO_COUNTEREXAMPLE": small["FAILURES"] == 0,
        "ACCOUNTING_CLOSES": sum(acct[k]["INPUT"] for k in acct) == 69
                             and sum(acct[k]["NEWLY_PRUNED"] + acct[k]["REMAINING"] for k in acct) == 69,
    }
    all_ok = all(checks.values())
    if not all_ok:
        bound_status = "INVALID" if not (named_ok and gen_ok) else "NOT_PROVED"
    else:
        bound_status = "PROVED"
    shell1 = ("PROVED_NO_STRICT_GAIN_WITHIN_DEFINED_SHELL1" if all_ok and n_rem == 0
              else "PARTIAL_BOUND_CERTIFIED" if all_ok else "NOT_PROVED")
    ru = resource.getrusage(resource.RUSAGE_SELF)
    result = {
        "TASK_ID": "B649_K20_V8_SHELL1_COMMON_NEIGHBOUR_CAPACITY_R7",
        "CREATED": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "BASE": subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True,
                               text=True).stdout.strip(),
        "CANONICAL": {"K20_COUNT": INCUMBENT, "K20_SHA256": r3.K20_SHA256, "S1_MINUS_S2_SHELL1": S1_MINUS_S2,
                      "S3_THRESHOLD": INCUMBENT - S1_MINUS_S2},
        "FROZEN_INPUTS_SHA256": FROZEN,
        "IMPLEMENTATION": {"PATH": Path(__file__).name,
                           "SHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        "PREDECESSOR_R6": {"RESULT": "joint_kn1_bound_r6.json", "INPUT_PROFILES": 69, **R6_COUNTS,
                           "INDEX_LIST_SHA256": idx_sha, "MAX_UB_R6": by_ub6[0]["UB_R6"],
                           "MAX_UB_R6_INDEX": by_ub6[0]["index"]},
        "PROVENANCE": PROVENANCE,
        "DEFINITIONS": DEFINITIONS,
        "FORMULA": FORMULA,
        "PROOF": PROOF,
        "R6_INVARIANTS_UNDER_ARBITRARY_SUBSET_RESTRICTION": R6_INVARIANTS,
        "PROOF_ASSUMPTIONS": ASSUMPTIONS,
        "CONSTANTS_REEVALUATED": consts,
        "ACCOUNTING": {
            "INPUT_PROFILES": 69,
            "BY_KIND": {k: dict(sorted(v.items())) for k, v in acct.items()},
            "P_A_NEWLY_PRUNED": acct["P_A"]["NEWLY_PRUNED"], "P_A_REMAINING": acct["P_A"]["REMAINING"],
            "P_C_NEWLY_PRUNED": acct["P_C"]["NEWLY_PRUNED"], "P_C_REMAINING": acct["P_C"]["REMAINING"],
            "TOTAL_NEWLY_PRUNED": 69 - n_rem, "TOTAL_REMAINING": n_rem,
            "REMAINING_INDICES": rem_idx,
            "REMAINING_INDEX_LIST_SHA256": hashlib.sha256(",".join(map(str, rem_idx)).encode()).hexdigest(),
            "LOAD_BEARING": {
                name: [r["index"] for r in recs if r[col] is None or r[col] > r["T_MAX_FOR_NO_GAIN"]]
                for name, col in (("EG", "T7_NO_EG"), ("BEDGE_ARBITRARY_SUBSET_LEVEL_PROGRAM", "T7_NO_BEDGE"),
                                  ("CIND", "T7_NO_CIND"))},
            "T_UNITS_BELOW_THRESHOLD_HISTOGRAM": {str(k): v for k, v in sorted(Counter(
                r.get("T_UNITS_BELOW_THRESHOLD") for r in recs).items(), key=lambda x: (x[0] is None, x[0] or 0))},
            "NOTE": "Applied once to R6's 69 open profiles (R1-R6-pruned profiles stay pruned). UB = min(UB_R6, UB_R7);"
                    " prune iff UB <= 313263888 (equality would be a tie, never a strict gain).",
        },
        "PROFILES": recs,
        "FOCUS_PROFILES": focus,
        "FALSIFICATION": {
            "NAMED": named_out,
            "PRIOR_1203_LEGAL_CONFIGS": "NOT_PRESERVED: generated in memory by the interrupted R7 session, never written",
            "GENERATED": {"SEED": SEED, "CONFIGS_PER_CELL": CONFIGS_PER_CELL, "T7_COST_CAP": T7_COST_CAP,
                          "COUNTS": dict(sorted(gen.items())), "MIN_T7_MINUS_T_TRUE": min_slack,
                          "NAIVE_PREFIX_CAP_EXAMPLES": naive_examples[:5]},
            "MUTANTS": {"RULE": "a -1 strengthening of a term is caught if it lowers T7 below T_TRUE of an"
                                " equality configuration, or if the term is tight (and binding) on a named or"
                                " generated legal configuration", "ALL_CAUGHT": all(
                v["CAUGHT_BY_EQUALITY_CONFIGS"] or v["COMPONENT_TIGHT_ON_LEGAL_CONFIGS"] for v in mutants.values()),
                        **mutants},
            "SMALL_EXHAUSTIVE_LEVEL_CONSTRAINT_SEARCH": small,
        },
        "CHECKS": checks,
        "MAX_VALID_UPPER_BOUND": max_ub,
        "MAX_VALID_UPPER_BOUND_INDEX": top["index"],
        "GAP_VS_313263888": max_ub - INCUMBENT,
        "REMAINING_PROOF_GAPS": [] if shell1.startswith("PROVED") else ["see CHECKS / ACCOUNTING.REMAINING_INDICES"],
        "SCOPE_CAVEATS": SCOPE_CAVEATS,
        "R7_STATUS": "COMPLETE" if all_ok else "PARTIAL",
        "R7_BOUND_STATUS": bound_status,
        "BONFERRONI_AUTHORITY_STATUS": "INDEPENDENTLY_VERIFIED_2026-10-08_AND_REEVALUATED_HERE"
                                       if consts["MATCHES_R3"] else "MISMATCH",
        "SHELL1_STATUS": shell1,
        "NO_CPSAT": True,
        "MULTIPROCESSING": False,
        "CPU_SECONDS": round(ru.ru_utime + ru.ru_stime, 2),
    }
    canon = json.loads(json.dumps(result))  # as re-read from the file: verify with json.load + pop + same dumps
    result["PAYLOAD_SHA256_EXCLUDING_THIS_FIELD"] = hashlib.sha256(
        json.dumps(canon, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    OUT.write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps({k: result[k] for k in ("R7_STATUS", "R7_BOUND_STATUS", "SHELL1_STATUS", "MAX_VALID_UPPER_BOUND",
                                             "GAP_VS_313263888", "CPU_SECONDS")}))
    print(json.dumps(result["ACCOUNTING"]["BY_KIND"]), json.dumps(checks))


# ---- proof record ---------------------------------------------------------------------------------------

PROVENANCE = {
    "PRIOR_R7_SESSION": "interrupted (Agent quota); no R7 file was ever written to TASK_ROOT; its scratch in a volatile"
                        " session directory was read (not executed for any result here) and is not persisted",
    "PRIOR_SCRATCH_SHA256": {"tb3.py": "41d65553854e7571a8346a9c4dbc19f6726452f9ebcf2d41c03d696b2f15deea",
                             "val3.py": "d74c4cfceda6ccb8105c325db92f0d158d9db7e2f28fcd28778c6e78b665ba64",
                             "c9blocks.json": "e34750d017f114176568c87b68d8c45db85ae30ee4b9d4d6b0b29d5121cd1244",
                             "rows69.json": "98af9999e8a5e125c0d4a289ee75f060ad85911917295de97fd7dfe3a09ecf38"},
    "THIS_IMPLEMENTATION": "independent rewrite of the narrow R7 extension from the derivation in PROOF; during"
                           " development its EG-off variant reproduced the prior candidate's T on all 69 profiles"
                           " and its EG-on variant equals the prior candidate with all options (dev cross-check);"
                           " C9_BLOCKS is the prior session's K13 - C9 triangle decomposition, re-verified here",
}

DEFINITIONS = {
    "CONFIG": "legal Shell-1 configuration: 20 tickets of 6 labels from 1..49, pairwise overlap <= 1, histogram"
              " P_A {1:1, 2:25, 3:23} or P_C {2:28, 3:20, 4:1} (sum C(d,2) = 94)",
    "GRAPH": "G: u ~ v iff tickets u, v share a label; overlap <= 1 gives every edge a unique label lab(uv);"
             " B_y = tickets holding y; the edges of label y form the clique on B_y",
    "CLASSES": "t_v = #trio labels (d = 3) on v; F = edges with a trio label, R = all other edges (pair-label or"
               " quad-label); deg_F(v) = 2 t_v, r_v = deg v - 2 t_v = deg_R(v), p_v = r_v - 3[v quad] = #pair-label"
               " edges at v",
    "CORE_Z": "C = {v : t_v >= 1}, Z = {v : t_v = 0}, nc = |C|, nz = |Z|, qC = #quad tickets in C. SCOPE: every quad"
              " ticket lies in C (checked on all 69 profiles; r7_bound fails closed otherwise)",
    "L": "L = pairs inside C that are not F-edges, ell_v = nc - 1 - 2 t_v (L-degree), |L| = C(nc,2) - 3*ntrip",
    "ASSIGNMENT": "v in C: j_v = #pair-label neighbours in C, qc_v = qC - 1 if v quad else 0, rC_v = j_v + qc_v"
                  " (R-neighbours in C), rZ_v = p_v - j_v (neighbours in Z). z in Z: k_z = #neighbours in C,"
                  " dint_z = r_z - k_z (neighbours in Z)",
    "TRUE_TRIANGLE": "three pairwise adjacent tickets with no label common to all three (R3 analyze: T_TRUE)",
}

FORMULA = {
    "PSI": "Psi(j,k) = FFF0 + W_R + A + min(B_Z, B_EDGE) + C_ZZ + D_ZZZ",
    "FFF0": "C(nc,3) - |L|(nc-2) + sum_C C(ell_v,2) - ntrip",
    "W_R": "(1/2) sum_C rC_v (nc - 2 ell_v)",
    "A": "sum_C C(rC_v,2) - C(qC,3)",
    "B_Z": "sum_Z C(k_z,2)",
    "B_EDGE": "sum_{theta>=1} min(EF(U_theta) + ER(U_theta), C(|U_theta|,2)), U_theta = {v in C : rZ_v >= theta},"
              " EF(U) = level_program(U, complement, t, quad, g_any(U)), ER(U) = floor(sum_U min(rC_v,|U|-1)/2)",
    "G_ANY": "g_any(U) = min(packing(|U|), ntrip, floor(t(U)/3))  (R6's prefix cap G(U) is NOT used here)",
    "C_ZZ": "sum_C min(C(s,2), max(0, e_Z - (sum of the m smallest dint) + C(m,2))), s = rZ_v, m = nz - s,"
            " e_Z = sum(dint)/2",
    "D_ZZZ": "C(nz,3) - (sum mu/2)(nz-2) + sum_Z C(mu_z,2), mu_z = nz - 1 - dint_z",
    "FEASIBLE": "max(0, p_v - nz) <= j_v <= min(p_v, ell_v - qc_v); max(0, r_z - nz + 1) <= k_z <= min(r_z, nc);"
                " (j_v) and (dint_z) pass Erdos-Gallai (incl. even sum); sum_C rZ = sum_Z k; Gale-Ryser on (rZ, k)",
    "T7": "floor(max Psi over FEASIBLE), enumerated as per-class multisets (class = equal (t,p,quad) in C, equal r in Z)",
    "UB_R7": "307923840 + 2800*W + 11872*T7 - 1400*Tstar;  UB = min(UB_R6, UB_R7);  prune iff UB <= 313263888",
}

PROOF = {
    "STARS_VS_TRUE": "Two edges of a triangle with the same label y share a vertex and their other ends lie in B_y,"
                     " so the third edge is also y. A triangle is therefore a star (inside one B_y, d_y >= 3: the"
                     " ntrip trio stars and, for P_C, the 4 quad stars) or has three pairwise distinct labels (true).",
    "PARTITION": "F-edges join two tickets that each carry a trio label, so both ends lie in C and Z-tickets meet"
                 " only R-edges. Each true triangle has 3, 2, 1 or 0 F-edges; with one F-edge its apex (the vertex"
                 " off the F-edge) lies in C or Z; with none it has 0..3 Z-vertices. The 8 classes FFF, FFR, FRR_C,"
                 " FRR_Z, RRR_CCC, RRR_CCZ, RRR_CZZ, RRR_ZZZ partition the true triangles: T_true is their sum and"
                 " no triangle is counted twice.",
    "FFF_EXACT": "Triangles of the F-graph on C = C(nc,3) - #(triples with >= 1 L-pair) and, by inclusion-exclusion"
                 " (a triple with k L-pairs gives k - C(k,2) + [k=3] = 1), #(triples with >= 1 L-pair) ="
                 " |L|(nc-2) - sum C(ell_v,2) + T_L, T_L = #triples of C with all three pairs in L. F-triangles are"
                 " the ntrip trio stars plus the true FFF triangles (STARS_VS_TRUE), so FFF = FFF0 - T_L.",
    "FFR_EXACT": "An FFR triangle has exactly one R-edge uw, inside C. Its third vertex x is F-adjacent to u and w;"
                 " among the nc-2 other core tickets, ell_u - 1 are L-partners of u and ell_w - 1 of w, so"
                 " #x = nc - ell_u - ell_w + lambda_L(uw), lambda_L(uw) = #x with xu, xw in L. The labels are"
                 " distinct (STARS_VS_TRUE). FFR = W_R + sum_{uw in R_CC} lambda_L(uw); W_R = sum_{uw}(nc - ell_u -"
                 " ell_w) = (1/2) sum_C rC_v (nc - 2 ell_v).",
    "A": "Cherries (v; u, w) with v, u, w in C and vu, vw in R number sum_C C(rC_v,2). If uw is F the triangle is"
         " FRR_C with apex v (vu, vw cannot share a label, else uw would carry it), one cherry each. If uw is R, the"
         " triple is an L-triple with 3 R-edges (a true RRR_CCC or one of the C(qC,3) quad stars inside C) and gives"
         " 3 cherries. If uw is a non-edge it is an L-triple with exactly 2 R-edges, 1 cherry. sum_{uw in R_CC}"
         " lambda_L(uw) = sum over L-triples of #R-edges, so sum lambda_L - T_L = sum over L-triples of (#R - 1)."
         " Hence sum_C C(rC_v,2) - C(qC,3) - (sum lambda_L - T_L + FRR_C + RRR_CCC) = #L-triples with no edge >= 0"
         " (checked as an equality on every test configuration). With FFF_EXACT and FFR_EXACT:"
         " FFF + FFR + FRR_C + RRR_CCC <= FFF0 + W_R + A.",
    "B": "FRR_Z and RRR_CCZ triangles are exactly the triangles {u, w, z} with u, w in C, z in Z (uz, wz are R; uw any"
         " edge). (i) Each gives one cherry at z with both ends in C: <= B_Z. (ii) Their number is sum over edges uw"
         " inside C of |N_Z(u) & N_Z(w)| <= sum_uw min(rZ_u, rZ_w) = sum_theta e(U_theta) (layer cake). e(U) ="
         " e_F(U) + e_R(U), e_R(U) <= ER(U) (v has <= min(rC_v, |U|-1) R-neighbours in U, each edge counted twice),"
         " e_F(U) <= EF(U) (ARBITRARY_SUBSET_LEVEL_PROGRAM) and e(U) <= C(|U|,2). So FRR_Z + RRR_CCZ <="
         " min(B_Z, B_EDGE).",
    "C": "An RRR_CZZ triangle has one core vertex v and its two Z-vertices are adjacent neighbours of v, so"
         " RRR_CZZ <= sum_C e(G[N_Z(v)]). For S = N_Z(v), |S| = s, m = nz - s: e(G[S]) <= C(s,2) and e(G[S]) ="
         " e_Z - (sum_{Z-S} dint - e(G[Z-S])) <= e_Z - (sum of the m smallest dint) + C(m,2).",
    "D": "Z-internal edges are pair-label edges (no quad ticket in Z), so RRR_ZZZ = #triangles of G[Z] ="
         " C(nz,3) - |M|(nz-2) + sum C(mu_z,2) - T_M <= D_ZZZ (M = non-edges inside Z, T_M >= 0).",
    "RELAXATION": "Summing: T_true <= Psi evaluated at the configuration's own (j, k), and Psi depends on the"
                  " configuration only through (j, k) and the profile. Every legal (j, k) is FEASIBLE: rC_v <= ell_v"
                  " (R-neighbours in C are L-partners), 0 <= rZ_v <= nz, 0 <= k_z <= min(r_z, nc), dint_z <= nz - 1;"
                  " the pair-label edges inside C form a simple graph with degrees j and G[Z] one with degrees dint"
                  " (Erdos-Gallai necessity incl. even sums); the C-Z edges form a simple bipartite graph with degrees"
                  " (rZ, k) (equal sums, Gale-Ryser necessity). Psi and the filters only depend on the multiset of"
                  " (t, p, quad, j) over C and of (r, k) over Z, so per-class multisets enumerate every legal (j, k)."
                  " T_true <= max Psi; 2*Psi is an integer (sum_C rC_v is even), so T_true <= floor(max Psi) = T7. An"
                  " empty FEASIBLE set would mean the profile has no legal configuration (never happens on the 69).",
    "ARBITRARY_SUBSET_LEVEL_PROGRAM": "For ANY ticket set U with complement D and T_i = #trio labels with exactly"
                                      " i members in U, every legal configuration satisfies: the identities"
                                      " t(U) = 3T3+2T2+T1, t(D) = 3T0+2T1+T2, e_F(U) = 3T3+T2, e_F(D) = 3T0+T1"
                                      " (a trio with i members in U has C(i,2) F-edges in U and C(3-i,2) in D);"
                                      " (a') T3 <= g_any(U): the trios inside U form a linear 3-graph on |U| points"
                                      " (two trios sharing two tickets would give overlap 2), so T3 <= D(|U|) <="
                                      " packing(|U|) (R3 PACKING_UPPER_BOUND), T3 <= ntrip and 3T3 <= t(U);"
                                      " (b) 3T3 <= sum_U min(t_v, floor(avail_U(v)/2)); (c) e_F(X) <="
                                      " floor(sum_X min(2t_v, avail_X(v))/2) for X in {U, D}. (b), (c) are R6's"
                                      " arguments verbatim: they never used that U is a prefix. level_program"
                                      " enumerates every integer (T0..T3) meeting these, so its maximum is >= e_F(U)"
                                      " (and it is infeasible only if no legal configuration exists). Only R6's (a)"
                                      " T3 <= G(U) relies on U being a degree-descending prefix (R3 KMAX_LEMMA); R7"
                                      " never passes G to a non-prefix set.",
    "UB": "R3: S3 = 2800*W + 11872*T_true - 1400*Tstar on every Shell-1 configuration (constants re-evaluated here,"
          " CONSTANTS_REEVALUATED); T_true <= T7 gives S3 <= 2800*W + 11872*T7 - 1400*Tstar; Bonferroni-3: union <="
          " S1 - S2 + S3 = UB_R7. UB_R6 stays valid, so UB = min(UB_R6, UB_R7). A profile with UB <= 313263888"
          " cannot hold a strict gain (equality would be a tie).",
    "NO_DOUBLE_COUNTING": "Each true triangle is in exactly one class (PARTITION) and each class is bounded once."
                          " A uses cherries centred in C with both ends in C, C_ZZ cherries centred in C with both"
                          " ends in Z, B_Z cherries centred in Z: disjoint cherry sets. No capacity is shared between"
                          " two terms: every term is an upper bound on a different class count, evaluated at the same"
                          " (j, k).",
    "INTEGER_DIRECTION": "Floors are applied only to quantities that upper-bound integers (EF, ER, cap(X), packing,"
                         " T7) or to exact even sums (e_Z, |M|, W_R enforced by the parity filters); max(0, .) and"
                         " min(., C(s,2)) only enlarge or keep valid caps.",
}

R6_INVARIANTS = {
    "IDENTITIES_T_U_T_D_E_F": "REMAIN TRUE for every partition U | D of the 20 tickets",
    "A_PREFIX_CAP_G_U": "PREFIX-ONLY (R3 KMAX_LEMMA along the degree-descending order); NOT generalized; replaced"
                        " by g_any(U) = min(packing(|U|), ntrip, floor(t(U)/3)), valid for every U",
    "B_IN3": "REMAINS TRUE for every U (partners of v inside U are distinct across v's trios)",
    "C_CAP_U_CAP_D": "REMAINS TRUE for every X (F-neighbours of v inside X are eligible members of X - v)",
    "LEVEL_PROGRAM_WITH_G_ANY": "valid upper bound on e_F(U) for arbitrary U; used only inside B_EDGE",
}

ASSUMPTIONS = [
    "Shell-1 := 20 tickets of 6 labels from 1..49, pairwise overlap <= 1, sum_y C(d_y,2) = 94 (histograms P_A, P_C).",
    "Objective = OFFICIAL_ANY_PRIZE union count; Bonferroni-3 upper bound S1 - S2 + S3. S1 - S2 = 307923840 and the"
    " S3 weights (PATH 2800, STAR 7000, TRIANGLE 20272) are re-evaluated here by the frozen constants.co_win DP and"
    " were independently verified on 2026-10-08 by four methods.",
    "D(k) <= packing(k) = Schonheim - [k = 5 mod 6] (R3 PROOF.PACKING_UPPER_BOUND, parity argument).",
    "Scope: every quad ticket has t >= 1 on the 69 profiles (checked); the bound fails closed otherwise.",
    "R1-R6 are inherited byte-identical: profile domain and W >= W0 survivor set (R3 certified DP), R3-R6 pruning"
    " (R6's 2193 NO_LEGAL_TRIO_SYSTEM exclusions independently re-proved 2026-10-09). R7 only re-evaluates R6's 69.",
    "Erdos-Gallai and Gale-Ryser are used only in their elementary necessary direction (double counting, proved in"
    " the docstrings). EG is not load-bearing: all 69 are pruned with EG off (ACCOUNTING.LOAD_BEARING.EG).",
]

SCOPE_CAVEATS = [
    "Shell-1 only: max pairwise overlap <= 1 and sum C(d,2) = 94. No claim about other shells or global K20"
    " optimality.",
    "Bonferroni-3 is an upper bound on the union count; a pruned profile cannot beat 313263888, but no exact union"
    " count of any Shell-1 portfolio was computed.",
]


if __name__ == "__main__":
    main()
