"""Rank and prune only K20 minimum-S2 degree profiles above the incumbent.

The profile envelope reuses the exact S3-by-wedge identity from r4 and the
already certified ``S4 >= 112`` floor from the r2 triple-core proof.  The
resulting order-three Bonferroni credit is 64.  No aggregate S4 witness
counting is repeated here.

For a linear 3-uniform core, a ticket of triple degree six has six supports
and therefore twelve distinct support-neighbors.  If exactly thirteen
tickets have positive core degree, such a ticket must meet every other
positive-degree ticket.  With ``h`` degree-six tickets, any other active
ticket of degree ``d`` must then satisfy ``2*d >= h``.  This exact local
incidence obstruction excludes the highest three dangerous degree profiles.

The remaining degree-837 class is left as a realizability envelope.  Its
27 double supports are treated only as residual ticket degrees and a
necessary simple-graph capacity check.  The support motif oracle below records
loose cycles, shared-vertex intersections, shadow triangles, and Pasch-like
four-support configurations when an actual core realization is supplied.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations, groupby

from .b649_k20_min_s2_higher_order_closure_r2 import (
    K20_INCUMBENT,
    K20_S1,
    K20_S2,
    k20_min_s2_s4_lower_bound_certificate,
)
from .b649_k20_min_s2_realizable_core_class_bound_r4 import (
    K20_DOUBLE_SUPPORT_COUNT,
    K20_LABEL_COUNT,
    K20_TICKET_CAPACITY,
    K20_TICKET_COUNT,
    K20_TRIPLE_INCIDENCE_COUNT,
    K20_TRIPLE_SUPPORT_COUNT,
    bounded_nonincreasing_degree_sequences,
    linear_triple_degree_sequence_passes_pair_capacity,
    overlap_wedge_count,
    s3_upper_bound_from_wedges,
)

type DegreeProfile = tuple[int, ...]
type Pair = tuple[int, int]
type Triple = tuple[int, int, int]

K20_PREVIOUS_R4_FAMILY_UPPER_BOUND = 313_777_016
K20_REUSED_S4_LOWER_BOUND = 112


@dataclass(frozen=True, slots=True)
class K20DangerousProfileEnvelope:
    """Ranked third/fourth-order envelope for one degree multiset."""

    degree_sequence: DegreeProfile
    wedge_count: int
    noncore_triangle_upper_bound: int
    s3_upper_bound: int
    s4_lower_bound: int
    fourth_order_credit: int
    family_upper_bound: int


@dataclass(frozen=True, slots=True)
class K20CoreDegreeObstruction:
    """A local support-incidence contradiction for one degree profile."""

    degree_sequence: DegreeProfile
    reason: str
    active_ticket_count: int
    degree_six_ticket_count: int
    minimum_active_degree: int
    required_minimum_active_degree: int


@dataclass(frozen=True, slots=True)
class K20DangerousCoreCertificate:
    """Dangerous-profile ranking and the first surviving envelope class."""

    total_bounded_profile_count: int
    pair_capacity_compatible_profile_count: int
    residual_capacity_compatible_profile_count: int
    dangerous_profile_count: int
    incumbent_s3_threshold_exclusive: int
    s4_lower_bound_reused: int
    fourth_order_credit: int
    closed_dangerous_degree_sequences: tuple[DegreeProfile, ...]
    top_surviving_profiles: tuple[K20DangerousProfileEnvelope, ...]
    s3_upper_bound: int
    family_upper_bound: int
    incumbent: int
    remaining_family_gap: int
    family_status: str


@dataclass(frozen=True, slots=True)
class K20SupportMotifSignature:
    """Motif counts induced by a supplied linear triple-support system."""

    triple_support_count: int
    shadow_triangle_count: int
    noncore_shadow_triangle_count: int
    shared_vertex_support_pair_count: int
    loose_three_cycle_count: int
    pasch_like_four_support_count: int


def _validated_degree_profile(degrees: Sequence[int]) -> DegreeProfile:
    values = tuple(degrees)
    if len(values) != K20_TICKET_COUNT:
        raise ValueError(f"K20 profiles must contain {K20_TICKET_COUNT} degrees")
    if any(type(value) is not int for value in values):
        raise TypeError("degrees must contain only integers")
    if any(not 0 <= value <= K20_TICKET_CAPACITY for value in values):
        raise ValueError("triple degrees must lie between zero and ticket capacity")
    if sum(values) != K20_TRIPLE_INCIDENCE_COUNT:
        raise ValueError("triple degrees must sum to 66")
    return tuple(sorted(values, reverse=True))


def residual_double_ticket_degrees(degrees: Sequence[int]) -> DegreeProfile:
    """Return the per-ticket residual degrees for the 27 size-two supports."""

    profile = _validated_degree_profile(degrees)
    residual = tuple(K20_TICKET_CAPACITY - degree for degree in profile)
    if sum(residual) != 2 * K20_DOUBLE_SUPPORT_COUNT:
        raise AssertionError("the residual double-support incidence total changed")
    return residual


def simple_graph_degree_sequence_is_graphical(degrees: Sequence[int]) -> bool:
    """Check the Erdos-Gallai criterion for a residual simple support graph."""

    values = tuple(degrees)
    if any(type(value) is not int for value in values):
        raise TypeError("graph degrees must contain only integers")
    if any(value < 0 for value in values):
        raise ValueError("graph degrees must be non-negative")
    vertex_count = len(values)
    if any(value >= vertex_count for value in values):
        return False
    if sum(values) % 2:
        return False

    ordered = tuple(sorted(values, reverse=True))
    prefix_sum = 0
    for index, degree in enumerate(ordered, start=1):
        prefix_sum += degree
        right_hand_side = index * (index - 1) + sum(
            min(tail_degree, index) for tail_degree in ordered[index:]
        )
        if prefix_sum > right_hand_side:
            return False
    return True


def linear_triple_profile_obstruction(
    degrees: Sequence[int],
) -> K20CoreDegreeObstruction | None:
    """Return a certified degree-six incidence obstruction, if one applies.

    The profile must already pass the existing necessary pair-capacity checks.
    The argument uses only 3-uniform incidence, distinct ticket pairs, and
    ticket degrees; size-two supports cannot repair a failed triple core.
    """

    profile = _validated_degree_profile(degrees)
    if not linear_triple_degree_sequence_passes_pair_capacity(profile, K20_TRIPLE_SUPPORT_COUNT):
        return K20CoreDegreeObstruction(
            degree_sequence=profile,
            reason="TRIPLE_PAIR_CAPACITY_FAILURE",
            active_ticket_count=sum(value > 0 for value in profile),
            degree_six_ticket_count=profile.count(K20_TICKET_CAPACITY),
            minimum_active_degree=min((value for value in profile if value > 0), default=0),
            required_minimum_active_degree=0,
        )

    active = tuple(value for value in profile if value > 0)
    high_degree_count = profile.count(K20_TICKET_CAPACITY)
    if high_degree_count == 0:
        return None

    if len(active) < K20_TICKET_CAPACITY * 2 + 1:
        return K20CoreDegreeObstruction(
            degree_sequence=profile,
            reason="DEGREE_SIX_NEEDS_TWELVE_DISTINCT_ACTIVE_NEIGHBORS",
            active_ticket_count=len(active),
            degree_six_ticket_count=high_degree_count,
            minimum_active_degree=min(active),
            required_minimum_active_degree=0,
        )
    if len(active) != K20_TICKET_CAPACITY * 2 + 1:
        return None

    required_minimum = (high_degree_count + 1) // 2
    minimum_active_degree = min(active)
    if minimum_active_degree < required_minimum:
        return K20CoreDegreeObstruction(
            degree_sequence=profile,
            reason="DEGREE_SIX_HUB_COVER_REQUIREMENT",
            active_ticket_count=len(active),
            degree_six_ticket_count=high_degree_count,
            minimum_active_degree=minimum_active_degree,
            required_minimum_active_degree=required_minimum,
        )
    return None


def _normalized_linear_supports(
    supports: Sequence[Sequence[int]],
) -> tuple[tuple[Triple, ...], frozenset[Pair]]:
    normalized: list[Triple] = []
    used_pairs: set[Pair] = set()
    seen_triples: set[Triple] = set()
    for support in supports:
        values = tuple(support)
        if len(values) != 3:
            raise ValueError("every triple support must contain exactly three tickets")
        if any(type(value) is not int for value in values):
            raise TypeError("support ticket identifiers must be integers")
        if len(set(values)) != 3:
            raise ValueError("a triple support cannot repeat a ticket")
        ordered_values = sorted(values)
        triple: Triple = (ordered_values[0], ordered_values[1], ordered_values[2])
        if triple in seen_triples:
            raise ValueError("triple supports must be distinct")
        seen_triples.add(triple)
        for pair_values in combinations(triple, 2):
            pair: Pair = (pair_values[0], pair_values[1])
            if pair in used_pairs:
                raise ValueError("triple supports violate pair capacity <= 1")
            used_pairs.add(pair)
        normalized.append(triple)
    return tuple(normalized), frozenset(used_pairs)


def support_motif_signature(supports: Sequence[Sequence[int]]) -> K20SupportMotifSignature:
    """Count shadow triangles and small motifs in a supplied linear 3-graph."""

    triples, shadow_edges = _normalized_linear_supports(supports)
    support_sets = tuple(frozenset(triple) for triple in triples)
    vertices = tuple(sorted({vertex for triple in triples for vertex in triple}))

    shadow_triangle_count = sum(
        all(tuple(pair) in shadow_edges for pair in combinations(triangle, 2))
        for triangle in combinations(vertices, 3)
    )
    shared_vertex_pairs = 0
    for first, second in combinations(support_sets, 2):
        shared_vertex_pairs += len(first.intersection(second)) == 1

    loose_three_cycles = 0
    for first, second, third in combinations(support_sets, 3):
        intersections = (
            first.intersection(second),
            second.intersection(third),
            third.intersection(first),
        )
        if all(len(intersection) == 1 for intersection in intersections):
            shared_vertices = tuple(next(iter(intersection)) for intersection in intersections)
            loose_three_cycles += len(set(shared_vertices)) == 3

    pasch_like_four_supports = 0
    for four_supports in combinations(support_sets, 4):
        vertex_counts = Counter(vertex for support in four_supports for vertex in support)
        if len(vertex_counts) != 6 or any(count != 2 for count in vertex_counts.values()):
            continue
        if all(
            len(first.intersection(second)) == 1 for first, second in combinations(four_supports, 2)
        ):
            pasch_like_four_supports += 1

    return K20SupportMotifSignature(
        triple_support_count=len(triples),
        shadow_triangle_count=shadow_triangle_count,
        noncore_shadow_triangle_count=shadow_triangle_count - len(triples),
        shared_vertex_support_pair_count=shared_vertex_pairs,
        loose_three_cycle_count=loose_three_cycles,
        pasch_like_four_support_count=pasch_like_four_supports,
    )


def validate_k20_support_realization(
    triple_supports: Sequence[Sequence[int]],
    double_supports: Sequence[Sequence[int]],
    expected_triple_degrees: Sequence[int],
) -> K20SupportMotifSignature:
    """Validate a 22-triple/27-double K20 support realization.

    Double supports are checked only as residual ticket and pair capacities:
    they must be distinct unused pairs and bring each ticket to capacity six.
    """

    triple_count = tuple(triple_supports)
    double_pairs = tuple(tuple(pair) for pair in double_supports)
    if len(triple_count) != K20_TRIPLE_SUPPORT_COUNT:
        raise ValueError("a K20 core must contain exactly 22 triple supports")
    if len(double_pairs) != K20_DOUBLE_SUPPORT_COUNT:
        raise ValueError("a K20 residual system must contain exactly 27 double supports")
    if len(triple_count) + len(double_pairs) != K20_LABEL_COUNT:
        raise AssertionError("the K20 support partition must contain exactly 49 labels")
    expected = tuple(expected_triple_degrees)
    if len(expected) != K20_TICKET_COUNT:
        raise ValueError(f"K20 profiles must contain {K20_TICKET_COUNT} degrees")
    if any(type(value) is not int for value in expected):
        raise TypeError("expected_triple_degrees must contain only integers")
    if any(not 0 <= value <= K20_TICKET_CAPACITY for value in expected):
        raise ValueError("triple degrees must lie between zero and ticket capacity")
    if sum(expected) != K20_TRIPLE_INCIDENCE_COUNT:
        raise ValueError("triple degrees must sum to 66")

    triples, used_pairs = _normalized_linear_supports(triple_count)
    triple_degrees = [0] * K20_TICKET_COUNT
    for triple in triples:
        if any(not 0 <= ticket < K20_TICKET_COUNT for ticket in triple):
            raise ValueError("ticket identifiers must lie between 0 and 19")
        for ticket in triple:
            triple_degrees[ticket] += 1
    if tuple(triple_degrees) != expected:
        raise ValueError("triple supports do not realize the requested degree sequence")

    double_degrees = [0] * K20_TICKET_COUNT
    seen_double_pairs: set[Pair] = set()
    for pair_values in double_pairs:
        if len(pair_values) != 2:
            raise ValueError("every double support must contain exactly two tickets")
        if any(type(value) is not int for value in pair_values):
            raise TypeError("support ticket identifiers must be integers")
        if pair_values[0] == pair_values[1]:
            raise ValueError("a double support cannot repeat a ticket")
        ordered_pair = tuple(sorted(pair_values))
        pair: Pair = (ordered_pair[0], ordered_pair[1])
        if any(not 0 <= ticket < K20_TICKET_COUNT for ticket in pair):
            raise ValueError("ticket identifiers must lie between 0 and 19")
        if pair in seen_double_pairs:
            raise ValueError("double supports must be distinct")
        if pair in used_pairs:
            raise ValueError("a double support cannot reuse a core ticket pair")
        seen_double_pairs.add(pair)
        double_degrees[pair[0]] += 1
        double_degrees[pair[1]] += 1

    if any(
        triple_degree + double_degree != K20_TICKET_CAPACITY
        for triple_degree, double_degree in zip(triple_degrees, double_degrees, strict=True)
    ):
        raise ValueError("triple and residual double supports must fill each ticket to six")
    return support_motif_signature(triples)


def _dangerous_profile_inventory() -> tuple[
    int,
    int,
    int,
    int,
    tuple[K20DangerousProfileEnvelope, ...],
]:
    # r4 reports only aggregate maxima, so regenerate its bounded list to rank
    # the 4,850 survivor envelopes deterministically.
    profiles = bounded_nonincreasing_degree_sequences(
        K20_TRIPLE_INCIDENCE_COUNT,
        K20_TICKET_COUNT,
        K20_TICKET_CAPACITY,
    )
    pair_capacity_profiles = tuple(
        profile
        for profile in profiles
        if linear_triple_degree_sequence_passes_pair_capacity(profile, K20_TRIPLE_SUPPORT_COUNT)
    )

    s4_lower_bound = k20_min_s2_s4_lower_bound_certificate().s4_lower_bound
    if s4_lower_bound != K20_REUSED_S4_LOWER_BOUND:
        raise AssertionError("the previously certified K20 S4 floor changed")
    fourth_order_credit = (4 * s4_lower_bound) // 7
    incumbent_s3_threshold = K20_INCUMBENT - (K20_S1 - K20_S2) + fourth_order_credit

    residual_capacity_profiles: list[DegreeProfile] = []
    dangerous: list[K20DangerousProfileEnvelope] = []
    for profile in pair_capacity_profiles:
        residual_degrees = residual_double_ticket_degrees(profile)
        if not simple_graph_degree_sequence_is_graphical(residual_degrees):
            continue
        residual_capacity_profiles.append(profile)
        wedge_count = overlap_wedge_count(profile)
        triangle_bound, s3_upper_bound = s3_upper_bound_from_wedges(wedge_count)
        family_upper_bound = K20_S1 - K20_S2 + s3_upper_bound - fourth_order_credit
        if s3_upper_bound <= incumbent_s3_threshold:
            continue
        dangerous.append(
            K20DangerousProfileEnvelope(
                degree_sequence=profile,
                wedge_count=wedge_count,
                noncore_triangle_upper_bound=triangle_bound,
                s3_upper_bound=s3_upper_bound,
                s4_lower_bound=s4_lower_bound,
                fourth_order_credit=fourth_order_credit,
                family_upper_bound=family_upper_bound,
            )
        )

    dangerous.sort(
        key=lambda envelope: (
            envelope.family_upper_bound,
            envelope.s3_upper_bound,
            envelope.wedge_count,
            envelope.degree_sequence,
        ),
        reverse=True,
    )
    return (
        len(profiles),
        len(pair_capacity_profiles),
        len(residual_capacity_profiles),
        incumbent_s3_threshold,
        tuple(dangerous),
    )


def rank_dangerous_profiles() -> tuple[K20DangerousProfileEnvelope, ...]:
    """Return only profiles whose current corrected envelope beats incumbent."""

    return _dangerous_profile_inventory()[4]


def k20_min_s2_dangerous_core_certificate() -> K20DangerousCoreCertificate:
    """Close top degree-impossible profiles and retain the first open class."""

    (
        total_profile_count,
        pair_capacity_count,
        residual_capacity_count,
        incumbent_s3_threshold,
        dangerous,
    ) = _dangerous_profile_inventory()
    if not dangerous:
        raise AssertionError("the K20 dangerous-profile set unexpectedly became empty")
    if K20_S1 - K20_S2 + dangerous[0].s3_upper_bound != K20_PREVIOUS_R4_FAMILY_UPPER_BOUND:
        raise AssertionError("the pinned r4 family envelope changed")

    closed: list[DegreeProfile] = []
    top_survivors: tuple[K20DangerousProfileEnvelope, ...] = ()
    for _, grouped in groupby(dangerous, key=lambda envelope: envelope.family_upper_bound):
        envelope_group = tuple(grouped)
        survivors: list[K20DangerousProfileEnvelope] = []
        for envelope in envelope_group:
            obstruction = linear_triple_profile_obstruction(envelope.degree_sequence)
            if obstruction is None:
                survivors.append(envelope)
            else:
                closed.append(envelope.degree_sequence)
        if survivors:
            top_survivors = tuple(survivors)
            break

    if not top_survivors:
        family_upper_bound = K20_INCUMBENT
        s3_upper_bound = incumbent_s3_threshold
        family_status = "CLOSED"
        remaining_gap = 0
    else:
        family_upper_bound = top_survivors[0].family_upper_bound
        s3_upper_bound = top_survivors[0].s3_upper_bound
        if family_upper_bound <= K20_INCUMBENT:
            family_status = "CLOSED"
            remaining_gap = 0
        elif family_upper_bound < K20_PREVIOUS_R4_FAMILY_UPPER_BOUND:
            family_status = "OPEN_STRICTLY_TIGHTENED"
            remaining_gap = family_upper_bound - K20_INCUMBENT
        else:
            family_status = "OPEN"
            remaining_gap = family_upper_bound - K20_INCUMBENT

    credit = dangerous[0].fourth_order_credit
    return K20DangerousCoreCertificate(
        total_bounded_profile_count=total_profile_count,
        pair_capacity_compatible_profile_count=pair_capacity_count,
        residual_capacity_compatible_profile_count=residual_capacity_count,
        dangerous_profile_count=len(dangerous),
        incumbent_s3_threshold_exclusive=incumbent_s3_threshold,
        s4_lower_bound_reused=dangerous[0].s4_lower_bound,
        fourth_order_credit=credit,
        closed_dangerous_degree_sequences=tuple(closed),
        top_surviving_profiles=top_survivors,
        s3_upper_bound=s3_upper_bound,
        family_upper_bound=family_upper_bound,
        incumbent=K20_INCUMBENT,
        remaining_family_gap=remaining_gap,
        family_status=family_status,
    )


__all__ = [
    "K20_PREVIOUS_R4_FAMILY_UPPER_BOUND",
    "K20_REUSED_S4_LOWER_BOUND",
    "K20CoreDegreeObstruction",
    "K20DangerousCoreCertificate",
    "K20DangerousProfileEnvelope",
    "K20SupportMotifSignature",
    "k20_min_s2_dangerous_core_certificate",
    "linear_triple_profile_obstruction",
    "rank_dangerous_profiles",
    "residual_double_ticket_degrees",
    "simple_graph_degree_sequence_is_graphical",
    "support_motif_signature",
    "validate_k20_support_realization",
]
