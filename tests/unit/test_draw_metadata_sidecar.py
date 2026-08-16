"""Unit coverage for the append-only JSON-lines official-draw metadata sidecar."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from lottolab.application.draw_metadata import OfficialDrawMetadataRecord
from lottolab.domain.draws import LotteryType
from lottolab.infrastructure.persistence.draw_metadata_sidecar import (
    DrawMetadataSidecarError,
    append_metadata_jsonl,
    read_metadata_jsonl,
)


def _record(draw_number: str = "115000079") -> OfficialDrawMetadataRecord:
    return OfficialDrawMetadataRecord(
        lottery_type=LotteryType.BIG_LOTTO,
        draw_number=draw_number,
        draw_date=date(2026, 8, 14),
        draw_number_appear=(35, 25, 5, 12, 34, 33, 27),
        sell_amount=93928200,
        total_amount=130683982,
        jackpot_winner_count=0,
        jackpot_per_prize=0,
        jackpot_prize=18825389,
        jackpot_last_prize=78084190,
        source_reference="taiwanlottery:/Lottery/Lotto649Result:115000079",
        raw_json='{"period": "115000079"}',
    )


def test_round_trips_a_single_record(tmp_path: Path) -> None:
    path = tmp_path / "metadata.jsonl"
    record = _record()

    written = append_metadata_jsonl(path, [record])
    read_back = read_metadata_jsonl(path)

    assert written == 1
    assert read_back == (record,)


def test_appending_twice_accumulates_lines(tmp_path: Path) -> None:
    path = tmp_path / "metadata.jsonl"
    append_metadata_jsonl(path, [_record("1")])
    append_metadata_jsonl(path, [_record("2")])

    read_back = read_metadata_jsonl(path)

    assert [record.draw_number for record in read_back] == ["1", "2"]


def test_reading_a_missing_file_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "does-not-exist.jsonl"

    assert read_metadata_jsonl(path) == ()


def test_creates_parent_directories(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "dir" / "metadata.jsonl"

    append_metadata_jsonl(path, [_record()])

    assert path.exists()


def test_relative_path_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(DrawMetadataSidecarError):
        append_metadata_jsonl(Path("relative/metadata.jsonl"), [_record()])


def test_lotterynew_path_component_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(DrawMetadataSidecarError):
        append_metadata_jsonl(tmp_path / "LotteryNew" / "metadata.jsonl", [_record()])


def test_preserves_a_lottery_type_with_no_rollover_pool(tmp_path: Path) -> None:
    path = tmp_path / "metadata.jsonl"
    record = OfficialDrawMetadataRecord(
        lottery_type=LotteryType.DAILY_539,
        draw_number="115000198",
        draw_date=date(2026, 8, 15),
        draw_number_appear=(35, 21, 37, 14, 12),
        sell_amount=36512950,
        total_amount=10531900,
        jackpot_winner_count=0,
        jackpot_per_prize=8000000,
        jackpot_prize=None,
        jackpot_last_prize=None,
        source_reference="taiwanlottery:/Lottery/Daily539Result:115000198",
        raw_json="{}",
    )

    append_metadata_jsonl(path, [record])
    read_back = read_metadata_jsonl(path)

    assert read_back[0].jackpot_prize is None
    assert read_back[0].jackpot_last_prize is None
