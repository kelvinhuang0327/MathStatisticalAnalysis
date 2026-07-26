"""Unit coverage for the explicit Historical Results import CLI."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pytest
from tests.fixtures.historical.builder import build_small_envelope, envelope_bytes
from typer.testing import CliRunner

import lottolab.interfaces.cli.historical_import as historical_cli
from lottolab.domain.historical_results import (
    HistoricalImportCommitResult,
    HistoricalRunImport,
    HistoricalRunStatus,
)
from lottolab.interfaces.cli.main import app
from lottolab.normalization.historical_import import HistoricalImportVerificationResult

runner = CliRunner()
REPO_ROOT = Path(__file__).resolve().parents[2]


def _task_input(tmp_path: Path, content: bytes = b"{}") -> Path:
    configured_root = os.environ.get("LOTTOLAB_HISTORICAL_IMPORT_TEST_INPUT_ROOT")
    root = Path(configured_root) if configured_root else tmp_path
    case_root = Path(tempfile.mkdtemp(prefix=f"{tmp_path.name}-", dir=root))
    path = case_root / "historical-import.json"
    path.write_bytes(content)
    return path


def _task_database(tmp_path: Path) -> Path:
    configured_root = os.environ.get("LOTTOLAB_HISTORICAL_IMPORT_TEST_DATABASE_ROOT")
    root = Path(configured_root) if configured_root else tmp_path
    case_root = Path(tempfile.mkdtemp(prefix=f"{tmp_path.name}-", dir=root))
    return case_root / "historical-results.db"


def _args(input_path: Path, database: Path) -> list[str]:
    return [
        "import-historical-results",
        "--input",
        str(input_path),
        "--database",
        str(database),
    ]


def _fixed_commit(*, idempotent: bool = False) -> HistoricalImportCommitResult:
    return HistoricalImportCommitResult(
        run_id="fixed-run",
        status=HistoricalRunStatus.COMPLETED,
        import_identity_sha256="a" * 64,
        manifest_sha256="b" * 64,
        is_idempotent_replay=idempotent,
        completed_at="2026-07-26T00:00:00.000000Z",
        error_code=None,
        error_summary=None,
    )


def test_command_is_registered_with_both_required_options() -> None:
    root_help = runner.invoke(app, ["--help"])
    command_help = runner.invoke(app, ["import-historical-results", "--help"])

    assert root_help.exit_code == 0
    assert "import-historical-results" in root_help.stdout
    assert command_help.exit_code == 0
    assert "--input" in command_help.stdout
    assert "--database" in command_help.stdout
    assert "required" in command_help.stdout.lower()


@pytest.mark.parametrize(
    "args",
    [
        ["import-historical-results", "--database", "/tmp/historical.db"],
        ["import-historical-results", "--input", "/tmp/historical.json"],
    ],
)
def test_both_options_are_required(args: list[str]) -> None:
    result = runner.invoke(app, args)

    assert result.exit_code != 0
    assert result.stdout == ""
    assert "Usage:" in result.stderr
    assert "Traceback" not in result.stderr


def test_relative_database_path_is_rejected_before_normalization(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    input_path = _task_input(tmp_path)
    called = False

    def forbidden_normalizer(_raw: bytes) -> HistoricalImportVerificationResult:
        nonlocal called
        called = True
        raise AssertionError("normalizer must not run for an invalid database path")

    monkeypatch.setattr(
        historical_cli,
        "verify_and_normalize_historical_import",
        forbidden_normalizer,
    )

    result = runner.invoke(
        app,
        [
            "import-historical-results",
            "--input",
            str(input_path),
            "--database",
            "relative.db",
        ],
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == "import-historical-results error: database path must be absolute\n"
    assert called is False


@pytest.mark.parametrize("kind", ["missing", "directory", "symlink"])
def test_non_regular_or_symlink_input_is_rejected(
    kind: str, tmp_path: Path
) -> None:
    input_path = _task_input(tmp_path)
    if kind == "missing":
        input_path.unlink()
    elif kind == "directory":
        input_path.unlink()
        input_path.mkdir()
    else:
        target = input_path.with_name("symlink-target.json")
        input_path.rename(target)
        input_path.symlink_to(target)

    result = runner.invoke(app, _args(input_path, _task_database(tmp_path)))

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "import-historical-results error:" in result.stderr
    assert "Traceback" not in result.stderr


def test_input_inside_git_worktree_is_rejected_without_reading_it(tmp_path: Path) -> None:
    result = runner.invoke(app, _args(REPO_ROOT / "README.md", _task_database(tmp_path)))

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == "import-historical-results error: input path is protected\n"


def test_validation_failure_returns_closed_json_before_repository_composition(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    input_path = _task_input(tmp_path, b"{not valid json")

    def forbidden_repository(_database: Path) -> object:
        raise AssertionError("repository must not be composed for a rejected envelope")

    monkeypatch.setattr(historical_cli, "SQLiteHistoricalResultRepository", forbidden_repository)

    result = runner.invoke(app, _args(input_path, _task_database(tmp_path)))

    assert result.exit_code == 1
    assert result.stderr == ""
    assert json.loads(result.stdout) == {
        "reason_code": "IMPORT_INPUT_UNVERIFIED",
        "status": "IMPORT_INPUT_UNVERIFIED",
    }


def test_normalizer_use_case_and_repository_are_each_called_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    raw = envelope_bytes(build_small_envelope())
    input_path = _task_input(tmp_path, raw)
    database = _task_database(tmp_path)
    normalizer_calls: list[bytes] = []
    repository_paths: list[Path] = []
    use_case_inputs: list[HistoricalRunImport] = []
    real_normalizer = historical_cli.verify_and_normalize_historical_import

    def counting_normalizer(candidate: bytes) -> HistoricalImportVerificationResult:
        normalizer_calls.append(candidate)
        return real_normalizer(candidate)

    class Repository:
        pass

    repository = Repository()

    def repository_factory(path: Path) -> Repository:
        repository_paths.append(path)
        return repository

    class UseCase:
        def __init__(self, candidate_repository: object) -> None:
            assert candidate_repository is repository

        def __call__(self, run_import: HistoricalRunImport) -> HistoricalImportCommitResult:
            use_case_inputs.append(run_import)
            return _fixed_commit()

    monkeypatch.setattr(
        historical_cli,
        "verify_and_normalize_historical_import",
        counting_normalizer,
    )
    monkeypatch.setattr(historical_cli, "SQLiteHistoricalResultRepository", repository_factory)
    monkeypatch.setattr(historical_cli, "ImportHistoricalResults", UseCase)

    result = runner.invoke(app, _args(input_path, database))

    assert result.exit_code == 0
    assert result.stderr == ""
    assert normalizer_calls == [raw]
    assert repository_paths == [database]
    assert len(use_case_inputs) == 1


def test_success_output_is_compact_sorted_deterministic_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    raw = envelope_bytes(build_small_envelope())
    input_path = _task_input(tmp_path, raw)
    database = _task_database(tmp_path)
    verification = historical_cli.verify_and_normalize_historical_import(raw)
    assert verification.normalized_import is not None

    class Repository:
        def commit_import(
            self, _run_import: HistoricalRunImport
        ) -> HistoricalImportCommitResult:
            return _fixed_commit()

    def repository_factory(_database: Path) -> Repository:
        return Repository()

    monkeypatch.setattr(
        historical_cli,
        "SQLiteHistoricalResultRepository",
        repository_factory,
    )

    first = runner.invoke(app, _args(input_path, database))
    second = runner.invoke(app, _args(input_path, database))

    expected: dict[str, Any] = {
        "completed_at": "2026-07-26T00:00:00.000000Z",
        "import_identity_sha256": "a" * 64,
        "is_idempotent_replay": False,
        "manifest_sha256": "b" * 64,
        "reason_code": None,
        "run_id": "fixed-run",
        "status": "COMPLETED",
    }
    expected_text = json.dumps(expected, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    assert first.exit_code == 0
    assert second.exit_code == 0
    assert first.stdout == f"{expected_text}\n"
    assert second.stdout == first.stdout
    assert first.stderr == second.stderr == ""


def test_missing_database_option_never_falls_back_to_environment(
    tmp_path: Path,
) -> None:
    input_path = _task_input(tmp_path)

    result = runner.invoke(
        app,
        ["import-historical-results", "--input", str(input_path)],
        env={
            "LOTTOLAB_DATA_DIR": str(_task_database(tmp_path).parent),
            "LOTTOLAB_HISTORICAL_RESULTS_DB": str(_task_database(tmp_path)),
        },
    )

    assert result.exit_code != 0
    assert result.stdout == ""
    assert "Usage:" in result.stderr


@pytest.mark.parametrize("failure_layer", ["normalizer", "repository"])
def test_unexpected_errors_are_sanitized(
    failure_layer: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    raw = envelope_bytes(build_small_envelope())
    input_path = _task_input(tmp_path, raw)

    if failure_layer == "normalizer":

        def explode_normalizer(_raw: bytes) -> HistoricalImportVerificationResult:
            raise RuntimeError("SELECT secret FROM /private/user/database")

        monkeypatch.setattr(
            historical_cli,
            "verify_and_normalize_historical_import",
            explode_normalizer,
        )
    else:

        def explode_repository(_database: Path) -> object:
            raise RuntimeError("sqlite3 failed at /private/user/database")

        monkeypatch.setattr(
            historical_cli,
            "SQLiteHistoricalResultRepository",
            explode_repository,
        )

    result = runner.invoke(app, _args(input_path, _task_database(tmp_path)))

    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == "import-historical-results error: request failed safely\n"
    assert "SELECT" not in result.stderr
    assert "sqlite3" not in result.stderr
    assert "/private" not in result.stderr
    assert "Traceback" not in result.stderr
