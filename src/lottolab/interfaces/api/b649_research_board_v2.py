"""Read-only HTTP API for the checksum-verified B649 research board V2."""

# FastAPI route functions are referenced through route registration decorators.
# pyright: reportUnusedFunction=false

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from lottolab.infrastructure.b649_research_board_v2_reader import (
    B649ResearchBoardV2DataError,
    B649ResearchBoardV2Dataset,
    B649ResearchBoardV2Reader,
    CsvRow,
)
from lottolab.interfaces.api.draw_data import (
    ApiValidationErrorResponse,
    RequestValidationIssueView,
)

JsonObject = dict[str, object]
PublicSourceIdentity = JsonObject | str
PublicSourceIdentityChain = list[JsonObject | str]
ResearchWindow = Literal["FULL", "RECENT_750", "RECENT_300", "RECENT_50"]


class B649ResearchBoardSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_task_id: str
    source_authority_commit: str
    observed_checkout_head: str
    source_manifest_sha256: str
    method_version_count: int
    inventory_count: int
    ranking_count: int
    metrics_availability_counts: dict[str, int]
    research_status_counts: dict[str, int]
    unavailable_count: int
    not_applicable_count: int
    comparable_group_count: int
    duplicate_output_groups: int
    windows: list[ResearchWindow]
    K_values: list[int]
    prize_metrics: list[str]
    cohorts: list[str]
    comparison_group_count: int


class B649ResearchBoardMethodView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method_id: str
    method_version: str
    method_family: str
    source_identity: PublicSourceIdentity
    task_id: str
    evaluation_cohort: str
    history_window: str
    K: int | None
    official_prize_metric: str
    successful_draws: int | None
    eligible_draws: int | None
    success_rate: str | None
    baseline_identity: str
    baseline_success_rate: str | None
    paired_difference: str | None
    research_status: str
    original_advance_decision: str
    artifact_locator: str
    artifact_sha256: str
    backtest_artifact_locator: str
    backtest_artifact_sha256: str
    metrics_availability: str
    metrics_unavailable_reason: str
    shared_output_identity: str
    method_type: str
    auxiliary_statistics_json: JsonObject
    arm_identity: str
    lottery_type: str
    window: str
    prize_metric: str
    wins: int | None
    baseline_rate: str | None
    delta_percentage_points: str | None
    research_class: str
    target_draw_set_identity: str
    comparison_rank: int | None
    comparison_group_id: str
    comparison_status: str
    original_board_metrics_availability: str
    original_board_metrics_unavailable_reason: str
    board_original_advance_decision: str
    source_identity_chain: PublicSourceIdentityChain
    source_shared_output_identities: list[str]
    source_lineage: list[dict[str, str]]
    source_record_id: str
    source_inventory_json: JsonObject
    owner_long_rank: str
    owner_middle_rank: str
    owner_short_rank: str
    owner_selected: str
    owner_reason: str


class B649ResearchBoardRankingView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method_id: str
    method_version: str
    arm_identity: str
    method_family: str
    task_id: str
    source_identity: PublicSourceIdentity
    source_identity_chain: PublicSourceIdentityChain
    lottery_type: str
    evaluation_cohort: str
    target_draw_set_identity: str
    window: ResearchWindow
    K: int
    prize_metric: str
    wins: int
    eligible_draws: int
    success_rate: str
    comparison_rank: int
    rank_basis_identity_count: int
    shared_output_identity: str
    source_shared_output_identities: list[str]
    baseline_identity: str
    baseline_rate: str | None
    delta_percentage_points: str | None
    research_status: str
    research_class: str
    original_advance_decision: str
    original_board_metrics_availability: str
    original_board_metrics_unavailable_reason: str
    board_original_advance_decision: str
    comparison_status: str
    comparison_notes: str
    artifact_locator: str
    artifact_sha256: str
    source_rank: int | None
    source_lineage: list[dict[str, str]]


class B649ResearchBoardMethodsPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[B649ResearchBoardMethodView]
    total: int
    limit: int
    offset: int


class B649ResearchBoardRankingsPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[B649ResearchBoardRankingView]
    total: int
    limit: int
    offset: int
    cohort: str
    K: int
    window: ResearchWindow
    prize_metric: str
    target_draw_set_identity: str | None
    eligible_draws: int | None
    comparison_group_count: int


class B649ResearchBoardApiErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_code: str
    message: str


def create_b649_research_board_v2_router(
    reader: B649ResearchBoardV2Reader | None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/b649-research-backtests", tags=["b649-research-backtests"])

    @router.get(
        "/summary",
        response_model=B649ResearchBoardSummaryResponse,
        responses={
            422: {"model": ApiValidationErrorResponse},
            503: {"model": B649ResearchBoardApiErrorResponse},
        },
        operation_id="getB649ResearchBacktestSummary",
    )
    def summary(request: Request) -> B649ResearchBoardSummaryResponse | JSONResponse:
        invalid = _reject_unknown_query(request, set())
        if invalid is not None:
            return invalid
        dataset = _read_dataset(reader)
        if isinstance(dataset, JSONResponse):
            return dataset
        return _summary_view(dataset)

    @router.get(
        "/methods",
        response_model=B649ResearchBoardMethodsPageResponse,
        responses={
            422: {"model": ApiValidationErrorResponse},
            503: {"model": B649ResearchBoardApiErrorResponse},
        },
        operation_id="listB649ResearchBacktestMethods",
    )
    def methods(
        request: Request,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
        method_id: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
        research_status: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    ) -> B649ResearchBoardMethodsPageResponse | JSONResponse:
        invalid = _reject_unknown_query(
            request, {"limit", "offset", "method_id", "research_status"}
        )
        if invalid is not None:
            return invalid
        dataset = _read_dataset(reader)
        if isinstance(dataset, JSONResponse):
            return dataset
        selected = [
            row
            for row in dataset.method_records
            if (method_id is None or row["method_id"] == method_id)
            and (research_status is None or row["research_status"] == research_status)
        ]
        page = selected[offset : offset + limit]
        return B649ResearchBoardMethodsPageResponse(
            items=[_method_view(row) for row in page],
            total=len(selected),
            limit=limit,
            offset=offset,
        )

    @router.get(
        "/rankings",
        response_model=B649ResearchBoardRankingsPageResponse,
        responses={
            422: {"model": ApiValidationErrorResponse},
            503: {"model": B649ResearchBoardApiErrorResponse},
        },
        operation_id="listB649ResearchBacktestRankings",
    )
    def rankings(
        request: Request,
        cohort: Annotated[str, Query(min_length=1, max_length=200)],
        k: Annotated[int, Query(alias="K", ge=1, le=20)],
        window: ResearchWindow,
        prize_metric: Annotated[Literal["OFFICIAL_ANY_PRIZE"], Query()],
        target_draw_set_identity: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
        eligible_draws: Annotated[int | None, Query(ge=1, le=100_000)] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
    ) -> B649ResearchBoardRankingsPageResponse | JSONResponse:
        invalid = _reject_unknown_query(
            request,
            {
                "cohort",
                "K",
                "window",
                "prize_metric",
                "target_draw_set_identity",
                "eligible_draws",
                "limit",
                "offset",
            },
        )
        if invalid is not None:
            return invalid
        dataset = _read_dataset(reader)
        if isinstance(dataset, JSONResponse):
            return dataset
        ranking_cohorts = {row["evaluation_cohort"] for row in dataset.ranking_records}
        if cohort not in ranking_cohorts:
            return _invalid_query_value("query.cohort")
        if k not in dataset.k_values:
            return _invalid_query_value("query.K")
        if (target_draw_set_identity is None) != (eligible_draws is None):
            return _invalid_query_value("query.target_draw_set_identity+query.eligible_draws")
        selected = [
            row
            for row in dataset.ranking_records
            if row["evaluation_cohort"] == cohort
            and row["K"] == str(k)
            and row["window"] == window
            and row["prize_metric"] == prize_metric
            and (
                target_draw_set_identity is None
                or row["target_draw_set_identity"] == target_draw_set_identity
            )
            and (eligible_draws is None or row["eligible_draws"] == str(eligible_draws))
        ]
        page = selected[offset : offset + limit]
        return B649ResearchBoardRankingsPageResponse(
            items=[_ranking_view(row) for row in page],
            total=len(selected),
            limit=limit,
            offset=offset,
            cohort=cohort,
            K=k,
            window=window,
            prize_metric=prize_metric,
            target_draw_set_identity=target_draw_set_identity,
            eligible_draws=eligible_draws,
            comparison_group_count=len(
                {
                    (
                        row["lottery_type"],
                        row["evaluation_cohort"],
                        row["target_draw_set_identity"],
                        row["window"],
                        row["K"],
                        row["prize_metric"],
                        row["eligible_draws"],
                    )
                    for row in selected
                }
            ),
        )

    return router


def _read_dataset(
    reader: B649ResearchBoardV2Reader | None,
) -> B649ResearchBoardV2Dataset | JSONResponse:
    if reader is None:
        return _unavailable(
            "B649_RESEARCH_BOARD_V2_NOT_CONFIGURED",
            "The B649 research board V2 root is not configured.",
        )
    try:
        return reader.read()
    except B649ResearchBoardV2DataError:
        return _unavailable(
            "B649_RESEARCH_BOARD_V2_UNAVAILABLE",
            "The configured B649 research board V2 is unavailable or failed verification.",
        )


def _summary_view(dataset: B649ResearchBoardV2Dataset) -> B649ResearchBoardSummaryResponse:
    return B649ResearchBoardSummaryResponse(
        source_task_id="NUMBER2_D_LMS_HUMAN_BOARD_V2_INTEGRATION_20261102_R1",
        source_authority_commit=dataset.source_authority_commit,
        observed_checkout_head=dataset.observed_checkout_head,
        source_manifest_sha256=dataset.source_manifest_sha256,
        method_version_count=dataset.method_version_count,
        inventory_count=dataset.inventory_count,
        ranking_count=dataset.ranking_count,
        metrics_availability_counts=dataset.metrics_availability_counts,
        research_status_counts=dataset.research_status_counts,
        unavailable_count=dataset.metrics_availability_counts["UNAVAILABLE"],
        not_applicable_count=dataset.metrics_availability_counts["NOT_APPLICABLE"],
        comparable_group_count=dataset.comparable_group_count,
        duplicate_output_groups=dataset.duplicate_output_groups,
        windows=[_research_window(window) for window in dataset.windows],
        K_values=list(dataset.k_values),
        prize_metrics=list(dataset.prize_metrics),
        cohorts=sorted({row["evaluation_cohort"] for row in dataset.inventory_records}),
        comparison_group_count=dataset.comparison_group_count,
    )


def _method_view(row: CsvRow) -> B649ResearchBoardMethodView:
    values = _convert_row(row, _METHOD_INT_FIELDS, _METHOD_JSON_FIELDS)
    values["artifact_locator"] = _public_locator(row["artifact_locator"])
    values["backtest_artifact_locator"] = _public_locator(row["backtest_artifact_locator"])
    return B649ResearchBoardMethodView.model_validate(values)


def _ranking_view(row: CsvRow) -> B649ResearchBoardRankingView:
    values = _convert_row(row, _RANKING_INT_FIELDS, _RANKING_JSON_FIELDS)
    values["artifact_locator"] = _public_locator(row["artifact_locator"])
    return B649ResearchBoardRankingView.model_validate(values)


_METHOD_INT_FIELDS = {
    "K",
    "successful_draws",
    "eligible_draws",
    "wins",
    "comparison_rank",
}
_RANKING_INT_FIELDS = {
    "K",
    "wins",
    "eligible_draws",
    "comparison_rank",
    "rank_basis_identity_count",
    "source_rank",
}
_OPTIONAL_METRIC_FIELDS = {
    "success_rate",
    "baseline_success_rate",
    "paired_difference",
    "baseline_rate",
    "delta_percentage_points",
}
_METHOD_JSON_FIELDS = {
    "source_identity",
    "source_identity_chain",
    "source_shared_output_identities",
    "source_lineage",
    "auxiliary_statistics_json",
    "source_inventory_json",
}
_RANKING_JSON_FIELDS = {
    "source_identity",
    "source_identity_chain",
    "source_shared_output_identities",
    "source_lineage",
}


def _convert_row(row: CsvRow, int_fields: set[str], json_fields: set[str]) -> dict[str, object]:
    converted: dict[str, object] = dict(row)
    for field in int_fields:
        raw = row[field]
        converted[field] = int(raw) if raw else None
    for field in _OPTIONAL_METRIC_FIELDS.intersection(row):
        if not row[field]:
            converted[field] = None
    for field in json_fields:
        converted[field] = _public_json(_parse_json_cell(row[field], field))
    return converted


def _parse_json_cell(raw: str, field: str) -> object:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        if field == "source_identity":
            return raw
        raise B649ResearchBoardV2DataError(f"the V2 JSON field {field} is invalid") from exc


def _research_window(value: str) -> ResearchWindow:
    allowed: tuple[ResearchWindow, ...] = ("FULL", "RECENT_750", "RECENT_300", "RECENT_50")
    if value not in allowed:
        raise B649ResearchBoardV2DataError("the V2 research window is invalid")
    return value


def _public_json(value: object) -> object:
    if isinstance(value, dict):
        typed_value = cast(dict[str, object], value)
        return {str(key): _public_json(item) for key, item in typed_value.items()}
    if isinstance(value, list):
        return [_public_json(item) for item in cast(list[object], value)]
    if isinstance(value, str):
        if value.startswith("/"):
            return _public_locator(value)
        stripped = value.lstrip()
        if stripped.startswith(("{", "[")):
            try:
                return _public_json(cast(object, json.loads(value)))
            except json.JSONDecodeError:
                return value
    return value


def _public_locator(value: str) -> str:
    if not value.startswith("/"):
        return value
    path_part, marker, fragment = value.partition("#")
    if "/MathStatisticalAnalysis/" in path_part:
        public_path = "PROJECT/" + path_part.split("/MathStatisticalAnalysis/", 1)[1]
    elif "/.task-data/" in path_part:
        public_path = "TASK_DATA/" + path_part.split("/.task-data/", 1)[1]
    else:
        public_path = "SOURCE/" + Path(path_part).name
    return public_path + (marker + fragment if marker else "")


def _reject_unknown_query(request: Request, allowed: set[str]) -> JSONResponse | None:
    unknown = sorted(set(request.query_params) - allowed)
    if not unknown:
        return None
    return _validation_error(
        [
            RequestValidationIssueView(location=f"query.{key}", type="extra_forbidden")
            for key in unknown
        ]
    )


def _invalid_query_value(location: str) -> JSONResponse:
    return _validation_error([RequestValidationIssueView(location=location, type="value_error")])


def _validation_error(fields: list[RequestValidationIssueView]) -> JSONResponse:
    response = ApiValidationErrorResponse(
        error_code="REQUEST_VALIDATION_FAILED",
        message="Request validation failed.",
        fields=fields,
    )
    return JSONResponse(status_code=422, content=response.model_dump(mode="json"))


def _unavailable(error_code: str, message: str) -> JSONResponse:
    response = B649ResearchBoardApiErrorResponse(error_code=error_code, message=message)
    return JSONResponse(status_code=503, content=response.model_dump(mode="json"))
