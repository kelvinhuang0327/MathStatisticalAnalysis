from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from lottolab.research.b649_k20_min_s2_current_bound_owner_refinement_r15 import (
    ProfileCertificate,
    canonical_primitive_preflight,
    reconstruct_family_max_ledger,
)
from lottolab.research.b649_k20_min_s2_higher_order_closure_r2 import K20_S1, K20_S2
from lottolab.research.b649_k20_min_s2_r16_freeze_and_owner_refinement_r17 import (
    EXPECTED_NEXT_CURSOR_PROFILE,
    EXPECTED_OWNER_PROFILE,
    NEXT_CURSOR_BOUND,
    R16_SOURCE_HASHES,
    RESULT_FILENAME,
    START_OWNER_BOUND,
    assert_owner_only_solver_scope,
    exact_support_triangle_refutation,
    owner_lineage,
    post_r16_bound_ledger,
    r16_freeze_regression,
    recompute_family_bound,
    witness_open_wedge_check,
)
from lottolab.research.b649_k20_min_s2_realizable_core_class_bound_r4 import (
    s3_sum_from_wedges_and_triangles,
)

Triple = tuple[int, int, int]
Pair = tuple[int, int]


def _owner_record() -> ProfileCertificate:
    ledger = reconstruct_family_max_ledger()
    return next(r for r in ledger.records if r.profile == EXPECTED_OWNER_PROFILE)


def test_canonical_primitives_match_packet() -> None:
    assert canonical_primitive_preflight() == {
        "STATUS": "PASS",
        "SINGLE_TICKET_ANY_PRIZE": 18_611_432,
        "K20_S1": 372_228_640,
    }


def test_r16_freeze_deliverables_are_byte_identical_to_the_source_worktree() -> None:
    assert r16_freeze_regression() == R16_SOURCE_HASHES
    assert set(R16_SOURCE_HASHES.values()) == {
        "84c12e5172099fe532f7512804b96ce35e71e69ff8abd47f6f696d1ec2e05303",
        "6cac2ab7187965af979a3b9540125eae48cddfcc35f8b1224deafab892ea1b6a",
        "777b7ee0bf85a0daf351f4c41120f29343d91266df8d59432a8b943602f80083",
    }


def test_post_r16_ledger_has_one_owner_above_the_cursor() -> None:
    bounds, sources = post_r16_bound_ledger()

    assert len(bounds) == 227
    assert max(bounds.values()) == START_OWNER_BOUND == 313_674_248
    assert [p for p, b in bounds.items() if b == START_OWNER_BOUND] == [EXPECTED_OWNER_PROFILE]
    assert sources[EXPECTED_OWNER_PROFILE] == "R11.PROFILE_BOUNDS[4]"
    others = [b for p, b in bounds.items() if p != EXPECTED_OWNER_PROFILE]
    assert max(others) == 313_671_448 < NEXT_CURSOR_BOUND == 313_672_792
    assert EXPECTED_NEXT_CURSOR_PROFILE not in bounds
    assert START_OWNER_BOUND - NEXT_CURSOR_BOUND == 1_456


def test_family_bound_keeps_the_cursor_ceiling_and_classifies_each_stop() -> None:
    bounds, _ = post_r16_bound_ledger()
    owner, cursor = EXPECTED_OWNER_PROFILE, EXPECTED_NEXT_CURSOR_PROFILE

    def recompute(refined: int) -> tuple[int, str, str, list[str]]:
        return recompute_family_bound(
            bounds,
            owner=owner,
            refined_owner_bound=refined,
            cursor=cursor,
            cursor_bound=NEXT_CURSOR_BOUND,
        )

    assert recompute(313_662_376) == (
        313_672_792,
        "SUCCESS_B_OWNER_ELIMINATED_CURSOR_LOAD_BEARING",
        "CURRENT_OWNER_ELIMINATED_CURSOR_LOAD_BEARING",
        ["66666665442211111110"],
    )
    assert recompute(NEXT_CURSOR_BOUND)[1] == "SUCCESS_B_OWNER_ELIMINATED_CURSOR_LOAD_BEARING"
    assert recompute(NEXT_CURSOR_BOUND + 1)[:3] == (
        NEXT_CURSOR_BOUND + 1,
        "SUCCESS_C_OWNER_STRICTLY_TIGHTENED",
        "OPEN_STRICTLY_TIGHTENED",
    )
    assert recompute(NEXT_CURSOR_BOUND + 1)[3] == ["66666555555311100000"]
    assert recompute(START_OWNER_BOUND)[1] == "BLOCKED_NO_CERTIFIED_OWNER_TIGHTENING"
    assert recompute(0)[0] == NEXT_CURSOR_BOUND
    with pytest.raises(AssertionError):
        recompute(START_OWNER_BOUND + 1)


def test_owner_bound_is_set_by_the_degree_class_open_wedge_relaxation() -> None:
    lineage = owner_lineage(_owner_record())

    assert lineage["caps"] == {
        "R8_COARSE_PROFILE_ENVELOPE": 278,
        "R10_MOTIF_CP_SAT_BEST_BOUND": 278,
        "R10_DEGREE_CLASS_OPEN_WEDGE_RELAXATION": 273,
    }
    assert lineage["wedge_count"] == 834
    assert lineage["open_wedge_lower_bound"] == 15
    assert lineage["fourth_order_credit"] == 64


def test_solver_scope_guard_rejects_cursor_and_extra_profiles() -> None:
    owner, cursor = EXPECTED_OWNER_PROFILE, EXPECTED_NEXT_CURSOR_PROFILE
    assert_owner_only_solver_scope((owner,), owner=owner, cursor=cursor)
    for requested in ((cursor,), (owner, cursor), (), (owner, owner)):
        with pytest.raises(AssertionError):
            assert_owner_only_solver_scope(requested, owner=owner, cursor=cursor)
    with pytest.raises(AssertionError):
        assert_owner_only_solver_scope((owner,), owner=owner, cursor=owner)


def test_exact_support_model_refutes_the_prior_triangle_cap() -> None:
    certificate = exact_support_triangle_refutation(
        EXPECTED_OWNER_PROFILE, refuted_triangle_count=273
    )

    assert certificate["STATUS"] == "INFEASIBLE"
    assert certificate["OPEN_WEDGE_CEILING_REFUTED"] == 15
    assert certificate["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"] == 272


def test_open_wedge_model_counts_the_committed_witness_exactly() -> None:
    lineage = owner_lineage(_owner_record())
    check = witness_open_wedge_check(
        EXPECTED_OWNER_PROFILE,
        cast(tuple[Triple, ...], lineage["triples"]),
        cast(tuple[Pair, ...], lineage["doubles"]),
    )

    assert check["WITNESS_GRAPH_TRIANGLES"] == 192
    assert check["WITNESS_OPEN_WEDGES"] == 834 - 3 * 192
    assert check["FIXED_WITNESS_STATUS_BY_CEILING"] == {
        "AT_WITNESS_COUNT": "OPTIMAL",
        "ONE_BELOW_WITNESS_COUNT": "INFEASIBLE",
    }


def test_result_artifact_eliminates_the_owner_and_stops_at_the_cursor() -> None:
    result_path = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "research"
        / "matrix-native-results"
        / RESULT_FILENAME
    )
    result = json.loads(result_path.read_text(encoding="utf-8"))

    refined_s3 = s3_sum_from_wedges_and_triangles(834, 250)
    assert result["TASK_STATUS"] == "SUCCESS_B_OWNER_ELIMINATED_CURSOR_LOAD_BEARING"
    assert result["R16_FREEZE_HEAD"] == "48c27139ca57b71eaa6b0a4b719a634c3a82afa9"
    assert result["R16_SOURCE_HASHES"] == R16_SOURCE_HASHES
    assert result["CURRENT_OWNER_PROFILE"] == "66666555555311100000"
    assert result["START_OWNER_BOUND"] == 313_674_248
    assert result["REFINED_GRAPH_TRIANGLE_UPPER_BOUND"] == 272
    assert result["REFINED_NONCORE_TRIANGLE_UPPER_BOUND"] == 250
    assert result["REFINED_S3_UPPER_BOUND"] == refined_s3 == 5_272_400
    assert result["OWNER_REFINED_BOUND"] == K20_S1 - K20_S2 + refined_s3 - 64
    assert result["OWNER_REFINED_BOUND"] == 313_662_376 == START_OWNER_BOUND - 11_872
    assert result["NEXT_CURSOR_PROFILE"] == "66666665442211111110"
    assert result["NEXT_CURSOR_BOUND"] == 313_672_792
    assert result["FAMILY_UPPER_BOUND"] == 313_672_792
    assert result["REMAINING_GAP"] == 433_131
    assert result["CURRENT_BOUND_OWNER"] == "66666665442211111110"
    assert result["CURRENT_BOUND_OWNER_KIND"] == "UNRESOLVED_RANKED_CURSOR"
    assert result["CANONICAL_PRIMITIVE_STATUS"] == "PASS"
    assert result["SOLVER_STATUS"] == "INFEASIBLE_CERTIFIED"
    assert result["SOLVER_PROFILES_SENT"] == ["66666555555311100000"]
    assert result["CURSOR_PROFILE_SOLVES"] == 0
    assert result["CURSOR_DESCENT_STARTED"] is False
    assert result["NEW_PORTFOLIO_SEARCH_STARTED"] == "NO"
    assert result["PRODUCTION_MUTATION"] == "NONE"

    route_b = result["ROUTE_B_EXACT_SUPPORT_REFUTATION"]
    assert route_b["STATUS"] == "INFEASIBLE"
    assert route_b["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"] == 272
    route_a = result["ROUTE_A_COMPLEMENT_ATTEMPT"]
    assert route_a["CERTIFICATE_KIND"] == "CP_SAT_BEST_OBJECTIVE_LOWER_BOUND"
    assert (
        route_a["GRAPH_TRIANGLE_IDENTITY_CONSTANT"]
        - route_a["COMPLEMENT_TRIANGLE_CERTIFIED_LOWER_BOUND"]
        == route_a["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"]
    )
    assert route_a["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"] >= 272
