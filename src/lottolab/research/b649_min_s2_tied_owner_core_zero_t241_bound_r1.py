"""Core-zero cap T<=241 for the tied owner 66555555555531000000 under the seven-row authority.

Authority. The seven-row result (6569a966, tree 986d2085) names 66555555555531000000 as one
of three owners of its next competing level 313398248; the seventh step changed only
66555555555540000000, so this is the six-row ledger row. Its S4 base is the global profile
floor 112 (r28; the NB refinement asserts every catalog row uses it). The R32 Route-B
envelope is strictly increasing, reproduces 313398248 at cap 265 and not at cap 264, so the
recorded cap is 265, as R30's last refutation step for this profile also records. The
4,647-row ledger is not replayed and no row of it is changed.

Support model and premises (as in the T256 certificate). Twenty tickets of six labels; 22
triple and 27 pair supports; two tickets share at most one label, so G has 93 edges and
deg(v)=6+d_v. Here d=(6^2,5^10,3,1,0^6): core K={d>0}, k=14; zeros Z, z=6. Triples lie in
K, so a core x meets Z only through its 6-d_x pair labels: sigma_x<=6-d_x, i.e. 0 at d=6,
{0,1} at d=5, 0..3 at d=3 and 0..5 at d=1. A zero has six pair neighbours but only five
other zeros, so 1<=zeta_u<=6. r=sum sigma=sum zeta counts the K-Z edges.

Identity. H is the complement, |E(H)|=97. T=1140-18*97+901-t(H)=295-t(H); Goodman's
1140-1690/2 agrees. With M=H[K], MZ=H[Z], deg_M(x)=7-d_x+sigma_x, deg_MZ(u)=zeta_u-1, the
T256 certificate's mixed-triangle count gives
 t(H)=z|M|+k|MZ|-sum sigma*deg_M-sum zeta*deg_MZ+P,  P=t(M)+t(MZ)+sum_M c_Z+sum_MZ c_K>=0,
and z|M|+k|MZ|=3(32+sum sigma)+7(sum zeta-6). Hence, as a polynomial in (sigma, zeta),
 T = D - P,  D = 241 + sum_x sigma_x(sigma_x+4-d_x) + sum_u zeta_u(zeta_u-8),
which equals e44a635f's F (checked on 0, e_i, 2e_i and e_i+e_j, a unisolvent set for
quadratics). sigma(sigma+4-d) is 0 at d=6 and d=5, b(b+1) at d=3 and c(c+3) at d=1, so with
a=sum sigma over d=5: T = 241-8a-7b+b^2-5c+c^2+sum zeta^2-P.

One more necessary condition, the support count: the zeta_u core neighbours of u are
distinct and each has sigma>=1, so zeta_u <= s = a+[b>0]+[c>0].

Cap. The relaxation a in 0..10, b in 0..3, c in 0..5, sorted zeta in 1..min(6,s) with sum
zeta = a+b+c is finite, and every support structure of the profile maps into it. Its exact
maximum of D is 241, so T <= 241-P <= 241 for the whole profile. A labelled recount over
all 24,576 sigma vectors and every zeta multiset with e44's raw F agrees. The support count
is load-bearing: without it the maximum is 246, or 243 with parity (G[Z] has degrees
6-zeta_u, so r is even). Parity and Erdos-Gallai on G[Z] also hold but lower nothing once
the support count is used. Equality needs P=0; attainment is not asserted.

Closed form. (zeta-1)(zeta-6)<=0 on 1..6 gives zeta(zeta-8)<=-zeta-6, so
 T <= 205 - a + b^2 + c(c+2) - P <= 205+9+35 = 249
with no support count or enumeration. 249 is the largest cap whose Route-B bound does not
exceed the incumbent.

Route B. The R32 envelope at S4 base 112 is re-evaluated for 22<=T<=241 in both pinned
implementations and in exact rationals. It is a prefix of the cap-265 envelope and peaks at
T=241 with 313183160 (base-insensitive there: the K4 term is 170184). The other two tied
owners keep 313398248, so no family bound is claimed. Supplementally, one constructed
legal support structure and seeded random graphs that satisfy the graph premises are
recounted triangle by triangle; they are checks, never the proof. No solver or search runs.
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
from . import b649_min_s2_next_owner_core_zero_t256_cert_r1 as t256

three, two, split, r32, r5, chase = t256.three, t256.two, t256.split, t256.r32, t256.r5, t256.chase
require, sha256, render = two.require, two.sha256, two.render
integer, rows, text = two.integer, two.rows, two.text

TASK_ID = "B649_NEXT_TIED_OWNER_BOUNDED_BOUND_RESEARCH_R1"
FROZEN_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
FROZEN_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
FROZEN_RESULT = f"{two.RESULT_DIRECTORY}/{t256.RESULT_STEM}-result.json"
FROZEN_RESULT_SHA256 = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"
R30_RESULT = (
    f"{two.RESULT_DIRECTORY}/b649-k20-min-s2-current-cursor-dynamic-family-max-r30-result.json"
)
TARGET_PROFILE = "66555555555531000000"
TIED_OWNERS = ("66555555555531000000", "66655555554441000000", "66655555555422000000")
FAMILY_BOUND = 313_398_532
OLD_CAP = 265
OLD_BOUND = 313_398_248
S4_BASE = 112
CONSTANT = 241
PROPOSED_CAP = 241
CLOSED_FORM_CAP = 249
NEW_BOUND = 313_183_160
INCUMBENT = two.INCUMBENT
TICKET_CAPACITY = 6
OPTIONAL_PREMISES = frozenset({"PARITY", "SUPPORT_COUNT"})
THEOREM_PREMISES = ("SUPPORT_COUNT",)
RANDOM_SEED = 20_261_012
RANDOM_GRAPHS = 400
RESULT_STEM = "b649-min-s2-tied-owner-core-zero-t241-bound-r1"
ROOT = two.ROOT
RESULT_PATH = ROOT / two.RESULT_DIRECTORY / f"{RESULT_STEM}-result.json"
REUSED: tuple[ModuleType, ...] = (t256, three, two, split, r32, r5, r28, chase)
Pair = tuple[int, int]
Support = tuple[int, ...]
Term = tuple[int, int, int, int, int, int]
Point = tuple[int, int, int, tuple[int, ...]]

# Supplemental only: a legal support structure of the target profile (T=209), built by a
# seeded greedy constructor outside this module. It shows the premises are consistent.
REALIZATION_TRIPLES: tuple[Support, ...] = (
    (0, 1, 8), (0, 5, 10), (1, 2, 3), (6, 7, 9), (1, 4, 11), (2, 9, 11), (7, 8, 10),
    (0, 3, 6), (4, 5, 6), (0, 4, 9), (3, 10, 12), (5, 7, 11), (1, 7, 12), (2, 5, 8),
    (3, 4, 8), (1, 6, 10), (3, 9, 13), (0, 11, 12), (2, 4, 10), (6, 8, 11), (1, 5, 9),
    (0, 2, 7),
)  # fmt: skip
REALIZATION_PAIRS: tuple[Support, ...] = (
    (16, 18), (14, 15), (17, 19), (13, 18), (15, 17), (16, 19), (13, 14), (15, 19),
    (16, 17), (14, 18), (12, 19), (13, 16), (14, 17), (15, 18), (13, 15), (14, 16),
    (17, 18), (13, 19), (12, 17), (4, 14), (7, 18), (12, 16), (3, 19), (8, 9),
    (10, 11), (2, 6), (5, 15),
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
    """Profile split, edge counts and the complement constant, two independent ways."""
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
        (k, z, classes, sum(p)) == (14, 6, {6: 2, 5: 10, 3: 1, 1: 1}, 66)
        and sum(TICKET_CAPACITY + d for d in p) % 2 == 0
        and g_edges == 22 * 3 + 27 == 93
        and h_edges == 97
        and phi == goodman == 295
        and (m_base, mz_base, mixed) == (32, -6, 54)
        and phi - mixed == CONSTANT
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
    }


def sigma_ranges() -> dict[int, range]:
    """sigma_x <= 6-d_x: a core vertex reaches Z only through its pair labels."""
    return {d: range(TICKET_CAPACITY - d + 1) for d in sorted(set(core_degrees()), reverse=True)}


def zeta_range(support: int = TICKET_CAPACITY) -> range:
    """1 <= zeta_u: at most z-1=5 of a zero's six neighbours are zeros."""
    z = profile().count(0)
    return range(TICKET_CAPACITY - (z - 1), min(TICKET_CAPACITY, support) + 1)


def separable(core: Sequence[int], sigma: Sequence[int], zeta: Sequence[int]) -> int:
    """D = 241 + sum sigma(sigma+4-d) + sum zeta(zeta-8), so that T = D - P."""
    return (
        CONSTANT
        + sum(s * (s + 4 - d) for d, s in zip(core, sigma, strict=True))
        + sum(v * (v - 8) for v in zeta)
    )


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
    """D equals e44a635f's F as polynomials, and the per-class reductions hold."""
    p, core = profile(), core_degrees()
    points = quadratic_points(len(core), p.count(0))
    for sigma, zeta in points:
        require(
            three.split_objective(p, sigma, zeta) == separable(core, sigma, zeta),
            "D differs from e44's F",
        )
    closed = {6: lambda s: 0, 5: lambda s: 0, 3: lambda s: s * (s + 1), 1: lambda s: s * (s + 3)}
    tables = {
        d: {s: (s * (s + 4 - d), closed[d](s)) for s in values}
        for d, values in sigma_ranges().items()
    }
    require(
        all(lhs == rhs for t in tables.values() for lhs, rhs in t.values()),
        "per-class reduction fails on the legal range",
    )
    return {
        "T_COMPLEMENT": "295-t(H)",
        "T_CLOSED_FORM": "241+sum sigma(sigma+4-d)+sum zeta(zeta-8)-P",
        "T_CLASS_FORM": "241-8a-7b+b^2-5c+c^2+sum zeta^2-P",
        "P_DEFINITION": "t(M)+t(MZ)+sum_{xy in M}|N_G(x)&N_G(y)&Z|+sum_{uw in MZ}|N_G(u)&N_G(w)&K|",
        "P_NONNEGATIVE": "SUM_OF_FOUR_CARDINALITIES",
        "E44_IDENTITY_POINTS_CHECKED": len(points),
        "SIGMA_RANGES": {str(d): list(v) for d, v in sigma_ranges().items()},
        "ZETA_RANGE": list(zeta_range()),
        "CORE_TERMS": {
            str(d): {str(s): pair[0] for s, pair in t.items()} for d, t in tables.items()
        },
    }


def class_sigma(a: int, b: int, c: int) -> tuple[int, ...]:
    counts = Counter(core_degrees())
    return (0,) * counts[6] + (1,) * a + (0,) * (counts[5] - a) + (b,) + (c,)


def relaxation(
    premise_set: Collection[str] = THEOREM_PREMISES, *, erdos_gallai: bool = False
) -> Iterator[Point]:
    """Class-sorted (a, b, c) and sorted zeta over the legal ranges with equal sums."""
    require(set(premise_set) <= OPTIONAL_PREMISES, "unknown premise")
    ranges, counts = sigma_ranges(), Counter(core_degrees())
    z = profile().count(0)
    for a, b, c in product(range(counts[5] + 1), ranges[3], ranges[1]):
        r = a + b + c
        if "PARITY" in premise_set and (TICKET_CAPACITY * z - r) % 2:
            continue
        support = a + (b > 0) + (c > 0) if "SUPPORT_COUNT" in premise_set else TICKET_CAPACITY
        for zeta in combinations_with_replacement(zeta_range(support), z):
            if sum(zeta) != r:
                continue
            if erdos_gallai and not split.graphical([TICKET_CAPACITY - v for v in zeta]):
                continue
            yield a, b, c, tuple(sorted(zeta, reverse=True))


def relaxation_maximum(
    premise_set: Collection[str] = THEOREM_PREMISES, *, erdos_gallai: bool = False
) -> tuple[int, list[Point], int]:
    core = core_degrees()
    best: int | None = None
    top: list[Point] = []
    count = 0
    for a, b, c, zeta in relaxation(premise_set, erdos_gallai=erdos_gallai):
        f = separable(core, class_sigma(a, b, c), zeta)
        require(
            f == CONSTANT - 8 * a - 7 * b + b * b - 5 * c + c * c + sum(v * v for v in zeta),
            "class form differs from D",
        )
        count += 1
        if best is None or f > best:
            best, top = f, [(a, b, c, zeta)]
        elif f == best:
            top.append((a, b, c, zeta))
    require(best is not None, "empty relaxation")
    return int(best), top, count


def labelled_recount() -> dict[str, object]:
    """Independent: every labelled sigma and zeta multiset, e44's raw 2F, support count."""
    p, core = profile(), core_degrees()
    k, z = len(core), p.count(0)
    phi = sum(comb(13 - d, 2) for d in p) - 606
    core_best: dict[tuple[int, int], int] = {}
    vectors = 0
    for sigma in product(*(range(TICKET_CAPACITY - d + 1) for d in core)):
        vectors += 1
        h = [13 - z - d + s for d, s in zip(core, sigma, strict=True)]
        part = 2 * phi - z * sum(h) + 2 * sum(s * v for s, v in zip(sigma, h, strict=True))
        key = (sum(sigma), sum(1 for s in sigma if s))
        core_best[key] = max(core_best.get(key, part), part)
    zero_best: dict[tuple[int, int], int] = {}
    multisets = 0
    for zeta in combinations_with_replacement(range(TICKET_CAPACITY + 1), z):
        inner = [TICKET_CAPACITY - v for v in zeta]
        if any(not 0 <= v <= z - 1 for v in inner):
            continue
        multisets += 1
        a = [z - 7 + v for v in zeta]
        part = -k * sum(a) + 2 * sum(v * w for v, w in zip(zeta, a, strict=True))
        key = (sum(zeta), max(zeta))
        zero_best[key] = max(zero_best.get(key, part), part)
    best: int | None = None
    for (r, support), left in core_best.items():
        for (rz, top), right in zero_best.items():
            if rz == r and top <= support:
                require((left + right) % 2 == 0, "2F is odd on an equal-sum point")
                value = (left + right) // 2
                best = value if best is None else max(best, value)
    require(best is not None, "empty labelled recount")
    return {
        "METHOD": "LABELLED_SIGMA_X_ZETA_MULTISET_RAW_E44_F_INTEGER",
        "SIGMA_VECTORS": vectors,
        "ZETA_MULTISETS_IN_RANGE": multisets,
        "MAXIMUM": best,
    }


def closed_form_chain() -> dict[str, object]:
    """Per-coordinate chain T <= 205 - a + b^2 + c(c+2) - P <= 249, no enumeration."""
    z = profile().count(0)
    require(
        all(v * (v - 8) <= -v - 6 for v in zeta_range()), "zeta(zeta-8) <= -zeta-6 fails on 1..6"
    )
    # sum zeta = sum sigma, so -sum zeta moves onto the core: sigma(sigma+4-d) - sigma.
    terms = {d: {s: s * (s + 3 - d) for s in values} for d, values in sigma_ranges().items()}
    counts = Counter(core_degrees())
    bound = CONSTANT - 6 * z + sum(n * max(terms[d].values()) for d, n in counts.items())
    require(bound == CLOSED_FORM_CAP, "closed-form chain does not reduce to 249")
    return {
        "CHAIN": "T<=241+sum sigma(sigma+3-d)-36-P=205-a+b^2+c(c+2)-P<=249",
        "ZETA_INEQUALITY": "(zeta-1)(zeta-6)<=0 on 1..6",
        "CORE_TERMS": {str(d): {str(s): v for s, v in t.items()} for d, t in terms.items()},
        "CAP": bound,
        "USES": ["P>=0", "LEGAL_RANGES"],
    }


def theorem() -> dict[str, object]:
    """T <= 241 for every legal structure of the target profile, by the proof above."""
    facts, identity = premises(), identity_check()
    cap, top, count = relaxation_maximum()
    recount = labelled_recount()
    require(cap == PROPOSED_CAP == recount["MAXIMUM"], "relaxation maximum is not 241")
    ablation = {
        "NONE": relaxation_maximum(())[0],
        "PARITY_ONLY": relaxation_maximum(("PARITY",))[0],
        "SUPPORT_COUNT_ONLY": cap,
        "PARITY_AND_SUPPORT_COUNT": relaxation_maximum(OPTIONAL_PREMISES)[0],
        "ALL_PLUS_ERDOS_GALLAI_ON_Z": relaxation_maximum(OPTIONAL_PREMISES, erdos_gallai=True)[0],
    }
    require(
        ablation["NONE"] > ablation["PARITY_ONLY"] > cap
        and ablation["PARITY_AND_SUPPORT_COUNT"] == ablation["ALL_PLUS_ERDOS_GALLAI_ON_Z"] == cap,
        "premise ablation changed",
    )
    return {
        **facts,
        **identity,
        "THEOREM_PREMISES": ["P>=0", "LEGAL_RANGES", "SUPPORT_COUNT"],
        "SUPPORT_COUNT": "zeta_u<=s=a+[b>0]+[c>0]",
        "NOT_LOAD_BEARING": ["PARITY: r even", "ERDOS_GALLAI on degrees 6-zeta_u of G[Z]"],
        "RELAXATION_POINTS": count,
        "RELAXATION_MAXIMUM": cap,
        "RELAXATION_ARGMAX": [[a, b, c, list(zeta)] for a, b, c, zeta in top],
        "INDEPENDENT_RECOUNT": recount,
        "PREMISE_ABLATION": ablation,
        "CLOSED_FORM_CHAIN": closed_form_chain(),
        "TRIANGLE_CAP": cap,
        "EQUALITY_NEEDS": "P=0 at a RELAXATION_ARGMAX point",
        "ATTAINMENT": "NOT_ASSERTED",
        "STATUS": "PROVEN",
    }


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
    dc = [d[x] for x in core]
    r, p, t = sum(sigma), integer(seen["P"]), integer(seen["T_G"])
    support = sum(1 for s in sigma if s)
    require(
        all(len(nb[x]) == TICKET_CAPACITY + d[x] for x in core)
        and all(len(nb[u]) == TICKET_CAPACITY for u in zero)
        and all(0 <= s <= TICKET_CAPACITY - c for c, s in zip(dc, sigma, strict=True)),
        "graph violates the degree premises",
    )
    require(
        all(1 <= v <= min(TICKET_CAPACITY, support) for v in zeta)
        and r == sum(zeta)
        and r % 2 == 0
        and direct == t == 295 - integer(seen["T_H"])
        and t == separable(dc, sigma, zeta) - p
        and p >= 0
        and t <= PROPOSED_CAP,
        "graph violates the T241 chain",
    )
    return {"T": t, "D": separable(dc, sigma, zeta), "P": p, "R": r}


def realization_check() -> dict[str, object]:
    """The supplemental support structure is legal, of the target profile, and under 241."""
    d = three.legal_degrees(REALIZATION_TRIPLES, REALIZATION_PAIRS)
    r5.validate_k20_support_realization(REALIZATION_TRIPLES, REALIZATION_PAIRS, d)
    require(chase.profile_id(split.profile_values(d)) == TARGET_PROFILE, "wrong profile")
    g = {
        t256.edge(x, y)
        for s in (*REALIZATION_TRIPLES, *REALIZATION_PAIRS)
        for x, y in combinations(s, 2)
    }
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
        t_max, d_max = max(t_max, integer(seen["T"])), max(d_max, integer(seen["D"]))
    return {
        "ROLE": "SUPPLEMENTAL_FALSIFICATION_NOT_PROOF",
        "SEED": seed,
        "GRAPHS_CHECKED": checked,
        "ATTEMPTS": attempts,
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
        and threshold == CLOSED_FORM_CAP
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
        "STATUS": "PASS_INTEGER_AND_RATIONAL",
    }


def compute_result() -> dict[str, object]:
    sources = frozen_sources()
    recorded = frozen_row()
    proof = theorem()
    route = route_b_result()
    new_bound = integer(route["ALL_T_MAX_BOUND"])
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
        "OLD_BOUND": OLD_BOUND,
        "T_CAP_BEFORE": OLD_CAP,
        "S4_BASE": S4_BASE,
        "SUPPORT_MODEL": three.support_model(),
        "PROOF_SCOPE": "FULL_PROFILE",
        "EXACT_INEQUALITY": "T=241-8a-7b+b^2-5c+c^2+sum zeta^2-P<=241",
        "THEOREM_T241": proof,
        "SUPPLEMENTAL_REALIZATION": realization_check(),
        "SUPPLEMENTAL_RANDOM_GRAPHS": random_graphs(),
        "ROUTE_B": route,
        "NEW_T_CAP": PROPOSED_CAP,
        "NEW_ADMISSIBLE_BOUND": new_bound,
        "STRICT_OWNER_BOUND_REDUCTION": OLD_BOUND - new_bound,
        "INCUMBENT": INCUMBENT,
        "OWNER_MARGIN_BELOW_INCUMBENT": INCUMBENT - new_bound,
        "OTHER_TIED_OWNERS_UNCHANGED": [p for p in TIED_OWNERS if p != TARGET_PROFILE],
        "FAMILY_BOUND_REDUCTION_CLAIMED": "NO",
        "FROZEN_LEDGER_MUTATED": "NO",
        "NEW_WINNING_OUTCOMES": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
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
    keys = ("NEW_T_CAP", "NEW_ADMISSIBLE_BOUND", "STRICT_OWNER_BOUND_REDUCTION")
    print(json.dumps({**{k: result[k] for k in keys}, "SHA256": sha256(payload)}))


if __name__ == "__main__":
    main()
