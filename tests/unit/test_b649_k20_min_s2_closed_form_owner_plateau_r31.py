"""R31 R30 authority, all-t Route 4 on the owner and its plateau, family recomputation."""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from fractions import Fraction
from itertools import pairwise
from math import ceil, comb
from time import monotonic
from typing import Any

import pytest

from lottolab.research import b649_k20_min_s2_closed_form_owner_plateau_r31 as x

RESULT = x.r28.repo_root() / x.RESULT_DIRECTORY / x.RESULT_FILENAME
R30_RESULT = x.r28.repo_root() / x.RESULT_DIRECTORY / x.R30_RESULT
Start = tuple[x.Chase, str]
NEXT_OWNERS = [
    "66666665444322000000",
    "66666664444431000000",
    "66666655544411100000",
    "66666655544331000000",
    "66666555555311100000",
    "66666555555222000000",
    "66666555554421000000",
]


@pytest.fixture(scope="module")
def start() -> Start:
    return x.start_chase(monotonic() + 3600)


@pytest.fixture
def chase(start: Start) -> x.Chase:
    fresh = copy.deepcopy(start[0])
    fresh.deadline = monotonic() + 3600
    return fresh


@pytest.fixture(scope="module")
def sealed() -> Any:
    return json.loads(RESULT.read_text())


def independent_bound(profile: x.DegreeProfile, triangles: int, s4_floor: int) -> int:
    """Route 4 at exactly ``triangles`` from first principles, exact rational arithmetic."""

    degrees = [6 + d for d in profile]
    wedges = sum(comb(g, 2) for g in degrees)
    excess = sum(comb(g, 3) for g in degrees) - (max(degrees) - 2) * (wedges - 3 * triangles)
    k4 = max(0, ceil(Fraction(excess, 4)))
    s4 = max(s4_floor, 448 * k4)
    s3 = 2_800 * wedges + 11_872 * (triangles - 22) - 30_800
    return ceil(372_228_640 - 63_838_600 + s3 - Fraction(4 * s4, 7))


def test_canonical_primitive_gate() -> None:
    assert x.r28.canonical_primitive_preflight() == {
        "STATUS": "PASS",
        "SINGLE_TICKET_ANY_PRIZE": 18_611_432,
        "K20_S1": 372_228_640,
    }
    assert x.r30.k4_quartet_weights() == x.K4_WEIGHTS


def test_r30_authority_and_exact_owner_reconstruction(start: Start) -> None:
    chase, digest = start
    assert digest == x.R30_SHA256
    assert x.r28.family_state(chase) == (313_568_072, (x.START_OWNER,))
    cert = chase.catalog[x.START_OWNER]
    assert (cert.triangle_cap, cert.s4, cert.relaxation) == (265, 112, x.r28.ROUTE_A)
    assert x.r29.ledger_digest(chase) == x.R30_LEDGER_SHA256 and len(chase.bounds) == 1_795
    assert (chase.cursor, chase.cursor_bound) == (x.CURSOR, 313_556_760)
    assert not chase.attempts and not chase.steps and len(chase.sequence) == 1


def test_tampered_r30_authority_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    with monkeypatch.context() as patch:
        patch.setattr(x, "R30_SHA256", "0" * 64)
        with pytest.raises(AssertionError, match="fingerprint"):
            x.r30_authority()
    with monkeypatch.context() as patch:
        patch.setattr(x, "R30_HEAD", "9fab2301c1634b36ba694a604a412eafe6430fbc")
        with pytest.raises(AssertionError, match="unchanged from R30"):
            x.r30_authority()
    with monkeypatch.context() as patch:
        patch.setattr(x, "PLATEAU_BOUND", x.PLATEAU_BOUND - 1)
        with pytest.raises(AssertionError, match="NEXT_COMPETING_BOUND"):
            x.r30_authority()


def test_owner_route4_holds_for_every_permitted_triangle_count(chase: x.Chase) -> None:
    row = x.certify(chase, x.START_OWNER, 0)
    assert row["STATUS"] == x.CERTIFIED and row["PREMISE_FAILURES"] == []
    assert (row["K4_LOWER_BOUND_AT_CAP"], row["S4_LOWER_BOUND_AT_CAP"]) == (498, 223_104)
    assert (row["OPEN_WEDGES_AT_CAP"], row["TRIANGLE_COUNTS_CHECKED"]) == (35, 265 - 22 + 1)
    assert (row["NEW_BOUND"], row["FAMILY_BOUND_AFTER"], row["OWNER_COUNT_AFTER"]) == (
        313_440_648,
        313_567_960,
        126,
    )
    values = [independent_bound(x.START_OWNER, t, 112) for t in range(22, 266)]
    assert values[-1] == max(values) == row["NEW_BOUND"] == row["BOUND_AT_CAP"]
    assert all(a < b for a, b in pairwise(values))
    cert = chase.catalog[x.START_OWNER]
    assert (cert.relaxation, cert.s4, cert.triangle_cap) == (x.r30.ROUTE_MOTIF, 112, 265)
    assert (cert.source_result, cert.source_row) == (x.RESULT_FILENAME, "ROUTE4_CERTIFICATES[0]")
    again = x.route4_certificate(x.START_OWNER, cert)
    assert again["STATUS"] == x.REJECTED
    assert "NOT_A_TRIANGLE_CAP_CERTIFICATE" in x.rows(again["PREMISE_FAILURES"])


def test_plateau_membership_matches_the_sealed_r30_ledger(chase: x.Chase) -> None:
    ledger: list[dict[str, Any]] = json.loads(R30_RESULT.read_text())["FINAL_RESOLVED_LEDGER"]
    level = sorted(r["PROFILE_ID"] for r in ledger if r["CURRENT_BOUND"] == 313_567_960)
    above = [r["PROFILE_ID"] for r in ledger if r["CURRENT_BOUND"] > 313_567_960]
    assert len(level) == 126 and above == [x.profile_id(x.START_OWNER)]
    with pytest.raises(AssertionError, match="owners"):
        x.certify(chase, x.decode_profile(level[0]), 0)
    x.certify(chase, x.START_OWNER, 0)
    members = x.plateau_members(chase)
    assert sorted(map(x.profile_id, members)) == level


def test_plateau_per_member_certificates_and_complete_family_maximum(chase: x.Chase) -> None:
    x.certify(chase, x.START_OWNER, 0)
    members = x.plateau_members(chase)
    mode = x.shared_class_check(chase, members)
    assert mode["MODE"] == "PER_MEMBER_CLOSED_FORM" and mode["TRIANGLE_CAPS"] == [269]
    assert (mode["WEDGE_COUNTS"], mode["MAX_GRAPH_DEGREES"]) == ([813], [11, 12])
    rows = [x.certify(chase, p, i + 1) for i, p in enumerate(members)]
    assert all(r["STATUS"] == x.CERTIFIED for r in rows)
    for p, r in zip(members, rows, strict=True):
        values = [independent_bound(p, t, 112) for t in range(22, 270)]
        assert r["NEW_BOUND"] == values[-1] == max(values) < 313_567_400
    assert max(x.integer(r["NEW_BOUND"]) for r in rows) == 313_431_064
    family, owners = x.r28.family_state(chase)
    assert (family, list(map(x.profile_id, owners))) == (313_567_400, NEXT_OWNERS)
    assert all(chase.catalog[p].relaxation == x.r28.ROUTE_A for p in owners)
    recompute = x.full_recompute(chase)
    assert (recompute["FAMILY_UPPER_BOUND"], recompute["OWNER_IDS"]) == (313_567_400, NEXT_OWNERS)
    assert x.r28.competing_bound(chase, owners) == 313_567_288 > x.CURSOR_BOUND
    assert [s["FAMILY_BOUND"] for s in chase.sequence] == [313_568_072, 313_567_960, 313_567_400]


def test_tampered_certificates_are_rejected(chase: x.Chase) -> None:
    cert = chase.catalog[x.START_OWNER]
    cases = {
        "BOUND_IS_NOT_THE_CAP_ENVELOPE": replace(cert, triangle_cap=266),
        "TRIANGLE_CAP_OUT_OF_RANGE": replace(cert, triangle_cap=21),
        "S4_NOT_THE_GLOBAL_PROFILE_FLOOR": replace(cert, s4=223_104),
        "NOT_A_TRIANGLE_CAP_CERTIFICATE": replace(cert, relaxation=x.r28.ROUTE_RESIDUAL),
        "CERTIFICATE_PROFILE_MISMATCH": replace(cert, profile=x.CURSOR),
    }
    for failure, tampered in cases.items():
        row = x.route4_certificate(x.START_OWNER, tampered)
        assert row["STATUS"] == x.REJECTED and failure in x.rows(row["PREMISE_FAILURES"])
        assert row["NEW_BOUND"] == tampered.bound
    assert "TRIANGLE_CAP_OUT_OF_RANGE" in x.premise_failures(
        x.START_OWNER, replace(cert, triangle_cap=830 // 3 + 1)
    )
    chase.catalog[x.START_OWNER] = replace(cert, relaxation=x.r30.ROUTE_MOTIF)
    row = x.certify(chase, x.START_OWNER, 0)
    assert row["STATUS"] == x.REJECTED
    assert x.r28.family_state(chase) == (x.START_BOUND, (x.START_OWNER,))


def test_changed_k4_weights_are_rejected(chase: x.Chase, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(x.r30, "k4_quartet_weights", lambda: {"UNIT": 1})
    row = x.certify(chase, x.START_OWNER, 0)
    assert row["PREMISE_FAILURES"] == ["K4_QUARTET_WEIGHTS_CHANGED"]
    assert x.r28.family_state(chase)[0] == x.START_BOUND


@pytest.mark.parametrize("shift", [-1, 1])
def test_inexact_k4_rounding_is_rejected(shift: int, monkeypatch: pytest.MonkeyPatch) -> None:
    real = x.r30.motif_s4_floor

    def shifted(profile: x.DegreeProfile, triangles: int) -> tuple[int, int]:
        k4 = real(profile, triangles)[0] + shift
        return k4, 448 * k4

    assert x.envelope_term(x.START_OWNER, 265, 112)[:3] == (313_440_648, 498, 223_104)
    monkeypatch.setattr(x.r30, "motif_s4_floor", shifted)
    with pytest.raises(AssertionError, match="rounding"):
        x.envelope_term(x.START_OWNER, 265, 112)


@pytest.mark.parametrize("shift", [-1, 1])
def test_bound_not_within_one_above_the_exact_rational_is_rejected(
    shift: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = x.bound_from_cap

    def shifted(profile: x.DegreeProfile, cap: int, s4: int) -> tuple[int, int]:
        s3, bound = real(profile, cap, s4)
        return s3, bound + shift

    monkeypatch.setattr(x, "bound_from_cap", shifted)
    with pytest.raises(AssertionError, match="rounding"):
        x.envelope_term(x.START_OWNER, 265, 112)


@pytest.mark.parametrize(
    ("slope", "offset", "status"),
    [(-1, -1_000_000, x.NOT_AT_CAP), (1, 0, x.NO_DROP)],
)
def test_envelope_off_cap_or_without_a_drop_is_not_applied(
    chase: x.Chase, slope: int, offset: int, status: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def term(profile: x.DegreeProfile, triangles: int, base: int) -> tuple[int, int, int, int]:
        return x.START_BOUND + offset + slope * triangles, 0, base, 0

    monkeypatch.setattr(x, "envelope_term", term)
    row = x.certify(chase, x.START_OWNER, 0)
    assert row["STATUS"] == status and row["NEW_BOUND"] == x.START_BOUND
    assert x.r28.family_state(chase) == (x.START_BOUND, (x.START_OWNER,))


def test_plateau_and_frontier_mismatches_stop(
    chase: x.Chase, monkeypatch: pytest.MonkeyPatch
) -> None:
    x.certify(chase, x.START_OWNER, 0)
    monkeypatch.setattr(x, "PLATEAU_COUNT", 125)
    with pytest.raises(AssertionError, match="126-profile"):
        x.plateau_members(chase)
    chase.cursor_bound = 313_567_500
    with pytest.raises(AssertionError, match="independent family recomputation"):
        x.full_recompute(chase)


def test_witness_soundness_and_overtightening_tripwire(monkeypatch: pytest.MonkeyPatch) -> None:
    assert x.r30.witness_soundness()["STATUS"] == "PASS"
    row = x.witness_route4()
    assert row["ROUTE4_BOUND_AT_REALIZED_CAP"] == 313_449_032 > x.WITNESS_UNION
    heavy = dict.fromkeys(x.K4_WEIGHTS, 2_000)
    monkeypatch.setattr(x, "K4_WEIGHTS", heavy)
    monkeypatch.setattr(x.r30, "k4_quartet_weights", lambda: heavy)
    with pytest.raises(AssertionError, match="over-tightens"):
        x.witness_route4()


def test_committed_result_is_reproduced_without_a_solver(
    sealed: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("a solver was called")

    monkeypatch.setattr(x.r28, "bounded_batch", forbidden)
    monkeypatch.setattr(x.r28, "solve_group", forbidden)
    assert json.loads(json.dumps(x.compute_result())) == sealed


def test_sealed_result_replay_and_handoff(sealed: Any) -> None:
    chase = x.replay_result(sealed, monotonic() + 3600)
    family, owners = x.r28.family_state(chase)
    assert sealed["TASK_STATUS"] == x.SUCCESS_A and sealed["FAMILY_STATUS"] == (
        "OPEN_STRICTLY_TIGHTENED"
    )
    assert family == sealed["FAMILY_UPPER_BOUND"] == 313_567_400
    assert list(map(x.profile_id, owners)) == sealed["FINAL_BOUND_OWNER_IDS"] == NEXT_OWNERS
    assert (sealed["CERTIFIED_FAMILY_DROP"], sealed["REMAINING_GAP"]) == (672, 303_512)
    assert sealed["ROUTE4_OWNER_BOUND"] == 313_440_648 and sealed["OBSTRUCTION"] is None
    assert sealed["PLATEAU_OWNER_COUNT"] == sealed["PLATEAU_CERTIFIED_COUNT"] == 126
    assert sealed["PLATEAU_REMAINING_OWNER_COUNT"] == 0
    assert sealed["ALL_T_CERTIFICATE_STATUS"] == "PASS"
    assert sealed["FULL_LEDGER_RECOMPUTATION"]["STATUS"] == "PASS"
    assert sealed["SOUNDNESS_WITNESS_STATUS"] == sealed["CANONICAL_PRIMITIVE_STATUS"] == "PASS"
    assert (sealed["SOLVER_CALLS"], sealed["NEW_HEAVY_SOLVER_STARTED"]) == (0, "NO")
    assert sealed["NEW_PORTFOLIO_SEARCH_STARTED"] == "NO"
    assert sealed["RESOLVED_LEDGER_COUNT"] == 1_795


def test_tampered_sealed_result_is_rejected(sealed: Any) -> None:
    bound = copy.deepcopy(sealed)
    bound["ROUTE4_CERTIFICATES"][5]["NEW_BOUND"] -= 1
    with pytest.raises(AssertionError, match="certificate replay diverged"):
        x.replay_result(bound, monotonic() + 3600)
    owner = copy.deepcopy(sealed)
    owner["ROUTE4_CERTIFICATES"][0]["PROFILE_ID"] = owner["ROUTE4_CERTIFICATES"][1]["PROFILE_ID"]
    with pytest.raises(AssertionError, match="owners"):
        x.replay_result(owner, monotonic() + 3600)
    ledger = copy.deepcopy(sealed)
    ledger["FINAL_RESOLVED_LEDGER"][0]["CURRENT_BOUND"] += 1
    with pytest.raises(AssertionError, match="ledger replay diverged"):
        x.replay_result(ledger, monotonic() + 3600)
