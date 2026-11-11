from __future__ import annotations

from typing import Protocol, cast

import httpx
from fastapi.testclient import TestClient

from lottolab.interfaces.api.app import create_app


class JsonTestClient(Protocol):
    def get(self, url: str, **kwargs: object) -> httpx.Response: ...


def _client() -> JsonTestClient:
    return cast(JsonTestClient, TestClient(create_app()))


def test_replay_strategy_inventory_api_lists_separate_states_and_full_backfill_ids() -> None:
    client = _client()

    response = client.get("/api/v1/replay-strategy-inventory")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_discovered_strategies"] == 651
    assert payload["total_unique_strategies"] == 443
    assert payload["total_executable"] == 211
    assert payload["total_reconstructable"] == 211
    assert payload["total_has_history"] == 0
    assert payload["total_artifact_only"] == 98
    assert payload["total_rejected"] == 74
    assert payload["lifecycle_status_counts"]["ONLINE"] == 137
    assert payload["lifecycle_status_counts"]["OBSERVATION"] == 0
    assert payload["lifecycle_status_counts"]["OFFLINE"] == 0
    assert payload["lifecycle_status_counts"]["CODE_ONLY"] == 3
    assert payload["source_status_counts"]["OBSERVATION"] == 2
    assert payload["replay_data_status_counts"]["CODE_ONLY"] == 2
    assert payload["execution_capability_counts"]["EXECUTABLE"] == 211
    assert payload["execution_capability_counts"]["UNAVAILABLE"] == 232
    assert payload["strategy_count"] == payload["total_unique_strategies"]
    assert len(payload["executable_strategy_ids"]) == payload["total_executable"]
    assert all(
        set(identity) == {"lottery_type", "strategy_id", "strategy_version"}
        for identity in payload["executable_strategy_ids"]
    )

    rejected = next(row for row in payload["strategies"] if row["replay_data_status"] == "REJECTED")
    assert rejected["lifecycle_status"] == "REJECTED"
    assert rejected["execution_capability"] == "UNAVAILABLE"
    assert rejected["historical_data_count"] == 0
    assert rejected["reconstruction_reason"].startswith("CLOSED_UNEXECUTABLE:")

    online_rows = [row for row in payload["strategies"] if row["lifecycle_status"] == "ONLINE"]
    assert len(online_rows) == 137
    assert all(row["historical_data_count"] == 0 for row in online_rows)


def test_replay_strategy_inventory_api_filters_by_lottery_strategy_and_data_status() -> None:
    client = _client()

    by_lottery = client.get(
        "/api/v1/replay-strategy-inventory",
        params={"lottery_type": "DAILY_539"},
    )
    assert by_lottery.status_code == 200
    assert by_lottery.json()["strategy_count"] == 62
    assert all(row["lottery_type"] == "DAILY_539" for row in by_lottery.json()["strategies"])

    by_strategy = client.get(
        "/api/v1/replay-strategy-inventory",
        params={"strategy_id": "research_biglotto__quick_ml_corrected_successor_v1"},
    )
    assert by_strategy.status_code == 200
    assert by_strategy.json()["strategy_count"] == 1
    successor = by_strategy.json()["strategies"][0]
    assert successor["lifecycle_status"] == "CODE_ONLY"
    assert successor["replay_data_status"] == "REBUILDABLE"
    assert successor["execution_capability"] == "EXECUTABLE"

    by_data_status = client.get(
        "/api/v1/replay-strategy-inventory",
        params={"replay_data_status": "REJECTED"},
    )
    assert by_data_status.status_code == 200
    assert by_data_status.json()["strategy_count"] == 74
    assert all(
        row["replay_data_status"] == "REJECTED" for row in by_data_status.json()["strategies"]
    )


def test_replay_strategy_inventory_api_rejects_invalid_filters() -> None:
    client = _client()

    invalid_lottery = client.get(
        "/api/v1/replay-strategy-inventory",
        params={"lottery_type": "UNKNOWN"},
    )
    invalid_data_status = client.get(
        "/api/v1/replay-strategy-inventory",
        params={"replay_data_status": "UNKNOWN"},
    )
    blank_strategy_id = client.get(
        "/api/v1/replay-strategy-inventory",
        params={"strategy_id": ""},
    )

    assert invalid_lottery.status_code == 422
    assert invalid_data_status.status_code == 422
    assert blank_strategy_id.status_code == 422
