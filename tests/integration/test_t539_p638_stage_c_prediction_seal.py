"""Disposable end-to-end acceptance for T539/P638 Stage C sealing."""

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

from lottolab.application.pre_outcome_target_operational import (
    OperationalRegistrationStatus,
)
from lottolab.application.prospective_prediction_seal import (
    SCHEDULE_AUTHORITY_LOAD_BEARING_ROLE,
    RunnablePredictionSealResult,
    RunnablePredictionSealStatus,
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
    PredictionContext,
    PredictionDraft,
    PredictionEntryDraft,
    ProducerDependency,
    ProducerFingerprint,
    ProspectiveSelection,
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
        raise AssertionError("Stage C synthetic acceptance must not access the network")

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


def _cohort(lottery_type: LotteryType) -> FrozenCohortRef:
    return FrozenCohortRef(
        lottery_type=lottery_type,
        cohort_id=f"synthetic-stage-c-{lottery_type.value.lower()}",
        cohort_version="v1",
        authority_sha256=_sha256(f"cohort:{lottery_type.value}"),
        frozen_at=datetime(2098, 12, 31, tzinfo=UTC),
        member_ids=("synthetic-member",),
        checkpoint_sizes=(1,),
        checkpoint_provenance=(TemporalProvenance.POST_FREEZE_DATE_PROSPECTIVE,),
    )


def _fingerprint(lottery_type: LotteryType) -> ProducerFingerprint:
    return ProducerFingerprint.create(
        producer_id=f"synthetic-stage-c-{lottery_type.value.lower()}",
        producer_version="v1",
        dependencies=(
            ProducerDependency(
                locator=f"fixture://stage-c-producer/{lottery_type.value}",
                source_sha256=_sha256(f"producer:{lottery_type.value}"),
                load_bearing_role="synthetic deterministic prediction behavior",
            ),
        ),
    )


def _draft(lottery_type: LotteryType) -> PredictionDraft:
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


class _Producer:
    def __init__(self, lottery_type: LotteryType) -> None:
        self.lottery_type = lottery_type
        self.calls: list[PredictionContext] = []

    def predict(self, context: PredictionContext) -> PredictionDraft:
        self.calls.append(context)
        return _draft(self.lottery_type)


class _ProducerFactory:
    def __init__(self, lottery_type: LotteryType) -> None:
        self.lottery_type = lottery_type
        self.calls: list[tuple[TargetAnnouncement, datetime]] = []
        self.producers: list[_Producer] = []

    def __call__(
        self,
        announcement: TargetAnnouncement,
        reference_time: datetime,
    ) -> _Producer:
        self.calls.append((announcement, reference_time))
        producer = _Producer(self.lottery_type)
        self.producers.append(producer)
        return producer


def _composition(
    paths: LocalDataPaths,
    seal_root: Path,
    lottery_type: LotteryType,
    factory: _ProducerFactory,
    *,
    now: datetime = _NOW,
):
    return compose_t539_p638_stage_c_prediction_seal(
        lottery_type=lottery_type,
        data_directory=paths.data_directory,
        prediction_store_root=seal_root,
        producer_factory=factory,
        cohort=_cohort(lottery_type),
        base_producer_fingerprint=_fingerprint(lottery_type),
        clock=lambda: now,
    )


def _seed_complete_schedules(paths: LocalDataPaths) -> None:
    SQLiteCanonicalScheduleAuthorityRepository(paths).apply_canonical_schedule_authority(
        _fetch(
            _row(LotteryType.DAILY_539),
            _row(LotteryType.POWER_LOTTO),
        )
    )


def _database_sha256(paths: LocalDataPaths) -> str:
    return hashlib.sha256(paths.database.read_bytes()).hexdigest()


def test_both_complete_runnable_targets_seal_and_restart_exactly(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path / "draw-data")
    _seed_complete_schedules(paths)
    for lottery_type in (LotteryType.DAILY_539, LotteryType.POWER_LOTTO):
        _seed_history_and_presence(paths, lottery_type)
    before_database = _database_sha256(paths)
    seal_root = tmp_path / "prediction-seals"
    created: dict[LotteryType, RunnablePredictionSealResult] = {}

    for lottery_type in (LotteryType.DAILY_539, LotteryType.POWER_LOTTO):
        factory = _ProducerFactory(lottery_type)
        result = _composition(paths, seal_root, lottery_type, factory).service.seal_earliest()
        created[lottery_type] = result
        assert result.status is RunnablePredictionSealStatus.CREATED
        assert result.registration_status is OperationalRegistrationStatus.CREATED
        assert result.prediction is not None
        assert result.immutable_schedule_sha256 is not None
        assert factory.calls[0][1] == _NOW
        schedule_dependencies = tuple(
            dependency
            for dependency in result.prediction.producer_fingerprint.dependencies
            if dependency.load_bearing_role == SCHEDULE_AUTHORITY_LOAD_BEARING_ROLE
        )
        assert len(schedule_dependencies) == 1
        assert schedule_dependencies[0].source_sha256 == result.immutable_schedule_sha256

    original_bytes = {
        path.relative_to(seal_root): path.read_bytes()
        for path in seal_root.rglob("prediction.json")
    }
    assert len(original_bytes) == 2
    assert len(tuple((paths.data_directory / "pre-outcome-target-authority-v1").rglob(
        "registration.json"
    ))) == 2

    for lottery_type in (LotteryType.DAILY_539, LotteryType.POWER_LOTTO):
        replay = _composition(
            paths,
            seal_root,
            lottery_type,
            _ProducerFactory(lottery_type),
        ).service.seal_earliest()
        assert replay.status is RunnablePredictionSealStatus.EXACT_IDEMPOTENT_NO_OP
        assert replay.prediction == created[lottery_type].prediction

    assert {
        path.relative_to(seal_root): path.read_bytes()
        for path in seal_root.rglob("prediction.json")
    } == original_bytes
    assert _database_sha256(paths) == before_database
    reader = SQLiteFutureDrawIdentityReader(paths)
    assert reader.find_earliest_unpopulated_future(
        LotteryType.DAILY_539,
        _NOW,
    ).immutable_schedule_sha256 == created[LotteryType.DAILY_539].immutable_schedule_sha256  # type: ignore[union-attr]
    assert reader.find_earliest_unpopulated_future(
        LotteryType.POWER_LOTTO,
        _NOW,
    ).immutable_schedule_sha256 == created[LotteryType.POWER_LOTTO].immutable_schedule_sha256  # type: ignore[union-attr]


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


def _apply_blocked_fixture(
    paths: LocalDataPaths,
    *,
    blocked: LotteryType,
    condition: str,
) -> None:
    other = (
        LotteryType.POWER_LOTTO
        if blocked is LotteryType.DAILY_539
        else LotteryType.DAILY_539
    )
    repository = SQLiteCanonicalScheduleAuthorityRepository(paths)
    if condition == "incomplete":
        repository.apply_canonical_schedule_authority(
            _fetch(_row(blocked, None), _row(other))
        )
        return
    _seed_complete_schedules(paths)
    if condition == "conflicted":
        repository.apply_canonical_schedule_authority(
            _fetch(
                _row(blocked, draw_date=date(2099, 1, 4)),
                _row(other),
                marker=1,
            )
        )
        return
    if condition == "cancelled":
        repository.apply_canonical_schedule_authority(
            _fetch(
                _row(blocked),
                _row(other),
                marker=2,
                active_vetoes=(_veto(blocked),),
            )
        )
        return
    raise AssertionError(f"unsupported blocked condition: {condition}")


@pytest.mark.parametrize("condition", ("incomplete", "conflicted", "cancelled"))
@pytest.mark.parametrize(
    "blocked",
    (LotteryType.DAILY_539, LotteryType.POWER_LOTTO),
)
def test_nonrunnable_game_creates_no_seal_and_does_not_block_other_game(
    condition: str,
    blocked: LotteryType,
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path / "draw-data")
    _apply_blocked_fixture(paths, blocked=blocked, condition=condition)
    for lottery_type in (LotteryType.DAILY_539, LotteryType.POWER_LOTTO):
        _seed_history_and_presence(paths, lottery_type)
    other = (
        LotteryType.POWER_LOTTO
        if blocked is LotteryType.DAILY_539
        else LotteryType.DAILY_539
    )
    seal_root = tmp_path / "prediction-seals"
    blocked_factory = _ProducerFactory(blocked)
    valid_factory = _ProducerFactory(other)

    blocked_result = _composition(
        paths,
        seal_root,
        blocked,
        blocked_factory,
    ).service.seal_earliest()
    valid_result = _composition(
        paths,
        seal_root,
        other,
        valid_factory,
    ).service.seal_earliest()

    assert blocked_result.status is RunnablePredictionSealStatus.NO_RUNNABLE_TARGET
    assert blocked_factory.calls == []
    assert valid_result.status is RunnablePredictionSealStatus.CREATED
    assert len(valid_factory.calls) == 1
    prediction_files = tuple(seal_root.rglob("prediction.json"))
    assert len(prediction_files) == 1
    assert other.value.lower() in prediction_files[0].parts


@pytest.mark.parametrize(
    "lottery_type",
    (LotteryType.DAILY_539, LotteryType.POWER_LOTTO),
)
def test_post_scheduled_clock_cannot_resolve_or_seal_target(
    lottery_type: LotteryType,
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path / "draw-data")
    _seed_complete_schedules(paths)
    _seed_history_and_presence(paths, lottery_type)
    record = SQLiteFutureDrawIdentityReader(paths).get_scheduled_draw(
        lottery_type,
        _DRAW_NUMBER,
    )
    assert record is not None
    factory = _ProducerFactory(lottery_type)

    result = _composition(
        paths,
        tmp_path / "prediction-seals",
        lottery_type,
        factory,
        now=record.announcement.scheduled_at,
    ).service.seal_earliest()

    assert result.status is RunnablePredictionSealStatus.NO_RUNNABLE_TARGET
    assert factory.calls == []
    assert tuple((tmp_path / "prediction-seals").rglob("prediction.json")) == ()


def test_stage_c_composition_does_not_admit_b649_or_create_state(
    tmp_path: Path,
) -> None:
    data_directory = tmp_path / "draw-data"
    seal_root = tmp_path / "prediction-seals"

    with pytest.raises(ValueError, match="only DAILY_539 and POWER_LOTTO"):
        compose_t539_p638_stage_c_prediction_seal(
            lottery_type=LotteryType.BIG_LOTTO,
            data_directory=data_directory,
            prediction_store_root=seal_root,
            producer_factory=_ProducerFactory(LotteryType.BIG_LOTTO),
            cohort=_cohort(LotteryType.BIG_LOTTO),
            base_producer_fingerprint=_fingerprint(LotteryType.BIG_LOTTO),
            clock=lambda: _NOW,
        )

    assert not data_directory.exists()
    assert not seal_root.exists()
