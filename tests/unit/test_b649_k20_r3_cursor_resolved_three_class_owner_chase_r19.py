"""Owner-resolved cursor, three-class ownership, and guarded R19 proof replay."""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from itertools import pairwise
from typing import Any, NoReturn, cast

import pytest

from lottolab.research import b649_k20_r3_cursor_resolved_three_class_owner_chase_r19 as r19

STALE_LEVEL_VECTOR_ID = "tail-vector:L8525433:0x14,4x1,10x1,25x2"


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(r19.RESULT_PATH.read_text(encoding="utf-8")))


def _forbidden(*_: object, **__: object) -> NoReturn:
    pytest.fail("a forbidden proof dependency was dispatched")


def _chase(*, tail: int = 101, vector: int = 99) -> r19.Chase:
    return r19.Chase(
        states=(("state:a", 100), ("state:b", 98)),
        baseline=1_000,
        next_loss=1_000 - tail,
        classified_maximum=("tail-vector:fixture", vector),
        classified_terms={"tail-vector:fixture": vector},
        start_bound=max(tail, vector, 100),
        r4_reference=0,
        drop_target=50,
    )


def test_canonical_primitives_and_tail_recomputed_from_authoritative_cursor() -> None:
    assert r19.canonical_primitives() == {
        "SINGLE_TICKET_ANY_PRIZE": 18_611_432,
        "PAIR_INTERSECTION_COST[6]": 18_611_432,
        "K20_S1": 372_228_640,
    }
    baseline = r19.canonical_primitives()["K20_S1"] - r19.r13.FIXED_CERTIFIED_LOSS
    assert baseline == r19.canonical_baseline() == 365_048_628
    assert baseline - 8_528_849 == r19.START_UNCLASSIFIED_TAIL_BOUND == 356_519_779
    assert baseline - 8_525_433 == r19.STALE_TAIL_BOUND == 356_523_195
    assert baseline - 356_505_100 == r19.STATE_CROSSOVER_LOSS == 8_543_528
    chase = r19.initial_chase()
    assert chase.bound == 356_519_873
    assert chase.next_loss == 8_528_849
    assert chase.tail_bound == 356_519_779 != r19.STALE_TAIL_BOUND
    assert chase.state_max == 356_505_100
    assert chase.owners == r19.START_OWNER_IDS
    assert chase.transition_limit == 10


def test_cursor_resolution_regression_rejects_superseded_cursor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolution = r19.resolve_cursor()
    assert resolution["cursor_authority_mode"] == "OWNER_RESOLVED_CONFLICT"
    assert resolution["superseded_packet_cursor"] == 8_525_433 == r19.r18.START_LOSS
    assert resolution["authoritative_next_unclassified_loss"] == 8_528_849
    assert resolution["r18_certified_level_range"] == [8_525_433, 8_528_422]
    assert resolution["recomputed_unclassified_tail_bound"] == 356_519_779
    assert resolution["rejected_stale_tail_bound"] == 356_523_195
    r19.require_authoritative_cursor(8_528_849, "levels must never be enumerated")
    with pytest.raises(AssertionError, match="superseded packet cursor 8525433"):
        r19.require_authoritative_cursor(8_525_433, "levels must never be enumerated")
    with pytest.raises(AssertionError, match="prior tail levels must never be enumerated"):
        r19.require_authoritative_cursor(8_528_848, "levels must never be enumerated")
    chase = r19.initial_chase()
    chase.next_loss = r19.SUPERSEDED_PACKET_CURSOR
    assert chase.owners == (r19.TAIL_ID,)
    monkeypatch.setattr(r19.r16, "iter_interval_vectors", _forbidden)
    with pytest.raises(AssertionError, match="superseded packet cursor"):
        r19.next_tail_level(chase)
    stale = r19.r17.counts_from_vector_id(STALE_LEVEL_VECTOR_ID)
    monkeypatch.setattr(r19.r13, "classify_vector", _forbidden)
    with pytest.raises(AssertionError, match="superseded packet cursor"):
        r19.classify_new_tail_vector(stale, r19.TAIL_BASE_CONSTANT, r19.START_STATE_MAX_BOUND)
    monkeypatch.setattr(r19, "AUTHORITATIVE_NEXT_UNCLASSIFIED_LOSS", 8_525_433)
    r19.resolve_cursor.cache_clear()
    try:
        with pytest.raises(AssertionError, match="certified level prefix"):
            r19.resolve_cursor()
    finally:
        monkeypatch.undo()
        r19.resolve_cursor.cache_clear()
    assert r19.resolve_cursor() == resolution


@pytest.mark.parametrize(
    ("tail", "vector", "owners"),
    [
        (101, 99, (r19.TAIL_ID,)),
        (99, 101, ("tail-vector:fixture",)),
        (99, 99, ("state:a",)),
        (100, 100, ("state:a", r19.TAIL_ID, "tail-vector:fixture")),
        (101, 101, (r19.TAIL_ID, "tail-vector:fixture")),
        (99, 100, ("state:a", "tail-vector:fixture")),
    ],
)
def test_three_class_owner_selection(tail: int, vector: int, owners: tuple[str, ...]) -> None:
    chase = _chase(tail=tail, vector=vector)
    assert chase.bound == max(tail, vector, 100)
    assert chase.owners == owners


def test_tied_owner_set_prefers_certificate_and_blocks_tail_descent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chase = _chase(tail=100, vector=100)
    assert r19.owner_classes(chase.owners) == [
        "classified-tail-vector",
        "state",
        "unclassified-tail",
    ]
    assert r19.select_owner(chase) == "state:a"
    monkeypatch.setattr(r19.r16, "iter_interval_vectors", _forbidden)
    with pytest.raises(AssertionError, match="at or below a competing owner"):
        r19.next_tail_level(chase)
    chase.states = (("state:a", 90), ("state:b", 80))
    assert r19.select_owner(chase) == "tail-vector:fixture"
    with pytest.raises(AssertionError, match="at or below a competing owner"):
        r19.next_tail_level(chase)


def test_owner_switching_across_all_three_classes_and_stop_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chase = _chase()
    monkeypatch.setattr(r19, "START_LOSS", 899)
    counts = tuple([0] * len(r19.r5.anchor_incidence_profiles()))

    def interval(*_: object) -> Iterator[r19.CountVector]:
        return iter((counts,))

    def lookahead(_losses: Sequence[int], _tickets: int, lower: int) -> int:
        return lower + 1

    monkeypatch.setattr(r19.r16, "iter_interval_vectors", interval)
    monkeypatch.setattr(r19.r16, "next_attained_loss", lookahead)

    def classify(
        vector: r19.CountVector, _baseline: int, _threshold: int
    ) -> r19.r13.ClassifiedVector:
        return r19.r13.ClassifiedVector(
            vector_id=f"synthetic:{chase.next_loss}",
            counts=vector,
            local_loss=chase.next_loss,
            status=r19.r12.ELIMINATED,
            pair_union_penalty=None,
            forest_floor=None,
            r6_correction=None,
            four_ticket_status=None,
            four_ticket_penalty=None,
            correction=None,
            vector_bound=None,
            witness=None,
        )

    monkeypatch.setattr(r19, "classify_new_tail_vector", classify)
    r19.advance_tail(chase)
    assert chase.owners == ("state:a",)
    chase.improve_state("state:a", {"new_bound": 80})
    assert chase.owners == (r19.TAIL_ID, "tail-vector:fixture")

    def recover(*_: object) -> dict[str, Any]:
        return {"counts": r19.sparse(counts), "source_loss_level": 899}

    def certificate(_: r19.CountVector) -> dict[str, Any]:
        return {"correction_lower_bound": 21}

    monkeypatch.setattr(r19, "recover_classified_vector", recover)
    monkeypatch.setattr(r19.r14, "moment_certificate", certificate)
    r19.refine_classified_owner(chase, "tail-vector:fixture")
    assert chase.owners == (r19.TAIL_ID,)
    r19.advance_tail(chase)
    assert chase.owners == ("state:b",)
    assert [r19.owner_classes(tuple(row["to"])) for row in chase.events] == [
        ["state"],
        ["classified-tail-vector", "unclassified-tail"],
        ["unclassified-tail"],
        ["state"],
    ]
    assert chase.transitions == 4
    chase.transition_limit = 4
    assert chase.stop_condition() == r19.STOP_C
    monkeypatch.setattr(r19, "frozen_state_record", _forbidden)
    with pytest.raises(AssertionError, match="work after stop condition"):
        r19.refine_state_owner(chase, "state:b")


def test_non_owner_guards_run_before_proof_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    chase = r19.initial_chase()
    vector_id = "tail-vector:L6709346:0x6,1x5,4x6,17x1"
    assert vector_id not in chase.owners
    state_id = max(chase.states, key=lambda row: row[1])[0]
    monkeypatch.setattr(r19, "recover_classified_vector", _forbidden)
    monkeypatch.setattr(r19, "frozen_state_record", _forbidden)
    monkeypatch.setattr(r19.r12, "construct_support_witness", _forbidden)
    monkeypatch.setattr(r19.r14, "moment_certificate", _forbidden)
    monkeypatch.setattr(r19.r16, "iter_interval_vectors", _forbidden)
    with pytest.raises(AssertionError, match="non-owner work forbidden"):
        r19.refine_classified_owner(chase, vector_id)
    with pytest.raises(AssertionError, match="non-owner work forbidden"):
        r19.refine_state_owner(chase, state_id)
    with pytest.raises(AssertionError, match="non-owner work forbidden"):
        r19.next_tail_level(chase)


def test_no_prior_level_rerun_or_reclassification(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(r19.r13, "classify_vector", _forbidden)
    for counts in (
        r19.dense([[0, 6], [1, 4], [4, 7], [19, 1]]),
        r19.r17.counts_from_vector_id("tail-vector:L8528422:0x9,5x4,9x1,16x4"),
    ):
        with pytest.raises(AssertionError, match="prior tail vectors must never be reclassified"):
            r19.classify_new_tail_vector(counts, r19.TAIL_BASE_CONSTANT, r19.START_STATE_MAX_BOUND)
    chase = r19.initial_chase()
    chase.classified_terms = {key: 0 for key in chase.classified_terms}
    chase.sync_classified_maximum()
    chase.next_loss = r19.START_LOSS - 1
    assert chase.owners == (r19.TAIL_ID,)
    monkeypatch.setattr(r19.r16, "iter_interval_vectors", _forbidden)
    with pytest.raises(AssertionError, match="prior tail levels must never be enumerated"):
        r19.next_tail_level(chase)


def test_classified_owner_recovers_full_structure_without_old_level_census(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chase = r19.initial_chase()
    monkeypatch.setattr(r19.r16, "iter_interval_vectors", _forbidden)
    monkeypatch.setattr(r19.r6, "iter_type_count_vectors", _forbidden)
    monkeypatch.setattr(r19.r13, "classify_vector", _forbidden)
    record = r19.recover_classified_vector(chase, r19.START_OWNER_IDS[0])
    assert record["source_loss_level"] == 6_709_346
    assert record["counts"] == [[0, 6], [1, 2], [4, 9], [17, 1]]
    assert record["relaxation_producing_current_bound"] == "R6_PAIR_TRIPLE_AND_FOREST_ENVELOPE"
    assert record["prior_certificate"] is None
    assert sum(row["count"] for row in record["anchor_type_records"]) == 18
    assert r19.r8.validate_support_assignment(
        r19.dense(record["counts"]), record["support_witness"]
    )
    assert record["current_correction"] == record["r6_structural_record"]["combined_pair_penalty"]
    assert (
        r19.r14.joint_constant()
        - record["anchor_pair_s2"]
        + record["anchor_triple_s3"]
        - record["current_correction"]
        == record["current_bound"]
        == 356_519_873
    )
    r19.refine_classified_owner(chase, r19.START_OWNER_IDS[0])
    assert chase.owners == (r19.START_OWNER_IDS[1],)
    assert chase.bound == 356_519_873
    assert chase.transitions == 1
    r19.refine_classified_owner(chase, r19.START_OWNER_IDS[1])
    assert chase.owners == (r19.TAIL_ID,)
    assert chase.bound == 356_519_779
    assert chase.transitions == 2
    assert all(
        row["new_bound"] < row["active_competing_threshold"] for row in chase.classified_records
    )


def test_pinned_certificate_lookup_uses_r18_records_first() -> None:
    chase = r19.initial_chase()
    certified = "tail-vector:L6709346:0x6,1x4,4x7,19x1"
    source, route = r19.pinned_classified_record(chase, certified)
    assert route == r19.RATIONAL_MOMENT_ROUTE
    assert source is not None
    assert source["new_bound"] == chase.classified_terms[certified] == 353_239_922
    source, route = r19.pinned_classified_record(chase, STALE_LEVEL_VECTOR_ID)
    assert route == "R13_TAIL_CLASSIFICATION"
    assert source is not None
    assert source["vector_bound"] == chase.classified_terms[STALE_LEVEL_VECTOR_ID]
    source, route = r19.pinned_classified_record(chase, r19.START_OWNER_IDS[0])
    assert (source, route) == (None, "R6_PAIR_TRIPLE_AND_FOREST_ENVELOPE")


def test_exhausted_owner_stops_without_substituting_a_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def weak(_: r19.CountVector) -> dict[str, Any]:
        return {"correction_lower_bound": 0}

    monkeypatch.setattr(r19.r14, "moment_certificate", weak)
    monkeypatch.setattr(r19.r16, "iter_interval_vectors", _forbidden)
    chase, stop, _ = r19.run_chase()
    assert stop == r19.STOP_EXHAUSTED
    assert chase.exhausted_owner == r19.START_OWNER_IDS[0]
    assert chase.transitions == 0
    assert chase.bound == r19.START_R3_BOUND


def test_compressed_state_member_covers_every_represented_vector_then_reselects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inherited = r19.frozen_state_record("state:s2-12692531-s3-681744")
    stored = next(
        row
        for row in inherited["region_moment_certificates"]
        if row["represented_vector_count"] > 1
    )
    counts = r19.dense(stored["witness_counts"])
    make_state_api = "_make_state"
    make_state = getattr(r19.r7, make_state_api)
    profiles = r19.r5.anchor_incidence_profiles()
    member = cast(
        r19.r7.ResidualJointState,
        make_state(counts, profiles, r19.r6.local_losses(profiles)),
    )
    raw = r19.r14.raw_bound(member)
    owner_id = "state:compressed-fixture"
    frozen = {
        "region_sha256": r19.digest(((counts, raw),)),
        "complete_region_members": [
            {
                "witness_counts": r19.sparse(counts),
                "represented_vector_count": 2,
                "raw_bound": raw,
                "final_bound": raw,
            }
        ],
    }

    def frozen_record(_: str) -> dict[str, Any]:
        return frozen

    monkeypatch.setattr(r19, "frozen_state_record", frozen_record)
    monkeypatch.setattr(r19.r7, "joint_residual_census", _forbidden)
    monkeypatch.setattr(r19.r6, "iter_type_count_vectors", _forbidden)
    calls: list[r19.CountVector] = []

    def certificate(vector: r19.CountVector) -> dict[str, Any]:
        calls.append(vector)
        return {
            "counts": r19.sparse(vector),
            "correction_lower_bound": member.applied_residual_union_penalty
            + (50 if vector == counts else 100),
        }

    monkeypatch.setattr(r19.r14, "moment_certificate", certificate)
    chase = r19.Chase(
        states=((owner_id, raw), ("state:next", raw - 25)),
        baseline=r19.TAIL_BASE_CONSTANT,
        next_loss=r19.TAIL_BASE_CONSTANT - raw + 200,
        classified_maximum=("tail-vector:fixture", raw - 300),
        classified_terms={"tail-vector:fixture": raw - 300},
        start_bound=raw,
        r4_reference=0,
    )
    r19.refine_state_owner(chase, owner_id)
    assert calls == [r19.dense(row["counts"]) for row in stored["vector_certificates"]]
    assert dict(chase.states)[owner_id] == raw - 50
    assert chase.owners == ("state:next",)
    assert chase.transitions == 1
    assert chase.state_records[0]["represented_vector_count"] == 2
    assert len(chase.state_records[0]["support_witnesses"]) == 2
    with pytest.raises(AssertionError, match="non-owner work forbidden"):
        r19.refine_state_owner(chase, owner_id)
    assert len(calls) == 2


def test_wall_budget_and_upstream_drift_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    for invalid in (0, -1, 3_601):
        with pytest.raises(ValueError, match="at most 3600"):
            r19.run_chase(wall_budget=invalid)
    monkeypatch.setattr(r19, "UPSTREAM_SHA256", {next(iter(r19.UPSTREAM_SHA256)): "0" * 64})
    with pytest.raises(AssertionError, match="R18 authority fingerprint mismatch"):
        r19.verify_upstream_fingerprints()


def test_guarded_replay_matches_all_certificates_and_exact_next_owner(
    result: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    classified_losses: list[int] = []
    owner_ids: list[str] = []
    intervals: list[tuple[int, int]] = []
    original_interval = r19.r16.iter_interval_vectors
    original_classify = r19.classify_new_tail_vector
    original_refine = r19.refine_classified_owner

    def interval(losses: Sequence[int], tickets: int, lower: int, upper: int) -> Any:
        assert r19.START_LOSS <= lower == upper
        assert lower != r19.SUPERSEDED_PACKET_CURSOR
        intervals.append((lower, upper))
        return original_interval(losses, tickets, lower, upper)

    def classify(
        counts: r19.CountVector, baseline: int, threshold: int
    ) -> r19.r13.ClassifiedVector:
        loss = r19.r12.local_loss(counts, r19.r6.local_losses(r19.r5.anchor_incidence_profiles()))
        assert loss >= r19.START_LOSS
        classified_losses.append(loss)
        return original_classify(counts, baseline, threshold)

    def refine(chase: r19.Chase, identifier: str) -> None:
        assert identifier in chase.owners
        assert r19.owner_class(identifier) == "classified-tail-vector"
        assert chase.transitions < 10
        owner_ids.append(identifier)
        original_refine(chase, identifier)

    for module in (r19.r17, r19.r16):
        monkeypatch.setattr(module, "verify_prior_level_fingerprints", _forbidden)
    monkeypatch.setattr(r19.r15, "tail_census", _forbidden)
    monkeypatch.setattr(r19.r7, "joint_residual_census", _forbidden)
    monkeypatch.setattr(r19.r6, "iter_type_count_vectors", _forbidden)
    monkeypatch.setattr(r19, "refine_state_owner", _forbidden)
    monkeypatch.setattr(r19.r16, "iter_interval_vectors", interval)
    monkeypatch.setattr(r19, "classify_new_tail_vector", classify)
    monkeypatch.setattr(r19, "refine_classified_owner", refine)
    replay = json.loads(json.dumps(r19.build_result()))
    assert len(intervals) == result["TAIL_LEVELS_PROCESSED"] == 6
    assert intervals[0] == (8_528_849, 8_528_849)
    assert len(classified_losses) == result["TAIL_VECTORS_PROCESSED"] == 66
    assert owner_ids == [row["owner_id"] for row in result["CLASSIFIED_OWNER_CERTIFICATES"]]
    assert len(owner_ids) == result["CLASSIFIED_VECTOR_OWNERS_PROCESSED"] == 8
    for key in (
        "R3_BOUND",
        "R3_DROP",
        "CURSOR_RESOLUTION",
        "CURRENT_STATE_TERMS",
        "CURRENT_CLASSIFIED_TERMS",
        "OWNER_TRANSITIONS",
        "OWNER_ACTION_TRAJECTORY",
        "OWNER_CLASS_SEQUENCE",
        "STATE_OWNER_CERTIFICATES",
        "CLASSIFIED_OWNER_CERTIFICATES",
        "TAIL_LEVEL_CERTIFICATES",
        "NEW_TAIL_VECTOR_STRUCTURAL_RECORDS",
        "FINAL_OWNER_IDS",
        "NEXT_UNCLASSIFIED_LOSS",
        "STOP_CONDITION",
    ):
        assert replay[key] == result[key]
    assert result["TASK_STATUS"] == "SUCCESS_C"
    assert result["SUCCESS_C"] is True
    assert result["SUCCESS_A"] is result["SUCCESS_B"] is False
    assert result["OWNER_TRANSITION_COUNT"] == 10
    assert result["R3_BOUND"] == 356_518_792
    assert result["R3_DROP"] == 1_081
    assert result["NEXT_UNCLASSIFIED_LOSS"] == 8_529_836
    assert result["FINAL_OWNER_IDS"] == [r19.TAIL_ID]
    assert result["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"] < result["STATE_MAX_BOUND"] == 356_505_100
    assert replay["CURRENT_STATE_TERMS"] == r19.authority()["CURRENT_STATE_TERMS"]
    assert result["STATE_OWNERS_PROCESSED"] == 0
    assert result["EXHAUSTED_OWNER_ID"] is None
    for event in replay["OWNER_ACTION_TRAJECTORY"]:
        assert event["r3_bound"] == max(
            event["state_max_bound"],
            event["unclassified_tail_bound"],
            event["max_classified_tail_vector_bound"],
        )
    trajectory = replay["OWNER_ACTION_TRAJECTORY"]
    assert trajectory[0]["from"] == list(r19.START_OWNER_IDS)
    assert all(row["from"] == previous["to"] for previous, row in pairwise(trajectory))
    assert sum(row["from"] != row["to"] for row in trajectory) == 10
    for row in replay["TAIL_LEVEL_CERTIFICATES"]:
        assert r19.TAIL_BASE_CONSTANT - row["local_loss"] > row["active_competing_threshold"]
        assert row["local_loss"] >= r19.START_LOSS
        assert row["four_ticket_applied_count"] == 0
        assert row["unresolved_count"] == 0
