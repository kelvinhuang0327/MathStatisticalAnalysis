"""Append-only JSON-lines sidecar for official-draw research metadata.

Deliberately outside the canonical draw database and the canonical research
store (``lottolab.infrastructure.persistence.research_schema``): this is a
small, additive file format for
:class:`lottolab.application.draw_metadata.OfficialDrawMetadataRecord` rows
only, meant to be read directly by future B-track research code without a
database dependency. It never mutates or is read by canonical draw ingestion.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import cast

from lottolab.application.draw_metadata import OfficialDrawMetadataRecord
from lottolab.domain.draws import LotteryType


class DrawMetadataSidecarError(RuntimeError):
    """The sidecar path or an existing line failed a safety/shape check."""


def append_metadata_jsonl(path: Path, records: Iterable[OfficialDrawMetadataRecord]) -> int:
    """Append ``records`` to ``path`` as one JSON object per line.

    ``path`` must be an absolute path outside a Git worktree so a research
    sidecar file is never accidentally committed as source. Creates the file
    (and its parent directory) if absent. Returns the number of lines
    appended.
    """

    _validate_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(_encode(record))
            handle.write("\n")
            written += 1
    return written


def read_metadata_jsonl(path: Path) -> tuple[OfficialDrawMetadataRecord, ...]:
    """Read every record previously written by :func:`append_metadata_jsonl`."""

    _validate_path(path)
    if not path.exists():
        return ()
    records: list[OfficialDrawMetadataRecord] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise DrawMetadataSidecarError(
                    f"{path}:{line_number} is not valid JSON"
                ) from exc
            records.append(_decode(payload, source=f"{path}:{line_number}"))
    return tuple(records)


def _validate_path(path: Path) -> None:
    if "\x00" in str(path):
        raise DrawMetadataSidecarError("sidecar path is invalid")
    if not path.is_absolute():
        raise DrawMetadataSidecarError("sidecar path must be absolute")
    if ".." in path.parts:
        raise DrawMetadataSidecarError("sidecar path traversal is not allowed")
    if any(part.casefold() == "lotterynew" for part in path.parts):
        raise DrawMetadataSidecarError("LotteryNew paths are forbidden")
    if path.exists() and path.is_symlink():
        raise DrawMetadataSidecarError("sidecar path must not be a symlink")


def _encode(record: OfficialDrawMetadataRecord) -> str:
    payload: dict[str, object] = {
        "lottery_type": record.lottery_type.value,
        "draw_number": record.draw_number,
        "draw_date": record.draw_date.isoformat(),
        "draw_number_appear": list(record.draw_number_appear),
        "sell_amount": record.sell_amount,
        "total_amount": record.total_amount,
        "jackpot_winner_count": record.jackpot_winner_count,
        "jackpot_per_prize": record.jackpot_per_prize,
        "jackpot_prize": record.jackpot_prize,
        "jackpot_last_prize": record.jackpot_last_prize,
        "source_reference": record.source_reference,
        "raw_json": record.raw_json,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _decode(payload: object, *, source: str) -> OfficialDrawMetadataRecord:
    if not isinstance(payload, dict):
        raise DrawMetadataSidecarError(f"{source} is not a JSON object")
    mapping = cast(dict[str, object], payload)
    try:
        return OfficialDrawMetadataRecord(
            lottery_type=LotteryType(_expect_str(mapping, "lottery_type")),
            draw_number=_expect_str(mapping, "draw_number"),
            draw_date=date.fromisoformat(_expect_str(mapping, "draw_date")),
            draw_number_appear=tuple(_expect_int_list(mapping, "draw_number_appear")),
            sell_amount=_expect_optional_int(mapping, "sell_amount"),
            total_amount=_expect_optional_int(mapping, "total_amount"),
            jackpot_winner_count=_expect_optional_int(mapping, "jackpot_winner_count"),
            jackpot_per_prize=_expect_optional_int(mapping, "jackpot_per_prize"),
            jackpot_prize=_expect_optional_int(mapping, "jackpot_prize"),
            jackpot_last_prize=_expect_optional_int(mapping, "jackpot_last_prize"),
            source_reference=_expect_str(mapping, "source_reference"),
            raw_json=_expect_str(mapping, "raw_json"),
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise DrawMetadataSidecarError(f"{source} has an invalid record shape") from exc


def _expect_str(mapping: dict[str, object], key: str) -> str:
    value = mapping[key]
    if not isinstance(value, str):
        raise TypeError(f"{key} must be a string")
    return value


def _expect_optional_int(mapping: dict[str, object], key: str) -> int | None:
    value = mapping[key]
    if value is None:
        return None
    if not isinstance(value, int):
        raise TypeError(f"{key} must be an int or null")
    return value


def _expect_int_list(mapping: dict[str, object], key: str) -> list[int]:
    value = mapping[key]
    if not isinstance(value, list):
        raise TypeError(f"{key} must be a list")
    items = cast(list[object], value)
    if any(not isinstance(item, int) for item in items):
        raise TypeError(f"{key} must contain only integers")
    return cast(list[int], items)


__all__ = [
    "DrawMetadataSidecarError",
    "append_metadata_jsonl",
    "read_metadata_jsonl",
]
