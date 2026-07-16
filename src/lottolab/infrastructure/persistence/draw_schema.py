"""Secure local path resolution and versioned SQLite schema for draw data."""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import stat
from collections.abc import Generator, Mapping
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

DATA_DIRECTORY_ENV = "LOTTOLAB_DATA_DIR"
DATABASE_FILENAME = "lottolab.db"
CURRENT_SCHEMA_VERSION = 1
MIGRATION_NAME = "create_local_draw_data_schema"
BUSY_TIMEOUT_MS = 5_000


class LocalDataError(RuntimeError):
    """The local data path or database failed a safety check."""


class SchemaMigrationError(RuntimeError):
    """The local database schema is absent, corrupt, or incompatible."""


class NewerSchemaVersionError(SchemaMigrationError):
    """The database belongs to a newer LottoLab version."""


class MigrationChecksumError(SchemaMigrationError):
    """A recorded migration does not match the code-owned migration."""


@dataclass(frozen=True, slots=True)
class LocalDataPaths:
    """Resolved paths only; constructing this value never creates or opens anything."""

    data_directory: Path
    database: Path


MIGRATION_STATEMENTS = (
    """
    CREATE TABLE schema_migrations (
        version INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        checksum TEXT NOT NULL,
        applied_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE ingestion_runs (
        id TEXT PRIMARY KEY,
        operation_type TEXT NOT NULL,
        status TEXT NOT NULL,
        lottery_type TEXT,
        source_filename TEXT NOT NULL,
        source_sha256 TEXT NOT NULL,
        parser_version TEXT NOT NULL,
        total_count INTEGER NOT NULL CHECK (total_count >= 0),
        inserted_count INTEGER NOT NULL CHECK (inserted_count >= 0),
        skipped_count INTEGER NOT NULL CHECK (skipped_count >= 0),
        conflict_count INTEGER NOT NULL CHECK (conflict_count >= 0),
        failed_count INTEGER NOT NULL CHECK (failed_count >= 0),
        first_draw_number TEXT,
        last_draw_number TEXT,
        started_at TEXT NOT NULL,
        completed_at TEXT,
        error_summary TEXT
    )
    """,
    """
    CREATE TABLE draws (
        id INTEGER PRIMARY KEY,
        lottery_type TEXT NOT NULL,
        draw_number TEXT NOT NULL,
        draw_date TEXT NOT NULL,
        main_numbers_json TEXT NOT NULL,
        special_numbers_json TEXT NOT NULL,
        normalized_record_hash TEXT NOT NULL,
        source_name TEXT,
        source_reference TEXT,
        ingestion_run_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE (lottery_type, draw_number),
        FOREIGN KEY (ingestion_run_id) REFERENCES ingestion_runs(id) ON DELETE RESTRICT
    )
    """,
    """
    CREATE TABLE ingestion_items (
        id INTEGER PRIMARY KEY,
        ingestion_run_id TEXT NOT NULL,
        source_row_number INTEGER NOT NULL CHECK (source_row_number >= 1),
        lottery_type TEXT,
        draw_number TEXT,
        disposition TEXT NOT NULL,
        normalized_record_hash TEXT,
        message TEXT,
        FOREIGN KEY (ingestion_run_id) REFERENCES ingestion_runs(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE INDEX idx_draws_history
    ON draws (lottery_type, draw_date DESC, draw_number DESC)
    """,
    """
    CREATE INDEX idx_ingestion_runs_history
    ON ingestion_runs (started_at DESC, id DESC)
    """,
    """
    CREATE INDEX idx_ingestion_items_run_row
    ON ingestion_items (ingestion_run_id, source_row_number, id)
    """,
)

MIGRATION_SQL = ";\n".join(statement.strip() for statement in MIGRATION_STATEMENTS) + ";\n"
MIGRATION_CHECKSUM = hashlib.sha256(MIGRATION_SQL.encode("utf-8")).hexdigest()

_EXPECTED_TABLE_XINFO = {
    "schema_migrations": (
        (0, "version", "INTEGER", 0, None, 1, 0),
        (1, "name", "TEXT", 1, None, 0, 0),
        (2, "checksum", "TEXT", 1, None, 0, 0),
        (3, "applied_at", "TEXT", 1, None, 0, 0),
    ),
    "ingestion_runs": (
        (0, "id", "TEXT", 0, None, 1, 0),
        (1, "operation_type", "TEXT", 1, None, 0, 0),
        (2, "status", "TEXT", 1, None, 0, 0),
        (3, "lottery_type", "TEXT", 0, None, 0, 0),
        (4, "source_filename", "TEXT", 1, None, 0, 0),
        (5, "source_sha256", "TEXT", 1, None, 0, 0),
        (6, "parser_version", "TEXT", 1, None, 0, 0),
        (7, "total_count", "INTEGER", 1, None, 0, 0),
        (8, "inserted_count", "INTEGER", 1, None, 0, 0),
        (9, "skipped_count", "INTEGER", 1, None, 0, 0),
        (10, "conflict_count", "INTEGER", 1, None, 0, 0),
        (11, "failed_count", "INTEGER", 1, None, 0, 0),
        (12, "first_draw_number", "TEXT", 0, None, 0, 0),
        (13, "last_draw_number", "TEXT", 0, None, 0, 0),
        (14, "started_at", "TEXT", 1, None, 0, 0),
        (15, "completed_at", "TEXT", 0, None, 0, 0),
        (16, "error_summary", "TEXT", 0, None, 0, 0),
    ),
    "draws": (
        (0, "id", "INTEGER", 0, None, 1, 0),
        (1, "lottery_type", "TEXT", 1, None, 0, 0),
        (2, "draw_number", "TEXT", 1, None, 0, 0),
        (3, "draw_date", "TEXT", 1, None, 0, 0),
        (4, "main_numbers_json", "TEXT", 1, None, 0, 0),
        (5, "special_numbers_json", "TEXT", 1, None, 0, 0),
        (6, "normalized_record_hash", "TEXT", 1, None, 0, 0),
        (7, "source_name", "TEXT", 0, None, 0, 0),
        (8, "source_reference", "TEXT", 0, None, 0, 0),
        (9, "ingestion_run_id", "TEXT", 1, None, 0, 0),
        (10, "created_at", "TEXT", 1, None, 0, 0),
        (11, "updated_at", "TEXT", 1, None, 0, 0),
    ),
    "ingestion_items": (
        (0, "id", "INTEGER", 0, None, 1, 0),
        (1, "ingestion_run_id", "TEXT", 1, None, 0, 0),
        (2, "source_row_number", "INTEGER", 1, None, 0, 0),
        (3, "lottery_type", "TEXT", 0, None, 0, 0),
        (4, "draw_number", "TEXT", 0, None, 0, 0),
        (5, "disposition", "TEXT", 1, None, 0, 0),
        (6, "normalized_record_hash", "TEXT", 0, None, 0, 0),
        (7, "message", "TEXT", 0, None, 0, 0),
    ),
}

_EXPECTED_INDEX_LIST = {
    "schema_migrations": {},
    "ingestion_runs": {
        "idx_ingestion_runs_history": (0, "c", 0),
        "sqlite_autoindex_ingestion_runs_1": (1, "pk", 0),
    },
    "draws": {
        "idx_draws_history": (0, "c", 0),
        "sqlite_autoindex_draws_1": (1, "u", 0),
    },
    "ingestion_items": {
        "idx_ingestion_items_run_row": (0, "c", 0),
    },
}

_EXPECTED_INDEX_XINFO = {
    "sqlite_autoindex_ingestion_runs_1": (
        (0, 0, "id", 0, "BINARY", 1),
        (1, -1, None, 0, "BINARY", 0),
    ),
    "sqlite_autoindex_draws_1": (
        (0, 1, "lottery_type", 0, "BINARY", 1),
        (1, 2, "draw_number", 0, "BINARY", 1),
        (2, -1, None, 0, "BINARY", 0),
    ),
    "idx_draws_history": (
        (0, 1, "lottery_type", 0, "BINARY", 1),
        (1, 3, "draw_date", 1, "BINARY", 1),
        (2, 2, "draw_number", 1, "BINARY", 1),
        (3, -1, None, 0, "BINARY", 0),
    ),
    "idx_ingestion_runs_history": (
        (0, 14, "started_at", 1, "BINARY", 1),
        (1, 0, "id", 1, "BINARY", 1),
        (2, -1, None, 0, "BINARY", 0),
    ),
    "idx_ingestion_items_run_row": (
        (0, 1, "ingestion_run_id", 0, "BINARY", 1),
        (1, 2, "source_row_number", 0, "BINARY", 1),
        (2, 0, "id", 0, "BINARY", 1),
        (3, -1, None, 0, "BINARY", 0),
    ),
}

_EXPECTED_FOREIGN_KEYS = {
    "schema_migrations": (),
    "ingestion_runs": (),
    "draws": ((0, 0, "ingestion_runs", "ingestion_run_id", "id", "NO ACTION", "RESTRICT", "NONE"),),
    "ingestion_items": (
        (0, 0, "ingestion_runs", "ingestion_run_id", "id", "NO ACTION", "CASCADE", "NONE"),
    ),
}

_EXPECTED_SCHEMA_SQL = {
    "schema_migrations": MIGRATION_STATEMENTS[0],
    "ingestion_runs": MIGRATION_STATEMENTS[1],
    "draws": MIGRATION_STATEMENTS[2],
    "ingestion_items": MIGRATION_STATEMENTS[3],
    "idx_draws_history": MIGRATION_STATEMENTS[4],
    "idx_ingestion_runs_history": MIGRATION_STATEMENTS[5],
    "idx_ingestion_items_run_row": MIGRATION_STATEMENTS[6],
    "sqlite_autoindex_draws_1": None,
    "sqlite_autoindex_ingestion_runs_1": None,
}

_EXPECTED_SCHEMA_OBJECTS = {("table", name, name) for name in _EXPECTED_TABLE_XINFO} | {
    ("index", "idx_draws_history", "draws"),
    ("index", "idx_ingestion_runs_history", "ingestion_runs"),
    ("index", "idx_ingestion_items_run_row", "ingestion_items"),
    ("index", "sqlite_autoindex_draws_1", "draws"),
    ("index", "sqlite_autoindex_ingestion_runs_1", "ingestion_runs"),
}

_SCHEMA_SQL_TOKEN = re.compile(
    r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|`(?:``|[^`])*`|\[[^]]*\]|[(),]|[^\s(),]+"
)


def resolve_local_data_paths(
    *,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> LocalDataPaths:
    """Resolve the configured location without creating directories or opening SQLite."""

    selected_environment = os.environ if environ is None else environ
    if DATA_DIRECTORY_ENV in selected_environment:
        configured = selected_environment[DATA_DIRECTORY_ENV]
        if not configured.strip():
            raise LocalDataError(f"{DATA_DIRECTORY_ENV} must not be empty")
        data_directory = Path(configured)
    else:
        selected_home = Path.home() if home is None else home
        data_directory = selected_home / "Library" / "Application Support" / "LottoLab"

    paths = LocalDataPaths(
        data_directory=data_directory,
        database=data_directory / DATABASE_FILENAME,
    )
    _validate_path_definition(paths)
    _validate_existing_paths(paths)
    return paths


def initialize_schema(paths: LocalDataPaths) -> None:
    """Securely create/upgrade an empty or version-1 database in one transaction."""

    _validate_path_definition(paths)
    _validate_existing_paths(paths)
    directory_created = False
    database_created = False

    try:
        directory_created = _ensure_data_directory(paths.data_directory)
        database_created = _ensure_database_file(paths.database)
        with _raw_connection(paths, read_only=False) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                if not _verify_migration_state(connection):
                    for statement in MIGRATION_STATEMENTS:
                        connection.execute(statement)
                    connection.execute(
                        """
                        INSERT INTO schema_migrations (version, name, checksum, applied_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            CURRENT_SCHEMA_VERSION,
                            MIGRATION_NAME,
                            MIGRATION_CHECKSUM,
                            _utc_now(),
                        ),
                    )
                    if not _verify_migration_state(connection):
                        raise SchemaMigrationError("schema migration did not reach version 1")
            except BaseException:
                connection.rollback()
                raise
            else:
                connection.commit()
        _validate_existing_paths(paths)
        _reject_wal_sidecars(paths.database)
    except (LocalDataError, SchemaMigrationError):
        if database_created:
            _remove_new_database(paths.database)
        if directory_created:
            _remove_empty_directory(paths.data_directory)
        raise
    except sqlite3.DatabaseError as exc:
        if database_created:
            _remove_new_database(paths.database)
        if directory_created:
            _remove_empty_directory(paths.data_directory)
        raise SchemaMigrationError("SQLite schema migration failed") from exc


def verify_schema_read_only(paths: LocalDataPaths) -> bool:
    """Return False for an absent DB; validate an existing DB without creating it."""

    _validate_path_definition(paths)
    _validate_existing_paths(paths)
    if not paths.database.exists():
        return False
    with _raw_connection(paths, read_only=True) as connection:
        try:
            initialized = _verify_migration_state(connection)
        except sqlite3.DatabaseError as exc:
            raise SchemaMigrationError("SQLite schema verification failed") from exc
        if not initialized:
            raise SchemaMigrationError("database exists without a schema migration")
    _validate_existing_paths(paths)
    return True


@contextmanager
def open_database(
    paths: LocalDataPaths, *, read_only: bool = False
) -> Generator[sqlite3.Connection]:
    """Open a fresh, configured connection to an existing verified version-1 DB."""

    _validate_path_definition(paths)
    _validate_existing_paths(paths)
    if not paths.database.exists():
        raise SchemaMigrationError("local draw database does not exist")
    with _raw_connection(paths, read_only=read_only) as connection:
        try:
            initialized = _verify_migration_state(connection)
        except sqlite3.DatabaseError as exc:
            raise SchemaMigrationError("SQLite schema verification failed") from exc
        if not initialized:
            raise SchemaMigrationError("database exists without a schema migration")
        yield connection


@contextmanager
def _raw_connection(paths: LocalDataPaths, *, read_only: bool) -> Generator[sqlite3.Connection]:
    _validate_existing_paths(paths)
    _reject_wal_sidecars(paths.database)
    mode = "ro" if read_only else "rw"
    uri = f"{paths.database.as_uri()}?mode={mode}"
    try:
        connection = sqlite3.connect(
            uri,
            uri=True,
            timeout=BUSY_TIMEOUT_MS / 1_000,
            isolation_level=None,
        )
    except sqlite3.DatabaseError as exc:
        raise SchemaMigrationError("cannot open the local draw database safely") from exc
    try:
        try:
            connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
            connection.execute("PRAGMA foreign_keys = ON")
            if connection.execute("PRAGMA foreign_keys").fetchone() != (1,):
                raise SchemaMigrationError("SQLite foreign-key enforcement is unavailable")
            if read_only:
                connection.execute("PRAGMA query_only = ON")
                journal_mode = connection.execute("PRAGMA journal_mode").fetchone()
            else:
                journal_mode = connection.execute("PRAGMA journal_mode = DELETE").fetchone()
            if journal_mode is None or str(journal_mode[0]).lower() != "delete":
                raise SchemaMigrationError("SQLite must use DELETE journal mode")
        except sqlite3.DatabaseError as exc:
            raise SchemaMigrationError("cannot configure SQLite safely") from exc
        yield connection
    finally:
        connection.close()


def _verify_migration_state(connection: sqlite3.Connection) -> bool:
    table_names = {
        str(row[0])
        for row in connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        )
    }
    if "schema_migrations" not in table_names:
        if table_names:
            raise SchemaMigrationError("unversioned database contains application tables")
        return False

    rows = connection.execute(
        "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
    ).fetchall()
    try:
        versions = [int(row[0]) for row in rows]
    except (TypeError, ValueError) as exc:
        raise SchemaMigrationError("database migration versions are invalid") from exc
    if any(version > CURRENT_SCHEMA_VERSION for version in versions):
        raise NewerSchemaVersionError("database schema is newer than this LottoLab build")
    if versions != [CURRENT_SCHEMA_VERSION]:
        raise SchemaMigrationError("database migration history is incomplete")
    _, name, checksum = rows[0]
    if name != MIGRATION_NAME or checksum != MIGRATION_CHECKSUM:
        raise MigrationChecksumError("database migration checksum does not match")

    _verify_schema_semantics(connection, table_names)
    return True


def _verify_schema_semantics(connection: sqlite3.Connection, table_names: set[str]) -> None:
    if table_names != set(_EXPECTED_TABLE_XINFO):
        raise SchemaMigrationError("database schema tables do not match version 1")

    schema_rows = connection.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_schema ORDER BY type, name"
    ).fetchall()
    schema_objects = {(str(row[0]), str(row[1]), str(row[2])) for row in schema_rows}
    if schema_objects != _EXPECTED_SCHEMA_OBJECTS:
        raise SchemaMigrationError("database schema objects do not match version 1")
    for row in schema_rows:
        name = str(row[1])
        expected_sql = _EXPECTED_SCHEMA_SQL[name]
        actual_sql = row[3]
        if expected_sql is None:
            if actual_sql is not None:
                raise SchemaMigrationError(f"database schema SQL does not match version 1: {name}")
        elif not isinstance(actual_sql, str) or _canonical_schema_sql(
            actual_sql
        ) != _canonical_schema_sql(expected_sql):
            raise SchemaMigrationError(f"database schema SQL does not match version 1: {name}")

    for table, expected_columns in _EXPECTED_TABLE_XINFO.items():
        columns = tuple(
            (
                int(row[0]),
                str(row[1]),
                str(row[2]),
                int(row[3]),
                None if row[4] is None else str(row[4]),
                int(row[5]),
                int(row[6]),
            )
            for row in connection.execute(f"PRAGMA table_xinfo({table})")
        )
        if columns != expected_columns:
            raise SchemaMigrationError(f"database table semantics do not match version 1: {table}")

        indexes = {
            str(row[1]): (int(row[2]), str(row[3]), int(row[4]))
            for row in connection.execute(f"PRAGMA index_list({table})")
        }
        if indexes != _EXPECTED_INDEX_LIST[table]:
            raise SchemaMigrationError(
                f"database index inventory does not match version 1: {table}"
            )

        foreign_keys = tuple(
            (
                int(row[0]),
                int(row[1]),
                str(row[2]),
                str(row[3]),
                str(row[4]),
                str(row[5]),
                str(row[6]),
                str(row[7]),
            )
            for row in connection.execute(f"PRAGMA foreign_key_list({table})")
        )
        if foreign_keys != _EXPECTED_FOREIGN_KEYS[table]:
            raise SchemaMigrationError(
                f"database foreign-key semantics do not match version 1: {table}"
            )

    for index, expected_index_columns in _EXPECTED_INDEX_XINFO.items():
        index_columns = tuple(
            (
                int(row[0]),
                int(row[1]),
                None if row[2] is None else str(row[2]),
                int(row[3]),
                None if row[4] is None else str(row[4]),
                int(row[5]),
            )
            for row in connection.execute(f"PRAGMA index_xinfo({index})")
        )
        if index_columns != expected_index_columns:
            raise SchemaMigrationError(f"database index semantics do not match version 1: {index}")


def _canonical_schema_sql(sql: str) -> tuple[str, ...]:
    return tuple(token.casefold() for token in _SCHEMA_SQL_TOKEN.findall(sql))


def _validate_path_definition(paths: LocalDataPaths) -> None:
    data_directory = paths.data_directory
    if "\x00" in str(data_directory):
        raise LocalDataError("local data path contains a null byte")
    if not data_directory.is_absolute():
        raise LocalDataError("local data path must be absolute")
    if ".." in data_directory.parts:
        raise LocalDataError("local data path traversal is not allowed")
    if data_directory == Path(data_directory.anchor):
        raise LocalDataError("local data path cannot be the filesystem root")
    if any(part.casefold() == "lotterynew" for part in data_directory.parts):
        raise LocalDataError("LotteryNew paths are forbidden")
    if paths.database != data_directory / DATABASE_FILENAME:
        raise LocalDataError("local database filename is fixed")
    _reject_git_worktree_path(data_directory)
    _reject_symlink_components(data_directory)


def _validate_existing_paths(paths: LocalDataPaths) -> None:
    _validate_path_definition(paths)
    try:
        directory_metadata = os.lstat(paths.data_directory)
    except FileNotFoundError:
        return
    if not stat.S_ISDIR(directory_metadata.st_mode):
        raise LocalDataError("local data path is not a directory")
    if directory_metadata.st_uid != os.getuid():
        raise LocalDataError("local data directory has a foreign owner")
    if stat.S_IMODE(directory_metadata.st_mode) != 0o700:
        raise LocalDataError("local data directory mode must be exactly 0700")

    try:
        database_metadata = os.lstat(paths.database)
    except FileNotFoundError:
        return
    if not stat.S_ISREG(database_metadata.st_mode):
        raise LocalDataError("local database must be a regular file")
    if database_metadata.st_uid != os.getuid():
        raise LocalDataError("local database has a foreign owner")
    if stat.S_IMODE(database_metadata.st_mode) != 0o600:
        raise LocalDataError("local database mode must be exactly 0600")
    if database_metadata.st_nlink != 1:
        raise LocalDataError("local database must have exactly one hard link")


def _ensure_data_directory(data_directory: Path) -> bool:
    existed = data_directory.exists()
    try:
        data_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError as exc:
        raise LocalDataError("cannot create the local data directory safely") from exc
    _reject_symlink_components(data_directory)
    paths = LocalDataPaths(data_directory, data_directory / DATABASE_FILENAME)
    _validate_existing_paths(paths)
    return not existed


def _ensure_database_file(database: Path) -> bool:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(database, flags, 0o600)
    except FileExistsError:
        paths = LocalDataPaths(database.parent, database)
        _validate_existing_paths(paths)
        return False
    except OSError as exc:
        raise LocalDataError("cannot create the local database safely") from exc
    try:
        os.fchmod(descriptor, 0o600)
    finally:
        os.close(descriptor)
    paths = LocalDataPaths(database.parent, database)
    _validate_existing_paths(paths)
    return True


def _reject_symlink_components(path: Path) -> None:
    current = Path(path.anchor)
    for component in path.parts[1:]:
        current /= component
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            break
        except OSError as exc:
            raise LocalDataError("cannot inspect the local data path safely") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise LocalDataError("local data path cannot contain symlinks")


def _reject_git_worktree_path(path: Path) -> None:
    for ancestor in (path, *path.parents):
        try:
            os.lstat(ancestor / ".git")
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise LocalDataError("cannot inspect Git-worktree boundaries safely") from exc
        raise LocalDataError("local data path must be outside Git worktrees")


def _reject_wal_sidecars(database: Path) -> None:
    for suffix in ("-wal", "-shm"):
        try:
            os.lstat(Path(f"{database}{suffix}"))
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise LocalDataError("cannot inspect SQLite sidecar files safely") from exc
        raise LocalDataError("WAL and SHM files are forbidden")


def _remove_new_database(database: Path) -> None:
    try:
        metadata = os.lstat(database)
    except OSError:
        return
    if stat.S_ISREG(metadata.st_mode) and metadata.st_uid == os.getuid() and metadata.st_nlink == 1:
        with suppress(OSError):
            database.unlink()


def _remove_empty_directory(data_directory: Path) -> None:
    with suppress(OSError):
        data_directory.rmdir()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
