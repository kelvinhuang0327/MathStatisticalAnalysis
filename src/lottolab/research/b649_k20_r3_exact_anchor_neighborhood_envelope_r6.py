"""Exact type-count envelope for the K20 r_max=3 anchor neighborhood.

The proof enumerates dangerous count vectors of the existing 30 anchor types.
It lower-bounds all pairwise intersections of anchor-excluded outcome sets,
then uses label-frequency capacity to force additional outside-label reuse.
No ticket portfolios are generated, and no optimizer is used.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from itertools import product
from math import comb
from typing import Any

from lottolab.research.b649_k20_outside_min_s2_global_penalty_bound_r1 import (
    DRAW_SIZE,
    INCUMBENT,
    OUTRIGHT_MATCHES,
    POOL_SIZE,
    TICKET_COUNT,
    pair_intersection_count,
    triple_intersection_count,
)
from lottolab.research.b649_k20_r3_anchor_incidence_bound_r5 import (
    AnchorIncidenceProfile,
    anchor_incidence_profiles,
)

BASE_HEAD = "92f88afb2f98073bdb9612f1e002e2c1a20cc350"
TASK_BRANCH = "codex/b649-k20-r3-exact-anchor-neighborhood-envelope-r6"
CURRENT_R3_BOUND = 351_926_868
PREVIOUS_REDUCTION = 5_314_680
UNCORRECTED_R3_BOUND = 357_241_548
FROZEN_R4_BOUND = 354_779_928
FROZEN_R5_BOUND = 350_778_728
FROZEN_R6_BOUND = 343_869_728
OUTSIDE_LABEL_CAPACITY = 40
ANCHOR_CELL_LABEL_CAPACITIES = (3, 3, 3)
CELL_LABEL_CAPACITIES = (*ANCHOR_CELL_LABEL_CAPACITIES, OUTSIDE_LABEL_CAPACITY)
CELL_NAMES = ("shared", "a_only", "b_only", "outside")
PAIR_MULTIPLICITY_DIVISOR = (TICKET_COUNT - 2) // 2
OUTSIDE_PAIR_SLOPE = 1_036
CellCounts = tuple[int, int, int, int]

# Frozen rows from the already-certified r5 count-by-good-ticket tradeoff.
# They are used only as a complementary lower bound; this module does not
# recompute the weighted-forest certificate.
PRIOR_FOREST_PENALTY_BY_GOOD_COUNT = (
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    1_148_000,
    2_296_000,
    2_870_000,
    3_444_000,
    4_018_000,
    4_592_000,
    5_166_000,
    5_740_000,
    6_314_000,
    6_888_000,
    7_462_000,
    8_036_000,
)


@dataclass(frozen=True)
class TypePairCertificate:
    """Exact pair-neighborhood floor for two anchor-incidence types."""

    minimum_residual_intersection: int
    outside_slope: Fraction | None
    maximum_cell_overlap: tuple[int, int, int, int]
    overlap_pattern_count: int


@dataclass(frozen=True)
class TypeCountEnvelope:
    """A finite-census row and its certified recovery-reduction bound."""

    counts: tuple[int, ...]
    good_ticket_count: int
    local_recovery: int
    local_loss: int
    outside_label_incidence_count: int
    outside_label_pair_mass_floor: int
    pair_intersection_mass_floor: int
    pair_union_penalty: int
    prior_forest_penalty: int
    combined_pair_penalty: int
    total_recovery_reduction: int


def _profile_cells(profile: AnchorIncidenceProfile) -> CellCounts:
    return profile.shared, profile.a_only, profile.b_only, profile.outside


def _pair_capacity(counts: Sequence[int], left: int, right: int) -> int:
    if left == right:
        return comb(counts[left], 2)
    return counts[left] * counts[right]


def iter_type_count_vectors(
    local_losses: Sequence[int], ticket_count: int, loss_limit: int
) -> Iterator[tuple[int, ...]]:
    """Independently enumerate count vectors under an additive local-loss cap.

    ``local_losses[0]`` must be the unique zero-loss type. Counts for all
    other types are recursively generated; the zero-loss count fills the
    remaining ticket slots. This generator has no solver dependency.
    """

    if not local_losses or local_losses[0] != 0:
        raise ValueError("the first type must be the zero-loss anchor type")
    if any(loss <= 0 for loss in local_losses[1:]):
        raise ValueError("nonbaseline types must have positive local loss")
    if ticket_count < 0:
        raise ValueError("ticket_count must be nonnegative")
    if loss_limit < 0:
        return

    counts = [0] * len(local_losses)

    def visit(type_index: int, remaining: int, used_loss: int) -> Iterator[tuple[int, ...]]:
        if type_index == len(local_losses):
            counts[0] = remaining
            yield tuple(counts)
            counts[0] = 0
            return

        loss = local_losses[type_index]
        maximum = min(remaining, (loss_limit - used_loss) // loss)
        for amount in range(maximum + 1):
            counts[type_index] = amount
            yield from visit(type_index + 1, remaining - amount, used_loss + amount * loss)
        counts[type_index] = 0

    yield from visit(1, ticket_count, 0)


def local_losses(
    profiles: Sequence[AnchorIncidenceProfile] | None = None,
) -> tuple[int, ...]:
    """Return exact local recovery losses relative to the best anchor type."""

    selected = tuple(profiles) if profiles is not None else anchor_incidence_profiles()
    maximum = max(profile.net_recovery for profile in selected)
    best_indices = [
        index
        for index, profile in enumerate(selected)
        if profile.net_recovery == maximum
    ]
    if best_indices != [0]:
        raise AssertionError("the unique best anchor type must remain at index zero")
    return tuple(maximum - profile.net_recovery for profile in selected)


def candidate_type_count_vectors() -> tuple[tuple[int, ...], ...]:
    """Enumerate all vectors whose local loss could match the prior reduction."""

    return tuple(
        iter_type_count_vectors(local_losses(), TICKET_COUNT - 2, PREVIOUS_REDUCTION)
    )


def full_type_count_vector_count(
    type_count: int = 30, ticket_count: int = TICKET_COUNT - 2
) -> int:
    """Count the unrestricted nonnegative type-count simplex."""

    if type_count <= 0 or ticket_count < 0:
        raise ValueError("type_count must be positive and ticket_count nonnegative")
    return comb(ticket_count + type_count - 1, type_count - 1)


def balanced_pair_mass(total_incidence: int, label_count: int) -> int:
    """Minimum sum of ``binom(f_l, 2)`` over bounded label frequencies."""

    if total_incidence < 0 or label_count <= 0:
        raise ValueError("incidence total and label count must be valid")
    quotient, remainder = divmod(total_incidence, label_count)
    if quotient > TICKET_COUNT or (quotient == TICKET_COUNT and remainder > 0):
        raise ValueError("label frequency exceeds the outside-ticket count")
    return remainder * comb(quotient + 1, 2) + (label_count - remainder) * comb(quotient, 2)


@cache
def feasible_pair_overlap_vectors(
    left_index: int, right_index: int
) -> tuple[CellCounts, ...]:
    """Enumerate physically possible cell overlaps with total overlap at most 3."""

    if left_index > right_index:
        left_index, right_index = right_index, left_index
    profiles = anchor_incidence_profiles()
    if not (0 <= left_index < len(profiles) and 0 <= right_index < len(profiles)):
        raise IndexError("anchor-incidence type index is out of range")
    left = _profile_cells(profiles[left_index])
    right = _profile_cells(profiles[right_index])
    lower = tuple(
        max(0, left_count + right_count - labels)
        for left_count, right_count, labels in zip(
            left, right, CELL_LABEL_CAPACITIES, strict=True
        )
    )
    upper = tuple(
        min(left_count, right_count)
        for left_count, right_count in zip(left, right, strict=True)
    )
    if any(low > high for low, high in zip(lower, upper, strict=True)):
        return ()
    patterns: list[CellCounts] = []
    for generated in product(
        *(range(low, high + 1) for low, high in zip(lower, upper, strict=True))
    ):
        if sum(generated) <= 3:
            patterns.append((generated[0], generated[1], generated[2], generated[3]))
    return tuple(patterns)


def residual_pair_intersection_floor(
    left: AnchorIncidenceProfile,
    right: AnchorIncidenceProfile,
    overlap: CellCounts,
    *,
    pool_size: int = POOL_SIZE,
    draw_size: int = DRAW_SIZE,
    outright_matches: int = OUTRIGHT_MATCHES,
) -> int:
    """Lower-bound residual event intersection by subtracting both anchors."""

    total_overlap = sum(overlap)
    pair_events = pair_intersection_count(
        total_overlap,
        pool_size=pool_size,
        draw_size=draw_size,
        outright_matches=outright_matches,
    )
    left_a, right_a = left.shared + left.a_only, right.shared + right.a_only
    left_b, right_b = left.shared + left.b_only, right.shared + right.b_only
    anchor_a_events = triple_intersection_count(
        (left_a, right_a, total_overlap),
        overlap[0] + overlap[1],
        pool_size=pool_size,
        draw_size=draw_size,
        outright_matches=outright_matches,
    )
    anchor_b_events = triple_intersection_count(
        (left_b, right_b, total_overlap),
        overlap[0] + overlap[2],
        pool_size=pool_size,
        draw_size=draw_size,
        outright_matches=outright_matches,
    )
    return max(0, pair_events - anchor_a_events - anchor_b_events)


@cache
def type_pair_certificate(left_index: int, right_index: int) -> TypePairCertificate | None:
    """Return exact pair floors and an outside-label dual slope for two types."""

    if left_index > right_index:
        left_index, right_index = right_index, left_index
    profiles = anchor_incidence_profiles()
    overlaps = feasible_pair_overlap_vectors(left_index, right_index)
    if not overlaps:
        return None
    left, right = profiles[left_index], profiles[right_index]
    costs = tuple(
        (overlap, residual_pair_intersection_floor(left, right, overlap))
        for overlap in overlaps
    )
    minimum = min(cost for _, cost in costs)
    outside_slopes = tuple(
        Fraction(cost - minimum, overlap[3])
        for overlap, cost in costs
        if overlap[3] > 0
    )
    maximum = tuple(
        max(overlap[cell] for overlap in overlaps) for cell in range(4)
    )
    maximum_cell_overlap: CellCounts = (maximum[0], maximum[1], maximum[2], maximum[3])
    return TypePairCertificate(
        minimum_residual_intersection=minimum,
        outside_slope=min(outside_slopes) if outside_slopes else None,
        maximum_cell_overlap=maximum_cell_overlap,
        overlap_pattern_count=len(overlaps),
    )


def minimum_outside_pair_slope() -> Fraction:
    """Return the exact common slope over all 30 anchor-incidence types."""

    eligible = range(len(anchor_incidence_profiles()))
    slopes = tuple(
        certificate.outside_slope
        for left_index in eligible
        for right_index in eligible
        if left_index <= right_index
        if (certificate := type_pair_certificate(left_index, right_index)) is not None
        and certificate.outside_slope is not None
    )
    if not slopes:
        raise AssertionError("the type-pair table has no outside-label reuse patterns")
    return min(slopes)


def aggregate_count_vector_is_feasible(counts: Sequence[int]) -> bool:
    """Check necessary label-frequency and pair-overlap realizability constraints.

    The check is deliberately an aggregate relaxation: it never assigns full
    tickets. Every actual portfolio satisfies these constraints; relaxing
    cross-category edge consistency can only make the certified upper bound
    weaker, never exclude a feasible portfolio.
    """

    profiles = anchor_incidence_profiles()
    if len(counts) != len(profiles) or any(type(count) is not int or count < 0 for count in counts):
        return False
    if sum(counts) != TICKET_COUNT - 2:
        return False

    totals = tuple(
        sum(
            count * cell[cell_index]
            for count, cell in zip(
                counts, map(_profile_cells, profiles), strict=True
            )
        )
        for cell_index in range(4)
    )
    pair_mass_maxima = [0, 0, 0, 0]
    for left_index in range(len(profiles)):
        for right_index in range(left_index, len(profiles)):
            pair_count = _pair_capacity(counts, left_index, right_index)
            if pair_count == 0:
                continue
            certificate = type_pair_certificate(left_index, right_index)
            if certificate is None:
                return False
            for cell_index, maximum in enumerate(certificate.maximum_cell_overlap):
                pair_mass_maxima[cell_index] += pair_count * maximum

    for total, capacity, pair_maximum in zip(
        totals, CELL_LABEL_CAPACITIES, pair_mass_maxima, strict=True
    ):
        if total > capacity * (TICKET_COUNT - 2):
            return False
        if balanced_pair_mass(total, capacity) > pair_maximum:
            return False
    return True


def type_count_envelope(counts: Sequence[int]) -> TypeCountEnvelope:
    """Derive exact local recovery and a mandatory residual-pair correction."""

    profiles = anchor_incidence_profiles()
    vector = tuple(counts)
    if not aggregate_count_vector_is_feasible(vector):
        raise ValueError("type-count vector fails aggregate realizability constraints")
    if len(vector) != len(profiles):
        raise ValueError("type-count vector has the wrong dimension")

    losses = local_losses(profiles)
    local_recovery = sum(
        count * profile.net_recovery
        for count, profile in zip(vector, profiles, strict=True)
    )
    local_loss = sum(
        count * loss for count, loss in zip(vector, losses, strict=True)
    )
    outside_incidence_count = sum(
        count * profile.outside
        for count, profile in zip(vector, profiles, strict=True)
    )
    outside_pair_mass_floor = balanced_pair_mass(
        outside_incidence_count, OUTSIDE_LABEL_CAPACITY
    )

    pair_intersection_mass_floor = OUTSIDE_PAIR_SLOPE * outside_pair_mass_floor
    for left_index in range(len(profiles)):
        for right_index in range(left_index, len(profiles)):
            pair_count = _pair_capacity(vector, left_index, right_index)
            if pair_count == 0:
                continue
            certificate = type_pair_certificate(left_index, right_index)
            if certificate is None:
                raise AssertionError("a feasible count vector has an impossible type pair")
            pair_intersection_mass_floor += (
                pair_count * certificate.minimum_residual_intersection
            )

    if minimum_outside_pair_slope() != Fraction(OUTSIDE_PAIR_SLOPE, 1):
        raise AssertionError("the exact outside-label pair-cost slope changed")
    pair_union_penalty = (
        pair_intersection_mass_floor + PAIR_MULTIPLICITY_DIVISOR - 1
    ) // PAIR_MULTIPLICITY_DIVISOR
    good_ticket_count = vector[0]
    prior_penalty = PRIOR_FOREST_PENALTY_BY_GOOD_COUNT[good_ticket_count]
    combined_penalty = max(pair_union_penalty, prior_penalty)
    return TypeCountEnvelope(
        counts=vector,
        good_ticket_count=good_ticket_count,
        local_recovery=local_recovery,
        local_loss=local_loss,
        outside_label_incidence_count=outside_incidence_count,
        outside_label_pair_mass_floor=outside_pair_mass_floor,
        pair_intersection_mass_floor=pair_intersection_mass_floor,
        pair_union_penalty=pair_union_penalty,
        prior_forest_penalty=prior_penalty,
        combined_pair_penalty=combined_penalty,
        total_recovery_reduction=local_loss + combined_penalty,
    )


@cache
def dangerous_type_count_envelopes() -> tuple[TypeCountEnvelope, ...]:
    """Complete finite census of aggregate-feasible vectors under the old cutoff."""

    candidates = candidate_type_count_vectors()
    return tuple(
        type_count_envelope(counts)
        for counts in candidates
        if aggregate_count_vector_is_feasible(counts)
    )


@cache
def critical_type_count_envelope() -> TypeCountEnvelope:
    """Return the minimum-reduction row in the dangerous-vector census."""

    envelopes = dangerous_type_count_envelopes()
    if not envelopes:
        raise AssertionError("the dangerous type-count census is empty")
    return min(envelopes, key=lambda envelope: envelope.total_recovery_reduction)


@cache
def guaranteed_recovery_reduction() -> int:
    """Combine the complete danger census with the local-loss tail bound."""

    losses = local_losses()
    minimum_non_good_loss = min(loss for loss in losses if loss > 0)
    local_tail_floor = (
        PREVIOUS_REDUCTION // minimum_non_good_loss + 1
    ) * minimum_non_good_loss
    census_floor = critical_type_count_envelope().total_recovery_reduction
    if local_tail_floor != 5_757_570 or census_floor != 6_695_798:
        raise AssertionError("the certified anchor-neighborhood envelope changed")
    if any(
        envelope.total_recovery_reduction <= PREVIOUS_REDUCTION
        for envelope in dangerous_type_count_envelopes()
    ):
        raise AssertionError("a dangerous type-count vector remains below the prior reduction")
    return min(local_tail_floor, census_floor)


def revised_r3_bound() -> int:
    """Return the r=3 upper bound after the exact type-count envelope."""

    reduction = guaranteed_recovery_reduction()
    bound = UNCORRECTED_R3_BOUND - reduction
    if bound != 351_483_978 or bound >= CURRENT_R3_BOUND:
        raise AssertionError("the exact anchor-neighborhood bound failed to improve r=3")
    return bound


def family_a_result_record() -> dict[str, Any]:
    """Build the compact proof record and frozen Family-A handoff."""

    envelopes = dangerous_type_count_envelopes()
    critical = critical_type_count_envelope()
    r3_bound = revised_r3_bound()
    family_bound = max(r3_bound, FROZEN_R4_BOUND, FROZEN_R5_BOUND, FROZEN_R6_BOUND)
    return {
        "TASK_ID": "B649_K20_R3_EXACT_ANCHOR_NEIGHBORHOOD_ENVELOPE_R6",
        "TASK_STATUS": "CERTIFIED_R3_BOUND_TIGHTENED",
        "BASE_HEAD": BASE_HEAD,
        "TASK_BRANCH": TASK_BRANCH,
        "ANCHOR_INCIDENCE_TYPE_COUNT": len(anchor_incidence_profiles()),
        "TYPE_COUNT_VECTOR_COUNT": len(envelopes),
        "FULL_TYPE_COUNT_SIMPLEX_COUNT": full_type_count_vector_count(),
        "TYPE_COUNT_CENSUS_SCOPE": (
            "Complete census of aggregate-feasible 30-type vectors with local loss "
            "at most the previous 5314680 reduction; vectors outside this set are "
            "bounded by the local-loss tail."
        ),
        "DANGEROUS_VECTOR_COUNT": sum(
            envelope.total_recovery_reduction <= PREVIOUS_REDUCTION
            for envelope in envelopes
        ),
        "AGGREGATE_REALIZABILITY": {
            "CELL_LABEL_CAPACITIES": {
                "shared": 3,
                "a_only": 3,
                "b_only": 3,
                "outside": OUTSIDE_LABEL_CAPACITY,
            },
            "TICKET_SIZE": DRAW_SIZE,
            "MAXIMUM_PAIR_OVERLAP": 3,
            "PAIR_CELL_OVERLAP": (
                "Each cell overlap is bounded by the two type coordinates and its "
                "physical label capacity; only four-cell overlap vectors totaling "
                "at most 3 are admitted."
            ),
            "REPEATED_LABEL_CAPACITY": (
                "Each physical label has frequency 0..18; for each cell the "
                "balanced-frequency convex minimum is checked against the maximum "
                "pair mass admitted by the type-pair overlap vectors."
            ),
            "MODEL_SCOPE": (
                "Necessary aggregate realizability relaxation. Every actual ticket "
                "family maps into it; no complete ticket portfolios are constructed."
            ),
        },
        "LOCAL_LOSS_CUTOFF": PREVIOUS_REDUCTION,
        "OUTSIDE_PAIR_SLOPE": str(minimum_outside_pair_slope()),
        "CRITICAL_DANGEROUS_VECTOR": [
            [index, count] for index, count in enumerate(critical.counts) if count
        ],
        "CRITICAL_LOCAL_RECOVERY": critical.local_recovery,
        "CRITICAL_LOCAL_LOSS": critical.local_loss,
        "CRITICAL_OUTSIDE_LABEL_INCIDENCES": critical.outside_label_incidence_count,
        "CRITICAL_OUTSIDE_LABEL_PAIR_MASS_FLOOR": critical.outside_label_pair_mass_floor,
        "CRITICAL_PAIR_INTERSECTION_MASS_FLOOR": critical.pair_intersection_mass_floor,
        "MANDATORY_OUTSIDE_PAIR_PENALTY": critical.pair_union_penalty,
        "CRITICAL_PRIOR_FOREST_PENALTY": critical.prior_forest_penalty,
        "CRITICAL_TOTAL_RECOVERY_REDUCTION": critical.total_recovery_reduction,
        "LOCAL_TAIL_RECOVERY_REDUCTION_FLOOR": 5_757_570,
        "GUARANTEED_RECOVERY_REDUCTION": guaranteed_recovery_reduction(),
        "UNCORRECTED_R3_BOUND": UNCORRECTED_R3_BOUND,
        "R3_PROOF": {
            "LOCAL_RECOVERY": (
                "For type t=(s,a,b,o), net(t)=J((3,s+a,s+b),s)-I(s+a)-I(s+b); "
                "the count-vector local recovery is the exact sum of n_t*net(t)."
            ),
            "PAIR_RESIDUAL_FLOOR": (
                "For outside tickets C,D with four-cell common counts x and d=sum(x), "
                "|R_C intersect R_D| >= max(0,I(d)-J((u_C,u_D,d),x_shared+x_A)-"
                "J((v_C,v_D,d),x_shared+x_B))."
            ),
            "PAIR_DUAL": (
                "For each type pair beta is the exact minimum of the pair residual "
                "floor over physically allowed cell overlaps totaling at most 3; "
                "the complete 30-type table proves floor >= beta+1036*x_outside."
            ),
            "OUTSIDE_REUSE": (
                "Q_out=sum_l binom(f_l,2), with 0<=f_l<=18 and sum_l f_l equal to "
                "the outside incidence count. Convexity gives the balanced-frequency "
                "minimum over 40 labels."
            ),
            "PAIR_SUM_TO_UNION": (
                "For outcome multiplicity k<=18, binom(k,2)<=9*(k-1); therefore "
                "the residual union correction is at least ceil(pair_intersection_mass/9)."
            ),
            "COMPLEMENTARY_PRIOR_CERTIFICATE": (
                "The frozen r5 good-count penalty rows are reused only via max with "
                "the new pair-sum bound; the r5 weighted-forest computation is not rerun."
            ),
            "GLOBAL_ENVELOPE": (
                "The census minimum is 6695798. Every omitted vector has at least "
                "13 non-good tickets and local loss at least 5757570; hence the "
                "certified global reduction is 5757570."
            ),
        },
        "R3_BOUND": r3_bound,
        "R3_STATUS": "TIGHTENED_OPEN",
        "R4_BOUND": FROZEN_R4_BOUND,
        "R5_BOUND": FROZEN_R5_BOUND,
        "R6_BOUND": FROZEN_R6_BOUND,
        "FAMILY_A_RECOMPUTED_BOUND": family_bound,
        "FAMILY_A_BOTTLENECK_R": "R4",
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": family_bound - INCUMBENT,
        "SOLVER_STATUS": "NOT_USED_COMPLETE_FINITE_CENSUS",
        "SOLVER_CONFIGURED_WALL_LIMIT": "NOT_APPLICABLE",
        "SOLVER_ACTUAL_WALL_TIME": "NOT_APPLICABLE",
        "SOLVER_CERTIFIED_BOUND": None,
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "WORKTREE_DISPOSITION": "RETAIN",
    }


__all__ = [
    "BASE_HEAD",
    "OUTSIDE_PAIR_SLOPE",
    "PRIOR_FOREST_PENALTY_BY_GOOD_COUNT",
    "TASK_BRANCH",
    "TypeCountEnvelope",
    "aggregate_count_vector_is_feasible",
    "balanced_pair_mass",
    "candidate_type_count_vectors",
    "dangerous_type_count_envelopes",
    "family_a_result_record",
    "feasible_pair_overlap_vectors",
    "full_type_count_vector_count",
    "guaranteed_recovery_reduction",
    "iter_type_count_vectors",
    "local_losses",
    "minimum_outside_pair_slope",
    "residual_pair_intersection_floor",
    "revised_r3_bound",
    "type_count_envelope",
    "type_pair_certificate",
]
