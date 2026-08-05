"""Read-only SQLite queries for the P638 all-10 official-prize ranking projection.

Distinct from ``p638_historical_repositories.py``: that module reads the
frozen 8-strategy P638 Historical Results V2 database. This module reads the
separate all-10 executable-strategy ranking database built by
``p638_all10_ranking_forwarder.py``.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import cast

from lottolab.application.p638_historical import (
    P638HistoricalResultsUnavailableError,
    P638RankingPage,
    P638RankingRecord,
)
from lottolab.infrastructure.persistence.p638_all10_ranking_schema import (
    P638All10RankingSchemaError,
    open_database,
    verify_schema_read_only,
)

LATEST_RUN_TOKEN = "latest"


class SQLiteP638All10RankingQueryRepository:
    """Explicit-path, read-only implementation of the P638 all-10 ranking query port.

    The all-10 ranking projection is built as one bounded analytical run
    rather than a continuously growing history, so callers may pass the
    reserved ``"latest"`` token instead of an exact ``run_id`` to resolve the
    most recently completed run without a separate discovery endpoint.
    """

    def __init__(self, database: Path) -> None:
        self._database = database

    def list_rankings(self, run_id: str) -> P638RankingPage | None:
        if not _verify_available(self._database):
            return None
        with _read_only_connection(self._database) as connection:
            resolved_run_id = self._resolve_run_id(connection, run_id)
            if resolved_run_id is None:
                return None
            run_id = resolved_run_id
            rows = connection.execute(
                """
                SELECT
                    run_id, rank, strategy_id, strategy_version, native_ticket_count,
                    eligible_target_count, winning_target_count, winning_target_rate,
                    total_complete_ticket_count, winning_ticket_count, ticket_winning_rate,
                    prize_tier_counts_json, highest_prize_tier_achieved, first_eligible_draw,
                    last_eligible_draw, prize_rule_version, prize_rule_provenance, provenance
                FROM p638_all10_ranking
                WHERE run_id = ?
                ORDER BY rank ASC
                """,
                (run_id,),
            ).fetchall()
        return P638RankingPage(run_id=run_id, items=tuple(_row_to_ranking(row) for row in rows))

    @staticmethod
    def _resolve_run_id(connection: sqlite3.Connection, run_id: str) -> str | None:
        if run_id == LATEST_RUN_TOKEN:
            row = connection.execute(
                "SELECT run_id FROM p638_all10_run ORDER BY completed_at DESC, run_id DESC LIMIT 1"
            ).fetchone()
            return None if row is None else str(row[0])
        row = connection.execute(
            "SELECT 1 FROM p638_all10_run WHERE run_id = ?", (run_id,)
        ).fetchone()
        return run_id if row is not None else None


def _row_to_ranking(row: tuple[object, ...]) -> P638RankingRecord:
    (
        run_id,
        rank,
        strategy_id,
        strategy_version,
        native_ticket_count,
        eligible_target_count,
        winning_target_count,
        winning_target_rate,
        total_complete_ticket_count,
        winning_ticket_count,
        ticket_winning_rate,
        prize_tier_counts_json,
        highest_prize_tier_achieved,
        first_eligible_draw,
        last_eligible_draw,
        prize_rule_version,
        prize_rule_provenance,
        provenance,
    ) = row
    return P638RankingRecord(
        run_id=str(run_id),
        rank=_db_int(rank),
        strategy_id=str(strategy_id),
        strategy_version=str(strategy_version),
        native_ticket_count=_db_int(native_ticket_count),
        eligible_target_count=_db_int(eligible_target_count),
        winning_target_count=_db_int(winning_target_count),
        winning_target_rate=_db_float(winning_target_rate),
        total_complete_ticket_count=_db_int(total_complete_ticket_count),
        winning_ticket_count=_db_int(winning_ticket_count),
        ticket_winning_rate=_db_float(ticket_winning_rate),
        prize_tier_counts=_decode_prize_tier_counts(prize_tier_counts_json),
        highest_prize_tier_achieved=(
            None if highest_prize_tier_achieved is None else str(highest_prize_tier_achieved)
        ),
        first_eligible_draw=None if first_eligible_draw is None else str(first_eligible_draw),
        last_eligible_draw=None if last_eligible_draw is None else str(last_eligible_draw),
        prize_rule_version=str(prize_rule_version),
        prize_rule_provenance=str(prize_rule_provenance),
        provenance=str(provenance),
    )


def _decode_prize_tier_counts(raw: object) -> tuple[tuple[str, int], ...]:
    try:
        value = json.loads(str(raw))
    except (TypeError, ValueError) as exc:
        raise P638HistoricalResultsUnavailableError(
            "stored P638 prize tier counts are malformed"
        ) from exc
    if not isinstance(value, dict):
        raise P638HistoricalResultsUnavailableError("stored P638 prize tier counts are malformed")
    raw_items = cast(dict[object, object], value).items()
    if not all(type(key) is str and type(count) is int for key, count in raw_items):
        raise P638HistoricalResultsUnavailableError("stored P638 prize tier counts are malformed")
    typed_value = cast(dict[str, int], value)
    return tuple((key, _db_int(count)) for key, count in typed_value.items())


def _verify_available(database: Path) -> bool:
    try:
        return verify_schema_read_only(database)
    except (P638All10RankingSchemaError, sqlite3.Error) as exc:
        raise P638HistoricalResultsUnavailableError(
            "P638 all-10 ranking storage failed schema verification"
        ) from exc


@contextmanager
def _read_only_connection(database: Path) -> Generator[sqlite3.Connection]:
    try:
        with open_database(database, read_only=True) as connection:
            yield connection
    except (P638All10RankingSchemaError, sqlite3.Error) as exc:
        raise P638HistoricalResultsUnavailableError(
            "P638 all-10 ranking storage is unavailable"
        ) from exc


def _db_int(value: object) -> int:
    if type(value) is not int:
        raise P638HistoricalResultsUnavailableError("stored P638 integer is malformed")
    return value


def _db_float(value: object) -> float:
    if type(value) is not float and type(value) is not int:
        raise P638HistoricalResultsUnavailableError("stored P638 float is malformed")
    return float(value)


__all__ = ["LATEST_RUN_TOKEN", "SQLiteP638All10RankingQueryRepository"]
