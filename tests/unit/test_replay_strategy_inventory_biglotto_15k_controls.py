from __future__ import annotations

from typing import Any, Protocol, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lottolab.application.replay_strategy_inventory import load_replay_strategy_inventory
from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_strategy_inventory import (
    ReplayDataStatus,
    ReplayExecutionCapability,
    ReplayLifecycleStatus,
)
from lottolab.infrastructure.persistence.replay_backfill_store import SQLiteBackfillStore
from lottolab.interfaces.api.replay_backfill import create_replay_backfill_router

KS = (1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 25, 40, 54)
PREFIX = "research_biglotto__historical_random_k"
VERSION = "v1.0.0"
SOURCE = "replay-backfill:NUMBER2_B_BIGLOTTO_15K_RANDOM_CONTROL_50_20261119_R1"


def _strategy_id(k: int) -> str:
    return f"{PREFIX}{k}_20261119_r1"


def _snapshot(k: int, run_id: str, version: str = VERSION) -> dict[str, Any]:
    strategy_id = _strategy_id(k)
    row = {
        "lottery_type": "BIG_LOTTO",
        "strategy_id": strategy_id,
        "strategy_version": version,
        "data_status": "HAS_HISTORY",
        "source_kind": "REPLAY_BACKFILL_IMPORTED_RESULT",
        "source_identity": f"synthetic-source-{k}",
        "executable": False,
        "available_target_count": 50,
        "training_status": "NOT_TRAINABLE",
    }
    return {
        "run_id": run_id,
        "selection_rule": "EXPLICIT_RUN_ID",
        "target_count": 50,
        "run_source": {"identity_status": "VERIFIED"},
        "strategy_inventory": [row],
        "selected_strategies": [row],
        "cell_status_counts": [
            {
                "lottery_type": "BIG_LOTTO",
                "strategy_id": strategy_id,
                "strategy_version": version,
                "execution_status": "COMPLETE",
                "cell_count": 50,
                "ticket_count": 50 * k,
                "saved_prediction_cell_count": 50,
            }
        ],
    }


class _SyntheticStore:
    def __init__(self, snapshots: dict[str, dict[str, Any]], latest: str) -> None:
        self.snapshots = snapshots
        self.latest = latest

    def strategy_history_snapshot(
        self, lottery_type: str, *, run_id: str | None = None
    ) -> dict[str, Any]:
        if lottery_type != "BIG_LOTTO":
            raise ValueError("unexpected lottery")
        selected = self.latest if run_id is None else run_id
        if selected not in self.snapshots:
            raise KeyError(selected)
        result = dict(self.snapshots[selected])
        result["selection_rule"] = (
            "LATEST_RUN_BY_CREATED_AT_PER_LOTTERY_TYPE" if run_id is None else "EXPLICIT_RUN_ID"
        )
        return result


class _JsonResponse(Protocol):
    status_code: int

    def json(self) -> dict[str, Any]: ...


class _JsonTestClient(Protocol):
    def get(self, url: str, *, params: Any = None) -> _JsonResponse: ...


def _client(snapshots: dict[str, dict[str, Any]], latest: str) -> _JsonTestClient:
    app = FastAPI()
    store = cast(SQLiteBackfillStore, _SyntheticStore(snapshots, latest))
    app.include_router(create_replay_backfill_router(store))
    return cast(_JsonTestClient, TestClient(app))


def _get_item(client: _JsonTestClient, k: int, *, run_id: str | None = None) -> dict[str, Any]:
    params = {"lottery_type": "BIG_LOTTO", "q": _strategy_id(k)}
    if run_id is not None:
        params["run_id"] = run_id
    response = client.get("/api/v1/replay-backfill/strategies", params=params)
    assert response.status_code == 200
    body = response.json()
    assert body["total_count"] == 1
    return cast(dict[str, Any], body["items"][0])


def test_inventory_exactly_fifteen_fixed_random_controls() -> None:
    inventory = load_replay_strategy_inventory()
    matched = [
        item
        for item in inventory.items
        if item.lottery_type is LotteryType.BIG_LOTTO and item.strategy_id.startswith(PREFIX)
    ]
    assert len(matched) == 15
    assert {item.strategy_id for item in matched} == {_strategy_id(k) for k in KS}
    assert all(item.strategy_version == VERSION for item in matched)
    assert all(
        item.lifecycle_status is ReplayLifecycleStatus.UNREGISTERED_IDENTIFIED for item in matched
    )
    assert all(item.replay_data_status is ReplayDataStatus.NO_HISTORY for item in matched)
    assert all(
        item.execution_capability is ReplayExecutionCapability.UNAVAILABLE for item in matched
    )
    assert all(item.source_statuses == ("CONTROL_BASELINE",) for item in matched)
    assert all(item.source_locator == SOURCE for item in matched)
    assert all(item.adapter_mapping is None and not item.backfill_runnable for item in matched)
    assert all(not item.backfill_native_binding for item in matched)
    assert all("not a future recommendation" in item.reconstruction_reason for item in matched)

    # Existing historical identities and controls must remain distinct.
    existing = {item.strategy_id for item in inventory.items}
    assert "evolution_h12_k30_matched_random_completion" in existing
    assert "research_biglotto__k9_optimal_coverage_candidate" in existing


@pytest.mark.parametrize("k", KS)
def test_explicit_run_overlays_only_its_own_fifty_cells(k: int) -> None:
    run_id = f"synthetic-run-{k}"
    client = _client({run_id: _snapshot(k, run_id)}, run_id)
    item = _get_item(client, k, run_id=run_id)
    assert item["strategy_id"] == _strategy_id(k)
    assert item["strategy_version"] == VERSION
    assert item["history_scope"] == "EXPLICIT_RUN_ID"
    assert item["history_run_id"] == run_id
    assert item["history_status"] == "HAS_HISTORY"
    assert item["history_counts"]["persisted_cell_count"] == 50
    assert item["history_counts"]["saved_ticket_count"] == 50 * k
    assert item["available_target_count"] == 50
    assert item["executable"] is False
    assert item["backfill_runnable"] is False


def test_wrong_run_does_not_mix_history_and_default_stays_latest() -> None:
    client = _client({"run-1": _snapshot(1, "run-1"), "run-2": _snapshot(2, "run-2")}, "run-2")
    wrong_run = _get_item(client, 1, run_id="run-2")
    assert wrong_run["history_scope"] == "EXPLICIT_RUN_ID"
    assert wrong_run["history_status"] == "NOT_SELECTED_IN_RUN"
    assert wrong_run["history_counts"]["persisted_cell_count"] == 0
    default = _get_item(client, 1)
    assert default["history_scope"] == "LATEST_RUN_BY_CREATED_AT_PER_LOTTERY_TYPE"
    assert default["history_run_id"] == "run-2"
    assert default["history_counts"]["persisted_cell_count"] == 0
    assert _get_item(client, 2)["history_counts"]["persisted_cell_count"] == 50


def test_wrong_strategy_version_does_not_attach_history() -> None:
    client = _client({"wrong-version": _snapshot(1, "wrong-version", "v1.0.1")}, "wrong-version")
    item = _get_item(client, 1, run_id="wrong-version")
    assert item["strategy_version"] == VERSION
    assert item["data_status"] == "NO_HISTORY"
    assert item["history_status"] == "NOT_SELECTED_IN_RUN"
    assert item["history_counts"]["persisted_cell_count"] == 0
