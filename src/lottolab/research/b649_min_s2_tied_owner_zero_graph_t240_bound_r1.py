"""Zero-graph cap T<=240 for the tied owner 66655555554441000000 under the seven-row authority.

Authority. The seven-row result (6569a966, tree 986d2085) names 66655555554441000000 as one
of three owners of its next competing level 313398248; the seventh step changed only
66555555555540000000, so this is the six-row ledger row. Its S4 base is the global profile
floor 112 (r28). The R32 Route-B envelope is strictly increasing, reproduces 313398248 at
cap 265 and not at cap 264, and R30's refinement steps for this profile end at cap 265. The
4,647-row ledger is not replayed and no row of it is changed.

Support model and premises (as in the T256 certificate). Twenty tickets of six labels; 22
triple and 27 pair supports; two tickets share at most one label, so G has 93 edges and
deg(v)=6+d_v. T=t(G). Here d=(6^3,5^7,4^3,1,0^6): core K={d>0}, k=14; zeros Z, z=6.
Triples lie in K, so a core x meets Z only through its 6-d_x pair labels: sigma_x<=6-d_x,
i.e. 0 at d=6, {0,1} at d=5, {0,1,2} at d=4 and 0..5 at d=1. A zero u has six distinct
neighbours; its zero neighbours span the simple graph G[Z] on six vertices, with degree
g_u=6-zeta_u, where zeta_u counts its core neighbours. r=sum sigma=sum zeta=36-2e, e=|E(G[Z])|.

Identity. H is the complement, |E(H)|=97. T=1140-18*97+901-t(H)=295-t(H); Goodman's
1140-1690/2 agrees. With M=H[K], MZ=H[Z], deg_M(x)=7-d_x+sigma_x, deg_MZ(u)=zeta_u-1, the
T256 certificate's mixed-triangle count gives
 t(H)=z|M|+k|MZ|-sum sigma*deg_M-sum zeta*deg_MZ+P,  P=t(M)+t(MZ)+sum_M c_Z+sum_MZ c_K>=0,
and z|M|+k|MZ|=3(32+r)+7(r-6). Hence T=D-P with
 D = 241 + sum_x sigma_x(sigma_x+4-d_x) + sum_u zeta_u(zeta_u-8),
which equals e44a635f's F as a polynomial (checked on 0, e_i, 2e_i and e_i+e_j). With
zeta=6-g, zeta(zeta-8)=g(g-4)-12, so
 D = 169 + sum_x sigma_x(sigma_x+4-d_x) + sum_u g_u(g_u-4).
Per class sigma(sigma+4-d) is 0 at d=6 and d=5, sigma^2 at d=4 and c(c+3) at d=1 (c the
sigma of the d=1 vertex); so the core part is at most 3*4+40=52, and core minus r, which is
sum sigma(sigma+3-d), is at most 3*2+35=41.

Range-only chain. g(g-5)<=0 on 0..5 gives sum g(g-4)<=sum g=2e=36-r, so
T<=205+sum sigma(sigma+3-d)-P<=246. That already lies below the closure threshold 249, and
246 is also the exact maximum of the range-only relaxation, so ranges give no more.

Zero-graph lemma (the one ingredient). G[Z] is a simple graph on six vertices, so exactly
one case holds:
 (i)   some g_u=0: every other zero has g<=4, so sum g(g-4)<=0 and T<=169+52=221;
 (ii)  every g>=1 and G[Z]!=K6: a non-edge uw of G[Z] has g_u, g_w in 1..4, where
       g(g-5)<=-4, so sum g(g-4)<=2e-8=28-r and T<=197+41=238;
 (iii) G[Z]=K6: g=5 throughout, sum g(g-4)=30, e=15, r=6. If c=5 the d=4 sigmas sum to at
       most 1, so the core part is at most 1+40; otherwise it is at most 12+28. T<=240.
So T<=240-P<=240 for every legal support structure of the profile. Only P>=0, the legal
sigma ranges and the simplicity of G[Z] are used; no sampling or search.

Exactness and recount. The class-sorted relaxation (a sigma=1 count at d=5, a multiset at
d=4, c) against every degree sequence of a graph on six vertices, read off all 2^15
labelled graphs (the set equals the Erdos-Gallai set), with equal sums, peaks at exactly
240 at the unique point a=0, d=4 sigmas (1,0,0), c=5, G[Z]=K6. An independent recount
over all 20,736 labelled sigma vectors and all 32,768 labelled graphs on Z, through
e44's raw F, agrees. Premise ablation: ranges only 246; parity 241; support count 241;
zero graph 240, and parity or the support count add nothing to it. Equality needs P=0 at
that point; attainment is not asserted.

Route B. The R32 envelope at S4 base 112 is re-evaluated for 22<=T<=240 in both pinned
implementations and in exact rationals. It is a prefix of the cap-265 envelope and peaks at
T=240 with 313174392 (base-insensitive there: the K4 term is 164752). The other two tied
owners keep 313398248, so no family bound is claimed. Supplementally, two constructed
legal support structures (one in the binding K6 class at the argmax, with T=237, D=240,
P=3) and seeded random graphs that satisfy the graph premises are recounted triangle by
triangle; they are checks, never the proof. No solver or search runs.
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

TASK_ID = "B649_NEXT_TIED_OWNER_EXACT_BOUND_R1"
FROZEN_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
FROZEN_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
FROZEN_RESULT = f"{two.RESULT_DIRECTORY}/{t256.RESULT_STEM}-result.json"
FROZEN_RESULT_SHA256 = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"
R30_RESULT = (
    f"{two.RESULT_DIRECTORY}/b649-k20-min-s2-current-cursor-dynamic-family-max-r30-result.json"
)
TARGET_PROFILE = "66655555554441000000"
TIED_OWNERS = ("66555555555531000000", "66655555554441000000", "66655555555422000000")
FAMILY_BOUND = 313_398_532
OLD_CAP = 265
OLD_BOUND = 313_398_248
S4_BASE = 112
CONSTANT = 241
ZERO_GRAPH_CONSTANT = 169
PROPOSED_CAP = 240
RANGE_ONLY_CAP = 246
CLOSURE_THRESHOLD = 249
NEW_BOUND = 313_174_392
INCUMBENT = two.INCUMBENT
TICKET_CAPACITY = 6
ZERO_GRAPH = "ZERO_GRAPH"
OPTIONAL_PREMISES = frozenset({"PARITY", "SUPPORT_COUNT", ZERO_GRAPH})
THEOREM_PREMISES = (ZERO_GRAPH,)
CASE_CAPS = {"ISOLATED_ZERO": 221, "NO_ISOLATED_NOT_K6": 238, "K6": 240}
RANDOM_SEED = 20_261_012
RANDOM_GRAPHS = 400
RESULT_STEM = "b649-min-s2-tied-owner-zero-graph-t240-bound-r1"
ROOT = two.ROOT
RESULT_PATH = ROOT / two.RESULT_DIRECTORY / f"{RESULT_STEM}-result.json"
REUSED: tuple[ModuleType, ...] = (t256, three, two, split, r32, r5, r28, chase)
Pair = tuple[int, int]
Support = tuple[int, ...]
Term = tuple[int, int, int, int, int, int]
Point = tuple[int, tuple[int, ...], int, tuple[int, ...]]

# Recorded at task time from local refs; never read here, never relied on.
PRIOR_ART: dict[str, dict[str, object]] = {
    "BC_GOODMAN_CERT": {
        "COMMIT": "a441c6ab8000496f4d28d3bd656c41678976e913",
        "BRANCH": "codex/b649-min-s2-tied-owners-bc-goodman-cert-r1",
        "BASE": "8d2411474c721264697438428b09a2ff00ea6802 (T248 eight-row, after this authority)",
        "CLAIMED_CAP_FOR_TARGET": 239,
        "CLAIMED_BOUND_FOR_TARGET": 313_165_236,
        "STATUS": "LOCAL_UNPUSHED_PENDING_FRESH_JUDGE",
        "USE": "NOT_RELIED_ON_NOT_READ_BY_THIS_MODULE",
    },
    "SIBLING_T241_CERT": {
        "COMMIT": "8c6e7bdd355cfee990e2d832be5f1e979640633d",
        "PROFILE": "66555555555531000000",
        "USE": "OTHER_PROFILE_NOT_IMPORTED",
    },
}

# Supplemental only: a legal support structure of the target profile, built by a seeded
# greedy constructor outside this module (seed 630). It shows the premises are consistent.
REALIZATION_TRIPLES: tuple[Support, ...] = (
    (0, 1, 2), (1, 7, 9), (2, 3, 6), (0, 5, 8), (4, 5, 10), (0, 7, 12), (3, 4, 8),
    (6, 9, 11), (2, 10, 12), (1, 4, 11), (2, 5, 9), (3, 7, 10), (1, 6, 8), (0, 4, 9),
    (2, 8, 11), (5, 6, 7), (0, 3, 11), (1, 12, 13), (2, 4, 7), (0, 6, 10), (1, 3, 5),
    (8, 9, 12),
)  # fmt: skip
REALIZATION_PAIRS: tuple[Support, ...] = (
    (14, 17), (16, 19), (15, 18), (13, 15), (16, 17), (14, 19), (17, 18), (13, 19),
    (14, 15), (16, 18), (14, 16), (17, 19), (10, 15), (13, 18), (11, 14), (18, 19),
    (15, 16), (12, 17), (13, 16), (5, 12), (11, 13), (10, 19), (8, 17), (7, 14),
    (3, 15), (4, 6), (9, 18),
)  # fmt: skip
# Supplemental only: a legal structure in the binding case G[Z]=K6 at the relaxation argmax
# (a=0, d=4 sigmas (1,0,0), c=5), from a seeded constructor outside this module (seed
# 83061); its T=237 shows the cap is within 3 of a realized value. Not a proof of anything.
K6_TRIPLES: tuple[Support, ...] = (
    (0, 1, 2), (0, 3, 6), (5, 7, 9), (1, 4, 8), (2, 3, 10), (4, 6, 9), (2, 7, 8),
    (0, 11, 12), (1, 5, 11), (5, 6, 8), (1, 10, 12), (0, 4, 7), (2, 9, 11), (1, 3, 9),
    (0, 5, 10), (3, 8, 12), (2, 6, 12), (7, 10, 13), (2, 4, 5), (3, 4, 11), (0, 8, 9),
    (1, 6, 7),
)  # fmt: skip
K6_PAIRS: tuple[Support, ...] = (
    (14, 15), (14, 16), (14, 17), (14, 18), (14, 19), (15, 16), (15, 17), (15, 18),
    (15, 19), (16, 17), (16, 18), (16, 19), (17, 18), (17, 19), (18, 19), (13, 18),
    (13, 14), (13, 17), (13, 16), (13, 19), (12, 15), (4, 10), (9, 12), (7, 11),
    (8, 10), (3, 5), (6, 11),
)  # fmt: skip


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
    """The target row as the frozen results record it, without a ledger replay."""
    raw = (ROOT / FROZEN_RESULT).read_bytes()
    require(sha256(raw) == FROZEN_RESULT_SHA256, "frozen seven-row result digest mismatch")
    seven = two.object_row(json.loads(raw))
    six_raw = (ROOT / t256.SIX_RESULT_PATH).read_bytes()
    require(sha256(six_raw) == t256.SIX_RESULT_SHA256, "six-row result digest mismatch")
    six_bounds = two.object_row(two.object_row(json.loads(six_raw))["RESOLVED_ROW_BOUNDS"])
    require(
        seven["TASK_ID"] == t256.TASK_ID
        and seven["FAMILY_BOUND_AFTER"] == FAMILY_BOUND
        and seven["NEXT_COMPETING_BOUND"] == OLD_BOUND
        and rows(seven["NEXT_COMPETING_OWNER_IDS"]) == list(TIED_OWNERS)
        and rows(seven["ROWS_CHANGED_FROM_SIX_ROW"]) == [t256.TARGET_PROFILE]
        and seven["SIX_ROW_RESULT_SHA256"] == t256.SIX_RESULT_SHA256
        and seven["INCUMBENT"] == INCUMBENT
        and seven["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
        and all(six_bounds[p] == OLD_BOUND for p in TIED_OWNERS),
        "frozen authority does not record the target at the tied level",
    )
    r30 = two.object_row(json.loads((ROOT / R30_RESULT).read_bytes()))
    steps = [
        two.object_row(s)
        for s in rows(r30["REFINEMENT_STEPS"])
        if two.object_row(s).get("PROFILE_ID") == TARGET_PROFILE
    ]
    r30_caps = [integer(s["TRIANGLE_CAP"]) for s in steps]
    require(r30_caps == [267, 266, OLD_CAP], "R30 cap history for the target changed")
    return {
        "SEVEN_ROW_FAMILY_BOUND": seven["FAMILY_BOUND_AFTER"],
        "SEVEN_ROW_NEXT_COMPETING_BOUND": seven["NEXT_COMPETING_BOUND"],
        "SEVEN_ROW_NEXT_COMPETING_OWNER_IDS": list(TIED_OWNERS),
        "SIX_ROW_RESOLVED_BOUND": six_bounds[TARGET_PROFILE],
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
        (k, z, classes, sum(p), sum(d * d for d in p)) == (14, 6, {6: 3, 5: 7, 4: 3, 1: 1}, 66, 332)
        and sum(TICKET_CAPACITY + d for d in p) % 2 == 0
        and g_edges == 22 * 3 + 27 == 93
        and h_edges == 97
        and phi == goodman == 295
        and (m_base, mz_base, mixed) == (32, -6, 54)
        and phi - mixed == CONSTANT
        and CONSTANT - z * 12 == ZERO_GRAPH_CONSTANT
        and z - 1 < TICKET_CAPACITY,
        "core-zero premises fail",
    )
    return {
        "PROFILE_ID": TARGET_PROFILE,
        "CORE_VERTICES": k,
        "ZERO_VERTICES": z,
        "CORE_DEGREE_CLASSES": {str(d): n for d, n in classes.items()},
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
    """D = 241 + sum sigma(sigma+4-d) + sum zeta(zeta-8), so that T = D - P."""
    return CONSTANT + core_part(core, sigma) + sum(v * (v - 8) for v in zeta)


def zero_graph_form(core: Sequence[int], sigma: Sequence[int], g: Sequence[int]) -> int:
    """The same D in the G[Z] degrees g = 6 - zeta: 169 + core part + sum g(g-4)."""
    return ZERO_GRAPH_CONSTANT + core_part(core, sigma) + sum(v * (v - 4) for v in g)


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
        "T_COMPLEMENT": "295-t(H)",
        "T_CLOSED_FORM": "241+sum sigma(sigma+4-d)+sum zeta(zeta-8)-P",
        "T_ZERO_GRAPH_FORM": "169+sum sigma(sigma+4-d)+sum g(g-4)-P, g=6-zeta=deg_G[Z]",
        "T_CLASS_FORM": "169+sum_{d=4} sigma^2+c(c+3)+sum g(g-4)-P",
        "P_DEFINITION": "t(M)+t(MZ)+sum_{xy in M}|N_G(x)&N_G(y)&Z|+sum_{uw in MZ}|N_G(u)&N_G(w)&K|",
        "P_NONNEGATIVE": "SUM_OF_FOUR_CARDINALITIES",
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
    """Class-sorted sigma: a d=5 vertices at 1, a multiset at d=4, c at d=1."""
    counts, ranges = Counter(core_degrees()), sigma_ranges()
    for a, b, c in product(
        range(counts[5] + 1), combinations_with_replacement(ranges[4], counts[4]), ranges[1]
    ):
        yield a, tuple(sorted(b, reverse=True)), c


def zero_graph_lemma() -> dict[str, object]:
    """The three-case bound, each inequality checked on its whole finite domain."""
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
    core_values = [
        (a + sum(b) + c, core_part(core, class_sigma(a, b, c))) for a, b, c in core_classes()
    ]
    core_max = max(v for _, v in core_values)
    core_minus_r = max(v - r for r, v in core_values)
    core_at_six = max(v for r, v in core_values if r == 6)
    caps = {
        "ISOLATED_ZERO": ZERO_GRAPH_CONSTANT + core_max + max(cases["ISOLATED_ZERO"]),
        "NO_ISOLATED_NOT_K6": ZERO_GRAPH_CONSTANT
        + 36
        + core_minus_r
        + max(cases["NO_ISOLATED_NOT_K6"]),
        "K6": ZERO_GRAPH_CONSTANT + core_at_six + max(cases["K6"]),
    }
    require(
        (core_max, core_minus_r, core_at_six) == (52, 41, 41)
        and len(cases["K6"]) == 1
        and max(cases["ISOLATED_ZERO"]) == 0
        and max(cases["NO_ISOLATED_NOT_K6"]) == -8
        and caps == CASE_CAPS,
        "zero-graph lemma constants changed",
    )
    core_by_r: dict[int, int] = {}
    for r, v in core_values:
        core_by_r[r] = max(core_by_r.get(r, v), v)
    table = [
        {
            "E": e,
            "R": 36 - 2 * e,
            "MAX_SUM_G_G_MINUS_4": by_edges[e],
            "MAX_CORE_PART": core_by_r.get(36 - 2 * e),
            "MAX_D": None
            if 36 - 2 * e not in core_by_r
            else ZERO_GRAPH_CONSTANT + core_by_r[36 - 2 * e] + by_edges[e],
        }
        for e in sorted(by_edges)
    ]
    exact = max(integer(row["MAX_D"]) for row in table if row["MAX_D"] is not None)
    require(exact == max(caps.values()) == PROPOSED_CAP, "edge-count table does not peak at 240")
    return {
        "CASES": {
            "ISOLATED_ZERO": "sum g(g-4)<=0; T<=169+52=221",
            "NO_ISOLATED_NOT_K6": "sum g(g-4)<=2e-8=28-r; T<=197+41=238",
            "K6": "e=15, r=6, sum g(g-4)=30, core<=41; T<=240",
        },
        "CASE_GRAPH_COUNTS": {k: len(v) for k, v in cases.items()},
        "CASE_CAPS": caps,
        "CORE_PART_MAX": core_max,
        "CORE_MINUS_R_MAX": core_minus_r,
        "CORE_PART_MAX_AT_R6": core_at_six,
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
    core = core_degrees()
    best: int | None = None
    top: list[Point] = []
    count = 0
    for a, b, c, zeta in relaxation(premise_set):
        sigma = class_sigma(a, b, c)
        f = separable(core, sigma, zeta)
        require(
            f
            == ZERO_GRAPH_CONSTANT
            + sum(v * v for v in b)
            + c * (c + 3)
            + sum((6 - v) * (2 - v) for v in zeta)
            and f == zero_graph_form(core, sigma, [TICKET_CAPACITY - v for v in zeta]),
            "class form differs from D",
        )
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
    core_best: dict[int, tuple[int, tuple[int, ...]]] = {}
    vectors = 0
    for sigma in product(*(range(TICKET_CAPACITY - d + 1) for d in core)):
        vectors += 1
        h = [13 - z - d + s for d, s in zip(core, sigma, strict=True)]
        part = 2 * phi - z * sum(h) + 2 * sum(s * v for s, v in zip(sigma, h, strict=True))
        r = sum(sigma)
        if r not in core_best or part > core_best[r][0]:
            core_best[r] = (part, sigma)
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
        (left, sigma), (right, zeta) = core_best[r], zero_best[r]
        require((left + right) % 2 == 0, "2F is odd on an equal-sum point")
        value = (left + right) // 2
        require(three.split_objective(p, sigma, zeta) == value, "split halves differ from F")
        best = value if best is None else max(best, value)
    require(best is not None, "empty labelled recount")
    return {
        "METHOD": "LABELLED_SIGMA_X_LABELLED_ZERO_GRAPH_RAW_E44_F_INTEGER",
        "SIGMA_VECTORS": vectors,
        "ZERO_GRAPHS": graphs,
        "COMMON_R_VALUES": sorted(core_best.keys() & zero_best.keys()),
        "MAXIMUM": best,
    }


def closed_form_chain() -> dict[str, object]:
    """Range-only: sum g(g-4) <= 2e = 36-r gives T <= 205 + sum sigma(sigma+3-d) <= 246."""
    require(all(g * (g - 4) <= g for g in range(TICKET_CAPACITY)), "g(g-4)<=g fails on 0..5")
    terms = {d: {s: s * (s + 3 - d) for s in values} for d, values in sigma_ranges().items()}
    counts = Counter(core_degrees())
    z = profile().count(0)
    bound = (
        ZERO_GRAPH_CONSTANT
        + TICKET_CAPACITY * z
        + sum(n * max(terms[d].values()) for d, n in counts.items())
    )
    require(bound == RANGE_ONLY_CAP, "closed-form chain does not reduce to 246")
    return {
        "CHAIN": "T<=169+sum sigma(sigma+4-d)+(36-r)-P=205+sum sigma(sigma+3-d)-P<=246",
        "ZERO_INEQUALITY": "g(g-5)<=0 on 0..5",
        "CORE_TERMS": {str(d): {str(s): v for s, v in t.items()} for d, t in terms.items()},
        "CAP": bound,
        "USES": ["P>=0", "LEGAL_RANGES"],
        "BELOW_CLOSURE_THRESHOLD": bound <= CLOSURE_THRESHOLD,
    }


def theorem() -> dict[str, object]:
    """T <= 240 for every legal structure of the target profile, by the proof above."""
    facts, identity = premises(), identity_check()
    lemma = zero_graph_lemma()
    cap, top, count = relaxation_maximum()
    recount = labelled_recount()
    require(
        cap == PROPOSED_CAP == recount["MAXIMUM"] == lemma["CAP"], "relaxation maximum is not 240"
    )
    ablation = {
        "NONE": relaxation_maximum(())[0],
        "PARITY_ONLY": relaxation_maximum(("PARITY",))[0],
        "SUPPORT_COUNT_ONLY": relaxation_maximum(("SUPPORT_COUNT",))[0],
        "PARITY_AND_SUPPORT_COUNT": relaxation_maximum(("PARITY", "SUPPORT_COUNT"))[0],
        "ZERO_GRAPH_ONLY": cap,
        "ALL_THREE": relaxation_maximum(OPTIONAL_PREMISES)[0],
    }
    require(
        ablation["NONE"] == RANGE_ONLY_CAP
        and min(ablation["PARITY_ONLY"], ablation["SUPPORT_COUNT_ONLY"]) > cap
        and ablation["PARITY_AND_SUPPORT_COUNT"] > cap
        and ablation["ALL_THREE"] == cap,
        "premise ablation changed",
    )
    return {
        **facts,
        **identity,
        "THEOREM_PREMISES": ["P>=0", "LEGAL_RANGES", "ZERO_GRAPH: G[Z] is a simple graph"],
        "NOT_LOAD_BEARING": ["PARITY: r even", "SUPPORT_COUNT: zeta_u<=#{sigma>0}"],
        "ZERO_GRAPH_LEMMA": lemma,
        "GRAPH_DEGREE_SEQUENCES": len(graph_degree_sequences()),
        "RELAXATION_POINTS": count,
        "RELAXATION_MAXIMUM": cap,
        "RELAXATION_ARGMAX": [[a, list(b), c, list(zeta)] for a, b, c, zeta in top],
        "INDEPENDENT_RECOUNT": recount,
        "PREMISE_ABLATION": ablation,
        "RANGE_ONLY_CHAIN": closed_form_chain(),
        "TRIANGLE_CAP": cap,
        "EQUALITY_NEEDS": "P=0 at the RELAXATION_ARGMAX point",
        "ATTAINMENT": "NOT_ASSERTED",
        "STATUS": "PROVEN",
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
    """One graph obeying the graph premises: direct recount of T, P and every condition."""
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
    require(
        all(len(nb[x]) == TICKET_CAPACITY + d[x] for x in core)
        and all(len(nb[u]) == TICKET_CAPACITY for u in zero)
        and all(0 <= s <= TICKET_CAPACITY - c for c, s in zip(dc, sigma, strict=True)),
        "graph violates the degree premises",
    )
    value = separable(dc, sigma, zeta)
    require(
        inner == [TICKET_CAPACITY - v for v in zeta]
        and sum(sigma) == sum(zeta) == 36 - sum(inner)
        and direct == t == 295 - integer(seen["T_H"])
        and value == zero_graph_form(dc, sigma, inner)
        and t == value - p
        and p >= 0
        and value <= case_cap(inner) <= PROPOSED_CAP,
        "graph violates the T240 chain",
    )
    return {"T": t, "D": value, "P": p, "R": sum(sigma), "CASE_CAP": case_cap(inner)}


def realization_check(
    triples: Sequence[Support] | None = None, pairs: Sequence[Support] | None = None
) -> dict[str, object]:
    """A supplemental support structure is legal, of the target profile, and under 240."""
    triples = REALIZATION_TRIPLES if triples is None else triples
    pairs = REALIZATION_PAIRS if pairs is None else pairs
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


def random_graphs(count: int = RANDOM_GRAPHS, seed: int = RANDOM_SEED) -> dict[str, object]:
    """Seeded graphs with deg 6+d, zero degree 6 and sigma<=6-d: falsification only."""
    rng = random.Random(seed)
    core_d = core_degrees()
    core, zero = list(range(len(core_d))), list(range(len(core_d), 20))
    d = dict(enumerate([*core_d, *(0 for _ in zero)]))
    checked, attempts, t_max, d_max = 0, 0, 0, 0
    cases: Counter[int] = Counter()
    while checked < count:
        attempts += 1
        require(attempts <= 50 * count, "random graph generator stalled")
        cross: set[Pair] = set()
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
        checked += 1
        cases[integer(seen["CASE_CAP"])] += 1
        t_max, d_max = max(t_max, integer(seen["T"])), max(d_max, integer(seen["D"]))
    return {
        "ROLE": "SUPPLEMENTAL_FALSIFICATION_NOT_PROOF",
        "SEED": seed,
        "GRAPHS_CHECKED": checked,
        "ATTEMPTS": attempts,
        "CASE_CAP_COUNTS": {str(k): v for k, v in sorted(cases.items())},
        "MAX_T": t_max,
        "MAX_D": d_max,
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
    below = [t for t, bound, *_ in old_terms if bound <= INCUMBENT]
    threshold = max(below)
    peak = max(new_terms, key=lambda term: (term[1], term[0]))
    require(
        old_bound == OLD_BOUND
        and route_b(OLD_CAP - 1)[1] < OLD_BOUND
        and all(x[1] < y[1] for x, y in pairwise(old_terms))
        and new_terms == old_terms[: len(new_terms)]
        and new_bound == NEW_BOUND == peak[1]
        and peak[0] == PROPOSED_CAP
        and route_b(PROPOSED_CAP, 0)[1] == new_bound
        and threshold == CLOSURE_THRESHOLD
        and below == list(range(22, threshold + 1)),
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
        "CAP_AFTER": PROPOSED_CAP,
        "TERM_COUNT": len(new_terms),
        "ALL_T_TERMS": [list(t) for t in new_terms],
        "ARGMAX_TERM": list(peak),
        "ALL_T_MAX_BOUND": new_bound,
        "PREFIX_OF_CAP_265_ENVELOPE": True,
        "CLOSURE_THRESHOLD_CAP": threshold,
        "BOUND_AT_CLOSURE_THRESHOLD": old_terms[threshold - 22][1],
        "BOUND_AT_CLOSURE_THRESHOLD_PLUS_ONE": old_terms[threshold - 21][1],
        "BOUND_AT_RANGE_ONLY_CAP": old_terms[RANGE_ONLY_CAP - 22][1],
        "STATUS": "PASS_INTEGER_AND_RATIONAL",
    }


def compute_result() -> dict[str, object]:
    sources = frozen_sources()
    recorded = frozen_row()
    proof = theorem()
    route = route_b_result()
    new_bound = integer(route["ALL_T_MAX_BOUND"])
    lemma = two.object_row(proof["ZERO_GRAPH_LEMMA"])
    recount = two.object_row(proof["INDEPENDENT_RECOUNT"])
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "STRICT_OWNER_BOUND_REDUCTION_PROVED",
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
        "SOURCE_PROFILE_BOUND": OLD_BOUND,
        "SOURCE_T_CAP": OLD_CAP,
        "SOURCE_S4_BASE": S4_BASE,
        "SUPPORT_MODEL": three.support_model(),
        "PROOF_SCOPE": "FULL_PROFILE",
        "EXACT_IDENTITY": "T=169+sum_{d=4} sigma^2+c(c+3)+sum_u g_u(g_u-4)-P, P>=0",
        "LOAD_BEARING_PREMISES": ["P>=0", "LEGAL_RANGES", "ZERO_GRAPH"],
        "COMBINATORIAL_BOUND": lemma["CASES"],
        "INTEGER_ROUNDING": "every Route-B term rechecked: integer K4 ceil, A_MAX floor, "
        "exact-rational bound with 0<=bound-exact<1",
        "RELAXATION_COMPLETENESS": "class-sorted sigma x all graph degree sequences on Z "
        f"({proof['RELAXATION_POINTS']} points); every legal structure maps into it",
        "INDEPENDENT_RECOUNT": f"{recount['SIGMA_VECTORS']} labelled sigma x "
        f"{recount['ZERO_GRAPHS']} labelled G[Z], raw e44 F max {recount['MAXIMUM']}",
        "NEGATIVE_CASES": {
            "PREMISE_ABLATION_CAPS": proof["PREMISE_ABLATION"],
            "SUPPORT_COUNT_ARGMAX": "zeta (6,6,1,1,1,1): G[Z] degrees (0,0,5,5,5,5), not graphic",
            "CLAIMED_CAP_239": "REFUTED_BY_RELAXATION_POINT_WITH_D_240",
            "WRONG_CONSTANT": "REFUTED_BY_E44_IDENTITY",
            "ROUTE_B_PLUS_MINUS_ONE": "REFUTED_BY_EXACT_ARITHMETIC",
        },
        "COUNTEREXAMPLE_STATUS": "NONE: every checked graph has T=D-P<=its case cap<=240",
        "THEOREM_T240": proof,
        "SUPPLEMENTAL_REALIZATION": realization_check(),
        "SUPPLEMENTAL_K6_CASE_REALIZATION": realization_check(K6_TRIPLES, K6_PAIRS),
        "SUPPLEMENTAL_RANDOM_GRAPHS": random_graphs(),
        "EVIDENCE_KINDS": {
            "ANALYTIC_INEQUALITY": "ZERO_GRAPH_LEMMA (three cases) and RANGE_ONLY_CHAIN",
            "COMPLETE_RELAXATION_ENUMERATION": "RELAXATION_MAXIMUM and INDEPENDENT_RECOUNT",
            "REALIZATION_SAMPLING": "SUPPLEMENTAL_* only; never used as proof",
        },
        "ROUTE_B": route,
        "OLD_BOUND": OLD_BOUND,
        "NEW_T_CAP": PROPOSED_CAP,
        "NEW_ADMISSIBLE_BOUND": new_bound,
        "STRICT_OWNER_BOUND_DELTA": OLD_BOUND - new_bound,
        "INCUMBENT": INCUMBENT,
        "OWNER_MARGIN_BELOW_INCUMBENT": INCUMBENT - new_bound,
        "OWNER_EXCLUSION_PROVED": new_bound < INCUMBENT,
        "OTHER_TIED_OWNERS_UNCHANGED": [p for p in TIED_OWNERS if p != TARGET_PROFILE],
        "FAMILY_BOUND_DELTA_CLAIMED": 0,
        "NEW_STRICT_WINNING_OUTCOMES": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "PRIOR_ART": PRIOR_ART,
        "FROZEN_LEDGER_MUTATED": "NO",
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
    keys = ("NEW_T_CAP", "NEW_ADMISSIBLE_BOUND", "STRICT_OWNER_BOUND_DELTA")
    print(json.dumps({**{k: result[k] for k in keys}, "SHA256": sha256(payload)}))


if __name__ == "__main__":
    main()
