"""Fixed, historical, full-portfolio comparisons independent of replay implementation."""

from __future__ import annotations

import csv
import hashlib
import json
import random
from dataclasses import replace
from datetime import date
from functools import cache
from importlib import import_module
from pathlib import Path
from unittest.mock import Mock

import pytest

from lottolab.application import legacy_source_native_portfolios_wave27 as wave27
from lottolab.application.biglotto_versioned_replay_bindings import VERSIONED_REPLAY_SOURCES
from lottolab.application.legacy_history_native_portfolios import LegacyHistoryDraw
from lottolab.application.use_cases.replay_backfill import (
    BackfillSelection,
    BackfillStore,
    ReplayBackfill,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayDraw
from lottolab.interfaces.cli import replay_backfill as cli
from lottolab.strategies.adapters.base import InsufficientHistory

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/replay"
WAVES = {
    "edge_splicer": 47,
    "edge_splicer_5bet": 47,
    "edge_splicer_v2": 47,
    "evaluate_concentrator": 47,
    "generate_2_3_bets": 47,
    "standard_ts3_5bet": 47,
    "backtest_biglotto_enhancements": 48,
    "evaluate_combinations": 49,
    "exhaustive_feature_sweep_v2": 50,
    "optimize_biglotto_cluster": 51,
    "optimize_deviation_extreme_generic": 51,
    "feature_discovery_and_retrospective": 52,
    "historical_audit_rigorous": 52,
    "predict_consensus_ensemble": 54,
}
BIG = LotteryType.BIG_LOTTO


@cache
def _ledger(wave: int):
    module = import_module(f"lottolab.application.legacy_source_grid_native_portfolios_wave{wave}")
    raw = (ROOT / "src/lottolab/strategies/data" / module.LEDGER_RESOURCE_NAME).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == module.LEDGER_FILE_SHA256
    return json.loads(raw)


@cache
def _extension():
    raw = (FIXTURES / "biglotto_feature_discovery_extension.json").read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == "0fd3c53ce5f6a6d79fa223ac37be7e86ea45fa6c7fef5fc946ce2392272bc35c"
    )
    return json.loads(raw)


@cache
def _draws():
    raw = json.loads(
        (ROOT / "data/fixtures/replay/biglotto-candidate-history-r1.json").read_bytes()
    )
    rows = {
        r["draw"]: ReplayDraw(
            BIG,
            r["draw"],
            date.fromisoformat(r["date"].replace("/", "-")),
            tuple(r["numbers"]),
            r["special"],
        )
        for r in raw
    }
    # Remaining public observations were read from the draw snapshot identified
    # in the extension fixture. The original ledger commits to every historical prefix.
    with (FIXTURES / "biglotto_frozen_grid_history.csv").open() as stream:
        for row in csv.DictReader(stream):
            number = row["draw"]
            assert number not in rows
            rows[number] = ReplayDraw(
                BIG,
                number,
                date.fromisoformat(row["date"]),
                tuple(int(row[f"n{i}"]) for i in range(1, 7)),
                int(row["special"]),
            )
    ids = [
        raw[0]["draw"],
        *_ledger(47)["target_draw_numbers"],
        *(r["target"] for r in _extension()["extended_targets"]),
    ]
    return tuple(rows[k] for k in ids)


def _source(name):
    return next(s for s in VERSIONED_REPLAY_SOURCES if Path(s.source_path).stem == name)


@cache
def _wave27_cases():
    raw = (FIXTURES / "biglotto_wave27_parity.json").read_bytes()
    evidence = json.loads(
        (
            ROOT
            / "src/lottolab/strategies/data/biglotto_legacy_source_native_wave27_evidence_v1.json"
        ).read_bytes()
    )
    assert hashlib.sha256(raw).hexdigest() == evidence["parity"]["parity_sha256"]
    parity = json.loads(raw)
    ledger = _ledger(47)
    assert parity["database_sha256"] == ledger["dataset_sha256"]
    cases = parity["cases"]
    assert len(cases) == parity["case_count"] == 292
    draws = _draws()
    for cutoff in {case["history_draw_count"] for case in cases}:
        history = [draw.main_numbers for draw in draws[:cutoff]]
        digest = hashlib.sha256(json.dumps(history, separators=(",", ":")).encode()).hexdigest()
        assert digest == ledger["context_numbers_sha256_by_target"][cutoff - 1]
    return cases


def test_frozen_two_bet_optimizer() -> None:
    _assert_wave27_optimizer_parity("biglotto_2bet_optimizer")


def test_frozen_two_bet_optimizer_v2() -> None:
    _assert_wave27_optimizer_parity("biglotto_2bet_optimizer_v2")


def _assert_wave27_optimizer_parity(name: str) -> None:
    source = _source(name)
    bindings, accounts = cli._exact_strategy_inventory(
        BIG, source.strategy_id, source.strategy_version
    )
    assert accounts[source.strategy_id]["source"] == source.locator
    strategy = bindings[0].strategy
    adapter = cli.build_adapter(BIG, bindings)
    draws = _draws()
    assert strategy.native_ticket_count == 2 and strategy.min_history == 1
    with pytest.raises(InsufficientHistory):
        adapter.generate(strategy, (), draws[0])

    cases = [case for case in _wave27_cases() if case["legacy_method_id"] == source.source_path]
    assert len(cases) == 73
    for case in cases:
        cutoff = case["history_draw_count"]
        assert case["status"] == "PASS" and case["native_ticket_count"] == 2
        tickets = adapter.generate(strategy, draws[:cutoff], draws[cutoff])
        assert [ticket.ticket_position for ticket in tickets] == [1, 2]
        assert [list(ticket.main_numbers) for ticket in tickets] == case["tickets"], cutoff
    target = replace(draws[1], main_numbers=(1, 2, 3, 4, 5, 6), special_number=49)
    assert adapter.generate(strategy, draws[:1], target) == adapter.generate(
        strategy, draws[:1], draws[1]
    )


@pytest.mark.parametrize(
    "method",
    (
        wave27.GEMINI_2BET_METHOD_ID,
        wave27.GEMINI_3BET_METHOD_ID,
    ),
)
def test_wave27_control_cases(method: str) -> None:
    cases = [case for case in _wave27_cases() if case["legacy_method_id"] == method]
    assert len(cases) == 73
    rows = tuple(LegacyHistoryDraw(draw.draw_number, draw.main_numbers) for draw in _draws())
    for case in cases:
        cutoff = case["history_draw_count"]
        request = wave27.LegacySourceNativeWave27Request(
            method, rows[cutoff].draw_number, rows[:cutoff]
        )
        if case["status"] == "CLOSED_PARITY":
            with pytest.raises(wave27.LegacySourceNativeWave27SourceError) as exc:
                wave27.generate_legacy_source_native_wave27_portfolio(request)
            assert exc.value.reason_code == case["reason_code"]
        else:
            result = wave27.generate_legacy_source_native_wave27_portfolio(request)
            assert [list(ticket) for ticket in result.tickets] == case["tickets"], cutoff


@pytest.mark.parametrize(
    ("name", "version", "production_adapter"),
    (
        (
            "biglotto_2bet_optimizer",
            "legacy-source-49a25effa62f-898ac9e38876",
            "BigLottoTwoBetOptimizerAdapter",
        ),
        (
            "biglotto_2bet_optimizer_v2",
            "legacy-source-49a25effa62f-783226366ac3",
            "BigLottoTwoBetOptimizerV2Adapter",
        ),
    ),
)
def test_two_bet_optimizer_versions_remain_separately_addressable(
    name: str, version: str, production_adapter: str
) -> None:
    source = _source(name)
    frozen, _ = cli._exact_strategy_inventory(BIG, source.strategy_id, source.strategy_version)
    current, accounts = cli._exact_strategy_inventory(BIG, source.strategy_id, "v0.1")
    live = current[0].strategy
    assert live.strategy_id == frozen[0].strategy.strategy_id
    assert live.strategy_version == "v0.1"
    assert frozen[0].strategy.strategy_version == version
    assert live.fingerprint != frozen[0].strategy.fingerprint
    assert accounts[source.strategy_id]["source"] == (
        f"lottolab.strategies.adapters.biglotto_wave3:{production_adapter}"
    )
    with pytest.raises(ValueError, match="identity is not pinned"):
        cli.build_adapter(BIG, frozen).generate(live, (), _draws()[0])


def _oracle(source, cutoff):
    ledger = _ledger(WAVES[Path(source.source_path).stem])
    assert ledger["source_sha256_by_method"][source.source_path] == source.source_sha256
    assert ledger["frozen_source_commit"] == source.source_commit
    if cutoff <= len(ledger["target_draw_numbers"]):
        idx = cutoff - 1
        return (
            ledger["target_draw_numbers"][idx],
            ledger["context_numbers_sha256_by_target"][idx],
            ledger["tickets_by_method"][source.source_path][idx],
        )
    extension = _extension()
    assert extension["source_path"] == source.source_path
    assert extension["source_commit"] == source.source_commit
    assert extension["source_sha256"] == source.source_sha256
    row = extension["extended_targets"][cutoff - 1 - len(ledger["target_draw_numbers"])]
    return row["target"], row["context_sha256"], row["tickets"]


@pytest.mark.parametrize("name", WAVES)
def test_ordered_portfolio(name: str) -> None:
    source = _source(name)
    bindings, _ = cli._exact_strategy_inventory(BIG, source.strategy_id, source.strategy_version)
    adapter = cli.build_adapter(BIG, bindings)
    strategy = bindings[0].strategy
    minimum = _ledger(WAVES[name])["minimum_history_by_method"][source.source_path]
    assert strategy.min_history == minimum
    draws = _draws()
    with pytest.raises(InsufficientHistory):
        adapter.generate(strategy, draws[: minimum - 1], draws[minimum - 1])
    # Use the common signal-grid window for seven related sources so that a
    # tie/order error can be located against the same historical draws.
    first = 649 if WAVES[name] in (47, 48, 49) else minimum
    # Short histories have tied spectral magnitudes that change the snake draft.
    early = range(1, 57) if name == "generate_2_3_bets" else ()
    for cutoff in dict.fromkeys((minimum, *early, *range(first, first + 30))):
        history, target = draws[:cutoff], draws[cutoff]
        expected_id, context_sha, expected = _oracle(source, cutoff)
        assert target.draw_number == expected_id and history[-1].draw_date < target.draw_date
        assert (
            hashlib.sha256(
                json.dumps([d.main_numbers for d in history], separators=(",", ":")).encode()
            ).hexdigest()
            == context_sha
        )
        tickets = adapter.generate(strategy, history, target)
        assert [t.ticket_position for t in tickets] == list(range(1, len(expected) + 1))
        assert [list(t.main_numbers) for t in tickets] == expected
        poisoned = replace(target, main_numbers=(1, 2, 3, 4, 5, 6), special_number=49)
        assert adapter.generate(strategy, history, poisoned) == tickets


@pytest.mark.parametrize("name", WAVES)
def test_backfill_exact_version(name: str, capsys) -> None:
    source = _source(name)
    args = [
        "--lottery-type",
        "BIG_LOTTO",
        "--inventory",
        "--strategy-id",
        source.strategy_id,
        "--strategy-version",
    ]
    assert cli.main([*args, source.strategy_version]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["executable_strategy_count"] == 1
    assert result["strategies"][source.strategy_id]["source"] == source.locator
    assert cli.main([*args, "wrong-frozen-version"]) == 1
    assert "no executable binding" in capsys.readouterr().err

    bindings, sources = cli._exact_strategy_inventory(
        BIG, source.strategy_id, source.strategy_version
    )
    strategy = bindings[0].strategy
    with pytest.raises(ValueError, match="no executable binding"):
        cli._exact_strategy_inventory(BIG, source.strategy_id, "wrong-frozen-version")
    store = Mock(spec=BackfillStore)
    store.lookup_complete_by_logical_keys.return_value = {}
    store.lookup_many_by_unique_keys.return_value = {}
    store.summary.return_value = {}
    worker = ReplayBackfill(
        adapter=cli.build_adapter(BIG, bindings),
        strategies=(strategy,),
        draws=_draws()[: strategy.min_history + 1],
        source_identity="fixed-historical-fixture",
        store=store,
        execution_version="source-grid-test",
        strategy_sources=sources,
    )
    result = worker.execute(BackfillSelection(latest=1))
    assert result["newly_calculated_count"] == 1
    [cell] = store.save_many.call_args.args[1]
    expected_id, _, expected = _oracle(source, strategy.min_history)
    assert cell["strategy_version"] == source.strategy_version
    assert cell["target_draw_id"] == expected_id
    assert cell["history_count"] == strategy.min_history
    assert cell["execution_status"] == "COMPLETE"
    assert [t["main_numbers"] for t in cell["predicted_tickets"]] == expected


def test_sweep_preserves_short_zonal_output_off_ledger() -> None:
    rng = random.Random(26)
    source = _source("exhaustive_feature_sweep_v2")
    bindings, _ = cli._exact_strategy_inventory(BIG, source.strategy_id, source.strategy_version)
    adapter, strategy = cli.build_adapter(BIG, bindings), bindings[0].strategy
    history = list(_draws()[: strategy.min_history])
    for i in range(len(history) - 200, len(history)):
        zones = rng.sample(range(7), rng.choice([2, 3, 4]))
        ticket = tuple(sorted(rng.sample([7 * z + n for z in zones for n in range(1, 8)], 6)))
        special = next(n for n in range(1, 50) if n not in ticket)
        history[i] = replace(history[i], main_numbers=ticket, special_number=special)
    target = _draws()[strategy.min_history]
    assert adapter.expected_native_ticket_count(strategy, tuple(history), target) == 11
    tickets = adapter.generate(strategy, tuple(history), target)
    assert len(tickets) == 11
    assert tickets[6].main_numbers == (8, 9, 11, 12, 13, 32)
