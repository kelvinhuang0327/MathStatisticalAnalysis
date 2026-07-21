"""Integration tests for the Replay-scoring projection SQLite repository.

Every database in this file lives under pytest's own ``tmp_path`` and is
discarded automatically at test teardown; nothing here ever opens a
canonical, default, or ``historical_*`` production database. Also folds in
focused migration/schema assertions (idempotency, checksum/text drift,
foreign-key enforcement) rather than a separate file, per the task's
footprint budget.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from lottolab.application.use_cases.persist_replay_scoring_artifact import (
    PersistReplayScoringArtifact,
)
from lottolab.application.use_cases.score_replay_artifact import ScoreReplayArtifact
from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_predictions import ReplayTarget
from lottolab.domain.replay_scoring import (
    ReplayTargetOutcome,
    ReplayTargetOutcomeReadReason,
    ReplayTargetOutcomeReadResult,
)
from lottolab.domain.replay_scoring_projection import ReplayScoringPersistenceOutcome
from lottolab.evidence.replay_artifact import (
    build_replay_artifact,
    build_replay_prediction_snapshot,
)
from lottolab.evidence.replay_scoring_artifact import (
    ReplayScoringArtifact,
    build_replay_scoring_artifact,
    serialize_replay_scoring_artifact,
)
from lottolab.infrastructure.persistence.replay_scoring_projection_repository import (
    ReplayScoringProjectionStorageError,
    ReplayScoringProjectionTamperError,
    SQLiteReplayScoringProjectionRepository,
)
from lottolab.infrastructure.persistence.replay_scoring_schema import (
    CURRENT_SCHEMA_VERSION,
    MIGRATION_NAME,
    TABLE_NAMES,
    ReplayScoringSchemaChecksumError,
    ReplayScoringSchemaMigrationError,
    initialize_schema,
    open_database,
    verify_schema_read_only,
)


class _Reader:
    def __init__(self, outcome: ReplayTargetOutcome) -> None:
        self.outcome = outcome

    def load_target_outcome(
        self, lottery_type: LotteryType, target_draw_number: str
    ) -> ReplayTargetOutcomeReadResult:
        if target_draw_number == self.outcome.target_draw_number:
            return ReplayTargetOutcomeReadResult.found(self.outcome)
        return ReplayTargetOutcomeReadResult.not_found(
            ReplayTargetOutcomeReadReason.TARGET_OUTCOME_NOT_FOUND
        )


def _build_two_by_two_artifact(
    *, dataset_version: str = "1", target_draw_numbers: tuple[str, str] = ("300", "301")
) -> ReplayScoringArtifact:
    """One artifact with a winning tier, explicit NO_PRIZE, and both not-scored reasons.

    2 targets x 2 strategies = 4 scored records:
    (target0, alpha) -> SCORED, a winning tier
    (target0, beta)  -> SCORED, explicit NO_PRIZE
    (target1, alpha) -> NOT_SCORED_HISTORY_CLOSED
    (target1, beta)  -> NOT_SCORED_PREDICTION_CLOSED
    """

    targets = (
        ReplayTarget(target_draw_numbers[0], date(2026, 3, 1)),
        ReplayTarget(target_draw_numbers[1], date(2026, 3, 2)),
    )
    snapshots = (
        build_replay_prediction_snapshot(
            dataset_id="dataset",
            dataset_version=dataset_version,
            lottery_type=LotteryType.BIG_LOTTO,
            target=targets[0],
            strategy_id="alpha",
            strategy_identity=("alpha", "Alpha", "1.0.0"),
            history_status="OK",
            history_reason_code=None,
            causal_history=(),
            prediction_status="OK",
            prediction_reason_code=None,
            predicted_main_numbers=(1, 2, 3, 4, 5, 6),
        ),
        build_replay_prediction_snapshot(
            dataset_id="dataset",
            dataset_version=dataset_version,
            lottery_type=LotteryType.BIG_LOTTO,
            target=targets[0],
            strategy_id="beta",
            strategy_identity=("beta", "Beta", "1.0.0"),
            history_status="OK",
            history_reason_code=None,
            causal_history=(),
            prediction_status="OK",
            prediction_reason_code=None,
            predicted_main_numbers=(13, 14, 15, 16, 17, 18),
        ),
        build_replay_prediction_snapshot(
            dataset_id="dataset",
            dataset_version=dataset_version,
            lottery_type=LotteryType.BIG_LOTTO,
            target=targets[1],
            strategy_id="alpha",
            strategy_identity=("alpha", "Alpha", "1.0.0"),
            history_status="TARGET_NOT_FOUND",
            history_reason_code="TARGET_DRAW_NOT_FOUND",
            causal_history=None,
            prediction_status=None,
            prediction_reason_code=None,
            predicted_main_numbers=None,
        ),
        build_replay_prediction_snapshot(
            dataset_id="dataset",
            dataset_version=dataset_version,
            lottery_type=LotteryType.BIG_LOTTO,
            target=targets[1],
            strategy_id="beta",
            strategy_identity=("beta", "Beta", "1.0.0"),
            history_status="OK",
            history_reason_code=None,
            causal_history=(),
            prediction_status="STRATEGY_ERROR",
            prediction_reason_code="STRATEGY_EXECUTION_FAILED",
            predicted_main_numbers=None,
        ),
    )
    source = build_replay_artifact(
        dataset_id="dataset",
        dataset_version=dataset_version,
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_ids=("alpha", "beta"),
        targets=targets,
        snapshots=snapshots,
    )
    outcome = ReplayTargetOutcome.create(
        lottery_type=LotteryType.BIG_LOTTO,
        target_draw_number=target_draw_numbers[0],
        target_draw_date=date(2026, 3, 1),
        winning_main_numbers=(1, 2, 3, 4, 5, 6),
        winning_special_number=7,
    )
    result = ScoreReplayArtifact(_Reader(outcome)).execute(source)
    return build_replay_scoring_artifact(
        source_artifact=source,
        scored_predictions=result.scored_predictions,
        strategy_aggregates=result.strategy_aggregates,
        overall_aggregate=result.overall_aggregate,
    )


def _table_row_count(connection: sqlite3.Connection, table: str) -> int:
    return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_fresh_valid_artifact_persists_one_run_and_exact_child_row_counts(
    tmp_path: Path,
) -> None:
    database = tmp_path / "replay_scoring.db"
    repository = SQLiteReplayScoringProjectionRepository(database)
    use_case = PersistReplayScoringArtifact(repository)
    artifact = _build_two_by_two_artifact()

    result = use_case.execute(artifact)

    assert result.outcome is ReplayScoringPersistenceOutcome.INSERTED
    assert result.scoring_artifact_payload_sha256 == artifact.payload_sha256
    with open_database(database, read_only=True) as connection:
        assert _table_row_count(connection, "replay_scoring_runs") == 1
        assert _table_row_count(connection, "replay_scored_predictions") == len(
            artifact.scored_predictions
        )
        assert _table_row_count(connection, "replay_scoring_strategy_aggregates") == len(
            artifact.strategy_aggregates
        )
        assert _table_row_count(connection, "replay_scoring_overall_aggregates") == 1


def test_readback_reconstructs_the_exact_typed_artifact_with_identical_bytes_and_sha(
    tmp_path: Path,
) -> None:
    database = tmp_path / "replay_scoring.db"
    repository = SQLiteReplayScoringProjectionRepository(database)
    use_case = PersistReplayScoringArtifact(repository)
    artifact = _build_two_by_two_artifact()

    use_case.execute(artifact)
    restored = repository.get_replay_scoring_artifact(artifact.payload_sha256)

    assert restored == artifact
    assert restored is not None
    assert serialize_replay_scoring_artifact(restored) == serialize_replay_scoring_artifact(
        artifact
    )
    assert restored.payload_sha256 == artifact.payload_sha256


def test_exact_reimport_is_idempotent_no_op_with_unchanged_table_contents(
    tmp_path: Path,
) -> None:
    database = tmp_path / "replay_scoring.db"
    repository = SQLiteReplayScoringProjectionRepository(database)
    use_case = PersistReplayScoringArtifact(repository)
    artifact = _build_two_by_two_artifact()

    first = use_case.execute(artifact)
    with open_database(database, read_only=True) as connection:
        before_run_count = _table_row_count(connection, "replay_scoring_runs")
        before_prediction_count = _table_row_count(connection, "replay_scored_predictions")

    second = use_case.execute(artifact)

    assert first.outcome is ReplayScoringPersistenceOutcome.INSERTED
    assert second.outcome is ReplayScoringPersistenceOutcome.ALREADY_PRESENT
    with open_database(database, read_only=True) as connection:
        assert _table_row_count(connection, "replay_scoring_runs") == before_run_count
        assert (
            _table_row_count(connection, "replay_scored_predictions")
            == before_prediction_count
        )
        stored_hashes = {
            row[0]
            for row in connection.execute(
                "SELECT scored_result_sha256 FROM replay_scored_predictions"
            )
        }
    assert stored_hashes == {record.scored_result_sha256 for record in artifact.scored_predictions}


def test_second_independent_run_is_isolated_from_the_first(tmp_path: Path) -> None:
    database = tmp_path / "replay_scoring.db"
    repository = SQLiteReplayScoringProjectionRepository(database)
    use_case = PersistReplayScoringArtifact(repository)
    first_artifact = _build_two_by_two_artifact()
    second_artifact = _build_two_by_two_artifact(
        dataset_version="2", target_draw_numbers=("400", "401")
    )
    assert first_artifact.payload_sha256 != second_artifact.payload_sha256

    use_case.execute(first_artifact)
    use_case.execute(second_artifact)

    with open_database(database, read_only=True) as connection:
        assert _table_row_count(connection, "replay_scoring_runs") == 2
        assert _table_row_count(connection, "replay_scored_predictions") == 2 * len(
            first_artifact.scored_predictions
        )
    restored_first = repository.get_replay_scoring_artifact(first_artifact.payload_sha256)
    restored_second = repository.get_replay_scoring_artifact(second_artifact.payload_sha256)
    assert restored_first == first_artifact
    assert restored_second == second_artifact


def test_conflicting_stored_content_under_the_same_identity_fails_closed(
    tmp_path: Path,
) -> None:
    database = tmp_path / "replay_scoring.db"
    repository = SQLiteReplayScoringProjectionRepository(database)
    artifact = _build_two_by_two_artifact()
    canonical_bytes = serialize_replay_scoring_artifact(artifact)
    repository.persist_replay_scoring_artifact(artifact, canonical_bytes)

    # Simulate a corrupted/foreign write under the same run identity: the
    # stored canonical bytes no longer match what this artifact serializes to.
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            UPDATE replay_scoring_runs SET canonical_bytes = ?
            WHERE scoring_artifact_payload_sha256 = ?
            """,
            (canonical_bytes + b" ", artifact.payload_sha256),
        )
        connection.commit()

    result = repository.persist_replay_scoring_artifact(artifact, canonical_bytes)

    assert result.outcome is ReplayScoringPersistenceOutcome.CONFLICT
    with open_database(database, read_only=True) as connection:
        assert _table_row_count(connection, "replay_scoring_runs") == 1


def test_transaction_failure_leaves_no_partial_rows(tmp_path: Path) -> None:
    database = tmp_path / "replay_scoring.db"
    repository = SQLiteReplayScoringProjectionRepository(database)
    artifact = _build_two_by_two_artifact()
    canonical_bytes = serialize_replay_scoring_artifact(artifact)
    # Corrupt the artifact's own internal consistency *after* construction
    # (bypassing the frozen dataclass) so a mid-transaction insert fails —
    # proving atomicity independently of any particular failure cause.
    object.__setattr__(artifact, "strategy_aggregates", artifact.strategy_aggregates[:1])

    with pytest.raises(ReplayScoringProjectionStorageError):
        repository.persist_replay_scoring_artifact(artifact, canonical_bytes)

    with open_database(database, read_only=True) as connection:
        assert _table_row_count(connection, "replay_scoring_runs") == 0
        assert _table_row_count(connection, "replay_scored_predictions") == 0
        assert _table_row_count(connection, "replay_scoring_strategy_aggregates") == 0
        assert _table_row_count(connection, "replay_scoring_overall_aggregates") == 0


def test_tampered_stored_child_row_fails_closed_on_readback(tmp_path: Path) -> None:
    database = tmp_path / "replay_scoring.db"
    repository = SQLiteReplayScoringProjectionRepository(database)
    artifact = _build_two_by_two_artifact()
    repository.persist_replay_scoring_artifact(
        artifact, serialize_replay_scoring_artifact(artifact)
    )

    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            UPDATE replay_scored_predictions SET main_number_hit_count = 99
            WHERE run_sha256 = ? AND ordinal = 0
            """,
            (artifact.payload_sha256,),
        )
        connection.commit()

    with pytest.raises(ReplayScoringProjectionTamperError):
        repository.get_replay_scoring_artifact(artifact.payload_sha256)


def test_reordered_ordinals_fail_closed_on_readback(tmp_path: Path) -> None:
    database = tmp_path / "replay_scoring.db"
    repository = SQLiteReplayScoringProjectionRepository(database)
    artifact = _build_two_by_two_artifact()
    repository.persist_replay_scoring_artifact(
        artifact, serialize_replay_scoring_artifact(artifact)
    )

    with sqlite3.connect(database) as connection:
        # Swap ordinals 1 and 2 (a cross-target/cross-strategy reorder) using a
        # temporary sentinel ordinal to respect the UNIQUE(run, ordinal) index.
        connection.execute(
            """
            UPDATE replay_scored_predictions SET ordinal = 999
            WHERE run_sha256 = ? AND ordinal = 1
            """,
            (artifact.payload_sha256,),
        )
        connection.execute(
            """
            UPDATE replay_scored_predictions SET ordinal = 1
            WHERE run_sha256 = ? AND ordinal = 2
            """,
            (artifact.payload_sha256,),
        )
        connection.execute(
            """
            UPDATE replay_scored_predictions SET ordinal = 2
            WHERE run_sha256 = ? AND ordinal = 999
            """,
            (artifact.payload_sha256,),
        )
        connection.commit()

    with pytest.raises(ReplayScoringProjectionTamperError):
        repository.get_replay_scoring_artifact(artifact.payload_sha256)


def test_duplicate_child_ordinal_is_rejected_by_the_unique_constraint(tmp_path: Path) -> None:
    database = tmp_path / "replay_scoring.db"
    repository = SQLiteReplayScoringProjectionRepository(database)
    artifact = _build_two_by_two_artifact()
    repository.persist_replay_scoring_artifact(
        artifact, serialize_replay_scoring_artifact(artifact)
    )

    with sqlite3.connect(database) as connection, pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO replay_scored_predictions (
                run_sha256, ordinal, source_snapshot_result_sha256, scored_result_sha256,
                target_draw_number, target_draw_date, strategy_id, strategy_version,
                source_history_status, scoring_status
            ) VALUES (?, 0, ?, ?, '999', '2026-03-09', 'gamma', 'OK', 'OK', 'SCORED')
            """,
            (artifact.payload_sha256, "d" * 64, "e" * 64),
        )


def test_optional_target_and_strategy_filters_return_deterministic_ordered_rows(
    tmp_path: Path,
) -> None:
    database = tmp_path / "replay_scoring.db"
    repository = SQLiteReplayScoringProjectionRepository(database)
    artifact = _build_two_by_two_artifact()
    repository.persist_replay_scoring_artifact(
        artifact, serialize_replay_scoring_artifact(artifact)
    )

    by_target = repository.list_scored_predictions(
        artifact.payload_sha256, target_draw_number="300"
    )
    assert [record.strategy_id for record in by_target] == ["alpha", "beta"]

    by_strategy = repository.list_scored_predictions(
        artifact.payload_sha256, strategy_id="alpha"
    )
    assert [record.target_draw_number for record in by_strategy] == ["300", "301"]

    by_both = repository.list_scored_predictions(
        artifact.payload_sha256, target_draw_number="301", strategy_id="beta"
    )
    assert len(by_both) == 1
    assert by_both[0].strategy_id == "beta"
    assert by_both[0].target_draw_number == "301"

    all_records = repository.list_scored_predictions(artifact.payload_sha256)
    assert [record.ordinal for record in all_records] == [0, 1, 2, 3]


def test_canonical_and_historical_tables_are_never_touched(tmp_path: Path) -> None:
    database = tmp_path / "replay_scoring.db"
    repository = SQLiteReplayScoringProjectionRepository(database)
    artifact = _build_two_by_two_artifact()
    repository.persist_replay_scoring_artifact(
        artifact, serialize_replay_scoring_artifact(artifact)
    )

    with sqlite3.connect(database) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }
    assert table_names == set(TABLE_NAMES)
    forbidden = {"draws", "ingestion_runs", "ingestion_items", "schema_migrations"}
    assert not (table_names & forbidden)
    assert not any(name.startswith("historical_") for name in table_names)


def test_every_database_path_lives_under_tmp_path(tmp_path: Path) -> None:
    database = tmp_path / "nested" / "replay_scoring.db"
    repository = SQLiteReplayScoringProjectionRepository(database)
    artifact = _build_two_by_two_artifact()

    repository.persist_replay_scoring_artifact(
        artifact, serialize_replay_scoring_artifact(artifact)
    )

    assert database.exists()
    assert database.resolve().is_relative_to(tmp_path.resolve())


# --- Focused schema/migration assertions (folded in per the task's path budget) ---


def test_initialize_schema_creates_all_five_tables(tmp_path: Path) -> None:
    database = tmp_path / "replay_scoring.db"
    initialize_schema(database)
    with open_database(database, read_only=True) as connection:
        names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        migration_rows = connection.execute(
            "SELECT version, name FROM replay_scoring_schema_migrations"
        ).fetchall()
    assert names == set(TABLE_NAMES)
    assert migration_rows == [(CURRENT_SCHEMA_VERSION, MIGRATION_NAME)]


def test_initialize_schema_is_idempotent_and_byte_stable(tmp_path: Path) -> None:
    database = tmp_path / "replay_scoring.db"
    initialize_schema(database)
    first_bytes = database.read_bytes()
    initialize_schema(database)
    second_bytes = database.read_bytes()
    assert first_bytes == second_bytes
    assert verify_schema_read_only(database) is True


def test_initialize_schema_preserves_prior_data_on_repeat_call(tmp_path: Path) -> None:
    database = tmp_path / "replay_scoring.db"
    repository = SQLiteReplayScoringProjectionRepository(database)
    artifact = _build_two_by_two_artifact()
    repository.persist_replay_scoring_artifact(
        artifact, serialize_replay_scoring_artifact(artifact)
    )

    initialize_schema(database)  # repeat call must be read-only verification, not a rewrite

    with open_database(database, read_only=True) as connection:
        assert _table_row_count(connection, "replay_scoring_runs") == 1
    assert repository.get_replay_scoring_artifact(artifact.payload_sha256) == artifact


def test_verify_schema_read_only_returns_false_for_absent_database(tmp_path: Path) -> None:
    database = tmp_path / "absent.db"
    assert verify_schema_read_only(database) is False
    assert not database.exists()


def test_checksum_drift_is_rejected(tmp_path: Path) -> None:
    database = tmp_path / "replay_scoring.db"
    initialize_schema(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE replay_scoring_schema_migrations SET checksum = 'deadbeef' WHERE version = ?",
            (CURRENT_SCHEMA_VERSION,),
        )
        connection.commit()
    with pytest.raises(ReplayScoringSchemaChecksumError):
        verify_schema_read_only(database)


def test_schema_object_text_drift_is_rejected(tmp_path: Path) -> None:
    database = tmp_path / "replay_scoring.db"
    initialize_schema(database)
    with sqlite3.connect(database) as connection:
        connection.execute("DROP TABLE replay_scoring_overall_aggregates")
        connection.commit()
    with pytest.raises(ReplayScoringSchemaMigrationError):
        verify_schema_read_only(database)


def test_open_database_on_absent_database_fails_closed(tmp_path: Path) -> None:
    database = tmp_path / "missing.db"
    with pytest.raises(ReplayScoringSchemaMigrationError), open_database(database):
        pass


def test_foreign_keys_are_enforced_for_scored_predictions(tmp_path: Path) -> None:
    database = tmp_path / "replay_scoring.db"
    initialize_schema(database)
    with open_database(database) as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone() == (1,)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO replay_scored_predictions (
                    run_sha256, ordinal, source_snapshot_result_sha256, scored_result_sha256,
                    target_draw_number, target_draw_date, strategy_id, source_history_status,
                    scoring_status
                ) VALUES ('missing-run', 0, ?, ?, '300', '2026-03-01', 'alpha', 'OK', 'SCORED')
                """,
                ("a" * 64, "b" * 64),
            )
