"""One new full-profile restriction: at most 187 contained-triple K4s.

Model: 22 linear triple supports and 27 pair supports on 20 tickets; each
ticket belongs to six supports, and every ticket pair occurs at most once.
Write d=(6^3,5^8,3^2,2,0^6), G for shadow plus pairs, H for its complement.
Thus g=6+d, |G|=93, |H|=97. Goodman gives
 t(G)+t(H)=C(20,3)-sum g(19-g)/2=294.
Independently, inclusion-exclusion gives 1140-18*97+900=294.

Core K has 14 vertices; Z has six. No triple meets Z. Cross-degrees sigma
and zeta therefore satisfy 0<=sigma<=6-d, 1<=zeta<=6 and equal sum r.
For M=H[K], MZ=H[Z], h=7-d+sigma, a=zeta-1, so
 |M|=(32+r)/2, |MZ|=(r-6)/2.
Counting mixed triangles by their unique same-part edge gives
 t(H)=6|M|+14|MZ|-sum sigma*h-sum zeta*a+P,
 P=t(M)+t(MZ)+sum_M |N_G(x)&N_G(y)&Z|
                  +sum_MZ |N_G(u)&N_G(v)&K| >= 0.
Consequently T=F-P, F=240+sum sigma(sigma+2-d)+sum zeta(zeta-6).
The EXISTING frozen split module supplies a complete necessary degree
relaxation: sigma sorted within equal-d classes and zeta sorted; all four
internal degree sequences pass Erdos-Gallai, the cross sequences Gale-Ryser.
Every legal support maps to one of its 428 configurations, max F=228.
We reuse this prior proof; neither attainment nor a new T theorem is claimed.

NEW restriction. A triple support S is contained in at most
 min_{v in S}(g_v-2)=4+min_{v in S}d_v K4s. No K4 contains two supports,
as two 3-subsets of a 4-set share a ticket pair. Let A,B have degree three
and C degree two. Both C supports lose at least three relative to min d=5.
The six A/B incidences have at most two in C supports (CA,CB each occur
at most once). At least four remain outside C; only one support can use
both A and B. Hence at least three distinct additional supports lose two.
Total loss >= 6+6=12. There is at most one all-degree-six support (only
three degree-six vertices); its gain relative to five is at most one.
Thus sum_S(4+min d) <= 22*(4+5)+1-12=187, universally.
An independently enumerated seven-pattern low-incidence relaxation checks
the loss argument over its complete integer box, including impossible
patterns, without graph/support search. Dropping pair linearity permits
loss eight and cap 191, so this premise is load-bearing.

Route B follows frozen R32: W=828, U=2324, gmax=12,
 K4(T)>=max(0,ceil((U-10*(W-3T))/4)),
 S4>=max(112,679*K4-231*min(K4,187)),
 S3=2800*W+11872*(T-22)-30800,
 bound=372228640-63838600+S3-floor(4*S4/7).
All integers T=22..265 are checked independently against exact Fractions.
The new restriction alone gives 313393608 at the frozen cap 265. Reusing
the existing full-profile cap 228 gives 313062208. This is one profile's
bound only: no family integration, winning outcomes or global optimum claim.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Sequence
from fractions import Fraction
from itertools import combinations, product
from math import comb
from pathlib import Path
from typing import cast

from . import b649_k20_min_s2_topw12_split_cap_certificate_r1 as prior

TASK_ID = "B649_NEXT_MAX_OWNER_66655555555332000000_R1"
PROFILE_ID = "66655555555332000000"
PROFILE = tuple(map(int, PROFILE_ID))
FROZEN_HEAD = "6569a9667d5e2094c8542cdff9905c3fd89f9e44"
FROZEN_TREE = "986d20859c86be9036b2321ac47e2e9622786a3b"
FROZEN_SHA = "880a672a7330a567cc4544170cdeb0f7aa4d3dc5b5e3603c89ef50663cd71743"
DIRECTORY = "docs/research/matrix-native-results"
FROZEN_PATH = f"{DIRECTORY}/b649-min-s2-next-owner-core-zero-t256-cert-r1-result.json"
SIX_PATH = f"{DIRECTORY}/b649-min-s2-six-row-existing-s4-family-authority-r1-result.json"
SIX_SHA = "1f94b064ab7392b88cf4c18ca4d3cb164305601ea9bc2b0f2174c0cddb185e5f"
ARCHIVE_PATH = (
    f"{DIRECTORY}/b649-min-s2-six-row-existing-s4-family-authority-r1-sources/s4-result.json"
)
ARCHIVE_SHA = "e376c3c15a767bdc75fe937f8ad36adf2ae94cc705628caccfab7f655c55852c"
SOURCE_LOCATOR = "b649-k20-min-s2-nb-degree-cap-frontier-r1-result.json:NB_CERTIFICATES[1205]"
SOURCE_CAP, S4_BASE, OLD_BOUND = 265, 112, 313_395_060
PRIOR_CAP, NEW_CONTAINED_CAP = 228, 187
NEXT_COMPETITOR, INCUMBENT = 313_394_776, 313_263_888
ROOT = Path(__file__).resolve().parents[3]
RESULT_PATH = ROOT / DIRECTORY / "b649-next-max-owner-66655555555332000000-r1-result.json"
PRIOR_PATH = "src/lottolab/research/b649_k20_min_s2_topw12_split_cap_certificate_r1.py"
PRIOR_SHA = "dd31017a685c809f494b359b7eece3fb3d832aef7f55699f7872dec53e25f784"
ROUTE_PATH = "src/lottolab/research/b649_k20_min_s2_route_b_current_owner_refinement_r32.py"
ROUTE_SHA = "d2bd52eaa53825fc138b95f42d06ec6152757ae25a70212b0674bf8ea311dc1d"
S4_PATH = "src/lottolab/research/b649_k20_min_s2_current_cursor_class_owner_chase_r28.py"
LOW_PATTERNS = ((0,), (1,), (2,), (0, 1), (0, 2), (1, 2), (0, 1, 2))
Term = tuple[int, int, int, int, int, int]
Support = tuple[int, ...]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def render(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def obj(value: object) -> dict[str, object]:
    require(isinstance(value, dict), "expected JSON object")
    return cast(dict[str, object], value)


def array(value: object) -> list[object]:
    require(isinstance(value, list), "expected JSON array")
    return cast(list[object], value)


def pinned(path: str, expected_sha: str | None = None) -> bytes:
    raw = subprocess.check_output(["git", "show", f"{FROZEN_HEAD}:{path}"], cwd=ROOT)
    require(expected_sha is None or digest(raw) == expected_sha, f"source SHA mismatch: {path}")
    require((ROOT / path).read_bytes() == raw, f"working source changed: {path}")
    return raw


def validate_profile(profile: Sequence[int]) -> None:
    require(
        all(type(v) is int for v in profile) and tuple(sorted(profile, reverse=True)) == PROFILE,
        "wrong profile",
    )


def source_authority() -> dict[str, object]:
    tree = subprocess.check_output(
        ["git", "rev-parse", f"{FROZEN_HEAD}^{{tree}}"], cwd=ROOT, text=True
    ).strip()
    require(tree == FROZEN_TREE, "frozen tree mismatch")
    frozen = obj(json.loads(pinned(FROZEN_PATH, FROZEN_SHA)))
    six = obj(json.loads(pinned(SIX_PATH, SIX_SHA)))
    archive = obj(json.loads(pinned(ARCHIVE_PATH, ARCHIVE_SHA)))
    require(
        frozen["FULL_ROWS_SHA256_BEFORE"] == six["FULL_ROWS_SHA256_AFTER"]
        and PROFILE_ID not in array(frozen["ROWS_CHANGED_FROM_SIX_ROW"])
        and obj(six["RESOLVED_ROW_BOUNDS"])[PROFILE_ID] == OLD_BOUND,
        "target row is not unchanged in frozen lineage",
    )
    row = obj(array(obj(archive["FINAL_FAMILY"])["ROWS_ABOVE_CURSOR"])[18])
    require(
        row
        == {
            "BOUND": OLD_BOUND,
            "PROFILE_ID": PROFILE_ID,
            "SOURCE": SOURCE_LOCATOR,
            "TRIANGLE_CAP": SOURCE_CAP,
        },
        "source row/cap mismatch",
    )
    require(PROFILE.count(0) == 6 and S4_BASE == 112, "source S4 base mismatch")
    # The profile floor is the frozen R28 function (112 unless there are seven zeros).
    s4_blob = pinned(S4_PATH)
    require(
        b"def profile_s4_floor" in s4_blob and b"if profile.count(0) == 7 else 0" in s4_blob,
        "S4 source rule mismatch",
    )
    pinned(PRIOR_PATH, PRIOR_SHA)
    pinned(ROUTE_PATH, ROUTE_SHA)
    require(Path(prior.__file__).resolve() == ROOT / PRIOR_PATH, "wrong prior module")
    return {
        "BOUND": OLD_BOUND,
        "TRIANGLE_CAP": SOURCE_CAP,
        "S4_BASE": S4_BASE,
        "SOURCE": SOURCE_LOCATOR,
        "ROW_PROJECTION_LOCATOR": f"{ARCHIVE_PATH}:FINAL_FAMILY.ROWS_ABOVE_CURSOR[18]",
        "FROZEN_LINEAGE_TARGET_REPLAY": {
            "bound": OLD_BOUND,
            "cap": SOURCE_CAP,
            "s4_base": S4_BASE,
            "source": SOURCE_LOCATOR,
            "realization": None,
        },
        "MODULE_PROVENANCE": {
            PRIOR_PATH: PRIOR_SHA,
            ROUTE_PATH: ROUTE_SHA,
            S4_PATH: digest(s4_blob),
        },
    }


def goodman() -> dict[str, object]:
    validate_profile(PROFILE)
    g = tuple(6 + d for d in PROFILE)
    phi = Fraction(comb(20, 3)) - Fraction(sum(v * (19 - v) for v in g), 2)
    ie = comb(20, 3) - 18 * 97 + sum(comb(13 - d, 2) for d in PROFILE)
    require(sum(PROFILE) == 66 and sum(d * d for d in PROFILE) == 330, "degree sums")
    require(sum(g) == 186 and phi == ie == 294, "Goodman constant")
    return {
        "CONSTANT": int(phi),
        "G_EDGES": 93,
        "H_EDGES": 97,
        "IDENTITY": "T+t(H)=1140-sum (6+d)(13-d)/2=1140-846=294",
        "INCLUSION_EXCLUSION": "1140-18*97+900=294",
        "CORE_ZERO": [14, 6],
        "M_DEGREES": "7-d+sigma",
        "MZ_DEGREES": "zeta-1",
        "M_EDGES": "(32+r)/2",
        "MZ_EDGES": "(r-6)/2",
        "T_H": "54+4r+sum d*sigma-sum sigma^2-sum zeta^2+P",
        "F": "240+sum sigma(sigma+2-d)+sum zeta(zeta-6)",
        "T": "F-P",
        "P": "t(M)+t(MZ)+sum_M common_G_zero+sum_MZ common_G_core",
        "NONNEGATIVE_REMAINDER": "SUM_OF_FOUR_CARDINALITIES",
    }


def prior_cap(claim: int = PRIOR_CAP) -> dict[str, object]:
    """Reuse the existing complete degree relaxation, without developing a new cap."""
    validate_profile(PROFILE)
    configs = list(prior.degree_configurations(PROFILE))
    require(bool(configs), "empty relaxation cannot certify a bound")
    for c in configs:
        d = tuple(v for v in PROFILE if v)
        independent = (
            240
            + sum(s * (s + 2 - v) for s, v in zip(c.sigma, d, strict=True))
            + sum(v * (v - 6) for v in c.zeta)
        )
        require(independent == c.f, "core-zero identity mismatch")
    maximum = max(c.f for c in configs)
    require(type(claim) is int and claim == maximum == 228, "wrong T cap")
    maxima = [
        {"SIGMA": list(c.sigma), "ZETA": list(c.zeta), "F": c.f} for c in configs if c.f == maximum
    ]
    return {
        "STATUS": "EXISTING_PROOF_REUSED",
        "SOURCE": PRIOR_PATH,
        "SOURCE_SHA256": PRIOR_SHA,
        "COUNT": len(configs),
        "MAX_F": maximum,
        "ARGMAX": maxima,
        "COVERAGE": "Equal-degree/zero permutations preserve F and all necessary conditions; "
        "every coordinate range is exhausted; four Erdos-Gallai tests and Gale-Ryser "
        "are necessary for every support; simultaneous realizability is not assumed.",
        "CONFIGURATION_SHA256": digest(
            render([[list(c.sigma), list(c.zeta), list(c.h), list(c.a), c.f] for c in configs])
        ),
    }


def low_relaxation(linear: bool = True) -> dict[str, object]:
    """Complete low-support incidence box; omitted high incidences only enlarge it."""
    degrees = (3, 3, 2)
    ranges = [range(min(degrees[v] for v in pattern) + 1) for pattern in LOW_PATTERNS]
    losses: list[tuple[int, tuple[int, ...]]] = []
    for counts in product(*ranges):
        if (
            tuple(
                sum(n for n, p in zip(counts, LOW_PATTERNS, strict=True) if v in p)
                for v in range(3)
            )
            != degrees
        ):
            continue
        if linear and any(
            sum(n for n, p in zip(counts, LOW_PATTERNS, strict=True) if set(pair) <= set(p)) > 1
            for pair in combinations(range(3), 2)
        ):
            continue
        loss = sum(n * (3 if 2 in p else 2) for n, p in zip(counts, LOW_PATTERNS, strict=True))
        losses.append((loss, counts))
    floor = min(loss for loss, _counts in losses)
    return {
        "BOX_SIZE": 5184,
        "COUNT": len(losses),
        "MIN_LOSS": floor,
        "CONTAINED_CAP": 22 * 9 + 1 - floor,
        "ARGMIN": [list(counts) for loss, counts in losses if loss == floor],
        "PAIRS_UNIQUE": linear,
        "COVERAGE": "Every support has exactly one of seven nonempty low intersections "
        "or an empty intersection. Multiplicities cover the complete incidence box; "
        "empty intersections and high-degree capacities are relaxed, never restricted.",
    }


def contained_certificate(
    claim: int = NEW_CONTAINED_CAP, *, linear: bool = True
) -> dict[str, object]:
    validate_profile(PROFILE)
    require(linear, "pair linearity premise removed")
    cert = low_relaxation(linear)
    require(cert["MIN_LOSS"] == 12, "low-support loss lemma")
    require(type(claim) is int and cert["CONTAINED_CAP"] == claim == 187, "wrong contained cap")
    return {
        "CAP": claim,
        "ANALYTIC_CHAIN": "A<=sum_S(4+min d)<=22*9+1-(2*3+3*2)=187",
        "LOW_INCIDENCES": [3, 3, 2],
        "ALL_D6_SUPPORT_CAP": 1,
        "RELAXATION": cert,
    }


def route_b(cap: int, contained_cap: int) -> tuple[list[Term], Term]:
    require(type(cap) is int and 22 <= cap <= 276, "invalid T cap")
    require(type(contained_cap) is int and 0 <= contained_cap <= 198, "invalid contained cap")
    g = tuple(6 + d for d in PROFILE)
    w, u, top = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g), max(g)
    terms: list[Term] = []
    for t in range(22, cap + 1):
        numerator = u - (top - 2) * (w - 3 * t)
        k4 = max(0, -(-numerator // 4))
        contained = min(k4, contained_cap)
        s4 = max(S4_BASE, 679 * k4 - 231 * contained)
        s3 = 2800 * w + 11872 * (t - 22) - 30800
        bound = 372_228_640 - 63_838_600 + s3 - (4 * s4) // 7
        q = Fraction(numerator, 4)
        rational_k4 = max(0, -(-q.numerator // q.denominator))
        rational_s4 = max(S4_BASE, 448 * contained + 679 * (rational_k4 - contained))
        exact = Fraction(372_228_640 - 63_838_600 + s3) - Fraction(4 * rational_s4, 7)
        rational_bound = -(-exact.numerator // exact.denominator)
        require(
            k4 == rational_k4
            and s4 == rational_s4
            and bound == rational_bound
            and 0 <= bound - exact < 1,
            f"exact rational/rounding mismatch at T={t}",
        )
        terms.append((t, bound, k4, contained, s4, s3))
    return terms, max(terms, key=lambda term: term[1])


def maximum_sufficient_cap(contained_cap: int) -> int:
    terms, _argmax = route_b(276, contained_cap)
    running, accepted = 0, 21
    for t, bound, *_rest in terms:
        running = max(running, bound)
        if running <= NEXT_COMPETITOR:
            accepted = t
    return accepted


def validate_support(triples: Sequence[Support], pairs: Sequence[Support]) -> tuple[int, ...]:
    require(len(triples) == 22 and len(pairs) == 27, "wrong support counts")
    used: set[Support] = set()
    incidences, degrees = [0] * 20, [0] * 20
    for size, supports in ((3, triples), (2, pairs)):
        for support in supports:
            require(
                len(support) == size
                and len(set(support)) == size
                and all(type(v) is int and 0 <= v < 20 for v in support),
                "illegal support vertices",
            )
            for pair in combinations(sorted(support), 2):
                require(pair not in used, "repeated ticket pair")
                used.add(pair)
            for v in support:
                incidences[v] += 1
                degrees[v] += size == 3
    require(incidences == [6] * 20, "ticket capacity violated")
    validate_profile(degrees)
    return tuple(degrees)


def graph_identity(core: Sequence[int], zero: Sequence[int], g: set[Support]) -> dict[str, int]:
    """Exact cardinality identity on any simple graph, also usable as a falsification seam."""
    vertices = sorted([*core, *zero])
    require(len(vertices) == len(set(vertices)), "invalid partition")
    all_edges = set(combinations(vertices, 2))
    require(g <= all_edges, "illegal graph edge")
    h = all_edges - g
    ks, zs = set(core), set(zero)
    m = {e for e in h if set(e) <= ks}
    mz = {e for e in h if set(e) <= zs}
    nb = {v: {w for w in vertices if tuple(sorted((v, w))) in g} for v in vertices}

    def triangles(part: Sequence[int], edges: set[Support]) -> int:
        return sum(
            all(e in edges for e in combinations(t, 2)) for t in combinations(sorted(part), 3)
        )

    parts = (
        triangles(core, m),
        triangles(zero, mz),
        sum(len(nb[x] & nb[y] & zs) for x, y in m),
        sum(len(nb[u] & nb[v] & ks) for u, v in mz),
    )
    t_g, t_h = triangles(vertices, g), triangles(vertices, h)
    base = len(zero) * len(m) + len(core) * len(mz)
    base -= sum(len(nb[x] & zs) * sum(x in e for e in m) for x in core)
    base -= sum(len(nb[u] & ks) * sum(u in e for e in mz) for u in zero)
    require(t_h == base + sum(parts) and min(parts) >= 0, "remainder identity")
    require(
        2 * (t_g + t_h)
        == 2 * comb(len(vertices), 3)
        - sum(len(nb[v]) * (len(vertices) - 1 - len(nb[v])) for v in vertices),
        "Goodman identity",
    )
    return {"T": t_g, "T_H": t_h, "BARE": base, "P": sum(parts)}


def compute_result() -> dict[str, object]:
    source, identity, reused, new = (
        source_authority(),
        goodman(),
        prior_cap(),
        contained_certificate(),
    )
    old_terms, old = route_b(SOURCE_CAP, 198)
    alone_terms, alone = route_b(SOURCE_CAP, NEW_CONTAINED_CAP)
    terms, best = route_b(PRIOR_CAP, NEW_CONTAINED_CAP)
    prior_terms, prior_best = route_b(PRIOR_CAP, 198)
    require(old[1] == OLD_BOUND and len(terms) == 207, "source Route-B recount")
    require(
        terms == alone_terms[: len(terms)] and prior_terms == old_terms[: len(terms)],
        "envelope prefix",
    )
    require(best == (228, 313_062_208, 221, 187, 106_862, 4_733_232), "argmax term")
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "FULL_PROFILE_BOUND_PROVED_SELF_CHECK_ONLY",
        "JUDGE_MODE": "SELF_CHECK_ONLY",
        "PROOF_SCOPE": "FULL_PROFILE",
        "PROOF": __doc__,
        "FROZEN_HEAD": FROZEN_HEAD,
        "FROZEN_TREE": FROZEN_TREE,
        "FROZEN_HEAD_TREE": "MATCH",
        "FROZEN_RESULT_SHA256": FROZEN_SHA,
        "FROZEN_RESULT_SHA256_STATUS": "MATCH",
        "PROFILE_ID": PROFILE_ID,
        "DEGREE_PROFILE": "6^3,5^8,3^2,2^1,0^6",
        "DEGREE_SUM": 66,
        "DEGREE_SQUARE_SUM": 330,
        "GOODMAN_CONSTANT": 294,
        "SOURCE_T_CAP": SOURCE_CAP,
        "SOURCE_S4_BASE": S4_BASE,
        "SOURCE_OLD_BOUND": OLD_BOUND,
        "SOURCE_LOCATOR": SOURCE_LOCATOR,
        "SOURCE_ROW": source,
        "GOODMAN_IDENTITY": identity,
        "CORE_ZERO_DECOMPOSITION": identity["F"],
        "NONNEGATIVE_REMAINDER": identity["P"],
        "LOAD_BEARING_PREMISES": [
            "22 triple supports; 27 pair supports; six labels per ticket",
            "all ticket pairs occur at most once",
            "exact target degree multiset",
            "two degree-3 vertices and one degree-2 vertex",
            "only three degree-6 vertices",
            "existing complete necessary degree relaxation",
            "frozen Route-B Bonferroni coefficients",
        ],
        "PRIOR_ART": reused,
        "PROVED_T_CAP": PRIOR_CAP,
        "T_CAP_ORIGIN": "EXISTING_FROZEN_PROOF",
        "NEW_RESTRICTION": new,
        "RELAXATION_SUPERSET_COMPLETENESS": "PROVED",
        "COUNTEREXAMPLE_STATUS": "NONE_TO_PROVED_INEQUALITIES; ATTAINMENT_NOT_ASSERTED",
        "UNPROVED_ASSUMPTIONS": [],
        "SUFFICIENT_CAP_FOR_NEXT_COMPETITOR": maximum_sufficient_cap(198),
        "SUFFICIENT_CAP_WITH_NEW_RESTRICTION": maximum_sufficient_cap(NEW_CONTAINED_CAP),
        "NEW_ADMISSIBLE_BOUND": best[1],
        "OWNER_BOUND_REDUCTION": OLD_BOUND - best[1],
        "NEW_RESTRICTION_ONLY_BOUND_AT_FROZEN_CAP": alone[1],
        "NEW_RESTRICTION_ONLY_REDUCTION": OLD_BOUND - alone[1],
        "REUSED_PRIOR_BOUND": prior_best[1],
        "NOVEL_RESTRICTION_GAIN_AT_PRIOR_CAP": prior_best[1] - best[1],
        "NEXT_COMPETITOR_BOUND": NEXT_COMPETITOR,
        "BELOW_NEXT_COMPETITOR": best[1] <= NEXT_COMPETITOR,
        "INCUMBENT": INCUMBENT,
        "PROFILE_BOUND_BELOW_INCUMBENT": best[1] < INCUMBENT,
        "ROUTE_B_INTEGER_RECOUNT": "PASS_ALL_T",
        "EXACT_RATIONAL_CROSSCHECK": "PASS_ALL_T",
        "ROUNDING_CHECK": "PASS_CEIL_K4_FLOOR_S4_CEIL_RATIONAL_BOUND",
        "ARGMAX_TERM": list(best),
        "ROUTE_B": {
            "TERM_ORDER": ["T", "BOUND", "K4_FLOOR", "CONTAINED_CAP", "S4", "S3"],
            "W": 828,
            "U": 2324,
            "GMAX": 12,
            "OLD_A_MAX": 198,
            "NEW_A_MAX": NEW_CONTAINED_CAP,
            "ALL_OLD_T_TERMS": [list(t) for t in old_terms],
            "ALL_NEW_T_TERMS_TO_FROZEN_CAP": [list(t) for t in alone_terms],
            "ADMISSIBLE_T_RANGE": [22, PRIOR_CAP],
            "ALL_ADMISSIBLE_T_TERMS": [list(t) for t in terms],
        },
        "NEGATIVE_CASE_RESULTS": {
            "PAIR_LINEARITY_REMOVED": low_relaxation(False),
            "GUARDS": [
                "wrong profile",
                "illegal support",
                "wrong T/contained cap",
                "source SHA",
                "Goodman/remainder identity",
                "removed pair-linearity premise",
            ],
        },
        "CPU_PROCESS_COUNT": 1,
        "CPU_BUDGET_SECONDS": 120,
        "PREFLIGHT_LEDGER_REPLAY_CPU_SECONDS": 38.393049,
        "HEAVY_SOLVER_STARTED": "NO",
        "FAMILY_GAIN_CLAIMED": 0,
        "NEW_WINNING_OUTCOMES": 0,
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "PUSH": "NOT_RUN",
        "MERGE": "NOT_RUN",
        "PRODUCTION_MUTATION": "NONE",
        "DELIVERY": "LOCAL_COMMIT_ONLY",
    }


def main() -> None:
    payload = render(compute_result())
    if RESULT_PATH.exists():
        stored = RESULT_PATH.read_bytes()
        research = obj(json.loads(stored))
        research.pop("VALIDATION", None)
        require(render(research) == payload, "result path changed")
        payload = stored
    else:
        with RESULT_PATH.open("xb") as output:
            output.write(payload)
    print(
        json.dumps(
            {
                "RESULT": str(RESULT_PATH),
                "RESULT_SHA256": digest(payload),
                "BOUND": 313_062_208,
                "CAP": 228,
                "CONTAINED_CAP": 187,
            }
        )
    )


if __name__ == "__main__":
    main()
