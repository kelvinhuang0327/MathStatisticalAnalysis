"""Exact R22 lineage, full-ledger switching and cursor/proof dispatch gates."""

from __future__ import annotations

import copy
import json
import subprocess
from collections.abc import Mapping
from dataclasses import replace
from typing import cast

import pytest

from lottolab.research import b649_k20_min_s2_resolved_owner_pair_refinement_r22 as r22

DegreeProfile = tuple[int, ...]


@pytest.fixture(scope="module")
def inputs() -> dict[str, dict[str, object]]:
    return r22.committed_inputs()[0]


@pytest.fixture(scope="module")
def state() -> r22.CurrentState:
    return r22.current_state()


def certified_attempt(cert: r22.Certificate) -> dict[str, object]:
    assert cert.triangle_cap is not None and cert.s4 is not None
    s3, bound = r22.bound_from_cap(cert.profile, cert.triangle_cap - 1, cert.s4)
    return {
        "PROFILE_ID": r22.profile_id(cert.profile),
        "CERTIFIED_OWNER_BOUND": bound,
        "REFINED_TRIANGLE_CAP": cert.triangle_cap - 1,
        "REFINED_S3": s3,
    }


def test_canonical_primitives_and_exact_complete_ledger(
    state: r22.CurrentState, inputs: dict[str, dict[str, object]]
) -> None:
    assert r22.canonical_primitive_preflight() == {
        "STATUS": "PASS",
        "SINGLE_TICKET_ANY_PRIZE": 18_611_432,
        "K20_S1": 372_228_640,
    }
    assert (r22.K20_S1, r22.K20_S2) == (372_228_640, 63_838_600)
    rows = cast(list[dict[str, object]], inputs["R20"]["FINAL_RESOLVED_LEDGER"])
    expected = {r22.decode_profile(row["PROFILE_ID"]): row["CURRENT_BOUND"] for row in rows}
    plateau = cast(list[dict[str, object]], inputs["R21"]["CLASS_CERTIFICATES"])[0]
    for raw in cast(list[object], plateau["PROFILE_IDENTITIES"]):
        expected[r22.decode_profile(raw)] = 313_646_248
    assert state.bounds == expected
    assert len(state.bounds) == 339
    assert r22.family_state(state.bounds) == (313_656_776, r22.OWNER_PROFILES)
    assert {p for p, b in state.bounds.items() if b > r22.CURSOR_BOUND} == set(r22.OWNER_PROFILES)
    assert r22.CURSOR_PROFILE not in state.bounds
    assert r22.CURSOR_BOUND == 313_655_320
    assert r22.profile_id(r22.CURSOR_PROFILE) == "66666665433111111111"


@pytest.mark.parametrize("index", (0, 1))
def test_owner_certificate_exact_lineage_and_witness(state: r22.CurrentState, index: int) -> None:
    profile = r22.OWNER_PROFILES[index]
    cert = state.owners[profile]
    lineage = state.lineage[index]
    assert (cert.bound, cert.s3, cert.s4, cert.triangle_cap) == (313_656_776, 5_266_800, 112, 272)
    assert r22.bound_from_cap(profile, 272, 112) == (5_266_800, 313_656_776)
    assert r22.bound_from_cap(profile, 271, 112) == (5_254_928, 313_644_904)
    assert cert.source_row == f"OWNER_ATTEMPTS[{index}]"
    assert cert.witness_source == f"R12.PROFILE_BOUNDS[{(8, 10)[index]}]"
    triples, doubles = r22.support_witness(cert)
    assert (len(triples), len(doubles)) == (22, 27)
    assert lineage["DEGREE_PROFILE"] == list(profile)
    assert lineage["NONCORE_TRIANGLE_CAP"] == 250
    assert lineage["OPEN_WEDGE_FLOOR"] == 16
    assert lineage["EXACT_RELAXATION"] == {
        "IDENTITY": "S1 - S2 + S3 - floor(4*S4/7)",
        "S1": 372_228_640,
        "S2": 63_838_600,
        "S3": 5_266_800,
        "S4_FLOOR": 112,
        "VALUE": 313_656_776,
    }


@pytest.mark.parametrize("third_bound", (313_656_776, 313_655_321))
def test_no_third_owner_assertion_rejects_tie_and_above_cursor(
    state: r22.CurrentState, third_bound: int
) -> None:
    bounds = dict(state.bounds)
    third = next(p for p in bounds if p not in state.owners)
    bounds[third] = third_bound
    with pytest.raises(AssertionError, match=r"two-owner|third resolved"):
        r22.assert_exact_owner_pair(bounds)


def test_incomplete_duplicate_and_cursor_ledgers_fail(state: r22.CurrentState) -> None:
    missing = dict(state.bounds)
    missing.pop(r22.OWNER_PROFILES[0])
    with pytest.raises(AssertionError, match="ledger count"):
        r22.assert_exact_owner_pair(missing)
    with pytest.raises(AssertionError, match="cursor must remain unresolved"):
        r22.family_state({**state.bounds, r22.CURSOR_PROFILE: r22.CURSOR_BOUND})


@pytest.mark.parametrize("kind", ("duplicate", "false_cap", "wrong_cursor", "incomplete_plateau"))
def test_reconstruction_rejects_corrupted_lineage(
    inputs: dict[str, dict[str, object]], kind: str
) -> None:
    broken = copy.deepcopy(inputs)
    if kind == "duplicate":
        rows = cast(list[dict[str, object]], broken["R20"]["FINAL_RESOLVED_LEDGER"])
        rows[1] = dict(rows[0])
    elif kind == "false_cap":
        attempts = cast(list[dict[str, object]], broken["R20"]["OWNER_ATTEMPTS"])
        attempts[0]["REFINED_TRIANGLE_CAP"] = 271
    elif kind == "wrong_cursor":
        broken["R21"]["NEXT_ACTIVE_PROFILE"] = r22.OWNER_IDS[0]
    else:
        classes = cast(list[dict[str, object]], broken["R21"]["CLASS_CERTIFICATES"])
        cast(list[object], classes[0]["PROFILE_IDENTITIES"]).pop()
    with pytest.raises(AssertionError):
        r22.reconstruct_state(broken, {})


def test_owner_switch_regression_stops_at_cursor_and_preserves_every_other_bound(
    state: r22.CurrentState,
) -> None:
    calls: list[DegreeProfile] = []

    def refine(cert: r22.Certificate, bounds: Mapping[DegreeProfile, int]) -> dict[str, object]:
        r22.assert_solver_scope(cert.profile, bounds)
        assert bounds[cert.profile] == max(bounds.values())
        calls.append(cert.profile)
        return certified_attempt(cert)

    outcome = r22.run_schedule(state, refine)
    assert tuple(calls) == r22.OWNER_PROFILES
    assert outcome.status == r22.SUCCESS_B
    assert outcome.family_bound == 313_655_320
    assert outcome.owners == (r22.CURSOR_PROFILE,)
    assert len(outcome.steps) == 2
    first, second = outcome.steps
    assert first["FAMILY_BOUND_AFTER"] == r22.START_BOUND
    assert first["OWNER_SET_AFTER"] == [r22.OWNER_IDS[1]]
    assert second["FAMILY_BOUND_AFTER"] == r22.CURSOR_BOUND
    assert second["OWNER_SET_AFTER"] == [r22.profile_id(r22.CURSOR_PROFILE)]
    for profile, bound in state.bounds.items():
        assert outcome.bounds[profile] == (313_644_904 if profile in state.owners else bound)


def test_success_c_identifies_new_resolved_maximum_and_stops(state: r22.CurrentState) -> None:
    bounds = dict(state.bounds)
    third = next(p for p in bounds if p not in state.owners)
    bounds[third] = r22.START_BOUND - 1
    synthetic = replace(state, bounds=bounds)
    outcome = r22.run_schedule(synthetic, lambda c, _: certified_attempt(c))
    assert outcome.status == r22.SUCCESS_C
    assert outcome.owners == (third,)
    assert outcome.family_bound == r22.START_BOUND - 1
    assert outcome.steps[-1]["OWNER_SET_AFTER"] == [r22.profile_id(third)]
    assert len(outcome.attempts) == 2


def test_uncertified_max_blocks_lower_owner_work(state: r22.CurrentState) -> None:
    calls: list[DegreeProfile] = []

    def refine(cert: r22.Certificate, _: Mapping[DegreeProfile, int]) -> dict[str, object]:
        calls.append(cert.profile)
        return {"PROFILE_ID": r22.profile_id(cert.profile), "CERTIFIED_OWNER_BOUND": None}

    outcome = r22.run_schedule(state, refine)
    assert tuple(calls) == r22.OWNER_PROFILES
    assert outcome.status == "NO_CERTIFIED_FAMILY_DROP"
    assert outcome.bounds == state.bounds
    assert outcome.family_bound == r22.START_BOUND
    assert not outcome.steps


def test_no_cursor_work_guard_at_dispatch_and_after_improvement(state: r22.CurrentState) -> None:
    with pytest.raises(AssertionError, match="cursor/profile work forbidden"):
        r22.assert_solver_scope(r22.CURSOR_PROFILE, state.bounds)
    lower = next(p for p in state.bounds if p not in state.owners)
    with pytest.raises(AssertionError, match="current max/tied max"):
        r22.assert_solver_scope(lower, state.bounds)
    bounds = {**state.bounds, r22.OWNER_PROFILES[0]: 313_644_904}
    with pytest.raises(AssertionError, match="current max/tied max"):
        r22.assert_solver_scope(r22.OWNER_PROFILES[0], bounds)
    r22.assert_solver_scope(r22.OWNER_PROFILES[1], bounds)


@pytest.mark.parametrize("status", ("FEASIBLE", "OPTIMAL", "UNKNOWN", "EXTERNAL_HARD_TIMEOUT"))
def test_feasible_or_unproved_cap_is_never_a_refutation(status: str) -> None:
    assert (
        r22.accepted_refutation_cap(
            {"STATUS": status, "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": 271}, 272
        )
        is None
    )


def test_infeasibility_certificate_must_refute_the_current_cap() -> None:
    proof = {
        "STATUS": "INFEASIBLE",
        "CERTIFICATE_KIND": "CP_SAT_INFEASIBLE",
        "REFUTED_GRAPH_TRIANGLE_COUNT": 272,
        "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": 271,
    }
    assert r22.accepted_refutation_cap(proof, 272) == 271
    with pytest.raises(AssertionError, match="identity mismatch"):
        r22.accepted_refutation_cap({**proof, "REFUTED_GRAPH_TRIANGLE_COUNT": 273}, 272)


def test_external_timeout_is_uncertified(
    state: r22.CurrentState, monkeypatch: pytest.MonkeyPatch
) -> None:
    def time_out(*args: object, **kwargs: object) -> object:
        assert kwargs["timeout"] == 90.0
        raise subprocess.TimeoutExpired("owner-test-child", 90)

    monkeypatch.setattr(r22.subprocess, "run", time_out)
    proof = r22.bounded_solver_call(
        state.owners[r22.OWNER_PROFILES[0]],
        state.bounds,
        r22.ROUTES[0],
        deadline=r22.monotonic() + 1000,
    )
    assert proof["STATUS"] == "EXTERNAL_HARD_TIMEOUT"
    assert r22.accepted_refutation_cap(proof, 272) is None
    assert proof["TERMINATION"] == "TASK_OWNED_CHILD_KILLED_AND_REAPED"


def test_native_refutation_limit_and_exact_profile_request(
    state: r22.CurrentState, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[DegreeProfile, int, float]] = []

    def refute(
        profile: DegreeProfile, *, refuted_triangle_count: int, wall_limit_seconds: float
    ) -> dict[str, object]:
        calls.append((profile, refuted_triangle_count, wall_limit_seconds))
        return {"STATUS": "UNKNOWN"}

    monkeypatch.setattr(r22, "exact_support_triangle_refutation", refute)
    request = {
        "PROFILE_ID": r22.OWNER_IDS[0],
        "ROUTE": r22.ROUTES[0],
        "EFFECTIVE_BOUNDS": {r22.profile_id(p): b for p, b in state.bounds.items()},
    }
    r22.solver_child(request)
    assert calls == [(r22.OWNER_PROFILES[0], 272, 60.0)]
    with pytest.raises(AssertionError, match="cursor/profile work forbidden"):
        r22.solver_child({**request, "PROFILE_ID": r22.profile_id(r22.CURSOR_PROFILE)})
    assert len(calls) == 1


def test_saved_proof_owner_pair_and_full_family_recomputation(state: r22.CurrentState) -> None:
    result = cast(dict[str, object], json.loads(r22.result_path().read_text()))
    assert result["TASK_STATUS"] == r22.SUCCESS_B
    assert result["OWNER_PROFILES"] == list(r22.OWNER_IDS)
    assert result["REFINED_OWNER_BOUNDS"] == dict.fromkeys(r22.OWNER_IDS, 313_644_904)
    assert result["FAMILY_UPPER_BOUND"] == r22.CURSOR_BOUND
    assert result["CURRENT_BOUND_OWNER_SET"] == [r22.profile_id(r22.CURSOR_PROFILE)]
    assert result["REMAINING_GAP"] == 415_659
    assert result["CURSOR_PROFILE_SOLVES"] == result["PLATEAU_RERUN_COUNT"] == 0
    rows = cast(list[dict[str, object]], result["FINAL_RESOLVED_LEDGER"])
    final = {r22.decode_profile(r["PROFILE_ID"]): cast(int, r["CURRENT_BOUND"]) for r in rows}
    assert len(final) == len(rows) == 339
    assert r22.family_state(final) == (r22.CURSOR_BOUND, (r22.CURSOR_PROFILE,))
    assert max(final.values()) == 313_653_976 < r22.CURSOR_BOUND
    for profile in state.bounds:
        assert final[profile] == (313_644_904 if profile in state.owners else state.bounds[profile])
    for step in cast(list[dict[str, object]], result["REFINEMENT_STEPS"]):
        attempt = cast(dict[str, object], step["CERTIFICATE"])
        routes = cast(list[dict[str, object]], attempt["ROUTES"])
        assert len(routes) == 1
        assert routes[0]["STATUS"] == "INFEASIBLE"
        assert routes[0]["REFUTED_GRAPH_TRIANGLE_COUNT"] == 272
        assert routes[0]["OPEN_WEDGE_CEILING_REFUTED"] == 16
        assert routes[0]["CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND"] == 271
        assert cast(dict[str, object], attempt["WITNESS_CHECK"])["STATUS"] == "PASS"


def resume_fixture(state: r22.CurrentState) -> dict[str, object]:
    cert = state.owners[r22.OWNER_PROFILES[0]]
    attempt = certified_attempt(cert)
    attempt["BOUND_LIMITING_RELAXATION"] = r22.ROUTES[0]
    attempt["ROUTES"] = [
        {
            "STATUS": "INFEASIBLE",
            "CERTIFICATE_KIND": "CP_SAT_INFEASIBLE",
            "REFUTED_GRAPH_TRIANGLE_COUNT": 272,
            "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": 271,
        }
    ]
    bounds = {**state.bounds, cert.profile: 313_644_904}
    return {
        "TASK_ID": r22.TASK_ID,
        "BASE_HEAD": r22.BASE_HEAD,
        "TASK_STATUS": "NO_CERTIFIED_FAMILY_DROP",
        "COMMITTED_INPUT_SHA256": dict(state.input_hashes),
        "REFINEMENT_STEPS": [
            {
                "PROFILE_ID": r22.profile_id(cert.profile),
                "REFINED_OWNER_BOUND": 313_644_904,
                "CERTIFICATE": attempt,
            }
        ],
        "FINAL_RESOLVED_LEDGER": [
            {"PROFILE_ID": r22.profile_id(p), "CURRENT_BOUND": b} for p, b in bounds.items()
        ],
    }


def test_resume_never_reruns_already_improved_owner(state: r22.CurrentState) -> None:
    effective = replace(state, bounds=r22.resume_bounds(state, resume_fixture(state)))
    calls: list[DegreeProfile] = []

    def refine(cert: r22.Certificate, bounds: Mapping[DegreeProfile, int]) -> dict[str, object]:
        r22.assert_solver_scope(cert.profile, bounds)
        calls.append(cert.profile)
        return certified_attempt(cert)

    outcome = r22.run_schedule(effective, refine)
    assert calls == [r22.OWNER_PROFILES[1]]
    assert outcome.status == r22.SUCCESS_B
    assert outcome.bounds[r22.OWNER_PROFILES[0]] == 313_644_904


@pytest.mark.parametrize("kind", ("nonowner", "false_proof", "completed"))
def test_resume_rejects_uncertified_or_completed_state(state: r22.CurrentState, kind: str) -> None:
    previous = resume_fixture(state)
    if kind == "nonowner":
        rows = cast(list[dict[str, object]], previous["FINAL_RESOLVED_LEDGER"])
        row = next(r for r in rows if r["PROFILE_ID"] not in r22.OWNER_IDS)
        row["CURRENT_BOUND"] = 0
    elif kind == "false_proof":
        step = cast(list[dict[str, object]], previous["REFINEMENT_STEPS"])[0]
        attempt = cast(dict[str, object], step["CERTIFICATE"])
        cast(list[dict[str, object]], attempt["ROUTES"])[0]["STATUS"] = "FEASIBLE"
    else:
        previous["TASK_STATUS"] = r22.SUCCESS_B
    with pytest.raises(AssertionError):
        r22.resume_bounds(state, previous)


def test_extended_refutation_still_has_external_hard_timeout(
    state: r22.CurrentState, monkeypatch: pytest.MonkeyPatch
) -> None:
    def time_out(*args: object, **kwargs: object) -> object:
        assert kwargs["timeout"] == 630.0
        raise subprocess.TimeoutExpired("extended-owner-test-child", 630)

    monkeypatch.setattr(r22.subprocess, "run", time_out)
    bounds = r22.resume_bounds(state, resume_fixture(state))
    proof = r22.bounded_solver_call(
        state.owners[r22.OWNER_PROFILES[1]],
        bounds,
        r22.ROUTES[0],
        deadline=r22.monotonic() + 1000,
        refutation_wall_seconds=600,
    )
    assert proof["STATUS"] == "EXTERNAL_HARD_TIMEOUT"
    assert proof["EXTERNAL_HARD_TIMEOUT_SECONDS"] == 630.0
    assert r22.accepted_refutation_cap(proof, 272) is None
