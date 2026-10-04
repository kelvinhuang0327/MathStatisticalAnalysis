"""Resolve only the top tied K20 minimum-S2 envelope profiles.

The R5 ranking leaves five profiles at W=837 after its three hub-incidence
closures.  Four have concrete 22-triple/27-pair realizations below; the fifth
is impossible because its required triple-shadow degree sequence is not
graphical.  For every realizable profile, the full 49-support graph has 837
wedges and cannot be a union of cliques: fewer than thirteen tickets have
degree twelve.  Therefore at least one wedge is open, so at most 278 of the
279 possible graph triangles occur.  Removing the 22 core triangles gives
the common noncore-triangle cap 256.  Each Pasch-like four-support pattern
contains four loose three-cycles, and each loose cycle has at most one fourth
support that completes it to a Pasch.  Thus the Pasch count is at most 256 // 4.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import comb

from .b649_k20_min_s2_dangerous_core_realizability_r5 import (
    K20_REUSED_S4_LOWER_BOUND,
    K20DangerousProfileEnvelope,
    K20SupportMotifSignature,
    k20_min_s2_dangerous_core_certificate,
    rank_dangerous_profiles,
    validate_k20_support_realization,
)
from .b649_k20_min_s2_higher_order_closure_r2 import (
    K20_INCUMBENT,
    K20_S1,
    K20_S2,
    k20_min_s2_s4_lower_bound_certificate,
)
from .b649_k20_min_s2_realizable_core_class_bound_r4 import (
    K20_DOUBLE_SUPPORT_COUNT,
    K20_TICKET_CAPACITY,
    K20_TRIPLE_SUPPORT_COUNT,
    overlap_wedge_count,
    s3_sum_from_wedges_and_triangles,
)

type DegreeProfile = tuple[int, ...]
type Pair = tuple[int, int]
type Triple = tuple[int, int, int]

K20_R5_FAMILY_UPPER_BOUND = 313_753_880
K20_TOP_ENVELOPE_WEDGE_COUNT = 837
K20_TOP_PROFILE_COUNT = 5
K20_TOTAL_GRAPH_TRIANGLE_UPPER_BOUND = 278
K20_NONCORE_TRIANGLE_UPPER_BOUND = (
    K20_TOTAL_GRAPH_TRIANGLE_UPPER_BOUND - K20_TRIPLE_SUPPORT_COUNT
)
K20_PASCH_LIKE_FOUR_SUPPORT_UPPER_BOUND = K20_NONCORE_TRIANGLE_UPPER_BOUND // 4
K20_SOLVER_EXTERNAL_WALL_LIMIT_SECONDS = 90
K20_SOLVER_PER_PROFILE_WALL_LIMIT_SECONDS = 12

TOP_PROFILE_1: DegreeProfile = (6, 6, 6, 6, 6, 6, 6, 4, 4, 4, 4, 4, 4, 0, 0, 0, 0, 0, 0, 0)
TOP_PROFILE_2: DegreeProfile = (6, 6, 6, 6, 6, 6, 5, 5, 5, 4, 4, 4, 3, 0, 0, 0, 0, 0, 0, 0)
TOP_PROFILE_3: DegreeProfile = (6, 6, 6, 6, 6, 5, 5, 5, 5, 5, 5, 4, 1, 1, 0, 0, 0, 0, 0, 0)
TOP_PROFILE_4: DegreeProfile = (6, 6, 6, 6, 6, 5, 5, 5, 5, 5, 5, 3, 3, 0, 0, 0, 0, 0, 0, 0)
TOP_PROFILE_5: DegreeProfile = (6, 6, 6, 6, 5, 5, 5, 5, 5, 5, 5, 5, 2, 0, 0, 0, 0, 0, 0, 0)


@dataclass(frozen=True, slots=True)
class K20TopProfileResolution:
    """A witnessed full support realization or a degree-graph obstruction."""

    degree_sequence: DegreeProfile
    realizable: bool
    triple_supports: tuple[Triple, ...]
    double_supports: tuple[Pair, ...]


@dataclass(frozen=True, slots=True)
class K20ErdosGallaiViolation:
    """One exact failed simple-graph degree inequality."""

    prefix_size: int
    left_hand_side: int
    right_hand_side: int


@dataclass(frozen=True, slots=True)
class K20TopProfileMotifEnvelope:
    """Realizability and motif caps for one surviving top-envelope profile."""

    degree_sequence: DegreeProfile
    wedge_count: int
    shared_vertex_support_pair_count: int
    witness_motif_signature: K20SupportMotifSignature
    total_graph_triangle_upper_bound: int
    noncore_triangle_upper_bound: int
    loose_three_cycle_upper_bound: int
    pasch_like_four_support_upper_bound: int
    s3_upper_bound: int
    s4_lower_bound: int
    fourth_order_credit: int
    family_upper_bound: int


@dataclass(frozen=True, slots=True)
class K20TopEnvelopeCertificate:
    """Bounded exact resolution of the current highest K20 envelope class."""

    total_bounded_profile_count: int
    ranked_dangerous_profile_count: int
    exactly_analyzed_profile_count: int
    previously_closed_profile_count: int
    newly_closed_profile_count: int
    closed_dangerous_profile_count: int
    realizable_top_profile_count: int
    profile_resolutions: tuple[K20TopProfileResolution, ...]
    profile_motif_envelopes: tuple[K20TopProfileMotifEnvelope, ...]
    top_surviving_profiles: tuple[K20DangerousProfileEnvelope, ...]
    top_surviving_profile: DegreeProfile
    next_unprocessed_profile: DegreeProfile
    next_unprocessed_family_upper_bound: int
    noncore_triangle_upper_bound: int
    s3_upper_bound: int
    s4_lower_bound: int
    fourth_order_credit: int
    family_upper_bound: int
    incumbent: int
    remaining_family_gap: int
    family_status: str


_RESOLUTIONS: tuple[K20TopProfileResolution, ...] = (
    K20TopProfileResolution(
        degree_sequence=TOP_PROFILE_1,
        realizable=True,
        triple_supports=(
            (0, 1, 2),
            (0, 3, 9),
            (0, 4, 7),
            (0, 5, 8),
            (0, 6, 11),
            (0, 10, 12),
            (1, 3, 11),
            (1, 4, 12),
            (1, 5, 10),
            (1, 6, 7),
            (1, 8, 9),
            (2, 3, 12),
            (2, 4, 8),
            (2, 5, 9),
            (2, 6, 10),
            (2, 7, 11),
            (3, 4, 10),
            (3, 5, 7),
            (3, 6, 8),
            (4, 5, 11),
            (4, 6, 9),
            (5, 6, 12),
        ),
        double_supports=(
            (7, 14),
            (7, 18),
            (8, 17),
            (8, 18),
            (9, 16),
            (9, 18),
            (10, 13),
            (10, 19),
            (11, 15),
            (11, 18),
            (12, 13),
            (12, 14),
            (13, 14),
            (13, 15),
            (13, 16),
            (13, 19),
            (14, 15),
            (14, 16),
            (14, 17),
            (15, 16),
            (15, 17),
            (15, 19),
            (16, 17),
            (16, 19),
            (17, 18),
            (17, 19),
            (18, 19),
        ),
    ),
    K20TopProfileResolution(
        degree_sequence=TOP_PROFILE_2,
        realizable=True,
        triple_supports=(
            (0, 1, 10),
            (0, 2, 3),
            (0, 4, 11),
            (0, 5, 12),
            (0, 6, 7),
            (0, 8, 9),
            (1, 2, 11),
            (1, 3, 12),
            (1, 4, 9),
            (1, 5, 7),
            (1, 6, 8),
            (2, 4, 12),
            (2, 5, 9),
            (2, 6, 10),
            (2, 7, 8),
            (3, 4, 8),
            (3, 5, 10),
            (3, 6, 9),
            (3, 7, 11),
            (4, 5, 6),
            (4, 7, 10),
            (5, 8, 11),
        ),
        double_supports=(
            (6, 12),
            (7, 9),
            (8, 17),
            (9, 19),
            (10, 11),
            (10, 18),
            (11, 15),
            (12, 13),
            (12, 16),
            (13, 14),
            (13, 15),
            (13, 16),
            (13, 18),
            (13, 19),
            (14, 15),
            (14, 16),
            (14, 17),
            (14, 18),
            (14, 19),
            (15, 16),
            (15, 17),
            (15, 18),
            (16, 17),
            (16, 19),
            (17, 18),
            (17, 19),
            (18, 19),
        ),
    ),
    K20TopProfileResolution(
        degree_sequence=TOP_PROFILE_3,
        realizable=False,
        triple_supports=(),
        double_supports=(),
    ),
    K20TopProfileResolution(
        degree_sequence=TOP_PROFILE_4,
        realizable=True,
        triple_supports=(
            (0, 1, 12),
            (0, 2, 7),
            (0, 3, 11),
            (0, 4, 8),
            (0, 5, 10),
            (0, 6, 9),
            (1, 2, 3),
            (1, 4, 11),
            (1, 5, 6),
            (1, 7, 9),
            (1, 8, 10),
            (2, 4, 12),
            (2, 5, 11),
            (2, 6, 10),
            (2, 8, 9),
            (3, 4, 6),
            (3, 5, 9),
            (3, 7, 10),
            (3, 8, 12),
            (4, 5, 7),
            (4, 9, 10),
            (6, 7, 8),
        ),
        double_supports=(
            (5, 8),
            (6, 14),
            (7, 16),
            (9, 14),
            (10, 15),
            (11, 13),
            (11, 15),
            (11, 17),
            (12, 15),
            (12, 18),
            (12, 19),
            (13, 14),
            (13, 16),
            (13, 17),
            (13, 18),
            (13, 19),
            (14, 15),
            (14, 16),
            (14, 19),
            (15, 17),
            (15, 18),
            (16, 17),
            (16, 18),
            (16, 19),
            (17, 18),
            (17, 19),
            (18, 19),
        ),
    ),
    K20TopProfileResolution(
        degree_sequence=TOP_PROFILE_5,
        realizable=True,
        triple_supports=(
            (0, 1, 8),
            (0, 2, 12),
            (0, 3, 6),
            (0, 4, 9),
            (0, 5, 11),
            (0, 7, 10),
            (1, 2, 9),
            (1, 3, 12),
            (1, 4, 5),
            (1, 6, 10),
            (1, 7, 11),
            (2, 3, 5),
            (2, 4, 11),
            (2, 6, 7),
            (2, 8, 10),
            (3, 4, 7),
            (3, 8, 9),
            (3, 10, 11),
            (4, 6, 8),
            (5, 7, 8),
            (5, 9, 10),
            (6, 9, 11),
        ),
        double_supports=(
            (4, 12),
            (5, 6),
            (7, 19),
            (8, 11),
            (9, 19),
            (10, 14),
            (12, 15),
            (12, 16),
            (12, 17),
            (13, 14),
            (13, 15),
            (13, 16),
            (13, 17),
            (13, 18),
            (13, 19),
            (14, 15),
            (14, 16),
            (14, 18),
            (14, 19),
            (15, 16),
            (15, 17),
            (15, 18),
            (16, 17),
            (16, 18),
            (17, 18),
            (17, 19),
            (18, 19),
        ),
    ),
)


def erdos_gallai_first_violation(degrees: Sequence[int]) -> K20ErdosGallaiViolation | None:
    """Return the first failed Erdos-Gallai inequality for a simple graph."""

    values = tuple(degrees)
    if any(type(value) is not int for value in values):
        raise TypeError("degrees must contain only integers")
    vertex_count = len(values)
    if any(value < 0 or value >= vertex_count for value in values):
        raise ValueError("simple-graph degrees must lie between zero and n - 1")
    if sum(values) % 2:
        raise ValueError("Erdos-Gallai applies only to sequences with even degree sum")

    ordered = tuple(sorted(values, reverse=True))
    for prefix_size in range(1, vertex_count + 1):
        left_hand_side = sum(ordered[:prefix_size])
        right_hand_side = prefix_size * (prefix_size - 1) + sum(
            min(degree, prefix_size) for degree in ordered[prefix_size:]
        )
        if left_hand_side > right_hand_side:
            return K20ErdosGallaiViolation(prefix_size, left_hand_side, right_hand_side)
    return None


def triple_shadow_degree_sequence(degrees: Sequence[int]) -> DegreeProfile:
    """Return the required simple-graph degrees of the triple shadow."""

    return tuple(2 * degree for degree in degrees)


def shared_vertex_support_pair_count(degrees: Sequence[int]) -> int:
    """Count pairs of triple supports sharing one ticket, exactly by degrees."""

    values = tuple(degrees)
    return sum(comb(degree, 2) for degree in values)


def _validate_profile_resolutions() -> tuple[K20SupportMotifSignature, ...]:
    signatures: list[K20SupportMotifSignature] = []
    for resolution in _RESOLUTIONS:
        if resolution.degree_sequence == TOP_PROFILE_3:
            if resolution.realizable or resolution.triple_supports or resolution.double_supports:
                raise AssertionError("the non-graphical top profile cannot have a witness")
            continue
        if not resolution.realizable:
            raise AssertionError("each other top profile must carry a realization")
        signature = validate_k20_support_realization(
            resolution.triple_supports,
            resolution.double_supports,
            resolution.degree_sequence,
        )
        if len(resolution.double_supports) != K20_DOUBLE_SUPPORT_COUNT:
            raise AssertionError("the residual support witness must contain 27 pairs")
        signatures.append(signature)
    return tuple(signatures)


def k20_min_s2_top_envelope_certificate() -> K20TopEnvelopeCertificate:
    """Return the exact top-profile resolution and the strict family envelope."""

    previous = k20_min_s2_dangerous_core_certificate()
    ranked = rank_dangerous_profiles()
    top_profiles = previous.top_surviving_profiles
    top_sequences = tuple(profile.degree_sequence for profile in top_profiles)
    expected_top = tuple(item.degree_sequence for item in _RESOLUTIONS)
    if len(ranked) != 4_850 or len(top_profiles) != K20_TOP_PROFILE_COUNT:
        raise AssertionError("the certified K20 dangerous-profile census changed")
    if top_sequences != expected_top:
        raise AssertionError("the highest tied envelope profiles changed")
    if {profile.wedge_count for profile in top_profiles} != {K20_TOP_ENVELOPE_WEDGE_COUNT}:
        raise AssertionError("the top envelope must remain tied at W=837")
    if previous.family_upper_bound != K20_R5_FAMILY_UPPER_BOUND:
        raise AssertionError("the pinned R5 family envelope changed")

    signatures = _validate_profile_resolutions()
    infeasible_profile = TOP_PROFILE_3
    shadow_degrees = triple_shadow_degree_sequence(infeasible_profile)
    obstruction = erdos_gallai_first_violation(shadow_degrees)
    if obstruction != K20ErdosGallaiViolation(5, 60, 59):
        raise AssertionError("the top-profile shadow obstruction changed")
    if any(
        erdos_gallai_first_violation(triple_shadow_degree_sequence(profile)) is not None
        for profile in expected_top
        if profile != infeasible_profile
    ):
        raise AssertionError("a witnessed triple-shadow degree sequence is not graphical")

    motif_envelopes: list[K20TopProfileMotifEnvelope] = []
    signature_by_profile = {
        resolution.degree_sequence: signature
        for resolution, signature in zip(
            (item for item in _RESOLUTIONS if item.realizable), signatures, strict=True
        )
    }
    s4_certificate = k20_min_s2_s4_lower_bound_certificate()
    s4_lower_bound = s4_certificate.s4_lower_bound
    if s4_lower_bound != K20_REUSED_S4_LOWER_BOUND:
        raise AssertionError("the previously certified S4 floor changed")
    fourth_order_credit = (4 * s4_lower_bound) // 7

    for profile in expected_top:
        if profile == infeasible_profile:
            continue
        wedge_count = overlap_wedge_count(profile)
        degree_twelve_count = profile.count(K20_TICKET_CAPACITY)
        if degree_twelve_count >= K20_TICKET_CAPACITY * 2 + 1:
            raise AssertionError("a union of K13 cliques has not been excluded")
        if wedge_count != K20_TOP_ENVELOPE_WEDGE_COUNT or wedge_count % 3:
            raise AssertionError("the strict wedge-closure argument needs W=837")

        total_triangle_upper_bound = (wedge_count - 1) // 3
        noncore_triangle_upper_bound = (
            total_triangle_upper_bound - K20_TRIPLE_SUPPORT_COUNT
        )
        loose_three_cycle_upper_bound = noncore_triangle_upper_bound
        # A loose support 3-cycle determines at most one Pasch completion:
        # its fourth support must consist of the three private vertices.
        pasch_upper_bound = loose_three_cycle_upper_bound // 4
        shared_pairs = shared_vertex_support_pair_count(profile)
        signature = signature_by_profile[profile]
        if signature.shared_vertex_support_pair_count != shared_pairs:
            raise AssertionError("the exact shared-ticket support-pair count changed")
        if signature.loose_three_cycle_count != signature.noncore_shadow_triangle_count:
            raise AssertionError("the triple-shadow loose-cycle identity changed")

        s3_upper_bound = s3_sum_from_wedges_and_triangles(
            wedge_count,
            noncore_triangle_upper_bound,
        )
        family_upper_bound = K20_S1 - K20_S2 + s3_upper_bound - fourth_order_credit
        motif_envelopes.append(
            K20TopProfileMotifEnvelope(
                degree_sequence=profile,
                wedge_count=wedge_count,
                shared_vertex_support_pair_count=shared_pairs,
                witness_motif_signature=signature,
                total_graph_triangle_upper_bound=total_triangle_upper_bound,
                noncore_triangle_upper_bound=noncore_triangle_upper_bound,
                loose_three_cycle_upper_bound=loose_three_cycle_upper_bound,
                pasch_like_four_support_upper_bound=pasch_upper_bound,
                s3_upper_bound=s3_upper_bound,
                s4_lower_bound=s4_lower_bound,
                fourth_order_credit=fourth_order_credit,
                family_upper_bound=family_upper_bound,
            )
        )

    already_closed = set(previous.closed_dangerous_degree_sequences)
    resolved = already_closed | set(expected_top)
    unprocessed = tuple(profile for profile in ranked if profile.degree_sequence not in resolved)
    if not unprocessed:
        raise AssertionError("the profile ranking unexpectedly ended at the top class")
    next_profile = unprocessed[0]
    next_profile_upper_bound = next_profile.family_upper_bound
    if next_profile.wedge_count != 836 or next_profile_upper_bound != 313_739_208:
        raise AssertionError("the next ranked envelope changed")

    top_class_upper_bound = max(item.family_upper_bound for item in motif_envelopes)
    family_upper_bound = max(top_class_upper_bound, next_profile_upper_bound)
    remaining_gap = family_upper_bound - K20_INCUMBENT
    if family_upper_bound <= K20_INCUMBENT:
        family_status = "CLOSED"
        remaining_gap = 0
    elif family_upper_bound < K20_R5_FAMILY_UPPER_BOUND:
        family_status = "OPEN_STRICTLY_TIGHTENED"
    else:
        family_status = "OPEN"

    return K20TopEnvelopeCertificate(
        total_bounded_profile_count=previous.total_bounded_profile_count,
        ranked_dangerous_profile_count=len(ranked),
        exactly_analyzed_profile_count=len(top_profiles),
        previously_closed_profile_count=len(already_closed),
        newly_closed_profile_count=1,
        closed_dangerous_profile_count=len(already_closed) + 1,
        realizable_top_profile_count=len(motif_envelopes),
        profile_resolutions=_RESOLUTIONS,
        profile_motif_envelopes=tuple(motif_envelopes),
        top_surviving_profiles=top_profiles,
        top_surviving_profile=motif_envelopes[0].degree_sequence,
        next_unprocessed_profile=next_profile.degree_sequence,
        next_unprocessed_family_upper_bound=next_profile_upper_bound,
        noncore_triangle_upper_bound=K20_NONCORE_TRIANGLE_UPPER_BOUND,
        s3_upper_bound=motif_envelopes[0].s3_upper_bound,
        s4_lower_bound=s4_lower_bound,
        fourth_order_credit=fourth_order_credit,
        family_upper_bound=family_upper_bound,
        incumbent=K20_INCUMBENT,
        remaining_family_gap=remaining_gap,
        family_status=family_status,
    )


__all__ = [
    "TOP_PROFILE_1",
    "TOP_PROFILE_2",
    "TOP_PROFILE_3",
    "TOP_PROFILE_4",
    "TOP_PROFILE_5",
    "K20ErdosGallaiViolation",
    "K20TopEnvelopeCertificate",
    "K20TopProfileMotifEnvelope",
    "K20TopProfileResolution",
    "erdos_gallai_first_violation",
    "k20_min_s2_top_envelope_certificate",
    "shared_vertex_support_pair_count",
    "triple_shadow_degree_sequence",
]
