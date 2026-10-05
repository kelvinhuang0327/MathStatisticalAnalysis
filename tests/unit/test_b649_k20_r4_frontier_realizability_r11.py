from __future__ import annotations

from itertools import product
from math import comb
from pathlib import Path

import pytest

from lottolab.research.b649_k20_r4_frontier_realizability_r11 import (
    GOOD_SIGNATURE,
    SPECIAL_147_WITNESS,
    SUPPORT_TYPE_GOOD,
    SUPPORT_TYPE_SPECIAL,
    SupportFeasibilityModel,
    certified_s3_upper_bound,
    certify_m153_higher_order,
    direct_full_s3_moment_from_support,
    enumerate_m153_frequency_histograms,
    frequency_pair_histogram_minimum,
    full_s3_moment_from_support,
    has_ticket_frequency_profile_decomposition,
    maximum_edges_with_components,
    maximum_triangles_for_pair_mass,
    maximum_wedges_for_pair_mass,
    overlap_components,
    residual_four_intersection_count,
    residual_triple_intersection_count,
    select_dangerous_frontier_states,
    ticket_frequency_profile_decompositions,
)


def test_dangerous_state_selection_reproduces_pinned_r10_threshold() -> None:
    root = Path(__file__).resolve().parents[2]
    selection = select_dangerous_frontier_states(root)

    assert selection.generated_joint_state_count == 9_384
    assert selection.source_frontier_segment_count == 45
    assert len(selection.states) == 174
    assert all(state.current_r4_envelope > 350_778_728 for state in selection.states)

    masses_by_realization = {
        label: {state.outside_pair_mass for state in selection.states if state.realization == label}
        for label in {state.realization for state in selection.states}
    }
    assert sorted(map(len, masses_by_realization.values())) == [9, 9, 11]
    assert len(masses_by_realization) == 3
    assert len({(state.realization, state.outside_pair_mass) for state in selection.states}) == 29


def test_component_edge_extrema_and_graph_moment_bounds_are_exact() -> None:
    assert maximum_edges_with_components(18, 1) == 153
    assert maximum_edges_with_components(18, 2) == 136
    assert maximum_edges_with_components(18, 3) == 120

    # K4 has six edges, twelve wedges, and four triangles.
    assert maximum_wedges_for_pair_mass(6, vertex_count=4) == 12
    assert maximum_triangles_for_pair_mass(6) == 4
    assert certified_s3_upper_bound(121, 107) > 0


def test_frequency_histogram_dp_matches_small_exhaustive_oracle() -> None:
    frequencies = range(7)
    cases = {
        (sum(row), sum(comb(value, 2) for value in row)) for row in product(frequencies, repeat=3)
    }
    for incidences, pair_mass in cases:
        expected = min(
            sum(comb(value, 3) for value in row)
            for row in product(frequencies, repeat=3)
            if sum(row) == incidences and sum(comb(value, 2) for value in row) == pair_mass
        )
        assert frequency_pair_histogram_minimum(3, incidences, pair_mass) == expected


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        (
            (
                (0, 1, 2, 3, 4, 5),
                (0, 6, 7, 8, 9, 10),
                (1, 6, 11, 12, 13, 14),
                (2, 7, 11, 15, 16, 17),
            ),
            81_088,
        ),
        (
            (
                (0, 1, 2, 3, 4, 5),
                (0, 6, 7, 8, 9, 10),
                (0, 11, 12, 13, 14, 15),
            ),
            7_000,
        ),
    ],
)
def test_realized_support_moments_match_direct_triple_oracle(
    rows: tuple[tuple[int, ...], ...], expected: int
) -> None:
    assert full_s3_moment_from_support(rows) == expected
    assert direct_full_s3_moment_from_support(rows) == expected
    assert overlap_components(rows) == 1


def test_residual_triple_oracle_handles_anchor_rescue_cells() -> None:
    assert (
        residual_triple_intersection_count(
            (GOOD_SIGNATURE, GOOD_SIGNATURE, GOOD_SIGNATURE),
            (1, 1, 1),
            0,
        )
        == 20_272
    )


def test_residual_four_oracle_distinguishes_compatible_support_profiles() -> None:
    no_common_triple = (
        (0, 1, 2, 3, 4, 5),
        (0, 6, 7, 8, 9, 10),
        (1, 6, 11, 12, 13, 14),
        (2, 7, 11, 15, 16, 17),
    )
    one_common_triple = (
        (0, 1, 2, 3, 4, 5),
        (0, 6, 7, 8, 9, 10),
        (0, 11, 12, 13, 14, 15),
        (1, 6, 11, 16, 17, 18),
    )
    common_four = (
        (0, 1, 2, 3, 4, 5),
        (0, 6, 7, 8, 9, 10),
        (0, 11, 12, 13, 14, 15),
        (0, 16, 17, 18, 19, 20),
    )

    assert tuple(
        residual_four_intersection_count(rows)
        for rows in (no_common_triple, one_common_triple, common_four)
    ) == (679, 448, 0)


def test_exact_m153_histogram_and_higher_order_certificate() -> None:
    histograms = enumerate_m153_frequency_histograms()
    below_100 = tuple(row for row in histograms if row.h_value < 100)
    at_100 = tuple(row for row in histograms if row.h_value == 100)
    assert len(below_100) == 4
    assert sum(has_ticket_frequency_profile_decomposition(row) for row in below_100) == 1
    assert len(at_100) == 2
    assert sum(has_ticket_frequency_profile_decomposition(row) for row in at_100) == 1
    unique_below_100 = next(
        row for row in below_100 if has_ticket_frequency_profile_decomposition(row)
    )
    assert len(ticket_frequency_profile_decompositions(unique_below_100)) == 3

    certificate = certify_m153_higher_order()
    assert certificate.s3_max == 15_214_752
    assert certificate.h_min == 100
    assert certificate.h_le_99_profile_decomposition_count == 3
    assert certificate.g_min == 28
    assert certificate.s4_profile_counts == (1_644, 1_388, 28)
    assert certificate.s4_min == 1_738_100


def test_exact_incidence_model_returns_a_verified_frontier_witness() -> None:
    root = Path(__file__).resolve().parents[2]
    selection = select_dangerous_frontier_states(root)
    state = next(
        row
        for row in selection.states
        if row.support_type == SUPPORT_TYPE_GOOD
        and row.outside_pair_mass == 126
        and row.component_count == 1
    )
    model = SupportFeasibilityModel(selection.states, SUPPORT_TYPE_GOOD)
    model.solver.parameters.max_time_in_seconds = 8.0

    realizable, witness = model.classify(state)

    assert realizable
    assert witness is not None


def test_high_mass_special_frontier_has_a_pinned_realization_witness() -> None:
    root = Path(__file__).resolve().parents[2]
    selection = select_dangerous_frontier_states(root)
    state = next(
        row
        for row in selection.states
        if row.support_type == SUPPORT_TYPE_SPECIAL
        and row.realization.endswith("A_ONLY")
        and row.outside_pair_mass == 147
        and row.component_count == 1
    )
    model = SupportFeasibilityModel(selection.states, SUPPORT_TYPE_SPECIAL)

    realizable, witness = model.classify(state)

    assert realizable
    assert witness == "f2d5b3587c67531cdc2b54ad03ae4fe41477ad76bcaa58a5b140a96055d46c2a"
    assert tuple(map(len, SPECIAL_147_WITNESS)) == (6,) * 17 + (5,)
