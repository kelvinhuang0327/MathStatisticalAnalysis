"""R21 owner-only correction, complete-band crossover, and frozen-state guards."""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from dataclasses import replace
from itertools import pairwise
from typing import Any, NoReturn, cast

import pytest

from lottolab.research import b649_k20_r3_classified_tail_band_to_state_r21 as r21


def forbidden(*_: object, **__: object) -> NoReturn:
    pytest.fail("a forbidden proof dependency was dispatched")


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(r21.RESULT_PATH.read_text(encoding="utf-8")))


def test_canonical_primitives_crossover_and_exact_start_owner() -> None:
    assert r21.canonical_primitives() == {
        "SINGLE_TICKET_ANY_PRIZE": 18_611_432,
        "PAIR_INTERSECTION_COST[6]": 18_611_432,
        "K20_S1": 372_228_640,
    }
    baseline = 372_228_640 - r21.r13.FIXED_CERTIFIED_LOSS
    assert baseline == r21.canonical_baseline() == 365_048_628
    assert baseline - 356_378_218 == r21.STATE_CROSSOVER_LOSS == 8_670_410
    assert baseline - 8_670_409 == 356_378_219
    chase = r21.initial_chase()
    assert chase.owners == (r21.START_OWNER_ID,)
    assert chase.classified_maximum == (r21.START_OWNER_ID, 356_501_945)
    assert chase.tail_bound == 356_501_796
    assert chase.next_loss == 8_546_832
    assert chase.state_max == 356_378_218
    assert chase.stop_condition() is None


def test_prior_certificates_never_rerun_old_census(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(r21.r16, "iter_interval_vectors", forbidden)
    monkeypatch.setattr(r21.r16, "next_attained_loss", forbidden)
    monkeypatch.setattr(r21.r20.r7, "joint_residual_census", forbidden)
    monkeypatch.setattr(r21.r6, "iter_type_count_vectors", forbidden)
    r21.prior_level_fingerprints.cache_clear()
    prior = r21.prior_level_fingerprints()
    assert prior["r20_certified_levels"] == 91
    assert prior["r20_certified_vectors"] == 917
    assert prior["r21_first_unclassified_loss"] == 8_546_832
    assert prior["prior_level_enumeration_calls"] == 0


def test_prior_level_guard_precedes_enumeration_and_classification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chase = r21.initial_chase()
    chase.classified_terms[r21.START_OWNER_ID] = 356_000_000
    chase.sync_classified_maximum()
    chase.next_loss = r21.START_LOSS - 1
    monkeypatch.setattr(r21.r16, "iter_interval_vectors", forbidden)
    monkeypatch.setattr(r21.r13, "classify_vector", forbidden)
    with pytest.raises(AssertionError, match="prior tail"):
        r21.next_tail_level(chase)
    counts = r21.r17.counts_from_vector_id(r21.START_OWNER_ID)
    with pytest.raises(AssertionError, match="prior tail"):
        r21.classify_new_tail_vector(counts, 365_048_628)


def test_initial_owner_relaxation_and_first_sufficient_certificate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(r21.r16, "iter_interval_vectors", forbidden)
    monkeypatch.setattr(r21.r6, "iter_type_count_vectors", forbidden)
    monkeypatch.setattr(r21.r13, "classify_vector", forbidden)
    monkeypatch.setattr(r21.r14, "run_s4_attempt", forbidden)
    monkeypatch.setattr(r21.r20, "refine_state_owner", forbidden)
    chase = r21.initial_chase()
    frozen = dict(chase.classified_terms)
    states = chase.states
    r21.refine_classified_owner(chase, r21.START_OWNER_ID)
    row = chase.classified_records[0]
    structural = row["structural_record"]
    assert structural["source_loss_level"] == 6_742_484
    assert structural["counts"] == [[0, 6], [1, 11], [6, 1]]
    assert structural["current_correction"] == 1_804_199
    assert structural["r6_structural_record"]["combined_pair_penalty"] == 1_804_199
    assert row["certificate"]["residual_s2_lower_bound"] == 44_905_364
    assert row["certificate"]["correction_lower_bound"] == 4_989_485
    assert row["new_bound"] == 353_316_659
    assert row["active_competing_threshold"] == 356_501_796
    assert chase.owners == (r21.TAIL_ID,)
    assert chase.states == states
    assert len(chase.classified_records) == 1
    assert row["first_sufficient_certificate"] is True
    assert row["further_refinement_dispatched"] is False
    counts = r21.r20.dense(structural["counts"])
    assert r21.r8.validate_support_assignment(counts, structural["support_witness"])
    assert all(
        bound == chase.classified_terms[identifier]
        for identifier, bound in frozen.items()
        if identifier != r21.START_OWNER_ID
    )
    with pytest.raises(AssertionError, match="non-owner work forbidden"):
        r21.refine_classified_owner(chase, r21.START_OWNER_ID)


def test_classified_owner_switches_and_tied_maxima_stay_separate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chase = r21.initial_chase()
    chase.classified_terms = {
        "tail-vector:first": 356_600_000,
        "tail-vector:second": 356_600_000,
        "tail-vector:lower": 356_599_000,
    }
    chase.sync_classified_maximum()
    recovered: list[str] = []

    def recover(_chase: r21.Chase, identifier: str) -> dict[str, Any]:
        recovered.append(identifier)
        return {"counts": [[0, 18]], "source_loss_level": 8_546_832}

    def moment(_: r21.CountVector) -> dict[str, Any]:
        return {"correction_lower_bound": 200_000}

    monkeypatch.setattr(r21.r19, "recover_classified_vector", recover)
    monkeypatch.setattr(r21.r14, "moment_certificate", moment)
    r21.refine_classified_owner(chase, "tail-vector:first")
    assert chase.owners == ("tail-vector:second",)
    with pytest.raises(AssertionError, match="non-owner work forbidden"):
        r21.refine_classified_owner(chase, "tail-vector:lower")
    r21.refine_classified_owner(chase, "tail-vector:second")
    assert chase.owners == ("tail-vector:lower",)
    assert recovered == ["tail-vector:first", "tail-vector:second"]


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_tail_crossover_stops_before_enumeration(
    offset: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chase = r21.initial_chase()
    chase.classified_terms[r21.START_OWNER_ID] = 353_316_659
    chase.sync_classified_maximum()
    chase.next_loss = r21.STATE_CROSSOVER_LOSS + offset
    calls: list[int] = []

    def interval(
        _losses: Sequence[int],
        _tickets: int,
        lower: int,
        _upper: int,
    ) -> Iterator[r21.CountVector]:
        calls.append(lower)
        return iter((r21.r17.counts_from_vector_id(r21.START_OWNER_ID),))

    def next_loss(_losses: Sequence[int], _tickets: int, lower: int) -> int:
        return lower

    monkeypatch.setattr(r21.r16, "iter_interval_vectors", interval)
    monkeypatch.setattr(r21.r16, "next_attained_loss", next_loss)
    if offset < 0:
        assert r21.next_tail_level(chase)[0] == 8_670_409
        assert calls == [8_670_409]
    else:
        assert chase.stop_condition() == r21.STOP_A
        with pytest.raises(AssertionError):
            r21.next_tail_level(chase)
        assert calls == []


def test_no_below_state_refinement_or_work_after_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chase = r21.initial_chase()
    chase.next_loss = r21.STATE_CROSSOVER_LOSS
    chase.classified_terms[r21.START_OWNER_ID] = r21.STATE_THRESHOLD
    chase.sync_classified_maximum()
    monkeypatch.setattr(r21.r19, "recover_classified_vector", forbidden)
    monkeypatch.setattr(r21.r14, "moment_certificate", forbidden)
    assert chase.stop_condition() == r21.STOP_A
    with pytest.raises(AssertionError, match="work after stop condition"):
        r21.refine_classified_owner(chase, r21.START_OWNER_ID)


def test_malformed_support_fails_before_level_is_certified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chase = r21.initial_chase()
    chase.classified_terms[r21.START_OWNER_ID] = 353_316_659
    chase.sync_classified_maximum()
    loss, vectors, lookahead = r21.next_tail_level(chase)
    valid = r21.classify_new_tail_vector(vectors[0], chase.baseline)
    malformed = replace(valid, witness=())

    def level(_: r21.Chase) -> tuple[int, tuple[r21.CountVector, ...], int]:
        return loss, (vectors[0],), lookahead

    def classify(_: r21.CountVector, _baseline: int) -> r21.ClassifiedVector:
        return malformed

    monkeypatch.setattr(r21, "next_tail_level", level)
    monkeypatch.setattr(r21, "classify_new_tail_vector", classify)
    with pytest.raises(AssertionError, match="support witness"):
        r21.advance_tail(chase)
    assert chase.tail_records == []
    assert chase.next_loss == r21.START_LOSS


def test_new_classified_owner_interrupts_tail_and_is_the_only_refinement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chase = r21.initial_chase()
    chase.classified_terms[r21.START_OWNER_ID] = 353_316_659
    chase.sync_classified_maximum()
    loss, vectors, lookahead = r21.next_tail_level(chase)
    valid = r21.classify_new_tail_vector(vectors[0], chase.baseline)
    newly_load_bearing = replace(valid, vector_bound=chase.baseline - lookahead + 1)

    def level(_: r21.Chase) -> tuple[int, tuple[r21.CountVector, ...], int]:
        return loss, (vectors[0],), lookahead

    def classify(_: r21.CountVector, _baseline: int) -> r21.ClassifiedVector:
        return newly_load_bearing

    def moment(_: r21.CountVector) -> dict[str, Any]:
        return {"correction_lower_bound": 200_000}

    monkeypatch.setattr(r21, "next_tail_level", level)
    monkeypatch.setattr(r21, "classify_new_tail_vector", classify)
    r21.advance_tail(chase)
    assert chase.owners == (valid.vector_id,)
    monkeypatch.setattr(r21.r16, "iter_interval_vectors", forbidden)
    monkeypatch.setattr(r21.r14, "moment_certificate", moment)
    r21.refine_classified_owner(chase, valid.vector_id)
    assert chase.owners == (r21.TAIL_ID,)
    assert chase.classified_records[0]["owner_id"] == valid.vector_id
    assert chase.classified_terms[valid.vector_id] <= r21.STATE_THRESHOLD


@pytest.mark.parametrize("budget", [0, -1, 3_601])
def test_invalid_wall_budget_rejected(budget: float) -> None:
    with pytest.raises(ValueError, match="at most 3600"):
        r21.run_chase(wall_budget=budget)


def test_upstream_fingerprint_drift_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(r21, "UPSTREAM_SHA256", {next(iter(r21.UPSTREAM_SHA256)): "0" * 64})
    with pytest.raises(AssertionError, match="R20 authority fingerprint mismatch"):
        r21.verify_upstream_fingerprints()


def test_success_does_not_depend_on_transition_count_or_drop() -> None:
    chase = r21.initial_chase()
    chase.drop_target = 1
    chase.transition_limit = 1
    chase.events = [{"from": ["previous"], "to": [r21.START_OWNER_ID]}] * 100
    assert chase.stop_condition() is None


def test_result_complete_band_and_exact_frozen_state(result: dict[str, Any]) -> None:
    assert result["TASK_STATUS"] == "SUCCESS_A"
    assert result["SUCCESS_A"] is True
    assert result["SUCCESS_B"] is result["SUCCESS_C"] is False
    assert result["CLASSIFIED_OWNERS_PROCESSED"] == 1
    assert result["TAIL_LEVELS_PROCESSED"] > 91
    assert result["TAIL_VECTORS_PROCESSED"] > 917
    assert result["NEXT_UNCLASSIFIED_LOSS"] >= 8_670_410
    assert result["UNCLASSIFIED_TAIL_BOUND"] <= 356_378_218
    assert result["MAX_CLASSIFIED_TAIL_VECTOR_BOUND"] <= 356_378_218
    assert result["STATE_MAX_BOUND"] == result["STATE_THRESHOLD"] == 356_378_218
    assert result["R3_BOUND"] == 356_378_218
    assert result["R3_DROP"] == 123_727
    assert result["R3_BOUND_OWNER_CLASS"] == "state"
    assert result["FINAL_OWNER_IDS"] == result["STATE_MAX_OWNER_IDS"]
    assert result["CURRENT_STATE_TERMS"] == r21.authority()["CURRENT_STATE_TERMS"]
    assert result["REMAINING_GAP"] == 43_138_557
    assert result["CANONICAL_PRIMITIVE_STATUS"] == "PASS"
    assert result["OWNER_TRANSITION_LIMIT"] is None
    for key in (
        "PRIOR_TAIL_LEVELS_ENUMERATED",
        "PRIOR_VECTORS_RECLASSIFIED",
        "STATE_TERMS_CHANGED",
        "STATE_REFINEMENT_DISPATCHES",
        "NON_OWNER_CLASSIFIED_TERMS_REFINED",
        "BELOW_STATE_REFINEMENT_DISPATCHES",
        "GENERIC_CLASSIFIED_CENSUS_CALLS",
    ):
        assert result[key] == 0


def test_guarded_full_replay_matches_all_levels_vectors_and_owners(
    result: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    intervals: list[int] = []
    original_interval = r21.r16.iter_interval_vectors
    original_classify = r21.classify_new_tail_vector
    original_refine = r21.refine_classified_owner
    refined: list[str] = []
    classified: list[int] = []

    def interval(
        losses: Sequence[int],
        tickets: int,
        lower: int,
        upper: int,
    ) -> Iterator[r21.CountVector]:
        assert r21.START_LOSS <= lower == upper < r21.STATE_CROSSOVER_LOSS
        intervals.append(lower)
        return original_interval(losses, tickets, lower, upper)

    def classify(counts: r21.CountVector, baseline: int) -> r21.ClassifiedVector:
        loss = r21.r12.local_loss(counts, r21.r6.local_losses(r21.r5.anchor_incidence_profiles()))
        assert loss >= r21.START_LOSS
        classified.append(loss)
        return original_classify(counts, baseline)

    def refine(chase: r21.Chase, identifier: str) -> None:
        assert identifier in chase.owners
        assert chase.classified_terms[identifier] > r21.STATE_THRESHOLD
        refined.append(identifier)
        original_refine(chase, identifier)

    monkeypatch.setattr(r21.r16, "iter_interval_vectors", interval)
    monkeypatch.setattr(r21, "classify_new_tail_vector", classify)
    monkeypatch.setattr(r21, "refine_classified_owner", refine)
    monkeypatch.setattr(r21.r6, "iter_type_count_vectors", forbidden)
    monkeypatch.setattr(r21.r20.r7, "joint_residual_census", forbidden)
    monkeypatch.setattr(r21.r20, "refine_state_owner", forbidden)
    monkeypatch.setattr(r21.r19, "refine_state_owner", forbidden)
    monkeypatch.setattr(r21.r16, "verify_prior_level_fingerprints", forbidden)
    monkeypatch.setattr(r21.r17, "verify_prior_level_fingerprints", forbidden)
    monkeypatch.setattr(r21.r14, "run_s4_attempt", forbidden)
    replay = cast(dict[str, Any], json.loads(json.dumps(r21.build_result())))
    for key in result:
        if key != "PROOF_WALL_SECONDS":
            assert replay[key] == result[key], key
    assert intervals == [row["local_loss"] for row in result["TAIL_LEVEL_CERTIFICATES"]]
    assert len(classified) == result["TAIL_VECTORS_PROCESSED"]
    assert refined == [r21.START_OWNER_ID]
    events = result["OWNER_ACTION_TRAJECTORY"]
    assert all(row["from"] == previous["to"] for previous, row in pairwise(events))
    for event in events:
        assert event["r3_bound"] == max(
            event["state_max_bound"],
            event["unclassified_tail_bound"],
            event["max_classified_tail_vector_bound"],
        )
    assert all(
        row["local_loss"] < 8_670_410 and row["unresolved_count"] == 0
        for row in replay["TAIL_LEVEL_CERTIFICATES"]
    )
    for row in replay["NEW_TAIL_VECTOR_STRUCTURAL_RECORDS"]:
        if row["status"] == r21.r12.WITNESS_REALIZED:
            assert r21.r8.validate_support_assignment(tuple(row["counts"]), row["witness"])
