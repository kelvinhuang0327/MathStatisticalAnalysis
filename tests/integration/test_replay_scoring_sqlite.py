"""Real SQLite composition for the complete Replay scoring vertical slice."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from lottolab.application.use_cases.score_replay_artifact import ScoreReplayArtifact
from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import BigLottoPrizeTierId, NoPrizeResult
from lottolab.domain.replay_predictions import ReplayPredictionSnapshot, ReplayTarget
from lottolab.domain.replay_scoring import (
    ReplayScoringStatus,
    ReplayTargetOutcomeReadReason,
    ReplayTargetOutcomeReadStatus,
)
from lottolab.evidence.replay_artifact import (
    ReplayArtifact,
    build_replay_artifact,
    build_replay_prediction_snapshot,
    serialize_replay_artifact,
)
from lottolab.evidence.replay_scoring_artifact import (
    build_replay_scoring_artifact,
    deserialize_replay_scoring_artifact,
    recompute_scoring_artifact_payload_sha256,
    serialize_replay_scoring_artifact,
)
from lottolab.infrastructure.imports.csv_draws import parse_draw_csv
from lottolab.infrastructure.persistence.draw_schema import (
    DATA_DIRECTORY_ENV,
    LocalDataPaths,
    open_database,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.replay_target_outcome_reader import (
    SQLiteReplayTargetOutcomeReader,
)
from lottolab.infrastructure.persistence.repositories import SQLiteDrawDataRepository

REPO_ROOT = Path(__file__).resolve().parents[2]
_TABLES = ("draws", "schema_migrations", "ingestion_runs", "ingestion_items")
_HEADER = "lottery_type,draw_number,draw_date,main_numbers,special_numbers,source"


def _paths(tmp_path: Path) -> LocalDataPaths:
    return resolve_local_data_paths(
        environ={DATA_DIRECTORY_ENV: str(tmp_path / "replay-scoring-db")}
    )


def _seed_draws(paths: LocalDataPaths, *, include_leakage_bait: bool = True) -> None:
    required_rows = (
        "BIG_LOTTO,299,2026-01-01,20|21|22|23|24|25,26,synthetic",
        "BIG_LOTTO,300,2026-01-02,1|2|3|4|5|6,7,synthetic",
        "BIG_LOTTO,301,2026-01-03,10|11|12|13|14|15,16,synthetic",
    )
    leakage_bait = (
        "BIG_LOTTO,302,2026-01-04,30|31|32|33|34|35,36,synthetic",
        "BIG_LOTTO,303,2026-01-05,40|41|42|43|44|45,46,synthetic",
    )
    rows = (*required_rows, *leakage_bait) if include_leakage_bait else required_rows
    parsed = parse_draw_csv("\n".join((_HEADER, *rows, "")), filename="scoring.csv")
    assert parsed.is_valid, parsed.errors
    result = SQLiteDrawDataRepository(paths).apply_valid_import(parsed)
    assert result.inserted_count == len(rows)


def _table_snapshot(paths: LocalDataPaths) -> dict[str, tuple[tuple[object, ...], ...]]:
    with open_database(paths, read_only=True) as connection:
        return {
            table: tuple(
                tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY rowid")
            )
            for table in _TABLES
        }


def _source_artifact() -> ReplayArtifact:
    targets = (
        ReplayTarget("300", date(2026, 1, 2)),
        ReplayTarget("301", date(2026, 1, 3)),
    )
    strategy_ids = ("scored", "closed")
    snapshots: list[ReplayPredictionSnapshot] = []
    for target in targets:
        snapshots.append(
            build_replay_prediction_snapshot(
                dataset_id="sqlite-dataset",
                dataset_version="1",
                lottery_type=LotteryType.BIG_LOTTO,
                target=target,
                strategy_id="scored",
                strategy_identity=("scored", "Scored", "1.0.0"),
                history_status="OK",
                history_reason_code=None,
                causal_history=(),
                prediction_status="OK",
                prediction_reason_code=None,
                predicted_main_numbers=(1, 2, 3, 4, 5, 6),
            )
        )
        snapshots.append(
            build_replay_prediction_snapshot(
                dataset_id="sqlite-dataset",
                dataset_version="1",
                lottery_type=LotteryType.BIG_LOTTO,
                target=target,
                strategy_id="closed",
                strategy_identity=("closed", "Closed", "1.0.0"),
                history_status="OK",
                history_reason_code=None,
                causal_history=(),
                prediction_status="ADAPTER_UNAVAILABLE",
                prediction_reason_code="ADAPTER_UNAVAILABLE",
                predicted_main_numbers=None,
            )
        )
    return build_replay_artifact(
        dataset_id="sqlite-dataset",
        dataset_version="1",
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_ids=strategy_ids,
        targets=targets,
        snapshots=tuple(snapshots),
    )


def test_real_sqlite_scoring_is_exact_read_only_and_canonical(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _seed_draws(paths)
    assert paths.database.resolve().is_relative_to(tmp_path.resolve())
    assert not paths.database.resolve().is_relative_to(REPO_ROOT.resolve())
    source = _source_artifact()
    source_bytes_before = serialize_replay_artifact(source)
    source_hash_before = source.payload_sha256
    tables_before = _table_snapshot(paths)

    result = ScoreReplayArtifact(SQLiteReplayTargetOutcomeReader(paths)).execute(source)

    tables_after = _table_snapshot(paths)
    assert tables_after == tables_before
    records = result.scored_predictions
    assert len(records) == 4
    assert tuple((record.target_draw_number, record.strategy_id) for record in records) == (
        ("300", "scored"),
        ("300", "closed"),
        ("301", "scored"),
        ("301", "closed"),
    )
    assert records[0].target_draw_date == date(2026, 1, 2)
    assert records[0].main_number_hit_count == 6
    assert records[0].special_number_hit is False
    assert records[0].prize_tier_id is BigLottoPrizeTierId.FIRST
    assert records[1].scoring_status is ReplayScoringStatus.NOT_SCORED_PREDICTION_CLOSED
    assert records[2].target_draw_date == date(2026, 1, 3)
    assert records[2].main_number_hit_count == 0
    assert records[2].special_number_hit is False
    assert records[2].no_prize_result is NoPrizeResult.NO_PRIZE
    assert records[3].scoring_status is ReplayScoringStatus.NOT_SCORED_PREDICTION_CLOSED
    assert records[0].target_outcome_sha256 != records[2].target_outcome_sha256

    scoring_artifact = build_replay_scoring_artifact(
        source_artifact=source,
        scored_predictions=result.scored_predictions,
        strategy_aggregates=result.strategy_aggregates,
        overall_aggregate=result.overall_aggregate,
    )
    first = serialize_replay_scoring_artifact(scoring_artifact)
    second = serialize_replay_scoring_artifact(scoring_artifact)
    assert first == second
    artifact_path = tmp_path / "replay-scoring-artifact.json"
    artifact_path.write_bytes(first)
    assert artifact_path.resolve().is_relative_to(tmp_path.resolve())
    assert not artifact_path.resolve().is_relative_to(REPO_ROOT.resolve())
    restored = deserialize_replay_scoring_artifact(artifact_path.read_bytes())
    assert restored == scoring_artifact
    assert recompute_scoring_artifact_payload_sha256(restored) == restored.payload_sha256

    assert serialize_replay_artifact(source) == source_bytes_before
    assert source.payload_sha256 == source_hash_before
    assert _table_snapshot(paths) == tables_before


def test_future_and_unrelated_draws_cannot_change_exact_target_scores(tmp_path: Path) -> None:
    without_bait = resolve_local_data_paths(
        environ={DATA_DIRECTORY_ENV: str(tmp_path / "without-bait")}
    )
    with_bait = resolve_local_data_paths(
        environ={DATA_DIRECTORY_ENV: str(tmp_path / "with-bait")}
    )
    _seed_draws(without_bait, include_leakage_bait=False)
    _seed_draws(with_bait, include_leakage_bait=True)
    source = _source_artifact()

    without_result = ScoreReplayArtifact(
        SQLiteReplayTargetOutcomeReader(without_bait)
    ).execute(source)
    with_result = ScoreReplayArtifact(SQLiteReplayTargetOutcomeReader(with_bait)).execute(source)

    assert with_result == without_result


def test_missing_database_and_target_return_typed_closed_results(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    reader = SQLiteReplayTargetOutcomeReader(paths)

    missing_database = reader.load_target_outcome(LotteryType.BIG_LOTTO, "300")
    assert missing_database.status is ReplayTargetOutcomeReadStatus.NOT_FOUND
    assert (
        missing_database.reason_code
        is ReplayTargetOutcomeReadReason.TARGET_OUTCOME_NOT_FOUND
    )

    _seed_draws(paths)
    missing_target = reader.load_target_outcome(LotteryType.BIG_LOTTO, "absent")
    assert missing_target.status is ReplayTargetOutcomeReadStatus.NOT_FOUND
    assert (
        missing_target.reason_code
        is ReplayTargetOutcomeReadReason.TARGET_OUTCOME_NOT_FOUND
    )
