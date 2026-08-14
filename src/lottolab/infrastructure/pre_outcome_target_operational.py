"""Canonical local operational bindings for pre-outcome target authority.

The binding is intentionally explicit and DB-local:

* announcements come only from one fixed, owner-only schedule authority file;
* accepted registrations live under one fixed directory below LottoLab's
  canonical local data directory;
* an ABSENT attestation requires a successful official-provider sync audit
  whose requested range covered the target date;
* the presence query reads target identity only, never winning numbers; and
* causal-history identity is built from stored normalized-record digests, not
  from target outcome content.

Resolving or composing these adapters never creates a directory, opens the
database, reads an announcement, or registers a target.  The durable authority
root is created lazily only when the canonical create-once store accepts a
registration.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import stat
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit

from lottolab.application.pre_outcome_target import (
    PreOutcomeTargetRegistrationService,
)
from lottolab.application.pre_outcome_target_operational import (
    CausalHistoryAuthorityError,
    OutcomePresenceEvidenceUnavailableError,
    PreOutcomeTargetOperationalService,
    TargetAnnouncementAuthorityError,
    TargetAnnouncementInventory,
    TargetAnnouncementSourceStatus,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.ingestion import IngestionRunStatus
from lottolab.domain.pre_outcome_target import (
    OutcomePresenceAttestation,
    PreOutcomeTargetRegistration,
    TargetAnnouncement,
    TargetSourceProvenance,
)
from lottolab.domain.prospective_observer import (
    CausalHistoryRef,
    CreateOnceOutcome,
    ObservationTarget,
    OutcomePresenceAtPrediction,
)
from lottolab.infrastructure.persistence.draw_schema import (
    CURRENT_SCHEMA_VERSION,
    LocalDataError,
    LocalDataPaths,
    SchemaMigrationError,
    open_database,
    resolve_local_data_paths,
    verify_schema_read_only,
)
from lottolab.infrastructure.pre_outcome_target_store import (
    FileSystemPreOutcomeTargetAuthorityStore,
)
from lottolab.infrastructure.taiwan_lottery_draw_provider import (
    PROVIDER_ID as OFFICIAL_DRAW_PROVIDER_ID,
)
from lottolab.infrastructure.taiwan_lottery_draw_provider import (
    PROVIDER_VERSION as OFFICIAL_DRAW_PROVIDER_VERSION,
)

OPERATIONAL_ANNOUNCEMENT_SCHEMA_VERSION = (
    "LOTTOLAB_PRE_OUTCOME_OPERATIONAL_ANNOUNCEMENTS_V1"
)
OPERATIONAL_CAUSAL_HISTORY_SCHEMA_VERSION = "LOTTOLAB_PRE_OUTCOME_CAUSAL_HISTORY_V1"
OFFICIAL_SCHEDULE_SOURCE_ID = "TAIWAN_LOTTERY_OFFICIAL_SCHEDULE"
OFFICIAL_SCHEDULE_SOURCE_VERSION = "taiwan-lottery-official-schedule-v1"
OFFICIAL_PRESENCE_SOURCE_ID = "LOTTOLAB_OFFICIAL_OUTCOME_PRESENCE_AUDIT"
ANNOUNCEMENT_FILENAME = "pre-outcome-target-announcements-v1.json"
AUTHORITY_DIRECTORY_NAME = "pre-outcome-target-authority-v1"
SCHEDULE_TIMEZONE = "Asia/Taipei"

_MAX_ANNOUNCEMENT_BYTES = 1024 * 1024
_MAX_ANNOUNCEMENTS = 1024
_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)
_DRAW_NUMBER = re.compile(r"[0-9]{1,32}", flags=re.ASCII)
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
_NONBLOCK = getattr(os, "O_NONBLOCK", 0)
_OFFICIAL_SCHEDULE_HOSTS = frozenset(
    {"www.taiwanlottery.com", "api.taiwanlottery.com"}
)


@dataclass(frozen=True, slots=True)
class PreOutcomeTargetOperationalPaths:
    """Exact canonical paths; construction is side-effect free."""

    local_data: LocalDataPaths
    announcement_file: Path
    authority_root: Path

    def __post_init__(self) -> None:
        if type(self.local_data) is not LocalDataPaths:
            raise ValueError("local_data must be LocalDataPaths")
        if self.announcement_file != self.local_data.data_directory / ANNOUNCEMENT_FILENAME:
            raise ValueError("announcement filename is fixed by the operational contract")
        if self.authority_root != self.local_data.data_directory / AUTHORITY_DIRECTORY_NAME:
            raise ValueError("authority directory is fixed by the operational contract")


def resolve_pre_outcome_target_operational_paths(
    *,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> PreOutcomeTargetOperationalPaths:
    """Resolve the one canonical local binding without creating or opening it."""

    local_data = resolve_local_data_paths(environ=environ, home=home)
    paths = PreOutcomeTargetOperationalPaths(
        local_data=local_data,
        announcement_file=local_data.data_directory / ANNOUNCEMENT_FILENAME,
        authority_root=local_data.data_directory / AUTHORITY_DIRECTORY_NAME,
    )
    _validate_existing_announcement_path(paths.announcement_file)
    _validate_existing_authority_root(paths.authority_root)
    return paths


class FileSystemOperationalTargetAnnouncementSource:
    """Read the fixed owner-certified official schedule authority document."""

    def __init__(self, path: Path) -> None:
        if not path.is_absolute():
            raise ValueError("announcement path must be absolute")
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    def read(self) -> TargetAnnouncementInventory:
        try:
            encoded = _read_optional_owner_file(self._path)
            if encoded is None:
                return TargetAnnouncementInventory(
                    status=TargetAnnouncementSourceStatus.NOT_CONFIGURED,
                    announcements=(),
                )
            return TargetAnnouncementInventory(
                status=TargetAnnouncementSourceStatus.AVAILABLE,
                announcements=_decode_announcements(encoded),
            )
        except TargetAnnouncementAuthorityError:
            raise
        except (OSError, TypeError, ValueError) as exc:
            raise TargetAnnouncementAuthorityError(
                "canonical target-announcement authority is invalid"
            ) from exc


class CanonicalPreOutcomeTargetAuthorityStore:
    """Lazy binding of the create-once store to the fixed operational root."""

    def __init__(self, root: Path) -> None:
        if not root.is_absolute():
            raise ValueError("authority root must be absolute")
        self._root = root

    @property
    def root(self) -> Path:
        return self._root

    def get_registration(
        self,
        target: ObservationTarget,
    ) -> PreOutcomeTargetRegistration | None:
        try:
            os.lstat(self._root)
        except FileNotFoundError:
            return None
        store = FileSystemPreOutcomeTargetAuthorityStore(self._root)
        try:
            return store.get_registration(target)
        finally:
            store.close()

    def create_registration(
        self,
        registration: PreOutcomeTargetRegistration,
    ) -> CreateOnceOutcome:
        store = FileSystemPreOutcomeTargetAuthorityStore(self._root)
        try:
            return store.create_registration(registration)
        finally:
            store.close()


class SQLiteOfficialOutcomePresenceProbe:
    """Read target presence without selecting any official outcome values.

    ABSENT is accepted only when the draw database contains a successful audit
    from the fixed official provider whose requested interval covered the target
    date.  The query reads audit metadata and target identity only.
    """

    def __init__(self, paths: LocalDataPaths) -> None:
        self._paths = paths

    def probe(
        self,
        target: ObservationTarget,
        *,
        as_of: datetime,
    ) -> OutcomePresenceAttestation:
        _require_target(target)
        _require_utc(as_of, "as_of")
        try:
            _require_current_database(self._paths)
            with open_database(self._paths, read_only=True) as connection:
                stored_date = _read_target_identity(connection, target)
                if stored_date is not None:
                    if stored_date != target.draw_date:
                        raise OutcomePresenceEvidenceUnavailableError(
                            "stored target identity conflicts with the announcement"
                        )
                    presence = OutcomePresenceAtPrediction.PRESENT
                    evidence: dict[str, object] = {
                        "evidence_kind": "CANONICAL_DRAW_IDENTITY",
                        "stored_draw_date": stored_date.isoformat(),
                    }
                    locator = "lottolab://draw-data/target-identity"
                else:
                    audit = _read_covering_official_audit(connection, target, as_of)
                    if audit is None:
                        raise OutcomePresenceEvidenceUnavailableError(
                            "no successful official-provider presence audit covers the target"
                        )
                    presence = OutcomePresenceAtPrediction.ABSENT
                    evidence = {
                        "completed_at": _utc_text(audit.completed_at),
                        "evidence_kind": "OFFICIAL_PROVIDER_RANGE_AUDIT",
                        "fetched_count": audit.fetched_count,
                        "provider_id": OFFICIAL_DRAW_PROVIDER_ID,
                        "provider_version": OFFICIAL_DRAW_PROVIDER_VERSION,
                        "requested_end": audit.requested_end.isoformat(),
                        "requested_start": audit.requested_start.isoformat(),
                        "run_id": audit.run_id,
                    }
                    locator = f"lottolab://draw-ingestion-audit/{audit.run_id}"
        except OutcomePresenceEvidenceUnavailableError:
            raise
        except (
            LocalDataError,
            SchemaMigrationError,
            TargetAnnouncementAuthorityError,
            sqlite3.DatabaseError,
            ValueError,
        ) as exc:
            raise OutcomePresenceEvidenceUnavailableError(
                "official outcome presence evidence is unavailable"
            ) from exc

        material = {
            "as_of": _utc_text(as_of),
            "evidence": evidence,
            "presence": presence.value,
            "target": target.canonical_dict(),
        }
        return OutcomePresenceAttestation(
            target=target,
            presence=presence,
            attested_at=as_of,
            source=TargetSourceProvenance(
                source_id=OFFICIAL_PRESENCE_SOURCE_ID,
                source_version=OFFICIAL_DRAW_PROVIDER_VERSION,
                source_locator=locator,
                source_sha256=_canonical_sha256(material),
                observed_at=as_of,
            ),
        )


class SQLitePreOutcomeCausalHistoryAuthority:
    """Bind all canonical draw digests strictly before an announced target."""

    def __init__(self, paths: LocalDataPaths) -> None:
        self._paths = paths

    def resolve(self, target: ObservationTarget) -> CausalHistoryRef:
        _require_target(target)
        try:
            _require_current_database(self._paths)
            with open_database(self._paths, read_only=True) as connection:
                rows = connection.execute(
                    """
                    SELECT draw_number, draw_date, normalized_record_hash
                    FROM draws
                    WHERE lottery_type = ?
                      AND draw_date <= ?
                    """,
                    (
                        target.lottery_type.value,
                        target.draw_date.isoformat(),
                    ),
                ).fetchall()
            decoded = tuple(_history_row(row) for row in rows)
            target_key = (target.draw_date, int(target.draw_number))
            history = tuple(
                sorted(
                    (
                        item
                        for item in decoded
                        if (item[1], int(item[0])) < target_key
                    ),
                    key=lambda item: (item[1], int(item[0]), item[0]),
                )
            )
            if not history:
                raise CausalHistoryAuthorityError(
                    "canonical causal history contains no strictly prior draw"
                )
            keys = tuple((item[1], int(item[0]), item[0]) for item in history)
            if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
                raise CausalHistoryAuthorityError(
                    "canonical causal history order or identity is invalid"
                )
            material = {
                "draws": [
                    {
                        "draw_date": draw_date_value.isoformat(),
                        "draw_number": draw_number,
                        "normalized_record_hash": normalized_record_hash,
                    }
                    for draw_number, draw_date_value, normalized_record_hash in history
                ],
                "lottery_type": target.lottery_type.value,
                "schema_version": OPERATIONAL_CAUSAL_HISTORY_SCHEMA_VERSION,
                "target": target.canonical_dict(),
            }
            last_number, last_date, _ = history[-1]
            return CausalHistoryRef(
                draw_count=len(history),
                last_draw_number=last_number,
                last_draw_date=last_date,
                history_sha256=_canonical_sha256(material),
            )
        except CausalHistoryAuthorityError:
            raise
        except (
            LocalDataError,
            SchemaMigrationError,
            TargetAnnouncementAuthorityError,
            sqlite3.DatabaseError,
            ValueError,
        ) as exc:
            raise CausalHistoryAuthorityError(
                "canonical causal-history authority is unavailable"
            ) from exc


@dataclass(frozen=True, slots=True)
class PreOutcomeTargetOperationalComposition:
    paths: PreOutcomeTargetOperationalPaths
    service: PreOutcomeTargetOperationalService


def compose_pre_outcome_target_operational_service(
    *,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
    clock: Callable[[], datetime] | None = None,
) -> PreOutcomeTargetOperationalComposition:
    """Compose the canonical adapters without reading or creating operational state."""

    paths = resolve_pre_outcome_target_operational_paths(environ=environ, home=home)
    selected_clock = _utc_now if clock is None else clock
    registration_service = PreOutcomeTargetRegistrationService(
        store=CanonicalPreOutcomeTargetAuthorityStore(paths.authority_root),
        outcome_presence_probe=SQLiteOfficialOutcomePresenceProbe(paths.local_data),
        clock=selected_clock,
    )
    return PreOutcomeTargetOperationalComposition(
        paths=paths,
        service=PreOutcomeTargetOperationalService(
            announcement_source=FileSystemOperationalTargetAnnouncementSource(
                paths.announcement_file
            ),
            causal_history_authority=SQLitePreOutcomeCausalHistoryAuthority(
                paths.local_data
            ),
            registration_service=registration_service,
            clock=selected_clock,
        ),
    )


@dataclass(frozen=True, slots=True)
class _OfficialPresenceAudit:
    run_id: str
    completed_at: datetime
    requested_start: date
    requested_end: date
    fetched_count: int


def _decode_announcements(encoded: bytes) -> tuple[TargetAnnouncement, ...]:
    try:
        value: object = json.loads(
            encoded.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_json_members,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TargetAnnouncementAuthorityError(
            "target-announcement authority must be valid UTF-8 JSON"
        ) from exc
    root = _object(value, "announcement authority")
    _expect_keys(root, {"announcements", "schema_version"}, "announcement authority")
    if root["schema_version"] != OPERATIONAL_ANNOUNCEMENT_SCHEMA_VERSION:
        raise TargetAnnouncementAuthorityError(
            "target-announcement authority schema_version is unsupported"
        )
    raw_announcements = root["announcements"]
    if not isinstance(raw_announcements, list):
        raise TargetAnnouncementAuthorityError("announcements must be a list")
    values = cast(list[object], raw_announcements)
    if len(values) > _MAX_ANNOUNCEMENTS:
        raise TargetAnnouncementAuthorityError("announcement inventory is too large")
    announcements = tuple(_decode_announcement(item) for item in values)
    targets = tuple(item.target for item in announcements)
    if len(targets) != len(set(targets)):
        raise TargetAnnouncementAuthorityError("announcement targets must be unique")
    return tuple(sorted(announcements, key=_announcement_order))


def _reject_duplicate_json_members(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    mapping: dict[str, object] = {}
    for key, value in pairs:
        if key in mapping:
            raise TargetAnnouncementAuthorityError(
                "target-announcement authority contains duplicate JSON members"
            )
        mapping[key] = value
    return mapping


def _decode_announcement(value: object) -> TargetAnnouncement:
    mapping = _object(value, "announcement")
    _expect_keys(
        mapping,
        {"schedule_timezone", "scheduled_at", "source", "target"},
        "announcement",
    )
    target_mapping = _object(mapping["target"], "announcement.target")
    _expect_keys(
        target_mapping,
        {"draw_date", "draw_number", "lottery_type"},
        "announcement.target",
    )
    source_mapping = _object(mapping["source"], "announcement.source")
    _expect_keys(
        source_mapping,
        {
            "observed_at",
            "source_id",
            "source_locator",
            "source_payload_sha256",
            "source_version",
        },
        "announcement.source",
    )

    try:
        lottery_type = LotteryType(_text(target_mapping["lottery_type"], "lottery_type"))
    except ValueError as exc:
        raise TargetAnnouncementAuthorityError("lottery_type is unsupported") from exc
    draw_number = _text(target_mapping["draw_number"], "draw_number")
    if _DRAW_NUMBER.fullmatch(draw_number) is None:
        raise TargetAnnouncementAuthorityError("draw_number is not canonical")
    draw_date_value = _canonical_date(target_mapping["draw_date"], "draw_date")
    scheduled_at = _canonical_datetime(mapping["scheduled_at"], "scheduled_at")
    schedule_timezone = _text(mapping["schedule_timezone"], "schedule_timezone")
    if schedule_timezone != SCHEDULE_TIMEZONE:
        raise TargetAnnouncementAuthorityError(
            f"schedule_timezone must be {SCHEDULE_TIMEZONE}"
        )

    source_id = _text(source_mapping["source_id"], "source_id")
    source_version = _text(source_mapping["source_version"], "source_version")
    source_locator = _text(source_mapping["source_locator"], "source_locator")
    source_payload_sha256 = _sha256_text(
        source_mapping["source_payload_sha256"],
        "source_payload_sha256",
    )
    observed_at = _canonical_datetime(source_mapping["observed_at"], "observed_at")
    if source_id != OFFICIAL_SCHEDULE_SOURCE_ID:
        raise TargetAnnouncementAuthorityError("schedule source_id is not canonical")
    if source_version != OFFICIAL_SCHEDULE_SOURCE_VERSION:
        raise TargetAnnouncementAuthorityError("schedule source_version is not canonical")
    _validate_official_source_locator(source_locator)

    try:
        return TargetAnnouncement(
            target=ObservationTarget(
                lottery_type=lottery_type,
                draw_number=draw_number,
                draw_date=draw_date_value,
            ),
            schedule_timezone=schedule_timezone,
            scheduled_at=scheduled_at,
            source=TargetSourceProvenance(
                source_id=source_id,
                source_version=source_version,
                source_locator=source_locator,
                source_sha256=source_payload_sha256,
                observed_at=observed_at,
            ),
        )
    except ValueError as exc:
        raise TargetAnnouncementAuthorityError(str(exc)) from exc


def _read_optional_owner_file(path: Path) -> bytes | None:
    flags = os.O_RDONLY | _NOFOLLOW | _CLOEXEC | _NONBLOCK
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise TargetAnnouncementAuthorityError(
            "cannot open target-announcement authority safely"
        ) from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise TargetAnnouncementAuthorityError(
                "target-announcement authority must be a regular file"
            )
        if metadata.st_uid != os.getuid():
            raise TargetAnnouncementAuthorityError(
                "target-announcement authority must be owner-owned"
            )
        if stat.S_IMODE(metadata.st_mode) != 0o600:
            raise TargetAnnouncementAuthorityError(
                "target-announcement authority mode must be exactly 0600"
            )
        if metadata.st_nlink != 1:
            raise TargetAnnouncementAuthorityError(
                "target-announcement authority must have exactly one hard link"
            )
        if metadata.st_size > _MAX_ANNOUNCEMENT_BYTES:
            raise TargetAnnouncementAuthorityError(
                "target-announcement authority exceeds the bounded size limit"
            )
        chunks: list[bytes] = []
        remaining = _MAX_ANNOUNCEMENT_BYTES + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        encoded = b"".join(chunks)
        if len(encoded) > _MAX_ANNOUNCEMENT_BYTES:
            raise TargetAnnouncementAuthorityError(
                "target-announcement authority exceeds the bounded size limit"
            )
        final_metadata = os.fstat(descriptor)
        initial_identity = (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_mode,
            metadata.st_uid,
            metadata.st_nlink,
            metadata.st_size,
            metadata.st_mtime_ns,
        )
        final_identity = (
            final_metadata.st_dev,
            final_metadata.st_ino,
            final_metadata.st_mode,
            final_metadata.st_uid,
            final_metadata.st_nlink,
            final_metadata.st_size,
            final_metadata.st_mtime_ns,
        )
        if final_identity != initial_identity:
            raise TargetAnnouncementAuthorityError(
                "target-announcement authority changed while being read"
            )
        return encoded
    finally:
        os.close(descriptor)


def _validate_existing_announcement_path(path: Path) -> None:
    try:
        metadata = os.lstat(path)
    except FileNotFoundError:
        return
    if not stat.S_ISREG(metadata.st_mode):
        raise LocalDataError("target-announcement authority must be a regular file")
    if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise LocalDataError("target-announcement authority must be owner-only")
    if metadata.st_nlink != 1:
        raise LocalDataError("target-announcement authority must have one hard link")


def _validate_existing_authority_root(path: Path) -> None:
    try:
        metadata = os.lstat(path)
    except FileNotFoundError:
        return
    if not stat.S_ISDIR(metadata.st_mode):
        raise LocalDataError("pre-outcome target authority root must be a directory")
    if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != 0o700:
        raise LocalDataError("pre-outcome target authority root must be owner-only")


def _require_current_database(paths: LocalDataPaths) -> None:
    if not verify_schema_read_only(paths):
        raise SchemaMigrationError("canonical draw database does not exist")
    with open_database(paths, read_only=True) as connection:
        row = connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    if row != (CURRENT_SCHEMA_VERSION,):
        raise SchemaMigrationError("canonical draw database requires the current schema")


def _read_target_identity(
    connection: sqlite3.Connection,
    target: ObservationTarget,
) -> date | None:
    row = connection.execute(
        "SELECT draw_date FROM draws WHERE lottery_type = ? AND draw_number = ?",
        (target.lottery_type.value, target.draw_number),
    ).fetchone()
    if row is None:
        return None
    if len(row) != 1 or not isinstance(row[0], str):
        raise ValueError("stored target identity is invalid")
    return _canonical_date(row[0], "stored draw_date")


def _read_covering_official_audit(
    connection: sqlite3.Connection,
    target: ObservationTarget,
    as_of: datetime,
) -> _OfficialPresenceAudit | None:
    row = connection.execute(
        """
        SELECT r.id, r.completed_at, c.requested_start, c.requested_end,
               c.fetched_count, r.total_count, r.inserted_count,
               r.skipped_count, r.conflict_count, r.failed_count,
               r.error_summary
        FROM ingestion_runs AS r
        INNER JOIN ingestion_run_context AS c
                ON c.ingestion_run_id = r.id
        WHERE r.status = ?
          AND r.lottery_type = ?
          AND r.completed_at IS NOT NULL
          AND r.completed_at <= ?
          AND c.provider = ?
          AND c.provider_version = ?
          AND c.requested_start <= ?
          AND c.requested_end >= ?
        ORDER BY r.completed_at DESC, r.id DESC
        LIMIT 1
        """,
        (
            IngestionRunStatus.SUCCESS.value,
            target.lottery_type.value,
            _database_utc_text(as_of),
            OFFICIAL_DRAW_PROVIDER_ID,
            OFFICIAL_DRAW_PROVIDER_VERSION,
            target.draw_date.isoformat(),
            target.draw_date.isoformat(),
        ),
    ).fetchone()
    if row is None:
        return None
    (
        run_id,
        completed_at,
        requested_start,
        requested_end,
        fetched_count,
        total_count,
        inserted_count,
        skipped_count,
        conflict_count,
        failed_count,
        error_summary,
    ) = row
    if not isinstance(run_id, str) or not run_id or len(run_id) > 255:
        raise ValueError("official audit run_id is invalid")
    if type(fetched_count) is not int or fetched_count < 0:
        raise ValueError("official audit fetched_count is invalid")
    counts = (total_count, inserted_count, skipped_count, conflict_count, failed_count)
    if any(type(value) is not int or value < 0 for value in counts):
        raise ValueError("official audit result counts are invalid")
    if (
        total_count != fetched_count
        or inserted_count + skipped_count != total_count
        or conflict_count != 0
        or failed_count != 0
        or error_summary is not None
    ):
        raise ValueError("official audit result counts are inconsistent")
    start = _canonical_date(requested_start, "official audit requested_start")
    end = _canonical_date(requested_end, "official audit requested_end")
    completed = _database_datetime(completed_at, "official audit completed_at")
    if completed > as_of or not (start <= target.draw_date <= end):
        raise ValueError("official audit does not cover the target at as_of")
    return _OfficialPresenceAudit(
        run_id=run_id,
        completed_at=completed,
        requested_start=start,
        requested_end=end,
        fetched_count=fetched_count,
    )


def _history_row(
    row: tuple[object, ...],
) -> tuple[str, date, str]:
    if len(row) != 3:
        raise CausalHistoryAuthorityError("stored causal-history row is invalid")
    draw_number_value, draw_date_value, normalized_hash_value = row
    if not isinstance(draw_number_value, str) or _DRAW_NUMBER.fullmatch(draw_number_value) is None:
        raise CausalHistoryAuthorityError("stored causal draw_number is invalid")
    parsed_date = _canonical_date(draw_date_value, "stored causal draw_date")
    if not isinstance(normalized_hash_value, str) or _SHA256.fullmatch(
        normalized_hash_value
    ) is None:
        raise CausalHistoryAuthorityError("stored normalized_record_hash is invalid")
    return draw_number_value, parsed_date, normalized_hash_value


def _validate_official_source_locator(value: str) -> None:
    if len(value) > 2048:
        raise TargetAnnouncementAuthorityError("source_locator is too long")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in _OFFICIAL_SCHEDULE_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or parsed.fragment
    ):
        raise TargetAnnouncementAuthorityError(
            "source_locator must be a credential-free official Taiwan Lottery HTTPS URL"
        )


def _object(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TargetAnnouncementAuthorityError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _expect_keys(value: Mapping[str, object], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise TargetAnnouncementAuthorityError(f"{label} fields do not match the contract")


def _text(value: object, label: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise TargetAnnouncementAuthorityError(f"{label} must be canonical non-empty text")
    return value


def _sha256_text(value: object, label: str) -> str:
    text = _text(value, label)
    if _SHA256.fullmatch(text) is None:
        raise TargetAnnouncementAuthorityError(
            f"{label} must be a lowercase SHA-256 digest"
        )
    return text


def _canonical_date(value: object, label: str) -> date:
    text = _text(value, label)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise TargetAnnouncementAuthorityError(f"{label} must be an ISO date") from exc
    if parsed.isoformat() != text:
        raise TargetAnnouncementAuthorityError(f"{label} must be a canonical ISO date")
    return parsed


def _canonical_datetime(value: object, label: str) -> datetime:
    text = _text(value, label)
    if not text.endswith("Z"):
        raise TargetAnnouncementAuthorityError(f"{label} must use canonical UTC text")
    try:
        parsed = datetime.fromisoformat(f"{text[:-1]}+00:00")
    except ValueError as exc:
        raise TargetAnnouncementAuthorityError(f"{label} must use canonical UTC text") from exc
    if parsed.tzinfo is not UTC or _utc_text(parsed) != text:
        raise TargetAnnouncementAuthorityError(f"{label} must use canonical UTC text")
    return parsed


def _database_datetime(value: object, label: str) -> datetime:
    text = _text(value, label)
    if not text.endswith("Z"):
        raise ValueError(f"{label} must use UTC text")
    try:
        parsed = datetime.fromisoformat(f"{text[:-1]}+00:00")
    except ValueError as exc:
        raise ValueError(f"{label} must use UTC text") from exc
    fixed_microseconds = parsed.isoformat(timespec="microseconds").replace("+00:00", "Z")
    if parsed.tzinfo is not UTC or text not in {_utc_text(parsed), fixed_microseconds}:
        raise ValueError(f"{label} must use canonical database UTC text")
    return parsed


def _require_target(value: object) -> None:
    if type(value) is not ObservationTarget:
        raise ValueError("target must be an ObservationTarget")


def _require_utc(value: object, label: str) -> None:
    if type(value) is not datetime or value.tzinfo is None or value.tzinfo is not UTC:
        raise ValueError(f"{label} must be a timezone-aware UTC datetime")


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _utc_text(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _database_utc_text(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _announcement_order(
    announcement: TargetAnnouncement,
) -> tuple[datetime, str, str, int, str]:
    return (
        announcement.scheduled_at,
        announcement.target.lottery_type.value,
        announcement.target.draw_date.isoformat(),
        int(announcement.target.draw_number),
        announcement.target.draw_number,
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


__all__ = [
    "ANNOUNCEMENT_FILENAME",
    "AUTHORITY_DIRECTORY_NAME",
    "OFFICIAL_SCHEDULE_SOURCE_ID",
    "OFFICIAL_SCHEDULE_SOURCE_VERSION",
    "OPERATIONAL_ANNOUNCEMENT_SCHEMA_VERSION",
    "OPERATIONAL_CAUSAL_HISTORY_SCHEMA_VERSION",
    "CanonicalPreOutcomeTargetAuthorityStore",
    "FileSystemOperationalTargetAnnouncementSource",
    "PreOutcomeTargetOperationalComposition",
    "PreOutcomeTargetOperationalPaths",
    "SQLiteOfficialOutcomePresenceProbe",
    "SQLitePreOutcomeCausalHistoryAuthority",
    "compose_pre_outcome_target_operational_service",
    "resolve_pre_outcome_target_operational_paths",
]
