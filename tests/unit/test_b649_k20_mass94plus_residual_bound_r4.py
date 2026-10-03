"""Focused checks for the K20 Family-B mass-94+ residual certificate."""

from __future__ import annotations

from collections import Counter
from itertools import combinations

import pytest

from lottolab.research.b649_k20_mass94plus_residual_bound_r4 import (
    CP_SAT_TIME_LIMIT_SECONDS,
    EXPECTED_PAIR_COUNTS,
    CpSatWitness,
    balanced_pair_mass,
    classify_three_edge_motif,
    minimum_mass_for_heavy_count,
    minimum_s2_for_heavy_count,
    multiplicity_witness,
    pair_costs,
    pair_reuse_floor,
    result_record,
    three_edge_motif_witnesses,
    ticket_overlap_degree_cap_at_mass_94,
    triple_profile_cap,
    winning_ticket_cap,
)
from lottolab.research.b649_k20_outside_min_s2_global_penalty_bound_r1 import INCUMBENT


def test_exact_pair_costs_and_mass_conditioned_s2_floors() -> None:
    assert pair_costs() == EXPECTED_PAIR_COUNTS
    assert minimum_s2_for_heavy_count(3, 94) == 66_272_164
    assert minimum_s2_for_heavy_count(3, 95) == 66_738_364
    assert minimum_s2_for_heavy_count(45, 94) == 93_815_260
    assert minimum_mass_for_heavy_count(47) == 94
    assert minimum_mass_for_heavy_count(48) == 96
    with pytest.raises(ValueError, match="incompatible"):
        minimum_s2_for_heavy_count(48, 94)


def test_all_three_edge_defect_graph_toys_have_one_of_five_motifs() -> None:
    possible_edges = tuple(combinations(range(6), 2))
    observed = Counter(
        classify_three_edge_motif(tuple(graph_edges), vertex_count=6)
        for graph_edges in combinations(possible_edges, 3)
    )
    assert observed == Counter(
        {
            "THREE_DISJOINT_PAIRS": 15,
            "PATH_2_PLUS_DISJOINT_EDGE": 180,
            "PATH_4": 180,
            "THREE_EDGE_STAR": 60,
            "TRIANGLE": 20,
        }
    )


def test_three_edge_motifs_are_closed_by_exact_triple_profile_caps() -> None:
    assert triple_profile_cap((0, 0, 2)) == 2_240
    assert triple_profile_cap((0, 1, 1)) == 2_800
    assert triple_profile_cap((0, 1, 2)) == 14_420
    assert triple_profile_cap((0, 2, 2)) == 33_264
    witnesses = three_edge_motif_witnesses()
    assert len(witnesses) == 5
    assert {witness.s2_lower_bound for witness in witnesses} == {66_272_164}
    assert {witness.ticket_overlap_degree_cap for witness in witnesses} == {13}
    assert max(witness.upper_bound for witness in witnesses) == 306_941_662
    assert all(witness.upper_bound < INCUMBENT for witness in witnesses)


def test_mass_94_ticket_capacity_and_repeated_label_incidence_cap() -> None:
    selected_at_19 = balanced_pair_mass(19, 6)
    outside_at_19 = balanced_pair_mass(101, 43)
    selected_at_20 = balanced_pair_mass(20, 6)
    outside_at_20 = balanced_pair_mass(100, 43)
    assert selected_at_19 + outside_at_19 == 94
    assert selected_at_20 + outside_at_20 == 95
    assert ticket_overlap_degree_cap_at_mass_94() == 13

    totals = [
        balanced_pair_mass(selected, 6) + balanced_pair_mass(120 - selected, 43)
        for selected in range(20, 121)
    ]
    assert totals == sorted(totals)


def test_seven_label_pair_reuse_caps_and_residual_witness() -> None:
    assert pair_reuse_floor(17) == 39
    assert pair_reuse_floor(18) == 45
    assert pair_reuse_floor(19) == 51
    assert winning_ticket_cap(3) == 8
    assert winning_ticket_cap(44) == 17
    assert winning_ticket_cap(45) == 18

    mass_94 = multiplicity_witness(45, 94)
    mass_95 = multiplicity_witness(45, 95)
    assert (mass_94.ordinary_edge_count, mass_94.s2_lower_bound) == (4, 93_815_260)
    assert mass_94.duplicate_outcome_lower_bound == 10_423_918
    assert mass_94.upper_bound == 353_997_642
    assert mass_95.upper_bound == 353_945_842
    assert mass_95.s2_lower_bound - mass_94.s2_lower_bound == 466_200


def test_result_record_reports_mass_slices_and_exact_unresolved_motif() -> None:
    record = result_record()
    assert record["MASS94_BOUND"] == 353_997_642
    assert record["MASS95PLUS_BOUND"] == 353_945_842
    assert record["FAMILY_B_BOUND"] == 353_997_642
    assert record["FAMILY_B_STATUS"] == "TIGHTENED_OPEN_RESIDUAL"
    assert record["CLOSED_GRAPH_FAMILIES"] == [
        "THREE_DISJOINT_PAIRS",
        "PATH_2_PLUS_DISJOINT_EDGE",
        "PATH_4",
        "THREE_EDGE_STAR",
        "TRIANGLE",
    ]
    assert record["UNRESOLVED_RESIDUAL"] == {
        "heavy_pair_count": 45,
        "ordinary_edge_count": 4,
        "overlap_mass_floor": 94,
        "mass_partition": "EXACT_MASS_94",
        "description": (
            "exactly 45 overlap-2 ticket pairs and 4 overlap-1 pairs "
            "at total overlap mass exactly 94"
        ),
    }
    assert record["CP_SAT"]["STATUS"] == "NOT_RUN"


def test_unknown_cpsat_result_does_not_change_the_analytic_bound() -> None:
    cp_sat = CpSatWitness(
        status="UNKNOWN",
        objective=None,
        certified_upper_bound=None,
        wall_time_seconds=812.974078,
        time_limit_seconds=CP_SAT_TIME_LIMIT_SECONDS,
        workers=1,
        scope="h=45, M=94, maximize tickets sharing one fixed 7-label outcome",
    )
    record = result_record(cp_sat)
    assert record["FAMILY_B_BOUND"] == 353_997_642
    assert record["CP_SAT"]["STATUS"] == "UNKNOWN"
    assert record["CP_SAT"]["CERTIFIED_UPPER_BOUND"] is None
    assert record["CP_SAT"]["REPORTED_WALL_TIME_EXCEEDS_FIXED_BUDGET"] is True
