"""Integration coverage for ZIP inventory, SQLite references, and CLI reports."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import warnings
import zipfile
from pathlib import Path

from lottolab.infrastructure.downloaded_draw_archive import (
    EXIT_FAIL_ON_CONFLICT,
    EXIT_OPERATIONAL_ERROR,
    EXIT_REFERENCE_CONFLICT,
    POWER_LOTTO,
    audit_downloaded_archives,
    exit_code,
    main,
    write_reports,
)

POWER_HEADER = [
    "遊戲名稱",
    "期別",
    "開獎日期",
    "銷售總額",
    "銷售注數",
    "總獎金",
    "獎號1",
    "獎號2",
    "獎號3",
    "獎號4",
    "獎號5",
    "獎號6",
    "第二區",
]


def _csv_row(identity: str, date_text: str, numbers: tuple[int, ...], zone2: int) -> str:
    values = ["威力彩", identity, date_text, "0", "0", "0"]
    values.extend(f"{value:02d}" for value in numbers)
    values.append(f"{zone2:02d}")
    return ",".join(values)


def _power_csv(rows: list[tuple[str, str, tuple[int, ...], int]], *, bom: bool = True) -> bytes:
    body = ",".join(POWER_HEADER) + "\n"
    body += "\n".join(_csv_row(*row) for row in rows) + "\n"
    encoded = body.encode("utf-8")
    return b"\xef\xbb\xbf" + encoded if bom else encoded


def _write_archive(root: Path, filename: str, members: dict[str, bytes]) -> Path:
    path = root / filename
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for member_name, content in members.items():
            archive.writestr(member_name, content)
    return path


def _write_references(
    root: Path,
    rows: list[tuple[str, str, tuple[int, ...], int]],
    *,
    target_date_overrides: dict[str, str] | None = None,
) -> tuple[Path, Path]:
    source = root / "source.sqlite3"
    target = root / "target.sqlite3"
    run_id = "run-1"
    with sqlite3.connect(source) as connection:
        connection.execute(
            "CREATE TABLE run_metadata (run_id TEXT PRIMARY KEY, lottery_type TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE draws (run_id TEXT, draw_number TEXT, draw_date TEXT, "
            "main_numbers_json TEXT, second_number INTEGER, source_reference TEXT)"
        )
        connection.execute("INSERT INTO run_metadata VALUES (?, ?)", (run_id, POWER_LOTTO))
        connection.executemany(
            "INSERT INTO draws VALUES (?, ?, ?, ?, ?, ?)",
            [
                (run_id, identity, date_text, json.dumps(list(numbers)), zone2, "fixture")
                for identity, date_text, numbers, zone2 in rows
            ],
        )
    with sqlite3.connect(target) as connection:
        connection.execute(
            "CREATE TABLE lottery_draw (draw_id INTEGER PRIMARY KEY, lottery_type TEXT, "
            "draw_number TEXT, draw_date TEXT, status TEXT)"
        )
        connection.execute(
            "CREATE TABLE lottery_draw_number (number_id INTEGER PRIMARY KEY, draw_id INTEGER, "
            "zone INTEGER, position INTEGER, number INTEGER)"
        )
        draw_values: list[tuple[int, str, str, str, str]] = []
        number_values: list[tuple[int, int, int, int, int]] = []
        number_id = 1
        for draw_id, (identity, date_text, numbers, zone2) in enumerate(rows, start=1):
            draw_values.append(
                (
                    draw_id,
                    POWER_LOTTO,
                    identity,
                    (target_date_overrides or {}).get(identity, date_text),
                    "COMPLETE",
                )
            )
            for position, number in enumerate(numbers, start=1):
                number_values.append((number_id, draw_id, 1, position, number))
                number_id += 1
            number_values.append((number_id, draw_id, 2, 1, zone2))
            number_id += 1
        connection.executemany("INSERT INTO lottery_draw VALUES (?, ?, ?, ?, ?)", draw_values)
        connection.executemany(
            "INSERT INTO lottery_draw_number VALUES (?, ?, ?, ?, ?)", number_values
        )
    return source, target


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_zip_inventory_streaming_safety_partial_coverage_and_reports(tmp_path: Path) -> None:
    rows = [
        ("1", "2026-01-01", (1, 2, 3, 4, 5, 6), 1),
        ("2", "2026-01-02", (2, 3, 4, 5, 6, 7), 2),
        ("3", "2026-01-03", (3, 4, 5, 6, 7, 8), 3),
    ]
    source, target = _write_references(tmp_path, rows)
    download_root = tmp_path / "downloads"
    download_root.mkdir()
    _write_archive(
        download_root,
        "arbitrary-name.zip",
        {
            "nested/draws.csv": _power_csv([rows[0], rows[2]]),
            "notes.txt": b"not a CSV",
            "../unsafe.csv": _power_csv([rows[1]]),
        },
    )
    source_hash = _hash(source)
    target_hash = _hash(target)

    summary = audit_downloaded_archives(download_root, source, target)
    output_dir = tmp_path / "output"
    write_reports(summary, output_dir)

    assert summary.root_archive_count == 1
    assert summary.csv_member_count == 2
    assert summary.classification_member_counts[POWER_LOTTO] == 1
    assert summary.coverage_status == "PARTIAL_CORROBORATION_ONLY"
    assert summary.missing_reference_draw_ranges == ("2",)
    assert summary.unsafe_member_count == 1
    assert summary.reference.source_query_only is True
    assert summary.reference.target_query_only is True
    assert _hash(source) == source_hash
    assert _hash(target) == target_hash
    assert not list(download_root.rglob("*.csv"))
    assert (output_dir / "audit_summary.json").is_file()
    assert (output_dir / "audit_report.md").is_file()
    assert (output_dir / "mismatches.json").is_file()
    assert (output_dir / "member_inventory.json").is_file()


def test_reference_semantic_conflict_is_reported_and_nonzero(tmp_path: Path) -> None:
    rows = [("1", "2026-01-01", (1, 2, 3, 4, 5, 6), 1)]
    source, target = _write_references(
        tmp_path,
        rows,
        target_date_overrides={"1": "2026-01-02"},
    )
    download_root = tmp_path / "downloads"
    download_root.mkdir()
    _write_archive(download_root, "draws.zip", {"draws.csv": _power_csv(rows)})

    summary = audit_downloaded_archives(download_root, source, target)

    assert summary.reference.semantically_identical is False
    assert summary.reference.semantic_conflicts[0].code == "REFERENCE_DATE_MISMATCH"
    assert exit_code(summary) == EXIT_REFERENCE_CONFLICT


def test_candidate_conflicts_extra_rows_malformed_rows_and_stable_fail_flag(tmp_path: Path) -> None:
    rows = [
        ("1", "2026-01-01", (1, 2, 3, 4, 5, 6), 1),
        ("2", "2026-01-02", (2, 3, 4, 5, 6, 7), 2),
    ]
    source, target = _write_references(tmp_path, rows)
    download_root = tmp_path / "downloads"
    download_root.mkdir()
    conflicting = _power_csv(
        [
                (*rows[0][:2], rows[0][2], 8),
            ("9", "2026-01-09", (9, 10, 11, 12, 13, 14), 4),
        ]
    ).decode("utf-8-sig")
    conflicting += _csv_row("bad", "2026/01/10", (1, 2, 3, 4, 5, 99), 1) + "\n"
    _write_archive(download_root, "draws.zip", {"draws.csv": conflicting.encode("utf-8")})

    summary = audit_downloaded_archives(download_root, source, target)
    codes = {item.code for item in summary.candidate.mismatches}

    assert "ZONE2_MISMATCH" in codes
    assert "MISSING_FROM_CANDIDATE" in codes
    assert "EXTRA_IN_CANDIDATE" in codes
    assert "MALFORMED_ROW" in codes
    assert exit_code(summary) == 4


def test_corrupt_zip_duplicate_member_and_cli_exit_codes_are_stable(tmp_path: Path) -> None:
    rows = [("1", "2026-01-01", (1, 2, 3, 4, 5, 6), 1)]
    source, target = _write_references(tmp_path, rows)
    download_root = tmp_path / "downloads"
    download_root.mkdir()
    _write_archive(download_root, "good.zip", {"draws.csv": _power_csv(rows)})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(download_root / "duplicate.zip", "w") as archive:
            archive.writestr("draws.csv", _power_csv(rows))
            archive.writestr("draws.csv", _power_csv(rows))
    (download_root / "corrupt.zip").write_bytes(b"not a zip")

    output_one = tmp_path / "out-one"
    output_two = tmp_path / "out-two"
    args = [
        "--download-root",
        str(download_root),
        "--source-db",
        str(source),
        "--target-db",
        str(target),
        "--output-dir",
        str(output_one),
    ]
    first_exit = main(args)
    args[-1] = str(output_two)
    second_exit = main(args)

    assert first_exit == EXIT_OPERATIONAL_ERROR
    assert second_exit == EXIT_OPERATIONAL_ERROR
    assert (output_one / "audit_summary.json").read_bytes() == (
        output_two / "audit_summary.json"
    ).read_bytes()
    summary = audit_downloaded_archives(download_root, source, target)
    assert summary.duplicate_member_name_count == 1
    assert summary.corrupt_archive_count == 1


def test_partial_coverage_can_be_promoted_to_nonzero_with_fail_on_conflict(tmp_path: Path) -> None:
    rows = [
        ("1", "2026-01-01", (1, 2, 3, 4, 5, 6), 1),
        ("2", "2026-01-02", (2, 3, 4, 5, 6, 7), 2),
    ]
    source, target = _write_references(tmp_path, rows)
    download_root = tmp_path / "downloads"
    download_root.mkdir()
    _write_archive(download_root, "draws.zip", {"draws.csv": _power_csv([rows[0]])})
    output = tmp_path / "output"
    result = main(
        [
            "--download-root",
            str(download_root),
            "--source-db",
            str(source),
            "--target-db",
            str(target),
            "--output-dir",
            str(output),
            "--fail-on-conflict",
        ]
    )
    assert result == EXIT_FAIL_ON_CONFLICT
