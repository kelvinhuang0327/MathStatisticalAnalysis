"""Donor parity and bounded-cardinality tests for native Apriori migration."""

from __future__ import annotations

import json
from datetime import date
from typing import cast

import pytest

from lottolab.application.historical_replay_adapters import (
    BigLottoReplayAdapter,
    ReplayStrategyBinding,
)
from lottolab.application.legacy_history_native_portfolios import LegacyHistoryDraw
from lottolab.application.legacy_source_native_portfolios_wave7 import (
    APRIORI_PREDICT_METHOD_ID,
    LegacySourceNativeWave7Request,
    generate_legacy_source_native_wave7_portfolio,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket
from lottolab.application.use_cases.generate_bet import (
    AdapterIdentityMismatchError,
    GenerateOneBetInput,
    GenerateOneBetReason,
    GenerateOneBetStatus,
    GeneratePortfolio,
    GeneratePortfolioReason,
    GeneratePortfolioStatus,
    build_production_generate_one_bet,
    build_production_generate_portfolio,
    run_cli_generate_portfolio,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayBehavior, ReplayDraw, ReplayStrategy
from lottolab.domain.strategies import LifecycleStatus, ResponseShape, StrategyDescriptor
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InvalidOutput,
    PortfolioBetAdapter,
)
from lottolab.strategies.adapters.biglotto_apriori import (
    BigLottoAprioriPredictorAdapter,
)
from lottolab.strategies.adapters.biglotto_concentrated_pool import (
    BigLottoConcentratedPoolPredictorAdapter,
)
from lottolab.strategies.adapters.biglotto_constraint_filter import (
    BigLottoConstraintFilterPredictorAdapter,
)
from lottolab.strategies.catalog import StrategyCatalog, production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

STRATEGY_ID = "legacy_biglotto__predict_biglotto_apriori__cda690ae84c2"


def _bounded_history(expected_count: int) -> tuple[CausalDrawRow, ...]:
    """Build only the repeated graph edges needed for 2..7 rule antecedents."""

    edges: list[tuple[int, int]] = []
    next_number = 1
    if expected_count % 2:
        edges.extend(((1, 2), (1, 3)))
        next_number = 4
        pair_count = (expected_count - 3) // 2
    else:
        pair_count = expected_count // 2
    for _ in range(pair_count):
        edges.append((next_number, next_number + 1))
        next_number += 2

    filler_stream = tuple(range(20, 50)) * 2
    rows: list[CausalDrawRow] = []
    filler_offset = 0
    for left, right in edges:
        for _ in range(3):
            fillers = filler_stream[filler_offset : filler_offset + 4]
            filler_offset += 4
            rows.append(
                CausalDrawRow(
                    draw=str(len(rows) + 1),
                    date=f"2020-01-{len(rows) + 1:02d}",
                    numbers=tuple(sorted((left, right, *fillers))),
                )
            )
    return tuple(rows)


def _donor_tickets(history: tuple[CausalDrawRow, ...]) -> tuple[Ticket, ...]:
    return generate_legacy_source_native_wave7_portfolio(
        LegacySourceNativeWave7Request(
            legacy_method_id=APRIORI_PREDICT_METHOD_ID,
            target_draw_number="parity-target",
            history=tuple(
                LegacyHistoryDraw(
                    draw_number=row.draw,
                    numbers=cast(Ticket, row.numbers),
                )
                for row in history
            ),
        )
    ).tickets


def _history_json(history: tuple[CausalDrawRow, ...]) -> str:
    return json.dumps(
        [{"draw": row.draw, "date": row.date, "numbers": list(row.numbers)} for row in history]
    )


def _bounded_descriptor() -> StrategyDescriptor:
    return StrategyDescriptor(
        strategy_id="fixture_bounded_portfolio",
        strategy_name="Fixture Bounded Portfolio",
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.OBSERVATION,
        executable=False,
        response_shape=ResponseShape.PORTFOLIO,
        native_ticket_count=7,
        minimum_native_ticket_count=2,
        maximum_native_ticket_count=7,
    )


class _BoundedOutputAdapter(PortfolioBetAdapter):
    strategy_id = "fixture_bounded_portfolio"
    strategy_name = "Fixture Bounded Portfolio"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 7
    minimum_native_ticket_count = 2
    maximum_native_ticket_count = 7

    def __init__(self, tickets: tuple[tuple[int, ...], ...]) -> None:
        self._tickets = tickets

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return self._tickets


@pytest.mark.parametrize("expected_count", range(2, 8))
def test_apriori_matches_preserved_donor_at_every_supported_cardinality(
    expected_count: int,
) -> None:
    history = _bounded_history(expected_count)
    expected = _donor_tickets(history)
    actual = BigLottoAprioriPredictorAdapter().get_bets(
        history,
        LotteryType.BIG_LOTTO,
    )

    assert len(expected) == expected_count
    assert actual == expected
    assert len(actual) == expected_count
    assert all(
        len(ticket) == 6
        and len(set(ticket)) == 6
        and tuple(sorted(ticket)) == ticket
        and all(1 <= number <= 49 for number in ticket)
        for ticket in actual
    )


def test_apriori_is_deterministic_and_uses_only_supplied_causal_prefix() -> None:
    adapter = BigLottoAprioriPredictorAdapter()
    causal_prefix = _bounded_history(5)
    future_suffix = _bounded_history(7)[len(causal_prefix) :]

    first = adapter.get_bets(causal_prefix, LotteryType.BIG_LOTTO)
    second = adapter.get_bets(causal_prefix, LotteryType.BIG_LOTTO)
    with_later_rows = adapter.get_bets(
        causal_prefix + future_suffix,
        LotteryType.BIG_LOTTO,
    )

    assert first == second == _donor_tickets(causal_prefix)
    assert with_later_rows == _donor_tickets(causal_prefix + future_suffix)


@pytest.mark.parametrize("ticket_count", (1, 8))
def test_bounded_portfolio_output_outside_declared_range_fails_closed(
    ticket_count: int,
) -> None:
    ticket = (1, 2, 3, 4, 5, 6)
    adapter = _BoundedOutputAdapter(tuple(ticket for _ in range(ticket_count)))
    use_case = GeneratePortfolio(
        StrategyCatalog((_bounded_descriptor(),)),
        {adapter.strategy_id: adapter},
    )
    request = GenerateOneBetInput(
        strategy_id=adapter.strategy_id,
        lottery_type=LotteryType.BIG_LOTTO,
        history=_bounded_history(2),
    )

    with pytest.raises(InvalidOutput, match="between 2 and 7"):
        adapter.get_bets(request.history, request.lottery_type)
    result = use_case.execute(request)
    assert result.status is GeneratePortfolioStatus.INVALID_OUTPUT
    assert result.reason_code is GeneratePortfolioReason.INVALID_OUTPUT
    assert result.numbers is None


@pytest.mark.parametrize("ticket_count", (2, 7))
def test_bounded_portfolio_accepts_both_declared_boundaries(ticket_count: int) -> None:
    ticket = (1, 2, 3, 4, 5, 6)
    adapter = _BoundedOutputAdapter(tuple(ticket for _ in range(ticket_count)))
    assert len(adapter.get_bets(_bounded_history(2), LotteryType.BIG_LOTTO)) == ticket_count


def test_bounded_portfolio_still_rejects_invalid_ticket_contents() -> None:
    adapter = _BoundedOutputAdapter(
        (
            (1, 2, 3, 4, 5, 50),
            (7, 8, 9, 10, 11, 12),
        )
    )
    with pytest.raises(InvalidOutput, match="out of range"):
        adapter.get_bets(_bounded_history(2), LotteryType.BIG_LOTTO)


def test_generate_portfolio_requires_matching_descriptor_bounds() -> None:
    exact_seven = StrategyDescriptor(
        strategy_id="fixture_bounded_portfolio",
        strategy_name="Fixture Bounded Portfolio",
        version="v0.1",
        lottery_types=(LotteryType.BIG_LOTTO,),
        lifecycle_status=LifecycleStatus.OBSERVATION,
        executable=False,
        response_shape=ResponseShape.PORTFOLIO,
        native_ticket_count=7,
    )
    adapter = _BoundedOutputAdapter(((1, 2, 3, 4, 5, 6),) * 2)
    with pytest.raises(AdapterIdentityMismatchError, match="does not match"):
        GeneratePortfolio(StrategyCatalog((exact_seven,)), {adapter.strategy_id: adapter})


def test_descriptor_rejects_unbounded_or_inconsistent_cardinality() -> None:
    with pytest.raises(ValueError, match="bounded minimum"):
        StrategyDescriptor(
            strategy_id="bad-min",
            strategy_name="bad-min",
            version="v0.1",
            lottery_types=(LotteryType.BIG_LOTTO,),
            lifecycle_status=LifecycleStatus.OBSERVATION,
            executable=False,
            response_shape=ResponseShape.PORTFOLIO,
            native_ticket_count=7,
            minimum_native_ticket_count=1,
            maximum_native_ticket_count=7,
        )
    with pytest.raises(ValueError, match="exceeds maximum"):
        StrategyDescriptor(
            strategy_id="bad-order",
            strategy_name="bad-order",
            version="v0.1",
            lottery_types=(LotteryType.BIG_LOTTO,),
            lifecycle_status=LifecycleStatus.OBSERVATION,
            executable=False,
            response_shape=ResponseShape.PORTFOLIO,
            native_ticket_count=7,
            minimum_native_ticket_count=8,
            maximum_native_ticket_count=7,
        )
    with pytest.raises(ValueError, match="bounded maximum"):
        StrategyDescriptor(
            strategy_id="bad-legacy-maximum",
            strategy_name="bad-legacy-maximum",
            version="v0.1",
            lottery_types=(LotteryType.BIG_LOTTO,),
            lifecycle_status=LifecycleStatus.OBSERVATION,
            executable=False,
            response_shape=ResponseShape.PORTFOLIO,
            native_ticket_count=6,
            minimum_native_ticket_count=2,
            maximum_native_ticket_count=7,
        )


def test_catalog_registry_and_production_paths_resolve_native_apriori() -> None:
    catalog = production_catalog()
    descriptor = catalog.get(STRATEGY_ID)
    adapter = BigLottoAprioriPredictorAdapter()

    assert (
        descriptor.strategy_id,
        descriptor.strategy_name,
        descriptor.version,
        descriptor.lottery_types,
        descriptor.lifecycle_status,
        descriptor.executable,
        descriptor.min_history,
        descriptor.response_shape,
        descriptor.native_ticket_count,
        descriptor.native_ticket_count_bounds,
        descriptor.adapter_path,
    ) == (
        adapter.strategy_id,
        adapter.strategy_name,
        adapter.strategy_version,
        (LotteryType.BIG_LOTTO,),
        LifecycleStatus.ONLINE,
        True,
        adapter.min_history,
        ResponseShape.PORTFOLIO,
        7,
        (2, 7),
        "lottolab.strategies.adapters.biglotto_apriori:BigLottoAprioriPredictorAdapter",
    )
    assert adapter.native_ticket_count_bounds() == (2, 7)
    assert ExecutableRegistry(catalog).load_adapter(STRATEGY_ID) is (
        BigLottoAprioriPredictorAdapter
    )
    assert descriptor.provenance[:4] == (
        "legacy_commit:49a25effa62fc24f40789c16be6f11bdfb41a4a9",
        "legacy_source:tools/predict_biglotto_apriori.py",
        "legacy_source_blob:53222aacf71474fb25487ea625e0e9519760a75a",
        "legacy_source_sha256:cda690ae84c2324b5f7d160a68e0ba3cf65d6073ecfc5c28ef48402b07018e7b",
    )

    history = _bounded_history(5)
    request = GenerateOneBetInput(STRATEGY_ID, LotteryType.BIG_LOTTO, history)
    portfolio = build_production_generate_portfolio().execute(request)
    single = build_production_generate_one_bet().execute(request)
    assert portfolio.status is GeneratePortfolioStatus.OK
    assert portfolio.numbers == _donor_tickets(history)
    assert single.status is GenerateOneBetStatus.WRONG_RESPONSE_PATH
    assert single.reason_code is GenerateOneBetReason.STRATEGY_IS_PORTFOLIO


def test_apriori_has_no_silent_fallback_when_rules_cannot_form_portfolio() -> None:
    history = (CausalDrawRow("1", "2020-01-01", (1, 2, 3, 4, 5, 6)),)
    request = GenerateOneBetInput(STRATEGY_ID, LotteryType.BIG_LOTTO, history)
    result = build_production_generate_portfolio().execute(request)
    assert result.status is GeneratePortfolioStatus.INVALID_OUTPUT
    assert result.reason_code is GeneratePortfolioReason.INVALID_OUTPUT
    assert result.numbers is None


def test_cli_serialization_preserves_order_and_is_deterministic() -> None:
    history = _bounded_history(6)
    first_text, first_ok = run_cli_generate_portfolio(
        strategy_id=STRATEGY_ID,
        seed=17,
        history_json=_history_json(history),
    )
    second_text, second_ok = run_cli_generate_portfolio(
        strategy_id=STRATEGY_ID,
        seed=17,
        history_json=_history_json(history),
    )

    assert first_ok and second_ok
    assert first_text == second_text
    payload = json.loads(first_text)
    assert payload["numbers"] == [list(ticket) for ticket in _donor_tickets(history)]
    assert payload["status"] == "OK"


def test_causal_replay_resolves_each_apriori_portfolio_count_without_schema_change() -> None:
    adapter = BigLottoAprioriPredictorAdapter()
    history_rows = _bounded_history(5)
    history = tuple(
        ReplayDraw(
            lottery_type=LotteryType.BIG_LOTTO,
            draw_number=row.draw,
            draw_date=date.fromisoformat(row.date),
            main_numbers=row.numbers,
            special_number=49,
        )
        for row in history_rows
    )
    target = ReplayDraw(
        lottery_type=LotteryType.BIG_LOTTO,
        draw_number="100",
        draw_date=date(2020, 2, 1),
        main_numbers=(7, 8, 9, 10, 11, 12),
        special_number=13,
    )
    strategy = ReplayStrategy(
        strategy_id=adapter.strategy_id,
        strategy_name=adapter.strategy_name,
        strategy_version=adapter.strategy_version,
        behavior=ReplayBehavior.DETERMINISTIC,
        native_ticket_count=adapter.native_ticket_count,
        min_history=adapter.min_history,
    )
    replay = BigLottoReplayAdapter((ReplayStrategyBinding(strategy, adapter),))

    expected_count = replay.expected_native_ticket_count(strategy, history, target)
    tickets = replay.generate(strategy, history, target)

    assert expected_count == 5
    assert len(tickets) == expected_count
    assert tuple(ticket.ticket_position for ticket in tickets) == (1, 2, 3, 4, 5)
    assert tuple(ticket.main_numbers for ticket in tickets) == _donor_tickets(history_rows)


def test_existing_native_mechanisms_remain_exact_two_and_executable() -> None:
    catalog = production_catalog()
    registry = ExecutableRegistry(catalog)
    expected = (
        (
            "legacy_biglotto__concentrated_pool_predictor__a03b90705749",
            BigLottoConcentratedPoolPredictorAdapter,
        ),
        (
            "legacy_biglotto__constraint_filter_predictor__3a85b3995002",
            BigLottoConstraintFilterPredictorAdapter,
        ),
    )
    for strategy_id, adapter_class in expected:
        descriptor = catalog.get(strategy_id)
        assert descriptor.native_ticket_count == 2
        assert descriptor.native_ticket_count_bounds == (2, 2)
        assert adapter_class.native_ticket_count_bounds() == (2, 2)
        assert registry.load_adapter(strategy_id) is adapter_class
