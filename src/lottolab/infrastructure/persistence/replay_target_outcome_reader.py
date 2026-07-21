"""Read-only SQLite adapter for exact Replay target outcomes."""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from typing import cast

from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_scoring import (
    ReplayTargetOutcome,
    ReplayTargetOutcomeReadReason,
    ReplayTargetOutcomeReadResult,
)
from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataError,
    LocalDataPaths,
    SchemaMigrationError,
    open_database,
    verify_schema_read_only,
)


class ReplayTargetOutcomeStorageError(RuntimeError):
    """A stored row cannot be represented by the target-outcome contract."""


class SQLiteReplayTargetOutcomeReader:
    """Exact, read-only implementation of ``ReplayTargetOutcomeReader``."""

    def __init__(self, paths: LocalDataPaths) -> None:
        self._paths = paths

    def load_target_outcome(
        self,
        lottery_type: LotteryType,
        target_draw_number: str,
    ) -> ReplayTargetOutcomeReadResult:
        try:
            if not verify_schema_read_only(self._paths):
                return ReplayTargetOutcomeReadResult.not_found(
                    ReplayTargetOutcomeReadReason.TARGET_OUTCOME_NOT_FOUND
                )
            with open_database(self._paths, read_only=True) as connection:
                row = connection.execute(
                    """
                    SELECT draw_number, draw_date, main_numbers_json, special_numbers_json
                    FROM draws
                    WHERE lottery_type = ? AND draw_number = ?
                    """,
                    (lottery_type.value, target_draw_number),
                ).fetchone()
            if row is None:
                return ReplayTargetOutcomeReadResult.not_found(
                    ReplayTargetOutcomeReadReason.TARGET_OUTCOME_NOT_FOUND
                )
            return ReplayTargetOutcomeReadResult.found(_decode_outcome(lottery_type, row))
        except (
            LocalDataError,
            ReplayTargetOutcomeStorageError,
            SchemaMigrationError,
            ValueError,
            sqlite3.DatabaseError,
        ):
            return ReplayTargetOutcomeReadResult.not_found(
                ReplayTargetOutcomeReadReason.TARGET_OUTCOME_STORAGE_UNAVAILABLE
            )


def _decode_outcome(
    lottery_type: LotteryType,
    row: tuple[object, ...],
) -> ReplayTargetOutcome:
    draw_number, draw_date_text, main_numbers_json, special_numbers_json = row
    if not isinstance(draw_number, str) or not draw_number:
        raise ReplayTargetOutcomeStorageError("draw_number is invalid")
    if not isinstance(draw_date_text, str):
        raise ReplayTargetOutcomeStorageError("draw_date is not text")
    try:
        draw_date_value = date.fromisoformat(draw_date_text)
    except ValueError as exc:
        raise ReplayTargetOutcomeStorageError("draw_date is invalid") from exc
    main_numbers = _decode_int_list(main_numbers_json, "main_numbers_json")
    special_numbers = _decode_int_list(special_numbers_json, "special_numbers_json")
    if len(special_numbers) != 1:
        raise ReplayTargetOutcomeStorageError(
            "special_numbers_json must decode to exactly one integer"
        )
    return ReplayTargetOutcome.create(
        lottery_type=lottery_type,
        target_draw_number=draw_number,
        target_draw_date=draw_date_value,
        winning_main_numbers=tuple(main_numbers),
        winning_special_number=special_numbers[0],
    )


def _decode_int_list(value: object, label: str) -> list[int]:
    if not isinstance(value, str):
        raise ReplayTargetOutcomeStorageError(f"{label} is not text")
    try:
        decoded = cast(object, json.loads(value))
    except (json.JSONDecodeError, TypeError) as exc:
        raise ReplayTargetOutcomeStorageError(f"{label} is invalid JSON") from exc
    if not isinstance(decoded, list) or any(
        type(item) is not int for item in cast("list[object]", decoded)
    ):
        raise ReplayTargetOutcomeStorageError(f"{label} must decode to integers")
    return cast("list[int]", decoded)


__all__ = ["ReplayTargetOutcomeStorageError", "SQLiteReplayTargetOutcomeReader"]
