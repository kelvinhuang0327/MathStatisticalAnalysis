"""NB degree cap and Route B over the exact W=808 frontier class (NB W808 R1).

Authority is the NB R1 result committed at 41fef463, pinned by SHA-256. NB R1's
own zero-solve replay (R32, then NB) rebuilds the 1,795-row resolved ledger,
adds its 133 certified W=809 members, and leaves the cursor at
66666652222222222221, the first profile of the sum d^2 = 290 class, at the
coarse 313,553,960, which is also the family maximum. This module replays that
chain, requires the replayed NB result to equal the sealed JSON, and does not
reopen W=809. R33, R25 and the Hunter tree are not inputs.

W=808 class. 2W = 1326 + sum d^2, so W = 808 is exactly sum d^2 = 290. The class
is frozen twice: once by R30's ranked plateau lookup, and once by enumerating
every histogram with 20 tickets, degrees 0..6, sum d = 66 and sum d^2 = 290
without pruning, then applying the same three admissibility screens. Both must
give the same profiles, and none of them may already be resolved.

Per-profile certificate. Each member gets the NB cap (NB R1's closed-form
neighbourhood lemma on g = 6 + d) and R18's induced-P3 class cap. A cap
certified earlier would also count, but none exists: no row of the pinned R25,
R30, R31 or R32 tables names a W=808 member, and the scan fails closed if one
does. The cap is therefore min(NB, R18), and its origin is recorded. Route B is
evaluated at every t in 22..cap, and the profile bound is the maximum over t.
Every term is re-derived with exact rational arithmetic, independently of the
R32 helper, and the two must agree term for term.

Frontier and family. The cursor moves to the first unresolved W <= 807 profile
from the ranked lookup. Its coarse envelope depends only on W. It is checked
to dominate the coarse envelope at every W from 774 (the minimum, from
convexity) to 807, so it bounds every unresolved profile that remains. The
family maximum is recomputed over the full ledger (1,795 + 133 + 147 rows) and
the new cursor. No solver, census, portfolio search or outcome enumeration
is run.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from fractions import Fraction
from itertools import combinations
from math import comb
from pathlib import Path
from time import monotonic
from types import ModuleType

from . import b649_k20_min_s2_nb_degree_cap_frontier_r1 as nb
from .b649_k20_min_s2_dangerous_core_realizability_r5 import (
    residual_double_ticket_degrees,
    simple_graph_degree_sequence_is_graphical,
)
from .b649_k20_min_s2_load_bearing_plateau_descent_r16 import PlateauFrontier
from .b649_k20_min_s2_next_active_profile_exact_bound_r8 import (
    INHERITED_FOURTH_ORDER_CREDIT,
    coarse_profile_envelope,
    profile_shadow_obstruction,
)
from .b649_k20_min_s2_realizable_core_class_bound_r4 import (
    K20_LABEL_COUNT,
    K20_S1,
    K20_S2,
    K20_TICKET_CAPACITY,
    K20_TICKET_COUNT,
    K20_TRIPLE_INCIDENCE_COUNT,
    K20_TRIPLE_SUPPORT_COUNT,
    linear_triple_degree_sequence_passes_pair_capacity,
    overlap_wedge_count,
    s3_sum_from_wedges_and_triangles,
)
from .b649_k20_min_s2_resolved_above_cursor_owner_chase_r20 import (
    Certificate,
    decode_profile,
    profile_id,
)

r28 = nb.r28
r29 = nb.r29
r30 = nb.r30
r31 = nb.r31
r32 = nb.r32
DegreeProfile = nb.DegreeProfile
Chase = nb.Chase
Term = nb.Term
CapAuthorities = nb.CapAuthorities

TASK_ID = "B649_K20_MIN_S2_NB_W808_FRONTIER_R1"
TASK_BRANCH = "codex/b649-k20-min-s2-nb-w808-frontier-r1"
WORKTREE_PATH = "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/" + TASK_ID
BASE_HEAD = "41fef463e39dd301925b23605cee61c9ddd44086"
BASE_TREE = "b069b7dcfaae2893d5c372604771398a58366c17"
NB_RESULT = nb.RESULT_FILENAME
NB_SHA256 = "609d5f6bf96e8d6454918f747c764e479f88bbb0da94d3934c2969b8f6cc7f0f"
START_BOUND = 313_553_960
START_GAP = 290_072
START_LEDGER_COUNT = nb.LEDGER_COUNT + nb.TARGET_W809_COUNT
START_LEDGER_SHA256 = "e3df25fe27e40e74b759c978b0178b3523309bc61cc4757540b4b8f0da0afb70"
CURSOR: DegreeProfile = (6, 6, 6, 6, 6, 6, 5, *([2] * 12), 1)
CURSOR_WEDGES = 808
CURSOR_SQUARE_SUM = 290
W809_SQUARE_SUM = nb.CURSOR_SQUARE_SUM
NEXT_COARSE_REFERENCE = 313_551_160
INCUMBENT = nb.INCUMBENT
WITNESS_UNION = nb.WITNESS_UNION
WITNESS_PROFILE = nb.WITNESS_PROFILE
WITNESS_TRIANGLES = nb.WITNESS_TRIANGLES
CURSOR_NB_OPEN_WEDGE_FLOOR = 86
CURSOR_NB_TRIANGLE_CAP = 240
TARGET_W808_COUNT = 147
TARGET_W808_CLASS_MAX = 313_340_936
K4_LIGHT = 448
K4_HEAVY = 679
SCREEN_PAIR_CAPACITY = "LINEAR_TRIPLE_PAIR_CAPACITY"
SCREEN_RESIDUAL = "RESIDUAL_DOUBLE_DEGREES_NOT_GRAPHICAL"
SCREEN_SHADOW = "PROFILE_SHADOW_OBSTRUCTION"
CAP_NB = nb.CAP_NB
CAP_R18 = nb.CAP_R18
CAP_TIE = "NB_AND_R18_EQUAL"
ROUTE = "NB_DEGREE_CAP_ROUTE_B_ALL_T_W808"
SCANNED_TABLES = ("proofs", "steps", "plateaus", "route4", "route_b", "cheap")
PROVENANCE_MODULES: tuple[ModuleType, ...] = (nb, r32, r31, r30, r28)
REPLAY_SECONDS = 600.0
RESULT_DIRECTORY = nb.RESULT_DIRECTORY
RESULT_FILENAME = "b649-k20-min-s2-nb-w808-frontier-r1-result.json"
SUCCESS_A = "SUCCESS_A_CERTIFIED_FAMILY_UPPER_BOUND_REDUCTION"
SUCCESS_B = "SUCCESS_B_NO_FAMILY_DROP"
BOUND_RULE = (
    "MAX_OVER_T_IN_22..MIN(NB,R18)_CAP_OF_"
    "CEIL(S1-S2+S3(T)-4*MAX(112,679*K4(T)-231*MIN(K4(T),A_MAX))/7)"
)

object_row = r28.object_row
rows = r28.rows
integer = r28.integer


def git(*args: str) -> bytes:
    return r31.git(*args)


def module_provenance() -> dict[str, str]:
    """Every reused module must be byte-identical to its blob at the committed base."""

    root = r28.repo_root().resolve()
    out: dict[str, str] = {}
    for module in PROVENANCE_MODULES:
        source = module.__file__
        if source is None:
            raise AssertionError("reused module has no source file")
        path = Path(source).resolve()
        if not path.is_relative_to(root):
            raise AssertionError(f"reused module loaded outside this tree: {path}")
        relative = path.relative_to(root).as_posix()
        try:
            committed = git("show", f"{BASE_HEAD}:{relative}")
        except subprocess.CalledProcessError as exc:
            raise AssertionError(f"reused module is not committed at the base: {relative}") from exc
        if path.read_bytes() != committed:
            raise AssertionError(f"reused module differs from the committed base: {relative}")
        out[relative] = hashlib.sha256(committed).hexdigest()
    return out


def nb_authority() -> tuple[dict[str, object], str]:
    """The NB R1 result at the base: exact tree, pinned digest, sealed frontier facts."""

    if git("rev-parse", f"{BASE_HEAD}^{{tree}}").decode().strip() != BASE_TREE:
        raise AssertionError("the base tree changed")
    blob = git("show", f"{BASE_HEAD}:{RESULT_DIRECTORY}/{NB_RESULT}")
    digest = hashlib.sha256(blob).hexdigest()
    if digest != NB_SHA256:
        raise AssertionError("sealed NB fingerprint changed")
    result = object_row(json.loads(blob))
    expected: dict[str, object] = {
        "TASK_ID": nb.TASK_ID,
        "TASK_STATUS": nb.SUCCESS_A,
        "NB_LEMMA_STATUS": "PROVED_CLOSED_FORM",
        "FINAL_FAMILY_UPPER_BOUND": START_BOUND,
        "NEXT_CURSOR_PROFILE": profile_id(CURSOR),
        "NEXT_CURSOR_BOUND": START_BOUND,
        "NEXT_CURSOR_SQUARE_SUM": CURSOR_SQUARE_SUM,
        "W809_CLASS_COUNT": nb.TARGET_W809_COUNT,
        "RESOLVED_LEDGER_COUNT": nb.LEDGER_COUNT,
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": START_GAP,
    }
    for key, value in expected.items():
        if result.get(key) != value:
            raise AssertionError(f"NB authority mismatch: {key}")
    return result, digest


def start_chase(deadline: float) -> tuple[Chase, CapAuthorities, dict[str, object]]:
    """Replay R32 -> NB with zero solves; the replay must equal the sealed NB result."""

    sealed, _digest = nb_authority()
    chase, _r32_digest, _r32 = nb.start_chase(deadline)
    authorities = nb.load_cap_authorities()
    replayed = nb.certify_family(chase, authorities, deadline)
    if not nb.same_result(replayed, sealed):
        raise AssertionError("NB replay diverged from the sealed NB result")
    family, owners = r28.family_state(chase)
    if (
        family != START_BOUND
        or (chase.cursor, chase.cursor_bound) != (CURSOR, START_BOUND)
        or list(map(profile_id, owners)) != sealed["FINAL_BOUND_OWNER_IDS"]
        or len(chase.bounds) != START_LEDGER_COUNT
        or r29.ledger_digest(chase) != START_LEDGER_SHA256
    ):
        raise AssertionError("NB cursor, owner or complete-ledger reconstruction failed")
    return chase, authorities, sealed


def square_sum(profile: Sequence[int]) -> int:
    return sum(d * d for d in profile)


def raw_histograms(target: int) -> tuple[DegreeProfile, ...]:
    """Every non-increasing 20-tuple over 0..6 with sum 66 and sum d^2 = target.

    The only pruning is monotone: partial sums never decrease.
    """

    found: list[DegreeProfile] = []

    def visit(prefix: list[int], top: int, total: int, squares: int) -> None:
        if total > K20_TRIPLE_INCIDENCE_COUNT or squares > target:
            return
        if len(prefix) == K20_TICKET_COUNT:
            if total == K20_TRIPLE_INCIDENCE_COUNT and squares == target:
                found.append(tuple(prefix))
            return
        for d in range(top, -1, -1):
            prefix.append(d)
            visit(prefix, d, total + d, squares + d * d)
            prefix.pop()

    visit([], K20_TICKET_CAPACITY, 0, 0)
    return tuple(sorted(found, reverse=True))


def admissibility_screen(profile: DegreeProfile) -> str | None:
    """The first of the three inherited admissibility screens a histogram fails."""

    if not linear_triple_degree_sequence_passes_pair_capacity(profile, K20_TRIPLE_SUPPORT_COUNT):
        return SCREEN_PAIR_CAPACITY
    if not simple_graph_degree_sequence_is_graphical(residual_double_ticket_degrees(profile)):
        return SCREEN_RESIDUAL
    if profile_shadow_obstruction(profile) is not None:
        return SCREEN_SHADOW
    return None


def independent_class(target: int) -> tuple[tuple[DegreeProfile, ...], dict[str, int], int]:
    """(admissible profiles, rejections by screen, raw histogram count) of one sum d^2 class."""

    raw = raw_histograms(target)
    rejected: Counter[str] = Counter()
    admitted: list[DegreeProfile] = []
    for profile in raw:
        screen = admissibility_screen(profile)
        if screen is None:
            admitted.append(profile)
        else:
            rejected[screen] += 1
    if len(admitted) + sum(rejected.values()) != len(raw):
        raise AssertionError("class screening dropped a histogram")
    return tuple(admitted), dict(sorted(rejected.items())), len(raw)


def assert_class_membership(
    chase: Chase, plateau: PlateauFrontier
) -> tuple[tuple[DegreeProfile, ...], dict[str, int], int]:
    """The ranked plateau is exactly the whole admissible sum d^2 = 290 class, none resolved."""

    eligible = nb.enumerate_degree_square_class(CURSOR_SQUARE_SUM)
    admitted, rejected, raw = independent_class(CURSOR_SQUARE_SUM)
    if admitted != eligible:
        raise AssertionError("pruned and unpruned W=808 class enumerations disagree")
    if any(profile in chase.bounds for profile in eligible):
        raise AssertionError("a W=808 profile is already in the resolved ledger")
    if not eligible or eligible[0] != CURSOR or tuple(plateau.profiles) != eligible:
        raise AssertionError("W=808 plateau disagrees with the independent degree class")
    for profile in eligible:
        if 2 * overlap_wedge_count(profile) != nb.WEDGE_OFFSET + square_sum(profile):
            raise AssertionError("wedge identity failed inside the W=808 class")
        if overlap_wedge_count(profile) != CURSOR_WEDGES:
            raise AssertionError("frontier member left the W=808 class")
    return eligible, rejected, raw


def prior_cap_scan(
    chase: Chase, authorities: CapAuthorities, members: Collection[DegreeProfile]
) -> dict[str, object]:
    """No sealed row may name a member: an unclassified cap is never borrowed."""

    quoted = [f'"{profile_id(profile)}"' for profile in members]
    tables = {
        "proofs": authorities.proofs,
        "steps": authorities.steps,
        "plateaus": authorities.plateaus,
        "route4": authorities.route4,
        "route_b": authorities.route_b,
        "cheap": authorities.cheap,
    }
    if tuple(tables) != SCANNED_TABLES:
        raise AssertionError("prior-cap scan does not cover every pinned table")
    scanned: dict[str, int] = {}
    hits: list[str] = []
    for name, table in tables.items():
        scanned[name] = len(table)
        for index, row in enumerate(table):
            blob = json.dumps(row, sort_keys=True)
            if any(identity in blob for identity in quoted):
                hits.append(f"{name}[{index}]")
    catalog = [profile_id(p) for p in members if p in chase.catalog]
    if hits or catalog:
        raise AssertionError(
            "a sealed row names a W=808 member; its cap is unclassified: "
            + ",".join(hits + catalog)
        )
    return {
        "STATUS": "NO_PRIOR_CERTIFIED_CAP_FOR_ANY_MEMBER",
        "TABLE_ROWS_SCANNED": scanned,
        "ROWS_NAMING_A_MEMBER": 0,
        "MEMBERS_IN_CATALOG": 0,
    }


def ceil_fraction(value: Fraction) -> int:
    return -((-value.numerator) // value.denominator)


def floor_fraction(value: Fraction) -> int:
    return value.numerator // value.denominator


def exact_route_b_terms(profile: DegreeProfile, cap: int, base: int) -> list[Term]:
    """Route B at every t in 22..cap, re-derived in exact rationals without the R32 helper."""

    graph = [K20_TICKET_CAPACITY + d for d in profile]
    wedges = sum(comb(g, 2) for g in graph)
    choose3 = sum(comb(g, 3) for g in graph)
    top = max(graph)
    outside = sum(d * (g - 2) for d, g in zip(profile, graph, strict=True))
    a_max = floor_fraction(Fraction(outside, 3))
    out: list[Term] = []
    for t in range(K20_TRIPLE_SUPPORT_COUNT, cap + 1):
        open_wedges = wedges - 3 * t
        if open_wedges < 0:
            raise AssertionError("triangle count exceeds the wedge identity")
        excess = choose3 - max(0, top - 2) * open_wedges
        k4 = max(0, ceil_fraction(Fraction(excess, 4)))
        contained = min(k4, a_max)
        s4 = max(base, K4_LIGHT * contained + K4_HEAVY * (k4 - contained))
        s3 = s3_sum_from_wedges_and_triangles(wedges, t - K20_TRIPLE_SUPPORT_COUNT)
        bound = ceil_fraction(K20_S1 - K20_S2 + s3 - Fraction(4 * s4, 7))
        out.append((t, bound, k4, contained, s4, s3))
    return out


def member_certificate(profile: DegreeProfile) -> dict[str, object]:
    """NB cap, R18 cap, their minimum with origin, and the exact all-t Route-B maximum."""

    if r32.structural_failures(profile):
        raise AssertionError("profile outside the min-S2 family")
    if r30.k4_quartet_weights() != r32.K4_WEIGHTS or r32.K4_WEIGHTS != {
        r32.WITH_TRIPLE: K4_LIGHT,
        r32.WITHOUT_TRIPLE: K4_HEAVY,
    }:
        raise AssertionError("K4 quartet weights changed")
    wedges, floor, nb_cap = nb.profile_nb_cap(profile)
    if wedges != CURSOR_WEDGES or square_sum(profile) != CURSOR_SQUARE_SUM:
        raise AssertionError("frontier member left the W=808 class")
    if profile == CURSOR and (
        floor < CURSOR_NB_OPEN_WEDGE_FLOOR or nb_cap > CURSOR_NB_TRIANGLE_CAP
    ):
        raise AssertionError("cursor NB regression")
    nb.assert_nb_capacity(nb.profile_degrees(profile))
    class_cap = nb.r18_cap(profile)
    cap = nb.combined_triangle_cap(nb_cap, class_cap)
    if cap != min(nb_cap, class_cap):
        raise AssertionError("triangle cap is not the strongest verified cap")
    origin = CAP_NB if nb_cap < class_cap else CAP_R18 if class_cap < nb_cap else CAP_TIE
    base = r28.profile_s4_floor(profile)
    terms = r32.route_b_envelope(profile, cap, base)
    if [term[0] for term in terms] != list(range(K20_TRIPLE_SUPPORT_COUNT, cap + 1)):
        raise AssertionError("Route-B envelope does not cover every t in 22..cap")
    if terms != exact_route_b_terms(profile, cap, base):
        raise AssertionError("Route-B integer rounding disagrees with the exact re-derivation")
    bound, s3, argmax, increasing = nb.profile_route_b(profile, cap)
    best = max(terms, key=lambda term: (term[1], term[0]))
    if (bound, s3, argmax) != (best[1], best[5], best[0]) or bound != max(t[1] for t in terms):
        raise AssertionError("all-t maximum disagrees with the envelope")
    coarse = coarse_profile_envelope(profile)
    if coarse.fourth_order_credit != INHERITED_FOURTH_ORDER_CREDIT:
        raise AssertionError("coarse fourth-order credit changed")
    if coarse.family_upper_bound != START_BOUND or bound > coarse.family_upper_bound:
        raise AssertionError("Route B exceeds the W=808 coarse envelope")
    return {
        "PROFILE_ID": profile_id(profile),
        "SQUARE_SUM": square_sum(profile),
        "WEDGE_COUNT": wedges,
        "NB_OPEN_WEDGE_FLOOR": floor,
        "NB_TRIANGLE_CAP": nb_cap,
        "R18_TRIANGLE_CAP": class_cap,
        "PRIOR_CERTIFIED_CAP": None,
        "TRIANGLE_CAP": cap,
        "CAP_ORIGIN": origin,
        "A_MAX": r32.contained_triple_k4_cap(profile),
        "S4_BASE": base,
        "T_RANGE": [K20_TRIPLE_SUPPORT_COUNT, cap],
        "TERM_COUNT": len(terms),
        "ENVELOPE_STRICTLY_INCREASING_IN_T": increasing,
        "ARGMAX_TRIANGLES": best[0],
        "K4_FLOOR_AT_ARGMAX": best[2],
        "CONTAINED_TRIPLE_K4_AT_ARGMAX": best[3],
        "S4_FLOOR_AT_ARGMAX": best[4],
        "S3_AT_ARGMAX": best[5],
        "ALL_T_MAX_BOUND": bound,
        "COARSE_FAMILY_UPPER_BOUND": coarse.family_upper_bound,
        "PREMISES": [
            "MIN_S2_STRUCTURE",
            "GRAPHICAL_DEGREE_LIST",
            "NB_CAPACITY_RECOMPUTED",
            "R18_CLASS_CAP",
            "K4_WEIGHTS_448_679",
            "S4_BASE_IS_PROFILE_FLOOR",
            "EXACT_RATIONAL_TERMS_AGREE",
        ],
        "ROUTE": ROUTE,
    }


def minimum_square_sum() -> int:
    """By convexity the balanced histogram minimises sum d^2 at sum d = 66."""

    quotient, remainder = divmod(K20_TRIPLE_INCIDENCE_COUNT, K20_TICKET_COUNT)
    return remainder * (quotient + 1) ** 2 + (K20_TICKET_COUNT - remainder) * quotient**2


def coarse_bound_at_wedges(wedges: int) -> int:
    """R8's coarse envelope as a function of W alone."""

    noncore = wedges // 3 - K20_TRIPLE_SUPPORT_COUNT
    s3 = s3_sum_from_wedges_and_triangles(wedges, noncore)
    return K20_S1 - K20_S2 + s3 - INHERITED_FOURTH_ORDER_CREDIT


def coarse_dominance(nxt: DegreeProfile, nxt_bound: int) -> dict[str, object]:
    """Every W from the convexity minimum to W(next) has coarse envelope <= the next bound."""

    low = (nb.WEDGE_OFFSET + minimum_square_sum()) // 2
    high = overlap_wedge_count(nxt)
    for profile in (CURSOR, nxt):
        envelope = coarse_profile_envelope(profile)
        if coarse_bound_at_wedges(envelope.wedge_count) != envelope.family_upper_bound:
            raise AssertionError("coarse envelope is not a function of W alone")
    if coarse_bound_at_wedges(high) != nxt_bound or coarse_bound_at_wedges(CURSOR_WEDGES) != (
        START_BOUND
    ):
        raise AssertionError("coarse frontier bounds disagree with the W formula")
    values = {w: coarse_bound_at_wedges(w) for w in range(low, high + 1)}
    if max(values.values()) != nxt_bound:
        raise AssertionError("a lower-W coarse envelope exceeds the next frontier bound")
    return {
        "STATUS": "PASS",
        "MIN_SQUARE_SUM": minimum_square_sum(),
        "W_MIN": low,
        "W_MAX": high,
        "COARSE_AT_W_MIN": values[low],
        "COARSE_AT_W_MAX": values[high],
    }


def frontier_completeness(chase: Chase, nxt: DegreeProfile) -> dict[str, object]:
    """W=809 stays resolved, and the next cursor is the first unresolved profile of its class."""

    w809 = nb.enumerate_degree_square_class(W809_SQUARE_SUM)
    if len(w809) != nb.TARGET_W809_COUNT or any(p not in chase.bounds for p in w809):
        raise AssertionError("a W=809 profile is unresolved")
    level = square_sum(nxt)
    if level >= CURSOR_SQUARE_SUM or level % 2:
        raise AssertionError("next frontier is not a lower square-sum class")
    eligible = nb.enumerate_degree_square_class(level)
    admitted, _rejected, _raw = independent_class(level)
    if admitted != eligible:
        raise AssertionError("pruned and unpruned next-class enumerations disagree")
    first = next((p for p in eligible if p not in chase.bounds), None)
    if first != nxt:
        raise AssertionError("next cursor is not the first unresolved profile of its class")
    for between in range(CURSOR_SQUARE_SUM - 2, level, -2):
        if any(p not in chase.bounds for p in nb.enumerate_degree_square_class(between)):
            raise AssertionError("an unresolved class lies between W=808 and the next cursor")
    return {
        "STATUS": "PASS",
        "W809_RESOLVED": len(w809),
        "NEXT_CLASS_SQUARE_SUM": level,
        "NEXT_CLASS_ADMISSIBLE": len(eligible),
        "NEXT_CLASS_RESOLVED_ABOVE_CURSOR": eligible.index(nxt),
    }


def install_frontier(
    chase: Chase, plateau: PlateauFrontier, certificates: Sequence[Mapping[str, object]]
) -> DegreeProfile:
    """Point the cursor at the next class, then enter the certified members in the ledger."""

    nxt, nxt_bound = plateau.next_profile, plateau.next_bound
    if nxt is None or nxt_bound is None or nxt in chase.bounds:
        raise AssertionError("the W=808 frontier did not end at a lower unresolved class")
    coarse = coarse_profile_envelope(nxt)
    if (
        coarse.family_upper_bound != nxt_bound
        or coarse.fourth_order_credit != INHERITED_FOURTH_ORDER_CREDIT
    ):
        raise AssertionError("next cursor coarse envelope disagrees with the plateau")
    chase.cursor, chase.cursor_bound = nxt, nxt_bound
    for index, row in enumerate(certificates):
        profile = decode_profile(nb.text(row["PROFILE_ID"]))
        if profile in chase.bounds or profile == chase.cursor:
            raise AssertionError("frontier member collides with the ledger or the cursor")
        bound = integer(row["ALL_T_MAX_BOUND"])
        chase.bounds[profile] = bound
        chase.catalog[profile] = Certificate(
            profile,
            bound,
            RESULT_FILENAME,
            f"W808_CERTIFICATES[{index}]",
            "CLASS_ENVELOPE_ONLY",
            integer(row["S3_AT_ARGMAX"]),
            integer(row["S4_BASE"]),
            integer(row["TRIANGLE_CAP"]),
            ROUTE,
        )
    return nxt


def witness_nb_soundness(witness: Mapping[str, object]) -> dict[str, object]:
    """The realized STS(13) portfolio obeys NB vertex by vertex, and NB-capped Route B covers it."""

    report = nb.witness_soundness(witness)
    tickets = [set(t) for t in r30.sts13_witness()]
    multiplicity = Counter(n for t in tickets for n in t)
    if len(multiplicity) != K20_LABEL_COUNT or set(multiplicity.values()) != {2, 3}:
        raise AssertionError("witness is not a min-S2 portfolio")
    neighbours = [
        {b for b in range(K20_TICKET_COUNT) if b != a and len(tickets[a] & tickets[b]) == 1}
        for a in range(K20_TICKET_COUNT)
    ]
    if any(len(tickets[a] & tickets[b]) > 1 for a, b in combinations(range(K20_TICKET_COUNT), 2)):
        raise AssertionError("witness has a pair overlap above one")
    local = nb.graph_nb_rows(neighbours)
    profile = tuple(sorted((sum(multiplicity[n] == 3 for n in t) for t in tickets), reverse=True))
    if profile != WITNESS_PROFILE:
        raise AssertionError("witness profile differs from the sealed witness")
    if sorted(g for g, _, _ in local) != sorted(nb.profile_degrees(profile)):
        raise AssertionError("witness graph degrees are not 6 + d")
    triangles = sum(inside for _, inside, _ in local) // 3
    open_wedges = sum(comb(g, 2) - inside for g, inside, _ in local)
    _wedges, floor, nb_cap = nb.profile_nb_cap(profile)
    if triangles != WITNESS_TRIANGLES or open_wedges < floor or triangles > nb_cap:
        raise AssertionError("NB cap fails on the realized witness")
    cap = nb.combined_triangle_cap(nb_cap, nb.r18_cap(profile))
    terms = r32.route_b_envelope(profile, cap, r28.profile_s4_floor(profile))
    bound = max(term[1] for term in terms)
    if bound < WITNESS_UNION:
        raise AssertionError("Route B fell below the realized witness portfolio")
    return {
        "STATUS": "PASS",
        "PROFILE_ID": profile_id(profile),
        "REALIZED_TRIANGLES": triangles,
        "REALIZED_OPEN_WEDGES": open_wedges,
        "NB_OPEN_WEDGE_FLOOR": floor,
        "NB_TRIANGLE_CAP": nb_cap,
        "NB_ROUTE_B_ALL_T_BOUND": bound,
        "EXACT_ANY_PRIZE_UNION": WITNESS_UNION,
        "ROUTE_B_ON_WITNESS": report,
    }


def certify_w808(chase: Chase, authorities: CapAuthorities, deadline: float) -> dict[str, object]:
    """Freeze W=808, certify every member, move the cursor, recompute the family maximum."""

    provenance = module_provenance()
    primitives = r28.canonical_primitive_preflight()
    if primitives["STATUS"] != "PASS" or primitives.get("K20_S1") != K20_S1:
        raise AssertionError("canonical primitive gate failed")
    witness = witness_nb_soundness(authorities.witness)
    if (chase.cursor, chase.cursor_bound) != (CURSOR, START_BOUND) or CURSOR in chase.bounds:
        raise AssertionError("NB cursor moved before the W=808 freeze")
    family_before, _owners = r28.family_state(chase)
    if family_before != START_BOUND:
        raise AssertionError("start family bound changed")
    original = dict(chase.bounds)
    resolved_max = max(original.values())
    plateau = r30.freeze_plateau(CURSOR, START_BOUND, chase.bounds, deadline)
    if type(plateau) is not PlateauFrontier:
        raise AssertionError("plateau freeze returned an unexpected frontier")
    members, rejected, raw = assert_class_membership(chase, plateau)
    scan = prior_cap_scan(chase, authorities, members)
    certificates = [member_certificate(profile) for profile in members]
    class_max = max(integer(row["ALL_T_MAX_BOUND"]) for row in certificates)
    class_owners = [r["PROFILE_ID"] for r in certificates if r["ALL_T_MAX_BOUND"] == class_max]
    nxt = install_frontier(chase, plateau, certificates)
    completeness = frontier_completeness(chase, nxt)
    dominance = coarse_dominance(nxt, integer(chase.cursor_bound))
    r30.record_owner(chase)
    family, owners = nb.assert_family_agreement(chase)
    independent = max(resolved_max, class_max, integer(chase.cursor_bound))
    if family != independent or family < INCUMBENT:
        raise AssertionError("family recompute disagreement")
    if len(chase.bounds) != START_LEDGER_COUNT + len(members):
        raise AssertionError("ledger lost or duplicated a profile")
    owner_ids = list(map(profile_id, owners))
    owner_type = "UNRESOLVED_CURSOR_COARSE_ENVELOPE" if owners[0] == nxt else "RESOLVED_LEDGER"
    competing = max((b for p, b in chase.bounds.items() if p not in owners), default=0)
    status = SUCCESS_A if family < START_BOUND else SUCCESS_B
    origins = Counter(nb.text(row["CAP_ORIGIN"]) for row in certificates)
    return {
        "TASK_ID": TASK_ID,
        "TASK_BRANCH": TASK_BRANCH,
        "WORKTREE_PATH": WORKTREE_PATH,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_STATUS": status,
        "NB_LEMMA_STATUS": "PROVED_CLOSED_FORM_REUSED_FROM_NB_R1",
        "ALL_T_CERTIFICATE_STATUS": "PASS_EXACT_RATIONAL_REDERIVATION_EVERY_T",
        "START_FAMILY_BOUND": START_BOUND,
        "START_LEDGER_COUNT": START_LEDGER_COUNT,
        "START_LEDGER_SHA256": START_LEDGER_SHA256,
        "W808_SQUARE_SUM": CURSOR_SQUARE_SUM,
        "W808_RAW_HISTOGRAM_COUNT": raw,
        "W808_SCREEN_REJECTIONS": rejected,
        "W808_PROFILE_COUNT": len(members),
        "W808_CERTIFIED_COUNT": len(certificates),
        "W808_CLASS_MAX": class_max,
        "W808_CLASS_MAX_PROFILE_IDS": class_owners,
        "W808_CAP_ORIGIN_COUNTS": dict(sorted(origins.items())),
        "W808_PRIOR_CAP_SCAN": scan,
        "W808_PROFILE_IDS": [profile_id(profile) for profile in members],
        "W808_CERTIFICATES": certificates,
        "PRE_EXISTING_RESOLVED_MAX": resolved_max,
        "NEXT_FRONTIER_PROFILE": profile_id(nxt),
        "NEXT_FRONTIER_W": overlap_wedge_count(nxt),
        "NEXT_FRONTIER_SQUARE_SUM": square_sum(nxt),
        "NEXT_FRONTIER_BOUND": chase.cursor_bound,
        "NEXT_FRONTIER_MATCHES_REFERENCE": chase.cursor_bound == NEXT_COARSE_REFERENCE,
        "FRONTIER_COMPLETENESS": completeness,
        "COARSE_DOMINANCE_BELOW_NEXT": dominance,
        "FAMILY_MAX_RECOMPUTATION": "PASS_FULL_LEDGER_AND_CURSOR",
        "FINAL_LEDGER_COUNT": len(chase.bounds),
        "FINAL_LEDGER_SHA256": r29.ledger_digest(chase),
        "FAMILY_UPPER_BOUND": family,
        "FINAL_FAMILY_UPPER_BOUND": family,
        "FINAL_OWNER_CLASS": ",".join(owner_ids),
        "FINAL_OWNER_TYPE": owner_type,
        "FINAL_BOUND_OWNER_IDS": owner_ids,
        "NEXT_COMPETING_RESOLVED_BOUND": competing,
        "CURRENT_INCUMBENT": INCUMBENT,
        "REMAINING_GAP": family - INCUMBENT,
        "CANONICAL_PRIMITIVE_STATUS": primitives["STATUS"],
        "CANONICAL_PRIMITIVES": primitives,
        "WITNESS_SOUNDNESS_STATUS": witness["STATUS"],
        "WITNESS_NB_SOUNDNESS": witness,
        "MODULE_PROVENANCE": provenance,
        "S1": K20_S1,
        "S2": K20_S2,
        "BOUND_RULE": BOUND_RULE,
        "SOLVER_CALLS": 0,
        "OUTCOME_ENUMERATIONS": 0,
        "NEW_HEAVY_SOLVER_STARTED": "NO",
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "FULL_CENSUS_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "NB_RESULT_SHA256": NB_SHA256,
    }


SUMMARY_KEYS = (
    "TASK_STATUS",
    "W808_PROFILE_COUNT",
    "W808_CERTIFIED_COUNT",
    "W808_CLASS_MAX",
    "NEXT_FRONTIER_W",
    "NEXT_FRONTIER_BOUND",
    "FINAL_FAMILY_UPPER_BOUND",
    "FINAL_OWNER_CLASS",
    "REMAINING_GAP",
)


def result_path() -> Path:
    return r28.repo_root() / RESULT_DIRECTORY / RESULT_FILENAME


def write_result(result: Mapping[str, object]) -> str:
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    target = result_path()
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, target)
    return hashlib.sha256(payload.encode()).hexdigest()


def replay_result(deadline: float | None = None) -> dict[str, object]:
    """Derive the W=808 result twice from the sealed NB chain; the written bytes must match."""

    limit = monotonic() + REPLAY_SECONDS if deadline is None else deadline
    first_chase, first_authorities, _sealed = start_chase(limit)
    first = certify_w808(first_chase, first_authorities, limit)
    second_chase, second_authorities, _sealed = start_chase(limit)
    second = certify_w808(second_chase, second_authorities, limit)
    if not nb.same_result(first, second):
        raise AssertionError("W=808 replay diverged")
    digest = write_result(second)
    loaded = object_row(json.loads(result_path().read_text(encoding="utf-8")))
    if not nb.same_result(loaded, first):
        raise AssertionError("written W=808 result diverged from the replay")
    if hashlib.sha256(result_path().read_bytes()).hexdigest() != digest:
        raise AssertionError("written W=808 result digest changed")
    return second


def main() -> None:
    result = replay_result()
    print(json.dumps({key: result[key] for key in SUMMARY_KEYS}), flush=True)


if __name__ == "__main__":
    main()
