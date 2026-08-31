"""Create-once writer and read-only projection for Next-Draw P4 artifacts."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Generator, Mapping
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast

from lottolab.domain.draws import LotteryType
from lottolab.domain.next_draw_outcome_attribution import (
    NextDrawOutcomeAttribution,
    NextDrawOutcomeAttributionPage,
    NextDrawP4PersistenceOutcome,
    NextDrawP4PersistResult,
    serialize_next_draw_outcome_attribution,
)
from lottolab.infrastructure.persistence.next_draw_p4_schema import (
    NextDrawP4SchemaError,
    initialize_schema,
    open_database,
    verify_schema_read_only,
)


class NextDrawP4StorageError(RuntimeError):
    """The isolated P4 authority failed a storage operation."""


class NextDrawP4StorageTamperError(NextDrawP4StorageError):
    """Stored row identity and reconstructed canonical content disagree."""


def _default_clock() -> datetime:
    return datetime.now(UTC)


class SQLiteNextDrawP4AttributionRepository:
    """Explicit-path implementation of the narrow P4 reader/writer ports."""

    def __init__(
        self,
        database: Path,
        *,
        clock: Callable[[], datetime] = _default_clock,
    ) -> None:
        self._database = database
        self._clock = clock

    def persist_next_draw_outcome_attribution(
        self,
        artifact: NextDrawOutcomeAttribution,
        canonical_bytes: bytes,
    ) -> NextDrawP4PersistResult:
        if canonical_bytes != serialize_next_draw_outcome_attribution(artifact):
            raise NextDrawP4StorageError(
                "caller-supplied canonical bytes do not match the P4 artifact"
            )
        try:
            initialize_schema(self._database)
            with open_database(self._database) as connection:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    row = connection.execute(
                        """
                        SELECT canonical_bytes
                        FROM next_draw_p4_attributions
                        WHERE lottery_type = ?
                          AND target_draw_number = ?
                          AND target_draw_date = ?
                        """,
                        (
                            artifact.target.lottery_type.value,
                            artifact.target.draw_number,
                            artifact.target.draw_date.isoformat(),
                        ),
                    ).fetchone()
                    if row is not None:
                        connection.rollback()
                        outcome = (
                            NextDrawP4PersistenceOutcome.ALREADY_PRESENT
                            if bytes(row[0]) == canonical_bytes
                            else NextDrawP4PersistenceOutcome.CONFLICT
                        )
                        return NextDrawP4PersistResult(outcome, artifact.attribution_sha256)
                    connection.execute(
                        """
                        INSERT INTO next_draw_p4_attributions (
                            lottery_type, target_draw_number, target_draw_date,
                            seal_file_sha256, seal_digest, outcome_sha256,
                            scoring_contract_sha256, attribution_sha256,
                            canonical_bytes, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            artifact.target.lottery_type.value,
                            artifact.target.draw_number,
                            artifact.target.draw_date.isoformat(),
                            artifact.seal_file_sha256,
                            artifact.seal_digest,
                            artifact.official_outcome.outcome_sha256,
                            artifact.scoring_contract_sha256,
                            artifact.attribution_sha256,
                            canonical_bytes,
                            _utc_text(self._clock()),
                        ),
                    )
                    connection.commit()
                    return NextDrawP4PersistResult(
                        NextDrawP4PersistenceOutcome.INSERTED,
                        artifact.attribution_sha256,
                    )
                except BaseException:
                    if connection.in_transaction:
                        connection.rollback()
                    raise
        except NextDrawP4StorageError:
            raise
        except (NextDrawP4SchemaError, sqlite3.Error, OSError, TypeError, ValueError) as exc:
            raise NextDrawP4StorageError("P4 persistence failed") from exc

    def get_attribution(
        self,
        lottery_type: LotteryType,
        target_draw_number: str,
        target_draw_date: date,
    ) -> NextDrawOutcomeAttribution | None:
        if not _verify_available(self._database):
            return None
        with _read_only_connection(self._database) as connection:
            row = connection.execute(
                """
                SELECT seal_file_sha256, seal_digest, outcome_sha256,
                       scoring_contract_sha256, attribution_sha256, canonical_bytes
                FROM next_draw_p4_attributions
                WHERE lottery_type = ?
                  AND target_draw_number = ?
                  AND target_draw_date = ?
                """,
                (
                    lottery_type.value,
                    target_draw_number,
                    target_draw_date.isoformat(),
                ),
            ).fetchone()
        if row is None:
            return None
        return _decode_artifact(
            row,
            lottery_type=lottery_type,
            target_draw_number=target_draw_number,
            target_draw_date=target_draw_date.isoformat(),
        )

    def list_attributions(
        self,
        *,
        lottery_type: LotteryType | None,
        page: int,
        page_size: int,
    ) -> NextDrawOutcomeAttributionPage:
        if (
            type(page) is not int
            or page < 1
            or type(page_size) is not int
            or not 1 <= page_size <= 100
        ):
            raise ValueError("P4 history pagination is invalid")
        if not _verify_available(self._database):
            return NextDrawOutcomeAttributionPage((), page, page_size, 0, 0)
        condition = "" if lottery_type is None else " WHERE lottery_type = ?"
        parameters: tuple[object, ...] = () if lottery_type is None else (lottery_type.value,)
        offset = (page - 1) * page_size
        with _read_only_connection(self._database) as connection:
            count_row = connection.execute(
                f"SELECT COUNT(*) FROM next_draw_p4_attributions{condition}",
                parameters,
            ).fetchone()
            if count_row is None or type(count_row[0]) is not int:
                raise NextDrawP4StorageTamperError("P4 history count is malformed")
            total_count = count_row[0]
            rows = connection.execute(
                f"""
                SELECT lottery_type, target_draw_number, target_draw_date,
                       seal_file_sha256, seal_digest, outcome_sha256,
                       scoring_contract_sha256, attribution_sha256, canonical_bytes
                FROM next_draw_p4_attributions{condition}
                ORDER BY created_at DESC, target_draw_date DESC,
                         length(target_draw_number) DESC, target_draw_number DESC,
                         lottery_type ASC
                LIMIT ? OFFSET ?
                """,
                (*parameters, page_size, offset),
            ).fetchall()
        records = tuple(_decode_history_row(row) for row in rows)
        total_pages = (total_count + page_size - 1) // page_size if total_count else 0
        return NextDrawOutcomeAttributionPage(
            records=records,
            page=page,
            page_size=page_size,
            total_count=total_count,
            total_pages=total_pages,
        )


def _decode_history_row(row: tuple[object, ...]) -> NextDrawOutcomeAttribution:
    if len(row) != 9:
        raise NextDrawP4StorageTamperError("P4 history row shape is malformed")
    try:
        lottery_type = LotteryType(str(row[0]))
    except ValueError as exc:
        raise NextDrawP4StorageTamperError("P4 history lottery_type is malformed") from exc
    return _decode_artifact(
        row[3:],
        lottery_type=lottery_type,
        target_draw_number=str(row[1]),
        target_draw_date=str(row[2]),
    )


def _decode_artifact(
    row: tuple[object, ...],
    *,
    lottery_type: LotteryType,
    target_draw_number: str,
    target_draw_date: str,
) -> NextDrawOutcomeAttribution:
    if len(row) != 6:
        raise NextDrawP4StorageTamperError("P4 artifact row shape is malformed")
    (
        seal_file_sha256,
        seal_digest,
        outcome_sha256,
        scoring_contract_sha256,
        attribution_sha256,
        canonical_blob,
    ) = row
    try:
        if type(canonical_blob) is not bytes:
            raise TypeError("canonical P4 payload is not a BLOB")
        canonical_bytes = canonical_blob
        decoded: object = json.loads(canonical_bytes.decode("utf-8"))
        if not isinstance(decoded, Mapping):
            raise ValueError("canonical P4 payload is not an object")
        artifact = NextDrawOutcomeAttribution.from_canonical_dict(
            cast(Mapping[str, object], decoded)
        )
    except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NextDrawP4StorageTamperError("stored P4 artifact is malformed") from exc
    if canonical_bytes != serialize_next_draw_outcome_attribution(artifact):
        raise NextDrawP4StorageTamperError("stored P4 canonical bytes do not reconstruct")
    expected_identity = (
        lottery_type,
        target_draw_number,
        target_draw_date,
        str(seal_file_sha256),
        str(seal_digest),
        str(outcome_sha256),
        str(scoring_contract_sha256),
        str(attribution_sha256),
    )
    actual_identity = (
        artifact.target.lottery_type,
        artifact.target.draw_number,
        artifact.target.draw_date.isoformat(),
        artifact.seal_file_sha256,
        artifact.seal_digest,
        artifact.official_outcome.outcome_sha256,
        artifact.scoring_contract_sha256,
        artifact.attribution_sha256,
    )
    if actual_identity != expected_identity:
        raise NextDrawP4StorageTamperError("stored P4 row identity disagrees with artifact")
    return artifact


def _verify_available(database: Path) -> bool:
    try:
        return verify_schema_read_only(database)
    except (NextDrawP4SchemaError, sqlite3.Error, OSError) as exc:
        raise NextDrawP4StorageError("P4 storage schema verification failed") from exc


@contextmanager
def _read_only_connection(database: Path) -> Generator[sqlite3.Connection]:
    try:
        with open_database(database, read_only=True) as connection:
            yield connection
    except (NextDrawP4SchemaError, sqlite3.Error, OSError) as exc:
        raise NextDrawP4StorageError("P4 storage is unavailable") from exc


def _utc_text(value: datetime) -> str:
    if value.tzinfo is not UTC:
        raise ValueError("P4 persistence clock must return a UTC datetime")
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


__all__ = [
    "NextDrawP4StorageError",
    "NextDrawP4StorageTamperError",
    "SQLiteNextDrawP4AttributionRepository",
]
