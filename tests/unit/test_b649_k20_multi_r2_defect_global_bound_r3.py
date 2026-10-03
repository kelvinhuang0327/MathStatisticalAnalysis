"""Focused exhaustive and certificate checks for the multi-r2 K20 bound."""

from __future__ import annotations

from itertools import combinations, product

from lottolab.research.b649_k20_multi_r2_defect_global_bound_r3 import (
    classify_heavy_graph,
    decomposed_triple_profile_cap,
    defect_bound_certificates,
    pair_costs,
    s2_floor_for_heavy_count,
    triple_profile_cap,
)


def test_exact_pair_costs_and_heavy_count_s2_floors() -> None:
    assert pair_costs() == (
        107_800,
        574_000,
        1_695_988,
        3_469_942,
        6_224_512,
        10_776_332,
        18_611_432,
    )
    assert s2_floor_for_heavy_count(2) == 65_150_176
    assert s2_floor_for_heavy_count(3) == 65_805_964
    assert s2_floor_for_heavy_count(46) == 94_004_848
    assert s2_floor_for_heavy_count(47) == 95_126_836
    assert s2_floor_for_heavy_count(60) == 115_773_280
    assert s2_floor_for_heavy_count(190) == 322_237_720


def test_heavy_pair_graph_classification_covers_the_three_families() -> None:
    assert classify_heavy_graph(((0, 1), (1, 2))) == "TWO_SHARED_VERTEX"
    assert classify_heavy_graph(((0, 1), (2, 3))) == "TWO_DISJOINT"
    assert classify_heavy_graph(((0, 1), (1, 2), (2, 0))) == "THREE_OR_MORE_HEAVY_PAIRS"


def test_every_k4_overlap_coloring_matches_exact_triple_profile_caps() -> None:
    """Exhaust all 3^6 small graph edge colorings and their defect classes."""

    vertices = range(4)
    edges = tuple(combinations(vertices, 2))
    edge_indices = {edge: index for index, edge in enumerate(edges)}
    profile_states = (0, 1, 2)
    seen_families: set[str] = set()

    for edge_states in product(profile_states, repeat=len(edges)):
        heavy_edges = tuple(
            edge for edge, state in zip(edges, edge_states, strict=True) if state == 2
        )
        if len(heavy_edges) >= 2:
            seen_families.add(classify_heavy_graph(heavy_edges))

        for triple in combinations(vertices, 3):
            first, second, third = triple
            profile = (
                edge_states[edge_indices[(first, second)]],
                edge_states[edge_indices[(first, third)]],
                edge_states[edge_indices[(second, third)]],
            )
            assert decomposed_triple_profile_cap(profile) == triple_profile_cap(profile)

    assert seen_families == {
        "TWO_SHARED_VERTEX",
        "TWO_DISJOINT",
        "THREE_OR_MORE_HEAVY_PAIRS",
    }


def test_mass_93_and_mass_at_least_94_certificates_leave_one_residual_family() -> None:
    certificates = defect_bound_certificates()
    assert certificates["DEFECT_GRAPH_FAMILY_COUNT"] == 3
    assert certificates["SHARED_VERTEX_R2_BOUND"] == 311_724_888
    assert certificates["DISJOINT_R2_BOUND"] == 311_670_736
    assert certificates["MULTI_R2_BOUND"] == 357_794_343
    assert certificates["FAMILY_B_BOUND"] == 357_794_343
    assert certificates["FAMILY_B_STATUS"] == "BOUNDED_OPEN_RESIDUAL"
    assert certificates["UNRESOLVED_DEFECT_GRAPH"] == (
        "THREE_OR_MORE_HEAVY_PAIRS_WITH_OVERLAP_MASS_AT_LEAST_94"
    )
    assert certificates["CLOSED_DEFECT_FAMILIES"] == [
        "TWO_SHARED_VERTEX",
        "TWO_DISJOINT",
        "THREE_OR_MORE_AT_MASS_93",
    ]
    assert certificates["MULTI_MASS_93_WITNESS"]["upper_bound"] == 305_929_560
    assert certificates["S2_MINIMUMS"]["THREE_OR_MORE_MASS_AT_LEAST_94"] == 66_272_164
    assert certificates["MULTI_MASS_GE_94_WITNESS"]["heavy_pair_count"] == 3
    assert certificates["MULTI_MASS_GE_94_WITNESS"]["ordinary_edge_count"] == 88
    assert certificates["MULTI_MASS_GE_94_WITNESS"]["upper_bound"] < 357_906_542
    assert certificates["CP_SAT"]["STATUS"] == "NOT_RUN"
