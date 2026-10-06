"""R20 crossover, maximizing-member dispatch, guarded replay, and exact handoff."""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from itertools import pairwise
from typing import Any, NoReturn, cast

import pytest

from lottolab.research import b649_k20_r3_tail_crossover_and_state_refinement_r20 as r20

NEXT_OWNER = "tail-vector:L6742484:0x6,1x11,6x1"
STATE_OWNER = "state:s2-12692531-s3-681744"


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(r20.RESULT_PATH.read_text(encoding="utf-8")))


def _forbidden(*_: object, **__: object) -> NoReturn:
    pytest.fail("a forbidden proof dependency was dispatched")


def test_canonical_primitives_initial_cursor_and_first_integer_crossover() -> None:
    assert r20.canonical_primitives() == {
        "SINGLE_TICKET_ANY_PRIZE": 18_611_432,
        "PAIR_INTERSECTION_COST[6]": 18_611_432,
        "K20_S1": 372_228_640,
    }
    baseline = 372_228_640 - r20.r13.FIXED_CERTIFIED_LOSS
    assert baseline == r20.canonical_baseline() == 365_048_628
    assert baseline - 8_529_836 == 356_518_792
    assert baseline - 356_505_100 == r20.STATE_CROSSOVER_LOSS == 8_543_528
    assert baseline - (8_543_528 - 1) == 356_505_101
    chase = r20.initial_chase()
    assert chase.next_loss == 8_529_836
    assert chase.bound == chase.tail_bound == 356_518_792
    assert chase.state_max == 356_505_100
    assert chase.classified_maximum == (NEXT_OWNER, 356_501_945)
    assert chase.owners == (r20.TAIL_ID,)
    assert chase.transition_limit == 0
    assert chase.stop_condition() is None


def test_frozen_state_and_prior_certificates_need_no_old_census(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(r20.r16, "iter_interval_vectors", _forbidden)
    monkeypatch.setattr(r20.r16, "next_attained_loss", _forbidden)
    monkeypatch.setattr(r20.r7, "joint_residual_census", _forbidden)
    monkeypatch.setattr(r20.r6, "iter_type_count_vectors", _forbidden)
    r20.prior_level_fingerprints.cache_clear()
    r20.state_owner_identification.cache_clear()
    prior = r20.prior_level_fingerprints()
    assert prior["r19_certified_levels"] == 6
    assert prior["r19_certified_level_range"] == [8_528_849, 8_529_766]
    assert prior["r19_certified_vectors"] == 66
    assert prior["r20_first_unclassified_loss"] == 8_529_836
    assert prior["prior_level_enumeration_calls"] == 0
    state = r20.state_owner_identification()
    assert state["tied_state_ids"] == [STATE_OWNER]
    assert state["state_max_bound"] == 356_505_100
    assert state["next_state_bound"] == 356_378_218
    assert state["region_compressed_member_count"] == 582
    assert state["region_members_at_state_max"] == 5
    assert state["region_members_at_or_above_start_classified_maximum"] == 25


def test_no_prior_tail_rerun_guard_precedes_enumeration_and_reclassification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    r20.require_unclassified_cursor(8_529_836, "levels must never be enumerated")
    with pytest.raises(AssertionError, match="prior tail levels must never be enumerated"):
        r20.require_unclassified_cursor(8_529_835, "levels must never be enumerated")
    chase = r20.initial_chase()
    chase.next_loss = 8_529_835
    monkeypatch.setattr(r20.r16, "iter_interval_vectors", _forbidden)
    monkeypatch.setattr(r20.r13, "classify_vector", _forbidden)
    with pytest.raises(AssertionError, match="prior tail levels must never be enumerated"):
        r20.next_tail_level(chase)
    for identifier in (
        "tail-vector:L8528422:0x9,5x4,9x1,16x4",
        NEXT_OWNER,
    ):
        counts = r20.r17.counts_from_vector_id(identifier)
        with pytest.raises(AssertionError, match="prior tail vectors must never be reclassified"):
            r20.classify_new_tail_vector(counts, 365_048_628, 356_505_100)


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_tail_dispatch_stops_at_state_crossover(
    offset: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    chase = r20.initial_chase()
    chase.next_loss = 8_543_528 + offset
    counts = r20.r17.counts_from_vector_id(NEXT_OWNER)
    intervals: list[tuple[int, int]] = []

    def interval(
        _losses: Sequence[int], _tickets: int, lower: int, upper: int
    ) -> Iterator[r20.CountVector]:
        intervals.append((lower, upper))
        return iter((counts,))

    def lookahead(_losses: Sequence[int], _tickets: int, lower: int) -> int:
        return lower

    monkeypatch.setattr(r20.r16, "iter_interval_vectors", interval)
    monkeypatch.setattr(r20.r16, "next_attained_loss", lookahead)
    if offset == -1:
        assert r20.select_owner(chase) == r20.TAIL_ID
        assert r20.next_tail_level(chase) == (8_543_527, (counts,), 8_543_528)
        assert intervals == [(8_543_527, 8_543_527)]
    else:
        assert r20.select_owner(chase) == STATE_OWNER
        message = "at or below a competing owner" if offset == 0 else "non-owner work forbidden"
        with pytest.raises(AssertionError, match=message):
            r20.next_tail_level(chase)
        assert intervals == []


def test_state_refinement_dispatches_only_maximizing_member_and_reselects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chase = r20.initial_chase()
    chase.next_loss = 8_543_528
    frozen = r20.frozen_state_record(STATE_OWNER)
    region = cast(list[dict[str, Any]], frozen["complete_region_members"])
    expected = min(
        r20.dense(row["witness_counts"]) for row in region if row["final_bound"] == 356_505_100
    )
    previous_states = dict(chase.states)
    monkeypatch.setattr(r20, "next_tail_level", _forbidden)
    monkeypatch.setattr(r20, "classify_new_tail_vector", _forbidden)
    monkeypatch.setattr(r20.r7, "joint_residual_census", _forbidden)
    monkeypatch.setattr(r20.r6, "iter_type_count_vectors", _forbidden)
    r20.refine_state_owner(chase, STATE_OWNER)
    assert chase.members_reconstructed == len(chase.state_records) == 1
    row = chase.state_records[0]
    assert row["witness_counts"] == r20.sparse(expected)
    assert row["member_prior_bound"] == 356_505_100
    assert row["member_new_bound"] < 356_505_100
    assert row["represented_vector_count"] == len(row["vector_certificates"])
    assert len(row["support_witnesses"]) == len(row["vector_certificates"])
    assert dict(chase.states) == previous_states
    assert chase.owners == (STATE_OWNER, r20.TAIL_ID)
    assert r20.select_owner(chase) == STATE_OWNER
    assert chase.stop_condition() is None
    r20.refine_state_owner(chase, STATE_OWNER)
    assert len(chase.state_records) == 2
    assert chase.state_records[1]["witness_counts"] != row["witness_counts"]
    assert chase.classified_records == []


def test_compressed_member_certifies_every_represented_vector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    region = cast(
        list[dict[str, Any]], r20.frozen_state_record(STATE_OWNER)["complete_region_members"]
    )
    stored = next(row for row in region if row["represented_vector_count"] > 1)
    counts = r20.dense(stored["witness_counts"])
    profiles = r20.r5.anchor_incidence_profiles()
    make_state_api = "_make_state"
    make_state = getattr(r20.r7, make_state_api)
    member = cast(
        r20.r7.ResidualJointState, make_state(counts, profiles, r20.r6.local_losses(profiles))
    )
    raw = r20.r14.raw_bound(member)
    owner_id = "state:compressed-fixture"
    frozen = {
        "region_sha256": r20.digest(((counts, raw),)),
        "complete_region_members": [{**stored, "raw_bound": raw, "final_bound": raw}],
    }

    def frozen_record(_: str) -> dict[str, Any]:
        return frozen

    monkeypatch.setattr(r20, "frozen_state_record", frozen_record)
    monkeypatch.setattr(r20.r7, "joint_residual_census", _forbidden)
    monkeypatch.setattr(r20.r6, "iter_type_count_vectors", _forbidden)
    calls: list[r20.CountVector] = []

    def certificate(vector: r20.CountVector) -> dict[str, Any]:
        calls.append(vector)
        return {
            "counts": r20.sparse(vector),
            "correction_lower_bound": member.applied_residual_union_penalty
            + (50 if vector == counts else 100),
        }

    monkeypatch.setattr(r20.r14, "moment_certificate", certificate)
    chase = r20.Chase(
        states=((owner_id, raw), ("state:next", raw - 25)),
        baseline=365_048_628,
        next_loss=365_048_628 - raw + 200,
        classified_maximum=("tail-vector:fixture", raw - 300),
        classified_terms={"tail-vector:fixture": raw - 300},
        start_bound=raw,
        r4_reference=0,
    )
    r20.refine_state_owner(chase, owner_id)
    assert len(set(calls)) == len(calls) == stored["represented_vector_count"] == 2
    assert counts in calls
    assert dict(chase.states)[owner_id] == raw - 50
    assert chase.owners == ("state:next",)
    assert r20.select_owner(chase) == "state:next"
    assert chase.state_records[0]["represented_vector_count"] == 2
    assert len(chase.state_records[0]["support_witnesses"]) == 2
    with pytest.raises(AssertionError, match="non-owner work forbidden"):
        r20.refine_state_owner(chase, owner_id)
    assert len(calls) == 2


def test_non_owner_guard_precedes_state_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    chase = r20.initial_chase()
    monkeypatch.setattr(r20, "frozen_state_record", _forbidden)
    monkeypatch.setattr(r20.r14, "moment_certificate", _forbidden)
    with pytest.raises(AssertionError, match="non-owner work forbidden"):
        r20.refine_state_owner(chase, STATE_OWNER)


def test_handoff_identifies_exact_next_owner_without_refinement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chase = r20.initial_chase()
    chase.next_loss = 365_048_628 - 356_501_945 + 1
    chase.states = tuple(
        (identifier, 356_501_944 if identifier == STATE_OWNER else bound)
        for identifier, bound in chase.states
    )
    chase.state_records.append(
        {
            "owner_id": STATE_OWNER,
            "compressed_member": False,
            "tightening_route": r20.RATIONAL_MOMENT_ROUTE,
        }
    )
    assert chase.owners == (NEXT_OWNER,)
    assert chase.stop_condition() == r20.STOP_C

    def finished(*, wall_budget: float) -> tuple[r20.Chase, str, float]:
        assert wall_budget == 3_600
        return chase, r20.STOP_C, 0.0

    monkeypatch.setattr(r20, "run_chase", finished)
    monkeypatch.setattr(r20, "advance_tail", _forbidden)
    monkeypatch.setattr(r20, "refine_state_owner", _forbidden)
    monkeypatch.setattr(r20.r19, "refine_classified_owner", _forbidden)
    handoff = r20.build_result()
    assert handoff["FINAL_OWNER_IDS"] == [NEXT_OWNER]
    assert handoff["NEXT_LOAD_BEARING_OWNER_ID"] == NEXT_OWNER
    assert handoff["FINAL_BOUND_OWNER_CLASS"] == "classified-tail-vector"
    assert handoff["TASK_STATUS"] == "SUCCESS_C"
    assert handoff["CLASSIFIED_VECTOR_OWNERS_PROCESSED"] == 0
    with pytest.raises(AssertionError, match="work after stop condition"):
        chase.require_dispatch(NEXT_OWNER)


@pytest.mark.parametrize("invalid", [0, -1, 3_601])
def test_wall_budget_rejects_unbounded_run(invalid: float) -> None:
    with pytest.raises(ValueError, match="at most 3600"):
        r20.run_chase(wall_budget=invalid)


def test_upstream_drift_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(r20, "UPSTREAM_SHA256", {next(iter(r20.UPSTREAM_SHA256)): "0" * 64})
    with pytest.raises(AssertionError, match="R19 authority fingerprint mismatch"):
        r20.verify_upstream_fingerprints()


def test_authoritative_result_matches_dry_run_and_stops_at_handoff(result: dict[str, Any]) -> None:
    assert result["TASK_STATUS"] == "SUCCESS_C"
    assert result["BASE_HEAD"] == "0f76a7c77013670d2bd35f334b245e6bf8d5cf6f"
    assert result["START_R3_BOUND"] == 356_518_792
    assert result["R3_BOUND"] == 356_501_945
    assert result["R3_DROP"] == 16_847
    assert result["TAIL_LEVELS_PROCESSED"] == 91
    assert result["STATE_MEMBERS_CERTIFIED"] == 25
    assert result["LOAD_BEARING_MEMBERS_RECONSTRUCTED"] == 25
    assert result["FINAL_BOUND_OWNER_CLASS"] == "classified-tail-vector"
    assert result["FINAL_OWNER_IDS"] == [NEXT_OWNER]
    assert result["NEXT_LOAD_BEARING_OWNER_ID"] == NEXT_OWNER
    assert result["PROCESSED_STATE_OWNER_IDS"] == [STATE_OWNER]
    assert result["HIGHER_ORDER_ESCALATION"] == (
        "NOT_REQUIRED_RATIONAL_MOMENT_CERTIFIED_EVERY_DISPATCHED_MEMBER"
    )
    assert result["EXHAUSTED_OWNER_ID"] is None
    assert result["CLASSIFIED_VECTOR_OWNERS_PROCESSED"] == 0
    assert result["SUCCESS_C"] is True
    assert result["SUCCESS_A"] is result["SUCCESS_B"] is result["STOP_D"] is False
    assert result["OWNER_TRANSITION_LIMIT"] is None
    assert result["CROSSOVER_DERIVATION"]["state_crossover_loss"] == 8_543_528
    assert result["CROSSOVER_DERIVATION"]["first_attained_cursor_at_or_past_crossover"] >= 8_543_528
    assert result["R3_BOUND"] == max(
        result["UNCLASSIFIED_TAIL_BOUND"],
        result["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"],
        result["STATE_MAX_BOUND"],
    )
    assert result["R4_REFERENCE_BOUND"] == 350_545_749
    assert result["INCUMBENT"] == 313_239_661
    assert result["REMAINING_GAP"] == 43_262_284
    assert result["CANONICAL_PRIMITIVES"] == r20.canonical_primitives()
    assert result["CANONICAL_PRIMITIVE_STATUS"] == "PASS"
    for key in (
        "PRIOR_TAIL_LEVELS_ENUMERATED",
        "PRIOR_VECTORS_RECLASSIFIED",
        "NON_OWNER_STATE_TERMS_CHANGED",
        "PRIOR_CLASSIFIED_TERMS_CHANGED",
        "GENERIC_FRONTIER_CENSUS_CALLS",
    ):
        assert result[key] == 0


def test_guarded_authoritative_replay_matches_every_certificate_and_owner(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    intervals: list[int] = []
    classified_losses: list[int] = []
    state_dispatches: list[str] = []
    original_interval = r20.r16.iter_interval_vectors
    original_classify = r20.classify_new_tail_vector
    original_refine = r20.refine_state_owner
    recovering_state_member = False

    def interval(
        losses: Sequence[int], tickets: int, lower: int, upper: int
    ) -> Iterator[r20.CountVector]:
        assert lower == upper
        if recovering_state_member:
            # This reconstructs the selected frozen state member, without tail classification.
            assert lower < 8_529_836
        else:
            assert lower >= 8_529_836
            intervals.append(lower)
        return original_interval(losses, tickets, lower, upper)

    def classify(
        counts: r20.CountVector, baseline: int, threshold: int
    ) -> r20.r13.ClassifiedVector:
        loss = r20.r12.local_loss(counts, r20.r6.local_losses(r20.r5.anchor_incidence_profiles()))
        assert loss >= 8_529_836
        classified_losses.append(loss)
        return original_classify(counts, baseline, threshold)

    def refine(chase: r20.Chase, identifier: str) -> None:
        nonlocal recovering_state_member
        assert identifier == r20.select_owner(chase) == STATE_OWNER
        assert chase.state_max >= chase.competitor(identifier)
        state_dispatches.append(identifier)
        recovering_state_member = True
        try:
            original_refine(chase, identifier)
        finally:
            recovering_state_member = False

    for module in (r20.r17, r20.r16):
        monkeypatch.setattr(module, "verify_prior_level_fingerprints", _forbidden)
    monkeypatch.setattr(r20.r15, "tail_census", _forbidden)
    monkeypatch.setattr(r20.r7, "joint_residual_census", _forbidden)
    monkeypatch.setattr(r20.r6, "iter_type_count_vectors", _forbidden)
    monkeypatch.setattr(r20.r19, "advance_tail", _forbidden)
    monkeypatch.setattr(r20.r19, "refine_classified_owner", _forbidden)
    monkeypatch.setattr(r20.r16, "iter_interval_vectors", interval)
    monkeypatch.setattr(r20, "classify_new_tail_vector", classify)
    monkeypatch.setattr(r20, "refine_state_owner", refine)
    replay = cast(dict[str, Any], json.loads(json.dumps(r20.build_result())))
    for key in result:
        if key != "PROOF_WALL_SECONDS":
            assert replay[key] == result[key], key
    assert intervals == [row["local_loss"] for row in result["TAIL_LEVEL_CERTIFICATES"]]
    assert len(intervals) == 91
    assert len(classified_losses) == result["TAIL_VECTORS_PROCESSED"]
    assert len(state_dispatches) == 25
    trajectory = replay["OWNER_ACTION_TRAJECTORY"]
    assert trajectory[0]["from"] == [r20.TAIL_ID]
    assert all(row["from"] == previous["to"] for previous, row in pairwise(trajectory))
    assert sum(row["from"] != row["to"] for row in trajectory) == result["OWNER_TRANSITION_COUNT"]
    for event in trajectory:
        assert event["r3_bound"] == max(
            event["state_max_bound"],
            event["unclassified_tail_bound"],
            event["max_classified_tail_vector_bound"],
        )
    for row in replay["TAIL_LEVEL_CERTIFICATES"]:
        assert 365_048_628 - row["local_loss"] > row["active_competing_threshold"]
        assert row["local_loss"] >= 8_529_836
        event = next(
            event for event in trajectory if event["action"] == f"tail:L{row['local_loss']}"
        )
        assert row["four_ticket_state_threshold"] == event["state_max_bound"]
        assert row["four_ticket_applied_count"] == row["unresolved_count"] == 0
    for row in replay["STATE_OWNER_CERTIFICATES"]:
        assert row["owner_id"] in row["owner_set_at_dispatch"]
        assert row["member_prior_bound"] >= row["active_competing_threshold"]
        assert row["member_new_bound"] < row["member_prior_bound"]
        assert row["no_other_state_terms_refined"] is True
        assert len(row["vector_certificates"]) == row["represented_vector_count"]
        assert len(row["support_witnesses"]) == row["represented_vector_count"]
