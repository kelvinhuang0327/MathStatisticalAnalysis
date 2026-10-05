"""Joint residual S2/S3 envelope for the K20 r_max=3 anchor family.

This proof reuses the exact r6 anchor-type and type-count APIs. It extends the
published 2,683-vector census only through the first certified total-reduction
threshold, then compresses feasible count vectors into coexisting S2/S3
incidence states. No ticket portfolios are constructed.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256
from math import comb
from typing import Any

from lottolab.research.b649_k20_outside_min_s2_global_penalty_bound_r1 import (
    INCUMBENT,
    SINGLE_TICKET_OUTCOMES,
    TICKET_COUNT,
    pair_intersection_table,
)
from lottolab.research.b649_k20_r3_anchor_incidence_bound_r5 import (
    AnchorIncidenceProfile,
    anchor_incidence_profiles,
)
from lottolab.research.b649_k20_r3_exact_anchor_neighborhood_envelope_r6 import (
    OUTSIDE_LABEL_CAPACITY,
    OUTSIDE_PAIR_SLOPE,
    PAIR_MULTIPLICITY_DIVISOR,
    PRIOR_FOREST_PENALTY_BY_GOOD_COUNT,
    UNCORRECTED_R3_BOUND,
    aggregate_count_vector_is_feasible,
    balanced_pair_mass,
    candidate_type_count_vectors,
    iter_type_count_vectors,
    local_losses,
    type_pair_certificate,
)

BASE_HEAD = "0ee55267daffeb6bb2c4cd16888d2b3ca8ecb6d7"
BASE_TREE = "a8b084ad88679bae4a9fc4495555975a8987834e"
TASK_BRANCH = "codex/b649-k20-r3-joint-residual-envelope-r7"
TASK_ID = "B649_K20_R3_JOINT_RESIDUAL_ENVELOPE_R7"
CURRENT_R3_BOUND = 351_483_978
FROZEN_R4_BOUND = 351_106_608
FROZEN_R5_BOUND = 350_778_728
FROZEN_R6_BOUND = 343_869_728
JOINT_LOCAL_LOSS_CUTOFF = 6_695_798
EXPECTED_REUSED_VECTOR_COUNT = 2_683
EXPECTED_REUSED_VECTOR_REPR_SHA256 = (
    "6e6dbdf5bb9cdf2905a7c8dbc061a032cb0dce005b3fb80b062f40eb64e1581f"
)
EXPECTED_CANDIDATE_VECTOR_COUNT = 10_816
ANCHOR_PAIR_INTERSECTION = pair_intersection_table()[3]
ANCHOR_PAIR_UNION_OUTCOMES = 2 * SINGLE_TICKET_OUTCOMES - ANCHOR_PAIR_INTERSECTION
JOINT_EXPRESSION_CONSTANT = (
    ANCHOR_PAIR_UNION_OUTCOMES
    + (TICKET_COUNT - 2) * SINGLE_TICKET_OUTCOMES
)
CellIncidences = tuple[int, int, int, int]
FrequencyHistogram = tuple[tuple[int, int], ...]
TypeCountVector = tuple[int, ...]


@dataclass(frozen=True)
class ResidualJointState:
    """One compressed count-vector state with mutually consistent moments."""

    local_loss: int
    anchor_pair_s2: int
    anchor_triple_s3: int
    residual_pair_intersection_mass_floor: int
    residual_pair_union_penalty: int
    complementary_forest_floor: int
    applied_residual_union_penalty: int
    joint_s2: int
    joint_s3: int
    cell_incidences: CellIncidences
    outside_incidence_total: int
    outside_multiplicity_floor: FrequencyHistogram
    witness_counts: TypeCountVector
    represented_vector_count: int

    @property
    def upper_bound(self) -> int:
        return JOINT_EXPRESSION_CONSTANT - self.joint_s2 + self.joint_s3


@dataclass(frozen=True)
class JointFrontierPoint:
    """The maximum realized S3 at one S2 level and its count-vector witness."""

    joint_s2: int
    maximum_joint_s3: int
    witness_counts: TypeCountVector
    maximizing_vector_count: int

    @property
    def upper_bound(self) -> int:
        return JOINT_EXPRESSION_CONSTANT - self.joint_s2 + self.maximum_joint_s3


@dataclass(frozen=True)
class JointResidualCensus:
    """Finite census summary after exact type-count-vector compression."""

    reused_vector_count: int
    reused_vector_sha256: str
    candidate_vector_count: int
    supplemental_vector_count: int
    feasible_vector_count: int
    feasible_reused_vector_count: int
    feasible_supplemental_vector_count: int
    states: tuple[ResidualJointState, ...]
    s2_s3_envelope: tuple[JointFrontierPoint, ...]
    frontier: tuple[JointFrontierPoint, ...]
    s2_level_count: int
    tail_bound: int
    r3_bound: int
    bound_source: str


def _vector_digest(vectors: tuple[TypeCountVector, ...]) -> str:
    return sha256(repr(vectors).encode("ascii")).hexdigest()


def reused_exact_type_count_vectors() -> tuple[TypeCountVector, ...]:
    """Return the exact published r6 vector census, guarded by its fingerprint."""

    vectors = candidate_type_count_vectors()
    if len(vectors) != EXPECTED_REUSED_VECTOR_COUNT:
        raise AssertionError("the established r3 type-count vector census changed")
    if len(set(vectors)) != len(vectors):
        raise AssertionError("the established r3 type-count vector census has duplicates")
    if _vector_digest(vectors) != EXPECTED_REUSED_VECTOR_REPR_SHA256:
        raise AssertionError("the established r3 type-count vectors do not match r6")
    return vectors


def balanced_frequency_histogram(
    incidence_total: int, label_capacity: int
) -> FrequencyHistogram:
    """Return the balanced frequency histogram giving the exact convex S2 floor."""

    if incidence_total < 0 or label_capacity <= 0:
        raise ValueError("incidence total and label capacity must be valid")
    quotient, remainder = divmod(incidence_total, label_capacity)
    if quotient > TICKET_COUNT - 2 or (
        quotient == TICKET_COUNT - 2 and remainder > 0
    ):
        raise ValueError("label frequency exceeds the number of outside tickets")
    rows: list[tuple[int, int]] = []
    if label_capacity - remainder:
        rows.append((quotient, label_capacity - remainder))
    if remainder:
        rows.append((quotient + 1, remainder))
    return tuple(rows)


def _multiplicity_pair_mass(histogram: FrequencyHistogram) -> int:
    return sum(label_count * comb(frequency, 2) for frequency, label_count in histogram)


def _vector_cell_incidences(
    counts: TypeCountVector, profiles: tuple[AnchorIncidenceProfile, ...]
) -> CellIncidences:
    return tuple(
        sum(count * getattr(profile, name) for count, profile in zip(counts, profiles, strict=True))
        for name in ("shared", "a_only", "b_only", "outside")
    )  # type: ignore[return-value]


def _pair_mass_floor(
    counts: TypeCountVector,
    outside_incidence_total: int,
) -> int:
    """Sum exact type-pair floors and the balanced outside-label S2 floor."""

    mass = OUTSIDE_PAIR_SLOPE * balanced_pair_mass(
        outside_incidence_total, OUTSIDE_LABEL_CAPACITY
    )
    for left_index, left_count in enumerate(counts):
        if left_count == 0:
            continue
        for right_index in range(left_index, len(counts)):
            right_count = counts[right_index]
            pair_count = (
                comb(left_count, 2) if left_index == right_index else left_count * right_count
            )
            if pair_count == 0:
                continue
            certificate = type_pair_certificate(left_index, right_index)
            if certificate is None:
                raise AssertionError("an aggregate-feasible vector has an impossible type pair")
            mass += pair_count * certificate.minimum_residual_intersection
    return mass


def _state_signature(state: ResidualJointState) -> tuple[object, ...]:
    return (
        state.local_loss,
        state.anchor_pair_s2,
        state.anchor_triple_s3,
        state.residual_pair_intersection_mass_floor,
        state.residual_pair_union_penalty,
        state.complementary_forest_floor,
        state.applied_residual_union_penalty,
        state.joint_s2,
        state.joint_s3,
        state.cell_incidences,
        state.outside_incidence_total,
        state.outside_multiplicity_floor,
    )


def _make_state(
    counts: TypeCountVector,
    profiles: tuple[AnchorIncidenceProfile, ...],
    losses: tuple[int, ...],
    *,
    represented_vector_count: int = 1,
    check_feasibility: bool = True,
) -> ResidualJointState:
    if len(counts) != len(profiles) or sum(counts) != TICKET_COUNT - 2:
        raise ValueError("type-count vector has an invalid dimension or total")
    if check_feasibility and not aggregate_count_vector_is_feasible(counts):
        raise ValueError("type-count vector fails the established aggregate feasibility test")

    anchor_pair_s2 = sum(
        count * profile.pair_recovery_cost
        for count, profile in zip(counts, profiles, strict=True)
    )
    anchor_triple_s3 = sum(
        count * profile.triple_recovery
        for count, profile in zip(counts, profiles, strict=True)
    )
    local_loss = sum(count * loss for count, loss in zip(counts, losses, strict=True))
    incidences = _vector_cell_incidences(counts, profiles)
    outside_total = incidences[3]
    outside_histogram = balanced_frequency_histogram(
        outside_total, OUTSIDE_LABEL_CAPACITY
    )
    outside_pair_mass = _multiplicity_pair_mass(outside_histogram)
    if outside_pair_mass != balanced_pair_mass(outside_total, OUTSIDE_LABEL_CAPACITY):
        raise AssertionError("outside multiplicity histogram disagrees with balanced S2 floor")
    pair_mass_floor = _pair_mass_floor(counts, outside_total)
    pair_union_penalty = (
        pair_mass_floor + PAIR_MULTIPLICITY_DIVISOR - 1
    ) // PAIR_MULTIPLICITY_DIVISOR
    complementary_forest_floor = PRIOR_FOREST_PENALTY_BY_GOOD_COUNT[counts[0]]
    applied_penalty = max(pair_union_penalty, complementary_forest_floor)
    joint_s2 = anchor_pair_s2 + applied_penalty

    best_net_recovery = profiles[0].net_recovery
    if local_loss != (TICKET_COUNT - 2) * best_net_recovery - (
        anchor_triple_s3 - anchor_pair_s2
    ):
        raise AssertionError("local loss disagrees with the exact per-type S2/S3 scores")
    if UNCORRECTED_R3_BOUND - local_loss != (
        JOINT_EXPRESSION_CONSTANT - anchor_pair_s2 + anchor_triple_s3
    ):
        raise AssertionError("anchor-conditioned S2/S3 expression disagrees with r6")

    return ResidualJointState(
        local_loss=local_loss,
        anchor_pair_s2=anchor_pair_s2,
        anchor_triple_s3=anchor_triple_s3,
        residual_pair_intersection_mass_floor=pair_mass_floor,
        residual_pair_union_penalty=pair_union_penalty,
        complementary_forest_floor=complementary_forest_floor,
        applied_residual_union_penalty=applied_penalty,
        joint_s2=joint_s2,
        joint_s3=anchor_triple_s3,
        cell_incidences=incidences,
        outside_incidence_total=outside_total,
        outside_multiplicity_floor=outside_histogram,
        witness_counts=counts,
        represented_vector_count=represented_vector_count,
    )


def pareto_s2_s3_pairs(
    moment_pairs: Iterable[tuple[int, int]],
) -> tuple[tuple[int, int], ...]:
    """Return realized nondominated ``(minimum S2, maximum S3)`` pairs."""

    maximum_s3_by_s2: dict[int, int] = {}
    for s2, s3 in moment_pairs:
        if s2 < 0 or s3 < 0:
            raise ValueError("S2 and S3 moments must be nonnegative")
        maximum_s3_by_s2[s2] = max(s3, maximum_s3_by_s2.get(s2, -1))

    frontier: list[tuple[int, int]] = []
    best_s3_so_far = -1
    for s2, s3 in sorted(maximum_s3_by_s2.items()):
        if s3 > best_s3_so_far:
            frontier.append((s2, s3))
            best_s3_so_far = s3
    return tuple(frontier)


def _joint_s2_s3_envelope(
    states: tuple[ResidualJointState, ...],
) -> tuple[JointFrontierPoint, ...]:
    best_by_s2: dict[int, ResidualJointState] = {}
    vector_counts_by_s2_s3: dict[tuple[int, int], int] = {}
    for state in states:
        current = best_by_s2.get(state.joint_s2)
        if current is None or state.joint_s3 > current.joint_s3 or (
            state.joint_s3 == current.joint_s3
            and state.witness_counts < current.witness_counts
        ):
            best_by_s2[state.joint_s2] = state
        moment_pair = (state.joint_s2, state.joint_s3)
        vector_counts_by_s2_s3[moment_pair] = (
            vector_counts_by_s2_s3.get(moment_pair, 0) + state.represented_vector_count
        )

    return tuple(
        JointFrontierPoint(
            joint_s2=s2,
            maximum_joint_s3=state.joint_s3,
            witness_counts=state.witness_counts,
            maximizing_vector_count=vector_counts_by_s2_s3[(s2, state.joint_s3)],
        )
        for s2, state in sorted(best_by_s2.items())
    )


def _pareto_frontier_from_envelope(
    envelope: tuple[JointFrontierPoint, ...],
) -> tuple[JointFrontierPoint, ...]:
    by_s2 = {point.joint_s2: point for point in envelope}
    pairs = pareto_s2_s3_pairs(
        (point.joint_s2, point.maximum_joint_s3) for point in envelope
    )
    return tuple(by_s2[s2] for s2, _ in pairs)


@dataclass
class _StateAccumulator:
    witness: TypeCountVector
    count: int


@dataclass(frozen=True)
class _CensusBuild:
    candidate_vector_count: int
    supplemental_vector_count: int
    feasible_vector_count: int
    feasible_reused_vector_count: int
    feasible_supplemental_vector_count: int
    states: tuple[ResidualJointState, ...]
    s2_level_count: int


def _build_joint_census() -> _CensusBuild:
    profiles = anchor_incidence_profiles()
    if len(profiles) != 30:
        raise AssertionError("the established r3 anchor-incidence table changed")
    losses = local_losses(profiles)
    reused_vectors = reused_exact_type_count_vectors()
    reused_set = set(reused_vectors)
    candidates = tuple(
        iter_type_count_vectors(
            losses, TICKET_COUNT - 2, JOINT_LOCAL_LOSS_CUTOFF
        )
    )
    if len(candidates) != EXPECTED_CANDIDATE_VECTOR_COUNT:
        raise AssertionError("the bounded joint type-count census changed")
    candidate_set = set(candidates)
    if len(candidate_set) != len(candidates) or not reused_set.issubset(candidate_set):
        raise AssertionError("the joint census did not exactly reuse the r6 vectors")
    if any(
        sum(count * loss for count, loss in zip(vector, losses, strict=True))
        > JOINT_LOCAL_LOSS_CUTOFF
        for vector in candidates
    ):
        raise AssertionError("the bounded census admitted a vector above its loss cutoff")

    accumulators: dict[tuple[object, ...], _StateAccumulator] = {}
    feasible_reused = 0
    feasible_supplemental = 0
    for vector in candidates:
        if not aggregate_count_vector_is_feasible(vector):
            continue
        is_reused = vector in reused_set
        state = _make_state(
            vector, profiles, losses, check_feasibility=False
        )
        signature = _state_signature(state)
        accumulator = accumulators.get(signature)
        if accumulator is None:
            accumulators[signature] = _StateAccumulator(vector, 1)
        else:
            accumulator.count += 1
            if vector < accumulator.witness:
                accumulator.witness = vector
        if is_reused:
            feasible_reused += 1
        else:
            feasible_supplemental += 1

    states = tuple(
        sorted(
            (
                _make_state(
                    accumulator.witness,
                    profiles,
                    losses,
                    represented_vector_count=accumulator.count,
                    check_feasibility=False,
                )
                for accumulator in accumulators.values()
            ),
            key=lambda state: (
                state.joint_s2,
                state.joint_s3,
                state.local_loss,
                state.witness_counts,
            ),
        )
    )
    feasible_count = feasible_reused + feasible_supplemental
    if feasible_reused != EXPECTED_REUSED_VECTOR_COUNT:
        raise AssertionError("an existing feasible r6 vector was lost from the joint census")
    if sum(state.represented_vector_count for state in states) != feasible_count:
        raise AssertionError("state compression changed the feasible vector count")

    s2_level_count = len({state.joint_s2 for state in states})
    return _CensusBuild(
        candidate_vector_count=len(candidates),
        supplemental_vector_count=len(candidates) - len(reused_vectors),
        feasible_vector_count=feasible_count,
        feasible_reused_vector_count=feasible_reused,
        feasible_supplemental_vector_count=feasible_supplemental,
        states=states,
        s2_level_count=s2_level_count,
    )


_joint_census_cache: _CensusBuild | None = None


def joint_residual_census() -> JointResidualCensus:
    """Build the exact compressed census and maximize its realized frontier."""

    global _joint_census_cache
    if _joint_census_cache is None:
        _joint_census_cache = _build_joint_census()
    build = _joint_census_cache
    envelope = _joint_s2_s3_envelope(build.states)
    frontier = _pareto_frontier_from_envelope(envelope)
    frontier_bound = max(point.upper_bound for point in frontier)
    tail_bound = UNCORRECTED_R3_BOUND - JOINT_LOCAL_LOSS_CUTOFF - 1
    r3_bound = max(frontier_bound, tail_bound)
    bound_source = "JOINT_S2_S3_FRONTIER" if frontier_bound >= tail_bound else "LOCAL_LOSS_TAIL"
    return JointResidualCensus(
        reused_vector_count=EXPECTED_REUSED_VECTOR_COUNT,
        reused_vector_sha256=EXPECTED_REUSED_VECTOR_REPR_SHA256,
        candidate_vector_count=build.candidate_vector_count,
        supplemental_vector_count=build.supplemental_vector_count,
        feasible_vector_count=build.feasible_vector_count,
        feasible_reused_vector_count=build.feasible_reused_vector_count,
        feasible_supplemental_vector_count=build.feasible_supplemental_vector_count,
        states=build.states,
        s2_s3_envelope=envelope,
        frontier=frontier,
        s2_level_count=build.s2_level_count,
        tail_bound=tail_bound,
        r3_bound=r3_bound,
        bound_source=bound_source,
    )


def _sparse_counts(counts: TypeCountVector) -> list[list[int]]:
    return [[index, count] for index, count in enumerate(counts) if count]


def _frontier_digest(frontier: tuple[JointFrontierPoint, ...]) -> str:
    payload = "\n".join(
        f"{point.joint_s2},{point.maximum_joint_s3}"
        for point in frontier
    )
    return sha256(payload.encode("ascii")).hexdigest()


def _envelope_digest(envelope: tuple[JointFrontierPoint, ...]) -> str:
    payload = "\n".join(
        f"{point.joint_s2},{point.maximum_joint_s3}"
        for point in envelope
    )
    return sha256(payload.encode("ascii")).hexdigest()


def family_a_result_record(
    *,
    focused_tests: str = "NOT_RUN",
    ruff: str = "NOT_RUN",
    pyright: str = "NOT_RUN",
) -> dict[str, Any]:
    """Build the compact proof record from the joint finite-state envelope."""

    census = joint_residual_census()
    frontier_witness = max(census.frontier, key=lambda point: point.upper_bound)
    best_state = next(
        state
        for state in census.states
        if state.witness_counts == frontier_witness.witness_counts
    )
    family_bounds = {
        "R3": census.r3_bound,
        "R4": FROZEN_R4_BOUND,
        "R5": FROZEN_R5_BOUND,
        "R6": FROZEN_R6_BOUND,
    }
    family_bound = max(family_bounds.values())
    bottleneck_r = max(family_bounds, key=family_bounds.__getitem__)
    r3_status = "CLOSED" if census.r3_bound <= INCUMBENT else "TIGHTENED_OPEN"
    return {
        "TASK_ID": TASK_ID,
        "TASK_STATUS": "CERTIFIED_R3_BOUND_TIGHTENED",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_BRANCH": TASK_BRANCH,
        "REUSED_EXACT_TYPE_COUNT_VECTOR_COUNT": census.reused_vector_count,
        "REUSED_EXACT_TYPE_COUNT_VECTOR_SHA256_REPR": census.reused_vector_sha256,
        "LOCAL_LOSS_CENSUS_CUTOFF": JOINT_LOCAL_LOSS_CUTOFF,
        "CANDIDATE_TYPE_COUNT_VECTOR_COUNT": census.candidate_vector_count,
        "SUPPLEMENTAL_TYPE_COUNT_VECTOR_COUNT": census.supplemental_vector_count,
        "FEASIBLE_TYPE_COUNT_VECTOR_COUNT": census.feasible_vector_count,
        "FEASIBLE_REUSED_TYPE_COUNT_VECTOR_COUNT": census.feasible_reused_vector_count,
        "FEASIBLE_SUPPLEMENTAL_TYPE_COUNT_VECTOR_COUNT": (
            census.feasible_supplemental_vector_count
        ),
        "RESIDUAL_STATE_COUNT": len(census.states),
        "S2_LEVEL_COUNT": census.s2_level_count,
        "S2_S3_ENVELOPE_LEVEL_COUNT": len(census.s2_s3_envelope),
        "S2_S3_ENVELOPE_SHA256": _envelope_digest(census.s2_s3_envelope),
        "S2_S3_FRONTIER_SIZE": len(census.frontier),
        "S2_S3_FRONTIER_SHA256": _frontier_digest(census.frontier),
        "S2_S3_FRONTIER": [
            {
                "JOINT_S2": point.joint_s2,
                "MAXIMUM_JOINT_S3": point.maximum_joint_s3,
                "UPPER_BOUND": point.upper_bound,
            }
            for point in census.frontier
        ],
        "JOINT_BOUND_SOURCE": census.bound_source,
        "JOINT_S2_S3_WITNESS": {
            "TYPE_COUNTS": _sparse_counts(best_state.witness_counts),
            "LOCAL_RECOVERY_LOSS": best_state.local_loss,
            "ANCHOR_PAIR_S2": best_state.anchor_pair_s2,
            "ANCHOR_TRIPLE_S3": best_state.anchor_triple_s3,
            "RESIDUAL_PAIR_INTERSECTION_MASS_FLOOR": (
                best_state.residual_pair_intersection_mass_floor
            ),
            "RESIDUAL_PAIR_UNION_PENALTY": best_state.residual_pair_union_penalty,
            "COMPLEMENTARY_FROZEN_FOREST_FLOOR": best_state.complementary_forest_floor,
            "APPLIED_RESIDUAL_UNION_PENALTY": (
                best_state.applied_residual_union_penalty
            ),
            "JOINT_S2": best_state.joint_s2,
            "JOINT_S3": best_state.joint_s3,
            "CELL_INCIDENCES": {
                "shared": best_state.cell_incidences[0],
                "a_only": best_state.cell_incidences[1],
                "b_only": best_state.cell_incidences[2],
                "outside": best_state.cell_incidences[3],
            },
            "OUTSIDE_MULTIPLICITY_FLOOR": [
                {"frequency": frequency, "label_count": count}
                for frequency, count in best_state.outside_multiplicity_floor
            ],
            "UPPER_BOUND": best_state.upper_bound,
        },
        "TAIL_LOCAL_LOSS_BOUND": census.tail_bound,
        "R3_BOUND": census.r3_bound,
        "R3_STATUS": r3_status,
        "FAMILY_A_LEAF_BOUNDS": family_bounds,
        "FAMILY_A_RECOMPUTED_BOUND": family_bound,
        "FAMILY_A_BOTTLENECK_R": bottleneck_r,
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": family_bound - INCUMBENT,
        "MANDATORY_OUTSIDE_PAIR_PENALTY": 1_824_008,
        "PROOF": {
            "JOINT_EXPRESSION": (
                "2*N-I(3)+18*N-S2+S3; S2 is the exact anchor-pair cost plus "
                "the maximum of a per-vector residual pair-union floor and the "
                "frozen complementary forest floor; S3=sum_C J(A,B,C)."
            ),
            "STATE_COHERENCE": (
                "Every frontier point is witnessed by one feasible exact type-count "
                "vector. Its cell incidences, outside-label frequency floor, S2, and "
                "S3 are carried together; no cross-state S2/S3 extrema are combined."
            ),
            "RESIDUAL_PAIR_FLOOR": (
                "For each type pair, reuse the exact r6 residual-intersection floor "
                "and outside-label slope; sum those inequalities, then apply the "
                "balanced 40-label frequency floor and ceil(mass/9)."
            ),
            "COMPLEMENTARY_FOREST_FLOOR": (
                "Reuse the frozen r5 good-count rows only as a complementary lower "
                "bound via max; the forest certificate is not recomputed."
            ),
            "TAIL": (
                "Every omitted vector has integer local loss greater than the census "
                "cutoff, so its bound is at most UNCORRECTED_R3_BOUND-cutoff-1."
            ),
            "PORTFOLIOS_ENUMERATED": "NO",
        },
        "SOLVER_STATUS": "NOT_USED_EXACT_FINITE_STATE_CENSUS",
        "SOLVER_CONFIGURED_WALL_LIMIT": "NOT_APPLICABLE",
        "SOLVER_ACTUAL_WALL_TIME": "NOT_APPLICABLE",
        "SOLVER_CERTIFIED_BOUND": None,
        "FOCUSED_TESTS": focused_tests,
        "RUFF": ruff,
        "PYRIGHT": pyright,
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


__all__ = [
    "BASE_HEAD",
    "BASE_TREE",
    "CURRENT_R3_BOUND",
    "JOINT_LOCAL_LOSS_CUTOFF",
    "TASK_BRANCH",
    "TASK_ID",
    "JointFrontierPoint",
    "JointResidualCensus",
    "ResidualJointState",
    "balanced_frequency_histogram",
    "family_a_result_record",
    "joint_residual_census",
    "pareto_s2_s3_pairs",
    "reused_exact_type_count_vectors",
]
