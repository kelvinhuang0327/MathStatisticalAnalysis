from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from lottolab.research.b649_eh02_dataset import (
    DEFAULT_P638_ZONE1_SQLITE_PATH,
    DEFAULT_T539_SQLITE_PATH,
    DatasetAuthorityError,
    load_p638_zone1_history,
    load_t539_history,
)

t539_present = pytest.mark.skipif(
    not DEFAULT_T539_SQLITE_PATH.is_file(),
    reason=(
        "T539_WAVE1_CLEAN_REPRODUCTION_AND_PUBLICATION_R2 authority is not present "
        "on this machine"
    ),
)
p638_present = pytest.mark.skipif(
    not DEFAULT_P638_ZONE1_SQLITE_PATH.is_file(),
    reason=(
        "P638_WAVE1_CLEAN_REPRODUCTION_AND_PUBLICATION_R2 authority is not present "
        "on this machine"
    ),
)


@t539_present
def test_t539_history_matches_the_resolution_pinned_identity() -> None:
    # Pinned by B649_TRACK_B_EH02_DATA_AUTHORITY_AND_PARAMETER_LOCK_RESOLUTION_R1.md
    # Sec. 2 -- an independent reload here reproducing the same row_count,
    # date_range, and logical_sha256 is a second independent hit, not a
    # coincidence.
    history = load_t539_history()
    assert history.row_count == 5930
    assert history.draw_dates[0] == "2007-01-01"
    assert history.draw_dates[-1] == "2026-08-01"
    assert history.logical_sha256 == (
        "794ef4e5ed3268c750f484836b0c31591ce56f287dca4b882b5925a6fddcaa42"
    )


@t539_present
def test_t539_history_is_strictly_ascending_with_no_duplicates() -> None:
    history = load_t539_history()
    assert list(history.draw_dates) == sorted(history.draw_dates)
    assert len(set(history.draw_dates)) == len(history.draw_dates)
    assert len(set(history.draw_ids)) == len(history.draw_ids)


@t539_present
def test_t539_main_number_sums_are_in_the_valid_range() -> None:
    # 5 distinct numbers from 1..39: min sum 1+2+3+4+5=15, max 35+..+39=185.
    history = load_t539_history()
    assert min(history.main_number_sums) >= 15
    assert max(history.main_number_sums) <= 185


@p638_present
def test_p638_zone1_history_matches_the_resolution_pinned_identity() -> None:
    history = load_p638_zone1_history()
    assert history.row_count == 1933
    assert history.draw_dates[0] == "2008-01-24"
    assert history.draw_dates[-1] == "2026-07-30"
    assert history.logical_sha256 == (
        "49c1911154a0f95256ab12b25f5301dfb4480e4302dc0d3b6f422d247ee46df0"
    )


@p638_present
def test_p638_zone1_history_is_strictly_ascending_with_no_duplicates() -> None:
    history = load_p638_zone1_history()
    assert list(history.draw_dates) == sorted(history.draw_dates)
    assert len(set(history.draw_dates)) == len(history.draw_dates)
    assert len(set(history.draw_ids)) == len(history.draw_ids)


@p638_present
def test_p638_zone1_main_number_sums_are_in_the_valid_range() -> None:
    # 6 distinct numbers from 1..38: min sum 1+..+6=21, max 33+..+38=213.
    history = load_p638_zone1_history()
    assert min(history.main_number_sums) >= 21
    assert max(history.main_number_sums) <= 213


def test_missing_t539_file_raises_dataset_authority_error(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.sqlite3"
    with pytest.raises(DatasetAuthorityError, match="STOP_DATASET_AUTHORITY_UNPINNED"):
        load_t539_history(missing)


def test_missing_p638_file_raises_dataset_authority_error(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.sqlite3"
    with pytest.raises(DatasetAuthorityError, match="STOP_DATASET_AUTHORITY_UNPINNED"):
        load_p638_zone1_history(missing)


def _make_t539_db(path: Path, rows: list[tuple[str, str, str, int]]) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "CREATE TABLE source_draws (draw_id TEXT, lottery_type TEXT, "
            "draw_date TEXT, main_numbers_json TEXT, draw_order INTEGER)"
        )
        connection.executemany(
            "INSERT INTO source_draws VALUES (?, 'DAILY_539', ?, ?, ?)",
            [
                (draw_id, draw_date, main_numbers_json, order)
                for draw_id, draw_date, main_numbers_json, order in rows
            ],
        )
        connection.commit()
    finally:
        connection.close()


def test_t539_loader_rejects_duplicate_draw_id(tmp_path: Path) -> None:
    path = tmp_path / "synthetic_t539.sqlite3"
    _make_t539_db(
        path,
        [
            ("1", "2020-01-01", json.dumps([1, 2, 3, 4, 5]), 1),
            ("1", "2020-01-02", json.dumps([6, 7, 8, 9, 10]), 2),
        ],
    )
    with pytest.raises(DatasetAuthorityError, match="STOP_CHRONOLOGY_INVALID"):
        load_t539_history(path)


def test_t539_loader_rejects_wrong_main_number_count(tmp_path: Path) -> None:
    path = tmp_path / "synthetic_t539.sqlite3"
    _make_t539_db(path, [("1", "2020-01-01", json.dumps([1, 2, 3, 4]), 1)])  # only 4, not 5
    with pytest.raises(DatasetAuthorityError, match="STOP_CHRONOLOGY_INVALID"):
        load_t539_history(path)


def test_t539_loader_rejects_out_of_range_main_number(tmp_path: Path) -> None:
    path = tmp_path / "synthetic_t539.sqlite3"
    _make_t539_db(path, [("1", "2020-01-01", json.dumps([1, 2, 3, 4, 40]), 1)])  # 40 > 39
    with pytest.raises(DatasetAuthorityError, match="STOP_CHRONOLOGY_INVALID"):
        load_t539_history(path)


def test_t539_loader_accepts_a_clean_synthetic_row(tmp_path: Path) -> None:
    path = tmp_path / "synthetic_t539.sqlite3"
    _make_t539_db(
        path,
        [
            ("1", "2020-01-01", json.dumps([1, 2, 3, 4, 5]), 1),
            ("2", "2020-01-02", json.dumps([6, 7, 8, 9, 10]), 2),
        ],
    )
    history = load_t539_history(path)
    assert history.row_count == 2
    assert history.main_number_sums == (15, 40)
    assert len(history.logical_sha256) == 64
