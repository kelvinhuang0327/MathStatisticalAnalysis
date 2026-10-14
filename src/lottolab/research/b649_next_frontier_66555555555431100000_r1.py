"""An eight-case analytic T<=255 certificate for exactly 66555555555431100000.

This is a simpler proof of an already known cap, applied ONLY to the requested
6569a966 Frozen row. It does not rerun either archived same-profile search, adopt
the stronger archived T251/Bonf64 result, or calculate a family maximum.

Domain: 20 tickets, six distinct labels each, 22 triple supports, 27 pair
supports, and each ticket pair in at most one support. Thus G is simple,
|E(G)|=93, deg_G=6+d, sum d=66, sum d^2=324, W=825. Counting homogeneous
three-sets gives T(G)+T(H)=C(20,3)-18*93+825=291, H=complement(G).

Let K={d>0}, Z={d=0}, |K|=15, |Z|=5; sigma_x=|N_G(x)&Z|,
zeta_u=|N_G(u)&K|, r=sum sigma=sum zeta. Only pair labels reach Z,
so 0<=sigma_x<=6-d_x. Since a zero has six G neighbours, 2<=zeta_u<=6.
For M=H[K], N=H[Z], their degrees are h_x=8-d_x+sigma_x and
n_u=zeta_u-2. Hence 2e(M)=54+r, 2e(N)=r-10 and 5e(M)+15e(N)=60+10r.
Each mixed H triangle has exactly one same-part edge. Counting its apices:
 t(H)=60+10r-sum sigma*h-sum zeta*n+P,
 P=t(M)+t(N)+sum_{xy in M}|N_G(x)&N_G(y)&Z|
                 +sum_{uv in N}|N_G(u)&N_G(v)&K| >= 0.
This classifies all H triangles, without any disjointness assumption about
the four nonnegative counts in P. Substituting r on both sides gives exactly
 T(G)=231+sum_K sigma(sigma+2-d)+sum_Z zeta(zeta-6)-P.

Write L=G[Z], m=e(L), q_u=deg_L(u), zeta_u=6-q_u, r=30-2m.
sum_K(6-d)=24, hence r<=24; L is simple on five vertices, hence 3<=m<=10.
Put x=sigma_A+sigma_B for the two d=1 vertices (x<=10), p=sigma at
d=3 (p<=3), v=sigma at d=4 (v<=2), and h=sum sigma at d=5 (h<=9).
The d=6 terms vanish, d=5 terms equal -2h, v(v-2)<=0,
p(p-1)<=2p, and each d=1 term s(s+1)<=6s. Therefore the core term C
is at most 6x+2p-2h. Since r=x+p+v+h, three linear certificates give
 C<=2r+40 (x<=10, v,h>=0), C<=66 (x<=10,p<=3,h>=0),
 C<=96-2r (x<=10,p<=3,v<=2).

The ONE graph inequality is edge-pair counting: for any simple graph with
m edges, sum q^2=2m+2*(intersecting unordered edge pairs)<=m(m+1).
Apply it also to the complement of L, with l=10-m edges:
 sum q^2=80-16l+sum deg_complement^2<=80-16l+l(l+1).
When m=5, at least one edge pair is disjoint, so sum q^2<=28. Indeed,
a pairwise-intersecting family of graph edges is a star or a triangle:
take ab,ac; an edge avoiding a must be bc, after which no fourth edge
is possible. A star on five vertices has at most four edges. Thus five
edges cannot all pairwise intersect. This uses simplicity essentially.

Consequently T(G)<=231+min(40+2r,66,96-2r)+Q(m)-12m, where Q is the
minimum of the two edge-pair bounds (also 28 at m=5). The eight integer
m cases give 255,255,255,255,255,255,253,251. Thus T<=255 universally.
Every legal support realization maps to one case; all omitted incidence,
core graphicality and triple-decomposition restrictions enlarge the relaxation.
No graph enumeration, sigma enumeration, sampling or solver is used.

Route B is separately recounted for every T=22..266 and its 22..255 prefix:
J=2299, A_max=floor(588/3)=196; K4>=max(0,ceil((30T-5951)/4));
S4>=max(112,679*K4-231*min(K4,196)). S3=2800*825+11872*(T-22)-30800.
The final bound is ceil(S1-S2+S3-4*S4/7), equivalently subtract floor(4*S4/7).
The widest sufficient integer cap for the cursor is 265, not 266.
At T=255 the maximum is 313296388, a Frozen-row improvement of 98388.
T255 attainment and any family improvement are NOT asserted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from fractions import Fraction
from math import comb
from pathlib import Path
from typing import cast

TASK_ID = "B649_NEXT_FRONTIER_66555555555431100000_R1"
PROFILE = "66555555555431100000"
FROZEN_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
FROZEN_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
DIRECTORY = "docs/research/matrix-native-results"
FROZEN_RESULT = f"{DIRECTORY}/b649-min-s2-next-owner-core-zero-t256-cert-r1-result.json"
FROZEN_SHA = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"
SIX_RESULT = f"{DIRECTORY}/b649-min-s2-six-row-existing-s4-family-authority-r1-result.json"
SIX_SHA = "1f94b064ab7392b88cf4c18ca4d3cb164305601ea9bc2b0f2174c0cddb185e5f"
R30_RESULT = f"{DIRECTORY}/b649-k20-min-s2-current-cursor-dynamic-family-max-r30-result.json"
R30_SHA = "9ed94532cc2bff5de1569f10561fb8340238ff3b1b1c3ae129e6a4929014f6fe"
SOURCE_LOCATOR = "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:NB_CERTIFICATES[1449]"
ROOT = Path(__file__).resolve().parents[3]
RESULT_PATH = ROOT / DIRECTORY / "b649-next-frontier-66555555555431100000-r1-result.json"
ARCHIVE_ROOT = Path(
    "/Users/kelvin/.codex/worktrees/b649-k20-665555555554311-structural-r1/"
    "MathStatisticalAnalysis/.task-data/B649_K20_665555555554311_STRUCTURAL_BOUND_R1"
)
CACHE_PATH = Path(
    "/Users/kelvin/.codex/worktrees/b649-k20-mins2-bonf64-ledger-r1/MathStatisticalAnalysis/"
    ".task-data/B649_K20_MIN_S2_FROZEN_LEDGER_BONF64_REPLAY_R1/replay_rows_cache.json"
)
CACHE_SHA = "1d530421c10ad08e8505b603928e0fb7c88a1044c5eb50c2a3e8cb55c60681a4"
SOURCE_CAP, SOURCE_BASE, OLD_BOUND = 266, 112, 313_394_776
PROVED_CAP, CURSOR_BOUND, INCUMBENT = 255, 313_394_584, 313_263_888
S1, S2 = 372_228_640, 63_838_600
type Term = tuple[int, int, int, int, int, int]
type Edge = tuple[int, int]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def obj(value: object) -> dict[str, object]:
    require(isinstance(value, dict), "expected object")
    result = cast(dict[object, object], value)
    require(all(type(k) is str for k in result), "expected string keys")
    return cast(dict[str, object], result)


def integer(value: object) -> int:
    require(type(value) is int, "expected exact integer")
    return cast(int, value)


def decode(data: bytes) -> dict[str, object]:
    return obj(cast(object, json.loads(data)))


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def pinned(path: str, digest: str, head: str = FROZEN_HEAD) -> dict[str, object]:
    data = git("show", f"{head}:{path}")
    require(sha(data) == digest, f"source SHA mismatch: {path}")
    return decode(data)


@dataclass(frozen=True)
class Premises:
    tickets: int = 20
    labels_per_ticket: int = 6
    triple_supports: int = 22
    pair_supports: int = 27
    support_sizes: tuple[int, int] = (2, 3)
    pair_linearity: bool = True


MODEL = Premises()


def premises(profile: str = PROFILE, model: Premises = MODEL) -> dict[str, object]:
    require(profile == PROFILE, "wrong exact profile")
    require(
        model == MODEL
        and model.pair_linearity is True
        and all(
            type(v) is int
            for v in (
                model.tickets,
                model.labels_per_ticket,
                model.triple_supports,
                model.pair_supports,
                *model.support_sizes,
            )
        ),
        "missing or altered support premises",
    )
    d = tuple(map(int, profile))
    g = tuple(6 + v for v in d)
    goodman = Fraction(comb(20, 3)) - Fraction(sum(v * (19 - v) for v in g), 2)
    complement = comb(20, 3) - 18 * 97 + sum(comb(13 - v, 2) for v in d)
    require(
        dict(Counter(d)) == {6: 2, 5: 9, 4: 1, 3: 1, 1: 2, 0: 5}
        and sum(d) == 66
        and sum(v * v for v in d) == 324
        and sum(g) == 186
        and sum(v * v for v in g) == 1836
        and sum(comb(v, 2) for v in g) == 825
        and goodman == complement == 291,
        "profile/Goodman identity mismatch",
    )
    return {
        "D": list(d),
        "G": list(g),
        "CORE_COUNT": 15,
        "ZERO_COUNT": 5,
        "DEGREE_SUM": 66,
        "DEGREE_SQUARE_SUM": 324,
        "GOODMAN_CONSTANT": 291,
        "W": 825,
        "J": sum(comb(v, 3) for v in g),
        "SUPPORT_EDGES": 93,
        "A_MAX": sum(v * (v + 4) for v in d) // 3,
        "ASSUMPTIONS": asdict(model),
    }


def core_ceiling(r: int) -> int:
    require(type(r) is int and 10 <= r <= 24, "cross degree outside necessary range")
    return min(40 + 2 * r, 66, 96 - 2 * r)


def zero_square_ceiling(m: int, *, vertices: int = 5, simple: bool = True) -> int:
    require(
        vertices == 5 and type(vertices) is int and simple is True, "simple five-vertex premise"
    )
    require(type(m) is int and 3 <= m <= 10, "zero-edge count outside necessary range")
    missing = 10 - m
    bound = min(m * (m + 1), 80 - 16 * missing + missing * (missing + 1))
    return min(bound, 28) if m == 5 else bound


def analytic_certificate(profile: str = PROFILE, model: Premises = MODEL) -> dict[str, object]:
    facts = premises(profile, model)
    # Check the scalar secant inequalities over their entire legal integer domains.
    secants = {
        "D1": all(s * (s + 1) <= 6 * s for s in range(6)),
        "D3": all(s * (s - 1) <= 2 * s for s in range(4)),
        "D4": all(s * (s - 2) <= 0 for s in range(3)),
        "D5": all(s * (s - 3) == -2 * s for s in range(2)),
        "D6": 0 * (0 - 4) == 0,
    }
    require(all(secants.values()), "core secant failed")
    cases: list[dict[str, int]] = []
    for m in range(3, 11):
        r = 30 - 2 * m
        core, square = core_ceiling(r), zero_square_ceiling(m)
        cases.append(
            {
                "M": m,
                "R": r,
                "CORE_CEILING": core,
                "ZERO_SQUARE_CEILING": square,
                "T_CEILING": 231 + core + square - 12 * m,
            }
        )
    cap = max(row["T_CEILING"] for row in cases)
    return {
        **facts,
        "PROFILE_ID": profile,
        "CAP": cap,
        "PROOF_SCOPE": "FULL_PROFILE",
        "CASES": cases,
        "SCALAR_SECANTS": secants,
        "ARGMAX_M": [row["M"] for row in cases if row["T_CEILING"] == cap],
        "EXACT_TRIANGLE_IDENTITY": "T(G)+T(H)=291",
        "CORE_ZERO_DECOMPOSITION": "T=231+sum sigma(sigma+2-d)+sum zeta(zeta-6)-P",
        "NONNEGATIVE_REMAINDER": (
            "P=t(H[K])+t(H[Z])+sum_E(H[K]) c_Z+sum_E(H[Z]) c_K; four cardinalities"
        ),
        "COMBINATORIAL_INEQUALITY": "sum deg(L)^2=2m+2 adjacent_edge_pairs<=m(m+1)",
        "M5_CORRECTION": "Five edges on five vertices include a disjoint edge pair: Q<=28",
        "RELAXATION_SUPERSET_COMPLETENESS": (
            "Every legal realization has simple L=G[Z], m in 3..10, r=30-2m, and the "
            "stated core capacities. Three linear certificates bound every core vector. "
            "Edge-pair counting bounds every L. All eight possible m are retained. "
            "No simultaneous graphicality or realizability assumption is imposed."
        ),
        "FULL_SUPPORT_GRAPHS_ENUMERATED": 0,
        "ZERO_GRAPHS_ENUMERATED": 0,
        "SIGMA_VECTORS_ENUMERATED": 0,
        "ATTAINMENT": "NOT_ASSERTED",
    }


def verify_analytic_certificate(certificate: Mapping[str, object]) -> None:
    # JSON arrays are the canonical representation of both tuples and lists.
    require(
        json.dumps(dict(certificate), sort_keys=True)
        == json.dumps(analytic_certificate(), sort_keys=True),
        "wrong cap or altered proof certificate",
    )


def support_graph(
    triples: Sequence[Sequence[int]],
    pairs: Sequence[Sequence[int]],
    profile: str = PROFILE,
    model: Premises = MODEL,
) -> frozenset[Edge]:
    """Reject illegal supports before using any graph identity; never construct/search supports."""
    premises(profile, model)
    require(len(triples) == 22 and len(pairs) == 27, "illegal support counts")
    edges: set[Edge] = set()
    degrees = [0] * 20
    labels = [0] * 20
    for supports, size in ((triples, 3), (pairs, 2)):
        for support in supports:
            require(
                len(support) == size
                and len(set(support)) == size
                and all(type(v) is int and 0 <= v < 20 for v in support),
                "illegal support vertices/arity",
            )
            part = sorted(support)
            for v in part:
                labels[v] += 1
                degrees[v] += int(size == 3)
            for i, u in enumerate(part):
                for v in part[i + 1 :]:
                    require((u, v) not in edges, "illegal pair reuse")
                    edges.add((u, v))
    require(labels == [6] * 20, "illegal ticket capacities")
    require("".join(map(str, sorted(degrees, reverse=True))) == profile, "wrong support profile")
    return frozenset(edges)


def route_terms(cap: int, base: int = SOURCE_BASE, profile: str = PROFILE) -> list[Term]:
    premises(profile)
    require(type(cap) is int and 22 <= cap <= SOURCE_CAP, "wrong cap domain")
    require(type(base) is int and base >= 0, "wrong S4 base")
    terms: list[Term] = []
    for t in range(22, cap + 1):
        numerator = 2299 - 10 * (825 - 3 * t)
        k4 = max(0, -(-numerator // 4))
        a = min(k4, 196)
        s4 = max(base, 679 * k4 - 231 * a)
        s3 = 2800 * 825 + 11872 * (t - 22) - 30800
        terms.append((t, S1 - S2 + s3 - 4 * s4 // 7, k4, a, s4, s3))
    return terms


def validate_terms(terms: Sequence[Term], cap: int, base: int = SOURCE_BASE) -> None:
    require(type(cap) is int and 22 <= cap <= SOURCE_CAP, "wrong envelope cap")
    require(type(base) is int and base >= 0, "wrong S4 base")
    require([row[0] for row in terms] == list(range(22, cap + 1)), "incomplete T coverage")
    for t, bound, k4, a, s4, s3 in terms:
        require(all(type(v) is int for v in (t, bound, k4, a, s4, s3)), "noninteger term")
        numerator = 30 * t - 5951
        k_exact = max(Fraction(0), Fraction(numerator, 4))
        k_ceiling = -(-k_exact.numerator // k_exact.denominator)
        require(k4 == k_ceiling and a == min(k4, 196), "K4 ceiling/contained cap")
        require(s4 == max(base, 448 * a + 679 * (k4 - a)), "S4 floor/credit mismatch")
        s3_exact = 2800 * (825 - 3 * t) + 20272 * (t - 22) + 7000 * 22
        exact = Fraction(S1 - S2 + s3_exact) - Fraction(4 * s4, 7)
        ceiling = -(-exact.numerator // exact.denominator)
        require(s3 == s3_exact and bound == ceiling, "S3/final rounding mismatch")


def widest_sufficient_cap(terms: Sequence[Term], cursor: int = CURSOR_BOUND) -> int:
    validate_terms(terms, SOURCE_CAP)
    require(type(cursor) is int, "noninteger cursor")
    running = -1
    sufficient: list[int] = []
    for t, bound, *_ in terms:
        running = max(running, bound)
        if running <= cursor:
            sufficient.append(t)
    require(bool(sufficient), "no sufficient cap")
    return max(sufficient)


def prior_art() -> list[dict[str, object]]:
    """Read sealed evidence only. None of the prior mathematical searches is executed."""
    source = ARCHIVE_ROOT / "verify_structural_bound.py"
    result = ARCHIVE_ROOT / "result.json"
    require(
        sha(source.read_bytes())
        == "b2d1856bdd4d9d79630591ba3df18037a255ff14a6433a8a5f860db50e3eeb14",
        "archived source SHA mismatch",
    )
    require(
        sha(result.read_bytes())
        == "3f5483e8991e2a5685ea1f7f5d4fbd7a0d16408513bf3a89b2f0376b1357ffa3",
        "archived result SHA mismatch",
    )
    overlay_path = f"{DIRECTORY}/b649-k20-independent-mathematical-closure-overlay.json"
    overlay = pinned(
        overlay_path,
        "e5a2faaff8a8f79e1c83755b86e40c54ce7d47247d22cedca5ee1ef874078010",
        "da26b434499927f5611e3c3d12e50485f2e58a6a",
    )
    accepted = obj(obj(overlay["ACCEPTED_PROFILES"])[PROFILE])
    require(
        accepted["MAX_CERTIFIED_T"] == 251 and accepted["RESOURCE_VERDICT"] == "FAIL",
        "archived acceptance changed",
    )
    previous_path = f"{DIRECTORY}/b649-next-single-max-owner-bound-r1-result.json"
    previous = pinned(
        previous_path,
        "0b12e9e962574082081ccfd5676db0e5a200bcf49bee3c94174fc9dbad476018",
        "317210d56cac9efcb779e0967049302c74d7be77",
    )
    return [
        {
            "KIND": "ACCEPTED_T251_STRUCTURAL_BONF64",
            "SOURCE_PATH": str(source),
            "SOURCE_SHA256": sha(source.read_bytes()),
            "RESULT_PATH": str(result),
            "RESULT_SHA256": sha(result.read_bytes()),
            "ACCEPTANCE_HEAD": "da26b434",
            "CAP": 251,
            "ACCEPTED_BOUND_WITH_BONF64": accepted["NEW_VALID_BOUND"],
            "RESOURCE_VERDICT": "FAIL",
            "EXACT_TOTAL_CPU": "UNKNOWN",
            "SEARCH_RERUN": "NO",
            "ADOPTED_HERE": "NO; STRONGER PRIOR ART IS ACKNOWLEDGED",
        },
        {
            "KIND": "T255_FINITE_ZERO_SHAPE_RELAXATION",
            "HEAD": "317210d56cac9efcb779e0967049302c74d7be77",
            "RESULT_SHA256": "0b12e9e962574082081ccfd5676db0e5a200bcf49bee3c94174fc9dbad476018",
            "RESULT_TASK_ID": previous["TASK_ID"],
            "SEARCH_RERUN": "NO",
            "NOVELTY": "SAME CAP; THIS MODULE USES EIGHT ANALYTIC CASES, NO GRAPH ENUMERATION",
        },
    ]


def frozen_authority() -> dict[str, object]:
    require(
        git("rev-parse", f"{FROZEN_HEAD}^{{tree}}").decode().strip() == FROZEN_TREE,
        "Frozen tree mismatch",
    )
    sealed = pinned(FROZEN_RESULT, FROZEN_SHA)
    require(
        sealed["SIX_ROW_RESULT_SHA256"] == SIX_SHA and sealed["INCUMBENT"] == INCUMBENT,
        "Frozen inheritance mismatch",
    )
    require(
        PROFILE not in cast(list[str], sealed["CERTIFICATE_PROFILE_IDS"]),
        "target already changed in Frozen result",
    )
    six = pinned(SIX_RESULT, SIX_SHA)
    require(obj(six["RESOLVED_ROW_BOUNDS"])[PROFILE] == OLD_BOUND, "Frozen target bound mismatch")
    cache_data = CACHE_PATH.read_bytes()
    require(sha(cache_data) == CACHE_SHA, "row cache source SHA mismatch")
    row = obj(obj(decode(cache_data)["rows"])[PROFILE])
    require(
        row
        == {
            "CAP": SOURCE_CAP,
            "S4_BASE": SOURCE_BASE,
            "BOUND": OLD_BOUND,
            "SOURCE": SOURCE_LOCATOR,
        },
        "Frozen row fields mismatch",
    )
    r30 = pinned(R30_RESULT, R30_SHA)
    attempts = cast(list[object], r30["GROUP_ATTEMPTS"])
    proof = obj(attempts[2738])
    required: dict[str, object] = {
        "ATTEMPT_INDEX": 2738,
        "PROFILE_IDS": [PROFILE],
        "STATUS": "INFEASIBLE",
        "CERTIFICATE_KIND": "CP_SAT_INFEASIBLE",
        "WEDGE_COUNT": 825,
        "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": 266,
        "TARGET_TRIANGLE_CAP": 266,
        "REFUTED_GRAPH_TRIANGLE_COUNT": 267,
    }
    require(all(proof[k] == v for k, v in required.items()), "original cap source mismatch")
    return {
        "FROZEN_HEAD": FROZEN_HEAD,
        "FROZEN_TREE": FROZEN_TREE,
        "FROZEN_RESULT_PATH": FROZEN_RESULT,
        "FROZEN_RESULT_SHA256": FROZEN_SHA,
        "INHERITED_SIX_RESULT_SHA256": SIX_SHA,
        "FROZEN_ROW": row,
        "ROW_CACHE_PATH": str(CACHE_PATH),
        "ROW_CACHE_SHA256": CACHE_SHA,
        "ROW_CACHE_BINDING": (
            "HASH-PINNED ROW; NB_CERTIFICATES[1449] IS AN IN-MEMORY ADOPTION INDEX"
        ),
        "ORIGINAL_CAP_SOURCE": f"{R30_RESULT}:GROUP_ATTEMPTS[2738]",
        "ORIGINAL_CAP_SOURCE_SHA256": R30_SHA,
        "ORIGINAL_CAP_SOURCE_FIELDS": required,
        "FROZEN_AUTHORITY_STATUS": sealed["TASK_STATUS"],
        "INHERITED_JUDGE_STATUS": six["AUTHORITY_JUDGE_STATUS"],
        "AUTHORITY_STATUS_UPGRADED": "NO",
    }


def frozen_route_crosscheck(terms: Sequence[Term]) -> dict[str, str]:
    # Import the frozen helpers only; never call their ledger replay or search entrypoints.
    from . import b649_k20_min_s2_realizable_core_class_bound_r4 as core
    from . import b649_k20_min_s2_route_b_current_owner_refinement_r32 as route

    modules = (
        route,
        core,
        route.r30,
        route.r28,
        route.r31,
        __import__(route.bound_from_cap.__module__, fromlist=["bound_from_cap"]),
    )
    provenance: dict[str, str] = {}
    for module in modules:
        path = Path(cast(str, module.__file__)).resolve()
        require(path.is_relative_to(ROOT), "reused source outside task worktree")
        relative = path.relative_to(ROOT).as_posix()
        data = git("show", f"{FROZEN_HEAD}:{relative}")
        require(path.read_bytes() == data, "reused source SHA mismatch")
        provenance[relative] = sha(data)
    d = tuple(map(int, PROFILE))
    require(route.r28.profile_s4_floor(d) == SOURCE_BASE, "original S4 base mismatch")
    require(
        route.route_b_envelope(d, SOURCE_CAP, SOURCE_BASE) == list(terms),
        "Frozen Route-B recount mismatch",
    )
    return provenance


def compute_result() -> dict[str, object]:
    authority = frozen_authority()
    prior = prior_art()
    proof = analytic_certificate()
    cap = integer(proof["CAP"])
    old_terms = route_terms(SOURCE_CAP)
    validate_terms(old_terms, SOURCE_CAP)
    provenance = frozen_route_crosscheck(old_terms)
    new_terms = route_terms(cap)
    validate_terms(new_terms, cap)
    require(new_terms == old_terms[: len(new_terms)], "prefix changed")
    old_bound = max(row[1] for row in old_terms)
    new_bound = max(row[1] for row in new_terms)
    sufficient = widest_sufficient_cap(old_terms)
    require(
        old_bound == OLD_BOUND and new_bound < old_bound and new_bound <= CURSOR_BOUND,
        "requested cursor/improvement criterion failed",
    )
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "SUCCESS_CURSOR_TARGET_ANALYTIC_FULL_PROFILE_CERTIFICATE",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "AUTHORITY": authority,
        "PRIOR_ART": prior,
        "FROZEN_HEAD_TREE": "MATCH",
        "FROZEN_RESULT_SHA256": "MATCH",
        "PROFILE_ID": PROFILE,
        "DEGREE_MULTIPLICITIES": "6^2,5^9,4^1,3^1,1^2,0^5",
        "GOODMAN_CONSTANT": 291,
        "CORE_COUNT": 15,
        "ZERO_COUNT": 5,
        "SOURCE_T_CAP": SOURCE_CAP,
        "SOURCE_S4_BASE": SOURCE_BASE,
        "SOURCE_OLD_BOUND": OLD_BOUND,
        "SOURCE_LOCATOR": SOURCE_LOCATOR,
        "EXACT_TRIANGLE_IDENTITY": proof["EXACT_TRIANGLE_IDENTITY"],
        "CORE_ZERO_DECOMPOSITION": proof["CORE_ZERO_DECOMPOSITION"],
        "NONNEGATIVE_REMAINDER": proof["NONNEGATIVE_REMAINDER"],
        "LOAD_BEARING_PREMISES": asdict(MODEL),
        "PROOF_SCOPE": "FULL_PROFILE",
        "PROVED_T_CAP": cap,
        "RELAXATION_SUPERSET_COMPLETENESS": proof["RELAXATION_SUPERSET_COMPLETENESS"],
        "COUNTEREXAMPLE_STATUS": "NONE; UNIVERSAL ANALYTIC PROOF; NO SUPPORT SEARCH RUN",
        "UNPROVED_ASSUMPTIONS": [],
        "ANALYTIC_CERTIFICATE": proof,
        "CURSOR_BOUND": CURSOR_BOUND,
        "SUFFICIENT_CAP_FOR_CURSOR": sufficient,
        "CURSOR_CAP_BOUND": old_terms[sufficient - 22][1],
        "NEXT_CAP_BOUND": old_terms[sufficient + 1 - 22][1],
        "NEW_ADMISSIBLE_BOUND": new_bound,
        "STRICT_OWNER_BOUND_DELTA": old_bound - new_bound,
        "BOUND_AT_OR_BELOW_CURSOR": True,
        "ROUTE_B_INTEGER_RECOUNT": "PASS",
        "EXACT_RATIONAL_CROSSCHECK": "PASS_ALL_T",
        "ROUNDING_CHECK": "PASS_ALL_T",
        "ARGMAX_TERM": list(max(new_terms, key=lambda row: (row[1], row[0]))),
        "ALL_ARGMAX_T": [row[0] for row in new_terms if row[1] == new_bound],
        "ARGMAX_S4_CREDIT": 4 * max(new_terms, key=lambda row: row[1])[4] // 7,
        "TERM_COLUMNS": ["T", "BOUND", "K4_CEILING", "CONTAINED_K4_CAP", "S4", "S3"],
        "OLD_ALL_T_TERMS": [list(row) for row in old_terms],
        "NEW_ALL_T_TERMS": [list(row) for row in new_terms],
        "REUSED_MODULE_SHA256": provenance,
        "CPU_PROCESS_COUNT": 1,
        "HEAVY_SOLVER_STARTED": "NO",
        "ARCHIVED_SEARCH_RERUN": "NO",
        "FAMILY_GAIN_CLAIMED": 0,
        "NEW_WINNING_OUTCOMES": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "CANONICAL_AUTHORITY_CHANGED": "NO",
        "FAMILY_REPLAY": "NOT_RUN",
        "PRIOR_ART_SUPERSEDED": "NO; T251 IS STRONGER; THIS IS A SIMPLER T255 PROOF",
        "PUSH": "NOT_RUN",
        "MERGE": "NOT_RUN",
        "PRODUCTION_MUTATION": "NONE",
        "RESULT_SHA256_NOTE": "Full-file SHA is reported externally to avoid self-reference.",
        "COMMIT_IDENTITY_NOTE": (
            "Commit HEAD/tree and clean status are reported after the one commit."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-result", action="store_true")
    args = parser.parse_args()
    result = compute_result()
    data = (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    if args.write_result:
        with RESULT_PATH.open("xb") as out:
            out.write(data)
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "TASK_STATUS",
                    "PROVED_T_CAP",
                    "SUFFICIENT_CAP_FOR_CURSOR",
                    "NEW_ADMISSIBLE_BOUND",
                    "STRICT_OWNER_BOUND_DELTA",
                    "ARGMAX_TERM",
                )
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
