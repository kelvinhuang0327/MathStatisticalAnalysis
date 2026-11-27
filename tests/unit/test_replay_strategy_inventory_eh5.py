from __future__ import annotations

from dataclasses import replace
from typing import Any, Protocol, cast

import httpx
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
from lottolab.interfaces.api.replay_backfill import create_replay_backfill_router
from lottolab.interfaces.api.replay_strategy_inventory import (
    create_replay_strategy_inventory_router,
)

EH03_ID = "research_biglotto_eh03_k5_saved_portfolio_gate_v1"
EH06_ID = "research_biglotto_eh06_k5_event_kernel_gate_v1"
EH07_ID = "research_biglotto_eh07_k5_nvar_gate_v1"
EH11_ID = "research_biglotto_eh11_k5_saved_portfolio_gate_v1"
EH12_ID = "research_biglotto_eh12_k5_saved_portfolio_gate_v1"
VERSION = "v1.0.0"
TARGET_IDS = {EH03_ID, EH06_ID, EH07_ID, EH11_ID, EH12_ID}


class _JsonTestClient(Protocol):
    def get(self, url: str, *, params: dict[str, str] | None = None) -> httpx.Response: ...


def _target_inventory():
    inventory = load_replay_strategy_inventory()
    rows = tuple(item for item in inventory.items if item.strategy_id in TARGET_IDS)
    assert len(rows) == 5
    return replace(inventory, items=rows)


def _empty_snapshot() -> dict[str, Any]:
    return {
        "run_id": None,
        "created_at": "2026-11-26T00:00:00+00:00",
        "dataset_identity": "synthetic-empty-overlay",
        "execution_version": "synthetic-v1",
        "selection_rule": "LATEST_RUN_BY_CREATED_AT_PER_LOTTERY_TYPE",
        "run_source": {"identity_status": "UNKNOWN"},
        "strategy_inventory": [],
        "cell_status_counts": [],
    }


def _snapshot(
    *,
    rows: tuple[dict[str, Any], ...],
    cells: tuple[dict[str, Any], ...],
    identity_status: str = "UNVERIFIED",
) -> dict[str, Any]:
    return {
        "run_id": "synthetic-eh-overlay",
        "created_at": "2026-11-26T00:00:00+00:00",
        "dataset_identity": "synthetic-eh-overlay-dataset",
        "execution_version": "synthetic-v1",
        "selection_rule": "LATEST_RUN_BY_CREATED_AT_PER_LOTTERY_TYPE",
        "run_source": {
            "identity_status": identity_status,
            "source_identity": "synthetic-eh-research-artifact",
            "source_kind": "HISTORICAL_RESEARCH_ARTIFACT",
            "source_locator": "synthetic-eh-research-artifact",
            "source_hash": None,
            "artifact_only": False,
        },
        "strategy_inventory": list(rows),
        "cell_status_counts": list(cells),
    }


def _inventory_row(
    lottery_type: str,
    strategy_id: str,
    version: str,
    target_count: int,
) -> dict[str, Any]:
    return {
        "lottery_type": lottery_type,
        "strategy_id": strategy_id,
        "strategy_version": version,
        "data_status": "HAS_HISTORY",
        "source_kind": "HISTORICAL_RESEARCH_ARTIFACT",
        "source_identity": "synthetic-eh-research-artifact",
        "executable": False,
        "available_target_count": target_count,
        "training_status": "NOT_REQUIRED",
    }


def _complete_cells(
    lottery_type: str,
    strategy_id: str,
    version: str,
    cell_count: int,
) -> dict[str, Any]:
    return {
        "lottery_type": lottery_type,
        "strategy_id": strategy_id,
        "strategy_version": version,
        "execution_status": "COMPLETE",
        "cell_count": cell_count,
        "ticket_count": cell_count * 5,
        "saved_prediction_cell_count": cell_count,
    }


class _SyntheticReplayStore:
    def __init__(
        self,
        snapshots: dict[str, dict[str, Any]],
        stored_rows: tuple[dict[str, Any], ...] = (),
    ) -> None:
        self.snapshots = snapshots
        self.stored_rows = stored_rows

    def strategy_history_snapshot(
        self,
        lottery_type: str,
        *,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        del run_id
        return self.snapshots[lottery_type]

    def stored_strategy_inventory(self, lottery_type: str) -> list[dict[str, Any]]:
        return [row for row in self.stored_rows if row["lottery_type"] == lottery_type]


def _backfill_client(
    snapshots: dict[str, dict[str, Any]],
    stored_rows: tuple[dict[str, Any], ...] = (),
) -> _JsonTestClient:
    app = FastAPI()
    app.include_router(
        create_replay_backfill_router(_SyntheticReplayStore(snapshots, stored_rows))  # type: ignore[arg-type]
    )
    return cast(_JsonTestClient, TestClient(app))


def _response_json(response: httpx.Response) -> dict[str, Any]:
    return cast(dict[str, Any], response.json())


def test_exact_research_identities_are_registered_without_history_or_native_binding() -> None:
    inventory = _target_inventory()
    assert {(item.strategy_id, item.strategy_version) for item in inventory.items} == {
        (EH03_ID, VERSION),
        (EH06_ID, VERSION),
        (EH07_ID, VERSION),
        (EH11_ID, VERSION),
        (EH12_ID, VERSION),
    }
    for item in inventory.items:
        assert item.lottery_type is LotteryType.BIG_LOTTO
        assert item.source_kind == "HISTORICAL_RESEARCH_ARTIFACT"
        assert item.lifecycle_status is ReplayLifecycleStatus.UNREGISTERED_IDENTIFIED
        assert item.replay_data_status is ReplayDataStatus.NO_HISTORY
        assert item.historical_data_count == 0
        assert item.historical_execution_count == 0
        assert item.native_ticket_count == 5
        assert "K5" in item.display_name
        assert item.execution_capability is ReplayExecutionCapability.UNAVAILABLE
        assert item.adapter_mapping is None
        assert item.backfill_native_binding is False
        assert item.backfill_runnable is False
        assert {"RESEARCH_STRATEGY", "UNVERIFIED"}.issubset(item.source_statuses)
        assert not item.source_locator.startswith("/")


def test_inventory_api_returns_the_exact_identity_and_unavailable_state() -> None:
    app = FastAPI()
    app.include_router(create_replay_strategy_inventory_router(_target_inventory()))
    client: _JsonTestClient = cast(_JsonTestClient, TestClient(app))

    for strategy_id in sorted(TARGET_IDS):
        response = client.get(
            "/api/v1/replay-strategy-inventory",
            params={"lottery_type": "BIG_LOTTO", "strategy_id": strategy_id},
        )
        assert response.status_code == 200
        rows: list[dict[str, Any]] = _response_json(response)["strategies"]
        assert len(rows) == 1
        row = rows[0]
        assert (row["lottery_type"], row["strategy_id"], row["strategy_version"]) == (
            "BIG_LOTTO",
            strategy_id,
            VERSION,
        )
        assert row["source_kind"] == "HISTORICAL_RESEARCH_ARTIFACT"
        assert row["lifecycle_status"] == "UNREGISTERED_IDENTIFIED"
        assert row["replay_data_status"] == "NO_HISTORY"
        assert row["historical_data_count"] == 0
        assert row["historical_execution_count"] == 0
        assert row["native_ticket_count"] == 5
        assert row["execution_capability"] == "UNAVAILABLE"
        assert row["adapter_mapping"] is None
        assert row["backfill_native_binding"] is False
        assert row["backfill_runnable"] is False
        assert {"RESEARCH_STRATEGY", "UNVERIFIED"}.issubset(row["source_statuses"])


def test_backfill_api_without_matching_overlay_keeps_no_history() -> None:
    snapshots = {
        lottery: _empty_snapshot() for lottery in ("BIG_LOTTO", "DAILY_539", "POWER_LOTTO")
    }
    response = _backfill_client(snapshots).get(
        "/api/v1/replay-backfill/strategies",
        params={"q": "research_biglotto_eh"},
    )

    assert response.status_code == 200
    rows: list[dict[str, Any]] = [
        row for row in _response_json(response)["items"] if row["strategy_id"] in TARGET_IDS
    ]
    assert {(row["strategy_id"], row["strategy_version"]) for row in rows} == {
        (EH03_ID, VERSION),
        (EH06_ID, VERSION),
        (EH07_ID, VERSION),
        (EH11_ID, VERSION),
        (EH12_ID, VERSION),
    }
    for row in rows:
        assert row["data_status"] == "NO_HISTORY"
        assert row["inventory_data_status"] == "NO_HISTORY"
        assert row["history_status"] == "NO_HISTORY"
        assert row["history_counts"]["persisted_cell_count"] == 0
        assert row["executable"] is False
        assert row["backfill_native_binding"] is False
        assert row["backfill_runnable"] is False
        assert row["native_ticket_count"] == 5


def test_backfill_api_overlays_only_exact_lottery_id_and_version() -> None:
    counts_by_identity = {
        EH03_ID: 2,
        EH06_ID: 3,
        EH07_ID: 4,
        EH11_ID: 5,
        EH12_ID: 6,
    }
    wrong_version = "v2.0.0"
    near_id = EH03_ID + "_near"
    rows = (
        *(
            _inventory_row("BIG_LOTTO", strategy_id, VERSION, count)
            for strategy_id, count in counts_by_identity.items()
        ),
        _inventory_row("BIG_LOTTO", EH03_ID, wrong_version, 97),
        _inventory_row("BIG_LOTTO", near_id, VERSION, 89),
    )
    cells = (
        *(
            _complete_cells("BIG_LOTTO", strategy_id, VERSION, count)
            for strategy_id, count in counts_by_identity.items()
        ),
        _complete_cells("BIG_LOTTO", EH03_ID, wrong_version, 97),
        _complete_cells("BIG_LOTTO", near_id, VERSION, 89),
    )
    response = _backfill_client(
        {
            "BIG_LOTTO": _snapshot(rows=rows, cells=cells),
            "DAILY_539": _empty_snapshot(),
            "POWER_LOTTO": _empty_snapshot(),
        }
    ).get(
        "/api/v1/replay-backfill/strategies",
        params={"q": "research_biglotto_eh"},
    )

    assert response.status_code == 200
    items: dict[str, dict[str, Any]] = {
        row["strategy_id"]: row
        for row in _response_json(response)["items"]
        if row["strategy_id"] in TARGET_IDS
    }
    assert set(items) == TARGET_IDS
    for strategy_id, expected_cells in counts_by_identity.items():
        item = items[strategy_id]
        assert item["strategy_version"] == VERSION
        assert item["inventory_data_status"] == "NO_HISTORY"
        assert item["data_status"] == "HAS_HISTORY"
        assert item["history_status"] == "HAS_HISTORY"
        assert item["history_source_identity_status"] == "UNVERIFIED"
        assert item["history_counts"]["persisted_cell_count"] == expected_cells
        assert item["history_counts"]["saved_prediction_cell_count"] == expected_cells
        assert item["history_counts"]["saved_ticket_count"] == expected_cells * 5
        assert item["native_ticket_count"] == 5
        assert item["executable"] is False
        assert item["backfill_native_binding"] is False
        assert item["backfill_runnable"] is False


def test_backfill_api_does_not_cross_lottery_for_the_same_identity() -> None:
    power_row = {
        **_inventory_row("POWER_LOTTO", EH03_ID, VERSION, 11),
        "lifecycle_status": "UNREGISTERED_IDENTIFIED",
        "display_name": "Synthetic other-lottery identity",
    }
    snapshots = {
        "BIG_LOTTO": _empty_snapshot(),
        "DAILY_539": _empty_snapshot(),
        "POWER_LOTTO": _snapshot(
            rows=(_inventory_row("POWER_LOTTO", EH03_ID, VERSION, 11),),
            cells=(_complete_cells("POWER_LOTTO", EH03_ID, VERSION, 11),),
        ),
    }
    response = _backfill_client(snapshots, stored_rows=(power_row,)).get(
        "/api/v1/replay-backfill/strategies",
        params={"q": EH03_ID},
    )

    assert response.status_code == 200
    rows = [
        row
        for row in _response_json(response)["items"]
        if row["lottery_type"] == "BIG_LOTTO" and row["strategy_id"] == EH03_ID
    ]
    assert len(rows) == 1
    assert rows[0]["strategy_version"] == VERSION
    assert rows[0]["data_status"] == "NO_HISTORY"
    assert rows[0]["history_status"] == "NO_HISTORY"
    assert rows[0]["history_counts"]["persisted_cell_count"] == 0


def test_inventory_api_keeps_lottery_id_and_version_as_distinct_identity_keys() -> None:
    inventory = _target_inventory()
    eh03 = next(item for item in inventory.items if item.strategy_id == EH03_ID)
    variants = (
        eh03,
        replace(eh03, strategy_version="v2.0.0"),
        replace(eh03, strategy_id=EH03_ID + "_near"),
        replace(eh03, lottery_type=LotteryType.POWER_LOTTO),
    )
    app = FastAPI()
    app.include_router(create_replay_strategy_inventory_router(replace(inventory, items=variants)))
    client: _JsonTestClient = cast(_JsonTestClient, TestClient(app))

    response = client.get(
        "/api/v1/replay-strategy-inventory",
        params={"strategy_id": EH03_ID},
    )

    assert response.status_code == 200
    rows: list[dict[str, Any]] = _response_json(response)["strategies"]
    assert {(row["lottery_type"], row["strategy_id"], row["strategy_version"]) for row in rows} == {
        ("BIG_LOTTO", EH03_ID, VERSION),
        ("BIG_LOTTO", EH03_ID, "v2.0.0"),
        ("POWER_LOTTO", EH03_ID, VERSION),
    }

    near_response = client.get(
        "/api/v1/replay-strategy-inventory",
        params={"strategy_id": EH03_ID + "_near"},
    )

    assert near_response.status_code == 200
    near_rows: list[dict[str, Any]] = _response_json(near_response)["strategies"]
    assert [
        (row["lottery_type"], row["strategy_id"], row["strategy_version"]) for row in near_rows
    ] == [("BIG_LOTTO", EH03_ID + "_near", VERSION)]

    with pytest.raises(ValueError, match="duplicate lottery/id/version identity"):
        replace(inventory, items=(*variants, eh03))
