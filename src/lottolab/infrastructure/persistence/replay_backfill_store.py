"""Explicit, standalone SQLite replay storage; never migrates a source/results DB."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import sqlite3
import stat
from collections.abc import Generator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any, TypedDict, TypeGuard, cast

from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import (
    ReplayDraw,
    SourceHistoryProvenanceStatus,
    parse_source_history_provenance_status,
)
from lottolab.domain.lottery_rules import LOTTERY_RULE_CONTRACTS, LotteryRuleContract
from lottolab.domain.prize_evaluation import evaluate_lottery_prize
from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataPaths,
    open_database,
    verify_schema_read_only,
)
from lottolab.infrastructure.persistence.project_database_paths import (
    is_project_database_boundary,
    is_project_scratch_database_boundary,
    project_database_directory,
    require_project_database_write_ready,
)
from lottolab.strategies.catalog import production_catalog

JsonObject = dict[str, Any]


def _is_non_bool_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_string(value: object) -> TypeGuard[str]:
    return isinstance(value, str)


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
_FIXED_K7_TICKET_COUNT = 7


class _TicketGroupDetails(TypedDict):
    ticket_count: int
    ticket_positions: list[int]
    valid: bool


def _saved_ticket_group_details(
    payload: JsonObject,
    saved_rows: list[tuple[object, ...]],
    *,
    lottery_type: str,
) -> _TicketGroupDetails:
    """Validate saved native positions and ticket groups without deduplicating tickets."""
    rule = LOTTERY_RULE_CONTRACTS[LotteryType(lottery_type)]
    raw_tickets: object = payload.get("predicted_tickets")
    payload_by_position: dict[int, tuple[tuple[int, ...], tuple[int, ...]]] = {}
    valid = type(raw_tickets) is list

    if type(raw_tickets) is list:
        for raw_ticket in cast(list[object], raw_tickets):
            if type(raw_ticket) is not dict:
                valid = False
                continue
            ticket = cast(JsonObject, raw_ticket)
            position = ticket.get("ticket_position")
            raw_main: object = ticket.get("main_numbers")
            special_number: object = ticket.get("special_number")
            if (
                type(position) is not int
                or position < 1
                or position in payload_by_position
                or type(raw_main) is not list
                or any(type(number) is not int for number in cast(list[object], raw_main))
                or (special_number is not None and type(special_number) is not int)
            ):
                valid = False
                continue
            main_numbers = tuple(cast(list[int], raw_main))
            special_numbers = () if special_number is None else (special_number,)
            payload_by_position[position] = (main_numbers, special_numbers)
            if not _ticket_numbers_match_rule(main_numbers, special_numbers, rule):
                valid = False

    saved_by_position: dict[int, tuple[tuple[int, ...], tuple[int, ...]]] = {}
    for raw_position, raw_main_json, raw_special_json in saved_rows:
        if type(raw_position) is not int or raw_position < 1 or raw_position in saved_by_position:
            valid = False
            continue
        try:
            main_values: object = json.loads(cast(str, raw_main_json))
            special_values: object = json.loads(cast(str, raw_special_json))
        except (TypeError, ValueError):
            valid = False
            continue
        if (
            type(main_values) is not list
            or any(type(number) is not int for number in cast(list[object], main_values))
            or type(special_values) is not list
            or any(type(number) is not int for number in cast(list[object], special_values))
        ):
            valid = False
            continue
        main_numbers = tuple(cast(list[int], main_values))
        special_numbers = tuple(cast(list[int], special_values))
        saved_by_position[raw_position] = (main_numbers, special_numbers)
        if not _ticket_numbers_match_rule(main_numbers, special_numbers, rule):
            valid = False

    ticket_positions = sorted(saved_by_position)
    payload_ticket_count = (
        len(cast(list[object], raw_tickets)) if isinstance(raw_tickets, list) else 0
    )
    if (
        ticket_positions != list(range(1, len(ticket_positions) + 1))
        or payload_by_position != saved_by_position
        or len(payload_by_position) != payload_ticket_count
    ):
        valid = False
    return {
        "ticket_count": len(saved_rows),
        "ticket_positions": ticket_positions,
        "valid": valid,
    }


def _ticket_numbers_match_rule(
    main_numbers: tuple[int, ...],
    special_numbers: tuple[int, ...],
    rule: LotteryRuleContract,
) -> bool:
    # BIG_LOTTO's special number belongs to the draw, not to each predicted ticket.
    ticket_special_count = (
        0 if rule.lottery_type is LotteryType.BIG_LOTTO else rule.special_number_count
    )
    return not (
        len(main_numbers) != rule.main_number_count
        or any(
            not rule.main_number_min <= number <= rule.main_number_max for number in main_numbers
        )
        or (rule.main_numbers_unique and len(set(main_numbers)) != len(main_numbers))
        or main_numbers != tuple(sorted(main_numbers))
        or len(special_numbers) != ticket_special_count
        or any(
            not rule.special_number_min <= number <= rule.special_number_max
            for number in special_numbers
        )
        or (rule.special_numbers_unique and len(set(special_numbers)) != len(special_numbers))
        or (
            not rule.main_special_overlap_allowed
            and set(main_numbers).intersection(special_numbers)
        )
    )


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
    connection.execute(f'INSERT INTO "{destination}" ({quoted}) SELECT {quoted} FROM "{source}"')


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
    run_cells_sql = (
        _schema_table_sql("replay_backfill_run_cells")
        .replace(
            "CREATE TABLE replay_backfill_run_cells (",
            "CREATE TABLE replay_backfill_run_cells_v2 (",
            1,
        )
        .replace(
            "REFERENCES replay_backfill_cells(cell_identity)",
            "REFERENCES replay_backfill_cells_v2(cell_identity)",
            1,
        )
    )
    connection.execute(cells_sql)
    connection.execute(run_cells_sql)
    _copy_table_columns(connection, "replay_backfill_cells_v1", "replay_backfill_cells_v2")
    _copy_table_columns(connection, "replay_backfill_run_cells_v1", "replay_backfill_run_cells_v2")
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

    connection.execute("ALTER TABLE replay_backfill_schema RENAME TO replay_backfill_schema_v1")
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
        if (parent / ".git").exists() and not (
            is_project_database_boundary(database, parent)
            or is_project_scratch_database_boundary(database, parent)
        ):
            raise ValueError("database must be outside a Git checkout or inside project scratch")
    if database.exists():
        info = database.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid():
            raise ValueError("database must be an owner-owned regular file without hardlinks")
    return database


@contextmanager
def _acquire_writer_lock(database: Path) -> Generator[None]:
    """Acquire the database's process-wide writer lock without waiting."""
    canonical_directory = project_database_directory()
    if database.is_relative_to(canonical_directory):
        lock_directory = canonical_directory / "locks"
        if lock_directory.is_symlink():
            raise ValueError(f"writer lock directory must not be a symlink: {lock_directory}")
        lock_directory.mkdir(parents=True, exist_ok=True)
    else:
        lock_directory = database.parent

    lock_path = lock_directory / f"{database.name}.writer.lock"
    if lock_path.is_symlink():
        raise ValueError(f"writer lock file must not be a symlink: {lock_path}")
    with lock_path.open("a+b") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise PermissionError(
                f"writer lock is held: {lock_path}; finish or stop the other process "
                "writing this database before retrying"
            ) from exc
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


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
    def official_ranking_data(
        self, lottery_type: str, window: str = "FULL"
    ) -> Generator[tuple[list[JsonObject], Generator[JsonObject]]]:
        """Read target and cell evidence in one consistent, query-only snapshot."""
        window_sizes = {"FULL": None, "RECENT_750": 750, "RECENT_300": 300, "RECENT_50": 50}
        if window not in window_sizes:
            raise ValueError("unsupported ranking window")
        with self._connect() as connection:
            connection.execute("PRAGMA temp_store=MEMORY")
            connection.execute("BEGIN")
            try:
                # A run can store source history in targets; its manifest defines
                # the actual evaluation IDs. Never treat source history as missing.
                manifest_ids: dict[str, set[str]] = {}
                invalid_runs: set[str] = set()
                manifest_dates: dict[tuple[str, str], str] = {}
                manifest_targets: dict[tuple[str, str], JsonObject] = {}
                for run_id, raw_manifest in connection.execute(
                    "SELECT run_id,manifest_json FROM replay_backfill_runs"
                ):
                    try:
                        manifest = json.loads(raw_manifest)
                        if manifest.get("lottery_type") != lottery_type:
                            continue
                        raw_ids = manifest.get("target_draw_ids")
                        raw_targets = manifest.get("targets")
                        if "target_draw_ids" not in manifest and isinstance(raw_targets, list):
                            raw_ids = [
                                t.get("draw_number") for t in raw_targets if isinstance(t, dict)
                            ]
                        if not isinstance(raw_ids, list) or not raw_ids:
                            invalid_runs.add(run_id)
                            manifest_ids[run_id] = set()
                            continue
                        valid_ids = [v for v in raw_ids if isinstance(v, str) and v]
                        if len(valid_ids) != len(raw_ids) or len(set(valid_ids)) != len(raw_ids):
                            invalid_runs.add(run_id)
                        manifest_ids[run_id] = set(valid_ids)
                        if "targets" in manifest:
                            if not isinstance(raw_targets, list):
                                invalid_runs.add(run_id)
                            else:
                                listed = [
                                    t.get("draw_number") if isinstance(t, dict) else None
                                    for t in raw_targets
                                ]
                                if (
                                    len(listed) != len(set(v for v in listed if isinstance(v, str)))
                                    or set(v for v in listed if isinstance(v, str))
                                    != set(valid_ids)
                                    or any(
                                        not isinstance(t, dict)
                                        or not isinstance(t.get("draw_date"), str)
                                        for t in raw_targets
                                    )
                                ):
                                    invalid_runs.add(run_id)
                        for target in raw_targets if isinstance(raw_targets, list) else []:
                            if isinstance(target, dict) and isinstance(
                                target.get("draw_date"), str
                            ):
                                key = (run_id, str(target.get("draw_number")))
                                manifest_dates[key] = target["draw_date"]
                                manifest_targets[key] = target
                    except (ValueError, TypeError, AttributeError):
                        continue
                source: dict[tuple[str, str], JsonObject] = {}
                for row in connection.execute(
                    "SELECT run_id,target_draw_id,target_draw_date,actual_main_numbers_json,"
                    "actual_special_numbers_json,source_identity FROM replay_backfill_targets "
                    "WHERE lottery_type=?",
                    (lottery_type,),
                ):
                    run_id, draw_id, draw_date, main, special, source_identity = row
                    if draw_id in manifest_ids.get(run_id, set()):
                        source[(run_id, draw_id)] = {
                            "run_id": run_id,
                            "target_draw_id": draw_id,
                            "target_draw_date": draw_date,
                            "main": main,
                            "special": special,
                            "source_identity": source_identity,
                        }
                # Verify target rows against every manifest field that exists.
                # A dated manifest need not duplicate the draw numbers if the
                # formal target row has complete, source-bound evidence.
                for (run_id, draw_id), manifest_target in manifest_targets.items():
                    if draw_id not in manifest_ids.get(run_id, set()):
                        continue
                    old = source.get((run_id, draw_id))
                    candidate = {
                        "run_id": run_id,
                        "target_draw_id": draw_id,
                        "target_draw_date": manifest_target["draw_date"],
                        "main": None,
                        "special": None,
                        "target_unverified": True,
                    }
                    if old is not None:
                        try:
                            date.fromisoformat(manifest_target["draw_date"])
                            main = json.loads(old["main"])
                            special = json.loads(old["special"])
                            limit, count = (
                                (39, 5)
                                if lottery_type == "DAILY_539"
                                else ((49, 6) if lottery_type == "BIG_LOTTO" else (38, 6))
                            )
                            valid = (
                                isinstance(main, list)
                                and len(main) == count
                                and all(type(n) is int and 1 <= n <= limit for n in main)
                                and len(set(main)) == count
                                and isinstance(special, list)
                                and all(type(n) is int for n in special)
                                and old["target_draw_date"] == manifest_target["draw_date"]
                                and isinstance(old["source_identity"], str)
                                and bool(old["source_identity"])
                            )
                            if lottery_type == "DAILY_539":
                                valid = valid and special == []
                            elif lottery_type == "BIG_LOTTO":
                                valid = (
                                    valid
                                    and len(special) == 1
                                    and 1 <= special[0] <= 49
                                    and special[0] not in main
                                )
                            else:
                                valid = valid and len(special) == 1 and 1 <= special[0] <= 8
                            if "main_numbers" in manifest_target:
                                valid = valid and sorted(manifest_target["main_numbers"]) == sorted(
                                    main
                                )
                            if "special_numbers" in manifest_target:
                                valid = valid and sorted(
                                    manifest_target["special_numbers"]
                                ) == sorted(special)
                            if "source_identity" in manifest_target:
                                valid = (
                                    valid
                                    and manifest_target["source_identity"] == old["source_identity"]
                                )
                            if valid:
                                candidate.update(
                                    {
                                        "main": json.dumps(main),
                                        "special": json.dumps(special),
                                        "target_unverified": False,
                                    }
                                )
                        except (ValueError, TypeError, KeyError, IndexError):
                            pass
                    source[(run_id, draw_id)] = candidate
                # A target row without a matching manifest draw record is not
                # independently source-bound. Do not infer validity from IDs alone.
                for key, value in source.items():
                    if key not in manifest_targets:
                        value.update({"main": None, "special": None, "target_unverified": True})
                # Missing target evidence stays UNKNOWN. Dates from persisted cells
                # let old manifests with IDs only participate in window selection.
                for run_id, ids in manifest_ids.items():
                    missing_ids = ids - {draw for r, draw in source if r == run_id}
                    undated = {draw for draw in missing_ids if (run_id, draw) not in manifest_dates}
                    if undated:
                        for draw_id, draw_date in connection.execute(
                            "SELECT c.target_draw_id,c.target_draw_date "
                            "FROM replay_backfill_run_cells r "
                            "JOIN replay_backfill_cells c USING(cell_identity) "
                            "WHERE r.run_id=? AND c.lottery_type=?",
                            (run_id, lottery_type),
                        ):
                            if draw_id in undated:
                                manifest_dates[(run_id, draw_id)] = draw_date
                    for draw_id in missing_ids:
                        source[(run_id, draw_id)] = {
                            "run_id": run_id,
                            "target_draw_id": draw_id,
                            "target_draw_date": manifest_dates.get((run_id, draw_id), ""),
                            "main": None,
                            "special": None,
                            "target_unverified": True,
                        }
                targets = []
                unresolved_runs: set[str] = set(invalid_runs)
                for run_id in manifest_ids:
                    rows = [v for (r, _), v in source.items() if r == run_id]
                    for target in rows:
                        try:
                            date.fromisoformat(target["target_draw_date"])
                        except (TypeError, ValueError):
                            unresolved_runs.add(run_id)
                    rows.sort(key=lambda t: (t["target_draw_date"], t["target_draw_id"]))
                    size = window_sizes[window]
                    if run_id in unresolved_runs:
                        for target in rows:
                            target["window_unresolved"] = True
                        targets.extend(rows)
                    else:
                        targets.extend(rows if size is None else rows[-size:])
                target_ids_by_run_lists: dict[str, list[str]] = {}
                for target in targets:
                    target_ids_by_run_lists.setdefault(target["run_id"], []).append(
                        target["target_draw_id"]
                    )
                target_ids_by_run = {
                    run_id: tuple(target_ids)
                    for run_id, target_ids in target_ids_by_run_lists.items()
                }

                del source, manifest_targets, manifest_dates

                def cells() -> Generator[JsonObject]:
                    columns = (
                        "cell_identity",
                        "run_id",
                        "strategy_id",
                        "strategy_version",
                        "execution_version",
                        "dataset_identity",
                        "target_draw_id",
                        "target_draw_date",
                        "execution_status",
                    )

                    def emit_joined_cells(
                        cursor: sqlite3.Cursor, run_id: str
                    ) -> Generator[JsonObject]:
                        current_id: str | None = None
                        current: JsonObject | None = None
                        tickets: list[tuple[object, ...]] = []

                        def finish(cell: JsonObject, saved: list[tuple[object, ...]]) -> JsonObject:
                            try:
                                payload = json.loads(cell.pop("payload_json"))
                                expected = payload.get("expected_native_ticket_count")
                                cell["payload_winning_present"] = "winning_numbers" in payload
                                cell["payload_winning_numbers"] = payload.get("winning_numbers")
                                details = _saved_ticket_group_details(
                                    payload, saved, lottery_type=lottery_type
                                )
                                cell["ticket_evidence_valid"] = (
                                    details["valid"]
                                    and type(expected) is int
                                    and expected > 0
                                    and expected == len(saved)
                                )
                            except (ValueError, TypeError, AttributeError, KeyError):
                                cell["ticket_evidence_valid"] = False
                            cell["tickets"] = saved
                            cell["ranking_window_included"] = True
                            return cell

                        while batch := cursor.fetchmany(1000):
                            for row in batch:
                                cell_id = row[0]
                                if current_id is not None and cell_id != current_id:
                                    assert current is not None
                                    yield finish(current, tickets)
                                    tickets = []
                                if cell_id != current_id:
                                    current_id = cell_id
                                    current = dict(zip(columns, row[:9], strict=True))
                                    current["run_id"] = run_id
                                    if run_id in unresolved_runs:
                                        current["scope_status"] = "WINDOW_UNDETERMINED"
                                    current["payload_json"] = row[12]
                                if row[9] is not None:
                                    tickets.append(row[9:12])
                        if current is not None:
                            yield finish(current, tickets)

                    # First stream unlinked cells, using only exact IDs during
                    # this pass; discard the membership set before per-run work.
                    linked_ids: set[str] = set()
                    run_ids: set[str] = set()
                    for run_id, cell_id in connection.execute(
                        "SELECT run_id,cell_identity FROM replay_backfill_run_cells"
                    ):
                        linked_ids.add(cell_id)
                        run_ids.add(run_id)
                    for row in connection.execute(
                        "SELECT c.cell_identity,NULL,c.strategy_id,c.strategy_version,"
                        "c.execution_version,c.dataset_identity,c.target_draw_id,"
                        "c.target_draw_date,c.execution_status FROM replay_backfill_cells c "
                        "NOT INDEXED WHERE c.lottery_type=?",
                        (lottery_type,),
                    ):
                        if row[0] in linked_ids:
                            continue
                        count = connection.execute(
                            "SELECT COUNT(*) FROM replay_backfill_tickets WHERE cell_identity=?",
                            (row[0],),
                        ).fetchone()[0]
                        item = dict(zip(columns, row, strict=True))
                        item.update(
                            {
                                "run_id": "UNLINKED",
                                "scope_status": "UNLINKED",
                                "tickets": [],
                                "ticket_count": count,
                                "ranking_window_included": True,
                            }
                        )
                        yield item
                    del linked_ids

                    # Run groups are contiguous, allowing aggregation to release
                    # period objects as soon as each run finishes.
                    for run_id in sorted(run_ids):
                        identities: set[tuple] = set()
                        rows = connection.execute(
                            "SELECT c.cell_identity,rc.run_id,c.strategy_id,c.strategy_version,"
                            "c.execution_version,c.dataset_identity,c.target_draw_id,"
                            "c.target_draw_date,c.execution_status "
                            "FROM replay_backfill_run_cells rc "
                            "JOIN replay_backfill_cells c ON c.cell_identity=rc.cell_identity "
                            "WHERE rc.run_id=? AND c.lottery_type=? ORDER BY rc.cell_identity",
                            (run_id, lottery_type),
                        )
                        for row in rows:
                            cell_id = row[0]
                            if run_id not in manifest_ids or (
                                run_id in invalid_runs and not manifest_ids[run_id]
                            ):
                                scope_status = "WINDOW_UNDETERMINED"
                            elif row[6] not in manifest_ids.get(run_id, set()):
                                scope_status = "OUTSIDE_MANIFEST"
                            else:
                                identities.add(tuple(row[2:6]))
                                continue
                            count = connection.execute(
                                "SELECT COUNT(*) FROM replay_backfill_tickets "
                                "WHERE cell_identity=?",
                                (cell_id,),
                            ).fetchone()[0]
                            item = dict(zip(columns, row, strict=True))
                            item.update(
                                {
                                    "scope_status": scope_status,
                                    "tickets": [],
                                    "ticket_count": count,
                                    "ranking_window_included": True,
                                }
                            )
                            yield item
                        for strategy, version, execution, dataset in sorted(identities):
                            yield {
                                "cell_identity": (
                                    f"WINDOW_PLACEHOLDER:{run_id}:{strategy}:{version}:"
                                    f"{execution}:{dataset}"
                                ),
                                "run_id": run_id,
                                "scope_status": (
                                    "WINDOW_UNDETERMINED"
                                    if run_id in unresolved_runs
                                    else "MANIFEST"
                                ),
                                "strategy_id": strategy,
                                "strategy_version": version,
                                "execution_version": execution,
                                "dataset_identity": dataset,
                                "target_draw_id": "",
                                "target_draw_date": "",
                                "execution_status": "MISSING",
                                "tickets": [],
                                "ranking_window_included": False,
                            }
                        target_ids = target_ids_by_run.get(run_id, ())
                        for start in range(0, len(target_ids), 700):
                            target_chunk = target_ids[start : start + 700]
                            if not target_chunk:
                                continue
                            target_placeholders = ",".join("?" for _ in target_chunk)
                            cursor = connection.execute(
                                "SELECT c.cell_identity,rc.run_id,c.strategy_id,c.strategy_version,"
                                "c.execution_version,c.dataset_identity,c.target_draw_id,"
                                "c.target_draw_date,c.execution_status,t.ticket_position,"
                                "t.main_numbers_json,t.special_numbers_json,c.payload_json "
                                "FROM replay_backfill_run_cells rc "
                                "JOIN replay_backfill_cells c ON c.cell_identity=rc.cell_identity "
                                "LEFT JOIN replay_backfill_tickets t "
                                "ON t.cell_identity=c.cell_identity "
                                "WHERE rc.run_id=? AND c.lottery_type=? "
                                f"AND c.target_draw_id IN ({target_placeholders}) "
                                "ORDER BY rc.cell_identity,t.ticket_position",
                                (run_id, lottery_type, *target_chunk),
                            )
                            yield from emit_joined_cells(cursor, run_id)

                yield targets, cells()
            finally:
                connection.rollback()

    @contextmanager
    def _connect(self, *, write: bool = False) -> Generator[sqlite3.Connection]:
        database = validate_database_path(self.database)
        if write and self.read_only:
            raise ValueError("read-only store")
        if write:
            require_project_database_write_ready(database)
            with (
                _acquire_writer_lock(database),
                self._open_connection(database, write=True) as connection,
            ):
                yield connection
            return
        with self._open_connection(database, write=False) as connection:
            yield connection

    @contextmanager
    def _open_connection(
        self,
        database: Path,
        *,
        write: bool,
        verify_schema: bool = True,
    ) -> Generator[sqlite3.Connection]:
        """Open a connection; write callers must already hold the writer lock."""
        connection = sqlite3.connect(
            database.as_uri() + "?mode=rw" if write else database.as_uri() + "?mode=ro",
            uri=True,
            timeout=5,
        )
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            if not write:
                connection.execute("PRAGMA query_only=ON")
            if verify_schema:
                self._verify(connection)
            with connection:
                if write:
                    connection.execute("BEGIN IMMEDIATE")
                yield connection
        finally:
            connection.close()

    @contextmanager
    def write_transaction(self) -> Generator[sqlite3.Connection]:
        """Open a guarded, immediate write transaction for bulk store operations."""
        with self._connect(write=True) as connection:
            yield connection

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
        with _acquire_writer_lock(path):
            if not path.exists():
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(fd)
            # A crash before the first schema commit leaves an empty task output.
            # Empty outputs can be initialized on resume; foreign schemas fail closed.
            with self._open_connection(path, write=True, verify_schema=False) as connection:
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
            with self._open_connection(path, write=True) as connection:
                tables = {
                    r[0]
                    for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
                }
                if tables != _TABLES:
                    raise ValueError("output must be a standalone replay backfill database")
                encoded = canonical_json(manifest)
                connection.execute(
                    "INSERT OR IGNORE INTO replay_backfill_runs"
                    "(run_id,manifest_json,expected_cells) "
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
                            source.get("training_status", "UNKNOWN"),
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

    def lookup_many_by_unique_keys(
        self,
        keys: tuple[tuple[str, str, str, str, str, str], ...],
    ) -> dict[tuple[str, str, str, str, str, str], JsonObject]:
        """Find cells by the database's six-column natural key."""
        if not keys:
            return {}
        columns = (
            "lottery_type",
            "strategy_id",
            "strategy_version",
            "execution_version",
            "dataset_identity",
            "target_draw_id",
        )
        found: dict[tuple[str, str, str, str, str, str], JsonObject] = {}
        with self._connect() as connection:
            for offset in range(0, len(keys), 100):
                batch = keys[offset : offset + 100]
                predicate = " OR ".join(
                    "(" + " AND ".join(f'"{column}"=?' for column in columns) + ")" for _ in batch
                )
                parameters = tuple(value for key in batch for value in key)
                rows = connection.execute(
                    f"SELECT {','.join(columns)},payload_json FROM replay_backfill_cells "
                    f"WHERE {predicate}",
                    parameters,
                )
                for row in rows:
                    key = cast(
                        tuple[str, str, str, str, str, str],
                        tuple(row[:6]),
                    )
                    found[key] = json.loads(row[6])
        return found

    def lookup_complete_by_logical_keys(
        self,
        keys: tuple[tuple[str, str, str, str], ...],
    ) -> dict[tuple[str, str, str, str], tuple[JsonObject, ...]]:
        """Find completed results for the same research target across identities."""
        if not keys:
            return {}
        database = validate_database_path(self.database)
        if not database.exists() or database.stat().st_size == 0:
            return {}

        found: dict[tuple[str, str, str, str], list[JsonObject]] = {}
        connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=5)
        try:
            connection.execute("PRAGMA query_only=ON")
            tables = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            if not tables:
                return {}
            if tables not in (_TABLES, _LEGACY_V1_TABLES):
                raise ValueError("output must be a standalone replay backfill database")
            schema_rows = connection.execute(
                "SELECT version,checksum FROM replay_backfill_schema"
            ).fetchall()
            if schema_rows not in (
                [(SCHEMA_VERSION, SCHEMA_CHECKSUM)],
                [(1, LEGACY_V1_SCHEMA_CHECKSUM)],
            ):
                raise ValueError("unsupported replay backfill schema")

            columns = (
                "lottery_type",
                "strategy_id",
                "strategy_version",
                "target_draw_id",
            )
            for offset in range(0, len(keys), 100):
                batch = keys[offset : offset + 100]
                predicate = " OR ".join(
                    "(" + " AND ".join(f'"{column}"=?' for column in columns) + ")" for _ in batch
                )
                parameters = tuple(value for key in batch for value in key)
                rows = connection.execute(
                    "SELECT lottery_type,strategy_id,strategy_version,target_draw_id,"
                    "execution_version,dataset_identity,payload_json "
                    "FROM replay_backfill_cells "
                    f"WHERE execution_status='COMPLETE' AND ({predicate})",
                    parameters,
                )
                for row in rows:
                    key = cast(tuple[str, str, str, str], tuple(row[:4]))
                    payload = _as_json_object(json.loads(row[6]))
                    if payload is None or tuple(
                        payload.get(column)
                        for column in (
                            "lottery_type",
                            "strategy_id",
                            "strategy_version",
                            "target_draw_id",
                            "execution_version",
                            "dataset_identity",
                        )
                    ) != tuple(row[:6]):
                        raise ValueError("COMPLETE replay identity conflicts with stored payload")
                    found.setdefault(key, []).append(payload)
        finally:
            connection.close()
        return {key: tuple(results) for key, results in found.items()}

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
            if "source_history_provenance_status" in result:
                parse_source_history_provenance_status(result["source_history_provenance_status"])
            encoded = canonical_json(result)
            body = {k: v for k, v in result.items() if k != "result_identity"}
            if identity(body) != result["result_identity"]:
                raise ValueError("result digest mismatch")
            encoded_results.append((result, encoded))
        with self._connect(write=True) as connection:
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
                    if "source_history_provenance_status" not in result:
                        raise ValueError(
                            "new replay results require source_history_provenance_status"
                        )
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
                    canonical_json([] if special_number is None else [special_number]),
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
                training.get("training_status", "UNKNOWN"),
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
                        manifest_source_kind if isinstance(manifest_source_kind, str) else None,
                    ),
                    "source_locator": single_source.get(
                        "source_locator",
                        manifest_source_locator
                        if isinstance(manifest_source_locator, str)
                        else None,
                    ),
                    "source_hash": single_source.get(
                        "source_hash",
                        manifest_source_hash if isinstance(manifest_source_hash, str) else None,
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
            manifest = json.loads(manifest_json)
            if (
                manifest.get("lottery_type") == lottery_type
                and "reference_projection" not in manifest
            ):
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
            selected_ids = {str(draw_id) for draw_id in cast(list[object], raw_target_ids)}
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
            statuses.get(status, 0) for status in ("NOT_ELIGIBLE", "TYPED_CLOSURE", "MISSING")
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

    def scan_window_coverage(
        self,
        *,
        lottery_type: str,
        strategies: tuple[tuple[str, str], ...],
        targets: tuple[tuple[str, str], ...],
        limit: int = 100,
        offset: int = 0,
    ) -> JsonObject:
        """Read exact strategy/version coverage for a source-defined draw window."""
        if len(strategies) != 5 or len({strategy_id for strategy_id, _ in strategies}) != 5:
            raise ValueError("coverage scan requires five distinct strategies")
        if not targets or len(targets) > 2500:
            raise ValueError("coverage scan requires between 1 and 2500 source targets")
        if not 1 <= limit <= 250 or offset < 0:
            raise ValueError("invalid coverage scan pagination")
        target_by_id = {draw_id: draw_date for draw_id, draw_date in targets}
        if len(target_by_id) != len(targets):
            raise ValueError("source target identities must be unique")

        strategy_filter = ",".join("?" for _ in strategies)
        earliest = min(draw_date for _, draw_date in targets)
        latest = max(draw_date for _, draw_date in targets)
        catalog = production_catalog()
        native_ticket_bounds: dict[tuple[str, str], tuple[int, int]] = {}
        for strategy_id, strategy_version in strategies:
            try:
                descriptor = catalog.get(strategy_id)
            except KeyError:
                continue
            if (
                descriptor.version == strategy_version
                and LotteryType(lottery_type) in descriptor.lottery_types
            ):
                native_ticket_bounds[(strategy_id, strategy_version)] = (
                    descriptor.native_ticket_count_bounds
                )
        with self._connect() as connection:
            connection.execute("BEGIN")
            rows = connection.execute(
                "SELECT strategy_id,strategy_version,target_draw_id,target_draw_date,"
                "execution_status,execution_version,dataset_identity,payload_json,cell_identity "
                "FROM replay_backfill_cells WHERE lottery_type=? AND target_draw_date>=? "
                f"AND target_draw_date<=? AND strategy_id IN ({strategy_filter}) "
                "ORDER BY target_draw_date,CAST(target_draw_id AS INTEGER),strategy_id,"
                "strategy_version,execution_version,dataset_identity",
                (lottery_type, earliest, latest, *(strategy_id for strategy_id, _ in strategies)),
            ).fetchall()
            cell_ids = [str(row[8]) for row in rows]
            saved_ticket_rows: dict[str, list[tuple[object, ...]]] = {}
            for start in range(0, len(cell_ids), 500):
                batch = cell_ids[start : start + 500]
                placeholders = ",".join("?" for _ in batch)
                ticket_rows = connection.execute(
                    "SELECT cell_identity,ticket_position,main_numbers_json,special_numbers_json "
                    "FROM replay_backfill_tickets "
                    f"WHERE cell_identity IN ({placeholders}) "
                    "ORDER BY cell_identity,ticket_position",
                    batch,
                ).fetchall()
                for ticket_row in ticket_rows:
                    saved_ticket_rows.setdefault(str(ticket_row[0]), []).append(ticket_row[1:])

        cells: dict[tuple[str, str, str], list[JsonObject]] = {}
        other_versions: dict[tuple[str, str], list[JsonObject]] = {}
        expected_versions = dict(strategies)
        orphan_count = 0
        for row in rows:
            strategy_id, strategy_version, draw_id, draw_date = row[:4]
            pair = (str(strategy_id), str(strategy_version))
            if str(draw_id) not in target_by_id or target_by_id[str(draw_id)] != str(draw_date):
                orphan_count += 1
                continue
            payload = json.loads(row[7])
            status = str(row[4])
            cell_identity = str(row[8])
            ticket_details = _saved_ticket_group_details(
                payload,
                saved_ticket_rows.get(cell_identity, []),
                lottery_type=lottery_type,
            )
            bounds = native_ticket_bounds.get(pair)
            native_ticket_set_complete = (
                ticket_details["valid"]
                and bounds is not None
                and bounds[0] <= ticket_details["ticket_count"] <= bounds[1]
            )
            item: JsonObject = {
                "strategy_version": pair[1],
                "execution_status": status,
                "execution_version": str(row[5]),
                "dataset_identity": str(row[6]),
                "ticket_count": ticket_details["ticket_count"],
                "ticket_positions": ticket_details["ticket_positions"],
                "ticket_set_valid": ticket_details["valid"],
                "native_ticket_count_bounds": list(bounds) if bounds is not None else None,
                "fixed_k7_comparison_eligible": (
                    ticket_details["valid"]
                    and ticket_details["ticket_count"] == _FIXED_K7_TICKET_COUNT
                    and status == "COMPLETE"
                ),
                "reason": (
                    payload.get("error_reason")
                    if status != "COMPLETE" and isinstance(payload.get("error_reason"), str)
                    else None
                ),
            }
            if status == "COMPLETE" and bounds is not None and not native_ticket_set_complete:
                item["coverage_status"] = "PARTIAL"
                item["coverage_reason"] = "INCOMPLETE_TICKET_SET"
            if expected_versions.get(pair[0]) == pair[1]:
                cells.setdefault((pair[0], pair[1], str(draw_id)), []).append(item)
            else:
                other_versions.setdefault((pair[0], str(draw_id)), []).append(item)

        scan_rows: list[JsonObject] = []
        status_counts: dict[str, int] = {}
        identity_variants: dict[str, dict[str, set[str]]] = {
            f"{strategy_id}@{strategy_version}": {
                "execution_versions": set(),
                "dataset_identities": set(),
            }
            for strategy_id, strategy_version in strategies
        }
        strategy_counts = {
            f"{strategy_id}@{strategy_version}": {
                "complete": 0,
                "incomplete": 0,
                "fixed_k7_comparison_eligible": 0,
            }
            for strategy_id, strategy_version in strategies
        }
        for draw_id, draw_date in targets:
            for strategy_id, strategy_version in strategies:
                records = cells.get((strategy_id, strategy_version, draw_id), [])
                if not records:
                    records = other_versions.get((strategy_id, draw_id), [])
                    if records:
                        status = "VERSION_MISMATCH"
                        reason = "ONLY_OTHER_STRATEGY_VERSION_SAVED"
                    else:
                        status = "MISSING"
                        reason = "NO_SAVED_CELL"
                elif len(records) > 1:
                    status = "AMBIGUOUS"
                    reason = "MULTIPLE_EXECUTION_OR_DATASET_IDENTITIES"
                else:
                    status = str(records[0]["execution_status"])
                    reason = records[0]["reason"]
                    if status == "COMPLETE" and records[0].get("coverage_status") == "PARTIAL":
                        status = "PARTIAL"
                        reason = "INCOMPLETE_TICKET_SET"
                    if status == "COMPLETE":
                        reason = None
                    elif reason is None:
                        reason = {
                            "FAILED": "EXECUTION_FAILED",
                            "PARTIAL": "INCOMPLETE_TICKET_SET",
                            "NOT_ELIGIBLE": "INSUFFICIENT_HISTORY_OR_NOT_ELIGIBLE",
                            "TYPED_CLOSURE": "TARGET_CLOSED_WITHOUT_REPLAY",
                            "MISSING": "SAVED_CELL_MARKED_MISSING",
                            "ARTIFACT_ONLY": "ARTIFACT_HAS_NO_REPLAY_CELL",
                        }.get(status, "NON_COMPLETE_REPLAY_CELL")
                key = f"{strategy_id}@{strategy_version}"
                if (
                    len(records) == 1
                    and status == "COMPLETE"
                    and records[0].get("fixed_k7_comparison_eligible") is True
                ):
                    strategy_counts[key]["fixed_k7_comparison_eligible"] += 1
                for record in records:
                    if record["strategy_version"] == strategy_version:
                        identity_variants[key]["execution_versions"].add(
                            record["execution_version"]
                        )
                        identity_variants[key]["dataset_identities"].add(record["dataset_identity"])
                complete = status == "COMPLETE"
                strategy_counts[key]["complete" if complete else "incomplete"] += 1
                status_counts[status] = status_counts.get(status, 0) + 1
                if not complete:
                    scan_rows.append(
                        {
                            "target_draw_id": draw_id,
                            "target_draw_date": draw_date,
                            "strategy_id": strategy_id,
                            "strategy_version": strategy_version,
                            "status": status,
                            "reason": reason,
                            "existing_records": records,
                        }
                    )

        total = len(targets) * len(strategies)
        return {
            "lottery_type": lottery_type,
            "window_start_date": earliest,
            "window_end_date": latest,
            "source_target_count": len(targets),
            "expected_cell_count": total,
            "complete_cell_count": total - len(scan_rows),
            "incomplete_cell_count": len(scan_rows),
            "complete_coverage_percent": 100.0 * (total - len(scan_rows)) / total,
            "status_counts": status_counts,
            "strategy_counts": {
                key: {
                    **counts,
                    "execution_versions": sorted(identity_variants[key]["execution_versions"]),
                    "dataset_identities": sorted(identity_variants[key]["dataset_identities"]),
                }
                for key, counts in strategy_counts.items()
            },
            "orphan_replay_row_count": orphan_count,
            "items": scan_rows[offset : offset + limit],
            "total_count": len(scan_rows),
            "limit": limit,
            "offset": offset,
            "next_offset": offset + limit if offset + limit < len(scan_rows) else None,
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
            "LATEST_RUN_BY_CREATED_AT_PER_LOTTERY_TYPE" if run_id is None else "EXPLICIT_RUN_ID"
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
                    if "reference_projection" in manifest:
                        continue
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

    def k3_comparison_payloads(
        self, run_id: str, new_strategy_id: str, old_strategy_id: str
    ) -> tuple[list[JsonObject], list[JsonObject]]:
        """Read one saved candidate run and its possible original cells consistently."""
        columns = (
            "c.cell_identity,c.lottery_type,c.strategy_id,c.strategy_version,"
            "c.target_draw_id,c.target_draw_date,c.dataset_identity,c.execution_version,"
            "c.result_identity,c.payload_json"
        )
        with self._connect() as connection:
            connection.execute("BEGIN")
            new_rows = connection.execute(
                f"SELECT {columns} FROM replay_backfill_run_cells r "
                "JOIN replay_backfill_cells c USING(cell_identity) "
                "WHERE r.run_id=? AND c.lottery_type=? AND c.strategy_id=? "
                "ORDER BY c.target_draw_date,CAST(c.target_draw_id AS INTEGER)",
                (run_id, "BIG_LOTTO", new_strategy_id),
            ).fetchall()
            old_rows = connection.execute(
                f"SELECT {columns} FROM replay_backfill_cells c "
                "WHERE c.lottery_type=? AND c.strategy_id=?",
                ("BIG_LOTTO", old_strategy_id),
            ).fetchall()
            old_ids = {row[0] for row in old_rows}
            old_run_ids: dict[str, list[str]] = {}
            for cell_id, old_run_id in connection.execute(
                "SELECT cell_identity,run_id FROM replay_backfill_run_cells"
            ):
                if cell_id in old_ids:
                    old_run_ids.setdefault(cell_id, []).append(old_run_id)

        def unpack(row: tuple[Any, ...]) -> JsonObject:
            return {
                "identity": dict(
                    zip(
                        (
                            "cell_identity",
                            "lottery_type",
                            "strategy_id",
                            "strategy_version",
                            "target_draw_id",
                            "target_draw_date",
                            "dataset_identity",
                            "execution_version",
                            "result_identity",
                        ),
                        row[:9],
                        strict=True,
                    )
                ),
                "payload": json.loads(row[9]),
            }

        return [unpack(row) for row in new_rows], [
            {**unpack(row), "run_ids": sorted(old_run_ids.get(row[0], []))} for row in old_rows
        ]

    def prediction_page(
        self,
        *,
        lottery_type: str,
        run_id: str | None = None,
        strategy_id: str | None,
        strategy_version: str | None = None,
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
        if strategy_version is not None:
            if strategy_id is None:
                raise ValueError("strategy_version requires strategy_id")
            if not strategy_version or strategy_version != strategy_version.strip():
                raise ValueError("strategy_version must be a non-blank exact value")
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
        if strategy_version is not None:
            clauses.append("c.strategy_version=?")
            params.append(strategy_version)
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
                "c.strategy_version,c.cell_identity,c.lottery_type,c.dataset_identity,"
                "c.execution_version,c.result_identity FROM replay_backfill_cells c "
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
                            "dataset_identity": row[7],
                            "execution_version": row[8],
                            "result_identity": row[9],
                        },
                        "cutoff_source": cutoff_source,
                        "portfolio_context": _research_portfolio_context(
                            manifest,
                            payload,
                            selected_run_id,
                            lottery_type,
                            stored_identity={
                                "target_draw_date": row[1],
                                "target_draw_id": row[2],
                                "strategy_id": row[3],
                                "strategy_version": row[4],
                                "cell_identity": row[5],
                                "dataset_identity": row[7],
                                "execution_version": row[8],
                                "result_identity": row[9],
                            },
                        ),
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
        items: list[JsonObject] = []
        for row in rows:
            payload = _as_json_object(json.loads(row[0]))
            if payload is None:
                raise ValueError("persisted replay result payload is invalid")
            provenance_status = payload.get(
                "source_history_provenance_status",
                SourceHistoryProvenanceStatus.UNKNOWN.value,
            )
            # Legacy payloads get a safe read-view default without changing stored bytes.
            payload["source_history_provenance_status"] = parse_source_history_provenance_status(
                provenance_status
            ).value
            items.append(payload)
        return {
            "items": items,
            "total_count": total,
            "limit": limit,
            "offset": offset,
        }

    def discover_strategy_runs(
        self,
        lottery_type: str | LotteryType,
        strategy_id: str,
        strategy_version: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> JsonObject:
        """Discover all runs where a strategy version appears in inventory or cells."""
        if isinstance(lottery_type, LotteryType):
            lottery_type_str = lottery_type.value
        elif _is_string(lottery_type):
            lottery_type_str = lottery_type.strip()
            if not lottery_type_str:
                raise ValueError("lottery_type must not be empty")
        else:
            raise ValueError(
                f"lottery_type must be a string or LotteryType, got {type(lottery_type).__name__}"
            )

        if not _is_string(strategy_id):
            raise ValueError(f"strategy_id must be a string, got {type(strategy_id).__name__}")
        strategy_id = strategy_id.strip()
        if not strategy_id:
            raise ValueError("strategy_id must not be empty")

        if strategy_version is not None:
            if not _is_string(strategy_version):
                raise ValueError(
                    "strategy_version must be None or a string, "
                    f"got {type(strategy_version).__name__}"
                )
            strategy_version = strategy_version.strip()
            if not strategy_version:
                raise ValueError("strategy_version must not be empty")

        if not _is_non_bool_integer(limit):
            raise ValueError(f"limit must be an integer, got {type(limit).__name__}")
        if limit <= 0 or limit > 250:
            raise ValueError(f"limit must be between 1 and 250, got {limit}")

        if not _is_non_bool_integer(offset):
            raise ValueError(f"offset must be an integer, got {type(offset).__name__}")
        if offset < 0:
            raise ValueError(f"offset must be non-negative, got {offset}")
        if offset > 9_007_199_254_740_991:
            raise ValueError(f"offset exceeds safe integer range: {offset}")

        with self._connect() as connection:
            all_matches = connection.execute(
                """
                WITH candidate_matches AS (
                    SELECT run_id, strategy_version
                    FROM replay_backfill_strategy_inventory
                    WHERE lottery_type = :lottery_type AND strategy_id = :strategy_id
                      AND (:strategy_version IS NULL OR strategy_version = :strategy_version)
                    UNION
                    SELECT rc.run_id, c.strategy_version
                    FROM replay_backfill_run_cells rc
                    JOIN replay_backfill_cells c ON c.cell_identity = rc.cell_identity
                    WHERE c.lottery_type = :lottery_type AND c.strategy_id = :strategy_id
                      AND (:strategy_version IS NULL OR c.strategy_version = :strategy_version)
                )
                SELECT cm.run_id, cm.strategy_version, r.created_at
                FROM candidate_matches cm
                JOIN replay_backfill_runs r ON r.run_id = cm.run_id
                ORDER BY r.created_at DESC, r.run_id ASC, cm.strategy_version ASC
                """,
                {
                    "lottery_type": lottery_type_str,
                    "strategy_id": strategy_id,
                    "strategy_version": strategy_version,
                },
            ).fetchall()

            total = len(all_matches)
            paged = all_matches[offset : offset + limit]
            has_more = (offset + limit) < total

            items: list[JsonObject] = []
            for run_id, item_version, run_created_at in paged:
                inventory_present = bool(
                    connection.execute(
                        """
                        SELECT 1 FROM replay_backfill_strategy_inventory
                        WHERE run_id = ? AND lottery_type = ? AND strategy_id = ?
                          AND strategy_version = ?
                        """,
                        (run_id, lottery_type_str, strategy_id, item_version),
                    ).fetchone()
                )

                cell_stats = connection.execute(
                    """
                    SELECT
                        COUNT(rc.cell_identity),
                        COUNT(DISTINCT c.target_draw_id),
                        MIN(c.target_draw_date),
                        MAX(c.target_draw_date)
                    FROM replay_backfill_run_cells rc
                    JOIN replay_backfill_cells c ON c.cell_identity = rc.cell_identity
                    WHERE rc.run_id = ? AND c.lottery_type = ? AND c.strategy_id = ?
                      AND c.strategy_version = ?
                    """,
                    (run_id, lottery_type_str, strategy_id, item_version),
                ).fetchone()

                associated_cell_count = int(cell_stats[0]) if cell_stats else 0
                if associated_cell_count > 0:
                    unique_target_draw_count = int(cell_stats[1])
                    earliest_date = cell_stats[2]
                    latest_date = cell_stats[3]

                    exec_identity_count = connection.execute(
                        """
                        SELECT COUNT(*) FROM (
                            SELECT DISTINCT c.execution_version, c.dataset_identity
                            FROM replay_backfill_run_cells rc
                            JOIN replay_backfill_cells c ON c.cell_identity = rc.cell_identity
                            WHERE rc.run_id = ? AND c.lottery_type = ? AND c.strategy_id = ?
                              AND c.strategy_version = ?
                        )
                        """,
                        (run_id, lottery_type_str, strategy_id, item_version),
                    ).fetchone()
                    execution_identity_count = (
                        int(exec_identity_count[0]) if exec_identity_count else 0
                    )

                    status_rows = connection.execute(
                        """
                        SELECT c.execution_status, COUNT(*)
                        FROM replay_backfill_run_cells rc
                        JOIN replay_backfill_cells c ON c.cell_identity = rc.cell_identity
                        WHERE rc.run_id = ? AND c.lottery_type = ? AND c.strategy_id = ?
                          AND c.strategy_version = ?
                        GROUP BY c.execution_status
                        ORDER BY c.execution_status
                        """,
                        (run_id, lottery_type_str, strategy_id, item_version),
                    ).fetchall()
                    execution_status_counts = {str(r[0]): int(r[1]) for r in status_rows}
                else:
                    unique_target_draw_count = 0
                    earliest_date = None
                    latest_date = None
                    execution_identity_count = 0
                    execution_status_counts = {}

                items.append(
                    {
                        "run_id": run_id,
                        "lottery_type": lottery_type_str,
                        "strategy_id": strategy_id,
                        "strategy_version": item_version,
                        "run_created_at": run_created_at,
                        "inventory_present": inventory_present,
                        "associated_cell_count": associated_cell_count,
                        "unique_target_draw_count": unique_target_draw_count,
                        "execution_identity_count": execution_identity_count,
                        "execution_status_counts": execution_status_counts,
                        "earliest_target_draw_date": earliest_date,
                        "latest_target_draw_date": latest_date,
                    }
                )

        return {
            "total_run_version_matches": total,
            "items": items,
            "has_more": has_more,
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
            if candidate.get("strategy_id") == payload.get("strategy_id") and candidate.get(
                "strategy_version"
            ) == payload.get("strategy_version"):
                matches.append(candidate)
    expected: object = matches[0].get("native_ticket_count") if len(matches) == 1 else None
    body = {key: value for key, value in payload.items() if key != "result_identity"}
    digest = payload.get("result_identity")
    stored = stored_identity or {}
    identity_fields = (
        "target_draw_date",
        "target_draw_id",
        "strategy_id",
        "strategy_version",
        "cell_identity",
        "dataset_identity",
        "execution_version",
        "result_identity",
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
                if any(
                    nested_data.get(key) != value for key, value in ticket_identity.items()
                ) or nested_data.get("ticket_position") != ticket.get("ticket_position"):
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
