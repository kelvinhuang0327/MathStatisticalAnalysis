"""Synthetic-only acceptance for the T539 prospective shadow observer harness."""

from __future__ import annotations

import copy
from typing import Any, cast

import pytest
from tools import run_t539_prospective_shadow_observer as observer

SYNTHETIC_TARGET = "999999999"
SYNTHETIC_HISTORY_START = int(SYNTHETIC_TARGET) - 750


@pytest.fixture(scope="module")
def contract() -> observer.FreezeContract:
    return observer.load_freeze_contract()


def _ticket(identity_index: int, position: int) -> list[int]:
    start = (identity_index * 3 + position * 7) % 39
    return sorted(((start + offset) % 39) + 1 for offset in range(5))


def _synthetic_inputs(contract: observer.FreezeContract) -> dict[str, Any]:
    cells: list[dict[str, Any]] = []
    for k in observer.FROZEN_K_VALUES:
        frozen_cell = contract.cells[k]
        candidate_metrics = [
            {
                "identity": list(identity),
                "prize_tier_counts": [0, 0, 0, 1],
                "success": True,
                "winning_ticket_count": 1,
            }
            for identity in frozen_cell.original_identities
        ]
        history = [
            {
                "candidate_metrics": candidate_metrics,
                "target_identity": str(SYNTHETIC_HISTORY_START + offset),
            }
            for offset in range(750)
        ]
        predictions = [
            {
                "identity": list(identity),
                "tickets": [_ticket(identity_index, position) for position in range(k)],
            }
            for identity_index, identity in enumerate(frozen_cell.original_identities)
        ]
        cells.append(
            {
                "history": history,
                "k": k,
                "lottery_id": "T539",
                "predictions": predictions,
            }
        )
    return {
        "authority_identity": "SYNTHETIC_T539_PRETARGET_FIXTURE_R1",
        "cells": cells,
        "outcome_presence": "ABSENT",
        "schema_version": observer.PRETARGET_INPUT_SCHEMA_VERSION,
    }


@pytest.fixture(scope="module")
def pretarget_inputs(contract: observer.FreezeContract) -> dict[str, Any]:
    return _synthetic_inputs(contract)


@pytest.fixture(scope="module")
def snapshot(pretarget_inputs: dict[str, Any]) -> dict[str, Any]:
    return observer.pretarget_prepare(
        target_identity=SYNTHETIC_TARGET,
        pretarget_inputs=pretarget_inputs,
    )


@pytest.fixture(scope="module")
def synthetic_outcome() -> dict[str, Any]:
    return {
        "schema_version": observer.POSTTARGET_OUTCOME_SCHEMA_VERSION,
        "target_identity": SYNTHETIC_TARGET,
        "winning_numbers": [1, 2, 3, 4, 5],
    }


def _experiments(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], snapshot["experiments"])


def _arms(experiment: dict[str, Any]) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], experiment["arms"])


@pytest.mark.parametrize("target", ["115000186", "115000185"])
def test_pretarget_rejects_target_at_or_before_boundary(
    target: str, pretarget_inputs: dict[str, Any]
) -> None:
    with pytest.raises(observer.ObserverContractError, match="TARGET_AT_OR_BELOW_FREEZE_BOUNDARY"):
        observer.pretarget_prepare(
            target_identity=target,
            pretarget_inputs=pretarget_inputs,
        )


def test_pretarget_accepts_strictly_post_boundary_target(snapshot: dict[str, Any]) -> None:
    assert snapshot["target_identity"] == SYNTHETIC_TARGET
    assert snapshot["phase"] == "PRETARGET_PREPARE"
    assert snapshot["outcome_presence_at_prepare"] == "ABSENT"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("official_outcome", {"winning_numbers": [1, 2, 3, 4, 5]}),
        ("outcome_presence", "PRESENT"),
    ],
)
def test_pretarget_rejects_any_target_outcome_field(
    field: str,
    value: object,
    pretarget_inputs: dict[str, Any],
) -> None:
    contaminated = dict(pretarget_inputs)
    contaminated[field] = value

    with pytest.raises(
        observer.ObserverContractError,
        match="TARGET_OUTCOME_PRESENT_DURING_PRETARGET",
    ):
        observer.pretarget_prepare(
            target_identity=SYNTHETIC_TARGET,
            pretarget_inputs=contaminated,
        )


@pytest.mark.parametrize("history_target", [SYNTHETIC_TARGET, "1000000000"])
def test_pretarget_rejects_current_or_later_history(
    history_target: str,
    pretarget_inputs: dict[str, Any],
) -> None:
    contaminated = copy.deepcopy(pretarget_inputs)
    cells = cast(list[dict[str, Any]], contaminated["cells"])
    history = cast(list[dict[str, Any]], cells[0]["history"])
    history[-1]["target_identity"] = history_target

    with pytest.raises(
        observer.ObserverContractError,
        match="HISTORY_TARGET_NOT_STRICTLY_BEFORE_TARGET",
    ):
        observer.pretarget_prepare(
            target_identity=SYNTHETIC_TARGET,
            pretarget_inputs=contaminated,
        )


def test_pretarget_materializes_complete_ordered_surface(snapshot: dict[str, Any]) -> None:
    experiments = _experiments(snapshot)
    expected = [
        (k, label, window)
        for k in observer.FROZEN_K_VALUES
        for label, window in observer.FROZEN_WINDOWS
    ]

    assert len(experiments) == 30
    assert [
        (experiment["k"], experiment["window_label"], experiment["window"])
        for experiment in experiments
    ] == expected
    assert all(
        [arm["arm"] for arm in _arms(experiment)] == list(observer.FROZEN_ARMS)
        for experiment in experiments
    )
    assert snapshot["surface"] == {
        "arm_record_count": 90,
        "arms": list(observer.FROZEN_ARMS),
        "experiment_count": 30,
        "k_values": list(observer.FROZEN_K_VALUES),
        "windows": [
            {"label": label, "size": window} for label, window in observer.FROZEN_WINDOWS
        ],
    }


def test_pretarget_preserves_frozen_representative_and_baseline_identities(
    snapshot: dict[str, Any], contract: observer.FreezeContract
) -> None:
    for experiment in _experiments(snapshot):
        k = cast(int, experiment["k"])
        window = cast(int, experiment["window"])
        frozen_cell = contract.cells[k]
        original, dedup, baseline = _arms(experiment)
        original_statistics = cast(list[dict[str, Any]], original["selector_statistics"])
        dedup_statistics = cast(list[dict[str, Any]], dedup["selector_statistics"])

        assert {
            tuple(cast(list[str], item["identity"])) for item in original_statistics
        } == set(frozen_cell.original_identities)
        assert {
            tuple(cast(list[str], item["identity"])) for item in dedup_statistics
        } == set(frozen_cell.representative_identities)
        assert tuple(cast(list[str], baseline["selected_strategy_identity"])) == (
            frozen_cell.baseline_by_window[window]
        )
        assert baseline["selector_statistics"] is None


def test_pretarget_snapshot_order_is_deterministic(snapshot: dict[str, Any]) -> None:
    for experiment in _experiments(snapshot):
        history = cast(list[str], experiment["history_target_identities"])
        assert history == sorted(history, key=int)
        for arm_index, arm in enumerate(_arms(experiment)):
            assert arm["arm_index"] == arm_index
            tickets = cast(list[list[int]], arm["prediction_tickets"])
            assert tickets == sorted(tickets)
            assert all(ticket == sorted(ticket) for ticket in tickets)


def test_identical_pretarget_input_produces_byte_identical_snapshot(
    pretarget_inputs: dict[str, Any], snapshot: dict[str, Any]
) -> None:
    rebuilt = observer.pretarget_prepare(
        target_identity=SYNTHETIC_TARGET,
        pretarget_inputs=pretarget_inputs,
    )

    assert observer.canonical_json_bytes(rebuilt) == observer.canonical_json_bytes(snapshot)
    assert rebuilt["snapshot_content_hash"] == observer.snapshot_content_hash(rebuilt)


def test_volatile_environment_metadata_is_excluded_from_snapshot_hash(
    monkeypatch: pytest.MonkeyPatch,
    pretarget_inputs: dict[str, Any],
    snapshot: dict[str, Any],
) -> None:
    monkeypatch.setenv("TMPDIR", "/volatile/test/location")
    monkeypatch.setenv("TZ", "Etc/GMT+12")
    monkeypatch.setenv("PWD", "/volatile/worktree")
    rebuilt = observer.pretarget_prepare(
        target_identity=SYNTHETIC_TARGET,
        pretarget_inputs=pretarget_inputs,
    )
    encoded = observer.canonical_json_bytes(rebuilt)

    assert rebuilt["snapshot_content_hash"] == snapshot["snapshot_content_hash"]
    for forbidden in (
        b'"absolute_path"',
        b'"object_address"',
        b'"pid"',
        b'"wall_clock"',
        b'"worktree_path"',
        b"/volatile/",
    ):
        assert forbidden not in encoded


def test_posttarget_rejects_missing_snapshot(synthetic_outcome: dict[str, Any]) -> None:
    with pytest.raises(observer.ObserverContractError, match="MISSING_PRETARGET_SNAPSHOT"):
        observer.posttarget_score(snapshot=None, official_outcome=synthetic_outcome)


def test_posttarget_rejects_modified_snapshot(
    snapshot: dict[str, Any], synthetic_outcome: dict[str, Any]
) -> None:
    modified = copy.deepcopy(snapshot)
    experiments = _experiments(modified)
    tickets = cast(list[list[int]], _arms(experiments[0])[0]["prediction_tickets"])
    tickets[0][0] = 39

    with pytest.raises(observer.ObserverContractError, match="SNAPSHOT_HASH_MISMATCH"):
        observer.posttarget_score(snapshot=modified, official_outcome=synthetic_outcome)


def test_posttarget_rejects_wrong_target_outcome(snapshot: dict[str, Any]) -> None:
    wrong_outcome = {
        "schema_version": observer.POSTTARGET_OUTCOME_SCHEMA_VERSION,
        "target_identity": "999999998",
        "winning_numbers": [1, 2, 3, 4, 5],
    }

    with pytest.raises(observer.ObserverContractError, match="OUTCOME_TARGET_MISMATCH"):
        observer.posttarget_score(snapshot=snapshot, official_outcome=wrong_outcome)


def test_posttarget_rejects_rule_fingerprint_mismatch_even_with_rehashed_snapshot(
    snapshot: dict[str, Any], synthetic_outcome: dict[str, Any]
) -> None:
    modified = copy.deepcopy(snapshot)
    modified["rule_fingerprint"] = "0" * 64
    modified["snapshot_content_hash"] = observer.snapshot_content_hash(modified)

    with pytest.raises(observer.ObserverContractError, match="RULE_FINGERPRINT_MISMATCH"):
        observer.posttarget_score(snapshot=modified, official_outcome=synthetic_outcome)


def test_posttarget_rejects_incomplete_experiment_surface_even_when_rehashed(
    snapshot: dict[str, Any], synthetic_outcome: dict[str, Any]
) -> None:
    modified = copy.deepcopy(snapshot)
    _experiments(modified).pop()
    modified["snapshot_content_hash"] = observer.snapshot_content_hash(modified)

    with pytest.raises(observer.ObserverContractError, match="INCOMPLETE_EXPERIMENT_SURFACE"):
        observer.posttarget_score(snapshot=modified, official_outcome=synthetic_outcome)


def _forbidden_phase_one_call(*args: object, **kwargs: object) -> None:
    raise AssertionError("POSTTARGET_SCORE called a PRETARGET-only function")


def test_posttarget_never_reruns_selector(
    monkeypatch: pytest.MonkeyPatch,
    snapshot: dict[str, Any],
    synthetic_outcome: dict[str, Any],
) -> None:
    monkeypatch.setattr(observer, "_select_strategy", _forbidden_phase_one_call)

    result = observer.posttarget_score(
        snapshot=snapshot,
        official_outcome=synthetic_outcome,
        pretarget_seal_status=observer.PRETARGET_SEAL_CONFIRMED,
    )

    assert result["score_status"] == "STRUCTURALLY_VALID_TARGET_SCORE"


def test_posttarget_never_regenerates_predictions(
    monkeypatch: pytest.MonkeyPatch,
    snapshot: dict[str, Any],
    synthetic_outcome: dict[str, Any],
) -> None:
    monkeypatch.setattr(observer, "_prediction_for_identity", _forbidden_phase_one_call)

    result = observer.posttarget_score(
        snapshot=snapshot,
        official_outcome=synthetic_outcome,
        pretarget_seal_status=observer.PRETARGET_SEAL_CONFIRMED,
    )

    assert len(cast(list[dict[str, Any]], result["experiments"])) == 30


def test_pretarget_predictions_remain_byte_identical_after_scoring(
    snapshot: dict[str, Any], synthetic_outcome: dict[str, Any]
) -> None:
    before = observer.canonical_json_bytes(snapshot)
    result = observer.posttarget_score(
        snapshot=snapshot,
        official_outcome=synthetic_outcome,
        pretarget_seal_status=observer.PRETARGET_SEAL_CONFIRMED,
    )
    after = observer.canonical_json_bytes(snapshot)

    assert before == after
    for source_experiment, score_experiment in zip(
        _experiments(snapshot),
        cast(list[dict[str, Any]], result["experiments"]),
        strict=True,
    ):
        for source_arm, score_arm in zip(
            _arms(source_experiment),
            cast(list[dict[str, Any]], score_experiment["arms"]),
            strict=True,
        ):
            assert score_arm["prediction_tickets"] == source_arm["prediction_tickets"]


def test_identical_snapshot_and_outcome_produce_identical_result(
    snapshot: dict[str, Any], synthetic_outcome: dict[str, Any]
) -> None:
    first = observer.posttarget_score(
        snapshot=snapshot,
        official_outcome=synthetic_outcome,
        pretarget_seal_status=observer.PRETARGET_SEAL_CONFIRMED,
    )
    second = observer.posttarget_score(
        snapshot=snapshot,
        official_outcome=synthetic_outcome,
        pretarget_seal_status=observer.PRETARGET_SEAL_CONFIRMED,
    )

    assert observer.canonical_json_bytes(first) == observer.canonical_json_bytes(second)
    assert first["result_content_hash"] == observer.result_content_hash(first)


def test_missed_pretarget_seal_cannot_become_valid_prospective_observation(
    snapshot: dict[str, Any], synthetic_outcome: dict[str, Any]
) -> None:
    missed = observer.posttarget_score(
        snapshot=snapshot,
        official_outcome=synthetic_outcome,
        pretarget_seal_status=observer.MISSED_PRETARGET_SEAL,
    )
    confirmed = observer.posttarget_score(
        snapshot=snapshot,
        official_outcome=synthetic_outcome,
        pretarget_seal_status=observer.PRETARGET_SEAL_CONFIRMED,
    )

    assert missed["score_status"] == "STRUCTURALLY_VALID_TARGET_SCORE"
    assert missed["prospective_observation_status"] == observer.MISSED_PRETARGET_SEAL
    assert missed["counts_as_valid_prospective_observation"] is False
    assert confirmed["prospective_observation_status"] == observer.VALID_PROSPECTIVE_OBSERVATION
    assert confirmed["counts_as_valid_prospective_observation"] is True
