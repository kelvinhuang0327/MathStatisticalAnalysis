"""Focused coverage for the P638 all-10 official-prize ranking projection."""

from __future__ import annotations

import random
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from lottolab.infrastructure.persistence.p638_all10_ranking_forwarder import (
    P638All10RankingBuildError,
    build_p638_all10_ranking,
)
from lottolab.infrastructure.persistence.p638_all10_ranking_repositories import (
    SQLiteP638All10RankingQueryRepository,
)
from lottolab.infrastructure.persistence.p638_all10_ranking_schema import (
    initialize_schema,
    verify_schema_read_only,
)
from lottolab.interfaces.api.app import create_app
from lottolab.strategies.adapters.powerlotto_wave1 import WAVE1_STRATEGIES

_DRAW_COUNT = 160


def _build_draw_db(path: Path, *, count: int = _DRAW_COUNT) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE migration_run (
                migration_id TEXT PRIMARY KEY,
                target_path TEXT,
                run_id TEXT,
                source_sha256 TEXT,
                status TEXT,
                total_draws INTEGER,
                migrated_draws INTEGER,
                total_numbers INTEGER,
                skipped_draws INTEGER,
                failed_draws INTEGER,
                started_at TEXT,
                completed_at TEXT
            );
            CREATE TABLE lottery_draw (
                draw_id INTEGER PRIMARY KEY,
                migration_id TEXT NOT NULL,
                lottery_type TEXT NOT NULL,
                draw_number TEXT NOT NULL,
                draw_date TEXT NOT NULL,
                source_reference TEXT NOT NULL,
                source_record_sha256 TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                completed_at TEXT
            );
            CREATE TABLE lottery_draw_number (
                number_id INTEGER PRIMARY KEY,
                draw_id INTEGER NOT NULL,
                zone INTEGER NOT NULL,
                position INTEGER NOT NULL,
                number INTEGER NOT NULL
            );
            """
        )
        connection.execute(
            "INSERT INTO migration_run (migration_id, status) VALUES (?, 'COMPLETED')",
            ("P638_OLD_DB_DRAW_MIGRATION_R1",),
        )
        rng = random.Random("p638-all10-ranking-fixture")
        for index in range(count):
            draw_number = f"{97000001 + index}"
            draw_date = f"2020-01-{(index % 28) + 1:02d}"
            connection.execute(
                """
                INSERT INTO lottery_draw (
                    draw_id, migration_id, lottery_type, draw_number, draw_date,
                    source_reference, source_record_sha256, status, created_at
                ) VALUES (
                    ?, 'P638_OLD_DB_DRAW_MIGRATION_R1', 'POWER_LOTTO', ?, ?, 'test', 'x',
                    'COMPLETE', ?
                )
                """,
                (index + 1, draw_number, draw_date, draw_date),
            )
            zone1 = sorted(rng.sample(range(1, 39), 6))
            for position, number in enumerate(zone1, start=1):
                connection.execute(
                    "INSERT INTO lottery_draw_number (draw_id, zone, position, number) "
                    "VALUES (?, 1, ?, ?)",
                    (index + 1, position, number),
                )
            connection.execute(
                "INSERT INTO lottery_draw_number (draw_id, zone, position, number) "
                "VALUES (?, 2, 1, ?)",
                (index + 1, rng.randint(1, 8)),
            )
        connection.commit()
    finally:
        connection.close()


@pytest.fixture(scope="module")
def built_projection(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str]:
    base = tmp_path_factory.mktemp("p638-all10")
    draw_db = base / "draws.sqlite3"
    _build_draw_db(draw_db)
    runtime_root = base / "runtime"
    output_db = runtime_root / "historical_results_all10_prize_ranking.sqlite3"
    result = build_p638_all10_ranking(
        draw_db=draw_db, runtime_root=runtime_root, output_db=output_db
    )
    return output_db, result.run_id


def test_all10_replay_has_zero_exclusions_and_zero_failures(
    built_projection: tuple[Path, str],
) -> None:
    output_db, run_id = built_projection
    assert verify_schema_read_only(output_db) is True
    connection = sqlite3.connect(f"file:{output_db}?mode=ro", uri=True)
    try:
        run_row = connection.execute(
            """
            SELECT strategy_count, excluded_strategy_count, eligible_target_failure_count,
                   draw_count
            FROM p638_all10_run WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        assert run_row == (10, 0, 0, _DRAW_COUNT)
        strategy_ids = {
            row[0]
            for row in connection.execute(
                "SELECT strategy_id FROM p638_all10_strategy WHERE run_id = ?", (run_id,)
            )
        }
        assert strategy_ids == {spec.strategy_id for spec in WAVE1_STRATEGIES}
        failed_targets = connection.execute(
            """
            SELECT COUNT(*) FROM p638_all10_target
            WHERE run_id = ? AND status NOT IN ('COMPLETE', 'EXCLUDED_INSUFFICIENT_HISTORY')
            """,
            (run_id,),
        ).fetchone()[0]
        assert failed_targets == 0
    finally:
        connection.close()


def test_all10_ranking_has_exactly_ten_rows_ranked_one_through_ten(
    built_projection: tuple[Path, str],
) -> None:
    output_db, run_id = built_projection
    repository = SQLiteP638All10RankingQueryRepository(output_db)
    page = repository.list_rankings(run_id)
    assert page is not None
    assert len(page.items) == 10
    assert tuple(item.rank for item in page.items) == tuple(range(1, 11))
    assert {item.strategy_id for item in page.items} == {
        spec.strategy_id for spec in WAVE1_STRATEGIES
    }
    for item in page.items:
        assert 0.0 <= item.winning_target_rate <= 1.0
        assert 0.0 <= item.ticket_winning_rate <= 1.0
        assert item.eligible_target_count >= 0
        assert item.winning_target_count <= item.eligible_target_count
        assert item.winning_ticket_count <= item.total_complete_ticket_count
        assert len(item.prize_tier_counts) == 10
        assert [tier for tier, _count in item.prize_tier_counts] == [
            "FIRST",
            "SECOND",
            "THIRD",
            "FOURTH",
            "FIFTH",
            "SIXTH",
            "SEVENTH",
            "EIGHTH",
            "NINTH",
            "GENERAL",
        ]
        assert (
            item.total_complete_ticket_count
            == item.eligible_target_count * item.native_ticket_count
        )

    # Sorted by winning_target_rate descending as the primary key.
    rates = [item.winning_target_rate for item in page.items]
    assert rates == sorted(rates, reverse=True)


def test_all10_ranking_repository_returns_none_for_unknown_run(
    built_projection: tuple[Path, str],
) -> None:
    output_db, _run_id = built_projection
    repository = SQLiteP638All10RankingQueryRepository(output_db)
    assert repository.list_rankings("unknown-run") is None


def test_all10_ranking_repository_resolves_latest_token(
    built_projection: tuple[Path, str],
) -> None:
    output_db, run_id = built_projection
    repository = SQLiteP638All10RankingQueryRepository(output_db)
    latest = repository.list_rankings("latest")
    assert latest is not None
    assert latest.run_id == run_id
    assert len(latest.items) == 10


def test_all10_build_is_idempotent(tmp_path: Path) -> None:
    draw_db = tmp_path / "draws.sqlite3"
    _build_draw_db(draw_db, count=120)
    runtime_root = tmp_path / "runtime"
    output_db = runtime_root / "historical_results_all10_prize_ranking.sqlite3"

    first = build_p638_all10_ranking(
        draw_db=draw_db, runtime_root=runtime_root, output_db=output_db
    )
    connection = sqlite3.connect(f"file:{output_db}?mode=ro", uri=True)
    ticket_count_before = connection.execute("SELECT COUNT(*) FROM p638_all10_ticket").fetchone()[0]
    second = build_p638_all10_ranking(
        draw_db=draw_db, runtime_root=runtime_root, output_db=output_db
    )
    connection = sqlite3.connect(f"file:{output_db}?mode=ro", uri=True)
    ticket_count_after = connection.execute("SELECT COUNT(*) FROM p638_all10_ticket").fetchone()[0]

    assert first.run_id == second.run_id
    assert ticket_count_before == ticket_count_after


def test_all10_build_rejects_draw_db_without_expected_migration(tmp_path: Path) -> None:
    draw_db = tmp_path / "bad.sqlite3"
    connection = sqlite3.connect(draw_db)
    connection.executescript(
        "CREATE TABLE migration_run (migration_id TEXT PRIMARY KEY);"
        "CREATE TABLE lottery_draw (draw_id INTEGER PRIMARY KEY);"
        "CREATE TABLE lottery_draw_number (number_id INTEGER PRIMARY KEY);"
    )
    connection.commit()
    connection.close()

    with pytest.raises(P638All10RankingBuildError, match="missing the expected migration"):
        build_p638_all10_ranking(
            draw_db=draw_db,
            runtime_root=tmp_path / "runtime",
            output_db=tmp_path / "runtime" / "out.sqlite3",
        )


def test_p638_all10_ranking_schema_initializes_idempotently(tmp_path: Path) -> None:
    database = tmp_path / "schema-only.sqlite3"
    assert verify_schema_read_only(database) is False
    initialize_schema(database)
    initialize_schema(database)
    assert verify_schema_read_only(database) is True


def test_rankings_api_returns_exactly_ten_rows_and_404s_for_unknown_run(
    built_projection: tuple[Path, str],
) -> None:
    output_db, run_id = built_projection
    repository = SQLiteP638All10RankingQueryRepository(output_db)
    app = create_app(p638_all10_ranking_query_repository_factory=lambda: repository)
    assert "/api/v1/p638-historical/runs/{run_id}/rankings" in app.openapi()["paths"]
    client: Any = TestClient(app)

    response = client.get(f"/api/v1/p638-historical/runs/{run_id}/rankings")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == run_id
    assert len(payload["items"]) == 10
    assert [item["rank"] for item in payload["items"]] == list(range(1, 11))
    assert "does not guarantee future winning" in payload["disclaimer"]

    missing = client.get("/api/v1/p638-historical/runs/unknown-run/rankings")
    assert missing.status_code == 404
    assert missing.json()["error_code"] == "P638_RUN_NOT_FOUND"


def test_rankings_api_reports_not_configured_without_a_repository() -> None:
    app = create_app()
    client: Any = TestClient(app)
    response = client.get("/api/v1/p638-historical/runs/any-run/rankings")
    assert response.status_code == 503
    assert response.json()["error_code"] == "P638_HISTORICAL_NOT_CONFIGURED"
