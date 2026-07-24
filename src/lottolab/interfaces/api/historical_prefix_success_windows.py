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
    RECENT_AUDIT_SPLIT_METHOD,
    RECENT_AUDIT_TARGET_COUNT,
    RECENT_REFERENCE_TARGET_COUNT,
    REQUIRED_LABELED_TARGET_COUNT,
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
    HistoricalPrefixSuccessImportNotFoundError,
    HistoricalPrefixSuccessSelectionIdentity,
    HistoricalPrefixSuccessStrategyIdentity,
    HistoricalPrefixSuccessStrategyNotFoundError,
    HistoricalPrefixSuccessWindowsContractError,
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
from lottolab.application.historical_success_qualification import (
    RANDOM_BASELINE_CAVEAT,
    HistoricalSuccessQualificationCensusStatus,
    HistoricalSuccessQualificationEvidenceStatus,
    HistoricalSuccessQualificationInformationalFlag,
    HistoricalSuccessQualificationOverlapRelation,
    HistoricalSuccessQualificationPairStatus,
    HistoricalSuccessQualificationPrimaryStatus,
    HistoricalSuccessResearchQualification,
)
from lottolab.application.historical_success_random_baseline import (
    HistoricalSuccessExactRational,
    HistoricalSuccessRandomBaselineCellIdentity,
    HistoricalSuccessRandomBaselineNotReadyReason,
    HistoricalSuccessRandomBaselineReadiness,
    HistoricalSuccessRandomBaselineResult,
    HistoricalSuccessRandomBaselineSamplingPolicy,
    render_exact_decimal_18,
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
_QUALIFICATION_RESPONSE = ConfigDict(frozen=True, extra="forbid")
_RANDOM_BASELINE_RESPONSE = ConfigDict(frozen=True, extra="forbid")


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
MultiImportIdentitySha256Item = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
MultiImportIdentitySha256 = Annotated[
    list[MultiImportIdentitySha256Item],
    Query(
        min_length=2,
        max_length=4,
        description=(
            "Two to four distinct exact Historical Results import SHA-256 values; "
            "repeat this query parameter in caller order."
        ),
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
CanonicalPositiveInteger = Annotated[
    str,
    Field(pattern=r"^[1-9][0-9]*$"),
]
ExactDecimal18 = Annotated[
    str,
    Field(pattern=r"^(?:0|[1-9][0-9]*)\.[0-9]{18}$"),
]


class HistoricalSuccessRandomBaselineCellView(BaseModel):
    model_config = _RANDOM_BASELINE_RESPONSE

    policy_version: str
    import_identity_sha256: str
    dataset_sha256: str
    source_artifact_sha256: str
    strategy_id: str
    strategy_version: str
    replicate: Annotated[int, Field(ge=1)]
    window_kind: WindowKind
    window_policy_version: str
    prefix_count: HistoricalPrefixSuccessPrefixCount
    criterion: HistoricalPrefixSuccessCriterion

    @classmethod
    def from_identity(
        cls, identity: HistoricalSuccessRandomBaselineCellIdentity
    ) -> HistoricalSuccessRandomBaselineCellView:
        return cls.model_validate(identity, from_attributes=True)

    def to_identity(self) -> HistoricalSuccessRandomBaselineCellIdentity:
        return HistoricalSuccessRandomBaselineCellIdentity(
            policy_version=self.policy_version,
            import_identity_sha256=self.import_identity_sha256,
            dataset_sha256=self.dataset_sha256,
            source_artifact_sha256=self.source_artifact_sha256,
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            replicate=self.replicate,
            window_kind=self.window_kind,
            window_policy_version=self.window_policy_version,
            prefix_count=int(self.prefix_count),
            criterion=self.criterion,
        )


class HistoricalSuccessRandomBaselineExactRationalView(BaseModel):
    model_config = _RANDOM_BASELINE_RESPONSE

    numerator: CanonicalProbabilityInteger
    denominator: CanonicalPositiveInteger
    decimal_18: ExactDecimal18

    @model_validator(mode="after")
    def validate_exact_decimal(self) -> Self:
        exact = self.to_exact()
        if self.decimal_18 != render_exact_decimal_18(exact):
            raise ValueError("decimal_18 must be the exact HALF_EVEN rendering")
        return self

    @classmethod
    def from_exact(
        cls, exact: HistoricalSuccessExactRational
    ) -> HistoricalSuccessRandomBaselineExactRationalView:
        return cls(
            numerator=str(exact.numerator),
            denominator=str(exact.denominator),
            decimal_18=render_exact_decimal_18(exact),
        )

    def to_exact(self) -> HistoricalSuccessExactRational:
        return HistoricalSuccessExactRational(
            numerator=int(self.numerator),
            denominator=int(self.denominator),
        )


class HistoricalSuccessRandomBaselineResponse(BaseModel):
    model_config = _RANDOM_BASELINE_RESPONSE

    cell: HistoricalSuccessRandomBaselineCellView
    readiness: HistoricalSuccessRandomBaselineReadiness
    reason_codes: tuple[HistoricalSuccessRandomBaselineNotReadyReason, ...]
    sampling_policy: HistoricalSuccessRandomBaselineSamplingPolicy
    ticket_count_interpretation: str
    legal_ticket_count: CanonicalPositiveInteger
    success_ticket_count: CanonicalPositiveInteger
    portfolio_success_probability: HistoricalSuccessRandomBaselineExactRationalView
    eligible_observation_count: Annotated[int, Field(ge=0)]
    excluded_observation_count: Annotated[int, Field(ge=0)]
    observed_success_count: Annotated[int, Field(ge=0)] | None
    expected_successes: HistoricalSuccessRandomBaselineExactRationalView | None
    upper_tail_probability: HistoricalSuccessRandomBaselineExactRationalView | None
    observed_ticket_position_count: Annotated[int, Field(ge=0)]
    observed_distinct_ticket_count: Annotated[int, Field(ge=0)]
    observed_duplicate_ticket_count: Annotated[int, Field(ge=0)]
    observation_count_with_duplicates: Annotated[int, Field(ge=0)]
    interpretation_caveat: str

    @model_validator(mode="after")
    def validate_application_invariants(self) -> Self:
        HistoricalSuccessRandomBaselineResult(
            cell=self.cell.to_identity(),
            readiness=self.readiness,
            reason_codes=self.reason_codes,
            sampling_policy=self.sampling_policy,
            ticket_count_interpretation=self.ticket_count_interpretation,
            legal_ticket_count=int(self.legal_ticket_count),
            success_ticket_count=int(self.success_ticket_count),
            portfolio_success_probability=self.portfolio_success_probability.to_exact(),
            eligible_observation_count=self.eligible_observation_count,
            excluded_observation_count=self.excluded_observation_count,
            observed_success_count=self.observed_success_count,
            expected_successes=(
                None if self.expected_successes is None else self.expected_successes.to_exact()
            ),
            upper_tail_probability=(
                None
                if self.upper_tail_probability is None
                else self.upper_tail_probability.to_exact()
            ),
            observed_ticket_position_count=self.observed_ticket_position_count,
            observed_distinct_ticket_count=self.observed_distinct_ticket_count,
            observed_duplicate_ticket_count=self.observed_duplicate_ticket_count,
            observation_count_with_duplicates=self.observation_count_with_duplicates,
            interpretation_caveat=self.interpretation_caveat,
        )
        return self

    @classmethod
    def from_result(
        cls, result: HistoricalSuccessRandomBaselineResult
    ) -> HistoricalSuccessRandomBaselineResponse:
        return cls(
            cell=HistoricalSuccessRandomBaselineCellView.from_identity(result.cell),
            readiness=result.readiness,
            reason_codes=result.reason_codes,
            sampling_policy=result.sampling_policy,
            ticket_count_interpretation=result.ticket_count_interpretation,
            legal_ticket_count=str(result.legal_ticket_count),
            success_ticket_count=str(result.success_ticket_count),
            portfolio_success_probability=(
                HistoricalSuccessRandomBaselineExactRationalView.from_exact(
                    result.portfolio_success_probability
                )
            ),
            eligible_observation_count=result.eligible_observation_count,
            excluded_observation_count=result.excluded_observation_count,
            observed_success_count=result.observed_success_count,
            expected_successes=(
                None
                if result.expected_successes is None
                else HistoricalSuccessRandomBaselineExactRationalView.from_exact(
                    result.expected_successes
                )
            ),
            upper_tail_probability=(
                None
                if result.upper_tail_probability is None
                else HistoricalSuccessRandomBaselineExactRationalView.from_exact(
                    result.upper_tail_probability
                )
            ),
            observed_ticket_position_count=result.observed_ticket_position_count,
            observed_distinct_ticket_count=result.observed_distinct_ticket_count,
            observed_duplicate_ticket_count=result.observed_duplicate_ticket_count,
            observation_count_with_duplicates=result.observation_count_with_duplicates,
            interpretation_caveat=result.interpretation_caveat,
        )


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


class HistoricalPrefixRecentStabilityAuditSplitView(BaseModel):
    model_config = _FROZEN_RESPONSE

    source_temporal_split_method: Literal["FIXED_LAST_750_DISCOVERY_LAST_300_CONFIRMATION"]
    audit_split_method: Literal["FIXED_CONFIRMATION_FIRST_250_REFERENCE_LAST_50_RECENT"]
    total_assignment_count: Annotated[int, Field(ge=0)]
    warmup_count: Annotated[int, Field(ge=0)]
    discovery_count: Annotated[int, Field(ge=0)]
    confirmation_count: Annotated[int, Field(ge=0)]
    reference_count: Literal[0, 250]
    recent_count: Literal[0, 50]
    discovery_first_target: HistoricalPrefixSuccessDrawIdentityView | None
    discovery_last_target: HistoricalPrefixSuccessDrawIdentityView | None
    confirmation_first_target: HistoricalPrefixSuccessDrawIdentityView | None
    confirmation_last_target: HistoricalPrefixSuccessDrawIdentityView | None
    reference_first_target: HistoricalPrefixSuccessDrawIdentityView | None
    reference_last_target: HistoricalPrefixSuccessDrawIdentityView | None
    recent_first_target: HistoricalPrefixSuccessDrawIdentityView | None
    recent_last_target: HistoricalPrefixSuccessDrawIdentityView | None

    @classmethod
    def from_split(
        cls, split: HistoricalPrefixRecentStabilityAuditSplit
    ) -> HistoricalPrefixRecentStabilityAuditSplitView:
        if split.source_temporal_split_method != TEMPORAL_HOLDOUT_SPLIT_METHOD:
            raise ValueError("application temporal split method is inconsistent")
        if split.audit_split_method != RECENT_AUDIT_SPLIT_METHOD:
            raise ValueError("application audit split method is inconsistent")
        if split.reference_count not in (0, RECENT_REFERENCE_TARGET_COUNT):
            raise ValueError("application reference count is outside the closed contract")
        if split.recent_count not in (0, RECENT_AUDIT_TARGET_COUNT):
            raise ValueError("application recent count is outside the closed contract")
        reference_count = split.reference_count
        recent_count = split.recent_count

        def view(
            target: HistoricalPrefixSuccessDrawIdentity | None,
        ) -> HistoricalPrefixSuccessDrawIdentityView | None:
            return (
                HistoricalPrefixSuccessDrawIdentityView.from_identity(target)
                if target is not None
                else None
            )

        return cls(
            source_temporal_split_method=TEMPORAL_HOLDOUT_SPLIT_METHOD,
            audit_split_method=RECENT_AUDIT_SPLIT_METHOD,
            total_assignment_count=split.total_assignment_count,
            warmup_count=split.warmup_count,
            discovery_count=split.discovery_count,
            confirmation_count=split.confirmation_count,
            reference_count=reference_count,
            recent_count=recent_count,
            discovery_first_target=view(split.discovery_first_target),
            discovery_last_target=view(split.discovery_last_target),
            confirmation_first_target=view(split.confirmation_first_target),
            confirmation_last_target=view(split.confirmation_last_target),
            reference_first_target=view(split.reference_first_target),
            reference_last_target=view(split.reference_last_target),
            recent_first_target=view(split.recent_first_target),
            recent_last_target=view(split.recent_last_target),
        )


class HistoricalPrefixRecentStabilityAuditCohortComparisonView(BaseModel):
    model_config = _FROZEN_RESPONSE

    cohort_index: int
    feature_key: HistoricalPrefixFeatureRelationTripleView
    reference_diagnostic: HistoricalPrefixFeatureCohortDiagnosticView
    recent_diagnostic: HistoricalPrefixFeatureCohortDiagnosticView
    effect_change: HistoricalPrefixSignedRateDeltaView
    relationship: HistoricalPrefixTemporalHoldoutRelationship

    @model_validator(mode="after")
    def validate_comparison(self) -> Self:
        reference = self.reference_diagnostic
        recent = self.recent_diagnostic
        if (
            reference.cohort_index != self.cohort_index
            or recent.cohort_index != self.cohort_index
            or reference.feature_key != self.feature_key
            or recent.feature_key != self.feature_key
        ):
            raise ValueError("recent stability comparison identity is inconsistent")
        reference_effect = reference.risk_difference
        recent_effect = recent.risk_difference
        if reference_effect.available and recent_effect.available:
            expected = Fraction(
                recent_effect.numerator,
                recent_effect.denominator,
            ) - Fraction(
                reference_effect.numerator,
                reference_effect.denominator,
            )
            if (
                not self.effect_change.available
                or self.effect_change.numerator != expected.numerator
                or self.effect_change.denominator != expected.denominator
            ):
                raise ValueError("recent stability effect change is inconsistent")
        elif (
            self.effect_change.available
            or self.effect_change.numerator != 0
            or self.effect_change.denominator != 0
        ):
            raise ValueError("unavailable recent stability effect change is inconsistent")
        relationship = (
            HistoricalPrefixTemporalHoldoutRelationship.UNAVAILABLE
            if (
                reference.relation_vs_outside is HistoricalPrefixRateRelation.UNAVAILABLE
                or recent.relation_vs_outside is HistoricalPrefixRateRelation.UNAVAILABLE
            )
            else (
                HistoricalPrefixTemporalHoldoutRelationship.DIFFERENT
                if reference.relation_vs_outside is not recent.relation_vs_outside
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
                }[reference.relation_vs_outside]
            )
        )
        if self.relationship is not relationship:
            raise ValueError("recent stability relationship is inconsistent")
        return self

    @classmethod
    def from_comparison(
        cls, comparison: HistoricalPrefixRecentStabilityAuditCohortComparison
    ) -> HistoricalPrefixRecentStabilityAuditCohortComparisonView:
        return cls(
            cohort_index=comparison.cohort_index,
            feature_key=HistoricalPrefixFeatureRelationTripleView.from_feature_key(
                comparison.feature_key
            ),
            reference_diagnostic=HistoricalPrefixFeatureCohortDiagnosticView.from_diagnostic(
                comparison.reference_diagnostic
            ),
            recent_diagnostic=HistoricalPrefixFeatureCohortDiagnosticView.from_diagnostic(
                comparison.recent_diagnostic
            ),
            effect_change=HistoricalPrefixSignedRateDeltaView.from_delta(comparison.effect_change),
            relationship=comparison.relationship,
        )


class HistoricalPrefixRecentStabilityAuditResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    metadata: HistoricalPrefixSuccessSourceMetadataView
    strategy: HistoricalPrefixSuccessStrategyIdentityView
    criterion: HistoricalPrefixSuccessCriterionView
    prefix_count: int
    split: HistoricalPrefixRecentStabilityAuditSplitView
    audit_status: HistoricalPrefixRecentStabilityAuditStatus
    family_size: Literal[64]
    reference: HistoricalPrefixStrategyFeatureCohortDiagnosticsResponse | None
    recent: HistoricalPrefixStrategyFeatureCohortDiagnosticsResponse | None
    comparisons: tuple[HistoricalPrefixRecentStabilityAuditCohortComparisonView, ...]

    @model_validator(mode="after")
    def validate_audit(self) -> Self:
        split = self.split
        if (
            split.source_temporal_split_method != TEMPORAL_HOLDOUT_SPLIT_METHOD
            or split.audit_split_method != RECENT_AUDIT_SPLIT_METHOD
            or split.total_assignment_count
            != split.warmup_count + split.discovery_count + split.confirmation_count
            or split.confirmation_count != split.reference_count + split.recent_count
        ):
            raise ValueError("recent stability split arithmetic is inconsistent")
        boundaries = (
            split.discovery_first_target,
            split.discovery_last_target,
            split.confirmation_first_target,
            split.confirmation_last_target,
            split.reference_first_target,
            split.reference_last_target,
            split.recent_first_target,
            split.recent_last_target,
        )
        if (
            self.audit_status
            is HistoricalPrefixRecentStabilityAuditStatus.NOT_READY_INSUFFICIENT_HISTORY
        ):
            if (
                split.total_assignment_count >= REQUIRED_LABELED_TARGET_COUNT
                or split.warmup_count != split.total_assignment_count
                or any(
                    count != 0
                    for count in (
                        split.discovery_count,
                        split.confirmation_count,
                        split.reference_count,
                        split.recent_count,
                    )
                )
                or any(boundary is not None for boundary in boundaries)
                or self.reference is not None
                or self.recent is not None
                or self.comparisons
            ):
                raise ValueError("not-ready recent stability audit is inconsistent")
            return self
        if (
            split.total_assignment_count < REQUIRED_LABELED_TARGET_COUNT
            or split.discovery_count != DISCOVERY_TARGET_COUNT
            or split.confirmation_count != CONFIRMATION_TARGET_COUNT
            or split.reference_count != RECENT_REFERENCE_TARGET_COUNT
            or split.recent_count != RECENT_AUDIT_TARGET_COUNT
            or any(boundary is None for boundary in boundaries)
            or self.reference is None
            or self.recent is None
            or len(self.comparisons) != self.family_size
        ):
            raise ValueError("complete recent stability audit is inconsistent")
        non_null_boundaries = tuple(boundary for boundary in boundaries if boundary is not None)
        try:
            orders = tuple(
                (date.fromisoformat(boundary.draw_date), boundary.draw_number)
                for boundary in non_null_boundaries
            )
        except ValueError as exc:
            raise ValueError("recent stability boundary dates must be ISO dates") from exc
        (
            discovery_first_order,
            discovery_last_order,
            confirmation_first_order,
            confirmation_last_order,
            reference_first_order,
            reference_last_order,
            recent_first_order,
            recent_last_order,
        ) = orders
        if not (
            discovery_first_order
            <= discovery_last_order
            < confirmation_first_order
            == reference_first_order
            <= reference_last_order
            < recent_first_order
            <= recent_last_order
            == confirmation_last_order
        ):
            raise ValueError("recent stability phase boundaries are out of order")
        reference = self.reference
        recent = self.recent
        if (
            reference.metadata != self.metadata
            or recent.metadata != self.metadata
            or reference.strategy != self.strategy
            or recent.strategy != self.strategy
            or reference.criterion != self.criterion
            or recent.criterion != self.criterion
            or reference.prefix_count != self.prefix_count
            or recent.prefix_count != self.prefix_count
            or reference.baseline.observation_count != RECENT_REFERENCE_TARGET_COUNT
            or recent.baseline.observation_count != RECENT_AUDIT_TARGET_COUNT
        ):
            raise ValueError("recent stability phase identity is inconsistent")
        for index, comparison in enumerate(self.comparisons):
            if (
                comparison.cohort_index != index
                or comparison.reference_diagnostic != reference.diagnostics[index]
                or comparison.recent_diagnostic != recent.diagnostics[index]
            ):
                raise ValueError("recent stability comparisons must preserve canonical order")
        return self

    @classmethod
    def from_result(
        cls, result: HistoricalPrefixRecentStabilityAuditResult
    ) -> HistoricalPrefixRecentStabilityAuditResponse:
        if result.family_size != 64:
            raise ValueError("application recent stability family size is inconsistent")
        return cls(
            metadata=HistoricalPrefixSuccessSourceMetadataView.from_metadata(result.metadata),
            strategy=HistoricalPrefixSuccessStrategyIdentityView.from_identity(result.strategy),
            criterion=HistoricalPrefixSuccessCriterionView.from_identity(result.criterion),
            prefix_count=result.prefix_count,
            split=HistoricalPrefixRecentStabilityAuditSplitView.from_split(result.split),
            audit_status=result.audit_status,
            family_size=64,
            reference=(
                HistoricalPrefixStrategyFeatureCohortDiagnosticsResponse.from_result(
                    result.reference
                )
                if result.reference is not None
                else None
            ),
            recent=(
                HistoricalPrefixStrategyFeatureCohortDiagnosticsResponse.from_result(result.recent)
                if result.recent is not None
                else None
            ),
            comparisons=tuple(
                HistoricalPrefixRecentStabilityAuditCohortComparisonView.from_comparison(
                    comparison
                )
                for comparison in result.comparisons
            ),
        )


class HistoricalPrefixCrossImportMetadataView(BaseModel):
    model_config = _FROZEN_RESPONSE

    left: HistoricalPrefixSuccessSourceMetadataView
    right: HistoricalPrefixSuccessSourceMetadataView
    same_dataset_sha256: bool
    same_source_artifact_sha256: bool

    @model_validator(mode="after")
    def validate_pair(self) -> Self:
        if self.left.import_identity_sha256 == self.right.import_identity_sha256:
            raise ValueError("cross-import identities must be distinct")
        if self.same_dataset_sha256 != (
            self.left.dataset_sha256 == self.right.dataset_sha256
        ):
            raise ValueError("dataset equality disclosure is inconsistent")
        if self.same_source_artifact_sha256 != (
            self.left.source_artifact_sha256 == self.right.source_artifact_sha256
        ):
            raise ValueError("source-artifact equality disclosure is inconsistent")
        return self

    @classmethod
    def from_metadata(
        cls, metadata: HistoricalPrefixCrossImportMetadata
    ) -> HistoricalPrefixCrossImportMetadataView:
        return cls(
            left=HistoricalPrefixSuccessSourceMetadataView.from_metadata(metadata.left),
            right=HistoricalPrefixSuccessSourceMetadataView.from_metadata(metadata.right),
            same_dataset_sha256=metadata.same_dataset_sha256,
            same_source_artifact_sha256=metadata.same_source_artifact_sha256,
        )


class HistoricalPrefixConfirmationTargetOverlapView(BaseModel):
    model_config = _FROZEN_RESPONSE

    left_confirmation_target_count: Literal[300]
    right_confirmation_target_count: Literal[300]
    overlap_count: Annotated[int, Field(ge=0, le=300)]
    left_only_count: Annotated[int, Field(ge=0, le=300)]
    right_only_count: Annotated[int, Field(ge=0, le=300)]
    relation: HistoricalPrefixConfirmationOverlapRelation

    @model_validator(mode="after")
    def validate_overlap(self) -> Self:
        if (
            self.left_only_count + self.overlap_count
            != self.left_confirmation_target_count
            or self.right_only_count + self.overlap_count
            != self.right_confirmation_target_count
        ):
            raise ValueError("confirmation overlap arithmetic is inconsistent")
        expected = (
            HistoricalPrefixConfirmationOverlapRelation.DISJOINT
            if self.overlap_count == 0
            else (
                HistoricalPrefixConfirmationOverlapRelation.IDENTICAL
                if (
                    self.overlap_count == self.left_confirmation_target_count
                    == self.right_confirmation_target_count
                    and self.left_only_count == self.right_only_count == 0
                )
                else HistoricalPrefixConfirmationOverlapRelation.PARTIAL_OVERLAP
            )
        )
        if self.relation is not expected:
            raise ValueError("confirmation overlap relation is inconsistent")
        return self

    @classmethod
    def from_overlap(
        cls, overlap: HistoricalPrefixConfirmationTargetOverlap
    ) -> HistoricalPrefixConfirmationTargetOverlapView:
        return cls(
            left_confirmation_target_count=300,
            right_confirmation_target_count=300,
            overlap_count=overlap.overlap_count,
            left_only_count=overlap.left_only_count,
            right_only_count=overlap.right_only_count,
            relation=overlap.relation,
        )


class HistoricalPrefixCrossImportCohortComparisonView(BaseModel):
    model_config = _FROZEN_RESPONSE

    cohort_index: int
    feature_key: HistoricalPrefixFeatureRelationTripleView
    left_confirmation_diagnostic: HistoricalPrefixFeatureCohortDiagnosticView
    right_confirmation_diagnostic: HistoricalPrefixFeatureCohortDiagnosticView
    effect_change: HistoricalPrefixSignedRateDeltaView
    relationship: HistoricalPrefixTemporalHoldoutRelationship

    @model_validator(mode="after")
    def validate_comparison(self) -> Self:
        left = self.left_confirmation_diagnostic
        right = self.right_confirmation_diagnostic
        if (
            left.cohort_index != self.cohort_index
            or right.cohort_index != self.cohort_index
            or left.feature_key != self.feature_key
            or right.feature_key != self.feature_key
        ):
            raise ValueError("cross-import comparison identity is inconsistent")
        left_effect = left.risk_difference
        right_effect = right.risk_difference
        if left_effect.available and right_effect.available:
            expected_effect = Fraction(
                right_effect.numerator,
                right_effect.denominator,
            ) - Fraction(
                left_effect.numerator,
                left_effect.denominator,
            )
            if (
                not self.effect_change.available
                or self.effect_change.numerator != expected_effect.numerator
                or self.effect_change.denominator != expected_effect.denominator
            ):
                raise ValueError("cross-import effect change is inconsistent")
        elif (
            self.effect_change.available
            or self.effect_change.numerator != 0
            or self.effect_change.denominator != 0
        ):
            raise ValueError("unavailable cross-import effect change is inconsistent")
        expected_relationship = (
            HistoricalPrefixTemporalHoldoutRelationship.UNAVAILABLE
            if (
                left.relation_vs_outside is HistoricalPrefixRateRelation.UNAVAILABLE
                or right.relation_vs_outside is HistoricalPrefixRateRelation.UNAVAILABLE
            )
            else (
                HistoricalPrefixTemporalHoldoutRelationship.DIFFERENT
                if left.relation_vs_outside is not right.relation_vs_outside
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
                }[left.relation_vs_outside]
            )
        )
        if self.relationship is not expected_relationship:
            raise ValueError("cross-import relationship is inconsistent")
        return self

    @classmethod
    def from_comparison(
        cls, comparison: HistoricalPrefixCrossImportCohortComparison
    ) -> HistoricalPrefixCrossImportCohortComparisonView:
        return cls(
            cohort_index=comparison.cohort_index,
            feature_key=HistoricalPrefixFeatureRelationTripleView.from_feature_key(
                comparison.feature_key
            ),
            left_confirmation_diagnostic=(
                HistoricalPrefixFeatureCohortDiagnosticView.from_diagnostic(
                    comparison.left_confirmation_diagnostic
                )
            ),
            right_confirmation_diagnostic=(
                HistoricalPrefixFeatureCohortDiagnosticView.from_diagnostic(
                    comparison.right_confirmation_diagnostic
                )
            ),
            effect_change=HistoricalPrefixSignedRateDeltaView.from_delta(comparison.effect_change),
            relationship=comparison.relationship,
        )


class HistoricalPrefixCrossImportConcordanceResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    metadata: HistoricalPrefixCrossImportMetadataView
    strategy: HistoricalPrefixSuccessStrategyIdentityView
    criterion: HistoricalPrefixSuccessCriterionView
    prefix_count: int
    pair_status: HistoricalPrefixCrossImportPairStatus
    left_holdout_status: HistoricalPrefixTemporalHoldoutStatus
    right_holdout_status: HistoricalPrefixTemporalHoldoutStatus
    confirmation_target_overlap: HistoricalPrefixConfirmationTargetOverlapView | None
    comparisons: tuple[HistoricalPrefixCrossImportCohortComparisonView, ...]

    @model_validator(mode="after")
    def validate_concordance(self) -> Self:
        left_ready = (
            self.left_holdout_status is HistoricalPrefixTemporalHoldoutStatus.COMPLETE
        )
        right_ready = (
            self.right_holdout_status is HistoricalPrefixTemporalHoldoutStatus.COMPLETE
        )
        expected_status = (
            HistoricalPrefixCrossImportPairStatus.COMPLETE
            if left_ready and right_ready
            else (
                HistoricalPrefixCrossImportPairStatus.BOTH_NOT_READY
                if not left_ready and not right_ready
                else (
                    HistoricalPrefixCrossImportPairStatus.LEFT_NOT_READY
                    if not left_ready
                    else HistoricalPrefixCrossImportPairStatus.RIGHT_NOT_READY
                )
            )
        )
        if self.pair_status is not expected_status:
            raise ValueError("cross-import pair status is inconsistent")
        if self.pair_status is not HistoricalPrefixCrossImportPairStatus.COMPLETE:
            if self.confirmation_target_overlap is not None or self.comparisons:
                raise ValueError("not-ready concordance cannot contain comparisons")
            return self
        if self.confirmation_target_overlap is None or len(self.comparisons) != 64:
            raise ValueError("complete concordance requires overlap and 64 comparisons")
        for index, comparison in enumerate(self.comparisons):
            expected_key = (
                FEATURE_COHORT_RELATION_ORDER[index // 16],
                FEATURE_COHORT_RELATION_ORDER[(index % 16) // 4],
                FEATURE_COHORT_RELATION_ORDER[index % 4],
            )
            feature_key = comparison.feature_key
            if (
                comparison.cohort_index != index
                or (
                    feature_key.long_to_medium,
                    feature_key.medium_to_short,
                    feature_key.long_to_short,
                )
                != expected_key
            ):
                raise ValueError("concordance comparisons must preserve canonical order")
        return self

    @classmethod
    def from_result(
        cls, result: HistoricalPrefixCrossImportConcordanceResult
    ) -> HistoricalPrefixCrossImportConcordanceResponse:
        return cls(
            metadata=HistoricalPrefixCrossImportMetadataView.from_metadata(result.metadata),
            strategy=HistoricalPrefixSuccessStrategyIdentityView.from_identity(result.strategy),
            criterion=HistoricalPrefixSuccessCriterionView.from_identity(result.criterion),
            prefix_count=result.prefix_count,
            pair_status=result.pair_status,
            left_holdout_status=result.left_holdout_status,
            right_holdout_status=result.right_holdout_status,
            confirmation_target_overlap=(
                HistoricalPrefixConfirmationTargetOverlapView.from_overlap(
                    result.confirmation_target_overlap
                )
                if result.confirmation_target_overlap is not None
                else None
            ),
            comparisons=tuple(
                HistoricalPrefixCrossImportCohortComparisonView.from_comparison(comparison)
                for comparison in result.comparisons
            ),
        )


class HistoricalPrefixMultiImportSourceView(BaseModel):
    model_config = _FROZEN_RESPONSE

    import_index: Annotated[int, Field(ge=0, le=3)]
    metadata: HistoricalPrefixSuccessSourceMetadataView
    holdout_status: HistoricalPrefixTemporalHoldoutStatus


class HistoricalPrefixMultiImportPairView(BaseModel):
    model_config = _FROZEN_RESPONSE

    left_import_index: Annotated[int, Field(ge=0, le=3)]
    right_import_index: Annotated[int, Field(ge=1, le=3)]
    metadata: HistoricalPrefixCrossImportMetadataView
    pair_status: HistoricalPrefixCrossImportPairStatus
    left_holdout_status: HistoricalPrefixTemporalHoldoutStatus
    right_holdout_status: HistoricalPrefixTemporalHoldoutStatus
    confirmation_target_overlap: HistoricalPrefixConfirmationTargetOverlapView | None

    @model_validator(mode="after")
    def validate_pair(self) -> Self:
        if self.left_import_index >= self.right_import_index:
            raise ValueError("multi-import pair indexes must be canonical")
        left_ready = (
            self.left_holdout_status is HistoricalPrefixTemporalHoldoutStatus.COMPLETE
        )
        right_ready = (
            self.right_holdout_status is HistoricalPrefixTemporalHoldoutStatus.COMPLETE
        )
        expected_status = (
            HistoricalPrefixCrossImportPairStatus.COMPLETE
            if left_ready and right_ready
            else (
                HistoricalPrefixCrossImportPairStatus.BOTH_NOT_READY
                if not left_ready and not right_ready
                else (
                    HistoricalPrefixCrossImportPairStatus.LEFT_NOT_READY
                    if not left_ready
                    else HistoricalPrefixCrossImportPairStatus.RIGHT_NOT_READY
                )
            )
        )
        if self.pair_status is not expected_status:
            raise ValueError("multi-import pair status is inconsistent")
        if left_ready and right_ready:
            if self.confirmation_target_overlap is None:
                raise ValueError("ready multi-import pair requires confirmation overlap")
        elif self.confirmation_target_overlap is not None:
            raise ValueError("not-ready multi-import pair cannot contain overlap")
        return self

    @classmethod
    def from_pair(
        cls, pair: HistoricalPrefixMultiImportPairResult
    ) -> HistoricalPrefixMultiImportPairView:
        return cls(
            left_import_index=pair.left_import_index,
            right_import_index=pair.right_import_index,
            metadata=HistoricalPrefixCrossImportMetadataView.from_metadata(pair.metadata),
            pair_status=pair.pair_status,
            left_holdout_status=pair.left_holdout_status,
            right_holdout_status=pair.right_holdout_status,
            confirmation_target_overlap=(
                HistoricalPrefixConfirmationTargetOverlapView.from_overlap(
                    pair.confirmation_target_overlap
                )
                if pair.confirmation_target_overlap is not None
                else None
            ),
        )


class HistoricalPrefixMultiImportConfirmationDiagnosticView(BaseModel):
    model_config = _FROZEN_RESPONSE

    import_index: Annotated[int, Field(ge=0, le=3)]
    import_identity_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    diagnostic: HistoricalPrefixFeatureCohortDiagnosticView

    @classmethod
    def from_diagnostic(
        cls, item: HistoricalPrefixMultiImportConfirmationDiagnostic
    ) -> HistoricalPrefixMultiImportConfirmationDiagnosticView:
        return cls(
            import_index=item.import_index,
            import_identity_sha256=item.import_identity_sha256,
            diagnostic=HistoricalPrefixFeatureCohortDiagnosticView.from_diagnostic(
                item.diagnostic
            ),
        )


class HistoricalPrefixMultiImportCohortCensusRowView(BaseModel):
    model_config = _FROZEN_RESPONSE

    cohort_index: Annotated[int, Field(ge=0, le=63)]
    feature_key: HistoricalPrefixFeatureRelationTripleView
    confirmation_diagnostics: tuple[
        HistoricalPrefixMultiImportConfirmationDiagnosticView, ...
    ]
    higher_count: Annotated[int, Field(ge=0, le=4)]
    equal_count: Annotated[int, Field(ge=0, le=4)]
    lower_count: Annotated[int, Field(ge=0, le=4)]
    unavailable_count: Annotated[int, Field(ge=0, le=4)]
    summary: HistoricalPrefixMultiImportCensusSummary

    @model_validator(mode="after")
    def validate_census_row(self) -> Self:
        import_count = len(self.confirmation_diagnostics)
        if not 2 <= import_count <= 4:
            raise ValueError("census row requires two to four ordered diagnostics")
        if (
            self.higher_count
            + self.equal_count
            + self.lower_count
            + self.unavailable_count
            != import_count
        ):
            raise ValueError("census row direction counts are inconsistent")
        expected = (
            HistoricalPrefixMultiImportCensusSummary.NO_AVAILABLE_EFFECT
            if self.unavailable_count == import_count
            else (
                HistoricalPrefixMultiImportCensusSummary.PARTIAL_AVAILABILITY
                if self.unavailable_count > 0
                else (
                    HistoricalPrefixMultiImportCensusSummary.ALL_AVAILABLE_HIGHER
                    if self.higher_count == import_count
                    else (
                        HistoricalPrefixMultiImportCensusSummary.ALL_AVAILABLE_EQUAL
                        if self.equal_count == import_count
                        else (
                            HistoricalPrefixMultiImportCensusSummary.ALL_AVAILABLE_LOWER
                            if self.lower_count == import_count
                            else HistoricalPrefixMultiImportCensusSummary.MIXED_AVAILABLE
                        )
                    )
                )
            )
        )
        if self.summary is not expected:
            raise ValueError("census row summary is inconsistent")
        return self

    @classmethod
    def from_row(
        cls, row: HistoricalPrefixMultiImportCohortCensusRow
    ) -> HistoricalPrefixMultiImportCohortCensusRowView:
        return cls(
            cohort_index=row.cohort_index,
            feature_key=HistoricalPrefixFeatureRelationTripleView.from_feature_key(
                row.feature_key
            ),
            confirmation_diagnostics=tuple(
                HistoricalPrefixMultiImportConfirmationDiagnosticView.from_diagnostic(item)
                for item in row.confirmation_diagnostics
            ),
            higher_count=row.higher_count,
            equal_count=row.equal_count,
            lower_count=row.lower_count,
            unavailable_count=row.unavailable_count,
            summary=row.summary,
        )


class HistoricalPrefixMultiImportConcordanceCensusResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    imports: tuple[HistoricalPrefixMultiImportSourceView, ...]
    strategy: HistoricalPrefixSuccessStrategyIdentityView
    criterion: HistoricalPrefixSuccessCriterionView
    prefix_count: int
    census_status: HistoricalPrefixMultiImportCensusStatus
    pair_count: Annotated[int, Field(ge=1, le=6)]
    pairs: tuple[HistoricalPrefixMultiImportPairView, ...]
    cohort_census_count: Annotated[int, Field(ge=0, le=64)]
    cohort_census: tuple[HistoricalPrefixMultiImportCohortCensusRowView, ...]

    @model_validator(mode="after")
    def validate_census(self) -> Self:
        import_count = len(self.imports)
        if not 2 <= import_count <= 4:
            raise ValueError("multi-import census requires two to four imports")
        identities = tuple(
            item.metadata.import_identity_sha256 for item in self.imports
        )
        if len(set(identities)) != import_count or any(
            item.import_index != index for index, item in enumerate(self.imports)
        ):
            raise ValueError("multi-import sources must be distinct and preserve caller order")
        ready_count = sum(
            item.holdout_status is HistoricalPrefixTemporalHoldoutStatus.COMPLETE
            for item in self.imports
        )
        expected_census_status = (
            HistoricalPrefixMultiImportCensusStatus.COMPLETE
            if ready_count == import_count
            else (
                HistoricalPrefixMultiImportCensusStatus.ALL_NOT_READY
                if ready_count == 0
                else HistoricalPrefixMultiImportCensusStatus.PARTIAL_NOT_READY
            )
        )
        if self.census_status is not expected_census_status:
            raise ValueError("multi-import census status is inconsistent")

        expected_pair_indexes = tuple(
            (left, right)
            for left in range(import_count)
            for right in range(left + 1, import_count)
        )
        if (
            self.pair_count != len(expected_pair_indexes)
            or len(self.pairs) != self.pair_count
            or tuple(
                (pair.left_import_index, pair.right_import_index)
                for pair in self.pairs
            )
            != expected_pair_indexes
        ):
            raise ValueError("multi-import pair matrix order or cardinality is inconsistent")
        for pair in self.pairs:
            left = self.imports[pair.left_import_index]
            right = self.imports[pair.right_import_index]
            if (
                pair.metadata.left.import_identity_sha256
                != left.metadata.import_identity_sha256
                or pair.metadata.right.import_identity_sha256
                != right.metadata.import_identity_sha256
                or pair.left_holdout_status is not left.holdout_status
                or pair.right_holdout_status is not right.holdout_status
            ):
                raise ValueError("multi-import pair does not match ordered sources")

        if self.census_status is not HistoricalPrefixMultiImportCensusStatus.COMPLETE:
            if self.cohort_census_count != 0 or self.cohort_census:
                raise ValueError("not-ready multi-import census cannot contain cohort rows")
            return self
        if self.cohort_census_count != 64 or len(self.cohort_census) != 64:
            raise ValueError("complete multi-import census requires 64 cohort rows")
        for cohort_index, row in enumerate(self.cohort_census):
            expected_key = (
                FEATURE_COHORT_RELATION_ORDER[cohort_index // 16],
                FEATURE_COHORT_RELATION_ORDER[(cohort_index % 16) // 4],
                FEATURE_COHORT_RELATION_ORDER[cohort_index % 4],
            )
            if (
                row.cohort_index != cohort_index
                or (
                    row.feature_key.long_to_medium,
                    row.feature_key.medium_to_short,
                    row.feature_key.long_to_short,
                )
                != expected_key
                or tuple(
                    (item.import_index, item.import_identity_sha256)
                    for item in row.confirmation_diagnostics
                )
                != tuple(enumerate(identities))
                or any(
                    item.diagnostic.cohort_index != cohort_index
                    or item.diagnostic.feature_key != row.feature_key
                    for item in row.confirmation_diagnostics
                )
            ):
                raise ValueError(
                    "multi-import census rows must preserve cohort and import order"
                )
        return self

    @classmethod
    def from_result(
        cls, result: HistoricalPrefixMultiImportConcordanceCensusResult
    ) -> HistoricalPrefixMultiImportConcordanceCensusResponse:
        return cls(
            imports=tuple(
                HistoricalPrefixMultiImportSourceView(
                    import_index=index,
                    metadata=HistoricalPrefixSuccessSourceMetadataView.from_metadata(
                        item.metadata
                    ),
                    holdout_status=item.holdout_status,
                )
                for index, item in enumerate(result.imports)
            ),
            strategy=HistoricalPrefixSuccessStrategyIdentityView.from_identity(
                result.strategy
            ),
            criterion=HistoricalPrefixSuccessCriterionView.from_identity(
                result.criterion
            ),
            prefix_count=result.prefix_count,
            census_status=result.census_status,
            pair_count=result.pair_count,
            pairs=tuple(
                HistoricalPrefixMultiImportPairView.from_pair(pair)
                for pair in result.pairs
            ),
            cohort_census_count=result.cohort_census_count,
            cohort_census=tuple(
                HistoricalPrefixMultiImportCohortCensusRowView.from_row(row)
                for row in result.cohort_census
            ),
        )


class HistoricalSuccessQualificationIdentityView(BaseModel):
    model_config = _QUALIFICATION_RESPONSE

    strategy_id: str
    strategy_version: str
    replicate: Annotated[int, Field(ge=1)]
    prefix_count: HistoricalPrefixSuccessPrefixCount
    criterion: HistoricalPrefixSuccessCriterion


class HistoricalSuccessQualificationImportEvidenceView(BaseModel):
    model_config = _QUALIFICATION_RESPONSE

    import_index: Annotated[int, Field(ge=0, le=3)]
    import_identity_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    dataset_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    source_artifact_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    source_observation_count: Annotated[int, Field(ge=0)]
    strategy_window_status: HistoricalSuccessQualificationEvidenceStatus
    temporal_holdout_status: HistoricalSuccessQualificationEvidenceStatus
    recent_audit_status: HistoricalSuccessQualificationEvidenceStatus
    recent_relationship_difference_count: Annotated[int, Field(ge=0, le=64)]

    @model_validator(mode="after")
    def validate_readiness(self) -> Self:
        if (
            self.temporal_holdout_status
            is HistoricalSuccessQualificationEvidenceStatus.COMPLETE
        ) != (
            self.recent_audit_status
            is HistoricalSuccessQualificationEvidenceStatus.COMPLETE
        ):
            raise ValueError("temporal holdout and recent audit readiness must agree")
        if (
            self.recent_audit_status
            is HistoricalSuccessQualificationEvidenceStatus.NOT_READY
            and self.recent_relationship_difference_count != 0
        ):
            raise ValueError("not-ready recent evidence cannot contain differences")
        return self


class HistoricalSuccessQualificationPairEvidenceView(BaseModel):
    model_config = _QUALIFICATION_RESPONSE

    left_import_index: Annotated[int, Field(ge=0, le=2)]
    right_import_index: Annotated[int, Field(ge=1, le=3)]
    pair_status: HistoricalSuccessQualificationPairStatus
    same_dataset_sha256: bool
    same_source_artifact_sha256: bool
    confirmation_overlap_relation: (
        HistoricalSuccessQualificationOverlapRelation | None
    )
    r1_comparable: bool

    @model_validator(mode="after")
    def validate_comparability(self) -> Self:
        if self.left_import_index >= self.right_import_index:
            raise ValueError("qualification pair indexes must be canonical")
        expected = (
            self.pair_status is HistoricalSuccessQualificationPairStatus.COMPLETE
            and not self.same_dataset_sha256
            and not self.same_source_artifact_sha256
            and self.confirmation_overlap_relation
            in {
                HistoricalSuccessQualificationOverlapRelation.PARTIAL_OVERLAP,
                HistoricalSuccessQualificationOverlapRelation.DISJOINT,
            }
        )
        if self.r1_comparable is not expected:
            raise ValueError("qualification pair comparability is inconsistent")
        if (
            self.pair_status is HistoricalSuccessQualificationPairStatus.COMPLETE
        ) != (self.confirmation_overlap_relation is not None):
            raise ValueError("qualification pair overlap readiness is inconsistent")
        return self


class HistoricalSuccessResearchQualificationResponse(BaseModel):
    model_config = _QUALIFICATION_RESPONSE

    identity: HistoricalSuccessQualificationIdentityView
    ordered_import_evidence: tuple[
        HistoricalSuccessQualificationImportEvidenceView, ...
    ]
    primary_status: HistoricalSuccessQualificationPrimaryStatus
    informational_flags: tuple[
        HistoricalSuccessQualificationInformationalFlag, ...
    ]
    random_baseline_caveat: str | None
    comparable_import_count: Annotated[int, Field(ge=0, le=4)]
    expected_pair_count: Annotated[int, Field(ge=1, le=6)]
    actual_pair_count: Annotated[int, Field(ge=0, le=6)]
    census_status: HistoricalSuccessQualificationCensusStatus
    cohort_census_count: Annotated[int, Field(ge=0, le=64)]
    pair_evidence: tuple[HistoricalSuccessQualificationPairEvidenceView, ...]

    @model_validator(mode="after")
    def validate_qualification(self) -> Self:
        imports = self.ordered_import_evidence
        import_count = len(imports)
        if (
            not 2 <= import_count <= 4
            or tuple(item.import_index for item in imports)
            != tuple(range(import_count))
            or len({item.import_identity_sha256 for item in imports}) != import_count
        ):
            raise ValueError(
                "qualification imports must be two to four distinct ordered identities"
            )
        expected_pair_count = import_count * (import_count - 1) // 2
        if self.expected_pair_count != expected_pair_count:
            raise ValueError("qualification expected pair count is inconsistent")
        if self.actual_pair_count != len(self.pair_evidence):
            raise ValueError("qualification actual pair count is inconsistent")
        pair_indexes = tuple(
            (pair.left_import_index, pair.right_import_index)
            for pair in self.pair_evidence
        )
        if (
            pair_indexes != tuple(sorted(pair_indexes))
            or len(set(pair_indexes)) != len(pair_indexes)
            or any(right >= import_count for _, right in pair_indexes)
        ):
            raise ValueError("qualification pairs must preserve canonical import order")
        comparable_indexes = {
            index
            for pair in self.pair_evidence
            if pair.r1_comparable
            for index in (pair.left_import_index, pair.right_import_index)
        }
        if self.comparable_import_count != len(comparable_indexes):
            raise ValueError("qualification comparable import count is inconsistent")
        canonical_flags = tuple(
            flag
            for flag in (
                HistoricalSuccessQualificationInformationalFlag.CROSS_IMPORT_UNRESOLVED,
                HistoricalSuccessQualificationInformationalFlag.HISTORICAL_CONCORDANCE_OBSERVED,
                HistoricalSuccessQualificationInformationalFlag.RECENT_RELATIONSHIP_DIFFERENCE,
            )
            if flag in self.informational_flags
        )
        if (
            len(set(self.informational_flags)) != len(self.informational_flags)
            or self.informational_flags != canonical_flags
        ):
            raise ValueError("qualification flags must be unique and canonically ordered")
        unresolved = (
            HistoricalSuccessQualificationInformationalFlag.CROSS_IMPORT_UNRESOLVED
            in self.informational_flags
        )
        concordant = (
            HistoricalSuccessQualificationInformationalFlag.HISTORICAL_CONCORDANCE_OBSERVED
            in self.informational_flags
        )
        if unresolved and concordant:
            raise ValueError("qualification flags are contradictory")
        candidate = (
            self.primary_status
            is HistoricalSuccessQualificationPrimaryStatus.RESEARCH_CANDIDATE
        )
        if candidate:
            if (
                not concordant
                or self.random_baseline_caveat != RANDOM_BASELINE_CAVEAT
                or self.census_status
                is not HistoricalSuccessQualificationCensusStatus.COMPLETE
                or self.cohort_census_count != 64
                or self.actual_pair_count != self.expected_pair_count
                or any(not pair.r1_comparable for pair in self.pair_evidence)
            ):
                raise ValueError("research-candidate qualification is inconsistent")
        elif self.random_baseline_caveat is not None:
            raise ValueError("non-candidate qualification cannot carry candidate caveat")
        if concordant and not candidate:
            raise ValueError("historical concordance requires research-candidate status")
        return self

    @classmethod
    def from_result(
        cls, result: HistoricalSuccessResearchQualification
    ) -> HistoricalSuccessResearchQualificationResponse:
        return cls(
            identity=HistoricalSuccessQualificationIdentityView(
                strategy_id=result.identity.strategy_id,
                strategy_version=result.identity.strategy_version,
                replicate=result.identity.replicate,
                prefix_count=HistoricalPrefixSuccessPrefixCount(
                    result.identity.prefix_count
                ),
                criterion=HistoricalPrefixSuccessCriterion(result.identity.criterion),
            ),
            ordered_import_evidence=tuple(
                HistoricalSuccessQualificationImportEvidenceView(
                    import_index=item.import_index,
                    import_identity_sha256=item.import_identity_sha256,
                    dataset_sha256=item.dataset_sha256,
                    source_artifact_sha256=item.source_artifact_sha256,
                    source_observation_count=item.source_observation_count,
                    strategy_window_status=item.strategy_window_status,
                    temporal_holdout_status=item.temporal_holdout_status,
                    recent_audit_status=item.recent_audit_status,
                    recent_relationship_difference_count=(
                        item.recent_relationship_difference_count
                    ),
                )
                for item in result.imports
            ),
            primary_status=result.primary_status,
            informational_flags=result.informational_flags,
            random_baseline_caveat=result.random_baseline_caveat,
            comparable_import_count=result.comparable_import_count,
            expected_pair_count=result.expected_pair_count,
            actual_pair_count=result.actual_pair_count,
            census_status=result.census_status,
            cohort_census_count=result.cohort_census_count,
            pair_evidence=tuple(
                HistoricalSuccessQualificationPairEvidenceView(
                    left_import_index=pair.left_import_index,
                    right_import_index=pair.right_import_index,
                    pair_status=pair.pair_status,
                    same_dataset_sha256=pair.same_dataset_sha256,
                    same_source_artifact_sha256=(
                        pair.same_source_artifact_sha256
                    ),
                    confirmation_overlap_relation=(
                        pair.confirmation_overlap_relation
                    ),
                    r1_comparable=pair.r1_comparable,
                )
                for pair in result.pairs
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
            "{strategy_id}/{strategy_version}/{replicate}/random-null-baseline"
        ),
        response_model=HistoricalSuccessRandomBaselineResponse,
        responses=error_responses,
        operation_id="getHistoricalPrefixStrategyRandomNullBaseline",
    )
    def get_historical_prefix_strategy_random_null_baseline(
        request: Request,
        strategy_id: StrategyId,
        strategy_version: StrategyVersion,
        replicate: Replicate,
        import_identity_sha256: ImportIdentitySha256,
        prefix_count: HistoricalPrefixSuccessPrefixCount,
        criterion: HistoricalPrefixSuccessCriterion,
        window_kind: WindowKind,
    ) -> HistoricalSuccessRandomBaselineResponse | JSONResponse:
        unexpected = sorted(
            set(request.query_params.keys())
            - {
                "import_identity_sha256",
                "prefix_count",
                "criterion",
                "window_kind",
            }
        )
        if unexpected:
            return _invalid_matrix_query_error(unexpected)
        if evaluator is None:
            return _not_configured_error()
        try:
            result = evaluator.get_random_null_baseline(
                import_identity_sha256=import_identity_sha256,
                strategy_id=strategy_id,
                strategy_version=strategy_version,
                replicate=replicate,
                window_kind=window_kind,
                prefix_count=int(prefix_count),
                criterion=criterion,
            )
        except HistoricalPrefixSuccessImportNotFoundError:
            return _import_not_found_error()
        except HistoricalPrefixSuccessStrategyNotFoundError:
            return _strategy_not_found_error()
        except Exception:
            return _unavailable_error()
        return HistoricalSuccessRandomBaselineResponse.from_result(result)

    @router.get(
        (
            "/historical-prefix-success-windows/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}/research-qualification"
        ),
        response_model=HistoricalSuccessResearchQualificationResponse,
        responses=error_responses,
        operation_id="getHistoricalPrefixStrategyResearchQualification",
    )
    def get_historical_prefix_strategy_research_qualification(
        request: Request,
        strategy_id: StrategyId,
        strategy_version: StrategyVersion,
        replicate: Replicate,
        import_identity_sha256: MultiImportIdentitySha256,
        prefix_count: HistoricalPrefixSuccessPrefixCount,
        criterion: HistoricalPrefixSuccessCriterion,
    ) -> HistoricalSuccessResearchQualificationResponse | JSONResponse:
        unexpected = sorted(
            set(request.query_params.keys())
            - {"import_identity_sha256", "prefix_count", "criterion"}
        )
        if unexpected:
            return _invalid_matrix_query_error(unexpected)
        if evaluator is None:
            return _not_configured_error()
        try:
            result = evaluator.get_research_qualification(
                import_identity_sha256s=tuple(import_identity_sha256),
                strategy_id=strategy_id,
                strategy_version=strategy_version,
                replicate=replicate,
                prefix_count=int(prefix_count),
                criterion=criterion,
            )
        except HistoricalPrefixSuccessWindowsContractError:
            return _duplicate_imports_error()
        except HistoricalPrefixSuccessImportNotFoundError:
            return _import_not_found_error()
        except HistoricalPrefixSuccessStrategyNotFoundError:
            return _strategy_not_found_error()
        except Exception:
            return _unavailable_error()
        return HistoricalSuccessResearchQualificationResponse.from_result(result)

    @router.get(
        (
            "/historical-prefix-success-windows/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}/feature-cohorts/"
            "multi-import-concordance-census"
        ),
        response_model=HistoricalPrefixMultiImportConcordanceCensusResponse,
        responses=error_responses,
        operation_id="getHistoricalPrefixStrategyMultiImportConcordanceCensus",
    )
    def get_historical_prefix_strategy_multi_import_concordance_census(
        request: Request,
        strategy_id: StrategyId,
        strategy_version: StrategyVersion,
        replicate: Replicate,
        import_identity_sha256: MultiImportIdentitySha256,
        prefix_count: HistoricalPrefixSuccessPrefixCount,
        criterion: HistoricalPrefixSuccessCriterion,
    ) -> HistoricalPrefixMultiImportConcordanceCensusResponse | JSONResponse:
        unexpected = sorted(
            set(request.query_params.keys())
            - {"import_identity_sha256", "prefix_count", "criterion"}
        )
        if unexpected:
            return _invalid_matrix_query_error(unexpected)
        if evaluator is None:
            return _not_configured_error()
        try:
            result = evaluator.get_multi_import_concordance_census(
                import_identity_sha256s=tuple(import_identity_sha256),
                strategy_id=strategy_id,
                strategy_version=strategy_version,
                replicate=replicate,
                prefix_count=int(prefix_count),
                criterion=criterion,
            )
        except HistoricalPrefixSuccessWindowsContractError:
            return _duplicate_imports_error()
        except HistoricalPrefixSuccessImportNotFoundError:
            return _import_not_found_error()
        except HistoricalPrefixSuccessStrategyNotFoundError:
            return _strategy_not_found_error()
        except Exception:
            return _unavailable_error()
        return HistoricalPrefixMultiImportConcordanceCensusResponse.from_result(result)

    @router.get(
        (
            "/historical-prefix-success-windows/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}/feature-cohorts/"
            "cross-import-concordance"
        ),
        response_model=HistoricalPrefixCrossImportConcordanceResponse,
        responses=error_responses,
        operation_id="getHistoricalPrefixStrategyCrossImportConcordance",
    )
    def get_historical_prefix_strategy_cross_import_concordance(
        request: Request,
        strategy_id: StrategyId,
        strategy_version: StrategyVersion,
        replicate: Replicate,
        left_import_identity_sha256: ImportIdentitySha256,
        right_import_identity_sha256: ImportIdentitySha256,
        prefix_count: HistoricalPrefixSuccessPrefixCount,
        criterion: HistoricalPrefixSuccessCriterion,
    ) -> HistoricalPrefixCrossImportConcordanceResponse | JSONResponse:
        unexpected = sorted(
            set(request.query_params.keys())
            - {
                "left_import_identity_sha256",
                "right_import_identity_sha256",
                "prefix_count",
                "criterion",
            }
        )
        if unexpected:
            return _invalid_matrix_query_error(unexpected)
        if evaluator is None:
            return _not_configured_error()
        try:
            result = evaluator.get_cross_import_concordance(
                left_import_identity_sha256=left_import_identity_sha256,
                right_import_identity_sha256=right_import_identity_sha256,
                strategy_id=strategy_id,
                strategy_version=strategy_version,
                replicate=replicate,
                prefix_count=int(prefix_count),
                criterion=criterion,
            )
        except HistoricalPrefixSuccessWindowsContractError:
            return _identical_imports_error()
        except HistoricalPrefixSuccessImportNotFoundError:
            return _import_not_found_error()
        except HistoricalPrefixSuccessStrategyNotFoundError:
            return _strategy_not_found_error()
        except Exception:
            return _unavailable_error()
        return HistoricalPrefixCrossImportConcordanceResponse.from_result(result)

    @router.get(
        (
            "/historical-prefix-success-windows/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}/feature-cohorts/"
            "recent-50-stability-audit"
        ),
        response_model=HistoricalPrefixRecentStabilityAuditResponse,
        responses=error_responses,
        operation_id="getHistoricalPrefixStrategyFeatureCohortRecent50StabilityAudit",
    )
    def get_historical_prefix_strategy_feature_cohort_recent_50_stability_audit(
        request: Request,
        strategy_id: StrategyId,
        strategy_version: StrategyVersion,
        replicate: Replicate,
        import_identity_sha256: ImportIdentitySha256,
        prefix_count: HistoricalPrefixSuccessPrefixCount,
        criterion: HistoricalPrefixSuccessCriterion,
    ) -> HistoricalPrefixRecentStabilityAuditResponse | JSONResponse:
        unexpected = sorted(
            set(request.query_params.keys())
            - {"import_identity_sha256", "prefix_count", "criterion"}
        )
        if unexpected:
            return _invalid_matrix_query_error(unexpected)
        if evaluator is None:
            return _not_configured_error()
        try:
            result = evaluator.get_feature_cohort_recent_50_stability_audit(
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
        return HistoricalPrefixRecentStabilityAuditResponse.from_result(result)

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


def _identical_imports_error() -> JSONResponse:
    model = ApiValidationErrorResponse(
        error_code="REQUEST_VALIDATION_FAILED",
        message="Request validation failed.",
        fields=[
            RequestValidationIssueView(
                location="query.right_import_identity_sha256",
                type="value_error",
            )
        ],
    )
    return JSONResponse(status_code=422, content=model.model_dump(mode="json"))


def _duplicate_imports_error() -> JSONResponse:
    model = ApiValidationErrorResponse(
        error_code="REQUEST_VALIDATION_FAILED",
        message="Request validation failed.",
        fields=[
            RequestValidationIssueView(
                location="query.import_identity_sha256",
                type="value_error",
            )
        ],
    )
    return JSONResponse(status_code=422, content=model.model_dump(mode="json"))


def _error_response(status_code: int, error_code: str, message: str) -> JSONResponse:
    model = ApiErrorResponse(error_code=error_code, message=message)
    return JSONResponse(status_code=status_code, content=model.model_dump(mode="json"))


__all__ = [
    "HistoricalPrefixConfirmationTargetOverlapView",
    "HistoricalPrefixCrossImportCohortComparisonView",
    "HistoricalPrefixCrossImportConcordanceResponse",
    "HistoricalPrefixCrossImportMetadataView",
    "HistoricalPrefixExactProbabilityView",
    "HistoricalPrefixExactSuccessRateView",
    "HistoricalPrefixFeatureCohortDiagnosticView",
    "HistoricalPrefixFeatureCohortTestStatus",
    "HistoricalPrefixFeatureCohortView",
    "HistoricalPrefixFeatureRelationTripleView",
    "HistoricalPrefixMultiImportCohortCensusRowView",
    "HistoricalPrefixMultiImportConcordanceCensusResponse",
    "HistoricalPrefixMultiImportConfirmationDiagnosticView",
    "HistoricalPrefixMultiImportPairView",
    "HistoricalPrefixMultiImportSourceView",
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
    "HistoricalSuccessRandomBaselineCellView",
    "HistoricalSuccessRandomBaselineExactRationalView",
    "HistoricalSuccessRandomBaselineResponse",
    "create_historical_prefix_success_windows_router",
]
