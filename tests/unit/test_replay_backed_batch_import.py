"""Read-only exact replay batch materialization tests."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, cast

import pytest
from typer.testing import CliRunner

from lottolab.application.biglotto_multi_ticket_backtest import INPUT_SCHEMA_VERSION
from lottolab.infrastructure.replay_backed_batch_import import (
    ReplayBatchImportError,
    load_pinned_biglotto_history,
    materialize_exact_replay_batch,
)
from lottolab.interfaces.cli.main import app

runner = CliRunner()


def _draws_only_fixture_database(path: Path) -> str:
    """A database with draw history but no strategy_prediction_replays table."""

    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE draws (
            draw TEXT, date TEXT, lottery_type TEXT, numbers TEXT, special INTEGER
        );
        CREATE VIEW draws_big_lotto_canonical_main AS
        SELECT * FROM draws WHERE lottery_type = 'BIG_LOTTO';
        """
    )
    for index in range(1, 11):
        numbers = sorted(((index + offset * 7) % 49) + 1 for offset in range(6))
        special = next(number for number in range(1, 50) if number not in numbers)
        connection.execute(
            "INSERT INTO draws VALUES (?,?,?,?,?)",
            (
                str(index),
                f"2020/01/{index:02d}",
                "BIG_LOTTO",
                json.dumps(numbers),
                special,
            ),
        )
    connection.commit()
    connection.close()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture_database(path: Path, *, noncausal: bool = False) -> str:
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
    for index in range(1, 31):
        numbers = sorted(((index + offset * 7) % 49) + 1 for offset in range(6))
        special = next(number for number in range(1, 50) if number not in numbers)
        connection.execute(
            "INSERT INTO draws VALUES (?,?,?,?,?)",
            (
                str(index),
                f"2020/01/{index:02d}",
                "BIG_LOTTO",
                json.dumps(numbers),
                special,
            ),
        )
    target_numbers = sorted(((30 + offset * 7) % 49) + 1 for offset in range(6))
    target_special = next(
        number for number in range(1, 50) if number not in target_numbers
    )
    cutoff = "30" if noncausal else "29"
    replay_rows: list[tuple[object, ...]] = [
        (
            1,
            "30",
            "2020/01/30",
            "biglotto_triple_strike",
            "v0.1",
            cutoff,
            "PREDICTED",
            None,
            json.dumps([1, 7, 15, 23, 28, 39]),
            json.dumps(target_numbers),
            target_special,
            "5",
            1,
        ),
        (
            2,
            "30",
            "2020/01/30",
            "biglotto_triple_strike",
            "v0.1",
            cutoff,
            "PREDICTED",
            None,
            json.dumps([1, 7, 15, 23, 28, 39]),
            json.dumps(target_numbers),
            target_special,
            "5",
            2,
        ),
    ]
    for bet_index, ticket in enumerate(
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
                2 + bet_index,
                "30",
                "2020/01/30",
                "biglotto_ts3_markov_4bet_w30",
                "v0.1",
                cutoff,
                "PREDICTED",
                None,
                json.dumps(ticket),
                json.dumps(target_numbers),
                target_special,
                None,
                bet_index,
            )
        )
    connection.executemany(
        "INSERT INTO strategy_prediction_replays VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        replay_rows,
    )
    connection.commit()
    connection.close()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_materialization_preserves_native_counts_order_and_one_ordered_20(
    tmp_path: Path,
) -> None:
    database = tmp_path / "legacy.db"
    database_sha256 = _fixture_database(database)

    document = materialize_exact_replay_batch(
        database=database,
        expected_database_sha256=database_sha256,
    )

    assert document["schema_version"] == INPUT_SCHEMA_VERSION
    assert document["dataset_sha256"] == database_sha256
    assert len(cast(list[object], document["targets"])) == 1
    executions = cast(list[dict[str, Any]], document["executions"])
    assert len(executions) == 2
    assert {row["native_ticket_count"] for row in executions} == {3, 4}
    assert all(len(row["ordered_portfolio"]) == 20 for row in executions)
    ts4 = next(row for row in executions if row["native_ticket_count"] == 4)
    assert ts4["native_tickets"] == [
        [1, 2, 3, 4, 5, 6],
        [7, 8, 9, 10, 11, 12],
        [13, 14, 15, 16, 17, 18],
        [19, 20, 21, 22, 23, 24],
    ]
    provenance = cast(dict[str, Any], document["source_provenance"])
    assert provenance["database_sha256_before"] == database_sha256
    assert provenance["database_sha256_after"] == database_sha256
    assert provenance["registry_execution_counts"] == {
        "biglotto_triple_strike": 1,
        "biglotto_ts3_markov_4bet_w30": 1,
    }
    assert hashlib.sha256(database.read_bytes()).hexdigest() == database_sha256


def test_noncausal_replay_and_wrong_database_pin_are_rejected(tmp_path: Path) -> None:
    database = tmp_path / "legacy.db"
    database_sha256 = _fixture_database(database, noncausal=True)

    with pytest.raises(ReplayBatchImportError, match="not causal"):
        materialize_exact_replay_batch(
            database=database,
            expected_database_sha256=database_sha256,
        )
    with pytest.raises(ReplayBatchImportError, match="caller pin"):
        materialize_exact_replay_batch(
            database=database,
            expected_database_sha256="0" * 64,
        )


def test_load_pinned_biglotto_history_defaults_to_requiring_replay_authority(
    tmp_path: Path,
) -> None:
    database = tmp_path / "draws_only.db"
    database_sha256 = _draws_only_fixture_database(database)

    with pytest.raises(ReplayBatchImportError, match="strategy replay table"):
        load_pinned_biglotto_history(
            database=database,
            expected_database_sha256=database_sha256,
        )


def test_load_pinned_biglotto_history_without_replay_authority_reads_draws_only(
    tmp_path: Path,
) -> None:
    database = tmp_path / "draws_only.db"
    database_sha256 = _draws_only_fixture_database(database)

    history = load_pinned_biglotto_history(
        database=database,
        expected_database_sha256=database_sha256,
        require_replay_authority=False,
    )

    assert len(history.draws) == 10
    assert history.replay_truth_supplemented_draw_count == 0
    assert history.database_sha256_before == database_sha256
    assert history.database_sha256_after == database_sha256


def test_materialize_exact_replay_batch_still_requires_replay_authority(
    tmp_path: Path,
) -> None:
    database = tmp_path / "draws_only.db"
    database_sha256 = _draws_only_fixture_database(database)

    with pytest.raises(ReplayBatchImportError, match="strategy replay table"):
        materialize_exact_replay_batch(
            database=database,
            expected_database_sha256=database_sha256,
        )


def test_cli_creates_canonical_input_and_refuses_overwrite(tmp_path: Path) -> None:
    database = tmp_path / "legacy.db"
    database_sha256 = _fixture_database(database)
    output = tmp_path / "input.json"
    args = [
        "materialize-biglotto-replay-batch",
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
    assert summary["execution_count"] == 2
    assert output.read_bytes().endswith(b"\n")

    second = runner.invoke(app, args)
    assert second.exit_code == 1
    assert "refusing to overwrite" in second.stderr
