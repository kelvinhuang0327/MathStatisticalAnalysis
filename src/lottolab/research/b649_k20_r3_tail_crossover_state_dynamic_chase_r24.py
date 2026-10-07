"""Finish R23's tail interval to the next state owner, then chase the live R3 owner (R24).

R23 (``aee3ebab``) left the unclassified tail as the sole R3 owner at 356,177,969
with its attained cursor at 8,870,659.  The next owner is the never-refined state
``s2-13548976-s3-951748`` at 356,161,470, so the tail must walk exactly to loss
365,048,628 - 356,161,470 = 8,887,158 (a 16,499-loss interval) before the state
takes ownership.  After that, every action is dispatched only to the live owner:

* a classified owner first.  The carried R12 aggregate is recovered one owner
  level at a time against R12's stored census; a vector owner gets R14's rational
  moment certificate;
* a state owner, including a state/tail tie, next.  Its R7 region is restored with
  every committed member certificate (R14, R15, R16, R20, R22, R23).  One maximizing
  member is then certified at a time;
* the tail last, one attained level at a time, never below the live competitor.

Neither a transition count nor a cumulative-drop target stops the chase; only R4
(SUCCESS A/B) or the 60-minute proof wall budget (SUCCESS C) does.  R23's tail
levels are carried by fingerprint and never enumerated or reclassified.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass, field
from functools import cache
from hashlib import sha256
from itertools import pairwise
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_r3_tail_to_state_dynamic_chase_r23 as r23
from lottolab.research.b649_k20_r3_tail_threshold_to_top_state_r13 import ClassifiedVector

r22, r19, r17, r16, r15, r14, r13 = r23.r22, r23.r19, r23.r17, r23.r16, r23.r15, r23.r14, r23.r13
r12, r8, r7, r6, r5 = r23.r12, r23.r8, r23.r7, r23.r6, r23.r5
CountVector = r23.CountVector
dense, sparse, digest = r23.dense, r23.sparse, r23.digest
owner_class, owner_classes = r23.owner_class, r23.owner_classes
state_region, region_sha256, member_record = r23.state_region, r23.region_sha256, r23.member_record
pinned_r7_census, canonical_primitives = r23.pinned_r7_census, r23.canonical_primitives
select_owner = r23.select_owner
STATE_CLASS, TAIL_CLASS, CLASSIFIED_CLASS = r23.STATE_CLASS, r23.TAIL_CLASS, r23.CLASSIFIED_CLASS
TAIL_ID = r23.TAIL_ID
STOP_C = r23.STOP_C
STOP_EXHAUSTED, STOP_SCOPE = r22.STOP_EXHAUSTED, r22.STOP_SCOPE
STOP_A = "A_R3_AT_OR_BELOW_R4_REFERENCE"
RATIONAL_MOMENT_ROUTE = r23.RATIONAL_MOMENT_ROUTE
TASK_ID = "B649_K20_R3_TAIL_CROSSOVER_STATE_DYNAMIC_CHASE_R24"
TASK_BRANCH = "codex/b649-k20-r3-tail-crossover-state-dynamic-chase-r24"
BASE_HEAD = "aee3ebabb6f07f5918a1f425aa5f62b01f07f3e3"
BASE_TREE = "9b713b391eed8c6961ce73573a68d8331c3919ac"
START_R3_BOUND = START_UNCLASSIFIED_TAIL_BOUND = 356_177_969
START_LOSS = 8_870_659
START_STATE_BOUND = 356_161_470
START_STATE_ID = "state:s2-13548976-s3-951748"
START_CLASSIFIED_MAXIMUM = 356_056_456
AGGREGATE_ID = START_CLASSIFIED_ID = "carried-r12-other-levels"
TAIL_BASE_CONSTANT = 365_048_628
STATE_CROSSOVER_LOSS = 8_887_158
STATE_CROSSOVER_INTERVAL = 16_499
# R23 keeps its pinned historical target; the live R24 target is refreshed separately.
R23_RECORDED_INCUMBENT = 313_239_661
R4_REFERENCE_BOUND, INCUMBENT = 350_545_749, 313_263_888
PROOF_WALL_BUDGET_SECONDS = 3_600.0
# One interval census enumerates up to this much loss ahead of the cursor, never
# past the loss where the tail meets its live competitor; levels are still
# classified and certified one at a time.
TAIL_WINDOW_WIDTH = 8_000
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS = "docs/research/matrix-native-results/"
RESULT_PATH = REPO_ROOT / (
    RESULTS + "b649-k20-r3-tail-crossover-state-dynamic-chase-r24-result.json"
)
R23_RESULT_RELATIVE = RESULTS + "b649-k20-r3-tail-to-state-dynamic-chase-r23-result.json"
R12_RESULT_RELATIVE = RESULTS + "b649-k20-r3-corrected-tail-min-loss-plateau-r12-result.json"
R14_RESULT_RELATIVE = RESULTS + "b649-k20-r3-state-tail-owner-chase-r14-result.json"
R15_RESULT_RELATIVE = RESULTS + "b649-k20-r3-tail-to-state-owner-chase-r15-result.json"
R16_RESULT_RELATIVE = RESULTS + "b649-k20-r3-tail-state-owner-chase-r16-result.json"
R20_RESULT_RELATIVE = RESULTS + "b649-k20-r3-tail-crossover-and-state-refinement-r20-result.json"
R22_RESULT_RELATIVE = r23.R22_RESULT_RELATIVE
UPSTREAM_SHA256 = {
    "src/lottolab/research/b649_k20_r3_tail_to_state_dynamic_chase_r23.py": (
        "9ba9dc55b14a14aabad2c21c9a03da4058e12c3dede959c3f050c88424e73c5e"
    ),
    R23_RESULT_RELATIVE: "dd53cdfa70488cbf0a07f1b5db9f04f4047ecf2186f7115426e469657da357d4",
}
# Committed member certificates and the R12 aggregate census: data reads only.
CARRIED_SHA256 = {
    R12_RESULT_RELATIVE: "fc9c31ecb106efef7867e93815772261e2d9eafc8031c62de477ee32979d3823",
    R14_RESULT_RELATIVE: "5f6c73900469724015fc18d5e713180682ef27ec7f9fa1d98cc7767fea47d115",
    R15_RESULT_RELATIVE: "30ea29e74a0111aa4b3721cf79b781f076eaadc6e5d185c007fb05f551b88865",
    R16_RESULT_RELATIVE: "7b7975b66b149eb37cfd688bc6878ef7f6461019b63b79642f13d7c432a21f70",
    R20_RESULT_RELATIVE: "65682bd1b41aafe1d8b398b224caf704686a9820c203fcfe61a904e83b16f72b",
    R22_RESULT_RELATIVE: "1f8d6b53ae55277067a8548d39054134ea5e8617ab4f288225fdeab65438f6e0",
}


def verify_upstream_fingerprints() -> dict[str, str]:
    pinned = UPSTREAM_SHA256 | CARRIED_SHA256
    observed = {
        relative: sha256((REPO_ROOT / relative).read_bytes()).hexdigest() for relative in pinned
    }
    if observed != pinned:
        raise AssertionError(f"R23 authority fingerprint mismatch: {observed}")
    r23.verify_upstream_fingerprints()  # Files only, never prior-level enumerators.
    return observed


@cache
def stored_result(relative: str) -> dict[str, Any]:
    verify_upstream_fingerprints()
    if relative not in CARRIED_SHA256:
        raise AssertionError(f"unpinned carried result: {relative}")
    return cast(dict[str, Any], json.loads((REPO_ROOT / relative).read_text(encoding="utf-8")))


@cache
def authority() -> dict[str, Any]:
    verify_upstream_fingerprints()
    stored = cast(
        dict[str, Any], json.loads((REPO_ROOT / R23_RESULT_RELATIVE).read_text(encoding="utf-8"))
    )
    expected = {
        "TASK_ID": r23.TASK_ID,
        "TASK_BRANCH": r23.TASK_BRANCH,
        "BASE_HEAD": r23.BASE_HEAD,
        "TASK_STATUS": "SUCCESS_B",
        "R3_BOUND": START_R3_BOUND,
        "FINAL_OWNER_IDS": [TAIL_ID],
        "STATE_MAX_BOUND": START_STATE_BOUND,
        "STATE_MAX_OWNER_IDS": [START_STATE_ID],
        "NEXT_UNCLASSIFIED_LOSS": START_LOSS,
        "UNCLASSIFIED_TAIL_BOUND": START_UNCLASSIFIED_TAIL_BOUND,
        "MAX_CLASSIFIED_TAIL_VECTOR_BOUND": START_CLASSIFIED_MAXIMUM,
        "MAX_CLASSIFIED_TAIL_VECTOR_ID": START_CLASSIFIED_ID,
        "R4_REFERENCE_BOUND": R4_REFERENCE_BOUND,
        "INCUMBENT": R23_RECORDED_INCUMBENT,
    }
    if any(stored[key] != value for key, value in expected.items()):
        raise AssertionError("R23 authority differs from the R24 Packet")
    return stored


def canonical_baseline() -> int:
    baseline = canonical_primitives()["K20_S1"] - r13.FIXED_CERTIFIED_LOSS
    if (
        baseline != TAIL_BASE_CONSTANT
        or baseline - START_LOSS != START_UNCLASSIFIED_TAIL_BOUND
        or baseline - START_STATE_BOUND != STATE_CROSSOVER_LOSS
        or STATE_CROSSOVER_LOSS - START_LOSS != STATE_CROSSOVER_INTERVAL
    ):
        raise AssertionError("the independent tail crossover arithmetic failed")
    return baseline


def require_unclassified_cursor(loss: int) -> None:
    if loss < START_LOSS:
        raise AssertionError("prior tail enumeration or reclassification is forbidden")


@cache
def prior_level_fingerprints() -> dict[str, Any]:
    rows = cast(list[dict[str, Any]], authority()["TAIL_LEVEL_CERTIFICATES"])
    if (
        int(rows[0]["local_loss"]) != r23.START_LOSS
        or any(int(a["next_unclassified_loss"]) != int(b["local_loss"]) for a, b in pairwise(rows))
        or int(rows[-1]["next_unclassified_loss"]) != START_LOSS
        or any(int(row["unresolved_count"]) for row in rows)
    ):
        raise AssertionError("the pinned R23 levels do not end at the R24 cursor")
    return {
        "r23_certified_levels": len(rows),
        "r23_certified_vectors": sum(int(row["vector_count"]) for row in rows),
        "r23_certified_level_range": [rows[0]["local_loss"], rows[-1]["local_loss"]],
        "r23_level_counts_sha256": digest(tuple(row["counts_sha256"] for row in rows)),
        "r24_first_unclassified_loss": START_LOSS,
        "prior_level_enumeration_calls": 0,
    }


@dataclass
class Chase(r23.Chase):
    start_bound: int = START_R3_BOUND
    split_r12_levels: list[int] = field(default_factory=lambda: [])
    r12_recoveries: list[dict[str, Any]] = field(default_factory=lambda: [])
    tail_window: dict[int, tuple[CountVector, ...]] = field(default_factory=lambda: {})
    tail_window_upper: int = -1
    tail_windows: list[dict[str, Any]] = field(default_factory=lambda: [])

    def stop_condition(self) -> str | None:
        """Only R4 ends the chase early; there is no transition or drop target."""
        if self.bound <= self.r4_reference:
            return STOP_A
        return None


def initial_chase() -> Chase:
    stored = authority()
    states = tuple(
        (str(row["stable_id"]), int(row["bound"]))
        for row in cast(list[dict[str, Any]], stored["CURRENT_STATE_TERMS"])
    )
    classified = {
        str(row["stable_id"]): int(row["bound"])
        for row in cast(list[dict[str, Any]], stored["CURRENT_CLASSIFIED_TERMS"])
    }
    chase = Chase(
        states=states,
        baseline=canonical_baseline(),
        next_loss=START_LOSS,
        classified_maximum=(START_CLASSIFIED_ID, START_CLASSIFIED_MAXIMUM),
        classified_terms=classified,
    )
    chase.sync_classified_maximum()
    if (
        len(states) != 23
        or chase.owners != (TAIL_ID,)
        or chase.bound != START_R3_BOUND
        or chase.state_max != START_STATE_BOUND
        or r13.identify_owner_set(chase.states) != (START_STATE_ID,)
        or chase.classified_maximum != (START_CLASSIFIED_ID, START_CLASSIFIED_MAXIMUM)
        or chase.competitor(TAIL_ID) != START_STATE_BOUND
    ):
        raise AssertionError("the initial owner/family maximum differs from R23")
    return chase


CarriedCertificate = tuple[str, CountVector, int, str]


@cache
def carried_member_certificates(owner_id: str) -> tuple[CarriedCertificate, ...]:
    """Every committed member certificate for one state: (round, member, bound, region)."""

    rows: list[CarriedCertificate] = []
    for label, relative in (
        ("R14", R14_RESULT_RELATIVE),
        ("R15", R15_RESULT_RELATIVE),
        ("R16", R16_RESULT_RELATIVE),
    ):
        for certificate in cast(
            list[dict[str, Any]], stored_result(relative)["STATE_OWNER_CERTIFICATES"]
        ):
            if certificate["owner_id"] != owner_id:
                continue
            region = str(certificate["region_sha256"])
            for row in cast(list[dict[str, Any]], certificate["region_moment_certificates"]):
                if "witness_counts" in row:
                    counts = dense(row["witness_counts"])
                elif int(row["represented_vector_count"]) == 1:
                    counts = dense(row["certificate"]["counts"])
                else:
                    raise AssertionError(f"a carried {label} certificate has no member key")
                rows.append((label, counts, int(row["certified_bound"]), region))
            for row in cast(list[dict[str, Any]], certificate.get("complete_region_members", [])):
                rows.append((label, dense(row["witness_counts"]), int(row["final_bound"]), region))
    for row in cast(
        list[dict[str, Any]], stored_result(R20_RESULT_RELATIVE)["STATE_OWNER_CERTIFICATES"]
    ):
        if row["owner_id"] == owner_id:
            rows.append(
                (
                    "R20",
                    dense(row["witness_counts"]),
                    int(row["member_new_bound"]),
                    str(row["region_sha256"]),
                )
            )
    for label, stored in (("R22", stored_result(R22_RESULT_RELATIVE)), ("R23", authority())):
        for region in cast(list[dict[str, Any]], stored["STATE_REGION_CERTIFICATES"]):
            if region["owner_id"] != owner_id:
                continue
            for row in cast(list[dict[str, Any]], region["complete_region_members"]):
                rows.append(
                    (
                        label,
                        dense(row["witness_counts"]),
                        int(row["final_bound"]),
                        str(region["region_sha256"]),
                    )
                )
    return tuple(rows)


def restore_owner_region(chase: Chase, owner_id: str) -> None:
    """Rebuild only the selected state's member bounds from its committed certificates."""

    chase.require_dispatch(owner_id)
    if select_owner(chase) != owner_id or owner_class(owner_id) != STATE_CLASS:
        raise AssertionError("region reconstruction requires the selected state owner")
    if owner_id in chase.state_region_bounds:
        return
    region = state_region(owner_id)
    region_digest = region_sha256(region)
    raw = {row.witness_counts: r14.raw_bound(row) for row in region}
    prior = dict(chase.states)[owner_id]
    bounds = dict(raw)
    certificates = carried_member_certificates(owner_id)
    for label, counts, bound, source_region in certificates:
        if source_region != region_digest or counts not in raw or bound > raw[counts]:
            raise AssertionError(f"a carried {label} member certificate differs from the R7 region")
        bounds[counts] = min(bounds[counts], bound)
    if max(bounds.values()) != prior:
        raise r22.StateScopeRequired(owner_id)
    reduced = [counts for counts, value in bounds.items() if value != raw[counts]]
    chase.state_region_bounds[owner_id] = bounds
    chase.carried_regions.append(
        {
            "owner_id": owner_id,
            "region_sha256": region_digest,
            "carried_certificate_rounds": sorted({row[0] for row in certificates}),
            "carried_certificate_rows": len(certificates),
            "carried_reduced_member_count": len(reduced),
            "carried_reduced_members_sha256": digest(tuple(sorted(reduced))),
            "carried_state_bound": prior,
            "raw_region_maximum": max(raw.values()),
            "prior_member_certificate_calls": 0,
            "initial_maximizing_members": [
                member_record(row) for row in region if bounds[row.witness_counts] == prior
            ],
            "initial_maximizing_members_raw": all(
                bounds[row.witness_counts] == raw[row.witness_counts]
                for row in region
                if bounds[row.witness_counts] == prior
            ),
            "region_compressed_member_count": len(region),
            "region_type_vector_count": sum(row.represented_vector_count for row in region),
        }
    )


def refine_state_owner(chase: Chase, owner_id: str) -> None:
    """Certify one maximizing member while the state owns R3, then reselect."""

    chase.require_dispatch(owner_id)
    if owner_class(owner_id) != STATE_CLASS:
        raise AssertionError("state proof requested for a non-state owner")
    prior = dict(chase.states)[owner_id]
    if select_owner(chase) != owner_id or prior < chase.tail_bound:
        raise AssertionError("state work below the tail is forbidden")
    threshold = chase.competitor(owner_id)
    restore_owner_region(chase, owner_id)
    region = state_region(owner_id)
    bounds = chase.state_region_bounds[owner_id]
    if max(bounds.values()) != prior:
        raise AssertionError("state term differs from its compressed region maximum")
    counts = min(vector for vector, value in bounds.items() if value == prior)
    member = next(row for row in region if row.witness_counts == counts)
    if bounds[counts] != r14.raw_bound(member):
        # The rational certificate is already spent on this member: exact S4 at
        # the S3 maximizers is the next route, and it is reported, not assumed.
        raise r15.RationalRouteExhausted(owner_id)
    vectors = r17.represented_vectors((member,))[counts]
    certificates: list[dict[str, Any]] = []
    witnesses: list[dict[str, Any]] = []
    for vector in vectors:
        support = r12.construct_support_witness(vector)
        if support is None or not r8.validate_support_assignment(vector, support):
            raise AssertionError("a represented vector has no verified support witness")
        certificates.append(r14.moment_certificate(vector))
        witnesses.append({"counts": sparse(vector), "support_witness": support})
    correction = max(
        member.applied_residual_union_penalty,
        min(int(row["correction_lower_bound"]) for row in certificates),
    )
    bound = min(
        prior, r14.joint_constant() - member.anchor_pair_s2 + member.anchor_triple_s3 - correction
    )
    chase.member_dispatches.append(
        {
            "owner_id": owner_id,
            "witness_counts": sparse(counts),
            "member_prior_bound": prior,
            "member_rational_bound": bound,
            "tail_bound_at_dispatch": chase.tail_bound,
            "active_competing_threshold": threshold,
        }
    )
    if bound >= prior:
        raise r15.RationalRouteExhausted(owner_id)
    before, previous = chase.owners, chase.bound
    bounds[counts] = bound
    new_bound = max(bounds.values())
    chase.states = tuple(
        (identifier, new_bound if identifier == owner_id else value)
        for identifier, value in chase.states
    )
    chase.state_records.append(
        {
            "owner_id": owner_id,
            "owner_set_at_dispatch": list(before),
            "prior_bound": prior,
            "new_bound": new_bound,
            "active_competing_threshold": threshold,
            "tail_bound_at_dispatch": chase.tail_bound,
            "member": member_record(member),
            "member_prior_relaxation": "CARRIED_RAW_R7_REGION_MEMBER",
            "represented_vector_count": len(vectors),
            "compressed_member": len(vectors) > 1,
            "vector_certificates": certificates,
            "support_witnesses": witnesses,
            "member_prior_bound": prior,
            "member_new_bound": bound,
            "member_certified_correction": correction,
            "state_term_after": new_bound,
            "state_at_or_below_tail_after": new_bound <= chase.tail_bound,
            "tightening_route": RATIONAL_MOMENT_ROUTE,
            "tightening_priority": "a_EXISTING_RATIONAL_MOMENT_CERTIFICATE",
            "region_sha256": region_sha256(region),
            "no_other_state_terms_refined": True,
        }
    )
    chase.record_event(f"state:{owner_id}", before, previous)


@cache
def r12_aggregate_rows() -> tuple[dict[str, Any], ...]:
    """R12's stored levels behind the aggregate term (R16 already split its owner level)."""

    rows = tuple(
        row
        for row in cast(list[dict[str, Any]], stored_result(R12_RESULT_RELATIVE)["LOSS_LEVEL_ROWS"])
        if int(row["local_loss"]) != r16.R12_OWNER_LOSS and row["maximum_vector_bound"] is not None
    )
    if max(int(row["maximum_vector_bound"]) for row in rows) != START_CLASSIFIED_MAXIMUM:
        raise AssertionError("the carried R12 aggregate differs from R12's stored levels")
    return rows


def recover_r12_aggregate_level(chase: Chase) -> None:
    """Split only the aggregate's owner level into vector terms, checked against R12."""

    chase.require_dispatch(AGGREGATE_ID)
    if select_owner(chase) != AGGREGATE_ID:
        raise AssertionError("aggregate recovery requires the selected classified owner")
    prior = chase.classified_terms[AGGREGATE_ID]
    remaining = [
        row for row in r12_aggregate_rows() if int(row["local_loss"]) not in chase.split_r12_levels
    ]
    if max(int(row["maximum_vector_bound"]) for row in remaining) != prior:
        raise AssertionError("the carried R12 aggregate differs from its unsplit levels")
    row = min(
        (row for row in remaining if int(row["maximum_vector_bound"]) == prior),
        key=lambda row: int(row["local_loss"]),
    )
    loss = int(row["local_loss"])
    if not loss < r13.START_UNCLASSIFIED_LOSS or loss >= START_LOSS:
        raise AssertionError("aggregate recovery is limited to R12's stored levels")
    if int(row["witness_realized"]) != int(row["vector_count"]):
        raise r22.ClassifiedScopeRequired(AGGREGATE_ID)
    losses = r6.local_losses(r5.anchor_incidence_profiles())
    vectors = tuple(sorted(r16.iter_interval_vectors(losses, r12.OUTSIDE_TICKET_COUNT, loss, loss)))
    corrections = {
        counts: r6.type_count_envelope(counts).combined_pair_penalty for counts in vectors
    }
    terms = {
        r13.vector_id(counts, loss): chase.baseline - loss - correction
        for counts, correction in corrections.items()
    }
    if (
        len(vectors) != int(row["vector_count"])
        or max(terms.values()) != int(row["maximum_vector_bound"])
        or min(corrections.values()) != int(row["minimum_correction"])
        or set(terms) & set(chase.classified_terms)
    ):
        raise AssertionError("the recovered R12 level differs from its stored census")
    before, previous = chase.owners, chase.bound
    chase.classified_terms.update(terms)
    chase.split_r12_levels.append(loss)
    rest = [int(other["maximum_vector_bound"]) for other in remaining if other is not row]
    if rest:
        chase.classified_terms[AGGREGATE_ID] = max(rest)
    else:
        del chase.classified_terms[AGGREGATE_ID]
    chase.sync_classified_maximum()
    chase.r12_recoveries.append(
        {
            "owner_id": AGGREGATE_ID,
            "owner_set_at_dispatch": list(before),
            "aggregate_prior_bound": prior,
            "aggregate_bound_after": chase.classified_terms.get(AGGREGATE_ID),
            "recovered_level": loss,
            "stored_level_row": row,
            "vector_count": len(vectors),
            "counts_sha256": digest(vectors),
            "recovered_terms": [{"stable_id": key, "bound": value} for key, value in terms.items()],
            "relaxation": "R12_R6_COMBINED_PAIR_PENALTY_CHECKED_AGAINST_STORED_MAX_AND_MIN",
            "classification_calls": 0,
            "support_constructions": 0,
            "certificates_issued": 0,
        }
    )
    chase.record_event(f"classified-recover:{AGGREGATE_ID}:L{loss}", before, previous)


def refine_classified_owner(chase: Chase, owner_id: str) -> None:
    if owner_id == AGGREGATE_ID:
        recover_r12_aggregate_level(chase)
    else:
        r22.refine_classified_owner(chase, owner_id)


def next_tail_level(chase: Chase) -> tuple[int, tuple[CountVector, ...], int]:
    chase.require_dispatch(TAIL_ID)
    require_unclassified_cursor(chase.next_loss)
    if select_owner(chase) != TAIL_ID or chase.tail_bound < chase.competitor(TAIL_ID):
        raise AssertionError("tail descent below the active competing bound is forbidden")
    losses = r6.local_losses(r5.anchor_incidence_profiles())
    # The tail may descend only to the loss where it meets the live competitor.
    entitled = chase.baseline - chase.competitor(TAIL_ID)
    if chase.tail_window_upper > entitled:
        chase.tail_window = {
            loss: vectors for loss, vectors in chase.tail_window.items() if loss <= entitled
        }
        chase.tail_window_upper = entitled
    if chase.next_loss > chase.tail_window_upper:
        upper = min(chase.next_loss + TAIL_WINDOW_WIDTH, entitled)
        grouped: dict[int, list[CountVector]] = {}
        for counts in r16.iter_interval_vectors(
            losses, r12.OUTSIDE_TICKET_COUNT, chase.next_loss, upper
        ):
            grouped.setdefault(r12.local_loss(counts, losses), []).append(counts)
        chase.tail_window = {loss: tuple(sorted(rows)) for loss, rows in grouped.items()}
        chase.tail_window_upper = upper
        chase.tail_windows.append(
            {
                "lower": chase.next_loss,
                "upper": upper,
                "entitled_upper": entitled,
                "attained_levels": len(grouped),
                "vector_count": sum(len(rows) for rows in grouped.values()),
            }
        )
    vectors = chase.tail_window.pop(chase.next_loss, ())
    if not vectors or any(loss < chase.next_loss for loss in chase.tail_window):
        raise AssertionError("the cursor must be an attained loss")
    lookahead = (
        min(chase.tail_window)
        if chase.tail_window
        else r16.next_attained_loss(losses, r12.OUTSIDE_TICKET_COUNT, chase.tail_window_upper + 1)
    )
    if lookahead <= chase.next_loss:
        raise AssertionError("the attained tail cursor must strictly advance")
    return chase.next_loss, vectors, lookahead


def classify_new_tail_vector(
    counts: CountVector, baseline: int, threshold: int
) -> ClassifiedVector:
    """Existing R6 stack, plus R8's four-ticket floor only above the live competitor."""

    loss = r12.local_loss(counts, r6.local_losses(r5.anchor_incidence_profiles()))
    require_unclassified_cursor(loss)
    return r13.classify_vector(counts, baseline, threshold)


def compact_vector_record(row: ClassifiedVector) -> dict[str, Any]:
    """The structural record with its verified support witness kept as a digest."""

    record = asdict(row)
    witness = record.pop("witness")
    record["witness_sha256"] = None if witness is None else digest(row.witness)
    return record


def advance_tail(chase: Chase) -> None:
    loss, vectors, next_loss = next_tail_level(chase)
    before, previous = chase.owners, chase.bound
    competitor = chase.competitor(TAIL_ID)
    if chase.tail_bound == competitor:
        chase.tail_tie_dispatches += 1
    rows = tuple(classify_new_tail_vector(counts, chase.baseline, competitor) for counts in vectors)
    for row in rows:
        if row.local_loss != loss or row.status not in (r12.WITNESS_REALIZED, r12.ELIMINATED):
            raise AssertionError("an unresolved or misplaced tail vector cannot be certified")
        if row.status == r12.WITNESS_REALIZED and (
            row.witness is None or not r8.validate_support_assignment(row.counts, row.witness)
        ):
            raise AssertionError("tail support witness failed independent validation")
        if row.vector_id in chase.classified_terms:
            raise AssertionError("a previously classified vector cannot be reclassified")
    for row in rows:
        if row.vector_bound is not None:
            if row.vector_bound > chase.baseline - loss:
                raise AssertionError("a certified correction cannot be negative")
            chase.classified_terms[row.vector_id] = row.vector_bound
            chase.vector_records[row.vector_id] = asdict(row)
        chase.tail_vector_records.append(compact_vector_record(row))
    chase.sync_classified_maximum()
    chase.next_loss = next_loss
    chase.tail_records.append(
        {
            "local_loss": loss,
            "next_unclassified_loss": next_loss,
            "vector_count": len(rows),
            "counts_sha256": digest(tuple(row.counts for row in rows)),
            "support_witness_sha256": digest(tuple(row.witness for row in rows)),
            "classified_rows_sha256": digest(rows),
            "maximum_new_vector_bound": max(
                (row.vector_bound for row in rows if row.vector_bound is not None), default=None
            ),
            "realizable_count": sum(row.status == r12.WITNESS_REALIZED for row in rows),
            "unrealizable_count": sum(row.status == r12.ELIMINATED for row in rows),
            "unresolved_count": 0,
            "four_ticket_applied_count": sum(
                row.four_ticket_status == r13.FOUR_TICKET_APPLIED for row in rows
            ),
            "active_competing_threshold": competitor,
            "four_ticket_threshold": competitor,
            "owner_set_at_dispatch": list(before),
        }
    )
    chase.record_event(f"tail:L{loss}", before, previous)


def run_chase(
    *, wall_budget: float = PROOF_WALL_BUDGET_SECONDS, action_limit: int | None = None
) -> tuple[Chase, str, float]:
    """Chase the live owner until R4 or the wall budget.

    ``action_limit`` is the deterministic replay of a stored run: it stops after
    exactly that many owner actions instead of reading the clock.
    """

    if not 0 < wall_budget <= PROOF_WALL_BUDGET_SECONDS:
        raise ValueError("proof wall budget must be positive and at most 3600 seconds")
    if action_limit is not None and action_limit < 0:
        raise ValueError("a replay action limit cannot be negative")
    started = time.monotonic()
    canonical_primitives()
    prior_level_fingerprints()
    chase = initial_chase()
    while True:
        stop = chase.stop_condition()
        if stop is not None:
            return chase, stop, time.monotonic() - started
        if action_limit is None:
            if time.monotonic() - started >= wall_budget:
                return chase, STOP_C, time.monotonic() - started
        elif len(chase.events) >= action_limit:
            return chase, STOP_C, time.monotonic() - started
        owner = select_owner(chase)
        try:
            if owner == TAIL_ID:
                advance_tail(chase)
            elif owner_class(owner) == STATE_CLASS:
                refine_state_owner(chase, owner)
            else:
                refine_classified_owner(chase, owner)
        except r15.RationalRouteExhausted:
            chase.exhausted_owner = owner
            return chase, STOP_EXHAUSTED, time.monotonic() - started
        except (r22.StateScopeRequired, r22.ClassifiedScopeRequired):
            chase.scope_owner = owner
            return chase, STOP_SCOPE, time.monotonic() - started


def tail_crossover(chase: Chase) -> dict[str, Any]:
    """Phase 1: the tail-only prefix and the owner that ended it."""

    events = chase.events
    first = next(
        (index for index, row in enumerate(events) if not str(row["action"]).startswith("tail:")),
        len(events),
    )
    levels = chase.tail_records[:first]
    end = events[first - 1] if first else None
    end_owners = [] if end is None else cast(list[str], end["to"])
    next_loss = START_LOSS if end is None else int(end["next_unclassified_loss"])
    newest = [
        int(row["maximum_new_vector_bound"])
        for row in levels
        if row["maximum_new_vector_bound"] is not None
    ]
    if any(owner_class(owner) == CLASSIFIED_CLASS for owner in end_owners):
        reason = "CLASSIFIED_VECTOR_ABOVE_STATE_OWNER"
    elif any(owner_class(owner) == STATE_CLASS for owner in end_owners):
        reason = "STATE_OWNER_AT_CROSSOVER"
    else:
        reason = "STOPPED_BEFORE_CROSSOVER"
    return {
        "tail_base_constant": chase.baseline,
        "start_next_unclassified_loss": START_LOSS,
        "start_unclassified_tail_bound": START_UNCLASSIFIED_TAIL_BOUND,
        "next_state_owner_id": START_STATE_ID,
        "next_state_bound": START_STATE_BOUND,
        "state_crossover_loss": STATE_CROSSOVER_LOSS,
        "crossover_interval": STATE_CROSSOVER_INTERVAL,
        "phase1_tail_levels": len(levels),
        "phase1_tail_vectors": sum(int(row["vector_count"]) for row in levels),
        "phase1_level_range": (
            [levels[0]["local_loss"], levels[-1]["local_loss"]] if levels else None
        ),
        "phase1_last_level_below_crossover": (
            bool(levels) and int(levels[-1]["local_loss"]) < STATE_CROSSOVER_LOSS
        ),
        "phase1_next_unclassified_loss": next_loss,
        "phase1_tail_bound_after": chase.baseline - next_loss,
        "phase1_maximum_new_vector_bound": max(newest, default=None),
        "phase1_new_vector_above_state_max": any(value > START_STATE_BOUND for value in newest),
        "phase1_end_owner_ids": end_owners,
        "phase1_end_reason": reason,
        "phase2_state_owner_set": [
            owner for owner in end_owners if owner_class(owner) == STATE_CLASS
        ],
    }


def family_maximum(chase: Chase) -> dict[str, Any]:
    """Recompute the three family maxima from the raw terms, not the cached fields."""

    state = max(bound for _, bound in chase.states)
    classified = max(chase.classified_terms.values())
    tail = chase.baseline - chase.next_loss
    terms = [*chase.states, (TAIL_ID, tail), *chase.classified_terms.items()]
    return {
        "STATE_MAX_BOUND": state,
        "UNCLASSIFIED_TAIL_BOUND": tail,
        "MAX_CLASSIFIED_TAIL_VECTOR_BOUND": classified,
        "R3_BOUND": max(state, tail, classified),
        "OWNER_IDS": list(r13.identify_owner_set(terms)),
    }


def build_result(
    *, wall_budget: float = PROOF_WALL_BUDGET_SECONDS, action_limit: int | None = None
) -> dict[str, Any]:
    chase, stop, wall = run_chase(wall_budget=wall_budget, action_limit=action_limit)
    initial = initial_chase()
    initial_states = dict(initial.states)
    state_ids = list(dict.fromkeys(str(row["owner_id"]) for row in chase.state_records))
    refined_vectors = {str(row["owner_id"]) for row in chase.classified_records}
    new_ids = {str(row["vector_id"]) for row in chase.tail_vector_records}
    surviving_ids = {
        str(row["vector_id"])
        for row in chase.tail_vector_records
        if row["vector_bound"] is not None
    }
    split_ids = {
        str(term["stable_id"])
        for row in chase.r12_recoveries
        for term in cast(list[dict[str, Any]], row["recovered_terms"])
    }
    retained = set(initial.classified_terms) - (
        {AGGREGATE_ID} if AGGREGATE_ID not in chase.classified_terms else set()
    )
    recomputed = family_maximum(chase)
    crossover = tail_crossover(chase)
    if (
        chase.bound != max(chase.tail_bound, chase.classified_maximum[1], chase.state_max)
        or recomputed["R3_BOUND"] != chase.bound
        or recomputed["OWNER_IDS"] != list(chase.owners)
        or recomputed["STATE_MAX_BOUND"] != chase.state_max
        or recomputed["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"] != chase.classified_maximum[1]
        or any(
            initial_states[identifier] != bound and identifier not in state_ids
            for identifier, bound in chase.states
        )
        or any(
            chase.classified_terms.get(identifier) != bound
            and identifier not in refined_vectors
            and identifier != AGGREGATE_ID
            for identifier, bound in initial.classified_terms.items()
        )
        or set(chase.classified_terms) != retained | surviving_ids | split_ids
        or new_ids & (set(initial.classified_terms) | split_ids)
        or any(int(row["local_loss"]) < START_LOSS for row in chase.tail_records)
        or any(
            chase.baseline - int(row["local_loss"]) < int(row["active_competing_threshold"])
            for row in chase.tail_records
        )
        or any(
            not START_LOSS <= int(row["lower"]) <= int(row["upper"]) <= int(row["entitled_upper"])
            for row in chase.tail_windows
        )
        or any(
            not any(
                int(window["lower"]) <= int(row["local_loss"]) <= int(window["upper"])
                for window in chase.tail_windows
            )
            for row in chase.tail_records
        )
        or any(
            int(row["member_prior_bound"]) < int(row["tail_bound_at_dispatch"])
            for row in chase.member_dispatches
        )
        or not 0
        <= len(chase.member_dispatches) - len(chase.state_records)
        <= (stop == STOP_EXHAUSTED)
        or (
            crossover["phase1_end_reason"] == "STATE_OWNER_AT_CROSSOVER"
            and (
                crossover["phase1_next_unclassified_loss"] < STATE_CROSSOVER_LOSS
                or not crossover["phase1_last_level_below_crossover"]
            )
        )
    ):
        raise AssertionError("the final maximum or an owner-only work guard failed")
    classes = owner_classes(chase.owners)
    transitions = [row for row in chase.events if row["from"] != row["to"]]
    region_records: list[dict[str, Any]] = []
    for identifier in chase.state_region_bounds:
        region = state_region(identifier)
        bounds = chase.state_region_bounds[identifier]
        region_records.append(
            {
                "owner_id": identifier,
                "region_sha256": region_sha256(region),
                "complete_region_members": [
                    {
                        "witness_counts": sparse(row.witness_counts),
                        "represented_vector_count": row.represented_vector_count,
                        "raw_bound": r14.raw_bound(row),
                        "final_bound": bounds[row.witness_counts],
                    }
                    for row in region
                ],
                "certified_member_count": sum(
                    bounds[row.witness_counts] != r14.raw_bound(row) for row in region
                ),
                "r24_certified_member_count": sum(
                    row["owner_id"] == identifier for row in chase.state_records
                ),
                "final_state_bound": max(bounds.values()),
            }
        )
    status = {STOP_A: "SUCCESS_A", STOP_C: "SUCCESS_C"}.get(stop, stop)
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": status,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_BRANCH": TASK_BRANCH,
        "R3_AUTHORITY": {
            "authority_head": BASE_HEAD,
            "authority_task_id": r23.TASK_ID,
            "authority_result_sha256": UPSTREAM_SHA256[R23_RESULT_RELATIVE],
        },
        "R23_FINGERPRINT_STATUS": "PASS",
        "START_R3_BOUND": START_R3_BOUND,
        "START_OWNER_IDS": [TAIL_ID],
        "CANONICAL_PRIMITIVES": canonical_primitives(),
        "CANONICAL_PRIMITIVE_STATUS": "PASS",
        "UPSTREAM_FINGERPRINTS_SHA256": verify_upstream_fingerprints(),
        "PRIOR_LEVEL_FINGERPRINTS": prior_level_fingerprints(),
        "TAIL_CROSSOVER": crossover,
        "CARRIED_OWNER_REGION_CERTIFICATES": chase.carried_regions,
        "R7_FINGERPRINT_STATUS": "PASS" if chase.state_region_bounds else "NOT_REQUIRED",
        "R7_CENSUS_PIN": pinned_r7_census() if chase.state_region_bounds else None,
        "OWNER_DISPATCH_RULE": (
            "classified owners first (the R12 aggregate is split one stored level at a time); "
            "state owners including a state/tail tie next; tail only at or above the live "
            "competitor; one maximizing state member per action"
        ),
        "OWNER_ACTIONS_EXECUTED": len(chase.events),
        "OWNER_TRANSITION_COUNT": len(transitions),
        "OWNER_TRANSITION_LIMIT": None,
        "OWNER_TRANSITION_DEFINITION": "EXACT_OWNER_SET_CHANGE_INCLUDING_TIED_SET_CHANGES",
        "OWNER_CLASS_SEQUENCE": [
            owner_classes(initial.owners),
            *[row["to_owner_classes"] for row in transitions],
        ],
        "OWNER_TRANSITIONS": transitions,
        "OWNER_ACTION_TRAJECTORY": chase.events,
        "STATE_OWNERS_PROCESSED": len(state_ids),
        "PROCESSED_STATE_OWNER_IDS": state_ids,
        "STATE_MEMBERS_CERTIFIED": len(chase.state_records),
        "COMPRESSED_MEMBERS_RECOVERED": sum(
            bool(row["compressed_member"]) for row in chase.state_records
        ),
        "STATE_OWNER_CERTIFICATES": chase.state_records,
        "STATE_MEMBER_DISPATCHES": chase.member_dispatches,
        "STATE_REGION_CERTIFICATES": region_records,
        "TIGHTENING_ROUTES_USED": sorted(
            {str(row["tightening_route"]) for row in chase.state_records}
            | {str(row["tightening_route"]) for row in chase.classified_records}
        ),
        "HIGHER_ORDER_ESCALATION": (
            "NOT_REQUIRED_RATIONAL_MOMENT_CERTIFIED_EVERY_DISPATCHED_OWNER"
            if chase.exhausted_owner is None
            else "EXACT_S4_AT_S3_MAXIMIZERS_REQUIRED_AT_EXHAUSTED_OWNER"
        ),
        "EXHAUSTED_OWNER_ID": chase.exhausted_owner,
        "SCOPE_OWNER_ID": chase.scope_owner,
        "TAIL_LEVELS_PROCESSED": len(chase.tail_records),
        "TAIL_VECTORS_PROCESSED": len(chase.tail_vector_records),
        "TAIL_TIE_DISPATCHES": chase.tail_tie_dispatches,
        "TAIL_WINDOW_WIDTH": TAIL_WINDOW_WIDTH,
        "TAIL_ENUMERATION_WINDOWS": chase.tail_windows,
        "TAIL_LEVEL_CERTIFICATES": chase.tail_records,
        "NEW_TAIL_VECTOR_STRUCTURAL_RECORDS": chase.tail_vector_records,
        "CLASSIFIED_VECTOR_OWNERS_PROCESSED": len(refined_vectors),
        "CLASSIFIED_OWNER_CERTIFICATES": chase.classified_records,
        "R12_AGGREGATE_LEVELS_RECOVERED": len(chase.r12_recoveries),
        "R12_AGGREGATE_RECOVERIES": chase.r12_recoveries,
        "CURRENT_STATE_TERMS": [
            {"stable_id": identifier, "bound": bound} for identifier, bound in chase.states
        ],
        "CURRENT_CLASSIFIED_TERMS": [
            {"stable_id": identifier, "bound": bound}
            for identifier, bound in chase.classified_terms.items()
        ],
        "FINAL_FAMILY_MAX_RECOMPUTATION": recomputed,
        "FINAL_BOUND_OWNER_CLASS": classes[0] if len(classes) == 1 else "TIED_OWNER_SET",
        "FINAL_OWNER_CLASSES": classes,
        "FINAL_OWNER_IDS": list(chase.owners),
        "NEXT_LOAD_BEARING_OWNER_ID": select_owner(chase),
        "STATE_MAX_BOUND": chase.state_max,
        "STATE_MAX_OWNER_IDS": list(r13.identify_owner_set(chase.states)),
        "UNCLASSIFIED_TAIL_BOUND": chase.tail_bound,
        "NEXT_UNCLASSIFIED_LOSS": chase.next_loss,
        "MAX_CLASSIFIED_TAIL_VECTOR_BOUND": chase.classified_maximum[1],
        "MAX_CLASSIFIED_TAIL_VECTOR_ID": chase.classified_maximum[0],
        "R3_BOUND": chase.bound,
        "R3_DROP": START_R3_BOUND - chase.bound,
        "R3_FORMULA": (
            "max(STATE_TERMS, UNCLASSIFIED_TAIL_BOUND, MAX_CLASSIFIED_TAIL_VECTOR_BOUND)"
        ),
        "R3_STATUS": "CERTIFIED_OWNER_ONLY_RATIONAL_MOMENT_AND_ATTAINED_TAIL_BOUND",
        "R4_REFERENCE_BOUND": R4_REFERENCE_BOUND,
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": chase.bound - INCUMBENT,
        "GAP_TO_R4_REFERENCE": chase.bound - R4_REFERENCE_BOUND,
        "STOP_CONDITION": stop,
        "SUCCESS_A": stop == STOP_A,
        "SUCCESS_B": stop == STOP_A,
        "SUCCESS_B_DEFINITION": (
            "R3 at or below R4_REFERENCE makes R4 (or a certified leaf at or below it) the "
            "Family-A owner; it is the same event as SUCCESS A"
        ),
        "SUCCESS_C": stop == STOP_C,
        "PROOF_WALL_SECONDS": wall,
        "PROOF_WALL_BUDGET_SECONDS": wall_budget,
        "SOLVER_STATUS": "NOT_DISPATCHED_EXACT_RATIONAL_CERTIFICATES_SUFFICIENT",
        "SOLVER_CONFIGURED_WALL_LIMIT": None,
        "SOLVER_ACTUAL_WALL_TIME": 0.0,
        "OUTCOME_HISTOGRAM_USED": False,
        "PRIOR_TAIL_LEVELS_ENUMERATED": 0,
        "PRIOR_VECTORS_RECLASSIFIED": 0,
        "NON_OWNER_STATE_TERMS_CHANGED": 0,
        "PRIOR_CLASSIFIED_TERMS_CHANGED": len(refined_vectors & set(initial.classified_terms)),
        "GENERIC_FRONTIER_CENSUS_CALLS": 0,
        "GENERIC_CLASSIFIED_CENSUS_CALLS": 0,
        "RESULT_ENCODING": "COMPACT_JSON_TAIL_SUPPORT_WITNESSES_AS_SHA256",
        "WORKTREE_DISPOSITION": "RETAIN",
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


PREFIX_KEYS = (
    "OWNER_ACTION_TRAJECTORY",
    "TAIL_LEVEL_CERTIFICATES",
    "NEW_TAIL_VECTOR_STRUCTURAL_RECORDS",
    "STATE_OWNER_CERTIFICATES",
    "STATE_MEMBER_DISPATCHES",
    "CARRIED_OWNER_REGION_CERTIFICATES",
    "CLASSIFIED_OWNER_CERTIFICATES",
    "R12_AGGREGATE_RECOVERIES",
    "TAIL_ENUMERATION_WINDOWS",
)


def encode(result: dict[str, Any]) -> str:
    return json.dumps(result, separators=(",", ":")) + "\n"


def replay_stored_result(prefix_actions: int | None = None) -> dict[str, Any]:
    """Replay the stored run by its action count; a prefix replay checks the prefix only."""

    stored = cast(dict[str, Any], json.loads(RESULT_PATH.read_text(encoding="utf-8")))
    total = int(stored["OWNER_ACTIONS_EXECUTED"])
    # A non-budget stop happens while attempting action ``total + 1``.
    full = total if stored["STOP_CONDITION"] == STOP_C else total + 1
    limit = full if prefix_actions is None else min(prefix_actions, total)
    observed = cast(
        dict[str, Any],
        json.loads(
            encode(
                build_result(
                    wall_budget=float(stored["PROOF_WALL_BUDGET_SECONDS"]), action_limit=limit
                )
            )
        ),
    )
    if limit == full:
        mismatched = [
            key for key in stored if key != "PROOF_WALL_SECONDS" and observed[key] != stored[key]
        ]
    else:
        mismatched = [
            key
            for key in PREFIX_KEYS
            if observed[key] != stored[key][: len(observed[key])]
            or (key == "OWNER_ACTION_TRAJECTORY" and len(observed[key]) != limit)
        ]
    return {
        "replayed_actions": limit,
        "stored_actions": total,
        "full_replay": limit == full,
        "mismatched_keys": mismatched,
        "status": "PASS" if not mismatched else "FAIL",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--wall-budget", type=float, default=PROOF_WALL_BUDGET_SECONDS)
    parser.add_argument("--replay", action="store_true")
    parser.add_argument("--replay-prefix", type=int, default=None)
    options = parser.parse_args()
    if options.replay:
        print(json.dumps(replay_stored_result(options.replay_prefix), indent=2))
        return
    result = build_result(wall_budget=options.wall_budget)
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
                "FINAL_OWNER_IDS": result["FINAL_OWNER_IDS"],
                "STATE_MAX_OWNER_IDS": result["STATE_MAX_OWNER_IDS"],
                "TAIL_CROSSOVER": result["TAIL_CROSSOVER"],
                "OWNER_CLASS_SEQUENCE_HEAD": result["OWNER_CLASS_SEQUENCE"][:40],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
