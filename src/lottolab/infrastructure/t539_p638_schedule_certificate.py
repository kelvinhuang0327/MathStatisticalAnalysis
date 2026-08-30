"""Strict, DB-free Owner schedule-certificate parsing for T539/P638."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Mapping
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from lottolab.application.schedule_certificate import (
    OWNER_SCHEDULE_CERTIFICATE_SCHEMA_VERSION,
    OWNER_SCHEDULE_CERTIFYING_AUTHORITY,
    OfficialSupportArtifactType,
    OwnerScheduleCertificate,
    ScheduleCertificateInputError,
    ScheduleCertificateReason,
)
from lottolab.application.schedule_sync import (
    CANONICAL_SCHEDULE_TIMEZONE,
    CanonicalScheduleFact,
    expected_schedule_game_code,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.pre_outcome_target import TargetAnnouncement, TargetSourceProvenance
from lottolab.domain.prospective_observer import ObservationTarget
from lottolab.infrastructure.persistence.future_draw_identity_repository import (
    OFFICIAL_SCHEDULE_SOURCE_ID,
    OFFICIAL_SCHEDULE_SOURCE_VERSION,
)

MAX_SCHEDULE_CERTIFICATE_BYTES = 1024 * 1024
MAX_SUPPORTING_ARTIFACT_BYTES = 16 * 1024 * 1024

_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)
_DRAW_NUMBER = re.compile(r"[0-9]{1,32}", flags=re.ASCII)
_LOCAL_TIME = re.compile(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]", flags=re.ASCII)
_OFFICIAL_HTTPS_HOSTS = frozenset(
    {"api.taiwanlottery.com", "www.taiwanlottery.com"}
)
_FORBIDDEN_RESULT_LOCATOR_MARKERS = (
    "drawhistory",
    "historyresult",
    "lastnumber",
    "lotteryresult",
    "result",
    "winningnumber",
)
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
_NONBLOCK = getattr(os, "O_NONBLOCK", 0)

_ROOT_FIELDS = {"certificate_input", "certificate_input_sha256", "schema_version"}
_REQUIRED_INPUT_FIELDS = {
    "certification_reason",
    "certified_at",
    "certifying_authority",
    "draw_date",
    "draw_number",
    "lottery_type",
    "official_game_code",
    "official_source_id",
    "official_source_locator",
    "official_source_observed_at",
    "official_source_version",
    "schedule_timezone",
    "scheduled_at",
    "scheduled_local_time",
    "supporting_artifact_sha256",
    "supporting_artifact_type",
}
_OPTIONAL_INPUT_FIELDS = {"source_period_identifier"}


def read_owner_schedule_certificate(
    certificate_path: Path,
    supporting_artifact_path: Path,
) -> OwnerScheduleCertificate:
    """Safely read and validate a certificate plus its exact supporting artifact."""

    if not certificate_path.is_absolute() or not supporting_artifact_path.is_absolute():
        raise ScheduleCertificateInputError(
            "certificate and supporting artifact paths must be absolute"
        )
    certificate_bytes = _read_owner_file(
        certificate_path,
        maximum_bytes=MAX_SCHEDULE_CERTIFICATE_BYTES,
        label="schedule certificate",
    )
    artifact_bytes = _read_owner_file(
        supporting_artifact_path,
        maximum_bytes=MAX_SUPPORTING_ARTIFACT_BYTES,
        label="supporting artifact",
    )
    return parse_owner_schedule_certificate(
        certificate_bytes,
        source_filename=certificate_path.name,
        supporting_artifact=artifact_bytes,
    )


def parse_owner_schedule_certificate(
    encoded: bytes,
    *,
    source_filename: str,
    supporting_artifact: bytes,
) -> OwnerScheduleCertificate:
    """Parse a fully hash-bound certificate without SQLite or network access."""

    if type(encoded) is not bytes or len(encoded) > MAX_SCHEDULE_CERTIFICATE_BYTES:
        raise ScheduleCertificateInputError("schedule certificate bytes are invalid")
    if type(supporting_artifact) is not bytes or len(
        supporting_artifact
    ) > MAX_SUPPORTING_ARTIFACT_BYTES:
        raise ScheduleCertificateInputError("supporting artifact bytes are invalid")
    filename = _text(source_filename, "source_filename")
    if "/" in filename or "\\" in filename:
        raise ScheduleCertificateInputError("source_filename must be a basename")

    try:
        decoded: object = json.loads(
            encoded.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_json_members,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ScheduleCertificateInputError(
            "schedule certificate must be valid UTF-8 JSON"
        ) from exc
    root = _object(decoded, "schedule certificate")
    _expect_exact_keys(root, _ROOT_FIELDS, "schedule certificate")
    if root["schema_version"] != OWNER_SCHEDULE_CERTIFICATE_SCHEMA_VERSION:
        raise ScheduleCertificateInputError("certificate schema_version is unsupported")

    certificate_input = _object(root["certificate_input"], "certificate_input")
    _expect_bounded_keys(
        certificate_input,
        required=_REQUIRED_INPUT_FIELDS,
        optional=_OPTIONAL_INPUT_FIELDS,
        label="certificate_input",
    )
    expected_input_sha256 = _sha256(
        root["certificate_input_sha256"],
        "certificate_input_sha256",
    )
    actual_input_sha256 = _canonical_sha256(certificate_input)
    if actual_input_sha256 != expected_input_sha256:
        raise ScheduleCertificateInputError(
            "certificate_input_sha256 does not bind the exact certificate input"
        )

    try:
        lottery_type = LotteryType(_text(certificate_input["lottery_type"], "lottery_type"))
    except ValueError as exc:
        raise ScheduleCertificateInputError("lottery_type is unsupported") from exc
    if lottery_type not in {LotteryType.DAILY_539, LotteryType.POWER_LOTTO}:
        raise ScheduleCertificateInputError(
            "manual schedule certificates support DAILY_539 and POWER_LOTTO"
        )
    game_code = certificate_input["official_game_code"]
    if type(game_code) is not int or game_code != expected_schedule_game_code(lottery_type):
        raise ScheduleCertificateInputError(
            "official_game_code does not match lottery_type"
        )

    draw_number = _text(certificate_input["draw_number"], "draw_number")
    if _DRAW_NUMBER.fullmatch(draw_number) is None:
        raise ScheduleCertificateInputError("draw_number must be ASCII decimal")
    draw_date_value = _canonical_date(certificate_input["draw_date"], "draw_date")
    timezone_name = _text(certificate_input["schedule_timezone"], "schedule_timezone")
    if timezone_name != CANONICAL_SCHEDULE_TIMEZONE:
        raise ScheduleCertificateInputError(
            f"schedule_timezone must be {CANONICAL_SCHEDULE_TIMEZONE}"
        )
    local_time = _canonical_local_time(
        certificate_input["scheduled_local_time"],
        "scheduled_local_time",
    )
    scheduled_at = _canonical_utc(certificate_input["scheduled_at"], "scheduled_at")
    expected_scheduled_at = datetime.combine(
        draw_date_value,
        local_time,
        tzinfo=ZoneInfo(CANONICAL_SCHEDULE_TIMEZONE),
    ).astimezone(UTC)
    if scheduled_at != expected_scheduled_at:
        raise ScheduleCertificateInputError(
            "scheduled_at does not match draw_date and scheduled_local_time"
        )

    period_value = certificate_input.get("source_period_identifier")
    if period_value is None:
        source_period_identifier = None
    else:
        source_period_identifier = _text(
            period_value,
            "source_period_identifier",
        )
        if (
            _DRAW_NUMBER.fullmatch(source_period_identifier) is None
            or source_period_identifier != draw_number
        ):
            raise ScheduleCertificateInputError(
                "source_period_identifier must equal the explicit draw_number"
            )

    source_id = _text(certificate_input["official_source_id"], "official_source_id")
    source_version = _text(
        certificate_input["official_source_version"],
        "official_source_version",
    )
    source_locator = _text(
        certificate_input["official_source_locator"],
        "official_source_locator",
    )
    if source_id != OFFICIAL_SCHEDULE_SOURCE_ID:
        raise ScheduleCertificateInputError("official_source_id is not canonical")
    if source_version != OFFICIAL_SCHEDULE_SOURCE_VERSION:
        raise ScheduleCertificateInputError("official_source_version is not canonical")
    _validate_official_support_locator(source_locator)

    supporting_artifact_sha256 = _sha256(
        certificate_input["supporting_artifact_sha256"],
        "supporting_artifact_sha256",
    )
    if hashlib.sha256(supporting_artifact).hexdigest() != supporting_artifact_sha256:
        raise ScheduleCertificateInputError(
            "supporting_artifact_sha256 does not match the exact artifact"
        )
    if not _artifact_explicitly_contains_draw_number(supporting_artifact, draw_number):
        raise ScheduleCertificateInputError(
            "supporting artifact does not explicitly contain the draw_number"
        )

    observed_at = _canonical_utc(
        certificate_input["official_source_observed_at"],
        "official_source_observed_at",
    )
    certified_at = _canonical_utc(certificate_input["certified_at"], "certified_at")
    if certified_at < observed_at:
        raise ScheduleCertificateInputError(
            "certification cannot precede official source observation"
        )
    actor = _text(certificate_input["certifying_authority"], "certifying_authority")
    if actor != OWNER_SCHEDULE_CERTIFYING_AUTHORITY:
        raise ScheduleCertificateInputError(
            "certifying_authority is not the authorized Project Owner"
        )
    try:
        reason = ScheduleCertificateReason(
            _text(certificate_input["certification_reason"], "certification_reason")
        )
    except ValueError as exc:
        raise ScheduleCertificateInputError("certification_reason is unsupported") from exc
    try:
        artifact_type = OfficialSupportArtifactType(
            _text(certificate_input["supporting_artifact_type"], "supporting_artifact_type")
        )
    except ValueError as exc:
        raise ScheduleCertificateInputError(
            "supporting_artifact_type is not official evidence"
        ) from exc

    try:
        fact = CanonicalScheduleFact(
            announcement=TargetAnnouncement(
                target=ObservationTarget(
                    lottery_type=lottery_type,
                    draw_number=draw_number,
                    draw_date=draw_date_value,
                ),
                schedule_timezone=timezone_name,
                scheduled_at=scheduled_at,
                source=TargetSourceProvenance(
                    source_id=source_id,
                    source_version=source_version,
                    source_locator=source_locator,
                    source_sha256=supporting_artifact_sha256,
                    observed_at=observed_at,
                ),
            ),
            official_game_code=game_code,
            scheduled_local_time=local_time,
            source_period_identifier=source_period_identifier,
        )
        return OwnerScheduleCertificate(
            schema_version=OWNER_SCHEDULE_CERTIFICATE_SCHEMA_VERSION,
            source_filename=filename,
            certificate_input_sha256=expected_input_sha256,
            certificate_document_sha256=hashlib.sha256(encoded).hexdigest(),
            fact=fact,
            supporting_artifact_type=artifact_type,
            certified_at=certified_at,
            certifying_authority=actor,
            certification_reason=reason,
        )
    except ValueError as exc:
        raise ScheduleCertificateInputError(str(exc)) from exc


def _read_owner_file(path: Path, *, maximum_bytes: int, label: str) -> bytes:
    flags = os.O_RDONLY | _NOFOLLOW | _CLOEXEC | _NONBLOCK
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ScheduleCertificateInputError(f"cannot safely open {label}") from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ScheduleCertificateInputError(f"{label} must be a regular file")
        if metadata.st_uid != os.getuid():
            raise ScheduleCertificateInputError(f"{label} must be owner-owned")
        if stat.S_IMODE(metadata.st_mode) != 0o600:
            raise ScheduleCertificateInputError(f"{label} mode must be exactly 0600")
        if metadata.st_nlink != 1:
            raise ScheduleCertificateInputError(f"{label} must have exactly one hard link")
        if metadata.st_size > maximum_bytes:
            raise ScheduleCertificateInputError(f"{label} exceeds its bounded size limit")
        remaining = maximum_bytes + 1
        chunks: list[bytes] = []
        while remaining > 0:
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        encoded = b"".join(chunks)
        if len(encoded) > maximum_bytes:
            raise ScheduleCertificateInputError(f"{label} exceeds its bounded size limit")
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
            raise ScheduleCertificateInputError(f"{label} changed while being read")
        return encoded
    finally:
        os.close(descriptor)


def _reject_duplicate_json_members(pairs: list[tuple[str, object]]) -> dict[str, object]:
    mapping: dict[str, object] = {}
    for key, value in pairs:
        if key in mapping:
            raise ScheduleCertificateInputError(
                "schedule certificate contains duplicate JSON members"
            )
        mapping[key] = value
    return mapping


def _object(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ScheduleCertificateInputError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _expect_exact_keys(value: Mapping[str, object], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise ScheduleCertificateInputError(f"{label} fields do not match the contract")


def _expect_bounded_keys(
    value: Mapping[str, object],
    *,
    required: set[str],
    optional: set[str],
    label: str,
) -> None:
    actual = set(value)
    if not required <= actual or not actual <= required | optional:
        raise ScheduleCertificateInputError(f"{label} fields do not match the contract")


def _text(value: object, label: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ScheduleCertificateInputError(f"{label} must be canonical non-empty text")
    return value


def _sha256(value: object, label: str) -> str:
    text = _text(value, label)
    if _SHA256.fullmatch(text) is None:
        raise ScheduleCertificateInputError(f"{label} must be a lowercase SHA-256 digest")
    return text


def _canonical_date(value: object, label: str) -> date:
    text = _text(value, label)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise ScheduleCertificateInputError(f"{label} must be a Gregorian ISO date") from exc
    if parsed.isoformat() != text:
        raise ScheduleCertificateInputError(f"{label} must be a canonical ISO date")
    return parsed


def _canonical_local_time(value: object, label: str) -> time:
    text = _text(value, label)
    if _LOCAL_TIME.fullmatch(text) is None:
        raise ScheduleCertificateInputError(f"{label} must be canonical HH:MM:SS")
    return time.fromisoformat(text)


def _canonical_utc(value: object, label: str) -> datetime:
    text = _text(value, label)
    if not text.endswith("Z"):
        raise ScheduleCertificateInputError(f"{label} must use canonical UTC text")
    try:
        parsed = datetime.fromisoformat(f"{text[:-1]}+00:00")
    except ValueError as exc:
        raise ScheduleCertificateInputError(f"{label} must use canonical UTC text") from exc
    if parsed.tzinfo is not UTC or _utc_text(parsed) != text:
        raise ScheduleCertificateInputError(f"{label} must use canonical UTC text")
    return parsed


def _validate_official_support_locator(value: str) -> None:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ScheduleCertificateInputError(
            "official_source_locator must be an official Taiwan Lottery HTTPS URL"
        ) from exc
    if (
        len(value) > 2048
        or parsed.scheme != "https"
        or parsed.hostname not in _OFFICIAL_HTTPS_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.fragment
    ):
        raise ScheduleCertificateInputError(
            "official_source_locator must be an official Taiwan Lottery HTTPS URL"
        )
    folded_locator = f"{parsed.path}?{parsed.query}".lower().replace("_", "").replace("-", "")
    if any(marker in folded_locator for marker in _FORBIDDEN_RESULT_LOCATOR_MARKERS):
        raise ScheduleCertificateInputError(
            "completed-result endpoints cannot authorize a future schedule"
        )


def _artifact_explicitly_contains_draw_number(encoded: bytes, draw_number: str) -> bool:
    pattern = rb"(?<![0-9])" + re.escape(draw_number.encode("ascii")) + rb"(?![0-9])"
    return re.search(pattern, encoded) is not None


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


__all__ = [
    "MAX_SCHEDULE_CERTIFICATE_BYTES",
    "MAX_SUPPORTING_ARTIFACT_BYTES",
    "parse_owner_schedule_certificate",
    "read_owner_schedule_certificate",
]
