"""R26 crossover: sibling replay, crossing arithmetic, grouping, routes and ledger."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import b649_k20_min_s2_six_owner_cursor_crossover_r26 as x
from lottolab.research.b649_k20_min_s2_resolved_above_cursor_owner_chase_r20 import (
    Certificate,
    bound_from_cap,
    profile_id,
)

HARD_OWNER = x.decode_profile("66665555554440000000")


@pytest.fixture(scope="module")
def r25() -> x.batch.State:
    return x.batch.current_state()


@pytest.fixture(scope="module")
def state() -> x.batch.State:
    return x.start_state()


def synthetic(profiles: Sequence[x.DegreeProfile], cap: int) -> dict[str, object]:
    return {
        "ROUTE": x.ROUTE_A,
        "STATUS": "INFEASIBLE",
        "CERTIFICATE_KIND": x.KIND_A,
        "PROFILE_IDS": [profile_id(p) for p in profiles],
        "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": cap,
        "REFUTED_GRAPH_TRIANGLE_COUNT": cap + 1,
        "OPEN_WEDGE_CEILING_REFUTED": x.overlap_wedge_count(profiles[0]) - 3 * (cap + 1),
    }


def always(
    group: Sequence[Certificate], _bounds: Mapping[x.DegreeProfile, int], cap: int
) -> dict[str, object]:
    return synthetic([c.profile for c in group], cap)


def test_canonical_primitives_and_s4() -> None:
    assert x.canonical_primitive_preflight() == {
        "STATUS": "PASS",
        "SINGLE_TICKET_ANY_PRIZE": 18_611_432,
        "K20_S1": 372_228_640,
    }
    assert x.K20_S2 == 63_838_600
    assert x.k20_min_s2_s4_lower_bound_certificate().s4_lower_bound == 112


def test_exact_six_owner_reconstruction(r25: x.batch.State, state: x.batch.State) -> None:
    assert x.family_state(r25.bounds) == (313_650_504, x.OWNERS)
    assert x.REQUIRED_DROP_TO_CURSOR == 313_650_504 - 313_637_848 == 12_656
    rows = x.six_owner_reconstruction(r25, state)
    assert [r["PROFILE_ID"] for r in rows] == list(x.OWNER_IDS)
    for index, row in enumerate(rows):
        assert row["START_BOUND"] == 313_650_504
        assert row["REQUIRED_DROP_TO_CURSOR"] == 12_656
        assert row["TRIANGLE_UNIT"] == 11_872
        assert row["TARGET_TRIANGLE_CAP"] == 269
        refined = x.object_row(row["REFINED_CERTIFICATE"])
        assert refined["CURRENT_BOUND"] == 313_626_760
        assert refined["TRIANGLE_CAP"] == 269
        assert refined["SOURCE_ROW"] == f"GROUP_ATTEMPTS[{index + 1}]"
        assert refined["SOURCE_RESULT"] == x.batch.RESULT_FILENAME


def test_insufficient_one_triangle_certificate_rejected(r25: x.batch.State) -> None:
    for p in x.OWNERS:
        cert = r25.certificates[p]
        with pytest.raises(AssertionError, match="insufficient"):
            x.crossing_bound(cert, 270)
        assert bound_from_cap(p, 270, 112)[1] == 313_638_632 > x.NEXT_CURSOR_BOUND
        assert x.crossing_bound(cert, 269) == (5_236_784, 313_626_760)
    rows = x.six_owner_reconstruction(r25, x.start_state())
    assert {r["ONE_TRIANGLE_VERDICT"] for r in rows} == {"REJECTED_ABOVE_CURSOR"}
    assert {r["TWO_TRIANGLE_VERDICT"] for r in rows} == {"SUFFICIENT"}
    forms = x.certificate_form_evaluation(r25)
    assert forms["ONE_TRIANGLE_SHORTFALL"] == 784
    assert (
        x.object_row(forms["B_ONE_TRIANGLE_PLUS_S4_CREDIT"])["MINIMUM_S4_FLOOR_INCREASE_REQUIRED"]
        == 1_372
    )


def test_structural_grouping(r25: x.batch.State, state: x.batch.State) -> None:
    six = x.signature_groups(r25.certificates[p] for p in x.OWNERS)
    # Identical moments, but the packet also groups by bound-limiting relaxation.
    assert [len(g) for g in six] == [5, 1]
    assert {x.signature(g[0])[:11] for g in six} == {
        (20, 22, 27, 93, 342, 834, 271, 249, 5_260_528, 112, 313_650_504)
    }
    certificates = [r25.certificates[p] for p in x.OWNERS]
    changed = [*certificates[:-1], replace(certificates[-1], s4=1680)]
    assert len(x.signature_groups(changed)) == 3
    above = [p for p, b in state.bounds.items() if b > x.NEXT_CURSOR_BOUND]
    groups = x.signature_groups(state.certificates[p] for p in above)
    assert len(above) == 137
    assert sorted(len(g) for g in groups) == [1, 1, 1, 1, 1, 2, 2, 4, 4, 4, 4, 55, 57]
    assert sorted(p for g in groups for p in (c.profile for c in g)) == sorted(above)
    for group in groups:
        assert len({x.signature(c) for c in group}) == 1


@pytest.mark.parametrize("mutation", ["status", "ledger", "proof", "owner"])
def test_sibling_replay_rejects_drift(r25: x.batch.State, mutation: str) -> None:
    sibling, digest = x.sibling_result()
    changed = copy.deepcopy(sibling)
    if mutation == "status":
        changed["TASK_STATUS"] = x.SUCCESS_B
    elif mutation == "ledger":
        x.object_row(x.rows(changed["FINAL_RESOLVED_LEDGER"])[0])["CURRENT_BOUND"] = 313_649_607
    elif mutation == "proof":
        x.object_row(x.rows(changed["GROUP_ATTEMPTS"])[1])["OPEN_WEDGE_CEILING_REFUTED"] = 0
    else:
        x.object_row(x.rows(changed["GROUP_ATTEMPTS"])[1])["PROFILE_IDS"] = [
            profile_id(x.NEXT_CURSOR_PROFILE)
        ]
    with pytest.raises(AssertionError):
        x.replay_sibling(r25, changed, digest)


def test_route_d_full_ticket_lemma() -> None:
    assert x.full_ticket_open_wedge_floor(HARD_OWNER) == 4 * (78 - 66 - 6) == 24
    proof = x.lemma_proof((HARD_OWNER,), 270)
    assert proof is not None
    assert proof["OPEN_WEDGE_CEILING_REFUTED"] == 834 - 3 * 271 == 21
    assert x.accepted_cap(proof, (HARD_OWNER,), 270) == 270
    # 24 forced open wedges cannot refute a 24-wedge ceiling (cap 269).
    assert x.lemma_proof((HARD_OWNER,), 269) is None
    assert all(x.full_ticket_open_wedge_floor(p) is None for p in x.OWNERS)
    forged = {**proof, "PROFILE_IDS": [x.OWNER_IDS[0]]}
    with pytest.raises(AssertionError):
        x.accepted_cap(forged, (x.OWNERS[0],), 270)


def test_route_d_agrees_with_exact_support_model() -> None:
    model, *_ = x.batch.union_support_model((HARD_OWNER,), 23)
    solver = x.configured_solver(30.0, x.CP_SAT_WORKERS)
    assert solver.StatusName(solver.Solve(model)) == "INFEASIBLE"


@pytest.mark.parametrize("status", ["FEASIBLE", "OPTIMAL", "UNKNOWN", "EXTERNAL_TIMEOUT"])
def test_feasible_is_never_a_refutation(status: str) -> None:
    proof = synthetic((HARD_OWNER,), 270)
    proof["STATUS"] = status
    assert x.accepted_cap(proof, (HARD_OWNER,), 270) is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("ROUTE", "FEASIBLE_OBJECTIVE"),
        ("CERTIFICATE_KIND", x.KIND_D),
        ("CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND", 269),
        ("REFUTED_GRAPH_TRIANGLE_COUNT", 270),
        ("OPEN_WEDGE_CEILING_REFUTED", 24),
        ("PROFILE_IDS", ["66655555555530000000"]),
    ],
)
def test_refutation_identity(field: str, value: object) -> None:
    proof = synthetic((HARD_OWNER,), 270)
    proof[field] = value
    with pytest.raises(AssertionError, match="identity"):
        x.accepted_cap(proof, (HARD_OWNER,), 270)


def test_complete_ledger_recomputed_to_success_b(state: x.batch.State) -> None:
    calls: list[tuple[x.DegreeProfile, ...]] = []

    def prove(
        group: Sequence[Certificate], bounds: Mapping[x.DegreeProfile, int], cap: int
    ) -> dict[str, object]:
        profiles = tuple(c.profile for c in group)
        x.assert_solver_scope(profiles, bounds)
        calls.append(profiles)
        return synthetic(profiles, cap)

    result = x.run_chase(state, prove)
    assert result["TASK_STATUS"] == x.SUCCESS_B
    assert result["FAMILY_UPPER_BOUND"] == x.NEXT_CURSOR_BOUND
    assert result["CURRENT_BOUND_OWNER_SET"] == [profile_id(x.NEXT_CURSOR_PROFILE)]
    assert result["REMAINING_RESOLVED_ABOVE_CURSOR_COUNT"] == 0
    assert all(x.NEXT_CURSOR_PROFILE not in c for c in calls)
    assert len(calls) == 13
    steps = [x.object_row(s) for s in x.rows(result["GROUP_REFINEMENT_STEPS"])]
    assert all(s["COMPLETE_LEDGER_ROW_COUNT"] == 408 for s in steps)
    assert [s["RESOLVED_ABOVE_CURSOR_AFTER"] for s in steps][-1] == 0
    ledger = {
        x.decode_profile(r["PROFILE_ID"]): x.integer(r["CURRENT_BOUND"])
        for r in map(x.object_row, x.rows(result["FINAL_RESOLVED_LEDGER"]))
    }
    assert len(ledger) == 408 and max(ledger.values()) <= x.NEXT_CURSOR_BOUND
    assert all(ledger[p] == 313_626_760 for p in x.OWNERS)


def test_newly_exposed_owner_switch(state: x.batch.State) -> None:
    calls: list[tuple[x.DegreeProfile, ...]] = []

    def prove(
        group: Sequence[Certificate], bounds: Mapping[x.DegreeProfile, int], cap: int
    ) -> dict[str, object]:
        profiles = tuple(c.profile for c in group)
        x.assert_solver_scope(profiles, bounds)
        calls.append(profiles)
        if len(calls) == 1:
            return synthetic(profiles, cap)
        return {
            "STATUS": "PROOF_BUDGET_EXHAUSTED",
            "PROFILE_IDS": [profile_id(p) for p in profiles],
        }

    result = x.run_chase(state, prove)
    assert calls[0] == (HARD_OWNER,)
    assert len(calls[1]) == 55
    assert result["TASK_STATUS"] == x.SUCCESS_C
    assert result["FAMILY_UPPER_BOUND"] == 313_649_048
    assert result["REMAINING_RESOLVED_ABOVE_CURSOR_COUNT"] == 136
    assert len(x.rows(result["CURRENT_BOUND_OWNER_SET"])) == 55


def test_no_drop_cannot_claim_success(state: x.batch.State) -> None:
    result = x.run_chase(state, lambda _g, _b, _c: {"STATUS": "FEASIBLE"})
    assert result["TASK_STATUS"] == x.NO_DROP
    assert result["FAMILY_UPPER_BOUND"] == 313_649_608
    assert result["GROUP_REFINEMENT_STEPS"] == []


def test_no_cursor_work_guard(state: x.batch.State) -> None:
    with pytest.raises(AssertionError, match="current resolved"):
        x.assert_solver_scope((x.NEXT_CURSOR_PROFILE,), state.bounds)
    with pytest.raises(AssertionError, match="current resolved"):
        x.assert_solver_scope((x.OWNERS[0],), state.bounds)
    with pytest.raises(AssertionError, match="forbidden"):
        x.batch.union_support_model((x.NEXT_CURSOR_PROFILE,), 1)
    result = x.run_chase(state, always)
    assert x.NEXT_CURSOR_PROFILE not in {
        x.decode_profile(r["PROFILE_ID"])
        for r in map(x.object_row, x.rows(result["FINAL_RESOLVED_LEDGER"]))
    }


def test_sealed_result_replays_to_its_ledger(state: x.batch.State) -> None:
    path: Path = x.repo_root() / x.RESULT_DIRECTORY / x.RESULT_FILENAME
    sealed = x.object_row(json.loads(path.read_text()))
    assert (sealed["BASE_HEAD"], sealed["PACKET_BASE_HEAD"]) == (x.BASE_HEAD, x.PACKET_BASE_HEAD)
    assert sealed["CANONICAL_PRIMITIVES"] == x.canonical_primitive_preflight()
    assert x.object_row(sealed["PROOF_CONFIG_NONVACUITY"])["STATUS"] == "PASS"
    assert x.object_row(sealed["SIX_OWNER_REPRODUCTION"])["STATUS"] == "PASS"
    assert sealed["CURSOR_PROFILE_SOLVES"] == 0 and sealed["NO_CURSOR_WORK_GUARD"] == "PASS"
    bounds = dict(state.bounds)
    for raw in x.rows(sealed["GROUP_ATTEMPTS"]):
        attempt = x.object_row(raw)
        profiles = tuple(x.decode_profile(p) for p in x.rows(attempt["PROFILE_IDS"]))
        x.assert_solver_scope(profiles, bounds)
        cap = x.integer(attempt["TARGET_TRIANGLE_CAP"])
        if x.accepted_cap(attempt, profiles, cap) is None:
            continue
        for p in profiles:
            bounds[p] = x.crossing_bound(replace(state.certificates[p], bound=bounds[p]), cap)[1]
    observed = {
        x.decode_profile(r["PROFILE_ID"]): x.integer(r["CURRENT_BOUND"])
        for r in map(x.object_row, x.rows(sealed["FINAL_RESOLVED_LEDGER"]))
    }
    assert observed == bounds
    family, owners = x.family_state(observed)
    above = [p for p, b in observed.items() if b > x.NEXT_CURSOR_BOUND]
    assert sealed["FAMILY_UPPER_BOUND"] == family
    assert sealed["MAX_RESOLVED_BOUND"] == max(observed.values())
    assert sealed["CURRENT_BOUND_OWNER_SET"] == list(map(profile_id, owners))
    assert sealed["REMAINING_RESOLVED_ABOVE_CURSOR_COUNT"] == len(above)
    assert sealed["REMAINING_GAP"] == family - x.INCUMBENT
    assert sealed["TASK_STATUS"] == (x.SUCCESS_B if not above else x.SUCCESS_C)
    assert cast(float, sealed["PROOF_ACTUAL_WALL_SECONDS"]) <= 3600
