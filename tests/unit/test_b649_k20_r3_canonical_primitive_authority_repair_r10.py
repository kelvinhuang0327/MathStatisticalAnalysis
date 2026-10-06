"""Focused regression checks for canonical R3 authority reconstruction."""

from __future__ import annotations

from lottolab.research import (
    b649_k20_r3_canonical_primitive_authority_repair_r10 as r10,
)


def test_canonical_single_ticket_pair_diagonal_and_k20_s1() -> None:
    primitives = r10.canonical_primitives()

    assert primitives["OFFICIAL_ANY_PRIZE_OUTCOME_SPACE"] == 601_304_088
    assert primitives["SINGLE_TICKET_ANY_PRIZE"] == 18_611_432
    assert primitives["PAIR_DIAGONAL_I6"] == primitives["SINGLE_TICKET_ANY_PRIZE"]
    assert primitives["K20_S1"] == 372_228_640
    assert primitives["OLD_INVALID_SINGLE_TICKET_COUNT"] == 18_221_078
    assert primitives["S1_CORRECTION"] == 7_807_080


def test_complete_corrected_frontier_is_recomputed_from_fingerprinted_r7_data() -> None:
    result = r10.build_canonical_authority_result()
    frontier = result["CORRECTED_LOAD_BEARING_FRONTIER"]

    assert result["S1_INDEPENDENT_R7_CENSUS"]["RESIDUAL_STATE_COUNT"] == 10_117
    assert result["S1_INDEPENDENT_R7_CENSUS"]["S2_S3_FRONTIER_SIZE"] == 23
    assert len(frontier) == result["CORRECTED_LOAD_BEARING_STATE_COUNT"] == 23
    assert all(row["capable_of_exceeding_r4_reference"] for row in frontier)
    assert tuple(row["canonical_frontier_rank"] for row in frontier) == tuple(range(1, 24))
    assert frontier[0]["canonical_frontier_upper_bound"] == 358_352_830
    assert frontier[0]["refinement_source"] == "R9_OPTIMAL_HISTOGRAM_AND_MULTIPLICITY"


def test_r9_reuse_checks_optimal_histograms_and_does_not_promote_feasible_s4() -> None:
    result = r10.build_canonical_authority_result()
    refinements = result["REUSED_R9_REFINEMENTS"]
    s4_status = result["REUSED_R9_EXACT_S4_SUMMARY"]

    assert len(refinements) == 7
    assert all(row["histogram_solver_status"] == "OPTIMAL" for row in refinements.values())
    assert all(
        row["multiplicity_bound_source"] == "STRUCTURAL_MAXIMUM_FROM_18_RESIDUAL_TICKETS"
        and row["multiplicity_cap"] == 18
        for row in refinements.values()
    )
    assert refinements["s2-11295555-s3-450450"]["multiplicity_solver_status"] == "FEASIBLE"
    assert (
        refinements["s2-11295555-s3-450450"]["multiplicity_exactness_source"]
        == "CONSERVATIVE_SOLVER_BOUND"
    )
    assert s4_status["last_state_minimum_proven"] is False
    assert s4_status["last_state_solver_status"] == "FEASIBLE"
    assert result["SOLVER_EXECUTION"]["S4_UNPROVEN_STATE_USED_AS_PROOF"] is False
    assert result["SOLVER_EXECUTION"]["FEASIBLE_IS_PROOF"] is False


def test_tail_gap_and_final_r3_bound_use_canonical_formula() -> None:
    result = r10.build_canonical_authority_result()
    tail = result["TAIL_CERTIFICATE"]
    state_terms = [
        row["certified_state_r3_upper_bound"] for row in result["CORRECTED_LOAD_BEARING_FRONTIER"]
    ]

    assert tail["VECTORS_AT_EXACT_CUTOFF_PLUS_ONE"] == 0
    assert tail["MINIMUM_OMITTED_LOCAL_LOSS"] == 6_695_800
    assert tail["CORRECTED_TAIL_BOUND"] == 358_352_828
    assert result["R3_BOUND"] == max(tail["CORRECTED_TAIL_BOUND"], *state_terms)
    assert result["R3_BOUND"] < 358_352_829
    assert result["SUCCESS_A"] is False
    assert result["SUCCESS_B"] is True
    assert result["SUCCESS_C"] is True


def test_machine_result_has_pinned_inputs_and_handoff_values() -> None:
    result = r10.build_canonical_authority_result()

    assert result["BASE_HEAD"] == "862b61c9bccc25222d17b664a77bdaf5014e77a1"
    assert result["BASE_TREE"] == "68cbefac9a215df49e9825d422bc32b2dfcc16d5"
    assert len(result["UPSTREAM_FINGERPRINTS_SHA256"]) == 11
    assert result["R4_REFERENCE_BOUND"] == 350_545_749
    assert result["FAMILY_A_RECOMPUTED_BOUND"] == result["R3_BOUND"]
    assert result["FAMILY_A_BOTTLENECK_R"] == "R3"
    assert result["INCUMBENT"] == 313_239_661
    assert result["REMAINING_GAP"] == 45_113_167
