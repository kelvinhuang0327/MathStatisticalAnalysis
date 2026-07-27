"""Canonical sealed-package bytes for ordered-candidate materialization."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, cast

from lottolab.domain.draws import LotteryType
from lottolab.domain.ordered_candidate_materialization import (
    OrderedCandidateMaterializationAttempt,
    OrderedCandidateMaterializationStatus,
    OrderedCandidateSourceRow,
)
from lottolab.evidence.canonical_json import (
    canonical_bytes,
    loads_canonical,
    self_key_removed_sha256,
    sha256_hex,
)
from lottolab.evidence.ordered_candidate_emission_artifact import (
    deserialize_ordered_candidate_emission_artifact,
)

ORDERED_CANDIDATE_PACKAGE_MANIFEST_SCHEMA_VERSION = "1.0.0"

_MANIFEST_KEYS = {
    "attempt_count",
    "attempts",
    "dataset_id",
    "dataset_version",
    "lottery_type",
    "manifest_payload_sha256",
    "manifest_schema_version",
    "maximum_history_draws",
    "minimum_history_draws",
    "ok_attempt_count",
    "replicate",
    "source_snapshot_sha256",
    "status_counts",
    "strategy_ids",
    "target_draws",
}
_ATTEMPT_REQUIRED_KEYS = {
    "ordinal",
    "status",
    "strategy_id",
    "strategy_ordinal",
    "target_draw",
    "target_ordinal",
}
_ATTEMPT_OPTIONAL_KEYS = {
    "emission_file_sha256",
    "emission_payload_sha256",
    "emission_relative_path",
    "history_cutoff",
    "reason_code",
    "strategy_version",
}


class OrderedCandidateEmissionPackageError(ValueError):
    """Package values or bytes violate the frozen closed contract."""


@dataclass(frozen=True, slots=True)
class OrderedCandidateEmissionFile:
    relative_path: str
    data: bytes
    payload_sha256: str
    file_sha256: str

    def __post_init__(self) -> None:
        if type(self.relative_path) is not str or not self.relative_path:
            raise ValueError("relative_path must be a non-empty string")
        if type(self.data) is not bytes:
            raise ValueError("data must be exact bytes")
        if sha256_hex(self.data) != self.file_sha256:
            raise ValueError("file_sha256 does not match exact emission bytes")
        artifact = deserialize_ordered_candidate_emission_artifact(self.data)
        if artifact.payload_sha256 != self.payload_sha256:
            raise ValueError("payload_sha256 does not match the emission artifact")


@dataclass(frozen=True, slots=True)
class OrderedCandidateEmissionPackage:
    """All bytes needed by the atomic writer before filesystem access."""

    manifest_bytes: bytes
    attempts: tuple[OrderedCandidateMaterializationAttempt, ...]
    emission_files: tuple[OrderedCandidateEmissionFile, ...]

    def __post_init__(self) -> None:
        if type(self.manifest_bytes) is not bytes:
            raise ValueError("manifest_bytes must be exact bytes")
        if type(self.attempts) is not tuple or any(
            type(attempt) is not OrderedCandidateMaterializationAttempt
            for attempt in self.attempts
        ):
            raise ValueError("attempts must be an immutable typed tuple")
        if type(self.emission_files) is not tuple or any(
            type(item) is not OrderedCandidateEmissionFile
            for item in self.emission_files
        ):
            raise ValueError("emission_files must be an immutable typed tuple")


def canonical_source_snapshot_bytes(
    rows: tuple[OrderedCandidateSourceRow, ...],
) -> bytes:
    """Return LCJ-1 bytes over every row in the supplied authoritative order."""

    if type(rows) is not tuple or any(
        type(row) is not OrderedCandidateSourceRow for row in rows
    ):
        raise OrderedCandidateEmissionPackageError(
            "source snapshot rows must be an immutable typed tuple"
        )
    return canonical_bytes([row.canonical_dict() for row in rows])


def source_snapshot_sha256(rows: tuple[OrderedCandidateSourceRow, ...]) -> str:
    return sha256_hex(canonical_source_snapshot_bytes(rows))


def _status_counts(
    attempts: tuple[OrderedCandidateMaterializationAttempt, ...],
) -> dict[str, int]:
    counts = Counter(attempt.status for attempt in attempts)
    return {
        status.value.lower(): counts.get(status, 0)
        for status in OrderedCandidateMaterializationStatus
    }


def build_ordered_candidate_emission_package(
    *,
    dataset_id: str,
    dataset_version: str,
    source_snapshot_sha256_value: str,
    target_draws: tuple[str, ...],
    strategy_ids: tuple[str, ...],
    minimum_history_draws: int,
    maximum_history_draws: int,
    replicate: int,
    attempts: tuple[OrderedCandidateMaterializationAttempt, ...],
    emission_files: tuple[OrderedCandidateEmissionFile, ...],
) -> OrderedCandidateEmissionPackage:
    """Build a complete deterministic manifest and verify every constituent."""

    _validate_attempt_matrix(
        target_draws=target_draws,
        strategy_ids=strategy_ids,
        attempts=attempts,
    )
    counts = Counter(attempt.status for attempt in attempts)
    draft: dict[str, Any] = {
        "attempt_count": len(attempts),
        "attempts": [_attempt_dict(attempt) for attempt in attempts],
        "dataset_id": dataset_id,
        "dataset_version": dataset_version,
        "lottery_type": LotteryType.BIG_LOTTO.value,
        "manifest_payload_sha256": "0" * 64,
        "manifest_schema_version": ORDERED_CANDIDATE_PACKAGE_MANIFEST_SCHEMA_VERSION,
        "maximum_history_draws": maximum_history_draws,
        "minimum_history_draws": minimum_history_draws,
        "ok_attempt_count": counts.get(OrderedCandidateMaterializationStatus.OK, 0),
        "replicate": replicate,
        "source_snapshot_sha256": source_snapshot_sha256_value,
        "status_counts": _status_counts(attempts),
        "strategy_ids": list(strategy_ids),
        "target_draws": list(target_draws),
    }
    draft["manifest_payload_sha256"] = self_key_removed_sha256(
        draft,
        "manifest_payload_sha256",
    )
    package = OrderedCandidateEmissionPackage(
        manifest_bytes=canonical_bytes(draft),
        attempts=attempts,
        emission_files=tuple(
            sorted(emission_files, key=lambda item: item.relative_path.encode("utf-8"))
        ),
    )
    verify_ordered_candidate_emission_package(package)
    return package


def verify_ordered_candidate_emission_package(
    package: OrderedCandidateEmissionPackage,
) -> dict[str, Any]:
    """Reparse all canonical bytes and validate ledger/artifact closure."""

    raw_manifest = loads_canonical(package.manifest_bytes)
    if not isinstance(raw_manifest, dict):
        raise OrderedCandidateEmissionPackageError("manifest must be a JSON object")
    manifest = cast(dict[str, Any], raw_manifest)
    if set(manifest) != _MANIFEST_KEYS:
        raise OrderedCandidateEmissionPackageError("manifest top-level keys are not closed")
    if canonical_bytes(manifest) != package.manifest_bytes:
        raise OrderedCandidateEmissionPackageError("manifest bytes are not canonical LCJ-1")
    if (
        manifest["manifest_schema_version"]
        != ORDERED_CANDIDATE_PACKAGE_MANIFEST_SCHEMA_VERSION
    ):
        raise OrderedCandidateEmissionPackageError("manifest schema version is unsupported")
    if (
        manifest["manifest_payload_sha256"]
        != self_key_removed_sha256(manifest, "manifest_payload_sha256")
    ):
        raise OrderedCandidateEmissionPackageError("manifest payload hash does not match")
    if manifest["lottery_type"] != LotteryType.BIG_LOTTO.value:
        raise OrderedCandidateEmissionPackageError("manifest lottery type is unsupported")
    if manifest["replicate"] != 1:
        raise OrderedCandidateEmissionPackageError("manifest replicate must be exactly 1")
    if (
        manifest["attempt_count"] != len(package.attempts)
        or manifest["ok_attempt_count"]
        != sum(
            attempt.status is OrderedCandidateMaterializationStatus.OK
            for attempt in package.attempts
        )
    ):
        raise OrderedCandidateEmissionPackageError("manifest attempt counts do not match")

    expected_attempts = [_attempt_dict(attempt) for attempt in package.attempts]
    if manifest["attempts"] != expected_attempts:
        raise OrderedCandidateEmissionPackageError("manifest attempt ledger does not match")
    raw_status_counts = manifest["status_counts"]
    expected_counts = _status_counts(package.attempts)
    if type(raw_status_counts) is not dict:
        raise OrderedCandidateEmissionPackageError("manifest status counts must be an object")
    status_counts = cast(dict[str, Any], raw_status_counts)
    status_count_values = tuple(status_counts.values())
    if (
        any(type(value) is not int or value < 0 for value in status_count_values)
        or status_counts != expected_counts
        or sum(cast(int, value) for value in status_count_values)
        != manifest["attempt_count"]
    ):
        raise OrderedCandidateEmissionPackageError("manifest status counts do not match")

    _validate_attempt_matrix(
        target_draws=tuple(cast(list[str], manifest["target_draws"])),
        strategy_ids=tuple(cast(list[str], manifest["strategy_ids"])),
        attempts=package.attempts,
    )
    sorted_files = tuple(
        sorted(package.emission_files, key=lambda item: item.relative_path.encode("utf-8"))
    )
    if sorted_files != package.emission_files:
        raise OrderedCandidateEmissionPackageError(
            "emission files must be sorted by relative-path UTF-8 bytes"
        )
    by_path = {item.relative_path: item for item in package.emission_files}
    if len(by_path) != len(package.emission_files):
        raise OrderedCandidateEmissionPackageError("emission paths must be unique")
    expected_paths = {
        attempt.emission_relative_path
        for attempt in package.attempts
        if attempt.status is OrderedCandidateMaterializationStatus.OK
    }
    if set(by_path) != expected_paths:
        raise OrderedCandidateEmissionPackageError(
            "emission files must match all and only OK attempts"
        )
    for attempt in package.attempts:
        if attempt.status is not OrderedCandidateMaterializationStatus.OK:
            continue
        assert attempt.emission_relative_path is not None
        item = by_path[attempt.emission_relative_path]
        if (
            item.file_sha256 != attempt.emission_file_sha256
            or item.payload_sha256 != attempt.emission_payload_sha256
        ):
            raise OrderedCandidateEmissionPackageError(
                "attempt hashes do not match emission bytes"
            )
        artifact = deserialize_ordered_candidate_emission_artifact(item.data)
        emission = artifact.emission
        if (
            emission.target_draw != attempt.target_draw
            or emission.strategy_id != attempt.strategy_id
            or emission.strategy_version != attempt.strategy_version
            or emission.history_cutoff != attempt.history_cutoff
            or emission.replicate != 1
        ):
            raise OrderedCandidateEmissionPackageError(
                "emission identity does not match its attempt"
            )
    return manifest


def sha256sums_bytes(package: OrderedCandidateEmissionPackage) -> bytes:
    """Return exact GNU-style SHA256SUMS bytes (excluding SHA256SUMS itself)."""

    entries = [
        (item.relative_path, item.file_sha256) for item in package.emission_files
    ]
    entries.append(("manifest.json", sha256_hex(package.manifest_bytes)))
    entries.sort(key=lambda pair: pair[0].encode("utf-8"))
    return b"".join(
        f"{digest}  {relative_path}\n".encode()
        for relative_path, digest in entries
    )


def _attempt_dict(
    attempt: OrderedCandidateMaterializationAttempt,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "ordinal": attempt.ordinal,
        "status": attempt.status.value,
        "strategy_id": attempt.strategy_id,
        "strategy_ordinal": attempt.strategy_ordinal,
        "target_draw": attempt.target_draw,
        "target_ordinal": attempt.target_ordinal,
    }
    for key in (
        "reason_code",
        "history_cutoff",
        "strategy_version",
        "emission_relative_path",
        "emission_payload_sha256",
        "emission_file_sha256",
    ):
        value = getattr(attempt, key)
        if value is not None:
            payload[key] = value
    if not payload.keys() >= _ATTEMPT_REQUIRED_KEYS or not payload.keys() <= (
        _ATTEMPT_REQUIRED_KEYS | _ATTEMPT_OPTIONAL_KEYS
    ):
        raise OrderedCandidateEmissionPackageError("attempt keys are not closed")
    return payload


def _validate_attempt_matrix(
    *,
    target_draws: tuple[str, ...],
    strategy_ids: tuple[str, ...],
    attempts: tuple[OrderedCandidateMaterializationAttempt, ...],
) -> None:
    expected = [
        (ordinal, target_ordinal, strategy_ordinal, target_draw, strategy_id)
        for ordinal, (target_ordinal, target_draw, strategy_ordinal, strategy_id) in enumerate(
            (
                (target_ordinal, target_draw, strategy_ordinal, strategy_id)
                for target_ordinal, target_draw in enumerate(target_draws)
                for strategy_ordinal, strategy_id in enumerate(strategy_ids)
            )
        )
    ]
    actual = [
        (
            attempt.ordinal,
            attempt.target_ordinal,
            attempt.strategy_ordinal,
            attempt.target_draw,
            attempt.strategy_id,
        )
        for attempt in attempts
    ]
    if actual != expected:
        raise OrderedCandidateEmissionPackageError(
            "attempt ledger is not the exact caller-ordered target x strategy matrix"
        )
    if len(set(target_draws)) != len(target_draws) or len(set(strategy_ids)) != len(
        strategy_ids
    ):
        raise OrderedCandidateEmissionPackageError(
            "target and strategy identities must not repeat"
        )
    if (
        not target_draws
        or not strategy_ids
        or len(attempts) != len(target_draws) * len(strategy_ids)
    ):
        raise OrderedCandidateEmissionPackageError("attempt matrix is incomplete")


__all__ = [
    "ORDERED_CANDIDATE_PACKAGE_MANIFEST_SCHEMA_VERSION",
    "OrderedCandidateEmissionFile",
    "OrderedCandidateEmissionPackage",
    "OrderedCandidateEmissionPackageError",
    "build_ordered_candidate_emission_package",
    "canonical_source_snapshot_bytes",
    "sha256sums_bytes",
    "source_snapshot_sha256",
    "verify_ordered_candidate_emission_package",
]
