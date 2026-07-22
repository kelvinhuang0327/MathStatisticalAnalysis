"""Real-SQLite evidence for the read-only Replay predictions CLI."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

from typer.testing import CliRunner, Result

from lottolab.application.draw_data import DrawHistoryQuery
from lottolab.domain.draws import LotteryType
from lottolab.evidence.replay_artifact import (
    causal_history_sha256,
    deserialize_replay_artifact,
    recompute_artifact_payload_sha256,
    serialize_replay_artifact,
)
from lottolab.infrastructure.imports.csv_draws import parse_draw_csv
from lottolab.infrastructure.persistence.draw_schema import (
    DATA_DIRECTORY_ENV,
    LocalDataPaths,
    open_database,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.replay_history_reader import SQLiteDrawHistoryReader
from lottolab.infrastructure.persistence.repositories import SQLiteDrawDataRepository
from lottolab.interfaces.cli.main import app

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "replay" / "synthetic_biglotto_causal_history.json"
)
_HEADER = "lottery_type,draw_number,draw_date,main_numbers,special_numbers,source"
_DATASET_ARGS = ("--dataset-id", "CLI_REPLAY_R1", "--dataset-version", "1")
_SOCIAL = "biglotto_social_wisdom_anti_popularity"
_ZONE = "biglotto_zone_split_3bet_bet1"
_SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")

runner = CliRunner()


def _paths(tmp_path: Path) -> LocalDataPaths:
    return resolve_local_data_paths(
        environ={DATA_DIRECTORY_ENV: str(tmp_path / "replay-cli-data")}
    )


def _fixture_rows() -> list[dict[str, Any]]:
    fixture = cast("dict[str, Any]", json.loads(FIXTURE_PATH.read_text(encoding="utf-8")))
    return cast("list[dict[str, Any]]", fixture["history_rows"])


def _seed(paths: LocalDataPaths) -> None:
    rows = [
        ",".join(
            (
                LotteryType.BIG_LOTTO.value,
                cast(str, row["draw_number"]),
                cast(str, row["draw_date"]),
                "|".join(str(number) for number in cast("list[int]", row["main_numbers"])),
                str(row["special_number"]),
                "replay-cli-test",
            )
        )
        for row in _fixture_rows()
    ]
    document = parse_draw_csv(
        "\n".join((_HEADER, *rows, "")),
        filename="replay-cli-test.csv",
    )
    assert document.is_valid, document.errors
    result = SQLiteDrawDataRepository(paths).apply_valid_import(document)
    assert result.inserted_count == len(rows) == 110


def _invoke(paths: LocalDataPaths, *args: str) -> Result:
    return runner.invoke(
        app,
        ["replay-predictions", *_DATASET_ARGS, *args],
        env={DATA_DIRECTORY_ENV: str(paths.data_directory)},
    )


def _sidecars(paths: LocalDataPaths) -> tuple[Path, ...]:
    return tuple(Path(f"{paths.database}{suffix}") for suffix in _SIDECAR_SUFFIXES)


def _database_state(paths: LocalDataPaths) -> dict[str, object]:
    with open_database(paths, read_only=True) as connection:
        tables = tuple(
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        )
        row_counts = tuple(
            (table, connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in tables
        )
        schema_metadata = tuple(
            tuple(row)
            for row in connection.execute(
                "SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name"
            )
        )
        schema_version = connection.execute("PRAGMA schema_version").fetchone()
    page = SQLiteDrawDataRepository(paths).list_draws(DrawHistoryQuery(page_size=1_000))
    return {
        "tables": tables,
        "row_counts": row_counts,
        "schema_metadata": schema_metadata,
        "schema_version": schema_version,
        "application_records": page.records,
        "database_sha256": hashlib.sha256(paths.database.read_bytes()).hexdigest(),
        "database_size": paths.database.stat().st_size,
        "sidecars": tuple(path.name for path in _sidecars(paths) if path.exists()),
    }


def test_cli_emits_only_a_deterministic_canonical_artifact_and_never_mutates_sqlite(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    _seed(paths)
    assert paths.database.resolve().is_relative_to(tmp_path.resolve())
    assert not paths.database.resolve().is_relative_to(REPO_ROOT.resolve())
    before = _database_state(paths)

    result = _invoke(
        paths,
        "--target-draw",
        "1000106",
        "--strategy-id",
        _SOCIAL,
    )

    assert result.exit_code == 0, result.stderr
    assert result.stderr == ""
    artifact = deserialize_replay_artifact(result.stdout.encode("utf-8"))
    assert result.stdout == serialize_replay_artifact(artifact).decode("utf-8") + "\n"
    assert recompute_artifact_payload_sha256(artifact) == artifact.payload_sha256
    assert artifact.lottery_type is LotteryType.BIG_LOTTO
    assert artifact.strategy_ids == (_SOCIAL,)
    assert tuple(target.draw_number for target in artifact.targets) == ("1000106",)
    stored_target = SQLiteDrawDataRepository(paths).get_draw(
        LotteryType.BIG_LOTTO, "1000106"
    )
    assert stored_target is not None
    assert artifact.targets[0].draw_date == stored_target.draw_date

    history = SQLiteDrawHistoryReader(paths).read_causal_history(
        LotteryType.BIG_LOTTO, "1000106"
    )
    snapshot = artifact.snapshots[0]
    assert snapshot.target_draw_number == "1000106"
    assert snapshot.target_draw_date == stored_target.draw_date
    assert snapshot.causal_history_count == len(history) == 106
    assert snapshot.causal_history_sha256 == causal_history_sha256(history)
    assert history[-1].draw_number == snapshot.cutoff_draw_number == "1000105"
    assert "1000106" not in {row.draw_number for row in history}
    assert {"1000107", "1000108", "1000109"}.isdisjoint(
        row.draw_number for row in history
    )
    assert history[0].special_number == 44
    assert snapshot.predicted_main_numbers is not None
    assert len(snapshot.predicted_main_numbers) == 6

    repeated = _invoke(
        paths,
        "--target-draw",
        "1000106",
        "--strategy-id",
        _SOCIAL,
    )
    assert repeated.exit_code == 0
    assert repeated.stdout == result.stdout
    assert _database_state(paths) == before
    assert not any(path.exists() for path in _sidecars(paths))


def test_cli_preserves_caller_target_and_strategy_order_and_stored_target_dates(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    _seed(paths)
    before = _database_state(paths)

    result = _invoke(
        paths,
        "--target-draw",
        "1000106",
        "--target-draw",
        "1000104",
        "--strategy-id",
        _ZONE,
        "--strategy-id",
        _SOCIAL,
    )

    assert result.exit_code == 0, result.stderr
    artifact = deserialize_replay_artifact(result.stdout.encode("utf-8"))
    assert tuple(target.draw_number for target in artifact.targets) == ("1000106", "1000104")
    assert artifact.strategy_ids == (_ZONE, _SOCIAL)
    assert tuple(
        (snapshot.target_draw_number, snapshot.strategy_id)
        for snapshot in artifact.snapshots
    ) == (
        ("1000106", _ZONE),
        ("1000106", _SOCIAL),
        ("1000104", _ZONE),
        ("1000104", _SOCIAL),
    )
    repository = SQLiteDrawDataRepository(paths)
    for target in artifact.targets:
        stored = repository.get_draw(LotteryType.BIG_LOTTO, target.draw_number)
        assert stored is not None
        assert target.draw_date == stored.draw_date
    assert _database_state(paths) == before


def test_cli_applies_minimum_and_maximum_history_bounds(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _seed(paths)
    before = _database_state(paths)

    bounded = _invoke(
        paths,
        "--target-draw",
        "1000106",
        "--strategy-id",
        _SOCIAL,
        "--maximum-history-draws",
        "5",
        "--minimum-history-draws",
        "5",
    )
    assert bounded.exit_code == 0, bounded.stderr
    bounded_artifact = deserialize_replay_artifact(bounded.stdout.encode("utf-8"))
    assert bounded_artifact.snapshots[0].causal_history_count == 5
    assert bounded_artifact.snapshots[0].cutoff_draw_number == "1000105"

    insufficient = _invoke(
        paths,
        "--target-draw",
        "1000106",
        "--strategy-id",
        _SOCIAL,
        "--minimum-history-draws",
        "107",
    )
    assert insufficient.exit_code == 0, insufficient.stderr
    insufficient_artifact = deserialize_replay_artifact(
        insufficient.stdout.encode("utf-8")
    )
    snapshot = insufficient_artifact.snapshots[0]
    assert snapshot.history_status == "INSUFFICIENT_HISTORY"
    assert snapshot.history_reason_code == "AVAILABLE_HISTORY_BELOW_MINIMUM"
    assert snapshot.prediction_status is None
    assert _database_state(paths) == before


def test_missing_database_and_missing_target_fail_closed_without_side_effects(
    tmp_path: Path,
) -> None:
    missing_paths = _paths(tmp_path / "missing")

    missing_database = _invoke(
        missing_paths,
        "--target-draw",
        "1000106",
        "--strategy-id",
        _SOCIAL,
    )

    assert missing_database.exit_code == 1
    assert missing_database.stdout == ""
    assert missing_database.stderr == (
        "replay-predictions error: local draw database is unavailable\n"
    )
    assert not missing_paths.data_directory.exists()

    paths = _paths(tmp_path)
    _seed(paths)
    before = _database_state(paths)
    missing_target = _invoke(
        paths,
        "--target-draw",
        "9999999",
        "--strategy-id",
        _SOCIAL,
    )
    assert missing_target.exit_code == 1
    assert missing_target.stdout == ""
    assert missing_target.stderr == (
        "replay-predictions error: target draw was not found: 9999999\n"
    )
    assert "Traceback" not in missing_target.stderr
    assert str(paths.database) not in missing_target.stderr
    assert _database_state(paths) == before
    assert not any(path.exists() for path in _sidecars(paths))
