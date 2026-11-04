from __future__ import annotations

import fcntl
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import pytest

import lottolab.infrastructure.persistence.project_database_paths as project_database_paths
from lottolab.infrastructure.persistence.replay_backfill_store import (
    SCHEMA_CHECKSUM,
    SCHEMA_SQL,
    SCHEMA_VERSION,
    SQLiteBackfillStore,
)
from lottolab.interfaces.cli.replay_backfill import main as replay_backfill_main

_SUBPROCESS_WRITER = """
import sys
from pathlib import Path
import lottolab.infrastructure.persistence.project_database_paths as locations
locations.PROJECT_ROOT = Path(sys.argv[1])
project_root, mode, database, test_root, source = sys.argv[1:]
from lottolab.infrastructure.persistence.replay_backfill_store import SQLiteBackfillStore
try:
    store = SQLiteBackfillStore(Path(database))
    if mode == "write_transaction":
        with store.write_transaction():
            pass
    elif mode == "prepare":
        store.prepare({})
    elif mode == "save_many":
        store.save_many("run", ())
    elif mode == "replay":
        from datetime import date
        from lottolab.application.historical_replay_adapters import (
            BigLottoReplayAdapter,
            ReplayStrategyBinding,
        )
        from lottolab.application.use_cases.replay_backfill import (
            BackfillSelection,
            ReplayBackfill,
        )
        from lottolab.domain.draws import LotteryType
        from lottolab.domain.historical_replay import (
            ReplayBehavior,
            ReplayDraw,
            ReplayStrategy,
        )

        class Producer:
            strategy_id = "two-tickets"

            def get_bets(self, history, lottery_type):
                return ((1, 2, 3, 4, 5, 6), (1, 2, 3, 4, 5, 7))

        producer = Producer()
        strategy = ReplayStrategy(
            producer.strategy_id,
            "two-tickets",
            "v1",
            ReplayBehavior.DETERMINISTIC,
            2,
            2,
            fingerprint="source-v1",
        )
        adapter = BigLottoReplayAdapter((ReplayStrategyBinding(strategy, producer),))
        replay = ReplayBackfill(
            adapter=adapter,
            strategies=(strategy,),
            draws=(
                ReplayDraw(
                    LotteryType.BIG_LOTTO,
                    "100000001",
                    date(2020, 1, 1),
                    (1, 2, 3, 4, 5, 6),
                    7,
                ),
            ),
            source_identity="synthetic-fixture-v1",
            store=store,
            execution_version="test-source-v1",
        )
        replay.execute(BackfillSelection(latest=1))
    elif mode == "import_stage":
        from lottolab.interfaces.cli.replay_backfill import main

        raise SystemExit(
            main(
                ["import-stage", "--source", source, "--database", database],
                test_only_external_database_root=Path(test_root),
            )
        )
    else:
        raise ValueError(f"unknown test mode: {mode}")
except PermissionError as exc:
    print(str(exc), file=sys.stderr)
    raise SystemExit(23)
"""


@pytest.fixture
def fake_canonical_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    project_root = tmp_path / "fake-canonical-project"
    database_directory = project_root / "data" / "databases"
    database_directory.mkdir(parents=True)
    (project_root / ".task-data" / "_scratch").mkdir(parents=True)
    (project_root / ".gitignore").write_text("/.task-data/_scratch/\n", encoding="utf-8")
    subprocess.run(
        ["git", "init", "--quiet", str(project_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    database = database_directory / "replay-backfill.sqlite3"
    (database_directory / "database-locations.json").write_text(
        json.dumps(
            {
                "version": 1,
                "read_databases": {
                    "LOTTOLAB_REPLAY_BACKFILL_DB": database.name,
                },
                "writable_databases": [database.name],
            }
        ),
        encoding="utf-8",
    )
    _create_empty_backfill_database(database)
    monkeypatch.setattr(project_database_paths, "PROJECT_ROOT", project_root)
    return project_root, database


def _create_empty_backfill_database(database: Path) -> None:
    with sqlite3.connect(database) as connection:
        connection.executescript(SCHEMA_SQL)
        connection.execute(
            "INSERT INTO replay_backfill_schema(version,checksum) VALUES(?,?)",
            (SCHEMA_VERSION, SCHEMA_CHECKSUM),
        )


def _fingerprint(database: Path) -> tuple[str, int]:
    return hashlib.sha256(database.read_bytes()).hexdigest(), database.stat().st_mtime_ns


@contextmanager
def _hold_writer_lock(lock_path: Path) -> Generator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _run_writer_subprocess(
    project_root: Path,
    mode: str,
    database: Path,
    test_root: Path,
    source: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    source_root = Path(__file__).resolve().parents[2] / "src"
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = str(source_root) + (
        os.pathsep + existing_pythonpath if existing_pythonpath else ""
    )
    return subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            _SUBPROCESS_WRITER,
            str(project_root),
            mode,
            str(database),
            str(test_root),
            str(source or ""),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
        timeout=5,
    )


def test_second_writer_fails_without_waiting_or_changing_database(
    fake_canonical_database: tuple[Path, Path], tmp_path: Path
) -> None:
    project_root, database = fake_canonical_database
    store = SQLiteBackfillStore(database)
    lock_path = project_root / "data" / "databases" / "locks" / f"{database.name}.writer.lock"

    with store.write_transaction():
        before = _fingerprint(database)
        for mode in ("write_transaction", "prepare", "save_many", "replay"):
            started_at = time.monotonic()
            result = _run_writer_subprocess(project_root, mode, database, tmp_path)
            assert time.monotonic() - started_at < 3.0
            assert result.returncode == 23, result.stderr
            assert str(lock_path) in result.stderr
            assert "finish or stop the other process" in result.stderr
            assert _fingerprint(database) == before

    assert lock_path.is_file()
    assert not (database.parent / lock_path.name).exists()


def test_writer_lock_releases_after_success_and_failure(
    fake_canonical_database: tuple[Path, Path], tmp_path: Path
) -> None:
    project_root, database = fake_canonical_database
    store = SQLiteBackfillStore(database)

    with store.write_transaction():
        pass
    successful_retry = _run_writer_subprocess(project_root, "write_transaction", database, tmp_path)
    assert successful_retry.returncode == 0, successful_retry.stderr

    with (
        pytest.raises(sqlite3.OperationalError, match="no such table"),
        store.write_transaction() as connection,
    ):
        connection.execute("INSERT INTO missing_table VALUES (1)")
    failed_retry = _run_writer_subprocess(project_root, "write_transaction", database, tmp_path)
    assert failed_retry.returncode == 0, failed_retry.stderr

    with pytest.raises(KeyError):
        store.prepare({})
    failed_prepare_retry = _run_writer_subprocess(
        project_root, "write_transaction", database, tmp_path
    )
    assert failed_prepare_retry.returncode == 0, failed_prepare_retry.stderr


def test_import_stage_target_is_locked_but_stage_source_is_read_only(
    fake_canonical_database: tuple[Path, Path], tmp_path: Path
) -> None:
    project_root, target = fake_canonical_database
    source = tmp_path / "stage.sqlite3"
    _create_empty_backfill_database(source)
    store = SQLiteBackfillStore(target)
    lock_path = project_root / "data" / "databases" / "locks" / f"{target.name}.writer.lock"

    with store.write_transaction():
        before = _fingerprint(target)
        blocked = _run_writer_subprocess(
            project_root, "import_stage", target, tmp_path, source=source
        )
        assert blocked.returncode == 1
        assert str(lock_path) in blocked.stderr
        assert "finish or stop the other process" in blocked.stderr
        assert _fingerprint(target) == before

    source_lock = source.parent / f"{source.name}.writer.lock"
    with _hold_writer_lock(source_lock):
        source_locked = _run_writer_subprocess(
            project_root, "import_stage", target, tmp_path, source=source
        )
        assert source_locked.returncode == 0, source_locked.stderr


def test_read_only_query_and_schema_ignore_writer_lock(
    fake_canonical_database: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, database = fake_canonical_database
    store = SQLiteBackfillStore(database)

    with store.write_transaction():
        assert store.query()["total_count"] == 0
        assert replay_backfill_main(["--schema"]) == 0

    assert SCHEMA_SQL.strip() in capsys.readouterr().out


def test_scratch_database_lock_is_beside_database(
    fake_canonical_database: tuple[Path, Path],
) -> None:
    project_root, _ = fake_canonical_database
    scratch_directory = project_root / ".task-data" / "_scratch" / "writer-locks"
    scratch_directory.mkdir()
    scratch_database = scratch_directory / "replay.sqlite3"
    _create_empty_backfill_database(scratch_database)

    with SQLiteBackfillStore(scratch_database).write_transaction():
        pass

    assert (scratch_directory / "replay.sqlite3.writer.lock").is_file()
    assert not (
        project_root / "data" / "databases" / "locks" / "replay.sqlite3.writer.lock"
    ).exists()
