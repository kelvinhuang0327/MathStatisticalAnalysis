"""Focused acceptance tests for source loaders and candidate persistence."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest

from lottolab.application.p638_historical import P638ReplayQuery
from lottolab.application.use_cases.historical_replay_controller import (
    HistoricalReplayController,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import (
    HistoricalReplayMode,
    HistoricalReplayRequest,
    ReplayBehavior,
    ReplayDraw,
    ReplayEvaluation,
    ReplayStrategy,
    ReplayTicket,
)
from lottolab.infrastructure.persistence.historical_replay_candidates import (
    CandidateConflictError,
    SQLiteP638CandidatePersistence,
    SQLiteT539CandidatePersistence,
    T539TypedClosureStorageRequired,
)
from lottolab.infrastructure.persistence.historical_replay_sources import (
    HistoricalReplaySourceBundle,
    SQLiteP638ReplaySourceLoader,
    SQLiteT539ReplaySourceLoader,
)
from lottolab.infrastructure.persistence.historical_schema import (
    initialize_schema,
    open_database,
)
from lottolab.infrastructure.persistence.p638_historical_forwarder import (
    P638ForwardingError,
    P638HistoricalForwarder,
)
from lottolab.infrastructure.persistence.p638_historical_repositories import (
    SQLiteP638HistoricalQueryRepository,
)
from lottolab.strategies.adapters.base import SourceNativePortfolioClosure


def _p638_draw(number: int) -> ReplayDraw:
    return ReplayDraw(
        lottery_type=LotteryType.POWER_LOTTO,
        draw_number=str(number),
        draw_date=date(2026, 1, 1) + timedelta(days=number - 1),
        main_numbers=(1, 2, 3, 4, 5, 6),
        special_number=1,
    )


def _daily_draw(number: int) -> ReplayDraw:
    return ReplayDraw(
        lottery_type=LotteryType.DAILY_539,
        draw_number=str(number),
        draw_date=date(2026, 1, 1) + timedelta(days=number - 1),
        main_numbers=(1, 2, 3, 4, 5),
    )


def _strategy(
    lottery_type: LotteryType,
    *,
    native_ticket_count: int = 1,
    min_history: int = 1,
) -> ReplayStrategy:
    return ReplayStrategy(
        strategy_id="fixture",
        strategy_name="Fixture",
        strategy_version="v1",
        behavior=ReplayBehavior.DETERMINISTIC,
        native_ticket_count=native_ticket_count,
        min_history=min_history,
        fingerprint=hashlib.sha256(b"fixture-provenance").hexdigest()
        if lottery_type is LotteryType.POWER_LOTTO
        else None,
    )


class _PowerFixtureAdapter:
    lottery_type = LotteryType.POWER_LOTTO

    def __init__(self, *, closure_target: str | None = None, changed: bool = False) -> None:
        self._closure_target = closure_target
        self._changed = changed

    def generate(
        self,
        strategy: ReplayStrategy,
        history: tuple[ReplayDraw, ...],
        target: ReplayDraw,
    ) -> tuple[ReplayTicket, ...]:
        if target.draw_number == self._closure_target:
            raise SourceNativePortfolioClosure(
                strategy_id=strategy.strategy_id,
                expected_ticket_count=strategy.native_ticket_count,
                actual_ticket_count=0,
            )
        offset = 7 if self._changed else 0
        return tuple(
            ReplayTicket(
                ticket_position=position,
                main_numbers=(1 + offset, 2 + offset, 3 + offset, 4 + offset, 5 + offset, 6),
                special_number=1,
            )
            for position in range(1, strategy.native_ticket_count + 1)
        )

    def evaluate(
        self,
        strategy: ReplayStrategy,
        ticket: ReplayTicket,
        target: ReplayDraw,
    ) -> ReplayEvaluation:
        return ReplayEvaluation(
            zone1_hits=len(set(ticket.main_numbers) & set(target.main_numbers)),
            zone2_hit=ticket.special_number == target.special_number,
            is_winner=True,
            prize_tier="FIXTURE",
        )


class _DailyFixtureAdapter:
    lottery_type = LotteryType.DAILY_539

    def __init__(self, *, closure_target: str | None = None) -> None:
        self._closure_target = closure_target

    def generate(
        self,
        strategy: ReplayStrategy,
        history: tuple[ReplayDraw, ...],
        target: ReplayDraw,
    ) -> tuple[ReplayTicket, ...]:
        if target.draw_number == self._closure_target:
            raise SourceNativePortfolioClosure(
                strategy_id=strategy.strategy_id,
                expected_ticket_count=strategy.native_ticket_count,
                actual_ticket_count=0,
            )
        return tuple(
            ReplayTicket(ticket_position=1, main_numbers=(1, 2, 3, 4, 5))
            for _ in range(strategy.native_ticket_count)
        )

    def evaluate(
        self,
        strategy: ReplayStrategy,
        ticket: ReplayTicket,
        target: ReplayDraw,
    ) -> ReplayEvaluation:
        return ReplayEvaluation(5, False, True, "FIXTURE")


def _make_p638_source(database: Path) -> None:
    initialize_schema(database)
    with open_database(database) as connection:
        connection.execute(
            """
            INSERT INTO historical_result_run (
                id, import_identity_sha256, manifest_sha256, contract_version,
                source_kind, source_repository, source_commit_oid, source_artifact_sha256,
                dataset_identity, dataset_sha256, legacy_run_id, lottery_type, status,
                started_at, completed_at, error_code, error_summary, created_at
            ) VALUES ('run-p638', ?, ?, 'fixture', 'TEST', 'repo', ?, ?, 'dataset', ?,
                      NULL, 'POWER_LOTTO', 'COMPLETED', 'now', 'now', NULL, NULL, 'now')
            """,
            ("1" * 64, "2" * 64, "3" * 40, "4" * 64, "5" * 64),
        )
        connection.execute(
            """
            INSERT INTO historical_strategy_snapshot (
                id, run_id, strategy_id, effective_strategy_id, strategy_version,
                replicate, identity_kind, governance_status, alias_of_strategy_id,
                equivalence_group, nested_prefix_supported, descriptor_sha256, created_at
            ) VALUES ('snapshot-fixture', 'run-p638', 'fixture', 'fixture', 'v1', 1,
                      'REAL', 'ONLINE', NULL, NULL, 1, ?, 'now')
            """,
            ("6" * 64,),
        )
        for number in (1, 2, 3):
            draw = _p638_draw(number)
            connection.execute(
                """
                INSERT INTO historical_draw_snapshot (
                    id, run_id, lottery_type, draw_number, draw_date,
                    main_numbers_json, special_numbers_json, draw_sha256, created_at
                ) VALUES (?, 'run-p638', 'POWER_LOTTO', ?, ?, ?, ?, ?, 'now')
                """,
                (
                    number,
                    draw.draw_number,
                    draw.draw_date.isoformat(),
                    json.dumps(draw.main_numbers, separators=(",", ":")),
                    json.dumps([draw.special_number], separators=(",", ":")),
                    str(number) * 64,
                ),
            )
        connection.execute(
            """
            INSERT INTO historical_p638_run (
                run_id, lottery_type, source_run_id, source_replay_sha256,
                source_draw_db_sha256, source_content_sha256, second_zone_ssot_version,
                total_source_targets, selected_strategy_count, draw_count, eligible_attempts,
                complete_targets, excluded_targets, failed_targets, ticket_rows,
                provenance_json, created_at, completed_at
            ) VALUES ('run-p638', 'POWER_LOTTO', 'source-p638', ?, ?, ?, 'ssot-v1',
                      0, 1, 3, 0, 0, 0, 0, 0, '{}', 'now', 'now')
            """,
            ("7" * 64, "8" * 64, "9" * 64),
        )
        connection.execute(
            """
            INSERT INTO historical_p638_strategy_ledger (
                strategy_snapshot_id, run_id, strategy_id, strategy_version, lottery_type,
                display_label, executable, adapter_path, native_ticket_count, min_history,
                zone1_contract, zone2_contract, lifecycle_status, replay_status,
                source_run_id, source_replay_sha256, source_paths_json, provenance,
                exclusion_reason
            ) VALUES ('snapshot-fixture', 'run-p638', 'fixture', 'v1', 'POWER_LOTTO',
                      'Fixture', 1, 'fixture', 2, 1, '6-of-38', '1-of-8', 'ONLINE',
                      'REPLAY_COMPLETED', 'source-p638', ?, '[]', 'fixture-provenance', NULL)
            """,
            ("7" * 64,),
        )
        connection.commit()


def _add_wrong_p638_target(database: Path) -> None:
    with open_database(database) as connection:
        connection.execute(
            """
            INSERT INTO historical_p638_target (
                id, run_id, strategy_snapshot_id, strategy_id, strategy_version,
                target_draw_snapshot_id, cutoff_draw_snapshot_id, target_draw_number,
                target_draw_date, history_boundary_draw_number, history_boundary_date,
                history_length, expected_ticket_count, status, exclusion_reason,
                failure_reason, source_target_locator
            ) VALUES ('wrong-target-2', 'run-p638', 'snapshot-fixture', 'fixture', 'v1',
                      2, 1, '2', '2026-01-02', '1', '2026-01-01', 1, 1, 'COMPLETE',
                      NULL, NULL, 'fixture-wrong-target')
            """
        )
        connection.execute(
            """
            INSERT INTO historical_p638_ticket (
                id, target_id, run_id, strategy_id, strategy_version, target_draw_number,
                ticket_position, predicted_zone1_numbers_json, predicted_zone2_number,
                actual_zone1_numbers_json, actual_zone2_number, zone1_hit_count, zone2_hit,
                status, source_run_id, source_replay_sha256, source_record_locator,
                second_zone_ssot_version, provenance
            ) VALUES ('wrong-ticket-2', 'wrong-target-2', 'run-p638', 'fixture', 'v1', '2',
                      1, '[7,8,9,10,11,12]', 1, '[1,2,3,4,5,6]', 1, 0, 1, 'COMPLETE',
                      'source-p638', ?, 'fixture-wrong-ticket', 'ssot-v1',
                      'fixture-provenance')
            """,
            ("7" * 64,),
        )
        connection.commit()


def _make_t539_source(database: Path) -> None:
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE run_metadata (
                run_id TEXT PRIMARY KEY, schema_version TEXT NOT NULL,
                lottery_type TEXT NOT NULL, source_endpoint TEXT NOT NULL,
                source_sha256 TEXT NOT NULL, as_of_date TEXT NOT NULL,
                adapter_source_commit TEXT NOT NULL, strategy_set_json TEXT NOT NULL,
                status TEXT NOT NULL
            );
            CREATE TABLE source_draws (
                draw_id TEXT PRIMARY KEY, lottery_type TEXT NOT NULL,
                draw_date TEXT NOT NULL, main_numbers_json TEXT NOT NULL,
                draw_order INTEGER NOT NULL
            );
            CREATE TABLE strategy_coverage (
                run_id TEXT NOT NULL, strategy_id TEXT NOT NULL,
                strategy_version TEXT NOT NULL, lottery_type TEXT NOT NULL,
                native_ticket_count INTEGER NOT NULL, min_history INTEGER NOT NULL,
                first_eligible_target_draw_id TEXT, expected_target_draw_count INTEGER NOT NULL,
                processed_target_draw_count INTEGER NOT NULL,
                successful_target_draw_count INTEGER NOT NULL,
                failed_target_draw_count INTEGER NOT NULL, status TEXT NOT NULL,
                PRIMARY KEY (run_id, strategy_id, strategy_version)
            );
            CREATE TABLE prediction_tickets (
                run_id TEXT NOT NULL, strategy_id TEXT NOT NULL, strategy_version TEXT NOT NULL,
                lottery_type TEXT NOT NULL, target_draw_id TEXT NOT NULL,
                target_draw_date TEXT NOT NULL,
                cutoff_draw_id TEXT, cutoff_draw_date TEXT, native_ticket_count INTEGER NOT NULL,
                ticket_position INTEGER NOT NULL, main_numbers_json TEXT, special_number INTEGER,
                hits INTEGER, execution_status TEXT NOT NULL, failure_reason TEXT,
                provenance_json TEXT NOT NULL, adapter_source_commit TEXT NOT NULL,
                PRIMARY KEY (run_id, strategy_id, strategy_version, target_draw_id, ticket_position)
            );
            CREATE TABLE prediction_scores (
                run_id TEXT NOT NULL, strategy_id TEXT NOT NULL, strategy_version TEXT NOT NULL,
                target_draw_id TEXT NOT NULL, ticket_position INTEGER NOT NULL,
                actual_main_numbers_json TEXT NOT NULL, hit_numbers_json TEXT NOT NULL,
                hits INTEGER NOT NULL, score_version TEXT NOT NULL,
                PRIMARY KEY (run_id, strategy_id, strategy_version, target_draw_id, ticket_position)
            );
            CREATE TABLE failure_ledger (
                run_id TEXT NOT NULL, strategy_id TEXT NOT NULL, strategy_version TEXT NOT NULL,
                target_draw_id TEXT NOT NULL, target_draw_date TEXT NOT NULL, cutoff_draw_id TEXT,
                failure_code TEXT NOT NULL, failure_message TEXT NOT NULL,
                expected_ticket_count INTEGER NOT NULL, provenance_json TEXT NOT NULL,
                adapter_source_commit TEXT NOT NULL,
                PRIMARY KEY (run_id, strategy_id, strategy_version, target_draw_id)
            );
            CREATE TABLE target_completion (
                run_id TEXT NOT NULL, strategy_id TEXT NOT NULL, strategy_version TEXT NOT NULL,
                target_draw_id TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('SUCCESS','FAILED')),
                native_ticket_count INTEGER NOT NULL,
                PRIMARY KEY (run_id, strategy_id, strategy_version, target_draw_id)
            );
            """
        )
        connection.execute(
            "INSERT INTO run_metadata VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "run-t539",
                "t539-v1",
                "DAILY_539",
                "fixture",
                "source-hash",
                "2026-01-03",
                "fixture-commit",
                "[]",
                "COMPLETE",
            ),
        )
        for number in (1, 2, 3):
            draw = _daily_draw(number)
            connection.execute(
                "INSERT INTO source_draws VALUES (?, ?, ?, ?, ?)",
                (
                    draw.draw_number,
                    "DAILY_539",
                    draw.draw_date.isoformat(),
                    json.dumps(draw.main_numbers, separators=(",", ":")),
                    number - 1,
                ),
            )
        connection.execute(
            "INSERT INTO strategy_coverage VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("run-t539", "fixture", "v1", "DAILY_539", 1, 1, "2", 2, 1, 1, 0, "COMPLETE"),
        )
        connection.execute(
            "INSERT INTO target_completion VALUES (?, ?, ?, ?, ?, ?)",
            ("run-t539", "fixture", "v1", "2", "SUCCESS", 1),
        )
        connection.execute(
            "INSERT INTO prediction_tickets VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "run-t539", "fixture", "v1", "DAILY_539", "2", "2026-01-02", "1",
                "2026-01-01", 1, 1, "[1,2,3,4,5]", None, 5, "SUCCESS", None, "{}", "fixture",
            ),
        )
        connection.execute(
            "INSERT INTO prediction_scores VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("run-t539", "fixture", "v1", "2", 1, "[1,2,3,4,5]", "[1,2,3,4,5]", 5, "fixture"),
        )
        connection.commit()


def _t539_request(
    bundle: HistoricalReplaySourceBundle,
    *,
    mode: HistoricalReplayMode = HistoricalReplayMode.FULL_REPLAY,
    official_draws: tuple[ReplayDraw, ...] = (),
) -> HistoricalReplayRequest:
    strategy = ReplayStrategy(
        strategy_id="fixture",
        strategy_name="Fixture",
        strategy_version="v1",
        behavior=ReplayBehavior.DETERMINISTIC,
        native_ticket_count=1,
        min_history=1,
    )
    return HistoricalReplayRequest(
        lottery_type=LotteryType.DAILY_539,
        mode=mode,
        source=replace(bundle.snapshot, official_draws=official_draws),
        strategies=(strategy,),
        cutoff_draw_number="3",
    )


def _p638_request(
    bundle: HistoricalReplaySourceBundle,
    *,
    mode: HistoricalReplayMode = HistoricalReplayMode.FULL_REPLAY,
    official_draws: tuple[ReplayDraw, ...] = (),
) -> HistoricalReplayRequest:
    return HistoricalReplayRequest(
        lottery_type=LotteryType.POWER_LOTTO,
        mode=mode,
        source=replace(bundle.snapshot, official_draws=official_draws),
        strategies=(_strategy(LotteryType.POWER_LOTTO, native_ticket_count=2),),
        cutoff_draw_number="3",
    )


def test_p638_loader_and_candidate_persistence_preserve_typed_closure(
    tmp_path: Path,
) -> None:
    source = tmp_path / "p638-source.db"
    candidate = tmp_path / "p638-candidate.db"
    _make_p638_source(source)
    bundle = SQLiteP638ReplaySourceLoader(source).load()
    request = _p638_request(bundle)
    controller = HistoricalReplayController(_PowerFixtureAdapter(closure_target="3"))
    writer = SQLiteP638CandidatePersistence(source, candidate, task_root=tmp_path)
    first = writer.execute(request, controller)
    assert first.records_inserted == 3
    assert first.records_reused == 0
    assert first.source_sha256_before == first.source_sha256_after

    repository = SQLiteP638HistoricalQueryRepository(candidate)
    closure = repository.get_target_by_identity("run-p638", "fixture", "v1", "3")
    assert closure is not None
    assert closure.status == "EXCLUDED_SOURCE_NATIVE_PORTFOLIO_CLOSURE"
    assert closure.exclusion_reason
    assert closure.failure_reason is None
    assert closure.expected_ticket_count == 2
    assert closure.history_length == 2
    assert closure.history_boundary_draw_number == "2"
    assert closure.tickets == ()
    alias_page = repository.list_replay(
        "run-p638",
        P638ReplayQuery(status="SOURCE_NATIVE_TYPED_CLOSURE", limit=10, offset=0),
    )
    assert alias_page is not None
    assert alias_page.total_count == 1
    assert alias_page.items[0].status == "EXCLUDED_SOURCE_NATIVE_PORTFOLIO_CLOSURE"
    metrics = repository.get_metrics("run-p638")
    assert metrics is not None
    assert metrics.complete_target_count == 1
    assert metrics.excluded_target_count == 2
    assert metrics.failed_target_count == 0
    assert metrics.ticket_count == 2
    summary = repository.list_runs(limit=10, offset=0).items[0]
    assert summary.complete_target_count == 1
    assert summary.excluded_target_count == 2
    assert summary.failed_target_count == 0
    assert summary.ticket_count == 2
    strategies = repository.list_strategies("run-p638", limit=10, offset=0)
    assert strategies is not None
    assert strategies.items[0].excluded_target_count == 2
    assert strategies.items[0].first_draw_number == "1"
    assert strategies.items[0].first_draw_date == "2026-01-01"
    assert strategies.items[0].last_draw_number == "3"
    assert strategies.items[0].last_draw_date == "2026-01-03"

    second = writer.execute(request, controller)
    assert second.records_inserted == 0
    assert second.records_reused == 3
    with open_database(candidate, read_only=True) as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute(
            "SELECT status, exclusion_reason, failure_reason FROM historical_p638_target "
            "WHERE target_draw_number = '3'"
        ).fetchone()[0] == "EXCLUDED_SOURCE_NATIVE_PORTFOLIO_CLOSURE"

    conflict_writer = SQLiteP638CandidatePersistence(
        source,
        tmp_path / "p638-conflict.db",
        task_root=tmp_path,
    )
    conflict_writer.execute(
        request,
        HistoricalReplayController(_PowerFixtureAdapter(closure_target="3", changed=True)),
    )
    with pytest.raises(CandidateConflictError):
        writer.execute(
            request,
            HistoricalReplayController(_PowerFixtureAdapter(closure_target="3", changed=True)),
        )


def test_t539_loader_and_candidate_persistence_keep_source_read_only(
    tmp_path: Path,
) -> None:
    source = tmp_path / "t539-source.db"
    candidate = tmp_path / "t539-candidate.db"
    _make_t539_source(source)
    source_before = source.read_bytes()
    bundle = SQLiteT539ReplaySourceLoader(source).load()
    assert len(bundle.snapshot.stored_targets) == 1
    assert len(bundle.snapshot.stored_tickets) == 1
    request = _t539_request(bundle)
    outcome = SQLiteT539CandidatePersistence(source, candidate, task_root=tmp_path).execute(
        request, HistoricalReplayController(_DailyFixtureAdapter())
    )
    assert outcome.records_inserted == 2
    assert source.read_bytes() == source_before
    with sqlite3.connect(candidate) as connection:
        assert connection.execute("SELECT COUNT(*) FROM target_completion").fetchone() == (2,)
        assert connection.execute("SELECT COUNT(*) FROM prediction_tickets").fetchone() == (2,)
        assert connection.execute(
            "SELECT processed_target_draw_count, successful_target_draw_count, "
            "failed_target_draw_count "
            "FROM strategy_coverage"
        ).fetchone() == (2, 2, 0)
    again = SQLiteT539CandidatePersistence(source, candidate, task_root=tmp_path).execute(
        request, HistoricalReplayController(_DailyFixtureAdapter())
    )
    assert again.records_inserted == 0
    assert again.records_reused == 2


def test_t539_incremental_refresh_creates_nested_candidate_and_rejects_draw_conflict(
    tmp_path: Path,
) -> None:
    source = tmp_path / "t539-source.db"
    candidate = tmp_path / "nested" / "t539-candidate.db"
    _make_t539_source(source)
    bundle = SQLiteT539ReplaySourceLoader(source).load()
    request = _t539_request(
        bundle,
        mode=HistoricalReplayMode.INCREMENTAL_REFRESH,
        official_draws=(_daily_draw(4),),
    )
    writer = SQLiteT539CandidatePersistence(source, candidate, task_root=tmp_path)
    first = writer.execute(request, HistoricalReplayController(_DailyFixtureAdapter()))
    assert first.candidate_created is True
    assert first.records_inserted == 1
    assert first.records_reused == 0

    second = writer.execute(request, HistoricalReplayController(_DailyFixtureAdapter()))
    assert second.candidate_created is False
    assert second.records_inserted == 0
    assert second.records_reused == 1
    with sqlite3.connect(candidate) as connection:
        assert connection.execute("SELECT COUNT(*) FROM source_draws").fetchone() == (4,)
        assert connection.execute("SELECT COUNT(*) FROM target_completion").fetchone() == (2,)

    conflicting_draw = replace(_daily_draw(4), main_numbers=(1, 2, 3, 8, 9))
    conflict_request = _t539_request(
        bundle,
        mode=HistoricalReplayMode.INCREMENTAL_REFRESH,
        official_draws=(conflicting_draw,),
    )
    with pytest.raises(CandidateConflictError):
        writer.execute(conflict_request, HistoricalReplayController(_DailyFixtureAdapter()))


def test_t539_reconcile_repairs_selected_cells_in_candidate_only(tmp_path: Path) -> None:
    source = tmp_path / "t539-source.db"
    candidate = tmp_path / "t539-reconcile-candidate.db"
    _make_t539_source(source)
    with sqlite3.connect(source) as connection:
        connection.execute(
            "UPDATE prediction_tickets SET main_numbers_json = '[9,10,11,12,13]' "
            "WHERE target_draw_id = '2'"
        )
        connection.commit()
    source_before = source.read_bytes()
    bundle = SQLiteT539ReplaySourceLoader(source).load()
    request = _t539_request(bundle, mode=HistoricalReplayMode.RECONCILE)
    outcome = SQLiteT539CandidatePersistence(source, candidate, task_root=tmp_path).execute(
        request, HistoricalReplayController(_DailyFixtureAdapter())
    )
    assert outcome.records_considered == 2
    assert outcome.records_inserted == 2
    assert source.read_bytes() == source_before
    with sqlite3.connect(candidate) as connection:
        assert connection.execute(
            "SELECT main_numbers_json FROM prediction_tickets "
            "WHERE target_draw_id = '2'"
        ).fetchone() == ("[1,2,3,4,5]",)


def test_p638_reconcile_repairs_selected_cells_in_candidate_only(tmp_path: Path) -> None:
    source = tmp_path / "p638-source.db"
    candidate = tmp_path / "p638-reconcile-candidate.db"
    _make_p638_source(source)
    _add_wrong_p638_target(source)
    source_before = source.read_bytes()
    bundle = SQLiteP638ReplaySourceLoader(source).load()
    request = _p638_request(bundle, mode=HistoricalReplayMode.RECONCILE)
    writer = SQLiteP638CandidatePersistence(source, candidate, task_root=tmp_path)
    first = writer.execute(request, HistoricalReplayController(_PowerFixtureAdapter()))
    assert first.records_considered == 2
    assert first.records_inserted == 2
    assert first.records_reused == 0
    assert source.read_bytes() == source_before

    with sqlite3.connect(candidate) as connection:
        repaired_target_id = connection.execute(
            "SELECT id FROM historical_p638_target "
            "WHERE target_draw_number = '2' AND strategy_id = 'fixture'"
        ).fetchone()[0]
        assert connection.execute(
            "SELECT predicted_zone1_numbers_json FROM historical_p638_ticket "
            "WHERE target_id = ?",
            (repaired_target_id,),
        ).fetchone() == ("[1,2,3,4,5,6]",)
        assert connection.execute(
            "SELECT COUNT(*) FROM historical_p638_target WHERE status = 'COMPLETE'"
        ).fetchone() == (2,)

    second = writer.execute(request, HistoricalReplayController(_PowerFixtureAdapter()))
    assert second.records_inserted == 0
    assert second.records_reused == 2


def test_t539_typed_closure_fails_closed_before_candidate_creation(tmp_path: Path) -> None:
    source = tmp_path / "t539-source.db"
    candidate = tmp_path / "t539-candidate.db"
    _make_t539_source(source)
    bundle = SQLiteT539ReplaySourceLoader(source).load()
    request = _t539_request(bundle)
    with pytest.raises(T539TypedClosureStorageRequired):
        SQLiteT539CandidatePersistence(source, candidate, task_root=tmp_path).execute(
            request,
            HistoricalReplayController(_DailyFixtureAdapter(closure_target="3")),
        )
    assert not candidate.exists()


def test_p638_forwarder_rejects_output_aliasing_a_source(tmp_path: Path) -> None:
    source_replay = tmp_path / "replay.sqlite3"
    source_draw = tmp_path / "draws.sqlite3"
    source_replay.write_bytes(b"replay")
    source_draw.write_bytes(b"draws")
    forwarder = P638HistoricalForwarder(
        source_replay_db=source_replay,
        source_draw_db=source_draw,
        output_db=source_replay,
        expected_source_replay_sha256=hashlib.sha256(b"replay").hexdigest(),
        expected_source_replay_bytes=len(b"replay"),
        expected_source_draw_sha256=hashlib.sha256(b"draws").hexdigest(),
        expected_source_draw_bytes=len(b"draws"),
    )
    with pytest.raises(P638ForwardingError, match="must not alias"):
        forwarder.forward()
