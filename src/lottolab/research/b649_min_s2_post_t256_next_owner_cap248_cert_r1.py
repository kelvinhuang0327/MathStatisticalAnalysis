"""Degree-square cap T<=248 for 66655555555521000000, then the eight-row min-S2 family.

Support model (r5, pinned through 6569a966). Twenty tickets carry six labels each: 22
labels have triple supports and 27 have pair supports. Every 2-subset of every support is
distinct, so G (shadow plus pairs) is simple with 66+27=93 edges and deg(v)=6+d_v, where
d_v counts the triples through v. T=t(G).

Premises. d=(6^3,5^9,2,1,0^6): core K={d>0}, k=14; zeros Z, z=6. A triple through a zero
would give it d>0, so all triples lie in K and G[K] has 66 shadow edges plus p pair edges.
A core x reaches Z only through its 6-d_x pair labels: sigma_x<=6-d_x, i.e. 0 at d=6,
{0,1} at d=5, {0..4} at d=2 and {0..5} at d=1. A zero u has six pair labels, so six
distinct neighbours: zeta_u in K and 6-zeta_u<=z-1=5 in Z, hence 1<=zeta_u<=6. Both sums
count the K-Z edges: r=sum sigma=sum zeta. With e_Z the G edges inside Z, the 27 pairs
give p+r+e_Z=27 and the zero degrees give 6z=36=r+2e_Z, so e_Z=18-r/2, p=9-r/2, r is
even and 6<=r<=18.

Complement. H is the complement, deg_H=13-d. Goodman gives t(G)+t(H)=C(20,3)
-sum(6+d)(13-d)/2=1140-842=298, as does 1140-18|E(H)|+sum C(13-d,2) with |E(H)|=97.
Put M=H[K], MZ=H[Z]: |M|=C(14,2)-66-p=16+r/2, |MZ|=15-e_Z=e:=(r-6)/2,
deg_M(x)=7-d_x+sigma_x and deg_MZ(u)=mu_u:=zeta_u-1. Over an M edge xy its Z apices
number z-sigma_x-sigma_y+c_Z(xy); over an MZ edge uw its K apices number
k-zeta_u-zeta_w+c_K(uw). Summing (the T256 identity, valid for any graph and split),
 t(H)=z|M|+k|MZ|-sum sigma*deg_M-sum zeta*mu+P,  P=t(M)+t(MZ)+sum_M c_Z+sum_MZ c_K>=0,
and z|M|+k|MZ|=96+3r+7r-42=54+10r. With sum sigma=sum zeta=r,
 T=298-t(H)=244+sum_x sigma_x(sigma_x-d_x-4)+sum_u zeta_u^2-P.

Restriction (the one new step). MZ is a graph with e edges and degrees mu. For each MZ
edge uw the MZ edges meeting it number mu_u+mu_w-1<=e, so
sum mu^2=sum_{uw in MZ}(mu_u+mu_w)<=e(e+1). As sum mu=2e,
 sum zeta^2=6+4e+sum mu^2<=(e+2)(e+3)=r(r-2)/4.

Cap. The core sum depends only on s1=sigma at d=1, s2=sigma at d=2 and n=#{d=5: sigma=1}
(each such vertex adds -8; d=6 adds 0):
 T<=244+s1(s1-5)+s2(s2-6)-8n+r(r-2)/4-P,  r=s1+s2+n even, 6<=r<=18.
All 6*5*10=300 integer triples are enumerated exactly. Without P the right side peaks at
248, only at (s1,s2,n)=(5,4,1) with r=10; the maxima for r=6,8,...,18 are 245, 247, 248,
242, 238, 236 and 236. Since P>=0, T<=248 for every legal support structure. No
graphicality test, sampling or search is used. Equality would need P=0, r=10 and MZ a
two-edge path; attainment is not asserted.

Checks. The reduction to the closed form is checked as an identity at every class-sorted
legal (sigma, zeta) with equal sums. The degree-square lemma is re-checked on all 2^15
graphs on six labelled vertices. Their exact maxima of sum zeta^2 give the same cap 248
(supplemental). With only 1<=zeta<=6 and no lemma the relaxation reaches 258 (ablation), so
the lemma is load-bearing. The recorded row realization is checked against every premise,
the identity and the cap. Route B (R32 envelope; integer, exact rational, and the e44 and
R32 implementations) at the row's S4 base 112 for 22<=T<=248 peaks at T=248. It is a
prefix of the cap-264 envelope, which reproduces the recorded row bound 313398532.

Ledger. The seven-row authority (6569a966; its commit records a fresh-context Judge verdict
of VERIFIED_WITH_CAVEATS) is pinned by tree and result digest. It is rebuilt from its own
six-row replay plus its one T256 row and must reproduce its stored digests. Exactly one row
changes, in a copy, and keeps its S4 base and realization. The family maximum over all rows
and the unchanged cursor is recomputed with every tied owner. Inherited statuses and caveats
are copied verbatim. Global K20 optimality is unknown. No solver or search is run.
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

from . import b649_min_s2_next_owner_core_zero_t256_cert_r1 as t256

TASK_ID = "B649_MIN_S2_POST_T256_NEXT_OWNER_SINGLE_EXACT_PROOF_R1"
BASE_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
BASE_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
T256_RESULT_SHA256 = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"
T256_JUDGE_RECORD = "Fresh-context Judge: VERIFIED_WITH_CAVEATS on tree 986d2085."
TARGET_PROFILE = "66655555555521000000"
CURRENT_CAP = 264
PROPOSED_CAP = 248
S4_BASE = 112
SEVEN_ROW_BOUND = 313_398_532
TICKET_CAPACITY = 6
GOODMAN_CONSTANT = 298
REDUCED_CONSTANT = 244
CORE_SHIFT = 4
ABLATION_CAP = 258
RESULT_STEM = "b649-min-s2-post-t256-next-owner-cap248-cert-r1"
six, three, two, chase = t256.six, t256.three, t256.two, t256.chase
split, r32, r5 = t256.split, t256.r32, t256.r5
ROOT = two.ROOT
RESULT_PATH = ROOT / two.RESULT_DIRECTORY / f"{RESULT_STEM}-result.json"
T256_RESULT_PATH = f"{two.RESULT_DIRECTORY}/{t256.RESULT_STEM}-result.json"
require, sha256 = two.require, two.sha256
integer, object_row, rows, text = two.integer, two.object_row, two.rows, two.text
INCUMBENT = two.INCUMBENT
Row = chase.Row
Support = tuple[int, ...]
Term = tuple[int, int, int, int, int, int]
Ranges = Mapping[int, Sequence[int]]
PRIOR_ART = {
    "STATUS": "INFORMAL_SCRATCH_ONLY_NOT_A_FORMAL_CERTIFICATE",
    "TASK_ID": "B649_K20_NEXT_UNCLOSED_CERTIFIED_PROFILE_BOUND_R1",
    "LOCATION": "uncommitted .task-data of a Codex worktree detached at 2e6b8879",
    "SCRIPT_SHA256": "7df411ab67536c315ee36536c4c47a089d3a50a863fd3f44e0c2fa259dcf80c7",
    "RESULT_SHA256": "2c50c349360007a2745c697f51d46ad8aaaefd4408f85956b0cd5b55e6b245dd",
    "CLAIMED_CAP": 248,
    "METHOD": "Goodman complement bound with an Erdos-Gallai test on Z",
    "JUDGE": "NONE",
    "USE_HERE": "METHOD_REUSED_EG_REPLACED_BY_DEGREE_SQUARE_LEMMA_NOT_ADOPTED_AS_AUTHORITY",
    "OBSERVATION": "RECORDED_AT_TASK_TIME_NOT_READ_BY_THIS_MODULE",
}


def module_provenance() -> dict[str, str]:
    """Every module this certificate calls equals its 6569a966 blob, byte for byte."""
    out: dict[str, str] = {}
    for module in (t256, six, six.five, six.five.four, three, two, chase, split, r32, r5):
        require(module.__file__ is not None, "reused module has no source")
        source = Path(text(module.__file__)).resolve()
        require(source.is_relative_to(ROOT), "reused module outside this worktree")
        relative = source.relative_to(ROOT).as_posix()
        committed = chase.git("show", f"{BASE_HEAD}:{relative}")
        require(source.read_bytes() == committed, f"reused source changed: {relative}")
        out[relative] = sha256(committed)
    return dict(sorted(out.items()))


def core_degrees() -> list[int]:
    return [d for d in split.profile_values(TARGET_PROFILE) if d]


def zero_count() -> int:
    return split.profile_values(TARGET_PROFILE).count(0)


def relations(r: int) -> tuple[int, int, int, int]:
    """(p, e_Z, |M|, |MZ|) forced by the 27 pairs and the zero degrees at K-Z count r."""
    k, z = len(core_degrees()), zero_count()
    require((TICKET_CAPACITY * z - r) % 2 == 0, "odd zero-degree remainder")
    e_z = (TICKET_CAPACITY * z - r) // 2
    p = 27 - r - e_z
    return p, e_z, comb(k, 2) - 66 - p, comb(z, 2) - e_z


def legal_r() -> list[int]:
    """K-Z counts with an integral e_Z and nonnegative p, e_Z and |MZ|."""
    even = range(TICKET_CAPACITY * zero_count() % 2, 2 * 27 + 1, 2)
    return [r for r in even if min(*relations(r)[:2], relations(r)[3]) >= 0]


def premises() -> dict[str, object]:
    """Profile split, edge counts, Goodman two ways, and the linear relations in r."""
    p = split.profile_values(TARGET_PROFILE)
    require(chase.profile_id(p) == TARGET_PROFILE, "theorem is stated for one profile only")
    core = core_degrees()
    k, z = len(core), zero_count()
    degree_sum = sum(TICKET_CAPACITY + d for d in p)
    require(degree_sum % 2 == 0, "odd G degree sum")
    g_edges = degree_sum // 2
    h_edges = comb(20, 2) - g_edges
    phi = comb(20, 3) - 18 * h_edges + sum(comb(13 - d, 2) for d in p)
    goodman = Fraction(comb(20, 3)) - Fraction(sum((TICKET_CAPACITY + d) * (13 - d) for d in p), 2)
    classes = dict(sorted(Counter(core).items(), reverse=True))
    rs = legal_r()
    linear = {r: z * relations(r)[2] + k * relations(r)[3] for r in rs}
    # T = 298 - (54 + 10r) + sum s(k-7-d+s) + sum v(v+z-7): the r coefficient folds to -4.
    shift = 10 + (7 - z) - (k - 7)
    require(
        (k, z, classes, sum(p)) == (14, 6, {6: 3, 5: 9, 2: 1, 1: 1}, 66)
        and core == [d for d, n in classes.items() for _ in range(n)]
        and g_edges == 22 * 3 + 27 == 93
        and h_edges == 97
        and phi == goodman == GOODMAN_CONSTANT
        and rs == list(range(6, 19, 2))
        and all(relations(r)[2:] == (16 + r // 2, (r - 6) // 2) for r in rs)
        and all(v == 54 + 10 * r for r, v in linear.items())
        and GOODMAN_CONSTANT - 54 == REDUCED_CONSTANT
        and shift == CORE_SHIFT,
        "cap-248 premises fail",
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
        "LEGAL_R": rs,
        "RELATIONS_P_EZ_M_MZ": {str(r): list(relations(r)) for r in rs},
        "Z_TIMES_M_PLUS_K_TIMES_MZ": "54+10r",
        "REDUCED_CONSTANT": REDUCED_CONSTANT,
        "CORE_SHIFT": shift,
    }


def legal_ranges() -> tuple[dict[int, range], range]:
    """sigma_x<=6-d_x (pair labels only reach Z); 1<=zeta_u<=6 (six neighbours, five zeros)."""
    sigma = {d: range(TICKET_CAPACITY - d + 1) for d in sorted(set(core_degrees()), reverse=True)}
    return sigma, range(TICKET_CAPACITY - (zero_count() - 1), TICKET_CAPACITY + 1)


def sigma_vectors(sigma_ranges: Ranges) -> Iterator[tuple[int, ...]]:
    """Class-sorted sigma over the given ranges, in the profile's core order."""
    counts = Counter(core_degrees())
    require(set(sigma_ranges) == set(counts), "unexpected range shape")
    options = [tuple(combinations_with_replacement(sigma_ranges[d], counts[d])) for d in counts]
    for pieces in product(*options):
        yield tuple(s for piece in pieces for s in piece)


def core_term(core: Sequence[int], sigma: Sequence[int]) -> int:
    return sum(s * (s - d - CORE_SHIFT) for d, s in zip(core, sigma, strict=True))


def objective(core: Sequence[int], sigma: Sequence[int], zeta: Sequence[int]) -> int:
    """244 + sum sigma(sigma-d-4) + sum zeta^2, which equals T + P."""
    return REDUCED_CONSTANT + core_term(core, sigma) + sum(v * v for v in zeta)


def complement_form(core: Sequence[int], sigma: Sequence[int], zeta: Sequence[int]) -> int:
    """298 - (z|M| + k|MZ| - sum sigma deg_M - sum zeta mu), before any simplification."""
    k, z = len(core), len(zeta)
    _p, _e_z, m, mz = relations(sum(sigma))
    deg_m = [k - 7 - d + s for d, s in zip(core, sigma, strict=True)]
    mu = [v + z - 7 for v in zeta]
    return GOODMAN_CONSTANT - (
        z * m
        + k * mz
        - sum(s * h for s, h in zip(sigma, deg_m, strict=True))
        - sum(v * a for v, a in zip(zeta, mu, strict=True))
    )


def identity_check() -> dict[str, object]:
    """The closed form equals the complement form at every legal class-sorted point."""
    sigma_ranges, zeta_range = legal_ranges()
    core, rs = core_degrees(), set(legal_r())
    by_sum: dict[int, list[tuple[int, ...]]] = {}
    for zeta in combinations_with_replacement(zeta_range, zero_count()):
        by_sum.setdefault(sum(zeta), []).append(zeta)
    points = 0
    for sigma in sigma_vectors(sigma_ranges):
        if sum(sigma) not in rs:
            continue
        for zeta in by_sum.get(sum(sigma), []):
            require(
                complement_form(core, sigma, zeta) == objective(core, sigma, zeta),
                "closed form differs from the complement form",
            )
            points += 1
    require(points > 0, "identity domain is empty")
    return {"POINTS_CHECKED": points, "STATUS": "PASS"}


def degree_square_lemma() -> tuple[dict[int, int], dict[str, object]]:
    """sum mu^2 <= e(e+1) on every graph on Z, and the exact sum zeta^2 maxima per e."""
    z = zero_count()
    slots = list(combinations(range(z), 2))
    exact: dict[int, int] = {}
    for mask in range(1 << len(slots)):
        mu = [0] * z
        for i, (a, b) in enumerate(slots):
            if mask >> i & 1:
                mu[a] += 1
                mu[b] += 1
        e = sum(mu) // 2
        squares = sum(v * v for v in mu)
        require(squares <= e * (e + 1), "degree-square lemma fails")
        zeta_squares = sum((1 + v) ** 2 for v in mu)
        require(zeta_squares == z + 4 * e + squares, "sum zeta^2 expansion fails")
        exact[e] = max(exact.get(e, 0), zeta_squares)
    lemma = {e: (e + 2) * (e + 3) for e in exact}
    require(
        z == 6 and all(exact[e] <= lemma[e] for e in exact),
        "lemma bound below an exact maximum",
    )
    return exact, {
        "GRAPHS_CHECKED": 1 << len(slots),
        "EXACT_MAX_SUM_ZETA_SQUARED": {str(e): v for e, v in sorted(exact.items())},
        "LEMMA_BOUND": {str(e): v for e, v in sorted(lemma.items())},
    }


def lemma_bounds() -> dict[int, int]:
    """(e+2)(e+3) at every legal MZ edge count e=(r-6)/2."""
    return {relations(r)[3]: (relations(r)[3] + 2) * (relations(r)[3] + 3) for r in legal_r()}


def range_only_bounds() -> dict[int, int]:
    """Ablation: the largest sum zeta^2 from 1<=zeta<=6 and sum zeta=r alone."""
    _sigma, zeta_range = legal_ranges()
    out: dict[int, int] = {}
    for zeta in combinations_with_replacement(zeta_range, zero_count()):
        r = sum(zeta)
        if r in legal_r():
            e = relations(r)[3]
            out[e] = max(out.get(e, 0), sum(v * v for v in zeta))
    return out


def relaxation(
    sigma_ranges: Ranges, zero_bounds: Mapping[int, int]
) -> tuple[int, dict[int, int], list[tuple[int, ...]]]:
    """max over legal class-sorted sigma of 244 + core term + zero bound at e=(r-6)/2."""
    core, rs = core_degrees(), set(legal_r())
    per_r: dict[int, int] = {}
    values: dict[tuple[int, ...], int] = {}
    for sigma in sigma_vectors(sigma_ranges):
        r = sum(sigma)
        if r not in rs:
            continue
        value = REDUCED_CONSTANT + core_term(core, sigma) + zero_bounds[relations(r)[3]]
        values[sigma] = value
        per_r[r] = max(per_r.get(r, value), value)
    best = max(values.values())
    return best, dict(sorted(per_r.items())), [s for s, v in values.items() if v == best]


def certify_cap(sigma_ranges: Ranges, zero_bounds: Mapping[int, int]) -> dict[str, object]:
    """Exhaustive exact enumeration of the reduced bound; every value is at most 248."""
    best, per_r, top = relaxation(sigma_ranges, zero_bounds)
    require(best <= PROPOSED_CAP, "relaxation maximum exceeds 248")
    require(best == PROPOSED_CAP, "relaxation maximum below 248: the cap is not tight here")
    core = core_degrees()
    argmax = [
        {
            "S1": next(s for d, s in zip(core, sigma, strict=True) if d == 1),
            "S2": next(s for d, s in zip(core, sigma, strict=True) if d == 2),
            "N5": sum(s for d, s in zip(core, sigma, strict=True) if d == 5),
            "R": sum(sigma),
        }
        for sigma in top
    ]
    require(argmax == [{"S1": 5, "S2": 4, "N5": 1, "R": 10}], "argmax changed")
    return {
        "SIGMA_RANGES": {str(d): list(v) for d, v in sigma_ranges.items()},
        "SIGMA_VECTORS_CHECKED": sum(1 for _ in sigma_vectors(sigma_ranges)),
        "MAX_BY_R": {str(r): v for r, v in per_r.items()},
        "RELAXATION_MAXIMUM": best,
        "ARGMAX": argmax,
        "EQUALITY_CONDITIONS": {"P": 0, "R": 10, "MZ": "TWO_EDGE_PATH"},
    }


def cap_theorem() -> dict[str, object]:
    """T <= 248 for every legal structure of the target profile, by the proof above."""
    facts = premises()
    identity = identity_check()
    exact_bounds, lemma = degree_square_lemma()
    sigma_ranges, zeta_range = legal_ranges()
    require(
        list(zeta_range) == list(range(1, 7))
        and {d: list(v) for d, v in sigma_ranges.items()}
        == {6: [0], 5: [0, 1], 2: list(range(5)), 1: list(range(6))},
        "legal ranges changed",
    )
    cap = certify_cap(sigma_ranges, lemma_bounds())
    exact_best, exact_per_r, _top = relaxation(sigma_ranges, exact_bounds)
    ablation_best, ablation_per_r, _ = relaxation(sigma_ranges, range_only_bounds())
    require(
        exact_best == PROPOSED_CAP and ablation_best == ABLATION_CAP > PROPOSED_CAP,
        "supplemental or ablation maximum changed",
    )
    return {
        **facts,
        "T_COMPLEMENT": "298-t(H)",
        "T_H_IDENTITY": "z|M|+k|MZ|-sum sigma*deg_M-sum zeta*mu+P",
        "T_CLOSED_FORM": "244+sum sigma(sigma-d-4)+sum zeta^2-P",
        "P_DEFINITION": "t(M)+t(MZ)+sum_{xy in M}|N_G(x)&N_G(y)&Z|+sum_{uw in MZ}|N_G(u)&N_G(w)&K|",
        "P_NONNEGATIVE": "SUM_OF_FOUR_CARDINALITIES",
        "ZETA_RANGE": list(zeta_range),
        "CLOSED_FORM_IDENTITY": identity,
        "RESTRICTION": "SUM_MU_SQUARED_LE_E_TIMES_E_PLUS_1_ON_MZ",
        "ZERO_TERM_BOUND": "sum zeta^2<=(e+2)(e+3)=r(r-2)/4",
        "DEGREE_SQUARE_LEMMA": lemma,
        **cap,
        "SUPPLEMENTAL_EXACT_Z_GRAPHS": {
            "MAX_BY_R": {str(r): v for r, v in exact_per_r.items()},
            "MAXIMUM": exact_best,
            "ROLE": "SUPPLEMENTAL_NOT_PROOF",
        },
        "ABLATION_RANGE_ONLY_ZETA": {
            "MAX_BY_R": {str(r): v for r, v in ablation_per_r.items()},
            "MAXIMUM": ablation_best,
            "ROLE": "SHOWS_LEMMA_IS_LOAD_BEARING",
        },
        "TRIANGLE_CAP": PROPOSED_CAP,
        "ATTAINMENT": "NOT_ASSERTED",
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
    r, e = sum(sigma), integer(seen["MZ_EDGES"])
    p, t = integer(seen["P"]), integer(seen["T_G"])
    mu = [v - 1 for v in zeta]
    require(
        all(0 <= s <= TICKET_CAPACITY - c for c, s in zip(dc, sigma, strict=True))
        and all(1 <= v <= TICKET_CAPACITY for v in zeta)
        and r == sum(zeta)
        and r in legal_r()
        and (integer(seen["M_EDGES"]), e) == relations(r)[2:]
        and rows(seen["H_CORE"]) == [7 - c + s for c, s in zip(dc, sigma, strict=True)]
        and rows(seen["A_ZERO"]) == mu
        and len(g) == 93
        and [sum(v in x for x in g) for v in range(20)] == [TICKET_CAPACITY + c for c in d],
        "cross-edge degree constraints fail",
    )
    bound = REDUCED_CONSTANT + core_term(dc, sigma) + (e + 2) * (e + 3)
    require(
        t == GOODMAN_CONSTANT - integer(seen["T_H"])
        and t == objective(dc, sigma, zeta) - p == complement_form(dc, sigma, zeta) - p
        and sum(v * v for v in mu) <= e * (e + 1)
        and t <= bound - p
        and bound <= PROPOSED_CAP,
        "realization violates the T248 chain",
    )
    return {
        "PROFILE_ID": TARGET_PROFILE,
        "TRIANGLES": t,
        "R": r,
        "CHAIN_BOUND_WITHOUT_P": bound,
        **seen,
    }


def route_b(cap: int, base: int = S4_BASE) -> tuple[list[Term], int]:
    """R32 envelope at cap: both implementations, then exact integers and rationals."""
    p = split.profile_values(TARGET_PROFILE)
    terms = r32.route_b_envelope(p, cap, base)
    require(terms == split.route_b_terms(p, cap, base), "Route-B implementations differ")
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
    return terms, max(term[1] for term in terms)


def required_improvement(old_terms: Sequence[Term]) -> dict[str, object]:
    """The smallest cap cut and the smallest S4 floor that lower the cap-264 row bound."""
    cap_terms, cap_bound = route_b(CURRENT_CAP - 1)
    peak = max(old_terms, key=lambda term: (term[1], term[0]))
    require(peak[0] == CURRENT_CAP and cap_bound < SEVEN_ROW_BOUND, "cap 263 does not tighten")
    floor = S4_BASE
    while route_b(CURRENT_CAP, floor)[1] >= SEVEN_ROW_BOUND:
        floor = max(floor + 1, peak[4])
    require(route_b(CURRENT_CAP, floor - 1)[1] >= SEVEN_ROW_BOUND, "S4 floor is not minimal")
    return {
        "PEAK_TERM_AT_CAP_264": list(peak),
        "MIN_CAP_REDUCTION": 1,
        "BOUND_AT_CAP_263": cap_bound,
        "CAP_263_TERM_COUNT": len(cap_terms),
        "MIN_S4_FLOOR_AT_CAP_264": floor,
        "S4_FLOOR_BEFORE": S4_BASE,
    }


def seven_row_authority() -> tuple[dict[str, object], dict[str, Row]]:
    """The pinned 6569a966 result, rebuilt from its own six-row replay plus its T256 row."""
    require(three.git_tree(BASE_HEAD) == BASE_TREE, "T256 base tree mismatch")
    raw = two.blob(BASE_HEAD, T256_RESULT_PATH, T256_RESULT_SHA256)
    require((ROOT / T256_RESULT_PATH).read_bytes() == raw, "T256 result changed")
    stem = t256.__name__.rsplit(".", 1)[1]
    for path in (f"src/lottolab/research/{stem}.py", f"tests/unit/test_{stem}.py"):
        require(
            (ROOT / path).read_bytes() == chase.git("show", f"{BASE_HEAD}:{path}"),
            "T256 source or tests changed",
        )
    message = chase.git("log", "-1", "--format=%B", BASE_HEAD).decode()
    require(T256_JUDGE_RECORD in message.splitlines(), "T256 Judge record missing")
    result = object_row(json.loads(raw))
    six_result, six_ledger = t256.six_row_authority()
    after = object_row(object_row(result["ROW_UPDATE"])["AFTER"])
    ledger = t256.apply_seventh(
        six_ledger, integer(after["bound"]), integer(after["cap"]), text(after["source"])
    )
    require(
        len(ledger) == result["LEDGER_ROWS"] == 4647
        and two.full_digest(six_ledger) == result["FULL_ROWS_SHA256_BEFORE"]
        and two.full_digest(ledger) == result["FULL_ROWS_SHA256_AFTER"]
        and two.bounds_digest(ledger) == result["BOUNDS_SHA256_AFTER"]
        and json.loads(json.dumps(asdict(ledger[t256.TARGET_PROFILE]))) == after
        and list(three.family(ledger))
        == [result[k] for k in ("FAMILY_BOUND_AFTER", "NEXT_OWNER_IDS", "NEXT_COMPETING_BOUND")]
        and result["FAMILY_BOUND_AFTER"] == SEVEN_ROW_BOUND
        and result["NEXT_OWNER_IDS"] == [TARGET_PROFILE]
        and result["PRESERVED_SIX_ROW_STATUS"]
        == {k: six_result[k] for k in t256.PRESERVED_SIX_ROW_FIELDS},
        "seven-row ledger does not reproduce 6569a966",
    )
    return result, ledger


def apply_eighth(ledger: Mapping[str, Row], bound: int, cap: int, source: str) -> dict[str, Row]:
    """Install exactly one tighter row for the target profile; nothing else may move."""
    old = ledger[TARGET_PROFILE]
    require(type(bound) is int and type(cap) is int, "update must use exact integers")
    require(
        (old.bound, old.cap, old.s4_base) == (SEVEN_ROW_BOUND, CURRENT_CAP, S4_BASE)
        and bound < old.bound
        and 22 <= cap < old.cap,
        "eighth update does not tighten the recorded row",
    )
    before = two.full_digest(ledger)
    after = dict(ledger)
    after[TARGET_PROFILE] = replace(old, bound=bound, cap=cap, source=source)
    require(
        set(after) == set(ledger)
        and [p for p in ledger if ledger[p] != after[p]] == [TARGET_PROFILE]
        and two.full_digest(ledger) == before,
        "eighth update changed another row or the frozen ledger",
    )
    return after


def compute_result() -> dict[str, object]:
    provenance = module_provenance()
    seven_result, ledger = seven_row_authority()
    theorem = cap_theorem()
    old_terms, old_bound = route_b(CURRENT_CAP)
    new_terms, new_bound = route_b(PROPOSED_CAP)
    row = ledger[TARGET_PROFILE]
    require(
        old_bound == row.bound == SEVEN_ROW_BOUND
        and (row.cap, row.s4_base) == (CURRENT_CAP, S4_BASE)
        and len(new_terms) == PROPOSED_CAP - 21
        and new_terms == old_terms[: len(new_terms)],
        "Route B does not extend the recorded row authority",
    )
    needed = required_improvement(old_terms)
    peak = max(new_terms, key=lambda term: (term[1], term[0]))
    if row.realization is None:
        raise AssertionError("target row has no recorded realization")
    recorded = realization_check(*row.realization)
    source = f"{TASK_ID}:DEGREE_SQUARE_T248_THEOREM"
    after = apply_eighth(ledger, new_bound, PROPOSED_CAP, source)
    before, before_owners, _ = three.family(ledger)
    best, owners, next_level = three.family(after)
    cursor = [chase.prior.CURSOR_ID] if next_level == chase.prior.CURSOR_BOUND else []
    next_owners = sorted([p for p, r in after.items() if r.bound == next_level] + cursor)
    previous = [text(p) for p in rows(seven_result["CERTIFICATE_PROFILE_IDS"])]
    require(
        TARGET_PROFILE not in previous
        and all(after[p] == ledger[p] for p in previous)
        and (before, before_owners) == (SEVEN_ROW_BOUND, [TARGET_PROFILE]),
        "prior certificates or the seven-row family were not preserved",
    )
    above = sorted(p for p, r in after.items() if r.bound > INCUMBENT)
    actual: dict[str, object] = {
        "PROFILE_BOUND_AFTER": new_bound,
        "FAMILY_BOUND_AFTER": best,
        "FAMILY_BOUND_DELTA": before - best,
        "NEXT_OWNER_IDS": owners,
        "GAP_TO_INCUMBENT": best - INCUMBENT,
        "T248_TERM": list(peak[2:]),
    }
    expected: dict[str, object] = {
        "PROFILE_BOUND_AFTER": 313_255_140,
        "FAMILY_BOUND_AFTER": 313_398_248,
        "FAMILY_BOUND_DELTA": 284,
        "NEXT_OWNER_IDS": [
            "66555555555531000000",
            "66655555554441000000",
            "66655555555422000000",
        ],
        "GAP_TO_INCUMBENT": 134_360,
        "T248_TERM": [369, 200, 204_351, 4_981_872],
    }
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "T248_EIGHT_ROW_RESULT_PENDING_FRESH_JUDGE",
        "PROOF": __doc__,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "T256_RESULT_SHA256": T256_RESULT_SHA256,
        "T256_JUDGE_RECORD": T256_JUDGE_RECORD,
        "PRESERVED_T256_STATUS": {
            k: seven_result[k]
            for k in ("TASK_ID", "TASK_STATUS", "PRESERVED_SIX_ROW_STATUS", "GLOBAL_K20_OPTIMUM")
        },
        "INHERITED_STATUS_SOURCE": "VERBATIM_T256_RESULT_FIELDS_NOT_UPGRADED",
        "PRIOR_ART": PRIOR_ART,
        "SUPPORT_MODEL": three.support_model(),
        "THEOREM_T248": theorem,
        "RECORDED_ROW_REALIZATION": recorded,
        "REQUIRED_IMPROVEMENT": needed,
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
        "PROFILE_BOUND_BELOW_INCUMBENT": new_bound <= INCUMBENT,
        "PROFILE_MARGIN_BELOW_INCUMBENT": INCUMBENT - new_bound,
        "LEDGER_ROWS": len(after),
        "CERTIFICATES_COMPOSED": len(previous) + 1,
        "CERTIFICATE_PROFILE_IDS": [*previous, TARGET_PROFILE],
        "ROWS_CHANGED_FROM_SEVEN_ROW": [p for p in ledger if ledger[p] != after[p]],
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
        "HEAVY_SEARCH_STARTED": "NO",
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
