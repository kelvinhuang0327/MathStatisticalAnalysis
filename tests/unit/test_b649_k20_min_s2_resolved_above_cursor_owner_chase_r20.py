"""Committed-ledger completeness, changing max owners and proof gates for R20."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from dataclasses import replace
from typing import cast

import pytest

from lottolab.research import b649_k20_min_s2_resolved_above_cursor_owner_chase_r20 as r20
from lottolab.research.b649_k20_min_s2_dual_owner_refinement_r19 import (
    post_r18_bound_ledger,
)

DegreeProfile = tuple[int, ...]
EXPECTED_ABOVE = (
    "66665555555411100000",
    "66655555555521000000",
    "66655555555511100000",
    "66666664444431000000",
    "66666655544411100000",
    "66666655544331000000",
    "66666555555311100000",
    "66666555554421000000",
    "66665555554440000000",
    "66655555555530000000",
    "66666555555221100000",
    "66666555554411100000",
    "66666555554331000000",
    "66665555555421000000",
)


@pytest.fixture(scope="module")
def inputs() -> dict[str, dict[str, object]]:
    return r20.committed_results()[0]


@pytest.fixture(scope="module")
def ledger(inputs: dict[str, dict[str, object]]) -> dict[DegreeProfile, r20.Certificate]:
    return r20.reconstruct_ledger(inputs)


def test_primitives_and_exact_complete_committed_ledger(
    ledger: dict[DegreeProfile, r20.Certificate],
    inputs: dict[str, dict[str, object]],
) -> None:
    assert r20.canonical_primitive_preflight() == {
        "STATUS": "PASS",
        "SINGLE_TICKET_ANY_PRIZE": 18_611_432,
        "K20_S1": 372_228_640,
    }
    prior, _ = post_r18_bound_ledger()
    r19 = cast(dict[str, object], inputs["R19"]["REFINED_OWNER_BOUNDS"])
    expected = {**prior, **{r20.decode_profile(p): cast(int, bound) for p, bound in r19.items()}}
    assert {p: cert.bound for p, cert in ledger.items()} == expected
    assert len(ledger) == 282
    above = r20.resolved_above_cursor(ledger)
    assert tuple(map(r20.profile_id, above)) == EXPECTED_ABOVE
    assert len(above) == 14 <= r20.MAX_OWNER_PROFILES
    assert r20.CURSOR_PROFILE not in ledger
    family, owners = r20.family_state(expected)
    assert family == 313_668_648
    assert tuple(map(r20.profile_id, owners)) == EXPECTED_ABOVE[:2]
    assert tuple(ledger[p].source_row for p in owners) == (
        "PROFILE_BOUNDS[8]",
        "PROFILE_BOUNDS[10]",
    )
    assert all(ledger[p].source_result == r20.INPUT_FILENAMES["R12"] for p in owners)


@pytest.mark.parametrize("identity", EXPECTED_ABOVE)
def test_current_certificate_and_committed_support_witness(
    identity: str,
    ledger: dict[DegreeProfile, r20.Certificate],
) -> None:
    cert = ledger[r20.decode_profile(identity)]
    assert cert.triangle_cap is not None and cert.s4 is not None
    assert r20.bound_from_cap(cert.profile, cert.triangle_cap, cert.s4) == (cert.s3, cert.bound)
    triples, doubles = r20.support_witness(cert)
    assert (len(triples), len(doubles)) == (22, 27)
    row = r20.ledger_row(cert)
    assert set(row) >= {
        "PROFILE_ID",
        "DEGREE_PROFILE",
        "SOURCE_RESULT",
        "SOURCE_ROW",
        "CURRENT_BOUND",
        "REALIZABILITY_STATUS",
        "S3",
        "S4_FLOOR",
        "BOUND_LIMITING_RELAXATION",
    }
    assert row["REALIZABILITY_STATUS"] == "REALIZABLE"


def test_prior_refinements_replace_stale_caps(ledger: dict[DegreeProfile, r20.Certificate]) -> None:
    for identity, label, cap in (
        ("66655555555511100000", "R15", 273),
        ("66666555554421000000", "R15", 272),
        ("66666555555311100000", "R17", 272),
        ("66666555554411100000", "R19", 272),
        ("66665555555421000000", "R19", 272),
    ):
        cert = ledger[r20.decode_profile(identity)]
        assert cert.source_result == r20.INPUT_FILENAMES[label]
        assert cert.triangle_cap == cap
    assert ledger[r20.decode_profile("66665555554440000000")].s4 == 1680
    assert ledger[r20.decode_profile("66655555555530000000")].s4 == 1680


def test_no_omitted_owner_gate_rejects_missing_duplicate_or_cursor(
    ledger: dict[DegreeProfile, r20.Certificate],
) -> None:
    profiles = tuple(r20.resolved_above_cursor(ledger))
    r20.assert_no_omitted_owner(ledger, profiles)
    for broken in (profiles[:-1], (*profiles, profiles[0]), (*profiles[:-1], r20.CURSOR_PROFILE)):
        with pytest.raises(AssertionError, match="incomplete or duplicated"):
            r20.assert_no_omitted_owner(ledger, broken)


def test_reconstruction_rejects_missing_committed_profile(
    inputs: dict[str, dict[str, object]],
) -> None:
    broken = copy.deepcopy(inputs)
    cast(list[object], broken["R12"]["PROFILE_BOUNDS"]).pop(10)
    with pytest.raises(AssertionError, match="R12 profile count"):
        r20.reconstruct_ledger(broken)


def test_reconstruction_rejects_false_refinement(inputs: dict[str, dict[str, object]]) -> None:
    broken = copy.deepcopy(inputs)
    rows = cast(dict[str, dict[str, object]], broken["R19"]["REFINED_OWNER_ROWS"])
    rows["66666555554411100000"]["GRAPH_TRIANGLE_UPPER_BOUND"] = 271
    with pytest.raises(AssertionError, match="does not reproduce"):
        r20.reconstruct_ledger(broken)


def test_support_witness_gate_rejects_corrupted_compact_support(
    ledger: dict[DegreeProfile, r20.Certificate],
) -> None:
    cert = next(iter(r20.resolved_above_cursor(ledger).values()))
    assert cert.witness_row is not None
    broken = dict(cert.witness_row)
    broken["WITNESS_TRIPLES"] = "0,0,1"
    with pytest.raises((AssertionError, ValueError)):
        r20.support_witness(replace(cert, witness_row=broken))


def test_descending_dispatch_and_immediate_owner_switch_all_fourteen(
    ledger: dict[DegreeProfile, r20.Certificate],
) -> None:
    calls: list[str] = []

    def refine(cert: r20.Certificate, bounds: Mapping[DegreeProfile, int]) -> dict[str, object]:
        r20.assert_solver_scope(cert.profile, ledger, bounds)
        calls.append(r20.profile_id(cert.profile))
        assert cert.triangle_cap is not None and cert.s4 is not None
        _, bound = r20.bound_from_cap(cert.profile, cert.triangle_cap - 1, cert.s4)
        return {"CERTIFIED_OWNER_BOUND": bound, "PROFILE_ID": r20.profile_id(cert.profile)}

    outcome = r20.run_owner_chase(ledger, refine)
    assert tuple(calls) == EXPECTED_ABOVE
    assert outcome.status == r20.SUCCESS_B
    assert outcome.family_bound == r20.CURSOR_BOUND
    assert outcome.owners == (r20.CURSOR_PROFILE,)
    assert len(outcome.steps) == 14
    assert all(outcome.bounds[p] <= r20.CURSOR_BOUND for p in r20.resolved_above_cursor(ledger))
    first, second = outcome.steps[:2]
    assert first["OWNER_SET_AFTER"] == [EXPECTED_ABOVE[1]]
    assert second["OWNER_SET_AFTER"] == [EXPECTED_ABOVE[2]]
    assert first["FAMILY_BOUND_AFTER"] == 313_668_648
    assert second["FAMILY_BOUND_AFTER"] == 313_665_848
    for step in outcome.steps:
        assert (
            cast(int, step["START_OWNER_BOUND"]) - cast(int, step["REFINED_OWNER_BOUND"]) == 11_872
        )


def test_uncertified_current_owner_blocks_lower_dispatch(
    ledger: dict[DegreeProfile, r20.Certificate],
) -> None:
    calls: list[str] = []

    def refine(cert: r20.Certificate, _: Mapping[DegreeProfile, int]) -> dict[str, object]:
        identity = r20.profile_id(cert.profile)
        calls.append(identity)
        if identity == EXPECTED_ABOVE[0]:
            return {"CERTIFIED_OWNER_BOUND": None}
        assert cert.triangle_cap is not None and cert.s4 is not None
        return {
            "CERTIFIED_OWNER_BOUND": r20.bound_from_cap(
                cert.profile, cert.triangle_cap - 1, cert.s4
            )[1]
        }

    outcome = r20.run_owner_chase(ledger, refine)
    assert calls == list(EXPECTED_ABOVE[:2])
    assert outcome.status == "NO_CERTIFIED_FAMILY_DROP"
    assert outcome.family_bound == r20.START_FAMILY_BOUND
    assert tuple(map(r20.profile_id, outcome.owners)) == (EXPECTED_ABOVE[0],)


def test_cursor_lower_owner_and_incomplete_ledger_solver_guards(
    ledger: dict[DegreeProfile, r20.Certificate],
) -> None:
    bounds = {p: cert.bound for p, cert in ledger.items()}
    owner = r20.decode_profile(EXPECTED_ABOVE[0])
    r20.assert_solver_scope(owner, ledger, bounds)
    for forbidden in (r20.CURSOR_PROFILE, r20.decode_profile(EXPECTED_ABOVE[2])):
        with pytest.raises(AssertionError):
            r20.assert_solver_scope(forbidden, ledger, bounds)
    with pytest.raises(AssertionError, match="omitted or weakened"):
        r20.assert_solver_scope(owner, ledger, {p: b for p, b in bounds.items() if p != owner})
    with pytest.raises(AssertionError, match="omitted or weakened"):
        r20.assert_solver_scope(owner, ledger, {**bounds, owner: bounds[owner] + 1})


def test_real_result_replays_every_proof_and_owner_transition(
    ledger: dict[DegreeProfile, r20.Certificate],
) -> None:
    artifact = cast(dict[str, object], json.loads(r20.result_path().read_text()))
    assert artifact["INPUT_AUTHORITY"] == "IMMUTABLE_BASE_HEAD_GIT_BLOBS_ONLY"
    assert artifact["RESOLVED_ABOVE_CURSOR_PROFILES"] == list(EXPECTED_ABOVE)
    assert artifact["RESOLVED_ABOVE_CURSOR_COUNT"] == 14
    assert artifact["RESOLVED_LEDGER_COUNT"] == 282
    assert artifact["OWNERS_REFINED_COUNT"] == 14
    assert artifact["OWNERS_PROCESSED_COUNT"] == 14
    assert artifact["TASK_STATUS"] == r20.SUCCESS_B
    assert artifact["END_FAMILY_BOUND"] == r20.CURSOR_BOUND
    assert artifact["CURRENT_BOUND_OWNER_SET"] == [r20.profile_id(r20.CURSOR_PROFILE)]
    assert artifact["REMAINING_RESOLVED_ABOVE_CURSOR_COUNT"] == 0
    assert artifact["CURSOR_PROFILE_SOLVES"] == 0
    assert artifact["CURSOR_GENUINELY_LOAD_BEARING"] is True
    assert artifact["NEW_PORTFOLIO_SEARCH_STARTED"] == "NO"
    assert artifact["PRODUCTION_MUTATION"] == "NONE"
    bounds = {p: cert.bound for p, cert in ledger.items()}
    steps = cast(list[dict[str, object]], artifact["REFINEMENT_STEPS"])
    for step in steps:
        owner = r20.decode_profile(step["PROFILE_ID"])
        r20.assert_solver_scope(owner, ledger, bounds)
        before, owners = r20.family_state(bounds)
        assert step["FAMILY_BOUND_BEFORE"] == before
        assert step["OWNER_SET_BEFORE"] == list(map(r20.profile_id, owners))
        proof = cast(dict[str, object], step["CERTIFICATE"])
        routes = cast(list[dict[str, object]], proof["ROUTES"])
        assert len(routes) == 1 and routes[0]["STATUS"] == "INFEASIBLE"
        assert routes[0]["ROUTE"] == "A_EXACT_SUPPORT_OPEN_WEDGE_REFUTATION"
        assert routes[0]["CERTIFICATE_KIND"] == "CP_SAT_INFEASIBLE"
        cap = cast(int, proof["REFINED_TRIANGLE_CAP"])
        s4 = cast(int, proof["S4_FLOOR"])
        assert r20.bound_from_cap(owner, cap, s4) == (
            proof["REFINED_S3"],
            step["REFINED_OWNER_BOUND"],
        )
        assert routes[0]["OPEN_WEDGE_CEILING_REFUTED"] == r20.overlap_wedge_count(owner) - 3 * (
            cap + 1
        )
        witness = cast(dict[str, object], proof["WITNESS_CHECK"])
        assert witness["STATUS"] == "PASS"
        assert witness["FIXED_WITNESS_STATUS_BY_CEILING"] == {
            "AT_WITNESS_COUNT": "OPTIMAL",
            "ONE_BELOW_WITNESS_COUNT": "INFEASIBLE",
        }
        bounds[owner] = cast(int, step["REFINED_OWNER_BOUND"])
        after, next_owners = r20.family_state(bounds)
        assert step["FAMILY_BOUND_AFTER"] == after
        assert step["OWNER_SET_AFTER"] == list(map(r20.profile_id, next_owners))
    final_rows = cast(list[dict[str, object]], artifact["FINAL_RESOLVED_LEDGER"])
    assert {
        r20.decode_profile(row["PROFILE_ID"]): row["CURRENT_BOUND"] for row in final_rows
    } == bounds
    assert r20.family_state(bounds) == (r20.CURSOR_BOUND, (r20.CURSOR_PROFILE,))
