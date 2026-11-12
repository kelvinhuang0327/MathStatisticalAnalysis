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
from typing import Annotated, Any, cast

from fastapi import APIRouter, FastAPI, Query
from fastapi.responses import JSONResponse

from lottolab.application.replay_portfolio_qualification import assess_research_portfolio
from lottolab.application.replay_strategy_inventory import load_replay_strategy_inventory
from lottolab.application.seeded_single_replay import seeded_replay_version
from lottolab.application.use_cases.replay_backfill import JsonObject, canonical_json
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayCellStatus
from lottolab.domain.replay_strategy_inventory import (
    ReplayDataStatus,
    ReplayExecutionCapability,
    ReplayLifecycleStatus,
)
from lottolab.infrastructure.persistence.replay_backfill_store import SQLiteBackfillStore
from lottolab.strategies.catalog import production_catalog

_MAX_ID_LENGTH = 200
_PERIODS = {"50": 50, "300": 300, "750": 750, "ALL": None}


def create_replay_backfill_router(store: SQLiteBackfillStore | None) -> APIRouter:
    router = APIRouter(prefix="/api/v1/replay-backfill", tags=["replay-backfill"])

    @router.get("/strategies", response_model=None)
    def strategies(
        lottery_type: LotteryType | None = None,
        q: Annotated[str | None, Query(max_length=_MAX_ID_LENGTH)] = None,
        lifecycle_status: str | None = None,
        data_status: ReplayDataStatus | None = None,
        limit: Annotated[int, Query(ge=1, le=250)] = 50,
        cursor: str | None = None,
    ) -> JsonObject | JSONResponse:
        if store is None:
            return _error(503, "REPLAY_BACKFILL_NOT_CONFIGURED")
        try:
            inventory = load_replay_strategy_inventory()
            query_lotteries = (lottery_type,) if lottery_type else tuple(LotteryType)
            stored = [
                row
                for selected_lottery in query_lotteries
                for row in store.stored_strategy_inventory(selected_lottery.value)
            ]
            stored_by_key = {
                (row["lottery_type"], row["strategy_id"], row["strategy_version"]): row
                for selected_lottery in query_lotteries
                for row in store.stored_strategy_inventory(selected_lottery.value)
            }
            seeded_descriptors = {
                d.strategy_id: d
                for d in production_catalog().list(lottery_type=LotteryType.BIG_LOTTO)
                if "randomness:PROCESS_GLOBAL_UNSEEDED_MATH_RANDOM_EQUIVALENT" in d.provenance
            }
            rows = []
            for item in inventory.items:
                lifecycle = _contract_lifecycle(item.lifecycle_status)
                source_row = stored_by_key.get(
                    (item.lottery_type.value, item.strategy_id, item.strategy_version)
                )
                item_data_status = (
                    source_row["data_status"]
                    if source_row is not None
                    else item.replay_data_status.value
                )
                if lottery_type is not None and item.lottery_type is not lottery_type:
                    continue
                if lifecycle_status is not None and lifecycle != lifecycle_status:
                    continue
                if data_status is not None and item_data_status != data_status.value:
                    continue
                if q and q.casefold() not in (
                    item.strategy_id + " " + item.display_name
                ).casefold():
                    continue
                rows.append(
                    {
                        "strategy_id": item.strategy_id,
                        "strategy_version": item.strategy_version,
                        "display_name": item.display_name,
                        "lottery_type": item.lottery_type.value,
                        "lifecycle_status": lifecycle,
                        "data_status": item_data_status,
                        "source_kind": (
                            source_row["source_kind"] if source_row else item.source_kind
                        ),
                        "executable": (
                            item.execution_capability is ReplayExecutionCapability.EXECUTABLE
                            and (source_row is None or source_row["executable"])
                            and item_data_status not in {"CODE_ONLY", "ARTIFACT_ONLY", "REJECTED"}
                            and not (
                                item.lottery_type is LotteryType.BIG_LOTTO
                                and item.strategy_id in seeded_descriptors
                                and item.strategy_version
                                == seeded_descriptors[item.strategy_id].version
                            )
                        ),
                        "available_target_count": (
                            source_row["available_target_count"]
                            if source_row
                            else 0
                        ),
                        "training_status": (
                            source_row["training_status"]
                            if source_row
                            else _training_status(item)
                        ),
                    }
                )
            if lottery_type in (None, LotteryType.BIG_LOTTO):
                for descriptor in seeded_descriptors.values():
                    version = seeded_replay_version(descriptor.version)
                    source_row = stored_by_key.get(
                        (LotteryType.BIG_LOTTO.value, descriptor.strategy_id, version)
                    )
                    seeded_status = source_row["data_status"] if source_row else "REBUILDABLE"
                    lifecycle = descriptor.lifecycle_status.value
                    if lifecycle_status is not None and lifecycle != lifecycle_status:
                        continue
                    if data_status is not None and seeded_status != data_status.value:
                        continue
                    if q and q.casefold() not in (
                        descriptor.strategy_id + " " + descriptor.strategy_name
                    ).casefold():
                        continue
                    rows.append(
                        {
                            "strategy_id": descriptor.strategy_id,
                            "strategy_version": version,
                            "display_name": descriptor.strategy_name,
                            "lottery_type": LotteryType.BIG_LOTTO.value,
                            "lifecycle_status": lifecycle,
                            "data_status": seeded_status,
                            "source_kind": (
                                source_row["source_kind"] if source_row else "SEEDED_REPLAY"
                            ),
                            "executable": (
                                descriptor.executable
                                and (source_row is None or source_row["executable"])
                                and seeded_status not in {"CODE_ONLY", "ARTIFACT_ONLY", "REJECTED"}
                            ),
                            "available_target_count": (
                                source_row["available_target_count"] if source_row else 0
                            ),
                            "training_status": (
                                source_row["training_status"] if source_row else "NOT_TRAINABLE"
                            ),
                        }
                    )
            existing_keys = {
                (row["lottery_type"], row["strategy_id"], row["strategy_version"])
                for row in rows
            }
            for source_row in stored:
                key = (
                    source_row["lottery_type"],
                    source_row["strategy_id"],
                    source_row["strategy_version"],
                )
                if key in existing_keys:
                    continue
                lifecycle = source_row["lifecycle_status"]
                if lifecycle_status is not None and lifecycle != lifecycle_status:
                    continue
                if data_status is not None and source_row["data_status"] != data_status.value:
                    continue
                if q and q.casefold() not in (
                    source_row["strategy_id"] + " " + source_row["display_name"]
                ).casefold():
                    continue
                rows.append(
                    {
                        "strategy_id": source_row["strategy_id"],
                        "strategy_version": source_row["strategy_version"],
                        "display_name": source_row["display_name"],
                        "lottery_type": source_row["lottery_type"],
                        "lifecycle_status": lifecycle,
                        "data_status": source_row["data_status"],
                        "source_kind": source_row["source_kind"],
                        "executable": source_row["executable"],
                        "available_target_count": source_row["available_target_count"],
                        "training_status": source_row["training_status"],
                    }
                )
            rows.sort(
                key=lambda row: (
                    row["lottery_type"], row["strategy_id"], row["strategy_version"] or ""
                )
            )
            filters = {
                "lottery_type": None if lottery_type is None else lottery_type.value,
                "q": q,
                "lifecycle_status": lifecycle_status,
                "data_status": None if data_status is None else data_status.value,
            }
            checksum = hashlib.sha256(canonical_json(rows).encode()).hexdigest()
            offset = _read_cursor(cursor, "strategies", checksum, filters)
            page = rows[offset : offset + limit]
            next_offset = offset + len(page)
            return {
                "items": page,
                "total_count": len(rows),
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

    @router.get("/predictions", response_model=None)
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
                raw_after = state.get("after")
                if not isinstance(raw_after, list) or len(raw_after) != 5:
                    return _error(422, "INVALID_CURSOR_OR_FILTER")
                after = (
                    str(raw_after[0]),
                    int(raw_after[1]),
                    str(raw_after[2]),
                    str(raw_after[3]),
                    str(raw_after[4]),
                )
                expected_run_id = str(state.get("run_id"))
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
                    _prediction_item(row["payload"], row.get("portfolio_context"))
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

    @router.get("/coverage", response_model=None)
    def coverage(lottery_type: LotteryType) -> JsonObject | JSONResponse:
        if store is None:
            return _error(503, "REPLAY_BACKFILL_NOT_CONFIGURED")
        try:
            result = store.backfill_coverage(lottery_type.value)
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
        except Exception:
            return _error(503, "REPLAY_BACKFILL_UNAVAILABLE")

    # Retained for existing local consumers; all routes remain GET-only.
    @router.get("/results", response_model=None)
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

    @router.get("/runs/{run_id}", response_model=None)
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
    payload: JsonObject, portfolio_context: JsonObject | None = None
) -> JsonObject:
    tickets: object = payload.get("predicted_tickets", [])
    hits: object = payload.get("hit_details", [])
    ticket_values = cast(list[object], tickets) if type(tickets) is list else []
    hit_values = cast(list[object], hits) if type(hits) is list else []
    predicted: list[JsonObject] = []
    for index, raw_ticket in enumerate(ticket_values):
        ticket: JsonObject = cast(JsonObject, raw_ticket) if type(raw_ticket) is dict else {}
        raw_hit = hit_values[index] if index < len(hit_values) else None
        hit: JsonObject = cast(JsonObject, raw_hit) if type(raw_hit) is dict else {}
        position: object = ticket.get("ticket_position")
        numbers: object = ticket.get("main_numbers")
        if type(numbers) is not list or any(
            type(n) is not int for n in cast(list[object], numbers)
        ):
            numbers = None
        predicted.append(
            {
                "ticket_position": position if type(position) is int and position > 0 else None,
                "main_numbers": numbers,
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
    context = portfolio_context or {}
    qualification = assess_research_portfolio(
        payload.get("predicted_tickets"), context.get("expected_count"),
        source_bound=context.get("source_bound") is True,
        execution_status=payload.get("execution_status"),
    )
    incomplete_ticket_evidence = type(cast(object, tickets)) is not list or any(
        ticket["ticket_position"] is None or ticket["main_numbers"] is None for ticket in predicted
    )
    return {
        "lottery_type": payload["lottery_type"],
        "strategy_id": payload["strategy_id"],
        "strategy_version": payload["strategy_version"],
        "target_draw_number": payload["target_draw_id"],
        "target_draw_date": payload["target_draw_date"],
        "prediction_status": payload["execution_status"],
        "research_portfolio_qualification": qualification,
        "predicted_tickets": predicted,
        "actual_main_numbers": winning.get("main_numbers", []),
        "actual_special_numbers": (
            [] if winning.get("special_number") is None else [winning["special_number"]]
        ),
        "portfolio_any_prize": (
            None
            if incomplete_ticket_evidence
            else any(ticket.get("prize_tier") for ticket in predicted)
        ),
        "best_main_hits": max(
            (ticket.get("main_hit_count") or 0 for ticket in predicted), default=0
        ) if not incomplete_ticket_evidence else None,
        "source_kind": payload.get("strategy_source", {}).get(
            "source_kind",
            payload.get("strategy_source", {}).get("source", "NATIVE_REPLAY"),
        ),
        "data_status": (
            "ARTIFACT_ONLY"
            if payload["execution_status"] == "ARTIFACT_ONLY"
            else "REBUILDABLE"
        ),
        "training": {
            "training_status": training.get("training_status") or "UNKNOWN",
            "model_version": training.get("model_version"),
            "training_cutoff": training.get("training_cutoff"),
            "training_artifact_id": training.get("training_artifact_id"),
            **{
                key: training[key]
                for key in (
                    "training_cutoff_draw_id",
                    "validation_first_draw_id",
                    "validation_last_draw_id",
                    "validation_draw_count",
                )
                if key in training
            },
        },
    }


def _contract_lifecycle(status: ReplayLifecycleStatus) -> str:
    if status is ReplayLifecycleStatus.UNREGISTERED_IDENTIFIED:
        return "UNREGISTERED"
    if status in {ReplayLifecycleStatus.ARTIFACT_ONLY, ReplayLifecycleStatus.CODE_ONLY,
                  ReplayLifecycleStatus.IDEA, ReplayLifecycleStatus.RETIRED}:
        return "OFFLINE"
    return status.value


def _training_status(item: Any) -> str:
    if item.replay_data_status is ReplayDataStatus.ARTIFACT_ONLY:
        return "HISTORICAL_ARTIFACT"
    if (
        item.strategy_id == "legacy_biglotto__evolution_engine__3df019c31ce4"
        and item.strategy_version in {"v0.2", "v0.3", "v0.4", "v0.5"}
    ):
        return "CAUSAL_FIT_PER_TARGET"
    return "NOT_TRAINABLE"


def _encode(value: JsonObject) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _decode(value: str) -> JsonObject:
    raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    result = json.loads(raw)
    if type(result) is not dict:
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
