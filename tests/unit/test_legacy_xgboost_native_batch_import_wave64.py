"""Causal batch and CLI contracts for wave 64."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, cast

from typer.testing import CliRunner

import lottolab.infrastructure.legacy_xgboost_native_batch_import_wave64 as batch_module
from lottolab.application.biglotto_multi_ticket_backtest import (
    evaluate_biglotto_multi_ticket_backtest,
)
from lottolab.application.legacy_xgboost_native_portfolios_wave64 import (
    CLOSED_REASON,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    PinnedBigLottoDraw,
)
from lottolab.interfaces.cli.main import app

runner = CliRunner()

_DRAWS = (
    ("96000001", "2007-01-02", (13, 21, 23, 27, 31, 49), 19),
    ("96000002", "2007-01-05", (12, 19, 23, 42, 44, 48), 33),
    ("96000003", "2007-01-09", (26, 28, 35, 39, 44, 45), 18),
    ("96000004", "2007-01-12", (10, 16, 26, 28, 31, 33), 44),
    ("96000005", "2007-01-16", (13, 28, 33, 38, 43, 48), 4),
    ("96000006", "2007-01-19", (6, 26, 27, 44, 45, 46), 2),
    ("96000007", "2007-01-23", (6, 7, 15, 31, 36, 44), 29),
    ("96000008", "2007-01-26", (8, 13, 18, 26, 34, 36), 17),
    ("96000009", "2007-01-30", (6, 18, 26, 39, 42, 45), 14),
    ("96000010", "2007-02-02", (7, 8, 10, 12, 47, 48), 38),
    ("96000011", "2007-02-06", (12, 16, 26, 32, 41, 48), 1),
    ("96000012", "2007-02-09", (7, 28, 30, 41, 45, 48), 44),
    ("96000013", "2007-02-13", (2, 8, 25, 39, 43, 46), 13),
    ("96000014", "2007-02-16", (18, 19, 27, 34, 44, 48), 37),
    ("96000015", "2007-02-20", (1, 13, 19, 33, 38, 45), 36),
    ("96000016", "2007-02-23", (5, 13, 25, 30, 39, 48), 36),
)


def _fake_draws() -> tuple[PinnedBigLottoDraw, ...]:
    return tuple(
        PinnedBigLottoDraw(
            draw_number=draw_number,
            draw_date=date.fromisoformat(draw_date),
            numbers=numbers,
            special=special,
        )
        for draw_number, draw_date, numbers, special in _DRAWS
    )


def _canonical_bytes(document: dict[str, object]) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def test_wave64_batch_preserves_closed_boundary_and_one_ordered20(
    monkeypatch: Any,
) -> None:
    def fake_load(path: Path) -> tuple[tuple[PinnedBigLottoDraw, ...], str]:
        del path
        return _fake_draws(), batch_module.HISTORY_INPUT_FILE_SHA256

    monkeypatch.setattr(batch_module, "_load_history_input", fake_load)
    document = batch_module.materialize_legacy_xgboost_native_wave64_batch(
        history_input=Path("unused.json")
    )
    executions = cast(list[dict[str, Any]], document["executions"])
    closed = [
        row
        for row in executions
        if row["status"] == "CLOSED_INSUFFICIENT_HISTORY"
    ]
    successful = [row for row in executions if row["status"] == "OK"]

    assert len(executions) == 16
    assert len(closed) == 15
    assert all(row["reason_code"] == CLOSED_REASON for row in closed)
    assert len(successful) == 1
    execution = successful[0]
    native = cast(dict[str, Any], execution["native_generation"])
    assert execution["candidate_k"] == 49
    assert execution["combination_count"] == 1
    assert execution["native_ticket_count"] == 1
    assert execution["native_tickets"] == [[6, 18, 26, 44, 45, 48]]
    assert execution["portfolio_ticket_count"] == 20
    assert len(cast(list[object], execution["ordered_portfolio"])) == 20
    assert native["candidate_k"] is None
    assert native["combination_count"] is None
    assert native["local_configuration_count"] == 1
    assert native["model_label_count"] == 49

    provenance = cast(dict[str, Any], document["source_provenance"])
    assert provenance["execution_status_counts"] == {
        "CLOSED_INSUFFICIENT_HISTORY": 15,
        "OK": 1,
    }
    assert provenance["native_ticket_count_distribution"] == {"1": 1}
    assert provenance["combination_count_distribution"] == {"1": 1}

    report = evaluate_biglotto_multi_ticket_backtest(
        _canonical_bytes(document)
    )
    assert report["portfolio_contract"] == {
        "candidate_k_is_ticket_count": False,
        "combination_count_is_ticket_count": False,
        "prefix_counts": [5, 10, 15, 20],
        "same_ordered_20_portfolio_for_every_prefix": True,
    }
    metrics = cast(list[dict[str, Any]], report["metrics"])
    assert {metric["prefix_count"] for metric in metrics} == {
        5,
        10,
        15,
        20,
    }
    assert cast(dict[str, int], report["progress"]) == {
        "backtested_count": 135,
        "closed_count": 74,
        "duplicate_alias_count": 12,
        "owner_decision_required_count": 0,
        "reproduced_count": 135,
        "total_strategy_count": 221,
        "uncompleted_count": 0,
    }


def test_wave64_cli_is_registered() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert (
        "materialize-biglotto-xgboost-native-wave64-batch"
        in result.stdout
    )
