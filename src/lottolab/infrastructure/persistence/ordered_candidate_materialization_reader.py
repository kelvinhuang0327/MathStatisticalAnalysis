"""One-transaction read-only source snapshot for P336 materialization."""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from typing import cast

from lottolab.domain.draws import LotteryType
from lottolab.domain.ordered_candidate_materialization import (
    OrderedCandidateSourceRow,
    OrderedCandidateSourceSnapshot,
)
from lottolab.evidence.ordered_candidate_emission_package import (
    source_snapshot_sha256,
)
from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataPaths,
    open_database,
)

_SOURCE_COLUMNS = """
    lottery_type,
    draw_date,
    draw_number,
    main_numbers_json,
    special_numbers_json,
    normalized_record_hash
"""


class OrderedCandidateMaterializationStorageError(RuntimeError):
    """Stored source data cannot satisfy the frozen materialization contract."""


class SQLiteOrderedCandidateMaterializationReader:
    """Read every BIG_LOTTO row in one consistent read-only transaction."""

    def __init__(self, paths: LocalDataPaths) -> None:
        self._paths = paths

    def read_source_snapshot(
        self,
        lottery_type: LotteryType,
    ) -> OrderedCandidateSourceSnapshot:
        if lottery_type is not LotteryType.BIG_LOTTO:
            raise ValueError("ordered-candidate materialization is BIG_LOTTO only")

        with open_database(self._paths, read_only=True) as connection:
            if connection.execute("PRAGMA query_only").fetchone() != (1,):
                raise OrderedCandidateMaterializationStorageError(
                    "SQLite query_only mode is unavailable"
                )
            connection.execute("BEGIN")
            try:
                raw_rows = connection.execute(
                    f"""
                    SELECT {_SOURCE_COLUMNS}
                    FROM draws
                    WHERE lottery_type = ?
                    ORDER BY draw_date ASC, CAST(draw_number AS INTEGER) ASC
                    """,
                    (lottery_type.value,),
                ).fetchall()
                rows = tuple(_decode_source_row(row) for row in raw_rows)
                digest = source_snapshot_sha256(rows)
            except BaseException:
                connection.rollback()
                raise
            else:
                connection.commit()

        return OrderedCandidateSourceSnapshot(
            lottery_type=lottery_type,
            rows=rows,
            source_snapshot_sha256=digest,
        )


def _decode_source_row(row: tuple[object, ...] | sqlite3.Row) -> OrderedCandidateSourceRow:
    values = tuple(row)
    if len(values) != 6:
        raise OrderedCandidateMaterializationStorageError(
            "source snapshot row shape is invalid"
        )
    lottery_type_raw, draw_date_raw, draw_number, main_json, special_json, row_hash = (
        values
    )
    try:
        lottery_type = LotteryType(lottery_type_raw)
    except (TypeError, ValueError) as exc:
        raise OrderedCandidateMaterializationStorageError(
            "source lottery_type is invalid"
        ) from exc
    if not isinstance(draw_date_raw, str):
        raise OrderedCandidateMaterializationStorageError(
            "source draw_date is not text"
        )
    try:
        draw_date_value = date.fromisoformat(draw_date_raw)
    except ValueError as exc:
        raise OrderedCandidateMaterializationStorageError(
            "source draw_date is invalid"
        ) from exc
    if not isinstance(draw_number, str):
        raise OrderedCandidateMaterializationStorageError(
            "source draw_number is not text"
        )
    if not isinstance(row_hash, str):
        raise OrderedCandidateMaterializationStorageError(
            "source normalized_record_hash is not text"
        )
    try:
        return OrderedCandidateSourceRow(
            lottery_type=lottery_type,
            draw_date=draw_date_value,
            draw_number=draw_number,
            main_numbers=tuple(_decode_int_list(main_json, "main_numbers_json")),
            special_numbers=tuple(
                _decode_int_list(special_json, "special_numbers_json")
            ),
            normalized_record_hash=row_hash,
        )
    except ValueError as exc:
        raise OrderedCandidateMaterializationStorageError(
            "source row violates the BIG_LOTTO contract"
        ) from exc


def _decode_int_list(value: object, name: str) -> list[int]:
    if not isinstance(value, str):
        raise OrderedCandidateMaterializationStorageError(f"{name} is not text")
    try:
        decoded = cast(object, json.loads(value))
    except (json.JSONDecodeError, TypeError) as exc:
        raise OrderedCandidateMaterializationStorageError(
            f"{name} is invalid JSON"
        ) from exc
    if not isinstance(decoded, list) or any(
        type(item) is not int for item in cast("list[object]", decoded)
    ):
        raise OrderedCandidateMaterializationStorageError(
            f"{name} must decode to exact integers"
        )
    return cast("list[int]", decoded)


__all__ = [
    "OrderedCandidateMaterializationStorageError",
    "SQLiteOrderedCandidateMaterializationReader",
]
