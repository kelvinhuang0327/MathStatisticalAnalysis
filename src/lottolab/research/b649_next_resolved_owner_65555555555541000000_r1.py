"""Core-zero triangle cap T<=238 for 65555555555541000000 (14 core, 6 zero).

Support model (r5, pinned at 6569a966). Twenty tickets carry six labels each; 22 labels
have triple supports and 27 have pair supports, and every 2-subset of every support is
distinct (pair-linearity). So G (triple shadows plus pairs) has 66+27=93 edges and a
ticket in d triples has degree 2d+(6-d)=6+d. T=t(G).

Premises. d=(6,5^11,4,1,0^6): core K={d>0}, k=14; zeros Z, z=6. A triple through a zero
would give it d>0, so every triple lies in K and a K-Z edge is a pair label:
sigma_x=|N(x)&Z|<=6-d_x, i.e. 0 at d=6, {0,1} at d=5, {0,1,2} at d=4 and {0..5} at d=1.
A zero u has six pair labels, i.e. six G-neighbours, but only z-1=5 other zeros, so
zeta_u=|N(u)&K| lies in [1,6]. Both sums count the K-Z edges: r=sum sigma=sum zeta.

Goodman. H is the complement, deg_H=13-d, |E(H)|=190-93=97. Counting vertex triples by
their H-edges, t(G)=C(20,3)-18|E(H)|+sum C(13-d,2)-t(H)=1140-1746+899-t(H)=293-t(H);
Goodman's C(20,3)-sum deg_G*deg_H/2=1140-847 agrees.

Remainder. Put M=H[K], MZ=H[Z]: h_x=deg_M(x)=7-d_x+sigma_x and a_u=deg_MZ(u)=zeta_u-1,
so |M|=(32+r)/2 and |MZ|=(r-6)/2. An H triangle lies in K, lies in Z, or has exactly one
same-part edge. Over an M edge xy its Z apices number 6-sigma_x-sigma_y+c_Z(xy) with
c_Z(xy)=|N_G(x)&N_G(y)&Z|; over an MZ edge uw its K apices number 14-zeta_u-zeta_w+c_K(uw).
Summing, t(H)=6|M|+14|MZ|-sum sigma*h-sum zeta*a+P=54+10r-sum sigma*h-sum zeta*a+P with
 P=t(M)+t(MZ)+sum_M c_Z+sum_MZ c_K>=0 (four cardinalities). Hence
 T=239-10r+sum_K sigma(7-d+sigma)+sum_Z zeta(zeta-1)-P, and splitting 10r=4r+6r,
 T=D-P,  D=239+sum_K sigma(sigma+3-d)+sum_Z zeta(zeta-7).

Cap. The one load-bearing combinatorial inequality is zeta_u>=1 (pigeonhole above). On
1<=zeta<=6 the zero deficit e(zeta)=-6-zeta(zeta-7)=(zeta-1)(6-zeta) is 0 at zeta in
{1,6} and at least 4 elsewhere. Per core class sigma(sigma+3-d) peaks at 0 (d=6), 0 (d=5,
sigma=0), 2 (d=4, sigma=2) and 35 (d=1, sigma=5), 37 in all. So D=240-dK-dZ with core
deficit dK>=0 and zero deficit dZ=sum e(zeta) in {0} or [4,oo), and T<=240-P already.
D>=239 needs dZ=0, so every zeta is 1 or 6 and r is in {6,11,...,36}, and dK<=1, so
sigma_1=5, sigma_4=2 and at most one d=5 ticket has sigma=1, i.e. r is 7 or 8. These r
sets are disjoint, so D<=238 and
 T<=238-P<=238
for every legal support structure of the profile. No graphicality, sampling or search is
used. Second proof: D depends only on the per-class multisets of sigma and the multiset of
zeta, so the 216 class-sorted core states and 462 sorted zero states with equal sums cover
every legal (sigma,zeta); their exact maximum is 238, attained only at sigma_1=5,
sigma_4=1, every other sigma 0 and zeta=1^6 (r=6). Whether a legal structure attains 238
(it would also need P=0) is not asserted. Dropping zeta>=1 lets zeta=0: the separable
bound becomes 276 and the balanced maximum 268, both above the sufficient cap 264, so the
inequality is load-bearing.

Checks. e44a635f's generic F equals D+sum sigma-sum zeta, checked as a polynomial at 0,
e_i and 2e_i. The complement split is checked as a graph identity on a legal realization
of the profile built here (STS(13) less five blocks, the d=1 triple, 18 K-Z pairs and a
3-regular zero graph): r=18, D=193, P=28, T=165.

Route B (R32 envelope, S4 base 112) over 22<=T<=238 peaks at T=238: K4 295, A_MAX
floor(592/3)=197, S4 154798, S3 4849152, bound 313150736. Every term is recounted in
exact integers and rationals (K4 ceiling, A_MAX floor, S4-credit floor, bound ceiling);
the envelope strictly increases, is a prefix of the cap-265 envelope that reproduces the
frozen row bound 313392516, and its largest cap with bound <=313392412 is 264.

Authority. The frozen T256 result (6569a966) is pinned by tree and digest; the six-row
replay plus its recorded seventh update must reproduce that result's ledger digests and
family. The target row (cap 265, S4 base 112, catalog label NB_CERTIFICATES[1614]), its
cap source R30 GROUP_ATTEMPTS[3397] (CP-SAT INFEASIBLE at T=266) and the next distinct
row level 313392412 are read back and checked. No ledger row is changed and no family
gain is claimed. Prior art on other lineages is recorded, not imported or re-run.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import replace
from fractions import Fraction
from itertools import combinations, combinations_with_replacement, pairwise, product
from math import comb
from pathlib import Path

from . import b649_min_s2_next_owner_core_zero_t256_cert_r1 as t256

TASK_ID = "B649_NEXT_RESOLVED_OWNER_65555555555541000000_R1"
FROZEN_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
FROZEN_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
FROZEN_RESULT_SHA256 = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"
TARGET_PROFILE = "65555555555541000000"
DEGREE_DISTRIBUTION = "6^1,5^11,4^1,1^1,0^6"
SOURCE_CAP = 265
SOURCE_S4_BASE = 112
SOURCE_ROW_BOUND = 313_392_516
SOURCE_LABEL = "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:NB_CERTIFICATES[1614]"
CAP_ATTEMPT_INDEX = 3397
CAP_PROOF_OBJECT_SHA256 = "b6f826609608b17265d1164afd79a559f68168bdfa3cdc2502fcea53d9440b2d"
R30_RESULT_SHA256 = "9ed94532cc2bff5de1569f10561fb8340238ff3b1b1c3ae129e6a4929014f6fe"
NEXT_COMPETITOR_BOUND = 313_392_412
NEXT_COMPETITOR_OWNERS = ["66655555555431000000", "66665555544441000000"]
GOODMAN_CONSTANT = 293
IDENTITY_CONSTANT = 239
SEPARABLE_CAP = 240
PROVED_CAP = 238
TICKET_CAPACITY = 6
CORE_TERM_CONSTANT = 3
ZERO_TERM_CONSTANT = 7
ZERO_PENALTY = 6
ZETA_FLOOR = 1
S1_MINUS_S2 = 372_228_640 - 63_838_600
RESULT_STEM = "b649-next-resolved-owner-65555555555541000000-r1"
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
State = tuple[int, int, tuple[int, ...]]
# Legal realization: STS(13) on tickets 0..12 less five blocks, the d=1 ticket 13 in the
# triple {1,3,13} (pair {1,3} freed by removing (1,3,8)), 18 K-Z pairs, prism on Z.
REMOVED_STS13_BLOCKS = ((1, 2, 5), (1, 3, 8), (3, 9, 11), (4, 10, 12), (6, 7, 10))
D1_TRIPLE = (1, 3, 13)
CORE_ZERO_PAIRS = (
    (1, 15), (2, 16), (3, 17), (4, 18), (5, 19), (6, 14), (7, 15), (8, 16), (9, 17),
    (10, 14), (10, 19), (11, 18), (12, 19), (13, 14), (13, 15), (13, 16), (13, 17), (13, 18),
)  # fmt: skip
ZERO_PAIRS = (
    (14, 15), (15, 16), (14, 16), (17, 18), (18, 19), (17, 19), (14, 17), (15, 18), (16, 19),
)  # fmt: skip
PRIOR_ART: dict[str, dict[str, object]] = {
    "SAME_PROFILE_T238_ZERO_GRAPH_CASES": {
        "LOCATION": "codex worktree b649-k20-next-distinct-open-profile-r1 (uncommitted)",
        "SOURCE_HEAD": "da26b434499927f5611e3c3d12e50485f2e58a6a",
        "SOURCE_TREE": "3372fe4e4eef8321b9f8eb1232f28bb52f656e92",
        "VERIFIER_SHA256": "f8b1eabee9a6fc609ec2e72018a78b1b5123884a75e89e6396af01bf3f70e4a8",
        "CLAIM": "T+I=293, I>=55, T<=238; its own Route B gives 313115352",
        "METHOD": "per-m capacity classes and zero-graph cases (m=0..6)",
        "STATUS": "INDEPENDENT_ACCEPTANCE NOT_RUN in its result; resource verdict FAIL",
        "LINEAGE": "da26b434 is not an ancestor of the frozen head",
        "USE_HERE": "NOT_IMPORTED_NOT_RERUN; same cap, independent and shorter proof here",
    },
    "SAME_PROFILE_T249_OPEN_WEDGE": {
        "COMMIT": "c7ec944b68d3ed9edc734e5984d5eda55f22a716",
        "TREE": "fd3e8e8d60c5e58d6a4c5f4cb00b6809dd32014a",
        "CLAIM": "OW>=78, T<=249 (R30 GROUP_ATTEMPTS[3397] cap 265 replaced)",
        "STATUS": "SELF_CHECK_ONLY adoption on base e6fee5eb",
        "LINEAGE": "not an ancestor of the frozen head",
        "USE_HERE": "NOT_USED; weaker than this certificate",
    },
    "GENERIC_SPLIT_E44": {
        "COMMIT": "e44a635f1932166734aaa3f64f9469c0e63c7520",
        "STATUS": "ancestor of the frozen head; row not adopted",
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
    """The frozen target row: bound, cap, S4 base, label and (absent) realization."""
    row = ledger[TARGET_PROFILE]
    require(
        (row.bound, row.cap, row.s4_base, row.source, row.realization)
        == (SOURCE_ROW_BOUND, SOURCE_CAP, SOURCE_S4_BASE, SOURCE_LABEL, None),
        "frozen target row differs from the source premises",
    )
    return row


def next_competitor(ledger: Mapping[str, Row]) -> dict[str, object]:
    """The next distinct bound level below the source row, cursor included, and its owners."""
    cursor = (chase.prior.CURSOR_BOUND, chase.prior.CURSOR_ID)
    levels = [(row.bound, pid) for pid, row in ledger.items()] + [cursor]
    level = max(bound for bound, _pid in levels if bound < SOURCE_ROW_BOUND)
    owners = sorted(pid for bound, pid in levels if bound == level)
    above = sorted(pid for bound, pid in levels if bound > SOURCE_ROW_BOUND)
    require(
        (level, owners) == (NEXT_COMPETITOR_BOUND, NEXT_COMPETITOR_OWNERS)
        and all(pid in ledger for pid in owners),
        "next competing level differs from the packet",
    )
    return {
        "BOUND": level,
        "OWNERS": owners,
        "OWNER_ROWS": {
            pid: {
                "CAP": ledger[pid].cap,
                "S4_BASE": ledger[pid].s4_base,
                "SOURCE": ledger[pid].source,
            }
            for pid in owners
        },
        "GAP_FROM_SOURCE_ROW": SOURCE_ROW_BOUND - level,
        "FROZEN_ENTRIES_ABOVE_SOURCE_ROW": len(above),
        "CURSOR_ABOVE_SOURCE_ROW": cursor[1] in above,
        "SOURCE_ROW_IS_FROZEN_FAMILY_MAX": not above,
    }


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
    a_numerator = sum(d * (v - 2) for d, v in zip(p, g, strict=True))
    require(
        (k, z, classes, sum(p), sum(d * d for d in p))
        == (14, 6, {6: 1, 5: 11, 4: 1, 1: 1}, 66, 328)
        and g_edges == 22 * 3 + 27 == 93
        and h_edges == 97
        and phi == goodman == GOODMAN_CONSTANT
        and (m_base, mz_base) == (32, -6)
        and constant == IDENTITY_CONSTANT
        and linear == 10
        and zeta_floor == ZETA_FLOOR
        and sum(comb(v, 2) for v in g) == 827
        and sum(comb(v, 3) for v in g) == 2310
        and a_numerator == 592,
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
        "A_MAX_EXACT": f"{a_numerator}/3",
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
    """239 + sum sigma(sigma+3-d) + sum zeta(zeta-7), the separable form of D."""
    return (
        IDENTITY_CONSTANT
        + sum(core_term(d, s) for d, s in zip(core, sigma, strict=True))
        + sum(zero_term(v) for v in zeta)
    )


def core_states(sigma_ranges: Ranges) -> Iterator[State]:
    """(core sum of D-terms, r, sigma) over every class-sorted core state."""
    counts = Counter(d for d in split.profile_values(TARGET_PROFILE) if d)
    classes = sorted(counts, reverse=True)
    options = [tuple(combinations_with_replacement(sigma_ranges[d], counts[d])) for d in classes]
    for pieces in product(*options):
        sigma = tuple(s for piece in pieces for s in piece)
        value = sum(
            core_term(d, s) for d, piece in zip(classes, pieces, strict=True) for s in piece
        )
        yield value, sum(sigma), sigma


def zero_states(zeta_range: Sequence[int]) -> Iterator[State]:
    """(zero sum of D-terms, r, zeta) over every sorted zero state."""
    zeros: int = split.profile_values(TARGET_PROFILE).count(0)
    for zeta in combinations_with_replacement(zeta_range, zeros):
        yield sum(zero_term(v) for v in zeta), sum(zeta), zeta


def certify_cap(sigma_ranges: Ranges, zeta_range: Sequence[int]) -> dict[str, object]:
    """Per-coordinate reduction, the zero inequality, the 240 chain and the deficit gap."""
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
    deficit = {v: -ZERO_PENALTY - zero_term(v) for v in zeta_range}
    require(
        all(e == (v - 1) * (6 - v) and e >= 0 for v, e in deficit.items()),
        "zeta(zeta-7) <= -6 fails on the legal range",
    )
    core_max = {d: max(core_term(d, s) for s in values) for d, values in sigma_ranges.items()}
    zero_max = max(zero_term(v) for v in zeta_range)
    core_total = sum(n * core_max[d] for d, n in counts.items())
    separable = IDENTITY_CONSTANT + core_total + zeros * zero_max
    require(separable == SEPARABLE_CAP, "separable maximum is not the analytic chain cap")
    # D = SEPARABLE_CAP - dK - dZ; D > PROVED_CAP needs dK + dZ < gap on equal sums.
    gap = SEPARABLE_CAP - PROVED_CAP
    core_near: dict[int, set[int]] = {}
    for value, r, _sigma in core_states(sigma_ranges):
        if core_total - value < gap:
            core_near.setdefault(core_total - value, set()).add(r)
    zero_near: dict[int, set[int]] = {}
    for value, r, _zeta in zero_states(zeta_range):
        if zeros * zero_max - value < gap:
            zero_near.setdefault(zeros * zero_max - value, set()).add(r)
    clash = [
        (dk, dz, r)
        for dk, core_r in core_near.items()
        for dz, zero_r in zero_near.items()
        if dk + dz < gap
        for r in sorted(core_r & zero_r)
    ]
    require(gap >= 1 and not clash, "deficit gap does not close the levels above the cap")
    positive = sorted({e for e in deficit.values() if e})
    return {
        "SIGMA_RANGES": {str(d): list(v) for d, v in sigma_ranges.items()},
        "ZETA_RANGE": list(zeta_range),
        "CORE_TERM_TABLE": {
            str(d): {str(s): pair[1] for s, pair in t.items()} for d, t in reduction.items()
        },
        "ZERO_TERM_TABLE": {str(v): pair[1] for v, pair in zero_reduction.items()},
        "ZERO_INEQUALITY": "zeta(zeta-7)+6=-(zeta-1)(6-zeta)<=0 on 1<=zeta<=6",
        "ZERO_DEFICIT_TABLE": {str(v): e for v, e in deficit.items()},
        "MIN_POSITIVE_ZERO_DEFICIT": positive[0] if positive else None,
        "CORE_CLASS_MAXIMA": {str(d): v for d, v in core_max.items()},
        "CORE_MAXIMUM": core_total,
        "ZERO_MAXIMUM": zeros * zero_max,
        "SEPARABLE_MAXIMUM": separable,
        "ANALYTIC_CHAIN": f"T<={IDENTITY_CONSTANT}+{core_total}-{-zeros * zero_max}-P<={separable}",
        "DEFICIT_GAP": {
            "LEVELS_EXCLUDED": list(range(PROVED_CAP + 1, SEPARABLE_CAP + 1)),
            "CORE_NEAR_TOP_R": {str(k): sorted(v) for k, v in sorted(core_near.items())},
            "ZERO_NEAR_TOP_R": {str(k): sorted(v) for k, v in sorted(zero_near.items())},
            "BALANCED_CLASHES": len(clash),
        },
    }


def balanced_maximum(sigma_ranges: Ranges, zeta_range: Sequence[int]) -> dict[str, object]:
    """Exact maximum of D over every class-sorted range state with sum sigma = sum zeta."""
    core_best: dict[int, tuple[int, list[tuple[int, ...]]]] = {}
    core_count = 0
    for value, r, sigma in core_states(sigma_ranges):
        core_count += 1
        if r not in core_best or value > core_best[r][0]:
            core_best[r] = (value, [sigma])
        elif value == core_best[r][0]:
            core_best[r][1].append(sigma)
    zero_best: dict[int, tuple[int, list[tuple[int, ...]]]] = {}
    zero_count = 0
    for value, r, zeta in zero_states(zeta_range):
        zero_count += 1
        if r not in zero_best or value > zero_best[r][0]:
            zero_best[r] = (value, [zeta])
        elif value == zero_best[r][0]:
            zero_best[r][1].append(zeta)
    joint = {
        r: IDENTITY_CONSTANT + core_best[r][0] + zero_best[r][0]
        for r in sorted(core_best)
        if r in zero_best
    }
    top = max(joint.values())
    argmax = [
        [list(sigma), list(zeta)]
        for r, v in joint.items()
        if v == top
        for sigma in core_best[r][1]
        for zeta in zero_best[r][1]
    ]
    r_top = sorted(r for r, v in joint.items() if v == top)
    return {
        "CORE_STATES": core_count,
        "ZERO_STATES": zero_count,
        "MAXIMUM": top,
        "MAXIMUM_BY_R": {str(r): v for r, v in joint.items()},
        "ARGMAX_R": r_top,
        "ARGMAX_STATES": argmax,
        "SUPERSET_COMPLETENESS": (
            "D is a sum of per-ticket terms that depend only on (d,sigma) or zeta, so each "
            "legal (sigma,zeta) has a class-sorted image here with the same D and sum"
        ),
        "ROLE": "SECOND_PROOF_FINITE_SUPERSET_RELAXATION",
    }


def ablation(sufficient: int) -> dict[str, object]:
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
    require(
        (separable, balanced) == (276, 268) and min(separable, balanced) > sufficient,
        "zeta>=1 is not load-bearing",
    )
    return {
        "WITHOUT": "zeta_u>=1",
        "SEPARABLE_MAXIMUM": separable,
        "BALANCED_MAXIMUM": balanced,
        "SUFFICIENT_CAP": sufficient,
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
    """T <= 238 for every legal support structure of the target profile."""
    facts = premises()
    sigma, zeta = legal_ranges()
    cap = certify_cap(sigma, zeta)
    balanced = balanced_maximum(sigma, zeta)
    require(balanced["MAXIMUM"] == PROVED_CAP, "balanced maximum is not the proved cap")
    return {
        **facts,
        "T_COMPLEMENT": f"{GOODMAN_CONSTANT}-t(H)",
        "T_H_IDENTITY": "54+10r-sum sigma*h-sum zeta*a+P",
        "EXACT_TRIANGLE_IDENTITY": "T=239-10r+sum sigma(7-d+sigma)+sum zeta(zeta-1)-P",
        "SEPARABLE_FORM": "T=D-P, D=239+sum_K sigma(sigma+3-d)+sum_Z zeta(zeta-7)",
        "CORE_ZERO_DECOMPOSITION": (
            "t(H)=t(M)+t(MZ)+sum_{xy in M}(6-sigma_x-sigma_y+c_Z(xy))"
            "+sum_{uw in MZ}(14-zeta_u-zeta_w+c_K(uw))"
        ),
        "P_DEFINITION": "t(M)+t(MZ)+sum_{xy in M}|N_G(x)&N_G(y)&Z|+sum_{uw in MZ}|N_G(u)&N_G(w)&K|",
        "P_NONNEGATIVE": "SUM_OF_FOUR_CARDINALITIES",
        "SUPPORT_PREMISES": [
            "20 tickets x 6 labels; 22 triple and 27 pair supports (r5 model)",
            "pair-linearity: all support 2-subsets distinct, so |E(G)|=93 and deg=6+d",
            "triples lie in K; K-Z edges are pair labels: 0<=sigma_x<=6-d_x",
            "zero degree 6: zeta_u<=6",
            "double count of K-Z edges: sum sigma = sum zeta = r",
        ],
        "LOAD_BEARING_INEQUALITY": "zeta_u>=1: deg_G(u)=6 > 5=|Z|-1, so zeta(zeta-7)<=-6",
        "CAP_CHAIN": "T<=239+37-36-P=240-P; dZ in {0}u[4,oo) and r-set disjointness: T<=238-P",
        "E44_IDENTITY_POINTS_CHECKED": e44_identity_points(),
        **cap,
        "BALANCED_RELAXATION": balanced,
        "TRIANGLE_CAP": PROVED_CAP,
        "PROOF_SCOPE": "FULL_PROFILE",
        "ATTAINMENT": "RELAXATION_ARGMAX_UNIQUE; LEGAL_ATTAINMENT_NOT_ASSERTED",
        "STATUS": "PROVEN",
    }


def witness() -> tuple[tuple[Support, ...], tuple[Support, ...]]:
    """A legal support structure of the target profile (non-vacuity of every premise)."""
    blocks = three.sts13_blocks()
    require(all(b in blocks for b in REMOVED_STS13_BLOCKS), "removed block is not in STS(13)")
    triples = (*(b for b in blocks if b not in REMOVED_STS13_BLOCKS), D1_TRIPLE)
    return triples, (*CORE_ZERO_PAIRS, *ZERO_PAIRS)


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
        "realization violates the T238 chain",
    )
    return {
        "PROFILE_ID": TARGET_PROFILE,
        "TRIANGLES": t,
        "R": r,
        "D": decomposition(dc, sigma, zeta),
        **seen,
    }


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
    """Which roundings bind: the K4 ceiling and the A_MAX floor; the S4 credit is integral."""
    p = split.profile_values(TARGET_PROFILE)
    g = [TICKET_CAPACITY + d for d in p]
    w, j = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g)
    a_exact = Fraction(sum(d * (v - 2) for d, v in zip(p, g, strict=True)), 3)
    excess = {t: j - (max(g) - 2) * (w - 3 * t) for t, *_rest in terms}
    k4_active = [t for t, _b, k4, *_rest in terms if k4 > 0 and excess[t] % 4]
    a_binding = [t for t, _b, k4, c, *_rest in terms if c < k4 and c < a_exact]
    integral = [t for t, _b, _k4, _c, s4, _s3 in terms if (4 * s4) % 7 == 0]
    slack = [t for t, b, _k4, _c, s4, s3 in terms if b != S1_MINUS_S2 + s3 - Fraction(4 * s4, 7)]
    require(len(integral) == len(terms) and not slack, "S4 credit is not integral")
    return {
        "K4_RULE": "K4=MAX(0,CEIL((J-(G_MAX-2)(W-3T))/4))",
        "K4_CEILING_ACTIVE_TERMS": len(k4_active),
        "A_MAX_RULE": f"FLOOR({a_exact.numerator}/{a_exact.denominator})={int(a_exact)}",
        "A_MAX_FLOOR_BINDING_TERMS": len(a_binding),
        "S4_CREDIT_INTEGRAL_TERMS": len(integral),
        "S4_CREDIT_INTEGRAL_REASON": "448=7*64, 679=7*97, 112=7*16",
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


def frozen_family_if_installed(ledger: Mapping[str, Row], bound: int) -> dict[str, object]:
    """Counterfactual on a copy: the frozen family max does not move (no gain claimed)."""
    old = ledger[TARGET_PROFILE]
    require(type(bound) is int and bound < old.bound, "update must tighten the row")
    before = two.full_digest(ledger)
    after = dict(ledger)
    after[TARGET_PROFILE] = replace(old, bound=bound, cap=PROVED_CAP, source=f"{TASK_ID}:T238")
    require(
        [p for p in ledger if ledger[p] != after[p]] == [TARGET_PROFILE]
        and two.full_digest(ledger) == before,
        "counterfactual changed another row or the frozen ledger",
    )
    best_before, owners_before, _ = three.family(ledger)
    best_after, owners_after, _ = three.family(after)
    return {
        "FAMILY_BEFORE": best_before,
        "FAMILY_OWNERS_BEFORE": owners_before,
        "FAMILY_IF_INSTALLED": best_after,
        "FAMILY_OWNERS_IF_INSTALLED": owners_after,
        "FAMILY_DELTA": best_before - best_after,
        "STATUS": "COUNTERFACTUAL_COPY_NOT_INSTALLED",
    }


def compute_result() -> dict[str, object]:
    provenance = module_provenance()
    frozen, ledger = frozen_authority()
    row = source_row(ledger)
    competitor = next_competitor(ledger)
    source = cap_authority()
    proof = theorem()
    old_terms, old_bound = route_b(SOURCE_CAP)
    new_terms, new_bound = route_b(PROVED_CAP)
    peak = max(new_terms, key=lambda term: (term[1], term[0]))
    enough = sufficient_cap(old_terms, NEXT_COMPETITOR_BOUND)
    ablated = ablation(enough)
    recorded = realization_check(*witness())
    counterfactual = frozen_family_if_installed(ledger, new_bound)
    require(
        old_bound == row.bound == SOURCE_ROW_BOUND
        and new_terms == old_terms[: len(new_terms)]
        and len(new_terms) == PROVED_CAP - 21
        and peak == new_terms[-1]
        and enough >= PROVED_CAP
        and new_bound <= NEXT_COMPETITOR_BOUND < old_bound,
        "Route B does not extend the frozen row authority",
    )
    actual: dict[str, object] = {
        "PROVED_T_CAP": PROVED_CAP,
        "SUFFICIENT_CAP_FOR_NEXT_COMPETITOR": enough,
        "NEW_ADMISSIBLE_BOUND": new_bound,
        "OWNER_BOUND_DELTA": old_bound - new_bound,
        "ARGMAX_TERM": list(peak),
        "SEPARABLE_CHAIN_CAP": proof["SEPARABLE_MAXIMUM"],
        "WITNESS_TRIANGLES": recorded["TRIANGLES"],
    }
    expected: dict[str, object] = {
        "PROVED_T_CAP": 238,
        "SUFFICIENT_CAP_FOR_NEXT_COMPETITOR": 264,
        "NEW_ADMISSIBLE_BOUND": 313_150_736,
        "OWNER_BOUND_DELTA": 241_780,
        "ARGMAX_TERM": [238, 313_150_736, 295, 197, 154_798, 4_849_152],
        "SEPARABLE_CHAIN_CAP": 240,
        "WITNESS_TRIANGLES": 165,
    }
    rounding = rounding_profile(new_terms)
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
        "GOODMAN_CONSTANT": GOODMAN_CONSTANT,
        "CORE_COUNT": proof["CORE_VERTICES"],
        "ZERO_COUNT": proof["ZERO_VERTICES"],
        "SOURCE_ROW": {
            "BOUND": row.bound,
            "CAP": row.cap,
            "S4_BASE": row.s4_base,
            "SOURCE": row.source,
            "REALIZATION_RECORDED": row.realization is not None,
        },
        "SOURCE_T_CAP": row.cap,
        "SOURCE_S4_BASE": row.s4_base,
        "SOURCE_OLD_BOUND": row.bound,
        "SOURCE_PROOF_LOCATOR": f"{R30_RESULT_PATH}:GROUP_ATTEMPTS[{CAP_ATTEMPT_INDEX}]",
        "SOURCE_CAP_AUTHORITY": source,
        "NEXT_COMPETITOR": competitor,
        "NEXT_COMPETITOR_BOUND": competitor["BOUND"],
        "NEXT_COMPETITOR_OWNERS": competitor["OWNERS"],
        "PRIOR_ART": PRIOR_ART,
        "SUPPORT_MODEL": three.support_model(),
        "THEOREM_T238": proof,
        "EXACT_TRIANGLE_IDENTITY": proof["EXACT_TRIANGLE_IDENTITY"],
        "NONNEGATIVE_REMAINDER": proof["P_DEFINITION"],
        "SUPPORT_PREMISES": proof["SUPPORT_PREMISES"],
        "LOAD_BEARING_INEQUALITY": proof["LOAD_BEARING_INEQUALITY"],
        "PROOF_SCOPE": proof["PROOF_SCOPE"],
        "RELAXATION_SUPERSET_COMPLETENESS": object_row(proof["BALANCED_RELAXATION"])[
            "SUPERSET_COMPLETENESS"
        ],
        "COUNTEREXAMPLE_STATUS": "NONE; the cap is proved and the legal witness has T=165",
        "UNPROVED_ASSUMPTIONS": (
            "NONE_NEW; inherited and pinned at the frozen head: the r5 22-triple/27-pair "
            "support model and the R32 Route-B bound rule"
        ),
        "ABLATION": ablated,
        "LEGAL_WITNESS_REALIZATION": recorded,
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
            "PREFIX_OF_CAP_265_ENVELOPE": True,
            "STRICTLY_INCREASING": True,
            "SUFFICIENT_CAP_TERMS": [list(t) for t in old_terms if t[0] >= enough],
            "ROUNDING": rounding,
            "STATUS": "PASS_INTEGER_AND_RATIONAL",
        },
        "ROUTE_B_INTEGER_RECOUNT": (
            f"PASS ({len(old_terms)} cap-265 terms; prefix {len(new_terms)})"
        ),
        "EXACT_RATIONAL_CHECK": "PASS (0 <= bound - exact < 1 and no ceiling slack)",
        "ROUNDING_CHECK": rounding,
        **actual,
        "EXPECTED_VALUES_MATCH": actual == expected,
        "EXPECTED_VALUE_DIFFERENCES": {
            k: {"EXPECTED": expected[k], "ACTUAL": actual[k]}
            for k in expected
            if actual[k] != expected[k]
        },
        "BELOW_NEXT_COMPETITOR": new_bound < NEXT_COMPETITOR_BOUND,
        "INCUMBENT": INCUMBENT,
        "ROW_BELOW_INCUMBENT": new_bound < INCUMBENT,
        "FROZEN_FAMILY_COUNTERFACTUAL": counterfactual,
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
