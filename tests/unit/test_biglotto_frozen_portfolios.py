"""Compare executable replay against independently generated frozen-source ticket ledgers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import date
from functools import cache
from pathlib import Path

import pytest

from lottolab.application import legacy_fft_native_portfolios_wave45 as wave45
from lottolab.application import legacy_source_grid_native_portfolios_wave46 as wave46
from lottolab.application import legacy_source_grid_native_portfolios_wave47 as wave47
from lottolab.application import legacy_source_grid_native_portfolios_wave48 as wave48
from lottolab.application import legacy_source_grid_native_portfolios_wave53 as wave53
from lottolab.application.biglotto_versioned_replay_bindings import (
    VERSIONED_REPLAY_SOURCES,
    VersionedReplaySource,
    versioned_biglotto_replay_bindings,
)
from lottolab.application.historical_replay_adapters import BigLottoReplayAdapter
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayDraw
from lottolab.strategies.adapters.base import InsufficientHistory

ROOT = Path(__file__).resolve().parents[2]
SOURCES = tuple(
    s for s in VERSIONED_REPLAY_SOURCES if ".biglotto_frozen_portfolios:" in s.adapter_path
)
LEDGERS = (wave45, wave46, wave47, wave48, wave53)


@cache
def _ledgers():
    result = []
    for module in LEDGERS:
        raw = (ROOT / "src/lottolab/strategies/data" / module.LEDGER_RESOURCE_NAME).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == module.LEDGER_FILE_SHA256
        result.append(json.loads(raw))
    return result


@cache
def _draws() -> tuple[ReplayDraw, ...]:
    local = json.loads(
        (ROOT / "data/fixtures/replay/biglotto-candidate-history-r1.json").read_bytes()
    )
    by_id = {row["draw"]: row for row in local}
    # The fixed source snapshot omits some rows present in the newer public draw fixture.
    ids = [local[0]["draw"], *_ledgers()[1]["target_draw_numbers"][:531]]
    return tuple(
        ReplayDraw(
            LotteryType.BIG_LOTTO,
            draw_id,
            date.fromisoformat(row["date"].replace("/", "-")),
            tuple(row["numbers"]),
            row["special"],
        )
        for draw_id in ids
        if (row := by_id[draw_id])
    )


@pytest.mark.parametrize("source", SOURCES, ids=lambda s: Path(s.source_path).stem)
def test_ordered_historical_parity(source: VersionedReplaySource) -> None:
    binding = next(
        b
        for b in versioned_biglotto_replay_bindings()
        if b.strategy.strategy_id == source.strategy_id
    )
    replay = BigLottoReplayAdapter((binding,))
    ledger = next(v for v in _ledgers() if source.source_path in v["tickets_by_method"])
    assert ledger["source_sha256_by_method"][source.source_path] == source.source_sha256
    assert ledger["frozen_source_commit"] == source.source_commit
    minimum = ledger["minimum_history_by_method"][source.source_path]
    assert binding.strategy.min_history == minimum
    draws = _draws()
    with pytest.raises(InsufficientHistory):
        replay.generate(binding.strategy, draws[: minimum - 1], draws[minimum - 1])
    for cutoff in dict.fromkeys((minimum, *range(501, 531))):
        history, target = draws[:cutoff], draws[cutoff]
        assert all(
            r.draw_number != target.draw_number and r.draw_date < target.draw_date for r in history
        )
        row_index = ledger["target_draw_numbers"].index(target.draw_number)
        context = (
            history[-ledger["context_draw_count"] :] if "context_draw_count" in ledger else history
        )
        digest = hashlib.sha256(
            json.dumps([r.main_numbers for r in context], separators=(",", ":")).encode()
        ).hexdigest()
        assert digest == ledger["context_numbers_sha256_by_target"][row_index]
        tickets = replay.generate(binding.strategy, history, target)
        expected = ledger["tickets_by_method"][source.source_path][row_index]
        assert [t.ticket_position for t in tickets] == list(
            range(1, binding.strategy.native_ticket_count + 1)
        )
        assert [list(t.main_numbers) for t in tickets] == expected
        poisoned_target = replace(target, main_numbers=(1, 2, 3, 4, 5, 6), special_number=49)
        assert replay.generate(binding.strategy, history, poisoned_target) == tickets


def test_canonical_replay_runs_exact_version_at_its_minimum(tmp_path: Path) -> None:
    from lottolab.application.use_cases.b649_historical_replay import (
        B649HistoricalReplayRequest,
        B649HistoricalReplayUseCase,
    )
    from lottolab.domain.historical_replay import (
        HistoricalReplayMode,
        ReplayCellStatus,
        ReplaySourceSnapshot,
    )

    (tmp_path / "raw_records").mkdir()
    use_case = B649HistoricalReplayUseCase(tmp_path)
    source = next(s for s in SOURCES if s.source_path == "tools/quick_predict.py")
    draws = _draws()[:51]
    result = use_case.execute(
        B649HistoricalReplayRequest(
            source=ReplaySourceSnapshot(lottery_type=LotteryType.BIG_LOTTO, historical_draws=draws),
            mode=HistoricalReplayMode.FULL_REPLAY,
            strategy_id=source.strategy_id,
        )
    )
    record = next(result.iter_strategy_results())
    assert record.identity.reason == "EXACT_FROZEN_REPLAY_ADAPTER"
    assert record.blocked_reason is None
    assert record.replay is not None
    final = record.replay.records[-1]
    assert final.status is ReplayCellStatus.COMPLETE
    assert final.strategy.strategy_version == source.strategy_version
    assert final.causal_history == draws[:-1]
    assert len(final.tickets) == 5


@pytest.mark.parametrize("source", SOURCES, ids=lambda s: Path(s.source_path).stem)
def test_backfill_cli_selects_exact_version(source: VersionedReplaySource, capsys) -> None:
    from lottolab.interfaces.cli.replay_backfill import main

    args = [
        "--lottery-type",
        "BIG_LOTTO",
        "--inventory",
        "--strategy-id",
        source.strategy_id,
        "--strategy-version",
    ]
    assert main([*args, source.strategy_version]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["executable_strategy_count"] == 1
    assert set(result["strategies"]) == {source.strategy_id}
    account = result["strategies"][source.strategy_id]
    assert account["strategy_version"] == source.strategy_version
    assert account["source"] == source.locator
    assert account["source_sha256"] == source.source_sha256
    assert main([*args, "no-such-version"]) == 1
