from __future__ import annotations

import hashlib
import json
import random
from importlib.resources import files
from unittest.mock import Mock, call

import pytest
from tests.unit.test_biglotto_frozen_grid import _draws

from lottolab.application import biglotto_frozen_enhanced_dual_bet as dual
from lottolab.application.biglotto_versioned_replay_bindings import VERSIONED_REPLAY_SOURCES
from lottolab.application.use_cases.replay_backfill import (
    BackfillSelection,
    BackfillStore,
    ReplayBackfill,
)
from lottolab.domain.draws import LotteryType
from lottolab.interfaces.cli import replay_backfill as cli
from lottolab.strategies.adapters.base import CausalDrawRow, InsufficientHistory

BIG = LotteryType.BIG_LOTTO
STRATEGY_ID = "legacy_biglotto__enhanced_dual_bet_predictor__d5b3de348d01"
VERSION = "legacy-source-49a25effa62f-d5b3de348d01"
CLOSED = "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"


def _canonical(value: object) -> bytes:
    return json.dumps(json.loads(json.dumps(value)), separators=(",", ":")).encode()


def test_ordered_portfolios() -> None:
    data = files("lottolab.strategies.data")
    evidence_bytes = data.joinpath(
        "biglotto_legacy_dual_seeded_wave58_evidence_v1.json"
    ).read_bytes()
    assert hashlib.sha256(evidence_bytes).hexdigest() == (
        "7db702bf9754c1a2d037130b9a11ce7b52e14121097e048d6c09cf505832ad35"
    )
    evidence = json.loads(evidence_bytes)
    ledger_bytes = data.joinpath("biglotto_dual_seeded_wave58_ticket_ledger_v1.json").read_bytes()
    assert (
        hashlib.sha256(ledger_bytes).hexdigest()
        == evidence["ledger_file_sha256"]
        == "3070f69175c806674547111c54b8109d94ec57c8b34a78b1082f4e34adbabe01"
    )
    ledger = json.loads(ledger_bytes)
    source = next(
        s
        for s in VERSIONED_REPLAY_SOURCES
        if (s.strategy_id, s.strategy_version) == (STRATEGY_ID, VERSION)
    )
    method = "lottery_api/models/enhanced_dual_bet_predictor.py"
    assert source.source_path == method
    assert (
        source.source_commit
        == ledger["frozen_source_commit"]
        == "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
    )
    assert source.source_blob_id == "7164233fff5a8206e9084277435ecab0888b6e81"
    assert (
        source.source_sha256
        == ledger["source_sha256_by_method"][method]
        == "d5b3de348d01164c2e0079ec207c1a590c44b935217f81dfc9d704a825e50957"
    )
    record = next(r for r in evidence["strategies"] if r["legacy_method_id"] == method)
    bindings, sources = cli._exact_strategy_inventory(BIG, STRATEGY_ID, VERSION)
    assert sources[STRATEGY_ID]["source"] == source.locator
    strategy = bindings[0].strategy
    adapter = cli.build_adapter(BIG, bindings)
    assert (strategy.min_history, strategy.native_ticket_count) == (100, 2)
    draws = _draws()[:2149]
    assert len(draws) == evidence["target_draw_count"] == 2149
    assert [draw.draw_number for draw in draws] == ledger["target_draw_numbers"]
    assert draws[100].draw_number == "96000103"

    prefix = hashlib.sha256(b"[")
    actual = []
    closed = 0
    duplicates = []
    for i, (target, digest, reason, expected) in enumerate(
        zip(
            draws,
            ledger["context_numbers_sha256_by_target"],
            ledger["closed_reason_by_method"][method],
            ledger["tickets_by_method"][method],
            strict=True,
        )
    ):
        context = prefix.copy()
        context.update(b"]")
        assert context.hexdigest() == digest, target.draw_number
        if i < strategy.min_history:
            assert reason == CLOSED and expected is None
            with pytest.raises(InsufficientHistory, match=f"^{CLOSED}$"):
                adapter.generate(strategy, draws[:i], target)
            closed += 1
        else:
            assert reason is None
            tickets = adapter.generate(strategy, draws[:i], target)
            assert [ticket.ticket_position for ticket in tickets] == [1, 2]
            assert all(ticket.special_number is None for ticket in tickets)
            portfolio = [list(ticket.main_numbers) for ticket in tickets]
            assert portfolio == expected, target.draw_number
            if portfolio[0] == portfolio[1]:
                duplicates.append(target.draw_number)
            actual.append(portfolio)
        if i:
            prefix.update(b",")
        prefix.update(_canonical(target.main_numbers))

    assert closed == record["closed_execution_count"] == 100
    assert record["closed_reason_code_distribution"] == {CLOSED: 100}
    assert len(actual) == record["ok_execution_count"] == 2049
    assert sum(map(len, actual)) == 4098
    assert duplicates == ["115000008"]
    assert (
        hashlib.sha256(_canonical(actual)).hexdigest()
        == record["ticket_sequence_sha256"]
        == "202affe6cb1b949469bc3d14cad63653f66a9badad05a0bcc2f1d76dfef7b19b"
    )


def test_off_ledger_windows_and_negative_exclusion(monkeypatch: pytest.MonkeyPatch) -> None:
    # The pinned donor produced these raw/filtered pairs for this synthetic history.
    rng = random.Random(24)
    history = tuple(
        CausalDrawRow(str(115000000 + i), "2024-01-01", tuple(sorted(rng.sample(range(1, 50), 6))))
        for i in range(610)
    )
    zone = Mock(wraps=dual._zone_balance_ticket)
    bayesian = Mock(wraps=dual._bayesian_desc_ticket)
    exclusions = Mock(wraps=dual._negative_selection_excluded)
    replacements = Mock(wraps=dual._filter_prediction)
    monkeypatch.setattr(dual, "_zone_balance_ticket", zone)
    monkeypatch.setattr(dual, "_bayesian_desc_ticket", bayesian)
    monkeypatch.setattr(dual, "_negative_selection_excluded", exclusions)
    monkeypatch.setattr(dual, "_filter_prediction", replacements)
    state = random.getstate()
    assert dual.FrozenEnhancedDualBetPredictor().get_bets(history, BIG) == (
        (6, 17, 19, 27, 33, 48),
        (19, 30, 33, 36, 37, 45),
    )
    assert random.getstate() == state
    recent_first = history[::-1]
    zone.assert_called_once_with(recent_first[:500])
    bayesian.assert_called_once_with(history[-300:])
    exclusions.assert_called_once_with(recent_first)
    excluded = {3, 5, 8, 25, 28, 32, 34, 41}
    assert replacements.call_args_list == [
        call([6, 17, 19, 27, 32, 48], excluded, recent_first),
        call([19, 28, 30, 32, 37, 45], excluded, recent_first),
    ]


def test_exact_version_and_backfill_boundary() -> None:
    frozen, sources = cli._exact_strategy_inventory(BIG, STRATEGY_ID, VERSION)
    live, _ = cli._exact_strategy_inventory(BIG, STRATEGY_ID, "v0.1")
    strategy = frozen[0].strategy
    assert frozen[0].implementation.strategy_version == strategy.strategy_version == VERSION
    assert live[0].implementation.strategy_version == live[0].strategy.strategy_version == "v0.1"
    assert strategy.fingerprint != live[0].strategy.fingerprint
    draws = _draws()[:101]
    store = Mock(spec=BackfillStore)
    store.lookup_complete_by_logical_keys.return_value = {}
    store.lookup_many_by_unique_keys.return_value = {}
    store.summary.return_value = {}
    backfill = ReplayBackfill(
        adapter=cli.build_adapter(BIG, frozen),
        strategies=(strategy,),
        draws=draws,
        source_identity="wave58-enhanced-dual-fixture",
        store=store,
        execution_version="wave58-test",
        strategy_sources=sources,
    )
    backfill.execute(BackfillSelection(all_draws=True), batch_size=len(draws))
    *closed, eligible = store.save_many.call_args.args[1]
    assert len(closed) == 100
    for count, cell in enumerate(closed):
        assert cell["target_draw_id"] == draws[count].draw_number and cell["history_count"] == count
        assert cell["execution_status"] == "NOT_ELIGIBLE" and cell["predicted_tickets"] == []
        assert cell["error_reason"] == f"INSUFFICIENT_CAUSAL_HISTORY_REQUIRED_100_GOT_{count}"
        assert cell["strategy_version"] == VERSION
    assert eligible["target_draw_id"] == "96000103" and eligible["history_count"] == 100
    assert eligible["execution_status"] == "COMPLETE" and len(eligible["predicted_tickets"]) == 2
    assert eligible["strategy_version"] == VERSION
