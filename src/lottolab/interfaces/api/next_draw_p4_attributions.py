"""GET-only API for persisted Next-Draw P4 outcome attributions."""

# pyright: reportUnusedFunction=false
# (route handlers are registered by FastAPI decorators, not called by name)

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Path, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from lottolab.application.ports import NextDrawP4AttributionReaderFactory
from lottolab.application.use_cases.query_next_draw_p4_attribution import (
    NextDrawP4AttributionNotFoundError,
    QueryNextDrawP4Attribution,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.next_draw_outcome_attribution import (
    NextDrawOutcomeAttribution,
    NextDrawOutcomeAttributionPage,
)
from lottolab.interfaces.api.draw_data import ApiErrorResponse
from lottolab.interfaces.api.strategy_catalog import API_PREFIX

TargetDrawNumber = Annotated[str, Path(pattern=r"^[0-9]{1,32}$")]
HistoryPage = Annotated[int, Query(ge=1)]
HistoryPageSize = Annotated[int, Query(ge=1, le=100)]

_FROZEN_RESPONSE = ConfigDict(frozen=True)


class NextDrawP4TargetView(BaseModel):
    model_config = _FROZEN_RESPONSE

    lottery_type: str
    draw_number: str
    draw_date: str


class NextDrawP4OutcomeProvenanceView(BaseModel):
    model_config = _FROZEN_RESPONSE

    completed_at: str
    ingestion_run_id: str
    operation_type: str
    parser_version: str
    source_filename: str
    source_name: str | None
    source_reference: str | None
    source_sha256: str
    status: str


class NextDrawP4OfficialOutcomeView(BaseModel):
    model_config = _FROZEN_RESPONSE

    draw_date: str
    draw_number: str
    lottery_type: str
    normalized_record_hash: str
    outcome_sha256: str
    provenance: NextDrawP4OutcomeProvenanceView
    winning_main_numbers: list[int]
    winning_special_number: int


class NextDrawP4TicketAttributionView(BaseModel):
    model_config = _FROZEN_RESPONSE

    is_winner: bool
    main_number_hit_count: int
    predicted_main_numbers: list[int]
    prize_rule_provenance: str
    prize_rule_version: str
    prize_tier: str | None
    special_number_hit: bool
    ticket_position: int


class NextDrawP4StrategyAttributionView(BaseModel):
    model_config = _FROZEN_RESPONSE

    detail: str
    rank: int
    seal_status: str
    strategy_id: str
    strategy_name: str
    ticket_attributions: list[NextDrawP4TicketAttributionView]


class NextDrawP4BucketAttributionView(BaseModel):
    model_config = _FROZEN_RESPONSE

    availability: str
    native_ticket_count: int
    strategies: list[NextDrawP4StrategyAttributionView]
    total_candidate_count: int


class NextDrawP4AttributionResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    attribution_sha256: str
    buckets: list[NextDrawP4BucketAttributionView]
    official_outcome: NextDrawP4OfficialOutcomeView
    schema_version: str
    scoring_contract_id: str
    scoring_contract_sha256: str
    seal_digest: str
    seal_file_sha256: str
    seal_schema_version: str
    seal_source_head: str | None
    seal_source_tree: str | None
    target: NextDrawP4TargetView

    @classmethod
    def from_artifact(
        cls, artifact: NextDrawOutcomeAttribution
    ) -> NextDrawP4AttributionResponse:
        return cls.model_validate(artifact.canonical_dict())


class NextDrawP4AttributionHistoryResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    records: list[NextDrawP4AttributionResponse]
    page: int
    page_size: int
    total_count: int
    total_pages: int

    @classmethod
    def from_page(
        cls, result: NextDrawOutcomeAttributionPage
    ) -> NextDrawP4AttributionHistoryResponse:
        return cls(
            records=[NextDrawP4AttributionResponse.from_artifact(item) for item in result.records],
            page=result.page,
            page_size=result.page_size,
            total_count=result.total_count,
            total_pages=result.total_pages,
        )


def create_next_draw_p4_attributions_router(
    reader_factory: NextDrawP4AttributionReaderFactory | None,
) -> APIRouter:
    """Expose stored P4 artifacts without initialization, scoring, or writes."""

    router = APIRouter(prefix=API_PREFIX, tags=["next-draw-p4-attributions"])
    query = QueryNextDrawP4Attribution(reader_factory) if reader_factory is not None else None
    error_responses: dict[int | str, dict[str, Any]] = {
        404: {"model": ApiErrorResponse},
        422: {"model": ApiErrorResponse},
        503: {"model": ApiErrorResponse},
    }

    @router.get(
        "/next-draw-p4-attributions/{lottery_type}/{target_draw_number}/{target_draw_date}",
        response_model=NextDrawP4AttributionResponse,
        responses=error_responses,
        operation_id="getNextDrawP4Attribution",
    )
    def get_next_draw_p4_attribution(
        lottery_type: LotteryType,
        target_draw_number: TargetDrawNumber,
        target_draw_date: date,
    ) -> NextDrawP4AttributionResponse | JSONResponse:
        if query is None:
            return _not_configured_error()
        try:
            artifact = query.get_exact(
                lottery_type=lottery_type,
                target_draw_number=target_draw_number,
                target_draw_date=target_draw_date,
            )
        except NextDrawP4AttributionNotFoundError:
            return _not_found_error()
        except ValueError:
            return _unsupported_lottery_error()
        except Exception:
            return _unavailable_error()
        return NextDrawP4AttributionResponse.from_artifact(artifact)

    @router.get(
        "/next-draw-p4-attributions",
        response_model=NextDrawP4AttributionHistoryResponse,
        responses=error_responses,
        operation_id="listNextDrawP4Attributions",
    )
    def list_next_draw_p4_attributions(
        lottery_type: LotteryType | None = None,
        page: HistoryPage = 1,
        page_size: HistoryPageSize = 20,
    ) -> NextDrawP4AttributionHistoryResponse | JSONResponse:
        if query is None:
            return _not_configured_error()
        try:
            result = query.history(
                lottery_type=lottery_type,
                page=page,
                page_size=page_size,
            )
        except ValueError:
            return _unsupported_lottery_error()
        except Exception:
            return _unavailable_error()
        return NextDrawP4AttributionHistoryResponse.from_page(result)

    return router


def _not_configured_error() -> JSONResponse:
    return _error_response(
        503,
        "NEXT_DRAW_P4_QUERY_NOT_CONFIGURED",
        "Next-Draw P4 attribution query is not configured.",
    )


def _not_found_error() -> JSONResponse:
    return _error_response(
        404,
        "NEXT_DRAW_P4_ATTRIBUTION_NOT_FOUND",
        "Next-Draw P4 attribution was not found.",
    )


def _unsupported_lottery_error() -> JSONResponse:
    return _error_response(
        422,
        "NEXT_DRAW_P4_LOTTERY_UNSUPPORTED",
        "Next-Draw P4 attribution supports BIG_LOTTO only.",
    )


def _unavailable_error() -> JSONResponse:
    return _error_response(
        503,
        "NEXT_DRAW_P4_QUERY_UNAVAILABLE",
        "Next-Draw P4 attribution storage is unavailable.",
    )


def _error_response(status_code: int, error_code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ApiErrorResponse(error_code=error_code, message=message).model_dump(mode="json"),
    )


__all__ = [
    "NextDrawP4AttributionHistoryResponse",
    "NextDrawP4AttributionResponse",
    "create_next_draw_p4_attributions_router",
]
