"""Explicit, standalone SQLite replay storage; never migrates a source/results DB."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import stat
from collections.abc import Generator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any, cast

from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayDraw
from lottolab.domain.prize_evaluation import evaluate_lottery_prize
from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataPaths,
    open_database,
    verify_schema_read_only,
)

JsonObject = dict[str, Any]


def _as_json_object(value: object) -> JsonObject | None:
    if type(value) is not dict:
        return None
    entries = cast(dict[object, object], value)
    normalized: JsonObject = {}
    for key, item in entries.items():
        if not isinstance(key, str):
            return None
        normalized[key] = item
    return normalized


def canonical_json(value: object) -> str:
    """Hash the same JSON representation that is persisted, including key coercion."""
    normalized = json.loads(json.dumps(value, default=_json_default, allow_nan=False))
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _json_default(value: object) -> str:
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def identity(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()

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
                        source.get("training_status", "NOT_TRAINABLE"),
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
                self._insert_result_children(connection, result, run_id)
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
    def _insert_result_children(
        connection: sqlite3.Connection, result: JsonObject, run_id: str
    ) -> None:
        raw_tickets = result.get("predicted_tickets", [])
        raw_hits = result.get("hit_details", [])
        if type(raw_tickets) is not list or type(raw_hits) is not list:
            raise ValueError("tickets and hit details must be arrays")
        ticket_values = cast(list[object], raw_tickets)
        hit_values = cast(list[object], raw_hits)
        expected_identity = {
            "lottery_type": result.get("lottery_type"),
            "run_id": run_id,
            "target_draw_id": result.get("target_draw_id"),
            "strategy_id": result.get("strategy_id"),
            "strategy_version": result.get("strategy_version"),
        }
        ticket_positions: set[int] = set()
        validated_tickets: list[tuple[int, JsonObject]] = []
        for raw_ticket in ticket_values:
            ticket = _as_json_object(raw_ticket)
            if ticket is None:
                raise ValueError("ticket identity must be an object")
            position = ticket.get("ticket_position")
            if type(position) is not int or position < 1 or position in ticket_positions:
                raise ValueError("ticket positions must be unique positive integers")
            if not _ticket_identity_matches(ticket, expected_identity, position):
                raise ValueError("ticket identity conflicts with replay cell")
            ticket_positions.add(position)
            validated_tickets.append((position, ticket))

        hits_by_position: dict[int, JsonObject] = {}
        for raw_hit in hit_values:
            hit = _as_json_object(raw_hit)
            if hit is None:
                raise ValueError("ticket evaluation identity must be an object")
            position = hit.get("ticket_position")
            if type(position) is not int:
                # Historical rows without position IDs cannot be safely paired by order.
                continue
            if position not in ticket_positions:
                raise ValueError("ticket evaluation has no matching ticket position")
            if position in hits_by_position:
                raise ValueError("duplicate ticket evaluation identity")
            if not _ticket_identity_matches(hit, expected_identity, position):
                raise ValueError("ticket evaluation identity conflicts with replay cell")
            hits_by_position[position] = hit
        for position, ticket in validated_tickets:
            hit = hits_by_position.get(position, {})
            main_numbers: object = ticket["main_numbers"]
            special_number: object = ticket.get("special_number")
            zone1_hits: object = hit.get("zone1_hits")
            zone2_hit: object = hit.get("zone2_hit")
            prize_tier: object = hit.get("prize_tier")
            if zone1_hits is not None and type(zone1_hits) is not int:
                raise ValueError("main hit count must be an integer or null")
            if zone2_hit is None:
                stored_zone2_hit: int | None = None
            elif type(zone2_hit) is bool:
                stored_zone2_hit = int(zone2_hit)
            elif type(zone2_hit) is int:
                stored_zone2_hit = zone2_hit
            else:
                raise ValueError("special hit must be a boolean, integer, or null")
            if prize_tier is not None and not isinstance(prize_tier, str):
                raise ValueError("prize tier must be a string or null")
            connection.execute(
                "INSERT OR IGNORE INTO replay_backfill_tickets VALUES(?,?,?,?,?,?,?)",
                (
                    result["cell_identity"],
                    position,
                    canonical_json(main_numbers),
                    canonical_json(
                        [] if special_number is None else [special_number]
                    ),
                    zone1_hits,
                    stored_zone2_hit,
                    prize_tier,
                ),
            )
        training = result.get("training", {})
        connection.execute(
            "INSERT OR REPLACE INTO replay_backfill_training VALUES(?,?,?,?,?,?,?,?)",
            (
                result["cell_identity"],
                training.get("training_status", "NOT_TRAINABLE"),
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

    def list_runs(self, lottery_type: str | None = None) -> list[JsonObject]:
        """List persisted run identities without scanning replay cells."""
        with self._connect() as connection:
            run_rows = cast(
                list[tuple[str, str, int, str]],
                connection.execute(
                    "SELECT run_id,manifest_json,expected_cells,created_at "
                    "FROM replay_backfill_runs ORDER BY created_at DESC,run_id"
                ).fetchall(),
            )
            source_rows = cast(
                list[tuple[str, str, str, str, str | None, int]],
                connection.execute(
                    "SELECT run_id,source_identity,source_kind,source_locator,source_hash,"
                    "artifact_only FROM replay_backfill_sources "
                    "ORDER BY run_id,source_identity"
                ).fetchall(),
            )

        sources_by_run: dict[str, list[JsonObject]] = {}
        for (
            source_run_id,
            source_identity,
            source_kind,
            source_locator,
            source_hash,
            artifact_only,
        ) in source_rows:
            sources_by_run.setdefault(source_run_id, []).append(
                {
                    "source_identity": source_identity,
                    "source_kind": source_kind,
                    "source_locator": source_locator,
                    "source_hash": source_hash,
                    "artifact_only": bool(artifact_only),
                }
            )

        items: list[JsonObject] = []
        for run_id, manifest_json, expected_cells, created_at in run_rows:
            manifest = _as_json_object(json.loads(manifest_json))
            if manifest is None:
                raise ValueError("run manifest is invalid")
            manifest_run_id = manifest.get("run_id")
            if manifest_run_id is not None and manifest_run_id != run_id:
                raise ValueError("run manifest identity does not match stored run")

            manifest_lottery_type = manifest.get("lottery_type")
            if lottery_type is not None and manifest_lottery_type != lottery_type:
                continue
            item_lottery_type = (
                manifest_lottery_type if isinstance(manifest_lottery_type, str) else None
            )
            sources = sources_by_run.get(run_id, [])
            single_source = sources[0] if len(sources) == 1 else {}
            manifest_status = manifest.get("status", manifest.get("run_status"))
            status = (
                manifest_status
                if isinstance(manifest_status, str) and manifest_status.strip()
                else "UNKNOWN"
            )
            status_counts = _as_json_object(manifest.get("status_counts"))
            raw_target_count = manifest.get("target_draw_count")
            target_draw_count = (
                raw_target_count
                if type(raw_target_count) is int and raw_target_count >= 0
                else None
            )
            execution_version = manifest.get("execution_version")
            dataset_identity = manifest.get("dataset_identity")
            manifest_source_identity = manifest.get("source_identity")
            manifest_source_kind = manifest.get("source_kind")
            manifest_source_locator = manifest.get("source_locator")
            manifest_source_hash = manifest.get("source_hash")
            items.append(
                {
                    "run_id": run_id,
                    "lottery_type": item_lottery_type,
                    "created_at": created_at,
                    "execution_version": (
                        execution_version if isinstance(execution_version, str) else None
                    ),
                    "dataset_identity": (
                        dataset_identity if isinstance(dataset_identity, str) else None
                    ),
                    "source_identity": single_source.get(
                        "source_identity",
                        manifest_source_identity
                        if isinstance(manifest_source_identity, str)
                        else None,
                    ),
                    "source_kind": single_source.get(
                        "source_kind",
                        manifest_source_kind
                        if isinstance(manifest_source_kind, str)
                        else None,
                    ),
                    "source_locator": single_source.get(
                        "source_locator",
                        manifest_source_locator
                        if isinstance(manifest_source_locator, str)
                        else None,
                    ),
                    "source_hash": single_source.get(
                        "source_hash",
                        manifest_source_hash
                        if isinstance(manifest_source_hash, str)
                        else None,
                    ),
                    "sources": sources,
                    "target_draw_count": target_draw_count,
                    "expected_cell_count": expected_cells,
                    "status": status,
                    "status_counts": status_counts,
                }
            )
        return items

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

    def _scope_target_ids(
        self,
        run_id: str,
        lottery_type: str,
        manifest: JsonObject,
        *,
        from_date: str | None,
        to_date: str | None,
        period: int | None,
    ) -> list[str]:
        raw_targets = manifest.get("targets")
        if type(raw_targets) is list:
            targets: list[object] = cast(list[object], raw_targets)
        else:
            raw_target_ids = manifest.get("target_draw_ids")
            if type(raw_target_ids) is not list:
                raise ValueError("run manifest target list is invalid")
            selected_ids = {
                str(draw_id) for draw_id in cast(list[object], raw_target_ids)
            }
            with self._connect() as connection:
                source_targets = cast(
                    list[tuple[object, object]],
                    connection.execute(
                        "SELECT target_draw_id,target_draw_date FROM replay_backfill_targets "
                        "WHERE run_id=? AND lottery_type=?",
                        (run_id, lottery_type),
                    ).fetchall(),
                )
                cell_targets = cast(
                    list[tuple[object, object]],
                    connection.execute(
                        "SELECT DISTINCT c.target_draw_id,c.target_draw_date "
                        "FROM replay_backfill_cells c JOIN replay_backfill_run_cells r "
                        "USING(cell_identity) WHERE r.run_id=? AND c.lottery_type=?",
                        (run_id, lottery_type),
                    ).fetchall(),
                )
            dates_by_id: dict[str, str] = {}
            for draw_id_value, draw_date_value in (*source_targets, *cell_targets):
                if not isinstance(draw_id_value, str) or not isinstance(draw_date_value, str):
                    raise ValueError("persisted target identity is invalid")
                dates_by_id[draw_id_value] = draw_date_value
            if {draw_id for draw_id in selected_ids if draw_id in dates_by_id} != selected_ids:
                raise ValueError("run target dates are incomplete in persisted source rows")
            targets = [
                {"draw_number": draw_id, "draw_date": dates_by_id[draw_id]}
                for draw_id in selected_ids
            ]
        scoped: list[tuple[str, int, str]] = []
        for raw_target in targets:
            target = _as_json_object(raw_target)
            if target is None:
                raise ValueError("run manifest target is invalid")
            raw_draw_id: object = target.get("draw_number", "")
            draw_id = str(raw_draw_id)
            draw_date: object = target.get("draw_date")
            if not draw_id or type(draw_date) is not str:
                raise ValueError("run manifest target identity is invalid")
            target_date = draw_date
            date.fromisoformat(target_date)
            if from_date is not None and target_date < from_date:
                continue
            if to_date is not None and target_date > to_date:
                continue
            scoped.append((target_date, int(draw_id), draw_id))
        scoped.sort(reverse=True)
        if period is not None:
            scoped = scoped[:period]
        return [draw_id for _, _, draw_id in scoped]

    def backfill_coverage(
        self,
        lottery_type: str,
        *,
        run_id: str | None = None,
        strategy_id: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        period: int | None = None,
    ) -> JsonObject | None:
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
            return None
        manifest = self.run_manifest(selected_run_id)
        if manifest.get("lottery_type") != lottery_type:
            raise ValueError("run lottery type does not match query")
        target_ids = self._scope_target_ids(
            selected_run_id,
            lottery_type,
            manifest,
            from_date=from_date,
            to_date=to_date,
            period=period,
        )
        raw_strategies = manifest.get("strategies", [])
        if type(raw_strategies) is not list:
            raise ValueError("run manifest strategy list is invalid")
        strategy_ids: list[str] = []
        for raw_strategy in cast(list[object], raw_strategies):
            strategy = _as_json_object(raw_strategy)
            if strategy is None:
                raise ValueError("run manifest strategy identity is invalid")
            selected_strategy_id: object = strategy.get("strategy_id")
            if type(selected_strategy_id) is not str:
                raise ValueError("run manifest strategy identity is invalid")
            if strategy_id is None or selected_strategy_id == strategy_id:
                strategy_ids.append(selected_strategy_id)
        with self._connect() as connection:
            statuses: dict[str, int] = {}
            strategy_counts: dict[str, int] = {}
            if target_ids and strategy_ids:
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
                statuses = dict(
                    connection.execute(
                        "SELECT c.execution_status,COUNT(*) FROM replay_backfill_cells c "
                        "JOIN replay_backfill_run_cells r USING(cell_identity) "
                        f"WHERE {where} GROUP BY c.execution_status",
                        params,
                    )
                )
                strategy_counts = dict(
                    connection.execute(
                        "SELECT c.strategy_id,COUNT(*) FROM replay_backfill_cells c "
                        "JOIN replay_backfill_run_cells r USING(cell_identity) "
                        f"WHERE {where} AND c.execution_status='COMPLETE' "
                        "GROUP BY c.strategy_id",
                        params,
                    )
                )
        target_count = len(target_ids)
        expected_strategy_count = len(strategy_ids)
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
                selected_strategy_id
                for selected_strategy_id in strategy_ids
                if strategy_counts.get(selected_strategy_id, 0) < target_count
            ),
            "run_id": selected_run_id,
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

    def strategy_history_snapshot(
        self,
        lottery_type: str,
        run_id: str | None = None,
    ) -> JsonObject:
        """Return one selected-run snapshot without merging results across runs."""

        selection_rule = (
            "LATEST_RUN_BY_CREATED_AT_PER_LOTTERY_TYPE"
            if run_id is None
            else "EXPLICIT_RUN_ID"
        )
        with self._connect() as connection:
            connection.execute("BEGIN")
            selected: tuple[str, JsonObject, str] | None = None
            if run_id is None:
                run_rows = cast(
                    list[tuple[str, str, str]],
                    connection.execute(
                        "SELECT run_id,manifest_json,created_at FROM replay_backfill_runs "
                        "ORDER BY created_at DESC,run_id"
                    ).fetchall(),
                )
                for candidate_run_id, manifest_json, created_at in run_rows:
                    manifest_value = json.loads(manifest_json)
                    if not isinstance(manifest_value, dict):
                        continue
                    manifest = cast(JsonObject, manifest_value)
                    if manifest.get("lottery_type") == lottery_type:
                        selected = (candidate_run_id, manifest, created_at)
                        break
            else:
                run_row = connection.execute(
                    "SELECT manifest_json,created_at FROM replay_backfill_runs WHERE run_id=?",
                    (run_id,),
                ).fetchone()
                if run_row is None:
                    raise KeyError("run not found")
                manifest_value = json.loads(run_row[0])
                manifest = _as_json_object(manifest_value)
                if manifest is None:
                    raise ValueError("run manifest is invalid")
                manifest_run_id = manifest.get("run_id")
                if manifest_run_id is not None and manifest_run_id != run_id:
                    raise ValueError("run manifest identity does not match stored run")
                if manifest.get("lottery_type") != lottery_type:
                    raise ValueError("run lottery type does not match query")
                selected = (run_id, manifest, str(run_row[1]))
            if selected is None:
                return {
                    "lottery_type": lottery_type,
                    "run_id": None,
                    "selection_rule": selection_rule,
                    "created_at": None,
                    "run_source": {
                        "identity_status": "UNKNOWN",
                        "source_identity": None,
                        "source_kind": None,
                        "source_locator": None,
                        "source_hash": None,
                        "artifact_only": None,
                    },
                    "selected_strategies": [],
                    "strategy_inventory": [],
                    "cell_status_counts": [],
                }

            run_id, manifest, created_at = selected
            inventory_rows = cast(
                list[tuple[str, str, str, str, str, str, str, int, int, str, str]],
                connection.execute(
                    "SELECT lottery_type,strategy_id,strategy_version,display_name,"
                    "lifecycle_status,data_status,source_kind,executable,available_target_count,"
                    "training_status,source_identity FROM replay_backfill_strategy_inventory "
                    "WHERE run_id=? AND lottery_type=? ORDER BY strategy_id,strategy_version",
                    (run_id, lottery_type),
                ).fetchall(),
            )
            cell_rows = cast(
                list[tuple[str, str, str, int, int, int]],
                connection.execute(
                    "SELECT c.strategy_id,c.strategy_version,c.execution_status,"
                    "COUNT(DISTINCT c.cell_identity),COUNT(t.ticket_position),"
                    "COUNT(DISTINCT CASE WHEN c.execution_status='COMPLETE' "
                    "AND t.cell_identity IS NOT NULL THEN c.cell_identity END) "
                    "FROM replay_backfill_cells c "
                    "JOIN replay_backfill_run_cells r USING(cell_identity) "
                    "LEFT JOIN replay_backfill_tickets t USING(cell_identity) "
                    "WHERE r.run_id=? AND c.lottery_type=? "
                    "GROUP BY c.strategy_id,c.strategy_version,c.execution_status "
                    "ORDER BY c.strategy_id,c.strategy_version,c.execution_status",
                    (run_id, lottery_type),
                ).fetchall(),
            )
            dataset_identity_value = manifest.get("dataset_identity")
            dataset_identity = (
                dataset_identity_value if isinstance(dataset_identity_value, str) else None
            )
            source_row: tuple[str, str, str, str | None, int] | None = None
            if dataset_identity is not None:
                source_row = cast(
                    tuple[str, str, str, str | None, int] | None,
                    connection.execute(
                        "SELECT source_identity,source_kind,source_locator,source_hash,"
                        "artifact_only FROM replay_backfill_sources "
                        "WHERE run_id=? AND source_identity=?",
                        (run_id, dataset_identity),
                    ).fetchone(),
                )

        source_status = "UNKNOWN"
        source: JsonObject = {
            "identity_status": source_status,
            "source_identity": dataset_identity,
            "source_kind": None,
            "source_locator": None,
            "source_hash": None,
            "artifact_only": None,
        }
        if source_row is not None:
            source_identity, source_kind, source_locator, source_hash, artifact_only = source_row
            expected_locator = manifest.get("source_locator")
            expected_hash = manifest.get("source_hash")
            identity_matches = source_identity == dataset_identity
            locator_matches = (
                not isinstance(expected_locator, str)
                or not expected_locator
                or expected_locator == source_locator
            )
            hash_matches = (
                not isinstance(expected_hash, str)
                or not expected_hash
                or expected_hash == source_hash
            )
            if not identity_matches or not locator_matches or not hash_matches or artifact_only:
                source_status = "UNTRUSTED"
            elif source_locator and source_hash:
                source_status = "VERIFIED"
            source = {
                "identity_status": source_status,
                "source_identity": source_identity,
                "source_kind": source_kind,
                "source_locator": source_locator,
                "source_hash": source_hash,
                "artifact_only": bool(artifact_only),
            }

        manifest_strategies_value = manifest.get("strategies", [])
        selected_strategies: list[JsonObject] = []
        if isinstance(manifest_strategies_value, list):
            for strategy_value in cast(list[object], manifest_strategies_value):
                if not isinstance(strategy_value, dict):
                    continue
                strategy = cast(JsonObject, strategy_value)
                strategy_id = strategy.get("strategy_id")
                strategy_version = strategy.get("strategy_version")
                if isinstance(strategy_id, str) and isinstance(strategy_version, str):
                    selected_strategies.append(
                        {"strategy_id": strategy_id, "strategy_version": strategy_version}
                    )
        manifest_targets = manifest.get("targets")
        target_ids = manifest.get("target_draw_ids")
        target_count = (
            len(cast(list[object], manifest_targets))
            if isinstance(manifest_targets, list)
            else (len(cast(list[object], target_ids)) if isinstance(target_ids, list) else 0)
        )

        return {
            "lottery_type": lottery_type,
            "run_id": run_id,
            "selection_rule": selection_rule,
            "created_at": created_at,
            "dataset_identity": dataset_identity,
            "execution_version": manifest.get("execution_version"),
            "target_count": target_count,
            "run_source": source,
            "selected_strategies": selected_strategies,
            "strategy_inventory": [
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
                for row in inventory_rows
            ],
            "cell_status_counts": [
                {
                    "strategy_id": row[0],
                    "strategy_version": row[1],
                    "execution_status": row[2],
                    "cell_count": row[3],
                    "ticket_count": row[4],
                    "saved_prediction_cell_count": row[5],
                }
                for row in cell_rows
            ],
        }

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
        target_ids = self._scope_target_ids(
            selected_run_id,
            lottery_type,
            manifest,
            from_date=from_date,
            to_date=to_date,
            period=period,
        )
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
        with self._connect() as connection:
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
                "c.strategy_version,c.cell_identity,c.lottery_type FROM replay_backfill_cells c "
                "JOIN replay_backfill_run_cells r USING(cell_identity) "
                f"WHERE {page_where} ORDER BY c.target_draw_date,CAST(c.target_draw_id AS INTEGER),"
                "c.strategy_id,c.strategy_version,c.cell_identity LIMIT ?",
                (*page_params, limit + 1),
            ).fetchall()
            output_rows: list[JsonObject] = []
            for row in rows:
                payload = json.loads(row[0])
                source_row = connection.execute(
                    "SELECT source_identity,source_kind,source_locator,source_hash,artifact_only "
                    "FROM replay_backfill_sources WHERE run_id=? AND source_identity=?",
                    (selected_run_id, f"causal-history:{row[5]}"),
                ).fetchone()
                cutoff_source = (
                    None
                    if source_row is None
                    else {
                        "source_identity": source_row[0],
                        "source_kind": source_row[1],
                        "source_locator": source_row[2],
                        "source_hash": source_row[3],
                        "artifact_only": bool(source_row[4]),
                    }
                )
                output_rows.append(
                    {
                        "payload": payload,
                        "identity": {
                            "lottery_type": row[6],
                            "run_id": selected_run_id,
                            "target_draw_id": row[2],
                            "target_draw_date": row[1],
                            "strategy_id": row[3],
                            "strategy_version": row[4],
                            "cell_identity": row[5],
                        },
                        "cutoff_source": cutoff_source,
                        "key": [row[1], int(row[2]), row[3], row[4], row[5]],
                    }
                )
        return {
            "run_id": selected_run_id,
            "total_count": total,
            "rows": output_rows,
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


def _ticket_identity_matches(
    item: JsonObject, cell_identity: JsonObject, ticket_position: int
) -> bool:
    """Check any supplied identity against its enclosing persisted cell."""
    for key, expected in cell_identity.items():
        if key in item and item[key] != expected:
            return False
    nested_identity = item.get("identity")
    if nested_identity is not None:
        if type(nested_identity) is not dict:
            return False
        nested = cast(JsonObject, nested_identity)
        if any(nested.get(key) != expected for key, expected in cell_identity.items()):
            return False
        if nested.get("ticket_position") != ticket_position:
            return False
    return True
