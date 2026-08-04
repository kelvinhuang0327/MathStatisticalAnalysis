"""Explicit-path CLI integration for the BIG_LOTTO research-backtest runner."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

import pytest
from typer.testing import CliRunner

from lottolab.application.research_backtest_runner import (
    BIG_LOTTO_RESEARCH_BACKTEST_RUN_MANIFEST_V1,
    BigLottoResearchBacktestManifest,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.research import ResearchRunKind
from lottolab.infrastructure.imports.csv_draws import parse_draw_csv
from lottolab.infrastructure.persistence import research_repository as research_repository_module
from lottolab.infrastructure.persistence.draw_schema import (
    DATA_DIRECTORY_ENV,
    LocalDataPaths,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.ordered_candidate_materialization_reader import (
    SQLiteOrderedCandidateMaterializationReader,
)
from lottolab.infrastructure.persistence.repositories import (
    SQLiteDrawDataRepository,
)
from lottolab.infrastructure.persistence.research_schema import (
    DATA_DIRECTORY_ENV as RESEARCH_DATA_DIRECTORY_ENV,
)
from lottolab.infrastructure.persistence.research_schema import (
    RESEARCH_DATABASE_FILENAME,
    ResearchDataPaths,
    initialize_schema,
)
from lottolab.interfaces.cli import research_backtest_runner as cli_module
from lottolab.interfaces.cli.main import app

runner = CliRunner()
_COMMIT = "d" * 40
_STRATEGY = "biglotto_social_wisdom_anti_popularity"
_HEADER = "lottery_type,draw_number,draw_date,main_numbers,special_numbers,source"


def _fixed_source_commit(_root: Path) -> str:
    return _COMMIT


def _raise_unexpected_source_failure(_root: Path) -> str:
    raise RuntimeError("secret-path")


def _draw_paths(tmp_path: Path) -> LocalDataPaths:
    return resolve_local_data_paths(
        environ={DATA_DIRECTORY_ENV: str(tmp_path / "draw-data")}
    )


def _seed(paths: LocalDataPaths, count: int = 5) -> None:
    rows = [_HEADER]
    for index in range(1, count + 1):
        main = "|".join(str(number) for number in range(index, index + 6))
        rows.append(
            f"BIG_LOTTO,{index},2026-02-{index:02d},{main},{index + 6},fixture"
        )
    rows.append("")
    parsed = parse_draw_csv("\n".join(rows), filename="cli-runner-fixture.csv")
    assert parsed.is_valid, parsed.errors
    SQLiteDrawDataRepository(paths).apply_valid_import(parsed)


def _manifest(
    draw_paths: LocalDataPaths,
    *,
    targets: tuple[str, ...],
    minimum: int = 2,
) -> BigLottoResearchBacktestManifest:
    snapshot = SQLiteOrderedCandidateMaterializationReader(
        draw_paths
    ).read_source_snapshot(LotteryType.BIG_LOTTO)
    return BigLottoResearchBacktestManifest(
        schema_version=BIG_LOTTO_RESEARCH_BACKTEST_RUN_MANIFEST_V1,
        lottery_type=LotteryType.BIG_LOTTO,
        run_kind=ResearchRunKind.HISTORICAL_BACKTEST,
        dataset_id="cli-fixture",
        dataset_version="v1",
        expected_source_snapshot_sha256=snapshot.source_snapshot_sha256,
        target_draws=targets,
        strategy_ids=(_STRATEGY,),
        minimum_history_draws=minimum,
        maximum_history_draws=4,
        replicate=1,
    )


def _write_manifest(
    tmp_path: Path,
    manifest: BigLottoResearchBacktestManifest,
    name: str = "manifest.json",
) -> Path:
    path = tmp_path / name
    path.write_bytes(manifest.canonical_file_bytes())
    return path


def _args(
    manifest_file: Path,
    draw_data_dir: Path,
    research_data_dir: Path,
) -> list[str]:
    return [
        "run-biglotto-research-backtest",
        "--manifest-file",
        str(manifest_file),
        "--draw-data-dir",
        str(draw_data_dir),
        "--research-data-dir",
        str(research_data_dir),
    ]


def _assert_no_sidecars(database: Path) -> None:
    for suffix in ("-wal", "-shm", "-journal"):
        assert not Path(f"{database}{suffix}").exists()


def _production_args(
    manifest_file: Path,
    draw_data_dir: Path,
    *,
    production: bool = False,
    research_data_dir: Path | None = None,
) -> list[str]:
    args = [
        "run-biglotto-research-backtest",
        "--manifest-file",
        str(manifest_file),
        "--draw-data-dir",
        str(draw_data_dir),
    ]
    if production:
        args.append("--production")
    if research_data_dir is not None:
        args += ["--research-data-dir", str(research_data_dir)]
    return args


def _seed_canonical_research_store(canonical_dir: Path) -> ResearchDataPaths:
    paths = ResearchDataPaths(
        canonical_dir,
        canonical_dir / RESEARCH_DATABASE_FILENAME,
    )
    initialize_schema(paths)
    return paths


class _FakeDiskUsage(NamedTuple):
    total: int
    used: int
    free: int


def _fake_disk_usage(free_bytes: int) -> Callable[[object], _FakeDiskUsage]:
    def _disk_usage(_path: object) -> _FakeDiskUsage:
        return _FakeDiskUsage(total=free_bytes + 1, used=1, free=free_bytes)

    return _disk_usage


def test_zero_history_cli_rejects_before_research_database_creation(
    tmp_path: Path,
) -> None:
    draw_paths = _draw_paths(tmp_path)
    _seed(draw_paths)
    research_dir = tmp_path / "research-data"
    research_dir.mkdir(mode=0o700)
    manifest_file = _write_manifest(
        tmp_path,
        _manifest(draw_paths, targets=("1",)),
    )
    draw_bytes = draw_paths.database.read_bytes()

    result = runner.invoke(
        app,
        _args(manifest_file, draw_paths.data_directory, research_dir),
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    error = json.loads(result.stderr)
    assert error == {
        "message": "target draw 1 has no strictly earlier source row",
        "reason_code": "TARGET_HAS_NO_STRICTLY_EARLIER_HISTORY",
        "status": "ERROR",
        "target_draw": "1",
    }
    research_database = research_dir / RESEARCH_DATABASE_FILENAME
    assert not research_database.exists()
    assert draw_paths.database.read_bytes() == draw_bytes
    _assert_no_sidecars(research_database)


def test_mixed_zero_history_cli_manifest_is_atomic_before_research_write(
    tmp_path: Path,
) -> None:
    draw_paths = _draw_paths(tmp_path)
    _seed(draw_paths)
    research_dir = tmp_path / "research-data"
    research_dir.mkdir(mode=0o700)
    manifest_file = _write_manifest(
        tmp_path,
        _manifest(draw_paths, targets=("2", "1")),
    )

    result = runner.invoke(
        app,
        _args(manifest_file, draw_paths.data_directory, research_dir),
    )

    assert result.exit_code == 1
    assert json.loads(result.stderr)["reason_code"] == (
        "TARGET_HAS_NO_STRICTLY_EARLIER_HISTORY"
    )
    assert not (research_dir / RESEARCH_DATABASE_FILENAME).exists()


def test_cli_uses_only_explicit_paths_and_completed_third_run_is_no_op(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cli_module,
        "resolve_repository_source_commit_oid",
        _fixed_source_commit,
    )
    draw_paths = _draw_paths(tmp_path)
    _seed(draw_paths)
    research_dir = tmp_path / "research-data"
    research_dir.mkdir(mode=0o700)
    ambient_dir = tmp_path / "ambient-must-remain-unused"
    ambient_dir.mkdir(mode=0o700)
    manifest_file = _write_manifest(
        tmp_path,
        _manifest(draw_paths, targets=("2", "3", "4")),
    )
    invocation = _args(
        manifest_file,
        draw_paths.data_directory,
        research_dir,
    )
    environment = {DATA_DIRECTORY_ENV: str(ambient_dir)}
    draw_database_before = draw_paths.database.read_bytes()

    first = runner.invoke(app, invocation, env=environment)

    assert first.exit_code == 0, first.stderr
    assert first.stderr == ""
    first_payload = json.loads(first.stdout)
    assert first_payload["status"] == "COMPLETED"
    assert first_payload["expected_target_count"] == 3
    assert first_payload["completed_target_count"] == 3
    assert first_payload["status_counts"]["INSUFFICIENT_HISTORY"] == 1
    assert first_payload["results_created"] >= 1
    research_database = research_dir / RESEARCH_DATABASE_FILENAME
    assert research_database.is_file()
    assert not (ambient_dir / RESEARCH_DATABASE_FILENAME).exists()
    assert draw_paths.database.read_bytes() == draw_database_before
    before = research_database.read_bytes()

    third = runner.invoke(app, invocation, env=environment)

    assert third.exit_code == 0, third.stderr
    assert third.stderr == ""
    third_payload = json.loads(third.stdout)
    assert third_payload["idempotent_no_op"] is True
    assert third_payload["targets_created"] == 0
    assert third_payload["tickets_created"] == 0
    assert third_payload["results_created"] == 0
    assert research_database.read_bytes() == before
    assert draw_paths.database.read_bytes() == draw_database_before
    assert not (ambient_dir / RESEARCH_DATABASE_FILENAME).exists()
    _assert_no_sidecars(research_database)


@pytest.mark.parametrize(
    "missing",
    ["manifest", "draw", "research"],
)
def test_missing_explicit_path_fails_before_database_creation(
    tmp_path: Path,
    missing: str,
) -> None:
    draw_paths = _draw_paths(tmp_path)
    _seed(draw_paths)
    research_dir = tmp_path / "research-data"
    research_dir.mkdir(mode=0o700)
    draw_directory = draw_paths.data_directory
    manifest_file = _write_manifest(
        tmp_path,
        _manifest(draw_paths, targets=("2",)),
    )
    if missing == "manifest":
        manifest_file = tmp_path / "missing-manifest.json"
    elif missing == "draw":
        draw_directory = tmp_path / "missing-draw-data"
    else:
        research_dir = tmp_path / "missing-research-data"

    result = runner.invoke(
        app,
        _args(manifest_file, draw_directory, research_dir),
    )

    assert result.exit_code == 1
    error = json.loads(result.stderr)
    assert error["reason_code"].endswith("_MISSING")
    assert not (research_dir / RESEARCH_DATABASE_FILENAME).exists()


def test_production_research_destination_is_rejected_without_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    draw_paths = _draw_paths(tmp_path)
    _seed(draw_paths)
    forbidden = tmp_path / "forbidden-production"
    forbidden.mkdir(mode=0o700)
    monkeypatch.setattr(
        cli_module,
        "_PRODUCTION_RESEARCH_DIRECTORY",
        forbidden,
    )
    manifest_file = _write_manifest(
        tmp_path,
        _manifest(draw_paths, targets=("2",)),
    )

    result = runner.invoke(
        app,
        _args(manifest_file, draw_paths.data_directory, forbidden),
    )

    assert result.exit_code == 1
    assert json.loads(result.stderr)["reason_code"] == (
        "PRODUCTION_RESEARCH_PATH_FORBIDDEN"
    )
    assert not (forbidden / RESEARCH_DATABASE_FILENAME).exists()


def test_production_research_destination_through_symlinked_parent_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    draw_paths = _draw_paths(tmp_path)
    _seed(draw_paths)
    forbidden = tmp_path / "forbidden-production"
    forbidden.mkdir(mode=0o700)
    alias_parent = tmp_path / "alias-parent"
    alias_parent.symlink_to(tmp_path, target_is_directory=True)
    aliased_forbidden = alias_parent / forbidden.name
    assert not aliased_forbidden.is_symlink()
    assert aliased_forbidden.resolve() == forbidden
    monkeypatch.setattr(
        cli_module,
        "_PRODUCTION_RESEARCH_DIRECTORY",
        forbidden,
    )
    manifest_file = _write_manifest(
        tmp_path,
        _manifest(draw_paths, targets=("2",)),
    )

    result = runner.invoke(
        app,
        _args(manifest_file, draw_paths.data_directory, aliased_forbidden),
    )

    assert result.exit_code == 1
    assert json.loads(result.stderr)["reason_code"] == (
        "PRODUCTION_RESEARCH_PATH_FORBIDDEN"
    )
    assert not (forbidden / RESEARCH_DATABASE_FILENAME).exists()


def test_unexpected_cli_failure_is_sanitized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cli_module,
        "resolve_repository_source_commit_oid",
        _raise_unexpected_source_failure,
    )
    draw_paths = _draw_paths(tmp_path)
    _seed(draw_paths)
    research_dir = tmp_path / "research-data"
    research_dir.mkdir(mode=0o700)
    manifest_file = _write_manifest(
        tmp_path,
        _manifest(draw_paths, targets=("2",)),
    )

    result = runner.invoke(
        app,
        _args(manifest_file, draw_paths.data_directory, research_dir),
    )

    assert result.exit_code == 1
    assert "secret-path" not in result.stderr
    assert json.loads(result.stderr) == {
        "message": "runner source commit could not be resolved",
        "reason_code": "RESEARCH_BACKTEST_FAILED",
        "status": "ERROR",
    }


def test_both_research_modes_selected_fails_before_database_access(
    tmp_path: Path,
) -> None:
    draw_paths = _draw_paths(tmp_path)
    _seed(draw_paths)
    research_dir = tmp_path / "research-data"
    research_dir.mkdir(mode=0o700)
    manifest_file = _write_manifest(
        tmp_path,
        _manifest(draw_paths, targets=("2",)),
    )

    result = runner.invoke(
        app,
        _production_args(
            manifest_file,
            draw_paths.data_directory,
            production=True,
            research_data_dir=research_dir,
        ),
    )

    assert result.exit_code == 1
    assert json.loads(result.stderr)["reason_code"] == "RESEARCH_MODE_AMBIGUOUS"
    assert not (research_dir / RESEARCH_DATABASE_FILENAME).exists()


def test_neither_research_mode_selected_fails_before_database_access(
    tmp_path: Path,
) -> None:
    draw_paths = _draw_paths(tmp_path)
    _seed(draw_paths)
    manifest_file = _write_manifest(
        tmp_path,
        _manifest(draw_paths, targets=("2",)),
    )

    result = runner.invoke(
        app,
        _production_args(manifest_file, draw_paths.data_directory),
    )

    assert result.exit_code == 1
    assert json.loads(result.stderr)["reason_code"] == "RESEARCH_MODE_REQUIRED"


def test_production_mode_success_uses_resolver_and_skips_initialize(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cli_module,
        "resolve_repository_source_commit_oid",
        _fixed_source_commit,
    )
    draw_paths = _draw_paths(tmp_path)
    _seed(draw_paths)
    canonical_dir = tmp_path / "canonical-research-store"
    canonical_paths = _seed_canonical_research_store(canonical_dir)
    manifest_file = _write_manifest(
        tmp_path,
        _manifest(draw_paths, targets=("2", "3", "4")),
    )
    monkeypatch.setattr(shutil, "disk_usage", _fake_disk_usage(100 * 1024**3))

    def _fail_if_initialized(_paths: ResearchDataPaths) -> None:
        raise AssertionError("production mode must not initialize the store")

    monkeypatch.setattr(
        research_repository_module, "initialize_schema", _fail_if_initialized
    )
    before = canonical_paths.database.read_bytes()

    result = runner.invoke(
        app,
        _production_args(manifest_file, draw_paths.data_directory, production=True),
        env={RESEARCH_DATA_DIRECTORY_ENV: str(canonical_dir)},
    )

    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "COMPLETED"
    assert canonical_paths.database.read_bytes() != before
    assert not (draw_paths.data_directory / RESEARCH_DATABASE_FILENAME).exists()
    _assert_no_sidecars(canonical_paths.database)


def test_production_missing_database_is_not_created(
    tmp_path: Path,
) -> None:
    draw_paths = _draw_paths(tmp_path)
    _seed(draw_paths)
    canonical_dir = tmp_path / "canonical-research-store"
    manifest_file = _write_manifest(
        tmp_path,
        _manifest(draw_paths, targets=("2",)),
    )

    result = runner.invoke(
        app,
        _production_args(manifest_file, draw_paths.data_directory, production=True),
        env={RESEARCH_DATA_DIRECTORY_ENV: str(canonical_dir)},
    )

    assert result.exit_code == 1
    assert json.loads(result.stderr)["reason_code"] == (
        "PRODUCTION_RESEARCH_DATABASE_MISSING"
    )
    assert not canonical_dir.exists()


def test_production_invalid_schema_fails_read_only(
    tmp_path: Path,
) -> None:
    draw_paths = _draw_paths(tmp_path)
    _seed(draw_paths)
    canonical_dir = tmp_path / "canonical-research-store"
    canonical_dir.mkdir(mode=0o700)
    database = canonical_dir / RESEARCH_DATABASE_FILENAME
    sqlite3.connect(str(database)).close()
    os.chmod(database, 0o600)
    manifest_file = _write_manifest(
        tmp_path,
        _manifest(draw_paths, targets=("2",)),
    )
    before = database.read_bytes()

    result = runner.invoke(
        app,
        _production_args(manifest_file, draw_paths.data_directory, production=True),
        env={RESEARCH_DATA_DIRECTORY_ENV: str(canonical_dir)},
    )

    assert result.exit_code == 1
    assert json.loads(result.stderr)["reason_code"] == "RESEARCH_BACKTEST_FAILED"
    assert database.read_bytes() == before


def test_production_low_disk_fails_before_repository_construction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    draw_paths = _draw_paths(tmp_path)
    _seed(draw_paths)
    canonical_dir = tmp_path / "canonical-research-store"
    canonical_paths = _seed_canonical_research_store(canonical_dir)
    manifest_file = _write_manifest(
        tmp_path,
        _manifest(draw_paths, targets=("2",)),
    )
    before = canonical_paths.database.read_bytes()
    monkeypatch.setattr(shutil, "disk_usage", _fake_disk_usage(1))

    def _fail_if_constructed(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("repository must not be constructed when disk is low")

    monkeypatch.setattr(cli_module, "SQLiteResearchRepository", _fail_if_constructed)

    result = runner.invoke(
        app,
        _production_args(manifest_file, draw_paths.data_directory, production=True),
        env={RESEARCH_DATA_DIRECTORY_ENV: str(canonical_dir)},
    )

    assert result.exit_code == 1
    error = json.loads(result.stderr)
    assert error["reason_code"] == "INSUFFICIENT_PRODUCTION_DISK_SPACE"
    assert str(canonical_dir) not in error["message"]
    assert "bytes" in error["message"]
    assert canonical_paths.database.read_bytes() == before


def test_production_mode_ignores_scratch_forbidden_directory_constant(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cli_module,
        "resolve_repository_source_commit_oid",
        _fixed_source_commit,
    )
    draw_paths = _draw_paths(tmp_path)
    _seed(draw_paths)
    canonical_dir = tmp_path / "canonical-research-store"
    canonical_paths = _seed_canonical_research_store(canonical_dir)
    decoy_directory = tmp_path / "decoy-scratch-forbidden-directory"
    monkeypatch.setattr(cli_module, "_PRODUCTION_RESEARCH_DIRECTORY", decoy_directory)
    manifest_file = _write_manifest(
        tmp_path,
        _manifest(draw_paths, targets=("2",)),
    )
    monkeypatch.setattr(shutil, "disk_usage", _fake_disk_usage(100 * 1024**3))
    before = canonical_paths.database.read_bytes()

    result = runner.invoke(
        app,
        _production_args(manifest_file, draw_paths.data_directory, production=True),
        env={RESEARCH_DATA_DIRECTORY_ENV: str(canonical_dir)},
    )

    assert result.exit_code == 0, result.stderr
    assert not decoy_directory.exists()
    assert canonical_paths.database.read_bytes() != before
