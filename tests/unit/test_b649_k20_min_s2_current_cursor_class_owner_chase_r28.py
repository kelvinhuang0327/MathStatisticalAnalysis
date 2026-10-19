"""R28: authority replay, cursor plateau class, owner chase and its guards."""

from __future__ import annotations

import copy
import json
from collections.abc import Collection, Sequence
from dataclasses import replace
from pathlib import Path
from time import monotonic

import pytest

from lottolab.research import b649_k20_min_s2_current_cursor_class_owner_chase_r28 as x
from lottolab.research.b649_k20_min_s2_resolved_above_cursor_owner_chase_r20 import (
    Certificate,
    bound_from_cap,
    decode_profile,
    profile_id,
)

PAIR = (decode_profile("66665555554440000000"), decode_profile("66655555555530000000"))


@pytest.fixture(scope="module")
def started() -> tuple[x.Chase, dict[str, object], dict[str, str]]:
    return x.start_chase(monotonic() + 3_600)


@pytest.fixture
def chase(started: tuple[x.Chase, dict[str, object], dict[str, str]]) -> x.Chase:
    fresh = copy.deepcopy(started[0])
    fresh.deadline = monotonic() + 3_600
    return fresh


def refutation(profiles: Sequence[x.DegreeProfile], cap: int, status: str) -> dict[str, object]:
    return {
        "ROUTE": x.ROUTE_A,
        "STATUS": status,
        "CERTIFICATE_KIND": x.KIND_A if status == "INFEASIBLE" else "NOT_CERTIFIED",
        "PROFILE_IDS": [profile_id(p) for p in profiles],
        "CERTIFIED_GRAPH_TRIANGLE_UPPER_BOUND": cap if status == "INFEASIBLE" else None,
        "REFUTED_GRAPH_TRIANGLE_COUNT": cap + 1,
        "OPEN_WEDGE_CEILING_REFUTED": x.overlap_wedge_count(profiles[0]) - 3 * (cap + 1),
        "SOLVER_WALL_TIME_SECONDS": 0.0,
    }


class Recorder:
    """Synthetic prover that also asserts it only ever sees current max owners."""

    def __init__(self, chase: x.Chase, decide: dict[int, str] | None = None) -> None:
        self.chase = chase
        self.decide = decide or {}
        self.calls: list[tuple[x.Solve, int]] = []

    def __call__(
        self, solves: Sequence[x.Solve], _seconds: float, owners: Collection[x.DegreeProfile]
    ) -> list[dict[str, object]]:
        family, live = x.family_state(self.chase)
        assert set(owners) == set(live)
        out: list[dict[str, object]] = []
        for profiles, cap in solves:
            assert all(self.chase.bounds[p] == family for p in profiles)
            assert all(cap < (self.chase.catalog[p].triangle_cap or 0) for p in profiles)
            self.calls.append(((profiles, cap), family))
            out.append(refutation(profiles, cap, self.decide.get(cap, "INFEASIBLE")))
        return out


def passing_check(cert: Certificate) -> dict[str, object]:
    return {"STATUS": "PASS", "PROFILE_ID": profile_id(cert.profile)}


def test_canonical_primitives() -> None:
    assert x.canonical_primitive_preflight() == {
        "STATUS": "PASS",
        "SINGLE_TICKET_ANY_PRIZE": 18_611_432,
        "K20_S1": 372_228_640,
    }
    assert x.k20_min_s2_s4_lower_bound_certificate().s4_lower_bound == 112


def test_ec95e55_authority_fingerprint_and_replay(
    started: tuple[x.Chase, dict[str, object], dict[str, str]],
) -> None:
    result, digest = x.r26_authority()
    assert digest == x.R26_RESULT_SHA256
    bounds, catalog = x.replay_authority(result)
    assert len(bounds) == 408 and max(bounds.values()) == 313_637_736
    assert all(catalog[p].bound == b for p, b in bounds.items())
    _, assertions, hashes = started
    assert hashes[f"{x.RESULT_DIRECTORY}/{x.R26_RESULT}"] == x.R26_RESULT_SHA256
    assert assertions["RESOLVED_ABOVE_CURSOR_COUNT"] == 0
    assert assertions["MAX_RESOLVED_BOUND"] == 313_637_736
    assert assertions["FROZEN_R25_CLASS_MEMBERS_EXPANDED"] == 76


def test_replay_rejects_tampered_authority() -> None:
    result, _ = x.r26_authority()
    tampered = copy.deepcopy(result)
    ledger = x.rows(tampered["FINAL_RESOLVED_LEDGER"])
    x.object_row(ledger[0])["CURRENT_BOUND"] = 313_637_735
    with pytest.raises(AssertionError):
        x.replay_authority(tampered)


def test_stale_r27_rejection_guard() -> None:
    assert x.stale_r27_guard()["STATUS"] == "PASS"
    with pytest.raises(AssertionError, match="stale R27"):
        x.assert_not_stale_r27(x.STALE_R27_BASE_HEAD, ())
    with pytest.raises(AssertionError, match="stale R27"):
        x.assert_not_stale_r27(
            x.BASE_HEAD,
            ["src/lottolab/research/b649_k20_min_s2_current_cursor_dynamic_closure_r27.py"],
        )


def test_start_family_and_frozen_class(chase: x.Chase) -> None:
    assert x.family_state(chase) == (313_637_848, (x.START_CURSOR,))
    assert not [p for p, b in chase.bounds.items() if b > x.START_BOUND]
    frozen = [p for p, c in chase.catalog.items() if c.source_row == "PLATEAU_CERTIFICATE"]
    assert len(frozen) == 76
    assert {chase.bounds[p] for p in frozen} == {313_628_776}
    assert {sum(d * d for d in p) for p in frozen} == {318}


def test_plateau_membership_and_class_certificate(chase: x.Chase) -> None:
    row = x.certify_cursor_plateau(chase)
    members = [decode_profile(p) for p in x.rows(row["PLATEAU_PROFILE_IDS"])]
    assert row["PLATEAU_PROFILE_COUNT"] == len(members) == 74
    assert members[0] == x.START_CURSOR
    assert row["SQUARE_SUMS"] == [316]
    assert row["INDUCED_P3_OPEN_WEDGE_LOWER_BOUND"] == 5
    assert row["GRAPH_TRIANGLE_UPPER_BOUND"] == 272
    assert row["CLASS_FAMILY_UPPER_BOUND"] == 313_625_976
    assert row["RESIDUAL_MEMBER_COUNT"] == 0 and row["INDIVIDUAL_SOLVES"] == 0
    assert row["NEXT_CURSOR_PROFILE"] == profile_id(x.EXPECTED_NEXT_CURSOR)
    assert row["NEXT_CURSOR_BOUND"] == 313_635_048
    assert all(chase.bounds[p] == 313_625_976 for p in members)
    # Owner switch: the resolved pair 112 below the cursor now owns the family.
    assert x.family_state(chase) == (313_637_736, PAIR)


def test_family_max_recomputation_is_complete(chase: x.Chase) -> None:
    x.certify_cursor_plateau(chase)
    probe = next(p for p, c in chase.catalog.items() if c.source_row == "PLATEAU_CERTIFICATE")
    cert = chase.catalog[probe]
    chase.bounds[probe] = 313_700_000
    chase.catalog[probe] = replace(cert, bound=313_700_000)
    assert x.family_state(chase) == (313_700_000, (probe,))
    chase.bounds[probe] = cert.bound
    with pytest.raises(AssertionError, match="diverged"):
        x.family_state(chase)


def test_target_caps() -> None:
    result, _ = x.r26_authority()
    _, catalog = x.replay_authority(result)
    cert = catalog[PAIR[0]]
    deep, shallow = x.target_caps(cert, 313_637_176)
    assert x.cap_bound(cert, deep) <= x.SUCCESS_B_TARGET < x.cap_bound(cert, deep + 1)
    assert x.cap_bound(cert, shallow) <= 313_637_176 < x.cap_bound(cert, shallow + 1)
    assert deep <= shallow < (cert.triangle_cap or 0)


def test_owner_chase_switches_and_reaches_success_b(chase: x.Chase) -> None:
    x.record_owner(chase)
    x.certify_cursor_plateau(chase)
    prover = Recorder(chase)
    status, stuck = x.run_chase(chase, prover, passing_check)
    family, _ = x.family_state(chase)
    assert status == x.SUCCESS_B and not stuck
    assert x.START_BOUND - family >= 25_000
    sequence = [x.integer(e["FAMILY_BOUND"]) for e in chase.sequence]
    assert sequence[:2] == [313_637_848, 313_637_736]
    assert sequence == sorted(sequence, reverse=True)
    assert chase.sequence[1]["OWNER_TYPES"] == [x.RESOLVED_OWNER]
    kinds = {t for e in chase.sequence for t in x.rows(e["OWNER_TYPES"])}
    assert {x.RESOLVED_OWNER, x.CLASS_OWNER} <= kinds
    assert len(chase.plateaus) >= 2
    # Only the actual max ever reached the prover, in non-increasing order.
    seen = [family for _, family in prover.calls]
    assert seen == sorted(seen, reverse=True)
    for step in chase.steps:
        assert x.integer(step["FAMILY_BOUND_AFTER"]) <= x.integer(step["FAMILY_BOUND_BEFORE"])


def test_feasible_or_unknown_never_certifies(chase: x.Chase) -> None:
    x.certify_cursor_plateau(chase)
    before = dict(chase.bounds)
    prover = Recorder(chase, {cap: "FEASIBLE" for cap in range(22, 300)})
    status, stuck = x.run_chase(chase, prover, passing_check)
    assert status == x.STOPPED and set(stuck) <= set(PAIR)
    assert chase.bounds == before and not chase.steps[1:]
    owner = stuck[0]
    deep = x.target_caps(chase.catalog[owner], 0)[0]
    with pytest.raises(AssertionError, match="never repeated"):
        x.dispatch(chase, [((owner,), deep)], 1, prover, "T")


def test_bisection_falls_back_to_exit_cap(chase: x.Chase) -> None:
    x.certify_cursor_plateau(chase)
    cert = chase.catalog[PAIR[0]]
    deep, shallow = x.target_caps(cert, x.competing_bound(chase, PAIR))
    assert shallow > deep
    prover = Recorder(chase, {c: "UNKNOWN" for c in range(22, shallow)})
    stuck = x.refine_group(chase, (cert,), prover, passing_check)
    assert not stuck
    targets = [solve[1] for solve, _ in prover.calls]
    assert targets[0] == deep and targets[-1] == shallow
    assert chase.catalog[PAIR[0]].triangle_cap == shallow
    assert chase.bounds[PAIR[0]] == bound_from_cap(PAIR[0], shallow, cert.s4 or 0)[1]


def test_no_old_work_and_owner_scope_guards(chase: x.Chase) -> None:
    prover = Recorder(chase)
    lower = next(p for p, b in chase.bounds.items() if b < 313_637_000)
    with pytest.raises(AssertionError, match="current family-max"):
        x.dispatch(chase, [((PAIR[0],), 260)], 1, prover, "T")
    x.certify_cursor_plateau(chase)
    with pytest.raises(AssertionError, match="current family-max"):
        x.dispatch(chase, [((lower,), 200)], 1, prover, "T")
    cap = chase.catalog[PAIR[0]].triangle_cap or 0
    with pytest.raises(AssertionError, match="re-proved"):
        x.dispatch(chase, [((PAIR[0],), cap)], 1, prover, "T")
    with pytest.raises(AssertionError, match="unresolved cursor"):
        x.certify_cursor_plateau(chase)


def test_refutation_identity_is_checked(chase: x.Chase) -> None:
    x.certify_cursor_plateau(chase)
    deep = x.target_caps(chase.catalog[PAIR[0]], 0)[0]
    proof = refutation((PAIR[0],), deep, "INFEASIBLE")
    proof["OPEN_WEDGE_CEILING_REFUTED"] = 0
    chase.attempts.append({"PROFILE_IDS": [profile_id(PAIR[0])], "TARGET_TRIANGLE_CAP": deep})
    with pytest.raises(AssertionError, match="identity"):
        x.apply_proof(chase, ((PAIR[0],), deep), proof)


def test_model_identity_and_witness_nonvacuity(chase: x.Chase) -> None:
    assert x.model_identity()["STATUS"] == "PASS"
    statuses = x.object_row(x.witness_nonvacuity(chase.catalog[PAIR[1]])["STATUSES"])
    assert statuses["UNFIXED_AT_WITNESS_COUNT"] in ("OPTIMAL", "FEASIBLE")
    assert statuses["FIXED_AT_WITNESS_COUNT"] == "OPTIMAL"
    assert statuses["FIXED_ONE_BELOW"] == "INFEASIBLE"


def test_sealed_result_replays_to_its_ledger(
    started: tuple[x.Chase, dict[str, object], dict[str, str]],
) -> None:
    path = x.repo_root() / x.RESULT_DIRECTORY / x.RESULT_FILENAME
    if not path.exists():
        pytest.skip("R28 result not yet sealed")
    result = x.object_row(json.loads(Path(path).read_text()))
    chase = copy.deepcopy(started[0])
    chase.deadline = monotonic() + 3_600
    steps = [x.object_row(s) for s in x.rows(result["REFINEMENT_STEPS"])]
    attempts = [x.object_row(a) for a in x.rows(result["GROUP_ATTEMPTS"])]
    for step in steps:
        if step["KIND"] == "CURSOR_PLATEAU_CLASS_CERTIFICATE":
            x.certify_cursor_plateau(chase)
        else:
            attempt = attempts[x.integer(step["ATTEMPT_INDEX"])]
            profiles = tuple(decode_profile(p) for p in x.rows(attempt["PROFILE_IDS"]))
            cap = x.integer(step["TRIANGLE_CAP"])
            chase.attempts.append(attempt)
            assert x.apply_proof(chase, (profiles, cap), attempt)
        assert x.family_state(chase)[0] == step["FAMILY_BOUND_AFTER"]
    family, owners = x.family_state(chase)
    assert family == result["FAMILY_UPPER_BOUND"]
    assert list(map(profile_id, owners)) == result["FINAL_BOUND_OWNER_IDS"]
    ledger = {
        decode_profile(r["PROFILE_ID"]): r["CURRENT_BOUND"]
        for r in map(x.object_row, x.rows(result["FINAL_RESOLVED_LEDGER"]))
    }
    assert ledger == chase.bounds
    assert result["BASE_HEAD"] == x.BASE_HEAD and result["NO_OLD_WORK_GUARD"] == "PASS"
