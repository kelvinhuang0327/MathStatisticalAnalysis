"""Current-owner dispatch, exact loss cursors, and compressed-vector coverage."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import replace
from itertools import pairwise
from typing import Any, NoReturn, cast

import pytest

from lottolab.research import b649_k20_r3_tail_state_owner_chase_r17 as r17


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    if r17.RESULT_PATH.exists():
        return cast(dict[str, Any], json.loads(r17.RESULT_PATH.read_text(encoding="utf-8")))
    return r17.build_result()


def _forbidden(*_: object, **__: object) -> NoReturn:
    pytest.fail("a forbidden proof dependency was dispatched")


def _chase() -> r17.Chase:
    return r17.Chase(
        states=(("state:a", 100), ("state:b", 98)),
        baseline=1_000,
        next_loss=899,
        classified_maximum=("tail-vector:test", 90),
        classified_terms={"tail-vector:test": 90},
        start_bound=101,
        r4_reference=0,
        drop_target=50,
    )


def _level(chase: r17.Chase, loss: int, next_loss: int) -> None:
    row = r17.r13.ClassifiedVector(
        vector_id=f"synthetic:{loss}",
        counts=(0,),
        local_loss=loss,
        status=r17.r12.ELIMINATED,
        pair_union_penalty=None,
        forest_floor=None,
        r6_correction=None,
        four_ticket_status=None,
        four_ticket_penalty=None,
        correction=None,
        vector_bound=None,
        witness=None,
    )
    chase.advance_tail(loss, ((0,),), next_loss, lambda _: row)


def test_canonical_primitives_and_exact_first_crossover() -> None:
    assert r17.canonical_primitives() == {
        "SINGLE_TICKET_ANY_PRIZE": 18_611_432,
        "PAIR_INTERSECTION_COST[6]": 18_611_432,
        "K20_S1": 372_228_640,
    }
    assert r17.canonical_baseline() == 365_048_628
    assert 365_048_628 - 356_505_100 == 8_543_528 == r17.START_CROSSOVER_LOSS
    assert 365_048_628 - 8_543_527 == 356_505_101
    assert r17.initial_chase().owners == (r17.TAIL_ID,)
    assert r17.initial_chase().bound == 356_530_622
    assert r17.r13.identify_owner_set(r17.initial_state_terms()) == (r17.START_STATE_OWNER_ID,)
    assert r17.TAIL_BASE_CONSTANT - r17.START_CLASSIFIED_MAXIMUM == 8_521_460


def test_tail_state_switch_and_non_owner_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    chase = _chase()
    _level(chase, 899, 901)
    assert chase.owners == ("state:a",)
    monkeypatch.setattr(r17, "authority", _forbidden)
    with pytest.raises(AssertionError, match="non-owner work forbidden"):
        r17.refine_state_owner(chase, "state:b")
    with pytest.raises(AssertionError, match="non-owner work forbidden"):
        r17.next_tail_level(chase)
    chase.improve_state("state:a", {"new_bound": 80})
    assert chase.owners == (r17.TAIL_ID,)
    _level(chase, 901, 903)
    assert chase.owners == ("state:b",)
    assert chase.transitions == 3


def test_tied_tail_and_state_blocks_tail_enumeration(monkeypatch: pytest.MonkeyPatch) -> None:
    chase = _chase()
    chase.next_loss = 900
    assert chase.owners == ("state:a", r17.TAIL_ID)
    monkeypatch.setattr(r17.r16, "iter_interval_vectors", _forbidden)
    with pytest.raises(AssertionError, match="tail descent below"):
        r17.next_tail_level(chase)


def test_classified_owner_is_not_success_c_and_scope_is_explicit() -> None:
    chase = _chase()
    chase.classified_terms = {"tail-vector:a": 102, "tail-vector:b": 102}
    chase.sync_classified_maximum()
    assert chase.owners == ("tail-vector:a", "tail-vector:b")
    assert chase.transitions == 0
    assert chase.stop_condition() == r17.STOP_SCOPE != r17.STOP_C
    chase.refine_classified_owners = True
    assert chase.stop_condition() is None
    chase.events = [{"from": ["a"], "to": ["b"]} for _ in range(8)]
    assert chase.stop_condition() == r17.STOP_C
    with pytest.raises(AssertionError, match="stop condition"):
        chase.require_dispatch("tail-vector:a")


def test_prior_level_and_non_owner_classified_guards_before_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(r17.r13, "classify_vector", _forbidden)
    counts = r17.dense([[0, 6], [1, 11], [17, 1]])
    with pytest.raises(AssertionError, match="must never be reclassified"):
        r17.classify_new_tail_vector(counts, r17.TAIL_BASE_CONSTANT, r17.START_STATE_MAX_BOUND)
    chase = r17.initial_chase()
    chase.next_loss = r17.START_LOSS - 1
    monkeypatch.setattr(r17.r16, "iter_interval_vectors", _forbidden)
    with pytest.raises(AssertionError, match="must never be enumerated"):
        r17.next_tail_level(chase)
    monkeypatch.setattr(r17.r12, "construct_support_witness", _forbidden)
    with pytest.raises(AssertionError, match="non-owner work forbidden"):
        r17.refine_classified_owner(chase, next(iter(chase.classified_terms)))


def test_prior_fingerprints_never_dispatch_classification_or_support(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(r17.r12, "classify_vector", _forbidden)
    monkeypatch.setattr(r17.r13, "classify_vector", _forbidden)
    monkeypatch.setattr(r17.r12, "construct_support_witness", _forbidden)
    monkeypatch.setattr(r17.r14, "moment_certificate", _forbidden)
    r17.verify_prior_level_fingerprints.cache_clear()
    try:
        assert r17.verify_prior_level_fingerprints() == {
            "R15_LEVELS": 397,
            "R15_VECTORS": 4586,
            "R16_LEVELS": 311,
            "R16_VECTORS": 3411,
        }
    finally:
        r17.verify_prior_level_fingerprints.cache_clear()


def test_prior_r13_r16_classified_vector_certificate_guard_before_support_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chase = r17.initial_chase(refine_classified_owners=True)
    owner_id = "tail-vector:L8460256:0x3,4x13,5x1,9x1"
    chase.classified_terms = {owner_id: r17.START_R3_BOUND + 1}
    chase.sync_classified_maximum()
    monkeypatch.setattr(r17.r12, "construct_support_witness", _forbidden)
    monkeypatch.setattr(r17.r14, "moment_certificate", _forbidden)
    with pytest.raises(AssertionError, match="fingerprint validation only"):
        r17.refine_classified_owner(chase, owner_id)


def test_prior_fingerprint_drift_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    stored = json.loads(json.dumps(r17.authority()))
    stored["TAIL_LEVEL_CERTIFICATES"][0]["counts_sha256"] = "0" * 64
    monkeypatch.setattr(r17, "authority", lambda: stored)
    r17.verify_prior_level_fingerprints.cache_clear()
    try:
        with pytest.raises(AssertionError, match="level fingerprints changed"):
            r17.verify_prior_level_fingerprints()
    finally:
        r17.verify_prior_level_fingerprints.cache_clear()


def test_frozen_classified_vector_ids_recover_without_old_level_enumeration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(r17.r16, "iter_interval_vectors", _forbidden)
    monkeypatch.setattr(r17.r6, "iter_type_count_vectors", _forbidden)
    monkeypatch.setattr(r17.r13, "classify_vector", _forbidden)
    terms = cast(list[dict[str, Any]], r17.authority()["CURRENT_CLASSIFIED_TERMS"])
    recovered = 0
    for row in terms:
        owner_id = str(row["stable_id"])
        if owner_id.startswith("tail-vector:"):
            counts = r17.counts_from_vector_id(owner_id)
            assert sum(counts) == 18
            assert (
                r17.r13.vector_id(
                    counts,
                    r17.r12.local_loss(
                        counts, r17.r6.local_losses(r17.r5.anchor_incidence_profiles())
                    ),
                )
                == owner_id
            )
            recovered += 1
    assert recovered == 26
    with pytest.raises(ValueError, match="duplicate type"):
        r17.counts_from_vector_id("tail-vector:L6709346:0x6,1x2,1x9,19x1")


def test_compressed_member_recovery_matches_all_frozen_vectors_without_frontier_census(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = cast(list[dict[str, Any]], r17.authority()["STATE_OWNER_CERTIFICATES"])[0]
    rows = [
        row for row in record["region_moment_certificates"] if row["represented_vector_count"] > 1
    ]
    make_state_api = "_make_state"
    make_state = getattr(r17.r7, make_state_api)
    profiles = r17.r5.anchor_incidence_profiles()
    losses = r17.r6.local_losses(profiles)
    members = tuple(
        replace(
            cast(
                r17.r7.ResidualJointState,
                make_state(r17.dense(row["witness_counts"]), profiles, losses),
            ),
            represented_vector_count=int(row["represented_vector_count"]),
        )
        for row in rows
    )
    monkeypatch.setattr(r17.r7, "joint_residual_census", _forbidden)
    monkeypatch.setattr(r17.r6, "iter_type_count_vectors", _forbidden)
    recovered = r17.represented_vectors(members)
    assert len(members) == 2
    assert sum(len(vectors) for vectors in recovered.values()) == 4
    for member, row in zip(members, rows, strict=True):
        expected = tuple(r17.dense(cert["counts"]) for cert in row["vector_certificates"])
        assert recovered[member.witness_counts] == expected
    with pytest.raises(AssertionError, match="were not recovered"):
        r17.represented_vectors((replace(members[0], represented_vector_count=3),))


def test_tail_stream_has_only_current_level_and_integer_lookahead(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chase = r17.initial_chase()
    calls: list[tuple[int, int]] = []
    original = r17.r16.iter_interval_vectors

    def counted(losses: Sequence[int], tickets: int, lower: int, upper: int) -> Any:
        calls.append((lower, upper))
        return original(losses, tickets, lower, upper)

    monkeypatch.setattr(r17.r16, "iter_interval_vectors", counted)
    loss, vectors, lookahead = r17.next_tail_level(chase)
    assert loss == 8_518_006
    assert vectors
    assert lookahead > loss
    assert calls == [(loss, loss)]


def test_state_member_uses_weakest_represented_certificate_then_reselects_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = cast(list[dict[str, Any]], r17.authority()["STATE_OWNER_CERTIFICATES"])[0]
    stored = next(
        row for row in record["region_moment_certificates"] if row["represented_vector_count"] > 1
    )
    counts = r17.dense(stored["witness_counts"])
    make_state_api = "_make_state"
    make_state = getattr(r17.r7, make_state_api)
    profiles = r17.r5.anchor_incidence_profiles()
    member = cast(
        r17.r7.ResidualJointState, make_state(counts, profiles, r17.r6.local_losses(profiles))
    )
    raw = r17.r14.raw_bound(member)
    owner_id = "state:compressed-fixture"
    frozen_region = [
        {
            "witness_counts": r17.sparse(counts),
            "represented_vector_count": 2,
            "raw_bound": raw,
            "final_bound": raw,
        }
    ]
    frozen_authority = {
        "STATE_OWNER_CERTIFICATES": [
            {
                "owner_id": owner_id,
                "region_sha256": r17.digest(((counts, raw),)),
                "complete_region_members": frozen_region,
            }
        ]
    }
    monkeypatch.setattr(r17, "authority", lambda: frozen_authority)
    monkeypatch.setattr(r17.r7, "joint_residual_census", _forbidden)
    monkeypatch.setattr(r17.r6, "iter_type_count_vectors", _forbidden)
    calls: list[r17.CountVector] = []

    def certificate(vector: r17.CountVector) -> dict[str, Any]:
        calls.append(vector)
        extra = 50 if vector == counts else 100
        return {"correction_lower_bound": member.applied_residual_union_penalty + extra}

    monkeypatch.setattr(r17.r14, "moment_certificate", certificate)
    chase = r17.Chase(
        states=((owner_id, raw), ("state:next", raw - 25)),
        baseline=r17.TAIL_BASE_CONSTANT,
        next_loss=r17.TAIL_BASE_CONSTANT - raw + 200,
        classified_maximum=("carried-classified", raw - 300),
        classified_terms={"carried-classified": raw - 300},
        start_bound=raw,
        r4_reference=0,
    )
    r17.refine_state_owner(chase, owner_id)
    assert calls == [r17.dense(row["counts"]) for row in stored["vector_certificates"]]
    assert dict(chase.states)[owner_id] == raw - 50
    assert chase.owners == ("state:next",)
    assert chase.transitions == 1
    assert chase.state_records[0]["represented_vector_count"] == 2
    with pytest.raises(AssertionError, match="non-owner work forbidden"):
        r17.refine_state_owner(chase, owner_id)
    assert len(calls) == 2


def test_guarded_owner_replay_matches_certificate_and_stops_at_exact_next_owner(
    result: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    classified_losses: list[int] = []
    classified_owners: list[str] = []
    original = r17.classify_new_tail_vector
    original_refine = r17.refine_classified_owner

    def guarded(counts: r17.CountVector, baseline: int, threshold: int) -> r17.r13.ClassifiedVector:
        loss = r17.r12.local_loss(counts, r17.r6.local_losses(r17.r5.anchor_incidence_profiles()))
        assert loss >= r17.START_LOSS
        classified_losses.append(loss)
        return original(counts, baseline, threshold)

    def guarded_refine(chase: r17.Chase, owner_id: str) -> None:
        assert owner_id in chase.owners
        assert chase.transitions < 8
        classified_owners.append(owner_id)
        original_refine(chase, owner_id)

    monkeypatch.setattr(
        r17, "verify_prior_level_fingerprints", lambda: result["PRIOR_LEVEL_FINGERPRINT_VALIDATION"]
    )
    monkeypatch.setattr(r17.r7, "joint_residual_census", _forbidden)
    monkeypatch.setattr(r17.r6, "iter_type_count_vectors", _forbidden)
    monkeypatch.setattr(r17, "classify_new_tail_vector", guarded)
    monkeypatch.setattr(r17, "refine_classified_owner", guarded_refine)
    replay = json.loads(
        json.dumps(
            r17.build_result(
                refine_classified_owners=bool(result["CLASSIFIED_OWNER_CONTINUATION_AUTHORIZED"])
            )
        )
    )
    assert len(classified_losses) == result["TAIL_VECTORS_PROCESSED"]
    assert classified_owners == [row["owner_id"] for row in result["CLASSIFIED_OWNER_CERTIFICATES"]]
    for key in (
        "R3_BOUND",
        "R3_DROP",
        "CURRENT_STATE_TERMS",
        "CURRENT_CLASSIFIED_TERMS",
        "OWNER_TRANSITIONS",
        "OWNER_ACTION_TRAJECTORY",
        "STATE_OWNER_CERTIFICATES",
        "CLASSIFIED_OWNER_CERTIFICATES",
        "TAIL_LEVEL_CERTIFICATES",
        "FINAL_OWNER_IDS",
        "NEXT_UNCLASSIFIED_LOSS",
        "STOP_CONDITION",
    ):
        assert replay[key] == result[key]
    assert result["STATE_OWNERS_PROCESSED"] == 0
    assert replay["CURRENT_STATE_TERMS"] == r17.authority()["CURRENT_STATE_TERMS"]
    trajectory = result["OWNER_ACTION_TRAJECTORY"]
    assert all(row["from"] == previous["to"] for previous, row in pairwise(trajectory))
    assert sum(row["from"] != row["to"] for row in trajectory) == result["OWNER_TRANSITION_COUNT"]
    assert result["R3_BOUND"] == max(
        result["STATE_MAX_BOUND"],
        result["UNCLASSIFIED_TAIL_BOUND"],
        result["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"],
    )
    for row in result["TAIL_LEVEL_CERTIFICATES"]:
        assert row["local_loss"] >= r17.START_LOSS
        assert r17.TAIL_BASE_CONSTANT - row["local_loss"] > row["active_competing_threshold"]
        assert row["unresolved_count"] == 0
    if result["CLASSIFIED_OWNER_CONTINUATION_AUTHORIZED"]:
        assert result["SUCCESS_C"] is True
        assert result["OWNER_TRANSITION_COUNT"] == 8
        assert result["TAIL_LEVELS_PROCESSED"] == 32
        assert result["TAIL_VECTORS_PROCESSED"] == 354
        assert result["CLASSIFIED_OWNERS_PROCESSED"] == 6
        assert result["R3_BOUND"] == 356_523_195
        assert result["R3_DROP"] == 7_427
        assert result["NEXT_UNCLASSIFIED_LOSS"] == 8_525_433
        assert result["FINAL_OWNER_IDS"] == [r17.TAIL_ID]
        assert result["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"] == 356_521_973
        assert result["SUCCESS_A"] is result["SUCCESS_B"] is False
    else:
        assert result["TASK_STATUS"] == r17.STOP_SCOPE
        assert result["OWNER_TRANSITION_COUNT"] == 1
        assert result["TAIL_LEVELS_PROCESSED"] == 22
        assert result["TAIL_VECTORS_PROCESSED"] == 208
        assert result["R3_BOUND"] == 356_527_168
        assert result["UNCLASSIFIED_TAIL_BOUND"] == 356_527_108
        assert result["FINAL_OWNER_IDS"] == [
            "tail-vector:L6709346:0x6,1x2,4x9,19x1",
            "tail-vector:L6709346:0x6,1x9,4x2,17x1",
        ]
