from __future__ import annotations

import json
import os
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from lottolab.application.use_cases.replay_backfill import BackfillSelection, ReplayBackfill
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import (
    ReplayBehavior,
    ReplayDraw,
    ReplayEvaluation,
    ReplayStrategy,
    ReplayTicket,
)
from lottolab.infrastructure.persistence.replay_backfill_store import SQLiteBackfillStore


class CountingProducer:
    strategy_id = "cross-version-guard"

    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    def get_bets(
        self, history: tuple[ReplayDraw, ...], lottery_type: LotteryType
    ) -> tuple[tuple[int, ...], ...]:
        self.calls += 1
        if self.fail:
            raise RuntimeError("synthetic generator failure")
        return ((1, 2, 3, 4, 5, 6), (1, 2, 3, 4, 5, 7))


class SyntheticAdapter:
    lottery_type = LotteryType.BIG_LOTTO

    def __init__(self, producer: CountingProducer) -> None:
        self._producer = producer

    def generate(
        self,
        strategy: ReplayStrategy,
        history: tuple[ReplayDraw, ...],
        target: ReplayDraw,
    ) -> tuple[ReplayTicket, ...]:
        return tuple(
            ReplayTicket(position, numbers, None)
            for position, numbers in enumerate(
                self._producer.get_bets(history, self.lottery_type),
                start=1,
            )
        )

    def evaluate(
        self, strategy: ReplayStrategy, ticket: ReplayTicket, target: ReplayDraw
    ) -> ReplayEvaluation:
        return ReplayEvaluation(0, False, False, None)


def _database_path(tmp_path: Path) -> Path:
    artifact_root = os.environ.get("MSA_ARTIFACT_ROOT")
    root = Path(artifact_root) / "synthetic-db" if artifact_root else tmp_path
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{uuid4().hex}.sqlite3"


def _draws() -> tuple[ReplayDraw, ...]:
    return tuple(
        ReplayDraw(
            LotteryType.BIG_LOTTO,
            str(100000001 + index),
            date(2024, 1, 1) + timedelta(days=index),
            (1, 2, 3, 4, 5, 6),
            7,
        )
        for index in range(4)
    )


def _worker(
    store: SQLiteBackfillStore,
    producer: CountingProducer,
    *,
    execution_version: str = "execution-v1",
    source_identity: str = "synthetic-dataset-v1",
    strategy_version: str = "strategy-v1",
) -> ReplayBackfill:
    strategy = ReplayStrategy(
        producer.strategy_id,
        "cross-version guard fixture",
        strategy_version,
        ReplayBehavior.DETERMINISTIC,
        2,
        2,
        fingerprint=f"fingerprint-{strategy_version}",
    )
    adapter = SyntheticAdapter(producer)
    return ReplayBackfill(
        adapter=adapter,
        strategies=(strategy,),
        draws=_draws(),
        source_identity=source_identity,
        store=store,
        execution_version=execution_version,
    )


def _snapshot(store: SQLiteBackfillStore) -> dict[str, tuple[tuple[object, ...], ...]]:
    uri = store.database.as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.execute("PRAGMA query_only=ON")
        tables = sorted(
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        )
        return {
            table: tuple(
                sorted(
                    connection.execute(f'SELECT * FROM "{table}"').fetchall(),
                    key=repr,
                )
            )
            for table in tables
        }


def _table_counts(snapshot: dict[str, tuple[tuple[object, ...], ...]]) -> dict[str, int]:
    return {table: len(rows) for table, rows in snapshot.items()}


def _cell_summary(snapshot: dict[str, tuple[tuple[object, ...], ...]]) -> list[dict[str, object]]:
    return [
        {
            "cell_identity": row[0],
            "execution_version": row[4],
            "dataset_identity": row[5],
            "execution_status": row[8],
            "result_identity": row[9],
            "attempts": row[11],
        }
        for row in snapshot.get("replay_backfill_cells", ())
    ]


def _seed_complete(
    store: SQLiteBackfillStore,
    *,
    execution_version: str = "execution-v1",
    source_identity: str = "synthetic-dataset-v1",
    strategy_version: str = "strategy-v1",
) -> tuple[ReplayBackfill, CountingProducer]:
    producer = CountingProducer()
    worker = _worker(
        store,
        producer,
        execution_version=execution_version,
        source_identity=source_identity,
        strategy_version=strategy_version,
    )
    result = worker.execute(BackfillSelection(latest=1))
    assert result["valid_result_cells"] == 1
    assert producer.calls == 1
    return worker, producer


def test_same_six_column_identity_resumes_without_generation(tmp_path: Path) -> None:
    store = SQLiteBackfillStore(_database_path(tmp_path))
    _seed_complete(store)
    before = _snapshot(store)
    resumed_producer = CountingProducer()
    resumed = _worker(store, resumed_producer)

    result = resumed.execute(BackfillSelection(latest=1))

    assert result["existing_skipped_count"] == 1
    assert result["newly_calculated_count"] == 0
    assert resumed_producer.calls == 0
    after = _snapshot(store)
    assert after == before
    print(
        "AC02_OBS "
        + json.dumps(
            {
                "generator_calls_on_resume": resumed_producer.calls,
                "table_counts_before": _table_counts(before),
                "table_counts_after": _table_counts(after),
                "cells": _cell_summary(after),
            },
            sort_keys=True,
        )
    )


def test_cross_execution_complete_fails_before_prepare_or_generation(tmp_path: Path) -> None:
    store = SQLiteBackfillStore(_database_path(tmp_path))
    _seed_complete(store, execution_version="execution-old")
    before = _snapshot(store)
    new_producer = CountingProducer()
    new_worker = _worker(store, new_producer, execution_version="execution-new")
    requested_dataset = new_worker.dataset_identity

    with pytest.raises(ValueError) as raised:
        new_worker.execute(BackfillSelection(latest=1))

    message = str(raised.value)
    assert "COMPLETE replay identity conflict" in message
    assert "execution_version='execution-old'" in message
    assert "execution_version='execution-new'" in message
    assert f"dataset_identity='{requested_dataset}'" in message
    assert new_producer.calls == 0
    after = _snapshot(store)
    assert after == before
    print(
        "AC03_OBS "
        + json.dumps(
            {
                "error": message,
                "generator_calls": new_producer.calls,
                "table_counts_before": _table_counts(before),
                "table_counts_after": _table_counts(after),
                "cells_before": _cell_summary(before),
                "cells_after": _cell_summary(after),
            },
            sort_keys=True,
        )
    )


def test_cross_dataset_complete_fails_before_prepare_or_generation(tmp_path: Path) -> None:
    store = SQLiteBackfillStore(_database_path(tmp_path))
    old_worker, _ = _seed_complete(
        store,
        execution_version="execution-same",
        source_identity="synthetic-dataset-old",
    )
    before = _snapshot(store)
    new_producer = CountingProducer()
    new_worker = _worker(
        store,
        new_producer,
        execution_version="execution-same",
        source_identity="synthetic-dataset-new",
    )
    requested_dataset = new_worker.dataset_identity
    original_rows = before["replay_backfill_cells"]
    assert len(original_rows) == 1
    original_payload = json.loads(str(original_rows[0][-2]))
    original_identity = original_payload["result_identity"]

    with pytest.raises(ValueError) as raised:
        new_worker.execute(BackfillSelection(latest=1))

    message = str(raised.value)
    assert "execution_version='execution-same'" in message
    assert f"dataset_identity='{old_worker.dataset_identity}'" in message
    assert f"dataset_identity='{requested_dataset}'" in message
    assert new_producer.calls == 0
    after = _snapshot(store)
    assert after == before
    current_rows = after["replay_backfill_cells"]
    assert json.loads(str(current_rows[0][-2]))["result_identity"] == original_identity
    print(
        "AC04_OBS "
        + json.dumps(
            {
                "error": message,
                "generator_calls": new_producer.calls,
                "table_counts_before": _table_counts(before),
                "table_counts_after": _table_counts(after),
                "cells_before": _cell_summary(before),
                "cells_after": _cell_summary(after),
                "old_result_identity_preserved": original_identity,
            },
            sort_keys=True,
        )
    )


def test_failed_cells_keep_retry_failed_policy(tmp_path: Path) -> None:
    store = SQLiteBackfillStore(_database_path(tmp_path))
    producer = CountingProducer(fail=True)
    worker = _worker(store, producer)
    first = worker.execute(BackfillSelection(latest=1))
    assert first["failed_cells"] == 1
    assert producer.calls == 1
    failed_snapshot = _snapshot(store)

    producer.fail = False
    skipped = worker.execute(BackfillSelection(latest=1), retry_failed=False)
    assert skipped["existing_skipped_count"] == 1
    assert skipped["newly_calculated_count"] == 0
    assert producer.calls == 1
    assert _snapshot(store) == failed_snapshot

    retried = worker.execute(BackfillSelection(latest=1), retry_failed=True)
    assert retried["newly_calculated_count"] == 1
    assert retried["failed_cells"] == 0
    assert producer.calls == 2
    rows = _snapshot(store)["replay_backfill_cells"]
    assert len(rows) == 1
    assert rows[0][8] == "COMPLETE"
    assert rows[0][11] == 2
    print(
        "AC05_OBS "
        + json.dumps(
            {
                "generator_calls_after_failure_skip_and_retry": producer.calls,
                "failed_table_counts": _table_counts(failed_snapshot),
                "final_table_counts": _table_counts(_snapshot(store)),
                "final_cell": _cell_summary(_snapshot(store))[0],
                "retry_failed_false_new_calculated": skipped["newly_calculated_count"],
                "retry_failed_true_new_calculated": retried["newly_calculated_count"],
            },
            sort_keys=True,
        )
    )


def test_new_strategy_version_and_unseen_target_remain_runnable(tmp_path: Path) -> None:
    store = SQLiteBackfillStore(_database_path(tmp_path))
    _seed_complete(store, strategy_version="strategy-v1")
    new_strategy_producer = CountingProducer()
    new_strategy = _worker(
        store,
        new_strategy_producer,
        strategy_version="strategy-v2",
    )
    version_result = new_strategy.execute(BackfillSelection(latest=1))
    assert version_result["newly_calculated_count"] == 1
    assert new_strategy_producer.calls == 1

    unseen_target_producer = CountingProducer()
    unseen_target = _worker(store, unseen_target_producer)
    unseen_result = unseen_target.execute(
        BackfillSelection(start_date=date(2024, 1, 3), end_date=date(2024, 1, 3))
    )
    assert unseen_result["newly_calculated_count"] == 1
    assert unseen_target_producer.calls == 1
    print(
        "AC06_OBS "
        + json.dumps(
            {
                "new_strategy_version_generated": new_strategy_producer.calls,
                "unseen_target_generated": unseen_target_producer.calls,
                "final_table_counts": _table_counts(_snapshot(store)),
                "cells": _cell_summary(_snapshot(store)),
            },
            sort_keys=True,
        )
    )
