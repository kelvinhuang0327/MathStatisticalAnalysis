"""Historical K10 versions appear without claiming a live replay adapter."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from lottolab.application.replay_strategy_inventory import load_replay_strategy_inventory
from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_strategy_inventory import (
    ReplayDataStatus,
    ReplayExecutionCapability,
)
from lottolab.interfaces.api.replay_backfill import create_replay_backfill_router

IDENTITIES = (
    ("legacy_biglotto__evolution_engine__3df019c31ce4", "v0.5-prefix-isolated-r1"),
    ("tasklocal_evolution_h1_duplicate_completion_20261105", "h1-prefix-isolated-r1"),
    ("tasklocal_evolution_h2_uniform_cover_20261105", "h2-prefix-isolated-r1"),
)


def test_exact_k10_versions_are_separate_and_not_executable() -> None:
    inventory = load_replay_strategy_inventory()
    for strategy_id, version in IDENTITIES:
        rows = [
            item
            for item in inventory.items
            if item.lottery_type is LotteryType.BIG_LOTTO
            and item.strategy_id == strategy_id
            and item.strategy_version == version
        ]
        assert len(rows) == 1
        assert rows[0].replay_data_status is ReplayDataStatus.CODE_ONLY
        assert rows[0].execution_capability is ReplayExecutionCapability.UNAVAILABLE
        assert rows[0].adapter_mapping is None
    assert any(
        item.strategy_id == IDENTITIES[0][0] and item.strategy_version == "v0.5"
        for item in inventory.items
    )


def test_replay_strategy_api_lists_each_exact_version_without_an_adapter() -> None:
    class EmptyReplayStore:
        def strategy_history_snapshot(self, lottery_type: str, **kwargs: object) -> dict:
            return {
                "run_id": None,
                "target_count": 0,
                "cell_status_counts": [],
                "strategy_inventory": [],
                "selected_strategies": [],
                "run_source": {"identity_status": "UNKNOWN"},
            }

        def stored_strategy_inventory(self, lottery_type: str) -> list:
            return []

    app = FastAPI()
    app.include_router(create_replay_backfill_router(EmptyReplayStore()))
    with TestClient(app) as client:
        for strategy_id, version in IDENTITIES:
            response = client.get(
                "/api/v1/replay-backfill/strategies",
                params={"lottery_type": "BIG_LOTTO", "q": strategy_id, "limit": 250},
            )
            assert response.status_code == 200
            rows = [
                item for item in response.json()["items"] if item["strategy_version"] == version
            ]
            assert len(rows) == 1
            assert rows[0]["executable"] is False
            assert rows[0]["inventory_data_status"] == "CODE_ONLY"
            assert rows[0]["available_target_count"] == 0
