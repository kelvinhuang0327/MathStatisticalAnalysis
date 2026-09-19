"""Read-only HTTP projection for the scheduler-owned B649 forecast."""

# pyright: reportUnusedFunction=false

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Final, Literal, NoReturn, cast

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from lottolab.application.b649_sealed_geometry_portfolio import (
    SEALED_GEOMETRY_METHOD_ID,
    SEALED_GEOMETRY_METHOD_VERSION,
    SEALED_GEOMETRY_PORTFOLIOS,
)

HEALTH_PATH_ENV: Final = "LOTTOLAB_B649_GOALC_HEALTH_PATH"
HEALTH_SCHEMA_VERSION: Final = "b649-goalc-local-scheduler-health-v1"
FORECAST_SCHEMA_VERSION: Final = "b649-canonical-forecast-v1"
FORECAST_METHOD_ID: Final = "B649_11_STREAM_EQUAL_WEIGHT_NUMBER_CONSENSUS"
FORECAST_METHOD_VERSION: Final = "1.0.0"
PORTFOLIO_SCHEMA_VERSION: Final = "b649-operational-portfolio-v2"
PORTFOLIO_METHOD_ID: Final = SEALED_GEOMETRY_METHOD_ID
PORTFOLIO_METHOD_VERSION: Final = SEALED_GEOMETRY_METHOD_VERSION
EXPECTED_STREAM_COUNT: Final = 11
_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)
_DRAW_NUMBER = re.compile(r"[0-9]+", flags=re.ASCII)


class B649CanonicalForecastTicket(BaseModel):
    """One scheduler-selected operational ticket."""

    model_config = ConfigDict(extra="forbid")

    ticket_position: int
    predicted_numbers: list[int]


class B649CanonicalForecastTarget(BaseModel):
    """The scheduler-owned target currently exposed by the API."""

    model_config = ConfigDict(extra="forbid")

    draw_number: str
    draw_date: str
    scheduled_at: str


class B649CanonicalForecastCurrentResponse(BaseModel):
    """The complete read-only current B649 forecast projection."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["AVAILABLE"]
    authority: Literal["SCHEDULER_ARTIFACT"]
    current_target: B649CanonicalForecastTarget
    consensus_numbers: list[int]
    source_stream_count: int
    k5_tickets: list[B649CanonicalForecastTicket]
    k10_tickets: list[B649CanonicalForecastTicket]
    k20_tickets: list[B649CanonicalForecastTicket]
    forecast_actual_sha256: str
    forecast_method_id: str
    forecast_method_version: str
    portfolio_actual_sha256: str
    portfolio_method_id: str
    portfolio_method_version: str


class B649CanonicalForecastApiErrorResponse(BaseModel):
    """Sanitized error returned when scheduler authority is unavailable."""

    model_config = ConfigDict(extra="forbid")

    error_code: str
    message: str


class _UnavailableError(RuntimeError):
    """The scheduler health/artifact tuple cannot be served safely."""


@dataclass(frozen=True, slots=True)
class _Target:
    draw_number: str
    draw_date: str
    scheduled_at: str
    scheduled_instant: datetime


@dataclass(frozen=True, slots=True)
class _HealthAuthority:
    path: Path
    raw: bytes
    target: _Target
    forecast_path: Path
    forecast_sha256: str
    portfolio_path: Path


def create_b649_canonical_forecast_router() -> APIRouter:
    """Create the fixed-path read-only scheduler-authority route."""

    router = APIRouter(prefix="/api", tags=["b649-canonical-forecast"])

    @router.get(
        "/b649/canonical-forecast/current",
        response_model=B649CanonicalForecastCurrentResponse,
        responses={503: {"model": B649CanonicalForecastApiErrorResponse}},
        operation_id="getB649CanonicalForecastCurrent",
    )
    def current() -> B649CanonicalForecastCurrentResponse | JSONResponse:
        try:
            return _read_current()
        except Exception:
            return _unavailable_response()

    return router


def _read_current() -> B649CanonicalForecastCurrentResponse:
    health_path = _configured_health_path()
    health_raw = _read_regular_bytes(health_path)
    health = _parse_object(health_raw)
    authority = _health_authority(health_path, health_raw, health)

    forecast_raw = _read_regular_bytes(authority.forecast_path)
    if hashlib.sha256(forecast_raw).hexdigest() != authority.forecast_sha256:
        raise _UnavailableError("forecast authority digest differs from scheduler health")
    forecast = _parse_object(forecast_raw)

    portfolio_raw = _read_regular_bytes(authority.portfolio_path)
    portfolio = _parse_object(portfolio_raw)
    portfolio_sha256 = hashlib.sha256(portfolio_raw).hexdigest()

    response = _build_response(
        authority,
        forecast,
        portfolio,
        portfolio_sha256=portfolio_sha256,
    )

    if _read_regular_bytes(authority.path) != authority.raw:
        raise _UnavailableError("scheduler health changed during request")
    return response


def _configured_health_path() -> Path:
    configured = os.environ.get(HEALTH_PATH_ENV)
    if configured is None or configured == "":
        raise _UnavailableError("scheduler health is not configured")
    path = Path(configured)
    if not path.is_absolute():
        raise _UnavailableError("scheduler health path is not absolute")
    return path


def _health_authority(
    health_path: Path,
    health_raw: bytes,
    health: Mapping[str, object],
) -> _HealthAuthority:
    if health.get("schema_version") != HEALTH_SCHEMA_VERSION:
        raise _UnavailableError("scheduler health schema is invalid")
    current_status = health.get("current_status")
    if current_status is not None and current_status != "PREDRAW_READY":
        raise _UnavailableError("scheduler health is not current")

    target = _target(health.get("current_target"), "current target")
    forecast_health = _mapping(health.get("forecast_materialization"), "forecast health")
    portfolio_health = _mapping(
        health.get("portfolio_materialization"), "portfolio health"
    )

    if forecast_health.get("status") != "COMPLETE":
        raise _UnavailableError("forecast authority is unavailable")
    _require_method(
        forecast_health,
        "method_id",
        "method_version",
        FORECAST_METHOD_ID,
        FORECAST_METHOD_VERSION,
        "forecast health",
    )
    forecast_path = _absolute_path(forecast_health.get("artifact_path"), "forecast authority")
    forecast_sha256 = _digest(forecast_health.get("artifact_sha256"), "forecast health")
    _optional_target_draw(forecast_health.get("target_draw"), target, "forecast health")

    portfolio_status = portfolio_health.get("status")
    if portfolio_status not in {"COMPLETE", "CREATED", "ALREADY_PRESENT"}:
        raise _UnavailableError("portfolio authority is unavailable")
    _require_method(
        portfolio_health,
        "method_id",
        "method_version",
        PORTFOLIO_METHOD_ID,
        PORTFOLIO_METHOD_VERSION,
        "portfolio health",
    )
    portfolio_path = _absolute_path(
        portfolio_health.get("portfolio_authority_locator"),
        "portfolio authority",
    )
    _optional_target_draw(portfolio_health.get("target_draw"), target, "portfolio health")
    return _HealthAuthority(
        path=health_path,
        raw=health_raw,
        target=target,
        forecast_path=forecast_path,
        forecast_sha256=forecast_sha256,
        portfolio_path=portfolio_path,
    )


def _build_response(
    authority: _HealthAuthority,
    forecast: Mapping[str, object],
    portfolio: Mapping[str, object],
    *,
    portfolio_sha256: str,
) -> B649CanonicalForecastCurrentResponse:
    _validate_forecast(authority.target, forecast)
    _validate_portfolio(authority.target, portfolio)
    forecast_method_id = _exact_method_value(
        forecast, "aggregation_method_id", FORECAST_METHOD_ID, "forecast artifact"
    )
    forecast_method_version = _exact_method_value(
        forecast,
        "aggregation_method_version",
        FORECAST_METHOD_VERSION,
        "forecast artifact",
    )
    portfolio_method_id = _exact_method_value(
        portfolio, "portfolio_method_id", PORTFOLIO_METHOD_ID, "portfolio artifact"
    )
    portfolio_method_version = _exact_method_value(
        portfolio,
        "portfolio_method_version",
        PORTFOLIO_METHOD_VERSION,
        "portfolio artifact",
    )
    return B649CanonicalForecastCurrentResponse(
        status="AVAILABLE",
        authority="SCHEDULER_ARTIFACT",
        current_target=B649CanonicalForecastTarget(
            draw_number=authority.target.draw_number,
            draw_date=authority.target.draw_date,
            scheduled_at=authority.target.scheduled_at,
        ),
        consensus_numbers=_forecast_numbers(forecast),
        source_stream_count=_stream_count(forecast),
        k5_tickets=_tickets(portfolio.get("k5"), 5, "portfolio k5"),
        k10_tickets=_tickets(portfolio.get("k10"), 10, "portfolio k10"),
        k20_tickets=_tickets(portfolio.get("k20"), 20, "portfolio k20"),
        forecast_actual_sha256=authority.forecast_sha256,
        forecast_method_id=forecast_method_id,
        forecast_method_version=forecast_method_version,
        portfolio_actual_sha256=portfolio_sha256,
        portfolio_method_id=portfolio_method_id,
        portfolio_method_version=portfolio_method_version,
    )


def _validate_forecast(target: _Target, forecast: Mapping[str, object]) -> None:
    if forecast.get("schema_version") != FORECAST_SCHEMA_VERSION:
        raise _UnavailableError("forecast schema is invalid")
    if forecast.get("lottery_type") not in {None, "BIG_LOTTO"}:
        raise _UnavailableError("forecast lottery type is invalid")
    _require_method(
        forecast,
        "aggregation_method_id",
        "aggregation_method_version",
        FORECAST_METHOD_ID,
        FORECAST_METHOD_VERSION,
        "forecast artifact",
    )
    _target_matches(
        forecast.get("target_draw"),
        forecast.get("scheduled_at"),
        target,
        "forecast artifact",
    )
    stream_count = _stream_count(forecast)
    stream_inputs_value = forecast.get("stream_inputs")
    if not isinstance(stream_inputs_value, list):
        raise _UnavailableError("forecast stream inventory is invalid")
    stream_inputs = cast(list[object], stream_inputs_value)
    if len(stream_inputs) != stream_count:
        raise _UnavailableError("forecast stream inventory is invalid")
    _forecast_numbers(forecast)


def _validate_portfolio(target: _Target, portfolio: Mapping[str, object]) -> None:
    if portfolio.get("schema_version") != PORTFOLIO_SCHEMA_VERSION:
        raise _UnavailableError("portfolio schema is invalid")
    if portfolio.get("lottery_type") not in {None, "BIG_LOTTO"}:
        raise _UnavailableError("portfolio lottery type is invalid")
    _require_method(
        portfolio,
        "portfolio_method_id",
        "portfolio_method_version",
        PORTFOLIO_METHOD_ID,
        PORTFOLIO_METHOD_VERSION,
        "portfolio artifact",
    )
    _target_matches(
        portfolio.get("target_draw"),
        portfolio.get("scheduled_at"),
        target,
        "portfolio artifact",
    )
    for key in ("portfolio_status", "k5_status", "k10_status", "k20_status"):
        if portfolio.get(key) != "COMPLETE":
            raise _UnavailableError("portfolio bucket is not complete")
    # Buckets are independently optimal per K (not nested); serve them only if
    # they are exactly the sealed geometry the method id promises.
    for size in (5, 10, 20):
        served = _tickets(portfolio.get(f"k{size}"), size, f"portfolio k{size}")
        sealed = SEALED_GEOMETRY_PORTFOLIOS[size].tickets
        if [tuple(ticket.predicted_numbers) for ticket in served] != list(sealed):
            raise _UnavailableError(f"portfolio k{size} is not the sealed geometry")


def _target(value: object, label: str) -> _Target:
    mapping = _mapping(value, label)
    if mapping.get("lottery_type") not in {None, "BIG_LOTTO"}:
        raise _UnavailableError(f"{label} lottery type is invalid")
    draw_number = _text(mapping.get("draw_number"), label)
    if _DRAW_NUMBER.fullmatch(draw_number) is None:
        raise _UnavailableError(f"{label} draw number is invalid")
    draw_date = _text(mapping.get("draw_date"), label)
    try:
        date.fromisoformat(draw_date)
    except ValueError as exc:
        raise _UnavailableError(f"{label} date is invalid") from exc
    scheduled_at = _text(mapping.get("scheduled_at"), label)
    return _Target(
        draw_number=draw_number,
        draw_date=draw_date,
        scheduled_at=scheduled_at,
        scheduled_instant=_instant(scheduled_at, label),
    )


def _target_matches(
    target_draw_value: object,
    scheduled_value: object,
    expected: _Target,
    label: str,
) -> None:
    target = _mapping(target_draw_value, f"{label} target")
    if _text(target.get("draw_number"), label) != expected.draw_number:
        raise _UnavailableError(f"{label} target differs")
    if _text(target.get("draw_date"), label) != expected.draw_date:
        raise _UnavailableError(f"{label} target differs")
    if _instant(scheduled_value, label) != expected.scheduled_instant:
        raise _UnavailableError(f"{label} schedule differs")


def _optional_target_draw(value: object, expected: _Target, label: str) -> None:
    if value is None:
        return
    if isinstance(value, Mapping):
        mapping = cast(Mapping[str, object], value)
        observed = _text(
            mapping.get("draw_number"),
            label,
        )
        if mapping.get("draw_date") is not None and _text(
            mapping.get("draw_date"), label
        ) != expected.draw_date:
            raise _UnavailableError(f"{label} target differs")
    else:
        observed = _text(value, label)
    if observed != expected.draw_number:
        raise _UnavailableError(f"{label} target differs")


def _forecast_numbers(forecast: Mapping[str, object]) -> list[int]:
    rows_value = forecast.get("final_recommended_output")
    if not isinstance(rows_value, list):
        raise _UnavailableError("forecast consensus is invalid")
    rows = cast(list[object], rows_value)
    if len(rows) != 1:
        raise _UnavailableError("forecast consensus is invalid")
    row = _mapping(rows[0], "forecast consensus")
    if set(row) != {"ticket_position", "predicted_numbers"} or row.get("ticket_position") != 1:
        raise _UnavailableError("forecast consensus is invalid")
    numbers = _numbers(row.get("predicted_numbers"), "forecast consensus")
    if len(numbers) != 6:
        raise _UnavailableError("forecast consensus is not six numbers")
    return numbers


def _stream_count(forecast: Mapping[str, object]) -> int:
    value = forecast.get("stream_count")
    if type(value) is not int or value != EXPECTED_STREAM_COUNT:
        raise _UnavailableError("forecast stream count is invalid")
    return value


def _tickets(value: object, expected_count: int, label: str) -> list[B649CanonicalForecastTicket]:
    if not isinstance(value, list):
        raise _UnavailableError(f"{label} ticket count is invalid")
    rows = cast(list[object], value)
    if len(rows) != expected_count:
        raise _UnavailableError(f"{label} ticket count is invalid")
    tickets: list[B649CanonicalForecastTicket] = []
    for position, item in enumerate(rows, start=1):
        row = _mapping(item, label)
        if row.get("ticket_position") != position:
            raise _UnavailableError(f"{label} ticket position is invalid")
        numbers = _numbers(row.get("predicted_numbers"), label)
        if len(numbers) != 6:
            raise _UnavailableError(f"{label} ticket is invalid")
        tickets.append(
            B649CanonicalForecastTicket(
                ticket_position=position,
                predicted_numbers=numbers,
            )
        )
    return tickets


def _numbers(value: object, label: str) -> list[int]:
    if not isinstance(value, list):
        raise _UnavailableError(f"{label} numbers are invalid")
    numbers = cast(list[object], value)
    if (
        any(type(number) is not int or not 1 <= number <= 49 for number in numbers)
        or len(set(numbers)) != len(numbers)
    ):
        raise _UnavailableError(f"{label} numbers are invalid")
    return cast(list[int], numbers)


def _require_method(
    value: Mapping[str, object],
    id_key: str,
    version_key: str,
    expected_id: str,
    expected_version: str,
    label: str,
) -> None:
    if value.get(id_key) != expected_id or value.get(version_key) != expected_version:
        raise _UnavailableError(f"{label} method provenance is invalid")


def _exact_method_value(
    value: Mapping[str, object], key: str, expected: str, label: str
) -> str:
    method = value.get(key)
    if method != expected:
        raise _UnavailableError(f"{label} method provenance is invalid")
    return cast(str, method)


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise _UnavailableError(f"{label} is not an object")
    return cast(Mapping[str, object], value)


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _UnavailableError(f"{label} text is invalid")
    return value


def _absolute_path(value: object, label: str) -> Path:
    path = Path(_text(value, label))
    if not path.is_absolute():
        raise _UnavailableError(f"{label} path is invalid")
    return path


def _digest(value: object, label: str) -> str:
    digest = _text(value, label)
    if _SHA256.fullmatch(digest) is None:
        raise _UnavailableError(f"{label} digest is invalid")
    return digest


def _instant(value: object, label: str) -> datetime:
    timestamp = _text(value, label)
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _UnavailableError(f"{label} timestamp is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise _UnavailableError(f"{label} timestamp is not timezone-aware")
    return parsed.astimezone(UTC)


def _read_regular_bytes(path: Path) -> bytes:
    try:
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise _UnavailableError("authority is not a regular file")
        return path.read_bytes()
    except _UnavailableError:
        raise
    except OSError as exc:
        raise _UnavailableError("authority could not be read") from exc


def _parse_object(raw: bytes) -> dict[str, object]:
    try:
        parsed = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_object_pairs,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise _UnavailableError("authority JSON is invalid") from exc
    if not isinstance(parsed, dict):
        raise _UnavailableError("authority JSON is not an object")
    return cast(dict[str, object], parsed)


def _object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_constant(value: str) -> NoReturn:
    raise ValueError(f"non-finite JSON constant is not allowed: {value}")


def _unavailable_response() -> JSONResponse:
    response = B649CanonicalForecastApiErrorResponse(
        error_code="B649_CANONICAL_FORECAST_UNAVAILABLE",
        message="The scheduler-owned B649 canonical forecast is unavailable.",
    )
    return JSONResponse(status_code=503, content=response.model_dump(mode="json"))


__all__ = [
    "HEALTH_PATH_ENV",
    "B649CanonicalForecastApiErrorResponse",
    "B649CanonicalForecastCurrentResponse",
    "B649CanonicalForecastTarget",
    "B649CanonicalForecastTicket",
    "create_b649_canonical_forecast_router",
]
