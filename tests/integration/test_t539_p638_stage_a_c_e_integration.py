"""Combined end-to-end integration acceptance and fixture rehearsal for Stage A -> C -> E.

Validates the full prospective pipeline lineage across DAILY_539 and POWER_LOTTO:
Stage A schedule authority -> runnable target gate -> Stage C immutable prediction seal
-> Stage E exact official-result join / score -> durable ScoreRecord -> exact replay.

Guarantees:
- Strict zero-network enforcement.
- Strict storage guard / no .git ancestor compliance.
- Complete 14-case matrix coverage:
  1. T539 successful flow
  2. P638 successful flow
  3. unavailable prediction
  4. cancelled target
  5. conflicted target
  6. late target
  7. wrong lottery
  8. wrong draw number
  9. wrong draw date
  10. changed Stage A digest
  11. prediction conflict
  12. outcome conflict
  13. exact replay
  14. cross-game isolation
"""

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
    open_t539_p638_stage_e_result_join,
)

from lottolab.application.draw_data import DrawRecord
from lottolab.application.pre_outcome_target_operational import (
    OperationalRegistrationStatus,
)
from lottolab.application.prospective_observer import (
    GameContractError,
    ProducerFingerprintDriftError,
    ScoreConflictError,
)
from lottolab.application.prospective_prediction_seal import (
    SCHEDULE_AUTHORITY_LOAD_BEARING_ROLE,
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
        raise AssertionError("Stage A-C-E combined rehearsal must not access network")

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
        cohort_id=f"synthetic-ace-{lottery_type.value.lower()}",
        cohort_version="v1",
        authority_sha256=_sha256(f"cohort:{lottery_type.value}"),
        frozen_at=datetime(2098, 12, 31, tzinfo=UTC),
        member_ids=("synthetic-member",),
        checkpoint_sizes=(1,),
        checkpoint_provenance=(TemporalProvenance.POST_FREEZE_DATE_PROSPECTIVE,),
    )


def _fingerprint(lottery_type: LotteryType) -> ProducerFingerprint:
    return ProducerFingerprint.create(
        producer_id=f"synthetic-ace-{lottery_type.value.lower()}",
        producer_version="v1",
        dependencies=(
            ProducerDependency(
                locator=f"fixture://stage-ace-producer/{lottery_type.value}",
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
                reason="synthetic unavailable prediction test",
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


# =============================================================================
# 14 Combined Fixture Rehearsal Scenarios
# =============================================================================


def test_scenario_01_t539_successful_flow(tmp_path: Path) -> None:
    """1. T539 successful end-to-end Stage A -> C -> E lineage."""
    paths = _paths(tmp_path / "draw-data")
    seal_root = tmp_path / "prediction-seals"

    # Stage A: Seed schedule and causal presence
    _seed_complete_schedules(paths)
    _seed_history_and_presence(paths, LotteryType.DAILY_539)

    # Stage C: Seal prediction
    seal_res = _seal_stage_c(
        paths, seal_root, LotteryType.DAILY_539, _available_draft(LotteryType.DAILY_539)
    )
    assert seal_res.status is RunnablePredictionSealStatus.CREATED
    assert seal_res.registration_status is OperationalRegistrationStatus.CREATED
    assert seal_res.prediction is not None
    prediction = seal_res.prediction

    # Verify Stage A immutable digest in producer dependency
    schedule_deps = [
        d
        for d in prediction.producer_fingerprint.dependencies
        if d.load_bearing_role == SCHEDULE_AUTHORITY_LOAD_BEARING_ROLE
    ]
    assert len(schedule_deps) == 1
    assert schedule_deps[0].source_sha256 == seal_res.immutable_schedule_sha256

    # Stage E: Seed official draw & join result
    _seed_official_outcome_draw(paths, LotteryType.DAILY_539)

    with open_t539_p638_stage_e_result_join(
        lottery_type=LotteryType.DAILY_539,
        data_directory=paths.data_directory,
        prediction_store_root=seal_root,
        clock=lambda: _SCORED_AT,
    ) as comp:
        join_res = comp.service.join_prediction(prediction)
        assert join_res.status is ProspectiveResultJoinStatus.CREATED
        assert join_res.score is not None
        assert join_res.outcome is not None
        assert join_res.score.prediction_hash == prediction.prediction_hash
        assert join_res.score.outcome.outcome_hash == join_res.outcome.outcome_hash
        assert join_res.score.entries[0].availability is ScoreAvailability.SCORED
        assert join_res.score.entries[0].evaluation is not None
        assert join_res.score.entries[0].evaluation.is_winner is True


def test_scenario_02_p638_successful_flow(tmp_path: Path) -> None:
    """2. P638 successful end-to-end Stage A -> C -> E lineage."""
    paths = _paths(tmp_path / "draw-data")
    seal_root = tmp_path / "prediction-seals"

    # Stage A: Seed schedule and causal presence
    _seed_complete_schedules(paths)
    _seed_history_and_presence(paths, LotteryType.POWER_LOTTO)

    # Stage C: Seal prediction (6/38 + Zone 2: 1..8)
    seal_res = _seal_stage_c(
        paths, seal_root, LotteryType.POWER_LOTTO, _available_draft(LotteryType.POWER_LOTTO)
    )
    assert seal_res.status is RunnablePredictionSealStatus.CREATED
    assert seal_res.registration_status is OperationalRegistrationStatus.CREATED
    assert seal_res.prediction is not None
    prediction = seal_res.prediction

    # Stage E: Seed official draw (6/38 + Zone 2: 2) & join result
    _seed_official_outcome_draw(paths, LotteryType.POWER_LOTTO)

    with open_t539_p638_stage_e_result_join(
        lottery_type=LotteryType.POWER_LOTTO,
        data_directory=paths.data_directory,
        prediction_store_root=seal_root,
        clock=lambda: _SCORED_AT,
    ) as comp:
        join_res = comp.service.join_prediction(prediction)
        assert join_res.status is ProspectiveResultJoinStatus.CREATED
        assert join_res.score is not None
        assert join_res.outcome is not None
        assert join_res.score.prediction_hash == prediction.prediction_hash
        assert join_res.score.outcome.outcome_hash == join_res.outcome.outcome_hash
        assert join_res.score.entries[0].availability is ScoreAvailability.SCORED
        assert join_res.score.entries[0].evaluation is not None
        assert join_res.score.entries[0].evaluation.is_winner is True


def test_scenario_03_unavailable_prediction(tmp_path: Path) -> None:
    """3. Sealed UNAVAILABLE_PREDICTION is joined and scored without being treated as miss."""
    paths = _paths(tmp_path / "draw-data")
    seal_root = tmp_path / "prediction-seals"

    _seed_complete_schedules(paths)
    _seed_history_and_presence(paths, LotteryType.DAILY_539)

    seal_res = _seal_stage_c(paths, seal_root, LotteryType.DAILY_539, _unavailable_draft())
    assert seal_res.status is RunnablePredictionSealStatus.CREATED
    assert seal_res.prediction is not None
    prediction = seal_res.prediction

    _seed_official_outcome_draw(paths, LotteryType.DAILY_539)

    with open_t539_p638_stage_e_result_join(
        lottery_type=LotteryType.DAILY_539,
        data_directory=paths.data_directory,
        prediction_store_root=seal_root,
        clock=lambda: _SCORED_AT,
    ) as comp:
        join_res = comp.service.join_prediction(prediction)
        assert join_res.status is ProspectiveResultJoinStatus.CREATED
        assert join_res.score is not None
        assert (
            join_res.score.entries[0].availability
            is ScoreAvailability.UNAVAILABLE_PREDICTION
        )
        assert join_res.score.entries[0].evaluation is None


def test_scenario_04_cancelled_target(tmp_path: Path) -> None:
    """4. Cancelled target via Stage A veto fails closed in Stage C (no seal)."""
    paths = _paths(tmp_path / "draw-data")
    seal_root = tmp_path / "prediction-seals"

    # Stage A: apply schedule with cancellation veto
    SQLiteCanonicalScheduleAuthorityRepository(paths).apply_canonical_schedule_authority(
        _fetch(
            _row(LotteryType.DAILY_539),
            _row(LotteryType.POWER_LOTTO),
            active_vetoes=(_veto(LotteryType.DAILY_539),),
        )
    )
    _seed_history_and_presence(paths, LotteryType.DAILY_539)

    # Stage C: Attempt to seal
    factory = _ProducerFactory(_available_draft(LotteryType.DAILY_539))
    comp = compose_t539_p638_stage_c_prediction_seal(
        lottery_type=LotteryType.DAILY_539,
        data_directory=paths.data_directory,
        prediction_store_root=seal_root,
        producer_factory=factory,
        cohort=_cohort(LotteryType.DAILY_539),
        base_producer_fingerprint=_fingerprint(LotteryType.DAILY_539),
        clock=lambda: _NOW,
    )
    result = comp.service.seal_earliest()
    assert result.status is RunnablePredictionSealStatus.NO_RUNNABLE_TARGET
    assert factory.calls == []
    assert tuple(seal_root.rglob("prediction.json")) == ()


def test_scenario_05_conflicted_target(tmp_path: Path) -> None:
    """5. Conflicted target in Stage A fails closed in Stage C (no seal)."""
    paths = _paths(tmp_path / "draw-data")
    seal_root = tmp_path / "prediction-seals"

    repo = SQLiteCanonicalScheduleAuthorityRepository(paths)
    _seed_complete_schedules(paths)
    # Apply conflicting date for DAILY_539
    repo.apply_canonical_schedule_authority(
        _fetch(
            _row(LotteryType.DAILY_539, draw_date=date(2099, 1, 4)),
            _row(LotteryType.POWER_LOTTO),
            marker=1,
        )
    )
    _seed_history_and_presence(paths, LotteryType.DAILY_539)

    factory = _ProducerFactory(_available_draft(LotteryType.DAILY_539))
    comp = compose_t539_p638_stage_c_prediction_seal(
        lottery_type=LotteryType.DAILY_539,
        data_directory=paths.data_directory,
        prediction_store_root=seal_root,
        producer_factory=factory,
        cohort=_cohort(LotteryType.DAILY_539),
        base_producer_fingerprint=_fingerprint(LotteryType.DAILY_539),
        clock=lambda: _NOW,
    )
    result = comp.service.seal_earliest()
    assert result.status is RunnablePredictionSealStatus.NO_RUNNABLE_TARGET
    assert factory.calls == []
    assert tuple(seal_root.rglob("prediction.json")) == ()


def test_scenario_06_late_target(tmp_path: Path) -> None:
    """6. Late target (clock >= scheduled_at) is rejected before prediction generation."""
    paths = _paths(tmp_path / "draw-data")
    seal_root = tmp_path / "prediction-seals"

    _seed_complete_schedules(paths)
    _seed_history_and_presence(paths, LotteryType.DAILY_539)

    target_record = SQLiteFutureDrawIdentityReader(paths).get_scheduled_draw(
        LotteryType.DAILY_539, _DRAW_NUMBER
    )
    assert target_record is not None

    factory = _ProducerFactory(_available_draft(LotteryType.DAILY_539))
    comp = compose_t539_p638_stage_c_prediction_seal(
        lottery_type=LotteryType.DAILY_539,
        data_directory=paths.data_directory,
        prediction_store_root=seal_root,
        producer_factory=factory,
        cohort=_cohort(LotteryType.DAILY_539),
        base_producer_fingerprint=_fingerprint(LotteryType.DAILY_539),
        clock=lambda: target_record.announcement.scheduled_at,
    )
    result = comp.service.seal_earliest()
    assert result.status is RunnablePredictionSealStatus.NO_RUNNABLE_TARGET
    assert factory.calls == []
    assert tuple(seal_root.rglob("prediction.json")) == ()


def test_scenario_07_wrong_lottery(tmp_path: Path) -> None:
    """7. Wrong lottery type fails closed on join attempt."""
    paths = _paths(tmp_path / "draw-data")
    seal_root = tmp_path / "prediction-seals"

    _seed_complete_schedules(paths)
    _seed_history_and_presence(paths, LotteryType.DAILY_539)
    seal_res = _seal_stage_c(
        paths, seal_root, LotteryType.DAILY_539, _available_draft(LotteryType.DAILY_539)
    )
    prediction = seal_res.prediction
    assert prediction is not None

    _seed_official_outcome_draw(paths, LotteryType.DAILY_539)

    # Attempting to join a DAILY_539 prediction using POWER_LOTTO composition fails closed
    with (
        open_t539_p638_stage_e_result_join(
            lottery_type=LotteryType.POWER_LOTTO,
            data_directory=paths.data_directory,
            prediction_store_root=seal_root,
            clock=lambda: _SCORED_AT,
        ) as comp,
        pytest.raises(GameContractError, match="no prospective game contract for DAILY_539"),
    ):
        comp.service.join_prediction(prediction)


def test_scenario_08_wrong_draw_number(tmp_path: Path) -> None:
    """8. Wrong draw number returns OUTCOME_UNAVAILABLE when missing from official DB."""
    paths = _paths(tmp_path / "draw-data")
    seal_root = tmp_path / "prediction-seals"

    _seed_complete_schedules(paths)
    _seed_history_and_presence(paths, LotteryType.DAILY_539)
    seal_res = _seal_stage_c(
        paths, seal_root, LotteryType.DAILY_539, _available_draft(LotteryType.DAILY_539)
    )
    prediction = seal_res.prediction
    assert prediction is not None

    # Seed draw with DIFFERENT draw number #999999902
    _seed_official_outcome_draw(paths, LotteryType.DAILY_539, draw_number="999999902")

    with open_t539_p638_stage_e_result_join(
        lottery_type=LotteryType.DAILY_539,
        data_directory=paths.data_directory,
        prediction_store_root=seal_root,
        clock=lambda: _SCORED_AT,
    ) as comp:
        join_res = comp.service.join_prediction(prediction)
        assert join_res.status is ProspectiveResultJoinStatus.OUTCOME_UNAVAILABLE
        assert join_res.score is None


def test_scenario_09_wrong_draw_date(tmp_path: Path) -> None:
    """9. Wrong draw date for matching draw number fails closed with GameContractError."""
    paths = _paths(tmp_path / "draw-data")
    seal_root = tmp_path / "prediction-seals"

    _seed_complete_schedules(paths)
    _seed_history_and_presence(paths, LotteryType.DAILY_539)
    seal_res = _seal_stage_c(
        paths, seal_root, LotteryType.DAILY_539, _available_draft(LotteryType.DAILY_539)
    )
    prediction = seal_res.prediction
    assert prediction is not None

    # Verify at SQLite level: database schedule trigger rejects corrupted completed draw date
    with (
        pytest.raises(Exception, match="completed draw date conflicts with schedule identity"),
    ):
        _seed_official_outcome_draw(
            paths, LotteryType.DAILY_539, draw_date=date(2099, 1, 5)
        )

    # Verify at Application service level: ProspectiveResultJoinService fails closed if draw
    # reader returns mismatched date
    class MismatchedDateDrawReader:
        def find(self, lottery_type: LotteryType, draw_number: str) -> DrawRecord | None:
            return DrawRecord(
                internal_id=1,
                lottery_type=lottery_type,
                draw_number=draw_number,
                draw_date=date(2099, 1, 5),  # Mismatched date
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
        data_directory=paths.data_directory,
        prediction_store_root=seal_root,
        clock=lambda: _SCORED_AT,
    ) as comp:
        service_with_mismatched_reader = ProspectiveResultJoinService(
            draw_reader=MismatchedDateDrawReader(),
            scoring_service=comp.scoring_service,
            store=comp.prediction_store,
        )
        with pytest.raises(
            GameContractError,
            match="official draw identity does not match prediction",
        ):
            service_with_mismatched_reader.join_prediction(prediction)


def test_scenario_10_changed_stage_a_digest(tmp_path: Path) -> None:
    """10. Changed Stage A digest in fingerprint fails closed with ProducerFingerprintDriftError."""
    paths = _paths(tmp_path / "draw-data")
    seal_root = tmp_path / "prediction-seals"

    _seed_complete_schedules(paths)
    _seed_history_and_presence(paths, LotteryType.DAILY_539)
    seal_res = _seal_stage_c(
        paths, seal_root, LotteryType.DAILY_539, _available_draft(LotteryType.DAILY_539)
    )
    prediction = seal_res.prediction
    assert prediction is not None

    _seed_official_outcome_draw(paths, LotteryType.DAILY_539)

    # Drifted fingerprint with corrupted Stage A schedule dependency digest
    corrupted_dependencies = tuple(
        ProducerDependency(
            locator=dep.locator,
            source_sha256=_sha256("tampered-digest"),
            load_bearing_role=dep.load_bearing_role,
        )
        for dep in prediction.producer_fingerprint.dependencies
    )
    drifted_fingerprint = ProducerFingerprint.create(
        producer_id=prediction.producer_fingerprint.producer_id,
        producer_version=prediction.producer_fingerprint.producer_version,
        dependencies=corrupted_dependencies,
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


def test_scenario_11_prediction_conflict(tmp_path: Path) -> None:
    """11. Conflicting prediction for same identity is rejected atomically."""
    paths = _paths(tmp_path / "draw-data")
    seal_root = tmp_path / "prediction-seals"

    _seed_complete_schedules(paths)
    _seed_history_and_presence(paths, LotteryType.DAILY_539)

    # First seal
    seal_res_1 = _seal_stage_c(
        paths, seal_root, LotteryType.DAILY_539, _available_draft(LotteryType.DAILY_539)
    )
    assert seal_res_1.status is RunnablePredictionSealStatus.CREATED

    # Second seal attempt with conflicting selections
    conflicting_draft = PredictionDraft(
        (
            PredictionEntryDraft.available(
                member_id="synthetic-member",
                selections=(ProspectiveSelection((6, 7, 8, 9, 10)),),
                matched_baseline=MatchedBaselineRef(
                    lottery_type=LotteryType.DAILY_539,
                    baseline_id="synthetic-shape-matched-baseline",
                    baseline_version="v1",
                    authority_sha256=_sha256("baseline:DAILY_539"),
                    ticket_count=1,
                    candidate_sizes=(5,),
                ),
            ),
        )
    )

    comp = compose_t539_p638_stage_c_prediction_seal(
        lottery_type=LotteryType.DAILY_539,
        data_directory=paths.data_directory,
        prediction_store_root=seal_root,
        producer_factory=_ProducerFactory(conflicting_draft),
        cohort=_cohort(LotteryType.DAILY_539),
        base_producer_fingerprint=_fingerprint(LotteryType.DAILY_539),
        clock=lambda: _NOW,
    )
    from lottolab.application.prospective_observer import PredictionConflictError

    with pytest.raises(PredictionConflictError):
        comp.service.seal_earliest()


def test_scenario_12_outcome_conflict(tmp_path: Path) -> None:
    """12. Conflicting outcome for already scored prediction fails closed."""
    paths = _paths(tmp_path / "draw-data")
    seal_root = tmp_path / "prediction-seals"

    _seed_complete_schedules(paths)
    _seed_history_and_presence(paths, LotteryType.DAILY_539)
    seal_res = _seal_stage_c(
        paths, seal_root, LotteryType.DAILY_539, _available_draft(LotteryType.DAILY_539)
    )
    prediction = seal_res.prediction
    assert prediction is not None

    _seed_official_outcome_draw(paths, LotteryType.DAILY_539, main_numbers=(1, 2, 3, 4, 5))

    # Initial successful score
    with open_t539_p638_stage_e_result_join(
        lottery_type=LotteryType.DAILY_539,
        data_directory=paths.data_directory,
        prediction_store_root=seal_root,
        clock=lambda: _SCORED_AT,
    ) as comp:
        join_res = comp.service.join_prediction(prediction)
        assert join_res.status is ProspectiveResultJoinStatus.CREATED

    # Attempt to score again with a conflicting outcome
    conflicting_outcome = OfficialOutcome.create(
        lottery_type=LotteryType.DAILY_539,
        draw_number=_DRAW_NUMBER,
        draw_date=_TARGET_DATE[LotteryType.DAILY_539],
        main_numbers=(10, 11, 12, 13, 14),
        special_number=None,
        source_id="conflicting-source",
        source_sha256=_sha256("conflicting-source"),
    )

    with (
        open_t539_p638_stage_e_result_join(
            lottery_type=LotteryType.DAILY_539,
            data_directory=paths.data_directory,
            prediction_store_root=seal_root,
            clock=lambda: _SCORED_AT,
        ) as comp,
        pytest.raises(ScoreConflictError),
    ):
        from lottolab.application.prospective_observer import ScorePhaseRequest

        comp.scoring_service.sync(
            ScorePhaseRequest(
                identity=prediction.identity,
                producer_fingerprint=prediction.producer_fingerprint,
                outcome=conflicting_outcome,
            )
        )


def test_scenario_13_exact_replay(tmp_path: Path) -> None:
    """13. Exact replay idempotency in both Stage C and Stage E produces 0 mutations."""
    paths = _paths(tmp_path / "draw-data")
    seal_root = tmp_path / "prediction-seals"

    _seed_complete_schedules(paths)
    for lt in (LotteryType.DAILY_539, LotteryType.POWER_LOTTO):
        _seed_history_and_presence(paths, lt)

    # Initial Stage C seals
    pred_t539 = _seal_stage_c(
        paths, seal_root, LotteryType.DAILY_539, _available_draft(LotteryType.DAILY_539)
    ).prediction
    pred_p638 = _seal_stage_c(
        paths, seal_root, LotteryType.POWER_LOTTO, _available_draft(LotteryType.POWER_LOTTO)
    ).prediction
    assert pred_t539 is not None and pred_p638 is not None
    predictions = {LotteryType.DAILY_539: pred_t539, LotteryType.POWER_LOTTO: pred_p638}

    # Replay Stage C
    for lt in (LotteryType.DAILY_539, LotteryType.POWER_LOTTO):
        replay_c = _seal_stage_c(paths, seal_root, lt, _available_draft(lt))
        assert replay_c.status is RunnablePredictionSealStatus.EXACT_IDEMPOTENT_NO_OP
        assert replay_c.prediction == predictions[lt]

    # Seed official draws
    _seed_official_outcome_draw(paths, LotteryType.DAILY_539)
    _seed_official_outcome_draw(paths, LotteryType.POWER_LOTTO)

    # Initial Stage E joins
    scores = {}
    for lt in (LotteryType.DAILY_539, LotteryType.POWER_LOTTO):
        with open_t539_p638_stage_e_result_join(
            lottery_type=lt,
            data_directory=paths.data_directory,
            prediction_store_root=seal_root,
            clock=lambda: _SCORED_AT,
        ) as comp:
            res = comp.service.join_prediction(predictions[lt])
            assert res.status is ProspectiveResultJoinStatus.CREATED
            scores[lt] = res.score

    # Capture file snapshots
    files_before = {
        p.relative_to(tmp_path): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }

    # Replay Stage E joins multiple times
    for _ in range(2):
        for lt in (LotteryType.DAILY_539, LotteryType.POWER_LOTTO):
            with open_t539_p638_stage_e_result_join(
                lottery_type=lt,
                data_directory=paths.data_directory,
                prediction_store_root=seal_root,
                clock=lambda: _SCORED_AT,
            ) as comp:
                replay_e = comp.service.join_prediction(predictions[lt])
                assert replay_e.status is ProspectiveResultJoinStatus.EXACT_IDEMPOTENT_NO_OP
                assert replay_e.score == scores[lt]

    files_after = {
        p.relative_to(tmp_path): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }
    assert files_after == files_before


def test_scenario_14_cross_game_isolation(tmp_path: Path) -> None:
    """14. Cross-game isolation: DAILY_539 target blocked/cancelled does not affect POWER_LOTTO."""
    paths = _paths(tmp_path / "draw-data")
    seal_root = tmp_path / "prediction-seals"

    # Stage A: apply schedule where DAILY_539 is cancelled, POWER_LOTTO is normal
    SQLiteCanonicalScheduleAuthorityRepository(paths).apply_canonical_schedule_authority(
        _fetch(
            _row(LotteryType.DAILY_539),
            _row(LotteryType.POWER_LOTTO),
            active_vetoes=(_veto(LotteryType.DAILY_539),),
        )
    )
    _seed_history_and_presence(paths, LotteryType.DAILY_539)
    _seed_history_and_presence(paths, LotteryType.POWER_LOTTO)

    # Stage C: DAILY_539 fails closed (no runnable target)
    t539_factory = _ProducerFactory(_available_draft(LotteryType.DAILY_539))
    comp_t539 = compose_t539_p638_stage_c_prediction_seal(
        lottery_type=LotteryType.DAILY_539,
        data_directory=paths.data_directory,
        prediction_store_root=seal_root,
        producer_factory=t539_factory,
        cohort=_cohort(LotteryType.DAILY_539),
        base_producer_fingerprint=_fingerprint(LotteryType.DAILY_539),
        clock=lambda: _NOW,
    )
    res_t539 = comp_t539.service.seal_earliest()
    assert res_t539.status is RunnablePredictionSealStatus.NO_RUNNABLE_TARGET
    assert t539_factory.calls == []

    # Stage C: POWER_LOTTO succeeds
    p638_factory = _ProducerFactory(_available_draft(LotteryType.POWER_LOTTO))
    comp_p638 = compose_t539_p638_stage_c_prediction_seal(
        lottery_type=LotteryType.POWER_LOTTO,
        data_directory=paths.data_directory,
        prediction_store_root=seal_root,
        producer_factory=p638_factory,
        cohort=_cohort(LotteryType.POWER_LOTTO),
        base_producer_fingerprint=_fingerprint(LotteryType.POWER_LOTTO),
        clock=lambda: _NOW,
    )
    res_p638 = comp_p638.service.seal_earliest()
    assert res_p638.status is RunnablePredictionSealStatus.CREATED
    assert res_p638.prediction is not None

    # Stage E: POWER_LOTTO joins official result cleanly
    _seed_official_outcome_draw(paths, LotteryType.POWER_LOTTO)

    with open_t539_p638_stage_e_result_join(
        lottery_type=LotteryType.POWER_LOTTO,
        data_directory=paths.data_directory,
        prediction_store_root=seal_root,
        clock=lambda: _SCORED_AT,
    ) as comp:
        join_p638 = comp.service.join_prediction(res_p638.prediction)
        assert join_p638.status is ProspectiveResultJoinStatus.CREATED
        assert join_p638.score is not None

    # Ensure no DAILY_539 predictions or scores exist on disk
    assert not (seal_root / "daily_539").exists()
    assert (seal_root / "power_lotto").exists()
