"""Evaluate exact persisted Historical Prefix portfolios as success windows."""

from __future__ import annotations

import re
from datetime import date
from fractions import Fraction
from math import comb, gcd

from lottolab.application.historical_prefix_success_windows import (
    BENJAMINI_YEKUTIELI_METHOD,
    CONFIRMATION_TARGET_COUNT,
    DEFAULT_PAGE_LIMIT,
    DEFAULT_PAGE_OFFSET,
    DISCOVERY_TARGET_COUNT,
    FEATURE_COHORT_RELATION_ORDER,
    FISHER_EXACT_TWO_SIDED_METHOD,
    MAX_PAGE_LIMIT,
    MIN_PAGE_LIMIT,
    RECENT_AUDIT_SPLIT_METHOD,
    RECENT_AUDIT_TARGET_COUNT,
    RECENT_REFERENCE_TARGET_COUNT,
    REQUIRED_LABELED_TARGET_COUNT,
    SUPPORTED_PREFIX_COUNTS,
    SUPPORTED_SUCCESS_CRITERIA,
    TEMPORAL_HOLDOUT_SPLIT_METHOD,
    HistoricalPrefixConfirmationOverlapRelation,
    HistoricalPrefixConfirmationTargetOverlap,
    HistoricalPrefixCrossImportCohortComparison,
    HistoricalPrefixCrossImportConcordanceResult,
    HistoricalPrefixCrossImportMetadata,
    HistoricalPrefixCrossImportPairStatus,
    HistoricalPrefixExactProbability,
    HistoricalPrefixExactSuccessRate,
    HistoricalPrefixFeatureCohortDiagnostic,
    HistoricalPrefixFeatureCohortSummary,
    HistoricalPrefixFeatureCohortTestStatus,
    HistoricalPrefixFeatureRelationTriple,
    HistoricalPrefixMultiImportCensusStatus,
    HistoricalPrefixMultiImportCensusSummary,
    HistoricalPrefixMultiImportCohortCensusRow,
    HistoricalPrefixMultiImportConcordanceCensusResult,
    HistoricalPrefixMultiImportConfirmationDiagnostic,
    HistoricalPrefixMultiImportPairResult,
    HistoricalPrefixMultiImportSourceResult,
    HistoricalPrefixOutcomeCounts,
    HistoricalPrefixRateRelation,
    HistoricalPrefixRecentStabilityAuditCohortComparison,
    HistoricalPrefixRecentStabilityAuditResult,
    HistoricalPrefixRecentStabilityAuditSplit,
    HistoricalPrefixRecentStabilityAuditStatus,
    HistoricalPrefixSignedRateDelta,
    HistoricalPrefixStrategyFeatureCohortDiagnostics,
    HistoricalPrefixStrategyFeatureCohortResult,
    HistoricalPrefixStrategySuccessMatrix,
    HistoricalPrefixStrategySuccessMatrixCell,
    HistoricalPrefixStrategySuccessWindowPage,
    HistoricalPrefixStrategySuccessWindowResult,
    HistoricalPrefixSuccessCriterion,
    HistoricalPrefixSuccessCriterionIdentity,
    HistoricalPrefixSuccessDrawIdentity,
    HistoricalPrefixSuccessEvaluationStatus,
    HistoricalPrefixSuccessImportNotFoundError,
    HistoricalPrefixSuccessSelectionIdentity,
    HistoricalPrefixSuccessSourceObservation,
    HistoricalPrefixSuccessSourceStrategy,
    HistoricalPrefixSuccessStrategyNotFoundError,
    HistoricalPrefixSuccessWindowsContractError,
    HistoricalPrefixSuccessWindowSource,
    HistoricalPrefixSuccessWindowSummary,
    HistoricalPrefixSuccessWindowsUnavailableError,
    HistoricalPrefixTemporalHoldoutCohortComparison,
    HistoricalPrefixTemporalHoldoutRelationship,
    HistoricalPrefixTemporalHoldoutResult,
    HistoricalPrefixTemporalHoldoutSplit,
    HistoricalPrefixTemporalHoldoutStatus,
    HistoricalPrefixWalkForwardAssignment,
    HistoricalPrefixWalkForwardBaseline,
    HistoricalPrefixWindowRateComparison,
    HistoricalPrefixWindowRateComparisonKind,
)
from lottolab.application.historical_success_qualification import (
    HistoricalSuccessQualificationCensusStatus,
    HistoricalSuccessQualificationCensusSummary,
    HistoricalSuccessQualificationEvidenceStatus,
    HistoricalSuccessQualificationIdentity,
    HistoricalSuccessQualificationImportEvidence,
    HistoricalSuccessQualificationOverlapRelation,
    HistoricalSuccessQualificationPairInput,
    HistoricalSuccessQualificationPairStatus,
    HistoricalSuccessResearchQualification,
    qualify_historical_success,
)
from lottolab.application.ports import (
    HistoricalPrefixSuccessWindowSourceReader,
    HistoricalPrefixSuccessWindowSourceReaderFactory,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import BIG_LOTTO_RULE_CONTRACT
from lottolab.domain.strategy_success_evaluation import (
    BigLottoSuccessCriterion,
    ObservationEvaluation,
    StrategySuccessEvaluationInputError,
    WindowEvaluationStatus,
    WindowKind,
    WindowSuccessSummary,
    evaluate_observation,
    evaluate_strategy_success_windows,
)
from lottolab.domain.strategy_success_measurement import (
    DEFAULT_WINDOW_POLICY,
    DEFAULT_WINDOW_POLICY_VERSION,
    BigLottoOutcomeSignature,
    BigLottoPortfolioOutcomeSignature,
    EvidenceStatus,
    MeasurementMode,
    MeasurementProvenance,
    SelectionIdentity,
    StrategySuccessMeasurement,
)

_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)

_CRITERION_PARAMETERS = {
    HistoricalPrefixSuccessCriterion.M3_PLUS: (3, False),
    HistoricalPrefixSuccessCriterion.M4_PLUS: (4, False),
    HistoricalPrefixSuccessCriterion.M5_PLUS: (5, False),
    HistoricalPrefixSuccessCriterion.M6: (6, False),
    HistoricalPrefixSuccessCriterion.M2_PLUS_SPECIAL: (2, True),
    HistoricalPrefixSuccessCriterion.M3_PLUS_SPECIAL: (3, True),
    HistoricalPrefixSuccessCriterion.M4_PLUS_SPECIAL: (4, True),
    HistoricalPrefixSuccessCriterion.M5_PLUS_SPECIAL: (5, True),
}
_COMPARISON_DEFINITIONS = (
    (
        HistoricalPrefixWindowRateComparisonKind.FULL_HISTORY_TO_LONG,
        WindowKind.FULL_HISTORY,
        WindowKind.LONG,
    ),
    (
        HistoricalPrefixWindowRateComparisonKind.LONG_TO_MEDIUM,
        WindowKind.LONG,
        WindowKind.MEDIUM,
    ),
    (
        HistoricalPrefixWindowRateComparisonKind.MEDIUM_TO_SHORT,
        WindowKind.MEDIUM,
        WindowKind.SHORT,
    ),
    (
        HistoricalPrefixWindowRateComparisonKind.LONG_TO_SHORT,
        WindowKind.LONG,
        WindowKind.SHORT,
    ),
)


def _contract_error(message: str) -> HistoricalPrefixSuccessWindowsContractError:
    return HistoricalPrefixSuccessWindowsContractError(message)


def _validate_import_identity(import_identity_sha256: str) -> None:
    if (
        type(import_identity_sha256) is not str
        or _SHA256_PATTERN.fullmatch(import_identity_sha256) is None
    ):
        raise _contract_error("import_identity_sha256 must be an exact lowercase SHA-256")


def _validate_import_identities(import_identity_sha256s: tuple[str, ...]) -> None:
    if type(import_identity_sha256s) is not tuple or not 2 <= len(import_identity_sha256s) <= 4:
        raise _contract_error("import_identity_sha256 must contain exactly 2 to 4 values")
    for import_identity_sha256 in import_identity_sha256s:
        _validate_import_identity(import_identity_sha256)
    if len(set(import_identity_sha256s)) != len(import_identity_sha256s):
        raise _contract_error("import identities must be distinct")


def _validate_prefix_count(prefix_count: int) -> None:
    if type(prefix_count) is not int or prefix_count not in SUPPORTED_PREFIX_COUNTS:
        raise _contract_error("prefix_count is outside the closed supported set")


def _validate_criterion(criterion: HistoricalPrefixSuccessCriterion) -> None:
    if type(criterion) is not HistoricalPrefixSuccessCriterion:
        raise _contract_error("criterion is outside the closed supported set")


def _validate_pagination(limit: int, offset: int) -> None:
    if type(limit) is not int or not MIN_PAGE_LIMIT <= limit <= MAX_PAGE_LIMIT:
        raise _contract_error("limit must be an integer between 1 and 200")
    if type(offset) is not int or offset < DEFAULT_PAGE_OFFSET:
        raise _contract_error("offset must be a non-negative integer")


def _validate_strategy_axis(value: str, name: str) -> None:
    if type(value) is not str or not value or value != value.strip() or len(value) > 200:
        raise _contract_error(f"{name} must be a non-empty canonical string")


def _criterion_identity(
    criterion: HistoricalPrefixSuccessCriterion,
) -> HistoricalPrefixSuccessCriterionIdentity:
    minimum_main_hits, require_special_hit = _CRITERION_PARAMETERS[criterion]
    return HistoricalPrefixSuccessCriterionIdentity(
        criterion=criterion,
        minimum_main_hits=minimum_main_hits,
        require_special_hit=require_special_hit,
        measurement_mode=MeasurementMode.LEGAL_TICKET_PRIZE,
    )


def _domain_criterion(criterion: HistoricalPrefixSuccessCriterion) -> BigLottoSuccessCriterion:
    identity = _criterion_identity(criterion)
    return BigLottoSuccessCriterion(
        minimum_main_hits=identity.minimum_main_hits,
        require_special_hit=identity.require_special_hit,
        expected_mode=MeasurementMode.LEGAL_TICKET_PRIZE,
    )


def _draw_token(draw: HistoricalPrefixSuccessDrawIdentity) -> str:
    return f"{draw.draw_date}#{draw.draw_number}"


def _selection(
    strategy: HistoricalPrefixSuccessSourceStrategy,
    prefix_count: int,
) -> SelectionIdentity:
    return SelectionIdentity(
        lottery=LotteryType.BIG_LOTTO,
        strategy_id=strategy.identity.strategy_id,
        strategy_version=strategy.identity.strategy_version,
        max_bet_index=prefix_count,
        ticket_count=prefix_count,
    )


def _selection_read_model(
    strategy: HistoricalPrefixSuccessSourceStrategy,
    prefix_count: int,
) -> HistoricalPrefixSuccessSelectionIdentity:
    return HistoricalPrefixSuccessSelectionIdentity(
        lottery=LotteryType.BIG_LOTTO,
        strategy_id=strategy.identity.strategy_id,
        strategy_version=strategy.identity.strategy_version,
        replicate=strategy.identity.replicate,
        ticket_count=prefix_count,
        max_bet_index=prefix_count,
    )


def _ordered_observations(
    strategy: HistoricalPrefixSuccessSourceStrategy,
) -> tuple[HistoricalPrefixSuccessSourceObservation, ...]:
    observations = tuple(
        sorted(
            strategy.observations,
            key=lambda item: (item.target.draw_date, item.target.draw_number),
        )
    )
    targets = tuple(item.target.draw_number for item in observations)
    if len(targets) != len(set(targets)):
        raise HistoricalPrefixSuccessWindowsUnavailableError(
            "persisted source contains a duplicate exact strategy/target observation"
        )
    return observations


def _walk_forward_observations(
    strategy: HistoricalPrefixSuccessSourceStrategy,
) -> tuple[HistoricalPrefixSuccessSourceObservation, ...]:
    observations = _ordered_observations(strategy)
    previous_target_number: int | None = None
    for observation in observations:
        try:
            target_date = date.fromisoformat(observation.target.draw_date)
            cutoff_date = date.fromisoformat(observation.cutoff.draw_date)
        except ValueError as exc:
            raise HistoricalPrefixSuccessWindowsUnavailableError(
                "persisted source contains malformed target/cutoff chronology"
            ) from exc
        if (
            target_date.isoformat() != observation.target.draw_date
            or cutoff_date.isoformat() != observation.cutoff.draw_date
            or (cutoff_date, observation.cutoff.draw_number)
            >= (target_date, observation.target.draw_number)
            or observation.cutoff.draw_number > observation.target.draw_number
        ):
            raise HistoricalPrefixSuccessWindowsUnavailableError(
                "persisted source contains malformed target/cutoff chronology"
            )
        if (
            previous_target_number is not None
            and observation.target.draw_number <= previous_target_number
        ):
            raise HistoricalPrefixSuccessWindowsUnavailableError(
                "persisted source contains inconsistent target chronology"
            )
        previous_target_number = observation.target.draw_number
    return observations


def _measurement(
    *,
    source: HistoricalPrefixSuccessWindowSource,
    strategy: HistoricalPrefixSuccessSourceStrategy,
    observation: HistoricalPrefixSuccessSourceObservation,
    prefix_count: int,
    criterion: HistoricalPrefixSuccessCriterion,
) -> StrategySuccessMeasurement:
    selected_tickets = observation.tickets[:prefix_count]
    outcome = BigLottoPortfolioOutcomeSignature(
        tickets=tuple(
            BigLottoOutcomeSignature(
                main_hits=ticket.main_hit_count,
                special_hit=ticket.special_hit,
            )
            for ticket in selected_tickets
        )
    )
    return StrategySuccessMeasurement(
        mode=MeasurementMode.LEGAL_TICKET_PRIZE,
        selection=_selection(strategy, prefix_count),
        outcome_signature=outcome,
        evidence_status=EvidenceStatus.DESCRIPTIVE_ONLY,
        provenance=MeasurementProvenance(
            strategy_version=strategy.identity.strategy_version,
            parameter_or_config_identity=(f"prefix={prefix_count};criterion={criterion.value}"),
            history_cutoff=_draw_token(observation.cutoff),
            target_draw=_draw_token(observation.target),
            window_policy_version=DEFAULT_WINDOW_POLICY_VERSION,
            game_rule_version=BIG_LOTTO_RULE_CONTRACT.contract_version,
            selection_family_identity=observation.constructor_identifier,
            source_artifact_identity=(
                f"{source.metadata.source_artifact_sha256}:{source.metadata.import_identity_sha256}"
            ),
        ),
        window_policy=DEFAULT_WINDOW_POLICY,
    )


def _window_read_model(
    summary: WindowSuccessSummary,
    observations_by_target: dict[str, HistoricalPrefixSuccessSourceObservation],
) -> HistoricalPrefixSuccessWindowSummary:
    try:
        first = observations_by_target[summary.first_target_draw]
        last = observations_by_target[summary.last_target_draw]
    except KeyError as exc:
        raise HistoricalPrefixSuccessWindowsUnavailableError(
            "evaluator returned target provenance absent from the persisted source"
        ) from exc
    return HistoricalPrefixSuccessWindowSummary(
        window_kind=summary.window_kind,
        window_role=summary.window_role,
        requested_draw_count=summary.requested_draw_count,
        source_draw_count=summary.source_draw_count,
        eligible_draw_count=summary.eligible_draw_count,
        excluded_draw_count=summary.excluded_draw_count,
        success_count=summary.success_count,
        failure_count=summary.failure_count,
        success_rate=HistoricalPrefixExactSuccessRate(
            numerator=summary.success_rate.numerator,
            denominator=summary.success_rate.denominator,
            available=summary.success_rate.is_available,
        ),
        first_target=first.target,
        last_target=last.target,
        first_cutoff=first.cutoff,
        last_cutoff=last.cutoff,
        nested_windows_independent=summary.nested_windows_independent,
        evaluation_status=summary.evaluation_status,
        evidence_status=summary.evidence_status,
    )


def _evaluate_strategy(
    *,
    source: HistoricalPrefixSuccessWindowSource,
    strategy: HistoricalPrefixSuccessSourceStrategy,
    prefix_count: int,
    criterion: HistoricalPrefixSuccessCriterion,
) -> HistoricalPrefixStrategySuccessWindowResult:
    selection = _selection_read_model(strategy, prefix_count)
    criterion_identity = _criterion_identity(criterion)
    observations = _ordered_observations(strategy)
    if not observations:
        return HistoricalPrefixStrategySuccessWindowResult(
            strategy=strategy.identity,
            criterion=criterion_identity,
            prefix_count=prefix_count,
            selection=selection,
            status=HistoricalPrefixSuccessEvaluationStatus.NO_OBSERVATIONS,
            source_observation_count=0,
            windows=(),
        )

    measurements = tuple(
        _measurement(
            source=source,
            strategy=strategy,
            observation=observation,
            prefix_count=prefix_count,
            criterion=criterion,
        )
        for observation in observations
    )
    observations_by_target = {_draw_token(item.target): item for item in observations}
    try:
        evaluated = evaluate_strategy_success_windows(
            measurements,
            _domain_criterion(criterion),
        )
    except (StrategySuccessEvaluationInputError, TypeError, ValueError) as exc:
        raise HistoricalPrefixSuccessWindowsUnavailableError(
            "persisted source could not be evaluated under the merged contract"
        ) from exc
    windows = tuple(_window_read_model(summary, observations_by_target) for summary in evaluated)
    if len(windows) != 4:
        raise HistoricalPrefixSuccessWindowsUnavailableError(
            "merged evaluator did not return the canonical four-window sequence"
        )
    return HistoricalPrefixStrategySuccessWindowResult(
        strategy=strategy.identity,
        criterion=criterion_identity,
        prefix_count=prefix_count,
        selection=selection,
        status=HistoricalPrefixSuccessEvaluationStatus.EVALUATED,
        source_observation_count=len(observations),
        windows=windows,
    )


def _signed_rate_delta(
    from_rate: HistoricalPrefixExactSuccessRate,
    to_rate: HistoricalPrefixExactSuccessRate,
) -> tuple[HistoricalPrefixSignedRateDelta, HistoricalPrefixRateRelation]:
    if not from_rate.available or not to_rate.available:
        return (
            HistoricalPrefixSignedRateDelta(
                numerator=0,
                denominator=0,
                available=False,
            ),
            HistoricalPrefixRateRelation.UNAVAILABLE,
        )
    if from_rate.denominator <= 0 or to_rate.denominator <= 0:
        raise HistoricalPrefixSuccessWindowsUnavailableError(
            "available success rates must have positive denominators"
        )
    numerator = (
        to_rate.numerator * from_rate.denominator - from_rate.numerator * to_rate.denominator
    )
    denominator = to_rate.denominator * from_rate.denominator
    divisor = gcd(abs(numerator), denominator)
    numerator //= divisor
    denominator //= divisor
    if numerator == 0:
        denominator = 1
        relation = HistoricalPrefixRateRelation.EQUAL
    elif numerator > 0:
        relation = HistoricalPrefixRateRelation.HIGHER
    else:
        relation = HistoricalPrefixRateRelation.LOWER
    return (
        HistoricalPrefixSignedRateDelta(
            numerator=numerator,
            denominator=denominator,
            available=True,
        ),
        relation,
    )


def _rate_comparisons(
    windows: tuple[HistoricalPrefixSuccessWindowSummary, ...],
) -> tuple[HistoricalPrefixWindowRateComparison, ...]:
    expected_order = (
        WindowKind.FULL_HISTORY,
        WindowKind.LONG,
        WindowKind.MEDIUM,
        WindowKind.SHORT,
    )
    if tuple(window.window_kind for window in windows) != expected_order:
        raise HistoricalPrefixSuccessWindowsUnavailableError(
            "merged evaluator did not return the canonical four-window sequence"
        )
    by_kind = {window.window_kind: window for window in windows}
    comparisons: list[HistoricalPrefixWindowRateComparison] = []
    for comparison_kind, from_kind, to_kind in _COMPARISON_DEFINITIONS:
        from_rate = by_kind[from_kind].success_rate
        to_rate = by_kind[to_kind].success_rate
        delta, relation = _signed_rate_delta(from_rate, to_rate)
        comparisons.append(
            HistoricalPrefixWindowRateComparison(
                comparison_kind=comparison_kind,
                from_window_kind=from_kind,
                to_window_kind=to_kind,
                from_rate=from_rate,
                to_rate=to_rate,
                delta=delta,
                relation=relation,
            )
        )
    return tuple(comparisons)


def _snapshot_feature_key(
    *,
    source: HistoricalPrefixSuccessWindowSource,
    strategy: HistoricalPrefixSuccessSourceStrategy,
    prior_observations: tuple[HistoricalPrefixSuccessSourceObservation, ...],
    prefix_count: int,
    criterion: HistoricalPrefixSuccessCriterion,
) -> HistoricalPrefixFeatureRelationTriple:
    if not prior_observations:
        return HistoricalPrefixFeatureRelationTriple(
            long_to_medium=HistoricalPrefixRateRelation.UNAVAILABLE,
            medium_to_short=HistoricalPrefixRateRelation.UNAVAILABLE,
            long_to_short=HistoricalPrefixRateRelation.UNAVAILABLE,
        )
    measurements = tuple(
        _measurement(
            source=source,
            strategy=strategy,
            observation=observation,
            prefix_count=prefix_count,
            criterion=criterion,
        )
        for observation in prior_observations
    )
    observations_by_target = {_draw_token(item.target): item for item in prior_observations}
    try:
        evaluated = evaluate_strategy_success_windows(
            measurements,
            _domain_criterion(criterion),
        )
    except (StrategySuccessEvaluationInputError, TypeError, ValueError) as exc:
        raise HistoricalPrefixSuccessWindowsUnavailableError(
            "persisted source could not produce a walk-forward snapshot"
        ) from exc
    windows = tuple(_window_read_model(summary, observations_by_target) for summary in evaluated)
    comparisons = _rate_comparisons(windows)
    relations = {comparison.comparison_kind: comparison.relation for comparison in comparisons}
    return HistoricalPrefixFeatureRelationTriple(
        long_to_medium=relations[HistoricalPrefixWindowRateComparisonKind.LONG_TO_MEDIUM],
        medium_to_short=relations[HistoricalPrefixWindowRateComparisonKind.MEDIUM_TO_SHORT],
        long_to_short=relations[HistoricalPrefixWindowRateComparisonKind.LONG_TO_SHORT],
    )


def _current_target_succeeded(
    *,
    source: HistoricalPrefixSuccessWindowSource,
    strategy: HistoricalPrefixSuccessSourceStrategy,
    current_target: HistoricalPrefixSuccessSourceObservation,
    prefix_count: int,
    criterion: HistoricalPrefixSuccessCriterion,
) -> bool:
    result = evaluate_observation(
        _measurement(
            source=source,
            strategy=strategy,
            observation=current_target,
            prefix_count=prefix_count,
            criterion=criterion,
        ),
        _domain_criterion(criterion),
    )
    if result is ObservationEvaluation.SUCCESS:
        return True
    if result is ObservationEvaluation.FAILURE:
        return False
    raise HistoricalPrefixSuccessWindowsUnavailableError(
        "current target could not be labeled under the exact criterion"
    )


def _success_rate(success_count: int, observation_count: int) -> HistoricalPrefixExactSuccessRate:
    if observation_count == 0:
        return HistoricalPrefixExactSuccessRate(
            numerator=0,
            denominator=0,
            available=False,
        )
    return HistoricalPrefixExactSuccessRate(
        numerator=success_count,
        denominator=observation_count,
        available=True,
    )


def _build_walk_forward_assignments(
    *,
    source: HistoricalPrefixSuccessWindowSource,
    strategy: HistoricalPrefixSuccessSourceStrategy,
    prefix_count: int,
    criterion: HistoricalPrefixSuccessCriterion,
) -> tuple[HistoricalPrefixWalkForwardAssignment, ...]:
    observations = _walk_forward_observations(strategy)
    assignments: list[HistoricalPrefixWalkForwardAssignment] = []
    frozen_source_identity = source.metadata.import_identity_sha256
    for index, current_target in enumerate(observations):
        feature_key = _snapshot_feature_key(
            source=source,
            strategy=strategy,
            prior_observations=observations[:index],
            prefix_count=prefix_count,
            criterion=criterion,
        )
        succeeded = _current_target_succeeded(
            source=source,
            strategy=strategy,
            current_target=current_target,
            prefix_count=prefix_count,
            criterion=criterion,
        )
        assignments.append(
            HistoricalPrefixWalkForwardAssignment(
                chronological_index=index,
                target=current_target.target,
                feature_key=feature_key,
                succeeded=succeeded,
            )
        )
    if source.metadata.import_identity_sha256 != frozen_source_identity:
        raise HistoricalPrefixSuccessWindowsUnavailableError(
            "persisted source identity changed during walk-forward reconstruction"
        )
    return tuple(assignments)


def _feature_cohorts_from_assignments(
    *,
    source: HistoricalPrefixSuccessWindowSource,
    strategy: HistoricalPrefixSuccessSourceStrategy,
    prefix_count: int,
    criterion: HistoricalPrefixSuccessCriterion,
    assignments: tuple[HistoricalPrefixWalkForwardAssignment, ...],
) -> HistoricalPrefixStrategyFeatureCohortResult:
    grouped: dict[
        HistoricalPrefixFeatureRelationTriple,
        list[HistoricalPrefixWalkForwardAssignment],
    ] = {}
    for assignment in assignments:
        grouped.setdefault(assignment.feature_key, []).append(assignment)
    baseline_count = len(assignments)
    baseline_successes = sum(int(item.succeeded) for item in assignments)
    baseline_rate = _success_rate(baseline_successes, baseline_count)
    baseline = HistoricalPrefixWalkForwardBaseline(
        observation_count=baseline_count,
        success_count=baseline_successes,
        failure_count=baseline_count - baseline_successes,
        success_rate=baseline_rate,
    )
    cohorts: list[HistoricalPrefixFeatureCohortSummary] = []
    for long_to_medium in FEATURE_COHORT_RELATION_ORDER:
        for medium_to_short in FEATURE_COHORT_RELATION_ORDER:
            for long_to_short in FEATURE_COHORT_RELATION_ORDER:
                feature_key = HistoricalPrefixFeatureRelationTriple(
                    long_to_medium=long_to_medium,
                    medium_to_short=medium_to_short,
                    long_to_short=long_to_short,
                )
                outcomes = grouped.get(feature_key, [])
                observation_count = len(outcomes)
                success_count = sum(int(item.succeeded) for item in outcomes)
                cohort_rate = _success_rate(success_count, observation_count)
                delta, relation = _signed_rate_delta(baseline_rate, cohort_rate)
                cohorts.append(
                    HistoricalPrefixFeatureCohortSummary(
                        feature_key=feature_key,
                        observation_count=observation_count,
                        success_count=success_count,
                        failure_count=observation_count - success_count,
                        success_rate=cohort_rate,
                        delta_vs_baseline=delta,
                        relation_vs_baseline=relation,
                        first_target=outcomes[0].target if outcomes else None,
                        last_target=outcomes[-1].target if outcomes else None,
                    )
                )
    if len(cohorts) != 64 or sum(cohort.observation_count for cohort in cohorts) != baseline_count:
        raise HistoricalPrefixSuccessWindowsUnavailableError(
            "walk-forward targets were not assigned to the canonical cohorts exactly once"
        )
    return HistoricalPrefixStrategyFeatureCohortResult(
        metadata=source.metadata,
        strategy=strategy.identity,
        criterion=_criterion_identity(criterion),
        prefix_count=prefix_count,
        baseline=baseline,
        cohort_count=len(cohorts),
        cohorts=tuple(cohorts),
    )


def _feature_cohorts(
    *,
    source: HistoricalPrefixSuccessWindowSource,
    strategy: HistoricalPrefixSuccessSourceStrategy,
    prefix_count: int,
    criterion: HistoricalPrefixSuccessCriterion,
) -> HistoricalPrefixStrategyFeatureCohortResult:
    assignments = _build_walk_forward_assignments(
        source=source,
        strategy=strategy,
        prefix_count=prefix_count,
        criterion=criterion,
    )
    return _feature_cohorts_from_assignments(
        source=source,
        strategy=strategy,
        prefix_count=prefix_count,
        criterion=criterion,
        assignments=assignments,
    )


def _exact_probability(value: Fraction) -> HistoricalPrefixExactProbability:
    if value < 0 or value > 1:
        raise HistoricalPrefixSuccessWindowsUnavailableError(
            "exact probability must be between zero and one"
        )
    return HistoricalPrefixExactProbability(
        numerator=value.numerator,
        denominator=value.denominator,
    )


def _fisher_exact_two_sided(
    cohort: HistoricalPrefixOutcomeCounts,
    outside: HistoricalPrefixOutcomeCounts,
) -> HistoricalPrefixExactProbability:
    total_observations = cohort.observation_count + outside.observation_count
    total_successes = cohort.success_count + outside.success_count
    cohort_observations = cohort.observation_count
    observed_successes = cohort.success_count
    lower = max(0, cohort_observations - (total_observations - total_successes))
    upper = min(cohort_observations, total_successes)
    if not lower <= observed_successes <= upper:
        raise HistoricalPrefixSuccessWindowsUnavailableError(
            "observed cohort successes fall outside the exact Fisher support"
        )
    denominator = comb(total_observations, cohort_observations)
    if denominator <= 0:
        raise HistoricalPrefixSuccessWindowsUnavailableError(
            "exact Fisher denominator must be positive"
        )

    def weight(successes: int) -> int:
        return comb(total_successes, successes) * comb(
            total_observations - total_successes,
            cohort_observations - successes,
        )

    observed_weight = weight(observed_successes)
    numerator = sum(
        candidate_weight
        for successes in range(lower, upper + 1)
        if (candidate_weight := weight(successes)) <= observed_weight
    )
    return _exact_probability(Fraction(numerator, denominator))


def _diagnostic_test_status(
    cohort: HistoricalPrefixOutcomeCounts,
    outside: HistoricalPrefixOutcomeCounts,
) -> HistoricalPrefixFeatureCohortTestStatus:
    if cohort.observation_count == 0:
        return HistoricalPrefixFeatureCohortTestStatus.NOT_TESTABLE_EMPTY_COHORT
    if outside.observation_count == 0:
        return HistoricalPrefixFeatureCohortTestStatus.NOT_TESTABLE_EMPTY_COMPLEMENT
    total_successes = cohort.success_count + outside.success_count
    total_observations = cohort.observation_count + outside.observation_count
    if total_successes == 0 or total_successes == total_observations:
        return HistoricalPrefixFeatureCohortTestStatus.NOT_TESTABLE_NO_OUTCOME_VARIATION
    return HistoricalPrefixFeatureCohortTestStatus.TESTED


def _adjust_benjamini_yekutieli(
    raw_probabilities: tuple[HistoricalPrefixExactProbability, ...],
) -> tuple[HistoricalPrefixExactProbability, ...]:
    family_size = len(raw_probabilities)
    if family_size != 64:
        raise HistoricalPrefixSuccessWindowsUnavailableError(
            "feature-cohort diagnostics require the fixed family size of 64"
        )
    harmonic_factor = sum(
        (Fraction(1, rank) for rank in range(1, family_size + 1)),
        start=Fraction(0, 1),
    )
    ordered = sorted(
        enumerate(raw_probabilities),
        key=lambda item: (
            Fraction(item[1].numerator, item[1].denominator),
            item[0],
        ),
    )
    candidates = [
        min(
            Fraction(1, 1),
            Fraction(probability.numerator, probability.denominator)
            * family_size
            * harmonic_factor
            / rank,
        )
        for rank, (_, probability) in enumerate(ordered, start=1)
    ]
    adjusted_sorted = [Fraction(1, 1)] * family_size
    running_minimum = Fraction(1, 1)
    for index in range(family_size - 1, -1, -1):
        running_minimum = min(running_minimum, candidates[index])
        adjusted_sorted[index] = running_minimum
    adjusted = [HistoricalPrefixExactProbability(1, 1)] * family_size
    for (canonical_index, _), probability in zip(ordered, adjusted_sorted, strict=True):
        adjusted[canonical_index] = _exact_probability(probability)
    return tuple(adjusted)


def _feature_cohort_diagnostics(
    result: HistoricalPrefixStrategyFeatureCohortResult,
) -> HistoricalPrefixStrategyFeatureCohortDiagnostics:
    if result.cohort_count != 64 or len(result.cohorts) != 64:
        raise HistoricalPrefixSuccessWindowsUnavailableError(
            "feature-cohort diagnostics require all 64 canonical cohorts"
        )
    baseline = result.baseline
    raw_probabilities: list[HistoricalPrefixExactProbability] = []
    unadjusted: list[
        tuple[
            HistoricalPrefixFeatureCohortTestStatus,
            HistoricalPrefixOutcomeCounts,
            HistoricalPrefixOutcomeCounts,
            HistoricalPrefixExactSuccessRate,
            HistoricalPrefixSignedRateDelta,
            HistoricalPrefixRateRelation,
        ]
    ] = []
    for cohort in result.cohorts:
        cohort_counts = HistoricalPrefixOutcomeCounts(
            observation_count=cohort.observation_count,
            success_count=cohort.success_count,
            failure_count=cohort.failure_count,
        )
        outside_counts = HistoricalPrefixOutcomeCounts(
            observation_count=baseline.observation_count - cohort.observation_count,
            success_count=baseline.success_count - cohort.success_count,
            failure_count=baseline.failure_count - cohort.failure_count,
        )
        for counts in (cohort_counts, outside_counts):
            if (
                min(
                    counts.observation_count,
                    counts.success_count,
                    counts.failure_count,
                )
                < 0
                or counts.success_count + counts.failure_count != counts.observation_count
            ):
                raise HistoricalPrefixSuccessWindowsUnavailableError(
                    "feature-cohort complement arithmetic is inconsistent"
                )
        status = _diagnostic_test_status(cohort_counts, outside_counts)
        outside_rate = _success_rate(
            outside_counts.success_count,
            outside_counts.observation_count,
        )
        risk_difference, relation = _signed_rate_delta(
            outside_rate,
            cohort.success_rate,
        )
        raw_probability = (
            _fisher_exact_two_sided(cohort_counts, outside_counts)
            if status is HistoricalPrefixFeatureCohortTestStatus.TESTED
            else HistoricalPrefixExactProbability(1, 1)
        )
        raw_probabilities.append(raw_probability)
        unadjusted.append(
            (
                status,
                cohort_counts,
                outside_counts,
                outside_rate,
                risk_difference,
                relation,
            )
        )
    adjusted_probabilities = _adjust_benjamini_yekutieli(tuple(raw_probabilities))
    diagnostics = tuple(
        HistoricalPrefixFeatureCohortDiagnostic(
            cohort_index=index,
            feature_key=cohort.feature_key,
            test_status=status,
            cohort_counts=cohort_counts,
            outside_counts=outside_counts,
            cohort_success_rate=cohort.success_rate,
            outside_success_rate=outside_rate,
            risk_difference=risk_difference,
            relation_vs_outside=relation,
            raw_p_value=raw_probabilities[index],
            adjusted_p_value=adjusted_probabilities[index],
            first_target=cohort.first_target,
            last_target=cohort.last_target,
        )
        for index, (cohort, details) in enumerate(zip(result.cohorts, unadjusted, strict=True))
        for (
            status,
            cohort_counts,
            outside_counts,
            outside_rate,
            risk_difference,
            relation,
        ) in (details,)
    )
    return HistoricalPrefixStrategyFeatureCohortDiagnostics(
        metadata=result.metadata,
        strategy=result.strategy,
        criterion=result.criterion,
        prefix_count=result.prefix_count,
        baseline=result.baseline,
        family_size=64,
        raw_test_method=FISHER_EXACT_TWO_SIDED_METHOD,
        adjustment_method=BENJAMINI_YEKUTIELI_METHOD,
        diagnostics=diagnostics,
    )


def _effect_change(
    discovery: HistoricalPrefixSignedRateDelta,
    confirmation: HistoricalPrefixSignedRateDelta,
) -> HistoricalPrefixSignedRateDelta:
    if not discovery.available or not confirmation.available:
        return HistoricalPrefixSignedRateDelta(
            numerator=0,
            denominator=0,
            available=False,
        )
    change = Fraction(
        confirmation.numerator,
        confirmation.denominator,
    ) - Fraction(discovery.numerator, discovery.denominator)
    return HistoricalPrefixSignedRateDelta(
        numerator=change.numerator,
        denominator=change.denominator,
        available=True,
    )


def _temporal_relationship(
    discovery: HistoricalPrefixRateRelation,
    confirmation: HistoricalPrefixRateRelation,
) -> HistoricalPrefixTemporalHoldoutRelationship:
    if (
        discovery is HistoricalPrefixRateRelation.UNAVAILABLE
        or confirmation is HistoricalPrefixRateRelation.UNAVAILABLE
    ):
        return HistoricalPrefixTemporalHoldoutRelationship.UNAVAILABLE
    if discovery is not confirmation:
        return HistoricalPrefixTemporalHoldoutRelationship.DIFFERENT
    return {
        HistoricalPrefixRateRelation.HIGHER: (
            HistoricalPrefixTemporalHoldoutRelationship.SAME_HIGHER
        ),
        HistoricalPrefixRateRelation.EQUAL: (
            HistoricalPrefixTemporalHoldoutRelationship.SAME_EQUAL
        ),
        HistoricalPrefixRateRelation.LOWER: (
            HistoricalPrefixTemporalHoldoutRelationship.SAME_LOWER
        ),
    }[discovery]


def _temporal_holdout(
    *,
    source: HistoricalPrefixSuccessWindowSource,
    strategy: HistoricalPrefixSuccessSourceStrategy,
    prefix_count: int,
    criterion: HistoricalPrefixSuccessCriterion,
    assignments: tuple[HistoricalPrefixWalkForwardAssignment, ...] | None = None,
) -> HistoricalPrefixTemporalHoldoutResult:
    if assignments is None:
        assignments = _build_walk_forward_assignments(
            source=source,
            strategy=strategy,
            prefix_count=prefix_count,
            criterion=criterion,
        )
    total_count = len(assignments)
    if total_count < REQUIRED_LABELED_TARGET_COUNT:
        return HistoricalPrefixTemporalHoldoutResult(
            metadata=source.metadata,
            strategy=strategy.identity,
            criterion=_criterion_identity(criterion),
            prefix_count=prefix_count,
            split=HistoricalPrefixTemporalHoldoutSplit(
                split_method=TEMPORAL_HOLDOUT_SPLIT_METHOD,
                total_assignment_count=total_count,
                warmup_count=total_count,
                discovery_count=0,
                confirmation_count=0,
                discovery_first_target=None,
                discovery_last_target=None,
                confirmation_first_target=None,
                confirmation_last_target=None,
            ),
            evaluation_status=(
                HistoricalPrefixTemporalHoldoutStatus.NOT_READY_INSUFFICIENT_HISTORY
            ),
            family_size=64,
            discovery=None,
            confirmation=None,
            comparisons=(),
        )

    warmup_count = total_count - REQUIRED_LABELED_TARGET_COUNT
    discovery_end = total_count - CONFIRMATION_TARGET_COUNT
    discovery_assignments = assignments[warmup_count:discovery_end]
    confirmation_assignments = assignments[discovery_end:]
    if (
        len(discovery_assignments) != DISCOVERY_TARGET_COUNT
        or len(confirmation_assignments) != CONFIRMATION_TARGET_COUNT
        or discovery_assignments[-1].chronological_index
        >= confirmation_assignments[0].chronological_index
    ):
        raise HistoricalPrefixSuccessWindowsUnavailableError(
            "fixed temporal holdout partition is inconsistent"
        )
    discovery = _feature_cohort_diagnostics(
        _feature_cohorts_from_assignments(
            source=source,
            strategy=strategy,
            prefix_count=prefix_count,
            criterion=criterion,
            assignments=discovery_assignments,
        )
    )
    confirmation = _feature_cohort_diagnostics(
        _feature_cohorts_from_assignments(
            source=source,
            strategy=strategy,
            prefix_count=prefix_count,
            criterion=criterion,
            assignments=confirmation_assignments,
        )
    )
    comparisons = tuple(
        HistoricalPrefixTemporalHoldoutCohortComparison(
            cohort_index=index,
            feature_key=discovery_diagnostic.feature_key,
            discovery_diagnostic=discovery_diagnostic,
            confirmation_diagnostic=confirmation_diagnostic,
            effect_change=_effect_change(
                discovery_diagnostic.risk_difference,
                confirmation_diagnostic.risk_difference,
            ),
            relationship=_temporal_relationship(
                discovery_diagnostic.relation_vs_outside,
                confirmation_diagnostic.relation_vs_outside,
            ),
        )
        for index, (discovery_diagnostic, confirmation_diagnostic) in enumerate(
            zip(discovery.diagnostics, confirmation.diagnostics, strict=True)
        )
    )
    if len(comparisons) != 64 or any(
        comparison.cohort_index != index
        or comparison.feature_key != comparison.discovery_diagnostic.feature_key
        or comparison.feature_key != comparison.confirmation_diagnostic.feature_key
        for index, comparison in enumerate(comparisons)
    ):
        raise HistoricalPrefixSuccessWindowsUnavailableError(
            "temporal holdout comparison family is inconsistent"
        )
    return HistoricalPrefixTemporalHoldoutResult(
        metadata=source.metadata,
        strategy=strategy.identity,
        criterion=_criterion_identity(criterion),
        prefix_count=prefix_count,
        split=HistoricalPrefixTemporalHoldoutSplit(
            split_method=TEMPORAL_HOLDOUT_SPLIT_METHOD,
            total_assignment_count=total_count,
            warmup_count=warmup_count,
            discovery_count=len(discovery_assignments),
            confirmation_count=len(confirmation_assignments),
            discovery_first_target=discovery_assignments[0].target,
            discovery_last_target=discovery_assignments[-1].target,
            confirmation_first_target=confirmation_assignments[0].target,
            confirmation_last_target=confirmation_assignments[-1].target,
        ),
        evaluation_status=HistoricalPrefixTemporalHoldoutStatus.COMPLETE,
        family_size=64,
        discovery=discovery,
        confirmation=confirmation,
        comparisons=comparisons,
    )


def _recent_50_stability_audit(
    *,
    source: HistoricalPrefixSuccessWindowSource,
    strategy: HistoricalPrefixSuccessSourceStrategy,
    prefix_count: int,
    criterion: HistoricalPrefixSuccessCriterion,
    assignments: tuple[HistoricalPrefixWalkForwardAssignment, ...],
    temporal_holdout: HistoricalPrefixTemporalHoldoutResult | None = None,
) -> HistoricalPrefixRecentStabilityAuditResult:
    if temporal_holdout is None:
        temporal_holdout = _temporal_holdout(
            source=source,
            strategy=strategy,
            prefix_count=prefix_count,
            criterion=criterion,
            assignments=assignments,
        )
    elif (
        temporal_holdout.metadata != source.metadata
        or temporal_holdout.strategy != strategy.identity
        or temporal_holdout.prefix_count != prefix_count
        or temporal_holdout.criterion != _criterion_identity(criterion)
    ):
        raise HistoricalPrefixSuccessWindowsUnavailableError(
            "supplied temporal holdout does not match recent audit identity"
        )
    temporal_split = temporal_holdout.split
    if (
        temporal_holdout.evaluation_status
        is HistoricalPrefixTemporalHoldoutStatus.NOT_READY_INSUFFICIENT_HISTORY
    ):
        return HistoricalPrefixRecentStabilityAuditResult(
            metadata=source.metadata,
            strategy=strategy.identity,
            criterion=_criterion_identity(criterion),
            prefix_count=prefix_count,
            split=HistoricalPrefixRecentStabilityAuditSplit(
                source_temporal_split_method=TEMPORAL_HOLDOUT_SPLIT_METHOD,
                audit_split_method=RECENT_AUDIT_SPLIT_METHOD,
                total_assignment_count=temporal_split.total_assignment_count,
                warmup_count=temporal_split.warmup_count,
                discovery_count=0,
                confirmation_count=0,
                reference_count=0,
                recent_count=0,
                discovery_first_target=None,
                discovery_last_target=None,
                confirmation_first_target=None,
                confirmation_last_target=None,
                reference_first_target=None,
                reference_last_target=None,
                recent_first_target=None,
                recent_last_target=None,
            ),
            audit_status=HistoricalPrefixRecentStabilityAuditStatus.NOT_READY_INSUFFICIENT_HISTORY,
            family_size=64,
            reference=None,
            recent=None,
            comparisons=(),
        )

    total_count = len(assignments)
    confirmation_start = total_count - CONFIRMATION_TARGET_COUNT
    recent_start = total_count - RECENT_AUDIT_TARGET_COUNT
    confirmation_assignments = assignments[confirmation_start:]
    reference_assignments = assignments[confirmation_start:recent_start]
    recent_assignments = assignments[recent_start:]
    if (
        len(confirmation_assignments) != CONFIRMATION_TARGET_COUNT
        or len(reference_assignments) != RECENT_REFERENCE_TARGET_COUNT
        or len(recent_assignments) != RECENT_AUDIT_TARGET_COUNT
        or reference_assignments + recent_assignments != confirmation_assignments
        or reference_assignments[-1].chronological_index
        >= recent_assignments[0].chronological_index
        or set(reference_assignments).intersection(recent_assignments)
    ):
        raise HistoricalPrefixSuccessWindowsUnavailableError(
            "fixed recent stability audit partition is inconsistent"
        )

    reference = _feature_cohort_diagnostics(
        _feature_cohorts_from_assignments(
            source=source,
            strategy=strategy,
            prefix_count=prefix_count,
            criterion=criterion,
            assignments=reference_assignments,
        )
    )
    recent = _feature_cohort_diagnostics(
        _feature_cohorts_from_assignments(
            source=source,
            strategy=strategy,
            prefix_count=prefix_count,
            criterion=criterion,
            assignments=recent_assignments,
        )
    )
    comparisons = tuple(
        HistoricalPrefixRecentStabilityAuditCohortComparison(
            cohort_index=index,
            feature_key=reference_diagnostic.feature_key,
            reference_diagnostic=reference_diagnostic,
            recent_diagnostic=recent_diagnostic,
            effect_change=_effect_change(
                reference_diagnostic.risk_difference,
                recent_diagnostic.risk_difference,
            ),
            relationship=_temporal_relationship(
                reference_diagnostic.relation_vs_outside,
                recent_diagnostic.relation_vs_outside,
            ),
        )
        for index, (reference_diagnostic, recent_diagnostic) in enumerate(
            zip(reference.diagnostics, recent.diagnostics, strict=True)
        )
    )
    if (
        len(comparisons) != 64
        or any(
            comparison.cohort_index != index
            or comparison.feature_key != comparison.reference_diagnostic.feature_key
            or comparison.feature_key != comparison.recent_diagnostic.feature_key
            for index, comparison in enumerate(comparisons)
        )
        or temporal_split.discovery_first_target is None
        or temporal_split.discovery_last_target is None
        or temporal_split.confirmation_first_target is None
        or temporal_split.confirmation_last_target is None
    ):
        raise HistoricalPrefixSuccessWindowsUnavailableError(
            "recent stability audit comparison family is inconsistent"
        )
    return HistoricalPrefixRecentStabilityAuditResult(
        metadata=source.metadata,
        strategy=strategy.identity,
        criterion=_criterion_identity(criterion),
        prefix_count=prefix_count,
        split=HistoricalPrefixRecentStabilityAuditSplit(
            source_temporal_split_method=temporal_split.split_method,
            audit_split_method=RECENT_AUDIT_SPLIT_METHOD,
            total_assignment_count=total_count,
            warmup_count=temporal_split.warmup_count,
            discovery_count=temporal_split.discovery_count,
            confirmation_count=temporal_split.confirmation_count,
            reference_count=len(reference_assignments),
            recent_count=len(recent_assignments),
            discovery_first_target=temporal_split.discovery_first_target,
            discovery_last_target=temporal_split.discovery_last_target,
            confirmation_first_target=temporal_split.confirmation_first_target,
            confirmation_last_target=temporal_split.confirmation_last_target,
            reference_first_target=reference_assignments[0].target,
            reference_last_target=reference_assignments[-1].target,
            recent_first_target=recent_assignments[0].target,
            recent_last_target=recent_assignments[-1].target,
        ),
        audit_status=HistoricalPrefixRecentStabilityAuditStatus.COMPLETE,
        family_size=64,
        reference=reference,
        recent=recent,
        comparisons=comparisons,
    )


def _cross_import_pair_status(
    left: HistoricalPrefixTemporalHoldoutStatus,
    right: HistoricalPrefixTemporalHoldoutStatus,
) -> HistoricalPrefixCrossImportPairStatus:
    left_ready = left is HistoricalPrefixTemporalHoldoutStatus.COMPLETE
    right_ready = right is HistoricalPrefixTemporalHoldoutStatus.COMPLETE
    if left_ready and right_ready:
        return HistoricalPrefixCrossImportPairStatus.COMPLETE
    if not left_ready and not right_ready:
        return HistoricalPrefixCrossImportPairStatus.BOTH_NOT_READY
    if not left_ready:
        return HistoricalPrefixCrossImportPairStatus.LEFT_NOT_READY
    return HistoricalPrefixCrossImportPairStatus.RIGHT_NOT_READY


def _confirmation_target_overlap(
    left_assignments: tuple[HistoricalPrefixWalkForwardAssignment, ...],
    right_assignments: tuple[HistoricalPrefixWalkForwardAssignment, ...],
) -> HistoricalPrefixConfirmationTargetOverlap:
    left_targets = tuple(
        assignment.target.draw_sha256
        for assignment in left_assignments[-CONFIRMATION_TARGET_COUNT:]
    )
    right_targets = tuple(
        assignment.target.draw_sha256
        for assignment in right_assignments[-CONFIRMATION_TARGET_COUNT:]
    )
    if (
        len(left_targets) != CONFIRMATION_TARGET_COUNT
        or len(right_targets) != CONFIRMATION_TARGET_COUNT
        or len(set(left_targets)) != CONFIRMATION_TARGET_COUNT
        or len(set(right_targets)) != CONFIRMATION_TARGET_COUNT
    ):
        raise HistoricalPrefixSuccessWindowsUnavailableError(
            "confirmation targets must contain 300 distinct exact draw identities per import"
        )
    left_set = set(left_targets)
    right_set = set(right_targets)
    overlap_count = len(left_set & right_set)
    if overlap_count == 0:
        relation = HistoricalPrefixConfirmationOverlapRelation.DISJOINT
    elif left_set == right_set:
        relation = HistoricalPrefixConfirmationOverlapRelation.IDENTICAL
    else:
        relation = HistoricalPrefixConfirmationOverlapRelation.PARTIAL_OVERLAP
    return HistoricalPrefixConfirmationTargetOverlap(
        left_confirmation_target_count=len(left_set),
        right_confirmation_target_count=len(right_set),
        overlap_count=overlap_count,
        left_only_count=len(left_set - right_set),
        right_only_count=len(right_set - left_set),
        relation=relation,
    )


def _cross_import_comparisons(
    left: HistoricalPrefixTemporalHoldoutResult,
    right: HistoricalPrefixTemporalHoldoutResult,
) -> tuple[HistoricalPrefixCrossImportCohortComparison, ...]:
    if left.confirmation is None or right.confirmation is None:
        raise HistoricalPrefixSuccessWindowsUnavailableError(
            "complete cross-import concordance requires both confirmation families"
        )
    comparisons = tuple(
        HistoricalPrefixCrossImportCohortComparison(
            cohort_index=index,
            feature_key=left_diagnostic.feature_key,
            left_confirmation_diagnostic=left_diagnostic,
            right_confirmation_diagnostic=right_diagnostic,
            effect_change=_effect_change(
                left_diagnostic.risk_difference,
                right_diagnostic.risk_difference,
            ),
            relationship=_temporal_relationship(
                left_diagnostic.relation_vs_outside,
                right_diagnostic.relation_vs_outside,
            ),
        )
        for index, (left_diagnostic, right_diagnostic) in enumerate(
            zip(
                left.confirmation.diagnostics,
                right.confirmation.diagnostics,
                strict=True,
            )
        )
    )
    if len(comparisons) != 64 or any(
        comparison.cohort_index != index
        or comparison.feature_key != comparison.left_confirmation_diagnostic.feature_key
        or comparison.feature_key != comparison.right_confirmation_diagnostic.feature_key
        for index, comparison in enumerate(comparisons)
    ):
        raise HistoricalPrefixSuccessWindowsUnavailableError(
            "cross-import confirmation comparison family is inconsistent"
        )
    return comparisons


def _multi_import_census_status(
    holdouts: tuple[HistoricalPrefixTemporalHoldoutResult, ...],
) -> HistoricalPrefixMultiImportCensusStatus:
    ready_count = sum(
        holdout.evaluation_status is HistoricalPrefixTemporalHoldoutStatus.COMPLETE
        for holdout in holdouts
    )
    if ready_count == len(holdouts):
        return HistoricalPrefixMultiImportCensusStatus.COMPLETE
    if ready_count == 0:
        return HistoricalPrefixMultiImportCensusStatus.ALL_NOT_READY
    return HistoricalPrefixMultiImportCensusStatus.PARTIAL_NOT_READY


def _multi_import_census_summary(
    *,
    import_count: int,
    higher_count: int,
    equal_count: int,
    lower_count: int,
    unavailable_count: int,
) -> HistoricalPrefixMultiImportCensusSummary:
    if higher_count + equal_count + lower_count + unavailable_count != import_count:
        raise HistoricalPrefixSuccessWindowsUnavailableError(
            "multi-import census direction counts are inconsistent"
        )
    if unavailable_count == import_count:
        return HistoricalPrefixMultiImportCensusSummary.NO_AVAILABLE_EFFECT
    if unavailable_count > 0:
        return HistoricalPrefixMultiImportCensusSummary.PARTIAL_AVAILABILITY
    if higher_count == import_count:
        return HistoricalPrefixMultiImportCensusSummary.ALL_AVAILABLE_HIGHER
    if equal_count == import_count:
        return HistoricalPrefixMultiImportCensusSummary.ALL_AVAILABLE_EQUAL
    if lower_count == import_count:
        return HistoricalPrefixMultiImportCensusSummary.ALL_AVAILABLE_LOWER
    return HistoricalPrefixMultiImportCensusSummary.MIXED_AVAILABLE


def _multi_import_pairs(
    *,
    sources: tuple[HistoricalPrefixSuccessWindowSource, ...],
    assignments: tuple[tuple[HistoricalPrefixWalkForwardAssignment, ...], ...],
    holdouts: tuple[HistoricalPrefixTemporalHoldoutResult, ...],
) -> tuple[HistoricalPrefixMultiImportPairResult, ...]:
    pairs = tuple(
        HistoricalPrefixMultiImportPairResult(
            left_import_index=left_index,
            right_import_index=right_index,
            metadata=HistoricalPrefixCrossImportMetadata(
                left=sources[left_index].metadata,
                right=sources[right_index].metadata,
                same_dataset_sha256=(
                    sources[left_index].metadata.dataset_sha256
                    == sources[right_index].metadata.dataset_sha256
                ),
                same_source_artifact_sha256=(
                    sources[left_index].metadata.source_artifact_sha256
                    == sources[right_index].metadata.source_artifact_sha256
                ),
            ),
            pair_status=_cross_import_pair_status(
                holdouts[left_index].evaluation_status,
                holdouts[right_index].evaluation_status,
            ),
            left_holdout_status=holdouts[left_index].evaluation_status,
            right_holdout_status=holdouts[right_index].evaluation_status,
            confirmation_target_overlap=(
                _confirmation_target_overlap(
                    assignments[left_index],
                    assignments[right_index],
                )
                if (
                    holdouts[left_index].evaluation_status
                    is HistoricalPrefixTemporalHoldoutStatus.COMPLETE
                    and holdouts[right_index].evaluation_status
                    is HistoricalPrefixTemporalHoldoutStatus.COMPLETE
                )
                else None
            ),
        )
        for left_index in range(len(sources))
        for right_index in range(left_index + 1, len(sources))
    )
    expected_count = len(sources) * (len(sources) - 1) // 2
    if len(pairs) != expected_count:
        raise HistoricalPrefixSuccessWindowsUnavailableError(
            "multi-import pair matrix cardinality is inconsistent"
        )
    return pairs


def _multi_import_cohort_census(
    sources: tuple[HistoricalPrefixSuccessWindowSource, ...],
    holdouts: tuple[HistoricalPrefixTemporalHoldoutResult, ...],
) -> tuple[HistoricalPrefixMultiImportCohortCensusRow, ...]:
    confirmations = tuple(holdout.confirmation for holdout in holdouts)
    if any(confirmation is None for confirmation in confirmations):
        raise HistoricalPrefixSuccessWindowsUnavailableError(
            "complete multi-import census requires every confirmation family"
        )
    diagnostics_by_import = tuple(
        confirmation.diagnostics
        for confirmation in confirmations
        if confirmation is not None
    )
    if len(diagnostics_by_import) != len(holdouts) or any(
        len(diagnostics) != 64 for diagnostics in diagnostics_by_import
    ):
        raise HistoricalPrefixSuccessWindowsUnavailableError(
            "multi-import confirmation families are inconsistent"
        )

    rows: list[HistoricalPrefixMultiImportCohortCensusRow] = []
    for cohort_index in range(64):
        diagnostics = tuple(
            HistoricalPrefixMultiImportConfirmationDiagnostic(
                import_index=import_index,
                import_identity_sha256=sources[import_index].metadata.import_identity_sha256,
                diagnostic=import_diagnostics[cohort_index],
            )
            for import_index, import_diagnostics in enumerate(diagnostics_by_import)
        )
        feature_key = diagnostics[0].diagnostic.feature_key
        if any(
            item.import_index != import_index
            or item.import_identity_sha256
            != sources[import_index].metadata.import_identity_sha256
            or item.diagnostic.cohort_index != cohort_index
            or item.diagnostic.feature_key != feature_key
            for import_index, item in enumerate(diagnostics)
        ):
            raise HistoricalPrefixSuccessWindowsUnavailableError(
                "multi-import confirmation cohort identity is inconsistent"
            )
        higher_count = sum(
            item.diagnostic.relation_vs_outside is HistoricalPrefixRateRelation.HIGHER
            for item in diagnostics
        )
        equal_count = sum(
            item.diagnostic.relation_vs_outside is HistoricalPrefixRateRelation.EQUAL
            for item in diagnostics
        )
        lower_count = sum(
            item.diagnostic.relation_vs_outside is HistoricalPrefixRateRelation.LOWER
            for item in diagnostics
        )
        unavailable_count = sum(
            item.diagnostic.relation_vs_outside is HistoricalPrefixRateRelation.UNAVAILABLE
            for item in diagnostics
        )
        rows.append(
            HistoricalPrefixMultiImportCohortCensusRow(
                cohort_index=cohort_index,
                feature_key=feature_key,
                confirmation_diagnostics=diagnostics,
                higher_count=higher_count,
                equal_count=equal_count,
                lower_count=lower_count,
                unavailable_count=unavailable_count,
                summary=_multi_import_census_summary(
                    import_count=len(diagnostics),
                    higher_count=higher_count,
                    equal_count=equal_count,
                    lower_count=lower_count,
                    unavailable_count=unavailable_count,
                ),
            )
        )
    return tuple(rows)


def _matrix_cell(
    result: HistoricalPrefixStrategySuccessWindowResult,
) -> HistoricalPrefixStrategySuccessMatrixCell:
    return HistoricalPrefixStrategySuccessMatrixCell(
        criterion=result.criterion,
        prefix_count=result.prefix_count,
        selection=result.selection,
        status=result.status,
        source_observation_count=result.source_observation_count,
        windows=result.windows,
        comparisons=_rate_comparisons(result.windows) if result.windows else (),
    )


def _find_exact_strategy(
    source: HistoricalPrefixSuccessWindowSource,
    *,
    strategy_id: str,
    strategy_version: str,
    replicate: int,
) -> HistoricalPrefixSuccessSourceStrategy:
    strategy = next(
        (
            candidate
            for candidate in source.strategies
            if candidate.identity.strategy_id == strategy_id
            and candidate.identity.strategy_version == strategy_version
            and candidate.identity.replicate == replicate
        ),
        None,
    )
    if strategy is None:
        raise HistoricalPrefixSuccessStrategyNotFoundError(
            "exact Historical Prefix strategy descriptor was not found"
        )
    return strategy


class EvaluateHistoricalPrefixSuccessWindows:
    """Load one exact import once and expose descriptive strategy windows."""

    def __init__(self, reader_factory: HistoricalPrefixSuccessWindowSourceReaderFactory) -> None:
        self._reader_factory = reader_factory

    @staticmethod
    def _load_with_reader(
        reader: HistoricalPrefixSuccessWindowSourceReader,
        import_identity_sha256: str,
    ) -> HistoricalPrefixSuccessWindowSource:
        source = reader.load_source(import_identity_sha256)
        if source is None:
            raise HistoricalPrefixSuccessImportNotFoundError(
                "exact persisted historical import was not found"
            )
        if type(source) is not HistoricalPrefixSuccessWindowSource:
            raise HistoricalPrefixSuccessWindowsUnavailableError(
                "reader returned a malformed Historical Prefix source"
            )
        if source.metadata.import_identity_sha256 != import_identity_sha256:
            raise HistoricalPrefixSuccessWindowsUnavailableError(
                "reader returned a different persisted import identity"
            )
        return source

    def _load(self, import_identity_sha256: str) -> HistoricalPrefixSuccessWindowSource:
        return self._load_with_reader(self._reader_factory(), import_identity_sha256)

    def list_strategies(
        self,
        *,
        import_identity_sha256: str,
        prefix_count: int,
        criterion: HistoricalPrefixSuccessCriterion,
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = DEFAULT_PAGE_OFFSET,
    ) -> HistoricalPrefixStrategySuccessWindowPage:
        _validate_import_identity(import_identity_sha256)
        _validate_prefix_count(prefix_count)
        _validate_criterion(criterion)
        _validate_pagination(limit, offset)
        source = self._load(import_identity_sha256)
        selected = source.strategies[offset : offset + limit]
        return HistoricalPrefixStrategySuccessWindowPage(
            metadata=source.metadata,
            criterion=_criterion_identity(criterion),
            prefix_count=prefix_count,
            total_count=len(source.strategies),
            limit=limit,
            offset=offset,
            items=tuple(
                _evaluate_strategy(
                    source=source,
                    strategy=strategy,
                    prefix_count=prefix_count,
                    criterion=criterion,
                )
                for strategy in selected
            ),
        )

    def get_strategy(
        self,
        *,
        import_identity_sha256: str,
        strategy_id: str,
        strategy_version: str,
        replicate: int,
        prefix_count: int,
        criterion: HistoricalPrefixSuccessCriterion,
    ) -> HistoricalPrefixStrategySuccessWindowResult:
        _validate_import_identity(import_identity_sha256)
        _validate_strategy_axis(strategy_id, "strategy_id")
        _validate_strategy_axis(strategy_version, "strategy_version")
        if type(replicate) is not int or replicate < 1:
            raise _contract_error("replicate must be an integer >= 1")
        _validate_prefix_count(prefix_count)
        _validate_criterion(criterion)
        source = self._load(import_identity_sha256)
        strategy = _find_exact_strategy(
            source,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            replicate=replicate,
        )
        return _evaluate_strategy(
            source=source,
            strategy=strategy,
            prefix_count=prefix_count,
            criterion=criterion,
        )

    def get_matrix(
        self,
        *,
        import_identity_sha256: str,
        strategy_id: str,
        strategy_version: str,
        replicate: int,
    ) -> HistoricalPrefixStrategySuccessMatrix:
        _validate_import_identity(import_identity_sha256)
        _validate_strategy_axis(strategy_id, "strategy_id")
        _validate_strategy_axis(strategy_version, "strategy_version")
        if type(replicate) is not int or replicate < 1:
            raise _contract_error("replicate must be an integer >= 1")
        source = self._load(import_identity_sha256)
        strategy = _find_exact_strategy(
            source,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            replicate=replicate,
        )
        criteria = tuple(_criterion_identity(criterion) for criterion in SUPPORTED_SUCCESS_CRITERIA)
        cells = tuple(
            _matrix_cell(
                _evaluate_strategy(
                    source=source,
                    strategy=strategy,
                    prefix_count=prefix_count,
                    criterion=criterion,
                )
            )
            for criterion in SUPPORTED_SUCCESS_CRITERIA
            for prefix_count in SUPPORTED_PREFIX_COUNTS
        )
        return HistoricalPrefixStrategySuccessMatrix(
            metadata=source.metadata,
            strategy=strategy.identity,
            source_observation_count=len(strategy.observations),
            prefix_counts=SUPPORTED_PREFIX_COUNTS,
            criteria=criteria,
            cell_count=len(cells),
            cells=cells,
        )

    def get_feature_cohorts(
        self,
        *,
        import_identity_sha256: str,
        strategy_id: str,
        strategy_version: str,
        replicate: int,
        prefix_count: int,
        criterion: HistoricalPrefixSuccessCriterion,
    ) -> HistoricalPrefixStrategyFeatureCohortResult:
        _validate_import_identity(import_identity_sha256)
        _validate_strategy_axis(strategy_id, "strategy_id")
        _validate_strategy_axis(strategy_version, "strategy_version")
        if type(replicate) is not int or replicate < 1:
            raise _contract_error("replicate must be an integer >= 1")
        _validate_prefix_count(prefix_count)
        _validate_criterion(criterion)
        source = self._load(import_identity_sha256)
        strategy = _find_exact_strategy(
            source,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            replicate=replicate,
        )
        return _feature_cohorts(
            source=source,
            strategy=strategy,
            prefix_count=prefix_count,
            criterion=criterion,
        )

    def get_feature_cohort_diagnostics(
        self,
        *,
        import_identity_sha256: str,
        strategy_id: str,
        strategy_version: str,
        replicate: int,
        prefix_count: int,
        criterion: HistoricalPrefixSuccessCriterion,
    ) -> HistoricalPrefixStrategyFeatureCohortDiagnostics:
        _validate_import_identity(import_identity_sha256)
        _validate_strategy_axis(strategy_id, "strategy_id")
        _validate_strategy_axis(strategy_version, "strategy_version")
        if type(replicate) is not int or replicate < 1:
            raise _contract_error("replicate must be an integer >= 1")
        _validate_prefix_count(prefix_count)
        _validate_criterion(criterion)
        source = self._load(import_identity_sha256)
        strategy = _find_exact_strategy(
            source,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            replicate=replicate,
        )
        cohorts = _feature_cohorts(
            source=source,
            strategy=strategy,
            prefix_count=prefix_count,
            criterion=criterion,
        )
        return _feature_cohort_diagnostics(cohorts)

    def get_feature_cohort_temporal_holdout(
        self,
        *,
        import_identity_sha256: str,
        strategy_id: str,
        strategy_version: str,
        replicate: int,
        prefix_count: int,
        criterion: HistoricalPrefixSuccessCriterion,
    ) -> HistoricalPrefixTemporalHoldoutResult:
        _validate_import_identity(import_identity_sha256)
        _validate_strategy_axis(strategy_id, "strategy_id")
        _validate_strategy_axis(strategy_version, "strategy_version")
        if type(replicate) is not int or replicate < 1:
            raise _contract_error("replicate must be an integer >= 1")
        _validate_prefix_count(prefix_count)
        _validate_criterion(criterion)
        source = self._load(import_identity_sha256)
        strategy = _find_exact_strategy(
            source,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            replicate=replicate,
        )
        return _temporal_holdout(
            source=source,
            strategy=strategy,
            prefix_count=prefix_count,
            criterion=criterion,
        )

    def get_feature_cohort_recent_50_stability_audit(
        self,
        *,
        import_identity_sha256: str,
        strategy_id: str,
        strategy_version: str,
        replicate: int,
        prefix_count: int,
        criterion: HistoricalPrefixSuccessCriterion,
    ) -> HistoricalPrefixRecentStabilityAuditResult:
        _validate_import_identity(import_identity_sha256)
        _validate_strategy_axis(strategy_id, "strategy_id")
        _validate_strategy_axis(strategy_version, "strategy_version")
        if type(replicate) is not int or replicate < 1:
            raise _contract_error("replicate must be an integer >= 1")
        _validate_prefix_count(prefix_count)
        _validate_criterion(criterion)
        source = self._load(import_identity_sha256)
        strategy = _find_exact_strategy(
            source,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            replicate=replicate,
        )
        assignments = _build_walk_forward_assignments(
            source=source,
            strategy=strategy,
            prefix_count=prefix_count,
            criterion=criterion,
        )
        return _recent_50_stability_audit(
            source=source,
            strategy=strategy,
            prefix_count=prefix_count,
            criterion=criterion,
            assignments=assignments,
        )

    def get_cross_import_concordance(
        self,
        *,
        left_import_identity_sha256: str,
        right_import_identity_sha256: str,
        strategy_id: str,
        strategy_version: str,
        replicate: int,
        prefix_count: int,
        criterion: HistoricalPrefixSuccessCriterion,
    ) -> HistoricalPrefixCrossImportConcordanceResult:
        _validate_import_identity(left_import_identity_sha256)
        _validate_import_identity(right_import_identity_sha256)
        if left_import_identity_sha256 == right_import_identity_sha256:
            raise _contract_error("left and right import identities must be distinct")
        _validate_strategy_axis(strategy_id, "strategy_id")
        _validate_strategy_axis(strategy_version, "strategy_version")
        if type(replicate) is not int or replicate < 1:
            raise _contract_error("replicate must be an integer >= 1")
        _validate_prefix_count(prefix_count)
        _validate_criterion(criterion)

        reader = self._reader_factory()
        left_source = self._load_with_reader(reader, left_import_identity_sha256)
        right_source = self._load_with_reader(reader, right_import_identity_sha256)
        left_strategy = _find_exact_strategy(
            left_source,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            replicate=replicate,
        )
        right_strategy = _find_exact_strategy(
            right_source,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            replicate=replicate,
        )
        if left_strategy.identity != right_strategy.identity:
            raise HistoricalPrefixSuccessWindowsUnavailableError(
                "cross-import exact strategy identities do not match"
            )

        left_assignments = _build_walk_forward_assignments(
            source=left_source,
            strategy=left_strategy,
            prefix_count=prefix_count,
            criterion=criterion,
        )
        right_assignments = _build_walk_forward_assignments(
            source=right_source,
            strategy=right_strategy,
            prefix_count=prefix_count,
            criterion=criterion,
        )
        left_holdout = _temporal_holdout(
            source=left_source,
            strategy=left_strategy,
            prefix_count=prefix_count,
            criterion=criterion,
            assignments=left_assignments,
        )
        right_holdout = _temporal_holdout(
            source=right_source,
            strategy=right_strategy,
            prefix_count=prefix_count,
            criterion=criterion,
            assignments=right_assignments,
        )
        pair_status = _cross_import_pair_status(
            left_holdout.evaluation_status,
            right_holdout.evaluation_status,
        )
        complete = pair_status is HistoricalPrefixCrossImportPairStatus.COMPLETE
        return HistoricalPrefixCrossImportConcordanceResult(
            metadata=HistoricalPrefixCrossImportMetadata(
                left=left_source.metadata,
                right=right_source.metadata,
                same_dataset_sha256=(
                    left_source.metadata.dataset_sha256
                    == right_source.metadata.dataset_sha256
                ),
                same_source_artifact_sha256=(
                    left_source.metadata.source_artifact_sha256
                    == right_source.metadata.source_artifact_sha256
                ),
            ),
            strategy=left_strategy.identity,
            criterion=_criterion_identity(criterion),
            prefix_count=prefix_count,
            pair_status=pair_status,
            left_holdout_status=left_holdout.evaluation_status,
            right_holdout_status=right_holdout.evaluation_status,
            confirmation_target_overlap=(
                _confirmation_target_overlap(left_assignments, right_assignments)
                if complete
                else None
            ),
            comparisons=(
                _cross_import_comparisons(left_holdout, right_holdout)
                if complete
                else ()
            ),
        )

    def get_multi_import_concordance_census(
        self,
        *,
        import_identity_sha256s: tuple[str, ...],
        strategy_id: str,
        strategy_version: str,
        replicate: int,
        prefix_count: int,
        criterion: HistoricalPrefixSuccessCriterion,
    ) -> HistoricalPrefixMultiImportConcordanceCensusResult:
        _validate_import_identities(import_identity_sha256s)
        _validate_strategy_axis(strategy_id, "strategy_id")
        _validate_strategy_axis(strategy_version, "strategy_version")
        if type(replicate) is not int or replicate < 1:
            raise _contract_error("replicate must be an integer >= 1")
        _validate_prefix_count(prefix_count)
        _validate_criterion(criterion)

        reader = self._reader_factory()
        sources = tuple(
            self._load_with_reader(reader, import_identity_sha256)
            for import_identity_sha256 in import_identity_sha256s
        )
        strategies = tuple(
            _find_exact_strategy(
                source,
                strategy_id=strategy_id,
                strategy_version=strategy_version,
                replicate=replicate,
            )
            for source in sources
        )
        if any(strategy.identity != strategies[0].identity for strategy in strategies[1:]):
            raise HistoricalPrefixSuccessWindowsUnavailableError(
                "multi-import exact strategy identities do not match"
            )
        assignments = tuple(
            _build_walk_forward_assignments(
                source=source,
                strategy=strategy,
                prefix_count=prefix_count,
                criterion=criterion,
            )
            for source, strategy in zip(sources, strategies, strict=True)
        )
        holdouts = tuple(
            _temporal_holdout(
                source=source,
                strategy=strategy,
                prefix_count=prefix_count,
                criterion=criterion,
                assignments=source_assignments,
            )
            for source, strategy, source_assignments in zip(
                sources,
                strategies,
                assignments,
                strict=True,
            )
        )
        census_status = _multi_import_census_status(holdouts)
        pairs = _multi_import_pairs(
            sources=sources,
            assignments=assignments,
            holdouts=holdouts,
        )
        cohort_census = (
            _multi_import_cohort_census(sources, holdouts)
            if census_status is HistoricalPrefixMultiImportCensusStatus.COMPLETE
            else ()
        )
        return HistoricalPrefixMultiImportConcordanceCensusResult(
            imports=tuple(
                HistoricalPrefixMultiImportSourceResult(
                    metadata=source.metadata,
                    holdout_status=holdout.evaluation_status,
                )
                for source, holdout in zip(sources, holdouts, strict=True)
            ),
            strategy=strategies[0].identity,
            criterion=_criterion_identity(criterion),
            prefix_count=prefix_count,
            census_status=census_status,
            pair_count=len(pairs),
            pairs=pairs,
            cohort_census_count=len(cohort_census),
            cohort_census=cohort_census,
        )

    def get_research_qualification(
        self,
        *,
        import_identity_sha256s: tuple[str, ...],
        strategy_id: str,
        strategy_version: str,
        replicate: int,
        prefix_count: int,
        criterion: HistoricalPrefixSuccessCriterion,
    ) -> HistoricalSuccessResearchQualification:
        _validate_import_identities(import_identity_sha256s)
        _validate_strategy_axis(strategy_id, "strategy_id")
        _validate_strategy_axis(strategy_version, "strategy_version")
        if type(replicate) is not int or replicate < 1:
            raise _contract_error("replicate must be an integer >= 1")
        _validate_prefix_count(prefix_count)
        _validate_criterion(criterion)

        reader = self._reader_factory()
        sources = tuple(
            self._load_with_reader(reader, import_identity_sha256)
            for import_identity_sha256 in import_identity_sha256s
        )
        strategies = tuple(
            _find_exact_strategy(
                source,
                strategy_id=strategy_id,
                strategy_version=strategy_version,
                replicate=replicate,
            )
            for source in sources
        )
        if any(strategy.identity != strategies[0].identity for strategy in strategies[1:]):
            raise HistoricalPrefixSuccessWindowsUnavailableError(
                "multi-import exact strategy identities do not match"
            )
        window_results = tuple(
            _evaluate_strategy(
                source=source,
                strategy=strategy,
                prefix_count=prefix_count,
                criterion=criterion,
            )
            for source, strategy in zip(sources, strategies, strict=True)
        )
        assignments = tuple(
            _build_walk_forward_assignments(
                source=source,
                strategy=strategy,
                prefix_count=prefix_count,
                criterion=criterion,
            )
            for source, strategy in zip(sources, strategies, strict=True)
        )
        holdouts = tuple(
            _temporal_holdout(
                source=source,
                strategy=strategy,
                prefix_count=prefix_count,
                criterion=criterion,
                assignments=source_assignments,
            )
            for source, strategy, source_assignments in zip(
                sources,
                strategies,
                assignments,
                strict=True,
            )
        )
        recent_audits = tuple(
            _recent_50_stability_audit(
                source=source,
                strategy=strategy,
                prefix_count=prefix_count,
                criterion=criterion,
                assignments=source_assignments,
                temporal_holdout=holdout,
            )
            for source, strategy, source_assignments, holdout in zip(
                sources,
                strategies,
                assignments,
                holdouts,
                strict=True,
            )
        )
        census_status = _multi_import_census_status(holdouts)
        pairs = _multi_import_pairs(
            sources=sources,
            assignments=assignments,
            holdouts=holdouts,
        )
        cohort_census = (
            _multi_import_cohort_census(sources, holdouts)
            if census_status is HistoricalPrefixMultiImportCensusStatus.COMPLETE
            else ()
        )

        import_evidence = tuple(
            HistoricalSuccessQualificationImportEvidence(
                import_index=index,
                import_identity_sha256=source.metadata.import_identity_sha256,
                dataset_sha256=source.metadata.dataset_sha256,
                source_artifact_sha256=source.metadata.source_artifact_sha256,
                source_observation_count=len(strategy.observations),
                strategy_window_status=(
                    HistoricalSuccessQualificationEvidenceStatus.COMPLETE
                    if (
                        window_result.status
                        is HistoricalPrefixSuccessEvaluationStatus.EVALUATED
                        and all(
                            window.evaluation_status
                            is WindowEvaluationStatus.COMPLETE
                            for window in window_result.windows
                        )
                    )
                    else HistoricalSuccessQualificationEvidenceStatus.NOT_READY
                ),
                temporal_holdout_status=(
                    HistoricalSuccessQualificationEvidenceStatus.COMPLETE
                    if holdout.evaluation_status
                    is HistoricalPrefixTemporalHoldoutStatus.COMPLETE
                    else HistoricalSuccessQualificationEvidenceStatus.NOT_READY
                ),
                recent_audit_status=(
                    HistoricalSuccessQualificationEvidenceStatus.COMPLETE
                    if recent.audit_status
                    is HistoricalPrefixRecentStabilityAuditStatus.COMPLETE
                    else HistoricalSuccessQualificationEvidenceStatus.NOT_READY
                ),
                recent_relationship_difference_count=sum(
                    comparison.relationship
                    is HistoricalPrefixTemporalHoldoutRelationship.DIFFERENT
                    for comparison in recent.comparisons
                ),
            )
            for index, (source, strategy, window_result, holdout, recent) in enumerate(
                zip(
                    sources,
                    strategies,
                    window_results,
                    holdouts,
                    recent_audits,
                    strict=True,
                )
            )
        )
        pair_inputs = tuple(
            HistoricalSuccessQualificationPairInput(
                left_import_index=pair.left_import_index,
                right_import_index=pair.right_import_index,
                pair_status=HistoricalSuccessQualificationPairStatus(
                    pair.pair_status.value
                ),
                confirmation_overlap_relation=(
                    HistoricalSuccessQualificationOverlapRelation(
                        pair.confirmation_target_overlap.relation.value
                    )
                    if pair.confirmation_target_overlap is not None
                    else None
                ),
            )
            for pair in pairs
        )
        strategy = strategies[0].identity
        return qualify_historical_success(
            identity=HistoricalSuccessQualificationIdentity(
                strategy_id=strategy.strategy_id,
                strategy_version=strategy.strategy_version,
                replicate=strategy.replicate,
                prefix_count=prefix_count,
                criterion=criterion.value,
            ),
            imports=import_evidence,
            pairs=pair_inputs,
            census_status=HistoricalSuccessQualificationCensusStatus(
                census_status.value
            ),
            cohort_census_count=len(cohort_census),
            cohort_summaries=tuple(
                HistoricalSuccessQualificationCensusSummary(row.summary.value)
                for row in cohort_census
            ),
        )


__all__ = ["EvaluateHistoricalPrefixSuccessWindows"]
