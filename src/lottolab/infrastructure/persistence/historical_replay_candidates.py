"""Candidate-only persistence for the shared historical replay controller.

This module is deliberately explicit about source and candidate paths.  A
candidate is either a safe copy of the sealed source (incremental/reconcile)
or a fresh task-owned projection (full replay).  The sealed source is opened
read-only and is never promoted, replaced, renamed, or modified.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from lottolab.application.use_cases.historical_replay_controller import (
    HistoricalReplayController,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import (
    HistoricalReplayMode,
    HistoricalReplayRequest,
    HistoricalReplayResult,
    ReplayCellStatus,
    ReplayDraw,
    ReplayTargetRecord,
)
from lottolab.infrastructure.persistence.historical_replay_sources import (
    HistoricalReplaySourceError,
)
from lottolab.infrastructure.persistence.historical_schema import (
    HistoricalSchemaError,
    initialize_schema,
    open_database,
)


class HistoricalReplayCandidateError(RuntimeError):
    """A candidate path or candidate write failed a fail-closed check."""


class CandidateConflictError(HistoricalReplayCandidateError):
    """A logical cell already exists with different content."""


class CandidatePathSafetyError(HistoricalReplayCandidateError):
    """Source and candidate paths are not safely separated."""


class InsufficientDiskForCandidateError(HistoricalReplayCandidateError):
    """The candidate build cannot be completed with the available disk space."""


class T539TypedClosureStorageRequired(HistoricalReplayCandidateError):
    """The flat T539 storage contract cannot represent a typed closure."""


@dataclass(frozen=True, slots=True)
class CandidateReplayOutcome:
    """Bounded evidence returned after a candidate write."""

    candidate_database: Path
    source_sha256_before: str
    source_sha256_after: str
    result: HistoricalReplayResult
    records_considered: int
    records_inserted: int
    records_reused: int
    candidate_created: bool


_ALLOWED_MODES = frozenset(
    {
        HistoricalReplayMode.INCREMENTAL_REFRESH,
        HistoricalReplayMode.RECONCILE,
        HistoricalReplayMode.FULL_REPLAY,
    }
)
_MIN_FREE_OVERHEAD = 512 * 1024 * 1024
_T539_TABLES = (
    "run_metadata",
    "source_draws",
    "strategy_coverage",
    "prediction_tickets",
    "prediction_scores",
    "failure_ledger",
    "target_completion",
)
_P638_COPY_TABLES = (
    "historical_result_run",
    "historical_strategy_snapshot",
    "historical_draw_snapshot",
    "historical_p638_run",
    "historical_p638_strategy_ledger",
)


class SQLiteT539CandidatePersistence:
    """Persist T539 controller output into a disposable flat-schema candidate."""

    def __init__(
        self,
        source_database: Path,
        candidate_database: Path,
        *,
        task_root: Path | None = None,
    ) -> None:
        self._source_database = _validate_database_path(source_database, "source")
        self._candidate_database = _validate_database_path(
            candidate_database, "candidate", task_root=task_root
        )
        _require_distinct_paths(self._source_database, self._candidate_database)

    def execute(
        self,
        request: HistoricalReplayRequest,
        controller: HistoricalReplayController,
    ) -> CandidateReplayOutcome:
        if request.lottery_type is not LotteryType.DAILY_539:
            raise HistoricalReplayCandidateError("T539 candidate requires DAILY_539")
        _require_mode(request.mode)
        source_before = _sha256_file(self._source_database)
        result = controller.execute(request)
        records = _records_for_persistence(controller, request, result)
        if any(record.status is ReplayCellStatus.TYPED_CLOSURE for record in records):
            raise T539TypedClosureStorageRequired(
                "the current T539 flat schema has no typed-closure storage contract"
            )
        candidate_created = self._prepare_candidate(request.mode)
        inserted, reused = self._write(request, records)
        source_after = _sha256_file(self._source_database)
        if source_after != source_before:
            raise HistoricalReplayCandidateError("T539 source changed during candidate build")
        return CandidateReplayOutcome(
            candidate_database=self._candidate_database,
            source_sha256_before=source_before,
            source_sha256_after=source_after,
            result=result,
            records_considered=len(records),
            records_inserted=inserted,
            records_reused=reused,
            candidate_created=candidate_created,
        )

    def _prepare_candidate(self, mode: HistoricalReplayMode) -> bool:
        if self._candidate_database.exists():
            if not self._candidate_database.is_file():
                raise CandidatePathSafetyError("candidate path is not a regular file")
            return False
        self._candidate_database.parent.mkdir(parents=True, exist_ok=True)
        _check_disk_for_copy(self._source_database, self._candidate_database)
        if mode is HistoricalReplayMode.FULL_REPLAY:
            _create_t539_fresh_candidate(self._source_database, self._candidate_database)
        else:
            shutil.copy2(self._source_database, self._candidate_database)
        return True

    def _write(
        self,
        request: HistoricalReplayRequest,
        records: tuple[ReplayTargetRecord, ...],
    ) -> tuple[int, int]:
        try:
            connection = sqlite3.connect(
                self._candidate_database, timeout=5, isolation_level=None
            )
        except sqlite3.Error as exc:
            raise HistoricalReplayCandidateError("cannot open T539 candidate") from exc
        try:
            _require_tables(connection, _T539_TABLES, "T539 candidate")
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN IMMEDIATE")
            try:
                run_id = _candidate_t539_run_id(connection)
                if run_id != _source_t539_run_id(self._source_database):
                    raise CandidateConflictError("T539 candidate run identity differs from source")
                _merge_t539_official_draws(connection, request.source.official_draws)
                inserted = 0
                reused = 0
                repair_keys: set[tuple[str, str]] = set()
                if request.mode is HistoricalReplayMode.RECONCILE:
                    repair_keys = {record.cell_key for record in records}
                for record in records:
                    state = _persist_t539_record(
                        connection,
                        run_id=run_id,
                        record=record,
                        allow_repair=record.cell_key in repair_keys,
                    )
                    inserted += state == "inserted"
                    reused += state == "reused"
                _refresh_t539_coverage(connection, run_id)
                connection.commit()
                return inserted, reused
            except BaseException:
                connection.rollback()
                raise
        except sqlite3.Error as exc:
            raise HistoricalReplayCandidateError("T539 candidate write failed") from exc
        finally:
            connection.close()


class SQLiteP638CandidatePersistence:
    """Persist P638 controller output into a disposable V4 candidate."""

    def __init__(
        self,
        source_database: Path,
        candidate_database: Path,
        *,
        task_root: Path | None = None,
    ) -> None:
        self._source_database = _validate_database_path(source_database, "source")
        self._candidate_database = _validate_database_path(
            candidate_database, "candidate", task_root=task_root
        )
        _require_distinct_paths(self._source_database, self._candidate_database)

    def execute(
        self,
        request: HistoricalReplayRequest,
        controller: HistoricalReplayController,
    ) -> CandidateReplayOutcome:
        if request.lottery_type is not LotteryType.POWER_LOTTO:
            raise HistoricalReplayCandidateError("P638 candidate requires POWER_LOTTO")
        _require_mode(request.mode)
        source_before = _sha256_file(self._source_database)
        result = controller.execute(request)
        records = _records_for_persistence(controller, request, result)
        candidate_created = self._prepare_candidate(request.mode)
        inserted, reused = self._write(request, records)
        source_after = _sha256_file(self._source_database)
        if source_after != source_before:
            raise HistoricalReplayCandidateError("P638 source changed during candidate build")
        return CandidateReplayOutcome(
            candidate_database=self._candidate_database,
            source_sha256_before=source_before,
            source_sha256_after=source_after,
            result=result,
            records_considered=len(records),
            records_inserted=inserted,
            records_reused=reused,
            candidate_created=candidate_created,
        )

    def _prepare_candidate(self, mode: HistoricalReplayMode) -> bool:
        if self._candidate_database.exists():
            if not self._candidate_database.is_file():
                raise CandidatePathSafetyError("candidate path is not a regular file")
            _verify_p638_candidate(self._candidate_database)
            return False
        self._candidate_database.parent.mkdir(parents=True, exist_ok=True)
        if mode is HistoricalReplayMode.FULL_REPLAY:
            _check_disk_for_copy(self._source_database, self._candidate_database)
            initialize_schema(self._candidate_database)
            _seed_p638_fresh_candidate(
                self._source_database,
                self._candidate_database,
            )
        else:
            _check_disk_for_copy(self._source_database, self._candidate_database)
            shutil.copy2(self._source_database, self._candidate_database)
            initialize_schema(self._candidate_database)
        _verify_p638_candidate(self._candidate_database)
        return True

    def _write(
        self,
        request: HistoricalReplayRequest,
        records: tuple[ReplayTargetRecord, ...],
    ) -> tuple[int, int]:
        try:
            connection = sqlite3.connect(
                self._candidate_database, timeout=5, isolation_level=None
            )
        except sqlite3.Error as exc:
            raise HistoricalReplayCandidateError("cannot open P638 candidate") from exc
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN IMMEDIATE")
            try:
                run_id = _candidate_p638_run_id(connection)
                if run_id != _source_p638_database_run_id(self._source_database):
                    raise CandidateConflictError("P638 candidate run identity differs from source")
                _merge_p638_official_draws(connection, request.source.official_draws)
                inserted = 0
                reused = 0
                repair_keys: set[tuple[str, str]] = set()
                if request.mode is HistoricalReplayMode.RECONCILE:
                    repair_keys = {record.cell_key for record in records}
                for record in records:
                    state = _persist_p638_record(
                        connection,
                        run_id=run_id,
                        record=record,
                        allow_repair=record.cell_key in repair_keys,
                    )
                    inserted += state == "inserted"
                    reused += state == "reused"
                _refresh_p638_summary(connection, run_id, len(request.strategies))
                connection.commit()
                return inserted, reused
            except BaseException:
                connection.rollback()
                raise
        except sqlite3.Error as exc:
            raise HistoricalReplayCandidateError("P638 candidate write failed") from exc
        finally:
            connection.close()


def _records_for_persistence(
    controller: HistoricalReplayController,
    request: HistoricalReplayRequest,
    result: HistoricalReplayResult,
) -> tuple[ReplayTargetRecord, ...]:
    if request.mode is HistoricalReplayMode.RECONCILE:
        return controller.generate_repair_records(request, result.repair_plan)
    return result.records


def _require_mode(mode: HistoricalReplayMode) -> None:
    if mode not in _ALLOWED_MODES:
        raise HistoricalReplayCandidateError("unsupported historical replay mode")


def _validate_database_path(
    database: Path,
    label: str,
    *,
    task_root: Path | None = None,
) -> Path:
    if not database.is_absolute():
        raise CandidatePathSafetyError(f"{label} database path must be absolute")
    if "\x00" in str(database):
        raise CandidatePathSafetyError(f"{label} database path contains a null byte")
    if any(part.casefold() == "lotterynew" for part in database.parts):
        raise CandidatePathSafetyError("LotteryNew paths are forbidden")
    if "b649" in str(database).casefold():
        raise CandidatePathSafetyError("B649 paths are protected")
    if label == "source" and not database.is_file():
        raise HistoricalReplaySourceError("source database is unavailable")
    resolved = database.resolve(strict=False)
    if task_root is not None and not resolved.is_relative_to(task_root.resolve()):
        raise CandidatePathSafetyError("candidate is outside the task-owned root")
    return resolved


def _check_disk_for_copy(source: Path, candidate: Path) -> None:
    usage = shutil.disk_usage(candidate.parent)
    required = source.stat().st_size + _MIN_FREE_OVERHEAD
    if usage.free < required:
        raise InsufficientDiskForCandidateError(
            f"insufficient free disk for candidate: need {required}, have {usage.free}"
        )


def _require_distinct_paths(source: Path, candidate: Path) -> None:
    if source == candidate:
        raise CandidatePathSafetyError("source and candidate resolve to the same path")


def _sha256_file(database: Path) -> str:
    digest = hashlib.sha256()
    try:
        with database.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise HistoricalReplayCandidateError("cannot hash database") from exc
    return digest.hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _require_tables(
    connection: sqlite3.Connection,
    required: Sequence[str],
    label: str,
) -> None:
    actual = {
        str(row[0])
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    if not set(required) <= actual:
        raise HistoricalReplayCandidateError(f"{label} is missing required tables")


def _create_t539_fresh_candidate(source: Path, candidate: Path) -> None:
    try:
        with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as source_connection:
            _require_tables(source_connection, _T539_TABLES, "T539 source")
            ddl_rows = source_connection.execute(
                "SELECT name, sql FROM sqlite_master WHERE type = 'table' "
                "AND name IN (" + ",".join("?" for _ in _T539_TABLES) + ") ORDER BY name",
                _T539_TABLES,
            ).fetchall()
            if len(ddl_rows) != len(_T539_TABLES) or any(row[1] is None for row in ddl_rows):
                raise HistoricalReplayCandidateError("T539 source DDL is incomplete")
            with sqlite3.connect(candidate) as candidate_connection:
                for _name, ddl in ddl_rows:
                    candidate_connection.execute(str(ddl))
                for table in ("run_metadata", "source_draws", "strategy_coverage"):
                    columns = _table_columns(source_connection, table)
                    placeholders = ",".join("?" for _ in columns)
                    rows = source_connection.execute(
                        f"SELECT {','.join(columns)} FROM {table}"
                    ).fetchall()
                    candidate_connection.executemany(
                        f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})",
                        rows,
                    )
                candidate_connection.commit()
    except sqlite3.Error as exc:
        raise HistoricalReplayCandidateError("cannot create fresh T539 candidate") from exc


def _table_columns(connection: sqlite3.Connection, table: str) -> tuple[str, ...]:
    return tuple(str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})"))


def _candidate_t539_run_id(connection: sqlite3.Connection) -> str:
    rows = connection.execute("SELECT run_id FROM run_metadata ORDER BY run_id").fetchall()
    if len(rows) != 1:
        raise HistoricalReplayCandidateError("T539 candidate must contain exactly one run")
    return str(rows[0][0])


def _source_t539_run_id(database: Path) -> str:
    try:
        with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
            rows = connection.execute("SELECT run_id FROM run_metadata ORDER BY run_id").fetchall()
    except sqlite3.Error as exc:
        raise HistoricalReplayCandidateError("cannot read T539 source run identity") from exc
    if len(rows) != 1:
        raise HistoricalReplayCandidateError("T539 source must contain exactly one run")
    return str(rows[0][0])


def _merge_t539_official_draws(
    connection: sqlite3.Connection, official_draws: Iterable[ReplayDraw]
) -> None:
    for draw in official_draws:
        if draw.lottery_type is not LotteryType.DAILY_539:
            raise HistoricalReplayCandidateError("T539 official draw has wrong lottery type")
        row = connection.execute(
            "SELECT draw_date, main_numbers_json FROM source_draws WHERE draw_id = ?",
            (draw.draw_number,),
        ).fetchone()
        encoded = json.dumps(draw.main_numbers, separators=(",", ":"))
        if row is None:
            next_order = int(
                connection.execute("SELECT COALESCE(MAX(draw_order), -1) + 1 FROM source_draws")
                .fetchone()[0]
            )
            connection.execute(
                "INSERT INTO source_draws VALUES (?, ?, ?, ?, ?)",
                (
                    draw.draw_number,
                    LotteryType.DAILY_539.value,
                    draw.draw_date.isoformat(),
                    encoded,
                    next_order,
                ),
            )
        elif (str(row[0]), str(row[1])) != (draw.draw_date.isoformat(), encoded):
            raise CandidateConflictError("T539 official draw conflicts with candidate")


def _persist_t539_record(
    connection: sqlite3.Connection,
    *,
    run_id: str,
    record: ReplayTargetRecord,
    allow_repair: bool,
) -> str:
    if record.status in (
        ReplayCellStatus.NOT_ELIGIBLE,
        ReplayCellStatus.MISSING,
        ReplayCellStatus.PARTIAL,
    ):
        return "skipped"
    if record.status is ReplayCellStatus.TYPED_CLOSURE:
        raise T539TypedClosureStorageRequired("T539 cannot store typed closure")
    status = "SUCCESS" if record.status is ReplayCellStatus.COMPLETE else "FAILED"
    expected = record.strategy.native_ticket_count
    coverage = connection.execute(
        """
        SELECT native_ticket_count
        FROM strategy_coverage
        WHERE run_id = ? AND strategy_id = ? AND strategy_version = ?
        """,
        (run_id, record.strategy.strategy_id, record.strategy.strategy_version),
    ).fetchone()
    if coverage is None:
        raise CandidateConflictError("T539 strategy identity is absent from candidate coverage")
    if int(coverage[0]) != expected:
        raise CandidateConflictError("T539 native ticket count conflicts with candidate coverage")
    if connection.execute(
        "SELECT 1 FROM source_draws WHERE draw_id = ?", (record.target.draw_number,)
    ).fetchone() is None:
        raise CandidateConflictError("T539 target draw is absent from candidate source draws")
    existing = connection.execute(
        """
        SELECT status, native_ticket_count
        FROM target_completion
        WHERE run_id = ? AND strategy_id = ? AND strategy_version = ? AND target_draw_id = ?
        """,
        (
            run_id,
            record.strategy.strategy_id,
            record.strategy.strategy_version,
            record.target.draw_number,
        ),
    ).fetchone()
    if existing is not None and allow_repair and tuple(existing) != (status, expected):
        _delete_t539_cell(connection, run_id, record)
        existing = None
    elif existing is not None and tuple(existing) != (status, expected):
        raise CandidateConflictError("T539 target content conflicts with candidate")
    if existing is None:
        connection.execute(
            """
            INSERT INTO target_completion
                (run_id, strategy_id, strategy_version, target_draw_id, status, native_ticket_count)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                record.strategy.strategy_id,
                record.strategy.strategy_version,
                record.target.draw_number,
                status,
                expected,
            ),
        )
        state = "inserted"
    else:
        state = "reused"
    try:
        if status == "SUCCESS":
            if len(record.tickets) != expected or len(record.evaluations) != expected:
                raise HistoricalReplayCandidateError("T539 complete record lost native ticket rows")
            _ensure_t539_success_rows(connection, run_id, record)
        else:
            _ensure_t539_failure_rows(connection, run_id, record)
    except CandidateConflictError:
        if not allow_repair:
            raise
        _delete_t539_cell(connection, run_id, record)
        connection.execute(
            """
            INSERT INTO target_completion
                (run_id, strategy_id, strategy_version, target_draw_id, status, native_ticket_count)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                record.strategy.strategy_id,
                record.strategy.strategy_version,
                record.target.draw_number,
                status,
                expected,
            ),
        )
        state = "inserted"
        if status == "SUCCESS":
            _ensure_t539_success_rows(connection, run_id, record)
        else:
            _ensure_t539_failure_rows(connection, run_id, record)
    return state


def _delete_t539_cell(
    connection: sqlite3.Connection, run_id: str, record: ReplayTargetRecord
) -> None:
    key = (
        run_id,
        record.strategy.strategy_id,
        record.strategy.strategy_version,
        record.target.draw_number,
    )
    connection.execute(
        "DELETE FROM prediction_scores WHERE run_id = ? AND strategy_id = ? "
        "AND strategy_version = ? AND target_draw_id = ?",
        key,
    )
    connection.execute(
        "DELETE FROM prediction_tickets WHERE run_id = ? AND strategy_id = ? "
        "AND strategy_version = ? AND target_draw_id = ?",
        key,
    )
    connection.execute(
        "DELETE FROM failure_ledger WHERE run_id = ? AND strategy_id = ? "
        "AND strategy_version = ? AND target_draw_id = ?",
        key,
    )
    connection.execute(
        "DELETE FROM target_completion WHERE run_id = ? AND strategy_id = ? "
        "AND strategy_version = ? AND target_draw_id = ?",
        key,
    )


def _ensure_t539_success_rows(
    connection: sqlite3.Connection, run_id: str, record: ReplayTargetRecord
) -> None:
    cutoff = record.causal_history[-1] if record.causal_history else None
    provenance = json.dumps(
        {
            "controller": "HistoricalReplayController",
            "history_fingerprint": record.history_fingerprint,
            "strategy_fingerprint": record.strategy.fingerprint,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    for ticket, evaluation in zip(record.tickets, record.evaluations, strict=True):
        identity = (
            run_id,
            record.strategy.strategy_id,
            record.strategy.strategy_version,
            record.target.draw_number,
            ticket.ticket_position,
        )
        row = connection.execute(
            """
            SELECT main_numbers_json, hits, execution_status, failure_reason
            FROM prediction_tickets
            WHERE run_id = ? AND strategy_id = ? AND strategy_version = ?
              AND target_draw_id = ? AND ticket_position = ?
            """,
            identity,
        ).fetchone()
        expected_ticket = (
            json.dumps(ticket.main_numbers, separators=(",", ":")),
            evaluation.zone1_hits,
            "SUCCESS",
            None,
        )
        if row is not None and tuple(row) != expected_ticket:
            raise CandidateConflictError("T539 ticket content conflicts with candidate")
        if row is None:
            connection.execute(
                """
                INSERT INTO prediction_tickets (
                    run_id, strategy_id, strategy_version, lottery_type,
                    target_draw_id, target_draw_date, cutoff_draw_id, cutoff_draw_date,
                    native_ticket_count, ticket_position, main_numbers_json, special_number,
                    hits, execution_status, failure_reason, provenance_json, adapter_source_commit
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, 'SUCCESS', NULL, ?, ?)
                """,
                (
                    run_id,
                    record.strategy.strategy_id,
                    record.strategy.strategy_version,
                    LotteryType.DAILY_539.value,
                    record.target.draw_number,
                    record.target.draw_date.isoformat(),
                    None if cutoff is None else cutoff.draw_number,
                    None if cutoff is None else cutoff.draw_date.isoformat(),
                    record.strategy.native_ticket_count,
                    ticket.ticket_position,
                    expected_ticket[0],
                    evaluation.zone1_hits,
                    provenance,
                    record.strategy.fingerprint or "historical-replay-controller",
                ),
            )
        score_row = connection.execute(
            """
            SELECT actual_main_numbers_json, hit_numbers_json, hits, score_version
            FROM prediction_scores
            WHERE run_id = ? AND strategy_id = ? AND strategy_version = ?
              AND target_draw_id = ? AND ticket_position = ?
            """,
            identity,
        ).fetchone()
        hit_numbers = tuple(
            number for number in ticket.main_numbers if number in record.target.main_numbers
        )
        expected_score = (
            json.dumps(record.target.main_numbers, separators=(",", ":")),
            json.dumps(hit_numbers, separators=(",", ":")),
            evaluation.zone1_hits,
            "historical-replay-controller-v1",
        )
        if score_row is not None and tuple(score_row) != expected_score:
            raise CandidateConflictError("T539 score content conflicts with candidate")
        if score_row is None:
            connection.execute(
                """
                INSERT INTO prediction_scores (
                    run_id, strategy_id, strategy_version, target_draw_id, ticket_position,
                    actual_main_numbers_json, hit_numbers_json, hits, score_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (*identity, *expected_score),
            )


def _ensure_t539_failure_rows(
    connection: sqlite3.Connection, run_id: str, record: ReplayTargetRecord
) -> None:
    reason = record.reason or "FAILED_EXECUTION"
    cutoff = record.causal_history[-1] if record.causal_history else None
    provenance = json.dumps(
        {"controller": "HistoricalReplayController", "reason": reason},
        sort_keys=True,
        separators=(",", ":"),
    )
    for position in range(1, record.strategy.native_ticket_count + 1):
        identity = (
            run_id,
            record.strategy.strategy_id,
            record.strategy.strategy_version,
            record.target.draw_number,
            position,
        )
        row = connection.execute(
            """
            SELECT main_numbers_json, hits, execution_status, failure_reason
            FROM prediction_tickets
            WHERE run_id = ? AND strategy_id = ? AND strategy_version = ?
              AND target_draw_id = ? AND ticket_position = ?
            """,
            identity,
        ).fetchone()
        expected = (None, None, "FAILED", reason)
        if row is not None and tuple(row) != expected:
            raise CandidateConflictError("T539 failed ticket conflicts with candidate")
        if row is None:
            connection.execute(
                """
                INSERT INTO prediction_tickets (
                    run_id, strategy_id, strategy_version, lottery_type,
                    target_draw_id, target_draw_date, cutoff_draw_id, cutoff_draw_date,
                    native_ticket_count, ticket_position, main_numbers_json, special_number,
                    hits, execution_status, failure_reason, provenance_json, adapter_source_commit
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, 'FAILED', ?, ?, ?)
                """,
                (
                    run_id,
                    record.strategy.strategy_id,
                    record.strategy.strategy_version,
                    LotteryType.DAILY_539.value,
                    record.target.draw_number,
                    record.target.draw_date.isoformat(),
                    None if cutoff is None else cutoff.draw_number,
                    None if cutoff is None else cutoff.draw_date.isoformat(),
                    record.strategy.native_ticket_count,
                    position,
                    reason,
                    provenance,
                    record.strategy.fingerprint or "historical-replay-controller",
                ),
            )
    failure_identity = (
        run_id,
        record.strategy.strategy_id,
        record.strategy.strategy_version,
        record.target.draw_number,
    )
    failure_row = connection.execute(
        "SELECT failure_code, failure_message, expected_ticket_count FROM failure_ledger "
        "WHERE run_id = ? AND strategy_id = ? AND strategy_version = ? AND target_draw_id = ?",
        failure_identity,
    ).fetchone()
    expected_failure = ("FAILED_EXECUTION", reason, record.strategy.native_ticket_count)
    if failure_row is not None and tuple(failure_row) != expected_failure:
        raise CandidateConflictError("T539 failure ledger conflicts with candidate")
    if failure_row is None:
        connection.execute(
            """
            INSERT INTO failure_ledger (
                run_id, strategy_id, strategy_version, target_draw_id, target_draw_date,
                cutoff_draw_id, failure_code, failure_message, expected_ticket_count,
                provenance_json, adapter_source_commit
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                record.strategy.strategy_id,
                record.strategy.strategy_version,
                record.target.draw_number,
                record.target.draw_date.isoformat(),
                None if cutoff is None else cutoff.draw_number,
                expected_failure[0],
                expected_failure[1],
                expected_failure[2],
                provenance,
                record.strategy.fingerprint or "historical-replay-controller",
            ),
        )


def _refresh_t539_coverage(connection: sqlite3.Connection, run_id: str) -> None:
    rows = connection.execute(
        "SELECT strategy_id, strategy_version, expected_target_draw_count FROM strategy_coverage "
        "WHERE run_id = ?",
        (run_id,),
    ).fetchall()
    for strategy_id, version, expected_count in rows:
        counts = connection.execute(
            """
            SELECT COUNT(*), SUM(status = 'SUCCESS'), SUM(status = 'FAILED')
            FROM target_completion
            WHERE run_id = ? AND strategy_id = ? AND strategy_version = ?
            """,
            (run_id, strategy_id, version),
        ).fetchone()
        processed = int(counts[0] or 0)
        successful = int(counts[1] or 0)
        failed = int(counts[2] or 0)
        status = "COMPLETE" if processed >= int(expected_count) else "IN_PROGRESS"
        connection.execute(
            """
            UPDATE strategy_coverage
            SET processed_target_draw_count = ?, successful_target_draw_count = ?,
                failed_target_draw_count = ?, status = ?
            WHERE run_id = ? AND strategy_id = ? AND strategy_version = ?
            """,
            (processed, successful, failed, status, run_id, strategy_id, version),
        )


def _verify_p638_candidate(database: Path) -> None:
    try:
        with open_database(database, read_only=True) as connection:
            _require_tables(
                connection,
                (
                    "historical_result_run",
                    "historical_draw_snapshot",
                    "historical_p638_run",
                    "historical_p638_strategy_ledger",
                    "historical_p638_target",
                    "historical_p638_ticket",
                ),
                "P638 candidate",
            )
    except (HistoricalSchemaError, sqlite3.Error) as exc:
        raise HistoricalReplayCandidateError("P638 candidate schema is invalid") from exc


def _seed_p638_fresh_candidate(source: Path, candidate: Path) -> None:
    try:
        with open_database(source, read_only=True) as source_connection, sqlite3.connect(
            candidate, timeout=5, isolation_level=None
        ) as candidate_connection:
            candidate_connection.execute("PRAGMA foreign_keys = ON")
            candidate_connection.execute("BEGIN IMMEDIATE")
            try:
                for table in _P638_COPY_TABLES:
                    columns = _table_columns(source_connection, table)
                    rows = source_connection.execute(
                        f"SELECT {','.join(columns)} FROM {table} WHERE run_id = ?"
                        if table != "historical_result_run"
                        else f"SELECT {','.join(columns)} FROM {table} WHERE id = ?",
                        (source_run_id := _source_p638_run_id(source_connection),),
                    ).fetchall()
                    if table == "historical_result_run":
                        rows = source_connection.execute(
                            f"SELECT {','.join(columns)} FROM {table} WHERE id = ?",
                            (source_run_id,),
                        ).fetchall()
                    if rows:
                        placeholders = ",".join("?" for _ in columns)
                        candidate_connection.executemany(
                            f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})",
                            rows,
                        )
                candidate_connection.commit()
            except BaseException:
                candidate_connection.rollback()
                raise
    except (HistoricalSchemaError, sqlite3.Error) as exc:
        raise HistoricalReplayCandidateError("cannot seed fresh P638 candidate") from exc


def _source_p638_run_id(connection: sqlite3.Connection) -> str:
    row = connection.execute(
        "SELECT run_id FROM historical_p638_run ORDER BY run_id LIMIT 1"
    ).fetchone()
    if row is None:
        raise HistoricalReplayCandidateError("P638 source has no replay run")
    return str(row[0])


def _candidate_p638_run_id(connection: sqlite3.Connection) -> str:
    row = connection.execute("SELECT run_id FROM historical_p638_run LIMIT 1").fetchone()
    if row is None:
        raise HistoricalReplayCandidateError("P638 candidate has no replay run")
    return str(row[0])


def _source_p638_database_run_id(database: Path) -> str:
    try:
        with open_database(database, read_only=True) as connection:
            row = connection.execute(
                "SELECT run_id FROM historical_p638_run ORDER BY run_id LIMIT 1"
            ).fetchone()
    except (HistoricalSchemaError, sqlite3.Error) as exc:
        raise HistoricalReplayCandidateError("cannot read P638 source run identity") from exc
    if row is None:
        raise HistoricalReplayCandidateError("P638 source has no replay run")
    return str(row[0])


def _merge_p638_official_draws(
    connection: sqlite3.Connection, official_draws: Iterable[ReplayDraw]
) -> None:
    for draw in official_draws:
        if draw.lottery_type is not LotteryType.POWER_LOTTO or draw.special_number is None:
            raise HistoricalReplayCandidateError("P638 official draw is incomplete")
        row = connection.execute(
            "SELECT draw_date, main_numbers_json, special_numbers_json "
            "FROM historical_draw_snapshot "
            "WHERE run_id = (SELECT run_id FROM historical_p638_run LIMIT 1) "
            "AND lottery_type = 'POWER_LOTTO' AND draw_number = ?",
            (draw.draw_number,),
        ).fetchone()
        encoded_main = json.dumps(draw.main_numbers, separators=(",", ":"))
        encoded_special = json.dumps([draw.special_number], separators=(",", ":"))
        if row is None:
            run_id = str(
                connection.execute(
                    "SELECT run_id FROM historical_p638_run LIMIT 1"
                ).fetchone()[0]
            )
            next_id = int(
                connection.execute(
                    "SELECT COALESCE(MAX(id), 0) + 1 FROM historical_draw_snapshot"
                ).fetchone()[0]
            )
            draw_sha256 = hashlib.sha256(
                json.dumps(
                    {
                        "draw_number": draw.draw_number,
                        "draw_date": draw.draw_date.isoformat(),
                        "zone1": draw.main_numbers,
                        "zone2": draw.special_number,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            connection.execute(
                """
                INSERT INTO historical_draw_snapshot (
                    id, run_id, lottery_type, draw_number, draw_date,
                    main_numbers_json, special_numbers_json, draw_sha256, created_at
                ) VALUES (?, ?, 'POWER_LOTTO', ?, ?, ?, ?, ?, ?)
                """,
                (
                    next_id,
                    run_id,
                    draw.draw_number,
                    draw.draw_date.isoformat(),
                    encoded_main,
                    encoded_special,
                    draw_sha256,
                    _utc_now(),
                ),
            )
            continue
        if tuple(row) != (draw.draw_date.isoformat(), encoded_main, encoded_special):
            raise HistoricalReplayCandidateError("P638 official draw conflicts with candidate")


def _persist_p638_record(
    connection: sqlite3.Connection,
    *,
    run_id: str,
    record: ReplayTargetRecord,
    allow_repair: bool,
) -> str:
    if record.status in (ReplayCellStatus.MISSING, ReplayCellStatus.PARTIAL):
        raise HistoricalReplayCandidateError("unresolved reconcile placeholder cannot be persisted")
    status, exclusion_reason, failure_reason = _p638_status(record)
    strategy_snapshot = connection.execute(
        """
        SELECT strategy_snapshot_id, native_ticket_count
        FROM historical_p638_strategy_ledger
        WHERE run_id = ? AND strategy_id = ? AND strategy_version = ?
        """,
        (run_id, record.strategy.strategy_id, record.strategy.strategy_version),
    ).fetchone()
    if strategy_snapshot is None:
        raise CandidateConflictError("P638 strategy identity is absent from candidate ledger")
    snapshot_id = str(strategy_snapshot[0])
    if (
        strategy_snapshot[1] is not None
        and int(strategy_snapshot[1]) != record.strategy.native_ticket_count
    ):
        raise CandidateConflictError("P638 native ticket count conflicts with candidate ledger")
    target_snapshot = connection.execute(
        """
        SELECT id FROM historical_draw_snapshot
        WHERE run_id = ? AND lottery_type = 'POWER_LOTTO' AND draw_number = ?
        """,
        (run_id, record.target.draw_number),
    ).fetchone()
    if target_snapshot is None:
        raise CandidateConflictError("P638 target draw is absent from candidate snapshot")
    target_snapshot_id = int(target_snapshot[0])
    boundary = record.causal_history[-1] if record.causal_history else None
    cutoff_snapshot_id = None
    if boundary is not None:
        row = connection.execute(
            "SELECT id FROM historical_draw_snapshot WHERE run_id = ? AND draw_number = ?",
            (run_id, boundary.draw_number),
        ).fetchone()
        if row is None:
            raise CandidateConflictError("P638 causal boundary is absent from candidate")
        cutoff_snapshot_id = int(row[0])
    target_id = _p638_target_id(run_id, record)
    expected_row = (
        target_id,
        run_id,
        snapshot_id,
        record.strategy.strategy_id,
        record.strategy.strategy_version,
        target_snapshot_id,
        cutoff_snapshot_id,
        record.target.draw_number,
        record.target.draw_date.isoformat(),
        None if boundary is None else boundary.draw_number,
        None if boundary is None else boundary.draw_date.isoformat(),
        len(record.causal_history),
        record.strategy.native_ticket_count,
        status,
        exclusion_reason,
        failure_reason,
        f"historical_replay_controller::{record.strategy.strategy_id}::{record.target.draw_number}",
    )
    existing = connection.execute(
        """
        SELECT id, run_id, strategy_snapshot_id, strategy_id, strategy_version,
               target_draw_snapshot_id, cutoff_draw_snapshot_id, target_draw_number,
               target_draw_date, history_boundary_draw_number, history_boundary_date,
               history_length, expected_ticket_count, status, exclusion_reason,
               failure_reason, source_target_locator
        FROM historical_p638_target
        WHERE run_id = ? AND strategy_id = ? AND strategy_version = ? AND target_draw_number = ?
        """,
        (
            run_id,
            record.strategy.strategy_id,
            record.strategy.strategy_version,
            record.target.draw_number,
        ),
    ).fetchone()
    if existing is not None and allow_repair and tuple(existing) != expected_row:
        connection.execute("DELETE FROM historical_p638_target WHERE id = ?", (str(existing[0]),))
        existing = None
    elif existing is not None and tuple(existing) != expected_row:
        raise CandidateConflictError("P638 target content conflicts with candidate")
    if existing is None:
        connection.execute(
            """
            INSERT INTO historical_p638_target (
                id, run_id, strategy_snapshot_id, strategy_id, strategy_version,
                target_draw_snapshot_id, cutoff_draw_snapshot_id, target_draw_number,
                target_draw_date, history_boundary_draw_number, history_boundary_date,
                history_length, expected_ticket_count, status, exclusion_reason,
                failure_reason, source_target_locator
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            expected_row,
        )
        state = "inserted"
    else:
        state = "reused"
    try:
        if status == "COMPLETE":
            _ensure_p638_ticket_rows(connection, run_id, record, target_id, snapshot_id)
        else:
            ticket_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM historical_p638_ticket WHERE target_id = ?",
                    (target_id,),
                ).fetchone()[0]
            )
            if ticket_count:
                raise CandidateConflictError("excluded or failed P638 target has ticket rows")
    except CandidateConflictError:
        if not allow_repair:
            raise
        connection.execute("DELETE FROM historical_p638_target WHERE id = ?", (target_id,))
        connection.execute(
            """
            INSERT INTO historical_p638_target (
                id, run_id, strategy_snapshot_id, strategy_id, strategy_version,
                target_draw_snapshot_id, cutoff_draw_snapshot_id, target_draw_number,
                target_draw_date, history_boundary_draw_number, history_boundary_date,
                history_length, expected_ticket_count, status, exclusion_reason,
                failure_reason, source_target_locator
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            expected_row,
        )
        state = "inserted"
        if status == "COMPLETE":
            _ensure_p638_ticket_rows(connection, run_id, record, target_id, snapshot_id)
    return state


def _p638_status(record: ReplayTargetRecord) -> tuple[str, str | None, str | None]:
    if record.status is ReplayCellStatus.COMPLETE:
        if len(record.tickets) != record.strategy.native_ticket_count:
            raise HistoricalReplayCandidateError("P638 complete record lost native tickets")
        if len(record.evaluations) != len(record.tickets):
            raise HistoricalReplayCandidateError("P638 complete record lost evaluations")
        return "COMPLETE", None, None
    if record.status is ReplayCellStatus.NOT_ELIGIBLE:
        return (
            "EXCLUDED_INSUFFICIENT_HISTORY",
            record.reason or "INSUFFICIENT_CAUSAL_HISTORY",
            None,
        )
    if record.status is ReplayCellStatus.TYPED_CLOSURE:
        return (
            "EXCLUDED_SOURCE_NATIVE_PORTFOLIO_CLOSURE",
            record.reason or "DECLARED_NATIVE_TICKET_CLOSURE",
            None,
        )
    if record.status is ReplayCellStatus.FAILED:
        return "FAILED", None, record.reason or "FAILED_EXECUTION"
    raise HistoricalReplayCandidateError("unsupported P638 replay status")


def _p638_target_id(run_id: str, record: ReplayTargetRecord) -> str:
    identity = (
        f"{run_id}|{record.strategy.strategy_id}|{record.strategy.strategy_version}|"
        f"{record.target.draw_number}"
    )
    return f"p638-target-{hashlib.sha256(identity.encode()).hexdigest()[:24]}"


def _ensure_p638_ticket_rows(
    connection: sqlite3.Connection,
    run_id: str,
    record: ReplayTargetRecord,
    target_id: str,
    strategy_snapshot_id: str,
) -> None:
    run_row = connection.execute(
        "SELECT source_run_id, source_replay_sha256, second_zone_ssot_version "
        "FROM historical_p638_run WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    if run_row is None:
        raise CandidateConflictError("P638 run provenance is absent")
    ledger_row = connection.execute(
        "SELECT provenance FROM historical_p638_strategy_ledger WHERE strategy_snapshot_id = ?",
        (strategy_snapshot_id,),
    ).fetchone()
    if ledger_row is None:
        raise CandidateConflictError("P638 strategy provenance is absent")
    source_run_id, source_replay_sha256, ssot_version = map(str, run_row)
    provenance = str(ledger_row[0])
    for ticket, evaluation in zip(record.tickets, record.evaluations, strict=True):
        if ticket.special_number is None or record.target.special_number is None:
            raise HistoricalReplayCandidateError("P638 ticket lost second-zone identity")
        ticket_id = _p638_ticket_id(target_id, ticket.ticket_position)
        expected = (
            ticket_id,
            target_id,
            run_id,
            record.strategy.strategy_id,
            record.strategy.strategy_version,
            record.target.draw_number,
            ticket.ticket_position,
            json.dumps(ticket.main_numbers, separators=(",", ":")),
            ticket.special_number,
            json.dumps(record.target.main_numbers, separators=(",", ":")),
            record.target.special_number,
            evaluation.zone1_hits,
            int(evaluation.zone2_hit),
            "COMPLETE",
            source_run_id,
            source_replay_sha256,
            f"historical_replay_controller::{record.strategy.strategy_id}::{record.target.draw_number}:{ticket.ticket_position}",
            ssot_version,
            provenance,
        )
        existing = connection.execute(
            """
            SELECT id, target_id, run_id, strategy_id, strategy_version, target_draw_number,
                   ticket_position, predicted_zone1_numbers_json, predicted_zone2_number,
                   actual_zone1_numbers_json, actual_zone2_number, zone1_hit_count, zone2_hit,
                   status, source_run_id, source_replay_sha256, source_record_locator,
                   second_zone_ssot_version, provenance
            FROM historical_p638_ticket
            WHERE target_id = ? AND ticket_position = ?
            """,
            (target_id, ticket.ticket_position),
        ).fetchone()
        if existing is not None and tuple(existing) != expected:
            raise CandidateConflictError("P638 ticket content conflicts with candidate")
        if existing is None:
            connection.execute(
                """
                INSERT INTO historical_p638_ticket (
                    id, target_id, run_id, strategy_id, strategy_version, target_draw_number,
                    ticket_position, predicted_zone1_numbers_json, predicted_zone2_number,
                    actual_zone1_numbers_json, actual_zone2_number, zone1_hit_count, zone2_hit,
                    status, source_run_id, source_replay_sha256, source_record_locator,
                    second_zone_ssot_version, provenance
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                expected,
            )


def _p638_ticket_id(target_id: str, position: int) -> str:
    return f"p638-ticket-{hashlib.sha256(f'{target_id}|{position}'.encode()).hexdigest()[:24]}"


def _refresh_p638_summary(
    connection: sqlite3.Connection, run_id: str, selected_strategy_count: int
) -> None:
    counts = {
        str(row[0]): int(row[1])
        for row in connection.execute(
            "SELECT status, COUNT(*) FROM historical_p638_target WHERE run_id = ? GROUP BY status",
            (run_id,),
        ).fetchall()
    }
    complete = counts.get("COMPLETE", 0)
    insufficient = counts.get("EXCLUDED_INSUFFICIENT_HISTORY", 0)
    closure = counts.get("EXCLUDED_SOURCE_NATIVE_PORTFOLIO_CLOSURE", 0)
    failed = counts.get("FAILED", 0)
    tickets = int(
        connection.execute(
            "SELECT COUNT(*) FROM historical_p638_ticket WHERE run_id = ? AND status = 'COMPLETE'",
            (run_id,),
        ).fetchone()[0]
    )
    draw_count = int(
        connection.execute(
            "SELECT COUNT(*) FROM historical_draw_snapshot "
            "WHERE run_id = ? AND lottery_type = 'POWER_LOTTO'",
            (run_id,),
        ).fetchone()[0]
    )
    connection.execute(
        """
        UPDATE historical_p638_run
        SET total_source_targets = ?, selected_strategy_count = ?, draw_count = ?,
            eligible_attempts = ?, complete_targets = ?, excluded_targets = ?,
            failed_targets = ?, ticket_rows = ?
        WHERE run_id = ?
        """,
        (
            complete + insufficient + closure + failed,
            selected_strategy_count,
            draw_count,
            complete + closure + failed,
            complete,
            insufficient + closure,
            failed,
            tickets,
            run_id,
        ),
    )


__all__ = [
    "CandidateConflictError",
    "CandidatePathSafetyError",
    "CandidateReplayOutcome",
    "HistoricalReplayCandidateError",
    "InsufficientDiskForCandidateError",
    "SQLiteP638CandidatePersistence",
    "SQLiteT539CandidatePersistence",
    "T539TypedClosureStorageRequired",
]
