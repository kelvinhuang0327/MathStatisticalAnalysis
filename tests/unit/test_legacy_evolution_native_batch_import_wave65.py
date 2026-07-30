"""Causal batch and CLI contracts for wave 65."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any, cast

from typer.testing import CliRunner

import lottolab.application.legacy_evolution_native_portfolios_wave65 as evolution_module
import lottolab.infrastructure.legacy_evolution_native_batch_import_wave65 as batch_module
from lottolab.application.biglotto_multi_ticket_backtest import (
    evaluate_biglotto_multi_ticket_backtest,
)
from lottolab.application.legacy_evolution_native_portfolios_wave65 import (
    CLOSED_REASON,
    load_legacy_evolution_native_wave65_ledger_for_verification,
)
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    PinnedBigLottoDraw,
)
from lottolab.interfaces.cli.main import app

runner = CliRunner()


def _fake_draws() -> tuple[PinnedBigLottoDraw, ...]:
    ledger = load_legacy_evolution_native_wave65_ledger_for_verification()
    first_date = date(2007, 1, 1)
    return tuple(
        PinnedBigLottoDraw(
            draw_number=ledger.targets[index],
            draw_date=first_date + timedelta(days=index),
            numbers=(1, 2, 3, 4, 5, 6),
            special=7,
        )
        for index in range(502)
    )


def _canonical_bytes(document: dict[str, object]) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def test_wave65_batch_preserves_closed_boundary_and_one_ordered20(
    monkeypatch: Any,
) -> None:
    ledger = load_legacy_evolution_native_wave65_ledger_for_verification()

    def fake_load(path: Path) -> tuple[tuple[PinnedBigLottoDraw, ...], str]:
        del path
        return _fake_draws(), batch_module.HISTORY_INPUT_FILE_SHA256

    def indexed_context(
        history: tuple[LegacyHistoryDraw, ...],
    ) -> str:
        return ledger.context_sha256[len(history)]

    monkeypatch.setattr(batch_module, "_load_history_input", fake_load)
    monkeypatch.setattr(
        evolution_module,
        "_context_sha256",
        indexed_context,
    )
    document = (
        batch_module.materialize_legacy_evolution_native_wave65_batch(
            history_input=Path("unused.json")
        )
    )
    executions = cast(list[dict[str, Any]], document["executions"])
    closed = [
        row
        for row in executions
        if row["status"] == "CLOSED_INSUFFICIENT_HISTORY"
    ]
    successful = [row for row in executions if row["status"] == "OK"]

    assert len(executions) == 502
    assert len(closed) == 501
    assert all(row["reason_code"] == CLOSED_REASON for row in closed)
    assert len(successful) == 1
    execution = successful[0]
    native = cast(dict[str, Any], execution["native_generation"])
    assert execution["candidate_k"] is None
    assert execution["combination_count"] is None
    assert execution["native_ticket_count"] == 5
    assert cast(list[object], execution["native_tickets"])[1] == cast(
        list[object],
        execution["native_tickets"],
    )[3]
    assert execution["portfolio_ticket_count"] == 20
    assert len(cast(list[object], execution["ordered_portfolio"])) == 20
    assert native["candidate_k"] is None
    assert native["combination_count"] is None
    assert native["driver_population_size"] == 50
    assert native["total_strategies_tested"] == 482

    provenance = cast(dict[str, Any], document["source_provenance"])
    assert provenance["execution_status_counts"] == {
        "CLOSED_INSUFFICIENT_HISTORY": 501,
        "OK": 1,
    }
    assert provenance["native_ticket_count_distribution"] == {"5": 1}
    assert provenance[
        "native_duplicate_ticket_count_distribution"
    ] == {"1": 1}
    assert provenance["candidate_k"] is None
    assert provenance["combination_count"] is None

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


def test_wave65_cli_is_registered() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert (
        "materialize-biglotto-evolution-native-wave65-batch"
        in result.stdout
    )
