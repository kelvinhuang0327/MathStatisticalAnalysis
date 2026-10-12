"""Exact two-owner ledger, owner-switch, stop-state and no-cursor regressions (R19)."""

from __future__ import annotations

import json
from typing import cast

import pytest

import lottolab.research.b649_k20_min_s2_dual_owner_refinement_r19 as r19
from lottolab.research.b649_k20_min_s2_current_bound_owner_refinement_r15 import (
    ProfileCertificate,
    canonical_primitive_preflight,
    reconstruct_family_max_ledger,
)
from lottolab.research.b649_k20_min_s2_higher_order_closure_r2 import K20_S1, K20_S2
from lottolab.research.b649_k20_min_s2_r16_freeze_and_owner_refinement_r17 import (
    exact_support_triangle_refutation,
    owner_lineage,
    witness_open_wedge_check,
)
from lottolab.research.b649_k20_min_s2_realizable_core_class_bound_r4 import (
    s3_sum_from_wedges_and_triangles,
)

DegreeProfile = tuple[int, ...]
Triple = tuple[int, int, int]
Pair = tuple[int, int]

A, B = r19.OWNER_A, r19.OWNER_B
CURSOR = r19.NEXT_CURSOR_PROFILE
R12_ROW_8: DegreeProfile = tuple(int(d) for d in "66665555555411100000")
R12_ROW_10: DegreeProfile = tuple(int(d) for d in "66655555555521000000")


def _identity(profile: DegreeProfile) -> str:
    return "".join(str(d) for d in profile)


def _record(profile: DegreeProfile) -> ProfileCertificate:
    return next(r for r in reconstruct_family_max_ledger().records if r.profile == profile)


def _owner_bound(_: DegreeProfile, cap: int) -> int:
    return r19.owner_bound_from_cap(833, cap, 64)[1]


def _artifact() -> dict[str, object]:
    return cast(dict[str, object], json.loads(r19.result_path().read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def ledger() -> tuple[dict[DegreeProfile, int], dict[DegreeProfile, str]]:
    return r19.post_r18_bound_ledger()


def test_canonical_primitives_match_packet() -> None:
    assert canonical_primitive_preflight() == {
        "STATUS": "PASS",
        "SINGLE_TICKET_ANY_PRIZE": 18_611_432,
        "K20_S1": 372_228_640,
    }


def test_post_r18_ledger_has_exactly_the_two_packet_owners(
    ledger: tuple[dict[DegreeProfile, int], dict[DegreeProfile, str]],
) -> None:
    bounds, sources = ledger

    assert len(bounds) == 282
    assert max(bounds.values()) == r19.START_FAMILY_BOUND == 313_671_448
    assert r19.assert_exact_two_owner_set(bounds, sources) == (A, B)
    assert [p for p, b in bounds.items() if b == 313_671_448] in ([A, B], [B, A])
    assert (sources[A], sources[B]) == ("R11.PROFILE_BOUNDS[15]", "R11.PROFILE_BOUNDS[17]")
    assert CURSOR not in bounds
    assert r19.NEXT_CURSOR_BOUND == 313_658_120 < 313_671_448
    others = {p: b for p, b in bounds.items() if p not in (A, B)}
    assert max(others.values()) == 313_668_648
    assert sorted(p for p, b in others.items() if b == 313_668_648) == [R12_ROW_10, R12_ROW_8]
    assert (sources[R12_ROW_8], sources[R12_ROW_10]) == (
        "R12.PROFILE_BOUNDS[8]",
        "R12.PROFILE_BOUNDS[10]",
    )
    assert sum(b > r19.NEXT_CURSOR_BOUND for b in others.values()) == 12


def test_no_third_owner_assertion_fails_closed(
    ledger: tuple[dict[DegreeProfile, int], dict[DegreeProfile, str]],
) -> None:
    bounds, sources = ledger

    with pytest.raises(AssertionError, match="third profile"):
        r19.assert_exact_two_owner_set({**bounds, R12_ROW_8: 313_671_448}, sources)
    with pytest.raises(AssertionError, match="differs"):
        r19.assert_exact_two_owner_set({**bounds, B: 313_671_447}, sources)
    with pytest.raises(AssertionError, match="cursor"):
        r19.assert_exact_two_owner_set(bounds, sources, cursor_bound=313_671_448)
    with pytest.raises(AssertionError, match="source"):
        r19.assert_exact_two_owner_set(bounds, {**sources, A: "R12.PROFILE_BOUNDS[0]"})


@pytest.mark.parametrize(
    ("owner", "source", "witness_triangles"),
    [(A, "R11.PROFILE_BOUNDS[15]", 209), (B, "R11.PROFILE_BOUNDS[17]", 194)],
)
def test_phase1_owner_lineage_reproduces_the_start_bound(
    owner: DegreeProfile, source: str, witness_triangles: int
) -> None:
    record = _record(owner)
    lineage = owner_lineage(record)
    row = r19.owner_ledger_row(owner, lineage, source)

    assert record.certificate_source == source
    assert lineage["caps"] == {
        "R8_COARSE_PROFILE_ENVELOPE": 277,
        "R10_MOTIF_CP_SAT_BEST_BOUND": 278,
        "R10_DEGREE_CLASS_OPEN_WEDGE_RELAXATION": 273,
    }
    assert row["LOAD_BEARING_RELAXATION"] == "R10_DEGREE_CLASS_OPEN_WEDGE_RELAXATION"
    assert row["WEDGE_COUNT"] == 833
    assert row["LOAD_BEARING_OPEN_WEDGE_LOWER_BOUND"] == 14
    assert row["GRAPH_TRIANGLE_UPPER_BOUND"] == 273
    assert row["NONCORE_TRIANGLE_UPPER_BOUND"] == 251
    assert row["COMPLEMENT_TRIANGLE_IDENTITY_CONSTANT"] == 299
    assert row["S3_UPPER_BOUND"] == s3_sum_from_wedges_and_triangles(833, 251) == 5_281_472
    assert (row["S4_LOWER_BOUND"], row["FOURTH_ORDER_CREDIT"]) == (112, 64)
    assert row["CERTIFIED_FAMILY_UPPER_BOUND"] == K20_S1 - K20_S2 + 5_281_472 - 64
    assert row["CERTIFIED_FAMILY_UPPER_BOUND"] == 313_671_448
    check = witness_open_wedge_check(
        owner,
        cast(tuple[Triple, ...], lineage["triples"]),
        cast(tuple[Pair, ...], lineage["doubles"]),
    )
    assert check["WITNESS_GRAPH_TRIANGLES"] == witness_triangles
    assert check["WITNESS_OPEN_WEDGES"] == 833 - 3 * witness_triangles
    assert check["FIXED_WITNESS_STATUS_BY_CEILING"] == {
        "AT_WITNESS_COUNT": "OPTIMAL",
        "ONE_BELOW_WITNESS_COUNT": "INFEASIBLE",
    }


@pytest.mark.parametrize("owner", [A, B])
def test_exact_support_model_refutes_cap_273_for_each_owner(owner: DegreeProfile) -> None:
    certificate = exact_support_triangle_refutation(owner, refuted_triangle_count=273)

    assert certificate["STATUS"] == "INFEASIBLE"
    assert certificate["OPEN_WEDGE_CEILING_REFUTED"] == 833 - 3 * 273 == 14
    assert certificate["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"] == 272
    assert _owner_bound(owner, 272) == 313_659_576 == 313_671_448 - 11_872


def test_owner_switch_regression_and_success_c_on_the_real_ledger(
    ledger: tuple[dict[DegreeProfile, int], dict[DegreeProfile, str]],
) -> None:
    bounds, _ = ledger
    calls: list[tuple[DegreeProfile, int]] = []

    def refine(owner: DegreeProfile, cap: int) -> int:
        calls.append((owner, cap))
        return cap - 1

    outcome = r19.run_refinement_schedule(
        bounds, owner_caps={A: 273, B: 273}, owner_bound=_owner_bound, refine=refine
    )

    assert calls == [(A, 273), (B, 273)]
    assert outcome.status == r19.SUCCESS_C
    assert [s.family_after.bound for s in outcome.steps] == [313_671_448, 313_668_648]
    assert outcome.steps[0].family_after.owners == (_identity(B),)
    assert outcome.owner_bounds == {A: 313_659_576, B: 313_659_576}
    assert outcome.family.owners == (_identity(R12_ROW_8), _identity(R12_ROW_10))
    assert not outcome.family.cursor_carries_bound

    reversed_calls: list[DegreeProfile] = []
    r19.run_refinement_schedule(
        bounds,
        owner_caps={A: 273, B: 273},
        owner_bound=_owner_bound,
        refine=lambda owner, cap: reversed_calls.append(owner) or cap - 1,
        owner_order=(B, A),
    )
    assert reversed_calls == [B, A]


def test_schedule_alternates_to_success_b_when_only_the_cursor_lies_below(
    ledger: tuple[dict[DegreeProfile, int], dict[DegreeProfile, str]],
) -> None:
    bounds, _ = ledger
    thinned = {p: b for p, b in bounds.items() if p in (A, B) or b <= r19.NEXT_CURSOR_BOUND}
    calls: list[DegreeProfile] = []

    def refine(owner: DegreeProfile, cap: int) -> int:
        calls.append(owner)
        return cap - 1

    outcome = r19.run_refinement_schedule(
        thinned, owner_caps={A: 273, B: 273}, owner_bound=_owner_bound, refine=refine
    )

    assert calls == [A, B, A, B]
    assert outcome.status == r19.SUCCESS_B
    assert outcome.owner_caps == {A: 271, B: 271}
    assert outcome.family.bound == r19.NEXT_CURSOR_BOUND
    assert outcome.family.owners == (_identity(CURSOR),)
    assert outcome.family.cursor_carries_bound


def test_schedule_switches_to_the_remaining_max_owner_after_a_deep_drop(
    ledger: tuple[dict[DegreeProfile, int], dict[DegreeProfile, str]],
) -> None:
    bounds, _ = ledger
    calls: list[tuple[DegreeProfile, int]] = []

    def refine(owner: DegreeProfile, cap: int) -> int:
        calls.append((owner, cap))
        return cap - 3 if owner == A else cap

    outcome = r19.run_refinement_schedule(
        bounds, owner_caps={A: 273, B: 273}, owner_bound=_owner_bound, refine=refine
    )

    assert calls == [(A, 273), (B, 273)]
    assert outcome.status == r19.BLOCKED
    assert outcome.family.bound == r19.START_FAMILY_BOUND
    assert outcome.owner_caps == {A: 270, B: 273}


def test_select_next_owner_and_classify_stop_states() -> None:
    assert r19.select_next_owner({A: 5, B: 5}, 5) == A
    assert r19.select_next_owner({A: 4, B: 5}, 5) == B
    assert r19.select_next_owner({A: 4, B: 4}, 5) is None
    with pytest.raises(AssertionError):
        r19.select_next_owner({A: 5}, 5)

    def state(bound: int, *owners: DegreeProfile) -> r19.FamilyState:
        return r19.FamilyState(bound, tuple(_identity(p) for p in owners), False)

    high = {A: 313_659_576, B: 313_659_576}
    assert r19.classify_stop(state(r19.INCUMBENT, R12_ROW_8), high) == r19.SUCCESS_A
    assert r19.classify_stop(state(313_658_120, CURSOR), {A: 313_658_120, B: 1}) == r19.SUCCESS_B
    assert r19.classify_stop(state(313_668_648, R12_ROW_8), high) == r19.SUCCESS_C
    assert r19.classify_stop(state(313_659_576, A, B), high) is None
    assert r19.classify_stop(state(313_671_448, B), {A: 313_659_576, B: 313_671_448}) is None


def test_no_cursor_or_outside_owner_solver_work_guard(
    ledger: tuple[dict[DegreeProfile, int], dict[DegreeProfile, str]],
) -> None:
    owners = (A, B)
    r19.assert_owner_set_solver_scope((A,), owners=owners, cursor=CURSOR)
    r19.assert_owner_set_solver_scope((B,), owners=owners, cursor=CURSOR)
    for requested in ((CURSOR,), (A, CURSOR), (), (A, B), (R12_ROW_8,)):
        with pytest.raises(AssertionError):
            r19.assert_owner_set_solver_scope(requested, owners=owners, cursor=CURSOR)
    with pytest.raises(AssertionError):
        r19.assert_owner_set_solver_scope((A,), owners=(A, CURSOR), cursor=CURSOR)

    bounds, _ = ledger
    with pytest.raises(AssertionError):
        r19.family_state({**bounds, CURSOR: 0}, {A: bounds[A]})
    with pytest.raises(AssertionError):
        r19.family_state(bounds, {A: bounds[A] + 1})


def test_result_artifact_records_success_c_and_no_cursor_work(
    ledger: tuple[dict[DegreeProfile, int], dict[DegreeProfile, str]],
) -> None:
    result = _artifact()
    bounds, _ = ledger

    assert result["TASK_ID"] == r19.TASK_ID
    assert result["BASE_HEAD"] == "70c154bcdd9ab2d4c74e4f1e1032f0a817fa4919"
    assert result["BASE_TREE"] == "832d52e02fdce09a4a4a2226f5e08d3405c42e8c"
    assert result["TASK_STATUS"] == r19.SUCCESS_C
    assert result["OWNER_PROFILE_COUNT"] == 2
    assert result["OWNER_PROFILES"] == [_identity(A), _identity(B)]
    assert result["NO_THIRD_OWNER_AT_START"] == "PASS"
    assert result["START_OWNER_BOUNDS"] == {_identity(A): 313_671_448, _identity(B): 313_671_448}
    assert result["REFINED_OWNER_BOUNDS"] == {_identity(A): 313_659_576, _identity(B): 313_659_576}
    family = r19.family_state(bounds, {A: 313_659_576, B: 313_659_576})
    assert result["FAMILY_UPPER_BOUND"] == family.bound == 313_668_648
    assert result["CURRENT_BOUND_OWNERS"] == list(family.owners)
    assert result["CURRENT_BOUND_OWNER"] == _identity(R12_ROW_8)
    assert result["REMAINING_GAP"] == 313_668_648 - 313_239_661 == 428_987
    assert result["CERTIFIED_FAMILY_DROP"] == 2_800
    assert result["PACKET_SUCCESS_B_SATISFIED"] is False
    assert result["PACKET_SUCCESS_B_PREMISE"] == "CONTRADICTED_RESOLVED_PROFILES_ABOVE_CURSOR"
    above = cast(list[object], result["RESOLVED_PROFILES_ABOVE_CURSOR_OUTSIDE_OWNER_SET"])
    assert len(above) == 12
    assert result["CANONICAL_PRIMITIVE_STATUS"] == "PASS"
    assert result["SOLVER_STATUS"] == "INFEASIBLE_CERTIFIED"
    assert result["SOLVER_CERTIFIED_BOUND"] == 313_659_576
    assert result["SOLVER_PROFILES_SENT"] == [_identity(A), _identity(B)]
    assert result["CURSOR_PROFILE_SOLVES"] == 0
    assert result["OUTSIDE_OWNER_SET_PROFILE_SOLVES"] == 0
    assert result["CURSOR_DESCENT_STARTED"] is False
    assert result["NEW_PORTFOLIO_SEARCH_STARTED"] == "NO"
    assert result["PRODUCTION_MUTATION"] == "NONE"
    assert result["UNCERTIFIED_FINAL_ATTEMPT"] is None

    steps = cast(list[dict[str, object]], result["REFINEMENT_STEPS"])
    assert [s["OWNER"] for s in steps] == [_identity(A), _identity(B)]
    assert [s["FAMILY_UPPER_BOUND"] for s in steps] == [313_671_448, 313_668_648]
    for step in steps:
        assert step["REFINED_GRAPH_TRIANGLE_UPPER_BOUND"] == 272
        routes = {cast(str, r["ROUTE"]): r for r in cast(list[dict[str, object]], step["ROUTES"])}
        route_b = routes["B_EXACT_SUPPORT_MODEL_OPEN_WEDGE_REFUTATION"]
        assert route_b["STATUS"] == "INFEASIBLE"
        assert route_b["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"] == 272
        route_a = routes["A_R15_COMPLEMENT_TRIANGLE_MODEL"]
        assert route_a["STATUS"] in {"OPTIMAL", "FEASIBLE"}
        assert (
            cast(int, route_a["GRAPH_TRIANGLE_IDENTITY_CONSTANT"])
            - cast(int, route_a["COMPLEMENT_TRIANGLE_CERTIFIED_LOWER_BOUND"])
            == route_a["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"]
        )
        assert cast(int, route_a["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"]) >= 272
