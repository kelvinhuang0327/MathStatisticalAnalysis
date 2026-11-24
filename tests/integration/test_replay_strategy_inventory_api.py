from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol, cast

import httpx
from fastapi.testclient import TestClient

from lottolab.infrastructure.persistence.replay_backfill_store import SQLiteBackfillStore
from lottolab.interfaces.api.app import create_app


class JsonTestClient(Protocol):
    def get(self, url: str, **kwargs: object) -> httpx.Response: ...


def _client() -> JsonTestClient:
    return cast(JsonTestClient, TestClient(create_app()))


def _multiseed_fixture() -> dict[str, Any]:
    fixture_path = Path(__file__).parent.parent / "fixtures" / "k30_multiseed_stage_sources.json"
    loaded = json.loads(fixture_path.read_text(encoding="utf-8"))
    return json.loads(json.dumps(loaded))


def test_replay_strategy_inventory_api_lists_separate_states_and_full_backfill_ids() -> None:
    client = _client()

    response = client.get("/api/v1/replay-strategy-inventory")

    assert response.status_code == 200
    payload = response.json()
    multiseed_count = len(_multiseed_fixture()["seed_identities"])
    assert payload["total_discovered_strategies"] == 765 + multiseed_count
    assert payload["total_unique_strategies"] == 510 + multiseed_count
    assert payload["total_executable"] == 224
    assert payload["total_reconstructable"] == 224
    assert payload["total_has_history"] == 0
    assert payload["total_artifact_only"] == 135
    assert payload["total_rejected"] == 74
    assert payload["lifecycle_status_counts"]["ONLINE"] == 138
    assert payload["lifecycle_status_counts"]["OBSERVATION"] == 0
    assert payload["lifecycle_status_counts"]["OFFLINE"] == 0
    assert payload["lifecycle_status_counts"]["CODE_ONLY"] == 9
    assert payload["source_status_counts"]["OBSERVATION"] == 2
    assert payload["replay_data_status_counts"]["CODE_ONLY"] == 5
    assert payload["execution_capability_counts"]["EXECUTABLE"] == 224
    assert payload["execution_capability_counts"]["UNAVAILABLE"] == 286 + multiseed_count
    assert payload["strategy_count"] == payload["total_unique_strategies"]
    assert len(payload["executable_strategy_ids"]) == payload["total_executable"]
    quick_ml_rows = [
        row
        for row in payload["strategies"]
        if row["strategy_id"] == "research_biglotto__quick_ml_pattern_bounds_v1"
    ]
    assert len(quick_ml_rows) == 1
    assert quick_ml_rows[0]["strategy_version"] == "v0.1-research"
    assert quick_ml_rows[0]["execution_capability"] == "EXECUTABLE"
    assert all(
        set(identity) == {"lottery_type", "strategy_id", "strategy_version"}
        for identity in payload["executable_strategy_ids"]
    )

    k9 = [
        row
        for row in payload["strategies"]
        if row["lottery_type"] == "BIG_LOTTO"
        and row["strategy_id"] == "research_biglotto__k9_optimal_coverage_candidate"
        and row["strategy_version"] == "v0.1-research"
    ]
    assert len(k9) == 1
    assert k9[0]["source_kind"] == "REPLAY_BACKFILL_IMPORTED_RESULT"
    assert k9[0]["replay_data_status"] == "NO_HISTORY"
    assert k9[0]["execution_capability"] == "UNAVAILABLE"
    assert k9[0]["source_statuses"] == ["RESEARCH_STRATEGY"]

    rejected = next(row for row in payload["strategies"] if row["replay_data_status"] == "REJECTED")
    assert rejected["lifecycle_status"] == "REJECTED"
    assert rejected["execution_capability"] == "UNAVAILABLE"
    assert rejected["historical_data_count"] == 0
    assert rejected["reconstruction_reason"].startswith("CLOSED_UNEXECUTABLE:")

    online_rows = [row for row in payload["strategies"] if row["lifecycle_status"] == "ONLINE"]
    assert len(online_rows) == 138
    assert all(row["historical_data_count"] == 0 for row in online_rows)


def test_power_lotto_fixed_random_controls_are_listed_without_claiming_history() -> None:
    class EmptyHistory:
        def strategy_history_snapshot(self, lottery_type: str, *, run_id: str | None = None):
            return {"run_id": None}

    store = cast(SQLiteBackfillStore, EmptyHistory())
    client = cast(JsonTestClient, TestClient(create_app(replay_backfill_store=store)))
    response = client.get(
        "/api/v1/replay-backfill/strategies",
        params={
            "lottery_type": "POWER_LOTTO",
            "q": "research_powerlotto__historical_random_k",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    expected = {
        (
            f"research_powerlotto__historical_random_k{k}_20261119_r1",
            "v1.0.0",
            f"威力彩 K{k} 固定隨機控制",
        )
        for k in (1, 2, 3, 4, 5, 7, 10, 11, 12, 25)
    }
    rows = payload["items"]
    assert payload["total_count"] == len(rows) == len(expected)
    assert {
        (row["strategy_id"], row["strategy_version"], row["display_name"]) for row in rows
    } == expected
    for row in rows:
        assert row["lottery_type"] == "POWER_LOTTO"
        assert row["data_status"] == row["history_status"] == "NO_HISTORY"
        assert row["available_target_count"] == 0
        assert row["backfill_runnable"] is False


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

    radical = client.get(
        "/api/v1/replay-strategy-inventory",
        params={"strategy_id": "research_biglotto__radical_recorded_causal_successor_v1"},
    )
    assert radical.status_code == 200
    assert radical.json()["strategy_count"] == 1
    row = radical.json()["strategies"][0]
    assert row["strategy_version"] == "v1"
    assert row["execution_capability"] == "EXECUTABLE"
    assert row["backfill_native_binding"] is True

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



def test_k30_multiseed_inventory_api_lists_seed_set_without_formal_history() -> None:
    fixture = _multiseed_fixture()
    expected = {
        (row["strategy_id"], row["strategy_version"])
        for row in fixture["seed_identities"]
    }
    response = _client().get("/api/v1/replay-strategy-inventory")
    assert response.status_code == 200
    payload = response.json()
    rows = [
        row for row in payload["strategies"]
        if row["strategy_id"].startswith("research_biglotto__k30_histseed_")
    ]
    assert {(row["strategy_id"], row["strategy_version"]) for row in rows} == expected
    assert len(rows) == len(expected) == len(fixture["seed_identities"]) == 1000
    assert not expected.intersection(
        (row["strategy_id"], row["strategy_version"])
        for row in payload["executable_strategy_ids"]
    )
    assert not expected.intersection(
        (row["strategy_id"], row["strategy_version"])
        for row in payload["backfill_runnable_strategy_ids"]
    )
    for row in rows:
        assert row["lottery_type"] == "BIG_LOTTO"
        assert row["source_kind"] == "REPLAY_BACKFILL_STAGE_CANDIDATE"
        assert row["replay_data_status"] == "NO_HISTORY"
        assert row["historical_data_count"] == 0
        assert row["execution_capability"] == "UNAVAILABLE"
        assert row["adapter_mapping"] is None
        assert row["backfill_native_binding"] is not True
        assert row["backfill_native_binding_sources"] == []
        assert row["backfill_runnable"] is False
        assert "RESEARCH_STRATEGY" in row["source_statuses"]
        assert all(
            source["source_status"] in {"VERIFIED", "UNVERIFIED", "UNKNOWN"}
            for source in row["alias_or_identity_mapping"]
            if source["source_kind"] == "REPLAY_BACKFILL_STAGE_CANDIDATE"
        )
    source_counts = [
        row for row in payload["source_counts"]
        if row["source_kind"] == "REPLAY_BACKFILL_STAGE_CANDIDATE"
    ]
    assert len(source_counts) == 1
    assert source_counts[0]["source_identity_count"] == 1000
    assert source_counts[0]["source_row_count"] == len(fixture["source_records"]) == 1200
