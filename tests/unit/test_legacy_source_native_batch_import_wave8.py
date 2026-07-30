"""Causal batch tests for the eighth source-native wave."""

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
from lottolab.application.legacy_source_native_portfolios_wave8 import (
    CLUSTER_ENHANCEMENTS_METHOD_ID,
    DYNAMIC_FREQUENCY_METHOD_ID,
    GEMINI_PHASE2_METHOD_ID,
    OPTIMIZE_THIRD_BET_METHOD_ID,
)
from lottolab.infrastructure.legacy_source_native_batch_import_wave8 import (
    materialize_legacy_source_native_wave8_batch,
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
    for index in range(205):
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
    connection.executemany("INSERT INTO draws VALUES (?,?,?,?,?)", rows)
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


def test_wave8_batch_preserves_candidate_configuration_and_closed_semantics(
    tmp_path: Path,
) -> None:
    database = tmp_path / "legacy.db"
    database_sha256 = _fixture_database(database)
    document = materialize_legacy_source_native_wave8_batch(
        database=database,
        expected_database_sha256=database_sha256,
    )

    executions = cast(list[dict[str, Any]], document["executions"])
    assert len(executions) == 820
    successful = [
        row for row in executions if row["status"] == "OK"
    ]
    closed = [
        row for row in executions if row["status"] != "OK"
    ]
    assert successful
    assert closed
    assert all(
        len(row["ordered_portfolio"]) == 20 for row in successful
    )
    assert all("ordered_portfolio" not in row for row in closed)
    by_method: dict[str, dict[str, Any]] = {}
    for row in successful:
        method_id = cast(
            str,
            row["native_generation"]["legacy_method_id"],
        )
        by_method.setdefault(method_id, row)
    assert by_method[GEMINI_PHASE2_METHOD_ID]["combination_count"] == 7
    assert by_method[GEMINI_PHASE2_METHOD_ID]["native_ticket_count"] == 7
    assert (
        by_method[DYNAMIC_FREQUENCY_METHOD_ID]["combination_count"]
        == 5
    )
    assert by_method[DYNAMIC_FREQUENCY_METHOD_ID][
        "native_ticket_count"
    ] == 1
    assert by_method[CLUSTER_ENHANCEMENTS_METHOD_ID][
        "combination_count"
    ] == 8
    optimized = by_method[OPTIMIZE_THIRD_BET_METHOD_ID]
    assert optimized["combination_count"] == 1
    assert optimized["native_ticket_count"] == 1
    assert cast(int, optimized["candidate_k"]) >= 20
    assert cast(int, optimized["candidate_combination_count"]) > 1
    provenance = cast(dict[str, Any], document["source_provenance"])
    assert provenance["database_sha256_before"] == database_sha256
    assert provenance["database_sha256_after"] == database_sha256


def test_wave8_batch_passes_complete_universe_evaluator(
    tmp_path: Path,
) -> None:
    database = tmp_path / "legacy.db"
    database_sha256 = _fixture_database(database)
    document = materialize_legacy_source_native_wave8_batch(
        database=database,
        expected_database_sha256=database_sha256,
    )

    report = evaluate_biglotto_multi_ticket_backtest(
        _canonical_bytes(document)
    )

    assert report["target_draw_count"] == 205
    assert cast(dict[str, int], report["progress"]) == {
        "backtested_count": 135,
        "closed_count": 74,
        "duplicate_alias_count": 12,
        "owner_decision_required_count": 0,
        "reproduced_count": 135,
        "total_strategy_count": 221,
        "uncompleted_count": 0,
    }


def test_wave8_cli_is_registered_and_refuses_overwrite(
    tmp_path: Path,
) -> None:
    database = tmp_path / "legacy.db"
    database_sha256 = _fixture_database(database)
    output = tmp_path / "input.json"
    args = [
        "materialize-biglotto-source-native-wave8-batch",
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
    assert summary["execution_count"] == 820
    assert summary["target_draw_count"] == 205
    assert summary["input_sha256"] == hashlib.sha256(
        output.read_bytes()
    ).hexdigest()
    assert second.exit_code == 1
    assert "refusing to overwrite" in second.stderr
