"""Fail-closed seal and official-outcome readers for Next-Draw P4."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from collections.abc import Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast

from lottolab.domain.draws import LotteryType
from lottolab.domain.next_draw_outcome_attribution import (
    NEXT_DRAW_RECOMMENDATION_SEAL_V1,
    NextDrawOfficialOutcome,
    NextDrawOfficialOutcomeProvenance,
    VerifiedNextDrawRecommendationSeal,
)
from lottolab.domain.next_draw_recommendation_seal import (
    NextDrawRecommendationSealV1,
    parse_next_draw_recommendation_seal,
)
from lottolab.infrastructure.persistence.draw_schema import (
    CURRENT_SCHEMA_VERSION,
    LocalDataPaths,
    open_database,
    verify_schema_read_only,
)

_MAX_SEAL_BYTES = 4 * 1024 * 1024


class NextDrawP4SealAuthorityError(RuntimeError):
    """An explicit seal file failed a P4 authority check."""


class NextDrawP4OfficialOutcomeStorageError(RuntimeError):
    """DRAW_DATA_V3 is absent, malformed, non-successful, or target-inconsistent."""


class FileSystemVerifiedNextDrawRecommendationSealReader:
    """Verify raw SHA, canonical bytes, self hash, path, target, and schema."""

    def read_verified_seal(
        self,
        seal_file: Path,
        *,
        expected_file_sha256: str,
        expected_seal_digest: str,
        lottery_type: LotteryType,
        target_draw_number: str,
        target_draw_date: date,
    ) -> VerifiedNextDrawRecommendationSeal:
        path = _validate_seal_path(
            seal_file,
            lottery_type=lottery_type,
            target_draw_number=target_draw_number,
            target_draw_date=target_draw_date,
        )
        raw = _read_plain_file(path)
        raw_sha256 = hashlib.sha256(raw).hexdigest()
        if raw_sha256 != expected_file_sha256:
            raise NextDrawP4SealAuthorityError("seal raw file SHA-256 does not match expectation")
        try:
            decoded: object = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise NextDrawP4SealAuthorityError("seal file is not valid UTF-8 JSON") from exc
        if not isinstance(decoded, Mapping):
            raise NextDrawP4SealAuthorityError("seal file must decode to an object")
        try:
            seal = parse_next_draw_recommendation_seal(
                cast(Mapping[str, object], decoded)
            )
        except (TypeError, ValueError) as exc:
            raise NextDrawP4SealAuthorityError("seal schema or self digest is invalid") from exc
        canonical_bytes = (
            json.dumps(
                seal.canonical_dict(),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
        if raw != canonical_bytes:
            raise NextDrawP4SealAuthorityError("seal file bytes are not canonical")
        if seal.seal_digest != expected_seal_digest:
            raise NextDrawP4SealAuthorityError("seal self digest does not match expectation")
        if (
            seal.target.lottery_type is not lottery_type
            or seal.target.draw_number != target_draw_number
            or seal.target.draw_date != target_draw_date
        ):
            raise NextDrawP4SealAuthorityError("seal target does not match the exact request")
        is_v1 = isinstance(seal, NextDrawRecommendationSealV1)
        if is_v1 != (seal.schema_version == NEXT_DRAW_RECOMMENDATION_SEAL_V1):
            raise NextDrawP4SealAuthorityError("seal runtime type contradicts schema_version")
        return VerifiedNextDrawRecommendationSeal(
            schema_version=seal.schema_version,
            target=seal.target,
            source_head=None if is_v1 else seal.source_head,
            source_tree=None if is_v1 else seal.source_tree,
            buckets=seal.buckets,
            seal_digest=seal.seal_digest,
            seal_file_sha256=raw_sha256,
        )


def _validate_seal_path(
    seal_file: Path,
    *,
    lottery_type: LotteryType,
    target_draw_number: str,
    target_draw_date: date,
) -> Path:
    if not isinstance(cast(object, seal_file), Path) or not seal_file.is_absolute():
        raise NextDrawP4SealAuthorityError("seal_file must be an explicit absolute path")
    expected_target_directory = f"{target_draw_date.isoformat()}_{target_draw_number}"
    if (
        seal_file.name != "seal.json"
        or seal_file.parent.name != expected_target_directory
        or seal_file.parent.parent.name != lottery_type.value
    ):
        raise NextDrawP4SealAuthorityError("seal_file path does not match the exact target")
    return seal_file


def _read_plain_file(path: Path) -> bytes:
    try:
        metadata = os.lstat(path)
    except OSError as exc:
        raise NextDrawP4SealAuthorityError("seal_file is unavailable") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise NextDrawP4SealAuthorityError("seal_file must be a plain non-symlink file")
    if metadata.st_size > _MAX_SEAL_BYTES:
        raise NextDrawP4SealAuthorityError("seal_file exceeds the accepted size")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise NextDrawP4SealAuthorityError("seal_file cannot be read") from exc
    try:
        after = os.lstat(path)
    except OSError as exc:
        raise NextDrawP4SealAuthorityError("seal_file changed while it was read") from exc
    if (
        after.st_ino != metadata.st_ino
        or after.st_dev != metadata.st_dev
        or after.st_size != metadata.st_size
        or after.st_mtime_ns != metadata.st_mtime_ns
    ):
        raise NextDrawP4SealAuthorityError("seal_file changed while it was read")
    return raw


class SQLiteNextDrawOfficialOutcomeReader:
    """Read one exact legal BIG_LOTTO outcome from an explicit DRAW_DATA_V3 DB."""

    def __init__(self, database: Path) -> None:
        if not isinstance(cast(object, database), Path) or not database.is_absolute():
            raise ValueError("draw database must be an explicit absolute path")
        self._paths = LocalDataPaths(data_directory=database.parent, database=database)

    def read_official_outcome(
        self,
        lottery_type: LotteryType,
        target_draw_number: str,
        target_draw_date: date,
    ) -> NextDrawOfficialOutcome | None:
        if lottery_type is not LotteryType.BIG_LOTTO:
            raise NextDrawP4OfficialOutcomeStorageError(
                "P4 outcome authority supports BIG_LOTTO only"
            )
        try:
            if not verify_schema_read_only(self._paths):
                return None
            with open_database(self._paths, read_only=True) as connection:
                version_row = connection.execute(
                    "SELECT MAX(version) FROM schema_migrations"
                ).fetchone()
                if version_row != (CURRENT_SCHEMA_VERSION,):
                    raise NextDrawP4OfficialOutcomeStorageError(
                        "official outcome authority must be exact DRAW_DATA_V3"
                    )
                row = connection.execute(
                    """
                    SELECT
                        d.draw_date, d.main_numbers_json, d.special_numbers_json,
                        d.normalized_record_hash, d.source_name, d.source_reference,
                        d.ingestion_run_id, r.operation_type, r.status,
                        r.source_filename, r.source_sha256, r.parser_version,
                        r.completed_at, r.error_summary, r.lottery_type
                    FROM draws AS d
                    LEFT JOIN ingestion_runs AS r ON r.id = d.ingestion_run_id
                    WHERE d.lottery_type = ? AND d.draw_number = ?
                    """,
                    (lottery_type.value, target_draw_number),
                ).fetchone()
        except NextDrawP4OfficialOutcomeStorageError:
            raise
        except Exception as exc:
            raise NextDrawP4OfficialOutcomeStorageError(
                "official outcome storage could not be verified read-only"
            ) from exc
        if row is None:
            return None
        return _decode_official_outcome(
            lottery_type=lottery_type,
            target_draw_number=target_draw_number,
            target_draw_date=target_draw_date,
            row=tuple(row),
        )


def _decode_official_outcome(
    *,
    lottery_type: LotteryType,
    target_draw_number: str,
    target_draw_date: date,
    row: tuple[object, ...],
) -> NextDrawOfficialOutcome:
    if len(row) != 15:
        raise NextDrawP4OfficialOutcomeStorageError("official outcome row shape is invalid")
    (
        draw_date_raw,
        main_numbers_raw,
        special_numbers_raw,
        normalized_record_hash,
        source_name,
        source_reference,
        ingestion_run_id,
        operation_type,
        status,
        source_filename,
        source_sha256,
        parser_version,
        completed_at,
        error_summary,
        ingestion_lottery_type,
    ) = row
    draw_date_value = _date_value(draw_date_raw, "draw_date")
    if draw_date_value != target_draw_date:
        raise NextDrawP4OfficialOutcomeStorageError(
            "official outcome draw date does not match the exact target"
        )
    if (
        status != "SUCCESS"
        or completed_at is None
        or error_summary is not None
        or ingestion_lottery_type != lottery_type.value
    ):
        raise NextDrawP4OfficialOutcomeStorageError(
            "official outcome lacks successful ingestion provenance"
        )
    main_numbers = _number_tuple(main_numbers_raw, "main_numbers_json")
    special_numbers = _number_tuple(special_numbers_raw, "special_numbers_json")
    if len(special_numbers) != 1:
        raise NextDrawP4OfficialOutcomeStorageError(
            "official outcome must contain exactly one special number"
        )
    try:
        provenance = NextDrawOfficialOutcomeProvenance(
            ingestion_run_id=_text(ingestion_run_id, "ingestion_run_id"),
            operation_type=_text(operation_type, "operation_type"),
            status=_text(status, "status"),
            source_filename=_text(source_filename, "source_filename"),
            source_sha256=_text(source_sha256, "source_sha256"),
            parser_version=_text(parser_version, "parser_version"),
            completed_at=_utc_datetime(completed_at, "completed_at"),
            source_name=_optional_text(source_name, "source_name"),
            source_reference=_optional_text(source_reference, "source_reference"),
        )
        return NextDrawOfficialOutcome.create(
            lottery_type=lottery_type,
            draw_number=target_draw_number,
            draw_date=draw_date_value,
            winning_main_numbers=main_numbers,
            winning_special_number=special_numbers[0],
            normalized_record_hash=_text(
                normalized_record_hash, "normalized_record_hash"
            ),
            provenance=provenance,
        )
    except (TypeError, ValueError) as exc:
        raise NextDrawP4OfficialOutcomeStorageError(
            "official outcome row violates the closed P4 contract"
        ) from exc


def _text(value: object, label: str) -> str:
    if type(value) is not str or not value:
        raise NextDrawP4OfficialOutcomeStorageError(f"{label} must be non-empty text")
    return value


def _optional_text(value: object, label: str) -> str | None:
    return None if value is None else _text(value, label)


def _date_value(value: object, label: str) -> date:
    text = _text(value, label)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise NextDrawP4OfficialOutcomeStorageError(f"{label} is invalid") from exc
    if parsed.isoformat() != text:
        raise NextDrawP4OfficialOutcomeStorageError(f"{label} is not canonical")
    return parsed


def _utc_datetime(value: object, label: str) -> datetime:
    text = _text(value, label)
    if not text.endswith("Z"):
        raise NextDrawP4OfficialOutcomeStorageError(f"{label} must use UTC Z text")
    try:
        parsed = datetime.fromisoformat(f"{text[:-1]}+00:00")
    except ValueError as exc:
        raise NextDrawP4OfficialOutcomeStorageError(f"{label} is invalid") from exc
    if parsed.tzinfo is not UTC or parsed.isoformat().replace("+00:00", "Z") != text:
        raise NextDrawP4OfficialOutcomeStorageError(f"{label} is not canonical UTC")
    return parsed


def _number_tuple(value: object, label: str) -> tuple[int, ...]:
    if type(value) is not str:
        raise NextDrawP4OfficialOutcomeStorageError(f"{label} must be text")
    try:
        decoded: object = json.loads(value)
    except json.JSONDecodeError as exc:
        raise NextDrawP4OfficialOutcomeStorageError(f"{label} is invalid JSON") from exc
    if type(decoded) is not list:
        raise NextDrawP4OfficialOutcomeStorageError(
            f"{label} must decode to exact integers"
        )
    items = cast(list[object], decoded)
    if any(type(item) is not int for item in items):
        raise NextDrawP4OfficialOutcomeStorageError(
            f"{label} must decode to exact integers"
        )
    return tuple(cast(list[int], items))


__all__ = [
    "FileSystemVerifiedNextDrawRecommendationSealReader",
    "NextDrawP4OfficialOutcomeStorageError",
    "NextDrawP4SealAuthorityError",
    "SQLiteNextDrawOfficialOutcomeReader",
]
