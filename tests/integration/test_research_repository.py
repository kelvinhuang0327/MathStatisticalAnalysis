from __future__ import annotations

import dataclasses
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from lottolab.domain.lottery_rules import BIG_LOTTO_RULE_CONTRACT
from lottolab.domain.research import (
    ResearchExecutionStatus,
    ResearchRunKind,
    ResearchRunStatus,
)
from lottolab.infrastructure.persistence.research_repository import (
    ClosureInput,
    CompletedTargetCursor,
    CoverageCursor,
    CoverageRow,
    DrawBindingInput,
    DuplicateIdempotencyKeyError,
    RankingCursor,
    RankingRow,
    ResearchConflictError,
    ResearchRepositoryError,
    RunSummaryInput,
    SQLiteResearchRepository,
    StrategySnapshotInput,
    TargetCommitInput,
    TicketCursor,
    TicketInput,
    TicketResultInput,
)
from lottolab.infrastructure.persistence.research_schema import (
    IMMUTABLE_TABLE_NAMES,
    RESEARCH_DATABASE_FILENAME,
    ResearchDataPaths,
    open_database,
)


def _paths(tmp_path: Path) -> ResearchDataPaths:
    directory = tmp_path.resolve() / "research-data"
    return ResearchDataPaths(directory, directory / RESEARCH_DATABASE_FILENAME)


def _digest(character: str) -> str:
    return character * 64


def _draw(
    draw_number: str,
    draw_date: str,
    *,
    digest_character: str,
    special_numbers_json: str = "[7]",
) -> DrawBindingInput:
    return DrawBindingInput(
        lottery_type="BIG_LOTTO",
        draw_number=draw_number,
        draw_date=draw_date,
        main_numbers_json="[1,2,3,4,5,6]",
        special_numbers_json=special_numbers_json,
        draw_sha256=_digest(digest_character),
        draw_data_version="draw-v1",
    )


def _tickets(count: int = 3) -> tuple[TicketInput, ...]:
    values: list[TicketInput] = []
    for position in range(1, count + 1):
        main = [1, 2, 3, 4, 5, 6] if position <= 2 else [1, 2, 3, 4, 5, position + 5]
        special = [7]
        canonical = (
            f'{{"main_numbers":[{",".join(str(value) for value in main)}],'
            f'"special_numbers":[{",".join(str(value) for value in special)}]}}'
        )
        values.append(
            TicketInput(
                native_position=position,
                ordered_portfolio_position=position,
                canonical_ticket_json=canonical,
            )
        )
    return tuple(values)


def _bootstrap(
    repository: SQLiteResearchRepository,
    *,
    suffix: str,
    run_kind: ResearchRunKind = ResearchRunKind.HISTORICAL_BACKTEST,
    expected_target_count: int = 2,
) -> tuple[str, str]:
    contract_id = repository.register_rule_contract(
        BIG_LOTTO_RULE_CONTRACT,
        idempotency_key=f"{suffix}-rule",
    )
    run_id = repository.create_run(
        run_kind=run_kind,
        rule_contract_id=contract_id,
        input_dataset_identity=f"dataset-{suffix}",
        input_dataset_sha256=_digest("a"),
        expected_target_count=expected_target_count,
        producer_identity="pytest",
        execution_code_version="test-v1",
        source_commit_oid="948f299",
        idempotency_key=f"{suffix}-run",
    )
    strategy_id = repository.register_strategy_snapshot(
        run_id,
        StrategySnapshotInput(
            lottery_type="BIG_LOTTO",
            strategy_id=f"strategy-{suffix}",
            strategy_version="1",
            source_commit_oid="948f299",
            strategy_source_sha256=_digest("b"),
            producer_identity="pytest",
            producer_version="1",
            runtime_fingerprint="python-test",
            parameters_json="{}",
            seed_protocol="DETERMINISTIC",
            replicate=1,
            execution_code_version="test-v1",
            governance_status="CANDIDATE",
            lifecycle_status="RESEARCH",
        ),
        idempotency_key=f"{suffix}-strategy",
    )
    return run_id, strategy_id


def _target(
    run_id: str,
    strategy_id: str,
    *,
    target_order: int = 0,
    target_draw_number: str = "0002",
    target_draw_date: str = "2026-01-08",
    execution_status: ResearchExecutionStatus = ResearchExecutionStatus.OK,
    ticket_count: int = 3,
) -> TargetCommitInput:
    closure = (
        None
        if execution_status is ResearchExecutionStatus.OK
        else ClosureInput(
            closure_type=execution_status,
            reason_code=f"{execution_status.value}_TEST",
        )
    )
    return TargetCommitInput(
        run_id=run_id,
        strategy_snapshot_id=strategy_id,
        target_order=target_order,
        input_dataset_identity="dataset",
        input_dataset_sha256=_digest("a"),
        history_cutoff=_draw("0001", "2026-01-01", digest_character="c"),
        history_draw_count=100,
        source_history_order="DRAW_DATE_ASC,DRAW_NUMBER_ASC",
        target_draw=_draw(
            target_draw_number,
            target_draw_date,
            digest_character="d",
        ),
        causal_eligible=True,
        candidate_k=12,
        combination_count=924,
        ticket_count_prefix=5,
        tickets=_tickets(ticket_count),
        execution_status=execution_status,
        closure=closure,
    )


def test_two_different_rule_contract_shapes_persist_including_zero_special_numbers(
    tmp_path: Path,
) -> None:
    repository = SQLiteResearchRepository(_paths(tmp_path))
    no_special = dataclasses.replace(
        BIG_LOTTO_RULE_CONTRACT,
        contract_version="zero-special-test-v1",
        special_number_count=0,
        special_number_required=False,
    )

    first = repository.register_rule_contract(
        BIG_LOTTO_RULE_CONTRACT,
        idempotency_key="rule-one",
    )
    second = repository.register_rule_contract(
        no_special,
        idempotency_key="rule-two",
    )

    assert first != second
    with open_database(repository.paths, read_only=True) as connection:
        payloads = [
            row[0]
            for row in connection.execute(
                """
                SELECT canonical_payload_json
                FROM research_rule_contracts
                ORDER BY contract_version
                """
            )
        ]
    assert len(payloads) == 2
    assert any('"special_number_count":0' in payload for payload in payloads)


def test_ticket_order_duplicates_and_arbitrary_prefixes_round_trip(
    tmp_path: Path,
) -> None:
    repository = SQLiteResearchRepository(_paths(tmp_path))
    run_id, strategy_id = _bootstrap(repository, suffix="roundtrip")
    value = _target(run_id, strategy_id)

    result = repository.commit_target(value, idempotency_key="target-roundtrip")
    rows = repository.list_target_tickets(result.target_id).items
    for prefix in (5, 10, 15, 20, 37):
        repository.store_run_summary(
            RunSummaryInput(
                run_id=run_id,
                strategy_snapshot_id=strategy_id,
                summary_kind="RANKING",
                ticket_count_prefix=prefix,
                summary_version=1,
                denominator_count=1,
                successful_count=1,
                closed_count=0,
                rank_value=float(prefix),
                canonical_summary_json=f'{{"prefix":{prefix}}}',
            ),
            idempotency_key=f"summary-{prefix}",
        )

    assert [row[0] for row in rows] == [1, 2, 3]
    assert [row[1] for row in rows] == [1, 2, 3]
    assert [row[2] for row in rows] == [
        ticket.canonical_ticket_json for ticket in value.tickets
    ]
    assert rows[0][2] == rows[1][2]
    assert {row.ticket_count_prefix for row in repository.rankings().items} == {
        5,
        10,
        15,
        20,
        37,
    }
    with open_database(repository.paths, read_only=True) as connection:
        duplicates = connection.execute(
            """
            SELECT native_position, native_duplicate_of_position,
                   portfolio_duplicate_of_position
            FROM research_prediction_tickets
            WHERE target_id = ?
            ORDER BY native_position
            """,
            (result.target_id,),
        ).fetchall()
    assert duplicates == [(1, None, None), (2, 1, 1), (3, None, None)]


def test_completed_target_reexecution_is_verified_no_op_and_conflict_raises(
    tmp_path: Path,
) -> None:
    repository = SQLiteResearchRepository(_paths(tmp_path))
    run_id, strategy_id = _bootstrap(repository, suffix="idempotent")
    value = _target(run_id, strategy_id)

    first = repository.commit_target(value, idempotency_key="target-first")
    second = repository.commit_target(value, idempotency_key="target-second")
    changed_tickets = list(value.tickets)
    changed_tickets[0] = dataclasses.replace(
        changed_tickets[0],
        canonical_ticket_json=(
            '{"main_numbers":[2,3,4,5,6,7],"special_numbers":[8]}'
        ),
    )
    changed = dataclasses.replace(value, tickets=tuple(changed_tickets))

    assert first.verified_no_op is False
    assert second == dataclasses.replace(first, verified_no_op=True)
    with pytest.raises(ResearchConflictError, match="conflicts"):
        repository.commit_target(changed, idempotency_key="target-conflict")
    with open_database(repository.paths, read_only=True) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM research_prediction_targets"
            ).fetchone()[0]
            == 1
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM research_prediction_tickets"
            ).fetchone()[0]
            == len(value.tickets)
        )


@pytest.mark.parametrize(
    ("cutoff_number", "cutoff_date"),
    [("0002", "2026-01-08"), ("0003", "2026-01-15")],
)
def test_causal_cutoff_rejects_own_or_later_draw(
    tmp_path: Path,
    cutoff_number: str,
    cutoff_date: str,
) -> None:
    repository = SQLiteResearchRepository(_paths(tmp_path))
    run_id, strategy_id = _bootstrap(repository, suffix=f"causal-{cutoff_number}")
    value = _target(run_id, strategy_id)
    invalid = dataclasses.replace(
        value,
        history_cutoff=_draw(
            cutoff_number,
            cutoff_date,
            digest_character="e",
        ),
    )

    with pytest.raises(ResearchRepositoryError, match="store contract"):
        repository.commit_target(
            invalid,
            idempotency_key=f"invalid-{cutoff_number}",
        )
    assert repository.progress(run_id).completed_target_count == 0


def test_reference_baselines_are_excluded_by_default_but_queryable(
    tmp_path: Path,
) -> None:
    repository = SQLiteResearchRepository(_paths(tmp_path))
    authoritative_run, authoritative_strategy = _bootstrap(
        repository,
        suffix="authoritative",
    )
    baseline_run, baseline_strategy = _bootstrap(
        repository,
        suffix="baseline",
        run_kind=ResearchRunKind.REFERENCE_BASELINE,
    )
    repository.commit_target(
        _target(authoritative_run, authoritative_strategy),
        idempotency_key="authoritative-target",
    )
    repository.commit_target(
        _target(baseline_run, baseline_strategy),
        idempotency_key="baseline-target",
    )
    for run_id, strategy_id, label in (
        (authoritative_run, authoritative_strategy, "authoritative"),
        (baseline_run, baseline_strategy, "baseline"),
    ):
        repository.store_run_summary(
            RunSummaryInput(
                run_id=run_id,
                strategy_snapshot_id=strategy_id,
                summary_kind="RANKING",
                ticket_count_prefix=5,
                summary_version=1,
                denominator_count=1,
                successful_count=1,
                closed_count=0,
                rank_value=1.0,
                canonical_summary_json=f'{{"label":"{label}"}}',
            ),
            idempotency_key=f"{label}-summary",
        )

    assert {row.run_id for row in repository.coverage().items} == {authoritative_run}
    assert {row.run_id for row in repository.rankings().items} == {authoritative_run}
    assert {row.run_id for row in repository.coverage(
        include_reference_baselines=True
    ).items} == {authoritative_run, baseline_run}
    assert {row.run_id for row in repository.rankings(
        include_reference_baselines=True
    ).items} == {authoritative_run, baseline_run}


def test_typed_closure_remains_in_denominator_and_progress_query(
    tmp_path: Path,
) -> None:
    repository = SQLiteResearchRepository(_paths(tmp_path))
    run_id, strategy_id = _bootstrap(repository, suffix="closure")
    repository.commit_target(
        _target(
            run_id,
            strategy_id,
            execution_status=ResearchExecutionStatus.INSUFFICIENT_HISTORY,
            ticket_count=0,
        ),
        idempotency_key="closed-target",
    )

    coverage = repository.coverage().items
    progress = repository.progress(run_id)

    assert len(coverage) == 1
    assert coverage[0].denominator_count == 1
    assert coverage[0].ok_count == 0
    assert coverage[0].closed_count == 1
    assert progress.completed_target_count == 1
    assert repository.completed_target_keys(run_id).items == (
        (strategy_id, "BIG_LOTTO", "0002"),
    )


def test_duplicate_state_changing_idempotency_key_is_rejected(
    tmp_path: Path,
) -> None:
    repository = SQLiteResearchRepository(_paths(tmp_path))

    repository.register_rule_contract(
        BIG_LOTTO_RULE_CONTRACT,
        idempotency_key="duplicate-key",
    )

    with pytest.raises(DuplicateIdempotencyKeyError, match="consumed"):
        repository.register_rule_contract(
            BIG_LOTTO_RULE_CONTRACT,
            idempotency_key="duplicate-key",
        )


def test_current_pointer_moves_without_mutating_run_history(tmp_path: Path) -> None:
    repository = SQLiteResearchRepository(_paths(tmp_path))
    first_run, _ = _bootstrap(repository, suffix="pointer-one")
    second_run, _ = _bootstrap(repository, suffix="pointer-two")
    with open_database(repository.paths, read_only=True) as connection:
        before = connection.execute(
            "SELECT * FROM research_runs ORDER BY id"
        ).fetchall()

    repository.set_current_run(
        "BIG_LOTTO/default",
        first_run,
        idempotency_key="pointer-first",
    )
    repository.set_current_run(
        "BIG_LOTTO/default",
        second_run,
        idempotency_key="pointer-second",
    )

    with open_database(repository.paths, read_only=True) as connection:
        after = connection.execute(
            "SELECT * FROM research_runs ORDER BY id"
        ).fetchall()
        pointer = connection.execute(
            """
            SELECT run_id FROM research_run_current_pointer
            WHERE pointer_name = 'BIG_LOTTO/default'
            """
        ).fetchone()
    assert before == after
    assert pointer == (second_run,)


def test_changed_draw_checksum_creates_a_new_retained_result_version(
    tmp_path: Path,
) -> None:
    repository = SQLiteResearchRepository(_paths(tmp_path))
    run_id, strategy_id = _bootstrap(repository, suffix="results")
    target = repository.commit_target(
        _target(run_id, strategy_id),
        idempotency_key="results-target",
    )
    result = TicketResultInput(
        ticket_native_position=1,
        ticket_count_prefix=5,
        main_hit_count=3,
        special_hit_count=0,
        prize_tier_id="GENERAL",
    )

    assert repository.commit_ticket_results(
        target.target_id,
        _draw("0002", "2026-01-08", digest_character="d"),
        [result],
        idempotency_key="result-v1",
    ) == 1
    assert repository.commit_ticket_results(
        target.target_id,
        _draw("0002", "2026-01-08", digest_character="d"),
        [result],
        idempotency_key="result-same",
    ) == 0
    assert repository.commit_ticket_results(
        target.target_id,
        _draw("0002", "2026-01-08", digest_character="f"),
        [dataclasses.replace(result, main_hit_count=4)],
        idempotency_key="result-v2",
    ) == 1

    with open_database(repository.paths, read_only=True) as connection:
        rows = connection.execute(
            """
            SELECT result_version, draw_sha256, main_hit_count
            FROM research_ticket_results
            ORDER BY result_version
            """
        ).fetchall()
    assert rows == [(1, _digest("d"), 3), (2, _digest("f"), 4)]


def test_ticket_results_reject_a_different_target_draw_natural_key(
    tmp_path: Path,
) -> None:
    repository = SQLiteResearchRepository(_paths(tmp_path))
    run_id, strategy_id = _bootstrap(repository, suffix="result-key")
    target = repository.commit_target(
        _target(run_id, strategy_id),
        idempotency_key="result-key-target",
    )
    wrong_draw = _draw("9999", "2026-01-08", digest_character="8")

    with pytest.raises(ResearchRepositoryError, match="natural key"):
        repository.commit_ticket_results(
            target.target_id,
            wrong_draw,
            [
                TicketResultInput(
                    ticket_native_position=1,
                    ticket_count_prefix=5,
                    main_hit_count=0,
                    special_hit_count=0,
                    prize_tier_id=None,
                )
            ],
            idempotency_key="wrong-result-draw",
        )

    with open_database(repository.paths, read_only=True) as connection:
        assert (
            connection.execute(
                """
                SELECT COUNT(*) FROM research_draw_bindings
                WHERE draw_number = '9999'
                """
            ).fetchone()[0]
            == 0
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM research_ticket_results"
            ).fetchone()[0]
            == 0
        )


def test_schema_trigger_rejects_cross_target_result_draw_binding(
    tmp_path: Path,
) -> None:
    repository = SQLiteResearchRepository(_paths(tmp_path))
    run_id, strategy_id = _bootstrap(repository, suffix="result-trigger")
    target = repository.commit_target(
        _target(run_id, strategy_id),
        idempotency_key="result-trigger-target",
    )
    seed_run, seed_strategy = _bootstrap(repository, suffix="result-trigger-seed")
    repository.commit_target(
        _target(
            seed_run,
            seed_strategy,
            target_draw_number="9999",
            target_draw_date="2026-01-08",
        ),
        idempotency_key="result-trigger-seed-target",
    )
    connection = sqlite3.connect(str(repository.paths.database))
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        wrong_binding = connection.execute(
            """
            SELECT id, draw_sha256 FROM research_draw_bindings
            WHERE draw_number = '9999'
            """
        ).fetchone()
        ticket_id = connection.execute(
            """
            SELECT id FROM research_prediction_tickets
            WHERE target_id = ? AND native_position = 1
            """,
            (target.target_id,),
        ).fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError, match="natural key"):
            connection.execute(
                """
                INSERT INTO research_ticket_results (
                    id, target_id, ticket_id, draw_binding_id, result_version,
                    draw_sha256, ticket_count_prefix, main_hit_count,
                    special_hit_count, prize_tier_id, result_sha256, created_at
                ) VALUES (
                    'wrong-result', ?, ?, ?, 1, ?, 5, 0, 0, NULL, ?, 'now'
                )
                """,
                (
                    target.target_id,
                    ticket_id,
                    wrong_binding[0],
                    wrong_binding[1],
                    _digest("7"),
                ),
            )
    finally:
        connection.close()


def test_all_list_queries_use_stable_keyset_pages_without_gaps_or_duplicates(
    tmp_path: Path,
) -> None:
    repository = SQLiteResearchRepository(_paths(tmp_path))
    run_id, strategy_id = _bootstrap(
        repository,
        suffix="pagination-targets",
        expected_target_count=5,
    )
    target_ids: list[str] = []
    for index in range(5):
        committed = repository.commit_target(
            _target(
                run_id,
                strategy_id,
                target_order=index,
                target_draw_number=f"{index + 2:04d}",
                target_draw_date="2026-01-08",
                ticket_count=5,
            ),
            idempotency_key=f"pagination-target-{index}",
        )
        target_ids.append(committed.target_id)

    first_targets = repository.completed_target_keys(run_id, limit=2)
    assert isinstance(first_targets.next_cursor, CompletedTargetCursor)
    second_targets = repository.completed_target_keys(
        run_id,
        limit=2,
        after=first_targets.next_cursor,
    )
    assert isinstance(second_targets.next_cursor, CompletedTargetCursor)
    third_targets = repository.completed_target_keys(
        run_id,
        limit=2,
        after=second_targets.next_cursor,
    )
    assert third_targets.next_cursor is None
    target_items = (
        *first_targets.items,
        *second_targets.items,
        *third_targets.items,
    )
    assert len(target_items) == len(set(target_items)) == 5

    first_tickets = repository.list_target_tickets(target_ids[0], limit=2)
    assert isinstance(first_tickets.next_cursor, TicketCursor)
    second_tickets = repository.list_target_tickets(
        target_ids[0],
        limit=2,
        after=first_tickets.next_cursor,
    )
    assert isinstance(second_tickets.next_cursor, TicketCursor)
    third_tickets = repository.list_target_tickets(
        target_ids[0],
        limit=2,
        after=second_tickets.next_cursor,
    )
    ticket_items = (
        *first_tickets.items,
        *second_tickets.items,
        *third_tickets.items,
    )
    assert [row[0] for row in ticket_items] == [1, 2, 3, 4, 5]
    assert third_tickets.next_cursor is None

    coverage_run_ids: list[str] = []
    for index in range(5):
        coverage_run, coverage_strategy = _bootstrap(
            repository,
            suffix=f"pagination-coverage-{index}",
            expected_target_count=1,
        )
        coverage_run_ids.append(coverage_run)
        repository.commit_target(
            _target(coverage_run, coverage_strategy),
            idempotency_key=f"pagination-coverage-target-{index}",
        )
    coverage_pages: list[CoverageRow] = []
    coverage_cursor: CoverageCursor | None = None
    while True:
        page = repository.coverage(limit=2, after=coverage_cursor)
        coverage_pages.extend(page.items)
        if page.next_cursor is None:
            break
        assert isinstance(page.next_cursor, CoverageCursor)
        coverage_cursor = page.next_cursor
    observed_coverage_ids = [row.run_id for row in coverage_pages]
    assert len(observed_coverage_ids) == len(set(observed_coverage_ids)) == 6
    assert set(coverage_run_ids) < set(observed_coverage_ids)

    for index, prefix in enumerate((5, 10, 15, 20, 37)):
        repository.store_run_summary(
            RunSummaryInput(
                run_id=run_id,
                strategy_snapshot_id=strategy_id,
                summary_kind="RANKING",
                ticket_count_prefix=prefix,
                summary_version=1,
                denominator_count=5,
                successful_count=5,
                closed_count=0,
                rank_value=1.0 if index < 3 else None,
                canonical_summary_json=f'{{"page":{index}}}',
            ),
            idempotency_key=f"pagination-ranking-{index}",
        )
    ranking_pages: list[RankingRow] = []
    ranking_cursor: RankingCursor | None = None
    while True:
        page = repository.rankings(limit=2, after=ranking_cursor)
        ranking_pages.extend(page.items)
        if page.next_cursor is None:
            break
        assert isinstance(page.next_cursor, RankingCursor)
        ranking_cursor = page.next_cursor
    assert len(ranking_pages) == 5
    assert len({row.summary_sha256 for row in ranking_pages}) == 5


def test_append_only_triggers_block_update_and_delete_on_every_immutable_table(
    tmp_path: Path,
) -> None:
    repository = SQLiteResearchRepository(_paths(tmp_path))
    artifact_id = repository.register_artifact(
        artifact_kind="TEST",
        source_locator="fixture://artifact",
        media_type="application/json",
        byte_length=2,
        artifact_sha256=_digest("9"),
        idempotency_key="artifact",
    )
    run_id, strategy_id = _bootstrap(repository, suffix="append")
    target = repository.commit_target(
        _target(run_id, strategy_id),
        idempotency_key="append-target",
    )
    repository.commit_target(
        _target(
            run_id,
            strategy_id,
            target_order=1,
            target_draw_number="0003",
            target_draw_date="2026-01-15",
            execution_status=ResearchExecutionStatus.REJECTED,
            ticket_count=0,
        ),
        idempotency_key="append-closure",
    )
    repository.commit_ticket_results(
        target.target_id,
        _draw("0002", "2026-01-08", digest_character="d"),
        [
            TicketResultInput(
                ticket_native_position=1,
                ticket_count_prefix=5,
                main_hit_count=3,
                special_hit_count=0,
                prize_tier_id="GENERAL",
            )
        ],
        idempotency_key="append-result",
    )
    repository.store_run_summary(
        RunSummaryInput(
            run_id=run_id,
            strategy_snapshot_id=strategy_id,
            summary_kind="AUDIT",
            ticket_count_prefix=None,
            summary_version=1,
            denominator_count=2,
            successful_count=1,
            closed_count=1,
            rank_value=None,
            canonical_summary_json='{"status":"ok"}',
        ),
        idempotency_key="append-summary",
    )
    connection = sqlite3.connect(str(repository.paths.database))
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """
            INSERT INTO research_artifact_custody_events (
                id, artifact_id, sequence, custody_action,
                actor_identity, detail_json, created_at
            ) VALUES ('custody-1', ?, 0, 'REGISTERED', 'pytest', '{}', 'now')
            """,
            (artifact_id,),
        )
        connection.commit()
        for table in IMMUTABLE_TABLE_NAMES:
            assert connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0] >= 1
            with pytest.raises(sqlite3.IntegrityError, match="append-only"):
                connection.execute(f"UPDATE {table} SET rowid = rowid")
            with pytest.raises(sqlite3.IntegrityError, match="append-only"):
                connection.execute(f"DELETE FROM {table}")
    finally:
        connection.close()


def test_run_status_is_append_only_and_resumable(tmp_path: Path) -> None:
    repository = SQLiteResearchRepository(_paths(tmp_path))
    run_id, strategy_id = _bootstrap(repository, suffix="resume")
    repository.commit_target(
        _target(run_id, strategy_id),
        idempotency_key="resume-target",
    )

    running = repository.progress(run_id)
    repository.append_run_status(
        run_id,
        status=ResearchRunStatus.PAUSED,
        progress_cursor="target:0",
        idempotency_key="resume-paused",
    )
    paused = repository.progress(run_id)

    assert running.status is ResearchRunStatus.RUNNING
    assert paused.status is ResearchRunStatus.PAUSED
    assert paused.progress_cursor == "target:0"
    assert paused.completed_target_count == 1
    with open_database(repository.paths, read_only=True) as connection:
        assert (
            connection.execute(
                """
                SELECT COUNT(*) FROM research_run_status_events
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()[0]
            == 2
        )


def test_kill_mid_target_transaction_then_resume_leaves_no_orphan_or_duplicate(
    tmp_path: Path,
) -> None:
    repository = SQLiteResearchRepository(_paths(tmp_path))
    run_id, strategy_id = _bootstrap(repository, suffix="crash-owner")
    seed_run, seed_strategy = _bootstrap(repository, suffix="crash-seed")
    value = _target(
        run_id,
        strategy_id,
        target_order=1,
        target_draw_number="0003",
        target_draw_date="2026-01-15",
    )
    repository.commit_target(
        _target(
            seed_run,
            seed_strategy,
            target_order=1,
            target_draw_number="0003",
            target_draw_date="2026-01-15",
        ),
        idempotency_key="crash-seed-target",
    )
    script = """
import sqlite3
import sys
import time

database, run_id, strategy_id = sys.argv[1:4]
connection = sqlite3.connect(database, isolation_level=None)
connection.execute("PRAGMA foreign_keys = ON")
connection.execute("BEGIN IMMEDIATE")
cutoff = connection.execute(
    "SELECT id FROM research_draw_bindings WHERE draw_number = '0001' LIMIT 1"
).fetchone()[0]
target = connection.execute(
    "SELECT id FROM research_draw_bindings WHERE draw_number = '0003' LIMIT 1"
).fetchone()[0]
connection.execute(
    '''
    INSERT INTO research_prediction_targets (
        id, run_id, strategy_snapshot_id, target_order,
        input_dataset_identity, input_dataset_sha256,
        history_cutoff_binding_id, history_cutoff_lottery_type,
        history_cutoff_draw_number, history_cutoff_draw_date,
        history_draw_count, source_history_order,
        target_draw_binding_id, target_lottery_type,
        target_draw_number, target_draw_date, causal_eligible,
        candidate_k, combination_count, ticket_count_prefix,
        native_ticket_count, ordered_portfolio_count,
        execution_status, terminal_marker, target_payload_sha256,
        completed_at, created_at
    ) VALUES (
        'crash-target', ?, ?, 1, 'dataset', ?, ?, 'BIG_LOTTO',
        '0001', '2026-01-01', 100, 'DRAW_DATE_ASC,DRAW_NUMBER_ASC',
        ?, 'BIG_LOTTO', '0003', '2026-01-15', 1, 12, 924, 5,
        3, 3, 'OK', 1, ?, 'now', 'now'
    )
    ''',
    (run_id, strategy_id, "a" * 64, cutoff, target, "f" * 64),
)
print("inserted", flush=True)
time.sleep(60)
"""
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            script,
            str(repository.paths.database),
            run_id,
            strategy_id,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    assert process.stdout.readline().strip() == "inserted"
    process.kill()
    assert process.wait(timeout=10) != 0

    resumed = repository.commit_target(
        value,
        idempotency_key="crash-resumed-target",
    )

    assert resumed.verified_no_op is False
    with open_database(repository.paths, read_only=True) as connection:
        target_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM research_prediction_targets
            WHERE run_id = ? AND target_draw_number = '0003'
            """,
            (run_id,),
        ).fetchone()[0]
        orphan_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM research_prediction_tickets AS ticket
            LEFT JOIN research_prediction_targets AS target
              ON target.id = ticket.target_id
            WHERE target.id IS NULL
            """
        ).fetchone()[0]
    assert target_count == 1
    assert orphan_count == 0


def test_reader_observes_consistent_progress_during_active_write_loop(
    tmp_path: Path,
) -> None:
    repository = SQLiteResearchRepository(_paths(tmp_path))
    run_id, strategy_id = _bootstrap(
        repository,
        suffix="concurrent",
        expected_target_count=25,
    )
    writer_errors: list[BaseException] = []
    finished = threading.Event()

    def write_targets() -> None:
        try:
            for index in range(25):
                repository.commit_target(
                    _target(
                        run_id,
                        strategy_id,
                        target_order=index,
                        target_draw_number=f"{index + 2:04d}",
                        target_draw_date=f"2026-02-{index + 2:02d}",
                        ticket_count=3,
                    ),
                    idempotency_key=f"concurrent-{index}",
                )
        except BaseException as exc:  # pragma: no cover - asserted by parent thread
            writer_errors.append(exc)
        finally:
            finished.set()

    writer = threading.Thread(target=write_targets)
    writer.start()
    observed: list[int] = []
    while not finished.is_set():
        observed.append(repository.progress(run_id).completed_target_count)
        time.sleep(0.001)
    writer.join(timeout=10)
    observed.append(repository.progress(run_id).completed_target_count)

    assert writer_errors == []
    assert observed == sorted(observed)
    assert observed[-1] == 25
    assert all(0 <= count <= 25 for count in observed)
