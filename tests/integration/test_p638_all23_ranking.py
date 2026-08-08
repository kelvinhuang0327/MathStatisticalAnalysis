"""Focused coverage for the P638 all-23 official-prize ranking projection."""

from __future__ import annotations

import random
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from lottolab.infrastructure.persistence.p638_all23_ranking_forwarder import (
    ALL23_STRATEGIES,
    P638All23RankingBuildError,
    build_p638_all23_ranking,
)
from lottolab.infrastructure.persistence.p638_all23_ranking_repositories import (
    SQLiteP638All23RankingQueryRepository,
)
from lottolab.infrastructure.persistence.p638_all23_ranking_schema import (
    CONTRACT_VERSION,
    CURRENT_SCHEMA_VERSION,
    MIGRATION_CHECKSUM,
    MIGRATION_NAME,
    MIGRATION_STATEMENTS,
    initialize_schema,
    verify_schema_read_only,
)
from lottolab.interfaces.api.app import create_app

_DRAW_COUNT = 160
_STRATEGY_COUNT = 23


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
        rng = random.Random("p638-all23-ranking-fixture")
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
    base = tmp_path_factory.mktemp("p638-all23")
    draw_db = base / "draws.sqlite3"
    _build_draw_db(draw_db)
    runtime_root = base / "runtime"
    output_db = runtime_root / "historical_results_all23_prize_ranking.sqlite3"
    result = build_p638_all23_ranking(
        draw_db=draw_db, runtime_root=runtime_root, output_db=output_db
    )
    return output_db, result.run_id


def test_all23_strategy_universe_is_wave1_plus_wave2() -> None:
    assert len(ALL23_STRATEGIES) == _STRATEGY_COUNT
    assert len({spec.strategy_id for spec in ALL23_STRATEGIES}) == _STRATEGY_COUNT


def test_all23_replay_has_zero_strategy_exclusions_and_zero_failed_targets(
    built_projection: tuple[Path, str],
) -> None:
    """Zero *strategy*-level exclusions and zero *target*-level failures are required.

    Per-target history exclusions and donor-native portfolio closures are
    legitimate outcomes and are NOT asserted to be zero here -- two strategies have
    ``min_history`` >= 500 and this fixture's 160-draw history causally
    excludes every one of their targets. Only ``FAILED`` targets (an
    unexplained replay error) and whole-strategy exclusions are required to
    be zero; see ``status NOT IN (...)`` below, which explicitly allows
    both explicit exclusion statuses through.
    """

    output_db, run_id = built_projection
    assert verify_schema_read_only(output_db) is True
    connection = sqlite3.connect(f"file:{output_db}?mode=ro", uri=True)
    try:
        run_row = connection.execute(
            """
            SELECT strategy_count, excluded_strategy_count, eligible_target_failure_count,
                   draw_count
            FROM p638_all23_run WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        assert run_row == (_STRATEGY_COUNT, 0, 0, _DRAW_COUNT)
        strategy_ids = {
            row[0]
            for row in connection.execute(
                "SELECT strategy_id FROM p638_all23_strategy WHERE run_id = ?", (run_id,)
            )
        }
        assert strategy_ids == {spec.strategy_id for spec in ALL23_STRATEGIES}
        failed_targets = connection.execute(
            """
            SELECT COUNT(*) FROM p638_all23_target
            WHERE run_id = ? AND status NOT IN (
                'COMPLETE',
                'EXCLUDED_INSUFFICIENT_HISTORY',
                'EXCLUDED_SOURCE_NATIVE_PORTFOLIO_CLOSURE'
            )
            """,
            (run_id,),
        ).fetchone()[0]
        assert failed_targets == 0
    finally:
        connection.close()


def test_all23_ranking_has_exactly_twentythree_rows_ranked_one_through_twentythree(
    built_projection: tuple[Path, str],
) -> None:
    output_db, run_id = built_projection
    repository = SQLiteP638All23RankingQueryRepository(output_db)
    page = repository.list_rankings(run_id)
    assert page is not None
    assert len(page.items) == _STRATEGY_COUNT
    assert tuple(item.rank for item in page.items) == tuple(range(1, _STRATEGY_COUNT + 1))
    assert {item.strategy_id for item in page.items} == {
        spec.strategy_id for spec in ALL23_STRATEGIES
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


def test_all23_ranking_repository_returns_none_for_unknown_run(
    built_projection: tuple[Path, str],
) -> None:
    output_db, _run_id = built_projection
    repository = SQLiteP638All23RankingQueryRepository(output_db)
    assert repository.list_rankings("unknown-run") is None


def test_all23_ranking_repository_resolves_latest_token(
    built_projection: tuple[Path, str],
) -> None:
    output_db, run_id = built_projection
    repository = SQLiteP638All23RankingQueryRepository(output_db)
    latest = repository.list_rankings("latest")
    assert latest is not None
    assert latest.run_id == run_id
    assert len(latest.items) == _STRATEGY_COUNT


def test_all23_build_is_idempotent(tmp_path: Path) -> None:
    draw_db = tmp_path / "draws.sqlite3"
    _build_draw_db(draw_db, count=120)
    runtime_root = tmp_path / "runtime"
    output_db = runtime_root / "historical_results_all23_prize_ranking.sqlite3"

    first = build_p638_all23_ranking(
        draw_db=draw_db, runtime_root=runtime_root, output_db=output_db
    )
    connection = sqlite3.connect(f"file:{output_db}?mode=ro", uri=True)
    ticket_count_before = connection.execute("SELECT COUNT(*) FROM p638_all23_ticket").fetchone()[0]
    second = build_p638_all23_ranking(
        draw_db=draw_db, runtime_root=runtime_root, output_db=output_db
    )
    connection = sqlite3.connect(f"file:{output_db}?mode=ro", uri=True)
    ticket_count_after = connection.execute("SELECT COUNT(*) FROM p638_all23_ticket").fetchone()[0]

    assert first.run_id == second.run_id
    assert ticket_count_before == ticket_count_after


def test_all23_build_rejects_draw_db_without_expected_migration(tmp_path: Path) -> None:
    draw_db = tmp_path / "bad.sqlite3"
    connection = sqlite3.connect(draw_db)
    connection.executescript(
        "CREATE TABLE migration_run (migration_id TEXT PRIMARY KEY);"
        "CREATE TABLE lottery_draw (draw_id INTEGER PRIMARY KEY);"
        "CREATE TABLE lottery_draw_number (number_id INTEGER PRIMARY KEY);"
    )
    connection.commit()
    connection.close()

    with pytest.raises(P638All23RankingBuildError, match="missing the expected migration"):
        build_p638_all23_ranking(
            draw_db=draw_db,
            runtime_root=tmp_path / "runtime",
            output_db=tmp_path / "runtime" / "out.sqlite3",
        )


def test_p638_all23_ranking_schema_initializes_idempotently(tmp_path: Path) -> None:
    database = tmp_path / "schema-only.sqlite3"
    assert verify_schema_read_only(database) is False
    initialize_schema(database)
    initialize_schema(database)
    assert verify_schema_read_only(database) is True


def test_p638_all23_ranking_schema_upgrades_v1_without_rewriting_v1_contract(
    tmp_path: Path,
) -> None:
    assert MIGRATION_CHECKSUM == "c63435c56aff19334d15478f3f5d60114724f1a06282935c63d3acf1b8ca0b11"
    database = tmp_path / "schema-v1.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        for statement in MIGRATION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            """
            INSERT INTO p638_all23_schema_migrations (version, name, checksum, applied_at)
            VALUES (1, ?, ?, '2026-08-08T00:00:00Z')
            """,
            (MIGRATION_NAME, MIGRATION_CHECKSUM),
        )
        connection.execute(
            """
            INSERT INTO p638_all23_run (
                run_id, contract_version, lottery_type, source_replay_db_sha256,
                source_draw_db_sha256, draw_count, first_draw_number, last_draw_number,
                strategy_count, excluded_strategy_count, eligible_target_failure_count,
                prize_rule_version, prize_rule_provenance, created_at, completed_at
            ) VALUES (
                'v1-run', ?, 'POWER_LOTTO', ?, ?, 1, '1', '1', 23, 0, 0,
                'test-v1', 'test', '2026-08-08T00:00:00Z', '2026-08-08T00:00:00Z'
            )
            """,
            (CONTRACT_VERSION, "a" * 64, "b" * 64),
        )
        connection.execute(
            """
            INSERT INTO p638_all23_strategy (
                run_id, strategy_id, strategy_version, native_ticket_count,
                min_history, source_paths_json, provenance
            ) VALUES ('v1-run', 'strategy', 'v1', 4, 50, '[]', 'test')
            """
        )
        connection.execute(
            """
            INSERT INTO p638_all23_target (
                id, run_id, strategy_id, strategy_version, target_draw_number,
                target_draw_date, cutoff_draw_number, history_length,
                expected_ticket_count, status, target_is_winner
            ) VALUES (
                'v1-target', 'v1-run', 'strategy', 'v1', '1', '2026-08-08',
                NULL, 0, 4, 'COMPLETE', 0
            )
            """
        )
        connection.execute(
            """
            INSERT INTO p638_all23_target (
                id, run_id, strategy_id, strategy_version, target_draw_number,
                target_draw_date, cutoff_draw_number, history_length,
                expected_ticket_count, status, target_is_winner
            ) VALUES (
                'v1-excluded', 'v1-run', 'strategy', 'v1', '2', '2026-08-09',
                '1', 1, 4, 'EXCLUDED_INSUFFICIENT_HISTORY', NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO p638_all23_ticket (
                id, target_id, run_id, strategy_id, target_draw_number,
                ticket_position, predicted_zone1_numbers_json, predicted_zone2_number,
                actual_zone1_numbers_json, actual_zone2_number, zone1_hit_count,
                zone2_hit, is_winner, prize_tier, prize_tier_order
            ) VALUES (
                'v1-ticket', 'v1-target', 'v1-run', 'strategy', '1', 1,
                '[1,2,3,4,5,6]', 1, '[1,2,3,4,5,6]', 2, 6, 0, 0, NULL, NULL
            )
            """
        )

    initialize_schema(database)
    assert verify_schema_read_only(database) is True
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        assert connection.execute(
            "SELECT version FROM p638_all23_schema_migrations ORDER BY version"
        ).fetchall() == [(1,), (CURRENT_SCHEMA_VERSION,)]
        assert connection.execute(
            "SELECT status FROM p638_all23_target WHERE id = 'v1-target'"
        ).fetchone() == ("COMPLETE",)
        assert connection.execute(
            "SELECT status FROM p638_all23_target WHERE id = 'v1-excluded'"
        ).fetchone() == ("EXCLUDED_INSUFFICIENT_HISTORY",)
        assert connection.execute(
            "SELECT target_id FROM p638_all23_ticket WHERE id = 'v1-ticket'"
        ).fetchone() == ("v1-target",)
        connection.execute(
            """
            INSERT INTO p638_all23_target (
                id, run_id, strategy_id, strategy_version, target_draw_number,
                target_draw_date, cutoff_draw_number, history_length,
                expected_ticket_count, status, target_is_winner
            ) VALUES (
                'v2-target', 'v1-run', 'strategy', 'v1', '3', '2026-08-10',
                '2', 2, 4, 'EXCLUDED_SOURCE_NATIVE_PORTFOLIO_CLOSURE', NULL
            )
            """
        )
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        ticket_parents = {
            str(row[2])
            for row in connection.execute(
                "PRAGMA foreign_key_list(p638_all23_ticket)"
            ).fetchall()
        }
        assert "p638_all23_target" in ticket_parents


def test_all23_rankings_api_returns_exactly_23_rows_and_404s_for_unknown_run(
    built_projection: tuple[Path, str],
) -> None:
    output_db, run_id = built_projection
    repository = SQLiteP638All23RankingQueryRepository(output_db)
    app = create_app(p638_all23_ranking_query_repository_factory=lambda: repository)
    assert "/api/v1/p638-historical/all23-runs/{run_id}/rankings" in app.openapi()["paths"]
    client: Any = TestClient(app)

    response = client.get(f"/api/v1/p638-historical/all23-runs/{run_id}/rankings")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == run_id
    assert len(payload["items"]) == _STRATEGY_COUNT
    assert [item["rank"] for item in payload["items"]] == list(range(1, _STRATEGY_COUNT + 1))
    assert "does not guarantee future winning" in payload["disclaimer"]

    missing = client.get("/api/v1/p638-historical/all23-runs/unknown-run/rankings")
    assert missing.status_code == 404
    assert missing.json()["error_code"] == "P638_ALL23_RUN_NOT_FOUND"


def test_all23_rankings_api_reports_not_configured_without_a_repository() -> None:
    app = create_app()
    client: Any = TestClient(app)
    response = client.get("/api/v1/p638-historical/all23-runs/any-run/rankings")
    assert response.status_code == 503
    assert response.json()["error_code"] == "P638_HISTORICAL_NOT_CONFIGURED"


def test_all23_rankings_api_is_distinct_from_all10_rankings_api(
    built_projection: tuple[Path, str],
) -> None:
    """The all-23 and all-10 rankings live at distinct paths with distinct run_id namespaces."""

    output_db, run_id = built_projection
    repository = SQLiteP638All23RankingQueryRepository(output_db)
    app = create_app(p638_all23_ranking_query_repository_factory=lambda: repository)
    client: Any = TestClient(app)

    all10_response = client.get(f"/api/v1/p638-historical/runs/{run_id}/rankings")
    assert all10_response.status_code == 503
    assert all10_response.json()["error_code"] == "P638_HISTORICAL_NOT_CONFIGURED"
