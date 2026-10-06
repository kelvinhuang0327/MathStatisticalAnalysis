from __future__ import annotations

import json
from pathlib import Path

import pytest

from lottolab.research.b649_k20_min_s2_current_bound_owner_refinement_r15 import (
    CURRENT_FAMILY_BOUND,
    EXPECTED_OWNER_PROFILE,
    NEXT_CURSOR_BOUND,
    assert_no_lower_cursor_work,
    assert_unresolved_suffix_bounded,
    canonical_primitive_preflight,
    reconstruct_family_max_ledger,
)


def test_family_max_ledger_reconstruction_selects_exact_owner() -> None:
    ledger = reconstruct_family_max_ledger()

    assert len(ledger.records) == 179
    assert ledger.family_upper_bound == CURRENT_FAMILY_BOUND
    assert ledger.incumbent == 313_239_661
    assert len(ledger.owner_profiles) == 1
    owner = ledger.owner_profiles[0]
    assert owner.profile == EXPECTED_OWNER_PROFILE
    assert owner.certificate_source == "R12.PROFILE_BOUNDS[30]"
    assert owner.realizability == "REALIZABLE"
    assert owner.support_solver_status == "OPTIMAL"
    assert owner.graph_triangle_upper_bound == 275
    assert owner.s3_upper_bound == 5_299_616
    assert owner.s4_lower_bound == 112
    assert ledger.next_cursor_bound == NEXT_CURSOR_BOUND
    assert_unresolved_suffix_bounded(ledger)


def test_owner_selection_guard_rejects_cursor_profiles() -> None:
    ledger = reconstruct_family_max_ledger()
    owner_profiles = tuple(owner.profile for owner in ledger.owner_profiles)
    newly_load_bearing = (6, 6, 6, 6, 6, 5, 5, 5, 5, 5, 4, 4, 2, 1, 0, 0, 0, 0, 0, 0)

    assert_no_lower_cursor_work(ledger, owner_profiles)
    assert_no_lower_cursor_work(
        ledger, (newly_load_bearing,), active_family_bound=313_686_120
    )
    with pytest.raises(AssertionError, match="non-owner"):
        assert_no_lower_cursor_work(
            ledger,
            (ledger.next_cursor_profile,),
            active_family_bound=313_686_120,
        )


def test_canonical_primitives_match_packet() -> None:
    assert canonical_primitive_preflight() == {
        "STATUS": "PASS",
        "SINGLE_TICKET_ANY_PRIZE": 18_611_432,
        "K20_S1": 372_228_640,
    }


def test_result_promotes_ranked_cursor_without_lower_profile_work() -> None:
    result_path = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "research"
        / "matrix-native-results"
        / "b649-k20-min-s2-current-bound-owner-refinement-r15-result.json"
    )
    result = json.loads(result_path.read_text(encoding="utf-8"))

    assert result["CURRENT_BOUND_OWNER_PROFILE_COUNT"] == 1
    assert result["CURRENT_BOUND_OWNER_PROFILES"] == ["66655555555511100000"]
    assert result["REFINED_LOAD_BEARING_PROFILE_COUNT"] == 2
    assert result["REFINED_LOAD_BEARING_PROFILES"] == [
        "66655555555511100000",
        "66666555554421000000",
    ]
    assert result["NEXT_CURSOR_BOUND"] == NEXT_CURSOR_BOUND
    assert result["NEXT_CURSOR_PROFILE"] == "66666665443111111110"
    assert result["LOWER_CURSOR_PROFILE_SOLVES"] == 0
    assert result["NO_LOWER_CURSOR_WORK_STATUS"] == "PASS"
    assert result["CANONICAL_PRIMITIVE_STATUS"] == "PASS"
    assert result["FULL_4850_PROFILE_CENSUS_REBUILT"] is False
    assert result["FAMILY_UPPER_BOUND"] == NEXT_CURSOR_BOUND
    assert result["FAMILY_UPPER_BOUND"] < CURRENT_FAMILY_BOUND
    assert result["FAMILY_STATUS"] == "CURRENT_OWNER_ELIMINATED_CURSOR_LOAD_BEARING"
    assert result["SOLVER_STATUS"] == "FEASIBLE"
    assert result["SOLVER_CERTIFIED_BOUND"] == NEXT_CURSOR_BOUND
    assert result["REMAINING_GAP"] == 435_931

    first_owner, second_owner = result["OWNER_PROFILE_BOUNDS"]
    assert first_owner["DEGREE_PROFILE"] == list(EXPECTED_OWNER_PROFILE)
    assert first_owner["CERTIFICATE_SOURCE"] == "R12.PROFILE_BOUNDS[30]"
    assert first_owner["REALIZABILITY"] == "REALIZABLE"
    assert first_owner["FAMILY_UPPER_BOUND"] == 313_665_848
    assert first_owner["REFINED_GRAPH_TRIANGLE_UPPER_BOUND"] == 273
    assert first_owner["S4_LOWER_BOUND_AT_S3_MAXIMIZERS"] == 112
    assert first_owner["EXACT_PROFILE_SPECIFIC_S4_MINIMUM"] == "NOT_COMPUTED"

    assert second_owner["PROFILE"] == "66666555554421000000"
    assert second_owner["DEGREE_PROFILE"] == [
        6, 6, 6, 6, 6, 5, 5, 5, 5, 5, 4, 4, 2, 1, 0, 0, 0, 0, 0, 0
    ]
    assert second_owner["CERTIFICATE_SOURCE"] == "R11.PROFILE_BOUNDS[6]"
    assert second_owner["REALIZABILITY"] == "REALIZABLE"
    assert second_owner["ORIGINAL_FAMILY_UPPER_BOUND"] == 313_686_120
    assert second_owner["REFINED_GRAPH_TRIANGLE_UPPER_BOUND"] == 272
    assert second_owner["FAMILY_UPPER_BOUND"] == 313_662_376
    assert second_owner["S4_LOWER_BOUND_AT_S3_MAXIMIZERS"] == 112
    assert second_owner["EXACT_PROFILE_SPECIFIC_S4_MINIMUM"] == "NOT_COMPUTED"
    assert second_owner["S3_CERTIFICATE"]["COMPLEMENT_TRIANGLE_CERTIFIED_LOWER_BOUND"] == 28
