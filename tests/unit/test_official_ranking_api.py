# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false
import hashlib
import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import lottolab.infrastructure.persistence.replay_backfill_store as store_module
import lottolab.interfaces.api.replay_backfill as api_module
from lottolab.application.replay_official_ranking import (
    _aggregate_ranking_materialized,
    aggregate_ranking,
)
from lottolab.domain.draws import LotteryType
from lottolab.infrastructure.persistence.replay_backfill_store import (
    SCHEMA_CHECKSUM,
    SCHEMA_SQL,
    SCHEMA_VERSION,
    SQLiteBackfillStore,
)


def _normalized_rows(rows: list[dict[str, Any]]) -> list[str]:
    return sorted(json.dumps(v, sort_keys=True) for v in json.loads(json.dumps(rows)))


def _insert_run_inventory(
    connection: sqlite3.Connection,
    run_id: str,
    lottery_type: str,
    strategy_id: str,
    strategy_version: str,
    *,
    target_count: int,
) -> None:
    connection.execute(
        "INSERT INTO replay_backfill_strategy_inventory "
        "(run_id,lottery_type,strategy_id,strategy_version,display_name,lifecycle_status,"
        "data_status,source_kind,executable,available_target_count,training_status,"
        "source_identity) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            run_id,
            lottery_type,
            strategy_id,
            strategy_version,
            strategy_id,
            "ONLINE",
            "REBUILDABLE",
            "NATIVE_REPLAY",
            1,
            target_count,
            "UNKNOWN",
            "fixture",
        ),
    )


def _insert_ranking_run(
    connection: sqlite3.Connection,
    run_id: str,
    strategy_pairs: list[tuple[str, str]],
    target_ids: list[str],
    *,
    declared_target_ids: list[str] | None = None,
    stored_expected_cells: int | None = None,
    manifest_expected_cells: int | None = None,
) -> None:
    declared_ids = target_ids if declared_target_ids is None else declared_target_ids
    unique_strategy_pairs = list(dict.fromkeys(strategy_pairs))
    expected = len(set(declared_ids)) * len(unique_strategy_pairs)
    targets = [
        {
            "draw_number": draw_id,
            "draw_date": (date(2026, 1, 1) + timedelta(days=int(draw_id) - 1)).isoformat(),
            "main_numbers": [1, 2, 3, 4, 5, 6],
            "special_numbers": [7],
            "source_identity": "dataset",
        }
        for draw_id in declared_ids
    ]
    manifest = {
        "lottery_type": "BIG_LOTTO",
        "execution_version": "execution-v1",
        "dataset_identity": "dataset-v1",
        "strategies": [
            {
                "strategy_id": strategy_id,
                "strategy_version": strategy_version,
                "strategy_name": strategy_id,
            }
            for strategy_id, strategy_version in strategy_pairs
        ],
        "target_draw_ids": declared_ids,
        "targets": targets,
        "expected_cells": expected if manifest_expected_cells is None else manifest_expected_cells,
    }
    connection.execute(
        "INSERT INTO replay_backfill_runs(run_id,manifest_json,expected_cells) VALUES (?,?,?)",
        (
            run_id,
            json.dumps(manifest),
            expected if stored_expected_cells is None else stored_expected_cells,
        ),
    )
    for strategy_id, strategy_version in unique_strategy_pairs:
        _insert_run_inventory(
            connection,
            run_id,
            "BIG_LOTTO",
            strategy_id,
            strategy_version,
            target_count=len(set(declared_ids)),
        )
    for draw_id in set(declared_ids):
        target = next(item for item in targets if item["draw_number"] == draw_id)
        connection.execute(
            "INSERT INTO replay_backfill_targets VALUES (?,?,?,?,?,?,?)",
            (
                run_id,
                "BIG_LOTTO",
                draw_id,
                target["draw_date"],
                json.dumps(target["main_numbers"]),
                json.dumps(target["special_numbers"]),
                "dataset",
            ),
        )


def _insert_ranking_cell(
    connection: sqlite3.Connection,
    run_id: str,
    strategy_id: str,
    strategy_version: str,
    draw_id: str,
    *,
    status: str = "COMPLETE",
) -> None:
    cell_id = f"{run_id}:{strategy_id}:{strategy_version}:{draw_id}"
    draw_date = (date(2026, 1, 1) + timedelta(days=int(draw_id) - 1)).isoformat()
    ticket = [1, 2, 7, 8, 9, 10]
    payload: dict[str, Any] = {}
    if status == "COMPLETE":
        payload = {
            "expected_native_ticket_count": 1,
            "predicted_tickets": [
                {"ticket_position": 1, "main_numbers": ticket, "special_number": None}
            ],
            "winning_numbers": {"main_numbers": [1, 2, 3, 4, 5, 6], "special_number": 7},
        }
    connection.execute(
        "INSERT INTO replay_backfill_cells(cell_identity,lottery_type,strategy_id,"
        "strategy_version,execution_version,dataset_identity,target_draw_id,target_draw_date,"
        "execution_status,result_identity,payload_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            cell_id,
            "BIG_LOTTO",
            strategy_id,
            strategy_version,
            "execution-v1",
            "dataset-v1",
            draw_id,
            draw_date,
            status,
            f"result:{cell_id}",
            json.dumps(payload),
        ),
    )
    connection.execute("INSERT INTO replay_backfill_run_cells VALUES (?,?)", (run_id, cell_id))
    if status == "COMPLETE":
        connection.execute(
            "INSERT INTO replay_backfill_tickets(cell_identity,ticket_position,"
            "main_numbers_json,special_numbers_json) VALUES (?,?,?,?)",
            (cell_id, 1, json.dumps(ticket), "[]"),
        )


def _ranking_client(database: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(store_module, "validate_database_path", lambda path: path)
    monkeypatch.setattr(
        api_module,
        "project_database_environment",
        lambda _: {"LOTTOLAB_REPLAY_BACKFILL_DB": str(database)},
    )
    monkeypatch.setattr(
        api_module, "load_replay_strategy_inventory", lambda: SimpleNamespace(items=[])
    )
    app = FastAPI()
    app.include_router(
        api_module.create_replay_backfill_router(SQLiteBackfillStore(database, read_only=True))
    )
    return TestClient(app)


def test_official_ranking_api_uses_saved_tickets_and_unknown_power(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "fixture.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript(SCHEMA_SQL)
        connection.execute(
            "INSERT INTO replay_backfill_schema VALUES (?,?)", (SCHEMA_VERSION, SCHEMA_CHECKSUM)
        )
        for lottery, run in [("BIG_LOTTO", "b"), ("POWER_LOTTO", "p"), ("DAILY_539", "d")]:
            is_daily = lottery == "DAILY_539"
            winning = [1, 2, 3, 4, 5] if is_daily else [1, 2, 3, 4, 5, 6]
            ticket = [1, 2, 8, 9, 10] if is_daily else [1, 2, 3, 8, 9, 10]
            if lottery == "BIG_LOTTO":
                ticket = [1, 2, 7, 8, 9, 10]
            special = None if is_daily else 7
            connection.execute(
                "INSERT INTO replay_backfill_runs(run_id,manifest_json,expected_cells) "
                "VALUES (?, ?, ?)",
                (
                    run,
                    json.dumps(
                        {
                            "lottery_type": lottery,
                            "execution_version": "e",
                            "dataset_identity": "d",
                            "strategies": [
                                {
                                    "strategy_id": "unregistered",
                                    "strategy_version": "v",
                                    "strategy_name": "Unregistered",
                                }
                            ],
                            "target_draw_ids": ["1"],
                            "expected_cells": 1,
                            "targets": [
                                {
                                    "draw_number": "1",
                                    "draw_date": "2026-01-01",
                                    "main_numbers": winning,
                                    "special_numbers": [] if special is None else [special],
                                    "source_identity": "source",
                                }
                            ],
                        }
                    ),
                    1,
                ),
            )
            _insert_run_inventory(connection, run, lottery, "unregistered", "v", target_count=1)
            connection.execute(
                "INSERT INTO replay_backfill_targets VALUES (?,?,?,?,?,?,?)",
                (
                    run,
                    lottery,
                    "1",
                    "2026-01-01",
                    json.dumps(winning),
                    json.dumps([] if special is None else [special]),
                    "source",
                ),
            )
            payload = {
                "expected_native_ticket_count": 1,
                "predicted_tickets": [
                    {
                        "ticket_position": 1,
                        "main_numbers": ticket,
                        "special_number": None,
                    }
                ],
                "winning_numbers": {"main_numbers": winning, "special_number": special},
            }
            connection.execute(
                "INSERT INTO replay_backfill_cells(cell_identity,lottery_type,strategy_id,"
                "strategy_version,execution_version,dataset_identity,target_draw_id,target_draw_date,"
                "execution_status,result_identity,payload_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    run,
                    lottery,
                    "unregistered",
                    "v",
                    "e",
                    "d",
                    "1",
                    "2026-01-01",
                    "COMPLETE",
                    "result",
                    json.dumps(payload),
                ),
            )
            connection.execute("INSERT INTO replay_backfill_run_cells VALUES (?,?)", (run, run))
            connection.execute(
                "INSERT INTO replay_backfill_tickets(cell_identity,ticket_position,"
                "main_numbers_json,special_numbers_json) VALUES (?,?,?,?)",
                (run, 1, json.dumps(ticket), "[]"),
            )
    monkeypatch.setattr(store_module, "validate_database_path", lambda p: p)
    monkeypatch.setattr(
        api_module,
        "project_database_environment",
        lambda _: {"LOTTOLAB_REPLAY_BACKFILL_DB": str(database)},
    )
    monkeypatch.setattr(
        api_module, "load_replay_strategy_inventory", lambda: SimpleNamespace(items=[])
    )
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    app = FastAPI()
    app.include_router(
        api_module.create_replay_backfill_router(SQLiteBackfillStore(database, read_only=True))
    )
    client = TestClient(app)
    for lottery in (LotteryType.BIG_LOTTO, LotteryType.POWER_LOTTO, LotteryType.DAILY_539):
        response = client.get(
            "/api/v1/replay-backfill/official-ranking",
            params={"lottery_type": lottery.value, "window": "RECENT_50"},
        )
        assert response.status_code == 200, response.text
        row = response.json()["items"][0]
        assert row["registered"] is False
        assert row["ticket_count"] == 1
        if lottery != LotteryType.POWER_LOTTO:
            assert (row["successes"], row["evaluated"], row["rank"]) == (1, 1, 1)
        else:
            assert (row["unknown"], row["rate"], row["baseline"], row["rank"]) == (
                1,
                None,
                None,
                None,
            )
    # General Prize (three main hits without special) is outside the event.
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE replay_backfill_tickets SET main_numbers_json=? WHERE cell_identity='b'",
            (json.dumps([1, 2, 3, 8, 9, 10]),),
        )
        connection.execute(
            "UPDATE replay_backfill_cells SET payload_json=json_set(payload_json, "
            "'$.predicted_tickets[0].main_numbers', json(?)) WHERE cell_identity='b'",
            (json.dumps([1, 2, 3, 8, 9, 10]),),
        )
    general_response = client.get(
        "/api/v1/replay-backfill/official-ranking",
        params={"lottery_type": "BIG_LOTTO", "window": "RECENT_50"},
    )
    assert general_response.status_code == 200
    general = general_response.json()["items"][0]
    assert (general["successes"], general["evaluated"]) == (0, 1)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE replay_backfill_tickets SET main_numbers_json=? WHERE cell_identity='b'",
            (json.dumps([1, 2, 7, 8, 9, 10]),),
        )
        connection.execute(
            "UPDATE replay_backfill_cells SET payload_json=json_set(payload_json, "
            "'$.predicted_tickets[0].main_numbers', json(?)) WHERE cell_identity='b'",
            (json.dumps([1, 2, 7, 8, 9, 10]),),
        )
    # Compare the run-streamed reducer with the prior materialized reducer
    # after the JSON round trip for each lottery and every requested window.
    for lottery in ("BIG_LOTTO", "POWER_LOTTO", "DAILY_539"):
        for window in ("FULL", "RECENT_750", "RECENT_300", "RECENT_50"):
            with SQLiteBackfillStore(database, read_only=True).official_ranking_data(
                lottery, window
            ) as (targets, cells):
                evidence = list(cells)
            old = _aggregate_ranking_materialized(lottery, window, targets, evidence, {})
            new = aggregate_ranking(lottery, window, targets, iter(evidence), {})
            assert _normalized_rows(new) == _normalized_rows(old)
    # Missing saved tickets must not be treated as a complete one-ticket set.
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE replay_backfill_cells SET payload_json=json_set(payload_json, "
            "'$.expected_native_ticket_count', 2) WHERE cell_identity='b'"
        )
    incomplete = client.get(
        "/api/v1/replay-backfill/official-ranking",
        params={"lottery_type": "BIG_LOTTO", "window": "RECENT_50"},
    ).json()["items"][0]
    assert (incomplete["unknown"], incomplete["evaluated"], incomplete["rank"]) == (1, 0, None)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE replay_backfill_cells SET payload_json=json_set(payload_json, "
            "'$.expected_native_ticket_count', 1) WHERE cell_identity='b'"
        )
    with sqlite3.connect(database) as connection:
        original = connection.execute(
            "SELECT manifest_json FROM replay_backfill_runs WHERE run_id='b'"
        ).fetchone()[0]
        manifest = json.loads(original)
        manifest["target_draw_ids"].append("2")
        connection.execute(
            "UPDATE replay_backfill_runs SET manifest_json=? WHERE run_id='b'",
            (json.dumps(manifest),),
        )
    uncertain = client.get(
        "/api/v1/replay-backfill/official-ranking",
        params={"lottery_type": "BIG_LOTTO", "window": "RECENT_50"},
    ).json()["items"][0]
    assert uncertain["scope_status"] == "WINDOW_UNDETERMINED"
    assert (uncertain["evaluated"], uncertain["rate"], uncertain["rank"]) == (0, None, None)
    for invalid_ids in (["1", "1"], "invalid"):
        invalid = json.loads(original)
        invalid["target_draw_ids"] = invalid_ids
        # Avoid fallback to the valid target list for the malformed-list case.
        invalid.pop("targets", None)
        with sqlite3.connect(database) as connection:
            connection.execute(
                "UPDATE replay_backfill_runs SET manifest_json=? WHERE run_id='b'",
                (json.dumps(invalid),),
            )
        row = client.get(
            "/api/v1/replay-backfill/official-ranking",
            params={"lottery_type": "BIG_LOTTO", "window": "RECENT_50"},
        ).json()["items"][0]
        assert row["scope_status"] == "WINDOW_UNDETERMINED"
        assert (row["evaluated"], row["rate"], row["rank"]) == (0, None, None)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE replay_backfill_runs SET manifest_json=? WHERE run_id='b'", (original,)
        )
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    assert (
        client.get(
            "/api/v1/replay-backfill/official-ranking",
            params={"lottery_type": "BIG_LOTTO", "window": "INVALID"},
        ).status_code
        == 422
    )
    monkeypatch.setattr(api_module, "project_database_environment", lambda _: {})
    assert (
        client.get(
            "/api/v1/replay-backfill/official-ranking", params={"lottery_type": "BIG_LOTTO"}
        ).json()["error_code"]
        == "OFFICIAL_REPLAY_DATABASE_MISMATCH"
    )
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before


def test_recent_window_reads_only_selected_tickets_and_keeps_older_cohort(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "fixture.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript(SCHEMA_SQL)
        connection.execute(
            "INSERT INTO replay_backfill_schema VALUES (?,?)", (SCHEMA_VERSION, SCHEMA_CHECKSUM)
        )
        connection.execute(
            "INSERT INTO replay_backfill_runs(run_id,manifest_json,expected_cells) "
            "VALUES ('daily',?,102)",
            (
                json.dumps(
                    {
                        "lottery_type": "DAILY_539",
                        "execution_version": "e1",
                        "dataset_identity": "data1",
                        "strategies": [
                            {
                                "strategy_id": strategy_id,
                                "strategy_version": "v1",
                                "strategy_name": strategy_id,
                            }
                            for strategy_id in ("old-only", "recent")
                        ],
                        "target_draw_ids": [str(i) for i in range(1, 52)],
                        "expected_cells": 102,
                        "targets": [
                            {
                                "draw_number": str(i),
                                "draw_date": (date(2026, 1, 1) + timedelta(days=i - 1)).isoformat(),
                                "main_numbers": [1, 2, 3, 4, 5],
                                "special_numbers": [],
                                "source_identity": "source",
                            }
                            for i in range(1, 52)
                        ],
                    }
                ),
            ),
        )
        for strategy_id in ("old-only", "recent"):
            _insert_run_inventory(
                connection, "daily", "DAILY_539", strategy_id, "v1", target_count=51
            )
        for index in range(51):
            draw_id = str(index + 1)
            draw_date = (date(2026, 1, 1) + timedelta(days=index)).isoformat()
            connection.execute(
                "INSERT INTO replay_backfill_targets VALUES (?,?,?,?,?,?,?)",
                (
                    "daily",
                    "DAILY_539",
                    draw_id,
                    draw_date,
                    "[1,2,3,4,5]",
                    "[]",
                    "source",
                ),
            )
        for identity, strategy, index in (
            ("old-cell", "old-only", 0),
            ("recent-cell", "recent", 50),
        ):
            draw_id = str(index + 1)
            draw_date = (date(2026, 1, 1) + timedelta(days=index)).isoformat()
            connection.execute(
                "INSERT INTO replay_backfill_cells(cell_identity,lottery_type,strategy_id,"
                "strategy_version,execution_version,dataset_identity,target_draw_id,target_draw_date,"
                "execution_status,result_identity,payload_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    identity,
                    "DAILY_539",
                    strategy,
                    "v1",
                    "e1",
                    "data1",
                    draw_id,
                    draw_date,
                    "COMPLETE",
                    "result",
                    json.dumps(
                        {
                            "expected_native_ticket_count": 1,
                            "predicted_tickets": [
                                {
                                    "ticket_position": 1,
                                    "main_numbers": [1, 2, 6, 7, 8],
                                    "special_number": None,
                                }
                            ],
                        }
                    ),
                ),
            )
            connection.execute(
                "INSERT INTO replay_backfill_run_cells VALUES ('daily',?)", (identity,)
            )
            connection.execute(
                "INSERT INTO replay_backfill_tickets(cell_identity,ticket_position,"
                "main_numbers_json,special_numbers_json) VALUES (?,?,?,?)",
                (identity, 1, "[1,2,6,7,8]", "[]"),
            )
        connection.execute(
            "INSERT INTO replay_backfill_cells(cell_identity,lottery_type,strategy_id,"
            "strategy_version,execution_version,dataset_identity,target_draw_id,target_draw_date,"
            "execution_status,result_identity,payload_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                "unlinked-cell",
                "DAILY_539",
                "unlinked",
                "v1",
                "e1",
                "data1",
                "52",
                "2026-02-21",
                "COMPLETE",
                "result",
                "{}",
            ),
        )
        connection.execute(
            "INSERT INTO replay_backfill_tickets(cell_identity,ticket_position,"
            "main_numbers_json,special_numbers_json) VALUES (?,?,?,?)",
            ("unlinked-cell", 1, "[1,2,6,7,8]", "[]"),
        )

    monkeypatch.setattr(store_module, "validate_database_path", lambda path: path)
    store = SQLiteBackfillStore(database, read_only=True)
    with store.official_ranking_data("DAILY_539", "RECENT_50") as (targets, cells):
        selected = list(cells)
    assert len(targets) == 50
    old_cell = next(cell for cell in selected if cell["strategy_id"] == "old-only")
    recent_cell = next(
        cell
        for cell in selected
        if cell["strategy_id"] == "recent" and cell["ranking_window_included"]
    )
    unlinked_cell = next(cell for cell in selected if cell["run_id"] == "UNLINKED")
    assert old_cell["ranking_window_included"] is False
    assert old_cell["tickets"] == []
    assert recent_cell["ranking_window_included"] is True
    assert len(recent_cell["tickets"]) == 1
    assert unlinked_cell["tickets"] == []
    assert unlinked_cell["ticket_count"] == 1

    rows = aggregate_ranking("DAILY_539", "RECENT_50", targets, selected, {})
    old_row = next(row for row in rows if row["strategy_id"] == "old-only")
    recent_row = next(row for row in rows if row["strategy_id"] == "recent")
    unlinked_row = next(row for row in rows if row["strategy_id"] == "unlinked")
    assert (old_row["ticket_count"], old_row["evaluated"], old_row["missing"]) == (None, 0, 50)
    assert (
        recent_row["ticket_count"],
        recent_row["successes"],
        recent_row["evaluated"],
    ) == (1, 1, 1)
    assert (unlinked_row["ticket_count"], unlinked_row["evaluated"], unlinked_row["unknown"]) == (
        1,
        0,
        1,
    )


def test_manifest_scope_excludes_history_and_keeps_missing_targets_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "scope.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript(SCHEMA_SQL)
        connection.execute(
            "INSERT INTO replay_backfill_schema VALUES (?,?)", (SCHEMA_VERSION, SCHEMA_CHECKSUM)
        )
        for run, ids in (("history", ["201", "202"]), ("no-target", ["301"])):
            manifest: dict[str, Any] = {
                "lottery_type": "DAILY_539",
                "execution_version": "e",
                "dataset_identity": "d",
                "strategies": [{"strategy_id": "s", "strategy_version": "v", "strategy_name": "S"}],
                "target_draw_ids": ids,
                "expected_cells": len(ids),
            }
            if run == "history":
                manifest["targets"] = [
                    {
                        "draw_number": draw,
                        "draw_date": (date(2025, 1, 1) + timedelta(days=int(draw))).isoformat(),
                        "main_numbers": [1, 2, 3, 4, 5],
                        "special_numbers": [],
                        "source_identity": "source",
                    }
                    for draw in ids
                ]
            connection.execute(
                "INSERT INTO replay_backfill_runs(run_id,manifest_json,expected_cells) "
                "VALUES (?,?,?)",
                (run, json.dumps(manifest), len(ids)),
            )
            _insert_run_inventory(connection, run, "DAILY_539", "s", "v", target_count=len(ids))
        for index in range(1, 203):
            connection.execute(
                "INSERT INTO replay_backfill_targets VALUES (?,?,?,?,?,?,?)",
                (
                    "history",
                    "DAILY_539",
                    str(index),
                    (date(2025, 1, 1) + timedelta(days=index)).isoformat(),
                    "[1,2,3,4,5]",
                    "[]",
                    "source",
                ),
            )
        for run, draw, identity in (
            ("history", "201", "in"),
            ("history", "202", "in-second"),
            ("history", "2", "outside"),
            ("no-target", "301", "unknown"),
        ):
            draw_date = (date(2025, 1, 1) + timedelta(days=int(draw))).isoformat()
            payload = {
                "expected_native_ticket_count": 1,
                "predicted_tickets": [
                    {"ticket_position": 1, "main_numbers": [1, 2, 6, 7, 8], "special_number": None}
                ],
            }
            connection.execute(
                "INSERT INTO replay_backfill_cells(cell_identity,lottery_type,strategy_id,"
                "strategy_version,execution_version,dataset_identity,target_draw_id,target_draw_date,"
                "execution_status,result_identity,payload_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    identity,
                    "DAILY_539",
                    "s",
                    "v",
                    "e",
                    "d",
                    draw,
                    draw_date,
                    "COMPLETE",
                    "result",
                    json.dumps(payload),
                ),
            )
            connection.execute(
                "INSERT INTO replay_backfill_run_cells VALUES (?,?)", (run, identity)
            )
            connection.execute(
                "INSERT INTO replay_backfill_tickets(cell_identity,ticket_position,"
                "main_numbers_json,special_numbers_json) VALUES (?,?,?,?)",
                (identity, 1, "[1,2,6,7,8]", "[]"),
            )
    monkeypatch.setattr(store_module, "validate_database_path", lambda p: p)
    with SQLiteBackfillStore(database, read_only=True).official_ranking_data(
        "DAILY_539", "FULL"
    ) as (targets, cells):
        assert {t["target_draw_id"] for t in targets if t["run_id"] == "history"} == {"201", "202"}
        evidence = list(cells)
        rows = aggregate_ranking("DAILY_539", "FULL", targets, iter(evidence), {})
        old = _aggregate_ranking_materialized("DAILY_539", "FULL", targets, evidence, {})
        assert _normalized_rows(rows) == _normalized_rows(old)
    scoped = next(r for r in rows if r["run_id"] == "history" and r["scope_status"] == "MANIFEST")
    assert (scoped["evaluated"], scoped["missing"]) == (2, 0)
    outside = next(r for r in rows if r["scope_status"] == "OUTSIDE_MANIFEST")
    assert (outside["unknown"], outside["missing"], outside["rank"]) == (1, 0, None)
    missing_target = next(r for r in rows if r["run_id"] == "no-target")
    assert (missing_target["unknown"], missing_target["evaluated"], missing_target["rank"]) == (
        1,
        0,
        None,
    )

    # A dated manifest can use a complete, source-bound target row.
    with sqlite3.connect(database) as connection:
        original_manifest = connection.execute(
            "SELECT manifest_json FROM replay_backfill_runs WHERE run_id='history'"
        ).fetchone()[0]
        partial = json.loads(original_manifest)
        partial["targets"][0].pop("main_numbers")
        connection.execute(
            "UPDATE replay_backfill_runs SET manifest_json=? WHERE run_id='history'",
            (json.dumps(partial),),
        )
    with SQLiteBackfillStore(database, read_only=True).official_ranking_data(
        "DAILY_539", "FULL"
    ) as (targets, cells):
        rows = aggregate_ranking("DAILY_539", "FULL", targets, cells, {})
    scoped = next(r for r in rows if r["run_id"] == "history" and r["scope_status"] == "MANIFEST")
    assert (scoped["evaluated"], scoped["unknown"], scoped["missing_target_evidence"]) == (2, 0, 0)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE replay_backfill_runs SET manifest_json=? WHERE run_id='history'",
            (original_manifest,),
        )

    # The same draw in a different order is still the same draw.
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE replay_backfill_targets SET actual_main_numbers_json='[5,4,3,2,1]' "
            "WHERE run_id='history' AND target_draw_id='201'"
        )
    with SQLiteBackfillStore(database, read_only=True).official_ranking_data(
        "DAILY_539", "FULL"
    ) as (targets, cells):
        rows = aggregate_ranking("DAILY_539", "FULL", targets, cells, {})
    scoped = next(r for r in rows if r["run_id"] == "history" and r["scope_status"] == "MANIFEST")
    assert (scoped["evaluated"], scoped["missing_target_evidence"]) == (2, 0)

    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE replay_backfill_targets SET source_identity='different' "
            "WHERE run_id='history' AND target_draw_id='201'"
        )
    with SQLiteBackfillStore(database, read_only=True).official_ranking_data(
        "DAILY_539", "FULL"
    ) as (targets, cells):
        rows = aggregate_ranking("DAILY_539", "FULL", targets, cells, {})
    scoped = next(r for r in rows if r["run_id"] == "history" and r["scope_status"] == "MANIFEST")
    assert (scoped["evaluated"], scoped["unknown"], scoped["missing_target_evidence"]) == (1, 1, 1)
    assert scoped["rank"] is None

    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE replay_backfill_targets SET source_identity='source' "
            "WHERE run_id='history' AND target_draw_id='201'"
        )
        old = json.loads(
            connection.execute(
                "SELECT payload_json FROM replay_backfill_cells WHERE cell_identity='in'"
            ).fetchone()[0]
        )
        # A missing special-number field is not a conflict with trusted evidence.
        old["winning_numbers"] = {"main_numbers": [1, 2, 3, 4, 5]}
        connection.execute(
            "UPDATE replay_backfill_cells SET payload_json=? WHERE cell_identity='in'",
            (json.dumps(old),),
        )
    with SQLiteBackfillStore(database, read_only=True).official_ranking_data(
        "DAILY_539", "FULL"
    ) as (targets, cells):
        rows = aggregate_ranking("DAILY_539", "FULL", targets, cells, {})
    scoped = next(r for r in rows if r["run_id"] == "history" and r["scope_status"] == "MANIFEST")
    assert (scoped["evaluated"], scoped["conflicting_target_evidence"]) == (2, 0)
    with sqlite3.connect(database) as connection:
        old["winning_numbers"] = {"main_numbers": [1, 2, 3, 4, 9], "special_number": None}
        connection.execute(
            "UPDATE replay_backfill_cells SET payload_json=? WHERE cell_identity='in'",
            (json.dumps(old),),
        )
        connection.execute(
            "INSERT INTO replay_backfill_cells(cell_identity,lottery_type,strategy_id,"
            "strategy_version,execution_version,dataset_identity,target_draw_id,target_draw_date,"
            "execution_status,result_identity,payload_json) SELECT 'other',lottery_type,'other',"
            "strategy_version,execution_version,dataset_identity,target_draw_id,target_draw_date,"
            "execution_status,result_identity,? FROM replay_backfill_cells "
            "WHERE cell_identity='in'",
            (
                json.dumps(
                    {
                        "expected_native_ticket_count": 1,
                        "predicted_tickets": [
                            {
                                "ticket_position": 1,
                                "main_numbers": [1, 2, 6, 7, 8],
                                "special_number": None,
                            }
                        ],
                    }
                ),
            ),
        )
        connection.execute("INSERT INTO replay_backfill_run_cells VALUES ('history','other')")
        connection.execute(
            "INSERT INTO replay_backfill_tickets(cell_identity,ticket_position,main_numbers_json,"
            "special_numbers_json) VALUES ('other',1,'[1,2,6,7,8]','[]')"
        )
    with SQLiteBackfillStore(database, read_only=True).official_ranking_data(
        "DAILY_539", "FULL"
    ) as (targets, cells):
        rows = aggregate_ranking("DAILY_539", "FULL", targets, cells, {})
    history_rows = [r for r in rows if r["run_id"] == "history" and r["scope_status"] == "MANIFEST"]
    assert len(history_rows) == 2
    assert all(r["conflicting_target_evidence"] == 1 and r["rank"] is None for r in history_rows)
    assert all(r["unknown"] == 1 for r in history_rows)

    # A target without any date makes the recent-window membership unknowable.
    with sqlite3.connect(database) as connection:
        manifest = json.loads(original_manifest)
        manifest["target_draw_ids"].append("999")
        connection.execute(
            "UPDATE replay_backfill_runs SET manifest_json=? WHERE run_id='history'",
            (json.dumps(manifest),),
        )
    with SQLiteBackfillStore(database, read_only=True).official_ranking_data(
        "DAILY_539", "RECENT_50"
    ) as (targets, cells):
        rows = aggregate_ranking("DAILY_539", "RECENT_50", targets, cells, {})
    undetermined = [
        r for r in rows if r["run_id"] == "history" and r["scope_status"] == "WINDOW_UNDETERMINED"
    ]
    assert len(undetermined) == 2
    assert all(
        r["evaluated"] == 0 and r["rate"] is None and r["rank"] is None for r in undetermined
    )
    assert all("窗口無法判定" in r["unknown_reason"] for r in undetermined)


def test_numeric_boundary_store_aggregate_api_and_twelve_windows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import lottolab.application.replay_official_ranking as ranking

    database = tmp_path / "numeric-boundary.sqlite3"
    # This is the independent expected target table, deliberately in reverse order.
    target_table = [(str(i), "2024-01-01") for i in (9, 10, 31)] + [
        (f"later-{i:02}", (date(2024, 1, 1) + timedelta(days=i)).isoformat()) for i in range(1, 50)
    ]
    with sqlite3.connect(database) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.execute(
            "INSERT INTO replay_backfill_schema VALUES (?,?)", (SCHEMA_VERSION, SCHEMA_CHECKSUM)
        )
        for lottery in ("BIG_LOTTO", "POWER_LOTTO", "DAILY_539"):
            daily = lottery == "DAILY_539"
            winning = [1, 2, 3, 4, 5] if daily else [1, 2, 3, 4, 5, 6]
            special = None if daily else 7
            targets = [
                {
                    "draw_number": i,
                    "draw_date": d,
                    "main_numbers": winning,
                    "special_numbers": [] if daily else [7],
                    "source_identity": "source",
                }
                for i, d in reversed(target_table)
            ]
            conn.execute(
                "INSERT INTO replay_backfill_runs(run_id,manifest_json,expected_cells) "
                "VALUES (?,?,?)",
                (
                    lottery,
                    json.dumps(
                        {
                            "lottery_type": lottery,
                            "execution_version": "e",
                            "dataset_identity": "d",
                            "strategies": [
                                {"strategy_id": "s", "strategy_version": "v", "strategy_name": "S"}
                            ],
                            "target_draw_ids": [t["draw_number"] for t in targets],
                            "expected_cells": len(targets),
                            "targets": targets,
                        }
                    ),
                    len(targets),
                ),
            )
            _insert_run_inventory(conn, lottery, lottery, "s", "v", target_count=len(targets))
            for item in targets:
                draw_id, draw_date = item["draw_number"], item["draw_date"]
                assert isinstance(draw_id, str)
                assert isinstance(draw_date, str)
                ticket = (
                    ([1, 2, 8, 9, 10] if draw_id == "31" else [1, 8, 9, 10, 11])
                    if daily
                    else ([1, 2, 7, 8, 9, 10] if draw_id == "31" else [1, 8, 9, 10, 11, 12])
                )
                ident = lottery + draw_id
                payload = {
                    "expected_native_ticket_count": 1,
                    "predicted_tickets": [
                        {"ticket_position": 1, "main_numbers": ticket, "special_number": None}
                    ],
                    "winning_numbers": {"main_numbers": winning, "special_number": special},
                }
                conn.execute(
                    "INSERT INTO replay_backfill_targets VALUES (?,?,?,?,?,?,?)",
                    (
                        lottery,
                        lottery,
                        draw_id,
                        draw_date,
                        json.dumps(winning),
                        json.dumps([] if daily else [7]),
                        "source",
                    ),
                )
                conn.execute(
                    "INSERT INTO replay_backfill_cells(cell_identity,lottery_type,strategy_id,"
                    "strategy_version,execution_version,dataset_identity,target_draw_id,"
                    "target_draw_date,execution_status,result_identity,payload_json) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        ident,
                        lottery,
                        "s",
                        "v",
                        "e",
                        "d",
                        draw_id,
                        draw_date,
                        "COMPLETE",
                        "result",
                        json.dumps(payload),
                    ),
                )
                conn.execute("INSERT INTO replay_backfill_run_cells VALUES (?,?)", (lottery, ident))
                conn.execute(
                    "INSERT INTO replay_backfill_tickets(cell_identity,ticket_position,"
                    "main_numbers_json,special_numbers_json) VALUES (?,?,?,?)",
                    (ident, 1, json.dumps(ticket), "[]"),
                )
    monkeypatch.setattr(store_module, "validate_database_path", lambda p: p)
    monkeypatch.setattr(
        api_module,
        "project_database_environment",
        lambda _: {"LOTTOLAB_REPLAY_BACKFILL_DB": str(database)},
    )
    monkeypatch.setattr(
        api_module, "load_replay_strategy_inventory", lambda: SimpleNamespace(items=[])
    )
    store = SQLiteBackfillStore(database, read_only=True)
    app = FastAPI()
    app.include_router(api_module.create_replay_backfill_router(store))
    client = TestClient(app)
    numeric_key = ranking.ranking_target_sort_key
    results = {}
    for lottery in ("BIG_LOTTO", "POWER_LOTTO", "DAILY_539"):
        for window in ("FULL", "RECENT_750", "RECENT_300", "RECENT_50"):
            variants = []
            for key in (lambda d, i: (d, i), numeric_key):
                monkeypatch.setattr(ranking, "ranking_target_sort_key", key)
                monkeypatch.setattr(store_module, "ranking_target_sort_key", key)
                with store.official_ranking_data(lottery, window) as (targets, cells):
                    selected_cells = list(cells)
                    rows = aggregate_ranking(lottery, window, targets, selected_cells, {})
                response = client.get(
                    "/api/v1/replay-backfill/official-ranking",
                    params={"lottery_type": lottery, "window": window},
                )
                assert response.status_code == 200
                row = json.loads(json.dumps(rows))[0]
                assert response.json()["items"][0] == row
                assert {c["target_draw_id"] for c in selected_cells if c["target_draw_id"]} == set(
                    row["target_ids"]
                )
                variants.append(row)
            old, new = variants
            assert old and new
            if window == "RECENT_50":
                expected_ids = ["31"] + [i for i, _ in target_table[3:]]
                assert new["target_ids"] == expected_ids
                assert old["target_ids"] == ["9", *expected_ids[1:]]
                if lottery != "POWER_LOTTO":
                    assert (
                        old["successes"],
                        old["evaluated"],
                        new["successes"],
                        new["evaluated"],
                    ) == (0, 50, 1, 50)
                allowed = {"target_ids", "successes", "rate", "delta"}
                assert {k: v for k, v in old.items() if k not in allowed} == {
                    k: v for k, v in new.items() if k not in allowed
                }
            else:
                assert set(old["target_ids"]) == set(new["target_ids"])
                assert {k: v for k, v in old.items() if k != "target_ids"} == {
                    k: v for k, v in new.items() if k != "target_ids"
                }
            assert (new["missing"], new["unknown"], new["ticket_count"]) == (
                0,
                50
                if lottery == "POWER_LOTTO" and window == "RECENT_50"
                else (52 if lottery == "POWER_LOTTO" else 0),
                1,
            )
            if lottery == "POWER_LOTTO":
                assert (new["baseline"], new["delta"], new["rank"]) == (None, None, None)
            elif lottery == "BIG_LOTTO":
                assert new["baseline"] == float(3629 / 249711)
                assert new["rank"] == 1
            results[(lottery, window)] = new
    assert len(results) == 12


def test_manifest_expected_rows_keep_missing_failed_and_out_of_scope_distinct(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "completeness.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript(SCHEMA_SQL)
        connection.execute(
            "INSERT INTO replay_backfill_schema VALUES (?,?)", (SCHEMA_VERSION, SCHEMA_CHECKSUM)
        )
        strategies = [
            ("complete", "v1"),
            ("empty", "v1"),
            ("partial", "v1"),
            ("status", "v1"),
        ]
        _insert_ranking_run(connection, "run", strategies, ["1", "2"])
        for draw_id in ("1", "2"):
            _insert_ranking_cell(connection, "run", "complete", "v1", draw_id)
        _insert_ranking_cell(connection, "run", "partial", "v1", "1")
        # Two persisted rows equal this identity's two expected targets, but
        # target 3 is outside the immutable manifest and cannot fill target 2.
        _insert_ranking_cell(connection, "run", "partial", "v1", "3")
        _insert_ranking_cell(connection, "run", "status", "v1", "1", status="FAILED")
        _insert_ranking_cell(connection, "run", "status", "v1", "2", status="NOT_ELIGIBLE")
        raw_partial_count = connection.execute(
            "SELECT COUNT(*) FROM replay_backfill_run_cells rc "
            "JOIN replay_backfill_cells c USING(cell_identity) "
            "WHERE rc.run_id='run' AND c.strategy_id='partial'"
        ).fetchone()[0]
        assert raw_partial_count == 2

    client = _ranking_client(database, monkeypatch)
    response = client.get(
        "/api/v1/replay-backfill/official-ranking",
        params={"lottery_type": "BIG_LOTTO", "window": "FULL"},
    )
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    by_id = {row["strategy_id"]: row for row in items if row["run_id"] == "run"}

    empty = by_id["empty"]
    assert empty["target_ids"] == ["1", "2"]
    assert (empty["successes"], empty["evaluated"], empty["missing"], empty["unknown"]) == (
        0,
        0,
        2,
        0,
    )
    assert (empty["rate"], empty["baseline"], empty["delta"], empty["rank"]) == (
        None,
        None,
        None,
        None,
    )

    partial = by_id["partial"]
    assert (partial["evaluated"], partial["missing"], partial["unknown"]) == (1, 1, 0)
    assert (partial["rate"], partial["baseline"], partial["delta"], partial["rank"]) == (
        None,
        None,
        None,
        None,
    )
    assert any(
        row["strategy_id"] == "partial" and row["scope_status"] == "OUTSIDE_MANIFEST"
        for row in items
    )

    status = by_id["status"]
    assert (status["successes"], status["evaluated"], status["missing"], status["unknown"]) == (
        0,
        0,
        0,
        2,
    )
    assert (status["failed_count"], status["not_eligible_count"]) == (1, 1)
    assert (status["rate"], status["baseline"], status["delta"], status["rank"]) == (
        None,
        None,
        None,
        None,
    )
    assert "FAILED" in status["unknown_reason"]
    assert "NOT_ELIGIBLE" in status["unknown_reason"]
    complete = by_id["complete"]
    assert (complete["evaluated"], complete["missing"], complete["rate"], complete["rank"]) == (
        2,
        0,
        1.0,
        1,
    )
    with sqlite3.connect(database) as connection:
        persisted = connection.execute(
            "SELECT c.execution_status FROM replay_backfill_run_cells rc "
            "JOIN replay_backfill_cells c USING(cell_identity) "
            "WHERE rc.run_id='run' AND c.strategy_id='status' ORDER BY c.target_draw_id"
        ).fetchall()
    assert [row[0] for row in persisted] == ["FAILED", "NOT_ELIGIBLE"]


def test_run_without_usable_manifest_identity_is_reported_as_diagnostic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "empty-manifest-identities.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript(SCHEMA_SQL)
        connection.execute(
            "INSERT INTO replay_backfill_schema VALUES (?,?)", (SCHEMA_VERSION, SCHEMA_CHECKSUM)
        )
        _insert_ranking_run(
            connection,
            "run-without-strategies",
            [],
            ["1"],
            stored_expected_cells=1,
            manifest_expected_cells=1,
        )

    client = _ranking_client(database, monkeypatch)
    response = client.get(
        "/api/v1/replay-backfill/official-ranking",
        params={"lottery_type": "BIG_LOTTO", "window": "FULL"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert not any(row["run_id"] == "run-without-strategies" for row in payload["items"])
    diagnostics = payload["run_diagnostics"]
    assert diagnostics == [
        {
            "kind": "INVALID_MANIFEST_NO_STRATEGY_IDENTITY",
            "run_id": "run-without-strategies",
            "matrix_reason": "invalid_manifest_strategies; expected_cells_mismatch",
            "successes": 0,
            "evaluated": 0,
            "denominator": 0,
            "rate": None,
            "baseline": None,
            "delta": None,
            "rank": None,
        }
    ]
    assert "strategy_id" not in diagnostics[0]
    assert "strategy_version" not in diagnostics[0]


def test_invalid_run_matrices_fail_closed_and_historical_versions_stay_separate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "invalid-matrices.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript(SCHEMA_SQL)
        connection.execute(
            "INSERT INTO replay_backfill_schema VALUES (?,?)", (SCHEMA_VERSION, SCHEMA_CHECKSUM)
        )

        _insert_ranking_run(
            connection,
            "duplicate-strategy",
            [("duplicate", "v1"), ("duplicate", "v1")],
            ["1"],
        )
        _insert_ranking_cell(connection, "duplicate-strategy", "duplicate", "v1", "1")

        _insert_ranking_run(
            connection,
            "mismatched-count",
            [("mismatch", "v1")],
            ["1", "2"],
            stored_expected_cells=1,
            manifest_expected_cells=1,
        )
        for draw_id in ("1", "2"):
            _insert_ranking_cell(connection, "mismatched-count", "mismatch", "v1", draw_id)

        _insert_ranking_run(
            connection,
            "duplicate-target",
            [("duplicate-target", "v1")],
            ["1"],
            declared_target_ids=["1", "1"],
        )
        _insert_ranking_cell(connection, "duplicate-target", "duplicate-target", "v1", "1")

        _insert_ranking_run(
            connection,
            "inventory-mismatch",
            [("inventory", "v1")],
            ["1"],
        )
        _insert_ranking_cell(connection, "inventory-mismatch", "inventory", "v1", "1")
        connection.execute(
            "DELETE FROM replay_backfill_strategy_inventory WHERE run_id='inventory-mismatch'"
        )

        _insert_ranking_run(
            connection,
            "versions",
            [("versioned", "v1"), ("versioned", "v2")],
            ["1"],
        )
        _insert_ranking_cell(connection, "versions", "versioned", "v1", "1")
        # Keep both run-scoped historical identities regardless of their scores.
        _insert_ranking_cell(connection, "versions", "versioned", "v2", "1", status="FAILED")

    client = _ranking_client(database, monkeypatch)
    response = client.get(
        "/api/v1/replay-backfill/official-ranking",
        params={"lottery_type": "BIG_LOTTO", "window": "FULL"},
    )
    assert response.status_code == 200, response.text
    items = response.json()["items"]

    duplicate_strategy = next(row for row in items if row["run_id"] == "duplicate-strategy")
    assert duplicate_strategy["rank"] is None and duplicate_strategy["rate"] is None
    assert "duplicate_strategy_identity" in duplicate_strategy["unknown_reason"]

    mismatched_count = next(row for row in items if row["run_id"] == "mismatched-count")
    assert mismatched_count["rank"] is None and mismatched_count["rate"] is None
    assert "expected_cells_mismatch" in mismatched_count["unknown_reason"]

    duplicate_target = next(row for row in items if row["run_id"] == "duplicate-target")
    assert duplicate_target["rank"] is None and duplicate_target["rate"] is None
    assert "duplicate_target_identity" in duplicate_target["unknown_reason"]

    inventory_mismatch = next(row for row in items if row["run_id"] == "inventory-mismatch")
    assert inventory_mismatch["rank"] is None and inventory_mismatch["rate"] is None
    assert "strategy_inventory_mismatch" in inventory_mismatch["unknown_reason"]

    version_rows = [row for row in items if row["run_id"] == "versions"]
    assert {row["strategy_version"] for row in version_rows} == {"v1", "v2"}
    assert all(row["rate"] is not None for row in version_rows if row["strategy_version"] == "v1")
    assert next(row for row in version_rows if row["strategy_version"] == "v2")["failed_count"] == 1
