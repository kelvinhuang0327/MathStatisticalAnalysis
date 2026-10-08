"""R30 sealed R29 replay, plateau class proof, owner chase, Route 4, resume, guards."""

from __future__ import annotations

import copy
import hashlib
import json
import random
from collections.abc import Collection, Mapping, Sequence
from dataclasses import replace
from itertools import combinations
from math import comb
from pathlib import Path
from time import monotonic

import pytest

from lottolab.research import b649_k20_min_s2_current_cursor_dynamic_family_max_r30 as x
from lottolab.research.b649_official_any_prize_exact import (
    all_main_draw_masks,
    evaluate_portfolio,
)

RESULT = x.r28.repo_root() / x.RESULT_DIRECTORY / x.RESULT_FILENAME
Initial = tuple[x.Chase, str, x.OldWork]


@pytest.fixture(scope="module")
def initial() -> Initial:
    return x.start_chase(monotonic() + 3600)


@pytest.fixture
def chase(initial: Initial) -> x.Chase:
    fresh = copy.deepcopy(initial[0])
    fresh.deadline = monotonic() + 3600
    return fresh


@pytest.fixture
def certified(chase: x.Chase) -> x.Chase:
    x.certify_plateau(chase)
    return chase


class Stop(Exception):
    pass


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
    """Fake prover: asserts every target is a current family-max owner at its exit cap."""

    def __init__(
        self,
        chase: x.Chase,
        statuses: dict[x.DegreeProfile, list[str]] | None = None,
        plateau_stop: int | None = None,
        call_stop: int | None = None,
    ) -> None:
        self.chase = chase
        self.statuses = statuses or {}
        self.plateau_stop = plateau_stop
        self.call_stop = call_stop
        self.calls: list[tuple[x.DegreeProfile, int, int, float]] = []
        self.batches = 0

    def __call__(
        self, solves: Sequence[x.Solve], seconds: float, owners: Collection[x.DegreeProfile]
    ) -> list[dict[str, object]]:
        if self.plateau_stop is not None and len(self.chase.plateaus) >= self.plateau_stop:
            raise Stop
        if self.call_stop is not None and self.batches >= self.call_stop:
            raise Stop
        self.batches += 1
        family, live = x.r28.family_state(self.chase)
        assert set(owners) == set(live)
        out: list[dict[str, object]] = []
        for profiles, cap in solves:
            (p,) = profiles
            assert p in live and self.chase.bounds[p] == family
            assert cap == x.exit_cap(self.chase.catalog[p])
            self.calls.append((p, cap, family, seconds))
            queue = self.statuses.get(p, [])
            out.append(proof(profiles, cap, queue.pop(0) if queue else "INFEASIBLE"))
        return out


def no_motif(profile: x.DegreeProfile, triangles: int) -> tuple[int, int]:
    return 0, 0


def no_log() -> x.DurableLog:
    return x.DurableLog(None, {})


def test_canonical_primitives_and_owner_margin() -> None:
    assert x.r28.canonical_primitive_preflight() == {
        "STATUS": "PASS",
        "SINGLE_TICKET_ANY_PRIZE": 18_611_432,
        "K20_S1": 372_228_640,
    }
    assert x.START_BOUND - x.START_MAX_RESOLVED == x.OWNER_MARGIN == 672
    assert x.START_BOUND - x.R29_INCUMBENT == x.START_GAP == 372_315
    assert x.INCUMBENT == 313_263_888 and x.INCUMBENT - x.WITNESS_UNION == 21
    assert x.START_BOUND - x.EXPECTED_CLASS_BOUND >= x.OWNER_MARGIN + 1


def test_r29_sealed_fingerprint_and_complete_ledger_replay(
    initial: Initial,
) -> None:
    chase, digest, old = initial
    assert digest == x.R29_SHA256
    assert x.r28.family_state(chase) == (x.START_BOUND, (x.START_CURSOR,))
    assert x.r29.ledger_digest(chase) == x.R29_LEDGER_SHA256
    assert len(chase.bounds) == x.LEDGER_COUNT
    assert max(chase.bounds.values()) == x.START_MAX_RESOLVED
    assert chase.cursor_bound == x.START_BOUND
    assert len(old) == 514 and not chase.attempts and not chase.steps


def test_tampered_r29_fingerprint_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(x, "R29_SHA256", "0" * 64)
    with pytest.raises(AssertionError, match="fingerprint"):
        x.r29_authority()


def test_phase1_exact_plateau_membership(chase: x.Chase) -> None:
    row = x.phase1_freeze(chase)
    ids = x.rows(row["PLATEAU_PROFILE_IDS"])
    assert row["PLATEAU_PROFILE_COUNT"] == len(ids) == len(set(ids)) == 112
    assert ids[0] == x.profile_id(x.START_CURSOR) and row["CURSOR_IS_MEMBER"] is True
    assert row["SQUARE_SUMS"] == [306]
    assert row["RESOLVED_ABOVE_CURSOR_COUNT"] == 0
    assert row["MAX_RESOLVED_BOUND"] == 313_611_304
    assert row["OWNER_MARGIN_OVER_RESOLVED"] == 672
    assert row["CLASS_DROP_THAT_EXPOSES_RESOLVED_MAX"] == 673
    assert row["NEXT_LOWER_PROFILE"] == x.profile_id(x.EXPECTED_NEXT_CURSOR)
    assert row["NEXT_LOWER_BOUND"] == x.EXPECTED_NEXT_BOUND
    members = [x.decode_profile(str(p)) for p in ids]
    assert all(p not in chase.bounds for p in members)
    assert all(x.coarse_profile_envelope(p).family_upper_bound == x.START_BOUND for p in members)


def test_phase2_class_certificate_exposes_resolved_owner(chase: x.Chase) -> None:
    frozen = x.phase1_freeze(chase)
    row = x.certify_plateau(chase)
    assert row["PLATEAU_MEMBERSHIP_SHA256"] == frozen["PLATEAU_MEMBERSHIP_SHA256"]
    assert row["CLASS_DOMINANCE"] == "COMPLETE" and row["INDIVIDUAL_SOLVES"] == 0
    assert row["GRAPH_TRIANGLE_UPPER_BOUND"] == 270
    assert row["CLASS_FAMILY_UPPER_BOUND"] == x.EXPECTED_CLASS_BOUND
    family, owners = x.r28.family_state(chase)
    assert family == x.START_MAX_RESOLVED and len(owners) == 88
    assert chase.cursor not in owners and chase.cursor == x.EXPECTED_NEXT_CURSOR
    assert {x.r28.owner_type(chase, p) for p in owners} == {x.r28.CLASS_OWNER}
    assert {sum(d * d for d in p) for p in owners} == {314}
    assert len(chase.bounds) == x.LEDGER_COUNT + 112
    assert [s["FAMILY_BOUND"] for s in chase.sequence] == [x.START_BOUND, x.START_MAX_RESOLVED]


def test_dynamic_owner_switch_regression(certified: x.Chase, initial: Initial) -> None:
    recorder = Recorder(certified, plateau_stop=2)
    with pytest.raises(Stop):
        x.run(certified, recorder, initial[2], no_log())
    sequence = [x.integer(s["FAMILY_BOUND"]) for s in certified.sequence]
    assert sequence == sorted(set(sequence), reverse=True)
    assert len(certified.plateaus) == 2
    assert certified.plateaus[1]["CURSOR_PROFILE"] == x.profile_id(x.EXPECTED_NEXT_CURSOR)
    assert certified.plateaus[1]["ACTIVE_COARSE_BOUND"] == x.EXPECTED_NEXT_BOUND
    first = [x.decode_profile(str(p)) for p in x.rows(certified.sequence[1]["OWNER_IDS"])]
    assert [c[0] for c in recorder.calls[:88]] == first
    for step in certified.steps:
        if step["KIND"] == x.KIND_REFUTATION:
            assert x.integer(step["FAMILY_BOUND_BEFORE"]) >= x.integer(step["FAMILY_BOUND_AFTER"])
    assert all(c[3] == x.MEMBER_SECONDS for c in recorder.calls)


def test_feasible_never_lowers_a_cap_and_unknown_is_retried(
    certified: x.Chase, initial: Initial
) -> None:
    _, owners = x.r28.family_state(certified)
    feasible, unknown = owners[0], owners[1]
    cap = x.integer(certified.catalog[feasible].triangle_cap)
    recorder = Recorder(
        certified, {feasible: ["FEASIBLE"], unknown: ["UNKNOWN", "INFEASIBLE"]}, call_stop=2
    )
    with pytest.raises(Stop):
        x.run(certified, recorder, initial[2], no_log())
    cert = certified.catalog[feasible]
    floor = max(112, x.motif_s4_floor(feasible, cap)[1])
    assert cert.triangle_cap == cap and cert.relaxation == x.ROUTE_MOTIF and cert.s4 == 112
    assert certified.bounds[feasible] == x.bound_from_cap(feasible, cap, floor)[1]
    pid = x.profile_id(feasible)
    assert [s["KIND"] for s in certified.steps if s.get("PROFILE_ID") == pid] == [x.KIND_MOTIF]
    (motif,) = [s for s in certified.steps if s["KIND"] == x.KIND_MOTIF]
    assert certified.attempts[x.integer(motif["TRIGGER_ATTEMPT_INDEX"])]["STATUS"] == "FEASIBLE"
    assert certified.bounds[unknown] < x.START_MAX_RESOLVED
    assert [c[3] for c in recorder.calls if c[0] == unknown] == [
        x.MEMBER_SECONDS,
        x.RETRY_SECONDS,
    ]
    stages = [a["STAGE"] for a in certified.attempts if a["PROFILE_IDS"] == [x.profile_id(unknown)]]
    assert stages == [x.STAGE_MEMBER, x.STAGE_RETRY]


@pytest.mark.parametrize("status", ["FEASIBLE", "OPTIMAL", "UNKNOWN"])
def test_failed_exact_support_without_route4_drop_stops_unchanged(
    certified: x.Chase, initial: Initial, monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    monkeypatch.setattr(x, "motif_s4_floor", no_motif)
    _, owners = x.r28.family_state(certified)
    owner = owners[0]
    recorder = Recorder(certified, {owner: [status, status]}, call_stop=3)
    assert x.run(certified, recorder, initial[2], no_log()) == (x.STOPPED, (owner,))
    assert certified.bounds[owner] == x.START_MAX_RESOLVED
    assert certified.catalog[owner].relaxation == x.r28.ROUTE_CLASS
    assert x.r28.family_state(certified)[0] == x.START_MAX_RESOLVED


def test_child_failure_never_triggers_route4(certified: x.Chase, initial: Initial) -> None:
    _, owners = x.r28.family_state(certified)
    owner = owners[0]
    recorder = Recorder(certified, {owner: ["CHILD_FAILURE"]}, call_stop=2)
    assert x.run(certified, recorder, initial[2], no_log()) == (x.STOPPED, (owner,))
    assert certified.bounds[owner] == x.START_MAX_RESOLVED
    assert not [s for s in certified.steps if s["KIND"] == x.KIND_MOTIF]


def test_budget_exhaustion_is_success_c_not_a_stop(certified: x.Chase, initial: Initial) -> None:
    _, owners = x.r28.family_state(certified)
    recorder = Recorder(certified, {owners[0]: ["PROOF_BUDGET_EXHAUSTED"]})
    status, stuck = x.run(certified, recorder, initial[2], no_log())
    assert (status, stuck) == (x.SUCCESS_C, (owners[0],))


def test_mismatched_infeasible_identity_raises(certified: x.Chase) -> None:
    _, owners = x.r28.family_state(certified)
    p, q = owners[0], owners[1]
    cap = x.exit_cap(certified.catalog[p])
    with pytest.raises(AssertionError, match="identity"):
        x.adopt(certified, ((p,), cap), 0, proof((q,), cap, "INFEASIBLE"))
    with pytest.raises(AssertionError, match="identity"):
        x.adopt(certified, ((p,), cap), 0, proof((p,), cap - 1, "INFEASIBLE"))


def test_guards_reject_unions_non_owners_deep_old_and_failed(
    certified: x.Chase, initial: Initial
) -> None:
    old = initial[2]
    family, owners = x.r28.family_state(certified)
    p, q = owners[0], owners[1]
    cap = x.exit_cap(certified.catalog[p])
    x.guard(certified, ((p,), cap), old)
    with pytest.raises(AssertionError, match="union"):
        x.guard(certified, ((p, q), cap), old)
    below = next(r for r, b in certified.bounds.items() if b < family)
    with pytest.raises(AssertionError, match="owners"):
        x.guard(certified, ((below,), x.exit_cap(certified.catalog[below])), old)
    with pytest.raises(AssertionError, match="deep"):
        x.guard(certified, ((p,), cap - 1), old)
    with pytest.raises(AssertionError, match="rerun"):
        x.guard(certified, ((p,), cap), frozenset({((x.profile_id(p),), cap)}))
    certified.failed[((p,), cap)] = "FEASIBLE"
    with pytest.raises(AssertionError, match="rerun"):
        x.guard(certified, ((p,), cap), old)
    cursor = certified.cursor
    assert cursor is not None
    with pytest.raises(AssertionError, match="owner"):
        x.guard(certified, ((cursor,), cap), old)


def test_exit_cap_is_shallowest_strict_tightening(certified: x.Chase) -> None:
    _, owners = x.r28.family_state(certified)
    cert = certified.catalog[owners[0]]
    assert x.exit_cap(cert) == x.integer(cert.triangle_cap) - 1
    lifted = x.bound_from_cap(cert.profile, x.integer(cert.triangle_cap) - 1, 112)[1]
    residual = replace(cert, bound=lifted)
    assert x.exit_cap(residual) == x.integer(cert.triangle_cap) - 2
    floor = replace(cert, triangle_cap=x.K20_TRIPLE_SUPPORT_COUNT)
    with pytest.raises(AssertionError, match="no stricter"):
        x.exit_cap(floor)


def test_durable_log_resume_serves_logged_proofs(
    chase: x.Chase, initial: Initial, tmp_path: Path
) -> None:
    resumed = copy.deepcopy(chase)
    x.certify_plateau(chase)
    first = Recorder(chase, call_stop=2)
    with pytest.raises(Stop):
        x.run(chase, first, initial[2], x.DurableLog(tmp_path, {}))
    logged = (tmp_path / x.PROOF_LOG).read_text().splitlines()
    assert len(logged) == len(first.calls) == 88
    checkpoint = json.loads((tmp_path / x.CHECKPOINT).read_text())
    assert checkpoint["FAMILY_UPPER_BOUND"] == x.r28.family_state(chase)[0]
    assert checkpoint["COMPLETE_LEDGER_SHA256"] == x.r29.ledger_digest(chase)
    x.certify_plateau(resumed)
    log = x.DurableLog(tmp_path, x.load_replayed(tmp_path / x.PROOF_LOG))
    second = Recorder(resumed, call_stop=0)
    with pytest.raises(Stop):
        x.run(resumed, second, initial[2], log)
    assert log.served == 88 and not second.calls
    assert resumed.bounds == chase.bounds


def test_sealed_result_complete_ledger_replay(initial: Initial) -> None:
    result = x.object_row(json.loads(RESULT.read_text()))
    assert result["TASK_ID"] == x.TASK_ID and result["BASE_HEAD"] == x.BASE_HEAD
    assert result["TASK_STATUS"] in (x.SUCCESS_A, x.SUCCESS_B, x.SUCCESS_C, x.STOPPED)
    assert result["CANONICAL_PRIMITIVE_STATUS"] == "PASS"
    assert result["FAMILY_UPPER_BOUND"] == result["SOLVER_CERTIFIED_BOUND"]
    assert result["REMAINING_GAP"] == x.integer(result["FAMILY_UPPER_BOUND"]) - x.INCUMBENT
    assert result["UNION_ATTEMPTS"] == 0 and result["R28_R29_PROOF_RERUN_COUNT"] == 0
    chase = x.replay_result(result, monotonic() + 3600)
    family, owners = x.r28.family_state(chase)
    assert result["FINAL_BOUND_OWNER_IDS"] == list(map(x.profile_id, owners))
    assert result["MAX_RESOLVED_BOUND"] == max(chase.bounds.values()) <= family
    old = initial[2]
    attempts = [x.object_row(a) for a in x.rows(result["GROUP_ATTEMPTS"])]
    first = {
        (tuple(map(str, x.rows(a["PROFILE_IDS"]))), a["TARGET_TRIANGLE_CAP"])
        for a in attempts[: x.CHECKPOINT_ATTEMPTS]
    }
    for index, attempt in enumerate(attempts):
        ids = tuple(map(str, x.rows(attempt["PROFILE_IDS"])))
        key = (ids, attempt["TARGET_TRIANGLE_CAP"])
        assert len(ids) == 1 and key not in old
        assert index < x.CHECKPOINT_ATTEMPTS or key not in first
        assert attempt["CURRENT_BOUND"] == attempt["FAMILY_BOUND_AT_DISPATCH"]
        assert x.integer(attempt["TARGET_TRIANGLE_CAP"]) < x.integer(
            attempt["CURRENT_TRIANGLE_CAP"]
        )
    for step in map(x.object_row, x.rows(result["REFINEMENT_STEPS"])):
        if step["KIND"] == x.KIND_REFUTATION:
            assert attempts[x.integer(step["ATTEMPT_INDEX"])]["STATUS"] == "INFEASIBLE"
        if step["KIND"] == x.KIND_MOTIF:
            assert attempts[x.integer(step["TRIGGER_ATTEMPT_INDEX"])]["STATUS"] in (
                x.ROUTE4_TRIGGERS
            )
    sequence = [
        x.integer(x.object_row(s)["FAMILY_BOUND"]) for s in x.rows(result["OWNER_CLASS_SEQUENCE"])
    ]
    assert sequence == sorted(set(sequence), reverse=True)
    assert min(sequence) >= x.WITNESS_UNION


def test_resumed_result_accounting_and_route4_certificate() -> None:
    result = x.object_row(json.loads(RESULT.read_text()))
    checkpoint = x.object_row(result["RESUME_CHECKPOINT"])
    assert checkpoint["CHECKPOINT_REPLAY_STATUS"] == "PASS"
    assert checkpoint["RESUME_CHECKPOINT_BOUND"] == x.CHECKPOINT_BOUND
    assert checkpoint["CHECKPOINT_OWNER"] == x.profile_id(x.CHECKPOINT_OWNER)
    assert checkpoint["SEGMENT1_RESULT_SHA256"] == x.SEGMENT1_SHA256
    assert result["TASK_STATUS"] in (x.SUCCESS_A, x.SUCCESS_B, x.SUCCESS_C)
    assert result["ROUTE4_STATUS"] == "OWNER_SWITCH" and result["INCUMBENT"] == x.INCUMBENT
    route4 = x.object_row(result["ROUTE4_CERTIFICATE"])
    assert route4["PROFILE_ID"] == x.profile_id(x.CHECKPOINT_OWNER)
    assert route4["TRIGGER_ATTEMPT_INDEX"] == x.CHECKPOINT_TRIGGER
    assert (route4["K4_LOWER_BOUND_AT_CAP"], route4["S4_LOWER_BOUND_AT_CAP"]) == (544, 243_712)
    assert route4["GLOBAL_S4_FLOOR"] == 112
    assert route4["NEW_BOUND"] == 313_449_032
    assert route4["FAMILY_BOUND_AFTER"] == x.CHECKPOINT_NEXT_COMPETITOR
    assert x.object_row(result["SOUNDNESS_WITNESS"])["STATUS"] == "PASS"
    capability = x.object_row(result["METHOD_CAPABILITY"])
    assert capability["ROUTES_1_TO_4_FLOOR_FOR_INCUMBENT_PROFILE"] == 313_399_016
    assert capability["ROUTES_1_TO_4_SHORTFALL_TO_INCUMBENT"] == 135_128
    assert capability["SUCCESS_A_REACHABLE_BY_ROUTES_1_TO_4"] is False
    assert result["TASK_STATUS"] != x.SUCCESS_A and result["TOTAL_BUDGET_CHECK"] == "PASS"
    prior, resumed = result["PRIOR_SEGMENT_WALL_TIME"], result["RESUME_SEGMENT_WALL_TIME"]
    assert isinstance(prior, float) and isinstance(resumed, float)
    assert result["ORIGINAL_PROOF_BUDGET"] == x.PROOF_WALL_SECONDS
    assert result["TOTAL_PROOF_WALL_TIME"] == prior + resumed
    assert result["SEGMENT1_SEALED_WALL_SECONDS"] == x.SEGMENT1_WALL_SECONDS
    assert prior == 2113.444 and resumed <= 1486.556 == result["SEGMENT2_CAP_SECONDS"]
    assert prior + resumed <= x.PROOF_WALL_SECONDS
    assert x.integer(result["FAMILY_UPPER_BOUND"]) < x.CHECKPOINT_BOUND
    assert result["TASK_STATUS"] == x.SUCCESS_C and result["NEXT_BLOCKER_OWNER_IDS"] == []
    assert (result["FAMILY_UPPER_BOUND"], result["REMAINING_GAP"]) == (313_568_072, 304_184)
    assert result["FINAL_BOUND_OWNER_IDS"] == ["66665555554422000000"]
    assert result["RESOLVED_LEDGER_COUNT"] == 1_795
    assert result["FINAL_COMPLETE_LEDGER_SHA256"] == (
        "55d439314e0df2955236b2263e7df7bae1a512ec8a5568d58c5a525b0c839b0a"
    )


def k4_masks() -> dict[str, dict[int, int]]:
    return {
        "SIX_EDGES_WITH_CONTAINED_TRIPLE": {7: 1, 9: 1, 10: 1, 12: 1, 1: 4, 2: 4, 4: 4, 8: 3},
        "SIX_EDGES_WITHOUT_CONTAINED_TRIPLE": {
            **dict.fromkeys((3, 5, 6, 9, 10, 12), 1),
            **dict.fromkeys((1, 2, 4, 8), 3),
        },
        "FIVE_EDGES_WITHOUT_CONTAINED_TRIPLE": {
            **dict.fromkeys((3, 5, 6, 9, 10), 1),
            1: 3,
            2: 3,
            4: 4,
            8: 4,
        },
    }


def quartet_from_masks(masks: Mapping[int, int]) -> list[frozenset[int]]:
    tickets: list[set[int]] = [set(), set(), set(), set()]
    label = 1
    for mask, count in masks.items():
        for _ in range(count):
            for i in range(4):
                if mask >> i & 1:
                    tickets[i].add(label)
            label += 1
    assert all(len(t) == 6 for t in tickets)
    return [frozenset(t) for t in tickets]


def seven_set_outcomes(tickets: Sequence[frozenset[int]]) -> int:
    """Independent count: each outcome is a 7-label set with one special among 7."""

    union: list[int] = sorted(frozenset[int]().union(*tickets))
    total = 0
    for k in range(3, 8):
        for chosen in combinations(union, k):
            if all(len(t.intersection(chosen)) >= 3 for t in tickets):
                total += comb(49 - len(union), 7 - k)
    return 7 * total


def test_k4_quartet_weights_match_independent_counts() -> None:
    weights = x.k4_quartet_weights()
    expected = {
        "SIX_EDGES_WITH_CONTAINED_TRIPLE": 448,
        "SIX_EDGES_WITHOUT_CONTAINED_TRIPLE": 679,
        "FIVE_EDGES_WITHOUT_CONTAINED_TRIPLE": 112,
    }
    draws = all_main_draw_masks(49, 6)
    for name, masks in k4_masks().items():
        tickets = quartet_from_masks(masks)
        assert seven_set_outcomes(tickets) == x.quartet_outcomes(tickets) == expected[name]
        if name in weights:
            assert weights[name] == expected[name]
            union = {
                size: sum(
                    evaluate_portfolio(
                        [tuple(sorted(tickets[i])) for i in s], draws=draws
                    ).official_any_prize_outcome_count
                    for s in combinations(range(4), size)
                )
                for size in range(1, 5)
            }
            assert union[1] - union[2] + union[3] - union[4] == expected[name]
    assert min(weights.values()) == 448


def test_k4_lower_bound_holds_on_random_graphs() -> None:
    rng = random.Random(30)
    for _ in range(300):
        n = rng.randint(4, 20)
        p = rng.uniform(0.2, 1.0)
        edges = {e for e in combinations(range(n), 2) if rng.random() < p}
        degrees = [sum(v in e for e in edges) for v in range(n)]
        triangles = sum(
            all(e in edges for e in combinations(q, 2)) for q in combinations(range(n), 3)
        )
        k4 = sum(all(e in edges for e in combinations(q, 2)) for q in combinations(range(n), 4))
        open_wedges = sum(comb(d, 2) for d in degrees) - 3 * triangles
        assert 0 <= x.k4_lower_bound(degrees, open_wedges) <= k4
    assert x.k4_lower_bound([11] * 12, 0) == comb(12, 4)
    with pytest.raises(AssertionError, match="non-negative"):
        x.k4_lower_bound([3, 3], -1)


def test_sts13_witness_is_a_tight_soundness_tripwire() -> None:
    witness = x.witness_soundness()
    assert witness["STATUS"] == "PASS"
    assert witness["PROFILE_ID"] == x.profile_id(x.CHECKPOINT_OWNER)
    assert witness["EXACT_ANY_PRIZE_UNION"] == x.WITNESS_UNION == 313_263_867
    assert witness["BELOW_INCUMBENT_BY"] == 21
    assert (witness["GRAPH_TRIANGLES"], witness["OPEN_WEDGES"]) == (270, 6)
    assert (witness["EXACT_K4"], witness["K4_FLOOR_AT_WITNESS_TRIANGLES"]) == (550, 544)
    assert (witness["EXACT_S4"], witness["S4_FLOOR_AT_WITNESS_TRIANGLES"]) == (331_240, 243_712)
    assert witness["ROUTE4_BOUND_AT_WITNESS_TRIANGLES"] == 313_449_032
    assert witness["BOUND_WITH_EXACT_S4"] == 313_399_016
    tickets = x.sts13_witness()
    assert sorted(n for t in tickets for n in t) == sorted(
        n for n in range(1, 50) for _ in range(sum(n in t for t in tickets))
    )
    assert {len(t) for t in tickets} == {6}


def segment1_view(result: Mapping[str, object]) -> dict[str, object]:
    """The first segment as a resume input, from itself or from a result extending it."""

    if "RESUME_CHECKPOINT" not in result:
        return dict(result)
    return {
        **result,
        "TASK_STATUS": x.STOPPED,
        "PROOF_ACTUAL_WALL_SECONDS": result["SEGMENT1_SEALED_WALL_SECONDS"],
    }


@pytest.fixture(scope="module")
def checkpoint() -> tuple[x.Chase, x.OldWork]:
    return x.checkpoint_chase(json.loads(RESULT.read_text()), monotonic() + 3600)


def test_checkpoint_replay_reproduces_first_segment(
    checkpoint: tuple[x.Chase, x.OldWork], initial: Initial
) -> None:
    chase, old = checkpoint
    family, owners = x.r28.family_state(chase)
    assert (family, owners) == (x.CHECKPOINT_BOUND, (x.CHECKPOINT_OWNER,))
    assert x.r29.ledger_digest(chase) == x.CHECKPOINT_LEDGER_SHA256
    assert len(chase.bounds) == x.CHECKPOINT_LEDGER_COUNT
    assert len(chase.attempts) == x.CHECKPOINT_ATTEMPTS and len(chase.steps) == x.CHECKPOINT_STEPS
    assert x.r28.competing_bound(chase, owners) == x.CHECKPOINT_NEXT_COMPETITOR
    assert chase.cursor == x.decode_profile("66666662222222222211")
    assert chase.cursor_bound == 313_577_032
    cap = x.exit_cap(chase.catalog[x.CHECKPOINT_OWNER])
    assert cap == x.WITNESS_TRIANGLES - 1
    assert chase.failed == {((x.CHECKPOINT_OWNER,), cap): "OPTIMAL"}
    assert len(chase.dispatched) == 1_001
    assert initial[2] < old and ((x.profile_id(x.CHECKPOINT_OWNER),), cap) in old
    with pytest.raises(AssertionError, match="rerun"):
        x.guard(chase, ((x.CHECKPOINT_OWNER,), cap), old)


def test_checkpoint_replay_rejects_tampered_first_segment() -> None:
    result = json.loads(RESULT.read_text())
    result["GROUP_ATTEMPTS"][x.CHECKPOINT_TRIGGER]["STATUS"] = "INFEASIBLE"
    with pytest.raises(AssertionError, match="first-segment"):
        x.checkpoint_chase(result, monotonic() + 3600)


def test_route4_certifies_the_checkpoint_blocker(checkpoint: tuple[x.Chase, x.OldWork]) -> None:
    chase = copy.deepcopy(checkpoint[0])
    row = x.motif_certify(chase, x.CHECKPOINT_OWNER, x.CHECKPOINT_TRIGGER)
    assert row is not None
    assert (row["K4_LOWER_BOUND_AT_CAP"], row["S4_LOWER_BOUND_AT_CAP"]) == (544, 243_712)
    assert chase.catalog[x.CHECKPOINT_OWNER].s4 == row["GLOBAL_S4_FLOOR"] == 112
    assert (row["TRIANGLE_CAP"], row["OPEN_WEDGES_AT_CAP"]) == (270, 6)
    assert row["ENVELOPE_MAXIMIZED_AT_TRIANGLES"] == 270
    assert row["NEW_BOUND"] == 313_449_032 > x.WITNESS_UNION
    assert x.r28.family_state(chase)[0] == x.CHECKPOINT_NEXT_COMPETITOR
    assert chase.catalog[x.CHECKPOINT_OWNER].relaxation == x.ROUTE_MOTIF
    assert x.motif_certify(chase, x.decode_profile("66666665332221111111"), 0) is not None
    with pytest.raises(AssertionError, match="owners"):
        x.motif_certify(chase, x.CHECKPOINT_OWNER, x.CHECKPOINT_TRIGGER)


def test_route4_witness_tripwire_and_motif_owner_guard(
    checkpoint: tuple[x.Chase, x.OldWork], monkeypatch: pytest.MonkeyPatch
) -> None:
    chase = copy.deepcopy(checkpoint[0])
    monkeypatch.setattr(x, "k4_quartet_weights", lambda: {"OFF_CAP": 10_000})
    assert x.motif_certify(chase, x.CHECKPOINT_OWNER, x.CHECKPOINT_TRIGGER) is None
    assert x.r28.family_state(chase)[0] == x.CHECKPOINT_BOUND
    monkeypatch.setattr(x, "k4_quartet_weights", lambda: {"OVER": 2_000})
    with pytest.raises(AssertionError, match="witness"):
        x.motif_certify(chase, x.CHECKPOINT_OWNER, x.CHECKPOINT_TRIGGER)
    monkeypatch.setattr(x, "k4_quartet_weights", lambda: {"UNIT": 1})
    row = x.motif_certify(chase, x.CHECKPOINT_OWNER, x.CHECKPOINT_TRIGGER)
    assert row is not None and row["NEW_BOUND"] == 313_587_986
    family, owners = x.r28.family_state(chase)
    assert (family, owners) == (313_587_986, (x.CHECKPOINT_OWNER,))
    cap = x.exit_cap(chase.catalog[x.CHECKPOINT_OWNER])
    with pytest.raises(AssertionError, match="motif"):
        x.guard(chase, ((x.CHECKPOINT_OWNER,), cap), frozenset())
    recorder = Recorder(chase, call_stop=0)
    assert x.run(chase, recorder, checkpoint[1], no_log()) == (x.STOPPED, (x.CHECKPOINT_OWNER,))


def exhausted(
    solves: Sequence[x.Solve], seconds: float, owners: Collection[x.DegreeProfile]
) -> list[dict[str, object]]:
    return [
        {"STATUS": "PROOF_BUDGET_EXHAUSTED", "PROFILE_IDS": list(map(x.profile_id, s[0]))}
        for s in solves
    ]


def test_resume_budget_end_is_success_c() -> None:
    segment1 = segment1_view(json.loads(RESULT.read_text()))
    result = x.resume_result(segment1, exhausted)
    assert result["TASK_STATUS"] == x.SUCCESS_C
    assert result["FAMILY_UPPER_BOUND"] == x.CHECKPOINT_NEXT_COMPETITOR
    assert result["RESUME_FAMILY_DROP"] == x.CHECKPOINT_BOUND - x.CHECKPOINT_NEXT_COMPETITOR
    assert result["NEW_PROFILES_PROCESSED"] == 1 and result["NEXT_BLOCKER_OWNER_IDS"] == []
    attempts = x.rows(result["GROUP_ATTEMPTS"])
    assert len(attempts) == x.CHECKPOINT_ATTEMPTS + 64
    assert result["ROUTE4_STATUS"] == "OWNER_SWITCH"
    assert result["SEGMENT1_SEALED_WALL_SECONDS"] == x.SEGMENT1_WALL_SECONDS
    assert (result["PRIOR_SEGMENT_WALL_TIME"], result["SEGMENT2_CAP_SECONDS"]) == (
        2113.444,
        1486.556,
    )
    assert result["RESUME_SEGMENT_BUDGET"] == 1486.556 - x.FINALIZE_RESERVE_SECONDS
    assert result["TOTAL_BUDGET_CHECK"] == "PASS"
    capability = x.object_row(result["METHOD_CAPABILITY"])
    assert capability["SUCCESS_A_REACHABLE_BY_ROUTES_1_TO_4"] is False
    assert x.object_row(result["RESUME_CHECKPOINT"])["SOLVES_DURING_REPLAY"] == 0
    chase = x.replay_result(result, monotonic() + 3600)
    assert x.r28.family_state(chase)[0] == x.CHECKPOINT_NEXT_COMPETITOR


def test_small_route4_tightening_that_keeps_the_owner_is_not_success_b(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(x, "k4_quartet_weights", lambda: {"UNIT": 1})
    segment1 = segment1_view(json.loads(RESULT.read_text()))
    result = x.resume_result(segment1, exhausted)
    assert result["TASK_STATUS"] == x.STOPPED
    assert result["ROUTE4_STATUS"] == "TIGHTENED_OWNER_UNCHANGED"
    assert result["FINAL_OWNER_SWITCHED_FROM_CHECKPOINT"] is False
    assert result["FAMILY_UPPER_BOUND"] == 313_587_986 > x.CHECKPOINT_NEXT_COMPETITOR
    assert result["FINAL_BOUND_OWNER_IDS"] == [x.profile_id(x.CHECKPOINT_OWNER)]
    assert result["UNTIGHTENED_OWNER_IDS"] == [x.profile_id(x.CHECKPOINT_OWNER)]
    assert result["NEXT_BLOCKER_OWNER_IDS"] == []
    assert len(x.rows(result["GROUP_ATTEMPTS"])) == x.CHECKPOINT_ATTEMPTS


def feasible(
    solves: Sequence[x.Solve], seconds: float, owners: Collection[x.DegreeProfile]
) -> list[dict[str, object]]:
    return [proof(profiles, cap, "FEASIBLE") for profiles, cap in solves]


def test_stall_at_a_new_owner_after_the_switch_is_success_b(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exact = x.motif_s4_floor

    def blocker_only(profile: x.DegreeProfile, triangles: int) -> tuple[int, int]:
        return exact(profile, triangles) if profile == x.CHECKPOINT_OWNER else (0, 0)

    monkeypatch.setattr(x, "motif_s4_floor", blocker_only)
    segment1 = segment1_view(json.loads(RESULT.read_text()))
    result = x.resume_result(segment1, feasible)
    assert result["TASK_STATUS"] == x.SUCCESS_B and result["ROUTE4_STATUS"] == "OWNER_SWITCH"
    assert result["FINAL_OWNER_SWITCHED_FROM_CHECKPOINT"] is True
    assert result["FAMILY_UPPER_BOUND"] == x.CHECKPOINT_NEXT_COMPETITOR
    blockers = x.rows(result["NEXT_BLOCKER_OWNER_IDS"])
    assert len(blockers) == x.BATCH_LIMIT
    assert x.profile_id(x.CHECKPOINT_OWNER) not in blockers
    assert set(map(str, blockers)) <= set(map(str, x.rows(result["FINAL_BOUND_OWNER_IDS"])))


def test_resume_without_route4_drop_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(x, "motif_s4_floor", no_motif)
    segment1 = segment1_view(json.loads(RESULT.read_text()))
    result = x.resume_result(segment1, exhausted)
    assert result["TASK_STATUS"] == x.STOPPED and result["ROUTE4_STATUS"] == "NOT_CERTIFIED"
    assert result["FAMILY_UPPER_BOUND"] == x.CHECKPOINT_BOUND


def test_segment1_authority_requires_untouched_durable_state(tmp_path: Path) -> None:
    with pytest.raises(AssertionError, match="durable state changed"):
        x.segment1_authority(tmp_path)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_same_run_resume_preserves_the_in_place_first_segment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    attempts = [{"ATTEMPT_INDEX": 0, "STATUS": "INFEASIBLE", "PROFILE_IDS": ["X"]}]
    target = tmp_path / "result.json"
    durable = tmp_path / "durable"
    durable.mkdir()
    result = json.dumps({"TASK_STATUS": x.STOPPED, "GROUP_ATTEMPTS": attempts}).encode()
    target.write_bytes(result)
    (durable / x.CHECKPOINT).write_bytes(b"{}\n")
    (durable / x.PROOF_LOG).write_bytes(json.dumps(attempts[0]).encode() + b"\n")
    monkeypatch.setattr(x, "SEGMENT1_SHA256", sha(result))
    monkeypatch.setattr(x, "SEGMENT1_CHECKPOINT_SHA256", sha(b"{}\n"))
    monkeypatch.setattr(x, "SEGMENT1_LOG_SHA256", sha((durable / x.PROOF_LOG).read_bytes()))
    x.preserve_segment1(target, durable)
    x.preserve_segment1(target, durable)
    assert (durable / x.SEGMENT1_RESULT).read_bytes() == result == target.read_bytes()
    assert x.segment1_authority(durable)["GROUP_ATTEMPTS"] == attempts
    target.write_bytes(b"{}")
    x.preserve_segment1(target, durable)
    (durable / x.SEGMENT1_RESULT).write_bytes(b"{}")
    with pytest.raises(AssertionError, match="durable state changed"):
        x.preserve_segment1(target, durable)


def test_served_resume_keeps_timeout_and_retry_attempt_identities(
    chase: x.Chase, initial: Initial, tmp_path: Path
) -> None:
    resumed = copy.deepcopy(chase)
    x.certify_plateau(chase)
    owner = x.r28.family_state(chase)[1][0]
    first = Recorder(chase, {owner: ["EXTERNAL_TIMEOUT", "INFEASIBLE"]}, call_stop=2)
    with pytest.raises(Stop):
        x.run(chase, first, initial[2], x.DurableLog(tmp_path, {}))
    statuses = [a["STATUS"] for a in chase.attempts if a["PROFILE_IDS"] == [x.profile_id(owner)]]
    assert (
        statuses == ["EXTERNAL_TIMEOUT", "INFEASIBLE"] and len(chase.attempts) == x.BATCH_LIMIT + 1
    )
    x.certify_plateau(resumed)
    log = x.DurableLog(tmp_path, x.load_replayed(tmp_path / x.PROOF_LOG))
    second = Recorder(resumed, call_stop=0)
    with pytest.raises(Stop):
        x.run(resumed, second, initial[2], log)
    assert log.served == x.BATCH_LIMIT + 1 and not second.calls
    strip = {"REPLAYED_FROM_DURABLE_LOG"}
    assert [{k: v for k, v in a.items() if k not in strip} for a in resumed.attempts] == (
        chase.attempts
    )
    assert resumed.bounds == chase.bounds and resumed.steps == chase.steps
    (timeout,) = [a for a in chase.attempts if a["STATUS"] == "EXTERNAL_TIMEOUT"]
    cap = x.integer(timeout["TARGET_TRIANGLE_CAP"])
    swapped = x.load_replayed(tmp_path / x.PROOF_LOG)
    swapped[(x.profile_id(owner), cap)].reverse()
    with pytest.raises(AssertionError, match="identity shifted"):
        x.DurableLog(None, swapped).serve(((owner,), cap), x.integer(timeout["ATTEMPT_INDEX"]))
