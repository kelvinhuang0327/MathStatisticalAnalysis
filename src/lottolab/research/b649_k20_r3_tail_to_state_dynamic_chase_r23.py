"""Resume the pinned R22 tail and dynamically chase only the current R3 owner.

R22's earlier tail levels and reduced region members are immutable inputs.
The attained cursor starts at 8,770,657.  After each completed owner action,
all three families are recomputed; only the new owner may dispatch work.
There is no transition cap or generic frontier/search run.
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

from lottolab.research import b649_k20_r3_state_tail_coupled_owner_chase_r22 as r22
from lottolab.research.b649_k20_r3_tail_threshold_to_top_state_r13 import ClassifiedVector

r19, r17, r16, r15, r14, r13 = r22.r19, r22.r17, r22.r16, r22.r15, r22.r14, r22.r13
r12, r8, r7, r6, r5 = r22.r12, r22.r8, r22.r7, r22.r6, r22.r5
CountVector = r22.CountVector
dense, sparse, digest = r22.dense, r22.sparse, r22.digest
owner_class, owner_classes = r22.owner_class, r22.owner_classes
state_region, region_sha256, member_record = r22.state_region, r22.region_sha256, r22.member_record
pinned_r7_census, canonical_primitives = r22.pinned_r7_census, r22.canonical_primitives
STATE_CLASS, TAIL_CLASS, CLASSIFIED_CLASS = r22.STATE_CLASS, r22.TAIL_CLASS, r22.CLASSIFIED_CLASS
TAIL_ID = r22.TAIL_ID
STOP_A, STOP_B, STOP_C = r22.STOP_A, r22.STOP_B, r22.STOP_C
RATIONAL_MOMENT_ROUTE = r22.RATIONAL_MOMENT_ROUTE
TASK_ID = "B649_K20_R3_TAIL_TO_STATE_DYNAMIC_CHASE_R23"
TASK_BRANCH = "codex/b649-k20-r3-tail-to-state-dynamic-chase-r23"
BASE_HEAD = "5e2c4a6b336860f03032e9d28a99ebcd23f01612"
BASE_TREE = "e84c731dac45741253011939aedf47394e09e70a"
START_R3_BOUND = START_UNCLASSIFIED_TAIL_BOUND = 356_277_971
START_STATE_BOUND = 356_247_108
START_STATE_ID = "state:s2-13169800-s3-789320"
START_CLASSIFIED_MAXIMUM = 356_056_456
START_CLASSIFIED_ID = "carried-r12-other-levels"
START_LOSS = 8_770_657
TAIL_BASE_CONSTANT = 365_048_628
STATE_CROSSOVER_LOSS = 8_801_520
R4_REFERENCE_BOUND, INCUMBENT = 350_545_749, 313_239_661
DROP_TARGET = 100_000
SUCCESS_B_THRESHOLD = START_R3_BOUND - DROP_TARGET
PROOF_WALL_BUDGET_SECONDS = 3_600.0
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_PATH = REPO_ROOT / (
    "docs/research/matrix-native-results/b649-k20-r3-tail-to-state-dynamic-chase-r23-result.json"
)
R22_RESULT_RELATIVE = (
    "docs/research/matrix-native-results/b649-k20-r3-state-tail-coupled-owner-chase-r22-result.json"
)
UPSTREAM_SHA256 = {
    "src/lottolab/research/b649_k20_r3_state_tail_coupled_owner_chase_r22.py": (
        "945c1b06ca35262c200c33e83de1ba8196cb13f75151ec25f85b1ae15d37f1d5"
    ),
    R22_RESULT_RELATIVE: "1f8d6b53ae55277067a8548d39054134ea5e8617ab4f288225fdeab65438f6e0",
}


def verify_upstream_fingerprints() -> dict[str, str]:
    observed = {
        relative: sha256((REPO_ROOT / relative).read_bytes()).hexdigest()
        for relative in UPSTREAM_SHA256
    }
    if observed != UPSTREAM_SHA256:
        raise AssertionError(f"R22 authority fingerprint mismatch: {observed}")
    r22.verify_upstream_fingerprints()
    return observed


@cache
def authority() -> dict[str, Any]:
    verify_upstream_fingerprints()
    stored = cast(dict[str, Any], json.loads((REPO_ROOT / R22_RESULT_RELATIVE).read_text()))
    expected = {
        "TASK_ID": r22.TASK_ID,
        "TASK_BRANCH": r22.TASK_BRANCH,
        "BASE_HEAD": r22.BASE_HEAD,
        "TASK_STATUS": "SUCCESS_B",
        "R3_BOUND": START_R3_BOUND,
        "STATE_MAX_BOUND": START_STATE_BOUND,
        "FINAL_OWNER_IDS": [TAIL_ID],
        "STATE_MAX_OWNER_IDS": [START_STATE_ID],
        "NEXT_UNCLASSIFIED_LOSS": START_LOSS,
        "UNCLASSIFIED_TAIL_BOUND": START_UNCLASSIFIED_TAIL_BOUND,
        "MAX_CLASSIFIED_TAIL_VECTOR_BOUND": START_CLASSIFIED_MAXIMUM,
        "MAX_CLASSIFIED_TAIL_VECTOR_ID": START_CLASSIFIED_ID,
        "R4_REFERENCE_BOUND": R4_REFERENCE_BOUND,
        "INCUMBENT": INCUMBENT,
    }
    if any(stored[key] != value for key, value in expected.items()):
        raise AssertionError("R22 authority differs from the R23 Packet")
    return stored


def canonical_baseline() -> int:
    baseline = canonical_primitives()["K20_S1"] - r13.FIXED_CERTIFIED_LOSS
    if (
        baseline != TAIL_BASE_CONSTANT
        or baseline - START_LOSS != START_UNCLASSIFIED_TAIL_BOUND
        or baseline - START_STATE_BOUND != STATE_CROSSOVER_LOSS
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
        int(rows[0]["local_loss"]) != r22.START_LOSS
        or any(int(a["next_unclassified_loss"]) != int(b["local_loss"]) for a, b in pairwise(rows))
        or int(rows[-1]["next_unclassified_loss"]) != START_LOSS
        or any(int(row["unresolved_count"]) for row in rows)
    ):
        raise AssertionError("the pinned R22 levels do not end at the R23 cursor")
    return {
        "r22_certified_levels": len(rows),
        "r22_certified_vectors": sum(int(row["vector_count"]) for row in rows),
        "r22_certified_level_range": [rows[0]["local_loss"], rows[-1]["local_loss"]],
        "r22_level_counts_sha256": digest(tuple(row["counts_sha256"] for row in rows)),
        "r23_first_unclassified_loss": START_LOSS,
        "prior_level_enumeration_calls": 0,
    }


@dataclass
class Chase(r22.Chase):
    start_bound: int = START_R3_BOUND
    carried_regions: list[dict[str, Any]] = field(default_factory=lambda: [])


def select_owner(chase: Chase) -> str:
    """At the state crossover stop the tail, including an exact state/tail tie."""
    owners = chase.owners
    classified = sorted(owner for owner in owners if owner_class(owner) == CLASSIFIED_CLASS)
    if classified:
        return classified[0]
    states = sorted(owner for owner in owners if owner_class(owner) == STATE_CLASS)
    return states[0] if states else TAIL_ID


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
        or chase.classified_maximum != (START_CLASSIFIED_ID, START_CLASSIFIED_MAXIMUM)
    ):
        raise AssertionError("the initial owner/family maximum differs from R22")
    return chase


def restore_owner_region(chase: Chase, owner_id: str) -> None:
    """Load only the selected state's complete carried R22 member certificate."""
    chase.require_dispatch(owner_id)
    if select_owner(chase) != owner_id or owner_class(owner_id) != STATE_CLASS:
        raise AssertionError("region reconstruction requires the selected state owner")
    if owner_id in chase.state_region_bounds:
        return
    region = state_region(owner_id)
    prior = dict(chase.states)[owner_id]
    stored = next(
        (row for row in authority()["STATE_REGION_CERTIFICATES"] if row["owner_id"] == owner_id),
        None,
    )
    if stored is None:
        if max(r14.raw_bound(row) for row in region) != prior:
            raise r22.StateScopeRequired(owner_id)
        return
    members = stored["complete_region_members"]
    by_counts = {dense(row["witness_counts"]): row for row in members}
    if (
        stored["region_sha256"] != region_sha256(region)
        or len(by_counts) != len(members)
        or set(by_counts) != {row.witness_counts for row in region}
        or any(
            by_counts[row.witness_counts]["raw_bound"] != r14.raw_bound(row)
            or by_counts[row.witness_counts]["represented_vector_count"]
            != row.represented_vector_count
            or by_counts[row.witness_counts]["final_bound"] > r14.raw_bound(row)
            for row in region
        )
    ):
        raise AssertionError("the carried R22 region differs from the pinned R7 region")
    bounds = {counts: int(row["final_bound"]) for counts, row in by_counts.items()}
    reduced = {
        counts for counts, row in by_counts.items() if bounds[counts] != int(row["raw_bound"])
    }
    certificates = {
        dense(row["member"]["witness_counts"]): row
        for row in authority()["STATE_OWNER_CERTIFICATES"]
        if row["owner_id"] == owner_id
    }
    if (
        max(bounds.values()) != prior
        or stored["final_state_bound"] != prior
        or len(reduced) != stored["certified_member_count"]
        or reduced != set(certificates)
        or any(
            bounds[counts] != int(certificates[counts]["member_new_bound"]) for counts in reduced
        )
    ):
        raise AssertionError("the carried member reductions do not certify the current state")
    chase.state_region_bounds[owner_id] = bounds
    chase.carried_regions.append(
        {
            "owner_id": owner_id,
            "region_sha256": region_sha256(region),
            "carried_reduced_member_count": len(reduced),
            "carried_state_bound": prior,
            "prior_member_certificate_calls": 0,
            "initial_maximizing_members": [
                member_record(row) for row in region if bounds[row.witness_counts] == prior
            ],
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
    bounds = chase.state_region_bounds.get(owner_id)
    if bounds is None:
        raw = {row.witness_counts: r14.raw_bound(row) for row in region}
        if max(raw.values()) != prior:
            raise r22.StateScopeRequired(owner_id)
        bounds = chase.state_region_bounds[owner_id] = raw
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


def refine_classified_owner(chase: Chase, owner_id: str) -> None:
    r22.refine_classified_owner(chase, owner_id)


def next_tail_level(chase: Chase) -> tuple[int, tuple[CountVector, ...], int]:
    chase.require_dispatch(TAIL_ID)
    require_unclassified_cursor(chase.next_loss)
    if select_owner(chase) != TAIL_ID or chase.tail_bound < chase.competitor(TAIL_ID):
        raise AssertionError("tail descent below the active competing bound is forbidden")
    losses = r6.local_losses(r5.anchor_incidence_profiles())
    vectors = tuple(
        sorted(
            r16.iter_interval_vectors(
                losses, r12.OUTSIDE_TICKET_COUNT, chase.next_loss, chase.next_loss
            )
        )
    )
    if not vectors:
        raise AssertionError("the cursor must be an attained loss")
    lookahead = r16.next_attained_loss(losses, r12.OUTSIDE_TICKET_COUNT, chase.next_loss + 1)
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
        chase.tail_vector_records.append(asdict(row))
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


def run_chase(*, wall_budget: float = PROOF_WALL_BUDGET_SECONDS) -> tuple[Chase, str, float]:
    if not 0 < wall_budget <= PROOF_WALL_BUDGET_SECONDS:
        raise ValueError("proof wall budget must be positive and at most 3600 seconds")
    started = time.monotonic()
    canonical_primitives()
    prior_level_fingerprints()
    chase = initial_chase()
    while True:
        stop = chase.stop_condition()
        if stop is not None:
            return chase, stop, time.monotonic() - started
        if time.monotonic() - started >= wall_budget:
            return chase, STOP_C, time.monotonic() - started
        owner = select_owner(chase)
        if owner == TAIL_ID:
            advance_tail(chase)
        elif owner_class(owner) == STATE_CLASS:
            refine_state_owner(chase, owner)
        else:
            refine_classified_owner(chase, owner)


def build_result(*, wall_budget: float = PROOF_WALL_BUDGET_SECONDS) -> dict[str, Any]:
    chase, stop, wall = run_chase(wall_budget=wall_budget)
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
    if (
        chase.bound != max(chase.tail_bound, chase.classified_maximum[1], chase.state_max)
        or any(
            initial_states[identifier] != bound and identifier not in state_ids
            for identifier, bound in chase.states
        )
        or any(
            chase.classified_terms[identifier] != bound and identifier not in refined_vectors
            for identifier, bound in initial.classified_terms.items()
        )
        or set(chase.classified_terms) != set(initial.classified_terms) | surviving_ids
        or new_ids & set(initial.classified_terms)
        or any(int(row["local_loss"]) < START_LOSS for row in chase.tail_records)
        or any(
            chase.baseline - int(row["local_loss"]) < int(row["active_competing_threshold"])
            for row in chase.tail_records
        )
        or any(
            int(row["member_prior_bound"]) < int(row["tail_bound_at_dispatch"])
            for row in chase.member_dispatches
        )
        or len(chase.member_dispatches) != len(chase.state_records)
    ):
        raise AssertionError("the final maximum or an owner-only work guard failed")
    classes = owner_classes(chase.owners)
    transitions = [row for row in chase.events if row["from"] != row["to"]]
    region_records: list[dict[str, Any]] = []
    for identifier in state_ids:
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
                "final_state_bound": max(bounds.values()),
            }
        )
    status = {
        STOP_A: "SUCCESS_A",
        STOP_B: "SUCCESS_B",
        STOP_C: "SUCCESS_C",
    }.get(stop, stop)
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": status,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_BRANCH": TASK_BRANCH,
        "R3_AUTHORITY": {
            "authority_head": BASE_HEAD,
            "authority_task_id": r22.TASK_ID,
            "authority_result_sha256": UPSTREAM_SHA256[R22_RESULT_RELATIVE],
        },
        "START_R3_BOUND": START_R3_BOUND,
        "START_OWNER_IDS": [TAIL_ID],
        "CANONICAL_PRIMITIVES": canonical_primitives(),
        "CANONICAL_PRIMITIVE_STATUS": "PASS",
        "UPSTREAM_FINGERPRINTS_SHA256": verify_upstream_fingerprints(),
        "PRIOR_LEVEL_FINGERPRINTS": prior_level_fingerprints(),
        "CROSSOVER_DERIVATION": {
            "tail_base_constant": canonical_baseline(),
            "start_next_unclassified_loss": START_LOSS,
            "start_unclassified_tail_bound": START_UNCLASSIFIED_TAIL_BOUND,
            "first_state_crossover_loss": canonical_baseline() - START_STATE_BOUND,
            "success_b_threshold": SUCCESS_B_THRESHOLD,
            "success_b_tail_loss": canonical_baseline() - SUCCESS_B_THRESHOLD,
        },
        "CARRIED_OWNER_REGION_CERTIFICATES": chase.carried_regions,
        "R7_FINGERPRINT_STATUS": "PASS" if state_ids else "NOT_REQUIRED_NO_STATE_DISPATCH",
        "R7_CENSUS_PIN": pinned_r7_census() if state_ids else None,
        "OWNER_DISPATCH_RULE": (
            "classified vector owners first; state owners including a state/tail tie next; "
            "tail only above the current competing state; one maximizing state member per action"
        ),
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
        "TAIL_LEVEL_CERTIFICATES": chase.tail_records,
        "NEW_TAIL_VECTOR_STRUCTURAL_RECORDS": chase.tail_vector_records,
        "CLASSIFIED_VECTOR_OWNERS_PROCESSED": len(refined_vectors),
        "CLASSIFIED_OWNER_CERTIFICATES": chase.classified_records,
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
        "STOP_CONDITION": stop,
        "SUCCESS_A": stop == STOP_A,
        "SUCCESS_B": stop == STOP_B,
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
    print(
        json.dumps(
            {
                key: value
                for key, value in result.items()
                if key.isupper() and not isinstance(value, (dict, list))
            }
            | {
                "OWNER_CLASS_SEQUENCE": result["OWNER_CLASS_SEQUENCE"],
                "FINAL_OWNER_IDS": result["FINAL_OWNER_IDS"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
