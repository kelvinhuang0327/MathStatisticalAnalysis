"""Real-SQLite integration coverage for the complete Replay artifact chain.

The committed synthetic Replay fixture is imported through the canonical draw
repository into a pytest-owned database.  The test then composes the production
SQLite reader, causal-history use case, strategy registry/adapters, Replay use
case, and canonical artifact serializer without introducing a second storage or
prediction path.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, cast

from lottolab.application.use_cases.build_causal_history import (
    BuildCausalHistory,
    BuildCausalHistoryInput,
    BuildCausalHistoryReason,
    BuildCausalHistoryStatus,
)
from lottolab.application.use_cases.generate_bet import (
    GenerateOneBetStatus,
    build_production_generate_one_bet,
)
from lottolab.application.use_cases.replay_historical_predictions import (
    ReplayHistoricalPredictions,
    ReplayHistoricalPredictionsInput,
    ReplayHistoricalPredictionsResult,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_predictions import ReplayTarget
from lottolab.evidence.replay_artifact import (
    ReplayArtifact,
    build_replay_artifact,
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
from lottolab.strategies.catalog import production_catalog

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "replay" / "synthetic_biglotto_causal_history.json"
)

_HEADER = "lottery_type,draw_number,draw_date,main_numbers,special_numbers,source"
_DATASET_ID = "SYNTHETIC_BIG_LOTTO_REPLAY_SQLITE_R1"
_DATASET_VERSION = "1"
_TARGET = ReplayTarget(draw_number="1000106", draw_date=date(2020, 4, 16))
_EXPECTED_HISTORY_COUNT = 106
_FUTURE_DRAW_NUMBERS = frozenset({"1000107", "1000108", "1000109"})
_STRATEGY_IDS = (
    "biglotto_social_wisdom_anti_popularity",
    "biglotto_zone_split_3bet_bet1",
    "biglotto_deviation_2bet",
)
_TABLES = ("draws", "schema_migrations", "ingestion_runs", "ingestion_items")


def _task_paths(tmp_path: Path) -> LocalDataPaths:
    return resolve_local_data_paths(
        environ={DATA_DIRECTORY_ENV: str(tmp_path / "real-sqlite-replay")}
    )


def _fixture_rows() -> list[dict[str, Any]]:
    fixture: dict[str, Any] = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return cast("list[dict[str, Any]]", fixture["history_rows"])


def _seed_canonical_draws(paths: LocalDataPaths) -> None:
    rows = [
        ",".join(
            (
                LotteryType.BIG_LOTTO.value,
                row["draw_number"],
                row["draw_date"],
                "|".join(str(number) for number in row["main_numbers"]),
                str(row["special_number"]),
                "synthetic-replay-sqlite",
            )
        )
        for row in _fixture_rows()
    ]
    document = parse_draw_csv(
        "\n".join((_HEADER, *rows, "")),
        filename="synthetic-replay-sqlite.csv",
    )
    assert document.is_valid, document.errors

    result = SQLiteDrawDataRepository(paths).apply_valid_import(document)

    assert result.inserted_count == len(rows) == 110
    assert result.skipped_count == result.conflict_count == result.failed_count == 0


def _table_snapshot(paths: LocalDataPaths) -> dict[str, tuple[tuple[object, ...], ...]]:
    with open_database(paths, read_only=True) as connection:
        return {
            table: tuple(
                tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY rowid")
            )
            for table in _TABLES
        }


def _assert_tables_unchanged(
    before: dict[str, tuple[tuple[object, ...], ...]],
    after: dict[str, tuple[tuple[object, ...], ...]],
) -> None:
    for table in _TABLES:
        assert after[table] == before[table], table


def _compose_real_replay(
    paths: LocalDataPaths,
) -> tuple[BuildCausalHistory, ReplayHistoricalPredictions]:
    build_causal_history = BuildCausalHistory(lambda: SQLiteDrawHistoryReader(paths))
    catalog = production_catalog()
    replay = ReplayHistoricalPredictions(
        build_causal_history,
        build_production_generate_one_bet(),
        catalog,
    )
    return build_causal_history, replay


def _execute_replay(
    replay: ReplayHistoricalPredictions,
    *,
    target: ReplayTarget = _TARGET,
    strategy_ids: tuple[str, ...] = _STRATEGY_IDS,
) -> ReplayHistoricalPredictionsResult:
    return replay.execute(
        ReplayHistoricalPredictionsInput(
            lottery_type=LotteryType.BIG_LOTTO,
            dataset_id=_DATASET_ID,
            dataset_version=_DATASET_VERSION,
            targets=(target,),
            strategy_ids=strategy_ids,
        )
    )


def _change_only_stored_special_number(paths: LocalDataPaths) -> None:
    with open_database(paths) as connection:
        before = connection.execute(
            """
            SELECT special_numbers_json FROM draws
            WHERE lottery_type = ? AND draw_number = ?
            """,
            (LotteryType.BIG_LOTTO.value, "1000000"),
        ).fetchone()
        assert before == ("[44]",)

        connection.execute("BEGIN IMMEDIATE")
        cursor = connection.execute(
            """
            UPDATE draws SET special_numbers_json = ?
            WHERE lottery_type = ? AND draw_number = ?
            """,
            ("[43]", LotteryType.BIG_LOTTO.value, "1000000"),
        )
        connection.commit()
        assert cursor.rowcount == 1


def test_real_sqlite_replay_builds_and_verifies_canonical_artifact(tmp_path: Path) -> None:
    paths = _task_paths(tmp_path)
    _seed_canonical_draws(paths)
    assert paths.database.resolve().is_relative_to(tmp_path.resolve())
    assert not paths.database.resolve().is_relative_to(REPO_ROOT.resolve())

    build_causal_history, replay = _compose_real_replay(paths)
    history_result = build_causal_history.execute(
        BuildCausalHistoryInput(
            lottery_type=LotteryType.BIG_LOTTO,
            target_draw_number=_TARGET.draw_number,
        )
    )
    assert history_result.status is BuildCausalHistoryStatus.OK
    assert history_result.reason_code is None
    assert history_result.history is not None
    history = history_result.history
    history_draw_numbers = {row.draw_number for row in history}
    assert len(history) == history_result.available_history_count == _EXPECTED_HISTORY_COUNT
    assert _TARGET.draw_number not in history_draw_numbers
    assert history_draw_numbers.isdisjoint(_FUTURE_DRAW_NUMBERS)

    before_replay = _table_snapshot(paths)
    result = _execute_replay(replay)
    after_replay = _table_snapshot(paths)
    _assert_tables_unchanged(before_replay, after_replay)

    assert len(result.snapshots) == len(_STRATEGY_IDS)
    assert tuple(
        (snapshot.target_draw_number, snapshot.strategy_id) for snapshot in result.snapshots
    ) == tuple((_TARGET.draw_number, strategy_id) for strategy_id in _STRATEGY_IDS)
    expected_history_sha256 = causal_history_sha256(history)
    expected_cutoff_row = history[-1]
    for snapshot in result.snapshots:
        assert snapshot.history_status == BuildCausalHistoryStatus.OK.value
        assert snapshot.causal_history_count == _EXPECTED_HISTORY_COUNT
        assert snapshot.causal_history_sha256 == expected_history_sha256
        assert snapshot.causal_history_sha256 is not None
        assert len(snapshot.causal_history_sha256) == 64
        assert snapshot.cutoff_draw_number == expected_cutoff_row.draw_number
        assert snapshot.cutoff_draw_date == expected_cutoff_row.draw_date
        assert snapshot.cutoff_draw_number != _TARGET.draw_number
        assert snapshot.prediction_status == GenerateOneBetStatus.OK.value
        assert snapshot.predicted_main_numbers is not None
        assert len(snapshot.predicted_main_numbers) == 6

    artifact = build_replay_artifact(
        dataset_id=_DATASET_ID,
        dataset_version=_DATASET_VERSION,
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_ids=_STRATEGY_IDS,
        targets=(_TARGET,),
        snapshots=result.snapshots,
    )
    first_bytes = serialize_replay_artifact(artifact)
    second_bytes = serialize_replay_artifact(artifact)
    assert first_bytes == second_bytes

    artifact_path = tmp_path / "replay-artifact.json"
    artifact_path.write_bytes(first_bytes)
    assert artifact_path.resolve().is_relative_to(tmp_path.resolve())
    assert not artifact_path.resolve().is_relative_to(REPO_ROOT.resolve())
    restored = deserialize_replay_artifact(artifact_path.read_bytes())
    assert isinstance(restored, ReplayArtifact)
    assert restored == artifact
    assert recompute_artifact_payload_sha256(restored) == restored.payload_sha256

    _change_only_stored_special_number(paths)
    after_special_change = _table_snapshot(paths)
    assert after_special_change.keys() == before_replay.keys()
    for table in _TABLES[1:]:
        assert after_special_change[table] == before_replay[table]
    changed_draw_rows = [
        (before, after)
        for before, after in zip(
            before_replay["draws"], after_special_change["draws"], strict=True
        )
        if before != after
    ]
    assert len(changed_draw_rows) == 1
    before_draw, after_draw = changed_draw_rows[0]
    assert before_draw[:5] == after_draw[:5]
    assert before_draw[5] == "[44]"
    assert after_draw[5] == "[43]"
    assert before_draw[6:] == after_draw[6:]

    changed_result = _execute_replay(replay)
    _assert_tables_unchanged(after_special_change, _table_snapshot(paths))
    for original, changed in zip(result.snapshots, changed_result.snapshots, strict=True):
        assert changed.causal_history_sha256 is not None
        assert changed.causal_history_sha256 != original.causal_history_sha256


def test_real_sqlite_missing_target_closes_without_infrastructure_exception(
    tmp_path: Path,
) -> None:
    paths = _task_paths(tmp_path)
    _seed_canonical_draws(paths)
    build_causal_history, replay = _compose_real_replay(paths)
    missing_target = ReplayTarget(draw_number="absent", draw_date=date(2021, 1, 1))
    history_result = build_causal_history.execute(
        BuildCausalHistoryInput(
            lottery_type=LotteryType.BIG_LOTTO,
            target_draw_number=missing_target.draw_number,
        )
    )
    assert history_result.status is BuildCausalHistoryStatus.TARGET_NOT_FOUND
    assert history_result.reason_code is BuildCausalHistoryReason.TARGET_DRAW_NOT_FOUND
    assert history_result.history is None
    assert history_result.available_history_count is None
    before_replay = _table_snapshot(paths)

    result = _execute_replay(
        replay,
        target=missing_target,
        strategy_ids=(_STRATEGY_IDS[0],),
    )

    _assert_tables_unchanged(before_replay, _table_snapshot(paths))
    assert len(result.snapshots) == 1
    snapshot = result.snapshots[0]
    assert snapshot.target_draw_number == missing_target.draw_number
    assert snapshot.strategy_id == _STRATEGY_IDS[0]
    assert snapshot.history_status == BuildCausalHistoryStatus.TARGET_NOT_FOUND.value
    assert snapshot.history_reason_code == BuildCausalHistoryReason.TARGET_DRAW_NOT_FOUND.value
    assert snapshot.causal_history_count is None
    assert snapshot.causal_history_sha256 is None
    assert snapshot.cutoff_draw_number is None
    assert snapshot.cutoff_draw_date is None
    assert snapshot.prediction_status is None
    assert snapshot.prediction_reason_code is None
    assert snapshot.predicted_main_numbers is None
