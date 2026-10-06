from __future__ import annotations

from itertools import combinations
from pathlib import Path
from typing import Any, cast

from ortools.sat.python import cp_model

from lottolab.research.b649_k20_r4_frontier_realizability_r11 import (
    overlap_components,
)
from lottolab.research.b649_k20_r4_threshold_descent_r13 import (
    NEW_R3_BOUND,
    OLD_R4_THRESHOLD,
    _add_dense_three_component_constraints,  # pyright: ignore[reportPrivateUsage]
    _special_ticket_degree_required,  # pyright: ignore[reportPrivateUsage]
    classify_threshold_frontier_states,
    maximum_edges_with_components,
    select_threshold_frontier_states,
)


def _fixed_graph_three_component_status(edges: set[tuple[int, int]]) -> int:
    cp_model_api = cast(Any, cp_model)
    model = cp_model_api.CpModel()
    edge_variables: dict[tuple[int, int], Any] = {
        edge: model.NewBoolVar(f"edge_{edge[0]}_{edge[1]}") for edge in combinations(range(18), 2)
    }
    for edge, variable in edge_variables.items():
        model.Add(variable == int(edge in edges))
    _add_dense_three_component_constraints(  # pyright: ignore[reportPrivateUsage]
        model,
        edge_variables,
        vertex_count=18,
        minimum_pair_mass=112,
    )
    solver = cp_model_api.CpSolver()
    solver.parameters.max_time_in_seconds = 2.0
    solver.parameters.num_search_workers = 1
    return solver.Solve(model)


def test_threshold_selection_reconstructs_exact_new_interval() -> None:
    root = Path(__file__).resolve().parents[2]
    selection = select_threshold_frontier_states(root)

    assert selection.generated_joint_state_count == 9_384
    assert selection.source_frontier_segment_count == 45
    assert selection.above_old_threshold_state_count == 174
    assert selection.at_or_below_new_threshold_state_count == 8_982
    assert len(selection.states) == 228
    assert selection.class_mass_count == 38
    assert len({row.state_id for row in selection.states}) == 228
    assert all(
        NEW_R3_BOUND < row.current_r4_envelope <= OLD_R4_THRESHOLD for row in selection.states
    )
    assert selection.states[0].state_id == "18_GOOD/components=1/outside_pair_mass=117"

    masses_by_realization = {
        label: tuple(
            row.outside_pair_mass
            for row in selection.states
            if row.realization == label and row.component_count == 1
        )
        for label in {
            "18_GOOD",
            "17_GOOD_PLUS_B_ONLY",
            "17_GOOD_PLUS_A_ONLY",
        }
    }
    assert masses_by_realization == {
        "18_GOOD": (117, 118, 119, 130, 131, 132, 142, 143, 144, 145, 154, 155),
        "17_GOOD_PLUS_B_ONLY": (
            112,
            113,
            114,
            124,
            125,
            126,
            136,
            137,
            138,
            148,
            149,
            150,
            151,
        ),
        "17_GOOD_PLUS_A_ONLY": (
            112,
            113,
            114,
            124,
            125,
            126,
            136,
            137,
            138,
            148,
            149,
            150,
            151,
        ),
    }


def test_dense_three_component_reduction_matches_graph_oracles() -> None:
    exactly_three = set(combinations(range(16), 2)) - {(0, 1), (2, 3), (4, 5)}
    exactly_two = set(combinations(range(17), 2))

    assert _fixed_graph_three_component_status(exactly_three) == cp_model.OPTIMAL
    assert _fixed_graph_three_component_status(exactly_two) == cp_model.INFEASIBLE

    support_rows = (
        (0, 1),
        (0, 1),
        (2, 3),
        (2, 3),
        (4, 5),
        (4, 5),
    )
    assert overlap_components(support_rows) == 3


def test_special_three_component_minimum_s2_exceeds_degree_cap() -> None:
    root = Path(__file__).resolve().parents[2]
    selection = select_threshold_frontier_states(root)
    special_three_component_states = tuple(
        row
        for row in selection.states
        if row.support_type == "17_GOOD_PLUS_SPECIAL"
        and row.component_count == 3
        and row.outside_pair_mass <= maximum_edges_with_components(18, 3)
    )

    assert len(special_three_component_states) == 6
    assert {
        row.outside_pair_mass for row in special_three_component_states
    } == {112, 113, 114}
    required_degrees = {
        _special_ticket_degree_required(row) for row in special_three_component_states
    }
    assert required_degrees == {17}
    assert all(degree is not None and degree > 18 - 3 for degree in required_degrees)


def test_affine_plane_witnesses_cover_good_dense_three_component_masses() -> None:
    root = Path(__file__).resolve().parents[2]
    selection = select_threshold_frontier_states(root)
    good_three_component_states = tuple(
        row
        for row in selection.states
        if row.support_type == "18_GOOD"
        and row.component_count == 3
        and row.outside_pair_mass <= maximum_edges_with_components(18, 3)
    )

    assert {row.outside_pair_mass for row in good_three_component_states} == {117, 118, 119}
    classifications = classify_threshold_frontier_states(good_three_component_states)
    assert len(classifications) == 3
    assert all(row.realizable for row in classifications)
    assert all(row.witness_sha256 is not None for row in classifications)
    assert all("affine-plane order-five" in row.classification_basis for row in classifications)
