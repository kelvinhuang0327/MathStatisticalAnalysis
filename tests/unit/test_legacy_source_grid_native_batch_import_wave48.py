"""Causal materialization contracts for wave 48."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any, cast

from typer.testing import CliRunner

import lottolab.application.legacy_source_grid_native_portfolios_wave48 as portfolio_module
import lottolab.infrastructure.legacy_source_grid_native_batch_import_wave48 as batch_module
from lottolab.application.legacy_source_grid_native_portfolios_wave48 import (
    DIRECTION_3_METHOD_ID,
    ENHANCEMENTS_METHOD_ID,
    PINNED_DATASET_SHA256,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    PinnedBigLottoDraw,
    PinnedBigLottoHistory,
)
from lottolab.interfaces.cli.main import app

runner = CliRunner()


def _fake_history() -> PinnedBigLottoHistory:
    ledger = portfolio_module.load_legacy_source_grid_native_wave48_ledger_for_verification()
    base = date(2000, 1, 1)
    draws = [
        PinnedBigLottoDraw(
            draw_number=("synthetic-root" if index == 0 else ledger.targets[index - 1]),
            draw_date=base + timedelta(days=index),
            numbers=(1, 2, 3, 4, 5, 6),
            special=7,
        )
        for index in range(650)
    ]
    return PinnedBigLottoHistory(
        draws=tuple(draws),
        database_sha256_before=PINNED_DATASET_SHA256,
        database_sha256_after=PINNED_DATASET_SHA256,
        replay_truth_supplemented_draw_count=0,
    )


def test_wave48_batch_preserves_minimums_native_positions_and_ordered20(
    monkeypatch: Any,
) -> None:
    ledger = portfolio_module.load_legacy_source_grid_native_wave48_ledger_for_verification()

    def fake_load(
        *,
        database: Path,
        expected_database_sha256: str,
        require_replay_authority: bool = False,
    ) -> PinnedBigLottoHistory:
        del database, expected_database_sha256
        return _fake_history()

    def fake_context(history: object) -> str:
        return ledger.context_sha256[len(cast(tuple[object, ...], history)) - 1]

    monkeypatch.setattr(batch_module, "load_pinned_biglotto_history", fake_load)
    monkeypatch.setattr(portfolio_module, "_context_sha256", fake_context)

    document = batch_module.materialize_legacy_source_grid_native_wave48_batch(
        database=Path("unused.db"),
        expected_database_sha256=PINNED_DATASET_SHA256,
    )
    executions = cast(list[dict[str, Any]], document["executions"])
    successful = [row for row in executions if row["status"] == "OK"]
    closed = [row for row in executions if row["status"] == "CLOSED_INSUFFICIENT_HISTORY"]

    assert len(executions) == 1300
    assert len(successful) == 151
    assert len(closed) == 1149
    assert all(
        row["candidate_k"] == 49
        and len(cast(list[object], row["ordered_portfolio"])) == 20
        and len(set(map(tuple, cast(list[list[int]], row["ordered_portfolio"])))) == 20
        for row in successful
    )
    provenance = cast(dict[str, Any], document["source_provenance"])
    assert provenance["execution_status_counts"] == {
        "CLOSED_INSUFFICIENT_HISTORY": 1149,
        "OK": 151,
    }
    assert (
        cast(dict[str, int], provenance["native_ticket_count"])[ENHANCEMENTS_METHOD_ID]
        == 42
    )
    assert (
        cast(dict[str, int], provenance["source_configuration_count"])[DIRECTION_3_METHOD_ID]
        == 2
    )
    enhancement_row = next(
        row
        for row in successful
        if row["native_generation"]["legacy_method_id"] == ENHANCEMENTS_METHOD_ID
    )
    assert len(cast(list[object], enhancement_row["native_tickets"])) == 42


def test_wave48_cli_is_registered() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "materialize-biglotto-source-grid-native-wave48-batch" in result.stdout
