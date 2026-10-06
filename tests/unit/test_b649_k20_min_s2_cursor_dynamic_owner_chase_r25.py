"""R25 frozen plateau, complete resolved ledger, cheap-owner and cursor regressions."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from collections.abc import Mapping
from dataclasses import replace
from functools import cache
from math import comb
from typing import cast

import pytest

from lottolab.research import b649_k20_min_s2_class_dominance_or_descent_r13 as r13
from lottolab.research import b649_k20_min_s2_cursor_dynamic_owner_chase_r25 as r25

DegreeProfile = tuple[int, ...]
SURVIVOR = r25.decode_profile("66555555555511110000")
NEXT_OWNERS = (
    "66666665444322000000",
    "66666664444431000000",
    "66666655544411100000",
    "66666655544331000000",
    "66666555555311100000",
    "66666555554421000000",
)


@pytest.fixture(scope="module")
def inputs() -> dict[str, dict[str, object]]:
    return r25.committed_inputs()[0]


@pytest.fixture(scope="module")
def state() -> r25.State:
    return r25.current_state()


@pytest.fixture(scope="module")
def cheap_rows(state: r25.State) -> dict[DegreeProfile, dict[str, object]]:
    # A real independent run; no sealed result or preliminary 47/48 count is input.
    return {p: r25.cheap_certificate(state, p) for p in state.owners}


def cheap_from(
    certificates: Mapping[DegreeProfile, dict[str, object]],
) -> r25.Callable[[r25.State, DegreeProfile], dict[str, object]]:
    return lambda _state, p: certificates[p]


def lower_owner(p: DegreeProfile, cap: int = 272) -> dict[str, object]:
    s3, bound = r25.bound_from_cap(p, cap, 112)
    return {
        "PROFILE_ID": r25.profile_id(p),
        "CERTIFIED_OWNER_BOUND": bound,
        "REFINED_TRIANGLE_CAP": cap,
        "REFINED_S3": s3,
        "BOUND_LIMITING_RELAXATION": r25.ROUTES[0],
    }


def test_plateau_certificate_regression_without_individual_work() -> None:
    cert = r25.plateau_certificate()
    assert (cert["PLATEAU_PROFILE_COUNT"], cert["PLATEAU_SQUARE_SUM"]) == (76, 318)
    assert cert["PLATEAU_CLASS_BOUND"] == 313_628_776
    assert cert["INDIVIDUAL_PLATEAU_SOLVES"] == 0
    assert cert["PLATEAU_EXPLORATION_RERUN"] is False
    assert cert["NEXT_RANKED_CURSOR"] == 313_637_848
    # Independent wedge/congruence/S3 arithmetic, with the weakest degree-6 premise.
    wedges = (318 + 11 * 66 + 30 * 20) // 2
    assert wedges == 822 == sum(comb(6 + d, 2) for d in r25.INITIAL_CURSOR_PROFILE)
    assert r25.generic_open_wedge_floor(20, 93, 6, 12) == 5
    triangles = (wedges - 6) // 3
    assert triangles == 272
    s3 = 2_800 * (wedges - 3 * triangles) + 20_272 * (triangles - 22) + 7_000 * 22
    assert 372_228_640 - 63_838_600 + s3 - (4 * 112) // 7 == 313_628_776


def test_next_cursor_identity_is_one_greedy_suffix_without_census() -> None:
    @cache
    def feasible(slots: int, total: int, squares: int, cap: int) -> bool:
        if slots == 0:
            return total == squares == 0
        if not 0 <= total <= slots * cap or not total <= squares <= cap * total:
            return False
        return any(feasible(slots - 1, total - d, squares - d * d, d) for d in range(cap, -1, -1))

    profile: list[int] = []
    slots, total, squares, cap = 20, 66, 316, 6
    while slots:
        d = next(
            d for d in range(cap, -1, -1) if feasible(slots - 1, total - d, squares - d * d, d)
        )
        profile.append(d)
        slots, total, squares, cap = slots - 1, total - d, squares - d * d, d
    assert tuple(profile) == r25.NEXT_CURSOR_PROFILE
    assert r25.profile_id(tuple(profile)) == "66666665422221111111"
    assert r25.coarse_profile_envelope(profile).family_upper_bound == 313_637_848


def test_canonical_primitives_and_complete_committed_ledger(
    state: r25.State, inputs: dict[str, dict[str, object]]
) -> None:
    assert r25.canonical_primitive_preflight() == {
        "STATUS": "PASS",
        "SINGLE_TICKET_ANY_PRIZE": 18_611_432,
        "K20_S1": 372_228_640,
    }
    assert (r25.K20_S1, r25.K20_S2) == (372_228_640, 63_838_600)
    assert r25.k20_min_s2_s4_lower_bound_certificate().s4_lower_bound == 112
    ledger = cast(list[dict[str, object]], inputs["R24"]["FINAL_RESOLVED_LEDGER"])
    expected = {r25.decode_profile(r["PROFILE_ID"]): r["CURRENT_BOUND"] for r in ledger}
    assert state.bounds == expected
    assert len(state.bounds) == 408
    assert len(state.above_cursor) == 191
    assert r25.family_state(state.bounds) == (313_651_848, state.owners)
    assert r25.INITIAL_CURSOR_PROFILE not in state.bounds
    assert r25.NEXT_CURSOR_PROFILE not in state.bounds


def test_exact_48_owner_reconstruction_independent_sources(
    state: r25.State, inputs: dict[str, dict[str, object]]
) -> None:
    cert = cast(list[dict[str, object]], inputs["R16"]["CLASS_CERTIFICATES"])[0]
    independent = {r25.decode_profile(p) for p in cast(list[object], cert["PROFILE_IDENTITIES"])}
    assert set(state.owners) == independent
    assert len(independent) == 48
    assert {sum(d * d for d in p) for p in independent} == {326}
    assert {state.bounds[p] for p in independent} == {313_651_848}
    assert len(set(state.bounds) - independent) == 360


def test_independent_47_of_48_r13_refinement(
    state: r25.State, cheap_rows: dict[DegreeProfile, dict[str, object]]
) -> None:
    assert len(cheap_rows) == 48
    candidates = {p: cast(int, r["CERTIFIED_OWNER_BOUND"]) for p, r in cheap_rows.items()}
    refined = {p for p in state.owners if candidates[p] < state.bounds[p]}
    assert len(refined) == 47
    assert set(state.owners) - refined == {SURVIVOR}
    assert all(
        cast(dict[str, object], r["R13_RELAXATION"])["SOLVER_STATUS"] == "OPTIMAL"
        for r in cheap_rows.values()
    )
    assert all(r["INDEPENDENT_R16_CERTIFICATE_MATCH"] == "PASS" for r in cheap_rows.values())
    bounds = {**state.bounds, **candidates}
    assert bounds == r25.committed_cheap_bounds(state)
    assert r25.family_state(bounds) == (313_651_848, (SURVIVOR,))
    assert max(candidates[p] for p in refined) == 313_592_488 < r25.NEXT_CURSOR_BOUND


@pytest.mark.parametrize("defect", ("missing", "duplicate", "invented", "square_sum"))
def test_owner_set_completeness_rejects_changed_r16_input(
    inputs: dict[str, dict[str, object]], defect: str
) -> None:
    trial = copy.deepcopy(inputs)
    cert = cast(list[dict[str, object]], trial["R16"]["CLASS_CERTIFICATES"])[0]
    identities = cast(list[object], cert["PROFILE_IDENTITIES"])
    if defect == "missing":
        identities.pop()
    elif defect == "duplicate":
        identities[-1] = identities[0]
    elif defect == "invented":
        identities[-1] = list(r25.NEXT_CURSOR_PROFILE)
    else:
        cert["SQUARE_SUM"] = 324
    with pytest.raises(AssertionError, match="exact 48 resolved owners"):
        r25.reconstruct_state(trial, {})


def test_no_omitted_resolved_profile_above_next_cursor(state: r25.State) -> None:
    r25.assert_no_omitted_above_cursor(state.bounds, state.above_cursor)
    owners = set(state.owners)
    nonowners = [r for r in state.above_cursor if r25.decode_profile(r["PROFILE_ID"]) not in owners]
    assert len(nonowners) == 143
    omitted = tuple(r for r in state.above_cursor if r != nonowners[-1])
    with pytest.raises(AssertionError, match="omitted, invented or changed"):
        r25.assert_no_omitted_above_cursor(state.bounds, omitted)
    with pytest.raises(AssertionError, match="omitted, invented or changed"):
        r25.assert_no_omitted_above_cursor(
            state.bounds, (*state.above_cursor, state.above_cursor[0])
        )


def test_strong_refinement_switches_to_exact_six_owners_and_stops(
    state: r25.State, cheap_rows: dict[DegreeProfile, dict[str, object]]
) -> None:
    calls: list[DegreeProfile] = []

    def stronger(p: DegreeProfile, bounds: Mapping[DegreeProfile, int]) -> dict[str, object]:
        r25.assert_solver_scope(p, bounds)
        assert r25.family_state(bounds) == (313_651_848, (SURVIVOR,))
        calls.append(p)
        return lower_owner(p)

    outcome = r25.run_chase(state, cheap_from(cheap_rows), stronger)
    assert calls == [SURVIVOR]
    assert outcome.status == r25.SUCCESS_C
    assert outcome.family_bound == 313_650_504
    assert tuple(map(r25.profile_id, outcome.owners)) == NEXT_OWNERS
    assert len(outcome.steps) == 48
    assert all(s["FAMILY_BOUND_AFTER"] == 313_651_848 for s in outcome.steps[:-1])
    assert outcome.steps[-1]["FAMILY_BOUND_AFTER"] == 313_650_504
    assert outcome.bounds[SURVIVOR] == 313_639_976
    assert set(outcome.bounds) == set(state.bounds)
    assert all(outcome.bounds[p] == b for p, b in state.bounds.items() if p not in state.owners)


def test_tied_owner_switch_recomputes_before_each_dispatch(
    state: r25.State, cheap_rows: dict[DegreeProfile, dict[str, object]]
) -> None:
    other = state.owners[0]
    certificates = {
        **cheap_rows,
        other: {
            **cheap_rows[other],
            "CERTIFIED_OWNER_BOUND": r25.CHASE_START_BOUND,
            "STRICT_REFINEMENT": False,
        },
    }
    seen: list[tuple[DegreeProfile, tuple[DegreeProfile, ...]]] = []

    def stronger(p: DegreeProfile, bounds: Mapping[DegreeProfile, int]) -> dict[str, object]:
        r25.assert_solver_scope(p, bounds)
        seen.append((p, r25.family_state(bounds)[1]))
        return lower_owner(p)

    outcome = r25.run_chase(state, cheap_from(certificates), stronger)
    assert seen == [(other, (other, SURVIVOR)), (SURVIVOR, (SURVIVOR,))]
    assert outcome.status == r25.SUCCESS_C
    assert tuple(map(r25.profile_id, outcome.owners)) == NEXT_OWNERS


def test_plateau_drop_alone_is_not_owner_chase_success_c(
    state: r25.State, cheap_rows: dict[DegreeProfile, dict[str, object]]
) -> None:
    outcome = r25.run_chase(
        state,
        cheap_from(cheap_rows),
        lambda p, _b: {
            "PROFILE_ID": r25.profile_id(p),
            "CERTIFIED_OWNER_BOUND": None,
        },
    )
    assert outcome.status == r25.NO_DROP
    assert outcome.family_bound == r25.CHASE_START_BOUND
    assert outcome.dispatched == (SURVIVOR,)


def test_success_b_stops_before_any_unresolved_cursor_work(
    state: r25.State, cheap_rows: dict[DegreeProfile, dict[str, object]]
) -> None:
    bounds = {
        p: b if p in state.owners else min(b, r25.NEXT_CURSOR_BOUND - 1)
        for p, b in state.bounds.items()
    }
    trial = replace(state, bounds=bounds)
    outcome = r25.run_chase(trial, cheap_from(cheap_rows), lambda p, _b: lower_owner(p, 271))
    assert outcome.status == r25.SUCCESS_B
    assert outcome.family_bound == r25.NEXT_CURSOR_BOUND
    assert outcome.owners == (r25.NEXT_CURSOR_PROFILE,)
    assert outcome.dispatched == (SURVIVOR,)


@pytest.mark.parametrize("cursor", (r25.INITIAL_CURSOR_PROFILE, r25.NEXT_CURSOR_PROFILE))
def test_no_cursor_work_guard_before_model_construction(
    state: r25.State, monkeypatch: pytest.MonkeyPatch, cursor: DegreeProfile
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> dict[str, object]:
        pytest.fail("a forbidden cursor reached a support solver")

    monkeypatch.setattr(r25, "support_witness", forbidden)
    bounds = r25.committed_cheap_bounds(state)
    with pytest.raises(AssertionError, match="cursor/plateau work forbidden"):
        r25.assert_solver_scope(cursor, bounds)
    with pytest.raises(AssertionError, match="cursor/plateau work forbidden"):
        r25.solver_child(
            {
                "PROFILE_ID": r25.profile_id(cursor),
                "ROUTE": "WITNESS",
                "BOUNDS": {r25.profile_id(p): b for p, b in bounds.items()},
            }
        )


def test_strong_solver_rejects_stale_or_incomplete_ledgers(state: r25.State) -> None:
    with pytest.raises(AssertionError, match="exact complete post-cheap ledger"):
        r25.solver_child(
            {
                "PROFILE_ID": r25.profile_id(SURVIVOR),
                "ROUTE": "WITNESS",
                "BOUNDS": {r25.profile_id(p): b for p, b in state.bounds.items()},
            }
        )
    bounds = r25.committed_cheap_bounds(state)
    bounds.pop(state.owners[0])
    with pytest.raises(AssertionError, match="exact complete post-cheap ledger"):
        r25.solver_child(
            {
                "PROFILE_ID": r25.profile_id(SURVIVOR),
                "ROUTE": "WITNESS",
                "BOUNDS": {r25.profile_id(p): b for p, b in bounds.items()},
            }
        )
    with pytest.raises(AssertionError, match="current max/tied max"):
        r25.assert_solver_scope(state.owners[0], r25.committed_cheap_bounds(state))


@pytest.mark.parametrize("status", ("FEASIBLE", "OPTIMAL", "UNKNOWN", "EXTERNAL_HARD_TIMEOUT"))
def test_exact_support_feasibility_or_timeout_never_certifies_refutation(status: str) -> None:
    assert (
        r25.accepted_cap(
            {
                "ROUTE": r25.ROUTES[0],
                "STATUS": status,
                "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": 272,
            }
        )
        is None
    )
    with pytest.raises(AssertionError, match="identity mismatch"):
        r25.accepted_cap(
            {
                "ROUTE": r25.ROUTES[0],
                "STATUS": "INFEASIBLE",
                "CERTIFICATE_KIND": "CP_SAT_INFEASIBLE",
                "REFUTED_GRAPH_TRIANGLE_COUNT": 272,
                "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": 272,
                "OPEN_WEDGE_CEILING_REFUTED": 7,
            }
        )


def test_resume_state_does_not_enumerate_plateau_or_rebuild_census(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        pytest.fail("resume attempted fresh plateau/census exploration")

    monkeypatch.setattr(r13, "iter_r12_square_sum_profiles", forbidden)
    monkeypatch.setattr(r13, "certify_square_sum_class_suffix", forbidden)
    assert len(r25.current_state().owners) == 48
    assert r25.plateau_certificate()["INDIVIDUAL_PLATEAU_SOLVES"] == 0


def test_sealed_authority_replays_full_ledger_and_first_success_c(
    state: r25.State, cheap_rows: dict[DegreeProfile, dict[str, object]]
) -> None:
    result = r25.object_row(json.loads(r25.result_path().read_text()))
    assert result["TASK_STATUS"] == r25.SUCCESS_C
    assert result["COMMITTED_INPUT_SHA256"] == dict(state.input_hashes)
    assert (
        result["SOLVER_MODEL_SOURCE_SHA256"]
        == hashlib.sha256(
            r25.repo_root()
            .joinpath("src/lottolab/research/b649_k20_min_s2_cursor_dynamic_owner_chase_r25.py")
            .read_bytes()
        ).hexdigest()
    )
    assert result["CHEAPLY_REFINED_OWNER_COUNT"] == 47
    sealed_cheap = {
        r25.decode_profile(r["PROFILE_ID"]): r
        for r in cast(list[dict[str, object]], result["CHEAP_CERTIFICATES"])
    }
    assert set(sealed_cheap) == set(state.owners)
    for p, fresh in cheap_rows.items():
        assert sealed_cheap[p]["CERTIFIED_OWNER_BOUND"] == fresh["CERTIFIED_OWNER_BOUND"]
        assert sealed_cheap[p]["TRIANGLE_ENVELOPE"] == fresh["TRIANGLE_ENVELOPE"]
    (attempt,) = cast(list[dict[str, object]], result["OWNER_ATTEMPTS"])
    (proof,) = cast(list[dict[str, object]], attempt["ROUTES"])
    assert r25.accepted_cap(proof) == 272
    assert attempt["PROFILE_ID"] == r25.profile_id(SURVIVOR)
    expected = r25.committed_cheap_bounds(state)
    expected[SURVIVOR] = r25.bound_from_cap(SURVIVOR, 272, 112)[1]
    final = {
        r25.decode_profile(r["PROFILE_ID"]): r["CURRENT_BOUND"]
        for r in cast(list[dict[str, object]], result["FINAL_RESOLVED_LEDGER"])
    }
    assert final == expected
    assert result["CURRENT_BOUND_OWNER_SET"] == list(NEXT_OWNERS)
    assert result["FAMILY_UPPER_BOUND"] == result["MAX_RESOLVED_BOUND"] == 313_650_504
    assert result["REMAINING_GAP"] == 410_843
    assert result["OWNERS_REFINED_COUNT"] == result["OWNER_TRANSITION_COUNT"] == 48
    assert result["STRONGER_OWNER_PROFILES_DISPATCHED"] == [r25.profile_id(SURVIVOR)]
    assert result["INDIVIDUAL_PLATEAU_SOLVES"] == result["CURSOR_PROFILE_SOLVES"] == 0
    assert result["FULL_4850_PROFILE_CENSUS_REBUILT"] is False
    assert result["CURSOR_GENUINELY_LOAD_BEARING"] is False


def test_existing_r25_result_is_preserved_before_starting_proof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden() -> dict[str, object]:
        pytest.fail("existing R25 authority caused a proof rerun")

    monkeypatch.setattr(r25, "compute_result", forbidden)
    monkeypatch.setattr(sys, "argv", ["r25", "--output", str(r25.result_path())])
    with pytest.raises(FileExistsError, match="preserve the existing R25 result"):
        r25.main()
