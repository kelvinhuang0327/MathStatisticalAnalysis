"""Canonical serialization, content hashing, and tamper detection for Replay.

Builds on the existing LCJ-1 primitives in ``lottolab.evidence.canonical_json``
(``canonical_bytes``, ``self_key_removed_sha256``, ``loads_canonical``) rather
than reinventing canonicalization. Optional snapshot fields are omitted from
the canonical payload when absent — LCJ-1 forbids JSON ``null`` outright, so
"not present" is represented by key absence, never by a null value.

This module is evidence-layer: it may depend on domain (:mod:`lottolab.domain`)
and stdlib only. It computes no production metric and performs no I/O.
"""

from __future__ import annotations

import dataclasses
from datetime import date
from typing import Any, cast

from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_history import ReplayCausalDrawRow
from lottolab.domain.replay_predictions import (
    SNAPSHOT_SCHEMA_VERSION,
    ReplayPredictionSnapshot,
    ReplaySourceMode,
    ReplayTarget,
)
from lottolab.evidence.canonical_json import (
    canonical_bytes,
    loads_canonical,
    self_key_removed_sha256,
    sha256_hex,
)

ARTIFACT_SCHEMA_VERSION = "1.0.0"

_PLACEHOLDER_SHA256 = "0" * 64


class ReplayArtifactTamperError(ValueError):
    """A deserialized artifact's declared ``payload_sha256`` does not match its bytes."""


class ReplayArtifactShapeError(ValueError):
    """Deserialized artifact bytes do not match the expected canonical shape."""


def _dataclass_field_dict(instance: Any) -> dict[str, Any]:
    return {field.name: getattr(instance, field.name) for field in dataclasses.fields(instance)}


def causal_history_canonical_payload(
    history: tuple[ReplayCausalDrawRow, ...],
) -> list[dict[str, Any]]:
    """Ordered, LCJ-1-safe payload for causal-history provenance hashing."""

    return [
        {
            "draw_number": row.draw_number,
            "draw_date": row.draw_date.isoformat(),
            "main_numbers": list(row.main_numbers),
            "special_number": row.special_number,
        }
        for row in history
    ]


def causal_history_sha256(history: tuple[ReplayCausalDrawRow, ...]) -> str:
    """SHA-256 over the ordered causal-history provenance payload."""

    return sha256_hex(canonical_bytes(causal_history_canonical_payload(history)))


def _snapshot_content_dict(
    *,
    snapshot_schema_version: str,
    dataset_id: str,
    dataset_version: str,
    lottery_type: LotteryType,
    source_mode: ReplaySourceMode,
    target_draw_number: str,
    target_draw_date: date,
    cutoff_draw_number: str | None,
    cutoff_draw_date: date | None,
    strategy_id: str,
    strategy_version: str | None,
    adapter_strategy_id: str | None,
    adapter_strategy_name: str | None,
    adapter_strategy_version: str | None,
    history_status: str,
    history_reason_code: str | None,
    causal_history_count: int | None,
    causal_history_sha256: str | None,
    prediction_status: str | None,
    prediction_reason_code: str | None,
    predicted_main_numbers: tuple[int, ...] | None,
    result_sha256: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "snapshot_schema_version": snapshot_schema_version,
        "dataset_id": dataset_id,
        "dataset_version": dataset_version,
        "lottery_type": lottery_type.value,
        "source_mode": source_mode.value,
        "target_draw_number": target_draw_number,
        "target_draw_date": target_draw_date.isoformat(),
        "strategy_id": strategy_id,
        "history_status": history_status,
        "result_sha256": result_sha256,
    }
    if cutoff_draw_number is not None and cutoff_draw_date is not None:
        payload["cutoff_draw_number"] = cutoff_draw_number
        payload["cutoff_draw_date"] = cutoff_draw_date.isoformat()
    if strategy_version is not None:
        payload["strategy_version"] = strategy_version
        payload["adapter_strategy_id"] = adapter_strategy_id
        payload["adapter_strategy_name"] = adapter_strategy_name
        payload["adapter_strategy_version"] = adapter_strategy_version
    if history_reason_code is not None:
        payload["history_reason_code"] = history_reason_code
    if causal_history_count is not None:
        payload["causal_history_count"] = causal_history_count
        payload["causal_history_sha256"] = causal_history_sha256
    if prediction_status is not None:
        payload["prediction_status"] = prediction_status
    if prediction_reason_code is not None:
        payload["prediction_reason_code"] = prediction_reason_code
    if predicted_main_numbers is not None:
        payload["predicted_main_numbers"] = list(predicted_main_numbers)
    return payload


def recompute_snapshot_result_sha256(snapshot: ReplayPredictionSnapshot) -> str:
    """Recompute a snapshot's content hash from its current field values."""

    content = _snapshot_content_dict(**_dataclass_field_dict(snapshot))
    return self_key_removed_sha256(content, "result_sha256")


def build_replay_prediction_snapshot(
    *,
    dataset_id: str,
    dataset_version: str,
    lottery_type: LotteryType,
    target: ReplayTarget,
    strategy_id: str,
    strategy_identity: tuple[str, str, str] | None,
    history_status: str,
    history_reason_code: str | None,
    causal_history: tuple[ReplayCausalDrawRow, ...] | None,
    prediction_status: str | None,
    prediction_reason_code: str | None,
    predicted_main_numbers: tuple[int, ...] | None,
) -> ReplayPredictionSnapshot:
    """Assemble one immutable, hash-stamped :class:`ReplayPredictionSnapshot`.

    ``strategy_identity`` is the catalog descriptor's own
    ``(strategy_id, strategy_name, version)`` triple resolved for
    ``strategy_id``; ``adapter_strategy_version`` and ``strategy_version``
    both mirror ``version``, since ``GenerateOneBet`` already guarantees any
    injected adapter's identity matches its descriptor exactly. Pass ``None``
    when the catalog has no descriptor for ``strategy_id`` (identity
    mismatch): the use case must still produce one closed snapshot, never a
    crash.
    """

    adapter_id, adapter_name, adapter_version = (
        strategy_identity if strategy_identity is not None else (None, None, None)
    )
    strategy_version = adapter_version
    causal_history_count = len(causal_history) if causal_history is not None else None
    causal_history_hash = (
        causal_history_sha256(causal_history) if causal_history is not None else None
    )
    if causal_history:
        cutoff_draw_number: str | None = causal_history[-1].draw_number
        cutoff_draw_date: date | None = causal_history[-1].draw_date
    else:
        cutoff_draw_number = None
        cutoff_draw_date = None

    content = _snapshot_content_dict(
        snapshot_schema_version=SNAPSHOT_SCHEMA_VERSION,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        lottery_type=lottery_type,
        source_mode=ReplaySourceMode.TARGET_NATIVE,
        target_draw_number=target.draw_number,
        target_draw_date=target.draw_date,
        cutoff_draw_number=cutoff_draw_number,
        cutoff_draw_date=cutoff_draw_date,
        strategy_id=strategy_id,
        strategy_version=strategy_version,
        adapter_strategy_id=adapter_id,
        adapter_strategy_name=adapter_name,
        adapter_strategy_version=adapter_version,
        history_status=history_status,
        history_reason_code=history_reason_code,
        causal_history_count=causal_history_count,
        causal_history_sha256=causal_history_hash,
        prediction_status=prediction_status,
        prediction_reason_code=prediction_reason_code,
        predicted_main_numbers=predicted_main_numbers,
        result_sha256=_PLACEHOLDER_SHA256,
    )
    result_sha256 = self_key_removed_sha256(content, "result_sha256")
    return ReplayPredictionSnapshot(
        snapshot_schema_version=SNAPSHOT_SCHEMA_VERSION,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        lottery_type=lottery_type,
        source_mode=ReplaySourceMode.TARGET_NATIVE,
        target_draw_number=target.draw_number,
        target_draw_date=target.draw_date,
        cutoff_draw_number=cutoff_draw_number,
        cutoff_draw_date=cutoff_draw_date,
        strategy_id=strategy_id,
        strategy_version=strategy_version,
        adapter_strategy_id=adapter_id,
        adapter_strategy_name=adapter_name,
        adapter_strategy_version=adapter_version,
        history_status=history_status,
        history_reason_code=history_reason_code,
        causal_history_count=causal_history_count,
        causal_history_sha256=causal_history_hash,
        prediction_status=prediction_status,
        prediction_reason_code=prediction_reason_code,
        predicted_main_numbers=predicted_main_numbers,
        result_sha256=result_sha256,
    )


def _snapshot_from_canonical_dict(payload: dict[str, Any]) -> ReplayPredictionSnapshot:
    def _optional_tuple(key: str) -> tuple[int, ...] | None:
        value = payload.get(key)
        return tuple(value) if value is not None else None

    def _optional_date(key: str) -> date | None:
        value = payload.get(key)
        return date.fromisoformat(value) if value is not None else None

    return ReplayPredictionSnapshot(
        snapshot_schema_version=payload["snapshot_schema_version"],
        dataset_id=payload["dataset_id"],
        dataset_version=payload["dataset_version"],
        lottery_type=LotteryType(payload["lottery_type"]),
        source_mode=ReplaySourceMode(payload["source_mode"]),
        target_draw_number=payload["target_draw_number"],
        target_draw_date=date.fromisoformat(payload["target_draw_date"]),
        cutoff_draw_number=payload.get("cutoff_draw_number"),
        cutoff_draw_date=_optional_date("cutoff_draw_date"),
        strategy_id=payload["strategy_id"],
        strategy_version=payload.get("strategy_version"),
        adapter_strategy_id=payload.get("adapter_strategy_id"),
        adapter_strategy_name=payload.get("adapter_strategy_name"),
        adapter_strategy_version=payload.get("adapter_strategy_version"),
        history_status=payload["history_status"],
        history_reason_code=payload.get("history_reason_code"),
        causal_history_count=payload.get("causal_history_count"),
        causal_history_sha256=payload.get("causal_history_sha256"),
        prediction_status=payload.get("prediction_status"),
        prediction_reason_code=payload.get("prediction_reason_code"),
        predicted_main_numbers=_optional_tuple("predicted_main_numbers"),
        result_sha256=payload["result_sha256"],
    )


@dataclasses.dataclass(frozen=True, slots=True)
class ReplayArtifact:
    """One immutable, closed-schema canonical Replay artifact.

    ``strategy_ids`` and ``targets`` are the ordered grouping keys;
    ``snapshots`` is the flat, deterministically ordered list of every
    target x strategy pair — ``snapshot_count`` must equal both
    ``len(snapshots)`` and ``len(strategy_ids) * len(targets)``.
    """

    artifact_schema_version: str
    dataset_id: str
    dataset_version: str
    lottery_type: LotteryType
    strategy_ids: tuple[str, ...]
    targets: tuple[ReplayTarget, ...]
    snapshots: tuple[ReplayPredictionSnapshot, ...]
    snapshot_count: int
    payload_sha256: str

    def __post_init__(self) -> None:
        if type(self.lottery_type) is not LotteryType:
            raise ValueError("lottery_type must be a LotteryType")
        if not self.strategy_ids:
            raise ValueError("strategy_ids must not be empty")
        if not self.targets:
            raise ValueError("targets must not be empty")
        if len(set(self.strategy_ids)) != len(self.strategy_ids):
            raise ValueError("strategy_ids must not contain duplicates")
        if len({target.draw_number for target in self.targets}) != len(self.targets):
            raise ValueError("targets must not contain duplicate draw numbers")
        if self.snapshot_count != len(self.snapshots):
            raise ValueError("snapshot_count must equal len(snapshots)")
        if self.snapshot_count != len(self.strategy_ids) * len(self.targets):
            raise ValueError("snapshot_count must equal len(strategy_ids) * len(targets)")


def _artifact_content_dict(
    *,
    artifact_schema_version: str,
    dataset_id: str,
    dataset_version: str,
    lottery_type: LotteryType,
    strategy_ids: tuple[str, ...],
    targets: tuple[ReplayTarget, ...],
    snapshots: tuple[ReplayPredictionSnapshot, ...],
    snapshot_count: int,
    payload_sha256: str,
) -> dict[str, Any]:
    return {
        "artifact_schema_version": artifact_schema_version,
        "dataset_id": dataset_id,
        "dataset_version": dataset_version,
        "lottery_type": lottery_type.value,
        "strategy_ids": list(strategy_ids),
        "targets": [
            {"draw_number": target.draw_number, "draw_date": target.draw_date.isoformat()}
            for target in targets
        ],
        "snapshots": [
            _snapshot_content_dict(**_dataclass_field_dict(snapshot)) for snapshot in snapshots
        ],
        "snapshot_count": snapshot_count,
        "payload_sha256": payload_sha256,
    }


def build_replay_artifact(
    *,
    dataset_id: str,
    dataset_version: str,
    lottery_type: LotteryType,
    strategy_ids: tuple[str, ...],
    targets: tuple[ReplayTarget, ...],
    snapshots: tuple[ReplayPredictionSnapshot, ...],
) -> ReplayArtifact:
    """Assemble the immutable, hash-stamped canonical Replay artifact."""

    snapshot_count = len(snapshots)
    content = _artifact_content_dict(
        artifact_schema_version=ARTIFACT_SCHEMA_VERSION,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        lottery_type=lottery_type,
        strategy_ids=strategy_ids,
        targets=targets,
        snapshots=snapshots,
        snapshot_count=snapshot_count,
        payload_sha256=_PLACEHOLDER_SHA256,
    )
    payload_sha256 = self_key_removed_sha256(content, "payload_sha256")
    return ReplayArtifact(
        artifact_schema_version=ARTIFACT_SCHEMA_VERSION,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        lottery_type=lottery_type,
        strategy_ids=strategy_ids,
        targets=targets,
        snapshots=snapshots,
        snapshot_count=snapshot_count,
        payload_sha256=payload_sha256,
    )


def recompute_artifact_payload_sha256(artifact: ReplayArtifact) -> str:
    """Recompute an artifact's content hash from its current field values."""

    content = _artifact_content_dict(**_dataclass_field_dict(artifact))
    return self_key_removed_sha256(content, "payload_sha256")


def serialize_replay_artifact(artifact: ReplayArtifact) -> bytes:
    """Byte-stable canonical JSON for ``artifact``, including its own hash."""

    content = _artifact_content_dict(**_dataclass_field_dict(artifact))
    return canonical_bytes(content)


def deserialize_replay_artifact(data: bytes) -> ReplayArtifact:
    """Parse canonical bytes back into a :class:`ReplayArtifact`.

    Always re-verifies ``payload_sha256`` against the parsed content before
    returning; raises :class:`ReplayArtifactTamperError` on any mismatch, so
    a caller can never observe a tampered artifact as if it were intact.
    """

    raw_parsed = loads_canonical(data)
    if not isinstance(raw_parsed, dict):
        raise ReplayArtifactShapeError("artifact payload must be a JSON object")
    parsed = cast(dict[str, Any], raw_parsed)

    required_keys = {
        "artifact_schema_version",
        "dataset_id",
        "dataset_version",
        "lottery_type",
        "strategy_ids",
        "targets",
        "snapshots",
        "snapshot_count",
        "payload_sha256",
    }
    missing = required_keys - parsed.keys()
    if missing:
        raise ReplayArtifactShapeError(f"artifact payload is missing key(s) {sorted(missing)}")

    declared_sha256: str = parsed["payload_sha256"]
    recomputed_sha256 = self_key_removed_sha256(parsed, "payload_sha256")
    if recomputed_sha256 != declared_sha256:
        raise ReplayArtifactTamperError(
            f"payload_sha256 mismatch: declared={declared_sha256} recomputed={recomputed_sha256}"
        )

    target_entries = cast("list[dict[str, Any]]", parsed["targets"])
    targets = tuple(
        ReplayTarget(
            draw_number=entry["draw_number"],
            draw_date=date.fromisoformat(entry["draw_date"]),
        )
        for entry in target_entries
    )
    snapshot_entries = cast("list[dict[str, Any]]", parsed["snapshots"])
    snapshots = tuple(_snapshot_from_canonical_dict(entry) for entry in snapshot_entries)
    return ReplayArtifact(
        artifact_schema_version=parsed["artifact_schema_version"],
        dataset_id=parsed["dataset_id"],
        dataset_version=parsed["dataset_version"],
        lottery_type=LotteryType(parsed["lottery_type"]),
        strategy_ids=tuple(parsed["strategy_ids"]),
        targets=targets,
        snapshots=snapshots,
        snapshot_count=parsed["snapshot_count"],
        payload_sha256=declared_sha256,
    )


__all__ = [
    "ARTIFACT_SCHEMA_VERSION",
    "ReplayArtifact",
    "ReplayArtifactShapeError",
    "ReplayArtifactTamperError",
    "build_replay_artifact",
    "build_replay_prediction_snapshot",
    "causal_history_sha256",
    "deserialize_replay_artifact",
    "recompute_artifact_payload_sha256",
    "recompute_snapshot_result_sha256",
    "serialize_replay_artifact",
]
