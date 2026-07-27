"""Closed values for durable ordered-candidate materialization.

This module is deliberately I/O-free.  It defines the source snapshot,
complete attempt ledger, and future publication binding without choosing a
database, filesystem, strategy registry, or CLI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import PurePosixPath

from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import BIG_LOTTO_RULE_CONTRACT
from lottolab.domain.ordered_candidate_emission import OrderedCandidateEmission
from lottolab.domain.ordered_candidate_evidence import (
    CandidateSourceArtifactIdentity,
)

ORDERED_CANDIDATE_MATERIALIZATION_SCHEMA_VERSION = "1.0.0"

_ASCII_DECIMAL = re.compile(r"[0-9]+", flags=re.ASCII)
_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)
_STRATEGY_ID = re.compile(r"[a-z0-9][a-z0-9_]{0,127}", flags=re.ASCII)
_STRATEGY_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", flags=re.ASCII)


class OrderedCandidateMaterializationStatus(StrEnum):
    """The exact closed status vocabulary for one requested attempt."""

    OK = "OK"
    TARGET_NOT_FOUND = "TARGET_NOT_FOUND"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    REJECTED = "REJECTED"
    INVALID_OUTPUT = "INVALID_OUTPUT"
    STRATEGY_UNAVAILABLE = "STRATEGY_UNAVAILABLE"
    REPLAY_ERROR = "REPLAY_ERROR"
    STORAGE_ERROR = "STORAGE_ERROR"


def _require_text(value: object, name: str) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be a non-empty canonical string")


def _require_decimal(value: object, name: str) -> None:
    if type(value) is not str or _ASCII_DECIMAL.fullmatch(value) is None:
        raise ValueError(f"{name} must be an ASCII decimal draw identity")


def _require_sha256(value: object, name: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be an exact lowercase SHA-256")


@dataclass(frozen=True, slots=True)
class OrderedCandidateSourceRow:
    """One exact BIG_LOTTO row participating in the source snapshot."""

    lottery_type: LotteryType
    draw_date: date
    draw_number: str
    main_numbers: tuple[int, ...]
    special_numbers: tuple[int, ...]
    normalized_record_hash: str

    def __post_init__(self) -> None:
        if self.lottery_type is not LotteryType.BIG_LOTTO:
            raise ValueError("ordered-candidate materialization is BIG_LOTTO only")
        if type(self.draw_date) is not date:
            raise ValueError("draw_date must be a date")
        _require_decimal(self.draw_number, "draw_number")
        rule = BIG_LOTTO_RULE_CONTRACT
        if (
            type(self.main_numbers) is not tuple
            or len(self.main_numbers) != rule.main_number_count
            or any(type(number) is not int for number in self.main_numbers)
            or len(set(self.main_numbers)) != rule.main_number_count
            or any(
                not rule.main_number_min <= number <= rule.main_number_max
                for number in self.main_numbers
            )
        ):
            raise ValueError("main_numbers has an invalid BIG_LOTTO shape")
        if (
            type(self.special_numbers) is not tuple
            or len(self.special_numbers) != 1
            or type(self.special_numbers[0]) is not int
            or not rule.special_number_min
            <= self.special_numbers[0]
            <= rule.special_number_max
            or self.special_numbers[0] in self.main_numbers
        ):
            raise ValueError("special_numbers has an invalid BIG_LOTTO shape")
        _require_sha256(self.normalized_record_hash, "normalized_record_hash")

    @property
    def sort_key(self) -> tuple[date, int]:
        return (self.draw_date, int(self.draw_number))

    def canonical_dict(self) -> dict[str, object]:
        return {
            "draw_date": self.draw_date.isoformat(),
            "draw_number": self.draw_number,
            "lottery_type": self.lottery_type.value,
            "main_numbers": list(self.main_numbers),
            "normalized_record_hash": self.normalized_record_hash,
            "special_numbers": list(self.special_numbers),
        }


@dataclass(frozen=True, slots=True)
class OrderedCandidateSourceSnapshot:
    """All BIG_LOTTO source rows and their exact LCJ-1 content digest."""

    lottery_type: LotteryType
    rows: tuple[OrderedCandidateSourceRow, ...]
    source_snapshot_sha256: str

    def __post_init__(self) -> None:
        if self.lottery_type is not LotteryType.BIG_LOTTO:
            raise ValueError("source snapshot is BIG_LOTTO only")
        if type(self.rows) is not tuple or any(
            type(row) is not OrderedCandidateSourceRow for row in self.rows
        ):
            raise ValueError("rows must be an immutable source-row tuple")
        if any(row.lottery_type is not self.lottery_type for row in self.rows):
            raise ValueError("source rows must match the snapshot lottery type")
        if tuple(sorted(self.rows, key=lambda row: row.sort_key)) != self.rows:
            raise ValueError("source rows must be in date/numeric-draw ascending order")
        if len({row.draw_number for row in self.rows}) != len(self.rows):
            raise ValueError("source rows must not repeat draw_number")
        _require_sha256(self.source_snapshot_sha256, "source_snapshot_sha256")


@dataclass(frozen=True, slots=True)
class OrderedCandidateMaterializationAttempt:
    """One ledger row for exactly one requested target x strategy attempt."""

    ordinal: int
    target_ordinal: int
    strategy_ordinal: int
    target_draw: str
    strategy_id: str
    status: OrderedCandidateMaterializationStatus
    reason_code: str | None = None
    history_cutoff: str | None = None
    strategy_version: str | None = None
    emission_relative_path: str | None = None
    emission_payload_sha256: str | None = None
    emission_file_sha256: str | None = None

    def __post_init__(self) -> None:
        for value, name in (
            (self.ordinal, "ordinal"),
            (self.target_ordinal, "target_ordinal"),
            (self.strategy_ordinal, "strategy_ordinal"),
        ):
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        _require_decimal(self.target_draw, "target_draw")
        if type(self.strategy_id) is not str or _STRATEGY_ID.fullmatch(
            self.strategy_id
        ) is None:
            raise ValueError("strategy_id is not path-safe canonical ASCII")
        if type(self.status) is not OrderedCandidateMaterializationStatus:
            raise ValueError("status must be an OrderedCandidateMaterializationStatus")
        if self.reason_code is not None:
            _require_text(self.reason_code, "reason_code")
        if self.history_cutoff is not None:
            _require_decimal(self.history_cutoff, "history_cutoff")
            if int(self.target_draw) <= int(self.history_cutoff):
                raise ValueError("history_cutoff must precede target_draw")
        if self.strategy_version is not None and (
            type(self.strategy_version) is not str
            or _STRATEGY_VERSION.fullmatch(self.strategy_version) is None
        ):
            raise ValueError("strategy_version is not path-safe canonical ASCII")

        artifact_values = (
            self.emission_relative_path,
            self.emission_payload_sha256,
            self.emission_file_sha256,
        )
        if self.status is OrderedCandidateMaterializationStatus.OK:
            if (
                self.reason_code is not None
                or self.history_cutoff is None
                or self.strategy_version is None
                or any(value is None for value in artifact_values)
            ):
                raise ValueError(
                    "OK attempts require cutoff/version/artifact identity and no reason"
                )
            expected_path = ordered_candidate_emission_relative_path(
                target_draw=self.target_draw,
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
            )
            if self.emission_relative_path != expected_path:
                raise ValueError("emission_relative_path does not match attempt identity")
            _require_sha256(
                self.emission_payload_sha256,
                "emission_payload_sha256",
            )
            _require_sha256(self.emission_file_sha256, "emission_file_sha256")
        elif any(value is not None for value in artifact_values):
            raise ValueError("non-OK attempts must not carry artifact identity")


@dataclass(frozen=True, slots=True)
class OrderedCandidateMaterializationSummary:
    """Compact successful materialization result suitable for CLI stdout."""

    output_directory: str
    source_snapshot_sha256: str
    attempt_count: int
    ok_attempt_count: int
    status_counts: tuple[tuple[OrderedCandidateMaterializationStatus, int], ...]

    def __post_init__(self) -> None:
        _require_text(self.output_directory, "output_directory")
        _require_sha256(self.source_snapshot_sha256, "source_snapshot_sha256")
        if (
            type(self.attempt_count) is not int
            or self.attempt_count < 1
            or type(self.ok_attempt_count) is not int
            or not 0 <= self.ok_attempt_count <= self.attempt_count
        ):
            raise ValueError("summary counts are invalid")
        expected_statuses = tuple(OrderedCandidateMaterializationStatus)
        if tuple(status for status, _ in self.status_counts) != expected_statuses:
            raise ValueError("status_counts must contain every closed status in enum order")
        if any(type(count) is not int or count < 0 for _, count in self.status_counts):
            raise ValueError("status counts must be non-negative integers")
        if sum(count for _, count in self.status_counts) != self.attempt_count:
            raise ValueError("status counts must sum to attempt_count")
        if dict(self.status_counts)[OrderedCandidateMaterializationStatus.OK] != (
            self.ok_attempt_count
        ):
            raise ValueError("OK status count must equal ok_attempt_count")


def ordered_candidate_emission_relative_path(
    *,
    target_draw: str,
    strategy_id: str,
    strategy_version: str,
) -> str:
    _require_decimal(target_draw, "target_draw")
    if _STRATEGY_ID.fullmatch(strategy_id) is None:
        raise ValueError("strategy_id is not path-safe canonical ASCII")
    if _STRATEGY_VERSION.fullmatch(strategy_version) is None:
        raise ValueError("strategy_version is not path-safe canonical ASCII")
    return (
        f"emissions/target-{target_draw}/strategy-{strategy_id}/"
        f"version-{strategy_version}/replicate-000001.json"
    )


def build_candidate_source_artifact_identity(
    *,
    attempt: OrderedCandidateMaterializationAttempt,
    publication_repository: str,
    publication_commit_oid: str,
    publication_package_path: str,
) -> CandidateSourceArtifactIdentity:
    """Bind one sealed OK emission to future external publication identity."""

    if attempt.status is not OrderedCandidateMaterializationStatus.OK:
        raise ValueError("only an OK attempt can be bound to a source artifact")
    _require_text(publication_package_path, "publication_package_path")
    package_path = PurePosixPath(publication_package_path)
    if (
        str(package_path) != publication_package_path
        or package_path.is_absolute()
        or any(
        part in {"", ".", ".."} for part in package_path.parts
        )
    ):
        raise ValueError("publication_package_path must be a canonical relative POSIX path")
    assert attempt.emission_relative_path is not None
    assert attempt.emission_file_sha256 is not None
    return CandidateSourceArtifactIdentity(
        repository=publication_repository,
        commit_oid=publication_commit_oid,
        path=str(package_path / attempt.emission_relative_path),
        sha256=attempt.emission_file_sha256,
    )


def attempt_from_emission(
    *,
    ordinal: int,
    target_ordinal: int,
    strategy_ordinal: int,
    emission: OrderedCandidateEmission,
    emission_payload_sha256: str,
    emission_file_sha256: str,
) -> OrderedCandidateMaterializationAttempt:
    relative_path = ordered_candidate_emission_relative_path(
        target_draw=emission.target_draw,
        strategy_id=emission.strategy_id,
        strategy_version=emission.strategy_version,
    )
    return OrderedCandidateMaterializationAttempt(
        ordinal=ordinal,
        target_ordinal=target_ordinal,
        strategy_ordinal=strategy_ordinal,
        target_draw=emission.target_draw,
        strategy_id=emission.strategy_id,
        status=OrderedCandidateMaterializationStatus.OK,
        history_cutoff=emission.history_cutoff,
        strategy_version=emission.strategy_version,
        emission_relative_path=relative_path,
        emission_payload_sha256=emission_payload_sha256,
        emission_file_sha256=emission_file_sha256,
    )


__all__ = [
    "ORDERED_CANDIDATE_MATERIALIZATION_SCHEMA_VERSION",
    "OrderedCandidateMaterializationAttempt",
    "OrderedCandidateMaterializationStatus",
    "OrderedCandidateMaterializationSummary",
    "OrderedCandidateSourceRow",
    "OrderedCandidateSourceSnapshot",
    "attempt_from_emission",
    "build_candidate_source_artifact_identity",
    "ordered_candidate_emission_relative_path",
]
