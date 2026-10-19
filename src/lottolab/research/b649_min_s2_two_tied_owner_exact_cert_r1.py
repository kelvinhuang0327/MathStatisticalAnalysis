"""Two specified min-S2 owners, with immutable scientific authority and no search.

MODEL. Twenty tickets have six supports each, 22 triple supports and 27 pair
supports. Pair-linearity makes all shadow and pair edges distinct. If d counts
triple supports, deg_G=6+d, |G|=93, deg_H=13-d and |H|=97, H=complement G.
On a vertex triple, counting its G edges and G wedges gives
 t(G)+t(H)=C(20,3)-18|G|+sum C(6+d,2).
Counting H edges instead gives C(20,3)-18|H|+sum C(13-d,2), independently.

A. Reuse the committed e44a635f general split theorem, not a second theorem
implementation. Its necessary domain is sigma_x in 0..6-d_x and zeta_u in
max(0,7-z)..min(6,k). The residual core pair graph, H[K], G[Z], H[Z] must
be graphical and the cross lists bipartite graphical. These are necessary,
not sufficient, conditions; separate compatibility cannot exclude a legal
structure. Sorting within equal-d classes and within Z only relabels vertices.
The exact identity is T=F-P with P a sum of four nonnegative cardinalities.
For A every configuration is in the general P>=0 branch. Re-evaluate its 423
degree configurations using that existing implementation and adopt T<=244.

B. K has 15 vertices, Z has 5 and L has the three d=1 vertices. Each of the
four d=6 vertices has 12 distinct shadow neighbours, all in K. Only 11 other
vertices of K lie outside L, so every high vertex needs a shadow neighbour
in L. L has six shadow incidences in total; at least four go to the high
vertices. Thus 2|shadow[L]|<=2, or |shadow[L]|<=1. (This proof deliberately
uses only this weaker necessary restriction.) L has 15 pair incidences,
of which sum_L sigma go to Z. Consequently
 2|G[L]| <= 2 + 15 - sum_L sigma = 17-sum_L sigma.
All eight labelled G[L] graphs satisfying this inequality are retained. No
assumption about a legal triple decomposition or joint realization is made.

B IDENTITIES. Put M=H[K], F=H[Z], h_x=8-d_x+sigma_x,
a_u=deg_F(u), zeta_u=2+a_u, and e=|F|. Incidence gives
r=sum sigma=sum zeta=10+2e and |M|=32+e. The total core pair capacity
is 24, so 0<=e<=7. A mixed triangle with core edge xy has exactly
5-sigma_x-sigma_y+c_Z(xy) zero apices, where c_Z is the number of
common G neighbours in Z. A mixed triangle with zero edge uv has
15-zeta_u-zeta_v+c_K(uv) core apices. Therefore
t(H)=t(M)+t(F)+5|M|-sum sigma*h+15e-sum zeta*a+C_Z+C_K.
Both corrections are sums of cardinalities and are nonnegative. For an
edge xy of J=H[L], c_Z(xy)>=max(0,sigma_x+sigma_y-5). Ignoring the other
corrections and clamping the whole core-core-zero count to zero is valid.

CORE FLOORS. For v in M let Q be its 14-h_v nonneighbours. The exact
neighbourhood identity is t_v=|M|-h_v-sum_Q h+|M[Q]|. Thus t_v is at least
max(0,|M|-h_v-the largest 14-h_v other degrees). Since sum t_v=3t(M),
both max_v t_v and ceil(sum_v t_v/3) are lower bounds. The omitted |M[Q]|
is nonnegative. Separately, for xy in J, the two H neighbourhoods in the
12 vertices K\\L have sizes h_x-deg_J(x), h_y-deg_J(y); their intersection
has size at least max(0,h_x+h_y-deg_J(x)-deg_J(y)-12). These triangles
have exactly two L vertices and distinct J edges. Add t(J), which counts
three-L triangles, without overlap. Take the maximum of these two floors.
The zero graph is enumerated exactly, so t(F) is counted directly; each
zero-edge mixed count is at least max(0,15-zeta_u-zeta_v).

COVERAGE. Use the existing complete EG/GR degree generator for B and retain
each distinct class-sorted sigma. Every legal graph survives its necessary
filters. For each class exhaust all eight labelled G[L] masks, filtered only
by the proven sum inequality. Independently exhaust all 1024 labelled F
graphs. Keep equal cross sums and Gale-Ryser, never sufficiency claims. The
counts 339/2565/1024 are checked after enumeration, never used as loop limits.
The derived minima differ from the Packet's unsourced table. The Owner's
continuation requires reporting the actual minima and their difference,
without claiming reproduction of that table. Adopt only the requested
t(H)>=39 and T<=259 after checking the computed minimum implies them.
The stronger computed consequence is supplemental. No T=259 witness is asserted.

INTEGRATION. Load the sealed a022431 4647-row bound projection, not a replay
or rewrite of a shared ledger. Pin its source, result, cursor and inherited
statuses. Replace exactly A and B in a copy and check all other 4645 bounds.
Compute the family maximum and every tie from every row and the cursor.
The original pending snapshots, SELF_CHECK_ONLY and historical resource
failure remain verbatim. The output is a bounds projection; it does not
claim refreshed complete row metadata, attainability or global optimality.
Only the requested two Route-B envelopes are evaluated. No solver, portfolio
enumeration, database/runtime/remote mutation or earlier cap proof is run.
"""

from __future__ import annotations

import ast
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
from math import comb
from pathlib import Path

from . import b649_k20_min_s2_nb_w808_frontier_r1 as rational
from . import b649_k20_min_s2_route_b_current_owner_refinement_r32 as official
from . import b649_k20_min_s2_topw12_split_cap_certificate_r1 as split
from . import b649_min_s2_three_tied_owner_combined_authority_r1 as prior

TASK_ID = "B649_MIN_S2_TWO_TIED_OWNER_EXACT_CERTIFICATE_R1"
BASE_HEAD = "a022431765bad9d4fb7aa3bf3ef3ca361e20e5c0"
BASE_TREE = "c58074e0b0e3d8aa0e5f52b694ce86e803fedc71"
ROOT = Path(__file__).resolve().parents[3]
DIRECTORY = "docs/research/matrix-native-results"
PROFILE_A, PROFILE_B = "66665555555331000000", "66665555555411100000"
TARGETS = (PROFILE_A, PROFILE_B)
CAPS = {PROFILE_A: 244, PROFILE_B: 259}
EXPECTED_BOUNDS = {PROFILE_A: 313_218_904, PROFILE_B: 313_353_140}
PACKET_FLOORS_COMPARISON_ONLY = (41, 42, 42, 39, 41, 44, 47, 54)
INCUMBENT = 313_263_888
FROZEN = f"{DIRECTORY}/b649-min-s2-three-tied-owner-combined-authority-r1-result.json"
FROZEN_SHA = "75d171e495487720bc8dc8f50d9d87b858a6236349db466fcdfa1b259b89cc82"
GENERIC_HEAD = "e44a635f1932166734aaa3f64f9469c0e63c7520"
GENERIC_TREE = "8d1b5d168157e8cea47ac44f9ca7537ace053c31"
GENERIC_SOURCE_SHA = "dd31017a685c809f494b359b7eece3fb3d832aef7f55699f7872dec53e25f784"
GENERIC_RESULT_SHA = "e6bab2ae892cfccd5dcea97781e99ad1a664029e55a80c374e3441a586ba5f9d"
S4_ROWS = f"{DIRECTORY}/b649-min-s2-six-row-existing-s4-family-authority-r1-sources/s4-result.json"
S4_ROWS_SHA = "e376c3c15a767bdc75fe937f8ad36adf2ae94cc705628caccfab7f655c55852c"
RESULT_PATH = ROOT / DIRECTORY / "b649-min-s2-two-tied-owner-exact-cert-r1-result.json"
require, obj, items, integer, string = (
    prior.require,
    prior.obj,
    prior.items,
    prior.integer,
    prior.string,
)
sha, render, projection, git, blob = (
    prior.sha,
    prior.render,
    prior.projection,
    prior.git,
    prior.blob,
)
type Pair = tuple[int, int]
type Term = tuple[int, int, int, int, int, int]


def profile(pid: str) -> tuple[int, ...]:
    require(pid in TARGETS, "wrong profile identity")
    d = split.profile_values(pid)
    require("".join(map(str, d)) == pid, "noncanonical profile")
    return d


def provenance() -> dict[str, object]:
    require(
        git("rev-parse", f"{BASE_HEAD}^{{tree}}").decode().strip() == BASE_TREE,
        "base tree mismatch",
    )
    message = prior.commit_identity(BASE_HEAD, BASE_TREE)
    pins: dict[str, str] = {}
    # Pin the complete loaded research import closure, including indirect helpers.
    for name, module in sorted(sys.modules.copy().items()):
        if name == "lottolab.research":
            continue  # This repository uses a namespace package, with no __init__.py.
        if name.startswith("lottolab.research"):
            require(module.__file__ is not None, "research module without source")
            path = Path(string(module.__file__)).resolve()
            require(path.is_relative_to(ROOT), "research helper outside isolated worktree")
            relative = path.relative_to(ROOT).as_posix()
            if relative == Path(__file__).relative_to(ROOT).as_posix():
                continue
            raw = git("show", f"{BASE_HEAD}:{relative}")
            require(path.read_bytes() == raw, f"helper source tamper: {relative}")
            pins[relative] = sha(raw)
    source_path = "src/lottolab/research/b649_k20_min_s2_topw12_split_cap_certificate_r1.py"
    source = blob(GENERIC_HEAD, source_path, GENERIC_SOURCE_SHA)
    result_path = f"{DIRECTORY}/{split.RESULT_FILENAME}"
    generic = prior.decode(blob(GENERIC_HEAD, result_path, GENERIC_RESULT_SHA))
    require(
        git("rev-parse", f"{GENERIC_HEAD}^{{tree}}").decode().strip() == GENERIC_TREE,
        "generic theorem tree mismatch",
    )
    require(source == git("show", f"{BASE_HEAD}:{source_path}"), "generic implementation differs")
    require(
        ast.get_docstring(ast.parse(source), clean=False) == generic["PROOF"],
        "generic theorem proof/result mismatch",
    )
    return {
        "BASE_JUDGE_COMMIT_MESSAGE_VERBATIM": message,
        "MODULE_SHA256": pins,
        "GENERIC_THEOREM": {
            "HEAD": GENERIC_HEAD,
            "TREE": GENERIC_TREE,
            "SOURCE": source_path,
            "SOURCE_BLOB": git("rev-parse", f"{GENERIC_HEAD}:{source_path}").decode().strip(),
            "SOURCE_SHA256": GENERIC_SOURCE_SHA,
            "RESULT": result_path,
            "RESULT_BLOB": git("rev-parse", f"{GENERIC_HEAD}:{result_path}").decode().strip(),
            "RESULT_SHA256": GENERIC_RESULT_SHA,
            "STATUS_VERBATIM": {k: v for k, v in generic.items() if "STATUS" in k or "JUDGE" in k},
        },
    }


def validate_cursor(cursor: Mapping[str, object], expected: Mapping[str, object]) -> None:
    require(render(cursor) == render(expected), "cursor integrity mismatch")
    ids = [string(x) for x in items(cursor["PROFILE_IDS"])]
    band = obj(obj(cursor["PARTITION"])["UNRESOLVED_FRONTIER_UNDER_W785_CURSOR"])
    require(
        len(ids) == len(set(ids)) == cursor["PROFILE_COUNT"] == band["COUNT"] == 197,
        "cursor count mismatch",
    )
    require(sha(json.dumps(ids).encode()) == band["IDS_SHA256"], "cursor identities mismatch")
    coarse = obj(cursor["COARSE_BOUND_PROJECTION"])
    require(set(coarse) == set(ids), "cursor projection identities mismatch")
    for pid in ids:
        w = sum(comb(6 + int(d), 2) for d in pid)
        bound = 372_228_640 - 63_838_600 + 2800 * w + 11872 * (w // 3 - 22) - 30800 - 64
        require(coarse[pid] == bound, "cursor arithmetic mismatch")
    require(
        cursor["ID"] == "66544333333333332222"
        and cursor["BOUND"] == 313_394_584 == max(integer(v) for v in coarse.values()),
        "cursor representative mismatch",
    )


def frozen_authority() -> tuple[dict[str, int], dict[str, object]]:
    sealed = prior.decode(blob(BASE_HEAD, FROZEN, FROZEN_SHA))
    bounds = {p: integer(v) for p, v in obj(sealed["RESOLVED_ROW_BOUNDS"]).items()}
    validate_rows(list(bounds.items()))
    require(sha(projection(bounds)) == sealed["BOUNDS_SHA256_AFTER"], "frozen projection mismatch")
    cursor = obj(sealed["CURSOR"])
    validate_cursor(cursor, cursor)
    require(
        sha(render(cursor)) == sealed["CURSOR_AUTHORITY_SHA256_AFTER"],
        "frozen cursor hash mismatch",
    )
    require(
        prior.family(bounds, cursor) == (313_398_144, sorted(TARGETS))
        and sealed["NEW_FAMILY_OWNER_IDS"] == sorted(TARGETS)
        and sealed["INCUMBENT"] == INCUMBENT
        and sealed["GAP_TO_INCUMBENT"] == 134_256,
        "frozen family authority differs",
    )
    historical = prior.decode(blob(BASE_HEAD, S4_ROWS, S4_ROWS_SHA))
    recorded = [obj(row) for row in items(obj(historical["START_FAMILY"])["ROWS_ABOVE_CURSOR"])]
    for target in TARGETS:
        matches = [row for row in recorded if row["PROFILE_ID"] == target]
        require(
            len(matches) == 1
            and matches[0]["TRIANGLE_CAP"] == 264
            and matches[0]["BOUND"] == bounds[target],
            "sealed original row cap differs",
        )
    return bounds, sealed


def validate_rows(rows: Sequence[tuple[str, int]]) -> None:
    require(len(rows) == 4647, "wrong ledger row count")
    require(len({p for p, _ in rows}) == len(rows), "duplicate ledger row")
    require(all(type(v) is int for _, v in rows), "noninteger bound")
    require(all(sum(p == target for p, _ in rows) == 1 for target in TARGETS), "missing target row")


def premises(pid: str) -> dict[str, object]:
    model = split.prior.r5
    require(
        (
            model.K20_TICKET_COUNT,
            model.K20_TICKET_CAPACITY,
            model.K20_TRIPLE_SUPPORT_COUNT,
            model.K20_DOUBLE_SUPPORT_COUNT,
            model.K20_LABEL_COUNT,
            model.K20_TRIPLE_INCIDENCE_COUNT,
        )
        == (20, 6, 22, 27, 49, 66),
        "support model differs",
    )
    d = profile(pid)
    g, h = tuple(6 + x for x in d), tuple(13 - x for x in d)
    goodman = Fraction(comb(20, 3)) - Fraction(sum(x * y for x, y in zip(g, h, strict=True)), 2)
    inclusion = comb(20, 3) - 18 * (sum(h) // 2) + sum(comb(x, 2) for x in h)
    g_identity = comb(20, 3) - 18 * (sum(g) // 2) + sum(comb(x, 2) for x in g)
    require(
        sum(d) == 66
        and sum(g) == 186
        and sum(h) == 194
        and goodman == inclusion == g_identity == 298,
        "complement identity differs",
    )
    return {
        "PROFILE_ID": pid,
        "D": list(d),
        "G_EDGES": 93,
        "H_EDGES": 97,
        "GOODMAN": int(goodman),
        "H_INCLUSION_EXCLUSION": inclusion,
        "G_EDGE_WEDGE_IDENTITY": g_identity,
        "W": sum(comb(x, 2) for x in g),
    }


def theorem_a() -> dict[str, object]:
    facts = premises(PROFILE_A)
    cert = split.split_certificate(profile(PROFILE_A))
    require(
        string(PROFILE_A) != split.SPECIAL
        and cert["DEGREE_CONFIGURATION_COUNT"] == 423
        and cert["BRANCH_COUNTS"] == {"A_NONNEGATIVE_P": 423}
        and cert["TRIANGLE_CAP"] == 244,
        "A generic theorem applicability/cap differs",
    )
    return {
        **facts,
        **cert,
        "STATUS": "PROVEN",
        "ATTAINABILITY": "NOT_ESTABLISHED",
        "IMPLEMENTATION": "REUSED_COMMITTED_GENERAL_SPLIT_THEOREM",
    }


def shadow_restriction(pid: str = PROFILE_B) -> dict[str, int]:
    require(pid == PROFILE_B, "shadow restriction wrong profile")
    core = [d for d in profile(pid) if d]
    high, low = core.count(6), core.count(1)
    nonlow_partners = len(core) - low - 1
    forced_high_low = high * max(0, 12 - nonlow_partners)
    low_stubs = 2 * low
    cap = (low_stubs - forced_high_low) // 2
    pair_stubs = 5 * low
    require(
        (high, low, nonlow_partners, forced_high_low, low_stubs, cap, pair_stubs)
        == (4, 3, 11, 4, 6, 1, 15),
        "shadow incidence restriction differs",
    )
    return {
        "HIGH_LOW_SHADOW_INCIDENCES_MIN": forced_high_low,
        "LOW_SHADOW_INCIDENCES": low_stubs,
        "LOW_SHADOW_EDGE_CAP": cap,
        "LOW_PAIR_INCIDENCES": pair_stubs,
    }


def graph_edges(n: int, mask: int) -> tuple[Pair, ...]:
    require(type(mask) is int and 0 <= mask < 1 << comb(n, 2), "graph mask outside domain")
    return tuple(edge for bit, edge in enumerate(combinations(range(n), 2)) if mask >> bit & 1)


def triangles(n: int, edges: Sequence[Pair]) -> int:
    present = set(edges)
    return sum(
        all(edge in present for edge in combinations(t, 2)) for t in combinations(range(n), 3)
    )


@dataclass(frozen=True)
class ZeroGraph:
    mask: int
    edges: tuple[Pair, ...]
    a: tuple[int, ...]
    zeta: tuple[int, ...]
    floor: int


def zero_graphs() -> tuple[ZeroGraph, ...]:
    out: list[ZeroGraph] = []
    for mask in range(1 << comb(5, 2)):
        edges = graph_edges(5, mask)
        a = tuple(sum(v in edge for edge in edges) for v in range(5))
        zeta = tuple(2 + x for x in a)
        floor = triangles(5, edges) + sum(max(0, 15 - zeta[u] - zeta[v]) for u, v in edges)
        require(
            sum(a) == 2 * len(edges) and sum(zeta) == 10 + 2 * len(edges), "zero incidence identity"
        )
        out.append(ZeroGraph(mask, edges, a, zeta, floor))
    return tuple(out)


def low_masks(sigma: Sequence[int], shadow_cap: int = 1) -> tuple[int, ...]:
    require(type(shadow_cap) is int and shadow_cap in (1, 3), "wrong shadow relaxation")
    return tuple(
        mask for mask in range(8) if 2 * mask.bit_count() <= 15 + 2 * shadow_cap - sum(sigma[-3:])
    )


def core_floor(h: Sequence[int]) -> int:
    m = sum(h) // 2
    vertex_floors = [
        max(
            0,
            m
            - degree
            - sum(sorted((v for j, v in enumerate(h) if j != i), reverse=True)[: 14 - degree]),
        )
        for i, degree in enumerate(h)
    ]
    return max(max(vertex_floors), (sum(vertex_floors) + 2) // 3)


def core_and_mixed_floors(sigma: Sequence[int], mask: int) -> tuple[int, int]:
    d = profile(PROFILE_B)[:15]
    h = tuple(8 - v + s for v, s in zip(d, sigma, strict=True))
    edges = graph_edges(3, 7 ^ mask)  # J=H[L], mask denotes G[L].
    q = tuple(sum(v in edge for edge in edges) for v in range(3))
    low = triangles(3, edges) + sum(
        max(0, h[12 + i] + h[12 + j] - q[i] - q[j] - 12) for i, j in edges
    )
    correction = sum(max(0, sigma[12 + i] + sigma[12 + j] - 5) for i, j in edges)
    mixed = max(
        0, 5 * (sum(h) // 2) - sum(s * v for s, v in zip(sigma, h, strict=True)) + correction
    )
    require(low >= 0 and correction >= 0 and mixed >= 0, "negative correction/floor")
    return max(core_floor(h), low), mixed


def enumerate_b(shadow_cap: int = 1) -> dict[str, object]:
    configs = tuple(split.degree_configurations(profile(PROFILE_B)))
    classes = sorted({c.sigma for c in configs})
    zeros = zero_graphs()
    minima: dict[int, int] = {}
    witnesses: dict[str, object] = {}
    low_count, compatible_count = 0, 0
    for sigma in classes:
        masks = low_masks(sigma, shadow_cap)
        low_count += len(masks)
        e = (sum(sigma) - 10) // 2
        require(sum(sigma) == 10 + 2 * e and 0 <= e <= 7, "core-zero incidence identity")
        candidates = [
            z for z in zeros if len(z.edges) == e and split.bipartite_graphical(sigma, z.zeta)
        ]
        require(bool(candidates), "generic core class lacks a necessary zero graph")
        for mask in masks:
            core, mixed = core_and_mixed_floors(sigma, mask)
            for z in candidates:
                compatible_count += 1
                total = core + mixed + z.floor
                if e not in minima or total < minima[e]:
                    minima[e] = total
                    witnesses[str(e)] = {
                        "SIGMA": list(sigma),
                        "G_LOW_MASK": mask,
                        "H_ZERO_MASK": z.mask,
                        "CORE_FLOOR": core,
                        "CORE_CORE_ZERO_FLOOR": mixed,
                        "ZERO_AND_CORE_ZERO_ZERO_FLOOR": z.floor,
                    }
    require(set(minima) == set(range(8)), "incomplete zero-edge domain")
    return {
        "CORE_CLASSES": len(classes),
        "LOW_DEGREE_STATES": low_count,
        "ZERO_GRAPHS": len(zeros),
        "GENERIC_CONFIGURATIONS": len(configs),
        "COMPATIBLE_CASES": compatible_count,
        "MINIMA_BY_ZERO_EDGES": [minima[e] for e in range(8)],
        "RELAXATION_MINIMIZERS_NOT_PORTFOLIOS": witnesses,
    }


def theorem_b() -> dict[str, object]:
    facts, restriction = premises(PROFILE_B), shadow_restriction()
    proved, removed = enumerate_b(), enumerate_b(3)
    require(
        (proved["CORE_CLASSES"], proved["LOW_DEGREE_STATES"], proved["ZERO_GRAPHS"])
        == (339, 2565, 1024),
        "B reduced domain counts differ",
    )
    floors = [integer(v) for v in items(proved["MINIMA_BY_ZERO_EDGES"])]
    lower = integer(facts["GOODMAN"]) - CAPS[PROFILE_B]
    require(min(floors) >= lower, "computed domain does not establish the adopted B cap")
    weaker = [integer(v) for v in items(removed["MINIMA_BY_ZERO_EDGES"])]
    require(
        integer(removed["LOW_DEGREE_STATES"]) > integer(proved["LOW_DEGREE_STATES"])
        and min(weaker) < lower,
        "shadow restriction is not load-bearing",
    )
    return {
        **facts,
        **proved,
        "SHADOW_RESTRICTION": restriction,
        "PACKET_TABLE_COMPARISON_ONLY": {
            "EXPECTED": list(PACKET_FLOORS_COMPARISON_ONLY),
            "COMPUTED": floors,
            "DIFFERENCES": {
                str(e): {"PACKET": expected, "COMPUTED": actual}
                for e, (actual, expected) in enumerate(
                    zip(floors, PACKET_FLOORS_COMPARISON_ONLY, strict=True)
                )
                if actual != expected
            },
            "ORIGINAL_TABLE_REPRODUCED": False,
            "ORIGINAL_TABLE_SOURCE": "NOT_PROVIDED_NOT_VERIFIED",
            "OWNER_CONTINUATION": "DERIVE_FROM_MODEL_REPORT_DIFFERENCES_KEEP_T259",
        },
        "ENUMERATED_MINIMUM": min(floors),
        "SUPPLEMENTAL_T_CAP": integer(facts["GOODMAN"]) - min(floors),
        "ADOPTED_COMPLEMENT_FLOOR": lower,
        "TRIANGLE_CAP": 298 - lower,
        "STATUS": "PROVEN",
        "ATTAINABILITY": "NOT_ESTABLISHED",
        "FLOOR_SHARPNESS": "NOT_CLAIMED_COMPUTED_MINIMA_CAN_BE_STRONGER",
        "REMOVED_SHADOW_RESTRICTION": removed,
    }


def route_b(pid: str, cap: int, base: int = 112) -> list[Term]:
    d = profile(pid)
    require(
        type(cap) is int and 22 <= cap <= 264 and type(base) is int and base == 112,
        "wrong Route-B cap/base",
    )
    g = tuple(6 + x for x in d)
    w, c3 = sum(comb(x, 2) for x in g), sum(comb(x, 3) for x in g)
    amax = sum(x * (y - 2) for x, y in zip(d, g, strict=True)) // 3
    out: list[Term] = []
    for t in range(22, cap + 1):
        excess = c3 - (max(g) - 2) * (w - 3 * t)
        k4 = max(0, -((-excess) // 4))
        contained = min(k4, amax)
        s4 = max(base, 679 * k4 - 231 * contained)
        s3 = 2800 * w + 11872 * (t - 22) - 30800
        fraction = Fraction(372_228_640 - 63_838_600 + s3) - Fraction(4 * s4, 7)
        bound = -((-fraction.numerator) // fraction.denominator)
        out.append((t, bound, k4, contained, s4, s3))
    require(
        out
        == rational.exact_route_b_terms(d, cap, base)
        == official.route_b_envelope(d, cap, base),
        "official Route-B arithmetic differs",
    )
    return out


def validate_envelope(pid: str, cap: int, raw: object) -> int:
    require(cap == CAPS[pid], "certificate cap mismatch")
    terms = route_b(pid, cap)
    require(raw == [list(t) for t in terms], "Route-B term arithmetic/completeness mismatch")
    bound = max(t[1] for t in terms)
    require(bound == EXPECTED_BOUNDS[pid], "full-profile bound mismatch")
    return bound


def integrate(
    bounds: Mapping[str, int],
    updates: Mapping[str, int],
    cursor: Mapping[str, object],
    expected_cursor: Mapping[str, object],
) -> dict[str, int]:
    validate_rows(list(bounds.items()))
    validate_cursor(cursor, expected_cursor)
    require(set(updates) == set(TARGETS), "exactly two target updates required")
    for pid in TARGETS:
        require(
            type(updates[pid]) is int
            and updates[pid] == max(t[1] for t in route_b(pid, CAPS[pid])) < bounds[pid],
            "update bound arithmetic mismatch",
        )
    before = projection(bounds)
    after = {**bounds, **updates}
    require(
        sorted(p for p in bounds if after[p] != bounds[p]) == sorted(TARGETS), "wrong changed rows"
    )
    other_before = {p: b for p, b in bounds.items() if p not in TARGETS}
    other_after = {p: b for p, b in after.items() if p not in TARGETS}
    require(
        len(other_before) == 4645 and projection(other_before) == projection(other_after),
        "other 4645 bounds changed",
    )
    require(before == projection(bounds), "input ledger mutated")
    return after


def compute_result() -> dict[str, object]:
    pins = provenance()
    bounds, sealed = frozen_authority()
    cursor = obj(sealed["CURSOR"])
    proofs = {PROFILE_A: theorem_a(), PROFILE_B: theorem_b()}
    envelopes = {p: [list(t) for t in route_b(p, CAPS[p])] for p in TARGETS}
    updates = {p: validate_envelope(p, CAPS[p], envelopes[p]) for p in TARGETS}
    for p in TARGETS:
        require(max(t[1] for t in route_b(p, 264)) == bounds[p], "original envelope differs")
    after = integrate(bounds, updates, cursor, cursor)
    before, old_owners = prior.family(bounds, cursor)
    best, owners = prior.family(after, cursor)
    independently_sorted = sorted(
        [(b, p) for p, b in after.items()] + [(integer(cursor["BOUND"]), string(cursor["ID"]))],
        reverse=True,
    )
    require(
        (best, owners)
        == (independently_sorted[0][0], sorted(p for b, p in independently_sorted if b == best)),
        "independent family computation differs",
    )
    # Expected family values only checked AFTER the complete independent maximum.
    comparisons = {
        "FAMILY_BOUND": best == 313_397_860,
        "OWNER_SET": owners == ["66665555554421100000"],
        "DELTA": before - best == 284,
        "GAP": best - INCUMBENT == 133_972,
    }
    open_count = sum(b > INCUMBENT for b in after.values())
    other = {p: b for p, b in bounds.items() if p not in TARGETS}
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "TWO_OWNER_AUTHORITY_PENDING_FRESH_JUDGE",
        "OWNER_CONVERSATION_ID": "01a12f03-2549-7ed2-87e2-234ce1d42897",
        "WRITE_OWNERSHIP": "SOLE_WRITER_AFTER_OWNER_AUTHORIZED_3_3_HANDOFF",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "PROOF": __doc__,
        "PROVENANCE": pins,
        "FROZEN_RESULT": FROZEN,
        "FROZEN_RESULT_SHA256": FROZEN_SHA,
        "HISTORICAL_CURRENT_CAP_ROWS": S4_ROWS,
        "HISTORICAL_CURRENT_CAP_ROWS_SHA256": S4_ROWS_SHA,
        "CURRENT_T_CAP_AUTHORITY": "SEALED_SYMBOLIC_NB_ROW_LOCATORS_NO_NEW_NB_PROOF",
        "SOURCE_LEDGER_ROWS": len(bounds),
        "ROWS_UPDATED": len(updates),
        "ROW_UPDATES": {
            p: {
                "BEFORE_BOUND": bounds[p],
                "AFTER_BOUND": after[p],
                "T_CAP": CAPS[p],
                "S4_BASE": 112,
                "STRICT_GAIN_EXCLUDED": after[p] <= INCUMBENT,
            }
            for p in TARGETS
        },
        "THEOREMS": proofs,
        "ROUTE_B_ENVELOPES": envelopes,
        "ROUTE_B_TERMS_CHECKED": {p: len(envelopes[p]) for p in TARGETS},
        "OTHER_ROWS_UNCHANGED": "PASS",
        "OTHER_4645_BOUNDS_SHA256": sha(projection(other)),
        "BOUNDS_SHA256_BEFORE": sha(projection(bounds)),
        "BOUNDS_SHA256_AFTER": sha(projection(after)),
        "RESOLVED_ROW_BOUNDS": dict(sorted(after.items())),
        "CURSOR": cursor,
        "CURSOR_PRESERVED": "PASS",
        "CURSOR_SHA256": sha(render(cursor)),
        "CURSOR_SHA256_BEFORE": sha(render(cursor)),
        "CURSOR_SHA256_AFTER": sha(render(cursor)),
        "FAMILY_BOUND_BEFORE": before,
        "FAMILY_OWNER_IDS_BEFORE": old_owners,
        "FAMILY_BOUND_AFTER": best,
        "EXACT_DELTA": before - best,
        "NEW_OWNER_IDS": owners,
        "INCUMBENT": INCUMBENT,
        "GAP_TO_INCUMBENT": best - INCUMBENT,
        "EXPECTED_VALUES_COMPARISON_ONLY": comparisons,
        "RESOLVED_OPEN_PROFILE_COUNT": open_count,
        "STILL_OPEN_PROFILE_COUNT": open_count + integer(cursor["PROFILE_COUNT"]),
        "UNRESOLVED_CURSOR_PROFILE_COUNT": cursor["PROFILE_COUNT"],
        "LEDGER_VIEW": "COMPLETE_BOUND_PROJECTION_ONLY_NO_NEW_FULL_METADATA_DIGEST",
        "FULL_METADATA_DIGEST_AFTER": sealed["FULL_METADATA_DIGEST_AFTER"],
        "INHERITED_CAVEATS_AND_STATUS_VERBATIM": sealed["INHERITED_CAVEATS_AND_STATUS_VERBATIM"],
        "INHERITED_DONOR_A_VERBATIM": sealed["DONOR_A"],
        "INHERITED_DONOR_BC_VERBATIM": sealed["DONOR_BC"],
        "INHERITED_PENDING_TASK_STATUS_VERBATIM": sealed["TASK_STATUS"],
        "INHERITED_CAVEAT_POLICY_VERBATIM": sealed["CAVEAT_POLICY"],
        "GLOBAL_K20_OPTIMUM": "UNKNOWN",
        "ATTAINABILITY": "NOT_ESTABLISHED",
        "PRIOR_THREE_ROW_CAP_PROOFS_REEXECUTED": 0,
        "SOLVER_CALLS": 0,
        "EXISTING_CERTIFICATES_MUTATED": "NO",
        "RUN1_MUTATED": "NO",
        "HEAVY_SOLVER_STARTED": "NO",
        "REMOTE_WRITE": "NO",
    }


def main() -> None:
    raw = render(compute_result())
    if RESULT_PATH.exists():
        require(RESULT_PATH.read_bytes() == raw, "sealed result differs")
    else:
        with RESULT_PATH.open("xb") as output:
            output.write(raw)
    print(json.dumps({"RESULT": str(RESULT_PATH), "SHA256": sha(raw)}))


if __name__ == "__main__":
    main()
