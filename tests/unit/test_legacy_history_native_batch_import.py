"""Causal batch tests for four frozen history-native BIG_LOTTO methods."""

from __future__ import annotations

import hashlib
import json
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any, cast

from typer.testing import CliRunner

from lottolab.application.biglotto_multi_ticket_backtest import (
    evaluate_biglotto_multi_ticket_backtest,
)
from lottolab.application.legacy_history_native_portfolios import (
    EXHAUSTIVE_AUDIT_METHOD_ID,
    OPTIMIZED_ENSEMBLE_METHOD_ID,
    QUICK_ML_METHOD_ID,
    QUICK_ML_PATTERN_SLICE_REASON,
    SOCIAL_WISDOM_METHOD_ID,
)
from lottolab.infrastructure.legacy_history_native_batch_import import (
    materialize_legacy_history_native_batch,
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
    rng = random.Random(20260728)
    first_date = date(2020, 1, 1)
    draws = [
        (
            str(index + 1),
            (first_date + timedelta(days=index)).strftime("%Y/%m/%d"),
            sorted(rng.sample(range(1, 50), 6)),
        )
        for index in range(55)
    ]
    connection.executemany(
        "INSERT INTO draws VALUES (?,?,?,?,?)",
        [
            (
                draw_number,
                draw_date,
                "BIG_LOTTO",
                json.dumps(numbers),
                next(number for number in range(1, 50) if number not in numbers),
            )
            for draw_number, draw_date, numbers in draws
        ],
    )
    last_draw_number, last_draw_date, last_numbers = draws[-1]
    special = next(number for number in range(1, 50) if number not in last_numbers)
    replay_rows: list[tuple[object, ...]] = [
        (
            1,
            last_draw_number,
            last_draw_date,
            "biglotto_triple_strike",
            "v0.1",
            draws[-2][0],
            "PREDICTED",
            None,
            json.dumps([1, 7, 15, 23, 28, 39]),
            json.dumps(last_numbers),
            special,
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
                draws[-2][0],
                "PREDICTED",
                None,
                json.dumps(ticket),
                json.dumps(last_numbers),
                special,
                None,
                index,
            )
        )
    connection.executemany(
        "INSERT INTO strategy_prediction_replays VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
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


def test_batch_preserves_per_method_success_and_closed_semantics(
    tmp_path: Path,
) -> None:
    database = tmp_path / "legacy.db"
    database_sha256 = _fixture_database(database)

    document = materialize_legacy_history_native_batch(
        database=database,
        expected_database_sha256=database_sha256,
    )

    executions = cast(list[dict[str, Any]], document["executions"])
    assert len(executions) == 4 * 55
    by_method = cast(
        dict[str, dict[str, int]],
        cast(dict[str, Any], document["source_provenance"])[
            "execution_status_counts_by_method"
        ],
    )
    assert by_method == {
        OPTIMIZED_ENSEMBLE_METHOD_ID: {
            "CLOSED_INSUFFICIENT_HISTORY": 1,
            "OK": 54,
        },
        SOCIAL_WISDOM_METHOD_ID: {
            "CLOSED_INSUFFICIENT_HISTORY": 1,
            "OK": 54,
        },
        QUICK_ML_METHOD_ID: {
            "CLOSED_EXECUTION_ERROR": 50,
            "CLOSED_INSUFFICIENT_HISTORY": 1,
            "OK": 4,
        },
        EXHAUSTIVE_AUDIT_METHOD_ID: {
            "CLOSED_INSUFFICIENT_HISTORY": 50,
            "OK": 5,
        },
    }
    successful = [row for row in executions if row["status"] == "OK"]
    assert len(successful) == 117
    assert all(len(row["ordered_portfolio"]) == 20 for row in successful)
    assert all(
        row["native_generation"]["history_cutoff_draw_number"]
        == row["history_cutoff_draw_number"]
        for row in successful
    )
    quick_errors = [
        row
        for row in executions
        if row.get("reason_code") == QUICK_ML_PATTERN_SLICE_REASON
    ]
    assert len(quick_errors) == 50
    assert all(row["status"] == "CLOSED_EXECUTION_ERROR" for row in quick_errors)
    provenance = cast(dict[str, Any], document["source_provenance"])
    assert provenance["database_sha256_before"] == database_sha256
    assert provenance["database_sha256_after"] == database_sha256


def test_batch_passes_complete_universe_evaluator(tmp_path: Path) -> None:
    database = tmp_path / "legacy.db"
    database_sha256 = _fixture_database(database)
    document = materialize_legacy_history_native_batch(
        database=database,
        expected_database_sha256=database_sha256,
    )

    report = evaluate_biglotto_multi_ticket_backtest(_canonical_bytes(document))

    assert report["target_draw_count"] == 55
    assert cast(dict[str, int], report["progress"]) == {
        "backtested_count": 135,
        "closed_count": 74,
        "duplicate_alias_count": 12,
        "owner_decision_required_count": 0,
        "reproduced_count": 135,
        "total_strategy_count": 221,
        "uncompleted_count": 0,
    }
    audit = cast(list[dict[str, Any]], report["execution_audit"])
    successful = [row for row in audit if row["status"] == "OK"]
    assert all(row["native_generation"]["seed_digest"] for row in successful)


def test_cli_is_registered_and_refuses_overwrite(tmp_path: Path) -> None:
    database = tmp_path / "legacy.db"
    database_sha256 = _fixture_database(database)
    output = tmp_path / "input.json"
    args = [
        "materialize-biglotto-history-native-batch",
        "--database",
        str(database),
        "--expected-database-sha256",
        database_sha256,
        "--output-file",
        str(output),
    ]

    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    summary = json.loads(result.stdout)
    assert summary["execution_count"] == 220
    assert summary["execution_status_counts"] == {
        "CLOSED_EXECUTION_ERROR": 50,
        "CLOSED_INSUFFICIENT_HISTORY": 53,
        "OK": 117,
    }
    assert output.read_bytes().endswith(b"\n")

    second = runner.invoke(app, args)
    assert second.exit_code == 1
    assert "refusing to overwrite" in second.stderr
