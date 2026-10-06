"""R24 committed-ledger reconstruction, handoff-owner resolution and owner-only gates."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from dataclasses import replace
from typing import cast

import pytest

from lottolab.research import b649_k20_min_s2_owner_ledger_reconcile_and_refine_r24 as r24

DegreeProfile = tuple[int, ...]
OWNER = r24.decode_profile(r24.HANDOFF_OWNER_FIELD)
OLD_PAIR = tuple(r24.decode_profile(p) for p in r24.HANDOFF_OWNER_SET_FIELD)
REFINED_OWNER_BOUND = 313_642_104


@pytest.fixture(scope="module")
def inputs() -> dict[str, dict[str, object]]:
    return r24.committed_inputs()[0]


@pytest.fixture(scope="module")
def state() -> r24.CurrentState:
    return r24.current_state()


def lowered_attempt(cert: r24.Certificate, bound: int = REFINED_OWNER_BOUND) -> dict[str, object]:
    assert cert.triangle_cap is not None and cert.s3 is not None
    return {
        "PROFILE_ID": r24.profile_id(cert.profile),
        "CERTIFIED_OWNER_BOUND": bound,
        "REFINED_TRIANGLE_CAP": cert.triangle_cap - 1,
        "REFINED_S3": cert.s3 - 11_872,
    }


def synthetic(state: r24.CurrentState, extra: Mapping[DegreeProfile, int]) -> r24.CurrentState:
    """Raise below-cursor profiles into the owner zone, reusing the owner's certificate."""

    bounds = {**state.bounds, **extra}
    certificates = dict(state.certificates)
    for profile, bound in extra.items():
        certificates[profile] = replace(state.certificates[OWNER], profile=profile, bound=bound)
    return replace(state, bounds=bounds, certificates=certificates)


def below_cursor_profiles(state: r24.CurrentState, count: int) -> list[DegreeProfile]:
    return [p for p, b in state.bounds.items() if b < r24.CURSOR_BOUND][:count]


def test_canonical_primitives_and_complete_committed_ledger(
    state: r24.CurrentState, inputs: dict[str, dict[str, object]]
) -> None:
    assert r24.canonical_primitive_preflight() == {
        "STATUS": "PASS",
        "SINGLE_TICKET_ANY_PRIZE": 18_611_432,
        "K20_S1": 372_228_640,
    }
    assert (r24.K20_S1, r24.K20_S2) == (372_228_640, 63_838_600)
    rows = cast(list[dict[str, object]], inputs["R22"]["FINAL_RESOLVED_LEDGER"])
    expected = {r24.decode_profile(row["PROFILE_ID"]): row["CURRENT_BOUND"] for row in rows}
    plateau = cast(list[dict[str, object]], inputs["R23"]["CLASS_CERTIFICATES"])[0]
    for raw in cast(list[object], plateau["PROFILE_IDENTITIES"]):
        expected[r24.decode_profile(raw)] = 313_631_576
    assert state.bounds == expected
    assert len(state.bounds) == 408
    assert r24.family_state(state.bounds) == (313_653_976, (OWNER,))
    assert r24.CURSOR_PROFILE not in state.bounds
    assert r24.profile_id(r24.CURSOR_PROFILE) == "66666665432211111111"
    assert state.carriers[OWNER] == "R22.FINAL_RESOLVED_LEDGER[0]"
    assert max(b for b in state.bounds.values() if b < r24.CURSOR_BOUND) == 313_651_848


@pytest.mark.parametrize(
    ("label", "key", "value", "recomputed"),
    (
        ("R23", "FAMILY_UPPER_BOUND", 313_653_975, 313_653_976),
        ("R22", "ROW0_BOUND", 313_653_977, 313_653_977),
    ),
)
def test_family_bound_recomputation_stops_with_exact_mismatch(
    inputs: dict[str, dict[str, object]], label: str, key: str, value: int, recomputed: int
) -> None:
    broken = copy.deepcopy(inputs)
    if key == "ROW0_BOUND":
        cast(list[dict[str, object]], broken["R22"]["FINAL_RESOLVED_LEDGER"])[0][
            "CURRENT_BOUND"
        ] = value
    else:
        broken[label][key] = value
    with pytest.raises(AssertionError, match=f"recomputed {recomputed}, packet 313653976"):
        r24.reconstruct_state(broken, {})


def test_handoff_owner_inconsistency_regression(
    state: r24.CurrentState, inputs: dict[str, dict[str, object]]
) -> None:
    handoff = state.handoff
    assert handoff["AUTHORITATIVE_CURRENT_BOUND_OWNER_SET"] == ["66655555555511100000"]
    assert handoff["HANDOFF_OWNER_FIELD_STATUS"] == (
        "AUTHORITATIVE_MATCHES_RECOMPUTED_FAMILY_MAXIMUM"
    )
    assert handoff["HANDOFF_OWNER_SET_FIELD_STATUS"] == "NOT_CURRENT_OWNERS_REJECTED"
    assert handoff["HANDOFF_OWNER_SET_FIELD_CURRENT_BOUNDS"] == {
        "66665555555411100000": 313_644_904,
        "66655555555521000000": 313_644_904,
    }
    assert all(state.bounds[p] < r24.CURSOR_BOUND for p in OLD_PAIR)
    r24.assert_owner_claim((r24.HANDOFF_OWNER_FIELD,), state.bounds)
    with pytest.raises(AssertionError, match="not the family maximum 313653976"):
        r24.assert_owner_claim(r24.HANDOFF_OWNER_SET_FIELD, state.bounds)
    with pytest.raises(AssertionError, match="not the family maximum"):
        r24.assert_owner_claim(
            (r24.HANDOFF_OWNER_FIELD, *r24.HANDOFF_OWNER_SET_FIELD), state.bounds
        )
    broken = copy.deepcopy(inputs)
    broken["R23"]["CURRENT_BOUND_OWNER_SET"] = list(r24.HANDOFF_OWNER_SET_FIELD)
    with pytest.raises(AssertionError, match="do not resolve to one committed owner set"):
        r24.reconstruct_state(broken, {})


def test_owner_certificate_exact_committed_provenance(state: r24.CurrentState) -> None:
    (row,) = state.above_cursor
    assert {k: row[k] for k in ("PROFILE_ID", "BOUND", "SOURCE_RESULT", "SOURCE_ROW")} == {
        "PROFILE_ID": "66655555555511100000",
        "BOUND": 313_653_976,
        "SOURCE_RESULT": "b649-k20-min-s2-resolved-above-cursor-owner-chase-r20-result.json",
        "SOURCE_ROW": "OWNER_ATTEMPTS[2]",
    }
    assert (row["REALIZABILITY_STATUS"], row["CERTIFICATE_KIND"]) == (
        "REALIZABLE",
        "CP_SAT_INFEASIBLE",
    )
    assert row["LEDGER_CARRIER"] == "R22.FINAL_RESOLVED_LEDGER[0]"
    cert = state.certificates[OWNER]
    assert (cert.bound, cert.s3, cert.s4, cert.triangle_cap) == (313_653_976, 5_264_000, 112, 272)
    assert cert.witness_source == "R12.PROFILE_BOUNDS[30]"
    assert r24.bound_from_cap(OWNER, 272, 112) == (5_264_000, 313_653_976)
    assert r24.bound_from_cap(OWNER, 271, 112) == (5_252_128, REFINED_OWNER_BOUND)
    assert REFINED_OWNER_BOUND < r24.CURSOR_BOUND
    assert r24.overlap_wedge_count(OWNER) == 831
    triples, doubles = r24.support_witness(cert)
    assert (len(triples), len(doubles)) == (22, 27)


def test_no_omitted_resolved_above_cursor_assertion(state: r24.CurrentState) -> None:
    r24.assert_no_omitted_above_cursor(state.bounds, state.above_cursor)
    with pytest.raises(AssertionError, match="omitted or invented"):
        r24.assert_no_omitted_above_cursor(state.bounds, ())
    for raised in (r24.CURSOR_BOUND, 313_653_000, r24.START_BOUND):
        lower = below_cursor_profiles(state, 1)[0]
        bounds = {**state.bounds, lower: raised}
        with pytest.raises(AssertionError, match="omitted or invented"):
            r24.assert_no_omitted_above_cursor(bounds, state.above_cursor)
    wrong = ({**state.above_cursor[0], "BOUND": r24.START_BOUND - 1},)
    with pytest.raises(AssertionError, match="differs from the ledger"):
        r24.assert_no_omitted_above_cursor(state.bounds, wrong)


@pytest.mark.parametrize("raised", (313_652_520, 313_653_000, 313_653_976))
def test_uncertified_resolved_profile_above_cursor_stops_reconstruction(
    inputs: dict[str, dict[str, object]], raised: int
) -> None:
    broken = copy.deepcopy(inputs)
    rows = cast(list[dict[str, object]], broken["R22"]["FINAL_RESOLVED_LEDGER"])
    rows[1]["CURRENT_BOUND"] = raised
    with pytest.raises(AssertionError, match="lacks a committed owner certificate"):
        r24.reconstruct_state(broken, {})


def test_tied_owner_switch_then_cursor_success_b(state: r24.CurrentState) -> None:
    tied = below_cursor_profiles(state, 1)[0]
    trial = synthetic(state, {tied: r24.START_BOUND})
    calls: list[DegreeProfile] = []

    def refine(cert: r24.Certificate, bounds: Mapping[DegreeProfile, int]) -> dict[str, object]:
        r24.assert_solver_scope(cert.profile, bounds)
        calls.append(cert.profile)
        return lowered_attempt(cert)

    outcome = r24.run_schedule(trial, refine)
    assert tuple(calls) == tuple(sorted((OWNER, tied), reverse=True))
    assert outcome.status == r24.SUCCESS_B
    assert outcome.family_bound == r24.CURSOR_BOUND
    assert outcome.owners == (r24.CURSOR_PROFILE,)
    first, second = outcome.steps
    assert first["FAMILY_BOUND_AFTER"] == r24.START_BOUND
    assert first["OWNER_SET_AFTER"] == [r24.profile_id(calls[1])]
    assert second["RESOLVED_AT_OR_ABOVE_CURSOR_AFTER"] == []


def test_different_resolved_maximum_switches_immediately(state: r24.CurrentState) -> None:
    other = below_cursor_profiles(state, 1)[0]
    trial = synthetic(state, {other: 313_653_000})
    calls: list[DegreeProfile] = []

    def refine(cert: r24.Certificate, bounds: Mapping[DegreeProfile, int]) -> dict[str, object]:
        r24.assert_solver_scope(cert.profile, bounds)
        calls.append(cert.profile)
        return lowered_attempt(cert)

    outcome = r24.run_schedule(trial, refine)
    assert calls == [OWNER, other]
    first = outcome.steps[0]
    assert (first["FAMILY_BOUND_BEFORE"], first["FAMILY_BOUND_AFTER"]) == (
        r24.START_BOUND,
        313_653_000,
    )
    assert first["OWNER_SET_AFTER"] == [r24.profile_id(other)]
    assert first["RESOLVED_AT_OR_ABOVE_CURSOR_AFTER"] == [
        {"PROFILE_ID": r24.profile_id(other), "BOUND": 313_653_000}
    ]
    assert outcome.status == r24.SUCCESS_B
    assert outcome.dispatched == (OWNER, other)


def test_uncertified_new_owner_stops_at_success_c_with_exact_owner(
    state: r24.CurrentState,
) -> None:
    other = below_cursor_profiles(state, 1)[0]
    trial = synthetic(state, {other: 313_653_000})

    def refine(cert: r24.Certificate, _: Mapping[DegreeProfile, int]) -> dict[str, object]:
        if cert.profile == OWNER:
            return lowered_attempt(cert)
        return {"PROFILE_ID": r24.profile_id(cert.profile), "CERTIFIED_OWNER_BOUND": None}

    outcome = r24.run_schedule(trial, refine)
    assert outcome.status == r24.SUCCESS_C
    assert (outcome.family_bound, outcome.owners) == (313_653_000, (other,))
    assert len(outcome.attempts) == 2


def test_owner_budget_and_no_drop(state: r24.CurrentState, monkeypatch: pytest.MonkeyPatch) -> None:
    other = below_cursor_profiles(state, 1)[0]
    trial = synthetic(state, {other: 313_653_000})
    monkeypatch.setattr(r24, "MAX_OWNER_PROFILES", 1)
    outcome = r24.run_schedule(trial, lambda c, _: lowered_attempt(c))
    assert outcome.status == r24.SUCCESS_C
    assert outcome.dispatched == (OWNER,)
    monkeypatch.undo()
    stuck = r24.run_schedule(
        state, lambda c, _: {"PROFILE_ID": r24.profile_id(c.profile), "CERTIFIED_OWNER_BOUND": None}
    )
    assert stuck.status == r24.NO_DROP
    assert stuck.bounds == state.bounds
    assert not stuck.steps


def test_no_cursor_work_guard(state: r24.CurrentState) -> None:
    with pytest.raises(AssertionError, match="cursor/profile work forbidden"):
        r24.assert_solver_scope(r24.CURSOR_PROFILE, state.bounds)
    with pytest.raises(AssertionError, match="cursor must remain unresolved"):
        r24.family_state({**state.bounds, r24.CURSOR_PROFILE: r24.CURSOR_BOUND})
    for profile in (*OLD_PAIR, below_cursor_profiles(state, 1)[0]):
        with pytest.raises(AssertionError, match="current max/tied max"):
            r24.assert_solver_scope(profile, state.bounds)
    lowered = {**state.bounds, OWNER: REFINED_OWNER_BOUND}
    with pytest.raises(AssertionError, match="current max/tied max"):
        r24.assert_solver_scope(OWNER, lowered)
    r24.assert_solver_scope(OWNER, state.bounds)
    request: dict[str, object] = {
        "PROFILE_ID": r24.profile_id(r24.CURSOR_PROFILE),
        "ROUTE": r24.ROUTES[0],
        "TRIANGLE_CAP": 272,
        "EFFECTIVE_BOUNDS": {r24.profile_id(p): b for p, b in state.bounds.items()},
    }
    with pytest.raises(AssertionError, match="cursor/profile work forbidden"):
        r24.solver_child(request)


@pytest.mark.parametrize("kind", ("weakened", "non_owner", "wrong_cap"))
def test_solver_child_rejects_invalid_requests_before_solving(
    state: r24.CurrentState, kind: str
) -> None:
    bounds = {r24.profile_id(p): b for p, b in state.bounds.items()}
    cap = 272
    if kind == "weakened":
        bounds[r24.HANDOFF_OWNER_FIELD] = r24.START_BOUND + 1
    elif kind == "non_owner":
        bounds[r24.HANDOFF_OWNER_SET_FIELD[0]] -= 1
    else:
        cap = 271
    request: dict[str, object] = {
        "PROFILE_ID": r24.HANDOFF_OWNER_FIELD,
        "ROUTE": r24.ROUTES[0],
        "TRIANGLE_CAP": cap,
        "EFFECTIVE_BOUNDS": bounds,
    }
    with pytest.raises(AssertionError):
        r24.solver_child(request)


@pytest.mark.parametrize("status", ("FEASIBLE", "OPTIMAL", "UNKNOWN", "EXTERNAL_HARD_TIMEOUT"))
def test_feasible_or_unproved_cap_is_never_a_refutation(status: str) -> None:
    assert (
        r24.accepted_refutation_cap(
            {"STATUS": status, "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": 271}, 272
        )
        is None
    )
    with pytest.raises(AssertionError, match="identity mismatch"):
        r24.accepted_refutation_cap(
            {
                "STATUS": "INFEASIBLE",
                "CERTIFICATE_KIND": "CP_SAT_INFEASIBLE",
                "REFUTED_GRAPH_TRIANGLE_COUNT": 273,
                "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": 272,
            },
            272,
        )


@pytest.mark.parametrize("route_a", ("INFEASIBLE", "UNKNOWN"))
def test_refine_owner_accepts_only_certified_routes(
    state: r24.CurrentState, monkeypatch: pytest.MonkeyPatch, route_a: str
) -> None:
    def fake_call(
        cert: r24.Certificate, bounds: Mapping[DegreeProfile, int], route: str, *, deadline: float
    ) -> dict[str, object]:
        del bounds, deadline
        if route == "WITNESS":
            return {"STATUS": "PASS"}
        if route == r24.ROUTES[0] and route_a == "INFEASIBLE":
            return {
                "ROUTE": route,
                "STATUS": "INFEASIBLE",
                "CERTIFICATE_KIND": "CP_SAT_INFEASIBLE",
                "REFUTED_GRAPH_TRIANGLE_COUNT": cert.triangle_cap,
                "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": cast(int, cert.triangle_cap) - 1,
            }
        return {"ROUTE": route, "STATUS": "FEASIBLE", "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": 200}

    monkeypatch.setattr(r24, "bounded_solver_call", fake_call)
    attempt = r24.refine_owner(state.certificates[OWNER], state.bounds, deadline=0.0)
    if route_a == "INFEASIBLE":
        assert attempt["CERTIFIED_OWNER_BOUND"] == REFINED_OWNER_BOUND
        assert (attempt["REFINED_TRIANGLE_CAP"], attempt["REFINED_S3"]) == (271, 5_252_128)
        assert len(cast(list[object], attempt["ROUTES"])) == 1
    else:
        assert attempt["CERTIFIED_OWNER_BOUND"] is None
        assert len(cast(list[object], attempt["ROUTES"])) == 3


def test_sealed_result_reproduces_from_committed_ledger(state: r24.CurrentState) -> None:
    result = cast(dict[str, object], json.loads(r24.result_path().read_text()))
    assert result["TASK_STATUS"] == r24.SUCCESS_B
    assert result["BASE_HEAD"] == r24.BASE_HEAD
    assert result["COMMITTED_INPUT_SHA256"] == dict(state.input_hashes)
    assert result["AUTHORITATIVE_CURRENT_BOUND_OWNER_SET"] == [r24.HANDOFF_OWNER_FIELD]
    assert result["RESOLVED_AT_OR_ABOVE_CURSOR_PROFILES"] == list(state.above_cursor)
    (attempt,) = cast(list[dict[str, object]], result["OWNER_ATTEMPTS"])
    (proof,) = cast(list[dict[str, object]], attempt["ROUTES"])
    assert r24.accepted_refutation_cap(proof, 272) == 271
    assert proof["OPEN_WEDGE_CEILING_REFUTED"] == 831 - 3 * 272
    assert r24.bound_from_cap(OWNER, 271, 112) == (attempt["REFINED_S3"], REFINED_OWNER_BOUND)
    final = {
        r24.decode_profile(row["PROFILE_ID"]): cast(int, row["CURRENT_BOUND"])
        for row in cast(list[dict[str, object]], result["FINAL_RESOLVED_LEDGER"])
    }
    assert final == {**state.bounds, OWNER: REFINED_OWNER_BOUND}
    assert r24.family_state(final) == (r24.CURSOR_BOUND, (r24.CURSOR_PROFILE,))
    assert r24.at_or_above_cursor(final) == ()
    assert result["FAMILY_UPPER_BOUND"] == r24.CURSOR_BOUND
    assert result["CURRENT_BOUND_OWNER_SET"] == ["66666665432211111111"]
    assert result["REMAINING_GAP"] == r24.CURSOR_BOUND - r24.INCUMBENT == 412_859
    assert result["SOLVER_PROFILES_SENT"] == [r24.HANDOFF_OWNER_FIELD]
    assert result["CURSOR_PROFILE_SOLVES"] == 0
