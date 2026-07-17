"""Multi-artifact comparability checking against a ranking policy (Contract Part 9).

Returns eligibility and reason codes only. Performs no sorting and produces
no ranking output — see docs/architecture/evaluation-evidence-contract.md.

The trust gate here is unconditional: only ``REGISTERED_CANONICAL`` evidence
may ever be eligible, independent of a policy's own ``required_evidence_trust``
declaration (Contract Authority Hierarchy #7-8 — no evidence becomes
canonical, and no ranking is valid, merely by self-declaration or policy
say-so).

Shared-environment equality is unanimous, not majority-vote: if any two
trusted candidates disagree on a shared-environment dimension, the whole
candidate set is mutually incomparable and every member is rejected. This
avoids inventing an unspecified tie-break rule for "most artifacts agree."
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from lottolab.evidence.models import (
    CandidateCountPolicy,
    EvidenceTrustClass,
    MetricResult,
    RankingPolicy,
    StrategyEvaluationEvidence,
)


@dataclass(frozen=True, slots=True)
class ComparabilityResult:
    artifact_id: str
    eligible: bool
    reason_codes: tuple[str, ...]


def _primary_result(
    evidence: StrategyEvaluationEvidence, policy: RankingPolicy
) -> MetricResult | None:
    return next(
        (
            result
            for result in evidence.metric_results
            if result.metric_id == policy.primary_metric_id
            and result.metric_version == policy.primary_metric_version
        ),
        None,
    )


def _candidate_count_conformance_key(
    evidence: StrategyEvaluationEvidence, policy: RankingPolicy
) -> tuple[int, ...] | None:
    if policy.candidate_count_policy is CandidateCountPolicy.ALLOW_ANY:
        return None
    return tuple(len(record.tickets) for record in evidence.records)


def _shared_environment_key(
    evidence: StrategyEvaluationEvidence, policy: RankingPolicy, primary_result: MetricResult
) -> tuple[object, ...]:
    return (
        evidence.dataset_reference.lottery_type.value,
        evidence.dataset_reference.dataset_sha256,
        evidence.evaluation_mode.value,
        evidence.evaluation_protocol.value,
        evidence.evaluation_windows.evaluation_window.start_sequence,
        evidence.evaluation_windows.evaluation_window.end_sequence,
        primary_result.metric_id,
        primary_result.metric_version,
        primary_result.metric_definition_sha256,
        primary_result.sample_unit.value,
        _candidate_count_conformance_key(evidence, policy),
    )


def check_comparability(
    candidates: list[tuple[StrategyEvaluationEvidence, EvidenceTrustClass]],
    policy: RankingPolicy,
) -> tuple[ComparabilityResult, ...]:
    reasons: dict[str, list[str]] = defaultdict(list)

    def reject(artifact_id: str, code: str) -> None:
        reasons[artifact_id].append(code)

    trusted: list[StrategyEvaluationEvidence] = []
    for evidence, trust in candidates:
        if trust is not EvidenceTrustClass.REGISTERED_CANONICAL:
            reject(evidence.artifact_id, "NOT_REGISTERED_CANONICAL")
        else:
            trusted.append(evidence)

    survivors: list[StrategyEvaluationEvidence] = []
    for evidence in trusted:
        if evidence.evaluation_mode not in policy.eligible_evaluation_modes:
            reject(evidence.artifact_id, "EVALUATION_MODE_NOT_ELIGIBLE")
        elif evidence.dataset_reference.lottery_type != policy.required_lottery_type:
            reject(evidence.artifact_id, "LOTTERY_TYPE_MISMATCH")
        else:
            survivors.append(evidence)
    trusted = survivors

    survivors = []
    primary_results: dict[str, MetricResult] = {}
    for evidence in trusted:
        result = _primary_result(evidence, policy)
        if result is None:
            reject(evidence.artifact_id, "PRIMARY_METRIC_RESULT_ABSENT")
        elif result.sample_size < policy.minimum_sample_size:
            reject(evidence.artifact_id, "SAMPLE_SIZE_BELOW_MINIMUM")
        else:
            primary_results[evidence.artifact_id] = result
            survivors.append(evidence)
    trusted = survivors

    if trusted:
        keyed: list[tuple[StrategyEvaluationEvidence, tuple[object, ...]]] = [
            (
                evidence,
                _shared_environment_key(evidence, policy, primary_results[evidence.artifact_id]),
            )
            for evidence in trusted
        ]
        distinct_keys = {key for _, key in keyed}
        if len(distinct_keys) > 1:
            for evidence, _ in keyed:
                reject(evidence.artifact_id, "SHARED_ENVIRONMENT_MISMATCH")
            trusted = []

    by_identity: dict[tuple[str, str], list[StrategyEvaluationEvidence]] = defaultdict(list)
    for evidence in trusted:
        by_identity[(evidence.strategy_id, evidence.strategy_version)].append(evidence)

    for group in by_identity.values():
        if len(group) > 1:
            for evidence in group:
                reject(evidence.artifact_id, "DUPLICATE_STRATEGY_IDENTITY")

    all_artifact_ids = {evidence.artifact_id for evidence, _ in candidates}
    results = [
        ComparabilityResult(
            artifact_id=artifact_id,
            eligible=artifact_id not in reasons,
            reason_codes=tuple(reasons.get(artifact_id, ())),
        )
        for artifact_id in all_artifact_ids
    ]
    return tuple(sorted(results, key=lambda result: result.artifact_id))
