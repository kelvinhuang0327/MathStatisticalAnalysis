"""R23 continuation, owner-only dispatch, pinned recovery, and isolated replay."""

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

from lottolab.research import b649_k20_r3_tail_to_state_dynamic_chase_r23 as r23


def forbidden(*_: object, **__: object) -> NoReturn:
    pytest.fail("forbidden prior-level or non-owner work")


def stored_result() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(r23.RESULT_PATH.read_text()))


def state_owned_chase() -> r23.Chase:
    chase = r23.initial_chase()
    chase.next_loss = r23.STATE_CROSSOVER_LOSS + 1
    assert chase.owners == (r23.START_STATE_ID,)
    return chase


def test_exact_base_r22_pins_primitives_and_crossover() -> None:
    assert r23.verify_upstream_fingerprints() == r23.UPSTREAM_SHA256
    assert r23.authority()["R3_BOUND"] == 356_277_971
    tree = subprocess.run(
        ["git", "-C", str(r23.REPO_ROOT), "rev-parse", f"{r23.BASE_HEAD}^{{tree}}"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert tree.stdout.strip() == r23.BASE_TREE
    assert r23.canonical_primitives() == {
        "SINGLE_TICKET_ANY_PRIZE": 18_611_432,
        "PAIR_INTERSECTION_COST[6]": 18_611_432,
        "K20_S1": 372_228_640,
    }
    assert r23.canonical_baseline() == 365_048_628
    assert 365_048_628 - 356_247_108 == r23.STATE_CROSSOVER_LOSS == 8_801_520
    chase = r23.initial_chase()
    assert chase.next_loss == 8_770_657
    assert chase.owners == (r23.TAIL_ID,)
    assert chase.state_max == 356_247_108
    assert chase.classified_maximum[1] == 356_056_456
    assert chase.state_region_bounds == {}


def test_r22_fingerprint_mutation_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    for relative in r23.UPSTREAM_SHA256:
        monkeypatch.setattr(r23, "UPSTREAM_SHA256", r23.UPSTREAM_SHA256 | {relative: "0" * 64})
        with pytest.raises(AssertionError, match="R22 authority fingerprint mismatch"):
            r23.verify_upstream_fingerprints()
        monkeypatch.undo()
    assert r23.verify_upstream_fingerprints() == r23.UPSTREAM_SHA256


def test_prior_level_guard_precedes_enumeration_and_classification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chase = r23.initial_chase()
    chase.next_loss = r23.START_LOSS - 1
    monkeypatch.setattr(r23.r16, "iter_interval_vectors", forbidden)
    monkeypatch.setattr(r23.r13, "classify_vector", forbidden)
    with pytest.raises(AssertionError, match="prior tail"):
        r23.next_tail_level(chase)
    counts = r23.r17.counts_from_vector_id("tail-vector:L8769565:0x8,4x7,8x1,12x1,16x1")
    with pytest.raises(AssertionError, match="prior tail"):
        r23.classify_new_tail_vector(counts, chase.baseline, chase.state_max)
    r23.prior_level_fingerprints.cache_clear()
    prior = r23.prior_level_fingerprints()
    assert prior["r22_certified_levels"] == 536
    assert prior["r22_certified_vectors"] == 5_959
    assert prior["r23_first_unclassified_loss"] == 8_770_657
    assert prior["prior_level_enumeration_calls"] == 0


def test_owner_switch_and_no_fixed_transition_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    chase = r23.initial_chase()
    monkeypatch.setattr(r23, "state_region", forbidden)
    with pytest.raises(AssertionError, match="non-owner"):
        r23.restore_owner_region(chase, r23.START_STATE_ID)
    with pytest.raises(AssertionError, match="non-owner"):
        r23.refine_state_owner(chase, r23.START_STATE_ID)
    chase.next_loss = r23.STATE_CROSSOVER_LOSS
    assert set(chase.owners) == {r23.START_STATE_ID, r23.TAIL_ID}
    assert r23.select_owner(chase) == r23.START_STATE_ID
    monkeypatch.setattr(r23.r16, "iter_interval_vectors", forbidden)
    with pytest.raises(AssertionError, match="tail descent"):
        r23.next_tail_level(chase)
    chase.next_loss += 1
    assert r23.select_owner(chase) == r23.START_STATE_ID
    monkeypatch.setattr(r23.r16, "iter_interval_vectors", forbidden)
    with pytest.raises(AssertionError, match="non-owner"):
        r23.next_tail_level(chase)
    chase.transition_limit = 1
    chase.events = [{"from": ["old"], "to": [r23.TAIL_ID]}] * 1_000
    assert chase.stop_condition() is None


def test_restore_exact_carried_region_without_prior_moment_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(r23.r14, "moment_certificate", forbidden)
    monkeypatch.setattr(r23.r14, "run_s4_attempt", forbidden)
    chase = state_owned_chase()
    r23.restore_owner_region(chase, r23.START_STATE_ID)
    bounds = chase.state_region_bounds[r23.START_STATE_ID]
    assert len(bounds) == 989
    assert max(bounds.values()) == 356_247_108
    assert chase.carried_regions[0]["carried_reduced_member_count"] == 36
    region = r23.state_region(r23.START_STATE_ID)
    assert sum(bounds[row.witness_counts] != r23.r14.raw_bound(row) for row in region) == 36
    assert len([row for row in region if bounds[row.witness_counts] == chase.state_max]) > 0


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
    r22 = r23.r22
    pinned = cast(dict[str, Any], json.loads((r22.REPO_ROOT / r22.R7_RESULT_RELATIVE).read_text()))
    pinned[key] = pinned[key] + 1 if isinstance(pinned[key], int) else "0" * 64
    path = tmp_path / "mutated-r7.json"
    path.write_text(json.dumps(pinned))
    monkeypatch.setattr(r22, "R7_RESULT_RELATIVE", str(path))
    r23.pinned_r7_census.cache_clear()
    try:
        with pytest.raises(AssertionError, match="differs from its pinned result"):
            r23.pinned_r7_census()
    finally:
        monkeypatch.undo()
        r23.pinned_r7_census.cache_clear()
    assert r23.pinned_r7_census()[key] != pinned[key]


@pytest.mark.parametrize("mutation", ["region", "member", "reduction"])
def test_carried_region_mutation_fails_before_dispatch(
    mutation: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pinned = cast(dict[str, Any], json.loads(json.dumps(r23.authority())))
    region = pinned["STATE_REGION_CERTIFICATES"][0]
    if mutation == "region":
        region["region_sha256"] = "0" * 64
    elif mutation == "member":
        region["complete_region_members"][0]["raw_bound"] += 1
    else:
        region["certified_member_count"] -= 1
    monkeypatch.setattr(r23, "authority", lambda: pinned)
    with pytest.raises(AssertionError, match="carried"):
        r23.restore_owner_region(state_owned_chase(), r23.START_STATE_ID)


def test_malformed_support_cannot_advance_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    chase = r23.initial_chase()
    loss, vectors, lookahead = r23.next_tail_level(chase)
    valid = r23.classify_new_tail_vector(vectors[0], chase.baseline, chase.state_max)
    malformed = replace(valid, witness=())

    def level(_: r23.Chase) -> tuple[int, tuple[r23.CountVector, ...], int]:
        return loss, (vectors[0],), lookahead

    def classify(
        _: r23.CountVector,
        _baseline: int,
        _threshold: int,
    ) -> r23.ClassifiedVector:
        return malformed

    monkeypatch.setattr(r23, "next_tail_level", level)
    monkeypatch.setattr(r23, "classify_new_tail_vector", classify)
    with pytest.raises(AssertionError, match="support witness"):
        r23.advance_tail(chase)
    assert chase.next_loss == r23.START_LOSS
    assert chase.tail_records == []
    assert chase.tail_vector_records == []


def test_fourth_order_is_used_only_above_live_competitor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chase = r23.initial_chase()
    _, vectors, _ = r23.next_tail_level(chase)
    counts = vectors[0]
    base = r23.r12.classify_vector(counts, chase.baseline)
    assert base.vector_bound is not None
    calls: list[r23.CountVector] = []

    def fourth(vector: r23.CountVector) -> int:
        calls.append(vector)
        return 0

    monkeypatch.setattr(r23.r13, "four_ticket_penalty", fourth)
    r23.r13.classify_vector.cache_clear()
    try:
        row = r23.classify_new_tail_vector(counts, chase.baseline, base.vector_bound)
        assert row.four_ticket_status == r23.r13.FOUR_TICKET_NOT_REQUIRED
        assert calls == []
        row = r23.classify_new_tail_vector(counts, chase.baseline, base.vector_bound - 1)
        assert row.four_ticket_status == r23.r13.FOUR_TICKET_APPLIED
        assert calls == [counts]
    finally:
        r23.r13.classify_vector.cache_clear()


def test_classified_owner_preempts_and_only_that_vector_is_refined(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chase = r23.initial_chase()
    chase.classified_terms |= {"tail-vector:first": 357_000_000, "tail-vector:lower": 356_300_000}
    chase.sync_classified_maximum()
    recovered: list[str] = []

    def recover(_: r23.Chase, identifier: str) -> dict[str, Any]:
        recovered.append(identifier)
        return {"counts": [[0, 18]], "source_loss_level": r23.START_LOSS}

    def moment(_: r23.CountVector) -> dict[str, Any]:
        return {"correction_lower_bound": 300_000}

    monkeypatch.setattr(r23.r19, "recover_classified_vector", recover)
    monkeypatch.setattr(r23.r14, "moment_certificate", moment)
    assert r23.select_owner(chase) == "tail-vector:first"
    with pytest.raises(AssertionError, match="non-owner"):
        r23.refine_classified_owner(chase, "tail-vector:lower")
    r23.refine_classified_owner(chase, "tail-vector:first")
    assert recovered == ["tail-vector:first"]
    assert chase.classified_terms["tail-vector:lower"] == 356_300_000
    assert r23.select_owner(chase) == "tail-vector:lower"


@pytest.mark.parametrize("budget", [0, -1, 3_601])
def test_invalid_wall_budget(budget: float) -> None:
    with pytest.raises(ValueError, match="at most 3600"):
        r23.run_chase(wall_budget=budget)


def test_family_maximum_transition_history_and_owner_only_accounting() -> None:
    result = stored_result()
    assert result["TASK_STATUS"] == "SUCCESS_B"
    assert result["START_R3_BOUND"] - result["R3_BOUND"] >= 100_000
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
    assert result["R7_FINGERPRINT_STATUS"] == result["CANONICAL_PRIMITIVE_STATUS"] == "PASS"
    assert result["OWNER_TRANSITION_LIMIT"] is None
    events = result["OWNER_ACTION_TRAJECTORY"]
    assert events[0]["from"] == [r23.TAIL_ID]
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
    assert len(result["OWNER_TRANSITIONS"]) == result["OWNER_TRANSITION_COUNT"]
    assert len(result["OWNER_CLASS_SEQUENCE"]) == result["OWNER_TRANSITION_COUNT"] + 1
    tail = result["TAIL_LEVEL_CERTIFICATES"]
    assert tail[0]["local_loss"] == 8_770_657
    assert all(a["next_unclassified_loss"] == b["local_loss"] for a, b in pairwise(tail))
    for row in tail:
        assert row["local_loss"] >= 8_770_657
        assert 365_048_628 - row["local_loss"] >= row["active_competing_threshold"]
        assert row["unresolved_count"] == 0
    prior_counts = {
        r23.dense(row["member"]["witness_counts"])
        for row in r23.authority()["STATE_OWNER_CERTIFICATES"]
    }
    for row in result["STATE_OWNER_CERTIFICATES"]:
        assert row["owner_id"] in row["owner_set_at_dispatch"]
        assert row["member_prior_bound"] >= row["tail_bound_at_dispatch"]
        assert r23.dense(row["member"]["witness_counts"]) not in prior_counts
        assert row["member_new_bound"] < row["member_prior_bound"]
    for key in (
        "PRIOR_TAIL_LEVELS_ENUMERATED",
        "PRIOR_VECTORS_RECLASSIFIED",
        "NON_OWNER_STATE_TERMS_CHANGED",
        "GENERIC_FRONTIER_CENSUS_CALLS",
        "GENERIC_CLASSIFIED_CENSUS_CALLS",
    ):
        assert result[key] == 0


def test_isolated_full_replay_from_empty_process_caches(tmp_path: Path) -> None:
    """A fresh interpreter guards dispatch before any dependency cache is warm."""
    script = r"""
import json
import sys
from lottolab.research import b649_k20_r3_tail_to_state_dynamic_chase_r23 as r

def forbidden(*args, **kwargs):
    raise AssertionError("forbidden historical or generic proof dispatch")

intervals, members, classified = [], [], []
old_interval = r.r16.iter_interval_vectors
old_moment = r.r14.moment_certificate
old_classify = r.r13.classify_vector
old_pin = r.r22.pinned_r7_census
old_r6_enumerate = r.r6.iter_type_count_vectors
old_r7_enumerate = r.r7.iter_type_count_vectors
inside_r7_pin = False
pin_enumerations = []
carried = {r.dense(row["member"]["witness_counts"])
           for row in r.authority()["STATE_OWNER_CERTIFICATES"]}

def pinned_census():
    global inside_r7_pin
    inside_r7_pin = True
    try:
        return old_pin()
    finally:
        inside_r7_pin = False

def r6_enumerate(losses, tickets, cutoff):
    assert inside_r7_pin, "generic R6 census outside R7 pin validation"
    assert cutoff == r.r6.PREVIOUS_REDUCTION
    pin_enumerations.append(("R6_REUSE", cutoff))
    return old_r6_enumerate(losses, tickets, cutoff)

def r7_enumerate(losses, tickets, cutoff):
    assert inside_r7_pin, "generic R7 census outside owner location"
    assert cutoff == r.r7.JOINT_LOCAL_LOSS_CUTOFF
    pin_enumerations.append(("R7_PIN", cutoff))
    return old_r7_enumerate(losses, tickets, cutoff)

def interval(losses, tickets, lower, upper):
    assert lower == upper
    if lower >= r.r7.JOINT_LOCAL_LOSS_CUTOFF:
        assert lower >= r.START_LOSS
        intervals.append(lower)
    return old_interval(losses, tickets, lower, upper)

def moment(counts):
    assert counts not in carried
    members.append(counts)
    return old_moment(counts)

def classify(counts, baseline, threshold):
    losses = r.r6.local_losses(r.r5.anchor_incidence_profiles())
    assert r.r12.local_loss(counts, losses) >= r.START_LOSS
    classified.append(counts)
    return old_classify(counts, baseline, threshold)

r.r16.iter_interval_vectors = interval
r.r14.moment_certificate = moment
r.r13.classify_vector = classify
r.r22.pinned_r7_census = pinned_census
r.r6.iter_type_count_vectors = r6_enumerate
r.r7.iter_type_count_vectors = r7_enumerate
r.r22.run_chase = forbidden
r.r22.build_result = forbidden
r.r22.refine_state_owner = forbidden
r.r22.next_tail_level = forbidden
r.r22.advance_tail = forbidden
r.r14.run_s4_attempt = forbidden
r.r7.family_a_result_record = forbidden
r.r16.verify_prior_level_fingerprints = forbidden
r.r17.verify_prior_level_fingerprints = forbidden
observed = json.loads(json.dumps(r.build_result()))
stored = json.loads(r.RESULT_PATH.read_text())
for key in stored:
    if key != "PROOF_WALL_SECONDS":
        assert observed[key] == stored[key], key
assert intervals == [row["local_loss"] for row in observed["TAIL_LEVEL_CERTIFICATES"]]
assert len(classified) == observed["TAIL_VECTORS_PROCESSED"]
assert len(members) == sum(row["represented_vector_count"]
                           for row in observed["STATE_OWNER_CERTIFICATES"])
assert pin_enumerations == [("R6_REUSE", r.r6.PREVIOUS_REDUCTION),
                            ("R7_PIN", r.r7.JOINT_LOCAL_LOSS_CUTOFF)]
for row in observed["NEW_TAIL_VECTOR_STRUCTURAL_RECORDS"]:
    if row["status"] == r.r12.WITNESS_REALIZED:
        assert r.r8.validate_support_assignment(tuple(row["counts"]), row["witness"])
print("ISOLATED_REPLAY_PASS", len(intervals), len(classified), len(members))
"""
    env = os.environ | {
        "PYTHONPATH": str(r23.REPO_ROOT / "src"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "TMPDIR": str(tmp_path),
    }
    replay = subprocess.run(
        [sys.executable, "-c", script],
        cwd=r23.REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=3_600,
    )
    assert replay.returncode == 0, replay.stdout + replay.stderr
    assert "ISOLATED_REPLAY_PASS" in replay.stdout
