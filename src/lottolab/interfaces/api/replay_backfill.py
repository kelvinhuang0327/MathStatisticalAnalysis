"""Read-only query API for persisted replay backfills.

Offline workers own all prediction and persistence. Every route below performs
bounded, read-only queries against the explicitly configured candidate store.
"""

# pyright: reportUnusedFunction=false

from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import date
from pathlib import Path
from typing import Annotated, cast

from fastapi import APIRouter, FastAPI, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from lottolab.application.replay_strategy_inventory import load_replay_strategy_inventory
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayCellStatus
from lottolab.domain.replay_strategy_inventory import (
    ReplayDataStatus,
    ReplayExecutionCapability,
    ReplayLifecycleStatus,
    ReplayStrategyInventoryItem,
)
from lottolab.infrastructure.persistence.replay_backfill_store import (
    JsonObject,
    SQLiteBackfillStore,
    canonical_json,
)
from lottolab.interfaces.api.draw_data import ApiValidationErrorResponse

_MAX_ID_LENGTH = 200
_PERIODS = {"50": 50, "300": 300, "750": 750, "ALL": None}


class ReplayBackfillErrorResponse(BaseModel):
    """Code-only response emitted for query errors handled by the route."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    error_code: str


def _as_json_object(value: object) -> JsonObject | None:
    if type(value) is not dict:
        return None
    entries = cast(dict[object, object], value)
    normalized: JsonObject = {}
    for key, item in entries.items():
        if not isinstance(key, str):
            return None
        normalized[key] = item
    return normalized


def _strategy_history_view(
    item: ReplayStrategyInventoryItem,
    snapshot: JsonObject,
    stored_row: JsonObject | None,
) -> JsonObject:
    run_id = snapshot.get("run_id")
    status_counts = {
        status: 0
        for status in (
            "COMPLETE",
            "FAILED",
            "NOT_ELIGIBLE",
            "TYPED_CLOSURE",
            "MISSING",
            "PARTIAL",
            "ARTIFACT_ONLY",
        )
    }
    saved_prediction_cell_count = 0
    saved_ticket_count = 0
    persisted_cell_count = 0
    exact_identity = (
        item.lottery_type.value,
        item.strategy_id,
        item.strategy_version,
    )
    cell_rows_value = snapshot.get("cell_status_counts", [])
    cell_rows: list[object] = (
        cast(list[object], cell_rows_value) if isinstance(cell_rows_value, list) else []
    )
    for cell_row_value in cell_rows:
        if not isinstance(cell_row_value, dict):
            continue
        cell_row = cast(JsonObject, cell_row_value)
        identity = (
            cell_row.get("lottery_type", item.lottery_type.value),
            cell_row.get("strategy_id"),
            cell_row.get("strategy_version"),
        )
        if identity != exact_identity:
            continue
        execution_status = cell_row.get("execution_status")
        cell_count = cell_row.get("cell_count", 0)
        ticket_count = cell_row.get("ticket_count", 0)
        saved_cells = cell_row.get("saved_prediction_cell_count", 0)
        if isinstance(execution_status, str) and execution_status in status_counts:
            if type(cell_count) is int:
                status_counts[execution_status] += cell_count
                persisted_cell_count += cell_count
            if type(ticket_count) is int and execution_status == "COMPLETE":
                saved_ticket_count += ticket_count
            if type(saved_cells) is int:
                saved_prediction_cell_count += saved_cells

    selected_keys: set[tuple[str, str]] = set()
    for list_name in ("selected_strategies", "strategy_inventory"):
        rows_value = snapshot.get(list_name, [])
        if not isinstance(rows_value, list):
            continue
        for row_value in cast(list[object], rows_value):
            if not isinstance(row_value, dict):
                continue
            row = cast(JsonObject, row_value)
            strategy_id = row.get("strategy_id")
            strategy_version = row.get("strategy_version")
            if isinstance(strategy_id, str) and isinstance(strategy_version, str):
                selected_keys.add((strategy_id, strategy_version))
    for cell_row_value in cell_rows:
        if not isinstance(cell_row_value, dict):
            continue
        cell_row = cast(JsonObject, cell_row_value)
        strategy_id = cell_row.get("strategy_id")
        strategy_version = cell_row.get("strategy_version")
        if isinstance(strategy_id, str) and isinstance(strategy_version, str):
            selected_keys.add((strategy_id, strategy_version))
    is_selected = (
        (item.strategy_id, item.strategy_version) in selected_keys
        if item.strategy_version is not None
        else False
    )
    run_source_value = snapshot.get("run_source", {})
    run_source = cast(JsonObject, run_source_value) if isinstance(run_source_value, dict) else {}
    source_identity_status = run_source.get("identity_status", "UNKNOWN")

    target_count = (
        stored_row.get("available_target_count", snapshot.get("target_count", 0))
        if is_selected and stored_row is not None
        else (snapshot.get("target_count", 0) if is_selected else 0)
    )
    expected_cell_count = target_count if type(target_count) is int else 0
    pending_cell_count = max(0, expected_cell_count - persisted_cell_count) if is_selected else 0
    saved_history = saved_prediction_cell_count > 0
    identity_unknown = item.strategy_version is None and run_id is not None
    statuses: list[str] = []
    if identity_unknown or (run_id is not None and source_identity_status != "VERIFIED"):
        statuses.append("SOURCE_IDENTITY_UNKNOWN")
    if saved_history:
        statuses.append("HAS_HISTORY")
    if status_counts["FAILED"] > 0:
        statuses.append("FAILED")
    if status_counts["NOT_ELIGIBLE"] > 0:
        statuses.append("INSUFFICIENT_HISTORY")
    if pending_cell_count > 0:
        statuses.append("PENDING")
    if status_counts["MISSING"] > 0:
        statuses.append("MISSING")
    if status_counts["PARTIAL"] > 0:
        statuses.append("PARTIAL")
    if status_counts["TYPED_CLOSURE"] > 0:
        statuses.append("TYPED_CLOSURE")
    if status_counts["ARTIFACT_ONLY"] > 0:
        statuses.append("ARTIFACT_ONLY")
    if not is_selected and not identity_unknown:
        statuses.append("NOT_SELECTED_IN_RUN" if run_id is not None else "NO_HISTORY")
    elif not statuses:
        statuses.append("NO_HISTORY")

    primary_status = statuses[0]
    if not identity_unknown:
        for candidate in (
            "HAS_HISTORY",
            "FAILED",
            "INSUFFICIENT_HISTORY",
            "PENDING",
            "MISSING",
            "PARTIAL",
            "TYPED_CLOSURE",
            "ARTIFACT_ONLY",
            "NOT_SELECTED_IN_RUN",
            "NO_HISTORY",
            "SOURCE_IDENTITY_UNKNOWN",
        ):
            if candidate in statuses:
                primary_status = candidate
                break

    return {
        "history_status": primary_status,
        "history_statuses": statuses,
        "history_run_id": run_id,
        "history_scope": (
            "EXPLICIT_RUN_ID"
            if snapshot.get("selection_rule") == "EXPLICIT_RUN_ID"
            else "LATEST_RUN_BY_CREATED_AT_PER_LOTTERY_TYPE"
        ),
        "history_source_identity_status": source_identity_status,
        "history_counts": {
            "expected_cell_count": expected_cell_count,
            "persisted_cell_count": persisted_cell_count,
            "saved_prediction_cell_count": saved_prediction_cell_count,
            "saved_ticket_count": saved_ticket_count,
            "pending_cell_count": pending_cell_count,
            "execution_status_counts": status_counts,
        },
    }


def create_replay_backfill_router(store: SQLiteBackfillStore | None) -> APIRouter:
    router = APIRouter(prefix="/api/v1/replay-backfill", tags=["replay-backfill"])

    @router.get(
        "/strategies",
        response_model=None,
        responses={
            422: {
                "model": ApiValidationErrorResponse | ReplayBackfillErrorResponse
            }
        },
    )
    def strategies(
        lottery_type: LotteryType | None = None,
        q: Annotated[str | None, Query(max_length=_MAX_ID_LENGTH)] = None,
        lifecycle_status: str | None = None,
        data_status: ReplayDataStatus | None = None,
        limit: Annotated[int, Query(ge=1, le=250)] = 50,
        cursor: str | None = None,
        run_id: str | None = None,
    ) -> JsonObject | JSONResponse:
        if store is None:
            return _error(503, "REPLAY_BACKFILL_NOT_CONFIGURED")
        if run_id is not None:
            if not run_id or run_id != run_id.strip() or len(run_id) > _MAX_ID_LENGTH:
                return _error(422, "INVALID_RUN_ID")
            if lottery_type is None:
                return _error(422, "INVALID_QUERY")
        try:
            inventory = load_replay_strategy_inventory()
        except Exception:
            return _error(503, "REPLAY_BACKFILL_UNAVAILABLE")
        query_lotteries: tuple[LotteryType, ...] = (
            (lottery_type,)
            if lottery_type is not None
            else (
                cast(LotteryType, LotteryType.BIG_LOTTO),
                cast(LotteryType, LotteryType.DAILY_539),
                cast(LotteryType, LotteryType.POWER_LOTTO),
            )
        )
        try:
            snapshots: dict[str, JsonObject] = {
                selected_lottery.value: store.strategy_history_snapshot(
                    selected_lottery.value,
                    run_id=run_id,
                )
                for selected_lottery in query_lotteries
            }
        except KeyError:
            return _error(404, "REPLAY_BACKFILL_RUN_NOT_FOUND")
        except ValueError:
            return _error(422, "INVALID_QUERY")
        except Exception:
            return _error(503, "REPLAY_BACKFILL_UNAVAILABLE")
        try:
            stored_by_key: dict[tuple[str, str, str], JsonObject] = {}
            for snapshot in snapshots.values():
                stored_rows_value = snapshot.get("strategy_inventory", [])
                if not isinstance(stored_rows_value, list):
                    continue
                for stored_row_value in cast(list[object], stored_rows_value):
                    if not isinstance(stored_row_value, dict):
                        continue
                    stored_row = cast(JsonObject, stored_row_value)
                    key_values = (
                        stored_row.get("lottery_type"),
                        stored_row.get("strategy_id"),
                        stored_row.get("strategy_version"),
                    )
                    if all(isinstance(value, str) for value in key_values):
                        stored_by_key[cast(tuple[str, str, str], key_values)] = stored_row
            rows: list[JsonObject] = []
            for item in inventory.items:
                if lottery_type is not None and item.lottery_type is not lottery_type:
                    continue
                lifecycle = _contract_lifecycle(item.lifecycle_status)
                selected_snapshot = snapshots[item.lottery_type.value]
                source_row = (
                    stored_by_key.get(
                        (item.lottery_type.value, item.strategy_id, item.strategy_version)
                    )
                    if item.strategy_version is not None
                    else None
                )
                item_data_status = (
                    source_row["data_status"]
                    if source_row is not None
                    else item.replay_data_status.value
                )
                if lifecycle_status is not None and lifecycle != lifecycle_status:
                    continue
                if data_status is not None and item_data_status != data_status.value:
                    continue
                if q and q.casefold() not in (
                    item.strategy_id + " " + item.display_name
                ).casefold():
                    continue
                row: JsonObject = {
                    "strategy_id": item.strategy_id,
                    "strategy_version": item.strategy_version,
                    "display_name": item.display_name,
                    "lottery_type": item.lottery_type.value,
                    "lifecycle_status": lifecycle,
                    "inventory_lifecycle_status": item.lifecycle_status.value,
                    "data_status": item_data_status,
                    "inventory_data_status": item.replay_data_status.value,
                    "source_kind": (
                        source_row["source_kind"] if source_row else item.source_kind
                    ),
                    "inventory_source_kind": item.source_kind,
                    "inventory_source_locator": item.source_locator,
                    "strategy_source_identity": (
                        source_row["source_identity"] if source_row else None
                    ),
                    "executable": (
                        item.execution_capability is ReplayExecutionCapability.EXECUTABLE
                        and (source_row is None or source_row["executable"])
                        and item_data_status not in {"CODE_ONLY", "ARTIFACT_ONLY", "REJECTED"}
                    ),
                    "reconstructable": item.reconstructable,
                    "wrapper_callable": item.wrapper_callable,
                    "backfill_native_binding": item.backfill_native_binding,
                    "backfill_native_binding_sources": [
                        {
                            "source_kind": binding.source_kind,
                            "source_locator": binding.source_locator,
                        }
                        for binding in item.backfill_native_binding_sources
                    ],
                    "backfill_runnable": item.backfill_runnable,
                    "execution_block_reason": item.execution_block_reason,
                    "available_target_count": (
                        source_row["available_target_count"] if source_row else 0
                    ),
                    "training_status": (
                        source_row["training_status"] if source_row else _training_status(item)
                    ),
                }
                row.update(_strategy_history_view(item, selected_snapshot, source_row))
                rows.append(row)
            rows.sort(
                key=lambda row: (
                    row["lottery_type"], row["strategy_id"], row["strategy_version"] or ""
                )
            )
            filters: dict[str, str | None] = {
                "lottery_type": None if lottery_type is None else lottery_type.value,
                "q": q,
                "lifecycle_status": lifecycle_status,
                "data_status": None if data_status is None else data_status.value,
            }
            if run_id is not None:
                filters["run_id"] = run_id
            checksum = hashlib.sha256(canonical_json(rows).encode()).hexdigest()
            offset = _read_cursor(cursor, "strategies", checksum, filters)
            page = rows[offset : offset + limit]
            next_offset = offset + len(page)
            return {
                "items": page,
                "total_count": len(rows),
                "history_scope": {
                    "strategy_identity_source": "CURRENT_REPLAY_STRATEGY_INVENTORY",
                    "persisted_history_source": "REPLAY_BACKFILL_SCHEMA_V2",
                    "run_selection_rule": (
                        "EXPLICIT_RUN_ID"
                        if run_id is not None
                        else "LATEST_RUN_BY_CREATED_AT_PER_LOTTERY_TYPE"
                    ),
                    "runs": {
                        key: {
                            "run_id": snapshot.get("run_id"),
                            "created_at": snapshot.get("created_at"),
                            "dataset_identity": snapshot.get("dataset_identity"),
                            "execution_version": snapshot.get("execution_version"),
                            "source": snapshot.get("run_source"),
                        }
                        for key, snapshot in snapshots.items()
                    },
                },
                "next_cursor": (
                    _write_cursor("strategies", checksum, filters, next_offset)
                    if next_offset < len(rows)
                    else None
                ),
            }
        except ValueError:
            return _error(422, "INVALID_CURSOR_OR_FILTER")
        except Exception:
            return _error(503, "REPLAY_BACKFILL_UNAVAILABLE")

    @router.get(
        "/predictions",
        response_model=None,
        responses={
            422: {
                "model": ApiValidationErrorResponse | ReplayBackfillErrorResponse
            }
        },
    )
    def predictions(
        lottery_type: LotteryType,
        run_id: Annotated[str | None, Query(min_length=1, max_length=_MAX_ID_LENGTH)] = None,
        strategy_id: Annotated[str | None, Query(min_length=1, max_length=_MAX_ID_LENGTH)] = None,
        from_date: date | None = None,
        to_date: date | None = None,
        period: Annotated[str, Query(pattern="^(50|300|750|ALL)$")] = "ALL",
        limit: Annotated[int, Query(ge=1, le=250)] = 50,
        cursor: str | None = None,
    ) -> JsonObject | JSONResponse:
        if store is None:
            return _error(503, "REPLAY_BACKFILL_NOT_CONFIGURED")
        if from_date and to_date and from_date > to_date:
            return _error(422, "INVALID_DATE_RANGE")
        filters = {
            "lottery_type": lottery_type.value,
            "run_id": run_id,
            "strategy_id": strategy_id,
            "from_date": None if from_date is None else from_date.isoformat(),
            "to_date": None if to_date is None else to_date.isoformat(),
            "period": period,
        }
        filter_hash = hashlib.sha256(canonical_json(filters).encode()).hexdigest()
        after: tuple[str, int, str, str, str] | None = None
        expected_run_id: str | None = None
        if cursor:
            try:
                state = _decode(cursor)
                if state.get("kind") != "predictions" or state.get("query") != filter_hash:
                    return _error(422, "INVALID_CURSOR_OR_FILTER")
                raw_after: object = state.get("after")
                if not isinstance(raw_after, list):
                    return _error(422, "INVALID_CURSOR_OR_FILTER")
                after_values = cast(list[object], raw_after)
                if len(after_values) != 5:
                    return _error(422, "INVALID_CURSOR_OR_FILTER")
                draw_date, draw_id, cursor_strategy_id, strategy_version, cell_id = after_values
                if (
                    type(draw_date) is not str
                    or type(draw_id) is not int
                    or type(cursor_strategy_id) is not str
                    or type(strategy_version) is not str
                    or type(cell_id) is not str
                ):
                    return _error(422, "INVALID_CURSOR_OR_FILTER")
                after = (
                    draw_date,
                    draw_id,
                    cursor_strategy_id,
                    strategy_version,
                    cell_id,
                )
                raw_cursor_run_id: object = state.get("run_id")
                if type(raw_cursor_run_id) is not str:
                    return _error(422, "INVALID_CURSOR_OR_FILTER")
                expected_run_id = raw_cursor_run_id
            except (ValueError, TypeError, json.JSONDecodeError):
                return _error(422, "INVALID_CURSOR_OR_FILTER")
        try:
            page = store.prediction_page(
                lottery_type=lottery_type.value,
                run_id=run_id,
                strategy_id=strategy_id,
                from_date=None if from_date is None else from_date.isoformat(),
                to_date=None if to_date is None else to_date.isoformat(),
                period=_PERIODS[period],
                limit=limit,
                after=after,
            )
            run_id = page["run_id"]
            if expected_run_id is not None and run_id != expected_run_id:
                return _error(422, "STALE_CURSOR")
            rows = page.get("rows", [])
            has_more = len(rows) > limit
            selected = rows[:limit]
            next_cursor = None
            if has_more and selected:
                next_cursor = _encode(
                    {
                        "kind": "predictions",
                        "query": filter_hash,
                        "run_id": run_id,
                        "after": selected[-1]["key"],
                    }
                )
            return {
                "run_id": run_id,
                "total_count": page["total_count"],
                "items": [
                    _prediction_item(
                        row["payload"],
                        row["identity"],
                        row["cutoff_source"],
                    )
                    for row in selected
                ],
                "next_cursor": next_cursor,
            }
        except KeyError:
            return _error(404, "REPLAY_BACKFILL_RUN_NOT_FOUND")
        except ValueError:
            return _error(422, "INVALID_QUERY")
        except Exception:
            return _error(503, "REPLAY_BACKFILL_UNAVAILABLE")

    @router.get(
        "/coverage",
        response_model=None,
        responses={
            422: {
                "model": ApiValidationErrorResponse | ReplayBackfillErrorResponse
            }
        },
    )
    def coverage(
        lottery_type: LotteryType,
        run_id: Annotated[str | None, Query(min_length=1, max_length=_MAX_ID_LENGTH)] = None,
        strategy_id: Annotated[str | None, Query(min_length=1, max_length=_MAX_ID_LENGTH)] = None,
        from_date: date | None = None,
        to_date: date | None = None,
        period: Annotated[str, Query(pattern="^(50|300|750|ALL)$")] = "ALL",
    ) -> JsonObject | JSONResponse:
        if store is None:
            return _error(503, "REPLAY_BACKFILL_NOT_CONFIGURED")
        if from_date and to_date and from_date > to_date:
            return _error(422, "INVALID_DATE_RANGE")
        try:
            result = store.backfill_coverage(
                lottery_type.value,
                run_id=run_id,
                strategy_id=strategy_id,
                from_date=None if from_date is None else from_date.isoformat(),
                to_date=None if to_date is None else to_date.isoformat(),
                period=_PERIODS[period],
            )
            if result is None:
                return {
                    "lottery_type": lottery_type.value,
                    "expected_strategy_count": 0,
                    "expected_target_count": 0,
                    "expected_cell_count": 0,
                    "completed_cell_count": 0,
                    "failed_cell_count": 0,
                    "closed_cell_count": 0,
                    "complete_coverage_percent": 0.0,
                    "missing_strategy_ids": [],
                    "run_id": None,
                }
            return result
        except KeyError:
            return _error(404, "REPLAY_BACKFILL_RUN_NOT_FOUND")
        except ValueError:
            return _error(422, "INVALID_QUERY")
        except Exception:
            return _error(503, "REPLAY_BACKFILL_UNAVAILABLE")

    # Retained for existing local consumers; all routes remain GET-only.
    @router.get(
        "/results",
        response_model=None,
        responses={
            422: {
                "model": ApiValidationErrorResponse | ReplayBackfillErrorResponse
            }
        },
    )
    def results(
        run_id: str | None = None,
        lottery_type: LotteryType | None = None,
        strategy_id: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        target_draw_id: str | None = None,
        execution_status: ReplayCellStatus | None = None,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> JsonObject | JSONResponse:
        if store is None:
            return _error(503, "REPLAY_BACKFILL_NOT_CONFIGURED")
        if start_date and end_date and start_date > end_date:
            return _error(422, "INVALID_DATE_RANGE")
        try:
            return store.query(
                run_id=run_id,
                lottery_type=lottery_type.value if lottery_type else None,
                strategy_id=strategy_id,
                start_date=start_date.isoformat() if start_date else None,
                end_date=end_date.isoformat() if end_date else None,
                target_draw_id=target_draw_id,
                execution_status=execution_status.value if execution_status else None,
                limit=limit,
                offset=offset,
            )
        except Exception:
            return _error(503, "REPLAY_BACKFILL_UNAVAILABLE")

    @router.get(
        "/runs",
        response_model=None,
        responses={
            422: {
                "model": ApiValidationErrorResponse | ReplayBackfillErrorResponse
            }
        },
    )
    def runs(
        lottery_type: LotteryType | None = None,
        limit: Annotated[int, Query(ge=1, le=250)] = 50,
        cursor: str | None = None,
    ) -> JsonObject | JSONResponse:
        if store is None:
            return _error(503, "REPLAY_BACKFILL_NOT_CONFIGURED")
        try:
            rows = store.list_runs(
                lottery_type=None if lottery_type is None else lottery_type.value
            )
        except Exception:
            return _error(503, "REPLAY_BACKFILL_UNAVAILABLE")

        filters: JsonObject = {
            "lottery_type": None if lottery_type is None else lottery_type.value
        }
        checksum = hashlib.sha256(canonical_json(rows).encode()).hexdigest()
        try:
            offset = _read_cursor(cursor, "runs", checksum, filters)
        except ValueError:
            return _error(422, "INVALID_CURSOR_OR_FILTER")
        if offset > len(rows):
            return _error(422, "INVALID_CURSOR_OR_FILTER")

        page = rows[offset : offset + limit]
        next_offset = offset + len(page)
        return {
            "items": page,
            "total_count": len(rows),
            "next_cursor": (
                _write_cursor("runs", checksum, filters, next_offset)
                if next_offset < len(rows)
                else None
            ),
        }

    @router.get(
        "/runs/{run_id}",
        response_model=None,
        responses={
            422: {
                "model": ApiValidationErrorResponse | ReplayBackfillErrorResponse
            }
        },
    )
    def progress(run_id: str) -> JsonObject | JSONResponse:
        if store is None:
            return _error(503, "REPLAY_BACKFILL_NOT_CONFIGURED")
        try:
            return store.summary(run_id)
        except KeyError:
            return _error(404, "REPLAY_BACKFILL_RUN_NOT_FOUND")
        except Exception:
            return _error(503, "REPLAY_BACKFILL_UNAVAILABLE")

    return router


def _prediction_item(
    payload: JsonObject,
    identity: JsonObject,
    cutoff_source: JsonObject | None,
) -> JsonObject:
    raw_tickets: object = payload.get("predicted_tickets", [])
    raw_hits: object = payload.get("hit_details", [])
    tickets_are_array = isinstance(raw_tickets, list)
    hits_are_array = isinstance(raw_hits, list)
    tickets: list[JsonObject] = []
    hits: list[JsonObject] = []
    invalid_entry = False
    if tickets_are_array:
        for raw_ticket in cast(list[object], raw_tickets):
            ticket = _as_json_object(raw_ticket)
            if ticket is None:
                invalid_entry = True
            else:
                tickets.append(ticket)
    if hits_are_array:
        for raw_hit in cast(list[object], raw_hits):
            hit = _as_json_object(raw_hit)
            if hit is None:
                invalid_entry = True
            else:
                hits.append(hit)
    identity_matches = tickets_are_array and hits_are_array and not invalid_entry
    hits_by_position: dict[int, JsonObject] = {}
    ambiguous_hit_positions: set[int] = set()
    for hit in hits:
        raw_position: object = hit.get("ticket_position")
        if type(raw_position) is not int:
            continue
        position = raw_position
        if position in hits_by_position:
            ambiguous_hit_positions.add(position)
            hits_by_position.pop(position)
        elif position not in ambiguous_hit_positions:
            hits_by_position[position] = hit
    if ambiguous_hit_positions:
        identity_matches = False
    identity_fields = (
        "lottery_type",
        "target_draw_id",
        "target_draw_date",
        "strategy_id",
        "strategy_version",
    )
    identity_matches = identity_matches and all(
        payload.get(key) == identity.get(key) for key in identity_fields
    )
    if "run_id" in payload and payload["run_id"] != identity.get("run_id"):
        identity_matches = False
    if "cell_identity" in payload and payload["cell_identity"] != identity.get("cell_identity"):
        identity_matches = False
    for ticket in tickets:
        if not _ticket_claims_identity_match(
            ticket, identity, ticket.get("ticket_position")
        ):
            identity_matches = False
    for hit in hits:
        if not _ticket_claims_identity_match(hit, identity, hit.get("ticket_position")):
            identity_matches = False
    predicted: list[JsonObject] = []
    for ticket in tickets:
        position = ticket.get("ticket_position")
        hit = (
            hits_by_position.get(position, {})
            if (
                type(position) is int
                and position not in ambiguous_hit_positions
                and identity_matches
            )
            else {}
        )
        ticket_identity = {
            "lottery_type": identity["lottery_type"],
            "run_id": identity["run_id"],
            "target_draw_id": identity["target_draw_id"],
            "strategy_id": identity["strategy_id"],
            "strategy_version": identity["strategy_version"],
            "ticket_position": position,
        }
        predicted.append(
            {
                "ticket_position": position,
                "ticket_identity": ticket_identity,
                "main_numbers": ticket["main_numbers"],
                "special_numbers": (
                    [] if ticket.get("special_number") is None else [ticket["special_number"]]
                ),
                "main_hit_count": hit.get("zone1_hits"),
                "special_hit": hit.get("zone2_hit"),
                "prize_tier": hit.get("prize_tier"),
            }
        )
    winning = payload.get("winning_numbers", {})
    training = payload.get("training", {})
    winning = {} if type(winning) is not dict else cast(JsonObject, winning)
    training = {} if type(training) is not dict else cast(JsonObject, training)
    evaluated = [
        ticket
        for ticket in predicted
        if type(ticket.get("main_hit_count")) is int
        and type(ticket.get("special_hit")) is bool
        and "prize_tier" in ticket
    ]
    fully_evaluated = bool(predicted) and len(evaluated) == len(predicted)
    source = payload.get("strategy_source", {})
    source = {} if type(source) is not dict else cast(JsonObject, source)
    strategy_fingerprint = payload.get("strategy_fingerprint")
    source_identity = (
        source.get("source_identity") or source.get("fingerprint") or strategy_fingerprint
    )
    prediction_cutoff = _prediction_cutoff(
        payload,
        identity,
        cutoff_source,
        identity_matches=identity_matches,
    )
    return {
        "lottery_type": identity["lottery_type"],
        "run_id": identity["run_id"],
        "strategy_id": identity["strategy_id"],
        "strategy_version": identity["strategy_version"],
        "target_draw_number": identity["target_draw_id"],
        "target_draw_date": identity["target_draw_date"],
        "identity_status": "VERIFIED" if identity_matches else "UNTRUSTED",
        "prediction_status": payload["execution_status"],
        "predicted_tickets": predicted,
        "actual_main_numbers": winning.get("main_numbers", []),
        "actual_special_numbers": (
            [] if winning.get("special_number") is None else [winning["special_number"]]
        ),
        "evaluation_status": (
            "UNTRUSTED"
            if not identity_matches
            else ("EVALUATED" if fully_evaluated else ("PARTIAL" if evaluated else "NOT_EVALUATED"))
        ),
        "portfolio_any_prize": (
            any(ticket.get("prize_tier") is not None for ticket in predicted)
            if fully_evaluated and identity_matches
            else None
        ),
        "best_main_hits": (
            max(ticket["main_hit_count"] for ticket in predicted)
            if fully_evaluated and identity_matches
            else None
        ),
        "source_kind": source.get("source_kind", source.get("source", "NATIVE_REPLAY")),
        "lifecycle_status": source.get("lifecycle_status", "UNKNOWN"),
        "data_status": source.get(
            "data_status",
            "ARTIFACT_ONLY" if payload["execution_status"] == "ARTIFACT_ONLY" else "REBUILDABLE",
        ),
        "prediction_cutoff": prediction_cutoff,
        "source_identity": source_identity,
        "source_hash": source.get("source_sha256") or strategy_fingerprint,
        "strategy_fingerprint": strategy_fingerprint,
        "dataset_identity": payload.get("dataset_identity"),
        "history_fingerprint": payload.get("history_fingerprint"),
        "engine_version": payload.get("engine_version"),
        "execution_version": payload.get("execution_version"),
        "training": {
            "training_status": training.get("training_status", "NOT_TRAINABLE"),
            "model_version": training.get("model_version"),
            "training_cutoff": training.get("training_cutoff"),
            "training_artifact_id": training.get("training_artifact_id"),
        },
    }


def _ticket_claims_identity_match(
    item: JsonObject, identity: JsonObject, ticket_position: object
) -> bool:
    fields = (
        "lottery_type",
        "run_id",
        "target_draw_id",
        "strategy_id",
        "strategy_version",
    )
    for key in fields:
        if key in item and item[key] != identity.get(key):
            return False
    nested_identity = item.get("identity")
    if nested_identity is not None:
        if type(nested_identity) is not dict:
            return False
        nested = cast(JsonObject, nested_identity)
        if any(nested.get(key) != identity.get(key) for key in fields):
            return False
        if nested.get("ticket_position") != ticket_position:
            return False
    return type(ticket_position) is int and ticket_position > 0


def _prediction_cutoff(
    payload: JsonObject,
    identity: JsonObject,
    source: JsonObject | None,
    *,
    identity_matches: bool,
) -> JsonObject:
    result: JsonObject = {
        "status": "UNKNOWN",
        "draw_number": None,
        "draw_date": None,
        "source_identity": None,
        "source_locator": None,
        "source_hash": None,
        "history_draw_count": None,
        "reason_code": "CUTOFF_SOURCE_NOT_RECORDED",
    }
    if not identity_matches:
        result["status"] = "UNTRUSTED"
        result["reason_code"] = "PREDICTION_IDENTITY_CONFLICT"
        return result

    cutoff_id = payload.get("cutoff_draw_id")
    cutoff_date = payload.get("cutoff_draw_date")
    if cutoff_id is None and cutoff_date is None:
        return result
    if type(cutoff_id) is not str or type(cutoff_date) is not str:
        result["status"] = "UNTRUSTED"
        result["reason_code"] = "INCOMPLETE_CUTOFF_IDENTITY"
        return result
    try:
        parsed_cutoff_date = date.fromisoformat(cutoff_date)
        parsed_target_date = date.fromisoformat(identity["target_draw_date"])
        cutoff_number = int(cutoff_id)
        target_number = int(identity["target_draw_id"])
    except (TypeError, ValueError):
        result["status"] = "UNTRUSTED"
        result["reason_code"] = "INVALID_CUTOFF_IDENTITY"
        return result
    if cutoff_number >= target_number or parsed_cutoff_date >= parsed_target_date:
        result["status"] = "UNTRUSTED"
        result["reason_code"] = "CUTOFF_NOT_BEFORE_TARGET"
        return result

    input_evidence = payload.get("prediction_input")
    if type(input_evidence) is not dict:
        result["reason_code"] = "PREDICTION_INPUT_NOT_RECORDED"
        return result
    evidence = cast(JsonObject, input_evidence)
    if (
        evidence.get("cutoff_draw_id") != cutoff_id
        or evidence.get("cutoff_draw_date") != cutoff_date
        or evidence.get("dataset_identity") != payload.get("dataset_identity")
    ):
        result["status"] = "UNTRUSTED"
        result["reason_code"] = "CUTOFF_INPUT_IDENTITY_CONFLICT"
        return result

    history_hash = evidence.get("history_fingerprint")
    history_count = evidence.get("history_draw_count")
    source_identity = f"causal-history:{identity['cell_identity']}"
    source_locator = f"replay-input://{identity['run_id']}/{identity['cell_identity']}"
    if (
        type(history_hash) is not str
        or len(history_hash) != 64
        or any(character not in "0123456789abcdef" for character in history_hash.lower())
        or history_hash != payload.get("history_fingerprint")
        or type(history_count) is not int
        or history_count < 1
        or evidence.get("source_identity") != source_identity
    ):
        result["status"] = "UNTRUSTED"
        result["reason_code"] = "CUTOFF_SOURCE_IDENTITY_CONFLICT"
        return result
    if source is None:
        result["reason_code"] = "CUTOFF_SOURCE_RECORD_MISSING"
        return result
    if (
        source.get("source_identity") != source_identity
        or source.get("source_kind") != "CAUSAL_HISTORY"
        or source.get("source_locator") != source_locator
        or source.get("source_hash") != history_hash
        or source.get("artifact_only") is not False
    ):
        result["status"] = "UNTRUSTED"
        result["reason_code"] = "CUTOFF_SOURCE_RECORD_CONFLICT"
        return result
    result.update(
        {
            "status": "VERIFIED",
            "draw_number": cutoff_id,
            "draw_date": cutoff_date,
            "source_identity": source_identity,
            "source_locator": source_locator,
            "source_hash": history_hash,
            "history_draw_count": history_count,
            "reason_code": None,
        }
    )
    return result


def _contract_lifecycle(status: ReplayLifecycleStatus) -> str:
    if status is ReplayLifecycleStatus.UNREGISTERED_IDENTIFIED:
        return "UNREGISTERED"
    if status in {ReplayLifecycleStatus.ARTIFACT_ONLY, ReplayLifecycleStatus.CODE_ONLY,
                  ReplayLifecycleStatus.IDEA, ReplayLifecycleStatus.RETIRED}:
        return "OFFLINE"
    return status.value


def _training_status(item: ReplayStrategyInventoryItem) -> str:
    if item.replay_data_status is ReplayDataStatus.ARTIFACT_ONLY:
        return "HISTORICAL_ARTIFACT"
    return "NOT_TRAINABLE"


def _encode(value: JsonObject) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _decode(value: str) -> JsonObject:
    raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    decoded: object = json.loads(raw)
    result = _as_json_object(decoded)
    if result is None:
        raise ValueError("cursor must be an object")
    return result


def _write_cursor(kind: str, checksum: str, filters: JsonObject, offset: int) -> str:
    return _encode({"kind": kind, "checksum": checksum, "filters": filters, "offset": offset})


def _read_cursor(
    cursor: str | None, kind: str, checksum: str, filters: JsonObject
) -> int:
    if cursor is None:
        return 0
    state = _decode(cursor)
    if state.get("kind") != kind or state.get("checksum") != checksum:
        raise ValueError("cursor snapshot changed")
    if state.get("filters") != filters:
        raise ValueError("cursor filters changed")
    offset = state.get("offset")
    if type(offset) is not int or offset < 0:
        raise ValueError("invalid cursor offset")
    return offset


def _error(status: int, code: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error_code": code})


def create_app() -> FastAPI:
    """Use only the explicit LOTTOLAB_REPLAY_BACKFILL_DB candidate path."""
    configured = os.environ.get("LOTTOLAB_REPLAY_BACKFILL_DB")
    store = SQLiteBackfillStore(Path(configured), read_only=True) if configured else None
    app = FastAPI(title="LottoLab Replay Backfill Results", version="1")
    app.include_router(create_replay_backfill_router(store))
    return app
