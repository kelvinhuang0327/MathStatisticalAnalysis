"""Exact structural S4 certificate for the STS(13) profile at its cap t=270.

Authority. The split-cap owner chase 2f709256 is pinned by tree and SHA-256. Its family
state is rebuilt from the e44a635f ledger replay plus its own committed certificates, and
the result must match its stored row digest. Only row 55555555555511111100 changes, and
only at t=270. Its triangle cap 270, its S4 base and every Route-B term at t=22..269 are
kept verbatim.

Setting. There are 20 tickets with 22 triple and 27 pair label supports, and two tickets
share at most one label. G is the overlap graph with g_v=6+d_v. For d=(5^12,1^6,0^2) this
gives g=(11^12,7^6,6^2) and W=sum C(g_v,2)=816. A wedge x-v-y is closed when x~y and open
otherwise. Each triangle closes three wedges, so the open-wedge count is OW=W-3t, and
OW=6 at t=270.

Lemma 1 (open-wedge inequality). If a and b are nonadjacent with a common neighbour, then
OW >= g_a+g_b-c, where c=|N(a)&N(b)|. Fix a common neighbour w. The c wedges a-x-b with
x in N(a)&N(b) are open. For u in N(a)-N(b) (so u!=w and u!=b), the wedge u-a-w is open
unless u~w. In that case u-w-b is open, because u is not adjacent to b. Symmetrically, for
v in N(b)-N(a), either v-b-w or v-w-a is open. Their centres and endpoint pairs make these
g_a+g_b-c wedges distinct.

Lemma 2 (isolation). Take any open wedge x-y-z. Lemma 1 and c<=min(g_x,g_z) give
6 >= g_x+g_z-c >= max(g_x,g_z). The minimum degree is 6, so g_x=g_z=6. Hence {x,z} is the
unique pair {a,b} of degree-6 tickets (the two d=0 tickets), c=6 and N(a)=N(b). The bound
is then tight, so the six wedges a-w-b with w in N(a) are all the open wedges, and every
open wedge has endpoints {a,b}. A connected graph with that property has diameter at most
two: a shortest path v0-v1-v2-v3 would give open wedges with distinct endpoint pairs
{v0,v2} and {v1,v3}. Its only nonadjacent pair is therefore {a,b}, so the component of a
is K_n minus the edge ab. Since n-2=g_a=6, n=8. Its other six vertices have degree 7, and
they are all six degree-7 tickets. Every other component has no open wedge, so it is a
clique; its vertices have degree 11, so it is K12. Thus G = K12 + (K8-e), with
t=C(12,3)+C(8,3)-6=270 and OW=6. No numerical search is used.

Lemma 3 (label supports). A triple label makes its three tickets pairwise adjacent, so each
triple support lies inside one component. K12 holds sum(d)/3=60/3=20 triple supports and
K8-e holds 6/3=2. Both of the latter lie on the six d=1 tickets, because a and b have d=0.
Two triple supports share at most one ticket (sharing two would give two common labels), so
a quartet contains at most one triple support. Then:
* K = C(12,4)+C(8,4)-C(6,2) = 550, since a quartet of K8-e is a K4 unless it contains a, b;
* A = 20*9+2*5 = 190, since each triple extends to a K4 by every other vertex of its
  component (in K8-e the triple avoids a and b, so all five others qualify);
* the five-edge quartets are exactly {a,b,x,y}, C(6,2)=15 of them. They contain a and b,
  which lie in no triple support, so D=15 have no contained triple and none has one;
* a quartet meeting both components has at most three edges.
The star count sum C(g_v,3)=2230=4K+2D (no paw or claw occurs) is an independent identity.

Weights. The pinned fourth-order table (higher-order closure r2) gives 679 outcomes for six
edges without a contained triple, 448 for six edges with one, 112 for five edges without
one, and 0 for every other quartet. Its local class DP is re-run on every quartet class of
the legal STS(13) witness. So every realization of the profile at t=270 has exactly
  S4 = 679(K-A) + 448A + 112D = 331,240,
which replaces the Route-B floor 679*K4(270)-231*min(K4(270),A_max) = 325,486.

Adoption. The t=270 term becomes S1-S2+S3(270)-floor(4*331,240/7) = 313,399,016; here
4*S4 is divisible by 7. The terms for t=22..269 are unchanged, with maximum 313,392,760, so
the profile bound falls from 313,402,304 to 313,399,016. The complete family maximum is
recomputed over all 4,647 resolved rows and the W<=785 cursor, keeping all 4,844 admissible
profiles covered. This branch contains no t=264 motif result, so the owner
66666555555311100000 keeps its committed bound. No solver, portfolio search or outcome
enumeration is run.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import replace
from fractions import Fraction
from itertools import combinations, combinations_with_replacement
from math import comb
from pathlib import Path

from . import b649_k20_min_s2_higher_order_closure_r2 as hoc
from . import b649_k20_min_s2_split_cap_current_owner_chase_r1 as chase

split = chase.split
prior = chase.prior
TASK_ID = "B649_K20_MIN_S2_STS13_ISOLATION_S4_CERTIFICATE_R1"
TASK_BRANCH = "codex/b649-k20-min-s2-sts13-isolation-s4-certificate-r1"
BASE_HEAD = "2f70925698cb28758fdf29a62bc5e91028c03a81"
BASE_TREE = "216bd91dee0afa58f8186a38aec52b1d47781ef8"
BASE_RESULT_SHA256 = "2269cc5e5e3bf08650fa711a240e7d088814e1bcd35d0cb9efcb01a91a2d67f3"
PROFILE = "55555555555511111100"
CAP = 270
LOAD_BEARING_T = 270
START_FAMILY_UB = 313_404_008
START_OWNER_IDS = ["66666555555311100000"]
START_PROFILE_BOUND = 313_402_304
INCUMBENT = chase.INCUMBENT
WEIGHT_K4 = 679
WEIGHT_K4_TRIPLE = 448
WEIGHT_DIAMOND = 112
RESULT_FILENAME = "b649-k20-min-s2-sts13-isolation-s4-certificate-r1-result.json"
ROOT = chase.ROOT
RESULT_PATH = ROOT / prior.RESULT_DIRECTORY / RESULT_FILENAME
CERTIFICATE_LOCATOR = f"{RESULT_FILENAME}:STS13_T270_CERTIFICATE"
Adjacency = tuple[frozenset[int], ...]
Wedge = tuple[int, int, int]
integer = chase.integer
object_row = chase.object_row
rows = chase.rows
text = chase.text


def pinned_base() -> dict[str, object]:
    """The 2f709256 chase result at its exact tree and digest, with its family state."""

    if chase.git("rev-parse", f"{BASE_HEAD}^{{tree}}").decode().strip() != BASE_TREE:
        raise AssertionError("base tree mismatch")
    blob = chase.git("show", f"{BASE_HEAD}:{prior.RESULT_DIRECTORY}/{chase.RESULT_FILENAME}")
    if hashlib.sha256(blob).hexdigest() != BASE_RESULT_SHA256:
        raise AssertionError("chase authority digest mismatch")
    base = object_row(json.loads(blob))
    expected: dict[str, object] = {
        "TASK_ID": chase.TASK_ID,
        "FINAL_COMPLETE_FAMILY_UB": START_FAMILY_UB,
        "FINAL_OWNER_IDS": START_OWNER_IDS,
        "NEXT_COMPETING_BOUND": START_PROFILE_BOUND,
        "FINAL_RESOLVED_ROW_COUNT": chase.RESOLVED_COUNT,
        "CURRENT_INCUMBENT": INCUMBENT,
    }
    for key, value in expected.items():
        if base.get(key) != value:
            raise AssertionError(f"chase authority mismatch: {key}")
    return base


def module_provenance() -> dict[str, str]:
    """Every reused module equals its blob at 2f709256, byte for byte."""

    out: dict[str, str] = {}
    for module in (chase, split, prior, chase.r20, hoc, *prior.PROVENANCE_MODULES):
        if module.__file__ is None:
            raise AssertionError("reused module has no source")
        path = Path(module.__file__).resolve()
        if not path.is_relative_to(ROOT):
            raise AssertionError(f"reused module loaded outside this tree: {path}")
        relative = path.relative_to(ROOT).as_posix()
        committed = chase.git("show", f"{BASE_HEAD}:{relative}")
        if path.read_bytes() != committed:
            raise AssertionError(f"reused source changed: {relative}")
        out[relative] = hashlib.sha256(committed).hexdigest()
    return out


def rows_digest(ledger: Mapping[str, chase.Row]) -> str:
    serialized = [{"PROFILE_ID": pid, "CURRENT_BOUND": ledger[pid].bound} for pid in sorted(ledger)]
    return hashlib.sha256(json.dumps(serialized, sort_keys=True).encode()).hexdigest()


def base_ledger(auth: chase.Authority, base: Mapping[str, object]) -> dict[str, chase.Row]:
    """The e44a635f replay with 2f709256's tightened rows installed and digest-checked."""

    ledger = dict(auth.ledger)
    for index, raw in enumerate(rows(base["CERTIFICATES"])):
        cert = object_row(raw)
        if cert["STATUS"] != chase.TIGHTENED:
            continue
        pid = text(cert["PROFILE_ID"])
        old = ledger[pid]
        existing = (cert["EXISTING_BOUND"], cert["EXISTING_TRIANGLE_CAP"], cert["S4_BASE"])
        if existing != (old.bound, old.cap, old.s4_base):
            raise AssertionError(f"chase certificate does not start from the replay: {pid}")
        cap, bound = integer(cert["TRIANGLE_CAP"]), integer(cert["ALL_T_MAX_BOUND"])
        terms = split.route_b_terms(split.profile_values(pid), cap, old.s4_base)
        stored = rows(cert["ALL_T_TERMS"])
        if [list(t) for t in terms] != stored or max(t[1] for t in terms) != bound:
            raise AssertionError(f"chase certificate envelope changed: {pid}")
        locator = f"{chase.RESULT_FILENAME}:CERTIFICATES[{index}]"
        ledger[pid] = replace(old, bound=bound, cap=cap, source=locator)
    if rows_digest(ledger) != base["FINAL_RESOLVED_ROWS_SHA256"]:
        raise AssertionError("rebuilt ledger differs from the 2f709256 row digest")
    if chase.family_state(ledger) != (START_FAMILY_UB, START_OWNER_IDS):
        raise AssertionError("rebuilt family state differs from 2f709256")
    return ledger


def adjacency(n: int, edges: Sequence[tuple[int, int]]) -> Adjacency:
    out: list[set[int]] = [set() for _ in range(n)]
    for x, y in edges:
        if x == y or y in out[x]:
            raise ValueError("graph edges must be distinct non-loops")
        out[x].add(y)
        out[y].add(x)
    return tuple(map(frozenset, out))


def open_wedges(adj: Adjacency) -> list[Wedge]:
    """Every open wedge as (centre, low end, high end)."""

    return [
        (v, x, y)
        for v, near in enumerate(adj)
        for x, y in combinations(sorted(near), 2)
        if y not in adj[x]
    ]


def wedge(centre: int, x: int, y: int) -> Wedge:
    return (centre, min(x, y), max(x, y))


def lemma1_wedges(adj: Adjacency, a: int, b: int) -> list[Wedge]:
    """The g_a+g_b-c distinct open wedges that Lemma 1 assigns to a nonadjacent pair."""

    common = adj[a] & adj[b]
    if a == b or b in adj[a] or not common:
        raise ValueError("Lemma 1 needs a nonadjacent pair with a common neighbour")
    w = min(common)
    out = [wedge(c, a, b) for c in sorted(common)]
    for end, other in ((a, b), (b, a)):
        for u in sorted(adj[end] - adj[other]):
            out.append(wedge(end, u, w) if w not in adj[u] else wedge(w, u, other))
    opened = set(open_wedges(adj))
    if len(set(out)) != len(out) or not set(out) <= opened:
        raise AssertionError("Lemma 1 wedges are not distinct open wedges")
    if len(out) != len(adj[a]) + len(adj[b]) - len(common):
        raise AssertionError("Lemma 1 count differs from g_a+g_b-c")
    return out


def isolation(profile: str, t: int) -> dict[str, object]:
    """Lemma 2 over the degree sequence: the only graph with these degrees and OW."""

    g = Counter(6 + d for d in split.profile_values(profile))
    w = sum(n * comb(v, 2) for v, n in g.items())
    ow = w - 3 * t
    if ow <= 0:
        raise AssertionError("isolation needs at least one open wedge")
    # Lemma 1: an open wedge's endpoints satisfy g_x+g_z-c <= OW with 1 <= c <= min(g).
    feasible = [
        (gx, gz, c)
        for gx, gz in combinations_with_replacement(sorted(g), 2)
        if gx != gz or g[gx] >= 2
        for c in range(1, min(gx, gz) + 1)
        if gx + gz - c <= ow
    ]
    if len(feasible) != 1:
        raise AssertionError("open-wedge endpoints are not forced to one degree pair")
    ga, gb, c = feasible[0]
    if not ga == gb == c or g[ga] != 2 or ga + gb - c != ow:
        raise AssertionError("endpoints are not a unique twin pair absorbing every open wedge")
    order = ga + 2
    if g[order - 1] != order - 2:
        raise AssertionError("the near-clique interior is not the whole degree class")
    rest = g - Counter({ga: 2, order - 1: order - 2})
    if any(n % (v + 1) for v, n in rest.items()):
        raise AssertionError("remaining degree classes do not split into cliques")
    cliques = sorted((v + 1 for v, n in rest.items() for _ in range(n // (v + 1))), reverse=True)
    triangles = sum(comb(k, 3) for k in cliques) + comb(order, 3) - (order - 2)
    if triangles != t:
        raise AssertionError("forced structure does not have t triangles")
    return {
        "W": w,
        "T": t,
        "OPEN_WEDGES": ow,
        "DEGREE_COUNTS": {str(v): n for v, n in sorted(g.items(), reverse=True)},
        "FEASIBLE_ENDPOINTS": [list(f) for f in feasible],
        "ENDPOINT_DEGREE": ga,
        "COMMON_NEIGHBOURS": c,
        "LEMMA1_TIGHT": True,
        "NEAR_CLIQUE_ORDER": order,
        "CLIQUE_ORDERS": cliques,
        "STRUCTURE": " + ".join([*(f"K{k}" for k in cliques), f"(K{order}-e)"]),
        "STRUCTURE_TRIANGLES": triangles,
        "STATUS": "PROVED_UNIQUE",
    }


def forced_graph(profile: str, iso: Mapping[str, object]) -> Adjacency:
    """K12 + (K8-e) on the sorted profile; the missing edge joins the two d=0 tickets."""

    d = split.profile_values(profile)
    order = integer(iso["NEAR_CLIQUE_ORDER"])
    blocks: list[range] = []
    start = 0
    for k in map(integer, rows(iso["CLIQUE_ORDERS"])):
        blocks.append(range(start, start + k))
        start += k
    near = range(start, start + order)
    if near.stop != len(d) or any(d[v] for v in near[-2:]):
        raise AssertionError("near-clique endpoints are not the trailing d=0 tickets")
    edges = [e for block in (*blocks, near) for e in combinations(block, 2)]
    edges.remove((near[-2], near[-1]))
    adj = adjacency(len(d), edges)
    if [len(n) for n in adj] != [6 + v for v in d]:
        raise AssertionError("forced graph has the wrong degree sequence")
    if len(open_wedges(adj)) != iso["OPEN_WEDGES"]:
        raise AssertionError("forced graph has the wrong open-wedge count")
    if split.triangle_count(range(len(d)), set(edges)) != iso["T"]:
        raise AssertionError("forced graph triangle count differs")
    return adj


def labels(profile: str, iso: Mapping[str, object]) -> dict[str, object]:
    """Lemma 3: the label supports force K, A and D on the isolated structure."""

    d = split.profile_values(profile)
    order = integer(iso["NEAR_CLIQUE_ORDER"])
    cliques = [integer(k) for k in rows(iso["CLIQUE_ORDERS"])]
    near_d = d[sum(cliques) :]
    if near_d[-2:] != (0, 0):
        raise AssertionError("the missing-edge endpoints must carry no triple support")
    start, clique_triples = 0, list[int]()
    for k in cliques:
        incidences = sum(d[start : start + k])
        if incidences % 3:
            raise AssertionError("clique component triple incidences are not a multiple of 3")
        clique_triples.append(incidences // 3)
        start += k
    if sum(near_d) % 3:
        raise AssertionError("near-clique triple incidences are not a multiple of 3")
    near_triples = sum(near_d) // 3
    pair_labels = [comb(k, 2) - 3 * n for k, n in zip(cliques, clique_triples, strict=True)]
    pair_labels.append(comb(order, 2) - 1 - 3 * near_triples)
    if sum(clique_triples) + near_triples != 22 or sum(pair_labels) != 27 or min(pair_labels) < 0:
        raise AssertionError("component label supports differ from the 22/27 minimum-S2 split")
    k4 = sum(comb(k, 4) for k in cliques) + comb(order, 4) - comb(order - 2, 2)
    contained = sum(n * (k - 3) for k, n in zip(cliques, clique_triples, strict=True))
    contained += near_triples * (order - 3)
    diamonds = comb(order - 2, 2)
    stars = sum(comb(6 + v, 3) for v in d)
    if stars != 4 * k4 + 2 * diamonds:
        raise AssertionError("star identity sum C(g,3) = 4K + 2D fails")
    s4 = WEIGHT_K4 * (k4 - contained) + WEIGHT_K4_TRIPLE * contained + WEIGHT_DIAMOND * diamonds
    return {
        "CLIQUE_TRIPLE_SUPPORTS": clique_triples,
        "NEAR_CLIQUE_TRIPLE_SUPPORTS": near_triples,
        "COMPONENT_PAIR_LABELS": pair_labels,
        "K4_COUNT": k4,
        "TRIPLE_CONTAINING_K4_COUNT": contained,
        "TRIPLE_FREE_K4_COUNT": k4 - contained,
        "DIAMOND_COUNT": diamonds,
        "DIAMOND_WITH_TRIPLE_COUNT": 0,
        "PAW_COUNT": 0,
        "CLAW_COUNT": 0,
        "STAR_COUNT": stars,
        "QUARTET_WEIGHTS": {
            "SIX_EDGES_NO_TRIPLE": WEIGHT_K4,
            "SIX_EDGES_ONE_TRIPLE": WEIGHT_K4_TRIPLE,
            "FIVE_EDGES_NO_TRIPLE": WEIGHT_DIAMOND,
            "OTHER": 0,
        },
        "EXACT_S4": s4,
    }


def table_weight(edges: int, triples: int) -> int:
    weights = {(6, 0): WEIGHT_K4, (6, 1): WEIGHT_K4_TRIPLE, (5, 0): WEIGHT_DIAMOND}
    return weights.get((edges, triples), 0)


def witness(
    triples: Sequence[split.Support], pairs: Sequence[split.Support], iso: Mapping[str, object]
) -> dict[str, object]:
    """A legal realization: isolation structure, quartet classes and class-DP S4."""

    seen = split.analyze_realization(triples, pairs)
    if seen["PROFILE_ID"] != PROFILE or seen["TRIANGLES"] != iso["T"]:
        raise AssertionError("witness is not a t=270 realization of the profile")
    supports = [*triples, *pairs]
    tickets = [sorted(k + 1 for k, s in enumerate(supports) if v in s) for v in range(20)]
    d = [sum(v in s for s in triples) for v in range(20)]
    adj = adjacency(20, sorted(split.edges_of(supports)))
    components: list[set[int]] = []
    for v in range(20):
        if not any(v in c for c in components):
            comp, frontier = {v}, [v]
            while frontier:
                frontier = [y for x in frontier for y in adj[x] if y not in comp]
                comp |= set(frontier)
            components.append(comp)
    gaps = [sum(1 for x, y in combinations(sorted(c), 2) if y not in adj[x]) for c in components]
    shape = sorted(zip(map(len, components), gaps, strict=True))
    near = next(c for c in components if len(c) == iso["NEAR_CLIQUE_ORDER"])
    missing = [(x, y) for x, y in combinations(sorted(near), 2) if y not in adj[x]]
    expected = sorted([*((k, 0) for k in map(integer, rows(iso["CLIQUE_ORDERS"]))), (len(near), 1)])
    if shape != expected or [d[v] for v in missing[0]] != [0, 0]:
        raise AssertionError("witness overlap graph is not the isolated structure")
    triple_sets = [frozenset(s) for s in triples]
    classes: Counter[tuple[int, int]] = Counter()
    profiles: Counter[tuple[tuple[int, ...], int, int]] = Counter()
    for q in combinations(range(20), 4):
        edges = sum(1 for x, y in combinations(q, 2) if y in adj[x])
        inside = sum(1 for s in triple_sets if s <= set(q))
        counts = [0] * 16
        for label in range(1, 50):
            counts[sum(1 << i for i, v in enumerate(q) if label in tickets[v])] += 1
        classes[(edges, inside)] += 1
        profiles[(tuple(counts), edges, inside)] += 1
    s4_dp = 0
    for (counts, edges, inside), n in profiles.items():
        weight = hoc.compressed_four_ticket_intersection_count(
            counts, pool_size=49, draw_size=6, outright_matches=3
        )
        if weight != table_weight(edges, inside):
            raise AssertionError("class DP disagrees with the fourth-order weight table")
        s4_dp += n * weight
    decomposition = hoc.k20_min_s2_s4_decomposition(tickets)
    return {
        "TRIANGLES": seen["TRIANGLES"],
        "COMPONENT_SHAPES": [list(s) for s in shape],
        "MISSING_EDGE_TRIPLE_DEGREES": [d[v] for v in missing[0]],
        "QUARTET_CLASSES": {f"{e}E{b}T": n for (e, b), n in sorted(classes.items())},
        "DP_PROFILE_COUNT": len(profiles),
        "DECOMPOSITION": [
            decomposition.six_edges_without_contained_triple,
            decomposition.six_edges_with_contained_triple,
            decomposition.five_edges_without_contained_triple,
        ],
        "S4_DECOMPOSITION": decomposition.s4,
        "S4_CLASS_DP": s4_dp,
        "STATUS": "PASS",
    }


def adoption(row: chase.Row, lab: Mapping[str, object]) -> dict[str, object]:
    """Replace only the t=270 S4 floor by the exact S4; every lower-t term stays."""

    p = split.profile_values(PROFILE)
    if row.cap != CAP:
        raise AssertionError("triangle-cap authority changed")
    old = split.route_b_terms(p, row.cap, row.s4_base)
    if max(term[1] for term in old) != row.bound:
        raise AssertionError("existing cap authority does not reproduce the ledger bound")
    *lower, last = old
    t, old_bound, k4_floor, a_used, old_s4, s3 = last
    k4, a, s4 = (integer(lab[k]) for k in ("K4_COUNT", "TRIPLE_CONTAINING_K4_COUNT", "EXACT_S4"))
    a_max = sum(d * (4 + d) for d in p) // 3
    if t != LOAD_BEARING_T or k4 < k4_floor or a > a_max or a_used != min(k4_floor, a_max):
        raise AssertionError("exact counts violate the Route-B floor premises")
    if s4 < old_s4:
        raise AssertionError("exact S4 is below the proved floor")
    w = sum(comb(6 + d, 2) for d in p)
    if s3 != 2800 * w + 11872 * (t - 22) - 30800:
        raise AssertionError("S3(270) differs from the local three-ticket formula")
    bound = hoc.K20_S1 - hoc.K20_S2 + s3 - (4 * s4) // 7
    if Fraction(hoc.K20_S1 - hoc.K20_S2 + s3) - Fraction(4 * s4, 7) < bound:
        raise AssertionError("integer t=270 term exceeds its rational value")
    terms = [*lower, (t, bound, k4, a, s4, s3)]
    best = max(terms, key=lambda term: (term[1], term[0]))
    return {
        "TRIANGLE_CAP": row.cap,
        "CAP_AUTHORITY": row.source,
        "S4_BASE": row.s4_base,
        "EXISTING_K4_FLOOR": k4_floor,
        "EXISTING_A_MAX": a_max,
        "EXISTING_S4_FLOOR": old_s4,
        "EXACT_S4": s4,
        "S4_CREDIT_GAIN": s4 - old_s4,
        "S4_DIVISIBLE_BY_7": s4 % 7 == 0,
        "S3_T270": s3,
        "T270_OLD_BOUND": old_bound,
        "T270_NEW_BOUND": bound,
        "LOWER_T_MAX_BOUND": max(term[1] for term in lower),
        "LOWER_T_TERMS_RETAINED": len(lower),
        "ALL_T_TERMS": [list(term) for term in terms],
        "TERM_COUNT": len(terms),
        "ARGMAX_TRIANGLES": best[0],
        "OLD_PROFILE_BOUND": row.bound,
        "FULL_PROFILE_BOUND": best[1],
    }


def certificate(row: chase.Row) -> dict[str, object]:
    """The complete t=270 certificate for the STS(13) profile, recomputed from scratch."""

    iso = isolation(PROFILE, LOAD_BEARING_T)
    adj = forced_graph(PROFILE, iso)
    probe = lemma1_wedges(adj, len(adj) - 2, len(adj) - 1)
    lab = labels(PROFILE, iso)
    seen = witness(*split.witness_supports("STS13"), iso)
    exact = integer(lab["EXACT_S4"])
    counts = [lab["TRIPLE_FREE_K4_COUNT"], lab["TRIPLE_CONTAINING_K4_COUNT"], lab["DIAMOND_COUNT"]]
    if seen["S4_DECOMPOSITION"] != exact or seen["S4_CLASS_DP"] != exact:
        raise AssertionError("witness S4 differs from the structural S4")
    if seen["DECOMPOSITION"] != counts:
        raise AssertionError("witness quartet counts differ from the structural counts")
    return {
        "PROFILE_ID": PROFILE,
        "LOAD_BEARING_T": LOAD_BEARING_T,
        "GRAPH_ISOLATION": iso,
        "FORCED_GRAPH_LEMMA1_WEDGES": len(probe),
        "LABEL_SUPPORTS": lab,
        "WITNESS": seen,
        "ADOPTION": adoption(row, lab),
        "STATUS": "PASS",
    }


def verify_certificate(cert: Mapping[str, object], row: chase.Row) -> None:
    """Reject any certificate that differs from a fresh recomputation."""

    fresh = certificate(row)
    changed = sorted(k for k in fresh.keys() | cert.keys() if fresh.get(k) != cert.get(k))
    if changed:
        raise AssertionError(f"STS13 certificate rejected: {changed}")


def family(
    auth: chase.Authority, ledger: Mapping[str, chase.Row], bound: int
) -> tuple[dict[str, chase.Row], dict[str, object]]:
    """Install the new row and recompute the complete maximum by an independent sort."""

    updated = dict(ledger)
    updated[PROFILE] = replace(ledger[PROFILE], bound=bound, source=CERTIFICATE_LOCATOR)
    covered = chase.coverage(updated, auth.members, auth.base)
    ranked = sorted(((r.bound, pid) for pid, r in updated.items()), reverse=True)
    terms = [*ranked, (prior.CURSOR_BOUND, prior.CURSOR_ID)]
    top = max(b for b, _pid in terms)
    owners = sorted((pid for b, pid in terms if b == top), reverse=True)
    reused, reused_owners = chase.family_state(updated)
    if (top, owners) != (reused, sorted(reused_owners, reverse=True)):
        raise AssertionError("complete family recomputation disagrees")
    if not INCUMBENT <= top <= START_FAMILY_UB:
        raise AssertionError("family bound left the [incumbent, start] interval")
    return updated, {
        "FINAL_FAMILY_UB_FROM_BASE": top,
        "FINAL_OWNER_IDS": reused_owners,
        "NEXT_COMPETING_BOUND": max(b for b, pid in terms if pid not in owners),
        "NEXT_COMPETING_IDS": [pid for b, pid in ranked if b < top][:1],
        "PROFILE_RANK_AFTER": [pid for _b, pid in terms].index(PROFILE) + 1,
        "FINAL_RESOLVED_ROW_COUNT": len(updated),
        "FINAL_RESOLVED_ROWS_SHA256": rows_digest(updated),
        "COVERAGE": covered,
        "CURRENT_INCUMBENT": INCUMBENT,
        "REMAINING_GAP": top - INCUMBENT,
    }


def compute_result(authority: chase.Authority | None = None) -> dict[str, object]:
    base = pinned_base()
    provenance = module_provenance()
    auth = chase.load_authority() if authority is None else authority
    ledger = base_ledger(auth, base)
    row = ledger[PROFILE]
    if (row.bound, row.cap) != (START_PROFILE_BOUND, CAP):
        raise AssertionError("STS13 row differs from the 2f709256 ledger")
    cert = certificate(row)
    verify_certificate(cert, row)
    adopted = object_row(cert["ADOPTION"])
    bound = integer(adopted["FULL_PROFILE_BOUND"])
    if not INCUMBENT <= bound < row.bound:
        raise AssertionError("certificate does not strictly improve a sound profile bound")
    _updated, fam = family(auth, ledger, bound)
    lab = object_row(cert["LABEL_SUPPORTS"])
    source = Path(__file__).read_bytes()
    return {
        "TASK_ID": TASK_ID,
        "TASK_BRANCH": TASK_BRANCH,
        "TASK_STATUS": "COMPLETE_SELF_CHECK_ONLY",
        "REMAINING_TASK_MODEL": "最強模型",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "BASE_RESULT": chase.RESULT_FILENAME,
        "BASE_RESULT_SHA256": BASE_RESULT_SHA256,
        "SOURCE_SHA256": hashlib.sha256(source).hexdigest(),
        "PROOF": __doc__,
        "MODULE_PROVENANCE": provenance,
        "BASE_FAMILY_UB": START_FAMILY_UB,
        "BASE_OWNER_IDS": START_OWNER_IDS,
        "BASE_ROWS_SHA256_VERIFIED": base["FINAL_RESOLVED_ROWS_SHA256"],
        "STS13_T270_CERTIFICATE": cert,
        "GRAPH_ISOLATION_STATUS": "PROVED_K12_PLUS_K8_MINUS_E_UNIQUE",
        "DEGREE_SEQUENCE_STATUS": "PASS_11^12_7^6_6^2_W816_OW6",
        "K4_COUNT": lab["K4_COUNT"],
        "TRIPLE_CONTAINING_K4_COUNT": lab["TRIPLE_CONTAINING_K4_COUNT"],
        "DIAMOND_COUNT": lab["DIAMOND_COUNT"],
        "EXACT_S4": lab["EXACT_S4"],
        "T270_OLD_BOUND": adopted["T270_OLD_BOUND"],
        "T270_NEW_BOUND": adopted["T270_NEW_BOUND"],
        "LOWER_T_MAX_BOUND": adopted["LOWER_T_MAX_BOUND"],
        "FULL_PROFILE_BOUND": bound,
        "WITNESS_SOUNDNESS_STATUS": "PASS_LEGAL_STS13_T270_EXACT_S4_MATCH",
        "PROFILE_COVERAGE_STATUS": "COMPLETE_4844_INHERITED_PARTITION_DIGESTS_MATCH",
        "MOTIF_T264_RESULT_INCLUDED": False,
        **fam,
        "SOLVER_CALLS": 0,
        "OUTCOME_ENUMERATIONS": 0,
        "NEW_HEAVY_SOLVER_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


def render(result: Mapping[str, object]) -> str:
    return json.dumps(result, indent=2, sort_keys=True) + "\n"


def main() -> None:
    result = compute_result()
    RESULT_PATH.write_text(render(result), encoding="utf-8")
    keys = ("EXACT_S4", "T270_NEW_BOUND", "FULL_PROFILE_BOUND", "FINAL_FAMILY_UB_FROM_BASE")
    print(json.dumps({k: result[k] for k in (*keys, "NEXT_COMPETING_BOUND")}, indent=2))


if __name__ == "__main__":
    main()
