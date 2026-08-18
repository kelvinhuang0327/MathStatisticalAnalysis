"""Focused acceptance tests for the read-only B649 operator CLI."""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime, timedelta
from gzip import open as gzip_open
from pathlib import Path

import pytest
from typer.testing import CliRunner

import lottolab.interfaces.cli.historical_replay_biglotto as replay_cli
from lottolab.application.draw_data import DrawHistoryPage, DrawHistoryQuery, DrawRecord
from lottolab.domain.biglotto_full_strategy_catalog import (
    ReproductionStatus,
    load_full_strategy_catalog,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayDraw, ReplaySourceSnapshot
from lottolab.infrastructure.persistence.draw_schema import LocalDataPaths
from lottolab.interfaces.cli.main import app
from lottolab.strategies.catalog import production_catalog

RAW_ONLY_ID = "legacy_biglotto__backtest_cluster_pivot_biglotto__b28957a6433e"
KEEP_UNRESOLVED_ID = (
    "legacy_biglotto__big649_no_db_strategy_output_adapter__6da3a06f4377"
)
RAW_HISTORY_NOT_FOUND_IDS = frozenset(
    {
        "legacy_biglotto__backtest_biglotto_5bet_ts3markov__25760472baa0",
        "legacy_biglotto__predict_biglotto_triple_strike__236fe529c01f",
    }
)

runner = CliRunner()


def _draw(number: int, *, main_numbers: tuple[int, ...], special: int) -> ReplayDraw:
    return ReplayDraw(
        lottery_type=LotteryType.BIG_LOTTO,
        draw_number=str(number),
        draw_date=date(2026, 1, 1) + timedelta(days=number - 100000001),
        main_numbers=main_numbers,
        special_number=special,
    )


def _source_root(tmp_path: Path) -> Path:
    root = tmp_path / "b649-foundation"
    (root / "raw_records").mkdir(parents=True)
    return root


def _write_identity_file_stems(root: Path) -> None:
    full_catalog = load_full_strategy_catalog()
    current_ids = {
        descriptor.strategy_id
        for descriptor in production_catalog().list(lottery_type=LotteryType.BIG_LOTTO)
        if f"full_strategy_catalog_id:{descriptor.strategy_id}" in descriptor.provenance
    }
    for record in full_catalog.records:
        if (
            record.reproduction_status is ReproductionStatus.BACKTESTED
            and record.strategy_id not in current_ids
            and record.strategy_id not in RAW_HISTORY_NOT_FOUND_IDS
        ):
            (root / "raw_records" / f"{record.strategy_id}.jsonl.gz").touch()


def _write_raw_portfolio(root: Path, *, ticket_count: int = 25) -> None:
    record = next(
        record
        for record in load_full_strategy_catalog().records
        if record.strategy_id == RAW_ONLY_ID
    )
    history = _draw(100000001, main_numbers=(7, 8, 9, 10, 11, 12), special=13)
    target = _draw(100000002, main_numbers=(1, 2, 3, 4, 5, 6), special=7)
    path = root / "raw_records" / f"{RAW_ONLY_ID}.jsonl.gz"
    with gzip_open(path, "wt", encoding="utf-8") as handle:
        for position in range(1, ticket_count + 1):
            handle.write(
                json.dumps(
                    {
                        "actual_main_numbers": list(target.main_numbers),
                        "actual_special_number": target.special_number,
                        "canonical_strategy_id": RAW_ONLY_ID,
                        "historical_input_cutoff_date": history.draw_date.isoformat(),
                        "historical_input_cutoff_draw": history.draw_number,
                        "lottery_type": LotteryType.BIG_LOTTO.value,
                        "native_ticket_count": ticket_count,
                        "predicted_numbers": list(target.main_numbers),
                        "replay_status": "EXACT_PRESERVED_OUTPUT_RECOVERED",
                        "strategy_version": record.strategy_version,
                        "target_draw_date": target.draw_date.isoformat(),
                        "target_draw_number": target.draw_number,
                        "ticket_position": position,
                    },
                    separators=(",", ":"),
                )
                + "\n"
            )


def _patch_source(monkeypatch: pytest.MonkeyPatch, *draws: ReplayDraw) -> None:
    source = ReplaySourceSnapshot(
        lottery_type=LotteryType.BIG_LOTTO,
        historical_draws=tuple(draws),
    )
    monkeypatch.setattr(replay_cli, "build_b649_replay_source_snapshot", lambda: source)


def _invoke(root: Path, *extra: str):
    return runner.invoke(
        app,
        [
            "historical-replay-biglotto",
            "--raw-history-root",
            str(root),
            *extra,
        ],
    )


def test_command_is_registered_and_defaults_to_bounded_summary() -> None:
    result = runner.invoke(app, ["historical-replay-biglotto", "--help"])

    assert result.exit_code == 0
    help_text = re.sub(r"\s+", "", re.sub(r"\x1b\[[0-9;]*m", "", result.stdout))
    assert "--raw-history-root" in help_text
    assert "--strategy-id" in help_text
    assert "--cutoff-draw-number" in help_text
    assert "--output-mode" in help_text


def test_all_identity_summary_uses_live_accounting_and_does_not_iterate_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _source_root(tmp_path)
    _write_identity_file_stems(root)
    _patch_source(monkeypatch, _draw(100000001, main_numbers=(1, 2, 3, 4, 5, 6), special=7))

    def fail_if_records_are_requested(_result: object):
        raise AssertionError("SUMMARY must not iterate replay records")

    monkeypatch.setattr(replay_cli, "iter_b649_record_payloads", fail_if_records_are_requested)
    result = _invoke(root)

    assert result.exit_code == 0, result.stderr
    assert result.stderr == ""
    summary = json.loads(result.stdout)
    assert summary == {
        "currently_replayable_identity_count": 52,
        "historical_raw_only_identity_count": 81,
        "keep_unresolved_alias_count": 3,
        "lottery_type": "BIG_LOTTO",
        "mode": "FULL_REPLAY",
        "resolved_alias_count": 9,
        "selected_strategy_count": 221,
        "terminal_unavailable_identity_count": 76,
        "total_identity_count": 221,
    }


def test_single_strategy_summary_and_cutoff_are_explicitly_selected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _source_root(tmp_path)
    _patch_source(
        monkeypatch,
        _draw(100000001, main_numbers=(1, 2, 3, 4, 5, 6), special=7),
        _draw(100000002, main_numbers=(2, 3, 4, 5, 6, 7), special=8),
    )

    result = _invoke(
        root,
        "--strategy-id",
        RAW_ONLY_ID,
        "--cutoff-draw-number",
        "100000002",
    )

    assert result.exit_code == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["selected_strategy_count"] == 1
    assert summary["total_identity_count"] == 221


def test_records_jsonl_preserves_all_native_positions_and_prize_evaluation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _source_root(tmp_path)
    _write_raw_portfolio(root)
    history = _draw(100000001, main_numbers=(7, 8, 9, 10, 11, 12), special=13)
    target = _draw(100000002, main_numbers=(1, 2, 3, 4, 5, 6), special=7)
    future = _draw(100000003, main_numbers=(2, 3, 4, 5, 6, 7), special=8)
    _patch_source(monkeypatch, history, target, future)

    result = _invoke(
        root,
        "--strategy-id",
        RAW_ONLY_ID,
        "--cutoff-draw-number",
        target.draw_number,
        "--output-mode",
        "records-jsonl",
    )

    assert result.exit_code == 0, result.stderr
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    ticket_rows = [row for row in rows if row["ticket_position"] is not None]
    assert len(rows) == 26
    assert tuple(row["ticket_position"] for row in ticket_rows) == tuple(range(1, 26))
    assert all(row["native_ticket_count"] == 25 for row in ticket_rows)
    assert all(row["replay_status"] == "COMPLETE" for row in ticket_rows)
    assert all(row["actual_main_numbers"] == [1, 2, 3, 4, 5, 6] for row in ticket_rows)
    assert all(row["predicted_main_numbers"] == [1, 2, 3, 4, 5, 6] for row in ticket_rows)
    assert ticket_rows[0]["main_hit_count"] == 6
    assert ticket_rows[0]["special_hit"] is False
    assert ticket_rows[0]["is_winner"] is True
    assert ticket_rows[0]["prize_tier"] == "FIRST"
    assert {row["target_draw_number"] for row in rows} == {
        history.draw_number,
        target.draw_number,
    }


def test_unavailable_and_keep_unresolved_identities_emit_status_without_tickets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _source_root(tmp_path)
    _patch_source(monkeypatch)
    use_case = replay_cli.B649HistoricalReplayUseCase(root)
    terminal_id = next(
        identity.strategy_id
        for identity in use_case.identity_accounts
        if identity.status is replay_cli.B649IdentityStatus.TERMINAL_UNAVAILABLE
    )

    for strategy_id, identity_status in (
        (KEEP_UNRESOLVED_ID, "KEEP_UNRESOLVED_ALIAS"),
        (terminal_id, "TERMINAL_UNAVAILABLE"),
    ):
        result = _invoke(root, "--strategy-id", strategy_id, "--output-mode", "RECORDS_JSONL")

        assert result.exit_code == 0, result.stderr
        rows = [json.loads(line) for line in result.stdout.splitlines()]
        assert len(rows) == 1
        assert rows[0]["identity_status"] == identity_status
        assert rows[0]["replay_status"] == "IDENTITY_UNAVAILABLE"
        assert rows[0]["ticket_position"] is None
        assert rows[0]["predicted_main_numbers"] is None
        assert rows[0]["target_draw_number"] is None


def test_source_composition_is_sorted_and_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)

    def record(number: str, day: date) -> DrawRecord:
        return DrawRecord(
            internal_id=int(number),
            lottery_type=LotteryType.BIG_LOTTO,
            draw_number=number,
            draw_date=day,
            main_numbers=(1, 2, 3, 4, 5, 6),
            special_numbers=(7,),
            normalized_record_hash="a" * 64,
            source_name="fixture",
            source_reference=None,
            ingestion_run_id="run",
            created_at=now,
            updated_at=now,
        )

    newer = record("100000002", date(2026, 1, 2))
    older = record("100000001", date(2026, 1, 1))

    class FakeRepository:
        def __init__(self, _paths: LocalDataPaths) -> None:
            pass

        def list_draws(self, query: DrawHistoryQuery) -> DrawHistoryPage:
            assert query.lottery_type is LotteryType.BIG_LOTTO
            return DrawHistoryPage(
                records=(newer, older),
                page=1,
                page_size=1_000,
                total_count=2,
                total_pages=1,
            )

    def read_only(_paths: LocalDataPaths) -> bool:
        return True

    monkeypatch.setattr(replay_cli, "verify_schema_read_only", read_only)
    monkeypatch.setattr(replay_cli, "SQLiteDrawDataRepository", FakeRepository)
    paths = LocalDataPaths(data_directory=tmp_path, database=tmp_path / "lottolab.db")

    snapshot = replay_cli.build_b649_replay_source_snapshot(paths=paths)

    assert tuple(draw.draw_number for draw in snapshot.historical_draws) == (
        "100000001",
        "100000002",
    )
    assert snapshot.official_draws == ()
