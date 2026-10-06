"""Three-class ownership, certificate recovery, and guarded R18 proof replay."""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from itertools import pairwise
from typing import Any, NoReturn, cast

import pytest

from lottolab.research import b649_k20_r3_three_class_owner_chase_r18 as r18


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(r18.RESULT_PATH.read_text(encoding="utf-8")))


def _forbidden(*_: object, **__: object) -> NoReturn:
    pytest.fail("a forbidden proof dependency was dispatched")


def _chase(*, tail: int = 101, vector: int = 99) -> r18.Chase:
    return r18.Chase(
        states=(("state:a", 100), ("state:b", 98)),
        baseline=1_000,
        next_loss=1_000 - tail,
        classified_maximum=("tail-vector:fixture", vector),
        classified_terms={"tail-vector:fixture": vector},
        start_bound=max(tail, vector, 100),
        r4_reference=0,
        drop_target=50,
    )


def test_canonical_primitives_and_both_exact_crossovers() -> None:
    assert r18.canonical_primitives() == {
        "SINGLE_TICKET_ANY_PRIZE": 18_611_432,
        "PAIR_INTERSECTION_COST[6]": 18_611_432,
        "K20_S1": 372_228_640,
    }
    baseline = r18.canonical_primitives()["K20_S1"] - r18.r13.FIXED_CERTIFIED_LOSS
    assert baseline == r18.canonical_baseline() == 365_048_628
    assert baseline - 356_521_973 == r18.CLASSIFIED_CROSSOVER_LOSS == 8_526_655
    assert baseline - 356_505_100 == r18.STATE_CROSSOVER_LOSS == 8_543_528
    assert baseline - 8_526_654 == 356_521_974
    assert baseline - 8_543_527 == 356_505_101
    chase = r18.initial_chase()
    assert chase.bound == 356_523_195
    assert chase.next_loss == 8_525_433
    assert chase.owners == (r18.TAIL_ID,)
    assert chase.transition_limit == 10


@pytest.mark.parametrize(
    ("tail", "vector", "owners"),
    [
        (101, 99, (r18.TAIL_ID,)),
        (99, 101, ("tail-vector:fixture",)),
        (99, 99, ("state:a",)),
        (100, 100, ("state:a", r18.TAIL_ID, "tail-vector:fixture")),
        (101, 101, (r18.TAIL_ID, "tail-vector:fixture")),
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
    assert r18.owner_classes(chase.owners) == [
        "classified-tail-vector",
        "state",
        "unclassified-tail",
    ]
    assert r18.select_owner(chase) == "state:a"
    monkeypatch.setattr(r18.r16, "iter_interval_vectors", _forbidden)
    with pytest.raises(AssertionError, match="at or below a competing owner"):
        r18.next_tail_level(chase)
    chase.states = (("state:a", 90), ("state:b", 80))
    assert r18.select_owner(chase) == "tail-vector:fixture"
    with pytest.raises(AssertionError, match="at or below a competing owner"):
        r18.next_tail_level(chase)


def test_tail_state_vector_switches_and_stop_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    chase = _chase()
    monkeypatch.setattr(r18, "START_LOSS", 899)
    counts = tuple([0] * len(r18.r5.anchor_incidence_profiles()))

    def interval(*_: object) -> Iterator[r18.CountVector]:
        return iter((counts,))

    def lookahead(_losses: Sequence[int], _tickets: int, lower: int) -> int:
        return lower + 1

    monkeypatch.setattr(r18.r16, "iter_interval_vectors", interval)
    monkeypatch.setattr(r18.r16, "next_attained_loss", lookahead)

    def classify(
        vector: r18.CountVector, _baseline: int, _threshold: int
    ) -> r18.r13.ClassifiedVector:
        return r18.r13.ClassifiedVector(
            vector_id=f"synthetic:{chase.next_loss}",
            counts=vector,
            local_loss=chase.next_loss,
            status=r18.r12.ELIMINATED,
            pair_union_penalty=None,
            forest_floor=None,
            r6_correction=None,
            four_ticket_status=None,
            four_ticket_penalty=None,
            correction=None,
            vector_bound=None,
            witness=None,
        )

    monkeypatch.setattr(r18, "classify_new_tail_vector", classify)
    r18.advance_tail(chase)
    assert chase.owners == ("state:a",)
    chase.improve_state("state:a", {"new_bound": 80})
    assert chase.owners == (r18.TAIL_ID, "tail-vector:fixture")

    def recover(*_: object) -> dict[str, Any]:
        return {"counts": r18.sparse(counts), "source_loss_level": 899}

    def certificate(_: r18.CountVector) -> dict[str, Any]:
        return {"correction_lower_bound": 21}

    monkeypatch.setattr(r18, "recover_classified_vector", recover)
    monkeypatch.setattr(r18.r14, "moment_certificate", certificate)
    r18.refine_classified_owner(chase, "tail-vector:fixture")
    assert chase.owners == (r18.TAIL_ID,)
    r18.advance_tail(chase)
    assert chase.owners == ("state:b",)
    assert chase.transitions == 4
    chase.transition_limit = 4
    assert chase.stop_condition() == r18.STOP_C
    monkeypatch.setattr(r18, "frozen_state_record", _forbidden)
    with pytest.raises(AssertionError, match="work after stop condition"):
        r18.refine_state_owner(chase, "state:b")


def test_non_owner_guards_run_before_proof_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    chase = r18.initial_chase()
    vector_id = chase.classified_maximum[0]
    state_id = max(chase.states, key=lambda row: row[1])[0]
    monkeypatch.setattr(r18, "recover_classified_vector", _forbidden)
    monkeypatch.setattr(r18, "frozen_state_record", _forbidden)
    monkeypatch.setattr(r18.r12, "construct_support_witness", _forbidden)
    monkeypatch.setattr(r18.r14, "moment_certificate", _forbidden)
    with pytest.raises(AssertionError, match="non-owner work forbidden"):
        r18.refine_classified_owner(chase, vector_id)
    with pytest.raises(AssertionError, match="non-owner work forbidden"):
        r18.refine_state_owner(chase, state_id)
    other = _chase(tail=99, vector=99)
    monkeypatch.setattr(r18.r16, "iter_interval_vectors", _forbidden)
    with pytest.raises(AssertionError, match="non-owner work forbidden"):
        r18.next_tail_level(other)


def test_no_prior_level_rerun_or_reclassification(monkeypatch: pytest.MonkeyPatch) -> None:
    counts = r18.dense([[0, 6], [1, 4], [4, 7], [19, 1]])
    monkeypatch.setattr(r18.r13, "classify_vector", _forbidden)
    with pytest.raises(AssertionError, match="prior tail vectors must never be reclassified"):
        r18.classify_new_tail_vector(counts, r18.TAIL_BASE_CONSTANT, r18.START_STATE_MAX_BOUND)
    chase = r18.initial_chase()
    chase.next_loss = r18.START_LOSS - 1
    monkeypatch.setattr(r18.r16, "iter_interval_vectors", _forbidden)
    with pytest.raises(AssertionError, match="prior tail levels must never be enumerated"):
        r18.next_tail_level(chase)


def test_classified_owner_recovers_full_structure_without_old_level_census(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chase = r18.initial_chase()
    chase.next_loss = r18.CLASSIFIED_CROSSOVER_LOSS + 1
    expected_ids = (
        "tail-vector:L6709346:0x6,1x4,4x7,19x1",
        "tail-vector:L6709346:0x6,1x7,4x4,17x1",
    )
    assert chase.owners == expected_ids
    monkeypatch.setattr(r18.r16, "iter_interval_vectors", _forbidden)
    monkeypatch.setattr(r18.r6, "iter_type_count_vectors", _forbidden)
    monkeypatch.setattr(r18.r13, "classify_vector", _forbidden)
    record = r18.recover_classified_vector(chase, expected_ids[0])
    assert record["source_loss_level"] == 6_709_346
    assert record["counts"] == [[0, 6], [1, 4], [4, 7], [19, 1]]
    assert record["relaxation_producing_current_bound"] == "R6_PAIR_TRIPLE_AND_FOREST_ENVELOPE"
    assert sum(row["count"] for row in record["anchor_type_records"]) == 18
    assert r18.r8.validate_support_assignment(
        r18.dense(record["counts"]), record["support_witness"]
    )
    assert record["current_correction"] == record["r6_structural_record"]["combined_pair_penalty"]
    assert (
        r18.r14.joint_constant()
        - record["anchor_pair_s2"]
        + record["anchor_triple_s3"]
        - record["current_correction"]
        == record["current_bound"]
        == 356_521_973
    )
    r18.refine_classified_owner(chase, expected_ids[0])
    assert chase.owners == (expected_ids[1],)
    assert chase.bound == 356_521_973
    assert chase.transitions == 1
    r18.refine_classified_owner(chase, expected_ids[1])
    assert chase.owners == (r18.TAIL_ID,)
    assert chase.bound == 356_521_972
    assert chase.transitions == 2
    assert len(chase.classified_records) == 2


def test_compressed_state_member_covers_every_represented_vector_then_reselects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inherited = r18.frozen_state_record("state:s2-12692531-s3-681744")
    stored = next(
        row
        for row in inherited["region_moment_certificates"]
        if row["represented_vector_count"] > 1
    )
    counts = r18.dense(stored["witness_counts"])
    make_state_api = "_make_state"
    make_state = getattr(r18.r7, make_state_api)
    profiles = r18.r5.anchor_incidence_profiles()
    member = cast(
        r18.r7.ResidualJointState,
        make_state(counts, profiles, r18.r6.local_losses(profiles)),
    )
    raw = r18.r14.raw_bound(member)
    owner_id = "state:compressed-fixture"
    frozen = {
        "region_sha256": r18.digest(((counts, raw),)),
        "complete_region_members": [
            {
                "witness_counts": r18.sparse(counts),
                "represented_vector_count": 2,
                "raw_bound": raw,
                "final_bound": raw,
            }
        ],
    }

    def frozen_record(_: str) -> dict[str, Any]:
        return frozen

    monkeypatch.setattr(r18, "frozen_state_record", frozen_record)
    monkeypatch.setattr(r18.r7, "joint_residual_census", _forbidden)
    monkeypatch.setattr(r18.r6, "iter_type_count_vectors", _forbidden)
    calls: list[r18.CountVector] = []

    def certificate(vector: r18.CountVector) -> dict[str, Any]:
        calls.append(vector)
        return {
            "counts": r18.sparse(vector),
            "correction_lower_bound": member.applied_residual_union_penalty
            + (50 if vector == counts else 100),
        }

    monkeypatch.setattr(r18.r14, "moment_certificate", certificate)
    chase = r18.Chase(
        states=((owner_id, raw), ("state:next", raw - 25)),
        baseline=r18.TAIL_BASE_CONSTANT,
        next_loss=r18.TAIL_BASE_CONSTANT - raw + 200,
        classified_maximum=("tail-vector:fixture", raw - 300),
        classified_terms={"tail-vector:fixture": raw - 300},
        start_bound=raw,
        r4_reference=0,
    )
    r18.refine_state_owner(chase, owner_id)
    assert calls == [r18.dense(row["counts"]) for row in stored["vector_certificates"]]
    assert dict(chase.states)[owner_id] == raw - 50
    assert chase.owners == ("state:next",)
    assert chase.transitions == 1
    assert chase.state_records[0]["represented_vector_count"] == 2
    assert len(chase.state_records[0]["support_witnesses"]) == 2
    with pytest.raises(AssertionError, match="non-owner work forbidden"):
        r18.refine_state_owner(chase, owner_id)
    assert len(calls) == 2


def test_new_vector_structural_record_uses_dense_counts() -> None:
    chase = r18.initial_chase()
    owner_id = chase.classified_maximum[0]
    counts = r18.r17.counts_from_vector_id(owner_id)
    chase.next_loss = r18.CLASSIFIED_CROSSOVER_LOSS + 1
    chase.vector_records[owner_id] = {
        "vector_id": owner_id,
        "counts": list(counts),
        "vector_bound": chase.classified_terms[owner_id],
    }
    recovered = r18.recover_classified_vector(chase, owner_id)
    assert recovered["counts"] == r18.sparse(counts)
    assert recovered["prior_certificate"] == chase.vector_records[owner_id]


def test_wall_budget_and_upstream_drift_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    for invalid in (0, -1, 3_601):
        with pytest.raises(ValueError, match="at most 3600"):
            r18.run_chase(wall_budget=invalid)
    monkeypatch.setattr(r18, "UPSTREAM_SHA256", {next(iter(r18.UPSTREAM_SHA256)): "0" * 64})
    with pytest.raises(AssertionError, match="R17 authority fingerprint mismatch"):
        r18.verify_upstream_fingerprints()


def test_guarded_replay_matches_all_certificates_and_exact_next_owner(
    result: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    classified_losses: list[int] = []
    owner_ids: list[str] = []
    intervals: list[tuple[int, int]] = []
    original_interval = r18.r16.iter_interval_vectors
    original_classify = r18.classify_new_tail_vector
    original_refine = r18.refine_classified_owner

    def interval(losses: Sequence[int], tickets: int, lower: int, upper: int) -> Any:
        assert r18.START_LOSS <= lower == upper
        intervals.append((lower, upper))
        return original_interval(losses, tickets, lower, upper)

    def classify(
        counts: r18.CountVector, baseline: int, threshold: int
    ) -> r18.r13.ClassifiedVector:
        loss = r18.r12.local_loss(counts, r18.r6.local_losses(r18.r5.anchor_incidence_profiles()))
        assert loss >= r18.START_LOSS
        classified_losses.append(loss)
        return original_classify(counts, baseline, threshold)

    def refine(chase: r18.Chase, identifier: str) -> None:
        assert identifier in chase.owners
        assert r18.owner_class(identifier) == "classified-tail-vector"
        assert chase.transitions < 10
        owner_ids.append(identifier)
        original_refine(chase, identifier)

    for module in (r18.r17, r18.r16):
        monkeypatch.setattr(module, "verify_prior_level_fingerprints", _forbidden)
    monkeypatch.setattr(r18.r15, "tail_census", _forbidden)
    monkeypatch.setattr(r18.r7, "joint_residual_census", _forbidden)
    monkeypatch.setattr(r18.r6, "iter_type_count_vectors", _forbidden)
    monkeypatch.setattr(r18, "refine_state_owner", _forbidden)
    monkeypatch.setattr(r18.r16, "iter_interval_vectors", interval)
    monkeypatch.setattr(r18, "classify_new_tail_vector", classify)
    monkeypatch.setattr(r18, "refine_classified_owner", refine)
    replay = json.loads(json.dumps(r18.build_result()))
    assert len(intervals) == result["TAIL_LEVELS_PROCESSED"] == 14
    assert len(classified_losses) == result["TAIL_VECTORS_PROCESSED"] == 158
    assert owner_ids == [row["owner_id"] for row in result["CLASSIFIED_OWNER_CERTIFICATES"]]
    assert len(owner_ids) == result["CLASSIFIED_VECTOR_OWNERS_PROCESSED"] == 6
    for key in (
        "R3_BOUND",
        "R3_DROP",
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
    assert result["R3_BOUND"] == 356_519_873
    assert result["R3_DROP"] == 3_322
    assert result["NEXT_UNCLASSIFIED_LOSS"] == 8_528_849
    assert result["FINAL_OWNER_IDS"] == [
        "tail-vector:L6709346:0x6,1x2,4x9,17x1",
        "tail-vector:L6709346:0x6,1x9,4x2,19x1",
    ]
    assert replay["CURRENT_STATE_TERMS"] == r18.authority()["CURRENT_STATE_TERMS"]
    assert result["STATE_OWNERS_PROCESSED"] == 0
    for event in replay["OWNER_ACTION_TRAJECTORY"]:
        assert event["r3_bound"] == max(
            event["state_max_bound"],
            event["unclassified_tail_bound"],
            event["max_classified_tail_vector_bound"],
        )
    trajectory = replay["OWNER_ACTION_TRAJECTORY"]
    assert all(row["from"] == previous["to"] for previous, row in pairwise(trajectory))
    assert sum(row["from"] != row["to"] for row in trajectory) == 10
    for row in replay["TAIL_LEVEL_CERTIFICATES"]:
        assert r18.TAIL_BASE_CONSTANT - row["local_loss"] > row["active_competing_threshold"]
        assert row["four_ticket_applied_count"] == 0
        assert row["unresolved_count"] == 0
