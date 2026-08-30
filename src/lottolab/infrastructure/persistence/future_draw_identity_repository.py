"""SQLite future-draw identity readers and owner-only manual supplement writer."""

from __future__ import annotations

import re
import sqlite3
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from urllib.parse import urlsplit

from lottolab.application.future_draw_identity import (
    FutureDrawIdentityConflictError,
    FutureDrawIdentityNotFutureError,
    FutureDrawIdentityPreviewConflictError,
    FutureDrawIdentityUnavailableError,
    ManualFutureDrawIdentitySupplementPreview,
    ManualFutureDrawIdentitySupplementResult,
    OwnerCertifiedFutureDrawIdentityInput,
    ScheduledDrawIdentityRecord,
    ScheduledDrawOutcomeState,
    normalized_announcement_sha256,
)
from lottolab.application.schedule_certificate import (
    OWNER_SCHEDULE_CERTIFICATE_SCHEMA_VERSION,
    ManualScheduleCertificateDisposition,
    ManualScheduleCertificatePreview,
    ManualScheduleCertificateResult,
    OwnerScheduleCertificate,
    ScheduleCertificateCompletedOutcomeError,
    ScheduleCertificateConflictError,
    ScheduleCertificateInputError,
    ScheduleCertificateUnavailableError,
)
from lottolab.application.schedule_sync import (
    CANONICAL_NORMAL_DRAW_LOCAL_TIME,
    CANONICAL_SCHEDULE_AUTHORITY_PARSER_VERSION,
    SCHEDULE_SYNC_PARSER_VERSION,
    AuthoritativeScheduleVeto,
    CanonicalScheduleAuthorityFetchResult,
    CanonicalScheduleAuthorityGameSyncResult,
    CanonicalScheduleAuthoritySyncResult,
    CanonicalScheduleFact,
    CanonicalScheduleSyncConflictError,
    OfficialGameScheduleAuthority,
    OfficialScheduleFetchResult,
    OfficialScheduleSyncResult,
    ScheduleAuthorityApplyStatus,
    ScheduleAuthorityStatus,
    expected_schedule_game_code,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.ingestion import (
    IngestionItemDisposition,
    IngestionOperationType,
    IngestionRunStatus,
)
from lottolab.domain.pre_outcome_target import TargetAnnouncement, TargetSourceProvenance
from lottolab.domain.prospective_observer import ObservationTarget
from lottolab.infrastructure.persistence.draw_schema import (
    CURRENT_SCHEMA_VERSION,
    LocalDataError,
    LocalDataPaths,
    SchemaMigrationError,
    initialize_schema,
    open_database,
    verify_schema_read_only,
)

MANUAL_FUTURE_DRAW_IDENTITY_PARSER_VERSION = "lottolab-future-draw-identity-json-v1"
OFFICIAL_SCHEDULE_SOURCE_ID = "TAIWAN_LOTTERY_OFFICIAL_SCHEDULE"
OFFICIAL_SCHEDULE_SOURCE_VERSION = "taiwan-lottery-official-schedule-v1"
SCHEDULE_TIMEZONE = "Asia/Taipei"

_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)
_DRAW_NUMBER = re.compile(r"[0-9]{1,32}", flags=re.ASCII)
_MAX_OFFICIAL_SCHEDULE_ANNOUNCEMENTS = 1024
_OFFICIAL_SCHEDULE_HOSTS = frozenset({"www.taiwanlottery.com", "api.taiwanlottery.com"})


class SQLiteFutureDrawIdentityReader:
    """Read immutable schedules and derive outcome state from completed draws."""

    def __init__(self, paths: LocalDataPaths) -> None:
        self._paths = paths

    def get_scheduled_draw(
        self,
        lottery_type: LotteryType,
        draw_number: str,
    ) -> ScheduledDrawIdentityRecord | None:
        _require_lottery_type(lottery_type)
        _require_draw_number(draw_number)
        try:
            if not verify_schema_read_only(self._paths):
                return None
            with open_database(self._paths, read_only=True) as connection:
                _require_current_schema(connection)
                connection.execute("BEGIN")
                try:
                    record = _get_scheduled_draw(connection, lottery_type, draw_number)
                finally:
                    connection.rollback()
            return record
        except (
            LocalDataError,
            SchemaMigrationError,
            sqlite3.DatabaseError,
            TypeError,
            ValueError,
        ) as exc:
            raise FutureDrawIdentityUnavailableError(
                "canonical future draw identity is unavailable"
            ) from exc

    def find_earliest_unpopulated_future(
        self,
        lottery_type: LotteryType,
        as_of: datetime,
    ) -> ScheduledDrawIdentityRecord | None:
        _require_lottery_type(lottery_type)
        _require_utc(as_of, "as_of")
        try:
            if not verify_schema_read_only(self._paths):
                return None
            with open_database(self._paths, read_only=True) as connection:
                _require_current_schema(connection)
                connection.execute("BEGIN")
                try:
                    _reject_cross_table_date_mismatch(connection)
                    row = connection.execute(
                        """
                        SELECT s.*, d.id AS outcome_draw_internal_id
                        FROM draw_schedules AS s
                        LEFT JOIN draws AS d
                               ON d.lottery_type = s.lottery_type
                              AND d.draw_number = s.draw_number
                        WHERE s.lottery_type = ?
                          AND s.scheduled_at > ?
                          AND d.id IS NULL
                          AND NOT EXISTS (
                              SELECT 1
                              FROM draw_schedule_authority_evidence AS e
                              WHERE e.lottery_type = s.lottery_type
                                AND (e.draw_number IS NULL OR e.draw_number = s.draw_number)
                                AND (
                                    e.event_kind IN (
                                        'SOURCE_CONFLICT', 'CANCELLATION'
                                    )
                                    OR (
                                        e.event_kind IN (
                                            'MISSING_SCHEDULE', 'INCOMPLETE_AUTHORITY',
                                            'POSTPONEMENT', 'TIME_CHANGE'
                                        )
                                        AND e.source_observed_at > s.source_observed_at
                                        AND NOT EXISTS (
                                            SELECT 1
                                            FROM draw_schedule_authority_evidence AS accepted
                                            WHERE accepted.lottery_type = s.lottery_type
                                              AND accepted.draw_number = s.draw_number
                                              AND accepted.event_kind IN (
                                                  'OFFICIAL_OBSERVATION',
                                                  'MANUAL_CERTIFICATE'
                                              )
                                              AND accepted.disposition IN (
                                                  'INSERTED', 'REOBSERVED', 'CONFIRMED'
                                              )
                                              AND accepted.id > e.id
                                        )
                                    )
                                )
                          )
                        ORDER BY s.scheduled_at ASC,
                                 CAST(s.draw_number AS INTEGER) ASC,
                                 s.draw_number ASC
                        LIMIT 1
                        """,
                        (lottery_type.value, _format_utc(as_of)),
                    ).fetchone()
                finally:
                    connection.rollback()
            return None if row is None else _scheduled_record(row)
        except (
            LocalDataError,
            SchemaMigrationError,
            sqlite3.DatabaseError,
            TypeError,
            ValueError,
        ) as exc:
            raise FutureDrawIdentityUnavailableError(
                "canonical future draw identity is unavailable"
            ) from exc

    def find_earliest_unpopulated_due(
        self,
        lottery_type: LotteryType,
        as_of: datetime,
    ) -> ScheduledDrawIdentityRecord | None:
        """Return the earliest explicit due schedule without a completed outcome."""

        _require_lottery_type(lottery_type)
        _require_utc(as_of, "as_of")
        try:
            if not verify_schema_read_only(self._paths):
                return None
            with open_database(self._paths, read_only=True) as connection:
                _require_current_schema(connection)
                connection.execute("BEGIN")
                try:
                    _reject_cross_table_date_mismatch(connection)
                    row = connection.execute(
                        """
                        SELECT s.*, d.id AS outcome_draw_internal_id
                        FROM draw_schedules AS s
                        LEFT JOIN draws AS d
                               ON d.lottery_type = s.lottery_type
                              AND d.draw_number = s.draw_number
                        WHERE s.lottery_type = ?
                          AND s.scheduled_at <= ?
                          AND d.id IS NULL
                          AND NOT EXISTS (
                              SELECT 1
                              FROM draw_schedule_authority_evidence AS e
                              WHERE e.lottery_type = s.lottery_type
                                AND (e.draw_number IS NULL OR e.draw_number = s.draw_number)
                                AND (
                                    e.event_kind IN (
                                        'SOURCE_CONFLICT', 'CANCELLATION'
                                    )
                                    OR (
                                        e.event_kind IN (
                                            'MISSING_SCHEDULE', 'INCOMPLETE_AUTHORITY',
                                            'POSTPONEMENT', 'TIME_CHANGE'
                                        )
                                        AND e.source_observed_at > s.source_observed_at
                                        AND NOT EXISTS (
                                            SELECT 1
                                            FROM draw_schedule_authority_evidence AS accepted
                                            WHERE accepted.lottery_type = s.lottery_type
                                              AND accepted.draw_number = s.draw_number
                                              AND accepted.event_kind IN (
                                                  'OFFICIAL_OBSERVATION',
                                                  'MANUAL_CERTIFICATE'
                                              )
                                              AND accepted.disposition IN (
                                                  'INSERTED', 'REOBSERVED', 'CONFIRMED'
                                              )
                                              AND accepted.id > e.id
                                        )
                                    )
                                )
                          )
                        ORDER BY s.scheduled_at ASC,
                                 CAST(s.draw_number AS INTEGER) ASC,
                                 s.draw_number ASC
                        LIMIT 1
                        """,
                        (lottery_type.value, _format_utc(as_of)),
                    ).fetchone()
                finally:
                    connection.rollback()
            return None if row is None else _scheduled_record(row)
        except (
            LocalDataError,
            SchemaMigrationError,
            sqlite3.DatabaseError,
            TypeError,
            ValueError,
        ) as exc:
            raise FutureDrawIdentityUnavailableError(
                "canonical future draw identity is unavailable"
            ) from exc


@dataclass(frozen=True, slots=True)
class _ScheduleDecision:
    announcement: TargetAnnouncement
    normalized_hash: str
    disposition: IngestionItemDisposition
    message: str


class SQLiteOfficialScheduleSyncRepository:
    """Atomically persist bounded official schedule identities and their audit."""

    def __init__(self, paths: LocalDataPaths) -> None:
        self._paths = paths

    def apply_official_schedule_sync(
        self,
        fetched: OfficialScheduleFetchResult,
    ) -> OfficialScheduleSyncResult:
        run_id = str(uuid.uuid4())
        decisions: tuple[_ScheduleDecision, ...] = ()
        status = IngestionRunStatus.FAILED
        try:
            _validate_official_schedule_fetch(fetched)
            timestamp = fetched.observed_at
            initialize_schema(self._paths)
            with open_database(self._paths) as connection:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    decisions = _plan_schedule_decisions(connection, fetched)
                    has_conflict = any(
                        decision.disposition is IngestionItemDisposition.CONFLICT
                        for decision in decisions
                    )
                    if has_conflict:
                        decisions = tuple(
                            replace(
                                decision,
                                disposition=(
                                    IngestionItemDisposition.FAILED
                                    if decision.disposition is IngestionItemDisposition.INSERTED
                                    else decision.disposition
                                ),
                                message=(
                                    "Batch rejected because another official schedule "
                                    "identity conflicts."
                                    if decision.disposition is IngestionItemDisposition.INSERTED
                                    else decision.message
                                ),
                            )
                            for decision in decisions
                        )
                    status = (
                        IngestionRunStatus.FAILED if has_conflict else IngestionRunStatus.SUCCESS
                    )
                    _insert_schedule_sync_audit(
                        connection,
                        fetched=fetched,
                        run_id=run_id,
                        timestamp=timestamp,
                        decisions=decisions,
                        status=status,
                        error_summary=(
                            "Official schedule batch contains a canonical identity conflict."
                            if has_conflict
                            else None
                        ),
                    )
                    if not has_conflict:
                        for decision in decisions:
                            if decision.disposition is IngestionItemDisposition.INSERTED:
                                _insert_schedule(
                                    connection,
                                    announcement=decision.announcement,
                                    normalized_hash=decision.normalized_hash,
                                    run_id=run_id,
                                    timestamp=timestamp,
                                )
                    connection.commit()
                except BaseException:
                    if connection.in_transaction:
                        connection.rollback()
                    raise
        except CanonicalScheduleSyncConflictError:
            raise
        except (
            LocalDataError,
            SchemaMigrationError,
            sqlite3.DatabaseError,
            TypeError,
            ValueError,
        ) as exc:
            raise FutureDrawIdentityUnavailableError(
                "official schedule synchronization is unavailable"
            ) from exc

        result = _schedule_sync_result(
            fetched,
            run_id=run_id,
            status=status,
            decisions=decisions,
        )
        if status is IngestionRunStatus.FAILED:
            raise CanonicalScheduleSyncConflictError(result)
        return result


@dataclass(frozen=True, slots=True)
class _CanonicalAuthorityDecision:
    fact: CanonicalScheduleFact
    disposition: IngestionItemDisposition
    message: str
    existing_schedule_id: int | None


class SQLiteCanonicalScheduleAuthorityRepository:
    """Persist T539/P638 authority in independently committed game transactions."""

    def __init__(self, paths: LocalDataPaths) -> None:
        self._paths = paths

    def apply_canonical_schedule_authority(
        self,
        fetched: CanonicalScheduleAuthorityFetchResult,
    ) -> CanonicalScheduleAuthoritySyncResult:
        try:
            _validate_canonical_authority_fetch(fetched)
            initialize_schema(self._paths)
            results: list[CanonicalScheduleAuthorityGameSyncResult] = []
            with open_database(self._paths) as connection:
                for game in fetched.games:
                    results.append(
                        _apply_canonical_game_authority(
                            connection,
                            fetched=fetched,
                            game=game,
                        )
                    )
            return CanonicalScheduleAuthoritySyncResult(
                source_payload_sha256=fetched.source_payload_sha256,
                observed_at=fetched.observed_at,
                game_results=tuple(results),
            )
        except (
            LocalDataError,
            SchemaMigrationError,
            sqlite3.DatabaseError,
            TypeError,
            ValueError,
        ) as exc:
            raise FutureDrawIdentityUnavailableError(
                "canonical T539/P638 schedule authority is unavailable"
            ) from exc

    def preview_owner_schedule_certificate(
        self,
        certificate: OwnerScheduleCertificate,
        expected_document_sha256: str,
    ) -> ManualScheduleCertificatePreview:
        """Classify one exact certificate using a zero-write read transaction."""

        _validate_owner_schedule_certificate_request(
            certificate,
            expected_document_sha256,
        )
        try:
            if not verify_schema_read_only(self._paths):
                raise ScheduleCertificateUnavailableError(
                    "canonical draw database does not exist"
                )
            with open_database(self._paths, read_only=True) as connection:
                _require_current_schema(connection)
                connection.execute("BEGIN")
                try:
                    decision = _classify_owner_schedule_certificate(
                        connection,
                        certificate,
                    )
                finally:
                    connection.rollback()
        except (
            ScheduleCertificateCompletedOutcomeError,
            ScheduleCertificateConflictError,
            ScheduleCertificateUnavailableError,
        ):
            raise
        except (
            LocalDataError,
            SchemaMigrationError,
            sqlite3.DatabaseError,
            TypeError,
            ValueError,
        ) as exc:
            raise ScheduleCertificateUnavailableError(
                "schedule certificate preview is unavailable"
            ) from exc
        if decision.disposition is ManualScheduleCertificateDisposition.CONFLICT:
            raise ScheduleCertificateConflictError()
        return ManualScheduleCertificatePreview(
            certificate=certificate,
            disposition=decision.disposition,
            zero_write=True,
        )

    def apply_owner_schedule_certificate(
        self,
        certificate: OwnerScheduleCertificate,
        expected_document_sha256: str,
    ) -> ManualScheduleCertificateResult:
        """Explicitly apply one certificate after transactional revalidation."""

        _validate_owner_schedule_certificate_request(
            certificate,
            expected_document_sha256,
        )
        try:
            if not verify_schema_read_only(self._paths):
                raise ScheduleCertificateUnavailableError(
                    "canonical draw database does not exist"
                )
            with open_database(self._paths) as connection:
                _require_current_schema(connection)
                result = _apply_owner_schedule_certificate_transaction(
                    connection,
                    certificate,
                )
        except (
            ScheduleCertificateCompletedOutcomeError,
            ScheduleCertificateConflictError,
            ScheduleCertificateUnavailableError,
        ):
            raise
        except (
            LocalDataError,
            SchemaMigrationError,
            sqlite3.DatabaseError,
            TypeError,
            ValueError,
        ) as exc:
            raise ScheduleCertificateUnavailableError(
                "schedule certificate application is unavailable"
            ) from exc
        if result.disposition is ManualScheduleCertificateDisposition.CONFLICT:
            raise ScheduleCertificateConflictError(result)
        return result


@dataclass(frozen=True, slots=True)
class _ManualCertificateDecision:
    disposition: ManualScheduleCertificateDisposition
    event_kind: str
    detail_code: str
    schedule_id: int | None


def _validate_owner_schedule_certificate_request(
    certificate: OwnerScheduleCertificate,
    expected_document_sha256: str,
) -> None:
    if type(certificate) is not OwnerScheduleCertificate:
        raise ScheduleCertificateInputError(
            "certificate must be a validated OwnerScheduleCertificate"
        )
    if (
        type(expected_document_sha256) is not str
        or _SHA256.fullmatch(expected_document_sha256) is None
    ):
        raise ScheduleCertificateInputError(
            "expected certificate SHA-256 must be lowercase hexadecimal"
        )
    if certificate.certificate_document_sha256 != expected_document_sha256:
        raise ScheduleCertificateInputError(
            "certificate document SHA-256 does not match the explicit pin"
        )


def _classify_owner_schedule_certificate(
    connection: sqlite3.Connection,
    certificate: OwnerScheduleCertificate,
) -> _ManualCertificateDecision:
    target = certificate.fact.announcement.target
    _reject_cross_table_date_mismatch(connection)
    if _completed_draw_exists(connection, target):
        raise ScheduleCertificateCompletedOutcomeError(
            "a completed official outcome already occupies this draw identity"
        )
    if _has_permanent_schedule_authority_block(connection, target):
        return _ManualCertificateDecision(
            disposition=ManualScheduleCertificateDisposition.CONFLICT,
            event_kind="MANUAL_CERTIFICATE",
            detail_code="EXISTING_OFFICIAL_CONFLICT_OR_CANCELLATION",
            schedule_id=_schedule_id_for_identity(
                connection,
                target.lottery_type,
                target.draw_number,
            ),
        )

    stored = _stored_canonical_authority_material(connection, target)
    if stored is not None:
        schedule_id = _positive_integer(stored[0])
        if _stored_authority_matches_fact(stored, certificate.fact):
            return _ManualCertificateDecision(
                disposition=ManualScheduleCertificateDisposition.CONFIRMED,
                event_kind="MANUAL_CERTIFICATE",
                detail_code="FULL_IMMUTABLE_SCHEDULE_FACT_CONFIRMED",
                schedule_id=schedule_id,
            )
        return _ManualCertificateDecision(
            disposition=ManualScheduleCertificateDisposition.CONFLICT,
            event_kind="SOURCE_CONFLICT",
            detail_code="CERTIFICATE_DIFFERS_FROM_IMMUTABLE_SCHEDULE_FACT",
            schedule_id=schedule_id,
        )

    if _current_complete_official_authority_blocks_manual(connection, certificate):
        return _ManualCertificateDecision(
            disposition=ManualScheduleCertificateDisposition.CONFLICT,
            event_kind="MANUAL_CERTIFICATE",
            detail_code="COMPLETE_OFFICIAL_AUTHORITY_OUTRANKS_MANUAL",
            schedule_id=None,
        )
    return _ManualCertificateDecision(
        disposition=ManualScheduleCertificateDisposition.INSERTED,
        event_kind="MANUAL_CERTIFICATE",
        detail_code="VALID_OWNER_CERTIFICATE_FALLBACK",
        schedule_id=None,
    )


def _has_permanent_schedule_authority_block(
    connection: sqlite3.Connection,
    target: ObservationTarget,
) -> bool:
    return (
        connection.execute(
            """
            SELECT 1
            FROM draw_schedule_authority_evidence
            WHERE lottery_type = ?
              AND event_kind IN ('SOURCE_CONFLICT', 'CANCELLATION')
              AND (draw_number IS NULL OR draw_number = ?)
            LIMIT 1
            """,
            (target.lottery_type.value, target.draw_number),
        ).fetchone()
        is not None
    )


def _current_complete_official_authority_blocks_manual(
    connection: sqlite3.Connection,
    certificate: OwnerScheduleCertificate,
) -> bool:
    row = connection.execute(
        """
        SELECT event_kind, disposition, scheduled_at
        FROM draw_schedule_authority_evidence
        WHERE lottery_type = ?
          AND certificate_input_sha256 IS NULL
        ORDER BY source_observed_at DESC, id DESC
        LIMIT 1
        """,
        (certificate.fact.announcement.target.lottery_type.value,),
    ).fetchone()
    if row is None:
        return False
    event_kind, disposition, scheduled_at = tuple(row)
    if event_kind != "OFFICIAL_OBSERVATION" or disposition not in {
        "INSERTED",
        "REOBSERVED",
    }:
        return False
    if scheduled_at is None:
        raise ValueError("complete official authority lacks scheduled_at")
    return _datetime_value(scheduled_at, "official authority scheduled_at") > (
        certificate.certified_at
    )


def _apply_owner_schedule_certificate_transaction(
    connection: sqlite3.Connection,
    certificate: OwnerScheduleCertificate,
) -> ManualScheduleCertificateResult:
    run_id = str(uuid.uuid4())
    timestamp = datetime.now(UTC)
    connection.execute("BEGIN IMMEDIATE")
    try:
        decision = _classify_owner_schedule_certificate(connection, certificate)
        status = (
            IngestionRunStatus.FAILED
            if decision.disposition is ManualScheduleCertificateDisposition.CONFLICT
            else IngestionRunStatus.SUCCESS
        )
        _insert_manual_schedule_certificate_audit(
            connection,
            certificate=certificate,
            decision=decision,
            run_id=run_id,
            status=status,
            timestamp=timestamp,
        )
        schedule_id = decision.schedule_id
        if decision.disposition is ManualScheduleCertificateDisposition.INSERTED:
            _insert_schedule(
                connection,
                announcement=certificate.fact.announcement,
                normalized_hash=normalized_announcement_sha256(
                    certificate.fact.announcement
                ),
                run_id=run_id,
                timestamp=timestamp,
            )
            schedule_id = _insert_canonical_schedule_fact(
                connection,
                certificate.fact,
                authority_origin="MANUAL",
            )
        _insert_authority_evidence(
            connection,
            schedule_id=schedule_id,
            lottery_type=certificate.fact.announcement.target.lottery_type,
            official_game_code=certificate.fact.official_game_code,
            draw_number=certificate.fact.announcement.target.draw_number,
            draw_date=certificate.fact.announcement.target.draw_date,
            fact=certificate.fact,
            event_kind=decision.event_kind,
            disposition=decision.disposition.value,
            detail_code=decision.detail_code,
            source=certificate.fact.announcement.source,
            run_id=run_id,
            created_at=timestamp,
            certificate_input_sha256=certificate.certificate_input_sha256,
            certificate_document_sha256=certificate.certificate_document_sha256,
            certified_at=certificate.certified_at,
            certifying_authority=certificate.certifying_authority,
            certification_reason=certificate.certification_reason.value,
            supporting_artifact_type=certificate.supporting_artifact_type.value,
        )
        connection.commit()
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise

    counts = {
        ManualScheduleCertificateDisposition.INSERTED: (1, 0, 0),
        ManualScheduleCertificateDisposition.CONFIRMED: (0, 1, 0),
        ManualScheduleCertificateDisposition.CONFLICT: (0, 0, 1),
    }[decision.disposition]
    return ManualScheduleCertificateResult(
        run_id=run_id,
        status=status,
        certificate=certificate,
        disposition=decision.disposition,
        inserted_count=counts[0],
        confirmed_count=counts[1],
        conflict_count=counts[2],
    )


def _insert_manual_schedule_certificate_audit(
    connection: sqlite3.Connection,
    *,
    certificate: OwnerScheduleCertificate,
    decision: _ManualCertificateDecision,
    run_id: str,
    status: IngestionRunStatus,
    timestamp: datetime,
) -> None:
    target = certificate.fact.announcement.target
    inserted_count = int(
        decision.disposition is ManualScheduleCertificateDisposition.INSERTED
    )
    skipped_count = int(
        decision.disposition is ManualScheduleCertificateDisposition.CONFIRMED
    )
    conflict_count = int(
        decision.disposition is ManualScheduleCertificateDisposition.CONFLICT
    )
    timestamp_text = _format_utc(timestamp)
    connection.execute(
        """
        INSERT INTO ingestion_runs (
            id, operation_type, status, lottery_type, source_filename,
            source_sha256, parser_version, total_count, inserted_count,
            skipped_count, conflict_count, failed_count, first_draw_number,
            last_draw_number, started_at, completed_at, error_summary
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, 0, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            IngestionOperationType.MANUAL_SCHEDULE_CERTIFICATE.value,
            status.value,
            target.lottery_type.value,
            certificate.source_filename,
            certificate.certificate_document_sha256,
            OWNER_SCHEDULE_CERTIFICATE_SCHEMA_VERSION,
            inserted_count,
            skipped_count,
            conflict_count,
            target.draw_number,
            target.draw_number,
            timestamp_text,
            timestamp_text,
            (
                "Owner schedule certificate failed closed."
                if status is IngestionRunStatus.FAILED
                else None
            ),
        ),
    )
    connection.execute(
        """
        INSERT INTO ingestion_run_context (
            ingestion_run_id, trigger, provider, provider_version,
            requested_start, requested_end, resolved_start, resolved_end,
            fetched_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (
            run_id,
            IngestionOperationType.MANUAL_SCHEDULE_CERTIFICATE.value,
            certificate.fact.announcement.source.source_id,
            certificate.fact.announcement.source.source_version,
            target.draw_date.isoformat(),
            target.draw_date.isoformat(),
            target.draw_date.isoformat(),
            target.draw_date.isoformat(),
        ),
    )
    disposition = {
        ManualScheduleCertificateDisposition.INSERTED: (
            IngestionItemDisposition.INSERTED
        ),
        ManualScheduleCertificateDisposition.CONFIRMED: (
            IngestionItemDisposition.SKIPPED_DUPLICATE
        ),
        ManualScheduleCertificateDisposition.CONFLICT: (
            IngestionItemDisposition.CONFLICT
        ),
    }[decision.disposition]
    connection.execute(
        """
        INSERT INTO ingestion_items (
            ingestion_run_id, source_row_number, lottery_type, draw_number,
            disposition, normalized_record_hash, message
        ) VALUES (?, 1, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            target.lottery_type.value,
            target.draw_number,
            disposition.value,
            certificate.fact.immutable_schedule_sha256,
            decision.detail_code,
        ),
    )


class SQLiteManualFutureDrawIdentitySupplementRepository:
    """Preview and commit one explicit owner-certified Big Lotto schedule identity."""

    def __init__(self, paths: LocalDataPaths) -> None:
        self._paths = paths

    def preview_owner_certified_supplement(
        self,
        parsed_input: OwnerCertifiedFutureDrawIdentityInput,
        selected_target: TargetAnnouncement,
        expected_sha256: str,
    ) -> ManualFutureDrawIdentitySupplementPreview:
        normalized_hash = _validate_manual_request(
            parsed_input,
            selected_target,
            expected_sha256,
        )
        try:
            if not verify_schema_read_only(self._paths):
                raise FutureDrawIdentityUnavailableError("canonical draw database does not exist")
            with open_database(self._paths, read_only=True) as connection:
                _require_current_schema(connection)
                connection.execute("BEGIN")
                try:
                    if _completed_draw_exists(connection, selected_target.target):
                        raise FutureDrawIdentityNotFutureError(
                            "selected draw already has a completed outcome"
                        )
                    existing = _get_scheduled_draw(
                        connection,
                        selected_target.target.lottery_type,
                        selected_target.target.draw_number,
                    )
                finally:
                    connection.rollback()
        except (FutureDrawIdentityNotFutureError, FutureDrawIdentityUnavailableError):
            raise
        except (
            LocalDataError,
            SchemaMigrationError,
            sqlite3.DatabaseError,
            TypeError,
            ValueError,
        ) as exc:
            raise FutureDrawIdentityUnavailableError(
                "canonical future draw identity preview is unavailable"
            ) from exc

        if existing is None:
            disposition = IngestionItemDisposition.INSERTED
        elif _is_exact_schedule(existing, selected_target, normalized_hash):
            disposition = IngestionItemDisposition.SKIPPED_DUPLICATE
        else:
            raise FutureDrawIdentityPreviewConflictError(
                "selected identity conflicts with the immutable stored schedule"
            )
        return ManualFutureDrawIdentitySupplementPreview(
            announcement=selected_target,
            normalized_announcement_hash=normalized_hash,
            input_sha256=parsed_input.input_sha256,
            disposition=disposition,
            zero_write=True,
        )

    def apply_owner_certified_supplement(
        self,
        parsed_input: OwnerCertifiedFutureDrawIdentityInput,
        selected_target: TargetAnnouncement,
        expected_sha256: str,
    ) -> ManualFutureDrawIdentitySupplementResult:
        normalized_hash = _validate_manual_request(
            parsed_input,
            selected_target,
            expected_sha256,
        )
        try:
            if not verify_schema_read_only(self._paths):
                raise FutureDrawIdentityUnavailableError("canonical draw database does not exist")
            with open_database(self._paths) as connection:
                _require_current_schema(connection)
                result = _apply_manual_transaction(
                    connection,
                    parsed_input=parsed_input,
                    selected_target=selected_target,
                    normalized_hash=normalized_hash,
                )
        except (
            FutureDrawIdentityConflictError,
            FutureDrawIdentityNotFutureError,
            FutureDrawIdentityUnavailableError,
        ):
            raise
        except (
            LocalDataError,
            SchemaMigrationError,
            sqlite3.DatabaseError,
            TypeError,
            ValueError,
        ) as exc:
            raise FutureDrawIdentityUnavailableError(
                "canonical future draw identity commit is unavailable"
            ) from exc
        if result.disposition is IngestionItemDisposition.CONFLICT:
            raise FutureDrawIdentityConflictError(result)
        return result


def _apply_manual_transaction(
    connection: sqlite3.Connection,
    *,
    parsed_input: OwnerCertifiedFutureDrawIdentityInput,
    selected_target: TargetAnnouncement,
    normalized_hash: str,
) -> ManualFutureDrawIdentitySupplementResult:
    run_id = str(uuid.uuid4())
    timestamp = datetime.now(UTC)
    target = selected_target.target
    connection.execute("BEGIN IMMEDIATE")
    try:
        if _completed_draw_exists(connection, target):
            raise FutureDrawIdentityNotFutureError("selected draw already has a completed outcome")
        existing = _get_scheduled_draw(
            connection,
            target.lottery_type,
            target.draw_number,
        )
        if existing is None:
            disposition = IngestionItemDisposition.INSERTED
            status = IngestionRunStatus.SUCCESS
            counts = (1, 0, 0)
            message = "Inserted owner-certified future draw identity."
            error_summary = None
        elif _is_exact_schedule(existing, selected_target, normalized_hash):
            disposition = IngestionItemDisposition.SKIPPED_DUPLICATE
            status = IngestionRunStatus.SUCCESS
            counts = (0, 1, 0)
            message = "Exact immutable schedule identity already exists."
            error_summary = None
        else:
            disposition = IngestionItemDisposition.CONFLICT
            status = IngestionRunStatus.FAILED
            counts = (0, 0, 1)
            message = "Stored immutable schedule identity differs."
            error_summary = "Future draw identity supplement conflicts with stored authority."

        inserted_count, skipped_count, conflict_count = counts
        timestamp_text = _format_utc(timestamp)
        connection.execute(
            """
            INSERT INTO ingestion_runs (
                id, operation_type, status, lottery_type, source_filename,
                source_sha256, parser_version, total_count, inserted_count,
                skipped_count, conflict_count, failed_count, first_draw_number,
                last_draw_number, started_at, completed_at, error_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, 0, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                IngestionOperationType.MANUAL_FUTURE_IDENTITY_SUPPLEMENT.value,
                status.value,
                target.lottery_type.value,
                parsed_input.source_filename,
                parsed_input.input_sha256,
                MANUAL_FUTURE_DRAW_IDENTITY_PARSER_VERSION,
                inserted_count,
                skipped_count,
                conflict_count,
                target.draw_number,
                target.draw_number,
                timestamp_text,
                timestamp_text,
                error_summary,
            ),
        )
        connection.execute(
            """
            INSERT INTO ingestion_run_context (
                ingestion_run_id, trigger, provider, provider_version,
                requested_start, requested_end, resolved_start, resolved_end,
                fetched_count
            ) VALUES (?, ?, NULL, NULL, NULL, NULL, NULL, NULL, 1)
            """,
            (
                run_id,
                IngestionOperationType.MANUAL_FUTURE_IDENTITY_SUPPLEMENT.value,
            ),
        )
        connection.execute(
            """
            INSERT INTO ingestion_items (
                ingestion_run_id, source_row_number, lottery_type, draw_number,
                disposition, normalized_record_hash, message
            ) VALUES (?, 1, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                target.lottery_type.value,
                target.draw_number,
                disposition.value,
                normalized_hash,
                message,
            ),
        )
        if disposition is IngestionItemDisposition.INSERTED:
            connection.execute(
                """
                INSERT INTO draw_schedules (
                    lottery_type, draw_number, draw_date, scheduled_at,
                    schedule_timezone, source_id, source_version, source_locator,
                    source_payload_sha256, source_observed_at,
                    normalized_announcement_hash, ingestion_run_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    target.lottery_type.value,
                    target.draw_number,
                    target.draw_date.isoformat(),
                    _format_utc(selected_target.scheduled_at),
                    selected_target.schedule_timezone,
                    selected_target.source.source_id,
                    selected_target.source.source_version,
                    selected_target.source.source_locator,
                    selected_target.source.source_payload_sha256,
                    _format_utc(selected_target.source.observed_at),
                    normalized_hash,
                    run_id,
                    timestamp_text,
                ),
            )
        connection.commit()
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
    return ManualFutureDrawIdentitySupplementResult(
        run_id=run_id,
        status=status,
        announcement=selected_target,
        normalized_announcement_hash=normalized_hash,
        input_sha256=parsed_input.input_sha256,
        disposition=disposition,
        inserted_count=inserted_count,
        skipped_count=skipped_count,
        conflict_count=conflict_count,
    )


def _validate_canonical_authority_fetch(
    fetched: CanonicalScheduleAuthorityFetchResult,
) -> None:
    if type(fetched) is not CanonicalScheduleAuthorityFetchResult:
        raise ValueError("fetched must be a CanonicalScheduleAuthorityFetchResult")
    if fetched.provider_id != OFFICIAL_SCHEDULE_SOURCE_ID:
        raise ValueError("canonical schedule provider identity is invalid")
    if fetched.provider_version != OFFICIAL_SCHEDULE_SOURCE_VERSION:
        raise ValueError("canonical schedule provider version is invalid")
    _validate_official_locator(fetched.source_url)
    _require_utc(fetched.observed_at, "observed_at")
    for game in fetched.games:
        if game.official_game_code != expected_schedule_game_code(game.lottery_type):
            raise ValueError("game authority official_game_code is invalid")
        for fact in game.schedules:
            if fact.source_period_identifier is None:
                raise ValueError("automatic official authority requires drawTerm")
            if fact.scheduled_local_time != CANONICAL_NORMAL_DRAW_LOCAL_TIME:
                raise ValueError("automatic official authority requires the normal draw time")
            if fact.announcement.scheduled_at <= fetched.observed_at:
                raise ValueError("official authority was not observed before scheduled_at")
            _validate_official_schedule_material(fact.announcement)
        for veto in game.vetoes:
            _validate_authoritative_veto(veto)


def _validate_authoritative_veto(veto: AuthoritativeScheduleVeto) -> None:
    if type(veto) is not AuthoritativeScheduleVeto:
        raise ValueError("veto must be AuthoritativeScheduleVeto")
    if veto.official_game_code != expected_schedule_game_code(veto.lottery_type):
        raise ValueError("veto official_game_code is invalid")
    _validate_official_locator(veto.source.source_locator)


def _apply_canonical_game_authority(
    connection: sqlite3.Connection,
    *,
    fetched: CanonicalScheduleAuthorityFetchResult,
    game: OfficialGameScheduleAuthority,
) -> CanonicalScheduleAuthorityGameSyncResult:
    run_id = str(uuid.uuid4())
    connection.execute("BEGIN IMMEDIATE")
    try:
        if game.status is not ScheduleAuthorityStatus.COMPLETE:
            status = (
                IngestionRunStatus.FAILED
                if game.status is ScheduleAuthorityStatus.SOURCE_CONFLICT
                else IngestionRunStatus.SUCCESS
            )
            _insert_canonical_authority_ingestion_audit(
                connection,
                fetched=fetched,
                game=game,
                run_id=run_id,
                decisions=(),
                status=status,
            )
            evidence_count = _record_noncomplete_game_authority(
                connection,
                fetched=fetched,
                game=game,
                run_id=run_id,
            )
            connection.commit()
            apply_status = {
                ScheduleAuthorityStatus.SOURCE_CONFLICT: (ScheduleAuthorityApplyStatus.CONFLICT),
                ScheduleAuthorityStatus.AUTHORITATIVE_VETO: (ScheduleAuthorityApplyStatus.VETOED),
            }.get(game.status, ScheduleAuthorityApplyStatus.NO_AUTHORITY)
            return CanonicalScheduleAuthorityGameSyncResult(
                run_id=run_id,
                lottery_type=game.lottery_type,
                official_game_code=game.official_game_code,
                authority_status=game.status,
                apply_status=apply_status,
                target_draw_numbers=(),
                inserted_count=0,
                reobserved_count=0,
                conflict_count=(1 if game.status is ScheduleAuthorityStatus.SOURCE_CONFLICT else 0),
                evidence_count=evidence_count,
            )

        decisions = _plan_canonical_authority_decisions(connection, game)
        has_conflict = any(
            decision.disposition is IngestionItemDisposition.CONFLICT for decision in decisions
        )
        audited_decisions = tuple(
            replace(
                decision,
                disposition=(
                    IngestionItemDisposition.FAILED
                    if has_conflict and decision.disposition is IngestionItemDisposition.INSERTED
                    else decision.disposition
                ),
                message=(
                    "Game-local batch rejected because another canonical fact conflicts."
                    if has_conflict and decision.disposition is IngestionItemDisposition.INSERTED
                    else decision.message
                ),
            )
            for decision in decisions
        )
        _insert_canonical_authority_ingestion_audit(
            connection,
            fetched=fetched,
            game=game,
            run_id=run_id,
            decisions=audited_decisions,
            status=(IngestionRunStatus.FAILED if has_conflict else IngestionRunStatus.SUCCESS),
        )
        if not has_conflict:
            for decision in audited_decisions:
                if decision.disposition is IngestionItemDisposition.INSERTED:
                    _insert_schedule(
                        connection,
                        announcement=decision.fact.announcement,
                        normalized_hash=normalized_announcement_sha256(decision.fact.announcement),
                        run_id=run_id,
                        timestamp=fetched.observed_at,
                    )
                    _insert_canonical_schedule_fact(connection, decision.fact)

        for decision in audited_decisions:
            _record_canonical_authority_decision(
                connection,
                fetched=fetched,
                decision=decision,
                run_id=run_id,
            )
        connection.commit()
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise

    return CanonicalScheduleAuthorityGameSyncResult(
        run_id=run_id,
        lottery_type=game.lottery_type,
        official_game_code=game.official_game_code,
        authority_status=game.status,
        apply_status=(
            ScheduleAuthorityApplyStatus.CONFLICT
            if has_conflict
            else ScheduleAuthorityApplyStatus.ACCEPTED
        ),
        target_draw_numbers=tuple(
            decision.fact.announcement.target.draw_number for decision in audited_decisions
        ),
        inserted_count=(
            0
            if has_conflict
            else sum(
                decision.disposition is IngestionItemDisposition.INSERTED
                for decision in audited_decisions
            )
        ),
        reobserved_count=sum(
            decision.disposition is IngestionItemDisposition.SKIPPED_DUPLICATE
            for decision in audited_decisions
        ),
        conflict_count=sum(
            decision.disposition is IngestionItemDisposition.CONFLICT
            for decision in audited_decisions
        ),
        evidence_count=len(audited_decisions),
    )


def _plan_canonical_authority_decisions(
    connection: sqlite3.Connection,
    game: OfficialGameScheduleAuthority,
) -> tuple[_CanonicalAuthorityDecision, ...]:
    _reject_cross_table_date_mismatch(connection)
    decisions: list[_CanonicalAuthorityDecision] = []
    for fact in sorted(game.schedules, key=lambda item: _schedule_sort_key(item.announcement)):
        target = fact.announcement.target
        stored = _stored_canonical_authority_material(connection, target)
        if stored is not None:
            schedule_id = _positive_integer(stored[0])
            if _stored_authority_matches_fact(stored, fact):
                disposition = (
                    IngestionItemDisposition.SKIPPED_COMPLETED
                    if _completed_draw_exists(connection, target)
                    else IngestionItemDisposition.SKIPPED_DUPLICATE
                )
                message = (
                    "Completed canonical schedule fact remains authoritative."
                    if disposition is IngestionItemDisposition.SKIPPED_COMPLETED
                    else "Canonical schedule fact re-observed with append-only provenance."
                )
            else:
                disposition = IngestionItemDisposition.CONFLICT
                message = "Stored full immutable schedule fact differs."
            decisions.append(
                _CanonicalAuthorityDecision(
                    fact=fact,
                    disposition=disposition,
                    message=message,
                    existing_schedule_id=schedule_id,
                )
            )
            continue

        completed_date = _completed_draw_date(connection, target)
        if completed_date is None:
            disposition = IngestionItemDisposition.INSERTED
            message = "Inserted complete explicit canonical schedule authority."
        elif completed_date == target.draw_date:
            disposition = IngestionItemDisposition.SKIPPED_COMPLETED
            message = "Completed draw identity is not reintroduced as unresolved."
        else:
            disposition = IngestionItemDisposition.CONFLICT
            message = "Completed draw date conflicts with canonical schedule authority."
        decisions.append(
            _CanonicalAuthorityDecision(
                fact=fact,
                disposition=disposition,
                message=message,
                existing_schedule_id=None,
            )
        )
    return tuple(decisions)


def _stored_canonical_authority_material(
    connection: sqlite3.Connection,
    target: ObservationTarget,
) -> tuple[object, ...] | None:
    row = connection.execute(
        """
        SELECT s.id, f.official_game_code, f.scheduled_local_time,
               f.source_period_identifier, f.immutable_schedule_hash,
               f.authority_origin
        FROM draw_schedules AS s
        LEFT JOIN draw_schedule_facts AS f ON f.schedule_id = s.id
        WHERE s.lottery_type = ? AND s.draw_number = ?
        """,
        (target.lottery_type.value, target.draw_number),
    ).fetchone()
    return None if row is None else tuple(row)


def _stored_authority_matches_fact(
    stored: tuple[object, ...],
    fact: CanonicalScheduleFact,
) -> bool:
    if len(stored) != 6:
        return False
    _, game_code, local_time, period, immutable_hash, origin = stored
    return (
        type(game_code) is int
        and game_code == fact.official_game_code
        and local_time == fact.scheduled_local_time.isoformat(timespec="seconds")
        and period == fact.source_period_identifier
        and immutable_hash == fact.immutable_schedule_sha256
        and origin in {"OFFICIAL", "MANUAL"}
    )


def _insert_canonical_schedule_fact(
    connection: sqlite3.Connection,
    fact: CanonicalScheduleFact,
    *,
    authority_origin: str = "OFFICIAL",
) -> int:
    target = fact.announcement.target
    row = connection.execute(
        """
        SELECT id FROM draw_schedules
        WHERE lottery_type = ? AND draw_number = ?
        """,
        (target.lottery_type.value, target.draw_number),
    ).fetchone()
    if row is None:
        raise ValueError("inserted canonical schedule row is unavailable")
    schedule_id = _positive_integer(row[0])
    connection.execute(
        """
        INSERT INTO draw_schedule_facts (
            schedule_id, official_game_code, scheduled_local_time,
            source_period_identifier, immutable_schedule_hash, authority_origin
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            schedule_id,
            fact.official_game_code,
            fact.scheduled_local_time.isoformat(timespec="seconds"),
            fact.source_period_identifier,
            fact.immutable_schedule_sha256,
            authority_origin,
        ),
    )
    return schedule_id


def _insert_canonical_authority_ingestion_audit(
    connection: sqlite3.Connection,
    *,
    fetched: CanonicalScheduleAuthorityFetchResult,
    game: OfficialGameScheduleAuthority,
    run_id: str,
    decisions: tuple[_CanonicalAuthorityDecision, ...],
    status: IngestionRunStatus,
) -> None:
    inserted_count = sum(
        item.disposition is IngestionItemDisposition.INSERTED for item in decisions
    )
    skipped_count = sum(
        item.disposition
        in {
            IngestionItemDisposition.SKIPPED_DUPLICATE,
            IngestionItemDisposition.SKIPPED_COMPLETED,
        }
        for item in decisions
    )
    conflict_count = sum(
        item.disposition is IngestionItemDisposition.CONFLICT for item in decisions
    )
    failed_count = sum(item.disposition is IngestionItemDisposition.FAILED for item in decisions)
    ordered = tuple(sorted(decisions, key=lambda item: _schedule_sort_key(item.fact.announcement)))
    dates = tuple(item.fact.announcement.target.draw_date for item in ordered)
    if not dates:
        dates = game.evidence_draw_dates
    timestamp_text = _format_utc(fetched.observed_at)
    first_number = None if not ordered else ordered[0].fact.announcement.target.draw_number
    last_number = None if not ordered else ordered[-1].fact.announcement.target.draw_number
    connection.execute(
        """
        INSERT INTO ingestion_runs (
            id, operation_type, status, lottery_type, source_filename,
            source_sha256, parser_version, total_count, inserted_count,
            skipped_count, conflict_count, failed_count, first_draw_number,
            last_draw_number, started_at, completed_at, error_summary
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            IngestionOperationType.OFFICIAL_SCHEDULE_SYNC.value,
            status.value,
            game.lottery_type.value,
            fetched.source_url,
            fetched.source_payload_sha256,
            CANONICAL_SCHEDULE_AUTHORITY_PARSER_VERSION,
            len(decisions),
            inserted_count,
            skipped_count,
            conflict_count,
            failed_count,
            first_number,
            last_number,
            timestamp_text,
            timestamp_text,
            (
                "Canonical game schedule authority failed closed."
                if status is IngestionRunStatus.FAILED
                else None
            ),
        ),
    )
    first_date = None if not dates else min(dates).isoformat()
    last_date = None if not dates else max(dates).isoformat()
    connection.execute(
        """
        INSERT INTO ingestion_run_context (
            ingestion_run_id, trigger, provider, provider_version,
            requested_start, requested_end, resolved_start, resolved_end,
            fetched_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            IngestionOperationType.OFFICIAL_SCHEDULE_SYNC.value,
            fetched.provider_id,
            fetched.provider_version,
            first_date,
            last_date,
            first_date,
            last_date,
            max(len(decisions), len(game.evidence_draw_dates)),
        ),
    )
    for row_number, decision in enumerate(ordered, start=1):
        connection.execute(
            """
            INSERT INTO ingestion_items (
                ingestion_run_id, source_row_number, lottery_type, draw_number,
                disposition, normalized_record_hash, message
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                row_number,
                game.lottery_type.value,
                decision.fact.announcement.target.draw_number,
                decision.disposition.value,
                decision.fact.immutable_schedule_sha256,
                decision.message,
            ),
        )


def _record_noncomplete_game_authority(
    connection: sqlite3.Connection,
    *,
    fetched: CanonicalScheduleAuthorityFetchResult,
    game: OfficialGameScheduleAuthority,
    run_id: str,
) -> int:
    if game.status is ScheduleAuthorityStatus.AUTHORITATIVE_VETO:
        for veto in game.vetoes:
            _insert_authority_evidence(
                connection,
                schedule_id=_schedule_id_for_identity(
                    connection,
                    veto.lottery_type,
                    veto.draw_number,
                ),
                lottery_type=veto.lottery_type,
                official_game_code=veto.official_game_code,
                draw_number=veto.draw_number,
                draw_date=(
                    game.evidence_draw_dates[0] if len(game.evidence_draw_dates) == 1 else None
                ),
                fact=None,
                event_kind=veto.exception_kind.value,
                disposition="VETOED",
                detail_code=game.detail_code,
                source=veto.source,
                run_id=run_id,
                created_at=fetched.observed_at,
            )
        return len(game.vetoes)

    source = TargetSourceProvenance(
        source_id=fetched.provider_id,
        source_version=fetched.provider_version,
        source_locator=fetched.source_url,
        source_sha256=fetched.source_payload_sha256,
        observed_at=fetched.observed_at,
    )
    evidence_dates: tuple[date | None, ...] = (
        tuple(game.evidence_draw_dates) if game.evidence_draw_dates else (None,)
    )
    for draw_date in evidence_dates:
        _insert_authority_evidence(
            connection,
            schedule_id=None,
            lottery_type=game.lottery_type,
            official_game_code=game.official_game_code,
            draw_number=None,
            draw_date=draw_date,
            fact=None,
            event_kind=game.status.value,
            disposition=(
                "CONFLICT"
                if game.status is ScheduleAuthorityStatus.SOURCE_CONFLICT
                else "NO_AUTHORITY"
            ),
            detail_code=game.detail_code,
            source=source,
            run_id=run_id,
            created_at=fetched.observed_at,
        )
    return len(evidence_dates)


def _record_canonical_authority_decision(
    connection: sqlite3.Connection,
    *,
    fetched: CanonicalScheduleAuthorityFetchResult,
    decision: _CanonicalAuthorityDecision,
    run_id: str,
) -> None:
    target = decision.fact.announcement.target
    schedule_id = decision.existing_schedule_id
    if decision.disposition is IngestionItemDisposition.INSERTED:
        schedule_id = _schedule_id_for_identity(
            connection,
            target.lottery_type,
            target.draw_number,
        )
        event_kind = "OFFICIAL_OBSERVATION"
        disposition = "INSERTED"
    elif decision.disposition is IngestionItemDisposition.SKIPPED_DUPLICATE:
        event_kind = "OFFICIAL_OBSERVATION"
        disposition = "REOBSERVED"
    elif decision.disposition is IngestionItemDisposition.SKIPPED_COMPLETED:
        event_kind = "OFFICIAL_OBSERVATION"
        disposition = "COMPLETED_OUTCOME"
    elif decision.disposition is IngestionItemDisposition.CONFLICT:
        event_kind = "SOURCE_CONFLICT"
        disposition = "CONFLICT"
    else:
        event_kind = "OFFICIAL_OBSERVATION"
        disposition = "REJECTED_BATCH_CONFLICT"
    _insert_authority_evidence(
        connection,
        schedule_id=schedule_id,
        lottery_type=target.lottery_type,
        official_game_code=decision.fact.official_game_code,
        draw_number=target.draw_number,
        draw_date=target.draw_date,
        fact=decision.fact,
        event_kind=event_kind,
        disposition=disposition,
        detail_code=decision.message,
        source=decision.fact.announcement.source,
        run_id=run_id,
        created_at=fetched.observed_at,
    )


def _insert_authority_evidence(
    connection: sqlite3.Connection,
    *,
    schedule_id: int | None,
    lottery_type: LotteryType,
    official_game_code: int,
    draw_number: str | None,
    draw_date: date | None,
    fact: CanonicalScheduleFact | None,
    event_kind: str,
    disposition: str,
    detail_code: str,
    source: TargetSourceProvenance,
    run_id: str,
    created_at: datetime,
    certificate_input_sha256: str | None = None,
    certificate_document_sha256: str | None = None,
    certified_at: datetime | None = None,
    certifying_authority: str | None = None,
    certification_reason: str | None = None,
    supporting_artifact_type: str | None = None,
) -> None:
    if fact is None:
        scheduled_local_time = None
        schedule_timezone = None
        scheduled_at = None
        source_period_identifier = None
        immutable_schedule_hash = None
    else:
        scheduled_local_time = fact.scheduled_local_time.isoformat(timespec="seconds")
        schedule_timezone = fact.announcement.schedule_timezone
        scheduled_at = _format_utc(fact.announcement.scheduled_at)
        source_period_identifier = fact.source_period_identifier
        immutable_schedule_hash = fact.immutable_schedule_sha256
    connection.execute(
        """
        INSERT INTO draw_schedule_authority_evidence (
            schedule_id, lottery_type, official_game_code, draw_number,
            draw_date, scheduled_local_time, schedule_timezone, scheduled_at,
            source_period_identifier, event_kind, disposition, detail_code,
            source_id, source_version, source_locator, source_payload_sha256,
            source_observed_at, immutable_schedule_hash,
            certificate_input_sha256, certificate_document_sha256,
            certified_at, certifying_authority, certification_reason,
            supporting_artifact_type, run_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            schedule_id,
            lottery_type.value,
            official_game_code,
            draw_number,
            None if draw_date is None else draw_date.isoformat(),
            scheduled_local_time,
            schedule_timezone,
            scheduled_at,
            source_period_identifier,
            event_kind,
            disposition,
            detail_code,
            source.source_id,
            source.source_version,
            source.source_locator,
            source.source_payload_sha256,
            _format_utc(source.observed_at),
            immutable_schedule_hash,
            certificate_input_sha256,
            certificate_document_sha256,
            None if certified_at is None else _format_utc(certified_at),
            certifying_authority,
            certification_reason,
            supporting_artifact_type,
            run_id,
            _format_utc(created_at),
        ),
    )


def _schedule_id_for_identity(
    connection: sqlite3.Connection,
    lottery_type: LotteryType,
    draw_number: str | None,
) -> int | None:
    if draw_number is None:
        return None
    row = connection.execute(
        """
        SELECT id FROM draw_schedules
        WHERE lottery_type = ? AND draw_number = ?
        """,
        (lottery_type.value, draw_number),
    ).fetchone()
    return None if row is None else _positive_integer(row[0])


def _get_scheduled_draw(
    connection: sqlite3.Connection,
    lottery_type: LotteryType,
    draw_number: str,
) -> ScheduledDrawIdentityRecord | None:
    row = connection.execute(
        """
        SELECT s.*, d.id AS outcome_draw_internal_id,
               d.draw_date AS outcome_draw_date
        FROM draw_schedules AS s
        LEFT JOIN draws AS d
               ON d.lottery_type = s.lottery_type
              AND d.draw_number = s.draw_number
        WHERE s.lottery_type = ? AND s.draw_number = ?
        """,
        (lottery_type.value, draw_number),
    ).fetchone()
    return None if row is None else _scheduled_record(row)


def _validate_official_schedule_fetch(fetched: OfficialScheduleFetchResult) -> None:
    if type(fetched) is not OfficialScheduleFetchResult:
        raise ValueError("fetched must be an OfficialScheduleFetchResult")
    if fetched.provider_id != OFFICIAL_SCHEDULE_SOURCE_ID:
        raise ValueError("official schedule provider identity is not canonical")
    if fetched.provider_version != OFFICIAL_SCHEDULE_SOURCE_VERSION:
        raise ValueError("official schedule provider version is not canonical")
    _validate_official_locator(fetched.source_url)
    if len(fetched.announcements) > _MAX_OFFICIAL_SCHEDULE_ANNOUNCEMENTS:
        raise ValueError("official schedule announcement batch exceeds the bounded limit")
    for announcement in fetched.announcements:
        if announcement.target.lottery_type is not LotteryType.BIG_LOTTO:
            raise ValueError("official schedule synchronization supports BIG_LOTTO only")
        if announcement.scheduled_at <= fetched.observed_at:
            raise ValueError("official schedule synchronization cannot backfill due identities")
        _validate_official_schedule_material(announcement)
        source = announcement.source
        if (
            source.source_id != fetched.provider_id
            or source.source_version != fetched.provider_version
            or source.source_locator != fetched.source_url
            or source.source_sha256 != fetched.source_payload_sha256
            or source.observed_at != fetched.observed_at
        ):
            raise ValueError("official schedule announcement provenance is inconsistent")


def _plan_schedule_decisions(
    connection: sqlite3.Connection,
    fetched: OfficialScheduleFetchResult,
) -> tuple[_ScheduleDecision, ...]:
    _reject_cross_table_date_mismatch(connection)
    seen: dict[tuple[LotteryType, str], TargetAnnouncement] = {}
    decisions: list[_ScheduleDecision] = []
    for announcement in sorted(fetched.announcements, key=_schedule_sort_key):
        key = (announcement.target.lottery_type, announcement.target.draw_number)
        normalized_hash = normalized_announcement_sha256(announcement)
        previous = seen.get(key)
        if previous is not None:
            if _same_schedule_material(previous, announcement):
                decisions.append(
                    _ScheduleDecision(
                        announcement=announcement,
                        normalized_hash=normalized_hash,
                        disposition=IngestionItemDisposition.SKIPPED_DUPLICATE,
                        message="Exact official schedule identity is duplicated in the batch.",
                    )
                )
            else:
                decisions.append(
                    _ScheduleDecision(
                        announcement=announcement,
                        normalized_hash=normalized_hash,
                        disposition=IngestionItemDisposition.CONFLICT,
                        message="Official schedule batch contains conflicting identities.",
                    )
                )
            continue
        seen[key] = announcement

        existing = _get_scheduled_draw(
            connection,
            announcement.target.lottery_type,
            announcement.target.draw_number,
        )
        if existing is not None:
            if _same_schedule_material(existing.announcement, announcement):
                disposition = (
                    IngestionItemDisposition.SKIPPED_COMPLETED
                    if existing.outcome_state is ScheduledDrawOutcomeState.POPULATED
                    else IngestionItemDisposition.SKIPPED_DUPLICATE
                )
                message = (
                    "Completed official schedule identity remains authoritative."
                    if disposition is IngestionItemDisposition.SKIPPED_COMPLETED
                    else "Exact official schedule identity already exists."
                )
            else:
                disposition = IngestionItemDisposition.CONFLICT
                message = "Stored immutable schedule identity differs."
        else:
            completed_date = _completed_draw_date(connection, announcement.target)
            if completed_date is not None:
                if completed_date == announcement.target.draw_date:
                    disposition = IngestionItemDisposition.SKIPPED_COMPLETED
                    message = "Completed draw identity is not reintroduced as unresolved."
                else:
                    disposition = IngestionItemDisposition.CONFLICT
                    message = "Completed draw date conflicts with the official schedule."
            else:
                disposition = IngestionItemDisposition.INSERTED
                message = "Inserted explicit official future draw identity."
        decisions.append(
            _ScheduleDecision(
                announcement=announcement,
                normalized_hash=normalized_hash,
                disposition=disposition,
                message=message,
            )
        )
    return tuple(decisions)


def _same_schedule_material(
    left: TargetAnnouncement,
    right: TargetAnnouncement,
) -> bool:
    """Compare immutable schedule authority while allowing a later observation time."""

    return (
        left.target == right.target
        and left.schedule_timezone == right.schedule_timezone
        and left.scheduled_at == right.scheduled_at
        and left.source.source_id == right.source.source_id
        and left.source.source_version == right.source.source_version
        and left.source.source_locator == right.source.source_locator
        and left.source.source_sha256 == right.source.source_sha256
    )


def _schedule_sort_key(
    announcement: TargetAnnouncement,
) -> tuple[datetime, int, str]:
    return (
        announcement.scheduled_at,
        int(announcement.target.draw_number),
        announcement.target.draw_number,
    )


def _schedule_counts(
    decisions: tuple[_ScheduleDecision, ...],
) -> tuple[int, int, int, int, int, int]:
    inserted_count = sum(
        decision.disposition is IngestionItemDisposition.INSERTED for decision in decisions
    )
    skipped_count = sum(
        decision.disposition
        in {
            IngestionItemDisposition.SKIPPED_DUPLICATE,
            IngestionItemDisposition.SKIPPED_COMPLETED,
        }
        for decision in decisions
    )
    exact_duplicate_count = sum(
        decision.disposition is IngestionItemDisposition.SKIPPED_DUPLICATE for decision in decisions
    )
    completed_count = sum(
        decision.disposition is IngestionItemDisposition.SKIPPED_COMPLETED for decision in decisions
    )
    conflict_count = sum(
        decision.disposition is IngestionItemDisposition.CONFLICT for decision in decisions
    )
    failed_count = sum(
        decision.disposition is IngestionItemDisposition.FAILED for decision in decisions
    )
    return (
        inserted_count,
        skipped_count,
        exact_duplicate_count,
        completed_count,
        conflict_count,
        failed_count,
    )


def _insert_schedule_sync_audit(
    connection: sqlite3.Connection,
    *,
    fetched: OfficialScheduleFetchResult,
    run_id: str,
    timestamp: datetime,
    decisions: tuple[_ScheduleDecision, ...],
    status: IngestionRunStatus,
    error_summary: str | None,
) -> None:
    ordered = tuple(
        sorted(decisions, key=lambda decision: _schedule_sort_key(decision.announcement))
    )
    if not ordered:
        raise ValueError("official schedule audit requires at least one decision")
    (
        inserted_count,
        skipped_count,
        _exact_duplicate_count,
        _completed_count,
        conflict_count,
        failed_count,
    ) = _schedule_counts(decisions)
    dates = tuple(decision.announcement.target.draw_date for decision in ordered)
    timestamp_text = _format_utc(timestamp)
    connection.execute(
        """
        INSERT INTO ingestion_runs (
            id, operation_type, status, lottery_type, source_filename,
            source_sha256, parser_version, total_count, inserted_count,
            skipped_count, conflict_count, failed_count, first_draw_number,
            last_draw_number, started_at, completed_at, error_summary
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            IngestionOperationType.OFFICIAL_SCHEDULE_SYNC.value,
            status.value,
            LotteryType.BIG_LOTTO.value,
            fetched.source_url,
            fetched.source_payload_sha256,
            SCHEDULE_SYNC_PARSER_VERSION,
            len(decisions),
            inserted_count,
            skipped_count,
            conflict_count,
            failed_count,
            ordered[0].announcement.target.draw_number,
            ordered[-1].announcement.target.draw_number,
            timestamp_text,
            timestamp_text,
            error_summary,
        ),
    )
    connection.execute(
        """
        INSERT INTO ingestion_run_context (
            ingestion_run_id, trigger, provider, provider_version,
            requested_start, requested_end, resolved_start, resolved_end,
            fetched_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            IngestionOperationType.OFFICIAL_SCHEDULE_SYNC.value,
            fetched.provider_id,
            fetched.provider_version,
            min(dates).isoformat(),
            max(dates).isoformat(),
            min(dates).isoformat(),
            max(dates).isoformat(),
            len(decisions),
        ),
    )
    for source_row_number, decision in enumerate(ordered, start=1):
        connection.execute(
            """
            INSERT INTO ingestion_items (
                ingestion_run_id, source_row_number, lottery_type, draw_number,
                disposition, normalized_record_hash, message
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                source_row_number,
                decision.announcement.target.lottery_type.value,
                decision.announcement.target.draw_number,
                decision.disposition.value,
                decision.normalized_hash,
                decision.message,
            ),
        )


def _insert_schedule(
    connection: sqlite3.Connection,
    *,
    announcement: TargetAnnouncement,
    normalized_hash: str,
    run_id: str,
    timestamp: datetime,
) -> None:
    target = announcement.target
    connection.execute(
        """
        INSERT INTO draw_schedules (
            lottery_type, draw_number, draw_date, scheduled_at,
            schedule_timezone, source_id, source_version, source_locator,
            source_payload_sha256, source_observed_at,
            normalized_announcement_hash, ingestion_run_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            target.lottery_type.value,
            target.draw_number,
            target.draw_date.isoformat(),
            _format_utc(announcement.scheduled_at),
            announcement.schedule_timezone,
            announcement.source.source_id,
            announcement.source.source_version,
            announcement.source.source_locator,
            announcement.source.source_payload_sha256,
            _format_utc(announcement.source.observed_at),
            normalized_hash,
            run_id,
            _format_utc(timestamp),
        ),
    )


def _completed_draw_date(
    connection: sqlite3.Connection,
    target: ObservationTarget,
) -> date | None:
    row = connection.execute(
        """
        SELECT draw_date
        FROM draws
        WHERE lottery_type = ? AND draw_number = ?
        """,
        (target.lottery_type.value, target.draw_number),
    ).fetchone()
    return None if row is None else _date_value(row[0], "completed draw date")


def _schedule_sync_result(
    fetched: OfficialScheduleFetchResult,
    *,
    run_id: str,
    status: IngestionRunStatus,
    decisions: tuple[_ScheduleDecision, ...],
) -> OfficialScheduleSyncResult:
    (
        inserted_count,
        skipped_count,
        exact_duplicate_count,
        completed_count,
        conflict_count,
        failed_count,
    ) = _schedule_counts(decisions)
    ordered = tuple(
        sorted(decisions, key=lambda decision: _schedule_sort_key(decision.announcement))
    )
    return OfficialScheduleSyncResult(
        run_id=run_id,
        status=status,
        provider_id=fetched.provider_id,
        provider_version=fetched.provider_version,
        source_url=fetched.source_url,
        source_payload_sha256=fetched.source_payload_sha256,
        observed_at=fetched.observed_at,
        target_draw_numbers=tuple(decision.announcement.target.draw_number for decision in ordered),
        total_count=len(decisions),
        inserted_count=inserted_count,
        skipped_count=skipped_count,
        exact_duplicate_count=exact_duplicate_count,
        completed_count=completed_count,
        conflict_count=conflict_count,
        failed_count=failed_count,
    )


def _scheduled_record(row: sqlite3.Row | tuple[object, ...]) -> ScheduledDrawIdentityRecord:
    values = tuple(row)
    if len(values) not in {15, 16}:
        raise ValueError("stored schedule row shape is invalid")
    lottery_type = LotteryType(_required_text(values[1], "lottery_type"))
    draw_number = _required_text(values[2], "draw_number")
    _require_draw_number(draw_number)
    draw_date_value = _date_value(values[3], "draw_date")
    scheduled_at = _datetime_value(values[4], "scheduled_at")
    source_observed_at = _datetime_value(values[10], "source_observed_at")
    announcement = TargetAnnouncement(
        target=ObservationTarget(lottery_type, draw_number, draw_date_value),
        schedule_timezone=_required_text(values[5], "schedule_timezone"),
        scheduled_at=scheduled_at,
        source=TargetSourceProvenance(
            source_id=_required_text(values[6], "source_id"),
            source_version=_required_text(values[7], "source_version"),
            source_locator=_required_text(values[8], "source_locator"),
            source_sha256=_required_sha256(values[9], "source_payload_sha256"),
            observed_at=source_observed_at,
        ),
    )
    _validate_official_schedule_material(announcement)
    normalized_hash = _required_sha256(values[11], "normalized_announcement_hash")
    if normalized_hash != normalized_announcement_sha256(announcement):
        raise ValueError("stored normalized announcement hash is invalid")
    outcome_id_value = values[14]
    outcome_id = None if outcome_id_value is None else _positive_integer(outcome_id_value)
    if len(values) == 16 and outcome_id is not None:
        outcome_date = _date_value(values[15], "outcome_draw_date")
        if outcome_date != draw_date_value:
            raise ValueError("stored schedule and completed draw dates conflict")
    return ScheduledDrawIdentityRecord(
        internal_id=_positive_integer(values[0]),
        announcement=announcement,
        normalized_announcement_hash=normalized_hash,
        ingestion_run_id=_required_text(values[12], "ingestion_run_id"),
        created_at=_datetime_value(values[13], "created_at"),
        outcome_state=(
            ScheduledDrawOutcomeState.NOT_POPULATED
            if outcome_id is None
            else ScheduledDrawOutcomeState.POPULATED
        ),
        outcome_draw_internal_id=outcome_id,
    )


def _validate_manual_request(
    parsed_input: OwnerCertifiedFutureDrawIdentityInput,
    selected_target: TargetAnnouncement,
    expected_sha256: str,
) -> str:
    if type(parsed_input) is not OwnerCertifiedFutureDrawIdentityInput:
        raise ValueError("parsed_input must be an owner-certified parse result")
    if type(selected_target) is not TargetAnnouncement:
        raise ValueError("selected_target must be a TargetAnnouncement")
    if type(expected_sha256) is not str or _SHA256.fullmatch(expected_sha256) is None:
        raise ValueError("expected_sha256 must be a lowercase SHA-256 digest")
    if parsed_input.input_sha256 != expected_sha256:
        raise ValueError("owner-certified input SHA-256 does not match the expected digest")
    if parsed_input.announcements.count(selected_target) != 1:
        raise ValueError("selected_target must occur exactly once in parsed_input")
    if selected_target.target.lottery_type is not LotteryType.BIG_LOTTO:
        raise ValueError("manual future identity supplementation initially supports BIG_LOTTO")
    _validate_official_schedule_material(selected_target)
    return normalized_announcement_sha256(selected_target)


def _validate_official_schedule_material(announcement: TargetAnnouncement) -> None:
    if announcement.schedule_timezone != SCHEDULE_TIMEZONE:
        raise ValueError(f"schedule_timezone must be {SCHEDULE_TIMEZONE}")
    if announcement.source.source_id != OFFICIAL_SCHEDULE_SOURCE_ID:
        raise ValueError("schedule source_id is not canonical")
    if announcement.source.source_version != OFFICIAL_SCHEDULE_SOURCE_VERSION:
        raise ValueError("schedule source_version is not canonical")
    _validate_official_locator(announcement.source.source_locator)


def _is_exact_schedule(
    existing: ScheduledDrawIdentityRecord,
    selected_target: TargetAnnouncement,
    normalized_hash: str,
) -> bool:
    return (
        existing.announcement == selected_target
        and existing.normalized_announcement_hash == normalized_hash
    )


def _completed_draw_exists(
    connection: sqlite3.Connection,
    target: ObservationTarget,
) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM draws WHERE lottery_type = ? AND draw_number = ?",
            (target.lottery_type.value, target.draw_number),
        ).fetchone()
        is not None
    )


def _reject_cross_table_date_mismatch(connection: sqlite3.Connection) -> None:
    row = connection.execute(
        """
        SELECT 1
        FROM draw_schedules AS s
        INNER JOIN draws AS d
                ON d.lottery_type = s.lottery_type
               AND d.draw_number = s.draw_number
        WHERE d.draw_date <> s.draw_date
        LIMIT 1
        """
    ).fetchone()
    if row is not None:
        raise ValueError("stored schedule and completed draw dates conflict")


def _require_current_schema(connection: sqlite3.Connection) -> None:
    if connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone() != (
        CURRENT_SCHEMA_VERSION,
    ):
        raise SchemaMigrationError(
            f"canonical draw database requires schema version {CURRENT_SCHEMA_VERSION}"
        )


def _validate_official_locator(value: str) -> None:
    if type(value) is not str:
        raise ValueError(
            "source_locator must be a credential-free official Taiwan Lottery HTTPS URL"
        )
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ValueError(
            "source_locator must be a credential-free official Taiwan Lottery HTTPS URL"
        ) from exc
    if (
        len(value) > 2048
        or parsed.scheme != "https"
        or parsed.hostname not in _OFFICIAL_SCHEDULE_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.fragment
    ):
        raise ValueError(
            "source_locator must be a credential-free official Taiwan Lottery HTTPS URL"
        )


def _require_lottery_type(value: object) -> None:
    if type(value) is not LotteryType:
        raise ValueError("lottery_type must be a LotteryType")


def _require_draw_number(value: object) -> None:
    if type(value) is not str or _DRAW_NUMBER.fullmatch(value) is None:
        raise ValueError("draw_number must contain 1-32 ASCII decimal digits")


def _require_utc(value: object, label: str) -> None:
    if type(value) is not datetime or value.tzinfo is not UTC:
        raise ValueError(f"{label} must be a timezone-aware UTC datetime")


def _required_text(value: object, label: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"stored {label} is invalid")
    return value


def _required_sha256(value: object, label: str) -> str:
    text = _required_text(value, label)
    if _SHA256.fullmatch(text) is None:
        raise ValueError(f"stored {label} is invalid")
    return text


def _date_value(value: object, label: str) -> date:
    text = _required_text(value, label)
    parsed = date.fromisoformat(text)
    if parsed.isoformat() != text:
        raise ValueError(f"stored {label} is not canonical")
    return parsed


def _datetime_value(value: object, label: str) -> datetime:
    text = _required_text(value, label)
    if not text.endswith("Z"):
        raise ValueError(f"stored {label} is not UTC")
    parsed = datetime.fromisoformat(f"{text[:-1]}+00:00")
    if parsed.tzinfo is not UTC or _format_utc(parsed) != text:
        raise ValueError(f"stored {label} is not canonical UTC")
    return parsed


def _positive_integer(value: object) -> int:
    if type(value) is not int or value < 1:
        raise ValueError("stored internal identity is invalid")
    return value


def _format_utc(value: datetime) -> str:
    _require_utc(value, "timestamp")
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


__all__ = [
    "MANUAL_FUTURE_DRAW_IDENTITY_PARSER_VERSION",
    "SQLiteCanonicalScheduleAuthorityRepository",
    "SQLiteFutureDrawIdentityReader",
    "SQLiteManualFutureDrawIdentitySupplementRepository",
    "SQLiteOfficialScheduleSyncRepository",
]
