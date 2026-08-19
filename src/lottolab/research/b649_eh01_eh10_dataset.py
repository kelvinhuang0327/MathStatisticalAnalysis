"""Read-only clean B649 chronological history for EH01/EH10 (B649 Track B).

Loads `research_draw_bindings` from the sealed
`BIGLOTTO_CANONICAL_FULL_HISTORY_BASELINE_R4` SQLite authority (read-only,
`PRAGMA query_only`), restricted to `lottery_type='BIG_LOTTO'` and the
superset `draw_data_version='canonical-full-history-2382-draws-v1'` (the
older `canonical-full-history-2157-draws-v1` rows are a verified strict
subset by content -- using the superset alone loses nothing). Excludes the
150 known `DATE_LIKE` contaminant rows (`draw_number == YYYYMMDD(draw_date)`,
a different, non-BigLotto game mislabeled at import time) using the same
clean discriminator already used by the sealed
`REGIME_CHANGE_POINT_CUSUM_B649_V1` cell -- both land on the identical 2,138
draws spanning 2007-03-09..2026-07-31, independently confirming this is the
project's established "clean" B649 eligible history, not a new invention for
this task.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import cast

from lottolab.infrastructure.persistence.research_repository import (
    fetch_research_draw_bindings_for_dataset,
)

DEFAULT_SQLITE_PATH = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/"
    "BIGLOTTO_CANONICAL_FULL_HISTORY_BASELINE_R4/baseline.sqlite"
)
DRAW_DATA_VERSION = "canonical-full-history-2382-draws-v1"
LOTTERY_TYPE = "BIG_LOTTO"


class DatasetAuthorityError(ValueError):
    """The clean B649 history failed a chronology/schema invariant (fail-closed)."""


@dataclass(frozen=True, slots=True)
class CleanB649History:
    """The frozen, ascending-chronological clean B649 eligible history."""

    draw_ids: tuple[int, ...]
    draw_dates: tuple[str, ...]
    main_number_sums: tuple[int, ...]
    source_path: str
    draw_data_version: str
    excluded_date_like_contaminants: int
    row_count: int
    logical_sha256: str


def _parse_main_numbers(main_numbers_json: str, draw_id: int) -> tuple[int, ...]:
    invalid = DatasetAuthorityError(
        f"STOP_CHRONOLOGY_INVALID: invalid main-number row at draw_id {draw_id}"
    )
    raw: object = json.loads(main_numbers_json)
    if not isinstance(raw, list):
        raise invalid
    raw_list = cast(list[object], raw)
    if len(raw_list) != 6 or any(type(value) is not int for value in raw_list):
        raise invalid
    numbers = cast(list[int], raw_list)
    if len(set(numbers)) != 6 or any(not (1 <= value <= 49) for value in numbers):
        raise invalid
    return tuple(numbers)


def load_clean_b649_history(sqlite_path: Path | str = DEFAULT_SQLITE_PATH) -> CleanB649History:
    """Read the sealed baseline read-only and return the frozen clean series.

    Fails closed (``DatasetAuthorityError``) on any duplicate draw identity,
    non-ascending chronology, or invalid main-number row -- never silently
    drops or reorders a row.
    """

    path = Path(sqlite_path)
    if not path.is_file():
        raise DatasetAuthorityError(f"STOP_DATASET_AUTHORITY_UNPINNED: not a file: {path}")

    uri = f"file:{path}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        connection.execute("PRAGMA query_only = ON;")
        rows, total_count = fetch_research_draw_bindings_for_dataset(
            connection,
            lottery_type=LOTTERY_TYPE,
            draw_data_version=DRAW_DATA_VERSION,
        )
    finally:
        connection.close()

    excluded = total_count - len(rows)

    draw_ids: list[int] = []
    draw_dates: list[str] = []
    sums: list[int] = []
    seen_ids: set[int] = set()
    seen_dates: set[str] = set()
    for draw_number_text, draw_date, main_numbers_json in rows:
        draw_id = int(draw_number_text)
        if draw_id in seen_ids:
            raise DatasetAuthorityError(f"STOP_CHRONOLOGY_INVALID: duplicate draw_id {draw_id}")
        if draw_date in seen_dates:
            raise DatasetAuthorityError(f"STOP_CHRONOLOGY_INVALID: duplicate draw_date {draw_date}")
        seen_ids.add(draw_id)
        seen_dates.add(draw_date)

        main_numbers = _parse_main_numbers(main_numbers_json, draw_id)
        draw_ids.append(draw_id)
        draw_dates.append(draw_date)
        sums.append(sum(main_numbers))

    if draw_dates != sorted(draw_dates):
        raise DatasetAuthorityError(
            "STOP_CHRONOLOGY_INVALID: rows are not in ascending draw_date order"
        )
    if not draw_ids:
        raise DatasetAuthorityError("STOP_DATASET_AUTHORITY_UNPINNED: clean history is empty")

    logical_payload = json.dumps(
        {"draw_ids": draw_ids, "draw_dates": draw_dates, "main_number_sums": sums},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    logical_sha256 = sha256(logical_payload).hexdigest()

    return CleanB649History(
        draw_ids=tuple(draw_ids),
        draw_dates=tuple(draw_dates),
        main_number_sums=tuple(sums),
        source_path=str(path),
        draw_data_version=DRAW_DATA_VERSION,
        excluded_date_like_contaminants=excluded,
        row_count=len(draw_ids),
        logical_sha256=logical_sha256,
    )


__all__ = [
    "DEFAULT_SQLITE_PATH",
    "CleanB649History",
    "DatasetAuthorityError",
    "load_clean_b649_history",
]
