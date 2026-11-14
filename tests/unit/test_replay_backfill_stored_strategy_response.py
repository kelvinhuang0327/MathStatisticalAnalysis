from __future__ import annotations

from types import SimpleNamespace
from typing import Protocol, cast

import httpx
import pytest
from fastapi import FastAPI
from fastapi.exceptions import ResponseValidationError
from fastapi.testclient import TestClient

from lottolab.application.seeded_single_replay import (
    SEED_CONTRACT,
    SeededSingleTicketReplay,
    seeded_replay_version,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_strategy_inventory import (
    ReplayDataStatus,
    ReplayExecutionCapability,
    ReplayLifecycleStatus,
)
from lottolab.interfaces.api import replay_backfill as api
from lottolab.interfaces.cli.replay_backfill import native_strategy_inventory
from lottolab.strategies.catalog import production_catalog


class JsonTestClient(Protocol):
    def get(self, url: str, **kwargs: object) -> httpx.Response: ...


TARGET_STRATEGY_ID = "biglotto_social_wisdom_anti_popularity"
TARGET_STRATEGY_VERSION = "v0.1"
TARGET_RUN_ID = "synthetic-run-for-api-contract-test"
_MISSING = object()
_SEEDED_REPLAY_PARITY_IDS = (
    "legacy_biglotto__frontend_collaborative_hybrid__97d79db161ba",
    "legacy_biglotto__frontend_ml_features__3a4324bc2aa9",
    "legacy_biglotto__frontend_ml_forest__3a4324bc2aa9",
    "legacy_biglotto__frontend_ml_genetic__3a4324bc2aa9",
    "legacy_biglotto__frontend_monte_carlo_strategy__9d8fe030546e",
    "legacy_biglotto__frontend_number_pairs_strategy__72ebb17b5a96",
    "legacy_biglotto__frontend_statistical_analysis_strategy__a9364825de2a",
    "legacy_biglotto__frontend_unified_ensemble_advanced__8f1183a9d8a7",
    "legacy_biglotto__frontend_unified_ensemble_weighted__8f1183a9d8a7",
    "legacy_biglotto__frontend_wheeling_strategy__ce978baff05b",
)
_STORED_ONLY_STRATEGY_ID = "research_biglotto__k30_geometry_qchamp_historical_v1"
_STORED_ONLY_STRATEGY_VERSION = "v1"


def _inventory_item(
    strategy_id: str = TARGET_STRATEGY_ID,
    strategy_version: str = TARGET_STRATEGY_VERSION,
) -> SimpleNamespace:
    return SimpleNamespace(
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_id=strategy_id,
        strategy_version=strategy_version,
        display_name="Synthetic registered strategy",
        source_kind="SYNTHETIC_CATALOG",
        source_locator="synthetic://catalog/strategy",
        lifecycle_status=ReplayLifecycleStatus.ONLINE,
        replay_data_status=ReplayDataStatus.HAS_HISTORY,
        execution_capability=ReplayExecutionCapability.EXECUTABLE,
        reconstructable=True,
        wrapper_callable=True,
        backfill_native_binding=True,
        backfill_native_binding_sources=(),
        backfill_runnable=True,
        execution_block_reason=None,
    )


def _stored_row(
    strategy_id: str,
    strategy_version: str,
    *,
    source_identity: object = "synthetic://stored/source",
    executable: bool = False,
) -> dict[str, object]:
    row: dict[str, object] = {
        "lottery_type": "BIG_LOTTO",
        "strategy_id": strategy_id,
        "strategy_version": strategy_version,
        "display_name": f"Stored {strategy_id}",
        "lifecycle_status": "OFFLINE",
        "data_status": "HAS_HISTORY",
        "source_kind": "STORED_LEGACY",
        "executable": executable,
        "available_target_count": 0,
        "training_status": "NOT_TRAINABLE",
    }
    if source_identity is not _MISSING:
        row["source_identity"] = source_identity
    return row


class _SyntheticStore:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def strategy_history_snapshot(
        self,
        lottery_type: str,
        *,
        run_id: str | None = None,
    ) -> dict[str, object]:
        del run_id
        if lottery_type != "BIG_LOTTO":
            return {
                "run_id": None,
                "target_count": 0,
                "cell_status_counts": [],
                "strategy_inventory": [],
                "selected_strategies": [],
                "run_source": {"identity_status": "UNKNOWN"},
            }
        return {
            "run_id": TARGET_RUN_ID,
            "created_at": "2026-01-01T00:00:00+00:00",
            "dataset_identity": "synthetic-dataset-identity",
            "execution_version": "synthetic-execution-v1",
            "selection_rule": "LATEST_RUN_BY_CREATED_AT_PER_LOTTERY_TYPE",
            "target_count": 1500,
            "strategy_inventory": [
                {
                    "strategy_id": TARGET_STRATEGY_ID,
                    "strategy_version": TARGET_STRATEGY_VERSION,
                }
            ],
            "selected_strategies": [
                {
                    "strategy_id": TARGET_STRATEGY_ID,
                    "strategy_version": TARGET_STRATEGY_VERSION,
                }
            ],
            "cell_status_counts": [
                {
                    "lottery_type": "BIG_LOTTO",
                    "strategy_id": TARGET_STRATEGY_ID,
                    "strategy_version": TARGET_STRATEGY_VERSION,
                    "execution_status": "COMPLETE",
                    "cell_count": 1500,
                    "ticket_count": 1500,
                    "saved_prediction_cell_count": 1500,
                }
            ],
            "run_source": {"identity_status": "UNKNOWN"},
        }

    def stored_strategy_inventory(self, lottery_type: str) -> list[dict[str, object]]:
        return [row.copy() for row in self.rows if row["lottery_type"] == lottery_type]


def _client(
    monkeypatch: pytest.MonkeyPatch,
    rows: list[dict[str, object]],
    inventory: list[SimpleNamespace] | None = None,
) -> JsonTestClient:
    monkeypatch.setattr(
        api,
        "load_replay_strategy_inventory",
        lambda: SimpleNamespace(items=inventory or []),
    )
    app = FastAPI()
    app.include_router(api.create_replay_backfill_router(_SyntheticStore(rows)))  # type: ignore[arg-type]
    return cast(JsonTestClient, TestClient(app))


def _combined_rows() -> list[dict[str, object]]:
    return [
        _stored_row(
            TARGET_STRATEGY_ID,
            TARGET_STRATEGY_VERSION,
            source_identity="catalog://synthetic/target",
            executable=True,
        ),
        _stored_row(
            "stored_only_legacy_strategy",
            "legacy-v0.9",
            source_identity="legacy://synthetic/source",
        ),
    ]


def test_unfiltered_and_filtered_queries_preserve_strategy_response_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(monkeypatch, _combined_rows(), [_inventory_item()])

    unfiltered = client.get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "BIG_LOTTO"},
    )
    assert unfiltered.status_code == 200
    page = api.ReplayBackfillStrategyPageResponse.model_validate(unfiltered.json())
    stored = next(item for item in page.items if item.strategy_id == "stored_only_legacy_strategy")
    assert stored.strategy_source_identity == "legacy://synthetic/source"
    assert stored.executable is False
    assert stored.data_status == "HAS_HISTORY"
    assert stored.history_source_identity_status == "UNKNOWN"
    assert stored.history_counts is not None
    assert stored.history_counts.saved_ticket_count == 0
    assert "source_identity" not in stored.model_dump()

    filtered = client.get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "BIG_LOTTO", "q": TARGET_STRATEGY_ID},
    )
    assert filtered.status_code == 200
    filtered_page = api.ReplayBackfillStrategyPageResponse.model_validate(filtered.json())
    assert filtered_page.total_count == 1
    target = filtered_page.items[0]
    assert target.strategy_id == TARGET_STRATEGY_ID
    assert target.strategy_version == TARGET_STRATEGY_VERSION
    assert target.history_run_id == TARGET_RUN_ID
    assert target.executable is True
    assert target.history_source_identity_status == "UNKNOWN"
    assert target.history_counts is not None
    assert target.history_counts.saved_ticket_count == 1500


def test_missing_source_identity_maps_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(
        monkeypatch,
        [_stored_row("identity_absent", "v1", source_identity=_MISSING)],
    )

    response = client.get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "BIG_LOTTO", "q": "identity_absent"},
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["strategy_source_identity"] is None
    assert "source_identity" not in item


def test_invalid_source_identity_type_is_rejected_at_mapped_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(
        monkeypatch,
        [_stored_row("invalid_identity", "v1", source_identity={"unexpected": "object"})],
    )

    with pytest.raises(ResponseValidationError) as captured:
        client.get(
            "/api/v1/replay-backfill/strategies",
            params={"lottery_type": "BIG_LOTTO", "q": "invalid_identity"},
        )

    errors = captured.value.errors()
    assert any(
        error["loc"][-1] == "strategy_source_identity"
        and error["type"] in {"string_type", "string_sub_type"}
        for error in errors
    )
    assert not any(error["loc"][-1] == "source_identity" for error in errors)


def test_distinct_stored_strategy_versions_keep_their_own_source_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        _stored_row("two_version_legacy", "legacy-v0.8", source_identity="source-v0.8"),
        _stored_row("two_version_legacy", "legacy-v0.9", source_identity="source-v0.9"),
    ]
    response = _client(monkeypatch, rows).get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "BIG_LOTTO", "q": "two_version_legacy"},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert [(item["strategy_version"], item["strategy_source_identity"]) for item in items] == [
        ("legacy-v0.8", "source-v0.8"),
        ("legacy-v0.9", "source-v0.9"),
    ]
    assert all(item["executable"] is False for item in items)


def test_backfill_runnable_matches_exact_native_versions_for_r152_identities() -> None:
    assert len(_SEEDED_REPLAY_PARITY_IDS) + 1 == 11
    store = _SyntheticStore(
        [
            _stored_row(
                _STORED_ONLY_STRATEGY_ID,
                _STORED_ONLY_STRATEGY_VERSION,
                executable=True,
            )
        ]
    )
    app = FastAPI()
    app.include_router(api.create_replay_backfill_router(store))  # type: ignore[arg-type]
    client = cast(JsonTestClient, TestClient(app))

    bindings, accounts = native_strategy_inventory(LotteryType.BIG_LOTTO)
    binding_by_id = {binding.strategy.strategy_id: binding for binding in bindings}
    catalog = production_catalog()

    for strategy_id in _SEEDED_REPLAY_PARITY_IDS:
        descriptor = catalog.get(strategy_id)
        seeded_version = seeded_replay_version(descriptor.version)
        binding = binding_by_id[strategy_id]
        account = accounts[strategy_id]
        assert isinstance(binding.implementation, SeededSingleTicketReplay)
        assert binding.strategy.strategy_version == seeded_version
        assert account["status"] == "EXECUTABLE"
        assert account["strategy_version"] == seeded_version
        assert account["source"] == descriptor.adapter_path
        assert account["seed_contract"] == SEED_CONTRACT
        assert account["seed_wrapper_sha256"]

        response = client.get(
            "/api/v1/replay-backfill/strategies",
            params={"lottery_type": "BIG_LOTTO", "q": strategy_id, "limit": 250},
        )
        assert response.status_code == 200
        rows = {item["strategy_version"]: item for item in response.json()["items"]}
        assert rows[descriptor.version]["backfill_runnable"] is False
        assert rows[descriptor.version]["execution_block_reason"] == "NO_CURRENT_NATIVE_BINDING"
        seeded = rows[seeded_version]
        assert seeded["backfill_runnable"] is True
        assert seeded["execution_block_reason"] is None
        assert seeded["backfill_native_binding_sources"] == [
            {
                "source_kind": "PRODUCTION_CATALOG_ADAPTER",
                "source_locator": descriptor.adapter_path,
            },
            {
                "source_kind": "SEEDED_SINGLE_TICKET_REPLAY",
                "source_locator": (
                    "src/lottolab/application/seeded_single_replay.py#SeededSingleTicketReplay"
                ),
            },
        ]

    orphan_response = client.get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "BIG_LOTTO", "q": _STORED_ONLY_STRATEGY_ID},
    )
    assert orphan_response.status_code == 200
    orphan = next(
        item
        for item in orphan_response.json()["items"]
        if item["strategy_id"] == _STORED_ONLY_STRATEGY_ID
    )
    assert orphan["executable"] is True
    assert orphan["backfill_runnable"] is False
    assert orphan["backfill_native_binding"] is False
    assert orphan["execution_block_reason"] == "NO_CURRENT_NATIVE_BINDING"
    assert (_STORED_ONLY_STRATEGY_ID, _STORED_ONLY_STRATEGY_VERSION) not in {
        (strategy_id, account["strategy_version"])
        for strategy_id, account in accounts.items()
        if account["status"] == "EXECUTABLE"
    }


def test_registered_executable_strategy_is_not_duplicated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = _stored_row(
        "registered_executable",
        "registered-v2",
        source_identity="source://registered-v2",
        executable=True,
    )
    response = _client(
        monkeypatch,
        [row],
        [_inventory_item("registered_executable", "registered-v2")],
    ).get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "BIG_LOTTO", "q": "registered_executable"},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["strategy_version"] == "registered-v2"
    assert items[0]["strategy_source_identity"] == "source://registered-v2"
    assert items[0]["executable"] is True
