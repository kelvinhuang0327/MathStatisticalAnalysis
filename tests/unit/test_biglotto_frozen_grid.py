"""Fixed, historical, full-portfolio comparisons independent of replay implementation."""

from __future__ import annotations

import csv
import hashlib
import json
import random
import sqlite3
from collections import Counter
from dataclasses import replace
from datetime import date
from functools import cache
from importlib import import_module
from pathlib import Path
from unittest.mock import Mock

import pytest

from lottolab.application import biglotto_frozen_diversified_ensemble_v6 as v6
from lottolab.application import biglotto_frozen_hpsb as hpsb
from lottolab.application import legacy_source_native_portfolios_wave27 as wave27
from lottolab.application.biglotto_versioned_replay_bindings import (
    VERSIONED_REPLAY_SOURCES,
    versioned_biglotto_replay_bindings,
)
from lottolab.application.legacy_history_native_portfolios import LegacyHistoryDraw
from lottolab.application.use_cases.historical_replay_controller import ReplayTypedClosure
from lottolab.application.use_cases.replay_backfill import (
    BackfillSelection,
    BackfillStore,
    ReplayBackfill,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayDraw
from lottolab.interfaces.cli import replay_backfill as cli
from lottolab.strategies.adapters.base import CausalDrawRow, InsufficientHistory, InvalidOutput

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


def test_wave64_xgboost_ordered_playback(monkeypatch: pytest.MonkeyPatch) -> None:
    deny_sqlite = Mock(side_effect=AssertionError("Wave 64 must use packaged data only"))
    monkeypatch.setattr(sqlite3, "connect", deny_sqlite)
    monkeypatch.setattr(sqlite3.dbapi2, "connect", deny_sqlite)
    resources = ROOT / "src/lottolab/strategies/data"
    evidence_raw = (resources / "biglotto_legacy_xgboost_wave64_evidence_v1.json").read_bytes()
    assert hashlib.sha256(evidence_raw).hexdigest() == (
        "2173aa5a4c354c8d8d11c0459e3017dcc4baaca770dc6fc623df683c0b191741"
    )
    evidence = json.loads(evidence_raw)
    raw = (resources / "biglotto_xgboost_wave64_ticket_ledger_v1.json").read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == evidence["ledger_file_sha256"]
        == ("0e2946ccf9a803488afd5475e833bd557a40bf93e5d1cb26e912a29926b1a9ba")
    )
    ledger = json.loads(raw)
    source = _source("xgboost_model")
    [record] = evidence["strategies"]
    parity = evidence["parity"]
    runtime = "CPYTHON_3_9_6_NUMPY_1_26_2_PANDAS_2_1_3_SKLEARN_1_3_2_XGBOOST_2_0_2"
    assert ledger["source_reference_runtime"] == parity["source_reference_runtime"] == runtime
    assert record["source_reference_runtime"] == runtime and parity["status"] == "PASS"
    assert ledger["legacy_method_id"] == source.source_path == record["legacy_method_id"]
    assert ledger["frozen_source_commit"] == source.source_commit == parity["frozen_source_commit"]
    assert (
        ledger["source_sha256"]
        == source.source_sha256
        == parity["source_artifact"]["source_sha256"]
    )
    assert source.source_blob_id == parity["source_artifact"]["source_blob_id"]
    assert parity["thread_count_parity"]["status"] == "PASS"
    assert parity["thread_count_parity"]["omp_thread_counts"] == [1, 8]
    bindings, accounts = cli._exact_strategy_inventory(
        BIG, source.strategy_id, source.strategy_version
    )
    strategy = bindings[0].strategy
    adapter = cli.build_adapter(BIG, bindings)
    assert accounts[source.strategy_id]["source"] == source.locator
    assert runtime in accounts[source.strategy_id]["replay_scope"]
    assert (strategy.min_history, strategy.native_ticket_count) == (15, 1)
    draws = _draws()[:2149]
    assert len(draws) == len(ledger["tickets"]) == evidence["target_draw_count"] == 2149
    assert [d.draw_number for d in draws] == ledger["target_draw_numbers"]
    assert draws[15].draw_number == "96000016" and draws[-1].draw_number == "115000073"
    assert ledger["history_input_draw_count"] == [min(i, 1000) for i in range(2149)]

    reason = "TRAINING_DATA_INSUFFICIENT_LT_15_HISTORY_DRAWS"
    assert ledger["closed_reason"] == [reason] * 15 + [None] * 2134
    prefix = hashlib.sha256(b"[")
    actual = []
    for cutoff, target in enumerate(draws):
        context = prefix.copy()
        context.update(b"]")
        assert context.hexdigest() == ledger["context_numbers_sha256_by_target"][cutoff]
        if cutoff < 15:
            with pytest.raises(InsufficientHistory) as closure:
                adapter.generate(strategy, draws[:cutoff], target)
            assert str(closure.value) == reason
            actual.append(None)
        else:
            [ticket] = adapter.generate(strategy, draws[:cutoff], target)
            assert ticket.ticket_position == 1 and ticket.special_number is None
            actual.append([list(ticket.main_numbers)])
        assert actual[-1] == ledger["tickets"][cutoff], target.draw_number
        if cutoff:
            prefix.update(b",")
        prefix.update(json.dumps(target.main_numbers, separators=(",", ":")).encode())
    assert (
        sum(len(row) for row in actual if row is not None) == record["ok_execution_count"] == 2134
    )
    digest = hashlib.sha256(json.dumps(actual, separators=(",", ":")).encode()).hexdigest()
    assert (
        digest
        == parity["ticket_sequence_sha256"]
        == record["ticket_sequence_sha256"]
        == ("1d9752141cdc71301c7410b015bbbf6ca6dd522a687d6171da3def2b139a36df")
    )
    deny_sqlite.assert_not_called()


def test_wave64_xgboost_scope_and_recorded_backfill_closures() -> None:
    source = _source("xgboost_model")
    bindings, accounts = cli._exact_strategy_inventory(
        BIG, source.strategy_id, source.strategy_version
    )
    strategy = bindings[0].strategy
    adapter = cli.build_adapter(BIG, bindings)
    draws = _draws()
    target = draws[15]
    assert adapter.generate(strategy, draws[:15], target) == adapter.generate(
        strategy, draws[:15], replace(target, main_numbers=(1, 2, 3, 4, 5, 6), special_number=49)
    )
    with pytest.raises(ReplayTypedClosure, match="TARGET_OUTSIDE_FROZEN_WAVE64_TICKET_LEDGER"):
        adapter.generate(strategy, draws[:2149], draws[2149])
    for cutoff in (3, 15, 1001):
        for altered in (
            replace(draws[0], main_numbers=(1, 2, 3, 4, 5, 6)),
            replace(draws[0], draw_number="96000000"),
        ):
            with pytest.raises(ValueError, match="FROZEN_WAVE64_FULL_PREFIX_CONTEXT_MISMATCH"):
                adapter.generate(strategy, (altered, *draws[1:cutoff]), draws[cutoff])
    with pytest.raises(ValueError, match="strictly precede"):
        future = replace(draws[0], draw_date=target.draw_date)
        adapter.generate(strategy, (future, *draws[1:15]), target)

    store = Mock(spec=BackfillStore)
    store.lookup_complete_by_logical_keys.return_value = {}
    store.lookup_many_by_unique_keys.return_value = {}
    store.summary.return_value = {}
    ReplayBackfill(
        adapter=adapter,
        strategies=(strategy,),
        draws=draws[:16],
        source_identity="wave64-fixture",
        store=store,
        execution_version="wave64-test",
        strategy_sources=accounts,
    ).execute(BackfillSelection(all_draws=True))
    *closed, first = store.save_many.call_args.args[1]
    assert [row["target_draw_id"] for row in closed] == [draw.draw_number for draw in draws[:15]]
    assert all(
        row["execution_status"] == "NOT_ELIGIBLE"
        and row["predicted_tickets"] == []
        and row["error_reason"] == "TRAINING_DATA_INSUFFICIENT_LT_15_HISTORY_DRAWS"
        for row in closed
    )
    assert first["target_draw_id"] == "96000016" and first["execution_status"] == "COMPLETE"
    assert first["predicted_tickets"] == [
        {"ticket_position": 1, "main_numbers": [6, 18, 26, 44, 45, 48], "special_number": None}
    ]
    assert first["training"]["training_status"] == "NOT_TRAINABLE"


def test_wave62_diversified_portfolios(monkeypatch: pytest.MonkeyPatch) -> None:
    reject_sqlite = Mock(side_effect=AssertionError("Wave 62 replay must not open SQLite"))
    monkeypatch.setattr(sqlite3, "connect", reject_sqlite)
    monkeypatch.setattr(sqlite3.dbapi2, "connect", reject_sqlite)
    source = _source("biglotto_diversified_ensemble")
    resources = ROOT / "src/lottolab/strategies/data"
    raw = (resources / "biglotto_legacy_diversified_wave62_evidence_v1.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "7441a0e0007e8d4e53f9e2e05ccc350d20518411b847b6c36ffd07ec4cbbfd3d"
    )
    evidence = json.loads(raw)
    record = next(r for r in evidence["strategies"] if r["legacy_method_id"] == source.source_path)
    raw = (resources / "biglotto_diversified_wave62_ticket_ledger_v1.json").read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == evidence["ledger_file_sha256"]
        == ("223b593f391d3f9f9aafc1c494b7693e4e25a194c68c620a83c8ee822b1182e9")
    )
    ledger = json.loads(raw)
    assert ledger["frozen_source_commit"] == source.source_commit
    assert ledger["source_sha256_by_method"][source.source_path] == source.source_sha256
    assert {
        "path": source.source_path,
        "sha256": source.source_sha256,
        "source_blob_id": source.source_blob_id,
    } in evidence["parity"]["source_artifacts"]
    bindings, accounts = cli._exact_strategy_inventory(
        BIG, source.strategy_id, source.strategy_version
    )
    assert accounts[source.strategy_id]["source"] == source.locator
    [binding] = bindings
    strategy, adapter = binding.strategy, cli.build_adapter(BIG, bindings)
    assert (strategy.min_history, strategy.native_ticket_count) == (50, 3)
    draws = _draws()[:2149]
    expected = ledger["tickets_by_method"][source.source_path]
    reasons = ledger["closed_reason_by_method"][source.source_path]
    closure = "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
    assert reasons == [closure] * 50 + [None] * 2099
    assert ledger["configuration_count_by_method"][source.source_path] == [None] * 50 + [1] * 2099
    assert len(expected) == len(draws) == len(ledger["context_numbers_sha256_by_target"]) == 2149
    assert [draw.draw_number for draw in draws] == ledger["target_draw_numbers"]
    assert draws[50].draw_number == "96000051"

    prefix = hashlib.sha256(b"[")
    actual = []
    for cutoff, target in enumerate(draws):
        context = prefix.copy()
        context.update(b"]")
        assert context.hexdigest() == ledger["context_numbers_sha256_by_target"][cutoff]
        if cutoff < 50:
            with pytest.raises(InsufficientHistory) as exc:
                adapter.generate(strategy, draws[:cutoff], target)
            assert str(exc.value) == reasons[cutoff]
            portfolio = None
        else:
            tickets = adapter.generate(strategy, draws[:cutoff], target)
            assert [t.ticket_position for t in tickets] == [1, 2, 3]
            assert all(t.special_number is None for t in tickets)
            portfolio = [list(t.main_numbers) for t in tickets]
        assert portfolio == expected[cutoff], (cutoff, target.draw_number)
        actual.append(portfolio)
        if cutoff:
            prefix.update(b",")
        prefix.update(json.dumps(target.main_numbers, separators=(",", ":")).encode())

    eligible = [p for p in actual if p is not None]
    assert actual.count(None) == record["closed_execution_count"] == 50
    assert len(eligible) == record["ok_execution_count"] == 2099
    assert sum(map(len, eligible)) == 6297
    assert (
        hashlib.sha256(json.dumps(eligible, separators=(",", ":")).encode()).hexdigest()
        == record["ticket_sequence_sha256"]
        == "06fd6f9bc0cdac34c20859d0cd27e9c1b5f8e60c3f031e86c1bdb93b3ae2ccf5"
    )
    assert hashlib.sha256(json.dumps(actual, separators=(",", ":")).encode()).hexdigest() == (
        "e24e53c0688b27e6c2d6b632912a46d79ca5366dce3b7ace393b5fe4870c75c6"
    )
    reject_sqlite.assert_not_called()


def test_wave62_diversified_seed_and_special_history(monkeypatch: pytest.MonkeyPatch) -> None:
    source = _source("biglotto_diversified_ensemble")
    bindings, _ = cli._exact_strategy_inventory(BIG, source.strategy_id, source.strategy_version)
    strategy, adapter = bindings[0].strategy, cli.build_adapter(BIG, bindings)
    draws = _draws()
    history, target = draws[:55], draws[55]
    changed_special = (*history[:-1], replace(history[-1], special_number=3))
    random_factory = Mock(wraps=random.Random)
    state = random.getstate()
    monkeypatch.setattr(random, "Random", random_factory)
    original = adapter.generate(strategy, history, target)
    changed = adapter.generate(strategy, changed_special, target)
    # The previous special determines the second pool. Its rejection draws can
    # shift the same RNG stream that supplies the third (entropy outlier) bet.
    assert original[0] == changed[0] and original[1] != changed[1] and original[2] != changed[2]
    secret = replace(target, main_numbers=(1, 2, 3, 4, 5, 6), special_number=7)
    assert adapter.generate(strategy, history, secret) == original
    assert [c.args for c in random_factory.call_args_list] == [(42,)] * 3
    assert random.getstate() == state
    with pytest.raises(InvalidOutput, match="strictly earlier"):
        adapter.generate(strategy, (*history, target), target)
    with pytest.raises(InvalidOutput, match="chronological"):
        adapter.generate(strategy, history[::-1], target)
    with pytest.raises(InvalidOutput, match="missing historical special"):
        adapter.generate(
            strategy, (*history[:-1], replace(history[-1], special_number=None)), target
        )


def test_wave62_diversified_backfill_minimum() -> None:
    source = _source("biglotto_diversified_ensemble")
    bindings, accounts = cli._exact_strategy_inventory(
        BIG, source.strategy_id, source.strategy_version
    )
    strategy = bindings[0].strategy
    draws = _draws()[:51]
    store = Mock(spec=BackfillStore)
    store.lookup_complete_by_logical_keys.return_value = {}
    store.lookup_many_by_unique_keys.return_value = {}
    store.summary.return_value = {}
    ReplayBackfill(
        adapter=cli.build_adapter(BIG, bindings),
        strategies=(strategy,),
        draws=draws,
        source_identity="wave62-fixture",
        store=store,
        execution_version="wave62-test",
        strategy_sources=accounts,
    ).execute(BackfillSelection(all_draws=True))
    *closed, eligible = [row for batch in store.save_many.call_args_list for row in batch.args[1]]
    assert len(closed) == 50
    for i, row in enumerate(closed):
        assert (row["target_draw_id"], row["history_count"]) == (draws[i].draw_number, i)
        assert row["execution_status"] == "NOT_ELIGIBLE" and row["predicted_tickets"] == []
        assert row["error_reason"] == "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
    assert eligible["target_draw_id"] == "96000051" and eligible["execution_status"] == "COMPLETE"
    assert eligible["strategy_version"] == source.strategy_version
    assert len(eligible["predicted_tickets"]) == 3


def test_r184_bindings_keep_fingerprints_and_default_minimum_closures() -> None:
    new_ids = {
        _source("xgboost_model").strategy_id,
        _source("biglotto_diversified_ensemble").strategy_id,
    }
    bindings = versioned_biglotto_replay_bindings()
    previous = tuple(b for b in bindings if b.strategy.strategy_id not in new_ids)
    strategies = {b.strategy.strategy_id: b.strategy for b in previous}
    assert len(previous) == len(strategies) == 41
    store = Mock(spec=BackfillStore)
    store.lookup_complete_by_logical_keys.return_value = {}
    store.lookup_many_by_unique_keys.return_value = {}
    store.summary.return_value = {}
    ReplayBackfill(
        adapter=cli.build_adapter(BIG, bindings),
        strategies=tuple(b.strategy for b in previous),
        draws=_draws()[:1],
        source_identity="r184-closures",
        store=store,
        execution_version="r186-test",
    ).execute(BackfillSelection(all_draws=True))
    rows = [row for batch in store.save_many.call_args_list for row in batch.args[1]]
    assert len(rows) == 41 and {r["strategy_id"] for r in rows} == set(strategies)
    snapshot = []
    for row in rows:
        strategy = strategies[row["strategy_id"]]
        assert row["execution_status"] == "NOT_ELIGIBLE" and row["predicted_tickets"] == []
        minimum = strategy.min_history
        assert row["error_reason"] == f"INSUFFICIENT_CAUSAL_HISTORY_REQUIRED_{minimum}_GOT_0"
        snapshot.append(
            (
                *strategy.identity,
                minimum,
                strategy.native_ticket_count,
                strategy.behavior.value,
                strategy.seed_contract,
                row["execution_status"],
                row["error_reason"],
            )
        )
    # Collected through ReplayBackfill at the R184 integration commit c59752b7.
    digest = hashlib.sha256(json.dumps(sorted(snapshot), separators=(",", ":")).encode())
    assert digest.hexdigest() == "9042e66a9145928343f15f9590da027d9c6890d1e37ce73384384117f00a64a7"


def test_wave63_advanced_ordered_portfolios(monkeypatch: pytest.MonkeyPatch) -> None:
    reject_sqlite = Mock(side_effect=AssertionError("Wave 63 replay must not open SQLite"))
    monkeypatch.setattr(sqlite3, "connect", reject_sqlite)
    monkeypatch.setattr(sqlite3.dbapi2, "connect", reject_sqlite)
    source = _source("advanced_methods_benchmark")
    resources = ROOT / "src/lottolab/strategies/data"
    raw = (resources / "biglotto_legacy_advanced_methods_wave63_evidence_v1.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "c9d0a3ae6e5678f1aca771dc88b1cc03b11756ce66c129a5198713bf594e0057"
    )
    evidence = json.loads(raw)
    raw = (resources / "biglotto_advanced_methods_wave63_ticket_ledger_v1.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == evidence["ledger_file_sha256"] == (
        "f98ad62752c35bcf47fe00338f8e8b4ddd1f39caa73a80405409c963a8651d04"
    )
    ledger = json.loads(raw)
    assert ledger["legacy_method_id"] == source.source_path
    assert ledger["frozen_source_commit"] == source.source_commit
    assert ledger["source_sha256"] == source.source_sha256
    [record] = evidence["strategies"]
    assert ledger["closed_reason"] == ["NO_PRIOR_DRAW_FOR_CAUSAL_CUTOFF", *([None] * 2148)]
    assert record["ok_execution_count"] == 2148 and ledger["tickets"][0] is None

    bindings, accounts = cli._exact_strategy_inventory(
        BIG, source.strategy_id, source.strategy_version
    )
    assert accounts[source.strategy_id]["source"] == source.locator
    strategy = bindings[0].strategy
    assert (strategy.strategy_version, strategy.min_history, strategy.native_ticket_count) == (
        source.strategy_version, 1, 25
    )
    adapter = cli.build_adapter(BIG, bindings)
    draws = _draws()[:2149]
    assert len(draws) == len(ledger["tickets"]) == 2149
    assert [row.draw_number for row in draws] == ledger["target_draw_numbers"]
    store = Mock(spec=BackfillStore)
    store.lookup_complete_by_logical_keys.return_value = {}
    store.lookup_many_by_unique_keys.return_value = {}
    store.summary.return_value = {}
    ReplayBackfill(
        adapter=adapter,
        strategies=(strategy,),
        draws=draws[:1],
        source_identity="wave63-historical-fixture",
        store=store,
        execution_version="wave63-test",
        strategy_sources=accounts,
    ).execute(BackfillSelection(all_draws=True))
    [closed] = store.save_many.call_args.args[1]
    assert closed["target_draw_id"] == "96000001" and closed["history_count"] == 0
    assert closed["execution_status"] == "NOT_ELIGIBLE" and closed["predicted_tickets"] == []

    prefix, outputs = hashlib.sha256(b"["), hashlib.sha256(b"[")
    duplicates: Counter[int] = Counter()
    positions = 0
    for cutoff, target in enumerate(draws[1:], 1):
        if cutoff > 1:
            prefix.update(b",")
            outputs.update(b",")
        prefix.update(json.dumps(draws[cutoff - 1].main_numbers, separators=(",", ":")).encode())
        context = prefix.copy()
        context.update(b"]")
        assert context.hexdigest() == ledger["context_numbers_sha256_by_target"][cutoff]
        tickets = adapter.generate(strategy, draws[:cutoff], target)
        assert [ticket.ticket_position for ticket in tickets] == list(range(1, 26))
        assert all(ticket.special_number is None for ticket in tickets)
        portfolio = [ticket.main_numbers for ticket in tickets]
        actual = [list(numbers) for numbers in portfolio]
        assert actual == ledger["tickets"][cutoff], target.draw_number
        duplicates[len(portfolio) - len(set(portfolio))] += 1
        positions += len(portfolio)
        outputs.update(json.dumps(portfolio, separators=(",", ":")).encode())
    outputs.update(b"]")
    assert positions == 53_700
    assert {str(n): count for n, count in duplicates.items()} == record[
        "native_duplicate_ticket_count_distribution"
    ]
    assert outputs.hexdigest() == "9562b26912310b56610b3c3aa1da426beb06dd7493123caf0a42d6dc479020a2"
    reject_sqlite.assert_not_called()


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


def test_wave58_v6_ordered_portfolios() -> None:
    source = _source("biglotto_diversified_ensemble_v6")
    resources = ROOT / "src/lottolab/strategies/data"
    raw = (resources / "biglotto_legacy_dual_seeded_wave58_evidence_v1.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "7db702bf9754c1a2d037130b9a11ce7b52e14121097e048d6c09cf505832ad35"
    )
    evidence = json.loads(raw)
    record = next(r for r in evidence["strategies"] if r["legacy_method_id"] == source.source_path)
    raw = (resources / "biglotto_dual_seeded_wave58_ticket_ledger_v1.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == evidence["ledger_file_sha256"] == (
        "3070f69175c806674547111c54b8109d94ec57c8b34a78b1082f4e34adbabe01"
    )
    ledger = json.loads(raw)
    assert ledger["frozen_source_commit"] == source.source_commit
    assert ledger["source_sha256_by_method"][source.source_path] == source.source_sha256
    bindings, accounts = cli._exact_strategy_inventory(
        BIG, source.strategy_id, source.strategy_version
    )
    assert accounts[source.strategy_id]["source"] == source.locator
    strategy, adapter = bindings[0].strategy, cli.build_adapter(BIG, bindings)
    assert (strategy.min_history, strategy.native_ticket_count) == (1, 3)
    expected = ledger["tickets_by_method"][source.source_path]
    draws = _draws()[:2149]
    assert len(expected) == len(draws) == 2149
    assert [d.draw_number for d in draws] == ledger["target_draw_numbers"]
    assert draws[0].draw_number == "96000001" and expected[0] is None
    assert ledger["closed_reason_by_method"][source.source_path] == [
        "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM", *([None] * 2148)
    ]
    with pytest.raises(InsufficientHistory):
        adapter.generate(strategy, (), draws[0])

    prefix = hashlib.sha256(b"[")
    actual = []
    for cutoff, target in enumerate(draws):
        context = prefix.copy()
        context.update(b"]")
        assert context.hexdigest() == ledger["context_numbers_sha256_by_target"][cutoff]
        if cutoff:
            tickets = adapter.generate(strategy, draws[:cutoff], target)
            assert [t.ticket_position for t in tickets] == [1, 2, 3]
            assert all(t.special_number is None for t in tickets)
            portfolio = [list(t.main_numbers) for t in tickets]
            assert portfolio == expected[cutoff], (cutoff, target.draw_number)
            actual.append(portfolio)
            prefix.update(b",")
        prefix.update(json.dumps(target.main_numbers, separators=(",", ":")).encode())

    assert len(actual) == record["ok_execution_count"] == 2148
    assert sum(map(len, actual)) == 6444
    digest = hashlib.sha256(json.dumps(actual, separators=(",", ":")).encode()).hexdigest()
    assert digest == record["ticket_sequence_sha256"] == (
        "e78dd91dd381562789ac0903fa030ac53082d7c39c063cdc3cd8b23f1ecc395e"
    )


def test_wave58_v6_backfill_closure_and_version() -> None:
    source = _source("biglotto_diversified_ensemble_v6")
    bindings, accounts = cli._exact_strategy_inventory(
        BIG, source.strategy_id, source.strategy_version
    )
    live, _ = cli._exact_strategy_inventory(BIG, source.strategy_id, "v0.1")
    strategy = bindings[0].strategy
    assert live[0].strategy.strategy_version == "v0.1"
    assert strategy.fingerprint != live[0].strategy.fingerprint
    adapter = cli.build_adapter(BIG, bindings)
    draws = _draws()
    history, target = draws[:1001], draws[1001]
    full = adapter.generate(strategy, history, target)
    assert full != adapter.generate(strategy, history[-1000:], target)
    limited = cli.build_adapter(BIG, live)
    assert limited.generate(live[0].strategy, history, target) == limited.generate(
        live[0].strategy, history[-1000:], target
    )
    assert full != limited.generate(live[0].strategy, history, target)

    store = Mock(spec=BackfillStore)
    store.lookup_complete_by_logical_keys.return_value = {}
    store.lookup_many_by_unique_keys.return_value = {}
    store.summary.return_value = {}
    worker = ReplayBackfill(
        adapter=adapter,
        strategies=(strategy,),
        draws=draws[:2],
        source_identity="wave58-fixture",
        store=store,
        execution_version="wave58-test",
        strategy_sources=accounts,
    )
    worker.execute(BackfillSelection(all_draws=True))
    closed, eligible = store.save_many.call_args.args[1]
    assert closed["target_draw_id"] == "96000001" and closed["history_count"] == 0
    assert closed["execution_status"] == "NOT_ELIGIBLE" and closed["predicted_tickets"] == []
    assert eligible["execution_status"] == "COMPLETE" and len(eligible["predicted_tickets"]) == 3
    assert eligible["strategy_version"] == source.strategy_version


def test_wave58_v6_graph_window_ties_and_seed_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    # A six-node clique gives equal nonzero centrality to its members and
    # equal zero centrality to the remaining nodes. The newer clique is disjoint.
    history = tuple(
        CausalDrawRow(str(i), str(i), (21, 22, 23, 24, 25, 26) if i < 500 else (1, 2, 3, 4, 5, 6))
        for i in range(1001)
    )
    graph = Mock(wraps=v6._graph_adjacency)
    monkeypatch.setattr(v6, "_graph_adjacency", graph)
    adapter = v6.FrozenDiversifiedEnsembleV6()
    global_state = random.getstate()
    try:
        random.seed(7)
        before = random.getstate()
        first = adapter.get_bets(history, BIG)
        assert random.getstate() == before
        graph.assert_called_once_with(history[:500][::-1], lookback=500)
        assert v6._graph_pool(history[:500]) == (*range(21, 27), *range(1, 15))
        random.seed(54321)
        before = random.getstate()
        adapter.get_bets(history[:2], BIG)
        assert adapter.get_bets(history, BIG) == first
        assert random.getstate() == before
    finally:
        random.setstate(global_state)


def test_wave58_v6_tail_pool_prefers_latest_ties_and_odds_first() -> None:
    newest = CausalDrawRow("2", "2007-01-02", (5, 6, 7, 8, 9, 10))
    oldest = CausalDrawRow("1", "2007-01-01", (1, 2, 3, 4, 9, 10))
    # Tails 9 and 0 occur twice. The next three slots go to tails 5, 6, 7.
    assert v6._tail_pool((newest, oldest)) == (
        5, 7, 9, 15, 17, 19, 25, 27, 29, 35, 37, 39, 45, 47, 49,
        6, 10, 16, 20, 26, 30, 36, 40, 46,
    )
    sparse = CausalDrawRow("1", "2007-01-01", (1, 2, 11, 12, 21, 22))
    assert v6._tail_pool((sparse,)) == tuple(range(1, 50))


def test_wave57_hpsb_ordered_portfolios() -> None:
    source = _source("hpsb_optimizer")
    resources = ROOT / "src/lottolab/strategies/data"
    raw = (resources / "biglotto_legacy_hpsb_native_wave57_evidence_v1.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "235947a7035aa43396125ba3340d48872dd81a60a3f367a1908da98dbf4b0512"
    )
    evidence = json.loads(raw)
    raw = (resources / "biglotto_hpsb_wave57_ticket_ledger_v1.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == evidence["ledger_file_sha256"] == (
        "5120f4cf4928eb843c4b1a29ccfe913692bcf34398308d0c89bcde66527f1e45"
    )
    ledger = json.loads(raw)
    assert ledger["frozen_source_commit"] == source.source_commit
    assert ledger["source_sha256_by_method"][source.source_path] == source.source_sha256
    assert ledger["source_reference_runtime"] == (
        "CPYTHON_3_9_6_NUMPY_1_26_2_SCIPY_1_12_0_HPSB_V2_DMS_STATISTICAL_RANDOM_SEED_HISTORY_LENGTH"
    )
    [record] = evidence["strategies"]
    assert record["closed_reason_code_distribution"] == {"NO_PRIOR_DRAW_FOR_CAUSAL_CUTOFF": 1}
    assert record["ok_execution_count"] == 2148

    bindings, accounts = cli._exact_strategy_inventory(
        BIG, source.strategy_id, source.strategy_version
    )
    assert accounts[source.strategy_id]["source"] == source.locator
    strategy, adapter = bindings[0].strategy, cli.build_adapter(BIG, bindings)
    assert (strategy.min_history, strategy.native_ticket_count) == (1, 1)
    draws = _draws()[:2149]
    expected = ledger["tickets_by_method"][source.source_path]
    assert [d.draw_number for d in draws] == ledger["target_draw_numbers"]
    assert len(expected) == len(draws) == 2149
    assert draws[0].draw_number == "96000001"
    with pytest.raises(InsufficientHistory):
        adapter.generate(strategy, (), draws[0])

    prefix = hashlib.sha256(b"[")
    outputs = hashlib.sha256(b"[")
    for cutoff, target in enumerate(draws[1:], 1):
        if cutoff > 1:
            prefix.update(b",")
            outputs.update(b",")
        prefix.update(json.dumps(draws[cutoff - 1].main_numbers, separators=(",", ":")).encode())
        context = prefix.copy()
        context.update(b"]")
        assert context.hexdigest() == ledger["context_numbers_sha256_by_target"][cutoff]
        [ticket] = adapter.generate(strategy, draws[:cutoff], target)
        assert ticket.ticket_position == 1 and ticket.special_number is None
        portfolio = [list(ticket.main_numbers)]
        assert portfolio == expected[cutoff], (cutoff, target.draw_number)
        outputs.update(json.dumps(portfolio, separators=(",", ":")).encode())
    outputs.update(b"]")
    assert outputs.hexdigest() == record["ticket_sequence_sha256"] == (
        "1b3acdf5a173d266dbf245da228c3b447e797cc0a6bc2a90dabdbab6abf307fe"
    )


def test_wave57_hpsb_backfill_closure_and_version() -> None:
    source = _source("hpsb_optimizer")
    bindings, accounts = cli._exact_strategy_inventory(
        BIG, source.strategy_id, source.strategy_version
    )
    live, _ = cli._exact_strategy_inventory(BIG, source.strategy_id, "v0.1")
    strategy = bindings[0].strategy
    assert live[0].strategy.strategy_version == "v0.1"
    assert live[0].strategy.fingerprint != strategy.fingerprint
    store = Mock(spec=BackfillStore)
    store.lookup_complete_by_logical_keys.return_value = {}
    store.lookup_many_by_unique_keys.return_value = {}
    store.summary.return_value = {}
    worker = ReplayBackfill(
        adapter=cli.build_adapter(BIG, bindings),
        strategies=(strategy,),
        draws=_draws()[:2],
        source_identity="wave57-historical-fixture",
        store=store,
        execution_version="wave57-test",
        strategy_sources=accounts,
    )
    result = worker.execute(BackfillSelection(all_draws=True))
    assert result["newly_calculated_count"] == 2
    closed, eligible = store.save_many.call_args.args[1]
    assert closed["target_draw_id"] == "96000001" and closed["history_count"] == 0
    assert closed["execution_status"] == "NOT_ELIGIBLE"
    assert closed["predicted_tickets"] == []
    assert eligible["strategy_version"] == source.strategy_version
    assert eligible["history_count"] == 1 and eligible["execution_status"] == "COMPLETE"
    [ticket] = eligible["predicted_tickets"]
    assert ticket["ticket_position"] == 1 and ticket["main_numbers"] == [3, 13, 21, 23, 27, 49]


def test_wave57_hpsb_prefix_length_seed() -> None:
    # At these adjacent Wave 57 targets the statistical method won the audit.
    draws = _draws()
    original_state = random.getstate()
    try:
        for global_seed in (7, 54321):
            random.seed(global_seed)
            state = random.getstate()
            for cutoff, expected in (
                (135, (1, 8, 15, 20, 31, 44)),
                (136, (13, 18, 28, 31, 34, 43)),
            ):
                prefix = tuple(
                    LegacyHistoryDraw(d.draw_number, d.main_numbers) for d in draws[:cutoff]
                )
                assert hpsb._statistical(prefix) == expected
            assert random.getstate() == state
    finally:
        random.setstate(original_state)


def test_wave60_hybrid_ordered_portfolios() -> None:
    source = _source("hybrid_integration_benchmark")
    raw = (
        ROOT / "src/lottolab/strategies/data/biglotto_seeded_benchmarks_wave60_ticket_ledger_v1.json"
    ).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "0834d1b9e1acb622a142fbf29b35ef2a4aa5d269583b67a0fecd6862ca9ccc4b"
    )
    ledger = json.loads(raw)
    assert ledger["frozen_source_commit"] == source.source_commit
    assert ledger["source_sha256_by_method"][source.source_path] == source.source_sha256
    expected = ledger["tickets_by_method"][source.source_path]
    assert hashlib.sha256(json.dumps(expected, separators=(",", ":")).encode()).hexdigest() == (
        "77f90ad4439da7ec1801362b8a9cff9294e92f940bfec5f0c305633520198746"
    )
    bindings, accounts = cli._exact_strategy_inventory(
        BIG, source.strategy_id, source.strategy_version
    )
    assert accounts[source.strategy_id]["source"] == source.locator
    strategy = bindings[0].strategy
    adapter = cli.build_adapter(BIG, bindings)
    assert (strategy.min_history, strategy.native_ticket_count) == (1, 12)
    assert ledger["closed_reason_by_method"][source.source_path] == [
        "NO_PRIOR_DRAW_FOR_CAUSAL_CUTOFF", *([None] * 2148)
    ]
    draws = _draws()[:2149]
    assert len(draws) == len(expected) == 2149
    assert [row.draw_number for row in draws] == ledger["targets"]
    assert expected[0] is None
    with pytest.raises(InsufficientHistory):
        adapter.generate(strategy, (), draws[0])

    # Append to the compact JSON prefix incrementally, checking the exact
    # history used by the source without re-serializing every earlier draw.
    prefix = hashlib.sha256(b"[")
    for cutoff, target in enumerate(draws):
        context = prefix.copy()
        context.update(b"]")
        assert context.hexdigest() == ledger["context_sha256"][cutoff], target.draw_number
        if cutoff:
            tickets = adapter.generate(strategy, draws[:cutoff], target)
            assert [t.ticket_position for t in tickets] == list(range(1, 13))
            assert [list(t.main_numbers) for t in tickets] == expected[cutoff], target.draw_number
            prefix.update(b",")
        prefix.update(json.dumps(target.main_numbers, separators=(",", ":")).encode())


def test_frozen_two_bet_optimizer() -> None:
    _assert_wave27_optimizer_parity("biglotto_2bet_optimizer")


def test_frozen_two_bet_optimizer_v2() -> None:
    _assert_wave27_optimizer_parity("biglotto_2bet_optimizer_v2")


def test_frozen_orthogonal_diversification() -> None:
    source = _source("orthogonal_diversification_benchmark")
    bindings, accounts = cli._exact_strategy_inventory(
        BIG, source.strategy_id, source.strategy_version
    )
    assert accounts[source.strategy_id]["source"] == source.locator
    with pytest.raises(ValueError, match="no executable binding"):
        cli._exact_strategy_inventory(BIG, source.strategy_id, "v0.1")

    strategy = bindings[0].strategy
    adapter = cli.build_adapter(BIG, bindings)
    assert (strategy.min_history, strategy.native_ticket_count) == (1, 35)
    resources = ROOT / "src/lottolab/strategies/data"
    ledger_path = resources / "biglotto_seeded_benchmarks_wave60_ticket_ledger_v1.json"
    raw = ledger_path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "0834d1b9e1acb622a142fbf29b35ef2a4aa5d269583b67a0fecd6862ca9ccc4b"
    )
    ledger = json.loads(raw)
    expected = ledger["tickets_by_method"][source.source_path]
    reasons = ledger["closed_reason_by_method"][source.source_path]
    targets = ledger["targets"]
    draws = _draws()[: len(targets)]
    assert len(expected) == len(targets) == 2149
    assert [draw.draw_number for draw in draws] == targets
    assert ledger["source_sha256_by_method"][source.source_path] == source.source_sha256
    assert ledger["frozen_source_commit"] == source.source_commit
    digest = hashlib.sha256(json.dumps(expected, separators=(",", ":")).encode()).hexdigest()
    assert digest == "fa144bf3a470cf52d599042c75ca3a4a3017aa27a83eb59a6c84fd33438131ba"
    assert expected[0] is None and reasons[0] == "NO_PRIOR_DRAW_FOR_CAUSAL_CUTOFF"
    assert reasons[1:] == [None] * 2148
    with pytest.raises(InsufficientHistory):
        adapter.generate(strategy, (), draws[0])

    # Confirm each prefix belongs to this target while hashing each history row only once.
    prefix = hashlib.sha256(b"[")
    positions = list(range(1, 36))
    for cutoff in range(1, len(targets)):
        if cutoff > 1:
            prefix.update(b",")
        prefix.update(json.dumps(draws[cutoff - 1].main_numbers, separators=(",", ":")).encode())
        closed = prefix.copy()
        closed.update(b"]")
        assert closed.hexdigest() == ledger["context_sha256"][cutoff], targets[cutoff]

        tickets = adapter.generate(strategy, draws[:cutoff], draws[cutoff])
        assert [ticket.ticket_position for ticket in tickets] == positions
        assert [list(ticket.main_numbers) for ticket in tickets] == expected[cutoff], targets[
            cutoff
        ]


def test_frozen_zone_split_optimizer() -> None:
    source = _source("zone_split_optimizer")
    bindings, accounts = cli._exact_strategy_inventory(
        BIG, source.strategy_id, source.strategy_version
    )
    assert accounts[source.strategy_id]["source"] == source.locator
    adapter, strategy = cli.build_adapter(BIG, bindings), bindings[0].strategy
    assert strategy.min_history == 1 and strategy.native_ticket_count == 18
    with pytest.raises(ValueError, match="no executable binding"):
        cli._exact_strategy_inventory(BIG, source.strategy_id, "v0.1")

    raw = (
        ROOT
        / "src/lottolab/strategies/data/biglotto_seeded_benchmarks_wave60_ticket_ledger_v1.json"
    ).read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == "0834d1b9e1acb622a142fbf29b35ef2a4aa5d269583b67a0fecd6862ca9ccc4b"
    )
    ledger = json.loads(raw)
    assert ledger["frozen_source_commit"] == source.source_commit
    assert ledger["source_sha256_by_method"][source.source_path] == source.source_sha256
    assert ledger["local_configuration_count_by_method"][source.source_path] == 6
    expected = ledger["tickets_by_method"][source.source_path]
    digest = hashlib.sha256(json.dumps(expected, separators=(",", ":")).encode()).hexdigest()
    assert digest == "8a2fb7ceb1fb545a18b06e8ccdf9325993f6ca4de46ee7eeee8680b33e19a509"
    draws = _draws()[:2149]
    assert [draw.draw_number for draw in draws] == ledger["targets"]
    assert len(expected) == len(draws) == 2149 and expected[0] is None
    assert ledger["closed_reason_by_method"][source.source_path] == [
        "NO_PRIOR_DRAW_FOR_CAUSAL_CUTOFF",
        *([None] * 2148),
    ]
    with pytest.raises(InsufficientHistory):
        adapter.generate(strategy, (), draws[0])

    prefix = hashlib.sha256(b"[")
    for cutoff, portfolio in enumerate(expected[1:], start=1):
        if cutoff > 1:
            prefix.update(b",")
        prefix.update(json.dumps(draws[cutoff - 1].main_numbers, separators=(",", ":")).encode())
        context = prefix.copy()
        context.update(b"]")
        assert context.hexdigest() == ledger["context_sha256"][cutoff]
        target = draws[cutoff]
        tickets = adapter.generate(strategy, draws[:cutoff], target)
        assert [ticket.ticket_position for ticket in tickets] == list(range(1, 19))
        assert [list(ticket.main_numbers) for ticket in tickets] == portfolio, target.draw_number


def test_frozen_zone_split_numpy_boundary_off_ledger() -> None:
    source = _source("zone_split_optimizer")
    bindings, _ = cli._exact_strategy_inventory(BIG, source.strategy_id, source.strategy_version)
    strategy, adapter = bindings[0].strategy, cli.build_adapter(BIG, bindings)
    # For this newest-first floating-point reduction, mean - std is
    # 13.999999999999998. Exact rational arithmetic would choose center 14.
    history = tuple(
        replace(draw, main_numbers=row, special_number=49)
        for draw, row in zip(
            _draws()[:3],
            [(7, 10, 12, 17, 36, 42), (18, 19, 22, 27, 34, 35), (6, 29, 32, 35, 36, 39)],
            strict=True,
        )
    )
    target = _draws()[-1]  # After the last Wave 60 target.
    tickets = adapter.generate(strategy, history, target)
    assert [ticket.main_numbers for ticket in tickets[15:]] == [
        (10, 11, 13, 16, 17, 18),
        (21, 22, 23, 27, 29, 30),
        (33, 34, 35, 36, 37, 39),
    ]
    poisoned = replace(target, main_numbers=(1, 2, 3, 4, 5, 6), special_number=49)
    assert adapter.generate(strategy, history, poisoned) == tickets


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
