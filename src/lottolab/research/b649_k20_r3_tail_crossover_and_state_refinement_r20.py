"""Walk the R19 tail to the state crossover, then refine only the live state owner.

R19 left the unclassified tail as the unique owner at ``365048628 - 8529836``.
The tail is resumed exactly at that cursor and descends one attained level at a
time only while it strictly owns R3, so it stops at the first level whose tail
term is at or below the live competitor.  Every new vector gets its R6
pair/triple correction, and R8's four-ticket floor only while it is still above
the live state maximum.

The state owner is an envelope over its frozen compressed R7 region.  Only its
maximizing member is reconstructed and certified with R14's rational moment
dual; every vector represented by a compressed member is recovered and
certified.  The owner is reselected after each strict improvement.  A tail
owner resumes descent, another state owner is switched to, and a classified
vector owner is identified and not refined (Success C).  No transition count
stops the run.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass, field, replace
from functools import cache
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_r3_cursor_resolved_three_class_owner_chase_r19 as r19

r18 = r19.r18
r17 = r19.r17
r16 = r19.r16
r15 = r19.r15
r14 = r19.r14
r13 = r19.r13
r12 = r19.r12
r8 = r19.r8
r7 = r19.r7
r6 = r19.r6
r5 = r19.r5
CountVector = r19.CountVector
StateTerms = r19.StateTerms
dense, sparse, digest = r19.dense, r19.sparse, r19.digest
owner_class, owner_classes, select_owner = r19.owner_class, r19.owner_classes, r19.select_owner
TASK_ID = "B649_K20_R3_TAIL_CROSSOVER_AND_STATE_REFINEMENT_R20"
BASE_HEAD = "0f76a7c77013670d2bd35f334b245e6bf8d5cf6f"
BASE_TREE = "2743bca4b6924194d76ca6935ddd23fd46f5a4cf"
TASK_BRANCH = "codex/b649-k20-r3-tail-crossover-and-state-refinement-r20"
START_LOSS = 8_529_836
START_R3_BOUND = 356_518_792
START_UNCLASSIFIED_TAIL_BOUND = 356_518_792
START_STATE_MAX_BOUND = 356_505_100
START_STATE_OWNER_IDS = ("state:s2-12692531-s3-681744",)
START_CLASSIFIED_MAXIMUM = 356_501_945
START_CLASSIFIED_ID = "tail-vector:L6742484:0x6,1x11,6x1"
STATE_CROSSOVER_LOSS = 8_543_528
TAIL_BASE_CONSTANT = 365_048_628
R4_REFERENCE_BOUND, INCUMBENT = 350_545_749, 313_239_661
DROP_TARGET = 100_000
PROOF_WALL_BUDGET_SECONDS = 3_600.0
TAIL_ID = r19.TAIL_ID
STOP_A = r19.STOP_A
STOP_B = r19.STOP_B
STOP_C = "C_STATE_OWNER_REFINED_BELOW_NEXT_COMPETITOR_NEXT_OWNER_IDENTIFIED"
STOP_D = "D_PROOF_WALL_BUDGET_EXHAUSTED_CURRENT_OWNER_RETAINED"
STOP_EXHAUSTED = r19.STOP_EXHAUSTED
STOP_NEW_VECTOR = "TAIL_STOPPED_NEW_VECTOR_ABOVE_STATE_MAX"
STOP_OUT_OF_SCOPE = "CLASSIFIED_OWNER_BEFORE_ANY_STATE_REFINEMENT"
RATIONAL_MOMENT_ROUTE = r19.RATIONAL_MOMENT_ROUTE
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_PATH = REPO_ROOT / (
    "docs/research/matrix-native-results/"
    "b649-k20-r3-tail-crossover-and-state-refinement-r20-result.json"
)
UPSTREAM_SHA256 = {
    "src/lottolab/research/b649_k20_r3_cursor_resolved_three_class_owner_chase_r19.py": (
        "dfe99452a5dfc32a1aca697729975592dd02afd14726d04077c15f2297d65e8a"
    ),
    "docs/research/matrix-native-results/"
    "b649-k20-r3-cursor-resolved-three-class-owner-chase-r19-result.json": (
        "fe8018e8ba7ca80a6c8d8eb781dcf1c9f0c48f114a4a43ea63f39b45102e6850"
    ),
}


def verify_upstream_fingerprints() -> dict[str, str]:
    observed = {
        relative: sha256((REPO_ROOT / relative).read_bytes()).hexdigest()
        for relative in UPSTREAM_SHA256
    }
    if observed != UPSTREAM_SHA256:
        raise AssertionError(f"R19 authority fingerprint mismatch: {observed}")
    # These validate certificate files, never the prior-level enumerators.
    r19.verify_upstream_fingerprints()
    return observed


@cache
def authority() -> dict[str, Any]:
    verify_upstream_fingerprints()
    stored = cast(dict[str, Any], json.loads(r19.RESULT_PATH.read_text(encoding="utf-8")))
    expected = {
        "TASK_ID": r19.TASK_ID,
        "TASK_STATUS": "SUCCESS_C",
        "R3_BOUND": START_R3_BOUND,
        "UNCLASSIFIED_TAIL_BOUND": START_UNCLASSIFIED_TAIL_BOUND,
        "NEXT_UNCLASSIFIED_LOSS": START_LOSS,
        "STATE_MAX_BOUND": START_STATE_MAX_BOUND,
        "MAX_CLASSIFIED_TAIL_VECTOR_BOUND": START_CLASSIFIED_MAXIMUM,
        "MAX_CLASSIFIED_TAIL_VECTOR_ID": START_CLASSIFIED_ID,
        "FINAL_OWNER_IDS": [TAIL_ID],
        "STATE_OWNERS_PROCESSED": 0,
    }
    if any(stored[key] != value for key, value in expected.items()):
        raise AssertionError("R19 authority differs from the R20 Packet")
    return stored


def canonical_primitives() -> dict[str, int]:
    observed = r19.canonical_primitives()
    if observed != {
        "SINGLE_TICKET_ANY_PRIZE": 18_611_432,
        "PAIR_INTERSECTION_COST[6]": 18_611_432,
        "K20_S1": 372_228_640,
    }:
        raise AssertionError("canonical primitive preflight failed")
    return observed


def canonical_baseline() -> int:
    baseline = canonical_primitives()["K20_S1"] - r13.FIXED_CERTIFIED_LOSS
    if baseline != TAIL_BASE_CONSTANT:
        raise AssertionError("the independent tail-base arithmetic failed")
    if baseline - START_LOSS != START_UNCLASSIFIED_TAIL_BOUND:
        raise AssertionError("the tail was not recomputed from the R19 cursor")
    if baseline - START_STATE_MAX_BOUND != STATE_CROSSOVER_LOSS:
        raise AssertionError("the independent state crossover arithmetic failed")
    if baseline - (STATE_CROSSOVER_LOSS - 1) != START_STATE_MAX_BOUND + 1:
        raise AssertionError("the state crossover is not the first integer threshold")
    return baseline


def require_unclassified_cursor(loss: int, action: str) -> None:
    if loss < START_LOSS:
        raise AssertionError(f"prior tail {action}")


@cache
def prior_level_fingerprints() -> dict[str, Any]:
    """Validate R19's certified level chain from its pinned file, with no enumeration."""

    levels = cast(list[dict[str, Any]], authority()["TAIL_LEVEL_CERTIFICATES"])
    chain = [int(row["local_loss"]) for row in levels]
    if (
        chain[0] != r19.START_LOSS
        or any(
            int(row["next_unclassified_loss"]) != following
            for row, following in zip(levels, chain[1:], strict=False)
        )
        or int(levels[-1]["next_unclassified_loss"]) != START_LOSS
        or any(int(row["unresolved_count"]) != 0 for row in levels)
    ):
        raise AssertionError("R19's certified tail levels do not end at the R20 cursor")
    return {
        "r19_certified_levels": len(chain),
        "r19_certified_level_range": [chain[0], chain[-1]],
        "r19_certified_vectors": sum(int(row["vector_count"]) for row in levels),
        "r19_level_counts_sha256": digest(tuple(str(row["counts_sha256"]) for row in levels)),
        "r20_first_unclassified_loss": START_LOSS,
        "prior_level_enumeration_calls": 0,
    }


@cache
def state_owner_identification() -> dict[str, Any]:
    """The exact state set attaining STATE_MAX_BOUND in the committed R19 terms."""

    terms = tuple(
        (str(row["stable_id"]), int(row["bound"]))
        for row in cast(list[dict[str, Any]], authority()["CURRENT_STATE_TERMS"])
    )
    owners = r13.identify_owner_set(terms)
    record = frozen_state_record(owners[0])
    region = cast(list[dict[str, Any]], record["complete_region_members"])
    ranked = sorted(int(row["final_bound"]) for row in region)
    tied = [row for row in region if int(row["final_bound"]) == START_STATE_MAX_BOUND]
    if (
        len(terms) != 23
        or owners != START_STATE_OWNER_IDS
        or max(value for _, value in terms) != START_STATE_MAX_BOUND
        or ranked[-1] != START_STATE_MAX_BOUND
    ):
        raise AssertionError("the committed state maximum or tied state set changed")
    return {
        "state_max_bound": START_STATE_MAX_BOUND,
        "tied_state_ids": list(owners),
        "next_state_bound": max(value for identifier, value in terms if identifier not in owners),
        "region_source_task": "B649_K20_R3_TAIL_STATE_OWNER_CHASE_R16",
        "region_sha256": record["region_sha256"],
        "region_compressed_member_count": len(region),
        "region_members_at_state_max": len(tied),
        "region_members_at_or_above_start_classified_maximum": sum(
            value >= START_CLASSIFIED_MAXIMUM for value in ranked
        ),
        "r17_to_r19_state_refinements": 0,
    }


@dataclass
class Chase(r19.Chase):
    start_bound: int = START_R3_BOUND
    transition_limit: int = 0
    new_vector_above_state: str | None = None
    members_reconstructed: int = 0
    state_crossover_loss: int | None = None
    member_dispatches: list[dict[str, Any]] = field(default_factory=lambda: [])

    def stop_condition(self) -> str | None:
        if self.bound <= self.r4_reference:
            return STOP_A
        if self.start_bound - self.bound >= self.drop_target:
            return STOP_B
        if self.new_vector_above_state is not None:
            return STOP_NEW_VECTOR
        owner = select_owner(self)
        if owner == TAIL_ID or owner.startswith("state:"):
            return None
        processed = {str(row["owner_id"]) for row in self.state_records}
        states = dict(self.states)
        if processed and all(states[identifier] < self.bound for identifier in processed):
            return STOP_C
        return STOP_OUT_OF_SCOPE


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
    require_unclassified_cursor(int(stored["NEXT_UNCLASSIFIED_LOSS"]), "levels must not resume")
    chase = Chase(
        states=states,
        baseline=canonical_baseline(),
        next_loss=int(stored["NEXT_UNCLASSIFIED_LOSS"]),
        classified_maximum=(START_CLASSIFIED_ID, START_CLASSIFIED_MAXIMUM),
        classified_terms=classified,
    )
    chase.sync_classified_maximum()
    if (
        chase.owners != (TAIL_ID,)
        or chase.bound != START_R3_BOUND
        or chase.state_max != START_STATE_MAX_BOUND
        or chase.classified_maximum != (START_CLASSIFIED_ID, START_CLASSIFIED_MAXIMUM)
        or chase.competitor(TAIL_ID) != START_STATE_MAX_BOUND
    ):
        raise AssertionError("the initial R20 maximum changed")
    return chase


def next_tail_level(chase: Chase) -> tuple[int, tuple[CountVector, ...], int]:
    chase.require_dispatch(TAIL_ID)
    if chase.tail_bound <= chase.competitor(TAIL_ID):
        raise AssertionError("tail descent at or below a competing owner is forbidden")
    require_unclassified_cursor(chase.next_loss, "levels must never be enumerated")
    losses = r6.local_losses(r5.anchor_incidence_profiles())
    vectors = tuple(
        sorted(
            r16.iter_interval_vectors(
                losses, r12.OUTSIDE_TICKET_COUNT, chase.next_loss, chase.next_loss
            )
        )
    )
    if not vectors:
        raise AssertionError("the tail cursor must be an attained loss")
    lookahead = r16.next_attained_loss(losses, r12.OUTSIDE_TICKET_COUNT, chase.next_loss + 1)
    return chase.next_loss, vectors, lookahead


def classify_new_tail_vector(
    counts: CountVector, baseline: int, state_threshold: int
) -> r13.ClassifiedVector:
    """R6 pair/triple correction, plus R8's four-ticket floor only above the state max."""

    loss = r12.local_loss(counts, r6.local_losses(r5.anchor_incidence_profiles()))
    require_unclassified_cursor(loss, "vectors must never be reclassified")
    return r13.classify_vector(counts, baseline, state_threshold)


def advance_tail(chase: Chase) -> None:
    loss, vectors, next_loss = next_tail_level(chase)
    before, previous = chase.owners, chase.bound
    competitor = chase.competitor(TAIL_ID)
    state_threshold = chase.state_max
    rows = tuple(
        classify_new_tail_vector(counts, chase.baseline, state_threshold) for counts in vectors
    )
    for row in rows:
        if row.local_loss != loss or row.status not in (r12.WITNESS_REALIZED, r12.ELIMINATED):
            raise AssertionError("tail level contains an unresolved or misplaced vector")
        if row.status == r12.WITNESS_REALIZED and (
            row.witness is None or not r8.validate_support_assignment(row.counts, row.witness)
        ):
            raise AssertionError("tail support witness failed independent validation")
        if row.vector_bound is not None:
            if row.vector_bound > chase.baseline - loss:
                raise AssertionError("a tail correction cannot be negative")
            chase.classified_terms[row.vector_id] = row.vector_bound
            chase.vector_records[row.vector_id] = asdict(row)
            chase.sync_classified_maximum()
            if row.vector_bound > state_threshold and chase.new_vector_above_state is None:
                chase.new_vector_above_state = row.vector_id
    chase.next_loss = next_loss
    if chase.state_crossover_loss is None and chase.tail_bound <= START_STATE_MAX_BOUND:
        chase.state_crossover_loss = next_loss
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
            "four_ticket_applied_count": sum(
                row.four_ticket_status == r13.FOUR_TICKET_APPLIED for row in rows
            ),
            "realizable_count": sum(row.status == r12.WITNESS_REALIZED for row in rows),
            "unrealizable_count": sum(row.status == r12.ELIMINATED for row in rows),
            "unresolved_count": 0,
            "active_competing_threshold": competitor,
            "four_ticket_state_threshold": state_threshold,
            "owner_set_at_dispatch": list(before),
        }
    )
    chase.record_event(f"tail:L{loss}", before, previous)


def frozen_state_record(owner_id: str) -> dict[str, Any]:
    """R19 refined no state, so R16's pinned region is still the latest complete one."""

    records = cast(list[dict[str, Any]], authority()["STATE_OWNER_CERTIFICATES"])
    if any(row["owner_id"] == owner_id for row in records):
        raise AssertionError("an R19 state member refinement would require replay")
    return r19.frozen_state_record(owner_id)


def refine_state_owner(chase: Chase, owner_id: str) -> None:
    """Certify one maximizing compressed member, then reselect the owner."""

    chase.require_dispatch(owner_id)
    if not owner_id.startswith("state:"):
        raise AssertionError("state proof requested for a non-state owner")
    record = frozen_state_record(owner_id)
    region = cast(list[dict[str, Any]], record["complete_region_members"])
    frozen = tuple((dense(row["witness_counts"]), int(row["raw_bound"])) for row in region)
    if digest(frozen) != record["region_sha256"]:
        raise AssertionError("the frozen current-owner region fingerprint changed")
    bounds = chase.state_region_bounds.setdefault(
        owner_id, {dense(row["witness_counts"]): int(row["final_bound"]) for row in region}
    )
    prior = dict(chase.states)[owner_id]
    if max(bounds.values()) != prior:
        raise AssertionError("state term differs from its compressed region maximum")
    threshold = chase.competitor(owner_id)
    counts = min(vector for vector, value in bounds.items() if value == prior)
    stored = next(row for row in region if dense(row["witness_counts"]) == counts)
    make_state_api = "_make_state"
    make_state = getattr(r7, make_state_api)
    profiles = r5.anchor_incidence_profiles()
    member = cast(r7.ResidualJointState, make_state(counts, profiles, r6.local_losses(profiles)))
    member = replace(member, represented_vector_count=int(stored["represented_vector_count"]))
    chase.members_reconstructed += 1
    if r14.raw_bound(member) != int(stored["raw_bound"]) or prior < threshold:
        raise AssertionError("a non-load-bearing compressed member was dispatched")
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
            "witness_counts": sparse(counts),
            "member_local_loss": member.local_loss,
            "member_joint_s2_s3": [member.joint_s2, member.joint_s3],
            "member_raw_bound": int(stored["raw_bound"]),
            "member_prior_relaxation": "CARRIED_RAW_R7_REGION_MEMBER",
            "represented_vector_count": len(vectors),
            "compressed_member": len(vectors) > 1,
            "vector_certificates": certificates,
            "support_witnesses": witnesses,
            "member_prior_bound": prior,
            "member_new_bound": bound,
            "member_below_competitor": bound < threshold,
            "tightening_route": RATIONAL_MOMENT_ROUTE,
            "region_sha256": record["region_sha256"],
            "no_other_state_terms_refined": True,
        }
    )
    chase.record_event(f"state:{owner_id}", before, previous)


def run_chase(*, wall_budget: float = PROOF_WALL_BUDGET_SECONDS) -> tuple[Chase, str, float]:
    if not 0 < wall_budget <= PROOF_WALL_BUDGET_SECONDS:
        raise ValueError("proof wall budget must be positive and at most 3600 seconds")
    started = time.monotonic()
    canonical_primitives()
    prior_level_fingerprints()
    state_owner_identification()
    chase = initial_chase()
    while True:
        stop = chase.stop_condition()
        if stop is not None:
            return chase, stop, time.monotonic() - started
        if time.monotonic() - started >= wall_budget:
            return chase, STOP_D, time.monotonic() - started
        owner = select_owner(chase)
        try:
            if owner == TAIL_ID:
                advance_tail(chase)
            elif owner.startswith("state:"):
                refine_state_owner(chase, owner)
            else:
                raise AssertionError(f"unhandled current owner: {owner}")
        except r15.RationalRouteExhausted:
            # Exact S4 at the S3 maximizers is the next route for this member;
            # report it rather than substitute an unproven bound.
            chase.exhausted_owner = owner
            return chase, STOP_EXHAUSTED, time.monotonic() - started


def build_result(*, wall_budget: float = PROOF_WALL_BUDGET_SECONDS) -> dict[str, Any]:
    chase, stop, wall = run_chase(wall_budget=wall_budget)
    transitions = [row for row in chase.events if row["from"] != row["to"]]
    state_ids = list(dict.fromkeys(str(row["owner_id"]) for row in chase.state_records))
    initial = initial_chase()
    initial_states = dict(initial.states)
    new_vector_ids = {row["vector_id"] for row in chase.vector_records.values()}
    if (
        chase.bound != max(chase.tail_bound, chase.classified_maximum[1], chase.state_max)
        or any(
            initial_states[identifier] != bound and identifier not in state_ids
            for identifier, bound in chase.states
        )
        or any(
            initial.classified_terms.get(identifier) != bound and identifier not in new_vector_ids
            for identifier, bound in chase.classified_terms.items()
        )
        or any(identifier in initial.classified_terms for identifier in new_vector_ids)
        or any(int(row["local_loss"]) < START_LOSS for row in chase.tail_records)
        or any(
            chase.baseline - int(row["local_loss"]) <= int(row["active_competing_threshold"])
            for row in chase.tail_records
        )
        or any(
            int(row["member_prior_bound"]) < int(row["active_competing_threshold"])
            for row in chase.member_dispatches
        )
        or chase.members_reconstructed != len(chase.member_dispatches)
    ):
        raise AssertionError("the final maximum or an owner-only work guard failed")
    classes = owner_classes(chase.owners)
    certified = len(chase.state_records)
    compressed = [row for row in chase.state_records if row["compressed_member"]]
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "SUCCESS_" + stop[0] if stop in (STOP_A, STOP_B, STOP_C) else stop,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_BRANCH": TASK_BRANCH,
        "START_R3_BOUND": START_R3_BOUND,
        "START_OWNER_IDS": [TAIL_ID],
        "CANONICAL_PRIMITIVES": canonical_primitives(),
        "CANONICAL_PRIMITIVE_STATUS": "PASS",
        "UPSTREAM_FINGERPRINTS_SHA256": verify_upstream_fingerprints(),
        "PRIOR_LEVEL_HANDLING": "PINNED_CERTIFICATES_NO_PRIOR_LEVEL_ENUMERATION",
        "PRIOR_LEVEL_FINGERPRINTS": prior_level_fingerprints(),
        "CROSSOVER_DERIVATION": {
            "tail_base_constant": canonical_baseline(),
            "start_next_unclassified_loss": START_LOSS,
            "start_unclassified_tail_bound": START_UNCLASSIFIED_TAIL_BOUND,
            "state_maximum": START_STATE_MAX_BOUND,
            "state_crossover_loss": STATE_CROSSOVER_LOSS,
            "first_attained_cursor_at_or_past_crossover": chase.state_crossover_loss,
            "classified_maximum": START_CLASSIFIED_MAXIMUM,
            "classified_crossover_loss": canonical_baseline() - START_CLASSIFIED_MAXIMUM,
        },
        "STATE_OWNER_IDENTIFICATION": state_owner_identification(),
        "OWNER_TRANSITION_COUNT": len(transitions),
        "OWNER_TRANSITION_LIMIT": None,
        "OWNER_TRANSITIONS": transitions,
        "OWNER_CLASS_SEQUENCE": [
            owner_classes(initial.owners),
            *[row["to_owner_classes"] for row in transitions],
        ],
        "OWNER_ACTION_TRAJECTORY": chase.events,
        "OWNER_TRANSITION_DEFINITION": "EXACT_OWNER_SET_CHANGE_INCLUDING_TIED_SET_CHANGES",
        "TAIL_LEVELS_PROCESSED": len(chase.tail_records),
        "TAIL_VECTORS_PROCESSED": sum(row["vector_count"] for row in chase.tail_records),
        "TAIL_LEVEL_CERTIFICATES": chase.tail_records,
        "NEW_TAIL_VECTOR_STRUCTURAL_RECORDS": list(chase.vector_records.values()),
        "NEW_VECTOR_ABOVE_STATE_MAX_ID": chase.new_vector_above_state,
        "STATE_OWNERS_PROCESSED": len(state_ids),
        "PROCESSED_STATE_OWNER_IDS": state_ids,
        "STATE_MEMBERS_CERTIFIED": certified,
        "LOAD_BEARING_MEMBERS_RECONSTRUCTED": chase.members_reconstructed,
        "COMPRESSED_MEMBERS_RECOVERED": len(compressed),
        "COMPRESSED_VECTORS_CERTIFIED": sum(
            int(row["represented_vector_count"]) for row in compressed
        ),
        "STATE_OWNER_CERTIFICATES": chase.state_records,
        "STATE_MEMBER_DISPATCHES": chase.member_dispatches,
        "TIGHTENING_ROUTES_USED": sorted(
            {str(row["tightening_route"]) for row in chase.state_records}
        ),
        "HIGHER_ORDER_ESCALATION": (
            "NOT_REQUIRED_RATIONAL_MOMENT_CERTIFIED_EVERY_DISPATCHED_MEMBER"
            if chase.exhausted_owner is None
            else "EXACT_S4_AT_S3_MAXIMIZERS_REQUIRED_AT_EXHAUSTED_OWNER"
        ),
        "EXHAUSTED_OWNER_ID": chase.exhausted_owner,
        "CLASSIFIED_VECTOR_OWNERS_PROCESSED": 0,
        "CURRENT_STATE_TERMS": [
            {"stable_id": identifier, "bound": bound} for identifier, bound in chase.states
        ],
        "CURRENT_CLASSIFIED_TERMS": [
            {"stable_id": identifier, "bound": bound}
            for identifier, bound in chase.classified_terms.items()
        ],
        "FINAL_BOUND_OWNER_CLASS": classes[0] if len(classes) == 1 else "TIED_OWNER_SET",
        "FINAL_OWNER_CLASSES": classes,
        "FINAL_OWNER_IDS": list(chase.owners),
        "NEXT_LOAD_BEARING_OWNER_ID": select_owner(chase),
        "UNCLASSIFIED_TAIL_BOUND": chase.tail_bound,
        "NEXT_UNCLASSIFIED_LOSS": chase.next_loss,
        "MAX_CLASSIFIED_TAIL_VECTOR_BOUND": chase.classified_maximum[1],
        "MAX_CLASSIFIED_TAIL_VECTOR_ID": chase.classified_maximum[0],
        "STATE_MAX_BOUND": chase.state_max,
        "STATE_MAX_OWNER_IDS": list(r13.identify_owner_set(chase.states)),
        "R3_BOUND": chase.bound,
        "R3_DROP": START_R3_BOUND - chase.bound,
        "R3_STATUS": "CERTIFIED_OWNER_ONLY_RATIONAL_MOMENT_AND_ATTAINED_TAIL_BOUND",
        "R3_FORMULA": (
            "max(STATE_TERMS, UNCLASSIFIED_TAIL_BOUND, MAX_CLASSIFIED_TAIL_VECTOR_BOUND)"
        ),
        "R4_REFERENCE_BOUND": R4_REFERENCE_BOUND,
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": chase.bound - INCUMBENT,
        "STOP_CONDITION": stop,
        "SUCCESS_A": stop == STOP_A,
        "SUCCESS_B": stop == STOP_B,
        "SUCCESS_C": stop == STOP_C,
        "STOP_D": stop == STOP_D,
        "PROOF_WALL_SECONDS": wall,
        "PROOF_WALL_BUDGET_SECONDS": wall_budget,
        "SOLVER_STATUS": "NOT_DISPATCHED_EXACT_RATIONAL_CERTIFICATES_SUFFICIENT",
        "SOLVER_CONFIGURED_WALL_LIMIT": None,
        "SOLVER_ACTUAL_WALL_TIME": 0.0,
        "SOLVER_CERTIFIED_BOUND": None,
        "PRIOR_TAIL_LEVELS_ENUMERATED": 0,
        "PRIOR_VECTORS_RECLASSIFIED": 0,
        "NON_OWNER_STATE_TERMS_CHANGED": 0,
        "PRIOR_CLASSIFIED_TERMS_CHANGED": 0,
        "GENERIC_FRONTIER_CENSUS_CALLS": 0,
        "WORKTREE_DISPOSITION": "RETAIN",
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--wall-budget", type=float, default=PROOF_WALL_BUDGET_SECONDS)
    options = parser.parse_args()
    result = build_result(wall_budget=options.wall_budget)
    if not options.no_write:
        RESULT_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    keys = (
        "TASK_STATUS",
        "R3_BOUND",
        "R3_DROP",
        "OWNER_TRANSITION_COUNT",
        "TAIL_LEVELS_PROCESSED",
        "TAIL_VECTORS_PROCESSED",
        "STATE_OWNERS_PROCESSED",
        "STATE_MEMBERS_CERTIFIED",
        "COMPRESSED_MEMBERS_RECOVERED",
        "FINAL_BOUND_OWNER_CLASS",
        "FINAL_OWNER_IDS",
        "NEXT_LOAD_BEARING_OWNER_ID",
        "UNCLASSIFIED_TAIL_BOUND",
        "NEXT_UNCLASSIFIED_LOSS",
        "MAX_CLASSIFIED_TAIL_VECTOR_BOUND",
        "MAX_CLASSIFIED_TAIL_VECTOR_ID",
        "STATE_MAX_BOUND",
        "EXHAUSTED_OWNER_ID",
        "PROOF_WALL_SECONDS",
    )
    print(json.dumps({key: result[key] for key in keys}, indent=2))


if __name__ == "__main__":
    main()
