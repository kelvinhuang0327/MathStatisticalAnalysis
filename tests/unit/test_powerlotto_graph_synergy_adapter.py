"""Focused donor/native characterization for deterministic Graph Synergy."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import json
import os
import random
import subprocess
import sys
from types import ModuleType
from typing import TypedDict, cast

import pytest

from lottolab.application.use_cases.generate_bet import (
    GenerateOneBetInput,
    GeneratePortfolioStatus,
    build_production_generate_portfolio,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import LifecycleStatus, ResponseShape
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.powerlotto_graph_synergy import (
    PowerLottoGraphSynergySeed42Adapter,
    _analyze_graph_communities,
    _build_cooccurrence_graph,
    _graph_clancy_tickets,
)
from lottolab.strategies.adapters.powerlotto_wave2 import WAVE2_BLOCKED_STRATEGIES
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

STRATEGY_ID = "power_graph_synergy_seed42_2bet"
DONOR_ID = "power_graph_synergy"
DONOR_SHA256 = "48701cd6854d442ced2b1ca63956d0928be23b715aaa880a116a86a8d905b581"


class _DonorResult(TypedDict):
    nodes: list[int]
    edges: list[list[int]]
    communities: list[list[int]]
    tickets: list[list[int]]


def _history(draws: list[tuple[int, ...]]) -> tuple[CausalDrawRow, ...]:
    return tuple(
        CausalDrawRow(
            draw=f"louvain-{index:04d}",
            date=f"2026-{index % 12 + 1:02d}-{index % 28 + 1:02d}",
            numbers=draw,
        )
        for index, draw in enumerate(draws)
    )


def _representative_cases() -> dict[str, tuple[CausalDrawRow, ...]]:
    ordinary = _history(
        [
            tuple(sorted(((index * 7 + offset * 5) % 38) + 1 for offset in range(6)))
            for index in range(120)
        ]
    )
    rng = random.Random(20260831)
    pseudo_random = _history([tuple(sorted(rng.sample(range(1, 39), 6))) for _ in range(600)])
    return {
        "empty_fallback": (),
        "minimum": _history([(1, 2, 3, 4, 5, 6)]),
        "ordinary": ordinary,
        "strong_cluster": _history([(1, 2, 3, 4, 5, 6)] * 90 + [(7, 8, 9, 10, 11, 12)] * 30),
        "tie_heavy": _history(
            [
                (1, 2, 3, 4, 5, 6),
                (7, 8, 9, 10, 11, 12),
                (13, 14, 15, 16, 17, 18),
                (19, 20, 21, 22, 23, 24),
                (25, 26, 27, 28, 29, 30),
                (31, 32, 33, 34, 35, 36),
            ]
            * 20
        ),
        "pseudo_random_trailing_500": pseudo_random,
        "repeated_same_history": pseudo_random,
    }


def _run_recovered_donor(
    cases: dict[str, tuple[CausalDrawRow, ...]],
) -> dict[str, _DonorResult]:
    donor_path = os.environ.get("LOTTOLAB_POWER_GRAPH_SYNERGY_DONOR")
    donor_python = os.environ.get("LOTTOLAB_POWER_GRAPH_SYNERGY_DONOR_PYTHON")
    if not donor_path or not donor_python:
        pytest.skip("recovered donor locator/interpreter not supplied")

    payload = {
        name: [{"numbers": list(row.numbers)} for row in history] for name, history in cases.items()
    }
    runner = r"""
import importlib.util
import json
import sys
import types

import numpy as np

donor_path = sys.argv[1]
tools_module = types.ModuleType("tools")
leaderboard_module = types.ModuleType("tools.strategy_leaderboard")
leaderboard_module.StrategyLeaderboard = object
sys.modules["tools"] = tools_module
sys.modules["tools.strategy_leaderboard"] = leaderboard_module
spec = importlib.util.spec_from_file_location("recovered_power_graph_synergy", donor_path)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

results = {}
original_graph = module.nx.Graph
for name, history in json.loads(sys.stdin.read()).items():
    captured = []
    class RecordingGraph(original_graph):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            captured.append(self)
    module.nx.Graph = RecordingGraph
    np.random.seed(42)
    communities = module.analyze_graph_communities(history, window=500)
    source_graph = captured[0]
    module.nx.Graph = original_graph
    np.random.seed(42)
    tickets = module.graph_clancy_predict(history, n_bets=2, window=500)
    results[name] = {
        "nodes": list(source_graph.nodes()),
        "edges": [
            [first, second, data["weight"]]
            for first, second, data in source_graph.edges(data=True)
        ],
        "communities": list(communities.values()),
        "tickets": tickets,
    }
print(json.dumps(results, sort_keys=True))
"""
    completed = subprocess.run(
        [donor_python, "-c", runner, donor_path],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        pytest.fail(f"recovered donor execution failed: {completed.stderr}")
    return cast(dict[str, _DonorResult], json.loads(completed.stdout))


def test_catalog_registry_and_historical_stochastic_authority_are_distinct() -> None:
    blocked = next(item for item in WAVE2_BLOCKED_STRATEGIES if item.strategy_id == DONOR_ID)
    assert "no random_state" in blocked.reason

    catalog = production_catalog()
    descriptor = catalog.get(STRATEGY_ID)
    assert sum(item.strategy_id == STRATEGY_ID for item in catalog) == 1
    assert descriptor.lifecycle_status is LifecycleStatus.ONLINE
    assert descriptor.executable is True
    assert descriptor.response_shape is ResponseShape.PORTFOLIO
    assert descriptor.native_ticket_count_bounds == (2, 2)
    assert descriptor.min_history == 1
    assert f"legacy_source_sha256:{DONOR_SHA256}" in descriptor.provenance
    assert "historical_donor_status:STOCHASTIC_BLOCKED_AUTHORITY_RETAINED" in (
        descriptor.provenance
    )
    assert "authorized_variant:CALL_LOCAL_DETERMINISTIC_LOUVAIN_SEED_42" in (descriptor.provenance)
    assert ExecutableRegistry(catalog).load_adapter(STRATEGY_ID) is (
        PowerLottoGraphSynergySeed42Adapter
    )


def test_recovered_donor_graph_community_ranking_and_tickets_match() -> None:
    cases = _representative_cases()
    expected = _run_recovered_donor(cases)

    for name, history in cases.items():
        graph = _build_cooccurrence_graph(history)
        donor = expected[name]
        assert graph.node_order() == tuple(donor["nodes"])
        assert graph.weighted_edges() == tuple(
            (first, second, weight) for first, second, weight in donor["edges"]
        )
        assert tuple(_analyze_graph_communities(history).values()) == tuple(
            tuple(community) for community in donor["communities"]
        )
        assert _graph_clancy_tickets(history) == tuple(tuple(ticket) for ticket in donor["tickets"])

    assert expected["pseudo_random_trailing_500"] == expected["repeated_same_history"]
    assert _graph_clancy_tickets(()) == (
        (1, 2, 3, 4, 5, 6),
        (1, 2, 3, 4, 5, 6),
    )


def test_repeatability_and_independence_from_unrelated_rng_consumption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = _representative_cases()["pseudo_random_trailing_500"]
    adapter = PowerLottoGraphSynergySeed42Adapter()

    class _UnrelatedNumpyRandom:
        consumed = 0

        def random(self, count: int) -> tuple[float, ...]:
            self.consumed += count
            return (0.5,) * count

    class _FakeNumpy(ModuleType):
        random: _UnrelatedNumpyRandom

    unrelated = _UnrelatedNumpyRandom()
    fake_numpy = _FakeNumpy("numpy")
    fake_numpy.random = unrelated
    monkeypatch.setitem(sys.modules, "numpy", fake_numpy)

    first = adapter.get_bets(history, LotteryType.POWER_LOTTO)
    random.seed(99991)
    for _ in range(1000):
        random.random()
    unrelated.random(1000)
    second = adapter.get_bets(history, LotteryType.POWER_LOTTO)
    third = PowerLottoGraphSynergySeed42Adapter().get_bets(
        history,
        LotteryType.POWER_LOTTO,
    )

    assert unrelated.consumed == 1000
    assert first == second == third
    assert PowerLottoGraphSynergySeed42Adapter.call_local_seed == 42


def test_adapter_boundary_shape_window_and_fail_closed_contract() -> None:
    adapter = PowerLottoGraphSynergySeed42Adapter()
    one_draw = _history([(1, 2, 3, 4, 5, 6)])
    executions = adapter.get_bets_with_emission(one_draw, LotteryType.POWER_LOTTO)
    assert tuple(item.legal_main_numbers for item in executions) == (
        (1, 2, 3, 4, 5, 6),
        (1, 2, 7, 8, 9, 10),
    )
    assert all(item.special_number is None for item in executions)

    valid_tail = _representative_cases()["pseudo_random_trailing_500"][-500:]
    invalid_ignored_prefix = CausalDrawRow(
        draw="outside-window",
        date="2025-01-01",
        numbers=(100, 101, 102, 103, 104, 105),
    )
    assert adapter.get_bets(
        (invalid_ignored_prefix, *valid_tail),
        LotteryType.POWER_LOTTO,
    ) == adapter.get_bets(valid_tail, LotteryType.POWER_LOTTO)

    with pytest.raises(InsufficientHistory):
        adapter.get_bets((), LotteryType.POWER_LOTTO)
    with pytest.raises(UnsupportedLotteryType):
        adapter.get_bets(one_draw, LotteryType.BIG_LOTTO)


def test_production_portfolio_executes_the_distinct_native_identity() -> None:
    history = _representative_cases()["ordinary"]
    use_case = build_production_generate_portfolio()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id=STRATEGY_ID,
            lottery_type=LotteryType.POWER_LOTTO,
            history=history,
        )
    )
    assert result.status is GeneratePortfolioStatus.OK
    assert result.numbers == PowerLottoGraphSynergySeed42Adapter().get_bets(
        history,
        LotteryType.POWER_LOTTO,
    )
