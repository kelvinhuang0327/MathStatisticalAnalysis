"""R24 crossover, owner-only dispatch, carried ledgers, R12 recovery, and isolated replay."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import replace
from itertools import pairwise
from pathlib import Path
from typing import Any, NoReturn, cast

import pytest

from lottolab.research import b649_k20_r3_tail_crossover_state_dynamic_chase_r24 as r24

CARRIED_STATE = "state:s2-13169800-s3-789320"
R14_R15_STATE = "state:s2-12695020-s3-735532"
R14_R16_R20_STATE = "state:s2-12692531-s3-681744"
R9_WHOLE_STATE = "state:s2-10833008-s3-427140"


def forbidden(*_: object, **__: object) -> NoReturn:
    pytest.fail("forbidden prior-level or non-owner work")


def stored_result() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(r24.RESULT_PATH.read_text()))


def owned_chase(owner_id: str) -> r24.Chase:
    """A synthetic chase where only ``owner_id`` keeps its carried term at the maximum."""

    chase = r24.initial_chase()
    term = dict(chase.states)[owner_id]
    chase.states = tuple(
        (identifier, bound if identifier == owner_id else min(bound, term - 1))
        for identifier, bound in chase.states
    )
    chase.classified_terms = {
        identifier: min(bound, term - 1) for identifier, bound in chase.classified_terms.items()
    }
    chase.sync_classified_maximum()
    chase.next_loss = chase.baseline - term + 1
    assert chase.owners == (owner_id,)
    return chase


def aggregate_owned_chase() -> r24.Chase:
    chase = r24.initial_chase()
    chase.states = tuple((identifier, 300_000_000) for identifier, _ in chase.states)
    chase.next_loss = chase.baseline - 300_000_000
    assert chase.owners == (r24.AGGREGATE_ID,)
    return chase


def test_exact_base_r23_pins_primitives_and_crossover() -> None:
    assert r24.verify_upstream_fingerprints() == r24.UPSTREAM_SHA256 | r24.CARRIED_SHA256
    assert r24.authority()["R3_BOUND"] == 356_177_969
    tree = subprocess.run(
        ["git", "-C", str(r24.REPO_ROOT), "rev-parse", f"{r24.BASE_HEAD}^{{tree}}"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert tree.stdout.strip() == r24.BASE_TREE
    assert r24.canonical_primitives() == {
        "SINGLE_TICKET_ANY_PRIZE": 18_611_432,
        "PAIR_INTERSECTION_COST[6]": 18_611_432,
        "K20_S1": 372_228_640,
    }
    assert r24.canonical_baseline() == 365_048_628 == 372_228_640 - 7_180_012
    assert 365_048_628 - 356_161_470 == r24.STATE_CROSSOVER_LOSS == 8_887_158
    assert 8_887_158 - 8_870_659 == r24.STATE_CROSSOVER_INTERVAL == 16_499
    assert r24.START_UNCLASSIFIED_TAIL_BOUND == 365_048_628 - 8_870_659
    chase = r24.initial_chase()
    assert chase.next_loss == 8_870_659
    assert chase.owners == (r24.TAIL_ID,)
    assert chase.state_max == 356_161_470
    assert r24.r13.identify_owner_set(chase.states) == (r24.START_STATE_ID,)
    assert chase.classified_maximum == (r24.AGGREGATE_ID, 356_056_456)
    assert chase.competitor(r24.TAIL_ID) == 356_161_470
    assert chase.state_region_bounds == {}


def test_r23_and_carried_fingerprint_mutation_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name, pins in (
        ("UPSTREAM_SHA256", r24.UPSTREAM_SHA256),
        ("CARRIED_SHA256", r24.CARRIED_SHA256),
    ):
        for relative in pins:
            monkeypatch.setattr(r24, name, pins | {relative: "0" * 64})
            with pytest.raises(AssertionError, match="R23 authority fingerprint mismatch"):
                r24.verify_upstream_fingerprints()
            monkeypatch.undo()
    assert r24.verify_upstream_fingerprints() == r24.UPSTREAM_SHA256 | r24.CARRIED_SHA256


def test_prior_level_guard_precedes_enumeration_and_classification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chase = r24.initial_chase()
    chase.next_loss = r24.START_LOSS - 1
    monkeypatch.setattr(r24.r16, "iter_interval_vectors", forbidden)
    monkeypatch.setattr(r24.r16, "next_attained_loss", forbidden)
    monkeypatch.setattr(r24.r13, "classify_vector", forbidden)
    with pytest.raises(AssertionError, match="prior tail"):
        r24.next_tail_level(chase)
    last_r23 = r24.authority()["NEW_TAIL_VECTOR_STRUCTURAL_RECORDS"][-1]
    counts = r24.r17.counts_from_vector_id(last_r23["vector_id"])
    with pytest.raises(AssertionError, match="prior tail"):
        r24.classify_new_tail_vector(counts, chase.baseline, chase.state_max)
    r24.prior_level_fingerprints.cache_clear()
    prior = r24.prior_level_fingerprints()
    assert prior["r23_certified_levels"] == 523
    assert prior["r23_certified_vectors"] == 6_592
    assert prior["r23_certified_level_range"][0] == 8_770_657
    assert prior["r24_first_unclassified_loss"] == 8_870_659
    assert prior["prior_level_enumeration_calls"] == 0


def test_tail_window_never_passes_the_live_competitor(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[int, int]] = []
    original = r24.r16.iter_interval_vectors

    def spy(losses: Any, tickets: int, lower: int, upper: int) -> Any:
        calls.append((lower, upper))
        return original(losses, tickets, lower, upper)

    monkeypatch.setattr(r24.r16, "iter_interval_vectors", spy)
    chase = r24.initial_chase()
    loss, vectors, lookahead = r24.next_tail_level(chase)
    assert (loss, calls) == (r24.START_LOSS, [(r24.START_LOSS, r24.START_LOSS + 8_000)])
    assert vectors and lookahead > loss
    assert all(level < r24.STATE_CROSSOVER_LOSS for level in chase.tail_window)
    # The last Phase-1 level: the window stops exactly at the state crossover.
    near = r24.initial_chase()
    near.next_loss = 8_887_102
    loss, vectors, lookahead = r24.next_tail_level(near)
    assert calls[-1] == (8_887_102, r24.STATE_CROSSOVER_LOSS)
    assert near.tail_windows[-1]["entitled_upper"] == r24.STATE_CROSSOVER_LOSS
    assert lookahead >= r24.STATE_CROSSOVER_LOSS
    near.next_loss = lookahead
    assert r24.select_owner(near) == r24.START_STATE_ID
    # A competitor that rises after the census shrinks the window before dispatch.
    rising = r24.initial_chase()
    rising.next_loss = r24.next_tail_level(rising)[2]
    rising.classified_terms["tail-vector:synthetic"] = 356_170_000
    rising.sync_classified_maximum()
    r24.next_tail_level(rising)
    assert rising.tail_window_upper == rising.baseline - 356_170_000
    assert all(level <= rising.tail_window_upper for level in rising.tail_window)


def test_owner_switch_and_no_fixed_transition_or_drop_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chase = r24.initial_chase()
    monkeypatch.setattr(r24, "state_region", forbidden)
    with pytest.raises(AssertionError, match="non-owner"):
        r24.restore_owner_region(chase, r24.START_STATE_ID)
    with pytest.raises(AssertionError, match="non-owner"):
        r24.refine_state_owner(chase, r24.START_STATE_ID)
    chase.next_loss = r24.STATE_CROSSOVER_LOSS
    assert set(chase.owners) == {r24.START_STATE_ID, r24.TAIL_ID}
    assert r24.select_owner(chase) == r24.START_STATE_ID
    monkeypatch.setattr(r24.r16, "iter_interval_vectors", forbidden)
    with pytest.raises(AssertionError, match="tail descent"):
        r24.next_tail_level(chase)
    chase.next_loss += 1
    with pytest.raises(AssertionError, match="non-owner"):
        r24.next_tail_level(chase)
    chase.events = [{"from": ["old"], "to": [r24.TAIL_ID]}] * 10_000
    assert chase.stop_condition() is None
    chase.next_loss = chase.baseline - (r24.START_R3_BOUND - 1_000_000)
    chase.states = tuple((identifier, 300_000_000) for identifier, _ in chase.states)
    chase.classified_terms = {r24.AGGREGATE_ID: 300_000_000}
    chase.sync_classified_maximum()
    assert chase.stop_condition() is None
    chase.next_loss = chase.baseline - r24.R4_REFERENCE_BOUND
    assert chase.stop_condition() == r24.STOP_A


@pytest.mark.parametrize(
    ("owner_id", "rounds", "members"),
    [
        (r24.START_STATE_ID, [], 1_427),
        (CARRIED_STATE, ["R22", "R23"], 989),
        (R14_R15_STATE, ["R14", "R15"], 1_222),
        (R14_R16_R20_STATE, ["R14", "R16", "R20"], 582),
    ],
)
def test_carried_member_ledger_reproduces_the_state_term_without_moment_work(
    owner_id: str,
    rounds: list[str],
    members: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(r24.r14, "moment_certificate", forbidden)
    monkeypatch.setattr(r24.r14, "run_s4_attempt", forbidden)
    chase = owned_chase(owner_id)
    r24.restore_owner_region(chase, owner_id)
    bounds = chase.state_region_bounds[owner_id]
    record = chase.carried_regions[-1]
    assert len(bounds) == members
    assert max(bounds.values()) == dict(chase.states)[owner_id]
    assert record["carried_certificate_rounds"] == rounds
    assert record["initial_maximizing_members_raw"] is True
    assert record["prior_member_certificate_calls"] == 0
    region = r24.state_region(owner_id)
    reduced = sum(bounds[row.witness_counts] != r24.r14.raw_bound(row) for row in region)
    assert reduced == record["carried_reduced_member_count"]
    assert (reduced > 0) == bool(rounds)


def test_whole_state_certificate_without_member_ledger_is_a_scope_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(r24.r14, "moment_certificate", forbidden)
    chase = owned_chase(R9_WHOLE_STATE)
    with pytest.raises(r24.r22.StateScopeRequired):
        r24.restore_owner_region(chase, R9_WHOLE_STATE)
    assert R9_WHOLE_STATE not in chase.state_region_bounds


@pytest.mark.parametrize("mutation", ["region", "above-raw", "outside", "dropped"])
def test_carried_ledger_mutation_fails_before_dispatch(
    mutation: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pinned = cast(dict[str, Any], json.loads(json.dumps(r24.authority())))
    r22_pinned = cast(
        dict[str, Any], json.loads(json.dumps(r24.stored_result(r24.R22_RESULT_RELATIVE)))
    )
    region = next(
        row for row in pinned["STATE_REGION_CERTIFICATES"] if row["owner_id"] == CARRIED_STATE
    )
    if mutation == "region":
        region["region_sha256"] = "0" * 64
    elif mutation == "above-raw":
        region["complete_region_members"][0]["final_bound"] = (
            region["complete_region_members"][0]["raw_bound"] + 1
        )
    elif mutation == "outside":
        region["complete_region_members"][0]["witness_counts"] = [[0, 18]]
    else:
        pinned["STATE_REGION_CERTIFICATES"] = []
        r22_pinned["STATE_REGION_CERTIFICATES"] = []
    original = r24.stored_result

    def stored(relative: str) -> dict[str, Any]:
        return r22_pinned if relative == r24.R22_RESULT_RELATIVE else original(relative)

    monkeypatch.setattr(r24, "authority", lambda: pinned)
    monkeypatch.setattr(r24, "stored_result", stored)
    monkeypatch.setattr(r24.r14, "moment_certificate", forbidden)
    r24.carried_member_certificates.cache_clear()
    try:
        chase = owned_chase(CARRIED_STATE)
        if mutation == "dropped":
            with pytest.raises(r24.r22.StateScopeRequired):
                r24.restore_owner_region(chase, CARRIED_STATE)
        else:
            with pytest.raises(AssertionError, match="carried R23 member certificate"):
                r24.restore_owner_region(chase, CARRIED_STATE)
        assert chase.state_region_bounds == {}
    finally:
        r24.carried_member_certificates.cache_clear()


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
def test_r7_pin_mutation_rejects_real_committed_topology(
    key: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    r22 = r24.r22
    pinned = cast(dict[str, Any], json.loads((r22.REPO_ROOT / r22.R7_RESULT_RELATIVE).read_text()))
    pinned[key] = pinned[key] + 1 if isinstance(pinned[key], int) else "0" * 64
    path = tmp_path / "mutated-r7.json"
    path.write_text(json.dumps(pinned))
    monkeypatch.setattr(r22, "R7_RESULT_RELATIVE", str(path))
    r24.pinned_r7_census.cache_clear()
    try:
        with pytest.raises(AssertionError, match="differs from its pinned result"):
            r24.pinned_r7_census()
    finally:
        monkeypatch.undo()
        r24.pinned_r7_census.cache_clear()
    assert r24.pinned_r7_census()[key] != pinned[key]


def test_r12_aggregate_recovers_only_its_owner_level(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(r24.r13, "classify_vector", forbidden)
    monkeypatch.setattr(r24.r12, "classify_vector", forbidden)
    monkeypatch.setattr(r24.r12, "construct_support_witness", forbidden)
    monkeypatch.setattr(r24.r14, "moment_certificate", forbidden)
    chase = aggregate_owned_chase()
    before = dict(chase.classified_terms)
    r24.refine_classified_owner(chase, r24.AGGREGATE_ID)
    record = chase.r12_recoveries[-1]
    assert record["recovered_level"] == 6_696_172
    assert record["vector_count"] == 14
    assert record["aggregate_bound_after"] == 356_056_008
    assert chase.split_r12_levels == [6_696_172]
    assert chase.bound == 356_056_456
    assert r24.AGGREGATE_ID not in chase.owners
    assert all(owner.startswith("tail-vector:L6696172:") for owner in chase.owners)
    recovered = {row["stable_id"] for row in record["recovered_terms"]}
    assert set(chase.classified_terms) == set(before) | recovered
    assert all(
        chase.classified_terms[key] == value
        for key, value in before.items()
        if key != r24.AGGREGATE_ID
    )
    with pytest.raises(AssertionError, match="non-owner"):
        r24.recover_r12_aggregate_level(chase)
    assert chase.events[-1]["action"] == "classified-recover:carried-r12-other-levels:L6696172"


def test_r12_census_mutation_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    pinned = cast(
        dict[str, Any], json.loads(json.dumps(r24.stored_result(r24.R12_RESULT_RELATIVE)))
    )
    row = next(row for row in pinned["LOSS_LEVEL_ROWS"] if row["local_loss"] == 6_696_172)
    row["minimum_correction"] -= 1
    original = r24.stored_result

    def stored(relative: str) -> dict[str, Any]:
        return pinned if relative == r24.R12_RESULT_RELATIVE else original(relative)

    monkeypatch.setattr(r24, "stored_result", stored)
    r24.r12_aggregate_rows.cache_clear()
    try:
        chase = aggregate_owned_chase()
        terms = dict(chase.classified_terms)
        with pytest.raises(AssertionError, match="stored census"):
            r24.recover_r12_aggregate_level(chase)
        assert chase.classified_terms == terms
        assert chase.split_r12_levels == []
    finally:
        r24.r12_aggregate_rows.cache_clear()


def test_malformed_support_cannot_advance_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    chase = r24.initial_chase()
    loss, vectors, lookahead = r24.next_tail_level(chase)
    valid = r24.classify_new_tail_vector(vectors[0], chase.baseline, chase.state_max)
    malformed = replace(valid, witness=())

    def level(_: r24.Chase) -> tuple[int, tuple[r24.CountVector, ...], int]:
        return loss, (vectors[0],), lookahead

    def classify(_: r24.CountVector, _baseline: int, _threshold: int) -> r24.ClassifiedVector:
        return malformed

    chase = r24.initial_chase()
    monkeypatch.setattr(r24, "next_tail_level", level)
    monkeypatch.setattr(r24, "classify_new_tail_vector", classify)
    with pytest.raises(AssertionError, match="support witness"):
        r24.advance_tail(chase)
    assert chase.next_loss == r24.START_LOSS
    assert chase.tail_records == []
    assert chase.tail_vector_records == []


def test_fourth_order_is_used_only_above_live_competitor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chase = r24.initial_chase()
    _, vectors, _ = r24.next_tail_level(chase)
    counts = vectors[0]
    base = r24.r12.classify_vector(counts, chase.baseline)
    assert base.vector_bound is not None
    calls: list[r24.CountVector] = []

    def fourth(vector: r24.CountVector) -> int:
        calls.append(vector)
        return 0

    monkeypatch.setattr(r24.r13, "four_ticket_penalty", fourth)
    r24.r13.classify_vector.cache_clear()
    try:
        row = r24.classify_new_tail_vector(counts, chase.baseline, base.vector_bound)
        assert row.four_ticket_status == r24.r13.FOUR_TICKET_NOT_REQUIRED
        assert calls == []
        row = r24.classify_new_tail_vector(counts, chase.baseline, base.vector_bound - 1)
        assert row.four_ticket_status == r24.r13.FOUR_TICKET_APPLIED
        assert calls == [counts]
    finally:
        r24.r13.classify_vector.cache_clear()


def test_classified_owner_preempts_and_only_that_vector_is_refined(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chase = r24.initial_chase()
    chase.classified_terms |= {"tail-vector:first": 357_000_000, "tail-vector:lower": 356_300_000}
    chase.sync_classified_maximum()
    recovered: list[str] = []

    def recover(_: r24.Chase, identifier: str) -> dict[str, Any]:
        recovered.append(identifier)
        return {"counts": [[0, 18]], "source_loss_level": r24.START_LOSS}

    def moment(_: r24.CountVector) -> dict[str, Any]:
        return {"correction_lower_bound": 300_000}

    monkeypatch.setattr(r24.r19, "recover_classified_vector", recover)
    monkeypatch.setattr(r24.r14, "moment_certificate", moment)
    assert r24.select_owner(chase) == "tail-vector:first"
    with pytest.raises(AssertionError, match="non-owner"):
        r24.refine_classified_owner(chase, "tail-vector:lower")
    r24.refine_classified_owner(chase, "tail-vector:first")
    assert recovered == ["tail-vector:first"]
    assert chase.classified_terms["tail-vector:lower"] == 356_300_000
    assert r24.select_owner(chase) == "tail-vector:lower"


@pytest.mark.parametrize(("budget", "limit"), [(0, None), (-1, None), (3_601, None), (60, -1)])
def test_invalid_wall_budget_or_replay_limit(budget: float, limit: int | None) -> None:
    with pytest.raises(ValueError):
        r24.run_chase(wall_budget=budget, action_limit=limit)


def carried_reduced_members(owner_id: str) -> set[r24.CountVector]:
    raw = {row.witness_counts: r24.r14.raw_bound(row) for row in r24.state_region(owner_id)}
    return {
        counts
        for _, counts, bound, _ in r24.carried_member_certificates(owner_id)
        if bound < raw[counts]
    }


def test_family_maximum_transition_history_and_owner_only_accounting() -> None:
    result = stored_result()
    assert result["TASK_STATUS"] == "SUCCESS_C"
    assert result["STOP_CONDITION"] == r24.STOP_C
    assert result["PROOF_WALL_BUDGET_SECONDS"] == 3_600.0
    assert result["PROOF_WALL_SECONDS"] >= 3_600.0
    assert result["EXHAUSTED_OWNER_ID"] is result["SCOPE_OWNER_ID"] is None
    states = {row["stable_id"]: row["bound"] for row in result["CURRENT_STATE_TERMS"]}
    classified = {row["stable_id"]: row["bound"] for row in result["CURRENT_CLASSIFIED_TERMS"]}
    tail = 365_048_628 - result["NEXT_UNCLASSIFIED_LOSS"]
    terms = [*states.items(), (r24.TAIL_ID, tail), *classified.items()]
    recomputed = {
        "STATE_MAX_BOUND": max(states.values()),
        "UNCLASSIFIED_TAIL_BOUND": tail,
        "MAX_CLASSIFIED_TAIL_VECTOR_BOUND": max(classified.values()),
        "R3_BOUND": max(bound for _, bound in terms),
        "OWNER_IDS": list(r24.r13.identify_owner_set(terms)),
    }
    assert result["FINAL_FAMILY_MAX_RECOMPUTATION"] == recomputed
    for key in (
        "STATE_MAX_BOUND",
        "UNCLASSIFIED_TAIL_BOUND",
        "MAX_CLASSIFIED_TAIL_VECTOR_BOUND",
        "R3_BOUND",
    ):
        assert result[key] == recomputed[key]
    assert result["FINAL_OWNER_IDS"] == recomputed["OWNER_IDS"]
    assert result["R3_BOUND"] < r24.START_R3_BOUND
    assert result["INCUMBENT"] == r24.INCUMBENT == 313_263_888
    assert result["REMAINING_GAP"] == result["R3_BOUND"] - r24.INCUMBENT == 42_470_743
    assert result["SUCCESS_A"] is False
    assert result["SUCCESS_B"] is False
    assert result["SUCCESS_C"] is True
    assert result["GAP_TO_R4_REFERENCE"] == result["R3_BOUND"] - 350_545_749 > 0
    assert result["R7_FINGERPRINT_STATUS"] == result["CANONICAL_PRIMITIVE_STATUS"] == "PASS"
    assert result["OWNER_TRANSITION_LIMIT"] is None
    events = result["OWNER_ACTION_TRAJECTORY"]
    assert len(events) == result["OWNER_ACTIONS_EXECUTED"]
    assert events[0]["from"] == [r24.TAIL_ID]
    assert events[-1]["to"] == result["FINAL_OWNER_IDS"]
    for previous, following in pairwise(events):
        assert previous["to"] == following["from"]
        assert previous["r3_bound"] >= following["r3_bound"]
    for event in events:
        assert event["r3_bound"] == max(
            event["state_max_bound"],
            event["unclassified_tail_bound"],
            event["max_classified_tail_vector_bound"],
        )
        owners = event["from"]
        action = event["action"]
        has_classified = any(r24.owner_class(owner) == r24.CLASSIFIED_CLASS for owner in owners)
        if action.startswith("tail:"):
            assert owners == [r24.TAIL_ID]
        elif action.startswith("state:"):
            assert action.removeprefix("state:") in owners and not has_classified
        else:
            assert action.startswith(("classified:", "classified-recover:"))
            identifier = action.split(":", 1)[1]
            if action.startswith("classified-recover:"):
                identifier = r24.AGGREGATE_ID
            assert identifier in owners
    assert len(result["OWNER_TRANSITIONS"]) == result["OWNER_TRANSITION_COUNT"]
    assert len(result["OWNER_CLASS_SEQUENCE"]) == result["OWNER_TRANSITION_COUNT"] + 1
    crossover = result["TAIL_CROSSOVER"]
    assert crossover["phase1_end_reason"] == "STATE_OWNER_AT_CROSSOVER"
    assert crossover["phase1_level_range"][0] == 8_870_659
    assert (
        crossover["phase1_level_range"][1] < 8_887_158 <= crossover["phase1_next_unclassified_loss"]
    )
    assert crossover["phase2_state_owner_set"] == [r24.START_STATE_ID]
    assert crossover["phase1_new_vector_above_state_max"] is False
    tail_rows = result["TAIL_LEVEL_CERTIFICATES"]
    assert tail_rows[0]["local_loss"] == 8_870_659
    assert all(a["next_unclassified_loss"] == b["local_loss"] for a, b in pairwise(tail_rows))
    assert tail_rows[-1]["next_unclassified_loss"] == result["NEXT_UNCLASSIFIED_LOSS"]
    windows = result["TAIL_ENUMERATION_WINDOWS"]
    for row in tail_rows:
        assert row["local_loss"] >= 8_870_659
        assert 365_048_628 - row["local_loss"] >= row["active_competing_threshold"]
        assert row["unresolved_count"] == 0
        assert row["owner_set_at_dispatch"] == [r24.TAIL_ID]
        assert any(w["lower"] <= row["local_loss"] <= w["upper"] for w in windows)
    assert all(w["upper"] <= w["entitled_upper"] for w in windows)
    assert sum(row["vector_count"] for row in tail_rows) == result["TAIL_VECTORS_PROCESSED"]
    certified: dict[str, set[r24.CountVector]] = {}
    for row in result["STATE_OWNER_CERTIFICATES"]:
        owner = row["owner_id"]
        counts = r24.dense(row["member"]["witness_counts"])
        assert owner in row["owner_set_at_dispatch"]
        assert row["member_prior_bound"] >= row["tail_bound_at_dispatch"]
        assert row["member_new_bound"] < row["member_prior_bound"]
        assert counts not in certified.setdefault(owner, set())
        certified[owner].add(counts)
    for owner, members in certified.items():
        assert not members & carried_reduced_members(owner)
    for region in result["STATE_REGION_CERTIFICATES"]:
        final = max(row["final_bound"] for row in region["complete_region_members"])
        assert final == region["final_state_bound"] == states[region["owner_id"]]
    initial = {row["stable_id"]: row["bound"] for row in r24.authority()["CURRENT_STATE_TERMS"]}
    changed = {owner for owner, bound in states.items() if bound != initial[owner]}
    assert changed <= set(result["PROCESSED_STATE_OWNER_IDS"])
    for key in (
        "PRIOR_TAIL_LEVELS_ENUMERATED",
        "PRIOR_VECTORS_RECLASSIFIED",
        "NON_OWNER_STATE_TERMS_CHANGED",
        "GENERIC_FRONTIER_CENSUS_CALLS",
        "GENERIC_CLASSIFIED_CENSUS_CALLS",
    ):
        assert result[key] == 0
    assert result["NEW_PORTFOLIO_SEARCH_STARTED"] == "NO"
    assert result["PRODUCTION_MUTATION"] == "NONE"


def test_isolated_prefix_replay_from_empty_process_caches(tmp_path: Path) -> None:
    """A fresh interpreter replays the stored prefix through every owner class."""
    script = r"""
import json
from lottolab.research import b649_k20_r3_tail_crossover_state_dynamic_chase_r24 as r

def forbidden(*args, **kwargs):
    raise AssertionError("forbidden historical or generic proof dispatch")

stored = json.loads(r.RESULT_PATH.read_text())
actions = [row["action"] for row in stored["OWNER_ACTION_TRAJECTORY"]]
classified = [i for i, a in enumerate(actions) if a.startswith("classified")]
prefix = min(len(actions), max(600, (classified[0] + 3) if classified else 0), 2_500)
r12_levels = {int(row["local_loss"]) for row in r.r12_aggregate_rows()}
intervals, members, tail_classified = [], [], []
old_interval = r.r16.iter_interval_vectors
old_moment = r.r14.moment_certificate
old_classify = r.r13.classify_vector
reduced = set()

def interval(losses, tickets, lower, upper):
    if lower >= r.START_LOSS:
        intervals.append(("TAIL_WINDOW", lower, upper))
    elif lower <= r.r7.JOINT_LOCAL_LOSS_CUTOFF:
        assert lower == upper, (lower, upper)
        intervals.append(("STATE_MEMBER_LEVEL", lower, upper))
    else:
        assert lower == upper and lower in r12_levels, (lower, upper)
        intervals.append(("R12_OWNER_LEVEL", lower, upper))
    return old_interval(losses, tickets, lower, upper)

def moment(counts):
    members.append(counts)
    return old_moment(counts)

def classify(counts, baseline, threshold):
    losses = r.r6.local_losses(r.r5.anchor_incidence_profiles())
    assert r.r12.local_loss(counts, losses) >= r.START_LOSS
    tail_classified.append(counts)
    return old_classify(counts, baseline, threshold)

r.r16.iter_interval_vectors = interval
r.r14.moment_certificate = moment
r.r13.classify_vector = classify
for module in (r.r23, r.r22):
    for name in (
        "run_chase", "build_result", "refine_state_owner", "next_tail_level", "advance_tail"
    ):
        setattr(module, name, forbidden)
r.r23.restore_owner_region = forbidden
r.r14.run_s4_attempt = forbidden
r.r7.family_a_result_record = forbidden
r.r16.verify_prior_level_fingerprints = forbidden
r.r17.verify_prior_level_fingerprints = forbidden
outcome = r.replay_stored_result(prefix)
assert outcome["status"] == "PASS", outcome
assert outcome["replayed_actions"] == prefix
observed = stored["OWNER_ACTION_TRAJECTORY"][:prefix]
replayed_tail = [e for e in observed if e["action"].startswith("tail:")]
assert len(tail_classified) == sum(
    row["vector_count"] for row in stored["TAIL_LEVEL_CERTIFICATES"][: len(replayed_tail)]
)
windows = [w for w in intervals if w[0] == "TAIL_WINDOW"]
assert windows == [
    ("TAIL_WINDOW", w["lower"], w["upper"])
    for w in stored["TAIL_ENUMERATION_WINDOWS"][: len(windows)]
]
assert all(w[2] - w[1] <= r.TAIL_WINDOW_WIDTH for w in windows)
assert [w[1] for w in intervals if w[0] == "STATE_MEMBER_LEVEL"] == [
    int(row["member"]["local_loss"])
    for row in stored["STATE_OWNER_CERTIFICATES"][
        : sum(e["action"].startswith("state:") for e in observed)
    ]
]
assert [w[1] for w in intervals if w[0] == "R12_OWNER_LEVEL"] == [
    int(row["recovered_level"])
    for row in stored["R12_AGGREGATE_RECOVERIES"][
        : sum(e["action"].startswith("classified-recover:") for e in observed)
    ]
]
for owner in {row["owner_id"] for row in stored["CARRIED_OWNER_REGION_CERTIFICATES"]}:
    raw = {row.witness_counts: r.r14.raw_bound(row) for row in r.state_region(owner)}
    reduced |= {c for _, c, b, _ in r.carried_member_certificates(owner) if b < raw[c]}
assert not reduced & set(members)
kinds = {e["action"].split(":", 1)[0] for e in observed}
print("ISOLATED_REPLAY_PASS", prefix, sorted(kinds), len(windows), len(members))
"""
    env = os.environ | {
        "PYTHONPATH": str(r24.REPO_ROOT / "src"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "TMPDIR": str(tmp_path),
    }
    replay = subprocess.run(
        [sys.executable, "-c", script],
        cwd=r24.REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=3_600,
    )
    assert replay.returncode == 0, replay.stdout + replay.stderr
    assert "ISOLATED_REPLAY_PASS" in replay.stdout
