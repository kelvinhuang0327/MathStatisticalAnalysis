"""Read-only and SQL-boundary guards for the R2 discovery corpus adapter."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest

from lottolab.infrastructure.historical_replay_meta_feature_interaction_corpus import (
    HistoricalReplayDiscoveryCorpusStorageError,
    load_historical_replay_discovery_corpus,
    sha256_file,
)
from lottolab.research.historical_replay_meta_feature_interaction_discovery import (
    DiscoveryPartition,
    DrawIdentity,
)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _numbers(offset: int) -> tuple[int, ...]:
    return tuple(sorted(((offset + step) % 49) + 1 for step in range(6)))


def _partition() -> DiscoveryPartition:
    start = date(2020, 1, 1)
    return DiscoveryPartition(
        split_method="SYNTHETIC_DISCOVERY_BOUNDARY",
        total_assignment_count=303,
        warmup_count=300,
        discovery_count=2,
        discovery_first_target=DrawIdentity(
            draw_date=(start + timedelta(days=300)).isoformat(),
            draw_number=100_000_300,
            draw_sha256=_sha("binding-300"),
        ),
        discovery_last_target=DrawIdentity(
            draw_date=(start + timedelta(days=301)).isoformat(),
            draw_number=100_000_301,
            draw_sha256=_sha("binding-301"),
        ),
    )


def _build_store(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE research_runs (
            id TEXT PRIMARY KEY,
            run_kind TEXT NOT NULL,
            input_dataset_identity TEXT NOT NULL,
            input_dataset_sha256 TEXT NOT NULL,
            rule_contract_id TEXT NOT NULL,
            started_at TEXT NOT NULL
        );
        CREATE TABLE research_run_status_events (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            sequence INTEGER NOT NULL,
            status TEXT NOT NULL
        );
        CREATE TABLE research_strategy_snapshots (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            strategy_id TEXT NOT NULL,
            strategy_version TEXT NOT NULL
        );
        CREATE TABLE research_draw_bindings (
            id TEXT PRIMARY KEY,
            draw_sha256 TEXT NOT NULL,
            main_numbers_json TEXT NOT NULL
        );
        CREATE TABLE research_prediction_targets (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            strategy_snapshot_id TEXT NOT NULL,
            target_draw_date TEXT NOT NULL,
            target_draw_number TEXT NOT NULL,
            native_ticket_count INTEGER NOT NULL,
            history_cutoff_draw_date TEXT NOT NULL,
            history_cutoff_draw_number TEXT NOT NULL,
            execution_status TEXT NOT NULL,
            target_draw_binding_id TEXT NOT NULL,
            history_cutoff_binding_id TEXT NOT NULL,
            causal_eligible INTEGER NOT NULL
        );
        CREATE TABLE research_prediction_tickets (
            id TEXT PRIMARY KEY,
            target_id TEXT NOT NULL,
            native_position INTEGER NOT NULL,
            main_numbers_json TEXT NOT NULL,
            ticket_sha256 TEXT NOT NULL,
            native_duplicate_of_position INTEGER,
            portfolio_duplicate_of_position INTEGER
        );
        CREATE TABLE research_ticket_results (
            id TEXT PRIMARY KEY,
            target_id TEXT NOT NULL,
            ticket_id TEXT NOT NULL,
            draw_binding_id TEXT NOT NULL,
            main_hit_count INTEGER NOT NULL,
            result_version INTEGER NOT NULL
        );
        """
    )
    run_id = "synthetic-reference-run"
    strategy_rows = (
        ("snapshot-a", run_id, "strategy-a", "v1"),
        ("snapshot-b", run_id, "strategy-b", "v1"),
    )
    connection.execute(
        "INSERT INTO research_runs VALUES (?, ?, ?, ?, ?, ?)",
        (
            run_id,
            "REFERENCE_BASELINE",
            "synthetic-dataset",
            _sha("synthetic-dataset"),
            "synthetic-rule-contract",
            "2026-01-01T00:00:00Z",
        ),
    )
    connection.execute(
        "INSERT INTO research_run_status_events VALUES (?, ?, ?, ?)",
        ("status-1", run_id, 1, "COMPLETED"),
    )
    connection.executemany(
        "INSERT INTO research_strategy_snapshots VALUES (?, ?, ?, ?)",
        strategy_rows,
    )

    start = date(2020, 1, 1)
    cutoff_binding_id = "binding-before"
    cutoff_date = (start - timedelta(days=1)).isoformat()
    cutoff_draw_number = "99999999"
    connection.execute(
        "INSERT INTO research_draw_bindings VALUES (?, ?, ?)",
        (cutoff_binding_id, _sha(cutoff_binding_id), json.dumps(_numbers(0))),
    )
    for index in range(303):
        target_date = (start + timedelta(days=index)).isoformat()
        target_draw_number = str(100_000_000 + index)
        target_binding_id = f"binding-{index}"
        winning = _numbers(index * 3)
        connection.execute(
            "INSERT INTO research_draw_bindings VALUES (?, ?, ?)",
            (target_binding_id, _sha(target_binding_id), json.dumps(winning)),
        )
        for strategy_index, (snapshot_id, _, strategy_id, _) in enumerate(
            strategy_rows,
            start=1,
        ):
            target_id = f"target-{index}-{strategy_id}"
            ticket_id = f"ticket-{index}-{strategy_id}"
            ticket_numbers = _numbers(index + strategy_index * 7)
            hit_count = len(set(ticket_numbers) & set(winning))
            if index == 302 and strategy_id == "strategy-a":
                hit_count = 6
            connection.execute(
                "INSERT INTO research_prediction_targets "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    target_id,
                    run_id,
                    snapshot_id,
                    target_date,
                    target_draw_number,
                    1,
                    cutoff_date,
                    cutoff_draw_number,
                    "OK",
                    target_binding_id,
                    cutoff_binding_id,
                    1,
                ),
            )
            connection.execute(
                "INSERT INTO research_prediction_tickets VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    ticket_id,
                    target_id,
                    1,
                    json.dumps(ticket_numbers),
                    _sha(ticket_id),
                    None,
                    None,
                ),
            )
            connection.execute(
                "INSERT INTO research_ticket_results VALUES (?, ?, ?, ?, ?, ?)",
                (
                    f"result-{index}-{strategy_id}",
                    target_id,
                    ticket_id,
                    target_binding_id,
                    hit_count,
                    1,
                ),
            )
        cutoff_binding_id = target_binding_id
        cutoff_date = target_date
        cutoff_draw_number = target_draw_number
    connection.commit()
    connection.close()


def test_loader_excludes_post_discovery_labels_and_is_hash_pinned_read_only(
    tmp_path: Path,
) -> None:
    database = tmp_path / "research.db"
    _build_store(database)
    before = sha256_file(database)

    loaded = load_historical_replay_discovery_corpus(
        database,
        expected_database_sha256=before,
        source_run_id="synthetic-reference-run",
        partition=_partition(),
    )

    assert loaded.database_sha256 == before
    assert sha256_file(database) == before
    assert len(loaded.corpus.draws) == 302
    assert loaded.corpus.draws[-1].target == _partition().discovery_last_target
    assert loaded.corpus.profile.recomputed_hit_mismatch_count == 0
    assert loaded.corpus.profile.required_null_count == 0
    assert loaded.corpus.profile.bounded_result_row_count == 604
    assert loaded.corpus.profile.run_inventory[0].distinct_target_count == 303


def test_loader_fails_closed_on_a_discovery_label_mismatch(tmp_path: Path) -> None:
    database = tmp_path / "research.db"
    _build_store(database)
    connection = sqlite3.connect(database)
    connection.execute(
        "UPDATE research_ticket_results SET main_hit_count = 6 WHERE id = ?",
        ("result-301-strategy-a",),
    )
    connection.commit()
    connection.close()

    with pytest.raises(
        HistoricalReplayDiscoveryCorpusStorageError,
        match=r"stored main_hit_count does not recompute|stored results disagree",
    ):
        load_historical_replay_discovery_corpus(
            database,
            expected_database_sha256=sha256_file(database),
            source_run_id="synthetic-reference-run",
            partition=_partition(),
        )
