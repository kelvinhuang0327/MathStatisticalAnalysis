"""Donor parity and DB-free runtime tests for Smart Multi-Bet migration."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import random
import sqlite3
from typing import cast

import pytest

from lottolab.application.legacy_history_native_portfolios import LegacyHistoryDraw
from lottolab.application.legacy_source_native_portfolios_wave17 import (
    DEFAULT_SOURCE_NATIVE_WAVE17_USER_SEED,
    SMART_MULTI_BET_METHOD_ID,
    LegacySourceNativeWave17Request,
    _build_smart_multi_pool,
    generate_legacy_source_native_wave17_portfolio,
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
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import LifecycleStatus, ResponseShape
from lottolab.strategies.adapters import biglotto_smart_multi_bet as smart_multi_module
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_smart_multi_bet import (
    BigLottoSmartMultiBetAdapter,
    _build_candidate_pool,
    _seed_integer,
    _smart_multi_bet,
    _target_after_causal_cutoff,
)
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

STRATEGY_ID = "legacy_biglotto__smart_multi_bet__613c62c1f192"


def _history(count: int) -> tuple[CausalDrawRow, ...]:
    rows: list[CausalDrawRow] = []
    for index in range(count):
        values = sorted(((index * 7 + offset * 5) % 49) + 1 for offset in range(6))
        rows.append(
            CausalDrawRow(
                draw=str(index + 1),
                date=f"2020-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
                numbers=tuple(values),
            )
        )
    return tuple(rows)


def _legacy_history(
    history: tuple[CausalDrawRow, ...],
) -> tuple[LegacyHistoryDraw, ...]:
    return tuple(
        LegacyHistoryDraw(
            draw_number=row.draw,
            numbers=cast(Ticket, row.numbers),
        )
        for row in history
    )


def _donor_tickets(
    history: tuple[CausalDrawRow, ...],
) -> tuple[tuple[int, ...], ...]:
    target_history = history[-300:]
    return generate_legacy_source_native_wave17_portfolio(
        LegacySourceNativeWave17Request(
            legacy_method_id=SMART_MULTI_BET_METHOD_ID,
            target_draw_number=_target_after_causal_cutoff(target_history),
            history=_legacy_history(history),
            user_seed=DEFAULT_SOURCE_NATIVE_WAVE17_USER_SEED,
        )
    ).tickets


@pytest.mark.parametrize("history_length", (1, 20, 50, 300, 350))
def test_adapter_matches_preserved_exact_parity_oracle(
    history_length: int,
) -> None:
    history = _history(history_length)
    expected = _donor_tickets(history)
    actual = BigLottoSmartMultiBetAdapter().get_bets(
        history,
        LotteryType.BIG_LOTTO,
    )

    assert actual == expected
    assert len(actual) == 6
    assert all(
        len(ticket) == len(set(ticket)) == 6
        and tuple(sorted(ticket)) == ticket
        and all(1 <= number <= 49 for number in ticket)
        for ticket in actual
    )


@pytest.mark.parametrize("history_length", (1, 20, 50, 300, 350))
def test_candidate_pool_matches_preserved_donor_components(
    history_length: int,
) -> None:
    history = _history(history_length)

    assert _build_candidate_pool(history) == _build_smart_multi_pool(_legacy_history(history))


def test_authoritative_wave17_seed_preserves_known_exact_output() -> None:
    history = _history(350)
    rng = random.Random()
    rng.seed(_seed_integer(target_draw_number="351"), version=2)

    tickets, pool_counts = _smart_multi_bet(rng, history)

    assert tickets == (
        (5, 9, 12, 24, 32, 34),
        (14, 18, 26, 44, 46, 47),
        (2, 4, 7, 19, 43, 48),
        (5, 7, 10, 29, 36, 41),
        (1, 17, 21, 40, 43, 45),
        (9, 12, 20, 27, 34, 41),
    )
    assert pool_counts == (15, 15, 19, 42, 6, 0)


def test_same_causal_input_and_seed_is_deterministic() -> None:
    history = _history(120)
    seed = _seed_integer(target_draw_number="next", user_seed="determinism")
    first_rng = random.Random()
    second_rng = random.Random()
    first_rng.seed(seed, version=2)
    second_rng.seed(seed, version=2)

    assert _smart_multi_bet(first_rng, history) == _smart_multi_bet(
        second_rng,
        history,
    )


def test_adapter_consumes_only_latest_300_causal_draws() -> None:
    history = _history(350)
    replacement_prefix = tuple(
        CausalDrawRow(
            draw=f"replacement-{index}",
            date="1999-01-01",
            numbers=(1, 2, 3, 4, 5, 6),
        )
        for index in range(50)
    )
    replaced = replacement_prefix + history[50:]
    adapter = BigLottoSmartMultiBetAdapter()

    assert adapter.get_bets(history, LotteryType.BIG_LOTTO) == adapter.get_bets(
        replaced,
        LotteryType.BIG_LOTTO,
    )


def test_malformed_insufficient_and_unsupported_input_fail_closed() -> None:
    adapter = BigLottoSmartMultiBetAdapter()
    history = _history(2)

    with pytest.raises(InsufficientHistory):
        adapter.get_bets((), LotteryType.BIG_LOTTO)
    with pytest.raises(UnsupportedLotteryType):
        adapter.get_bets(history, LotteryType.POWER_LOTTO)
    with pytest.raises(InvalidOutput):
        adapter.get_bets("not-a-tuple", LotteryType.BIG_LOTTO)  # type: ignore[arg-type]
    with pytest.raises(InvalidOutput):
        adapter.get_bets(
            (CausalDrawRow("bad", "2020-01-01", (1, 2, 3, 4, 5, 99)),),
            LotteryType.BIG_LOTTO,
        )
    with pytest.raises(InvalidOutput, match="identities must be unique"):
        adapter.get_bets((history[0], history[0]), LotteryType.BIG_LOTTO)


def test_catalog_registry_and_generation_dispatch_preserve_portfolio() -> None:
    catalog = production_catalog()
    descriptor = catalog.get(STRATEGY_ID)
    adapter = BigLottoSmartMultiBetAdapter()

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
        6,
        (6, 6),
        "lottolab.strategies.adapters.biglotto_smart_multi_bet:BigLottoSmartMultiBetAdapter",
    )
    assert ExecutableRegistry(catalog).load_adapter(STRATEGY_ID) is (BigLottoSmartMultiBetAdapter)
    assert "runtime_boundary:CALLER_SUPPLIED_CAUSAL_HISTORY_NO_DB" in (descriptor.provenance)
    assert "live_db_required:NO" in descriptor.provenance
    assert "db_write:NONE" in descriptor.provenance

    history = _history(80)
    request = GenerateOneBetInput(
        strategy_id=STRATEGY_ID,
        lottery_type=LotteryType.BIG_LOTTO,
        history=history,
    )
    portfolio = build_production_generate_portfolio().execute(request)
    single = build_production_generate_one_bet().execute(request)

    assert portfolio.status is GeneratePortfolioStatus.OK
    assert portfolio.numbers == _donor_tickets(history)
    assert single.status is GenerateOneBetStatus.WRONG_RESPONSE_PATH
    assert single.reason_code is GenerateOneBetReason.STRATEGY_IS_PORTFOLIO
    assert single.numbers is None


def test_production_generation_never_opens_a_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _forbidden_connect(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Smart Multi-Bet must not open a database")

    monkeypatch.setattr(sqlite3, "connect", _forbidden_connect)
    history = _history(80)
    result = build_production_generate_portfolio().execute(
        GenerateOneBetInput(STRATEGY_ID, LotteryType.BIG_LOTTO, history)
    )

    assert result.status is GeneratePortfolioStatus.OK
    assert result.numbers == _donor_tickets(history)


def test_invalid_native_cardinality_has_no_silent_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _one_ticket(
        rng: random.Random,
        history: tuple[CausalDrawRow, ...],
    ) -> tuple[tuple[tuple[int, ...], ...], tuple[int, ...]]:
        del rng, history
        return ((1, 2, 3, 4, 5, 6),), ()

    monkeypatch.setattr(smart_multi_module, "_smart_multi_bet", _one_ticket)
    result = build_production_generate_portfolio().execute(
        GenerateOneBetInput(
            STRATEGY_ID,
            LotteryType.BIG_LOTTO,
            _history(20),
        )
    )

    assert result.status is GeneratePortfolioStatus.INVALID_OUTPUT
    assert result.reason_code is GeneratePortfolioReason.INVALID_OUTPUT
    assert result.numbers is None


def test_production_catalog_preserves_smart_multi_bet_append_position() -> None:
    strategy_ids = tuple(descriptor.strategy_id for descriptor in production_catalog())

    assert len(strategy_ids) == 118
    assert strategy_ids[-13] == STRATEGY_ID
    assert strategy_ids[:-13].count(STRATEGY_ID) == 0
    assert strategy_ids[-16:-13] == (
        "legacy_biglotto__concentrated_pool_predictor__a03b90705749",
        "legacy_biglotto__constraint_filter_predictor__3a85b3995002",
        "legacy_biglotto__predict_biglotto_apriori__cda690ae84c2",
    )
    assert strategy_ids[-12:-10] == (
        "legacy_biglotto__anti_consensus_strategy__a454ddd26cef",
        "legacy_biglotto__cooccurrence_graph__25fa2e473092",
    )
    assert strategy_ids[-10] == "legacy_biglotto__backtest_radical_strategy__e54cc0812bc6"
    assert strategy_ids[-9] == "legacy_biglotto__power_fourier_rhythm__cb75e72e4c94"
    assert strategy_ids[-8] == ("legacy_biglotto__backtest_big_lotto_orthogonal_5bet__c4dff46c5a5e")
    assert strategy_ids[-7] == "legacy_biglotto__predict_biglotto_quad_strike__e202e664208f"
    assert strategy_ids[-6] == "legacy_biglotto__frontend_markov_strategy__2fc1cafea55c"
    assert strategy_ids[-5] == "legacy_biglotto__orthogonal_2bet_optimizer__aa51b0e5e4a4"
    assert strategy_ids[-4] == "legacy_biglotto__frontend_trend_strategy__a5f4554c80ef"
    assert strategy_ids[-3] == "legacy_biglotto__frontend_bayesian_strategy__baa3045817fb"
    assert strategy_ids[-2] == "legacy_biglotto__biglotto_2bet_hedging__07a3aa455074"
    assert strategy_ids[-1] == "legacy_biglotto__frontend_frequency_strategy__2e3e8febb5f1"
