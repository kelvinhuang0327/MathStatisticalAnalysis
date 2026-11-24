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

K30_GEOMETRY_ID = "evolution_h12_k30_geometry_completion"
K30_RANDOM_ID = "evolution_h12_k30_matched_random_completion"
K30_EXACT_SWAP_ID = "research_biglotto__k30_geometry_exact_swap_history_v1"
K30_VERSION = "v0.1"
K30_FIXED_CONTROL_ID = "research_biglotto__k30_fixed_random_control_20261119_r1"
K30_FIXED_CONTROL_VERSION = "v1.0.0"
K9_ID = "research_biglotto__k9_optimal_coverage_candidate"
K9_VERSION = "v0.1-research"

ERA_CANDIDATES = {
    "research_biglotto__k30_fixed_414665013": ("v1", "RESEARCH_STRATEGY"),
    "research_biglotto__k30_fixed_414671103": ("v1", "RESEARCH_STRATEGY"),
    "research_biglotto__k30_fixed_random_control_20261119_r1": ("v1.0.0", "CONTROL_BASELINE"),
}


class _JsonResponse(Protocol):
    status_code: int

    def json(self) -> dict[str, Any]: ...


class _JsonTestClient(Protocol):
    def get(self, url: str, *, params: Any = None) -> _JsonResponse: ...


def _json_client(app: Any) -> _JsonTestClient:
    return cast(_JsonTestClient, TestClient(app))


def _snapshot(
    *,
    run_id: str | None = "synthetic-k30-overlay",
    rows: tuple[dict[str, Any], ...] = (),
    cells: tuple[dict[str, Any], ...] = (),
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "created_at": "2026-11-10T00:00:00+00:00",
        "dataset_identity": "synthetic-k30-overlay-dataset",
        "execution_version": "synthetic-v1",
        "selection_rule": "LATEST_RUN_BY_CREATED_AT_PER_LOTTERY_TYPE",
        "run_source": {
            "identity_status": "UNKNOWN",
            "source_identity": "k30_stage_synthetic",
            "source_kind": "REPLAY_BACKFILL_IMPORTED_RESULT",
            "source_locator": "k30_stage_synthetic",
            "source_hash": None,
            "artifact_only": False,
        },
        "strategy_inventory": list(rows),
        "cell_status_counts": list(cells),
    }


class SyntheticReplayStore:
    def __init__(self, snapshots: dict[str, dict[str, Any]]) -> None:
        self.snapshots = snapshots

    def strategy_history_snapshot(
        self, lottery_type: str, *, run_id: str | None = None
    ) -> dict[str, Any]:
        return self.snapshots[lottery_type]


def _client(snapshots: dict[str, dict[str, Any]]) -> _JsonTestClient:
    app = FastAPI()
    # The inventory endpoint exercised here only uses strategy_history_snapshot.
    store = cast(SQLiteBackfillStore, SyntheticReplayStore(snapshots))
    app.include_router(create_replay_backfill_router(store))
    return _json_client(app)


def _inventory_row(
    *,
    lottery_type: str,
    strategy_id: str,
    version: str,
    target_count: int = 730,
) -> dict[str, Any]:
    return {
        "lottery_type": lottery_type,
        "strategy_id": strategy_id,
        "strategy_version": version,
        "data_status": "HAS_HISTORY",
        "source_kind": "REPLAY_BACKFILL_IMPORTED_RESULT",
        "source_identity": f"synthetic-{strategy_id}",
        "executable": False,
        "available_target_count": target_count,
        "training_status": "NOT_TRAINABLE",
    }


def _complete_cells(
    *,
    lottery_type: str,
    strategy_id: str,
    version: str,
    cell_count: int = 730,
    ticket_count: int = 21900,
) -> dict[str, Any]:
    return {
        "lottery_type": lottery_type,
        "strategy_id": strategy_id,
        "strategy_version": version,
        "execution_status": "COMPLETE",
        "cell_count": cell_count,
        "ticket_count": ticket_count,
        "saved_prediction_cell_count": cell_count,
    }


def test_k30_era_candidates_are_unique_unavailable_and_keep_old_versions() -> None:
    items = load_replay_strategy_inventory().items
    for strategy_id, (old_version, role) in ERA_CANDIDATES.items():
        rows = [
            item
            for item in items
            if item.lottery_type is LotteryType.BIG_LOTTO and item.strategy_id == strategy_id
        ]
        assert {item.strategy_version for item in rows} == {old_version, "v1-era2014"}
        assert len(rows) == 2
        item = next(item for item in rows if item.strategy_version == "v1-era2014")
        assert item.source_kind == "REPLAY_BACKFILL_STAGE_CANDIDATE"
        assert item.source_statuses == (role, "UNKNOWN")
        assert item.alias_or_identity_mapping[0].source_status == "UNKNOWN"
        assert "source_history_provenance_status=UNKNOWN" in item.source_locator
        assert item.replay_data_status is ReplayDataStatus.NO_HISTORY
        assert item.execution_capability is ReplayExecutionCapability.UNAVAILABLE
        assert item.adapter_mapping is None
        assert not item.backfill_native_binding
        assert not item.backfill_runnable


def test_k30_era_candidates_backfill_projection_has_no_invented_history() -> None:
    client = _client(
        {lottery: _snapshot(run_id=None) for lottery in ("BIG_LOTTO", "DAILY_539", "POWER_LOTTO")}
    )
    for strategy_id in ERA_CANDIDATES:
        response = client.get(
            "/api/v1/replay-backfill/strategies",
            params={"lottery_type": "BIG_LOTTO", "q": strategy_id},
        )
        assert response.status_code == 200
        rows = [
            row
            for row in response.json()["items"]
            if row["strategy_id"] == strategy_id and row["strategy_version"] == "v1-era2014"
        ]
        assert len(rows) == 1
        row = rows[0]
        assert row["data_status"] == row["inventory_data_status"] == "NO_HISTORY"
        assert row["available_target_count"] == 0
        assert not row["executable"]
        assert not row["backfill_native_binding"]
        assert not row["backfill_runnable"]


def test_k9_inventory_identity_and_history_overlay() -> None:
    matches = [
        item
        for item in load_replay_strategy_inventory().items
        if item.lottery_type is LotteryType.BIG_LOTTO
        and item.strategy_id == K9_ID
        and item.strategy_version == K9_VERSION
    ]
    assert len(matches) == 1
    item = matches[0]
    assert item.execution_capability is ReplayExecutionCapability.UNAVAILABLE
    assert item.adapter_mapping is None
    assert item.backfill_runnable is False
    assert item.source_statuses == ("RESEARCH_STRATEGY",)

    snapshot = _snapshot(
        rows=(
            _inventory_row(
                lottery_type="BIG_LOTTO", strategy_id=K9_ID, version=K9_VERSION, target_count=2183
            ),
        ),
        cells=(
            _complete_cells(
                lottery_type="BIG_LOTTO",
                strategy_id=K9_ID,
                version=K9_VERSION,
                cell_count=2183,
                ticket_count=19647,
            ),
        ),
    )
    client = _client({"BIG_LOTTO": snapshot, "DAILY_539": _snapshot(), "POWER_LOTTO": _snapshot()})
    response = client.get(
        "/api/v1/replay-backfill/strategies", params={"lottery_type": "BIG_LOTTO", "q": K9_ID}
    )
    assert response.status_code == 200
    assert response.json()["total_count"] == 1
    result = response.json()["items"][0]
    assert result["strategy_version"] == K9_VERSION
    assert result["data_status"] == "HAS_HISTORY"
    assert result["available_target_count"] == 2183
    assert result["executable"] is False
    assert result["backfill_runnable"] is False


def test_fixed_random_control_is_history_only_and_overlay_requires_exact_version() -> None:
    matches = [
        item
        for item in load_replay_strategy_inventory().items
        if item.lottery_type is LotteryType.BIG_LOTTO
        and item.strategy_id == K30_FIXED_CONTROL_ID
        and item.strategy_version == K30_FIXED_CONTROL_VERSION
    ]
    assert len(matches) == 1
    item = matches[0]
    assert item.source_statuses == ("CONTROL_BASELINE",)
    assert item.replay_data_status is ReplayDataStatus.NO_HISTORY
    assert item.execution_capability is ReplayExecutionCapability.UNAVAILABLE
    assert item.adapter_mapping is None
    assert item.backfill_runnable is False

    snapshot = _snapshot(
        rows=(
            _inventory_row(
                lottery_type="BIG_LOTTO",
                strategy_id=K30_FIXED_CONTROL_ID,
                version=K30_FIXED_CONTROL_VERSION,
                target_count=2188,
            ),
        ),
        cells=(
            _complete_cells(
                lottery_type="BIG_LOTTO",
                strategy_id=K30_FIXED_CONTROL_ID,
                version=K30_FIXED_CONTROL_VERSION,
                cell_count=2188,
                ticket_count=65640,
            ),
        ),
    )
    # The real Store recorded the original replay producer as REBUILDABLE,
    # despite there being no executable binding in the current inventory.
    snapshot["strategy_inventory"][0]["data_status"] = "REBUILDABLE"
    client = _client({"BIG_LOTTO": snapshot, "DAILY_539": _snapshot(), "POWER_LOTTO": _snapshot()})
    response = client.get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "BIG_LOTTO", "q": K30_FIXED_CONTROL_ID},
    )
    assert response.status_code == 200
    assert response.json()["total_count"] == 2
    result = next(row for row in response.json()["items"]
                  if row["strategy_version"] == K30_FIXED_CONTROL_VERSION)
    assert result["strategy_version"] == K30_FIXED_CONTROL_VERSION
    assert result["data_status"] == "HAS_HISTORY"
    assert result["available_target_count"] == 2188
    assert result["executable"] is False
    assert result["backfill_runnable"] is False
    assert result["history_status"] == "HAS_HISTORY"
    filtered = client.get(
        "/api/v1/replay-backfill/strategies",
        params={
            "lottery_type": "BIG_LOTTO",
            "q": K30_FIXED_CONTROL_ID,
            "data_status": "HAS_HISTORY",
        },
    )
    assert filtered.json()["total_count"] == 1

    snapshot["cell_status_counts"] = []
    without_saved_cells = client.get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "BIG_LOTTO", "q": K30_FIXED_CONTROL_ID},
    )
    original = next(row for row in without_saved_cells.json()["items"]
                    if row["strategy_version"] == K30_FIXED_CONTROL_VERSION)
    assert original["data_status"] == "REBUILDABLE"
    assert original["history_status"] != "HAS_HISTORY"

    other_version = _snapshot(
        rows=(
            _inventory_row(
                lottery_type="BIG_LOTTO", strategy_id=K30_FIXED_CONTROL_ID, version="v2"
            ),
        ),
        cells=(
            _complete_cells(
                lottery_type="BIG_LOTTO", strategy_id=K30_FIXED_CONTROL_ID, version="v2"
            ),
        ),
    )
    client = _client(
        {"BIG_LOTTO": other_version, "DAILY_539": _snapshot(), "POWER_LOTTO": _snapshot()}
    )
    response = client.get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "BIG_LOTTO", "q": K30_FIXED_CONTROL_ID},
    )
    exact = next(
        result
        for result in response.json()["items"]
        if result["strategy_version"] == K30_FIXED_CONTROL_VERSION
    )
    assert exact["data_status"] == "NO_HISTORY"
    assert exact["available_target_count"] == 0


@pytest.mark.parametrize(
    ("strategy_id", "version", "count"),
    [
        ("legacy_biglotto__test_ecp__c9d5ac6decdd", "v0.2", 1),
        ("legacy_biglotto__biglotto_3bet_optimizer__2835d6cb20c5", "v0.2", 1),
        ("research_biglotto__radical_gap_complete_v2", "v2", 83),
    ],
)
def test_saved_research_history_does_not_claim_unavailable_rebuild(
    strategy_id: str, version: str, count: int
) -> None:
    row = _inventory_row(
        lottery_type="BIG_LOTTO", strategy_id=strategy_id, version=version, target_count=count
    )
    row["data_status"] = "REBUILDABLE"
    snapshot = _snapshot(
        rows=(row,),
        cells=(
            _complete_cells(
                lottery_type="BIG_LOTTO", strategy_id=strategy_id, version=version, cell_count=count
            ),
        ),
    )
    client = _client({"BIG_LOTTO": snapshot, "DAILY_539": _snapshot(), "POWER_LOTTO": _snapshot()})
    response = client.get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "BIG_LOTTO", "q": strategy_id, "data_status": "HAS_HISTORY"},
    )
    assert response.status_code == 200
    row_result = next(row for row in response.json()["items"] if row["strategy_version"] == version)
    assert row_result["history_status"] == "HAS_HISTORY"
    assert row_result["available_target_count"] == count
    assert row_result["executable"] is False
    assert row_result["backfill_runnable"] is False

    snapshot["cell_status_counts"] = []
    missing = client.get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "BIG_LOTTO", "q": strategy_id},
    )
    same_version = next(
        row for row in missing.json()["items"] if row["strategy_version"] == version
    )
    assert same_version["data_status"] == "REBUILDABLE"
    assert same_version["history_status"] != "HAS_HISTORY"


def test_static_inventory_registers_both_k30_identities() -> None:
    inv = load_replay_strategy_inventory()
    items = {
        (item.lottery_type, item.strategy_id, item.strategy_version): item for item in inv.items
    }

    geo_key = (LotteryType.BIG_LOTTO, K30_GEOMETRY_ID, K30_VERSION)
    rand_key = (LotteryType.BIG_LOTTO, K30_RANDOM_ID, K30_VERSION)
    exact_swap_key = (LotteryType.BIG_LOTTO, K30_EXACT_SWAP_ID, "v1")

    assert geo_key in items, "Geometry identity missing from inventory"
    assert rand_key in items, "Matched random control identity missing from inventory"
    assert exact_swap_key in items, "Existing exact-swap identity must remain preserved"

    geo = items[geo_key]
    rand = items[rand_key]
    exact_swap = items[exact_swap_key]

    # AC5: exact swap research identity remains separate from K30 Geometry Completion
    assert exact_swap.strategy_id != geo.strategy_id
    assert exact_swap.strategy_version == "v1"
    assert exact_swap.lifecycle_status is ReplayLifecycleStatus.CODE_ONLY

    # Check Geometry role and execution attributes
    assert geo.display_name == "K30 Geometry (歷史研究策略)"
    assert geo.lifecycle_status is ReplayLifecycleStatus.UNREGISTERED_IDENTIFIED
    assert geo.replay_data_status is ReplayDataStatus.NO_HISTORY
    assert geo.execution_capability is ReplayExecutionCapability.UNAVAILABLE
    assert geo.adapter_mapping is None
    assert geo.backfill_native_binding is False
    assert geo.backfill_runnable is False
    assert geo.reconstructable is False
    assert geo.wrapper_callable is False
    assert geo.source_statuses == ("RESEARCH_STRATEGY",)

    # Check Matched Random control role and execution attributes
    assert rand.display_name == "K30 Matched Random (隨機補票對照組)"
    assert rand.lifecycle_status is ReplayLifecycleStatus.UNREGISTERED_IDENTIFIED
    assert rand.replay_data_status is ReplayDataStatus.NO_HISTORY
    assert rand.execution_capability is ReplayExecutionCapability.UNAVAILABLE
    assert rand.adapter_mapping is None
    assert rand.backfill_native_binding is False
    assert rand.backfill_runnable is False
    assert rand.reconstructable is False
    assert rand.wrapper_callable is False
    assert rand.source_statuses == ("CONTROL_BASELINE",)


def test_api_overlays_has_history_when_store_has_exact_k30_rows() -> None:
    big_lotto = _snapshot(
        rows=(
            _inventory_row(
                lottery_type="BIG_LOTTO",
                strategy_id=K30_GEOMETRY_ID,
                version=K30_VERSION,
                target_count=730,
            ),
            _inventory_row(
                lottery_type="BIG_LOTTO",
                strategy_id=K30_RANDOM_ID,
                version=K30_VERSION,
                target_count=730,
            ),
        ),
        cells=(
            _complete_cells(
                lottery_type="BIG_LOTTO",
                strategy_id=K30_GEOMETRY_ID,
                version=K30_VERSION,
                cell_count=730,
                ticket_count=21900,
            ),
            _complete_cells(
                lottery_type="BIG_LOTTO",
                strategy_id=K30_RANDOM_ID,
                version=K30_VERSION,
                cell_count=730,
                ticket_count=21900,
            ),
        ),
    )

    client = _client(
        {
            "BIG_LOTTO": big_lotto,
            "DAILY_539": _snapshot(),
            "POWER_LOTTO": _snapshot(),
        }
    )

    # Query Geometry
    resp_geo = client.get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "BIG_LOTTO", "q": K30_GEOMETRY_ID},
    )
    assert resp_geo.status_code == 200
    payload_geo = resp_geo.json()
    assert payload_geo["total_count"] == 1
    item_geo = payload_geo["items"][0]
    assert item_geo["lottery_type"] == "BIG_LOTTO"
    assert item_geo["strategy_id"] == K30_GEOMETRY_ID
    assert item_geo["strategy_version"] == K30_VERSION
    assert item_geo["display_name"] == "K30 Geometry (歷史研究策略)"
    assert item_geo["data_status"] == "HAS_HISTORY"
    assert item_geo["inventory_data_status"] == "NO_HISTORY"
    assert item_geo["history_status"] == "HAS_HISTORY"
    assert item_geo["history_source_identity_status"] == "UNKNOWN"
    assert "SOURCE_IDENTITY_UNKNOWN" in item_geo["history_statuses"]
    assert item_geo["available_target_count"] == 730
    assert item_geo["executable"] is False
    assert item_geo["backfill_native_binding"] is False
    assert item_geo["backfill_runnable"] is False

    # Query Matched Random
    resp_rand = client.get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "BIG_LOTTO", "q": K30_RANDOM_ID},
    )
    assert resp_rand.status_code == 200
    payload_rand = resp_rand.json()
    assert payload_rand["total_count"] == 1
    item_rand = payload_rand["items"][0]
    assert item_rand["lottery_type"] == "BIG_LOTTO"
    assert item_rand["strategy_id"] == K30_RANDOM_ID
    assert item_rand["strategy_version"] == K30_VERSION
    assert item_rand["display_name"] == "K30 Matched Random (隨機補票對照組)"
    assert item_rand["data_status"] == "HAS_HISTORY"
    assert item_rand["inventory_data_status"] == "NO_HISTORY"
    assert item_rand["history_status"] == "HAS_HISTORY"
    assert item_rand["history_source_identity_status"] == "UNKNOWN"
    assert "SOURCE_IDENTITY_UNKNOWN" in item_rand["history_statuses"]
    assert item_rand["available_target_count"] == 730
    assert item_rand["executable"] is False
    assert item_rand["backfill_native_binding"] is False
    assert item_rand["backfill_runnable"] is False


def test_api_does_not_invent_history_when_store_lacks_exact_rows() -> None:
    # Snapshot contains unrelated strategies and different versions
    big_lotto = _snapshot(
        run_id=None,
        rows=(
            _inventory_row(
                lottery_type="BIG_LOTTO",
                strategy_id=K30_GEOMETRY_ID,
                version="v0.2",
            ),
            _inventory_row(
                lottery_type="BIG_LOTTO",
                strategy_id="other_strategy",
                version=K30_VERSION,
            ),
        ),
    )

    client = _client(
        {
            "BIG_LOTTO": big_lotto,
            "DAILY_539": _snapshot(run_id=None),
            "POWER_LOTTO": _snapshot(run_id=None),
        }
    )

    resp_geo = client.get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "BIG_LOTTO", "q": K30_GEOMETRY_ID},
    )
    assert resp_geo.status_code == 200
    payload_geo = resp_geo.json()
    assert payload_geo["total_count"] == 1
    item_geo = payload_geo["items"][0]
    assert item_geo["data_status"] == "NO_HISTORY"
    assert item_geo["inventory_data_status"] == "NO_HISTORY"
    assert item_geo["available_target_count"] == 0
    assert item_geo["executable"] is False
    assert item_geo["backfill_native_binding"] is False
    assert item_geo["backfill_runnable"] is False

    resp_rand = client.get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "BIG_LOTTO", "q": K30_RANDOM_ID},
    )
    assert resp_rand.status_code == 200
    payload_rand = resp_rand.json()
    assert payload_rand["total_count"] == 1
    item_rand = payload_rand["items"][0]
    assert item_rand["data_status"] == "NO_HISTORY"
    assert item_rand["inventory_data_status"] == "NO_HISTORY"
    assert item_rand["available_target_count"] == 0
    assert item_rand["executable"] is False
    assert item_rand["backfill_native_binding"] is False
    assert item_rand["backfill_runnable"] is False


def test_api_does_not_mix_lottery_types_for_k30() -> None:
    # Historical data exists only under POWER_LOTTO, not BIG_LOTTO
    power_lotto = _snapshot(
        rows=(
            _inventory_row(
                lottery_type="POWER_LOTTO",
                strategy_id=K30_GEOMETRY_ID,
                version=K30_VERSION,
                target_count=730,
            ),
            _inventory_row(
                lottery_type="POWER_LOTTO",
                strategy_id=K30_RANDOM_ID,
                version=K30_VERSION,
                target_count=730,
            ),
        ),
    )

    client = _client(
        {
            "BIG_LOTTO": _snapshot(run_id=None),
            "DAILY_539": _snapshot(run_id=None),
            "POWER_LOTTO": power_lotto,
        }
    )

    resp_geo = client.get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "BIG_LOTTO", "q": K30_GEOMETRY_ID},
    )
    assert resp_geo.status_code == 200
    item_geo = resp_geo.json()["items"][0]
    assert item_geo["lottery_type"] == "BIG_LOTTO"
    assert item_geo["data_status"] == "NO_HISTORY"

    resp_rand = client.get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "BIG_LOTTO", "q": K30_RANDOM_ID},
    )
    assert resp_rand.status_code == 200
    item_rand = resp_rand.json()["items"][0]
    assert item_rand["lottery_type"] == "BIG_LOTTO"
    assert item_rand["data_status"] == "NO_HISTORY"
