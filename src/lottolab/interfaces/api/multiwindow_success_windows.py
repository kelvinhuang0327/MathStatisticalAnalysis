"""FastAPI adapter for the count-independent T539/P638 success-window evidence."""

# pyright: reportUnusedFunction=false

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from lottolab.application.multiwindow_success_windows import (
    ExactRational,
    MultiWindowAnalysis,
    MultiWindowSuccessQueryError,
    NullContract,
    StabilityDelta,
    TierCount,
    WindowDefinition,
    WindowResult,
    analyze_multiwindow_success_windows,
)
from lottolab.application.ports import MultiWindowSuccessSourceReaderFactory
from lottolab.interfaces.api.draw_data import ApiErrorResponse, ApiValidationErrorResponse
from lottolab.interfaces.api.strategy_catalog import API_PREFIX

_FROZEN_RESPONSE = ConfigDict(frozen=True)
CanonicalSignedInteger = Annotated[
    str,
    Field(pattern=r"^-?(?:0|[1-9][0-9]*)$"),
]
CanonicalPositiveInteger = Annotated[
    str,
    Field(pattern=r"^[1-9][0-9]*$"),
]
RunId = Annotated[str, Path(min_length=1, max_length=128)]


class ExactRationalView(BaseModel):
    model_config = _FROZEN_RESPONSE

    numerator: CanonicalSignedInteger
    denominator: CanonicalPositiveInteger
    decimal_18: str

    @classmethod
    def from_value(cls, value: ExactRational) -> ExactRationalView:
        canonical = value.canonical_dict()
        return cls(
            numerator=str(canonical["numerator"]),
            denominator=str(canonical["denominator"]),
            decimal_18=str(canonical["decimal_18"]),
        )


class WindowDefinitionView(BaseModel):
    model_config = _FROZEN_RESPONSE

    window_kind: str
    requested_target_count: int | None
    selection: str
    window_role: str

    @classmethod
    def from_value(cls, value: WindowDefinition) -> WindowDefinitionView:
        return cls(
            window_kind=value.window_kind.value,
            requested_target_count=value.requested_target_count,
            selection=value.selection,
            window_role=value.window_role,
        )


class TierCountView(BaseModel):
    model_config = _FROZEN_RESPONSE

    tier_id: str
    tier_order: int
    count: int

    @classmethod
    def from_value(cls, value: TierCount) -> TierCountView:
        return cls(tier_id=value.tier_id, tier_order=value.tier_order, count=value.count)


class NullContractView(BaseModel):
    model_config = _FROZEN_RESPONSE

    lottery_type: str
    game_spec: str
    sampling_policy: str
    official_evaluator: str
    prize_rule_version: str
    prize_rule_source_sha256: str
    legal_ticket_count: int
    any_prize_ticket_count: int
    single_ticket_any_prize_probability: ExactRationalView
    portfolio_formula: str
    hit_state_weights: list[dict[str, object]]

    @classmethod
    def from_value(cls, value: NullContract) -> NullContractView:
        return cls(
            lottery_type=value.lottery_type,
            game_spec=value.game_spec,
            sampling_policy=value.sampling_policy,
            official_evaluator=value.official_evaluator,
            prize_rule_version=value.prize_rule_version,
            prize_rule_source_sha256=value.prize_rule_source_sha256,
            legal_ticket_count=value.legal_ticket_count,
            any_prize_ticket_count=value.any_prize_ticket_count,
            single_ticket_any_prize_probability=ExactRationalView.from_value(
                value.single_ticket_any_prize_probability
            ),
            portfolio_formula=value.portfolio_formula,
            hit_state_weights=[dict(item) for item in value.hit_state_weights],
        )


class MultiWindowRowView(BaseModel):
    model_config = _FROZEN_RESPONSE

    lottery_type: str
    run_id: str
    strategy_id: str
    strategy_version: str
    native_ticket_count: int
    window_kind: str
    window_role: str
    status: str
    source_target_count: int
    requested_target_count: int | None
    actual_target_count: int
    first_target_id: str | None
    first_target_date: str | None
    last_target_id: str | None
    last_target_date: str | None
    observed_winning_target_count: int
    observed_winning_target_rate: ExactRationalView | None
    observed_ticket_count: int
    observed_winning_ticket_count: int
    observed_ticket_winning_rate: ExactRationalView | None
    prize_tier_vector: list[TierCountView]
    highest_prize_tier: str | None
    null_single_ticket_probability: ExactRationalView
    null_portfolio_probability: ExactRationalView
    expected_null_target_successes: ExactRationalView | None
    observed_minus_null_rate: ExactRationalView | None
    lift_vs_null: ExactRationalView | None
    raw_p_value: ExactRationalView | None
    by_adjusted_p_value: ExactRationalView | None
    evidence_status: str

    @classmethod
    def from_value(cls, value: WindowResult) -> MultiWindowRowView:
        return cls(
            lottery_type=value.lottery_type,
            run_id=value.run_id,
            strategy_id=value.strategy_id,
            strategy_version=value.strategy_version,
            native_ticket_count=value.native_ticket_count,
            window_kind=value.window_kind.value,
            window_role=value.window_role,
            status=value.status.value,
            source_target_count=value.source_target_count,
            requested_target_count=value.requested_target_count,
            actual_target_count=value.actual_target_count,
            first_target_id=value.first_target_id,
            first_target_date=value.first_target_date,
            last_target_id=value.last_target_id,
            last_target_date=value.last_target_date,
            observed_winning_target_count=value.observed_winning_target_count,
            observed_winning_target_rate=_optional_view(value.observed_winning_target_rate),
            observed_ticket_count=value.observed_ticket_count,
            observed_winning_ticket_count=value.observed_winning_ticket_count,
            observed_ticket_winning_rate=_optional_view(value.observed_ticket_winning_rate),
            prize_tier_vector=[TierCountView.from_value(item) for item in value.prize_tier_vector],
            highest_prize_tier=value.highest_prize_tier,
            null_single_ticket_probability=ExactRationalView.from_value(
                value.null_single_ticket_probability
            ),
            null_portfolio_probability=ExactRationalView.from_value(
                value.null_portfolio_probability
            ),
            expected_null_target_successes=_optional_view(value.expected_null_target_successes),
            observed_minus_null_rate=_optional_view(value.observed_minus_null_rate),
            lift_vs_null=_optional_view(value.lift_vs_null),
            raw_p_value=_optional_view(value.raw_p_value),
            by_adjusted_p_value=_optional_view(value.by_adjusted_p_value),
            evidence_status=value.evidence_status,
        )


class StabilityDeltaView(BaseModel):
    model_config = _FROZEN_RESPONSE

    strategy_id: str
    strategy_version: str
    from_window: str
    to_window: str
    delta_observed_winning_target_rate: ExactRationalView | None
    relation: str

    @classmethod
    def from_value(cls, value: StabilityDelta) -> StabilityDeltaView:
        return cls(
            strategy_id=value.strategy_id,
            strategy_version=value.strategy_version,
            from_window=value.from_window.value,
            to_window=value.to_window.value,
            delta_observed_winning_target_rate=_optional_view(
                value.delta_observed_winning_target_rate
            ),
            relation=value.relation.value,
        )


class MultiWindowSuccessWindowsResponse(BaseModel):
    model_config = _FROZEN_RESPONSE

    lottery_type: str
    run_id: str
    schema_version: str
    source_sha256: str
    source_commit: str
    strategy_set_fingerprint: str
    status: str
    draw_count: int
    event: str
    evidence_status: str
    research_only: bool
    promotion_allowed: bool
    window_definitions: list[WindowDefinitionView]
    null_contract: NullContractView
    strategy_count: int
    family_size: int
    rows: list[MultiWindowRowView]
    stability: list[StabilityDeltaView]
    source_authority: str

    @classmethod
    def from_value(cls, value: MultiWindowAnalysis) -> MultiWindowSuccessWindowsResponse:
        return cls(
            lottery_type=value.lottery_type,
            run_id=value.run_id,
            schema_version=value.schema_version,
            source_sha256=value.source_sha256,
            source_commit=value.source_commit,
            strategy_set_fingerprint=value.strategy_set_fingerprint,
            status=value.status,
            draw_count=value.draw_count,
            event=value.event,
            evidence_status=value.evidence_status,
            research_only=value.research_only,
            promotion_allowed=value.promotion_allowed,
            window_definitions=[
                WindowDefinitionView.from_value(item) for item in value.window_definitions
            ],
            null_contract=NullContractView.from_value(value.null_contract),
            strategy_count=value.strategy_count,
            family_size=value.family_size,
            rows=[MultiWindowRowView.from_value(item) for item in value.rows],
            stability=[StabilityDeltaView.from_value(item) for item in value.stability],
            source_authority=value.source_authority,
        )


def create_multiwindow_success_windows_router(
    t539_source_reader_factory: MultiWindowSuccessSourceReaderFactory | None,
    p638_source_reader_factory: MultiWindowSuccessSourceReaderFactory | None,
) -> APIRouter:
    router = APIRouter(tags=["multiwindow-success-windows"])

    @router.get(
        f"{API_PREFIX}/t539-historical/runs/{{run_id}}/success-windows",
        response_model=MultiWindowSuccessWindowsResponse,
        responses={
            404: {"model": ApiErrorResponse},
            422: {"model": ApiValidationErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="getT539HistoricalSuccessWindows",
    )
    def get_t539_success_windows(run_id: RunId) -> MultiWindowSuccessWindowsResponse | JSONResponse:
        return _query(
            run_id=run_id,
            source_reader_factory=t539_source_reader_factory,
            not_configured_code="T539_HISTORICAL_NOT_CONFIGURED",
            not_configured_message="T539 Historical Results are not configured.",
            not_found_code="T539_RUN_NOT_FOUND",
            unavailable_code="T539_HISTORICAL_UNAVAILABLE",
            unavailable_message="T539 Historical Results are unavailable.",
        )

    @router.get(
        f"{API_PREFIX}/p638-historical/current-runs/{{run_id}}/success-windows",
        response_model=MultiWindowSuccessWindowsResponse,
        responses={
            404: {"model": ApiErrorResponse},
            422: {"model": ApiValidationErrorResponse},
            503: {"model": ApiErrorResponse},
        },
        operation_id="getP638HistoricalCurrentSuccessWindows",
    )
    def get_p638_success_windows(run_id: RunId) -> MultiWindowSuccessWindowsResponse | JSONResponse:
        return _query(
            run_id=run_id,
            source_reader_factory=p638_source_reader_factory,
            not_configured_code="P638_HISTORICAL_NOT_CONFIGURED",
            not_configured_message="P638 Historical Results are not configured.",
            not_found_code="P638_CURRENT_RUN_NOT_FOUND",
            unavailable_code="P638_HISTORICAL_UNAVAILABLE",
            unavailable_message="P638 Historical Results are unavailable.",
        )

    return router


def _query(
    *,
    run_id: str,
    source_reader_factory: MultiWindowSuccessSourceReaderFactory | None,
    not_configured_code: str,
    not_configured_message: str,
    not_found_code: str,
    unavailable_code: str,
    unavailable_message: str,
) -> MultiWindowSuccessWindowsResponse | JSONResponse:
    if source_reader_factory is None:
        return _json_error(503, not_configured_code, not_configured_message)
    try:
        source = source_reader_factory().load_source(run_id)
        if source is None:
            return _json_error(404, not_found_code, "The requested replay run was not found.")
        return MultiWindowSuccessWindowsResponse.from_value(
            analyze_multiwindow_success_windows(source)
        )
    except (MultiWindowSuccessQueryError, ValueError):
        return _json_error(503, unavailable_code, unavailable_message)


def _optional_view(value: ExactRational | None) -> ExactRationalView | None:
    return None if value is None else ExactRationalView.from_value(value)


def _json_error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ApiErrorResponse(error_code=code, message=message).model_dump(mode="json"),
    )


__all__ = [
    "MultiWindowSuccessWindowsResponse",
    "create_multiwindow_success_windows_router",
]
