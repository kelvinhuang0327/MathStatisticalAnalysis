"""Deterministic standalone fixture rehearsal runner for T539/P638 Stage A -> C -> E pipeline.

Executes all 14 fixture rehearsal scenarios in a dedicated runtime root:
/Users/kelvin/LottoLab-TaskData/T539_P638_STAGE_A_C_E_INTEGRATION_R1

Ensures:
- Strict zero-network enforcement.
- Strict storage guard / no .git ancestor compliance.
- Complete execution of all 14 matrix scenarios.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import socket
from datetime import UTC, date, datetime
from pathlib import Path
from typing import NoReturn

from lottolab.application.draw_data import DrawRecord
from lottolab.application.prospective_observer import (
    GameContractError,
    PredictionConflictError,
    ProducerFingerprintDriftError,
    ScoreConflictError,
    ScorePhaseRequest,
)
from lottolab.application.prospective_prediction_seal import (
    RunnablePredictionSealResult,
    RunnablePredictionSealStatus,
)
from lottolab.application.prospective_result_join import (
    ProspectiveResultJoinService,
    ProspectiveResultJoinStatus,
)
from lottolab.application.schedule_sync import (
    P638_SCHEDULE_GAME_CODE,
    T539_SCHEDULE_GAME_CODE,
    AuthoritativeScheduleVeto,
    ScheduleExceptionKind,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.ingestion import IngestionOperationType, IngestionRunStatus
from lottolab.domain.pre_outcome_target import TargetAnnouncement, TargetSourceProvenance
from lottolab.domain.prospective_observer import (
    FrozenCohortRef,
    MatchedBaselineRef,
    OfficialOutcome,
    PredictionContext,
    PredictionDraft,
    PredictionEntryDraft,
    ProducerDependency,
    ProducerFingerprint,
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
    SQLiteFutureDrawIdentityReader,
)
from lottolab.infrastructure.taiwan_lottery_draw_provider import (
    PROVIDER_ID,
    PROVIDER_VERSION,
)
from lottolab.infrastructure.taiwan_lottery_schedule_provider import (
    parse_official_t539_p638_schedule,
)
from tools.t539_p638_stage_c_prediction_seal import (
    compose_t539_p638_stage_c_prediction_seal,
)
from tools.t539_p638_stage_e_result_join import (
    open_t539_p638_stage_e_result_join,
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


def _block_network() -> None:
    def forbidden_network(*_args: object, **_kwargs: object) -> NoReturn:
        raise AssertionError("Combined fixture rehearsal must not access network")

    socket.create_connection = forbidden_network  # type: ignore[assignment]
    socket.socket = forbidden_network  # type: ignore[misc]


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


def _fetch(
    *rows: object,
    marker: int = 0,
    active_vetoes: tuple[AuthoritativeScheduleVeto, ...] = (),
):
    body = json.dumps(
        {
            "content": {"nextDrawDateList": list(rows)},
            "fixtureMarker": marker,
            "rtCode": 0,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return parse_official_t539_p638_schedule(
        body,
        observed_at=datetime(2099, 1, 1, 6, tzinfo=UTC),
        active_vetoes=active_vetoes,
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


def _cohort(lottery_type: LotteryType) -> FrozenCohortRef:
    return FrozenCohortRef(
        lottery_type=lottery_type,
        cohort_id=f"rehearsal-cohort-{lottery_type.value.lower()}",
        cohort_version="v1",
        authority_sha256=_sha256(f"cohort:{lottery_type.value}"),
        frozen_at=datetime(2098, 12, 31, tzinfo=UTC),
        member_ids=("synthetic-member",),
        checkpoint_sizes=(1,),
        checkpoint_provenance=(TemporalProvenance.POST_FREEZE_DATE_PROSPECTIVE,),
    )


def _fingerprint(lottery_type: LotteryType) -> ProducerFingerprint:
    return ProducerFingerprint.create(
        producer_id=f"rehearsal-producer-{lottery_type.value.lower()}",
        producer_version="v1",
        dependencies=(
            ProducerDependency(
                locator=f"fixture://rehearsal-producer/{lottery_type.value}",
                source_sha256=_sha256(f"producer:{lottery_type.value}"),
                load_bearing_role="rehearsal deterministic prediction behavior",
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
                    baseline_id="rehearsal-shape-matched-baseline",
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
                reason="rehearsal unavailable prediction test",
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
        self.calls: list[tuple[TargetAnnouncement, datetime]] = []

    def __call__(
        self,
        announcement: TargetAnnouncement,
        reference_time: datetime,
    ) -> _Producer:
        self.calls.append((announcement, reference_time))
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
    *,
    now: datetime = _NOW,
) -> RunnablePredictionSealResult:
    comp = compose_t539_p638_stage_c_prediction_seal(
        lottery_type=lottery_type,
        data_directory=paths.data_directory,
        prediction_store_root=seal_root,
        producer_factory=_ProducerFactory(draft),
        cohort=_cohort(lottery_type),
        base_producer_fingerprint=_fingerprint(lottery_type),
        clock=lambda: now,
    )
    return comp.service.seal_earliest()


def _veto(lottery_type: LotteryType) -> AuthoritativeScheduleVeto:
    return AuthoritativeScheduleVeto(
        lottery_type=lottery_type,
        official_game_code=_GAME_CODE[lottery_type],
        draw_number=_DRAW_NUMBER,
        exception_kind=ScheduleExceptionKind.CANCELLATION,
        source=TargetSourceProvenance(
            source_id="TAIWAN_LOTTERY_OFFICIAL_EXCEPTION_NOTICE",
            source_version="synthetic-v1",
            source_locator=f"https://www.taiwanlottery.com/announcement/{_DRAW_NUMBER}",
            source_sha256=_sha256(f"veto:{lottery_type.value}"),
            observed_at=datetime(2099, 1, 1, 7, tzinfo=UTC),
        ),
    )


def run_full_fixture_rehearsal(runtime_root: Path) -> dict[str, str]:
    """Run all 14 combined fixture rehearsal scenarios in the isolated runtime root."""
    results: dict[str, str] = {}

    # Verify runtime root has no .git ancestor
    for parent in (runtime_root, *runtime_root.parents):
        if (parent / ".git").exists():
            raise RuntimeError(f"Runtime root contains .git ancestor: {parent}")

    if runtime_root.exists():
        shutil.rmtree(runtime_root)
    runtime_root.mkdir(parents=True, exist_ok=True)

    # 1. T539 successful flow
    s1_dir = runtime_root / "scenario_01"
    paths_1 = _paths(s1_dir / "draw-data")
    seal_1 = s1_dir / "prediction-seals"
    _seed_complete_schedules(paths_1)
    _seed_history_and_presence(paths_1, LotteryType.DAILY_539)
    seal_res_1 = _seal_stage_c(
        paths_1, seal_1, LotteryType.DAILY_539, _available_draft(LotteryType.DAILY_539)
    )
    assert seal_res_1.status is RunnablePredictionSealStatus.CREATED
    assert seal_res_1.prediction is not None
    _seed_official_outcome_draw(paths_1, LotteryType.DAILY_539)
    with open_t539_p638_stage_e_result_join(
        lottery_type=LotteryType.DAILY_539,
        data_directory=paths_1.data_directory,
        prediction_store_root=seal_1,
        clock=lambda: _SCORED_AT,
    ) as comp:
        join_res_1 = comp.service.join_prediction(seal_res_1.prediction)
        assert join_res_1.status is ProspectiveResultJoinStatus.CREATED
        assert join_res_1.score is not None
        assert join_res_1.score.entries[0].availability is ScoreAvailability.SCORED
    results["01_t539_successful_flow"] = "PASS"

    # 2. P638 successful flow
    s2_dir = runtime_root / "scenario_02"
    paths_2 = _paths(s2_dir / "draw-data")
    seal_2 = s2_dir / "prediction-seals"
    _seed_complete_schedules(paths_2)
    _seed_history_and_presence(paths_2, LotteryType.POWER_LOTTO)
    seal_res_2 = _seal_stage_c(
        paths_2, seal_2, LotteryType.POWER_LOTTO, _available_draft(LotteryType.POWER_LOTTO)
    )
    assert seal_res_2.status is RunnablePredictionSealStatus.CREATED
    assert seal_res_2.prediction is not None
    _seed_official_outcome_draw(paths_2, LotteryType.POWER_LOTTO)
    with open_t539_p638_stage_e_result_join(
        lottery_type=LotteryType.POWER_LOTTO,
        data_directory=paths_2.data_directory,
        prediction_store_root=seal_2,
        clock=lambda: _SCORED_AT,
    ) as comp:
        join_res_2 = comp.service.join_prediction(seal_res_2.prediction)
        assert join_res_2.status is ProspectiveResultJoinStatus.CREATED
        assert join_res_2.score is not None
        assert join_res_2.score.entries[0].availability is ScoreAvailability.SCORED
    results["02_p638_successful_flow"] = "PASS"

    # 3. unavailable prediction
    s3_dir = runtime_root / "scenario_03"
    paths_3 = _paths(s3_dir / "draw-data")
    seal_3 = s3_dir / "prediction-seals"
    _seed_complete_schedules(paths_3)
    _seed_history_and_presence(paths_3, LotteryType.DAILY_539)
    seal_res_3 = _seal_stage_c(paths_3, seal_3, LotteryType.DAILY_539, _unavailable_draft())
    assert seal_res_3.status is RunnablePredictionSealStatus.CREATED
    assert seal_res_3.prediction is not None
    _seed_official_outcome_draw(paths_3, LotteryType.DAILY_539)
    with open_t539_p638_stage_e_result_join(
        lottery_type=LotteryType.DAILY_539,
        data_directory=paths_3.data_directory,
        prediction_store_root=seal_3,
        clock=lambda: _SCORED_AT,
    ) as comp:
        join_res_3 = comp.service.join_prediction(seal_res_3.prediction)
        assert join_res_3.status is ProspectiveResultJoinStatus.CREATED
        assert (
            join_res_3.score is not None
            and join_res_3.score.entries[0].availability
            is ScoreAvailability.UNAVAILABLE_PREDICTION
        )
    results["03_unavailable_prediction"] = "PASS"

    # 4. cancelled target
    s4_dir = runtime_root / "scenario_04"
    paths_4 = _paths(s4_dir / "draw-data")
    seal_4 = s4_dir / "prediction-seals"
    SQLiteCanonicalScheduleAuthorityRepository(paths_4).apply_canonical_schedule_authority(
        _fetch(
            _row(LotteryType.DAILY_539),
            _row(LotteryType.POWER_LOTTO),
            active_vetoes=(_veto(LotteryType.DAILY_539),),
        )
    )
    _seed_history_and_presence(paths_4, LotteryType.DAILY_539)
    factory_4 = _ProducerFactory(_available_draft(LotteryType.DAILY_539))
    comp_4 = compose_t539_p638_stage_c_prediction_seal(
        lottery_type=LotteryType.DAILY_539,
        data_directory=paths_4.data_directory,
        prediction_store_root=seal_4,
        producer_factory=factory_4,
        cohort=_cohort(LotteryType.DAILY_539),
        base_producer_fingerprint=_fingerprint(LotteryType.DAILY_539),
        clock=lambda: _NOW,
    )
    res_4 = comp_4.service.seal_earliest()
    assert res_4.status is RunnablePredictionSealStatus.NO_RUNNABLE_TARGET
    assert factory_4.calls == []
    results["04_cancelled_target"] = "PASS"

    # 5. conflicted target
    s5_dir = runtime_root / "scenario_05"
    paths_5 = _paths(s5_dir / "draw-data")
    seal_5 = s5_dir / "prediction-seals"
    _seed_complete_schedules(paths_5)
    SQLiteCanonicalScheduleAuthorityRepository(paths_5).apply_canonical_schedule_authority(
        _fetch(
            _row(LotteryType.DAILY_539, draw_date=date(2099, 1, 4)),
            _row(LotteryType.POWER_LOTTO),
            marker=1,
        )
    )
    _seed_history_and_presence(paths_5, LotteryType.DAILY_539)
    factory_5 = _ProducerFactory(_available_draft(LotteryType.DAILY_539))
    comp_5 = compose_t539_p638_stage_c_prediction_seal(
        lottery_type=LotteryType.DAILY_539,
        data_directory=paths_5.data_directory,
        prediction_store_root=seal_5,
        producer_factory=factory_5,
        cohort=_cohort(LotteryType.DAILY_539),
        base_producer_fingerprint=_fingerprint(LotteryType.DAILY_539),
        clock=lambda: _NOW,
    )
    res_5 = comp_5.service.seal_earliest()
    assert res_5.status is RunnablePredictionSealStatus.NO_RUNNABLE_TARGET
    assert factory_5.calls == []
    results["05_conflicted_target"] = "PASS"

    # 6. late target
    s6_dir = runtime_root / "scenario_06"
    paths_6 = _paths(s6_dir / "draw-data")
    seal_6 = s6_dir / "prediction-seals"
    _seed_complete_schedules(paths_6)
    _seed_history_and_presence(paths_6, LotteryType.DAILY_539)
    target_rec_6 = SQLiteFutureDrawIdentityReader(paths_6).get_scheduled_draw(
        LotteryType.DAILY_539, _DRAW_NUMBER
    )
    assert target_rec_6 is not None
    factory_6 = _ProducerFactory(_available_draft(LotteryType.DAILY_539))
    comp_6 = compose_t539_p638_stage_c_prediction_seal(
        lottery_type=LotteryType.DAILY_539,
        data_directory=paths_6.data_directory,
        prediction_store_root=seal_6,
        producer_factory=factory_6,
        cohort=_cohort(LotteryType.DAILY_539),
        base_producer_fingerprint=_fingerprint(LotteryType.DAILY_539),
        clock=lambda: target_rec_6.announcement.scheduled_at,
    )
    res_6 = comp_6.service.seal_earliest()
    assert res_6.status is RunnablePredictionSealStatus.NO_RUNNABLE_TARGET
    assert factory_6.calls == []
    results["06_late_target"] = "PASS"

    # 7. wrong lottery
    s7_dir = runtime_root / "scenario_07"
    paths_7 = _paths(s7_dir / "draw-data")
    seal_7 = s7_dir / "prediction-seals"
    _seed_complete_schedules(paths_7)
    _seed_history_and_presence(paths_7, LotteryType.DAILY_539)
    pred_7 = _seal_stage_c(
        paths_7, seal_7, LotteryType.DAILY_539, _available_draft(LotteryType.DAILY_539)
    ).prediction
    assert pred_7 is not None
    _seed_official_outcome_draw(paths_7, LotteryType.DAILY_539)
    try:
        with open_t539_p638_stage_e_result_join(
            lottery_type=LotteryType.POWER_LOTTO,
            data_directory=paths_7.data_directory,
            prediction_store_root=seal_7,
            clock=lambda: _SCORED_AT,
        ) as comp:
            comp.service.join_prediction(pred_7)
        raise AssertionError("wrong lottery should have raised GameContractError")
    except GameContractError:
        pass
    results["07_wrong_lottery"] = "PASS"

    # 8. wrong draw number
    s8_dir = runtime_root / "scenario_08"
    paths_8 = _paths(s8_dir / "draw-data")
    seal_8 = s8_dir / "prediction-seals"
    _seed_complete_schedules(paths_8)
    _seed_history_and_presence(paths_8, LotteryType.DAILY_539)
    pred_8 = _seal_stage_c(
        paths_8, seal_8, LotteryType.DAILY_539, _available_draft(LotteryType.DAILY_539)
    ).prediction
    assert pred_8 is not None
    _seed_official_outcome_draw(paths_8, LotteryType.DAILY_539, draw_number="999999902")
    with open_t539_p638_stage_e_result_join(
        lottery_type=LotteryType.DAILY_539,
        data_directory=paths_8.data_directory,
        prediction_store_root=seal_8,
        clock=lambda: _SCORED_AT,
    ) as comp:
        join_res_8 = comp.service.join_prediction(pred_8)
        assert join_res_8.status is ProspectiveResultJoinStatus.OUTCOME_UNAVAILABLE
    results["08_wrong_draw_number"] = "PASS"

    # 9. wrong draw date
    s9_dir = runtime_root / "scenario_09"
    paths_9 = _paths(s9_dir / "draw-data")
    seal_9 = s9_dir / "prediction-seals"
    _seed_complete_schedules(paths_9)
    _seed_history_and_presence(paths_9, LotteryType.DAILY_539)
    pred_9 = _seal_stage_c(
        paths_9, seal_9, LotteryType.DAILY_539, _available_draft(LotteryType.DAILY_539)
    ).prediction
    assert pred_9 is not None

    class MismatchedDateDrawReader:
        def find(self, lottery_type: LotteryType, draw_number: str) -> DrawRecord | None:
            return DrawRecord(
                internal_id=1,
                lottery_type=lottery_type,
                draw_number=draw_number,
                draw_date=date(2099, 1, 5),
                main_numbers=(1, 2, 3, 4, 5),
                special_numbers=(),
                normalized_record_hash=_sha256("mismatched-draw"),
                source_name="synthetic-draw",
                source_reference="run-001",
                ingestion_run_id="run-001",
                created_at=_SCORED_AT,
                updated_at=_SCORED_AT,
            )

    with open_t539_p638_stage_e_result_join(
        lottery_type=LotteryType.DAILY_539,
        data_directory=paths_9.data_directory,
        prediction_store_root=seal_9,
        clock=lambda: _SCORED_AT,
    ) as comp:
        svc_mismatch = ProspectiveResultJoinService(
            draw_reader=MismatchedDateDrawReader(),
            scoring_service=comp.scoring_service,
            store=comp.prediction_store,
        )
        try:
            svc_mismatch.join_prediction(pred_9)
            raise AssertionError("wrong draw date should have raised GameContractError")
        except GameContractError:
            pass
    results["09_wrong_draw_date"] = "PASS"

    # 10. changed Stage A digest
    s10_dir = runtime_root / "scenario_10"
    paths_10 = _paths(s10_dir / "draw-data")
    seal_10 = s10_dir / "prediction-seals"
    _seed_complete_schedules(paths_10)
    _seed_history_and_presence(paths_10, LotteryType.DAILY_539)
    pred_10 = _seal_stage_c(
        paths_10, seal_10, LotteryType.DAILY_539, _available_draft(LotteryType.DAILY_539)
    ).prediction
    assert pred_10 is not None
    _seed_official_outcome_draw(paths_10, LotteryType.DAILY_539)
    corrupted_deps = tuple(
        ProducerDependency(
            locator=dep.locator,
            source_sha256=_sha256("tampered-digest"),
            load_bearing_role=dep.load_bearing_role,
        )
        for dep in pred_10.producer_fingerprint.dependencies
    )
    drifted_fp = ProducerFingerprint.create(
        producer_id=pred_10.producer_fingerprint.producer_id,
        producer_version=pred_10.producer_fingerprint.producer_version,
        dependencies=corrupted_deps,
    )
    with open_t539_p638_stage_e_result_join(
        lottery_type=LotteryType.DAILY_539,
        data_directory=paths_10.data_directory,
        prediction_store_root=seal_10,
        clock=lambda: _SCORED_AT,
    ) as comp:
        try:
            comp.service.join_result(pred_10.identity, drifted_fp)
            raise AssertionError(
                "drifted fingerprint should have raised ProducerFingerprintDriftError"
            )
        except ProducerFingerprintDriftError:
            pass
    results["10_changed_stage_a_digest"] = "PASS"

    # 11. prediction conflict
    s11_dir = runtime_root / "scenario_11"
    paths_11 = _paths(s11_dir / "draw-data")
    seal_11 = s11_dir / "prediction-seals"
    _seed_complete_schedules(paths_11)
    _seed_history_and_presence(paths_11, LotteryType.DAILY_539)
    _seal_stage_c(
        paths_11, seal_11, LotteryType.DAILY_539, _available_draft(LotteryType.DAILY_539)
    )
    conflicting_draft = PredictionDraft(
        (
            PredictionEntryDraft.available(
                member_id="synthetic-member",
                selections=(ProspectiveSelection((6, 7, 8, 9, 10)),),
                matched_baseline=MatchedBaselineRef(
                    lottery_type=LotteryType.DAILY_539,
                    baseline_id="rehearsal-baseline",
                    baseline_version="v1",
                    authority_sha256=_sha256("baseline:DAILY_539"),
                    ticket_count=1,
                    candidate_sizes=(5,),
                ),
            ),
        )
    )
    comp_11 = compose_t539_p638_stage_c_prediction_seal(
        lottery_type=LotteryType.DAILY_539,
        data_directory=paths_11.data_directory,
        prediction_store_root=seal_11,
        producer_factory=_ProducerFactory(conflicting_draft),
        cohort=_cohort(LotteryType.DAILY_539),
        base_producer_fingerprint=_fingerprint(LotteryType.DAILY_539),
        clock=lambda: _NOW,
    )
    try:
        comp_11.service.seal_earliest()
        raise AssertionError("prediction conflict should have raised PredictionConflictError")
    except PredictionConflictError:
        pass
    results["11_prediction_conflict"] = "PASS"

    # 12. outcome conflict
    s12_dir = runtime_root / "scenario_12"
    paths_12 = _paths(s12_dir / "draw-data")
    seal_12 = s12_dir / "prediction-seals"
    _seed_complete_schedules(paths_12)
    _seed_history_and_presence(paths_12, LotteryType.DAILY_539)
    pred_12 = _seal_stage_c(
        paths_12, seal_12, LotteryType.DAILY_539, _available_draft(LotteryType.DAILY_539)
    ).prediction
    assert pred_12 is not None
    _seed_official_outcome_draw(paths_12, LotteryType.DAILY_539, main_numbers=(1, 2, 3, 4, 5))
    with open_t539_p638_stage_e_result_join(
        lottery_type=LotteryType.DAILY_539,
        data_directory=paths_12.data_directory,
        prediction_store_root=seal_12,
        clock=lambda: _SCORED_AT,
    ) as comp:
        comp.service.join_prediction(pred_12)
    conflicting_outcome = OfficialOutcome.create(
        lottery_type=LotteryType.DAILY_539,
        draw_number=_DRAW_NUMBER,
        draw_date=_TARGET_DATE[LotteryType.DAILY_539],
        main_numbers=(10, 11, 12, 13, 14),
        special_number=None,
        source_id="conflicting-source",
        source_sha256=_sha256("conflicting-source"),
    )
    with open_t539_p638_stage_e_result_join(
        lottery_type=LotteryType.DAILY_539,
        data_directory=paths_12.data_directory,
        prediction_store_root=seal_12,
        clock=lambda: _SCORED_AT,
    ) as comp:
        try:
            comp.scoring_service.sync(
                ScorePhaseRequest(
                    identity=pred_12.identity,
                    producer_fingerprint=pred_12.producer_fingerprint,
                    outcome=conflicting_outcome,
                )
            )
            raise AssertionError("outcome conflict should have raised ScoreConflictError")
        except ScoreConflictError:
            pass
    results["12_outcome_conflict"] = "PASS"

    # 13. exact replay
    s13_dir = runtime_root / "scenario_13"
    paths_13 = _paths(s13_dir / "draw-data")
    seal_13 = s13_dir / "prediction-seals"
    _seed_complete_schedules(paths_13)
    for lt in (LotteryType.DAILY_539, LotteryType.POWER_LOTTO):
        _seed_history_and_presence(paths_13, lt)
    pred_13_t539 = _seal_stage_c(
        paths_13, seal_13, LotteryType.DAILY_539, _available_draft(LotteryType.DAILY_539)
    ).prediction
    pred_13_p638 = _seal_stage_c(
        paths_13, seal_13, LotteryType.POWER_LOTTO, _available_draft(LotteryType.POWER_LOTTO)
    ).prediction
    assert pred_13_t539 is not None and pred_13_p638 is not None
    _seed_official_outcome_draw(paths_13, LotteryType.DAILY_539)
    _seed_official_outcome_draw(paths_13, LotteryType.POWER_LOTTO)
    scores_13 = {}
    test_pairs = (
        (LotteryType.DAILY_539, pred_13_t539),
        (LotteryType.POWER_LOTTO, pred_13_p638),
    )
    for lt, pred in test_pairs:
        with open_t539_p638_stage_e_result_join(
            lottery_type=lt,
            data_directory=paths_13.data_directory,
            prediction_store_root=seal_13,
            clock=lambda: _SCORED_AT,
        ) as comp:
            res_e = comp.service.join_prediction(pred)
            assert res_e.status is ProspectiveResultJoinStatus.CREATED
            scores_13[lt] = res_e.score
    files_before = {
        p.relative_to(s13_dir): p.read_bytes() for p in s13_dir.rglob("*") if p.is_file()
    }
    for _ in range(2):
        for lt, pred in test_pairs:
            with open_t539_p638_stage_e_result_join(
                lottery_type=lt,
                data_directory=paths_13.data_directory,
                prediction_store_root=seal_13,
                clock=lambda: _SCORED_AT,
            ) as comp:
                replay_res = comp.service.join_prediction(pred)
                assert replay_res.status is ProspectiveResultJoinStatus.EXACT_IDEMPOTENT_NO_OP
                assert replay_res.score == scores_13[lt]
    files_after = {
        p.relative_to(s13_dir): p.read_bytes() for p in s13_dir.rglob("*") if p.is_file()
    }
    assert files_after == files_before
    results["13_exact_replay"] = "PASS"

    # 14. cross-game isolation
    s14_dir = runtime_root / "scenario_14"
    paths_14 = _paths(s14_dir / "draw-data")
    seal_14 = s14_dir / "prediction-seals"
    SQLiteCanonicalScheduleAuthorityRepository(paths_14).apply_canonical_schedule_authority(
        _fetch(
            _row(LotteryType.DAILY_539),
            _row(LotteryType.POWER_LOTTO),
            active_vetoes=(_veto(LotteryType.DAILY_539),),
        )
    )
    _seed_history_and_presence(paths_14, LotteryType.DAILY_539)
    _seed_history_and_presence(paths_14, LotteryType.POWER_LOTTO)
    t539_fact = _ProducerFactory(_available_draft(LotteryType.DAILY_539))
    comp_t539_14 = compose_t539_p638_stage_c_prediction_seal(
        lottery_type=LotteryType.DAILY_539,
        data_directory=paths_14.data_directory,
        prediction_store_root=seal_14,
        producer_factory=t539_fact,
        cohort=_cohort(LotteryType.DAILY_539),
        base_producer_fingerprint=_fingerprint(LotteryType.DAILY_539),
        clock=lambda: _NOW,
    )
    res_seal_14 = comp_t539_14.service.seal_earliest()
    assert res_seal_14.status is RunnablePredictionSealStatus.NO_RUNNABLE_TARGET
    p638_fact = _ProducerFactory(_available_draft(LotteryType.POWER_LOTTO))
    comp_p638_14 = compose_t539_p638_stage_c_prediction_seal(
        lottery_type=LotteryType.POWER_LOTTO,
        data_directory=paths_14.data_directory,
        prediction_store_root=seal_14,
        producer_factory=p638_fact,
        cohort=_cohort(LotteryType.POWER_LOTTO),
        base_producer_fingerprint=_fingerprint(LotteryType.POWER_LOTTO),
        clock=lambda: _NOW,
    )
    res_p638_14 = comp_p638_14.service.seal_earliest()
    assert res_p638_14.status is RunnablePredictionSealStatus.CREATED
    assert res_p638_14.prediction is not None
    _seed_official_outcome_draw(paths_14, LotteryType.POWER_LOTTO)
    with open_t539_p638_stage_e_result_join(
        lottery_type=LotteryType.POWER_LOTTO,
        data_directory=paths_14.data_directory,
        prediction_store_root=seal_14,
        clock=lambda: _SCORED_AT,
    ) as comp:
        res_j = comp.service.join_prediction(res_p638_14.prediction)
        assert res_j.status is ProspectiveResultJoinStatus.CREATED
    assert not (seal_14 / "daily_539").exists()
    assert (seal_14 / "power_lotto").exists()
    results["14_cross_game_isolation"] = "PASS"

    return results


def main() -> None:
    _block_network()
    target_root = Path("/Users/kelvin/LottoLab-TaskData/T539_P638_STAGE_A_C_E_INTEGRATION_R1")
    print(f"Running Stage A-C-E combined fixture rehearsal in {target_root}...")
    results = run_full_fixture_rehearsal(target_root)
    print("Combined Fixture Rehearsal Results:")
    for scenario, status in sorted(results.items()):
        print(f"  {scenario}: {status}")
    assert len(results) == 14
    assert all(status == "PASS" for status in results.values())
    print("\nALL 14 COMBINED FIXTURE REHEARSAL SCENARIOS PASSED SUCCESSFULLY.")


if __name__ == "__main__":
    main()
