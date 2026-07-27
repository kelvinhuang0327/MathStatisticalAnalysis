"""Registration, validation order, and sanitized CLI error tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

import lottolab.interfaces.cli.ordered_candidate_materialization as cli_module
from lottolab.interfaces.cli.main import app

runner = CliRunner()


def _args(output: Path, *extra: str) -> list[str]:
    return [
        "materialize-ordered-candidate-emissions",
        "--lottery-type",
        "BIG_LOTTO",
        "--dataset-id",
        "dataset",
        "--dataset-version",
        "v1",
        "--source-snapshot-sha256",
        "a" * 64,
        "--target-draw",
        "101",
        "--strategy-id",
        "biglotto_social_wisdom_anti_popularity",
        "--minimum-history-draws",
        "1",
        "--maximum-history-draws",
        "100",
        "--replicate",
        "1",
        "--output-directory",
        str(output),
        *extra,
    ]


def test_command_is_registered() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "materialize-ordered-candidate-emissions" in result.stdout


def test_replicate_other_than_one_fails_before_data_path_or_output_access(
    tmp_path: Path,
) -> None:
    data = tmp_path / "must-not-exist-data"
    output = tmp_path / "must-not-exist-output"
    args = _args(output)
    args[args.index("--replicate") + 1] = "2"

    result = runner.invoke(
        app,
        args,
        env={"LOTTOLAB_DATA_DIR": str(data)},
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == (
        "materialize-ordered-candidate-emissions error: "
        "replicate must be exactly 1\n"
    )
    assert not data.exists()
    assert not output.exists()


def test_non_big_lotto_fails_closed_without_database_or_writer_access(
    tmp_path: Path,
) -> None:
    data = tmp_path / "must-not-exist-data"
    output = tmp_path / "must-not-exist-output"
    args = _args(output)
    args[args.index("--lottery-type") + 1] = "DAILY_539"

    result = runner.invoke(
        app,
        args,
        env={"LOTTOLAB_DATA_DIR": str(data)},
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "lottery type must be BIG_LOTTO" in result.stderr
    assert not data.exists()
    assert not output.exists()


@pytest.mark.parametrize(
    "missing_option",
    (
        "--dataset-id",
        "--dataset-version",
        "--source-snapshot-sha256",
        "--target-draw",
        "--strategy-id",
        "--minimum-history-draws",
        "--maximum-history-draws",
        "--replicate",
        "--output-directory",
    ),
)
def test_required_options_fail_with_empty_stdout(
    tmp_path: Path,
    missing_option: str,
) -> None:
    args = _args(tmp_path / "output")
    index = args.index(missing_option)
    del args[index : index + 2]

    result = runner.invoke(app, args)

    assert result.exit_code != 0
    assert result.stdout == ""
    assert "Usage:" in result.stderr
    assert "Traceback" not in result.stderr


def test_unexpected_failure_is_sanitized_and_leaks_no_internal_detail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(**_kwargs: object) -> str:
        raise RuntimeError("SELECT secret FROM /absolute/private/database")

    monkeypatch.setattr(
        cli_module,
        "build_ordered_candidate_materialization_cli_summary",
        explode,
    )

    result = runner.invoke(app, _args(tmp_path / "output"))

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == (
        "materialize-ordered-candidate-emissions error: "
        "materialization failed safely\n"
    )
    assert "SELECT" not in result.stderr
    assert "/absolute" not in result.stderr
    assert "Traceback" not in result.stderr
