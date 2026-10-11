"""Core-zero cap T<=256 for 66555555555540000000, then the seven-row min-S2 family.

Support model (r5 at 83ddad7a). Twenty tickets carry six labels each: 22 labels have
triple supports and 27 have pair supports. Every 2-subset of every support is distinct,
so two tickets share at most one label, G (shadow plus pairs) has 66+27=93 edges and
deg(v)=2d_v+(6-d_v)=6+d_v, where d_v counts the triples through v. T=t(G).

Premises. d=(6^2,5^10,4,0^7): core K={d>0}, k=13; zeros Z, z=7. A triple through a zero
would give it d>0, so every triple lies in K and a core x reaches Z only through its 6-d_x
pair labels: sigma_x<=6-d_x, i.e. 0 at d=6, {0,1} at d=5 and {0,1,2} at d=4. A zero has
degree 6, so 0<=zeta_u<=6. Both sums count the K-Z edges of G: r=sum sigma=sum zeta.
Let a=sum sigma over d=5 and q=sigma at d=4, so r=a+q.

Complement. H is the complement: |E(H)|=190-93=97, deg_H=13-d. Counting vertex triples
by their H-edges gives t(G)=C(20,3)-18|E(H)|+sum C(13-d,2)-t(H)=1140-1746+904-t(H)
=298-t(H). Goodman's C(20,3)-sum deg_G*deg_H/2=1140-842 agrees.

Remainder. Put M=H[K], MZ=H[Z]: deg_M(x)=h_x=6-d_x+sigma_x, deg_MZ(u)=zeta_u. An H
triangle lies in K, lies in Z, or has exactly one same-part edge. Over an M edge xy its Z
apices number z-sigma_x-sigma_y+c_Z(xy), c_Z(xy)=|N_G(x)&N_G(y)&Z|; over an MZ edge uw its
K apices number k-zeta_u-zeta_w+c_K(uw). Summing,
 t(H)=z|M|+k|MZ|-sum sigma*h-sum zeta^2+P,  P=t(M)+t(MZ)+sum_M c_Z+sum_MZ c_K.
P is a sum of four cardinalities, so P>=0. With |M|=(12+r)/2 and |MZ|=r/2,
z|M|+k|MZ|=42+10r. Per coordinate sigma*h is 0 at d=6, 2sigma at d=5 (sigma^2=sigma on
{0,1}) and 2q+q^2 at d=4, so sum sigma*h=2r+q^2. Hence
 t(H)=42+8r-q^2-sum zeta^2+P  and  T=256-8r+q^2+sum zeta^2-P.

Cap. q^2<=2q on {0,1,2} and zeta^2<=6zeta on {0..6}, so
 T<=256-8r+2q+6r-P=256-2a-P<=256
for every legal support structure. No graphicality, sampling or enumeration is used.
Equality needs P=0, a=0, q in {0,2} and every zeta in {0,6}; sum zeta=q then forces r=0,
so Z spans a K7. Whether 256 is attained is not asserted.

Checks. e44a635f's generic F equals D+(sum sigma-sum zeta)/2 with
D=256+sum sigma(sigma+2-d)+sum zeta(zeta-6), checked as a polynomial: a separable
quadratic is fixed by its values at 0, e_i and 2e_i. Each per-coordinate fact above is
checked over its whole legal range. Supplementally, all 471 class-sorted (sigma,zeta) with
legal ranges and equal sums, a superset of e44a635f's 94 graphical ones, give F<=256.
Route B (R32 envelope; integer, exact rational, and the e44 and R32 implementations) for
22<=T<=256 at the row's S4 base 1680 peaks at T=256: K4 428, A_MAX 200, S4 244412,
S3 5076848, bound 313327224. It is a prefix of the cap-264 envelope that reproduces the
recorded row bound 313398920. The recorded row realization is checked against the cap.

Ledger. The six-row authority (83ddad7a) is pinned by tree and result digest; its own
zero-solve replay rebuilds 4,647 rows that must match its stored digests. Exactly one row
changes, in a copy; its S4 base and realization are retained. The family maximum over all
rows and the unchanged unresolved cursor is recomputed with every tied owner. Six-row
statuses and caveats are copied verbatim, never upgraded. Global K20 optimality is
unknown. No solver or search is run.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import asdict, replace
from fractions import Fraction
from itertools import combinations, combinations_with_replacement, product
from math import comb
from pathlib import Path

from . import b649_min_s2_core_zero_t257_three_row_cert_r1 as three
from . import b649_min_s2_six_row_existing_s4_family_authority_r1 as six

TASK_ID = "B649_MIN_S2_NEXT_OWNER_CORE_ZERO_T256_FORMAL_CERT_R1"
BASE_HEAD = "83ddad7ade4ae286d12890efdbf3ea7768103d5e"
BASE_TREE = "8939ae0a9150e269bbdb787a75ceb699b0cc3bca"
SIX_RESULT_SHA256 = "1f94b064ab7392b88cf4c18ca4d3cb164305601ea9bc2b0f2174c0cddb185e5f"
TARGET_PROFILE = "66555555555540000000"
CURRENT_CAP = 264
PROPOSED_CAP = 256
S4_BASE = 1_680
SIX_ROW_BOUND = 313_398_920
TICKET_CAPACITY = 6
CORE_TERM_CONSTANT = 2
ZERO_TERM_CONSTANT = 6
SUPERSET_COUNT = 471
RESULT_STEM = "b649-min-s2-next-owner-core-zero-t256-cert-r1"
two, chase, split, r32, r5 = three.two, three.chase, three.split, three.r32, three.r5
ROOT = two.ROOT
RESULT_PATH = ROOT / two.RESULT_DIRECTORY / f"{RESULT_STEM}-result.json"
SIX_RESULT_PATH = f"{two.RESULT_DIRECTORY}/{six.RESULT_STEM}-result.json"
require, sha256 = two.require, two.sha256
integer, object_row, rows, text = two.integer, two.object_row, two.rows, two.text
INCUMBENT = two.INCUMBENT
Row = chase.Row
Pair = tuple[int, int]
Support = tuple[int, ...]
Term = tuple[int, int, int, int, int, int]
Ranges = Mapping[int, Sequence[int]]
PRESERVED_SIX_ROW_FIELDS = (
    "TASK_ID",
    "TASK_STATUS",
    "AUTHORITY_JUDGE_STATUS",
    "PRIOR_FIVE_ROW_JUDGE",
    "PRIOR_JUDGE_CAVEATS",
    "DONOR_JUDGE_STATUS",
    "DONOR_APPLICABILITY",
    "CERTIFICATE_PROFILE_IDS",
    "CURSOR",
    "CURSOR_STATUS",
    "CURSOR_PROFILE_COUNT",
    "CURSOR_PARTITION_AUTHORITY",
    "GLOBAL_K20_OPTIMUM",
)


def module_provenance() -> dict[str, str]:
    """Every module this certificate calls equals its 83ddad7a blob, byte for byte."""
    out: dict[str, str] = {}
    for module in (six, six.five, six.five.four, three, two, chase, split, r32, r5):
        require(module.__file__ is not None, "reused module has no source")
        source = Path(text(module.__file__)).resolve()
        require(source.is_relative_to(ROOT), "reused module outside this worktree")
        relative = source.relative_to(ROOT).as_posix()
        committed = chase.git("show", f"{BASE_HEAD}:{relative}")
        require(source.read_bytes() == committed, f"reused source changed: {relative}")
        out[relative] = sha256(committed)
    return dict(sorted(out.items()))


def premises() -> dict[str, object]:
    """Profile split, edge counts and the complement constant, two independent ways."""
    p = split.profile_values(TARGET_PROFILE)
    require(chase.profile_id(p) == TARGET_PROFILE, "theorem is stated for one profile only")
    core = [d for d in p if d]
    k, z = len(core), p.count(0)
    degree_sum = sum(TICKET_CAPACITY + d for d in p)
    require(degree_sum % 2 == 0, "odd G degree sum")
    g_edges = degree_sum // 2
    h_edges = comb(20, 2) - g_edges
    phi = comb(20, 3) - 18 * h_edges + sum(comb(13 - d, 2) for d in p)
    goodman = Fraction(comb(20, 3)) - Fraction(sum((TICKET_CAPACITY + d) * (13 - d) for d in p), 2)
    m_slack = sum(TICKET_CAPACITY - d for d in core)
    constant = phi - Fraction(z * m_slack, 2)
    classes = dict(sorted(Counter(core).items(), reverse=True))
    require(
        (k, z, classes, sum(p)) == (13, 7, {6: 2, 5: 10, 4: 1}, 66)
        and g_edges == 22 * 3 + 27 == 93
        and h_edges == 97
        and phi == goodman == 298
        and m_slack == 12
        and constant == PROPOSED_CAP
        and 13 - z == TICKET_CAPACITY
        and Fraction(z + k, 2) == 10,
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
        "Z_TIMES_M_PLUS_K_TIMES_MZ": "42+10r",
        "CONSTANT": int(constant),
    }


def legal_ranges() -> tuple[dict[int, range], range]:
    """sigma_x<=6-d_x (pair labels only reach Z); zeta_u<=6 (a zero has degree 6)."""
    core = {d for d in split.profile_values(TARGET_PROFILE) if d}
    sigma = {d: range(TICKET_CAPACITY - d + 1) for d in sorted(core, reverse=True)}
    return sigma, range(TICKET_CAPACITY + 1)


def certify_cap(sigma_ranges: Ranges, zeta_range: Sequence[int]) -> dict[str, object]:
    """The packet chain and the separable maximum, each fact over its whole legal range."""
    require(set(sigma_ranges) == {6, 5, 4} and min(zeta_range) >= 0, "unexpected range shape")
    q_range = sigma_ranges[4]
    # sum sigma*h = 2r + q^2: each core coordinate contributes 2 sigma, plus sigma^2 at d=4.
    reduction = {
        d: {s: (s * (TICKET_CAPACITY - d + s), 2 * s + (s * s if d == 4 else 0)) for s in values}
        for d, values in sigma_ranges.items()
    }
    require(
        all(lhs == rhs for table in reduction.values() for lhs, rhs in table.values()),
        "sum sigma*h = 2r + q^2 fails on the legal range",
    )
    require(all(s >= 0 for values in sigma_ranges.values() for s in values), "negative sigma")
    require(all(q * q <= 2 * q for q in q_range), "q^2 <= 2q fails on the legal range")
    require(
        all(v * v <= ZERO_TERM_CONSTANT * v for v in zeta_range),
        "zeta^2 <= 6 zeta fails on the legal range",
    )
    # -8r + 2q + 6r with r = a + q: coefficients of (a, q).
    chain = (-8 + 6, -8 + 2 + 6)
    require(chain == (-2, 0), "linear chain does not reduce to -2a")
    core_terms = {
        d: {s: s * (s + CORE_TERM_CONSTANT - d) for s in values}
        for d, values in sigma_ranges.items()
    }
    zero_terms = {v: v * (v - ZERO_TERM_CONSTANT) for v in zeta_range}
    counts = Counter(d for d in split.profile_values(TARGET_PROFILE) if d)
    zeros: int = split.profile_values(TARGET_PROFILE).count(0)
    separable = (
        PROPOSED_CAP
        + sum(n * max(core_terms[d].values()) for d, n in counts.items())
        + zeros * max(zero_terms.values())
    )
    require(separable == PROPOSED_CAP, "separable maximum exceeds 256")
    # Equality: a=0, P=0, q^2=2q, zeta^2=6zeta, and sum zeta = r = q.
    q_equal = [q for q in q_range if q * q == 2 * q]
    z_equal = [v for v in zeta_range if v * v == ZERO_TERM_CONSTANT * v]
    zeta_sums = {sum(combo) for combo in combinations_with_replacement(z_equal, zeros)}
    forced = [q for q in q_equal if q in zeta_sums]
    require(q_equal == [0, 2] and z_equal == [0, 6] and forced == [0], "equality set changed")
    return {
        "SIGMA_RANGES": {str(d): list(v) for d, v in sigma_ranges.items()},
        "ZETA_RANGE": list(zeta_range),
        "SIGMA_H_REDUCTION": {
            str(d): {str(s): list(pair) for s, pair in t.items()} for d, t in reduction.items()
        },
        "Q_SQUARED_LE_2Q": {str(q): [q * q, 2 * q] for q in q_range},
        "ZETA_SQUARED_LE_6ZETA": {str(v): [v * v, 6 * v] for v in zeta_range},
        "CHAIN_COEFFICIENTS_A_Q": list(chain),
        "CORE_TERMS": {str(d): {str(s): v for s, v in t.items()} for d, t in core_terms.items()},
        "ZERO_TERMS": {str(v): w for v, w in zero_terms.items()},
        "SEPARABLE_MAXIMUM": separable,
        "EQUALITY_CONDITIONS": {"P": 0, "A": 0, "Q": forced, "ZETA": [0], "R": 0},
    }


def decomposition(core: Sequence[int], sigma: Sequence[int], zeta: Sequence[int]) -> int:
    """256 + sum sigma(sigma+2-d) + sum zeta(zeta-6), the separable form."""
    return (
        PROPOSED_CAP
        + sum(s * (s + CORE_TERM_CONSTANT - d) for d, s in zip(core, sigma, strict=True))
        + sum(v * (v - ZERO_TERM_CONSTANT) for v in zeta)
    )


def packet_objective(core: Sequence[int], sigma: Sequence[int], zeta: Sequence[int]) -> int:
    """256 - 8r + q^2 + sum zeta^2 with r = sum sigma and q = sigma at d=4."""
    q = sum(s for d, s in zip(core, sigma, strict=True) if d == 4)
    return PROPOSED_CAP - 8 * sum(sigma) + q * q + sum(v * v for v in zeta)


def t256_theorem() -> dict[str, object]:
    """T <= 256 for every legal structure of the target profile, by the proof above."""
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
        "T_COMPLEMENT": "298-t(H)",
        "T_H_IDENTITY": "42+8r-q^2-sum zeta^2+P",
        "T_CLOSED_FORM": "256-8r+q^2+sum zeta^2-P",
        "CAP_CHAIN": "T<=256-8r+2q+6r-P=256-2a-P<=256",
        "P_DEFINITION": "t(M)+t(MZ)+sum_{xy in M}|N_G(x)&N_G(y)&Z|+sum_{uw in MZ}|N_G(u)&N_G(w)&K|",
        "P_NONNEGATIVE": "SUM_OF_FOUR_CARDINALITIES",
        "SEPARABLE_FORM": "e44 F=256+sum sigma(sigma+2-d)+sum zeta(zeta-6)+(sum sigma-sum zeta)/2",
        "IDENTITY_POINTS_CHECKED": len(three.identity_points(k, z)),
        **cap,
        "TRIANGLE_CAP": PROPOSED_CAP,
        "ATTAINMENT": "NOT_ASSERTED",
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
    options = [tuple(combinations_with_replacement(v, counts[d])) for d, v in sigma_ranges.items()]
    for pieces in product(*options):
        sigma = tuple(s for piece in pieces for s in piece)
        for zeta in by_sum.get(sum(sigma), []):
            yield sigma, zeta


def superset_check() -> dict[str, object]:
    """Supplemental falsification: all 471 reduced configurations, never the proof."""
    p = split.profile_values(TARGET_PROFILE)
    core = [d for d in p if d]
    values: dict[tuple[tuple[int, ...], tuple[int, ...]], int] = {}
    for sigma, zeta in superset_configurations():
        f = three.split_objective(p, sigma, zeta)
        require(
            f == decomposition(core, sigma, zeta) == packet_objective(core, sigma, zeta),
            "objective forms differ on a reduced configuration",
        )
        values[sigma, zeta] = int(f)
    graphical = list(split.degree_configurations(TARGET_PROFILE))
    require(
        len(values) == SUPERSET_COUNT
        and max(values.values()) == PROPOSED_CAP
        and all(values[c.sigma, c.zeta] == c.f for c in graphical),
        "reduced superset disagrees",
    )
    top = [[list(s), list(z)] for (s, z), f in values.items() if f == PROPOSED_CAP]
    return {
        "COUNT": len(values),
        "MAX_F": max(values.values()),
        "ARGMAX": top,
        "E44_GRAPHICAL_SUBSET_COUNT": len(graphical),
        "E44_GRAPHICAL_MAX_F": max(c.f for c in graphical),
        "ROLE": "SUPPLEMENTAL_NOT_PROOF",
    }


def edge(x: int, y: int) -> Pair:
    return (x, y) if x < y else (y, x)


def complement_split(core: Sequence[int], zero: Sequence[int], g: set[Pair]) -> dict[str, object]:
    """For any graph on K and Z: both complement identities and the exact remainder P."""
    vertices = sorted([*core, *zero])
    n, ks, zs = len(vertices), set(core), set(zero)
    every = set(combinations(vertices, 2))
    require(g <= every and len(ks | zs) == n and not ks & zs, "graph outside the partition")
    h = every - g
    nb = {v: {w for w in vertices if w != v and edge(v, w) in g} for v in vertices}
    m = {e for e in h if e[0] in ks and e[1] in ks}
    mz = {e for e in h if e[0] in zs and e[1] in zs}
    sigma = [len(nb[x] & zs) for x in core]
    zeta = [len(nb[u] & ks) for u in zero]
    h_core = [sum(x in e for e in m) for x in core]
    a_zero = [sum(u in e for e in mz) for u in zero]
    cross = dict(zip(core, sigma, strict=True)) | dict(zip(zero, zeta, strict=True))
    for (x, y), apex, other in [*((e, zero, zs) for e in m), *((e, core, ks) for e in mz)]:
        seen = sum(edge(x, w) in h and edge(y, w) in h for w in apex)
        require(
            seen == len(apex) - cross[x] - cross[y] + len(nb[x] & nb[y] & other),
            "mixed apex count is not inclusion-exclusion",
        )
    parts = [
        three.triangles(core, m),
        three.triangles(zero, mz),
        sum(len(nb[x] & nb[y] & zs) for x, y in m),
        sum(len(nb[u] & nb[w] & ks) for u, w in mz),
    ]
    t_g, t_h = three.triangles(vertices, g), three.triangles(vertices, h)
    degrees = [len(nb[v]) for v in vertices]
    require(
        2 * (t_g + t_h) == 2 * comb(n, 3) - sum(v * (n - 1 - v) for v in degrees)
        and t_g == comb(n, 3) - (n - 2) * len(h) + sum(comb(n - 1 - v, 2) for v in degrees) - t_h,
        "complement identity fails",
    )
    require(
        t_h
        == len(zero) * len(m)
        + len(core) * len(mz)
        - sum(s * v for s, v in zip(sigma, h_core, strict=True))
        - sum(s * v for s, v in zip(zeta, a_zero, strict=True))
        + sum(parts)
        and min(parts) >= 0,
        "mixed-triangle decomposition fails",
    )
    return {
        "T_G": t_g,
        "T_H": t_h,
        "M_EDGES": len(m),
        "MZ_EDGES": len(mz),
        "SIGMA": sigma,
        "ZETA": zeta,
        "H_CORE": h_core,
        "A_ZERO": a_zero,
        "P_TERMS": parts,
        "P": sum(parts),
    }


def realization_check(triples: Sequence[Support], pairs: Sequence[Support]) -> dict[str, object]:
    """A legal support structure of the target profile obeys every premise and the cap."""
    d = three.legal_degrees(triples, pairs)
    r5.validate_k20_support_realization(triples, pairs, d)
    require(chase.profile_id(split.profile_values(d)) == TARGET_PROFILE, "wrong profile")
    g = {edge(x, y) for s in (*triples, *pairs) for x, y in combinations(s, 2)}
    core = [v for v in range(20) if d[v]]
    zero = [v for v in range(20) if not d[v]]
    seen = complement_split(core, zero, g)
    sigma = [integer(v) for v in rows(seen["SIGMA"])]
    zeta = [integer(v) for v in rows(seen["ZETA"])]
    dc = [d[v] for v in core]
    a = sum(s for c, s in zip(dc, sigma, strict=True) if c == 5)
    q = sum(s for c, s in zip(dc, sigma, strict=True) if c == 4)
    r, p, t = sum(sigma), integer(seen["P"]), integer(seen["T_G"])
    require(
        all(0 <= s <= TICKET_CAPACITY - c for c, s in zip(dc, sigma, strict=True))
        and all(0 <= v <= TICKET_CAPACITY for v in zeta)
        and r == a + q == sum(zeta)
        and rows(seen["H_CORE"]) == [6 - c + s for c, s in zip(dc, sigma, strict=True)]
        and rows(seen["A_ZERO"]) == zeta
        and len(g) == 93
        and [sum(v in e for e in g) for v in range(20)] == [TICKET_CAPACITY + c for c in d],
        "cross-edge degree constraints fail",
    )
    require(
        t == 298 - integer(seen["T_H"])
        and integer(seen["T_H"]) == 42 + 8 * r - q * q - sum(v * v for v in zeta) + p
        and t == packet_objective(dc, sigma, zeta) - p == decomposition(dc, sigma, zeta) - p
        and t <= PROPOSED_CAP - 2 * a - p <= PROPOSED_CAP,
        "realization violates the T256 chain",
    )
    return {"PROFILE_ID": TARGET_PROFILE, "TRIANGLES": t, "A": a, "Q": q, "R": r, **seen}


def route_b(cap: int) -> tuple[list[Term], int]:
    """R32 envelope at cap: both implementations, then exact integers and rationals."""
    p = split.profile_values(TARGET_PROFILE)
    terms = r32.route_b_envelope(p, cap, S4_BASE)
    require(terms == split.route_b_terms(p, cap, S4_BASE), "Route-B implementations differ")
    g = [TICKET_CAPACITY + d for d in p]
    w, u = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g)
    a_max = Fraction(sum(d * (v - 2) for d, v in zip(p, g, strict=True)), 3)
    require([t[0] for t in terms] == list(range(22, cap + 1)), "triangle domain differs")
    for t, bound, k4, contained, s4, s3 in terms:
        excess = Fraction(u - (max(g) - 2) * (w - 3 * t), 4)
        k4_exact = max(0, -((-excess.numerator) // excess.denominator))
        c_exact = min(k4_exact, a_max.numerator // a_max.denominator)
        s4_exact = max(S4_BASE, 448 * c_exact + 679 * (k4_exact - c_exact))
        s3_exact = 2800 * w + 11872 * (t - 22) - 30800
        exact = 372_228_640 - 63_838_600 + s3_exact - Fraction(4 * s4_exact, 7)
        require(
            (k4, contained, s4, s3) == (k4_exact, c_exact, s4_exact, s3_exact)
            and 0 <= bound - exact < 1,
            f"Route-B term {t} fails exact arithmetic",
        )
    return terms, max(term[1] for term in terms)


def six_row_authority() -> tuple[dict[str, object], dict[str, Row]]:
    """The pinned 83ddad7a result and its own zero-solve replay, digest for digest."""
    require(three.git_tree(BASE_HEAD) == BASE_TREE, "six-row base tree mismatch")
    raw = two.blob(BASE_HEAD, SIX_RESULT_PATH, SIX_RESULT_SHA256)
    require((ROOT / SIX_RESULT_PATH).read_bytes() == raw, "six-row result changed")
    for path in (
        f"src/lottolab/research/{six.__name__.rsplit('.', 1)[1]}.py",
        f"tests/unit/test_{six.__name__.rsplit('.', 1)[1]}.py",
    ):
        require(
            (ROOT / path).read_bytes() == chase.git("show", f"{BASE_HEAD}:{path}"),
            "six-row source or tests changed",
        )
    result = object_row(json.loads(raw))
    prior, cert, identity = six.authorities()
    require(
        prior == result["PRESERVED_FIVE_ROW_AUTHORITY"]
        and cert == result["CERTIFICATE_F"]
        and json.loads(json.dumps(identity)) == result["CERTIFICATE_F_IDENTITY"],
        "six-row inputs differ from its sealed result",
    )
    ledger = six.apply_sixth(six.five_row_ledger(prior), cert)
    require(
        len(ledger) == result["LEDGER_ROWS"] == 4647
        and two.full_digest(ledger) == result["FULL_ROWS_SHA256_AFTER"]
        and two.bounds_digest(ledger) == result["BOUNDS_SHA256_AFTER"]
        and {p: row.bound for p, row in sorted(ledger.items())} == result["RESOLVED_ROW_BOUNDS"]
        and list(three.family(ledger))
        == [result[k] for k in ("FAMILY_BOUND_AFTER", "FAMILY_OWNER_IDS", "NEXT_COMPETING_BOUND")]
        and result["FAMILY_BOUND_AFTER"] == SIX_ROW_BOUND
        and result["FAMILY_OWNER_IDS"] == [TARGET_PROFILE]
        and result["CURSOR"] == {"ID": chase.prior.CURSOR_ID, "BOUND": chase.prior.CURSOR_BOUND},
        "six-row ledger does not reproduce 83ddad7a",
    )
    return result, ledger


def apply_seventh(ledger: Mapping[str, Row], bound: int, cap: int, source: str) -> dict[str, Row]:
    """Install exactly one tighter row for the target profile; nothing else may move."""
    old = ledger[TARGET_PROFILE]
    require(type(bound) is int and type(cap) is int, "update must use exact integers")
    require(
        (old.bound, old.cap, old.s4_base) == (SIX_ROW_BOUND, CURRENT_CAP, S4_BASE)
        and bound < old.bound
        and 22 <= cap < old.cap,
        "seventh update does not tighten the recorded row",
    )
    before = two.full_digest(ledger)
    after = dict(ledger)
    after[TARGET_PROFILE] = replace(old, bound=bound, cap=cap, source=source)
    require(
        set(after) == set(ledger)
        and [p for p in ledger if ledger[p] != after[p]] == [TARGET_PROFILE]
        and two.full_digest(ledger) == before,
        "seventh update changed another row or the frozen ledger",
    )
    return after


def compute_result() -> dict[str, object]:
    provenance = module_provenance()
    six_result, ledger = six_row_authority()
    theorem = t256_theorem()
    superset = superset_check()
    old_terms, old_bound = route_b(CURRENT_CAP)
    new_terms, new_bound = route_b(PROPOSED_CAP)
    row = ledger[TARGET_PROFILE]
    require(
        old_bound == row.bound == SIX_ROW_BOUND
        and (row.cap, row.s4_base) == (CURRENT_CAP, S4_BASE)
        and len(new_terms) == PROPOSED_CAP - 21
        and new_terms == old_terms[: len(new_terms)],
        "Route B does not extend the recorded row authority",
    )
    peak = max(new_terms, key=lambda term: (term[1], term[0]))
    if row.realization is None:
        raise AssertionError("target row has no recorded realization")
    recorded = realization_check(*row.realization)
    source = f"{TASK_ID}:CORE_ZERO_T256_THEOREM"
    after = apply_seventh(ledger, new_bound, PROPOSED_CAP, source)
    before, before_owners, _ = three.family(ledger)
    best, owners, next_level = three.family(after)
    cursor = [chase.prior.CURSOR_ID] if next_level == chase.prior.CURSOR_BOUND else []
    next_owners = sorted([p for p, r in after.items() if r.bound == next_level] + cursor)
    previous = [text(p) for p in rows(six_result["CERTIFICATE_PROFILE_IDS"])]
    require(
        TARGET_PROFILE not in previous
        and all(after[p] == ledger[p] for p in previous)
        and (before, before_owners) == (SIX_ROW_BOUND, [TARGET_PROFILE]),
        "prior certificates or the six-row family were not preserved",
    )
    above = sorted(p for p, r in after.items() if r.bound > INCUMBENT)
    actual: dict[str, object] = {
        "PROFILE_BOUND_AFTER": new_bound,
        "FAMILY_BOUND_AFTER": best,
        "FAMILY_BOUND_DELTA": before - best,
        "NEXT_OWNER_IDS": owners,
        "GAP_TO_INCUMBENT": best - INCUMBENT,
        "T256_TERM": list(peak[2:]),
    }
    expected: dict[str, object] = {
        "PROFILE_BOUND_AFTER": 313_327_224,
        "FAMILY_BOUND_AFTER": 313_398_532,
        "FAMILY_BOUND_DELTA": 388,
        "NEXT_OWNER_IDS": ["66655555555521000000"],
        "GAP_TO_INCUMBENT": 134_644,
        "T256_TERM": [428, 200, 244_412, 5_076_848],
    }
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "T256_SEVEN_ROW_RESULT_PENDING_FRESH_JUDGE",
        "PROOF": __doc__,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "SIX_ROW_RESULT_SHA256": SIX_RESULT_SHA256,
        "PRESERVED_SIX_ROW_STATUS": {k: six_result[k] for k in PRESERVED_SIX_ROW_FIELDS},
        "SIX_ROW_STATUS_SOURCE": "VERBATIM_SIX_ROW_RESULT_FIELDS_NOT_UPGRADED",
        "SUPPORT_MODEL": three.support_model(),
        "THEOREM_T256": theorem,
        "SUPPLEMENTAL_REDUCED_SUPERSET": superset,
        "RECORDED_ROW_REALIZATION": recorded,
        "ROUTE_B": {
            "BOUND_RULE": r32.BOUND_RULE,
            "S4_BASE": S4_BASE,
            "CAP_BEFORE": CURRENT_CAP,
            "BOUND_BEFORE": old_bound,
            "CAP_AFTER": PROPOSED_CAP,
            "TERM_COUNT": len(new_terms),
            "ALL_T_TERMS": [list(t) for t in new_terms],
            "ARGMAX_TERM": list(peak),
            "ALL_T_MAX_BOUND": new_bound,
            "PREFIX_OF_CAP_264_ENVELOPE": True,
            "STATUS": "PASS_INTEGER_AND_RATIONAL",
        },
        "LEDGER_ROWS": len(after),
        "CERTIFICATES_COMPOSED": len(previous) + 1,
        "CERTIFICATE_PROFILE_IDS": [*previous, TARGET_PROFILE],
        "ROWS_CHANGED_FROM_SIX_ROW": [p for p in ledger if ledger[p] != after[p]],
        "ROW_UPDATE": {
            "PROFILE_ID": TARGET_PROFILE,
            "BEFORE": asdict(ledger[TARGET_PROFILE]),
            "AFTER": asdict(after[TARGET_PROFILE]),
        },
        "PROFILE_BOUND_BEFORE": row.bound,
        "FAMILY_BOUND_BEFORE": before,
        **actual,
        "NEXT_COMPETING_BOUND": next_level,
        "NEXT_COMPETING_OWNER_IDS": next_owners,
        "EXPECTED_VALUES_MATCH": actual == expected,
        "EXPECTED_VALUE_DIFFERENCES": {
            k: {"EXPECTED": expected[k], "ACTUAL": actual[k]}
            for k in expected
            if actual[k] != expected[k]
        },
        "NEW_OWNER_ROWS": {p: asdict(after[p]) for p in owners if p in after},
        "INCUMBENT": INCUMBENT,
        "STRICT_GAIN_THRESHOLD": INCUMBENT + 1,
        "RESOLVED_ROWS_ABOVE_INCUMBENT": len(above),
        "FULL_ROWS_SHA256_BEFORE": two.full_digest(ledger),
        "FULL_ROWS_SHA256_AFTER": two.full_digest(after),
        "BOUNDS_SHA256_BEFORE": two.bounds_digest(ledger),
        "BOUNDS_SHA256_AFTER": two.bounds_digest(after),
        "MODULE_PROVENANCE": provenance,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "FROZEN_LEDGER_MUTATED": "NO",
        "RUN1_MUTATED": "NO",
        "HEAVY_SOLVER_STARTED": "NO",
        "REMOTE_WRITE": "NO",
        "SOLVER_CALLS": 0,
    }


def main() -> None:
    result = compute_result()
    payload = two.render(result)
    if RESULT_PATH.exists():
        require(RESULT_PATH.read_bytes() == payload, "existing exact result differs")
    else:
        with RESULT_PATH.open("xb") as output:
            output.write(payload)
    keys = ("PROFILE_BOUND_AFTER", "FAMILY_BOUND_AFTER", "FAMILY_BOUND_DELTA", "NEXT_OWNER_IDS")
    summary = {k: result[k] for k in (*keys, "GAP_TO_INCUMBENT", "EXPECTED_VALUES_MATCH")}
    print(json.dumps({**summary, "RESULT": str(RESULT_PATH), "SHA256": sha256(payload)}))


if __name__ == "__main__":
    main()
