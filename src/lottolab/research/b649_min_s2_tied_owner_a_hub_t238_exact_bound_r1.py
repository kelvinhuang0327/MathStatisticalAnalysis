"""Exact cap T<=238 for the tied row 66555555555441000000 under the seven-row authority.

Authority. The seven-row result (6569a966, tree 986d2085) changed only 66555555555540000000,
so the six-row ledger row stands: 66555555555441000000 at 313395448, tied with
66555555555522000000, below the next competing level 313398248 and above the preserved
cursor 66544333333333332222 at 313394584. Its S4 base is the global profile floor 112 (r28);
the R32 Route-B envelope reproduces 313395448 at cap 265 and not at cap 264, and R30's
refinement steps for this profile end at cap 265. The 4,647-row ledger is not replayed and
no row of it is changed.

Support model and premises (as in the T256 certificate). Twenty tickets of six labels; 22
triple and 27 pair supports; two tickets share at most one label, so G has 93 edges and
deg(v)=6+d_v. T=t(G). Here d=(6^2,5^9,4^2,1,0^6): core K={d>0}, k=14, with one hub y at
d=1; zeros Z, z=6. Triples lie in K, so a core x meets Z only through its 6-d_x pair labels:
sigma_x<=6-d_x, i.e. 0 at d=6, {0,1} at d=5, {0,1,2} at d=4 and c=sigma_y in 0..5. A zero
has six distinct neighbours, at most five of them zeros: g_u=6-zeta_u is its degree in the
simple graph G[Z], and r=sum sigma=sum zeta=36-2e with e=|E(G[Z])|.

Identity. H is the complement, |E(H)|=97. T=1140-18*97+900-t(H)=294-t(H); Goodman's
1140-1692/2 agrees. With M=H[K], MZ=H[Z], deg_M(x)=7-d_x+sigma_x, deg_MZ(u)=zeta_u-1, the
T256 certificate's mixed-triangle count gives
 t(H)=z|M|+k|MZ|-sum sigma*deg_M-sum zeta*deg_MZ+P,  P=t(M)+t(MZ)+sum_M c_Z+sum_MZ c_K,
and z|M|+k|MZ|=3(32+r)+7(r-6). Hence T=D-P with P>=t(M)>=0 and
 D = 240 + sum_x sigma_x(sigma_x+4-d_x) + sum_u zeta_u(zeta_u-8)
   = 168 + sum_x sigma_x(sigma_x+4-d_x) + sum_u g_u(g_u-4),
which equals e44a635f's F as a polynomial (checked on 0, e_i, 2e_i and e_i+e_j). Per class
sigma(sigma+4-d) is 0 at d=6 and d=5, sigma^2 at d=4 and c(c+3) at y, so the core part is at
most 2*4+40=48 and sum sigma(sigma+3-d) is at most 2*2+35=39.

Range-only chains. zeta(zeta-8)<=-7 on 1..6 gives T<=240+48-42=246; (zeta-1)(zeta-6)<=0
gives T<=204+sum sigma(sigma+3-d)<=243. The range-only relaxation peaks at 241 (r=11).

Zero-graph lemma (G[Z] is a simple graph on six vertices). Exactly one case holds:
 (i)   some g_u=0: every other zero has g<=4, sum g(g-4)<=0 and T<=168+48=216;
 (ii)  every g>=1, G[Z]!=K6: a non-edge uw has g_u, g_w in 1..4, where g(g-5)<=-4, so
       sum g(g-4)<=2e-8=28-r and T<=196+39=235;
 (iii) G[Z]=K6: g=5, e=15, r=6, every zero has one core neighbour and D=198+core part with
       sum sigma=6. If c<=4 the core part is at most 28+4 and T<=230. If c=5 exactly one
       w!=y has sigma_w=1, d_w in {4,5}, and D=239 (d_w=4) or 238 (d_w=5).
So G[Z] alone gives T<=239, at the single point G[Z]=K6, c=5, d_w=4.

Hub lemma (the one further ingredient). y has G-degree 7: c zeros and a set A of 7-c core
vertices, so deg_M(y)=6+c and N_M(y)=K-{y}-A. Every M-edge meeting neither y nor A lies in
N_M(y) and closes a triangle with y, distinct edges giving distinct triangles, and at most
sum_A deg_M M-edges meet A. Hence
 P >= t(M) >= |M| - (6+c) - sum_{a in A} deg_M(a),  |M|=(32+r)/2,
and sum_A deg_M is at most the 7-c largest of 7-d_x+sigma_x over x!=y. In case (iii) with
c=5: |M|=19, deg_M(y)=11; for d_w=4 the two largest are 4 and 3, so t(M)>=1 and T<=238;
for d_w=5 they are 3 and 3, so t(M)>=2 and T<=236. So T<=238 for every legal support
structure of the profile. Only P>=t(M), the legal ranges, the simplicity of G[Z] and the
hub count are used; no sampling or search.

Exactness. Remove from STS(13) on core tickets 0..12 the double star {0,1,4}, {0,2,7},
{0,5,11}, {1,3,8}, {1,6,12}; add the triple {0,1,13} with hub y=13; take core pairs 0-4, 1-6,
1-12, 2-7, 5-11, 3-8, y to zeros 14..18, ticket 0 to zero 19, and K6 on Z. The pinned
validator accepts it, the profile is 66555555555441000000, and a direct count gives T=238
with D=239 and P=t(M)=1 (the triangle y,6,12). So 238 is the exact maximum of T on the
profile, and no T cap can take this row's Route-B bound below 313153668.

Completeness and recount. Class-sorted sigma against every degree sequence of a graph on
six vertices (all 2^15 labelled graphs; the set equals the Erdos-Gallai set), with equal
sums and the hub bound, peaks at exactly 238 at the unique point a=0, d=4 sigmas (1,0), c=5,
G[Z]=K6. An independent recount over all 27,648 labelled sigma vectors and all 32,768
labelled graphs on Z, through e44's raw F, agrees. Premise ablation: ranges only 241;
parity, the support count or the zero graph alone 239; hub alone 240; hub with any one of
them 238.

Route B. The R32 envelope at S4 base 112 is re-evaluated for 22<=T<=238 in both pinned
implementations and in exact rationals. It is a prefix of the cap-265 envelope and peaks at
T=238 with 313153668 (base-insensitive there: the K4 term is 154567). The widest cap whose
envelope stays at or below the cursor 313394584 is 264 (313386680); the widest at or below
the incumbent is 250 (313261212). The tied partner keeps 313395448 and the three rows at
313398248 are above it, so no family bound is claimed. Seeded random graphs that satisfy the
graph premises (400 general, 200 in the binding class G[Z]=K6, c=5, d_w=4) are recounted
triangle by triangle; they are checks, never the proof.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections import Counter
from collections.abc import Collection, Iterator, Mapping, Sequence
from fractions import Fraction
from itertools import combinations, combinations_with_replacement, pairwise, product
from math import comb
from pathlib import Path
from types import ModuleType

from . import b649_k20_min_s2_current_cursor_class_owner_chase_r28 as r28
from . import b649_k20_min_s2_dangerous_core_realizability_r5 as r5
from . import b649_k20_min_s2_route_b_current_owner_refinement_r32 as r32
from . import b649_k20_min_s2_split_cap_current_owner_chase_r1 as chase
from . import b649_k20_min_s2_topw12_split_cap_certificate_r1 as split
from . import b649_min_s2_core_zero_t257_three_row_cert_r1 as three
from . import b649_min_s2_next_owner_core_zero_t256_cert_r1 as t256
from . import b649_min_s2_two_certified_row_combined_authority_r1 as two

require, sha256, render = two.require, two.sha256, two.render
integer, rows, text = two.integer, two.rows, two.text
require(
    (three, two, split, r32, r5, chase)
    == (t256.three, t256.two, t256.split, t256.r32, t256.r5, t256.chase),
    "reused modules differ from the T256 certificate's",
)

TASK_ID = "B649_NEXT_TIED_OWNER_A_EXACT_BOUND_R1"
FROZEN_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
FROZEN_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
FROZEN_RESULT = f"{two.RESULT_DIRECTORY}/{t256.RESULT_STEM}-result.json"
FROZEN_RESULT_SHA256 = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"
R30_RESULT = (
    f"{two.RESULT_DIRECTORY}/b649-k20-min-s2-current-cursor-dynamic-family-max-r30-result.json"
)
TARGET_PROFILE = "66555555555441000000"
TIED_PARTNER = "66555555555522000000"
SEVEN_ROW_OWNERS = ("66555555555531000000", "66655555554441000000", "66655555555422000000")
FAMILY_BOUND = 313_398_532
NEXT_COMPETING_BOUND = 313_398_248
CURSOR_ID = "66544333333333332222"
CURSOR_BOUND = 313_394_584
OLD_CAP = 265
OLD_BOUND = 313_395_448
S4_BASE = 112
CONSTANT = 240
ZERO_GRAPH_CONSTANT = 168
M_BASE = 32
PROPOSED_CAP = 238
ZERO_GRAPH_CAP = 239
RANGE_ONLY_CAP = 241
CHAIN_CAPS = {"MINIMAL": 246, "CONVEXITY": 243}
CURSOR_SUFFICIENT_CAP = 264
CLOSURE_THRESHOLD = 250
NEW_BOUND = 313_153_668
INCUMBENT = two.INCUMBENT
TICKET_CAPACITY = 6
HUB_DEGREE = 1
ZERO_GRAPH = "ZERO_GRAPH"
HUB = "HUB"
OPTIONAL_PREMISES = frozenset({"PARITY", "SUPPORT_COUNT", ZERO_GRAPH, HUB})
THEOREM_PREMISES = (ZERO_GRAPH, HUB)
CASE_CAPS = {"ISOLATED_ZERO": 216, "NO_ISOLATED_NOT_K6": 235, "K6": 238}
RANDOM_SEED = 20_261_013
RANDOM_GRAPHS = 400
BINDING_GRAPHS = 200
RESULT_STEM = "b649-min-s2-tied-owner-a-hub-t238-exact-bound-r1"
ROOT = two.ROOT
RESULT_PATH = ROOT / two.RESULT_DIRECTORY / f"{RESULT_STEM}-result.json"
REUSED: tuple[ModuleType, ...] = (t256, three, two, split, r32, r5, r28, chase)
Pair = tuple[int, int]
Support = tuple[int, ...]
Term = tuple[int, int, int, int, int, int]
Point = tuple[int, tuple[int, ...], int, tuple[int, ...]]

# The exactness witness: STS(13) minus this double star, as described in the docstring.
HUB_TICKET = 13
DOUBLE_STAR: tuple[Support, ...] = ((0, 1, 4), (0, 2, 7), (0, 5, 11), (1, 3, 8), (1, 6, 12))
WITNESS_CORE_PAIRS: tuple[Pair, ...] = ((0, 4), (1, 6), (1, 12), (2, 7), (5, 11), (3, 8))
WITNESS_CROSS_PAIRS: tuple[Pair, ...] = ((13, 14), (13, 15), (13, 16), (13, 17), (13, 18), (0, 19))

# Recorded at task time from local refs; never read here, never relied on.
PRIOR_ART: dict[str, dict[str, object]] = {
    "BONFERRONI5_ROW": {
        "COMMIT": "e3a9843db4339167bffcdc92fb782ff6bb663ed8",
        "CLAIMED_BOUND_FOR_TARGET": 313_386_680,
        "RULE": "MIN(ROUTE_B, BONFERRONI5) AT T=265 WITH T<=264 TERMS RETAINED",
        "USE": "NOT_RELIED_ON_DIFFERENT_BOUND_RULE",
    },
    "FAMILY_CLOSURE": {
        "COMMIT": "e6fee5ebbfb972a1432bbc10ab5a337feac38478",
        "USE": "OTHER_LINEAGE_NOT_READ_BY_THIS_MODULE",
    },
    "SIBLING_ZERO_GRAPH_T240": {
        "COMMIT": "2434d065eea9aa9c133f1c5d47e2fb99ae638e12",
        "PROFILE": "66655555554441000000",
        "USE": "SAME_METHOD_OTHER_PROFILE_NOT_IMPORTED",
    },
}


def module_path(module: ModuleType) -> str:
    require(module.__file__ is not None, "reused module has no source")
    source = Path(text(module.__file__)).resolve()
    require(source.is_relative_to(ROOT), "reused module outside this worktree")
    return source.relative_to(ROOT).as_posix()


def blob_sha1(raw: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(raw) + raw).hexdigest()


def frozen_sources() -> dict[str, str]:
    """Every file read here equals its 6569a966 blob; two git calls in total."""
    require(three.git_tree(FROZEN_HEAD) == FROZEN_TREE, "frozen head/tree mismatch")
    paths = sorted(
        {*(module_path(m) for m in REUSED), FROZEN_RESULT, t256.SIX_RESULT_PATH, R30_RESULT}
    )
    listing = chase.git("ls-tree", FROZEN_HEAD, "--", *paths).decode().splitlines()
    committed = {line.split("\t", 1)[1]: line.split()[2] for line in listing}
    require(sorted(committed) == paths, "a pinned path is missing at the frozen head")
    for path in paths:
        require(blob_sha1((ROOT / path).read_bytes()) == committed[path], f"changed: {path}")
    return {path: sha256((ROOT / path).read_bytes()) for path in paths}


def frozen_row() -> dict[str, object]:
    """The target row, its tie and the cursor as the frozen results record them."""
    raw = (ROOT / FROZEN_RESULT).read_bytes()
    require(sha256(raw) == FROZEN_RESULT_SHA256, "frozen seven-row result digest mismatch")
    seven = two.object_row(json.loads(raw))
    six_raw = (ROOT / t256.SIX_RESULT_PATH).read_bytes()
    require(sha256(six_raw) == t256.SIX_RESULT_SHA256, "six-row result digest mismatch")
    six_bounds = {
        p: integer(b)
        for p, b in two.object_row(
            two.object_row(json.loads(six_raw))["RESOLVED_ROW_BOUNDS"]
        ).items()
    }
    changed = rows(seven["ROWS_CHANGED_FROM_SIX_ROW"])
    seven_bounds = {**six_bounds, t256.TARGET_PROFILE: integer(seven["PROFILE_BOUND_AFTER"])}
    cursor = two.object_row(two.object_row(seven["PRESERVED_SIX_ROW_STATUS"])["CURSOR"])
    require(
        seven["TASK_ID"] == t256.TASK_ID
        and seven["FAMILY_BOUND_AFTER"] == FAMILY_BOUND
        and seven["NEXT_COMPETING_BOUND"] == NEXT_COMPETING_BOUND
        and rows(seven["NEXT_COMPETING_OWNER_IDS"]) == list(SEVEN_ROW_OWNERS)
        and changed == [t256.TARGET_PROFILE]
        and seven["SIX_ROW_RESULT_SHA256"] == t256.SIX_RESULT_SHA256
        and seven["INCUMBENT"] == INCUMBENT
        and seven["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
        and cursor == {"BOUND": CURSOR_BOUND, "ID": CURSOR_ID}
        and TARGET_PROFILE not in changed
        and sorted(p for p, b in seven_bounds.items() if b == OLD_BOUND)
        == sorted((TARGET_PROFILE, TIED_PARTNER))
        and NEXT_COMPETING_BOUND > OLD_BOUND > CURSOR_BOUND,
        "frozen authority does not record the target row as packeted",
    )
    r30 = two.object_row(json.loads((ROOT / R30_RESULT).read_bytes()))
    steps = [
        two.object_row(s)
        for s in rows(r30["REFINEMENT_STEPS"])
        if two.object_row(s).get("PROFILE_ID") == TARGET_PROFILE
    ]
    r30_caps = [integer(s["TRIANGLE_CAP"]) for s in steps]
    require(r30_caps == [268, 267, 266, OLD_CAP], "R30 cap history for the target changed")
    return {
        "SEVEN_ROW_FAMILY_BOUND": FAMILY_BOUND,
        "SEVEN_ROW_NEXT_COMPETING_BOUND": NEXT_COMPETING_BOUND,
        "SEVEN_ROW_RESOLVED_BOUND": seven_bounds[TARGET_PROFILE],
        "TIED_ROWS_AT_OLD_BOUND": sorted((TARGET_PROFILE, TIED_PARTNER)),
        "SEVEN_ROW_ROWS_ABOVE_TARGET": sum(b > OLD_BOUND for b in seven_bounds.values()),
        "CURSOR": {"ID": CURSOR_ID, "BOUND": CURSOR_BOUND},
        "R30_REFINEMENT_CAPS": r30_caps,
    }


def profile() -> split.Profile:
    p = split.profile_values(TARGET_PROFILE)
    require(chase.profile_id(p) == TARGET_PROFILE, "theorem is stated for one profile only")
    return p


def core_degrees() -> list[int]:
    return [d for d in profile() if d]


def premises() -> dict[str, object]:
    """Profile split, edge counts and the complement constants, two independent ways."""
    p = profile()
    core = core_degrees()
    k, z = len(core), p.count(0)
    g_edges = sum(TICKET_CAPACITY + d for d in p) // 2
    h_edges = comb(20, 2) - g_edges
    phi = comb(20, 3) - 18 * h_edges + sum(comb(13 - d, 2) for d in p)
    goodman = Fraction(comb(20, 3)) - Fraction(sum((TICKET_CAPACITY + d) * (13 - d) for d in p), 2)
    m_base = sum(k - 1 - TICKET_CAPACITY - d for d in core)
    mz_base = z * (z - 1 - TICKET_CAPACITY)
    mixed = Fraction(z * m_base + k * mz_base, 2)
    classes = dict(sorted(Counter(core).items(), reverse=True))
    require(
        (k, z, classes, sum(p), sum(d * d for d in p)) == (14, 6, {6: 2, 5: 9, 4: 2, 1: 1}, 66, 330)
        and sum(TICKET_CAPACITY + d for d in p) % 2 == 0
        and g_edges == 22 * 3 + 27 == 93
        and h_edges == 97
        and phi == goodman == 294
        and (m_base, mz_base, mixed) == (M_BASE, -6, 54)
        and phi - mixed == CONSTANT
        and CONSTANT - z * 12 == ZERO_GRAPH_CONSTANT
        and z - 1 < TICKET_CAPACITY,
        "core-zero premises fail",
    )
    return {
        "PROFILE_ID": TARGET_PROFILE,
        "DEGREE_PROFILE": "d=(6^2,5^9,4^2,1,0^6)",
        "CORE_VERTICES": k,
        "ZERO_VERTICES": z,
        "CORE_DEGREE_CLASSES": {str(d): n for d, n in classes.items()},
        "SUM_D": sum(p),
        "SUM_D_SQUARED": sum(d * d for d in p),
        "G_EDGES": g_edges,
        "H_EDGES": h_edges,
        "PHI_INCLUSION_EXCLUSION": phi,
        "PHI_GOODMAN": int(goodman),
        "Z_TIMES_M_PLUS_K_TIMES_MZ": "3(32+sum sigma)+7(sum zeta-6)",
        "CONSTANT": int(phi - mixed),
        "ZERO_GRAPH_CONSTANT": ZERO_GRAPH_CONSTANT,
    }


def sigma_ranges() -> dict[int, range]:
    """sigma_x <= 6-d_x: a core vertex reaches Z only through its pair labels."""
    return {d: range(TICKET_CAPACITY - d + 1) for d in sorted(set(core_degrees()), reverse=True)}


def zeta_range(support: int = TICKET_CAPACITY) -> range:
    """1 <= zeta_u: at most z-1=5 of a zero's six neighbours are zeros."""
    z = profile().count(0)
    return range(TICKET_CAPACITY - (z - 1), min(TICKET_CAPACITY, support) + 1)


def core_part(core: Sequence[int], sigma: Sequence[int]) -> int:
    return sum(s * (s + 4 - d) for d, s in zip(core, sigma, strict=True))


def class_term(d: int, s: int) -> int:
    """sigma(sigma+4-d) in closed form: 0 at d=6 and d=5, sigma^2 at d=4, c(c+3) at d=1."""
    return {6: 0, 5: 0, 4: s * s, 1: s * (s + 3)}[d]


def separable(core: Sequence[int], sigma: Sequence[int], zeta: Sequence[int]) -> int:
    """D = 240 + sum sigma(sigma+4-d) + sum zeta(zeta-8), so that T = D - P."""
    return CONSTANT + core_part(core, sigma) + sum(v * (v - 8) for v in zeta)


def zero_graph_form(core: Sequence[int], sigma: Sequence[int], g: Sequence[int]) -> int:
    """The same D in the G[Z] degrees g = 6 - zeta: 168 + core part + sum g(g-4)."""
    return ZERO_GRAPH_CONSTANT + core_part(core, sigma) + sum(v * (v - 4) for v in g)


def hub_bound(core: Sequence[int], sigma: Sequence[int]) -> int:
    """Lower bound on t(M) through the d=1 hub: ceil(|M|-(6+c)-top_{7-c} deg_M), at least 0."""
    (y,) = [i for i, d in enumerate(core) if d == HUB_DEGREE]
    k = len(core)
    degrees = sorted(
        (k - 1 - TICKET_CAPACITY - core[i] + sigma[i] for i in range(k) if i != y), reverse=True
    )
    outside = TICKET_CAPACITY + HUB_DEGREE - sigma[y]
    twice = M_BASE + sum(sigma) - 2 * (k - 1 - outside) - 2 * sum(degrees[:outside])
    return max(0, -(-twice // 2))


def quadratic_points(k: int, z: int) -> list[tuple[tuple[int, ...], tuple[int, ...]]]:
    """0, e_i, 2e_i and e_i+e_j: equal values here make two quadratics identical."""
    n = k + z
    vectors = [[0] * n]
    for i in range(n):
        for step in (1, 2):
            vectors.append([step if j == i else 0 for j in range(n)])
    for i, j in combinations(range(n), 2):
        vectors.append([1 if m in (i, j) else 0 for m in range(n)])
    return [(tuple(v[:k]), tuple(v[k:])) for v in vectors]


def identity_check() -> dict[str, object]:
    """D equals e44a635f's F as polynomials; the zero-graph and per-class forms hold."""
    p, core = profile(), core_degrees()
    points = quadratic_points(len(core), p.count(0))
    for sigma, zeta in points:
        require(
            three.split_objective(p, sigma, zeta) == separable(core, sigma, zeta),
            "D differs from e44's F",
        )
        require(
            zero_graph_form(core, sigma, [TICKET_CAPACITY - v for v in zeta])
            == separable(core, sigma, zeta),
            "zero-graph form differs from D",
        )
    tables = {
        d: {s: (s * (s + 4 - d), class_term(d, s)) for s in values}
        for d, values in sigma_ranges().items()
    }
    require(
        all(lhs == rhs for t in tables.values() for lhs, rhs in t.values()),
        "per-class reduction fails on the legal range",
    )
    return {
        "T_COMPLEMENT": "294-t(H)",
        "T_CLOSED_FORM": "240+sum sigma(sigma+4-d)+sum zeta(zeta-8)-P",
        "T_ZERO_GRAPH_FORM": "168+sum sigma(sigma+4-d)+sum g(g-4)-P, g=6-zeta=deg_G[Z]",
        "T_CLASS_FORM": "168+sum_{d=4} sigma^2+c(c+3)+sum g(g-4)-P",
        "P_DEFINITION": "t(M)+t(MZ)+sum_{xy in M}|N_G(x)&N_G(y)&Z|+sum_{uw in MZ}|N_G(u)&N_G(w)&K|",
        "P_NONNEGATIVE": "SUM_OF_FOUR_CARDINALITIES; P>=t(M)>=0",
        "E44_IDENTITY_POINTS_CHECKED": len(points),
        "SIGMA_RANGES": {str(d): list(v) for d, v in sigma_ranges().items()},
        "ZETA_RANGE": list(zeta_range()),
        "CORE_TERMS": {
            str(d): {str(s): pair[0] for s, pair in t.items()} for d, t in tables.items()
        },
    }


def zero_graphs() -> Iterator[tuple[int, tuple[int, ...]]]:
    """All 2^15 labelled simple graphs on the six zeros, as (edge count, degree vector)."""
    z = profile().count(0)
    pairs = list(combinations(range(z), 2))
    for mask in range(1 << len(pairs)):
        g = [0] * z
        for bit, (u, w) in enumerate(pairs):
            if mask >> bit & 1:
                g[u] += 1
                g[w] += 1
        yield mask.bit_count(), tuple(g)


def graph_degree_sequences() -> frozenset[tuple[int, ...]]:
    """Sorted degree sequences of graphs on Z; must equal the Erdos-Gallai set on 0..5."""
    z = profile().count(0)
    seen = frozenset(tuple(sorted(g, reverse=True)) for _, g in zero_graphs())
    eg = frozenset(
        tuple(sorted(s, reverse=True))
        for s in combinations_with_replacement(range(z), z)
        if split.graphical(list(s))
    )
    require(seen == eg, "graph degree sequences differ from the Erdos-Gallai set")
    return seen


def class_sigma(a: int, b: Sequence[int], c: int) -> tuple[int, ...]:
    counts = Counter(core_degrees())
    return (0,) * counts[6] + (1,) * a + (0,) * (counts[5] - a) + tuple(b) + (c,)


def core_classes() -> Iterator[tuple[int, tuple[int, ...], int]]:
    """Class-sorted sigma: a d=5 vertices at 1, a multiset at d=4, c at the hub."""
    counts, ranges = Counter(core_degrees()), sigma_ranges()
    for a, b, c in product(
        range(counts[5] + 1),
        combinations_with_replacement(ranges[4], counts[4]),
        ranges[HUB_DEGREE],
    ):
        yield a, tuple(sorted(b, reverse=True)), c


def case_lemma() -> dict[str, object]:
    """The three G[Z] cases and the hub split of the K6 case, each on its whole domain."""
    core = core_degrees()
    require(
        all(g * (g - 5) <= 0 for g in range(TICKET_CAPACITY))
        and all(g * (g - 5) <= -4 for g in range(1, TICKET_CAPACITY - 1)),
        "per-vertex zero inequality fails",
    )
    cases: dict[str, list[int]] = {"ISOLATED_ZERO": [], "NO_ISOLATED_NOT_K6": [], "K6": []}
    by_edges: dict[int, int] = {}
    for e, g in zero_graphs():
        value = sum(v * (v - 4) for v in g)
        require(2 * e == sum(g) and max(g) <= TICKET_CAPACITY - 1, "degree sum is not 2e")
        by_edges[e] = max(by_edges.get(e, value), value)
        if min(g) == 0:
            require(value <= 0, "isolated-zero case exceeds 0")
            cases["ISOLATED_ZERO"].append(value)
        elif e < comb(TICKET_CAPACITY, 2):
            require(value <= 2 * e - 8, "non-complete case exceeds 2e-8")
            cases["NO_ISOLATED_NOT_K6"].append(value - 2 * e)
        else:
            require(g == (5,) * 6 and value == 30, "K6 case differs")
            cases["K6"].append(value)
    points = [
        (a, b, c, core_part(core, class_sigma(a, b, c)), hub_bound(core, class_sigma(a, b, c)))
        for a, b, c in core_classes()
    ]
    core_max = max(v for *_, v, _ in points)
    core_minus_r = max(v - (a + sum(b) + c) for a, b, c, v, _ in points)
    at_six = [(a, b, c, v, h) for a, b, c, v, h in points if a + sum(b) + c == 6]
    k6_base = ZERO_GRAPH_CONSTANT + max(cases["K6"])
    low_core = max(v for _, _, c, v, _ in at_six if c < 5)
    hub_points = [
        (a, list(b), v, h, k6_base + v, k6_base + v - h) for a, b, c, v, h in at_six if c == 5
    ]
    caps = {
        "ISOLATED_ZERO": ZERO_GRAPH_CONSTANT + core_max + max(cases["ISOLATED_ZERO"]),
        "NO_ISOLATED_NOT_K6": ZERO_GRAPH_CONSTANT
        + 36
        + core_minus_r
        + max(cases["NO_ISOLATED_NOT_K6"]),
        "K6": max(k6_base + low_core, *(row[-1] for row in hub_points)),
    }
    require(
        (core_max, core_minus_r, low_core) == (48, 39, 32)
        and len(cases["K6"]) == 1
        and max(cases["ISOLATED_ZERO"]) == 0
        and max(cases["NO_ISOLATED_NOT_K6"]) == -8
        and hub_points == [(0, [1, 0], 41, 1, 239, 238), (1, [0, 0], 40, 2, 238, 236)]
        and caps == CASE_CAPS,
        "case lemma constants changed",
    )
    core_by_r: dict[int, tuple[int, int]] = {}
    for a, b, c, v, h in points:
        r = a + sum(b) + c
        old = core_by_r.get(r, (v, v - h))
        core_by_r[r] = (max(old[0], v), max(old[1], v - h))
    table = [
        {
            "E": e,
            "R": 36 - 2 * e,
            "MAX_SUM_G_G_MINUS_4": by_edges[e],
            "MAX_D": None
            if 36 - 2 * e not in core_by_r
            else ZERO_GRAPH_CONSTANT + core_by_r[36 - 2 * e][0] + by_edges[e],
            "MAX_D_MINUS_HUB": None
            if 36 - 2 * e not in core_by_r
            else ZERO_GRAPH_CONSTANT + core_by_r[36 - 2 * e][1] + by_edges[e],
        }
        for e in sorted(by_edges)
    ]
    peaks = [
        max(integer(row[key]) for row in table if row[key] is not None)
        for key in ("MAX_D", "MAX_D_MINUS_HUB")
    ]
    require(
        peaks == [ZERO_GRAPH_CAP, PROPOSED_CAP] == [k6_base + 41, max(caps.values())],
        "edge-count table does not peak at 239 and 238",
    )
    return {
        "CASES": {
            "ISOLATED_ZERO": "sum g(g-4)<=0; T<=168+48=216",
            "NO_ISOLATED_NOT_K6": "sum g(g-4)<=2e-8=28-r; T<=196+39=235",
            "K6_C_AT_MOST_4": "e=15, r=6, core<=28+4; T<=230",
            "K6_C5_W_AT_D4": "D=239; |M|=19, deg_M(y)=11, top-two deg_M 4+3; t(M)>=1, T<=238",
            "K6_C5_W_AT_D5": "D=238; top-two deg_M 3+3; t(M)>=2, T<=236",
        },
        "CASE_GRAPH_COUNTS": {k: len(v) for k, v in cases.items()},
        "CASE_CAPS": caps,
        "ZERO_GRAPH_ONLY_CAP": peaks[0],
        "CORE_PART_MAX": core_max,
        "CORE_MINUS_R_MAX": core_minus_r,
        "K6_CORE_PART_MAX_C_AT_MOST_4": low_core,
        "K6_C5_POINTS_A_B_CORE_HUB_D_D_MINUS_HUB": hub_points,
        "BY_ZERO_EDGES": table,
        "CAP": max(caps.values()),
    }


def relaxation(premise_set: Collection[str] = THEOREM_PREMISES) -> Iterator[Point]:
    """Class-sorted sigma and sorted zeta over the legal ranges with equal sums."""
    require(set(premise_set) <= OPTIONAL_PREMISES, "unknown premise")
    z = profile().count(0)
    graphic = graph_degree_sequences() if ZERO_GRAPH in premise_set else None
    for a, b, c in core_classes():
        r = a + sum(b) + c
        if "PARITY" in premise_set and (TICKET_CAPACITY * z - r) % 2:
            continue
        support = (
            a + sum(1 for v in b if v) + (c > 0)
            if "SUPPORT_COUNT" in premise_set
            else TICKET_CAPACITY
        )
        for zeta in combinations_with_replacement(zeta_range(support), z):
            if sum(zeta) != r:
                continue
            g = tuple(sorted((TICKET_CAPACITY - v for v in zeta), reverse=True))
            if graphic is not None and g not in graphic:
                continue
            yield a, b, c, tuple(sorted(zeta, reverse=True))


def relaxation_maximum(
    premise_set: Collection[str] = THEOREM_PREMISES,
) -> tuple[int, list[Point], int]:
    """Max of D minus (the hub bound if HUB is a premise) over the relaxation."""
    core = core_degrees()
    best: int | None = None
    top: list[Point] = []
    count = 0
    for a, b, c, zeta in relaxation(premise_set):
        sigma = class_sigma(a, b, c)
        d = separable(core, sigma, zeta)
        require(
            d
            == ZERO_GRAPH_CONSTANT
            + sum(v * v for v in b)
            + c * (c + 3)
            + sum((6 - v) * (2 - v) for v in zeta)
            and d == zero_graph_form(core, sigma, [TICKET_CAPACITY - v for v in zeta]),
            "class form differs from D",
        )
        f = d - (hub_bound(core, sigma) if HUB in premise_set else 0)
        count += 1
        if best is None or f > best:
            best, top = f, [(a, b, c, zeta)]
        elif f == best:
            top.append((a, b, c, zeta))
    if best is None:
        raise AssertionError("empty relaxation")
    return best, top, count


def labelled_recount() -> dict[str, object]:
    """Independent: all labelled sigma and all labelled G[Z] through e44's raw 2F."""
    p, core = profile(), core_degrees()
    k, z = len(core), p.count(0)
    phi = sum(comb(13 - d, 2) for d in p) - 606
    (y,) = [i for i, d in enumerate(core) if d == HUB_DEGREE]
    core_best: dict[int, tuple[int, tuple[int, ...], int]] = {}
    vectors = 0
    for sigma in product(*(range(TICKET_CAPACITY - d + 1) for d in core)):
        vectors += 1
        h = [13 - z - d + s for d, s in zip(core, sigma, strict=True)]
        part = 2 * phi - z * sum(h) + 2 * sum(s * v for s, v in zip(sigma, h, strict=True))
        r = sum(sigma)
        outside = TICKET_CAPACITY + HUB_DEGREE - sigma[y]
        m_degrees = sorted((h[i] for i in range(k) if i != y), reverse=True)
        hub = max(0, -(-(M_BASE + r - 2 * h[y] - 2 * sum(m_degrees[:outside])) // 2))
        require(h[y] == k - 1 - outside, "hub M-degree is not 6+c")
        part -= 2 * hub
        if r not in core_best or part > core_best[r][0]:
            core_best[r] = (part, sigma, hub)
    zero_best: dict[int, tuple[int, tuple[int, ...]]] = {}
    graphs = 0
    for _, g in zero_graphs():
        graphs += 1
        zeta = tuple(TICKET_CAPACITY - v for v in g)
        a = [z - 7 + v for v in zeta]
        part = -k * sum(a) + 2 * sum(v * w for v, w in zip(zeta, a, strict=True))
        r = sum(zeta)
        if r not in zero_best or part > zero_best[r][0]:
            zero_best[r] = (part, zeta)
    best: int | None = None
    for r in sorted(core_best.keys() & zero_best.keys()):
        (left, sigma, hub), (right, zeta) = core_best[r], zero_best[r]
        require((left + right) % 2 == 0, "2F is odd on an equal-sum point")
        value = (left + right) // 2
        require(
            three.split_objective(p, sigma, zeta) - hub == value and hub == hub_bound(core, sigma),
            "split halves differ from F minus the hub bound",
        )
        best = value if best is None else max(best, value)
    require(best is not None, "empty labelled recount")
    return {
        "METHOD": "LABELLED_SIGMA_X_LABELLED_ZERO_GRAPH_RAW_E44_F_MINUS_HUB_INTEGER",
        "SIGMA_VECTORS": vectors,
        "ZERO_GRAPHS": graphs,
        "COMMON_R_VALUES": sorted(core_best.keys() & zero_best.keys()),
        "MAXIMUM": best,
    }


def closed_form_chains() -> dict[str, object]:
    """Ranges and P>=0 only: two one-line chains, both under the cursor-sufficient cap."""
    require(
        all(v * (v - 8) <= -7 and (v - 1) * (v - 6) <= 0 for v in zeta_range()),
        "zero inequalities fail on 1..6",
    )
    counts = Counter(core_degrees())
    z = profile().count(0)
    ranges = sigma_ranges()
    core_max = sum(n * max(class_term(d, s) for s in ranges[d]) for d, n in counts.items())
    minus_r = sum(n * max(s * (s + 3 - d) for s in ranges[d]) for d, n in counts.items())
    caps = {
        "MINIMAL": CONSTANT + core_max - 7 * z,
        "CONVEXITY": CONSTANT - 6 * z + minus_r,
    }
    require(
        (core_max, minus_r) == (48, 39) and caps == CHAIN_CAPS,
        "closed-form chains changed",
    )
    return {
        "MINIMAL": "zeta(zeta-8)<=-7 on 1..6: T<=240+48-42=246",
        "CONVEXITY": "(zeta-1)(zeta-6)<=0: T<=204+sum sigma(sigma+3-d)<=204+39=243",
        "CAPS": caps,
        "USES": ["P>=0", "LEGAL_RANGES"],
        "AT_OR_BELOW_CURSOR_SUFFICIENT_CAP": max(caps.values()) <= CURSOR_SUFFICIENT_CAP,
        "AT_OR_BELOW_CLOSURE_THRESHOLD": max(caps.values()) <= CLOSURE_THRESHOLD,
    }


def witness() -> tuple[tuple[Support, ...], tuple[Support, ...]]:
    """STS(13) minus the double star, plus the hub triple, the core pairs, the cross pairs, K6."""
    blocks = three.sts13_blocks()
    a1, a2 = DOUBLE_STAR[0][:2]
    star = [v for b in DOUBLE_STAR for v in b if v not in (a1, a2)]
    removed = {t256.edge(x, y) for b in DOUBLE_STAR for x, y in combinations(b, 2)}
    require(
        set(DOUBLE_STAR) <= set(blocks)
        and [sum(a in b for b in DOUBLE_STAR) for a in (a1, a2)] == [3, 3]
        and len(star) == len(set(star)) == 9
        and set(WITNESS_CORE_PAIRS) <= removed,
        "witness double star is not as described",
    )
    triples = tuple(sorted([*(b for b in blocks if b not in DOUBLE_STAR), (a1, a2, HUB_TICKET)]))
    zeros = range(HUB_TICKET + 1, 20)
    return triples, (*WITNESS_CORE_PAIRS, *WITNESS_CROSS_PAIRS, *combinations(zeros, 2))


def theorem() -> dict[str, object]:
    """T <= 238 for every legal structure of the target profile, attained by the witness."""
    facts, identity = premises(), identity_check()
    lemma = case_lemma()
    cap, top, count = relaxation_maximum()
    recount = labelled_recount()
    attained = realization_check()
    require(
        cap == PROPOSED_CAP == recount["MAXIMUM"] == lemma["CAP"] == attained["T"],
        "relaxation maximum or attained value is not 238",
    )
    ablation = {
        "NONE": relaxation_maximum(())[0],
        "PARITY_ONLY": relaxation_maximum(("PARITY",))[0],
        "SUPPORT_COUNT_ONLY": relaxation_maximum(("SUPPORT_COUNT",))[0],
        "ZERO_GRAPH_ONLY": relaxation_maximum((ZERO_GRAPH,))[0],
        "HUB_ONLY": relaxation_maximum((HUB,))[0],
        "PARITY_AND_HUB": relaxation_maximum(("PARITY", HUB))[0],
        "SUPPORT_COUNT_AND_HUB": relaxation_maximum(("SUPPORT_COUNT", HUB))[0],
        "ZERO_GRAPH_AND_HUB": cap,
        "PARITY_SUPPORT_COUNT_ZERO_GRAPH": relaxation_maximum(
            ("PARITY", "SUPPORT_COUNT", ZERO_GRAPH)
        )[0],
        "ALL_FOUR": relaxation_maximum(OPTIONAL_PREMISES)[0],
    }
    require(
        ablation["NONE"] == RANGE_ONLY_CAP
        and ablation["PARITY_ONLY"]
        == ablation["SUPPORT_COUNT_ONLY"]
        == ablation["ZERO_GRAPH_ONLY"]
        == ablation["PARITY_SUPPORT_COUNT_ZERO_GRAPH"]
        == ZERO_GRAPH_CAP
        and ablation["HUB_ONLY"] > ZERO_GRAPH_CAP
        and ablation["PARITY_AND_HUB"]
        == ablation["SUPPORT_COUNT_AND_HUB"]
        == ablation["ALL_FOUR"]
        == cap,
        "premise ablation changed",
    )
    return {
        **facts,
        **identity,
        "THEOREM_PREMISES": [
            "P>=t(M)>=0",
            "LEGAL_RANGES",
            "ZERO_GRAPH: G[Z] is a simple graph",
            "HUB: t(M)>=|M|-deg_M(y)-sum_{a in A} deg_M(a)",
        ],
        "NOT_LOAD_BEARING": ["PARITY: r even", "SUPPORT_COUNT: zeta_u<=#{sigma>0}"],
        "CASE_LEMMA": lemma,
        "GRAPH_DEGREE_SEQUENCES": len(graph_degree_sequences()),
        "RELAXATION_POINTS": count,
        "RELAXATION_MAXIMUM": cap,
        "RELAXATION_ARGMAX": [[a, list(b), c, list(zeta)] for a, b, c, zeta in top],
        "INDEPENDENT_RECOUNT": recount,
        "PREMISE_ABLATION": ablation,
        "RANGE_ONLY_CHAINS": closed_form_chains(),
        "TRIANGLE_CAP": cap,
        "ATTAINED_BY_WITNESS": attained,
        "EXACT_PROFILE_MAXIMUM": cap,
        "STATUS": "PROVEN_AND_ATTAINED",
    }


def case_cap(g: Sequence[int]) -> int:
    """The lemma's cap for the case a G[Z] degree vector falls in."""
    if min(g) == 0:
        return CASE_CAPS["ISOLATED_ZERO"]
    if min(g) < TICKET_CAPACITY - 1:
        return CASE_CAPS["NO_ISOLATED_NOT_K6"]
    return CASE_CAPS["K6"]


def graph_check(
    core: Sequence[int], zero: Sequence[int], d: Mapping[int, int], g: set[Pair]
) -> dict[str, object]:
    """One graph obeying the graph premises: direct recount of T, P, the hub and the case."""
    seen = t256.complement_split(core, zero, g)
    nb = {v: {w for e in g if v in e for w in e if w != v} for v in (*core, *zero)}
    direct = sum(
        1 for x, y, w in combinations(sorted(nb), 3) if y in nb[x] and w in nb[x] and w in nb[y]
    )
    sigma = [integer(v) for v in rows(seen["SIGMA"])]
    zeta = [integer(v) for v in rows(seen["ZETA"])]
    inner = [len(nb[u] & set(zero)) for u in zero]
    dc = [d[x] for x in core]
    p, t = integer(seen["P"]), integer(seen["T_G"])
    t_m = integer(rows(seen["P_TERMS"])[0])
    require(
        all(len(nb[x]) == TICKET_CAPACITY + d[x] for x in core)
        and all(len(nb[u]) == TICKET_CAPACITY for u in zero)
        and all(0 <= s <= TICKET_CAPACITY - c for c, s in zip(dc, sigma, strict=True)),
        "graph violates the degree premises",
    )
    (y,) = [x for x in core if d[x] == HUB_DEGREE]
    c = sigma[core.index(y)]
    outside = nb[y] & set(core)
    m_degree = {x: len(core) - 1 - len(nb[x] & set(core)) for x in core}
    m_edges = integer(seen["M_EDGES"])
    labelled = m_edges - m_degree[y] - sum(m_degree[a] for a in outside)
    hub = hub_bound(dc, sigma)
    value = separable(dc, sigma, zeta)
    require(
        2 * m_edges == M_BASE + sum(sigma)
        and m_degree[y] == TICKET_CAPACITY + c
        and len(outside) == TICKET_CAPACITY + HUB_DEGREE - c
        and t_m >= labelled
        and max(labelled, 0) >= hub,
        "graph violates the hub lemma",
    )
    require(
        inner == [TICKET_CAPACITY - v for v in zeta]
        and sum(sigma) == sum(zeta) == 36 - sum(inner)
        and direct == t == 294 - integer(seen["T_H"])
        and value == zero_graph_form(dc, sigma, inner)
        and t == value - p
        and p >= t_m >= 0
        and value - hub <= case_cap(inner) <= PROPOSED_CAP,
        "graph violates the T238 chain",
    )
    return {
        "T": t,
        "D": value,
        "P": p,
        "T_M": t_m,
        "HUB_BOUND": hub,
        "R": sum(sigma),
        "CASE_CAP": case_cap(inner),
    }


def realization_check(
    triples: Sequence[Support] | None = None, pairs: Sequence[Support] | None = None
) -> dict[str, object]:
    """A support structure is legal, of the target profile, and obeys every step above."""
    if triples is None or pairs is None:
        triples, pairs = witness()
    d = three.legal_degrees(triples, pairs)
    r5.validate_k20_support_realization(triples, pairs, d)
    require(chase.profile_id(split.profile_values(d)) == TARGET_PROFILE, "wrong profile")
    g = {t256.edge(x, y) for s in (*triples, *pairs) for x, y in combinations(s, 2)}
    core = [v for v in range(20) if d[v]]
    zero = [v for v in range(20) if not d[v]]
    return {"PROFILE_ID": TARGET_PROFILE, **graph_check(core, zero, dict(enumerate(d)), g)}


def realize(rng: random.Random, vertices: Sequence[int], degrees: Sequence[int]) -> set[Pair]:
    """Havel-Hakimi with random tie-breaks, then degree-preserving random swaps."""
    left = dict(zip(vertices, degrees, strict=True))
    edges: set[Pair] = set()
    while any(left.values()):
        v = max(left, key=lambda w: (left[w], rng.random()))
        others = sorted((w for w in left if w != v), key=lambda w: (-left[w], rng.random()))
        need = left[v]
        require(need <= len(others) and all(left[w] > 0 for w in others[:need]), "not graphical")
        for w in others[:need]:
            edges.add(t256.edge(v, w))
            left[w] -= 1
        left[v] = 0
    for _ in range(4 * len(edges)):
        (x, y), (u, w) = rng.sample(sorted(edges), 2)
        if len({x, y, u, w}) == 4 and t256.edge(x, w) not in edges and t256.edge(u, y) not in edges:
            edges -= {(x, y), (u, w)}
            edges |= {t256.edge(x, w), t256.edge(u, y)}
    return edges


def random_graphs(
    count: int = RANDOM_GRAPHS, seed: int = RANDOM_SEED, binding: bool = False
) -> dict[str, object]:
    """Seeded graphs with deg 6+d, zero degree 6 and sigma<=6-d: falsification only.

    With binding=True every graph lies in the binding class G[Z]=K6, c=5, d_w=4, D=239,
    so the hub lemma alone separates it from 239.
    """
    rng = random.Random(seed)
    core_d = core_degrees()
    core, zero = list(range(len(core_d))), list(range(len(core_d), 20))
    d = dict(enumerate([*core_d, *(0 for _ in zero)]))
    hub = core_d.index(HUB_DEGREE)
    fours = [x for x in core if core_d[x] == 4]
    checked, attempts, t_max, d_max, hub_max = 0, 0, 0, 0, 0
    cases: Counter[int] = Counter()
    while checked < count:
        attempts += 1
        require(attempts <= 50 * count, "random graph generator stalled")
        cross: set[Pair] = set()
        if binding:
            order = rng.sample(zero, len(zero))
            cross = {t256.edge(hub, u) for u in order[1:]} | {
                t256.edge(rng.choice(fours), order[0])
            }
        else:
            for x, c in zip(core, core_d, strict=True):
                top = TICKET_CAPACITY - c
                s = top if rng.random() < 0.5 else rng.randint(0, top)
                cross |= {t256.edge(x, u) for u in rng.sample(zero, s)}
        inner_k = [
            TICKET_CAPACITY + c - sum(t256.edge(x, u) in cross for u in zero)
            for x, c in zip(core, core_d, strict=True)
        ]
        inner_z = [TICKET_CAPACITY - sum(t256.edge(x, u) in cross for x in core) for u in zero]
        if not (split.graphical(inner_k) and split.graphical(inner_z)):
            continue
        g = cross | realize(rng, core, inner_k) | realize(rng, zero, inner_z)
        seen = graph_check(core, zero, d, g)
        require(
            not binding or (seen["D"], seen["HUB_BOUND"], seen["CASE_CAP"]) == (239, 1, 238),
            "binding sample left the binding class",
        )
        checked += 1
        cases[integer(seen["CASE_CAP"])] += 1
        t_max, d_max = max(t_max, integer(seen["T"])), max(d_max, integer(seen["D"]))
        hub_max = max(hub_max, integer(seen["HUB_BOUND"]))
    return {
        "ROLE": "SUPPLEMENTAL_FALSIFICATION_NOT_PROOF",
        "BINDING_CLASS_ONLY": binding,
        "SEED": seed,
        "GRAPHS_CHECKED": checked,
        "ATTEMPTS": attempts,
        "CASE_CAP_COUNTS": {str(k): v for k, v in sorted(cases.items())},
        "MAX_T": t_max,
        "MAX_D": d_max,
        "MAX_HUB_BOUND": hub_max,
    }


def check_terms(terms: Sequence[Term], cap: int, base: int) -> None:
    """Exact integer and rational recheck of every Route-B term, rounding included."""
    p = profile()
    g = [TICKET_CAPACITY + d for d in p]
    w, u = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g)
    a_max = Fraction(sum(d * (v - 2) for d, v in zip(p, g, strict=True)), 3)
    require([t[0] for t in terms] == list(range(22, cap + 1)), "triangle domain differs")
    for t, bound, k4, contained, s4, s3 in terms:
        excess = Fraction(u - (max(g) - 2) * (w - 3 * t), 4)
        k4_exact = max(0, -((-excess.numerator) // excess.denominator))
        c_exact = min(k4_exact, a_max.numerator // a_max.denominator)
        s4_exact = max(base, 448 * c_exact + 679 * (k4_exact - c_exact))
        s3_exact = 2800 * w + 11872 * (t - 22) - 30800
        exact = 372_228_640 - 63_838_600 + s3_exact - Fraction(4 * s4_exact, 7)
        require(
            (k4, contained, s4, s3) == (k4_exact, c_exact, s4_exact, s3_exact)
            and 0 <= bound - exact < 1,
            f"Route-B term {t} fails exact arithmetic",
        )


def route_b(cap: int, base: int = S4_BASE) -> tuple[list[Term], int]:
    """R32 envelope at cap: both pinned implementations, then exact arithmetic."""
    p = profile()
    terms = r32.route_b_envelope(p, cap, base)
    require(terms == split.route_b_terms(p, cap, base), "Route-B implementations differ")
    check_terms(terms, cap, base)
    return terms, max(term[1] for term in terms)


def route_b_result() -> dict[str, object]:
    require(r28.profile_s4_floor(profile()) == S4_BASE, "S4 base is not the profile floor")
    old_terms, old_bound = route_b(OLD_CAP)
    new_terms, new_bound = route_b(PROPOSED_CAP)
    peak = max(new_terms, key=lambda term: (term[1], term[0]))

    def widest(limit: int) -> int:
        below = [t for t, bound, *_ in old_terms if bound <= limit]
        require(below == list(range(22, max(below) + 1)), "envelope is not a prefix below limit")
        return max(below)

    sufficient, threshold = widest(CURSOR_BOUND), widest(INCUMBENT)
    require(
        old_bound == OLD_BOUND
        and route_b(OLD_CAP - 1)[1] < OLD_BOUND
        and all(x[1] < y[1] for x, y in pairwise(old_terms))
        and new_terms == old_terms[: len(new_terms)]
        and new_bound == NEW_BOUND == peak[1]
        and peak[0] == PROPOSED_CAP
        and route_b(PROPOSED_CAP, 0)[1] == new_bound
        and sufficient == CURSOR_SUFFICIENT_CAP
        and threshold == CLOSURE_THRESHOLD,
        "Route B does not extend the recorded row authority",
    )
    return {
        "BOUND_RULE": r32.BOUND_RULE,
        "S4_BASE": S4_BASE,
        "S4_BASE_SOURCE": "r28.profile_s4_floor (global profile floor, NB-asserted)",
        "S4_BASE_LOAD_BEARING_AT_ARGMAX": False,
        "CAP_BEFORE": OLD_CAP,
        "BOUND_BEFORE": old_bound,
        "BOUND_AT_CAP_BEFORE_MINUS_ONE": route_b(OLD_CAP - 1)[1],
        "CURSOR_BOUND": CURSOR_BOUND,
        "CURSOR_SUFFICIENT_CAP": sufficient,
        "BOUND_AT_CURSOR_SUFFICIENT_CAP": old_terms[sufficient - 22][1],
        "CLOSURE_THRESHOLD_CAP": threshold,
        "BOUND_AT_CLOSURE_THRESHOLD": old_terms[threshold - 22][1],
        "BOUND_AT_CLOSURE_THRESHOLD_PLUS_ONE": old_terms[threshold - 21][1],
        "BOUND_AT_CHAIN_CAPS": {k: old_terms[v - 22][1] for k, v in CHAIN_CAPS.items()},
        "BOUND_AT_RANGE_ONLY_CAP": old_terms[RANGE_ONLY_CAP - 22][1],
        "BOUND_AT_ZERO_GRAPH_CAP": old_terms[ZERO_GRAPH_CAP - 22][1],
        "CAP_AFTER": PROPOSED_CAP,
        "TERM_COUNT": len(new_terms),
        "ALL_T_TERMS": [list(t) for t in new_terms],
        "ARGMAX_TERM": list(peak),
        "ALL_T_MAX_BOUND": new_bound,
        "PREFIX_OF_CAP_265_ENVELOPE": True,
        "STATUS": "PASS_INTEGER_AND_RATIONAL",
    }


def compute_result() -> dict[str, object]:
    sources = frozen_sources()
    recorded = frozen_row()
    proof = theorem()
    route = route_b_result()
    new_bound = integer(route["ALL_T_MAX_BOUND"])
    lemma = two.object_row(proof["CASE_LEMMA"])
    recount = two.object_row(proof["INDEPENDENT_RECOUNT"])
    triples, pairs = witness()
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "STRICT_OWNER_BOUND_REDUCTION_PROVED_CAP_EXACT",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "PROOF": __doc__,
        "FROZEN_HEAD": FROZEN_HEAD,
        "FROZEN_TREE": FROZEN_TREE,
        "FROZEN_RESULT": FROZEN_RESULT,
        "FROZEN_RESULT_SHA256": FROZEN_RESULT_SHA256,
        "FROZEN_RESULT_SHA256_VERIFIED": True,
        "FROZEN_SOURCE_SHA256": sources,
        "FROZEN_ROW": recorded,
        "TARGET_PROFILE": TARGET_PROFILE,
        "DEGREE_PROFILE": proof["DEGREE_PROFILE"],
        "SOURCE_PROFILE_BOUND": OLD_BOUND,
        "SOURCE_T_CAP": OLD_CAP,
        "SOURCE_S4_BASE": S4_BASE,
        "SUPPORT_MODEL": three.support_model(),
        "PROOF_SCOPE": "FULL_PROFILE",
        "GOODMAN_IDENTITY": "T=294-t(H)=240+sum sigma(sigma+4-d)+sum zeta(zeta-8)-P",
        "SUPPORT_PREMISES": [
            "sigma_x<=6-d_x (core meets Z only through pair labels)",
            "1<=zeta_u (at most five zero neighbours)",
            "G[Z] simple graph on six vertices",
            "hub y (d=1): deg_G(y)=7, A=core G-neighbours of y, |A|=7-c",
        ],
        "NONNEGATIVE_REMAINDER": "P=t(M)+t(MZ)+sum_M c_Z+sum_MZ c_K>=t(M)>=0",
        "EXACT_IDENTITY": "T=168+sum_{d=4} sigma^2+c(c+3)+sum_u g_u(g_u-4)-P",
        "LOAD_BEARING_PREMISES": ["P>=t(M)>=0", "LEGAL_RANGES", "ZERO_GRAPH", "HUB"],
        "COMBINATORIAL_BOUND": lemma["CASES"],
        "INTEGER_ROUNDING": "every Route-B term rechecked: integer K4 ceil, A_MAX floor, "
        "exact-rational bound with 0<=bound-exact<1; hub bound is an integer ceiling",
        "RELAXATION_COMPLETENESS": "class-sorted sigma x all graph degree sequences on Z "
        f"({proof['RELAXATION_POINTS']} points) with the hub bound; every legal structure "
        "maps into it, and D and the hub bound are invariant under relabelling within classes",
        "INDEPENDENT_RECOUNT": f"{recount['SIGMA_VECTORS']} labelled sigma x "
        f"{recount['ZERO_GRAPHS']} labelled G[Z], raw e44 F minus hub, max {recount['MAXIMUM']}",
        "NEGATIVE_CASES": {
            "PREMISE_ABLATION_CAPS": proof["PREMISE_ABLATION"],
            "CLAIMED_CAP_237": "REFUTED_BY_WITNESS_WITH_T_238",
            "HUB_PLUS_ONE": "REFUTED_BY_WITNESS_WITH_T_M_1",
            "WRONG_CONSTANT": "REFUTED_BY_E44_IDENTITY",
            "D6_VERTEX_REACHING_Z": "REFUSED_BY_DEGREE_PREMISES",
            "ROUTE_B_PLUS_MINUS_ONE": "REFUTED_BY_EXACT_ARITHMETIC",
        },
        "COUNTEREXAMPLE_STATUS": "NONE: every checked graph has T=D-P<=D-hub<=its case cap<=238",
        "THEOREM_T238": proof,
        "WITNESS_TRIPLES": [list(s) for s in triples],
        "WITNESS_PAIRS": [list(s) for s in pairs],
        "SUPPLEMENTAL_RANDOM_GRAPHS": random_graphs(),
        "SUPPLEMENTAL_BINDING_CLASS_GRAPHS": random_graphs(
            BINDING_GRAPHS, RANDOM_SEED + 1, binding=True
        ),
        "EVIDENCE_KINDS": {
            "ANALYTIC_INEQUALITY": "CASE_LEMMA (K6 split by hub) and RANGE_ONLY_CHAINS",
            "COMPLETE_RELAXATION_ENUMERATION": "RELAXATION_MAXIMUM and INDEPENDENT_RECOUNT",
            "CONSTRUCTIVE_ATTAINMENT": "ATTAINED_BY_WITNESS (pinned validator, direct count)",
            "REALIZATION_SAMPLING": "SUPPLEMENTAL_*_GRAPHS only; never used as proof",
        },
        "ROUTE_B": route,
        "OLD_BOUND": OLD_BOUND,
        "NEW_T_CAP": PROPOSED_CAP,
        "NEW_T_CAP_EXACT": True,
        "CURSOR_BOUND": CURSOR_BOUND,
        "SUFFICIENT_CAP_FOR_CURSOR": route["CURSOR_SUFFICIENT_CAP"],
        "NEW_ADMISSIBLE_BOUND": new_bound,
        "OWNER_BOUND_REDUCTION": OLD_BOUND - new_bound,
        "BOUND_BELOW_CURSOR": new_bound < CURSOR_BOUND,
        "INCUMBENT": INCUMBENT,
        "OWNER_MARGIN_BELOW_INCUMBENT": INCUMBENT - new_bound,
        "OWNER_EXCLUSION_PROVED": new_bound < INCUMBENT,
        "TIED_PARTNER_UNCHANGED": TIED_PARTNER,
        "FAMILY_BOUND_GAIN_CLAIMED": 0,
        "NEW_WINNING_OUTCOMES": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "PRIOR_ART": PRIOR_ART,
        "FROZEN_LEDGER_MUTATED": "NO",
        "FAMILY_AUTHORITY_UPDATED": "NO",
        "HEAVY_SOLVER_STARTED": "NO",
        "SOLVER_CALLS": 0,
        "FIBER_MUTATION": "NONE",
        "PRODUCTION_MUTATION": "NONE",
    }


def main() -> None:
    result = compute_result()
    payload = render(result)
    if RESULT_PATH.exists():
        require(RESULT_PATH.read_bytes() == payload, "existing exact result differs")
    else:
        with RESULT_PATH.open("xb") as output:
            output.write(payload)
    keys = ("NEW_T_CAP", "NEW_ADMISSIBLE_BOUND", "OWNER_BOUND_REDUCTION")
    print(json.dumps({**{k: result[k] for k in keys}, "SHA256": sha256(payload)}))


if __name__ == "__main__":
    main()
