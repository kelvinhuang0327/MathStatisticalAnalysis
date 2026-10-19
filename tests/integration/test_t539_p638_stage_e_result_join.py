"""Integration acceptance for T539/P638 Stage E prospective result join."""

from __future__ import annotations

import hashlib
import json
import socket
from datetime import UTC, date, datetime
from pathlib import Path
from typing import NoReturn

import pytest
from tools.t539_p638_stage_c_prediction_seal import (
    compose_t539_p638_stage_c_prediction_seal,
)
from tools.t539_p638_stage_e_result_join import (
    compose_t539_p638_stage_e_result_join,
    open_t539_p638_stage_e_result_join,
)

from lottolab.application.prospective_observer import (
    ProducerFingerprintDriftError,
)
from lottolab.application.prospective_prediction_seal import (
    RunnablePredictionSealStatus,
)
from lottolab.application.prospective_result_join import (
    ProspectiveResultJoinStatus,
)
from lottolab.application.schedule_sync import (
    P638_SCHEDULE_GAME_CODE,
    T539_SCHEDULE_GAME_CODE,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.ingestion import IngestionOperationType, IngestionRunStatus
from lottolab.domain.pre_outcome_target import TargetAnnouncement
from lottolab.domain.prospective_observer import (
    FrozenCohortRef,
    MatchedBaselineRef,
    PredictionContext,
    PredictionDraft,
    PredictionEntryDraft,
    PredictionRecord,
    ProducerDependency,
    ProducerFingerprint,
    ProspectiveObservationIdentity,
    ProspectiveSelection,
    ScoreAvailability,
    TemporalProvenance,
)
from lottolab.infrastructure.persistence.draw_schema import (
    DATA_DIRECTORY_ENV,
    LocalDataPaths,
    initialize_schema,
    open_database,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.future_draw_identity_repository import (
    SQLiteCanonicalScheduleAuthorityRepository,
)
from lottolab.infrastructure.taiwan_lottery_draw_provider import (
    PROVIDER_ID,
    PROVIDER_VERSION,
)
from lottolab.infrastructure.taiwan_lottery_schedule_provider import (
    parse_official_t539_p638_schedule,
)

_NOW = datetime(2099, 1, 1, 8, tzinfo=UTC)
_SCORED_AT = datetime(2099, 1, 2, 22, tzinfo=UTC)
_DRAW_NUMBER = "999999901"
_HISTORY_DRAW_NUMBER = "999999900"
_TARGET_DATE = {
    LotteryType.DAILY_539: date(2099, 1, 2),
    LotteryType.POWER_LOTTO: date(2099, 1, 3),
}
_GAME_CODE = {
    LotteryType.DAILY_539: T539_SCHEDULE_GAME_CODE,
    LotteryType.POWER_LOTTO: P638_SCHEDULE_GAME_CODE,
}


@pytest.fixture(autouse=True)
def _network_is_forbidden(  # pyright: ignore[reportUnusedFunction]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_network(*_args: object, **_kwargs: object) -> NoReturn:
        raise AssertionError("Stage E synthetic acceptance must not access the network")

    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    monkeypatch.setattr(socket, "socket", forbidden_network)


def _sha256(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _paths(root: Path) -> LocalDataPaths:
    paths = resolve_local_data_paths(environ={DATA_DIRECTORY_ENV: str(root)})
    initialize_schema(paths)
    return paths


def _row(
    lottery_type: LotteryType,
    draw_number: str | None = _DRAW_NUMBER,
    *,
    draw_date: date | None = None,
) -> dict[str, object]:
    selected_date = _TARGET_DATE[lottery_type] if draw_date is None else draw_date
    return {
        "drawDate": selected_date.strftime("%Y%m%d"),
        "drawTerm": draw_number,
        "gameCode": _GAME_CODE[lottery_type],
    }


def _fetch(*rows: object):
    body = json.dumps(
        {
            "content": {"nextDrawDateList": list(rows)},
            "fixtureMarker": 0,
            "rtCode": 0,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return parse_official_t539_p638_schedule(
        body,
        observed_at=datetime(2099, 1, 1, 6, tzinfo=UTC),
    )


def _insert_run(
    paths: LocalDataPaths,
    *,
    run_id: str,
    lottery_type: LotteryType,
    requested_start: date,
    requested_end: date,
    fetched_count: int,
) -> None:
    timestamp = "2099-01-01T07:30:00.000000Z"
    with open_database(paths, read_only=False) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO ingestion_runs (
                id, operation_type, status, lottery_type, source_filename,
                source_sha256, parser_version, total_count, inserted_count,
                skipped_count, conflict_count, failed_count, first_draw_number,
                last_draw_number, started_at, completed_at, error_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, NULL, NULL, ?, ?, NULL)
            """,
            (
                run_id,
                IngestionOperationType.MANUAL_SYNC.value,
                IngestionRunStatus.SUCCESS.value,
                lottery_type.value,
                "synthetic-official-sync.json",
                _sha256(run_id),
                "synthetic-parser-v1",
                fetched_count,
                fetched_count,
                timestamp,
                timestamp,
            ),
        )
        connection.execute(
            """
            INSERT INTO ingestion_run_context (
                ingestion_run_id, trigger, provider, provider_version,
                requested_start, requested_end, resolved_start, resolved_end,
                fetched_count
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?)
            """,
            (
                run_id,
                IngestionOperationType.MANUAL_SYNC.value,
                PROVIDER_ID,
                PROVIDER_VERSION,
                requested_start.isoformat(),
                requested_end.isoformat(),
                fetched_count,
            ),
        )
        connection.commit()


def _seed_history_and_presence(
    paths: LocalDataPaths,
    lottery_type: LotteryType,
) -> None:
    suffix = lottery_type.value.lower()
    history_date = date(2099, 1, 1)
    history_run = f"history-{suffix}"
    _insert_run(
        paths,
        run_id=history_run,
        lottery_type=lottery_type,
        requested_start=history_date,
        requested_end=history_date,
        fetched_count=1,
    )
    main = [1, 2, 3, 4, 5] if lottery_type is LotteryType.DAILY_539 else [1, 2, 3, 4, 5, 6]
    special = [] if lottery_type is LotteryType.DAILY_539 else [7]
    with open_database(paths, read_only=False) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO draws (
                lottery_type, draw_number, draw_date, main_numbers_json,
                special_numbers_json, normalized_record_hash, source_name,
                source_reference, ingestion_run_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)
            """,
            (
                lottery_type.value,
                _HISTORY_DRAW_NUMBER,
                history_date.isoformat(),
                json.dumps(main, separators=(",", ":")),
                json.dumps(special, separators=(",", ":")),
                _sha256(f"history-row:{suffix}"),
                "synthetic-history",
                history_run,
                "2099-01-01T07:00:00.000000Z",
                "2099-01-01T07:00:00.000000Z",
            ),
        )
        connection.commit()
    target_date = _TARGET_DATE[lottery_type]
    _insert_run(
        paths,
        run_id=f"presence-{suffix}",
        lottery_type=lottery_type,
        requested_start=target_date,
        requested_end=target_date,
        fetched_count=0,
    )


def _seed_official_outcome_draw(
    paths: LocalDataPaths,
    lottery_type: LotteryType,
    *,
    draw_number: str = _DRAW_NUMBER,
    draw_date: date | None = None,
    main_numbers: tuple[int, ...] | None = None,
    special_numbers: tuple[int, ...] | None = None,
) -> None:
    selected_date = _TARGET_DATE[lottery_type] if draw_date is None else draw_date
    if main_numbers is None:
        main_numbers = (
            (1, 2, 3, 4, 5) if lottery_type is LotteryType.DAILY_539 else (1, 2, 3, 4, 5, 6)
        )
    if special_numbers is None:
        special_numbers = () if lottery_type is LotteryType.DAILY_539 else (2,)
    run_id = f"outcome-run-{lottery_type.value.lower()}"
    _insert_run(
        paths,
        run_id=run_id,
        lottery_type=lottery_type,
        requested_start=selected_date,
        requested_end=selected_date,
        fetched_count=1,
    )
    timestamp = "2099-01-02T21:30:00.000000Z"
    with open_database(paths, read_only=False) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO draws (
                lottery_type, draw_number, draw_date, main_numbers_json,
                special_numbers_json, normalized_record_hash, source_name,
                source_reference, ingestion_run_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)
            """,
            (
                lottery_type.value,
                draw_number,
                selected_date.isoformat(),
                json.dumps(list(main_numbers), separators=(",", ":")),
                json.dumps(list(special_numbers), separators=(",", ":")),
                _sha256(f"outcome-row:{lottery_type.value}:{draw_number}"),
                "synthetic-official-draw",
                run_id,
                timestamp,
                timestamp,
            ),
        )
        connection.commit()


def _cohort(
    lottery_type: LotteryType, member_ids: tuple[str, ...] = ("synthetic-member",)
) -> FrozenCohortRef:
    return FrozenCohortRef(
        lottery_type=lottery_type,
        cohort_id=f"synthetic-stage-e-{lottery_type.value.lower()}",
        cohort_version="v1",
        authority_sha256=_sha256(f"cohort:{lottery_type.value}"),
        frozen_at=datetime(2098, 12, 31, tzinfo=UTC),
        member_ids=member_ids,
        checkpoint_sizes=(1,),
        checkpoint_provenance=(TemporalProvenance.POST_FREEZE_DATE_PROSPECTIVE,),
    )


def _fingerprint(lottery_type: LotteryType) -> ProducerFingerprint:
    return ProducerFingerprint.create(
        producer_id=f"synthetic-stage-e-{lottery_type.value.lower()}",
        producer_version="v1",
        dependencies=(
            ProducerDependency(
                locator=f"fixture://stage-e-producer/{lottery_type.value}",
                source_sha256=_sha256(f"producer:{lottery_type.value}"),
                load_bearing_role="synthetic deterministic prediction behavior",
            ),
        ),
    )


def _available_draft(lottery_type: LotteryType) -> PredictionDraft:
    selection = (
        ProspectiveSelection((1, 2, 3, 4, 5))
        if lottery_type is LotteryType.DAILY_539
        else ProspectiveSelection((1, 2, 3, 4, 5, 6), 2)
    )
    return PredictionDraft(
        (
            PredictionEntryDraft.available(
                member_id="synthetic-member",
                selections=(selection,),
                matched_baseline=MatchedBaselineRef(
                    lottery_type=lottery_type,
                    baseline_id="synthetic-shape-matched-baseline",
                    baseline_version="v1",
                    authority_sha256=_sha256(f"baseline:{lottery_type.value}"),
                    ticket_count=1,
                    candidate_sizes=(len(selection.main_numbers),),
                ),
            ),
        )
    )


def _unavailable_draft() -> PredictionDraft:
    return PredictionDraft(
        (
            PredictionEntryDraft.unavailable(
                member_id="synthetic-member",
                reason="synthetic unavailable prediction",
            ),
        )
    )


class _Producer:
    def __init__(self, draft: PredictionDraft) -> None:
        self._draft = draft

    def predict(self, context: PredictionContext) -> PredictionDraft:
        return self._draft


class _ProducerFactory:
    def __init__(self, draft: PredictionDraft) -> None:
        self._draft = draft

    def __call__(
        self,
        announcement: TargetAnnouncement,
        reference_time: datetime,
    ) -> _Producer:
        return _Producer(self._draft)


def _seed_complete_schedules(paths: LocalDataPaths) -> None:
    SQLiteCanonicalScheduleAuthorityRepository(paths).apply_canonical_schedule_authority(
        _fetch(
            _row(LotteryType.DAILY_539),
            _row(LotteryType.POWER_LOTTO),
        )
    )


def _seal_stage_c(
    paths: LocalDataPaths,
    seal_root: Path,
    lottery_type: LotteryType,
    draft: PredictionDraft,
) -> PredictionRecord:
    comp = compose_t539_p638_stage_c_prediction_seal(
        lottery_type=lottery_type,
        data_directory=paths.data_directory,
        prediction_store_root=seal_root,
        producer_factory=_ProducerFactory(draft),
        cohort=_cohort(lottery_type),
        base_producer_fingerprint=_fingerprint(lottery_type),
        clock=lambda: _NOW,
    )
    res = comp.service.seal_earliest()
    assert res.status is RunnablePredictionSealStatus.CREATED
    assert res.prediction is not None
    return res.prediction


# =============================================================================
# E2E Integration Acceptance
# =============================================================================


def test_t539_and_p638_e2e_stage_e_join_and_replay(tmp_path: Path) -> None:
    paths = _paths(tmp_path / "draw-data")
    _seed_complete_schedules(paths)
    for lottery_type in (LotteryType.DAILY_539, LotteryType.POWER_LOTTO):
        _seed_history_and_presence(paths, lottery_type)
    seal_root = tmp_path / "prediction-seals"

    # Stage C: Seal predictions for both lotteries
    pred_t539 = _seal_stage_c(
        paths, seal_root, LotteryType.DAILY_539, _available_draft(LotteryType.DAILY_539)
    )
    pred_p638 = _seal_stage_c(
        paths, seal_root, LotteryType.POWER_LOTTO, _available_draft(LotteryType.POWER_LOTTO)
    )
    predictions = {LotteryType.DAILY_539: pred_t539, LotteryType.POWER_LOTTO: pred_p638}

    # Seed official outcomes into SQLite database
    _seed_official_outcome_draw(paths, LotteryType.DAILY_539)
    _seed_official_outcome_draw(paths, LotteryType.POWER_LOTTO)

    # Stage E: Exact result join
    for lottery_type in (LotteryType.DAILY_539, LotteryType.POWER_LOTTO):
        with open_t539_p638_stage_e_result_join(
            lottery_type=lottery_type,
            data_directory=paths.data_directory,
            prediction_store_root=seal_root,
            clock=lambda: _SCORED_AT,
        ) as comp:
            prediction = predictions[lottery_type]
            join_result = comp.service.join_prediction(prediction)
            assert join_result.status is ProspectiveResultJoinStatus.CREATED
            assert join_result.score is not None
            assert join_result.outcome is not None
            assert join_result.score.prediction_hash == prediction.prediction_hash
            assert join_result.score.outcome.outcome_hash == join_result.outcome.outcome_hash
            assert join_result.score.entries[0].availability is ScoreAvailability.SCORED
            assert join_result.score.entries[0].evaluation is not None
            assert join_result.score.entries[0].evaluation.is_winner is True

    # Exact replay / idempotency check
    for lottery_type in (LotteryType.DAILY_539, LotteryType.POWER_LOTTO):
        with open_t539_p638_stage_e_result_join(
            lottery_type=lottery_type,
            data_directory=paths.data_directory,
            prediction_store_root=seal_root,
            clock=lambda: _SCORED_AT,
        ) as comp:
            prediction = predictions[lottery_type]
            replay_result = comp.service.join_prediction(prediction)
            assert replay_result.status is ProspectiveResultJoinStatus.EXACT_IDEMPOTENT_NO_OP
            assert replay_result.score is not None


def test_unavailable_prediction_e2e_join(tmp_path: Path) -> None:
    paths = _paths(tmp_path / "draw-data")
    _seed_complete_schedules(paths)
    _seed_history_and_presence(paths, LotteryType.DAILY_539)
    seal_root = tmp_path / "prediction-seals"

    # Stage C: Seal unavailable prediction
    prediction = _seal_stage_c(paths, seal_root, LotteryType.DAILY_539, _unavailable_draft())

    # Seed official draw
    _seed_official_outcome_draw(paths, LotteryType.DAILY_539)

    # Stage E: Exact join
    with open_t539_p638_stage_e_result_join(
        lottery_type=LotteryType.DAILY_539,
        data_directory=paths.data_directory,
        prediction_store_root=seal_root,
        clock=lambda: _SCORED_AT,
    ) as comp:
        result = comp.service.join_prediction(prediction)

        assert result.status is ProspectiveResultJoinStatus.CREATED
        assert result.score is not None
        assert result.score.entries[0].availability is ScoreAvailability.UNAVAILABLE_PREDICTION
        assert result.score.entries[0].evaluation is None


def test_identity_mismatch_and_conflict_rejection(tmp_path: Path) -> None:
    paths = _paths(tmp_path / "draw-data")
    _seed_complete_schedules(paths)
    _seed_history_and_presence(paths, LotteryType.DAILY_539)
    seal_root = tmp_path / "prediction-seals"

    # Stage C: Seal prediction
    prediction = _seal_stage_c(
        paths, seal_root, LotteryType.DAILY_539, _available_draft(LotteryType.DAILY_539)
    )

    # 1. Official draw not in database yet -> OUTCOME_UNAVAILABLE
    with open_t539_p638_stage_e_result_join(
        lottery_type=LotteryType.DAILY_539,
        data_directory=paths.data_directory,
        prediction_store_root=seal_root,
        clock=lambda: _SCORED_AT,
    ) as comp:
        result = comp.service.join_prediction(prediction)
        assert result.status is ProspectiveResultJoinStatus.OUTCOME_UNAVAILABLE
        assert result.score is None

    # 2. Seed matching official draw
    _seed_official_outcome_draw(
        paths,
        LotteryType.DAILY_539,
    )

    # 3. Mismatched draw date on identity query fails closed
    mismatched_identity = ProspectiveObservationIdentity(
        lottery_type=LotteryType.DAILY_539,
        cohort_id=prediction.identity.cohort_id,
        cohort_version=prediction.identity.cohort_version,
        target_draw_number=prediction.identity.target_draw_number,
        target_draw_date=date(2099, 1, 4),  # Mismatched date
    )
    with open_t539_p638_stage_e_result_join(
        lottery_type=LotteryType.DAILY_539,
        data_directory=paths.data_directory,
        prediction_store_root=seal_root,
        clock=lambda: _SCORED_AT,
    ) as comp:
        # Prediction for mismatched identity does not exist
        from lottolab.application.prospective_observer import PredictionRequiredError

        with pytest.raises(PredictionRequiredError, match="score requires an immutable prediction"):
            comp.service.join_result(mismatched_identity, prediction.producer_fingerprint)

    # 4. Drifted producer fingerprint fails closed
    drifted_fingerprint = ProducerFingerprint.create(
        producer_id=prediction.producer_fingerprint.producer_id,
        producer_version="v2-drifted",
        dependencies=prediction.producer_fingerprint.dependencies,
    )
    with (
        open_t539_p638_stage_e_result_join(
            lottery_type=LotteryType.DAILY_539,
            data_directory=paths.data_directory,
            prediction_store_root=seal_root,
            clock=lambda: _SCORED_AT,
        ) as comp,
        pytest.raises(
            ProducerFingerprintDriftError,
            match="producer fingerprint differs from immutable prediction authority",
        ),
    ):
        comp.service.join_result(prediction.identity, drifted_fingerprint)


def test_stage_e_rejects_b649_composition(tmp_path: Path) -> None:
    paths = _paths(tmp_path / "draw-data")
    seal_root = tmp_path / "prediction-seals"

    with (
        open_database(paths, read_only=True) as connection,
        pytest.raises(
            ValueError, match="Stage E composition supports only DAILY_539 and POWER_LOTTO"
        ),
    ):
        compose_t539_p638_stage_e_result_join(
            lottery_type=LotteryType.BIG_LOTTO,
            data_directory=paths.data_directory,
            prediction_store_root=seal_root,
            connection=connection,
        )
