"""Classify the K20 R3 corrected-tail plateaus above the R7 local-loss cutoff.

R11 proved that no 18-ticket type-count vector has local loss cutoff+1 or
cutoff+2.  This module walks the exact attained loss levels above the cutoff in
ascending order.  Each vector is eliminated by the established aggregate
realizability relaxation or realized by an independently validated label
support; every surviving vector then receives the established R6 pair/triple
residual-union correction.  The 23 non-owner R3 state terms are reused
unchanged.  No portfolio search, outcome enumeration, or solver is used.
"""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
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
    b649_k20_r3_bound_owner_reduction_r11 as r11,
)
from lottolab.research import (
    b649_k20_r3_canonical_primitive_authority_repair_r10 as r10,
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

TASK_ID = "B649_K20_R3_CORRECTED_TAIL_MIN_LOSS_PLATEAU_R12"
BASE_HEAD = "35ddfb6065121a1bf0657bed6768da0c41e11973"
BASE_TREE = "e8576f102eaae7e7407566d7d6e84693e044fea5"
TASK_BRANCH = "codex/b649-k20-r3-corrected-tail-min-loss-plateau-r12"
PRIOR_R3_BOUND = 358_352_827
PRIOR_MINIMUM_OMITTED_LOSS = 6_695_801
TOP_NON_TAIL_STATE_BOUND = 356_799_210
R4_REFERENCE_BOUND = 350_545_749
R7_CENSUS_VECTOR_COUNT = 10_816
LOSS_LEVEL_BUDGET = 32
TIGHTENING_STOP = 50_000
PROOF_WALL_BUDGET_SECONDS = 3_600.0
INITIAL_CENSUS_WINDOW = 4_096
MAXIMUM_PAIR_OVERLAP = 3
WITNESS_RESTARTS = 64
WITNESS_TICKET_TRIES = 256
OUTSIDE_TICKET_COUNT = r1.TICKET_COUNT - 2
# Physical label ranges used by R8's independent support validator.
SUPPORT_CELL_LABELS = (
    tuple(range(0, 3)),
    tuple(range(3, 6)),
    tuple(range(6, 9)),
    tuple(range(9, r1.POOL_SIZE)),
)
REPO_ROOT = Path(__file__).resolve().parents[3]
RESULT_PATH = (
    REPO_ROOT / "docs/research/matrix-native-results/"
    "b649-k20-r3-corrected-tail-min-loss-plateau-r12-result.json"
)
R11_RESULT_PATH = r11.RESULT_PATH

# R11 is the current R3 authority; R10 pins everything R11 reuses.
UPSTREAM_SHA256 = {
    "src/lottolab/research/b649_k20_r3_bound_owner_reduction_r11.py": (
        "9a344dc2d6c03fb45e9cb105661dbda58c55eea9db6c93eed12ff998e5f403fc"
    ),
    "docs/research/matrix-native-results/b649-k20-r3-bound-owner-reduction-r11-result.json": (
        "2684443adc1a7165738df321eb2d4d0b03e2939e7a73cdc6897dda171de54e18"
    ),
}

ELIMINATED = "ELIMINATED_AGGREGATE_INFEASIBLE"
WITNESS_REALIZED = "WITNESS_REALIZED"
UNWITNESSED = "NOT_ELIMINATED_UNWITNESSED"

TypeCountVector = tuple[int, ...]
SupportWitness = tuple[tuple[int, ...], ...]

_MASK64 = (1 << 64) - 1


@dataclass(frozen=True)
class TailLevelCensus:
    """Exact attained local-loss levels above the R7 cutoff."""

    cutoff: int
    vectors_at_or_below_cutoff: int
    enumeration_loss_limit: int
    enumerated_vector_count: int
    levels: tuple[tuple[int, tuple[TypeCountVector, ...]], ...]


@dataclass(frozen=True)
class VectorClassification:
    """One tail vector's realizability status and mandatory correction."""

    counts: TypeCountVector
    local_loss: int
    status: str
    pair_union_penalty: int | None
    forest_floor: int | None
    correction: int | None
    vector_bound: int | None
    witness: SupportWitness | None


@dataclass(frozen=True)
class LevelClassification:
    """A fully classified attained loss level and the tail after it."""

    ordinal: int
    local_loss: int
    vectors: tuple[VectorClassification, ...]
    next_unprocessed_loss: int
    effective_tail_bound: int
    r3_bound: int


@dataclass(frozen=True)
class TailPlateauCertificate:
    """Ascending plateau classification with its stop reason."""

    census: TailLevelCensus
    levels: tuple[LevelClassification, ...]
    stop_condition: str
    stop_flags: dict[str, bool]
    effective_tail_bound: int
    r3_bound: int
    wall_seconds: float


class _SplitMix64:
    """Version-stable deterministic generator for witness construction."""

    def __init__(self, seed: int) -> None:
        self._state = seed & _MASK64

    def next(self) -> int:
        self._state = (self._state + 0x9E3779B97F4A7C15) & _MASK64
        value = self._state
        value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & _MASK64
        value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & _MASK64
        return value ^ (value >> 31)

    def shuffled(self, values: Sequence[int]) -> list[int]:
        items = list(values)
        for index in range(len(items) - 1, 0, -1):
            swap = self.next() % (index + 1)
            items[index], items[swap] = items[swap], items[index]
        return items


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def verify_upstream_fingerprints() -> dict[str, str]:
    """Fail closed if the R11 authority or any R10-pinned input drifted."""

    r10.verify_upstream_fingerprints()
    observed = {relative: _sha256(REPO_ROOT / relative) for relative in UPSTREAM_SHA256}
    if observed != UPSTREAM_SHA256:
        raise AssertionError(f"R11 authority fingerprint mismatch: {observed}")
    return observed


def canonical_primitives() -> dict[str, int]:
    """Recheck the official-any-prize primitives through the R11 authority."""

    return r11.canonical_primitives()


def local_loss(counts: Sequence[int], losses: Sequence[int]) -> int:
    return sum(count * loss for count, loss in zip(counts, losses, strict=True))


@cache
def prior_authority() -> dict[str, Any]:
    """Rebuild R11 and require it to match its fingerprinted certificate."""

    verify_upstream_fingerprints()
    stored: dict[str, Any] = json.loads(R11_RESULT_PATH.read_text(encoding="utf-8"))
    rebuilt = r11.build_result()
    for key in ("R3_BOUND", "CORRECTED_TAIL_BOUND", "CURRENT_BOUND_OWNER_SET"):
        if rebuilt[key] != stored[key]:
            raise AssertionError(f"rebuilt R11 differs from its certificate at {key}")
    if rebuilt["TOP_LEVEL_R3_TERMS"] != stored["TOP_LEVEL_R3_TERMS"]:
        raise AssertionError("rebuilt R11 top-level terms differ from the certificate")
    tail = cast(dict[str, Any], stored["TAIL_OWNER_DECOMPOSITION"])
    if (
        stored["R3_BOUND"] != PRIOR_R3_BOUND
        or stored["CURRENT_BOUND_OWNER_SET"] != ["corrected-tail"]
        or tail["MINIMUM_OMITTED_LOCAL_LOSS"] != PRIOR_MINIMUM_OMITTED_LOSS
        or tail["LOCAL_LOSS_CUTOFF"] != r7.JOINT_LOCAL_LOSS_CUTOFF
    ):
        raise AssertionError("the R11 authority differs from the task's R3 authority")
    return stored


def non_owner_state_terms() -> tuple[tuple[str, int], ...]:
    """Return the 23 frozen non-tail state terms exactly as R11 certified them."""

    terms = cast(list[dict[str, Any]], prior_authority()["TOP_LEVEL_R3_TERMS"])
    states = tuple(
        (str(term["stable_id"]), int(term["bound"]))
        for term in terms
        if str(term["stable_id"]).startswith("state:")
    )
    if len(states) != 23 or len(terms) != 24:
        raise AssertionError("R11 must contain the corrected tail and exactly 23 states")
    if max(bound for _, bound in states) != TOP_NON_TAIL_STATE_BOUND:
        raise AssertionError("the highest non-tail R3 state bound changed")
    return states


def canonical_uncorrected_baseline() -> int:
    """Return canonical K20 S1 minus the fixed S1-independent R6 reduction."""

    tail = cast(dict[str, Any], prior_authority()["TAIL_OWNER_DECOMPOSITION"])
    fixed = int(tail["FIXED_BASELINE_REDUCTION"])
    baseline = canonical_primitives()["K20_S1"] - fixed
    if fixed != 7_180_012 or baseline != int(tail["CANONICAL_UNCORRECTED_BASELINE"]):
        raise AssertionError("the canonical uncorrected baseline decomposition changed")
    return baseline


@cache
def tail_level_census(level_count: int) -> TailLevelCensus:
    """Enumerate every vector through the first ``level_count`` attained tail levels."""

    if level_count <= 0:
        raise ValueError("level_count must be positive")
    profiles = r5.anchor_incidence_profiles()
    losses = r6.local_losses(profiles)
    cutoff = r7.JOINT_LOCAL_LOSS_CUTOFF
    window = INITIAL_CENSUS_WINDOW
    while True:
        limit = cutoff + window
        at_or_below = 0
        enumerated = 0
        by_loss: dict[int, list[TypeCountVector]] = {}
        for vector in r6.iter_type_count_vectors(losses, OUTSIDE_TICKET_COUNT, limit):
            enumerated += 1
            loss = local_loss(vector, losses)
            if loss > limit or len(vector) != len(profiles):
                raise AssertionError("the exact type-count census emitted an invalid vector")
            if loss <= cutoff:
                at_or_below += 1
            else:
                by_loss.setdefault(loss, []).append(vector)
        if len(by_loss) >= level_count:
            break
        window *= 2

    if at_or_below != R7_CENSUS_VECTOR_COUNT:
        raise AssertionError("the at-or-below-cutoff census differs from R7")
    ordered = sorted(by_loss)[:level_count]
    if ordered[0] < PRIOR_MINIMUM_OMITTED_LOSS:
        raise AssertionError("a tail vector lies below R11's certified omitted-loss floor")
    return TailLevelCensus(
        cutoff=cutoff,
        vectors_at_or_below_cutoff=at_or_below,
        enumeration_loss_limit=limit,
        enumerated_vector_count=enumerated,
        levels=tuple((loss, tuple(sorted(by_loss[loss]))) for loss in ordered),
    )


def attained_levels_below(loss_threshold: int) -> tuple[int, int]:
    """Count attained tail levels and vectors with cutoff < loss < threshold."""

    losses = r6.local_losses(r5.anchor_incidence_profiles())
    cutoff = r7.JOINT_LOCAL_LOSS_CUTOFF
    levels: set[int] = set()
    vectors = 0
    for vector in r6.iter_type_count_vectors(losses, OUTSIDE_TICKET_COUNT, loss_threshold - 1):
        loss = local_loss(vector, losses)
        if loss > cutoff:
            levels.add(loss)
            vectors += 1
    return len(levels), vectors


def construct_support_witness(
    counts: TypeCountVector,
    *,
    restarts: int = WITNESS_RESTARTS,
    ticket_tries: int = WITNESS_TICKET_TRIES,
) -> SupportWitness | None:
    """Build a concrete 18-ticket label support, or return None if none is found.

    A returned witness is accepted only after R8's solver-independent support
    validator confirms every cell demand and every pair overlap of at most 3.
    ``None`` is not an infeasibility proof.
    """

    profiles = r5.anchor_incidence_profiles()
    if len(counts) != len(profiles) or sum(counts) != OUTSIDE_TICKET_COUNT:
        raise ValueError("type-count vector has an invalid dimension or total")
    row_types = tuple(index for index, count in enumerate(counts) for _ in range(count))
    demands = tuple(
        (
            profiles[index].shared,
            profiles[index].a_only,
            profiles[index].b_only,
            profiles[index].outside,
        )
        for index in row_types
    )
    seed = int.from_bytes(sha256(repr(tuple(counts)).encode("ascii")).digest()[:8], "big")
    for restart in range(restarts):
        rng = _SplitMix64(seed + restart)
        # Place rows with the most anchor-cell incidences first.
        keys = [(-sum(demand[:3]), rng.next()) for demand in demands]
        order = sorted(range(len(row_types)), key=keys.__getitem__)
        usage = [0] * r1.POOL_SIZE
        supports: dict[int, frozenset[int]] = {}
        for row in order:
            chosen: frozenset[int] | None = None
            for _ in range(ticket_tries):
                labels: list[int] = []
                for cell, demand in zip(SUPPORT_CELL_LABELS, demands[row], strict=True):
                    ordered = rng.shuffled(cell)
                    if rng.next() & 1:
                        ordered.sort(key=usage.__getitem__)
                    labels.extend(ordered[:demand])
                candidate = frozenset(labels)
                if all(
                    len(candidate & other) <= MAXIMUM_PAIR_OVERLAP for other in supports.values()
                ):
                    chosen = candidate
                    break
            if chosen is None:
                break
            supports[row] = chosen
            for label in chosen:
                usage[label] += 1
        if len(supports) == len(row_types):
            witness = tuple(tuple(sorted(supports[row])) for row in range(len(row_types)))
            if not r8.validate_support_assignment(counts, witness):
                raise AssertionError("a constructed support witness failed the R8 validator")
            return witness
    return None


def classify_vector(counts: TypeCountVector, baseline: int) -> VectorClassification:
    """Eliminate, or realize and correct, one tail type-count vector."""

    profiles = r5.anchor_incidence_profiles()
    losses = r6.local_losses(profiles)
    loss = local_loss(counts, losses)
    if not r6.aggregate_count_vector_is_feasible(counts):
        return VectorClassification(counts, loss, ELIMINATED, None, None, None, None, None)

    envelope = r6.type_count_envelope(counts)
    if envelope.local_loss != loss:
        raise AssertionError("the R6 envelope disagrees with the census local loss")
    anchor_s2 = sum(
        count * profile.pair_recovery_cost for count, profile in zip(counts, profiles, strict=True)
    )
    anchor_s3 = sum(
        count * profile.triple_recovery for count, profile in zip(counts, profiles, strict=True)
    )
    joint_constant = canonical_primitives()["K20_S1"] - r7.ANCHOR_PAIR_INTERSECTION
    if joint_constant - anchor_s2 + anchor_s3 != baseline - loss:
        raise AssertionError("the coarse tail loss disagrees with exact anchor S2/S3")
    correction = envelope.combined_pair_penalty
    witness = construct_support_witness(counts)
    return VectorClassification(
        counts=counts,
        local_loss=loss,
        status=WITNESS_REALIZED if witness is not None else UNWITNESSED,
        pair_union_penalty=envelope.pair_union_penalty,
        forest_floor=envelope.prior_forest_penalty,
        correction=correction,
        vector_bound=baseline - loss - correction,
        witness=witness,
    )


@cache
def classify_tail_plateaus(level_budget: int = LOSS_LEVEL_BUDGET) -> TailPlateauCertificate:
    """Classify ascending attained tail levels until the first stop condition."""

    started = time.monotonic()
    baseline = canonical_uncorrected_baseline()
    top_state = max(bound for _, bound in non_owner_state_terms())
    # One extra level certifies the floor that remains after the last processed level.
    census = tail_level_census(level_budget + 1)
    processed: list[LevelClassification] = []
    processed_maximum: int | None = None
    stop_condition = "NONE"
    flags = {
        "A_R3_AT_OR_BELOW_TOP_NON_TAIL_STATE": False,
        "B_R3_AT_OR_BELOW_R4_REFERENCE": False,
        "C_CERTIFIED_TIGHTENING_AT_LEAST_50000": False,
        "D_LOSS_LEVEL_BUDGET_EXHAUSTED": False,
        "E_PROOF_WALL_BUDGET_EXHAUSTED": False,
    }
    for ordinal, (loss, vectors) in enumerate(census.levels[:level_budget], start=1):
        if time.monotonic() - started >= PROOF_WALL_BUDGET_SECONDS:
            flags["E_PROOF_WALL_BUDGET_EXHAUSTED"] = True
            stop_condition = "E_PROOF_WALL_BUDGET_EXHAUSTED"
            break
        rows = tuple(classify_vector(vector, baseline) for vector in vectors)
        for row in rows:
            if row.vector_bound is not None:
                processed_maximum = (
                    row.vector_bound
                    if processed_maximum is None
                    else max(processed_maximum, row.vector_bound)
                )
        next_loss = census.levels[ordinal][0]
        floor_bound = baseline - next_loss
        effective_tail = (
            floor_bound if processed_maximum is None else max(processed_maximum, floor_bound)
        )
        r3_bound = max(effective_tail, top_state)
        processed.append(
            LevelClassification(ordinal, loss, rows, next_loss, effective_tail, r3_bound)
        )
        flags["A_R3_AT_OR_BELOW_TOP_NON_TAIL_STATE"] = r3_bound <= TOP_NON_TAIL_STATE_BOUND
        flags["B_R3_AT_OR_BELOW_R4_REFERENCE"] = r3_bound <= R4_REFERENCE_BOUND
        flags["C_CERTIFIED_TIGHTENING_AT_LEAST_50000"] = (
            PRIOR_R3_BOUND - r3_bound >= TIGHTENING_STOP
        )
        flags["D_LOSS_LEVEL_BUDGET_EXHAUSTED"] = ordinal >= level_budget
        flags["E_PROOF_WALL_BUDGET_EXHAUSTED"] = (
            time.monotonic() - started >= PROOF_WALL_BUDGET_SECONDS
        )
        triggered = [name for name, value in flags.items() if value]
        if triggered:
            stop_condition = triggered[0]
            break

    if not processed:
        raise AssertionError("no tail loss level was classified before the stop condition")
    final = processed[-1]
    return TailPlateauCertificate(
        census=census,
        levels=tuple(processed),
        stop_condition=stop_condition,
        stop_flags=dict(flags),
        effective_tail_bound=final.effective_tail_bound,
        r3_bound=final.r3_bound,
        wall_seconds=time.monotonic() - started,
    )


def identify_owner_set(terms: Sequence[tuple[str, int]]) -> tuple[str, ...]:
    """Return every term tied at the maximum, preserving input order."""

    return r11.identify_owner_set(
        r11.BoundTerm(
            term_id=term_id,
            bound=bound,
            primitive_dependencies=(),
            structural_certificate_source="R12",
        )
        for term_id, bound in terms
    )


def _witness_digest(rows: Sequence[VectorClassification]) -> str:
    payload = tuple((row.counts, row.witness) for row in rows if row.witness is not None)
    return sha256(repr(payload).encode("ascii")).hexdigest()


def _sparse(counts: TypeCountVector) -> list[list[int]]:
    return [[index, count] for index, count in enumerate(counts) if count]


def build_result() -> dict[str, Any]:
    """Build the compact effective-tail certificate and final R3 maximum."""

    primitives = canonical_primitives()
    fingerprints = verify_upstream_fingerprints()
    prior = prior_authority()
    baseline = canonical_uncorrected_baseline()
    states = non_owner_state_terms()
    certificate = classify_tail_plateaus()
    census = certificate.census
    rows = tuple(row for level in certificate.levels for row in level.vectors)
    surviving = tuple(row for row in rows if row.vector_bound is not None)
    eliminated = sum(row.status == ELIMINATED for row in rows)
    realized = sum(row.status == WITNESS_REALIZED for row in rows)
    unwitnessed = sum(row.status == UNWITNESSED for row in rows)
    if eliminated + realized + unwitnessed != len(rows):
        raise AssertionError("a tail vector has no classification")

    final = certificate.levels[-1]
    tail_bound = certificate.effective_tail_bound
    floor_bound = baseline - final.next_unprocessed_loss
    worst = max(surviving, key=lambda row: (cast(int, row.vector_bound), row.counts))
    if tail_bound != max(floor_bound, cast(int, worst.vector_bound)):
        raise AssertionError("the effective-tail certificate formula failed")
    binding = (
        "NEXT_UNPROCESSED_LOSS_LEVEL_FLOOR"
        if floor_bound >= cast(int, worst.vector_bound)
        else "PROCESSED_VECTOR_CORRECTED_BOUND"
    )
    terms = (("corrected-tail", tail_bound), *states)
    owners = identify_owner_set(terms)
    r3_bound = max(bound for _, bound in terms)
    if r3_bound != certificate.r3_bound or r3_bound > PRIOR_R3_BOUND:
        raise AssertionError("the final R3 maximum disagrees with the plateau certificate")
    if tail_bound >= int(prior["CORRECTED_TAIL_BOUND"]) and r3_bound != PRIOR_R3_BOUND:
        raise AssertionError("a non-tightened tail cannot change R3")

    corrections = [cast(int, row.correction) for row in surviving]
    stop_a_loss = baseline - TOP_NON_TAIL_STATE_BOUND
    sizing_levels, sizing_vectors = attained_levels_below(stop_a_loss)
    first_loss = census.levels[0][0]
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": (
            "CERTIFIED_R3_BOUND_TIGHTENED" if r3_bound < PRIOR_R3_BOUND else "NO_TIGHTENING"
        ),
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
        "PRIOR_CORRECTED_TAIL_BOUND": prior["CORRECTED_TAIL_BOUND"],
        "PRIOR_BOUND_OWNER_SET": prior["CURRENT_BOUND_OWNER_SET"],
        "START_TAIL_LOSS": PRIOR_MINIMUM_OMITTED_LOSS,
        "START_PLATEAU": {
            "LOCAL_LOSS": PRIOR_MINIMUM_OMITTED_LOSS,
            "VECTOR_COUNT": 0,
            "STATUS": "EMPTY",
            "CERTIFIED_EMPTY_LOSS_INTERVAL": [PRIOR_MINIMUM_OMITTED_LOSS, first_loss - 1],
        },
        "LEVEL_CENSUS": {
            "LOCAL_LOSS_CUTOFF": census.cutoff,
            "VECTORS_AT_OR_BELOW_CUTOFF": census.vectors_at_or_below_cutoff,
            "ENUMERATION_LOSS_LIMIT": census.enumeration_loss_limit,
            "ENUMERATED_VECTOR_COUNT": census.enumerated_vector_count,
            "ATTAINED_LEVELS_RECORDED": len(census.levels),
            "LEVEL_DEFINITION": (
                "A loss level is a local-loss value attained by at least one 18-ticket "
                "type-count vector; every integer strictly between consecutive levels is "
                "certified empty by the same exact enumeration."
            ),
        },
        "LOSS_LEVELS_PROCESSED": len(certificate.levels),
        "LOSS_LEVEL_ROWS": [
            {
                "ordinal": level.ordinal,
                "local_loss": level.local_loss,
                "offset_above_cutoff": level.local_loss - census.cutoff,
                "vector_count": len(level.vectors),
                "eliminated": sum(row.status == ELIMINATED for row in level.vectors),
                "witness_realized": sum(row.status == WITNESS_REALIZED for row in level.vectors),
                "unwitnessed": sum(row.status == UNWITNESSED for row in level.vectors),
                "minimum_correction": min(
                    (row.correction for row in level.vectors if row.correction is not None),
                    default=None,
                ),
                "maximum_vector_bound": max(
                    (row.vector_bound for row in level.vectors if row.vector_bound is not None),
                    default=None,
                ),
                "next_unprocessed_loss": level.next_unprocessed_loss,
                "effective_tail_bound": level.effective_tail_bound,
                "r3_bound": level.r3_bound,
            }
            for level in certificate.levels
        ],
        "MIN_REALIZABLE_TAIL_LOSS": min(
            (row.local_loss for row in rows if row.status == WITNESS_REALIZED), default=None
        ),
        "TAIL_VECTOR_COUNT": len(rows),
        "UNREALIZABLE_VECTOR_COUNT": eliminated,
        "REALIZABLE_VECTOR_COUNT": realized,
        "UNRESOLVED_VECTOR_COUNT": unwitnessed,
        "SUPPORT_WITNESS_SHA256": _witness_digest(rows),
        "SUPPORT_WITNESS_VALIDATOR": "R8 validate_support_assignment (solver-independent)",
        "MANDATORY_HIGHER_ORDER_CORRECTION": {
            "MINIMUM": min(corrections),
            "MAXIMUM": max(corrections),
            "SOURCE": (
                "R6 type_count_envelope: max(ceil(residual pair/anchor-triple intersection "
                "mass floor / 9), frozen R5 weighted-forest floor)"
            ),
            "FOURTH_ORDER_CORRECTION": "NOT_REQUIRED; every processed vector is below the floor",
            "MINIMUM_SLACK_BELOW_TAIL_FLOOR": floor_bound - cast(int, worst.vector_bound),
            "WORST_PROCESSED_VECTOR": {
                "TYPE_COUNTS": _sparse(worst.counts),
                "LOCAL_LOSS": worst.local_loss,
                "CORRECTION": worst.correction,
                "VECTOR_BOUND": worst.vector_bound,
            },
        },
        "EFFECTIVE_TAIL_CERTIFICATE": {
            "CANONICAL_K20_S1": primitives["K20_S1"],
            "FIXED_CERTIFIED_LOSS": primitives["K20_S1"] - baseline,
            "BINDING_TERM": binding,
            "TYPE_COUNT_LOSS": final.next_unprocessed_loss,
            "MANDATORY_STRUCTURAL_CORRECTION": 0,
            "EFFECTIVE_TAIL_BOUND": tail_bound,
            "FORMULA": (
                "max(max over processed surviving v of S1 - fixed - L(v) - corr(v), "
                "S1 - fixed - first unprocessed attained level)"
            ),
        },
        "CORRECTED_TAIL_BOUND": tail_bound,
        "TOP_STATE_BOUND": max(bound for _, bound in states),
        "TOP_LEVEL_R3_TERMS": [{"stable_id": term_id, "bound": bound} for term_id, bound in terms],
        "CURRENT_BOUND_OWNER_SET": list(owners),
        "R3_BOUND": r3_bound,
        "R3_STATUS": (
            "CERTIFIED_STRICTLY_BELOW_PRIOR_BOUND" if r3_bound < PRIOR_R3_BOUND else "UNCHANGED"
        ),
        "R3_TIGHTENING": PRIOR_R3_BOUND - r3_bound,
        "STOP_CONDITION": certificate.stop_condition,
        "STOP_FLAGS": certificate.stop_flags,
        "SUCCESS_A": r3_bound <= R4_REFERENCE_BOUND,
        "SUCCESS_B": r3_bound <= TOP_NON_TAIL_STATE_BOUND,
        "SUCCESS_C": r3_bound < PRIOR_R3_BOUND,
        "R4_REFERENCE_BOUND": R4_REFERENCE_BOUND,
        "INCUMBENT": r1.INCUMBENT,
        "REMAINING_GAP": r3_bound - r1.INCUMBENT,
        "NEXT_PACKET_SIZING": {
            "STOP_A_LOCAL_LOSS_THRESHOLD": stop_a_loss,
            "ATTAINED_LEVELS_BELOW_STOP_A_THRESHOLD": sizing_levels,
            "VECTORS_BELOW_STOP_A_THRESHOLD": sizing_vectors,
            "SCOPE": "census count only; levels beyond the budget were not classified",
        },
        "PROOF_WALL_SECONDS": round(certificate.wall_seconds, 6),
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
