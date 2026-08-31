"""Synthetic cross-contract acceptance for the T539 prospective research stack."""

from __future__ import annotations

import copy
import inspect
from collections.abc import Mapping
from typing import Any, cast

import pytest
import tools.freeze_t539_prospective_evaluation_protocol as protocol
from tools import run_t539_prospective_shadow_observer as observer

SYNTHETIC_TARGET = "999999999"
SYNTHETIC_HISTORY_START = int(SYNTHETIC_TARGET) - 750
SYNTHETIC_OUTCOME: dict[str, Any] = {
    "schema_version": observer.POSTTARGET_OUTCOME_SCHEMA_VERSION,
    "target_identity": SYNTHETIC_TARGET,
    "winning_numbers": [1, 2, 3, 4, 5],
}


def _ticket(identity_index: int, position: int) -> list[int]:
    start = (identity_index * 3 + position * 7) % 39
    return sorted(((start + offset) % 39) + 1 for offset in range(5))


def _synthetic_inputs(contract: observer.FreezeContract) -> dict[str, Any]:
    cells: list[dict[str, Any]] = []
    for k in observer.FROZEN_K_VALUES:
        frozen_cell = contract.cells[k]
        candidate_metrics: list[dict[str, Any]] = [
            {
                "identity": list(identity),
                "prize_tier_counts": [0, 0, 0, 1],
                "success": True,
                "winning_ticket_count": 1,
            }
            for identity in frozen_cell.original_identities
        ]
        history: list[dict[str, Any]] = [
            {
                "candidate_metrics": candidate_metrics,
                "target_identity": str(SYNTHETIC_HISTORY_START + offset),
            }
            for offset in range(750)
        ]
        predictions: list[dict[str, Any]] = [
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
        "authority_identity": "SYNTHETIC_T539_STACK_INTEGRATION_R1",
        "cells": cells,
        "outcome_presence": "ABSENT",
        "schema_version": observer.PRETARGET_INPUT_SCHEMA_VERSION,
    }


def _experiments(value: Mapping[str, Any]) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], value["experiments"])


def _arms(experiment: Mapping[str, Any]) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], experiment["arms"])


def _protocol_experiments(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    surface = cast(dict[str, Any], manifest["frozen_surface"])
    return cast(list[dict[str, Any]], surface["experiments"])


def _metadata(
    snapshot: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    sealed_before_outcome: bool,
) -> protocol.ProspectiveMetadata:
    return protocol.ProspectiveMetadata(
        target_identity=cast(str, snapshot["target_identity"]),
        pretarget_snapshot_exists=True,
        pretarget_snapshot_sealed_before_outcome=sealed_before_outcome,
        pretarget_snapshot_valid=True,
        snapshot_rule_fingerprint=cast(str, snapshot["rule_fingerprint"]),
        snapshot_target_identity=cast(str, snapshot["target_identity"]),
        outcome_authority_available=True,
        outcome_target_identity=cast(str, result["target_identity"]),
        complete_experiment_ids=tuple(
            cast(str, experiment["experiment_id"])
            for experiment in _experiments(snapshot)
        ),
    )


def _all_mapping_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        for raw_key, child in mapping.items():
            keys.add(str(raw_key))
            keys.update(_all_mapping_keys(child))
    elif isinstance(value, list):
        for child in cast(list[object], value):
            keys.update(_all_mapping_keys(child))
    return keys


@pytest.fixture(scope="module")
def protocol_manifest() -> dict[str, Any]:
    return protocol.build_protocol(protocol.load_frozen_authority())


@pytest.fixture(scope="module")
def freeze_contract() -> observer.FreezeContract:
    return observer.load_freeze_contract()


@pytest.fixture(scope="module")
def pretarget_inputs(freeze_contract: observer.FreezeContract) -> dict[str, Any]:
    return _synthetic_inputs(freeze_contract)


@pytest.fixture(scope="module")
def snapshot(pretarget_inputs: dict[str, Any]) -> dict[str, Any]:
    return observer.pretarget_prepare(
        target_identity=SYNTHETIC_TARGET,
        pretarget_inputs=pretarget_inputs,
    )


@pytest.fixture(scope="module")
def valid_result(snapshot: dict[str, Any]) -> dict[str, Any]:
    return observer.posttarget_score(
        snapshot=snapshot,
        official_outcome=SYNTHETIC_OUTCOME,
        pretarget_seal_status=observer.PRETARGET_SEAL_CONFIRMED,
    )


def test_protocol_and_harness_share_exact_authority_and_complete_surface(
    protocol_manifest: dict[str, Any],
    freeze_contract: observer.FreezeContract,
    snapshot: dict[str, Any],
) -> None:
    authority = cast(dict[str, Any], protocol_manifest["authority"])
    assert protocol.EXPECTED_FREEZE_SHA256 == observer.EXPECTED_FREEZE_SHA256
    assert protocol.EXPECTED_RULE_FINGERPRINT == observer.EXPECTED_RULE_FINGERPRINT
    assert authority["freeze_sha256"] == freeze_contract.manifest_sha256
    assert authority["rule_fingerprint"] == freeze_contract.rule_fingerprint

    protocol_experiments = _protocol_experiments(protocol_manifest)
    snapshot_experiments = _experiments(snapshot)
    assert len(protocol_experiments) == len(snapshot_experiments) == 30
    assert snapshot["surface"] == {
        "arm_record_count": 90,
        "arms": list(observer.FROZEN_ARMS),
        "experiment_count": 30,
        "k_values": list(observer.FROZEN_K_VALUES),
        "windows": [
            {"label": label, "size": size} for label, size in observer.FROZEN_WINDOWS
        ],
    }

    expected_arm_ids = [arm_id for arm_id, _ in protocol.ARM_BINDINGS]
    expected_frozen_arms = [frozen_arm for _, frozen_arm in protocol.ARM_BINDINGS]
    for protocol_experiment, snapshot_experiment in zip(
        protocol_experiments,
        snapshot_experiments,
        strict=True,
    ):
        protocol_window = cast(dict[str, Any], protocol_experiment["window"])
        assert snapshot_experiment["experiment_id"] == protocol_experiment["experiment_id"]
        assert snapshot_experiment["k"] == protocol_experiment["native_ticket_count"]
        assert snapshot_experiment["window_label"] == protocol_window["label"]
        assert protocol_experiment["arm_ids"] == expected_arm_ids
        assert [arm["arm"] for arm in _arms(snapshot_experiment)] == expected_frozen_arms


def test_pretarget_interface_cannot_receive_target_outcome(
    pretarget_inputs: dict[str, Any],
) -> None:
    parameters = inspect.signature(observer.pretarget_prepare).parameters
    assert set(parameters) == {"target_identity", "pretarget_inputs", "freeze_path"}
    assert "official_outcome" not in parameters

    contaminated = dict(pretarget_inputs)
    contaminated["official_outcome"] = SYNTHETIC_OUTCOME
    with pytest.raises(
        observer.ObserverContractError,
        match="TARGET_OUTCOME_PRESENT_DURING_PRETARGET",
    ):
        observer.pretarget_prepare(
            target_identity=SYNTHETIC_TARGET,
            pretarget_inputs=contaminated,
        )


def _forbidden_pretarget_call(*args: object, **kwargs: object) -> None:
    raise AssertionError("POSTTARGET_SCORE called a PRETARGET-only function")


def test_posttarget_requires_and_preserves_one_untampered_sealed_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    snapshot: dict[str, Any],
) -> None:
    with pytest.raises(observer.ObserverContractError, match="MISSING_PRETARGET_SNAPSHOT"):
        observer.posttarget_score(snapshot=None, official_outcome=SYNTHETIC_OUTCOME)

    before = observer.canonical_json_bytes(snapshot)
    monkeypatch.setattr(observer, "_select_strategy", _forbidden_pretarget_call)
    monkeypatch.setattr(observer, "_prediction_for_identity", _forbidden_pretarget_call)
    result = observer.posttarget_score(
        snapshot=snapshot,
        official_outcome=SYNTHETIC_OUTCOME,
        pretarget_seal_status=observer.PRETARGET_SEAL_CONFIRMED,
    )
    assert observer.canonical_json_bytes(snapshot) == before
    assert result["pretarget_snapshot_content_hash"] == snapshot["snapshot_content_hash"]
    for source_experiment, scored_experiment in zip(
        _experiments(snapshot),
        _experiments(result),
        strict=True,
    ):
        for source_arm, scored_arm in zip(
            _arms(source_experiment),
            _arms(scored_experiment),
            strict=True,
        ):
            assert scored_arm["prediction_tickets"] == source_arm["prediction_tickets"]

    tampered = copy.deepcopy(snapshot)
    tampered_tickets = cast(
        list[list[int]],
        _arms(_experiments(tampered)[0])[0]["prediction_tickets"],
    )
    tampered_tickets[0][0] = 39
    with pytest.raises(observer.ObserverContractError, match="SNAPSHOT_HASH_MISMATCH"):
        observer.posttarget_score(snapshot=tampered, official_outcome=SYNTHETIC_OUTCOME)


def test_missed_pretarget_seal_never_enters_protocol_cohort(
    protocol_manifest: dict[str, Any],
    snapshot: dict[str, Any],
) -> None:
    missed = observer.posttarget_score(
        snapshot=snapshot,
        official_outcome=SYNTHETIC_OUTCOME,
        pretarget_seal_status=observer.MISSED_PRETARGET_SEAL,
    )
    assert missed["counts_as_valid_prospective_observation"] is False
    assert missed["prospective_observation_status"] == observer.MISSED_PRETARGET_SEAL
    assert protocol.classify_prospective_metadata(
        _metadata(snapshot, missed, sealed_before_outcome=False)
    ) == "MISSED_PRETARGET_SEAL"

    inclusion = cast(dict[str, Any], protocol_manifest["prospective_inclusion"])
    missed_contract = cast(dict[str, Any], inclusion["missed_pretarget_seal"])
    assert missed_contract["backfill"] == "FORBIDDEN"


def test_valid_synthetic_result_maps_only_to_b_minus_a_and_b_minus_c(
    protocol_manifest: dict[str, Any],
    snapshot: dict[str, Any],
    valid_result: dict[str, Any],
) -> None:
    assert protocol.classify_prospective_metadata(
        _metadata(snapshot, valid_result, sealed_before_outcome=True)
    ) == "VALID_PROSPECTIVE"

    accumulation = cast(dict[str, Any], protocol_manifest["accumulation_contract"])
    required_fields = cast(list[str], accumulation["raw_target_record_required_fields"])
    measurement = cast(dict[str, Any], protocol_manifest["measurement_contract"])
    comparisons = cast(list[dict[str, Any]], measurement["paired_comparisons"])
    arm_id_by_frozen: dict[str, str] = {
        frozen_arm: arm_id for arm_id, frozen_arm in protocol.ARM_BINDINGS
    }
    raw_records: list[dict[str, object]] = []
    paired_records: dict[str, dict[str, tuple[int, int]]] = {}

    for scored_experiment in _experiments(valid_result):
        indicators = {
            arm_id_by_frozen[cast(str, arm["arm"])]: int(
                cast(bool, arm["official_any_prize_success"])
            )
            for arm in _arms(scored_experiment)
        }
        record: dict[str, object] = {
            "target_identity": valid_result["target_identity"],
            "pretarget_snapshot_identity": snapshot["snapshot_content_hash"],
            "snapshot_rule_fingerprint": snapshot["rule_fingerprint"],
            "outcome_authority_identity": valid_result["official_outcome_sha256"],
            "experiment_id": scored_experiment["experiment_id"],
            "A_success_indicator": indicators["A"],
            "B_success_indicator": indicators["B"],
            "C_success_indicator": indicators["C"],
        }
        assert list(record) == required_fields
        raw_records.append(record)

        pairwise: dict[str, tuple[int, int]] = {}
        for comparison in comparisons:
            comparison_id = cast(str, comparison["comparison_id"])
            minuend = cast(str, comparison["minuend_arm_id"])
            subtrahend = cast(str, comparison["subtrahend_arm_id"])
            pairwise[comparison_id] = (indicators[minuend] - indicators[subtrahend], 1)
        assert tuple(pairwise) == protocol.COMPARISON_IDS
        paired_records[cast(str, scored_experiment["experiment_id"])] = pairwise

    assert len(raw_records) == len(paired_records) == 30
    assert set(paired_records) == set(protocol.EXPECTED_EXPERIMENT_IDS)
    assert measurement["aggregation_scope"] == "ONE_K_X_WINDOW_EXPERIMENT_AT_A_TIME"

    selection_guards = cast(dict[str, Any], protocol_manifest["selection_guards"])
    guardrails = cast(dict[str, Any], protocol_manifest["inferential_guardrails"])
    assert selection_guards["cross_k_aggregation"] == "FORBIDDEN"
    assert selection_guards["cross_window_aggregation"] == "FORBIDDEN"
    assert guardrails["composite_score"] == "NOT_DEFINED"
    assert guardrails["best_window_selection"] == "FORBIDDEN"
    assert guardrails["early_stopping_winner_rule"] == "FORBIDDEN"
    forbidden_result_keys = {
        "best_window_selection",
        "composite_score",
        "cross_k_aggregation",
        "cross_window_aggregation",
        "promotion_rule",
        "significance_rule",
        "weighted_score",
        "winner_selection",
    }
    assert forbidden_result_keys.isdisjoint(_all_mapping_keys(valid_result))

    integrity = cast(dict[str, Any], protocol_manifest["integrity"])
    result_authority = cast(dict[str, Any], valid_result["input_authority"])
    assert integrity["future_outcome_access"] == "NO"
    assert integrity["database_access"] == "NO"
    assert integrity["prospective_observations"] == 0
    assert snapshot["target_identity"] == SYNTHETIC_TARGET
    assert valid_result["official_outcome"] == SYNTHETIC_OUTCOME
    assert result_authority["identity"] == "SYNTHETIC_T539_STACK_INTEGRATION_R1"
