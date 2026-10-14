"""A universal T <= 255 certificate for exactly 66555555555431100000.

Model and scope. There are 20 tickets of six distinct labels, 22 labels with
support size three and 27 with support size two. Pair-linearity means that
two tickets share at most one label. The support graph G therefore has
3*22+27 = 93 edges and g_v = 6+d_v. The exact d histogram is
(6^2,5^9,4^1,3^1,1^2,0^5), with sum d=66. Independently,
sum g=186, sum g^2=1836, W=sum C(g,2)=825. On each mixed three-set,
sum_v g_v(19-g_v) counts two edge/nonedge incidences, whereas homogeneous
three-sets contribute zero. Thus, for the complement H,
T(G)+T(H)=C(20,3)-(19*186-1836)/2=291.

Partition. Z={d=0} has FIVE vertices; K={d>0} has FIFTEEN. Let
sigma_x=|N_G(x) intersect Z| and zeta_z=|N_G(z) intersect K|, and let
r=sum_K sigma=sum_Z zeta. A Z neighbour uses a pair label of x, so
0 <= sigma_x <= 6-d_x. The two d=6 vertices have sigma=0 and each of
the nine d=5 vertices has sigma in {0,1}. Write h for the number with
sigma=1. For L=(d=4,3,1,1), sigma lies respectively in
0..2, 0..3, 0..5, 0..5. Since deg_G(z)=6 and |Z|-1=4,
2 <= zeta_z <= 6 and G[Z] has degrees 6-zeta_z.

Exact split and remainder. Put M=H[K], N=H[Z]. Their degrees are
m_x=8-d_x+sigma_x and n_z=zeta_z-2. Their degree sums give
2e(M)=54+r and 2e(N)=r-10, hence 5e(M)+15e(N)=60+10r.
For an M edge xy, the number of H triangles with its third vertex in Z
is 5-sigma_x-sigma_y+c_Z(xy), where
c_Z(xy)=|N_G(x) intersect N_G(y) intersect Z|. For an N edge uv,
the analogous count with its third vertex in K is
15-zeta_u-zeta_v+c_K(uv). Thus exactly
  T(H)=60+10r-sum_K sigma*m-sum_Z zeta*n+P,
  P=T(M)+T(N)+sum_{xy in E(M)} c_Z(xy)+sum_{uv in E(N)} c_K(uv).
Every summand is the cardinality of an explicitly defined finite set;
all four parts of P are nonnegative integers, regardless of overlaps
between those sets. The split classifies triangles by their number of
vertices in Z, so it is an identity, not an estimate. Consequently
  T(G)=231-10r+sum_K sigma(8-d+sigma)+sum_Z zeta(zeta-2)-P.
Dropping P increases the right side. The two d=6 vertices contribute
zero and the h active d=5 vertices contribute 4h. Therefore
  T(G) <= U=231-10r+s4(s4+4)+s3(s3+5)
                 +s1(s1+7)+s1'(s1'+7)+4h+sum_Z zeta(zeta-2).

Finite necessary-condition relaxation. Enumerate the 1024 simple graphs
on the FIVE Z vertices and retain their sorted zeta multisets, with a
witness mask and exact multiplicity for each. Enumerate all 4320 ordered
(s4,s3,s1,s1',h) vectors in the stated ranges. Combine a vector with each
graphical zeta multiset only when sum sigma+h=sum zeta. Every legal
realization maps to one of these states; sorting Z is sound because U
is symmetric in Z. We impose no cross-incidence compatibility, no
graphicality of M, no triple decomposition constraints, and no positive
lower bound on P. Omitting those necessary conditions enlarges the state
set, which can only increase its maximum. No state is asserted realizable.
There is no pruning. Exact integer evaluation gives max U=255. Its six
argmax states all have sigma=(2,3,5,5), with (h,zeta) equal to
(1,(2,2,4,4,4)), (1,(2,3,3,3,5)), (3,(3,3,3,3,6)),
(7,(2,5,5,5,5)), (9,(3,5,5,5,6)), and (9,(4,4,4,6,6)).
This is sufficient to improve the old cap 266;
no stronger relaxation or full support-graph search is needed here.

Authority and envelope. The old cap is the minimum of this exact profile's
pinned R30 accepted INFEASIBLE refutation at 267 (cap 266), NB cap 267,
and class cap 273. The mathematical Base's own S4 floor is queried for
this row (112). At each integer T, S4 is MAX(inherited,Route-B), never a
sum. The fixed Base has no adopted S5 certificate for this target; S5
stays unused. Recompute every T in 22..266 and 22..255, every K4/S3/S4
term and all argmax, with exact rational final ceiling. No maximum is
assumed to occur at a cap and no T in the interval is claimed feasible.

The direct R1 and its R2 input are re-executed without changes and must
reproduce their pinned result bytes. First reproduce family 313394776
and its sole owner. Then scan all 4647 resolved rows and all 197 cursor
rows; change only this resolved row. The unchanged cursor maximum
313394584 is a projection floor. Improving this row cannot close the
130888 incumbent gap: even that floor leaves a gap of 130696. This is
a conditional projection preserving all inherited authority/caveats,
not canonical adoption, a global optimum, or a prediction-gain claim.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, fields
from fractions import Fraction
from functools import cache
from itertools import combinations, product
from math import comb
from typing import cast

from . import b649_next_two_max_profiles_exact_bound_r1 as r1
from .b649_three_max_profiles_shared_certificate_r2 import Assumptions

route, nb, r2 = r1.route, r1.nb, r1.r2
require, obj, integer, sha = r1.require, r1.obj, r1.integer, r1.sha
render, git, identity, blob, decode = r1.render, r1.git, r1.identity, r1.blob, r1.decode
ROOT, DIRECTORY, MODEL = r1.ROOT, r1.DIRECTORY, r1.MODEL
TASK_ID = "B649_NEXT_SINGLE_MAX_OWNER_BOUND_R1"
TARGET = "66555555555431100000"
INPUT_HEAD = "e744534a3475d77aa192bf67733ade00b11c2ea3"
INPUT_TREE = "e6f053dc966194a1a89474fc4591bd74cb6e00fd"
R2_HEAD = "ef69e3fb4a2fdb171c4bc6944a3672706506beac"
R2_TREE = "bb8615cfe4af6d78bf55756b37a3f8530b05a304"
MAIN_HEAD = "61bad6d9ed4bdb6977d076d6b7fa28ac7b05f82a"
MAIN_TREE = "78f4a11e774c3c6fe3a13d0f1ab10f7e7d8c7ed0"
BASE_HEAD = "8d08e843b30300e8379f63e7dc9db401581e2e5e"
BASE_TREE = "231494ec0995981d2324cc5ef697ba4b1975b2f0"
INPUT_RESULT = f"{DIRECTORY}/b649-next-two-max-profiles-exact-bound-r1-result.json"
INPUT_PINS = {
    r1.SOURCE: "9ca78ac773221a7747f62015c1b7db9d0726cc9949635f72a42076ded71f694d",
    r1.TEST: "411660997fd166d27bfa8a1b0f52d94c6fdba98cecdd7b6f35e7efced1d9279f",
    INPUT_RESULT: "f538210b9719aa09639c3faf81c378f12658a2a2be865bbc5acdbe088fb74f44",
}
SOURCE = "src/lottolab/research/b649_next_single_max_owner_bound_r1.py"
TEST = "tests/unit/test_b649_next_single_max_owner_bound_r1.py"
RESULT = ROOT / DIRECTORY / "b649-next-single-max-owner-bound-r1-result.json"
type Term = tuple[int, int, int, int, int, int]


@dataclass(frozen=True)
class Claim:
    wedges: int = 825
    goodman: int = 291
    core: int = 15
    zeros: int = 5
    split_constant: int = 231
    zeta_floor: int = 2


CLAIM = Claim()


def theorem(
    pid: str = TARGET, claim: Claim = CLAIM, assumptions: Assumptions = MODEL
) -> dict[str, object]:
    require(pid == TARGET, "wrong exact profile")
    require(
        assumptions == MODEL
        and assumptions.pair_linearity is True
        and all(
            type(v) is int
            for v in (
                assumptions.tickets,
                assumptions.labels_per_ticket,
                assumptions.labels,
                assumptions.triples,
                assumptions.pairs,
                *assumptions.support_sizes,
            )
        ),
        "wrong support assumptions",
    )
    require(all(type(getattr(claim, f.name)) is int for f in fields(claim)), "noninteger claim")
    d = tuple(map(int, pid))
    g = tuple(6 + v for v in d)
    histogram = {6: 2, 5: 9, 4: 1, 3: 1, 1: 2, 0: 5}
    edges = assumptions.triples * comb(3, 2) + assumptions.pairs
    w = sum(comb(v, 2) for v in g)
    goodman = Fraction(comb(20, 3)) - Fraction(sum(v * (19 - v) for v in g), 2)
    require(
        len(d) == 20
        and dict(Counter(d)) == histogram
        and sum(d) == 66
        and edges == 93
        and sum(g) == 186
        and sum(v * v for v in g) == 2 * w + 186,
        "profile degree/edge/distribution mismatch",
    )
    require(w == claim.wedges, "wedge sum mismatch")
    require(goodman == claim.goodman, "Goodman identity mismatch")
    k, z = len(d) - d.count(0), d.count(0)
    require((k, z) == (claim.core, claim.zeros), "K/Z partition mismatch")
    twice_constant = z * (k * (k - 7) - sum(d)) + k * z * (z - 7)
    require(twice_constant == 120, "split degree-sum constant mismatch")
    constant = goodman - Fraction(twice_constant, 2)
    require(constant == claim.split_constant, "split constant mismatch")
    require(max(0, 7 - z) == claim.zeta_floor, "zeta floor mismatch")
    return {
        "PROFILE_ID": pid,
        "D": list(d),
        "G": list(g),
        "HISTOGRAM": {str(v): n for v, n in histogram.items()},
        "VERTICES": len(d),
        "SUPPORT_EDGES": edges,
        "DEGREE_SUM_D": sum(d),
        "DEGREE_SUM_G": sum(g),
        "SUM_G_SQUARED": sum(v * v for v in g),
        "WEDGES": w,
        "GOODMAN_SUM": int(goodman),
        "K": k,
        "Z": z,
        "SPLIT_CONSTANT": int(constant),
        "ZETA_RANGE": [claim.zeta_floor, 6],
        "LOW_ORDER_D": [4, 3, 1, 1],
        "SIGMA_CAPS": [2, 3, 5, 5],
        "H5_COUNT": d.count(5),
        "H6_COUNT": d.count(6),
        "M_DEGREE": "8-d+sigma",
        "N_DEGREE": "zeta-2",
        "REMAINDER": "T(M)+T(N)+sum_E(M)c_Z+sum_E(N)c_K",
        "REMAINDER_NONNEGATIVE": "EACH_TERM_COUNTS_A_FINITE_SET",
        "ASSUMPTIONS": asdict(assumptions),
        "ATTAINABILITY": "NOT_ASSERTED",
    }


@cache
def zero_shapes() -> tuple[tuple[tuple[int, ...], tuple[int, ...]], ...]:
    """All sorted graphical zeta multisets and all their labelled witness masks."""
    pairs = tuple(combinations(range(5), 2))
    groups: dict[tuple[int, ...], list[int]] = {}
    for mask in range(1 << len(pairs)):
        degrees = [0] * 5
        for i, (u, v) in enumerate(pairs):
            if mask >> i & 1:
                degrees[u] += 1
                degrees[v] += 1
        zeta = tuple(sorted(6 - q for q in degrees))
        groups.setdefault(zeta, []).append(mask)
    require(sum(len(masks) for masks in groups.values()) == 1024, "auxiliary graph census")
    return tuple((z, tuple(groups[z])) for z in sorted(groups))


def state_upper(sigma: Sequence[int], h: int, zeta: Sequence[int]) -> int:
    require(
        len(sigma) == 4
        and type(h) is int
        and 0 <= h <= 9
        and all(type(s) is int and 0 <= s <= c for s, c in zip(sigma, (2, 3, 5, 5), strict=True))
        and len(zeta) == 5
        and all(type(z) is int and 2 <= z <= 6 for z in zeta),
        "wrong relaxation state ranges",
    )
    r = sum(sigma) + h
    require(r == sum(zeta), "cross-edge degree sum mismatch")
    return (
        231
        - 10 * r
        + sum(s * (s + 8 - d) for s, d in zip(sigma, (4, 3, 1, 1), strict=True))
        + 4 * h
        + sum(z * (z - 2) for z in zeta)
    )


@cache
def relaxation() -> dict[str, object]:
    theorem()
    best: int | None = None
    argmax: list[dict[str, object]] = []
    vectors = states = labelled = 0
    shapes = zero_shapes()
    for sigma in product(range(3), range(4), range(6), range(6)):
        for h in range(10):
            vectors += 1
            for zeta, masks in shapes:
                if sum(sigma) + h != sum(zeta):
                    continue
                states += 1
                labelled += len(masks)
                value = state_upper(sigma, h, zeta)
                if best is None or value > best:
                    best, argmax = value, []
                if value == best:
                    argmax.append(
                        {
                            "SIGMA_LOW": list(sigma),
                            "H5_ACTIVE": h,
                            "ZETA": list(zeta),
                            "R": sum(zeta),
                            "VALUE": value,
                            "AUXILIARY_GRAPH_MASKS": list(masks),
                        }
                    )
    require(vectors == 4320 and best is not None, "empty/incomplete relaxation")
    return {
        "CAP": best,
        "ALL_ARGMAX_STATES": argmax,
        "SIGMA_H_VECTORS": vectors,
        "AUXILIARY_Z_GRAPHS": 1024,
        "DISTINCT_GRAPHICAL_ZETA_MULTISETS": len(shapes),
        "RELAXATION_STATES": states,
        "LABELLED_RELAXATION_STATES": labelled,
        "ALL_GRAPHICAL_ZETA_MULTISETS": [
            {"ZETA": list(z), "GRAPH_MASKS": list(masks)} for z, masks in shapes
        ],
        "AUXILIARY_GRAPH_MASK_PAIR_ORDER": list(combinations(range(5), 2)),
        "PRUNING": "NONE",
        "DROPPED_REMAINDER_LOWER_BOUND": 0,
        "COMPLETENESS": "EXACT_FINITE_NECESSARY_CONDITION_RELAXATION_ONLY",
        "REALIZABLE_STATES": "NOT_ASSERTED",
        "FULL_SUPPORT_GRAPHS_ENUMERATED": 0,
    }


def validate_envelope(pid: str, cap: int, floor: int, terms: Sequence[Term]) -> None:
    require(pid == TARGET and type(cap) is int and 22 <= cap <= 275, "wrong profile/cap")
    require(type(floor) is int and floor >= 0, "wrong S4 floor")
    require([t[0] for t in terms] == list(range(22, cap + 1)), "incomplete T envelope")
    d = tuple(map(int, pid))
    g = tuple(6 + v for v in d)
    w, choose3, top = sum(comb(v, 2) for v in g), sum(comb(v, 3) for v in g), max(g)
    a_max = sum(v * (6 + v - 2) for v in d) // 3
    for t, bound, k4, contained, s4, s3 in terms:
        require(all(type(v) is int for v in (t, bound, k4, contained, s4, s3)), "noninteger term")
        opened = w - 3 * t
        expected_k4 = max(0, -(-(choose3 - (top - 2) * opened) // 4))
        require(k4 == expected_k4 and contained == min(k4, a_max), "K4 rounding/containment")
        require(s4 == max(floor, 679 * k4 - 231 * contained), "S4 direction/floor")
        expected_s3 = 2800 * opened + 20272 * (t - 22) + 7000 * 22
        exact = Fraction(route.K20_S1 - route.K20_S2 + expected_s3) - Fraction(4 * s4, 7)
        require(
            s3 == expected_s3 and bound == -(-exact.numerator // exact.denominator),
            "S3 or final ceiling rounding",
        )


def envelope(cap: int, floor: int) -> list[Term]:
    terms = route.route_b_envelope(tuple(map(int, TARGET)), cap, floor)
    validate_envelope(TARGET, cap, floor, terms)
    return terms


def fixed_input() -> dict[str, object]:
    for head, tree in (
        (INPUT_HEAD, INPUT_TREE),
        (R2_HEAD, R2_TREE),
        (MAIN_HEAD, MAIN_TREE),
        (BASE_HEAD, BASE_TREE),
    ):
        identity(head, tree)
    require(git("rev-parse", f"{INPUT_HEAD}^").decode().strip() == R2_HEAD, "R1 parent drift")
    for path, digest in INPUT_PINS.items():
        require((ROOT / path).read_bytes() == blob(INPUT_HEAD, path, digest), f"R1 changed: {path}")
    require((r1.CERTIFICATE_HEAD, r1.CERTIFICATE_TREE) == (R2_HEAD, R2_TREE), "R2 input pin drift")
    fixed = r1.compute_result()  # Includes full byte-for-byte R2 replay and Base closure check.
    require(render(fixed) == (ROOT / INPUT_RESULT).read_bytes(), "R1 result not reproduced")
    return fixed


def family(resolved: Mapping[str, int], cursor: Mapping[str, int]) -> dict[str, object]:
    require(len(resolved) == 4647 and len(cursor) == 197, "family row count mismatch")
    require(not (set(resolved) & set(cursor)), "overlapping resolved/cursor IDs")
    require(all(type(b) is int for b in (*resolved.values(), *cursor.values())), "noninteger bound")
    merged = dict(resolved) | dict(cursor)
    levels = sorted(set(merged.values()), reverse=True)
    maximum = levels[0]
    owners = sorted(p for p, b in merged.items() if b == maximum)
    return {
        "MAXIMUM": maximum,
        "ALL_MAX_OWNERS": owners,
        "NEXT_DISTINCT_BOUND": levels[1],
        "RESOLVED_MAXIMUM": max(resolved.values()),
        "CURSOR_MAXIMUM": max(cursor.values()),
        "RESOLVED_ROWS_SCANNED": len(resolved),
        "CURSOR_ROWS_SCANNED": len(cursor),
        "MAXIMUM_OWNER_CLASSES": sorted(
            {"RESOLVED" if p in resolved else "CURSOR" for p in owners}
        ),
    }


def compute_result() -> dict[str, object]:
    fixed = fixed_input()
    pins = r2.source_pins()
    sealed = decode(blob(BASE_HEAD, r2.BASE_RESULT, r2.BASE_SHA))
    before = {p: integer(b) for p, b in obj(fixed["RESOLVED_ROW_BOUNDS_AFTER"]).items()}
    r2.checked_rows(list(before.items()), before)
    require(sha(r2.projection(before)) == fixed["BOUNDS_SHA256_AFTER"], "R1 ledger digest")
    cursor = obj(fixed["CURSOR"])
    require(
        cursor == sealed["CURSOR"] and sha(render(cursor)) == sealed["CURSOR_SHA256"], "cursor pin"
    )
    coarse = {p: integer(b) for p, b in obj(cursor["COARSE_BOUND_PROJECTION"]).items()}
    require(
        len(coarse) == 197 and set(coarse) == set(cast(list[str], cursor["PROFILE_IDS"])),
        "cursor IDs",
    )
    for pid, bound in coarse.items():
        require(
            route.r28.coarse_profile_envelope(tuple(map(int, pid))).family_upper_bound == bound,
            "cursor bound differs from Base evaluator",
        )
    first = family(before, coarse)
    require(
        first["MAXIMUM"] == 313394776 and first["ALL_MAX_OWNERS"] == [TARGET], "baseline owner/max"
    )
    proof = theorem()
    adopted_s5 = set(obj(sealed["PROFILE_CERTIFICATES"])) | {
        r2.string(obj(sealed["INHERITED_TARGET_BONFERRONI_5"])["PROFILE_ID"])
    }
    adopted_caps = set(obj(sealed["CERTIFICATES_ADOPTED"]))
    require(TARGET not in adopted_s5 | adopted_caps, "target has adopted S5 authority")
    require(sealed["ALL_T_BONFERRONI_5_ADOPTION"] == "NOT_VERIFIED", "all-T S5 adoption drift")
    r30 = decode(blob(BASE_HEAD, r2.R30_PATH, r2.R30_SHA))
    references = [
        a
        for a in cast(list[dict[str, object]], r30["GROUP_ATTEMPTS"])
        if a.get("PROFILE_IDS") == [TARGET] and a.get("STATUS") == "INFEASIBLE"
    ]
    require(bool(references), "missing exact-profile cap authority")
    refutation = min(references, key=lambda a: integer(a["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"]))
    d = tuple(map(int, TARGET))
    accepted = integer(refutation["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"])
    require(
        route.r28.r26.accepted_cap(refutation, (d,), accepted) == accepted, "old cap not accepted"
    )
    nb_cap, class_cap = nb.profile_nb_cap(d)[2], nb.r18_cap(d)
    old_cap = min(accepted, nb_cap, class_cap)
    floor = route.r28.profile_s4_floor(d)
    old = envelope(old_cap, floor)
    relax = relaxation()
    new_cap = min(old_cap, integer(relax["CAP"]))
    new = envelope(new_cap, floor)
    old_bound, new_bound = max(t[1] for t in old), max(t[1] for t in new)
    require(before[TARGET] == old_bound, "old full envelope differs from input row")
    after = dict(before)
    after[TARGET] = new_bound
    require(
        {p: b for p, b in before.items() if p != TARGET}
        == {p: b for p, b in after.items() if p != TARGET},
        "other resolved rows changed",
    )
    last = family(after, coarse)
    incumbent = integer(sealed["INCUMBENT"])
    status = "PROVEN_IMPROVEMENT" if new_cap < old_cap else "NO_PROVEN_GAIN"
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": status,
        "INPUT_CERTIFICATE": {
            "HEAD": INPUT_HEAD,
            "TREE": INPUT_TREE,
            "FILE_SHA256": INPUT_PINS,
            "R1_AND_R2_REPRODUCED_BYTE_FOR_BYTE": True,
        },
        "PREVIOUS_R2_CERTIFICATE": {"HEAD": R2_HEAD, "TREE": R2_TREE, "FILE_SHA256": r1.R2_PINS},
        "PINNED_MAIN_BASE": {"HEAD": MAIN_HEAD, "TREE": MAIN_TREE},
        "MATHEMATICAL_BASE": {
            "HEAD": BASE_HEAD,
            "TREE": BASE_TREE,
            "RESULT_PATH": r2.BASE_RESULT,
            "RESULT_SHA256": r2.BASE_SHA,
        },
        "SOURCE_SHA256": sha((ROOT / SOURCE).read_bytes()),
        "TEST_SHA256": sha((ROOT / TEST).read_bytes()),
        "SOURCE_PINS": pins,
        "PROOF": __doc__,
        "PROFILE_FACTS": proof,
        "RELAXATION": relax,
        "OLD_T_CAP": old_cap,
        "NEW_PROVEN_T_CAP": new_cap,
        "OLD_CAP_AUTHORITY": {
            "BASE_HEAD": BASE_HEAD,
            "PATH": r2.R30_PATH,
            "SHA256": r2.R30_SHA,
            "REFUTATION": refutation,
            "NB_CAP": nb_cap,
            "CLASS_CAP": class_cap,
        },
        "S4_AUTHORITY": {
            "BASE_HEAD": BASE_HEAD,
            "EXACT_PROFILE": TARGET,
            "INHERITED_FLOOR": floor,
            "FUNCTION": "b649_k20_min_s2_current_cursor_class_owner_chase_r28.profile_s4_floor",
            "RULE": "MAX(INHERITED,ROUTE_B); NONNEGATIVE_LOWER_BOUND_SUBTRACTED",
        },
        "S5_AUTHORITY": {
            "ADOPTED_TARGETS_IN_BASE": sorted(adopted_s5),
            "ADOPTED_CAP_CERTIFICATES": sorted(adopted_caps),
            "ALL_T_ADOPTION": sealed["ALL_T_BONFERRONI_5_ADOPTION"],
            "VALUE": None,
            "USED": False,
            "STATUS": "NO_ADOPTED_TARGET_CERTIFICATE",
        },
        "TERM_COLUMNS": ["T", "BOUND", "K4_FLOOR", "CONTAINED_K4", "S4_FLOOR", "S3"],
        "ROUNDING": "K4_CEILING; A_MAX_FLOOR; FINAL_EXACT_RATIONAL_CEILING",
        "OLD_T_RANGE": [22, old_cap],
        "NEW_T_RANGE": [22, new_cap],
        "OLD_TERM_COUNT": len(old),
        "NEW_TERM_COUNT": len(new),
        "OLD_ALL_T_TERMS": old,
        "NEW_ALL_T_TERMS": new,
        "OLD_ALL_ARGMAX": [t for t in old if t[1] == old_bound],
        "NEW_ALL_ARGMAX": [t for t in new if t[1] == new_bound],
        "OLD_ROW_BOUND": old_bound,
        "NEW_ROW_BOUND": new_bound,
        "ROW_DELTA": old_bound - new_bound,
        "RESOLVED_ROW_BOUNDS_BEFORE": before,
        "RESOLVED_ROW_BOUNDS_AFTER": after,
        "RESOLVED_ROWS": len(after),
        "OTHER_RESOLVED_ROWS_UNCHANGED": 4646,
        "BOUNDS_SHA256_BEFORE": sha(r2.projection(before)),
        "BOUNDS_SHA256_AFTER": sha(r2.projection(after)),
        "PROJECTED_FAMILY_BEFORE": first,
        "PROJECTED_FAMILY_AFTER": last,
        "FAMILY_BEFORE": first["MAXIMUM"],
        "FAMILY_AFTER": last["MAXIMUM"],
        "FAMILY_DELTA": integer(first["MAXIMUM"]) - integer(last["MAXIMUM"]),
        "ALL_NEW_MAX_OWNERS": last["ALL_MAX_OWNERS"],
        "NEXT_DISTINCT_BOUND": last["NEXT_DISTINCT_BOUND"],
        "CURSOR": cursor,
        "CURSOR_COUNT": len(coarse),
        "CURSOR_MAXIMUM": max(coarse.values()),
        "CURSOR_SHA256_BEFORE": sha(render(cursor)),
        "CURSOR_SHA256_AFTER": sha(render(cursor)),
        "CURSOR_PRESERVED": "ALL_197_IDS_AND_BOUNDS_UNCHANGED_AND_REEVALUATED",
        "CURSOR_IS_HIGHEST_BOTTLENECK": max(coarse.values()) == last["MAXIMUM"],
        "FRONTIER_FLOOR": max(coarse.values()),
        "FRONTIER_FLOOR_GAP": max(coarse.values()) - incumbent,
        "INCUMBENT": incumbent,
        "OLD_GAP_TO_INCUMBENT": integer(first["MAXIMUM"]) - incumbent,
        "GAP_TO_INCUMBENT": integer(last["MAXIMUM"]) - incumbent,
        "PROJECTION_STATUS": "CONDITIONAL_PROJECTION; NOT_CANONICAL_ADOPTION",
        "INHERITED_PROVENANCE_VERBATIM": sealed["PROVENANCE"],
        "INHERITED_CAVEATS_AUTHORITY": {
            "HEAD": BASE_HEAD,
            "PATH": r2.BASE_RESULT,
            "RESULT_SHA256": r2.BASE_SHA,
            "FIELD": "INHERITED_CAVEATS_AND_STATUS_VERBATIM",
            "FIELD_RENDER_SHA256": sha(render(sealed["INHERITED_CAVEATS_AND_STATUS_VERBATIM"])),
            "DISPOSITION": "PRESERVED_VERBATIM_AT_FIXED_LOCATOR_WITHOUT_AUTHORITY_UPGRADE",
        },
        "FRESH_FOCUSED_REVIEW": (
            "REQUIRED_ON_FROZEN_CANDIDATE_TREE; VERDICT_IS_EXTERNAL_TO_THIS_BLOB"
        ),
        "GRAPH_ENUMERATION_COMPLETENESS": "NOT_RUN — NO_FULL_SUPPORT_GRAPH_ENUMERATION",
        "SOLVER_CALLS": 0,
        "FULL_SUPPORT_GRAPHS_ENUMERATED": 0,
        "PORTFOLIOS_ENUMERATED": 0,
        "GLOBAL_OPTIMUM": "UNKNOWN",
        "PREDICTION_GAIN_CLAIMED": False,
        "CANONICAL_AUTHORITY_CHANGED": "NO",
        "REMOTE_WRITE": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "REMAINING_TASK_MODEL": "最強模型(cursor 新通用證明); 強模型(已驗收結果接合)",
    }


def verify_result(stored: Mapping[str, object]) -> None:
    require(render(stored) == render(compute_result()), "stored result not exactly reproducible")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reproduce the one-profile universal cap certificate"
    )
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = compute_result()
    raw = render(result)
    if RESULT.exists():
        require(RESULT.read_bytes() == raw, "stored result differs")
    else:
        require(not args.verify, "missing result")
        with RESULT.open("xb") as out:
            out.write(raw)
    print(
        json.dumps(
            {
                "RESULT": str(RESULT),
                "SHA256": sha(raw),
                "CAP": result["NEW_PROVEN_T_CAP"],
                "ROW_BOUND": result["NEW_ROW_BOUND"],
                "FAMILY": result["PROJECTED_FAMILY_AFTER"],
                "GAP": result["GAP_TO_INCUMBENT"],
            }
        )
    )


if __name__ == "__main__":
    main()
