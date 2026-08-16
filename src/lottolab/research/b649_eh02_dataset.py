"""Read-only pinned datasets for EH02 (B649 Track B cross-lottery transfer entropy).

Loads the three series pinned by
`B649_TRACK_B_EH02_DATA_AUTHORITY_AND_PARAMETER_LOCK_RESOLUTION_R1.md`
Sec. 5.1 (SHA-256
76aef07bedb10d51ab0446170c116bf9b5ffee8fc3b5c36ad8e13c14f46daae7):

- B649 (target, Dataset A): reuses `load_clean_b649_history` from
  `b649_eh01_eh10_dataset` unchanged -- the resolution selected the exact
  same `research_draw_bindings` / `EXCLUDE_DATE_LIKE` authority EH01/EH10
  already uses (2,138 rows), so no second implementation is created for the
  same pin.
- T539 (source 1, Dataset B): `source_draws` in `t539_wave1.sqlite3`
  (`T539_WAVE1_CLEAN_REPRODUCTION_AND_PUBLICATION_R2`), 5,930 rows.
- P638 Zone-1 (source 2, Dataset C): `draws` in `p638_wave1.sqlite3`
  (`P638_WAVE1_CLEAN_REPRODUCTION_AND_PUBLICATION_R2`), 1,933 rows, Zone-2
  (`second_number`) never read into any join, hash, or count.

Every loader fails closed (`DatasetAuthorityError`) on a schema, duplicate,
or chronology violation, and reports a `logical_sha256` using the identical
sorted-key-JSON convention as the B649 loader so it can be compared directly
against the resolution artifact's pinned hashes.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import cast

DEFAULT_T539_SQLITE_PATH = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.runs/MathStatisticalAnalysis/"
    "T539_WAVE1_CLEAN_REPRODUCTION_AND_PUBLICATION_R2/t539_wave1.sqlite3"
)
DEFAULT_P638_ZONE1_SQLITE_PATH = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.runs/MathStatisticalAnalysis/"
    "P638_WAVE1_CLEAN_REPRODUCTION_AND_PUBLICATION_R2/p638_wave1.sqlite3"
)
T539_LOTTERY_TYPE = "DAILY_539"
T539_MAIN_COUNT = 5
T539_MAIN_MAX = 39
P638_ZONE1_MAIN_COUNT = 6
P638_ZONE1_MAIN_MAX = 38


class DatasetAuthorityError(ValueError):
    """A pinned EH02 source series failed a schema/chronology invariant (fail-closed)."""


@dataclass(frozen=True, slots=True)
class CleanSeriesHistory:
    """A frozen, ascending-chronological clean series (T539 or P638 Zone-1)."""

    draw_ids: tuple[int, ...]
    draw_dates: tuple[str, ...]
    main_number_sums: tuple[int, ...]
    source_path: str
    row_count: int
    logical_sha256: str


def _logical_sha256(draw_ids: list[int], draw_dates: list[str], sums: list[int]) -> str:
    payload = json.dumps(
        {"draw_ids": draw_ids, "draw_dates": draw_dates, "main_number_sums": sums},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def _parse_main_numbers(
    main_numbers_json: str, draw_id: object, *, count: int, maximum: int
) -> tuple[int, ...]:
    invalid = DatasetAuthorityError(
        f"STOP_CHRONOLOGY_INVALID: invalid main-number row at draw_id {draw_id!r}"
    )
    raw: object = json.loads(main_numbers_json)
    if not isinstance(raw, list):
        raise invalid
    raw_list = cast(list[object], raw)
    if len(raw_list) != count or any(type(value) is not int for value in raw_list):
        raise invalid
    numbers = cast(list[int], raw_list)
    if len(set(numbers)) != count or any(not (1 <= value <= maximum) for value in numbers):
        raise invalid
    return tuple(numbers)


def _assemble(
    rows: list[tuple[str | int, str, str]],
    *,
    path: Path,
    main_count: int,
    main_max: int,
) -> CleanSeriesHistory:
    draw_ids: list[int] = []
    draw_dates: list[str] = []
    sums: list[int] = []
    seen_ids: set[int] = set()
    seen_dates: set[str] = set()
    for draw_id_raw, draw_date, main_numbers_json in rows:
        draw_id = int(draw_id_raw)
        if draw_id in seen_ids:
            raise DatasetAuthorityError(f"STOP_CHRONOLOGY_INVALID: duplicate draw_id {draw_id}")
        if draw_date in seen_dates:
            raise DatasetAuthorityError(
                f"STOP_CHRONOLOGY_INVALID: duplicate draw_date {draw_date}"
            )
        seen_ids.add(draw_id)
        seen_dates.add(draw_date)

        main_numbers = _parse_main_numbers(
            main_numbers_json, draw_id, count=main_count, maximum=main_max
        )
        draw_ids.append(draw_id)
        draw_dates.append(draw_date)
        sums.append(sum(main_numbers))

    if draw_dates != sorted(draw_dates):
        raise DatasetAuthorityError(
            "STOP_CHRONOLOGY_INVALID: rows are not in ascending draw_date order"
        )
    if not draw_ids:
        raise DatasetAuthorityError("STOP_DATASET_AUTHORITY_UNPINNED: series is empty")

    return CleanSeriesHistory(
        draw_ids=tuple(draw_ids),
        draw_dates=tuple(draw_dates),
        main_number_sums=tuple(sums),
        source_path=str(path),
        row_count=len(draw_ids),
        logical_sha256=_logical_sha256(draw_ids, draw_dates, sums),
    )


def load_t539_history(sqlite_path: Path | str = DEFAULT_T539_SQLITE_PATH) -> CleanSeriesHistory:
    """Read `source_draws` (DAILY_539 only) read-only; fails closed on any invariant breach."""

    path = Path(sqlite_path)
    if not path.is_file():
        raise DatasetAuthorityError(f"STOP_DATASET_AUTHORITY_UNPINNED: not a file: {path}")

    uri = f"file:{path}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        connection.execute("PRAGMA query_only = ON;")
        rows = connection.execute(
            """
            SELECT draw_id, draw_date, main_numbers_json
            FROM source_draws
            WHERE lottery_type = ?
            ORDER BY draw_date ASC, CAST(draw_id AS INTEGER) ASC
            """,
            (T539_LOTTERY_TYPE,),
        ).fetchall()
    finally:
        connection.close()

    return _assemble(
        rows, path=path, main_count=T539_MAIN_COUNT, main_max=T539_MAIN_MAX
    )


def load_p638_zone1_history(
    sqlite_path: Path | str = DEFAULT_P638_ZONE1_SQLITE_PATH,
) -> CleanSeriesHistory:
    """Read `draws` (Zone-1 main numbers only) read-only; fails closed on any invariant breach.

    Zone-2 (`second_number`) is never selected -- confirmed unused, matching the
    resolution artifact's explicit `OUT_OF_SCOPE` boundary (Sec. 3).
    """

    path = Path(sqlite_path)
    if not path.is_file():
        raise DatasetAuthorityError(f"STOP_DATASET_AUTHORITY_UNPINNED: not a file: {path}")

    uri = f"file:{path}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        connection.execute("PRAGMA query_only = ON;")
        rows = connection.execute(
            """
            SELECT draw_number, draw_date, main_numbers_json
            FROM draws
            ORDER BY draw_date ASC, CAST(draw_number AS INTEGER) ASC
            """
        ).fetchall()
    finally:
        connection.close()

    return _assemble(
        rows, path=path, main_count=P638_ZONE1_MAIN_COUNT, main_max=P638_ZONE1_MAIN_MAX
    )


__all__ = [
    "DEFAULT_P638_ZONE1_SQLITE_PATH",
    "DEFAULT_T539_SQLITE_PATH",
    "CleanSeriesHistory",
    "DatasetAuthorityError",
    "load_p638_zone1_history",
    "load_t539_history",
]
