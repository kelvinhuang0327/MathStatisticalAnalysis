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
                            "target_draw_ids": ["1"],
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
            "VALUES ('daily',?,2)",
            (
                json.dumps(
                    {
                        "lottery_type": "DAILY_539",
                        "target_draw_ids": [str(i) for i in range(1, 52)],
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
            manifest: dict[str, Any] = {"lottery_type": "DAILY_539", "target_draw_ids": ids}
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
