"""Chase the frozen R17 maximum across all three owner classes.

Only a live owner authorizes a new certificate. Tied vectors remain separate
terms, and a tied state/vector is resolved before descending the tail. Prior
levels are carried through pinned certificate files, with no prefix census.
An inherited vector is recovered directly from its ID and its certified
relaxation; a state member recovers every vector in its compression signature.
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

from lottolab.research import b649_k20_r3_tail_state_owner_chase_r17 as r17

r16 = r17.r16
r15 = r17.r15
r14 = r17.r14
r13 = r17.r13
r12 = r17.r12
r8 = r17.r8
r7 = r17.r7
r6 = r17.r6
r5 = r17.r5
CountVector = r17.CountVector
StateTerms = r17.StateTerms
dense, sparse, digest = r17.dense, r17.sparse, r17.digest
TASK_ID = "B649_K20_R3_THREE_CLASS_OWNER_CHASE_R18"
BASE_HEAD = "ca5211cb359b2757adb533bc46b47a264d62d485"
BASE_TREE = "681a059f5b7d32110c1f5e6f77c0c372e1170a86"
TASK_BRANCH = "codex/b649-k20-r3-three-class-owner-chase-r18"
START_R3_BOUND = 356_523_195
START_LOSS = 8_525_433
START_CLASSIFIED_MAXIMUM = 356_521_973
START_STATE_MAX_BOUND = 356_505_100
CLASSIFIED_CROSSOVER_LOSS = 8_526_655
STATE_CROSSOVER_LOSS = 8_543_528
TAIL_BASE_CONSTANT = 365_048_628
R4_REFERENCE_BOUND, INCUMBENT = 350_545_749, 313_239_661
OWNER_TRANSITION_LIMIT = 10
PROOF_WALL_BUDGET_SECONDS = 3_600.0
TAIL_ID = r17.TAIL_ID
STOP_A, STOP_B, STOP_C = r17.STOP_A, r17.STOP_B, r17.STOP_C
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_PATH = REPO_ROOT / (
    "docs/research/matrix-native-results/b649-k20-r3-three-class-owner-chase-r18-result.json"
)
UPSTREAM_SHA256 = {
    "src/lottolab/research/b649_k20_r3_tail_state_owner_chase_r17.py": (
        "0edad246de25771745a215b0d922fc27e8839c40472a2f9859dc9a242a000a3b"
    ),
    "docs/research/matrix-native-results/b649-k20-r3-tail-state-owner-chase-r17-result.json": (
        "b38e5dc8e21d59697ce805864060daef13f12b62b37ade1ad8d32ad63c2755d2"
    ),
}


def verify_upstream_fingerprints() -> dict[str, str]:
    observed = {
        relative: sha256((REPO_ROOT / relative).read_bytes()).hexdigest()
        for relative in UPSTREAM_SHA256
    }
    if observed != UPSTREAM_SHA256:
        raise AssertionError(f"R17 authority fingerprint mismatch: {observed}")
    # These validate certificate files, never the prior-level enumerators.
    r17.verify_upstream_fingerprints()
    return observed


@cache
def authority() -> dict[str, Any]:
    verify_upstream_fingerprints()
    stored = cast(dict[str, Any], json.loads(r17.RESULT_PATH.read_text(encoding="utf-8")))
    expected = {
        "TASK_ID": r17.TASK_ID,
        "R3_BOUND": START_R3_BOUND,
        "UNCLASSIFIED_TAIL_BOUND": START_R3_BOUND,
        "MAX_CLASSIFIED_TAIL_VECTOR_BOUND": START_CLASSIFIED_MAXIMUM,
        "STATE_MAX_BOUND": START_STATE_MAX_BOUND,
        "NEXT_UNCLASSIFIED_LOSS": START_LOSS,
        "FINAL_OWNER_IDS": [TAIL_ID],
    }
    if any(stored[key] != value for key, value in expected.items()):
        raise AssertionError("R17 authority differs from the R18 Packet")
    return stored


def canonical_primitives() -> dict[str, int]:
    observed = r17.canonical_primitives()
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
    for target, loss in (
        (START_CLASSIFIED_MAXIMUM, CLASSIFIED_CROSSOVER_LOSS),
        (START_STATE_MAX_BOUND, STATE_CROSSOVER_LOSS),
    ):
        if baseline - target != loss or baseline - loss != target:
            raise AssertionError("the independent crossover arithmetic failed")
        if baseline - (loss - 1) != target + 1:
            raise AssertionError("the crossover is not the first integer threshold")
    return baseline


def owner_class(identifier: str) -> str:
    if identifier == TAIL_ID:
        return "unclassified-tail"
    if identifier.startswith("tail-vector:"):
        return "classified-tail-vector"
    if identifier.startswith("state:"):
        return "state"
    raise AssertionError(f"unhandled owner identifier: {identifier}")


def owner_classes(identifiers: tuple[str, ...]) -> list[str]:
    return sorted({owner_class(identifier) for identifier in identifiers})


@dataclass
class Chase(r17.Chase):
    start_bound: int = START_R3_BOUND
    transition_limit: int = OWNER_TRANSITION_LIMIT
    refine_classified_owners: bool = True
    vector_records: dict[str, dict[str, Any]] = field(default_factory=lambda: {})

    def stop_condition(self) -> str | None:
        if self.bound <= self.r4_reference:
            return STOP_A
        if self.start_bound - self.bound >= self.drop_target:
            return STOP_B
        if self.transitions >= self.transition_limit:
            return STOP_C
        return None

    def competitor(self, identifier: str) -> int:
        return max(bound for other, bound in self.terms if other != identifier)

    def record_event(self, action: str, before: tuple[str, ...], previous: int) -> None:
        super().record_event(action, before, previous)
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
        classified_maximum=(str(stored["MAX_CLASSIFIED_TAIL_VECTOR_ID"]), START_CLASSIFIED_MAXIMUM),
        classified_terms=classified,
    )
    chase.sync_classified_maximum()
    if (
        len(states) != 23
        or chase.owners != (TAIL_ID,)
        or chase.bound != START_R3_BOUND
        or chase.state_max != START_STATE_MAX_BOUND
        or chase.classified_maximum[1] != START_CLASSIFIED_MAXIMUM
    ):
        raise AssertionError("the initial three-class maximum changed")
    return chase


def select_owner(chase: Chase) -> str:
    """Keep the entire tied set; prefer a tied non-tail certificate to descent."""

    return min(chase.owners, key=lambda identifier: (identifier == TAIL_ID, identifier))


def next_tail_level(chase: Chase) -> tuple[int, tuple[CountVector, ...], int]:
    chase.require_dispatch(TAIL_ID)
    if chase.tail_bound <= chase.competitor(TAIL_ID):
        raise AssertionError("tail descent at or below a competing owner is forbidden")
    if chase.next_loss < START_LOSS:
        raise AssertionError("prior tail levels must never be enumerated")
    losses = r6.local_losses(r5.anchor_incidence_profiles())
    vectors = tuple(sorted(r16.iter_interval_vectors(losses, 18, chase.next_loss, chase.next_loss)))
    if not vectors:
        raise AssertionError("the authoritative cursor must be an attained loss")
    lookahead = r16.next_attained_loss(losses, 18, chase.next_loss + 1)
    return chase.next_loss, vectors, lookahead


def classify_new_tail_vector(
    counts: CountVector, baseline: int, threshold: int
) -> r13.ClassifiedVector:
    loss = r12.local_loss(counts, r6.local_losses(r5.anchor_incidence_profiles()))
    if loss < START_LOSS:
        raise AssertionError("prior tail vectors must never be reclassified")
    return r13.classify_vector(counts, baseline, threshold)


def advance_tail(chase: Chase) -> None:
    loss, vectors, next_loss = next_tail_level(chase)
    before, previous = chase.owners, chase.bound
    threshold = chase.competitor(TAIL_ID)
    rows = tuple(classify_new_tail_vector(counts, chase.baseline, threshold) for counts in vectors)
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
            "four_ticket_applied_count": sum(
                row.four_ticket_status == r13.FOUR_TICKET_APPLIED for row in rows
            ),
            "realizable_count": sum(row.status == r12.WITNESS_REALIZED for row in rows),
            "unrealizable_count": sum(row.status == r12.ELIMINATED for row in rows),
            "unresolved_count": 0,
            "active_competing_threshold": threshold,
            "owner_set_at_dispatch": list(before),
        }
    )
    chase.record_event(f"tail:L{loss}", before, previous)


def recover_classified_vector(chase: Chase, owner_id: str) -> dict[str, Any]:
    """Recover just this owner and its original relaxation, without a level census."""

    chase.require_dispatch(owner_id)
    if not owner_id.startswith("tail-vector:"):
        raise AssertionError("classified-vector recovery requires a vector owner")
    counts = r17.counts_from_vector_id(owner_id)
    profiles = r5.anchor_incidence_profiles()
    loss = r12.local_loss(counts, r6.local_losses(profiles))
    envelope = r6.type_count_envelope(counts)
    prior = chase.classified_terms[owner_id]
    source: dict[str, Any] | None = chase.vector_records.get(owner_id)
    relaxation = "R6_PAIR_TRIPLE_AND_FOREST_ENVELOPE"
    if source is None:
        for stored in (authority(), r17.authority()):
            records = cast(list[dict[str, Any]], stored["CLASSIFIED_OWNER_CERTIFICATES"])
            source = next((row for row in reversed(records) if row["owner_id"] == owner_id), None)
            if source is not None:
                relaxation = "R8_EXACT_FOUR_EVENT_RATIONAL_PAIR_MOMENT"
                break
    anchor_s2 = sum(count * p.pair_recovery_cost for count, p in zip(counts, profiles, strict=True))
    anchor_s3 = sum(count * p.triple_recovery for count, p in zip(counts, profiles, strict=True))
    if r14.joint_constant() - anchor_s2 + anchor_s3 != chase.baseline - loss:
        raise AssertionError("the recovered vector's exact anchor expression changed")
    if source is not None:
        source_bound = int(source.get("new_bound", source.get("vector_bound", -1)))
        source_counts = (
            tuple(cast(list[int], source["counts"]))
            if "vector_id" in source
            else dense(cast(list[list[int]], source["counts"]))
        )
        if source_bound != prior or source_counts != counts:
            raise AssertionError("the certified structural record differs from its live term")
    elif loss == r16.R12_OWNER_LOSS:
        # The pinned R16 certificate already split this whole R12 level into IDs.
        # Reconstruct only this vector's original expression, never the level.
        if chase.baseline - loss - envelope.combined_pair_penalty != prior:
            raise AssertionError("the inherited R12 vector's R6 relaxation changed")
    else:
        relaxation = "PINNED_PRIOR_TAIL_VECTOR_CORRECTION"
        if prior > chase.baseline - loss - envelope.combined_pair_penalty:
            raise AssertionError("a carried correction is weaker than its original R6 floor")
    support = r12.construct_support_witness(counts)
    if support is None or not r8.validate_support_assignment(counts, support):
        raise AssertionError("the recovered classified owner has no verified support witness")
    return {
        "owner_id": owner_id,
        "source_loss_level": loss,
        "counts": sparse(counts),
        "anchor_type_records": [
            {"type_index": index, "count": count, **asdict(profiles[index])}
            for index, count in enumerate(counts)
            if count
        ],
        "anchor_pair_s2": anchor_s2,
        "anchor_triple_s3": anchor_s3,
        "r6_structural_record": asdict(envelope),
        "current_bound": prior,
        "current_correction": chase.baseline - loss - prior,
        "relaxation_producing_current_bound": relaxation,
        "prior_certificate": source,
        "support_witness": support,
        "support_witness_sha256": digest(support),
        "vector_recovery": "EXACT_FROZEN_VECTOR_ID_NO_LEVEL_CENSUS",
        "prior_level_enumeration_calls": 0,
        "prior_level_classification_calls": 0,
    }


def refine_classified_owner(chase: Chase, owner_id: str) -> None:
    chase.require_dispatch(owner_id)
    before, previous = chase.owners, chase.bound
    structural = recover_classified_vector(chase, owner_id)
    counts = dense(cast(list[list[int]], structural["counts"]))
    certificate = r14.moment_certificate(counts)
    prior = chase.classified_terms[owner_id]
    bound = min(
        prior,
        chase.baseline
        - int(structural["source_loss_level"])
        - int(certificate["correction_lower_bound"]),
    )
    if bound >= prior:
        raise r15.RationalRouteExhausted(owner_id)
    chase.classified_terms[owner_id] = bound
    chase.sync_classified_maximum()
    record = {
        "owner_id": owner_id,
        "owner_set_at_dispatch": list(before),
        "active_competing_threshold": chase.competitor(owner_id),
        "prior_bound": prior,
        "new_bound": bound,
        "structural_record": structural,
        "certificate": certificate,
        "tightening_route": "R8_EXACT_FOUR_EVENT_RATIONAL_PAIR_MOMENT",
        "counts": sparse(counts),
        "prior_level_classification_calls": 0,
        "no_other_classified_vectors_refined": True,
    }
    chase.classified_records.append(record)
    chase.vector_records[owner_id] = record
    chase.record_event(f"classified:{owner_id}", before, previous)


def frozen_state_record(owner_id: str) -> dict[str, Any]:
    """Use the latest complete compressed region certificate for this state."""

    for stored in (authority(), r17.authority(), r16.authority(), r15.authority()):
        records = cast(list[dict[str, Any]], stored["STATE_OWNER_CERTIFICATES"])
        for row in reversed(records):
            if row["owner_id"] == owner_id and "complete_region_members" in row:
                return row
    raise AssertionError("the current state has no frozen complete region record")


def refine_state_owner(chase: Chase, owner_id: str) -> None:
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
            "represented_vector_count": len(vectors),
            "vector_certificates": certificates,
            "support_witnesses": witnesses,
            "member_prior_bound": prior,
            "member_new_bound": bound,
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
    chase = initial_chase()
    while True:
        stop = chase.stop_condition()
        if stop is not None:
            return chase, stop, time.monotonic() - started
        if time.monotonic() - started >= wall_budget:
            return chase, r15.STOP_WALL, time.monotonic() - started
        owner = select_owner(chase)
        if owner == TAIL_ID:
            advance_tail(chase)
        elif owner.startswith("tail-vector:"):
            refine_classified_owner(chase, owner)
        elif owner.startswith("state:"):
            refine_state_owner(chase, owner)
        else:
            raise AssertionError(f"unhandled current owner: {owner}")


def build_result(*, wall_budget: float = PROOF_WALL_BUDGET_SECONDS) -> dict[str, Any]:
    chase, stop, wall = run_chase(wall_budget=wall_budget)
    transitions = [row for row in chase.events if row["from"] != row["to"]]
    state_ids = list(dict.fromkeys(str(row["owner_id"]) for row in chase.state_records))
    initial = dict(initial_chase().states)
    if (
        chase.bound != max(chase.tail_bound, chase.classified_maximum[1], chase.state_max)
        or len(transitions) > OWNER_TRANSITION_LIMIT
        or any(
            initial[identifier] != bound and identifier not in state_ids
            for identifier, bound in chase.states
        )
    ):
        raise AssertionError("the final maximum, owner budget, or state work guard failed")
    classes = owner_classes(chase.owners)
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "SUCCESS_" + stop[0] if stop in (STOP_A, STOP_B, STOP_C) else stop,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_BRANCH": TASK_BRANCH,
        "START_R3_BOUND": START_R3_BOUND,
        "CANONICAL_PRIMITIVES": canonical_primitives(),
        "CANONICAL_PRIMITIVE_STATUS": "PASS",
        "UPSTREAM_FINGERPRINTS_SHA256": verify_upstream_fingerprints(),
        "PRIOR_LEVEL_HANDLING": "PINNED_CERTIFICATES_NO_PRIOR_LEVEL_ENUMERATION",
        "CROSSOVER_DERIVATION": {
            "tail_base_constant": canonical_baseline(),
            "classified_maximum": START_CLASSIFIED_MAXIMUM,
            "classified_crossover_loss": CLASSIFIED_CROSSOVER_LOSS,
            "state_maximum": START_STATE_MAX_BOUND,
            "state_crossover_loss": STATE_CROSSOVER_LOSS,
        },
        "OWNER_TRANSITION_COUNT": len(transitions),
        "OWNER_TRANSITION_LIMIT": OWNER_TRANSITION_LIMIT,
        "OWNER_TRANSITIONS": transitions,
        "OWNER_CLASS_SEQUENCE": [
            owner_classes(initial_chase().owners),
            *[row["to_owner_classes"] for row in transitions],
        ],
        "OWNER_ACTION_TRAJECTORY": chase.events,
        "OWNER_TRANSITION_DEFINITION": "EXACT_OWNER_SET_CHANGE_INCLUDING_TIED_SET_CHANGES",
        "TAIL_LEVELS_PROCESSED": len(chase.tail_records),
        "TAIL_VECTORS_PROCESSED": sum(row["vector_count"] for row in chase.tail_records),
        "TAIL_LEVEL_CERTIFICATES": chase.tail_records,
        "NEW_TAIL_VECTOR_STRUCTURAL_RECORDS": [
            row for row in chase.vector_records.values() if "vector_id" in row
        ],
        "CLASSIFIED_VECTOR_OWNERS_PROCESSED": len(chase.classified_records),
        "CLASSIFIED_OWNER_CERTIFICATES": chase.classified_records,
        "STATE_OWNERS_PROCESSED": len(state_ids),
        "PROCESSED_STATE_OWNER_IDS": state_ids,
        "STATE_OWNER_CERTIFICATES": chase.state_records,
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
        "UNCLASSIFIED_TAIL_BOUND": chase.tail_bound,
        "NEXT_UNCLASSIFIED_LOSS": chase.next_loss,
        "MAX_CLASSIFIED_TAIL_VECTOR_BOUND": chase.classified_maximum[1],
        "MAX_CLASSIFIED_TAIL_VECTOR_ID": chase.classified_maximum[0],
        "STATE_MAX_BOUND": chase.state_max,
        "R3_BOUND": chase.bound,
        "R3_DROP": START_R3_BOUND - chase.bound,
        "R3_STATUS": "CERTIFIED_THREE_CLASS_OWNER_ONLY_RATIONAL_MOMENT_AND_ATTAINED_TAIL_BOUND",
        "R3_FORMULA": (
            "max(UNCLASSIFIED_TAIL_BOUND, MAX_CLASSIFIED_TAIL_VECTOR_BOUND, STATE_MAX_BOUND)"
        ),
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
        "SOLVER_CERTIFIED_BOUND": None,
        "PRIOR_TAIL_LEVELS_ENUMERATED": 0,
        "PRIOR_VECTORS_RECLASSIFIED": 0,
        "NON_OWNER_STATE_TERMS_CHANGED": 0,
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
        "CLASSIFIED_VECTOR_OWNERS_PROCESSED",
        "STATE_OWNERS_PROCESSED",
        "FINAL_BOUND_OWNER_CLASS",
        "FINAL_OWNER_IDS",
        "UNCLASSIFIED_TAIL_BOUND",
        "MAX_CLASSIFIED_TAIL_VECTOR_BOUND",
        "STATE_MAX_BOUND",
        "PROOF_WALL_SECONDS",
    )
    print(json.dumps({key: result[key] for key in keys}, indent=2))


if __name__ == "__main__":
    main()
