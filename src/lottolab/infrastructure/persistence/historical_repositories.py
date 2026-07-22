"""BLHQ R1: whole-run atomic SQLite repository for the historical-results projection.

Persists exactly the values a validated :class:`HistoricalRunImport` already
carries — it computes no canonical hash and parses no raw JSON.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from lottolab.application.historical_queries import (
    HistoricalDrawIdentity,
    HistoricalPortfolioRecord,
    HistoricalReplayPage,
    HistoricalReplayQuery,
    HistoricalResultsUnavailableError,
    HistoricalRunPage,
    HistoricalRunQuery,
    HistoricalRunSummary,
    HistoricalStrategySummary,
    HistoricalStrategySummaryList,
    HistoricalTicketRecord,
)
from lottolab.domain.historical_results import (
    HistoricalImportCommitResult,
    HistoricalRunImport,
    HistoricalRunStatus,
)
from lottolab.infrastructure.persistence.historical_schema import (
    HistoricalSchemaError,
    initialize_schema,
    open_database,
    verify_schema_read_only,
)

TICKET_COUNT_TIERS: tuple[int, ...] = (10, 15, 20)
PERSISTENCE_FAILURE_ERROR_CODE = "HISTORICAL_IMPORT_PERSISTENCE_FAILURE"
_MAX_ERROR_SUMMARY_LENGTH = 500


class HistoricalRepositoryError(RuntimeError):
    """Persistence failed and the failed-audit transaction also failed."""


@dataclass
class _StrategySummaryAccumulator:
    target_draws: set[int] = field(default_factory=lambda: set[int]())
    portfolio_count: int = 0
    m4plus: dict[int, int] = field(default_factory=lambda: dict.fromkeys(TICKET_COUNT_TIERS, 0))


def _default_clock() -> datetime:
    return datetime.now(UTC)


def _default_id_factory() -> str:
    return str(uuid.uuid4())


class SQLiteHistoricalResultRepository:
    """Explicit-path SQLite implementation of ``HistoricalResultRepository``."""

    def __init__(
        self,
        database: Path,
        *,
        clock: Callable[[], datetime] = _default_clock,
        id_factory: Callable[[], str] = _default_id_factory,
    ) -> None:
        self._database = database
        self._clock = clock
        self._id_factory = id_factory

    def commit_import(self, run_import: HistoricalRunImport) -> HistoricalImportCommitResult:
        initialize_schema(self._database)
        with open_database(self._database) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                existing = _find_completed_run(connection, run_import.import_identity_sha256)
                if existing is not None:
                    connection.rollback()
                    return existing
                result = _insert_full_run(
                    connection, run_import, clock=self._clock, id_factory=self._id_factory
                )
                connection.commit()
                return result
            except Exception as original_error:
                if connection.in_transaction:
                    connection.rollback()
                try:
                    return _record_failed_audit(
                        connection,
                        run_import,
                        clock=self._clock,
                        id_factory=self._id_factory,
                        error_summary=str(original_error),
                    )
                except Exception as audit_error:
                    raise HistoricalRepositoryError(
                        f"import failed ({original_error!r}) and the failed-audit transaction "
                        f"also failed ({audit_error!r}); no durable audit row exists"
                    ) from audit_error


def _find_completed_run(
    connection: sqlite3.Connection, import_identity_sha256: str
) -> HistoricalImportCommitResult | None:
    row = connection.execute(
        """
        SELECT id, manifest_sha256, completed_at FROM historical_result_run
        WHERE import_identity_sha256 = ? AND status = 'COMPLETED'
        """,
        (import_identity_sha256,),
    ).fetchone()
    if row is None:
        return None
    run_id, manifest_sha256, completed_at = row
    return HistoricalImportCommitResult(
        run_id=str(run_id),
        status=HistoricalRunStatus.COMPLETED,
        import_identity_sha256=import_identity_sha256,
        manifest_sha256=str(manifest_sha256),
        is_idempotent_replay=True,
        completed_at=str(completed_at),
        error_code=None,
        error_summary=None,
    )


def _insert_full_run(
    connection: sqlite3.Connection,
    run_import: HistoricalRunImport,
    *,
    clock: Callable[[], datetime],
    id_factory: Callable[[], str],
) -> HistoricalImportCommitResult:
    run_id = id_factory()
    started_at = _format_utc(clock())
    connection.execute(
        """
        INSERT INTO historical_result_run (
            id, import_identity_sha256, manifest_sha256, contract_version, source_kind,
            source_repository, source_commit_oid, source_artifact_sha256, dataset_identity,
            dataset_sha256, legacy_run_id, lottery_type, status, started_at, completed_at,
            error_code, error_summary, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'IN_PROGRESS', ?, NULL, NULL, NULL, ?)
        """,
        (
            run_id,
            run_import.import_identity_sha256,
            run_import.manifest_sha256,
            run_import.contract_version,
            run_import.source.source_kind.value,
            run_import.source.source_repository,
            run_import.source.source_commit_oid,
            run_import.source.source_artifact_sha256,
            run_import.dataset.dataset_identity,
            run_import.dataset.dataset_sha256,
            run_import.source.legacy_run_id,
            run_import.dataset.lottery_type.value,
            started_at,
            started_at,
        ),
    )

    strategy_snapshot_ids: dict[tuple[str, str, int], str] = {}
    for descriptor in run_import.strategy_descriptors:
        snapshot_id = id_factory()
        connection.execute(
            """
            INSERT INTO historical_strategy_snapshot (
                id, run_id, strategy_id, effective_strategy_id, strategy_version, replicate,
                identity_kind, governance_status, alias_of_strategy_id, equivalence_group,
                nested_prefix_supported, descriptor_sha256, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                run_id,
                descriptor.strategy_id,
                descriptor.effective_strategy_id,
                descriptor.strategy_version,
                descriptor.replicate,
                descriptor.identity_kind.value,
                descriptor.governance_status.value,
                descriptor.alias_of_strategy_id,
                descriptor.equivalence_group,
                int(descriptor.nested_prefix_supported),
                descriptor.descriptor_sha256,
                started_at,
            ),
        )
        key = (descriptor.strategy_id, descriptor.strategy_version, descriptor.replicate)
        strategy_snapshot_ids[key] = snapshot_id

    draw_snapshot_ids: dict[int, int] = {}
    for draw in run_import.draw_snapshots:
        cursor = connection.execute(
            """
            INSERT INTO historical_draw_snapshot (
                run_id, lottery_type, draw_number, draw_date, main_numbers_json,
                special_numbers_json, draw_sha256, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                run_import.dataset.lottery_type.value,
                str(draw.draw_number),
                draw.draw_date,
                json.dumps(list(draw.main_numbers), separators=(",", ":")),
                json.dumps(list(draw.special_numbers), separators=(",", ":")),
                draw.draw_sha256,
                started_at,
            ),
        )
        row_id = cursor.lastrowid
        if row_id is None:
            raise HistoricalRepositoryError("draw snapshot insert did not return a row id")
        draw_snapshot_ids[draw.draw_number] = row_id

    summary_accumulator: dict[str, _StrategySummaryAccumulator] = {}
    for portfolio in run_import.portfolios:
        strategy_key = (portfolio.strategy_id, portfolio.strategy_version, portfolio.replicate)
        strategy_snapshot_id = strategy_snapshot_ids[strategy_key]
        target_snapshot_id = draw_snapshot_ids[portfolio.target_draw_number]
        cutoff_snapshot_id = draw_snapshot_ids[portfolio.cutoff_draw_number]
        if len(portfolio.tickets) != 20:
            raise HistoricalRepositoryError("a portfolio must carry exactly 20 ordered tickets")

        portfolio_id = id_factory()
        connection.execute(
            """
            INSERT INTO historical_portfolio (
                id, run_id, strategy_snapshot_id, target_draw_snapshot_id, cutoff_draw_snapshot_id,
                constructor_identifier, portfolio_sha256, prefix10_sha256, prefix15_sha256,
                source_record_locator, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                portfolio_id,
                run_id,
                strategy_snapshot_id,
                target_snapshot_id,
                cutoff_snapshot_id,
                portfolio.constructor_identifier,
                portfolio.portfolio_sha256,
                portfolio.prefix10_sha256,
                portfolio.prefix15_sha256,
                portfolio.source_record_locator,
                started_at,
            ),
        )
        for ticket in portfolio.tickets:
            connection.execute(
                """
                INSERT INTO historical_ticket (
                    portfolio_id, portfolio_position, main_numbers_json, special_numbers_json,
                    main_hit_count, special_hit, ticket_sha256, legacy_row_id,
                    legacy_storage_bet_index
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    portfolio_id,
                    ticket.portfolio_position,
                    json.dumps(list(ticket.main_numbers), separators=(",", ":")),
                    json.dumps(list(ticket.special_numbers), separators=(",", ":")),
                    ticket.main_hit_count,
                    int(ticket.special_hit),
                    ticket.ticket_sha256,
                    ticket.legacy_row_id,
                    ticket.legacy_storage_bet_index,
                ),
            )

        stats = summary_accumulator.setdefault(
            strategy_snapshot_id, _StrategySummaryAccumulator()
        )
        stats.target_draws.add(portfolio.target_draw_number)
        stats.portfolio_count += 1
        for tier in TICKET_COUNT_TIERS:
            if any(
                ticket.main_hit_count >= 4
                for ticket in portfolio.tickets
                if ticket.portfolio_position <= tier
            ):
                stats.m4plus[tier] += 1

    for strategy_snapshot_id, stats in summary_accumulator.items():
        evaluated_draws = len(stats.target_draws)
        complete_portfolios = stats.portfolio_count
        for tier in TICKET_COUNT_TIERS:
            connection.execute(
                """
                INSERT INTO historical_count_summary (
                    run_id, strategy_snapshot_id, ticket_count, evaluated_draws,
                    complete_portfolios, m4plus_hit_count, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    strategy_snapshot_id,
                    tier,
                    evaluated_draws,
                    complete_portfolios,
                    stats.m4plus[tier],
                    started_at,
                ),
            )

    completed_at = _format_utc(clock())
    cursor = connection.execute(
        """
        UPDATE historical_result_run
        SET status = 'COMPLETED', completed_at = ?
        WHERE id = ? AND status = 'IN_PROGRESS'
        """,
        (completed_at, run_id),
    )
    if cursor.rowcount != 1:
        raise HistoricalRepositoryError("run completion did not update exactly one row")

    return HistoricalImportCommitResult(
        run_id=run_id,
        status=HistoricalRunStatus.COMPLETED,
        import_identity_sha256=run_import.import_identity_sha256,
        manifest_sha256=run_import.manifest_sha256,
        is_idempotent_replay=False,
        completed_at=completed_at,
        error_code=None,
        error_summary=None,
    )


def _record_failed_audit(
    connection: sqlite3.Connection,
    run_import: HistoricalRunImport,
    *,
    clock: Callable[[], datetime],
    id_factory: Callable[[], str],
    error_summary: str,
) -> HistoricalImportCommitResult:
    run_id = id_factory()
    timestamp = _format_utc(clock())
    truncated_summary = error_summary[:_MAX_ERROR_SUMMARY_LENGTH]
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute(
            """
            INSERT INTO historical_result_run (
                id, import_identity_sha256, manifest_sha256, contract_version, source_kind,
                source_repository, source_commit_oid, source_artifact_sha256, dataset_identity,
                dataset_sha256, legacy_run_id, lottery_type, status, started_at, completed_at,
                error_code, error_summary, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'FAILED', ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                run_import.import_identity_sha256,
                run_import.manifest_sha256,
                run_import.contract_version,
                run_import.source.source_kind.value,
                run_import.source.source_repository,
                run_import.source.source_commit_oid,
                run_import.source.source_artifact_sha256,
                run_import.dataset.dataset_identity,
                run_import.dataset.dataset_sha256,
                run_import.source.legacy_run_id,
                run_import.dataset.lottery_type.value,
                timestamp,
                timestamp,
                PERSISTENCE_FAILURE_ERROR_CODE,
                truncated_summary,
                timestamp,
            ),
        )
    except BaseException:
        connection.rollback()
        raise
    connection.commit()
    return HistoricalImportCommitResult(
        run_id=run_id,
        status=HistoricalRunStatus.FAILED,
        import_identity_sha256=run_import.import_identity_sha256,
        manifest_sha256=run_import.manifest_sha256,
        is_idempotent_replay=False,
        completed_at=timestamp,
        error_code=PERSISTENCE_FAILURE_ERROR_CODE,
        error_summary=truncated_summary,
    )


def _format_utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise ValueError("timestamp must use UTC")
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


class SQLiteHistoricalResultQueryRepository:
    """Explicit-path, read-only SQLite implementation of ``HistoricalResultQueryRepository``.

    Never calls ``initialize_schema`` and never writes. An absent database is
    treated as "no data yet" (see :func:`_verify_available`); an existing but
    corrupt/incompatible database fails closed with
    :class:`HistoricalResultsUnavailableError`.
    """

    def __init__(self, database: Path) -> None:
        self._database = database

    def list_runs(self, query: HistoricalRunQuery) -> HistoricalRunPage:
        if not _verify_available(self._database):
            return HistoricalRunPage(
                items=(), total_count=0, limit=query.limit, offset=query.offset
            )
        with _read_only_connection(self._database) as connection:
            total_count = _scalar(
                connection, "SELECT COUNT(*) FROM historical_result_run WHERE status = 'COMPLETED'"
            )
            rows = connection.execute(
                """
                SELECT id, import_identity_sha256, manifest_sha256, contract_version, source_kind,
                       source_repository, source_commit_oid, source_artifact_sha256,
                       dataset_identity, dataset_sha256, legacy_run_id, lottery_type,
                       started_at, completed_at
                FROM historical_result_run
                WHERE status = 'COMPLETED'
                ORDER BY completed_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (query.limit, query.offset),
            ).fetchall()
        items = tuple(_row_to_run_summary(row) for row in rows)
        return HistoricalRunPage(
            items=items, total_count=total_count, limit=query.limit, offset=query.offset
        )

    def list_strategies(
        self, run_id: str, *, ticket_count: int
    ) -> HistoricalStrategySummaryList | None:
        if not _verify_available(self._database):
            return None
        with _read_only_connection(self._database) as connection:
            if not _run_is_completed(connection, run_id):
                return None
            rows = connection.execute(
                """
                SELECT s.id, s.strategy_id, s.effective_strategy_id, s.strategy_version,
                       s.replicate, s.identity_kind, s.governance_status, s.alias_of_strategy_id,
                       s.equivalence_group, s.nested_prefix_supported,
                       c.evaluated_draws, c.complete_portfolios, c.m4plus_hit_count
                FROM historical_strategy_snapshot s
                JOIN historical_count_summary c
                    ON c.strategy_snapshot_id = s.id AND c.run_id = s.run_id AND c.ticket_count = ?
                WHERE s.run_id = ?
                ORDER BY s.strategy_id ASC, s.strategy_version ASC, s.replicate ASC
                """,
                (ticket_count, run_id),
            ).fetchall()
        items = tuple(_row_to_strategy_summary(row, ticket_count) for row in rows)
        return HistoricalStrategySummaryList(run_id=run_id, ticket_count=ticket_count, items=items)

    def list_replay_portfolios(
        self, run_id: str, query: HistoricalReplayQuery
    ) -> HistoricalReplayPage | None:
        if not _verify_available(self._database):
            return None
        with _read_only_connection(self._database) as connection:
            if not _run_is_completed(connection, run_id):
                return None
            portfolio_rows = connection.execute(
                """
                SELECT p.id, p.run_id, p.strategy_snapshot_id, p.constructor_identifier,
                       p.source_record_locator, p.portfolio_sha256, p.prefix10_sha256,
                       p.prefix15_sha256, s.strategy_id, s.effective_strategy_id,
                       s.strategy_version, s.replicate,
                       td.draw_number, td.draw_date, td.main_numbers_json,
                       td.special_numbers_json, td.draw_sha256,
                       cd.draw_number, cd.draw_date, cd.main_numbers_json,
                       cd.special_numbers_json, cd.draw_sha256
                FROM historical_portfolio p
                JOIN historical_strategy_snapshot s ON s.id = p.strategy_snapshot_id
                JOIN historical_draw_snapshot td ON td.id = p.target_draw_snapshot_id
                JOIN historical_draw_snapshot cd ON cd.id = p.cutoff_draw_snapshot_id
                WHERE p.run_id = ? AND s.strategy_id = ?
                ORDER BY
                    td.draw_date ASC,
                    CAST(td.draw_number AS INTEGER) ASC,
                    s.strategy_id ASC,
                    s.strategy_version ASC,
                    s.replicate ASC,
                    p.id ASC
                """,
                (run_id, query.strategy_id),
            ).fetchall()
            candidates = [
                _row_to_portfolio_record(
                    connection, row, ticket_count=query.ticket_count, run_id=run_id
                )
                for row in portfolio_rows
            ]
        filtered = (
            [item for item in candidates if item.m4plus] if query.m4plus_only else candidates
        )
        total_count = len(filtered)
        page_items = tuple(filtered[query.offset : query.offset + query.limit])
        return HistoricalReplayPage(
            run_id=run_id,
            strategy_id=query.strategy_id,
            ticket_count=query.ticket_count,
            items=page_items,
            total_count=total_count,
            limit=query.limit,
            offset=query.offset,
        )

    def get_portfolio(
        self, portfolio_id: str, *, ticket_count: int
    ) -> HistoricalPortfolioRecord | None:
        if not _verify_available(self._database):
            return None
        with _read_only_connection(self._database) as connection:
            row = connection.execute(
                """
                SELECT p.id, p.run_id, p.strategy_snapshot_id, p.constructor_identifier,
                       p.source_record_locator, p.portfolio_sha256, p.prefix10_sha256,
                       p.prefix15_sha256, s.strategy_id, s.effective_strategy_id,
                       s.strategy_version, s.replicate,
                       td.draw_number, td.draw_date, td.main_numbers_json,
                       td.special_numbers_json, td.draw_sha256,
                       cd.draw_number, cd.draw_date, cd.main_numbers_json,
                       cd.special_numbers_json, cd.draw_sha256,
                       r.status
                FROM historical_portfolio p
                JOIN historical_strategy_snapshot s ON s.id = p.strategy_snapshot_id
                JOIN historical_draw_snapshot td ON td.id = p.target_draw_snapshot_id
                JOIN historical_draw_snapshot cd ON cd.id = p.cutoff_draw_snapshot_id
                JOIN historical_result_run r ON r.id = p.run_id
                WHERE p.id = ?
                """,
                (portfolio_id,),
            ).fetchone()
            if row is None or row[-1] != "COMPLETED":
                return None
            return _row_to_portfolio_record(
                connection, row[:-1], ticket_count=ticket_count, run_id=str(row[1])
            )


def _verify_available(database: Path) -> bool:
    """Return False for an absent database; raise for a corrupt/incompatible one."""

    try:
        return verify_schema_read_only(database)
    except (HistoricalSchemaError, sqlite3.Error) as exc:
        raise HistoricalResultsUnavailableError(
            "historical results storage failed schema verification"
        ) from exc


@contextmanager
def _read_only_connection(database: Path) -> Generator[sqlite3.Connection]:
    try:
        with open_database(database, read_only=True) as connection:
            yield connection
    except (HistoricalSchemaError, sqlite3.Error) as exc:
        raise HistoricalResultsUnavailableError(
            "historical results storage is unavailable"
        ) from exc


def _scalar(connection: sqlite3.Connection, sql: str) -> int:
    row = connection.execute(sql).fetchone()
    if row is None:
        raise HistoricalResultsUnavailableError("expected aggregate query result is missing")
    return int(row[0])


def _run_is_completed(connection: sqlite3.Connection, run_id: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM historical_result_run WHERE id = ? AND status = 'COMPLETED'",
        (run_id,),
    ).fetchone()
    return row is not None


def _decode_int(raw: object) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise HistoricalResultsUnavailableError("stored integer column is malformed")
    return raw


def _decode_numbers(raw: object) -> tuple[int, ...]:
    try:
        parsed: object = json.loads(str(raw))
    except (TypeError, ValueError) as exc:
        raise HistoricalResultsUnavailableError(
            "stored ticket/draw numbers are malformed"
        ) from exc
    if not isinstance(parsed, list):
        raise HistoricalResultsUnavailableError("stored ticket/draw numbers are malformed")
    numbers: list[int] = []
    for item in cast(list[object], parsed):
        numbers.append(_decode_int(item))
    return tuple(numbers)


def _row_to_run_summary(row: sqlite3.Row | tuple[object, ...]) -> HistoricalRunSummary:
    (
        run_id,
        import_identity_sha256,
        manifest_sha256,
        contract_version,
        source_kind,
        source_repository,
        source_commit_oid,
        source_artifact_sha256,
        dataset_identity,
        dataset_sha256,
        legacy_run_id,
        lottery_type,
        started_at,
        completed_at,
    ) = row
    return HistoricalRunSummary(
        run_id=str(run_id),
        import_identity_sha256=str(import_identity_sha256),
        manifest_sha256=str(manifest_sha256),
        contract_version=str(contract_version),
        source_kind=str(source_kind),
        source_repository=str(source_repository),
        source_commit_oid=str(source_commit_oid),
        source_artifact_sha256=str(source_artifact_sha256),
        dataset_identity=str(dataset_identity),
        dataset_sha256=str(dataset_sha256),
        legacy_run_id=None if legacy_run_id is None else str(legacy_run_id),
        lottery_type=str(lottery_type),
        started_at=str(started_at),
        completed_at=str(completed_at),
    )


def _row_to_strategy_summary(
    row: sqlite3.Row | tuple[object, ...], ticket_count: int
) -> HistoricalStrategySummary:
    (
        strategy_snapshot_id,
        strategy_id,
        effective_strategy_id,
        strategy_version,
        replicate,
        identity_kind,
        governance_status,
        alias_of_strategy_id,
        equivalence_group,
        nested_prefix_supported,
        evaluated_draws,
        complete_portfolios,
        m4plus_hit_count,
    ) = row
    return HistoricalStrategySummary(
        strategy_snapshot_id=str(strategy_snapshot_id),
        strategy_id=str(strategy_id),
        effective_strategy_id=str(effective_strategy_id),
        strategy_version=str(strategy_version),
        replicate=_decode_int(replicate),
        identity_kind=str(identity_kind),
        governance_status=str(governance_status),
        alias_of_strategy_id=None if alias_of_strategy_id is None else str(alias_of_strategy_id),
        equivalence_group=None if equivalence_group is None else str(equivalence_group),
        nested_prefix_supported=bool(nested_prefix_supported),
        ticket_count=ticket_count,
        evaluated_draws=_decode_int(evaluated_draws),
        complete_portfolios=_decode_int(complete_portfolios),
        m4plus_hit_count=_decode_int(m4plus_hit_count),
    )


def _row_to_portfolio_record(
    connection: sqlite3.Connection,
    row: sqlite3.Row | tuple[object, ...],
    *,
    ticket_count: int,
    run_id: str,
) -> HistoricalPortfolioRecord:
    (
        portfolio_id,
        _run_id_column,
        strategy_snapshot_id,
        constructor_identifier,
        source_record_locator,
        portfolio_sha256,
        prefix10_sha256,
        prefix15_sha256,
        strategy_id,
        effective_strategy_id,
        strategy_version,
        replicate,
        target_draw_number,
        target_draw_date,
        target_main_numbers_json,
        target_special_numbers_json,
        target_draw_sha256,
        cutoff_draw_number,
        cutoff_draw_date,
        cutoff_main_numbers_json,
        cutoff_special_numbers_json,
        cutoff_draw_sha256,
    ) = row
    ticket_rows = connection.execute(
        """
        SELECT portfolio_position, main_numbers_json, special_numbers_json, main_hit_count,
               special_hit, ticket_sha256, legacy_row_id, legacy_storage_bet_index
        FROM historical_ticket
        WHERE portfolio_id = ? AND portfolio_position <= ?
        ORDER BY portfolio_position ASC
        """,
        (portfolio_id, ticket_count),
    ).fetchall()
    tickets = tuple(_row_to_ticket_record(ticket_row) for ticket_row in ticket_rows)
    m4plus = any(ticket.main_hit_count >= 4 for ticket in tickets)
    return HistoricalPortfolioRecord(
        portfolio_id=str(portfolio_id),
        run_id=run_id,
        strategy_snapshot_id=str(strategy_snapshot_id),
        strategy_id=str(strategy_id),
        effective_strategy_id=str(effective_strategy_id),
        strategy_version=str(strategy_version),
        replicate=_decode_int(replicate),
        constructor_identifier=str(constructor_identifier),
        source_record_locator=(
            None if source_record_locator is None else str(source_record_locator)
        ),
        portfolio_sha256=str(portfolio_sha256),
        prefix10_sha256=str(prefix10_sha256),
        prefix15_sha256=str(prefix15_sha256),
        target_draw=HistoricalDrawIdentity(
            draw_number=str(target_draw_number),
            draw_date=str(target_draw_date),
            main_numbers=_decode_numbers(target_main_numbers_json),
            special_numbers=_decode_numbers(target_special_numbers_json),
            draw_sha256=str(target_draw_sha256),
        ),
        cutoff_draw=HistoricalDrawIdentity(
            draw_number=str(cutoff_draw_number),
            draw_date=str(cutoff_draw_date),
            main_numbers=_decode_numbers(cutoff_main_numbers_json),
            special_numbers=_decode_numbers(cutoff_special_numbers_json),
            draw_sha256=str(cutoff_draw_sha256),
        ),
        requested_ticket_count=ticket_count,
        m4plus=m4plus,
        tickets=tickets,
    )


def _row_to_ticket_record(row: sqlite3.Row | tuple[object, ...]) -> HistoricalTicketRecord:
    (
        portfolio_position,
        main_numbers_json,
        special_numbers_json,
        main_hit_count,
        special_hit,
        ticket_sha256,
        legacy_row_id,
        legacy_storage_bet_index,
    ) = row
    return HistoricalTicketRecord(
        portfolio_position=_decode_int(portfolio_position),
        main_numbers=_decode_numbers(main_numbers_json),
        special_numbers=_decode_numbers(special_numbers_json),
        main_hit_count=_decode_int(main_hit_count),
        special_hit=bool(special_hit),
        ticket_sha256=str(ticket_sha256),
        legacy_row_id=None if legacy_row_id is None else str(legacy_row_id),
        legacy_storage_bet_index=(
            None if legacy_storage_bet_index is None else _decode_int(legacy_storage_bet_index)
        ),
    )
