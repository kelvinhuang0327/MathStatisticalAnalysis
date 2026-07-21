"""Integration tests for the BLHQ R2 read-only historical-results query repository.

Every database in this file lives under pytest's own ``tmp_path`` and is
discarded automatically at test teardown; nothing here ever opens a
canonical or default production database.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from tests.fixtures.historical.builder import (
    CUTOFF_DRAW_NUMBER,
    CUTOFF_MAIN_NUMBERS,
    CUTOFF_SPECIAL_NUMBERS,
    REAL_STRATEGY_IDS,
    TARGET_DRAW_NUMBER,
    TARGET_MAIN_NUMBERS,
    TARGET_SPECIAL_NUMBERS,
    build_baseline_envelope,
    build_draw_snapshot,
    build_envelope,
    build_portfolio,
    build_strategy_descriptor,
    build_ticket,
    envelope_bytes,
)

from lottolab.application.historical_queries import (
    HistoricalReplayQuery,
    HistoricalResultsUnavailableError,
    HistoricalRunQuery,
)
from lottolab.domain.historical_results import HistoricalRunImport, HistoricalRunStatus
from lottolab.infrastructure.persistence.historical_repositories import (
    SQLiteHistoricalResultQueryRepository,
    SQLiteHistoricalResultRepository,
)
from lottolab.infrastructure.persistence.historical_schema import initialize_schema, open_database
from lottolab.normalization.historical_import import verify_and_normalize_historical_import


def _normalized_import(envelope: dict[str, Any]) -> HistoricalRunImport:
    result = verify_and_normalize_historical_import(envelope_bytes(envelope))
    assert result.normalized_import is not None
    return result.normalized_import


def _commit(database: Path, envelope: dict[str, Any], *, clock: Any = None) -> str:
    kwargs = {} if clock is None else {"clock": clock}
    write_repository = SQLiteHistoricalResultRepository(database, **kwargs)
    result = write_repository.commit_import(_normalized_import(envelope))
    assert result.status is HistoricalRunStatus.COMPLETED
    return result.run_id


def _insert_raw_run(database: Path, *, run_id: str, status: str, completed_at: str | None) -> None:
    """Directly insert a run row bypassing the write-side repository.

    The public commit path never durably persists a non-terminal run (it
    only ever leaves COMPLETED or FAILED rows), so exercising the
    completed-only visibility filter for IN_PROGRESS requires inserting one
    by hand.
    """

    initialize_schema(database)
    with open_database(database) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO historical_result_run (
                id, import_identity_sha256, manifest_sha256, contract_version, source_kind,
                source_repository, source_commit_oid, source_artifact_sha256, dataset_identity,
                dataset_sha256, legacy_run_id, lottery_type, status, started_at, completed_at,
                error_code, error_summary, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 'BIG_LOTTO', ?, ?, ?, NULL, NULL, ?)
            """,
            (
                run_id,
                "a" * 64,
                "b" * 64,
                "1.0.0",
                "SYNTHETIC_TEST_ONLY",
                "github.com/example/example",
                "c" * 40,
                "d" * 64,
                f"raw_dataset_{run_id}",
                "e" * 64,
                status,
                "2026-01-01T00:00:00.000000Z",
                completed_at,
                "2026-01-01T00:00:00.000000Z",
            ),
        )
        connection.commit()


def test_list_runs_returns_only_completed_runs(tmp_path: Path) -> None:
    database = tmp_path / "historical.db"
    completed_run_id = _commit(database, build_baseline_envelope())
    _insert_raw_run(
        database, run_id="failed-run", status="FAILED", completed_at="2026-01-01T00:00:00.000000Z"
    )
    _insert_raw_run(database, run_id="in-progress-run", status="IN_PROGRESS", completed_at=None)

    repository = SQLiteHistoricalResultQueryRepository(database)
    page = repository.list_runs(HistoricalRunQuery(limit=50, offset=0))

    assert page.total_count == 1
    assert [item.run_id for item in page.items] == [completed_run_id]


def test_get_run_specific_endpoints_treat_failed_and_in_progress_as_not_found(
    tmp_path: Path,
) -> None:
    database = tmp_path / "historical.db"
    _insert_raw_run(
        database, run_id="failed-run", status="FAILED", completed_at="2026-01-01T00:00:00.000000Z"
    )
    _insert_raw_run(database, run_id="in-progress-run", status="IN_PROGRESS", completed_at=None)

    repository = SQLiteHistoricalResultQueryRepository(database)

    assert repository.list_strategies("failed-run", ticket_count=10) is None
    assert repository.list_strategies("in-progress-run", ticket_count=10) is None
    assert (
        repository.list_replay_portfolios(
            "failed-run",
            HistoricalReplayQuery(strategy_id=REAL_STRATEGY_IDS[0], ticket_count=10),
        )
        is None
    )


def test_list_strategies_summary_matches_committed_count_summary_for_each_tier(
    tmp_path: Path,
) -> None:
    database = tmp_path / "historical.db"
    run_id = _commit(database, build_baseline_envelope())
    repository = SQLiteHistoricalResultQueryRepository(database)

    for tier in (10, 15, 20):
        summaries = repository.list_strategies(run_id, ticket_count=tier)
        assert summaries is not None
        assert summaries.ticket_count == tier
        assert len(summaries.items) == 5
        ordering_key = [(s.strategy_id, s.strategy_version, s.replicate) for s in summaries.items]
        assert ordering_key == sorted(ordering_key)
        for summary in summaries.items:
            assert summary.evaluated_draws == 1
            assert summary.complete_portfolios == 1
            # The default fixture's ticket #1 exactly matches the target draw's
            # main numbers (hits=6), so every tier's prefix already includes it.
            assert summary.m4plus_hit_count == 1


def test_replay_portfolio_tickets_are_strict_prefixes_across_tiers(tmp_path: Path) -> None:
    database = tmp_path / "historical.db"
    run_id = _commit(database, build_baseline_envelope())
    repository = SQLiteHistoricalResultQueryRepository(database)

    page10 = repository.list_replay_portfolios(
        run_id, HistoricalReplayQuery(strategy_id=REAL_STRATEGY_IDS[0], ticket_count=10)
    )
    page15 = repository.list_replay_portfolios(
        run_id, HistoricalReplayQuery(strategy_id=REAL_STRATEGY_IDS[0], ticket_count=15)
    )
    page20 = repository.list_replay_portfolios(
        run_id, HistoricalReplayQuery(strategy_id=REAL_STRATEGY_IDS[0], ticket_count=20)
    )
    assert page10 is not None and page15 is not None and page20 is not None
    for tier, page in ((10, page10), (15, page15), (20, page20)):
        assert page.total_count == 1
        (portfolio,) = page.items
        assert [t.portfolio_position for t in portfolio.tickets] == list(range(1, tier + 1))

    ticket10 = [t.ticket_sha256 for t in page10.items[0].tickets]
    ticket15 = [t.ticket_sha256 for t in page15.items[0].tickets]
    ticket20 = [t.ticket_sha256 for t in page20.items[0].tickets]
    assert ticket15[:10] == ticket10
    assert ticket20[:15] == ticket15


def _build_m4plus_boundary_envelope() -> dict[str, Any]:
    """One portfolio whose only main_hit_count>=4 ticket sits at position 14.

    Positions 1-10 (and 15-20 except 14) score 0-3 hits against a
    deliberately offset target_main; only position 14 hits all six numbers.
    Position 1 also carries a special-number hit with zero main hits, to
    prove special-only hits never count toward M4+.
    """

    boundary_target_main = (40, 41, 42, 43, 44, 45)
    tickets = [
        build_ticket(
            position, target_main=boundary_target_main, target_special=TARGET_SPECIAL_NUMBERS
        )
        for position in range(1, 21)
    ]
    assert tickets[0]["main_hit_count"] == 0
    assert tickets[0]["special_hit"] is True
    assert tickets[13]["main_hit_count"] == 6
    assert all(t["main_hit_count"] < 4 for t in tickets if t["portfolio_position"] != 14)

    # The actual target draw's main numbers must equal boundary_target_main:
    # normalization independently recomputes each ticket's declared hit
    # counts against the real target draw snapshot and rejects a mismatch.
    draw_snapshots = [
        build_draw_snapshot(
            draw_number=CUTOFF_DRAW_NUMBER,
            draw_date="2026-01-01",
            main_numbers=CUTOFF_MAIN_NUMBERS,
            special_numbers=CUTOFF_SPECIAL_NUMBERS,
        ),
        build_draw_snapshot(
            draw_number=TARGET_DRAW_NUMBER,
            draw_date="2026-01-10",
            main_numbers=boundary_target_main,
            special_numbers=TARGET_SPECIAL_NUMBERS,
        ),
    ]
    strategy_descriptors = [
        build_strategy_descriptor(
            strategy_id=REAL_STRATEGY_IDS[0], identity_kind="REAL", governance_status="UNKNOWN"
        )
    ]
    portfolios = [build_portfolio(strategy_id=REAL_STRATEGY_IDS[0], tickets=tickets)]
    return build_envelope(
        strategy_descriptors=strategy_descriptors,
        draw_snapshots=draw_snapshots,
        portfolios=portfolios,
    )


def test_m4plus_flag_and_filter_use_only_the_requested_prefix(tmp_path: Path) -> None:
    database = tmp_path / "historical.db"
    run_id = _commit(database, _build_m4plus_boundary_envelope())
    repository = SQLiteHistoricalResultQueryRepository(database)

    page10 = repository.list_replay_portfolios(
        run_id, HistoricalReplayQuery(strategy_id=REAL_STRATEGY_IDS[0], ticket_count=10)
    )
    page15 = repository.list_replay_portfolios(
        run_id, HistoricalReplayQuery(strategy_id=REAL_STRATEGY_IDS[0], ticket_count=15)
    )
    page20 = repository.list_replay_portfolios(
        run_id, HistoricalReplayQuery(strategy_id=REAL_STRATEGY_IDS[0], ticket_count=20)
    )
    assert page10 is not None and page10.items[0].m4plus is False
    assert page15 is not None and page15.items[0].m4plus is True
    assert page20 is not None and page20.items[0].m4plus is True

    # Position 1 carries a special-number hit with zero main hits: confirm it
    # never counts toward M4+ on its own.
    assert page10.items[0].tickets[0].special_hit is True
    assert page10.items[0].tickets[0].main_hit_count == 0

    filtered_out = repository.list_replay_portfolios(
        run_id,
        HistoricalReplayQuery(strategy_id=REAL_STRATEGY_IDS[0], ticket_count=10, m4plus_only=True),
    )
    assert filtered_out is not None
    assert filtered_out.total_count == 0
    assert filtered_out.items == ()

    filtered_in = repository.list_replay_portfolios(
        run_id,
        HistoricalReplayQuery(strategy_id=REAL_STRATEGY_IDS[0], ticket_count=15, m4plus_only=True),
    )
    assert filtered_in is not None
    assert filtered_in.total_count == 1


def test_replay_portfolios_use_numeric_not_lexical_draw_ordering(tmp_path: Path) -> None:
    cutoff = build_draw_snapshot(
        draw_number=1,
        draw_date="2026-01-01",
        main_numbers=CUTOFF_MAIN_NUMBERS,
        special_numbers=CUTOFF_SPECIAL_NUMBERS,
    )
    draw_9 = build_draw_snapshot(
        draw_number=9,
        draw_date="2026-02-01",
        main_numbers=TARGET_MAIN_NUMBERS,
        special_numbers=TARGET_SPECIAL_NUMBERS,
    )
    draw_10 = build_draw_snapshot(
        draw_number=10,
        draw_date="2026-02-01",
        main_numbers=TARGET_MAIN_NUMBERS,
        special_numbers=TARGET_SPECIAL_NUMBERS,
    )
    strategy = build_strategy_descriptor(
        strategy_id=REAL_STRATEGY_IDS[0], identity_kind="REAL", governance_status="UNKNOWN"
    )
    # Deliberately built with draw 10's portfolio listed first, to prove the
    # repository -- not fixture insertion order -- determines the result order.
    portfolio_10 = build_portfolio(
        strategy_id=REAL_STRATEGY_IDS[0], target_draw_number=10, cutoff_draw_number=1
    )
    portfolio_9 = build_portfolio(
        strategy_id=REAL_STRATEGY_IDS[0], target_draw_number=9, cutoff_draw_number=1
    )
    envelope = build_envelope(
        strategy_descriptors=[strategy],
        draw_snapshots=[cutoff, draw_9, draw_10],
        portfolios=[portfolio_10, portfolio_9],
    )

    database = tmp_path / "historical.db"
    run_id = _commit(database, envelope)
    repository = SQLiteHistoricalResultQueryRepository(database)

    page = repository.list_replay_portfolios(
        run_id, HistoricalReplayQuery(strategy_id=REAL_STRATEGY_IDS[0], ticket_count=10)
    )
    assert page is not None
    assert [item.target_draw.draw_number for item in page.items] == ["9", "10"]


def test_replay_pagination_is_deterministic(tmp_path: Path) -> None:
    database = tmp_path / "historical.db"
    cutoff = build_draw_snapshot(
        draw_number=1,
        draw_date="2026-01-01",
        main_numbers=CUTOFF_MAIN_NUMBERS,
        special_numbers=CUTOFF_SPECIAL_NUMBERS,
    )
    strategy = build_strategy_descriptor(
        strategy_id=REAL_STRATEGY_IDS[0], identity_kind="REAL", governance_status="UNKNOWN"
    )
    draw_snapshots: list[dict[str, Any]] = [cutoff]
    portfolios: list[dict[str, Any]] = []
    for target_number in range(2, 7):
        draw_snapshots.append(
            build_draw_snapshot(
                draw_number=target_number,
                draw_date="2026-03-01",
                main_numbers=TARGET_MAIN_NUMBERS,
                special_numbers=TARGET_SPECIAL_NUMBERS,
            )
        )
        portfolios.append(
            build_portfolio(
                strategy_id=REAL_STRATEGY_IDS[0],
                target_draw_number=target_number,
                cutoff_draw_number=1,
            )
        )
    envelope = build_envelope(
        strategy_descriptors=[strategy], draw_snapshots=draw_snapshots, portfolios=portfolios
    )
    run_id = _commit(database, envelope)
    repository = SQLiteHistoricalResultQueryRepository(database)

    full_query = HistoricalReplayQuery(
        strategy_id=REAL_STRATEGY_IDS[0], ticket_count=10, limit=50, offset=0
    )
    full_page = repository.list_replay_portfolios(run_id, full_query)
    assert full_page is not None
    assert full_page.total_count == 5
    ordered_numbers = [item.target_draw.draw_number for item in full_page.items]

    first_query = HistoricalReplayQuery(
        strategy_id=REAL_STRATEGY_IDS[0], ticket_count=10, limit=2, offset=0
    )
    first_page = repository.list_replay_portfolios(run_id, first_query)
    second_query = HistoricalReplayQuery(
        strategy_id=REAL_STRATEGY_IDS[0], ticket_count=10, limit=2, offset=2
    )
    second_page = repository.list_replay_portfolios(run_id, second_query)
    third_query = HistoricalReplayQuery(
        strategy_id=REAL_STRATEGY_IDS[0], ticket_count=10, limit=2, offset=4
    )
    third_page = repository.list_replay_portfolios(run_id, third_query)
    assert first_page is not None and second_page is not None and third_page is not None
    assert [item.target_draw.draw_number for item in first_page.items] == ordered_numbers[0:2]
    assert [item.target_draw.draw_number for item in second_page.items] == ordered_numbers[2:4]
    assert [item.target_draw.draw_number for item in third_page.items] == ordered_numbers[4:5]
    assert first_page.total_count == second_page.total_count == third_page.total_count == 5


def test_unknown_run_and_portfolio_are_not_found(tmp_path: Path) -> None:
    database = tmp_path / "historical.db"
    _commit(database, build_baseline_envelope())
    repository = SQLiteHistoricalResultQueryRepository(database)

    assert repository.list_strategies("does-not-exist", ticket_count=10) is None
    assert repository.get_portfolio("does-not-exist", ticket_count=10) is None
    assert (
        repository.list_replay_portfolios(
            "does-not-exist",
            HistoricalReplayQuery(strategy_id=REAL_STRATEGY_IDS[0], ticket_count=10),
        )
        is None
    )


def test_absent_database_creates_nothing(tmp_path: Path) -> None:
    database = tmp_path / "does-not-exist" / "historical.db"
    repository = SQLiteHistoricalResultQueryRepository(database)

    page = repository.list_runs(HistoricalRunQuery(limit=50, offset=0))
    assert page.items == ()
    assert page.total_count == 0
    assert repository.get_portfolio("anything", ticket_count=10) is None
    assert repository.list_strategies("anything", ticket_count=10) is None

    assert not database.exists()
    assert not database.parent.exists()


def test_corrupt_database_fails_closed_instead_of_empty(tmp_path: Path) -> None:
    database = tmp_path / "historical.db"
    database.write_bytes(b"this is not a valid sqlite database file, just garbage bytes")
    repository = SQLiteHistoricalResultQueryRepository(database)

    with pytest.raises(HistoricalResultsUnavailableError):
        repository.list_runs(HistoricalRunQuery(limit=50, offset=0))
    with pytest.raises(HistoricalResultsUnavailableError):
        repository.get_portfolio("anything", ticket_count=10)


def test_read_only_queries_leave_the_database_byte_identical_and_create_no_sidecar_files(
    tmp_path: Path,
) -> None:
    database = tmp_path / "historical.db"
    run_id = _commit(database, build_baseline_envelope())
    before = database.read_bytes()

    repository = SQLiteHistoricalResultQueryRepository(database)
    repository.list_runs(HistoricalRunQuery(limit=50, offset=0))
    repository.list_strategies(run_id, ticket_count=10)
    repository.list_replay_portfolios(
        run_id, HistoricalReplayQuery(strategy_id=REAL_STRATEGY_IDS[0], ticket_count=20)
    )
    page = repository.list_replay_portfolios(
        run_id, HistoricalReplayQuery(strategy_id=REAL_STRATEGY_IDS[0], ticket_count=20)
    )
    assert page is not None
    repository.get_portfolio(page.items[0].portfolio_id, ticket_count=20)

    after = database.read_bytes()
    assert before == after
    assert not (tmp_path / "historical.db-wal").exists()
    assert not (tmp_path / "historical.db-shm").exists()
    assert not (tmp_path / "historical.db-journal").exists()
