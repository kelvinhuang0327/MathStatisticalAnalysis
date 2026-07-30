"""Causal batch and CLI contracts for wave 57."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, cast

from typer.testing import CliRunner

import lottolab.infrastructure.legacy_hpsb_native_batch_import_wave57 as batch_module
from lottolab.application.biglotto_multi_ticket_backtest import (
    evaluate_biglotto_multi_ticket_backtest,
)
from lottolab.application.legacy_hpsb_native_portfolios_wave57 import (
    HPSB_METHOD_ID,
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


def test_wave57_batch_preserves_causal_coverage(
    monkeypatch: Any,
) -> None:
    def fake_load(
        *,
        database: Path,
        expected_database_sha256: str,
    ) -> PinnedBigLottoHistory:
        del database, expected_database_sha256
        return _fake_history()

    monkeypatch.setattr(
        batch_module,
        "load_pinned_biglotto_history",
        fake_load,
    )
    document = batch_module.materialize_legacy_hpsb_native_wave57_batch(
        database=Path("unused.db"),
        expected_database_sha256=PINNED_DATASET_SHA256,
    )
    executions = cast(list[dict[str, Any]], document["executions"])
    successful = [row for row in executions if row["status"] == "OK"]
    closed = [
        row
        for row in executions
        if row["status"] == "CLOSED_INSUFFICIENT_HISTORY"
    ]

    assert len(executions) == 2
    assert len(successful) == 1
    assert len(closed) == 1
    assert closed[0]["reason_code"] == "NO_PRIOR_DRAW_FOR_CAUSAL_CUTOFF"
    assert successful[0]["candidate_k"] == 49
    assert successful[0]["combination_count"] is None
    assert successful[0]["native_ticket_count"] == 1
    assert len(cast(list[object], successful[0]["ordered_portfolio"])) == 20
    provenance = cast(dict[str, Any], document["source_provenance"])
    assert provenance["execution_status_counts"] == {
        "CLOSED_INSUFFICIENT_HISTORY": 1,
        "OK": 1,
    }
    assert provenance["native_ticket_count"] == {HPSB_METHOD_ID: 1}

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


def test_wave57_cli_is_registered() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert (
        "materialize-biglotto-hpsb-native-wave57-batch"
        in result.stdout
    )
