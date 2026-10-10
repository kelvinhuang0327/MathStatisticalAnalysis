"""Formal Y/L block-isolation certificate T<=246 for the min-S2 owner 66666555555311100000.

Authority. The split-cap chase 2f709256 ends with the complete 4,647-row family maximum
313,404,008, owned only by d=(6^5,5^6,3,1^3,0^5). That row's cap 264 comes from R32 Route B;
its split relaxation gives 300 and cannot tighten it. The chase result is pinned by tree and
SHA-256, its ledger is replayed through the chase itself and the pinned ledger digest is
re-asserted. Only the owner row is replaced; no other closure certificate is adopted.

Model (r4, r5). 20 tickets carry six labels each. Of the 49 labels, 22 are triple supports
and 27 double supports, and no ticket pair lies in two supports. G joins tickets that share
a label. It is simple with 22*3+27=93 edges, and the triples are edge-disjoint triangles of
G. A ticket of triple degree d has 2d shadow neighbours and 6-d pair neighbours, all distinct.
T counts every triangle of G, the 22 support triangles included, as in Route B's 22..cap.

Write S6, S5, w, S1 and Z for the tickets of degree 6, 5, 3, 1 and 0. Their sizes are 5, 6,
1, 3 and 5, so the core K (positive degree) has 15 tickets. Put Y=S6+S5+w (12) and L=S1+Z (8).
The block of x in S1 is its only triple.

L1 (each S6 ticket lies in a block). v in S6 has 12 shadow neighbours, all in K, because
zeros lie in no triple. It therefore misses exactly 15-1-12=2 core tickets. v meets x in S1
iff v lies in x's block, so a v in no block would miss all three x's, and 3>2.

L2 (three distinct blocks with slots in Y). If two x's shared a block, the blocks would hold
at most 1+2=3 tickets outside S1 (none if all three share). L1 needs the 5 S6 tickets there.
A block holds no second x, whose only triple would then be that block. So each block is
{x,s,s'} with s,s' in K-S1=Y. The six slots (with multiplicity beta) cover S6, which leaves
one extra slot. So beta>=1 on S6, beta<=2 everywhere, and the extra slot is on an S6, an S5
or w.

L3 (shadow isolation). The 19 triples without an x lie in Y, and each block adds one Y edge
ss'. So Y has exactly 57+3=60 shadow edges and L has none: an x lies in one triple with two
Y tickets, and zeros lie in none. Exactly 6 shadow edges cross, the x-slot edges.

L4 (pair budget). The pair degrees are S6 0, S5 1, w 3, S1 5 and Z 6. Let p_Y, q and p_L
count pair edges inside Y, across, and inside L. Then 2p_Y+q=9, 2p_L+q=45 and
p_Y+q+p_L=27, so q is odd and p_Y<=4. G[Y] has 60+p_Y of its 66 pairs, which leaves
N=6-p_Y missing.

A crossing pair edge starts at an S5 ticket (a of them; each sends at most one) or at w (b<=3
of them), with a+b=q. The 3-b internal pairs of w go to distinct S5 tickets that keep their
label inside Y, so 3-b<=6-a. For l in L, pi_l=a_l+b_l counts its pair neighbours in Y:
a_l from distinct S5 tickets and b_l in {0,1} from w. Also pi_x<=5 and pi_z<=6.

L5 (triangles split by how many vertices they have in L).
  T0: triangles of K12 minus N edges. A missing edge lies in 10 of the 220 triangles, and two
      missing edges share at most one, so T0<=220-10N+C(N,2) by Bonferroni.
  T1: sum over l of e(G[N_Y(l)]). N_Y(x) is two slots plus pi_x pair neighbours, and N_Y(z)
      is pi_z pair neighbours. So T1<=sum_x C(2+pi_x,2)+sum_z C(pi_z,2).
  T2: sum over y in Y of e(G[N_L(y)]), with |N_L(y)|<=beta_y+6-d_y. The extra slot on an
      S6, an S5 or w gives at most 1+3, 1+3 or C(4,2). So T2<=6.
  T3: G[L] has only pair edges, with deg_L(x)=5-pi_x and deg_L(z)=6-pi_z. Its complement
      H_L in K8 has e(H_L)=28-p_L=(11+q)/2, h_x=2+pi_x and h_z=1+pi_z. The exact identity
      t(G[L])=C(8,3)-6e(H_L)+sum C(h,2)-t(H_L) gives
      T3<=23-3q+sum_x C(2+pi_x,2)+sum_z C(1+pi_z,2).

Enumeration. Every legal realization projects onto (a_l, b_l) for the eight labelled L tickets
under the L4 limits, and p_Y and q follow from the projection. The L5 bound depends only on the
projection. Exhaustive stdlib enumeration covers every labelled a in [0,6]^8 with sum<=6 and
every b in {0,1}^8 with sum<=3, so it covers every realization. Its maximum is 246, at p_Y=2,
q=5 and one x with pi_x=5; hence T<=246. Ablations show which limits carry weight. Without
the per-source limits a_l, b_l the maximum is 251. The w-internal limit 3-b<=6-a carries none.

Falsification, not proof. The recorded T=192 realization passes every lemma and every
component bound. So does each legal pair-support swap of it.

Route B and family. The pinned R32 envelope at cap 246 with S4 base 112 is re-evaluated at
every t in 22..246 and must be a prefix of the cap-264 envelope. Then exactly one ledger row
is replaced and the complete family maximum over all 4,647 rows and the cursor is recomputed.
No solver, portfolio search or outcome enumeration is run.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from itertools import combinations
from math import comb
from pathlib import Path
from time import process_time

from . import b649_k20_min_s2_route_b_current_owner_refinement_r32 as r32
from . import b649_k20_min_s2_split_cap_current_owner_chase_r1 as chase

split = chase.split
prior = chase.prior
TASK_ID = "B649_MIN_S2_TOP_OWNER_YL_CAP246_FORMAL_CERT_R1"
TASK_BRANCH = "codex/b649-min-s2-top-owner-yl-cap246-formal-cert-r1"
BASE_HEAD = "2f70925698cb28758fdf29a62bc5e91028c03a81"
BASE_TREE = "216bd91dee0afa58f8186a38aec52b1d47781ef8"
BASE_RESULT_SHA256 = "2269cc5e5e3bf08650fa711a240e7d088814e1bcd35d0cb9efcb01a91a2d67f3"
LEDGER_SHA256 = "2cf91665b86167e917f47779fdee3cb23b07b1d1b3d2491eae8b3ab42d9307a8"
LEDGER_ROWS = 4_647
TARGET = "66666555555311100000"
DEGREE_COUNTS = {6: 5, 5: 6, 3: 1, 1: 3, 0: 5}
FAMILY_BEFORE = 313_404_008
CAP_BEFORE = 264
CAP = 246
S4_BASE = 112
INCUMBENT = chase.INCUMBENT
Y_SIZE, L_SIZE = 12, 8
Y_SHADOW = 60
Y_PAIR_INCIDENCE, L_PAIR_INCIDENCE = 9, 45
S5_COUNT, W_PAIRS, X_PAIRS, Z_PAIRS = 6, 3, 5, 6
X_COUNT, Z_COUNT = 3, 5
ROOT = chase.ROOT
RESULT_FILENAME = "b649-min-s2-top-owner-yl-cap246-formal-cert-r1-result.json"
RESULT_PATH = ROOT / prior.RESULT_DIRECTORY / RESULT_FILENAME
CERT_LOCATOR = f"{RESULT_FILENAME}:CERTIFIED_T_CAP"
Supports = chase.Supports
integer = chase.integer
object_row = chase.object_row
rows = chase.rows
text = chase.text


def pinned_authority() -> dict[str, object]:
    """The 2f709256 chase result at its exact tree and digest, ending at the target owner."""

    if chase.git("rev-parse", f"{BASE_HEAD}^{{tree}}").decode().strip() != BASE_TREE:
        raise AssertionError("base tree mismatch")
    blob = chase.git("show", f"{BASE_HEAD}:{prior.RESULT_DIRECTORY}/{chase.RESULT_FILENAME}")
    if hashlib.sha256(blob).hexdigest() != BASE_RESULT_SHA256:
        raise AssertionError("split-cap chase authority digest mismatch")
    base = object_row(json.loads(blob))
    expected: dict[str, object] = {
        "TASK_ID": chase.TASK_ID,
        "FINAL_COMPLETE_FAMILY_UB": FAMILY_BEFORE,
        "FINAL_OWNER_IDS": [TARGET],
        "FINAL_RESOLVED_ROW_COUNT": LEDGER_ROWS,
        "FINAL_RESOLVED_ROWS_SHA256": LEDGER_SHA256,
        "CURRENT_INCUMBENT": INCUMBENT,
    }
    for key, value in expected.items():
        if base.get(key) != value:
            raise AssertionError(f"split-cap chase authority mismatch: {key}")
    cert = target_certificate(base)
    if (cert["TRIANGLE_CAP"], cert["ALL_T_MAX_BOUND"], cert["S4_BASE"]) != (
        CAP_BEFORE,
        FAMILY_BEFORE,
        S4_BASE,
    ):
        raise AssertionError("target row authority changed")
    return base


def target_certificate(base: Mapping[str, object]) -> dict[str, object]:
    certs = [object_row(c) for c in rows(base["CERTIFICATES"])]
    found = [c for c in certs if c["PROFILE_ID"] == TARGET]
    if len(found) != 1 or found[0]["STATUS"] != chase.NOT_TIGHTENED:
        raise AssertionError("target is not the single untightened chase stopper")
    return found[0]


def module_provenance(inherited: Mapping[str, str]) -> dict[str, str]:
    """The chase, split and R32 sources equal their 2f709256 blobs, byte for byte."""

    out = dict(inherited)
    for module in (chase, split, r32):
        if module.__file__ is None:
            raise AssertionError("reused module has no source")
        path = Path(module.__file__).resolve()
        if not path.is_relative_to(ROOT):
            raise AssertionError(f"reused module loaded outside this tree: {path}")
        relative = path.relative_to(ROOT).as_posix()
        committed = chase.git("show", f"{BASE_HEAD}:{relative}")
        if path.read_bytes() != committed:
            raise AssertionError(f"reused source changed: {relative}")
        digest = hashlib.sha256(committed).hexdigest()
        if out.setdefault(relative, digest) != digest:
            raise AssertionError(f"reused source digest disagrees: {relative}")
    return dict(sorted(out.items()))


def lemma_premises() -> dict[str, object]:
    """Every count L1-L4 consume, derived from the profile and the 22/27 support model."""

    p = split.profile_values(TARGET)
    n = Counter(p)
    if dict(n) != DEGREE_COUNTS:
        raise AssertionError("target degree multiset changed")
    triples, pair_incidence = sum(p) // 3, sum(6 - d for d in p)
    if (triples, pair_incidence // 2, 3 * triples + pair_incidence // 2) != (22, 27, 93):
        raise AssertionError("profile is not a 22-triple, 27-pair, 93-edge realization shape")
    core = 20 - n[0]
    missed = core - 1 - 2 * 6
    shared_slots = max(1 + 2 * (n[1] - 2), 0)
    if not (missed < n[1] and shared_slots < n[6] <= 2 * n[1]):
        raise AssertionError("L1/L2 premise fails")
    y = [d for d in p if d >= 3]
    y_triples = triples - n[1]
    y_shadow = 3 * y_triples + n[1]
    if (
        (len(y), 20 - len(y), core - n[1], n[1] + n[0]) != (Y_SIZE, L_SIZE, Y_SIZE, L_SIZE)
        or sum(y) != 3 * y_triples + 2 * n[1]
        or y_shadow != Y_SHADOW
    ):
        raise AssertionError("L3 shadow count fails")
    y_pairs = sum(6 - d for d in y)
    l_pairs = pair_incidence - y_pairs
    if (y_pairs, l_pairs) != (Y_PAIR_INCIDENCE, L_PAIR_INCIDENCE):
        raise AssertionError("L4 pair incidence fails")
    t2, patterns = t2_cap()
    return {
        "DEGREE_COUNTS": {str(d): c for d, c in sorted(n.items(), reverse=True)},
        "TRIPLE_SUPPORTS": triples,
        "DOUBLE_SUPPORTS": pair_incidence // 2,
        "GRAPH_EDGES": 3 * triples + pair_incidence // 2,
        "CORE_COUNT": core,
        "L1_CORE_TICKETS_MISSED_BY_S6": missed,
        "L1_S1_COUNT": n[1],
        "L2_SLOTS_IF_TWO_X_SHARE_A_BLOCK": shared_slots,
        "L2_SLOTS": 2 * n[1],
        "L2_EXTRA_SLOTS": 2 * n[1] - n[6],
        "Y_SIZE": Y_SIZE,
        "L_SIZE": L_SIZE,
        "L3_TRIPLES_INSIDE_Y": y_triples,
        "L3_Y_SHADOW_EDGES": y_shadow,
        "L3_L_SHADOW_EDGES": 0,
        "L3_CROSSING_SHADOW_EDGES": 2 * n[1],
        "L4_Y_PAIR_INCIDENCE": y_pairs,
        "L4_L_PAIR_INCIDENCE": l_pairs,
        "L5_T2_CAP": t2,
        "L5_T2_BY_EXTRA_SLOT": patterns,
    }


def t2_cap() -> tuple[int, dict[str, int]]:
    """Max of sum_y C(beta_y+6-d_y, 2) over the three places the extra slot can sit."""

    degrees = (6,) * 5 + (5,) * 6 + (3,)
    out: dict[str, int] = {}
    for name, holder in (("S6", 0), ("S5", 5), ("W", 11)):
        beta = [1] * 5 + [0] * 7
        beta[holder] += 1
        out[name] = sum(comb(b + 6 - d, 2) for b, d in zip(beta, degrees, strict=True))
    return max(out.values()), out


T2_CAP = 6


def component_bounds(p_y: int, pi: Sequence[int]) -> tuple[int, int, int, int]:
    """L5 upper bounds on T0..T3; pi lists the three x tickets, then the five zeros."""

    if len(pi) != L_SIZE or not 0 <= p_y <= 4:
        raise ValueError("projection outside the L4 domain")
    q, missing = Y_PAIR_INCIDENCE - 2 * p_y, comb(Y_SIZE, 2) - Y_SHADOW - p_y
    xs, zs = pi[:X_COUNT], pi[X_COUNT:]
    if sum(pi) != q or any(v > X_PAIRS for v in xs) or any(v > Z_PAIRS for v in zs):
        raise ValueError("projection violates the pair budget")
    t0 = comb(Y_SIZE, 3) - (Y_SIZE - 2) * missing + comb(missing, 2)
    t1 = sum(comb(2 + v, 2) for v in xs) + sum(comb(v, 2) for v in zs)
    p_l = (L_PAIR_INCIDENCE - q) // 2
    h = [L_SIZE - 1 - (X_PAIRS - v) for v in xs] + [L_SIZE - 1 - (Z_PAIRS - v) for v in zs]
    t3 = comb(L_SIZE, 3) - (L_SIZE - 2) * (comb(L_SIZE, 2) - p_l) + sum(comb(v, 2) for v in h)
    return t0, t1, T2_CAP, t3


def compositions(total: int, parts: int) -> Iterator[tuple[int, ...]]:
    if parts == 1:
        yield (total,)
        return
    for head in range(total + 1):
        for tail in compositions(total - head, parts - 1):
            yield (head, *tail)


@dataclass(frozen=True)
class Projection:
    """S5 edges a_l and w edges b_l into each L ticket (x0, x1, x2, z0..z4)."""

    a: tuple[int, ...]
    b: tuple[int, ...]

    @property
    def pi(self) -> tuple[int, ...]:
        return tuple(u + v for u, v in zip(self.a, self.b, strict=True))

    @property
    def p_y(self) -> int:
        return (Y_PAIR_INCIDENCE - sum(self.a) - sum(self.b)) // 2


def feasible(a: Sequence[int], b: Sequence[int], *, w_internal: bool = True) -> bool:
    """Every L4 limit on one labelled projection."""

    sa, sb = sum(a), sum(b)
    pi = [u + v for u, v in zip(a, b, strict=True)]
    return (
        len(a) == len(b) == L_SIZE
        and min(a) >= 0
        and set(b) <= {0, 1}
        and sa <= S5_COUNT
        and sb <= W_PAIRS
        and (Y_PAIR_INCIDENCE - sa - sb) % 2 == 0
        and (not w_internal or W_PAIRS - sb <= S5_COUNT - sa)
        and all(v <= X_PAIRS for v in pi[:X_COUNT])
        and all(v <= Z_PAIRS for v in pi[X_COUNT:])
    )


def projections(*, w_internal: bool = True) -> Iterator[Projection]:
    """All labelled a in [0,6]^8 with sum<=6 and b in {0,1}^8 with sum<=3 meeting L4."""

    for total in range(S5_COUNT + 1):
        for a in compositions(total, L_SIZE):
            for size in range(W_PAIRS + 1):
                for chosen in combinations(range(L_SIZE), size):
                    b = tuple(int(i in chosen) for i in range(L_SIZE))
                    if feasible(a, b, w_internal=w_internal):
                        yield Projection(a, b)


def relaxation(*, w_internal: bool = True) -> dict[str, object]:
    """Exhaustive maximum of T0+T1+T2+T3 bounds over every feasible projection."""

    best, count, per_p_y = -1, 0, dict[int, int]()
    argmax: list[Projection] = []
    for proj in projections(w_internal=w_internal):
        count += 1
        total = sum(component_bounds(proj.p_y, proj.pi))
        per_p_y[proj.p_y] = max(per_p_y.get(proj.p_y, -1), total)
        if total > best:
            best, argmax = total, [proj]
        elif total == best:
            argmax.append(proj)
    return {
        "PROJECTION_COUNT": count,
        "MAXIMUM": best,
        "MAXIMUM_BY_P_Y": {str(k): v for k, v in sorted(per_p_y.items())},
        "ARGMAX": [
            {
                "A": list(p.a),
                "B": list(p.b),
                "P_Y": p.p_y,
                "Q": sum(p.pi),
                "PI": list(p.pi),
                "COMPONENT_BOUNDS": list(component_bounds(p.p_y, p.pi)),
            }
            for p in argmax
        ],
    }


def unlimited_source_maximum() -> int:
    """Ablation: drop the per-source limits a_l, b_l and keep only sum(pi)=q, pi_x<=5, pi_z<=6."""

    best = -1
    for p_y in range(5):
        for pi in compositions(Y_PAIR_INCIDENCE - 2 * p_y, L_SIZE):
            if all(v <= X_PAIRS for v in pi[:X_COUNT]) and all(v <= Z_PAIRS for v in pi[X_COUNT:]):
                best = max(best, sum(component_bounds(p_y, pi)))
    return best


def triangles(edges: set[tuple[int, int]], vertices: Sequence[int]) -> list[tuple[int, ...]]:
    return [
        t for t in combinations(sorted(vertices), 3) if all(e in edges for e in combinations(t, 2))
    ]


def audit(triples: Supports, pairs: Supports) -> dict[str, object]:
    """Check one legal realization of the target against L1-L5, component by component."""

    seen = split.analyze_realization(triples, pairs)
    if seen["PROFILE_ID"] != TARGET:
        raise ValueError("realization is not the target profile")
    d = [sum(v in t for t in triples) for v in range(20)]
    s6, s5, w = ({v for v in range(20) if d[v] == k} for k in (6, 5, 3))
    s1, zeros = sorted(v for v in range(20) if d[v] == 1), sorted(v for v in range(20) if not d[v])
    y, low = s6 | s5 | w, [*s1, *zeros]
    blocks = [next(t for t in triples if x in t) for x in s1]
    slots = [v for t in blocks for v in t if v not in s1]
    if not all(any(v in t for t in blocks) for v in s6):
        raise AssertionError("L1 fails: an S6 ticket lies in no block")
    if len(set(blocks)) != X_COUNT or any(len(set(t) & set(s1)) != 1 for t in blocks):
        raise AssertionError("L2 fails: blocks are not three distinct single-x triples")
    if not set(slots) <= y or len(slots) != 2 * X_COUNT or not s6 <= set(slots):
        raise AssertionError("L2 fails: slots leave Y or miss S6")
    beta = Counter(slots)
    shadow = split.edges_of(triples)
    pair_edges = split.edges_of(pairs)
    edges = shadow | pair_edges
    in_y = {e for e in edges if set(e) <= y}
    crossing_shadow = {e for e in shadow if len(set(e) & y) == 1}
    slot_edges = {
        tuple(sorted((x, v))) for x, t in zip(s1, blocks, strict=True) for v in t if v != x
    }
    if (
        len(shadow & in_y) != Y_SHADOW
        or any(set(e) <= set(low) for e in shadow)
        or crossing_shadow != slot_edges
    ):
        raise AssertionError("L3 fails")
    p_y = len(pair_edges & in_y)
    p_l = len({e for e in pair_edges if set(e) <= set(low)})
    q = len(pair_edges) - p_y - p_l
    a = tuple(sum(1 for u in s5 if tuple(sorted((u, v))) in pair_edges) for v in low)
    b = tuple(sum(1 for u in w if tuple(sorted((u, v))) in pair_edges) for v in low)
    proj = Projection(a, b)
    if (
        (2 * p_y + q, 2 * p_l + q) != (Y_PAIR_INCIDENCE, L_PAIR_INCIDENCE)
        or not feasible(a, b)
        or proj.p_y != p_y
        or sum(proj.pi) != q
    ):
        raise AssertionError("L4 fails")
    counts = [0, 0, 0, 0]
    for t in triangles(edges, range(20)):
        counts[len(set(t) & set(low))] += 1
    h_edges = set(combinations(low, 2)) - edges
    h = [sum(v in e for e in h_edges) for v in low]
    identity = comb(L_SIZE, 3) - (L_SIZE - 2) * len(h_edges) + sum(comb(v, 2) for v in h)
    t2_local = sum(comb(beta[v] + 6 - d[v], 2) for v in y)
    caps = component_bounds(p_y, proj.pi)
    if (
        sum(counts) != seen["TRIANGLES"]
        or counts[3] != identity - len(triangles(h_edges, low))
        or counts[2] > t2_local
        or t2_local > T2_CAP
        or any(c > cap for c, cap in zip(counts, caps, strict=True))
        or sum(caps) > CAP
    ):
        raise AssertionError("L5 fails")
    return {
        "PROFILE_ID": TARGET,
        "TRIANGLES": seen["TRIANGLES"],
        "SPLIT_T0_T1_T2_T3": counts,
        "COMPONENT_BOUNDS": list(caps),
        "PROJECTION_BOUND": sum(caps),
        "T2_SLOT_BOUND": t2_local,
        "T3_COMPLEMENT_TRIANGLES": len(triangles(h_edges, low)),
        "BLOCKS": [list(t) for t in blocks],
        "SLOT_MULTIPLICITY": {str(v): c for v, c in sorted(beta.items())},
        "P_Y": p_y,
        "Q": q,
        "P_L": p_l,
        "A": list(a),
        "B": list(b),
        "PI": list(proj.pi),
        "STATUS": "PASS",
    }


def pair_swaps(triples: Supports, pairs: Supports) -> Iterator[Supports]:
    """Every pair-support swap uv,st -> us,vt or ut,vs that keeps G simple."""

    used = split.edges_of((*triples, *pairs))
    for i, j in combinations(range(len(pairs)), 2):
        (u, v), (s, t) = pairs[i], pairs[j]
        if len({u, v, s, t}) < 4:
            continue
        for e, f in (((u, s), (v, t)), ((u, t), (v, s))):
            e2, f2 = tuple(sorted(e)), tuple(sorted(f))
            if e2 not in used and f2 not in used:
                rest = [pairs[k] for k in range(len(pairs)) if k not in (i, j)]
                yield tuple(sorted((*rest, e2, f2)))


def swap_neighbourhood(triples: Supports, pairs: Supports) -> dict[str, object]:
    """Falsification only: audit every legal one-swap neighbour of the recorded realization."""

    audits = [audit(triples, nxt) for nxt in pair_swaps(triples, pairs)]
    return {
        "LEGAL_NEIGHBOURS": len(audits),
        "MAX_TRIANGLES": max(integer(r["TRIANGLES"]) for r in audits),
        "MAX_PROJECTION_BOUND": max(integer(r["PROJECTION_BOUND"]) for r in audits),
        "STATUS": "PASS_EVERY_NEIGHBOUR_NOT_A_PROOF",
    }


def route_b(previous: Mapping[str, object]) -> dict[str, object]:
    """R32 Route B at cap 246, cross-checked and a prefix of the pinned cap-264 envelope."""

    p = split.profile_values(TARGET)
    terms = r32.route_b_envelope(p, CAP, S4_BASE)
    old = r32.route_b_envelope(p, CAP_BEFORE, S4_BASE)
    if (
        terms != split.route_b_terms(p, CAP, S4_BASE)
        or terms != old[: len(terms)]
        or [list(t) for t in old] != rows(previous["ALL_T_TERMS"])
        or max(t[1] for t in old) != FAMILY_BEFORE
    ):
        raise AssertionError("Route-B envelope disagrees with the pinned formula")
    best = max(terms, key=lambda term: (term[1], term[0]))
    return {
        "TRIANGLE_CAP": CAP,
        "S4_BASE": S4_BASE,
        "TERM_COUNT": len(terms),
        "ALL_T_TERMS": [list(t) for t in terms],
        "ARGMAX_TRIANGLES": best[0],
        "ALL_T_MAX_BOUND": best[1],
        "BELOW_INCUMBENT": best[1] < INCUMBENT,
        "ALL_T_STATUS": "PASS_R32_SPLIT_AND_EXACT_RATIONAL",
    }


def replayed_ledger(auth: chase.Authority, base: Mapping[str, object]) -> dict[str, chase.Row]:
    """Re-run the pinned chase on its replayed ledger and match the sealed end state."""

    outcome = chase.chase(auth.ledger, process_time() + chase.CPU_SECONDS)
    family = chase.final_family(outcome.ledger, outcome)
    if (
        family["FINAL_RESOLVED_ROWS_SHA256"] != LEDGER_SHA256
        or family["FINAL_RESOLVED_ROW_COUNT"] != LEDGER_ROWS
        or family["FINAL_COMPLETE_FAMILY_UB"] != FAMILY_BEFORE
        or outcome.stop != base["STOP"]
        or json.loads(json.dumps(outcome.certificates)) != base["CERTIFICATES"]
    ):
        raise AssertionError("replayed ledger differs from the pinned chase end state")
    return outcome.ledger


def single_row_update(ledger: Mapping[str, chase.Row], bound: int) -> dict[str, object]:
    """Replace only the target row, then take the complete maximum by an independent sort."""

    if len(ledger) != LEDGER_ROWS or ledger[TARGET].bound != FAMILY_BEFORE:
        raise AssertionError("ledger is not the pinned 4,647-row state")
    after = dict(ledger)
    after[TARGET] = replace(ledger[TARGET], bound=bound, cap=CAP, source=CERT_LOCATOR)
    changed = [pid for pid in ledger if ledger[pid] != after[pid]]
    terms = [*((r.bound, pid) for pid, r in after.items()), (prior.CURSOR_BOUND, prior.CURSOR_ID)]
    family = max(t for t, _ in terms)
    owners = sorted((pid for t, pid in terms if t == family), reverse=True)
    reused, reused_owners = chase.family_state(after)
    before, before_owners = chase.family_state(ledger)
    if (
        changed != [TARGET]
        or (reused, sorted(reused_owners, reverse=True)) != (family, owners)
        or (before, before_owners) != (FAMILY_BEFORE, [TARGET])
        or not INCUMBENT <= family < FAMILY_BEFORE
    ):
        raise AssertionError("single-row family recomputation disagrees")
    owner_rows = {pid: after[pid] for pid in owners if pid in after}
    return {
        "FAMILY_BOUND_BEFORE": before,
        "FAMILY_OWNERS_BEFORE": before_owners,
        "FAMILY_BOUND_AFTER_SINGLE_ROW_UPDATE": family,
        "FAMILY_OWNERS_AFTER": owners,
        "FAMILY_OWNER_AFTER_CAPS": {pid: r.cap for pid, r in owner_rows.items()},
        "FAMILY_BOUND_DELTA": family - before,
        "NEXT_COMPETING_BOUND_AFTER": max(t for t, pid in terms if pid not in owners),
        "ROWS_CHANGED": changed,
        "ROWS_ABOVE_INCUMBENT_BEFORE": sum(r.bound > INCUMBENT for r in ledger.values()),
        "ROWS_ABOVE_INCUMBENT_AFTER": sum(r.bound > INCUMBENT for r in after.values()),
        "REMAINING_GAP_AFTER": family - INCUMBENT,
        "OTHER_CLOSURE_CERTIFICATES_ADOPTED": [],
    }


def compute_result(authority: chase.Authority | None = None) -> dict[str, object]:
    base = pinned_authority()
    auth = chase.load_authority() if authority is None else authority
    provenance = module_provenance(auth.provenance)
    premises = lemma_premises()
    if premises["L5_T2_CAP"] != T2_CAP:
        raise AssertionError("T2 slot-pattern cap changed")
    relaxed = relaxation()
    if relaxed["MAXIMUM"] != CAP:
        raise AssertionError("relaxation maximum does not support T<=246")
    ledger = replayed_ledger(auth, base)
    realization = ledger[TARGET].realization
    if realization is None:
        raise AssertionError("no recorded realization of the target")
    witness = audit(*realization)
    previous = target_certificate(base)
    envelope = route_b(previous)
    bound = integer(envelope["ALL_T_MAX_BOUND"])
    family = single_row_update(ledger, bound)
    sts = object_row(object_row(base["WITNESS_SOUNDNESS"])["STS13_WITNESS"])
    owners = rows(family["FAMILY_OWNERS_AFTER"])
    realized = owners == [sts["PROFILE_ID"]] and sts["TRIANGLES"] == sts["LEDGER_TRIANGLE_CAP"]
    if not realized or family["FAMILY_BOUND_AFTER_SINGLE_ROW_UPDATE"] != sts["LEDGER_BOUND"]:
        raise AssertionError("new owner is not the realized-cap STS13 row")
    return {
        "TASK_ID": TASK_ID,
        "TASK_BRANCH": TASK_BRANCH,
        "TASK_STATUS": "COMPLETE_PENDING_FRESH_JUDGE",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_RESULT": chase.RESULT_FILENAME,
        "BASE_RESULT_SHA256": BASE_RESULT_SHA256,
        "LEDGER_SHA256": LEDGER_SHA256,
        "LEDGER_ROWS": LEDGER_ROWS,
        "PROOF": __doc__,
        "MODULE_PROVENANCE": provenance,
        "TARGET_PROFILE": TARGET,
        "LEMMA_PREMISES": premises,
        "RELAXATION": relaxed,
        "ABLATIONS": {
            "DROP_W_INTERNAL_PARTNER_LIMIT": relaxation(w_internal=False)["MAXIMUM"],
            "DROP_PER_SOURCE_LIMITS": unlimited_source_maximum(),
        },
        "COMPLETE_ENUMERATION": "PASS",
        "THEOREM_STATUS": "PROVEN",
        "CERTIFIED_T_CAP": CAP,
        "WITNESS_AUDIT": witness,
        "SWAP_NEIGHBOURHOOD": swap_neighbourhood(*realization),
        "PROFILE_BOUND_BEFORE": FAMILY_BEFORE,
        "PREVIOUS_CAP_AUTHORITY": previous["EXISTING_AUTHORITY"],
        "PREVIOUS_TRIANGLE_CAP": CAP_BEFORE,
        "ROUTE_B": envelope,
        "PROFILE_BOUND_AFTER": bound,
        **family,
        "NEW_OWNER_CAP_REALIZED_BY_STS13_WITNESS": realized,
        "FAMILY_NOTE": (
            "Single-row update only. The new owner's cap 270 is realized by the pinned STS13 "
            "witness, so closing other rows cannot lower the family below this bound."
        ),
        "CURRENT_INCUMBENT": INCUMBENT,
        "INCUMBENT_CHANGED": "NO",
        "RUN1_MUTATED": "NO",
        "SOLVER_CALLS": 0,
        "HEAVY_SOLVER_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


def render(result: Mapping[str, object]) -> str:
    return json.dumps(result, indent=2, sort_keys=True) + "\n"


def main() -> None:
    result = compute_result()
    RESULT_PATH.write_text(render(result), encoding="utf-8")
    keys = (
        "CERTIFIED_T_CAP",
        "PROFILE_BOUND_AFTER",
        "FAMILY_BOUND_AFTER_SINGLE_ROW_UPDATE",
        "FAMILY_OWNERS_AFTER",
        "FAMILY_BOUND_DELTA",
    )
    print(json.dumps({k: result[k] for k in keys}, indent=2))


if __name__ == "__main__":
    main()
