"""Explicit, standalone SQLite replay storage; never migrates a source/results DB."""

from __future__ import annotations

import json
import os
import sqlite3
import stat
from collections.abc import Generator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any, cast

from lottolab.application.use_cases.replay_backfill import JsonObject, canonical_json, identity
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayDraw
from lottolab.domain.prize_evaluation import evaluate_lottery_prize
from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataPaths,
    open_database,
    verify_schema_read_only,
)
from lottolab.infrastructure.persistence.project_database_paths import (
    is_project_database_boundary,
    require_project_database_write_ready,
)

SCHEMA_SQL = """
CREATE TABLE replay_backfill_schema (
    version INTEGER PRIMARY KEY CHECK(version = 2), checksum TEXT NOT NULL
);
CREATE TABLE replay_backfill_runs (
    run_id TEXT PRIMARY KEY, manifest_json TEXT NOT NULL,
    expected_cells INTEGER NOT NULL CHECK(expected_cells > 0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE replay_backfill_targets (
    run_id TEXT NOT NULL REFERENCES replay_backfill_runs(run_id),
    lottery_type TEXT NOT NULL, target_draw_id TEXT NOT NULL, target_draw_date TEXT NOT NULL,
    actual_main_numbers_json TEXT NOT NULL, actual_special_numbers_json TEXT NOT NULL,
    source_identity TEXT NOT NULL,
    PRIMARY KEY(run_id,target_draw_id)
);
CREATE TABLE replay_backfill_strategy_inventory (
    run_id TEXT NOT NULL REFERENCES replay_backfill_runs(run_id),
    lottery_type TEXT NOT NULL, strategy_id TEXT NOT NULL, strategy_version TEXT NOT NULL,
    display_name TEXT NOT NULL, lifecycle_status TEXT NOT NULL, data_status TEXT NOT NULL,
    source_kind TEXT NOT NULL, executable INTEGER NOT NULL CHECK(executable IN (0,1)),
    available_target_count INTEGER NOT NULL CHECK(available_target_count >= 0),
    training_status TEXT NOT NULL, source_identity TEXT NOT NULL,
    PRIMARY KEY(run_id,lottery_type,strategy_id,strategy_version)
);
CREATE TABLE replay_backfill_cells (
    cell_identity TEXT PRIMARY KEY,
    lottery_type TEXT NOT NULL, strategy_id TEXT NOT NULL, strategy_version TEXT NOT NULL,
    execution_version TEXT NOT NULL, dataset_identity TEXT NOT NULL,
    target_draw_id TEXT NOT NULL, target_draw_date TEXT NOT NULL,
    execution_status TEXT NOT NULL CHECK(execution_status IN
        ('COMPLETE','FAILED','NOT_ELIGIBLE','TYPED_CLOSURE','MISSING','PARTIAL','ARTIFACT_ONLY')),
    result_identity TEXT NOT NULL, payload_json TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 1 CHECK(attempts > 0),
    UNIQUE(lottery_type,strategy_id,strategy_version,execution_version,dataset_identity,target_draw_id)
);
CREATE TABLE replay_backfill_run_cells (
    run_id TEXT NOT NULL REFERENCES replay_backfill_runs(run_id),
    cell_identity TEXT NOT NULL REFERENCES replay_backfill_cells(cell_identity),
    PRIMARY KEY(run_id,cell_identity)
);
CREATE TABLE replay_backfill_tickets (
    cell_identity TEXT NOT NULL REFERENCES replay_backfill_cells(cell_identity),
    ticket_position INTEGER NOT NULL, main_numbers_json TEXT NOT NULL,
    special_numbers_json TEXT NOT NULL, main_hit_count INTEGER, special_hit INTEGER,
    prize_tier TEXT, PRIMARY KEY(cell_identity,ticket_position)
);
CREATE TABLE replay_backfill_training (
    cell_identity TEXT PRIMARY KEY REFERENCES replay_backfill_cells(cell_identity),
    training_status TEXT NOT NULL, model_version TEXT, training_cutoff TEXT,
    training_artifact_id TEXT, input_source_hash TEXT, trainer_identity TEXT,
    training_artifact_hash TEXT
);
CREATE TABLE replay_backfill_sources (
    run_id TEXT NOT NULL REFERENCES replay_backfill_runs(run_id), source_identity TEXT NOT NULL,
    source_kind TEXT NOT NULL, source_locator TEXT NOT NULL, source_hash TEXT,
    artifact_only INTEGER NOT NULL CHECK(artifact_only IN (0,1)),
    PRIMARY KEY(run_id,source_identity)
);
CREATE INDEX replay_backfill_filter ON replay_backfill_cells
    (lottery_type,strategy_id,target_draw_date,target_draw_id);
CREATE INDEX replay_backfill_status ON replay_backfill_cells(execution_status);
CREATE INDEX replay_backfill_targets_period ON replay_backfill_targets
    (run_id,target_draw_date,target_draw_id);
CREATE INDEX replay_backfill_inventory_status ON replay_backfill_strategy_inventory
    (lottery_type,lifecycle_status,data_status,strategy_id);
CREATE INDEX replay_backfill_tickets_position ON replay_backfill_tickets
    (ticket_position,cell_identity);
"""
SCHEMA_CHECKSUM = identity(SCHEMA_SQL)
SCHEMA_VERSION = 2
LEGACY_V1_SCHEMA_CHECKSUM = "87659eafeb6be707bf711e0951cf9695bfce30748ddc218213c5cb799f33f16c"
_LEGACY_V1_TABLES = {
    "replay_backfill_schema",
    "replay_backfill_runs",
    "replay_backfill_cells",
    "replay_backfill_run_cells",
}
_TABLES = {
    "replay_backfill_schema",
    "replay_backfill_runs",
    "replay_backfill_targets",
    "replay_backfill_strategy_inventory",
    "replay_backfill_cells",
    "replay_backfill_run_cells",
    "replay_backfill_tickets",
    "replay_backfill_training",
    "replay_backfill_sources",
}


def _schema_table_sql(table: str) -> str:
    prefix = f"CREATE TABLE {table} ("
    for statement in SCHEMA_SQL.split(";"):
        candidate = statement.strip()
        if candidate.startswith(prefix):
            return candidate
    raise RuntimeError(f"missing schema table definition: {table}")


def _column_names(connection: sqlite3.Connection, table: str) -> tuple[str, ...]:
    return tuple(row[1] for row in connection.execute(f'PRAGMA table_info("{table}")'))


def _copy_table_columns(
    connection: sqlite3.Connection,
    source: str,
    destination: str,
) -> None:
    columns = _column_names(connection, source)
    if columns != _column_names(connection, destination):
        raise ValueError(f"unsupported legacy replay backfill table: {source}")
    quoted = ",".join(f'"{column}"' for column in columns)
    connection.execute(
        f'INSERT INTO "{destination}" ({quoted}) SELECT {quoted} FROM "{source}"'
    )


def _migrate_legacy_v1(connection: sqlite3.Connection) -> None:
    schema_row = connection.execute(
        "SELECT version,checksum FROM replay_backfill_schema"
    ).fetchall()
    if schema_row != [(1, LEGACY_V1_SCHEMA_CHECKSUM)]:
        raise ValueError("unsupported replay backfill schema")

    expected_columns = {
        "replay_backfill_schema": ("version", "checksum"),
        "replay_backfill_runs": ("run_id", "manifest_json", "expected_cells", "created_at"),
        "replay_backfill_cells": (
            "cell_identity",
            "lottery_type",
            "strategy_id",
            "strategy_version",
            "execution_version",
            "dataset_identity",
            "target_draw_id",
            "target_draw_date",
            "execution_status",
            "result_identity",
            "payload_json",
            "attempts",
        ),
        "replay_backfill_run_cells": ("run_id", "cell_identity"),
    }
    for table, columns in expected_columns.items():
        if _column_names(connection, table) != columns:
            raise ValueError(f"unsupported legacy replay backfill table: {table}")
    indexes = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"
        )
    }
    if indexes != {"replay_backfill_filter", "replay_backfill_status"}:
        raise ValueError("unsupported legacy replay backfill indexes")

    connection.execute("ALTER TABLE replay_backfill_cells RENAME TO replay_backfill_cells_v1")
    connection.execute(
        "ALTER TABLE replay_backfill_run_cells RENAME TO replay_backfill_run_cells_v1"
    )
    cells_sql = _schema_table_sql("replay_backfill_cells").replace(
        "CREATE TABLE replay_backfill_cells (",
        "CREATE TABLE replay_backfill_cells_v2 (",
        1,
    )
    run_cells_sql = _schema_table_sql("replay_backfill_run_cells").replace(
        "CREATE TABLE replay_backfill_run_cells (",
        "CREATE TABLE replay_backfill_run_cells_v2 (",
        1,
    ).replace(
        "REFERENCES replay_backfill_cells(cell_identity)",
        "REFERENCES replay_backfill_cells_v2(cell_identity)",
        1,
    )
    connection.execute(cells_sql)
    connection.execute(run_cells_sql)
    _copy_table_columns(connection, "replay_backfill_cells_v1", "replay_backfill_cells_v2")
    _copy_table_columns(
        connection, "replay_backfill_run_cells_v1", "replay_backfill_run_cells_v2"
    )
    connection.execute("DROP TABLE replay_backfill_run_cells_v1")
    connection.execute("DROP TABLE replay_backfill_cells_v1")
    connection.execute("ALTER TABLE replay_backfill_cells_v2 RENAME TO replay_backfill_cells")
    connection.execute(
        "ALTER TABLE replay_backfill_run_cells_v2 RENAME TO replay_backfill_run_cells"
    )

    for table in (
        "replay_backfill_targets",
        "replay_backfill_strategy_inventory",
        "replay_backfill_tickets",
        "replay_backfill_training",
        "replay_backfill_sources",
    ):
        connection.execute(_schema_table_sql(table))

    connection.execute(
        "ALTER TABLE replay_backfill_schema RENAME TO replay_backfill_schema_v1"
    )
    connection.execute(_schema_table_sql("replay_backfill_schema"))
    connection.execute(
        "INSERT INTO replay_backfill_schema(version,checksum) VALUES(?,?)",
        (SCHEMA_VERSION, SCHEMA_CHECKSUM),
    )
    connection.execute("DROP TABLE replay_backfill_schema_v1")
    for statement in SCHEMA_SQL.split(";"):
        index_sql = statement.strip()
        if index_sql.startswith("CREATE INDEX "):
            connection.execute(index_sql)
    if connection.execute("PRAGMA foreign_key_check").fetchall():
        raise ValueError("legacy replay backfill migration failed foreign key check")


def validate_database_path(database: Path) -> Path:
    if not database.is_absolute() or "\x00" in str(database):
        raise ValueError("database must be an absolute path")
    if any(p.lower() in {"lotterynew", ".git"} for p in database.parts):
        raise ValueError("protected database path")
    if any(p.is_symlink() for p in (database, *database.parents)):
        raise ValueError("database path must not contain symlinks")
    for parent in database.parents:
        if (parent / ".git").exists():
            if is_project_database_boundary(database, parent):
                continue
            raise ValueError("database must be outside a Git checkout")
    if database.exists():
        info = database.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid():
            raise ValueError("database must be an owner-owned regular file without hardlinks")
    return database


def load_draw_snapshot(database: Path, lottery_type: LotteryType) -> tuple[ReplayDraw, ...]:
    """One consistent read transaction, with canonical draw-schema verification."""
    validate_database_path(database)
    paths = LocalDataPaths(database.parent, database)
    if not verify_schema_read_only(paths):
        raise ValueError("draw database is missing or has an invalid schema")
    with open_database(paths, read_only=True) as connection:
        connection.execute("BEGIN")
        rows = connection.execute(
            "SELECT draw_number,draw_date,main_numbers_json,special_numbers_json FROM draws "
            "WHERE lottery_type=? ORDER BY draw_date,CAST(draw_number AS INTEGER)",
            (lottery_type.value,),
        ).fetchall()
    draws: list[ReplayDraw] = []
    for number, draw_date, main_json, special_json in rows:
        main: object = json.loads(main_json)
        special: object = json.loads(special_json)
        required_special = 0 if lottery_type is LotteryType.DAILY_539 else 1
        if not isinstance(main, list) or not isinstance(special, list):
            raise ValueError("draw numbers must be JSON arrays")
        raw_main = cast(list[object], main)
        raw_special = cast(list[object], special)
        if any(type(n) is not int for n in (*raw_main, *raw_special)):
            raise ValueError("draw numbers must be exact integers")
        main_numbers = tuple(cast(list[int], raw_main))
        special_numbers = cast(list[int], raw_special)
        if len(special_numbers) != required_special:
            raise ValueError("draw has an invalid special-number count")
        special_number = special_numbers[0] if special_numbers else None
        # The canonical evaluator validates native number counts/ranges/uniqueness.
        evaluate_lottery_prize(
            lottery_type=lottery_type,
            predicted_main_numbers=main_numbers,
            predicted_special_number=special_number
            if lottery_type is LotteryType.POWER_LOTTO
            else None,
            winning_main_numbers=main_numbers,
            winning_special_number=special_number,
        )
        draws.append(
            ReplayDraw(
                lottery_type, number, date.fromisoformat(draw_date), main_numbers, special_number
            )
        )
    return tuple(draws)


class SQLiteBackfillStore:
    def __init__(self, database: Path, *, read_only: bool = False) -> None:
        # Construction and OpenAPI generation do not touch the database.
        self.database = database
        self.read_only = read_only

    @contextmanager
    def _connect(self, *, write: bool = False) -> Generator[sqlite3.Connection]:
        database = validate_database_path(self.database)
        if write and self.read_only:
            raise ValueError("read-only store")
        if write:
            require_project_database_write_ready(database)
        connection = sqlite3.connect(
            database.as_uri() + "?mode=rw" if write else database.as_uri() + "?mode=ro",
            uri=True,
            timeout=5,
        )
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            if not write:
                connection.execute("PRAGMA query_only=ON")
            self._verify(connection)
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _verify(connection: sqlite3.Connection) -> None:
        row = connection.execute("SELECT version,checksum FROM replay_backfill_schema").fetchall()
        if row != [(SCHEMA_VERSION, SCHEMA_CHECKSUM)]:
            raise ValueError("unsupported replay backfill schema")

    def prepare(self, manifest: JsonObject) -> None:
        if self.read_only:
            raise ValueError("read-only store")
        path = validate_database_path(self.database)
        require_project_database_write_ready(path)
        if not path.parent.is_dir():
            raise ValueError("output database parent must already exist")
        if not path.exists():
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        # A crash before the first schema commit leaves an empty task output.
        # Empty outputs can be initialized on resume; foreign schemas fail closed.
        connection = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, timeout=5)
        try:
            connection.execute("BEGIN IMMEDIATE")
            tables = {
                r[0]
                for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            if not tables:
                for statement in SCHEMA_SQL.split(";"):
                    if statement.strip():
                        connection.execute(statement)
                connection.execute(
                    "INSERT INTO replay_backfill_schema VALUES(?,?)",
                    (SCHEMA_VERSION, SCHEMA_CHECKSUM),
                )
            elif tables == _LEGACY_V1_TABLES:
                _migrate_legacy_v1(connection)
            elif tables != _TABLES:
                raise ValueError("output must be a standalone replay backfill database")
            self._verify(connection)
            connection.commit()
        finally:
            connection.close()
        with self._connect(write=True) as connection:
            tables = {
                r[0]
                for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            if tables != _TABLES:
                raise ValueError("output must be a standalone replay backfill database")
            encoded = canonical_json(manifest)
            connection.execute(
                "INSERT OR IGNORE INTO replay_backfill_runs(run_id,manifest_json,expected_cells) "
                "VALUES(?,?,?)",
                (manifest["run_id"], encoded, manifest["expected_cells"]),
            )
            stored = connection.execute(
                "SELECT manifest_json FROM replay_backfill_runs WHERE run_id=?",
                (manifest["run_id"],),
            ).fetchone()
            if stored != (encoded,):
                raise ValueError("run identity conflicts with stored manifest")
            lottery_type = manifest["lottery_type"]
            for target in manifest.get("source_targets", manifest.get("targets", [])):
                connection.execute(
                    "INSERT OR IGNORE INTO replay_backfill_targets VALUES(?,?,?,?,?,?,?)",
                    (
                        manifest["run_id"],
                        lottery_type,
                        target["draw_number"],
                        target["draw_date"],
                        canonical_json(target["main_numbers"]),
                        canonical_json(target["special_numbers"]),
                        target["source_identity"],
                    ),
                )
            for strategy in manifest.get("strategies", []):
                source = manifest.get("strategy_sources", {}).get(strategy["strategy_id"], {})
                connection.execute(
                    "INSERT OR IGNORE INTO replay_backfill_strategy_inventory "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        manifest["run_id"],
                        lottery_type,
                        strategy["strategy_id"],
                        strategy["strategy_version"],
                        strategy["strategy_name"],
                        source.get("lifecycle_status", "ONLINE"),
                        source.get("data_status", "REBUILDABLE"),
                        source.get("source", source.get("source_kind", "NATIVE_REPLAY")),
                        1,
                        len(manifest.get("targets", [])),
                        source.get("training_status") or "UNKNOWN",
                        source.get("fingerprint", strategy.get("fingerprint") or ""),
                    ),
                )
            source_identity = manifest["dataset_identity"]
            connection.execute(
                "INSERT OR IGNORE INTO replay_backfill_sources VALUES(?,?,?,?,?,0)",
                (
                    manifest["run_id"],
                    source_identity,
                    "OFFICIAL_HISTORICAL",
                    manifest.get("source_locator", ""),
                    manifest.get("source_hash", source_identity),
                ),
            )

    def lookup(self, cell_identity: str) -> JsonObject | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM replay_backfill_cells WHERE cell_identity=?",
                (cell_identity,),
            ).fetchone()
        return json.loads(row[0]) if row is not None else None

    def lookup_many(self, cell_identities: tuple[str, ...]) -> dict[str, JsonObject]:
        if not cell_identities:
            return {}
        found: dict[str, JsonObject] = {}
        with self._connect() as connection:
            for offset in range(0, len(cell_identities), 500):
                batch = cell_identities[offset : offset + 500]
                placeholders = ",".join("?" for _ in batch)
                for cell_id, payload in connection.execute(
                    f"SELECT cell_identity,payload_json FROM replay_backfill_cells "
                    f"WHERE cell_identity IN ({placeholders})",
                    batch,
                ):
                    found[cell_id] = json.loads(payload)
        return found

    def save(self, run_id: str, result: JsonObject, *, attempted: bool = True) -> None:
        self.save_many(run_id, (result,), retry_failed=attempted)

    def save_many(
        self,
        run_id: str,
        results: tuple[JsonObject, ...],
        *,
        retry_failed: bool = True,
    ) -> None:
        encoded_results: list[tuple[JsonObject, str]] = []
        for result in results:
            encoded = canonical_json(result)
            body = {k: v for k, v in result.items() if k != "result_identity"}
            if identity(body) != result["result_identity"]:
                raise ValueError("result digest mismatch")
            encoded_results.append((result, encoded))
        with self._connect(write=True) as connection:
            connection.execute("BEGIN IMMEDIATE")
            for result, encoded in encoded_results:
                cell_id = result["cell_identity"]
                old = connection.execute(
                    "SELECT execution_status,result_identity FROM replay_backfill_cells "
                    "WHERE cell_identity=?",
                    (cell_id,),
                ).fetchone()
                if old is not None and old[1] != result["result_identity"]:
                    if old[0] != "FAILED" or not retry_failed:
                        raise ValueError(
                            "CONFLICT: cell identity already has different result bytes"
                        )
                    connection.execute(
                        "DELETE FROM replay_backfill_tickets WHERE cell_identity=?", (cell_id,)
                    )
                    connection.execute(
                        "DELETE FROM replay_backfill_training WHERE cell_identity=?", (cell_id,)
                    )
                    connection.execute(
                        "UPDATE replay_backfill_cells SET execution_status=?,result_identity=?,"
                        "payload_json=?,attempts=attempts+1 WHERE cell_identity=?",
                        (result["execution_status"], result["result_identity"], encoded, cell_id),
                    )
                elif old is None:
                    keys = (
                        "cell_identity",
                        "lottery_type",
                        "strategy_id",
                        "strategy_version",
                        "execution_version",
                        "dataset_identity",
                        "target_draw_id",
                        "target_draw_date",
                        "execution_status",
                        "result_identity",
                    )
                    connection.execute(
                        "INSERT INTO replay_backfill_cells VALUES(?,?,?,?,?,?,?,?,?,?,?,1)",
                        (*(result[k] for k in keys), encoded),
                    )
                connection.execute(
                    "INSERT OR IGNORE INTO replay_backfill_run_cells VALUES(?,?)",
                    (run_id, cell_id),
                )
                self._insert_result_children(connection, result)
                if result.get("execution_status") == "ARTIFACT_ONLY":
                    source = result.get("strategy_source", {})
                    training = result.get("training", {})
                    connection.execute(
                        "INSERT OR IGNORE INTO replay_backfill_strategy_inventory "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            run_id,
                            result["lottery_type"],
                            result["strategy_id"],
                            result["strategy_version"],
                            result.get("display_name", result["strategy_id"]),
                            "UNREGISTERED",
                            "ARTIFACT_ONLY",
                            source.get("source_kind", "HISTORICAL_RESEARCH_ARTIFACT"),
                            0,
                            0,
                            training.get("training_status", "HISTORICAL_ARTIFACT"),
                            source.get("source_identity", result["dataset_identity"]),
                        ),
                    )
                    connection.execute(
                        "UPDATE replay_backfill_strategy_inventory SET available_target_count=("
                        "SELECT COUNT(DISTINCT c.target_draw_id) FROM replay_backfill_cells c "
                        "JOIN replay_backfill_run_cells r USING(cell_identity) "
                        "WHERE r.run_id=? AND c.strategy_id=? AND c.strategy_version=? "
                        "AND c.execution_status='ARTIFACT_ONLY') WHERE run_id=? AND strategy_id=? "
                        "AND strategy_version=?",
                        (
                            run_id,
                            result["strategy_id"],
                            result["strategy_version"],
                            run_id,
                            result["strategy_id"],
                            result["strategy_version"],
                        ),
                    )
                    connection.execute(
                        "INSERT OR IGNORE INTO replay_backfill_sources VALUES(?,?,?,?,?,1)",
                        (
                            run_id,
                            source.get("source_identity", result["result_identity"]),
                            source.get("source_kind", "HISTORICAL_RESEARCH_ARTIFACT"),
                            source.get("source_locator", ""),
                            source.get("source_hash"),
                        ),
                    )

    @staticmethod
    def _insert_result_children(connection: sqlite3.Connection, result: JsonObject) -> None:
        tickets = result.get("predicted_tickets", [])
        hits = result.get("hit_details", [])
        for index, ticket in enumerate(tickets):
            hit = hits[index] if index < len(hits) else {}
            connection.execute(
                "INSERT OR IGNORE INTO replay_backfill_tickets VALUES(?,?,?,?,?,?,?)",
                (
                    result["cell_identity"],
                    ticket["ticket_position"],
                    canonical_json(ticket["main_numbers"]),
                    canonical_json(
                        [] if ticket.get("special_number") is None else [ticket["special_number"]]
                    ),
                    hit.get("zone1_hits"),
                    None if hit.get("zone2_hit") is None else int(hit["zone2_hit"]),
                    hit.get("prize_tier"),
                ),
            )
        training = result.get("training", {})
        connection.execute(
            "INSERT OR REPLACE INTO replay_backfill_training VALUES(?,?,?,?,?,?,?,?)",
            (
                result["cell_identity"],
                training.get("training_status") or "UNKNOWN",
                training.get("model_version"),
                training.get("training_cutoff"),
                training.get("training_artifact_id"),
                training.get("input_source_hash"),
                training.get("trainer_identity"),
                training.get("training_artifact_hash"),
            ),
        )

    def summary(self, run_id: str) -> JsonObject:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT manifest_json,expected_cells FROM replay_backfill_runs WHERE run_id=?",
                (run_id,),
            ).fetchone()
            if row is None:
                raise KeyError("run not found")
            counts = dict(
                connection.execute(
                    "SELECT c.execution_status,COUNT(*) FROM replay_backfill_cells c "
                    "JOIN replay_backfill_run_cells r USING(cell_identity) "
                    "WHERE r.run_id=? GROUP BY c.execution_status",
                    (run_id,),
                )
            )
        expected = row[1]
        processed = sum(value for status, value in counts.items() if status != "ARTIFACT_ONLY")
        valid = counts.get("COMPLETE", 0)
        return {
            "run_id": run_id,
            "manifest": json.loads(row[0]),
            "expected_cells": expected,
            "processed_cells": processed,
            "pending_cells": max(0, expected - processed),
            "valid_result_cells": valid,
            "failed_cells": counts.get("FAILED", 0),
            "missing_history_cells": counts.get("NOT_ELIGIBLE", 0),
            "status_counts": counts,
            "coverage_percent": 100 * valid / expected,
            "status": "IN_PROGRESS"
            if processed < expected
            else ("COMPLETED" if valid == expected else "FINISHED_WITH_GAPS"),
        }

    def latest_run_id(self, lottery_type: str) -> str | None:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT run_id,manifest_json FROM replay_backfill_runs "
                "ORDER BY created_at DESC,run_id"
            ).fetchall()
        for run_id, manifest_json in rows:
            if json.loads(manifest_json).get("lottery_type") == lottery_type:
                return str(run_id)
        return None

    def run_manifest(self, run_id: str) -> JsonObject:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT manifest_json FROM replay_backfill_runs WHERE run_id=?", (run_id,)
            ).fetchone()
        if row is None:
            raise KeyError("run not found")
        return json.loads(row[0])

    def backfill_coverage(self, lottery_type: str) -> JsonObject | None:
        run_id = self.latest_run_id(lottery_type)
        if run_id is None:
            return None
        with self._connect() as connection:
            row = connection.execute(
                "SELECT manifest_json,expected_cells FROM replay_backfill_runs WHERE run_id=?",
                (run_id,),
            ).fetchone()
            if row is None:
                return None
            manifest = json.loads(row[0])
            statuses = dict(
                connection.execute(
                    "SELECT c.execution_status,COUNT(*) FROM replay_backfill_cells c "
                    "JOIN replay_backfill_run_cells r USING(cell_identity) "
                    "WHERE r.run_id=? GROUP BY c.execution_status",
                    (run_id,),
                )
            )
            strategy_counts = dict(
                connection.execute(
                    "SELECT c.strategy_id,COUNT(*) FROM replay_backfill_cells c "
                    "JOIN replay_backfill_run_cells r USING(cell_identity) "
                    "WHERE r.run_id=? AND c.execution_status='COMPLETE' GROUP BY c.strategy_id",
                    (run_id,),
                )
            )
        strategies = manifest.get("strategies", [])
        target_count = manifest.get("target_draw_count", 0)
        expected_strategy_count = len(strategies)
        expected_cell_count = target_count * expected_strategy_count
        completed = statuses.get("COMPLETE", 0)
        failed = statuses.get("FAILED", 0) + statuses.get("PARTIAL", 0)
        closed = sum(
            statuses.get(status, 0)
            for status in ("NOT_ELIGIBLE", "TYPED_CLOSURE", "MISSING")
        )
        return {
            "lottery_type": lottery_type,
            "expected_strategy_count": expected_strategy_count,
            "expected_target_count": target_count,
            "expected_cell_count": expected_cell_count,
            "completed_cell_count": completed,
            "failed_cell_count": failed,
            "closed_cell_count": closed,
            "complete_coverage_percent": (
                100.0 * completed / expected_cell_count if expected_cell_count else 0.0
            ),
            "missing_strategy_ids": sorted(
                strategy["strategy_id"]
                for strategy in strategies
                if strategy_counts.get(strategy["strategy_id"], 0) < target_count
            ),
            "run_id": run_id,
        }

    def strategy_target_counts(self, lottery_type: str) -> dict[str, int]:
        run_id = self.latest_run_id(lottery_type)
        if run_id is None:
            return {}
        with self._connect() as connection:
            return dict(
                connection.execute(
                    "SELECT strategy_id,MAX(available_target_count) "
                    "FROM replay_backfill_strategy_inventory WHERE run_id=? GROUP BY strategy_id",
                    (run_id,),
                )
            )

    def stored_strategy_inventory(self, lottery_type: str) -> list[JsonObject]:
        run_id = self.latest_run_id(lottery_type)
        if run_id is None:
            return []
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT lottery_type,strategy_id,strategy_version,display_name,lifecycle_status,"
                "data_status,"
                "source_kind,executable,available_target_count,training_status,source_identity "
                "FROM replay_backfill_strategy_inventory WHERE lottery_type=? AND run_id=? "
                "ORDER BY strategy_id,strategy_version",
                (lottery_type, run_id),
            ).fetchall()
        return [
            {
                "lottery_type": row[0],
                "strategy_id": row[1],
                "strategy_version": row[2],
                "display_name": row[3],
                "lifecycle_status": row[4],
                "data_status": row[5],
                "source_kind": row[6],
                "executable": bool(row[7]),
                "available_target_count": row[8],
                "training_status": row[9],
                "source_identity": row[10],
            }
            for row in rows
        ]

    def prediction_page(
        self,
        *,
        lottery_type: str,
        run_id: str | None = None,
        strategy_id: str | None,
        from_date: str | None,
        to_date: str | None,
        period: int | None,
        limit: int,
        after: tuple[str, int, str, str, str] | None = None,
    ) -> JsonObject:
        if limit < 1 or limit > 250:
            raise ValueError("limit must be between 1 and 250")
        if period not in {None, 50, 300, 750}:
            raise ValueError("period must be 50, 300, 750, or ALL")
        if from_date is not None:
            date.fromisoformat(from_date)
        if to_date is not None:
            date.fromisoformat(to_date)
        if from_date and to_date and from_date > to_date:
            raise ValueError("invalid date range")
        selected_run_id = run_id or self.latest_run_id(lottery_type)
        if selected_run_id is None:
            return {"run_id": None, "total_count": 0, "items": []}
        manifest = self.run_manifest(selected_run_id)
        if manifest.get("lottery_type") != lottery_type:
            raise ValueError("run lottery type does not match query")
        target_clauses = ["run_id=?", "lottery_type=?"]
        target_params: list[Any] = [selected_run_id, lottery_type]
        if from_date is not None:
            target_clauses.append("target_draw_date>=?")
            target_params.append(from_date)
        if to_date is not None:
            target_clauses.append("target_draw_date<=?")
            target_params.append(to_date)
        target_where = " AND ".join(target_clauses)
        with self._connect() as connection:
            target_sql = (
                "SELECT target_draw_id FROM replay_backfill_targets WHERE "
                + target_where
                + " ORDER BY target_draw_date DESC,CAST(target_draw_id AS INTEGER) DESC"
            )
            if period is not None:
                target_sql += " LIMIT ?"
                target_rows = connection.execute(target_sql, (*target_params, period)).fetchall()
            else:
                target_rows = connection.execute(target_sql, target_params).fetchall()
            target_ids = [str(row[0]) for row in target_rows]
            if not target_ids:
                return {"run_id": selected_run_id, "total_count": 0, "items": []}
            placeholders = ",".join("?" for _ in target_ids)
            clauses = [
                "r.run_id=?",
                "c.lottery_type=?",
                f"c.target_draw_id IN ({placeholders})",
            ]
            params: list[Any] = [selected_run_id, lottery_type, *target_ids]
            if strategy_id is not None:
                clauses.append("c.strategy_id=?")
                params.append(strategy_id)
            where = " AND ".join(clauses)
            total = connection.execute(
                "SELECT COUNT(*) FROM replay_backfill_cells c JOIN replay_backfill_run_cells r "
                f"USING(cell_identity) WHERE {where}",
                params,
            ).fetchone()[0]
            page_clauses = list(clauses)
            page_params = list(params)
            if after is not None:
                page_clauses.append(
                    "(c.target_draw_date>? OR (c.target_draw_date=? AND "
                    "CAST(c.target_draw_id AS INTEGER)>?) OR (c.target_draw_date=? AND "
                    "CAST(c.target_draw_id AS INTEGER)=? AND c.strategy_id>?) OR "
                    "(c.target_draw_date=? AND CAST(c.target_draw_id AS INTEGER)=? AND "
                    "c.strategy_id=? AND c.strategy_version>?) OR "
                    "(c.target_draw_date=? AND CAST(c.target_draw_id AS INTEGER)=? AND "
                    "c.strategy_id=? AND c.strategy_version=? AND c.cell_identity>?))"
                )
                draw_date, draw_id, sid, version, cell_id = after
                page_params.extend(
                    [
                        draw_date,
                        draw_date,
                        draw_id,
                        draw_date,
                        draw_id,
                        sid,
                        draw_date,
                        draw_id,
                        sid,
                        version,
                        draw_date,
                        draw_id,
                        sid,
                        version,
                        cell_id,
                    ]
                )
            page_where = " AND ".join(page_clauses)
            rows = connection.execute(
                "SELECT c.payload_json,c.target_draw_date,c.target_draw_id,c.strategy_id,"
                "c.strategy_version,c.cell_identity,c.dataset_identity,c.execution_version,"
                "c.result_identity FROM replay_backfill_cells c "
                "JOIN replay_backfill_run_cells r USING(cell_identity) "
                f"WHERE {page_where} ORDER BY c.target_draw_date,CAST(c.target_draw_id AS INTEGER),"
                "c.strategy_id,c.strategy_version,c.cell_identity LIMIT ?",
                (*page_params, limit + 1),
            ).fetchall()
        return {
            "run_id": selected_run_id,
            "total_count": total,
            "rows": [
                {
                    "payload": json.loads(row[0]),
                    "portfolio_context": _research_portfolio_context(
                        manifest, json.loads(row[0]), selected_run_id, lottery_type,
                        stored_identity={
                            "target_draw_date": row[1], "target_draw_id": row[2],
                            "strategy_id": row[3], "strategy_version": row[4],
                            "cell_identity": row[5], "dataset_identity": row[6],
                            "execution_version": row[7], "result_identity": row[8],
                        },
                    ),
                    "key": [row[1], int(row[2]), row[3], row[4], row[5]],
                }
                for row in rows
            ],
        }

    def query(
        self,
        *,
        run_id: str | None = None,
        lottery_type: str | None = None,
        strategy_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        target_draw_id: str | None = None,
        execution_status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> JsonObject:
        if not 1 <= limit <= 200 or offset < 0:
            raise ValueError("invalid pagination")
        if start_date is not None:
            date.fromisoformat(start_date)
        if end_date is not None:
            date.fromisoformat(end_date)
        if start_date and end_date and start_date > end_date:
            raise ValueError("invalid date range")
        clauses: list[str] = []
        params: list[Any] = []
        for column, value, op in (
            ("lottery_type", lottery_type, "="),
            ("strategy_id", strategy_id, "="),
            ("target_draw_date", start_date, ">="),
            ("target_draw_date", end_date, "<="),
            ("target_draw_id", target_draw_id, "="),
            ("execution_status", execution_status, "="),
        ):
            if value is not None:
                clauses.append(f"c.{column}{op}?")
                params.append(value)
        if run_id is not None:
            clauses.append(
                "EXISTS(SELECT 1 FROM replay_backfill_run_cells r "
                "WHERE r.cell_identity=c.cell_identity AND r.run_id=?)"
            )
            params.append(run_id)
        where = " AND ".join(clauses) if clauses else "1=1"
        with self._connect() as connection:
            connection.execute("BEGIN")
            total = connection.execute(
                f"SELECT COUNT(*) FROM replay_backfill_cells c WHERE {where}", params
            ).fetchone()[0]
            rows = connection.execute(
                f"SELECT c.payload_json FROM replay_backfill_cells c WHERE {where} "
                "ORDER BY c.target_draw_date,CAST(c.target_draw_id AS INTEGER),c.strategy_id,"
                "c.strategy_version,c.cell_identity LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return {
            "items": [json.loads(r[0]) for r in rows],
            "total_count": total,
            "limit": limit,
            "offset": offset,
        }


def _research_portfolio_context(
    manifest: JsonObject,
    payload: JsonObject,
    run_id: str,
    lottery_type: str,
    *,
    stored_identity: JsonObject | None = None,
) -> JsonObject:
    """Bind uniqueness inputs to the selected run and persisted cell identity.

    This checks recorded provenance and the result digest, not the source archive
    itself. Full import qualification must independently verify that archive.
    """
    strategies = manifest.get("strategies")
    matches: list[JsonObject] = []
    if type(strategies) is list:
        for item in cast(list[object], strategies):
            if type(item) is not dict:
                continue
            candidate = cast(JsonObject, item)
            if (candidate.get("strategy_id") == payload.get("strategy_id")
                    and candidate.get("strategy_version") == payload.get("strategy_version")):
                matches.append(candidate)
    expected: object = matches[0].get("native_ticket_count") if len(matches) == 1 else None
    body = {key: value for key, value in payload.items() if key != "result_identity"}
    digest = payload.get("result_identity")
    stored = stored_identity or {}
    identity_fields = (
        "target_draw_date", "target_draw_id", "strategy_id", "strategy_version", "cell_identity",
        "dataset_identity", "execution_version", "result_identity",
    )
    stored_matches = all(
        payload.get(key) == stored.get(key) and stored.get(key) is not None
        for key in identity_fields
    )
    ticket_identity = {
        "lottery_type": lottery_type,
        "run_id": run_id,
        "target_draw_id": stored.get("target_draw_id"),
        "strategy_id": stored.get("strategy_id"),
        "strategy_version": stored.get("strategy_version"),
    }
    raw_tickets: object = payload.get("predicted_tickets")
    ticket_identities_match = type(raw_tickets) is list
    if type(raw_tickets) is list:
        for raw in cast(list[object], raw_tickets):
            if type(raw) is not dict:
                ticket_identities_match = False
                break
            ticket = cast(JsonObject, raw)
            if any(
                key in ticket and ticket[key] != value for key, value in ticket_identity.items()
            ):
                ticket_identities_match = False
                break
            nested: object = ticket.get("identity")
            if nested is not None:
                if type(nested) is not dict:
                    ticket_identities_match = False
                    break
                nested_data = cast(JsonObject, nested)
                if (any(nested_data.get(key) != value for key, value in ticket_identity.items())
                        or nested_data.get("ticket_position") != ticket.get("ticket_position")):
                    ticket_identities_match = False
                    break
    source_bound = (
        lottery_type == "BIG_LOTTO"
        and manifest.get("lottery_type") == lottery_type
        and payload.get("lottery_type") == lottery_type
        and manifest.get("run_id") == run_id
        and ("run_id" not in payload or payload.get("run_id") == run_id)
        and type(manifest.get("dataset_identity")) is str
        and bool(manifest.get("dataset_identity"))
        and manifest.get("dataset_identity") == payload.get("dataset_identity")
        and type(manifest.get("source_locator")) is str
        and bool(manifest.get("source_locator"))
        and type(manifest.get("source_hash")) is str
        and bool(manifest.get("source_hash"))
        and type(expected) is int
        and expected == payload.get("expected_native_ticket_count")
        and type(digest) is str
        and identity(body) == digest
        and stored_matches
        and ticket_identities_match
    )
    return {"expected_count": expected, "source_bound": source_bound}
