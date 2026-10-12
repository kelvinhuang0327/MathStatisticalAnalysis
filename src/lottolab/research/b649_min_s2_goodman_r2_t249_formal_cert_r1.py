"""Formal Goodman R2 certificate for 66665555554421100000 in the current min-S2 family.

Domain. There are 20 tickets, six labels per ticket, 22 triple labels and 27
pair labels. Every ticket pair occurs in at most one support (pair linearity).
For d=(6^4,5^6,4^2,2,1,1,0^5), deg_G(v)=2d_v+(6-d_v)=6+d_v.
Thus E=3*22+27=93 and W=sum C(6+d_v,2)=829. On any three vertices with
e edges, the indicator of being a triangle or independent is
1-e+C(e,2). Summing gives T+I=C(20,3)-18E+W=295. Each support triple is a
distinct G triangle, so 22<=T. T here includes the 22 support triangles.

Partition. C={d>0} has 15 vertices, Z={d=0} has five. All triples lie in C.
Let m count pair supports inside C, b_i=|N_G(i) intersect Z|, and F=G[Z]^c.
The core pair capacity is 24. Consequently cross edges=24-2m, G[Z]
edges=3+m, core nonedges=39-m and F edges=7-m. Hence 0<=m<=7.
Every legal structure has 0<=b_i<=6-d_i and sum b_i=24-2m. Put
h_i=deg_{G[C]^c}(i)=8-d_i+b_i. For f_z=deg_F(z), cross degree c_z=2+f_z.

L incidence lemma. L=(z,x,y) has triple degrees (2,1,1), and R=C minus L has
12 vertices. Every one of the four d=6 hubs has 12 distinct triple-shadow
neighbours and no pair labels; only eleven other R vertices are available.
It therefore meets L through a triple. If a triple is {z,x,y}, the only
remaining L incidence is one z support, which can meet at most two R hubs.
If separate triples contain zx and zy, all four L incidences are spent and
only their two R endpoints can be hubs. Both contradict four hub neighbours.
Two shadow edges incident to x or y must be in its sole triple, hence imply
{z,x,y}. Pair linearity prohibits duplicate low pairs. Therefore the low
shadow mask is exactly among {empty,zx,zy,xy}; every legal pattern is included.
An independent finite enumeration of all multisets of nonempty L intersections
of its at most four incident triples checks these cases and their hub capacity.
It is a local incidence check, not support/portfolio search.

Lower bound. H=G[C]^c, A=sum h_i*b_i, Q=sum f_z^2. The exact mixed independent
triples are CCZ=5(39-m)-A+sum_{ij in H} common_Z_G(i,j), and
CZZ=77-11m-Q+sum_{zw in F} common_C_G(z,w). For each core vertex i,
at least max(0,C(b_i,2)-(3+m)) pairs of its Z neighbours are F edges; summing
these counts lower-bounds the latter common-neighbour sum. On a low H edge
ij, common_Z_G>=max(0,b_i+b_j-5). Write a_i=deg_{H[L]}(i) and r_i=h_i-a_i.
Every low H edge has at least max(0,r_i+r_j-12) common H neighbours in R.
These count disjoint CCC triangles with exactly two L vertices. Add one for
H[L]=K3, counting its all-L triangle. The remaining CCC and ZZZ counts are
nonnegative. Thus I>=272-16m-A-Q+S+U+V, with S,U,V the three floors just given.
No triangle is counted in two of S,U,V: they count CZZ, CCZ, CCC respectively.

Completeness. Enumerate all product(7-d_i) = 103680 labelled b vectors,
retaining exactly the necessary sum/m relation. Enumerate all 1024 labelled
F masks, retaining edge counts 0..7, and group only by sorted f. The objective
depends on F solely through Q, so this quotient loses no lower-bound value.
For each retained b and F-degree class, include all four low shadow patterns
and all eight low pair masks subject only to disjointness, pair degrees
<=6-d_i-b_i, and pair-mask size<=m. All follow from a legal structure;
no graphicality, Gale-Ryser, construction failure or sampling is used.
The minimum over this enlarged domain gives I floors 59,56,55,50,52,52,50,46
for m=0..7. Hence I>=46 and T<=249 universally; attainment is not asserted.

Objective and authority. Recompute every T=22..249 Route-B term, compare with
the pinned R32 and split-cap implementations, and check exact rational ceilings.
Its maximum 313254468 lies 9420 below the incumbent. Replay the SHA-sealed
a022431 bounds projection and cursor, modifying one row only in Scenario 1.
Scenario 2 additionally adopts the Owner-confirmed research caps 331->244 and
111->259 in memory. It is PROJECTED_ONLY and grants neither row formal authority.
The original authority's metadata caveats and unresolved cursor are preserved
by immutable source reference; no complete new ledger metadata digest is claimed.
The historical R2 math is provenance only: historical resource conformance was
refuted, its U64 objective is not the current Route-B certificate, and no
Bonferroni-5 donor, solver, DB, RUN1, shared ledger or remote write is used.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from itertools import combinations, combinations_with_replacement, product
from math import comb
from pathlib import Path

from . import b649_k20_min_s2_route_b_current_owner_refinement_r32 as r32
from . import b649_k20_min_s2_topw12_split_cap_certificate_r1 as split
from . import b649_min_s2_three_tied_owner_combined_authority_r1 as authority

TASK_ID = "B649_MIN_S2_GOODMAN_R2_T249_FORMAL_CERT_R1"
BASE_HEAD = "a022431765bad9d4fb7aa3bf3ef3ca361e20e5c0"
BASE_TREE = "c58074e0b0e3d8aa0e5f52b694ce86e803fedc71"
OWNER_CONVERSATION_ID = "01a12f6b-f4c3-7892-ac05-a647440bd631"
TARGET = "66665555554421100000"
DEGREES = tuple(map(int, TARGET))
CORE = DEGREES[:15]
CAP = 249
OLD_CAP = 265
OLD_BOUND = 313_397_860
INCUMBENT = 313_263_888
S4_BASE = 112
EXPECTED_FLOORS = (59, 56, 55, 50, 52, 52, 50, 46)
LOW_EDGES = ((0, 1), (0, 2), (1, 2))
DIRECTORY = "docs/research/matrix-native-results"
BASE_RESULT = f"{DIRECTORY}/b649-min-s2-three-tied-owner-combined-authority-r1-result.json"
BASE_RESULT_SHA = "75d171e495487720bc8dc8f50d9d87b858a6236349db466fcdfa1b259b89cc82"
RESULT_PATH = authority.ROOT / DIRECTORY / "b649-min-s2-goodman-r2-t249-formal-cert-r1-result.json"
SOURCE_PINS = {
    "b649_min_s2_three_tied_owner_combined_authority_r1": (
        "bd5a778d0a3474c2fa7d673b9a9c8481fce4b5b70775e813b5ddd1aeace8dc91"
    ),
    "b649_k20_min_s2_route_b_current_owner_refinement_r32": (
        "d2bd52eaa53825fc138b95f42d06ec6152757ae25a70212b0674bf8ea311dc1d"
    ),
    "b649_k20_min_s2_topw12_split_cap_certificate_r1": (
        "dd31017a685c809f494b359b7eece3fb3d832aef7f55699f7872dec53e25f784"
    ),
    "b649_k20_min_s2_realizable_core_class_bound_r4": (
        "cbc57debfcc037b8be605f9c3e157dba9029fbbcca50fa05dcff99390066edec"
    ),
    "b649_k20_min_s2_dangerous_core_realizability_r5": (
        "ad2c524bcdb716af1f1f744435576376499e3f39c3a744aec613542c41964487"
    ),
    "b649_k20_min_s2_current_cursor_dynamic_family_max_r30": (
        "230cb455bb162f6c8ab428afbbc8e7d9cbc7ee3c88575ef247e8d57ae925acb5"
    ),
    "b649_k20_min_s2_resolved_above_cursor_owner_chase_r20": (
        "b63081af598a6366ab9989f00f3e269052e8edbc41956a0771941dc03891b74e"
    ),
}
HISTORICAL_SHA256 = {
    "verify_goodman_r2.py": "fc9fad3cc951395134789ab29ff14f7b2363d400acbeae9e7f1f39b9e1c59be6",
    "goodman_r2_accepted_result.json": (
        "0fc4e3b9a38c62a250473f86cd5e7cc2030a43da257430aa2cc16a866b38cace"
    ),
    "goodman_r2_result.json": "c9b09d4848f6cf34f8e9da6dbf0935d74fb6e1c5028c2a7d8af632d0a1b1fdfa",
}
PROJECTED_CAPS = {"66665555555331000000": 244, "66665555555411100000": 259}
require, obj, integer = authority.require, authority.obj, authority.integer
render, sha, git = authority.render, authority.sha, authority.git
type Term = tuple[int, int, int, int, int, int]


def premises(profile: str = TARGET) -> dict[str, object]:
    require(profile == TARGET, "wrong profile: theorem applies only to target")
    model = (
        r32.K20_TICKET_COUNT,
        r32.K20_TICKET_CAPACITY,
        r32.K20_TRIPLE_SUPPORT_COUNT,
        split.prior.r5.K20_DOUBLE_SUPPORT_COUNT,
        split.prior.r5.K20_LABEL_COUNT,
    )
    require(model == (20, 6, 22, 27, 49), "pinned support model differs")
    g = tuple(6 + d for d in DEGREES)
    e = 3 * model[2] + model[3]
    w = sum(comb(v, 2) for v in g)
    identity = comb(20, 3) - (20 - 2) * e + w
    require(sum(g) == 2 * e and sum(DEGREES) == 66, "degree/support identity differs")
    require((e, w, identity) == (93, 829, 295), "Goodman identity differs")
    require(len(CORE) == 15 and DEGREES.count(0) == 5, "core/zero split differs")
    require(sum(6 - d for d in CORE) == 24, "core pair capacity differs")
    return {
        "PROFILE": profile,
        "TICKETS": 20,
        "LABELS_PER_TICKET": 6,
        "TRIPLE_LABELS": 22,
        "PAIR_LABELS": 27,
        "PAIR_LINEARITY": "REQUIRED",
        "E": e,
        "W": w,
        "T_PLUS_I": identity,
        "T_MIN": 22,
        "CORE_SIZE": 15,
        "ZERO_SIZE": 5,
        "CORE_PAIR_CAPACITY": 24,
        "M_ACCOUNTING": [
            {
                "m": m,
                "CROSS_EDGES": 24 - 2 * m,
                "ZERO_EDGES": 3 + m,
                "CORE_NONEDGES": 39 - m,
                "ZERO_NONEDGES": 7 - m,
            }
            for m in range(8)
        ],
    }


def incidence_templates() -> list[dict[str, object]]:
    """All local low-support intersections, before and after necessary hub coverage."""
    records: list[dict[str, object]] = []
    for n in range(1, 5):
        for supports in combinations_with_replacement(range(1, 8), n):
            if tuple(sum(bool(s & (1 << i)) for s in supports) for i in range(3)) != (2, 1, 1):
                continue
            edges: list[int] = []
            for s in supports:
                edges.extend(
                    bit for bit, (i, j) in enumerate(LOW_EDGES) if s & (1 << i) and s & (1 << j)
                )
            if len(edges) != len(set(edges)):
                continue
            mask = sum(1 << bit for bit in edges)
            hub_capacity = sum(3 - s.bit_count() for s in supports)
            records.append(
                {
                    "L_INTERSECTIONS": list(supports),
                    "SHADOW_MASK": mask,
                    "R_HUB_CAPACITY": hub_capacity,
                    "ACCEPTED": hub_capacity >= 4,
                }
            )
    return records


def incidence_masks() -> tuple[int, ...]:
    out = tuple(sorted({integer(t["SHADOW_MASK"]) for t in incidence_templates() if t["ACCEPTED"]}))
    require(out == (0, 1, 2, 4), "unproved incidence restriction")
    return out


@dataclass(frozen=True)
class LowOption:
    shadow: int
    pairs: int
    missing: int
    mixed: int
    core: int


@cache
def low_options(low_b: tuple[int, ...], m: int, shadows: tuple[int, ...]) -> tuple[LowOption, ...]:
    require(
        len(low_b) == 3 and all(0 <= v <= c for v, c in zip(low_b, (4, 5, 5), strict=True)),
        "invalid low incidence/cross degree",
    )
    p = tuple(c - b for c, b in zip((4, 5, 5), low_b, strict=True))
    h = tuple(c + b for c, b in zip((6, 7, 7), low_b, strict=True))
    options: list[LowOption] = []
    for shadow in shadows:
        for pairs in range(8):
            if shadow & pairs or pairs.bit_count() > m:
                continue
            pd = tuple(
                sum(bool(pairs & (1 << bit)) for bit, edge in enumerate(LOW_EDGES) if i in edge)
                for i in range(3)
            )
            if any(v > cap for v, cap in zip(pd, p, strict=True)):
                continue
            missing = 7 ^ (shadow | pairs)
            hd = tuple(
                sum(bool(missing & (1 << bit)) for bit, edge in enumerate(LOW_EDGES) if i in edge)
                for i in range(3)
            )
            r = tuple(v - a for v, a in zip(h, hd, strict=True))
            mixed = sum(
                max(0, low_b[i] + low_b[j] - 5)
                for bit, (i, j) in enumerate(LOW_EDGES)
                if missing & (1 << bit)
            )
            core = int(missing == 7) + sum(
                max(0, r[i] + r[j] - 12)
                for bit, (i, j) in enumerate(LOW_EDGES)
                if missing & (1 << bit)
            )
            options.append(LowOption(shadow, pairs, missing, mixed, core))
    require(bool(options), "empty low-incidence relaxation")
    return tuple(options)


def zero_classes() -> tuple[list[set[tuple[int, ...]]], list[int]]:
    classes: list[set[tuple[int, ...]]] = [set() for _ in range(8)]
    counts = [0] * 8
    edges = tuple(combinations(range(5), 2))
    for mask in range(1024):
        e = mask.bit_count()
        if e > 7:
            continue
        degree = tuple(
            sum(bool(mask & (1 << bit)) for bit, edge in enumerate(edges) if v in edge)
            for v in range(5)
        )
        m = 7 - e
        classes[m].add(tuple(sorted(degree)))
        counts[m] += 1
    require(counts == [comb(10, 7 - m) for m in range(8)], "zero graph coverage differs")
    return classes, counts


def zero_neighbour_vectors() -> Iterator[tuple[int, ...]]:
    yield from product(*(range(7 - d) for d in CORE))


def enumerate_relaxation(shadows: tuple[int, ...]) -> dict[str, object]:
    """Diagnostic relaxation. Only certify() may adopt its result as a theorem."""
    classes, zero_counts = zero_classes()
    floors = [10**9] * 8
    states = [0] * 8
    vectors = [0] * 8
    witnesses: list[dict[str, object]] = [{} for _ in range(8)]
    digest = hashlib.sha256()
    raw_count = 0
    for b in zero_neighbour_vectors():
        raw_count += 1
        digest.update(bytes(b))
        residual = 24 - sum(b)
        if residual % 2 or not 0 <= residual // 2 <= 7:
            continue
        m = residual // 2
        vectors[m] += 1
        h = tuple(8 - d + v for d, v in zip(CORE, b, strict=True))
        a = sum(v * cross for v, cross in zip(h, b, strict=True))
        s = sum(max(0, comb(v, 2) - (3 + m)) for v in b)
        options = low_options(b[12:], m, shadows)
        for f in sorted(classes[m]):
            q = sum(v * v for v in f)
            states[m] += len(options)
            for option in options:
                value = 272 - 16 * m - a - q + s + option.mixed + option.core
                if value < floors[m]:
                    floors[m] = value
                    witnesses[m] = {
                        "B": list(b),
                        "F_DEGREES": list(f),
                        "A": a,
                        "Q": q,
                        "S": s,
                        "U": option.mixed,
                        "V": option.core,
                        "SHADOW": option.shadow,
                        "PAIRS": option.pairs,
                        "LOW_COMPLEMENT": option.missing,
                        "I_FLOOR": value,
                    }
    require(raw_count == 103680, "incomplete labelled zero-neighbour vectors")
    return {
        "LABELLED_VECTORS": raw_count,
        "VECTORS_SHA256": digest.hexdigest(),
        "RETAINED_VECTORS_BY_M": vectors,
        "RELAXED_STATES_BY_M": states,
        "ZERO_MASKS_VISITED": 1024,
        "ZERO_GRAPH_COUNTS_BY_M": zero_counts,
        "ZERO_DEGREE_CLASSES_BY_M": [len(c) for c in classes],
        "I_FLOORS": floors,
        "MIN_I": min(floors),
        "MINIMIZERS": witnesses,
        "LOW_SHADOW_MASKS": list(shadows),
        "PAIR_MASKS_VISITED_PER_SHADOW": 8,
        "GRAPHICALITY_OR_BIPARTITE_FILTER": "NONE",
        "SAMPLING": "NONE",
    }


def certify(profile: str = TARGET, shadows: tuple[int, ...] | None = None) -> dict[str, object]:
    premises(profile)
    allowed = incidence_masks()
    require(shadows is None or shadows == allowed, "invalid incidence restriction")
    result = enumerate_relaxation(allowed)
    floors = tuple(integer(v) for v in authority.items(result["I_FLOORS"]))
    require(floors == EXPECTED_FLOORS, "eight I floors differ")
    require(295 - min(floors) == CAP, "T cap not derived from Goodman identity")
    return result


def route_b(profile: str, cap: int, base: int = S4_BASE) -> list[Term]:
    require(profile in (TARGET, *PROJECTED_CAPS), "wrong profile for Route-B replay")
    require(type(cap) is int and 22 <= cap <= 265 and base == 112, "wrong Route-B cap/base")
    d = tuple(map(int, profile))
    g = tuple(6 + v for v in d)
    w, c3 = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g)
    amax = Fraction(sum(v * (deg - 2) for v, deg in zip(d, g, strict=True)), 3)
    out: list[Term] = []
    for t in range(22, cap + 1):
        excess = Fraction(c3 - (max(g) - 2) * (w - 3 * t), 4)
        k4 = max(0, -((-excess.numerator) // excess.denominator))
        contained = min(k4, amax.numerator // amax.denominator)
        s4 = max(base, 448 * contained + 679 * (k4 - contained))
        s3 = 2800 * w + 11872 * (t - 22) - 30800
        rational = 372_228_640 - 63_838_600 + s3 - Fraction(4 * s4, 7)
        bound = -((-rational.numerator) // rational.denominator)
        require(0 <= bound - rational < 1, "official integer rounding differs")
        out.append((t, bound, k4, contained, s4, s3))
    require(
        out == r32.route_b_envelope(d, cap, base) == split.route_b_terms(d, cap, base),
        "pinned Route-B terms differ",
    )
    return out


def source_authority() -> dict[str, object]:
    require(
        git("rev-parse", f"{BASE_HEAD}^{{tree}}").decode().strip() == BASE_TREE,
        "base tree mismatch",
    )
    for stem, expected in SOURCE_PINS.items():
        path = f"src/lottolab/research/{stem}.py"
        raw = authority.blob(BASE_HEAD, path, expected)
        require((authority.ROOT / path).read_bytes() == raw, f"live source differs: {path}")
    return authority.decode(authority.blob(BASE_HEAD, BASE_RESULT, BASE_RESULT_SHA))


def baseline() -> tuple[dict[str, int], dict[str, object], dict[str, object]]:
    sealed = source_authority()
    bounds = {p: integer(v) for p, v in obj(sealed["RESOLVED_ROW_BOUNDS"]).items()}
    require(len(bounds) == 4647 and bounds[TARGET] == OLD_BOUND, "baseline rows/profile differ")
    require(
        sha(authority.projection(bounds)) == sealed["BOUNDS_SHA256_AFTER"],
        "baseline projection SHA mismatch",
    )
    cursor = obj(sealed["CURSOR"])
    six = authority.decode(
        authority.blob(
            BASE_HEAD, f"{DIRECTORY}/{authority.SIX}", authority.RESULT_PINS[authority.SIX]
        )
    )
    coverage = authority.decode(
        authority.blob(
            BASE_HEAD,
            f"{DIRECTORY}/{authority.COVERAGE}",
            authority.RESULT_PINS[authority.COVERAGE],
        )
    )
    require(cursor == authority.cursor_authority(six, coverage), "wrong baseline cursor")
    require(sha(render(cursor)) == sealed["CURSOR_AUTHORITY_SHA256_AFTER"], "cursor SHA mismatch")
    require(
        authority.family(bounds, cursor)
        == (integer(sealed["FAMILY_BOUND_AFTER"]), authority.items(sealed["NEW_FAMILY_OWNER_IDS"])),
        "baseline family differs",
    )
    require(
        max(t[1] for t in route_b(TARGET, OLD_CAP)) == OLD_BOUND,
        "current profile cap/S4 authority differs",
    )
    return bounds, cursor, sealed


def scenarios(
    bounds: Mapping[str, int],
    cursor: Mapping[str, object],
    expected_cursor: Mapping[str, object],
    new_bound: int,
) -> dict[str, object]:
    require(render(cursor) == render(expected_cursor), "wrong cursor: tamper rejected")
    require(len(bounds) == 4647 and bounds[TARGET] == OLD_BOUND, "wrong scenario baseline")
    require(new_bound == max(t[1] for t in route_b(TARGET, CAP)), "unverified T249 row")
    one = dict(bounds)
    one[TARGET] = new_bound
    best1, owners1 = authority.family(one, cursor)
    two = dict(one)
    projected: dict[str, object] = {}
    for p, cap in PROJECTED_CAPS.items():
        value = max(t[1] for t in route_b(p, cap))
        require(value < bounds[p], "projected row does not improve baseline")
        two[p] = value
        projected[p] = {
            "CAP": cap,
            "BOUND": value,
            "STATUS": "PROJECTED_ONLY",
            "AUTHORITY": "OWNER_CONFIRMED_RESEARCH_CAP_NOT_FORMAL_CERTIFICATE",
        }
    best2, owners2 = authority.family(two, cursor)
    unchanged = {p: v for p, v in bounds.items() if p != TARGET}
    require(unchanged == {p: v for p, v in one.items() if p != TARGET}, "other rows changed")
    require(
        sorted(p for p in bounds if bounds[p] != two[p]) == sorted((TARGET, *PROJECTED_CAPS)),
        "Scenario 2 must change exactly three rows",
    )
    require(
        (best2, owners2, best2 - INCUMBENT) == (313_396_120, ["65555555555550000000"], 132232),
        "projected family differs",
    )
    return {
        "SCENARIO_1": {
            "STATUS": "T249_ONLY_BASELINE_BOUND_PROJECTION",
            "FAMILY_BOUND": best1,
            "OWNER_IDS": owners1,
            "GAP": best1 - INCUMBENT,
            "ROWS_CHANGED": 1,
            "BOUNDS_SHA256": sha(authority.projection(one)),
            "OTHER_ROWS_UNCHANGED_SHA256": sha(authority.projection(unchanged)),
        },
        "SCENARIO_2": {
            "STATUS": "PROJECTED_ONLY",
            "FAMILY_BOUND": best2,
            "OWNER_IDS": owners2,
            "GAP": best2 - INCUMBENT,
            "ROWS_CHANGED": 3,
            "RESEARCH_ROWS": projected,
            "BOUNDS_SHA256": sha(authority.projection(two)),
            "FORMAL_T244_T259_AUTHORITY": "NOT_CLAIMED",
        },
        "CURSOR_PRESERVED_SHA256": sha(render(cursor)),
        "BASELINE_INPUT_UNCHANGED": "PASS",
    }


def compute_result() -> dict[str, object]:
    bounds, cursor, sealed = baseline()
    theorem = certify()
    terms = route_b(TARGET, CAP)
    bound = max(t[1] for t in terms)
    require(
        (len(terms), terms[-1][4], bound, OLD_BOUND - bound, INCUMBENT - bound)
        == (228, 211603, 313254468, 143392, 9420),
        "expected scientific result differs",
    )
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "THEOREM_COMPLETE_PENDING_FRESH_CONTEXT_JUDGE",
        "OWNER_CONVERSATION_ID": OWNER_CONVERSATION_ID,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TARGET_PROFILE": TARGET,
        "PROOF": __doc__,
        "SUPPORT_MODEL": premises(),
        "INCIDENCE_TEMPLATES": incidence_templates(),
        "THEOREM": {
            "STATUS": "PROVEN",
            "ENUMERATION": theorem,
            "I_FLOOR": theorem["MIN_I"],
            "T_CAP": CAP,
            "ATTAINMENT": "NOT_ASSERTED",
        },
        "ROUTE_B": {
            "ALL_T_TERMS": [list(t) for t in terms],
            "TERM_COUNT": len(terms),
            "S4_FLOOR_AT_CAP": terms[-1][4],
            "MAXIMIZING_T": terms[-1][0],
            "INTEGER_RATIONAL_AND_TWO_PINNED_IMPLEMENTATIONS": "PASS",
        },
        "PROFILE_BOUND": bound,
        "PROFILE_DELTA": OLD_BOUND - bound,
        "STRICT_GAIN_EXCLUDED": "YES",
        "DISTANCE_BELOW_INCUMBENT": INCUMBENT - bound,
        "ROW_UPDATE": {
            "BEFORE": {"cap": OLD_CAP, "bound": OLD_BOUND, "s4_base": S4_BASE},
            "AFTER": {"cap": CAP, "bound": bound, "s4_base": S4_BASE},
        },
        "FAMILY_SCENARIOS": scenarios(bounds, cursor, cursor, bound),
        "BASE_AUTHORITY": {
            "RESULT": BASE_RESULT,
            "SHA256": BASE_RESULT_SHA,
            "BOUNDS_SHA256": sealed["BOUNDS_SHA256_AFTER"],
            "SOURCE_PINS": SOURCE_PINS,
            "CURSOR": cursor,
            "INHERITED_CAVEATS": sealed["INHERITED_CAVEATS_AND_STATUS_VERBATIM"],
            "FULL_METADATA_DIGEST_AFTER": "NOT_CLAIMED_BOUND_PROJECTION_ONLY",
        },
        "HISTORICAL_R2": {
            "LOCATOR": "~/.codex/worktrees/b649-k20-666655555544211-goodman-r2",
            "SHA256": HISTORICAL_SHA256,
            "MATHEMATICS": "PROVED",
            "RESOURCE_CONFORMANCE": "REFUTED",
            "PROMOTED_AS_AUTHORITY": "NO",
            "HISTORICAL_U64_BOUND_USED": "NO",
            "BONFERRONI_5_USED": "NO",
        },
        "IMPLEMENTATION_SHA256": sha(Path(__file__).read_bytes()),
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "HEAVY_SOLVER_STARTED": "NO",
        "T244_T259_PROOFS_REEXECUTED": "NO",
        "SHARED_LEDGER_MUTATED": "NO",
        "DB_OR_RUN1_MUTATED": "NO",
        "REMOTE_WRITE": "NO",
        "WORKERS": 1,
    }


def main() -> None:
    raw = render(compute_result())
    if RESULT_PATH.exists():
        require(RESULT_PATH.read_bytes() == raw, "sealed result differs")
    else:
        with RESULT_PATH.open("xb") as output:
            output.write(raw)
    print(json.dumps({"RESULT": str(RESULT_PATH), "SHA256": sha(raw), "T_CAP": CAP}))


if __name__ == "__main__":
    main()
