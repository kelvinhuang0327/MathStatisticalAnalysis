"""Parity and contract tests for the BigLotto native-strategy batch 18
adapters (``verify_markov_vs_triple_2bet`` and
``backtest_biglotto_coldpool_15``).

Golden fixtures below were produced by executing the REAL, byte-identical
donor source files under a real numpy/scipy interpreter (donor DB imports
never touched, only the pure prediction functions), on a
``random.Random(42)``-seeded synthetic draw history -- 13 golden lengths x 2
strategies, 0 mismatches. See ``biglotto_batch18.py``'s own module docstring
for why a seeded-random generator was used instead of this adapter family's
usual fixed-stride arithmetic-progression generator (stride data triggers
``biglotto_batch16.py``'s own already-documented numpy-``argsort``
tie-break deviation far more often than realistic draw data does).
"""

# pyright: reportPrivateUsage=false
# (reachability check reads the registry's internal adapter map directly,
# the same established pattern test_biglotto_batch16_adapters.py already
# uses for the identical purpose)

import random

import pytest

from lottolab.application.use_cases.generate_bet import (
    GenerateOneBetInput,
    GeneratePortfolioStatus,
    build_production_generate_portfolio,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import ResponseShape
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_batch18 import (
    BigLottoColdPool15Adapter,
    BigLottoMarkovTriple4BetAdapter,
)
from lottolab.strategies.catalog import production_catalog

MARKOV_TRIPLE_ID = "legacy_biglotto__verify_markov_vs_triple_2bet__2094ee4bc361"
COLDPOOL15_ID = "legacy_biglotto__backtest_biglotto_coldpool_15__2a80423e3cf5"


def _history(n: int, seed: int = 42) -> tuple[CausalDrawRow, ...]:
    rng = random.Random(seed)
    rows: list[CausalDrawRow] = []
    for index in range(n):
        numbers: tuple[int, ...] = tuple(sorted(rng.sample(range(1, 50), 6)))
        rows.append(
            CausalDrawRow(
                draw=str(index),
                date=f"2026-01-{(index % 28) + 1:02d}",
                numbers=numbers,
            )
        )
    return tuple(rows)


# ─── golden fixtures: real donor output under numpy/scipy, seed=42 ─────────

MARKOV_TRIPLE_4BET_GOLDENS: dict[int, tuple[tuple[int, ...], ...]] = {
    500: (
        (4, 26, 30, 33, 36, 44), (8, 9, 20, 31, 46, 47),
        (6, 12, 14, 19, 39, 48), (2, 5, 7, 11, 28, 41),
    ),
    501: (
        (25, 31, 35, 36, 44, 47), (4, 9, 14, 20, 21, 27),
        (5, 18, 19, 26, 29, 35), (2, 6, 7, 11, 28, 41),
    ),
    600: (
        (6, 9, 20, 25, 40, 44), (7, 16, 23, 26, 37, 47),
        (3, 6, 7, 28, 35, 47), (4, 8, 13, 14, 17, 43),
    ),
    750: (
        (4, 5, 6, 7, 11, 15), (13, 22, 23, 30, 38, 46),
        (9, 24, 25, 29, 30, 35), (14, 19, 33, 39, 40, 45),
    ),
    900: (
        (1, 4, 17, 19, 36, 44), (7, 13, 22, 27, 43, 45),
        (27, 29, 31, 36, 43, 47), (2, 5, 6, 10, 12, 20),
    ),
    1200: (
        (12, 13, 17, 36, 47, 49), (2, 21, 29, 34, 41, 45),
        (9, 10, 25, 29, 37, 40), (1, 5, 19, 31, 38, 44),
    ),
}

COLDPOOL15_GOLDENS: dict[int, tuple[tuple[int, ...], ...]] = {
    300: (
        (30, 32, 40, 41, 42, 48), (1, 11, 13, 31, 47, 49), (5, 7, 10, 21, 28, 43),
        (3, 9, 16, 17, 25, 35), (2, 6, 26, 27, 45, 46),
        (30, 32, 40, 41, 42, 48), (1, 11, 13, 31, 47, 49), (5, 7, 10, 21, 28, 43),
        (3, 9, 16, 17, 25, 35), (2, 6, 26, 27, 45, 46),
    ),
    301: (
        (5, 21, 23, 32, 37, 39), (1, 11, 13, 31, 47, 49), (7, 10, 28, 43, 46, 48),
        (3, 9, 16, 17, 25, 35), (2, 4, 26, 38, 40, 42),
        (5, 21, 23, 32, 37, 39), (1, 11, 13, 31, 47, 49), (7, 10, 28, 43, 46, 48),
        (3, 9, 16, 17, 25, 35), (2, 4, 26, 38, 40, 42),
    ),
    350: (
        (21, 22, 29, 30, 41, 42), (1, 17, 18, 32, 35, 49), (6, 10, 19, 24, 33, 39),
        (8, 13, 14, 15, 26, 47), (4, 9, 20, 27, 31, 44),
        (21, 22, 29, 30, 41, 42), (1, 13, 17, 35, 37, 49), (6, 10, 19, 24, 33, 39),
        (8, 14, 18, 26, 32, 47), (4, 9, 20, 27, 31, 44),
    ),
    500: (
        (6, 25, 29, 31, 32, 34), (5, 11, 18, 28, 41, 49), (4, 16, 20, 30, 35, 44),
        (1, 2, 7, 19, 22, 40), (3, 8, 24, 37, 38, 42),
        (6, 25, 29, 31, 32, 34), (2, 18, 23, 28, 40, 41), (4, 16, 20, 30, 35, 44),
        (1, 7, 11, 19, 22, 49), (3, 8, 24, 37, 38, 42),
    ),
    600: (
        (14, 16, 17, 37, 44, 46), (4, 13, 22, 31, 39, 43), (7, 8, 12, 29, 32, 45),
        (1, 5, 10, 18, 34, 48), (2, 3, 9, 35, 38, 49),
        (14, 16, 17, 37, 44, 46), (4, 13, 22, 31, 39, 43), (7, 8, 12, 29, 32, 45),
        (1, 5, 10, 18, 34, 48), (2, 3, 9, 35, 38, 49),
    ),
    900: (
        (17, 24, 34, 36, 47, 49), (5, 20, 26, 28, 35, 37), (19, 33, 40, 43, 44, 46),
        (2, 6, 10, 11, 18, 32), (13, 15, 21, 23, 31, 48),
        (17, 24, 34, 36, 47, 49), (2, 20, 26, 28, 37, 38), (19, 33, 40, 43, 44, 46),
        (5, 6, 10, 11, 18, 32), (13, 15, 21, 23, 31, 48),
    ),
    1200: (
        (13, 14, 29, 30, 32, 37), (5, 19, 22, 23, 38, 44), (2, 9, 12, 34, 46, 49),
        (1, 4, 7, 17, 24, 31), (3, 11, 16, 26, 35, 43),
        (13, 14, 29, 30, 32, 37), (5, 19, 22, 23, 38, 44), (2, 9, 12, 34, 46, 49),
        (1, 4, 7, 17, 24, 31), (3, 11, 16, 26, 35, 43),
    ),
}


# ─── BigLottoMarkovTriple4BetAdapter ────────────────────────────────────────


@pytest.mark.parametrize("length", sorted(MARKOV_TRIPLE_4BET_GOLDENS))
def test_markov_triple_4bet_golden(length: int) -> None:
    history = _history(length)
    tickets = BigLottoMarkovTriple4BetAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert tickets == MARKOV_TRIPLE_4BET_GOLDENS[length]


def test_markov_triple_4bet_rejects_insufficient_history() -> None:
    history = _history(499)
    with pytest.raises(InsufficientHistory):
        BigLottoMarkovTriple4BetAdapter().get_bets(history, LotteryType.BIG_LOTTO)


def test_markov_triple_4bet_accepts_exactly_min_history() -> None:
    history = _history(500)
    tickets = BigLottoMarkovTriple4BetAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert len(tickets) == 4


def test_markov_triple_4bet_rejects_wrong_lottery_type() -> None:
    history = _history(600)
    with pytest.raises(UnsupportedLotteryType):
        BigLottoMarkovTriple4BetAdapter().get_bets(history, LotteryType.POWER_LOTTO)


def test_markov_triple_4bet_repeated_execution_byte_equality() -> None:
    history = _history(600)
    first = BigLottoMarkovTriple4BetAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    second = BigLottoMarkovTriple4BetAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert first == second


def test_markov_triple_4bet_each_ticket_is_legal() -> None:
    history = _history(600)
    tickets = BigLottoMarkovTriple4BetAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert len(tickets) == 4
    for ticket in tickets:
        assert len(ticket) == 6
        assert len(set(ticket)) == 6
        assert all(1 <= number <= 49 for number in ticket)
        assert ticket == tuple(sorted(ticket))


def test_markov_triple_4bet_production_catalog_declares_expected_shape() -> None:
    descriptor = production_catalog().get(MARKOV_TRIPLE_ID)
    assert descriptor.response_shape is ResponseShape.PORTFOLIO
    assert descriptor.native_ticket_count == 4
    assert descriptor.executable is True
    assert descriptor.min_history == 500
    assert descriptor.lottery_types == (LotteryType.BIG_LOTTO,)


def test_markov_triple_4bet_reachable_only_through_portfolio_path() -> None:
    portfolio = build_production_generate_portfolio()
    assert MARKOV_TRIPLE_ID in portfolio._adapters


def test_markov_triple_4bet_generate_portfolio_returns_golden() -> None:
    use_case = build_production_generate_portfolio()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id=MARKOV_TRIPLE_ID,
            lottery_type=LotteryType.BIG_LOTTO,
            history=_history(600),
        )
    )
    assert result.status is GeneratePortfolioStatus.OK
    assert result.numbers == MARKOV_TRIPLE_4BET_GOLDENS[600]


# ─── BigLottoColdPool15Adapter ──────────────────────────────────────────────


@pytest.mark.parametrize("length", sorted(COLDPOOL15_GOLDENS))
def test_coldpool15_golden(length: int) -> None:
    history = _history(length)
    tickets = BigLottoColdPool15Adapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert tickets == COLDPOOL15_GOLDENS[length]


def test_coldpool15_rejects_insufficient_history() -> None:
    history = _history(299)
    with pytest.raises(InsufficientHistory):
        BigLottoColdPool15Adapter().get_bets(history, LotteryType.BIG_LOTTO)


def test_coldpool15_accepts_exactly_min_history() -> None:
    history = _history(300)
    tickets = BigLottoColdPool15Adapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert len(tickets) == 10


def test_coldpool15_rejects_wrong_lottery_type() -> None:
    history = _history(600)
    with pytest.raises(UnsupportedLotteryType):
        BigLottoColdPool15Adapter().get_bets(history, LotteryType.POWER_LOTTO)


def test_coldpool15_repeated_execution_byte_equality() -> None:
    history = _history(600)
    first = BigLottoColdPool15Adapter().get_bets(history, LotteryType.BIG_LOTTO)
    second = BigLottoColdPool15Adapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert first == second


def test_coldpool15_each_ticket_is_legal() -> None:
    history = _history(600)
    tickets = BigLottoColdPool15Adapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert len(tickets) == 10
    for ticket in tickets:
        assert len(ticket) == 6
        assert len(set(ticket)) == 6
        assert all(1 <= number <= 49 for number in ticket)
        assert ticket == tuple(sorted(ticket))


def test_coldpool15_pool12_and_pool15_halves_each_internally_disjoint() -> None:
    """Each 5-ticket half (pool=12, pool=15) is independently generated from
    ``history`` with its own running ``used`` exclusion set, so bet1..bet5
    within *one* half never repeat a number -- but bet1 is identical across
    both halves by construction (it never depends on cold_pool_size), so no
    disjointness claim is made *across* the two halves; this matches the
    donor's own two independent ``generate_5bet`` calls exactly."""

    history = _history(600)
    tickets = BigLottoColdPool15Adapter().get_bets(history, LotteryType.BIG_LOTTO)
    for half in (tickets[:5], tickets[5:]):
        seen: set[int] = set()
        for ticket in half:
            assert seen.isdisjoint(ticket)
            seen.update(ticket)
    assert tickets[0] == tickets[5]


def test_coldpool15_production_catalog_declares_expected_shape() -> None:
    descriptor = production_catalog().get(COLDPOOL15_ID)
    assert descriptor.response_shape is ResponseShape.PORTFOLIO
    assert descriptor.native_ticket_count == 10
    assert descriptor.executable is True
    assert descriptor.min_history == 300
    assert descriptor.lottery_types == (LotteryType.BIG_LOTTO,)


def test_coldpool15_reachable_only_through_portfolio_path() -> None:
    portfolio = build_production_generate_portfolio()
    assert COLDPOOL15_ID in portfolio._adapters


def test_coldpool15_generate_portfolio_returns_golden() -> None:
    use_case = build_production_generate_portfolio()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id=COLDPOOL15_ID,
            lottery_type=LotteryType.BIG_LOTTO,
            history=_history(600),
        )
    )
    assert result.status is GeneratePortfolioStatus.OK
    assert result.numbers == COLDPOOL15_GOLDENS[600]


# ─── catalog append-order (this batch adds exactly two BIG_LOTTO ids) ──────


def test_production_catalog_appends_batch18_after_preceding_admitted_batches() -> None:
    catalog = production_catalog()
    all_ids = tuple(descriptor.strategy_id for descriptor in catalog)
    pre_wave2 = all_ids[:92]
    assert pre_wave2[-6] == MARKOV_TRIPLE_ID
    assert pre_wave2[-5] == COLDPOOL15_ID
    assert pre_wave2[-7] == "legacy_biglotto__backtest_biglotto_hot_stop_rebound__1794a8c507ae"
    assert all_ids.count(MARKOV_TRIPLE_ID) == 1
    assert all_ids.count(COLDPOOL15_ID) == 1
