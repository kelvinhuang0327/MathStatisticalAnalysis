"""BLHQ R1: whole-run atomic SQLite repository for the historical-results projection.

Persists exactly the values a validated :class:`HistoricalRunImport` already
carries — it computes no canonical hash and parses no raw JSON.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from lottolab.domain.historical_results import (
    HistoricalImportCommitResult,
    HistoricalRunImport,
    HistoricalRunStatus,
)
from lottolab.infrastructure.persistence.historical_schema import initialize_schema, open_database

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
