"""Evaluate exact persisted Historical Prefix portfolios as success windows."""

from __future__ import annotations

import re
from datetime import date
from math import gcd

from lottolab.application.historical_prefix_success_windows import (
    DEFAULT_PAGE_LIMIT,
    DEFAULT_PAGE_OFFSET,
    FEATURE_COHORT_RELATION_ORDER,
    MAX_PAGE_LIMIT,
    MIN_PAGE_LIMIT,
    SUPPORTED_PREFIX_COUNTS,
    SUPPORTED_SUCCESS_CRITERIA,
    HistoricalPrefixExactSuccessRate,
    HistoricalPrefixFeatureCohortSummary,
    HistoricalPrefixFeatureRelationTriple,
    HistoricalPrefixRateRelation,
    HistoricalPrefixSignedRateDelta,
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
    HistoricalPrefixWalkForwardBaseline,
    HistoricalPrefixWindowRateComparison,
    HistoricalPrefixWindowRateComparisonKind,
)
from lottolab.application.ports import HistoricalPrefixSuccessWindowSourceReaderFactory
from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import BIG_LOTTO_RULE_CONTRACT
from lottolab.domain.strategy_success_evaluation import (
    BigLottoSuccessCriterion,
    ObservationEvaluation,
    StrategySuccessEvaluationInputError,
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
            parameter_or_config_identity=(
                f"prefix={prefix_count};criterion={criterion.value}"
            ),
            history_cutoff=_draw_token(observation.cutoff),
            target_draw=_draw_token(observation.target),
            window_policy_version=DEFAULT_WINDOW_POLICY_VERSION,
            game_rule_version=BIG_LOTTO_RULE_CONTRACT.contract_version,
            selection_family_identity=observation.constructor_identifier,
            source_artifact_identity=(
                f"{source.metadata.source_artifact_sha256}:"
                f"{source.metadata.import_identity_sha256}"
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
    windows = tuple(
        _window_read_model(summary, observations_by_target) for summary in evaluated
    )
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
        to_rate.numerator * from_rate.denominator
        - from_rate.numerator * to_rate.denominator
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
    observations_by_target = {
        _draw_token(item.target): item for item in prior_observations
    }
    try:
        evaluated = evaluate_strategy_success_windows(
            measurements,
            _domain_criterion(criterion),
        )
    except (StrategySuccessEvaluationInputError, TypeError, ValueError) as exc:
        raise HistoricalPrefixSuccessWindowsUnavailableError(
            "persisted source could not produce a walk-forward snapshot"
        ) from exc
    windows = tuple(
        _window_read_model(summary, observations_by_target) for summary in evaluated
    )
    comparisons = _rate_comparisons(windows)
    relations = {
        comparison.comparison_kind: comparison.relation
        for comparison in comparisons
    }
    return HistoricalPrefixFeatureRelationTriple(
        long_to_medium=relations[
            HistoricalPrefixWindowRateComparisonKind.LONG_TO_MEDIUM
        ],
        medium_to_short=relations[
            HistoricalPrefixWindowRateComparisonKind.MEDIUM_TO_SHORT
        ],
        long_to_short=relations[
            HistoricalPrefixWindowRateComparisonKind.LONG_TO_SHORT
        ],
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


def _feature_cohorts(
    *,
    source: HistoricalPrefixSuccessWindowSource,
    strategy: HistoricalPrefixSuccessSourceStrategy,
    prefix_count: int,
    criterion: HistoricalPrefixSuccessCriterion,
) -> HistoricalPrefixStrategyFeatureCohortResult:
    observations = _walk_forward_observations(strategy)
    assignments: dict[
        HistoricalPrefixFeatureRelationTriple,
        list[tuple[HistoricalPrefixSuccessDrawIdentity, bool]],
    ] = {}
    baseline_successes = 0
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
        assignments.setdefault(feature_key, []).append(
            (current_target.target, succeeded)
        )
        baseline_successes += int(succeeded)
    if source.metadata.import_identity_sha256 != frozen_source_identity:
        raise HistoricalPrefixSuccessWindowsUnavailableError(
            "persisted source identity changed during walk-forward reconstruction"
        )

    baseline_count = len(observations)
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
                outcomes = assignments.get(feature_key, [])
                observation_count = len(outcomes)
                success_count = sum(int(succeeded) for _, succeeded in outcomes)
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
                        first_target=outcomes[0][0] if outcomes else None,
                        last_target=outcomes[-1][0] if outcomes else None,
                    )
                )
    if (
        len(cohorts) != 64
        or sum(cohort.observation_count for cohort in cohorts) != baseline_count
    ):
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

    def _load(self, import_identity_sha256: str) -> HistoricalPrefixSuccessWindowSource:
        reader = self._reader_factory()
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
        criteria = tuple(
            _criterion_identity(criterion) for criterion in SUPPORTED_SUCCESS_CRITERIA
        )
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


__all__ = ["EvaluateHistoricalPrefixSuccessWindows"]
