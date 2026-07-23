"""GET-only API for persisted Historical Prefix strategy-success windows."""

# pyright: reportUnusedFunction=false

from __future__ import annotations

from enum import IntEnum
from typing import Annotated, Any

from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from lottolab.application.historical_prefix_success_windows import (
    DEFAULT_PAGE_LIMIT,
    DEFAULT_PAGE_OFFSET,
    MAX_PAGE_LIMIT,
    MIN_PAGE_LIMIT,
    HistoricalPrefixExactSuccessRate,
    HistoricalPrefixRateRelation,
    HistoricalPrefixSignedRateDelta,
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
            success_rate=HistoricalPrefixExactSuccessRateView.from_rate(
                summary.success_rate
            ),
            first_target=HistoricalPrefixSuccessDrawIdentityView.from_identity(
                summary.first_target
            ),
            last_target=HistoricalPrefixSuccessDrawIdentityView.from_identity(
                summary.last_target
            ),
            first_cutoff=HistoricalPrefixSuccessDrawIdentityView.from_identity(
                summary.first_cutoff
            ),
            last_cutoff=HistoricalPrefixSuccessDrawIdentityView.from_identity(
                summary.last_cutoff
            ),
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
            strategy=HistoricalPrefixSuccessStrategyIdentityView.from_identity(
                result.strategy
            ),
            criterion=HistoricalPrefixSuccessCriterionView.from_identity(
                result.criterion
            ),
            prefix_count=result.prefix_count,
            selection=HistoricalPrefixSuccessSelectionIdentityView.from_identity(
                result.selection
            ),
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
            metadata=HistoricalPrefixSuccessSourceMetadataView.from_metadata(
                page.metadata
            ),
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
            from_rate=HistoricalPrefixExactSuccessRateView.from_rate(
                comparison.from_rate
            ),
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
            selection=HistoricalPrefixSuccessSelectionIdentityView.from_identity(
                cell.selection
            ),
            status=cell.status.value,
            source_observation_count=cell.source_observation_count,
            windows=tuple(
                HistoricalPrefixSuccessWindowSummaryView.from_summary(item)
                for item in cell.windows
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
            metadata=HistoricalPrefixSuccessSourceMetadataView.from_metadata(
                matrix.metadata
            ),
            strategy=HistoricalPrefixSuccessStrategyIdentityView.from_identity(
                matrix.strategy
            ),
            source_observation_count=matrix.source_observation_count,
            prefix_counts=matrix.prefix_counts,
            criteria=tuple(
                HistoricalPrefixSuccessCriterionView.from_identity(item)
                for item in matrix.criteria
            ),
            cell_count=matrix.cell_count,
            cells=tuple(
                HistoricalPrefixStrategySuccessMatrixCellView.from_cell(item)
                for item in matrix.cells
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
        unexpected = sorted(
            set(request.query_params.keys()) - {"import_identity_sha256"}
        )
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
    "HistoricalPrefixExactSuccessRateView",
    "HistoricalPrefixSignedRateDeltaView",
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
    "HistoricalPrefixWindowRateComparisonView",
    "create_historical_prefix_success_windows_router",
]
