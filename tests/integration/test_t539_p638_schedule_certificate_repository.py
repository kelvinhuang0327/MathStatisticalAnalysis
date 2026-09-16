"""Disposable-DB acceptance for T539/P638 Owner schedule-certificate fallback."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from lottolab.application.schedule_certificate import (
    OWNER_SCHEDULE_CERTIFICATE_SCHEMA_VERSION,
    OWNER_SCHEDULE_CERTIFYING_AUTHORITY,
    ManualScheduleCertificateDisposition,
    OwnerScheduleCertificate,
    ScheduleCertificateCompletedOutcomeError,
    ScheduleCertificateConflictError,
    ScheduleCertificateInputError,
)
from lottolab.application.schedule_sync import (
    P638_SCHEDULE_GAME_CODE,
    T539_SCHEDULE_GAME_CODE,
    AuthoritativeScheduleVeto,
    ScheduleExceptionKind,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.pre_outcome_target import TargetSourceProvenance
from lottolab.infrastructure.persistence.draw_schema import (
    DATA_DIRECTORY_ENV,
    LocalDataPaths,
    initialize_schema,
    open_database,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.future_draw_identity_repository import (
    OFFICIAL_SCHEDULE_SOURCE_ID,
    OFFICIAL_SCHEDULE_SOURCE_VERSION,
    SQLiteCanonicalScheduleAuthorityRepository,
    SQLiteFutureDrawIdentityReader,
)
from lottolab.infrastructure.t539_p638_schedule_certificate import (
    parse_owner_schedule_certificate,
)
from lottolab.infrastructure.taiwan_lottery_schedule_provider import (
    parse_official_t539_p638_schedule,
)


def _paths(tmp_path: Path) -> LocalDataPaths:
    return resolve_local_data_paths(
        environ={DATA_DIRECTORY_ENV: str(tmp_path / "manual-schedule-authority")}
    )


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    ).hexdigest()


def _certificate(
    *,
    draw_number: str = "9001",
    draw_date: str = "2099-01-02",
    local_time: str = "20:30:00",
    source_period_identifier: str | None = "9001",
    variant: str = "canonical",
    reason: str = "OFFICIAL_AUTHORITY_ABSENT",
) -> OwnerScheduleCertificate:
    artifact = (
        f"Official Taiwan Lottery future schedule draw {draw_number}; variant={variant}."
    ).encode()
    scheduled_at = datetime.fromisoformat(f"{draw_date}T{local_time}").replace(
        tzinfo=ZoneInfo("Asia/Taipei")
    ).astimezone(UTC)
    certificate_input: dict[str, object] = {
        "certification_reason": reason,
        "certified_at": "2099-01-01T01:00:00Z",
        "certifying_authority": OWNER_SCHEDULE_CERTIFYING_AUTHORITY,
        "draw_date": draw_date,
        "draw_number": draw_number,
        "lottery_type": LotteryType.DAILY_539.value,
        "official_game_code": T539_SCHEDULE_GAME_CODE,
        "official_source_id": OFFICIAL_SCHEDULE_SOURCE_ID,
        "official_source_locator": (
            "https://api.taiwanlottery.com/TLCAPIWeB/Lottery/NextDrawDate"
            f"?fixture={variant}"
        ),
        "official_source_observed_at": "2099-01-01T00:00:00Z",
        "official_source_version": OFFICIAL_SCHEDULE_SOURCE_VERSION,
        "schedule_timezone": "Asia/Taipei",
        "scheduled_at": scheduled_at.isoformat().replace("+00:00", "Z"),
        "scheduled_local_time": local_time,
        "supporting_artifact_sha256": hashlib.sha256(artifact).hexdigest(),
        "supporting_artifact_type": "OFFICIAL_TAIWAN_LOTTERY_HTTPS_PAYLOAD",
    }
    if source_period_identifier is not None:
        certificate_input["source_period_identifier"] = source_period_identifier
    document = {
        "certificate_input": certificate_input,
        "certificate_input_sha256": _canonical_sha256(certificate_input),
        "schema_version": OWNER_SCHEDULE_CERTIFICATE_SCHEMA_VERSION,
    }
    encoded = json.dumps(document, separators=(",", ":"), sort_keys=True).encode()
    return parse_owner_schedule_certificate(
        encoded,
        source_filename=f"schedule-{draw_number}-{variant}.json",
        supporting_artifact=artifact,
    )


def _official_body(*rows: dict[str, object], marker: int = 0) -> bytes:
    return json.dumps(
        {
            "content": {"nextDrawDateList": list(rows)},
            "fixtureMarker": marker,
            "rtCode": 0,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def _official_row(
    game_code: int,
    draw_number: str | None,
    draw_date: str,
) -> dict[str, object]:
    return {
        "drawDate": draw_date,
        "drawTerm": draw_number,
        "gameCode": game_code,
    }


def _apply_official(
    paths: LocalDataPaths,
    *rows: dict[str, object],
    marker: int = 0,
) -> None:
    fetched = parse_official_t539_p638_schedule(
        _official_body(*rows, marker=marker),
        observed_at=datetime(2099, 1, 1, tzinfo=UTC),
    )
    SQLiteCanonicalScheduleAuthorityRepository(paths).apply_canonical_schedule_authority(
        fetched
    )


def _schedule_snapshot(
    paths: LocalDataPaths,
    draw_number: str,
) -> tuple[object, ...]:
    with open_database(paths, read_only=True) as connection:
        row = connection.execute(
            """
            SELECT s.*, f.official_game_code, f.scheduled_local_time,
                   f.source_period_identifier, f.immutable_schedule_hash,
                   f.authority_origin
            FROM draw_schedules AS s
            INNER JOIN draw_schedule_facts AS f ON f.schedule_id = s.id
            WHERE s.lottery_type = 'DAILY_539' AND s.draw_number = ?
            """,
            (draw_number,),
        ).fetchone()
    assert row is not None
    return tuple(row)


def _insert_completed_t539_draw(paths: LocalDataPaths, draw_number: str) -> None:
    timestamp = "2099-01-01T00:00:00.000000Z"
    with open_database(paths) as connection:
        connection.execute(
            """
            INSERT INTO ingestion_runs (
                id, operation_type, status, lottery_type, source_filename,
                source_sha256, parser_version, total_count, inserted_count,
                skipped_count, conflict_count, failed_count, first_draw_number,
                last_draw_number, started_at, completed_at, error_summary
            ) VALUES (
                'completed-fixture', 'DRAW_CSV_IMPORT', 'SUCCESS', 'DAILY_539',
                'completed.csv', ?, 'fixture-v1', 1, 1, 0, 0, 0, ?, ?, ?, ?, NULL
            )
            """,
            ("a" * 64, draw_number, draw_number, timestamp, timestamp),
        )
        connection.execute(
            """
            INSERT INTO draws (
                lottery_type, draw_number, draw_date, main_numbers_json,
                special_numbers_json, normalized_record_hash, source_name,
                source_reference, ingestion_run_id, created_at, updated_at
            ) VALUES (
                'DAILY_539', ?, '2099-01-02', '[1,2,3,4,5]', '[]', ?,
                'fixture', 'fixture', 'completed-fixture', ?, ?
            )
            """,
            (draw_number, "b" * 64, timestamp, timestamp),
        )
        connection.commit()


def test_preview_is_byte_stable_and_explicit_apply_inserts_manual_authority(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    initialize_schema(paths)
    certificate = _certificate()
    repository = SQLiteCanonicalScheduleAuthorityRepository(paths)
    before_bytes = paths.database.read_bytes()
    before_mtime = paths.database.stat().st_mtime_ns

    preview = repository.preview_owner_schedule_certificate(
        certificate,
        certificate.certificate_document_sha256,
    )

    assert preview.disposition is ManualScheduleCertificateDisposition.INSERTED
    assert preview.zero_write is True
    assert paths.database.read_bytes() == before_bytes
    assert paths.database.stat().st_mtime_ns == before_mtime
    assert SQLiteFutureDrawIdentityReader(paths).get_scheduled_draw(
        LotteryType.DAILY_539,
        "9001",
    ) is None

    result = repository.apply_owner_schedule_certificate(
        certificate,
        certificate.certificate_document_sha256,
    )
    assert result.disposition is ManualScheduleCertificateDisposition.INSERTED
    assert result.inserted_count == 1
    assert _schedule_snapshot(paths, "9001")[-1] == "MANUAL"
    resolved = SQLiteFutureDrawIdentityReader(paths).find_earliest_unpopulated_future(
        LotteryType.DAILY_539,
        datetime(2099, 1, 1, tzinfo=UTC),
    )
    assert resolved is not None
    assert resolved.announcement.target.draw_number == "9001"
    with open_database(paths, read_only=True) as connection:
        evidence = connection.execute(
            """
            SELECT event_kind, disposition, certificate_input_sha256,
                   certificate_document_sha256, certifying_authority,
                   supporting_artifact_type
            FROM draw_schedule_authority_evidence
            WHERE lottery_type = 'DAILY_539' AND draw_number = '9001'
            """
        ).fetchone()
    assert evidence == (
        "MANUAL_CERTIFICATE",
        "INSERTED",
        certificate.certificate_input_sha256,
        certificate.certificate_document_sha256,
        OWNER_SCHEDULE_CERTIFYING_AUTHORITY,
        "OFFICIAL_TAIWAN_LOTTERY_HTTPS_PAYLOAD",
    )


def test_repository_requires_the_exact_certificate_document_hash_pin(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    initialize_schema(paths)
    certificate = _certificate()
    before = paths.database.read_bytes()

    with pytest.raises(ScheduleCertificateInputError):
        SQLiteCanonicalScheduleAuthorityRepository(
            paths
        ).preview_owner_schedule_certificate(certificate, "0" * 64)

    assert paths.database.read_bytes() == before


def test_incomplete_automatic_authority_permits_manual_fallback(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _apply_official(
        paths,
        _official_row(T539_SCHEDULE_GAME_CODE, None, "20990102"),
        _official_row(P638_SCHEDULE_GAME_CODE, "8001", "20990103"),
    )
    certificate = _certificate(reason="OFFICIAL_AUTHORITY_INCOMPLETE")

    result = SQLiteCanonicalScheduleAuthorityRepository(
        paths
    ).apply_owner_schedule_certificate(
        certificate,
        certificate.certificate_document_sha256,
    )

    assert result.disposition is ManualScheduleCertificateDisposition.INSERTED
    assert _schedule_snapshot(paths, "9001")[-1] == "MANUAL"
    resolved = SQLiteFutureDrawIdentityReader(paths).find_earliest_unpopulated_future(
        LotteryType.DAILY_539,
        datetime(2099, 1, 1, tzinfo=UTC),
    )
    assert resolved is not None
    assert resolved.announcement.target.draw_number == "9001"


def test_manual_same_as_complete_official_is_audited_confirmation(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    _apply_official(
        paths,
        _official_row(T539_SCHEDULE_GAME_CODE, "9001", "20990102"),
        _official_row(P638_SCHEDULE_GAME_CODE, "8001", "20990103"),
    )
    original = _schedule_snapshot(paths, "9001")
    certificate = _certificate()
    repository = SQLiteCanonicalScheduleAuthorityRepository(paths)

    preview = repository.preview_owner_schedule_certificate(
        certificate,
        certificate.certificate_document_sha256,
    )
    result = repository.apply_owner_schedule_certificate(
        certificate,
        certificate.certificate_document_sha256,
    )

    assert preview.disposition is ManualScheduleCertificateDisposition.CONFIRMED
    assert result.disposition is ManualScheduleCertificateDisposition.CONFIRMED
    assert result.confirmed_count == 1
    assert _schedule_snapshot(paths, "9001") == original
    with open_database(paths, read_only=True) as connection:
        rows = connection.execute(
            """
            SELECT event_kind, disposition
            FROM draw_schedule_authority_evidence
            WHERE lottery_type = 'DAILY_539' AND draw_number = '9001'
            ORDER BY id
            """
        ).fetchall()
    assert rows == [
        ("OFFICIAL_OBSERVATION", "INSERTED"),
        ("MANUAL_CERTIFICATE", "CONFIRMED"),
    ]


def test_manual_conflict_with_official_never_overwrites_and_fails_closed(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    _apply_official(
        paths,
        _official_row(T539_SCHEDULE_GAME_CODE, "9001", "20990102"),
        _official_row(P638_SCHEDULE_GAME_CODE, "8001", "20990103"),
    )
    original = _schedule_snapshot(paths, "9001")
    conflicting = _certificate(
        local_time="21:15:00",
        variant="changed-time",
        reason="OFFICIAL_TIME_CHANGE",
    )
    repository = SQLiteCanonicalScheduleAuthorityRepository(paths)

    with pytest.raises(ScheduleCertificateConflictError):
        repository.preview_owner_schedule_certificate(
            conflicting,
            conflicting.certificate_document_sha256,
        )
    with pytest.raises(ScheduleCertificateConflictError) as caught:
        repository.apply_owner_schedule_certificate(
            conflicting,
            conflicting.certificate_document_sha256,
        )

    assert caught.value.result is not None
    assert caught.value.result.disposition is ManualScheduleCertificateDisposition.CONFLICT
    assert _schedule_snapshot(paths, "9001") == original
    assert SQLiteFutureDrawIdentityReader(paths).find_earliest_unpopulated_future(
        LotteryType.DAILY_539,
        datetime(2099, 1, 1, tzinfo=UTC),
    ) is None


def test_complete_official_authority_for_game_forbids_new_manual_target(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    _apply_official(
        paths,
        _official_row(T539_SCHEDULE_GAME_CODE, "9000", "20990102"),
        _official_row(P638_SCHEDULE_GAME_CODE, "8001", "20990103"),
    )
    certificate = _certificate(draw_number="9001", draw_date="2099-01-04")
    repository = SQLiteCanonicalScheduleAuthorityRepository(paths)

    with pytest.raises(ScheduleCertificateConflictError):
        repository.preview_owner_schedule_certificate(
            certificate,
            certificate.certificate_document_sha256,
        )
    with pytest.raises(ScheduleCertificateConflictError):
        repository.apply_owner_schedule_certificate(
            certificate,
            certificate.certificate_document_sha256,
        )

    assert SQLiteFutureDrawIdentityReader(paths).get_scheduled_draw(
        LotteryType.DAILY_539,
        "9001",
    ) is None


def test_completed_outcome_already_exists_is_rejected(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    initialize_schema(paths)
    _insert_completed_t539_draw(paths, "9001")
    certificate = _certificate()
    repository = SQLiteCanonicalScheduleAuthorityRepository(paths)

    with pytest.raises(ScheduleCertificateCompletedOutcomeError):
        repository.preview_owner_schedule_certificate(
            certificate,
            certificate.certificate_document_sha256,
        )
    with pytest.raises(ScheduleCertificateCompletedOutcomeError):
        repository.apply_owner_schedule_certificate(
            certificate,
            certificate.certificate_document_sha256,
        )


def test_manual_reobservation_confirms_but_different_manual_fact_conflicts(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    initialize_schema(paths)
    repository = SQLiteCanonicalScheduleAuthorityRepository(paths)
    first = _certificate()
    repository.apply_owner_schedule_certificate(
        first,
        first.certificate_document_sha256,
    )
    original = _schedule_snapshot(paths, "9001")
    reobserved = _certificate(variant="reobserved")
    confirmed = repository.apply_owner_schedule_certificate(
        reobserved,
        reobserved.certificate_document_sha256,
    )
    conflicting = _certificate(
        local_time="21:15:00",
        variant="conflicting-manual",
        reason="OFFICIAL_TIME_CHANGE",
    )

    assert confirmed.disposition is ManualScheduleCertificateDisposition.CONFIRMED
    with pytest.raises(ScheduleCertificateConflictError):
        repository.apply_owner_schedule_certificate(
            conflicting,
            conflicting.certificate_document_sha256,
        )
    assert _schedule_snapshot(paths, "9001") == original
    with open_database(paths, read_only=True) as connection:
        rows = connection.execute(
            """
            SELECT event_kind, disposition, certificate_document_sha256
            FROM draw_schedule_authority_evidence
            WHERE lottery_type = 'DAILY_539' AND draw_number = '9001'
            ORDER BY id
            """
        ).fetchall()
    assert [row[:2] for row in rows] == [
        ("MANUAL_CERTIFICATE", "INSERTED"),
        ("MANUAL_CERTIFICATE", "CONFIRMED"),
        ("SOURCE_CONFLICT", "CONFLICT"),
    ]
    assert len({row[2] for row in rows}) == 3


def test_prevalidated_time_change_veto_can_be_resolved_only_by_later_explicit_fact(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    veto_observed_at = datetime(2099, 1, 1, 0, 30, tzinfo=UTC)
    veto = AuthoritativeScheduleVeto(
        lottery_type=LotteryType.DAILY_539,
        official_game_code=T539_SCHEDULE_GAME_CODE,
        draw_number="9001",
        exception_kind=ScheduleExceptionKind.TIME_CHANGE,
        source=TargetSourceProvenance(
            source_id="TAIWAN_LOTTERY_OFFICIAL_EXCEPTION_NOTICE",
            source_version="fixture-v1",
            source_locator="https://www.taiwanlottery.com/announcement/9001-time",
            source_sha256="e" * 64,
            observed_at=veto_observed_at,
        ),
    )
    fetched = parse_official_t539_p638_schedule(
        _official_body(
            _official_row(T539_SCHEDULE_GAME_CODE, "9001", "20990102"),
            _official_row(P638_SCHEDULE_GAME_CODE, "8001", "20990103"),
        ),
        observed_at=veto_observed_at,
        active_vetoes=(veto,),
    )
    repository = SQLiteCanonicalScheduleAuthorityRepository(paths)
    repository.apply_canonical_schedule_authority(fetched)
    assert SQLiteFutureDrawIdentityReader(paths).get_scheduled_draw(
        LotteryType.DAILY_539,
        "9001",
    ) is None
    certificate = _certificate(
        local_time="21:15:00",
        variant="explicit-time-change",
        reason="OFFICIAL_TIME_CHANGE",
    )

    result = repository.apply_owner_schedule_certificate(
        certificate,
        certificate.certificate_document_sha256,
    )

    assert result.disposition is ManualScheduleCertificateDisposition.INSERTED
    resolved = SQLiteFutureDrawIdentityReader(paths).find_earliest_unpopulated_future(
        LotteryType.DAILY_539,
        datetime(2099, 1, 1, tzinfo=UTC),
    )
    assert resolved is not None
    assert resolved.announcement.scheduled_at.isoformat() == "2099-01-02T13:15:00+00:00"
