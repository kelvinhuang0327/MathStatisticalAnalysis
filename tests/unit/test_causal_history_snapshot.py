"""The operational loaders must bind the numbers they read to the cutoff digest."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from tools.b649_operational_prediction_loop import load_canonical_history

from lottolab.domain.draws import LotteryType
from lottolab.domain.prospective_observer import ObservationTarget
from lottolab.infrastructure import pre_outcome_target_operational as authority_module
from lottolab.infrastructure.forward_auto_cycle_operational import (
    ForwardCycleTarget,
    load_causal_history,
)
from lottolab.infrastructure.imports.csv_draws import normalized_draw_record_hash
from lottolab.infrastructure.persistence.draw_schema import CURRENT_SCHEMA_VERSION, LocalDataPaths
from lottolab.infrastructure.pre_outcome_target_operational import (
    CausalHistoryAuthorityError,
    SQLitePreOutcomeCausalHistoryAuthority,
)

_DATE = date(2026, 8, 14)
_TARGET = ObservationTarget(LotteryType.BIG_LOTTO, "00000010", _DATE)
_DB_PATH = Path("unused-in-memory.db")
_MAIN = (1, 2, 3, 4, 5, 6)
_SPECIAL = (7,)


def _hash(draw_number: str) -> str:
    return normalized_draw_record_hash(
        lottery_type=LotteryType.BIG_LOTTO,
        draw_number=draw_number,
        draw_date_value=_DATE,
        main_numbers=_MAIN,
        special_numbers=_SPECIAL,
    )


@pytest.fixture
def memory_db() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(":memory:", isolation_level=None)
    try:
        connection.executescript(
            """
            CREATE TABLE schema_migrations(version INTEGER NOT NULL);
            CREATE TABLE draws(
                lottery_type TEXT, draw_number TEXT, draw_date TEXT, normalized_record_hash TEXT,
                main_numbers_json TEXT, special_numbers_json TEXT, created_at TEXT
            );
            CREATE TABLE caller_changes(message TEXT);
            """
        )
        connection.execute("INSERT INTO schema_migrations VALUES (?)", (CURRENT_SCHEMA_VERSION,))
        for number in ("00000009", "00000002", _TARGET.draw_number, "00000100"):
            is_prior = int(number) < int(_TARGET.draw_number)
            connection.execute(
                "INSERT INTO draws VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    LotteryType.BIG_LOTTO.value,
                    number,
                    _DATE.isoformat(),
                    _hash(number),
                    json.dumps(_MAIN) if is_prior else "ignored outcome",
                    json.dumps(_SPECIAL) if is_prior else "ignored outcome",
                    "2026-08-14T08:00:00+00:00" if is_prior else "2026-08-14T14:00:00+00:00",
                ),
            )
        yield connection
    finally:
        connection.close()


@pytest.fixture
def trace(
    monkeypatch: pytest.MonkeyPatch,
    memory_db: sqlite3.Connection,
) -> tuple[list[str], list[Path]]:
    statements: list[str] = []
    opens: list[Path] = []
    memory_db.set_trace_callback(statements.append)

    @contextmanager
    def open_history(
        paths: LocalDataPaths, *, read_only: bool = False
    ) -> Iterator[sqlite3.Connection]:
        assert read_only
        opens.append(paths.database)
        yield memory_db

    monkeypatch.setattr(authority_module, "open_database", open_history)
    return statements, opens


def _load_entry(entry: str) -> tuple[str, int, str, str | None]:
    if entry == "big_lotto_tool":
        snapshot = load_canonical_history(
            _DB_PATH, target_draw_number=_TARGET.draw_number, target_draw_date=_DATE.isoformat()
        )
        assert snapshot.normalized_record_hashes == (_hash("00000002"), _hash("00000009"))
        assert tuple(row.draw for row in snapshot.rows) == ("00000002", "00000009")
        return snapshot.cutoff_draw, snapshot.draw_count, snapshot.history_sha256, None
    forward_snapshot = load_causal_history(
        _DB_PATH,
        target=ForwardCycleTarget(
            _TARGET.lottery_type.value,
            _TARGET.draw_number,
            _DATE.isoformat(),
            "2026-08-14T20:30:00+08:00",
        ),
        lottery_type=_TARGET.lottery_type,
        operation_root=Path("missing-in-memory-outcome-directory"),
        row_factory=lambda *row: row,
        as_of=datetime(2026, 8, 14, 12, tzinfo=UTC),
    )
    assert forward_snapshot.rows == (
        ("00000002", _DATE.isoformat(), _MAIN, _SPECIAL),
        ("00000009", _DATE.isoformat(), _MAIN, _SPECIAL),
    )
    return (
        forward_snapshot.cutoff_draw,
        forward_snapshot.draw_count,
        forward_snapshot.history_sha256,
        forward_snapshot.latest_known_draw_at_prediction_time,
    )


@pytest.mark.parametrize("entry", ["big_lotto_tool", "forward_cycle"])
def test_entry_reads_identity_content_and_freshness_in_one_transaction(
    entry: str,
    memory_db: sqlite3.Connection,
    trace: tuple[list[str], list[Path]],
) -> None:
    statements, opens = trace
    cutoff, count, digest, latest = _load_entry(entry)

    assert (cutoff, count) == ("00000009", 2)
    assert latest == ("00000009" if entry == "forward_cycle" else None)
    assert opens == [_DB_PATH]
    assert statements[0] == "BEGIN"
    assert statements[-1] == "ROLLBACK"
    assert "SELECT MAX(version) FROM schema_migrations" in statements[1]
    assert "normalized_record_hash" in statements[2]
    assert "main_numbers_json" in statements[2] and "special_numbers_json" in statements[2]
    assert len(statements) == (5 if entry == "forward_cycle" else 4)
    if entry == "forward_cycle":
        assert "created_at" in statements[3]
    assert not memory_db.in_transaction
    assert len(digest) == 64


def test_validated_prefix_preserves_registration_authority_identity(
    memory_db: sqlite3.Connection,
    trace: tuple[list[str], list[Path]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del trace
    # The fixture supplies the verified connection in place of filesystem setup.
    monkeypatch.setattr(authority_module, "_require_current_database", lambda _paths: None)
    authority = SQLitePreOutcomeCausalHistoryAuthority(LocalDataPaths(_DB_PATH.parent, _DB_PATH))
    registered = authority.resolve(_TARGET)
    with authority.open_verified_snapshot(_TARGET, connection=memory_db) as (_, snapshot):
        assert snapshot.ref == registered


def test_verified_snapshot_select_is_limited_to_requested_cutoff(
    memory_db: sqlite3.Connection,
    trace: tuple[list[str], list[Path]],
) -> None:
    statements, _opens = trace
    authority = SQLitePreOutcomeCausalHistoryAuthority(LocalDataPaths(_DB_PATH.parent, _DB_PATH))
    with authority.open_verified_snapshot(
        _TARGET,
        connection=memory_db,
        history_cutoff_draw="00000009",
    ) as (_, snapshot):
        assert tuple(row.draw_number for row in snapshot.draws) == ("00000002", "00000009")

    history_select = next(
        statement for statement in statements if "SELECT draw_number, draw_date" in statement
    )
    assert "draw_date <" in history_select
    assert "ltrim(draw_number, '0') <=" in history_select
    assert "00000010" not in history_select and "00000100" not in history_select
    assert statements[0] == "BEGIN"
    assert statements[-1] == "ROLLBACK"
    assert not memory_db.in_transaction


def test_verified_snapshot_rejects_cutoff_without_an_exact_final_row(
    memory_db: sqlite3.Connection,
) -> None:
    authority = SQLitePreOutcomeCausalHistoryAuthority(LocalDataPaths(_DB_PATH.parent, _DB_PATH))
    with pytest.raises(CausalHistoryAuthorityError, match="does not end at the requested cutoff"):
        with authority.open_verified_snapshot(
            _TARGET,
            connection=memory_db,
            history_cutoff_draw="00000008",
        ):
            pytest.fail("a non-existent cutoff was accepted")


def test_numeric_boundary_supports_long_same_day_draw_numbers(
    memory_db: sqlite3.Connection,
) -> None:
    previous = "10000000000000000000000000000000"
    target = "10000000000000000000000000000001"
    later = "10000000000000000000000000000002"
    memory_db.execute("DELETE FROM draws")
    for number in (previous, target, later):
        memory_db.execute(
            "INSERT INTO draws VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                LotteryType.BIG_LOTTO.value,
                number,
                _DATE.isoformat(),
                _hash(number),
                json.dumps(_MAIN),
                json.dumps(_SPECIAL),
                "2026-08-14T08:00:00+00:00",
            ),
        )
    authority = SQLitePreOutcomeCausalHistoryAuthority(LocalDataPaths(_DB_PATH.parent, _DB_PATH))
    with authority.open_verified_snapshot(
        ObservationTarget(LotteryType.BIG_LOTTO, target, _DATE), connection=memory_db
    ) as (_, snapshot):
        assert snapshot.draws[-1].draw_number == previous
        assert snapshot.ref.draw_count == 1


@pytest.mark.parametrize("entry", ["big_lotto_tool", "forward_cycle"])
@pytest.mark.parametrize(
    ("column", "changed", "error"),
    [
        ("main_numbers_json", "[1,2,3,4,5,8]", "does not match normalized_record_hash"),
        ("special_numbers_json", "[8]", "does not match normalized_record_hash"),
        ("normalized_record_hash", _hash("00000002").upper(), "normalized_record_hash is invalid"),
    ],
)
def test_entry_rejects_changed_historical_values_without_changing_cutoff(
    entry: str,
    column: str,
    changed: str,
    error: str,
    memory_db: sqlite3.Connection,
    trace: tuple[list[str], list[Path]],
) -> None:
    memory_db.execute(
        f"UPDATE draws SET {column} = ? WHERE draw_number = '00000002'",
        (changed,),
    )
    statements, opens = trace
    statements.clear()
    with pytest.raises(CausalHistoryAuthorityError, match=error):
        _load_entry(entry)
    assert opens == [_DB_PATH]
    assert statements[0] == "BEGIN"
    assert statements[-1] == "ROLLBACK"
    assert not memory_db.in_transaction


@pytest.mark.parametrize("damaged", [False, True])
def test_borrowed_transaction_stays_owned_by_the_caller(
    damaged: bool,
    memory_db: sqlite3.Connection,
) -> None:
    authority = SQLitePreOutcomeCausalHistoryAuthority(LocalDataPaths(_DB_PATH.parent, _DB_PATH))
    memory_db.execute("BEGIN")
    memory_db.execute("INSERT INTO caller_changes VALUES ('keep uncommitted')")
    if damaged:
        memory_db.execute(
            "UPDATE draws SET special_numbers_json = '[8]' WHERE draw_number = '00000002'"
        )
        with (
            pytest.raises(
                CausalHistoryAuthorityError, match="does not match normalized_record_hash"
            ),
            authority.open_verified_snapshot(_TARGET, connection=memory_db),
        ):
            pytest.fail("damaged borrowed snapshot unexpectedly loaded")
    else:
        with authority.open_verified_snapshot(_TARGET, connection=memory_db) as (same, snapshot):
            assert same is memory_db
            assert snapshot.ref.draw_count == 2
    assert memory_db.in_transaction
    assert memory_db.execute("SELECT count(*) FROM caller_changes").fetchone() == (1,)
    memory_db.rollback()
    assert memory_db.execute("SELECT count(*) FROM caller_changes").fetchone() == (0,)


@pytest.mark.parametrize("entry", ["big_lotto_tool", "forward_cycle"])
def test_wal_writer_commit_during_causal_read_preserves_snapshot(
    entry: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both product loaders read their verified history from the pre-commit snapshot."""
    database = tmp_path / "causal-history.sqlite3"
    changed_numbers = (1, 2, 3, 4, 5, 8)
    changed_hash = normalized_draw_record_hash(
        lottery_type=LotteryType.BIG_LOTTO,
        draw_number="00000002",
        draw_date_value=_DATE,
        main_numbers=changed_numbers,
        special_numbers=_SPECIAL,
    )
    with sqlite3.connect(database, isolation_level=None) as setup:
        assert setup.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        setup.executescript(
            """
            CREATE TABLE schema_migrations(version INTEGER NOT NULL);
            CREATE TABLE draws(
                lottery_type TEXT, draw_number TEXT, draw_date TEXT, normalized_record_hash TEXT,
                main_numbers_json TEXT, special_numbers_json TEXT, created_at TEXT
            );
            """
        )
        setup.execute("INSERT INTO schema_migrations VALUES (?)", (CURRENT_SCHEMA_VERSION,))
        for number in ("00000002", "00000009"):
            setup.execute(
                "INSERT INTO draws VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    LotteryType.BIG_LOTTO.value,
                    number,
                    _DATE.isoformat(),
                    _hash(number),
                    json.dumps(_MAIN),
                    json.dumps(_SPECIAL),
                    "2026-08-14T08:00:00+00:00",
                ),
            )

    events: list[str] = []

    class InterleavedReader(sqlite3.Connection):
        def execute(self, sql: str, parameters: object = (), /) -> sqlite3.Cursor:
            if "FROM draws" in sql and not events:
                assert self.in_transaction
                events.append("writer_started_before_history_query")
                with sqlite3.connect(database, isolation_level=None) as writer:
                    writer.execute("BEGIN IMMEDIATE")
                    writer.execute(
                        "UPDATE draws SET main_numbers_json = ?, normalized_record_hash = ? "
                        "WHERE draw_number = '00000002'",
                        (json.dumps(changed_numbers), changed_hash),
                    )
                    writer.execute("COMMIT")
                events.append("writer_committed")
            return super().execute(sql, parameters)

    @contextmanager
    def open_history(
        paths: LocalDataPaths, *, read_only: bool = False
    ) -> Iterator[sqlite3.Connection]:
        assert read_only
        assert paths.database == database
        connection = sqlite3.connect(
            database.as_uri() + "?mode=ro",
            uri=True,
            isolation_level=None,
            factory=InterleavedReader,
        )
        try:
            yield connection
        finally:
            connection.close()

    monkeypatch.setattr(authority_module, "open_database", open_history)
    if entry == "big_lotto_tool":
        snapshot = load_canonical_history(
            database, target_draw_number=_TARGET.draw_number, target_draw_date=_DATE.isoformat()
        )
        assert tuple(row.numbers for row in snapshot.rows) == (_MAIN, _MAIN)
        assert snapshot.normalized_record_hashes == (_hash("00000002"), _hash("00000009"))
    else:
        snapshot = load_causal_history(
            database,
            target=ForwardCycleTarget(
                _TARGET.lottery_type.value,
                _TARGET.draw_number,
                _DATE.isoformat(),
                "2026-08-14T20:30:00+08:00",
            ),
            lottery_type=_TARGET.lottery_type,
            operation_root=tmp_path / "outcomes",
            row_factory=lambda *row: row,
            as_of=datetime(2026, 8, 14, 12, tzinfo=UTC),
        )
        assert tuple(row[2] for row in snapshot.rows) == (_MAIN, _MAIN)
        assert snapshot.latest_known_draw_at_prediction_time == "00000009"

    assert events == ["writer_started_before_history_query", "writer_committed"]
    assert snapshot.draw_count == 2
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as verification:
        assert verification.execute(
            "SELECT main_numbers_json, normalized_record_hash FROM draws "
            "WHERE draw_number = '00000002'"
        ).fetchone() == (json.dumps(changed_numbers), changed_hash)
