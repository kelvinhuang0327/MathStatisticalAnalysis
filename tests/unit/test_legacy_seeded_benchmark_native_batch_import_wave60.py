"""Causal batch and CLI contracts for wave 60."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, cast

from typer.testing import CliRunner

import lottolab.infrastructure.legacy_seeded_benchmark_native_batch_import_wave60 as batch_module
from lottolab.application.biglotto_multi_ticket_backtest import (
    evaluate_biglotto_multi_ticket_backtest,
)
from lottolab.application.legacy_seeded_benchmark_native_portfolios_wave60 import (
    HYBRID_METHOD_ID,
    ORTHOGONAL_METHOD_ID,
    PINNED_DATASET_SHA256,
    ZONE_METHOD_ID,
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


def test_wave60_batch_preserves_config_and_native_counts(
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
    document = (
        batch_module.materialize_legacy_seeded_benchmark_native_wave60_batch(
            database=Path("unused.db"),
            expected_database_sha256=PINNED_DATASET_SHA256,
        )
    )
    executions = cast(list[dict[str, Any]], document["executions"])
    successful = [row for row in executions if row["status"] == "OK"]
    closed = [
        row
        for row in executions
        if row["status"] == "CLOSED_INSUFFICIENT_HISTORY"
    ]

    assert len(executions) == 6
    assert len(successful) == 3
    assert len(closed) == 3
    assert {
        (
            cast(dict[str, Any], row["native_generation"])[
                "legacy_method_id"
            ],
            row["combination_count"],
            row["native_ticket_count"],
        )
        for row in successful
    } == {
        (HYBRID_METHOD_ID, 4, 12),
        (ORTHOGONAL_METHOD_ID, 14, 35),
        (ZONE_METHOD_ID, 6, 18),
    }
    assert all(
        len(cast(list[object], row["ordered_portfolio"])) == 20
        for row in successful
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


def test_wave60_cli_is_registered() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert (
        "materialize-biglotto-seeded-benchmark-native-wave60-batch"
        in result.stdout
    )
