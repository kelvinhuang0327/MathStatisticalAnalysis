"""Parity and contract tests for the BigLotto native-strategy wave 2 adapters.

Golden fixtures below were cross-verified by executing the actual frozen
donor source (commit 49a25effa62fc24f40789c16be6f11bdfb41a4a9, read-only
checkout) against the exact deterministic synthetic histories built by
``_wave2_history`` in this file: 8 history lengths x 7 tickets for
high_prize_trend, 8 history lengths x 12 tickets for core_satellite, and
6 history lengths x 54 tickets for auto_discovery -- 362 total ticket
comparisons across all three adapters, zero mismatches.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import builtins
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

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
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    PortfolioBetAdapter,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_wave2 import (
    BigLottoAutoDiscoveryAdapter,
    BigLottoCoreSatelliteAdapter,
    BigLottoHighPrizeTrendAdapter,
)
from lottolab.strategies.catalog import production_catalog

REPO_ROOT = Path(__file__).resolve().parents[2]

WAVE2_IDS = {
    "legacy_biglotto__high_prize_trend_optimizer__0fc72409150e",
    "legacy_biglotto__core_satellite__2e82891003b3",
    "legacy_biglotto__auto_discovery_biglotto__06bcb164db84",
}


def _wave2_row(index: int) -> CausalDrawRow:
    """Deterministic 6-of-49 draw. Stride 8 is coprime with 49, so six
    consecutive steps always land on six distinct residues — no collisions."""

    numbers = tuple(sorted(((index + step * 8) % 49) + 1 for step in range(6)))
    assert len(set(numbers)) == 6
    return CausalDrawRow(
        draw=f"w2-{index}",
        date=f"2020-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
        numbers=numbers,
    )


def _wave2_history(n: int) -> tuple[CausalDrawRow, ...]:
    return tuple(_wave2_row(i) for i in range(n))


PORTFOLIO_ADAPTER_CLASSES = (
    BigLottoHighPrizeTrendAdapter,
    BigLottoCoreSatelliteAdapter,
    BigLottoAutoDiscoveryAdapter,
)


# ─── high_prize_trend_optimizer goldens (portfolio, 7 native tickets) ──────

HIGH_PRIZE_TREND_GOLDENS: dict[int, tuple[tuple[int, ...], ...]] = {
    1: ((1, 9, 17, 25, 33, 41),) * 7,
    2: ((2, 10, 18, 26, 34, 42),) * 7,
    6: ((6, 14, 22, 30, 38, 46),) * 7,
    20: ((3, 11, 20, 28, 36, 44),) * 7,
    50: ((1, 9, 17, 25, 33, 41),) * 7,
    100: ((2, 10, 18, 26, 34, 42),) * 7,
    299: ((5, 13, 21, 29, 37, 45),) * 7,
    300: ((6, 14, 22, 30, 38, 46),) * 7,
    301: ((7, 15, 23, 31, 39, 47),) * 7,
    500: ((1, 10, 18, 26, 34, 42),) * 7,
    750: ((6, 15, 23, 31, 39, 47),) * 7,
}


@pytest.mark.parametrize("n", sorted(HIGH_PRIZE_TREND_GOLDENS))
def test_high_prize_trend_matches_frozen_donor_golden(n: int) -> None:
    history = _wave2_history(n)
    bets = BigLottoHighPrizeTrendAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert bets == HIGH_PRIZE_TREND_GOLDENS[n]


def test_high_prize_trend_minimum_history_boundary() -> None:
    with pytest.raises(InsufficientHistory):
        BigLottoHighPrizeTrendAdapter().get_bets((), LotteryType.BIG_LOTTO)
    assert (
        BigLottoHighPrizeTrendAdapter().get_bets(_wave2_history(1), LotteryType.BIG_LOTTO)
        == HIGH_PRIZE_TREND_GOLDENS[1]
    )


def test_high_prize_trend_recent_target_rolls_forward() -> None:
    outputs = {
        n: BigLottoHighPrizeTrendAdapter().get_bets(_wave2_history(n), LotteryType.BIG_LOTTO)
        for n in (299, 300, 301)
    }
    assert len({outputs[299], outputs[300], outputs[301]}) == 3


def test_high_prize_trend_seven_native_tickets_are_identical_by_construction() -> None:
    """All 7 lambda configurations rank the same weighted-frequency scores
    identically at these short synthetic histories (ties broken the same
    way for every lambda) -- this positional-duplicate structure must be
    preserved verbatim, never deduplicated by the base class."""
    bets = BigLottoHighPrizeTrendAdapter().get_bets(_wave2_history(50), LotteryType.BIG_LOTTO)
    assert len(bets) == 7
    assert len(set(bets)) == 1


def test_high_prize_trend_lambda_sweep_is_mutation_sensitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Proves the 7-lambda sweep is load-bearing: shrinking it to one lambda
    must change the native ticket count validation (caught fail-closed by
    the portfolio base class)."""
    from lottolab.strategies.adapters import biglotto_wave2 as module

    monkeypatch.setattr(module, "_HIGH_PRIZE_TREND_LAMBDAS", (0.05,))
    with pytest.raises(InvalidOutput):
        BigLottoHighPrizeTrendAdapter().get_bets(_wave2_history(300), LotteryType.BIG_LOTTO)


def test_high_prize_trend_lambda_value_is_mutation_sensitive() -> None:
    """Direct proof against the real scoring function that lambda is
    load-bearing: a history dominated by (1..6) with one anomalous most
    recent draw (44..49) is picked up entirely differently by a slow decay
    (rewards the long-run majority) versus a fast decay (rewards only the
    most recent draw)."""
    from lottolab.strategies.adapters.biglotto_wave2 import _high_prize_trend_predict

    def row(i: int, numbers: tuple[int, ...]) -> CausalDrawRow:
        return CausalDrawRow(draw=f"skew-{i}", date="2020-01-01", numbers=tuple(sorted(numbers)))

    history = (
        *(row(i, (1, 2, 3, 4, 5, 6)) for i in range(40)),
        row(40, (44, 45, 46, 47, 48, 49)),
    )
    slow_decay = _high_prize_trend_predict(history, 0.01)
    fast_decay = _high_prize_trend_predict(history, 5.0)
    assert slow_decay == (1, 2, 3, 4, 5, 6)
    assert fast_decay == (44, 45, 46, 47, 48, 49)
    assert slow_decay != fast_decay


# ─── core_satellite goldens (portfolio, 12 native tickets) ─────────────────

CORE_SATELLITE_GOLDENS: dict[int, tuple[tuple[int, ...], ...]] = {
    1: (
        (1, 9, 17, 25, 33, 41),
        (1, 2, 3, 4, 9, 17),
        (1, 5, 6, 7, 9, 17),
        (1, 9, 17, 25, 33, 41),
        (1, 2, 3, 4, 9, 17),
        (1, 5, 6, 7, 9, 17),
        (2, 3, 4, 5, 6, 7),
        (2, 3, 4, 8, 10, 11),
        (2, 3, 4, 12, 13, 14),
        (1, 2, 3, 4, 9, 17),
        (1, 2, 5, 9, 25, 33),
        (1, 2, 6, 7, 9, 41),
    ),
    2: (
        (1, 2, 9, 10, 17, 18),
        (1, 2, 9, 25, 26, 33),
        (1, 2, 9, 34, 41, 42),
        (1, 2, 9, 10, 17, 18),
        (1, 2, 9, 25, 26, 33),
        (1, 2, 9, 34, 41, 42),
        (3, 4, 5, 6, 7, 8),
        (3, 4, 5, 11, 12, 13),
        (3, 4, 5, 14, 15, 16),
        (1, 2, 3, 4, 5, 9),
        (1, 2, 3, 6, 10, 17),
        (1, 2, 3, 7, 8, 18),
    ),
    6: (
        (1, 2, 3, 4, 5, 6),
        (1, 2, 3, 9, 10, 11),
        (1, 2, 3, 12, 13, 14),
        (1, 2, 3, 4, 5, 6),
        (1, 2, 3, 9, 10, 11),
        (1, 2, 3, 12, 13, 14),
        (7, 8, 15, 16, 23, 24),
        (7, 8, 15, 31, 32, 39),
        (7, 8, 15, 40, 47, 48),
        (1, 2, 3, 7, 8, 15),
        (1, 2, 4, 5, 7, 16),
        (1, 2, 6, 7, 23, 24),
    ),
    20: (
        (1, 2, 3, 9, 10, 11),
        (1, 2, 3, 17, 18, 19),
        (1, 2, 3, 20, 25, 26),
        (1, 2, 3, 9, 10, 11),
        (1, 2, 3, 17, 18, 19),
        (1, 2, 3, 20, 25, 26),
        (4, 5, 6, 7, 8, 12),
        (4, 5, 6, 13, 14, 15),
        (4, 5, 6, 16, 21, 22),
        (1, 2, 3, 4, 5, 6),
        (1, 2, 4, 7, 9, 10),
        (1, 2, 4, 8, 11, 12),
    ),
    50: (
        (1, 4, 5, 6, 7, 8),
        (1, 4, 5, 9, 12, 13),
        (1, 4, 5, 14, 15, 16),
        (1, 4, 5, 6, 7, 8),
        (1, 4, 5, 9, 12, 13),
        (1, 4, 5, 14, 15, 16),
        (2, 3, 10, 11, 18, 19),
        (2, 3, 10, 20, 26, 27),
        (2, 3, 10, 28, 34, 35),
        (1, 2, 3, 4, 5, 10),
        (1, 2, 4, 6, 7, 11),
        (1, 2, 4, 8, 18, 19),
    ),
    100: (
        (1, 2, 5, 6, 7, 8),
        (1, 2, 5, 9, 10, 13),
        (1, 2, 5, 14, 15, 16),
        (1, 2, 5, 6, 7, 8),
        (1, 2, 5, 9, 10, 13),
        (1, 2, 5, 14, 15, 16),
        (3, 4, 11, 12, 19, 20),
        (3, 4, 11, 21, 27, 28),
        (3, 4, 11, 29, 35, 36),
        (1, 2, 3, 4, 5, 11),
        (1, 2, 3, 6, 7, 12),
        (1, 2, 3, 8, 19, 20),
    ),
    299: (
        (1, 2, 3, 4, 5, 8),
        (1, 2, 3, 9, 10, 11),
        (1, 2, 3, 12, 13, 16),
        (1, 2, 3, 4, 5, 8),
        (1, 2, 3, 9, 10, 11),
        (1, 2, 3, 12, 13, 16),
        (6, 7, 14, 15, 22, 23),
        (6, 7, 14, 24, 30, 31),
        (6, 7, 14, 32, 38, 39),
        (1, 2, 3, 6, 7, 14),
        (1, 2, 4, 5, 6, 15),
        (1, 2, 6, 8, 22, 23),
    ),
    300: (
        (1, 2, 3, 4, 5, 6),
        (1, 2, 3, 9, 10, 11),
        (1, 2, 3, 12, 13, 14),
        (1, 2, 3, 4, 5, 6),
        (1, 2, 3, 9, 10, 11),
        (1, 2, 3, 12, 13, 14),
        (7, 8, 15, 16, 23, 24),
        (7, 8, 15, 25, 31, 32),
        (7, 8, 15, 33, 39, 40),
        (1, 2, 3, 7, 8, 15),
        (1, 2, 4, 5, 7, 16),
        (1, 2, 6, 7, 23, 24),
    ),
    301: (
        (2, 3, 4, 5, 6, 7),
        (2, 3, 4, 10, 11, 12),
        (2, 3, 4, 13, 14, 15),
        (2, 3, 4, 5, 6, 7),
        (2, 3, 4, 10, 11, 12),
        (2, 3, 4, 13, 14, 15),
        (1, 8, 9, 16, 17, 24),
        (1, 8, 9, 25, 26, 32),
        (1, 8, 9, 33, 34, 40),
        (1, 2, 3, 4, 8, 9),
        (1, 2, 3, 5, 6, 16),
        (1, 2, 3, 7, 17, 24),
    ),
    500: (
        (1, 5, 6, 7, 8, 9),
        (1, 5, 6, 10, 13, 14),
        (1, 5, 6, 15, 16, 17),
        (1, 5, 6, 7, 8, 9),
        (1, 5, 6, 10, 13, 14),
        (1, 5, 6, 15, 16, 17),
        (2, 3, 4, 11, 12, 19),
        (2, 3, 4, 20, 27, 28),
        (2, 3, 4, 29, 35, 36),
        (1, 2, 3, 4, 5, 6),
        (1, 2, 5, 7, 8, 11),
        (1, 2, 5, 9, 12, 19),
    ),
    750: (
        (2, 3, 4, 5, 6, 10),
        (2, 3, 4, 11, 12, 13),
        (2, 3, 4, 14, 15, 18),
        (2, 3, 4, 5, 6, 10),
        (2, 3, 4, 11, 12, 13),
        (2, 3, 4, 14, 15, 18),
        (1, 7, 8, 9, 16, 17),
        (1, 7, 8, 24, 25, 32),
        (1, 7, 8, 33, 34, 40),
        (1, 2, 3, 4, 7, 8),
        (1, 2, 3, 5, 6, 9),
        (1, 2, 3, 10, 16, 17),
    ),
}


@pytest.mark.parametrize("n", sorted(CORE_SATELLITE_GOLDENS))
def test_core_satellite_matches_frozen_donor_golden(n: int) -> None:
    history = _wave2_history(n)
    bets = BigLottoCoreSatelliteAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert bets == CORE_SATELLITE_GOLDENS[n]


def test_core_satellite_minimum_history_boundary() -> None:
    with pytest.raises(InsufficientHistory):
        BigLottoCoreSatelliteAdapter().get_bets((), LotteryType.BIG_LOTTO)
    assert (
        BigLottoCoreSatelliteAdapter().get_bets(_wave2_history(1), LotteryType.BIG_LOTTO)
        == CORE_SATELLITE_GOLDENS[1]
    )


def test_core_satellite_recent_target_rolls_forward() -> None:
    outputs = {
        n: BigLottoCoreSatelliteAdapter().get_bets(_wave2_history(n), LotteryType.BIG_LOTTO)
        for n in (299, 300, 301)
    }
    assert len({outputs[299], outputs[300], outputs[301]}) == 3


def test_core_satellite_preserves_positional_duplicates_across_modes() -> None:
    """mid_frequency and hot rank identically at these short deterministic
    fixtures (ties broken the same way), so tickets 1-3 == tickets 4-6 by
    construction -- this must be preserved verbatim, never deduplicated."""
    for n in (1, 20, 300):
        bets = CORE_SATELLITE_GOLDENS[n]
        assert bets[0:3] == bets[3:6]


def test_core_satellite_four_mode_sweep_is_mutation_sensitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lottolab.strategies.adapters import biglotto_wave2 as module

    monkeypatch.setattr(module, "_CORE_SATELLITE_MODES", ("mid_frequency",))
    with pytest.raises(InvalidOutput):
        BigLottoCoreSatelliteAdapter().get_bets(_wave2_history(300), LotteryType.BIG_LOTTO)


def test_core_satellite_pool_mode_is_mutation_sensitive() -> None:
    """Direct proof against the real pool builder that 'hot' and 'cold' rank
    the candidate pool in genuinely opposite directions for a history with
    a clear frequency skew: their top-6 anchor candidates are disjoint."""
    from lottolab.strategies.adapters.biglotto_wave2 import _core_satellite_pool

    history = _wave2_history(300)
    hot_pool = _core_satellite_pool(history, 30, "hot")
    cold_pool = _core_satellite_pool(history, 30, "cold")
    assert hot_pool != cold_pool
    assert set(hot_pool[:6]).isdisjoint(cold_pool[:6])


def test_core_satellite_num_anchors_is_mutation_sensitive() -> None:
    """Direct proof against the real bet builder that num_anchors controls
    how many numbers are shared (anchored) across every native ticket."""
    from lottolab.strategies.adapters.biglotto_wave2 import (
        _core_satellite_generate,
        _core_satellite_pool,
    )

    pool = _core_satellite_pool(_wave2_history(300), 30, "mid_frequency")
    two_anchor_bets = _core_satellite_generate(pool, 3, 2, 6)
    three_anchor_bets = _core_satellite_generate(pool, 3, 3, 6)
    two_anchor_core = set(two_anchor_bets[0]) & set(two_anchor_bets[1]) & set(two_anchor_bets[2])
    three_anchor_core = (
        set(three_anchor_bets[0]) & set(three_anchor_bets[1]) & set(three_anchor_bets[2])
    )
    assert len(two_anchor_core) == 2
    assert len(three_anchor_core) == 3
    assert two_anchor_bets != three_anchor_bets


# ─── auto_discovery_biglotto goldens (portfolio, 54 native tickets) ────────

AUTO_DISCOVERY_GOLDENS: dict[int, tuple[tuple[int, ...], ...]] = {
    50: (
        (4, 5, 12, 13, 45, 46),
        (1, 9, 17, 25, 33, 41),
        (1, 9, 17, 25, 33, 41),
        (1, 9, 17, 25, 33, 41),
        (2, 10, 18, 26, 34, 43),
        (2, 10, 18, 26, 34, 42),
        (2, 10, 18, 26, 34, 42),
        (2, 3, 4, 5, 6, 7),
        (2, 3, 4, 5, 6, 7),
        (2, 3, 4, 5, 6, 7),
        (1, 9, 17, 25, 33, 41),
        (1, 9, 17, 25, 33, 41),
        (2, 10, 18, 26, 34, 43),
        (2, 10, 18, 26, 34, 42),
        (2, 10, 18, 26, 34, 42),
        (1, 9, 17, 25, 34, 41),
        (1, 9, 17, 25, 34, 41),
        (1, 9, 17, 25, 34, 41),
        (1, 4, 5, 45, 46, 47),
        (1, 9, 17, 25, 48, 49),
        (1, 9, 17, 25, 48, 49),
        (2, 4, 6, 8, 10, 12),
        (2, 4, 6, 8, 10, 12),
        (2, 4, 6, 8, 10, 12),
        (2, 10, 18, 26, 34, 42),
        (2, 10, 18, 26, 34, 42),
        (2, 3, 4, 5, 6, 7),
        (2, 3, 4, 5, 6, 7),
        (2, 3, 4, 5, 6, 7),
        (2, 3, 4, 5, 6, 7),
        (2, 3, 4, 5, 6, 7),
        (5, 6, 7, 8, 13, 14),
        (5, 6, 7, 8, 13, 14),
        (4, 5, 6, 7, 8, 12),
        (2, 3, 4, 5, 6, 7),
        (2, 3, 4, 5, 6, 7),
        (7, 15, 23, 31, 39, 48),
        (23, 24, 25, 31, 32, 33),
        (15, 16, 17, 21, 22, 23),
        (6, 7, 8, 10, 11, 12),
        (1, 9, 17, 25, 34, 41),
        (1, 9, 17, 25, 34, 41),
        (1, 9, 17, 25, 34, 41),
        (1, 4, 17, 21, 37, 38),
        (1, 9, 17, 25, 34, 41),
        (1, 9, 17, 25, 34, 41),
        (1, 9, 17, 25, 33, 41),
        (1, 9, 17, 25, 33, 41),
        (1, 9, 17, 25, 33, 41),
        (1, 2, 3, 4, 5, 6),
        (1, 2, 3, 4, 5, 6),
        (1, 9, 17, 25, 33, 41),
        (1, 9, 17, 25, 33, 41),
        (1, 9, 17, 25, 33, 41),
    ),
    51: (
        (5, 6, 13, 14, 46, 47),
        (2, 10, 18, 26, 34, 42),
        (1, 9, 17, 25, 33, 41),
        (1, 9, 17, 25, 33, 41),
        (3, 11, 19, 27, 35, 44),
        (3, 11, 19, 27, 35, 43),
        (3, 11, 19, 27, 35, 43),
        (1, 3, 4, 5, 6, 7),
        (3, 4, 5, 6, 7, 8),
        (3, 4, 5, 6, 7, 8),
        (2, 10, 18, 26, 34, 42),
        (1, 9, 17, 25, 33, 41),
        (3, 11, 19, 27, 35, 44),
        (3, 11, 19, 27, 35, 43),
        (3, 11, 19, 27, 35, 43),
        (1, 2, 17, 18, 34, 41),
        (1, 2, 17, 18, 34, 41),
        (1, 2, 17, 18, 34, 41),
        (1, 2, 5, 42, 48, 49),
        (1, 2, 10, 18, 26, 42),
        (1, 2, 9, 41, 45, 46),
        (1, 3, 5, 7, 9, 11),
        (1, 9, 17, 25, 33, 41),
        (1, 9, 17, 25, 33, 41),
        (3, 11, 19, 27, 35, 43),
        (2, 10, 18, 26, 34, 42),
        (1, 3, 4, 5, 6, 7),
        (1, 9, 17, 25, 33, 41),
        (1, 9, 17, 25, 33, 41),
        (1, 3, 4, 5, 6, 7),
        (1, 9, 17, 25, 33, 41),
        (1, 6, 7, 8, 9, 14),
        (6, 7, 8, 14, 15, 16),
        (1, 5, 6, 7, 8, 9),
        (1, 3, 4, 5, 6, 7),
        (1, 9, 17, 25, 33, 41),
        (8, 16, 24, 32, 40, 49),
        (23, 24, 25, 26, 32, 33),
        (15, 16, 17, 18, 22, 23),
        (6, 7, 8, 9, 11, 12),
        (2, 10, 18, 26, 34, 42),
        (1, 2, 17, 18, 34, 41),
        (1, 2, 17, 18, 34, 41),
        (1, 2, 17, 18, 34, 38),
        (2, 10, 18, 26, 34, 42),
        (1, 2, 17, 18, 34, 41),
        (2, 10, 18, 26, 34, 42),
        (1, 9, 17, 25, 33, 41),
        (1, 9, 17, 25, 33, 41),
        (1, 2, 3, 4, 5, 6),
        (1, 2, 3, 4, 5, 6),
        (2, 10, 18, 26, 34, 42),
        (2, 10, 18, 25, 33, 41),
        (2, 10, 18, 25, 33, 41),
    ),
    500: (
        (5, 6, 13, 14, 21, 22),
        (1, 10, 18, 26, 34, 42),
        (9, 17, 25, 33, 41, 49),
        (7, 15, 23, 31, 39, 47),
        (3, 11, 19, 27, 35, 43),
        (2, 11, 19, 27, 35, 43),
        (2, 11, 19, 27, 35, 43),
        (2, 3, 4, 5, 6, 7),
        (2, 3, 4, 5, 6, 7),
        (2, 3, 4, 5, 6, 11),
        (1, 10, 18, 26, 34, 42),
        (9, 17, 25, 33, 41, 49),
        (3, 11, 19, 27, 35, 43),
        (2, 11, 19, 27, 35, 43),
        (2, 11, 19, 27, 35, 43),
        (1, 9, 17, 18, 34, 41),
        (1, 7, 17, 18, 34, 39),
        (1, 9, 17, 18, 34, 41),
        (1, 5, 6, 42, 48, 49),
        (1, 10, 18, 26, 46, 47),
        (1, 2, 9, 10, 34, 49),
        (1, 3, 5, 7, 9, 10),
        (1, 9, 10, 17, 25, 33),
        (1, 7, 8, 9, 15, 17),
        (2, 11, 19, 27, 35, 43),
        (1, 10, 18, 26, 34, 42),
        (2, 3, 4, 5, 6, 7),
        (9, 17, 25, 33, 41, 49),
        (8, 9, 16, 17, 24, 25),
        (2, 3, 4, 5, 6, 7),
        (9, 17, 25, 33, 41, 49),
        (6, 7, 8, 9, 14, 15),
        (6, 7, 8, 14, 15, 16),
        (5, 6, 7, 8, 9, 13),
        (2, 3, 4, 5, 6, 7),
        (9, 17, 25, 33, 41, 49),
        (8, 16, 24, 32, 40, 48),
        (24, 25, 26, 31, 32, 33),
        (16, 17, 18, 21, 22, 23),
        (6, 7, 8, 9, 11, 12),
        (1, 10, 18, 26, 34, 42),
        (1, 9, 17, 18, 34, 41),
        (1, 7, 17, 18, 34, 39),
        (1, 5, 17, 18, 34, 38),
        (1, 10, 18, 26, 34, 42),
        (1, 9, 17, 18, 34, 41),
        (1, 10, 18, 26, 34, 42),
        (9, 17, 25, 33, 41, 49),
        (7, 15, 23, 31, 39, 47),
        (1, 2, 3, 4, 5, 6),
        (1, 2, 3, 4, 5, 6),
        (1, 10, 18, 26, 34, 42),
        (10, 18, 26, 33, 41, 49),
        (10, 18, 26, 31, 39, 47),
    ),
    750: (
        (10, 11, 18, 19, 26, 27),
        (6, 15, 23, 31, 39, 47),
        (5, 14, 22, 30, 38, 46),
        (3, 12, 20, 28, 36, 44),
        (8, 16, 24, 32, 40, 48),
        (7, 16, 24, 32, 40, 48),
        (7, 16, 24, 32, 40, 48),
        (1, 2, 3, 4, 5, 7),
        (1, 2, 3, 4, 7, 8),
        (1, 2, 7, 8, 9, 10),
        (6, 15, 23, 31, 39, 47),
        (5, 14, 22, 30, 38, 46),
        (8, 16, 24, 32, 40, 48),
        (7, 16, 24, 32, 40, 48),
        (7, 16, 24, 32, 40, 48),
        (5, 6, 22, 23, 38, 39),
        (3, 4, 20, 21, 36, 37),
        (6, 14, 22, 23, 38, 39),
        (2, 3, 4, 44, 48, 49),
        (6, 15, 23, 31, 39, 47),
        (5, 6, 14, 30, 46, 47),
        (2, 4, 6, 8, 10, 15),
        (5, 6, 14, 22, 30, 38),
        (3, 4, 6, 12, 14, 20),
        (7, 16, 24, 32, 40, 48),
        (6, 15, 23, 31, 39, 47),
        (1, 2, 3, 4, 5, 7),
        (5, 14, 22, 30, 38, 46),
        (4, 5, 13, 14, 21, 22),
        (1, 2, 3, 4, 5, 7),
        (5, 14, 22, 30, 38, 46),
        (2, 3, 4, 5, 11, 12),
        (2, 3, 4, 11, 12, 13),
        (2, 3, 4, 5, 10, 11),
        (1, 2, 3, 4, 5, 7),
        (5, 14, 22, 30, 38, 46),
        (4, 13, 21, 29, 37, 45),
        (23, 28, 29, 30, 31, 36),
        (15, 18, 19, 20, 21, 22),
        (5, 7, 8, 9, 10, 11),
        (6, 15, 23, 31, 39, 47),
        (5, 6, 22, 23, 38, 39),
        (3, 4, 20, 21, 36, 37),
        (2, 3, 18, 19, 35, 36),
        (6, 15, 23, 31, 39, 47),
        (5, 6, 22, 23, 38, 39),
        (6, 15, 23, 31, 39, 47),
        (5, 14, 22, 30, 38, 46),
        (3, 12, 20, 28, 36, 44),
        (1, 2, 3, 4, 5, 6),
        (1, 2, 3, 4, 5, 6),
        (6, 15, 23, 31, 39, 47),
        (5, 15, 23, 31, 38, 46),
        (3, 15, 23, 31, 36, 44),
    ),
}


@pytest.mark.parametrize("n", sorted(AUTO_DISCOVERY_GOLDENS))
def test_auto_discovery_matches_frozen_donor_golden(n: int) -> None:
    history = _wave2_history(n)
    bets = BigLottoAutoDiscoveryAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert bets == AUTO_DISCOVERY_GOLDENS[n]


def test_auto_discovery_minimum_history_boundary() -> None:
    with pytest.raises(InsufficientHistory):
        BigLottoAutoDiscoveryAdapter().get_bets(_wave2_history(49), LotteryType.BIG_LOTTO)
    assert (
        BigLottoAutoDiscoveryAdapter().get_bets(_wave2_history(50), LotteryType.BIG_LOTTO)
        == AUTO_DISCOVERY_GOLDENS[50]
    )


def test_auto_discovery_50_vs_51_rows_window_is_mutation_sensitive() -> None:
    assert AUTO_DISCOVERY_GOLDENS[50] != AUTO_DISCOVERY_GOLDENS[51]


def test_auto_discovery_native_ticket_count_and_order_is_fixed() -> None:
    """54 tickets, always in the donor's own ``build_methods()`` insertion
    order (dimension A through F, each method's own declared window sweep)."""
    for n in (50, 500, 750):
        bets = BigLottoAutoDiscoveryAdapter().get_bets(_wave2_history(n), LotteryType.BIG_LOTTO)
        assert len(bets) == 54
        assert bets == AUTO_DISCOVERY_GOLDENS[n]


def test_auto_discovery_preserves_positional_duplicates_across_configurations() -> None:
    """Several dimension-A/F window variants rank identically at these
    deterministic fixtures by construction -- this must be preserved
    verbatim, never deduplicated across the 54-ticket portfolio."""
    bets = AUTO_DISCOVERY_GOLDENS[50]
    assert bets[1] == bets[2] == bets[3]  # A1_cooc_pairs_w{50,100,200}
    assert bets[7] == bets[8] == bets[9]  # A3_cooc_anti_w{50,100,200}


def test_auto_discovery_dimension_a1_window_is_mutation_sensitive() -> None:
    """Direct proof against the real candidate function that the window
    parameter is load-bearing for dimension A1."""
    from lottolab.strategies.adapters.biglotto_wave2 import _ad_cooccurrence_top_pairs

    history = _wave2_history(750)
    narrow = _ad_cooccurrence_top_pairs(history, window=30)
    wide = _ad_cooccurrence_top_pairs(history, window=200)
    assert narrow != wide


def test_auto_discovery_method_sweep_is_mutation_sensitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lottolab.strategies.adapters import biglotto_wave2 as module

    monkeypatch.setattr(module, "_AUTO_DISCOVERY_METHODS", module._AUTO_DISCOVERY_METHODS[:10])
    with pytest.raises(InvalidOutput):
        BigLottoAutoDiscoveryAdapter().get_bets(_wave2_history(300), LotteryType.BIG_LOTTO)


def test_auto_discovery_wrong_native_ticket_count_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lottolab.strategies.adapters import biglotto_wave2 as module

    def short_predict_all(
        self: object, history: object, lottery_type: object
    ) -> tuple[tuple[int, ...], ...]:
        return ((1, 2, 3, 4, 5, 6),)

    monkeypatch.setattr(module.BigLottoAutoDiscoveryAdapter, "_predict_all", short_predict_all)
    with pytest.raises(InvalidOutput):
        BigLottoAutoDiscoveryAdapter().get_bets(_wave2_history(50), LotteryType.BIG_LOTTO)


# ─── shared: closure, repeated-execution byte equality, wrong lottery type ─


@pytest.mark.parametrize("adapter_class", PORTFOLIO_ADAPTER_CLASSES)
def test_wave2_portfolio_closure(adapter_class: type[PortfolioBetAdapter]) -> None:
    history = _wave2_history(max(adapter_class().min_history, 1) + 250)
    bets = adapter_class().get_bets(history, LotteryType.BIG_LOTTO)
    assert len(bets) == adapter_class.native_ticket_count
    for ticket in bets:
        assert len(ticket) == 6
        assert len(set(ticket)) == 6
        assert ticket == tuple(sorted(ticket))
        assert all(1 <= n <= 49 for n in ticket)


@pytest.mark.parametrize("adapter_class", PORTFOLIO_ADAPTER_CLASSES)
def test_wave2_portfolio_repeated_execution_byte_equality(
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    history = _wave2_history(max(adapter_class().min_history, 1) + 250)
    first = adapter_class().get_bets(history, LotteryType.BIG_LOTTO)
    second = adapter_class().get_bets(history, LotteryType.BIG_LOTTO)
    assert first == second


@pytest.mark.parametrize("adapter_class", PORTFOLIO_ADAPTER_CLASSES)
def test_wave2_portfolio_rejects_wrong_lottery_type(
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    history = _wave2_history(max(adapter_class().min_history, 1) + 10)
    with pytest.raises(UnsupportedLotteryType):
        adapter_class().get_bets(history, LotteryType.POWER_LOTTO)


def test_wave2_adapters_need_no_filesystem_clock_database_or_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("external state access is forbidden")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(time, "time", forbidden)
    monkeypatch.setattr(time, "monotonic", forbidden)

    history = _wave2_history(750)
    assert (
        BigLottoHighPrizeTrendAdapter().get_bets(history, LotteryType.BIG_LOTTO)
        == HIGH_PRIZE_TREND_GOLDENS[750]
    )
    assert (
        BigLottoCoreSatelliteAdapter().get_bets(history, LotteryType.BIG_LOTTO)
        == CORE_SATELLITE_GOLDENS[750]
    )
    assert (
        BigLottoAutoDiscoveryAdapter().get_bets(history, LotteryType.BIG_LOTTO)
        == AUTO_DISCOVERY_GOLDENS[750]
    )


def test_subprocess_repeatability_across_python_hash_seeds() -> None:
    code = """
import sys
sys.path.insert(0, {src!r})
from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.adapters.biglotto_wave2 import (
    BigLottoAutoDiscoveryAdapter, BigLottoCoreSatelliteAdapter, BigLottoHighPrizeTrendAdapter,
)

def row(i):
    numbers = tuple(sorted(((i + s * 8) % 49) + 1 for s in range(6)))
    draw = f"w2-{{i}}"
    date = f"2020-{{(i%12)+1:02d}}-{{(i%28)+1:02d}}"
    return CausalDrawRow(draw=draw, date=date, numbers=numbers)

history = tuple(row(i) for i in range(300))
outputs = [
    BigLottoHighPrizeTrendAdapter().get_bets(history, LotteryType.BIG_LOTTO),
    BigLottoCoreSatelliteAdapter().get_bets(history, LotteryType.BIG_LOTTO),
    BigLottoAutoDiscoveryAdapter().get_bets(history, LotteryType.BIG_LOTTO),
]
print(outputs)
"""
    src = str(REPO_ROOT / "src")
    outputs: list[str] = []
    for hash_seed in ("1", "9173"):
        environment = {**os.environ, "PYTHONHASHSEED": hash_seed}
        completed = subprocess.run(
            [sys.executable, "-B", "-c", code.format(src=src)],
            cwd=REPO_ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        outputs.append(completed.stdout)
    assert outputs[0] == outputs[1]


# ─── generate_bet use-case fail-closed / portfolio-path tests ──────────────


@pytest.mark.parametrize("strategy_id", sorted(WAVE2_IDS))
def test_generate_one_bet_fails_closed_for_wave2_portfolio_strategy(strategy_id: str) -> None:
    use_case = build_production_generate_one_bet()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id=strategy_id,
            lottery_type=LotteryType.BIG_LOTTO,
            history=_wave2_history(50),
        )
    )
    assert result.status is GenerateOneBetStatus.WRONG_RESPONSE_PATH
    assert result.reason_code is GenerateOneBetReason.STRATEGY_IS_PORTFOLIO
    assert result.numbers is None


def test_generate_one_bet_does_not_expose_wave2_portfolio_adapters() -> None:
    use_case = build_production_generate_one_bet()
    assert WAVE2_IDS.isdisjoint(use_case._adapters.keys())


def test_generate_portfolio_returns_complete_native_ticket_set_for_each_wave2_strategy() -> None:
    use_case = build_production_generate_portfolio()
    for strategy_id, expected_count in (
        ("legacy_biglotto__high_prize_trend_optimizer__0fc72409150e", 7),
        ("legacy_biglotto__core_satellite__2e82891003b3", 12),
        ("legacy_biglotto__auto_discovery_biglotto__06bcb164db84", 54),
    ):
        result = use_case.execute(
            GenerateOneBetInput(
                strategy_id=strategy_id,
                lottery_type=LotteryType.BIG_LOTTO,
                history=_wave2_history(100),
            )
        )
        assert result.status is GeneratePortfolioStatus.OK
        assert result.numbers is not None
        assert len(result.numbers) == expected_count


def test_all_wave2_strategies_are_reachable_through_exactly_one_response_path() -> None:
    one_bet = build_production_generate_one_bet()
    portfolio = build_production_generate_portfolio()
    reachable = set(one_bet._adapters.keys()) | set(portfolio._adapters.keys())
    assert reachable >= WAVE2_IDS
    assert set(one_bet._adapters.keys()) & set(portfolio._adapters.keys()) == set()


def test_generate_portfolio_unknown_strategy_still_fails_closed() -> None:
    use_case = build_production_generate_portfolio()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id="does_not_exist",
            lottery_type=LotteryType.BIG_LOTTO,
            history=_wave2_history(50),
        )
    )
    assert result.status is GeneratePortfolioStatus.STRATEGY_UNAVAILABLE
    assert result.reason_code is GeneratePortfolioReason.UNKNOWN_STRATEGY


# ─── catalog / descriptor invariant tests ──────────────────────────────────


def test_production_catalog_wave2_descriptors_declare_expected_shapes() -> None:
    catalog = production_catalog()
    expected_counts = {
        "legacy_biglotto__high_prize_trend_optimizer__0fc72409150e": 7,
        "legacy_biglotto__core_satellite__2e82891003b3": 12,
        "legacy_biglotto__auto_discovery_biglotto__06bcb164db84": 54,
    }
    for strategy_id, native_ticket_count in expected_counts.items():
        descriptor = catalog.get(strategy_id)
        assert descriptor.response_shape is ResponseShape.PORTFOLIO
        assert descriptor.native_ticket_count == native_ticket_count
        assert descriptor.executable is True


def test_production_catalog_now_has_sixteen_descriptors() -> None:
    catalog = production_catalog()
    assert len(catalog) == 16


def test_wave1_and_pre_wave1_descriptors_are_unaffected_by_wave2() -> None:
    """Existing 13 adapters and their outputs must remain unchanged."""
    catalog = production_catalog()
    pre_existing_single_ticket_ids = (
        "biglotto_social_wisdom_anti_popularity",
        "biglotto_zone_split_3bet_bet1",
        "biglotto_zone_split_3bet_bet2",
        "biglotto_zone_split_3bet_bet3",
        "biglotto_deviation_2bet",
        "biglotto_deviation_2bet_bet2",
        "biglotto_p0_2bet_bet1",
        "biglotto_p0_2bet_bet2",
        "legacy_biglotto__graph_predictor__cd70713a5709",
        "legacy_biglotto__backtest_must_hit__909c91fd2fd0",
        "legacy_biglotto__dynamic_frequency_predictor__36e5bf9998ac",
        "legacy_biglotto__hot_cooccurrence_analyzer__48121f27d7ee",
    )
    for strategy_id in pre_existing_single_ticket_ids:
        descriptor = catalog.get(strategy_id)
        assert descriptor.response_shape is ResponseShape.SINGLE_TICKET
        assert descriptor.native_ticket_count == 1
    echo_phase2 = catalog.get("legacy_biglotto__predict_biglotto_echo_phase2__51c44b5c13d4")
    assert echo_phase2.response_shape is ResponseShape.PORTFOLIO
    assert echo_phase2.native_ticket_count == 5
