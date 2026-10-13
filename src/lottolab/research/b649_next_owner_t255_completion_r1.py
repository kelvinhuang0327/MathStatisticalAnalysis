"""Exact core-zero cap T<=255 for 65555555555550000000 on the frozen seven-row authority.

Support model (r5 at 6569a966). Twenty tickets carry six labels each: 22 labels have
triple supports and 27 have pair supports. Every 2-subset of every support is distinct,
so two tickets share at most one label, G (shadow plus pairs) has 66+27=93 edges and
deg(v)=2d_v+(6-d_v)=6+d_v, where d_v counts the triples through v. T=t(G), the 22 support
triangles included.

Premises. d=(6,5^12,0^7): sum d=66, core K={d>0} with k=13, zeros Z with z=7. A triple
through a zero would give it d>0, so all 22 triples lie in K and a core x reaches Z only
through its 6-d_x pair labels: sigma_x=|N_G(x)&Z|<=6-d_x, i.e. 0 at the hub (d=6) and
{0,1} at d=5. A zero has degree 6, so 0<=zeta_u=|N_G(u)&K|<=6. Both sums count the K-Z
edges of G: r=sum sigma=sum zeta.

Complement. H is the complement: |E(H)|=190-93=97, deg_H=13-d. Counting vertex triples
by their H-edges gives t(G)=C(20,3)-18|E(H)|+sum C(13-d,2)-t(H)=1140-1746+903-t(H)
=297-t(H). Goodman's C(20,3)-sum deg_G*deg_H/2=1140-843 agrees. The constant is
re-derived here: the T256 row has 298 and the T257 row 299.

Remainder. Put M=H[K], MZ=H[Z]: deg_M(x)=h_x=12-(6+d_x-sigma_x)=6-d_x+sigma_x and
deg_MZ(u)=6-(6-zeta_u)=zeta_u. An H triangle lies in K, lies in Z, or has exactly one
same-part edge. Over an M edge xy its Z apices number z-sigma_x-sigma_y+c_Z(xy),
c_Z(xy)=|N_G(x)&N_G(y)&Z|; over an MZ edge uw its K apices number
k-zeta_u-zeta_w+c_K(uw). Summing,
 t(H)=z|M|+k|MZ|-sum sigma*h-sum zeta^2+P,  P=t(M)+t(MZ)+sum_M c_Z+sum_MZ c_K.
P is a sum of four cardinalities, so P>=0. Sum h=12+r, so |M|=(12+r)/2, |MZ|=r/2 and
z|M|+k|MZ|=42+10r. Per coordinate sigma*h is 0 at the hub and sigma(1+sigma)=2sigma on
{0,1}, so sum sigma*h=2r. Hence
 t(H)=42+8r-sum zeta^2+P  and  T=255-8r+sum zeta^2-P.

Cap. zeta^2<=6zeta on {0..6}, so
 T<=255-8r+6r-P=255-2r-P<=255
for every legal support structure of the profile. No graphicality, sampling or
enumeration is used. Separable form: -8r=-2 sum sigma-6 sum zeta, so
T+P=255+sum sigma(sigma+2-d)+sum zeta(zeta-6), and every coordinate term is <=0 on its
legal range. Equality needs r=0 (the -2r term) and P=0. Conversely r=0 makes every zeta
0, MZ empty and M the perfect matching {h=1} on the twelve d=5 tickets, so P=0 and T=255:
T=255 exactly when r=0.

Attainment (separate from the proof). Hub triples {0,2i-1,2i}; 16 triples on 1..12 that
pack K12 minus the hub matching minus the 12-cycle L=1-3-5-7-9-11-2-4-6-8-10-12; the six
alternate L edges as core pair labels; K7 on the zeros. The r5 validator accepts it, r=0
and its directly counted T is 255, so 255 is the exact profile maximum.

Route B. The frozen R32 envelope at the row's S4 base 1680 is recounted from scratch
(S1, S2, the S3 path/pure/support weights, the K4 ceiling, the A_MAX floor) and must equal
the r32 and e44 implementations term by term, with every bound equal to the ceiling of its
exact rational value. The terms increase strictly in T, so each cap's envelope peaks at
the cap. Cap 264 reproduces the recorded row bound 313396120; the 234 terms for
22<=T<=255 peak at T=255 with bound 313315656 (K4 420, A_MAX 200, S4 238980, S3 5062176).
Strict reduction needs cap<=263, the cursor 313394584 needs cap<=263, and the incumbent
313263888 needs cap<=249.

Ledger. 6569a966 is pinned by tree and by the seven-row result digest. The six-row
replay (83ddad7a pins) plus the sealed seventh update must reproduce the frozen
seven-row ledger digest for digest; the target row is read from it, unchanged. Nothing
is installed: no family gain is claimed. Global K20 optimality is unknown. No solver or
search is run.
"""

from __future__ import annotations

import json
import resource
import sys
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from fractions import Fraction
from itertools import combinations, combinations_with_replacement, pairwise
from math import comb
from pathlib import Path
from time import process_time

from . import b649_min_s2_next_owner_core_zero_t256_cert_r1 as t256

TASK_ID = "B649_NEXT_OWNER_T255_COMPLETION_R1"
FROZEN_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
FROZEN_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
FROZEN_RESULT_SHA256 = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"
TARGET_PROFILE = "65555555555550000000"
SOURCE_BOUND = 313_396_120
SOURCE_CAP = 264
SOURCE_S4_BASE = 1_680
SOURCE_ROW = "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:NB_CERTIFICATES[1613]"
GOODMAN_CONSTANT = 297
PROVED_CAP = 255
TICKETS = 20
TICKET_CAPACITY = 6
CORE_TERM_CONSTANT = 2
ZERO_TERM_CONSTANT = 6
SUPERSET_COUNT = 201
E44_GRAPHICAL_COUNT = 49
CPU_LIMIT_SECONDS = 120
RESULT_STEM = "b649-next-owner-t255-completion-r1"
# The interrupted draft this task completes. It is read, never imported or trusted.
DONOR_DRAFT = {
    "BRANCH": "codex/b649-next-active-owner-65555555555550000000-r1",
    "PATH": "src/lottolab/research/b649_next_active_owner_65555555555550000000_r1.py",
    "GIT_STATE": "UNTRACKED_UNCOMMITTED",
    "SHA256": "f0857ee60865d5a48ff7283712fa1a1d9f0b09358ba9a9b0f3141cefe3891419",
    "ROLE": "REVIEWED_INPUT_NOT_AUTHORITY",
    "DEFECTS_FIXED": [
        "ROUTE_B_SCAN_TO_T297_EXCEEDS_WEDGE_LIMIT_T277_AND_RAISES",
        "SUPERSET_COUNT_1027_WRONG_ACTUAL_201",
        "RECORDED_ROW_TRIANGLES_189_WRONG_ACTUAL_193",
    ],
}
three, six, two, chase = t256.three, t256.six, t256.two, t256.chase
split, r32, r5 = t256.split, t256.r32, t256.r5
ROOT = two.ROOT
RESULT_PATH = ROOT / two.RESULT_DIRECTORY / f"{RESULT_STEM}-result.json"
SEVEN_RESULT_PATH = f"{two.RESULT_DIRECTORY}/{t256.RESULT_STEM}-result.json"
require, sha256 = two.require, two.sha256
integer, object_row, rows, text = two.integer, two.object_row, two.rows, two.text
INCUMBENT = two.INCUMBENT
CURSOR_ID, CURSOR_BOUND = chase.prior.CURSOR_ID, chase.prior.CURSOR_BOUND
Row = chase.Row
Pair = tuple[int, int]
Support = tuple[int, ...]
Term = tuple[int, int, int, int, int, int]
Ranges = Mapping[int, Sequence[int]]

# Frozen R32 Route-B weights, recounted here without the r32/e44 code.
SINGLE_WEIGHT = 18_611_432
EDGE_WEIGHT, NON_EDGE_WEIGHT = 574_000, 107_800
PATH_WEIGHT, PURE_TRIANGLE_WEIGHT, SUPPORT_TRIANGLE_WEIGHT = 2_800, 20_272, 7_000
PURE_K4_WEIGHT, CONTAINED_K4_WEIGHT = 679, 448
SUPPORT_TRIANGLES = 22

# Attainment witness (supplemental): hub 0, core 1..12, zeros 13..19.
HUB_TRIPLES: tuple[Support, ...] = tuple((0, 2 * i - 1, 2 * i) for i in range(1, 7))
CORE_TRIPLES: tuple[Support, ...] = (
    (1, 4, 8),
    (1, 5, 11),
    (1, 6, 9),
    (1, 7, 10),
    (2, 3, 7),
    (2, 5, 10),
    (2, 6, 12),
    (2, 8, 9),
    (3, 6, 10),
    (3, 8, 11),
    (3, 9, 12),
    (4, 5, 9),
    (4, 7, 12),
    (4, 10, 11),
    (5, 8, 12),
    (6, 7, 11),
)
LEAVE_CYCLE = (1, 3, 5, 7, 9, 11, 2, 4, 6, 8, 10, 12)
CORE_PAIRS: tuple[Support, ...] = tuple(
    tuple(sorted(LEAVE_CYCLE[i : i + 2])) for i in range(0, len(LEAVE_CYCLE), 2)
)
ZERO_TICKETS = tuple(range(13, 20))
# Supplemental pair switches from the witness: {x,y},{u,w} -> {x,u},{y,w}; r grows by 2.
SPREAD_MOVES: tuple[tuple[Pair, Pair], ...] = (
    ((1, 3), (13, 14)),
    ((7, 5), (15, 14)),
    ((9, 11), (13, 15)),
    ((2, 4), (16, 17)),
    ((6, 8), (16, 18)),
    ((10, 12), (16, 19)),
)
STAR_MOVES: tuple[tuple[Pair, Pair], ...] = tuple(
    ((q[0], q[1]), (13, w)) for q, w in zip(CORE_PAIRS, range(14, 20), strict=True)
)
SUPPORT_PREMISES = (
    "SUPPORT_MODEL_22_TRIPLES_27_PAIRS_SIX_LABELS_PER_TICKET",
    "LINEARITY_TWO_TICKETS_SHARE_AT_MOST_ONE_LABEL",
    "TRIPLES_LIE_IN_CORE_SO_SIGMA_LE_6_MINUS_D",
    "ZERO_DEGREE_SIX_SO_ZETA_LE_6",
    "CROSS_EDGE_DOUBLE_COUNT_SUM_SIGMA_EQ_SUM_ZETA",
    "P_IS_A_SUM_OF_FOUR_CARDINALITIES",
)
LOAD_BEARING_INEQUALITY = "sum zeta_u^2 <= 6 sum zeta_u = 6r (zeta_u in 0..6), with r>=0, P>=0"


def edge(x: int, y: int) -> Pair:
    return (x, y) if x < y else (y, x)


def frozen_authority() -> dict[str, object]:
    """6569a966 at its exact tree; its seven-row result blob, digest and working bytes."""
    require(three.git_tree(FROZEN_HEAD) == FROZEN_TREE, "frozen tree mismatch")
    raw = two.blob(FROZEN_HEAD, SEVEN_RESULT_PATH, FROZEN_RESULT_SHA256)
    require((ROOT / SEVEN_RESULT_PATH).read_bytes() == raw, "seven-row result changed")
    seven = object_row(json.loads(raw))
    require(
        seven["TASK_ID"] == t256.TASK_ID
        and seven["LEDGER_ROWS"] == 4647
        and seven["ROWS_CHANGED_FROM_SIX_ROW"] == [t256.TARGET_PROFILE]
        and TARGET_PROFILE not in rows(seven["CERTIFICATE_PROFILE_IDS"]),
        "frozen seven-row result identity mismatch",
    )
    return seven


def module_provenance() -> dict[str, str]:
    """Every reused module, and every other loaded research module, equals its 6569a966 blob."""
    reused = (t256, six, six.five, six.five.four, three, two, chase, split, r32, r5)
    package = Path(text(t256.__file__)).resolve().parent
    loaded = {
        Path(text(m.__file__)).resolve()
        for name, m in list(sys.modules.items())
        if name != __name__
        and getattr(m, "__file__", None) is not None
        and Path(text(m.__file__)).resolve().parent == package
    }
    pinned = {Path(text(m.__file__)).resolve() for m in reused}
    out: dict[str, str] = {}
    for source in sorted(loaded | pinned):
        require(source.is_relative_to(ROOT), "reused module outside this worktree")
        relative = source.relative_to(ROOT).as_posix()
        committed = chase.git("show", f"{FROZEN_HEAD}:{relative}")
        require(source.read_bytes() == committed, f"reused source changed: {relative}")
        out[relative] = sha256(committed)
    return {p: out[p] for p in sorted(s.relative_to(ROOT).as_posix() for s in pinned)}


def frozen_row(seven: Mapping[str, object]) -> tuple[Row, dict[str, object]]:
    """Rebuild the frozen seven-row ledger digest for digest and read the target row."""
    six_result, ledger6 = t256.six_row_authority()
    after = object_row(object_row(seven["ROW_UPDATE"])["AFTER"])
    ledger7 = t256.apply_seventh(
        ledger6, integer(after["bound"]), integer(after["cap"]), text(after["source"])
    )
    best, owners, next_level = three.family(ledger7)
    require(
        two.full_digest(ledger6) == seven["FULL_ROWS_SHA256_BEFORE"]
        and two.full_digest(ledger7) == seven["FULL_ROWS_SHA256_AFTER"]
        and two.bounds_digest(ledger7) == seven["BOUNDS_SHA256_AFTER"]
        and (best, owners, next_level)
        == (seven["FAMILY_BOUND_AFTER"], seven["NEXT_OWNER_IDS"], seven["NEXT_COMPETING_BOUND"]),
        "frozen seven-row ledger is not reproduced",
    )
    row = ledger7[TARGET_PROFILE]
    require(
        row == ledger6[TARGET_PROFILE]
        and (row.bound, row.cap, row.s4_base, row.source)
        == (SOURCE_BOUND, SOURCE_CAP, SOURCE_S4_BASE, SOURCE_ROW)
        and object_row(six_result["RESOLVED_ROW_BOUNDS"])[TARGET_PROFILE] == SOURCE_BOUND
        and row.realization is not None,
        "target row differs from the frozen ledger",
    )
    above = sorted((r.bound, p) for p, r in ledger7.items() if r.bound > SOURCE_BOUND)
    context: dict[str, object] = {
        "FROZEN_FAMILY_BOUND": best,
        "FROZEN_FAMILY_OWNER_IDS": owners,
        "FROZEN_NEXT_COMPETING_BOUND": next_level,
        "ROWS_ABOVE_TARGET": [[b, p] for b, p in reversed(above)],
        "ROWS_ABOVE_TARGET_COUNT": len(above),
        "CURSOR": {"ID": CURSOR_ID, "BOUND": CURSOR_BOUND},
        "TARGET_IN_CERTIFICATE_PROFILE_IDS": False,
        "FULL_ROWS_SHA256": two.full_digest(ledger7),
        "BOUNDS_SHA256": two.bounds_digest(ledger7),
    }
    return row, context


def premises() -> dict[str, object]:
    """Profile split, edge counts, the complement constant and the 42+10r term, two ways."""
    p = split.profile_values(TARGET_PROFILE)
    require(chase.profile_id(p) == TARGET_PROFILE, "theorem is stated for one profile only")
    core = [d for d in p if d]
    k, z = len(core), p.count(0)
    degrees = [TICKET_CAPACITY + d for d in p]
    require(sum(degrees) % 2 == 0, "odd G degree sum")
    g_edges = sum(degrees) // 2
    h_edges = comb(TICKETS, 2) - g_edges
    phi = comb(TICKETS, 3) - (TICKETS - 2) * h_edges + sum(comb(13 - d, 2) for d in p)
    goodman = Fraction(comb(TICKETS, 3)) - Fraction(sum(g * (TICKETS - 1 - g) for g in degrees), 2)
    m_slack = sum(TICKET_CAPACITY - d for d in core)
    base_term, slope = Fraction(z * m_slack, 2), Fraction(z + k, 2)
    constant = phi - base_term
    classes = dict(sorted(Counter(core).items(), reverse=True))
    wedges = sum(comb(g, 2) for g in degrees)
    require(
        (k, z, classes, sum(p), sum(d * d for d in p)) == (13, 7, {6: 1, 5: 12}, 66, 336)
        and g_edges == 22 * 3 + 27 == 93
        and h_edges == 97
        and phi == goodman == GOODMAN_CONSTANT
        and m_slack == 12
        and (base_term, slope) == (42, 10)
        and constant == PROVED_CAP
        and 13 - z == TICKET_CAPACITY
        and wedges == 831,
        "core-zero premises fail",
    )
    return {
        "PROFILE_ID": TARGET_PROFILE,
        "DEGREE_PROFILE": "6^1,5^12,0^7",
        "DEGREE_SUM": sum(p),
        "CORE_VERTICES": k,
        "ZERO_VERTICES": z,
        "CORE_DEGREE_CLASSES": {str(d): n for d, n in classes.items()},
        "G_DEGREES": {str(g): n for g, n in sorted(Counter(degrees).items(), reverse=True)},
        "G_EDGES": g_edges,
        "H_EDGES": h_edges,
        "WEDGES": wedges,
        "PHI_INCLUSION_EXCLUSION": phi,
        "PHI_GOODMAN": int(goodman),
        "TYPE": "CORE13_ZERO7",
        "Z_TIMES_M_PLUS_K_TIMES_MZ": "42+10r",
        "CONSTANT": int(constant),
    }


def legal_ranges() -> tuple[dict[int, range], range]:
    """sigma_x<=6-d_x (pair labels only reach Z); zeta_u<=6 (a zero has degree 6)."""
    core = {d for d in split.profile_values(TARGET_PROFILE) if d}
    sigma = {d: range(TICKET_CAPACITY - d + 1) for d in sorted(core, reverse=True)}
    return sigma, range(TICKET_CAPACITY + 1)


def certify_cap(sigma_ranges: Ranges, zeta_range: Sequence[int]) -> dict[str, object]:
    """The cap chain and the separable maximum, each fact over its whole legal range."""
    require(
        set(sigma_ranges) == {6, 5}
        and min(zeta_range) >= 0
        and all(s >= 0 for values in sigma_ranges.values() for s in values),
        "unexpected range shape",
    )
    # sum sigma*h = 2r: sigma(6-d+sigma) is 0 at the hub and 2 sigma at d=5.
    reduction = {
        d: {s: (s * (TICKET_CAPACITY - d + s), 2 * s) for s in values}
        for d, values in sigma_ranges.items()
    }
    require(
        all(lhs == rhs for table in reduction.values() for lhs, rhs in table.values()),
        "sum sigma*h = 2r fails on the legal range",
    )
    require(
        all(v * v <= ZERO_TERM_CONSTANT * v for v in zeta_range),
        "zeta^2 <= 6 zeta fails on the legal range",
    )
    # 42+10r-2r: t(H)=42+8r-sum zeta^2+P; then -8r+6r leaves -2r.
    r_coefficient = -10 + 2
    chain = r_coefficient + ZERO_TERM_CONSTANT
    require((r_coefficient, chain) == (-8, -2), "linear chain does not reduce to -2r")
    core_terms = {
        d: {s: s * (s + CORE_TERM_CONSTANT - d) for s in values}
        for d, values in sigma_ranges.items()
    }
    zero_terms = {v: v * (v - ZERO_TERM_CONSTANT) for v in zeta_range}
    counts = Counter(d for d in split.profile_values(TARGET_PROFILE) if d)
    zeros: int = split.profile_values(TARGET_PROFILE).count(0)
    separable = (
        PROVED_CAP
        + sum(n * max(core_terms[d].values()) for d, n in counts.items())
        + zeros * max(zero_terms.values())
    )
    require(separable == PROVED_CAP, "separable maximum exceeds 255")
    # Equality: -2r=0 forces r=0, then sum zeta=0 forces every zeta to 0.
    z_equal = [v for v in zeta_range if v * v == ZERO_TERM_CONSTANT * v]
    forced = sorted({c for c in combinations_with_replacement(z_equal, zeros) if sum(c) == 0})
    require(z_equal == [0, 6] and forced == [(0,) * zeros], "equality set changed")
    return {
        "SIGMA_RANGES": {str(d): list(v) for d, v in sigma_ranges.items()},
        "ZETA_RANGE": list(zeta_range),
        "SIGMA_H_REDUCTION": {
            str(d): {str(s): list(pair) for s, pair in t.items()} for d, t in reduction.items()
        },
        "ZETA_SQUARED_LE_6ZETA": {str(v): [v * v, 6 * v] for v in zeta_range},
        "R_COEFFICIENT": r_coefficient,
        "CHAIN_COEFFICIENT_R": chain,
        "CORE_TERMS": {str(d): {str(s): v for s, v in t.items()} for d, t in core_terms.items()},
        "ZERO_TERMS": {str(v): w for v, w in zero_terms.items()},
        "SEPARABLE_MAXIMUM": separable,
        "EQUALITY_CONDITIONS": {"P": 0, "R": 0, "ZETA": [0], "SIGMA": [0]},
    }


def decomposition(core: Sequence[int], sigma: Sequence[int], zeta: Sequence[int]) -> int:
    """255 + sum sigma(sigma+2-d) + sum zeta(zeta-6), the separable form."""
    return (
        PROVED_CAP
        + sum(s * (s + CORE_TERM_CONSTANT - d) for d, s in zip(core, sigma, strict=True))
        + sum(v * (v - ZERO_TERM_CONSTANT) for v in zeta)
    )


def closed_form(sigma: Sequence[int], zeta: Sequence[int]) -> int:
    """255 - 8r + sum zeta^2 with r = sum sigma (legal sigma only)."""
    return PROVED_CAP - 8 * sum(sigma) + sum(v * v for v in zeta)


def theorem() -> dict[str, object]:
    """T <= 255 for every legal structure of the target profile, by the proof above."""
    facts = premises()
    p = split.profile_values(TARGET_PROFILE)
    core = [d for d in p if d]
    k, z = len(core), p.count(0)
    for sigma, zeta in three.identity_points(k, z):
        gap = Fraction(sum(sigma) - sum(zeta), 2)
        require(
            three.split_objective(p, sigma, zeta) == decomposition(core, sigma, zeta) + gap,
            "e44 objective is not D + (sum sigma - sum zeta)/2",
        )
    cap = certify_cap(*legal_ranges())
    return {
        **facts,
        "T_COMPLEMENT": "297-t(H)",
        "T_H_IDENTITY": "42+8r-sum zeta^2+P",
        "EXACT_TRIANGLE_IDENTITY": "T=255-8r+sum zeta^2-P",
        "CAP_CHAIN": "T<=255-8r+6r-P=255-2r-P<=255",
        "P_DEFINITION": "t(M)+t(MZ)+sum_{xy in M}|N_G(x)&N_G(y)&Z|+sum_{uw in MZ}|N_G(u)&N_G(w)&K|",
        "P_NONNEGATIVE": "SUM_OF_FOUR_CARDINALITIES",
        "SEPARABLE_FORM": "e44 F=255+sum sigma(sigma+2-d)+sum zeta(zeta-6)+(sum sigma-sum zeta)/2",
        "IDENTITY_POINTS_CHECKED": len(three.identity_points(k, z)),
        **cap,
        "SUPPORT_PREMISES": list(SUPPORT_PREMISES),
        "LOAD_BEARING_INEQUALITY": LOAD_BEARING_INEQUALITY,
        "TRIANGLE_CAP": PROVED_CAP,
        "EQUALITY_CHARACTERIZATION": "T=255 IFF r=0",
        "STATUS": "PROVEN",
    }


def superset_configurations() -> Iterator[tuple[tuple[int, ...], tuple[int, ...]]]:
    """Class-sorted sigma and sorted zeta over the legal ranges with equal sums."""
    sigma_ranges, zeta_range = legal_ranges()
    counts = Counter(d for d in split.profile_values(TARGET_PROFILE) if d)
    zeros: int = split.profile_values(TARGET_PROFILE).count(0)
    by_sum: dict[int, list[tuple[int, ...]]] = {}
    for combo in combinations_with_replacement(zeta_range, zeros):
        by_sum.setdefault(sum(combo), []).append(combo)
    for hub in combinations_with_replacement(sigma_ranges[6], counts[6]):
        for fives in combinations_with_replacement(sigma_ranges[5], counts[5]):
            sigma = (*hub, *fives)
            for zeta in by_sum.get(sum(sigma), []):
                yield sigma, zeta


def superset_check() -> dict[str, object]:
    """Supplemental falsification over every reduced (sigma, zeta), never the proof."""
    p = split.profile_values(TARGET_PROFILE)
    core = [d for d in p if d]
    values: dict[tuple[tuple[int, ...], tuple[int, ...]], int] = {}
    for sigma, zeta in superset_configurations():
        f = three.split_objective(p, sigma, zeta)
        require(
            f == decomposition(core, sigma, zeta) == closed_form(sigma, zeta),
            "objective forms differ on a reduced configuration",
        )
        values[sigma, zeta] = int(f)
    graphical = list(split.degree_configurations(TARGET_PROFILE))
    require(
        len(values) == SUPERSET_COUNT
        and max(values.values()) == PROVED_CAP
        and len(graphical) == E44_GRAPHICAL_COUNT
        and all(values[c.sigma, c.zeta] == c.f for c in graphical),
        "reduced superset disagrees",
    )
    top = [[list(s), list(z)] for (s, z), f in values.items() if f == PROVED_CAP]
    by_r: dict[int, int] = {}
    for (s, _z), f in values.items():
        by_r[sum(s)] = max(by_r.get(sum(s), f), f)
    return {
        "COUNT": len(values),
        "MAX_F": max(values.values()),
        "ARGMAX": top,
        "MAX_F_BY_R": {str(r): f for r, f in sorted(by_r.items())},
        "E44_GRAPHICAL_SUBSET_COUNT": len(graphical),
        "E44_GRAPHICAL_MAX_F": max(c.f for c in graphical),
        "ROLE": "SUPPLEMENTAL_NOT_PROOF",
    }


def triangle_count(vertices: Sequence[int], edges: set[Pair]) -> int:
    return sum(
        edge(a, b) in edges and edge(a, c) in edges and edge(b, c) in edges
        for a, b, c in combinations(sorted(vertices), 3)
    )


def realization_check(triples: Sequence[Support], pairs: Sequence[Support]) -> dict[str, object]:
    """Count T directly; every premise, both identities and the cap hold on the structure."""
    d = three.legal_degrees(triples, pairs)
    r5.validate_k20_support_realization(triples, pairs, d)
    require(chase.profile_id(split.profile_values(d)) == TARGET_PROFILE, "wrong profile")
    g = {edge(x, y) for s in (*triples, *pairs) for x, y in combinations(s, 2)}
    h = set(combinations(range(TICKETS), 2)) - g
    nb = [{w for w in range(TICKETS) if w != v and edge(v, w) in g} for v in range(TICKETS)]
    core = [v for v in range(TICKETS) if d[v]]
    zero = [v for v in range(TICKETS) if not d[v]]
    ks, zs = set(core), set(zero)
    m = {e for e in h if e[0] in ks and e[1] in ks}
    mz = {e for e in h if e[0] in zs and e[1] in zs}
    sigma = [len(nb[x] & zs) for x in core]
    zeta = [len(nb[u] & ks) for u in zero]
    h_core = [sum(x in e for e in m) for x in core]
    parts = [
        triangle_count(core, m),
        triangle_count(zero, mz),
        sum(len(nb[x] & nb[y] & zs) for x, y in m),
        sum(len(nb[u] & nb[w] & ks) for u, w in mz),
    ]
    t, t_h = triangle_count(range(TICKETS), g), triangle_count(range(TICKETS), h)
    r, p = sum(sigma), sum(parts)
    dc = [d[x] for x in core]
    require(
        len(g) == 93
        and [len(nb[v]) for v in range(TICKETS)] == [TICKET_CAPACITY + v for v in d]
        and all(0 <= s <= TICKET_CAPACITY - c for c, s in zip(dc, sigma, strict=True))
        and all(0 <= v <= TICKET_CAPACITY for v in zeta)
        and r == sum(zeta)
        and h_core == [TICKET_CAPACITY - c + s for c, s in zip(dc, sigma, strict=True)]
        and 2 * len(m) == 12 + r
        and 2 * len(mz) == r
        and min(parts) >= 0,
        "structure violates a premise",
    )
    require(
        t + t_h == GOODMAN_CONSTANT
        and t_h == 42 + 8 * r - sum(v * v for v in zeta) + p
        and t == closed_form(sigma, zeta) - p == decomposition(dc, sigma, zeta) - p
        and t <= PROVED_CAP - 2 * r - p <= PROVED_CAP
        and (t == PROVED_CAP) == (r == 0),
        "realization violates the T255 chain",
    )
    reused = t256.complement_split(core, zero, g)
    require(
        (reused["T_G"], reused["T_H"], reused["P_TERMS"]) == (t, t_h, parts),
        "independent split differs from the frozen complement split",
    )
    return {
        "PROFILE_ID": TARGET_PROFILE,
        "TRIANGLES": t,
        "T_H": t_h,
        "R": r,
        "SUM_ZETA_SQUARED": sum(v * v for v in zeta),
        "SIGMA": sigma,
        "ZETA": zeta,
        "M_EDGES": len(m),
        "MZ_EDGES": len(mz),
        "P_TERMS": parts,
        "P": p,
        "SLACK_TO_CAP": PROVED_CAP - t,
    }


def witness() -> tuple[tuple[Support, ...], tuple[Support, ...]]:
    """r=0 structure: the leave of the 16 core triples is L and holds the six core pairs."""
    hub_matching = {edge(b, c) for _a, b, c in HUB_TRIPLES}
    leave = {edge(LEAVE_CYCLE[i], LEAVE_CYCLE[(i + 1) % 12]) for i in range(12)}
    covered = [edge(*e) for t in CORE_TRIPLES for e in combinations(t, 2)]
    require(
        sorted(covered) == sorted(set(combinations(range(1, 13), 2)) - hub_matching - leave)
        and len(covered) == 48
        and {edge(*q) for q in CORE_PAIRS} <= leave
        and sorted(v for q in CORE_PAIRS for v in q) == list(range(1, 13)),
        "witness packing changed",
    )
    return (*HUB_TRIPLES, *CORE_TRIPLES), (*CORE_PAIRS, *combinations(ZERO_TICKETS, 2))


def switched(
    pairs: Sequence[Support], moves: Sequence[tuple[Pair, Pair]]
) -> list[tuple[Support, ...]]:
    """Replace {x,y},{u,w} by {x,u},{y,w} per move; the full structure is checked later."""
    out = [edge(q[0], q[1]) for q in pairs]
    steps: list[tuple[Support, ...]] = []
    for (x, y), (u, w) in moves:
        require(edge(x, y) in out and edge(u, w) in out, "switch pair missing")
        out = [q for q in out if q not in (edge(x, y), edge(u, w))] + [edge(x, u), edge(y, w)]
        steps.append(tuple(sorted(out)))
    return steps


def switch_family() -> dict[str, object]:
    """Supplemental: legal structures with r=2..12, exercising P>0 and the identity."""
    triples, pairs = witness()
    out: dict[str, object] = {}
    for name, moves in (("SPREAD", SPREAD_MOVES), ("STAR", STAR_MOVES)):
        seen = [realization_check(triples, step) for step in switched(pairs, moves)]
        out[name] = [[s["R"], s["TRIANGLES"], s["SUM_ZETA_SQUARED"], s["P"]] for s in seen]
    return {"COLUMNS": ["R", "T", "SUM_ZETA_SQUARED", "P"], **out}


def ceil_fraction(value: Fraction) -> int:
    """Exact ceiling of a rational, by integer floor division of its negation."""
    return -((-value.numerator) // value.denominator)


def independent_terms(cap: int, base: int) -> list[Term]:
    """The R32 envelope from scratch: own weights, exact rationals, explicit rounding."""
    p = split.profile_values(TARGET_PROFILE)
    g = [TICKET_CAPACITY + d for d in p]
    edges = sum(g) // 2
    s1 = TICKETS * SINGLE_WEIGHT
    s2 = edges * EDGE_WEIGHT + (comb(TICKETS, 2) - edges) * NON_EDGE_WEIGHT
    wedges, claws, top = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g), max(g)
    a_max = Fraction(sum(d * (v - 2) for d, v in zip(p, g, strict=True)), 3)
    require(cap >= SUPPORT_TRIANGLES and 3 * cap <= wedges, "cap outside the wedge identity")
    terms: list[Term] = []
    for t in range(SUPPORT_TRIANGLES, cap + 1):
        s3 = (
            PATH_WEIGHT * (wedges - 3 * t)
            + PURE_TRIANGLE_WEIGHT * (t - SUPPORT_TRIANGLES)
            + SUPPORT_TRIANGLE_WEIGHT * SUPPORT_TRIANGLES
        )
        k4 = max(0, ceil_fraction(Fraction(claws - (top - 2) * (wedges - 3 * t), 4)))
        contained = min(k4, a_max.numerator // a_max.denominator)
        s4 = max(base, CONTAINED_K4_WEIGHT * contained + PURE_K4_WEIGHT * (k4 - contained))
        bound = ceil_fraction(s1 - s2 + s3 - Fraction(4 * s4, 7))
        terms.append((t, bound, k4, contained, s4, s3))
    return terms


def route_b(cap: int, base: int = SOURCE_S4_BASE) -> tuple[list[Term], dict[str, object]]:
    """Three Route-B implementations agree term by term; rounding is checked exactly."""
    p = split.profile_values(TARGET_PROFILE)
    frozen = r32.route_b_envelope(p, cap, base)
    require(frozen == split.route_b_terms(p, cap, base), "Route-B implementations differ")
    mine = independent_terms(cap, base)
    require(mine == frozen, "independent Route-B recount differs")
    residues: set[Fraction] = set()
    for t, bound, _k4, _c, s4, s3 in mine:
        exact = TICKETS * SINGLE_WEIGHT - 63_838_600 + s3 - Fraction(4 * s4, 7)
        require(0 <= bound - exact < 1, f"Route-B term {t} fails exact arithmetic")
        residues.add(bound - exact)
    require(
        [t[0] for t in mine] == list(range(SUPPORT_TRIANGLES, cap + 1))
        and all(b[1] > a[1] for a, b in pairwise(mine)),
        "Route-B terms are not strictly increasing on the triangle domain",
    )
    peak = max(mine, key=lambda term: (term[1], term[0]))
    return mine, {
        "TERM_COUNT": len(mine),
        "ARGMAX_TERM": list(peak),
        "ALL_T_MAX_BOUND": peak[1],
        "ROUNDING_RESIDUES": sorted(str(v) for v in residues),
        "MIN_STEP": min(b[1] - a[1] for a, b in pairwise(mine)),
        "MAX_STEP": max(b[1] - a[1] for a, b in pairwise(mine)),
    }


def threshold(terms: Sequence[Term], limit: int, strict: bool) -> dict[str, object]:
    """Largest cap whose envelope is <limit (strict) or <=limit, with the cap+1 value."""
    envelope = {t: max(term[1] for term in terms if term[0] <= t) for t, *_rest in terms}
    ok = [t for t, b in envelope.items() if (b < limit if strict else b <= limit)]
    require(bool(ok) and max(ok) + 1 in envelope, "threshold outside the scanned domain")
    cap = max(ok)
    require(
        all((envelope[t] < limit if strict else envelope[t] <= limit) for t in envelope if t <= cap)
        and not (envelope[cap + 1] < limit if strict else envelope[cap + 1] <= limit),
        "threshold is not a clean cut",
    )
    return {
        "CAP": cap,
        "LIMIT": limit,
        "RELATION": "<" if strict else "<=",
        "BOUND_AT_CAP": envelope[cap],
        "BOUND_AT_CAP_PLUS_1": envelope[cap + 1],
    }


def compute_result() -> dict[str, object]:
    seven = frozen_authority()
    row, context = frozen_row(seven)
    provenance = module_provenance()
    proof = theorem()
    superset = superset_check()
    if row.realization is None:
        raise AssertionError("target row has no recorded realization")
    recorded = realization_check(*row.realization)
    tight = realization_check(*witness())
    switches = switch_family()
    old_terms, old = route_b(SOURCE_CAP)
    new_terms, new = route_b(PROVED_CAP)
    new_bound = integer(new["ALL_T_MAX_BOUND"])
    require(
        old["ALL_T_MAX_BOUND"] == row.bound == SOURCE_BOUND
        and new_terms == old_terms[: len(new_terms)]
        and len(new_terms) == PROVED_CAP - SUPPORT_TRIANGLES + 1
        and tight["TRIANGLES"] == PROVED_CAP
        and integer(recorded["TRIANGLES"]) <= PROVED_CAP,
        "Route B does not extend the recorded row authority",
    )
    strict_cut = threshold(old_terms, SOURCE_BOUND, strict=True)
    cursor_cut = threshold(old_terms, CURSOR_BOUND, strict=False)
    incumbent_cut = threshold(old_terms, INCUMBENT, strict=False)
    actual: dict[str, object] = {
        "PROVED_T_CAP": PROVED_CAP,
        "NEW_ADMISSIBLE_BOUND": new_bound,
        "STRICT_OWNER_BOUND_DELTA": SOURCE_BOUND - new_bound,
        "ROUTE_B_TERM_COUNT": len(new_terms),
        "ARGMAX_TERM": new["ARGMAX_TERM"],
        "THRESHOLDS": [strict_cut["CAP"], cursor_cut["CAP"], incumbent_cut["CAP"]],
        "WITNESS_TRIANGLE_COUNT": tight["TRIANGLES"],
        "RECORDED_ROW_TRIANGLES": recorded["TRIANGLES"],
    }
    expected: dict[str, object] = {
        "PROVED_T_CAP": 255,
        "NEW_ADMISSIBLE_BOUND": 313_315_656,
        "STRICT_OWNER_BOUND_DELTA": 80_464,
        "ROUTE_B_TERM_COUNT": 234,
        "ARGMAX_TERM": [255, 313_315_656, 420, 200, 238_980, 5_062_176],
        "THRESHOLDS": [263, 263, 249],
        "WITNESS_TRIANGLE_COUNT": 255,
        "RECORDED_ROW_TRIANGLES": 193,
    }
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "COMPLETE_PROVED_SELF_CHECK_ONLY",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "PROOF": __doc__,
        "FROZEN_HEAD": FROZEN_HEAD,
        "FROZEN_TREE": FROZEN_TREE,
        "FROZEN_HEAD_TREE": "MATCH",
        "FROZEN_RESULT_SHA256": FROZEN_RESULT_SHA256,
        "FROZEN_RESULT_SHA256_STATUS": "MATCH",
        "FROZEN_LEDGER_CONTEXT": context,
        "SOURCE_ROW": {
            "PROFILE_ID": TARGET_PROFILE,
            "SOURCE": row.source,
            "SOURCE_T_CAP": row.cap,
            "SOURCE_S4_BASE": row.s4_base,
            "SOURCE_ROW_BOUND": row.bound,
        },
        "DONOR_DRAFT": DONOR_DRAFT,
        "SUPPORT_MODEL": three.support_model(),
        "THEOREM_T255": proof,
        "T255_PROOF_SCOPE": "FULL_PROFILE",
        "LOAD_BEARING_INEQUALITY": LOAD_BEARING_INEQUALITY,
        "SUPPORT_PREMISES": list(SUPPORT_PREMISES),
        "RELAXATION_DOMAIN": (
            "ALL (sigma,zeta,P): sigma_hub=0, sigma_x in {0,1} at d=5, zeta_u in 0..6, "
            "sum sigma=sum zeta, P>=0; no graphicality or realizability filter"
        ),
        "RELAXATION_COMPLETENESS": (
            "COMPLETE: every legal support structure of the profile maps into the domain by "
            "the support premises; the cap is an analytic inequality on the whole domain"
        ),
        "COUNTEREXAMPLE_STATUS": "NONE_POSSIBLE_BY_PROOF; WITNESS_ATTAINS_255",
        "PROOF_VS_ATTAINMENT": (
            "UPPER_BOUND_FROM_IDENTITY_ON_EVERY_LEGAL_STRUCTURE; WITNESS_ONLY_SHOWS_255_IS_ATTAINED"
        ),
        "INHERITED_NOT_REPROVED": [
            "the min-S2 support-model domain (labels of multiplicity 2 or 3, linear)",
            "the frozen R32 Route-B model S1-S2+S3-floor(4*max(base,S4_B)/7), its K4 floor, "
            "A_MAX and the row's S4 base 1680",
        ],
        "SUPPLEMENTAL_REDUCED_SUPERSET": superset,
        "RECORDED_ROW_REALIZATION": recorded,
        "T255_LEGAL_WITNESS": {
            "STATUS": "VERIFIED",
            "VALIDATORS": [
                "three.legal_degrees",
                "r5.validate_k20_support_realization",
                "direct triangle count",
                "t256.complement_split",
            ],
            "TRIPLES": [list(t) for t in witness()[0]],
            "PAIRS": [list(q) for q in witness()[1]],
            "CHECK": tight,
            "ROLE": "SUPPLEMENTAL_ATTAINMENT_NOT_PROOF",
        },
        "CAP_ATTAINMENT": "ATTAINED_EXACT_PROFILE_MAXIMUM",
        "SUPPLEMENTAL_SWITCH_FAMILY": switches,
        "ROUTE_B": {
            "BOUND_RULE": r32.BOUND_RULE,
            "S4_BASE": SOURCE_S4_BASE,
            "CAP_BEFORE": SOURCE_CAP,
            "BOUND_BEFORE": old["ALL_T_MAX_BOUND"],
            "CAP_AFTER": PROVED_CAP,
            **new,
            "ALL_T_TERMS": [list(t) for t in new_terms],
            "PREFIX_OF_CAP_264_ENVELOPE": True,
            "INDEPENDENT_INTEGER_RECOUNT": "PASS_OWN_WEIGHTS_EQUAL_R32_AND_E44_EVERY_TERM",
            "EXACT_RATIONAL_ROUNDING": "PASS_EVERY_BOUND_IS_THE_CEILING_OF_ITS_EXACT_VALUE",
            "ROUNDING_NOTE": (
                "K4=ceil(excess/4) rounds a lower bound of an integer count up; A_MAX floored; "
                "bound=S1-S2+S3-floor(4*S4/7); 448=7*64, 679=7*97, 1680=7*240, so 4*S4/7 is "
                "an integer and every residue is 0"
            ),
        },
        "STRICT_REDUCTION_THRESHOLD": strict_cut,
        "CURSOR_THRESHOLD": cursor_cut,
        "INCUMBENT_CLOSURE_THRESHOLD": incumbent_cut,
        "OLD_BOUND": SOURCE_BOUND,
        "NEW_CAP": PROVED_CAP,
        "NEW_BOUND": new_bound,
        **actual,
        "OWNER_BOUND_DELTA": SOURCE_BOUND - new_bound,
        "NEW_BOUND_VS_CURSOR": CURSOR_BOUND - new_bound,
        "NEW_BOUND_GAP_TO_INCUMBENT": new_bound - INCUMBENT,
        "EXPECTED_VALUES_MATCH": actual == expected,
        "EXPECTED_VALUE_DIFFERENCES": {
            k: {"EXPECTED": expected[k], "ACTUAL": actual[k]}
            for k in expected
            if actual[k] != expected[k]
        },
        "INCUMBENT": INCUMBENT,
        "CURSOR_BOUND": CURSOR_BOUND,
        "MODULE_PROVENANCE": provenance,
        "CPU_PROCESS_COUNT": 1,
        "CPU_LIMIT_SECONDS": CPU_LIMIT_SECONDS,
        "HEAVY_SOLVER_STARTED": "NO",
        "SOLVER_CALLS": 0,
        "FAMILY_BOUND_GAIN_CLAIMED": 0,
        "LEDGER_ROW_INSTALLED": "NO",
        "FROZEN_LEDGER_MUTATED": "NO",
        "ORIGINAL_WORKTREE_MUTATED": "NO",
        "NEW_WINNING_OUTCOMES": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "PUSH": "NOT_RUN",
        "MERGE": "NOT_RUN",
        "PRODUCTION_MUTATION": "NONE",
    }


def main() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_LIMIT_SECONDS, CPU_LIMIT_SECONDS))
    result = compute_result()
    payload = two.render(result)
    if RESULT_PATH.exists():
        require(RESULT_PATH.read_bytes() == payload, "existing exact result differs")
    else:
        with RESULT_PATH.open("xb") as output:
            output.write(payload)
    keys = ("PROVED_T_CAP", "NEW_ADMISSIBLE_BOUND", "STRICT_OWNER_BOUND_DELTA", "THRESHOLDS")
    summary = {k: result[k] for k in (*keys, "EXPECTED_VALUES_MATCH")}
    usage = resource.getrusage(resource.RUSAGE_SELF)
    cpu = {"PROCESS_TIME": round(process_time(), 2), "SELF_CPU": round(usage.ru_utime, 2)}
    print(json.dumps({**summary, "RESULT": str(RESULT_PATH), "SHA256": sha256(payload), **cpu}))


if __name__ == "__main__":
    main()
