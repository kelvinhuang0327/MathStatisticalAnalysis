"""NB degree cap and Route B over the 22 exact W=807..786 frontier classes (NB batch R1).

Authority is the NB W=808 result committed at 96d44032, pinned by SHA-256. Its own
zero-solve replay (R32, then NB, then W=808) rebuilds the 2,075-row resolved ledger and
leaves the cursor at 66666643322222222211, the first profile of the W=807 class, at the
coarse 313,551,160, which is also the family maximum. This module replays that chain,
requires the replayed W=808 result to equal the sealed JSON, and does not reopen any
class with W >= 808. R33, R25 and the Hunter tree are not inputs.

Classes. 2W = 1326 + sum d^2, so W = 807 down to W = 786 is exactly sum d^2 = 288 down
to 246 in steps of two. Every class is frozen twice: once by R30's ranked plateau lookup
from the moving cursor, and once by enumerating every histogram with 20 tickets, degrees
0..6, sum d = 66 and the class's sum d^2 without pruning, then applying the same three
admissibility screens. Both must give the same profiles in the same order, the member
count must equal the pinned count, and none of them may already be resolved.

Per-profile certificate. Each member gets the NB cap (NB R1's closed-form neighbourhood
lemma on g = 6 + d, re-derived here from the lemma text and required to agree) and R18's
induced-P3 class cap. A cap certified earlier would also count, but none exists: no row
of the pinned R25, R30, R31 or R32 tables names a member, and the scan fails closed if
one does. The cap is therefore min(NB, R18) and its origin is recorded. Route B is
evaluated at every t in 22..cap with exact integer floors and ceilings, re-derived in
exact rationals independently of the R32 helper, and the profile bound is the maximum
over t. The per-profile rows are stored as columns, and each can be re-audited alone.

Frontier and family. After each class the cursor moves to the first profile of the next
class. After W=786 it sits on the first W=785 profile. Its coarse envelope depends only on
W, and is checked against every one of the 197 unresolved profiles with W <= 785. The
family maximum is recomputed over the complete ledger and the cursor. The whole
admissible census is partitioned against the ledger: the ledger must be exactly the
admissible classes from W=786 to W=834. Twelve admissible profiles of W=835..837 are
outside the replayed ledger. They are inherited, not reopened, not installed and not used
for the family bound, but their closed-form bounds are recorded as a cross-check so the
exposure is explicit. No solver, census search, portfolio search or outcome enumeration
is run.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from math import comb
from pathlib import Path
from time import monotonic
from types import ModuleType
from typing import cast

from . import b649_k20_min_s2_nb_w808_frontier_r1 as w8
from .b649_k20_min_s2_load_bearing_plateau_descent_r16 import PlateauFrontier
from .b649_k20_min_s2_next_active_profile_exact_bound_r8 import (
    INHERITED_FOURTH_ORDER_CREDIT,
    coarse_profile_envelope,
)
from .b649_k20_min_s2_realizable_core_class_bound_r4 import (
    K20_S1,
    K20_S2,
    K20_TICKET_CAPACITY,
    K20_TRIPLE_SUPPORT_COUNT,
    overlap_wedge_count,
)
from .b649_k20_min_s2_resolved_above_cursor_owner_chase_r20 import (
    Certificate,
    decode_profile,
    profile_id,
)

nb = w8.nb
r28 = w8.r28
r29 = w8.r29
r30 = w8.r30
r31 = w8.r31
r32 = w8.r32
DegreeProfile = w8.DegreeProfile
Chase = w8.Chase
CapAuthorities = w8.CapAuthorities

TASK_ID = "B649_K20_MIN_S2_NB_W807_W786_BATCH_CERTIFICATE_R1"
TASK_BRANCH = "codex/b649-k20-min-s2-nb-w807-w786-batch-certificate-r1"
WORKTREE_PATH = "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/" + TASK_ID
BASE_HEAD = "96d4403251ea1f577921dc859a1eff3be528b470"
BASE_TREE = "d8c78a64d869f450a0cd201cc6f1015255972c11"
W808_RESULT = w8.RESULT_FILENAME
W808_SHA256 = "01d86528fa983f558ec576945173efecfc9b74e3d17edca4365e562736aeb99d"
START_BOUND = 313_551_160
START_GAP = 287_272
START_LEDGER_COUNT = w8.START_LEDGER_COUNT + w8.TARGET_W808_COUNT
START_LEDGER_SHA256 = "b844b1cf550abd64fe50a6fddd2e980af678e0dbaa3119e0dce20be9367672d8"
START_CURSOR_ID = "66666643322222222211"
START_RESOLVED_MAX = 313_404_784
INCUMBENT = nb.INCUMBENT
WITNESS_UNION = nb.WITNESS_UNION
WITNESS_PROFILE = nb.WITNESS_PROFILE
HIGH_W = 807
LOW_W = 786
NEXT_W = LOW_W - 1
CLASS_WEDGES: tuple[int, ...] = tuple(range(HIGH_W, LOW_W - 1, -1))
CLASS_COUNTS: dict[int, int] = {
    807: 147, 806: 140, 805: 150, 804: 154, 803: 142, 802: 149, 801: 147, 800: 139,
    799: 141, 798: 137, 797: 125, 796: 130, 795: 121, 794: 107, 793: 108, 792: 102,
    791: 86, 790: 83, 789: 76, 788: 65, 787: 60, 786: 51,
}  # fmt: skip
TOTAL_PROFILES = 2_560
NEXT_CLASS_COUNT = 41
NEXT_COARSE_REFERENCE = 313_394_584
FRONTIER_COUNT = 197
MIN_W = 774
LEDGER_TOP_W = 834
CENSUS_TOTAL = 4_844
MAX_SQUARE_SUM = 396
UNLEDGERED_COUNT = 12
UNLEDGERED_IDS_SHA256 = "e67525d0ce144e1e2292d0a1d48017c744b67cbd727bf0c1636903f1cc584217"
K4_LIGHT = w8.K4_LIGHT
K4_HEAVY = w8.K4_HEAVY
CAP_NB = nb.CAP_NB
CAP_R18 = nb.CAP_R18
CAP_TIE = w8.CAP_TIE
ROUTE = "NB_DEGREE_CAP_ROUTE_B_ALL_T_W807_W786"
PREMISES: tuple[str, ...] = (
    "MIN_S2_STRUCTURE",
    "GRAPHICAL_DEGREE_LIST",
    "NB_CAPACITY_RECOMPUTED",
    "NB_CAP_INDEPENDENTLY_DERIVED",
    "R18_CLASS_CAP",
    "K4_WEIGHTS_448_679",
    "S4_BASE_IS_PROFILE_FLOOR",
    "EXACT_RATIONAL_TERMS_AGREE",
)
ROW_COLUMNS: tuple[str, ...] = (
    "PROFILE_ID",
    "NB_OPEN_WEDGE_FLOOR",
    "NB_TRIANGLE_CAP",
    "R18_TRIANGLE_CAP",
    "TRIANGLE_CAP",
    "CAP_ORIGIN",
    "A_MAX",
    "S4_BASE",
    "ARGMAX_TRIANGLES",
    "K4_FLOOR_AT_ARGMAX",
    "CONTAINED_TRIPLE_K4_AT_ARGMAX",
    "S4_FLOOR_AT_ARGMAX",
    "S3_AT_ARGMAX",
    "ALL_T_MAX_BOUND",
    "ENVELOPE_STRICTLY_INCREASING_IN_T",
)
PROVENANCE_MODULES: tuple[ModuleType, ...] = (w8, nb, r32, r31, r30, r28)
REPLAY_SECONDS = 900.0
RESULT_DIRECTORY = nb.RESULT_DIRECTORY
RESULT_FILENAME = "b649-k20-min-s2-nb-w807-w786-batch-certificate-r1-result.json"
SUCCESS_A = "SUCCESS_A_CERTIFIED_FAMILY_UPPER_BOUND_REDUCTION"
SUCCESS_B = "SUCCESS_B_NO_FAMILY_DROP"
BOUND_RULE = w8.BOUND_RULE

object_row = r28.object_row
rows = r28.rows
integer = r28.integer
text = nb.text
git = w8.git


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


def w808_authority() -> tuple[dict[str, object], str]:
    """The W=808 result at the base: exact tree, pinned digest, sealed frontier facts."""

    if git("rev-parse", f"{BASE_HEAD}^{{tree}}").decode().strip() != BASE_TREE:
        raise AssertionError("the base tree changed")
    blob = git("show", f"{BASE_HEAD}:{RESULT_DIRECTORY}/{W808_RESULT}")
    digest = hashlib.sha256(blob).hexdigest()
    if digest != W808_SHA256:
        raise AssertionError("sealed W808 fingerprint changed")
    result = object_row(json.loads(blob))
    expected: dict[str, object] = {
        "TASK_ID": w8.TASK_ID,
        "TASK_STATUS": w8.SUCCESS_A,
        "FINAL_FAMILY_UPPER_BOUND": START_BOUND,
        "NEXT_FRONTIER_PROFILE": START_CURSOR_ID,
        "NEXT_FRONTIER_BOUND": START_BOUND,
        "NEXT_FRONTIER_W": HIGH_W,
        "FINAL_LEDGER_COUNT": START_LEDGER_COUNT,
        "FINAL_LEDGER_SHA256": START_LEDGER_SHA256,
        "FINAL_BOUND_OWNER_IDS": [START_CURSOR_ID],
        "PRE_EXISTING_RESOLVED_MAX": START_RESOLVED_MAX,
        "W808_PROFILE_COUNT": w8.TARGET_W808_COUNT,
        "CURRENT_INCUMBENT": INCUMBENT,
        "REMAINING_GAP": START_GAP,
    }
    for key, value in expected.items():
        if result.get(key) != value:
            raise AssertionError(f"W808 authority mismatch: {key}")
    return result, digest


def start_chase(deadline: float) -> tuple[Chase, CapAuthorities, dict[str, object]]:
    """Replay R32 -> NB -> W=808 with zero solves; the replay must equal the sealed W=808."""

    sealed, _digest = w808_authority()
    chase, authorities, _nb_sealed = w8.start_chase(deadline)
    replayed = w8.certify_w808(chase, authorities, deadline)
    if not nb.same_result(replayed, sealed):
        raise AssertionError("W808 replay diverged from the sealed W808 result")
    family, owners = r28.family_state(chase)
    if (
        family != START_BOUND
        or (chase.cursor, chase.cursor_bound) != (decode_profile(START_CURSOR_ID), START_BOUND)
        or list(map(profile_id, owners)) != sealed["FINAL_BOUND_OWNER_IDS"]
        or len(chase.bounds) != START_LEDGER_COUNT
        or r29.ledger_digest(chase) != START_LEDGER_SHA256
        or max(chase.bounds.values()) != START_RESOLVED_MAX
    ):
        raise AssertionError("W808 cursor, owner or complete-ledger reconstruction failed")
    return chase, authorities, sealed


def class_level(wedges: int) -> int:
    """sum d^2 of the W-class, from 2W = 1326 + sum d^2."""

    return 2 * wedges - nb.WEDGE_OFFSET


def coarse_at(wedges: int) -> int:
    """R8's coarse envelope as a function of W alone."""

    return w8.coarse_bound_at_wedges(wedges)


def exact_nb_cap(profile: DegreeProfile) -> tuple[int, int, int]:
    """(W, OW_NB, cap) from the lemma text alone, independent of the nb module's helpers."""

    graph = sorted((K20_TICKET_CAPACITY + d for d in profile), reverse=True)
    wedges = sum(comb(g, 2) for g in graph)
    floor = 0
    for index, g in enumerate(graph):
        chosen = (graph[:index] + graph[index + 1 :])[:g]
        capacity = sum(min(u - 1, g - 1) for u in chosen)
        floor += comb(g, 2) - capacity // 2
    return wedges, floor, (wedges - floor) // 3


def assert_class_membership(
    chase: Chase, plateau: PlateauFrontier, wedges: int
) -> tuple[tuple[DegreeProfile, ...], dict[str, int], int]:
    """The ranked plateau is exactly the whole admissible class of W, none of it resolved."""

    level = class_level(wedges)
    eligible = nb.enumerate_degree_square_class(level)
    admitted, rejected, raw = w8.independent_class(level)
    if admitted != eligible:
        raise AssertionError(f"pruned and unpruned W={wedges} class enumerations disagree")
    if len(eligible) != CLASS_COUNTS.get(wedges):
        raise AssertionError(f"W={wedges} class size differs from the pinned count")
    if any(profile in chase.bounds or profile in chase.catalog for profile in eligible):
        raise AssertionError(f"a W={wedges} profile is already in the resolved ledger")
    if chase.cursor != eligible[0] or tuple(plateau.profiles) != eligible:
        raise AssertionError(f"W={wedges} plateau disagrees with the independent degree class")
    for profile in eligible:
        if 2 * overlap_wedge_count(profile) != nb.WEDGE_OFFSET + w8.square_sum(profile):
            raise AssertionError(f"wedge identity failed inside the W={wedges} class")
        if overlap_wedge_count(profile) != wedges:
            raise AssertionError(f"frontier member left the W={wedges} class")
    return eligible, rejected, raw


def member_certificate(profile: DegreeProfile, wedges: int) -> dict[str, object]:
    """NB cap, R18 cap, their minimum with origin, and the exact all-t Route-B maximum."""

    if r32.structural_failures(profile):
        raise AssertionError("profile outside the min-S2 family")
    if r30.k4_quartet_weights() != r32.K4_WEIGHTS or r32.K4_WEIGHTS != {
        r32.WITH_TRIPLE: K4_LIGHT,
        r32.WITHOUT_TRIPLE: K4_HEAVY,
    }:
        raise AssertionError("K4 quartet weights changed")
    profile_wedges, floor, nb_cap = nb.profile_nb_cap(profile)
    if profile_wedges != wedges or w8.square_sum(profile) != class_level(wedges):
        raise AssertionError(f"frontier member left the W={wedges} class")
    if (profile_wedges, floor, nb_cap) != exact_nb_cap(profile):
        raise AssertionError("NB cap disagrees with the independent derivation")
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
    if terms != w8.exact_route_b_terms(profile, cap, base):
        raise AssertionError("Route-B integer rounding disagrees with the exact re-derivation")
    bound, _s3, _argmax, increasing = nb.profile_route_b(profile, cap)
    best = max(terms, key=lambda term: (term[1], term[0]))
    if bound != best[1] or bound != max(term[1] for term in terms):
        raise AssertionError("all-t maximum disagrees with the envelope")
    if profile == WITNESS_PROFILE and bound < WITNESS_UNION:
        raise AssertionError("Route B fell below the realized witness portfolio")
    coarse = coarse_profile_envelope(profile)
    if coarse.fourth_order_credit != INHERITED_FOURTH_ORDER_CREDIT:
        raise AssertionError("coarse fourth-order credit changed")
    if coarse.family_upper_bound != coarse_at(wedges) or bound > coarse.family_upper_bound:
        raise AssertionError(f"Route B exceeds the W={wedges} coarse envelope")
    return {
        "PROFILE_ID": profile_id(profile),
        "SQUARE_SUM": w8.square_sum(profile),
        "WEDGE_COUNT": profile_wedges,
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
        "PREMISES": list(PREMISES),
        "ROUTE": ROUTE,
    }


def certificate_row(certificate: Mapping[str, object]) -> list[object]:
    return [certificate[column] for column in ROW_COLUMNS]


def expand_row(wedges: int, row: Sequence[object]) -> dict[str, object]:
    """Rebuild the full certificate a stored row claims, from the row and its class alone."""

    if len(row) != len(ROW_COLUMNS):
        raise AssertionError("certificate row has the wrong width")
    cells = dict(zip(ROW_COLUMNS, row, strict=True))
    cap = integer(cells["TRIANGLE_CAP"])
    return {
        "PROFILE_ID": text(cells["PROFILE_ID"]),
        "SQUARE_SUM": class_level(wedges),
        "WEDGE_COUNT": wedges,
        "NB_OPEN_WEDGE_FLOOR": cells["NB_OPEN_WEDGE_FLOOR"],
        "NB_TRIANGLE_CAP": cells["NB_TRIANGLE_CAP"],
        "R18_TRIANGLE_CAP": cells["R18_TRIANGLE_CAP"],
        "PRIOR_CERTIFIED_CAP": None,
        "TRIANGLE_CAP": cap,
        "CAP_ORIGIN": cells["CAP_ORIGIN"],
        "A_MAX": cells["A_MAX"],
        "S4_BASE": cells["S4_BASE"],
        "T_RANGE": [K20_TRIPLE_SUPPORT_COUNT, cap],
        "TERM_COUNT": cap - K20_TRIPLE_SUPPORT_COUNT + 1,
        "ENVELOPE_STRICTLY_INCREASING_IN_T": cells["ENVELOPE_STRICTLY_INCREASING_IN_T"],
        "ARGMAX_TRIANGLES": cells["ARGMAX_TRIANGLES"],
        "K4_FLOOR_AT_ARGMAX": cells["K4_FLOOR_AT_ARGMAX"],
        "CONTAINED_TRIPLE_K4_AT_ARGMAX": cells["CONTAINED_TRIPLE_K4_AT_ARGMAX"],
        "S4_FLOOR_AT_ARGMAX": cells["S4_FLOOR_AT_ARGMAX"],
        "S3_AT_ARGMAX": cells["S3_AT_ARGMAX"],
        "ALL_T_MAX_BOUND": cells["ALL_T_MAX_BOUND"],
        "COARSE_FAMILY_UPPER_BOUND": coarse_at(wedges),
        "PREMISES": list(PREMISES),
        "ROUTE": ROUTE,
    }


def audit_row(wedges: int, row: Sequence[object]) -> None:
    """A stored row must equal a fresh exact re-derivation, field by field."""

    claimed = expand_row(wedges, row)
    expected = member_certificate(decode_profile(text(row[0])), wedges)
    differing = sorted(key for key in expected if claimed.get(key) != expected[key])
    if differing:
        raise AssertionError(
            "certificate row differs from its exact re-derivation: " + ",".join(differing)
        )


def install_class(
    chase: Chase,
    plateau: PlateauFrontier,
    wedges: int,
    certificates: Sequence[Mapping[str, object]],
) -> DegreeProfile:
    """Point the cursor at the next class, then enter the certified members in the ledger."""

    nxt, nxt_bound = plateau.next_profile, plateau.next_bound
    if nxt is None or nxt_bound is None or nxt in chase.bounds:
        raise AssertionError(f"the W={wedges} frontier did not end at a lower unresolved class")
    if overlap_wedge_count(nxt) != wedges - 1:
        raise AssertionError(f"the class after W={wedges} is not W={wedges - 1}")
    coarse = coarse_profile_envelope(nxt)
    if (
        coarse.family_upper_bound != nxt_bound
        or coarse.family_upper_bound != coarse_at(wedges - 1)
        or coarse.fourth_order_credit != INHERITED_FOURTH_ORDER_CREDIT
    ):
        raise AssertionError("next cursor coarse envelope disagrees with the plateau")
    chase.cursor, chase.cursor_bound = nxt, nxt_bound
    for index, row in enumerate(certificates):
        profile = decode_profile(text(row["PROFILE_ID"]))
        if profile in chase.bounds or profile == chase.cursor:
            raise AssertionError("frontier member collides with the ledger or the cursor")
        bound = integer(row["ALL_T_MAX_BOUND"])
        chase.bounds[profile] = bound
        chase.catalog[profile] = Certificate(
            profile,
            bound,
            RESULT_FILENAME,
            f"W{wedges}_CERTIFICATES[{index}]",
            "CLASS_ENVELOPE_ONLY",
            integer(row["S3_AT_ARGMAX"]),
            integer(row["S4_BASE"]),
            integer(row["TRIANGLE_CAP"]),
            ROUTE,
        )
    return nxt


def class_completeness(chase: Chase, wedges: int, nxt: DegreeProfile) -> dict[str, object]:
    """The class is fully resolved, and the cursor is the first unresolved profile after it."""

    members = nb.enumerate_degree_square_class(class_level(wedges))
    if len(members) != CLASS_COUNTS[wedges] or any(p not in chase.bounds for p in members):
        raise AssertionError(f"a W={wedges} profile is unresolved")
    level = w8.square_sum(nxt)
    if level != class_level(wedges) - 2:
        raise AssertionError("next frontier is not the adjacent lower square-sum class")
    eligible = nb.enumerate_degree_square_class(level)
    admitted, _rejected, _raw = w8.independent_class(level)
    if admitted != eligible:
        raise AssertionError("pruned and unpruned next-class enumerations disagree")
    expected = CLASS_COUNTS.get(wedges - 1, NEXT_CLASS_COUNT)
    if len(eligible) != expected or any(p in chase.bounds for p in eligible):
        raise AssertionError("next class is not whole and unresolved")
    if eligible[0] != nxt:
        raise AssertionError("next cursor is not the first unresolved profile of its class")
    return {
        "STATUS": "PASS",
        "CLASS_RESOLVED": len(members),
        "NEXT_CLASS_SQUARE_SUM": level,
        "NEXT_CLASS_ADMISSIBLE": len(eligible),
        "NEXT_CLASS_RESOLVED_ABOVE_CURSOR": 0,
    }


def certify_class(
    chase: Chase, authorities: CapAuthorities, wedges: int, deadline: float
) -> dict[str, object]:
    """Freeze one class, certify every member, move the cursor, enter the ledger."""

    cursor, active = chase.cursor, chase.cursor_bound
    if cursor is None or active is None or cursor in chase.bounds:
        raise AssertionError(f"the cursor is not unresolved at the W={wedges} frontier")
    if overlap_wedge_count(cursor) != wedges or active != coarse_at(wedges):
        raise AssertionError(f"the cursor is not at the W={wedges} frontier")
    plateau = r30.freeze_plateau(cursor, active, chase.bounds, deadline)
    if type(plateau) is not PlateauFrontier:
        raise AssertionError("plateau freeze returned an unexpected frontier")
    members, rejected, raw = assert_class_membership(chase, plateau, wedges)
    scan = w8.prior_cap_scan(chase, authorities, members)
    certificates = [member_certificate(profile, wedges) for profile in members]
    class_max = max(integer(row["ALL_T_MAX_BOUND"]) for row in certificates)
    owners = [text(r["PROFILE_ID"]) for r in certificates if r["ALL_T_MAX_BOUND"] == class_max]
    origins = Counter(text(row["CAP_ORIGIN"]) for row in certificates)
    nxt = install_class(chase, plateau, wedges, certificates)
    completeness = class_completeness(chase, wedges, nxt)
    return {
        "W": wedges,
        "SQUARE_SUM": class_level(wedges),
        "RAW_HISTOGRAM_COUNT": raw,
        "SCREEN_REJECTIONS": rejected,
        "PROFILE_COUNT": len(members),
        "CERTIFIED_COUNT": len(certificates),
        "COARSE_FAMILY_UPPER_BOUND": coarse_at(wedges),
        "CLASS_MAX": class_max,
        "CLASS_MAX_PROFILE_IDS": owners,
        "CAP_ORIGIN_COUNTS": dict(sorted(origins.items())),
        "PRIOR_CAP_SCAN_ROWS_NAMING_A_MEMBER": scan["ROWS_NAMING_A_MEMBER"],
        "NEXT_PROFILE": profile_id(nxt),
        "NEXT_BOUND": chase.cursor_bound,
        "COMPLETENESS": completeness,
        "CERTIFICATES": [certificate_row(row) for row in certificates],
    }


def census_by_wedges() -> dict[int, tuple[DegreeProfile, ...]]:
    """Every admissible profile of the whole census, by W, from the independent enumerator."""

    out: dict[int, tuple[DegreeProfile, ...]] = {}
    for level in range(w8.minimum_square_sum(), MAX_SQUARE_SUM + 1, 2):
        members = nb.enumerate_degree_square_class(level)
        if members:
            out[(nb.WEDGE_OFFSET + level) // 2] = members
    return out


def frontier_below(
    chase: Chase, census: Mapping[int, Sequence[DegreeProfile]]
) -> dict[str, object]:
    """Every unresolved profile has W <= 785 and its coarse envelope is at most the cursor's."""

    cursor, bound = chase.cursor, chase.cursor_bound
    if cursor is None or bound is None or cursor in chase.bounds:
        raise AssertionError("missing unresolved cursor")
    first = census[NEXT_W][0]
    if cursor != first or overlap_wedge_count(cursor) != NEXT_W or bound != coarse_at(NEXT_W):
        raise AssertionError("cursor is not the first W=785 profile at its coarse envelope")
    remaining = [p for w, members in census.items() if w < LOW_W for p in members]
    if len(remaining) != FRONTIER_COUNT or any(p in chase.bounds for p in remaining):
        raise AssertionError("unresolved frontier population changed")
    for profile in remaining:
        envelope = coarse_profile_envelope(profile)
        w = overlap_wedge_count(profile)
        if envelope.family_upper_bound != coarse_at(w) or envelope.family_upper_bound > bound:
            raise AssertionError("an unresolved profile exceeds the cursor coarse envelope")
    values = {w: coarse_at(w) for w in range(MIN_W, NEXT_W + 1)}
    if min(w for w in census) != MIN_W or max(values.values()) != bound:
        raise AssertionError("coarse envelope is not maximal at the next frontier")
    if nb.enumerate_degree_square_class(w8.minimum_square_sum() - 2):
        raise AssertionError("a class below the convexity minimum is not empty")
    return {
        "STATUS": "PASS",
        "UNRESOLVED_PROFILES": len(remaining),
        "MIN_SQUARE_SUM": w8.minimum_square_sum(),
        "W_MIN": MIN_W,
        "W_MAX": NEXT_W,
        "COARSE_AT_W_MIN": values[MIN_W],
        "COARSE_AT_W_MAX": values[NEXT_W],
    }


def unledgered_cross_check(
    census: Mapping[int, Sequence[DegreeProfile]], ledger: Collection[DegreeProfile]
) -> dict[str, object]:
    """Admissible profiles above the ledger. Informational: never installed, never used."""

    top = [p for w, members in census.items() if w > LEDGER_TOP_W for p in members]
    ids = [profile_id(p) for p in top]
    digest = hashlib.sha256(json.dumps(ids).encode()).hexdigest()
    if len(top) != UNLEDGERED_COUNT or any(p in ledger for p in top):
        raise AssertionError("unledgered top population changed")
    if digest != UNLEDGERED_IDS_SHA256:
        raise AssertionError("unledgered top identities changed")
    bounds = {
        profile_id(p): integer(member_certificate(p, overlap_wedge_count(p))["ALL_T_MAX_BOUND"])
        for p in top
    }
    worst = max(bounds.values())
    return {
        "STATUS": "INHERITED_EXCEPTION_NOT_REOPENED_NOT_INSTALLED_NOT_USED_FOR_FAMILY_BOUND",
        "PROFILE_COUNT": len(top),
        "W_VALUES": sorted({overlap_wedge_count(p) for p in top}),
        "PROFILE_IDS": ids,
        "PROFILE_IDS_SHA256": digest,
        "CLOSED_FORM_NB_ROUTE_B_BOUNDS": bounds,
        "CLOSED_FORM_MAX": worst,
        "CLOSED_FORM_MAX_PROFILE_IDS": [i for i, b in bounds.items() if b == worst],
    }


def ledger_universe_check(
    chase: Chase, census: Mapping[int, Sequence[DegreeProfile]], low_w: int
) -> dict[str, object]:
    """The ledger is exactly the admissible classes low_w..834; the rest are classified."""

    total = sum(len(members) for members in census.values())
    if total != CENSUS_TOTAL:
        raise AssertionError("admissible census size changed")
    expected = {p for w, members in census.items() if low_w <= w <= LEDGER_TOP_W for p in members}
    if set(chase.bounds) != expected or set(chase.catalog) != expected:
        raise AssertionError(
            f"ledger is not exactly the admissible classes W={low_w}..{LEDGER_TOP_W}"
        )
    below = sum(len(members) for w, members in census.items() if w < low_w)
    above = sum(len(members) for w, members in census.items() if w > LEDGER_TOP_W)
    if len(expected) + below + above != total:
        raise AssertionError("census partition lost a profile")
    return {
        "STATUS": "PASS",
        "CENSUS_PROFILES": total,
        "LEDGERED": len(expected),
        "UNRESOLVED_BELOW_LEDGER": below,
        "OUTSIDE_LEDGER_ABOVE": above,
        "LEDGER_W_RANGE": [low_w, LEDGER_TOP_W],
    }


def object_row_list(raw: object) -> list[object]:
    if not isinstance(raw, list):
        raise AssertionError("certificate row is not a list")
    return list(cast("list[object]", raw))


def audit_class(wedges: int, class_row: Mapping[str, object]) -> int:
    """Re-derive a sealed class from nothing but its W; return the number of rows audited."""

    members = nb.enumerate_degree_square_class(class_level(wedges))
    stored = rows(class_row["CERTIFICATES"])
    if class_row.get("W") != wedges or len(members) != CLASS_COUNTS[wedges]:
        raise AssertionError(f"sealed W={wedges} class header is wrong")
    identities = [text(object_row_list(item)[0]) for item in stored]
    if identities != [profile_id(p) for p in members]:
        raise AssertionError(f"sealed W={wedges} rows are not the exact class in order")
    for item in stored:
        audit_row(wedges, object_row_list(item))
    bounds = [
        integer(object_row_list(item)[ROW_COLUMNS.index("ALL_T_MAX_BOUND")]) for item in stored
    ]
    class_max = max(bounds)
    owners = [i for i, b in zip(identities, bounds, strict=True) if b == class_max]
    origins = Counter(
        text(object_row_list(item)[ROW_COLUMNS.index("CAP_ORIGIN")]) for item in stored
    )
    if (
        class_row.get("CLASS_MAX") != class_max
        or class_row.get("CLASS_MAX_PROFILE_IDS") != owners
        or class_row.get("CAP_ORIGIN_COUNTS") != dict(sorted(origins.items()))
        or class_row.get("PROFILE_COUNT") != len(stored)
        or class_row.get("CERTIFIED_COUNT") != len(stored)
        or class_row.get("COARSE_FAMILY_UPPER_BOUND") != coarse_at(wedges)
        or class_max > coarse_at(wedges)
    ):
        raise AssertionError(f"sealed W={wedges} class summary is wrong")
    return len(stored)


def audit_sealed_result(result: Mapping[str, object]) -> dict[str, object]:
    """Independently re-audit every sealed class and the batch totals."""

    classes = object_row(result["W_CLASSES"])
    if sorted(classes) != sorted(str(w) for w in CLASS_WEDGES):
        raise AssertionError("sealed class set is not exactly W=807..786")
    if list(rows(result["CERTIFICATE_COLUMNS"])) != list(ROW_COLUMNS):
        raise AssertionError("sealed certificate columns changed")
    audited = sum(audit_class(w, object_row(classes[str(w)])) for w in CLASS_WEDGES)
    maxima = {w: integer(object_row(classes[str(w)])["CLASS_MAX"]) for w in CLASS_WEDGES}
    batch_max = max(maxima.values())
    if (
        audited != TOTAL_PROFILES
        or result.get("PROFILES_CERTIFIED") != audited
        or result.get("CLASSES_PROCESSED") != len(CLASS_WEDGES)
        or result.get("BATCH_CLASS_MAX") != batch_max
        or result.get("BATCH_CLASS_MAX_W") != max(w for w, m in maxima.items() if m == batch_max)
    ):
        raise AssertionError("sealed batch totals are wrong")
    return {"STATUS": "PASS", "ROWS_AUDITED": audited, "BATCH_CLASS_MAX": batch_max}


def certify_batch(chase: Chase, authorities: CapAuthorities, deadline: float) -> dict[str, object]:
    """Certify W=807..786, move the cursor to W=785, recompute the family maximum."""

    provenance = module_provenance()
    primitives = r28.canonical_primitive_preflight()
    if primitives["STATUS"] != "PASS" or primitives.get("K20_S1") != K20_S1:
        raise AssertionError("canonical primitive gate failed")
    witness = w8.witness_nb_soundness(authorities.witness)
    cursor = decode_profile(START_CURSOR_ID)
    if (chase.cursor, chase.cursor_bound) != (cursor, START_BOUND) or cursor in chase.bounds:
        raise AssertionError("the cursor moved before the W=807 freeze")
    family_before, _owners = r28.family_state(chase)
    if family_before != START_BOUND:
        raise AssertionError("start family bound changed")
    census = census_by_wedges()
    universe_before = ledger_universe_check(chase, census, 808)
    unledgered = unledgered_cross_check(census, chase.bounds)
    resolved_max = max(chase.bounds.values())
    classes: dict[str, object] = {}
    summary: list[dict[str, object]] = []
    for wedges in CLASS_WEDGES:
        row = certify_class(chase, authorities, wedges, deadline)
        classes[str(wedges)] = row
        summary.append({key: value for key, value in row.items() if key != "CERTIFICATES"})
    maxima = {w: integer(object_row(classes[str(w)])["CLASS_MAX"]) for w in CLASS_WEDGES}
    batch_max = max(maxima.values())
    batch_owner_w = max(w for w, m in maxima.items() if m == batch_max)
    if len(chase.bounds) != START_LEDGER_COUNT + TOTAL_PROFILES:
        raise AssertionError("ledger lost or duplicated a profile")
    universe_after = ledger_universe_check(chase, census, LOW_W)
    frontier = frontier_below(chase, census)
    nxt = chase.cursor
    if nxt is None:
        raise AssertionError("missing cursor")
    r30.record_owner(chase)
    family, owners = nb.assert_family_agreement(chase)
    independent = max(resolved_max, batch_max, integer(chase.cursor_bound))
    if family != independent or family < INCUMBENT:
        raise AssertionError("family recompute disagreement")
    owner_ids = list(map(profile_id, owners))
    owner_type = "UNRESOLVED_CURSOR_COARSE_ENVELOPE" if owners[0] == nxt else "RESOLVED_LEDGER"
    competing = max((b for p, b in chase.bounds.items() if p not in owners), default=0)
    status = SUCCESS_A if family < START_BOUND else SUCCESS_B
    top_max = integer(unledgered["CLOSED_FORM_MAX"])
    top_owners = [text(item) for item in rows(unledgered["CLOSED_FORM_MAX_PROFILE_IDS"])]
    exposed = max(family, top_max)
    if top_max < family:
        exposed_owners = owner_ids
    elif top_max > family:
        exposed_owners = top_owners
    else:
        exposed_owners = [*owner_ids, *top_owners]
    all_origins: Counter[str] = Counter()
    for item in summary:
        for origin, count in object_row(item["CAP_ORIGIN_COUNTS"]).items():
            all_origins[origin] += integer(count)
    return {
        "TASK_ID": TASK_ID,
        "TASK_BRANCH": TASK_BRANCH,
        "WORKTREE_PATH": WORKTREE_PATH,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_STATUS": status,
        "NB_LEMMA_STATUS": "PROVED_CLOSED_FORM_REUSED_FROM_NB_R1",
        "ALL_T_CERTIFICATE_STATUS": "PASS_EXACT_RATIONAL_REDERIVATION_EVERY_T",
        "CERTIFICATE_PROVENANCE_STATUS": "PASS_CAPS_RECOMPUTED_NB_AND_R18_NO_PRIOR_CAP_USED",
        "START_FAMILY_BOUND": START_BOUND,
        "START_GAP": START_GAP,
        "START_LEDGER_COUNT": START_LEDGER_COUNT,
        "START_LEDGER_SHA256": START_LEDGER_SHA256,
        "START_CURSOR_PROFILE": START_CURSOR_ID,
        "CLASSES_PROCESSED": len(CLASS_WEDGES),
        "HIGHEST_CERTIFIED_W": HIGH_W,
        "LOWEST_CERTIFIED_W": LOW_W,
        "PROFILES_CERTIFIED": sum(integer(item["CERTIFIED_COUNT"]) for item in summary),
        "CAP_ORIGIN_COUNTS": dict(sorted(all_origins.items())),
        "BATCH_CLASS_MAX": batch_max,
        "BATCH_CLASS_MAX_W": batch_owner_w,
        "BATCH_CLASS_MAX_PROFILE_IDS": object_row(classes[str(batch_owner_w)])[
            "CLASS_MAX_PROFILE_IDS"
        ],
        "CLASS_SUMMARY": summary,
        "CERTIFICATE_COLUMNS": list(ROW_COLUMNS),
        "W_CLASSES": classes,
        "PRE_EXISTING_RESOLVED_MAX": resolved_max,
        "RESOLVED_LEDGER_MAX": max(chase.bounds.values()),
        "NEXT_FRONTIER_PROFILE": profile_id(nxt),
        "NEXT_FRONTIER_W": overlap_wedge_count(nxt),
        "NEXT_FRONTIER_SQUARE_SUM": w8.square_sum(nxt),
        "NEXT_FRONTIER_BOUND": chase.cursor_bound,
        "NEXT_FRONTIER_MATCHES_REFERENCE": chase.cursor_bound == NEXT_COARSE_REFERENCE,
        "FRONTIER_COVERAGE": frontier,
        "LEDGER_UNIVERSE_BEFORE": universe_before,
        "LEDGER_UNIVERSE_AFTER": universe_after,
        "UNLEDGERED_TOP_CROSS_CHECK": unledgered,
        "FAMILY_MAX_RECOMPUTATION": "PASS_FULL_LEDGER_AND_CURSOR",
        "FINAL_LEDGER_COUNT": len(chase.bounds),
        "FINAL_LEDGER_SHA256": r29.ledger_digest(chase),
        "FAMILY_UPPER_BOUND": family,
        "FINAL_FAMILY_UPPER_BOUND": family,
        "FINAL_OWNER_TYPE": owner_type,
        "FINAL_BOUND_OWNER_IDS": owner_ids,
        "FAMILY_BOUND_DEFINITION": "MAX_OVER_REPLAYED_LEDGER_AND_UNRESOLVED_CURSOR",
        "FAMILY_BOUND_CAVEAT": (
            "12 admissible W=835..837 profiles are outside the replayed ledger and the cursor; "
            "their closed-form NB/Route-B bounds are recorded in UNLEDGERED_TOP_CROSS_CHECK and "
            "are not installed"
        ),
        "FINAL_FAMILY_UPPER_BOUND_WITH_UNLEDGERED_TOP_CLOSED_FORM": exposed,
        "FINAL_BOUND_OWNER_IDS_WITH_UNLEDGERED_TOP_CLOSED_FORM": exposed_owners,
        "UNLEDGERED_TOP_EXPOSURE": exposed - family,
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
        "W808_RESULT_SHA256": W808_SHA256,
        "NB_RESULT_SHA256": w8.NB_SHA256,
    }


SUMMARY_KEYS = (
    "TASK_STATUS",
    "CLASSES_PROCESSED",
    "PROFILES_CERTIFIED",
    "BATCH_CLASS_MAX",
    "NEXT_FRONTIER_W",
    "NEXT_FRONTIER_BOUND",
    "RESOLVED_LEDGER_MAX",
    "FINAL_FAMILY_UPPER_BOUND",
    "FINAL_OWNER_TYPE",
    "REMAINING_GAP",
)


def result_path() -> Path:
    return r28.repo_root() / RESULT_DIRECTORY / RESULT_FILENAME


def render(value: object, level: int = 0) -> str:
    """Deterministic JSON: sorted keys, two-space indent, one line per scalar-only list."""

    pad = "  " * level
    if isinstance(value, Mapping):
        mapping = cast("Mapping[object, object]", value)
        if not mapping:
            return "{}"
        parts = [
            f"{pad}  {json.dumps(str(key))}: {render(item, level + 1)}"
            for key, item in sorted(mapping.items(), key=lambda pair: str(pair[0]))
        ]
        return "{\n" + ",\n".join(parts) + f"\n{pad}}}"
    if isinstance(value, (list, tuple)):
        items = list(cast("Sequence[object]", value))
        if all(not isinstance(item, (Mapping, list, tuple)) for item in items):
            return json.dumps(items)
        parts = [f"{pad}  {render(item, level + 1)}" for item in items]
        return "[\n" + ",\n".join(parts) + f"\n{pad}]"
    return json.dumps(value)


def write_result(result: Mapping[str, object]) -> str:
    payload = render(result) + "\n"
    if object_row(json.loads(payload)) != json.loads(json.dumps(result, sort_keys=True)):
        raise AssertionError("rendered result does not round-trip")
    target = result_path()
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, target)
    return hashlib.sha256(payload.encode()).hexdigest()


def replay_result(deadline: float | None = None) -> dict[str, object]:
    """Derive the batch twice from the sealed W=808 chain; the written bytes must match."""

    limit = monotonic() + REPLAY_SECONDS if deadline is None else deadline
    first_chase, first_authorities, _sealed = start_chase(limit)
    first = certify_batch(first_chase, first_authorities, limit)
    second_chase, second_authorities, _sealed = start_chase(limit)
    second = certify_batch(second_chase, second_authorities, limit)
    if not nb.same_result(first, second):
        raise AssertionError("W=807..786 replay diverged")
    digest = write_result(second)
    loaded = object_row(json.loads(result_path().read_text(encoding="utf-8")))
    if not nb.same_result(loaded, first):
        raise AssertionError("written W=807..786 result diverged from the replay")
    audit_sealed_result(loaded)
    if hashlib.sha256(result_path().read_bytes()).hexdigest() != digest:
        raise AssertionError("written W=807..786 result digest changed")
    return second


def main() -> None:
    result = replay_result()
    print(json.dumps({key: result[key] for key in SUMMARY_KEYS}), flush=True)


if __name__ == "__main__":
    main()
