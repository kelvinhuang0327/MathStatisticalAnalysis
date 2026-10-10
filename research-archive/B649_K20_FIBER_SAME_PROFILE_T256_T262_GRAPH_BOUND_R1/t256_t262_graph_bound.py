"""B649 K20 Fiber cells 55555555555511111100 / T=256..262: bounded graph closure (R1).

Claim: no simple graph with degrees 11^12, 7^6, 6^2 has T in {256, ..., 262} triangles, so the
seven Fiber cells (profile 55555555555511111100, T=256..262) are empty. The written proof is
stored in result.json. It rests on an exact triangle identity in the missing-edge graphs F
(inside H) and R (inside L), an exhaustive Erdos-Gallai scan of their degree sequences, the
arm lemma of the T263..T268 result, and two equality-case lemmas (m = 1 and m = 12). Every
step is also checked mechanically. Pure standard library, single worker, no solver, no Fiber
state touched.

    nice -n 15 <python> -I -B <task-root>/t256_t262_graph_bound.py
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import hashlib  # noqa: E402
import itertools  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import random  # noqa: E402
import resource  # noqa: E402
import time  # noqa: E402
from collections import Counter  # noqa: E402
from math import comb  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any  # noqa: E402

TASK_ID = "B649_K20_FIBER_SAME_PROFILE_T256_T262_GRAPH_BOUND_R1"
TASK_ROOT = Path(__file__).resolve().parent
RESULT_PATH = TASK_ROOT / "result.json"
CPU_LIMIT_SECONDS = 100
REFERENCE_MAIN = "d079d4add8715a1034f2b7a0cd62e00cab59f656"
CANONICAL_COUNT = 313263888
PORTFOLIO_SHA256 = "eaed652900d101881b678a1515d2a366bff9de6723dbec2ec9c82fe0d0d7844c"
PREDECESSORS = {
    "T270": (
        "cd136425601d69c4cf1f437ea11a2c2bd25ff9d295e2cc2f670092aeb20176b8",
        "/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/.task-data/"
        "B649_K20_FIBER_INCUMBENT_T270_STRUCTURAL_EXACT_CLOSURE_R1/result.json",
    ),
    "T269": (
        "3bb366d7f53cf3ec922dc806932e28ec8780ae4f3c89bad2149716b171159180",
        "/Users/kelvin/.codex/worktrees/b649-k20-fiber-t269-structural-r1/MathStatisticalAnalysis/"
        ".task-data/B649_K20_FIBER_T269_STRUCTURAL_EXCLUSION_R1/result.json",
    ),
    "T263_T268": (
        "8ad5419f57ff23342a6503a1579631b133a5d7aa19a8026b63792f7480550e3e",
        "/Users/kelvin/.codex/worktrees/b649-k20-fiber-t263-t268-gap-r1/MathStatisticalAnalysis/"
        ".task-data/B649_K20_FIBER_SAME_PROFILE_T263_T268_GRAPH_GAP_R1/result.json",
    ),
}

PROFILE = "55555555555511111100"
CELLS = tuple(range(256, 263))
T_INCUMBENT = 270
T_CEILING = 255  # claimed: every graph with c > 0 has T <= 255
N_H, N_L = 12, 8
N = N_H + N_L
H = range(N_H)
L = range(N_H, N)
H_MASK = (1 << N_H) - 1
L_MASK = ((1 << N) - 1) ^ H_MASK
DEGREES = [6 + int(ch) for ch in PROFILE]  # overlap degree of a ticket = 6 + triple degree
DEG_SORTED = sorted(DEGREES)
H_DEG = 11
DELTA = {x: 7 - DEGREES[x] for x in L}  # 1 on the two degree-6 vertices, 0 on the degree-7 ones
Y6 = tuple(x for x in L if DELTA[x] == 1)
L_DEGS = (7, 6)
F_DEG_CAP = N_L  # d_F(u) = deg_L(u) <= |L|
W_EXPECTED = sum(comb(d, 2) for d in DEGREES)
O_BY_T = {t: W_EXPECTED - 3 * t for t in CELLS}
M_TABLE = tuple(range(1, 14))
B_EXPECTED = {1: 256, 2: 246, 3: 240, 4: 238, 5: 240, 6: 246, 7: 246, 8: 250, 9: 246, 10: 246, 11: 249, 12: 256, 13: 260}
SEED = 20261009
WALK_RESTARTS, WALK_STEPS = 120, 40
CLIMB_RESTARTS, CLIMB_SCRAMBLE, CLIMB_STEPS = 48, 50, 300


def popcount(x: int) -> int:
    return x.bit_count()


# --------------------------------------------------------------------------- graph kernel


def build(h_missing, hl_edges, l_missing) -> list[int]:
    """Adjacency bitmasks: H = K12 minus h_missing, L = K8 minus l_missing, plus hl_edges."""
    adj = [0] * N

    def add(u: int, v: int) -> None:
        adj[u] |= 1 << v
        adj[v] |= 1 << u

    hm = {frozenset(e) for e in h_missing}
    lm = {frozenset(e) for e in l_missing}
    for u, v in itertools.combinations(H, 2):
        if frozenset((u, v)) not in hm:
            add(u, v)
    for u, v in itertools.combinations(L, 2):
        if frozenset((u, v)) not in lm:
            add(u, v)
    for u, v in hl_edges:
        add(u, v)
    return adj


def edges_of(adj: list[int]) -> list[tuple[int, int]]:
    return [(u, v) for u in range(N) for v in range(u + 1, N) if adj[u] >> v & 1]


def degrees(adj: list[int]) -> list[int]:
    return [popcount(a) for a in adj]


def triangles(adj: list[int]) -> int:
    return sum(popcount(adj[u] & adj[v]) for u, v in edges_of(adj)) // 3


def triangles_brute(adj: list[int]) -> int:
    return sum(
        1 for a, b, c in itertools.combinations(range(N), 3) if adj[a] >> b & 1 and adj[a] >> c & 1 and adj[b] >> c & 1
    )


def arm_count(adj: list[int], u: int, v: int) -> int:
    """Open wedges having edge uv as an arm: deg u + deg v - 2 - 2 |N(u) & N(v)|."""
    return popcount(adj[u]) + popcount(adj[v]) - 2 - 2 * popcount(adj[u] & adj[v])


def hl_edge_count(adj: list[int]) -> int:
    return sum(popcount(adj[u] & L_MASK) for u in H)


def identity_terms(adj: list[int]) -> dict[str, int]:
    """Every term of the identity T = 270 - 20m + S_F + S_R - Y - Z, plus its structural facts."""
    f_nb = [0] * N
    r_nb = [0] * N
    f_edges: list[tuple[int, int]] = []
    r_edges: list[tuple[int, int]] = []
    for u, v in itertools.combinations(H, 2):
        if not adj[u] >> v & 1:
            f_edges.append((u, v))
            f_nb[u] |= 1 << v
            f_nb[v] |= 1 << u
    for x, y in itertools.combinations(L, 2):
        if not adj[x] >> y & 1:
            r_edges.append((x, y))
            r_nb[x] |= 1 << y
            r_nb[y] |= 1 << x
    m = len(f_edges)
    c = hl_edge_count(adj)
    d_f = [popcount(f_nb[u]) for u in H]
    d_r = {x: popcount(r_nb[x]) for x in L}
    h = {x: popcount(adj[x] & H_MASK) for x in L}
    assert c == 2 * m and len(r_edges) == m + 1  # parity, |R| = 28 - e(L) = m + 1
    assert all(d_f[u] == popcount(adj[u] & L_MASK) <= F_DEG_CAP for u in H)  # deg_L(u) = d_F(u) <= 8
    assert all(d_r[x] == h[x] + DELTA[x] for x in L)  # d_R(x) = deg_H(x) + delta_x
    assert all(d_r[y] >= 1 for y in Y6)
    t_f = sum(popcount(f_nb[u] & f_nb[v]) for u, v in f_edges) // 3
    t_r = sum(popcount(r_nb[x] & r_nb[y]) for x, y in r_edges) // 3
    z_fx = sum(popcount(adj[u] & adj[v] & L_MASK) for u, v in f_edges)  # sum_x e_F(N_H(x))
    z_ru = sum(popcount(adj[x] & adj[y] & H_MASK) for x, y in r_edges)  # sum_u e_R(N_L(u))
    s_f = sum(d * d for d in d_f)
    s_r = sum(d * d for d in d_r.values())
    y_term = sum(d_r[y] for y in Y6)
    z = t_f + z_fx + z_ru + t_r
    return {
        "M": m,
        "C": c,
        "S_F": s_f,
        "S_R": s_r,
        "Y": y_term,
        "T_F": t_f,
        "Z_FX": z_fx,
        "Z_RU": z_ru,
        "T_R": t_r,
        "Z": z,
        "T_FORMULA": T_INCUMBENT - 20 * m + s_f + s_r - y_term - z,
    }


# --------------------------------------------------------------------------- phase 1: arithmetic + arm lemma


def arm_lemma_min() -> int:
    """Smallest arm term of an H-L edge ux over every (deg x, k = |N(u) & N(x)| <= deg x - 1)."""
    return min((H_DEG - 1 - k) + (dx - 1 - k) for dx in L_DEGS for k in range(dx))


def m_max_for(o: int, arm: int) -> int:
    c_max = (2 * o) // arm
    return (c_max - c_max % 2) // 2  # c is even


def phase1() -> dict[str, Any]:
    assert DEG_SORTED == [6, 6] + [7] * 6 + [11] * 12
    assert sum(DEGREES) // 2 == 93 == 3 * 22 + 27
    assert W_EXPECTED == 816 == 12 * 55 + 6 * 21 + 2 * 15
    assert [O_BY_T[t] for t in CELLS] == [48, 45, 42, 39, 36, 33, 30]
    assert len(Y6) == 2 and sum(DELTA.values()) == 2
    arm = arm_lemma_min()
    assert arm == 4
    m_max = {t: m_max_for(O_BY_T[t], arm) for t in CELLS}
    assert [m_max[t] for t in CELLS] == [12, 11, 10, 9, 9, 8, 7]
    assert all(m_max[t] < 12 for t in CELLS if t != 256)  # m = 12 needs O >= 48, i.e. T = 256 only
    return {
        "W": W_EXPECTED,
        "O_BY_T": {str(t): o for t, o in O_BY_T.items()},
        "HL_ARM_TERM_LOWER_BOUND": arm,
        "C_MAX_EVEN_BY_T": {str(t): 2 * m_max[t] for t in CELLS},
        "M_MAX_BY_T": {str(t): m_max[t] for t in CELLS},
        "M_12_ADMISSIBLE_ONLY_AT": [t for t in CELLS if m_max[t] >= 12],
    }


# --------------------------------------------------------------------------- phase 2: degree-sequence scan


def partitions(total: int, max_part: int, max_len: int):
    if total == 0:
        yield ()
        return
    if max_len == 0:
        return
    for p in range(min(total, max_part), 0, -1):
        for rest in partitions(total - p, p, max_len - 1):
            yield (p, *rest)


def erdos_gallai(seq: tuple[int, ...], n: int) -> bool:
    s = list(seq) + [0] * (n - len(seq))
    if sum(s) % 2 or len(s) > n:
        return False
    return all(sum(s[:k]) <= k * (k - 1) + sum(min(d, k) for d in s[k:]) for k in range(1, n + 1))


def havel_hakimi(seq: tuple[int, ...]) -> bool:
    rem = sorted(seq, reverse=True)
    while rem and rem[0] > 0:
        d, rem = rem[0], rem[1:]
        if d > len(rem):
            return False
        rem = [x - 1 for x in rem[:d]] + rem[d:]
        if min(rem[:d], default=0) < 0:
            return False
        rem.sort(reverse=True)
    return True


def graphic_sequences(edges: int, n: int, cap: int) -> list[tuple[int, ...]]:
    """Positive parts of every graphic degree sequence with `edges` edges on n vertices, max <= cap."""
    out = []
    for p in partitions(2 * edges, min(cap, n - 1), n):
        eg = erdos_gallai(p, n)
        assert eg == havel_hakimi(p), p
        if eg:
            out.append(p)
    return out


def u_f(m: int, cap: int = F_DEG_CAP) -> tuple[int, tuple[int, ...]]:
    """max sum d^2 over graphic F (m edges, 12 vertices, d <= cap)."""
    return max((sum(d * d for d in p), p) for p in graphic_sequences(m, N_H, cap))


def v_r(e: int, two_y: bool = True) -> tuple[int, tuple[int, ...]]:
    """max over graphic R (e edges, 8 vertices) of sum d^2 minus the two smallest positive degrees
    (the largest value of S_R - d_R(y1) - d_R(y2) over placements with d_R(y_i) >= 1)."""
    return max((sum(d * d for d in p) - (p[-1] + p[-2] if two_y else 0), p) for p in graphic_sequences(e, N_L, N_L - 1))


def b_bound(m: int, cap: int = F_DEG_CAP, two_y: bool = True) -> int:
    return T_INCUMBENT - 20 * m + u_f(m, cap)[0] + v_r(m + 1, two_y)[0]


def crude_b_bound(m: int) -> int:
    """Edge-sum bound S <= e (e + 1) for both F and R (no vertex-count cap): too weak at m = 7."""
    return T_INCUMBENT - 20 * m + m * (m + 1) + (m + 1) * (m + 2) - 2


def phase2() -> dict[str, Any]:
    table: dict[str, Any] = {}
    for m in M_TABLE:
        uf, uf_seq = u_f(m)
        vr, vr_seq = v_r(m + 1)
        b = T_INCUMBENT - 20 * m + uf + vr
        assert b == B_EXPECTED[m], (m, b)
        table[str(m)] = {"U_F": uf, "U_F_ARGMAX": list(uf_seq), "V_R": vr, "V_R_ARGMAX": list(vr_seq), "B": b}
    assert max(B_EXPECTED[m] for m in range(2, 12)) == 250 < CELLS[0]
    # Small cases by hand: F = one edge / path; R = path P3 / star K1,3.
    assert u_f(1) == (2, (1, 1)) and v_r(2) == (4, (2, 1, 1)) and v_r(3) == (10, (3, 1, 1, 1))
    teeth = {
        # The cap d_F <= 8 is load-bearing: without it B(9) = 258 > 255.
        "B_WITHOUT_F_DEGREE_CAP_M9": b_bound(9, cap=N_H - 1),
        # The exact 8-vertex scan is load-bearing: the edge-sum bound gives 256 at m = 7.
        "CRUDE_EDGE_SUM_BOUND_M7": crude_b_bound(7),
        # The arm lemma is load-bearing: m = 13 alone would allow T up to 260.
        "B_M13_EXCLUDED_ONLY_BY_ARM_LEMMA": B_EXPECTED[13],
        # The -d_R(y1) - d_R(y2) term is load-bearing at m = 11 under the dropped-term variant? recorded.
        "B_WITHOUT_Y_TERM": {str(m): b_bound(m, two_y=False) for m in range(1, 13)},
    }
    assert teeth["B_WITHOUT_F_DEGREE_CAP_M9"] == 258 > T_CEILING
    assert teeth["CRUDE_EDGE_SUM_BOUND_M7"] == 256 > T_CEILING
    assert B_EXPECTED[13] > T_CEILING
    return {"B_TABLE": table, "TEETH": teeth}


# @@CONTINUE@@

# Continuation preserves every byte of the 11,919-byte predecessor draft.
# Its unused randomized-search constants and m=13 diagnostic are never run.
ORIGINAL_BYTES = 11919
ORIGINAL_SHA256 = "92ae4554a63bc7576af2454fd329c300a4ecb731d202bd04ef3e46a33a45e979"
CURRENT_REFERENCE_MAIN = "3f1ba09511f5879193c62c82d323b12776f2008e"
WORKTREE_HEAD = "d079d4add8715a1034f2b7a0cd62e00cab59f656"
WORKTREE_TREE = "0d511efeed51ca7b94f6dd302ee371f07fd4b940"
OWNER_CHAT = "01a12150-791d-70b1-a1b1-f871a2c13874"

PROOF = {
    "DEFINITIONS_AND_SIMULTANEOUS_CONSTRAINTS": (
        "G is a simple undirected graph with H of size 12 and L of size 8. "
        "F=K12-G[H], M=K8-G[L], and B=G[H,L]. Put a_h=deg_F(h), "
        "q_l=deg_M(l), delta_l=7-deg_G(l), b_l=deg_B(l). Delta is 1 "
        "at exactly the two degree-6 vertices and 0 elsewhere. Degree equations "
        "give deg_B(h)=a_h<=8 and b_l=q_l-delta_l>=0, with q_l<=7, "
        "b_l<=12 and q_l>=1 at both delta vertices. Summing the H equations "
        "gives c=2|F|=2m. Summing L gives 54=2|G[L]|+c, so |G[L]|=27-m "
        "and |M|=m+1. Thus sum a=sum b=2m and sum q=2m+2. All equations "
        "hold simultaneously in the same graph; B must be a binary incidence "
        "matrix with these row and column sums. Independent maxima below are "
        "only upper relaxations, never certificates of joint feasibility."
    ),
    "CLIQUE_MINUS_MISSING_EDGES": (
        "For any missing-edge graph Q on n vertices, each missing edge lies "
        "in n-2 triples. Two missing edges share a triple exactly when they "
        "share a vertex; there are A_Q=sum_v C(deg_Q(v),2) such pairs. Three "
        "missing edges share a triple exactly for a triangle of Q. No triple "
        "has more than three edges. Inclusion-exclusion therefore gives "
        "triangles(K_n-Q)=C(n,3)-(n-2)|Q|+A_Q-t_Q. Applying this to F "
        "and M gives T_H=220-10m+A_F-t_F and T_L=50-6m+A_M-t_M."
    ),
    "BOTH_CROSS_TRIANGLE_TYPES": (
        "For each l in L, its b_l neighbors in H supply C(b_l,2) pairs. "
        "Subtract the pairs in F: Z_FB=sum_{hh' in F}|N_B(h) intersect "
        "N_B(h')|. Thus C_HHL=sum_l C(b_l,2)-Z_FB. Likewise "
        "C_HLL=sum_h C(a_h,2)-Z_MB, where Z_MB=sum_{ll' in M}|N_B(l) "
        "intersect N_B(l')|. These count the two disjoint cross-triangle "
        "types exactly, including every incidence and internal adjacency."
    ),
    "EXACT_IDENTITY_DERIVATION": (
        "Let Y=q_y1+q_y2, S_F=sum a_h^2, S_M=sum q_l^2, "
        "Z=t_F+t_M+Z_FB+Z_MB. Since delta is 0 or 1, "
        "C(q-delta,2)=C(q,2)-delta*(q-1), so sum_l C(b_l,2)=A_M-Y+2. "
        "Adding all four triangle types yields "
        "T=270-16m+A_F+A_M-t_F-t_M+C_HHL+C_HLL "
        "=272-16m+2A_F+2A_M-Y-Z. Since 2A_F=S_F-2m and "
        "2A_M=S_M-2m-2, this is exactly T=270-20m+S_F+S_M-Y-Z. "
        "Every term of Z is nonnegative. This is an algebraic proof for "
        "every graph in the domain, independent of example checks. The "
        "packet's tentative formula with negative A_F,A_M and negative "
        "actual cross-triangle counts has incorrect signs and is replaced "
        "by the proved identities above."
    ),
    "ARM_BOUND_AND_EXHAUSTIVE_M_RANGE": (
        "W=sum C(deg_G(v),2)=816, and each triangle occupies three centered "
        "wedges, so O=816-3T. For an edge hl let k be its common-neighbor "
        "count. Its open-wedge arm count is 11+deg_G(l)-2-2k. "
        "Since k<=deg_G(l)-1, this is at least 4 for degree 7 and at least "
        "5 for degree 6. Each open wedge has two arms, so 4c<=2O, hence "
        "O>=4m. For T>=256, O<=48 and m<=12 (c<=24). For m>=13, "
        "T<=floor((816-52)/3)=254. Therefore the m=0..12 table together "
        "with this tail covers every graph, not just a sampled range."
    ),
    "DEGREE_SEQUENCE_CERTIFICATE_COMPLETENESS": (
        "Sort the positive degrees of F or M; pad with zero degrees to 12 "
        "or 8 vertices. For a graph with e edges this is a nonincreasing "
        "integer partition of 2e, with at most n parts and each part at "
        "most the degree cap. The partitions recursion enumerates every "
        "such partition exactly: choose the first positive part p, then "
        "recurse on total-p with next cap p and one fewer available part; "
        "induction on the remaining total proves completeness. For any k "
        "vertices of largest degrees, their degree sum is at most "
        "k(k-1)+sum_{i>k}min(d_i,k), by counting internal and external "
        "edges. Hence every graph passes all inequalities in erdos_gallai. "
        "Filtering by these necessary inequalities cannot remove a valid "
        "graph; sufficiency of the inequalities is not needed for the proof. "
        "The Havel-Hakimi comparison is only a consistency check. The scan "
        "maximizes S_F with 2m total and cap 8, and S_M-q_y1-q_y2 with "
        "2m+2 total and cap 7. Both delta vertices have positive q, so "
        "subtracting the two smallest positive parts safely upper-bounds "
        "the latter quantity for every placement. Thus "
        "T<=270-20m+U_F(m)+V_M(m+1), with no claim that separate "
        "maximizers share a feasible B. This is exhaustive bounded "
        "degree accounting justified by necessary conditions; it is not "
        "a full graph census, random test, or replacement for the identity proof."
    ),
    "M0": (
        "When m=0, B is empty, F is empty and M has one edge. The two "
        "delta vertices both have q>=1 and sum q=2, so this edge joins "
        "exactly those two vertices. Therefore T=C(12,3)+C(8,3)-6=270."
    ),
    "M1_EQUALITY_CONTRADICTION": (
        "The relaxed upper bound is 256: S_F=2 and S_M-Y<=4. If T=256, "
        "equality forces M degree sequence (2,1,1), both delta vertices "
        "on its leaves, and Z=0. (The only other two-edge graph is two "
        "disjoint edges, giving S_M-Y=2.) Let x be the path center. "
        "Then b_x=2 and all other L columns are zero. The two endpoints "
        "u,v of the sole F edge each have a=1, so B must contain ux,vx. "
        "Consequently Z_FB=1, contradicting Z=0. Thus T<=255 for m=1. "
        "The supplied m=1 graph certificate attains 255 and verifies "
        "all simultaneous degree and incidence constraints."
    ),
    "M12_EQUALITY_CONTRADICTION": (
        "The necessary-degree scan gives U_F(12)=108 and V_M(13)=118, "
        "so the relaxed upper bound is 256. T=256 would force both "
        "maxima and Z=0. The sole M degree sequence maximizing V_M is "
        "(7,7,2,2,2,2,2,2). In any simple graph with this sequence, the "
        "two degree-7 vertices are adjacent to all other seven vertices. "
        "Their edge with each of the six others forms a distinct triangle, "
        "so t_M>=6, contradicting Z=0. This uses mandatory adjacency, "
        "not failure to construct a graph. Independently, the sole F "
        "maximizer (8,5,2,2,2,2,1,1,1) requires an H vertex with all "
        "eight L neighbors, including both degree-6 vertices. At T=256 "
        "and m=12, 4c=2O=96 would require every cross arm to equal 4; "
        "each such degree-6 incidence has at least 5 arms, also a "
        "contradiction. Thus the maxima cannot simultaneously produce "
        "a valid equality case, and T<=255 for m=12."
    ),
    "CONCLUSION": (
        "For m=2..11 the certified relaxed upper bounds are respectively "
        "246,240,238,240,246,246,250,246,246,249. The two boundary "
        "arguments lower m=1 and m=12 from 256 to 255. The tail m>=13 "
        "is at most 254, and m=0 is exactly 270. Consequently every "
        "graph with degree sequence 11^12,7^6,6^2 has T=270 or T<=255. "
        "The non-270 ceiling 255 is sharp at graph level. Hence all "
        "T256..T262 cells of the specified profile are empty. A graph "
        "witness at 255 is not a ticket-portfolio realization or an "
        "improvement of the canonical winning count."
    ),
}


def check_graph(adj: list[int]) -> dict[str, int]:
    """Focused graph diagnostic; the universal identity is proved in PROOF."""
    assert len(adj) == N
    assert all(0 <= mask < (1 << N) for mask in adj)
    assert all(not (adj[u] >> u & 1) for u in range(N))
    assert all((adj[u] >> v & 1) == (adj[v] >> u & 1) for u in range(N) for v in range(N))
    assert degrees(adj) == DEGREES, "degree-domain violation"
    terms = identity_terms(adj)
    m = terms["M"]
    q = [7 - popcount(adj[x] & L_MASK) for x in L]
    a = [11 - popcount(adj[h] & H_MASK) for h in H]
    af = sum(comb(d, 2) for d in a)
    am = sum(comb(d, 2) for d in q)
    chhl = sum(comb(popcount(adj[x] & H_MASK), 2) for x in L) - terms["Z_FX"]
    chll = sum(comb(popcount(adj[h] & L_MASK), 2) for h in H) - terms["Z_RU"]
    th = 220 - 10 * m + af - terms["T_F"]
    tl = 50 - 6 * m + am - terms["T_R"]
    actual = triangles_brute(adj)
    assert actual == triangles(adj) == th + tl + chhl + chll == terms["T_FORMULA"]
    assert actual == 272 - 16 * m + 2 * af + 2 * am - terms["Y"] - terms["Z"]
    assert chhl >= 0 and chll >= 0
    terms.update({"T": actual, "A_F": af, "A_M": am, "T_H": th, "T_L": tl,
                  "C_HHL": chhl, "C_HLL": chll})
    return terms


def focused_certificate() -> dict[str, Any]:
    """Only the prescribed 0..12 bounded accounting; no predecessor execution."""
    arithmetic = phase1()
    table = {"0": {"M": 0, "C": 0, "PROVED_T": 270, "EXACT": True}}
    for m in range(1, 13):
        f_seqs = graphic_sequences(m, N_H, F_DEG_CAP)
        m_seqs = graphic_sequences(m + 1, N_L, N_L - 1)
        uf = max(sum(d * d for d in p) for p in f_seqs)
        vm = max(sum(d * d for d in p) - p[-1] - p[-2] for p in m_seqs)
        f_top = [list(p) for p in f_seqs if sum(d * d for d in p) == uf]
        m_top = [list(p) for p in m_seqs if sum(d * d for d in p) - p[-1] - p[-2] == vm]
        relaxed = 270 - 20 * m + uf + vm
        assert relaxed == B_EXPECTED[m]
        table[str(m)] = {"M": m, "C": 2 * m, "U_F": uf, "V_M": vm,
                         "RELAXED_BOUND": relaxed,
                         "PROVED_BOUND": 255 if m in (1, 12) else relaxed,
                         "F_SEQUENCE_COUNT": len(f_seqs), "M_SEQUENCE_COUNT": len(m_seqs),
                         "F_ARGMAX_SEQUENCES": f_top, "M_ARGMAX_SEQUENCES": m_top,
                         "JOINT_REALIZABILITY_CLAIMED": False}
    assert table["1"]["M_ARGMAX_SEQUENCES"] == [[2, 1, 1]]
    assert table["12"]["F_ARGMAX_SEQUENCES"] == [[8, 5, 2, 2, 2, 2, 1, 1, 1]]
    assert table["12"]["M_ARGMAX_SEQUENCES"] == [[7, 7, 2, 2, 2, 2, 2, 2]]
    assert max(table[str(m)]["PROVED_BOUND"] for m in range(1, 13)) == 255
    witness = build([(0, 1)], [(0, 12), (1, 12)], [(12, 18), (12, 19)])
    terms = check_graph(witness)
    assert terms["T"] == 255 and terms["M"] == 1 and terms["Z_FX"] == 1
    # A controlled invalid fixture establishes that domain validation rejects defects.
    bad = witness.copy()
    bad[0] ^= 1 << 2
    bad[2] ^= 1 << 0
    try:
        check_graph(bad)
    except AssertionError as error:
        assert str(error) == "degree-domain violation"
    else:
        raise AssertionError("domain validator accepted invalid degrees")
    predecessor_checks = {}
    for name, (expected, locator) in PREDECESSORS.items():
        p = Path(locator)
        observed = hashlib.sha256(p.read_bytes()).hexdigest()
        assert observed == expected, (name, observed)
        predecessor_checks[name] = {"PATH": str(p), "SHA256": observed, "EXECUTED": False}
    script = Path(__file__).read_bytes()
    assert hashlib.sha256(script[:ORIGINAL_BYTES]).hexdigest() == ORIGINAL_SHA256
    out: dict[str, Any] = {
        "TASK_ID": TASK_ID, "TASK_STATUS": "COMPLETE",
        "OWNER_STATUS": "OWNER_AUTHORIZED_CONTINUATION_AFTER_STABLE_NO_OBSERVED_OVERLAPPING_WRITER",
        "OWNERSHIP_EVIDENCE": {
            "CURRENT_WRITER_CHAT": OWNER_CHAT,
            "PREEXISTING_FILES": ["t256_t262_graph_bound.py"],
            "PREEXISTING_SCRIPT_BYTES": ORIGINAL_BYTES,
            "PREEXISTING_SCRIPT_SHA256": ORIGINAL_SHA256,
            "ORIGINAL_PREFIX_PRESERVED_BYTE_IDENTICALLY": True,
            "TASK_OWNER_LOCK_OR_CHECKPOINT_FOUND": False,
            "OVERLAPPING_PROCESS_OR_OPEN_FILE_FOUND": False,
            "SCRIPT_SHA_AND_MTIME_STABLE_ACROSS_OBSERVATIONS": True,
            "SEPARATE_INDEPENDENT_PROOF_CHAT": "01a12150-e659-7dd2-9b7e-809dac61a2bd",
            "SEPARATE_CHAT_SCOPE": "READ_ONLY; explicitly no writes to this worktree",
            "ORIGINAL_SESSION_TERMINATION_USED_AS_OWNERSHIP_PROOF": False,
        },
        "DOMAIN": {"VERTICES": N, "PROFILE": PROFILE, "DEGREES": DEGREES,
                   "W": W_EXPECTED, "TARGET_T": list(CELLS), "TARGET_M_RANGE": [0, 12]},
        "AUTHORITY": {"REPOSITORY": "kelvinhuang0327/MathStatisticalAnalysis",
                      "CURRENT_REFERENCE_MAIN": CURRENT_REFERENCE_MAIN,
                      "WORKTREE_HEAD": WORKTREE_HEAD, "WORKTREE_TREE": WORKTREE_TREE,
                      "K20_COUNT": CANONICAL_COUNT, "K20_PORTFOLIO_SHA256": PORTFOLIO_SHA256,
                      "COUNT_AND_PORTFOLIO_SOURCE": "frozen Owner packet; no portfolio recomputation"},
        "PREDECESSOR_CHECKS": predecessor_checks,
        "MATHEMATICAL_IDENTITY": "PROVED",
        "EXACT_TRIANGLE_IDENTITY": "T=270-20m+S_F+S_M-Y-t_F-t_M-Z_FB-Z_MB",
        "TENTATIVE_PACKET_IDENTITY": "INCORRECT_AS_WRITTEN; corrected by first-principles proof",
        "PROOF": PROOF, "ARITHMETIC": arithmetic, "BOUNDED_CASE_ACCOUNTING": table,
        "EQUALITY_M1": "PROVED", "EQUALITY_M12": "PROVED",
        "EQUALITY_INTERPRETATION": "The relaxed upper-bound equality T=256 is impossible in both cases",
        "STRONGEST_PROVED_TRIANGLE_BOUND": "T=270 (m=0) or T<=255 (m>=1); 255 attained by a legal graph",
        "OUTER_M_TAIL": {"M_MIN": 13, "T_UPPER_BOUND": 254, "METHOD": "O>=4m and O=816-3T"},
        "NEWLY_CLOSED_CELLS": [{"PROFILE": PROFILE, "T": t} for t in CELLS],
        "UNRESOLVED_CELLS": [], "TARGET_GRAPH_CERTIFICATE": None,
        "SHARPNESS_GRAPH_T255": {"H_MISSING_EDGES": [[0, 1]],
                                 "L_MISSING_EDGES": [[12, 18], [12, 19]],
                                 "HL_EDGES": [[0, 12], [1, 12]],
                                 "ADJACENCY_BITMASKS": witness, "DEGREES": degrees(witness),
                                 "IDENTITY_TERMS": terms},
        "TICKET_PORTFOLIO_REALIZABILITY_CLAIMED": False,
        "HIGHER_WINNING_COUNT_CLAIMED": False,
        "FOCUSED_TEST_STATUS": "PASS",
        "FOCUSED_CHECKS": ["integer arithmetic and arm bounds", "complete necessary-degree partition scan",
                           "both equality contradictions", "T255 graph degrees and four-way triangle count",
                           "controlled invalid-degree fixture rejected", "original draft prefix preserved",
                           "three predecessor SHA256 checks without execution"],
        "IMPLEMENTATION_ATTEMPTS": [
            {"ATTEMPT": 1, "ACTION": "read-only arithmetic diagnostic with CPU/RLIMIT_AS caps",
             "STATUS": "STOPPED_BEFORE_MODULE_IMPORT", "ERROR": "macOS RLIMIT_AS ValueError",
             "WRITES": [], "CPU_LIMIT_SECONDS": 30},
            {"ATTEMPT": 2, "ACTION": "read-only arithmetic diagnostic with CPU cap and observed peak RSS",
             "STATUS": "PASS", "CPU_SECONDS": "1.902413", "PEAK_RSS_BYTES": 21659648, "WRITES": []},
        ],
        "RESOURCE_CONTRACT": {"MAX_TOTAL_CPU_SECONDS": 120, "MAX_MEMORY_BYTES": 1073741824,
                              "WORKERS": 1, "NICE_MIN": 15, "CP_SAT": False,
                              "FULL_GRAPH_CENSUS": False, "MEMORY_CHECK": "observed peak RSS below cap"},
        "SCRIPT_PATH": str(Path(__file__).resolve()), "SCRIPT_SHA256": hashlib.sha256(script).hexdigest(),
        "RESULT_PATH": str(RESULT_PATH),
        "WORKTREE_STATUS": {"PATH": str(TASK_ROOT.parent.parent),
                            "TRACKED_WORKTREE_CLEAN": True, "TASK_FILES_GIT_IGNORED": True,
                            "FILES_CHANGED": ["t256_t262_graph_bound.py (append only)", "result.json (new)"],
                            "COMMIT_PUSH_PR_MERGE": "NOT RUN"},
        "FIBER_RUN1_MUTATION": "NONE", "RUNTIME_TRANSITION_OCCURRED": False,
        "REMAINING_TASK_REQUIRED_MODEL": "最強模型",
        "NEXT_TASK": "Only any substantive disagreement with the independent proof, or the next uncovered K20 family",
    }
    out.update({f"T{t}_STATUS": "PROVED_EMPTY" for t in CELLS})
    return out


def main() -> None:
    """Default reads only; --write-result exclusively creates the sole result."""
    assert sys.argv[1:] in ([], ["--write-result"]), "usage: script.py [--write-result]"
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 15, "run with nice -n 15"
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_LIMIT_SECONDS, CPU_LIMIT_SECONDS))
    result = focused_certificate()
    usage = resource.getrusage(resource.RUSAGE_SELF)
    cpu_us = int((usage.ru_utime + usage.ru_stime) * 1_000_000)
    # On this macOS host ru_maxrss is bytes. No unsupported memory limit is claimed.
    assert sys.platform == "darwin"
    assert usage.ru_maxrss < 1073741824
    assert cpu_us < 100_000_000
    result["CPU_SECONDS"] = f"{cpu_us // 1_000_000}.{cpu_us % 1_000_000:06d}"
    result["CPU_MICROSECONDS"] = cpu_us
    result["PEAK_RSS_BYTES"] = usage.ru_maxrss
    result["OBSERVED_NICE"] = os.getpriority(os.PRIO_PROCESS, 0)
    result["PRIOR_DIAGNOSTIC_CPU_SECONDS"] = "1.902413 (plus subsecond failed setup)"
    if sys.argv[1:] == ["--write-result"]:
        with RESULT_PATH.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
        saved = json.loads(RESULT_PATH.read_text())
        assert saved == result
        print("RESULT_SHA256=" + hashlib.sha256(RESULT_PATH.read_bytes()).hexdigest())
    else:
        assert RESULT_PATH.is_file(), "generate the result once with --write-result"
        saved = json.loads(RESULT_PATH.read_text())
        variable = {"CPU_SECONDS", "CPU_MICROSECONDS", "PEAK_RSS_BYTES", "OBSERVED_NICE"}
        assert {k: v for k, v in saved.items() if k not in variable} == {
            k: v for k, v in result.items() if k not in variable
        }, "saved certificate differs from focused reproduction"
    print("TASK_STATUS=COMPLETE MATHEMATICAL_IDENTITY=PROVED T256..T262=PROVED_EMPTY")
    print("EQUALITY_M1=PROVED EQUALITY_M12=PROVED T=270 or T<=255")
    print("FOCUSED_TEST_STATUS=PASS CPU_SECONDS=" + result["CPU_SECONDS"])
    print("PEAK_RSS_BYTES=" + str(usage.ru_maxrss) + " NICE=" + str(result["OBSERVED_NICE"]))


if __name__ == "__main__":
    main()
