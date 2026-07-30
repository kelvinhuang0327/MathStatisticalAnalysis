"""Causal materialization contracts for wave 50."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any, cast

from typer.testing import CliRunner

import lottolab.application.legacy_source_grid_native_portfolios_wave50 as portfolio_module
import lottolab.infrastructure.legacy_source_grid_native_batch_import_wave50 as batch_module
from lottolab.application.legacy_source_grid_native_portfolios_wave50 import (
    COVERING_METHOD_ID,
    EXHAUSTIVE_METHOD_ID,
    PINNED_DATASET_SHA256,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    PinnedBigLottoDraw,
    PinnedBigLottoHistory,
)
from lottolab.interfaces.cli.main import app

runner = CliRunner()


def _fake_history() -> PinnedBigLottoHistory:
    ledger = portfolio_module.load_legacy_source_grid_native_wave50_ledger_for_verification()
    base = date(2000, 1, 1)
    draws = [
        PinnedBigLottoDraw(
            draw_number=("synthetic-root" if index == 0 else ledger.targets[index - 1]),
            draw_date=base + timedelta(days=index),
            numbers=(1, 2, 3, 4, 5, 6),
            special=7,
        )
        for index in range(2000)
    ]
    return PinnedBigLottoHistory(
        draws=tuple(draws),
        database_sha256_before=PINNED_DATASET_SHA256,
        database_sha256_after=PINNED_DATASET_SHA256,
        replay_truth_supplemented_draw_count=0,
    )


def test_wave50_batch_preserves_minimums_native_positions_and_ordered20(
    monkeypatch: Any,
) -> None:
    ledger = portfolio_module.load_legacy_source_grid_native_wave50_ledger_for_verification()

    def fake_load(
        *,
        database: Path,
        expected_database_sha256: str,
    ) -> PinnedBigLottoHistory:
        del database, expected_database_sha256
        return _fake_history()

    def fake_context(history: object) -> str:
        return ledger.context_sha256[len(cast(tuple[object, ...], history)) - 1]

    monkeypatch.setattr(batch_module, "load_pinned_biglotto_history", fake_load)
    monkeypatch.setattr(portfolio_module, "_context_sha256", fake_context)

    document = batch_module.materialize_legacy_source_grid_native_wave50_batch(
        database=Path("unused.db"),
        expected_database_sha256=PINNED_DATASET_SHA256,
    )
    executions = cast(list[dict[str, Any]], document["executions"])
    successful = [row for row in executions if row["status"] == "OK"]
    closed = [
        row for row in executions if row["status"] == "CLOSED_INSUFFICIENT_HISTORY"
    ]

    assert len(executions) == 4000
    assert len(successful) == 1352
    assert len(closed) == 2648
    assert all(
        row["candidate_k"] == 49
        and len(cast(list[object], row["ordered_portfolio"])) == 20
        and len(set(map(tuple, cast(list[list[int]], row["ordered_portfolio"])))) == 20
        for row in successful
    )
    provenance = cast(dict[str, Any], document["source_provenance"])
    assert provenance["execution_status_counts"] == {
        "CLOSED_INSUFFICIENT_HISTORY": 2648,
        "OK": 1352,
    }
    assert (
        cast(dict[str, int], provenance["native_ticket_count"])[COVERING_METHOD_ID]
        == 40
    )
    assert (
        cast(dict[str, int], provenance["source_configuration_count"])[
            EXHAUSTIVE_METHOD_ID
        ]
        == 6
    )


def test_wave50_cli_is_registered() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "materialize-biglotto-source-grid-native-wave50-batch" in result.stdout
