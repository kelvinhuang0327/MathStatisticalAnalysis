"""Resume the frozen R16 maximum, dispatching only its current owner.

Tail enumeration is one attained level at a time, with an integer lookahead
and no enumeration below the active cursor.  Old classifications are carried
by fingerprint.  Compressed state vectors are recovered at their exact losses,
without rebuilding the R7 frontier.  Inherited classified-owner refinement is
an explicit continuation option; identifying that owner is never Success C.
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from functools import cache
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from lottolab.research import b649_k20_r3_tail_state_owner_chase_r16 as r16

r15 = r16.r15
r14 = r15.r14
r13 = r15.r13
r12 = r15.r12
r8 = r15.r8
r7 = r15.r7
r6 = r15.r6
r5 = r15.r5
TASK_ID = "B649_K20_R3_TAIL_STATE_OWNER_CHASE_R17"
BASE_HEAD = "7de59633827227362b36dbf7e73656a4ec8e5197"
BASE_TREE = "37ad2ba34ece2df8b912b8ae44750c0e3bd5c07b"
TASK_BRANCH = "codex/b649-k20-r3-tail-state-owner-chase-r17"
START_R3_BOUND = 356_530_622
START_LOSS = 8_518_006
START_STATE_MAX_BOUND = 356_505_100
START_STATE_OWNER_ID = "state:s2-12692531-s3-681744"
START_CLASSIFIED_MAXIMUM = 356_527_168
START_CROSSOVER_LOSS = 8_543_528
TAIL_BASE_CONSTANT = 365_048_628
R4_REFERENCE_BOUND, INCUMBENT = 350_545_749, 313_239_661
OWNER_TRANSITION_LIMIT = 8
PROOF_WALL_BUDGET_SECONDS = 3_600.0
DROP_TARGET = 100_000
TAIL_ID = r15.TAIL_ID
STOP_A, STOP_B, STOP_C = r15.STOP_A, r15.STOP_B, r15.STOP_C
STOP_SCOPE = "CLASSIFIED_OWNER_CERTIFICATE_CONTINUATION_SCOPE_REQUIRED"
STOP_EXHAUSTED = "CURRENT_OWNER_RATIONAL_CERTIFICATE_EXHAUSTED"
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_PATH = REPO_ROOT / (
    "docs/research/matrix-native-results/b649-k20-r3-tail-state-owner-chase-r17-result.json"
)
UPSTREAM_SHA256 = {
    "src/lottolab/research/b649_k20_r3_tail_state_owner_chase_r16.py": (
        "7296c471b63e728e8d873878d96bf3ab84a78a951a288d4dd87aeea1cd882b9f"
    ),
    "docs/research/matrix-native-results/b649-k20-r3-tail-state-owner-chase-r16-result.json": (
        "7b7975b66b149eb37cfd688bc6878ef7f6461019b63b79642f13d7c432a21f70"
    ),
}
CountVector = r16.CountVector
StateTerms = r16.StateTerms
MemberBounds = r16.MemberBounds
digest, sparse, dense = r16.digest, r16.sparse, r16.dense


def verify_upstream_fingerprints() -> dict[str, str]:
    observed = {
        relative: sha256((REPO_ROOT / relative).read_bytes()).hexdigest()
        for relative in UPSTREAM_SHA256
    }
    if observed != UPSTREAM_SHA256:
        raise AssertionError(f"R16 authority fingerprint mismatch: {observed}")
    r16.authority()
    return observed


@cache
def authority() -> dict[str, Any]:
    verify_upstream_fingerprints()
    stored = cast(dict[str, Any], json.loads(r16.RESULT_PATH.read_text(encoding="utf-8")))
    expected = {
        "TASK_ID": r16.TASK_ID,
        "R3_BOUND": START_R3_BOUND,
        "FINAL_OWNER_IDS": [TAIL_ID],
        "NEXT_UNCLASSIFIED_LOSS": START_LOSS,
        "STATE_MAX_BOUND": START_STATE_MAX_BOUND,
        "UNCLASSIFIED_TAIL_BOUND": START_R3_BOUND,
        "MAX_CLASSIFIED_TAIL_VECTOR_BOUND": START_CLASSIFIED_MAXIMUM,
    }
    if any(stored[key] != value for key, value in expected.items()):
        raise AssertionError("R16 authority differs from the R17 Packet")
    return stored


def canonical_primitives() -> dict[str, int]:
    observed = r16.canonical_primitives()
    if observed != {
        "SINGLE_TICKET_ANY_PRIZE": 18_611_432,
        "PAIR_INTERSECTION_COST[6]": 18_611_432,
        "K20_S1": 372_228_640,
    }:
        raise AssertionError("canonical primitive preflight failed")
    return observed


def canonical_baseline() -> int:
    baseline = canonical_primitives()["K20_S1"] - r13.FIXED_CERTIFIED_LOSS
    if baseline != TAIL_BASE_CONSTANT or baseline != START_R3_BOUND + START_LOSS:
        raise AssertionError("the independent tail-base arithmetic failed")
    if baseline - START_STATE_MAX_BOUND != START_CROSSOVER_LOSS:
        raise AssertionError("the independent first crossover arithmetic failed")
    if baseline - (START_CROSSOVER_LOSS - 1) != START_STATE_MAX_BOUND + 1:
        raise AssertionError("the crossover is not the exact first integer threshold")
    return baseline


def initial_state_terms() -> StateTerms:
    terms = tuple(
        (str(row["stable_id"]), int(row["bound"]))
        for row in cast(list[dict[str, Any]], authority()["CURRENT_STATE_TERMS"])
    )
    if (
        len(terms) != 23
        or max(value for _, value in terms) != START_STATE_MAX_BOUND
        or r13.identify_owner_set(terms) != (START_STATE_OWNER_ID,)
    ):
        raise AssertionError("the frozen state maximum or tied state set changed")
    return terms


@cache
def verify_prior_level_fingerprints() -> dict[str, int]:
    """Fingerprint old vectors without support construction or classification."""

    prior = r16.verify_prior_level_fingerprints()
    losses = r6.local_losses(r5.anchor_incidence_profiles())
    grouped: dict[int, list[CountVector]] = {}
    for counts in r16.iter_interval_vectors(
        losses, r12.OUTSIDE_TICKET_COUNT, r16.START_LOSS, START_LOSS - 1
    ):
        grouped.setdefault(r12.local_loss(counts, losses), []).append(counts)
    observed = [
        (loss, len(rows), digest(tuple(sorted(rows)))) for loss, rows in sorted(grouped.items())
    ]
    records = cast(list[dict[str, Any]], authority()["TAIL_LEVEL_CERTIFICATES"])
    expected = [
        (int(row["local_loss"]), int(row["vector_count"]), str(row["counts_sha256"]))
        for row in records
    ]
    if observed != expected or int(records[-1]["next_unclassified_loss"]) != START_LOSS:
        raise AssertionError("R16's classified level fingerprints changed")
    return {**prior, "R16_LEVELS": len(records), "R16_VECTORS": sum(row[1] for row in observed)}


def counts_from_vector_id(identifier: str) -> CountVector:
    """Recover the frozen vector itself, never its earlier loss-level census."""

    prefix, loss_text, payload = identifier.split(":", 2)
    if prefix != "tail-vector" or not loss_text.startswith("L"):
        raise ValueError("a complete classified-vector identifier is required")
    pairs = [tuple(map(int, token.split("x"))) for token in payload.split(",")]
    if any(len(pair) != 2 for pair in pairs):
        raise ValueError("invalid sparse vector identifier")
    if len({pair[0] for pair in pairs}) != len(pairs):
        raise ValueError("duplicate type in vector identifier")
    profiles = r5.anchor_incidence_profiles()
    if any(not 0 <= index < len(profiles) or count <= 0 for index, count in pairs):
        raise ValueError("invalid type index or count")
    counts = dense(pairs)
    losses = r6.local_losses(profiles)
    if (
        sum(counts) != r12.OUTSIDE_TICKET_COUNT
        or r12.local_loss(counts, losses) != int(loss_text[1:])
        or r13.vector_id(counts, int(loss_text[1:])) != identifier
    ):
        raise AssertionError("the frozen vector identifier failed exact recovery")
    return counts


@dataclass
class Chase(r15.Chase):
    start_bound: int = START_R3_BOUND
    classified_terms: dict[str, int] = field(default_factory=lambda: {})
    classified_records: list[dict[str, Any]] = field(default_factory=lambda: [])
    refine_classified_owners: bool = False
    state_region_bounds: dict[str, MemberBounds] = field(default_factory=lambda: {})

    @property
    def terms(self) -> StateTerms:
        classified = tuple(self.classified_terms.items()) or (self.classified_maximum,)
        return (*self.states, (TAIL_ID, self.tail_bound), *classified)

    def sync_classified_maximum(self) -> None:
        self.classified_maximum = min(
            self.classified_terms.items(), key=lambda row: (-row[1], row[0])
        )

    def stop_condition(self) -> str | None:
        if self.bound <= self.r4_reference:
            return STOP_A
        if self.start_bound - self.bound >= self.drop_target:
            return STOP_B
        if self.transitions >= self.transition_limit:
            return STOP_C
        if all(owner.startswith("tail-vector:") for owner in self.owners) and (
            not self.refine_classified_owners
        ):
            return STOP_SCOPE
        return None

    def record_event(self, action: str, before: tuple[str, ...], previous: int) -> None:
        self._event(action, before, previous)


def initial_chase(*, refine_classified_owners: bool = False) -> Chase:
    stored = authority()
    classified = {
        str(row["stable_id"]): int(row["bound"])
        for row in cast(list[dict[str, Any]], stored["CURRENT_CLASSIFIED_TERMS"])
    }
    chase = Chase(
        states=initial_state_terms(),
        baseline=canonical_baseline(),
        next_loss=START_LOSS,
        classified_maximum=(str(stored["MAX_CLASSIFIED_TAIL_VECTOR_ID"]), START_CLASSIFIED_MAXIMUM),
        classified_terms=classified,
        refine_classified_owners=refine_classified_owners,
    )
    chase.sync_classified_maximum()
    if chase.owners != (TAIL_ID,) or chase.bound != START_R3_BOUND:
        raise AssertionError("the initial R17 owner selection failed")
    return chase


def next_tail_level(chase: Chase) -> tuple[int, tuple[CountVector, ...], int]:
    """Emit exactly the current attained level and one integer cursor lookahead."""

    chase.require_dispatch(TAIL_ID)
    if chase.tail_bound <= chase.state_max:
        raise AssertionError("tail descent below the active state threshold is forbidden")
    if chase.next_loss < START_LOSS:
        raise AssertionError("prior R13-R16 levels must never be enumerated for classification")
    losses = r6.local_losses(r5.anchor_incidence_profiles())
    counts = tuple(
        sorted(
            r16.iter_interval_vectors(
                losses, r12.OUTSIDE_TICKET_COUNT, chase.next_loss, chase.next_loss
            )
        )
    )
    if not counts:
        raise AssertionError("the authoritative cursor must be an attained loss")
    lookahead = r16.next_attained_loss(losses, r12.OUTSIDE_TICKET_COUNT, chase.next_loss + 1)
    return chase.next_loss, counts, lookahead


def classify_new_tail_vector(
    counts: CountVector, baseline: int, threshold: int
) -> r13.ClassifiedVector:
    loss = r12.local_loss(counts, r6.local_losses(r5.anchor_incidence_profiles()))
    if loss < START_LOSS:
        raise AssertionError("prior R13-R16 levels must never be reclassified")
    return r13.classify_vector(counts, baseline, threshold)


def advance_tail(chase: Chase) -> None:
    loss, vectors, next_loss = next_tail_level(chase)
    threshold = max(chase.state_max, chase.classified_maximum[1])

    def classify(counts: CountVector) -> r13.ClassifiedVector:
        row = classify_new_tail_vector(counts, chase.baseline, threshold)
        if row.vector_bound is not None:
            chase.classified_terms[row.vector_id] = row.vector_bound
            chase.sync_classified_maximum()
        return row

    chase.advance_tail(loss, vectors, next_loss, classify)
    chase.tail_records[-1]["active_competing_threshold"] = threshold
    chase.tail_records[-1]["owner_set_at_dispatch"] = chase.events[-1]["from"]


def refine_classified_owner(chase: Chase, owner_id: str) -> None:
    """Certificate-only refinement of one actual owner from a frozen vector ID."""

    chase.require_dispatch(owner_id)
    if not chase.refine_classified_owners or not owner_id.startswith("tail-vector:"):
        raise AssertionError("classified-owner continuation scope is required")
    before, previous = chase.owners, chase.bound
    counts = counts_from_vector_id(owner_id)
    loss = r12.local_loss(counts, r6.local_losses(r5.anchor_incidence_profiles()))
    if r13.START_UNCLASSIFIED_LOSS <= loss < START_LOSS:
        raise AssertionError("prior R13-R16 tail vectors permit fingerprint validation only")
    support = r12.construct_support_witness(counts)
    if support is None or not r8.validate_support_assignment(counts, support):
        raise AssertionError("the classified owner's support witness is invalid")
    certificate = r14.moment_certificate(counts)
    prior = chase.classified_terms[owner_id]
    bound = min(prior, chase.baseline - loss - int(certificate["correction_lower_bound"]))
    if bound >= prior:
        raise r15.RationalRouteExhausted(owner_id)
    chase.classified_terms[owner_id] = bound
    chase.sync_classified_maximum()
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
            "vector_recovery": "EXACT_FROZEN_VECTOR_ID_NO_LEVEL_CENSUS",
            "prior_level_classification_calls": 0,
        }
    )
    chase.record_event(f"classified:{owner_id}", before, previous)


def represented_vectors(
    members: Sequence[r7.ResidualJointState],
) -> dict[CountVector, tuple[CountVector, ...]]:
    """Recover all compressed vectors only at the selected members' exact losses."""

    profiles = r5.anchor_incidence_profiles()
    losses = r6.local_losses(profiles)
    make_state_api, signature_api = "_make_state", "_state_signature"
    make_state, signature = getattr(r7, make_state_api), getattr(r7, signature_api)
    targets = {signature(row): row.witness_counts for row in members}
    if len(targets) != len(members):
        raise AssertionError("owner members share a compression signature")
    found: dict[CountVector, list[CountVector]] = {row.witness_counts: [] for row in members}
    for loss in sorted({row.local_loss for row in members}):
        for counts in r16.iter_interval_vectors(losses, r12.OUTSIDE_TICKET_COUNT, loss, loss):
            if not r6.aggregate_count_vector_is_feasible(counts):
                continue
            row = make_state(counts, profiles, losses, check_feasibility=False)
            key = targets.get(signature(row))
            if key is not None:
                found[key].append(counts)
    for row in members:
        vectors = found[row.witness_counts]
        if len(vectors) != row.represented_vector_count or min(vectors) != row.witness_counts:
            raise AssertionError("a compressed member's represented vectors were not recovered")
    return {key: tuple(sorted(rows)) for key, rows in found.items()}


def refine_state_owner(chase: Chase, owner_id: str) -> None:
    """Refine one maximizing compressed member, then immediately reselect owner."""

    chase.require_dispatch(owner_id)
    if not owner_id.startswith("state:"):
        raise AssertionError("state proof requested for a non-state owner")
    records = cast(list[dict[str, Any]], authority()["STATE_OWNER_CERTIFICATES"])
    record = next(row for row in records if row["owner_id"] == owner_id)
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
    threshold = max(value for identifier, value in chase.terms if identifier != owner_id)
    counts = min(counts for counts, value in bounds.items() if value == prior)
    stored = next(row for row in region if dense(row["witness_counts"]) == counts)
    make_state_api = "_make_state"
    make_state = getattr(r7, make_state_api)
    profiles = r5.anchor_incidence_profiles()
    member = cast(
        r7.ResidualJointState,
        make_state(counts, profiles, r6.local_losses(profiles)),
    )
    member = replace(member, represented_vector_count=int(stored["represented_vector_count"]))
    if r14.raw_bound(member) != int(stored["raw_bound"]) or prior < threshold:
        raise AssertionError("a non-load-bearing compressed member was dispatched")
    vectors = represented_vectors((member,))[counts]
    certificates: list[dict[str, Any]] = []
    witnesses: list[dict[str, Any]] = []
    for vector in vectors:
        support = r12.construct_support_witness(vector)
        if support is None or not r8.validate_support_assignment(vector, support):
            raise AssertionError("a represented state vector has no verified support witness")
        certificates.append(r14.moment_certificate(vector))
        witnesses.append({"counts": sparse(vector), "support_witness": support})
    correction = max(
        member.applied_residual_union_penalty,
        min(int(row["correction_lower_bound"]) for row in certificates),
    )
    bound = min(
        prior, r14.joint_constant() - member.anchor_pair_s2 + member.anchor_triple_s3 - correction
    )
    if bound >= prior:
        raise r15.RationalRouteExhausted(owner_id)
    bounds[counts] = bound
    new_bound = max(bounds.values())
    certificate = {
        "owner_id": owner_id,
        "owner_set_at_dispatch": list(chase.owners),
        "prior_bound": prior,
        "new_bound": new_bound,
        "active_competing_threshold": threshold,
        "witness_counts": sparse(counts),
        "represented_vector_count": len(vectors),
        "vector_certificates": certificates,
        "support_witnesses": witnesses,
        "member_prior_bound": prior,
        "member_new_bound": bound,
        "region_sha256": record["region_sha256"],
        "no_other_state_terms_refined": True,
    }
    # Other maximizing members can keep this state tied at the same bound.
    chase.require_dispatch(owner_id)
    before, previous = chase.owners, chase.bound
    chase.states = tuple(
        (identifier, new_bound if identifier == owner_id else value)
        for identifier, value in chase.states
    )
    chase.state_records.append(certificate)
    chase.record_event(f"state:{owner_id}", before, previous)


def run_chase(
    *, refine_classified_owners: bool = False, wall_budget: float = PROOF_WALL_BUDGET_SECONDS
) -> tuple[Chase, str, float]:
    started = time.monotonic()
    canonical_primitives()
    verify_prior_level_fingerprints()
    chase = initial_chase(refine_classified_owners=refine_classified_owners)
    while True:
        stop = chase.stop_condition()
        if stop is not None:
            return chase, stop, time.monotonic() - started
        if time.monotonic() - started >= wall_budget:
            return chase, r15.STOP_WALL, time.monotonic() - started
        owner = chase.owners[0]
        try:
            if owner == TAIL_ID:
                advance_tail(chase)
            elif owner.startswith("state:"):
                refine_state_owner(chase, owner)
            elif owner.startswith("tail-vector:"):
                refine_classified_owner(chase, owner)
            else:
                raise AssertionError(f"unhandled current owner: {owner}")
        except r15.RationalRouteExhausted:
            return chase, STOP_EXHAUSTED, time.monotonic() - started


def build_result(*, refine_classified_owners: bool = False) -> dict[str, Any]:
    chase, stop, wall = run_chase(refine_classified_owners=refine_classified_owners)
    transitions = [row for row in chase.events if row["from"] != row["to"]]
    processed = list(dict.fromkeys(str(row["owner_id"]) for row in chase.state_records))
    initial = dict(initial_state_terms())
    if (
        chase.bound != max(chase.state_max, chase.tail_bound, chase.classified_maximum[1])
        or len(transitions) > OWNER_TRANSITION_LIMIT
        or any(initial[owner] != bound and owner not in processed for owner, bound in chase.states)
    ):
        raise AssertionError("the final coupled maximum, owner budget, or work guard failed")
    result: dict[str, Any] = {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "SUCCESS_" + stop[0] if stop in (STOP_A, STOP_B, STOP_C) else stop,
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
            "first_classified_owner_crossover_loss": TAIL_BASE_CONSTANT - START_CLASSIFIED_MAXIMUM,
        },
        "OWNER_TRANSITION_COUNT": len(transitions),
        "OWNER_TRANSITION_LIMIT": OWNER_TRANSITION_LIMIT,
        "OWNER_TRANSITIONS": transitions,
        "OWNER_ACTION_TRAJECTORY": chase.events,
        "TAIL_LEVELS_PROCESSED": len(chase.tail_records),
        "TAIL_VECTORS_PROCESSED": sum(row["vector_count"] for row in chase.tail_records),
        "TAIL_LEVEL_CERTIFICATES": chase.tail_records,
        "STATE_OWNERS_PROCESSED": len(processed),
        "PROCESSED_STATE_OWNER_IDS": processed,
        "STATE_OWNER_CERTIFICATES": chase.state_records,
        "CLASSIFIED_OWNERS_PROCESSED": len(chase.classified_records),
        "CLASSIFIED_OWNER_CERTIFICATES": chase.classified_records,
        "CLASSIFIED_OWNER_CONTINUATION_AUTHORIZED": refine_classified_owners,
        "CURRENT_STATE_TERMS": [
            {"stable_id": owner, "bound": bound} for owner, bound in chase.states
        ],
        "CURRENT_CLASSIFIED_TERMS": [
            {"stable_id": owner, "bound": bound} for owner, bound in chase.classified_terms.items()
        ],
        "FINAL_BOUND_OWNER": (
            "state"
            if chase.owners[0].startswith("state:")
            else "unclassified-tail"
            if chase.owners[0] == TAIL_ID
            else "classified-tail-vector"
        ),
        "FINAL_OWNER_IDS": list(chase.owners),
        "STATE_MAX_BOUND": chase.state_max,
        "UNCLASSIFIED_TAIL_BOUND": chase.tail_bound,
        "NEXT_UNCLASSIFIED_LOSS": chase.next_loss,
        "MAX_CLASSIFIED_TAIL_VECTOR_BOUND": chase.classified_maximum[1],
        "MAX_CLASSIFIED_TAIL_VECTOR_ID": chase.classified_maximum[0],
        "R3_BOUND": chase.bound,
        "R3_DROP": START_R3_BOUND - chase.bound,
        "R3_STATUS": "CERTIFIED_OWNER_ONLY_RATIONAL_MOMENT_AND_ATTAINED_TAIL_BOUND",
        "R3_FORMULA": "max(STATE_TERMS, UNCLASSIFIED_TAIL_BOUND, MAX_CLASSIFIED_TAIL_VECTOR_BOUND)",
        "R4_REFERENCE_BOUND": R4_REFERENCE_BOUND,
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": chase.bound - INCUMBENT,
        "STOP_CONDITION": stop,
        "SUCCESS_A": stop == STOP_A,
        "SUCCESS_B": stop == STOP_B,
        "SUCCESS_C": stop == STOP_C,
        "PROOF_WALL_SECONDS": wall,
        "PROOF_WALL_BUDGET_SECONDS": PROOF_WALL_BUDGET_SECONDS,
        "SOLVER_STATUS": (
            "NOT_DISPATCHED_CURRENT_PHASE_CERTIFIED_CONTINUATION_SCOPE_REQUIRED"
            if stop == STOP_SCOPE
            else "NOT_DISPATCHED_EXACT_RATIONAL_CERTIFICATES_SUFFICIENT"
        ),
        "SOLVER_CONFIGURED_WALL_LIMIT": None,
        "SOLVER_ACTUAL_WALL_TIME": 0.0,
        "SOLVER_CERTIFIED_BOUND": None,
        "PRIOR_VECTORS_RECLASSIFIED": 0,
        "NON_OWNER_STATE_TERMS_CHANGED": 0,
        "GENERIC_FRONTIER_CENSUS_CALLS": 0,
        "WORKTREE_DISPOSITION": "RETAIN",
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }
    if stop == STOP_SCOPE:
        result.update(
            {
                "BLOCKER_CODE": "CLASSIFIED_OWNER_CONTINUATION_RULE_UNSPECIFIED",
                "BLOCKER_DETAIL": (
                    f"Inherited classified vectors {list(chase.owners)} own R3={chase.bound}; "
                    f"the tail is {chase.tail_bound} and the state maximum is {chase.state_max}. "
                    "The Packet stops tail work here but supplies no inherited classified-owner "
                    "refinement rule. One transition does not satisfy Success C."
                ),
                "SMALLEST_NEXT_ACTION": (
                    "Authorize certificate-only refinement of the current inherited classified "
                    "owner, with exact frozen-vector recovery and no earlier level classification."
                ),
            }
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--refine-classified-owners", action="store_true")
    options = parser.parse_args()
    result = build_result(refine_classified_owners=options.refine_classified_owners)
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
        "FINAL_OWNER_IDS",
        "STATE_MAX_BOUND",
        "UNCLASSIFIED_TAIL_BOUND",
        "MAX_CLASSIFIED_TAIL_VECTOR_BOUND",
        "PROOF_WALL_SECONDS",
    )
    print(json.dumps({key: result[key] for key in keys}, indent=2))


if __name__ == "__main__":
    main()
