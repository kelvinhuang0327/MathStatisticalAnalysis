"""Acceptance coverage for the T539 Wave 1 Strategy Analysis vertical.

Unlike P638, T539 Wave 1 has no forwarding step: most tests here build a
small synthetic disposable SQLite fixture that mirrors the sealed Wave 1
schema exactly, per this task's authorization ("Synthetic disposable SQLite
fixtures are allowed only inside tests"). One acceptance test additionally
opens the real authority database read-only when it is present locally and
proves it is byte-identical before and after.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from lottolab.application.t539_historical import T539ReplayQuery
from lottolab.infrastructure.persistence.t539_historical_repositories import (
    SQLiteT539HistoricalQueryRepository,
)
from lottolab.interfaces.api.app import create_app

RUN_ID = "T539_TEST_RUN"

_SCHEMA_DDL = (
    """
    CREATE TABLE run_metadata (
        run_id TEXT PRIMARY KEY,
        schema_version TEXT NOT NULL,
        lottery_type TEXT NOT NULL CHECK (lottery_type = 'DAILY_539'),
        source_endpoint TEXT NOT NULL,
        source_sha256 TEXT NOT NULL,
        as_of_date TEXT NOT NULL,
        adapter_source_commit TEXT NOT NULL,
        strategy_set_json TEXT NOT NULL,
        status TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE source_draws (
        draw_id TEXT PRIMARY KEY,
        lottery_type TEXT NOT NULL CHECK (lottery_type = 'DAILY_539'),
        draw_date TEXT NOT NULL UNIQUE,
        main_numbers_json TEXT NOT NULL,
        draw_order INTEGER NOT NULL UNIQUE
    )
    """,
    """
    CREATE TABLE strategy_coverage (
        run_id TEXT NOT NULL,
        strategy_id TEXT NOT NULL,
        strategy_version TEXT NOT NULL,
        lottery_type TEXT NOT NULL CHECK (lottery_type = 'DAILY_539'),
        native_ticket_count INTEGER NOT NULL,
        min_history INTEGER NOT NULL,
        first_eligible_target_draw_id TEXT,
        expected_target_draw_count INTEGER NOT NULL,
        processed_target_draw_count INTEGER NOT NULL DEFAULT 0,
        successful_target_draw_count INTEGER NOT NULL DEFAULT 0,
        failed_target_draw_count INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL,
        PRIMARY KEY (run_id, strategy_id, strategy_version)
    )
    """,
    """
    CREATE TABLE prediction_tickets (
        run_id TEXT NOT NULL,
        strategy_id TEXT NOT NULL,
        strategy_version TEXT NOT NULL,
        lottery_type TEXT NOT NULL CHECK (lottery_type = 'DAILY_539'),
        target_draw_id TEXT NOT NULL,
        target_draw_date TEXT NOT NULL,
        cutoff_draw_id TEXT NOT NULL,
        cutoff_draw_date TEXT NOT NULL,
        native_ticket_count INTEGER NOT NULL,
        ticket_position INTEGER NOT NULL,
        main_numbers_json TEXT,
        special_number INTEGER,
        hits INTEGER,
        execution_status TEXT NOT NULL,
        failure_reason TEXT,
        provenance_json TEXT NOT NULL,
        adapter_source_commit TEXT NOT NULL,
        PRIMARY KEY (run_id, strategy_id, strategy_version, target_draw_id, ticket_position)
    )
    """,
    """
    CREATE TABLE prediction_scores (
        run_id TEXT NOT NULL,
        strategy_id TEXT NOT NULL,
        strategy_version TEXT NOT NULL,
        target_draw_id TEXT NOT NULL,
        ticket_position INTEGER NOT NULL,
        actual_main_numbers_json TEXT NOT NULL,
        hit_numbers_json TEXT NOT NULL,
        hits INTEGER NOT NULL,
        score_version TEXT NOT NULL,
        PRIMARY KEY (run_id, strategy_id, strategy_version, target_draw_id, ticket_position)
    )
    """,
    """
    CREATE TABLE failure_ledger (
        run_id TEXT NOT NULL,
        strategy_id TEXT NOT NULL,
        strategy_version TEXT NOT NULL,
        target_draw_id TEXT NOT NULL,
        target_draw_date TEXT NOT NULL,
        cutoff_draw_id TEXT NOT NULL,
        failure_code TEXT NOT NULL,
        failure_message TEXT NOT NULL,
        expected_ticket_count INTEGER NOT NULL,
        provenance_json TEXT NOT NULL,
        adapter_source_commit TEXT NOT NULL,
        PRIMARY KEY (run_id, strategy_id, strategy_version, target_draw_id)
    )
    """,
    """
    CREATE TABLE target_completion (
        run_id TEXT NOT NULL,
        strategy_id TEXT NOT NULL,
        strategy_version TEXT NOT NULL,
        target_draw_id TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('SUCCESS', 'FAILED')),
        native_ticket_count INTEGER NOT NULL,
        PRIMARY KEY (run_id, strategy_id, strategy_version, target_draw_id)
    )
    """,
)


def _build_fixture_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        for statement in _SCHEMA_DDL:
            connection.execute(statement)

        connection.execute(
            "INSERT INTO run_metadata VALUES (?, ?, 'DAILY_539', ?, ?, ?, ?, ?, ?)",
            (
                RUN_ID,
                "t539-wave1-v1",
                "https://api.taiwanlottery.com/TLCAPIWeB/Lottery/Daily539Result",
                "0" * 64,
                "2020-02-04",
                "testcommit",
                "[]",
                "COMPLETE",
            ),
        )

        for draw_id, draw_date, numbers, order in (
            ("90000001", "2020-01-01", [1, 2, 3, 4, 5], 0),
            ("90000002", "2020-02-01", [1, 2, 3, 4, 5], 1),
            ("90000003", "2020-02-02", [1, 2, 3, 6, 7], 2),
        ):
            connection.execute(
                "INSERT INTO source_draws VALUES (?, 'DAILY_539', ?, ?, ?)",
                (draw_id, draw_date, json.dumps(numbers), order),
            )

        connection.execute(
            "INSERT INTO strategy_coverage VALUES (?, 'strat_a', 'v1', 'DAILY_539', 1, 30, "
            "'90000002', 4, 4, 3, 1, 'COMPLETE')",
            (RUN_ID,),
        )
        connection.execute(
            "INSERT INTO strategy_coverage VALUES (?, 'strat_b', 'v1', 'DAILY_539', 1, 30, "
            "'90000002', 2, 2, 2, 0, 'COMPLETE')",
            (RUN_ID,),
        )

        tickets = (
            # (strategy_id, target_draw_id, target_draw_date, cutoff_id, cutoff_date,
            #  predicted, actual, hits)
            ("strat_a", "90000002", "2020-02-01", "90000001", "2020-01-01",
             [1, 2, 3, 4, 5], [1, 2, 3, 4, 5], 5),
            ("strat_a", "90000003", "2020-02-02", "90000002", "2020-02-01",
             [1, 2, 3, 20, 21], [1, 2, 3, 6, 7], 3),
            ("strat_a", "90000004", "2020-02-03", "90000003", "2020-02-02",
             [30, 31, 32, 33, 34], [1, 2, 3, 4, 5], 0),
            ("strat_b", "90000002", "2020-02-01", "90000001", "2020-01-01",
             [1, 2, 3, 4, 6], [1, 2, 3, 4, 5], 4),
            ("strat_b", "90000003", "2020-02-02", "90000002", "2020-02-01",
             [1, 2, 10, 11, 12], [1, 2, 3, 6, 7], 2),
        )
        for (
            strategy_id, target_id, target_date, cutoff_id, cutoff_date, predicted, actual, hits,
        ) in tickets:
            connection.execute(
                "INSERT INTO prediction_tickets VALUES "
                "(?, ?, 'v1', 'DAILY_539', ?, ?, ?, ?, 1, 1, ?, NULL, ?, 'SUCCESS', NULL, '{}', "
                "'testcommit')",
                (
                    RUN_ID, strategy_id, target_id, target_date, cutoff_id, cutoff_date,
                    json.dumps(predicted), hits,
                ),
            )
            hit_numbers = sorted(set(predicted) & set(actual))
            connection.execute(
                "INSERT INTO prediction_scores VALUES (?, ?, 'v1', ?, 1, ?, ?, ?, 'test-v1')",
                (
                    RUN_ID, strategy_id, target_id,
                    json.dumps(actual), json.dumps(hit_numbers), hits,
                ),
            )
            connection.execute(
                "INSERT INTO target_completion VALUES (?, ?, 'v1', ?, 'SUCCESS', 1)",
                (RUN_ID, strategy_id, target_id),
            )

        connection.execute(
            "INSERT INTO failure_ledger VALUES "
            "(?, 'strat_a', 'v1', '90000005', '2020-02-04', '90000004', 'TEST_FAILURE', "
            "'synthetic failure for test coverage', 1, '{}', 'testcommit')",
            (RUN_ID,),
        )
        connection.execute(
            "INSERT INTO target_completion VALUES (?, 'strat_a', 'v1', '90000005', 'FAILED', 1)",
            (RUN_ID,),
        )
        connection.commit()
    finally:
        connection.close()


@pytest.fixture
def fixture_database(tmp_path: Path) -> Path:
    path = tmp_path / "t539_wave1_fixture.sqlite3"
    _build_fixture_database(path)
    return path


def _build_fixture_database_with_f4cold_single(path: Path) -> None:
    _build_fixture_database(path)
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "INSERT INTO strategy_coverage VALUES (?, 'daily539_f4cold', 'v0.1', 'DAILY_539', "
            "1, 100, '90000002', 2, 2, 2, 0, 'COMPLETE')",
            (RUN_ID,),
        )
        connection.commit()
    finally:
        connection.close()


@pytest.fixture
def fixture_database_with_f4cold_single(tmp_path: Path) -> Path:
    path = tmp_path / "t539_wave1_fixture_with_f4cold.sqlite3"
    _build_fixture_database_with_f4cold_single(path)
    return path


def _build_fixture_database_with_wave3_acb1(path: Path) -> None:
    _build_fixture_database_with_f4cold_single(path)
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "INSERT INTO strategy_coverage VALUES (?, 'acb_1bet', 'v0.1-p31a', 'DAILY_539', "
            "1, 100, '90000002', 2, 2, 2, 0, 'COMPLETE')",
            (RUN_ID,),
        )
        connection.commit()
    finally:
        connection.close()


@pytest.fixture
def fixture_database_with_wave3_acb1(tmp_path: Path) -> Path:
    path = tmp_path / "t539_wave1_fixture_with_wave3_acb1.sqlite3"
    _build_fixture_database_with_wave3_acb1(path)
    return path


class TestSQLiteT539HistoricalQueryRepository:
    def test_list_runs_reports_aggregate_counts(self, fixture_database: Path) -> None:
        repo = SQLiteT539HistoricalQueryRepository(fixture_database)
        page = repo.list_runs(limit=10, offset=0)
        assert page.total_count == 1
        run = page.items[0]
        assert run.run_id == RUN_ID
        assert run.strategy_count == 2
        assert run.draw_count == 3
        assert run.eligible_target_count == 6  # 4 (strat_a) + 2 (strat_b)
        assert run.ticket_count == 5
        assert run.failure_count == 1
        assert run.first_draw_id == "90000001"
        assert run.last_draw_id == "90000003"

    def test_unknown_run_returns_none_everywhere(self, fixture_database: Path) -> None:
        repo = SQLiteT539HistoricalQueryRepository(fixture_database)
        assert repo.list_strategies("nope", limit=10, offset=0) is None
        assert repo.list_replay("nope", T539ReplayQuery()) is None
        assert repo.get_metrics("nope") is None
        assert repo.list_rankings("nope") is None
        assert repo.get_coverage_ledger("nope") is None

    def test_list_strategies_hit_distribution_and_winners(self, fixture_database: Path) -> None:
        repo = SQLiteT539HistoricalQueryRepository(fixture_database)
        page = repo.list_strategies(RUN_ID, limit=10, offset=0)
        assert page is not None
        assert page.total_count == 2
        by_id = {item.strategy_id: item for item in page.items}
        assert by_id["strat_a"].ticket_count == 3
        assert by_id["strat_a"].winning_ticket_count == 2
        assert dict(by_id["strat_a"].hit_distribution) == {0: 1, 3: 1, 5: 1}
        assert by_id["strat_b"].winning_ticket_count == 2

    def test_list_replay_status_filter_exposes_failed_target(
        self, fixture_database: Path
    ) -> None:
        repo = SQLiteT539HistoricalQueryRepository(fixture_database)
        page = repo.list_replay(
            RUN_ID, T539ReplayQuery(strategy_id="strat_a", status="FAILED")
        )
        assert page is not None
        assert page.total_count == 1
        failed = page.items[0]
        assert failed.status == "FAILED"
        assert failed.tickets == ()
        assert failed.target_draw_id == "90000005"

    def test_list_replay_success_targets_carry_prize_tiers(
        self, fixture_database: Path
    ) -> None:
        repo = SQLiteT539HistoricalQueryRepository(fixture_database)
        page = repo.list_replay(
            RUN_ID, T539ReplayQuery(strategy_id="strat_a", status="SUCCESS")
        )
        assert page is not None
        assert page.total_count == 3
        by_target = {item.target_draw_id: item for item in page.items}
        assert by_target["90000002"].tickets[0].prize_tier == "FIRST"
        assert by_target["90000002"].tickets[0].prize_amount == 8_000_000
        assert by_target["90000003"].tickets[0].prize_tier == "THIRD"
        assert by_target["90000004"].tickets[0].is_winner is False

    def test_list_replay_date_range_filter(self, fixture_database: Path) -> None:
        repo = SQLiteT539HistoricalQueryRepository(fixture_database)
        page = repo.list_replay(
            RUN_ID,
            T539ReplayQuery(date_from="2020-02-02", date_to="2020-02-02"),
        )
        assert page is not None
        assert page.total_count == 2
        assert {item.target_draw_id for item in page.items} == {"90000003"}

    def test_get_target_round_trips_with_list_replay(self, fixture_database: Path) -> None:
        repo = SQLiteT539HistoricalQueryRepository(fixture_database)
        page = repo.list_replay(RUN_ID, T539ReplayQuery(strategy_id="strat_a"))
        assert page is not None
        first = page.items[0]
        fetched = repo.get_target(RUN_ID, first.target_id)
        assert fetched == first

    def test_get_target_unknown_id_and_malformed_id(self, fixture_database: Path) -> None:
        repo = SQLiteT539HistoricalQueryRepository(fixture_database)
        assert repo.get_target(RUN_ID, "strat_a:v1:99999999") is None
        assert repo.get_target(RUN_ID, "not-a-composite-id") is None

    def test_get_metrics_aggregate_and_scoped(self, fixture_database: Path) -> None:
        repo = SQLiteT539HistoricalQueryRepository(fixture_database)
        aggregate = repo.get_metrics(RUN_ID)
        assert aggregate is not None
        assert aggregate.strategy_id is None
        assert aggregate.ticket_count == 5
        assert aggregate.winning_ticket_count == 4
        assert aggregate.winning_target_count == 4

        scoped = repo.get_metrics(RUN_ID, strategy_id="strat_a")
        assert scoped is not None
        assert scoped.ticket_count == 3
        assert scoped.winning_ticket_count == 2
        assert repo.get_metrics(RUN_ID, strategy_id="does-not-exist") is None

    def test_rankings_prioritise_prize_tier_vector_over_ticket_rate(
        self, fixture_database: Path
    ) -> None:
        repo = SQLiteT539HistoricalQueryRepository(fixture_database)
        page = repo.list_rankings(RUN_ID)
        assert page is not None
        assert [item.strategy_id for item in page.items] == ["strat_a", "strat_b"]
        assert [item.rank for item in page.items] == [1, 2]
        strat_a, strat_b = page.items
        # strat_b has a strictly higher ticket_winning_rate (1.0 vs 0.667) but
        # strat_a still ranks first because it reached the FIRST tier at all.
        assert strat_b.ticket_winning_rate > strat_a.ticket_winning_rate
        assert dict(strat_a.prize_tier_counts)["FIRST"] == 1
        assert dict(strat_b.prize_tier_counts)["FIRST"] == 0
        assert strat_a.highest_prize_tier_achieved == "FIRST"
        assert strat_b.highest_prize_tier_achieved == "SECOND"

    def test_coverage_ledger_lists_executed_and_blocked_without_conflation(
        self, fixture_database: Path
    ) -> None:
        repo = SQLiteT539HistoricalQueryRepository(fixture_database)
        ledger = repo.get_coverage_ledger(RUN_ID)
        assert ledger is not None
        assert {item.strategy_id for item in ledger.executed} == {"strat_a", "strat_b"}
        assert len(ledger.blocked) == 7
        assert ledger.coverage_complete is False
        blocked_ids = {item.strategy_id for item in ledger.blocked}
        executed_ids = {item.strategy_id for item in ledger.executed}
        assert blocked_ids.isdisjoint(executed_ids)

    def test_coverage_ledger_suppresses_blocked_entry_once_executed_in_this_db(
        self, fixture_database_with_f4cold_single: Path
    ) -> None:
        repo = SQLiteT539HistoricalQueryRepository(fixture_database_with_f4cold_single)
        ledger = repo.get_coverage_ledger(RUN_ID)
        assert ledger is not None
        executed_ids = {item.strategy_id for item in ledger.executed}
        assert executed_ids == {"strat_a", "strat_b", "daily539_f4cold"}
        blocked_ids = {item.strategy_id for item in ledger.blocked}
        assert "daily539_f4cold" not in blocked_ids
        assert len(ledger.blocked) == 6
        assert ledger.coverage_complete is False
        assert blocked_ids.isdisjoint(executed_ids)

        f4cold_entry = next(
            item for item in ledger.executed if item.strategy_id == "daily539_f4cold"
        )
        assert f4cold_entry.native_ticket_count == 1
        assert f4cold_entry.min_history == 100
        assert f4cold_entry.selection_reason != ""

    def test_coverage_ledger_suppresses_acb1_blocked_entry_once_executed_in_this_db(
        self, fixture_database_with_wave3_acb1: Path
    ) -> None:
        repo = SQLiteT539HistoricalQueryRepository(fixture_database_with_wave3_acb1)
        ledger = repo.get_coverage_ledger(RUN_ID)
        assert ledger is not None
        executed_ids = {item.strategy_id for item in ledger.executed}
        assert executed_ids == {"strat_a", "strat_b", "daily539_f4cold", "acb_1bet"}
        blocked_ids = {item.strategy_id for item in ledger.blocked}
        assert "acb_1bet" not in blocked_ids
        assert "daily539_f4cold" not in blocked_ids
        assert len(ledger.blocked) == 5
        assert ledger.coverage_complete is False
        assert blocked_ids.isdisjoint(executed_ids)

        acb1_entry = next(item for item in ledger.executed if item.strategy_id == "acb_1bet")
        assert acb1_entry.strategy_version == "v0.1-p31a"
        assert acb1_entry.native_ticket_count == 1
        assert acb1_entry.min_history == 100
        assert acb1_entry.selection_reason != ""


class TestT539HistoricalApi:
    def test_reports_unconfigured_without_opening_a_database(self) -> None:
        app = create_app()
        client: Any = TestClient(app)
        response = client.get(f"/api/v1/t539-historical/runs/{RUN_ID}/coverage")
        assert response.status_code == 503
        assert response.json()["error_code"] == "T539_HISTORICAL_NOT_CONFIGURED"

    def test_happy_path_surfaces_rankings_and_coverage(self, fixture_database: Path) -> None:
        factory = lambda: SQLiteT539HistoricalQueryRepository(fixture_database)  # noqa: E731
        app = create_app(t539_historical_query_repository_factory=factory)
        client: Any = TestClient(app)

        runs = client.get("/api/v1/t539-historical/runs")
        assert runs.status_code == 200
        assert runs.json()["total_count"] == 1

        rankings = client.get(f"/api/v1/t539-historical/runs/{RUN_ID}/rankings")
        assert rankings.status_code == 200
        ranking_body = rankings.json()
        assert [item["strategy_id"] for item in ranking_body["items"]] == ["strat_a", "strat_b"]
        assert "does not" in ranking_body["disclaimer"].lower()

        coverage = client.get(f"/api/v1/t539-historical/runs/{RUN_ID}/coverage")
        assert coverage.status_code == 200
        coverage_body = coverage.json()
        assert coverage_body["coverage_complete"] is False
        assert len(coverage_body["blocked"]) == 7

        missing_run = client.get("/api/v1/t539-historical/runs/nope/rankings")
        assert missing_run.status_code == 404
        assert missing_run.json()["error_code"] == "T539_RUN_NOT_FOUND"


# ---------------------------------------------------------------------------
# Real authority DB acceptance: skipped when the sealed Wave 1 DB is absent.
# ---------------------------------------------------------------------------


def _find_workspace_root(start: Path) -> Path:
    """Locate the ``VibeCoding-WorkSpace`` ancestor regardless of worktree depth.

    Task worktrees for this repo are checked out at varying depths under
    ``VibeCoding-WorkSpace`` (a flat ``<repo>-agent`` sibling, or nested
    ``.worktrees/<repo>/<TASK_DIR>``); a fixed ``parents[N]`` index only
    matches one of those conventions. Falling back to a path that can never
    exist keeps the dependent ``.exists()`` checks below false (skip), not a
    crash, when no such ancestor is present at all.
    """

    for candidate in (start, *start.parents):
        if candidate.name == "VibeCoding-WorkSpace":
            return candidate
    return Path("/nonexistent-workspace-root-marker")


WORKSPACE = _find_workspace_root(Path(__file__).resolve())
AUTHORITY_DB = (
    WORKSPACE
    / ".runs/MathStatisticalAnalysis/T539_WAVE1_CLEAN_REPRODUCTION_AND_PUBLICATION_R2"
    / "t539_wave1.sqlite3"
)
EXPECTED_AUTHORITY_SHA256 = (
    "cddfd82e39359bbff1e781f624fca42afd26849c38dab628223e7afd857b9b81"
)


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_real_authority_database_is_read_only_and_byte_invariant() -> None:
    if not AUTHORITY_DB.exists():
        pytest.skip("the sealed T539 Wave 1 authority database is not present locally")
    before = _sha256(AUTHORITY_DB)
    assert before == EXPECTED_AUTHORITY_SHA256

    repo = SQLiteT539HistoricalQueryRepository(AUTHORITY_DB)
    run_page = repo.list_runs(limit=10, offset=0)
    assert run_page.total_count == 1
    run_id = run_page.items[0].run_id
    assert run_page.items[0].strategy_count == 8
    assert run_page.items[0].eligible_target_count == 46_710
    assert run_page.items[0].ticket_count == 105_010
    assert run_page.items[0].failure_count == 0

    ledger = repo.get_coverage_ledger(run_id)
    assert ledger is not None
    assert len(ledger.executed) == 8
    assert len(ledger.blocked) == 7

    after = _sha256(AUTHORITY_DB)
    assert after == before

    sidecars = list(AUTHORITY_DB.parent.glob(f"{AUTHORITY_DB.name}-wal")) + list(
        AUTHORITY_DB.parent.glob(f"{AUTHORITY_DB.name}-shm")
    )
    assert sidecars == []


# ---------------------------------------------------------------------------
# Wave 2 F4Cold-single acceptance: skipped when the sealed Wave 2 DB is
# absent. Nine-strategy coverage, blocked-ledger closure, and ticket-1
# parity with both F4Cold siblings are all derived from the sealed DB
# itself, never hardcoded.
# ---------------------------------------------------------------------------

WAVE2_F4COLD_SINGLE_DB = (
    WORKSPACE
    / ".runs/MathStatisticalAnalysis/T539_WAVE2_F4COLD_SINGLE_COVERAGE_CLOSURE_R1"
    / "t539_f4cold_single_wave2.sqlite3"
)


def _ticket1_rows(connection: sqlite3.Connection, strategy_id: str) -> list[tuple[object, ...]]:
    return connection.execute(
        "SELECT pt.target_draw_id, pt.main_numbers_json, ps.hits "
        "FROM prediction_tickets pt JOIN prediction_scores ps "
        "ON ps.run_id = pt.run_id AND ps.strategy_id = pt.strategy_id "
        "AND ps.strategy_version = pt.strategy_version "
        "AND ps.target_draw_id = pt.target_draw_id "
        "AND ps.ticket_position = pt.ticket_position "
        "WHERE pt.strategy_id = ? AND pt.ticket_position = 1 "
        "ORDER BY CAST(pt.target_draw_id AS INTEGER)",
        (strategy_id,),
    ).fetchall()


def test_wave2_f4cold_single_projection_nine_strategies_and_ticket_parity() -> None:
    if not WAVE2_F4COLD_SINGLE_DB.exists():
        pytest.skip("the sealed Wave 2 F4Cold-single database is not present locally")

    repo = SQLiteT539HistoricalQueryRepository(WAVE2_F4COLD_SINGLE_DB)
    run_page = repo.list_runs(limit=10, offset=0)
    assert run_page.total_count == 1
    run = run_page.items[0]
    assert run.strategy_count == 9
    assert run.failure_count == 0

    ledger = repo.get_coverage_ledger(run.run_id)
    assert ledger is not None
    assert len(ledger.executed) == 9
    assert len(ledger.blocked) == 6
    assert ledger.coverage_complete is False
    blocked_ids = {item.strategy_id for item in ledger.blocked}
    executed_ids = {item.strategy_id for item in ledger.executed}
    assert "daily539_f4cold" not in blocked_ids
    assert "daily539_f4cold" in executed_ids
    assert blocked_ids.isdisjoint(executed_ids)

    strategies = repo.list_strategies(run.run_id, limit=20, offset=0)
    assert strategies is not None
    by_id = {item.strategy_id: item for item in strategies.items}
    single, three, five = by_id["daily539_f4cold"], by_id["daily539_f4cold_3bet"], by_id[
        "daily539_f4cold_5bet"
    ]
    assert single.native_ticket_count == 1
    assert single.expected_target_draw_count == three.expected_target_draw_count
    assert single.expected_target_draw_count == five.expected_target_draw_count
    assert single.ticket_count == single.expected_target_draw_count > 0

    connection = sqlite3.connect(
        f"{WAVE2_F4COLD_SINGLE_DB.resolve().as_uri()}?mode=ro", uri=True
    )
    try:
        single_rows = _ticket1_rows(connection, "daily539_f4cold")
        assert len(single_rows) == single.expected_target_draw_count
        for sibling_id in ("daily539_f4cold_3bet", "daily539_f4cold_5bet"):
            assert single_rows == _ticket1_rows(connection, sibling_id)
    finally:
        connection.close()

    rankings = repo.list_rankings(run.run_id)
    assert rankings is not None
    assert len(rankings.items) == 9
    assert "daily539_f4cold" in {item.strategy_id for item in rankings.items}


# ---------------------------------------------------------------------------
# Wave 3 acb_1bet-alias acceptance: skipped when the sealed Wave 3 DB is
# absent. Ten-strategy coverage, blocked-ledger closure, and full ticket
# parity with acb_single_539 are all derived from the sealed DB itself.
# ---------------------------------------------------------------------------

WAVE3_ACB1_ALIAS_DB = (
    WORKSPACE
    / ".runs/MathStatisticalAnalysis/T539_WAVE3_ACB1_ALIAS_COVERAGE_CLOSURE_R1"
    / "t539_wave3_acb1_alias.sqlite3"
)


def test_wave3_acb1_alias_projection_ten_strategies_and_ticket_parity() -> None:
    if not WAVE3_ACB1_ALIAS_DB.exists():
        pytest.skip("the sealed Wave 3 acb_1bet-alias database is not present locally")

    repo = SQLiteT539HistoricalQueryRepository(WAVE3_ACB1_ALIAS_DB)
    run_page = repo.list_runs(limit=10, offset=0)
    assert run_page.total_count == 1
    run = run_page.items[0]
    assert run.strategy_count == 10
    assert run.failure_count == 0

    ledger = repo.get_coverage_ledger(run.run_id)
    assert ledger is not None
    assert len(ledger.executed) == 10
    assert len(ledger.blocked) == 5
    assert ledger.coverage_complete is False
    blocked_ids = {item.strategy_id for item in ledger.blocked}
    executed_ids = {item.strategy_id for item in ledger.executed}
    assert "acb_1bet" not in blocked_ids
    assert "acb_1bet" in executed_ids
    assert blocked_ids.isdisjoint(executed_ids)

    strategies = repo.list_strategies(run.run_id, limit=20, offset=0)
    assert strategies is not None
    by_id = {item.strategy_id: item for item in strategies.items}
    alias, single = by_id["acb_1bet"], by_id["acb_single_539"]
    assert alias.strategy_version == "v0.1-p31a"
    assert single.strategy_version == "v0.1-p36"
    assert alias.native_ticket_count == 1
    assert alias.expected_target_draw_count == single.expected_target_draw_count
    assert alias.ticket_count == alias.expected_target_draw_count > 0
    assert alias.hit_distribution == single.hit_distribution
    assert alias.winning_ticket_count == single.winning_ticket_count

    connection = sqlite3.connect(f"{WAVE3_ACB1_ALIAS_DB.resolve().as_uri()}?mode=ro", uri=True)
    try:
        alias_rows = _ticket1_rows(connection, "acb_1bet")
        single_rows = _ticket1_rows(connection, "acb_single_539")
        assert len(alias_rows) == alias.expected_target_draw_count
        assert alias_rows == single_rows
    finally:
        connection.close()

    rankings = repo.list_rankings(run.run_id)
    assert rankings is not None
    assert len(rankings.items) == 10
    assert "acb_1bet" in {item.strategy_id for item in rankings.items}
