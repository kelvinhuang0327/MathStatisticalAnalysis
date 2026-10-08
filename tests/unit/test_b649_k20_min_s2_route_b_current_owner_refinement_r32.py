"""R32 R31 authority, all-t Route B on the owners and the 104 plateau, family recomputation."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Sequence
from dataclasses import replace
from fractions import Fraction
from itertools import pairwise
from math import ceil, comb, floor
from time import monotonic
from typing import Any

import pytest

from lottolab.research import b649_k20_min_s2_route_b_current_owner_refinement_r32 as x

RESULT = x.r28.repo_root() / x.RESULT_DIRECTORY / x.RESULT_FILENAME
R31_RESULT = x.r28.repo_root() / x.RESULT_DIRECTORY / x.R31_RESULT
Start = tuple[x.Chase, str, dict[str, object]]
OWNER_BOUNDS = [313_403_620, *[313_404_008] * 5, 313_404_396]
NEXT_BOUND = 313_566_616


@pytest.fixture(scope="module")
def start() -> Start:
    return x.start_chase(monotonic() + 3600)


@pytest.fixture(scope="module")
def proofs() -> list[dict[str, object]]:
    return x.r30_proofs()


@pytest.fixture
def chase(start: Start) -> x.Chase:
    fresh = copy.deepcopy(start[0])
    fresh.deadline = monotonic() + 3600
    return fresh


@pytest.fixture(scope="module")
def sealed() -> Any:
    return json.loads(RESULT.read_text())


def independent_bound(profile: x.DegreeProfile, triangles: int, s4_floor: int) -> int:
    """Route B at exactly ``triangles`` from first principles, exact rational arithmetic."""

    degrees = [6 + d for d in profile]
    wedges = sum(comb(g, 2) for g in degrees)
    excess = sum(comb(g, 3) for g in degrees) - (max(degrees) - 2) * (wedges - 3 * triangles)
    k4 = max(0, ceil(Fraction(excess, 4)))
    a_max = floor(Fraction(sum(d * (g - 2) for d, g in zip(profile, degrees, strict=True)), 3))
    contained = min(k4, a_max)
    s4 = max(s4_floor, 448 * contained + 679 * (k4 - contained))
    s3 = 2_800 * wedges + 11_872 * (triangles - 22) - 30_800
    return ceil(372_228_640 - 63_838_600 + s3 - Fraction(4 * s4, 7))


def certify_owners(chase: x.Chase, proofs: x.Proofs) -> list[dict[str, object]]:
    return [x.certify(chase, p, i, proofs) for i, p in enumerate(x.START_OWNERS)]


def test_canonical_primitive_gate_and_authority_pins() -> None:
    assert x.r28.canonical_primitive_preflight() == {
        "STATUS": "PASS",
        "SINGLE_TICKET_ANY_PRIZE": 18_611_432,
        "K20_S1": 372_228_640,
    }
    assert x.r30.k4_quartet_weights() == x.K4_WEIGHTS
    assert x.R30_SHA256 == x.r31.R30_SHA256
    assert hashlib.sha256(R31_RESULT.read_bytes()).hexdigest() == x.R31_SHA256


def test_r31_authority_and_exact_owner_and_plateau_reconstruction(start: Start) -> None:
    chase, digest, result = start
    assert digest == x.R31_SHA256
    assert x.r28.family_state(chase) == (313_567_400, x.START_OWNERS)
    for i, p in enumerate(x.START_OWNERS):
        cert = chase.catalog[p]
        assert (cert.triangle_cap, cert.s4, cert.relaxation) == (264, 112, x.r28.ROUTE_A)
        assert (cert.source_result, cert.source_row) == (
            x.CAP_SOURCE_RESULT,
            f"GROUP_ATTEMPTS[{2500 + i}]",
        )
    assert x.r29.ledger_digest(chase) == x.R31_LEDGER_SHA256 and len(chase.bounds) == 1_795
    assert (chase.cursor, chase.cursor_bound) == (x.CURSOR, 313_556_760)
    assert not chase.attempts and not chase.steps and len(chase.sequence) == 1
    ledger: list[dict[str, Any]] = json.loads(R31_RESULT.read_text())["FINAL_RESOLVED_LEDGER"]
    level = sorted(r["PROFILE_ID"] for r in ledger if r["CURRENT_BOUND"] == 313_567_288)
    assert len(level) == 104 and not [r for r in ledger if r["CURRENT_BOUND"] > 313_567_400]
    assert sorted(map(x.profile_id, x.sealed_level(result, x.PLATEAU_BOUND))) == level


def test_tampered_r31_authority_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    cases: dict[str, tuple[str, object]] = {
        "fingerprint": ("R31_SHA256", "0" * 64),
        "base tree": ("BASE_TREE", "0" * 40),
        "FAMILY_UPPER_BOUND": ("START_BOUND", x.START_BOUND - 1),
        "NEXT_COMPETING_BOUND": ("PLATEAU_BOUND", x.PLATEAU_BOUND - 1),
        "R30_RESULT_SHA256": ("R30_SHA256", "0" * 64),
    }
    for message, (name, value) in cases.items():
        with monkeypatch.context() as patch:
            patch.setattr(x, name, value)
            with pytest.raises(AssertionError, match=message):
                x.r31_authority()


def test_contained_triple_split_primitive() -> None:
    assert {x.contained_triple_k4_cap(p) for p in x.START_OWNERS} == {202}
    assert x.contained_triple_k4_cap(x.REFERENCE_OWNER) == 199
    assert x.contained_triple_k4_cap(x.WITNESS_PROFILE) == 190
    for a_max in (0, 50, 202, 1_000):
        floors = [x.route_b_s4_floor(k4, a_max) for k4 in range(400)]
        for k4, (contained, s4) in enumerate(floors):
            assert contained == min(k4, a_max) and s4 == 679 * k4 - 231 * contained
            assert s4 >= 448 * k4
        assert all(a[1] < b[1] for a, b in pairwise(floors))
    with pytest.raises(AssertionError, match="non-negative"):
        x.route_b_s4_floor(-1, 5)


def test_reference_regression_on_the_original_r30_owner(proofs: x.Proofs) -> None:
    row = x.reference_regression(proofs, monotonic() + 3600)
    assert (row["R30_BOUND"], row["ROUTE_B_BOUND"]) == (313_568_072, 313_401_180)
    assert (row["CERTIFIED_TRIANGLE_CAP"], row["A_MAX"]) == (265, 199)
    assert (row["K4_FLOOR"], row["S4_FLOOR"]) == (498, 292_173)
    assert x.object_row(row["CERTIFICATE_SOURCE"])["SOURCE_ROW"] == "GROUP_ATTEMPTS[2497]"
    values = [independent_bound(x.REFERENCE_OWNER, t, 112) for t in range(22, 266)]
    assert values[-1] == max(values) == 313_401_180


def test_owner_route_b_holds_for_every_permitted_triangle_count(
    chase: x.Chase, proofs: x.Proofs
) -> None:
    rows = certify_owners(chase, proofs)
    assert [r["NEW_BOUND"] for r in rows] == OWNER_BOUNDS
    for p, r in zip(x.START_OWNERS, rows, strict=True):
        assert r["STATUS"] == x.CERTIFIED and r["PREMISE_FAILURES"] == []
        assert (r["TRIANGLE_COUNTS_CHECKED"], r["A_MAX"], r["CONTAINED_TRIPLE_K4_AT_CAP"]) == (
            243,
            202,
            202,
        )
        assert x.integer(r["S4_FLOOR"]) > x.integer(r["ROUTE4_S4_FLOOR_AT_CAP"])
        values = [independent_bound(p, t, 112) for t in range(22, 265)]
        assert values[-1] == max(values) == r["NEW_BOUND"] == r["ALL_T_MAX_BOUND"]
        assert all(a < b for a, b in pairwise(values))
        cert = chase.catalog[p]
        assert (cert.relaxation, cert.s4, cert.triangle_cap) == (x.ROUTE_B, 112, 264)
        again = x.route_b_certificate(p, cert, proofs)
        assert again["STATUS"] == x.REJECTED
        assert x.rows(again["PREMISE_FAILURES"]) == [
            "CERTIFICATE_SOURCE_NOT_A_SEALED_R30_ATTEMPT",
            "BOUND_IS_NOT_THE_CAP_ENVELOPE",
        ]
    family, owners = x.r28.family_state(chase)
    assert (family, len(owners)) == (313_567_288, 104)


def test_plateau_per_member_certificates_and_complete_family_maximum(
    chase: x.Chase, proofs: x.Proofs, start: Start
) -> None:
    certify_owners(chase, proofs)
    members = x.plateau_members(chase, x.sealed_level(start[2], x.PLATEAU_BOUND))
    mode = x.certificate_mode(chase, members)
    assert mode["MODE"] == "PER_MEMBER_CLOSED_FORM" and mode["TRIANGLE_CAPS"] == [268]
    assert (mode["DISTINCT_SOURCE_CERTIFICATES"], mode["DISTINCT_PREMISE_TUPLES"]) == (104, 35)
    assert (mode["A_MAX_VALUES"], mode["WEDGE_COUNTS"], mode["MAX_GRAPH_DEGREES"]) == (
        [190],
        [817],
        [11, 12],
    )
    rows = [x.certify(chase, p, i + 7, proofs) for i, p in enumerate(members)]
    assert all(r["STATUS"] == x.CERTIFIED for r in rows)
    for p, r in zip(members, rows, strict=True):
        values = [independent_bound(p, t, 112) for t in range(22, 269)]
        assert r["NEW_BOUND"] == values[-1] == max(values) < NEXT_BOUND
    assert max(x.integer(r["NEW_BOUND"]) for r in rows) == 313_388_732
    family, owners = x.r28.family_state(chase)
    assert (family, len(owners)) == (NEXT_BOUND, 74)
    assert {(chase.catalog[p].relaxation, chase.catalog[p].triangle_cap) for p in owners} == {
        (x.r28.ROUTE_A, 267)
    }
    recompute = x.full_recompute(chase)
    assert (
        recompute["FAMILY_UPPER_BOUND"] == NEXT_BOUND and len(x.rows(recompute["OWNER_IDS"])) == 74
    )
    assert x.r28.competing_bound(chase, owners) == 313_566_504 > x.CURSOR_BOUND
    obstruction = x.next_obstruction(chase, (*x.START_OWNERS, *members))
    assert obstruction["KIND"] == "FIRST_LEVEL_OUTSIDE_THE_7_PLUS_104_SLICE"
    assert (obstruction["OWNER_COUNT"], obstruction["SLICE_OWNERS_REMAINING"]) == (74, 0)
    assert obstruction["CURSOR_IS_OWNER"] is False
    assert [s["FAMILY_BOUND"] for s in chase.sequence] == [313_567_400, 313_567_288, NEXT_BOUND]


def test_certificate_identity_is_checked_against_the_sealed_refutation(
    chase: x.Chase, proofs: list[dict[str, object]]
) -> None:
    p = x.START_OWNERS[0]
    cert = chase.catalog[p]
    lower = x.bound_from_cap(p, 263, 112)[1]
    unsealed = "CERTIFICATE_SOURCE_NOT_A_SEALED_R30_ATTEMPT"
    cases = [
        ("SOURCE_PROOF_IDENTITY_MISMATCH", replace(cert, source_row="GROUP_ATTEMPTS[2501]")),
        ("SOURCE_PROOF_IDENTITY_MISMATCH", replace(cert, triangle_cap=263, bound=lower)),
        (unsealed, replace(cert, source_row="GROUP_ATTEMPTS[999999]")),
        (unsealed, replace(cert, source_row="ROUTE4_CERTIFICATES[0]")),
        (unsealed, replace(cert, source_result=x.R31_RESULT)),
        ("NOT_A_VERIFIED_TRIANGLE_CAP_CERTIFICATE", replace(cert, relaxation=x.r30.ROUTE_MOTIF)),
        ("TRIANGLE_CAP_MISSING", replace(cert, triangle_cap=None)),
    ]
    for failure, tampered in cases:
        row = x.route_b_certificate(p, tampered, proofs)
        assert row["STATUS"] == x.REJECTED and failure in x.rows(row["PREMISE_FAILURES"])
        assert row["NEW_BOUND"] == tampered.bound
    for status in ("FEASIBLE", "UNKNOWN", "OPTIMAL"):
        forged = copy.deepcopy(proofs)
        forged[2500]["STATUS"] = status
        row = x.route_b_certificate(p, cert, forged)
        assert row["PREMISE_FAILURES"] == ["SOURCE_PROOF_NOT_INFEASIBLE"]
        assert row["STATUS"] == x.REJECTED and row["NEW_BOUND"] == cert.bound
    for key, failure in (
        ("TARGET_BOUND", "SOURCE_PROOF_BOUND_MISMATCH"),
        ("TARGET_TRIANGLE_CAP", "SOURCE_PROOF_TARGET_CAP_MISMATCH"),
        ("ATTEMPT_INDEX", unsealed),
    ):
        forged = copy.deepcopy(proofs)
        forged[2500][key] = x.integer(forged[2500][key]) + 1
        assert x.route_b_certificate(p, cert, forged)["PREMISE_FAILURES"] == [failure]
    forged = copy.deepcopy(proofs)
    forged[2500]["STATUS"] = "UNKNOWN"
    assert x.certify(chase, p, 0, forged)["STATUS"] == x.REJECTED
    assert x.r28.family_state(chase) == (x.START_BOUND, x.START_OWNERS)


def test_tampered_premises_are_rejected(chase: x.Chase, proofs: x.Proofs) -> None:
    p = x.START_OWNERS[0]
    cert = chase.catalog[p]
    cases = {
        "S4_NOT_THE_GLOBAL_PROFILE_FLOOR": replace(cert, s4=286_727),
        "TRIANGLE_CAP_OUT_OF_RANGE": replace(cert, triangle_cap=834 // 3 + 1),
        "BOUND_IS_NOT_THE_CAP_ENVELOPE": replace(cert, bound=cert.bound + 1),
        "CERTIFICATE_PROFILE_MISMATCH": replace(cert, profile=x.CURSOR),
    }
    for failure, tampered in cases.items():
        row = x.route_b_certificate(p, tampered, proofs)
        assert row["STATUS"] == x.REJECTED and failure in x.rows(row["PREMISE_FAILURES"])
    assert x.structural_failures((6,) * 12 + (0,) * 8) == [
        "TRIPLE_INCIDENCES_ARE_NOT_THREE_PER_TRIPLE_SUPPORT"
    ]
    for bad in ((0,) * 8 + (6,) * 11 + (0,), (6,) * 11, (7,) + (6,) * 9 + (5,) + (0,) * 9):
        assert x.structural_failures(bad) == ["PROFILE_NOT_A_K20_TRIPLE_DEGREE_SEQUENCE"]
    heavy = (6,) * 12 + (0,) * 8
    row = x.route_b_certificate(heavy, replace(cert, profile=heavy), proofs)
    assert row["PREMISE_FAILURES"] == ["TRIPLE_INCIDENCES_ARE_NOT_THREE_PER_TRIPLE_SUPPORT"]


def test_changed_k4_weights_are_rejected(
    chase: x.Chase, proofs: x.Proofs, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(x.r30, "k4_quartet_weights", lambda: {"UNIT": 1})
    row = x.certify(chase, x.START_OWNERS[0], 0, proofs)
    assert row["PREMISE_FAILURES"] == ["K4_QUARTET_WEIGHTS_CHANGED"]
    assert x.r28.family_state(chase)[0] == x.START_BOUND


@pytest.mark.parametrize("shift", [-1, 1])
def test_inexact_k4_ceiling_is_rejected(shift: int, monkeypatch: pytest.MonkeyPatch) -> None:
    real = x.r30.k4_lower_bound
    p = x.START_OWNERS[0]
    assert x.envelope_term(p, 264, 112, 202) == (264, 313_403_620, 491, 202, 286_727, 5_177_424)

    def shifted(degrees: Sequence[int], open_wedges: int) -> int:
        return real(degrees, open_wedges) + shift

    monkeypatch.setattr(x.r30, "k4_lower_bound", shifted)
    with pytest.raises(AssertionError, match="K4 ceiling"):
        x.envelope_term(p, 264, 112, 202)


@pytest.mark.parametrize("shift", [-1, 1])
def test_bound_not_within_one_above_the_exact_rational_is_rejected(
    shift: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = x.bound_from_cap

    def shifted(profile: x.DegreeProfile, cap: int, s4: int) -> tuple[int, int]:
        s3, bound = real(profile, cap, s4)
        return s3, bound + shift

    monkeypatch.setattr(x, "bound_from_cap", shifted)
    with pytest.raises(AssertionError, match="S4 credit"):
        x.envelope_term(x.START_OWNERS[0], 264, 112, 202)


@pytest.mark.parametrize(
    ("slope", "offset", "status"),
    [(-1, -1_000_000, x.NOT_AT_CAP), (1, 0, x.NO_DROP)],
)
def test_envelope_off_cap_or_without_a_drop_is_not_applied(
    chase: x.Chase,
    proofs: x.Proofs,
    slope: int,
    offset: int,
    status: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def term(profile: x.DegreeProfile, triangles: int, base: int, a_max: int) -> x.Term:
        return triangles, x.START_BOUND + offset + slope * triangles, 0, 0, base, 0

    monkeypatch.setattr(x, "envelope_term", term)
    row = x.certify(chase, x.START_OWNERS[0], 0, proofs)
    assert row["STATUS"] == status and row["NEW_BOUND"] == x.START_BOUND
    assert x.r28.family_state(chase) == (x.START_BOUND, x.START_OWNERS)


def test_plateau_and_frontier_mismatches_stop(
    chase: x.Chase, proofs: x.Proofs, start: Start, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(AssertionError, match="owners"):
        x.certify(chase, x.sealed_level(start[2], x.PLATEAU_BOUND)[0], 0, proofs)
    certify_owners(chase, proofs)
    plateau = x.sealed_level(start[2], x.PLATEAU_BOUND)
    with pytest.raises(AssertionError, match="104-profile"):
        x.plateau_members(chase, plateau[1:])
    with monkeypatch.context() as patch:
        patch.setattr(x, "PLATEAU_COUNT", 103)
        with pytest.raises(AssertionError, match="104-profile"):
            x.plateau_members(chase, plateau)
    chase.cursor_bound = 313_567_500
    with pytest.raises(AssertionError, match="independent family recomputation"):
        x.full_recompute(chase)


def test_r31_route4_certificates_stay_intact(chase: x.Chase, start: Start) -> None:
    row = x.r31_route4_revalidation(chase, start[2])
    assert (row["CERTIFICATES_REVALIDATED"], row["MAX_R31_ROUTE4_BOUND"]) == (127, 313_440_648)
    p = x.REFERENCE_OWNER
    chase.catalog[p] = replace(chase.catalog[p], relaxation=x.ROUTE_B)
    with pytest.raises(AssertionError, match="R31 Route-4 certificate changed"):
        x.r31_route4_revalidation(chase, start[2])


def test_witness_soundness_and_overtightening_tripwires(
    start: Start, monkeypatch: pytest.MonkeyPatch
) -> None:
    witness = x.object_row(start[2]["SOUNDNESS_WITNESS"])
    row = x.witness_route_b(witness)
    assert (row["ROUTE_B_S4_FLOOR"], row["EXACT_S4"], row["EXACT_K4_MOTIF_S4"]) == (
        325_486,
        331_240,
        329_560,
    )
    assert row["EXACT_CONTAINED_TRIPLE_K4"] == row["A_MAX"] == 190
    assert (row["EXACT_K4"], row["K4_FLOOR_AT_REALIZED_TRIANGLES"]) == (550, 544)
    assert row["ROUTE_B_BOUND_AT_REALIZED_CAP"] == 313_402_304 > x.WITNESS_UNION
    for key, value, message in (
        ("EXACT_S4", 325_485, "over-tightens"),
        ("EXACT_S4", 329_559, "over-tightens"),
        ("GRAPH_TRIANGLES", 271, "structure differs"),
        ("EXACT_ANY_PRIZE_UNION", 313_263_868, "structure differs"),
        ("STATUS", "FAIL", "structure differs"),
    ):
        with pytest.raises(AssertionError, match=message):
            x.witness_route_b({**witness, key: value})
    with monkeypatch.context() as patch:

        def short(profile: x.DegreeProfile) -> int:
            return 189

        patch.setattr(x, "contained_triple_k4_cap", short)
        with pytest.raises(AssertionError, match="over-tightens"):
            x.witness_route_b(witness)
    with monkeypatch.context() as patch:
        patch.setattr(x, "K4_WEIGHTS", {x.WITH_TRIPLE: 600, x.WITHOUT_TRIPLE: 900})
        with pytest.raises(AssertionError, match="over-tightens"):
            x.witness_route_b(witness)
    with monkeypatch.context() as patch:
        patch.setattr(x, "WITNESS_ROUTE_B_S4_FLOOR", 325_487)
        with pytest.raises(AssertionError, match="independent proof"):
            x.witness_route_b(witness)


def test_committed_result_is_reproduced_without_a_solver_or_enumeration(
    sealed: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("a solver or outcome enumeration was called")

    monkeypatch.setattr(x.r28, "bounded_batch", forbidden)
    monkeypatch.setattr(x.r28, "solve_group", forbidden)
    monkeypatch.setattr(x.r30, "evaluate_portfolio", forbidden)
    assert json.loads(json.dumps(x.compute_result())) == sealed


def test_sealed_result_replay_and_handoff(sealed: Any) -> None:
    chase = x.replay_result(sealed, monotonic() + 3600)
    family, owners = x.r28.family_state(chase)
    assert sealed["TASK_STATUS"] == x.SUCCESS_A
    assert sealed["FAMILY_STATUS"] == "OPEN_STRICTLY_TIGHTENED"
    assert family == sealed["FAMILY_UPPER_BOUND"] == NEXT_BOUND
    assert list(map(x.profile_id, owners)) == sealed["FINAL_BOUND_OWNER_IDS"]
    assert (sealed["CERTIFIED_FAMILY_DROP"], sealed["REMAINING_GAP"]) == (784, 302_728)
    assert sealed["CURRENT_OWNERS_CERTIFIED"] == sealed["CURRENT_OWNER_COUNT"] == 7
    assert sealed["NEXT_PLATEAU_CERTIFIED"] == sealed["NEXT_PLATEAU_COUNT"] == 104
    assert sealed["ALL_T_CERTIFICATE_STATUS"] == "PASS"
    assert sealed["ROUTE_B_APPLICABILITY"] == "ALL_SLICE_CERTIFICATES_SATISFY_EVERY_PREMISE"
    assert sealed["FULL_LEDGER_RECOMPUTATION"]["STATUS"] == "PASS"
    assert sealed["R31_ROUTE4_REVALIDATION"]["CERTIFICATES_REVALIDATED"] == 127
    assert sealed["REFERENCE_REGRESSION"]["ROUTE_B_BOUND"] == 313_401_180
    assert sealed["WITNESS_SOUNDNESS_STATUS"] == sealed["CANONICAL_PRIMITIVE_STATUS"] == "PASS"
    assert sealed["NEXT_OBSTRUCTION"]["KIND"] == "FIRST_LEVEL_OUTSIDE_THE_7_PLUS_104_SLICE"
    assert (sealed["SOLVER_CALLS"], sealed["OUTCOME_ENUMERATIONS"]) == (0, 0)
    assert (sealed["NEW_HEAVY_SOLVER_STARTED"], sealed["NEW_PORTFOLIO_SEARCH_STARTED"]) == (
        "NO",
        "NO",
    )
    assert sealed["RESOLVED_LEDGER_COUNT"] == 1_795


def test_tampered_sealed_result_is_rejected(sealed: Any) -> None:
    bound = copy.deepcopy(sealed)
    bound["ROUTE_B_CERTIFICATES"][9]["NEW_BOUND"] -= 1
    with pytest.raises(AssertionError, match="certificate replay diverged"):
        x.replay_result(bound, monotonic() + 3600)
    owner = copy.deepcopy(sealed)
    owner["ROUTE_B_CERTIFICATES"][0]["PROFILE_ID"] = owner["ROUTE_B_CERTIFICATES"][7]["PROFILE_ID"]
    with pytest.raises(AssertionError, match="owners"):
        x.replay_result(owner, monotonic() + 3600)
    ledger = copy.deepcopy(sealed)
    ledger["FINAL_RESOLVED_LEDGER"][0]["CURRENT_BOUND"] += 1
    with pytest.raises(AssertionError, match="ledger replay diverged"):
        x.replay_result(ledger, monotonic() + 3600)
