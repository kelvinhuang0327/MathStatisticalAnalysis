from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.fixtures.legacy_reference_corpus import build_legacy_reference_corpus
from typer.testing import CliRunner

import lottolab.interfaces.cli.legacy_reference_import as legacy_reference_import_cli
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


def test_legacy_reference_import_without_data_dir_fails_before_filesystem_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    isolated_home = tmp_path / "isolated-home"
    isolated_home.mkdir()
    monkeypatch.setenv("HOME", str(isolated_home))
    monkeypatch.delenv(DATA_DIRECTORY_ENV, raising=False)
    default_data_directory = (
        isolated_home / "Library" / "Application Support" / "LottoLab"
    )

    result = runner.invoke(
        app,
        [
            "import-biglotto-legacy-reference",
            "--corpus-root",
            str(tmp_path / "unused-corpus-root"),
        ],
    )

    assert result.exit_code != 0
    assert not default_data_directory.exists()


def test_legacy_reference_import_ignores_ambient_data_dir_and_uses_explicit_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ambient_directory = tmp_path / "ambient-should-not-be-used"
    explicit_directory = tmp_path / "explicit-scratch"
    monkeypatch.setenv(DATA_DIRECTORY_ENV, str(ambient_directory))
    monkeypatch.setattr(
        legacy_reference_import_cli,
        "_resolve_source_commit_oid",
        lambda: "a" * 40,
    )
    corpus_root = build_legacy_reference_corpus(tmp_path)

    result = runner.invoke(
        app,
        [
            "import-biglotto-legacy-reference",
            "--corpus-root",
            str(corpus_root),
            "--data-dir",
            str(explicit_directory),
        ],
    )

    assert result.exit_code == 0, result.stderr
    assert not ambient_directory.exists()
    assert (explicit_directory / RESEARCH_DATABASE_FILENAME).exists()
    payload = json.loads(result.stdout)
    assert payload["completed_target_count"] == 2
    assert payload["expected_target_count"] == 2


def test_legacy_reference_import_explicit_scratch_directory_is_resumable_and_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(DATA_DIRECTORY_ENV, raising=False)
    monkeypatch.setattr(
        legacy_reference_import_cli,
        "_resolve_source_commit_oid",
        lambda: "b" * 40,
    )
    corpus_root = build_legacy_reference_corpus(tmp_path)
    data_dir = tmp_path / "scratch"
    invocation = [
        "import-biglotto-legacy-reference",
        "--corpus-root",
        str(corpus_root),
        "--data-dir",
        str(data_dir),
    ]

    first = runner.invoke(app, invocation)
    second = runner.invoke(app, invocation)

    assert first.exit_code == second.exit_code == 0, (first.stderr, second.stderr)
    first_payload = json.loads(first.stdout)
    second_payload = json.loads(second.stdout)
    assert first_payload["idempotent_no_op"] is False
    assert first_payload["targets_created"] == 2
    assert second_payload["idempotent_no_op"] is True
    assert second_payload["targets_created"] == 0
    assert second_payload["completed_target_count"] == 2
