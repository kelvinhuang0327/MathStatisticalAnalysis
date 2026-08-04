from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from tools.migrate_powerlotto_draws_from_replay_db import MigrationStop, migrate_powerlotto_draws

from lottolab.infrastructure.persistence.powerlotto_draw_archive import (
    MIGRATION_ID,
    canonical_source_record_sha256,
    initialize_schema,
)

RUN_ID = "fixture-run"


def test_migrates_two_zones_and_reconciles(tmp_path: Path) -> None:
    source = _make_source(tmp_path / "source.sqlite3", _draw_rows(2))
    target_root = tmp_path / "target"

    result = migrate_powerlotto_draws(
        source_db=source, target_root=target_root, expected_draw_count=2
    )

    assert result.source_sha256_before == result.source_sha256_after
    assert result.complete_draw_count == 2
    assert result.zone1_number_count == 12
    assert result.zone2_number_count == 2
    with sqlite3.connect(result.target_database) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("SELECT COUNT(*) FROM migration_run").fetchone()[0] == 1
        assert connection.execute(
            "SELECT status, inserted_draw_count, zone1_number_count, zone2_number_count "
            "FROM migration_run"
        ).fetchone() == ("COMPLETED", 2, 12, 2)
        assert connection.execute(
            "SELECT COUNT(*) FROM lottery_draw WHERE status = 'COMPLETE'"
        ).fetchone()[0] == 2
        assert connection.execute(
            "SELECT COUNT(*) FROM lottery_draw_number WHERE zone = 1"
        ).fetchone()[0] == 12
        assert connection.execute(
            "SELECT COUNT(*) FROM lottery_draw_number WHERE zone = 2"
        ).fetchone()[0] == 2
        assert connection.execute(
            "SELECT number FROM lottery_draw_number WHERE draw_id = 1 AND zone = 1 "
            "ORDER BY position"
        ).fetchall() == [(1,), (2,), (3,), (4,), (5,), (6,)]


@pytest.mark.parametrize(
    ("main_numbers", "second_number", "match"),
    [
        ("[1,2,3,4,5,39]", 1, "range 1..38"),
        ("[1,2,2,4,5,6]", 1, "unique"),
        ("[1,2,3,4,5,6]", 9, "range 1..8"),
        ("[1,2,3,5,4,6]", 1, "ascending"),
    ],
)
def test_rejects_invalid_source_rows_and_retains_uncompleted_target(
    tmp_path: Path, main_numbers: str, second_number: int, match: str
) -> None:
    source = _make_source(
        tmp_path / "source.sqlite3",
        _draw_rows(1, main_numbers=main_numbers, second_number=second_number),
    )
    target_root = tmp_path / "target"

    with pytest.raises(MigrationStop, match=match):
        migrate_powerlotto_draws(source_db=source, target_root=target_root, expected_draw_count=1)

    target_database = target_root / "powerlotto_draws.sqlite3"
    assert target_database.exists()
    with sqlite3.connect(target_database) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'migration_run'"
        ).fetchone()[0] == 0


def test_rejects_missing_second_zone_value(tmp_path: Path) -> None:
    source = _make_source(tmp_path / "source.sqlite3", _draw_rows(1, second_number=None))

    with pytest.raises(MigrationStop, match="second_number"):
        migrate_powerlotto_draws(
            source_db=source, target_root=tmp_path / "target", expected_draw_count=1
        )


def test_rejects_target_identity_collision_on_rerun(tmp_path: Path) -> None:
    source = _make_source(tmp_path / "source.sqlite3", _draw_rows(1))
    target_root = tmp_path / "target"
    migrate_powerlotto_draws(source_db=source, target_root=target_root, expected_draw_count=1)
    target_database = target_root / "powerlotto_draws.sqlite3"
    before = target_database.read_bytes()

    with pytest.raises(MigrationStop, match="STOP_P638_DRAW_TARGET_IDENTITY_COLLISION"):
        migrate_powerlotto_draws(source_db=source, target_root=target_root, expected_draw_count=1)

    assert target_database.read_bytes() == before


def test_completion_trigger_rejects_incomplete_draw(tmp_path: Path) -> None:
    database = tmp_path / "archive.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        initialize_schema(connection)
        connection.execute(
            """
            INSERT INTO migration_run (
                migration_id, source_database, source_run_id, source_sha256, status,
                expected_draw_count, inserted_draw_count, zone1_number_count,
                zone2_number_count, failed_draw_count, started_at
            ) VALUES (?, 'fixture.sqlite3', ?, ?, 'IN_PROGRESS', 1, 0, 0, 0, 0, 'now')
            """,
            (MIGRATION_ID, RUN_ID, "0" * 64),
        )
        connection.execute(
            """
            INSERT INTO lottery_draw (
                migration_id, lottery_type, draw_number, draw_date, source_reference,
                source_record_sha256, status, created_at
            ) VALUES (?, 'POWER_LOTTO', '97000001', '2008-01-24', 'fixture', ?, 'STAGING', 'now')
            """,
            (MIGRATION_ID, "1" * 64),
        )
        draw_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
        connection.executemany(
            "INSERT INTO lottery_draw_number (draw_id, zone, position, number) VALUES (?, 1, ?, ?)",
            [(draw_id, position, position) for position in range(1, 6)],
        )
        connection.execute(
            "INSERT INTO lottery_draw_number (draw_id, zone, position, number) VALUES (?, 2, 1, 1)",
            (draw_id,),
        )

        with pytest.raises(sqlite3.IntegrityError, match="exactly six"):
            connection.execute(
                "UPDATE lottery_draw SET status = 'COMPLETE' WHERE draw_id = ?", (draw_id,)
            )

        connection.execute(
            "INSERT INTO lottery_draw_number (draw_id, zone, position, number) VALUES (?, 1, 6, 6)",
            (draw_id,),
        )
        connection.execute(
            "UPDATE lottery_draw SET status = 'COMPLETE' WHERE draw_id = ?", (draw_id,)
        )
        assert connection.execute(
            "SELECT status FROM lottery_draw WHERE draw_id = ?", (draw_id,)
        ).fetchone() == ("COMPLETE",)


def _make_source(path: Path, rows: list[tuple[str, str, str, int | None, str]]) -> Path:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE run_metadata (
                run_id TEXT PRIMARY KEY,
                lottery_type TEXT NOT NULL,
                source_count INTEGER NOT NULL,
                status TEXT NOT NULL
            );
            CREATE TABLE completion (
                run_id TEXT PRIMARY KEY,
                status TEXT NOT NULL
            );
            CREATE TABLE draws (
                run_id TEXT NOT NULL,
                draw_number TEXT NOT NULL,
                draw_date TEXT NOT NULL,
                main_numbers_json TEXT NOT NULL,
                second_number INTEGER,
                source_reference TEXT NOT NULL,
                PRIMARY KEY (run_id, draw_number)
            );
            """
        )
        connection.execute(
            "INSERT INTO run_metadata VALUES (?, 'POWER_LOTTO', ?, 'COMPLETE')",
            (RUN_ID, len(rows)),
        )
        connection.execute("INSERT INTO completion VALUES (?, 'COMPLETE')", (RUN_ID,))
        connection.executemany(
            "INSERT INTO draws VALUES (?, ?, ?, ?, ?, ?)",
            [(RUN_ID, *row) for row in rows],
        )
        connection.commit()
    finally:
        connection.close()
    return path


def _draw_rows(
    count: int,
    *,
    main_numbers: str = "[1,2,3,4,5,6]",
    second_number: int | None = 7,
) -> list[tuple[str, str, str, int | None, str]]:
    return [
        (
            f"970000{index:02d}",
            f"2008-01-{24 + index:02d}",
            main_numbers,
            second_number,
            "https://example.invalid/powerlotto",
        )
        for index in range(1, count + 1)
    ]


def test_canonical_hash_is_independent_of_json_spacing() -> None:
    first = canonical_source_record_sha256(
        draw_number="97000001",
        draw_date="2008-01-24",
        main_numbers=(1, 2, 3, 4, 5, 6),
        second_number=7,
        source_reference="https://example.invalid/powerlotto",
    )
    second = canonical_source_record_sha256(
        draw_number="97000001",
        draw_date="2008-01-24",
        main_numbers=json.loads("[1, 2, 3, 4, 5, 6]"),
        second_number=7,
        source_reference="https://example.invalid/powerlotto",
    )
    assert first == second
    assert MIGRATION_ID == "P638_OLD_DB_DRAW_MIGRATION_R1"
