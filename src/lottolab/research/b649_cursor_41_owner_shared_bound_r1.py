"""A shared Route-B upper bound for the 41 tied maximum cursor profiles (R1).

Fixed input. Commit 317210d5 (tree 259e5a92) projects the family maximum
313394584. All 41 owners are cursor rows whose bound is the Base coarse
evaluator S1-S2+S3(W,floor(W/3))-floor(4*112/7) at W=785. The owner IDs are
read from that result and re-derived by its own family aggregation.

Cursor coverage. A cursor ID is an exact sorted triple-degree histogram d. It
is NOT a resolved profile: no triangle cap, refutation, witness, R18 class or
R30 status is known or read for it. Every legal portfolio of the model (20
tickets of six distinct labels, 22 triple and 27 pair supports, pair-linearity)
has exactly one histogram: a non-increasing 20-tuple over 0..6 with sum 66.
Enumerating all 5126 such tuples yields the 197 cursor IDs as exactly the
tuples with W=sum C(6+d,2) <= 785, and the 41 owners as exactly those with
W=785. So the 41 rows cover every legal portfolio with W=785, for every
support graph, triangle count t and K4 count. These are its legal
continuations, and the bound below holds for each of them.

Universal facts for one legal portfolio with histogram d and W=785. Its support
graph G has degrees g=6+d. A triangle closes three wedges, and distinct
triangles close distinct wedges, so 3t <= W. The 22 triple supports are 22
distinct triangles, so t >= 22. Hence 22 <= t <= 261, and exactly
o=W-3t >= 0 wedges are open; o_v of them have centre v. A nonadjacent pair in
N(v) lies in at most g_v-2 of the C(g_v,3) triples of N(v). So v lies in at
least C(g_v,3)-(g_v-2)o_v K4. Summing over v counts each K4 four times, giving
  K4 >= max(0, ceil((sum C(g,3)-(g_max-2)o)/4)).
A K4 holds at most one triple support, since two would share two tickets. A
triple support T lies in at most min_{v in T}(g_v-2) K4. So the number a of
K4 containing a triple is at most
  A_max = floor(sum d(g-2)/3) = floor((sum d^2+264)/3) = 169,
because sum d^2 = 2W-1326 = 244. Each such quartet adds exactly 448 to S4 and
every other K4 adds 679. All other S4 terms are nonnegative, so
  S4 >= 679 K4 - 231 min(K4, A_max).
The right side increases in K4 (slope 448 or 679), so the K4 floor may be
substituted. S4 >= 112 is the Base profile floor; it is not load-bearing, since
floor 0 gives identical maxima. The Base exact identity
S3 = 2800 o + 20272 (t-22) + 7000*22 and the Base S4 credit give, at the TRUE t,
  union <= B(d,t) = ceil(S1 - S2 + S3 - 4 max(112, S4_B(t)) / 7).
So the union is at most max_{t=22..261} B(d,t). This is the Base Route-B rule
with the universal wedge cap floor(W/3) in place of a certified cap. The coarse
bound is the same formula at t=261 with the floor 112 alone, so the only change
is a larger valid S4 lower bound. Every t is kept; no t is claimed feasible.

Shared class envelope. All 41 histograms share W=785 and A_max=169. Over them
sum C(g,3) >= 1979, and g <= 12 for every histogram. The K4 floor increases in
sum C(g,3) and decreases in g_max, so a single envelope with (1979, 12) is at or
above every member's envelope at every t. Its maximum, 313226836, is one bound
for every legal W=785 portfolio. The adopted row bounds are the exact
per-histogram envelopes of the Base evaluator, each at most 313226448.

Arithmetic. K4 uses an integer ceiling and A_max an integer floor; the final
bound is the exact-rational ceiling. Every term of all 41 envelopes (240 each)
is checked independently. Here 448, 679, 231*169 and 112 are multiples of 7, so
every certified S4 credit 4*S4/7 is an integer and no term relies on rounding.

Family. Only the 41 cursor bounds change. The other 156 cursor bounds remain
the Base coarse values, and all 4647 resolved bounds stay unchanged. The family
is recomputed over all 4844 rows. A positive delta is claimed only if all 41
rows drop strictly and the recomputed maximum drops. This is a conditional
projection, not canonical adoption, a global optimum, or a prediction-gain claim.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from fractions import Fraction
from functools import cache
from math import comb
from typing import cast

from . import b649_next_single_max_owner_bound_r1 as prev
from .b649_three_max_profiles_shared_certificate_r2 import Assumptions

r1, r2, route = prev.r1, prev.r2, prev.route
require, obj, integer, sha = prev.require, prev.obj, prev.integer, prev.sha
render, git, identity, blob, decode = prev.render, prev.git, prev.identity, prev.blob, prev.decode
ROOT, DIRECTORY, MODEL = prev.ROOT, prev.DIRECTORY, prev.MODEL
TASK_ID = "B649_CURSOR_41_OWNER_SHARED_BOUND_R1"
INPUT_HEAD = "317210d56cac9efcb779e0967049302c74d7be77"
INPUT_TREE = "259e5a92b42a508e2fcc8e262996963c1bef6670"
TWO_OWNER_HEAD, TWO_OWNER_TREE = prev.INPUT_HEAD, prev.INPUT_TREE
R2_HEAD, R2_TREE = prev.R2_HEAD, prev.R2_TREE
MAIN_HEAD, MAIN_TREE = prev.MAIN_HEAD, prev.MAIN_TREE
BASE_HEAD, BASE_TREE = prev.BASE_HEAD, prev.BASE_TREE
INPUT_RESULT = f"{DIRECTORY}/b649-next-single-max-owner-bound-r1-result.json"
INPUT_PINS = {
    prev.SOURCE: "fad7255ac5e1a45b729696fd42ea419af15f44882469508f14aa223a53d68687",
    prev.TEST: "0b32c86c8e5c43ef85a4d6d38603943a7ac0c4b2ebe4ba0f7b8ea6555f768bd9",
    INPUT_RESULT: "0b12e9e962574082081ccfd5676db0e5a200bcf49bee3c94174fc9dbad476018",
}
SOURCE = "src/lottolab/research/b649_cursor_41_owner_shared_bound_r1.py"
TEST = "tests/unit/test_b649_cursor_41_owner_shared_bound_r1.py"
RESULT = ROOT / DIRECTORY / "b649-cursor-41-owner-shared-bound-r1-result.json"
EXPECTED_FAMILY = 313394584
EXPECTED_NEXT = 313392516
OWNER_COUNT, CURSOR_COUNT, RESOLVED_COUNT = 41, 197, 4647
OWNER_IDS_SHA256 = "392121227ff8abb5bedc2ce95624fcccf216d2f64e66d7e0dfb5c24a9691bf77"
FRONTIER_IDS_SHA256 = "1fd8ef4779e3967b75cbeaa2ca65de9afc2551d27ae7e98daa1e3f700fc24e8b"
RAW_HISTOGRAMS = 5126
OWNER_W, MIN_W = 785, 774
G_CEILING = 12  # g = 6 + d with d <= 6, for every histogram.
type Term = tuple[int, int, int, int, int, int]
type Profile = tuple[int, ...]


def wedges(d: Sequence[int]) -> int:
    return sum(comb(6 + v, 2) for v in d)


def ids_digest(ids: Sequence[str]) -> str:
    # The Base coverage-repair convention: JSON list in descending profile order.
    return sha(json.dumps(sorted(ids, reverse=True)).encode())


@cache
def raw_histograms() -> tuple[Profile, ...]:
    """Every non-increasing 20-tuple over 0..6 with sum 66; no screen applied."""
    found: list[Profile] = []

    def visit(prefix: list[int], top: int, remaining: int) -> None:
        slots = 20 - len(prefix)
        if slots == 0:
            if remaining == 0:
                found.append(tuple(prefix))
            return
        if remaining <= slots * top:
            for v in range(min(top, remaining), -1, -1):
                visit([*prefix, v], v, remaining - v)

    visit([], 6, 66)
    require(len(found) == len(set(found)) == RAW_HISTOGRAMS, "raw histogram census")
    return tuple(found)


def coverage(
    cursor_ids: Sequence[str], owners: Sequence[str], resolved: Sequence[str]
) -> dict[str, object]:
    """The cursor IDs are exactly the W<=785 histograms; the owners exactly the W=785 ones."""
    raw = {"".join(map(str, p)): wedges(p) for p in raw_histograms()}
    require(len(cursor_ids) == len(set(cursor_ids)) == CURSOR_COUNT, "cursor ID count/duplicate")
    require(len(owners) == len(set(owners)) == OWNER_COUNT, "owner ID count/duplicate")
    frontier = {p for p, w in raw.items() if w <= OWNER_W}
    top = {p for p, w in raw.items() if w == OWNER_W}
    require(set(cursor_ids) == frontier, "cursor IDs are not exactly the W<=785 histograms")
    require(set(owners) == top, "owners are not exactly the W=785 histograms")
    require(ids_digest(cursor_ids) == FRONTIER_IDS_SHA256, "frontier partition digest")
    require(min(raw.values()) == MIN_W, "minimum wedge count")
    require(all(raw[p] > OWNER_W for p in resolved), "resolved row inside the cursor band")
    return {
        "MEANING": "EACH_ID_IS_ONE_EXACT_SORTED_TRIPLE_DEGREE_HISTOGRAM_NOT_A_RESOLVED_PROFILE",
        "CONTINUATIONS": "EVERY_LEGAL_PORTFOLIO_OF_THE_HISTOGRAM; ALL_GRAPHS; ALL_T_22_TO_W_DIV_3",
        "RAW_HISTOGRAMS": len(raw),
        "CURSOR_IDS_EQUAL_ALL_RAW_W_LE_785": True,
        "OWNER_IDS_EQUAL_ALL_RAW_W_EQ_785": True,
        "FRONTIER_IDS_SHA256": FRONTIER_IDS_SHA256,
        "OWNER_IDS_SHA256": ids_digest(owners),
        "CURSOR_W_HISTOGRAM": {
            str(w): n for w, n in sorted(Counter(raw[p] for p in cursor_ids).items())
        },
        "RESOLVED_MIN_W": min(raw[p] for p in resolved),
        "SCREENS_USED": "NONE; THE BAND CONTAINS EVERY RAW HISTOGRAM",
        "R18_R30_CAPS_OR_STATUSES_USED": 0,
    }


@cache
def owner_ids() -> frozenset[str]:
    """The 41 owners as pinned in the fixed input result JSON."""
    fixed = decode(blob(INPUT_HEAD, INPUT_RESULT, INPUT_PINS[INPUT_RESULT]))
    owners = cast(list[str], fixed["ALL_NEW_MAX_OWNERS"])
    require(ids_digest(owners) == OWNER_IDS_SHA256 and len(owners) == OWNER_COUNT, "owner pin")
    return frozenset(owners)


def theorem(pid: str, assumptions: Assumptions = MODEL) -> dict[str, object]:
    require(pid in owner_ids(), "not one of the 41 tied cursor owners")
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
    d = tuple(map(int, pid))
    g = tuple(6 + v for v in d)
    w = wedges(d)
    edges = assumptions.triples * 3 + assumptions.pairs
    require(
        len(d) == assumptions.tickets == 20
        and list(d) == sorted(d, reverse=True)
        and all(0 <= v <= assumptions.labels_per_ticket for v in d)
        and sum(d) == 3 * assumptions.triples == 66
        and sum(g) == 2 * edges == 186
        and w == OWNER_W
        and sum(v * v for v in d) == 2 * w - 1326 == 244,
        "histogram/wedge facts",
    )
    a_total = sum(v * (6 + v - 2) for v in d)
    a_max = a_total // 3
    require(
        a_total == 244 + 4 * 66 and a_max == 169 and 3 * a_max <= a_total < 3 * a_max + 3, "A_max"
    )
    return {
        "PROFILE_ID": pid,
        "WEDGES": w,
        "T_RANGE": [assumptions.triples, w // 3],
        "OPEN_WEDGES_AT_TOP_T": w - 3 * (w // 3),
        "SUM_D_SQUARED": 244,
        "SUM_C_G_3": sum(comb(v, 3) for v in g),
        "G_MAX": max(g),
        "A_MAX": a_max,
        "ASSUMPTIONS": asdict(assumptions),
    }


def validate_envelope(pid: str, cap: int, floor: int, terms: Sequence[Term]) -> None:
    require(pid in owner_ids() and type(cap) is int, "wrong cursor owner/cap")
    d = tuple(map(int, pid))
    w = wedges(d)
    require(cap == w // 3, "cap is not the universal wedge cap floor(W/3)")
    require(type(floor) is int and floor >= 0, "wrong S4 floor")
    require([t[0] for t in terms] == list(range(22, cap + 1)), "incomplete T envelope")
    g = tuple(6 + v for v in d)
    choose3, top = sum(comb(v, 3) for v in g), max(g)
    a_max = sum(v * (v + 4) for v in d) // 3
    for t, bound, k4, contained, s4, s3 in terms:
        require(all(type(v) is int for v in (t, bound, k4, contained, s4, s3)), "noninteger term")
        opened = w - 3 * t
        require(k4 == max(0, -(-(choose3 - (top - 2) * opened) // 4)), "K4 rounding")
        require(contained == min(k4, a_max), "A_max containment")
        require(s4 == max(floor, 679 * k4 - 231 * contained), "S4 direction/floor")
        exact_s3 = 2800 * opened + 20272 * (t - 22) + 7000 * 22
        exact = Fraction(route.K20_S1 - route.K20_S2 + exact_s3) - Fraction(4 * s4, 7)
        require(s3 == exact_s3, "S3 identity")
        require(bound == -(-exact.numerator // exact.denominator), "final ceiling rounding")


def envelope(pid: str, floor: int) -> list[Term]:
    d = tuple(map(int, pid))
    cap = wedges(d) // 3
    terms = route.route_b_envelope(d, cap, floor)
    validate_envelope(pid, cap, floor, terms)
    return terms


def class_envelope(members: Sequence[str], choose3_floor: int, top: int) -> list[Term]:
    """One envelope over the class, valid when its premises hold for every member."""
    require(frozenset(members) == owner_ids(), "class must be exactly the 41 owners")
    for pid in members:
        d = [int(v) for v in pid]
        g = [6 + v for v in d]
        require(wedges(d) == OWNER_W, "class member wedge count")
        require(sum(v * (v + 4) for v in d) // 3 == 169, "class A_max")
        require(sum(comb(v, 3) for v in g) >= choose3_floor, "class C3 floor exceeds a member")
        require(max(g) <= top <= G_CEILING, "class g_max below a member")
    terms: list[Term] = []
    for t in range(22, OWNER_W // 3 + 1):
        opened = OWNER_W - 3 * t
        k4 = max(0, -(-(choose3_floor - (top - 2) * opened) // 4))
        contained = min(k4, 169)
        s4 = max(112, 679 * k4 - 231 * contained)
        s3 = 2800 * opened + 20272 * (t - 22) + 7000 * 22
        exact = Fraction(route.K20_S1 - route.K20_S2 + s3) - Fraction(4 * s4, 7)
        terms.append((t, -(-exact.numerator // exact.denominator), k4, contained, s4, s3))
    return terms


def dominated(shared: Sequence[Term], terms: Sequence[Term]) -> bool:
    return [t[0] for t in shared] == [t[0] for t in terms] and all(
        s[1] >= p[1] for s, p in zip(shared, terms, strict=True)
    )


def tightened(coarse: Mapping[str, int], new: Mapping[str, int]) -> dict[str, int]:
    """Replace exactly the 41 owner rows; every other cursor row keeps its coarse bound."""
    require(len(coarse) == CURSOR_COUNT, "cursor row count")
    require(
        frozenset(new) == owner_ids() and set(new) <= set(coarse),
        "replacement is not exactly the owners",
    )
    require(all(type(b) is int and b < coarse[p] for p, b in new.items()), "non-strict replacement")
    return {p: new.get(p, b) for p, b in coarse.items()}


def family_status(
    before: Mapping[str, object], after: Mapping[str, object], new: Mapping[str, int]
) -> str:
    strict = frozenset(new) == owner_ids() and all(b < EXPECTED_FAMILY for b in new.values())
    dropped = integer(after["MAXIMUM"]) < integer(before["MAXIMUM"])
    return "PROVEN_FAMILY_GAIN" if strict and dropped else "NO_PROVEN_FAMILY_GAIN"


def fixed_input() -> dict[str, object]:
    for head, tree in (
        (INPUT_HEAD, INPUT_TREE),
        (TWO_OWNER_HEAD, TWO_OWNER_TREE),
        (R2_HEAD, R2_TREE),
        (MAIN_HEAD, MAIN_TREE),
        (BASE_HEAD, BASE_TREE),
    ):
        identity(head, tree)
    require(git("rev-parse", f"{INPUT_HEAD}^").decode().strip() == TWO_OWNER_HEAD, "input parent")
    require(git("rev-parse", f"{TWO_OWNER_HEAD}^").decode().strip() == R2_HEAD, "upstream parent")
    for path, digest in INPUT_PINS.items():
        require(
            (ROOT / path).read_bytes() == blob(INPUT_HEAD, path, digest), f"input changed: {path}"
        )
    fixed = prev.compute_result()  # Re-executes the input, its two upstreams and the Base closure.
    require(render(fixed) == (ROOT / INPUT_RESULT).read_bytes(), "input result not reproduced")
    return fixed


def compute_result() -> dict[str, object]:
    fixed = fixed_input()
    pins = r2.source_pins()
    sealed = decode(blob(BASE_HEAD, r2.BASE_RESULT, r2.BASE_SHA))
    resolved = {p: integer(b) for p, b in obj(fixed["RESOLVED_ROW_BOUNDS_AFTER"]).items()}
    r2.checked_rows(list(resolved.items()), resolved)
    require(sha(r2.projection(resolved)) == fixed["BOUNDS_SHA256_AFTER"], "resolved ledger digest")
    cursor = obj(fixed["CURSOR"])
    require(
        cursor == sealed["CURSOR"] and sha(render(cursor)) == sealed["CURSOR_SHA256"], "cursor pin"
    )
    ids = cast(list[str], cursor["PROFILE_IDS"])
    coarse = {p: integer(b) for p, b in obj(cursor["COARSE_BOUND_PROJECTION"]).items()}
    require(set(coarse) == set(ids), "cursor IDs")
    for pid, bound in coarse.items():
        envelope_row = route.r28.coarse_profile_envelope(tuple(map(int, pid)))
        require(
            envelope_row.family_upper_bound == bound, "cursor bound differs from Base evaluator"
        )
    first = prev.family(resolved, coarse)
    owners = cast(list[str], fixed["ALL_NEW_MAX_OWNERS"])
    require(
        first["MAXIMUM"] == fixed["FAMILY_AFTER"] == EXPECTED_FAMILY
        and first["ALL_MAX_OWNERS"] == owners
        and frozenset(owners) == owner_ids()
        and first["MAXIMUM_OWNER_CLASSES"] == ["CURSOR"]
        and first["NEXT_DISTINCT_BOUND"] == EXPECTED_NEXT
        and cursor["ID"] in owners
        and cursor["BOUND"] == EXPECTED_FAMILY,
        "fixed family/owners not reproduced",
    )
    covered = coverage(ids, owners, list(resolved))
    per: dict[str, dict[str, object]] = {}
    envelopes: dict[str, list[Term]] = {}
    for pid in owners:
        facts = theorem(pid)
        floor = route.r28.profile_s4_floor(tuple(map(int, pid)))
        require(floor == 112, "Base S4 floor drift")
        terms = envelope(pid, floor)
        new = max(t[1] for t in terms)
        require(new == max(t[1] for t in envelope(pid, 0)), "S4 base floor is load-bearing")
        require(coarse[pid] == EXPECTED_FAMILY and new < coarse[pid], "no strict drop")
        envelopes[pid] = terms
        per[pid] = {
            **facts,
            "OLD_COARSE_BOUND": coarse[pid],
            "NEW_BOUND": new,
            "DELTA": coarse[pid] - new,
            "TERM_COUNT": len(terms),
            "ALL_T_TERMS_SHA256": sha(render(terms)),
            "ALL_ARGMAX": [t for t in terms if t[1] == new],
            "TOP_T_TERM": terms[-1],
        }
    fractional = sum((4 * t[4]) % 7 != 0 for terms in envelopes.values() for t in terms)
    choose3_floor = min(integer(v["SUM_C_G_3"]) for v in per.values())
    shared = class_envelope(owners, choose3_floor, G_CEILING)
    require(all(dominated(shared, terms) for terms in envelopes.values()), "class domination")
    shared_bound = max(t[1] for t in shared)
    new_bounds = {p: integer(v["NEW_BOUND"]) for p, v in per.items()}
    after = tightened(coarse, new_bounds)
    require(
        {p: b for p, b in after.items() if p not in new_bounds}
        == {p: b for p, b in coarse.items() if p not in new_bounds},
        "other cursor rows changed",
    )
    last = prev.family(resolved, after)
    status = family_status(first, last, new_bounds)
    incumbent = integer(sealed["INCUMBENT"])
    require(integer(last["MAXIMUM"]) >= incumbent, "family below incumbent")
    require(
        wedges(tuple(map(int, "55555555555511111100"))) != OWNER_W, "incumbent profile in class"
    )
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": status,
        "INPUT_CERTIFICATE": {
            "HEAD": INPUT_HEAD,
            "TREE": INPUT_TREE,
            "FILE_SHA256": INPUT_PINS,
            "REPRODUCED_BYTE_FOR_BYTE": True,
        },
        "UPSTREAM_CERTIFICATE_CHAIN": [
            {"ROLE": "INPUT_SINGLE_OWNER", "HEAD": INPUT_HEAD, "TREE": INPUT_TREE},
            {"ROLE": "UPSTREAM_TWO_OWNER", "HEAD": TWO_OWNER_HEAD, "TREE": TWO_OWNER_TREE},
            {"ROLE": "UPSTREAM_R2", "HEAD": R2_HEAD, "TREE": R2_TREE},
            {"ROLE": "MATHEMATICAL_BASE", "HEAD": BASE_HEAD, "TREE": BASE_TREE},
        ],
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
        "CURSOR_COVERAGE": covered,
        "OWNER_IDS": owners,
        "PER_CURSOR": per,
        "CLASS_ENVELOPE": {
            "MEMBERS": OWNER_COUNT,
            "WEDGES": OWNER_W,
            "A_MAX": 169,
            "SUM_C_G_3_FLOOR": choose3_floor,
            "G_MAX_CEILING": G_CEILING,
            "BOUND": shared_bound,
            "ALL_ARGMAX": [t for t in shared if t[1] == shared_bound],
            "ALL_T_TERMS": shared,
            "DOMINATES_EVERY_MEMBER_AT_EVERY_T": True,
        },
        "TERM_COLUMNS": ["T", "BOUND", "K4_FLOOR", "CONTAINED_K4", "S4_FLOOR", "S3"],
        "ROUNDING": "K4_CEILING; A_MAX_FLOOR; FINAL_EXACT_RATIONAL_CEILING",
        "FRACTIONAL_S4_CREDIT_TERMS": fractional,
        "S4_AUTHORITY": {
            "INHERITED_FLOOR": 112,
            "FUNCTION": "b649_k20_min_s2_current_cursor_class_owner_chase_r28.profile_s4_floor",
            "RULE": "MAX(INHERITED,ROUTE_B); NONNEGATIVE_LOWER_BOUND_SUBTRACTED",
            "FLOOR_ZERO_GIVES_SAME_MAXIMA": True,
        },
        "S5_USED": False,
        "OLD_CURSOR_MAXIMUM": max(coarse[p] for p in owners),
        "NEW_OWNER_MAXIMUM": max(new_bounds.values()),
        "NEW_OWNER_MAXIMUM_IDS": sorted(
            p for p, b in new_bounds.items() if b == max(new_bounds.values())
        ),
        "ALL_41_STRICTLY_BELOW_OLD": all(b < EXPECTED_FAMILY for b in new_bounds.values()),
        "CURSOR": cursor,
        "CURSOR_SHA256": sha(render(cursor)),
        "CURSOR_ROW_BOUNDS_BEFORE": coarse,
        "CURSOR_ROW_BOUNDS_AFTER": after,
        "OTHER_CURSOR_ROWS_UNCHANGED": len(coarse) - len(new_bounds),
        "RESOLVED_ROWS": len(resolved),
        "RESOLVED_ROW_BOUNDS": resolved,
        "RESOLVED_BOUNDS_SHA256": sha(r2.projection(resolved)),
        "RESOLVED_ROWS_CHANGED": 0,
        "PROJECTED_FAMILY_BEFORE": first,
        "PROJECTED_FAMILY_AFTER": last,
        "FAMILY_BEFORE": first["MAXIMUM"],
        "FAMILY_AFTER": last["MAXIMUM"],
        "FAMILY_DELTA": integer(first["MAXIMUM"]) - integer(last["MAXIMUM"]),
        "ALL_NEW_MAX_OWNERS": last["ALL_MAX_OWNERS"],
        "NEXT_DISTINCT_BOUND": last["NEXT_DISTINCT_BOUND"],
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
        "FRESH_FOCUSED_REVIEW": "REQUIRED_ON_FROZEN_CANDIDATE_TREE; VERDICT_EXTERNAL_TO_BLOB",
        "SOLVER_CALLS": 0,
        "FULL_SUPPORT_GRAPHS_ENUMERATED": 0,
        "PORTFOLIOS_ENUMERATED": 0,
        "GLOBAL_OPTIMUM": "UNKNOWN",
        "PREDICTION_GAIN_CLAIMED": False,
        "CANONICAL_AUTHORITY_CHANGED": "NO",
        "REMOTE_WRITE": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "REMAINING_TASK_MODEL": "強模型(已驗收結果接合); 最強模型(下一個 family owner 的新證明)",
    }


def verify_result(stored: Mapping[str, object]) -> None:
    require(render(stored) == render(compute_result()), "stored result not exactly reproducible")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reproduce the 41-cursor shared bound")
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
                "STATUS": result["TASK_STATUS"],
                "FAMILY": result["PROJECTED_FAMILY_AFTER"],
                "GAP": result["GAP_TO_INCUMBENT"],
            }
        )
    )


if __name__ == "__main__":
    main()
