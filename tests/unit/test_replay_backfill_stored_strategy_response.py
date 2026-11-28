import hashlib
import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Protocol, cast

import httpx
import pytest
from fastapi import FastAPI
from fastapi.exceptions import ResponseValidationError
from fastapi.testclient import TestClient

import lottolab
from lottolab.application.replay_strategy_inventory import load_replay_strategy_inventory
from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_strategy_inventory import (
    ReplayDataStatus,
    ReplayExecutionCapability,
    ReplayLifecycleStatus,
)
from lottolab.infrastructure.persistence.replay_backfill_store import (
    SCHEMA_CHECKSUM,
    SCHEMA_SQL,
    SCHEMA_VERSION,
    SQLiteBackfillStore,
    canonical_json,
)
from lottolab.interfaces.api import replay_backfill as api


class JsonTestClient(Protocol):
    def get(self, url: str, **kwargs: object) -> httpx.Response: ...


TARGET_STRATEGY_ID = "biglotto_social_wisdom_anti_popularity"
TARGET_STRATEGY_VERSION = "v0.1"
TARGET_RUN_ID = "synthetic-run-for-api-contract-test"
_MISSING = object()


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
        native_ticket_count=None,
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


FIXTURE_TAG = "SYNTHETIC_TEST_FIXTURE"
EH02_RUN_ID = f"{FIXTURE_TAG}_EH02_RUN"
EH03_RUN_ID = f"{FIXTURE_TAG}_EH03_RUN"
EMPTY_RUN_ID = f"{FIXTURE_TAG}_EMPTY_RUN"
DUPLICATE_RUN_ID = f"{FIXTURE_TAG}_DUPLICATE_RUN"
DIFF_LOTTERY_RUN_ID = f"{FIXTURE_TAG}_DAILY539_RUN"


def _create_synthetic_store(tmp_path: Path) -> SQLiteBackfillStore:
    # On macOS tmp_path is in /var/folders/... which is a real path (resolve to be sure)
    db_path = tmp_path.resolve() / "synthetic_replay.sqlite3"
    with sqlite3.connect(db_path) as conn:
        for stmt in SCHEMA_SQL.split(";"):
            if stmt.strip():
                conn.execute(stmt)
        conn.execute(
            "INSERT INTO replay_backfill_schema VALUES(?,?)",
            (SCHEMA_VERSION, SCHEMA_CHECKSUM),
        )

        # Each run has 1,317 saved cells across three strategy identities.
        # Rebuild each cell and its native tickets in SQLite for truth-based checks.
        eh02_targets = [str(201000000 + i) for i in range(438)]
        eh02_target_dates = {
            target_id: (date(2026, 1, 1) + timedelta(days=index)).isoformat()
            for index, target_id in enumerate(eh02_targets)
        }
        eh02_manifest = {
            "run_id": EH02_RUN_ID,
            "lottery_type": "BIG_LOTTO",
            "dataset_identity": f"{FIXTURE_TAG}_DS_EH02",
            "execution_version": "v1.0",
            "target_draw_ids": eh02_targets,
            "targets": [
                {"draw_number": target_id, "draw_date": eh02_target_dates[target_id]}
                for target_id in eh02_targets
            ],
            "strategies": [
                {"strategy_id": "eh02_k2_synth", "strategy_version": "v1.0"},
                {"strategy_id": "eh02_k3_synth", "strategy_version": "v1.0"},
                {"strategy_id": "eh02_k5_synth", "strategy_version": "v1.0"},
            ],
        }
        conn.execute(
            "INSERT INTO replay_backfill_runs (run_id, manifest_json, expected_cells, created_at) "
            "VALUES (?, ?, ?, ?)",
            (EH02_RUN_ID, canonical_json(eh02_manifest), 1314, "2026-11-01T10:00:00Z"),
        )
        conn.execute(
            "INSERT INTO replay_backfill_sources "
            "(run_id, source_identity, source_kind, source_locator, source_hash, artifact_only) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                EH02_RUN_ID,
                f"{FIXTURE_TAG}_DS_EH02",
                "OFFICIAL_HISTORICAL",
                "synthetic://locator",
                "hash1",
                0,
            ),
        )

        for tid in eh02_targets:
            conn.execute(
                "INSERT INTO replay_backfill_targets "
                "(run_id, lottery_type, target_draw_id, target_draw_date, "
                "actual_main_numbers_json, actual_special_numbers_json, source_identity) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    EH02_RUN_ID,
                    "BIG_LOTTO",
                    tid,
                    eh02_target_dates[tid],
                    "[1,2,3,4,5,6]",
                    "[7]",
                    f"{FIXTURE_TAG}_DS_EH02",
                ),
            )

        # EH02 Strategies in Inventory: K2, K3, K5
        # Simulate executable=1 in DB to test AC08 (fake executable must still be forced to False)
        for sid, k in [("eh02_k2_synth", 2), ("eh02_k3_synth", 3), ("eh02_k5_synth", 5)]:
            conn.execute(
                "INSERT INTO replay_backfill_strategy_inventory "
                "(run_id, lottery_type, strategy_id, strategy_version, display_name, "
                "lifecycle_status, data_status, source_kind, executable, available_target_count, "
                "training_status, source_identity) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    EH02_RUN_ID,
                    "BIG_LOTTO",
                    sid,
                    "v1.0",
                    f"EH02 K={k} Synthetic",
                    "ONLINE",
                    "HAS_HISTORY",
                    "STORED_LEGACY",
                    1,  # stored as 1 in DB to test fake executable guard
                    len(eh02_targets),
                    "NOT_TRAINABLE",
                    f"synthetic://source/{sid}",
                ),
            )

            # Insert cells and tickets for EH02 strategies
            # 438 cells per strategy, each cell has k native ticket positions.
            for tid in eh02_targets:
                cell_id = f"{EH02_RUN_ID}_{sid}_{tid}"
                payload_json = canonical_json(
                    {
                        "source_history_provenance_status": "VERIFIED",
                        "fixture_tag": FIXTURE_TAG,
                        "strategy_id": sid,
                        "target_draw_id": tid,
                        "native_ticket_positions": list(range(1, k + 1)),
                    }
                )
                conn.execute(
                    "INSERT INTO replay_backfill_cells "
                    "(cell_identity, lottery_type, strategy_id, strategy_version, "
                    "execution_version, dataset_identity, target_draw_id, target_draw_date, "
                    "execution_status, result_identity, payload_json, attempts) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        cell_id,
                        "BIG_LOTTO",
                        sid,
                        "v1.0",
                        "v1.0",
                        f"{FIXTURE_TAG}_DS_EH02",
                        tid,
                        eh02_target_dates[tid],
                        "COMPLETE",
                        f"res_{cell_id}",
                        payload_json,
                        1,
                    ),
                )
                conn.execute(
                    "INSERT INTO replay_backfill_run_cells (run_id, cell_identity) VALUES (?, ?)",
                    (EH02_RUN_ID, cell_id),
                )
                for pos in range(1, k + 1):
                    conn.execute(
                        "INSERT INTO replay_backfill_tickets "
                        "(cell_identity, ticket_position, main_numbers_json, special_numbers_json, "
                        "main_hit_count, special_hit, prize_tier) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (cell_id, pos, "[1,2,3,4,5,6]", "[7]", 6, 1, "JACKPOT"),
                    )

        eh03_targets = [str(202000000 + i) for i in range(439)]
        eh03_target_dates = {
            target_id: (date(2027, 1, 1) + timedelta(days=index)).isoformat()
            for index, target_id in enumerate(eh03_targets)
        }
        eh03_manifest = {
            "run_id": EH03_RUN_ID,
            "lottery_type": "BIG_LOTTO",
            "dataset_identity": f"{FIXTURE_TAG}_DS_EH03",
            "execution_version": "v1.0",
            "target_draw_ids": eh03_targets,
            "targets": [
                {"draw_number": tid, "draw_date": eh03_target_dates[tid]} for tid in eh03_targets
            ],
            "strategies": [
                {"strategy_id": "eh03_k2_synth", "strategy_version": "v1.0"},
                {"strategy_id": "eh03_k3_synth", "strategy_version": "v1.0"},
                {"strategy_id": "eh03_k5_synth", "strategy_version": "v1.0"},
            ],
        }
        conn.execute(
            "INSERT INTO replay_backfill_runs (run_id, manifest_json, expected_cells, created_at) "
            "VALUES (?, ?, ?, ?)",
            (EH03_RUN_ID, canonical_json(eh03_manifest), 1317, "2026-11-02T10:00:00Z"),
        )
        conn.execute(
            "INSERT INTO replay_backfill_sources "
            "(run_id, source_identity, source_kind, source_locator, source_hash, artifact_only) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                EH03_RUN_ID,
                f"{FIXTURE_TAG}_DS_EH03",
                "OFFICIAL_HISTORICAL",
                "synthetic://locator",
                "hash2",
                0,
            ),
        )

        for tid in eh03_targets:
            conn.execute(
                "INSERT INTO replay_backfill_targets "
                "(run_id, lottery_type, target_draw_id, target_draw_date, "
                "actual_main_numbers_json, actual_special_numbers_json, source_identity) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    EH03_RUN_ID,
                    "BIG_LOTTO",
                    tid,
                    eh03_target_dates[tid],
                    "[1,2,3,4,5,6]",
                    "[7]",
                    f"{FIXTURE_TAG}_DS_EH03",
                ),
            )

        # EH03 Strategies: K2, K3, K5 (439 cells each, k tickets per cell)
        for sid, k in [("eh03_k2_synth", 2), ("eh03_k3_synth", 3), ("eh03_k5_synth", 5)]:
            conn.execute(
                "INSERT INTO replay_backfill_strategy_inventory "
                "(run_id, lottery_type, strategy_id, strategy_version, display_name, "
                "lifecycle_status, data_status, source_kind, executable, available_target_count, "
                "training_status, source_identity) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    EH03_RUN_ID,
                    "BIG_LOTTO",
                    sid,
                    "v1.0",
                    f"EH03 K={k} Synthetic",
                    "ONLINE",
                    "HAS_HISTORY",
                    "STORED_LEGACY",
                    0,
                    len(eh03_targets),
                    "NOT_TRAINABLE",
                    f"synthetic://source/{sid}",
                ),
            )
            for tid in eh03_targets:
                cell_id = f"{EH03_RUN_ID}_{sid}_{tid}"
                payload_json = canonical_json(
                    {
                        "source_history_provenance_status": "VERIFIED",
                        "fixture_tag": FIXTURE_TAG,
                        "strategy_id": sid,
                        "target_draw_id": tid,
                        "native_ticket_positions": list(range(1, k + 1)),
                    }
                )
                conn.execute(
                    "INSERT INTO replay_backfill_cells "
                    "(cell_identity, lottery_type, strategy_id, strategy_version, "
                    "execution_version, dataset_identity, target_draw_id, target_draw_date, "
                    "execution_status, result_identity, payload_json, attempts) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        cell_id,
                        "BIG_LOTTO",
                        sid,
                        "v1.0",
                        "v1.0",
                        f"{FIXTURE_TAG}_DS_EH03",
                        tid,
                        eh03_target_dates[tid],
                        "COMPLETE",
                        f"res_{cell_id}",
                        payload_json,
                        1,
                    ),
                )
                conn.execute(
                    "INSERT INTO replay_backfill_run_cells (run_id, cell_identity) VALUES (?, ?)",
                    (EH03_RUN_ID, cell_id),
                )
                for pos in range(1, k + 1):
                    conn.execute(
                        "INSERT INTO replay_backfill_tickets "
                        "(cell_identity, ticket_position, main_numbers_json, special_numbers_json, "
                        "main_hit_count, special_hit, prize_tier) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (cell_id, pos, "[1,2,3,4,5,6]", "[7]", 6, 1, "JACKPOT"),
                    )

        # 3. Negative fixtures (AC10)
        # Empty Run
        conn.execute(
            "INSERT INTO replay_backfill_runs (run_id, manifest_json, expected_cells, created_at) "
            "VALUES (?, ?, ?, ?)",
            (
                EMPTY_RUN_ID,
                json.dumps({"run_id": EMPTY_RUN_ID, "lottery_type": "BIG_LOTTO"}),
                1,
                "2026-11-03T10:00:00Z",
            ),
        )

        # Duplicate Strategy Run: eh02_k2_synth also recorded in DUPLICATE_RUN_ID
        conn.execute(
            "INSERT INTO replay_backfill_runs (run_id, manifest_json, expected_cells, created_at) "
            "VALUES (?, ?, ?, ?)",
            (
                DUPLICATE_RUN_ID,
                json.dumps({"run_id": DUPLICATE_RUN_ID, "lottery_type": "BIG_LOTTO"}),
                1,
                "2026-11-04T10:00:00Z",
            ),
        )
        conn.execute(
            "INSERT INTO replay_backfill_strategy_inventory "
            "(run_id, lottery_type, strategy_id, strategy_version, display_name, "
            "lifecycle_status, data_status, source_kind, executable, available_target_count, "
            "training_status, source_identity) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                DUPLICATE_RUN_ID,
                "BIG_LOTTO",
                "eh02_k2_synth",
                "v1.0",
                "EH02 K=2 Synthetic Newer",
                "ONLINE",
                "HAS_HISTORY",
                "STORED_LEGACY",
                0,
                5,
                "NOT_TRAINABLE",
                "synthetic://source/eh02_k2_synth_newer",
            ),
        )

        # Version Mismatch: eh02_k2 with version v2.0 in EH02_RUN (not v1.0)
        conn.execute(
            "INSERT INTO replay_backfill_strategy_inventory "
            "(run_id, lottery_type, strategy_id, strategy_version, display_name, "
            "lifecycle_status, data_status, source_kind, executable, available_target_count, "
            "training_status, source_identity) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                EH02_RUN_ID,
                "BIG_LOTTO",
                "eh02_k2_synth",
                "v2.0",
                "EH02 K=2 v2",
                "ONLINE",
                "HAS_HISTORY",
                "STORED_LEGACY",
                0,
                1,
                "NOT_TRAINABLE",
                "synthetic://source/v2",
            ),
        )
        conn.execute(
            "INSERT INTO replay_backfill_cells "
            "(cell_identity, lottery_type, strategy_id, strategy_version, "
            "execution_version, dataset_identity, target_draw_id, target_draw_date, "
            "execution_status, result_identity, payload_json, attempts) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "cell_v2",
                "BIG_LOTTO",
                "eh02_k2_synth",
                "v2.0",
                "v2.0",
                f"{FIXTURE_TAG}_DS_EH02",
                "20261101",
                "2026-11-01",
                "COMPLETE",
                "res_v2",
                "{}",
                1,
            ),
        )
        conn.execute(
            "INSERT INTO replay_backfill_run_cells (run_id, cell_identity) VALUES (?, ?)",
            (EH02_RUN_ID, "cell_v2"),
        )
        conn.execute(
            "INSERT INTO replay_backfill_tickets "
            "(cell_identity, ticket_position, main_numbers_json, special_numbers_json, "
            "main_hit_count, special_hit, prize_tier) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("cell_v2", 1, "[1,2,3,4,5,6]", "[7]", 6, 1, "JACKPOT"),
        )

        # Different LotteryType: DAILY_539 Run
        conn.execute(
            "INSERT INTO replay_backfill_runs (run_id, manifest_json, expected_cells, created_at) "
            "VALUES (?, ?, ?, ?)",
            (
                DIFF_LOTTERY_RUN_ID,
                json.dumps({"run_id": DIFF_LOTTERY_RUN_ID, "lottery_type": "DAILY_539"}),
                1,
                "2026-11-05T10:00:00Z",
            ),
        )
        conn.execute(
            "INSERT INTO replay_backfill_strategy_inventory "
            "(run_id, lottery_type, strategy_id, strategy_version, display_name, "
            "lifecycle_status, data_status, source_kind, executable, available_target_count, "
            "training_status, source_identity) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                DIFF_LOTTERY_RUN_ID,
                "DAILY_539",
                "daily_strat_synth",
                "v1.0",
                "Daily 539 Synth",
                "ONLINE",
                "HAS_HISTORY",
                "STORED_LEGACY",
                0,
                1,
                "NOT_TRAINABLE",
                "synthetic://source/daily",
            ),
        )

        # No tickets cell: COMPLETE status, but 0 tickets
        conn.execute(
            "INSERT INTO replay_backfill_strategy_inventory "
            "(run_id, lottery_type, strategy_id, strategy_version, display_name, "
            "lifecycle_status, data_status, source_kind, executable, available_target_count, "
            "training_status, source_identity) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                EH02_RUN_ID,
                "BIG_LOTTO",
                "no_tickets_strat",
                "v1.0",
                "No Tickets Strat",
                "ONLINE",
                "HAS_HISTORY",
                "STORED_LEGACY",
                0,
                1,
                "NOT_TRAINABLE",
                "synthetic://source/notickets",
            ),
        )
        conn.execute(
            "INSERT INTO replay_backfill_cells "
            "(cell_identity, lottery_type, strategy_id, strategy_version, "
            "execution_version, dataset_identity, target_draw_id, target_draw_date, "
            "execution_status, result_identity, payload_json, attempts) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "cell_no_tickets",
                "BIG_LOTTO",
                "no_tickets_strat",
                "v1.0",
                "v1.0",
                f"{FIXTURE_TAG}_DS_EH02",
                "20261101",
                "2026-11-01",
                "COMPLETE",
                "res_notickets",
                "{}",
                1,
            ),
        )
        conn.execute(
            "INSERT INTO replay_backfill_run_cells (run_id, cell_identity) VALUES (?, ?)",
            (EH02_RUN_ID, "cell_no_tickets"),
        )

        # Tickets but non-COMPLETE: FAILED execution status with 2 tickets
        conn.execute(
            "INSERT INTO replay_backfill_strategy_inventory "
            "(run_id, lottery_type, strategy_id, strategy_version, display_name, "
            "lifecycle_status, data_status, source_kind, executable, available_target_count, "
            "training_status, source_identity) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                EH02_RUN_ID,
                "BIG_LOTTO",
                "failed_with_tickets_strat",
                "v1.0",
                "Failed With Tickets",
                "ONLINE",
                "HAS_HISTORY",
                "STORED_LEGACY",
                0,
                1,
                "NOT_TRAINABLE",
                "synthetic://source/failed_tickets",
            ),
        )
        conn.execute(
            "INSERT INTO replay_backfill_cells "
            "(cell_identity, lottery_type, strategy_id, strategy_version, "
            "execution_version, dataset_identity, target_draw_id, target_draw_date, "
            "execution_status, result_identity, payload_json, attempts) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "cell_failed_tickets",
                "BIG_LOTTO",
                "failed_with_tickets_strat",
                "v1.0",
                "v1.0",
                f"{FIXTURE_TAG}_DS_EH02",
                "20261101",
                "2026-11-01",
                "FAILED",
                "res_failed",
                "{}",
                1,
            ),
        )
        conn.execute(
            "INSERT INTO replay_backfill_run_cells (run_id, cell_identity) VALUES (?, ?)",
            (EH02_RUN_ID, "cell_failed_tickets"),
        )
        conn.execute(
            "INSERT INTO replay_backfill_tickets "
            "(cell_identity, ticket_position, main_numbers_json, special_numbers_json, "
            "main_hit_count, special_hit, prize_tier) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("cell_failed_tickets", 1, "[1,2,3,4,5,6]", "[7]", 0, 0, None),
        )
        conn.execute(
            "INSERT INTO replay_backfill_tickets "
            "(cell_identity, ticket_position, main_numbers_json, special_numbers_json, "
            "main_hit_count, special_hit, prize_tier) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("cell_failed_tickets", 2, "[1,2,3,4,5,6]", "[7]", 0, 0, None),
        )

        conn.commit()

    return SQLiteBackfillStore(db_path)


def _run_history_truth(
    store: SQLiteBackfillStore, run_id: str
) -> dict[tuple[str, str], tuple[int, int, int, dict[str, int]]]:
    with sqlite3.connect(store.database) as conn:
        rows = conn.execute(
            "SELECT c.strategy_id,c.strategy_version,c.execution_status,"
            "COUNT(DISTINCT c.cell_identity),COUNT(t.ticket_position),"
            "COUNT(DISTINCT CASE WHEN c.execution_status='COMPLETE' "
            "AND t.cell_identity IS NOT NULL THEN c.cell_identity END) "
            "FROM replay_backfill_cells c "
            "JOIN replay_backfill_run_cells r USING(cell_identity) "
            "LEFT JOIN replay_backfill_tickets t USING(cell_identity) "
            "WHERE r.run_id=? AND c.lottery_type='BIG_LOTTO' "
            "GROUP BY c.strategy_id,c.strategy_version,c.execution_status",
            (run_id,),
        ).fetchall()

    truth: dict[tuple[str, str], tuple[int, int, int, dict[str, int]]] = {}
    for strategy_id, strategy_version, status, cells, tickets, saved_cells in rows:
        key = (str(strategy_id), str(strategy_version))
        previous = truth.get(key, (0, 0, 0, {}))
        status_counts = previous[3].copy()
        status_counts[str(status)] = int(cells)
        truth[key] = (
            previous[0] + int(cells),
            previous[1] + (int(tickets) if status == "COMPLETE" else 0),
            previous[2] + int(saved_cells),
            status_counts,
        )
    return truth


def _run_data_fingerprint(store: SQLiteBackfillStore, run_id: str) -> str:
    with sqlite3.connect(store.database) as conn:
        cells = conn.execute(
            "SELECT c.cell_identity,c.lottery_type,c.strategy_id,c.strategy_version,"
            "c.execution_version,c.dataset_identity,c.target_draw_id,c.target_draw_date,"
            "c.execution_status,c.result_identity,c.payload_json,c.attempts "
            "FROM replay_backfill_cells c "
            "JOIN replay_backfill_run_cells r USING(cell_identity) "
            "WHERE r.run_id=? ORDER BY c.cell_identity",
            (run_id,),
        ).fetchall()
        tickets = conn.execute(
            "SELECT t.cell_identity,t.ticket_position,t.main_numbers_json,t.special_numbers_json,"
            "t.main_hit_count,t.special_hit,t.prize_tier "
            "FROM replay_backfill_tickets t "
            "JOIN replay_backfill_run_cells r USING(cell_identity) "
            "WHERE r.run_id=? ORDER BY t.cell_identity,t.ticket_position",
            (run_id,),
        ).fetchall()
    evidence = canonical_json({"cells": cells, "tickets": tickets})
    return hashlib.sha256(evidence.encode()).hexdigest()


def _candidate_client(store: SQLiteBackfillStore) -> JsonTestClient:
    app = FastAPI()
    app.include_router(api.create_replay_backfill_router(store))
    return cast(JsonTestClient, TestClient(app))


def test_ac01_source_loaded_from_test_checkout_src() -> None:
    """AC01: Verify code under test is loaded from this test checkout."""
    test_checkout_root = Path(__file__).resolve().parents[2]
    expected_package = (test_checkout_root / "src" / "lottolab").resolve()
    imported_package = Path(lottolab.__file__).resolve().parent
    assert imported_package == expected_package, (
        f"Expected lottolab from {expected_package}, got: {imported_package}"
    )


def test_ac02_registered_inventory_preserved(tmp_path: Path) -> None:
    """AC02: K3 Hedge and K6+ registered items not modified, overwritten or duplicated."""
    store = _create_synthetic_store(tmp_path)
    client = _candidate_client(store)

    registered = load_replay_strategy_inventory()
    registered_items = [
        it
        for it in registered.items
        if "k3_hedge" in it.strategy_id
        or "k6" in it.strategy_id
        or "k30" in it.strategy_id
        or "k3_nonoverlap" in it.strategy_id
    ]
    registered_ids = {item.strategy_id for item in registered_items}
    assert any("k3_hedge" in strategy_id for strategy_id in registered_ids)
    assert any("k6" in strategy_id for strategy_id in registered_ids)
    assert any("k30" in strategy_id for strategy_id in registered_ids)

    for item in registered_items:
        res = client.get(
            "/api/v1/replay-backfill/strategies",
            params={"lottery_type": item.lottery_type.value, "q": item.strategy_id},
        )
        assert res.status_code == 200
        page = api.ReplayBackfillStrategyPageResponse.model_validate(res.json())
        matches = [
            it
            for it in page.items
            if it.strategy_id == item.strategy_id and it.strategy_version == item.strategy_version
        ]
        assert len(matches) == 1, (
            f"Expected 1 match for {item.strategy_id} {item.strategy_version}, got {len(matches)}"
        )
        match = matches[0]
        assert match.executable == (item.execution_capability.value == "EXECUTABLE")
        assert match.backfill_runnable == item.backfill_runnable


def test_ac03_multi_run_stored_identity_discovery(tmp_path: Path) -> None:
    """AC03: Both EH02 and EH03 strategy identities are discovered across different runs."""
    store = _create_synthetic_store(tmp_path)
    client = _candidate_client(store)

    # 1. Store method level discovery
    stored_items = store.stored_strategy_inventory("BIG_LOTTO")
    stored_ids = {item["strategy_id"] for item in stored_items}
    for expected in ("eh02_k2_synth", "eh02_k3_synth", "eh02_k5_synth"):
        assert expected in stored_ids, f"EH02 strategy {expected} not discovered"
    for expected in ("eh03_k2_synth", "eh03_k3_synth", "eh03_k5_synth"):
        assert expected in stored_ids, f"EH03 strategy {expected} not discovered"

    # 2. API level discovery
    res = client.get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "BIG_LOTTO", "q": "synth", "limit": 100},
    )
    assert res.status_code == 200
    page = api.ReplayBackfillStrategyPageResponse.model_validate(res.json())
    api_ids = {item.strategy_id for item in page.items}

    assert "eh02_k2_synth" in api_ids
    assert "eh02_k3_synth" in api_ids
    assert "eh02_k5_synth" in api_ids
    assert "eh03_k2_synth" in api_ids
    assert "eh03_k3_synth" in api_ids
    assert "eh03_k5_synth" in api_ids


def test_ac04_eh02_run_exact_history_counts(tmp_path: Path) -> None:
    """AC04: When querying explicit EH02 run, cells and tickets match run truth (not all 0)."""
    store = _create_synthetic_store(tmp_path)
    client = _candidate_client(store)

    res = client.get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "BIG_LOTTO", "run_id": EH02_RUN_ID, "q": "eh02", "limit": 100},
    )
    assert res.status_code == 200
    page = api.ReplayBackfillStrategyPageResponse.model_validate(res.json())
    items_by_key = {(item.strategy_id, item.strategy_version): item for item in page.items}

    run_truth = _run_history_truth(store, EH02_RUN_ID)
    assert sum(counts[0] for counts in run_truth.values()) == 1317
    for sid in ("eh02_k2_synth", "eh02_k3_synth", "eh02_k5_synth"):
        key = (sid, "v1.0")
        exp_cells, exp_tickets, exp_saved_cells, exp_statuses = run_truth[key]
        assert key in items_by_key
        item = items_by_key[key]
        assert item.history_run_id == EH02_RUN_ID
        assert item.history_status == "HAS_HISTORY"
        assert item.history_counts is not None
        assert item.history_counts.persisted_cell_count == exp_cells
        assert item.history_counts.saved_prediction_cell_count == exp_saved_cells
        assert item.history_counts.saved_ticket_count == exp_tickets
        assert {
            status: count
            for status, count in item.history_counts.execution_status_counts.items()
            if count
        } == exp_statuses


def test_ac05_eh03_run_exact_history_counts_no_eh02_leakage(tmp_path: Path) -> None:
    """AC05: When querying explicit EH03 run, EH03 counts are exact and EH02 is not mixed in."""
    store = _create_synthetic_store(tmp_path)
    client = _candidate_client(store)

    res = client.get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "BIG_LOTTO", "run_id": EH03_RUN_ID, "q": "synth", "limit": 100},
    )
    assert res.status_code == 200
    page = api.ReplayBackfillStrategyPageResponse.model_validate(res.json())
    items_by_key = {(item.strategy_id, item.strategy_version): item for item in page.items}

    run_truth = _run_history_truth(store, EH03_RUN_ID)
    assert sum(counts[0] for counts in run_truth.values()) == 1317
    assert set(run_truth) == {
        ("eh03_k2_synth", "v1.0"),
        ("eh03_k3_synth", "v1.0"),
        ("eh03_k5_synth", "v1.0"),
    }

    for (sid, sver), (exp_cells, exp_tickets, exp_saved_cells, exp_statuses) in run_truth.items():
        assert (sid, sver) in items_by_key
        item = items_by_key[(sid, sver)]
        assert item.history_run_id == EH03_RUN_ID
        assert item.history_status == "HAS_HISTORY"
        assert item.history_counts is not None
        assert item.history_counts.persisted_cell_count == exp_cells
        assert item.history_counts.saved_prediction_cell_count == exp_saved_cells
        assert item.history_counts.saved_ticket_count == exp_tickets
        assert {
            status: count
            for status, count in item.history_counts.execution_status_counts.items()
            if count
        } == exp_statuses

    # Check EH02 strategies in EH03 run: must have 0 cells and 0 tickets in this run!
    for sid in ("eh02_k2_synth", "eh02_k3_synth", "eh02_k5_synth"):
        key = (sid, "v1.0")
        assert key in items_by_key
        eh02_item = items_by_key[key]
        assert eh02_item.history_run_id == EH03_RUN_ID
        assert eh02_item.history_status == "NOT_SELECTED_IN_RUN", (
            eh02_item.history_statuses,
            eh02_item.history_counts,
        )
        assert eh02_item.history_counts is not None
        assert eh02_item.history_counts.persisted_cell_count == 0
        assert eh02_item.history_counts.saved_ticket_count == 0


def test_ac06_strict_identity_and_run_isolation(tmp_path: Path) -> None:
    """AC06: All quantities strictly isolated by strategy_id, version, run_id."""
    store = _create_synthetic_store(tmp_path)
    client = _candidate_client(store)

    # Query EH02 run
    res02 = client.get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "BIG_LOTTO", "run_id": EH02_RUN_ID, "q": "synth", "limit": 100},
    )
    items02 = {
        (item.strategy_id, item.strategy_version): item
        for item in api.ReplayBackfillStrategyPageResponse.model_validate(res02.json()).items
    }

    # Query EH03 run
    res03 = client.get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "BIG_LOTTO", "run_id": EH03_RUN_ID, "q": "synth", "limit": 100},
    )
    items03 = {
        (item.strategy_id, item.strategy_version): item
        for item in api.ReplayBackfillStrategyPageResponse.model_validate(res03.json()).items
    }

    truth02 = _run_history_truth(store, EH02_RUN_ID)
    truth03 = _run_history_truth(store, EH03_RUN_ID)
    counts02 = items02[("eh02_k2_synth", "v1.0")].history_counts
    counts03 = items03[("eh03_k2_synth", "v1.0")].history_counts
    assert counts02 is not None
    assert counts02.persisted_cell_count == truth02[("eh02_k2_synth", "v1.0")][0]
    assert counts02.saved_ticket_count == truth02[("eh02_k2_synth", "v1.0")][1]
    assert counts03 is not None
    assert counts03.persisted_cell_count == truth03[("eh03_k2_synth", "v1.0")][0]
    assert counts03.saved_ticket_count == truth03[("eh03_k2_synth", "v1.0")][1]

    # Verify no version bleed: v1.0 does not count v2.0
    # Version v1.0 is counted independently from the one v2.0 cell.
    v1_item = items02[("eh02_k2_synth", "v1.0")]
    v2_item = items02[("eh02_k2_synth", "v2.0")]
    assert v1_item.history_counts is not None
    assert v1_item.history_counts.persisted_cell_count == truth02[("eh02_k2_synth", "v1.0")][0]
    assert v2_item.history_counts is not None and v2_item.history_counts.persisted_cell_count == 1


def test_ac07_ac08_stored_only_strategies_remain_non_executable(tmp_path: Path) -> None:
    """AC07 & AC08: Stored-only strategies remain executable=false and backfill_runnable=false."""
    store = _create_synthetic_store(tmp_path)
    client = _candidate_client(store)

    res = client.get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "BIG_LOTTO", "q": "synth", "limit": 100},
    )
    assert res.status_code == 200
    page = api.ReplayBackfillStrategyPageResponse.model_validate(res.json())

    for item in page.items:
        if "synth" in item.strategy_id:
            # AC07 & AC08: Even if executable=1 in DB, it MUST be False!
            assert item.executable is False, f"Strategy {item.strategy_id} has executable=True"
            assert item.backfill_runnable is False, (
                f"Strategy {item.strategy_id} has backfill_runnable=True"
            )
            assert item.backfill_native_binding is None or item.backfill_native_binding is False


def test_ac09_nonexistent_run_returns_404(tmp_path: Path) -> None:
    """AC09: Nonexistent run_id returns explicit 404, does not fall back to latest run."""
    store = _create_synthetic_store(tmp_path)
    client = _candidate_client(store)

    res = client.get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "BIG_LOTTO", "run_id": "nonexistent_run_id_123"},
    )
    assert res.status_code == 404
    assert res.json() == {"error_code": "REPLAY_BACKFILL_RUN_NOT_FOUND"}


def test_ac10_negative_cases(tmp_path: Path) -> None:
    """AC10: Negative cases: cross-run, version mismatch, lottery mismatch,

    duplicate identity, empty run, no tickets, non-COMPLETE status, fake executable.
    """
    store = _create_synthetic_store(tmp_path)
    client = _candidate_client(store)

    # 1. Empty run
    res_empty = client.get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "BIG_LOTTO", "run_id": EMPTY_RUN_ID, "q": "synth", "limit": 100},
    )
    assert res_empty.status_code == 200
    page_empty = api.ReplayBackfillStrategyPageResponse.model_validate(res_empty.json())
    for item in page_empty.items:
        if item.strategy_id.startswith("eh02_") or item.strategy_id.startswith("eh03_"):
            assert item.history_status == "NOT_SELECTED_IN_RUN"
            assert item.history_counts is not None
            assert item.history_counts.persisted_cell_count == 0
            assert item.history_counts.saved_ticket_count == 0

    # 2. Duplicate strategy across runs: in both EH02_RUN and DUPLICATE_RUN_ID
    # Must appear only once per (lottery_type, strategy_id, strategy_version)
    res_all = client.get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "BIG_LOTTO", "q": "eh02_k2_synth", "limit": 100},
    )
    page_all = api.ReplayBackfillStrategyPageResponse.model_validate(res_all.json())
    k2_v1_items = [
        item
        for item in page_all.items
        if item.strategy_id == "eh02_k2_synth" and item.strategy_version == "v1.0"
    ]
    assert len(k2_v1_items) == 1, "Duplicate strategy identity was not deduplicated"
    # Latest metadata from DUPLICATE_RUN_ID was used
    assert k2_v1_items[0].display_name == "EH02 K=2 Synthetic Newer"

    # 3. Version mismatch: v2.0 is separated from v1.0
    v2_items = [
        item
        for item in page_all.items
        if item.strategy_id == "eh02_k2_synth" and item.strategy_version == "v2.0"
    ]
    assert len(v2_items) == 1
    assert v2_items[0].strategy_version == "v2.0"

    # 4. Different LotteryType: DAILY_539 strategy does not appear under BIG_LOTTO query
    res_bl = client.get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "BIG_LOTTO", "q": "daily_strat_synth"},
    )
    page_bl = api.ReplayBackfillStrategyPageResponse.model_validate(res_bl.json())
    assert page_bl.total_count == 0

    # 5. Cell with 0 tickets: persisted_cell_count > 0, but saved_ticket_count == 0
    res_eh02 = client.get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "BIG_LOTTO", "run_id": EH02_RUN_ID, "q": "no_tickets_strat"},
    )
    eh02_page = api.ReplayBackfillStrategyPageResponse.model_validate(res_eh02.json())
    items_eh02 = {item.strategy_id: item for item in eh02_page.items}

    no_tickets_item = items_eh02["no_tickets_strat"]
    assert no_tickets_item.history_counts is not None
    assert no_tickets_item.history_counts.persisted_cell_count == 1
    assert no_tickets_item.history_counts.saved_prediction_cell_count == 0
    assert no_tickets_item.history_counts.saved_ticket_count == 0

    # 6. Tickets with non-COMPLETE (FAILED) execution status:
    # 2 tickets in DB, but execution_status is FAILED -> saved_ticket_count MUST be 0!
    res_failed = client.get(
        "/api/v1/replay-backfill/strategies",
        params={
            "lottery_type": "BIG_LOTTO",
            "run_id": EH02_RUN_ID,
            "q": "failed_with_tickets_strat",
        },
    )
    failed_page = api.ReplayBackfillStrategyPageResponse.model_validate(res_failed.json())
    items_failed = {item.strategy_id: item for item in failed_page.items}

    failed_item = items_failed["failed_with_tickets_strat"]
    assert failed_item.history_counts is not None
    assert failed_item.history_counts.persisted_cell_count == 1
    assert failed_item.history_counts.execution_status_counts["FAILED"] == 1
    assert failed_item.history_counts.execution_status_counts["COMPLETE"] == 0
    assert failed_item.history_counts.saved_ticket_count == 0
    assert failed_item.history_counts.saved_prediction_cell_count == 0
    assert failed_item.history_status == "FAILED"

    # 7. Run lottery type mismatch
    res_mismatch = client.get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "DAILY_539", "run_id": EH02_RUN_ID},
    )
    assert res_mismatch.status_code == 422
    assert res_mismatch.json() == {"error_code": "INVALID_QUERY"}


def test_ac11_six_column_invariants(tmp_path: Path) -> None:
    """AC11: Existing Replay six-column key and schema version 2 invariants preserved."""
    store = _create_synthetic_store(tmp_path)
    before = _run_data_fingerprint(store, EH02_RUN_ID)
    response = _candidate_client(store).get(
        "/api/v1/replay-backfill/strategies",
        params={"lottery_type": "BIG_LOTTO", "run_id": EH02_RUN_ID, "q": "eh02"},
    )
    assert response.status_code == 200
    assert _run_data_fingerprint(store, EH02_RUN_ID) == before
    with sqlite3.connect(store.database) as conn:
        schema_row = conn.execute("SELECT version, checksum FROM replay_backfill_schema").fetchone()
        assert schema_row == (SCHEMA_VERSION, SCHEMA_CHECKSUM)

        provenance_payloads = conn.execute(
            "SELECT c.payload_json FROM replay_backfill_cells c "
            "JOIN replay_backfill_run_cells r USING(cell_identity) "
            "WHERE r.run_id=? AND c.strategy_version='v1.0' "
            "AND c.strategy_id IN (?,?,?)",
            (EH02_RUN_ID, "eh02_k2_synth", "eh02_k3_synth", "eh02_k5_synth"),
        ).fetchall()
        assert len(provenance_payloads) == 1314
        assert all(
            json.loads(row[0]).get("source_history_provenance_status") == "VERIFIED"
            for row in provenance_payloads
        )

        duplicate_ticket_cells = conn.execute(
            "SELECT COUNT(*) FROM ("
            "SELECT t.cell_identity FROM replay_backfill_tickets t "
            "JOIN replay_backfill_run_cells r USING(cell_identity) "
            "WHERE r.run_id=? GROUP BY t.cell_identity,t.main_numbers_json,t.special_numbers_json "
            "HAVING COUNT(*)>1)",
            (EH02_RUN_ID,),
        ).fetchone()[0]
        assert duplicate_ticket_cells > 0

        k3_cell = conn.execute(
            "SELECT c.cell_identity FROM replay_backfill_cells c "
            "JOIN replay_backfill_run_cells r USING(cell_identity) "
            "WHERE r.run_id=? AND c.strategy_id='eh02_k3_synth' LIMIT 1",
            (EH02_RUN_ID,),
        ).fetchone()[0]
        native_positions = conn.execute(
            "SELECT ticket_position FROM replay_backfill_tickets "
            "WHERE cell_identity=? ORDER BY ticket_position",
            (k3_cell,),
        ).fetchall()
        assert [row[0] for row in native_positions] == [1, 2, 3]

        # Check unique constraint on six columns:
        # (lottery_type, strategy_id, strategy_version,
        #  execution_version, dataset_identity, target_draw_id)
        cols = conn.execute("PRAGMA table_info(replay_backfill_cells)").fetchall()
        col_names = [col[1] for col in cols]
        for expected_col in (
            "cell_identity",
            "lottery_type",
            "strategy_id",
            "strategy_version",
            "execution_version",
            "dataset_identity",
            "target_draw_id",
            "target_draw_date",
            "execution_status",
            "result_identity",
            "payload_json",
            "attempts",
        ):
            assert expected_col in col_names
        expected_six_column_key = [
            "lottery_type",
            "strategy_id",
            "strategy_version",
            "execution_version",
            "dataset_identity",
            "target_draw_id",
        ]
        unique_keys: list[list[str]] = []
        for index_row in conn.execute("PRAGMA index_list(replay_backfill_cells)"):
            if index_row[2] != 1:
                continue
            index_name = str(index_row[1]).replace('"', '""')
            columns = [
                str(column_row[2])
                for column_row in conn.execute(f'PRAGMA index_info("{index_name}")')
            ]
            if columns == expected_six_column_key:
                unique_keys.append(columns)
        assert unique_keys == [expected_six_column_key]
