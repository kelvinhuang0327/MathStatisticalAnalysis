"""Focused checks for the Y/L block-isolation certificate T<=246 of 66666555555311100000."""

from __future__ import annotations

from dataclasses import replace

import pytest

from lottolab.research import b649_min_s2_top_owner_yl_cap246_formal_cert_r1 as x

STS13 = "55555555555511111100"


@pytest.fixture(scope="module")
def authority() -> x.chase.Authority:
    return x.chase.load_authority()


@pytest.fixture(scope="module")
def result(authority: x.chase.Authority) -> dict[str, object]:
    return x.compute_result(authority)


@pytest.fixture(scope="module")
def realization(authority: x.chase.Authority) -> x.chase.Realization:
    found = authority.ledger[x.TARGET].realization
    assert found is not None
    return found


def test_lemma_premises_follow_from_the_profile_and_model() -> None:
    premises = x.lemma_premises()
    assert (premises["TRIPLE_SUPPORTS"], premises["DOUBLE_SUPPORTS"]) == (22, 27)
    assert (premises["GRAPH_EDGES"], premises["CORE_COUNT"]) == (93, 15)
    assert (premises["L1_CORE_TICKETS_MISSED_BY_S6"], premises["L1_S1_COUNT"]) == (2, 3)
    assert premises["L2_SLOTS_IF_TWO_X_SHARE_A_BLOCK"] == 3
    assert (premises["L2_SLOTS"], premises["L2_EXTRA_SLOTS"]) == (6, 1)
    assert (premises["L3_TRIPLES_INSIDE_Y"], premises["L3_Y_SHADOW_EDGES"]) == (19, 60)
    assert (premises["L3_L_SHADOW_EDGES"], premises["L3_CROSSING_SHADOW_EDGES"]) == (0, 6)
    assert (premises["L4_Y_PAIR_INCIDENCE"], premises["L4_L_PAIR_INCIDENCE"]) == (9, 45)
    assert premises["L5_T2_BY_EXTRA_SLOT"] == {"S6": 4, "S5": 4, "W": 6}
    assert premises["L5_T2_CAP"] == x.T2_CAP == 6


def test_exhaustive_relaxation_maximum_is_246() -> None:
    relaxed = x.relaxation()
    assert relaxed["PROJECTION_COUNT"] == 144_737
    assert relaxed["MAXIMUM"] == x.CAP == 246
    assert relaxed["MAXIMUM_BY_P_Y"] == {"0": 245, "1": 244, "2": 246, "3": 237, "4": 237}
    argmax = [x.object_row(r) for r in x.rows(relaxed["ARGMAX"])]
    assert len(argmax) == 3
    for i, row in enumerate(argmax):
        assert (row["P_Y"], row["Q"], row["COMPONENT_BOUNDS"]) == (2, 5, [186, 23, 6, 31])
        assert x.rows(row["PI"]) == [5 if j == 2 - i else 0 for j in range(8)]
        assert sum(x.integer(v) for v in x.rows(row["B"])) == 1


def test_ablations_identify_the_load_bearing_source_limits() -> None:
    assert x.relaxation(w_internal=False)["MAXIMUM"] == 246
    assert x.unlimited_source_maximum() == 251


def test_l4_feasibility_rejects_every_violated_limit() -> None:
    ok_a, ok_b = (4, 0, 0, 0, 0, 0, 0, 0), (1, 0, 0, 0, 0, 0, 0, 0)
    a3 = (3, 0, 0, 0, 0, 0, 0, 0)
    assert x.feasible(ok_a, ok_b)
    assert not x.feasible(a3, (2, 0, 0, 0, 0, 0, 0, 0))  # w reaches one ticket twice
    seven = (0, 0, 0, 2, 2, 2, 1, 0)
    assert not x.feasible(seven, (0,) * 8, w_internal=False)  # more than six S5 sources
    assert not x.feasible(a3, (1, 1, 1, 1, 0, 0, 0, 0))  # w has three pair labels
    assert not x.feasible((5, 0, 0, 0, 0, 0, 0, 0), (1, 1, 0, 0, 0, 0, 0, 0))  # pi_x > 5
    assert not x.feasible((2, 0, 0, 0, 0, 0, 0, 0), (0,) * 8)  # q must be odd
    six, one = (0, 0, 0, 3, 3, 0, 0, 0), (0, 0, 0, 0, 0, 1, 0, 0)
    assert not x.feasible(six, one)  # w keeps two labels but no S5 partner is free
    assert x.feasible(six, one, w_internal=False)


def test_component_bounds_values_and_domain() -> None:
    assert x.component_bounds(2, (5, 0, 0, 0, 0, 0, 0, 0)) == (186, 23, 6, 31)
    assert x.component_bounds(0, (1, 1, 1, 1, 1, 2, 2, 0)) == (175, 11, 6, 13)
    assert x.component_bounds(4, (0, 0, 0, 1, 0, 0, 0, 0)) == (201, 3, 6, 24)
    for p_y, pi in ((5, (0,) * 8), (2, (4, 0, 0, 0, 0, 0, 0, 0)), (0, (6, 3, 0, 0, 0, 0, 0, 0))):
        with pytest.raises(ValueError):
            x.component_bounds(p_y, pi)


def test_recorded_realization_passes_every_lemma(realization: x.chase.Realization) -> None:
    seen = x.audit(*realization)
    assert (seen["TRIANGLES"], seen["SPLIT_T0_T1_T2_T3"]) == (192, [170, 9, 1, 12])
    assert (seen["P_Y"], seen["Q"], seen["P_L"]) == (0, 9, 18)
    assert seen["PI"] == [1, 1, 1, 1, 1, 2, 2, 0]
    assert seen["COMPONENT_BOUNDS"] == [175, 11, 6, 13]
    assert (seen["PROJECTION_BOUND"], seen["T2_SLOT_BOUND"]) == (205, 4)
    assert seen["BLOCKS"] == [[0, 1, 12], [3, 4, 13], [0, 2, 14]]
    assert seen["SLOT_MULTIPLICITY"] == {"0": 2, "1": 1, "2": 1, "3": 1, "4": 1}


def test_swap_neighbourhood_is_falsification_only(realization: x.chase.Realization) -> None:
    sweep = x.swap_neighbourhood(*realization)
    assert sweep == {
        "LEGAL_NEIGHBOURS": 170,
        "MAX_TRIANGLES": 200,
        "MAX_PROJECTION_BOUND": 212,
        "STATUS": "PASS_EVERY_NEIGHBOUR_NOT_A_PROOF",
    }


def test_audit_rejects_foreign_and_illegal_realizations(
    realization: x.chase.Realization,
) -> None:
    with pytest.raises(ValueError, match="not the target"):
        x.audit(*x.split.witness_supports("STS13"))
    triples, pairs = realization
    with pytest.raises(ValueError):
        x.audit(triples, (*pairs[:-1], pairs[0]))


def test_route_b_closes_the_profile(result: dict[str, object]) -> None:
    envelope = x.object_row(result["ROUTE_B"])
    assert (envelope["TRIANGLE_CAP"], envelope["S4_BASE"], envelope["TERM_COUNT"]) == (
        246,
        112,
        225,
    )
    assert (envelope["ARGMAX_TRIANGLES"], envelope["ALL_T_MAX_BOUND"]) == (246, 313_242_692)
    assert envelope["BELOW_INCUMBENT"] is True
    assert (result["PROFILE_BOUND_BEFORE"], result["PROFILE_BOUND_AFTER"]) == (
        313_404_008,
        313_242_692,
    )
    assert result["PROFILE_BOUND_AFTER"] == x.INCUMBENT - 21_196


def test_single_row_family_update(result: dict[str, object]) -> None:
    assert (result["FAMILY_BOUND_BEFORE"], result["FAMILY_OWNERS_BEFORE"]) == (
        313_404_008,
        [x.TARGET],
    )
    assert result["FAMILY_BOUND_AFTER_SINGLE_ROW_UPDATE"] == 313_402_304
    assert result["FAMILY_OWNERS_AFTER"] == [STS13]
    assert result["FAMILY_OWNER_AFTER_CAPS"] == {STS13: 270}
    assert result["FAMILY_BOUND_DELTA"] == -1_704
    assert result["NEXT_COMPETING_BOUND_AFTER"] == 313_401_852
    assert result["ROWS_CHANGED"] == [x.TARGET]
    assert (result["ROWS_ABOVE_INCUMBENT_BEFORE"], result["ROWS_ABOVE_INCUMBENT_AFTER"]) == (
        1_381,
        1_380,
    )
    assert result["OTHER_CLOSURE_CERTIFICATES_ADOPTED"] == []
    assert result["NEW_OWNER_CAP_REALIZED_BY_STS13_WITNESS"] is True


def test_single_row_update_refuses_a_different_ledger(authority: x.chase.Authority) -> None:
    ledger = dict(authority.ledger)
    with pytest.raises(AssertionError, match="pinned 4,647-row"):
        x.single_row_update({k: v for k, v in ledger.items() if k != STS13}, 313_242_692)
    ledger[x.TARGET] = replace(ledger[x.TARGET], bound=313_404_009)
    with pytest.raises(AssertionError, match="pinned 4,647-row"):
        x.single_row_update(ledger, 313_242_692)


def test_authority_flags_and_committed_result(result: dict[str, object]) -> None:
    assert (result["BASE_HEAD"], result["BASE_RESULT_SHA256"]) == (
        x.BASE_HEAD,
        x.BASE_RESULT_SHA256,
    )
    assert (result["LEDGER_SHA256"], result["LEDGER_ROWS"]) == (x.LEDGER_SHA256, 4_647)
    provenance = x.object_row(result["MODULE_PROVENANCE"])
    for name in ("split_cap_current_owner_chase_r1", "route_b_current_owner_refinement_r32"):
        assert f"src/lottolab/research/b649_k20_min_s2_{name}.py" in provenance
    assert (result["THEOREM_STATUS"], result["CERTIFIED_T_CAP"]) == ("PROVEN", 246)
    assert result["COMPLETE_ENUMERATION"] == "PASS"
    assert (result["SOLVER_CALLS"], result["HEAVY_SOLVER_STARTED"]) == (0, "NO")
    assert (result["INCUMBENT_CHANGED"], result["RUN1_MUTATED"]) == ("NO", "NO")
    assert x.RESULT_PATH.read_text(encoding="utf-8") == x.render(result)
