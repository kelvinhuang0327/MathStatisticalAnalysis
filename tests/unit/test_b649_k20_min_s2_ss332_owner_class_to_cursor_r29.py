"""R29 sealed replay, minimal strengthening, dynamic maxima and false proofs."""

from __future__ import annotations

import copy
import json
import subprocess
from collections.abc import Collection, Sequence
from dataclasses import replace
from time import monotonic

import pytest

from lottolab.research import b649_k20_min_s2_ss332_owner_class_to_cursor_r29 as x


@pytest.fixture(scope="module")
def initial() -> x.r28.Chase:
    return x.replay(x.authority()[0], monotonic() + 3600)


@pytest.fixture
def chase(initial: x.r28.Chase) -> x.r28.Chase:
    fresh = copy.deepcopy(initial)
    fresh.deadline = monotonic() + 3600
    return fresh


def proof(profiles: Sequence[x.DegreeProfile], cap: int, status: str) -> dict[str, object]:
    return {
        "ROUTE": x.r28.ROUTE_A,
        "STATUS": status,
        "CERTIFICATE_KIND": x.r28.KIND_A if status == "INFEASIBLE" else "NOT_CERTIFIED",
        "PROFILE_IDS": list(map(x.profile_id, profiles)),
        "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": cap if status == "INFEASIBLE" else None,
        "REFUTED_GRAPH_TRIANGLE_COUNT": cap + 1,
        "OPEN_WEDGE_CEILING_REFUTED": x.r28.overlap_wedge_count(profiles[0]) - 3 * (cap + 1),
    }


class Recorder:
    def __init__(self, chase: x.r28.Chase, union_status: str = "INFEASIBLE") -> None:
        self.chase = chase
        self.union_status = union_status
        self.calls: list[tuple[tuple[x.DegreeProfile, ...], int, int]] = []

    def __call__(
        self,
        solves: Sequence[x.Solve],
        _seconds: float,
        owners: Collection[x.DegreeProfile],
    ) -> list[dict[str, object]]:
        family, live = x.r28.family_state(self.chase)
        assert set(owners) == set(live)
        out: list[dict[str, object]] = []
        for profiles, cap in solves:
            assert all(self.chase.bounds[p] == family for p in profiles)
            assert all(cap == x.exit_cap(self.chase.catalog[p]) for p in profiles)
            self.calls.append((profiles, cap, family))
            out.append(
                proof(profiles, cap, self.union_status if len(profiles) == 30 else "INFEASIBLE")
            )
        return out


def test_canonical_and_thresholds() -> None:
    assert x.r28.canonical_primitive_preflight() == {
        "STATUS": "PASS",
        "SINGLE_TICKET_ANY_PRIZE": 18_611_432,
        "K20_S1": 372_228_640,
    }
    assert x.START_BOUND - x.NEXT_COMPETING_BOUND == 672
    assert x.START_BOUND - x.NEXT_CURSOR_BOUND == 784


def test_pinned_r28_complete_owner_reconstruction(initial: x.r28.Chase) -> None:
    sealed, digest = x.authority()
    assert digest == x.R28_SHA256
    family, owners = x.r28.family_state(initial)
    assert family == x.START_BOUND and len(owners) == 30
    assert list(map(x.profile_id, owners)) == sealed["FINAL_BOUND_OWNER_IDS"]
    assert {sum(d * d for d in p) for p in owners} == {332}
    assert {initial.catalog[p].triangle_cap for p in owners} == {269}
    assert len(x.ledger(initial)) == 934
    assert x.r28.competing_bound(initial, owners) == 313_612_088
    assert initial.cursor == x.NEXT_CURSOR_PROFILE and initial.cursor not in initial.bounds
    assert initial.attempts == [] and initial.dispatched == []


def test_authority_fingerprint_falsifiable(monkeypatch: pytest.MonkeyPatch) -> None:
    actual = subprocess.check_output

    def altered(command: list[str], **kwargs: object) -> bytes:
        del kwargs
        return actual(command, cwd=x.r28.repo_root()) + b" "

    monkeypatch.setattr(subprocess, "check_output", altered)
    with pytest.raises(AssertionError, match="fingerprint"):
        x.authority()


def test_replay_rejects_sealed_ledger_tampering() -> None:
    sealed = copy.deepcopy(x.authority()[0])
    row = x.r28.object_row(x.r28.rows(sealed["FINAL_RESOLVED_LEDGER"])[-1])
    row["CURRENT_BOUND"] = x.r28.integer(row["CURRENT_BOUND"]) + 1
    with pytest.raises(AssertionError, match="reconstruction"):
        x.replay(sealed, monotonic() + 3600)


def test_minimal_class_cap_switches_to_nine_then_cursor(chase: x.r28.Chase) -> None:
    recorder = Recorder(chase)
    assert x.run(chase, recorder) == x.SUCCESS_B
    assert [len(profiles) for profiles, _, _ in recorder.calls] == [30, 9]
    assert [family for _, _, family in recorder.calls] == [313_612_760, 313_612_088]
    assert [s["FAMILY_BOUND"] for s in chase.sequence] == [313_612_760, 313_612_088, 313_611_976]
    assert x.r28.family_state(chase) == (313_611_976, (x.NEXT_CURSOR_PROFILE,))
    assert max(chase.bounds.values()) <= 313_611_976
    assert all(step["COMPLETE_LEDGER_COUNT"] == 934 for step in chase.steps)
    assert len(chase.steps) == 2


@pytest.mark.parametrize("status", ["FEASIBLE", "UNKNOWN", "EXTERNAL_TIMEOUT", "CHILD_FAILURE"])
def test_noncertified_union_never_changes_bound(chase: x.r28.Chase, status: str) -> None:
    owners = x.r28.family_state(chase)[1]
    before = dict(chase.bounds)
    assert not x.attempt(chase, owners, 10, Recorder(chase, status), "GENERIC_SS332_CLASS")
    assert chase.bounds == before and not chase.steps
    assert x.r28.family_state(chase)[0] == x.START_BOUND
    with pytest.raises(AssertionError, match="must not be rerun"):
        x.guard(chase, owners, 268)


def test_unknown_union_falls_back_only_to_live_residuals(chase: x.r28.Chase) -> None:
    recorder = Recorder(chase, "UNKNOWN")
    assert x.run(chase, recorder) == x.SUCCESS_B
    assert len(recorder.calls[0][0]) == 30
    assert sum(len(profiles) == 1 for profiles, _, _ in recorder.calls) == 30
    assert len(recorder.calls[-1][0]) == 9
    assert len(chase.steps) == 31
    assert [s["OWNER_COUNT"] for s in chase.sequence[:30]] == list(range(30, 0, -1))
    assert x.r28.family_state(chase)[1] == (x.NEXT_CURSOR_PROFILE,)


def test_no_old_cap_no_deep_work_and_no_lower_family_work(chase: x.r28.Chase) -> None:
    owners = x.r28.family_state(chase)[1]
    lower = next(p for p, b in chase.bounds.items() if b < x.NEXT_CURSOR_BOUND)
    for p in (lower, x.NEXT_CURSOR_PROFILE):
        with pytest.raises(AssertionError, match="current family-max"):
            x.guard(chase, (p,), 268)
    for cap in (269, 270, 267):
        with pytest.raises(AssertionError, match="unnecessarily deep"):
            x.guard(chase, owners, cap)
    assert x.attempt(chase, owners, 10, Recorder(chase), "GENERIC_SS332_CLASS")
    with pytest.raises(AssertionError, match="current family-max"):
        x.guard(chase, owners, 267)


def test_complete_ledger_max_and_catalog_divergence(chase: x.r28.Chase) -> None:
    lower = next(p for p, b in chase.bounds.items() if b < x.NEXT_CURSOR_BOUND)
    cert = chase.catalog[lower]
    chase.bounds[lower] = x.START_BOUND + 1
    chase.catalog[lower] = replace(cert, bound=x.START_BOUND + 1)
    assert x.r28.family_state(chase) == (x.START_BOUND + 1, (lower,))
    assert len(x.ledger(chase)) == 934
    chase.bounds[lower] = cert.bound
    with pytest.raises(AssertionError, match="diverged"):
        x.ledger(chase)


def test_wrong_refutation_identity_is_rejected(chase: x.r28.Chase) -> None:
    owners = x.r28.family_state(chase)[1]
    forged = proof(owners, 268, "INFEASIBLE")
    forged["OPEN_WEDGE_CEILING_REFUTED"] = 0
    with pytest.raises(AssertionError, match="identity"):
        x.adopt(chase, (owners, 268), forged)


def test_sealed_r29_replays_every_change_and_complete_ledger(chase: x.r28.Chase) -> None:
    path = x.r28.repo_root() / x.r28.RESULT_DIRECTORY / x.RESULT_FILENAME
    assert path.exists(), "R29 result must be sealed before completion"
    result = x.r28.object_row(json.loads(path.read_text()))
    steps = {
        x.r28.integer(s["ATTEMPT_INDEX"]): s
        for s in map(x.r28.object_row, x.r28.rows(result["REFINEMENT_STEPS"]))
    }
    for index, raw in enumerate(x.r28.rows(result["GROUP_ATTEMPTS"])):
        attempt = x.r28.object_row(raw)
        profiles = tuple(x.decode_profile(p) for p in x.r28.rows(attempt["PROFILE_IDS"]))
        cap = x.r28.integer(attempt["TARGET_TRIANGLE_CAP"])
        x.guard(chase, profiles, cap)
        assert attempt["FAMILY_BOUND_AT_DISPATCH"] == x.r28.family_state(chase)[0]
        chase.attempts.append(attempt)
        accepted = x.adopt(chase, (profiles, cap), attempt)
        assert accepted == (attempt["STATUS"] == "INFEASIBLE")
        if accepted:
            assert chase.steps[-1] == steps[index]
    assert x.ledger(chase) == result["FINAL_RESOLVED_LEDGER"]
    assert x.ledger_digest(chase) == result["FINAL_COMPLETE_LEDGER_SHA256"]
    assert chase.sequence == result["OWNER_CLASS_SEQUENCE"]
    family, owners = x.r28.family_state(chase)
    assert family == result["FAMILY_UPPER_BOUND"]
    assert list(map(x.profile_id, owners)) == result["FINAL_BOUND_OWNER_IDS"]
    assert result["TASK_STATUS"] == x.SUCCESS_B
    assert max(chase.bounds.values()) <= x.NEXT_CURSOR_BOUND
    assert result["NEXT_COMPETING_BOUND"] == max(chase.bounds.values())
    assert result["INITIAL_NEXT_COMPETING_BOUND"] == 313_612_088
    assert result["CURSOR_PROFILE_SOLVES"] == 0
