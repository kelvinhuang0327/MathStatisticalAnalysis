"""Temporary-DB invariance tests for the P336 one-transaction reader."""

from __future__ import annotations

import contextlib
import hashlib
import sqlite3
from collections.abc import Generator
from pathlib import Path

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.evidence.ordered_candidate_emission_package import (
    source_snapshot_sha256,
)
from lottolab.infrastructure.imports.csv_draws import parse_draw_csv
from lottolab.infrastructure.persistence import (
    ordered_candidate_materialization_reader as reader_module,
)
from lottolab.infrastructure.persistence.draw_schema import (
    DATA_DIRECTORY_ENV,
    LocalDataPaths,
    open_database,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.ordered_candidate_materialization_reader import (
    SQLiteOrderedCandidateMaterializationReader,
)
from lottolab.infrastructure.persistence.repositories import SQLiteDrawDataRepository

_HEADER = "lottery_type,draw_number,draw_date,main_numbers,special_numbers,source"


def _paths(tmp_path: Path) -> LocalDataPaths:
    return resolve_local_data_paths(
        environ={DATA_DIRECTORY_ENV: str(tmp_path / "p336-data")}
    )


def _row(draw: str, draw_date: str) -> str:
    return f"BIG_LOTTO,{draw},{draw_date},1|2|3|4|5|6,7,fixture"


def _seed(paths: LocalDataPaths) -> None:
    parsed = parse_draw_csv(
        "\n".join(
            (
                _HEADER,
                _row("1", "2026-01-01"),
                _row("2", "2026-01-02"),
                _row("9", "2026-01-10"),
                _row("10", "2026-01-10"),
                "",
            )
        ),
        filename="fixture.csv",
    )
    assert parsed.is_valid, parsed.errors
    SQLiteDrawDataRepository(paths).apply_valid_import(parsed)


def _db_evidence(paths: LocalDataPaths) -> tuple[str, int, tuple[int, ...], str]:
    database_bytes = paths.database.read_bytes()
    with open_database(paths, read_only=True) as connection:
        counts = tuple(
            int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in (
                "draws",
                "schema_migrations",
                "ingestion_runs",
                "ingestion_items",
            )
        )
        schema_rows = connection.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_schema ORDER BY type, name"
        ).fetchall()
    schema_digest = hashlib.sha256(repr(schema_rows).encode("utf-8")).hexdigest()
    return (
        hashlib.sha256(database_bytes).hexdigest(),
        len(database_bytes),
        counts,
        schema_digest,
    )


def test_snapshot_uses_date_then_numeric_draw_order_and_exact_lcj_digest(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    _seed(paths)

    snapshot = SQLiteOrderedCandidateMaterializationReader(
        paths
    ).read_source_snapshot(LotteryType.BIG_LOTTO)

    assert [row.draw_number for row in snapshot.rows] == ["1", "2", "9", "10"]
    assert snapshot.source_snapshot_sha256 == source_snapshot_sha256(snapshot.rows)
    assert all(row.lottery_type is LotteryType.BIG_LOTTO for row in snapshot.rows)
    assert all(len(row.normalized_record_hash) == 64 for row in snapshot.rows)


def test_reader_keeps_database_bytes_size_rows_schema_and_sidecars_invariant(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    _seed(paths)
    before = _db_evidence(paths)

    SQLiteOrderedCandidateMaterializationReader(paths).read_source_snapshot(
        LotteryType.BIG_LOTTO
    )

    after = _db_evidence(paths)
    assert after == before
    for suffix in ("-wal", "-shm", "-journal"):
        assert not Path(f"{paths.database}{suffix}").exists()


def test_source_hash_query_runs_once_inside_one_explicit_read_transaction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _paths(tmp_path)
    _seed(paths)
    statements: list[str] = []
    commits = 0
    rollbacks = 0
    real_open = open_database

    class ConnectionProxy:
        def __init__(self, connection: sqlite3.Connection) -> None:
            self.connection = connection

        def execute(
            self,
            statement: str,
            parameters: tuple[object, ...] = (),
        ) -> sqlite3.Cursor:
            statements.append(" ".join(statement.split()))
            return self.connection.execute(statement, parameters)

        def commit(self) -> None:
            nonlocal commits
            commits += 1
            self.connection.commit()

        def rollback(self) -> None:
            nonlocal rollbacks
            rollbacks += 1
            self.connection.rollback()

    @contextlib.contextmanager
    def wrapped_open(
        requested_paths: LocalDataPaths,
        *,
        read_only: bool = False,
    ) -> Generator[ConnectionProxy]:
        assert requested_paths == paths
        assert read_only is True
        with real_open(requested_paths, read_only=read_only) as connection:
            yield ConnectionProxy(connection)

    monkeypatch.setattr(reader_module, "open_database", wrapped_open)

    SQLiteOrderedCandidateMaterializationReader(paths).read_source_snapshot(
        LotteryType.BIG_LOTTO
    )

    assert statements.count("BEGIN") == 1
    assert sum("FROM draws" in statement for statement in statements) == 1
    assert commits == 1
    assert rollbacks == 0
