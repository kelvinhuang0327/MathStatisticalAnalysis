from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lottolab.infrastructure.persistence.research_schema import (
    APPEND_ONLY_TRIGGER_NAMES,
    CURRENT_SCHEMA_VERSION,
    DATA_DIRECTORY_ENV,
    MIGRATION_CHECKSUM,
    RESEARCH_DATABASE_FILENAME,
    TABLE_NAMES,
)
from lottolab.interfaces.cli.main import app

runner = CliRunner()


def test_verify_only_absent_store_exits_nonzero_and_creates_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_directory = tmp_path.resolve() / "research-data"
    monkeypatch.setenv(DATA_DIRECTORY_ENV, str(data_directory))

    result = runner.invoke(app, ["research-store", "--verify-only"])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == "research-store error: research store is absent\n"
    assert not data_directory.exists()


def test_create_then_verify_reports_full_store_health(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_directory = tmp_path.resolve() / "research-data"
    monkeypatch.setenv(DATA_DIRECTORY_ENV, str(data_directory))

    created = runner.invoke(app, ["research-store", "--create"])
    verified = runner.invoke(app, ["research-store", "--verify-only"])

    assert created.exit_code == verified.exit_code == 0
    assert created.stderr == verified.stderr == ""
    assert created.stdout == verified.stdout
    report = json.loads(created.stdout)
    assert report["healthy"] is True
    assert report["resolved_path"] == str(
        data_directory / RESEARCH_DATABASE_FILENAME
    )
    assert report["schema_version"] == CURRENT_SCHEMA_VERSION
    assert report["migration_checksum"] == MIGRATION_CHECKSUM
    assert report["migration_checksum_match"] is True
    assert report["table_inventory"] == sorted(TABLE_NAMES)
    assert report["append_only_trigger_count"] == len(APPEND_ONLY_TRIGGER_NAMES)
    assert report["missing_append_only_triggers"] == []
    assert report["missing_artifact_references"] == 0
    assert report["wal_sidecars_present"] == []
    assert report["resumable_runs"] == []
    assert {row["table_name"] for row in report["row_counts"]} == set(TABLE_NAMES)
    assert not Path(f"{report['resolved_path']}-wal").exists()
    assert not Path(f"{report['resolved_path']}-shm").exists()
