"""R22 coupled state/tail/classified owner dispatch, lineage, and replay guards."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator, Sequence
from dataclasses import replace
from itertools import pairwise
from pathlib import Path
from typing import Any, NoReturn, cast

import pytest

from lottolab.research import b649_k20_r3_state_tail_coupled_owner_chase_r22 as r22


def forbidden(*_: object, **__: object) -> NoReturn:
    pytest.fail("a forbidden proof dependency was dispatched")


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(r22.RESULT_PATH.read_text(encoding="utf-8")))


def with_state(chase: r22.Chase, identifier: str, bound: int) -> None:
    chase.states = tuple(
        (other, bound if other == identifier else value) for other, value in chase.states
    )


def tail_owned_chase() -> r22.Chase:
    chase = r22.initial_chase()
    with_state(chase, r22.START_STATE_ID, r22.START_UNCLASSIFIED_TAIL_BOUND - 1)
    assert chase.owners == (r22.TAIL_ID,)
    return chase


def test_canonical_primitives_margin_and_exact_start_owner() -> None:
    assert r22.canonical_primitives() == {
        "SINGLE_TICKET_ANY_PRIZE": 18_611_432,
        "PAIR_INTERSECTION_COST[6]": 18_611_432,
        "K20_S1": 372_228_640,
    }
    assert r22.canonical_baseline() == 372_228_640 - r22.r13.FIXED_CERTIFIED_LOSS == 365_048_628
    assert r22.START_OWNER_MARGIN == 154
    assert r22.STATE_TO_TAIL_SOLE_OWNER_DROP == 155
    assert r22.SUCCESS_B_THRESHOLD == 356_278_218
    chase = r22.initial_chase()
    assert chase.owners == (r22.START_STATE_ID,)
    assert r22.select_owner(chase) == r22.START_STATE_ID
    assert chase.bound == chase.state_max == 356_378_218
    assert chase.tail_bound == 356_378_064
    assert chase.next_loss == 8_670_564
    assert chase.classified_maximum == ("carried-r12-other-levels", 356_056_456)
    assert chase.competitor(r22.START_STATE_ID) == 356_378_064
    assert chase.stop_condition() is None


def test_r21_authority_fingerprint_and_lineage() -> None:
    assert r22.verify_upstream_fingerprints() == r22.UPSTREAM_SHA256
    stored = r22.authority()
    assert stored["TASK_ID"] == r22.r21.TASK_ID
    assert stored["R3_BOUND"] == 356_378_218
    root = r22.REPO_ROOT
    for head in (r22.BASE_HEAD, r22.WEAKER_SIBLING_HEAD):
        ancestry = subprocess.run(
            ["git", "-C", str(root), "merge-base", "--is-ancestor", head, "HEAD"], check=False
        )
        assert ancestry.returncode == 0
    tree = subprocess.run(
        ["git", "-C", str(root), "rev-parse", f"{r22.BASE_HEAD}^{{tree}}"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert tree.stdout.strip() == r22.BASE_TREE


def test_weaker_sibling_lineage_is_never_substituted() -> None:
    r20_result = cast(dict[str, Any], json.loads(r22.r20.RESULT_PATH.read_text(encoding="utf-8")))
    assert r20_result["R3_BOUND"] == 356_501_945
    with pytest.raises(AssertionError, match="weaker-lineage"):
        r22.require_r21_authority(r20_result)
    r21_result = dict(r22.authority())
    r22.require_r21_authority(r21_result)
    for override in (
        {"R3_BOUND": 356_598_858},
        {"BASE_HEAD": "0f76a7c77013670d2bd35f334b245e6bf8d5cf6f"},
        {"TASK_ID": r22.r20.TASK_ID},
    ):
        with pytest.raises(AssertionError, match="weaker-lineage"):
            r22.require_r21_authority(r21_result | override)


def test_upstream_fingerprint_drift_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(r22, "UPSTREAM_SHA256", {next(iter(r22.UPSTREAM_SHA256)): "0" * 64})
    with pytest.raises(AssertionError, match="R21 authority fingerprint mismatch"):
        r22.verify_upstream_fingerprints()


@pytest.mark.parametrize(
    ("drop", "owners", "selected", "guard"),
    [
        (153, ("state:s2-13169800-s3-789320",), "state:s2-13169800-s3-789320", None),
        (
            154,
            ("state:s2-13169800-s3-789320", "unclassified-tail"),
            "unclassified-tail",
            "at or below the tail",
        ),
        # The state is no longer an owner, so dispatch rejects it before the tail check.
        (155, ("unclassified-tail",), "unclassified-tail", "non-owner work forbidden"),
    ],
)
def test_state_to_tail_switch_at_155_drop(
    drop: int, owners: tuple[str, ...], selected: str, guard: str | None
) -> None:
    chase = r22.initial_chase()
    with_state(chase, r22.START_STATE_ID, r22.START_STATE_BOUND - drop)
    assert chase.owners == owners
    assert r22.select_owner(chase) == selected
    if guard is not None:
        with pytest.raises(AssertionError, match=guard):
            r22.refine_state_owner(chase, r22.START_STATE_ID)


def test_state_structural_certificate_recovers_region_and_relaxation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(r22.r16, "next_attained_loss", forbidden)
    monkeypatch.setattr(r22.r13, "classify_vector", forbidden)
    monkeypatch.setattr(r22.r14, "run_s4_attempt", forbidden)
    record = r22.state_structural_certificate(r22.START_STATE_ID)
    assert record["joint_s2"] == 13_169_800
    assert record["maximum_joint_s3"] == 789_320
    assert record["frontier_bound"] == 356_378_218
    assert record["canonical_joint_expression_constant"] == 372_228_640 - 3_469_942
    assert record["region_compressed_member_count"] == 989
    assert record["region_type_vector_count"] == 1_072
    assert record["maximizing_member_count"] == 6
    assert all(len(vectors) == 1 for vectors in record["maximizing_represented_vectors"])
    assert record["r7_census_pin"]["RESIDUAL_STATE_COUNT"] == 10_117
    assert record["prior_state_refinements"] == 0
    for member in record["maximizing_members"]:
        assert member["raw_bound"] == 356_378_218
        assert member["applied_residual_union_penalty"] == 2_296_000
        assert member["applied_residual_union_penalty"] == max(
            member["residual_pair_union_penalty"], member["complementary_forest_floor"]
        )
    assert record["load_bearing_relaxations"]


def test_r7_census_pin_drift_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(r22, "R7_RESULT_RELATIVE", r22.R21_RESULT_RELATIVE)
    r22.pinned_r7_census.cache_clear()
    try:
        with pytest.raises((AssertionError, KeyError)):
            r22.pinned_r7_census()
    finally:
        monkeypatch.undo()
        r22.pinned_r7_census.cache_clear()


@pytest.mark.parametrize(
    "key",
    [
        "RESIDUAL_STATE_COUNT",
        "FEASIBLE_TYPE_COUNT_VECTOR_COUNT",
        "S2_S3_FRONTIER_SIZE",
        "S2_S3_FRONTIER_SHA256",
        "S2_S3_ENVELOPE_SHA256",
    ],
)
def test_r7_committed_fingerprint_mismatch_fails_closed(
    key: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stored = cast(
        dict[str, Any],
        json.loads((r22.REPO_ROOT / r22.R7_RESULT_RELATIVE).read_text(encoding="utf-8")),
    )
    value = stored[key]
    stored[key] = value + 1 if isinstance(value, int) else "0" * 64
    pinned = tmp_path / "r7-result.json"
    pinned.write_text(json.dumps(stored), encoding="utf-8")
    monkeypatch.setattr(r22, "R7_RESULT_RELATIVE", str(pinned))
    r22.pinned_r7_census.cache_clear()
    try:
        with pytest.raises(AssertionError, match="differs from its pinned result"):
            r22.pinned_r7_census()
    finally:
        monkeypatch.undo()
        r22.pinned_r7_census.cache_clear()


def test_state_members_refine_one_at_a_time_until_tail_owns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(r22.r16, "next_attained_loss", forbidden)
    monkeypatch.setattr(r22.r13, "classify_vector", forbidden)
    monkeypatch.setattr(r22.r14, "run_s4_attempt", forbidden)
    monkeypatch.setattr(r22.r20, "refine_state_owner", forbidden)
    chase = r22.initial_chase()
    others = {key: value for key, value in chase.states if key != r22.START_STATE_ID}
    for ordinal in range(6):
        assert chase.owners == (r22.START_STATE_ID,)
        r22.refine_state_owner(chase, r22.START_STATE_ID)
        row = chase.state_records[-1]
        assert row["member_prior_bound"] == 356_378_218
        assert row["member"]["raw_bound"] == 356_378_218
        assert row["member_new_bound"] < r22.SUCCESS_B_THRESHOLD
        assert row["tightening_route"] == r22.RATIONAL_MOMENT_ROUTE
        assert row["active_competing_threshold"] == 356_378_064
        assert row["new_bound"] == (356_378_218 if ordinal < 5 else 356_377_770)
        for witness in row["support_witnesses"]:
            counts = r22.dense(witness["counts"])
            assert r22.r8.validate_support_assignment(counts, witness["support_witness"])
    assert chase.owners == (r22.TAIL_ID,)
    assert r22.select_owner(chase) == r22.TAIL_ID
    assert {key: value for key, value in chase.states if key != r22.START_STATE_ID} == others
    with pytest.raises(AssertionError, match="non-owner work forbidden"):
        r22.refine_state_owner(chase, r22.START_STATE_ID)


def test_prior_tail_guard_precedes_enumeration_and_classification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chase = tail_owned_chase()
    chase.next_loss = r22.START_LOSS - 1
    monkeypatch.setattr(r22.r16, "iter_interval_vectors", forbidden)
    monkeypatch.setattr(r22.r13, "classify_vector", forbidden)
    with pytest.raises(AssertionError, match="prior tail"):
        r22.next_tail_level(chase)
    counts = r22.r17.counts_from_vector_id("tail-vector:L8460256:0x3,4x13,5x1,9x1")
    with pytest.raises(AssertionError, match="prior tail"):
        r22.classify_new_tail_vector(counts, 365_048_628, 356_378_064)


def test_prior_levels_are_fingerprinted_never_enumerated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(r22.r16, "iter_interval_vectors", forbidden)
    monkeypatch.setattr(r22.r16, "next_attained_loss", forbidden)
    monkeypatch.setattr(r22.r6, "iter_type_count_vectors", forbidden)
    r22.prior_level_fingerprints.cache_clear()
    prior = r22.prior_level_fingerprints()
    assert prior["r21_certified_levels"] == 580
    assert prior["r21_certified_vectors"] == 6_741
    assert prior["r22_first_unclassified_loss"] == 8_670_564
    assert prior["prior_level_enumeration_calls"] == 0


def test_tail_is_dispatched_only_while_it_owns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(r22.r16, "iter_interval_vectors", forbidden)
    chase = r22.initial_chase()
    with pytest.raises(AssertionError, match="non-owner work forbidden"):
        r22.next_tail_level(chase)
    chase = tail_owned_chase()
    monkeypatch.undo()
    loss, vectors, lookahead = r22.next_tail_level(chase)
    assert loss == r22.START_LOSS
    assert vectors
    assert lookahead > loss


def test_classified_owner_first_and_tightened_only_until_ownership_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chase = r22.initial_chase()
    chase.classified_terms |= {
        "tail-vector:first": 356_600_000,
        "tail-vector:second": 356_600_000,
        "tail-vector:lower": 356_500_000,
    }
    chase.sync_classified_maximum()
    with_state(chase, r22.START_STATE_ID, 356_600_000)
    recovered: list[str] = []

    def recover(_chase: r22.Chase, identifier: str) -> dict[str, Any]:
        recovered.append(identifier)
        return {"counts": [[0, 18]], "source_loss_level": 8_670_564}

    def moment(_: r22.CountVector) -> dict[str, Any]:
        return {"correction_lower_bound": 300_000}

    monkeypatch.setattr(r22.r19, "recover_classified_vector", recover)
    monkeypatch.setattr(r22.r14, "moment_certificate", moment)
    assert r22.select_owner(chase) == "tail-vector:first"
    with pytest.raises(AssertionError, match="at or below the tail"):
        r22.refine_state_owner(chase, r22.START_STATE_ID)
    r22.refine_classified_owner(chase, "tail-vector:first")
    assert r22.select_owner(chase) == "tail-vector:second"
    r22.refine_classified_owner(chase, "tail-vector:second")
    assert chase.owners == (r22.START_STATE_ID,)
    assert chase.classified_terms["tail-vector:first"] == 365_048_628 - 8_670_564 - 300_000
    with pytest.raises(AssertionError, match="non-owner work forbidden"):
        r22.refine_classified_owner(chase, "tail-vector:lower")
    assert recovered == ["tail-vector:first", "tail-vector:second"]


def test_aggregate_classified_and_carried_state_owners_stop_for_scope() -> None:
    chase = r22.initial_chase()
    chase.classified_terms[r22.START_CLASSIFIED_ID] = 357_000_000
    chase.sync_classified_maximum()
    with pytest.raises(r22.ClassifiedScopeRequired):
        r22.refine_classified_owner(chase, r22.START_CLASSIFIED_ID)
    chase = r22.initial_chase()
    carried = "state:s2-12695020-s3-735532"
    with_state(chase, carried, 356_400_000)
    assert chase.owners == (carried,)
    with pytest.raises(r22.StateScopeRequired):
        r22.refine_state_owner(chase, carried)


def test_exhausted_rational_member_is_reported_not_assumed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def weak(_: r22.CountVector) -> dict[str, Any]:
        return {"correction_lower_bound": 0}

    monkeypatch.setattr(r22.r14, "moment_certificate", weak)
    chase = r22.initial_chase()
    with pytest.raises(r22.r15.RationalRouteExhausted):
        r22.refine_state_owner(chase, r22.START_STATE_ID)
    assert chase.states == r22.initial_chase().states
    assert chase.state_records == []


def test_malformed_support_fails_before_level_is_certified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chase = tail_owned_chase()
    loss, vectors, lookahead = r22.next_tail_level(chase)
    valid = r22.classify_new_tail_vector(vectors[0], chase.baseline, chase.competitor(r22.TAIL_ID))
    malformed = replace(valid, witness=())

    def level(_: r22.Chase) -> tuple[int, tuple[r22.CountVector, ...], int]:
        return loss, (vectors[0],), lookahead

    def classify(_: r22.CountVector, _baseline: int, _threshold: int) -> r22.ClassifiedVector:
        return malformed

    monkeypatch.setattr(r22, "next_tail_level", level)
    monkeypatch.setattr(r22, "classify_new_tail_vector", classify)
    with pytest.raises(AssertionError, match="support witness"):
        r22.advance_tail(chase)
    assert chase.tail_records == []
    assert chase.next_loss == r22.START_LOSS


def test_success_ignores_transition_count_and_stops_at_drop() -> None:
    chase = r22.initial_chase()
    chase.transition_limit = 1
    chase.events = [{"from": ["previous"], "to": [r22.START_STATE_ID]}] * 100
    assert chase.stop_condition() is None
    with_state(chase, r22.START_STATE_ID, r22.SUCCESS_B_THRESHOLD)
    chase.next_loss = 365_048_628 - r22.SUCCESS_B_THRESHOLD
    assert chase.bound == r22.SUCCESS_B_THRESHOLD
    assert chase.stop_condition() == r22.STOP_B
    with pytest.raises(AssertionError, match="work after stop condition"):
        r22.next_tail_level(chase)


@pytest.mark.parametrize("budget", [0, -1, 3_601])
def test_invalid_wall_budget_rejected(budget: float) -> None:
    with pytest.raises(ValueError, match="at most 3600"):
        r22.run_chase(wall_budget=budget)


def test_result_owner_chase_and_final_maximum(result: dict[str, Any]) -> None:
    assert result["TASK_STATUS"] == "SUCCESS_B"
    assert result["SUCCESS_B"] is True
    assert result["SUCCESS_A"] is result["SUCCESS_C"] is False
    assert result["START_R3_BOUND"] == 356_378_218
    assert result["R3_DROP"] >= 100_000
    assert result["R3_BOUND"] <= r22.SUCCESS_B_THRESHOLD
    assert result["R3_BOUND"] == max(
        result["STATE_MAX_BOUND"],
        result["UNCLASSIFIED_TAIL_BOUND"],
        result["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"],
    )
    assert result["STATE_MAX_BOUND"] == max(row["bound"] for row in result["CURRENT_STATE_TERMS"])
    assert result["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"] == max(
        row["bound"] for row in result["CURRENT_CLASSIFIED_TERMS"]
    )
    assert result["UNCLASSIFIED_TAIL_BOUND"] == 365_048_628 - result["NEXT_UNCLASSIFIED_LOSS"]
    assert result["REMAINING_GAP"] == result["R3_BOUND"] - 313_239_661
    assert result["CANONICAL_PRIMITIVE_STATUS"] == "PASS"
    assert result["OWNER_TRANSITION_LIMIT"] is None
    assert result["STATE_OWNERS_PROCESSED"] == 1
    assert result["PROCESSED_STATE_OWNER_IDS"] == [r22.START_STATE_ID]
    assert result["STATE_MEMBERS_CERTIFIED"] == 36
    assert result["CLASSIFIED_VECTOR_OWNERS_PROCESSED"] == 0
    switch = result["STATE_TO_TAIL_SWITCH"]
    assert switch["state_drop_at_first_switch"] >= 155
    assert switch["tail_sole_owner_at_first_switch"] is True
    sequence = result["OWNER_CLASS_SEQUENCE"]
    assert sequence[0] == ["state"]
    assert len(sequence) == result["OWNER_TRANSITION_COUNT"] + 1
    assert all(previous != following for previous, following in pairwise(sequence))
    initial = {row["stable_id"]: row["bound"] for row in r22.authority()["CURRENT_STATE_TERMS"]}
    final = {row["stable_id"]: row["bound"] for row in result["CURRENT_STATE_TERMS"]}
    assert {key: value for key, value in final.items() if key != r22.START_STATE_ID} == {
        key: value for key, value in initial.items() if key != r22.START_STATE_ID
    }
    for row in result["STATE_OWNER_CERTIFICATES"]:
        assert row["member_prior_bound"] > row["tail_bound_at_dispatch"]
        assert row["member_prior_bound"] >= row["active_competing_threshold"]
    for row in result["TAIL_LEVEL_CERTIFICATES"]:
        assert row["local_loss"] >= r22.START_LOSS
        assert 365_048_628 - row["local_loss"] >= row["active_competing_threshold"]
        assert row["unresolved_count"] == 0
    for key in (
        "PRIOR_TAIL_LEVELS_ENUMERATED",
        "PRIOR_VECTORS_RECLASSIFIED",
        "NON_OWNER_STATE_TERMS_CHANGED",
        "PRIOR_CLASSIFIED_TERMS_CHANGED",
        "GENERIC_FRONTIER_CENSUS_CALLS",
        "GENERIC_CLASSIFIED_CENSUS_CALLS",
    ):
        assert result[key] == 0


def test_guarded_full_replay_matches_every_owner_action(
    result: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    intervals: list[int] = []
    member_losses: list[int] = []
    refined: list[str] = []
    original_interval = r22.r16.iter_interval_vectors
    original_refine = r22.refine_state_owner

    def interval(
        losses: Sequence[int],
        tickets: int,
        lower: int,
        upper: int,
    ) -> Iterator[r22.CountVector]:
        assert lower == upper
        if lower < r22.r7.JOINT_LOCAL_LOSS_CUTOFF:
            member_losses.append(lower)  # compressed-member recovery, never a tail level
        else:
            assert r22.START_LOSS <= lower < 365_048_628 - r22.SUCCESS_B_THRESHOLD
            intervals.append(lower)
        return original_interval(losses, tickets, lower, upper)

    def refine(chase: r22.Chase, identifier: str) -> None:
        assert r22.select_owner(chase) == identifier
        assert dict(chase.states)[identifier] > chase.tail_bound
        refined.append(identifier)
        original_refine(chase, identifier)

    # The pinned R7 census replay only locates the owner region; warm it before the
    # guards so this replay does not depend on earlier tests having filled the caches.
    r22.state_region(r22.START_STATE_ID)
    monkeypatch.setattr(r22.r16, "iter_interval_vectors", interval)
    monkeypatch.setattr(r22, "refine_state_owner", refine)
    monkeypatch.setattr(r22.r6, "iter_type_count_vectors", forbidden)
    monkeypatch.setattr(r22.r21, "next_tail_level", forbidden)
    monkeypatch.setattr(r22.r21, "advance_tail", forbidden)
    monkeypatch.setattr(r22.r20, "refine_state_owner", forbidden)
    monkeypatch.setattr(r22.r19, "refine_state_owner", forbidden)
    monkeypatch.setattr(r22.r16, "verify_prior_level_fingerprints", forbidden)
    monkeypatch.setattr(r22.r17, "verify_prior_level_fingerprints", forbidden)
    monkeypatch.setattr(r22.r14, "run_s4_attempt", forbidden)
    replay = cast(dict[str, Any], json.loads(json.dumps(r22.build_result())))
    for key in result:
        if key != "PROOF_WALL_SECONDS":
            assert replay[key] == result[key], key
    assert intervals == [row["local_loss"] for row in result["TAIL_LEVEL_CERTIFICATES"]]
    assert refined == [r22.START_STATE_ID] * result["STATE_MEMBERS_CERTIFIED"]
    assert set(member_losses) <= {
        row["member"]["local_loss"] for row in result["STATE_OWNER_CERTIFICATES"]
    }
    events = result["OWNER_ACTION_TRAJECTORY"]
    assert all(row["from"] == previous["to"] for previous, row in pairwise(events))
    for event in events:
        assert event["r3_bound"] == max(
            event["state_max_bound"],
            event["unclassified_tail_bound"],
            event["max_classified_tail_vector_bound"],
        )
    for row in replay["NEW_TAIL_VECTOR_STRUCTURAL_RECORDS"]:
        if row["status"] == r22.r12.WITNESS_REALIZED:
            assert r22.r8.validate_support_assignment(tuple(row["counts"]), row["witness"])
