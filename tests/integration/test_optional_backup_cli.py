from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from lottolab.interfaces.cli import optional_backup
from lottolab.interfaces.cli.main import app


@pytest.fixture
def source(tmp_path: Path) -> Path:
    database = tmp_path / "source.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE sample (value INTEGER)")
        connection.execute("INSERT INTO sample VALUES (42)")
    return database


@pytest.mark.parametrize(
    "free", [optional_backup.MIN_FREE_BYTES, optional_backup.MIN_FREE_BYTES + 1]
)
def test_backup_accepts_threshold_and_checks_resolved_destination_volume(
    source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, free: int
) -> None:
    target_dir = tmp_path / "actual"
    target_dir.mkdir()
    link = tmp_path / "destination-link"
    link.symlink_to(target_dir, target_is_directory=True)
    checked = []

    def disk_usage(path: Path) -> SimpleNamespace:
        checked.append(path)
        return SimpleNamespace(free=free)

    monkeypatch.setattr(optional_backup.shutil, "disk_usage", disk_usage)
    destination = link / "backup.sqlite3"
    result = CliRunner().invoke(app, ["optional-backup", str(source), str(destination)])
    assert result.exit_code == 0, result.output
    assert checked == [target_dir.resolve()]
    with sqlite3.connect(destination) as connection:
        assert connection.execute("SELECT value FROM sample").fetchall() == [(42,)]


def test_low_space_refuses_without_creating_destination_and_normal_read_still_works(
    source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        shutil, "disk_usage", lambda _: SimpleNamespace(free=optional_backup.MIN_FREE_BYTES - 1)
    )
    destination = tmp_path / "backup.sqlite3"
    result = CliRunner().invoke(app, ["optional-backup", str(source), str(destination)])
    assert result.exit_code == 1
    assert "optional backup refused" in result.output
    assert not destination.exists()
    assert not list(tmp_path.glob(".optional-backup-*"))
    result = CliRunner().invoke(app, ["replay-backfill", "--schema"])
    assert result.exit_code == 0, result.output
    with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as connection:
        assert connection.execute("SELECT value FROM sample").fetchall() == [(42,)]


@pytest.mark.parametrize("symlink", [False, True])
def test_existing_destination_is_never_replaced(
    source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, symlink: bool
) -> None:
    monkeypatch.setattr(
        shutil, "disk_usage", lambda _: SimpleNamespace(free=optional_backup.MIN_FREE_BYTES)
    )
    existing = tmp_path / "existing"
    existing.write_bytes(b"keep")
    destination = tmp_path / "backup"
    if symlink:
        destination.symlink_to(existing)
    else:
        destination = existing
    result = CliRunner().invoke(app, ["optional-backup", str(source), str(destination)])
    assert result.exit_code == 1
    assert existing.read_bytes() == b"keep"


def test_backup_failure_closes_connections_and_removes_partial_file(
    source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        shutil, "disk_usage", lambda _: SimpleNamespace(free=optional_backup.MIN_FREE_BYTES)
    )
    original_connect = sqlite3.connect
    closed = []

    class FailingSource:
        def __init__(self, connection: sqlite3.Connection) -> None:
            self.connection = connection

        def execute(self, sql: str):
            return self.connection.execute(sql)

        def backup(self, destination: sqlite3.Connection) -> None:
            destination.execute("CREATE TABLE partial (x)")
            raise sqlite3.OperationalError("simulated backup failure")

        def close(self) -> None:
            self.connection.close()
            closed.append(True)

    def connect(*args, **kwargs):
        connection = original_connect(*args, **kwargs)
        return FailingSource(connection) if kwargs.get("uri") else connection

    monkeypatch.setattr(optional_backup.sqlite3, "connect", connect)
    destination = tmp_path / "backup.sqlite3"
    result = CliRunner().invoke(app, ["optional-backup", str(source), str(destination)])
    assert result.exit_code == 1
    assert "simulated backup failure" in result.output
    assert closed == [True]
    assert not destination.exists()
    assert not list(tmp_path.glob(".optional-backup-*"))
