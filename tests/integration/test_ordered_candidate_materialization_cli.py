"""End-to-end temporary-DB CLI materialization without external effects."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from typer.testing import CliRunner

from lottolab.domain.draws import LotteryType
from lottolab.infrastructure.imports.csv_draws import parse_draw_csv
from lottolab.infrastructure.persistence.draw_schema import (
    DATA_DIRECTORY_ENV,
    LocalDataPaths,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.ordered_candidate_materialization_reader import (
    SQLiteOrderedCandidateMaterializationReader,
)
from lottolab.infrastructure.persistence.repositories import SQLiteDrawDataRepository
from lottolab.interfaces.cli.main import app

runner = CliRunner()
_HEADER = "lottery_type,draw_number,draw_date,main_numbers,special_numbers,source"
_STRATEGY = "biglotto_social_wisdom_anti_popularity"


def _paths(tmp_path: Path) -> LocalDataPaths:
    return resolve_local_data_paths(
        environ={DATA_DIRECTORY_ENV: str(tmp_path / "p336-cli-data")}
    )


def _seed(paths: LocalDataPaths) -> None:
    parsed = parse_draw_csv(
        "\n".join(
            (
                _HEADER,
                "BIG_LOTTO,1,2026-01-01,1|2|3|4|5|6,7,fixture",
                "BIG_LOTTO,2,2026-01-02,2|3|4|5|6|7,8,fixture",
                "BIG_LOTTO,3,2026-01-03,3|4|5|6|7|8,9,fixture",
                "",
            )
        ),
        filename="fixture.csv",
    )
    assert parsed.is_valid, parsed.errors
    SQLiteDrawDataRepository(paths).apply_valid_import(parsed)


def test_cli_seals_package_returns_only_summary_and_preserves_db_bytes(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    _seed(paths)
    snapshot = SQLiteOrderedCandidateMaterializationReader(
        paths
    ).read_source_snapshot(LotteryType.BIG_LOTTO)
    db_before = paths.database.read_bytes()
    resolved_tmp = tmp_path.resolve()
    parent = resolved_tmp / "owner-output"
    parent.mkdir(mode=0o700)
    parent.chmod(0o700)
    output = parent / "sealed-package"

    result = runner.invoke(
        app,
        [
            "materialize-ordered-candidate-emissions",
            "--lottery-type",
            "BIG_LOTTO",
            "--dataset-id",
            "dataset",
            "--dataset-version",
            "v1",
            "--source-snapshot-sha256",
            snapshot.source_snapshot_sha256,
            "--target-draw",
            "3",
            "--strategy-id",
            _STRATEGY,
            "--minimum-history-draws",
            "1",
            "--maximum-history-draws",
            "2",
            "--replicate",
            "1",
            "--output-directory",
            str(output),
        ],
        env={DATA_DIRECTORY_ENV: str(paths.data_directory)},
    )

    assert result.exit_code == 0, result.stderr
    assert result.stderr == ""
    summary = json.loads(result.stdout)
    assert summary == {
        "attempt_count": 1,
        "ok_attempt_count": 1,
        "output_directory": str(output),
        "source_snapshot_sha256": snapshot.source_snapshot_sha256,
        "status_counts": {
            "INSUFFICIENT_HISTORY": 0,
            "INVALID_OUTPUT": 0,
            "OK": 1,
            "REJECTED": 0,
            "REPLAY_ERROR": 0,
            "STORAGE_ERROR": 0,
            "STRATEGY_UNAVAILABLE": 0,
            "TARGET_NOT_FOUND": 0,
        },
    }
    assert "attempts" not in summary
    assert (output / "manifest.json").is_file()
    assert (output / "SHA256SUMS").is_file()
    emissions = list((output / "emissions").rglob("replicate-000001.json"))
    assert len(emissions) == 1
    assert paths.database.read_bytes() == db_before
    assert hashlib.sha256(paths.database.read_bytes()).hexdigest() == hashlib.sha256(
        db_before
    ).hexdigest()
    for suffix in ("-wal", "-shm", "-journal"):
        assert not Path(f"{paths.database}{suffix}").exists()
