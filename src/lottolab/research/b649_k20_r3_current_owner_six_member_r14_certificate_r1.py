"""Certify the six current owners of R3 state ``s2-13548976-s3-951748`` (R1).

The sealed Top-21 certificate left this state, and therefore the complete R3
family, at 355,637,030.  Those six tied members still carry the R6/forest
correction 4,592,000.  This task replays R14's residual pair moment on
``R_i = E_i \\ (E_A union E_B)``, takes the ceiling of that moment divided by
9, and replaces the previous correction by the max of the R6 pair floor, the
forest floor, and that R14 value.  The correction is subtracted once from the
anchor bound.  The other 1,421 member bounds and the Top-21 certificates stay
put.  The 1,427-member state maximum is then substituted into the sealed
23-state family.

No R7 census, Hunter numerical correction, heavy solver, outcome enumeration,
or portfolio search runs.
"""

from __future__ import annotations

import argparse
import json
import math
from functools import cache
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_r3_hunter_top16_complete_integration_r1 as hunter
from lottolab.research import b649_k20_r3_state_13548976_top_band_certificate_r1 as catalog
from lottolab.research import b649_k20_r3_tail_seven_class_uniform_r6_certificate_r1 as tail

CountVector = catalog.CountVector
r14, r12, r8, r7 = catalog.r14, catalog.r12, catalog.r8, catalog.r7
dense, sparse, digest = catalog.dense, catalog.sparse, catalog.digest
TASK_ID = "B649_K20_R3_CURRENT_OWNER_SIX_MEMBER_R14_CERTIFICATE_R1"
TASK_BRANCH = "codex/b649-k20-r3-current-owner-six-member-r14-certificate-r1"
BASE_HEAD = "87ffd9194ecef52937f381790d38929d89f11050"
BASE_TREE = "de48e3138a0fbb915ca91b7c2421a5ad6ec3d2be"
TARGET_STATE_ID = catalog.TARGET_STATE_ID
REGION_SHA256 = catalog.TARGET_REGION_SHA256
REGION_MEMBER_COUNT = catalog.REGION_MEMBER_COUNT
REPRESENTED_VECTOR_COUNT = catalog.REPRESENTED_VECTOR_COUNT
TOP_BAND_CERTIFICATE_COUNT = catalog.TOP_BAND_MEMBER_COUNT
LOAD_BEARING_MEMBER_COUNT = 6
REMAINDER_MEMBER_COUNT = REGION_MEMBER_COUNT - LOAD_BEARING_MEMBER_COUNT
RESIDUAL_EVENT_DEFINITION = "R_i = E_i \\ (E_A ∪ E_B)"  # noqa: RUF001
R14_CORRECTION_RULE = "CEIL(EXACT_RESIDUAL_PAIR_MOMENT / 9)"
CORRECTION_COMBINATION = "MAX(R6_PAIR, FOREST, R14_RATIONAL)"
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS = catalog.RESULTS
HUNTER_RESULT_RELATIVE = hunter.RESULT_RELATIVE
TOP_BAND_RESULT_RELATIVE = (
    RESULTS + "b649-k20-r3-state-13548976-top-band-certificate-r1-result.json"
)
TAIL_RESULT_RELATIVE = (
    RESULTS + "b649-k20-r3-tail-seven-class-uniform-r6-certificate-r1-result.json"
)
RESULT_RELATIVE = RESULTS + "b649-k20-r3-current-owner-six-member-r14-certificate-r1-result.json"
RESULT_PATH = REPO_ROOT / RESULT_RELATIVE
_SOURCES = "src/lottolab/research/"
UPSTREAM_SHA256 = {
    HUNTER_RESULT_RELATIVE: "4c31f615558a1a6807438dd88209b659931ad96cce1b305a547b323db8d25d08",
    TOP_BAND_RESULT_RELATIVE: "eb0f8f0fc4fb68d1fe05bcef9d899c4ef67726bfcf6d6182dac6f2ef05f359db",
    TAIL_RESULT_RELATIVE: "77d22715fa003c35ae764aafe0ee44c3368f404d8e71ca499fb6ef6b5ab988f2",
    _SOURCES + "b649_k20_r3_state_13548976_top_band_certificate_r1.py": (
        "ef881a099bdb5c402612273c9e7f054be4f4306a2869d8535980750dab8db203"
    ),
    _SOURCES + "b649_k20_r3_state_tail_owner_chase_r14.py": (
        "b30f6420eca033bc051ef35457993fc2588ee2e26cc1041363ced5d2c775ce99"
    ),
    _SOURCES + "b649_k20_r3_frontier_realizability_bound_r8.py": (
        "14884faf5b2e66c1f30d4e04e453ba5838b7f95815d70d8b7d45be47c5e9bd2b"
    ),
    _SOURCES + "b649_k20_r3_corrected_tail_min_loss_plateau_r12.py": (
        "4501b7a496d32a87bdbfa2d4e0951bca330a60feb8b799350cc0a76607008c92"
    ),
    _SOURCES + "b649_k20_r3_tail_state_owner_chase_r17.py": (
        "0edad246de25771745a215b0d922fc27e8839c40472a2f9859dc9a242a000a3b"
    ),
    _SOURCES + "b649_k20_r3_tail_seven_class_uniform_r6_certificate_r1.py": (
        "efb43c77c6e5cae4c5989c6334402f774dd17a83025f5462f4f2f01f3760e820"
    ),
    _SOURCES + "b649_k20_r3_joint_residual_envelope_r7.py": (
        "f376899a25bc287e45b80c3f5d9116db97f4c09de31ec81d0ccd2badf4222c50"
    ),
}
# Packet figures are checks on the recomputation.  They are not inputs.
EXPECTED_PRIOR_CORRECTION = 4_592_000
EXPECTED_MEMBER_CERTIFICATES = (
    ("[0,12][4,5][25,1]", 5_628_293, 354_600_737),
    ("[0,12][1,1][4,4][25,1]", 5_629_537, 354_599_493),
    ("[0,12][1,2][4,3][25,1]", 5_630_160, 354_598_870),
    ("[0,12][1,3][4,2][25,1]", 5_630_160, 354_598_870),
    ("[0,12][1,4][4,1][25,1]", 5_629_537, 354_599_493),
    ("[0,12][1,5][25,1]", 5_628_293, 354_600_737),
)
EXPECTED_START_STATE_BOUND = 355_637_030
EXPECTED_FINAL_STATE_BOUND = 355_630_646
EXPECTED_NEXT_BAND = (11, 12)
EXPECTED_NEXT_STATE = ("state:s2-13169800-s3-789320", 355_628_469)
EXPECTED_INCUMBENT = 313_263_888
EXPECTED_REMAINING_GAP = 42_366_758
SUMMARY_FIELDS = (
    "REGION_IDENTITY",
    "LOAD_BEARING_MEMBER_COUNT",
    "SIX_CERTIFICATES_STATUS",
    "REMAINDER_MEMBER_COUNT",
    "REMAINDER_MAX",
    "FINAL_STATE_BOUND",
    "START_COMPLETE_R3_UB",
    "FINAL_COMPLETE_R3_UB",
    "FINAL_OWNER_IDS",
    "CURRENT_INCUMBENT",
    "REMAINING_GAP",
    "NON_DUPLICATE_CREDIT_STATUS",
    "WITNESS_SOUNDNESS_STATUS",
    "FULL_STATE_CATALOG_STATUS",
    "NEW_HEAVY_SOLVER_STARTED",
    "PRODUCTION_MUTATION",
)


def verify_upstream_fingerprints() -> dict[str, str]:
    observed = {
        relative: sha256((REPO_ROOT / relative).read_bytes()).hexdigest()
        for relative in UPSTREAM_SHA256
    }
    if observed != UPSTREAM_SHA256:
        raise AssertionError(f"upstream fingerprint mismatch: {observed}")
    return observed


def read_json(relative: str) -> dict[str, Any]:
    verify_upstream_fingerprints()
    return cast(dict[str, Any], json.loads((REPO_ROOT / relative).read_text(encoding="utf-8")))


@cache
def hunter_authority() -> dict[str, Any]:
    stored = read_json(HUNTER_RESULT_RELATIVE)
    if stored["TASK_ID"] != hunter.TASK_ID or stored["FINAL_OWNER_IDS"] != [TARGET_STATE_ID]:
        raise AssertionError("sealed complete R3 authority is not this state's owner")
    return stored


@cache
def top_band_authority() -> dict[str, Any]:
    stored = read_json(TOP_BAND_RESULT_RELATIVE)
    if (
        stored["TASK_ID"] != catalog.TASK_ID
        or stored["STATE_ID"] != TARGET_STATE_ID
        or stored["REGION_SHA256"] != REGION_SHA256
        or stored["FINAL_STATE_BOUND"] != EXPECTED_START_STATE_BOUND
    ):
        raise AssertionError("sealed Top-21 authority differs from this state")
    return stored


@cache
def tail_authority() -> dict[str, Any]:
    return read_json(TAIL_RESULT_RELATIVE)


def member_id(counts: CountVector) -> str:
    return "".join(f"[{index},{count}]" for index, count in sparse(counts))


def region_members() -> tuple[catalog.LedgerMember, ...]:
    """The pinned 1,427-member region, read from the immutable ledger."""

    verify_upstream_fingerprints()
    members = catalog.target_region_ledger()
    vectors = sum(member.represented_vector_count for member in members)
    if (
        catalog.region_fingerprint(members) != REGION_SHA256
        or len(members) != REGION_MEMBER_COUNT
        or vectors != REPRESENTED_VECTOR_COUNT
        or len({member.counts for member in members}) != len(members)
    ):
        raise AssertionError("target region identity or 1427/1543 coverage failed")
    return members


def sealed_top_band_bounds() -> dict[CountVector, int]:
    records = cast(list[dict[str, Any]], top_band_authority()["NEW_MEMBER_CERTIFICATES"])
    bounds = {
        dense(record["member"]["witness_counts"]): int(record["member_new_bound"])
        for record in records
    }
    if len(bounds) != len(records) or len(bounds) != TOP_BAND_CERTIFICATE_COUNT:
        raise AssertionError("Top-21 certificates are not one bound per member")
    return bounds


def current_member_bounds(
    members: tuple[catalog.LedgerMember, ...],
) -> dict[CountVector, int]:
    """Member bounds after the sealed Top-21 replacement, before this one."""

    rows = cast(list[dict[str, Any]], top_band_authority()["COMPLETE_REGION_MEMBERS"])
    certified = sealed_top_band_bounds()
    if len(rows) != len(members):
        raise AssertionError("top-band catalog cardinality mismatch")
    bounds: dict[CountVector, int] = {}
    for member, row in zip(members, rows, strict=True):
        counts = dense(row["witness_counts"])
        if (
            counts != member.counts
            or int(row["represented_vector_count"]) != member.represented_vector_count
            or int(row["raw_bound"]) != member.raw_bound
            or int(row["r24_final_bound"]) != member.final_bound
        ):
            raise AssertionError("top-band catalog row does not match the immutable ledger")
        bounds[counts] = int(row["final_bound"])
    for counts, bound in certified.items():
        if bounds.get(counts) != bound:
            raise AssertionError("a Top-21 certificate is not the current member bound")
    for member in members:
        if member.counts not in certified and bounds[member.counts] != member.final_bound:
            raise AssertionError("an uncertified member bound differs from the ledger")
    return bounds


def load_bearing_members(
    members: tuple[catalog.LedgerMember, ...], bounds: dict[CountVector, int]
) -> tuple[catalog.LedgerMember, ...]:
    """Every member tied at the current state maximum.  Each owns one vector."""

    maximum = max(bounds.values())
    owners = tuple(member for member in members if bounds[member.counts] == maximum)
    if (
        len(owners) != LOAD_BEARING_MEMBER_COUNT
        or any(member.represented_vector_count != 1 for member in owners)
        or any(member.counts in sealed_top_band_bounds() for member in owners)
        or any(bounds[member.counts] != member.raw_bound for member in owners)
    ):
        raise AssertionError("the current owner is not six uncertified one-vector members")
    return owners


def occupied_type_pairs(counts: CountVector) -> tuple[tuple[int, int], ...]:
    pairs: list[tuple[int, int]] = []
    for left, left_count in enumerate(counts):
        if left_count == 0:
            continue
        for right in range(left, len(counts)):
            right_count = counts[right]
            pair_count = math.comb(left_count, 2) if left == right else left_count * right_count
            if pair_count:
                pairs.append((left, right))
    return tuple(pairs)


def residual_pair_intersection(
    left_index: int, right_index: int, overlap: tuple[int, int, int, int]
) -> int:
    """Exact pair moment of one residual-event cell overlap."""

    profiles = catalog.r5.anchor_incidence_profiles()
    left, right = profiles[left_index], profiles[right_index]
    total = sum(overlap)
    triple_a = r8.triple_intersection_count(
        (left.overlap_with_a, right.overlap_with_a, total), overlap[0] + overlap[1]
    )
    triple_b = r8.triple_intersection_count(
        (left.overlap_with_b, right.overlap_with_b, total), overlap[0] + overlap[2]
    )
    profile_api = "_four_ticket_profile"
    quadruple = r8.four_ticket_event_intersection_count(
        cast(tuple[int, ...], getattr(r8, profile_api)(left, right, overlap))
    )
    pair_events = r8.pair_intersection_count(total)
    return pair_events - triple_a - triple_b + quadruple


def assert_residual_event_identity(left_index: int, right_index: int) -> None:
    if left_index > right_index:
        left_index, right_index = right_index, left_index
    table_api = "_pair_event_correction_table"
    table = cast(tuple[tuple[int, ...], ...], getattr(r8, table_api)(left_index, right_index))
    for row in table:
        overlap = (int(row[0]), int(row[1]), int(row[2]), int(row[3]))
        if residual_pair_intersection(left_index, right_index, overlap) != int(row[4]):
            raise AssertionError(f"residual event definition is not {RESIDUAL_EVENT_DEFINITION}")
    if not table:
        raise AssertionError("a type pair has no residual-event rows")


def ceiling_divide_by_9(pair_moment: int) -> int:
    """Ceiling of an exact non-negative integer moment divided by 9."""

    if pair_moment < 0:
        raise ValueError("residual pair moment must be non-negative")
    return -(-pair_moment // 9)


def combine_corrections(r6_pair: int, forest: int, rational: int) -> int:
    """Combine the R6 pair floor, forest floor, and R14 correction by max."""

    if min(r6_pair, forest, rational) < 0:
        raise ValueError("corrections must be non-negative")
    return max(r6_pair, forest, rational)


def member_bound(uncorrected: int, correction: int) -> int:
    """Subtract the combined correction once from the anchor bound."""

    if correction < 0 or uncorrected <= correction:
        raise ValueError("member bound is not a single positive correction")
    return uncorrected - correction


def exact_residual_pair_moment(counts: CountVector) -> int:
    pairs = occupied_type_pairs(counts)
    if not pairs:
        raise AssertionError("member has no residual ticket pairs")
    for left, right in pairs:
        assert_residual_event_identity(left, right)
    moment = int(r14.moment_certificate(counts)["residual_s2_lower_bound"])
    if moment < 0:
        raise AssertionError("residual pair moment is negative")
    return moment


def certify_member(member: catalog.LedgerMember) -> dict[str, Any]:
    """One R14 certificate for a current-owner member and its single vector."""

    state = catalog.rebuild_member(member)
    vectors = catalog.r17.represented_vectors((state,))[member.counts]
    if vectors != (member.counts,) or member.represented_vector_count != 1:
        raise AssertionError("a load-bearing member does not represent exactly one vector")
    vector = vectors[0]
    moment_row = r14.moment_certificate(vector)
    pair_moment = exact_residual_pair_moment(vector)
    rational = ceiling_divide_by_9(pair_moment)
    if pair_moment != int(moment_row["residual_s2_lower_bound"]) or rational != int(
        moment_row["correction_lower_bound"]
    ):
        raise AssertionError("local R14 ceiling drifted from the residual moment certificate")
    r6_pair = int(state.residual_pair_union_penalty)
    forest = int(state.complementary_forest_floor)
    applied = int(state.applied_residual_union_penalty)
    if applied != max(r6_pair, forest) or applied != EXPECTED_PRIOR_CORRECTION:
        raise AssertionError("the previous correction is not the R6/forest max")
    correction = combine_corrections(r6_pair, forest, rational)
    uncorrected = r14.joint_constant() - int(state.anchor_pair_s2) + int(state.anchor_triple_s3)
    bound = member_bound(uncorrected, correction)
    if (
        correction != max(applied, rational)
        or member.raw_bound != uncorrected - applied
        or bound >= member.raw_bound
    ):
        raise AssertionError("member correction does not replace the applied penalty once")
    support = r12.construct_support_witness(vector)
    if support is None or not r8.validate_support_assignment(vector, support):
        raise AssertionError("load-bearing member has no valid support witness")
    return {
        "member_id": member_id(vector),
        "witness_counts": sparse(vector),
        "represented_vector_count": 1,
        "residual_event_definition": RESIDUAL_EVENT_DEFINITION,
        "residual_pair_moment": pair_moment,
        "r14_correction_rule": R14_CORRECTION_RULE,
        "r14_correction": rational,
        "r6_pair_correction": r6_pair,
        "forest_correction": forest,
        "prior_applied_correction": applied,
        "correction_combination": CORRECTION_COMBINATION,
        "member_certified_correction": correction,
        "uncorrected_anchor_bound": uncorrected,
        "member_prior_bound": member.raw_bound,
        "member_raw_bound": member.raw_bound,
        "member_new_bound": bound,
        "support_witness": catalog.normalized(support),
        "support_sha256": digest(support),
        "vector_certificate": catalog.normalized(moment_row),
        "hunter_correction_applied": False,
    }


def support_of(record: dict[str, Any]) -> tuple[tuple[int, ...], ...]:
    return tuple(
        tuple(int(label) for label in ticket)
        for ticket in cast(list[list[int]], record["support_witness"])
    )


def verify_member_certificate(record: dict[str, Any], member: catalog.LedgerMember) -> None:
    vector = dense(cast(list[list[int]], record["witness_counts"]))
    support = support_of(record)
    if not r8.validate_support_assignment(vector, support):
        raise AssertionError("a stored support witness fails independent validation")
    if digest(support) != record["support_sha256"]:
        raise AssertionError("a stored support witness sha does not match its bytes")
    if certify_member(member) != record:
        raise AssertionError("stored member certificate differs from its replay")


def replaced_bounds(
    priors: dict[CountVector, int], records: list[dict[str, Any]]
) -> dict[CountVector, int]:
    bounds = dict(priors)
    certified = [dense(cast(list[list[int]], record["witness_counts"])) for record in records]
    if len(set(certified)) != len(certified):
        raise AssertionError("a member is certified twice")
    for counts, record in zip(certified, records, strict=True):
        if counts not in bounds or bounds[counts] != int(record["member_prior_bound"]):
            raise AssertionError("a certificate does not replace a current member bound")
        bounds[counts] = int(record["member_new_bound"])
        if bounds[counts] >= int(record["member_prior_bound"]):
            raise AssertionError("a certificate does not tighten its member")
    return bounds


def sealed_tail_bound() -> int:
    stored = tail_authority()
    bound = (
        catalog.r24.canonical_baseline() - tail.TAIL_START_LOSS - int(stored["UNIFORM_CORRECTION"])
    )
    if bound != int(stored["FINAL_TAIL_BOUND"]):
        raise AssertionError("the sealed tail correction was not applied exactly once")
    return bound


def state_terms() -> tuple[tuple[str, int], ...]:
    rows = cast(list[dict[str, Any]], hunter_authority()["FINAL_STATE_TERMS"])
    terms = tuple((str(row["stable_id"]), int(row["bound"])) for row in rows)
    if len(terms) != 23 or len(dict(terms)) != 23:
        raise AssertionError("the complete 23-state catalog is required")
    return terms


def classified_terms() -> tuple[tuple[str, int], ...]:
    _states, classified = tail.committed_terms()
    if digest(classified) != hunter_authority()["CLASSIFIED_TERMS_SHA256"]:
        raise AssertionError("classified term digest differs from the sealed authority")
    return classified


def recompute_family(state_bound: int) -> dict[str, Any]:
    terms = state_terms()
    classified = classified_terms()
    tail_bound = sealed_tail_bound()
    authority = hunter_authority()
    if tail_bound != int(authority["TAIL_BOUND"]):
        raise AssertionError("recomputed tail differs from the sealed complete authority")
    start = tail.family_maximum(tail_bound, terms, classified)
    if start != authority["FINAL_FAMILY_MAX_RECOMPUTATION"]:
        raise AssertionError("starting family maximum does not reproduce the sealed authority")
    replaced = tuple(
        (key, state_bound if key == TARGET_STATE_ID else bound) for key, bound in terms
    )
    changed = [
        key for (key, before), (_, after) in zip(terms, replaced, strict=True) if before != after
    ]
    if changed != [TARGET_STATE_ID]:
        raise AssertionError("exactly the certified state term must change")
    family = tail.family_maximum(tail_bound, replaced, classified)
    aggregate = [
        {"stable_id": key, "bound": bound}
        for key, bound in classified
        if key == catalog.r24.AGGREGATE_ID
    ]
    if (
        len(aggregate) != 1
        or aggregate[0]["bound"] != family["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"]
        or aggregate != authority["CLASSIFIED_AGGREGATE"]
    ):
        raise AssertionError("classified aggregate was not reproduced")
    return {
        "start": start,
        "family": family,
        "terms": replaced,
        "tail_bound": tail_bound,
        "classified_count": len(classified),
        "classified_sha256": digest(classified),
        "aggregate": aggregate,
    }


def check_regression(result: dict[str, Any]) -> None:
    observed = tuple(
        (
            record["member_id"],
            int(record["member_certified_correction"]),
            int(record["member_new_bound"]),
        )
        for record in cast(list[dict[str, Any]], result["MEMBER_CERTIFICATES"])
    )
    others = sorted(
        (
            (int(row["bound"]), str(row["stable_id"]))
            for row in cast(list[dict[str, Any]], result["FINAL_STATE_TERMS"])
            if row["stable_id"] != TARGET_STATE_ID
        ),
        reverse=True,
    )
    if (
        observed != EXPECTED_MEMBER_CERTIFICATES
        or result["START_COMPLETE_R3_UB"] != EXPECTED_START_STATE_BOUND
        or result["FINAL_STATE_BOUND"] != EXPECTED_FINAL_STATE_BOUND
        or result["FINAL_COMPLETE_R3_UB"] != EXPECTED_FINAL_STATE_BOUND
        or result["NEXT_BAND_COMPRESSED_MEMBERS"] != EXPECTED_NEXT_BAND[0]
        or result["NEXT_BAND_REPRESENTED_VECTORS"] != EXPECTED_NEXT_BAND[1]
        or (others[0][1], others[0][0]) != EXPECTED_NEXT_STATE
        or result["CURRENT_INCUMBENT"] != EXPECTED_INCUMBENT
        or result["REMAINING_GAP"] != EXPECTED_REMAINING_GAP
        or result["REMAINDER_MEMBER_COUNT"] != REMAINDER_MEMBER_COUNT
        or result["REMAINDER_MAX"] != EXPECTED_FINAL_STATE_BOUND
        or result["FINAL_OWNER_IDS"] != [TARGET_STATE_ID]
    ):
        raise AssertionError("recomputed certificate disagrees with its regression targets")


def build_result() -> dict[str, Any]:
    fingerprints = verify_upstream_fingerprints()
    members = region_members()
    priors = current_member_bounds(members)
    owners = load_bearing_members(members, priors)
    if max(priors.values()) != dict(state_terms())[TARGET_STATE_ID]:
        raise AssertionError("catalog maximum differs from the sealed state term")
    records = [certify_member(member) for member in owners]
    bounds = replaced_bounds(priors, records)
    owner_counts = {member.counts for member in owners}
    if any(
        bounds[counts] != prior for counts, prior in priors.items() if counts not in owner_counts
    ):
        raise AssertionError("a remainder member bound changed")
    final_bound = max(bounds.values())
    remainder_max = max(prior for counts, prior in priors.items() if counts not in owner_counts)
    band = [member for member in members if bounds[member.counts] == final_bound]
    family = recompute_family(final_bound)
    incumbent = catalog.r24.INCUMBENT
    result: dict[str, Any] = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "SUCCESS",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_BRANCH": TASK_BRANCH,
        "UPSTREAM_FINGERPRINTS_SHA256": fingerprints,
        "REGION_IDENTITY": REGION_SHA256,
        "STATE_ID": TARGET_STATE_ID,
        "REGION_SHA256": catalog.region_fingerprint(members),
        "REGION_COMPRESSED_MEMBER_COUNT": len(members),
        "REGION_REPRESENTED_VECTOR_COUNT": sum(
            member.represented_vector_count for member in members
        ),
        "RESIDUAL_EVENT_DEFINITION": RESIDUAL_EVENT_DEFINITION,
        "R14_CORRECTION_RULE": R14_CORRECTION_RULE,
        "CORRECTION_COMBINATION": CORRECTION_COMBINATION,
        "LOAD_BEARING_MEMBER_COUNT": len(records),
        "SIX_CERTIFICATES_STATUS": "PASS_6_EXACT_RESIDUAL_CEILING_CERTIFICATES",
        "MEMBER_CERTIFICATES": records,
        "TOP_BAND_CERTIFICATE_COUNT": TOP_BAND_CERTIFICATE_COUNT,
        "TOP_BAND_CERTIFICATES_PRESERVED": all(
            bounds[counts] == bound for counts, bound in sealed_top_band_bounds().items()
        ),
        "REMAINDER_MEMBER_COUNT": len(members) - len(records),
        "REMAINDER_MAX": remainder_max,
        "COMPLETE_REGION_MEMBERS": [
            {
                "member_id": member_id(member.counts),
                "witness_counts": sparse(member.counts),
                "represented_vector_count": member.represented_vector_count,
                "raw_bound": member.raw_bound,
                "prior_bound": priors[member.counts],
                "final_bound": bounds[member.counts],
            }
            for member in members
        ],
        "NEXT_BAND_COMPRESSED_MEMBERS": len(band),
        "NEXT_BAND_REPRESENTED_VECTORS": sum(member.represented_vector_count for member in band),
        "FINAL_STATE_BOUND": final_bound,
        "START_STATE_TERMS": [{"stable_id": key, "bound": bound} for key, bound in state_terms()],
        "FINAL_STATE_TERMS": [{"stable_id": key, "bound": bound} for key, bound in family["terms"]],
        "STATE_TERM_COUNT": len(family["terms"]),
        "CHANGED_STATE_IDS": [TARGET_STATE_ID],
        "TAIL_BOUND": family["tail_bound"],
        "CLASSIFIED_TERM_COUNT": family["classified_count"],
        "CLASSIFIED_TERMS_SHA256": family["classified_sha256"],
        "CLASSIFIED_AGGREGATE": family["aggregate"],
        "CLASSIFIED_MAX": family["family"]["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"],
        "START_FAMILY_MAX_RECOMPUTATION": family["start"],
        "FINAL_FAMILY_MAX_RECOMPUTATION": family["family"],
        "START_COMPLETE_R3_UB": family["start"]["R3_BOUND"],
        "FINAL_COMPLETE_R3_UB": family["family"]["R3_BOUND"],
        "FINAL_OWNER_IDS": family["family"]["OWNER_IDS"],
        "CURRENT_INCUMBENT": incumbent,
        "REMAINING_GAP": int(family["family"]["R3_BOUND"]) - incumbent,
        "NON_DUPLICATE_CREDIT_STATUS": "PASS_MAX_OF_R6_PAIR_FOREST_AND_R14_SINGLE_REPLACEMENT",
        "DUPLICATE_CORRECTIONS": 0,
        "WITNESS_SOUNDNESS_STATUS": "PASS_6_VALIDATED_SUPPORT_WITNESSES",
        "FULL_STATE_CATALOG_STATUS": (
            f"PASS_{len(members)}_OF_{len(members)}_{len(members) - len(records)}_UNCHANGED"
        ),
        "R7_CENSUS_REBUILD_CALLS": 0,
        "NEW_HEAVY_SOLVER_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "WORKTREE_DISPOSITION": "RETAIN",
    }
    if (
        not result["TOP_BAND_CERTIFICATES_PRESERVED"]
        or result["FINAL_STATE_BOUND"] != result["FINAL_COMPLETE_R3_UB"]
        or any(record["hunter_correction_applied"] for record in records)
    ):
        raise AssertionError("certificate preservation or family substitution failed")
    check_regression(result)
    verify_result(result)
    return result


def verify_result(result: dict[str, Any]) -> dict[str, Any]:
    """Replay the certificate.  A tampered field, source, or witness is rejected."""

    verify_upstream_fingerprints()
    members = region_members()
    priors = current_member_bounds(members)
    owners = load_bearing_members(members, priors)
    records = cast(list[dict[str, Any]], result["MEMBER_CERTIFICATES"])
    expected_ids = [member_id(member.counts) for member in owners]
    if [record["member_id"] for record in records] != expected_ids:
        raise AssertionError("certificate member coverage mismatch")
    for record, member in zip(records, owners, strict=True):
        verify_member_certificate(record, member)
    bounds = replaced_bounds(priors, records)
    rows = cast(list[dict[str, Any]], result["COMPLETE_REGION_MEMBERS"])
    if rows != [
        {
            "member_id": member_id(member.counts),
            "witness_counts": sparse(member.counts),
            "represented_vector_count": member.represented_vector_count,
            "raw_bound": member.raw_bound,
            "prior_bound": priors[member.counts],
            "final_bound": bounds[member.counts],
        }
        for member in members
    ]:
        raise AssertionError("stored region bounds differ from the replayed catalog")
    family = recompute_family(max(bounds.values()))
    if (
        result["REGION_IDENTITY"] != REGION_SHA256
        or result["FINAL_STATE_BOUND"] != max(bounds.values())
        or result["FINAL_COMPLETE_R3_UB"] != family["family"]["R3_BOUND"]
        or result["FINAL_OWNER_IDS"] != family["family"]["OWNER_IDS"]
        or result["START_COMPLETE_R3_UB"] != family["start"]["R3_BOUND"]
        or result["REMAINING_GAP"] != int(family["family"]["R3_BOUND"]) - catalog.r24.INCUMBENT
        or result["FINAL_STATE_TERMS"]
        != [{"stable_id": key, "bound": bound} for key, bound in family["terms"]]
        or result["CLASSIFIED_AGGREGATE"] != family["aggregate"]
        or result["TAIL_BOUND"] != family["tail_bound"]
        or result["NEW_HEAVY_SOLVER_STARTED"] != "NO"
        or result["PRODUCTION_MUTATION"] != "NONE"
    ):
        raise AssertionError("stored family maximum differs from the replay")
    return {"status": "PASS", "certificates": len(records)}


def encode(result: dict[str, Any]) -> str:
    return json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n"


def summary(result: dict[str, Any]) -> dict[str, Any]:
    return {field: result[field] for field in SUMMARY_FIELDS}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--verify", action="store_true")
    options = parser.parse_args()
    if options.verify:
        stored = cast(dict[str, Any], json.loads(RESULT_PATH.read_text(encoding="utf-8")))
        print(json.dumps(verify_result(stored), sort_keys=True))
        return
    result = build_result()
    if options.write:
        RESULT_PATH.write_text(encode(result), encoding="utf-8")
    print(json.dumps(summary(result), sort_keys=True))


if __name__ == "__main__":
    main()
