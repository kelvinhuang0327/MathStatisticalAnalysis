"""Unit coverage for Replay CLI registration, validation, and error boundaries."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

import lottolab.interfaces.cli.replay_predictions as replay_cli
from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import LifecycleStatus, StrategyDescriptor
from lottolab.interfaces.cli.main import app
from lottolab.strategies.catalog import StrategyCatalog

runner = CliRunner()
_ONLINE_STRATEGY = "biglotto_social_wisdom_anti_popularity"


def _args(*extra: str) -> list[str]:
    return [
        "replay-predictions",
        "--dataset-id",
        "dataset",
        "--dataset-version",
        "v1",
        "--target-draw",
        "100",
        "--strategy-id",
        _ONLINE_STRATEGY,
        *extra,
    ]


def test_replay_predictions_command_is_registered() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "replay-predictions" in result.stdout


@pytest.mark.parametrize(
    ("args", "missing_option"),
    [
        (
            [
                "replay-predictions",
                "--dataset-version",
                "v1",
                "--target-draw",
                "100",
                "--strategy-id",
                _ONLINE_STRATEGY,
            ],
            "--dataset-id",
        ),
        (
            [
                "replay-predictions",
                "--dataset-id",
                "dataset",
                "--target-draw",
                "100",
                "--strategy-id",
                _ONLINE_STRATEGY,
            ],
            "--dataset-version",
        ),
        (
            [
                "replay-predictions",
                "--dataset-id",
                "dataset",
                "--dataset-version",
                "v1",
                "--strategy-id",
                _ONLINE_STRATEGY,
            ],
            "--target-draw",
        ),
        (
            [
                "replay-predictions",
                "--dataset-id",
                "dataset",
                "--dataset-version",
                "v1",
                "--target-draw",
                "100",
            ],
            "--strategy-id",
        ),
    ],
)
def test_required_options_fail_closed(args: list[str], missing_option: str) -> None:
    result = runner.invoke(app, args)

    assert result.exit_code != 0
    assert missing_option in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (_args("--dataset-id", " "), "dataset ID must not be blank"),
        (_args("--dataset-version", " "), "dataset version must not be blank"),
        (_args("--target-draw", " "), "target draws must not be blank"),
        (_args("--strategy-id", " "), "strategy IDs must not be blank"),
        (_args("--target-draw", "100"), "target draws must not contain duplicates"),
        (_args("--strategy-id", _ONLINE_STRATEGY), "strategy IDs must not contain duplicates"),
        (
            _args("--maximum-history-draws", "4", "--minimum-history-draws", "5"),
            "minimum history draws must not exceed maximum",
        ),
    ],
)
def test_semantically_invalid_inputs_are_sanitized(args: list[str], message: str) -> None:
    result = runner.invoke(app, args)

    assert result.exit_code == 1
    assert result.stdout == ""
    assert message in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("--maximum-history-draws", "0"),
        ("--maximum-history-draws", "-1"),
        ("--minimum-history-draws", "0"),
        ("--minimum-history-draws", "-1"),
    ],
)
def test_nonpositive_history_bounds_are_rejected(option: str, value: str) -> None:
    result = runner.invoke(app, _args(option, value))

    assert result.exit_code != 0
    assert result.stdout == ""
    assert option in result.stderr
    assert "Traceback" not in result.stderr


def test_unknown_strategy_fails_before_database_access(tmp_path: Path) -> None:
    data_directory = tmp_path / "must-not-be-created"
    result = runner.invoke(
        app,
        _args("--strategy-id", "unknown-strategy"),
        env={"LOTTOLAB_DATA_DIR": str(data_directory)},
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "unknown strategy ID: unknown-strategy" in result.stderr
    assert not data_directory.exists()


def test_unavailable_strategy_fails_before_database_access(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    unavailable = StrategyDescriptor(
        strategy_id="offline-strategy",
        strategy_name="Offline strategy",
        version="v1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.OBSERVATION,
        executable=False,
    )
    monkeypatch.setattr(
        replay_cli,
        "production_catalog",
        lambda: StrategyCatalog((unavailable,)),
    )
    data_directory = tmp_path / "must-not-be-created"

    result = runner.invoke(
        app,
        [
            "replay-predictions",
            "--dataset-id",
            "dataset",
            "--dataset-version",
            "v1",
            "--target-draw",
            "100",
            "--strategy-id",
            unavailable.strategy_id,
        ],
        env={"LOTTOLAB_DATA_DIR": str(data_directory)},
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "strategy is unavailable: offline-strategy" in result.stderr
    assert not data_directory.exists()


def test_unexpected_failure_is_sanitized_without_internal_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(**_kwargs: object) -> bytes:
        raise RuntimeError("SELECT secret FROM /absolute/private/database")

    monkeypatch.setattr(replay_cli, "build_replay_predictions_cli_artifact", explode)

    result = runner.invoke(app, _args())

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == "replay-predictions error: request failed safely\n"
    assert "SELECT" not in result.stderr
    assert "/absolute" not in result.stderr
    assert "Traceback" not in result.stderr


def test_output_file_option_is_absent_and_creates_nothing(tmp_path: Path) -> None:
    output_path = tmp_path / "forbidden-artifact.json"

    result = runner.invoke(app, _args("--output-file", str(output_path)))

    assert result.exit_code != 0
    assert result.stdout == ""
    assert "--output-file" in result.stderr
    assert not output_path.exists()
