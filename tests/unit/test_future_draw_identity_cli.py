"""Root CLI contracts for preview-first manual future identity supplementation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from click import unstyle
from typer.testing import CliRunner

from lottolab.infrastructure.persistence.draw_schema import (
    DATA_DIRECTORY_ENV,
    initialize_schema,
    resolve_local_data_paths,
)
from lottolab.infrastructure.pre_outcome_target_operational import (
    OPERATIONAL_ANNOUNCEMENT_SCHEMA_VERSION,
)
from lottolab.interfaces.cli.main import app

runner = CliRunner()


def _input(path: Path, *, draw_date: str = "2099-01-02") -> str:
    document = {
        "announcements": [
            {
                "schedule_timezone": "Asia/Taipei",
                "scheduled_at": f"{draw_date}T12:30:00Z",
                "source": {
                    "observed_at": "2099-01-01T00:00:00Z",
                    "source_id": "TAIWAN_LOTTERY_OFFICIAL_SCHEDULE",
                    "source_locator": "https://www.taiwanlottery.com/schedule/209900001",
                    "source_payload_sha256": "a" * 64,
                    "source_version": "taiwan-lottery-official-schedule-v1",
                },
                "target": {
                    "draw_date": draw_date,
                    "draw_number": "209900001",
                    "lottery_type": "BIG_LOTTO",
                },
            }
        ],
        "schema_version": OPERATIONAL_ANNOUNCEMENT_SCHEMA_VERSION,
    }
    encoded = json.dumps(document, separators=(",", ":"), sort_keys=True).encode()
    path.write_bytes(encoded)
    path.chmod(0o600)
    return hashlib.sha256(encoded).hexdigest()


def _arguments(path: Path, digest: str, *, commit: bool = False) -> list[str]:
    arguments = [
        "supplement-future-draw-identity",
        "--input",
        str(path),
        "--expected-input-sha256",
        digest,
        "--lottery-type",
        "BIG_LOTTO",
        "--draw-number",
        "209900001",
    ]
    if commit:
        arguments.append("--commit")
    return arguments


def test_root_command_registers_all_required_manual_gates() -> None:
    root_help = runner.invoke(app, ["--help"])
    command_help = runner.invoke(
        app,
        ["supplement-future-draw-identity", "--help"],
        env={"COLUMNS": "200"},
    )
    help_text = unstyle(command_help.stdout)

    assert root_help.exit_code == 0
    assert "supplement-future-draw-identity" in root_help.stdout
    assert command_help.exit_code == 0
    assert "--input" in help_text
    assert "--expected-input-sha256" in help_text
    assert "--lottery-type" in help_text
    assert "--draw-number" in help_text
    assert "--commit" in help_text


def test_default_preview_is_byte_stable_and_commit_is_explicit(tmp_path: Path) -> None:
    data_directory = tmp_path / "canonical-data"
    paths = resolve_local_data_paths(environ={DATA_DIRECTORY_ENV: str(data_directory)})
    initialize_schema(paths)
    input_path = tmp_path / "owner-certified.json"
    digest = _input(input_path)
    environment = {DATA_DIRECTORY_ENV: str(data_directory)}
    before = (
        hashlib.sha256(paths.database.read_bytes()).hexdigest(),
        paths.database.stat().st_size,
        paths.database.stat().st_mtime_ns,
    )

    preview = runner.invoke(app, _arguments(input_path, digest), env=environment)

    after = (
        hashlib.sha256(paths.database.read_bytes()).hexdigest(),
        paths.database.stat().st_size,
        paths.database.stat().st_mtime_ns,
    )
    assert preview.exit_code == 0
    assert preview.stderr == ""
    preview_payload = json.loads(preview.stdout)
    assert preview_payload["status"] == "PREVIEW_ONLY"
    assert preview_payload["zero_write"] is True
    assert preview_payload["commit_requested"] is False
    assert preview_payload["disposition"] == "INSERTED"
    assert preview_payload["run_id"] is None
    assert after == before

    committed = runner.invoke(
        app,
        _arguments(input_path, digest, commit=True),
        env=environment,
    )

    assert committed.exit_code == 0
    assert committed.stderr == ""
    receipt = json.loads(committed.stdout)
    assert receipt["status"] == "SUCCESS"
    assert receipt["zero_write"] is False
    assert receipt["commit_requested"] is True
    assert receipt["disposition"] == "INSERTED"
    assert receipt["inserted_count"] == 1
    assert receipt["run_id"]


def test_invalid_digest_and_non_big_lotto_leave_database_unchanged(tmp_path: Path) -> None:
    data_directory = tmp_path / "canonical-data"
    paths = resolve_local_data_paths(environ={DATA_DIRECTORY_ENV: str(data_directory)})
    initialize_schema(paths)
    input_path = tmp_path / "owner-certified.json"
    digest = _input(input_path)
    environment = {DATA_DIRECTORY_ENV: str(data_directory)}
    before = hashlib.sha256(paths.database.read_bytes()).hexdigest()

    bad_digest = runner.invoke(
        app,
        _arguments(input_path, "0" * 64),
        env=environment,
    )
    other_lottery_arguments = _arguments(input_path, digest)
    other_lottery_arguments[other_lottery_arguments.index("BIG_LOTTO")] = "DAILY_539"
    other_lottery = runner.invoke(app, other_lottery_arguments, env=environment)

    assert bad_digest.exit_code == 1
    assert "MANUAL_SUPPLEMENT_REQUEST_INVALID" in bad_digest.stderr
    assert other_lottery.exit_code == 1
    assert "OWNER_CERTIFIED_INPUT_INVALID" in other_lottery.stderr
    assert hashlib.sha256(paths.database.read_bytes()).hexdigest() == before
