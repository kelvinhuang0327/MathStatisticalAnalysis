"""Read-only SQLite queries for the P638 Historical Results V2 extension."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import cast

from lottolab.application.p638_historical import (
    P638_ALLOWED_TARGET_STATUSES,
    P638_LOTTERY_TYPE,
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
from lottolab.infrastructure.persistence.historical_schema import (
    HistoricalSchemaError,
    open_database,
    verify_schema_read_only,
)


class SQLiteP638HistoricalQueryRepository:
    """Explicit-path, read-only implementation of the P638 query port."""

    def __init__(self, database: Path) -> None:
        self._database = database

    def list_runs(self, *, limit: int, offset: int) -> P638RunPage:
        if not _verify_available(self._database):
            return P638RunPage(items=(), total_count=0, limit=limit, offset=offset)
        with _read_only_connection(self._database) as connection:
            total_count = _scalar(
                connection,
                """
                SELECT COUNT(*) FROM historical_result_run
                WHERE lottery_type = ? AND status = 'COMPLETED'
                """,
                (P638_LOTTERY_TYPE,),
            )
            rows = connection.execute(
                """
                SELECT
                    r.id, r.import_identity_sha256, r.manifest_sha256,
                    r.contract_version, r.source_artifact_sha256,
                    r.source_commit_oid, r.started_at, r.completed_at,
                    p.source_run_id, p.source_replay_sha256, p.source_draw_db_sha256,
                    p.source_content_sha256, p.second_zone_ssot_version,
                    p.selected_strategy_count, p.draw_count, p.complete_targets,
                    p.excluded_targets, p.failed_targets, p.ticket_rows,
                    first_draw.draw_number, first_draw.draw_date,
                    last_draw.draw_number, last_draw.draw_date
                FROM historical_result_run AS r
                JOIN historical_p638_run AS p ON p.run_id = r.id
                LEFT JOIN historical_draw_snapshot AS first_draw
                    ON first_draw.id = (
                        SELECT d.id FROM historical_draw_snapshot AS d
                        WHERE d.run_id = r.id AND d.lottery_type = ?
                        ORDER BY d.draw_date ASC, CAST(d.draw_number AS INTEGER) ASC
                        LIMIT 1
                    )
                LEFT JOIN historical_draw_snapshot AS last_draw
                    ON last_draw.id = (
                        SELECT d.id FROM historical_draw_snapshot AS d
                        WHERE d.run_id = r.id AND d.lottery_type = ?
                        ORDER BY d.draw_date DESC, CAST(d.draw_number AS INTEGER) DESC
                        LIMIT 1
                    )
                WHERE r.lottery_type = ? AND r.status = 'COMPLETED'
                ORDER BY r.completed_at DESC, r.id DESC
                LIMIT ? OFFSET ?
                """,
                (
                    P638_LOTTERY_TYPE,
                    P638_LOTTERY_TYPE,
                    P638_LOTTERY_TYPE,
                    limit,
                    offset,
                ),
            ).fetchall()
        return P638RunPage(
            items=tuple(_row_to_run_summary(row) for row in rows),
            total_count=total_count,
            limit=limit,
            offset=offset,
        )

    def list_strategies(self, run_id: str, *, limit: int, offset: int) -> P638StrategyPage | None:
        if not _verify_available(self._database):
            return None
        with _read_only_connection(self._database) as connection:
            if not _run_is_completed(connection, run_id):
                return None
            total_count = _scalar(
                connection,
                """
                SELECT COUNT(*) FROM historical_p638_strategy_ledger AS l
                JOIN historical_result_run AS r ON r.id = l.run_id
                WHERE l.run_id = ? AND l.lottery_type = ? AND r.lottery_type = ?
                """,
                (run_id, P638_LOTTERY_TYPE, P638_LOTTERY_TYPE),
            )
            rows = connection.execute(
                """
                SELECT
                    l.strategy_snapshot_id, l.run_id, l.strategy_id, l.display_label,
                    l.strategy_version, l.executable, l.adapter_path, l.native_ticket_count,
                    l.min_history, l.zone1_contract, l.zone2_contract, l.lifecycle_status,
                    l.replay_status, l.source_run_id, l.source_replay_sha256,
                    l.source_paths_json, l.provenance, l.exclusion_reason,
                    COALESCE(targets.complete_target_count, 0),
                    COALESCE(targets.excluded_target_count, 0),
                    COALESCE(targets.failed_target_count, 0),
                    0,
                    '{}',
                    '{}',
                    targets.first_draw_number, targets.first_draw_date,
                    targets.last_draw_number, targets.last_draw_date
                FROM historical_p638_strategy_ledger AS l
                JOIN historical_result_run AS r ON r.id = l.run_id
                LEFT JOIN (
                    SELECT
                        strategy_snapshot_id,
                        SUM(status = 'COMPLETE') AS complete_target_count,
                        SUM(status IN (
                            'EXCLUDED_INSUFFICIENT_HISTORY',
                            'EXCLUDED_SOURCE_NATIVE_PORTFOLIO_CLOSURE'
                        )) AS excluded_target_count,
                        SUM(status = 'FAILED') AS failed_target_count,
                        MIN(CASE WHEN status IN (
                            'COMPLETE', 'EXCLUDED_INSUFFICIENT_HISTORY',
                            'EXCLUDED_SOURCE_NATIVE_PORTFOLIO_CLOSURE', 'FAILED'
                        )
                            THEN target_draw_number END) AS first_draw_number,
                        MIN(CASE WHEN status IN (
                            'COMPLETE', 'EXCLUDED_INSUFFICIENT_HISTORY',
                            'EXCLUDED_SOURCE_NATIVE_PORTFOLIO_CLOSURE', 'FAILED'
                        )
                            THEN target_draw_date END) AS first_draw_date,
                        MAX(CASE WHEN status IN (
                            'COMPLETE', 'EXCLUDED_INSUFFICIENT_HISTORY',
                            'EXCLUDED_SOURCE_NATIVE_PORTFOLIO_CLOSURE', 'FAILED'
                        )
                            THEN target_draw_number END) AS last_draw_number,
                        MAX(CASE WHEN status IN (
                            'COMPLETE', 'EXCLUDED_INSUFFICIENT_HISTORY',
                            'EXCLUDED_SOURCE_NATIVE_PORTFOLIO_CLOSURE', 'FAILED'
                        )
                            THEN target_draw_date END) AS last_draw_date
                    FROM historical_p638_target
                    WHERE run_id = ?
                    GROUP BY strategy_snapshot_id
                ) AS targets ON targets.strategy_snapshot_id = l.strategy_snapshot_id
                WHERE l.run_id = ? AND l.lottery_type = ? AND r.lottery_type = ?
                ORDER BY l.strategy_id ASC, l.strategy_version ASC
                LIMIT ? OFFSET ?
                """,
                (
                    run_id,
                    run_id,
                    P638_LOTTERY_TYPE,
                    P638_LOTTERY_TYPE,
                    limit,
                    offset,
                ),
            ).fetchall()
            enriched_rows: list[tuple[object, ...]] = []
            for raw_row in rows:
                row = tuple(raw_row)
                ticket_count, zone1_distribution, zone2_distribution = _strategy_ticket_summary(
                    connection,
                    run_id=run_id,
                    strategy_snapshot_id=str(row[0]),
                )
                first_number, first_date, last_number, last_date = _strategy_target_range(
                    connection,
                    run_id=run_id,
                    strategy_snapshot_id=str(row[0]),
                )
                enriched_rows.append(
                    (
                        *row[:21],
                        ticket_count,
                        json.dumps(dict(zone1_distribution), separators=(",", ":")),
                        json.dumps(dict(zone2_distribution), separators=(",", ":")),
                        first_number,
                        first_date,
                        last_number,
                        last_date,
                    )
                )
        return P638StrategyPage(
            run_id=run_id,
            items=tuple(_row_to_strategy(row) for row in enriched_rows),
            total_count=total_count,
            limit=limit,
            offset=offset,
        )

    def list_draws(self, run_id: str, *, limit: int, offset: int) -> P638DrawPage | None:
        if not _verify_available(self._database):
            return None
        with _read_only_connection(self._database) as connection:
            if not _run_is_completed(connection, run_id):
                return None
            total_count = _scalar(
                connection,
                "SELECT COUNT(*) FROM historical_draw_snapshot "
                "WHERE run_id = ? AND lottery_type = ?",
                (run_id, P638_LOTTERY_TYPE),
            )
            rows = connection.execute(
                "SELECT draw_number, draw_date, main_numbers_json, special_numbers_json "
                "FROM historical_draw_snapshot WHERE run_id = ? AND lottery_type = ? "
                "ORDER BY draw_date ASC, CAST(draw_number AS INTEGER) ASC "
                "LIMIT ? OFFSET ?",
                (run_id, P638_LOTTERY_TYPE, limit, offset),
            ).fetchall()
        return P638DrawPage(
            run_id=run_id,
            items=tuple(
                P638DrawRecord(
                    draw_number=str(draw_number),
                    draw_date=str(draw_date),
                    winning_zone1_numbers=_decode_numbers(main_numbers),
                    winning_zone2_number=_decode_numbers(special_numbers)[0],
                )
                for draw_number, draw_date, main_numbers, special_numbers in rows
            ),
            total_count=total_count,
            limit=limit,
            offset=offset,
        )

    def get_draw(self, run_id: str, draw_number: str) -> P638DrawRecord | None:
        if not _verify_available(self._database):
            return None
        with _read_only_connection(self._database) as connection:
            if not _run_is_completed(connection, run_id):
                return None
            row = connection.execute(
                "SELECT draw_number, draw_date, main_numbers_json, special_numbers_json "
                "FROM historical_draw_snapshot WHERE run_id = ? AND lottery_type = ? "
                "AND draw_number = ?",
                (run_id, P638_LOTTERY_TYPE, draw_number),
            ).fetchone()
        if row is None:
            return None
        return P638DrawRecord(
            draw_number=str(row[0]),
            draw_date=str(row[1]),
            winning_zone1_numbers=_decode_numbers(row[2]),
            winning_zone2_number=_decode_numbers(row[3])[0],
        )

    def list_replay(self, run_id: str, query: P638ReplayQuery) -> P638ReplayPage | None:
        if not _verify_available(self._database):
            return None
        with _read_only_connection(self._database) as connection:
            if not _run_is_completed(connection, run_id):
                return None
            predicate, parameters = _target_predicate(run_id, query)
            total_count = _scalar(
                connection,
                f"SELECT COUNT(*) FROM historical_p638_target AS t "
                f"JOIN historical_result_run AS r ON r.id = t.run_id WHERE {predicate}",
                parameters,
            )
            rows = connection.execute(
                f"""
                SELECT
                    t.id, t.run_id, t.strategy_snapshot_id, t.strategy_id,
                    t.strategy_version, t.target_draw_number, t.target_draw_date,
                    t.history_boundary_draw_number, t.history_boundary_date,
                    t.history_length, t.expected_ticket_count, t.status,
                    t.exclusion_reason, t.failure_reason, t.source_target_locator,
                    l.source_run_id, l.source_replay_sha256, l.provenance,
                    d.main_numbers_json, d.special_numbers_json
                FROM historical_p638_target AS t
                JOIN historical_result_run AS r ON r.id = t.run_id
                JOIN historical_p638_strategy_ledger AS l
                    ON l.strategy_snapshot_id = t.strategy_snapshot_id
                JOIN historical_draw_snapshot AS d
                    ON d.id = t.target_draw_snapshot_id
                WHERE {predicate}
                ORDER BY
                    t.target_draw_date ASC,
                    CAST(t.target_draw_number AS INTEGER) ASC,
                    t.strategy_id ASC,
                    t.strategy_version ASC,
                    t.id ASC
                LIMIT ? OFFSET ?
                """,
                (*parameters, query.limit, query.offset),
            ).fetchall()
            records = tuple(_row_to_replay_record(connection, row) for row in rows)
        return P638ReplayPage(
            run_id=run_id,
            items=records,
            total_count=total_count,
            limit=query.limit,
            offset=query.offset,
        )

    def get_target(self, run_id: str, target_id: str) -> P638TargetDetail | None:
        if not _verify_available(self._database):
            return None
        with _read_only_connection(self._database) as connection:
            if not _run_is_completed(connection, run_id):
                return None
            row = connection.execute(
                """
                SELECT
                    t.id, t.run_id, t.strategy_snapshot_id, t.strategy_id,
                    t.strategy_version, t.target_draw_number, t.target_draw_date,
                    t.history_boundary_draw_number, t.history_boundary_date,
                    t.history_length, t.expected_ticket_count, t.status,
                    t.exclusion_reason, t.failure_reason, t.source_target_locator,
                    l.source_run_id, l.source_replay_sha256, l.provenance,
                    d.main_numbers_json, d.special_numbers_json
                FROM historical_p638_target AS t
                JOIN historical_result_run AS r ON r.id = t.run_id
                JOIN historical_p638_strategy_ledger AS l
                    ON l.strategy_snapshot_id = t.strategy_snapshot_id
                JOIN historical_draw_snapshot AS d
                    ON d.id = t.target_draw_snapshot_id
                WHERE t.id = ? AND t.run_id = ?
                  AND r.lottery_type = ? AND d.lottery_type = ?
                """,
                (target_id, run_id, P638_LOTTERY_TYPE, P638_LOTTERY_TYPE),
            ).fetchone()
            if row is None:
                return None
            return _row_to_replay_record(connection, row)

    def get_target_by_identity(
        self, run_id: str, strategy_id: str, strategy_version: str, draw_number: str
    ) -> P638TargetDetail | None:
        if not _verify_available(self._database):
            return None
        with _read_only_connection(self._database) as connection:
            if not _run_is_completed(connection, run_id):
                return None
            row = connection.execute(
                "SELECT id FROM historical_p638_target WHERE run_id = ? "
                "AND strategy_id = ? AND strategy_version = ? AND target_draw_number = ?",
                (run_id, strategy_id, strategy_version, draw_number),
            ).fetchone()
        return None if row is None else self.get_target(run_id, str(row[0]))

    def get_metrics(
        self, run_id: str, *, strategy_id: str | None = None
    ) -> P638StrategyMetrics | None:
        if not _verify_available(self._database):
            return None
        with _read_only_connection(self._database) as connection:
            if not _run_is_completed(connection, run_id):
                return None
            target_predicate = "t.run_id = ? AND r.lottery_type = ?"
            target_parameters: list[object] = [run_id, P638_LOTTERY_TYPE]
            if strategy_id is not None:
                target_predicate += " AND t.strategy_id = ?"
                target_parameters.append(strategy_id)
            target_counts = connection.execute(
                f"""
                SELECT
                    COUNT(*),
                    SUM(t.status = 'COMPLETE'),
                    SUM(t.status IN (
                        'EXCLUDED_INSUFFICIENT_HISTORY',
                        'EXCLUDED_SOURCE_NATIVE_PORTFOLIO_CLOSURE'
                    )),
                    SUM(t.status = 'FAILED'),
                    MIN(CASE WHEN t.status IN {P638_ALLOWED_TARGET_STATUSES!s}
                        THEN t.target_draw_number END),
                    MIN(CASE WHEN t.status IN {P638_ALLOWED_TARGET_STATUSES!s}
                        THEN t.target_draw_date END),
                    MAX(CASE WHEN t.status IN {P638_ALLOWED_TARGET_STATUSES!s}
                        THEN t.target_draw_number END),
                    MAX(CASE WHEN t.status IN {P638_ALLOWED_TARGET_STATUSES!s}
                        THEN t.target_draw_date END)
                FROM historical_p638_target AS t
                JOIN historical_result_run AS r ON r.id = t.run_id
                WHERE {target_predicate}
                """,
                tuple(target_parameters),
            ).fetchone()
            ticket_predicate = "t.run_id = ? AND t.status = 'COMPLETE'"
            ticket_parameters: list[object] = [run_id]
            if strategy_id is not None:
                ticket_predicate += " AND t.strategy_id = ?"
                ticket_parameters.append(strategy_id)
            ticket_count = _scalar(
                connection,
                f"SELECT COUNT(*) FROM historical_p638_ticket AS t WHERE {ticket_predicate}",
                tuple(ticket_parameters),
            )
            combined = _scalar(
                connection,
                f"""
                SELECT COUNT(*) FROM historical_p638_ticket AS t
                WHERE {ticket_predicate} AND t.zone1_hit_count >= 4 AND t.zone2_hit = 1
                """,
                tuple(ticket_parameters),
            )
            zone1_rows = connection.execute(
                f"""
                SELECT zone1_hit_count, COUNT(*)
                FROM historical_p638_ticket AS t
                WHERE {ticket_predicate}
                GROUP BY zone1_hit_count ORDER BY zone1_hit_count ASC
                """,
                tuple(ticket_parameters),
            ).fetchall()
            zone2_rows = connection.execute(
                f"""
                SELECT zone2_hit, COUNT(*)
                FROM historical_p638_ticket AS t
                WHERE {ticket_predicate}
                GROUP BY zone2_hit ORDER BY zone2_hit ASC
                """,
                tuple(ticket_parameters),
            ).fetchall()
            first_number, first_date, last_number, last_date = _metrics_target_range(
                connection,
                predicate=target_predicate,
                parameters=tuple(target_parameters),
            )
        counts = target_counts or (0,) * 8
        return P638StrategyMetrics(
            run_id=run_id,
            strategy_id=strategy_id,
            target_count=_db_int(counts[0] or 0),
            complete_target_count=_db_int(counts[1] or 0),
            excluded_target_count=_db_int(counts[2] or 0),
            failed_target_count=_db_int(counts[3] or 0),
            ticket_count=ticket_count,
            combined_zone1_4plus_zone2_hit_count=combined,
            zone1_hit_distribution=tuple((_db_int(row[0]), _db_int(row[1])) for row in zone1_rows),
            zone2_hit_distribution=tuple((_db_int(row[0]), _db_int(row[1])) for row in zone2_rows),
            first_draw_number=first_number,
            first_draw_date=first_date,
            last_draw_number=last_number,
            last_draw_date=last_date,
        )


def _target_predicate(run_id: str, query: P638ReplayQuery) -> tuple[str, tuple[object, ...]]:
    clauses = [
        "t.run_id = ?",
        "r.lottery_type = ?",
    ]
    parameters: list[object] = [run_id, P638_LOTTERY_TYPE]
    if query.strategy_id is not None:
        clauses.append("t.strategy_id = ?")
        parameters.append(query.strategy_id)
    if query.date_from is not None:
        clauses.append("t.target_draw_date >= ?")
        parameters.append(query.date_from)
    if query.date_to is not None:
        clauses.append("t.target_draw_date <= ?")
        parameters.append(query.date_to)
    if query.status is not None:
        clauses.append("t.status = ?")
        parameters.append(
            {
                "COMPLETE_CAUSAL_REPLAY": "COMPLETE",
                "PRE_ELIGIBILITY": "EXCLUDED_INSUFFICIENT_HISTORY",
                "SOURCE_NATIVE_TYPED_CLOSURE": "EXCLUDED_SOURCE_NATIVE_PORTFOLIO_CLOSURE",
            }.get(query.status, query.status)
        )
    return " AND ".join(clauses), tuple(parameters)


def _row_to_run_summary(row: sqlite3.Row | tuple[object, ...]) -> P638RunSummary:
    (
        run_id,
        import_identity,
        manifest,
        contract,
        _source_replay,
        source_commit,
        started,
        completed,
        source_run,
        source_replay_sha,
        source_draw_sha,
        source_content_sha,
        ssot_version,
        strategy_count,
        draw_count,
        complete_targets,
        excluded_targets,
        failed_targets,
        ticket_count,
        first_number,
        first_date,
        last_number,
        last_date,
    ) = row
    return P638RunSummary(
        run_id=str(run_id),
        import_identity_sha256=str(import_identity),
        manifest_sha256=str(manifest),
        contract_version=str(contract),
        source_run_id=str(source_run),
        source_replay_sha256=str(source_replay_sha),
        source_draw_db_sha256=str(source_draw_sha),
        source_commit_oid=str(source_commit),
        source_content_sha256=str(source_content_sha),
        second_zone_ssot_version=str(ssot_version),
        status="COMPLETED",
        started_at=str(started),
        completed_at=str(completed),
        strategy_count=_db_int(strategy_count),
        draw_count=_db_int(draw_count),
        complete_target_count=_db_int(complete_targets),
        excluded_target_count=_db_int(excluded_targets),
        failed_target_count=_db_int(failed_targets),
        ticket_count=_db_int(ticket_count),
        first_draw_number=str(first_number),
        first_draw_date=str(first_date),
        last_draw_number=str(last_number),
        last_draw_date=str(last_date),
    )


def _strategy_target_range(
    connection: sqlite3.Connection, *, run_id: str, strategy_snapshot_id: str
) -> tuple[str | None, str | None, str | None, str | None]:
    base = """
        FROM historical_p638_target
        WHERE run_id = ? AND strategy_snapshot_id = ?
    """
    first = connection.execute(
        "SELECT target_draw_number, target_draw_date "
        + base
        + " ORDER BY target_draw_date ASC, CAST(target_draw_number AS INTEGER) ASC LIMIT 1",
        (run_id, strategy_snapshot_id),
    ).fetchone()
    last = connection.execute(
        "SELECT target_draw_number, target_draw_date "
        + base
        + " ORDER BY target_draw_date DESC, CAST(target_draw_number AS INTEGER) DESC LIMIT 1",
        (run_id, strategy_snapshot_id),
    ).fetchone()
    return (
        None if first is None else str(first[0]),
        None if first is None else str(first[1]),
        None if last is None else str(last[0]),
        None if last is None else str(last[1]),
    )


def _metrics_target_range(
    connection: sqlite3.Connection,
    *,
    predicate: str,
    parameters: tuple[object, ...],
) -> tuple[str | None, str | None, str | None, str | None]:
    first = connection.execute(
        f"""
        SELECT t.target_draw_number, t.target_draw_date
        FROM historical_p638_target AS t
        JOIN historical_result_run AS r ON r.id = t.run_id
        WHERE {predicate}
        ORDER BY t.target_draw_date ASC, CAST(t.target_draw_number AS INTEGER) ASC
        LIMIT 1
        """,
        parameters,
    ).fetchone()
    last = connection.execute(
        f"""
        SELECT t.target_draw_number, t.target_draw_date
        FROM historical_p638_target AS t
        JOIN historical_result_run AS r ON r.id = t.run_id
        WHERE {predicate}
        ORDER BY t.target_draw_date DESC, CAST(t.target_draw_number AS INTEGER) DESC
        LIMIT 1
        """,
        parameters,
    ).fetchone()
    return (
        None if first is None else str(first[0]),
        None if first is None else str(first[1]),
        None if last is None else str(last[0]),
        None if last is None else str(last[1]),
    )


def _strategy_ticket_summary(
    connection: sqlite3.Connection, *, run_id: str, strategy_snapshot_id: str
) -> tuple[int, tuple[tuple[int, int], ...], tuple[tuple[int, int], ...]]:
    base = """
        FROM historical_p638_ticket AS ticket
        JOIN historical_p638_target AS target ON target.id = ticket.target_id
        WHERE ticket.run_id = ? AND target.run_id = ?
          AND target.strategy_snapshot_id = ? AND ticket.status = 'COMPLETE'
    """
    ticket_count = _scalar(
        connection,
        "SELECT COUNT(*) " + base,
        (run_id, run_id, strategy_snapshot_id),
    )
    zone1_rows = connection.execute(
        "SELECT ticket.zone1_hit_count, COUNT(*) "
        + base
        + " GROUP BY ticket.zone1_hit_count ORDER BY ticket.zone1_hit_count ASC",
        (run_id, run_id, strategy_snapshot_id),
    ).fetchall()
    zone2_rows = connection.execute(
        "SELECT ticket.zone2_hit, COUNT(*) "
        + base
        + " GROUP BY ticket.zone2_hit ORDER BY ticket.zone2_hit ASC",
        (run_id, run_id, strategy_snapshot_id),
    ).fetchall()
    return (
        ticket_count,
        tuple((_db_int(row[0]), _db_int(row[1])) for row in zone1_rows),
        tuple((_db_int(row[0]), _db_int(row[1])) for row in zone2_rows),
    )


def _row_to_strategy(row: sqlite3.Row | tuple[object, ...]) -> P638StrategyRecord:
    (
        snapshot_id,
        run_id,
        strategy_id,
        display_label,
        version,
        executable,
        adapter_path,
        native_count,
        min_history,
        zone1_contract,
        zone2_contract,
        lifecycle,
        replay_status,
        source_run,
        source_replay,
        source_paths_json,
        provenance,
        exclusion_reason,
        complete_targets,
        excluded_targets,
        failed_targets,
        ticket_count,
        zone1_distribution_json,
        zone2_distribution_json,
        first_number,
        first_date,
        last_number,
        last_date,
    ) = row
    return P638StrategyRecord(
        strategy_snapshot_id=str(snapshot_id),
        run_id=str(run_id),
        strategy_id=str(strategy_id),
        display_label=str(display_label),
        strategy_version=str(version),
        executable=bool(executable),
        adapter_path=_optional_text(adapter_path),
        native_ticket_count=_optional_int(native_count),
        min_history=_optional_int(min_history),
        zone1_contract=str(zone1_contract),
        zone2_contract=str(zone2_contract),
        lifecycle_status=str(lifecycle),
        replay_status=str(replay_status),
        source_run_id=_optional_text(source_run),
        source_replay_sha256=_optional_text(source_replay),
        source_paths=_decode_text_tuple(source_paths_json),
        provenance=str(provenance),
        exclusion_reason=_optional_text(exclusion_reason),
        complete_target_count=_db_int(complete_targets or 0),
        excluded_target_count=_db_int(excluded_targets or 0),
        failed_target_count=_db_int(failed_targets or 0),
        ticket_count=_db_int(ticket_count or 0),
        zone1_hit_distribution=_decode_distribution(zone1_distribution_json),
        zone2_hit_distribution=_decode_distribution(zone2_distribution_json),
        first_draw_number=_optional_text(first_number),
        first_draw_date=_optional_text(first_date),
        last_draw_number=_optional_text(last_number),
        last_draw_date=_optional_text(last_date),
    )


def _row_to_replay_record(
    connection: sqlite3.Connection, row: sqlite3.Row | tuple[object, ...]
) -> P638ReplayRecord:
    (
        target_id,
        run_id,
        strategy_snapshot_id,
        strategy_id,
        version,
        target_number,
        target_date,
        boundary_number,
        boundary_date,
        history_length,
        expected_ticket_count,
        status,
        exclusion_reason,
        failure_reason,
        source_locator,
        source_run,
        source_replay,
        provenance,
        actual_zone1_json,
        actual_zone2_json,
    ) = row
    tickets = connection.execute(
        """
        SELECT
            id, ticket_position, predicted_zone1_numbers_json, predicted_zone2_number,
            actual_zone1_numbers_json, actual_zone2_number, zone1_hit_count, zone2_hit,
            status, source_run_id, source_replay_sha256, source_record_locator,
            second_zone_ssot_version, provenance
        FROM historical_p638_ticket
        WHERE target_id = ? AND run_id = ? AND status = 'COMPLETE'
        ORDER BY ticket_position ASC
        """,
        (target_id, run_id),
    ).fetchall()
    return P638ReplayRecord(
        target_id=str(target_id),
        run_id=str(run_id),
        strategy_snapshot_id=str(strategy_snapshot_id),
        strategy_id=str(strategy_id),
        strategy_version=str(version),
        target_draw_number=str(target_number),
        target_draw_date=str(target_date),
        history_boundary_draw_number=_optional_text(boundary_number),
        history_boundary_date=_optional_text(boundary_date),
        history_length=_db_int(history_length),
        expected_ticket_count=_db_int(expected_ticket_count),
        status=str(status),
        exclusion_reason=_optional_text(exclusion_reason),
        failure_reason=_optional_text(failure_reason),
        actual_zone1_numbers=_decode_numbers(actual_zone1_json),
        actual_zone2_number=_decode_numbers(actual_zone2_json)[0],
        source_target_locator=_optional_text(source_locator),
        source_run_id=_optional_text(source_run),
        source_replay_sha256=_optional_text(source_replay),
        provenance=str(provenance),
        tickets=tuple(_row_to_ticket(ticket) for ticket in tickets),
    )


def _row_to_ticket(row: sqlite3.Row | tuple[object, ...]) -> P638TicketRecord:
    (
        ticket_id,
        position,
        predicted_zone1_json,
        predicted_zone2,
        actual_zone1_json,
        actual_zone2,
        zone1_hits,
        zone2_hit,
        status,
        source_run,
        source_replay,
        source_locator,
        ssot_version,
        provenance,
    ) = row
    tier = POWER_LOTTO_PRIZE_RULE_CONTRACT.resolve(
        zone1_hits=_db_int(zone1_hits), zone2_hit=bool(zone2_hit)
    )
    return P638TicketRecord(
        ticket_id=str(ticket_id),
        ticket_position=_db_int(position),
        predicted_zone1_numbers=_decode_numbers(predicted_zone1_json),
        predicted_zone2_number=_db_int(predicted_zone2),
        actual_zone1_numbers=_decode_numbers(actual_zone1_json),
        actual_zone2_number=_db_int(actual_zone2),
        zone1_hit_count=_db_int(zone1_hits),
        zone2_hit=bool(zone2_hit),
        status=str(status),
        source_run_id=str(source_run),
        source_replay_sha256=str(source_replay),
        source_record_locator=_optional_text(source_locator),
        second_zone_ssot_version=str(ssot_version),
        provenance=str(provenance),
        is_winner=tier is not None,
        prize_tier=None if tier is None else tier.tier_id.value,
        prize_tier_order=None if tier is None else tier.tier_order,
        prize_amount=None if tier is None else tier.prize_amount,
    )


def _run_is_completed(connection: sqlite3.Connection, run_id: str) -> bool:
    row = connection.execute(
        """
        SELECT 1 FROM historical_result_run
        WHERE id = ? AND lottery_type = ? AND status = 'COMPLETED'
        """,
        (run_id, P638_LOTTERY_TYPE),
    ).fetchone()
    return row is not None


def _verify_available(database: Path) -> bool:
    try:
        return verify_schema_read_only(database)
    except (HistoricalSchemaError, sqlite3.Error) as exc:
        raise P638HistoricalResultsUnavailableError(
            "historical results storage failed schema verification"
        ) from exc


@contextmanager
def _read_only_connection(database: Path) -> Generator[sqlite3.Connection]:
    try:
        with open_database(database, read_only=True) as connection:
            table_names = {
                str(row[0])
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
            required = {
                "historical_p638_run",
                "historical_p638_strategy_ledger",
                "historical_p638_target",
                "historical_p638_ticket",
            }
            if not required <= table_names:
                raise P638HistoricalResultsUnavailableError(
                    "P638 Historical Results V2 extension is unavailable"
                )
            yield connection
    except P638HistoricalResultsUnavailableError:
        raise
    except (HistoricalSchemaError, sqlite3.Error) as exc:
        raise P638HistoricalResultsUnavailableError(
            "historical results storage is unavailable"
        ) from exc


def _scalar(
    connection: sqlite3.Connection,
    sql: str,
    parameters: tuple[object, ...] = (),
) -> int:
    row = connection.execute(sql, parameters).fetchone()
    if row is None:
        raise P638HistoricalResultsUnavailableError("expected aggregate query result is missing")
    return _db_int(row[0] or 0)


def _decode_numbers(raw: object) -> tuple[int, ...]:
    try:
        value = json.loads(str(raw))
    except (TypeError, ValueError) as exc:
        raise P638HistoricalResultsUnavailableError("stored P638 numbers are malformed") from exc
    if not isinstance(value, list):
        raise P638HistoricalResultsUnavailableError("stored P638 numbers are malformed")
    items = cast(list[object], value)
    if not all(type(item) is int for item in items):
        raise P638HistoricalResultsUnavailableError("stored P638 numbers are malformed")
    return tuple(cast(list[int], items))


def _decode_text_tuple(raw: object) -> tuple[str, ...]:
    try:
        value = json.loads(str(raw))
    except (TypeError, ValueError) as exc:
        raise P638HistoricalResultsUnavailableError(
            "stored P638 source paths are malformed"
        ) from exc
    if not isinstance(value, list):
        raise P638HistoricalResultsUnavailableError("stored P638 source paths are malformed")
    items = cast(list[object], value)
    if not all(type(item) is str for item in items):
        raise P638HistoricalResultsUnavailableError("stored P638 source paths are malformed")
    return tuple(cast(list[str], items))


def _decode_distribution(raw: object) -> tuple[tuple[int, int], ...]:
    try:
        value = json.loads(str(raw))
    except (TypeError, ValueError) as exc:
        raise P638HistoricalResultsUnavailableError(
            "stored P638 hit distribution is malformed"
        ) from exc
    if not isinstance(value, dict):
        raise P638HistoricalResultsUnavailableError("stored P638 hit distribution is malformed")
    items = cast(dict[object, object], value).items()
    if not all(type(key) is str and type(count) is int for key, count in items):
        raise P638HistoricalResultsUnavailableError("stored P638 hit distribution is malformed")
    typed_value = cast(dict[str, int], value)
    return tuple(sorted((_db_int(int(key)), _db_int(count)) for key, count in typed_value.items()))


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)


def _optional_int(value: object) -> int | None:
    return None if value is None else _db_int(value)


def _db_int(value: object) -> int:
    if type(value) is not int:
        raise P638HistoricalResultsUnavailableError("stored P638 integer is malformed")
    return value


__all__ = ["SQLiteP638HistoricalQueryRepository"]
