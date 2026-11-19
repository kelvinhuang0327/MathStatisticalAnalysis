"""Read-only HTTP projection of the fixed Native B649 current pointer."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from lottolab.domain.research_live_forecast import (
    NATIVE_STREAM,
    NATIVE_STREAM_VERSION,
)
from lottolab.infrastructure.persistence.research_repository import (
    ResearchConflictError,
    SQLiteResearchRepository,
)
from lottolab.infrastructure.persistence.research_schema import resolve_research_data_paths
from lottolab.interfaces.api.draw_data import ApiValidationErrorResponse


class B649NativeForecastScope(BaseModel):
    """The immutable scope selected by the request and Native contract."""

    model_config = ConfigDict(extra="forbid")

    lottery_type: Literal["BIG_LOTTO"]
    target_draw_number: str
    target_draw_date: str
    forecast_stream_id: Literal["B649_NEXT_UNDRAWN_FORECAST"]
    forecast_stream_version: Literal["B649_FULL_OFFICIAL_ANY_PRIZE_R1"]


class B649NativeForecastRequestIdentity(BaseModel):
    """Stored request and current-version identity returned by the Reader."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    request_sha256: str
    version: int
    run_id: str
    payload_sha256: str
    generation_started_at: str
    generation_finished_at: str
    committed_at: str


class B649NativeForecastCurrentResponse(BaseModel):
    """The Native current scope, request identity, and original JSON payload."""

    model_config = ConfigDict(extra="forbid")

    scope: B649NativeForecastScope
    request_identity: B649NativeForecastRequestIdentity
    payload: dict[str, object]


class B649NativeForecastApiErrorResponse(BaseModel):
    """Sanitized error response without storage or exception details."""

    model_config = ConfigDict(extra="forbid")

    error_code: str
    message: str


def _default_repository_factory() -> SQLiteResearchRepository:
    return SQLiteResearchRepository(resolve_research_data_paths(), initialize=False)


def _error_response(status_code: int, error_code: str, message: str) -> JSONResponse:
    body = B649NativeForecastApiErrorResponse(
        error_code=error_code,
        message=message,
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


def create_b649_native_forecast_router(
    repository_factory: Callable[[], SQLiteResearchRepository] | None = None,
) -> APIRouter:
    """Create a read-only route pinned to the Native stream and stream version."""

    router = APIRouter(prefix="/api", tags=["b649-native-forecast"])
    resolve_repository = repository_factory or _default_repository_factory

    @router.get(
        "/b649/native-forecast/current",
        response_model=B649NativeForecastCurrentResponse,
        responses={
            404: {"model": B649NativeForecastApiErrorResponse},
            409: {"model": B649NativeForecastApiErrorResponse},
            422: {"model": B649NativeForecastApiErrorResponse | ApiValidationErrorResponse},
            503: {"model": B649NativeForecastApiErrorResponse},
        },
        operation_id="getB649NativeForecastCurrent",
    )
    def current(
        target_draw_number: Annotated[str, Query(pattern=r"^[0-9]{9}$")],
        target_draw_date: Annotated[str, Query(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")],
    ) -> B649NativeForecastCurrentResponse | JSONResponse:
        try:
            parsed_date = date.fromisoformat(target_draw_date)
        except ValueError:
            return _error_response(
                422,
                "B649_NATIVE_FORECAST_INVALID_SCOPE",
                "The requested Native forecast scope is invalid.",
            )
        if parsed_date.isoformat() != target_draw_date:
            return _error_response(
                422,
                "B649_NATIVE_FORECAST_INVALID_SCOPE",
                "The requested Native forecast scope is invalid.",
            )

        scope = (
            "BIG_LOTTO",
            target_draw_number,
            target_draw_date,
            NATIVE_STREAM,
            NATIVE_STREAM_VERSION,
        )
        try:
            result = resolve_repository().read_current_native(scope)
        except ResearchConflictError:
            return _error_response(
                409,
                "B649_NATIVE_CURRENT_INTEGRITY_CONFLICT",
                "The Native current forecast failed integrity validation.",
            )
        except Exception:
            return _error_response(
                503,
                "B649_NATIVE_CURRENT_UNAVAILABLE",
                "The Native current forecast is unavailable.",
            )
        if result is None:
            return _error_response(
                404,
                "B649_NATIVE_CURRENT_NOT_FOUND",
                "The requested Native current forecast was not found.",
            )

        try:
            payload_value = json.loads(result.payload_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return _error_response(
                409,
                "B649_NATIVE_CURRENT_INTEGRITY_CONFLICT",
                "The Native current forecast failed integrity validation.",
            )
        if not isinstance(payload_value, dict):
            return _error_response(
                409,
                "B649_NATIVE_CURRENT_INTEGRITY_CONFLICT",
                "The Native current forecast failed integrity validation.",
            )

        return B649NativeForecastCurrentResponse(
            scope=B649NativeForecastScope(
                lottery_type="BIG_LOTTO",
                target_draw_number=target_draw_number,
                target_draw_date=target_draw_date,
                forecast_stream_id=NATIVE_STREAM,
                forecast_stream_version=NATIVE_STREAM_VERSION,
            ),
            request_identity=B649NativeForecastRequestIdentity(
                request_id=result.request_id,
                request_sha256=result.request_sha256,
                version=result.version,
                run_id=result.run_id,
                payload_sha256=result.payload_sha256,
                generation_started_at=str(result.forecast.original["generation_started_at"]),
                generation_finished_at=str(result.forecast.original["generation_finished_at"]),
                committed_at=result.committed_at,
            ),
            payload=cast(dict[str, object], payload_value),
        )

    return router
