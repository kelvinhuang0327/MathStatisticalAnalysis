"""Certify the complete live tail band below the frozen R20 state maximum.

Carry committed classified terms; recover only a live vector owner.  Stop its
correction stack at the first sufficient exact rational certificate.  Resume
attained tail levels at R20's cursor, reselecting all owners after every action.
Neither a transition count nor a drop target ends the walk.  State terms are
immutable, including after the state crossover.
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

from lottolab.research import b649_k20_r3_tail_crossover_and_state_refinement_r20 as r20
from lottolab.research.b649_k20_r3_tail_threshold_to_top_state_r13 import ClassifiedVector

r19, r17, r16 = r20.r19, r20.r17, r20.r16
r14, r13, r12 = r20.r14, r20.r13, r20.r12
r8, r6, r5 = r20.r8, r20.r6, r20.r5
CountVector = r20.CountVector
owner_class, owner_classes, select_owner = r20.owner_class, r20.owner_classes, r20.select_owner
TASK_ID = "B649_K20_R3_CLASSIFIED_TAIL_BAND_TO_STATE_R21"
BASE_HEAD = "ef5c56e64cbd9fd3e07d49b8658ecd3f71a105cd"
BASE_TREE = "f5bf9f75a9457e6167d65da5752119687c0088d1"
TASK_BRANCH = "codex/b649-k20-r3-classified-tail-band-to-state-r21"
START_OWNER_ID = "tail-vector:L6742484:0x6,1x11,6x1"
START_R3_BOUND = START_CLASSIFIED_OWNER_BOUND = 356_501_945
START_LOSS = 8_546_832
START_UNCLASSIFIED_TAIL_BOUND = 356_501_796
STATE_THRESHOLD = STATE_MAX_BOUND = 356_378_218
TAIL_BASE_CONSTANT = 365_048_628
STATE_CROSSOVER_LOSS = 8_670_410
R4_REFERENCE_BOUND, INCUMBENT = 350_545_749, 313_239_661
PROOF_WALL_BUDGET_SECONDS = 3_600.0
TAIL_ID = r20.TAIL_ID
STOP_A = "A_COMPLETE_TAIL_BAND_AT_OR_BELOW_FROZEN_STATE"
STOP_B = "B_R3_AT_OR_BELOW_R4_REFERENCE"
STOP_WALL = "PROOF_WALL_BUDGET_EXHAUSTED"
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_PATH = REPO_ROOT / (
    "docs/research/matrix-native-results/b649-k20-r3-classified-tail-band-to-state-r21-result.json"
)
UPSTREAM_SHA256 = {
    "src/lottolab/research/b649_k20_r3_tail_crossover_and_state_refinement_r20.py": (
        "f3791b46291a549bc49717b05f4a2c39a75eea5204feb3b9a242455d8f73848b"
    ),
    "docs/research/matrix-native-results/"
    "b649-k20-r3-tail-crossover-and-state-refinement-r20-result.json": (
        "65682bd1b41aafe1d8b398b224caf704686a9820c203fcfe61a904e83b16f72b"
    ),
}


def verify_upstream_fingerprints() -> dict[str, str]:
    observed = {
        relative: sha256((REPO_ROOT / relative).read_bytes()).hexdigest()
        for relative in UPSTREAM_SHA256
    }
    if observed != UPSTREAM_SHA256:
        raise AssertionError(f"R20 authority fingerprint mismatch: {observed}")
    r20.verify_upstream_fingerprints()  # Files only, never prior-level enumerators.
    return observed


@cache
def authority() -> dict[str, Any]:
    verify_upstream_fingerprints()
    stored = cast(dict[str, Any], json.loads(r20.RESULT_PATH.read_text(encoding="utf-8")))
    expected = {
        "TASK_ID": r20.TASK_ID,
        "TASK_STATUS": "SUCCESS_C",
        "R3_BOUND": START_R3_BOUND,
        "FINAL_OWNER_IDS": [START_OWNER_ID],
        "NEXT_UNCLASSIFIED_LOSS": START_LOSS,
        "UNCLASSIFIED_TAIL_BOUND": START_UNCLASSIFIED_TAIL_BOUND,
        "MAX_CLASSIFIED_TAIL_VECTOR_BOUND": START_CLASSIFIED_OWNER_BOUND,
        "MAX_CLASSIFIED_TAIL_VECTOR_ID": START_OWNER_ID,
        "STATE_MAX_BOUND": STATE_MAX_BOUND,
    }
    if any(stored[key] != value for key, value in expected.items()):
        raise AssertionError("R20 authority differs from the R21 Packet")
    return stored


def canonical_primitives() -> dict[str, int]:
    observed = r20.canonical_primitives()
    if tuple(observed.values()) != (18_611_432, 18_611_432, 372_228_640):
        raise AssertionError("canonical primitive preflight failed")
    return observed


def canonical_baseline() -> int:
    baseline = canonical_primitives()["K20_S1"] - r13.FIXED_CERTIFIED_LOSS
    if (
        baseline != TAIL_BASE_CONSTANT
        or baseline - START_LOSS != START_UNCLASSIFIED_TAIL_BOUND
        or baseline - STATE_THRESHOLD != STATE_CROSSOVER_LOSS
        or baseline - (STATE_CROSSOVER_LOSS - 1) != STATE_THRESHOLD + 1
    ):
        raise AssertionError("the independent state-crossover arithmetic failed")
    return baseline


def require_unclassified_cursor(loss: int) -> None:
    if loss < START_LOSS:
        raise AssertionError("prior tail enumeration or reclassification is forbidden")


@cache
def prior_level_fingerprints() -> dict[str, Any]:
    rows = cast(list[dict[str, Any]], authority()["TAIL_LEVEL_CERTIFICATES"])
    if (
        int(rows[0]["local_loss"]) != r20.START_LOSS
        or any(
            int(row["next_unclassified_loss"]) != int(following["local_loss"])
            for row, following in pairwise(rows)
        )
        or int(rows[-1]["next_unclassified_loss"]) != START_LOSS
        or any(int(row["unresolved_count"]) for row in rows)
    ):
        raise AssertionError("the pinned R20 levels do not end at the R21 cursor")
    return {
        "r20_certified_levels": len(rows),
        "r20_certified_vectors": sum(int(row["vector_count"]) for row in rows),
        "r20_certified_level_range": [rows[0]["local_loss"], rows[-1]["local_loss"]],
        "r20_level_counts_sha256": r20.digest(tuple(row["counts_sha256"] for row in rows)),
        "r21_first_unclassified_loss": START_LOSS,
        "prior_level_enumeration_calls": 0,
    }


@dataclass
class Chase(r19.Chase):
    start_bound: int = START_R3_BOUND
    transition_limit: int = 0
    tail_vector_records: list[dict[str, Any]] = field(default_factory=lambda: [])

    def stop_condition(self) -> str | None:
        if self.bound <= self.r4_reference:
            return STOP_B
        if self.tail_bound <= self.state_max and self.classified_maximum[1] <= self.state_max:
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
        classified_maximum=(START_OWNER_ID, START_CLASSIFIED_OWNER_BOUND),
        classified_terms=classified,
    )
    chase.sync_classified_maximum()
    if (
        len(states) != 23
        or chase.owners != (START_OWNER_ID,)
        or chase.bound != START_R3_BOUND
        or chase.state_max != STATE_MAX_BOUND
        or chase.classified_maximum != (START_OWNER_ID, START_CLASSIFIED_OWNER_BOUND)
    ):
        raise AssertionError("the current classified-owner identity changed")
    return chase


def refine_classified_owner(chase: Chase, identifier: str) -> None:
    chase.require_dispatch(identifier)
    if not identifier.startswith("tail-vector:"):
        raise AssertionError("a classified vector owner is required")
    prior = chase.classified_terms[identifier]
    if prior <= chase.state_max:
        raise AssertionError("further correction at or below state is forbidden")
    before, previous = chase.owners, chase.bound
    threshold = (
        max(chase.state_max, chase.competitor(identifier))
        if identifier == START_OWNER_ID
        else chase.state_max
    )
    structural = r19.recover_classified_vector(chase, identifier)
    if identifier == START_OWNER_ID and (
        int(structural["current_correction"])
        != int(structural["r6_structural_record"]["combined_pair_penalty"])
        or int(structural["source_loss_level"]) != 6_742_484
    ):
        raise AssertionError("the starting owner's R6 relaxation changed")
    counts = r20.dense(cast(list[list[int]], structural["counts"]))
    # First sufficient route only: a naturally stronger result is retained,
    # but never authorizes another dispatch once ownership has passed away.
    certificate = r14.moment_certificate(counts)
    bound = min(
        prior,
        chase.baseline
        - int(structural["source_loss_level"])
        - int(certificate["correction_lower_bound"]),
    )
    if bound >= prior or bound > threshold:
        raise r20.r15.RationalRouteExhausted(identifier)
    record = {
        "owner_id": identifier,
        "owner_set_at_dispatch": list(before),
        "active_competing_threshold": threshold,
        "state_threshold": chase.state_max,
        "prior_bound": prior,
        "new_bound": bound,
        "structural_record": structural,
        "certificate": certificate,
        "counts": r20.sparse(counts),
        "tightening_route": r19.RATIONAL_MOMENT_ROUTE,
        "first_sufficient_certificate": True,
        "further_refinement_dispatched": False,
        "no_other_classified_vectors_refined": True,
        "prior_level_classification_calls": 0,
    }
    chase.classified_terms[identifier] = bound
    chase.vector_records[identifier] = record
    chase.classified_records.append(record)
    chase.sync_classified_maximum()
    chase.record_event(f"classified:{identifier}", before, previous)


def next_tail_level(chase: Chase) -> tuple[int, tuple[CountVector, ...], int]:
    chase.require_dispatch(TAIL_ID)
    require_unclassified_cursor(chase.next_loss)
    if chase.next_loss >= STATE_CROSSOVER_LOSS or chase.tail_bound <= chase.competitor(TAIL_ID):
        raise AssertionError("tail descent at or below the active threshold is forbidden")
    losses = r6.local_losses(r5.anchor_incidence_profiles())
    vectors = tuple(sorted(r16.iter_interval_vectors(losses, 18, chase.next_loss, chase.next_loss)))
    if not vectors:
        raise AssertionError("the cursor must be an attained loss")
    lookahead = r16.next_attained_loss(losses, 18, chase.next_loss + 1)
    if lookahead <= chase.next_loss:
        raise AssertionError("the attained tail cursor must strictly advance")
    return chase.next_loss, vectors, lookahead


def classify_new_tail_vector(counts: CountVector, baseline: int) -> ClassifiedVector:
    loss = r12.local_loss(counts, r6.local_losses(r5.anchor_incidence_profiles()))
    require_unclassified_cursor(loss)
    if loss >= STATE_CROSSOVER_LOSS:
        raise AssertionError("tail classification at or below state is forbidden")
    return r13.classify_vector(counts, baseline, STATE_THRESHOLD)


def advance_tail(chase: Chase) -> None:
    loss, vectors, next_loss = next_tail_level(chase)
    before, previous = chase.owners, chase.bound
    competitor = chase.competitor(TAIL_ID)
    rows = tuple(classify_new_tail_vector(counts, chase.baseline) for counts in vectors)
    for row in rows:
        if row.local_loss != loss or row.status not in (r12.WITNESS_REALIZED, r12.ELIMINATED):
            raise AssertionError("an unresolved or misplaced tail vector cannot be certified")
        if row.status == r12.WITNESS_REALIZED and (
            row.witness is None or not r8.validate_support_assignment(row.counts, row.witness)
        ):
            raise AssertionError("tail support witness failed independent validation")
        if row.vector_id in chase.classified_terms:
            raise AssertionError("a previously classified vector cannot be reclassified")
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
            "counts_sha256": r20.digest(tuple(row.counts for row in rows)),
            "support_witness_sha256": r20.digest(tuple(row.witness for row in rows)),
            "classified_rows_sha256": r20.digest(rows),
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
            "four_ticket_state_threshold": STATE_THRESHOLD,
            "owner_set_at_dispatch": list(before),
        }
    )
    chase.record_event(f"tail:L{loss}", before, previous)


def run_chase(*, wall_budget: float = PROOF_WALL_BUDGET_SECONDS) -> tuple[Chase, str, float]:
    if not 0 < wall_budget <= PROOF_WALL_BUDGET_SECONDS:
        raise ValueError("proof wall budget must be positive and at most 3600 seconds")
    started = time.monotonic()
    prior_level_fingerprints()
    chase = initial_chase()
    while True:
        stop = chase.stop_condition()
        if stop is not None:
            return chase, stop, time.monotonic() - started
        if time.monotonic() - started >= wall_budget:
            return chase, STOP_WALL, time.monotonic() - started
        identifier = select_owner(chase)
        if identifier == TAIL_ID:
            advance_tail(chase)
        elif identifier.startswith("tail-vector:"):
            refine_classified_owner(chase, identifier)
        else:
            raise AssertionError("state refinement is forbidden in R21")


def build_result(*, wall_budget: float = PROOF_WALL_BUDGET_SECONDS) -> dict[str, Any]:
    chase, stop, wall = run_chase(wall_budget=wall_budget)
    initial = initial_chase()
    refined = {str(row["owner_id"]) for row in chase.classified_records}
    new_ids = {str(row["vector_id"]) for row in chase.tail_vector_records}
    surviving_ids = {
        str(row["vector_id"])
        for row in chase.tail_vector_records
        if row["vector_bound"] is not None
    }
    if (
        chase.states != initial.states
        or chase.state_records
        or any(
            chase.classified_terms[identifier] != bound and identifier not in refined
            for identifier, bound in initial.classified_terms.items()
        )
        or set(chase.classified_terms) != set(initial.classified_terms) | surviving_ids
        or new_ids & set(initial.classified_terms)
        or chase.bound != max(chase.tail_bound, chase.classified_maximum[1], chase.state_max)
    ):
        raise AssertionError("the final maximum or immutable carried-term guard failed")
    classes = owner_classes(chase.owners)
    transitions = [row for row in chase.events if row["from"] != row["to"]]
    success_c = stop == STOP_WALL and chase.bound < START_R3_BOUND
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "SUCCESS_A"
        if stop == STOP_A
        else ("SUCCESS_B" if stop == STOP_B else "SUCCESS_C" if success_c else stop),
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_BRANCH": TASK_BRANCH,
        "STATE_THRESHOLD": STATE_THRESHOLD,
        "START_CLASSIFIED_OWNER_BOUND": START_CLASSIFIED_OWNER_BOUND,
        "START_OWNER_IDS": [START_OWNER_ID],
        "CLASSIFIED_OWNERS_PROCESSED": len(chase.classified_records),
        "CLASSIFIED_OWNER_CERTIFICATES": chase.classified_records,
        "TAIL_LEVELS_PROCESSED": len(chase.tail_records),
        "TAIL_VECTORS_PROCESSED": len(chase.tail_vector_records),
        "TAIL_LEVEL_CERTIFICATES": chase.tail_records,
        "NEW_TAIL_VECTOR_STRUCTURAL_RECORDS": chase.tail_vector_records,
        "UNCLASSIFIED_TAIL_BOUND": chase.tail_bound,
        "NEXT_UNCLASSIFIED_LOSS": chase.next_loss,
        "MAX_CLASSIFIED_TAIL_VECTOR_BOUND": chase.classified_maximum[1],
        "MAX_CLASSIFIED_TAIL_VECTOR_ID": chase.classified_maximum[0],
        "CURRENT_CLASSIFIED_TERMS": [
            {"stable_id": identifier, "bound": bound}
            for identifier, bound in chase.classified_terms.items()
        ],
        "STATE_MAX_BOUND": chase.state_max,
        "STATE_MAX_OWNER_IDS": list(r13.identify_owner_set(chase.states)),
        "CURRENT_STATE_TERMS": [
            {"stable_id": identifier, "bound": bound} for identifier, bound in chase.states
        ],
        "R3_BOUND": chase.bound,
        "R3_DROP": START_R3_BOUND - chase.bound,
        "R3_BOUND_OWNER_CLASS": classes[0] if len(classes) == 1 else "TIED_OWNER_SET",
        "FINAL_OWNER_CLASSES": classes,
        "FINAL_OWNER_IDS": list(chase.owners),
        "R3_STATUS": "CERTIFIED_FROZEN_STATE_OWNER"
        if stop == STOP_A
        else ("CERTIFIED_OWNER_ONLY_RATIONAL_MOMENT_AND_ATTAINED_TAIL_BOUND"),
        "R4_REFERENCE_BOUND": R4_REFERENCE_BOUND,
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": chase.bound - INCUMBENT,
        "OWNER_TRANSITION_COUNT": len(transitions),
        "OWNER_TRANSITION_LIMIT": None,
        "OWNER_TRANSITIONS": transitions,
        "OWNER_ACTION_TRAJECTORY": chase.events,
        "CROSSOVER_DERIVATION": {
            "tail_base_constant": canonical_baseline(),
            "state_threshold": STATE_THRESHOLD,
            "state_crossover_loss": STATE_CROSSOVER_LOSS,
            "start_next_unclassified_loss": START_LOSS,
            "start_unclassified_tail_bound": START_UNCLASSIFIED_TAIL_BOUND,
        },
        "CANONICAL_PRIMITIVES": canonical_primitives(),
        "CANONICAL_PRIMITIVE_STATUS": "PASS",
        "UPSTREAM_FINGERPRINTS_SHA256": verify_upstream_fingerprints(),
        "PRIOR_LEVEL_FINGERPRINTS": prior_level_fingerprints(),
        "STOP_CONDITION": stop,
        "SUCCESS_A": stop == STOP_A,
        "SUCCESS_B": stop == STOP_B,
        "SUCCESS_C": success_c,
        "PROOF_WALL_SECONDS": wall,
        "PROOF_WALL_BUDGET_SECONDS": wall_budget,
        "SOLVER_STATUS": "NOT_DISPATCHED_EXACT_RATIONAL_CERTIFICATES_SUFFICIENT",
        "PRIOR_TAIL_LEVELS_ENUMERATED": 0,
        "PRIOR_VECTORS_RECLASSIFIED": 0,
        "STATE_TERMS_CHANGED": 0,
        "STATE_REFINEMENT_DISPATCHES": 0,
        "NON_OWNER_CLASSIFIED_TERMS_REFINED": 0,
        "BELOW_STATE_REFINEMENT_DISPATCHES": 0,
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
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
