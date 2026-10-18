"""Chase the R21 state owner through whichever term owns R3 next (R22).

R21 (``a08a7e21``) left ``state:s2-13169800-s3-789320`` as the unique R3 owner,
only 154 above the unclassified tail.  That state was never refined, so its
complete R7 frontier region is recovered here and only its maximizing members
are certified, one at a time, with the first sufficient exact rational moment
certificate.  The owner is reselected after every strict improvement:

* a state strictly above every other term is refined;
* a state at or below the tail hands dispatch to the tail, which resumes
  exactly at R21's cursor and descends one attained level at a time;
* a classified vector owner is recovered and tightened only until ownership
  passes.

Neither a transition count nor a member budget ends the chase.  Prior tail
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

from lottolab.research import b649_k20_r3_classified_tail_band_to_state_r21 as r21
from lottolab.research.b649_k20_r3_tail_threshold_to_top_state_r13 import ClassifiedVector

r20 = r21.r20
r19 = r20.r19
r17 = r20.r17
r16 = r20.r16
r15 = r20.r15
r14 = r20.r14
r13 = r20.r13
r12 = r20.r12
r8 = r20.r8
r7 = r20.r7
r6 = r20.r6
r5 = r20.r5
CountVector = r20.CountVector
dense = r20.dense
sparse = r20.sparse
digest = r20.digest
TASK_ID = "B649_K20_R3_STATE_TAIL_COUPLED_OWNER_CHASE_R22"
BASE_HEAD = "a08a7e217a03a77efb7f75b89a5df9e7e27a6c51"
BASE_TREE = "2a28f5917f68694a0ccd4142f970de74f6a4e54d"
TASK_BRANCH = "codex/b649-k20-r3-state-tail-coupled-owner-chase-r22"
START_STATE_ID = "state:s2-13169800-s3-789320"
START_STATE_JOINT_S2, START_STATE_MAXIMUM_JOINT_S3 = 13_169_800, 789_320
START_R3_BOUND = START_STATE_BOUND = 356_378_218
START_LOSS = 8_670_564
START_UNCLASSIFIED_TAIL_BOUND = 356_378_064
START_CLASSIFIED_MAXIMUM = 356_056_456
START_CLASSIFIED_ID = "carried-r12-other-levels"
START_OWNER_MARGIN = START_STATE_BOUND - START_UNCLASSIFIED_TAIL_BOUND
STATE_TO_TAIL_SOLE_OWNER_DROP = START_OWNER_MARGIN + 1
TAIL_BASE_CONSTANT = 365_048_628
R4_REFERENCE_BOUND, INCUMBENT = 350_545_749, 313_239_661
DROP_TARGET = 100_000
SUCCESS_B_THRESHOLD = START_R3_BOUND - DROP_TARGET
PROOF_WALL_BUDGET_SECONDS = 3_600.0
TAIL_ID = r21.TAIL_ID
STATE_CLASS, TAIL_CLASS, CLASSIFIED_CLASS = "state", "unclassified-tail", "classified-tail-vector"
STOP_A = "A_R3_AT_OR_BELOW_R4_REFERENCE"
STOP_B = "B_CERTIFIED_R3_DROP_AT_LEAST_100000"
STOP_C = "C_PROOF_WALL_BUDGET_EXHAUSTED_EXACT_OWNER_RETAINED"
STOP_EXHAUSTED = "CURRENT_OWNER_RATIONAL_CERTIFICATE_EXHAUSTED"
STOP_SCOPE = "CURRENT_OWNER_REQUIRES_A_CARRIED_CERTIFICATE_SCOPE"
RATIONAL_MOMENT_ROUTE = r19.RATIONAL_MOMENT_ROUTE
# R20 (ef5c56e6) is the weaker sibling lineage named by the Packet: R21 builds on
# it, but neither it nor any other 356,5xx,xxx result may stand in for R21.
WEAKER_SIBLING_HEAD = r21.BASE_HEAD
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_PATH = REPO_ROOT / (
    "docs/research/matrix-native-results/b649-k20-r3-state-tail-coupled-owner-chase-r22-result.json"
)
R7_RESULT_RELATIVE = (
    "docs/research/matrix-native-results/b649-k20-r3-joint-residual-envelope-r7-result.json"
)
R21_RESULT_RELATIVE = (
    "docs/research/matrix-native-results/b649-k20-r3-classified-tail-band-to-state-r21-result.json"
)
UPSTREAM_SHA256 = {
    "src/lottolab/research/b649_k20_r3_classified_tail_band_to_state_r21.py": (
        "9809146ae3bf07d9739007dee9ce886b262bce223f85f74066eb1d7de46a28cb"
    ),
    R21_RESULT_RELATIVE: "f94e967f4cfdea81537beb953388723339f1c5315f7f82c0a51843ce03b60ca6",
}


def verify_upstream_fingerprints() -> dict[str, str]:
    observed = {
        relative: sha256((REPO_ROOT / relative).read_bytes()).hexdigest()
        for relative in UPSTREAM_SHA256
    }
    if observed != UPSTREAM_SHA256:
        raise AssertionError(f"R21 authority fingerprint mismatch: {observed}")
    r21.verify_upstream_fingerprints()  # Files only, never prior-level enumerators.
    return observed


def require_r21_authority(stored: dict[str, Any]) -> None:
    """Reject R20 and every other weaker 356,5xx,xxx lineage as the R3 authority."""

    bound = int(stored.get("R3_BOUND", -1))
    if 356_500_000 <= bound < 356_600_000:
        raise AssertionError("weaker-lineage authority substitution is forbidden: 356,5xx,xxx")
    if (
        stored.get("TASK_ID") != r21.TASK_ID
        or stored.get("TASK_BRANCH") != r21.TASK_BRANCH
        or stored.get("BASE_HEAD") != r21.BASE_HEAD
        or bound != START_R3_BOUND
    ):
        raise AssertionError("weaker-lineage authority substitution is forbidden")


@cache
def authority() -> dict[str, Any]:
    verify_upstream_fingerprints()
    stored = cast(
        dict[str, Any], json.loads((REPO_ROOT / R21_RESULT_RELATIVE).read_text(encoding="utf-8"))
    )
    require_r21_authority(stored)
    expected = {
        "TASK_STATUS": "SUCCESS_A",
        "R3_BOUND": START_R3_BOUND,
        "FINAL_OWNER_IDS": [START_STATE_ID],
        "STATE_MAX_BOUND": START_STATE_BOUND,
        "STATE_MAX_OWNER_IDS": [START_STATE_ID],
        "NEXT_UNCLASSIFIED_LOSS": START_LOSS,
        "UNCLASSIFIED_TAIL_BOUND": START_UNCLASSIFIED_TAIL_BOUND,
        "MAX_CLASSIFIED_TAIL_VECTOR_BOUND": START_CLASSIFIED_MAXIMUM,
        "MAX_CLASSIFIED_TAIL_VECTOR_ID": START_CLASSIFIED_ID,
        "R4_REFERENCE_BOUND": R4_REFERENCE_BOUND,
        "INCUMBENT": INCUMBENT,
    }
    if any(stored[key] != value for key, value in expected.items()):
        raise AssertionError("R21 authority differs from the R22 Packet")
    return stored


def canonical_primitives() -> dict[str, int]:
    observed = r21.canonical_primitives()
    if observed != {
        "SINGLE_TICKET_ANY_PRIZE": 18_611_432,
        "PAIR_INTERSECTION_COST[6]": 18_611_432,
        "K20_S1": 372_228_640,
    }:
        raise AssertionError("canonical primitive preflight failed")
    return observed


def canonical_baseline() -> int:
    baseline = canonical_primitives()["K20_S1"] - r13.FIXED_CERTIFIED_LOSS
    if (
        baseline != TAIL_BASE_CONSTANT
        or baseline - START_LOSS != START_UNCLASSIFIED_TAIL_BOUND
        or START_OWNER_MARGIN != 154
        or baseline - SUCCESS_B_THRESHOLD != 8_770_410
    ):
        raise AssertionError("the independent tail and owner-margin arithmetic failed")
    return baseline


def require_unclassified_cursor(loss: int) -> None:
    if loss < START_LOSS:
        raise AssertionError("prior tail enumeration or reclassification is forbidden")


@cache
def prior_level_fingerprints() -> dict[str, Any]:
    rows = cast(list[dict[str, Any]], authority()["TAIL_LEVEL_CERTIFICATES"])
    if (
        int(rows[0]["local_loss"]) != r21.START_LOSS
        or any(
            int(row["next_unclassified_loss"]) != int(following["local_loss"])
            for row, following in pairwise(rows)
        )
        or int(rows[-1]["next_unclassified_loss"]) != START_LOSS
        or any(int(row["unresolved_count"]) for row in rows)
    ):
        raise AssertionError("the pinned R21 levels do not end at the R22 cursor")
    return {
        "r21_certified_levels": len(rows),
        "r21_certified_vectors": sum(int(row["vector_count"]) for row in rows),
        "r21_certified_level_range": [rows[0]["local_loss"], rows[-1]["local_loss"]],
        "r21_level_counts_sha256": digest(tuple(row["counts_sha256"] for row in rows)),
        "r22_first_unclassified_loss": START_LOSS,
        "prior_level_enumeration_calls": 0,
    }


def owner_class(identifier: str) -> str:
    if identifier == TAIL_ID:
        return TAIL_CLASS
    if identifier.startswith("state:"):
        return STATE_CLASS
    return CLASSIFIED_CLASS


def owner_classes(identifiers: tuple[str, ...]) -> list[str]:
    return sorted({owner_class(identifier) for identifier in identifiers})


def select_owner(chase: Chase) -> str:
    """Classified owners first; a state at or below the tail yields to the tail."""

    owners = chase.owners
    classified = sorted(owner for owner in owners if owner_class(owner) == CLASSIFIED_CLASS)
    if classified:
        return classified[0]
    if TAIL_ID in owners:
        return TAIL_ID
    return min(owners)


@dataclass
class Chase(r21.Chase):
    start_bound: int = START_R3_BOUND
    drop_target: int = DROP_TARGET
    transition_limit: int = 0
    scope_owner: str | None = None
    member_dispatches: list[dict[str, Any]] = field(default_factory=lambda: [])
    tail_tie_dispatches: int = 0

    def stop_condition(self) -> str | None:
        if self.bound <= self.r4_reference:
            return STOP_A
        if self.start_bound - self.bound >= self.drop_target:
            return STOP_B
        return None

    def record_event(self, action: str, before: tuple[str, ...], previous: int) -> None:
        self._event(action, before, previous)
        self.events[-1].update(
            {
                "from_owner_classes": owner_classes(before),
                "to_owner_classes": owner_classes(self.owners),
            }
        )


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
        or chase.owners != (START_STATE_ID,)
        or chase.bound != START_R3_BOUND
        or chase.state_max != START_STATE_BOUND
        or chase.tail_bound != START_UNCLASSIFIED_TAIL_BOUND
        or chase.classified_maximum != (START_CLASSIFIED_ID, START_CLASSIFIED_MAXIMUM)
        or chase.competitor(START_STATE_ID) != START_UNCLASSIFIED_TAIL_BOUND
    ):
        raise AssertionError("the current state-owner identity changed")
    return chase


class StateScopeRequired(Exception):
    """A state owner whose term is not its raw region maximum needs carried certificates."""


class ClassifiedScopeRequired(Exception):
    """An aggregate classified certificate owns R3; it is not an individual vector."""


@cache
def pinned_r7_census() -> dict[str, Any]:
    """Replay R7's compressed census only to locate an owner region, against R7's pins."""

    stored = cast(
        dict[str, Any], json.loads((REPO_ROOT / R7_RESULT_RELATIVE).read_text(encoding="utf-8"))
    )
    census = r7.joint_residual_census()
    frontier_digest_api, envelope_digest_api = "_frontier_digest", "_envelope_digest"
    observed = {
        "RESIDUAL_STATE_COUNT": len(census.states),
        "FEASIBLE_TYPE_COUNT_VECTOR_COUNT": census.feasible_vector_count,
        "S2_S3_FRONTIER_SIZE": len(census.frontier),
        "S2_S3_FRONTIER_SHA256": getattr(r7, frontier_digest_api)(census.frontier),
        "S2_S3_ENVELOPE_SHA256": getattr(r7, envelope_digest_api)(census.s2_s3_envelope),
    }
    if stored["TASK_ID"] != r7.TASK_ID or any(
        stored[key] != value for key, value in observed.items()
    ):
        raise AssertionError("the replayed R7 census differs from its pinned result")
    return {
        "r7_result_sha256": sha256((REPO_ROOT / R7_RESULT_RELATIVE).read_bytes()).hexdigest(),
        **observed,
        "role": "OWNER_REGION_LOCATION_ONLY_NO_NEW_FRONTIER_BOUND",
    }


@cache
def state_region(owner_id: str) -> tuple[r7.ResidualJointState, ...]:
    pinned_r7_census()
    region = r14.owner_region(owner_id)
    if len({row.witness_counts for row in region}) != len(region):
        raise AssertionError("owner region members are not uniquely keyed")
    return region


def region_sha256(region: tuple[r7.ResidualJointState, ...]) -> str:
    return digest(tuple((row.witness_counts, r14.raw_bound(row)) for row in region))


def binding_relaxation(row: r7.ResidualJointState) -> str:
    if row.residual_pair_union_penalty >= row.complementary_forest_floor:
        return "R6_RESIDUAL_PAIR_MASS_FLOOR_OVER_9_WITHOUT_FOUR_EVENT_ADD_BACK"
    return "R5_COMPLEMENTARY_FOREST_FLOOR"


def member_record(row: r7.ResidualJointState) -> dict[str, Any]:
    return {
        "witness_counts": sparse(row.witness_counts),
        "represented_vector_count": row.represented_vector_count,
        "local_loss": row.local_loss,
        "anchor_pair_s2": row.anchor_pair_s2,
        "anchor_triple_s3": row.anchor_triple_s3,
        "residual_pair_intersection_mass_floor": row.residual_pair_intersection_mass_floor,
        "residual_pair_union_penalty": row.residual_pair_union_penalty,
        "complementary_forest_floor": row.complementary_forest_floor,
        "applied_residual_union_penalty": row.applied_residual_union_penalty,
        "binding_relaxation": binding_relaxation(row),
        "joint_s2": row.joint_s2,
        "joint_s3": row.joint_s3,
        "raw_bound": r14.raw_bound(row),
    }


@cache
def state_structural_certificate(owner_id: str) -> dict[str, Any]:
    """The frontier point, complete R7 region, and members attaining the state term."""

    s2_text, s3_text = owner_id.removeprefix("state:s2-").split("-s3-")
    joint_s2, maximum_joint_s3 = int(s2_text), int(s3_text)
    region = state_region(owner_id)
    frontier_bound = r14.joint_constant() - joint_s2 + maximum_joint_s3
    maximizing = tuple(
        sorted(
            (row for row in region if r14.raw_bound(row) == frontier_bound),
            key=lambda row: row.witness_counts,
        )
    )
    if (
        max(r14.raw_bound(row) for row in region) != frontier_bound
        or not maximizing
        or any((row.joint_s2, row.joint_s3) != (joint_s2, maximum_joint_s3) for row in maximizing)
    ):
        raise AssertionError("the recovered region does not attain its frontier term")
    represented = r17.represented_vectors(maximizing)
    return {
        "owner_id": owner_id,
        "structural_certificate_source": (
            "R7_EXACT_S2_S3_FRONTIER; complete region = R7 states whose first dominating "
            "frontier point in increasing S2 order is this point"
        ),
        "joint_s2": joint_s2,
        "maximum_joint_s3": maximum_joint_s3,
        "canonical_joint_expression_constant": r14.joint_constant(),
        "anchor_pair_intersection_i3": r7.ANCHOR_PAIR_INTERSECTION,
        "r7_census_pin": pinned_r7_census(),
        "frontier_bound": frontier_bound,
        "region_compressed_member_count": len(region),
        "region_type_vector_count": sum(row.represented_vector_count for row in region),
        "region_multi_vector_member_count": sum(row.represented_vector_count > 1 for row in region),
        "region_sha256": region_sha256(region),
        "maximizing_member_count": len(maximizing),
        "maximizing_members": [member_record(row) for row in maximizing],
        "maximizing_represented_vectors": [
            [sparse(vector) for vector in represented[row.witness_counts]] for row in maximizing
        ],
        "load_bearing_relaxations": sorted({binding_relaxation(row) for row in maximizing}),
        "relaxation_responsible_for_bound": (
            "carried raw R7 envelope: canonical K20 S1 - I(3) - exact anchor S2 + exact anchor "
            "S3 - max(ceil(R6 residual pair mass floor/9), R5 forest floor); the R6 residual "
            "pair floor omits the exact four-event add-back"
        ),
        "prior_state_refinements": 0,
    }


def refine_state_owner(chase: Chase, owner_id: str) -> None:
    """Certify one maximizing member while the state strictly owns R3, then reselect."""

    chase.require_dispatch(owner_id)
    if owner_class(owner_id) != STATE_CLASS:
        raise AssertionError("state proof requested for a non-state owner")
    prior = dict(chase.states)[owner_id]
    if select_owner(chase) != owner_id or prior <= chase.tail_bound:
        raise AssertionError("state work at or below the tail is forbidden")
    threshold = chase.competitor(owner_id)
    region = state_region(owner_id)
    bounds = chase.state_region_bounds.get(owner_id)
    if bounds is None:
        raw = {row.witness_counts: r14.raw_bound(row) for row in region}
        if max(raw.values()) != prior:
            raise StateScopeRequired(owner_id)
        state_structural_certificate(owner_id)
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


def refine_classified_owner(chase: Chase, identifier: str) -> None:
    """Recover only this vector; stop its stack at the first strict certificate."""

    chase.require_dispatch(identifier)
    if not identifier.startswith("tail-vector:"):
        raise ClassifiedScopeRequired(identifier)
    if select_owner(chase) != identifier:
        raise AssertionError("classified work below a competing owner is forbidden")
    prior = chase.classified_terms[identifier]
    threshold = chase.competitor(identifier)
    structural = r19.recover_classified_vector(chase, identifier)
    counts = dense(cast(list[list[int]], structural["counts"]))
    certificate = r14.moment_certificate(counts)
    bound = min(
        prior,
        chase.baseline
        - int(structural["source_loss_level"])
        - int(certificate["correction_lower_bound"]),
    )
    if bound >= prior:
        raise r15.RationalRouteExhausted(identifier)
    before, previous = chase.owners, chase.bound
    record = {
        "owner_id": identifier,
        "owner_set_at_dispatch": list(before),
        "active_competing_threshold": threshold,
        "prior_bound": prior,
        "new_bound": bound,
        "structural_record": structural,
        "certificate": certificate,
        "counts": sparse(counts),
        "tightening_route": RATIONAL_MOMENT_ROUTE,
        "first_sufficient_certificate": True,
        "prior_level_classification_calls": 0,
    }
    chase.classified_terms[identifier] = bound
    chase.vector_records[identifier] = record
    chase.classified_records.append(record)
    chase.sync_classified_maximum()
    chase.record_event(f"classified:{identifier}", before, previous)


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
        except (StateScopeRequired, ClassifiedScopeRequired):
            chase.scope_owner = owner
            return chase, STOP_SCOPE, time.monotonic() - started


def state_to_tail_switch(chase: Chase) -> dict[str, Any]:
    """The first state-to-tail ownership pass and the drop that caused it."""

    first = next(
        (
            row
            for row in chase.events
            if STATE_CLASS in row["from_owner_classes"] and TAIL_ID in row["to"]
        ),
        None,
    )
    return {
        "start_state_bound": START_STATE_BOUND,
        "start_unclassified_tail_bound": START_UNCLASSIFIED_TAIL_BOUND,
        "start_owner_margin": START_OWNER_MARGIN,
        "tie_at_state_drop": START_OWNER_MARGIN,
        "sole_tail_owner_at_state_drop": STATE_TO_TAIL_SOLE_OWNER_DROP,
        "first_switch_event_ordinal": None if first is None else first["ordinal"],
        "state_drop_at_first_switch": (
            None if first is None else START_STATE_BOUND - int(first["state_max_bound"])
        ),
        "tail_sole_owner_at_first_switch": first is not None and first["to"] == [TAIL_ID],
    }


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
            int(row["member_prior_bound"]) <= int(row["tail_bound_at_dispatch"])
            for row in chase.member_dispatches
        )
        or not 0
        <= len(chase.member_dispatches) - len(chase.state_records)
        <= (stop == STOP_EXHAUSTED)
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
            "authority_task_id": r21.TASK_ID,
            "authority_result_sha256": UPSTREAM_SHA256[R21_RESULT_RELATIVE],
            "rejected_weaker_sibling_head": WEAKER_SIBLING_HEAD,
            "rejected_lineage_band": "356,5xx,xxx",
        },
        "START_R3_BOUND": START_R3_BOUND,
        "START_OWNER_IDS": [START_STATE_ID],
        "CANONICAL_PRIMITIVES": canonical_primitives(),
        "CANONICAL_PRIMITIVE_STATUS": "PASS",
        "UPSTREAM_FINGERPRINTS_SHA256": verify_upstream_fingerprints(),
        "PRIOR_LEVEL_FINGERPRINTS": prior_level_fingerprints(),
        "CROSSOVER_DERIVATION": {
            "tail_base_constant": canonical_baseline(),
            "start_next_unclassified_loss": START_LOSS,
            "start_unclassified_tail_bound": START_UNCLASSIFIED_TAIL_BOUND,
            "success_b_threshold": SUCCESS_B_THRESHOLD,
            "success_b_tail_loss": canonical_baseline() - SUCCESS_B_THRESHOLD,
        },
        "STATE_TO_TAIL_SWITCH": state_to_tail_switch(chase),
        "STATE_STRUCTURAL_CERTIFICATES": [
            state_structural_certificate(identifier) for identifier in state_ids
        ],
        "OWNER_DISPATCH_RULE": (
            "classified vector owners first; a state at or below the tail yields to the tail; "
            "a state strictly above every other term is refined one maximizing member at a time"
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
                "STATE_TO_TAIL_SWITCH": result["STATE_TO_TAIL_SWITCH"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
