# pyright: reportPrivateUsage=false

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import cast

import pytest
import tools.run_daily539_t539_wave1 as runner_module
from tools.run_daily539_t539_wave1 import (
    BIGLOTTO68_TO_T539_CROSS_LOTTERY_CONFIG,
    BLOCKED_DAILY539_STRATEGIES,
    DEFAULT_STRATEGY_SPECS,
    LOTTERY_TYPE,
    RUN_ID,
    STRATEGY_SET_CONFIGS,
    WAVE1_CONFIG,
    WAVE2_F4COLD_SINGLE_CONFIG,
    WAVE3_ACB1_ALIAS_CONFIG,
    WAVE4_REMAINING5_BATCH_CONFIG,
    SourceDraw,
    StrategySpec,
    load_external_source_cache,
    run_batch,
    source_payload_sha256,
)

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow


def _draws(count: int = 9) -> tuple[SourceDraw, ...]:
    start = date(2020, 1, 1)
    return tuple(
        SourceDraw(
            draw_id=str(1000 + index),
            draw_date=(start + timedelta(days=index)).isoformat(),
            numbers=tuple(sorted(((index + step * 8) % 39) + 1 for step in range(5))),
        )
        for index in range(count)
    )


class _GoodPortfolio:
    strategy_id = "test_good_portfolio"
    strategy_name = "test good"
    strategy_version = "v-test"
    min_history = 3
    native_ticket_count = 2

    def get_bets(self, history: object, lottery_type: LotteryType) -> tuple[tuple[int, ...], ...]:
        assert lottery_type is LotteryType.DAILY_539
        rows = cast(tuple[CausalDrawRow, ...], history)
        return (rows[-1].numbers, (1, 2, 3, 4, 5))


class _FailingPortfolio(_GoodPortfolio):
    strategy_id = "test_failing_portfolio"

    def get_bets(self, history: object, lottery_type: LotteryType) -> tuple[tuple[int, ...], ...]:
        rows = cast(tuple[CausalDrawRow, ...], history)
        if len(rows) >= 5:
            raise RuntimeError("synthetic adapter failure")
        return super().get_bets(history, lottery_type)


def _spec(adapter: type[_GoodPortfolio], strategy_id: str) -> StrategySpec:
    return StrategySpec(
        strategy_id=strategy_id,
        strategy_name=strategy_id,
        strategy_version="v-test",
        lottery_type=LOTTERY_TYPE,
        min_history=3,
        native_ticket_count=2,
        adapter_factory=adapter,
        adapter_source_paths=("tests/unit/test_daily539_t539_wave1_runner.py",),
        selection_reason="synthetic runner contract",
    )


def _run_specs() -> tuple[StrategySpec, ...]:
    return (
        _spec(_GoodPortfolio, _GoodPortfolio.strategy_id),
        _spec(_FailingPortfolio, _FailingPortfolio.strategy_id),
    )


def _count(db_path: Path, sql: str, parameters: tuple[object, ...] = ()) -> int:
    with sqlite3.connect(db_path) as connection:
        return int(connection.execute(sql, parameters).fetchone()[0])


def test_batch_is_resumable_idempotent_and_reconciles_native_rows(tmp_path: Path) -> None:
    draws = _draws()
    runtime_root = tmp_path / "runtime"
    specs = _run_specs()

    partial = run_batch(
        runtime_root,
        draws,
        adapter_source_commit="adapter-commit-test",
        as_of_date="2020-01-09",
        specs=specs,
        max_targets_per_strategy=2,
    )
    assert partial["status"] == "PARTIAL"
    assert (runtime_root / "t539_wave1.sqlite3").exists()
    resumed = run_batch(
        runtime_root,
        draws,
        adapter_source_commit="adapter-commit-test",
        as_of_date="2020-01-09",
        specs=specs,
    )
    assert resumed["status"] == "COMPLETE"
    assert resumed["failure_count"] == 4

    db_path = runtime_root / "t539_wave1.sqlite3"
    assert _count(db_path, "SELECT COUNT(*) FROM source_draws") == 9
    assert _count(db_path, "SELECT COUNT(*) FROM target_completion") == 12
    assert _count(db_path, "SELECT COUNT(*) FROM prediction_tickets") == 24
    assert _count(db_path, "SELECT COUNT(*) FROM prediction_scores") == 16
    assert _count(db_path, "SELECT COUNT(*) FROM failure_ledger") == 4
    assert (
        _count(
            db_path,
            "SELECT COUNT(*) FROM (SELECT run_id, strategy_id, strategy_version, target_draw_id, "
            "ticket_position FROM prediction_tickets GROUP BY run_id, strategy_id, "
            "strategy_version, target_draw_id, ticket_position HAVING COUNT(*) > 1)",
        )
        == 0
    )
    assert (
        _count(db_path, "SELECT COUNT(*) FROM prediction_tickets WHERE execution_status = 'FAILED'")
        == 8
    )
    assert (
        _count(
            db_path,
            "SELECT COUNT(*) FROM prediction_tickets WHERE execution_status = 'FAILED' "
            "AND main_numbers_json IS NULL",
        )
        == 8
    )

    with sqlite3.connect(db_path) as connection:
        causal_row = connection.execute(
            "SELECT target_draw_id, cutoff_draw_id, main_numbers_json FROM prediction_tickets "
            "WHERE strategy_id = ? AND target_draw_id = ? AND ticket_position = 1",
            (_GoodPortfolio.strategy_id, "1003"),
        ).fetchone()
    assert causal_row == ("1003", "1002", json.dumps([3, 11, 19, 27, 35], separators=(",", ":")))

    before = db_path.read_bytes()
    again = run_batch(
        runtime_root,
        draws,
        adapter_source_commit="adapter-commit-test",
        as_of_date="2020-01-09",
        specs=specs,
    )
    assert again["status"] == "COMPLETE"
    assert db_path.read_bytes() == before

    reports = json.loads((runtime_root / "run_summary.json").read_text(encoding="utf-8"))
    assert reports["run_id"] == RUN_ID
    assert reports["status"] == "COMPLETE"
    assert len(json.loads((runtime_root / "failure_ledger.json").read_text(encoding="utf-8"))) == 4


def test_runner_rejects_non_daily539_specs_and_future_draws(tmp_path: Path) -> None:
    draws = _draws()
    bad_spec = StrategySpec(
        strategy_id="bad-lottery",
        strategy_name="bad",
        strategy_version="v1",
        lottery_type=LotteryType.BIG_LOTTO.value,
        min_history=3,
        native_ticket_count=1,
        adapter_factory=_GoodPortfolio,
        adapter_source_paths=("test",),
        selection_reason="test",
    )
    with pytest.raises(ValueError, match="DAILY_539 strategies only"):
        run_batch(
            tmp_path / "wrong-lottery",
            draws,
            adapter_source_commit="test",
            as_of_date="2020-01-09",
            specs=(bad_spec,),
        )

    future_draws = (*draws[:-1], SourceDraw("9999", "2020-01-10", draws[-1].numbers))
    with pytest.raises(ValueError, match="after the authorized as-of date"):
        run_batch(
            tmp_path / "future",
            future_draws,
            adapter_source_commit="test",
            as_of_date="2020-01-09",
            specs=_run_specs(),
        )


def test_wave2_config_appends_single_ticket_and_shrinks_blocked_ledger() -> None:
    default_ids = [spec.strategy_id for spec in DEFAULT_STRATEGY_SPECS]
    wave2_ids = [spec.strategy_id for spec in WAVE2_F4COLD_SINGLE_CONFIG.specs]
    assert wave2_ids == [*default_ids, "daily539_f4cold"]

    added_spec = WAVE2_F4COLD_SINGLE_CONFIG.specs[-1]
    assert added_spec.native_ticket_count == 1
    assert added_spec.min_history == 100
    assert added_spec.strategy_version == "v0.1"
    assert added_spec.lottery_type == LOTTERY_TYPE

    old_blocked_ids = {entry["strategy_id"] for entry in BLOCKED_DAILY539_STRATEGIES}
    new_blocked_ids = {
        entry["strategy_id"] for entry in WAVE2_F4COLD_SINGLE_CONFIG.blocked_strategies
    }
    assert old_blocked_ids - new_blocked_ids == {"daily539_f4cold"}
    assert new_blocked_ids.issubset(old_blocked_ids)
    assert len(BLOCKED_DAILY539_STRATEGIES) == 7
    assert len(WAVE2_F4COLD_SINGLE_CONFIG.blocked_strategies) == 6

    assert STRATEGY_SET_CONFIGS["wave1"] is WAVE1_CONFIG
    assert STRATEGY_SET_CONFIGS["wave2-f4cold-single"] is WAVE2_F4COLD_SINGLE_CONFIG
    assert WAVE1_CONFIG.run_id == RUN_ID
    assert WAVE1_CONFIG.specs == DEFAULT_STRATEGY_SPECS
    assert WAVE1_CONFIG.blocked_strategies == BLOCKED_DAILY539_STRATEGIES
    assert WAVE2_F4COLD_SINGLE_CONFIG.run_id != WAVE1_CONFIG.run_id
    assert WAVE2_F4COLD_SINGLE_CONFIG.db_name != WAVE1_CONFIG.db_name
    assert WAVE2_F4COLD_SINGLE_CONFIG.schema_version != WAVE1_CONFIG.schema_version


def test_wave3_config_appends_acb1_alias_and_shrinks_blocked_ledger() -> None:
    wave2_ids = [spec.strategy_id for spec in WAVE2_F4COLD_SINGLE_CONFIG.specs]
    wave3_ids = [spec.strategy_id for spec in WAVE3_ACB1_ALIAS_CONFIG.specs]
    assert wave3_ids == [*wave2_ids, "acb_1bet"]
    assert len(wave2_ids) == 9
    assert len(wave3_ids) == 10

    added_spec = WAVE3_ACB1_ALIAS_CONFIG.specs[-1]
    assert added_spec.strategy_id == "acb_1bet"
    assert added_spec.native_ticket_count == 1
    assert added_spec.min_history == 100
    assert added_spec.strategy_version == "v0.1-p31a"
    assert added_spec.lottery_type == LOTTERY_TYPE

    wave2_blocked_ids = {
        entry["strategy_id"] for entry in WAVE2_F4COLD_SINGLE_CONFIG.blocked_strategies
    }
    wave3_blocked_ids = {
        entry["strategy_id"] for entry in WAVE3_ACB1_ALIAS_CONFIG.blocked_strategies
    }
    assert wave2_blocked_ids - wave3_blocked_ids == {"acb_1bet"}
    assert wave3_blocked_ids.issubset(wave2_blocked_ids)
    assert len(WAVE2_F4COLD_SINGLE_CONFIG.blocked_strategies) == 6
    assert len(WAVE3_ACB1_ALIAS_CONFIG.blocked_strategies) == 5

    assert STRATEGY_SET_CONFIGS["wave3-acb1-alias"] is WAVE3_ACB1_ALIAS_CONFIG
    assert WAVE3_ACB1_ALIAS_CONFIG.run_id != WAVE1_CONFIG.run_id
    assert WAVE3_ACB1_ALIAS_CONFIG.run_id != WAVE2_F4COLD_SINGLE_CONFIG.run_id
    assert WAVE3_ACB1_ALIAS_CONFIG.db_name != WAVE2_F4COLD_SINGLE_CONFIG.db_name
    assert WAVE3_ACB1_ALIAS_CONFIG.schema_version != WAVE2_F4COLD_SINGLE_CONFIG.schema_version

    # Wave 1 and Wave 2 configurations are untouched by the Wave 3 addition.
    assert WAVE1_CONFIG.specs == DEFAULT_STRATEGY_SPECS
    assert WAVE1_CONFIG.blocked_strategies == BLOCKED_DAILY539_STRATEGIES
    assert len(WAVE2_F4COLD_SINGLE_CONFIG.specs) == 9
    assert [spec.strategy_id for spec in WAVE2_F4COLD_SINGLE_CONFIG.specs] == [
        *[spec.strategy_id for spec in DEFAULT_STRATEGY_SPECS],
        "daily539_f4cold",
    ]


def test_wave4_config_appends_remaining5_batch_and_empties_blocked_ledger() -> None:
    wave3_ids = [spec.strategy_id for spec in WAVE3_ACB1_ALIAS_CONFIG.specs]
    wave4_ids = [spec.strategy_id for spec in WAVE4_REMAINING5_BATCH_CONFIG.specs]
    added_ids = [
        "acb_markov_midfreq",
        "zone_gap_3bet_539",
        "539_3bet_orthogonal",
        "p0b_539_3bet_f_cold_fmid",
        "p0c_539_3bet_f_cold_x2",
    ]
    assert wave4_ids == [*wave3_ids, *added_ids]
    assert len(wave3_ids) == 10
    assert len(wave4_ids) == 15

    added_specs = {spec.strategy_id: spec for spec in WAVE4_REMAINING5_BATCH_CONFIG.specs[-5:]}
    for strategy_id in added_ids:
        spec = added_specs[strategy_id]
        assert spec.native_ticket_count == 1
        assert spec.min_history == 100
        assert spec.lottery_type == LOTTERY_TYPE
    assert added_specs["acb_markov_midfreq"].strategy_version == "v0.1-p31a"
    for strategy_id in (
        "zone_gap_3bet_539",
        "539_3bet_orthogonal",
        "p0b_539_3bet_f_cold_fmid",
        "p0c_539_3bet_f_cold_x2",
    ):
        assert added_specs[strategy_id].strategy_version == "v0.1-p36"

    wave3_blocked_ids = {
        entry["strategy_id"] for entry in WAVE3_ACB1_ALIAS_CONFIG.blocked_strategies
    }
    wave4_blocked_ids = {
        entry["strategy_id"] for entry in WAVE4_REMAINING5_BATCH_CONFIG.blocked_strategies
    }
    assert wave3_blocked_ids - wave4_blocked_ids == set(added_ids)
    assert wave4_blocked_ids == set()
    assert len(WAVE3_ACB1_ALIAS_CONFIG.blocked_strategies) == 5
    assert len(WAVE4_REMAINING5_BATCH_CONFIG.blocked_strategies) == 0

    assert STRATEGY_SET_CONFIGS["wave4-remaining5-batch"] is WAVE4_REMAINING5_BATCH_CONFIG
    assert WAVE4_REMAINING5_BATCH_CONFIG.run_id != WAVE3_ACB1_ALIAS_CONFIG.run_id
    assert WAVE4_REMAINING5_BATCH_CONFIG.db_name != WAVE3_ACB1_ALIAS_CONFIG.db_name
    assert WAVE4_REMAINING5_BATCH_CONFIG.schema_version != WAVE3_ACB1_ALIAS_CONFIG.schema_version

    # Wave 1, Wave 2, and Wave 3 configurations are untouched by the Wave 4 addition.
    assert WAVE1_CONFIG.specs == DEFAULT_STRATEGY_SPECS
    assert WAVE1_CONFIG.blocked_strategies == BLOCKED_DAILY539_STRATEGIES
    assert len(WAVE2_F4COLD_SINGLE_CONFIG.specs) == 9
    assert len(WAVE3_ACB1_ALIAS_CONFIG.specs) == 10
    assert [spec.strategy_id for spec in WAVE3_ACB1_ALIAS_CONFIG.specs] == [
        *[spec.strategy_id for spec in DEFAULT_STRATEGY_SPECS],
        "daily539_f4cold",
        "acb_1bet",
    ]


def test_biglotto68_cross_lottery_config_appends_nine_target_native_specs() -> None:
    wave4_ids = [spec.strategy_id for spec in WAVE4_REMAINING5_BATCH_CONFIG.specs]
    closure_ids = [
        "t539_biglotto_cold_hunter_1bet",
        "t539_biglotto_short_window_deviation_1bet",
        "t539_biglotto_rebound_aware_1bet",
        "t539_biglotto_zone_momentum_1bet",
        "t539_biglotto_pure_cold_1bet",
        "t539_biglotto_moderate_rank_1bet",
        "t539_biglotto_gap_pressure_1bet",
        "t539_biglotto_dm_dms_2bet",
        "t539_biglotto_dms_1bet",
    ]
    closure_ids_in_config = [
        spec.strategy_id for spec in BIGLOTTO68_TO_T539_CROSS_LOTTERY_CONFIG.specs[-9:]
    ]
    assert closure_ids_in_config == closure_ids
    assert [
        spec.strategy_id for spec in BIGLOTTO68_TO_T539_CROSS_LOTTERY_CONFIG.specs[:-9]
    ] == wave4_ids
    assert len(BIGLOTTO68_TO_T539_CROSS_LOTTERY_CONFIG.specs) == 24
    assert tuple(
        spec.min_history for spec in BIGLOTTO68_TO_T539_CROSS_LOTTERY_CONFIG.specs[-9:]
    ) == (1,) * 9
    assert tuple(
        spec.native_ticket_count for spec in BIGLOTTO68_TO_T539_CROSS_LOTTERY_CONFIG.specs[-9:]
    ) == (1, 1, 1, 1, 1, 1, 1, 2, 1)
    assert BIGLOTTO68_TO_T539_CROSS_LOTTERY_CONFIG.blocked_strategies == ()
    assert (
        STRATEGY_SET_CONFIGS["biglotto68-to-t539-cross-lottery"]
        is BIGLOTTO68_TO_T539_CROSS_LOTTERY_CONFIG
    )
    assert BIGLOTTO68_TO_T539_CROSS_LOTTERY_CONFIG.run_id == (
        "BIGLOTTO68_TO_T539_CROSS_LOTTERY_CLOSURE_R1"
    )


def test_run_batch_named_configuration_uses_its_own_run_identity_and_db(
    tmp_path: Path,
) -> None:
    draws = _draws()
    runtime_root = tmp_path / "wave2-runtime"
    specs = _run_specs()
    custom_blocked = ({"strategy_id": "still_blocked", "reason_code": "X", "reason": "x"},)

    summary = run_batch(
        runtime_root,
        draws,
        adapter_source_commit="adapter-commit-wave2",
        as_of_date="2020-01-09",
        specs=specs,
        run_id="CUSTOM_RUN_ID",
        schema_version="custom-schema-v1",
        db_name="custom_wave2.sqlite3",
        blocked_strategies=custom_blocked,
    )
    assert summary["run_id"] == "CUSTOM_RUN_ID"
    assert summary["schema_version"] == "custom-schema-v1"
    assert summary["blocked_strategies"] == list(custom_blocked)

    db_path = runtime_root / "custom_wave2.sqlite3"
    assert db_path.exists()
    assert not (runtime_root / "t539_wave1.sqlite3").exists()

    with sqlite3.connect(db_path) as connection:
        run_ids = {
            row[0] for row in connection.execute("SELECT DISTINCT run_id FROM run_metadata")
        }
        assert run_ids == {"CUSTOM_RUN_ID"}
        ticket_run_ids = {
            row[0] for row in connection.execute("SELECT DISTINCT run_id FROM prediction_tickets")
        }
        assert ticket_run_ids == {"CUSTOM_RUN_ID"}
        failure_run_ids = {
            row[0] for row in connection.execute("SELECT DISTINCT run_id FROM failure_ledger")
        }
        assert failure_run_ids == {"CUSTOM_RUN_ID"}
        provenance_run_ids = {
            json.loads(row[0])["run_id"]
            for row in connection.execute("SELECT DISTINCT provenance_json FROM prediction_tickets")
        }
        assert provenance_run_ids == {"CUSTOM_RUN_ID"}


def _external_cache_payload(
    draws: tuple[SourceDraw, ...], as_of_date: str, *, source_sha256: str | None = None
) -> dict[str, object]:
    resolved_sha256 = (
        source_sha256 if source_sha256 is not None else source_payload_sha256(draws)
    )
    return {
        "schema_version": "t539-wave1-v1",
        "source_endpoint": runner_module.OFFICIAL_SOURCE_ENDPOINT,
        "as_of_date": as_of_date,
        "lottery_type": LOTTERY_TYPE,
        "source_sha256": resolved_sha256,
        "draws": [
            {
                "draw_id": draw.draw_id,
                "draw_date": draw.draw_date,
                "main_numbers": list(draw.numbers),
            }
            for draw in draws
        ],
    }


def test_load_external_source_cache_reads_sealed_cache_without_network_or_local_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    draws = _draws(5)
    cache_path = tmp_path / "external_source.json"
    cache_path.write_text(
        json.dumps(_external_cache_payload(draws, "2020-01-05")), encoding="utf-8"
    )

    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("load_external_source_cache attempted a subprocess call")

    monkeypatch.setattr(subprocess, "run", forbidden)

    loaded = load_external_source_cache(cache_path, "2020-01-05")
    assert loaded == draws
    assert list(tmp_path.iterdir()) == [cache_path]


def test_load_external_source_cache_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="external source cache not found"):
        load_external_source_cache(tmp_path / "absent.json", "2020-01-05")


def test_load_external_source_cache_digest_mismatch_raises(tmp_path: Path) -> None:
    draws = _draws(5)
    cache_path = tmp_path / "external_source.json"
    cache_path.write_text(
        json.dumps(_external_cache_payload(draws, "2020-01-05", source_sha256="0" * 64)),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="digest mismatch"):
        load_external_source_cache(cache_path, "2020-01-05")


def test_parse_args_default_invocation_preserves_wave1_strategy_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "argv", ["run_daily539_t539_wave1.py"])
    args = runner_module._parse_args()
    assert args.strategy_set == WAVE1_CONFIG.name
    assert args.runtime_root is None
    assert args.source_cache is None
    assert args.as_of_date == runner_module.DEFAULT_AS_OF_DATE


def test_parse_args_accepts_wave2_strategy_set_and_source_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_path = tmp_path / "cache.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_daily539_t539_wave1.py",
            "--strategy-set",
            "wave2-f4cold-single",
            "--source-cache",
            str(cache_path),
        ],
    )
    args = runner_module._parse_args()
    assert args.strategy_set == WAVE2_F4COLD_SINGLE_CONFIG.name
    assert args.source_cache == cache_path
