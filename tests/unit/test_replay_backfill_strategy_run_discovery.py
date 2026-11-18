from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.infrastructure.persistence.replay_backfill_store import (
    SCHEMA_CHECKSUM,
    SCHEMA_SQL,
    SCHEMA_VERSION,
    SQLiteBackfillStore,
)


def _init_test_db(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.execute(
            "INSERT INTO replay_backfill_schema(version, checksum) VALUES(?, ?)",
            (SCHEMA_VERSION, SCHEMA_CHECKSUM),
        )


def _insert_run(
    conn: sqlite3.Connection,
    run_id: str,
    created_at: str,
    manifest: dict[str, Any] | None = None,
    expected_cells: int = 10,
) -> None:
    if manifest is None:
        manifest = {"run_id": run_id, "lottery_type": "BIG_LOTTO"}
    conn.execute(
        "INSERT INTO replay_backfill_runs(run_id, manifest_json, expected_cells, created_at) "
        "VALUES(?, ?, ?, ?)",
        (run_id, json.dumps(manifest), expected_cells, created_at),
    )


def _insert_inventory(
    conn: sqlite3.Connection,
    run_id: str,
    lottery_type: str,
    strategy_id: str,
    strategy_version: str,
    available_target_count: int = 10,
) -> None:
    conn.execute(
        "INSERT INTO replay_backfill_strategy_inventory("
        "run_id, lottery_type, strategy_id, strategy_version, display_name, "
        "lifecycle_status, data_status, source_kind, executable, available_target_count, "
        "training_status, source_identity) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            run_id,
            lottery_type,
            strategy_id,
            strategy_version,
            f"Display {strategy_id}",
            "ACTIVE",
            "AVAILABLE",
            "TEST",
            1,
            available_target_count,
            "TRAINED",
            f"source-{strategy_id}",
        ),
    )


def _insert_cell(
    conn: sqlite3.Connection,
    cell_identity: str,
    lottery_type: str,
    strategy_id: str,
    strategy_version: str,
    target_draw_id: str,
    target_draw_date: str,
    execution_version: str = "exec_v1",
    dataset_identity: str = "ds_v1",
    execution_status: str = "COMPLETE",
) -> None:
    conn.execute(
        "INSERT INTO replay_backfill_cells("
        "cell_identity, lottery_type, strategy_id, strategy_version, execution_version, "
        "dataset_identity, target_draw_id, target_draw_date, execution_status, "
        "result_identity, payload_json) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            cell_identity,
            lottery_type,
            strategy_id,
            strategy_version,
            execution_version,
            dataset_identity,
            target_draw_id,
            target_draw_date,
            execution_status,
            f"res-{cell_identity}",
            json.dumps({"cell_identity": cell_identity}),
        ),
    )


def _link_run_cell(conn: sqlite3.Connection, run_id: str, cell_identity: str) -> None:
    conn.execute(
        "INSERT INTO replay_backfill_run_cells(run_id, cell_identity) VALUES(?, ?)",
        (run_id, cell_identity),
    )


def _insert_ticket(
    conn: sqlite3.Connection,
    cell_identity: str,
    ticket_position: int,
    main_numbers: list[int] | None = None,
    special_numbers: list[int] | None = None,
    main_hit_count: int = 0,
    special_hit: int = 0,
) -> None:
    if main_numbers is None:
        main_numbers = [1, 2, 3, 4, 5, 6]
    if special_numbers is None:
        special_numbers = [7]
    conn.execute(
        "INSERT INTO replay_backfill_tickets("
        "cell_identity, ticket_position, main_numbers_json, special_numbers_json, "
        "main_hit_count, special_hit) VALUES(?, ?, ?, ?, ?, ?)",
        (
            cell_identity,
            ticket_position,
            json.dumps(main_numbers),
            json.dumps(special_numbers),
            main_hit_count,
            special_hit,
        ),
    )


def test_discover_strategy_runs_attribute_exists(tmp_path: Path) -> None:
    db_file = tmp_path / "test.sqlite3"
    _init_test_db(db_file)
    store = SQLiteBackfillStore(db_file)
    assert hasattr(store, "discover_strategy_runs")
    assert callable(store.discover_strategy_runs)


def test_ac1_exact_identity_matching(tmp_path: Path) -> None:
    db_file = tmp_path / "test_ac1.sqlite3"
    _init_test_db(db_file)
    with sqlite3.connect(db_file) as conn:
        _insert_run(conn, "R1", "2026-01-01T10:00:00Z")
        # S1 v1
        _insert_inventory(conn, "R1", "BIG_LOTTO", "S1", "v1")
        _insert_cell(conn, "c1", "BIG_LOTTO", "S1", "v1", "101", "2026-01-02")
        _insert_cell(conn, "c2", "BIG_LOTTO", "S1", "v1", "102", "2026-01-05")
        _link_run_cell(conn, "R1", "c1")
        _link_run_cell(conn, "R1", "c2")
        # S1 v2
        _insert_inventory(conn, "R1", "BIG_LOTTO", "S1", "v2")
        _insert_cell(conn, "c3", "BIG_LOTTO", "S1", "v2", "103", "2026-01-09")
        _link_run_cell(conn, "R1", "c3")
        # S2 v1
        _insert_inventory(conn, "R1", "BIG_LOTTO", "S2", "v1")
        _insert_cell(conn, "c4", "BIG_LOTTO", "S2", "v1", "101", "2026-01-02")
        _link_run_cell(conn, "R1", "c4")

    store = SQLiteBackfillStore(db_file)

    # Exact match S1 v1
    res_v1 = store.discover_strategy_runs("BIG_LOTTO", "S1", "v1")
    assert res_v1["total_run_version_matches"] == 1
    assert len(res_v1["items"]) == 1
    assert res_v1["items"][0]["strategy_id"] == "S1"
    assert res_v1["items"][0]["strategy_version"] == "v1"
    assert res_v1["items"][0]["associated_cell_count"] == 2
    assert res_v1["items"][0]["unique_target_draw_count"] == 2
    assert res_v1["items"][0]["earliest_target_draw_date"] == "2026-01-02"
    assert res_v1["items"][0]["latest_target_draw_date"] == "2026-01-05"

    # Exact match S1 v2
    res_v2 = store.discover_strategy_runs("BIG_LOTTO", "S1", "v2")
    assert res_v2["total_run_version_matches"] == 1
    assert len(res_v2["items"]) == 1
    assert res_v2["items"][0]["strategy_version"] == "v2"
    assert res_v2["items"][0]["associated_cell_count"] == 1
    assert res_v2["items"][0]["unique_target_draw_count"] == 1

    # Unspecified version returns both separate versions, not a merged version
    res_all = store.discover_strategy_runs(LotteryType.BIG_LOTTO, "S1")
    assert res_all["total_run_version_matches"] == 2
    assert len(res_all["items"]) == 2
    versions = [item["strategy_version"] for item in res_all["items"]]
    assert versions == ["v1", "v2"]

    # Different lottery_type returns empty
    res_other = store.discover_strategy_runs("SUPER_LOTTO", "S1")
    assert res_other["total_run_version_matches"] == 0
    assert res_other["items"] == []


def test_ac2_cross_run_discovery_and_inventory_only(tmp_path: Path) -> None:
    db_file = tmp_path / "test_ac2.sqlite3"
    _init_test_db(db_file)
    with sqlite3.connect(db_file) as conn:
        _insert_run(conn, "R1", "2026-01-01T10:00:00Z")
        _insert_run(conn, "R2", "2026-02-01T10:00:00Z")
        _insert_run(conn, "R3", "2026-03-01T10:00:00Z")  # Latest run, no S1

        # R1 has inventory and 2 cells
        _insert_inventory(conn, "R1", "BIG_LOTTO", "S1", "v1")
        _insert_cell(conn, "c1", "BIG_LOTTO", "S1", "v1", "101", "2026-01-02")
        _insert_cell(conn, "c2", "BIG_LOTTO", "S1", "v1", "102", "2026-01-05")
        _link_run_cell(conn, "R1", "c1")
        _link_run_cell(conn, "R1", "c2")

        # R2 has inventory ONLY (0 cells)
        _insert_inventory(conn, "R2", "BIG_LOTTO", "S1", "v1")

    store = SQLiteBackfillStore(db_file)
    res = store.discover_strategy_runs("BIG_LOTTO", "S1", "v1")

    assert res["total_run_version_matches"] == 2
    items = res["items"]
    assert len(items) == 2

    # Ordered created_at DESC -> R2 first, then R1
    run_ids = [it["run_id"] for it in items]
    assert run_ids == ["R2", "R1"]

    # R2 is inventory-only with 0 cells
    r2_item = items[0]
    assert r2_item["run_id"] == "R2"
    assert r2_item["inventory_present"] is True
    assert r2_item["associated_cell_count"] == 0
    assert r2_item["unique_target_draw_count"] == 0
    assert r2_item["execution_identity_count"] == 0
    assert r2_item["execution_status_counts"] == {}
    assert r2_item["earliest_target_draw_date"] is None
    assert r2_item["latest_target_draw_date"] is None

    # R1 has cells
    r1_item = items[1]
    assert r1_item["run_id"] == "R1"
    assert r1_item["inventory_present"] is True
    assert r1_item["associated_cell_count"] == 2
    assert r1_item["unique_target_draw_count"] == 2
    assert r1_item["earliest_target_draw_date"] == "2026-01-02"
    assert r1_item["latest_target_draw_date"] == "2026-01-05"


def test_ac3_shared_cell_across_runs_and_draw_deduplication(tmp_path: Path) -> None:
    db_file = tmp_path / "test_ac3.sqlite3"
    _init_test_db(db_file)
    with sqlite3.connect(db_file) as conn:
        _insert_run(conn, "R1", "2026-01-01T10:00:00Z")
        _insert_run(conn, "R2", "2026-02-01T10:00:00Z")

        # Single cell C1 referenced by both R1 and R2
        _insert_cell(conn, "c1", "BIG_LOTTO", "S1", "v1", "101", "2026-01-02")
        _link_run_cell(conn, "R1", "c1")
        _link_run_cell(conn, "R2", "c1")

        # C1 has 5 tickets in tickets table
        for pos in range(1, 6):
            _insert_ticket(conn, "c1", pos, [pos, 10, 11, 12, 13, 14], [1])

    store = SQLiteBackfillStore(db_file)
    res = store.discover_strategy_runs("BIG_LOTTO", "S1", "v1")

    assert res["total_run_version_matches"] == 2
    for item in res["items"]:
        # Each run references C1 once -> associated_cell_count is 1
        assert item["associated_cell_count"] == 1
        # Target draw identity count is 1 (not 5 tickets, not duplicated)
        assert item["unique_target_draw_count"] == 1


def test_ac4_execution_conflict_preservation(tmp_path: Path) -> None:
    db_file = tmp_path / "test_ac4.sqlite3"
    _init_test_db(db_file)
    with sqlite3.connect(db_file) as conn:
        _insert_run(conn, "R1", "2026-01-01T10:00:00Z")

        # Two different executions for the SAME target draw 101
        _insert_cell(
            conn,
            "c1_a",
            "BIG_LOTTO",
            "S1",
            "v1",
            "101",
            "2026-01-02",
            execution_version="ev1",
            dataset_identity="ds1",
            execution_status="COMPLETE",
        )
        _insert_cell(
            conn,
            "c1_b",
            "BIG_LOTTO",
            "S1",
            "v1",
            "101",
            "2026-01-02",
            execution_version="ev2",
            dataset_identity="ds2",
            execution_status="FAILED",
        )
        # One cell for target draw 102
        _insert_cell(
            conn,
            "c2",
            "BIG_LOTTO",
            "S1",
            "v1",
            "102",
            "2026-01-05",
            execution_version="ev1",
            dataset_identity="ds1",
            execution_status="COMPLETE",
        )
        _link_run_cell(conn, "R1", "c1_a")
        _link_run_cell(conn, "R1", "c1_b")
        _link_run_cell(conn, "R1", "c2")

    store = SQLiteBackfillStore(db_file)
    res = store.discover_strategy_runs("BIG_LOTTO", "S1", "v1")

    assert res["total_run_version_matches"] == 1
    item = res["items"][0]
    assert item["associated_cell_count"] == 3
    assert item["unique_target_draw_count"] == 2  # draws 101 and 102
    assert item["execution_identity_count"] == 2  # (ev1, ds1) and (ev2, ds2)
    assert item["execution_status_counts"] == {"COMPLETE": 2, "FAILED": 1}
    # Neither execution is discarded or picked as winner


def test_ac5_status_counts_separation(tmp_path: Path) -> None:
    db_file = tmp_path / "test_ac5.sqlite3"
    _init_test_db(db_file)
    statuses = [
        "COMPLETE",
        "FAILED",
        "NOT_ELIGIBLE",
        "TYPED_CLOSURE",
        "MISSING",
        "PARTIAL",
        "ARTIFACT_ONLY",
    ]
    with sqlite3.connect(db_file) as conn:
        _insert_run(conn, "R1", "2026-01-01T10:00:00Z")
        for i, st in enumerate(statuses):
            cid = f"c_{st}"
            _insert_cell(
                conn,
                cid,
                "BIG_LOTTO",
                "S1",
                "v1",
                str(100 + i),
                f"2026-01-{i + 1:02d}",
                execution_status=st,
            )
            _link_run_cell(conn, "R1", cid)

        # Add another COMPLETE cell that has a 0-hit ticket (legal 0 win)
        _insert_cell(
            conn,
            "c_complete_0hit",
            "BIG_LOTTO",
            "S1",
            "v1",
            "200",
            "2026-01-20",
            execution_status="COMPLETE",
        )
        _link_run_cell(conn, "R1", "c_complete_0hit")
        _insert_ticket(conn, "c_complete_0hit", 1, main_hit_count=0, special_hit=0)

    store = SQLiteBackfillStore(db_file)
    res = store.discover_strategy_runs("BIG_LOTTO", "S1", "v1")

    item = res["items"][0]
    expected_counts = {
        "ARTIFACT_ONLY": 1,
        "COMPLETE": 2,  # 1 original + 1 legal 0-hit
        "FAILED": 1,
        "MISSING": 1,
        "NOT_ELIGIBLE": 1,
        "PARTIAL": 1,
        "TYPED_CLOSURE": 1,
    }
    assert item["execution_status_counts"] == expected_counts
    # FAILED is NOT converted to 0-win, and legal 0-win is NOT converted to FAILED


def test_ac6_pagination_and_deterministic_order(tmp_path: Path) -> None:
    db_file = tmp_path / "test_ac6.sqlite3"
    _init_test_db(db_file)
    runs = [
        ("R1", "2026-01-01T10:00:00Z"),
        ("R2", "2026-02-01T10:00:00Z"),
        ("R3", "2026-03-01T10:00:00Z"),
        ("R4", "2026-04-01T10:00:00Z"),
    ]
    with sqlite3.connect(db_file) as conn:
        for r_id, created in runs:
            _insert_run(conn, r_id, created)
            _insert_inventory(conn, r_id, "BIG_LOTTO", "S1", "v1")

    store = SQLiteBackfillStore(db_file)

    # Full query
    res_full = store.discover_strategy_runs("BIG_LOTTO", "S1", "v1", limit=50, offset=0)
    assert res_full["total_run_version_matches"] == 4
    assert [it["run_id"] for it in res_full["items"]] == ["R4", "R3", "R2", "R1"]
    assert res_full["has_more"] is False

    # Page 1: limit 1, offset 0 -> R4
    res_p1 = store.discover_strategy_runs("BIG_LOTTO", "S1", "v1", limit=1, offset=0)
    assert res_p1["total_run_version_matches"] == 4
    assert [it["run_id"] for it in res_p1["items"]] == ["R4"]
    assert res_p1["has_more"] is True

    # Page 2: limit 2, offset 1 -> R3, R2
    res_p2 = store.discover_strategy_runs("BIG_LOTTO", "S1", "v1", limit=2, offset=1)
    assert res_p2["total_run_version_matches"] == 4
    assert [it["run_id"] for it in res_p2["items"]] == ["R3", "R2"]
    assert res_p2["has_more"] is True

    # Page 3: limit 2, offset 2 -> R2, R1
    res_p3 = store.discover_strategy_runs("BIG_LOTTO", "S1", "v1", limit=2, offset=2)
    assert res_p3["total_run_version_matches"] == 4
    assert [it["run_id"] for it in res_p3["items"]] == ["R2", "R1"]
    assert res_p3["has_more"] is False

    # Page beyond end: offset 4
    res_empty = store.discover_strategy_runs("BIG_LOTTO", "S1", "v1", limit=2, offset=4)
    assert res_empty["total_run_version_matches"] == 4
    assert res_empty["items"] == []
    assert res_empty["has_more"] is False


def test_ac6_parameter_validation(tmp_path: Path) -> None:
    db_file = tmp_path / "test_param_val.sqlite3"
    _init_test_db(db_file)
    store = SQLiteBackfillStore(db_file)

    # limit validation
    for bad_limit in [-1, 0, 251, 1.5, float("nan"), float("inf"), True, "50"]:
        with pytest.raises(ValueError):
            store.discover_strategy_runs("BIG_LOTTO", "S1", limit=bad_limit)  # type: ignore[arg-type]

    # offset validation
    for bad_offset in [-1, 1.5, float("nan"), float("inf"), True, 9_007_199_254_740_992]:
        with pytest.raises(ValueError):
            store.discover_strategy_runs("BIG_LOTTO", "S1", offset=bad_offset)  # type: ignore[arg-type]

    # lottery_type validation
    for bad_lt in ["", "   ", 123, None]:
        with pytest.raises(ValueError):
            store.discover_strategy_runs(bad_lt, "S1")  # type: ignore[arg-type]

    # strategy_id validation
    for bad_sid in ["", "   ", 123, None]:
        with pytest.raises(ValueError):
            store.discover_strategy_runs("BIG_LOTTO", bad_sid)  # type: ignore[arg-type]

    # strategy_version validation
    for bad_ver in ["", "   ", 123]:
        with pytest.raises(ValueError):
            store.discover_strategy_runs("BIG_LOTTO", "S1", bad_ver)  # type: ignore[arg-type]


def test_ac7_parameter_binding_and_read_only(tmp_path: Path) -> None:
    db_file = tmp_path / "test_ac7.sqlite3"
    _init_test_db(db_file)
    with sqlite3.connect(db_file) as conn:
        _insert_run(conn, "R1", "2026-01-01T10:00:00Z")
        _insert_inventory(conn, "R1", "BIG_LOTTO", "S1", "v1")

    # SQL injection string in strategy_id
    store = SQLiteBackfillStore(db_file, read_only=True)
    injection_id = "S1' OR '1'='1"
    res = store.discover_strategy_runs("BIG_LOTTO", injection_id)
    assert res["total_run_version_matches"] == 0
    assert res["items"] == []

    # Read-only store executes normal query safely
    res_normal = store.discover_strategy_runs("BIG_LOTTO", "S1")
    assert res_normal["total_run_version_matches"] == 1


def test_ac8_empty_results_and_indeterminate_state(tmp_path: Path) -> None:
    db_file = tmp_path / "test_ac8.sqlite3"
    _init_test_db(db_file)
    store = SQLiteBackfillStore(db_file)

    res = store.discover_strategy_runs("BIG_LOTTO", "non_existent_strategy")
    assert res["total_run_version_matches"] == 0
    assert res["items"] == []
    assert res["has_more"] is False
    assert "win_rate" not in res
    assert "cross_run_success_rate" not in res
