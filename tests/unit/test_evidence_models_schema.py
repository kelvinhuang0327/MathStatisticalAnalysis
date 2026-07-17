"""Structural (Pydantic layer 2) adversarial tests for evidence contract models.

These tests never touch the filesystem and never call
``lottolab.evidence.validator``: they only exercise field types, regexes,
enums, required keys, and strictly local model invariants. Declared hash
fields use well-formed placeholder hex strings throughout, since hash
*correctness* is a semantic-validator concern tested in
``test_evidence_validator.py``.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

import pytest
from pydantic import ValidationError

from lottolab.evidence.models import (
    ComparabilityDimensions,
    DatasetSnapshot,
    MetricDefinition,
    RankingPolicy,
    RuleParameters,
    StrategyEvaluationEvidence,
)

HASH_A = "a" * 64
HASH_B = "b" * 64
OID_A = "c" * 40


def _rule_parameters(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "main_number_count": 6,
        "main_number_min": 1,
        "main_number_max": 49,
        "main_numbers_unique": True,
        "special_number_count": 1,
        "special_number_min": 1,
        "special_number_max": 49,
        "special_numbers_unique": True,
        "main_special_overlap_allowed": False,
        "rule_contract_version": "v1",
        "rule_parameters_sha256": HASH_A,
    }
    base.update(overrides)
    return base


def _dataset_snapshot_dict() -> dict[str, Any]:
    return {
        "schema_id": "lottolab.evidence.dataset_snapshot",
        "schema_version": "1.0.0",
        "dataset_id": "SYNTHETIC_TEST_DATASET",
        "dataset_version": "1.0.0",
        "lottery_type": "BIG_LOTTO",
        "rule_binding": _rule_parameters(),
        "source_provenance": {"kind": "SYNTHETIC", "declared_description": "test"},
        "draws": [
            {
                "draw_id": "D0",
                "draw_sequence": 0,
                "draw_date": "2020-01-01",
                "main_numbers": [1, 2, 3, 4, 5, 6],
                "special_numbers": [7],
            },
            {
                "draw_id": "D1",
                "draw_sequence": 1,
                "draw_date": "2020-01-02",
                "main_numbers": [2, 3, 4, 5, 6, 7],
                "special_numbers": [8],
            },
        ],
        "dataset_sha256": HASH_A,
    }


def _evidence_dict() -> dict[str, Any]:
    return {
        "schema_id": "lottolab.evidence.strategy_evaluation_evidence",
        "schema_version": "1.0.0",
        "artifact_id": "artifact-1",
        "evidence_status": "DRAFT",
        "produced_at": "2026-01-01T00:00:00Z",
        "producer_name": "tester",
        "artifact_content_sha256": HASH_A,
        "strategy_id": "strat-1",
        "strategy_version": "v1",
        "method_id": "method-1",
        "method_version": "v1",
        "method_source_git_oid": OID_A,
        "feature_version": "v1",
        "feature_definition_path": "contracts/evidence/metric_definitions/d3.json",
        "feature_definition_sha256": HASH_A,
        "parameters": {"window": 1},
        "parameters_sha256": HASH_A,
        "dataset_reference": {
            "dataset_id": "SYNTHETIC_TEST_DATASET",
            "dataset_version": "1.0.0",
            "dataset_sha256": HASH_A,
            "lottery_type": "BIG_LOTTO",
            "draw_count": 2,
            "first_draw": {"draw_id": "D0", "draw_sequence": 0, "draw_date": "2020-01-01"},
            "last_draw": {"draw_id": "D1", "draw_sequence": 1, "draw_date": "2020-01-02"},
        },
        "rule_parameters": _rule_parameters(),
        "evaluation_mode": "EX_ANTE",
        "evaluation_protocol": "WALK_FORWARD",
        "evaluation_windows": {
            "evaluation_window": {"start_sequence": 1, "end_sequence": 1},
            "training_window": {"start_sequence": 0, "end_sequence": 0},
            "parameter_selection_mode": "FIXED",
            "parameter_selection_window": {"start_sequence": 0, "end_sequence": 0},
            "minimum_history": 1,
            "missing_draw_policy": "STRICT_NONE_TOLERATED",
            "duplicate_draw_policy": "STRICT_NONE_TOLERATED",
            "maximum_data_cutoff": {"draw_id": "D0", "draw_sequence": 0, "draw_date": "2020-01-01"},
            "walk_forward_cutoff_lag": 1,
        },
        "records": [
            {
                "target": {"draw_id": "D1", "draw_sequence": 1, "draw_date": "2020-01-02"},
                "cutoff": {"draw_id": "D0", "draw_sequence": 0, "draw_date": "2020-01-01"},
                "tickets": [
                    {
                        "ticket_id": "T0",
                        "main_numbers": [1, 2, 3, 4, 5, 6],
                        "special_numbers": [7],
                        "main_hit_count": 0,
                        "special_hit": False,
                    }
                ],
                "actual_main_numbers": [2, 3, 4, 5, 6, 7],
                "actual_special_numbers": [8],
                "outcome_source": "DATASET_SNAPSHOT",
                "record_sha256": HASH_A,
            }
        ],
        "metric_results": [],
    }


def _metric_definition_dict(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_id": "lottolab.evidence.metric_definition",
        "schema_version": "1.0.0",
        "metric_id": "HIT_RATE_MAIN",
        "metric_version": "v1",
        "direction": "HIGHER_IS_BETTER",
        "unit": "RATIO",
        "aggregation": "MEAN",
        "sample_unit": "TICKETS",
        "decimal_scale": 4,
        "rounding_mode": "ROUND_HALF_EVEN",
        "formula_status": "DEFINED",
        "definition_prose": "test",
    }
    base.update(overrides)
    return base


def _ranking_policy_dict(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_id": "lottolab.evidence.ranking_policy",
        "schema_version": "1.0.0",
        "policy_id": "SYNTHETIC_POLICY",
        "policy_version": "v1",
        "declared_status": "DRAFT",
        "primary_metric_id": "HIT_RATE_MAIN",
        "primary_metric_version": "v1",
        "primary_metric_definition_sha256": HASH_A,
        "minimum_sample_size": 1,
        "required_evidence_trust": "REGISTERED_CANONICAL",
        "eligible_evaluation_modes": ["EX_ANTE"],
        "required_lottery_type": "BIG_LOTTO",
        "candidate_count_policy": "ALLOW_ANY",
        "parameter_policy": "PINNED_HASH",
        "comparability_dimensions": {
            "shared_environment": [
                "lottery_type",
                "dataset_sha256",
                "evaluation_mode",
                "evaluation_protocol",
                "evaluation_window",
                "metric_identity",
                "sample_unit",
                "candidate_count_conformance",
            ],
            "per_strategy_identity": [
                "strategy_identity",
                "method_identity",
                "feature_version",
                "parameters_sha256",
            ],
        },
        "tie_breakers": ["primary_metric_value", "strategy_id"],
        "missing_evidence_behavior": "TREAT_AS_INELIGIBLE",
        "ineligibility_reason_codes": ["NOT_REGISTERED_CANONICAL"],
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------------
# Baselines must actually be valid
# --------------------------------------------------------------------------


def test_baselines_are_valid():
    DatasetSnapshot.model_validate(_dataset_snapshot_dict())
    StrategyEvaluationEvidence.model_validate(_evidence_dict())
    MetricDefinition.model_validate(_metric_definition_dict())
    RankingPolicy.model_validate(_ranking_policy_dict())


# --------------------------------------------------------------------------
# Closed-schema (extra="forbid") rejection
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("model", "make_dict"),
    [
        (DatasetSnapshot, _dataset_snapshot_dict),
        (StrategyEvaluationEvidence, _evidence_dict),
        (MetricDefinition, _metric_definition_dict),
        (RankingPolicy, _ranking_policy_dict),
    ],
)
def test_unknown_top_level_key_rejected(
    model: type[DatasetSnapshot | StrategyEvaluationEvidence | MetricDefinition | RankingPolicy],
    make_dict: Callable[[], dict[str, Any]],
) -> None:
    document = make_dict()
    document["unexpected_extra_field"] = "nope"
    with pytest.raises(ValidationError):
        model.model_validate(document)


def test_policy_direction_override_rejected():
    document = _ranking_policy_dict()
    document["metric_direction_override"] = "HIGHER_IS_BETTER"
    with pytest.raises(ValidationError):
        RankingPolicy.model_validate(document)


def test_tie_breakers_without_final_strategy_id_rejected():
    document = _ranking_policy_dict(tie_breakers=["strategy_id", "primary_metric_value"])
    with pytest.raises(ValidationError):
        RankingPolicy.model_validate(document)


def test_comparability_dimensions_cannot_be_redefined():
    document = _ranking_policy_dict()
    document["comparability_dimensions"]["shared_environment"] = ["lottery_type"]
    with pytest.raises(ValidationError):
        RankingPolicy.model_validate(document)


# --------------------------------------------------------------------------
# Hashes: Git OID / SHA-256 field-type confusion
# --------------------------------------------------------------------------


def test_git_oid_in_sha256_field_rejected():
    document = _evidence_dict()
    document["artifact_content_sha256"] = OID_A  # 40 hex chars, not 64
    with pytest.raises(ValidationError):
        StrategyEvaluationEvidence.model_validate(document)


def test_sha256_in_git_oid_field_rejected():
    document = _evidence_dict()
    document["method_source_git_oid"] = HASH_A  # 64 hex chars, not 40
    with pytest.raises(ValidationError):
        StrategyEvaluationEvidence.model_validate(document)


# --------------------------------------------------------------------------
# Dataset: rule parameter ranges, provenance kind
# --------------------------------------------------------------------------


def test_rule_parameters_inverted_range_rejected():
    with pytest.raises(ValidationError):
        RuleParameters.model_validate(_rule_parameters(main_number_min=50, main_number_max=1))


def test_rule_parameters_unique_count_exceeding_capacity_rejected():
    with pytest.raises(ValidationError):
        RuleParameters.model_validate(
            _rule_parameters(main_number_count=10, main_number_min=1, main_number_max=5)
        )


def test_dataset_provenance_local_committed_file_requires_fields():
    document = _dataset_snapshot_dict()
    document["source_provenance"] = {"kind": "LOCAL_COMMITTED_FILE"}
    with pytest.raises(ValidationError):
        DatasetSnapshot.model_validate(document)


def test_dataset_provenance_synthetic_forbids_local_fields():
    document = _dataset_snapshot_dict()
    document["source_provenance"] = {
        "kind": "SYNTHETIC",
        "source_definition_path": "contracts/evidence/metric_definitions/d3.json",
        "source_git_oid": OID_A,
        "source_file_sha256": HASH_A,
    }
    with pytest.raises(ValidationError):
        DatasetSnapshot.model_validate(document)


def test_dataset_id_synthetic_prefix_required_for_synthetic_provenance():
    document = _dataset_snapshot_dict()
    document["dataset_id"] = "NOT_SYNTHETIC_PREFIXED"
    with pytest.raises(ValidationError):
        DatasetSnapshot.model_validate(document)


# --------------------------------------------------------------------------
# Evaluation protocol / window shape
# --------------------------------------------------------------------------


def test_walk_forward_missing_cutoff_lag_rejected():
    document = _evidence_dict()
    del document["evaluation_windows"]["walk_forward_cutoff_lag"]
    with pytest.raises(ValidationError):
        StrategyEvaluationEvidence.model_validate(document)


def test_one_shot_with_walk_forward_lag_rejected():
    document = _evidence_dict()
    document["evaluation_protocol"] = "ONE_SHOT"
    document["evaluation_windows"]["one_shot_cutoff"] = {
        "draw_id": "D0",
        "draw_sequence": 0,
        "draw_date": "2020-01-01",
    }
    # walk_forward_cutoff_lag is still set from the WALK_FORWARD baseline
    with pytest.raises(ValidationError):
        StrategyEvaluationEvidence.model_validate(document)


def test_per_step_refit_under_one_shot_rejected():
    document = _evidence_dict()
    document["evaluation_protocol"] = "ONE_SHOT"
    windows = document["evaluation_windows"]
    del windows["walk_forward_cutoff_lag"]
    windows["one_shot_cutoff"] = {"draw_id": "D0", "draw_sequence": 0, "draw_date": "2020-01-01"}
    windows["parameter_selection_mode"] = "PER_STEP_REFIT"
    del windows["parameter_selection_window"]
    with pytest.raises(ValidationError):
        StrategyEvaluationEvidence.model_validate(document)


def test_fixed_parameter_selection_requires_window():
    document = _evidence_dict()
    del document["evaluation_windows"]["parameter_selection_window"]
    with pytest.raises(ValidationError):
        StrategyEvaluationEvidence.model_validate(document)


def test_sequence_window_inverted_rejected():
    document = _evidence_dict()
    document["evaluation_windows"]["evaluation_window"] = {"start_sequence": 5, "end_sequence": 1}
    with pytest.raises(ValidationError):
        StrategyEvaluationEvidence.model_validate(document)


def test_evidence_synthetic_status_requires_synthetic_artifact_id_prefix():
    document = _evidence_dict()
    document["evidence_status"] = "SYNTHETIC_TEST_ONLY"
    with pytest.raises(ValidationError):
        StrategyEvaluationEvidence.model_validate(document)


# --------------------------------------------------------------------------
# Metrics: decimal-string shape, VALUE_PRESENT/NOT_COMPUTABLE, D3 direction
# --------------------------------------------------------------------------


def _evidence_with_metric_result(**overrides: object) -> dict[str, Any]:
    document = _evidence_dict()
    result: dict[str, Any] = {
        "metric_id": "HIT_RATE_MAIN",
        "metric_version": "v1",
        "metric_definition_path": (
            "tests/fixtures/evidence/synthetic/metric_definition_hit_rate.json"
        ),
        "metric_definition_sha256": HASH_A,
        "sample_size": 1,
        "sample_unit": "TICKETS",
        "aggregation": "MEAN",
        "value_status": "VALUE_PRESENT",
        "value": "0.5000",
        "verification_state": "DECLARED_NOT_RECOMPUTED",
    }
    result.update(overrides)
    document["metric_results"] = [result]
    return document


@pytest.mark.parametrize(
    "bad_value",
    ["+0.5000", "00.5000", "1e2", "-0.0000"],
    ids=["plus_sign", "leading_zero", "exponent", "negative_zero"],
)
def test_metric_value_decimal_shape_rejected(bad_value: str) -> None:
    document = _evidence_with_metric_result(value=bad_value)
    with pytest.raises(ValidationError):
        StrategyEvaluationEvidence.model_validate(document)


def test_metric_value_present_requires_value():
    document = _evidence_with_metric_result()
    del document["metric_results"][0]["value"]
    with pytest.raises(ValidationError):
        StrategyEvaluationEvidence.model_validate(document)


def test_metric_value_present_forbids_reason_code():
    document = _evidence_with_metric_result(reason_code="SOME_REASON")
    with pytest.raises(ValidationError):
        StrategyEvaluationEvidence.model_validate(document)


def test_metric_not_computable_requires_reason_code():
    document = _evidence_with_metric_result(value_status="NOT_COMPUTABLE")
    del document["metric_results"][0]["value"]
    with pytest.raises(ValidationError):
        StrategyEvaluationEvidence.model_validate(document)


def test_metric_not_computable_forbids_value():
    document = _evidence_with_metric_result(value_status="NOT_COMPUTABLE")
    with pytest.raises(ValidationError):
        StrategyEvaluationEvidence.model_validate(document)


def test_reserved_unavailable_metric_must_be_descriptive_only():
    with pytest.raises(ValidationError):
        MetricDefinition.model_validate(
            _metric_definition_dict(
                formula_status="RESERVED_UNAVAILABLE", direction="HIGHER_IS_BETTER"
            )
        )


def test_decimal_scale_out_of_bounds_rejected():
    with pytest.raises(ValidationError):
        MetricDefinition.model_validate(_metric_definition_dict(decimal_scale=13))


def test_ticket_and_draw_arrays_reject_empty():
    document = _dataset_snapshot_dict()
    document["draws"] = []
    with pytest.raises(ValidationError):
        DatasetSnapshot.model_validate(document)

    evidence = _evidence_dict()
    evidence["records"][0]["tickets"] = []
    with pytest.raises(ValidationError):
        StrategyEvaluationEvidence.model_validate(evidence)


def test_comparability_dimensions_helper_validates_standalone():
    ComparabilityDimensions.model_validate(_ranking_policy_dict()["comparability_dimensions"])
    with pytest.raises(ValidationError):
        ComparabilityDimensions.model_validate(
            {"shared_environment": [], "per_strategy_identity": []}
        )


def test_deepcopy_of_valid_documents_still_valid():
    # guards against a helper accidentally sharing mutable state across tests
    DatasetSnapshot.model_validate(copy.deepcopy(_dataset_snapshot_dict()))
    StrategyEvaluationEvidence.model_validate(copy.deepcopy(_evidence_dict()))
