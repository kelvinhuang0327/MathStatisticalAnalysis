"""One-inequality triangle cap T<=255 for 66665555554431000000 (14 core, 6 zero).

Support model (r5, pinned at 6569a966). Twenty tickets carry six labels each; 22 labels
have triple supports and 27 have pair supports, and every 2-subset of every support is
distinct (pair-linearity). So G (triple shadows plus pairs) has 66+27=93 edges and a
ticket in d triples has degree 2d+(6-d)=6+d. T=t(G).

Premises. d=(6^4,5^6,4^2,3,1,0^6): core K={d>0}, k=14; zeros Z, z=6. A triple through a
zero would give it d>0, so every triple lies in K and a K-Z edge is a pair label:
sigma_x=|N(x)&Z|<=6-d_x. A zero u has six pair labels, i.e. six G-neighbours, but only
z-1=5 other zeros, so zeta_u=|N(u)&K| lies in [1,6]. Both sums count the K-Z edges:
r=sum sigma=sum zeta.

Goodman. H is the complement, deg_H=13-d, |E(H)|=190-93=97. Counting vertex triples by
their H-edges, t(G)=C(20,3)-18|E(H)|+sum C(13-d,2)-t(H)=1140-1746+903-t(H)=297-t(H);
Goodman's C(20,3)-sum deg_G*deg_H/2=1140-843 agrees.

Remainder. Put M=H[K], MZ=H[Z]: h_x=deg_M(x)=7-d_x+sigma_x and a_u=deg_MZ(u)=zeta_u-1,
so |M|=(32+r)/2 and |MZ|=(r-6)/2. An H triangle lies in K, lies in Z, or has exactly one
same-part edge. Over an M edge xy its Z apices number 6-sigma_x-sigma_y+c_Z(xy) with
c_Z(xy)=|N_G(x)&N_G(y)&Z|; over an MZ edge uw its K apices number 14-zeta_u-zeta_w+c_K(uw).
Summing, t(H)=6|M|+14|MZ|-sum sigma*h-sum zeta*a+P=54+10r-sum sigma*h-sum zeta*a+P with
 P=t(M)+t(MZ)+sum_M c_Z+sum_MZ c_K>=0 (four cardinalities). Splitting 10r=4r+6r,
 T=243+sum_K sigma(sigma+3-d)+sum_Z zeta(zeta-7)-P.

Cap. The one load-bearing combinatorial inequality is zeta_u>=1 (pigeonhole above). With
zeta_u<=6 it gives zeta(zeta-7)+6=(zeta-1)(zeta-6)<=0, so the zero side is at most -36.
Per core class on 0<=sigma<=6-d, sigma(sigma+3-d) peaks at 0 (d=6), 0 (d=5), 2 (d=4,
sigma=2), 9 (d=3, sigma=3) and 35 (d=1, sigma=5): at most 4*0+6*0+2*2+9+35=48. Hence
 T<=243+48-36-P<=255
for every legal support structure of the profile. No graphicality, sampling or search is
used. Equality would need P=0, the core argmax (sum 12) and every zeta in {1,6}; but such
zeta sum to 6+5j, never 12, so 255 is not attained and is not claimed tight. Dropping
zeta>=1 leaves zeta=0 free: the separable maximum becomes 291 and the exact balanced range
maximum 279, both above the sufficient cap 263, so the inequality is load-bearing.

Checks. e44a635f's generic F equals D+sum sigma-sum zeta for the D above, checked as a
polynomial at 0, e_i and 2e_i. The complement split is checked as a graph identity and on
the frozen row's recorded realization. Supplementally the exact maximum over all balanced
class-sorted range states is 253 (with zeta>=1) and 279 (without).

Route B (R32 envelope, S4 base 112) over 22<=T<=255 peaks at T=255: K4 423, A_MAX 200,
S4 241017, S3 5062176, bound 313314492. Every term is recounted in exact integers and
rationals (K4 ceiling, A_MAX floor, S4-credit floor, bound ceiling); the envelope strictly
increases, is a prefix of the cap-264 envelope that reproduces the frozen row bound
313395344, and its largest cap with bound <=313395164 is 263.

Authority. The frozen T256 result (6569a966) is pinned by tree and digest; the six-row
replay plus its recorded seventh update must reproduce that result's ledger digests and
family. The target row (cap 264, S4 base 112) and its cap source, R30 GROUP_ATTEMPTS[3414],
are read back and checked. No ledger row is changed and no family gain is claimed. Prior
art on other lineages (97dcfa9a: T<=243) is recorded, not imported or re-run.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from fractions import Fraction
from itertools import combinations, combinations_with_replacement, pairwise, product
from math import comb
from pathlib import Path

from . import b649_min_s2_next_owner_core_zero_t256_cert_r1 as t256

TASK_ID = "B649_NEW_FAMILY_MAX_OWNER_B_R1"
FROZEN_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
FROZEN_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
FROZEN_RESULT_SHA256 = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"
TARGET_PROFILE = "66665555554431000000"
DEGREE_DISTRIBUTION = "6^4,5^6,4^2,3^1,1^1,0^6"
SOURCE_CAP = 264
SOURCE_S4_BASE = 112
SOURCE_ROW_BOUND = 313_395_344
SOURCE_LABEL = "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:NB_CERTIFICATES[881]"
CAP_ATTEMPT_INDEX = 3414
CAP_PROOF_OBJECT_SHA256 = "eaca04bb815f5f59eab06d29a07140a1e9042fd21666fbda7a4064fa7cc02205"
R30_RESULT_SHA256 = "9ed94532cc2bff5de1569f10561fb8340238ff3b1b1c3ae129e6a4929014f6fe"
PRIORITY_THRESHOLD = 313_395_164
GOODMAN_CONSTANT = 297
IDENTITY_CONSTANT = 243
PROVED_CAP = 255
TICKET_CAPACITY = 6
CORE_TERM_CONSTANT = 3
ZERO_TERM_CONSTANT = 7
ZERO_PENALTY = 6
ZETA_FLOOR = 1
S1_MINUS_S2 = 372_228_640 - 63_838_600
RESULT_STEM = "b649-new-family-max-owner-b-r1"
three, two, chase, split, r32, r5 = t256.three, t256.two, t256.chase, t256.split, t256.r32, t256.r5
ROOT = two.ROOT
RESULT_PATH = ROOT / two.RESULT_DIRECTORY / f"{RESULT_STEM}-result.json"
FROZEN_RESULT_PATH = f"{two.RESULT_DIRECTORY}/{t256.RESULT_STEM}-result.json"
R30_RESULT_PATH = (
    f"{two.RESULT_DIRECTORY}/b649-k20-min-s2-current-cursor-dynamic-family-max-r30-result.json"
)
require, sha256 = two.require, two.sha256
integer, object_row, rows, text = two.integer, two.object_row, two.rows, two.text
INCUMBENT = two.INCUMBENT
Row = chase.Row
Term = t256.Term
Support = t256.Support
Ranges = Mapping[int, Sequence[int]]
PRIOR_ART: dict[str, dict[str, object]] = {
    "SAME_PROFILE_EXACT_SPLIT_CAP_243": {
        "COMMIT": "97dcfa9a2cfec1ef30097d808ecb6f87e9c6241f",
        "TREE": "83fbdfece095ec5f88ac411a9d2db7a9aaf833f3",
        "RESULT_SHA256": "9e8bc62cf36eab69a6714237841316609907b9da5a8e7026ffb7955950902a0b",
        "CLAIM": "T<=243, Route-B 313206948 at S4 base 112",
        "METHOD": "e44a635f split identity, necessary graphicality over 957 of 5113 states",
        "SCOPE": "FULL_PROFILE_NECESSARY_RELAXATION",
        "JUDGE": "VERIFIED_WITH_CAVEATS per its commit message (judged tree 83fbdfec)",
        "LINEAGE": "base 8d08e843; not an ancestor of the frozen head",
        "USE_HERE": "NOT_IMPORTED_NOT_RERUN; stronger than this certificate",
    },
    "SAME_PROFILE_BONFERRONI5": {
        "COMMIT": "8fa9c0e6",
        "CLAIM": "S5 lever, cap 264 kept, row 313386188",
        "STATUS": "COMPLETE_SELF_CHECK_ONLY; not an ancestor of the frozen head",
        "USE_HERE": "NOT_USED",
    },
    "ACTIVE_PROFILE_NEIGHBOR_DEFICIT": {
        "COMMIT": "209e7d3c",
        "CLAIM": "profile bound 313257518 (no triangle cap)",
        "STATUS": "COMPLETE_SELF_CHECK_ONLY; not an ancestor of the frozen head",
        "USE_HERE": "NOT_USED",
    },
    "GENERIC_SPLIT_E44": {
        "COMMIT": "e44a635f1932166734aaa3f64f9469c0e63c7520",
        "STATUS": "COMPLETE_SELF_CHECK_ONLY; ancestor of the frozen head; row not adopted",
        "USE_HERE": "SPLIT_OBJECTIVE_POLYNOMIAL_CROSS_CHECK_ONLY",
    },
}


def module_provenance() -> dict[str, str]:
    """Every reused module equals its frozen-head blob, byte for byte."""
    six = t256.six
    out: dict[str, str] = {}
    for module in (t256, six, six.five, six.five.four, three, two, chase, split, r32, r5):
        require(module.__file__ is not None, "reused module has no source")
        source = Path(text(module.__file__)).resolve()
        require(source.is_relative_to(ROOT), "reused module outside this worktree")
        relative = source.relative_to(ROOT).as_posix()
        committed = chase.git("show", f"{FROZEN_HEAD}:{relative}")
        require(source.read_bytes() == committed, f"reused source changed: {relative}")
        out[relative] = sha256(committed)
    return dict(sorted(out.items()))


def frozen_authority() -> tuple[dict[str, object], dict[str, Row]]:
    """The frozen T256 result and the seven-row ledger it seals, digest for digest."""
    require(three.git_tree(FROZEN_HEAD) == FROZEN_TREE, "frozen tree mismatch")
    raw = two.blob(FROZEN_HEAD, FROZEN_RESULT_PATH, FROZEN_RESULT_SHA256)
    require((ROOT / FROZEN_RESULT_PATH).read_bytes() == raw, "frozen result changed")
    frozen = object_row(json.loads(raw))
    seventh = object_row(object_row(frozen["ROW_UPDATE"])["AFTER"])
    _six_result, ledger = t256.six_row_authority()
    seven = t256.apply_seventh(
        ledger, integer(seventh["bound"]), integer(seventh["cap"]), text(seventh["source"])
    )
    require(
        len(seven) == frozen["LEDGER_ROWS"] == 4647
        and two.full_digest(seven) == frozen["FULL_ROWS_SHA256_AFTER"]
        and two.bounds_digest(seven) == frozen["BOUNDS_SHA256_AFTER"]
        and list(three.family(seven))
        == [frozen[k] for k in ("FAMILY_BOUND_AFTER", "NEXT_OWNER_IDS", "NEXT_COMPETING_BOUND")],
        "frozen seven-row ledger does not reproduce 6569a966",
    )
    return frozen, seven


def source_row(ledger: Mapping[str, Row]) -> Row:
    """The frozen target row: bound, cap, S4 base and source label exactly as sealed."""
    row = ledger[TARGET_PROFILE]
    require(
        (row.bound, row.cap, row.s4_base, row.source)
        == (SOURCE_ROW_BOUND, SOURCE_CAP, SOURCE_S4_BASE, SOURCE_LABEL)
        and row.realization is not None,
        "frozen target row differs from the source premises",
    )
    return row


def cap_authority() -> dict[str, object]:
    """R30's INFEASIBLE refutation of exactly this profile at SOURCE_CAP+1."""
    raw = two.blob(FROZEN_HEAD, R30_RESULT_PATH, R30_RESULT_SHA256)
    require((ROOT / R30_RESULT_PATH).read_bytes() == raw, "R30 result changed")
    attempt = object_row(rows(object_row(json.loads(raw))["GROUP_ATTEMPTS"])[CAP_ATTEMPT_INDEX])
    digest = sha256(json.dumps(attempt, sort_keys=True).encode())
    require(
        digest == CAP_PROOF_OBJECT_SHA256
        and attempt["ATTEMPT_INDEX"] == CAP_ATTEMPT_INDEX
        and attempt["PROFILE_IDS"] == [TARGET_PROFILE]
        and attempt["STATUS"] == "INFEASIBLE"
        and attempt["REFUTED_GRAPH_TRIANGLE_COUNT"] == SOURCE_CAP + 1
        and attempt["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"] == SOURCE_CAP,
        "cap source is not the R30 refutation of this profile",
    )
    return {
        "SOURCE_LABEL": SOURCE_LABEL,
        "SOURCE_LABEL_KIND": "HISTORICAL_CATALOG_LABEL_NOT_A_RESULT_POINTER",
        "R30_RESULT": R30_RESULT_PATH,
        "R30_RESULT_SHA256": R30_RESULT_SHA256,
        "ATTEMPT": f"GROUP_ATTEMPTS[{CAP_ATTEMPT_INDEX}]",
        "PROOF_OBJECT_SHA256": digest,
        "ROUTE": attempt["ROUTE"],
        "CERTIFICATE_KIND": attempt["CERTIFICATE_KIND"],
        "STATUS": attempt["STATUS"],
        "CAP": SOURCE_CAP,
        "REPLAYED_HISTORICAL_SOLVER": False,
    }


def premises() -> dict[str, object]:
    """Profile split, edge counts, Goodman two ways, and the identity constants."""
    p = split.profile_values(TARGET_PROFILE)
    require(chase.profile_id(p) == TARGET_PROFILE, "theorem is stated for one profile only")
    core = [d for d in p if d]
    k, z = len(core), p.count(0)
    g = [TICKET_CAPACITY + d for d in p]
    require(sum(g) % 2 == 0, "odd G degree sum")
    g_edges = sum(g) // 2
    h_edges = comb(20, 2) - g_edges
    phi = comb(20, 3) - 18 * h_edges + sum(comb(13 - d, 2) for d in p)
    goodman = Fraction(comb(20, 3)) - Fraction(sum(v * (19 - v) for v in g), 2)
    m_base = sum(13 - z - d for d in core)  # 2|M| = m_base + r
    mz_base = z * (13 - k)  # 2|MZ| = mz_base + r
    constant = phi - Fraction(z * m_base + k * mz_base, 2)
    linear = Fraction(z + k, 2)
    zeta_floor = TICKET_CAPACITY - (z - 1)
    classes = dict(sorted(Counter(core).items(), reverse=True))
    require(
        (k, z, classes, sum(p), sum(d * d for d in p))
        == (14, 6, {6: 4, 5: 6, 4: 2, 3: 1, 1: 1}, 66, 336)
        and g_edges == 22 * 3 + 27 == 93
        and h_edges == 97
        and phi == goodman == GOODMAN_CONSTANT
        and (m_base, mz_base) == (32, -6)
        and constant == IDENTITY_CONSTANT
        and linear == 10
        and zeta_floor == ZETA_FLOOR
        and sum(comb(v, 2) for v in g) == 831
        and sum(comb(v, 3) for v in g) == 2349,
        "core-zero premises fail",
    )
    return {
        "PROFILE_ID": TARGET_PROFILE,
        "DEGREE_DISTRIBUTION": DEGREE_DISTRIBUTION,
        "DEGREE_SUM": sum(p),
        "DEGREE_SQUARE_SUM": sum(d * d for d in p),
        "CORE_VERTICES": k,
        "ZERO_VERTICES": z,
        "CORE_DEGREE_CLASSES": {str(d): n for d, n in classes.items()},
        "G_EDGES": g_edges,
        "H_EDGES": h_edges,
        "W": sum(comb(v, 2) for v in g),
        "J": sum(comb(v, 3) for v in g),
        "PHI_INCLUSION_EXCLUSION": phi,
        "PHI_GOODMAN": int(goodman),
        "M_EDGES": "(32+r)/2",
        "MZ_EDGES": "(r-6)/2",
        "Z_TIMES_M_PLUS_K_TIMES_MZ": "54+10r",
        "IDENTITY_CONSTANT": int(constant),
        "ZETA_FLOOR": zeta_floor,
    }


def legal_ranges() -> tuple[dict[int, range], range]:
    """sigma_x<=6-d_x (pair labels only reach Z); 1<=zeta_u<=6 (pigeonhole on Z)."""
    core = {d for d in split.profile_values(TARGET_PROFILE) if d}
    sigma = {d: range(TICKET_CAPACITY - d + 1) for d in sorted(core, reverse=True)}
    return sigma, range(ZETA_FLOOR, TICKET_CAPACITY + 1)


def core_term(d: int, s: int) -> int:
    return s * (s + CORE_TERM_CONSTANT - d)


def zero_term(v: int) -> int:
    return v * (v - ZERO_TERM_CONSTANT)


def decomposition(core: Sequence[int], sigma: Sequence[int], zeta: Sequence[int]) -> int:
    """243 + sum sigma(sigma+3-d) + sum zeta(zeta-7), the separable form."""
    return (
        IDENTITY_CONSTANT
        + sum(core_term(d, s) for d, s in zip(core, sigma, strict=True))
        + sum(zero_term(v) for v in zeta)
    )


def certify_cap(sigma_ranges: Ranges, zeta_range: Sequence[int]) -> dict[str, object]:
    """Per-coordinate reduction, the zero inequality and the separable maximum."""
    counts = Counter(d for d in split.profile_values(TARGET_PROFILE) if d)
    zeros: int = split.profile_values(TARGET_PROFILE).count(0)
    require(set(sigma_ranges) == set(counts) and min(zeta_range) >= 0, "unexpected range shape")
    require(all(s >= 0 for values in sigma_ranges.values() for s in values), "negative sigma")
    # 10r = 4 sum sigma + 6 sum zeta: sigma*h-4sigma and zeta*a-6zeta are the terms.
    reduction = {
        d: {s: (s * (13 - zeros - d + s) - 4 * s, core_term(d, s)) for s in values}
        for d, values in sigma_ranges.items()
    }
    zero_reduction = {v: (v * (v - 1) - 6 * v, zero_term(v)) for v in zeta_range}
    require(
        all(lhs == rhs for table in reduction.values() for lhs, rhs in table.values())
        and all(lhs == rhs for lhs, rhs in zero_reduction.values()),
        "split of -10r into core and zero terms fails on the legal range",
    )
    require(
        all(zero_term(v) <= -ZERO_PENALTY for v in zeta_range),
        "zeta(zeta-7) <= -6 fails on the legal range",
    )
    core_max = {d: max(core_term(d, s) for s in values) for d, values in sigma_ranges.items()}
    argmax = {
        d: [s for s in values if core_term(d, s) == core_max[d]]
        for d, values in sigma_ranges.items()
    }
    zero_max = max(zero_term(v) for v in zeta_range)
    separable = (
        IDENTITY_CONSTANT + sum(n * core_max[d] for d, n in counts.items()) + zeros * zero_max
    )
    require(separable == PROVED_CAP, "separable maximum is not the proved cap")
    # Equality needs the core argmax and every zeta in the zero argmax with equal sums.
    zeta_top = [v for v in zeta_range if zero_term(v) == zero_max]
    core_sums = {
        sum(s for part in parts for s in part)
        for parts in product(*(combinations_with_replacement(argmax[d], counts[d]) for d in counts))
    }
    zeta_sums = {sum(c) for c in combinations_with_replacement(zeta_top, zeros)}
    require(
        core_max == {6: 0, 5: 0, 4: 2, 3: 9, 1: 35}
        and zeta_top == [1, 6]
        and core_sums == {12}
        and not core_sums & zeta_sums,
        "equality set changed",
    )
    return {
        "SIGMA_RANGES": {str(d): list(v) for d, v in sigma_ranges.items()},
        "ZETA_RANGE": list(zeta_range),
        "CORE_TERM_TABLE": {
            str(d): {str(s): pair[1] for s, pair in t.items()} for d, t in reduction.items()
        },
        "ZERO_TERM_TABLE": {str(v): pair[1] for v, pair in zero_reduction.items()},
        "ZERO_INEQUALITY": "zeta(zeta-7)+6=(zeta-1)(zeta-6)<=0 on 1<=zeta<=6",
        "CORE_CLASS_MAXIMA": {str(d): v for d, v in core_max.items()},
        "CORE_CLASS_ARGMAX": {str(d): v for d, v in argmax.items()},
        "CORE_MAXIMUM": sum(n * core_max[d] for d, n in counts.items()),
        "ZERO_MAXIMUM": zeros * zero_max,
        "SEPARABLE_MAXIMUM": separable,
        "EQUALITY": {
            "CORE_ARGMAX_SUM": sorted(core_sums),
            "ZERO_ARGMAX_SUMS": sorted(zeta_sums),
            "BALANCED": False,
            "ATTAINED": False,
        },
    }


def balanced_maximum(sigma_ranges: Ranges, zeta_range: Sequence[int]) -> dict[str, object]:
    """Exact maximum of D over every class-sorted range state with sum sigma = sum zeta."""
    counts = Counter(d for d in split.profile_values(TARGET_PROFILE) if d)
    zeros: int = split.profile_values(TARGET_PROFILE).count(0)
    core_best: dict[int, tuple[int, tuple[int, ...]]] = {}
    states = 0
    classes = sorted(counts, reverse=True)
    options = [tuple(combinations_with_replacement(sigma_ranges[d], counts[d])) for d in classes]
    for pieces in product(*options):
        states += 1
        sigma = tuple(s for piece in pieces for s in piece)
        value = sum(
            core_term(d, s) for d, piece in zip(classes, pieces, strict=True) for s in piece
        )
        if sum(sigma) not in core_best or value > core_best[sum(sigma)][0]:
            core_best[sum(sigma)] = (value, sigma)
    zero_best: dict[int, tuple[int, tuple[int, ...]]] = {}
    for zeta in combinations_with_replacement(zeta_range, zeros):
        value = sum(zero_term(v) for v in zeta)
        if sum(zeta) not in zero_best or value > zero_best[sum(zeta)][0]:
            zero_best[sum(zeta)] = (value, zeta)
    joint = {
        r: IDENTITY_CONSTANT + core_best[r][0] + zero_best[r][0]
        for r in sorted(core_best)
        if r in zero_best
    }
    top = max(joint.values())
    r_top = min(r for r, v in joint.items() if v == top)
    return {
        "CORE_STATES": states,
        "ZERO_STATES": comb(len(zeta_range) + zeros - 1, zeros),
        "MAXIMUM": top,
        "ARGMAX_R": r_top,
        "ARGMAX_SIGMA": list(core_best[r_top][1]),
        "ARGMAX_ZETA": list(zero_best[r_top][1]),
        "ROLE": "SUPPLEMENTAL_NOT_PROOF",
    }


def ablation() -> dict[str, object]:
    """Drop zeta>=1: both maxima exceed the sufficient cap, so the inequality carries the cap."""
    sigma, _zeta = legal_ranges()
    widened = range(TICKET_CAPACITY + 1)
    counts = Counter(d for d in split.profile_values(TARGET_PROFILE) if d)
    zeros: int = split.profile_values(TARGET_PROFILE).count(0)
    separable = (
        IDENTITY_CONSTANT
        + sum(n * max(core_term(d, s) for s in sigma[d]) for d, n in counts.items())
        + zeros * max(zero_term(v) for v in widened)
    )
    balanced = integer(balanced_maximum(sigma, widened)["MAXIMUM"])
    cap = sufficient_cap(route_b(SOURCE_CAP)[0], PRIORITY_THRESHOLD)
    require(
        (separable, balanced) == (291, 279) and min(separable, balanced) > cap,
        "zeta>=1 is not load-bearing",
    )
    return {
        "WITHOUT": "zeta_u>=1",
        "SEPARABLE_MAXIMUM": separable,
        "BALANCED_MAXIMUM": balanced,
        "SUFFICIENT_CAP": cap,
        "LOAD_BEARING": True,
    }


def e44_identity_points() -> int:
    """e44a635f's F equals D + sum sigma - sum zeta as a separable quadratic."""
    p = split.profile_values(TARGET_PROFILE)
    core = [d for d in p if d]
    k, z = len(core), p.count(0)
    points = three.identity_points(k, z)
    for sigma, zeta in points:
        require(
            three.split_objective(p, sigma, zeta)
            == decomposition(core, sigma, zeta) + sum(sigma) - sum(zeta),
            "e44 objective is not D + sum sigma - sum zeta",
        )
    return len(points)


def theorem() -> dict[str, object]:
    """T <= 255 for every legal support structure of the target profile."""
    facts = premises()
    cap = certify_cap(*legal_ranges())
    return {
        **facts,
        "T_COMPLEMENT": "297-t(H)",
        "T_H_IDENTITY": "54+10r-sum sigma*h-sum zeta*a+P",
        "EXACT_TRIANGLE_IDENTITY": "T=243-10r+sum sigma(7-d+sigma)+sum zeta(zeta-1)-P",
        "SEPARABLE_FORM": "T=243+sum_K sigma(sigma+3-d)+sum_Z zeta(zeta-7)-P",
        "CORE_ZERO_DECOMPOSITION": (
            "t(H)=t(M)+t(MZ)+sum_{xy in M}(6-sigma_x-sigma_y+c_Z(xy))"
            "+sum_{uw in MZ}(14-zeta_u-zeta_w+c_K(uw))"
        ),
        "P_DEFINITION": "t(M)+t(MZ)+sum_{xy in M}|N_G(x)&N_G(y)&Z|+sum_{uw in MZ}|N_G(u)&N_G(w)&K|",
        "P_NONNEGATIVE": "SUM_OF_FOUR_CARDINALITIES",
        "SUPPORT_PREMISES": [
            "20 tickets x 6 labels; 22 triple and 27 pair supports",
            "pair-linearity: all support 2-subsets distinct, so |E(G)|=93 and deg=6+d",
            "triples lie in K; K-Z edges are pair labels: 0<=sigma_x<=6-d_x",
            "zero degree 6: zeta_u<=6",
            "double count of K-Z edges: sum sigma = sum zeta = r",
        ],
        "LOAD_BEARING_INEQUALITY": "zeta_u>=1: deg_G(u)=6 > 5=|Z|-1, so zeta(zeta-7)<=-6",
        "CAP_CHAIN": "T<=243+48-36-P<=255",
        "E44_IDENTITY_POINTS_CHECKED": e44_identity_points(),
        **cap,
        "TRIANGLE_CAP": PROVED_CAP,
        "PROOF_SCOPE": "FULL_PROFILE",
        "ATTAINMENT": "NOT_ATTAINED_IN_RELAXATION; LEGAL_MAXIMUM_NOT_ASSERTED",
        "STATUS": "PROVEN",
    }


def realization_check(triples: Sequence[Support], pairs: Sequence[Support]) -> dict[str, object]:
    """A legal support structure of the target profile obeys every premise and the cap."""
    d = three.legal_degrees(triples, pairs)
    r5.validate_k20_support_realization(triples, pairs, d)
    require(chase.profile_id(split.profile_values(d)) == TARGET_PROFILE, "wrong profile")
    g = {t256.edge(x, y) for s in (*triples, *pairs) for x, y in combinations(s, 2)}
    core = [v for v in range(20) if d[v]]
    zero = [v for v in range(20) if not d[v]]
    seen = t256.complement_split(core, zero, g)
    sigma = [integer(v) for v in rows(seen["SIGMA"])]
    zeta = [integer(v) for v in rows(seen["ZETA"])]
    dc = [d[v] for v in core]
    r, p, t = sum(sigma), integer(seen["P"]), integer(seen["T_G"])
    require(
        all(0 <= s <= TICKET_CAPACITY - c for c, s in zip(dc, sigma, strict=True))
        and all(ZETA_FLOOR <= v <= TICKET_CAPACITY for v in zeta)
        and r == sum(zeta)
        and rows(seen["H_CORE"]) == [7 - c + s for c, s in zip(dc, sigma, strict=True)]
        and rows(seen["A_ZERO"]) == [v - 1 for v in zeta]
        and len(g) == 93
        and [sum(v in e for e in g) for v in range(20)] == [TICKET_CAPACITY + c for c in d],
        "cross-edge degree constraints fail",
    )
    require(
        t == GOODMAN_CONSTANT - integer(seen["T_H"])
        and integer(seen["T_H"])
        == 54
        + 10 * r
        - sum(s * (7 - c + s) for c, s in zip(dc, sigma, strict=True))
        - sum(v * (v - 1) for v in zeta)
        + p
        and t == decomposition(dc, sigma, zeta) - p
        and t <= PROVED_CAP - p <= PROVED_CAP,
        "realization violates the T255 chain",
    )
    return {"PROFILE_ID": TARGET_PROFILE, "TRIANGLES": t, "R": r, **seen}


def route_b(cap: int) -> tuple[list[Term], int]:
    """R32 envelope at cap: both implementations, then exact integers and rationals."""
    require(type(cap) is int and 22 <= cap <= SOURCE_CAP, "invalid triangle cap")
    p = split.profile_values(TARGET_PROFILE)
    terms = r32.route_b_envelope(p, cap, SOURCE_S4_BASE)
    require(terms == split.route_b_terms(p, cap, SOURCE_S4_BASE), "Route-B implementations differ")
    require(r32.K20_S1 - r32.K20_S2 == S1_MINUS_S2, "S1-S2 constant differs")
    g = [TICKET_CAPACITY + d for d in p]
    w, j = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g)
    a_exact = Fraction(sum(d * (v - 2) for d, v in zip(p, g, strict=True)), 3)
    a_max = a_exact.numerator // a_exact.denominator
    require([t[0] for t in terms] == list(range(22, cap + 1)), "triangle domain differs")
    for t, bound, k4, contained, s4, s3 in terms:
        excess = Fraction(j - (max(g) - 2) * (w - 3 * t), 4)
        k4_exact = max(0, -((-excess.numerator) // excess.denominator))
        c_exact = min(k4_exact, a_max)
        s4_exact = max(SOURCE_S4_BASE, 448 * c_exact + 679 * (k4_exact - c_exact))
        s3_exact = 2800 * w + 11872 * (t - 22) - 30800
        exact = S1_MINUS_S2 + s3_exact - Fraction(4 * s4_exact, 7)
        ceiling = -((-exact.numerator) // exact.denominator)
        require(
            (k4, contained, s4, s3, bound) == (k4_exact, c_exact, s4_exact, s3_exact, ceiling)
            and bound == S1_MINUS_S2 + s3_exact - (4 * s4_exact) // 7
            and 0 <= bound - exact < 1
            and (excess <= 0 if k4_exact == 0 else k4_exact - 1 < excess <= k4_exact)
            and a_max <= a_exact < a_max + 1,
            f"Route-B term {t} fails exact arithmetic",
        )
    require(all(a[1] < b[1] for a, b in pairwise(terms)), "Route-B envelope is not increasing")
    return terms, max(term[1] for term in terms)


def rounding_profile(terms: Sequence[Term]) -> dict[str, object]:
    """Which roundings move bounds: the K4 ceiling does; the S4 credit is always integral."""
    p = split.profile_values(TARGET_PROFILE)
    g = [TICKET_CAPACITY + d for d in p]
    w, j = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g)
    excess = {t: j - (max(g) - 2) * (w - 3 * t) for t, *_rest in terms}
    k4_active = [t for t, _b, k4, *_rest in terms if k4 > 0 and excess[t] % 4]
    integral = [t for t, _b, _k4, _c, s4, _s3 in terms if (4 * s4) % 7 == 0]
    slack = [t for t, b, _k4, _c, s4, s3 in terms if b != S1_MINUS_S2 + s3 - Fraction(4 * s4, 7)]
    require(len(integral) == len(terms) and not slack, "S4 credit is not integral")
    return {
        "K4_RULE": "K4=MAX(0,CEIL((J-(G_MAX-2)(W-3T))/4))",
        "K4_CEILING_ACTIVE_TERMS": len(k4_active),
        "A_MAX_RULE": "FLOOR(600/3)=200 EXACT",
        "S4_CREDIT_INTEGRAL_TERMS": len(integral),
        "S4_CREDIT_INTEGRAL_REASON": "679=7*97, 231=7*33, 112=7*16",
        "BOUND_CEILING_SLACK_TERMS": len(slack),
    }


def sufficient_cap(terms: Sequence[Term], threshold: int) -> int:
    """Largest cap whose whole prefix envelope stays at or below threshold."""
    best = 0
    for i in range(len(terms)):
        if max(term[1] for term in terms[: i + 1]) <= threshold:
            best = terms[i][0]
    require(best >= 22, "no cap meets the threshold")
    return best


def compute_result() -> dict[str, object]:
    provenance = module_provenance()
    frozen, ledger = frozen_authority()
    row = source_row(ledger)
    source = cap_authority()
    proof = theorem()
    sigma, zeta = legal_ranges()
    balanced = balanced_maximum(sigma, zeta)
    ablated = ablation()
    old_terms, old_bound = route_b(SOURCE_CAP)
    new_terms, new_bound = route_b(PROVED_CAP)
    peak = max(new_terms, key=lambda term: (term[1], term[0]))
    enough = sufficient_cap(old_terms, PRIORITY_THRESHOLD)
    if row.realization is None:
        raise AssertionError("target row has no recorded realization")
    recorded = realization_check(*row.realization)
    require(
        old_bound == row.bound == SOURCE_ROW_BOUND
        and new_terms == old_terms[: len(new_terms)]
        and len(new_terms) == PROVED_CAP - 21
        and peak == new_terms[-1]
        and integer(balanced["MAXIMUM"]) <= PROVED_CAP <= enough
        and new_bound <= PRIORITY_THRESHOLD
        and new_bound < old_bound,
        "Route B does not extend the frozen row authority",
    )
    actual: dict[str, object] = {
        "PROVED_T_CAP": PROVED_CAP,
        "MAX_SUFFICIENT_CAP_FOR_313395164": enough,
        "NEW_ADMISSIBLE_BOUND": new_bound,
        "OWNER_BOUND_DELTA": old_bound - new_bound,
        "ARGMAX_TERM": list(peak),
        "BALANCED_RELAXATION_MAXIMUM": balanced["MAXIMUM"],
    }
    expected: dict[str, object] = {
        "PROVED_T_CAP": 255,
        "MAX_SUFFICIENT_CAP_FOR_313395164": 263,
        "NEW_ADMISSIBLE_BOUND": 313_314_492,
        "OWNER_BOUND_DELTA": 80_852,
        "ARGMAX_TERM": [255, 313_314_492, 423, 200, 241_017, 5_062_176],
        "BALANCED_RELAXATION_MAXIMUM": 253,
    }
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "COMPLETE_FULL_PROFILE_PROOF_SELF_CHECK_ONLY",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "PROOF": __doc__,
        "FROZEN_HEAD": FROZEN_HEAD,
        "FROZEN_TREE": FROZEN_TREE,
        "FROZEN_HEAD_TREE": "MATCH",
        "FROZEN_RESULT_SHA256": FROZEN_RESULT_SHA256,
        "FROZEN_RESULT_SHA256_STATUS": "MATCH",
        "FROZEN_FAMILY": {
            k: frozen[k] for k in ("FAMILY_BOUND_AFTER", "NEXT_OWNER_IDS", "NEXT_COMPETING_BOUND")
        },
        "FROZEN_LEDGER_ROWS": len(ledger),
        "FROZEN_FULL_ROWS_SHA256": two.full_digest(ledger),
        "PROFILE_ID": TARGET_PROFILE,
        "DEGREE_DISTRIBUTION": DEGREE_DISTRIBUTION,
        "SOURCE_ROW": {
            "BOUND": row.bound,
            "CAP": row.cap,
            "S4_BASE": row.s4_base,
            "SOURCE": row.source,
            "REALIZATION_RECORDED": True,
        },
        "SOURCE_CAP_AUTHORITY": source,
        "PRIOR_ART": PRIOR_ART,
        "SUPPORT_MODEL": three.support_model(),
        "THEOREM_T255": proof,
        "ABLATION": ablated,
        "SUPPLEMENTAL_BALANCED_RELAXATION": balanced,
        "RECORDED_ROW_REALIZATION": recorded,
        "ROUTE_B": {
            "BOUND_RULE": r32.BOUND_RULE,
            "S4_BASE": SOURCE_S4_BASE,
            "CAP_BEFORE": SOURCE_CAP,
            "BOUND_BEFORE": old_bound,
            "CAP_AFTER": PROVED_CAP,
            "TERM_COUNT": len(new_terms),
            "ALL_T_TERMS": [list(t) for t in new_terms],
            "ARGMAX_TERM": list(peak),
            "ALL_T_MAX_BOUND": new_bound,
            "PREFIX_OF_CAP_264_ENVELOPE": True,
            "STRICTLY_INCREASING": True,
            "SUFFICIENT_CAP_TERMS": [list(t) for t in old_terms if t[0] >= enough],
            "ROUNDING": rounding_profile(new_terms),
            "STATUS": "PASS_INTEGER_AND_RATIONAL",
        },
        **actual,
        "EXPECTED_VALUES_MATCH": actual == expected,
        "EXPECTED_VALUE_DIFFERENCES": {
            k: {"EXPECTED": expected[k], "ACTUAL": actual[k]}
            for k in expected
            if actual[k] != expected[k]
        },
        "PRIORITY_THRESHOLD": PRIORITY_THRESHOLD,
        "PRIORITY_THRESHOLD_MET": new_bound <= PRIORITY_THRESHOLD,
        "INCUMBENT": INCUMBENT,
        "ROW_BELOW_INCUMBENT": new_bound < INCUMBENT,
        "LEDGER_ROWS_CHANGED": 0,
        "FAMILY_GAIN_CLAIMED": 0,
        "NEW_WINNING_OUTCOMES": 0,
        "MODULE_PROVENANCE": provenance,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "FROZEN_LEDGER_MUTATED": "NO",
        "HEAVY_SOLVER_STARTED": "NO",
        "SOLVER_CALLS": 0,
        "REMOTE_WRITE": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


def main() -> None:
    result = compute_result()
    payload = two.render(result)
    if RESULT_PATH.exists():
        require(RESULT_PATH.read_bytes() == payload, "existing exact result differs")
    else:
        with RESULT_PATH.open("xb") as output:
            output.write(payload)
    keys = ("PROVED_T_CAP", "NEW_ADMISSIBLE_BOUND", "OWNER_BOUND_DELTA", "EXPECTED_VALUES_MATCH")
    print(
        json.dumps(
            {**{k: result[k] for k in keys}, "RESULT": str(RESULT_PATH), "SHA256": sha256(payload)}
        )
    )


if __name__ == "__main__":
    main()
