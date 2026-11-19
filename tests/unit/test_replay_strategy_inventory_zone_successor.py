from __future__ import annotations

from typing import Any, Protocol, cast

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

ZONE_STRATEGY_ID = "research_biglotto__zone_momentum_complete_v1"
SOURCE_RUN_ID = (
    "zone_successor_stage_642fb680b1a86e13c2594a6585b5c8f3776392936ff0681ac2b43f1846f73b5d"
)


class _JsonResponse(Protocol):
    status_code: int

    def json(self) -> dict[str, Any]: ...


class _JsonTestClient(Protocol):
    def get(self, url: str, *, params: Any = None) -> _JsonResponse: ...


def _json_client(app: Any) -> _JsonTestClient:
    return cast(_JsonTestClient, TestClient(app))


def _snapshot(
    *,
    run_id: str | None = "synthetic-zone-overlay",
    rows: tuple[dict[str, Any], ...] = (),
    cells: tuple[dict[str, Any], ...] = (),
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "created_at": "2026-11-09T00:00:00+00:00",
        "dataset_identity": "synthetic-zone-overlay-dataset",
        "execution_version": "synthetic-v1",
        "selection_rule": "LATEST_RUN_BY_CREATED_AT_PER_LOTTERY_TYPE",
        "run_source": {
            "identity_status": "UNKNOWN",
            "source_identity": SOURCE_RUN_ID,
            "source_kind": "REPLAY_BACKFILL_IMPORTED_RESULT",
            "source_locator": SOURCE_RUN_ID,
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
    *, lottery_type: str, strategy_id: str, version: str, target_count: int = 3
) -> dict[str, Any]:
    return {
        "lottery_type": lottery_type,
        "strategy_id": strategy_id,
        "strategy_version": version,
        "data_status": "HAS_HISTORY",
        "source_kind": "REPLAY_BACKFILL_IMPORTED_RESULT",
        "source_identity": "synthetic-overlay-identity",
        "executable": False,
        "available_target_count": target_count,
        "training_status": "NOT_REQUIRED",
    }


def _complete_cells(*, lottery_type: str, strategy_id: str, version: str) -> dict[str, Any]:
    return {
        "lottery_type": lottery_type,
        "strategy_id": strategy_id,
        "strategy_version": version,
        "execution_status": "COMPLETE",
        "cell_count": 3,
        "ticket_count": 6,
        "saved_prediction_cell_count": 3,
    }


def test_zone_successor_is_identified_without_fabricated_history_or_binding() -> None:
    inventory = load_replay_strategy_inventory()
    rows = inventory.query(
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_id=ZONE_STRATEGY_ID,
    )

    assert len(rows) == 1
    item = rows[0]
    assert item.strategy_version == "v1"
    assert item.source_kind == "REPLAY_BACKFILL_IMPORTED_RESULT"
    assert item.source_locator == SOURCE_RUN_ID
    assert item.lifecycle_status is ReplayLifecycleStatus.UNREGISTERED_IDENTIFIED
    assert item.replay_data_status is ReplayDataStatus.NO_HISTORY
    assert item.historical_data_count == 0
    assert item.execution_capability is ReplayExecutionCapability.UNAVAILABLE
    assert item.adapter_mapping is None
    assert item.backfill_native_binding is False
    assert item.backfill_runnable is False
    assert "Replay Backfill DB overlay" in item.reconstruction_reason
    assert any(
        source.source_kind == item.source_kind
        and source.source_locator == SOURCE_RUN_ID
        and source.strategy_version == "v1"
        for source in item.alias_or_identity_mapping
    )


def test_replay_backfill_api_overlays_only_the_exact_zone_lottery_id_and_version() -> None:
    big_lotto = _snapshot(
        rows=(
            _inventory_row(
                lottery_type="BIG_LOTTO",
                strategy_id=ZONE_STRATEGY_ID,
                version="v1",
            ),
            _inventory_row(
                lottery_type="BIG_LOTTO",
                strategy_id="different-zone-strategy",
                version="v1",
            ),
            _inventory_row(
                lottery_type="BIG_LOTTO",
                strategy_id=ZONE_STRATEGY_ID,
                version="v2",
            ),
        ),
        cells=(
            _complete_cells(
                lottery_type="BIG_LOTTO",
                strategy_id=ZONE_STRATEGY_ID,
                version="v1",
            ),
        ),
    )
    power_lotto = _snapshot(
        rows=(
            _inventory_row(
                lottery_type="POWER_LOTTO",
                strategy_id=ZONE_STRATEGY_ID,
                version="v1",
            ),
        ),
        cells=(
            _complete_cells(
                lottery_type="POWER_LOTTO",
                strategy_id=ZONE_STRATEGY_ID,
                version="v1",
            ),
        ),
    )
    response = _client(
        {
            "BIG_LOTTO": big_lotto,
            "DAILY_539": _snapshot(),
            "POWER_LOTTO": power_lotto,
        }
    ).get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "BIG_LOTTO", "q": ZONE_STRATEGY_ID},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_count"] == 1
    item = payload["items"][0]
    assert item["lottery_type"] == "BIG_LOTTO"
    assert item["strategy_id"] == ZONE_STRATEGY_ID
    assert item["strategy_version"] == "v1"
    assert item["data_status"] == "HAS_HISTORY"
    assert item["inventory_data_status"] == "NO_HISTORY"
    assert item["source_kind"] == "REPLAY_BACKFILL_IMPORTED_RESULT"
    assert item["inventory_source_locator"] == SOURCE_RUN_ID
    assert item["available_target_count"] == 3
    assert item["history_status"] == "HAS_HISTORY"
    assert item["history_source_identity_status"] == "UNKNOWN"
    assert "SOURCE_IDENTITY_UNKNOWN" in item["history_statuses"]
    assert item["history_counts"] == {
        "expected_cell_count": 3,
        "persisted_cell_count": 3,
        "saved_prediction_cell_count": 3,
        "saved_ticket_count": 6,
        "pending_cell_count": 0,
        "execution_status_counts": {
            "COMPLETE": 3,
            "FAILED": 0,
            "NOT_ELIGIBLE": 0,
            "TYPED_CLOSURE": 0,
            "MISSING": 0,
            "PARTIAL": 0,
            "ARTIFACT_ONLY": 0,
        },
    }
    assert item["executable"] is False
    assert item["backfill_native_binding"] is False
    assert item["backfill_runnable"] is False


def test_api_does_not_invent_history_when_the_exact_zone_row_is_missing() -> None:
    big_lotto = _snapshot(
        run_id=None,
        rows=(
            _inventory_row(
                lottery_type="BIG_LOTTO",
                strategy_id=ZONE_STRATEGY_ID,
                version="v2",
            ),
            _inventory_row(
                lottery_type="BIG_LOTTO",
                strategy_id="different-zone-strategy",
                version="v1",
            ),
        ),
        cells=(
            _complete_cells(
                lottery_type="BIG_LOTTO",
                strategy_id=ZONE_STRATEGY_ID,
                version="v2",
            ),
            _complete_cells(
                lottery_type="BIG_LOTTO",
                strategy_id="different-zone-strategy",
                version="v1",
            ),
        ),
    )
    power_lotto = _snapshot(
        run_id=None,
        rows=(
            _inventory_row(
                lottery_type="POWER_LOTTO",
                strategy_id=ZONE_STRATEGY_ID,
                version="v1",
            ),
        ),
        cells=(
            _complete_cells(
                lottery_type="POWER_LOTTO",
                strategy_id=ZONE_STRATEGY_ID,
                version="v1",
            ),
        ),
    )
    response = _client(
        {
            "BIG_LOTTO": big_lotto,
            "DAILY_539": _snapshot(run_id=None),
            "POWER_LOTTO": power_lotto,
        }
    ).get(
        "/api/v1/replay-backfill/strategies",
        params={"q": ZONE_STRATEGY_ID},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_count"] == 1
    item = payload["items"][0]
    assert item["data_status"] == "NO_HISTORY"
    assert item["inventory_data_status"] == "NO_HISTORY"
    assert item["available_target_count"] == 0
    assert item["history_status"] == "NO_HISTORY"
    assert item["executable"] is False
    assert item["backfill_native_binding"] is False
    assert item["backfill_runnable"] is False


def test_combined_zone_and_k30_inventory_uses_exact_overlay_and_paginates() -> None:
    geometry_id = "evolution_h12_k30_geometry_completion"
    random_id = "evolution_h12_k30_matched_random_completion"
    identities = {
        ("BIG_LOTTO", ZONE_STRATEGY_ID, "v1"),
        ("BIG_LOTTO", geometry_id, "v0.1"),
        ("BIG_LOTTO", random_id, "v0.1"),
    }
    big_lotto = _snapshot(
        rows=(
            _inventory_row(
                lottery_type="BIG_LOTTO",
                strategy_id=ZONE_STRATEGY_ID,
                version="v1",
                target_count=3,
            ),
            _inventory_row(
                lottery_type="BIG_LOTTO",
                strategy_id=ZONE_STRATEGY_ID,
                version="v2",
                target_count=99,
            ),
            _inventory_row(
                lottery_type="BIG_LOTTO",
                strategy_id=geometry_id,
                version="v0.1",
                target_count=3,
            ),
            _inventory_row(
                lottery_type="BIG_LOTTO",
                strategy_id=geometry_id,
                version="v0.2",
                target_count=99,
            ),
            _inventory_row(
                lottery_type="BIG_LOTTO",
                strategy_id=random_id,
                version="v0.1",
                target_count=3,
            ),
        ),
        cells=(
            _complete_cells(
                lottery_type="BIG_LOTTO",
                strategy_id=ZONE_STRATEGY_ID,
                version="v1",
            ),
            _complete_cells(
                lottery_type="BIG_LOTTO",
                strategy_id=geometry_id,
                version="v0.1",
            ),
            _complete_cells(
                lottery_type="BIG_LOTTO",
                strategy_id=random_id,
                version="v0.1",
            ),
        ),
    )
    power_lotto = _snapshot(
        rows=tuple(
            _inventory_row(
                lottery_type="POWER_LOTTO",
                strategy_id=strategy_id,
                version=version,
                target_count=99,
            )
            for _, strategy_id, version in identities
        ),
        cells=tuple(
            _complete_cells(
                lottery_type="POWER_LOTTO",
                strategy_id=strategy_id,
                version=version,
            )
            for _, strategy_id, version in identities
        ),
    )
    client = _client(
        {
            "BIG_LOTTO": big_lotto,
            "DAILY_539": _snapshot(),
            "POWER_LOTTO": power_lotto,
        }
    )

    first = client.get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "BIG_LOTTO", "q": "comple", "limit": 2},
    )
    assert first.status_code == 200
    first_payload = first.json()
    assert first_payload["total_count"] >= 5
    assert len(first_payload["items"]) == 2
    assert first_payload["next_cursor"]
    page_items = list(first_payload["items"])
    cursor = first_payload["next_cursor"]
    seen_cursors: set[str] = set()
    while cursor is not None:
        assert cursor not in seen_cursors
        seen_cursors.add(cursor)
        response = client.get(
            "/api/v1/replay-backfill/strategies",
            params={"lottery_type": "BIG_LOTTO", "q": "comple", "limit": 2, "cursor": cursor},
        )
        assert response.status_code == 200
        page = response.json()
        assert page["total_count"] == first_payload["total_count"]
        page_items.extend(page["items"])
        cursor = page["next_cursor"]
    assert len(page_items) == first_payload["total_count"]
    page_identities = {
        (item["lottery_type"], item["strategy_id"], item["strategy_version"]) for item in page_items
    }
    assert identities.issubset(page_identities)
    overlay_items = [
        item
        for item in page_items
        if (item["lottery_type"], item["strategy_id"], item["strategy_version"]) in identities
    ]
    assert len(overlay_items) == 3
    assert all(item["data_status"] == "HAS_HISTORY" for item in overlay_items)
    assert all(item["inventory_data_status"] == "NO_HISTORY" for item in overlay_items)
    assert all(item["history_status"] == "HAS_HISTORY" for item in overlay_items)
    assert all(item["history_source_identity_status"] == "UNKNOWN" for item in overlay_items)
    assert all(item["available_target_count"] == 3 for item in overlay_items)
    assert all(item["executable"] is False for item in overlay_items)
    assert all(item["backfill_native_binding"] is False for item in overlay_items)
    assert all(item["backfill_runnable"] is False for item in overlay_items)
    other_items = [item for item in page_items if item not in overlay_items]
    by_id = {item["strategy_id"]: item for item in other_items}
    assert {"cold_complement_biglotto", "research_biglotto__radical_gap_complete_v2"} <= set(by_id)
    for strategy_id in ("cold_complement_biglotto", "research_biglotto__radical_gap_complete_v2"):
        assert by_id[strategy_id]["data_status"] == "NO_HISTORY"
        assert by_id[strategy_id]["available_target_count"] == 0

    no_random_exact_row = _snapshot(
        run_id=None,
        rows=(
            _inventory_row(
                lottery_type="BIG_LOTTO",
                strategy_id=random_id,
                version="v0.2",
                target_count=99,
            ),
        ),
    )
    no_random_history = _client(
        {
            "BIG_LOTTO": no_random_exact_row,
            "DAILY_539": _snapshot(run_id=None),
            "POWER_LOTTO": power_lotto,
        }
    ).get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "BIG_LOTTO", "q": random_id},
    )
    assert no_random_history.status_code == 200
    no_history_item = no_random_history.json()["items"][0]
    assert no_history_item["strategy_id"] == random_id
    assert no_history_item["strategy_version"] == "v0.1"
    assert no_history_item["data_status"] == "NO_HISTORY"
    assert no_history_item["inventory_data_status"] == "NO_HISTORY"
    assert no_history_item["history_status"] == "NO_HISTORY"
    assert no_history_item["available_target_count"] == 0
    assert no_history_item["backfill_native_binding"] is False
    assert no_history_item["backfill_runnable"] is False
