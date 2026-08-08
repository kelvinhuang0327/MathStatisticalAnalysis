"""Causal batch and CLI contracts for wave 61."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, cast

from typer.testing import CliRunner

import lottolab.infrastructure.legacy_five_bet_native_batch_import_wave61 as batch_module
from lottolab.application.biglotto_multi_ticket_backtest import (
    evaluate_biglotto_multi_ticket_backtest,
)
from lottolab.application.legacy_five_bet_native_portfolios_wave61 import (
    PINNED_DATASET_SHA256,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    PinnedBigLottoDraw,
    PinnedBigLottoHistory,
)
from lottolab.interfaces.cli.main import app

runner = CliRunner()


def _fake_history() -> PinnedBigLottoHistory:
    return PinnedBigLottoHistory(
        draws=(
            PinnedBigLottoDraw(
                draw_number="96000001",
                draw_date=date(2007, 1, 2),
                numbers=(13, 21, 23, 27, 31, 49),
                special=19,
            ),
            PinnedBigLottoDraw(
                draw_number="96000002",
                draw_date=date(2007, 1, 5),
                numbers=(12, 19, 23, 42, 44, 48),
                special=33,
            ),
        ),
        database_sha256_before=PINNED_DATASET_SHA256,
        database_sha256_after=PINNED_DATASET_SHA256,
        replay_truth_supplemented_draw_count=0,
    )


def _canonical_bytes(document: dict[str, object]) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def test_wave61_batch_preserves_source_horizon_closures(
    monkeypatch: Any,
) -> None:
    def fake_load(
        *,
        database: Path,
        expected_database_sha256: str,
        require_replay_authority: bool = False,
    ) -> PinnedBigLottoHistory:
        del database, expected_database_sha256
        return _fake_history()

    monkeypatch.setattr(
        batch_module,
        "load_pinned_biglotto_history",
        fake_load,
    )
    document = (
        batch_module.materialize_legacy_five_bet_native_wave61_batch(
            database=Path("unused.db"),
            expected_database_sha256=PINNED_DATASET_SHA256,
        )
    )
    executions = cast(list[dict[str, Any]], document["executions"])

    assert len(executions) == 2
    assert {row["status"] for row in executions} == {
        "CLOSED_REJECTED"
    }
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


def test_wave61_cli_is_registered() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert (
        "materialize-biglotto-five-bet-native-wave61-batch"
        in result.stdout
    )
