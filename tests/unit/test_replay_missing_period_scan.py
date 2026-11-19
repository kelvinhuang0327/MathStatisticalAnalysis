"""Focused acceptance tests for the read-only replay missing-period scan."""

# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
# Starlette TestClient is partially untyped under the httpx compatibility shim.

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lottolab.domain.draws import LotteryType
from lottolab.infrastructure.persistence.replay_backfill_store import (
    SCHEMA_CHECKSUM,
    SCHEMA_SQL,
    SCHEMA_VERSION,
    SQLiteBackfillStore,
)
from lottolab.interfaces.api.replay_backfill import create_replay_backfill_router

_SCAN_PATH = "/api/v1/replay-backfill/coverage/scan"
_STRATEGIES = (
    ("legacy_biglotto__predict_biglotto_elite7__eb46a9856446", "v0.1"),
    ("strategy_version_case", "v2"),
    ("strategy_failed", "v1"),
    ("strategy_partial", "v1"),
    ("legacy_biglotto__predict_biglotto_apriori__cda690ae84c2", "v1"),
)
_EVIDENCE_ENV = "MSA_REPLAY_SCAN_EVIDENCE_ROOT"
_TASK_ID = "NUMBER2_2_REPLAY_MISSING_PERIOD_TICKET_COMPLETENESS_FIX_20261116_R1"


@dataclass(frozen=True)
class _Harness:
    client: TestClient
    replay_database: Path
    draw_database: Path
    work_directory: Path


@pytest.fixture
def scan_harness(tmp_path: Path, request: pytest.FixtureRequest) -> Iterator[_Harness]:
    evidence_root = Path(os.environ.get(_EVIDENCE_ENV, str(tmp_path)))
    evidence_root.mkdir(parents=True, exist_ok=True)
    synthetic_root = evidence_root / "synthetic_sqlite"
    synthetic_root.mkdir(parents=True, exist_ok=True)
    temporary_directory = tempfile.TemporaryDirectory(prefix="replay-scan-", dir=synthetic_root)
    work_directory = Path(temporary_directory.name)
    replay_database = work_directory / "replay.sqlite3"
    draw_database = work_directory / "draws.sqlite3"
    _create_draw_database(draw_database)
    _create_replay_database(replay_database)

    def read_window(
        lottery_type: LotteryType, start_date: date, end_date: date
    ) -> tuple[tuple[str, str], ...]:
        assert lottery_type is LotteryType.BIG_LOTTO
        with sqlite3.connect(draw_database.as_uri() + "?mode=ro", uri=True) as connection:
            rows = connection.execute(
                "SELECT draw_number,draw_date FROM draws "
                "WHERE lottery_type=? AND draw_date>=? AND draw_date<=? "
                "ORDER BY draw_date,CAST(draw_number AS INTEGER)",
                (lottery_type.value, start_date.isoformat(), end_date.isoformat()),
            ).fetchall()
        return tuple((str(number), str(draw_date)) for number, draw_date in rows)

    app = FastAPI()
    app.include_router(
        create_replay_backfill_router(
            SQLiteBackfillStore(replay_database, read_only=True),
            window_draw_reader=read_window,
        )
    )
    client = TestClient(app)
    try:
        yield _Harness(client, replay_database, draw_database, work_directory)
    finally:
        client.close()
        cleanup_records: list[dict[str, Any]] = []
        if _EVIDENCE_ENV in os.environ:
            for database in (replay_database, draw_database):
                if database.exists():
                    cleanup_records.append(
                        {
                            "test": request.node.name,
                            "path": str(database),
                            "sha256_before_deletion": _file_sha256(database),
                            "bytes_before_deletion": database.stat().st_size,
                        }
                    )
        temporary_directory.cleanup()
        if cleanup_records:
            deleted_at = datetime.now(UTC).isoformat()
            for cleanup_record in cleanup_records:
                cleanup_record["deleted_at_utc"] = deleted_at
            _append_summary("synthetic_sqlite_fixtures", cleanup_records)


def _create_draw_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE draws (lottery_type TEXT, draw_number TEXT, draw_date TEXT, "
            "PRIMARY KEY(lottery_type,draw_number))"
        )
        connection.execute(
            "CREATE TABLE official_schedule (lottery_type TEXT, draw_number TEXT, draw_date TEXT, "
            "PRIMARY KEY(lottery_type,draw_number))"
        )
        base = date(2020, 1, 1)
        rows = [
            (LotteryType.BIG_LOTTO.value, str(1000 + day), (base + timedelta(days=day)).isoformat())
            for day in range(10)
        ]
        rows.extend(
            (
                LotteryType.BIG_LOTTO.value,
                str(2000 + day),
                (date(2021, 2, 1) + timedelta(days=day)).isoformat(),
            )
            for day in range(5)
        )
        rows.extend(
            (
                LotteryType.BIG_LOTTO.value,
                str(5000 + draw),
                "2022-01-01" if draw < 2500 else "2022-01-02",
            )
            for draw in range(2501)
        )
        connection.executemany("INSERT INTO draws VALUES(?,?,?)", rows)
        connection.execute(
            "INSERT INTO official_schedule VALUES(?,?,?)",
            (LotteryType.BIG_LOTTO.value, "1010", "2020-01-11"),
        )


def _create_replay_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(SCHEMA_SQL)
        connection.execute(
            "INSERT INTO replay_backfill_schema(version,checksum) VALUES(?,?)",
            (SCHEMA_VERSION, SCHEMA_CHECKSUM),
        )
        for run_id in ("fixture-run-a", "fixture-run-b", "fixture-run-other"):
            manifest = json.dumps(
                {"run_id": run_id, "fixture": True}, sort_keys=True, separators=(",", ":")
            )
            connection.execute(
                "INSERT INTO replay_backfill_runs(run_id,manifest_json,expected_cells) "
                "VALUES(?,?,1)",
                (run_id, manifest),
            )

        _insert_cell(
            connection,
            strategy_id="unrequested_strategy",
            strategy_version="v1",
            target_draw_id="1000",
            execution_status="COMPLETE",
            run_ids=("fixture-run-other",),
        )
        _insert_cell(
            connection,
            strategy_id=_STRATEGIES[1][0],
            strategy_version="v1",
            target_draw_id="1001",
            execution_status="COMPLETE",
            run_ids=("fixture-run-other",),
        )
        _insert_cell(
            connection,
            strategy_id=_STRATEGIES[2][0],
            strategy_version=_STRATEGIES[2][1],
            target_draw_id="1002",
            execution_status="FAILED",
            reason="SYNTHETIC_EXECUTION_FAILURE",
            run_ids=("fixture-run-a",),
        )
        _insert_cell(
            connection,
            strategy_id=_STRATEGIES[3][0],
            strategy_version=_STRATEGIES[3][1],
            target_draw_id="1003",
            execution_status="PARTIAL",
            reason="INCOMPLETE_TICKET_SET",
            ticket_count=3,
            run_ids=("fixture-run-a",),
        )
        _insert_cell(
            connection,
            strategy_id=_STRATEGIES[4][0],
            strategy_version=_STRATEGIES[4][1],
            target_draw_id="1004",
            execution_status="NOT_ELIGIBLE",
            reason="INSUFFICIENT_HISTORY",
            run_ids=("fixture-run-a",),
        )
        _insert_cell(
            connection,
            strategy_id=_STRATEGIES[0][0],
            strategy_version=_STRATEGIES[0][1],
            target_draw_id="1005",
            execution_status="TYPED_CLOSURE",
            reason="TARGET_CLOSED_WITHOUT_REPLAY",
            run_ids=("fixture-run-a",),
        )
        _insert_cell(
            connection,
            strategy_id=_STRATEGIES[1][0],
            strategy_version=_STRATEGIES[1][1],
            target_draw_id="1006",
            execution_status="COMPLETE",
            execution_version="execution-a",
            dataset_identity="dataset-a",
            run_ids=("fixture-run-a",),
        )
        _insert_cell(
            connection,
            strategy_id=_STRATEGIES[1][0],
            strategy_version=_STRATEGIES[1][1],
            target_draw_id="1006",
            execution_version="execution-b",
            dataset_identity="dataset-b",
            execution_status="COMPLETE",
            run_ids=("fixture-run-b",),
        )
        _insert_cell(
            connection,
            strategy_id=_STRATEGIES[0][0],
            strategy_version=_STRATEGIES[0][1],
            target_draw_id="1007",
            execution_status="COMPLETE",
            ticket_count=3,
            run_ids=("fixture-run-a",),
        )
        _insert_cell(
            connection,
            strategy_id=_STRATEGIES[4][0],
            strategy_version=_STRATEGIES[4][1],
            target_draw_id="1008",
            execution_status="COMPLETE",
            ticket_count=3,
            run_ids=("fixture-run-b",),
        )
        _insert_cell(
            connection,
            strategy_id=_STRATEGIES[0][0],
            strategy_version=_STRATEGIES[0][1],
            target_draw_id="1009",
            execution_status="COMPLETE",
            ticket_count=7,
            run_ids=("fixture-run-a",),
        )


def _insert_cell(
    connection: sqlite3.Connection,
    *,
    strategy_id: str,
    strategy_version: str,
    target_draw_id: str,
    execution_status: str,
    reason: str | None = None,
    execution_version: str = "execution-default",
    dataset_identity: str = "dataset-default",
    ticket_count: int = 7,
    run_ids: Sequence[str],
) -> None:
    target_day = int(target_draw_id) - 1000
    target_date = (date(2020, 1, 1) + timedelta(days=target_day)).isoformat()
    tickets = [
        {"ticket_position": position, "main_numbers": [1, 2, 3, 4, 5, 6]}
        for position in range(1, ticket_count + 1)
    ]
    payload: dict[str, Any] = {"predicted_tickets": tickets}
    if reason is not None:
        payload["error_reason"] = reason
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    cell_identity = hashlib.sha256(
        "|".join(
            (
                strategy_id,
                strategy_version,
                target_draw_id,
                execution_version,
                dataset_identity,
            )
        ).encode()
    ).hexdigest()
    result_identity = hashlib.sha256(payload_json.encode()).hexdigest()
    connection.execute(
        "INSERT INTO replay_backfill_cells VALUES(?,?,?,?,?,?,?,?,?,?,?,1)",
        (
            cell_identity,
            LotteryType.BIG_LOTTO.value,
            strategy_id,
            strategy_version,
            execution_version,
            dataset_identity,
            target_draw_id,
            target_date,
            execution_status,
            result_identity,
            payload_json,
        ),
    )
    for run_id in run_ids:
        connection.execute(
            "INSERT INTO replay_backfill_run_cells(run_id,cell_identity) VALUES(?,?)",
            (run_id, cell_identity),
        )
    for position in range(1, ticket_count + 1):
        connection.execute(
            "INSERT INTO replay_backfill_tickets VALUES(?,?,?,?,?,?,?)",
            (cell_identity, position, "[1,2,3,4,5,6]", "[]", None, None, None),
        )


def _request_params(
    start_date: str,
    end_date: str,
    *,
    limit: int | None = None,
    offset: int = 0,
) -> list[tuple[str, str]]:
    params = [
        ("lottery_type", LotteryType.BIG_LOTTO.value),
        ("start_date", start_date),
        ("end_date", end_date),
        *(("strategy_id", strategy_id) for strategy_id, _ in _STRATEGIES),
        *(("strategy_version", version) for _, version in _STRATEGIES),
    ]
    if limit is not None:
        params.append(("limit", str(limit)))
    if offset:
        params.append(("offset", str(offset)))
    return params


def _items_by_identity(body: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(item["target_draw_id"]), str(item["strategy_id"])): item
        for item in cast(list[dict[str, Any]], body["items"])
    }


def _database_digest(path: Path) -> str:
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as connection:
        schema = connection.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
        ).fetchall()
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE "
                "type='table' AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name"
            )
        ]
        contents = {}
        for table in tables:
            quoted = table.replace('"', '""')
            contents[table] = connection.execute(
                f'SELECT * FROM "{quoted}" ORDER BY rowid'
            ).fetchall()
        snapshot = {
            "schema": schema,
            "tables": contents,
            "schema_version": connection.execute("PRAGMA schema_version").fetchone()[0],
            "user_version": connection.execute("PRAGMA user_version").fetchone()[0],
            "foreign_key_errors": connection.execute("PRAGMA foreign_key_check").fetchall(),
        }
    round_tripped = json.loads(json.dumps(snapshot, sort_keys=True, default=str))
    encoded = json.dumps(round_tripped, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _append_summary(key: str, values: list[dict[str, Any]]) -> None:
    root_value = os.environ.get(_EVIDENCE_ENV)
    if root_value is None:
        return
    path = Path(root_value) / "backend_acceptance_summary.json"
    payload: dict[str, Any] = {"task_id": _TASK_ID}
    if path.exists():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            payload = loaded
    current = payload.setdefault(key, [])
    if isinstance(current, list):
        current.extend(values)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _record_observation(name: str, observation: dict[str, Any]) -> None:
    _append_summary("observations", [{"test": name, **observation}])


def test_scan_classifies_missing_version_status_and_conflicting_identities(
    scan_harness: _Harness,
) -> None:
    response = scan_harness.client.get(
        _SCAN_PATH,
        params=_request_params("2020-01-01", "2020-01-07"),
    )
    assert response.status_code == 200
    body = cast(dict[str, Any], response.json())
    items = _items_by_identity(body)
    expected = {
        ("1000", _STRATEGIES[0][0]): ("MISSING", "NO_SAVED_CELL"),
        ("1001", _STRATEGIES[1][0]): ("VERSION_MISMATCH", "ONLY_OTHER_STRATEGY_VERSION_SAVED"),
        ("1002", _STRATEGIES[2][0]): ("FAILED", "SYNTHETIC_EXECUTION_FAILURE"),
        ("1003", _STRATEGIES[3][0]): ("PARTIAL", "INCOMPLETE_TICKET_SET"),
        ("1004", _STRATEGIES[4][0]): ("NOT_ELIGIBLE", "INSUFFICIENT_HISTORY"),
        ("1005", _STRATEGIES[0][0]): ("TYPED_CLOSURE", "TARGET_CLOSED_WITHOUT_REPLAY"),
        ("1006", _STRATEGIES[1][0]): (
            "AMBIGUOUS",
            "MULTIPLE_EXECUTION_OR_DATASET_IDENTITIES",
        ),
    }
    actual = {
        f"{draw_id}/{strategy_id}": {
            "status": items[(draw_id, strategy_id)]["status"],
            "reason": items[(draw_id, strategy_id)]["reason"],
        }
        for draw_id, strategy_id in expected
    }
    _record_observation(
        "status_matrix",
        {
            "expected": {
                f"{draw_id}/{strategy_id}": {"status": status, "reason": reason}
                for (draw_id, strategy_id), (status, reason) in expected.items()
            },
            "actual": actual,
            "status_counts": body["status_counts"],
        },
    )
    assert actual == {
        f"{draw_id}/{strategy_id}": {"status": status, "reason": reason}
        for (draw_id, strategy_id), (status, reason) in expected.items()
    }
    missing = items[("1000", _STRATEGIES[0][0])]
    assert missing["status"] == "MISSING"
    assert missing["reason"] == "NO_SAVED_CELL"
    assert "never" not in json.dumps(missing, sort_keys=True).casefold()
    ambiguous = items[("1006", _STRATEGIES[1][0])]
    assert len(ambiguous["existing_records"]) == 2
    assert ambiguous["status"] != "COMPLETE"
    with sqlite3.connect(
        scan_harness.replay_database.as_uri() + "?mode=ro", uri=True
    ) as connection:
        observed_runs = {
            row[0]
            for row in connection.execute(
                "SELECT r.run_id FROM replay_backfill_run_cells r "
                "JOIN replay_backfill_cells c USING(cell_identity) "
                "WHERE c.target_draw_id='1006'"
            )
        }
    assert observed_runs == {"fixture-run-a", "fixture-run-b"}


def test_short_fixed_k7_is_incomplete(
    scan_harness: _Harness,
) -> None:
    k7_response = scan_harness.client.get(
        _SCAN_PATH,
        params=_request_params("2020-01-08", "2020-01-08"),
    )
    assert k7_response.status_code == 200
    k7 = cast(dict[str, Any], k7_response.json())
    k7_rows = _items_by_identity(k7)
    k7_entry = k7_rows.get(("1007", _STRATEGIES[0][0]))
    _record_observation(
        "fixed_k7_ticket_contract",
        {
            "ticket_count": 3,
            "execution_status": (
                k7_entry["existing_records"][0]["execution_status"] if k7_entry else None
            ),
            "status": k7_entry["status"] if k7_entry else "COUNTED_COMPLETE",
            "complete_cell_count": k7["complete_cell_count"],
            "incomplete_cell_count": k7["incomplete_cell_count"],
            "expected_cell_count": k7["expected_cell_count"],
            "status_counts": k7["status_counts"],
            "item": (
                {
                    "target_draw_id": k7_entry["target_draw_id"],
                    "status": k7_entry["status"],
                    "reason": k7_entry["reason"],
                    "execution_status": k7_entry["existing_records"][0]["execution_status"],
                    "ticket_count": k7_entry["existing_records"][0]["ticket_count"],
                    "ticket_positions": k7_entry["existing_records"][0]["ticket_positions"],
                    "ticket_set_valid": k7_entry["existing_records"][0]["ticket_set_valid"],
                    "fixed_k7_comparison_eligible": k7_entry["existing_records"][0][
                        "fixed_k7_comparison_eligible"
                    ],
                }
                if k7_entry
                else None
            ),
        },
    )
    assert k7_entry is not None, "three tickets cannot satisfy a fixed seven-ticket comparison"
    assert k7_entry["status"] in {"PARTIAL", "INCOMPLETE"}
    assert k7_entry["existing_records"][0]["execution_status"] == "COMPLETE"
    assert k7_entry["existing_records"][0]["ticket_count"] == 3
    assert k7_entry["existing_records"][0]["fixed_k7_comparison_eligible"] is False
    assert k7["expected_cell_count"] == 5
    assert k7["complete_cell_count"] == 0
    assert k7["incomplete_cell_count"] == 5
    assert k7["complete_cell_count"] + k7["incomplete_cell_count"] == k7["expected_cell_count"]


def test_apriori_native_variable_ticket_count_is_not_invalid_output(
    scan_harness: _Harness,
) -> None:
    apriori_response = scan_harness.client.get(
        _SCAN_PATH,
        params=_request_params("2020-01-09", "2020-01-09"),
    )
    assert apriori_response.status_code == 200
    apriori = cast(dict[str, Any], apriori_response.json())
    apriori_key = f"{_STRATEGIES[4][0]}@{_STRATEGIES[4][1]}"
    assert apriori["strategy_counts"][apriori_key]["complete"] == 1
    assert apriori["strategy_counts"][apriori_key]["incomplete"] == 0
    assert apriori["strategy_counts"][apriori_key]["fixed_k7_comparison_eligible"] == 0
    assert "INVALID_OUTPUT" not in apriori["status_counts"]
    with sqlite3.connect(
        scan_harness.replay_database.as_uri() + "?mode=ro", uri=True
    ) as connection:
        saved_execution_status, saved_ticket_count = connection.execute(
            "SELECT c.execution_status,COUNT(t.ticket_position) "
            "FROM replay_backfill_cells c "
            "JOIN replay_backfill_tickets t USING(cell_identity) "
            "WHERE c.strategy_id=? AND c.target_draw_id='1008' "
            "GROUP BY c.cell_identity,c.execution_status",
            (_STRATEGIES[4][0],),
        ).fetchone()
    assert saved_ticket_count == 3
    _record_observation(
        "apriori_native_vs_fixed_k7_comparison",
        {
            "saved_ticket_count": saved_ticket_count,
            "execution_status": saved_execution_status,
            "native_complete_count": apriori["strategy_counts"][apriori_key]["complete"],
            "native_incomplete_count": apriori["strategy_counts"][apriori_key]["incomplete"],
            "fixed_k7_comparison_eligible": (
                apriori["strategy_counts"][apriori_key]["fixed_k7_comparison_eligible"]
            ),
            "status_counts": apriori["status_counts"],
        },
    )


def test_ticket_positions_and_legal_groups_are_required_for_fixed_k7(
    scan_harness: _Harness,
) -> None:
    strategy_id, strategy_version = _STRATEGIES[0]
    with sqlite3.connect(scan_harness.replay_database) as connection:
        cell_identity = connection.execute(
            "SELECT cell_identity FROM replay_backfill_cells "
            "WHERE strategy_id=? AND strategy_version=? AND target_draw_id='1009'",
            (strategy_id, strategy_version),
        ).fetchone()[0]
        payload_json = connection.execute(
            "SELECT payload_json FROM replay_backfill_cells WHERE cell_identity=?",
            (cell_identity,),
        ).fetchone()[0]
    original_payload = json.loads(payload_json)

    valid_response = scan_harness.client.get(
        _SCAN_PATH,
        params=_request_params("2020-01-10", "2020-01-10"),
    )
    assert valid_response.status_code == 200
    valid_body = cast(dict[str, Any], valid_response.json())
    strategy_key = f"{strategy_id}@{strategy_version}"
    assert valid_body["strategy_counts"][strategy_key]["complete"] == 1
    assert valid_body["strategy_counts"][strategy_key]["fixed_k7_comparison_eligible"] == 1

    duplicate_position_payload = json.loads(json.dumps(original_payload))
    duplicate_position_payload["predicted_tickets"][1]["ticket_position"] = 1
    with sqlite3.connect(scan_harness.replay_database) as connection:
        connection.execute(
            "UPDATE replay_backfill_cells SET payload_json=? WHERE cell_identity=?",
            (
                json.dumps(duplicate_position_payload, sort_keys=True, separators=(",", ":")),
                cell_identity,
            ),
        )
    duplicate_response = scan_harness.client.get(
        _SCAN_PATH,
        params=_request_params("2020-01-10", "2020-01-10"),
    )
    duplicate_entry = _items_by_identity(cast(dict[str, Any], duplicate_response.json()))[
        ("1009", strategy_id)
    ]
    assert duplicate_entry["status"] == "PARTIAL"
    assert duplicate_entry["existing_records"][0]["ticket_set_valid"] is False

    with sqlite3.connect(scan_harness.replay_database) as connection:
        connection.execute(
            "UPDATE replay_backfill_cells SET payload_json=? WHERE cell_identity=?",
            (payload_json, cell_identity),
        )
        connection.execute(
            "UPDATE replay_backfill_tickets SET ticket_position=8 "
            "WHERE cell_identity=? AND ticket_position=7",
            (cell_identity,),
        )
    gap_response = scan_harness.client.get(
        _SCAN_PATH,
        params=_request_params("2020-01-10", "2020-01-10"),
    )
    gap_entry = _items_by_identity(cast(dict[str, Any], gap_response.json()))[("1009", strategy_id)]
    assert gap_entry["status"] == "PARTIAL"
    assert gap_entry["existing_records"][0]["ticket_set_valid"] is False

    with sqlite3.connect(scan_harness.replay_database) as connection:
        connection.execute(
            "UPDATE replay_backfill_tickets SET ticket_position=7 "
            "WHERE cell_identity=? AND ticket_position=8",
            (cell_identity,),
        )
        connection.execute(
            "UPDATE replay_backfill_tickets SET main_numbers_json='[1,1,3,4,5,6]' "
            "WHERE cell_identity=? AND ticket_position=1",
            (cell_identity,),
        )
    invalid_ticket_response = scan_harness.client.get(
        _SCAN_PATH,
        params=_request_params("2020-01-10", "2020-01-10"),
    )
    invalid_entry = _items_by_identity(cast(dict[str, Any], invalid_ticket_response.json()))[
        ("1009", strategy_id)
    ]
    assert invalid_entry["status"] == "PARTIAL"
    assert invalid_entry["existing_records"][0]["ticket_set_valid"] is False


def test_query_is_read_only_and_repeatable_with_a_stable_digest(
    scan_harness: _Harness,
) -> None:
    replay_before = _database_digest(scan_harness.replay_database)
    draws_before = _database_digest(scan_harness.draw_database)
    params = _request_params("2020-01-01", "2020-01-07")
    first_response = scan_harness.client.get(_SCAN_PATH, params=params)
    second_response = scan_harness.client.get(_SCAN_PATH, params=params)
    replay_after = _database_digest(scan_harness.replay_database)
    draws_after = _database_digest(scan_harness.draw_database)
    assert first_response.status_code == second_response.status_code == 200
    first = cast(dict[str, Any], first_response.json())
    second = cast(dict[str, Any], second_response.json())
    normalized = json.loads(json.dumps(first, sort_keys=True))
    output_digest = hashlib.sha256(
        json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    _record_observation(
        "read_only_and_repeatability",
        {
            "replay_database_before_sha256": replay_before,
            "replay_database_after_sha256": replay_after,
            "draw_database_before_sha256": draws_before,
            "draw_database_after_sha256": draws_after,
            "first_output_sha256": output_digest,
            "repeat_output_sha256": hashlib.sha256(
                json.dumps(second, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
            "first_status_counts": first["status_counts"],
            "repeat_status_counts": second["status_counts"],
        },
    )
    assert replay_before == replay_after
    assert draws_before == draws_after
    assert first == second


def test_query_is_get_only_and_does_not_call_store_writers(
    scan_harness: _Harness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_writer(*args: object, **kwargs: object) -> None:
        del args, kwargs
        pytest.fail("coverage GET called a replay writer or recovery path")

    monkeypatch.setattr(SQLiteBackfillStore, "prepare", forbidden_writer)
    monkeypatch.setattr(SQLiteBackfillStore, "save", forbidden_writer)
    monkeypatch.setattr(SQLiteBackfillStore, "save_many", forbidden_writer)
    response = scan_harness.client.get(
        _SCAN_PATH,
        params=_request_params("2020-01-01", "2020-01-07"),
    )
    assert response.status_code == 200
    assert (
        scan_harness.client.post(
            _SCAN_PATH,
            params=_request_params("2020-01-01", "2020-01-07"),
        ).status_code
        == 405
    )


def test_source_window_is_draw_database_limited_and_does_not_invent_missing_draws(
    scan_harness: _Harness,
) -> None:
    response = scan_harness.client.get(
        _SCAN_PATH,
        params=_request_params("2020-01-01", "2020-01-11"),
    )
    assert response.status_code == 200
    body = cast(dict[str, Any], response.json())
    assert body["source_target_count"] == 10
    assert all(item["target_draw_id"] != "1010" for item in body["items"])
    assert body["status_counts"].get("MISSING", 0) > 0
    with sqlite3.connect(scan_harness.draw_database.as_uri() + "?mode=ro", uri=True) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM official_schedule WHERE draw_number='1010'"
            ).fetchone()[0]
            == 1
        )
        assert (
            connection.execute("SELECT COUNT(*) FROM draws WHERE draw_number='1010'").fetchone()[0]
            == 0
        )
    _record_observation(
        "source_limited_periods",
        {
            "draw_database_target_count": body["source_target_count"],
            "scheduled_but_absent_draw_id": "1010",
            "scheduled_but_absent_draw_reported_as_strategy_missing": False,
        },
    )


def test_target_cap_validation_and_pagination_have_no_gaps_or_duplicates(
    scan_harness: _Harness,
) -> None:
    first_page = scan_harness.client.get(
        _SCAN_PATH,
        params=_request_params("2021-02-01", "2021-02-05", limit=7),
    )
    assert first_page.status_code == 200
    page = cast(dict[str, Any], first_page.json())
    seen: list[dict[str, Any]] = list(cast(list[dict[str, Any]], page["items"]))
    while page["next_offset"] is not None:
        next_offset = int(page["next_offset"])
        response = scan_harness.client.get(
            _SCAN_PATH,
            params=_request_params("2021-02-01", "2021-02-05", limit=7, offset=next_offset),
        )
        assert response.status_code == 200
        page = cast(dict[str, Any], response.json())
        seen.extend(cast(list[dict[str, Any]], page["items"]))
    expected = [
        (str(2000 + day), strategy_id, version)
        for day in range(5)
        for strategy_id, version in _STRATEGIES
    ]
    actual = [
        (str(row["target_draw_id"]), str(row["strategy_id"]), str(row["strategy_version"]))
        for row in seen
    ]
    assert actual == expected
    assert len(set(actual)) == len(expected)

    at_limit = scan_harness.client.get(
        _SCAN_PATH,
        params=_request_params("2022-01-01", "2022-01-01", limit=1),
    )
    assert at_limit.status_code == 200
    assert at_limit.json()["source_target_count"] == 2500
    assert at_limit.json()["expected_cell_count"] == 12_500
    assert at_limit.json()["total_count"] == 12_500

    over_limit = scan_harness.client.get(
        _SCAN_PATH,
        params=_request_params("2022-01-01", "2022-01-02"),
    )
    assert over_limit.status_code == 422
    assert over_limit.json()["error_code"] == "WINDOW_EXCEEDS_2500_TARGETS"

    invalid_windows = (
        _request_params("2020-01-03", "2020-01-01"),
        _request_params("2020-99-01", "2020-99-02"),
        _request_params("2020-01-01", "2020-01-02", limit=251),
    )
    for params in invalid_windows:
        assert scan_harness.client.get(_SCAN_PATH, params=params).status_code == 422
    _record_observation(
        "bounded_query_and_pagination",
        {
            "targets_at_limit": at_limit.json()["source_target_count"],
            "expected_cell_targets_at_limit": at_limit.json()["expected_cell_count"],
            "targets_over_limit_status": over_limit.status_code,
            "pagination_expected_items": len(expected),
            "pagination_produced_items": len(actual),
            "pagination_unique_items": len(set(actual)),
        },
    )
