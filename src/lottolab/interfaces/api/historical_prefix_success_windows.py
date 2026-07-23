"""GET-only API for persisted Historical Prefix strategy-success windows."""

# pyright: reportUnusedFunction=false

from __future__ import annotations

import re
from datetime import date
from enum import IntEnum
from fractions import Fraction
from math import gcd
from typing import Annotated, Any, Literal, Self

from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    REQUIRED_LABELED_TARGET_COUNT,
    TEMPORAL_HOLDOUT_SPLIT_METHOD,
    HistoricalPrefixExactProbability,
    HistoricalPrefixExactSuccessRate,
    HistoricalPrefixFeatureCohortDiagnostic,
    HistoricalPrefixFeatureCohortSummary,
    HistoricalPrefixFeatureCohortTestStatus,
    HistoricalPrefixFeatureRelationTriple,
    HistoricalPrefixOutcomeCounts,
    HistoricalPrefixRateRelation,
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
    HistoricalPrefixSuccessImportNotFoundError,
    HistoricalPrefixSuccessSelectionIdentity,
    HistoricalPrefixSuccessStrategyIdentity,
    HistoricalPrefixSuccessStrategyNotFoundError,
    HistoricalPrefixSuccessWindowSourceMetadata,
    HistoricalPrefixSuccessWindowSummary,
    HistoricalPrefixTemporalHoldoutCohortComparison,
    HistoricalPrefixTemporalHoldoutRelationship,
    HistoricalPrefixTemporalHoldoutResult,
    HistoricalPrefixTemporalHoldoutSplit,
    HistoricalPrefixTemporalHoldoutStatus,
    HistoricalPrefixWalkForwardBaseline,
    HistoricalPrefixWindowRateComparison,
    HistoricalPrefixWindowRateComparisonKind,
)
from lottolab.application.ports import HistoricalPrefixSuccessWindowSourceReaderFactory
from lottolab.application.use_cases.evaluate_historical_prefix_success_windows import (
    EvaluateHistoricalPrefixSuccessWindows,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.strategy_success_evaluation import (
    WindowEvaluationStatus,
    WindowKind,
)
from lottolab.domain.strategy_success_measurement import (
    EvidenceStatus,
    MeasurementMode,
    WindowRole,
)
from lottolab.interfaces.api.draw_data import (
    ApiErrorResponse,
    ApiValidationErrorResponse,
    RequestValidationIssueView,
)
from lottolab.interfaces.api.strategy_catalog import API_PREFIX

_FROZEN_RESPONSE = ConfigDict(frozen=True)


class HistoricalPrefixSuccessPrefixCount(IntEnum):
    ONE = 1
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    TEN = 10
    FIFTEEN = 15
    TWENTY = 20


ImportIdentitySha256 = Annotated[
    str,
    Query(
        pattern=r"^[0-9a-f]{64}$",
        description="Exact lowercase SHA-256 of one persisted Historical Results import.",
    ),
]
StrategyId = Annotated[
    str,
    Path(min_length=1, max_length=200, pattern=r"^\S(?:.*\S)?$"),
]
StrategyVersion = Annotated[
    str,
    Path(min_length=1, max_length=200, pattern=r"^\S(?:.*\S)?$"),
]
Replicate = Annotated[int, Path(ge=1)]
Limit = Annotated[int, Query(ge=MIN_PAGE_LIMIT, le=MAX_PAGE_LIMIT)]
Offset = Annotated[int, Query(ge=DEFAULT_PAGE_OFFSET)]
CanonicalProbabilityInteger = Annotated[
    str,
    Field(pattern=r"^(?:0|[1-9][0-9]*)$"),
]


class HistoricalPrefixSuccessSourceMetadataView(BaseModel):
    model_config = _FROZEN_RESPONSE

    run_id: str
    contract_version: str
    import_identity_sha256: str
    source_kind: str
    source_repository: str
    source_commit_oid: str
    source_artifact_sha256: str
    dataset_identity: str
    dataset_sha256: str
    lottery_type: str

    @classmethod
    def from_metadata(
        cls, metadata: HistoricalPrefixSuccessWindowSourceMetadata
    ) -> HistoricalPrefixSuccessSourceMetadataView:
        return cls(
            run_id=metadata.run_id,
            contract_version=metadata.contract_version,
            import_identity_sha256=metadata.import_identity_sha256,
            source_kind=metadata.source_kind,
            source_repository=metadata.source_repository,
            source_commit_oid=metadata.source_commit_oid,
            source_artifact_sha256=metadata.source_artifact_sha256,
            dataset_identity=metadata.dataset_identity,
            dataset_sha256=metadata.dataset_sha256,
            lottery_type=metadata.lottery_type.value,
        )


class HistoricalPrefixSuccessCriterionView(BaseModel):
    model_config = _FROZEN_RESPONSE

    criterion: HistoricalPrefixSuccessCriterion
    minimum_main_hits: int
    require_special_hit: bool
    measurement_mode: MeasurementMode

    @classmethod
    def from_identity(
        cls, identity: HistoricalPrefixSuccessCriterionIdentity
    ) -> HistoricalPrefixSuccessCriterionView:
        return cls(
            criterion=identity.criterion,
            minimum_main_hits=identity.minimum_main_hits,
            require_special_hit=identity.require_special_hit,
            measurement_mode=identity.measurement_mode,
        )


class HistoricalPrefixSuccessDrawIdentityView(BaseModel):
    model_config = _FROZEN_RESPONSE

    draw_number: int
    draw_date: str
    draw_sha256: str

    @classmethod
    def from_identity(
        cls, identity: HistoricalPrefixSuccessDrawIdentity
    ) -> HistoricalPrefixSuccessDrawIdentityView:
        return cls(
            draw_number=identity.draw_number,
            draw_date=identity.draw_date,
            draw_sha256=identity.draw_sha256,
        )


class HistoricalPrefixSuccessStrategyIdentityView(BaseModel):
    model_config = _FROZEN_RESPONSE

    strategy_id: str
    effective_strategy_id: str
    strategy_version: str
    replicate: int
    identity_kind: str
    governance_status: str
    alias_of_strategy_id: str | None
    equivalence_group: str | None
    nested_prefix_supported: bool
    descriptor_sha256: str

    @classmethod
    def from_identity(
        cls, identity: HistoricalPrefixSuccessStrategyIdentity
    ) -> HistoricalPrefixSuccessStrategyIdentityView:
        return cls.model_validate(identity, from_attributes=True)


class HistoricalPrefixSuccessSelectionIdentityView(BaseModel):
    model_config = _FROZEN_RESPONSE

    lottery: LotteryType
    strategy_id: str
    strategy_version: str
    replicate: int
    ticket_count: int
    max_bet_index: int

    @classmethod
    def from_identity(
        cls, identity: HistoricalPrefixSuccessSelectionIdentity
    ) -> HistoricalPrefixSuccessSelectionIdentityView:
        return cls.model_validate(identity, from_attributes=True)


class HistoricalPrefixExactSuccessRateView(BaseModel):
    model_config = _FROZEN_RESPONSE

    numerator: int
    denominator: int
    available: bool

    @classmethod
    def from_rate(
        cls, rate: HistoricalPrefixExactSuccessRate
    ) -> HistoricalPrefixExactSuccessRateView:
        return cls.model_validate(rate, from_attributes=True)


class HistoricalPrefixSuccessWindowSummaryView(BaseModel):
    model_config = _FROZEN_RESPONSE

    window_kind: WindowKind
    window_role: WindowRole
    requested_draw_count: int | None
    source_draw_count: int
    eligible_draw_count: int
    excluded_draw_count: int
    success_count: int
    failure_count: int
    success_rate: HistoricalPrefixExactSuccessRateView
    first_target: HistoricalPrefixSuccessDrawIdentityView
    last_target: HistoricalPrefixSuccessDrawIdentityView
    first_cutoff: HistoricalPrefixSuccessDrawIdentityView
    last_cutoff: HistoricalPrefixSuccessDrawIdentityView
    nested_windows_independent: bool
    evaluation_status: WindowEvaluationStatus
    evidence_status: EvidenceStatus

    @classmethod
    def from_summary(
        cls, summary: HistoricalPrefixSuccessWindowSummary
    ) -> HistoricalPrefixSuccessWindowSummaryView:
        return cls(
            window_kind=summary.window_kind,
            window_role=summary.window_role,
            requested_draw_count=summary.requested_draw_count,
            source_draw_count=summary.source_draw_count,
            eligible_draw_count=summary.eligible_draw_count,
            excluded_draw_count=summary.excluded_draw_count,
            success_count=summary.success_count,
            failure_count=summary.failure_count,
            success_rate=HistoricalPrefixExactSuccessRateView.from_rate(summary.success_rate),
            first_target=HistoricalPrefixSuccessDrawIdentityView.from_identity(
                summary.first_target
            ),
            last_target=HistoricalPrefixSuccessDrawIdentityView.from_identity(summary.last_target),
            first_cutoff=HistoricalPrefixSuccessDrawIdentityView.from_identity(
                summary.first_cutoff
            ),
            last_cutoff=HistoricalPrefixSuccessDrawIdentityView.from_identity(summary.last_cutoff),
            nested_windows_independent=summary.nested_windows_independent,
            evaluation_status=summary.evaluation_status,
            evidence_status=summary.evidence_status,
        )


class HistoricalPrefixStrategySuccessWindowResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    strategy: HistoricalPrefixSuccessStrategyIdentityView
    criterion: HistoricalPrefixSuccessCriterionView
    prefix_count: int
    selection: HistoricalPrefixSuccessSelectionIdentityView
    status: str
    source_observation_count: int
    windows: tuple[HistoricalPrefixSuccessWindowSummaryView, ...]

    @classmethod
    def from_result(
        cls, result: HistoricalPrefixStrategySuccessWindowResult
    ) -> HistoricalPrefixStrategySuccessWindowResponse:
        return cls(
            strategy=HistoricalPrefixSuccessStrategyIdentityView.from_identity(result.strategy),
            criterion=HistoricalPrefixSuccessCriterionView.from_identity(result.criterion),
            prefix_count=result.prefix_count,
            selection=HistoricalPrefixSuccessSelectionIdentityView.from_identity(result.selection),
            status=result.status.value,
            source_observation_count=result.source_observation_count,
            windows=tuple(
                HistoricalPrefixSuccessWindowSummaryView.from_summary(item)
                for item in result.windows
            ),
        )


class HistoricalPrefixStrategySuccessWindowPageResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    metadata: HistoricalPrefixSuccessSourceMetadataView
    criterion: HistoricalPrefixSuccessCriterionView
    prefix_count: int
    total_count: int
    limit: int
    offset: int
    items: tuple[HistoricalPrefixStrategySuccessWindowResponse, ...]

    @classmethod
    def from_page(
        cls, page: HistoricalPrefixStrategySuccessWindowPage
    ) -> HistoricalPrefixStrategySuccessWindowPageResponse:
        return cls(
            metadata=HistoricalPrefixSuccessSourceMetadataView.from_metadata(page.metadata),
            criterion=HistoricalPrefixSuccessCriterionView.from_identity(page.criterion),
            prefix_count=page.prefix_count,
            total_count=page.total_count,
            limit=page.limit,
            offset=page.offset,
            items=tuple(
                HistoricalPrefixStrategySuccessWindowResponse.from_result(item)
                for item in page.items
            ),
        )


class HistoricalPrefixSignedRateDeltaView(BaseModel):
    model_config = _FROZEN_RESPONSE

    numerator: int
    denominator: int
    available: bool

    @classmethod
    def from_delta(
        cls, delta: HistoricalPrefixSignedRateDelta
    ) -> HistoricalPrefixSignedRateDeltaView:
        return cls.model_validate(delta, from_attributes=True)


class HistoricalPrefixWindowRateComparisonView(BaseModel):
    model_config = _FROZEN_RESPONSE

    comparison_kind: HistoricalPrefixWindowRateComparisonKind
    from_window_kind: WindowKind
    to_window_kind: WindowKind
    from_rate: HistoricalPrefixExactSuccessRateView
    to_rate: HistoricalPrefixExactSuccessRateView
    delta: HistoricalPrefixSignedRateDeltaView
    relation: HistoricalPrefixRateRelation

    @classmethod
    def from_comparison(
        cls, comparison: HistoricalPrefixWindowRateComparison
    ) -> HistoricalPrefixWindowRateComparisonView:
        return cls(
            comparison_kind=comparison.comparison_kind,
            from_window_kind=comparison.from_window_kind,
            to_window_kind=comparison.to_window_kind,
            from_rate=HistoricalPrefixExactSuccessRateView.from_rate(comparison.from_rate),
            to_rate=HistoricalPrefixExactSuccessRateView.from_rate(comparison.to_rate),
            delta=HistoricalPrefixSignedRateDeltaView.from_delta(comparison.delta),
            relation=comparison.relation,
        )


class HistoricalPrefixStrategySuccessMatrixCellView(BaseModel):
    model_config = _FROZEN_RESPONSE

    criterion: HistoricalPrefixSuccessCriterionView
    prefix_count: int
    selection: HistoricalPrefixSuccessSelectionIdentityView
    status: str
    source_observation_count: int
    windows: tuple[HistoricalPrefixSuccessWindowSummaryView, ...]
    comparisons: tuple[HistoricalPrefixWindowRateComparisonView, ...]

    @classmethod
    def from_cell(
        cls, cell: HistoricalPrefixStrategySuccessMatrixCell
    ) -> HistoricalPrefixStrategySuccessMatrixCellView:
        return cls(
            criterion=HistoricalPrefixSuccessCriterionView.from_identity(cell.criterion),
            prefix_count=cell.prefix_count,
            selection=HistoricalPrefixSuccessSelectionIdentityView.from_identity(cell.selection),
            status=cell.status.value,
            source_observation_count=cell.source_observation_count,
            windows=tuple(
                HistoricalPrefixSuccessWindowSummaryView.from_summary(item) for item in cell.windows
            ),
            comparisons=tuple(
                HistoricalPrefixWindowRateComparisonView.from_comparison(item)
                for item in cell.comparisons
            ),
        )


class HistoricalPrefixStrategySuccessMatrixResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    metadata: HistoricalPrefixSuccessSourceMetadataView
    strategy: HistoricalPrefixSuccessStrategyIdentityView
    source_observation_count: int
    prefix_counts: tuple[int, ...]
    criteria: tuple[HistoricalPrefixSuccessCriterionView, ...]
    cell_count: int
    cells: tuple[HistoricalPrefixStrategySuccessMatrixCellView, ...]

    @classmethod
    def from_matrix(
        cls, matrix: HistoricalPrefixStrategySuccessMatrix
    ) -> HistoricalPrefixStrategySuccessMatrixResponse:
        return cls(
            metadata=HistoricalPrefixSuccessSourceMetadataView.from_metadata(matrix.metadata),
            strategy=HistoricalPrefixSuccessStrategyIdentityView.from_identity(matrix.strategy),
            source_observation_count=matrix.source_observation_count,
            prefix_counts=matrix.prefix_counts,
            criteria=tuple(
                HistoricalPrefixSuccessCriterionView.from_identity(item) for item in matrix.criteria
            ),
            cell_count=matrix.cell_count,
            cells=tuple(
                HistoricalPrefixStrategySuccessMatrixCellView.from_cell(item)
                for item in matrix.cells
            ),
        )


class HistoricalPrefixFeatureRelationTripleView(BaseModel):
    model_config = _FROZEN_RESPONSE

    long_to_medium: HistoricalPrefixRateRelation
    medium_to_short: HistoricalPrefixRateRelation
    long_to_short: HistoricalPrefixRateRelation

    @classmethod
    def from_feature_key(
        cls, feature_key: HistoricalPrefixFeatureRelationTriple
    ) -> HistoricalPrefixFeatureRelationTripleView:
        return cls.model_validate(feature_key, from_attributes=True)


class HistoricalPrefixWalkForwardBaselineView(BaseModel):
    model_config = _FROZEN_RESPONSE

    observation_count: int
    success_count: int
    failure_count: int
    success_rate: HistoricalPrefixExactSuccessRateView

    @classmethod
    def from_baseline(
        cls, baseline: HistoricalPrefixWalkForwardBaseline
    ) -> HistoricalPrefixWalkForwardBaselineView:
        return cls(
            observation_count=baseline.observation_count,
            success_count=baseline.success_count,
            failure_count=baseline.failure_count,
            success_rate=HistoricalPrefixExactSuccessRateView.from_rate(baseline.success_rate),
        )


class HistoricalPrefixFeatureCohortView(BaseModel):
    model_config = _FROZEN_RESPONSE

    feature_key: HistoricalPrefixFeatureRelationTripleView
    observation_count: int
    success_count: int
    failure_count: int
    success_rate: HistoricalPrefixExactSuccessRateView
    delta_vs_baseline: HistoricalPrefixSignedRateDeltaView
    relation_vs_baseline: HistoricalPrefixRateRelation
    first_target: HistoricalPrefixSuccessDrawIdentityView | None
    last_target: HistoricalPrefixSuccessDrawIdentityView | None

    @classmethod
    def from_cohort(
        cls, cohort: HistoricalPrefixFeatureCohortSummary
    ) -> HistoricalPrefixFeatureCohortView:
        return cls(
            feature_key=HistoricalPrefixFeatureRelationTripleView.from_feature_key(
                cohort.feature_key
            ),
            observation_count=cohort.observation_count,
            success_count=cohort.success_count,
            failure_count=cohort.failure_count,
            success_rate=HistoricalPrefixExactSuccessRateView.from_rate(cohort.success_rate),
            delta_vs_baseline=HistoricalPrefixSignedRateDeltaView.from_delta(
                cohort.delta_vs_baseline
            ),
            relation_vs_baseline=cohort.relation_vs_baseline,
            first_target=(
                HistoricalPrefixSuccessDrawIdentityView.from_identity(cohort.first_target)
                if cohort.first_target is not None
                else None
            ),
            last_target=(
                HistoricalPrefixSuccessDrawIdentityView.from_identity(cohort.last_target)
                if cohort.last_target is not None
                else None
            ),
        )


class HistoricalPrefixStrategyFeatureCohortResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    metadata: HistoricalPrefixSuccessSourceMetadataView
    strategy: HistoricalPrefixSuccessStrategyIdentityView
    criterion: HistoricalPrefixSuccessCriterionView
    prefix_count: int
    baseline: HistoricalPrefixWalkForwardBaselineView
    cohort_count: int
    cohorts: tuple[HistoricalPrefixFeatureCohortView, ...]

    @classmethod
    def from_result(
        cls, result: HistoricalPrefixStrategyFeatureCohortResult
    ) -> HistoricalPrefixStrategyFeatureCohortResponse:
        return cls(
            metadata=HistoricalPrefixSuccessSourceMetadataView.from_metadata(result.metadata),
            strategy=HistoricalPrefixSuccessStrategyIdentityView.from_identity(result.strategy),
            criterion=HistoricalPrefixSuccessCriterionView.from_identity(result.criterion),
            prefix_count=result.prefix_count,
            baseline=HistoricalPrefixWalkForwardBaselineView.from_baseline(result.baseline),
            cohort_count=result.cohort_count,
            cohorts=tuple(
                HistoricalPrefixFeatureCohortView.from_cohort(cohort) for cohort in result.cohorts
            ),
        )


class HistoricalPrefixExactProbabilityView(BaseModel):
    model_config = _FROZEN_RESPONSE

    numerator: CanonicalProbabilityInteger
    denominator: CanonicalProbabilityInteger

    @model_validator(mode="after")
    def validate_canonical_probability(self) -> Self:
        canonical = re.compile(r"^(?:0|[1-9][0-9]*)$", flags=re.ASCII)
        if (
            canonical.fullmatch(self.numerator) is None
            or canonical.fullmatch(self.denominator) is None
            or self.denominator == "0"
        ):
            raise ValueError("probability integers must be canonical decimal strings")
        numerator = int(self.numerator)
        denominator = int(self.denominator)
        if numerator > denominator or gcd(numerator, denominator) != 1:
            raise ValueError("probability fraction must be reduced and between zero and one")
        return self

    @classmethod
    def from_probability(
        cls, probability: HistoricalPrefixExactProbability
    ) -> HistoricalPrefixExactProbabilityView:
        return cls(
            numerator=str(probability.numerator),
            denominator=str(probability.denominator),
        )


class HistoricalPrefixOutcomeCountsView(BaseModel):
    model_config = _FROZEN_RESPONSE

    observation_count: int
    success_count: int
    failure_count: int

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if (
            min(self.observation_count, self.success_count, self.failure_count) < 0
            or self.success_count + self.failure_count != self.observation_count
        ):
            raise ValueError("diagnostic outcome counts are inconsistent")
        return self

    @classmethod
    def from_counts(
        cls, counts: HistoricalPrefixOutcomeCounts
    ) -> HistoricalPrefixOutcomeCountsView:
        return cls.model_validate(counts, from_attributes=True)


class HistoricalPrefixFeatureCohortDiagnosticView(BaseModel):
    model_config = _FROZEN_RESPONSE

    cohort_index: int
    feature_key: HistoricalPrefixFeatureRelationTripleView
    test_status: HistoricalPrefixFeatureCohortTestStatus
    cohort_counts: HistoricalPrefixOutcomeCountsView
    outside_counts: HistoricalPrefixOutcomeCountsView
    cohort_success_rate: HistoricalPrefixExactSuccessRateView
    outside_success_rate: HistoricalPrefixExactSuccessRateView
    risk_difference: HistoricalPrefixSignedRateDeltaView
    relation_vs_outside: HistoricalPrefixRateRelation
    raw_p_value: HistoricalPrefixExactProbabilityView
    adjusted_p_value: HistoricalPrefixExactProbabilityView
    first_target: HistoricalPrefixSuccessDrawIdentityView | None
    last_target: HistoricalPrefixSuccessDrawIdentityView | None

    @classmethod
    def from_diagnostic(
        cls, diagnostic: HistoricalPrefixFeatureCohortDiagnostic
    ) -> HistoricalPrefixFeatureCohortDiagnosticView:
        return cls(
            cohort_index=diagnostic.cohort_index,
            feature_key=HistoricalPrefixFeatureRelationTripleView.from_feature_key(
                diagnostic.feature_key
            ),
            test_status=diagnostic.test_status,
            cohort_counts=HistoricalPrefixOutcomeCountsView.from_counts(diagnostic.cohort_counts),
            outside_counts=HistoricalPrefixOutcomeCountsView.from_counts(diagnostic.outside_counts),
            cohort_success_rate=HistoricalPrefixExactSuccessRateView.from_rate(
                diagnostic.cohort_success_rate
            ),
            outside_success_rate=HistoricalPrefixExactSuccessRateView.from_rate(
                diagnostic.outside_success_rate
            ),
            risk_difference=HistoricalPrefixSignedRateDeltaView.from_delta(
                diagnostic.risk_difference
            ),
            relation_vs_outside=diagnostic.relation_vs_outside,
            raw_p_value=HistoricalPrefixExactProbabilityView.from_probability(
                diagnostic.raw_p_value
            ),
            adjusted_p_value=HistoricalPrefixExactProbabilityView.from_probability(
                diagnostic.adjusted_p_value
            ),
            first_target=(
                HistoricalPrefixSuccessDrawIdentityView.from_identity(diagnostic.first_target)
                if diagnostic.first_target is not None
                else None
            ),
            last_target=(
                HistoricalPrefixSuccessDrawIdentityView.from_identity(diagnostic.last_target)
                if diagnostic.last_target is not None
                else None
            ),
        )


class HistoricalPrefixStrategyFeatureCohortDiagnosticsResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    metadata: HistoricalPrefixSuccessSourceMetadataView
    strategy: HistoricalPrefixSuccessStrategyIdentityView
    criterion: HistoricalPrefixSuccessCriterionView
    prefix_count: int
    baseline: HistoricalPrefixWalkForwardBaselineView
    family_size: Literal[64]
    raw_test_method: Literal["FISHER_EXACT_TWO_SIDED_PROBABILITY_ORDERING"]
    adjustment_method: Literal["BENJAMINI_YEKUTIELI"]
    diagnostics: tuple[HistoricalPrefixFeatureCohortDiagnosticView, ...]

    @model_validator(mode="after")
    def validate_family(self) -> Self:
        if (
            self.raw_test_method != FISHER_EXACT_TWO_SIDED_METHOD
            or self.adjustment_method != BENJAMINI_YEKUTIELI_METHOD
            or len(self.diagnostics) != self.family_size
        ):
            raise ValueError("diagnostic family identity is inconsistent")
        baseline = self.baseline
        for index, diagnostic in enumerate(self.diagnostics):
            expected_key = (
                FEATURE_COHORT_RELATION_ORDER[index // 16],
                FEATURE_COHORT_RELATION_ORDER[(index % 16) // 4],
                FEATURE_COHORT_RELATION_ORDER[index % 4],
            )
            actual_key = diagnostic.feature_key
            if (
                diagnostic.cohort_index != index
                or (
                    actual_key.long_to_medium,
                    actual_key.medium_to_short,
                    actual_key.long_to_short,
                )
                != expected_key
            ):
                raise ValueError("diagnostics must preserve canonical cohort order")
            cohort = diagnostic.cohort_counts
            outside = diagnostic.outside_counts
            if (
                cohort.observation_count + outside.observation_count != baseline.observation_count
                or cohort.success_count + outside.success_count != baseline.success_count
                or cohort.failure_count + outside.failure_count != baseline.failure_count
            ):
                raise ValueError("diagnostic cohort and complement must partition baseline")
        return self

    @classmethod
    def from_result(
        cls, result: HistoricalPrefixStrategyFeatureCohortDiagnostics
    ) -> HistoricalPrefixStrategyFeatureCohortDiagnosticsResponse:
        if (
            result.family_size != 64
            or result.raw_test_method != FISHER_EXACT_TWO_SIDED_METHOD
            or result.adjustment_method != BENJAMINI_YEKUTIELI_METHOD
        ):
            raise ValueError("application diagnostics family identity is inconsistent")
        return cls(
            metadata=HistoricalPrefixSuccessSourceMetadataView.from_metadata(result.metadata),
            strategy=HistoricalPrefixSuccessStrategyIdentityView.from_identity(result.strategy),
            criterion=HistoricalPrefixSuccessCriterionView.from_identity(result.criterion),
            prefix_count=result.prefix_count,
            baseline=HistoricalPrefixWalkForwardBaselineView.from_baseline(result.baseline),
            family_size=64,
            raw_test_method="FISHER_EXACT_TWO_SIDED_PROBABILITY_ORDERING",
            adjustment_method="BENJAMINI_YEKUTIELI",
            diagnostics=tuple(
                HistoricalPrefixFeatureCohortDiagnosticView.from_diagnostic(diagnostic)
                for diagnostic in result.diagnostics
            ),
        )


class HistoricalPrefixTemporalHoldoutSplitView(BaseModel):
    model_config = _FROZEN_RESPONSE

    split_method: Literal["FIXED_LAST_750_DISCOVERY_LAST_300_CONFIRMATION"]
    total_assignment_count: Annotated[int, Field(ge=0)]
    warmup_count: Annotated[int, Field(ge=0)]
    discovery_count: Annotated[int, Field(ge=0)]
    confirmation_count: Annotated[int, Field(ge=0)]
    discovery_first_target: HistoricalPrefixSuccessDrawIdentityView | None
    discovery_last_target: HistoricalPrefixSuccessDrawIdentityView | None
    confirmation_first_target: HistoricalPrefixSuccessDrawIdentityView | None
    confirmation_last_target: HistoricalPrefixSuccessDrawIdentityView | None

    @classmethod
    def from_split(
        cls, split: HistoricalPrefixTemporalHoldoutSplit
    ) -> HistoricalPrefixTemporalHoldoutSplitView:
        return cls(
            split_method="FIXED_LAST_750_DISCOVERY_LAST_300_CONFIRMATION",
            total_assignment_count=split.total_assignment_count,
            warmup_count=split.warmup_count,
            discovery_count=split.discovery_count,
            confirmation_count=split.confirmation_count,
            discovery_first_target=(
                HistoricalPrefixSuccessDrawIdentityView.from_identity(split.discovery_first_target)
                if split.discovery_first_target is not None
                else None
            ),
            discovery_last_target=(
                HistoricalPrefixSuccessDrawIdentityView.from_identity(split.discovery_last_target)
                if split.discovery_last_target is not None
                else None
            ),
            confirmation_first_target=(
                HistoricalPrefixSuccessDrawIdentityView.from_identity(
                    split.confirmation_first_target
                )
                if split.confirmation_first_target is not None
                else None
            ),
            confirmation_last_target=(
                HistoricalPrefixSuccessDrawIdentityView.from_identity(
                    split.confirmation_last_target
                )
                if split.confirmation_last_target is not None
                else None
            ),
        )


class HistoricalPrefixTemporalHoldoutCohortComparisonView(BaseModel):
    model_config = _FROZEN_RESPONSE

    cohort_index: int
    feature_key: HistoricalPrefixFeatureRelationTripleView
    discovery_diagnostic: HistoricalPrefixFeatureCohortDiagnosticView
    confirmation_diagnostic: HistoricalPrefixFeatureCohortDiagnosticView
    effect_change: HistoricalPrefixSignedRateDeltaView
    relationship: HistoricalPrefixTemporalHoldoutRelationship

    @model_validator(mode="after")
    def validate_comparison(self) -> Self:
        discovery = self.discovery_diagnostic
        confirmation = self.confirmation_diagnostic
        if (
            discovery.cohort_index != self.cohort_index
            or confirmation.cohort_index != self.cohort_index
            or discovery.feature_key != self.feature_key
            or confirmation.feature_key != self.feature_key
        ):
            raise ValueError("temporal comparison identity is inconsistent")
        discovery_effect = discovery.risk_difference
        confirmation_effect = confirmation.risk_difference
        if discovery_effect.available and confirmation_effect.available:
            expected = Fraction(
                confirmation_effect.numerator,
                confirmation_effect.denominator,
            ) - Fraction(
                discovery_effect.numerator,
                discovery_effect.denominator,
            )
            if (
                not self.effect_change.available
                or self.effect_change.numerator != expected.numerator
                or self.effect_change.denominator != expected.denominator
            ):
                raise ValueError("temporal effect change is inconsistent")
        elif (
            self.effect_change.available
            or self.effect_change.numerator != 0
            or self.effect_change.denominator != 0
        ):
            raise ValueError("unavailable temporal effect change is inconsistent")
        relationship = (
            HistoricalPrefixTemporalHoldoutRelationship.UNAVAILABLE
            if (
                discovery.relation_vs_outside is HistoricalPrefixRateRelation.UNAVAILABLE
                or confirmation.relation_vs_outside is HistoricalPrefixRateRelation.UNAVAILABLE
            )
            else (
                HistoricalPrefixTemporalHoldoutRelationship.DIFFERENT
                if discovery.relation_vs_outside is not confirmation.relation_vs_outside
                else {
                    HistoricalPrefixRateRelation.HIGHER: (
                        HistoricalPrefixTemporalHoldoutRelationship.SAME_HIGHER
                    ),
                    HistoricalPrefixRateRelation.EQUAL: (
                        HistoricalPrefixTemporalHoldoutRelationship.SAME_EQUAL
                    ),
                    HistoricalPrefixRateRelation.LOWER: (
                        HistoricalPrefixTemporalHoldoutRelationship.SAME_LOWER
                    ),
                }[discovery.relation_vs_outside]
            )
        )
        if self.relationship is not relationship:
            raise ValueError("temporal relationship is inconsistent")
        return self

    @classmethod
    def from_comparison(
        cls, comparison: HistoricalPrefixTemporalHoldoutCohortComparison
    ) -> HistoricalPrefixTemporalHoldoutCohortComparisonView:
        return cls(
            cohort_index=comparison.cohort_index,
            feature_key=HistoricalPrefixFeatureRelationTripleView.from_feature_key(
                comparison.feature_key
            ),
            discovery_diagnostic=(
                HistoricalPrefixFeatureCohortDiagnosticView.from_diagnostic(
                    comparison.discovery_diagnostic
                )
            ),
            confirmation_diagnostic=(
                HistoricalPrefixFeatureCohortDiagnosticView.from_diagnostic(
                    comparison.confirmation_diagnostic
                )
            ),
            effect_change=HistoricalPrefixSignedRateDeltaView.from_delta(comparison.effect_change),
            relationship=comparison.relationship,
        )


class HistoricalPrefixTemporalHoldoutResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    metadata: HistoricalPrefixSuccessSourceMetadataView
    strategy: HistoricalPrefixSuccessStrategyIdentityView
    criterion: HistoricalPrefixSuccessCriterionView
    prefix_count: int
    split: HistoricalPrefixTemporalHoldoutSplitView
    evaluation_status: HistoricalPrefixTemporalHoldoutStatus
    family_size: Literal[64]
    discovery: HistoricalPrefixStrategyFeatureCohortDiagnosticsResponse | None
    confirmation: HistoricalPrefixStrategyFeatureCohortDiagnosticsResponse | None
    comparisons: tuple[HistoricalPrefixTemporalHoldoutCohortComparisonView, ...]

    @model_validator(mode="after")
    def validate_holdout(self) -> Self:
        split = self.split
        if (
            split.split_method != TEMPORAL_HOLDOUT_SPLIT_METHOD
            or split.total_assignment_count
            != split.warmup_count + split.discovery_count + split.confirmation_count
        ):
            raise ValueError("temporal split arithmetic is inconsistent")
        boundaries = (
            split.discovery_first_target,
            split.discovery_last_target,
            split.confirmation_first_target,
            split.confirmation_last_target,
        )
        if (
            self.evaluation_status
            is HistoricalPrefixTemporalHoldoutStatus.NOT_READY_INSUFFICIENT_HISTORY
        ):
            if (
                split.total_assignment_count >= REQUIRED_LABELED_TARGET_COUNT
                or split.warmup_count != split.total_assignment_count
                or split.discovery_count != 0
                or split.confirmation_count != 0
                or any(boundary is not None for boundary in boundaries)
                or self.discovery is not None
                or self.confirmation is not None
                or self.comparisons
            ):
                raise ValueError("not-ready temporal holdout is inconsistent")
            return self
        if (
            split.total_assignment_count < REQUIRED_LABELED_TARGET_COUNT
            or split.discovery_count != DISCOVERY_TARGET_COUNT
            or split.confirmation_count != CONFIRMATION_TARGET_COUNT
            or any(boundary is None for boundary in boundaries)
            or self.discovery is None
            or self.confirmation is None
            or len(self.comparisons) != self.family_size
        ):
            raise ValueError("complete temporal holdout is inconsistent")
        discovery_first = split.discovery_first_target
        discovery_last = split.discovery_last_target
        confirmation_first = split.confirmation_first_target
        confirmation_last = split.confirmation_last_target
        if (
            discovery_first is None
            or discovery_last is None
            or confirmation_first is None
            or confirmation_last is None
        ):
            raise ValueError("complete temporal holdout boundaries are required")
        try:
            discovery_first_order = (
                date.fromisoformat(discovery_first.draw_date),
                discovery_first.draw_number,
            )
            discovery_last_order = (
                date.fromisoformat(discovery_last.draw_date),
                discovery_last.draw_number,
            )
            confirmation_first_order = (
                date.fromisoformat(confirmation_first.draw_date),
                confirmation_first.draw_number,
            )
            confirmation_last_order = (
                date.fromisoformat(confirmation_last.draw_date),
                confirmation_last.draw_number,
            )
        except ValueError as exc:
            raise ValueError("temporal holdout boundary dates must be ISO dates") from exc
        if not (
            discovery_first_order
            <= discovery_last_order
            < confirmation_first_order
            <= confirmation_last_order
        ):
            raise ValueError("temporal holdout phase boundaries are out of order")
        discovery = self.discovery
        confirmation = self.confirmation
        if (
            discovery.metadata != self.metadata
            or confirmation.metadata != self.metadata
            or discovery.strategy != self.strategy
            or confirmation.strategy != self.strategy
            or discovery.criterion != self.criterion
            or confirmation.criterion != self.criterion
            or discovery.prefix_count != self.prefix_count
            or confirmation.prefix_count != self.prefix_count
            or discovery.baseline.observation_count != DISCOVERY_TARGET_COUNT
            or confirmation.baseline.observation_count != CONFIRMATION_TARGET_COUNT
        ):
            raise ValueError("temporal phase identity is inconsistent")
        for index, comparison in enumerate(self.comparisons):
            if (
                comparison.cohort_index != index
                or comparison.discovery_diagnostic != discovery.diagnostics[index]
                or comparison.confirmation_diagnostic != confirmation.diagnostics[index]
            ):
                raise ValueError("temporal comparisons must preserve canonical order")
        return self

    @classmethod
    def from_result(
        cls, result: HistoricalPrefixTemporalHoldoutResult
    ) -> HistoricalPrefixTemporalHoldoutResponse:
        return cls(
            metadata=HistoricalPrefixSuccessSourceMetadataView.from_metadata(result.metadata),
            strategy=HistoricalPrefixSuccessStrategyIdentityView.from_identity(result.strategy),
            criterion=HistoricalPrefixSuccessCriterionView.from_identity(result.criterion),
            prefix_count=result.prefix_count,
            split=HistoricalPrefixTemporalHoldoutSplitView.from_split(result.split),
            evaluation_status=result.evaluation_status,
            family_size=64,
            discovery=(
                HistoricalPrefixStrategyFeatureCohortDiagnosticsResponse.from_result(
                    result.discovery
                )
                if result.discovery is not None
                else None
            ),
            confirmation=(
                HistoricalPrefixStrategyFeatureCohortDiagnosticsResponse.from_result(
                    result.confirmation
                )
                if result.confirmation is not None
                else None
            ),
            comparisons=tuple(
                HistoricalPrefixTemporalHoldoutCohortComparisonView.from_comparison(comparison)
                for comparison in result.comparisons
            ),
        )


def create_historical_prefix_success_windows_router(
    reader_factory: HistoricalPrefixSuccessWindowSourceReaderFactory | None,
) -> APIRouter:
    """Expose both routes without creating or invoking the optional reader."""

    router = APIRouter(prefix=API_PREFIX, tags=["historical-prefix-success-windows"])
    evaluator = (
        EvaluateHistoricalPrefixSuccessWindows(reader_factory)
        if reader_factory is not None
        else None
    )
    error_responses: dict[int | str, dict[str, Any]] = {
        404: {"model": ApiErrorResponse},
        422: {"model": ApiValidationErrorResponse},
        503: {"model": ApiErrorResponse},
    }

    @router.get(
        "/historical-prefix-success-windows",
        response_model=HistoricalPrefixStrategySuccessWindowPageResponse,
        responses=error_responses,
        operation_id="listHistoricalPrefixStrategySuccessWindows",
    )
    def list_historical_prefix_strategy_success_windows(
        import_identity_sha256: ImportIdentitySha256,
        prefix_count: HistoricalPrefixSuccessPrefixCount,
        criterion: HistoricalPrefixSuccessCriterion,
        limit: Limit = DEFAULT_PAGE_LIMIT,
        offset: Offset = DEFAULT_PAGE_OFFSET,
    ) -> HistoricalPrefixStrategySuccessWindowPageResponse | JSONResponse:
        if evaluator is None:
            return _not_configured_error()
        try:
            page = evaluator.list_strategies(
                import_identity_sha256=import_identity_sha256,
                prefix_count=int(prefix_count),
                criterion=criterion,
                limit=limit,
                offset=offset,
            )
        except HistoricalPrefixSuccessImportNotFoundError:
            return _import_not_found_error()
        except Exception:
            return _unavailable_error()
        return HistoricalPrefixStrategySuccessWindowPageResponse.from_page(page)

    @router.get(
        (
            "/historical-prefix-success-windows/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}/feature-cohorts/temporal-holdout"
        ),
        response_model=HistoricalPrefixTemporalHoldoutResponse,
        responses=error_responses,
        operation_id="getHistoricalPrefixStrategyFeatureCohortTemporalHoldout",
    )
    def get_historical_prefix_strategy_feature_cohort_temporal_holdout(
        request: Request,
        strategy_id: StrategyId,
        strategy_version: StrategyVersion,
        replicate: Replicate,
        import_identity_sha256: ImportIdentitySha256,
        prefix_count: HistoricalPrefixSuccessPrefixCount,
        criterion: HistoricalPrefixSuccessCriterion,
    ) -> HistoricalPrefixTemporalHoldoutResponse | JSONResponse:
        unexpected = sorted(
            set(request.query_params.keys())
            - {"import_identity_sha256", "prefix_count", "criterion"}
        )
        if unexpected:
            return _invalid_matrix_query_error(unexpected)
        if evaluator is None:
            return _not_configured_error()
        try:
            result = evaluator.get_feature_cohort_temporal_holdout(
                import_identity_sha256=import_identity_sha256,
                strategy_id=strategy_id,
                strategy_version=strategy_version,
                replicate=replicate,
                prefix_count=int(prefix_count),
                criterion=criterion,
            )
        except HistoricalPrefixSuccessImportNotFoundError:
            return _import_not_found_error()
        except HistoricalPrefixSuccessStrategyNotFoundError:
            return _strategy_not_found_error()
        except Exception:
            return _unavailable_error()
        return HistoricalPrefixTemporalHoldoutResponse.from_result(result)

    @router.get(
        (
            "/historical-prefix-success-windows/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}/feature-cohorts/diagnostics"
        ),
        response_model=HistoricalPrefixStrategyFeatureCohortDiagnosticsResponse,
        responses=error_responses,
        operation_id="getHistoricalPrefixStrategyFeatureCohortDiagnostics",
    )
    def get_historical_prefix_strategy_feature_cohort_diagnostics(
        request: Request,
        strategy_id: StrategyId,
        strategy_version: StrategyVersion,
        replicate: Replicate,
        import_identity_sha256: ImportIdentitySha256,
        prefix_count: HistoricalPrefixSuccessPrefixCount,
        criterion: HistoricalPrefixSuccessCriterion,
    ) -> HistoricalPrefixStrategyFeatureCohortDiagnosticsResponse | JSONResponse:
        unexpected = sorted(
            set(request.query_params.keys())
            - {"import_identity_sha256", "prefix_count", "criterion"}
        )
        if unexpected:
            return _invalid_matrix_query_error(unexpected)
        if evaluator is None:
            return _not_configured_error()
        try:
            result = evaluator.get_feature_cohort_diagnostics(
                import_identity_sha256=import_identity_sha256,
                strategy_id=strategy_id,
                strategy_version=strategy_version,
                replicate=replicate,
                prefix_count=int(prefix_count),
                criterion=criterion,
            )
        except HistoricalPrefixSuccessImportNotFoundError:
            return _import_not_found_error()
        except HistoricalPrefixSuccessStrategyNotFoundError:
            return _strategy_not_found_error()
        except Exception:
            return _unavailable_error()
        return HistoricalPrefixStrategyFeatureCohortDiagnosticsResponse.from_result(result)

    @router.get(
        (
            "/historical-prefix-success-windows/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}/feature-cohorts"
        ),
        response_model=HistoricalPrefixStrategyFeatureCohortResponse,
        responses=error_responses,
        operation_id="getHistoricalPrefixStrategyFeatureCohorts",
    )
    def get_historical_prefix_strategy_feature_cohorts(
        request: Request,
        strategy_id: StrategyId,
        strategy_version: StrategyVersion,
        replicate: Replicate,
        import_identity_sha256: ImportIdentitySha256,
        prefix_count: HistoricalPrefixSuccessPrefixCount,
        criterion: HistoricalPrefixSuccessCriterion,
    ) -> HistoricalPrefixStrategyFeatureCohortResponse | JSONResponse:
        unexpected = sorted(
            set(request.query_params.keys())
            - {"import_identity_sha256", "prefix_count", "criterion"}
        )
        if unexpected:
            return _invalid_matrix_query_error(unexpected)
        if evaluator is None:
            return _not_configured_error()
        try:
            result = evaluator.get_feature_cohorts(
                import_identity_sha256=import_identity_sha256,
                strategy_id=strategy_id,
                strategy_version=strategy_version,
                replicate=replicate,
                prefix_count=int(prefix_count),
                criterion=criterion,
            )
        except HistoricalPrefixSuccessImportNotFoundError:
            return _import_not_found_error()
        except HistoricalPrefixSuccessStrategyNotFoundError:
            return _strategy_not_found_error()
        except Exception:
            return _unavailable_error()
        return HistoricalPrefixStrategyFeatureCohortResponse.from_result(result)

    @router.get(
        (
            "/historical-prefix-success-windows/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}"
        ),
        response_model=HistoricalPrefixStrategySuccessWindowResponse,
        responses=error_responses,
        operation_id="getHistoricalPrefixStrategySuccessWindows",
    )
    def get_historical_prefix_strategy_success_windows(
        strategy_id: StrategyId,
        strategy_version: StrategyVersion,
        replicate: Replicate,
        import_identity_sha256: ImportIdentitySha256,
        prefix_count: HistoricalPrefixSuccessPrefixCount,
        criterion: HistoricalPrefixSuccessCriterion,
    ) -> HistoricalPrefixStrategySuccessWindowResponse | JSONResponse:
        if evaluator is None:
            return _not_configured_error()
        try:
            result = evaluator.get_strategy(
                import_identity_sha256=import_identity_sha256,
                strategy_id=strategy_id,
                strategy_version=strategy_version,
                replicate=replicate,
                prefix_count=int(prefix_count),
                criterion=criterion,
            )
        except HistoricalPrefixSuccessImportNotFoundError:
            return _import_not_found_error()
        except HistoricalPrefixSuccessStrategyNotFoundError:
            return _strategy_not_found_error()
        except Exception:
            return _unavailable_error()
        return HistoricalPrefixStrategySuccessWindowResponse.from_result(result)

    @router.get(
        (
            "/historical-prefix-success-windows/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}/matrix"
        ),
        response_model=HistoricalPrefixStrategySuccessMatrixResponse,
        responses=error_responses,
        operation_id="getHistoricalPrefixStrategySuccessMatrix",
    )
    def get_historical_prefix_strategy_success_matrix(
        request: Request,
        strategy_id: StrategyId,
        strategy_version: StrategyVersion,
        replicate: Replicate,
        import_identity_sha256: ImportIdentitySha256,
    ) -> HistoricalPrefixStrategySuccessMatrixResponse | JSONResponse:
        unexpected = sorted(set(request.query_params.keys()) - {"import_identity_sha256"})
        if unexpected:
            return _invalid_matrix_query_error(unexpected)
        if evaluator is None:
            return _not_configured_error()
        try:
            matrix = evaluator.get_matrix(
                import_identity_sha256=import_identity_sha256,
                strategy_id=strategy_id,
                strategy_version=strategy_version,
                replicate=replicate,
            )
        except HistoricalPrefixSuccessImportNotFoundError:
            return _import_not_found_error()
        except HistoricalPrefixSuccessStrategyNotFoundError:
            return _strategy_not_found_error()
        except Exception:
            return _unavailable_error()
        return HistoricalPrefixStrategySuccessMatrixResponse.from_matrix(matrix)

    return router


def _not_configured_error() -> JSONResponse:
    return _error_response(
        503,
        "HISTORICAL_PREFIX_SUCCESS_WINDOWS_NOT_CONFIGURED",
        "Historical prefix success windows are not configured.",
    )


def _import_not_found_error() -> JSONResponse:
    return _error_response(
        404,
        "HISTORICAL_PREFIX_SUCCESS_IMPORT_NOT_FOUND",
        "Historical prefix success import was not found.",
    )


def _strategy_not_found_error() -> JSONResponse:
    return _error_response(
        404,
        "HISTORICAL_PREFIX_SUCCESS_STRATEGY_NOT_FOUND",
        "Historical prefix success strategy was not found.",
    )


def _unavailable_error() -> JSONResponse:
    return _error_response(
        503,
        "HISTORICAL_PREFIX_SUCCESS_WINDOWS_UNAVAILABLE",
        "Historical prefix success windows are unavailable.",
    )


def _invalid_matrix_query_error(fields: list[str]) -> JSONResponse:
    model = ApiValidationErrorResponse(
        error_code="REQUEST_VALIDATION_FAILED",
        message="Request validation failed.",
        fields=[
            RequestValidationIssueView(
                location=f"query.{field}",
                type="extra_forbidden",
            )
            for field in fields
        ],
    )
    return JSONResponse(status_code=422, content=model.model_dump(mode="json"))


def _error_response(status_code: int, error_code: str, message: str) -> JSONResponse:
    model = ApiErrorResponse(error_code=error_code, message=message)
    return JSONResponse(status_code=status_code, content=model.model_dump(mode="json"))


__all__ = [
    "HistoricalPrefixExactProbabilityView",
    "HistoricalPrefixExactSuccessRateView",
    "HistoricalPrefixFeatureCohortDiagnosticView",
    "HistoricalPrefixFeatureCohortTestStatus",
    "HistoricalPrefixFeatureCohortView",
    "HistoricalPrefixFeatureRelationTripleView",
    "HistoricalPrefixOutcomeCountsView",
    "HistoricalPrefixSignedRateDeltaView",
    "HistoricalPrefixStrategyFeatureCohortDiagnosticsResponse",
    "HistoricalPrefixStrategyFeatureCohortResponse",
    "HistoricalPrefixStrategySuccessMatrixCellView",
    "HistoricalPrefixStrategySuccessMatrixResponse",
    "HistoricalPrefixStrategySuccessWindowPageResponse",
    "HistoricalPrefixStrategySuccessWindowResponse",
    "HistoricalPrefixSuccessCriterionView",
    "HistoricalPrefixSuccessDrawIdentityView",
    "HistoricalPrefixSuccessPrefixCount",
    "HistoricalPrefixSuccessSelectionIdentityView",
    "HistoricalPrefixSuccessSourceMetadataView",
    "HistoricalPrefixSuccessStrategyIdentityView",
    "HistoricalPrefixSuccessWindowSummaryView",
    "HistoricalPrefixTemporalHoldoutCohortComparisonView",
    "HistoricalPrefixTemporalHoldoutResponse",
    "HistoricalPrefixTemporalHoldoutSplitView",
    "HistoricalPrefixWalkForwardBaselineView",
    "HistoricalPrefixWindowRateComparisonView",
    "create_historical_prefix_success_windows_router",
]
