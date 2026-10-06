"""Continue R15's exact tail/state owner chase without replaying old proofs.

Only the live owner authorizes work. Prior levels are fingerprint checked;
new tail enumeration ends at the first attained crossover loss. State
regions reuse R14/R15 certificates, and every newly binding compressed
member receives the weakest certificate over all its represented vectors.
The inherited R12 maximizing level is recovered from its frozen certificate.
Only its currently maximizing vectors receive additional exact moment proofs;
R13/R14/R15 levels are never reclassified. Identifying a classified owner alone
does not exhaust the eight-transition budget.
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from functools import cache
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_r3_tail_to_state_owner_chase_r15 as r15

TASK_ID = "B649_K20_R3_TAIL_STATE_OWNER_CHASE_R16"
BASE_HEAD = "51d64c89cdf96b89bf5c1decc6235c829aeee089"
BASE_TREE = "5686a2fef114f1cfd8c56e9ece079963faf2b88f"
TASK_BRANCH = "codex/b649-k20-r3-tail-state-owner-chase-r16"
START_R3_BOUND = 356_598_858
START_LOSS = 8_449_770
START_STATE_MAX_BOUND = 356_551_580
START_STATE_OWNER_ID = "state:s2-12692531-s3-681744"
NEXT_STATE_ID = "state:s2-13169800-s3-789320"
NEXT_STATE_BOUND = 356_378_218
START_CLASSIFIED_MAXIMUM = 356_534_853
R12_OWNER_LOSS = 6_709_346
START_CROSSOVER_LOSS = 8_497_048
TAIL_BASE_CONSTANT = 365_048_628
DROP_TARGET = 100_000
OWNER_TRANSITION_LIMIT = 8
PROOF_WALL_BUDGET_SECONDS = 3_600.0
R4_REFERENCE_BOUND = r15.R4_REFERENCE_BOUND
INCUMBENT = r15.INCUMBENT
TAIL_ID = r15.TAIL_ID
STOP_A, STOP_B, STOP_C = r15.STOP_A, r15.STOP_B, r15.STOP_C
STOP_CLASSIFIED = "INHERITED_CLASSIFIED_VECTOR_OWNER_REQUIRES_CONTINUATION_SCOPE"
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_PATH = REPO_ROOT / (
    "docs/research/matrix-native-results/b649-k20-r3-tail-state-owner-chase-r16-result.json"
)
UPSTREAM_SHA256 = {
    "src/lottolab/research/b649_k20_r3_tail_to_state_owner_chase_r15.py": (
        "e1daab84f1ca47fa6ba1f2a75650f1e0fa9931984b5f0c662228f99391fced5f"
    ),
    "docs/research/matrix-native-results/b649-k20-r3-tail-to-state-owner-chase-r15-result.json": (
        "30ea29e74a0111aa4b3721cf79b781f076eaadc6e5d185c007fb05f551b88865"
    ),
}
CountVector = r15.CountVector
StateTerms = r15.StateTerms
MemberBounds = r15.MemberBounds
digest, sparse, dense = r15.digest, r15.sparse, r15.dense


def verify_upstream_fingerprints() -> dict[str, str]:
    observed = {
        relative: sha256((REPO_ROOT / relative).read_bytes()).hexdigest()
        for relative in UPSTREAM_SHA256
    }
    if observed != UPSTREAM_SHA256:
        raise AssertionError(f"R15 authority fingerprint mismatch: {observed}")
    r15.authority()
    return observed


@cache
def authority() -> dict[str, Any]:
    verify_upstream_fingerprints()
    stored = cast(dict[str, Any], json.loads(r15.RESULT_PATH.read_text(encoding="utf-8")))
    if (
        stored["TASK_ID"] != r15.TASK_ID
        or stored["R3_BOUND"] != START_R3_BOUND
        or stored["FINAL_OWNER_IDS"] != [TAIL_ID]
        or stored["UNCLASSIFIED_TAIL_BOUND"] != START_R3_BOUND
        or stored["NEXT_UNCLASSIFIED_LOSS"] != START_LOSS
        or stored["STATE_MAX_BOUND"] != START_STATE_MAX_BOUND
        or stored["STATE_MAX_OWNER_IDS"] != [START_STATE_OWNER_ID]
        or stored["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"] != START_CLASSIFIED_MAXIMUM
    ):
        raise AssertionError("R15 authority differs from the R16 Packet")
    return stored


def canonical_primitives() -> dict[str, int]:
    return r15.canonical_primitives()


def canonical_baseline() -> int:
    baseline = r15.canonical_baseline()
    if baseline != START_R3_BOUND + START_LOSS or baseline != TAIL_BASE_CONSTANT:
        raise AssertionError("the independent tail-base arithmetic failed")
    if baseline - START_STATE_MAX_BOUND != START_CROSSOVER_LOSS:
        raise AssertionError("the independent first crossover arithmetic failed")
    return baseline


def initial_state_terms() -> StateTerms:
    """Reconstruct the carried state terms by applying the frozen certificates."""

    terms = dict(r15.initial_state_terms())
    for record in cast(list[dict[str, Any]], authority()["STATE_OWNER_CERTIFICATES"]):
        identifier = str(record["owner_id"])
        if terms[identifier] != int(record["prior_bound"]):
            raise AssertionError("the inherited state certificate has the wrong prior bound")
        terms[identifier] = int(record["new_bound"])
    stored = tuple(
        (str(row["stable_id"]), int(row["bound"]))
        for row in cast(list[dict[str, Any]], authority()["CURRENT_STATE_TERMS"])
    )
    if tuple(terms.items()) != stored or len(stored) != 23:
        raise AssertionError("the reconstructed R15 state terms changed")
    ordered = sorted(stored, key=lambda row: row[1], reverse=True)
    independent_next = r15.r14.joint_constant() - 13_169_800 + 789_320
    if (
        ordered[0] != (START_STATE_OWNER_ID, START_STATE_MAX_BOUND)
        or ordered[1] != (NEXT_STATE_ID, independent_next)
        or independent_next != NEXT_STATE_BOUND
    ):
        raise AssertionError("the next competing state was not independently reconstructed")
    return stored


@cache
def verify_prior_level_fingerprints() -> dict[str, int]:
    """Validate old level identities without invoking any old classifier."""

    levels = r15.tail_census(START_LOSS)
    records = cast(list[dict[str, Any]], authority()["TAIL_LEVEL_CERTIFICATES"])
    observed = [(loss, len(vectors), digest(vectors)) for loss, vectors in levels[:-1]]
    expected = [
        (int(row["local_loss"]), int(row["vector_count"]), str(row["counts_sha256"]))
        for row in records
    ]
    if observed != expected or levels[-1][0] != START_LOSS:
        raise AssertionError("R15's classified level fingerprints changed")
    return {"R15_LEVELS": len(records), "R15_VECTORS": sum(row[1] for row in observed)}


def iter_interval_vectors(
    losses: Sequence[int], tickets: int, lower: int, upper: int
) -> Iterator[CountVector]:
    """Enumerate only the requested additive-loss interval, with exact pruning."""

    if not losses or losses[0] != 0 or any(loss <= 0 for loss in losses[1:]):
        raise ValueError("one zero type and strictly positive remaining losses are required")
    if tickets < 0 or lower < 0:
        raise ValueError("tickets and lower loss must be nonnegative")
    if upper < lower:
        return
    counts = [0] * len(losses)
    suffix_max = [max(losses[index:], default=0) for index in range(len(losses) + 1)]

    def visit(index: int, remaining: int, used: int) -> Iterator[CountVector]:
        if used + remaining * suffix_max[index] < lower:
            return
        if index == len(losses):
            counts[0] = remaining
            yield tuple(counts)
            counts[0] = 0
            return
        maximum = min(remaining, (upper - used) // losses[index])
        for amount in range(maximum + 1):
            counts[index] = amount
            yield from visit(index + 1, remaining - amount, used + amount * losses[index])
        counts[index] = 0

    yield from visit(1, tickets, 0)


def next_attained_loss(losses: Sequence[int], tickets: int, lower: int) -> int:
    """Find the first lookahead loss without emitting any later tail levels."""

    if (
        lower < 0
        or tickets < 0
        or not losses
        or losses[0] != 0
        or any(loss <= 0 for loss in losses[1:])
    ):
        raise ValueError("invalid attained-loss search")
    if lower == 0:
        return 0
    candidates = [
        ((lower + loss - 1) // loss) * loss
        for loss in losses[1:]
        if (lower + loss - 1) // loss <= tickets
    ]
    if not candidates:
        raise ValueError("the requested loss exceeds the finite type-count space")
    best = min(candidates)
    suffix_max = [max(losses[index:], default=0) for index in range(len(losses) + 1)]

    def visit(index: int, remaining: int, used: int) -> None:
        nonlocal best
        if used >= lower:
            best = min(best, used)
            return
        if index == len(losses) or used + remaining * suffix_max[index] < lower:
            return
        maximum = min(remaining, (best - 1 - used) // losses[index])
        for amount in range(maximum + 1):
            visit(index + 1, remaining - amount, used + amount * losses[index])

    visit(1, tickets, 0)
    return best


def tail_census(cursor: int, required_loss: int) -> tuple[tuple[int, tuple[CountVector, ...]], ...]:
    """Return load-bearing levels and exactly one unclassified lookahead level."""

    if cursor < START_LOSS or cursor >= required_loss:
        raise AssertionError("tail census outside the active owner interval is forbidden")
    losses = r15.r6.local_losses(r15.r5.anchor_incidence_profiles())
    tickets = r15.r12.OUTSIDE_TICKET_COUNT
    grouped: dict[int, list[CountVector]] = {}
    for counts in iter_interval_vectors(losses, tickets, cursor, required_loss - 1):
        grouped.setdefault(r15.r12.local_loss(counts, losses), []).append(counts)
    next_loss = next_attained_loss(losses, tickets, required_loss)
    lookahead = tuple(sorted(iter_interval_vectors(losses, tickets, next_loss, next_loss)))
    levels = tuple((loss, tuple(sorted(rows))) for loss, rows in sorted(grouped.items()))
    if not levels or levels[0][0] != cursor or not lookahead:
        raise AssertionError("the exact attained tail cursor or lookahead is missing")
    return (*levels, (next_loss, lookahead))


@dataclass
class Chase(r15.Chase):
    start_bound: int = START_R3_BOUND
    classified_terms: dict[str, int] = field(default_factory=lambda: {})
    r12_member_counts: dict[str, CountVector] = field(default_factory=lambda: {})
    classified_records: list[dict[str, Any]] = field(default_factory=lambda: [])
    r12_recovery: dict[str, Any] = field(default_factory=lambda: {})
    new_classified_maximum: tuple[str, int] | None = None

    @property
    def terms(self) -> StateTerms:
        if not self.classified_terms or not self.classified_records:
            return super().terms
        new = () if self.new_classified_maximum is None else (self.new_classified_maximum,)
        return (*self.states, (TAIL_ID, self.tail_bound), *self.classified_terms.items(), *new)

    def record_classified_event(
        self, owner_id: str, before: tuple[str, ...], previous: int
    ) -> None:
        self._event(f"classified:{owner_id}", before, previous)

    def stop_condition(self) -> str | None:
        if self.bound <= self.r4_reference:
            return STOP_A
        if self.start_bound - self.bound >= self.drop_target:
            return STOP_B
        if self.transitions >= self.transition_limit:
            return STOP_C
        original_r12 = self.classified_maximum[0].startswith(f"tail-vector:L{R12_OWNER_LOSS}:")
        if (
            not original_r12
            and all(owner.startswith("tail-vector:") for owner in self.owners)
            and any(owner not in self.r12_member_counts for owner in self.owners)
        ):
            return STOP_CLASSIFIED
        if (
            not original_r12
            and not self.classified_terms
            and self.owners == (self.classified_maximum[0],)
        ):
            return STOP_CLASSIFIED
        return None


def initial_chase() -> Chase:
    stored = authority()
    members: dict[str, MemberBounds] = {}
    for record in cast(list[dict[str, Any]], stored["STATE_OWNER_CERTIFICATES"]):
        members[str(record["owner_id"])] = {
            dense(cast(list[list[int]], row["witness_counts"])): int(row["certified_bound"])
            for row in cast(list[dict[str, Any]], record["region_moment_certificates"])
        }
    chase = Chase(
        states=initial_state_terms(),
        baseline=canonical_baseline(),
        next_loss=START_LOSS,
        classified_maximum=(str(stored["MAX_CLASSIFIED_TAIL_VECTOR_ID"]), START_CLASSIFIED_MAXIMUM),
        member_bounds=members,
    )
    return chase


def recover_r12_owner_level(chase: Chase) -> None:
    """Materialize the inherited owner envelope, without old level classification.

    The earlier exact run identified this R12 level as the active owner. Its
    stored census attests that every vector was realized. Rebuilding only its
    existing R6 expressions checks the stored maximum and minimum correction;
    no new support or moment refinement is performed during recovery.
    """

    if chase.classified_terms:
        return
    chase.require_dispatch(chase.classified_maximum[0])
    r12_stored = r15.r13.prior_authority()
    records = cast(list[dict[str, Any]], r12_stored["LOSS_LEVEL_ROWS"])
    record = next(row for row in records if int(row["local_loss"]) == R12_OWNER_LOSS)
    losses = r15.r6.local_losses(r15.r5.anchor_incidence_profiles())
    vectors = tuple(sorted(iter_interval_vectors(losses, 18, R12_OWNER_LOSS, R12_OWNER_LOSS)))
    if len(vectors) != record["vector_count"] or record["witness_realized"] != len(vectors):
        raise AssertionError("the inherited R12 owner level census changed")
    corrections: list[int] = []
    for counts in vectors:
        envelope = r15.r6.type_count_envelope(counts)
        corrections.append(envelope.combined_pair_penalty)
        identifier = r15.r13.vector_id(counts, R12_OWNER_LOSS)
        chase.r12_member_counts[identifier] = counts
        chase.classified_terms[identifier] = chase.baseline - R12_OWNER_LOSS - corrections[-1]
    if (
        max(chase.classified_terms.values()) != record["maximum_vector_bound"]
        or min(corrections) != record["minimum_correction"]
        or max(chase.classified_terms.values()) != START_CLASSIFIED_MAXIMUM
    ):
        raise AssertionError("the recovered R12 certificate does not match its stored maximum")
    r13_stored = r15.r14.authority()
    r13_max = cast(dict[str, Any], r13_stored["CLASSIFIED_VECTOR_CORRECTIONS"]["NEW_WORST_VECTOR"])
    chase.classified_terms[str(r13_max["VECTOR_ID"])] = int(r13_max["VECTOR_BOUND"])
    other_r12_max = max(
        int(row["maximum_vector_bound"])
        for row in records
        if int(row["local_loss"]) != R12_OWNER_LOSS
    )
    chase.classified_terms["carried-r12-other-levels"] = other_r12_max
    later_max = max(
        int(row["maximum_new_vector_bound"])
        for stored in (r15.authority(), authority())
        for row in cast(list[dict[str, Any]], stored["TAIL_LEVEL_CERTIFICATES"])
        if row["maximum_new_vector_bound"] is not None
    )
    if later_max > int(r13_max["VECTOR_BOUND"]):
        raise AssertionError("an inherited R14/R15 level needs a separate classified term")
    chase.r12_recovery = {
        "local_loss": R12_OWNER_LOSS,
        "vector_count": len(vectors),
        "counts_sha256": digest(vectors),
        "stored_maximum": record["maximum_vector_bound"],
        "stored_minimum_correction": record["minimum_correction"],
        "other_r12_levels_carried_maximum": other_r12_max,
        "r13_maximum_carried_by_fingerprint": r13_max,
        "r14_r15_new_vector_maximum_carried_by_fingerprint": later_max,
        "classification_calls": 0,
        "support_constructions": 0,
        "recovery_counts_as_owner_transition": False,
        "aggregate_owner_retained_until_first_certificate": True,
    }


def refine_classified_owner(chase: Chase, owner_id: str) -> None:
    chase.require_dispatch(owner_id)
    if owner_id not in chase.r12_member_counts:
        raise AssertionError("only the recovered R12 owner level may receive a new certificate")
    before, previous = chase.owners, chase.bound
    counts = chase.r12_member_counts[owner_id]
    support = r15.r12.construct_support_witness(counts)
    if support is None or not r15.r8.validate_support_assignment(counts, support):
        raise AssertionError("the classified owner's support witness is invalid")
    certificate = r15.r14.moment_certificate(counts)
    prior = chase.classified_terms[owner_id]
    correction = max(
        int(certificate["correction_lower_bound"]), chase.baseline - R12_OWNER_LOSS - prior
    )
    bound = chase.baseline - R12_OWNER_LOSS - correction
    if bound >= prior:
        raise r15.RationalRouteExhausted(owner_id)
    chase.classified_terms[owner_id] = bound
    new_terms = list(chase.classified_terms.items())
    if chase.new_classified_maximum is not None:
        new_terms.append(chase.new_classified_maximum)
    chase.classified_maximum = min(new_terms, key=lambda row: (-row[1], row[0]))
    chase.classified_records.append(
        {
            "owner_id": owner_id,
            "owner_set_at_dispatch": list(before),
            "prior_bound": prior,
            "new_bound": bound,
            "counts": sparse(counts),
            "support_witness": support,
            "support_witness_sha256": digest(support),
            "certificate": certificate,
            "next_classified_owner_ids": [
                identifier
                for identifier, value in new_terms
                if value == chase.classified_maximum[1]
            ],
            "next_classified_bound": chase.classified_maximum[1],
            "prior_level_classification_calls": 0,
        }
    )
    chase.record_classified_event(owner_id, before, previous)


def classify_new_tail_vector(
    counts: CountVector, baseline: int, threshold: int
) -> r15.r13.ClassifiedVector:
    loss = r15.r12.local_loss(counts, r15.r6.local_losses(r15.r5.anchor_incidence_profiles()))
    if loss < START_LOSS:
        raise AssertionError("prior R13/R14/R15 levels must never be reclassified")
    return r15.r13.classify_vector(counts, baseline, threshold)


def certify_state(chase: Chase, owner_id: str) -> tuple[dict[str, Any], MemberBounds]:
    chase.require_dispatch(owner_id)
    record, members = r15.certify_state(chase, owner_id)
    region = r15.r14.owner_region(owner_id)
    record["prior_r16_refined_member_count"] = record.pop("prior_r15_refined_member_count")
    record["complete_region_members"] = [
        {
            "witness_counts": sparse(row.witness_counts),
            "represented_vector_count": row.represented_vector_count,
            "raw_bound": r15.r14.raw_bound(row),
            "final_bound": members.get(row.witness_counts, r15.r14.raw_bound(row)),
        }
        for row in region
    ]
    return record, members


def run_chase(*, wall_budget: float = PROOF_WALL_BUDGET_SECONDS) -> tuple[Chase, str, float]:
    started = time.monotonic()
    canonical_primitives()
    verify_prior_level_fingerprints()
    chase = initial_chase()
    if chase.owners != (TAIL_ID,) or chase.bound != START_R3_BOUND:
        raise AssertionError("the initial R16 owner selection failed")
    while True:
        stop = chase.stop_condition()
        if stop is not None:
            return chase, stop, time.monotonic() - started
        if time.monotonic() - started >= wall_budget:
            return chase, r15.STOP_WALL, time.monotonic() - started
        owner = chase.owners[0]
        if owner.startswith("state:"):
            try:
                certificate, members = certify_state(chase, owner)
            except r15.RationalRouteExhausted:
                return chase, r15.STOP_EXHAUSTED, time.monotonic() - started
            chase.improve_state(owner, certificate, members)
        elif owner == TAIL_ID:
            target = max(
                chase.state_max, chase.classified_maximum[1], chase.start_bound - DROP_TARGET
            )
            levels = tail_census(chase.next_loss, chase.baseline - target)
            for index, (loss, vectors) in enumerate(levels[:-1]):
                if chase.stop_condition() is not None or TAIL_ID not in chase.owners:
                    break
                if chase.tail_bound <= chase.state_max:
                    break
                if time.monotonic() - started >= wall_budget:
                    return chase, r15.STOP_WALL, time.monotonic() - started
                threshold = max(chase.state_max, chase.classified_maximum[1])

                def classify(
                    counts: CountVector, threshold: int = threshold
                ) -> r15.r13.ClassifiedVector:
                    row = classify_new_tail_vector(counts, chase.baseline, threshold)
                    if row.vector_bound is not None and (
                        chase.new_classified_maximum is None
                        or row.vector_bound > chase.new_classified_maximum[1]
                    ):
                        chase.new_classified_maximum = row.vector_id, row.vector_bound
                    return row

                chase.advance_tail(
                    loss,
                    vectors,
                    levels[index + 1][0],
                    classify,
                )
                chase.tail_records[-1]["active_competing_threshold"] = threshold
        elif owner.startswith(f"tail-vector:L{R12_OWNER_LOSS}:"):
            recover_r12_owner_level(chase)
            try:
                refine_classified_owner(chase, owner)
            except r15.RationalRouteExhausted:
                return chase, r15.STOP_EXHAUSTED, time.monotonic() - started
        else:
            raise AssertionError(f"unhandled owner: {owner}")


def build_result() -> dict[str, Any]:
    chase, stop, wall = run_chase()
    transitions = [row for row in chase.events if row["from"] != row["to"]]
    if (
        chase.bound != max(chase.state_max, chase.tail_bound, chase.classified_maximum[1])
        or len(transitions) > OWNER_TRANSITION_LIMIT
    ):
        raise AssertionError("the final coupled maximum or transition budget is invalid")
    initial = dict(initial_state_terms())
    processed = [str(record["owner_id"]) for record in chase.state_records]
    if any(
        initial[identifier] != bound and identifier not in processed
        for identifier, bound in chase.states
    ):
        raise AssertionError("a non-owner state term changed")
    success = stop in (STOP_A, STOP_B, STOP_C)
    result = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "SUCCESS_" + stop[0] if success else stop,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_BRANCH": TASK_BRANCH,
        "START_R3_BOUND": START_R3_BOUND,
        "CANONICAL_PRIMITIVES": canonical_primitives(),
        "CANONICAL_PRIMITIVE_STATUS": "PASS",
        "UPSTREAM_FINGERPRINTS_SHA256": verify_upstream_fingerprints(),
        "PRIOR_LEVEL_FINGERPRINT_VALIDATION": verify_prior_level_fingerprints(),
        "CROSSOVER_DERIVATION": {
            "tail_base_constant": canonical_baseline(),
            "state_max_bound": START_STATE_MAX_BOUND,
            "required_next_unclassified_loss": START_CROSSOVER_LOSS,
            "tail_at_required_loss": TAIL_BASE_CONSTANT - START_CROSSOVER_LOSS,
            "tail_one_below_required_loss": TAIL_BASE_CONSTANT - START_CROSSOVER_LOSS + 1,
            "next_state_id": NEXT_STATE_ID,
            "next_state_bound": NEXT_STATE_BOUND,
        },
        "OWNER_TRANSITION_COUNT": len(transitions),
        "OWNER_TRANSITION_LIMIT": OWNER_TRANSITION_LIMIT,
        "OWNER_TRANSITIONS": transitions,
        "OWNER_ACTION_TRAJECTORY": chase.events,
        "STATE_OWNERS_PROCESSED": len(chase.state_records),
        "PROCESSED_STATE_OWNER_IDS": processed,
        "STATE_OWNER_CERTIFICATES": chase.state_records,
        "CLASSIFIED_OWNERS_PROCESSED": len(chase.classified_records),
        "CLASSIFIED_OWNER_CERTIFICATES": chase.classified_records,
        "R12_OWNER_LEVEL_RECOVERY": chase.r12_recovery,
        "CURRENT_CLASSIFIED_TERMS": [
            {"stable_id": identifier, "bound": value}
            for identifier, value in (
                *chase.classified_terms.items(),
                *((chase.new_classified_maximum,) if chase.new_classified_maximum else ()),
            )
        ],
        "TAIL_LEVELS_PROCESSED": len(chase.tail_records),
        "TAIL_VECTORS_PROCESSED": sum(row["vector_count"] for row in chase.tail_records),
        "TAIL_FOUR_TICKET_APPLIED_VECTORS": sum(
            row["four_ticket_applied_count"] for row in chase.tail_records
        ),
        "TAIL_LEVEL_CERTIFICATES": chase.tail_records,
        "FINAL_BOUND_OWNER": (
            "state"
            if chase.owners[0].startswith("state:")
            else "tail"
            if chase.owners[0] == TAIL_ID
            else "classified-tail-vector"
        ),
        "FINAL_OWNER_IDS": list(chase.owners),
        "STATE_MAX_BOUND": chase.state_max,
        "UNCLASSIFIED_TAIL_BOUND": chase.tail_bound,
        "NEXT_UNCLASSIFIED_LOSS": chase.next_loss,
        "MAX_CLASSIFIED_TAIL_VECTOR_BOUND": chase.classified_maximum[1],
        "MAX_CLASSIFIED_TAIL_VECTOR_ID": chase.classified_maximum[0],
        "CURRENT_STATE_TERMS": [
            {"stable_id": identifier, "bound": bound} for identifier, bound in chase.states
        ],
        "R3_BOUND": chase.bound,
        "R3_DROP": START_R3_BOUND - chase.bound,
        "R3_STATUS": "CERTIFIED_OWNER_ONLY_RATIONAL_MOMENT_AND_ATTAINED_TAIL_BOUND",
        "R3_FORMULA": "max(UNCLASSIFIED_TAIL_BOUND, STATE_TERMS, MAX_CLASSIFIED_TAIL_VECTOR_BOUND)",
        "R4_REFERENCE_BOUND": R4_REFERENCE_BOUND,
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": chase.bound - INCUMBENT,
        "STOP_CONDITION": stop,
        "SUCCESS_A": stop == STOP_A,
        "SUCCESS_B": stop == STOP_B,
        "SUCCESS_C": stop == STOP_C,
        "PROOF_WALL_SECONDS": wall,
        "PROOF_WALL_BUDGET_SECONDS": PROOF_WALL_BUDGET_SECONDS,
        "SOLVER_STATUS": "NOT_DISPATCHED_EXACT_RATIONAL_CERTIFICATES_SUFFICIENT",
        "SOLVER_CONFIGURED_WALL_LIMIT": None,
        "SOLVER_ACTUAL_WALL_TIME": 0.0,
        "SOLVER_CERTIFIED_BOUND": None,
        "PRIOR_VECTORS_RECLASSIFIED": 0,
        "NON_OWNER_STATE_TERMS_CHANGED": 0,
        "WORKTREE_DISPOSITION": "RETAIN",
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }
    if stop == STOP_CLASSIFIED:
        result.update(
            {
                "BLOCKER_CODE": "CLASSIFIED_OWNER_CONTINUATION_SCOPE_UNSPECIFIED",
                "BLOCKER_DETAIL": (
                    f"Inherited owner {chase.owners[0]} has bound {chase.bound}; "
                    f"the Success B target is {START_R3_BOUND - DROP_TARGET}. The Packet "
                    "defines tail/state dispatch and forbids prior-level replay, but does not "
                    "define inherited classified-vector refinement. Three transitions do not "
                    "satisfy the eight-transition Success C stop."
                ),
                "SMALLEST_NEXT_ACTION": (
                    "Authorize certificate-only refinement of the inherited classified owner "
                    "and recovery of its next competing classified bound, without old level replay."
                ),
            }
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-write", action="store_true")
    options = parser.parse_args()
    result = build_result()
    if not options.no_write:
        RESULT_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "TASK_STATUS",
                    "R3_BOUND",
                    "R3_DROP",
                    "OWNER_TRANSITION_COUNT",
                    "TAIL_LEVELS_PROCESSED",
                    "TAIL_VECTORS_PROCESSED",
                    "STATE_OWNERS_PROCESSED",
                    "FINAL_OWNER_IDS",
                    "STATE_MAX_BOUND",
                    "UNCLASSIFIED_TAIL_BOUND",
                    "MAX_CLASSIFIED_TAIL_VECTOR_BOUND",
                    "PROOF_WALL_SECONDS",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
