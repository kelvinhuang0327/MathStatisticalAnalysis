"""Infrastructure coverage for canonical pre-outcome operational bindings."""

from __future__ import annotations

import hashlib
import inspect
import json
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import cast

import pytest
from typer.testing import CliRunner

import lottolab.infrastructure.pre_outcome_target_operational as operational_module
from lottolab.application.future_draw_identity import normalized_announcement_sha256
from lottolab.application.pre_outcome_target_operational import (
    CausalHistoryAuthorityError,
    OperationalRegistrationStatus,
    OutcomePresenceEvidenceUnavailableError,
    TargetAnnouncementAuthorityError,
    TargetAnnouncementSourceStatus,
)
from lottolab.application.schedule_sync import (
    SUPPORTED_CANONICAL_SCHEDULE_LOTTERIES,
    CanonicalScheduleFact,
    expected_schedule_game_code,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.ingestion import IngestionOperationType, IngestionRunStatus
from lottolab.domain.pre_outcome_target import (
    OutcomePresenceAttestation,
    PreOutcomeTargetRegistration,
    TargetAnnouncement,
    TargetSourceProvenance,
)
from lottolab.domain.prospective_observer import (
    CausalHistoryRef,
    ObservationTarget,
    OutcomePresenceAtPrediction,
)
from lottolab.infrastructure.persistence.draw_schema import (
    DATA_DIRECTORY_ENV,
    LocalDataPaths,
    initialize_schema,
    open_database,
    resolve_local_data_paths,
)
from lottolab.infrastructure.pre_outcome_target_operational import (
    ANNOUNCEMENT_FILENAME,
    AUTHORITY_DIRECTORY_NAME,
    OFFICIAL_SCHEDULE_SOURCE_ID,
    OFFICIAL_SCHEDULE_SOURCE_VERSION,
    OPERATIONAL_ANNOUNCEMENT_SCHEMA_VERSION,
    CanonicalPreOutcomeTargetAuthorityStore,
    FileSystemOperationalTargetAnnouncementSource,
    SQLiteOfficialOutcomePresenceProbe,
    SQLitePreOutcomeCausalHistoryAuthority,
    compose_pre_outcome_target_operational_service,
    resolve_pre_outcome_target_operational_paths,
)
from lottolab.infrastructure.pre_outcome_target_store import (
    FileSystemPreOutcomeTargetAuthorityStore,
)
from lottolab.infrastructure.taiwan_lottery_draw_provider import (
    PROVIDER_ID,
    PROVIDER_VERSION,
)
from lottolab.interfaces.cli.main import app

NOW = datetime(2099, 1, 1, 8, tzinfo=UTC)
TARGET_DATE = date(2099, 1, 2)
SCHEDULED_AT = datetime(2099, 1, 2, 12, 30, tzinfo=UTC)
runner = CliRunner()


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _paths(tmp_path: Path) -> LocalDataPaths:
    paths = resolve_local_data_paths(
        environ={DATA_DIRECTORY_ENV: str(tmp_path / "lottolab-data")}
    )
    initialize_schema(paths)
    return paths


def _announcement_item(
    lottery_type: LotteryType,
    draw_number: str,
    *,
    draw_date: date = TARGET_DATE,
    scheduled_at: datetime = SCHEDULED_AT,
    locator: str = "https://www.taiwanlottery.com/lotto/results",
) -> dict[str, object]:
    return {
        "target": {
            "lottery_type": lottery_type.value,
            "draw_number": draw_number,
            "draw_date": draw_date.isoformat(),
        },
        "schedule_timezone": "Asia/Taipei",
        "scheduled_at": scheduled_at.isoformat().replace("+00:00", "Z"),
        "source": {
            "source_id": OFFICIAL_SCHEDULE_SOURCE_ID,
            "source_version": OFFICIAL_SCHEDULE_SOURCE_VERSION,
            "source_locator": locator,
            "source_payload_sha256": _sha256(
                f"official-schedule:{lottery_type.value}:{draw_number}"
            ),
            "observed_at": "2099-01-01T06:00:00Z",
        },
    }


def _write_announcements(path: Path, *items: dict[str, object]) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": OPERATIONAL_ANNOUNCEMENT_SCHEMA_VERSION,
                "announcements": list(items),
            },
            separators=(",", ":"),
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    path.chmod(0o600)


def _insert_run(
    paths: LocalDataPaths,
    *,
    run_id: str,
    lottery_type: LotteryType,
    requested_start: date,
    requested_end: date,
    completed_at: datetime,
    fetched_count: int,
    provider: str = PROVIDER_ID,
    provider_version: str = PROVIDER_VERSION,
) -> None:
    timestamp = completed_at.isoformat(timespec="microseconds").replace("+00:00", "Z")
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
                "official-sync.json",
                _sha256(run_id),
                "test-parser-v1",
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
                provider,
                provider_version,
                requested_start.isoformat(),
                requested_end.isoformat(),
                fetched_count,
            ),
        )
        connection.commit()


def _insert_draw(
    paths: LocalDataPaths,
    *,
    run_id: str,
    lottery_type: LotteryType,
    draw_number: str,
    draw_date: date,
    digest: str,
) -> None:
    special = [] if lottery_type is LotteryType.DAILY_539 else [7]
    main = [1, 2, 3, 4, 5] if lottery_type is LotteryType.DAILY_539 else [1, 2, 3, 4, 5, 6]
    timestamp = "2099-01-01T07:00:00.000000Z"
    with open_database(paths, read_only=False) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO draws (
                lottery_type, draw_number, draw_date, main_numbers_json,
                special_numbers_json, normalized_record_hash, source_name,
                source_reference, ingestion_run_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lottery_type.value,
                draw_number,
                draw_date.isoformat(),
                json.dumps(main, separators=(",", ":")),
                json.dumps(special, separators=(",", ":")),
                digest,
                "test-history",
                None,
                run_id,
                timestamp,
                timestamp,
            ),
        )
        connection.commit()


def _insert_schedule(
    paths: LocalDataPaths,
    *,
    lottery_type: LotteryType,
    draw_number: str,
    suffix: str,
) -> None:
    run_id = f"schedule-{suffix}"
    _insert_run(
        paths,
        run_id=run_id,
        lottery_type=lottery_type,
        requested_start=TARGET_DATE,
        requested_end=TARGET_DATE,
        completed_at=datetime(2099, 1, 1, 6, 30, tzinfo=UTC),
        fetched_count=0,
    )
    announcement = TargetAnnouncement(
        target=ObservationTarget(lottery_type, draw_number, TARGET_DATE),
        schedule_timezone="Asia/Taipei",
        scheduled_at=SCHEDULED_AT,
        source=TargetSourceProvenance(
            source_id=OFFICIAL_SCHEDULE_SOURCE_ID,
            source_version=OFFICIAL_SCHEDULE_SOURCE_VERSION,
            source_locator="https://www.taiwanlottery.com/lotto/results",
            source_sha256=_sha256(f"official-schedule:{lottery_type.value}:{draw_number}"),
            observed_at=datetime(2099, 1, 1, 6, tzinfo=UTC),
        ),
    )
    with open_database(paths, read_only=False) as connection:
        connection.execute("BEGIN IMMEDIATE")
        inserted = connection.execute(
            """
            INSERT INTO draw_schedules (
                lottery_type, draw_number, draw_date, scheduled_at,
                schedule_timezone, source_id, source_version, source_locator,
                source_payload_sha256, source_observed_at,
                normalized_announcement_hash, ingestion_run_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lottery_type.value,
                draw_number,
                TARGET_DATE.isoformat(),
                "2099-01-02T12:30:00.000000Z",
                announcement.schedule_timezone,
                announcement.source.source_id,
                announcement.source.source_version,
                announcement.source.source_locator,
                announcement.source.source_payload_sha256,
                "2099-01-01T06:00:00.000000Z",
                normalized_announcement_sha256(announcement),
                run_id,
                "2099-01-01T06:30:00.000000Z",
            ),
        )
        if lottery_type in SUPPORTED_CANONICAL_SCHEDULE_LOTTERIES:
            fact = CanonicalScheduleFact(
                announcement=announcement,
                official_game_code=expected_schedule_game_code(lottery_type),
                scheduled_local_time=time(20, 30),
                source_period_identifier=draw_number,
            )
            connection.execute(
                """
                INSERT INTO draw_schedule_facts (
                    schedule_id, official_game_code, scheduled_local_time,
                    source_period_identifier, immutable_schedule_hash,
                    authority_origin
                ) VALUES (?, ?, ?, ?, ?, 'OFFICIAL')
                """,
                (
                    inserted.lastrowid,
                    fact.official_game_code,
                    fact.scheduled_local_time.isoformat(timespec="seconds"),
                    fact.source_period_identifier,
                    fact.immutable_schedule_sha256,
                ),
            )
        connection.commit()


def _seed_history_and_presence_audit(
    paths: LocalDataPaths,
    lottery_type: LotteryType,
    *,
    suffix: str,
) -> None:
    history_run = f"history-{suffix}"
    history_date = date(2099, 1, 1)
    _insert_run(
        paths,
        run_id=history_run,
        lottery_type=lottery_type,
        requested_start=history_date,
        requested_end=history_date,
        completed_at=datetime(2099, 1, 1, 7, tzinfo=UTC),
        fetched_count=1,
    )
    _insert_draw(
        paths,
        run_id=history_run,
        lottery_type=lottery_type,
        draw_number="999999900",
        draw_date=history_date,
        digest=_sha256(f"history-row:{suffix}"),
    )
    _insert_run(
        paths,
        run_id=f"presence-{suffix}",
        lottery_type=lottery_type,
        requested_start=TARGET_DATE,
        requested_end=TARGET_DATE,
        completed_at=datetime(2099, 1, 1, 7, 30, tzinfo=UTC),
        fetched_count=0,
    )


def _registration(lottery_type: LotteryType) -> PreOutcomeTargetRegistration:
    target = ObservationTarget(lottery_type, "999999901", TARGET_DATE)
    source = TargetSourceProvenance(
        source_id="fixture",
        source_version="v1",
        source_locator="fixture://authority",
        source_sha256=_sha256("fixture-source"),
        observed_at=datetime(2099, 1, 1, 6, tzinfo=UTC),
    )
    announcement = TargetAnnouncement(
        target=target,
        schedule_timezone="Asia/Taipei",
        scheduled_at=SCHEDULED_AT,
        source=source,
    )
    return PreOutcomeTargetRegistration.create(
        announcement=announcement,
        absence_attestation=OutcomePresenceAttestation(
            target=target,
            presence=OutcomePresenceAtPrediction.ABSENT,
            attested_at=NOW,
            source=source,
        ),
        causal_history=CausalHistoryRef(
            draw_count=1,
            last_draw_number="999999900",
            last_draw_date=date(2099, 1, 1),
            history_sha256=_sha256("history"),
        ),
        registered_at=NOW,
    )


def _keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        mapping = cast(dict[object, object], value)
        keys.update(str(key) for key in mapping)
        for item in mapping.values():
            keys.update(_keys(item))
    elif isinstance(value, list):
        for item in cast(list[object], value):
            keys.update(_keys(item))
    return keys


def test_path_resolution_defines_exact_paths_without_creating_them(tmp_path: Path) -> None:
    data_directory = tmp_path / "absent-data"

    paths = resolve_pre_outcome_target_operational_paths(
        environ={DATA_DIRECTORY_ENV: str(data_directory)}
    )

    assert paths.local_data.database == data_directory / "lottolab.db"
    assert paths.announcement_file == data_directory / ANNOUNCEMENT_FILENAME
    assert paths.authority_root == data_directory / AUTHORITY_DIRECTORY_NAME
    assert not data_directory.exists()


@pytest.mark.parametrize("lottery_type", tuple(LotteryType))
def test_announcement_source_accepts_each_lottery_and_binds_entry_digest(
    tmp_path: Path,
    lottery_type: LotteryType,
) -> None:
    paths = _paths(tmp_path)
    item = _announcement_item(lottery_type, "999999901")
    _write_announcements(paths.data_directory / ANNOUNCEMENT_FILENAME, item)
    source = FileSystemOperationalTargetAnnouncementSource(
        paths.data_directory / ANNOUNCEMENT_FILENAME
    )

    first = source.read()
    first_digest = first.announcements[0].source.source_sha256
    _write_announcements(
        paths.data_directory / ANNOUNCEMENT_FILENAME,
        item,
        _announcement_item(
            LotteryType.BIG_LOTTO,
            "999999902",
            draw_date=date(2099, 1, 3),
            scheduled_at=datetime(2099, 1, 3, 12, 30, tzinfo=UTC),
        ),
    )
    second = source.read()

    assert first.status is TargetAnnouncementSourceStatus.AVAILABLE
    assert first.announcements[0].target.lottery_type is lottery_type
    assert len(first_digest) == 64
    assert first_digest == _sha256(
        f"official-schedule:{lottery_type.value}:999999901"
    )
    assert next(
        entry.source.source_sha256
        for entry in second.announcements
        if entry.target == first.announcements[0].target
    ) == first_digest


def test_missing_announcement_file_is_not_configured_without_creation(tmp_path: Path) -> None:
    path = tmp_path / "missing" / ANNOUNCEMENT_FILENAME
    source = FileSystemOperationalTargetAnnouncementSource(path)

    inventory = source.read()

    assert inventory.status is TargetAnnouncementSourceStatus.NOT_CONFIGURED
    assert inventory.announcements == ()
    assert not path.parent.exists()


@pytest.mark.parametrize(
    "mutation",
    [
        "outcome_field",
        "unofficial_locator",
        "invalid_source_hash",
        "wrong_timezone",
        "duplicate_target",
    ],
)
def test_announcement_source_rejects_untrusted_or_outcome_bearing_material(
    tmp_path: Path,
    mutation: str,
) -> None:
    paths = _paths(tmp_path)
    first = _announcement_item(LotteryType.BIG_LOTTO, "999999901")
    items = [first]
    if mutation == "outcome_field":
        first["winning_main_numbers"] = [1, 2, 3, 4, 5, 6]
    elif mutation == "unofficial_locator":
        source = first["source"]
        assert isinstance(source, dict)
        source["source_locator"] = "https://example.com/schedule"
    elif mutation == "invalid_source_hash":
        source = first["source"]
        assert isinstance(source, dict)
        source["source_payload_sha256"] = "not-a-digest"
    elif mutation == "wrong_timezone":
        first["schedule_timezone"] = "UTC"
    else:
        items.append(dict(first))
    path = paths.data_directory / ANNOUNCEMENT_FILENAME
    _write_announcements(path, *items)

    with pytest.raises(TargetAnnouncementAuthorityError):
        FileSystemOperationalTargetAnnouncementSource(path).read()


def test_announcement_source_rejects_duplicate_json_members_recursively(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    path = paths.data_directory / ANNOUNCEMENT_FILENAME
    item = _announcement_item(LotteryType.BIG_LOTTO, "999999901")
    encoded = json.dumps(
        {
            "schema_version": OPERATIONAL_ANNOUNCEMENT_SCHEMA_VERSION,
            "announcements": [item],
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    encoded = encoded.replace(
        '"lottery_type":"BIG_LOTTO"',
        '"lottery_type":"DAILY_539","lottery_type":"BIG_LOTTO"',
        1,
    )
    path.write_text(encoded, encoding="utf-8")
    path.chmod(0o600)

    with pytest.raises(TargetAnnouncementAuthorityError, match="duplicate JSON"):
        FileSystemOperationalTargetAnnouncementSource(path).read()


def test_announcement_file_must_be_owner_only(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    path = paths.data_directory / ANNOUNCEMENT_FILENAME
    _write_announcements(path, _announcement_item(LotteryType.BIG_LOTTO, "999999901"))
    path.chmod(0o644)

    with pytest.raises(TargetAnnouncementAuthorityError, match="0600"):
        FileSystemOperationalTargetAnnouncementSource(path).read()


@pytest.mark.parametrize("kind", ["directory", "symlink", "hardlink"])
def test_announcement_source_rejects_non_regular_or_aliased_authority(
    tmp_path: Path,
    kind: str,
) -> None:
    paths = _paths(tmp_path)
    path = paths.data_directory / ANNOUNCEMENT_FILENAME
    if kind == "directory":
        path.mkdir(mode=0o700)
    else:
        target = paths.data_directory / "announcement-target.json"
        _write_announcements(
            target,
            _announcement_item(LotteryType.BIG_LOTTO, "999999901"),
        )
        if kind == "symlink":
            path.symlink_to(target)
        else:
            path.hardlink_to(target)

    with pytest.raises(TargetAnnouncementAuthorityError):
        FileSystemOperationalTargetAnnouncementSource(path).read()


def test_presence_probe_requires_covering_official_audit_for_absence(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    target = ObservationTarget(LotteryType.BIG_LOTTO, "999999901", TARGET_DATE)
    probe = SQLiteOfficialOutcomePresenceProbe(paths)

    with pytest.raises(OutcomePresenceEvidenceUnavailableError, match="audit"):
        probe.probe(target, as_of=NOW)

    _insert_run(
        paths,
        run_id="official-presence",
        lottery_type=LotteryType.BIG_LOTTO,
        requested_start=TARGET_DATE,
        requested_end=TARGET_DATE,
        completed_at=datetime(2099, 1, 1, 7, tzinfo=UTC),
        fetched_count=0,
    )
    attestation = probe.probe(target, as_of=NOW)

    assert attestation.presence is OutcomePresenceAtPrediction.ABSENT
    assert attestation.target == target
    assert attestation.attested_at == NOW
    assert attestation.source.source_id == "LOTTOLAB_OFFICIAL_OUTCOME_PRESENCE_AUDIT"
    assert "main_numbers" not in attestation.canonical_dict()


def test_presence_probe_returns_present_from_identity_without_outcome_columns(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    _insert_run(
        paths,
        run_id="existing-outcome",
        lottery_type=LotteryType.BIG_LOTTO,
        requested_start=TARGET_DATE,
        requested_end=TARGET_DATE,
        completed_at=datetime(2099, 1, 1, 7, tzinfo=UTC),
        fetched_count=1,
    )
    _insert_draw(
        paths,
        run_id="existing-outcome",
        lottery_type=LotteryType.BIG_LOTTO,
        draw_number="999999901",
        draw_date=TARGET_DATE,
        digest=_sha256("target-outcome"),
    )
    target = ObservationTarget(LotteryType.BIG_LOTTO, "999999901", TARGET_DATE)

    attestation = SQLiteOfficialOutcomePresenceProbe(paths).probe(target, as_of=NOW)

    assert attestation.presence is OutcomePresenceAtPrediction.PRESENT
    source = inspect.getsource(SQLiteOfficialOutcomePresenceProbe.probe)
    assert "main_numbers" not in source
    assert "special_numbers" not in source


def test_presence_probe_rejects_internally_inconsistent_success_audit(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    _insert_run(
        paths,
        run_id="inconsistent-presence",
        lottery_type=LotteryType.BIG_LOTTO,
        requested_start=TARGET_DATE,
        requested_end=TARGET_DATE,
        completed_at=datetime(2099, 1, 1, 7, tzinfo=UTC),
        fetched_count=0,
    )
    with open_database(paths, read_only=False) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "UPDATE ingestion_runs SET total_count = 1 WHERE id = ?",
            ("inconsistent-presence",),
        )
        connection.commit()

    with pytest.raises(OutcomePresenceEvidenceUnavailableError):
        SQLiteOfficialOutcomePresenceProbe(paths).probe(
            ObservationTarget(LotteryType.BIG_LOTTO, "999999901", TARGET_DATE),
            as_of=NOW,
        )


@pytest.mark.parametrize("lottery_type", tuple(LotteryType))
def test_causal_history_binds_only_strictly_prior_normalized_digests(
    tmp_path: Path,
    lottery_type: LotteryType,
) -> None:
    paths = _paths(tmp_path)
    _seed_history_and_presence_audit(paths, lottery_type, suffix=lottery_type.value)
    target = ObservationTarget(lottery_type, "999999901", TARGET_DATE)

    history = SQLitePreOutcomeCausalHistoryAuthority(paths).resolve(target)

    assert history.draw_count == 1
    assert history.last_draw_number == "999999900"
    assert history.last_draw_date == date(2099, 1, 1)
    assert len(history.history_sha256) == 64


def test_causal_history_fails_closed_when_no_prior_draw_exists(tmp_path: Path) -> None:
    paths = _paths(tmp_path)

    with pytest.raises(CausalHistoryAuthorityError, match="no strictly prior"):
        SQLitePreOutcomeCausalHistoryAuthority(paths).resolve(
            ObservationTarget(LotteryType.BIG_LOTTO, "999999901", TARGET_DATE)
        )


def test_lazy_store_does_not_create_root_on_read_but_creates_one_record_on_write(
    tmp_path: Path,
) -> None:
    root = tmp_path / "canonical-authority"
    store = CanonicalPreOutcomeTargetAuthorityStore(root)
    registration = _registration(LotteryType.BIG_LOTTO)

    assert store.get_registration(registration.target) is None
    assert not root.exists()
    assert store.create_registration(registration).value == "INSERTED"
    assert store.get_registration(registration.target) == registration
    record_path = FileSystemPreOutcomeTargetAuthorityStore.record_path_for(
        root, registration.target
    )
    assert record_path.is_file()
    assert hashlib.sha256(record_path.read_bytes()).hexdigest() == (
        FileSystemPreOutcomeTargetAuthorityStore.canonical_record_sha256(registration)
    )


def test_composition_without_source_is_a_no_write_result(tmp_path: Path) -> None:
    data_directory = tmp_path / "absent-data"
    composition = compose_pre_outcome_target_operational_service(
        environ={DATA_DIRECTORY_ENV: str(data_directory)},
        clock=lambda: NOW,
    )

    result = composition.service.register_earliest(LotteryType.BIG_LOTTO)

    assert result.status is OperationalRegistrationStatus.NO_CANONICAL_TARGET_ANNOUNCEMENT
    assert not data_directory.exists()


def test_file_announcement_is_never_an_operational_fallback(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _write_announcements(
        paths.data_directory / ANNOUNCEMENT_FILENAME,
        _announcement_item(LotteryType.BIG_LOTTO, "999999901"),
    )
    before = hashlib.sha256(paths.database.read_bytes()).hexdigest()
    composition = compose_pre_outcome_target_operational_service(
        environ={DATA_DIRECTORY_ENV: str(paths.data_directory)},
        clock=lambda: NOW,
    )

    result = composition.service.register_earliest(LotteryType.BIG_LOTTO)

    assert result.status is OperationalRegistrationStatus.NO_CANONICAL_TARGET_ANNOUNCEMENT
    assert hashlib.sha256(paths.database.read_bytes()).hexdigest() == before
    assert not composition.paths.authority_root.exists()


def test_invalid_legacy_announcement_file_cannot_block_db_only_composition(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    announcement_path = paths.data_directory / ANNOUNCEMENT_FILENAME
    announcement_path.write_text("not-json", encoding="utf-8")
    announcement_path.chmod(0o644)
    before = hashlib.sha256(paths.database.read_bytes()).hexdigest()

    composition = compose_pre_outcome_target_operational_service(
        environ={DATA_DIRECTORY_ENV: str(paths.data_directory)},
        clock=lambda: NOW,
    )
    result = composition.service.register_earliest(LotteryType.BIG_LOTTO)

    assert result.status is OperationalRegistrationStatus.NO_CANONICAL_TARGET_ANNOUNCEMENT
    assert hashlib.sha256(paths.database.read_bytes()).hexdigest() == before
    assert announcement_path.read_text(encoding="utf-8") == "not-json"
    assert not composition.paths.authority_root.exists()


def test_file_change_or_removal_cannot_change_db_selected_target(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _seed_history_and_presence_audit(paths, LotteryType.BIG_LOTTO, suffix="db-only")
    _insert_schedule(
        paths,
        lottery_type=LotteryType.BIG_LOTTO,
        draw_number="999999901",
        suffix="db-only",
    )
    _write_announcements(
        paths.data_directory / ANNOUNCEMENT_FILENAME,
        _announcement_item(LotteryType.BIG_LOTTO, "999999999"),
    )
    composition = compose_pre_outcome_target_operational_service(
        environ={DATA_DIRECTORY_ENV: str(paths.data_directory)},
        clock=lambda: NOW,
    )

    created = composition.service.register_earliest(LotteryType.BIG_LOTTO)
    composition.paths.announcement_file.unlink()
    replayed = composition.service.register_earliest(LotteryType.BIG_LOTTO)

    assert created.status is OperationalRegistrationStatus.CREATED
    assert created.announcement is not None
    assert created.announcement.target.draw_number == "999999901"
    assert replayed.status is OperationalRegistrationStatus.EXACT_IDEMPOTENT_NO_OP
    assert replayed.announcement == created.announcement


def test_multilottery_composition_creates_one_isolated_registration_per_lottery(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    for index, lottery_type in enumerate(LotteryType, start=1):
        _seed_history_and_presence_audit(paths, lottery_type, suffix=str(index))
        _insert_schedule(
            paths,
            lottery_type=lottery_type,
            draw_number="999999901",
            suffix=str(index),
        )
    composition = compose_pre_outcome_target_operational_service(
        environ={DATA_DIRECTORY_ENV: str(paths.data_directory)},
        clock=lambda: NOW,
    )

    results = tuple(
        composition.service.register_earliest(lottery_type)
        for lottery_type in LotteryType
    )

    assert all(result.status is OperationalRegistrationStatus.CREATED for result in results)
    record_paths = tuple(composition.paths.authority_root.rglob("registration.json"))
    assert len(record_paths) == 3
    assert {
        path.relative_to(composition.paths.authority_root).parts[0] for path in record_paths
    } == {lottery_type.value.lower() for lottery_type in LotteryType}


def test_cli_success_is_create_once_idempotent_and_outcome_free(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(operational_module, "_utc_now", lambda: NOW)
    paths = _paths(tmp_path)
    _seed_history_and_presence_audit(paths, LotteryType.BIG_LOTTO, suffix="cli")
    _insert_schedule(
        paths,
        lottery_type=LotteryType.BIG_LOTTO,
        draw_number="999999901",
        suffix="cli",
    )
    arguments = [
        "register-pre-outcome-target",
        "--lottery-type",
        "BIG_LOTTO",
    ]
    environment = {DATA_DIRECTORY_ENV: str(paths.data_directory)}

    created = runner.invoke(app, arguments, env=environment)
    assert created.exit_code == 0
    assert created.stderr == ""
    created_payload = json.loads(created.stdout)
    assert created_payload["status"] == "CREATED"
    record_path = Path(created_payload["record_path"])
    first_bytes = record_path.read_bytes()
    assert hashlib.sha256(first_bytes).hexdigest() == created_payload["record_sha256"]
    assert _keys(created_payload).isdisjoint(
        {
            "main_numbers",
            "outcome_hash",
            "payout",
            "prize_result",
            "score",
            "special_number",
            "winning_main_numbers",
            "winning_special_number",
        }
    )

    replayed = runner.invoke(app, arguments, env=environment)
    assert replayed.exit_code == 0
    assert replayed.stderr == ""
    replayed_payload = json.loads(replayed.stdout)
    assert replayed_payload["status"] == "EXACT_IDEMPOTENT_NO_OP"
    assert replayed_payload["registration"] == created_payload["registration"]
    assert record_path.read_bytes() == first_bytes
