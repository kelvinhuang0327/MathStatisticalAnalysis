"""Causal batch and CLI contracts for wave 63."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, cast

from typer.testing import CliRunner

import lottolab.infrastructure.legacy_advanced_methods_native_batch_import_wave63 as batch_module
from lottolab.application.biglotto_multi_ticket_backtest import (
    evaluate_biglotto_multi_ticket_backtest,
)
from lottolab.application.legacy_advanced_methods_native_portfolios_wave63 import (
    FIRST_TARGET_REASON,
    METHOD_ORDER,
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


def test_wave63_batch_preserves_closure_native_order_and_one_ordered20(
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
        batch_module.materialize_legacy_advanced_methods_native_wave63_batch(
            database=Path("unused.db"),
            expected_database_sha256=PINNED_DATASET_SHA256,
        )
    )
    executions = cast(list[dict[str, Any]], document["executions"])

    assert len(executions) == 2
    assert executions[0] == {
        "reason_code": FIRST_TARGET_REASON,
        "status": "CLOSED_INSUFFICIENT_HISTORY",
        "strategy_id": (
            "legacy_biglotto__advanced_methods_benchmark__87ee0d15033c"
        ),
        "strategy_version": (
            "legacy-source-49a25effa62f-87ee0d15033c"
        ),
        "target_draw_number": "96000001",
    }
    execution = executions[1]
    native = cast(dict[str, Any], execution["native_generation"])
    assert execution["status"] == "OK"
    assert execution["candidate_k"] == 49
    assert execution["combination_count"] == 10
    assert execution["native_ticket_count"] == 25
    assert len(cast(list[object], execution["native_tickets"])) == 25
    assert execution["portfolio_ticket_count"] == 20
    assert len(cast(list[object], execution["ordered_portfolio"])) == 20
    assert native["candidate_k"] is None
    assert native["combination_count"] is None
    assert native["local_configuration_count"] == 10
    assert native["native_duplicate_ticket_count"] == 23
    assert native["local_method_order"] == METHOD_ORDER

    provenance = cast(dict[str, Any], document["source_provenance"])
    assert provenance["execution_status_counts"] == {
        "CLOSED_INSUFFICIENT_HISTORY": 1,
        "OK": 1,
    }
    assert provenance["native_ticket_count_distribution"] == {"25": 2148}
    assert provenance["combination_count_distribution"] == {"10": 2148}

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


def test_wave63_cli_is_registered() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert (
        "materialize-biglotto-advanced-methods-native-wave63-batch"
        in result.stdout
    )
