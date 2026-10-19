"""Complete-universe coverage repair for the K20 minimum-S2 family bound (top-W12 R1).

Authority is the NB W=807..786 batch result committed at 9f7fe7c6, pinned by SHA-256.
Its zero-solve replay (R32, NB, W=808, then the batch) rebuilds the 4,635-row resolved
ledger of W=786..834 and leaves the cursor on the first W=785 profile at the coarse
313,394,584. The batch's family value 313,404,784 is a maximum over that ledger and the
cursor only. Twelve admissible profiles of W=835..837 lie in neither, so it is not a
complete family maximum. This module replays the batch, requires the replay to equal the
sealed JSON, and changes none of its rows.

Universe. Every non-increasing 20-tuple over 0..6 with sum 66 is enumerated with no screen
and no square-sum target: 5,126 raw histograms. Each is admissible or fails one of three
necessary conditions for a min-S2 portfolio, re-derived here as an explicit integer
inequality: R4's pair capacity (the k largest degrees force more ticket pairs inside the
k-set than C(k, 2)), R5's Erdos-Gallai test on the residual degrees 6 - d, and R8's
Erdos-Gallai test on the shadow degrees 2d. Each outcome must agree with the inherited
screen functions. The admissible set must equal the census enumerator's 4,844 profiles, and
R5's 4,850-profile ranking must be the census plus exactly the six shadow-obstructed
histograms. Each of those six has an earlier sealed closure (R5, R6, R8 or R10),
cross-referenced by result digest and row.

Partition. The admissible profiles are split by unique id using the replayed ledger's own
certificate sources: the R32/NB rows (W=810..834), the NB W=809 class, the W=808 class
and the W=807..786 batch classes. Next come the profiles whose coarse envelope the cursor
dominates (the W<=785 frontier), then the rest. Membership, disjointness and completeness
are checked against the raw universe. The rest is found by set difference, not assumed,
and must be exactly the twelve pinned W=835..837 ids. R6, R9 and R10 recorded every one of
them as realizable, so none can be dropped.

Certificates. Each of the twelve gets the batch's closed-form route: the NB cap (re-derived
independently), R18's class cap, their minimum, and Route B at every t in 22..cap with exact
integer floors and ceilings, re-derived in exact rationals. The whole envelope is stored.
No pinned R25/R30/R31/R32 row names one of them, so no earlier cap is borrowed. Their
R7/R9/R10 bounds are cross-referenced and not used. The twelve enter the ledger with every
previous row unchanged, and the family maximum is recomputed over the complete ledger and
the cursor. No solver, portfolio search or outcome enumeration is run.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from math import comb
from pathlib import Path
from time import monotonic
from types import ModuleType
from typing import cast

from . import b649_k20_min_s2_dangerous_core_realizability_r5 as r5
from . import b649_k20_min_s2_nb_w807_w786_batch_certificate_r1 as nbb
from . import b649_k20_min_s2_next_active_profile_exact_bound_r8 as r8
from . import b649_k20_min_s2_realizable_core_class_bound_r4 as r4
from .b649_k20_min_s2_next_active_profile_exact_bound_r8 import (
    INHERITED_FOURTH_ORDER_CREDIT,
    coarse_profile_envelope,
)
from .b649_k20_min_s2_realizable_core_class_bound_r4 import (
    K20_S1,
    K20_S2,
    K20_TICKET_CAPACITY,
    K20_TICKET_COUNT,
    K20_TRIPLE_INCIDENCE_COUNT,
    K20_TRIPLE_SUPPORT_COUNT,
    overlap_wedge_count,
)
from .b649_k20_min_s2_resolved_above_cursor_owner_chase_r20 import (
    Certificate,
    decode_profile,
    profile_id,
)

w8 = nbb.w8
nb = nbb.nb
r28 = nbb.r28
r29 = nbb.r29
r30 = nbb.r30
r31 = nbb.r31
r32 = nbb.r32
DegreeProfile = nbb.DegreeProfile
Chase = nbb.Chase
CapAuthorities = nbb.CapAuthorities
Term = w8.Term
Witness = tuple[int, int, int]

TASK_ID = "B649_K20_MIN_S2_TOPW12_COVERAGE_REPAIR_R1"
TASK_BRANCH = "codex/b649-k20-min-s2-topw12-coverage-repair-r1"
WORKTREE_PATH = "/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/" + TASK_ID
BASE_HEAD = "9f7fe7c6b714d06995a4c28012068afaf9b91b92"
BASE_TREE = "070b8ac9329c54b8dabc813e8e3f289d09e4c041"
BATCH_RESULT = nbb.RESULT_FILENAME
BATCH_SHA256 = "8f91947de1d9e97683c083a8cd33945d14cc49649aeaa1c4881cef934fa7b0d7"
PREVIOUS_REPORTED_BOUND = nbb.START_BOUND
LEDGER_COUNT = 4_635
LEDGER_SHA256 = "d7f3f1cb70e3f16f90210cd229e5178855d3e466ef595b4d0d15feebd5253e1f"
LEDGER_DEFINED_MAX = 313_404_784
LEDGER_DEFINED_OWNER_IDS = ["66665555554440000000", "66655555555530000000"]
CURSOR_ID = "66544333333333332222"
CURSOR_BOUND = 313_394_584
CURSOR_W = 785
INCUMBENT = nbb.INCUMBENT
LEDGER_TOP_W = nbb.LEDGER_TOP_W
TOP_CLASS_COUNTS: dict[int, int] = {837: 4, 836: 3, 835: 5}
TOP_COUNT = 12
TOP_IDS_SHA256 = nbb.UNLEDGERED_IDS_SHA256
PROVISIONAL_TOP_MAX = 313_476_764
PROVISIONAL_TOP_OWNER = "66665555555520000000"
RAW_COUNT = 5_126
ADMISSIBLE_COUNT = nbb.CENSUS_TOTAL
RANKED_COUNT = 4_850
MAX_SQUARE_SUM = nbb.MAX_SQUARE_SUM
SCREEN_PAIR = w8.SCREEN_PAIR_CAPACITY
SCREEN_RESIDUAL = w8.SCREEN_RESIDUAL
SCREEN_SHADOW = w8.SCREEN_SHADOW
SCREENS: tuple[str, ...] = (SCREEN_PAIR, SCREEN_RESIDUAL, SCREEN_SHADOW)
EXCLUDED_COUNTS: dict[str, int] = {SCREEN_PAIR: 276, SCREEN_RESIDUAL: 0, SCREEN_SHADOW: 6}
PART_LEDGER = "RESOLVED_LEDGER_R32_NB_W810_834"
PART_W809 = "NB_W809_CLASS"
PART_W808 = "NB_W808_CLASS"
PART_BATCH = "NB_BATCH_W807_786_CLASSES"
PART_FRONTIER = "UNRESOLVED_FRONTIER_UNDER_W785_CURSOR"
PART_TOP = "TOP_W835_837_COVERAGE_REPAIR"
PART_EXCLUDED = "EXCLUDED_BY_NECESSARY_CONDITION"
LEDGER_PARTS: dict[str, tuple[int, int, int, tuple[str, ...]]] = {
    PART_LEDGER: (1_795, 810, 834, (nb.RESULT_FILENAME, r32.RESULT_FILENAME)),
    PART_W809: (133, 809, 809, (nb.RESULT_FILENAME,)),
    PART_W808: (147, 808, 808, (w8.RESULT_FILENAME,)),
    PART_BATCH: (2_560, 786, 807, (nbb.RESULT_FILENAME,)),
}
OPEN_PARTS: dict[str, tuple[int, int, int]] = {
    PART_FRONTIER: (197, 774, 785),
    PART_TOP: (12, 835, 837),
}
PART_ORDER: tuple[str, ...] = (*LEDGER_PARTS, *OPEN_PARTS, PART_EXCLUDED)
EARLIER_RESULTS: dict[str, tuple[str, str]] = {
    "R5": (
        "b649-k20-min-s2-dangerous-core-realizability-r5-result.json",
        "7a2280455167bee462dc8a62b2684b13ef8dd592f363fc6f9bc4b0d0b01ef9c3",
    ),
    "R6": (
        "b649-k20-min-s2-top-envelope-realizability-r6-result.json",
        "990940c0fb09f699c03c41f45109e981e6637e2b35ac3aec1327b60f61208641",
    ),
    "R7": (
        "b649-k20-min-s2-top-realizable-motif-bound-r7-result.json",
        "3769a9a5e7b42660d01562e70f540897533a729d2b4763d8067bd4ed7cf691d3",
    ),
    "R8": (
        "b649-k20-min-s2-next-active-profile-exact-bound-r8-result.json",
        "13654859317c643dd04102b0b0b8adea91dbd6a3f3346fee189e59918e528f38",
    ),
    "R9": (
        "b649-k20-min-s2-top-plateau-closure-r9-result.json",
        "95bdaad6e8ae872a256cddbe0a953be51cc63e877286d0b7b092fce63156dee4",
    ),
    "R10": (
        "b649-k20-min-s2-next-distinct-plateau-r10-result.json",
        "65e307f5f16d6c2ab2666d316284bf5bf3afe93e492322e115e3f8e3aa5ecea9",
    ),
}
K4_LIGHT = nbb.K4_LIGHT
K4_HEAVY = nbb.K4_HEAVY
CAP_NB = nbb.CAP_NB
CAP_R18 = nbb.CAP_R18
CAP_TIE = nbb.CAP_TIE
ROUTE = "NB_DEGREE_CAP_ROUTE_B_ALL_T_TOP_W835_837"
PREMISES: tuple[str, ...] = (
    "MIN_S2_STRUCTURE",
    "PAIR_CAPACITY_PASSES",
    "RESIDUAL_DEGREES_GRAPHICAL",
    "SHADOW_DEGREES_GRAPHICAL",
    "GRAPHICAL_DEGREE_LIST",
    "NB_CAPACITY_RECOMPUTED",
    "NB_CAP_INDEPENDENTLY_DERIVED",
    "R18_CLASS_CAP",
    "K4_WEIGHTS_448_679",
    "S4_BASE_IS_PROFILE_FLOOR",
    "EXACT_RATIONAL_TERMS_AGREE",
)
TERM_COLUMNS: tuple[str, ...] = ("T", "BOUND", "K4_FLOOR", "CONTAINED_TRIPLE_K4", "S4_FLOOR", "S3")
EXCLUSION_COLUMNS: tuple[str, ...] = (
    "PROFILE_ID",
    "W",
    "SCREEN",
    "PREFIX_K",
    "LEFT_HAND_SIDE",
    "RIGHT_HAND_SIDE",
)
PROVENANCE_MODULES: tuple[ModuleType, ...] = (nbb, w8, nb, r32, r31, r30, r29, r28, r8, r5, r4)
REPLAY_SECONDS = 900.0
RESULT_DIRECTORY = nbb.RESULT_DIRECTORY
RESULT_FILENAME = "b649-k20-min-s2-topw12-coverage-repair-r1-result.json"
SUCCESS = "SUCCESS_COMPLETE_PROFILE_COVERAGE_FAMILY_BOUND_CORRECTED"
COVERAGE_COMPLETE = "COMPLETE"

object_row = r28.object_row
rows = r28.rows
integer = r28.integer
text = nb.text
git = w8.git


def ids_digest(profiles: Collection[DegreeProfile]) -> str:
    """SHA-256 of the JSON list of ids, in descending profile order."""

    ids = [profile_id(p) for p in sorted(profiles, reverse=True)]
    return hashlib.sha256(json.dumps(ids).encode()).hexdigest()


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


def sealed_blob(filename: str, digest: str) -> dict[str, object]:
    """A result at the base, by exact tree and pinned digest."""

    if git("rev-parse", f"{BASE_HEAD}^{{tree}}").decode().strip() != BASE_TREE:
        raise AssertionError("the base tree changed")
    blob = git("show", f"{BASE_HEAD}:{RESULT_DIRECTORY}/{filename}")
    if hashlib.sha256(blob).hexdigest() != digest:
        raise AssertionError(f"sealed fingerprint changed: {filename}")
    return object_row(json.loads(blob))


def batch_authority() -> dict[str, object]:
    """The W=807..786 batch result: pinned digest and the sealed ledger and frontier facts."""

    result = sealed_blob(BATCH_RESULT, BATCH_SHA256)
    expected: dict[str, object] = {
        "TASK_ID": nbb.TASK_ID,
        "TASK_STATUS": nbb.SUCCESS_A,
        "FINAL_FAMILY_UPPER_BOUND": LEDGER_DEFINED_MAX,
        "RESOLVED_LEDGER_MAX": LEDGER_DEFINED_MAX,
        "FINAL_BOUND_OWNER_IDS": LEDGER_DEFINED_OWNER_IDS,
        "FINAL_LEDGER_COUNT": LEDGER_COUNT,
        "FINAL_LEDGER_SHA256": LEDGER_SHA256,
        "NEXT_FRONTIER_PROFILE": CURSOR_ID,
        "NEXT_FRONTIER_BOUND": CURSOR_BOUND,
        "NEXT_FRONTIER_W": CURSOR_W,
        "START_FAMILY_BOUND": PREVIOUS_REPORTED_BOUND,
        "CURRENT_INCUMBENT": INCUMBENT,
        "FINAL_FAMILY_UPPER_BOUND_WITH_UNLEDGERED_TOP_CLOSED_FORM": PROVISIONAL_TOP_MAX,
    }
    for key, value in expected.items():
        if result.get(key) != value:
            raise AssertionError(f"batch authority mismatch: {key}")
    top = object_row(result["UNLEDGERED_TOP_CROSS_CHECK"])
    if (
        top.get("PROFILE_COUNT") != TOP_COUNT
        or top.get("PROFILE_IDS_SHA256") != TOP_IDS_SHA256
        or top.get("CLOSED_FORM_MAX") != PROVISIONAL_TOP_MAX
    ):
        raise AssertionError("batch authority mismatch: unledgered top cross-check")
    return result


def predecessor_top_bounds(batch: Mapping[str, object]) -> dict[str, int]:
    """The batch's informational closed-form bounds for the twelve, keyed by id."""

    top = object_row(batch["UNLEDGERED_TOP_CROSS_CHECK"])
    return {
        key: integer(value)
        for key, value in object_row(top["CLOSED_FORM_NB_ROUTE_B_BOUNDS"]).items()
    }


def start_chase(deadline: float) -> tuple[Chase, CapAuthorities, dict[str, object]]:
    """Replay R32 -> NB -> W=808 -> batch with zero solves; it must equal the sealed batch."""

    sealed = batch_authority()
    chase, authorities, _w808 = nbb.start_chase(deadline)
    replayed = nbb.certify_batch(chase, authorities, deadline)
    if not nb.same_result(replayed, sealed):
        raise AssertionError("batch replay diverged from the sealed batch result")
    family, owners = r28.family_state(chase)
    if (
        family != LEDGER_DEFINED_MAX
        or list(map(profile_id, owners)) != LEDGER_DEFINED_OWNER_IDS
        or (chase.cursor, chase.cursor_bound) != (decode_profile(CURSOR_ID), CURSOR_BOUND)
        or len(chase.bounds) != LEDGER_COUNT
        or r29.ledger_digest(chase) != LEDGER_SHA256
    ):
        raise AssertionError("batch cursor, owner or complete-ledger reconstruction failed")
    return chase, authorities, sealed


def erdos_gallai_witness(degrees: Sequence[int]) -> Witness | None:
    """First k with (sum of the k largest) > k(k - 1) + sum over the rest of min(d, k)."""

    ordered = sorted(degrees, reverse=True)
    if any(type(d) is not int or d < 0 for d in ordered) or sum(ordered) % 2:
        raise AssertionError("Erdos-Gallai needs non-negative integers with an even sum")
    for k in range(1, len(ordered) + 1):
        left = sum(ordered[:k])
        right = k * (k - 1) + sum(min(d, k) for d in ordered[k:])
        if left > right:
            return k, left, right
    return None


def pair_capacity_witness(profile: DegreeProfile) -> Witness | None:
    """First k whose k largest degrees force more than C(k, 2) ticket pairs inside the k-set.

    A triple support meets the k-set in x of 0..3 tickets and covers C(x, 2) of its pairs.
    Pair overlaps of at most one make those pairs distinct across supports. The x sum to
    the incidence count, so by convexity the sum of C(x, 2) is least when the x are as equal
    as possible over the 22 supports.
    """

    ordered = sorted(profile, reverse=True)
    for k in range(1, len(ordered) + 1):
        incidences = sum(ordered[:k])
        quotient, remainder = divmod(incidences, K20_TRIPLE_SUPPORT_COUNT)
        if quotient > 3 or (quotient == 3 and remainder):
            raise AssertionError("incidences exceed three per triple support")
        least = (K20_TRIPLE_SUPPORT_COUNT - remainder) * comb(quotient, 2) + remainder * comb(
            quotient + 1, 2
        )
        if least > comb(k, 2):
            return k, least, comb(k, 2)
    return None


def screen_results(profile: DegreeProfile) -> dict[str, Witness | None]:
    """All three necessary conditions, re-derived here and checked against their sources."""

    if r32.structural_failures(profile):
        raise AssertionError("histogram is not a 20-ticket, sum-66 degree sequence")
    pair = pair_capacity_witness(profile)
    residual = erdos_gallai_witness([K20_TICKET_CAPACITY - d for d in profile])
    shadow = erdos_gallai_witness([2 * d for d in profile])
    if (pair is None) != r4.linear_triple_degree_sequence_passes_pair_capacity(
        profile, K20_TRIPLE_SUPPORT_COUNT
    ):
        raise AssertionError("pair-capacity witness disagrees with R4")
    residual_ok = r5.simple_graph_degree_sequence_is_graphical(
        r5.residual_double_ticket_degrees(profile)
    )
    if (residual is None) != residual_ok:
        raise AssertionError("residual Erdos-Gallai witness disagrees with R5")
    inherited = r8.profile_shadow_obstruction(profile)
    expected = (
        None
        if inherited is None
        else (inherited.prefix_size, inherited.left_hand_side, inherited.right_hand_side)
    )
    if shadow != expected:
        raise AssertionError("shadow Erdos-Gallai witness disagrees with R8")
    return {SCREEN_PAIR: pair, SCREEN_RESIDUAL: residual, SCREEN_SHADOW: shadow}


def first_failure(results: Mapping[str, Witness | None]) -> tuple[str, Witness] | None:
    """The first failing screen in the census order, with its witness."""

    for screen in SCREENS:
        witness = results[screen]
        if witness is not None:
            return screen, witness
    return None


def raw_universe() -> tuple[DegreeProfile, ...]:
    """Every non-increasing 20-tuple over 0..6 with sum 66: no screen, no square-sum target."""

    found: list[DegreeProfile] = []

    def visit(prefix: list[int], top: int, remaining: int) -> None:
        slots = K20_TICKET_COUNT - len(prefix)
        if slots == 0:
            if remaining == 0:
                found.append(tuple(prefix))
            return
        if remaining > slots * top:
            return
        for d in range(min(top, remaining), -1, -1):
            prefix.append(d)
            visit(prefix, d, remaining - d)
            prefix.pop()

    visit([], K20_TICKET_CAPACITY, K20_TRIPLE_INCIDENCE_COUNT)
    ordered = tuple(sorted(found, reverse=True))
    if len(set(ordered)) != len(ordered):
        raise AssertionError("raw histogram enumeration duplicated a profile")
    return ordered


class Universe:
    """The raw histograms, their admissible part, the exclusions and the census by W."""

    def __init__(
        self,
        raw: tuple[DegreeProfile, ...],
        admissible: tuple[DegreeProfile, ...],
        exclusions: dict[DegreeProfile, tuple[str, Witness]],
        census: dict[int, tuple[DegreeProfile, ...]],
    ) -> None:
        self.raw = raw
        self.admissible = admissible
        self.exclusions = exclusions
        self.census = census

    def band(self, low: int, high: int) -> set[DegreeProfile]:
        return {p for p in self.admissible if low <= overlap_wedge_count(p) <= high}

    def excluded_by(self, screen: str) -> frozenset[DegreeProfile]:
        return frozenset(p for p, (name, _w) in self.exclusions.items() if name == screen)


def build_universe() -> Universe:
    """Screen every raw histogram; the admissible set must be the census enumerator's."""

    raw = raw_universe()
    if len(raw) != RAW_COUNT:
        raise AssertionError("raw histogram count changed")
    squares = {w8.square_sum(p) for p in raw}
    if (
        min(squares) != w8.minimum_square_sum()
        or max(squares) != MAX_SQUARE_SUM
        or any(s % 2 for s in squares)
    ):
        raise AssertionError("raw square sums leave the census level range")
    admissible: list[DegreeProfile] = []
    exclusions: dict[DegreeProfile, tuple[str, Witness]] = {}
    for profile in raw:
        failure = first_failure(screen_results(profile))
        if (None if failure is None else failure[0]) != w8.admissibility_screen(profile):
            raise AssertionError("first failing screen disagrees with the census screen order")
        if failure is None:
            admissible.append(profile)
        else:
            exclusions[profile] = failure
    counts = Counter(screen for screen, _witness in exclusions.values())
    if {screen: counts.get(screen, 0) for screen in SCREENS} != EXCLUDED_COUNTS:
        raise AssertionError("exclusion counts by screen changed")
    census = nbb.census_by_wedges()
    listed = [p for members in census.values() for p in members]
    if len(listed) != len(set(listed)) or set(listed) != set(admissible):
        raise AssertionError("admissible histograms differ from the census enumerator")
    if len(admissible) != ADMISSIBLE_COUNT:
        raise AssertionError("admissible census size changed")
    return Universe(raw, tuple(admissible), exclusions, census)


def exclusion_rows(universe: Universe) -> list[list[object]]:
    """One row per excluded histogram: its first failing screen and the exact inequality."""

    out: list[list[object]] = []
    for profile in sorted(universe.exclusions, reverse=True):
        screen, (k, left, right) = universe.exclusions[profile]
        if left <= right:
            raise AssertionError("exclusion witness is not a strict violation")
        out.append([profile_id(profile), overlap_wedge_count(profile), screen, k, left, right])
    return out


def universe_summary(universe: Universe) -> dict[str, object]:
    walls = sorted(universe.census)
    return {
        "RAW_HISTOGRAM_COUNT": len(universe.raw),
        "RAW_IDS_SHA256": ids_digest(universe.raw),
        "SQUARE_SUM_RANGE": [w8.minimum_square_sum(), MAX_SQUARE_SUM],
        "ADMISSIBLE_COUNT": len(universe.admissible),
        "ADMISSIBLE_IDS_SHA256": ids_digest(universe.admissible),
        "ADMISSIBLE_W_RANGE": [walls[0], walls[-1]],
        "EXCLUDED_COUNT": len(universe.exclusions),
        "EXCLUDED_BY_SCREEN": dict(EXCLUDED_COUNTS),
        "SCREEN_ORDER": list(SCREENS),
        "SCREENS_RE_DERIVED_AND_AGREE_WITH_R4_R5_R8": True,
        "CENSUS_ENUMERATOR_AGREES": True,
    }


def ranking_reconciliation(
    universe: Universe, earlier: Mapping[str, Mapping[str, object]]
) -> dict[str, object]:
    """R5's 4,850-profile ranking is the census plus exactly the six shadow exclusions."""

    ranked = [envelope.degree_sequence for envelope in r5.rank_dangerous_profiles()]
    shadow = universe.excluded_by(SCREEN_SHADOW)
    if len(ranked) != RANKED_COUNT or len(set(ranked)) != len(ranked):
        raise AssertionError("R5 ranking size changed")
    if set(ranked) != set(universe.admissible) | shadow:
        raise AssertionError("R5 ranking is not the census plus the shadow exclusions")
    if set(ranked) & (universe.excluded_by(SCREEN_PAIR) | universe.excluded_by(SCREEN_RESIDUAL)):
        raise AssertionError("R5 ranking contains a pair or residual exclusion")
    counts = object_row(earlier["R5"]["PROFILE_COUNTS"])
    expected = {
        "TOTAL_BOUNDED_PROFILES": len(universe.raw),
        "PAIR_CAPACITY_COMPATIBLE_PROFILES": len(universe.raw) - EXCLUDED_COUNTS[SCREEN_PAIR],
        "RESIDUAL_DOUBLE_DEGREE_GRAPHICAL_PROFILES": RANKED_COUNT,
        "DANGEROUS_PROFILES": RANKED_COUNT,
    }
    if counts != expected:
        raise AssertionError("sealed R5 profile counts disagree with the raw universe")
    return {
        "STATUS": "PASS",
        "R5_RANKED_COUNT": len(ranked),
        "R5_RANKED_MINUS_ADMISSIBLE": [profile_id(p) for p in sorted(shadow, reverse=True)],
        "R5_SEALED_PROFILE_COUNTS": dict(counts),
    }


def earlier_results() -> dict[str, dict[str, object]]:
    return {label: sealed_blob(name, digest) for label, (name, digest) in EARLIER_RESULTS.items()}


def _witness(row: Mapping[str, object], keys: tuple[str, str, str]) -> Witness:
    return integer(row[keys[0]]), integer(row[keys[1]]), integer(row[keys[2]])


def earlier_exclusion_authority(
    universe: Universe, earlier: Mapping[str, Mapping[str, object]]
) -> dict[str, object]:
    """Each shadow exclusion has exactly one earlier sealed closure; its witness must match."""

    shadow = {p: universe.exclusions[p][1] for p in universe.excluded_by(SCREEN_SHADOW)}
    found: dict[DegreeProfile, dict[str, object]] = {}

    def claim(raw: object, label: str, locator: str, method: str, witness: Witness | None) -> None:
        profile = decode_profile(raw)
        if profile not in shadow:
            raise AssertionError(f"{label} closure is not a shadow-obstructed histogram")
        if profile in found:
            raise AssertionError("an exclusion has two earlier closures")
        if witness is not None and witness != shadow[profile]:
            raise AssertionError(f"{label} Erdos-Gallai witness differs from the re-derived one")
        found[profile] = {
            "RESULT": EARLIER_RESULTS[label][0],
            "RESULT_SHA256": EARLIER_RESULTS[label][1],
            "LOCATOR": f"{label}:{locator}",
            "METHOD": method,
            "EARLIER_WITNESS_CHECKED": witness is not None,
        }

    for index, raw in enumerate(rows(earlier["R5"]["CLOSED_DANGEROUS_PROFILES"])):
        claim(raw, "R5", f"CLOSED_DANGEROUS_PROFILES[{index}]", "LOCAL_INCIDENCE", None)
    for index, raw in enumerate(rows(earlier["R6"]["TOP_PROFILE_RESOLUTIONS"])):
        row = object_row(raw)
        if row.get("STATUS") == "UNREALIZABLE":
            keys = ("ERDOS_GALLAI_PREFIX_K", "LEFT_HAND_SIDE", "RIGHT_HAND_SIDE")
            witness = _witness(object_row(row["OBSTRUCTION"]), keys)
            locator = f"TOP_PROFILE_RESOLUTIONS[{index}]"
            claim(row["DEGREE_PROFILE"], "R6", locator, "SHADOW_ERDOS_GALLAI", witness)
    r8_result = earlier["R8"]
    if r8_result.get("ACTIVE_PROFILE_BOUND") != "ELIMINATED_UNREALIZABLE":
        raise AssertionError("R8 no longer eliminates its active profile")
    certificate = object_row(r8_result["REALIZABILITY_CERTIFICATE"])
    keys = ("PREFIX_K", "LEFT_HAND_SIDE", "RIGHT_HAND_SIDE")
    witness = _witness(object_row(certificate["ERDOS_GALLAI_VIOLATION"]), keys)
    claim(r8_result["ACTIVE_PROFILE"], "R8", "ACTIVE_PROFILE", "SHADOW_ERDOS_GALLAI", witness)
    for index, raw in enumerate(rows(earlier["R10"]["PROFILE_BOUNDS"])):
        row = object_row(raw)
        if row.get("REALIZABILITY") == "UNREALIZABLE":
            keys = ("prefix_size", "left_hand_side", "right_hand_side")
            witness = _witness(object_row(row["SHADOW_OBSTRUCTION"]), keys)
            locator = f"PROFILE_BOUNDS[{index}]"
            claim(row["PROFILE"], "R10", locator, "SHADOW_ERDOS_GALLAI", witness)
    if set(found) != set(shadow):
        raise AssertionError("a shadow exclusion has no earlier sealed closure")
    return {
        "STATUS": "PASS",
        "EXCLUSION_CERTIFICATE": "EACH_ROW_CARRIES_ITS_RE_DERIVED_STRICT_INEQUALITY",
        "PAIR_CAPACITY": {
            "COUNT": EXCLUDED_COUNTS[SCREEN_PAIR],
            "LEMMA": "R4 linear_triple_degree_sequence_passes_pair_capacity",
            "EARLIER_AGGREGATE": "R5:PROFILE_COUNTS 5126 - 4850",
        },
        "RESIDUAL_GRAPHICAL": {"COUNT": EXCLUDED_COUNTS[SCREEN_RESIDUAL]},
        "SHADOW_ERDOS_GALLAI": {profile_id(p): found[p] for p in sorted(found, reverse=True)},
    }


def partition(chase: Chase, universe: Universe) -> dict[str, frozenset[DegreeProfile]]:
    """Split the raw universe by unique id; the uncovered rest is found by set difference."""

    if set(chase.bounds) != set(chase.catalog):
        raise AssertionError("certificate catalog and family ledger diverged")
    if not set(chase.bounds) <= set(universe.admissible):
        raise AssertionError("a ledger row is outside the admissible universe")
    parts: dict[str, set[DegreeProfile]] = {name: set() for name in PART_ORDER}
    for profile, certificate in chase.catalog.items():
        wedges = overlap_wedge_count(profile)
        homes = [
            name
            for name, (_count, low, high, sources) in LEDGER_PARTS.items()
            if low <= wedges <= high and certificate.source_result in sources
        ]
        if len(homes) != 1:
            raise AssertionError(f"ledger row {profile_id(profile)} has no unique source part")
        parts[homes[0]].add(profile)
    cursor, bound = chase.cursor, chase.cursor_bound
    if cursor is None or bound is None or cursor in chase.bounds:
        raise AssertionError("missing unresolved cursor")
    for profile in universe.admissible:
        if profile in chase.bounds:
            continue
        dominated = coarse_profile_envelope(profile).family_upper_bound <= bound
        if dominated and overlap_wedge_count(profile) <= overlap_wedge_count(cursor):
            parts[PART_FRONTIER].add(profile)
        else:
            parts[PART_TOP].add(profile)
    parts[PART_EXCLUDED] = set(universe.exclusions)
    if cursor not in parts[PART_FRONTIER]:
        raise AssertionError("the cursor is not in its own frontier")
    if sum(map(len, parts.values())) != len(universe.raw) or set[DegreeProfile]().union(
        *parts.values()
    ) != set(universe.raw):
        raise AssertionError("partition is not disjoint and complete over the raw universe")
    for name, (count, low, high, _sources) in LEDGER_PARTS.items():
        if len(parts[name]) != count or parts[name] != universe.band(low, high):
            raise AssertionError(f"{name} is not the whole admissible band W={low}..{high}")
    for name, (count, low, high) in OPEN_PARTS.items():
        if len(parts[name]) != count or parts[name] != universe.band(low, high):
            raise AssertionError(f"{name} is not the whole admissible band W={low}..{high}")
    return {name: frozenset(members) for name, members in parts.items()}


def partition_summary(
    chase: Chase, parts: Mapping[str, frozenset[DegreeProfile]]
) -> dict[str, object]:
    out: dict[str, object] = {}
    for name in PART_ORDER:
        members = parts[name]
        walls = sorted(overlap_wedge_count(p) for p in members)
        row: dict[str, object] = {
            "COUNT": len(members),
            "W_RANGE": [walls[0], walls[-1]],
            "IDS_SHA256": ids_digest(members),
        }
        if name in LEDGER_PARTS:
            sources = Counter(chase.catalog[p].source_result for p in members)
            row["SOURCE_RESULTS"] = dict(sorted(sources.items()))
        out[name] = row
    return out


def top_ids_in_batch_order(universe: Universe) -> list[str]:
    """The twelve in the batch's census order: W ascending, each class descending."""

    return [profile_id(p) for w in sorted(TOP_CLASS_COUNTS) for p in universe.census[w]]


def top_history(
    top: Collection[DegreeProfile], earlier: Mapping[str, Mapping[str, object]]
) -> dict[str, object]:
    """R6, R9 and R10 recorded each of the twelve as realizable; old bounds are not used."""

    found: dict[DegreeProfile, dict[str, object]] = {}

    def note(raw: object, realized: str, bounded: str, bound: int) -> None:
        profile = decode_profile(raw)
        if profile not in top or profile in found:
            raise AssertionError("historical realizable row is not a distinct top profile")
        found[profile] = {
            "REALIZABILITY": "REALIZABLE",
            "REALIZABILITY_LOCATOR": realized,
            "HISTORICAL_BOUND_LOCATOR": bounded,
            "HISTORICAL_PROFILE_BOUND": bound,
            "USED_FOR_FAMILY_BOUND": False,
        }

    r7_rows = [object_row(raw) for raw in rows(earlier["R7"]["PROFILE_BOUNDS"])]
    r7_index = {decode_profile(row["DEGREE_PROFILE"]): i for i, row in enumerate(r7_rows)}
    for index, raw in enumerate(rows(earlier["R6"]["TOP_PROFILE_RESOLUTIONS"])):
        row = object_row(raw)
        if row.get("STATUS") == "REALIZABLE":
            j = r7_index[decode_profile(row["DEGREE_PROFILE"])]
            bound = integer(r7_rows[j]["PROFILE_FAMILY_UPPER_BOUND"])
            realized = f"R6:TOP_PROFILE_RESOLUTIONS[{index}]"
            note(row["DEGREE_PROFILE"], realized, f"R7:PROFILE_BOUNDS[{j}]", bound)
    for label in ("R9", "R10"):
        for index, raw in enumerate(rows(earlier[label]["PROFILE_BOUNDS"])):
            row = object_row(raw)
            if row.get("REALIZABILITY") == "REALIZABLE":
                locator = f"{label}:PROFILE_BOUNDS[{index}]"
                note(row["PROFILE"], locator, locator, integer(row["FAMILY_UPPER_BOUND"]))
    if set(found) != set(top):
        raise AssertionError("historical realizable rows are not exactly the twelve")
    return {profile_id(p): found[p] for p in sorted(found, reverse=True)}


def top_certificate(profile: DegreeProfile, predecessor_bound: int) -> dict[str, object]:
    """Premises, NB and R18 caps, and the exact all-t Route-B envelope of one top profile."""

    wedges = overlap_wedge_count(profile)
    if wedges not in TOP_CLASS_COUNTS or wedges <= LEDGER_TOP_W:
        raise AssertionError("profile is outside the W=835..837 band")
    if first_failure(screen_results(profile)) is not None or w8.admissibility_screen(profile):
        raise AssertionError("top profile fails a necessary condition")
    if r30.k4_quartet_weights() != r32.K4_WEIGHTS or r32.K4_WEIGHTS != {
        r32.WITH_TRIPLE: K4_LIGHT,
        r32.WITHOUT_TRIPLE: K4_HEAVY,
    }:
        raise AssertionError("K4 quartet weights changed")
    profile_wedges, floor, nb_cap = nb.profile_nb_cap(profile)
    if profile_wedges != wedges or 2 * wedges != nb.WEDGE_OFFSET + w8.square_sum(profile):
        raise AssertionError("wedge identity W = (1326 + sum d^2) / 2 failed")
    if (profile_wedges, floor, nb_cap) != nbb.exact_nb_cap(profile):
        raise AssertionError("NB cap disagrees with the independent derivation")
    nb.assert_nb_capacity(nb.profile_degrees(profile))
    class_cap = nb.r18_cap(profile)
    cap = nb.combined_triangle_cap(nb_cap, class_cap)
    if cap != min(nb_cap, class_cap):
        raise AssertionError("triangle cap is not the strongest verified cap")
    origin = CAP_NB if nb_cap < class_cap else CAP_R18 if class_cap < nb_cap else CAP_TIE
    a_max = r32.contained_triple_k4_cap(profile)
    outside = sum(d * (K20_TICKET_CAPACITY + d - 2) for d in profile)
    if a_max != outside // 3:
        raise AssertionError("A_max is not floor(sum d (g - 2) / 3)")
    base = r28.profile_s4_floor(profile)
    terms = r32.route_b_envelope(profile, cap, base)
    if [term[0] for term in terms] != list(range(K20_TRIPLE_SUPPORT_COUNT, cap + 1)):
        raise AssertionError("Route-B envelope does not cover every t in 22..cap")
    exact = w8.exact_route_b_terms(profile, cap, base)
    if terms != exact:
        raise AssertionError("Route-B integer rounding disagrees with the exact re-derivation")
    bound, s3, argmax, increasing = nb.profile_route_b(profile, cap)
    best = max(exact, key=lambda term: (term[1], term[0]))
    if (bound, s3, argmax) != (best[1], best[5], best[0]) or bound != max(t[1] for t in exact):
        raise AssertionError("all-t maximum disagrees with the envelope")
    if bound != predecessor_bound:
        raise AssertionError("bound differs from the batch's closed-form cross-check")
    coarse = coarse_profile_envelope(profile)
    if (
        coarse.fourth_order_credit != INHERITED_FOURTH_ORDER_CREDIT
        or coarse.family_upper_bound != nbb.coarse_at(wedges)
        or bound > coarse.family_upper_bound
    ):
        raise AssertionError("Route B exceeds the coarse envelope")
    return {
        "PROFILE_ID": profile_id(profile),
        "W": wedges,
        "SQUARE_SUM": w8.square_sum(profile),
        "GRAPH_DEGREES": list(nb.profile_degrees(profile)),
        "STRUCTURAL_SCREENS": dict.fromkeys(SCREENS, "PASS"),
        "NB_OPEN_WEDGE_FLOOR": floor,
        "NB_TRIANGLE_CAP": nb_cap,
        "R18_TRIANGLE_CAP": class_cap,
        "PRIOR_CERTIFIED_CAP": None,
        "TRIANGLE_CAP": cap,
        "CAP_ORIGIN": origin,
        "A_MAX": a_max,
        "S4_BASE": base,
        "T_RANGE": [K20_TRIPLE_SUPPORT_COUNT, cap],
        "TERM_COUNT": len(exact),
        "ENVELOPE_STRICTLY_INCREASING_IN_T": increasing,
        "ARGMAX_TRIANGLES": best[0],
        "K4_FLOOR_AT_ARGMAX": best[2],
        "CONTAINED_TRIPLE_K4_AT_ARGMAX": best[3],
        "S4_FLOOR_AT_ARGMAX": best[4],
        "S3_AT_ARGMAX": best[5],
        "ALL_T_MAX_BOUND": bound,
        "ALL_T_TERMS": [list(term) for term in exact],
        "COARSE_FAMILY_UPPER_BOUND": coarse.family_upper_bound,
        "PREDECESSOR_CLOSED_FORM_BOUND": predecessor_bound,
        "PREMISES": list(PREMISES),
        "ROUTE": ROUTE,
    }


def audit_top_certificate(stored: Mapping[str, object], predecessor: Mapping[str, int]) -> None:
    """A stored certificate must equal a fresh exact re-derivation, field by field."""

    identity = text(stored.get("PROFILE_ID"))
    if identity not in predecessor:
        raise AssertionError("certificate names a profile outside the twelve")
    expected = top_certificate(decode_profile(identity), predecessor[identity])
    differing = sorted(k for k in set(expected) | set(stored) if stored.get(k) != expected.get(k))
    if differing:
        raise AssertionError(
            "top certificate differs from its exact re-derivation: " + ",".join(differing)
        )


def previous_rows_digest(chase: Chase, previous: Collection[DegreeProfile]) -> str:
    """R29's ledger digest restricted to the previous rows."""

    serialized = [
        {"PROFILE_ID": profile_id(p), "CURRENT_BOUND": chase.bounds[p]}
        for p in sorted(previous, reverse=True)
    ]
    return hashlib.sha256(json.dumps(serialized, sort_keys=True).encode()).hexdigest()


def install_top(chase: Chase, certificates: Sequence[Mapping[str, object]]) -> None:
    """Enter the twelve; every previous ledger row and certificate stays as it was."""

    bounds = dict(chase.bounds)
    catalog = dict(chase.catalog)
    for index, row in enumerate(certificates):
        profile = decode_profile(text(row["PROFILE_ID"]))
        if profile in chase.bounds or profile == chase.cursor:
            raise AssertionError("top profile collides with the ledger or the cursor")
        bound = integer(row["ALL_T_MAX_BOUND"])
        chase.bounds[profile] = bound
        chase.catalog[profile] = Certificate(
            profile,
            bound,
            RESULT_FILENAME,
            f"TOP_W_CERTIFICATES[{index}]",
            "CLASS_ENVELOPE_ONLY",
            integer(row["S3_AT_ARGMAX"]),
            integer(row["S4_BASE"]),
            integer(row["TRIANGLE_CAP"]),
            ROUTE,
        )
    if len(chase.bounds) != len(bounds) + len(certificates) or any(
        chase.bounds[p] != b or chase.catalog[p] is not catalog[p] for p, b in bounds.items()
    ):
        raise AssertionError("a previous ledger row changed")
    if previous_rows_digest(chase, bounds) != LEDGER_SHA256:
        raise AssertionError("previous ledger rows no longer reproduce the sealed digest")


def coverage_after(
    chase: Chase, universe: Universe, parts: Mapping[str, frozenset[DegreeProfile]]
) -> dict[str, object]:
    """Every admissible profile is a ledger row or dominated by the cursor; nothing else."""

    ledgered = set[DegreeProfile]().union(*(parts[name] for name in LEDGER_PARTS))
    if set(chase.bounds) != ledgered | parts[PART_TOP]:
        raise AssertionError("ledger is not exactly the previous rows plus the twelve")
    low = min(part[1] for part in LEDGER_PARTS.values())
    if set(chase.bounds) != universe.band(low, OPEN_PARTS[PART_TOP][2]):
        raise AssertionError("ledger is not exactly the admissible band W=786..837")
    cursor, bound = chase.cursor, chase.cursor_bound
    if cursor is None or bound is None:
        raise AssertionError("missing unresolved cursor")
    for profile in parts[PART_FRONTIER]:
        if profile in chase.bounds or coarse_profile_envelope(profile).family_upper_bound > bound:
            raise AssertionError("a frontier profile is not dominated by the cursor")
    covered = set(chase.bounds) | parts[PART_FRONTIER]
    uncovered = set(universe.admissible) - covered
    if uncovered or covered - set(universe.admissible):
        raise AssertionError("an admissible profile is uncovered")
    return {
        "STATUS": "PASS",
        "CANONICAL_PROFILE_UNIVERSE_COUNT": len(universe.admissible),
        "COVERED_PROFILE_COUNT": len(covered),
        "UNCOVERED_PROFILE_COUNT": len(uncovered),
        "LEDGERED_PROFILE_COUNT": len(chase.bounds),
        "LEDGER_W_RANGE": [
            min(map(overlap_wedge_count, chase.bounds)),
            max(map(overlap_wedge_count, chase.bounds)),
        ],
        "UNDER_CURSOR_PROFILE_COUNT": len(parts[PART_FRONTIER]),
        "EXCLUDED_HISTOGRAM_COUNT": len(universe.exclusions),
    }


def family_owners(
    terms: Mapping[str, int], cursor_id: str, cursor_bound: int
) -> tuple[int, list[str]]:
    """Maximum over resolved terms and the cursor, with every owner in ledger order."""

    family = max([*terms.values(), cursor_bound])
    owners = sorted((i for i, b in terms.items() if b == family), reverse=True)
    return family, [cursor_id, *owners] if cursor_bound == family else owners


def certify_coverage(
    chase: Chase, authorities: CapAuthorities, batch: Mapping[str, object]
) -> dict[str, object]:
    """Partition the universe, certify the twelve, install them, recompute the family."""

    provenance = module_provenance()
    primitives = r28.canonical_primitive_preflight()
    if primitives["STATUS"] != "PASS" or primitives.get("K20_S1") != K20_S1:
        raise AssertionError("canonical primitive gate failed")
    witness = w8.witness_nb_soundness(authorities.witness)
    family_before, owners_before = r28.family_state(chase)
    if (
        family_before != LEDGER_DEFINED_MAX
        or list(map(profile_id, owners_before)) != LEDGER_DEFINED_OWNER_IDS
        or len(chase.bounds) != LEDGER_COUNT
        or r29.ledger_digest(chase) != LEDGER_SHA256
        or (chase.cursor, chase.cursor_bound) != (decode_profile(CURSOR_ID), CURSOR_BOUND)
    ):
        raise AssertionError("the ledger or cursor moved before the coverage repair")
    universe = build_universe()
    earlier = earlier_results()
    ranking = ranking_reconciliation(universe, earlier)
    exclusions = earlier_exclusion_authority(universe, earlier)
    parts = partition(chase, universe)
    before = partition_summary(chase, parts)
    top = sorted(parts[PART_TOP], reverse=True)
    batch_order = top_ids_in_batch_order(universe)
    digest = hashlib.sha256(json.dumps(batch_order).encode()).hexdigest()
    if len(top) != TOP_COUNT or digest != TOP_IDS_SHA256:
        raise AssertionError("set difference is not exactly the twelve pinned profiles")
    if Counter(overlap_wedge_count(p) for p in top) != Counter(TOP_CLASS_COUNTS):
        raise AssertionError("top class sizes changed")
    history = top_history(parts[PART_TOP], earlier)
    scan = w8.prior_cap_scan(chase, authorities, top)
    predecessor = predecessor_top_bounds(batch)
    if set(predecessor) != {profile_id(p) for p in top}:
        raise AssertionError("batch cross-check does not name exactly the twelve")
    certificates = [top_certificate(p, predecessor[profile_id(p)]) for p in top]
    top_bounds = {text(c["PROFILE_ID"]): integer(c["ALL_T_MAX_BOUND"]) for c in certificates}
    top_max = max(top_bounds.values())
    top_owners = [i for i, b in top_bounds.items() if b == top_max]
    class_maxima = {
        str(w): max(integer(c["ALL_T_MAX_BOUND"]) for c in certificates if c["W"] == w)
        for w in sorted(TOP_CLASS_COUNTS, reverse=True)
    }
    previous = frozenset(chase.bounds)
    install_top(chase, certificates)
    coverage = coverage_after(chase, universe, parts)
    frontier = nbb.frontier_below(chase, universe.census)
    family, owners = nb.assert_family_agreement(chase)
    owner_ids = list(map(profile_id, owners))
    resolved = {profile_id(p): b for p, b in chase.bounds.items()}
    independent = family_owners(resolved, CURSOR_ID, CURSOR_BOUND)
    if (family, owner_ids) != independent or family != max(
        LEDGER_DEFINED_MAX, top_max, CURSOR_BOUND
    ):
        raise AssertionError("family recompute disagreement")
    if family < INCUMBENT or family > PREVIOUS_REPORTED_BOUND:
        raise AssertionError("family bound left the [incumbent, previous report] interval")
    if chase.cursor in owners:
        raise AssertionError("cursor unexpectedly owns the corrected family bound")
    competing = max([b for p, b in chase.bounds.items() if p not in owners] + [CURSOR_BOUND])
    origins = Counter(text(c["CAP_ORIGIN"]) for c in certificates)
    return {
        "TASK_ID": TASK_ID,
        "TASK_BRANCH": TASK_BRANCH,
        "WORKTREE_PATH": WORKTREE_PATH,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_STATUS": SUCCESS,
        "BATCH_RESULT": BATCH_RESULT,
        "BATCH_RESULT_SHA256": BATCH_SHA256,
        "BATCH_REPLAY": "PASS_EQUALS_SEALED_BATCH_RESULT",
        "PREVIOUS_REPORTED_FAMILY_BOUND": PREVIOUS_REPORTED_BOUND,
        "LEDGER_DEFINED_MAX": LEDGER_DEFINED_MAX,
        "LEDGER_DEFINED_OWNER_IDS": LEDGER_DEFINED_OWNER_IDS,
        "START_LEDGER_COUNT": LEDGER_COUNT,
        "START_LEDGER_SHA256": LEDGER_SHA256,
        "CANONICAL_PROFILE_UNIVERSE": universe_summary(universe),
        "CANONICAL_PROFILE_UNIVERSE_COUNT": len(universe.admissible),
        "R5_RANKING_RECONCILIATION": ranking,
        "EXCLUSION_COLUMNS": list(EXCLUSION_COLUMNS),
        "EXCLUSIONS": exclusion_rows(universe),
        "EARLIER_EXCLUSION_AUTHORITY": exclusions,
        "PROFILE_PARTITION_BEFORE_REPAIR": before,
        "PARTITION_STATUS": "PASS_UNIQUE_IDS_DISJOINT_COMPLETE_OVER_RAW_UNIVERSE",
        "SET_DIFFERENCE_BEFORE_REPAIR": [profile_id(p) for p in top],
        "MISSING_TOP_W_PROFILE_COUNT": len(top),
        "MISSING_TOP_W_IDS_IN_BATCH_ORDER": batch_order,
        "MISSING_TOP_W_IDS_SHA256": digest,
        "TOP_W_HISTORY": history,
        "TOP_W_PRIOR_CAP_SCAN": scan,
        "ALL_T_TERM_COLUMNS": list(TERM_COLUMNS),
        "TOP_W_CERTIFICATES": certificates,
        "TOP_W_CAP_ORIGIN_COUNTS": dict(sorted(origins.items())),
        "TOP_W_CLASS_MAXIMA": class_maxima,
        "MISSING_TOP_W_CERTIFIED_COUNT": len(certificates),
        "MISSING_TOP_W_MAX": top_max,
        "MISSING_TOP_W_MAX_PROFILE_IDS": top_owners,
        "PREVIOUS_LEDGER_ROWS_UNCHANGED": True,
        "PREVIOUS_LEDGER_ROWS_SHA256": previous_rows_digest(chase, previous),
        "FRONTIER_COVERAGE": frontier,
        "COVERAGE_AFTER_REPAIR": coverage,
        "COVERED_PROFILE_COUNT": coverage["COVERED_PROFILE_COUNT"],
        "UNCOVERED_PROFILE_COUNT": coverage["UNCOVERED_PROFILE_COUNT"],
        "PROFILE_COVERAGE_STATUS": COVERAGE_COMPLETE,
        "FINAL_LEDGER_COUNT": len(chase.bounds),
        "FINAL_LEDGER_SHA256": r29.ledger_digest(chase),
        "FAMILY_TERMS": {
            "RESOLVED_LEDGER_W786_834": LEDGER_DEFINED_MAX,
            "TOP_W835_837": top_max,
            "UNRESOLVED_CURSOR_W785_COARSE": CURSOR_BOUND,
            "EXCLUDED_HISTOGRAMS": "NO_PORTFOLIO_REALIZES_AN_EXCLUDED_HISTOGRAM",
        },
        "FAMILY_MAX_RECOMPUTATION": "PASS_COMPLETE_LEDGER_AND_CURSOR",
        "FAMILY_BOUND_DEFINITION": "MAX_OVER_COMPLETE_ADMISSIBLE_UNIVERSE",
        "FINAL_COMPLETE_FAMILY_UPPER_BOUND": family,
        "FINAL_BOUND_OWNER_IDS": owner_ids,
        "FINAL_OWNER_TYPE": "RESOLVED_LEDGER_TOP_W_CERTIFICATE",
        "NEXT_COMPETING_BOUND": competing,
        "PREVIOUS_REPORTED_BOUND_REMAINS_VALID": family <= PREVIOUS_REPORTED_BOUND,
        "LEDGER_DEFINED_MAX_IS_COMPLETE_FAMILY_MAX": family <= LEDGER_DEFINED_MAX,
        "CURRENT_INCUMBENT": INCUMBENT,
        "REMAINING_GAP": family - INCUMBENT,
        "ALL_T_CERTIFICATE_STATUS": "PASS_EXACT_RATIONAL_REDERIVATION_EVERY_T_STORED",
        "NB_LEMMA_STATUS": "PROVED_CLOSED_FORM_REUSED_FROM_NB_R1",
        "CANONICAL_PRIMITIVE_STATUS": primitives["STATUS"],
        "CANONICAL_PRIMITIVES": primitives,
        "WITNESS_SOUNDNESS_STATUS": witness["STATUS"],
        "WITNESS_NB_SOUNDNESS": witness,
        "MODULE_PROVENANCE": provenance,
        "S1": K20_S1,
        "S2": K20_S2,
        "BOUND_RULE": nbb.BOUND_RULE,
        "SOLVER_CALLS": 0,
        "OUTCOME_ENUMERATIONS": 0,
        "NEW_HEAVY_SOLVER_STARTED": "NO",
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


def audit_sealed_result(
    result: Mapping[str, object], batch: Mapping[str, object]
) -> dict[str, object]:
    """Re-derive the universe, the partition bands, the twelve and the family from scratch."""

    universe = build_universe()
    stored = [list(cast("list[object]", row)) for row in rows(result["EXCLUSIONS"])]
    if stored != exclusion_rows(universe):
        raise AssertionError("sealed exclusion rows differ from the re-derived universe")
    summary = object_row(result["PROFILE_PARTITION_BEFORE_REPAIR"])
    bands = {name: part[1:3] for name, part in LEDGER_PARTS.items()} | {
        name: part[1:] for name, part in OPEN_PARTS.items()
    }
    for name, (low, high) in bands.items():
        members = universe.band(low, high)
        row = object_row(summary[name])
        if row.get("COUNT") != len(members) or row.get("IDS_SHA256") != ids_digest(members):
            raise AssertionError(f"sealed partition part {name} is wrong")
    excluded = object_row(summary[PART_EXCLUDED])
    if excluded.get("IDS_SHA256") != ids_digest(universe.exclusions):
        raise AssertionError("sealed exclusion part is wrong")
    if sum(integer(object_row(summary[name])["COUNT"]) for name in PART_ORDER) != RAW_COUNT:
        raise AssertionError("sealed partition does not cover the raw universe")
    top = universe.band(*OPEN_PARTS[PART_TOP][1:])
    certificates = [object_row(raw) for raw in rows(result["TOP_W_CERTIFICATES"])]
    identities = [text(c.get("PROFILE_ID")) for c in certificates]
    if identities != [profile_id(p) for p in sorted(top, reverse=True)]:
        raise AssertionError("sealed top certificates are not exactly the twelve")
    predecessor = predecessor_top_bounds(batch)
    for certificate in certificates:
        audit_top_certificate(certificate, predecessor)
    ledger_max = integer(batch["RESOLVED_LEDGER_MAX"])
    cursor_bound = integer(batch["NEXT_FRONTIER_BOUND"])
    terms = {text(c["PROFILE_ID"]): integer(c["ALL_T_MAX_BOUND"]) for c in certificates}
    ledger_owners = [text(i) for i in rows(batch["FINAL_BOUND_OWNER_IDS"])]
    terms |= dict.fromkeys(ledger_owners, ledger_max)
    family, owners = family_owners(terms, text(batch["NEXT_FRONTIER_PROFILE"]), cursor_bound)
    top_max = max(integer(c["ALL_T_MAX_BOUND"]) for c in certificates)
    if (
        result.get("FINAL_COMPLETE_FAMILY_UPPER_BOUND") != family
        or result.get("FINAL_BOUND_OWNER_IDS") != owners
        or result.get("MISSING_TOP_W_MAX") != top_max
        or result.get("MISSING_TOP_W_CERTIFIED_COUNT") != len(top)
        or result.get("REMAINING_GAP") != family - INCUMBENT
        or result.get("CANONICAL_PROFILE_UNIVERSE_COUNT") != len(universe.admissible)
        or result.get("UNCOVERED_PROFILE_COUNT") != 0
        or result.get("COVERED_PROFILE_COUNT") != len(universe.admissible)
    ):
        raise AssertionError("sealed family or coverage totals are wrong")
    return {"STATUS": "PASS", "TOP_ROWS_AUDITED": len(certificates), "FAMILY": family}


SUMMARY_KEYS = (
    "TASK_STATUS",
    "CANONICAL_PROFILE_UNIVERSE_COUNT",
    "COVERED_PROFILE_COUNT",
    "UNCOVERED_PROFILE_COUNT",
    "MISSING_TOP_W_CERTIFIED_COUNT",
    "MISSING_TOP_W_MAX",
    "LEDGER_DEFINED_MAX",
    "FINAL_COMPLETE_FAMILY_UPPER_BOUND",
    "FINAL_BOUND_OWNER_IDS",
    "REMAINING_GAP",
)


def result_path() -> Path:
    return r28.repo_root() / RESULT_DIRECTORY / RESULT_FILENAME


def write_result(result: Mapping[str, object]) -> str:
    payload = nbb.render(result) + "\n"
    if object_row(json.loads(payload)) != json.loads(json.dumps(result, sort_keys=True)):
        raise AssertionError("rendered result does not round-trip")
    target = result_path()
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(target)
    return hashlib.sha256(payload.encode()).hexdigest()


def replay_result(deadline: float | None = None) -> dict[str, object]:
    """Derive the repair twice from the sealed batch chain; the written bytes must match."""

    limit = monotonic() + REPLAY_SECONDS if deadline is None else deadline
    first_chase, first_authorities, batch = start_chase(limit)
    first = certify_coverage(first_chase, first_authorities, batch)
    second_chase, second_authorities, batch = start_chase(limit)
    second = certify_coverage(second_chase, second_authorities, batch)
    if not nb.same_result(first, second):
        raise AssertionError("coverage repair replay diverged")
    digest = write_result(second)
    loaded = object_row(json.loads(result_path().read_text(encoding="utf-8")))
    if not nb.same_result(loaded, first):
        raise AssertionError("written coverage repair diverged from the replay")
    audit_sealed_result(loaded, batch)
    if hashlib.sha256(result_path().read_bytes()).hexdigest() != digest:
        raise AssertionError("written coverage repair digest changed")
    return second


def main() -> None:
    result = replay_result()
    print(json.dumps({key: result[key] for key in SUMMARY_KEYS}), flush=True)


if __name__ == "__main__":
    main()
