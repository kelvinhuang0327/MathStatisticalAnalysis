"""Read-only bulk causal history for one lottery type, oldest first.

A dedicated bulk reader distinct from the paginated ``DrawHistoryQuery``
path: live execution needs every real historical draw in one ordered
sequence, not a page. Opens its own short-lived read-only connection and
never mutates the database.
"""

from __future__ import annotations

import json
import sqlite3

from lottolab.domain.draws import LotteryType
from lottolab.infrastructure.persistence.draw_schema import LocalDataPaths
from lottolab.strategies.adapters.base import CausalDrawRow


def read_full_causal_history(
    paths: LocalDataPaths, lottery_type: LotteryType
) -> tuple[CausalDrawRow, ...]:
    connection = sqlite3.connect(f"file:{paths.database}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT draw_number, draw_date, main_numbers_json FROM draws "
            "WHERE lottery_type = ? ORDER BY draw_date ASC, draw_number ASC",
            (lottery_type.value,),
        ).fetchall()
    finally:
        connection.close()
    return tuple(
        CausalDrawRow(draw=draw_number, date=draw_date, numbers=tuple(sorted(json.loads(raw))))
        for draw_number, draw_date, raw in rows
    )


__all__ = ["read_full_causal_history"]
