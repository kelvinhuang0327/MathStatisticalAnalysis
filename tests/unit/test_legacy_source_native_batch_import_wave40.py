"""Causal batch tests for the fortieth source-native wave."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any, cast

from tests.unit.test_legacy_source_native_batch_import_wave24 import (
    fixture_database_wave24,
)
from typer.testing import CliRunner

from lottolab.application.biglotto_multi_ticket_backtest import (
    evaluate_biglotto_multi_ticket_backtest,
)
from lottolab.infrastructure.legacy_source_native_batch_import_wave40 import (
    materialize_legacy_source_native_wave40_batch,
)
from lottolab.interfaces.cli.main import app

runner = CliRunner()


def fixture_database_wave40(path: Path) -> str:
    fixture_database_wave24(path)
    connection = sqlite3.connect(path)
    first_date = date(2020, 1, 1)
    rows: list[tuple[object, ...]] = []
    for index in range(40, 140):
        numbers = sorted(
            ((index * 7 + offset * 5) % 49) + 1
            for offset in range(6)
        )
        rows.append(
            (
                str(index + 1),
                (first_date + timedelta(days=index)).strftime("%Y/%m/%d"),
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


def test_wave40_batch_preserves_causal_and_native_semantics(
    tmp_path: Path,
) -> None:
    database = tmp_path / "legacy.db"
    database_sha256 = fixture_database_wave40(database)
    document = materialize_legacy_source_native_wave40_batch(
        database=database,
        expected_database_sha256=database_sha256,
    )

    executions = cast(list[dict[str, Any]], document["executions"])
    assert len(executions) == 140
    successful = [
        row for row in executions if row["status"] == "OK"
    ]
    assert len(successful) == 40
    assert all(
        row["candidate_k"] is None
        and row["combination_count"] == 3
        and row["native_ticket_count"] in (3, 4)
        and len(cast(list[object], row["ordered_portfolio"])) == 20
        for row in successful
    )
    provenance = cast(dict[str, Any], document["source_provenance"])
    assert provenance["database_sha256_before"] == database_sha256
    assert provenance["database_sha256_after"] == database_sha256
    assert provenance["execution_status_counts"] == {
        "CLOSED_INSUFFICIENT_HISTORY": 100,
        "OK": 40,
    }


def test_wave40_batch_passes_complete_universe_evaluator(
    tmp_path: Path,
) -> None:
    database = tmp_path / "legacy.db"
    database_sha256 = fixture_database_wave40(database)
    document = materialize_legacy_source_native_wave40_batch(
        database=database,
        expected_database_sha256=database_sha256,
    )

    report = evaluate_biglotto_multi_ticket_backtest(
        _canonical_bytes(document)
    )

    assert cast(dict[str, int], report["progress"]) == {
        "backtested_count": 135,
        "closed_count": 74,
        "duplicate_alias_count": 12,
        "owner_decision_required_count": 0,
        "reproduced_count": 135,
        "total_strategy_count": 221,
        "uncompleted_count": 0,
    }


def test_wave40_cli_is_registered_and_refuses_overwrite(
    tmp_path: Path,
) -> None:
    database = tmp_path / "legacy.db"
    database_sha256 = fixture_database_wave40(database)
    output = tmp_path / "input.json"
    args = [
        "materialize-biglotto-source-native-wave40-batch",
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
    assert summary["execution_count"] == 140
    assert summary["target_draw_count"] == 140
    assert summary["execution_status_counts"] == {
        "CLOSED_INSUFFICIENT_HISTORY": 100,
        "OK": 40,
    }
    assert summary["input_sha256"] == hashlib.sha256(
        output.read_bytes()
    ).hexdigest()
    assert second.exit_code == 1
    assert "refusing to overwrite" in second.stderr
