"""Zero-solve certificate for the top band of R3 state ``s2-13548976-s3-951748`` (R1).

R24 (``27614636``) left this state at 355,726,896.  Its immutable region ledger
holds 1,427 compressed members (1,543 represented vectors).  The top seven
448-step levels of that ledger hold three raw members each.  This state-local
task certifies exactly those 21 members with R14's existing rational moment
certificate, then recomputes the state term over the whole ledger:

* every member is rebuilt from its witness vector with R7's exact state
  constructor and must replay its ledger raw bound;
* a member's represented vectors are recovered only at its exact loss (R17).
  Each vector carries a verified support witness and a replayed rational
  certificate, and the member takes the smallest vector correction, so the
  certificate holds for every represented vector;
* the rational correction replaces the R7 penalty already inside the raw bound
  (``max``, never a sum), and no member is certified twice;
* every other member keeps its R24 final bound.

No R7 census, R24 tail walk, Hunter correction, solver or outcome enumeration
runs.  The result is a state term only; it makes no global R3 claim.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, replace
from functools import cache
from hashlib import sha256
from itertools import pairwise
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_r3_joint_residual_envelope_r7 as r7
from lottolab.research import b649_k20_r3_tail_crossover_state_dynamic_chase_r24 as r24

r17, r15, r14, r12, r8, r6, r5 = r24.r17, r24.r15, r24.r14, r24.r12, r24.r8, r24.r6, r24.r5
CountVector = r24.CountVector
dense, sparse, digest = r24.dense, r24.sparse, r24.digest
TASK_ID = "B649_K20_R3_STATE_13548976_TOP_BAND_CERTIFICATE_R1"
TASK_BRANCH = "codex/b649-k20-r3-state-13548976-top-band-certificate-r1"
BASE_HEAD = "27614636ac4c20392619b3d9364d22bf2af9cff4"
BASE_TREE = "cd99dee2289867b45bc6142baed87d5e0dbab96a"
TARGET_STATE_ID = r24.START_STATE_ID
TARGET_REGION_SHA256 = "1eed0fb9bc975d825d42413dd07ebfad5296d00185118850a38512c8a94e1f63"
REGION_MEMBER_COUNT = 1_427
REPRESENTED_VECTOR_COUNT = 1_543
R24_CERTIFIED_MEMBER_COUNT = 62
START_STATE_BOUND = 355_726_896
R24_DURABLE_R3_BOUND = 355_734_631
TOP_BAND_LEVEL_COUNT = 7
TOP_BAND_LEVEL_SIZE = 3
TOP_BAND_MEMBER_COUNT = TOP_BAND_LEVEL_COUNT * TOP_BAND_LEVEL_SIZE
# Packet research values: compared with the recomputed terms, never used to derive them.
RESEARCH_PROJECTED_STATE_BOUND = 355_637_030
PACKET_KNOWN_NEXT_STATE_BOUND = 355_641_258
MULTIPLICITY_CAP = 18
CORRECTION_COMBINATION = (
    "MAX(R7_APPLIED_RESIDUAL_UNION_PENALTY, MIN_REPRESENTED_VECTOR_RATIONAL_MOMENT); "
    "the R7 penalty is already inside the raw bound, so the rational term replaces it"
)
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS = r24.RESULTS
R24_RESULT_RELATIVE = RESULTS + "b649-k20-r3-tail-crossover-state-dynamic-chase-r24-result.json"
RESULT_PATH = REPO_ROOT / (
    RESULTS + "b649-k20-r3-state-13548976-top-band-certificate-r1-result.json"
)
_SOURCES = "src/lottolab/research/"
# The immutable R24 ledger and every source whose primitives this certificate replays.
UPSTREAM_SHA256 = {
    R24_RESULT_RELATIVE: "32182a3c3c803d95b3a7aee448f8ade3fadb291771affc9dca8beaab8147fc71",
    _SOURCES + "b649_k20_r3_tail_crossover_state_dynamic_chase_r24.py": (
        "2a5e57a7319bd215f8cbc7f4db26453308a74c3f540c25787c44604aa39c8fd7"
    ),
    _SOURCES + "b649_k20_r3_state_tail_owner_chase_r14.py": (
        "b30f6420eca033bc051ef35457993fc2588ee2e26cc1041363ced5d2c775ce99"
    ),
    _SOURCES + "b649_k20_r3_tail_state_owner_chase_r17.py": (
        "0edad246de25771745a215b0d922fc27e8839c40472a2f9859dc9a242a000a3b"
    ),
    _SOURCES + "b649_k20_r3_joint_residual_envelope_r7.py": (
        "f376899a25bc287e45b80c3f5d9116db97f4c09de31ec81d0ccd2badf4222c50"
    ),
    _SOURCES + "b649_k20_r3_corrected_tail_min_loss_plateau_r12.py": (
        "4501b7a496d32a87bdbfa2d4e0951bca330a60feb8b799350cc0a76607008c92"
    ),
    _SOURCES + "b649_k20_r3_frontier_realizability_bound_r8.py": (
        "14884faf5b2e66c1f30d4e04e453ba5838b7f95815d70d8b7d45be47c5e9bd2b"
    ),
}


@dataclass(frozen=True)
class LedgerMember:
    """One compressed member of the target region exactly as R24 recorded it."""

    counts: CountVector
    represented_vector_count: int
    raw_bound: int
    final_bound: int


def verify_upstream_fingerprints() -> dict[str, str]:
    observed = {
        relative: sha256((REPO_ROOT / relative).read_bytes()).hexdigest()
        for relative in UPSTREAM_SHA256
    }
    if observed != UPSTREAM_SHA256:
        raise AssertionError(f"R24 authority fingerprint mismatch: {observed}")
    return observed


@cache
def r24_authority() -> dict[str, Any]:
    verify_upstream_fingerprints()
    stored = cast(
        dict[str, Any], json.loads((REPO_ROOT / R24_RESULT_RELATIVE).read_text(encoding="utf-8"))
    )
    expected = {
        "TASK_ID": r24.TASK_ID,
        "TASK_BRANCH": r24.TASK_BRANCH,
        "BASE_HEAD": r24.BASE_HEAD,
        "R3_BOUND": R24_DURABLE_R3_BOUND,
        "STATE_MAX_BOUND": START_STATE_BOUND,
        "STATE_MAX_OWNER_IDS": [TARGET_STATE_ID],
    }
    if any(stored[key] != value for key, value in expected.items()):
        raise AssertionError("R24 authority differs from the Packet")
    return stored


def region_fingerprint(members: tuple[LedgerMember, ...]) -> str:
    """R22's region digest: the ordered (witness vector, raw bound) pairs."""

    return digest(tuple((member.counts, member.raw_bound) for member in members))


@cache
def target_region_ledger() -> tuple[LedgerMember, ...]:
    """The complete target region from R24's ledger, without an R7 census rebuild."""

    stored = r24_authority()
    regions = [
        row
        for row in cast(list[dict[str, Any]], stored["STATE_REGION_CERTIFICATES"])
        if row["owner_id"] == TARGET_STATE_ID
    ]
    carried = [
        row
        for row in cast(list[dict[str, Any]], stored["CARRIED_OWNER_REGION_CERTIFICATES"])
        if row["owner_id"] == TARGET_STATE_ID
    ]
    terms = [
        int(row["bound"])
        for row in cast(list[dict[str, Any]], stored["CURRENT_STATE_TERMS"])
        if row["stable_id"] == TARGET_STATE_ID
    ]
    if len(regions) != 1 or len(carried) != 1 or terms != [START_STATE_BOUND]:
        raise AssertionError("the target state has no unique R24 region ledger")
    region, entry = regions[0], carried[0]
    members = tuple(
        LedgerMember(
            dense(row["witness_counts"]),
            int(row["represented_vector_count"]),
            int(row["raw_bound"]),
            int(row["final_bound"]),
        )
        for row in cast(list[dict[str, Any]], region["complete_region_members"])
    )
    fingerprint = region_fingerprint(members)
    if (
        fingerprint != TARGET_REGION_SHA256
        or region["region_sha256"] != fingerprint
        or entry["region_sha256"] != fingerprint
        or len(members) != REGION_MEMBER_COUNT
        or entry["region_compressed_member_count"] != REGION_MEMBER_COUNT
        or sum(member.represented_vector_count for member in members) != REPRESENTED_VECTOR_COUNT
        or entry["region_type_vector_count"] != REPRESENTED_VECTOR_COUNT
        or len({member.counts for member in members}) != len(members)
        or any(
            member.represented_vector_count < 1 or member.final_bound > member.raw_bound
            for member in members
        )
        or max(member.final_bound for member in members) != START_STATE_BOUND
        or region["final_state_bound"] != START_STATE_BOUND
        or sum(member.final_bound != member.raw_bound for member in members)
        != region["certified_member_count"]
    ):
        raise AssertionError("the R24 target-region ledger fingerprint or completeness failed")
    return members


@cache
def carried_member_certificates() -> dict[CountVector, tuple[str, int]]:
    """Every committed certificate on the target region, at most one per member.

    R14-R23 rows come from R24's own carried-certificate reader; R24 rows come
    from its state certificates.  The ledger's reduced members must be exactly
    these members, each at its certified bound.
    """

    ledger = {member.counts: member for member in target_region_ledger()}
    rows: dict[CountVector, list[tuple[str, int]]] = {}
    for label, counts, bound, region in r24.carried_member_certificates(TARGET_STATE_ID):
        if region != TARGET_REGION_SHA256 or counts not in ledger:
            raise AssertionError(f"a carried {label} certificate differs from the target region")
        rows.setdefault(counts, []).append((label, bound))
    for record in cast(list[dict[str, Any]], r24_authority()["STATE_OWNER_CERTIFICATES"]):
        if record["owner_id"] != TARGET_STATE_ID:
            continue
        counts = dense(record["member"]["witness_counts"])
        if record["region_sha256"] != TARGET_REGION_SHA256 or counts not in ledger:
            raise AssertionError("an R24 member certificate differs from the target region")
        rows.setdefault(counts, []).append(("R24", int(record["member_new_bound"])))
    if any(len(values) != 1 for values in rows.values()):
        raise AssertionError("a target member carries more than one committed correction")
    for counts, member in ledger.items():
        certified = rows.get(counts)
        expected = member.raw_bound if certified is None else certified[0][1]
        if member.final_bound != expected or expected > member.raw_bound:
            raise AssertionError("a ledger bound is not backed by its committed certificate")
    if len(rows) != R24_CERTIFIED_MEMBER_COUNT:
        raise AssertionError("the committed target certificates are incomplete")
    return {counts: values[0] for counts, values in rows.items()}


def top_band(
    members: tuple[LedgerMember, ...],
) -> tuple[tuple[int, tuple[LedgerMember, ...]], ...]:
    """The seven highest distinct ledger levels, three members each."""

    levels = sorted({member.final_bound for member in members}, reverse=True)[:TOP_BAND_LEVEL_COUNT]
    band = tuple(
        (level, tuple(member for member in members if member.final_bound == level))
        for level in levels
    )
    if (
        len(band) != TOP_BAND_LEVEL_COUNT
        or levels[0] != START_STATE_BOUND
        or any(len(rows) != TOP_BAND_LEVEL_SIZE for _, rows in band)
    ):
        raise AssertionError("the top band is not seven levels of three members")
    return band


def rebuild_member(member: LedgerMember) -> r7.ResidualJointState:
    """R7's exact state constructor on the witness vector; the ledger raw bound must replay."""

    profiles = r5.anchor_incidence_profiles()
    make_state_api = "_make_state"
    make_state = getattr(r7, make_state_api)
    state = cast(
        r7.ResidualJointState, make_state(member.counts, profiles, r6.local_losses(profiles))
    )
    state = replace(state, represented_vector_count=member.represented_vector_count)
    # R14's canonical joint constant, not R7's pre-R10 ``upper_bound`` constant.
    if r14.raw_bound(state) != member.raw_bound:
        raise AssertionError("a rebuilt member does not replay its ledger raw bound")
    return state


def normalized(payload: object) -> Any:
    """The JSON form a stored result carries (tuples become lists)."""

    return json.loads(json.dumps(payload))


def certify_member(member: LedgerMember) -> dict[str, Any]:
    """R14's rational moment certificate, valid for every represented vector."""

    if member.final_bound != member.raw_bound:
        # The rational certificate is already spent on this member.
        raise r15.RationalRouteExhausted(TARGET_STATE_ID)
    state = rebuild_member(member)
    vectors = r17.represented_vectors((state,))[member.counts]
    certificates: list[dict[str, Any]] = []
    witnesses: list[dict[str, Any]] = []
    for vector in vectors:
        support = r12.construct_support_witness(vector)
        if support is None or not r8.validate_support_assignment(vector, support):
            raise AssertionError("a represented vector has no verified support witness")
        certificates.append(r14.moment_certificate(vector))
        witnesses.append({"counts": sparse(vector), "support_witness": support})
    rational = min(int(row["correction_lower_bound"]) for row in certificates)
    correction = max(state.applied_residual_union_penalty, rational)
    uncorrected = r14.joint_constant() - state.anchor_pair_s2 + state.anchor_triple_s3
    bound = uncorrected - correction
    if bound >= member.raw_bound:
        raise r15.RationalRouteExhausted(TARGET_STATE_ID)
    return {
        "member": r24.member_record(state),
        "represented_vectors": [sparse(vector) for vector in vectors],
        "vector_certificates": certificates,
        "support_witnesses": witnesses,
        "joint_constant": r14.joint_constant(),
        "uncorrected_anchor_bound": uncorrected,
        "prior_applied_correction": state.applied_residual_union_penalty,
        "minimum_vector_rational_correction": rational,
        "member_certified_correction": correction,
        "correction_combination": CORRECTION_COMBINATION,
        "member_prior_bound": member.final_bound,
        "member_raw_bound": member.raw_bound,
        "member_new_bound": bound,
        "member_drop": member.raw_bound - bound,
        "tightening_route": r24.RATIONAL_MOMENT_ROUTE,
        "region_sha256": TARGET_REGION_SHA256,
    }


def check_certificate_arithmetic(record: dict[str, Any]) -> None:
    """Exact integer checks on a stored certificate's own fields, without a replay."""

    member = cast(dict[str, Any], record["member"])
    certificates = cast(list[dict[str, Any]], record["vector_certificates"])
    vectors = cast(list[Any], record["represented_vectors"])
    if (
        not certificates
        or len(certificates) != int(member["represented_vector_count"])
        or [row["counts"] for row in certificates] != vectors
        or [row["counts"] for row in record["support_witnesses"]] != vectors
        or min(vectors) != member["witness_counts"]
    ):
        raise AssertionError("a certificate does not cover every represented vector once")
    # The multiplicity dual 2/M: 2*C(m, 2) <= M*(m - 1) for every winner multiplicity m <= M.
    if any(
        2 * math.comb(m, 2) > MULTIPLICITY_CAP * max(0, m - 1) for m in range(MULTIPLICITY_CAP + 1)
    ):
        raise AssertionError("the rational multiplicity dual is invalid")
    for row in certificates:
        s2 = int(row["residual_s2_lower_bound"])
        if (
            row["multiplicity_cap"] != MULTIPLICITY_CAP
            or row["multiplicity_dual"] != [1, MULTIPLICITY_CAP // 2]
            or int(row["correction_lower_bound"]) != -(-2 * s2 // MULTIPLICITY_CAP)
        ):
            raise AssertionError("a vector correction is not ceil(2*S2/18)")
    rational = min(int(row["correction_lower_bound"]) for row in certificates)
    applied = int(member["applied_residual_union_penalty"])
    uncorrected = (
        int(record["joint_constant"])
        - int(member["anchor_pair_s2"])
        + int(member["anchor_triple_s3"])
    )
    correction = int(record["member_certified_correction"])
    if (
        applied
        != max(
            int(member["residual_pair_union_penalty"]), int(member["complementary_forest_floor"])
        )
        or int(record["prior_applied_correction"]) != applied
        or int(record["minimum_vector_rational_correction"]) != rational
        or int(member["joint_s2"]) != int(member["anchor_pair_s2"]) + applied
        or int(record["uncorrected_anchor_bound"]) != uncorrected
        or int(member["raw_bound"]) != uncorrected - applied
        or int(record["member_raw_bound"]) != int(member["raw_bound"])
        or int(record["member_prior_bound"]) != int(member["raw_bound"])
        # Applied once: the larger correction replaces the raw penalty, never adds to it.
        or correction != max(applied, rational)
        or int(record["member_new_bound"]) != uncorrected - correction
        or int(record["member_drop"]) != int(member["raw_bound"]) - int(record["member_new_bound"])
        or int(record["member_new_bound"]) >= int(record["member_prior_bound"])
        or record["correction_combination"] != CORRECTION_COMBINATION
        or record["region_sha256"] != TARGET_REGION_SHA256
    ):
        raise AssertionError("a member certificate fails its exact correction arithmetic")


def verify_member_certificate(record: dict[str, Any], member: LedgerMember) -> None:
    """Arithmetic first, then replay identity, vectors, certificates and witnesses."""

    check_certificate_arithmetic(record)
    if record["joint_constant"] != r14.joint_constant():
        raise AssertionError("a certificate uses a different canonical joint constant")
    state = rebuild_member(member)
    if record["member"] != normalized(r24.member_record(state)) or member.final_bound != (
        member.raw_bound
    ):
        raise AssertionError("a certificate differs from its rebuilt raw member")
    vectors = r17.represented_vectors((state,))[member.counts]
    if record["represented_vectors"] != [sparse(vector) for vector in vectors]:
        raise AssertionError("a certificate's represented vectors differ from R17's recovery")
    for vector, certificate, witness in zip(
        vectors, record["vector_certificates"], record["support_witnesses"], strict=True
    ):
        if certificate != normalized(r14.moment_certificate(vector)):
            raise AssertionError("a stored rational certificate differs from its replay")
        support = tuple(tuple(int(label) for label in row) for row in witness["support_witness"])
        if not r8.validate_support_assignment(vector, support):
            raise AssertionError("a stored support witness fails independent validation")


def recompute_state(
    members: tuple[LedgerMember, ...], certificates: list[dict[str, Any]]
) -> dict[CountVector, int]:
    """Replace only the newly certified member bounds; every other member keeps R24's."""

    bounds = {member.counts: member.final_bound for member in members}
    certified = [dense(record["member"]["witness_counts"]) for record in certificates]
    if len(set(certified)) != len(certified):
        raise AssertionError("a member is certified twice")
    for counts, record in zip(certified, certificates, strict=True):
        if counts not in bounds or bounds[counts] != int(record["member_prior_bound"]):
            raise AssertionError("a certificate does not replace a carried R24 member bound")
        bounds[counts] = int(record["member_new_bound"])
    return bounds


def other_state_terms() -> list[tuple[int, str]]:
    return sorted(
        (
            (int(row["bound"]), str(row["stable_id"]))
            for row in cast(list[dict[str, Any]], r24_authority()["CURRENT_STATE_TERMS"])
            if row["stable_id"] != TARGET_STATE_ID
        ),
        reverse=True,
    )


def build_result() -> dict[str, Any]:
    authority = r24_authority()
    canonical = r24.canonical_primitives()
    members = target_region_ledger()
    carried = carried_member_certificates()
    raw_replays = [rebuild_member(member) for member in members]
    band = top_band(members)
    band_members = [member for _, rows in band for member in rows]
    previously = [member for member in band_members if member.counts in carried]
    if any(
        (member.final_bound != member.raw_bound) != (member.counts in carried) for member in members
    ):
        raise AssertionError("carried certificates and reduced ledger members disagree")
    certificates = [certify_member(member) for member in band_members if member not in previously]
    bounds = recompute_state(members, certificates)
    final_bound = max(bounds.values())
    owners = [member for member in members if bounds[member.counts] == final_bound]
    band_after = max(bounds[member.counts] for member in band_members)
    others = other_state_terms()
    packet_next = [
        identifier for bound, identifier in others if bound == PACKET_KNOWN_NEXT_STATE_BOUND
    ]
    result: dict[str, Any] = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "SUCCESS" if band_after < final_bound else "TOP_BAND_NOT_CLEARED",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_BRANCH": TASK_BRANCH,
        "R24_AUTHORITY": {
            "authority_head": BASE_HEAD,
            "authority_task_id": authority["TASK_ID"],
            "authority_result_sha256": UPSTREAM_SHA256[R24_RESULT_RELATIVE],
            "authority_r3_bound": authority["R3_BOUND"],
            "authority_r3_owner_ids": authority["FINAL_OWNER_IDS"],
        },
        "UPSTREAM_FINGERPRINTS_SHA256": verify_upstream_fingerprints(),
        "UPSTREAM_FINGERPRINT_STATUS": "PASS",
        "CANONICAL_PRIMITIVES": canonical,
        "JOINT_CONSTANT": r14.joint_constant(),
        "STATE_ID": TARGET_STATE_ID,
        "REGION_SHA256": region_fingerprint(members),
        "REGION_SOURCE": "R24_STATE_REGION_CERTIFICATES_LEDGER_NO_R7_CENSUS_REBUILD",
        "REGION_MEMBER_COUNT": len(members),
        "REPRESENTED_VECTOR_COUNT": sum(member.represented_vector_count for member in members),
        "REGION_COMPRESSED_MEMBER_COUNT": sum(
            member.represented_vector_count > 1 for member in members
        ),
        "REGION_RAW_BOUND_REPLAY": {
            "members_rebuilt": len(raw_replays),
            "raw_bound_mismatches": 0,
            "constructor": "R7_MAKE_STATE_WITH_AGGREGATE_FEASIBILITY",
        },
        "CARRIED_CERTIFIED_MEMBER_COUNT": len(carried),
        "CARRIED_CERTIFICATE_ROUNDS": sorted({label for label, _ in carried.values()}),
        "CARRIED_CERTIFIED_MEMBERS_SHA256": digest(tuple(sorted(carried.items()))),
        "REGION_COMPLETENESS_STATUS": "PASS",
        "TOP_BAND_LEVELS": [
            {
                "bound": level,
                "members": [
                    {
                        "witness_counts": sparse(member.counts),
                        "represented_vector_count": member.represented_vector_count,
                        "local_loss": state.local_loss,
                    }
                    for member, state in ((member, rebuild_member(member)) for member in rows)
                ],
            }
            for level, rows in band
        ],
        "TOP_BAND_LEVEL_SPACING": sorted({a - b for (a, _), (b, _) in pairwise(band)}),
        "TOP_BAND_MEMBER_COUNT": len(band_members),
        "TOP_BAND_REPRESENTED_VECTOR_COUNT": sum(
            member.represented_vector_count for member in band_members
        ),
        "PREVIOUSLY_CERTIFIED_BAND_MEMBERS": [
            {
                "witness_counts": sparse(member.counts),
                "round": carried[member.counts][0],
                "bound": member.final_bound,
            }
            for member in previously
        ],
        "NEW_MEMBER_CERTIFICATE_COUNT": len(certificates),
        "NEW_MEMBER_CERTIFICATES": certificates,
        "MAXIMUM_NEW_MEMBER_BOUND": max(int(row["member_new_bound"]) for row in certificates),
        "MINIMUM_NEW_MEMBER_DROP": min(int(row["member_drop"]) for row in certificates),
        "RATIONAL_MOMENT_STATUS": "PASS",
        "WITNESS_SOUNDNESS_STATUS": "PASS",
        "CORRECTION_COMBINATION": CORRECTION_COMBINATION,
        "DUPLICATE_CORRECTIONS": 0,
        "COMPLETE_REGION_MEMBERS": [
            {
                "witness_counts": sparse(member.counts),
                "represented_vector_count": member.represented_vector_count,
                "raw_bound": member.raw_bound,
                "r24_final_bound": member.final_bound,
                "final_bound": bounds[member.counts],
            }
            for member in members
        ],
        "CERTIFIED_MEMBER_COUNT_AFTER": sum(
            bounds[member.counts] != member.raw_bound for member in members
        ),
        "START_STATE_BOUND": START_STATE_BOUND,
        "FINAL_STATE_BOUND": final_bound,
        "STATE_DROP": START_STATE_BOUND - final_bound,
        "FINAL_STATE_OWNER_MEMBERS": [
            {
                "witness_counts": sparse(member.counts),
                "represented_vector_count": member.represented_vector_count,
                "raw_bound": member.raw_bound,
                "carried_certificate": member.counts in carried,
            }
            for member in owners
        ],
        "TOP_BAND_MAXIMUM_AFTER": band_after,
        "TOP_BAND_CLEARED": band_after < final_bound,
        "RESEARCH_PROJECTED_STATE_BOUND": RESEARCH_PROJECTED_STATE_BOUND,
        "RESEARCH_PROJECTION_MATCH": final_bound == RESEARCH_PROJECTED_STATE_BOUND,
        "OTHER_R24_STATE_TERMS": [{"stable_id": key, "bound": bound} for bound, key in others],
        "NEXT_COMPETING_STATE_ID": others[0][1],
        "NEXT_COMPETING_STATE_BOUND": others[0][0],
        "PACKET_KNOWN_NEXT_STATE_BOUND": PACKET_KNOWN_NEXT_STATE_BOUND,
        "PACKET_KNOWN_NEXT_STATE_IDS": packet_next,
        "PACKET_KNOWN_NEXT_STATE_RANK": [key for _, key in others].index(packet_next[0]) + 1
        if packet_next
        else None,
        "R3_DURABLE_BOUND": R24_DURABLE_R3_BOUND,
        "R3_DURABLE_BOUND_UNCHANGED": True,
        "R3_CLAIM": "NONE_STATE_LOCAL_CERTIFICATE_ONLY",
        "SOLVER_STATUS": "NOT_DISPATCHED_ZERO_SOLVE_RATIONAL_CERTIFICATES",
        "NEW_HEAVY_SOLVER_STARTED": "NO",
        "R7_CENSUS_REBUILD_CALLS": 0,
        "R24_TAIL_WALK_REPLAY_CALLS": 0,
        "HUNTER_CORRECTIONS_APPLIED": 0,
        "OUTCOME_ENUMERATION_USED": False,
        "PRODUCTION_MUTATION": "NONE",
    }
    verify_result(result)
    return result


def verify_result(result: dict[str, Any]) -> dict[str, Any]:
    """Re-derive a stored result from the R24 ledger; any tampered field is rejected."""

    members = target_region_ledger()
    ledger = {member.counts: member for member in members}
    carried = carried_member_certificates()
    band = top_band(members)
    expected = [
        sparse(member.counts) for _, rows in band for member in rows if member.counts not in carried
    ]
    records = cast(list[dict[str, Any]], result["NEW_MEMBER_CERTIFICATES"])
    if (
        result["TASK_ID"] != TASK_ID
        or result["STATE_ID"] != TARGET_STATE_ID
        or result["REGION_SHA256"] != region_fingerprint(members)
        or result["UPSTREAM_FINGERPRINTS_SHA256"] != verify_upstream_fingerprints()
        or [record["member"]["witness_counts"] for record in records] != expected
        or result["NEW_MEMBER_CERTIFICATE_COUNT"] != len(records)
    ):
        raise AssertionError("the certified members differ from the raw top band")
    for record in records:
        verify_member_certificate(record, ledger[dense(record["member"]["witness_counts"])])
    bounds = recompute_state(members, records)
    rows = cast(list[dict[str, Any]], result["COMPLETE_REGION_MEMBERS"])
    final_bound = max(bounds.values())
    if (
        rows
        != [
            {
                "witness_counts": sparse(member.counts),
                "represented_vector_count": member.represented_vector_count,
                "raw_bound": member.raw_bound,
                "r24_final_bound": member.final_bound,
                "final_bound": bounds[member.counts],
            }
            for member in members
        ]
        or result["FINAL_STATE_BOUND"] != final_bound
        or result["STATE_DROP"] != START_STATE_BOUND - final_bound
        or [row["witness_counts"] for row in result["FINAL_STATE_OWNER_MEMBERS"]]
        != [sparse(member.counts) for member in members if bounds[member.counts] == final_bound]
        or result["CERTIFIED_MEMBER_COUNT_AFTER"]
        != sum(bounds[member.counts] != member.raw_bound for member in members)
        or result["R3_DURABLE_BOUND"] != R24_DURABLE_R3_BOUND
        or result["R3_CLAIM"] != "NONE_STATE_LOCAL_CERTIFICATE_ONLY"
    ):
        raise AssertionError("the recomputed region maximum differs from the stored result")
    return {
        "verified_member_certificates": len(records),
        "final_state_bound": final_bound,
        "status": "PASS",
    }


def encode(result: dict[str, Any]) -> str:
    return json.dumps(result, separators=(",", ":")) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--verify", action="store_true")
    options = parser.parse_args()
    if options.verify:
        stored = cast(dict[str, Any], json.loads(RESULT_PATH.read_text(encoding="utf-8")))
        print(json.dumps(verify_result(stored), indent=2))
        return
    result = build_result()
    if not options.no_write:
        RESULT_PATH.write_text(encode(result), encoding="utf-8")
    print(
        json.dumps(
            {
                key: value
                for key, value in result.items()
                if key.isupper() and not isinstance(value, (dict, list))
            }
            | {
                "PACKET_KNOWN_NEXT_STATE_IDS": result["PACKET_KNOWN_NEXT_STATE_IDS"],
                "FINAL_STATE_OWNER_MEMBERS": result["FINAL_STATE_OWNER_MEMBERS"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
