"""Causal materialization tests for the two random-native legacy methods."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, cast

from typer.testing import CliRunner

from lottolab.application.biglotto_multi_ticket_backtest import (
    evaluate_biglotto_multi_ticket_backtest,
)
from lottolab.infrastructure.legacy_random_batch_import import (
    materialize_legacy_random_native_batch,
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
    draws = (
        ("1", "2020/01/01", [1, 8, 15, 22, 29, 36], 2),
        ("2", "2020/01/02", [3, 10, 17, 24, 31, 38], 4),
        ("3", "2020/01/03", [5, 12, 19, 26, 33, 40], 6),
        ("4", "2020/01/04", [7, 14, 21, 28, 35, 42], 8),
    )
    connection.executemany(
        "INSERT INTO draws VALUES (?,?,?,?,?)",
        [
            (draw, draw_date, "BIG_LOTTO", json.dumps(numbers), special)
            for draw, draw_date, numbers, special in draws
        ],
    )
    replay_rows: list[tuple[object, ...]] = [
        (
            1,
            "4",
            "2020/01/04",
            "biglotto_triple_strike",
            "v0.1",
            "3",
            "PREDICTED",
            None,
            json.dumps([1, 7, 15, 23, 28, 39]),
            json.dumps(draws[-1][2]),
            draws[-1][3],
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
                1 + index,
                "4",
                "2020/01/04",
                "biglotto_ts3_markov_4bet_w30",
                "v0.1",
                "3",
                "PREDICTED",
                None,
                json.dumps(ticket),
                json.dumps(draws[-1][2]),
                draws[-1][3],
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


def test_random_native_batch_has_explicit_genesis_close_and_causal_successes(
    tmp_path: Path,
) -> None:
    database = tmp_path / "legacy.db"
    database_sha256 = _fixture_database(database)

    document = materialize_legacy_random_native_batch(
        database=database,
        expected_database_sha256=database_sha256,
    )

    targets = cast(list[dict[str, Any]], document["targets"])
    executions = cast(list[dict[str, Any]], document["executions"])
    assert len(targets) == 4
    assert len(executions) == 8
    assert sum(row["status"] == "CLOSED_INSUFFICIENT_HISTORY" for row in executions) == 2
    successful = [row for row in executions if row["status"] == "OK"]
    assert len(successful) == 6
    assert {row["native_ticket_count"] for row in successful} == {3}
    assert all(len(row["ordered_portfolio"]) == 20 for row in successful)
    assert all(
        row["history_cutoff_draw_number"]
        == str(int(cast(str, row["target_draw_number"])) - 1)
        for row in successful
    )
    assert all(
        row["native_generation"]["target_draw_number"]
        == row["target_draw_number"]
        for row in successful
    )
    assert all(
        "winning_main_numbers" not in row["native_generation"]
        for row in successful
    )
    provenance = cast(dict[str, Any], document["source_provenance"])
    assert provenance["execution_status_counts"] == {
        "CLOSED_INSUFFICIENT_HISTORY": 2,
        "OK": 6,
    }
    assert provenance["database_sha256_before"] == database_sha256
    assert provenance["database_sha256_after"] == database_sha256


def test_random_native_input_passes_complete_universe_evaluator(
    tmp_path: Path,
) -> None:
    database = tmp_path / "legacy.db"
    database_sha256 = _fixture_database(database)
    document = materialize_legacy_random_native_batch(
        database=database,
        expected_database_sha256=database_sha256,
    )

    report = evaluate_biglotto_multi_ticket_backtest(
        _canonical_bytes(document)
    )

    assert report["target_draw_count"] == 4
    progress = cast(dict[str, int], report["progress"])
    assert progress == {
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


def test_random_native_cli_is_registered_and_refuses_overwrite(
    tmp_path: Path,
) -> None:
    database = tmp_path / "legacy.db"
    database_sha256 = _fixture_database(database)
    output = tmp_path / "input.json"
    args = [
        "materialize-biglotto-random-native-batch",
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
    assert summary["execution_count"] == 8
    assert summary["execution_status_counts"]["OK"] == 6
    assert output.read_bytes().endswith(b"\n")

    second = runner.invoke(app, args)
    assert second.exit_code == 1
    assert "refusing to overwrite" in second.stderr
