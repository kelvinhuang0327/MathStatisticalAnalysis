"""Read-only queries for the complete P638 current-base data projection.

The official-prize projection owns strategy, target, ticket, and prize rows.
The paired replay database supplies the complete official draw archive and the
source-native closure reasons. Both paths are opened with SQLite read-only
connections and query-only mode; this adapter never forwards writes or
creates a database.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import cast

from lottolab.application.p638_historical import (
    P638DrawPage,
    P638DrawRecord,
    P638HistoricalResultsUnavailableError,
    P638ReplayPage,
    P638ReplayQuery,
    P638ReplayRecord,
    P638RunPage,
    P638RunSummary,
    P638StrategyMetrics,
    P638StrategyPage,
    P638StrategyRecord,
    P638TargetDetail,
    P638TicketRecord,
)
from lottolab.domain.prize_evaluation import POWER_LOTTO_PRIZE_RULE_CONTRACT
from lottolab.infrastructure.persistence.p638_current_ranking_schema import (
    open_database,
    verify_schema_read_only,
)

_RAW_STATUS_BY_QUERY = {
    "COMPLETE_CAUSAL_REPLAY": "COMPLETE",
    "PRE_ELIGIBILITY": "EXCLUDED_INSUFFICIENT_HISTORY",
    "SOURCE_NATIVE_TYPED_CLOSURE": "EXCLUDED_SOURCE_NATIVE_PORTFOLIO_CLOSURE",
}
_CANONICAL_STATUS = {
    "COMPLETE": "COMPLETE_CAUSAL_REPLAY",
    "EXCLUDED_INSUFFICIENT_HISTORY": "PRE_ELIGIBILITY",
    "EXCLUDED_SOURCE_NATIVE_PORTFOLIO_CLOSURE": "SOURCE_NATIVE_TYPED_CLOSURE",
}


class SQLiteP638BaseDataQueryRepository:
    """Query the complete P638 official-prize projection by exact file paths."""

    def __init__(self, database: Path, replay_database: Path | None = None) -> None:
        self._database = database
        self._replay_database = replay_database

    def list_runs(self, *, limit: int, offset: int) -> P638RunPage:
        self._require_projection()
        with _projection_connection(self._database) as connection:
            total_count = _scalar(connection, "SELECT COUNT(*) FROM p638_current_run")
            rows = connection.execute(
                "SELECT run_id, contract_version, source_replay_db_sha256, "
                "source_draw_db_sha256, strategy_count, draw_count, first_draw_number, "
                "last_draw_number, prize_rule_version, created_at, completed_at "
                "FROM p638_current_run ORDER BY completed_at DESC, run_id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            items = tuple(self._row_to_run(connection, row) for row in rows)
        return P638RunPage(
            items=items,
            total_count=total_count,
            limit=limit,
            offset=offset,
        )

    def list_draws(self, run_id: str, *, limit: int, offset: int) -> P638DrawPage | None:
        self._require_projection()
        with _projection_connection(self._database) as connection:
            if not self._run_exists(connection, run_id):
                return None
        with self._replay_connection() as replay:
            total_count = _scalar(
                replay, "SELECT COUNT(*) FROM draws WHERE run_id = ?", (run_id,)
            )
            rows = replay.execute(
                "SELECT draw_number, draw_date, main_numbers_json, second_number "
                "FROM draws WHERE run_id = ? ORDER BY draw_date ASC, "
                "CAST(draw_number AS INTEGER) ASC LIMIT ? OFFSET ?",
                (run_id, limit, offset),
            ).fetchall()
        return P638DrawPage(
            run_id=run_id,
            items=tuple(_row_to_draw(row) for row in rows),
            total_count=total_count,
            limit=limit,
            offset=offset,
        )

    def get_draw(self, run_id: str, draw_number: str) -> P638DrawRecord | None:
        self._require_projection()
        with _projection_connection(self._database) as connection:
            if not self._run_exists(connection, run_id):
                return None
        with self._replay_connection() as replay:
            row = replay.execute(
                "SELECT draw_number, draw_date, main_numbers_json, second_number "
                "FROM draws WHERE run_id = ? AND draw_number = ?",
                (run_id, draw_number),
            ).fetchone()
        return None if row is None else _row_to_draw(row)

    def list_strategies(self, run_id: str, *, limit: int, offset: int) -> P638StrategyPage | None:
        self._require_projection()
        with _projection_connection(self._database) as connection:
            if not self._run_exists(connection, run_id):
                return None
            total_count = _scalar(
                connection, "SELECT COUNT(*) FROM p638_current_strategy WHERE run_id = ?", (run_id,)
            )
            rows = connection.execute(
                "SELECT strategy_id, strategy_version, native_ticket_count, min_history, "
                "source_paths_json, provenance FROM p638_current_strategy WHERE run_id = ? "
                "ORDER BY strategy_id ASC, strategy_version ASC LIMIT ? OFFSET ?",
                (run_id, limit, offset),
            ).fetchall()
            items = tuple(self._row_to_strategy(connection, run_id, row) for row in rows)
        return P638StrategyPage(
            run_id=run_id,
            items=items,
            total_count=total_count,
            limit=limit,
            offset=offset,
        )

    def list_replay(self, run_id: str, query: P638ReplayQuery) -> P638ReplayPage | None:
        self._require_projection()
        with _projection_connection(self._database) as connection:
            if not self._run_exists(connection, run_id):
                return None
            where = ["run_id = ?"]
            parameters: list[object] = [run_id]
            if query.strategy_id is not None:
                where.append("strategy_id = ?")
                parameters.append(query.strategy_id)
            if query.date_from is not None:
                where.append("target_draw_date >= ?")
                parameters.append(query.date_from)
            if query.date_to is not None:
                where.append("target_draw_date <= ?")
                parameters.append(query.date_to)
            if query.status is not None:
                where.append("status = ?")
                parameters.append(_RAW_STATUS_BY_QUERY.get(query.status, query.status))
            predicate = " AND ".join(where)
            total_count = _scalar(
                connection,
                f"SELECT COUNT(*) FROM p638_current_target WHERE {predicate}",
                tuple(parameters),
            )
            rows = connection.execute(
                f"SELECT id, run_id, strategy_id, strategy_version, target_draw_number, "
                f"target_draw_date, cutoff_draw_number, history_length, expected_ticket_count, "
                f"status, target_is_winner FROM p638_current_target WHERE {predicate} "
                "ORDER BY target_draw_date ASC, CAST(target_draw_number AS INTEGER) ASC, "
                "strategy_id ASC, strategy_version ASC, id ASC LIMIT ? OFFSET ?",
                (*parameters, query.limit, query.offset),
            ).fetchall()
            records = self._records(connection, rows)
        return P638ReplayPage(
            run_id=run_id,
            items=records,
            total_count=total_count,
            limit=query.limit,
            offset=query.offset,
        )

    def get_target(self, run_id: str, target_id: str) -> P638TargetDetail | None:
        self._require_projection()
        with _projection_connection(self._database) as connection:
            row = connection.execute(
                "SELECT id, run_id, strategy_id, strategy_version, target_draw_number, "
                "target_draw_date, cutoff_draw_number, history_length, expected_ticket_count, "
                "status, target_is_winner FROM p638_current_target "
                "WHERE run_id = ? AND id = ?",
                (run_id, target_id),
            ).fetchone()
            if row is None:
                return None
            return self._records(connection, (row,))[0]

    def get_target_by_identity(
        self, run_id: str, strategy_id: str, strategy_version: str, draw_number: str
    ) -> P638TargetDetail | None:
        self._require_projection()
        with _projection_connection(self._database) as connection:
            row = connection.execute(
                "SELECT id FROM p638_current_target WHERE run_id = ? AND strategy_id = ? "
                "AND strategy_version = ? AND target_draw_number = ?",
                (run_id, strategy_id, strategy_version, draw_number),
            ).fetchone()
        return None if row is None else self.get_target(run_id, _text(row[0]))

    def get_metrics(
        self, run_id: str, *, strategy_id: str | None = None
    ) -> P638StrategyMetrics | None:
        self._require_projection()
        with _projection_connection(self._database) as connection:
            if not self._run_exists(connection, run_id):
                return None
            target_where = ["run_id = ?"]
            target_parameters: list[object] = [run_id]
            ticket_where = ["run_id = ?"]
            ticket_parameters: list[object] = [run_id]
            if strategy_id is not None:
                target_where.append("strategy_id = ?")
                target_parameters.append(strategy_id)
                ticket_where.append("strategy_id = ?")
                ticket_parameters.append(strategy_id)
            target_predicate = " AND ".join(target_where)
            ticket_predicate = " AND ".join(ticket_where)
            target_row = connection.execute(
                f"SELECT COUNT(*), SUM(status = 'COMPLETE'), "
                f"SUM(status = 'EXCLUDED_INSUFFICIENT_HISTORY'), "
                f"SUM(status = 'EXCLUDED_SOURCE_NATIVE_PORTFOLIO_CLOSURE'), "
                f"MIN(target_draw_number), MIN(target_draw_date), MAX(target_draw_number), "
                f"MAX(target_draw_date) FROM p638_current_target WHERE {target_predicate}",
                tuple(target_parameters),
            ).fetchone()
            ticket_count = _scalar(
                connection,
                f"SELECT COUNT(*) FROM p638_current_ticket WHERE {ticket_predicate}",
                tuple(ticket_parameters),
            )
            zone1_rows = connection.execute(
                f"SELECT zone1_hit_count, COUNT(*) FROM p638_current_ticket "
                f"WHERE {ticket_predicate} GROUP BY zone1_hit_count ORDER BY zone1_hit_count",
                tuple(ticket_parameters),
            ).fetchall()
            zone2_rows = connection.execute(
                f"SELECT zone2_hit, COUNT(*) FROM p638_current_ticket "
                f"WHERE {ticket_predicate} GROUP BY zone2_hit ORDER BY zone2_hit",
                tuple(ticket_parameters),
            ).fetchall()
            combined = _scalar(
                connection,
                f"SELECT COUNT(*) FROM p638_current_ticket WHERE {ticket_predicate} "
                "AND zone1_hit_count >= 4 AND zone2_hit = 1",
                tuple(ticket_parameters),
            )
        return P638StrategyMetrics(
            run_id=run_id,
            strategy_id=strategy_id,
            target_count=_db_int(target_row[0]),
            complete_target_count=_db_int(target_row[1] or 0),
            excluded_target_count=_db_int(target_row[2] or 0)
            + _db_int(target_row[3] or 0),
            failed_target_count=0,
            ticket_count=ticket_count,
            combined_zone1_4plus_zone2_hit_count=combined,
            zone1_hit_distribution=tuple((_db_int(row[0]), _db_int(row[1])) for row in zone1_rows),
            zone2_hit_distribution=tuple((_db_int(row[0]), _db_int(row[1])) for row in zone2_rows),
            first_draw_number=_optional_text(target_row[4]),
            first_draw_date=_optional_text(target_row[5]),
            last_draw_number=_optional_text(target_row[6]),
            last_draw_date=_optional_text(target_row[7]),
        )

    def _row_to_run(
        self, connection: sqlite3.Connection, row: tuple[object, ...]
    ) -> P638RunSummary:
        (
            run_id,
            contract_version,
            source_replay_sha256,
            source_draw_sha256,
            strategy_count,
            draw_count,
            first_draw_number,
            last_draw_number,
            _prize_rule_version,
            created_at,
            completed_at,
        ) = row
        run_id_text = _text(run_id)
        counts = connection.execute(
            "SELECT SUM(status = 'COMPLETE'), "
            "SUM(status = 'EXCLUDED_INSUFFICIENT_HISTORY'), "
            "SUM(status = 'EXCLUDED_SOURCE_NATIVE_PORTFOLIO_CLOSURE') "
            "FROM p638_current_target WHERE run_id = ?",
            (run_id_text,),
        ).fetchone()
        ticket_count = _scalar(
            connection, "SELECT COUNT(*) FROM p638_current_ticket WHERE run_id = ?", (run_id_text,)
        )
        first = self.get_draw(run_id_text, _text(first_draw_number))
        last = self.get_draw(run_id_text, _text(last_draw_number))
        if first is None or last is None:
            raise P638HistoricalResultsUnavailableError("P638 draw source is unavailable")
        return P638RunSummary(
            run_id=run_id_text,
            import_identity_sha256=_text(source_replay_sha256),
            manifest_sha256=_text(source_draw_sha256),
            contract_version=_text(contract_version),
            source_run_id=run_id_text,
            source_replay_sha256=_text(source_replay_sha256),
            source_draw_db_sha256=_text(source_draw_sha256),
            source_commit_oid="",
            source_content_sha256=_text(source_draw_sha256),
            second_zone_ssot_version="p638-powerlotto-second-zone-v1",
            status="COMPLETED",
            started_at=_text(created_at),
            completed_at=_text(completed_at),
            strategy_count=_db_int(strategy_count),
            draw_count=_db_int(draw_count),
            complete_target_count=_db_int(counts[0] or 0),
            excluded_target_count=_db_int(counts[1] or 0) + _db_int(counts[2] or 0),
            failed_target_count=0,
            ticket_count=ticket_count,
            first_draw_number=_text(first_draw_number),
            first_draw_date=first.draw_date,
            last_draw_number=_text(last_draw_number),
            last_draw_date=last.draw_date,
            is_idempotent_replay=False,
        )

    def _row_to_strategy(
        self, connection: sqlite3.Connection, run_id: str, row: tuple[object, ...]
    ) -> P638StrategyRecord:
        strategy_id, version, native_count, min_history, source_paths, provenance = row
        counts = connection.execute(
            "SELECT SUM(status = 'COMPLETE'), SUM(status = 'EXCLUDED_INSUFFICIENT_HISTORY'), "
            "SUM(status = 'EXCLUDED_SOURCE_NATIVE_PORTFOLIO_CLOSURE'), "
            "MIN(target_draw_number), MIN(target_draw_date), MAX(target_draw_number), "
            "MAX(target_draw_date) FROM p638_current_target WHERE run_id = ? AND strategy_id = ?",
            (run_id, strategy_id),
        ).fetchone()
        ticket_count = _scalar(
            connection,
            "SELECT COUNT(*) FROM p638_current_ticket WHERE run_id = ? AND strategy_id = ?",
            (run_id, strategy_id),
        )
        zone1 = connection.execute(
            "SELECT zone1_hit_count, COUNT(*) FROM p638_current_ticket "
            "WHERE run_id = ? AND strategy_id = ? GROUP BY zone1_hit_count "
            "ORDER BY zone1_hit_count",
            (run_id, strategy_id),
        ).fetchall()
        zone2 = connection.execute(
            "SELECT zone2_hit, COUNT(*) FROM p638_current_ticket "
            "WHERE run_id = ? AND strategy_id = ? GROUP BY zone2_hit ORDER BY zone2_hit",
            (run_id, strategy_id),
        ).fetchall()
        paths_value: object = json.loads(_text(source_paths))
        if not isinstance(paths_value, list):
            raise P638HistoricalResultsUnavailableError("stored P638 source paths are malformed")
        path_items = cast(list[object], paths_value)
        if not all(type(item) is str for item in path_items):
            raise P638HistoricalResultsUnavailableError("stored P638 source paths are malformed")
        return P638StrategyRecord(
            strategy_snapshot_id=f"{run_id}:{strategy_id}:{version}",
            run_id=run_id,
            strategy_id=_text(strategy_id),
            display_label=_text(strategy_id),
            strategy_version=_text(version),
            executable=True,
            adapter_path=None,
            native_ticket_count=_db_int(native_count),
            min_history=_db_int(min_history),
            zone1_contract="6-of-38",
            zone2_contract="1-of-8",
            lifecycle_status="ACTIVE",
            replay_status="COMPLETE",
            source_run_id=run_id,
            source_replay_sha256=None,
            source_paths=tuple(cast(str, item) for item in path_items),
            provenance=_text(provenance),
            exclusion_reason=None,
            complete_target_count=_db_int(counts[0] or 0),
            excluded_target_count=_db_int(counts[1] or 0) + _db_int(counts[2] or 0),
            failed_target_count=0,
            ticket_count=ticket_count,
            zone1_hit_distribution=tuple((_db_int(item[0]), _db_int(item[1])) for item in zone1),
            zone2_hit_distribution=tuple((_db_int(item[0]), _db_int(item[1])) for item in zone2),
            first_draw_number=_optional_text(counts[3]),
            first_draw_date=_optional_text(counts[4]),
            last_draw_number=_optional_text(counts[5]),
            last_draw_date=_optional_text(counts[6]),
        )

    def _records(
        self,
        connection: sqlite3.Connection,
        rows: tuple[tuple[object, ...], ...] | list[tuple[object, ...]],
    ) -> tuple[P638ReplayRecord, ...]:
        needs_replay = any(str(row[9]) != "COMPLETE" for row in rows)
        replay_context = self._replay_connection() if needs_replay else _empty_context()
        with replay_context as replay:
            return tuple(self._row_to_replay(connection, row, replay) for row in rows)

    def _row_to_replay(
        self,
        connection: sqlite3.Connection,
        row: tuple[object, ...],
        replay: sqlite3.Connection | None,
    ) -> P638ReplayRecord:
        (
            target_id,
            run_id,
            strategy_id,
            strategy_version,
            draw_number,
            draw_date,
            cutoff_number,
            history_length,
            expected_count,
            status,
            _target_is_winner,
        ) = row
        run_row = connection.execute(
            "SELECT source_replay_db_sha256, prize_rule_version, prize_rule_provenance "
            "FROM p638_current_run WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        strategy_row = connection.execute(
            "SELECT provenance FROM p638_current_strategy WHERE run_id = ? AND strategy_id = ?",
            (run_id, strategy_id),
        ).fetchone()
        ticket_rows = connection.execute(
            "SELECT id, ticket_position, predicted_zone1_numbers_json, predicted_zone2_number, "
            "actual_zone1_numbers_json, actual_zone2_number, zone1_hit_count, zone2_hit, "
            "is_winner, prize_tier, prize_tier_order "
            "FROM p638_current_ticket WHERE target_id = ? ORDER BY ticket_position ASC",
            (target_id,),
        ).fetchall()
        source_hash = _text(run_row[0])
        ssot_version = "p638-powerlotto-second-zone-v1"
        ticket_provenance = _text(run_row[2])
        tickets = tuple(
            _row_to_ticket(
                ticket,
                run_id=_text(run_id),
                source_hash=source_hash,
                ssot_version=ssot_version,
                provenance=ticket_provenance,
            )
            for ticket in ticket_rows
        )
        actual_zone1 = tickets[0].actual_zone1_numbers if tickets else ()
        actual_zone2 = tickets[0].actual_zone2_number if tickets else 0
        cutoff_date = None
        if cutoff_number is not None and replay is not None:
            cutoff_row = replay.execute(
                "SELECT draw_date FROM draws WHERE run_id = ? AND draw_number = ?",
                (run_id, cutoff_number),
            ).fetchone()
            cutoff_date = None if cutoff_row is None else _text(cutoff_row[0])
        if not tickets:
            if replay is None:
                raise P638HistoricalResultsUnavailableError(
                    "P638 draw source is required for non-complete target details"
                )
            draw_row = replay.execute(
                "SELECT main_numbers_json, second_number FROM draws "
                "WHERE run_id = ? AND draw_number = ?",
                (run_id, draw_number),
            ).fetchone()
            if draw_row is None:
                raise P638HistoricalResultsUnavailableError("P638 draw source is unavailable")
            actual_zone1 = _decode_numbers(draw_row[0])
            actual_zone2 = _db_int(draw_row[1])
        raw_status = _text(status)
        reason_type = _reason_type(raw_status)
        reason = _source_reason(
            replay,
            _text(run_id),
            _text(strategy_id),
            _text(strategy_version),
            _text(draw_number),
        )
        if reason is None and reason_type is not None:
            reason = reason_type
        return P638ReplayRecord(
            target_id=_text(target_id),
            run_id=_text(run_id),
            strategy_snapshot_id=f"{run_id}:{strategy_id}:{strategy_version}",
            strategy_id=_text(strategy_id),
            strategy_version=_text(strategy_version),
            target_draw_number=_text(draw_number),
            target_draw_date=_text(draw_date),
            history_boundary_draw_number=None if cutoff_number is None else _text(cutoff_number),
            history_boundary_date=cutoff_date,
            history_length=_db_int(history_length),
            expected_ticket_count=_db_int(expected_count),
            status=raw_status,
            exclusion_reason=reason if raw_status != "COMPLETE" else None,
            failure_reason=reason if raw_status == "FAILED" else None,
            actual_zone1_numbers=actual_zone1,
            actual_zone2_number=actual_zone2,
            source_target_locator=None,
            source_run_id=_text(run_id),
            source_replay_sha256=source_hash,
            provenance=_text(strategy_row[0]) if strategy_row is not None else ssot_version,
            tickets=tickets,
            reason_type=reason_type,
            reason=reason,
            target_success=None if _target_is_winner is None else bool(_target_is_winner),
        )

    def _run_exists(self, connection: sqlite3.Connection, run_id: str) -> bool:
        return connection.execute(
            "SELECT 1 FROM p638_current_run WHERE run_id = ?", (run_id,)
        ).fetchone() is not None

    def _require_projection(self) -> None:
        try:
            if not verify_schema_read_only(self._database):
                raise P638HistoricalResultsUnavailableError(
                    "P638 current-universe ranking storage is unavailable"
                )
        except (P638HistoricalResultsUnavailableError, sqlite3.Error) as exc:
            if isinstance(exc, P638HistoricalResultsUnavailableError):
                raise
            raise P638HistoricalResultsUnavailableError(
                "P638 current-universe ranking storage is unavailable"
            ) from exc

    @contextmanager
    def _replay_connection(self) -> Generator[sqlite3.Connection]:
        if self._replay_database is None or not self._replay_database.exists():
            raise P638HistoricalResultsUnavailableError("P638 draw source is unavailable")
        uri = f"{self._replay_database.as_uri()}?mode=ro"
        try:
            connection = sqlite3.connect(uri, uri=True, isolation_level=None)
            connection.execute("PRAGMA query_only = ON")
            tables = {
                _text(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            if not {"run_metadata", "draws", "strategy_targets"} <= tables:
                raise P638HistoricalResultsUnavailableError("P638 draw source is unavailable")
        except (OSError, sqlite3.Error) as exc:
            raise P638HistoricalResultsUnavailableError("P638 draw source is unavailable") from exc
        try:
            yield connection
        finally:
            connection.close()


@contextmanager
def _projection_connection(database: Path) -> Generator[sqlite3.Connection]:
    try:
        with open_database(database, read_only=True) as connection:
            yield connection
    except sqlite3.Error as exc:
        raise P638HistoricalResultsUnavailableError(
            "P638 current-universe ranking storage is unavailable"
        ) from exc


@contextmanager
def _empty_context() -> Generator[None]:
    yield None


def _row_to_draw(row: tuple[object, ...]) -> P638DrawRecord:
    return P638DrawRecord(
        draw_number=_text(row[0]),
        draw_date=_text(row[1]),
        winning_zone1_numbers=_decode_numbers(row[2]),
        winning_zone2_number=_db_int(row[3]),
    )


def _row_to_ticket(
    row: tuple[object, ...],
    *,
    run_id: str,
    source_hash: str,
    ssot_version: str,
    provenance: str,
) -> P638TicketRecord:
    (
        ticket_id,
        position,
        predicted_zone1,
        predicted_zone2,
        actual_zone1,
        actual_zone2,
        zone1_hits,
        zone2_hit,
        is_winner,
        prize_tier,
        prize_order,
    ) = row
    tier = POWER_LOTTO_PRIZE_RULE_CONTRACT.resolve(
        zone1_hits=_db_int(zone1_hits), zone2_hit=bool(zone2_hit)
    )
    return P638TicketRecord(
        ticket_id=_text(ticket_id),
        ticket_position=_db_int(position),
        predicted_zone1_numbers=_decode_numbers(predicted_zone1),
        predicted_zone2_number=_db_int(predicted_zone2),
        actual_zone1_numbers=_decode_numbers(actual_zone1),
        actual_zone2_number=_db_int(actual_zone2),
        zone1_hit_count=_db_int(zone1_hits),
        zone2_hit=bool(zone2_hit),
        status="COMPLETE",
        source_run_id=run_id,
        source_replay_sha256=source_hash,
        source_record_locator=None,
        second_zone_ssot_version=ssot_version,
        provenance=provenance,
        is_winner=bool(is_winner),
        prize_tier=None if prize_tier in (None, "") else _text(prize_tier),
        prize_tier_order=None if prize_order is None else _db_int(prize_order),
        prize_amount=None if tier is None else tier.prize_amount,
    )


def _source_reason(
    replay: sqlite3.Connection | None,
    run_id: str,
    strategy_id: str,
    strategy_version: str,
    draw_number: str,
) -> str | None:
    if replay is None:
        return None
    row = replay.execute(
        "SELECT failure_reason FROM strategy_targets WHERE run_id = ? AND strategy_id = ? "
        "AND strategy_version = ? AND target_draw_number = ?",
        (run_id, strategy_id, strategy_version, draw_number),
    ).fetchone()
    return None if row is None or row[0] is None else _text(row[0])


def _reason_type(status: str) -> str | None:
    if status == "EXCLUDED_INSUFFICIENT_HISTORY":
        return "INSUFFICIENT_CAUSAL_HISTORY"
    if status == "EXCLUDED_SOURCE_NATIVE_PORTFOLIO_CLOSURE":
        return "SOURCE_NATIVE_PORTFOLIO_CLOSURE"
    return None


def _decode_numbers(raw: object) -> tuple[int, ...]:
    try:
        value: object = json.loads(_text(raw))
    except (TypeError, ValueError) as exc:
        raise P638HistoricalResultsUnavailableError("stored P638 numbers are malformed") from exc
    if not isinstance(value, list):
        raise P638HistoricalResultsUnavailableError("stored P638 numbers are malformed")
    number_items = cast(list[object], value)
    if not all(type(item) is int for item in number_items):
        raise P638HistoricalResultsUnavailableError("stored P638 numbers are malformed")
    return tuple(cast(int, item) for item in number_items)


def _scalar(
    connection: sqlite3.Connection, sql: str, parameters: tuple[object, ...] = ()
) -> int:
    row = connection.execute(sql, parameters).fetchone()
    if row is None:
        raise P638HistoricalResultsUnavailableError("expected P638 aggregate is missing")
    return _db_int(row[0] or 0)


def _optional_text(value: object) -> str | None:
    return None if value is None else _text(value)


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise P638HistoricalResultsUnavailableError("stored P638 text is malformed")
    return value


def _db_int(value: object) -> int:
    if type(value) is not int:
        raise P638HistoricalResultsUnavailableError("stored P638 integer is malformed")
    return value


__all__ = ["SQLiteP638BaseDataQueryRepository"]
