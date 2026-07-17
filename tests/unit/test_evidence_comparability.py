"""Adversarial tests for cross-artifact comparability (Contract Part 9).

``check_comparability`` takes already-classified ``(evidence, trust)`` pairs,
so these tests use well-formed placeholder hashes throughout (format-valid,
not cryptographically recomputed) — hash *correctness* is exercised in
``test_evidence_validator.py``. Trust is passed in explicitly to isolate the
comparability algorithm from trust classification itself.
"""

from __future__ import annotations

from typing import Any

from lottolab.evidence import comparability
from lottolab.evidence.models import (
    PER_STRATEGY_IDENTITY_DIMENSIONS,
    SHARED_ENVIRONMENT_DIMENSIONS,
    EvidenceTrustClass,
    RankingPolicy,
    StrategyEvaluationEvidence,
)

HASH_A = "a" * 64
HASH_B = "b" * 64
OID_A = "c" * 40


def _draw_ref(draw_id: str, seq: int, date: str) -> dict[str, Any]:
    return {"draw_id": draw_id, "draw_sequence": seq, "draw_date": date}


def _rule_parameters() -> dict[str, Any]:
    return {
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


def _evidence(
    artifact_id: str,
    strategy_id: str,
    strategy_version: str = "v1",
    *,
    mode: str = "EX_ANTE",
    protocol: str = "WALK_FORWARD",
    dataset_sha256: str = HASH_A,
    metric_id: str = "HIT_RATE_MAIN",
    metric_version: str = "v1",
    metric_definition_sha256: str = HASH_A,
    parameters_sha256: str = HASH_A,
    sample_size: int = 1,
) -> StrategyEvaluationEvidence:
    windows: dict[str, Any] = {
        "evaluation_window": {"start_sequence": 1, "end_sequence": 1},
        "training_window": {"start_sequence": 0, "end_sequence": 0},
        "parameter_selection_mode": "FIXED",
        "parameter_selection_window": {"start_sequence": 0, "end_sequence": 0},
        "minimum_history": 1,
        "missing_draw_policy": "STRICT_NONE_TOLERATED",
        "duplicate_draw_policy": "STRICT_NONE_TOLERATED",
        "maximum_data_cutoff": _draw_ref("D0", 0, "2020-01-01"),
    }
    if protocol == "WALK_FORWARD":
        windows["walk_forward_cutoff_lag"] = 1
    else:
        windows["one_shot_cutoff"] = _draw_ref("D0", 0, "2020-01-01")

    document = {
        "schema_id": "lottolab.evidence.strategy_evaluation_evidence",
        "schema_version": "1.0.0",
        "artifact_id": artifact_id,
        "evidence_status": "DRAFT",
        "produced_at": "2026-01-01T00:00:00Z",
        "producer_name": "comparability-test",
        "artifact_content_sha256": HASH_A,
        "strategy_id": strategy_id,
        "strategy_version": strategy_version,
        "method_id": "method-1",
        "method_version": "v1",
        "method_source_git_oid": OID_A,
        "feature_version": "v1",
        "feature_definition_path": "contracts/evidence/metric_definitions/d3.json",
        "feature_definition_sha256": HASH_A,
        "parameters": {"window": 1},
        "parameters_sha256": parameters_sha256,
        "dataset_reference": {
            "dataset_id": "SYNTHETIC_COMPARABILITY_TEST",
            "dataset_version": "1.0.0",
            "dataset_sha256": dataset_sha256,
            "lottery_type": "BIG_LOTTO",
            "draw_count": 2,
            "first_draw": _draw_ref("D0", 0, "2020-01-01"),
            "last_draw": _draw_ref("D1", 1, "2020-01-02"),
        },
        "rule_parameters": _rule_parameters(),
        "evaluation_mode": mode,
        "evaluation_protocol": protocol,
        "evaluation_windows": windows,
        "records": [
            {
                "target": _draw_ref("D1", 1, "2020-01-02"),
                "cutoff": _draw_ref("D0", 0, "2020-01-01"),
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
        "metric_results": [
            {
                "metric_id": metric_id,
                "metric_version": metric_version,
                "metric_definition_path": "contracts/evidence/metric_definitions/d3.json",
                "metric_definition_sha256": metric_definition_sha256,
                "sample_size": sample_size,
                "sample_unit": "TICKETS",
                "aggregation": "MEAN",
                "value_status": "VALUE_PRESENT",
                "value": "0.5000",
                "verification_state": "DECLARED_NOT_RECOMPUTED",
            }
        ],
    }
    return StrategyEvaluationEvidence.model_validate(document)


def _policy(**overrides: object) -> RankingPolicy:
    document: dict[str, Any] = {
        "schema_id": "lottolab.evidence.ranking_policy",
        "schema_version": "1.0.0",
        "policy_id": "SYNTHETIC_COMPARABILITY_POLICY",
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
            "shared_environment": list(SHARED_ENVIRONMENT_DIMENSIONS),
            "per_strategy_identity": list(PER_STRATEGY_IDENTITY_DIMENSIONS),
        },
        "tie_breakers": ["strategy_id"],
        "missing_evidence_behavior": "TREAT_AS_INELIGIBLE",
        "ineligibility_reason_codes": ["NOT_REGISTERED_CANONICAL"],
    }
    document.update(overrides)
    return RankingPolicy.model_validate(document)


def _by_id(
    results: tuple[comparability.ComparabilityResult, ...],
) -> dict[str, comparability.ComparabilityResult]:
    return {result.artifact_id: result for result in results}


CANONICAL = EvidenceTrustClass.REGISTERED_CANONICAL


def test_untrusted_evidence_is_never_eligible():
    policy = _policy()
    evidence = _evidence("A1", "strat-a")
    results = comparability.check_comparability(
        [(evidence, EvidenceTrustClass.UNTRUSTED_DECLARED)], policy
    )
    result = _by_id(results)["A1"]
    assert result.eligible is False
    assert "NOT_REGISTERED_CANONICAL" in result.reason_codes


def test_ex_ante_and_replay_mixture_rejected():
    policy = _policy(eligible_evaluation_modes=["EX_ANTE", "HISTORICAL_REPLAY"])
    ex_ante = _evidence("A1", "strat-a", mode="EX_ANTE")
    replay = _evidence("A2", "strat-b", mode="HISTORICAL_REPLAY")
    results = _by_id(
        comparability.check_comparability([(ex_ante, CANONICAL), (replay, CANONICAL)], policy)
    )
    assert results["A1"].eligible is False
    assert results["A2"].eligible is False
    assert "SHARED_ENVIRONMENT_MISMATCH" in results["A1"].reason_codes
    assert "SHARED_ENVIRONMENT_MISMATCH" in results["A2"].reason_codes


def test_dataset_hash_mismatch_rejected():
    policy = _policy()
    a = _evidence("A1", "strat-a", dataset_sha256=HASH_A)
    b = _evidence("A2", "strat-b", dataset_sha256=HASH_B)
    results = _by_id(comparability.check_comparability([(a, CANONICAL), (b, CANONICAL)], policy))
    assert results["A1"].eligible is False
    assert results["A2"].eligible is False
    assert "SHARED_ENVIRONMENT_MISMATCH" in results["A1"].reason_codes


def test_metric_definition_hash_mismatch_rejected():
    policy = _policy()
    a = _evidence("A1", "strat-a", metric_definition_sha256=HASH_A)
    b = _evidence("A2", "strat-b", metric_definition_sha256=HASH_B)
    results = _by_id(comparability.check_comparability([(a, CANONICAL), (b, CANONICAL)], policy))
    assert results["A1"].eligible is False
    assert results["A2"].eligible is False
    assert "SHARED_ENVIRONMENT_MISMATCH" in results["A1"].reason_codes


def test_duplicate_strategy_identity_rejected_for_all_carriers():
    policy = _policy()
    a = _evidence("A1", "strat-a", strategy_version="v1", parameters_sha256=HASH_A)
    b = _evidence("A2", "strat-a", strategy_version="v1", parameters_sha256=HASH_A)
    results = _by_id(comparability.check_comparability([(a, CANONICAL), (b, CANONICAL)], policy))
    assert results["A1"].eligible is False
    assert results["A2"].eligible is False
    assert "DUPLICATE_STRATEGY_IDENTITY" in results["A1"].reason_codes
    assert "DUPLICATE_STRATEGY_IDENTITY" in results["A2"].reason_codes


def test_same_strategy_identity_different_parameters_sha256_rejected():
    policy = _policy()
    a = _evidence("A1", "strat-a", strategy_version="v1", parameters_sha256=HASH_A)
    b = _evidence("A2", "strat-a", strategy_version="v1", parameters_sha256=HASH_B)
    results = _by_id(comparability.check_comparability([(a, CANONICAL), (b, CANONICAL)], policy))
    assert results["A1"].eligible is False
    assert results["A2"].eligible is False
    assert "DUPLICATE_STRATEGY_IDENTITY" in results["A1"].reason_codes


def test_different_strategies_different_parameter_hashes_remain_comparable():
    policy = _policy()
    a = _evidence("A1", "strat-a", parameters_sha256=HASH_A)
    b = _evidence("A2", "strat-b", parameters_sha256=HASH_B)
    results = _by_id(comparability.check_comparability([(a, CANONICAL), (b, CANONICAL)], policy))
    assert results["A1"].eligible is True
    assert results["A2"].eligible is True
    assert results["A1"].reason_codes == ()
    assert results["A2"].reason_codes == ()


def test_evaluation_mode_not_eligible_rejected():
    policy = _policy(eligible_evaluation_modes=["HISTORICAL_REPLAY"])
    evidence = _evidence("A1", "strat-a", mode="EX_ANTE")
    result = _by_id(comparability.check_comparability([(evidence, CANONICAL)], policy))["A1"]
    assert result.eligible is False
    assert "EVALUATION_MODE_NOT_ELIGIBLE" in result.reason_codes


def test_lottery_type_mismatch_rejected():
    policy = _policy(required_lottery_type="DAILY_539")
    evidence = _evidence("A1", "strat-a")
    result = _by_id(comparability.check_comparability([(evidence, CANONICAL)], policy))["A1"]
    assert result.eligible is False
    assert "LOTTERY_TYPE_MISMATCH" in result.reason_codes


def test_sample_size_below_minimum_rejected():
    policy = _policy(minimum_sample_size=10)
    evidence = _evidence("A1", "strat-a", sample_size=1)
    result = _by_id(comparability.check_comparability([(evidence, CANONICAL)], policy))["A1"]
    assert result.eligible is False
    assert "SAMPLE_SIZE_BELOW_MINIMUM" in result.reason_codes


def test_comparability_checker_returns_no_ranking_output():
    policy = _policy()
    a = _evidence("A1", "strat-a")
    b = _evidence("A2", "strat-b")
    results = comparability.check_comparability([(a, CANONICAL), (b, CANONICAL)], policy)
    for result in results:
        assert not hasattr(result, "rank")
        assert not hasattr(result, "score")
    assert {type(r).__name__ for r in results} == {"ComparabilityResult"}
