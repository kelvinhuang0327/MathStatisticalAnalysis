"""Read-only SQLite implementation of Replay's causal Big Lotto history port.

Ordering contract (load-bearing, mirrors :attr:`lottolab.domain.draws.Draw.sort_key`):
``draw_number`` is stored as TEXT and must never be ordered or compared
lexicographically. Every comparison and ordering here goes through
``draw_date`` first, then ``CAST(draw_number AS INTEGER)`` — never a plain
string comparison of ``draw_number``.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from typing import cast

from lottolab.application.ports import TargetDrawNotFoundError
from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_history import ReplayCausalDrawRow
from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataPaths,
    open_database,
    verify_schema_read_only,
)

_COLUMNS = "draw_number, draw_date, main_numbers_json, special_numbers_json"

_BASE_PREDICATE = """
    lottery_type = ?
    AND (
        draw_date < ?
        OR (draw_date = ? AND CAST(draw_number AS INTEGER) < ?)
    )
"""


class ReplayHistoryStorageError(RuntimeError):
    """A stored draw row cannot be decoded into a Replay domain history row."""


class SQLiteDrawHistoryReader:
    """Read-only causal Big Lotto history reader bound to one local database.

    Implements :class:`lottolab.application.ports.DrawHistoryReader`.
    """

    def __init__(self, paths: LocalDataPaths) -> None:
        self._paths = paths

    def read_causal_history(
        self,
        lottery_type: LotteryType,
        target_draw_number: str,
        *,
        maximum_history_draws: int | None = None,
    ) -> tuple[ReplayCausalDrawRow, ...]:
        if maximum_history_draws is not None and maximum_history_draws <= 0:
            raise ValueError("maximum_history_draws must be positive when provided")

        if verify_schema_read_only(self._paths) is False:
            raise TargetDrawNotFoundError(
                f"no {lottery_type.value} draw matches draw_number={target_draw_number!r}"
            )

        with open_database(self._paths, read_only=True) as connection:
            target_date_text, target_numeric = self._resolve_target(
                connection, lottery_type, target_draw_number
            )
            rows = self._select_rows_before_target(
                connection,
                lottery_type=lottery_type,
                target_date_text=target_date_text,
                target_numeric=target_numeric,
                maximum_history_draws=maximum_history_draws,
            )
        return tuple(_decode_row(row) for row in rows)

    @staticmethod
    def _resolve_target(
        connection: sqlite3.Connection,
        lottery_type: LotteryType,
        target_draw_number: str,
    ) -> tuple[str, int]:
        target = connection.execute(
            "SELECT draw_date, draw_number FROM draws WHERE lottery_type = ? AND draw_number = ?",
            (lottery_type.value, target_draw_number),
        ).fetchone()
        if target is None:
            raise TargetDrawNotFoundError(
                f"no {lottery_type.value} draw matches draw_number={target_draw_number!r}"
            )
        target_date_text, target_number_text = target
        if not isinstance(target_date_text, str):
            raise ReplayHistoryStorageError("draw_date is not text")
        return target_date_text, _numeric_draw_number(target_number_text)

    @staticmethod
    def _select_rows_before_target(
        connection: sqlite3.Connection,
        *,
        lottery_type: LotteryType,
        target_date_text: str,
        target_numeric: int,
        maximum_history_draws: int | None,
    ) -> list[tuple[object, ...]]:
        base_parameters = (
            lottery_type.value,
            target_date_text,
            target_date_text,
            target_numeric,
        )

        if maximum_history_draws is None:
            query = f"""
                SELECT {_COLUMNS}
                FROM draws
                WHERE {_BASE_PREDICATE}
                ORDER BY draw_date ASC, CAST(draw_number AS INTEGER) ASC
            """
            return connection.execute(query, base_parameters).fetchall()

        query = f"""
            SELECT {_COLUMNS}
            FROM (
                SELECT {_COLUMNS}
                FROM draws
                WHERE {_BASE_PREDICATE}
                ORDER BY draw_date DESC, CAST(draw_number AS INTEGER) DESC
                LIMIT ?
            )
            ORDER BY draw_date ASC, CAST(draw_number AS INTEGER) ASC
        """
        return connection.execute(query, (*base_parameters, maximum_history_draws)).fetchall()


def _numeric_draw_number(value: object) -> int:
    if not isinstance(value, str):
        raise ReplayHistoryStorageError("draw_number is not text")
    try:
        return int(value)
    except ValueError as exc:
        raise ReplayHistoryStorageError(f"draw_number is not numeric: {value!r}") from exc


def _decode_row(row: tuple[object, ...]) -> ReplayCausalDrawRow:
    draw_number, draw_date_text, main_numbers_json, special_numbers_json = row
    if not isinstance(draw_number, str) or not draw_number:
        raise ReplayHistoryStorageError("draw_number is invalid")
    if not isinstance(draw_date_text, str):
        raise ReplayHistoryStorageError("draw_date is not text")
    try:
        draw_date_value = date.fromisoformat(draw_date_text)
    except ValueError as exc:
        raise ReplayHistoryStorageError("draw_date is invalid") from exc

    main_numbers = _decode_int_list(main_numbers_json, "main_numbers_json")
    special_numbers = _decode_int_list(special_numbers_json, "special_numbers_json")
    if len(special_numbers) != 1:
        raise ReplayHistoryStorageError(
            "special_numbers_json must decode to exactly one integer for BIG_LOTTO"
        )

    return ReplayCausalDrawRow(
        draw_number=draw_number,
        draw_date=draw_date_value,
        main_numbers=tuple(main_numbers),
        special_number=special_numbers[0],
    )


def _decode_int_list(value: object, label: str) -> list[int]:
    if not isinstance(value, str):
        raise ReplayHistoryStorageError(f"{label} is not text")
    try:
        decoded = cast(object, json.loads(value))
    except (json.JSONDecodeError, TypeError) as exc:
        raise ReplayHistoryStorageError(f"{label} is invalid JSON") from exc
    if not isinstance(decoded, list) or any(
        type(item) is not int for item in cast("list[object]", decoded)
    ):
        raise ReplayHistoryStorageError(f"{label} must decode to a list of integers")
    return cast("list[int]", decoded)


__all__ = ["ReplayHistoryStorageError", "SQLiteDrawHistoryReader"]
