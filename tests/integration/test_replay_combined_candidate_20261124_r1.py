from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Protocol, cast

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lottolab.application.replay_strategy_inventory import load_replay_strategy_inventory
from lottolab.application.use_cases.replay_backfill import BackfillSelection, ReplayBackfill
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import (
    ReplayBehavior,
    ReplayDraw,
    ReplayEvaluation,
    ReplayStrategy,
    ReplayTicket,
)
from lottolab.domain.replay_strategy_inventory import (
    ReplayDataStatus,
    ReplayExecutionCapability,
)
from lottolab.infrastructure.persistence.replay_backfill_store import SQLiteBackfillStore
from lottolab.interfaces.api.replay_backfill import create_replay_backfill_router

_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "k30_multiseed_stage_sources.json"
)
_TICKET_NUMBERS = (1, 2, 3, 4, 5, 6)


class _JsonTestClient(Protocol):
    def get(self, url: str, **kwargs: object) -> httpx.Response: ...


class _ThirtyTicketAdapter:
    lottery_type = LotteryType.BIG_LOTTO

    def generate(
        self,
        strategy: ReplayStrategy,
        history: tuple[ReplayDraw, ...],
        target: ReplayDraw,
    ) -> tuple[ReplayTicket, ...]:
        del strategy, history, target
        return tuple(
            ReplayTicket(position, _TICKET_NUMBERS)
            for position in range(1, 31)
        )

    def evaluate(
        self,
        strategy: ReplayStrategy,
        ticket: ReplayTicket,
        target: ReplayDraw,
    ) -> ReplayEvaluation:
        del strategy, ticket, target
        return ReplayEvaluation(0, False, False, None)


def _seed_identity() -> tuple[str, str]:
    fixture = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    identities = cast(list[dict[str, object]], fixture["seed_identities"])
    first = identities[0]
    return cast(str, first["strategy_id"]), cast(str, first["strategy_version"])


def _draws() -> tuple[ReplayDraw, ...]:
    return tuple(
        ReplayDraw(
            LotteryType.BIG_LOTTO,
            str(100000001 + index),
            date(2024, 1, 1) + timedelta(days=index),
            _TICKET_NUMBERS,
            7,
        )
        for index in range(4)
    )


def _worker(
    store: SQLiteBackfillStore,
    *,
    execution_version: str,
    provenance: str,
) -> ReplayBackfill:
    strategy_id, strategy_version = _seed_identity()
    strategy = ReplayStrategy(
        strategy_id,
        "Synthetic K30 stage candidate",
        strategy_version,
        ReplayBehavior.DETERMINISTIC,
        30,
        1,
        fingerprint="combined-k30-fingerprint-v1",
    )
    return ReplayBackfill(
        adapter=_ThirtyTicketAdapter(),
        strategies=(strategy,),
        draws=_draws(),
        source_identity="synthetic://combined-k30-history",
        store=store,
        execution_version=execution_version,
        source_history_provenance_status=provenance,
    )


def _client(store: SQLiteBackfillStore) -> _JsonTestClient:
    app = FastAPI()
    app.include_router(create_replay_backfill_router(store))
    return cast(_JsonTestClient, TestClient(app))


def _api_item(client: _JsonTestClient, run_id: str) -> dict[str, object]:
    strategy_id, strategy_version = _seed_identity()
    response = client.get(
        "/api/v1/replay-backfill/strategies",
        params={
            "lottery_type": LotteryType.BIG_LOTTO.value,
            "run_id": run_id,
            "q": strategy_id,
        },
    )
    assert response.status_code == 200
    payload_value: object = response.json()
    assert isinstance(payload_value, dict)
    payload = cast(dict[str, object], payload_value)
    items = payload.get("items")
    assert isinstance(items, list)
    matched: list[dict[str, object]] = []
    for value in cast(list[object], items):
        if not isinstance(value, dict):
            continue
        item = cast(dict[str, object], value)
        if (
            item.get("strategy_id") == strategy_id
            and item.get("strategy_version") == strategy_version
        ):
            matched.append(item)
    assert len(matched) == 1
    return matched[0]


def test_combined_k30_identity_keeps_verified_provenance_out_of_history_status() -> None:
    strategy_id, strategy_version = _seed_identity()
    load_replay_strategy_inventory.cache_clear()
    inventory = load_replay_strategy_inventory()
    item = next(
        row
        for row in inventory.items
        if row.strategy_id == strategy_id and row.strategy_version == strategy_version
    )

    assert item.replay_data_status is ReplayDataStatus.NO_HISTORY
    assert item.historical_data_count == 0
    assert item.execution_capability is ReplayExecutionCapability.UNAVAILABLE
    assert item.backfill_runnable is False
    assert item.adapter_mapping is None
    assert item.backfill_native_binding is not True
    assert "VERIFIED" in item.source_statuses


def test_combined_k30_cell_reuse_keeps_thirty_tickets_and_run_scoped_api_counts(
    tmp_path: Path,
) -> None:
    database = tmp_path / "combined-k30.sqlite3"
    store = SQLiteBackfillStore(database)
    worker = _worker(
        store,
        execution_version="combined-execution-v1",
        provenance="UNKNOWN",
    )
    last_draw_date = worker.draws[-1].draw_date
    first_selection = BackfillSelection(start_date=last_draw_date, end_date=last_draw_date)
    second_selection = BackfillSelection(latest=1)

    first = worker.execute(first_selection)
    second = worker.execute(second_selection)
    first_run_id = cast(str, first["run_id"])
    second_run_id = cast(str, second["run_id"])
    assert first_run_id != second_run_id
    assert first["newly_calculated_count"] == 1
    assert second["newly_calculated_count"] == 0
    assert second["existing_skipped_count"] == 1

    client = _client(store)
    for run_id in (first_run_id, second_run_id):
        item = _api_item(client, run_id)
        counts_value = item.get("history_counts")
        assert isinstance(counts_value, dict)
        counts = cast(dict[str, object], counts_value)
        assert counts.get("persisted_cell_count") == 1
        assert counts.get("saved_prediction_cell_count") == 1
        assert counts.get("saved_ticket_count") == 30
        statuses_value = counts.get("execution_status_counts")
        assert isinstance(statuses_value, dict)
        statuses = cast(dict[str, int], statuses_value)
        assert {
            status: count
            for status, count in statuses.items()
            if count
        } == {"COMPLETE": 1}

    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
        connection.execute("PRAGMA query_only=ON")
        cell_count = connection.execute(
            "SELECT COUNT(*) FROM replay_backfill_cells WHERE lottery_type=? AND strategy_id=? "
            "AND strategy_version=? AND execution_version=? AND dataset_identity=?",
            (
                LotteryType.BIG_LOTTO.value,
                worker.strategies[0].strategy_id,
                worker.strategies[0].strategy_version,
                worker.execution_version,
                worker.dataset_identity,
            ),
        ).fetchone()
        assert cell_count == (1,)
        cell_identity = connection.execute(
            "SELECT cell_identity FROM replay_backfill_cells "
            "WHERE lottery_type=? AND strategy_id=? "
            "AND strategy_version=? AND execution_version=? AND dataset_identity=?",
            (
                LotteryType.BIG_LOTTO.value,
                worker.strategies[0].strategy_id,
                worker.strategies[0].strategy_version,
                worker.execution_version,
                worker.dataset_identity,
            ),
        ).fetchone()
        assert cell_identity is not None
        cell_id = cast(str, cell_identity[0])
        run_reference_count = connection.execute(
            "SELECT COUNT(*) FROM replay_backfill_run_cells WHERE cell_identity=?",
            (cell_id,),
        ).fetchone()
        assert run_reference_count == (2,)
        ticket_truth: dict[str, tuple[int, int, int, int]] = {}
        for run_id in (first_run_id, second_run_id):
            row = connection.execute(
                "SELECT COUNT(DISTINCT c.cell_identity),COUNT(t.ticket_position),"
                "MIN(t.ticket_position),MAX(t.ticket_position) "
                "FROM replay_backfill_cells c "
                "JOIN replay_backfill_run_cells r USING(cell_identity) "
                "LEFT JOIN replay_backfill_tickets t USING(cell_identity) "
                "WHERE r.run_id=? AND c.cell_identity=?",
                (run_id, cell_id),
            ).fetchone()
            assert row is not None
            ticket_truth[run_id] = cast(tuple[int, int, int, int], row)
        assert ticket_truth == {
            first_run_id: (1, 30, 1, 30),
            second_run_id: (1, 30, 1, 30),
        }
        payload_row = connection.execute(
            "SELECT payload_json FROM replay_backfill_cells WHERE cell_identity=?",
            (cell_id,),
        ).fetchone()
        assert payload_row is not None
        payload = json.loads(cast(str, payload_row[0]))
        assert payload["source_history_provenance_status"] == "UNKNOWN"
        assert [ticket["ticket_position"] for ticket in payload["predicted_tickets"]] == list(
            range(1, 31)
        )


def test_combined_empty_wrong_scope_and_unverified_source_do_not_claim_history(
    tmp_path: Path,
) -> None:
    database = tmp_path / "combined-empty-and-unverified.sqlite3"
    store = SQLiteBackfillStore(database)
    strategy_id, strategy_version = _seed_identity()
    empty_worker = _worker(
        store,
        execution_version="combined-empty-execution-v1",
        provenance="UNKNOWN",
    )
    empty_manifest = empty_worker.manifest(BackfillSelection(latest=1))
    empty_run_id = cast(str, empty_manifest["run_id"])
    store.prepare(empty_manifest)

    snapshot = store.strategy_history_snapshot(
        LotteryType.BIG_LOTTO.value,
        run_id=empty_run_id,
    )
    source = snapshot.get("run_source")
    assert isinstance(source, dict)
    # Locator/hash identity is separate from historical-provenance status.
    # An empty run still has no result cell from which to claim replay history.
    assert snapshot.get("cell_status_counts") == []

    client = _client(store)
    empty_item = _api_item(client, empty_run_id)
    empty_counts_value = empty_item.get("history_counts")
    assert isinstance(empty_counts_value, dict)
    empty_counts = cast(dict[str, object], empty_counts_value)
    assert empty_counts.get("persisted_cell_count") == 0
    assert empty_counts.get("saved_ticket_count") == 0

    wrong_version = client.get(
        "/api/v1/replay-backfill/strategy-runs",
        params={
            "lottery_type": LotteryType.BIG_LOTTO.value,
            "strategy_id": strategy_id,
            "strategy_version": "wrong-version",
        },
    )
    assert wrong_version.status_code == 200
    wrong_version_payload_value: object = wrong_version.json()
    assert isinstance(wrong_version_payload_value, dict)
    wrong_version_payload = cast(dict[str, object], wrong_version_payload_value)
    assert wrong_version_payload.get("total_run_version_matches") == 0
    assert wrong_version_payload.get("items") == []

    wrong_lottery = client.get(
        "/api/v1/replay-backfill/strategies",
        params={
            "lottery_type": LotteryType.DAILY_539.value,
            "run_id": empty_run_id,
        },
    )
    assert wrong_lottery.status_code == 422
    assert wrong_lottery.json() == {"error_code": "INVALID_QUERY"}

    unverified_worker = _worker(
        store,
        execution_version="combined-unverified-execution-v1",
        provenance="UNVERIFIED",
    )
    unverified = unverified_worker.execute(BackfillSelection(latest=1))
    unverified_run_id = cast(str, unverified["run_id"])
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
        connection.execute("PRAGMA query_only=ON")
        row = connection.execute(
            "SELECT payload_json FROM replay_backfill_cells WHERE strategy_id=? "
            "AND strategy_version=? AND execution_version=?",
            (strategy_id, strategy_version, unverified_worker.execution_version),
        ).fetchone()
    assert row is not None
    payload = json.loads(cast(str, row[0]))
    assert payload["source_history_provenance_status"] == "UNVERIFIED"
    unverified_item = _api_item(client, unverified_run_id)
    unverified_counts_value = unverified_item.get("history_counts")
    assert isinstance(unverified_counts_value, dict)
    unverified_counts = cast(dict[str, object], unverified_counts_value)
    assert unverified_counts.get("persisted_cell_count") == 1
    assert unverified_counts.get("saved_ticket_count") == 30
