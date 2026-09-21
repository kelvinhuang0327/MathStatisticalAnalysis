"""Validation helpers for the frozen B649 per-stream M3_PLUS authority.

This module deliberately has no database, filesystem, clock, or strategy
execution dependency.  It validates the committed authority artifact and
provides the exact M3_PLUS predicate used when the artifact was materialized.
Consumers still have to pass only a strictly prior slice to the frozen
downstream candidate.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final, cast

ARTIFACT_SCHEMA_VERSION: Final = "B649_M3_PLUS_HISTORY_AUTHORITY_V1"
ARTIFACT_PATH: Final = (
    Path(__file__).parents[3]
    / "docs/research/matrix-native-results/"
    "b649-dynamic-stream-reliability-m3-plus-history-authority-v1.json"
)
METRIC_ID: Final = "M3_PLUS"
METRIC_VERSION: Final = "v1"
TARGET_DRAW_NUMBER: Final = "115000087"
TARGET_DRAW_DATE: Final = "2026-09-11"
CAUSAL_CUTOFF_DRAW_NUMBER: Final = "115000086"
CAUSAL_CUTOFF_DRAW_DATE: Final = "2026-09-08"
TRAILING_WINDOW_DRAW_COUNT: Final = 300

EXPECTED_STREAM_IDS: Final = (
    "b649_new_horizon_minimax_disagreement_r1",
    "biglotto_deviation_2bet",
    "biglotto_social_wisdom_anti_popularity",
    "legacy_biglotto__graph_predictor__cd70713a5709",
    "legacy_biglotto__hpsb_optimizer__cf5cd7d971e8",
    "legacy_biglotto__pure_cold_predict__9e89f2b41add",
    "legacy_biglotto__test_asm__d39a233a4c75",
    "legacy_biglotto__test_ces__78d17c530ab8",
    "legacy_biglotto__test_ecp__c9d5ac6decdd",
    "legacy_biglotto__test_mwsc__ba37643d6a3b",
    "legacy_biglotto__test_tme__f3bb5106dfe3",
)

_DRAW_NUMBER = re.compile(r"[0-9]+", flags=re.ASCII)
_ROW_KEYS = frozenset({"draw_date", "draw_number", "stream_id", "success"})


class M3PlusHistoryAuthorityError(ValueError):
    """Raised when the committed authority or a target slice is invalid."""


@dataclass(frozen=True, slots=True)
class M3PlusObservation:
    """One canonical prior-draw success observation."""

    draw_number: str
    draw_date: str
    success: bool


def _validate_draw_identity(draw_number: str, draw_date: str, label: str) -> None:
    if type(draw_number) is not str or _DRAW_NUMBER.fullmatch(draw_number) is None:
        raise M3PlusHistoryAuthorityError(f"{label} draw_number must be numeric text")
    if type(draw_date) is not str:
        raise M3PlusHistoryAuthorityError(f"{label} draw_date must be ISO date text")
    try:
        parsed = date.fromisoformat(draw_date)
    except ValueError as exc:
        raise M3PlusHistoryAuthorityError(
            f"{label} draw_date must be ISO date text"
        ) from exc
    if parsed.isoformat() != draw_date:
        raise M3PlusHistoryAuthorityError(f"{label} draw_date must be ISO date text")


def _draw_key(draw_number: str, draw_date: str) -> tuple[date, int]:
    return date.fromisoformat(draw_date), int(draw_number)


def canonical_content_bytes(payload: Mapping[str, object]) -> bytes:
    """Return deterministic bytes for the artifact hash, excluding its hash field."""

    body = {key: value for key, value in payload.items() if key != "artifact_content_sha256"}
    return json.dumps(
        body,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def artifact_content_sha256(payload: Mapping[str, object]) -> str:
    """Compute the artifact's non-self-referential deterministic content hash."""

    return hashlib.sha256(canonical_content_bytes(payload)).hexdigest()


def _as_object(value: object, label: str) -> dict[str, object]:
    if type(value) is not dict:
        raise M3PlusHistoryAuthorityError(f"{label} must be an object")
    return cast(dict[str, object], value)


def _as_rows(value: object) -> list[dict[str, object]]:
    if type(value) is not list:
        raise M3PlusHistoryAuthorityError("rows must be a list")
    rows: list[dict[str, object]] = []
    for index, item in enumerate(cast(list[object], value)):
        rows.append(_as_object(item, f"rows[{index}]"))
    return rows


def validate_artifact_payload(payload: Mapping[str, object]) -> None:
    """Validate schema, identity, ordering, uniqueness, hash, and frozen cutoff."""

    if payload.get("artifact_schema_version") != ARTIFACT_SCHEMA_VERSION:
        raise M3PlusHistoryAuthorityError("unexpected artifact schema version")
    if payload.get("metric_id") != METRIC_ID or payload.get("metric_version") != METRIC_VERSION:
        raise M3PlusHistoryAuthorityError("unexpected M3_PLUS metric identity")
    if payload.get("stream_ids") != list(EXPECTED_STREAM_IDS):
        raise M3PlusHistoryAuthorityError("artifact stream identity does not match frozen order")
    expected_hash = payload.get("artifact_content_sha256")
    if type(expected_hash) is not str or expected_hash != artifact_content_sha256(payload):
        raise M3PlusHistoryAuthorityError("artifact content hash mismatch")

    rows = _as_rows(payload.get("rows"))
    seen: set[tuple[str, str]] = set()
    expected_order: list[tuple[int, int, date]] = []
    actual_order: list[tuple[int, int, date]] = []
    stream_positions = {stream_id: index for index, stream_id in enumerate(EXPECTED_STREAM_IDS)}
    for index, row in enumerate(rows):
        if frozenset(row) != _ROW_KEYS:
            raise M3PlusHistoryAuthorityError(f"rows[{index}] has unexpected fields")
        stream_id = row.get("stream_id")
        draw_number = row.get("draw_number")
        draw_date = row.get("draw_date")
        success = row.get("success")
        if type(stream_id) is not str or stream_id not in stream_positions:
            raise M3PlusHistoryAuthorityError(f"rows[{index}] has an unknown stream_id")
        if type(draw_number) is not str or type(draw_date) is not str:
            raise M3PlusHistoryAuthorityError(f"rows[{index}] has an invalid draw identity")
        _validate_draw_identity(draw_number, draw_date, f"rows[{index}]")
        if type(success) is not bool:
            raise M3PlusHistoryAuthorityError(f"rows[{index}] success must be boolean")
        identity = (stream_id, draw_number)
        if identity in seen:
            raise M3PlusHistoryAuthorityError(f"duplicate stream/draw row: {identity}")
        seen.add(identity)
        if int(draw_number) > int(CAUSAL_CUTOFF_DRAW_NUMBER):
            raise M3PlusHistoryAuthorityError(
                f"rows[{index}] is later than the frozen causal cutoff"
            )
        key = (stream_positions[stream_id], int(draw_number), date.fromisoformat(draw_date))
        actual_order.append(key)
        expected_order.append(key)

    expected_order.sort()
    if actual_order != expected_order:
        raise M3PlusHistoryAuthorityError("rows are not in deterministic stream/draw order")

    if payload.get("row_count") != len(rows):
        raise M3PlusHistoryAuthorityError("row_count does not match rows")


def load_artifact(path: Path = ARTIFACT_PATH) -> dict[str, object]:
    """Load and validate one committed authority artifact."""

    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise M3PlusHistoryAuthorityError(f"cannot load authority artifact: {path}") from exc
    payload = _as_object(loaded, "artifact")
    validate_artifact_payload(payload)
    return payload


def observations_for_stream(
    payload: Mapping[str, object],
    stream_id: str,
) -> tuple[M3PlusObservation, ...]:
    """Return ordered observations for one frozen stream without hiding future rows."""

    if stream_id not in EXPECTED_STREAM_IDS:
        raise M3PlusHistoryAuthorityError(f"unknown frozen stream: {stream_id}")
    rows = _as_rows(payload.get("rows"))
    observations = tuple(
        M3PlusObservation(
            draw_number=cast(str, row["draw_number"]),
            draw_date=cast(str, row["draw_date"]),
            success=cast(bool, row["success"]),
        )
        for row in rows
        if row.get("stream_id") == stream_id
    )
    return observations


def validate_strictly_prior(
    observations: Iterable[M3PlusObservation],
    *,
    target_draw_number: str,
    target_draw_date: str,
) -> tuple[M3PlusObservation, ...]:
    """Reject any same/future observation before a consumer can use it."""

    _validate_draw_identity(target_draw_number, target_draw_date, "target")
    target = _draw_key(target_draw_number, target_draw_date)
    ordered = tuple(observations)
    for observation in ordered:
        if type(observation) is not M3PlusObservation:
            raise M3PlusHistoryAuthorityError("observations must use M3PlusObservation")
        _validate_draw_identity(
            observation.draw_number,
            observation.draw_date,
            "observation",
        )
        if _draw_key(observation.draw_number, observation.draw_date) >= target:
            raise M3PlusHistoryAuthorityError(
                "historical observation is not strictly prior to target"
            )
    return tuple(
        sorted(ordered, key=lambda item: _draw_key(item.draw_number, item.draw_date))
    )


def m3_plus_success(
    native_tickets: Sequence[Sequence[int]],
    winning_main_numbers: Sequence[int],
) -> bool:
    """Evaluate exact M3_PLUS: any native ticket has at least three main hits."""

    winning = set(winning_main_numbers)
    if len(winning) != 6 or any(type(number) is not int for number in winning):
        raise M3PlusHistoryAuthorityError("winning main numbers must be six distinct integers")
    return any(len(set(ticket) & winning) >= 3 for ticket in native_tickets)
