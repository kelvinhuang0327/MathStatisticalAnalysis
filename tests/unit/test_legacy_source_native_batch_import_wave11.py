"""Causal batch tests for the eleventh source-native wave."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any, cast

from typer.testing import CliRunner

from lottolab.application.biglotto_multi_ticket_backtest import (
    evaluate_biglotto_multi_ticket_backtest,
)
from lottolab.application.legacy_source_native_portfolios_wave11 import (
    EXHAUSTIVE_NBET_METHOD_ID,
    MUST_HIT_METHOD_ID,
)
from lottolab.infrastructure.legacy_source_native_batch_import_wave11 import (
    materialize_legacy_source_native_wave11_batch,
)
from lottolab.interfaces.cli.main import app

runner = CliRunner()


def _fixture_database(path: Path) -> str:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE draws (
            draw TEXT, date TEXT, lottery_type TEXT, numbers TEXT, special INTEGER
        );
        CREATE VIEW draws_big_lotto_canonical_main AS
        SELECT * FROM draws WHERE lottery_type = 'BIG_LOTTO';
        CREATE TABLE strategy_prediction_replays (
            id INTEGER PRIMARY KEY,
            target_draw TEXT,
            target_date TEXT,
            strategy_id TEXT,
            strategy_version TEXT,
            history_cutoff_draw TEXT,
            replay_status TEXT,
            reject_reason TEXT,
            predicted_numbers TEXT,
            actual_numbers TEXT,
            actual_special INTEGER,
            replay_run_id TEXT,
            bet_index INTEGER
        );
        """
    )
    first_date = date(2020, 1, 1)
    rows: list[tuple[object, ...]] = []
    for index in range(505):
        numbers = sorted(
            ((index * 7 + offset * 5) % 49) + 1
            for offset in range(6)
        )
        rows.append(
            (
                str(index + 1),
                (
                    first_date + timedelta(days=index)
                ).strftime("%Y/%m/%d"),
                "BIG_LOTTO",
                json.dumps(numbers),
                next(
                    number
                    for number in range(1, 50)
                    if number not in numbers
                ),
            )
        )
    connection.executemany(
        "INSERT INTO draws VALUES (?,?,?,?,?)",
        rows,
    )
    last_draw_number = cast(str, rows[-1][0])
    last_draw_date = cast(str, rows[-1][1])
    last_numbers = json.loads(cast(str, rows[-1][3]))
    last_special = cast(int, rows[-1][4])
    replay_rows: list[tuple[object, ...]] = [
        (
            1,
            last_draw_number,
            last_draw_date,
            "biglotto_triple_strike",
            "v0.1",
            cast(str, rows[-2][0]),
            "PREDICTED",
            None,
            json.dumps([1, 7, 15, 23, 28, 39]),
            json.dumps(last_numbers),
            last_special,
            "fixture",
            1,
        )
    ]
    for index, ticket in enumerate(
        (
            [1, 2, 3, 4, 5, 6],
            [7, 8, 9, 10, 11, 12],
            [13, 14, 15, 16, 17, 18],
            [19, 20, 21, 22, 23, 24],
        ),
        start=1,
    ):
        replay_rows.append(
            (
                index + 1,
                last_draw_number,
                last_draw_date,
                "biglotto_ts3_markov_4bet_w30",
                "v0.1",
                cast(str, rows[-2][0]),
                "PREDICTED",
                None,
                json.dumps(ticket),
                json.dumps(last_numbers),
                last_special,
                None,
                index,
            )
        )
    connection.executemany(
        "INSERT INTO strategy_prediction_replays "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        replay_rows,
    )
    connection.commit()
    connection.close()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_bytes(document: dict[str, object]) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def test_wave11_batch_preserves_configuration_and_closed_semantics(
    tmp_path: Path,
) -> None:
    database = tmp_path / "legacy.db"
    database_sha256 = _fixture_database(database)
    document = materialize_legacy_source_native_wave11_batch(
        database=database,
        expected_database_sha256=database_sha256,
    )

    executions = cast(list[dict[str, Any]], document["executions"])
    assert len(executions) == 1010
    successful = [
        row for row in executions if row["status"] == "OK"
    ]
    closed = [
        row for row in executions if row["status"] != "OK"
    ]
    assert len(successful) == 460
    assert len(closed) == 550
    assert all(
        len(row["ordered_portfolio"]) == 20 for row in successful
    )
    assert all("ordered_portfolio" not in row for row in closed)
    by_method: dict[str, dict[str, Any]] = {}
    for row in successful:
        native = cast(dict[str, Any], row["native_generation"])
        method_id = cast(str, native["legacy_method_id"])
        by_method.setdefault(method_id, row)

    exhaustive = by_method[EXHAUSTIVE_NBET_METHOD_ID]
    assert exhaustive["combination_count"] == 26
    assert exhaustive["native_ticket_count"] == 65
    exhaustive_native = cast(
        dict[str, Any],
        exhaustive["native_generation"],
    )
    assert exhaustive_native["source_candidate_ticket_counts"] == (
        (2,) * 13 + (3,) * 13
    )
    assert exhaustive_native["native_duplicate_ticket_count"] > 0
    must_hit = by_method[MUST_HIT_METHOD_ID]
    assert must_hit["combination_count"] == 3
    assert must_hit["native_ticket_count"] == 1
    must_hit_native = cast(dict[str, Any], must_hit["native_generation"])
    assert must_hit_native["source_candidate_k_values"] == (6, 10, 15)
    assert [
        len(pool)
        for pool in must_hit_native["source_candidate_number_pools"]
    ] == [6, 10, 15]
    assert must_hit_native["candidate_k"] is None
    assert must_hit_native["combination_count"] is None
    provenance = cast(dict[str, Any], document["source_provenance"])
    assert provenance["database_sha256_before"] == database_sha256
    assert provenance["database_sha256_after"] == database_sha256


def test_wave11_batch_passes_complete_universe_evaluator(
    tmp_path: Path,
) -> None:
    database = tmp_path / "legacy.db"
    database_sha256 = _fixture_database(database)
    document = materialize_legacy_source_native_wave11_batch(
        database=database,
        expected_database_sha256=database_sha256,
    )

    report = evaluate_biglotto_multi_ticket_backtest(
        _canonical_bytes(document)
    )

    assert report["target_draw_count"] == 505
    assert cast(dict[str, int], report["progress"]) == {
        "backtested_count": 135,
        "closed_count": 74,
        "duplicate_alias_count": 12,
        "owner_decision_required_count": 0,
        "reproduced_count": 135,
        "total_strategy_count": 221,
        "uncompleted_count": 0,
    }


def test_wave11_cli_is_registered_and_refuses_overwrite(
    tmp_path: Path,
) -> None:
    database = tmp_path / "legacy.db"
    database_sha256 = _fixture_database(database)
    output = tmp_path / "input.json"
    args = [
        "materialize-biglotto-source-native-wave11-batch",
        "--database",
        str(database),
        "--expected-database-sha256",
        database_sha256,
        "--output-file",
        str(output),
    ]

    first = runner.invoke(app, args)
    second = runner.invoke(app, args)

    assert first.exit_code == 0
    summary = json.loads(first.stdout)
    assert summary["execution_count"] == 1010
    assert summary["target_draw_count"] == 505
    assert summary["execution_status_counts"] == {
        "CLOSED_INSUFFICIENT_HISTORY": 550,
        "OK": 460,
    }
    assert summary["input_sha256"] == hashlib.sha256(
        output.read_bytes()
    ).hexdigest()
    assert second.exit_code == 1
    assert "refusing to overwrite" in second.stderr
