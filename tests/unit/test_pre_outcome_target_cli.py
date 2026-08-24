"""CLI contracts for the canonical pre-outcome operational binding."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click import unstyle
from typer.testing import CliRunner

import lottolab.interfaces.cli.pre_outcome_target as target_cli
from lottolab.application.future_draw_identity import FutureDrawIdentityUnavailableError
from lottolab.domain.draws import LotteryType
from lottolab.infrastructure.persistence.draw_schema import DATA_DIRECTORY_ENV
from lottolab.interfaces.cli.main import app

runner = CliRunner()


def test_command_is_registered_with_required_multilottery_option() -> None:
    root_help = runner.invoke(app, ["--help"])
    command_help = runner.invoke(
        app,
        ["register-pre-outcome-target", "--help"],
        color=True,
    )
    help_text = unstyle(command_help.stdout)

    assert root_help.exit_code == 0
    assert "register-pre-outcome-target" in root_help.stdout
    assert command_help.exit_code == 0
    assert "--lottery-type" in help_text
    assert "BIG_LOTTO" in help_text
    assert "DAILY_539" in help_text
    assert "POWER_LOTTO" in help_text
    assert "required" in help_text.lower()


def test_missing_required_lottery_type_is_a_usage_error() -> None:
    result = runner.invoke(app, ["register-pre-outcome-target"])

    assert result.exit_code != 0
    assert result.stdout == ""
    assert "Usage:" in result.stderr
    assert "Traceback" not in result.stderr


def test_unknown_lottery_type_is_rejected_before_composition(tmp_path: Path) -> None:
    data_directory = tmp_path / "must-not-exist"
    result = runner.invoke(
        app,
        ["register-pre-outcome-target", "--lottery-type", "UNKNOWN"],
        env={DATA_DIRECTORY_ENV: str(data_directory)},
    )

    assert result.exit_code != 0
    assert result.stdout == ""
    assert "Invalid value" in result.stderr
    assert not data_directory.exists()


@pytest.mark.parametrize("lottery_type", ["BIG_LOTTO", "DAILY_539", "POWER_LOTTO"])
def test_missing_database_schedule_authority_returns_closed_json_without_writes(
    tmp_path: Path,
    lottery_type: str,
) -> None:
    data_directory = tmp_path / f"absent-{lottery_type.lower()}"
    result = runner.invoke(
        app,
        ["register-pre-outcome-target", "--lottery-type", lottery_type],
        env={DATA_DIRECTORY_ENV: str(data_directory)},
    )

    assert result.exit_code == 0
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload == {
        "authority_root": str(data_directory / "pre-outcome-target-authority-v1"),
        "causal_history": None,
        "future_identity_database": str(data_directory / "lottolab.db"),
        "lottery_type": lottery_type,
        "record_path": None,
        "record_sha256": None,
        "registration": None,
        "status": "NO_CANONICAL_TARGET_ANNOUNCEMENT",
        "target": None,
    }
    assert not data_directory.exists()


def test_operational_failures_are_sanitized_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise target_cli.PreOutcomeTargetCliError("TARGET_AUTHORITY_CORRUPT")

    monkeypatch.setattr(target_cli, "run_pre_outcome_target_registration", fail)

    result = runner.invoke(
        app,
        ["register-pre-outcome-target", "--lottery-type", "BIG_LOTTO"],
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == (
        "register-pre-outcome-target error: TARGET_AUTHORITY_CORRUPT\n"
    )
    assert "Traceback" not in result.stderr


def test_future_identity_reader_failure_is_mapped_to_sanitized_authority_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise FutureDrawIdentityUnavailableError("sensitive implementation detail")

    monkeypatch.setattr(target_cli, "compose_pre_outcome_target_operational_service", fail)

    with pytest.raises(
        target_cli.PreOutcomeTargetCliError,
        match=r"^OPERATIONAL_DATA_AUTHORITY_UNAVAILABLE$",
    ):
        target_cli.run_pre_outcome_target_registration(LotteryType.BIG_LOTTO)
