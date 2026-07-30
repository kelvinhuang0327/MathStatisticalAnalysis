"""Causal batch tests for the fourteenth source-native wave."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any, cast

from typer.testing import CliRunner

from lottolab.application.biglotto_multi_ticket_backtest import (
    evaluate_biglotto_multi_ticket_backtest,
)
from lottolab.application.legacy_source_native_portfolios_wave14 import (
    GRAPH_PREDICTOR_METHOD_ID,
    HIGH_PRIZE_TREND_METHOD_ID,
)
from lottolab.infrastructure.legacy_source_native_batch_import_wave14 import (
    materialize_legacy_source_native_wave14_batch,
)
from lottolab.interfaces.cli.main import app

runner = CliRunner()


def _canonical_bytes(document: dict[str, object]) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


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
    for index in range(105):
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


def test_wave14_batch_preserves_native_and_closed_semantics(
    tmp_path: Path,
) -> None:
    database = tmp_path / "legacy.db"
    database_sha256 = _fixture_database(database)
    document = materialize_legacy_source_native_wave14_batch(
        database=database,
        expected_database_sha256=database_sha256,
    )

    executions = cast(list[dict[str, Any]], document["executions"])
    assert len(executions) == 210
    by_method: dict[str, list[dict[str, Any]]] = {
        GRAPH_PREDICTOR_METHOD_ID: [],
        HIGH_PRIZE_TREND_METHOD_ID: [],
    }
    strategy_to_method = {
        "legacy_biglotto__graph_predictor__cd70713a5709": (
            GRAPH_PREDICTOR_METHOD_ID
        ),
        "legacy_biglotto__high_prize_trend_optimizer__0fc72409150e": (
            HIGH_PRIZE_TREND_METHOD_ID
        ),
    }
    for row in executions:
        by_method[
            strategy_to_method[cast(str, row["strategy_id"])]
        ].append(row)

    graph_counts = Counter(
        cast(str, row["status"])
        for row in by_method[GRAPH_PREDICTOR_METHOD_ID]
    )
    trend_counts = Counter(
        cast(str, row["status"])
        for row in by_method[HIGH_PRIZE_TREND_METHOD_ID]
    )
    assert graph_counts == {
        "CLOSED_INSUFFICIENT_HISTORY": 1,
        "OK": 104,
    }
    assert trend_counts == {
        "CLOSED_INSUFFICIENT_HISTORY": 100,
        "OK": 5,
    }
    successful = [
        row for row in executions if row["status"] == "OK"
    ]
    assert all(
        len(row["ordered_portfolio"]) == 20 for row in successful
    )
    graph_first = next(
        row
        for row in successful
        if row["strategy_id"]
        == "legacy_biglotto__graph_predictor__cd70713a5709"
    )
    trend_first = next(
        row
        for row in successful
        if row["strategy_id"]
        == "legacy_biglotto__high_prize_trend_optimizer__0fc72409150e"
    )
    assert graph_first["candidate_k"] == 15
    assert graph_first["combination_count"] is None
    assert graph_first["native_ticket_count"] == 1
    assert trend_first["candidate_k"] is None
    assert trend_first["combination_count"] == 7
    assert trend_first["native_ticket_count"] == 7
    provenance = cast(dict[str, Any], document["source_provenance"])
    assert provenance["database_sha256_before"] == database_sha256
    assert provenance["database_sha256_after"] == database_sha256
    assert provenance["source_result_selection"].startswith(
        "NO_TARGET_OUTCOME_CONFIGURATION_SELECTION"
    )


def test_wave14_batch_is_byte_reproducible(tmp_path: Path) -> None:
    database = tmp_path / "legacy.db"
    database_sha256 = _fixture_database(database)

    first = materialize_legacy_source_native_wave14_batch(
        database=database,
        expected_database_sha256=database_sha256,
    )
    second = materialize_legacy_source_native_wave14_batch(
        database=database,
        expected_database_sha256=database_sha256,
    )

    assert json.dumps(
        first,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ) == json.dumps(
        second,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def test_wave14_batch_passes_complete_universe_evaluator(
    tmp_path: Path,
) -> None:
    database = tmp_path / "legacy.db"
    database_sha256 = _fixture_database(database)
    document = materialize_legacy_source_native_wave14_batch(
        database=database,
        expected_database_sha256=database_sha256,
    )

    report = evaluate_biglotto_multi_ticket_backtest(
        _canonical_bytes(document)
    )

    assert report["target_draw_count"] == 105
    assert cast(dict[str, int], report["progress"]) == {
        "backtested_count": 135,
        "closed_count": 74,
        "duplicate_alias_count": 12,
        "owner_decision_required_count": 0,
        "reproduced_count": 135,
        "total_strategy_count": 221,
        "uncompleted_count": 0,
    }


def test_wave14_cli_is_registered_and_refuses_overwrite(
    tmp_path: Path,
) -> None:
    database = tmp_path / "legacy.db"
    database_sha256 = _fixture_database(database)
    output = tmp_path / "input.json"
    args = [
        "materialize-biglotto-source-native-wave14-batch",
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
    assert summary["execution_count"] == 210
    assert summary["target_draw_count"] == 105
    assert summary["execution_status_counts"] == {
        "CLOSED_INSUFFICIENT_HISTORY": 101,
        "OK": 109,
    }
    assert summary["input_sha256"] == hashlib.sha256(
        output.read_bytes()
    ).hexdigest()
    assert second.exit_code == 1
    assert "refusing to overwrite" in second.stderr
