"""CLI contracts for the explicit Next-Draw Recommendation seal command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click import unstyle
from typer.testing import CliRunner

import lottolab.interfaces.cli.next_draw_recommendation_seal as seal_cli
from lottolab.infrastructure.persistence.draw_schema import DATA_DIRECTORY_ENV
from lottolab.interfaces.cli.main import app

runner = CliRunner()


def test_command_is_registered_with_required_multilottery_option() -> None:
    root_help = runner.invoke(app, ["--help"])
    command_help = runner.invoke(
        app,
        ["seal-next-draw-recommendation", "--help"],
        color=True,
    )
    help_text = unstyle(command_help.stdout)

    assert root_help.exit_code == 0
    assert "seal-next-draw-recommendation" in root_help.stdout
    assert command_help.exit_code == 0
    assert "--lottery-type" in help_text
    assert "BIG_LOTTO" in help_text
    assert "required" in help_text.lower()


def test_missing_required_lottery_type_is_a_usage_error() -> None:
    result = runner.invoke(app, ["seal-next-draw-recommendation"])

    assert result.exit_code != 0
    assert result.stdout == ""
    assert "Usage:" in result.stderr
    assert "Traceback" not in result.stderr


def test_unknown_lottery_type_is_rejected_before_composition(tmp_path: Path) -> None:
    data_directory = tmp_path / "must-not-exist"
    result = runner.invoke(
        app,
        ["seal-next-draw-recommendation", "--lottery-type", "UNKNOWN"],
        env={DATA_DIRECTORY_ENV: str(data_directory)},
    )

    assert result.exit_code != 0
    assert result.stdout == ""
    assert "Invalid value" in result.stderr
    assert not data_directory.exists()


def test_missing_database_schedule_authority_returns_no_eligible_target_without_writes(
    tmp_path: Path,
) -> None:
    data_directory = tmp_path / "absent-big-lotto"
    result = runner.invoke(
        app,
        ["seal-next-draw-recommendation", "--lottery-type", "BIG_LOTTO"],
        env={DATA_DIRECTORY_ENV: str(data_directory)},
    )

    assert result.exit_code == 0
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload == {
        "lottery_type": "BIG_LOTTO",
        "record_path": None,
        "seal": None,
        "seal_digest": None,
        "seal_root": str(data_directory / "next-draw-recommendation-seals-v1"),
        "status": "NO_ELIGIBLE_TARGET",
    }
    # No schedule authority exists at all: the seal command must never
    # create the local data directory, the target-authority store, or the
    # seal store just to discover there is nothing eligible to seal.
    assert not data_directory.exists()


def test_operational_failures_are_sanitized_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise seal_cli.NextDrawRecommendationSealCliError("TARGET_AUTHORITY_CORRUPT")

    monkeypatch.setattr(seal_cli, "run_next_draw_recommendation_seal", fail)

    result = runner.invoke(app, ["seal-next-draw-recommendation", "--lottery-type", "BIG_LOTTO"])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "seal-next-draw-recommendation error: TARGET_AUTHORITY_CORRUPT" in result.stderr
    assert "Traceback" not in result.stderr
