"""Causal materialization contracts for wave 45."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any, cast

from typer.testing import CliRunner

import lottolab.application.legacy_fft_native_portfolios_wave45 as portfolio_module
import lottolab.infrastructure.legacy_fft_native_batch_import_wave45 as batch_module
from lottolab.application.legacy_fft_native_portfolios_wave45 import (
    FCF_VS_TS3_METHOD_ID,
    PINNED_DATASET_SHA256,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    PinnedBigLottoDraw,
    PinnedBigLottoHistory,
)
from lottolab.interfaces.cli.main import app

runner = CliRunner()


def _fake_history() -> PinnedBigLottoHistory:
    ledger = portfolio_module.load_legacy_fft_native_wave45_ledger_for_verification()
    base = date(2000, 1, 1)
    draws: list[PinnedBigLottoDraw] = []
    for index in range(502):
        draw_number = f"synthetic-{index:04d}" if index < 150 else ledger.targets[index - 150]
        draws.append(
            PinnedBigLottoDraw(
                draw_number=draw_number,
                draw_date=base + timedelta(days=index),
                numbers=(1, 2, 3, 4, 5, 6),
                special=7,
            )
        )
    return PinnedBigLottoHistory(
        draws=tuple(draws),
        database_sha256_before=PINNED_DATASET_SHA256,
        database_sha256_after=PINNED_DATASET_SHA256,
        replay_truth_supplemented_draw_count=0,
    )


def test_wave45_batch_preserves_minimums_counts_and_ordered20(
    monkeypatch: Any,
) -> None:
    ledger = portfolio_module.load_legacy_fft_native_wave45_ledger_for_verification()

    def fake_load(
        *,
        database: Path,
        expected_database_sha256: str,
    ) -> PinnedBigLottoHistory:
        del database, expected_database_sha256
        return _fake_history()

    def fake_context(history: object) -> str:
        return ledger.context_sha256[len(cast(tuple[object, ...], history)) - 150]

    monkeypatch.setattr(
        batch_module,
        "load_pinned_biglotto_history",
        fake_load,
    )
    monkeypatch.setattr(
        portfolio_module,
        "_context_sha256",
        fake_context,
    )

    document = batch_module.materialize_legacy_fft_native_wave45_batch(
        database=Path("unused.db"),
        expected_database_sha256=PINNED_DATASET_SHA256,
    )
    executions = cast(list[dict[str, Any]], document["executions"])
    successful = [row for row in executions if row["status"] == "OK"]
    closed = [row for row in executions if row["status"] == "CLOSED_INSUFFICIENT_HISTORY"]

    assert len(executions) == 2008
    assert len(successful) == 357
    assert len(closed) == 1651
    assert all(
        row["candidate_k"] == 49 and len(cast(list[object], row["ordered_portfolio"])) == 20
        for row in successful
    )
    provenance = cast(dict[str, Any], document["source_provenance"])
    assert provenance["execution_status_counts"] == {
        "CLOSED_INSUFFICIENT_HISTORY": 1651,
        "OK": 357,
    }
    assert cast(dict[str, int], provenance["native_ticket_count"])[FCF_VS_TS3_METHOD_ID] == 6
    assert cast(dict[str, int | None], provenance["combination_count"])[FCF_VS_TS3_METHOD_ID] == 2


def test_wave45_cli_is_registered() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "materialize-biglotto-fft-native-wave45-batch" in result.stdout
