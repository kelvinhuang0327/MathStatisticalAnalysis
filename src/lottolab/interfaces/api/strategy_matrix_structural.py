"""Read-only HTTP projection of the canonical structural Matrix authority.

Distinct authority family from historical success-rate or ranking evidence:
this endpoint never exposes a historical success rate, a ranking score, or
any combined structural/historical score.
"""

# pyright: reportUnusedFunction=false

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from lottolab.application.ports import StrategyMatrixStructuralReaderFactory
from lottolab.application.strategy_matrix_structural import (
    StrategyMatrixStructuralDataset,
    StrategyMatrixStructuralQuery,
    StructuralCaseId,
    StructuralLottery,
    StructuralMatrixCell,
    StructuralMeasurementStatus,
    StructuralMethodId,
    StructuralSourceStatus,
    StructuralTicketCount,
)
from lottolab.application.use_cases.query_strategy_matrix_structural import (
    QueryStrategyMatrixStructural,
)
from lottolab.infrastructure.strategy_matrix_structural_reader import (
    StrategyMatrixStructuralProjectionError,
)
from lottolab.interfaces.api.draw_data import (
    ApiErrorResponse,
    ApiValidationErrorResponse,
    RequestValidationIssueView,
)
from lottolab.interfaces.api.strategy_catalog import API_PREFIX

_FROZEN_RESPONSE = ConfigDict(frozen=True, extra="forbid")
_ALLOWED_QUERY_FIELDS = frozenset({"lottery", "method_id", "ticket_count"})


class SourceReferenceView(BaseModel):
    model_config = _FROZEN_RESPONSE

    repository_path: str
    file_sha256: str


class StructuralMatrixAuthoritySourcesView(BaseModel):
    model_config = _FROZEN_RESPONSE

    metric_surface: SourceReferenceView
    matrix: SourceReferenceView
    ledger: SourceReferenceView


class StructuralMatrixAuthorityView(BaseModel):
    model_config = _FROZEN_RESPONSE

    kind: Literal["CANONICAL_PACKAGED_MATRIX"]
    source_head: str
    source_tree: str
    sources: StructuralMatrixAuthoritySourcesView


class StructuralMatrixMetricView(BaseModel):
    model_config = _FROZEN_RESPONSE

    metric_id: str
    definition: str
    unit: str
    draw_distribution: str
    exactness: str


class StructuralMatrixClaimBoundaryView(BaseModel):
    model_config = _FROZEN_RESPONSE

    historical_outcomes_used: bool
    historical_success_rate_claimed: bool
    ranking_score_claimed: bool
    global_optimum_claimed: bool
    cross_lottery_normalization: str


class StructuralMatrixValueView(BaseModel):
    model_config = _FROZEN_RESPONSE

    numerator: str
    denominator: str


class StructuralMatrixCellView(BaseModel):
    model_config = _FROZEN_RESPONSE

    row_id: str
    case_id: StructuralCaseId
    lottery: StructuralLottery
    method_id: StructuralMethodId
    ticket_count: int
    method_objective: str
    source_status: StructuralSourceStatus
    measurement_status: StructuralMeasurementStatus
    value: StructuralMatrixValueView | None
    portfolio_sha256: str | None
    unavailable_reason: str | None
    local_optimum_status: str | None

    @classmethod
    def from_cell(cls, cell: StructuralMatrixCell) -> StructuralMatrixCellView:
        return cls(
            row_id=cell.row_id,
            case_id=cell.case_id,
            lottery=cell.lottery,
            method_id=cell.method_id,
            ticket_count=int(cell.ticket_count),
            method_objective=cell.method_objective,
            source_status=cell.source_status,
            measurement_status=cell.measurement_status,
            value=(
                StructuralMatrixValueView(
                    numerator=cell.value.numerator, denominator=cell.value.denominator
                )
                if cell.value is not None
                else None
            ),
            portfolio_sha256=cell.portfolio_sha256,
            unavailable_reason=cell.unavailable_reason,
            local_optimum_status=cell.local_optimum_status,
        )


class StrategyMatrixStructuralResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    schema_id: str
    schema_version: str
    projection_sha256: str
    authority: StructuralMatrixAuthorityView
    scope: str
    supported_ticket_counts: list[int]
    metric: StructuralMatrixMetricView
    claim_boundary: StructuralMatrixClaimBoundaryView
    cells: list[StructuralMatrixCellView]

    @classmethod
    def from_dataset(
        cls, dataset: StrategyMatrixStructuralDataset
    ) -> StrategyMatrixStructuralResponse:
        return cls(
            schema_id=dataset.schema_id,
            schema_version=dataset.schema_version,
            projection_sha256=dataset.projection_sha256,
            authority=StructuralMatrixAuthorityView(
                kind="CANONICAL_PACKAGED_MATRIX",
                source_head=dataset.authority.source_head,
                source_tree=dataset.authority.source_tree,
                sources=StructuralMatrixAuthoritySourcesView(
                    metric_surface=SourceReferenceView(
                        repository_path=dataset.authority.sources.metric_surface.repository_path,
                        file_sha256=dataset.authority.sources.metric_surface.file_sha256,
                    ),
                    matrix=SourceReferenceView(
                        repository_path=dataset.authority.sources.matrix.repository_path,
                        file_sha256=dataset.authority.sources.matrix.file_sha256,
                    ),
                    ledger=SourceReferenceView(
                        repository_path=dataset.authority.sources.ledger.repository_path,
                        file_sha256=dataset.authority.sources.ledger.file_sha256,
                    ),
                ),
            ),
            scope=dataset.scope,
            supported_ticket_counts=list(dataset.supported_ticket_counts),
            metric=StructuralMatrixMetricView(
                metric_id=dataset.metric.metric_id,
                definition=dataset.metric.definition,
                unit=dataset.metric.unit,
                draw_distribution=dataset.metric.draw_distribution,
                exactness=dataset.metric.exactness,
            ),
            claim_boundary=StructuralMatrixClaimBoundaryView(
                historical_outcomes_used=dataset.claim_boundary.historical_outcomes_used,
                historical_success_rate_claimed=dataset.claim_boundary.historical_success_rate_claimed,
                ranking_score_claimed=dataset.claim_boundary.ranking_score_claimed,
                global_optimum_claimed=dataset.claim_boundary.global_optimum_claimed,
                cross_lottery_normalization=dataset.claim_boundary.cross_lottery_normalization,
            ),
            cells=[StructuralMatrixCellView.from_cell(cell) for cell in dataset.cells],
        )


def create_strategy_matrix_structural_router(
    reader_factory: StrategyMatrixStructuralReaderFactory,
) -> APIRouter:
    router = APIRouter(prefix=API_PREFIX, tags=["strategy-matrix-structural"])
    query_use_case = QueryStrategyMatrixStructural(reader_factory)

    @router.get(
        "/strategy-matrix/structural",
        response_model=StrategyMatrixStructuralResponse,
        responses={422: {"model": ApiValidationErrorResponse}, 503: {"model": ApiErrorResponse}},
        operation_id="queryStrategyMatrixStructural",
    )
    def query_strategy_matrix_structural_endpoint(
        request: Request,
        lottery: StructuralLottery | None = None,
        method_id: StructuralMethodId | None = None,
        ticket_count: StructuralTicketCount | None = None,
    ) -> StrategyMatrixStructuralResponse | JSONResponse:
        unexpected = sorted(set(request.query_params.keys()) - _ALLOWED_QUERY_FIELDS)
        if unexpected:
            return _invalid_query_error(unexpected)
        try:
            dataset = query_use_case.execute(
                StrategyMatrixStructuralQuery(
                    lottery=lottery,
                    method_id=method_id,
                    ticket_count=ticket_count,
                )
            )
        except StrategyMatrixStructuralProjectionError:
            return _unavailable_error()
        return StrategyMatrixStructuralResponse.from_dataset(dataset)

    return router


def _invalid_query_error(fields: list[str]) -> JSONResponse:
    model = ApiValidationErrorResponse(
        error_code="REQUEST_VALIDATION_FAILED",
        message="Request validation failed.",
        fields=[
            RequestValidationIssueView(location=f"query.{field}", type="extra_forbidden")
            for field in fields
        ],
    )
    return JSONResponse(status_code=422, content=model.model_dump(mode="json"))


def _unavailable_error() -> JSONResponse:
    error = ApiErrorResponse(
        error_code="STRUCTURAL_MATRIX_AUTHORITY_UNAVAILABLE",
        message="Canonical structural Matrix authority is unavailable.",
    )
    return JSONResponse(status_code=503, content=error.model_dump(mode="json"))
