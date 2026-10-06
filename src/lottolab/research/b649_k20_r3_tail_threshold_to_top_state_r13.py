"""Drive the K20 R3 corrected tail from the R12 cursor to the top-state crossover.

R12 classified the 32 lowest attained 18-ticket type-count loss levels above
the R7 cutoff and left its cursor at the next attained level.  This module
resumes at that cursor and walks every attained level in ascending order, with
no level-count cap, until the unclassified-tail floor no longer exceeds the
highest R3 state term or a classified vector becomes the exact R3 owner.  Each
vector is realized by an R8-validated label support and receives R12's R6
pair/triple correction (the frozen R5 forest floor when stronger); a vector
whose corrected bound would still exceed the top state additionally receives
R8's exact four-ticket residual-pair floor.  R12's 235 vectors are
fingerprint-validated, never reclassified.  No portfolio search, outcome
enumeration, or solver is used.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import cache
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from lottolab.research import (
    b649_k20_outside_min_s2_global_penalty_bound_r1 as r1,
)
from lottolab.research import (
    b649_k20_r3_anchor_incidence_bound_r5 as r5,
)
from lottolab.research import (
    b649_k20_r3_corrected_tail_min_loss_plateau_r12 as r12,
)
from lottolab.research import (
    b649_k20_r3_exact_anchor_neighborhood_envelope_r6 as r6,
)
from lottolab.research import (
    b649_k20_r3_frontier_realizability_bound_r8 as r8,
)
from lottolab.research import (
    b649_k20_r3_joint_residual_envelope_r7 as r7,
)

TASK_ID = "B649_K20_R3_TAIL_THRESHOLD_TO_TOP_STATE_R13"
BASE_HEAD = "f66424c8fc762d7ebe7128fbb3eb95481e153374"
BASE_TREE = "cf32c22fdc1e71dd9e35ec0d3f3c6e02809456fd"
TASK_BRANCH = "codex/b649-k20-r3-tail-threshold-to-top-state-r13"
PRIOR_R3_BOUND = 358_337_063
PRIOR_BOUND_OWNER = "corrected-tail"
START_UNCLASSIFIED_LOSS = 6_711_565
R12_FIRST_ATTAINED_LOSS = 6_696_172
R12_LEVEL_COUNT = 32
R12_VECTOR_COUNT = 235
TOP_STATE_BOUND = 356_799_210
R4_REFERENCE_BOUND = 350_545_749
FIXED_CERTIFIED_LOSS = 7_180_012
CROSSOVER_LOSS_THRESHOLD = 8_249_418
PROOF_WALL_BUDGET_SECONDS = 3_600.0
INITIAL_CENSUS_WINDOW = 4_096
TRAJECTORY_CHECKPOINT_STRIDE = 512
UNCLASSIFIED_TAIL_TERM = "unclassified-tail"
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_PATH = (
    REPO_ROOT / "docs/research/matrix-native-results/"
    "b649-k20-r3-tail-threshold-to-top-state-r13-result.json"
)
R12_RESULT_PATH = r12.RESULT_PATH

# R12 is the current R3 authority; it pins the R10/R11 inputs it reuses.
UPSTREAM_SHA256 = {
    "src/lottolab/research/b649_k20_r3_corrected_tail_min_loss_plateau_r12.py": (
        "4501b7a496d32a87bdbfa2d4e0951bca330a60feb8b799350cc0a76607008c92"
    ),
    (
        "docs/research/matrix-native-results/"
        "b649-k20-r3-corrected-tail-min-loss-plateau-r12-result.json"
    ): "fc9c31ecb106efef7867e93815772261e2d9eafc8031c62de477ee32979d3823",
}

FOUR_TICKET_NOT_REQUIRED = "NOT_REQUIRED_R6_BOUND_AT_OR_BELOW_TOP_STATE"
FOUR_TICKET_APPLIED = "APPLIED"
FOUR_TICKET_NOT_APPLICABLE = "NOT_APPLICABLE_TYPE_PAIR_WITHOUT_OUTSIDE_OVERLAP"

STOP_A = "A_R3_AT_OR_BELOW_R4_REFERENCE"
STOP_B = "B_R3_AT_OR_BELOW_TOP_STATE"
STOP_C = "C_CLASSIFIED_VECTOR_OWNER_IDENTIFIED"
STOP_D = "D_PROOF_WALL_BUDGET_EXHAUSTED"
CENSUS_LIMIT_REACHED = "CENSUS_LIMIT_REACHED"

TypeCountVector = tuple[int, ...]
SupportWitness = tuple[tuple[int, ...], ...]
LevelRows = tuple[tuple[int, tuple[TypeCountVector, ...]], ...]


@dataclass(frozen=True)
class TailCensus:
    """Exact attained tail levels above the R7 cutoff, split at the R12 cursor."""

    cutoff: int
    enumeration_loss_limit: int
    enumerated_vector_count: int
    vectors_at_or_below_cutoff: int
    prior_levels: LevelRows
    levels: LevelRows


@dataclass(frozen=True)
class ClassifiedVector:
    """One tail vector's realizability status and its certified bound."""

    vector_id: str
    counts: TypeCountVector
    local_loss: int
    status: str
    pair_union_penalty: int | None
    forest_floor: int | None
    r6_correction: int | None
    four_ticket_status: str | None
    four_ticket_penalty: int | None
    correction: int | None
    vector_bound: int | None
    witness: SupportWitness | None


@dataclass(frozen=True)
class LevelStep:
    """The four authoritative R3 quantities after one completed attained level."""

    ordinal: int
    local_loss: int
    vector_count: int
    next_unclassified_loss: int
    unclassified_tail_bound: int
    max_classified_vector_bound: int
    max_classified_vector_id: str
    r3_bound: int
    owner_set: tuple[str, ...]


@dataclass(frozen=True)
class ThresholdWalk:
    """Ascending level walk with its first stop condition."""

    steps: tuple[LevelStep, ...]
    rows: tuple[ClassifiedVector, ...]
    stop_condition: str
    stop_flags: dict[str, bool]


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _digest(payload: object) -> str:
    return sha256(repr(payload).encode("ascii")).hexdigest()


def _sparse(counts: TypeCountVector) -> list[list[int]]:
    return [[index, count] for index, count in enumerate(counts) if count]


def vector_id(counts: TypeCountVector, loss: int) -> str:
    """Return a stable identifier for one type-count vector."""

    support = ",".join(f"{index}x{count}" for index, count in enumerate(counts) if count)
    return f"tail-vector:L{loss}:{support}"


def verify_upstream_fingerprints() -> dict[str, str]:
    """Fail closed if the R12 authority or any R10/R11 input it pins drifted."""

    r12.verify_upstream_fingerprints()
    observed = {relative: _sha256(REPO_ROOT / relative) for relative in UPSTREAM_SHA256}
    if observed != UPSTREAM_SHA256:
        raise AssertionError(f"R12 authority fingerprint mismatch: {observed}")
    return observed


def canonical_primitives() -> dict[str, int]:
    """Recheck the official-any-prize primitives through the R12 authority."""

    primitives = r12.canonical_primitives()
    if (
        primitives["SINGLE_TICKET_ANY_PRIZE"] != 18_611_432
        or primitives["PAIR_DIAGONAL_I6"] != 18_611_432
        or primitives["K20_S1"] != 372_228_640
    ):
        raise AssertionError(f"canonical primitive preflight failed: {primitives}")
    return primitives


def crossover_loss_threshold() -> int:
    """Return the first local loss whose pure tail floor is at most the top state."""

    primitives = canonical_primitives()
    baseline = r12.canonical_uncorrected_baseline()
    threshold = primitives["K20_S1"] - FIXED_CERTIFIED_LOSS - TOP_STATE_BOUND
    if (
        baseline != primitives["K20_S1"] - FIXED_CERTIFIED_LOSS
        or threshold != CROSSOVER_LOSS_THRESHOLD
        or baseline - threshold != TOP_STATE_BOUND
        or baseline - (threshold - 1) <= TOP_STATE_BOUND
    ):
        raise AssertionError("the exact crossover arithmetic failed")
    return threshold


@cache
def prior_authority() -> dict[str, Any]:
    """Load the fingerprinted R12 certificate and require the task's authority."""

    verify_upstream_fingerprints()
    stored = cast(dict[str, Any], json.loads(R12_RESULT_PATH.read_text(encoding="utf-8")))
    effective = cast(dict[str, Any], stored["EFFECTIVE_TAIL_CERTIFICATE"])
    level_rows = cast(list[dict[str, Any]], stored["LOSS_LEVEL_ROWS"])
    if (
        stored["TASK_ID"] != r12.TASK_ID
        or stored["R3_BOUND"] != PRIOR_R3_BOUND
        or stored["CURRENT_BOUND_OWNER_SET"] != [PRIOR_BOUND_OWNER]
        or stored["TOP_STATE_BOUND"] != TOP_STATE_BOUND
        or effective["TYPE_COUNT_LOSS"] != START_UNCLASSIFIED_LOSS
        or effective["FIXED_CERTIFIED_LOSS"] != FIXED_CERTIFIED_LOSS
        or stored["LOSS_LEVELS_PROCESSED"] != R12_LEVEL_COUNT
        or len(level_rows) != R12_LEVEL_COUNT
        or level_rows[-1]["next_unprocessed_loss"] != START_UNCLASSIFIED_LOSS
        or stored["MIN_REALIZABLE_TAIL_LOSS"] != R12_FIRST_ATTAINED_LOSS
        or stored["TAIL_VECTOR_COUNT"] != R12_VECTOR_COUNT
        or stored["REALIZABLE_VECTOR_COUNT"] != R12_VECTOR_COUNT
        or stored["UNREALIZABLE_VECTOR_COUNT"] != 0
        or stored["UNRESOLVED_VECTOR_COUNT"] != 0
    ):
        raise AssertionError("the R12 certificate differs from the task's R3 authority")
    return stored


def state_terms() -> tuple[tuple[str, int], ...]:
    """Return R12's 23 state terms, cross-checked against the R11 rebuild."""

    terms = cast(list[dict[str, Any]], prior_authority()["TOP_LEVEL_R3_TERMS"])
    if terms[0] != {"stable_id": PRIOR_BOUND_OWNER, "bound": PRIOR_R3_BOUND}:
        raise AssertionError("R12's corrected tail must be its first and owning term")
    stored = tuple((str(term["stable_id"]), int(term["bound"])) for term in terms[1:])
    if stored != r12.non_owner_state_terms():
        raise AssertionError("R12's stored state terms differ from the R11 rebuild")
    if max(bound for _, bound in stored) != TOP_STATE_BOUND:
        raise AssertionError("the highest R3 state term changed")
    return stored


def r12_carried_maximum() -> tuple[str, int]:
    """Return R12's worst classified vector from its certificate, not a rerun."""

    worst = cast(
        dict[str, Any],
        prior_authority()["MANDATORY_HIGHER_ORDER_CORRECTION"]["WORST_PROCESSED_VECTOR"],
    )
    counts = [0] * len(r5.anchor_incidence_profiles())
    for index, count in cast(list[list[int]], worst["TYPE_COUNTS"]):
        counts[index] = count
    vector = tuple(counts)
    loss = r12.local_loss(vector, r6.local_losses(r5.anchor_incidence_profiles()))
    bound = int(worst["VECTOR_BOUND"])
    if (
        loss != worst["LOCAL_LOSS"]
        or not R12_FIRST_ATTAINED_LOSS <= loss < START_UNCLASSIFIED_LOSS
        or r12.canonical_uncorrected_baseline() - loss - int(worst["CORRECTION"]) != bound
    ):
        raise AssertionError("R12's stored worst vector is internally inconsistent")
    return vector_id(vector, loss), bound


@cache
def tail_census(loss_limit: int) -> TailCensus:
    """Enumerate every tail vector through ``loss_limit`` and pin the R12 prefix."""

    if loss_limit < START_UNCLASSIFIED_LOSS:
        raise ValueError("the census must reach the R12 cursor")
    losses = r6.local_losses(r5.anchor_incidence_profiles())
    cutoff = r7.JOINT_LOCAL_LOSS_CUTOFF
    at_or_below = 0
    enumerated = 0
    by_loss: dict[int, list[TypeCountVector]] = {}
    for vector in r6.iter_type_count_vectors(losses, r12.OUTSIDE_TICKET_COUNT, loss_limit):
        enumerated += 1
        loss = r12.local_loss(vector, losses)
        if loss > loss_limit:
            raise AssertionError("the exact type-count census emitted an invalid vector")
        if loss <= cutoff:
            at_or_below += 1
        else:
            by_loss.setdefault(loss, []).append(vector)
    if at_or_below != r12.R7_CENSUS_VECTOR_COUNT:
        raise AssertionError("the at-or-below-cutoff census differs from R7")

    ordered = tuple((loss, tuple(sorted(by_loss[loss]))) for loss in sorted(by_loss))
    prior = tuple(level for level in ordered if level[0] < START_UNCLASSIFIED_LOSS)
    remaining = tuple(level for level in ordered if level[0] >= START_UNCLASSIFIED_LOSS)
    stored_rows = cast(list[dict[str, Any]], prior_authority()["LOSS_LEVEL_ROWS"])
    if [(loss, len(vectors)) for loss, vectors in prior] != [
        (int(row["local_loss"]), int(row["vector_count"])) for row in stored_rows
    ]:
        raise AssertionError("the census below the cursor differs from R12's certified levels")
    if sum(len(vectors) for _, vectors in prior) != R12_VECTOR_COUNT:
        raise AssertionError("the census below the cursor differs from R12's vector count")
    if remaining and remaining[0][0] != START_UNCLASSIFIED_LOSS:
        raise AssertionError("R12's cursor is not the first attained level above its levels")
    return TailCensus(
        cutoff=cutoff,
        enumeration_loss_limit=loss_limit,
        enumerated_vector_count=enumerated,
        vectors_at_or_below_cutoff=at_or_below,
        prior_levels=prior,
        levels=remaining,
    )


def four_ticket_penalty(counts: TypeCountVector) -> int | None:
    """Return R8's exact four-ticket residual-pair penalty, or None if inapplicable.

    R8's outside-label dual needs every represented type pair to admit an
    outside-cell overlap.  A pair without one (any pair involving the
    zero-outside type) makes the R8 floor unavailable; the caller then keeps
    the already-valid R6/R5 correction rather than inventing a substitute.
    """

    present = [index for index, count in enumerate(counts) if count]
    for position, left in enumerate(present):
        for right in present[position:]:
            if left == right and counts[left] < 2:
                continue
            if not any(overlap[3] > 0 for overlap in r6.feasible_pair_overlap_vectors(left, right)):
                return None
    floor = r8.state_moment_floor(counts).residual_s2_lower_bound
    divisor = r6.PAIR_MULTIPLICITY_DIVISOR
    return (floor + divisor - 1) // divisor


@cache
def classify_vector(
    counts: TypeCountVector,
    baseline: int,
    load_bearing_threshold: int = TOP_STATE_BOUND,
) -> ClassifiedVector:
    """Classify one post-cursor vector; add R8's floor only when still load-bearing."""

    losses = r6.local_losses(r5.anchor_incidence_profiles())
    loss = r12.local_loss(counts, losses)
    if loss < START_UNCLASSIFIED_LOSS:
        raise AssertionError("R12 already certified this vector; R13 must not reclassify it")
    base = r12.classify_vector(counts, baseline)
    identifier = vector_id(counts, loss)
    if base.vector_bound is None or base.correction is None:
        return ClassifiedVector(
            identifier, counts, loss, base.status, None, None, None, None, None, None, None, None
        )

    status = FOUR_TICKET_NOT_REQUIRED
    four: int | None = None
    correction = base.correction
    if base.vector_bound > load_bearing_threshold:
        four = four_ticket_penalty(counts)
        if four is None:
            status = FOUR_TICKET_NOT_APPLICABLE
        else:
            status = FOUR_TICKET_APPLIED
            correction = max(correction, four)
    return ClassifiedVector(
        vector_id=identifier,
        counts=counts,
        local_loss=loss,
        status=base.status,
        pair_union_penalty=base.pair_union_penalty,
        forest_floor=base.forest_floor,
        r6_correction=base.correction,
        four_ticket_status=status,
        four_ticket_penalty=four,
        correction=correction,
        vector_bound=baseline - loss - correction,
        witness=base.witness,
    )


def identify_owner_set(terms: Sequence[tuple[str, int]]) -> tuple[str, ...]:
    """Return every term tied at the maximum, preserving input order."""

    return r12.identify_owner_set(terms)


def walk_attained_levels(
    levels: Sequence[tuple[int, Sequence[TypeCountVector]]],
    classify: Callable[[TypeCountVector], ClassifiedVector],
    *,
    baseline: int,
    states: Sequence[tuple[str, int]],
    carried_maximum: tuple[str, int],
    r4_reference: int = R4_REFERENCE_BOUND,
    started: float | None = None,
    wall_budget_seconds: float = PROOF_WALL_BUDGET_SECONDS,
) -> ThresholdWalk:
    """Classify ascending attained levels and recompute R3 after each one.

    A level is processed only when the following attained level is known, so
    the unclassified-tail floor is always exact.  Every later vector has loss
    at least that next level, hence bound at most ``baseline - next``.
    """

    clock = time.monotonic() if started is None else started
    top_state = max(bound for _, bound in states)
    owner_id, owner_bound = carried_maximum
    steps: list[LevelStep] = []
    rows: list[ClassifiedVector] = []
    flags = {STOP_A: False, STOP_B: False, STOP_C: False, STOP_D: False}
    stop_condition = CENSUS_LIMIT_REACHED
    for index in range(len(levels) - 1):
        loss, vectors = levels[index]
        next_loss = levels[index + 1][0]
        if next_loss <= loss or (index and loss <= levels[index - 1][0]):
            raise AssertionError("attained loss levels must be strictly ascending")
        if time.monotonic() - clock >= wall_budget_seconds:
            flags[STOP_D] = True
            stop_condition = STOP_D
            break
        level_rows = tuple(classify(vector) for vector in vectors)
        for row in level_rows:
            if row.local_loss != loss:
                raise AssertionError("a classified vector is not on its attained level")
            if row.vector_bound is None:
                continue
            if row.vector_bound > baseline - loss:
                raise AssertionError("a vector correction cannot be negative")
            if row.vector_bound > owner_bound:
                owner_id, owner_bound = row.vector_id, row.vector_bound
        rows.extend(level_rows)

        floor = baseline - next_loss
        terms = ((UNCLASSIFIED_TAIL_TERM, floor), (owner_id, owner_bound), *states)
        r3_bound = max(bound for _, bound in terms)
        if steps and r3_bound > steps[-1].r3_bound:
            raise AssertionError("the R3 bound must not increase as levels are classified")
        steps.append(
            LevelStep(
                ordinal=index + 1,
                local_loss=loss,
                vector_count=len(level_rows),
                next_unclassified_loss=next_loss,
                unclassified_tail_bound=floor,
                max_classified_vector_bound=owner_bound,
                max_classified_vector_id=owner_id,
                r3_bound=r3_bound,
                owner_set=identify_owner_set(terms),
            )
        )
        flags[STOP_A] = r3_bound <= r4_reference
        flags[STOP_B] = r3_bound <= top_state
        # Once the floor cannot exceed a classified owner above every state,
        # later levels are irrelevant: none of their vectors can exceed it.
        flags[STOP_C] = owner_bound > top_state and floor <= owner_bound
        flags[STOP_D] = time.monotonic() - clock >= wall_budget_seconds
        triggered = [name for name, value in flags.items() if value]
        if triggered:
            stop_condition = triggered[0]
            break
    return ThresholdWalk(tuple(steps), tuple(rows), stop_condition, dict(flags))


@cache
def classify_to_crossover() -> tuple[TailCensus, ThresholdWalk, float]:
    """Walk from the R12 cursor, widening the exact census until a stop fires."""

    started = time.monotonic()
    baseline = r12.canonical_uncorrected_baseline()
    states = state_terms()
    carried = r12_carried_maximum()
    window = INITIAL_CENSUS_WINDOW
    while True:
        census = tail_census(crossover_loss_threshold() + window)
        walk = walk_attained_levels(
            census.levels,
            lambda vector: classify_vector(vector, baseline),
            baseline=baseline,
            states=states,
            carried_maximum=carried,
            started=started,
        )
        if walk.stop_condition != CENSUS_LIMIT_REACHED:
            break
        window *= 2
    if not walk.steps:
        raise AssertionError("no attained level was classified before the stop condition")
    return census, walk, time.monotonic() - started


def _trajectory_row(step: LevelStep) -> dict[str, Any]:
    return {
        "ordinal": step.ordinal,
        "local_loss": step.local_loss,
        "vector_count": step.vector_count,
        "next_unclassified_loss": step.next_unclassified_loss,
        "unclassified_tail_bound": step.unclassified_tail_bound,
        "max_classified_vector_bound": step.max_classified_vector_bound,
        "max_classified_vector_id": step.max_classified_vector_id,
        "r3_bound": step.r3_bound,
        "owner_set": list(step.owner_set),
    }


def _owner_transitions(steps: Sequence[LevelStep]) -> list[dict[str, Any]]:
    transitions: list[dict[str, Any]] = []
    previous: tuple[str, ...] = (PRIOR_BOUND_OWNER,)
    for step in steps:
        if step.owner_set != previous:
            transitions.append(
                {
                    "ordinal": step.ordinal,
                    "next_unclassified_loss": step.next_unclassified_loss,
                    "from": list(previous),
                    "to": list(step.owner_set),
                    "r3_bound": step.r3_bound,
                }
            )
            previous = step.owner_set
    return transitions


def build_result() -> dict[str, Any]:
    """Build the compact threshold certificate and the recomputed R3 maximum."""

    primitives = canonical_primitives()
    fingerprints = verify_upstream_fingerprints()
    prior = prior_authority()
    baseline = r12.canonical_uncorrected_baseline()
    crossover = crossover_loss_threshold()
    states = state_terms()
    carried_id, carried_bound = r12_carried_maximum()
    census, walk, wall_seconds = classify_to_crossover()
    rows = walk.rows
    steps = walk.steps
    final = steps[-1]

    eliminated = sum(row.status == r12.ELIMINATED for row in rows)
    realized = sum(row.status == r12.WITNESS_REALIZED for row in rows)
    unwitnessed = sum(row.status == r12.UNWITNESSED for row in rows)
    if eliminated + realized + unwitnessed != len(rows):
        raise AssertionError("a tail vector has no classification")
    if any(row.local_loss < START_UNCLASSIFIED_LOSS for row in rows):
        raise AssertionError("an R12-certified vector was reclassified")
    surviving = tuple(row for row in rows if row.vector_bound is not None)
    new_worst = max(surviving, key=lambda row: (cast(int, row.vector_bound), row.counts))
    four_applied = sum(row.four_ticket_status == FOUR_TICKET_APPLIED for row in surviving)
    four_unavailable = sum(
        row.four_ticket_status == FOUR_TICKET_NOT_APPLICABLE for row in surviving
    )
    forest_binding = sum(
        cast(int, row.forest_floor) > cast(int, row.pair_union_penalty) for row in surviving
    )
    corrections = [cast(int, row.correction) for row in surviving]

    terms = (
        (UNCLASSIFIED_TAIL_TERM, final.unclassified_tail_bound),
        (final.max_classified_vector_id, final.max_classified_vector_bound),
        *states,
    )
    owners = identify_owner_set(terms)
    r3_bound = max(bound for _, bound in terms)
    if r3_bound != final.r3_bound or owners != final.owner_set or r3_bound > PRIOR_R3_BOUND:
        raise AssertionError("the final R3 maximum disagrees with the level walk")
    expected_maximum = max(
        (carried_bound, carried_id),
        (cast(int, new_worst.vector_bound), new_worst.vector_id),
    )
    if final.max_classified_vector_bound != expected_maximum[0]:
        raise AssertionError("the classified-vector maximum disagrees with the rows")

    through_crossover = final.next_unclassified_loss >= crossover
    if r3_bound <= R4_REFERENCE_BOUND:
        r3_status = "CERTIFIED_AT_OR_BELOW_R4_REFERENCE"
    elif r3_bound <= TOP_STATE_BOUND:
        r3_status = "CERTIFIED_CORRECTED_TAIL_NO_LONGER_EXCEEDS_TOP_STATE"
    elif final.max_classified_vector_id in owners:
        r3_status = "CERTIFIED_CLASSIFIED_VECTOR_OWNS_R3"
    else:
        r3_status = "CERTIFIED_PARTIAL_TAIL_TIGHTENING"
    task_status = {
        STOP_A: "SUCCESS_A_R3_AT_OR_BELOW_R4_REFERENCE",
        STOP_B: "SUCCESS_B_R3_AT_OR_BELOW_TOP_STATE",
        STOP_C: "SUCCESS_C_EXACT_CLASSIFIED_OWNER_IDENTIFIED",
        STOP_D: "STOP_D_PROOF_WALL_BUDGET_EXHAUSTED",
    }[walk.stop_condition]
    checkpoints = [
        _trajectory_row(step)
        for step in steps
        if step.ordinal == 1 or step.ordinal % TRAJECTORY_CHECKPOINT_STRIDE == 0 or step is final
    ]
    prior_rows = cast(list[dict[str, Any]], prior["LOSS_LEVEL_ROWS"])
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": task_status,
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_BRANCH": TASK_BRANCH,
        "CANONICAL_PRIMITIVES": {
            "SINGLE_TICKET_ANY_PRIZE": primitives["SINGLE_TICKET_ANY_PRIZE"],
            "PAIR_INTERSECTION_COST[6]": primitives["PAIR_DIAGONAL_I6"],
            "K20_S1": primitives["K20_S1"],
        },
        "CANONICAL_PRIMITIVE_STATUS": "PASS",
        "UPSTREAM_FINGERPRINTS_SHA256": fingerprints,
        "PRIOR_R3_BOUND": PRIOR_R3_BOUND,
        "PRIOR_BOUND_OWNER_SET": prior["CURRENT_BOUND_OWNER_SET"],
        "CROSSOVER": {
            "CANONICAL_K20_S1": primitives["K20_S1"],
            "FIXED_CERTIFIED_LOSS": FIXED_CERTIFIED_LOSS,
            "CANONICAL_UNCORRECTED_BASELINE": baseline,
            "TOP_STATE_BOUND": TOP_STATE_BOUND,
            "CROSSOVER_LOSS_THRESHOLD": crossover,
            "FORMULA": "K20_S1 - fixed certified loss - TOP_STATE_BOUND",
            "TAIL_FLOOR_AT_THRESHOLD": baseline - crossover,
            "LAST_CLASSIFIED_LEVEL_LOSS": final.local_loss,
            "FIRST_UNCLASSIFIED_LEVEL_LOSS": final.next_unclassified_loss,
            "CERTIFIED_EMPTY_LOSS_INTERVAL": [
                final.local_loss + 1,
                final.next_unclassified_loss - 1,
            ],
            "CLASSIFICATION_THROUGH_CROSSOVER_COMPLETE": through_crossover,
        },
        "NO_RERUN_GUARD": {
            "R12_LEVELS_FINGERPRINT_VALIDATED": len(census.prior_levels),
            "R12_VECTORS_FINGERPRINT_VALIDATED": sum(
                len(vectors) for _, vectors in census.prior_levels
            ),
            "R12_LEVEL_SEQUENCE_SHA256": _digest(
                tuple((loss, len(vectors)) for loss, vectors in census.prior_levels)
            ),
            "R12_LEVEL_SEQUENCE_MATCHES_CERTIFICATE": [
                [loss, len(vectors)] for loss, vectors in census.prior_levels
            ]
            == [[row["local_loss"], row["vector_count"]] for row in prior_rows],
            "R12_VECTORS_RECLASSIFIED": 0,
            "R12_MAXIMUM_CARRIED_FROM_CERTIFICATE": {
                "VECTOR_ID": carried_id,
                "VECTOR_BOUND": carried_bound,
            },
            "GUARD": "classify_vector refuses any vector below START_UNCLASSIFIED_LOSS",
        },
        "START_UNCLASSIFIED_LOSS": START_UNCLASSIFIED_LOSS,
        "CROSSOVER_LOSS_THRESHOLD": crossover,
        "LEVEL_CENSUS": {
            "LOCAL_LOSS_CUTOFF": census.cutoff,
            "VECTORS_AT_OR_BELOW_CUTOFF": census.vectors_at_or_below_cutoff,
            "ENUMERATION_LOSS_LIMIT": census.enumeration_loss_limit,
            "ENUMERATED_VECTOR_COUNT": census.enumerated_vector_count,
            "ATTAINED_LEVELS_AT_OR_ABOVE_CURSOR": len(census.levels),
            "LEVEL_COUNT_CAP": "NONE",
            "LEVEL_DEFINITION": (
                "A loss level is a local-loss value attained by at least one 18-ticket "
                "type-count vector; every integer strictly between consecutive levels is "
                "certified empty by the same exact enumeration."
            ),
        },
        "NEW_LOSS_LEVEL_COUNT": len(steps),
        "NEW_VECTOR_COUNT": len(rows),
        "NEW_REALIZABLE_VECTOR_COUNT": realized,
        "NEW_UNREALIZABLE_VECTOR_COUNT": eliminated,
        "NEW_UNRESOLVED_VECTOR_COUNT": unwitnessed,
        "TOTAL_CLASSIFIED_VECTOR_COUNT": int(prior["TAIL_VECTOR_COUNT"]) + len(rows),
        "REALIZABLE_VECTOR_COUNT": int(prior["REALIZABLE_VECTOR_COUNT"]) + realized,
        "UNREALIZABLE_VECTOR_COUNT": int(prior["UNREALIZABLE_VECTOR_COUNT"]) + eliminated,
        "UNRESOLVED_VECTOR_COUNT": int(prior["UNRESOLVED_VECTOR_COUNT"]) + unwitnessed,
        "SUPPORT_WITNESS_SHA256": _digest(
            tuple((row.counts, row.witness) for row in rows if row.witness is not None)
        ),
        "SUPPORT_WITNESS_VALIDATOR": "R8 validate_support_assignment (solver-independent)",
        "CLASSIFIED_ROWS_SHA256": _digest(
            tuple(
                (
                    row.counts,
                    row.status,
                    row.pair_union_penalty,
                    row.forest_floor,
                    row.four_ticket_status,
                    row.four_ticket_penalty,
                    row.correction,
                    row.vector_bound,
                )
                for row in rows
            )
        ),
        "CLASSIFIED_VECTOR_CORRECTIONS": {
            "R6_SOURCE": (
                "R6 type_count_envelope: max(ceil(residual pair/anchor-triple intersection "
                "mass floor / 9), frozen R5 weighted-forest floor)"
            ),
            "MINIMUM": min(corrections),
            "MAXIMUM": max(corrections),
            "R5_FOREST_FLOOR_BINDING_COUNT": forest_binding,
            "FOUR_TICKET_TRIGGER": "R6-corrected vector bound > TOP_STATE_BOUND",
            "FOUR_TICKET_SOURCE": "R8 state_moment_floor: ceil(residual S2 floor / 9)",
            "FOUR_TICKET_APPLIED_COUNT": four_applied,
            "FOUR_TICKET_NOT_APPLICABLE_COUNT": four_unavailable,
            "NEW_WORST_VECTOR": {
                "VECTOR_ID": new_worst.vector_id,
                "TYPE_COUNTS": _sparse(new_worst.counts),
                "LOCAL_LOSS": new_worst.local_loss,
                "CORRECTION": new_worst.correction,
                "FOUR_TICKET_STATUS": new_worst.four_ticket_status,
                "VECTOR_BOUND": new_worst.vector_bound,
                "SLACK_BELOW_TOP_STATE": TOP_STATE_BOUND - cast(int, new_worst.vector_bound),
            },
        },
        "NEXT_UNCLASSIFIED_LOSS": final.next_unclassified_loss,
        "UNCLASSIFIED_TAIL_BOUND": final.unclassified_tail_bound,
        "MAX_CLASSIFIED_VECTOR_BOUND": final.max_classified_vector_bound,
        "MAX_CLASSIFIED_VECTOR_ID": final.max_classified_vector_id,
        "TOP_STATE_BOUND": TOP_STATE_BOUND,
        "TOP_LEVEL_R3_TERMS": [{"stable_id": term_id, "bound": bound} for term_id, bound in terms],
        "R3_FORMULA": (
            "max(UNCLASSIFIED_TAIL_BOUND, MAX_CLASSIFIED_VECTOR_BOUND, TOP_STATE_BOUND, "
            "remaining 22 state terms)"
        ),
        "R3_BOUND": r3_bound,
        "R3_BOUND_OWNER": owners[0] if len(owners) == 1 else list(owners),
        "CURRENT_BOUND_OWNER_SET": list(owners),
        "R3_STATUS": r3_status,
        "R3_TIGHTENING": PRIOR_R3_BOUND - r3_bound,
        "OWNER_TRANSITIONS": _owner_transitions(steps),
        "TRAJECTORY_CHECKPOINTS": checkpoints,
        "TRAJECTORY_SHA256": _digest(steps),
        "STOP_CONDITION": walk.stop_condition,
        "STOP_FLAGS": walk.stop_flags,
        "SUCCESS_A": r3_bound <= R4_REFERENCE_BOUND,
        "SUCCESS_B": r3_bound <= TOP_STATE_BOUND,
        "SUCCESS_C": through_crossover or walk.stop_condition == STOP_C,
        "R4_REFERENCE_BOUND": R4_REFERENCE_BOUND,
        "INCUMBENT": r1.INCUMBENT,
        "REMAINING_GAP": r3_bound - r1.INCUMBENT,
        "PROOF_WALL_SECONDS": round(wall_seconds, 6),
        "PROOF_WALL_BUDGET_SECONDS": PROOF_WALL_BUDGET_SECONDS,
        "SOLVER_STATUS": "NOT_USED_EXACT_TYPE_COUNT_CENSUS_AND_CONSTRUCTIVE_WITNESSES",
        "OUTCOME_SPACE_ENUMERATED": "NO",
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


def write_result() -> dict[str, Any]:
    """Write the compact JSON certificate inside the repository."""

    result = build_result()
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(f"{json.dumps(result, indent=2)}\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(write_result(), indent=2))
