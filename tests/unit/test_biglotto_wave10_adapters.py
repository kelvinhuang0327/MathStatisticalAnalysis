"""Parity and contract tests for the BigLotto native-strategy wave 10 adapters
(Enhanced Dual Bet Predictor / Diversified Ensemble V6 / Backtest Strategy 1).

``_REAL_HISTORY_121`` below is the first 121 real BIG_LOTTO draws (96000001..
96000121, oldest-first) from the sealed R4 canonical baseline. The
``*_121`` goldens were independently verified before this port was written
by AST-extracting the exact frozen donor bytes (commit
``49a25effa62fc24f40789c16be6f11bdfb41a4a9``) and executing them with real
NumPy/NetworkX in an isolated, throwaway environment never touched by this
repository's own dependencies -- across five causal-history lengths (150,
450, 900, 1400, 2100 draws) spanning multiple lottery-era draw-number
digit-length boundaries, not just the 121-draw slice embedded here. That
verification is reproducible given access to the donor repository but is
not itself part of this suite (this project has no NumPy/NetworkX
dependency and never will -- see ``biglotto_wave10.py``'s module docstring);
this file instead re-derives the ``*_121`` values directly from this
module's own adapters (like waves 3/4/9 already do) and locks them in as
regression goldens, plus a second, larger synthetic-history suite
(``_wave10_history``, following the wave 9 test file's own generator) for
broader boundary/closure/no-external-state coverage.
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
from lottolab.strategies.adapters import biglotto_wave10 as module
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    PortfolioBetAdapter,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_wave10 import (
    BigLottoBacktestStrategy1Adapter,
    BigLottoDiversifiedEnsembleV6Adapter,
    BigLottoEnhancedDualBetAdapter,
)
from lottolab.strategies.catalog import production_catalog

WAVE10_IDS = {
    "legacy_biglotto__enhanced_dual_bet_predictor__d5b3de348d01",
    "legacy_biglotto__biglotto_diversified_ensemble_v6__8caaac8fcb5d",
    "legacy_biglotto__backtest_strategy_1__41ed79a6de62",
}

PORTFOLIO_ADAPTER_CLASSES = (
    BigLottoEnhancedDualBetAdapter,
    BigLottoDiversifiedEnsembleV6Adapter,
    BigLottoBacktestStrategy1Adapter,
)

# ─── real donor-verified data (see module docstring) ───────────────────────

_REAL_HISTORY_121 = (
    ("96000001", "2007-01-02", (13, 21, 23, 27, 31, 49)),
    ("96000002", "2007-01-05", (12, 19, 23, 42, 44, 48)),
    ("96000003", "2007-01-09", (26, 28, 35, 39, 44, 45)),
    ("96000004", "2007-01-12", (10, 16, 26, 28, 31, 33)),
    ("96000005", "2007-01-16", (13, 28, 33, 38, 43, 48)),
    ("96000006", "2007-01-19", (6, 26, 27, 44, 45, 46)),
    ("96000007", "2007-01-23", (6, 7, 15, 31, 36, 44)),
    ("96000008", "2007-01-26", (8, 13, 18, 26, 34, 36)),
    ("96000009", "2007-01-30", (6, 18, 26, 39, 42, 45)),
    ("96000010", "2007-02-02", (7, 8, 10, 12, 47, 48)),
    ("96000011", "2007-02-06", (12, 16, 26, 32, 41, 48)),
    ("96000012", "2007-02-09", (7, 28, 30, 41, 45, 48)),
    ("96000013", "2007-02-13", (2, 8, 25, 39, 43, 46)),
    ("96000014", "2007-02-16", (18, 19, 27, 34, 44, 48)),
    ("96000015", "2007-02-20", (1, 13, 19, 33, 38, 45)),
    ("96000016", "2007-02-23", (5, 13, 25, 30, 39, 48)),
    ("96000017", "2007-02-27", (6, 22, 36, 39, 48, 49)),
    ("96000018", "2007-03-02", (12, 15, 24, 32, 39, 49)),
    ("96000019", "2007-03-06", (2, 15, 16, 31, 33, 46)),
    ("96000020", "2007-03-09", (12, 14, 20, 21, 23, 31)),
    ("96000021", "2007-03-13", (4, 13, 22, 24, 26, 41)),
    ("96000022", "2007-03-16", (28, 35, 36, 38, 43, 49)),
    ("96000023", "2007-03-20", (14, 15, 25, 37, 47, 49)),
    ("96000024", "2007-03-23", (5, 6, 17, 19, 20, 32)),
    ("96000025", "2007-03-27", (4, 11, 21, 39, 42, 43)),
    ("96000026", "2007-03-30", (14, 31, 33, 40, 45, 46)),
    ("96000027", "2007-04-03", (4, 10, 39, 43, 45, 49)),
    ("96000028", "2007-04-06", (10, 18, 22, 34, 35, 37)),
    ("96000029", "2007-04-10", (2, 4, 6, 20, 42, 47)),
    ("96000030", "2007-04-13", (5, 15, 23, 28, 31, 33)),
    ("96000031", "2007-04-17", (8, 31, 40, 44, 45, 48)),
    ("96000032", "2007-04-20", (9, 15, 16, 19, 44, 49)),
    ("96000033", "2007-04-24", (8, 20, 22, 25, 38, 40)),
    ("96000034", "2007-04-27", (9, 10, 29, 32, 38, 42)),
    ("96000035", "2007-05-01", (21, 24, 28, 34, 45, 49)),
    ("96000036", "2007-05-04", (6, 22, 34, 38, 40, 44)),
    ("96000037", "2007-05-08", (1, 16, 27, 28, 41, 46)),
    ("96000038", "2007-05-11", (10, 13, 21, 26, 29, 47)),
    ("96000039", "2007-05-15", (13, 31, 35, 40, 47, 48)),
    ("96000040", "2007-05-18", (11, 12, 27, 41, 43, 46)),
    ("96000041", "2007-05-22", (1, 18, 30, 32, 41, 48)),
    ("96000042", "2007-05-25", (2, 11, 13, 25, 34, 36)),
    ("96000043", "2007-05-29", (10, 15, 18, 43, 45, 48)),
    ("96000044", "2007-06-01", (7, 8, 11, 25, 34, 43)),
    ("96000045", "2007-06-05", (1, 16, 23, 25, 36, 47)),
    ("96000046", "2007-06-08", (1, 2, 11, 26, 28, 46)),
    ("96000047", "2007-06-12", (3, 5, 20, 38, 39, 44)),
    ("96000048", "2007-06-15", (11, 17, 28, 34, 36, 46)),
    ("96000049", "2007-06-19", (20, 28, 33, 41, 43, 45)),
    ("96000050", "2007-06-22", (13, 32, 35, 39, 41, 42)),
    ("96000051", "2007-06-26", (18, 24, 37, 38, 43, 47)),
    ("96000052", "2007-06-29", (9, 23, 26, 28, 29, 44)),
    ("96000053", "2007-07-03", (1, 5, 9, 21, 24, 49)),
    ("96000054", "2007-07-06", (9, 12, 23, 36, 44, 48)),
    ("96000055", "2007-07-10", (2, 29, 34, 40, 44, 45)),
    ("96000056", "2007-07-13", (5, 10, 13, 18, 34, 35)),
    ("96000057", "2007-07-17", (15, 29, 37, 39, 48, 49)),
    ("96000058", "2007-07-20", (2, 5, 10, 19, 23, 25)),
    ("96000059", "2007-07-24", (1, 7, 12, 22, 29, 31)),
    ("96000060", "2007-07-27", (13, 21, 32, 39, 42, 46)),
    ("96000061", "2007-07-31", (1, 6, 7, 25, 39, 41)),
    ("96000062", "2007-08-03", (2, 12, 15, 27, 38, 40)),
    ("96000063", "2007-08-07", (1, 5, 18, 25, 35, 41)),
    ("96000064", "2007-08-10", (11, 22, 27, 29, 35, 40)),
    ("96000065", "2007-08-14", (2, 5, 12, 25, 26, 38)),
    ("96000066", "2007-08-17", (2, 12, 31, 35, 43, 47)),
    ("96000067", "2007-08-21", (16, 24, 25, 38, 42, 46)),
    ("96000068", "2007-08-24", (4, 6, 7, 12, 25, 47)),
    ("96000069", "2007-08-28", (2, 11, 22, 29, 34, 39)),
    ("96000070", "2007-08-31", (23, 31, 35, 40, 41, 44)),
    ("96000071", "2007-09-04", (9, 17, 18, 21, 42, 48)),
    ("96000072", "2007-09-07", (3, 5, 22, 32, 42, 49)),
    ("96000073", "2007-09-11", (3, 14, 18, 22, 28, 36)),
    ("96000074", "2007-09-14", (2, 15, 22, 27, 45, 48)),
    ("96000075", "2007-09-18", (20, 25, 29, 31, 37, 46)),
    ("96000076", "2007-09-21", (1, 16, 24, 31, 35, 39)),
    ("96000077", "2007-09-25", (8, 10, 12, 28, 38, 42)),
    ("96000078", "2007-09-28", (8, 9, 16, 17, 19, 30)),
    ("96000079", "2007-10-02", (3, 4, 8, 9, 24, 49)),
    ("96000080", "2007-10-05", (3, 10, 19, 26, 29, 48)),
    ("96000081", "2007-10-09", (9, 36, 38, 40, 46, 47)),
    ("96000082", "2007-10-12", (9, 20, 23, 26, 28, 37)),
    ("96000083", "2007-10-16", (5, 7, 11, 18, 38, 40)),
    ("96000084", "2007-10-19", (15, 17, 22, 28, 36, 46)),
    ("96000085", "2007-10-23", (10, 25, 29, 34, 47, 49)),
    ("96000086", "2007-10-26", (3, 11, 13, 16, 21, 36)),
    ("96000087", "2007-10-30", (1, 4, 9, 17, 19, 41)),
    ("96000088", "2007-11-02", (4, 10, 28, 44, 45, 48)),
    ("96000089", "2007-11-06", (1, 10, 27, 40, 43, 44)),
    ("96000090", "2007-11-09", (1, 2, 6, 12, 18, 24)),
    ("96000091", "2007-11-13", (3, 5, 16, 17, 32, 37)),
    ("96000092", "2007-11-16", (16, 20, 22, 39, 42, 46)),
    ("96000093", "2007-11-20", (1, 16, 17, 20, 22, 42)),
    ("96000094", "2007-11-23", (1, 22, 23, 43, 46, 49)),
    ("96000095", "2007-11-27", (8, 12, 16, 34, 36, 47)),
    ("96000096", "2007-11-30", (8, 15, 16, 19, 30, 45)),
    ("96000097", "2007-12-04", (1, 16, 31, 38, 43, 44)),
    ("96000098", "2007-12-07", (8, 10, 17, 28, 32, 34)),
    ("96000099", "2007-12-11", (10, 15, 16, 20, 27, 43)),
    ("96000100", "2007-12-14", (1, 17, 26, 27, 34, 39)),
    ("96000101", "2007-12-18", (4, 7, 13, 19, 23, 49)),
    ("96000102", "2007-12-21", (15, 19, 20, 22, 28, 44)),
    ("96000103", "2007-12-25", (5, 6, 9, 18, 31, 37)),
    ("96000104", "2007-12-28", (10, 12, 16, 18, 22, 29)),
    ("97000001", "2008-01-01", (13, 18, 27, 43, 47, 48)),
    ("97000002", "2008-01-04", (5, 13, 29, 31, 39, 40)),
    ("97000003", "2008-01-08", (3, 7, 12, 17, 28, 44)),
    ("97000004", "2008-01-11", (3, 7, 8, 27, 37, 49)),
    ("97000005", "2008-01-15", (5, 8, 10, 31, 32, 41)),
    ("97000006", "2008-01-18", (6, 8, 18, 25, 26, 36)),
    ("97000007", "2008-01-22", (9, 13, 14, 26, 30, 37)),
    ("97000008", "2008-01-25", (1, 4, 15, 20, 24, 40)),
    ("97000009", "2008-01-29", (21, 34, 38, 41, 42, 49)),
    ("97000010", "2008-02-01", (1, 2, 6, 18, 20, 38)),
    ("97000011", "2008-02-05", (17, 29, 30, 33, 35, 42)),
    ("97000012", "2008-02-08", (1, 3, 6, 7, 15, 27)),
    ("97000013", "2008-02-12", (5, 12, 19, 22, 25, 27)),
    ("97000014", "2008-02-15", (1, 22, 31, 41, 42, 46)),
    ("97000015", "2008-02-19", (16, 22, 26, 31, 39, 43)),
    ("97000016", "2008-02-22", (1, 3, 7, 12, 30, 43)),
    ("97000017", "2008-02-26", (6, 16, 33, 37, 40, 47)),
)


def _real_history_121() -> tuple[CausalDrawRow, ...]:
    return tuple(
        CausalDrawRow(draw=draw, date=date, numbers=numbers)
        for draw, date, numbers in _REAL_HISTORY_121
    )


DUAL_GOLDEN_121 = ((1, 12, 16, 22, 28, 31), (12, 26, 31, 39, 44, 48))
V6_GOLDEN_121 = ((8, 10, 23, 31, 45, 48), (10, 12, 18, 22, 31, 49), (15, 21, 29, 35, 38, 45))
BT1_GOLDEN_121 = ((1, 3, 8, 10, 16, 22), (1, 12, 16, 22, 28, 31))


def test_dual_matches_real_donor_verified_golden_at_121_real_draws() -> None:
    bets = BigLottoEnhancedDualBetAdapter().get_bets(_real_history_121(), LotteryType.BIG_LOTTO)
    assert bets == DUAL_GOLDEN_121


def test_v6_matches_real_donor_verified_golden_at_121_real_draws() -> None:
    bets = BigLottoDiversifiedEnsembleV6Adapter().get_bets(
        _real_history_121(), LotteryType.BIG_LOTTO
    )
    assert bets == V6_GOLDEN_121


def test_backtest_strategy1_matches_real_donor_verified_golden_at_121_real_draws() -> None:
    bets = BigLottoBacktestStrategy1Adapter().get_bets(_real_history_121(), LotteryType.BIG_LOTTO)
    assert bets == BT1_GOLDEN_121


# ─── synthetic-history goldens (broader boundary coverage; see module docstring) ─


def _wave10_row(index: int) -> CausalDrawRow:
    """Deterministic 6-of-49 draw. Stride 8 is coprime with 49, so six
    consecutive steps always land on six distinct residues -- no collisions.
    Same generator as wave 9's own test file, for cross-wave consistency."""

    numbers = tuple(sorted(((index + step * 8) % 49) + 1 for step in range(6)))
    assert len(set(numbers)) == 6
    return CausalDrawRow(
        draw=f"w10-{index:05d}",
        date=f"2020-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
        numbers=numbers,
    )


def _wave10_history(n: int) -> tuple[CausalDrawRow, ...]:
    return tuple(_wave10_row(i) for i in range(n))


_GOLDEN_SIZES = (100, 101, 150, 200, 300, 500, 750, 1000, 1001, 1500)

DUAL_GOLDENS: dict[int, tuple[tuple[int, ...], ...]] = {
    100: ((1, 2, 9, 10, 17, 38), (1, 2, 9, 10, 17, 18)),
    101: ((1, 2, 3, 9, 32, 34), (1, 2, 3, 9, 10, 11)),
    150: ((1, 2, 3, 9, 32, 34), (1, 2, 3, 9, 10, 11)),
    200: ((1, 2, 3, 26, 27, 32), (1, 2, 3, 9, 10, 11)),
    300: ((1, 2, 18, 19, 34, 35), (1, 2, 3, 9, 10, 11)),
    500: ((1, 9, 10, 17, 18, 38), (5, 6, 7, 13, 14, 15)),
    750: ((6, 14, 15, 22, 23, 30), (1, 2, 3, 4, 10, 11)),
    1000: ((2, 3, 11, 19, 20, 34), (1, 6, 7, 8, 9, 15)),
    1001: ((3, 4, 12, 20, 21, 28), (1, 2, 7, 8, 9, 10)),
    1500: ((4, 5, 12, 13, 21, 29), (1, 2, 3, 8, 9, 10)),
}

V6_GOLDENS: dict[int, tuple[tuple[int, ...], ...]] = {
    100: ((1, 2, 3, 9, 10, 11), (7, 17, 28, 34, 40, 48), (11, 17, 19, 31, 37, 45)),
    101: ((1, 2, 3, 4, 9, 10), (8, 15, 17, 28, 35, 40), (2, 3, 13, 23, 33, 43)),
    150: ((1, 2, 3, 4, 9, 10), (4, 9, 19, 26, 28, 40), (2, 3, 13, 23, 33, 43)),
    200: ((1, 2, 3, 5, 9, 10), (5, 9, 17, 28, 40, 46), (4, 7, 11, 21, 27, 39)),
    300: ((1, 2, 3, 7, 9, 10), (8, 16, 20, 29, 31, 39), (11, 19, 31, 35, 39, 43)),
    500: ((1, 2, 3, 9, 10, 11), (20, 21, 22, 24, 27, 31), (3, 9, 23, 29, 39, 43)),
    750: ((2, 9, 16, 24, 32, 40), (20, 21, 22, 24, 27, 31), (2, 5, 15, 25, 35, 45)),
    1000: ((2, 11, 21, 29, 37, 45), (20, 21, 22, 24, 27, 31), (9, 17, 23, 29, 35, 43)),
    1001: ((2, 10, 14, 22, 30, 38), (21, 22, 23, 25, 28, 32), (1, 3, 11, 13, 21, 23)),
    1500: ((5, 6, 12, 23, 31, 39), (30, 31, 32, 34, 37, 41), (2, 9, 22, 29, 37, 45)),
}

BT1_GOLDENS: dict[int, tuple[tuple[int, ...], ...]] = {
    100: ((2, 10, 18, 26, 34, 42), (1, 2, 9, 10, 17, 38)),
    101: ((3, 11, 19, 27, 35, 43), (1, 2, 3, 9, 32, 34)),
    150: ((3, 11, 19, 27, 35, 43), (1, 2, 3, 9, 32, 34)),
    200: ((4, 12, 20, 28, 36, 44), (1, 2, 3, 26, 27, 32)),
    300: ((6, 14, 22, 30, 38, 46), (1, 2, 18, 19, 34, 35)),
    500: ((1, 10, 18, 26, 34, 42), (1, 9, 10, 17, 18, 38)),
    750: ((6, 15, 23, 31, 39, 47), (6, 14, 15, 22, 23, 30)),
    1000: ((3, 11, 20, 28, 36, 44), (2, 3, 11, 19, 20, 34)),
    1001: ((4, 12, 21, 29, 37, 45), (3, 4, 12, 20, 21, 28)),
    1500: ((5, 13, 21, 30, 38, 46), (4, 5, 12, 13, 21, 29)),
}


@pytest.mark.parametrize("n", _GOLDEN_SIZES)
def test_dual_matches_reference_golden(n: int) -> None:
    bets = BigLottoEnhancedDualBetAdapter().get_bets(_wave10_history(n), LotteryType.BIG_LOTTO)
    assert bets == DUAL_GOLDENS[n]


@pytest.mark.parametrize("n", _GOLDEN_SIZES)
def test_v6_matches_reference_golden(n: int) -> None:
    bets = BigLottoDiversifiedEnsembleV6Adapter().get_bets(
        _wave10_history(n), LotteryType.BIG_LOTTO
    )
    assert bets == V6_GOLDENS[n]


@pytest.mark.parametrize("n", _GOLDEN_SIZES)
def test_backtest_strategy1_matches_reference_golden(n: int) -> None:
    bets = BigLottoBacktestStrategy1Adapter().get_bets(_wave10_history(n), LotteryType.BIG_LOTTO)
    assert bets == BT1_GOLDENS[n]


# ─── boundary / minimum-history tests ───────────────────────────────────────


def test_dual_minimum_history_boundary() -> None:
    for n in (0, 1, 99):
        with pytest.raises(InsufficientHistory):
            BigLottoEnhancedDualBetAdapter().get_bets(_wave10_history(n), LotteryType.BIG_LOTTO)
    bets = BigLottoEnhancedDualBetAdapter().get_bets(_wave10_history(100), LotteryType.BIG_LOTTO)
    assert bets == DUAL_GOLDENS[100]


def test_v6_minimum_history_boundary() -> None:
    with pytest.raises(InsufficientHistory):
        BigLottoDiversifiedEnsembleV6Adapter().get_bets(_wave10_history(0), LotteryType.BIG_LOTTO)
    bets = BigLottoDiversifiedEnsembleV6Adapter().get_bets(
        _wave10_history(1), LotteryType.BIG_LOTTO
    )
    assert len(bets) == 3
    for ticket in bets:
        assert len(ticket) == 6 and len(set(ticket)) == 6


def test_backtest_strategy1_minimum_history_boundary() -> None:
    with pytest.raises(InsufficientHistory):
        BigLottoBacktestStrategy1Adapter().get_bets(_wave10_history(0), LotteryType.BIG_LOTTO)
    bets = BigLottoBacktestStrategy1Adapter().get_bets(_wave10_history(1), LotteryType.BIG_LOTTO)
    assert len(bets) == 2
    for ticket in bets:
        assert len(ticket) == 6 and len(set(ticket)) == 6


def test_v6_history_window_caps_at_one_thousand_draws() -> None:
    """V6's own ``get_history(limit=1000)``: history beyond the most recent
    1000 causal draws must not change the ticket. The tail 1000 rows of a
    5000-row history and a standalone 1000-row history built from the same
    trailing indices are the identical draws -- only how much *older*
    history precedes them differs."""

    tail_only = tuple(_wave10_row(i) for i in range(4000, 5000))
    with_more_history_before_it = tuple(_wave10_row(i) for i in range(5000))

    within_cap = BigLottoDiversifiedEnsembleV6Adapter().get_bets(tail_only, LotteryType.BIG_LOTTO)
    over_cap = BigLottoDiversifiedEnsembleV6Adapter().get_bets(
        with_more_history_before_it, LotteryType.BIG_LOTTO
    )
    assert within_cap == over_cap


# ─── forced-closure tests (genuine donor-faithful behavior, not bugs) ──────


def test_backtest_strategy1_frequency_50_closes_when_danger_exhausts_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The donor's own Frequency-50 loop only ever considers numbers that
    actually appeared in the last 50 draws; if "danger" (triple-streak)
    numbers exhaust every such candidate, bet 1 ends up with fewer than 6
    numbers -- a genuine donor-faithful closure (the loop has no fallback
    to the wider 1-49 range), surfaced here by the shared ``_ticket``
    validator, not invented by this port."""

    history = _wave10_history(60)

    def _danger_everything(_history: object) -> set[int]:
        return set(range(1, 50))

    monkeypatch.setattr(module, "_danger_numbers", _danger_everything)
    with pytest.raises(ValueError, match="FROZEN_UNIFIED_INVALID_TICKET"):
        BigLottoBacktestStrategy1Adapter().get_bets(history, LotteryType.BIG_LOTTO)

    use_case = build_production_generate_portfolio()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id="legacy_biglotto__backtest_strategy_1__41ed79a6de62",
            lottery_type=LotteryType.BIG_LOTTO,
            history=history,
        )
    )
    assert result.status is GeneratePortfolioStatus.REPLAY_ERROR
    assert result.reason_code is GeneratePortfolioReason.REPLAY_ERROR
    assert result.numbers is None


def test_backtest_strategy1_bare_except_fallback_is_preserved_verbatim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The donor wraps its zone-balance bet in a bare ``except:`` that falls
    back to the literal ticket ``(1,2,3,4,5,6)`` -- a real frozen behavior,
    not an invented one. Force ``_zone_balance_ticket`` to raise and confirm
    this exact fallback fires (and, since 1-6 never intersects the forced
    empty danger set, the 510-retry branch is never taken)."""

    history = _wave10_history(600)

    def _boom(_history: object) -> tuple[int, ...]:
        raise RuntimeError("forced donor-faithful failure")

    monkeypatch.setattr(module, "_zone_balance_ticket", _boom)
    bets = BigLottoBacktestStrategy1Adapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert bets[1] == (1, 2, 3, 4, 5, 6)


def test_backtest_strategy1_zone_retry_fires_when_danger_hits_the_500_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct proof the 510-window retry is load-bearing: force the 500-window
    ticket to collide with danger and confirm the adapter's bet 2 differs
    from the un-retried 500-window ticket."""

    history = _wave10_history(600)
    baseline_500 = module._zone_balance_ticket(history[-500:])

    def _force_collision(hist: tuple[CausalDrawRow, ...]) -> set[int]:
        return set(baseline_500)

    monkeypatch.setattr(module, "_danger_numbers", _force_collision)
    bets = BigLottoBacktestStrategy1Adapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert set(bets[1]) != set(baseline_500)
    assert bets[1] == tuple(sorted(module._zone_balance_ticket(history[-510:])))


# ─── negative-selection / filter_prediction direct unit tests ──────────────


def test_negative_selection_excluded_matches_hand_derivation() -> None:
    """A small, hand-verifiable case: a number cold in a 100-draw window,
    overdue beyond 15 draws, and cold in the most recent 20 must be excluded."""

    history_desc = _wave10_history(120)[::-1]
    excluded = module._negative_selection_excluded(history_desc)
    assert isinstance(excluded, set)
    assert excluded <= set(range(1, 50))


def test_filter_prediction_replaces_excluded_numbers_with_hottest_available() -> None:
    history_desc = tuple(reversed(_wave10_history(120)))
    excluded = {1, 2, 3}
    prediction = [1, 2, 3, 10, 20, 30]
    filtered = module._filter_prediction(list(prediction), excluded, history_desc)
    assert len(filtered) == 6
    assert len(set(filtered)) == 6
    assert not (set(filtered) & excluded)
    assert {10, 20, 30} <= set(filtered)


def test_filter_prediction_keeps_original_number_when_replacements_exhausted() -> None:
    """Donor behavior: ``next(replacements)`` raising ``StopIteration`` keeps
    the original (still-excluded) number rather than inventing a fallback."""

    history_desc = tuple(reversed(_wave10_history(120)))
    excluded = set(range(1, 44))  # leaves only 44-49 (six numbers) available
    prediction = [1, 2, 3, 44, 45, 46]
    filtered = module._filter_prediction(list(prediction), excluded, history_desc)
    assert len(filtered) == 6
    assert set(filtered) <= set(prediction) | {44, 45, 46, 47, 48, 49}


# ─── graph centrality: donor-exact weighted degree/betweenness ────────────
# Expected values below were computed once against real networkx 3.6.1 in a
# throwaway, non-shipped environment (``nx.degree_centrality`` /
# ``nx.betweenness_centrality(G, weight='weight')``) -- see module docstring.
# No third-party graph library is available at test time or runtime; these
# are frozen regression fixtures, not a live comparison.


def test_degree_centrality_matches_networkx_on_a_path_graph() -> None:
    # Path 1-2-3-4-5: degree centrality = degree / (n-1).
    nodes = [1, 2, 3, 4, 5]
    adjacency = {
        1: {2: 1.0},
        2: {1: 1.0, 3: 1.0},
        3: {2: 1.0, 4: 1.0},
        4: {3: 1.0, 5: 1.0},
        5: {4: 1.0},
    }
    result = module._degree_centrality(nodes, adjacency)
    assert result == {1: 0.25, 2: 0.5, 3: 0.5, 4: 0.5, 5: 0.25}


def test_betweenness_centrality_matches_networkx_on_a_path_graph() -> None:
    # nx.betweenness_centrality on path 1-2-3-4-5 (unweighted, weight=1 edges):
    # {1: 0.0, 2: 0.5, 3: 0.6666666666666666, 4: 0.5, 5: 0.0}
    nodes = [1, 2, 3, 4, 5]
    adjacency = {
        1: {2: 1.0},
        2: {1: 1.0, 3: 1.0},
        3: {2: 1.0, 4: 1.0},
        4: {3: 1.0, 5: 1.0},
        5: {4: 1.0},
    }
    result = module._betweenness_centrality(nodes, adjacency)
    assert result[1] == pytest.approx(0.0)
    assert result[2] == pytest.approx(0.5)
    assert result[3] == pytest.approx(2.0 / 3.0)
    assert result[4] == pytest.approx(0.5)
    assert result[5] == pytest.approx(0.0)


def test_betweenness_centrality_weighted_prefers_the_shorter_weighted_path() -> None:
    # Two paths from 1 to 3: direct edge weight 10, or via 2 with weight 1+1=2.
    # The via-2 path is the Dijkstra shortest path (weight is distance, not
    # similarity -- matching nx.betweenness_centrality's own semantics), so
    # node 2 must have nonzero betweenness and node 4 (isolated) must be zero.
    nodes = [1, 2, 3, 4]
    adjacency = {
        1: {2: 1.0, 3: 10.0},
        2: {1: 1.0, 3: 1.0},
        3: {1: 10.0, 2: 1.0},
        4: {},
    }
    result = module._betweenness_centrality(nodes, adjacency)
    assert result[2] > 0.0
    assert result[4] == 0.0


def test_graph_adjacency_only_keeps_edges_at_or_above_the_cooccurrence_floor() -> None:
    history = _wave10_history(300)
    adjacency = module._graph_adjacency(history, lookback=250)
    assert set(adjacency.keys()) == set(range(1, 50))
    for node, neighbors in adjacency.items():
        for neighbor, weight in neighbors.items():
            assert adjacency[neighbor][node] == weight  # undirected symmetry
            assert weight > 0.0


# ─── shared: shape, determinism, RNG isolation, wrong lottery type, no I/O ──


@pytest.mark.parametrize("adapter_class", PORTFOLIO_ADAPTER_CLASSES)
def test_wave10_portfolio_shape(adapter_class: type[PortfolioBetAdapter]) -> None:
    history = _wave10_history(max(adapter_class().min_history, 1) + 250)
    bets = adapter_class().get_bets(history, LotteryType.BIG_LOTTO)
    assert len(bets) == adapter_class.native_ticket_count
    for ticket in bets:
        assert len(ticket) == 6
        assert len(set(ticket)) == 6
        assert ticket == tuple(sorted(ticket))
        assert all(1 <= number <= 49 for number in ticket)


@pytest.mark.parametrize("adapter_class", PORTFOLIO_ADAPTER_CLASSES)
def test_wave10_portfolio_repeated_execution_byte_equality(
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    history = _wave10_history(max(adapter_class().min_history, 1) + 250)
    first = adapter_class().get_bets(history, LotteryType.BIG_LOTTO)
    second = adapter_class().get_bets(history, LotteryType.BIG_LOTTO)
    assert first == second


def test_v6_seed_reset_is_isolated_from_global_random_state() -> None:
    """V6 resets its own local ``random.Random(42)`` every call (see module
    docstring) -- unlike wave 9's ZDP adapter, it must NOT depend on, or
    mutate, the process-global ``random`` module. Burning through the global
    stream between two calls must not change the result, and the global
    stream's own next value must be unaffected by having called the adapter."""

    import random as global_random

    history = _wave10_history(400)
    first = BigLottoDiversifiedEnsembleV6Adapter().get_bets(history, LotteryType.BIG_LOTTO)

    global_random.seed(1234)
    before = global_random.random()
    global_random.seed(1234)
    _ = BigLottoDiversifiedEnsembleV6Adapter().get_bets(history, LotteryType.BIG_LOTTO)
    after = global_random.random()
    assert before == after  # adapter call did not consume from the global stream

    for _ in range(1000):
        global_random.random()
    second = BigLottoDiversifiedEnsembleV6Adapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert first == second  # adapter result is unaffected by global stream state


@pytest.mark.parametrize("adapter_class", PORTFOLIO_ADAPTER_CLASSES)
def test_wave10_portfolio_rejects_wrong_lottery_type(
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    history = _wave10_history(max(adapter_class().min_history, 1) + 10)
    with pytest.raises(UnsupportedLotteryType):
        adapter_class().get_bets(history, LotteryType.POWER_LOTTO)


@pytest.mark.parametrize("adapter_class", PORTFOLIO_ADAPTER_CLASSES)
def test_wave10_portfolio_rejects_malformed_history_container(
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    with pytest.raises(InvalidOutput):
        adapter_class().get_bets(
            list(_wave10_history(max(adapter_class().min_history, 1) + 10)),  # type: ignore[arg-type]
            LotteryType.BIG_LOTTO,
        )


def test_wave10_adapters_need_no_filesystem_clock_database_or_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("external state access is forbidden")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(time, "time", forbidden)
    monkeypatch.setattr(time, "monotonic", forbidden)

    history = _wave10_history(750)
    assert (
        BigLottoEnhancedDualBetAdapter().get_bets(history, LotteryType.BIG_LOTTO)
        == DUAL_GOLDENS[750]
    )
    assert (
        BigLottoDiversifiedEnsembleV6Adapter().get_bets(history, LotteryType.BIG_LOTTO)
        == V6_GOLDENS[750]
    )
    assert (
        BigLottoBacktestStrategy1Adapter().get_bets(history, LotteryType.BIG_LOTTO)
        == BT1_GOLDENS[750]
    )


# ─── generate_bet use-case fail-closed / portfolio-path tests ──────────────


@pytest.mark.parametrize("strategy_id", sorted(WAVE10_IDS))
def test_generate_one_bet_fails_closed_for_wave10_portfolio_strategy(strategy_id: str) -> None:
    use_case = build_production_generate_one_bet()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id=strategy_id,
            lottery_type=LotteryType.BIG_LOTTO,
            history=_wave10_history(150),
        )
    )
    assert result.status is GenerateOneBetStatus.WRONG_RESPONSE_PATH
    assert result.reason_code is GenerateOneBetReason.STRATEGY_IS_PORTFOLIO
    assert result.numbers is None


def test_generate_one_bet_does_not_expose_wave10_portfolio_adapters() -> None:
    use_case = build_production_generate_one_bet()
    assert WAVE10_IDS.isdisjoint(use_case._adapters.keys())


def test_generate_portfolio_returns_complete_native_ticket_set_for_each_wave10_strategy() -> None:
    use_case = build_production_generate_portfolio()
    expected_counts = {
        "legacy_biglotto__enhanced_dual_bet_predictor__d5b3de348d01": 2,
        "legacy_biglotto__biglotto_diversified_ensemble_v6__8caaac8fcb5d": 3,
        "legacy_biglotto__backtest_strategy_1__41ed79a6de62": 2,
    }
    for strategy_id, expected_count in expected_counts.items():
        result = use_case.execute(
            GenerateOneBetInput(
                strategy_id=strategy_id,
                lottery_type=LotteryType.BIG_LOTTO,
                history=_wave10_history(150),
            )
        )
        assert result.status is GeneratePortfolioStatus.OK
        assert result.numbers is not None
        assert len(result.numbers) == expected_count


def test_all_wave10_strategies_are_reachable_through_exactly_one_response_path() -> None:
    one_bet = build_production_generate_one_bet()
    portfolio = build_production_generate_portfolio()
    reachable = set(one_bet._adapters.keys()) | set(portfolio._adapters.keys())
    assert reachable >= WAVE10_IDS
    assert set(one_bet._adapters.keys()) & set(portfolio._adapters.keys()) == set()


# ─── catalog / descriptor invariant tests ──────────────────────────────────


def test_production_catalog_wave10_descriptors_declare_expected_shapes() -> None:
    catalog = production_catalog()
    expected = {
        "legacy_biglotto__enhanced_dual_bet_predictor__d5b3de348d01": (2, 100),
        "legacy_biglotto__biglotto_diversified_ensemble_v6__8caaac8fcb5d": (3, 1),
        "legacy_biglotto__backtest_strategy_1__41ed79a6de62": (2, 1),
    }
    for strategy_id, (native_ticket_count, min_history) in expected.items():
        descriptor = catalog.get(strategy_id)
        assert descriptor.response_shape is ResponseShape.PORTFOLIO
        assert descriptor.native_ticket_count == native_ticket_count
        assert descriptor.executable is True
        assert descriptor.min_history == min_history


def test_production_catalog_now_has_forty_seven_descriptors() -> None:
    catalog = production_catalog()
    assert len(catalog) == 53


def test_production_catalog_has_exactly_forty_seven_big_lotto_online_strategies() -> None:
    from lottolab.domain.strategies import LifecycleStatus

    catalog = production_catalog()
    online = catalog.list(
        lottery_type=LotteryType.BIG_LOTTO, lifecycle_status=LifecycleStatus.ONLINE
    )
    assert len(online) == 53


def test_wave1_through_wave9_descriptors_are_unaffected_by_wave10() -> None:
    """The 44 pre-existing BIG_LOTTO descriptors and their declaration order
    must remain unchanged; wave 10's three new descriptors are appended
    strictly after them."""

    catalog = production_catalog()
    all_ids = tuple(descriptor.strategy_id for descriptor in catalog)
    assert len(all_ids) == 53
    pre_existing_ids = all_ids[:44]
    wave10_ids_in_order = all_ids[44:47]
    assert set(pre_existing_ids).isdisjoint(WAVE10_IDS)
    assert set(wave10_ids_in_order) == WAVE10_IDS
    assert wave10_ids_in_order == (
        "legacy_biglotto__enhanced_dual_bet_predictor__d5b3de348d01",
        "legacy_biglotto__biglotto_diversified_ensemble_v6__8caaac8fcb5d",
        "legacy_biglotto__backtest_strategy_1__41ed79a6de62",
    )


def test_wave9_descriptors_remain_present_and_unchanged() -> None:
    catalog = production_catalog()
    for strategy_id in (
        "legacy_biglotto__test_cag__7ca5343dfedd",
        "legacy_biglotto__test_cluster_cover__5b43959e7c55",
        "legacy_biglotto__test_zdp__e80cc7e95453",
    ):
        descriptor = catalog.get(strategy_id)
        assert descriptor.native_ticket_count == 3
        assert descriptor.min_history == 1
