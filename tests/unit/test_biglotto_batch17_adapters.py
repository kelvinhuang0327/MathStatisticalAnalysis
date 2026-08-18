"""Parity and contract tests for the BigLotto native-strategy batch 17
adapters (Base Method Universe Batch03 intake: predict_biglotto_triple_strike,
backtest_sum_constraint, backtest_biglotto_markov_4bet,
backtest_biglotto_hot_stop_rebound).

Scope note: mirrors ``test_biglotto_batch16_adapters.py``'s bounded-fixture
acceptance level (structural/contract properties plus targeted load-bearing
checks, not exhaustive golden fixtures) appropriate to this intake task. Two
differences from that suite, both because none of these four donors touch
any RNG at all (see the adapter module's own RNG/seed contract note): there
is no "global random state is unchanged" test here (nothing seeds or reads
``random``), and window-boundary ("only reads its declared window") checks
are limited to the cheaper 100-draw windows (cold/tail/frequency) -- a
dedicated boundary test for the 500-draw Fourier window would require >=501
draws and would re-run the O(window^2) hand-rolled DFT at that scale several
times over, for coverage the cheaper windows and the general determinism/
legal-output tests already exercise the same code path for (just at a
smaller, history-capped window).
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import builtins
import socket
import time

import pytest

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
from lottolab.domain.strategies import ResponseShape
from lottolab.strategies.adapters.base import (
    BetAdapter,
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    PortfolioBetAdapter,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_batch17 import (
    BigLottoBacktestBiglottoHotStopReboundAdapter,
    BigLottoBacktestBiglottoMarkov4BetAdapter,
    BigLottoBacktestSumConstraintAdapter,
    BigLottoPredictBiglottoTripleStrikeAdapter,
    _hsr_get_hot_stop_candidates,
    _markov4_orthogonal_bet,
    _sumc_generate_ts_sum_constrained,
    _ts_cold_numbers_bet,
    _ts_generate_triple_strike,
    _ts_tail_balance_bet,
)
from lottolab.strategies.catalog import production_catalog

BATCH17_IDS = {
    "legacy_biglotto__predict_biglotto_triple_strike__dad1c50d1504",
    "legacy_biglotto__backtest_sum_constraint__acb3b118300d",
    "legacy_biglotto__backtest_biglotto_markov_4bet__aefb54eb345b",
    "legacy_biglotto__backtest_biglotto_hot_stop_rebound__1794a8c507ae",
}

PORTFOLIO_ADAPTER_CLASSES = (
    BigLottoPredictBiglottoTripleStrikeAdapter,
    BigLottoBacktestSumConstraintAdapter,
    BigLottoBacktestBiglottoMarkov4BetAdapter,
)

_MIN_HISTORY_BY_PORTFOLIO_CLASS: dict[type[PortfolioBetAdapter], int] = {
    BigLottoPredictBiglottoTripleStrikeAdapter: 150,
    BigLottoBacktestSumConstraintAdapter: 150,
    BigLottoBacktestBiglottoMarkov4BetAdapter: 150,
}

_HSR_MIN_HISTORY = 200


def _row(index: int, *, prefix: str = "b17") -> CausalDrawRow:
    """Deterministic 6-of-49 draw. Stride 8 is coprime with 49, so six
    consecutive steps always land on six distinct residues -- the same
    generator style as waves 4/11/12/13/14's and batch 16's own fixtures."""

    numbers = tuple(sorted(((index + step * 8) % 49) + 1 for step in range(6)))
    assert len(set(numbers)) == 6
    return CausalDrawRow(
        draw=f"{prefix}-{index:05d}",
        date=f"2020-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
        numbers=numbers,
    )


def _history(n: int) -> tuple[CausalDrawRow, ...]:
    return tuple(_row(i) for i in range(n))


def _assert_legal_ticket(ticket: tuple[int, ...]) -> None:
    assert len(ticket) == 6
    assert len(set(ticket)) == 6
    assert all(1 <= n <= 49 for n in ticket)
    assert ticket == tuple(sorted(ticket))


def _assert_legal_portfolio(bets: tuple[tuple[int, ...], ...]) -> None:
    for bet in bets:
        _assert_legal_ticket(bet)


# ─── legal output / determinism / boundary contract, all three portfolios ──


@pytest.mark.parametrize("adapter_class", PORTFOLIO_ADAPTER_CLASSES)
def test_batch17_portfolio_rejects_insufficient_history(
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    min_history = _MIN_HISTORY_BY_PORTFOLIO_CLASS[adapter_class]
    short_history = _history(min_history - 1)
    with pytest.raises(InsufficientHistory):
        adapter_class().get_bets(short_history, LotteryType.BIG_LOTTO)


@pytest.mark.parametrize("adapter_class", PORTFOLIO_ADAPTER_CLASSES)
def test_batch17_portfolio_rejects_wrong_lottery_type(
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    history = _history(_MIN_HISTORY_BY_PORTFOLIO_CLASS[adapter_class])
    with pytest.raises(UnsupportedLotteryType):
        adapter_class().get_bets(history, LotteryType.POWER_LOTTO)


def test_hot_stop_rebound_rejects_insufficient_history() -> None:
    short_history = _history(_HSR_MIN_HISTORY - 1)
    with pytest.raises(InsufficientHistory):
        BigLottoBacktestBiglottoHotStopReboundAdapter().get_one_bet(
            short_history, LotteryType.BIG_LOTTO
        )


def test_hot_stop_rebound_rejects_wrong_lottery_type() -> None:
    history = _history(_HSR_MIN_HISTORY)
    with pytest.raises(UnsupportedLotteryType):
        BigLottoBacktestBiglottoHotStopReboundAdapter().get_one_bet(
            history, LotteryType.POWER_LOTTO
        )


# ─── legal / deterministic / fixed-count / zero-overlap-by-construction ────


def test_triple_strike_legal_deterministic_fixed_count_and_zero_overlap() -> None:
    history = _history(200)
    adapter = BigLottoPredictBiglottoTripleStrikeAdapter()
    first = adapter.get_bets(history, LotteryType.BIG_LOTTO)
    second = adapter.get_bets(history, LotteryType.BIG_LOTTO)
    assert first == second
    assert len(first) == 3
    _assert_legal_portfolio(first)
    all_numbers = [n for bet in first for n in bet]
    assert len(all_numbers) == len(set(all_numbers)) == 18


def test_sum_constraint_legal_deterministic_fixed_count_and_zero_overlap() -> None:
    history = _history(200)
    adapter = BigLottoBacktestSumConstraintAdapter()
    first = adapter.get_bets(history, LotteryType.BIG_LOTTO)
    second = adapter.get_bets(history, LotteryType.BIG_LOTTO)
    assert first == second
    assert len(first) == 3
    _assert_legal_portfolio(first)
    all_numbers = [n for bet in first for n in bet]
    assert len(all_numbers) == len(set(all_numbers)) == 18


def test_markov4_legal_deterministic_fixed_count_and_zero_overlap() -> None:
    history = _history(200)
    adapter = BigLottoBacktestBiglottoMarkov4BetAdapter()
    first = adapter.get_bets(history, LotteryType.BIG_LOTTO)
    second = adapter.get_bets(history, LotteryType.BIG_LOTTO)
    assert first == second
    assert len(first) == 4
    _assert_legal_portfolio(first)
    all_numbers = [n for bet in first for n in bet]
    assert len(all_numbers) == len(set(all_numbers)) == 24


def test_markov4_first_three_bets_match_triple_strike_on_identical_history() -> None:
    """The two donor files embed byte-identical Triple-Strike logic (see the
    module docstring's PHASE_0 SEQUENCING NOTE) -- their first three bets
    must agree exactly given the same causal history."""

    history = _history(200)
    ts3 = BigLottoPredictBiglottoTripleStrikeAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    ts3_markov4 = BigLottoBacktestBiglottoMarkov4BetAdapter().get_bets(
        history, LotteryType.BIG_LOTTO
    )
    assert ts3_markov4[:3] == ts3


def test_hot_stop_rebound_legal_and_deterministic() -> None:
    history = _history(250)
    adapter = BigLottoBacktestBiglottoHotStopReboundAdapter()
    first, special1 = adapter.get_one_bet(history, LotteryType.BIG_LOTTO)
    second, special2 = adapter.get_one_bet(history, LotteryType.BIG_LOTTO)
    assert first == second
    assert special1 is None
    assert special2 is None
    _assert_legal_ticket(first)


# ─── causal window-boundary contract (cheap 100-draw windows only) ─────────


def test_ts_cold_numbers_bet_only_reads_its_declared_window() -> None:
    window_history = _history(100)
    padded_history = (_row(-1, prefix="older"), *window_history)
    bets_a = _ts_cold_numbers_bet(window_history, window=100)
    bets_b = _ts_cold_numbers_bet(padded_history, window=100)
    assert bets_a == bets_b


def test_ts_tail_balance_bet_only_reads_its_declared_window() -> None:
    window_history = _history(100)
    padded_history = (_row(-1, prefix="older"), *window_history)
    bets_a = _ts_tail_balance_bet(window_history, window=100)
    bets_b = _ts_tail_balance_bet(padded_history, window=100)
    assert bets_a == bets_b


def test_hot_stop_rebound_only_reads_its_declared_freq_window() -> None:
    window_history = _history(100)
    padded_history = (_row(-1, prefix="older"), *window_history)
    candidates_a, gaps_a, freqs_a = _hsr_get_hot_stop_candidates(window_history)
    candidates_b, gaps_b, freqs_b = _hsr_get_hot_stop_candidates(padded_history)
    assert candidates_a == candidates_b
    assert freqs_a == freqs_b
    assert gaps_a == gaps_b


# ─── no filesystem / clock / network access ────────────────────────────────


def test_batch17_adapters_need_no_filesystem_clock_or_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("external state access is forbidden")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(time, "time", forbidden)
    monkeypatch.setattr(time, "monotonic", forbidden)

    BigLottoPredictBiglottoTripleStrikeAdapter().get_bets(_history(150), LotteryType.BIG_LOTTO)
    BigLottoBacktestSumConstraintAdapter().get_bets(_history(150), LotteryType.BIG_LOTTO)
    BigLottoBacktestBiglottoMarkov4BetAdapter().get_bets(_history(150), LotteryType.BIG_LOTTO)
    BigLottoBacktestBiglottoHotStopReboundAdapter().get_one_bet(
        _history(200), LotteryType.BIG_LOTTO
    )


# ─── load-bearing internal helper checks ───────────────────────────────────


def test_ts_fourier_rhythm_bet_is_load_bearing(monkeypatch: pytest.MonkeyPatch) -> None:
    import lottolab.strategies.adapters.biglotto_batch17 as module

    history = _history(200)
    baseline = BigLottoPredictBiglottoTripleStrikeAdapter().get_bets(history, LotteryType.BIG_LOTTO)

    def _stub(_history: object, window: int = 500) -> list[int]:
        return [1, 2, 3, 4, 5, 6]

    monkeypatch.setattr(module, "_ts_fourier_rhythm_bet", _stub)
    mutated = BigLottoPredictBiglottoTripleStrikeAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert mutated != baseline
    assert mutated[0] == (1, 2, 3, 4, 5, 6)


def test_sumc_sum_select_from_pool_is_load_bearing(monkeypatch: pytest.MonkeyPatch) -> None:
    import lottolab.strategies.adapters.biglotto_batch17 as module

    history = _history(200)
    baseline = BigLottoBacktestSumConstraintAdapter().get_bets(history, LotteryType.BIG_LOTTO)

    def _stub(pool: list[int], target_low: float, target_high: float, n: int = 6) -> list[int]:
        return sorted(pool[:n])

    monkeypatch.setattr(module, "_sumc_sum_select_from_pool", _stub)
    mutated = BigLottoBacktestSumConstraintAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert mutated != baseline


def test_markov4_orthogonal_bet_is_load_bearing(monkeypatch: pytest.MonkeyPatch) -> None:
    import lottolab.strategies.adapters.biglotto_batch17 as module

    history = _history(200)
    baseline = BigLottoBacktestBiglottoMarkov4BetAdapter().get_bets(history, LotteryType.BIG_LOTTO)

    def _stub(
        _history: object, *, exclude: frozenset[int] | None = None, markov_window: int = 100
    ) -> list[int]:
        used = exclude or frozenset()
        fallback = [n for n in range(1, 50) if n not in used]
        return sorted(fallback[:6])

    monkeypatch.setattr(module, "_markov4_orthogonal_bet", _stub)
    mutated = BigLottoBacktestBiglottoMarkov4BetAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert mutated[:3] == baseline[:3]
    assert mutated[3] != baseline[3]


def test_hsr_candidates_are_load_bearing(monkeypatch: pytest.MonkeyPatch) -> None:
    import lottolab.strategies.adapters.biglotto_batch17 as module

    history = _history(250)
    baseline, _ = BigLottoBacktestBiglottoHotStopReboundAdapter().get_one_bet(
        history, LotteryType.BIG_LOTTO
    )

    def _no_candidates(
        _history: object,
        *,
        freq_threshold: int = 15,
        gap_threshold: int = 10,
        freq_window: int = 100,
        gap_window: int = 10,
    ) -> tuple[list[tuple[int, int]], dict[int, int], dict[int, int]]:
        return [], dict.fromkeys(range(1, 50), 0), dict.fromkeys(range(1, 50), 0)

    monkeypatch.setattr(module, "_hsr_get_hot_stop_candidates", _no_candidates)
    mutated, _ = BigLottoBacktestBiglottoHotStopReboundAdapter().get_one_bet(
        history, LotteryType.BIG_LOTTO
    )
    assert mutated != baseline
    assert mutated == (1, 2, 3, 4, 5, 6)


def test_ts_generate_triple_strike_and_sumc_generate_are_pure_history_functions() -> None:
    history = _history(200)
    assert _ts_generate_triple_strike(history) == _ts_generate_triple_strike(history)
    assert _sumc_generate_ts_sum_constrained(history) == _sumc_generate_ts_sum_constrained(history)


def test_markov4_orthogonal_bet_excludes_given_numbers() -> None:
    history = _history(150)
    excluded = frozenset(range(1, 20))
    bet = _markov4_orthogonal_bet(history, exclude=excluded, markov_window=100)
    assert set(bet).isdisjoint(excluded)
    assert len(bet) == 6


# ─── catalog / descriptor invariant tests ──────────────────────────────────


def test_production_catalog_batch17_descriptors_declare_expected_shapes() -> None:
    catalog = production_catalog()

    triple_strike = catalog.get("legacy_biglotto__predict_biglotto_triple_strike__dad1c50d1504")
    assert triple_strike.response_shape is ResponseShape.PORTFOLIO
    assert triple_strike.native_ticket_count == 3
    assert triple_strike.executable is True
    assert triple_strike.min_history == 150

    sum_constraint = catalog.get("legacy_biglotto__backtest_sum_constraint__acb3b118300d")
    assert sum_constraint.response_shape is ResponseShape.PORTFOLIO
    assert sum_constraint.native_ticket_count == 3
    assert sum_constraint.executable is True
    assert sum_constraint.min_history == 150

    markov4 = catalog.get("legacy_biglotto__backtest_biglotto_markov_4bet__aefb54eb345b")
    assert markov4.response_shape is ResponseShape.PORTFOLIO
    assert markov4.native_ticket_count == 4
    assert markov4.executable is True
    assert markov4.min_history == 150

    hot_stop_rebound = catalog.get(
        "legacy_biglotto__backtest_biglotto_hot_stop_rebound__1794a8c507ae"
    )
    assert hot_stop_rebound.response_shape is ResponseShape.SINGLE_TICKET
    assert hot_stop_rebound.native_ticket_count == 1
    assert hot_stop_rebound.executable is True
    assert hot_stop_rebound.min_history == 200


def test_pre_batch17_descriptors_are_unaffected_by_batch17() -> None:
    """Every pre-existing descriptor and its declaration order must remain
    unchanged; batch 17's four new descriptors are appended strictly after
    them."""

    catalog = production_catalog()
    all_ids = tuple(descriptor.strategy_id for descriptor in catalog)
    pre_existing_ids = all_ids[:-4]
    batch17_ids_in_order = all_ids[-4:]
    assert set(pre_existing_ids).isdisjoint(BATCH17_IDS)
    assert set(batch17_ids_in_order) == BATCH17_IDS
    assert batch17_ids_in_order == (
        "legacy_biglotto__predict_biglotto_triple_strike__dad1c50d1504",
        "legacy_biglotto__backtest_sum_constraint__acb3b118300d",
        "legacy_biglotto__backtest_biglotto_markov_4bet__aefb54eb345b",
        "legacy_biglotto__backtest_biglotto_hot_stop_rebound__1794a8c507ae",
    )


def test_batch17_portfolio_strategies_are_reachable_through_portfolio_path() -> None:
    portfolio = build_production_generate_portfolio()
    portfolio_ids = BATCH17_IDS - {
        "legacy_biglotto__backtest_biglotto_hot_stop_rebound__1794a8c507ae"
    }
    assert portfolio_ids.issubset(portfolio._adapters.keys())


def test_hot_stop_rebound_is_reachable_through_one_bet_path() -> None:
    one_bet = build_production_generate_one_bet()
    assert "legacy_biglotto__backtest_biglotto_hot_stop_rebound__1794a8c507ae" in (
        one_bet._adapters
    )


# ─── generate_portfolio / generate_one_bet replay-path tests ───────────────


def test_generate_portfolio_returns_complete_native_ticket_set_for_batch17_portfolios() -> None:
    use_case = build_production_generate_portfolio()
    expectations = (
        ("legacy_biglotto__predict_biglotto_triple_strike__dad1c50d1504", 150, 3),
        ("legacy_biglotto__backtest_sum_constraint__acb3b118300d", 150, 3),
        ("legacy_biglotto__backtest_biglotto_markov_4bet__aefb54eb345b", 150, 4),
    )
    for strategy_id, history_len, expected_count in expectations:
        result = use_case.execute(
            GenerateOneBetInput(
                strategy_id=strategy_id,
                lottery_type=LotteryType.BIG_LOTTO,
                history=_history(history_len),
            )
        )
        assert result.status is GeneratePortfolioStatus.OK
        assert result.numbers is not None
        assert len(result.numbers) == expected_count


def test_generate_one_bet_returns_legal_ticket_for_hot_stop_rebound() -> None:
    use_case = build_production_generate_one_bet()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id="legacy_biglotto__backtest_biglotto_hot_stop_rebound__1794a8c507ae",
            lottery_type=LotteryType.BIG_LOTTO,
            history=_history(200),
        )
    )
    assert result.status is GenerateOneBetStatus.OK
    assert result.numbers is not None
    _assert_legal_ticket(result.numbers)


def test_generate_portfolio_fails_closed_for_markov4_insufficient_history() -> None:
    use_case = build_production_generate_portfolio()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id="legacy_biglotto__backtest_biglotto_markov_4bet__aefb54eb345b",
            lottery_type=LotteryType.BIG_LOTTO,
            history=_history(149),
        )
    )
    assert result.status is GeneratePortfolioStatus.INSUFFICIENT_HISTORY
    assert result.reason_code is GeneratePortfolioReason.INSUFFICIENT_HISTORY
    assert result.numbers is None


def test_generate_one_bet_fails_closed_for_hot_stop_rebound_insufficient_history() -> None:
    use_case = build_production_generate_one_bet()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id="legacy_biglotto__backtest_biglotto_hot_stop_rebound__1794a8c507ae",
            lottery_type=LotteryType.BIG_LOTTO,
            history=_history(199),
        )
    )
    assert result.status is GenerateOneBetStatus.INSUFFICIENT_HISTORY
    assert result.reason_code is GenerateOneBetReason.INSUFFICIENT_HISTORY
    assert result.numbers is None


def test_generate_one_bet_rejects_portfolio_strategy_with_wrong_response_path() -> None:
    use_case = build_production_generate_one_bet()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id="legacy_biglotto__predict_biglotto_triple_strike__dad1c50d1504",
            lottery_type=LotteryType.BIG_LOTTO,
            history=_history(150),
        )
    )
    assert result.status is GenerateOneBetStatus.WRONG_RESPONSE_PATH
    assert result.reason_code is GenerateOneBetReason.STRATEGY_IS_PORTFOLIO


def test_generate_portfolio_rejects_single_ticket_strategy_with_wrong_response_path() -> None:
    use_case = build_production_generate_portfolio()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id="legacy_biglotto__backtest_biglotto_hot_stop_rebound__1794a8c507ae",
            lottery_type=LotteryType.BIG_LOTTO,
            history=_history(200),
        )
    )
    assert result.status is GeneratePortfolioStatus.WRONG_RESPONSE_PATH
    assert result.reason_code is GeneratePortfolioReason.STRATEGY_IS_NOT_PORTFOLIO


def test_batch17_adapter_identities_match_their_catalog_descriptors() -> None:
    catalog = production_catalog()
    for adapter_class in (
        BigLottoPredictBiglottoTripleStrikeAdapter,
        BigLottoBacktestSumConstraintAdapter,
        BigLottoBacktestBiglottoMarkov4BetAdapter,
        BigLottoBacktestBiglottoHotStopReboundAdapter,
    ):
        adapter = adapter_class()
        assert isinstance(adapter, (BetAdapter, PortfolioBetAdapter))
        descriptor = catalog.get(adapter.strategy_id)
        assert descriptor.strategy_name == adapter.strategy_name
        assert descriptor.version == adapter.strategy_version


def test_batch17_portfolio_output_is_invalid_output_on_malformed_ticket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Base-class output validation (not this port's own code) is what fails
    closed on a malformed ticket -- confirmed here via the triple-strike
    adapter as one representative of the shared ``PortfolioBetAdapter``
    contract."""

    import lottolab.strategies.adapters.biglotto_batch17 as module

    def _bad_generate(_history: object) -> list[list[int]]:
        return [[1, 2, 3, 4, 5, 5], [1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12]]

    monkeypatch.setattr(module, "_ts_generate_triple_strike", _bad_generate)
    with pytest.raises(InvalidOutput):
        BigLottoPredictBiglottoTripleStrikeAdapter().get_bets(_history(150), LotteryType.BIG_LOTTO)
