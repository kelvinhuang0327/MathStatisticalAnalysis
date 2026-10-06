"""Owner dispatch, the exact tail crossover, and owner-only envelope certificates."""

from __future__ import annotations

import json
from typing import Any, cast

import pytest

from lottolab.research import b649_k20_r3_tail_to_state_owner_chase_r15 as r15


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(r15.RESULT_PATH.read_text(encoding="utf-8")))


def _chase(*, drop_target: int = 50, transition_limit: int = 8) -> r15.Chase:
    return r15.Chase(
        states=(("state:a", 100), ("state:b", 98)),
        baseline=1_000,
        next_loss=899,
        classified_maximum=("classified-vector", 90),
        start_bound=101,
        r4_reference=0,
        drop_target=drop_target,
        transition_limit=transition_limit,
    )


def _eliminated(counts: r15.CountVector, loss: int) -> r15.r13.ClassifiedVector:
    return r15.r13.ClassifiedVector(
        vector_id=f"synthetic-vector:{loss}",
        counts=counts,
        local_loss=loss,
        status=r15.r12.ELIMINATED,
        pair_union_penalty=None,
        forest_floor=None,
        r6_correction=None,
        four_ticket_status=None,
        four_ticket_penalty=None,
        correction=None,
        vector_bound=None,
        witness=None,
    )


def _level(chase: r15.Chase, loss: int, next_loss: int) -> None:
    chase.advance_tail(loss, ((0,),), next_loss, lambda counts: _eliminated(counts, loss))


def test_canonical_primitives_crossover_derivation_and_start_owner() -> None:
    assert r15.canonical_primitives() == {
        "SINGLE_TICKET_ANY_PRIZE": 18_611_432,
        "PAIR_INTERSECTION_COST[6]": 18_611_432,
        "K20_S1": 372_228_640,
    }
    baseline = r15.canonical_baseline()
    assert baseline == 372_228_640 - 7_180_012 == 365_048_628
    assert r15.crossover_loss(356_636_210) == r15.START_CROSSOVER_LOSS == 8_412_418
    assert baseline - 8_412_418 == 356_636_210 < baseline - 8_412_417
    assert r15.crossover_loss(r15.START_R3_BOUND - r15.DROP_TARGET) == 8_449_642
    stored = r15.authority()
    chase = r15.Chase(
        states=r15.initial_state_terms(),
        baseline=baseline,
        next_loss=r15.START_LOSS,
        classified_maximum=(
            str(stored["MAX_CLASSIFIED_TAIL_VECTOR_ID"]),
            int(stored["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"]),
        ),
    )
    assert chase.owners == (r15.TAIL_ID,)
    assert chase.bound == r15.START_R3_BOUND
    assert chase.tail_bound - chase.state_max == 62_776
    assert chase.stop_condition() is None


def test_tail_state_transitions_switch_back_immediately() -> None:
    chase = _chase()
    assert chase.owners == (r15.TAIL_ID,)
    _level(chase, 899, 901)
    assert chase.owners == ("state:a",)
    assert chase.tail_bound == 99 < chase.state_max == 100
    with pytest.raises(AssertionError, match="non-owner work forbidden"):
        _level(chase, 901, 902)
    chase.improve_state("state:a", {"new_bound": 80})
    assert chase.owners == (r15.TAIL_ID,)
    _level(chase, 901, 903)
    assert chase.owners == ("state:b",)
    assert chase.transitions == 3
    assert [event["to"] for event in chase.events] == [
        ["state:a"],
        [r15.TAIL_ID],
        ["state:b"],
    ]


def test_tied_owner_selection_dispatches_state_and_blocks_tail_descent() -> None:
    chase = _chase()
    chase.next_loss = 900
    assert chase.owners == ("state:a", r15.TAIL_ID)
    with pytest.raises(AssertionError, match="tail descent below"):
        _level(chase, 900, 901)
    chase.states = (("state:a", 100), ("state:b", 100))
    chase.improve_state("state:a", {"new_bound": 80})
    assert chase.bound == 100
    assert chase.owners == ("state:b", r15.TAIL_ID)


def test_non_owner_state_is_rejected_before_any_certificate_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(_: str) -> None:
        raise RuntimeError("certificate recovery was called for a non-owner")

    monkeypatch.setattr(r15.r14, "owner_region", forbidden)
    chase = _chase()
    _level(chase, 899, 901)
    with pytest.raises(AssertionError, match="non-owner work forbidden"):
        r15.certify_state(chase, "state:b")
    with pytest.raises(AssertionError, match="non-owner work forbidden"):
        r15.certify_state(_chase(), "state:a")


def test_transition_budget_completes_the_handoff_then_stops() -> None:
    chase = _chase(transition_limit=2)
    _level(chase, 899, 901)
    assert chase.stop_condition() is None
    chase.improve_state("state:a", {"new_bound": 80})
    assert chase.stop_condition() == r15.STOP_C
    assert chase.owners == (r15.TAIL_ID,)
    with pytest.raises(AssertionError, match="stop condition"):
        _level(chase, 901, 903)


def test_success_b_and_classified_owner_stops() -> None:
    chase = _chase(drop_target=3)
    _level(chase, 899, 901)
    chase.improve_state("state:a", {"new_bound": 80})
    _level(chase, 901, 903)
    assert chase.bound == 98
    assert chase.stop_condition() == r15.STOP_B
    with pytest.raises(AssertionError, match="stop condition"):
        chase.improve_state("state:b", {"new_bound": 70})
    blocked = _chase()
    blocked.classified_maximum = ("classified-vector", 105)
    assert blocked.owners == ("classified-vector",)
    assert blocked.stop_condition() == r15.STOP_C_CLASSIFIED


def test_tail_rejects_an_invalid_support_witness(result: dict[str, Any]) -> None:
    record = result["STATE_OWNER_CERTIFICATES"][0]
    counts = r15.dense(record["support_witness_counts"])
    support = tuple(tuple(int(label) for label in row) for row in record["support_witness"])
    assert r15.r8.validate_support_assignment(counts, support)
    broken = (support[1], *support[1:])
    assert not r15.r8.validate_support_assignment(counts, broken)
    row = r15.r13.ClassifiedVector(
        vector_id="synthetic-realized",
        counts=counts,
        local_loss=899,
        status=r15.r12.WITNESS_REALIZED,
        pair_union_penalty=0,
        forest_floor=0,
        r6_correction=0,
        four_ticket_status=r15.r13.FOUR_TICKET_NOT_REQUIRED,
        four_ticket_penalty=None,
        correction=0,
        vector_bound=0,
        witness=broken,
    )
    with pytest.raises(AssertionError, match="support witness"):
        _chase().advance_tail(899, (counts,), 901, lambda _: row)


def test_state_envelope_carries_r14_and_certifies_compressed_members_vector_wise(
    result: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (record,) = cast(list[dict[str, Any]], result["STATE_OWNER_CERTIFICATES"])
    owner = str(record["owner_id"])
    assert owner == r15.START_STATE_OWNER_ID
    region = r15.r14.owner_region(owner)
    inherited = r15.r14_refined_members(owner, region)
    threshold = int(record["active_competing_threshold"])
    pending = tuple(
        row
        for row in region
        if r15.r14.raw_bound(row) >= threshold and row.witness_counts not in inherited
    )
    refined = cast(list[dict[str, Any]], record["region_moment_certificates"])
    assert len(inherited) == record["inherited_r14_refined_member_count"] == 75
    assert len(pending) == len(refined) == record["new_refined_member_count"]
    assert record["new_refined_compressed_member_count"] == 2
    vectors = r15.represented_vectors(pending)
    for state, row in zip(pending, refined, strict=True):
        members = vectors[state.witness_counts]
        assert len(members) == state.represented_vector_count == row["represented_vector_count"]
        certificates = [r15.r14.moment_certificate(vector) for vector in members]
        assert row["vector_certificates"] == certificates
        correction = max(
            state.applied_residual_union_penalty,
            min(int(certificate["correction_lower_bound"]) for certificate in certificates),
        )
        expected = (
            r15.r14.joint_constant() - state.anchor_pair_s2 + state.anchor_triple_s3 - correction
        )
        assert row["certified_bound"] == expected <= row["raw_bound"] == r15.r14.raw_bound(state)
    touched = {state.witness_counts for state in pending} | set(inherited)
    carried = [r15.r14.raw_bound(row) for row in region if row.witness_counts not in touched]
    assert max(carried) == record["carried_raw_maximum"] < threshold
    assert record["new_bound"] == max(
        max(carried), max(inherited.values()), max(int(row["certified_bound"]) for row in refined)
    )
    assert len(carried) + len(touched) == len(region) == record["region_compressed_state_count"]
    support = tuple(tuple(int(label) for label in row) for row in record["support_witness"])
    maximizer = r15.dense(record["support_witness_counts"])
    assert (
        r15.r14.raw_bound(next(row for row in region if row.witness_counts == maximizer))
        == (record["prior_bound"])
    )
    assert r15.r8.witness_costs(maximizer, support) == (
        record["witness_residual_s2"],
        record["witness_s4"],
    )

    # Owner certification computes exactly the new members' vector certificates.
    calls: list[r15.CountVector] = []
    original = r15.r14.moment_certificate

    def counted(counts: r15.CountVector) -> dict[str, Any]:
        calls.append(counts)
        return original(counts)

    monkeypatch.setattr(r15.r14, "moment_certificate", counted)
    chase = r15.Chase(
        states=r15.initial_state_terms(),
        baseline=r15.canonical_baseline(),
        next_loss=8_412_425,
        classified_maximum=("prior", r15.START_CLASSIFIED_MAXIMUM),
    )
    assert chase.owners == (owner,)
    replay, _ = r15.certify_state(chase, owner)
    assert len(calls) == record["new_refined_type_vector_count"] == 70
    assert replay["new_bound"] == record["new_bound"] == 356_117_720


def test_attained_tail_conservation_no_skipped_levels_and_exact_first_stop(
    result: dict[str, Any],
) -> None:
    levels = r15.tail_census(int(result["NEXT_UNCLASSIFIED_LOSS"]))
    records = cast(list[dict[str, Any]], result["TAIL_LEVEL_CERTIFICATES"])
    assert len(levels) == len(records) + 1
    assert levels[0][0] == r15.START_LOSS
    assert levels[-1][0] == result["NEXT_UNCLASSIFIED_LOSS"]
    baseline = r15.canonical_baseline()
    for index, record in enumerate(records):
        loss, counts = levels[index]
        assert record["local_loss"] == loss
        assert record["next_unclassified_loss"] == levels[index + 1][0]
        assert record["vector_count"] == len(counts)
        assert record["counts_sha256"] == r15.digest(counts)
        assert record["realizable_count"] + record["unrealizable_count"] == len(counts)
        assert record["unresolved_count"] == 0
        assert baseline - loss > record["active_state_threshold"]
    trajectory = cast(list[dict[str, Any]], result["OWNER_ACTION_TRAJECTORY"])
    target = r15.START_R3_BOUND - r15.DROP_TARGET
    assert all(event["r3_bound"] > target for event in trajectory[:-1])
    assert trajectory[-1]["r3_bound"] <= target
    crossing = next(event for event in trajectory if event["to"] != [r15.TAIL_ID])
    assert crossing["next_unclassified_loss"] >= r15.START_CROSSOVER_LOSS
    assert crossing["unclassified_tail_bound"] <= r15.START_STATE_MAX_BOUND
    assert crossing["to"] == [r15.START_STATE_OWNER_ID]
    previous = trajectory[trajectory.index(crossing) - 1]
    assert previous["next_unclassified_loss"] < r15.START_CROSSOVER_LOSS
    assert result["OWNER_TRANSITION_COUNT"] == 2
    assert result["STOP_CONDITION"] == r15.STOP_B
    assert result["R3_BOUND"] == 356_598_858
    assert result["R3_BOUND"] == max(
        result["STATE_MAX_BOUND"],
        result["UNCLASSIFIED_TAIL_BOUND"],
        result["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"],
    )
    final = {row["stable_id"]: row["bound"] for row in result["CURRENT_STATE_TERMS"]}
    processed = set(result["PROCESSED_STATE_OWNER_IDS"])
    assert processed == {r15.START_STATE_OWNER_ID}
    assert all(
        final[identifier] == bound
        for identifier, bound in r15.initial_state_terms()
        if identifier not in processed
    )


def test_r14_level_fingerprints_fail_closed_on_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    stored = json.loads(json.dumps(r15.authority()))
    stored["TAIL_LEVEL_CERTIFICATES"][0]["counts_sha256"] = "0" * 64
    monkeypatch.setattr(r15, "authority", lambda: stored)
    with pytest.raises(AssertionError, match="R14's classified levels changed"):
        r15.tail_census(r15.START_LOSS)


def test_full_replay_matches_the_authoritative_result(result: dict[str, Any]) -> None:
    replay = json.loads(json.dumps(r15.build_result()))
    for key in (
        "R3_BOUND",
        "R3_DROP",
        "CROSSOVER_DERIVATION",
        "CURRENT_STATE_TERMS",
        "OWNER_TRANSITIONS",
        "OWNER_ACTION_TRAJECTORY",
        "STATE_OWNER_CERTIFICATES",
        "TAIL_LEVEL_CERTIFICATES",
        "FINAL_OWNER_IDS",
        "NEXT_UNCLASSIFIED_LOSS",
        "STOP_CONDITION",
    ):
        assert replay[key] == result[key]
