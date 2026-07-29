"""Causal batch contracts for wave 55."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, cast

from tests.unit.test_legacy_checkpoint_native_portfolios_wave55 import (
    CONTEXT,
)
from typer.testing import CliRunner

import lottolab.application.legacy_checkpoint_native_portfolios_wave55 as portfolio_module
import lottolab.infrastructure.legacy_checkpoint_native_batch_import_wave55 as batch_module
from lottolab.application.biglotto_multi_ticket_backtest import (
    evaluate_biglotto_multi_ticket_backtest,
)
from lottolab.application.legacy_checkpoint_native_portfolios_wave55 import (
    PINNED_DATASET_SHA256,
)
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    PinnedBigLottoDraw,
    PinnedBigLottoHistory,
)
from lottolab.interfaces.cli.main import app

runner = CliRunner()
_DATES = (
    date(2026, 2, 6),
    date(2026, 2, 10),
    date(2026, 2, 12),
    date(2026, 2, 13),
    date(2026, 2, 14),
    date(2026, 2, 15),
    date(2026, 2, 16),
    date(2026, 2, 17),
    date(2026, 2, 18),
    date(2026, 2, 19),
    date(2026, 2, 20),
    date(2026, 2, 21),
    date(2026, 2, 22),
    date(2026, 2, 23),
    date(2026, 2, 24),
)


def _fake_history() -> PinnedBigLottoHistory:
    draws = [
        PinnedBigLottoDraw(
            draw_number=draw_number,
            draw_date=_DATES[index],
            numbers=numbers,
            special=next(
                number for number in range(1, 50) if number not in numbers
            ),
        )
        for index, (draw_number, numbers) in enumerate(CONTEXT)
    ]
    draws.append(
        PinnedBigLottoDraw(
            draw_number="115000026",
            draw_date=date(2026, 2, 25),
            numbers=(7, 15, 22, 38, 45, 49),
            special=31,
        )
    )
    return PinnedBigLottoHistory(
        draws=tuple(draws),
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


def test_wave55_batch_preserves_causal_checkpoint_coverage(
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
    ledger = (
        portfolio_module.load_legacy_checkpoint_native_wave55_ledger_for_verification()
    )

    def fake_context(history: tuple[LegacyHistoryDraw, ...]) -> str:
        del history
        return ledger.context_sha256[0]

    monkeypatch.setattr(
        portfolio_module,
        "_full_context_sha256",
        fake_context,
    )

    document = (
        batch_module.materialize_legacy_checkpoint_native_wave55_batch(
            database=Path("unused.db"),
            expected_database_sha256=PINNED_DATASET_SHA256,
        )
    )
    executions = cast(list[dict[str, Any]], document["executions"])
    successful = [row for row in executions if row["status"] == "OK"]
    rejected = [
        row for row in executions if row["status"] == "CLOSED_REJECTED"
    ]

    assert len(executions) == 32
    assert len(successful) == 2
    assert len(rejected) == 30
    assert all(
        row["candidate_k"] == 49
        and row["combination_count"] is None
        and row["native_ticket_count"] in {3, 6}
        and len(cast(list[object], row["ordered_portfolio"])) == 20
        for row in successful
    )
    provenance = cast(dict[str, Any], document["source_provenance"])
    assert provenance["execution_status_counts"] == {
        "CLOSED_REJECTED": 30,
        "OK": 2,
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


def test_wave55_cli_is_registered() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert (
        "materialize-biglotto-checkpoint-native-wave55-batch"
        in result.stdout
    )
