"""Mechanism-component parity for native Cooccurrence Graph migration."""

# pyright: reportPrivateUsage=false
# Differential acceptance intentionally exercises retained/target components.

from __future__ import annotations

import json
import random
from collections.abc import Sequence
from datetime import date, timedelta
from typing import cast

import pytest

import lottolab.strategies.adapters.biglotto_cooccurrence_graph as graph_module
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
    LegacyNumpyRandomState,
)
from lottolab.application.legacy_history_native_portfolios_wave2 import (
    _cooccurrence_graph as retained_cooccurrence_graph,
)
from lottolab.application.legacy_history_native_portfolios_wave2 import (
    _CooccurrenceGraph as RetainedCooccurrenceGraph,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket
from lottolab.application.use_cases.generate_bet import (
    GenerateOneBetInput,
    GenerateOneBetReason,
    GenerateOneBetStatus,
    GeneratePortfolioReason,
    GeneratePortfolioStatus,
    build_production_generate_one_bet,
    build_production_generate_portfolio,
    run_cli_generate_portfolio,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    load_full_strategy_catalog,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayBehavior, ReplayDraw, ReplayStrategy
from lottolab.domain.strategies import LifecycleStatus, ResponseShape
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_cooccurrence_graph import (
    BigLottoCooccurrenceGraphAdapter,
)
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

STRATEGY_ID = "legacy_biglotto__cooccurrence_graph__25fa2e473092"
SOURCE_SHA256 = "25fa2e47309232265f442a688ddc1de2bbd853ce6c63762a5298aef016c008ab"


def _history(count: int = 120, *, seed: int = 20260728) -> tuple[CausalDrawRow, ...]:
    rng = random.Random(seed)
    return tuple(
        CausalDrawRow(
            draw=str(index + 1),
            date=f"2026-{index % 12 + 1:02d}-{index % 28 + 1:02d}",
            numbers=tuple(sorted(rng.sample(range(1, 50), 6))),
        )
        for index in range(count)
    )


def _symmetric_history() -> tuple[CausalDrawRow, ...]:
    return tuple(
        CausalDrawRow(
            draw=str(index + 1),
            date=f"2026-{index % 12 + 1:02d}-{index % 28 + 1:02d}",
            numbers=(1, 2, 3, 4, 5, 6),
        )
        for index in range(100)
    )


def _retained_history(
    history: tuple[CausalDrawRow, ...],
) -> tuple[LegacyHistoryDraw, ...]:
    return tuple(
        LegacyHistoryDraw(
            draw_number=row.draw,
            numbers=cast(Ticket, row.numbers),
        )
        for row in history
    )


def _history_json(history: tuple[CausalDrawRow, ...]) -> str:
    return json.dumps(
        [{"draw": row.draw, "date": row.date, "numbers": list(row.numbers)} for row in history]
    )


class _RecordingWeightedRng:
    def __init__(self, seed: int) -> None:
        self._delegate = graph_module._LegacyWeightedNumpyRandomState(seed)
        self.calls: list[tuple[tuple[int, ...], int, tuple[float, ...] | None]] = []

    def choice_without_replacement(
        self,
        values: list[int],
        size: int,
        *,
        probabilities: list[float] | None = None,
    ) -> list[int]:
        self.calls.append(
            (
                tuple(values),
                size,
                None if probabilities is None else tuple(probabilities),
            )
        )
        return self._delegate.choice_without_replacement(
            values,
            size,
            probabilities=probabilities,
        )


class _RecordingPythonRng:
    def __init__(self, seed: int) -> None:
        self._delegate = random.Random()
        self._delegate.seed(seed, version=2)
        self.calls: list[tuple[tuple[int, ...], int]] = []

    def sample(self, population: Sequence[int], k: int) -> list[int]:
        self.calls.append((tuple(population), k))
        return self._delegate.sample(population, k)


class _ExplodingPythonRng:
    def sample(self, population: Sequence[int], k: int) -> list[int]:
        del population, k
        raise AssertionError("CPython fallback must not run")


class _ExplodingWeightedRng:
    def choice_without_replacement(
        self,
        values: list[int],
        size: int,
        *,
        probabilities: list[float] | None = None,
    ) -> list[int]:
        del values, size, probabilities
        raise AssertionError("weighted fallback must not run")


class _ScriptedWeightedRng:
    def __init__(self, scripts: tuple[tuple[int, ...], ...]) -> None:
        self._scripts = iter(scripts)

    def choice_without_replacement(
        self,
        values: list[int],
        size: int,
        *,
        probabilities: list[float] | None = None,
    ) -> list[int]:
        del probabilities
        indices = next(self._scripts)
        assert len(indices) == size
        return [values[index] for index in indices]


def test_authoritative_identity_is_unique_cataloged_bounded_portfolio() -> None:
    retained = next(
        record
        for record in load_full_strategy_catalog().records
        if record.strategy_id == STRATEGY_ID
    )
    assert retained.legacy_method_id == "lottery_api/models/cooccurrence_graph.py"
    assert retained.source_blob_id == "69a7a0c903a025b4df67eaec927ecd09168e7e49"
    assert retained.source_sha256 == SOURCE_SHA256
    assert retained.method_family == "neighbor"
    assert retained.native_ticket_semantics == (
        "FROZEN_HISTORY_NATIVE_SOURCE_SOURCE_ORDER_UP_TO_4_UNIQUE"
    )

    catalog = production_catalog()
    descriptor = catalog.get(STRATEGY_ID)
    assert sum(item.strategy_id == STRATEGY_ID for item in catalog) == 1
    assert descriptor.lifecycle_status is LifecycleStatus.ONLINE
    assert descriptor.executable is True
    assert descriptor.response_shape is ResponseShape.PORTFOLIO
    assert descriptor.native_ticket_count_bounds == (1, 4)
    assert descriptor.min_history == 100
    assert f"legacy_source_sha256:{SOURCE_SHA256}" in descriptor.provenance
    assert "rng_authority:HISTORICAL_RNG_STATE_ONLY_MISSING" in descriptor.provenance
    assert "donor_parity:MECHANISM_COMPONENT_PARITY" in descriptor.provenance

    registry = ExecutableRegistry(catalog)
    assert registry.load_adapter(STRATEGY_ID) is BigLottoCooccurrenceGraphAdapter


@pytest.mark.parametrize("history_count", (100, 120, 300))
def test_graph_nodes_edges_weights_rankings_and_communities_match_retained(
    history_count: int,
) -> None:
    history = _history(history_count)
    target = graph_module._CooccurrenceGraph()
    target.build(history)
    retained = RetainedCooccurrenceGraph()
    retained.build(_retained_history(history))

    assert dict(target.edges) == dict(retained.edges)
    assert {number for edge in target.edges for number in edge} == {
        number for edge in retained.edges for number in edge
    }
    assert target.degree_centrality() == retained.degree_centrality()
    assert target.pagerank() == retained.pagerank()
    assert target.communities() == retained.communities()
    assert [target.neighbors(number) for number in range(1, 50)] == [
        retained.neighbors(number) for number in range(1, 50)
    ]


@pytest.mark.parametrize("seed", (0, 42, 2**32 - 1))
def test_weighted_numpy_random_state_operations_match_retained(seed: int) -> None:
    target = graph_module._LegacyWeightedNumpyRandomState(seed)
    retained = LegacyNumpyRandomState(seed)
    values = list(range(1, 21))
    probabilities = [float(index) for index in values]
    total = sum(probabilities)
    normalized = [value / total for value in probabilities]

    for _ in range(3):
        assert target.choice_without_replacement(
            values,
            6,
            probabilities=normalized,
        ) == retained.choice_without_replacement(
            values,
            6,
            probabilities=normalized,
        )


@pytest.mark.parametrize("history_count", (100, 120, 300))
@pytest.mark.parametrize("seed", (0, 42, 2**32 - 1))
def test_explicit_seed_matches_retained_complete_mechanism(
    history_count: int,
    seed: int,
) -> None:
    history = _history(history_count)
    expected = retained_cooccurrence_graph(_retained_history(history), seed)
    actual = BigLottoCooccurrenceGraphAdapter(rng_seed=seed).get_bets(
        history,
        LotteryType.BIG_LOTTO,
    )

    assert actual == expected
    assert 1 <= len(actual) <= 4
    assert len(actual) == len(set(actual))
    assert all(
        len(ticket) == 6
        and len(set(ticket)) == 6
        and ticket == tuple(sorted(ticket))
        and all(1 <= number <= 49 for number in ticket)
        for ticket in actual
    )


def test_weighted_fallback_population_distribution_and_call_order_are_exact() -> None:
    history = _history(100)
    graph = graph_module._CooccurrenceGraph()
    graph.build(history)
    native_candidates, page_rank = graph_module._native_graph_candidates(graph)
    candidates = tuple(
        number
        for number, _score in sorted(
            page_rank.items(),
            key=lambda item: -item[1],
        )[:20]
    )
    total = sum(page_rank[number] for number in candidates)
    probabilities = tuple(page_rank[number] / total for number in candidates)
    numpy_rng = _RecordingWeightedRng(20260820)

    tickets = graph_module._cooccurrence_graph_tickets(
        history,
        numpy_rng,
        _ExplodingPythonRng(),
    )

    assert len(native_candidates) == 2
    assert len(tickets) == 4
    assert numpy_rng.calls == [
        (candidates, 6, probabilities),
        (candidates, 6, probabilities),
    ]
    assert len(tickets) == len(set(tickets))


@pytest.mark.parametrize(
    ("scripts", "expected_count"),
    (
        (((0, 1, 2, 3, 4, 5),), 2),
        (((0, 1, 2, 3, 4, 6), (0, 1, 2, 3, 4, 6)), 3),
        (((0, 1, 2, 3, 4, 6), (0, 1, 2, 3, 4, 7)), 4),
    ),
)
def test_duplicate_stop_preserves_best_effort_two_to_four_cardinality(
    scripts: tuple[tuple[int, ...], ...],
    expected_count: int,
) -> None:
    tickets = graph_module._cooccurrence_graph_tickets(
        _history(100),
        _ScriptedWeightedRng(scripts),
        _ExplodingPythonRng(),
    )

    assert len(tickets) == expected_count
    assert len(tickets) == len(set(tickets))


def test_duplicate_stop_preserves_one_ticket_native_closure() -> None:
    history = _symmetric_history()
    expected = ((1, 2, 3, 4, 5, 6),)

    assert retained_cooccurrence_graph(_retained_history(history), 42) == expected
    assert (
        BigLottoCooccurrenceGraphAdapter(rng_seed=42).get_bets(
            history,
            LotteryType.BIG_LOTTO,
        )
        == expected
    )


def test_replay_count_seam_resolves_the_same_seeded_best_effort_count() -> None:
    replay_history = tuple(
        ReplayDraw(
            lottery_type=LotteryType.BIG_LOTTO,
            draw_number=row.draw,
            draw_date=date(2026, 1, 1) + timedelta(days=index),
            main_numbers=row.numbers,
        )
        for index, row in enumerate(_symmetric_history())
    )
    strategy = ReplayStrategy(
        strategy_id=STRATEGY_ID,
        strategy_name="Cooccurrence Graph",
        strategy_version="v0.1",
        behavior=ReplayBehavior.SEEDED_STOCHASTIC,
        native_ticket_count=4,
        min_history=100,
        seed_contract="target-local explicit MT19937 seed",
    )
    target = ReplayDraw(
        lottery_type=LotteryType.BIG_LOTTO,
        draw_number="101",
        draw_date=date(2026, 4, 11),
        main_numbers=(7, 8, 9, 10, 11, 12),
    )

    assert (
        BigLottoCooccurrenceGraphAdapter(rng_seed=42).expected_native_ticket_count(
            strategy,
            replay_history,
            target,
        )
        == 1
    )


def test_empty_graph_python_fallback_call_order_matches_retained_component() -> None:
    seed = 7919
    python_rng = _RecordingPythonRng(seed)

    actual = graph_module._cooccurrence_graph_tickets(
        (),
        _ExplodingWeightedRng(),
        python_rng,
    )

    assert actual == retained_cooccurrence_graph((), seed)
    assert python_rng.calls == [
        (tuple(range(1, 50)), 6),
        (tuple(range(1, 50)), 6),
        (tuple(range(1, 50)), 6),
        (tuple(range(1, 50)), 6),
    ]


def test_same_seed_is_deterministic_isolated_and_window_causal() -> None:
    history = _history(130)
    adapter = BigLottoCooccurrenceGraphAdapter(rng_seed=104729)
    first = adapter.get_bets(history, LotteryType.BIG_LOTTO)
    interleaved = BigLottoCooccurrenceGraphAdapter(rng_seed=7919).get_bets(
        history,
        LotteryType.BIG_LOTTO,
    )
    repeated = adapter.get_bets(history, LotteryType.BIG_LOTTO)
    changed_outside_window = tuple(
        CausalDrawRow(row.draw, row.date, (44, 45, 46, 47, 48, 49)) if index < 30 else row
        for index, row in enumerate(history)
    )

    assert first == repeated
    assert interleaved != first
    assert (
        adapter.with_seed(104729).get_bets(
            changed_outside_window,
            LotteryType.BIG_LOTTO,
        )
        == first
    )


def test_malformed_insufficient_and_unsupported_inputs_fail_closed() -> None:
    adapter = BigLottoCooccurrenceGraphAdapter()
    with pytest.raises(InsufficientHistory):
        adapter.get_bets(_history(99), LotteryType.BIG_LOTTO)
    with pytest.raises(InvalidOutput):
        adapter.get_bets(list(_history(100)), LotteryType.BIG_LOTTO)
    duplicate_identity = list(_history(100))
    duplicate_identity[-1] = CausalDrawRow(
        duplicate_identity[0].draw,
        duplicate_identity[-1].date,
        duplicate_identity[-1].numbers,
    )
    with pytest.raises(InvalidOutput, match="identities must be unique"):
        adapter.get_bets(tuple(duplicate_identity), LotteryType.BIG_LOTTO)
    with pytest.raises(UnsupportedLotteryType):
        adapter.get_bets(_history(100), LotteryType.DAILY_539)
    for invalid_seed in (-1, True, 2**32):
        with pytest.raises(InvalidOutput):
            BigLottoCooccurrenceGraphAdapter(rng_seed=invalid_seed)


def test_production_generation_requires_seed_and_preserves_one_to_four_tickets() -> None:
    portfolio = build_production_generate_portfolio()
    history = _history(120)
    request = GenerateOneBetInput(
        strategy_id=STRATEGY_ID,
        lottery_type=LotteryType.BIG_LOTTO,
        history=history,
        seed=37,
    )

    first = portfolio.execute(request)
    second = portfolio.execute(request)
    changed_seed = portfolio.execute(
        GenerateOneBetInput(
            strategy_id=STRATEGY_ID,
            lottery_type=LotteryType.BIG_LOTTO,
            history=history,
            seed=38,
        )
    )
    one_ticket = portfolio.execute(
        GenerateOneBetInput(
            strategy_id=STRATEGY_ID,
            lottery_type=LotteryType.BIG_LOTTO,
            history=_symmetric_history(),
            seed=37,
        )
    )
    missing_seed = portfolio.execute(
        GenerateOneBetInput(
            strategy_id=STRATEGY_ID,
            lottery_type=LotteryType.BIG_LOTTO,
            history=history,
        )
    )
    wrong_path = build_production_generate_one_bet().execute(request)

    assert first.status is GeneratePortfolioStatus.OK
    assert first.numbers is not None and 1 <= len(first.numbers) <= 4
    assert second == first
    assert changed_seed.status is GeneratePortfolioStatus.OK
    assert changed_seed.numbers != first.numbers
    assert one_ticket.status is GeneratePortfolioStatus.OK
    assert one_ticket.numbers == ((1, 2, 3, 4, 5, 6),)
    assert missing_seed.status is GeneratePortfolioStatus.INVALID_OUTPUT
    assert missing_seed.reason_code is GeneratePortfolioReason.INVALID_OUTPUT
    assert wrong_path.status is GenerateOneBetStatus.WRONG_RESPONSE_PATH
    assert wrong_path.reason_code is GenerateOneBetReason.STRATEGY_IS_PORTFOLIO


def test_cli_generation_uses_explicit_seed_without_claiming_historical_replay() -> None:
    history_json = _history_json(_history(100))
    first_text, first_ok = run_cli_generate_portfolio(
        strategy_id=STRATEGY_ID,
        seed=1234,
        history_json=history_json,
    )
    second_text, second_ok = run_cli_generate_portfolio(
        strategy_id=STRATEGY_ID,
        seed=1234,
        history_json=history_json,
    )
    changed_text, changed_ok = run_cli_generate_portfolio(
        strategy_id=STRATEGY_ID,
        seed=1235,
        history_json=history_json,
    )
    first = json.loads(first_text)
    second = json.loads(second_text)
    changed = json.loads(changed_text)

    assert first_ok is second_ok is changed_ok is True
    assert first["status"] == "OK"
    assert first["seed"] == 1234
    assert 1 <= len(first["numbers"]) <= 4
    assert second["numbers"] == first["numbers"]
    assert changed["numbers"] != first["numbers"]


def test_rng_failure_has_no_alternate_strategy_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _ExplodingRng:
        def __init__(self, _seed: int) -> None:
            pass

        def choice_without_replacement(
            self,
            values: list[int],
            size: int,
            *,
            probabilities: list[float] | None = None,
        ) -> list[int]:
            del values, size, probabilities
            raise RuntimeError("rng unavailable")

    monkeypatch.setattr(
        graph_module,
        "_LegacyWeightedNumpyRandomState",
        _ExplodingRng,
    )
    history = _history(100)

    with pytest.raises(RuntimeError, match="rng unavailable"):
        BigLottoCooccurrenceGraphAdapter(rng_seed=7).get_bets(
            history,
            LotteryType.BIG_LOTTO,
        )
    result = build_production_generate_portfolio().execute(
        GenerateOneBetInput(
            strategy_id=STRATEGY_ID,
            lottery_type=LotteryType.BIG_LOTTO,
            history=history,
            seed=7,
        )
    )
    assert result.status is GeneratePortfolioStatus.REPLAY_ERROR
    assert result.reason_code is GeneratePortfolioReason.REPLAY_ERROR
    assert result.numbers is None
