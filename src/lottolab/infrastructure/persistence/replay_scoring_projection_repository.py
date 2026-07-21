"""Whole-run atomic SQLite repository for the Replay-scoring projection.

Persists exactly the values an already-validated ``ReplayScoringArtifact``
carries. Tamper detection on readback is layered: each reconstructed nested
value object (``ReplayScoredPrediction``, ``ReplayPrizeAggregation``) already
recomputes and verifies its own SHA-256 in ``__post_init__``, and the
top-level ``ReplayScoringArtifact`` recomputes cross-record consistency and
its own payload hash — so reconstructing the typed objects from stored rows
*is* the tamper check; this module never duplicates that hashing logic.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast

from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import BigLottoPrizeTierId, NoPrizeResult
from lottolab.domain.replay_predictions import ReplayTarget
from lottolab.domain.replay_scoring import (
    AGGREGATION_SCHEMA_VERSION,
    SCORING_SCHEMA_VERSION,
    ReplayPrizeAggregation,
    ReplayScoredPrediction,
    ReplayScoringReason,
    ReplayScoringStatus,
    ReplayScoringStrategyIdentity,
)
from lottolab.domain.replay_scoring_projection import (
    ReplayOverallAggregateProjection,
    ReplayScoredPredictionProjection,
    ReplayScoringPersistenceOutcome,
    ReplayScoringPersistResult,
    ReplayScoringRunProjection,
    ReplayStrategyAggregateProjection,
)
from lottolab.evidence.replay_scoring_artifact import (
    ReplayScoringArtifact,
    ReplayScoringArtifactShapeError,
    ReplayScoringArtifactTamperError,
    serialize_replay_scoring_artifact,
)
from lottolab.infrastructure.persistence.replay_scoring_schema import (
    ReplayScoringSchemaError,
    initialize_schema,
    open_database,
    verify_schema_read_only,
)

_AGGREGATE_COUNT_COLUMNS = (
    "source_snapshot_count",
    "scored_count",
    "history_closed_count",
    "prediction_closed_count",
    "target_outcome_not_found_count",
    "target_identity_mismatch_count",
    "first_prize_count",
    "second_prize_count",
    "third_prize_count",
    "fourth_prize_count",
    "fifth_prize_count",
    "sixth_prize_count",
    "seventh_prize_count",
    "general_prize_count",
    "no_prize_count",
)

_PREDICTION_COLUMNS = (
    "ordinal",
    "source_snapshot_result_sha256",
    "scored_result_sha256",
    "target_draw_number",
    "target_draw_date",
    "strategy_id",
    "strategy_version",
    "source_history_status",
    "source_history_reason_code",
    "source_prediction_status",
    "source_prediction_reason_code",
    "scoring_status",
    "scoring_reason_code",
    "predicted_main_numbers_json",
    "target_outcome_sha256",
    "main_number_hit_count",
    "special_number_hit",
    "prize_tier_id",
    "prize_official_label",
    "no_prize_result",
)


class ReplayScoringProjectionStorageError(RuntimeError):
    """The Replay-scoring projection repository failed a storage operation."""


class ReplayScoringProjectionTamperError(ReplayScoringProjectionStorageError):
    """Persisted Replay-scoring rows do not match their recorded identity/hashes."""


def _default_clock() -> datetime:
    return datetime.now(UTC)


def _utc_format(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise ValueError("timestamp must use UTC")
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


class SQLiteReplayScoringProjectionRepository:
    """Explicit-path SQLite implementation of the Replay-scoring projection ports."""

    def __init__(
        self,
        database: Path,
        *,
        clock: Callable[[], datetime] = _default_clock,
    ) -> None:
        self._database = database
        self._clock = clock

    def persist_replay_scoring_artifact(
        self,
        artifact: ReplayScoringArtifact,
        canonical_bytes: bytes,
    ) -> ReplayScoringPersistResult:
        try:
            initialize_schema(self._database)
            with open_database(self._database) as connection:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    row = connection.execute(
                        """
                        SELECT canonical_bytes FROM replay_scoring_runs
                        WHERE scoring_artifact_payload_sha256 = ?
                        """,
                        (artifact.payload_sha256,),
                    ).fetchone()
                    if row is not None:
                        connection.rollback()
                        stored_bytes = bytes(row[0])
                        outcome = (
                            ReplayScoringPersistenceOutcome.ALREADY_PRESENT
                            if stored_bytes == canonical_bytes
                            else ReplayScoringPersistenceOutcome.CONFLICT
                        )
                        return ReplayScoringPersistResult(outcome, artifact.payload_sha256)
                    _insert_full_run(
                        connection, artifact, canonical_bytes, created_at=self._clock()
                    )
                    connection.commit()
                    return ReplayScoringPersistResult(
                        ReplayScoringPersistenceOutcome.INSERTED, artifact.payload_sha256
                    )
                except BaseException:
                    if connection.in_transaction:
                        connection.rollback()
                    raise
        except ReplayScoringProjectionStorageError:
            raise
        except Exception as exc:
            raise ReplayScoringProjectionStorageError(
                "replay-scoring projection persistence failed"
            ) from exc

    def get_run(
        self, scoring_artifact_payload_sha256: str
    ) -> ReplayScoringRunProjection | None:
        if not _verify_available(self._database):
            return None
        with _read_only_connection(self._database) as connection:
            row = connection.execute(
                """
                SELECT scoring_artifact_schema_version, source_replay_artifact_payload_sha256,
                       dataset_id, dataset_version, lottery_type, target_count, strategy_count,
                       scored_record_count, overall_aggregate_sha256
                FROM replay_scoring_runs WHERE scoring_artifact_payload_sha256 = ?
                """,
                (scoring_artifact_payload_sha256,),
            ).fetchone()
        if row is None:
            return None
        try:
            return ReplayScoringRunProjection(
                scoring_artifact_schema_version=str(row[0]),
                scoring_artifact_payload_sha256=scoring_artifact_payload_sha256,
                source_replay_artifact_payload_sha256=str(row[1]),
                dataset_id=str(row[2]),
                dataset_version=str(row[3]),
                lottery_type=str(row[4]),
                target_count=_decode_int(row[5]),
                strategy_count=_decode_int(row[6]),
                scored_record_count=_decode_int(row[7]),
                overall_aggregate_sha256=str(row[8]),
            )
        except (TypeError, ValueError) as exc:
            raise ReplayScoringProjectionTamperError("stored run row is malformed") from exc

    def get_overall_aggregate(
        self, scoring_artifact_payload_sha256: str
    ) -> ReplayOverallAggregateProjection | None:
        if not _verify_available(self._database):
            return None
        with _read_only_connection(self._database) as connection:
            row = connection.execute(
                f"""
                SELECT {", ".join(_AGGREGATE_COUNT_COLUMNS)}, aggregate_sha256
                FROM replay_scoring_overall_aggregates WHERE run_sha256 = ?
                """,
                (scoring_artifact_payload_sha256,),
            ).fetchone()
        if row is None:
            return None
        try:
            counts = {name: _decode_int(value) for name, value in zip(
                _AGGREGATE_COUNT_COLUMNS, row[:-1], strict=True
            )}
            return ReplayOverallAggregateProjection(
                run_payload_sha256=scoring_artifact_payload_sha256,
                aggregate_sha256=str(row[-1]),
                **counts,
            )
        except (TypeError, ValueError) as exc:
            raise ReplayScoringProjectionTamperError(
                "stored overall aggregate row is malformed"
            ) from exc

    def list_strategy_aggregates(
        self, scoring_artifact_payload_sha256: str
    ) -> tuple[ReplayStrategyAggregateProjection, ...]:
        if not _verify_available(self._database):
            return ()
        with _read_only_connection(self._database) as connection:
            rows = connection.execute(
                f"""
                SELECT ordinal, strategy_id, strategy_version,
                       {", ".join(_AGGREGATE_COUNT_COLUMNS)}, aggregate_sha256
                FROM replay_scoring_strategy_aggregates
                WHERE run_sha256 = ? ORDER BY ordinal ASC
                """,
                (scoring_artifact_payload_sha256,),
            ).fetchall()
        try:
            return tuple(
                _row_to_strategy_aggregate_projection(row, scoring_artifact_payload_sha256)
                for row in rows
            )
        except (TypeError, ValueError) as exc:
            raise ReplayScoringProjectionTamperError(
                "stored strategy aggregate row is malformed"
            ) from exc

    def list_scored_predictions(
        self,
        scoring_artifact_payload_sha256: str,
        *,
        target_draw_number: str | None = None,
        strategy_id: str | None = None,
    ) -> tuple[ReplayScoredPredictionProjection, ...]:
        if not _verify_available(self._database):
            return ()
        conditions = ["run_sha256 = ?"]
        params: list[object] = [scoring_artifact_payload_sha256]
        if target_draw_number is not None:
            conditions.append("target_draw_number = ?")
            params.append(target_draw_number)
        if strategy_id is not None:
            conditions.append("strategy_id = ?")
            params.append(strategy_id)
        query = (
            f"SELECT {', '.join(_PREDICTION_COLUMNS)} FROM replay_scored_predictions "
            f"WHERE {' AND '.join(conditions)} ORDER BY ordinal ASC"
        )
        with _read_only_connection(self._database) as connection:
            rows = connection.execute(query, params).fetchall()
        try:
            return tuple(
                _row_to_scored_prediction_projection(row, scoring_artifact_payload_sha256)
                for row in rows
            )
        except (TypeError, ValueError) as exc:
            raise ReplayScoringProjectionTamperError(
                "stored scored-prediction row is malformed"
            ) from exc

    def get_replay_scoring_artifact(
        self, scoring_artifact_payload_sha256: str
    ) -> ReplayScoringArtifact | None:
        if not _verify_available(self._database):
            return None
        with _read_only_connection(self._database) as connection:
            run_row = connection.execute(
                """
                SELECT scoring_artifact_schema_version, source_replay_artifact_payload_sha256,
                       dataset_id, dataset_version, lottery_type, target_count, strategy_count,
                       scored_record_count, canonical_bytes
                FROM replay_scoring_runs WHERE scoring_artifact_payload_sha256 = ?
                """,
                (scoring_artifact_payload_sha256,),
            ).fetchone()
            if run_row is None:
                return None
            prediction_rows = connection.execute(
                f"""
                SELECT {", ".join(_PREDICTION_COLUMNS)} FROM replay_scored_predictions
                WHERE run_sha256 = ? ORDER BY ordinal ASC
                """,
                (scoring_artifact_payload_sha256,),
            ).fetchall()
            aggregate_rows = connection.execute(
                f"""
                SELECT ordinal, strategy_id, strategy_version,
                       {", ".join(_AGGREGATE_COUNT_COLUMNS)}, aggregate_sha256
                FROM replay_scoring_strategy_aggregates
                WHERE run_sha256 = ? ORDER BY ordinal ASC
                """,
                (scoring_artifact_payload_sha256,),
            ).fetchall()
            overall_row = connection.execute(
                f"""
                SELECT {", ".join(_AGGREGATE_COUNT_COLUMNS)}, aggregate_sha256
                FROM replay_scoring_overall_aggregates WHERE run_sha256 = ?
                """,
                (scoring_artifact_payload_sha256,),
            ).fetchone()

        (
            artifact_schema_version,
            source_replay_artifact_payload_sha256,
            dataset_id,
            dataset_version,
            lottery_type_raw,
            target_count_raw,
            strategy_count_raw,
            scored_record_count_raw,
            canonical_bytes_blob,
        ) = run_row
        target_count = _decode_int(target_count_raw)
        strategy_count = _decode_int(strategy_count_raw)
        scored_record_count = _decode_int(scored_record_count_raw)

        if overall_row is None:
            raise ReplayScoringProjectionTamperError("run is missing its overall aggregate row")
        if len(aggregate_rows) != strategy_count:
            raise ReplayScoringProjectionTamperError("strategy aggregate row count mismatch")
        if [_decode_int(row[0]) for row in aggregate_rows] != list(range(strategy_count)):
            raise ReplayScoringProjectionTamperError(
                "strategy aggregate ordinal sequence mismatch"
            )
        if len(prediction_rows) != scored_record_count:
            raise ReplayScoringProjectionTamperError("scored prediction row count mismatch")
        if [_decode_int(row[0]) for row in prediction_rows] != list(
            range(scored_record_count)
        ):
            raise ReplayScoringProjectionTamperError(
                "scored prediction ordinal sequence mismatch"
            )

        try:
            lottery_type = LotteryType(str(lottery_type_raw))
            strategy_identities = tuple(
                ReplayScoringStrategyIdentity(
                    strategy_id=str(row[5]),
                    strategy_version=None if row[6] is None else str(row[6]),
                )
                for row in prediction_rows[:strategy_count]
            )
            target_identities = tuple(
                ReplayTarget(
                    draw_number=str(row[3]),
                    draw_date=date.fromisoformat(str(row[4])),
                )
                for row in prediction_rows[0::strategy_count][:target_count]
            )
            scored_predictions = tuple(
                _build_scored_prediction(
                    row,
                    source_replay_artifact_payload_sha256=str(
                        source_replay_artifact_payload_sha256
                    ),
                    dataset_id=str(dataset_id),
                    dataset_version=str(dataset_version),
                    lottery_type=lottery_type,
                )
                for row in prediction_rows
            )
            strategy_aggregates = tuple(_build_aggregation(row) for row in aggregate_rows)
            overall_aggregate = _build_overall_aggregation(overall_row)
            artifact = ReplayScoringArtifact(
                artifact_schema_version=str(artifact_schema_version),
                source_replay_artifact_payload_sha256=str(
                    source_replay_artifact_payload_sha256
                ),
                dataset_id=str(dataset_id),
                dataset_version=str(dataset_version),
                lottery_type=lottery_type,
                target_identities=target_identities,
                strategy_identities=strategy_identities,
                scored_predictions=scored_predictions,
                strategy_aggregates=strategy_aggregates,
                overall_aggregate=overall_aggregate,
                scored_record_count=scored_record_count,
                payload_sha256=scoring_artifact_payload_sha256,
            )
        except (
            TypeError,
            ValueError,
            ReplayScoringArtifactTamperError,
            ReplayScoringArtifactShapeError,
        ) as exc:
            raise ReplayScoringProjectionTamperError(
                "stored replay-scoring projection failed reconstruction"
            ) from exc

        reconstructed_bytes = serialize_replay_scoring_artifact(artifact)
        if reconstructed_bytes != bytes(canonical_bytes_blob):
            raise ReplayScoringProjectionTamperError(
                "reconstructed canonical bytes do not match stored canonical bytes"
            )
        return artifact


def _insert_full_run(
    connection: sqlite3.Connection,
    artifact: ReplayScoringArtifact,
    canonical_bytes: bytes,
    *,
    created_at: datetime,
) -> None:
    connection.execute(
        """
        INSERT INTO replay_scoring_runs (
            scoring_artifact_payload_sha256, scoring_artifact_schema_version,
            source_replay_artifact_payload_sha256, dataset_id, dataset_version, lottery_type,
            target_count, strategy_count, scored_record_count, overall_aggregate_sha256,
            canonical_bytes, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            artifact.payload_sha256,
            artifact.artifact_schema_version,
            artifact.source_replay_artifact_payload_sha256,
            artifact.dataset_id,
            artifact.dataset_version,
            artifact.lottery_type.value,
            len(artifact.target_identities),
            len(artifact.strategy_identities),
            artifact.scored_record_count,
            artifact.overall_aggregate.aggregation_sha256,
            canonical_bytes,
            _utc_format(created_at),
        ),
    )
    for ordinal, record in enumerate(artifact.scored_predictions):
        connection.execute(
            """
            INSERT INTO replay_scored_predictions (
                run_sha256, ordinal, source_snapshot_result_sha256, scored_result_sha256,
                target_draw_number, target_draw_date, strategy_id, strategy_version,
                source_history_status, source_history_reason_code, source_prediction_status,
                source_prediction_reason_code, scoring_status, scoring_reason_code,
                predicted_main_numbers_json, target_outcome_sha256, main_number_hit_count,
                special_number_hit, prize_tier_id, prize_official_label, no_prize_result
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact.payload_sha256,
                ordinal,
                record.source_replay_snapshot_result_sha256,
                record.scored_result_sha256,
                record.target_draw_number,
                record.target_draw_date.isoformat(),
                record.strategy_id,
                record.strategy_version,
                record.source_history_status,
                record.source_history_reason_code,
                record.source_prediction_status,
                record.source_prediction_reason_code,
                record.scoring_status.value,
                None if record.scoring_reason_code is None else record.scoring_reason_code.value,
                (
                    None
                    if record.predicted_main_numbers is None
                    else json.dumps(list(record.predicted_main_numbers), separators=(",", ":"))
                ),
                record.target_outcome_sha256,
                record.main_number_hit_count,
                None if record.special_number_hit is None else int(record.special_number_hit),
                None if record.prize_tier_id is None else record.prize_tier_id.value,
                record.prize_official_label,
                None if record.no_prize_result is None else record.no_prize_result.value,
            ),
        )
    for ordinal, (identity, aggregation) in enumerate(
        zip(artifact.strategy_identities, artifact.strategy_aggregates, strict=True)
    ):
        connection.execute(
            """
            INSERT INTO replay_scoring_strategy_aggregates (
                run_sha256, ordinal, strategy_id, strategy_version, source_snapshot_count,
                scored_count, history_closed_count, prediction_closed_count,
                target_outcome_not_found_count, target_identity_mismatch_count,
                first_prize_count, second_prize_count, third_prize_count, fourth_prize_count,
                fifth_prize_count, sixth_prize_count, seventh_prize_count, general_prize_count,
                no_prize_count, aggregate_sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact.payload_sha256,
                ordinal,
                identity.strategy_id,
                identity.strategy_version,
                aggregation.source_snapshot_count,
                aggregation.scored_count,
                aggregation.history_closed_count,
                aggregation.prediction_closed_count,
                aggregation.target_outcome_not_found_count,
                aggregation.target_identity_mismatch_count,
                aggregation.first_prize_count,
                aggregation.second_prize_count,
                aggregation.third_prize_count,
                aggregation.fourth_prize_count,
                aggregation.fifth_prize_count,
                aggregation.sixth_prize_count,
                aggregation.seventh_prize_count,
                aggregation.general_prize_count,
                aggregation.no_prize_count,
                aggregation.aggregation_sha256,
            ),
        )
    overall = artifact.overall_aggregate
    connection.execute(
        """
        INSERT INTO replay_scoring_overall_aggregates (
            run_sha256, source_snapshot_count, scored_count, history_closed_count,
            prediction_closed_count, target_outcome_not_found_count,
            target_identity_mismatch_count, first_prize_count, second_prize_count,
            third_prize_count, fourth_prize_count, fifth_prize_count, sixth_prize_count,
            seventh_prize_count, general_prize_count, no_prize_count, aggregate_sha256
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            artifact.payload_sha256,
            overall.source_snapshot_count,
            overall.scored_count,
            overall.history_closed_count,
            overall.prediction_closed_count,
            overall.target_outcome_not_found_count,
            overall.target_identity_mismatch_count,
            overall.first_prize_count,
            overall.second_prize_count,
            overall.third_prize_count,
            overall.fourth_prize_count,
            overall.fifth_prize_count,
            overall.sixth_prize_count,
            overall.seventh_prize_count,
            overall.general_prize_count,
            overall.no_prize_count,
            overall.aggregation_sha256,
        ),
    )


def _build_scored_prediction(
    row: tuple[object, ...],
    *,
    source_replay_artifact_payload_sha256: str,
    dataset_id: str,
    dataset_version: str,
    lottery_type: LotteryType,
) -> ReplayScoredPrediction:
    (
        _ordinal,
        source_snapshot_result_sha256,
        scored_result_sha256,
        target_draw_number,
        target_draw_date,
        strategy_id,
        strategy_version,
        source_history_status,
        source_history_reason_code,
        source_prediction_status,
        source_prediction_reason_code,
        scoring_status,
        scoring_reason_code,
        predicted_main_numbers_json,
        target_outcome_sha256,
        main_number_hit_count,
        special_number_hit,
        prize_tier_id,
        prize_official_label,
        no_prize_result,
    ) = row
    return ReplayScoredPrediction(
        scoring_schema_version=SCORING_SCHEMA_VERSION,
        source_replay_artifact_payload_sha256=source_replay_artifact_payload_sha256,
        source_replay_snapshot_result_sha256=str(source_snapshot_result_sha256),
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        lottery_type=lottery_type,
        target_draw_number=str(target_draw_number),
        target_draw_date=date.fromisoformat(str(target_draw_date)),
        strategy_id=str(strategy_id),
        strategy_version=None if strategy_version is None else str(strategy_version),
        source_history_status=str(source_history_status),
        source_history_reason_code=(
            None if source_history_reason_code is None else str(source_history_reason_code)
        ),
        source_prediction_status=(
            None if source_prediction_status is None else str(source_prediction_status)
        ),
        source_prediction_reason_code=(
            None
            if source_prediction_reason_code is None
            else str(source_prediction_reason_code)
        ),
        scoring_status=ReplayScoringStatus(str(scoring_status)),
        scoring_reason_code=(
            None if scoring_reason_code is None else ReplayScoringReason(str(scoring_reason_code))
        ),
        predicted_main_numbers=(
            None
            if predicted_main_numbers_json is None
            else _decode_json_int_tuple(predicted_main_numbers_json)
        ),
        target_outcome_sha256=(
            None if target_outcome_sha256 is None else str(target_outcome_sha256)
        ),
        main_number_hit_count=(
            None if main_number_hit_count is None else _decode_int(main_number_hit_count)
        ),
        special_number_hit=(
            None if special_number_hit is None else bool(_decode_int(special_number_hit))
        ),
        prize_tier_id=(None if prize_tier_id is None else BigLottoPrizeTierId(str(prize_tier_id))),
        prize_official_label=(
            None if prize_official_label is None else str(prize_official_label)
        ),
        no_prize_result=(None if no_prize_result is None else NoPrizeResult(str(no_prize_result))),
        scored_result_sha256=str(scored_result_sha256),
    )


def _build_aggregation(row: tuple[object, ...]) -> ReplayPrizeAggregation:
    ordinal_and_identity = row[:3]
    counts_and_hash = row[3:]
    _ordinal, strategy_id, strategy_version = ordinal_and_identity
    counts = {
        name: _decode_int(value)
        for name, value in zip(_AGGREGATE_COUNT_COLUMNS, counts_and_hash[:-1], strict=True)
    }
    return ReplayPrizeAggregation(
        aggregation_schema_version=AGGREGATION_SCHEMA_VERSION,
        strategy_id=str(strategy_id),
        strategy_version=None if strategy_version is None else str(strategy_version),
        aggregation_sha256=str(counts_and_hash[-1]),
        **counts,
    )


def _build_overall_aggregation(row: tuple[object, ...]) -> ReplayPrizeAggregation:
    counts = {
        name: _decode_int(value)
        for name, value in zip(_AGGREGATE_COUNT_COLUMNS, row[:-1], strict=True)
    }
    return ReplayPrizeAggregation(
        aggregation_schema_version=AGGREGATION_SCHEMA_VERSION,
        strategy_id=None,
        strategy_version=None,
        aggregation_sha256=str(row[-1]),
        **counts,
    )


def _row_to_strategy_aggregate_projection(
    row: tuple[object, ...], run_payload_sha256: str
) -> ReplayStrategyAggregateProjection:
    ordinal, strategy_id, strategy_version, *counts_and_hash = row
    counts = {
        name: _decode_int(value)
        for name, value in zip(_AGGREGATE_COUNT_COLUMNS, counts_and_hash[:-1], strict=True)
    }
    return ReplayStrategyAggregateProjection(
        run_payload_sha256=run_payload_sha256,
        ordinal=_decode_int(ordinal),
        strategy_id=str(strategy_id),
        strategy_version=None if strategy_version is None else str(strategy_version),
        aggregate_sha256=str(counts_and_hash[-1]),
        **counts,
    )


def _row_to_scored_prediction_projection(
    row: tuple[object, ...], run_payload_sha256: str
) -> ReplayScoredPredictionProjection:
    (
        ordinal,
        source_snapshot_result_sha256,
        scored_result_sha256,
        target_draw_number,
        target_draw_date,
        strategy_id,
        strategy_version,
        source_history_status,
        source_history_reason_code,
        source_prediction_status,
        source_prediction_reason_code,
        scoring_status,
        scoring_reason_code,
        predicted_main_numbers_json,
        target_outcome_sha256,
        main_number_hit_count,
        special_number_hit,
        prize_tier_id,
        prize_official_label,
        no_prize_result,
    ) = row
    return ReplayScoredPredictionProjection(
        run_payload_sha256=run_payload_sha256,
        ordinal=_decode_int(ordinal),
        source_snapshot_result_sha256=str(source_snapshot_result_sha256),
        scored_result_sha256=str(scored_result_sha256),
        target_draw_number=str(target_draw_number),
        target_draw_date=str(target_draw_date),
        strategy_id=str(strategy_id),
        strategy_version=None if strategy_version is None else str(strategy_version),
        source_history_status=str(source_history_status),
        source_history_reason_code=(
            None if source_history_reason_code is None else str(source_history_reason_code)
        ),
        source_prediction_status=(
            None if source_prediction_status is None else str(source_prediction_status)
        ),
        source_prediction_reason_code=(
            None
            if source_prediction_reason_code is None
            else str(source_prediction_reason_code)
        ),
        scoring_status=str(scoring_status),
        scoring_reason_code=(
            None if scoring_reason_code is None else str(scoring_reason_code)
        ),
        predicted_main_numbers=(
            None
            if predicted_main_numbers_json is None
            else _decode_json_int_tuple(predicted_main_numbers_json)
        ),
        target_outcome_sha256=(
            None if target_outcome_sha256 is None else str(target_outcome_sha256)
        ),
        main_number_hit_count=(
            None if main_number_hit_count is None else _decode_int(main_number_hit_count)
        ),
        special_number_hit=(
            None if special_number_hit is None else bool(_decode_int(special_number_hit))
        ),
        prize_tier_id=(None if prize_tier_id is None else str(prize_tier_id)),
        prize_official_label=(
            None if prize_official_label is None else str(prize_official_label)
        ),
        no_prize_result=(None if no_prize_result is None else str(no_prize_result)),
    )


def _decode_int(raw: object) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ReplayScoringProjectionTamperError("stored integer column is malformed")
    return raw


def _decode_json_int_tuple(raw: object) -> tuple[int, ...]:
    try:
        parsed: object = json.loads(str(raw))
    except (TypeError, ValueError) as exc:
        raise ReplayScoringProjectionTamperError(
            "stored predicted main numbers are malformed"
        ) from exc
    if not isinstance(parsed, list) or any(
        isinstance(item, bool) or not isinstance(item, int) for item in cast(list[object], parsed)
    ):
        raise ReplayScoringProjectionTamperError("stored predicted main numbers are malformed")
    return tuple(cast(list[int], parsed))


def _verify_available(database: Path) -> bool:
    """Return False for an absent database; raise for a corrupt/incompatible one."""

    try:
        return verify_schema_read_only(database)
    except (ReplayScoringSchemaError, sqlite3.Error) as exc:
        raise ReplayScoringProjectionStorageError(
            "replay-scoring projection storage failed schema verification"
        ) from exc


@contextmanager
def _read_only_connection(database: Path) -> Generator[sqlite3.Connection]:
    try:
        with open_database(database, read_only=True) as connection:
            yield connection
    except (ReplayScoringSchemaError, sqlite3.Error) as exc:
        raise ReplayScoringProjectionStorageError(
            "replay-scoring projection storage is unavailable"
        ) from exc


__all__ = [
    "ReplayScoringProjectionStorageError",
    "ReplayScoringProjectionTamperError",
    "SQLiteReplayScoringProjectionRepository",
]
