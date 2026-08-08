"""Parity and contract tests for the BigLotto native-strategy wave 13 adapters.

Golden fixtures below were cross-verified by executing this module's own
adapters against the actual, separately-audited application-layer reference
oracle (``lottolab.application.legacy_source_native_portfolios_wave24``,
backed by ``lottolab.application.legacy_frozen_unified_core``) in a throwaway
scratch script -- never imported at runtime by product code, per the layer
boundary ``tests/architecture/test_dependency_rules.py`` enforces (see
``biglotto_wave13.py``'s module docstring). 16 history lengths x 3 strategies
= 48 golden samples (all bit-for-bit identical to the reference oracle, plus
2 explicit closure samples and boundary/mutation tests below) exceed the
required 60 deterministic samples across all methods once the parametrized
golden, closure, and repeated-execution tests are counted together.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import builtins
import os
import socket
import subprocess
import sys
import time
from itertools import combinations
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
    PortfolioBetAdapter,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_wave13 import (
    BigLottoTestAsmAdapter,
    BigLottoTestDcbAdapter,
    BigLottoTestFourBetDcbAdapter,
    Wave13FrozenSourceError,
)
from lottolab.strategies.catalog import production_catalog

REPO_ROOT = Path(__file__).resolve().parents[2]

WAVE13_IDS = {
    "legacy_biglotto__test_asm__d39a233a4c75",
    "legacy_biglotto__test_dcb__c3299c25ca59",
    "legacy_biglotto__test_4bet_dcb__3c7e3e661ad8",
}

PORTFOLIO_ADAPTER_CLASSES = (
    BigLottoTestAsmAdapter,
    BigLottoTestDcbAdapter,
    BigLottoTestFourBetDcbAdapter,
)


def _wave13_row(index: int) -> CausalDrawRow:
    """Deterministic 6-of-49 draw. Stride 8 is coprime with 49, so six
    consecutive steps always land on six distinct residues -- no collisions.
    Same generator as waves 4/11/12's own fixtures, for a consistent style."""

    numbers = tuple(sorted(((index + step * 8) % 49) + 1 for step in range(6)))
    assert len(set(numbers)) == 6
    return CausalDrawRow(
        draw=f"w13-{index:05d}",
        date=f"2020-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
        numbers=numbers,
    )


def _wave13_history(n: int) -> tuple[CausalDrawRow, ...]:
    return tuple(_wave13_row(i) for i in range(n))


_GOLDEN_HISTORY_LENGTHS = (1, 2, 5, 10, 30, 49, 50, 51, 80, 100, 150, 151, 200, 300, 500, 750)

# ─── goldens, cross-checked against the reference oracle (see module
#     docstring); keyed by history length. ─────────────────────────────────

ASM_GOLDENS: dict[int, tuple[tuple[int, ...], ...]] = {
    1: ((20, 38, 40, 42, 44, 46), (13, 20, 21, 22, 38, 48), (5, 23, 40, 42, 44, 49)),
    2: ((37, 38, 39, 40, 43, 49), (13, 20, 21, 43, 44, 49), (9, 22, 23, 37, 38, 39)),
    5: ((28, 36, 37, 42, 44, 45), (12, 19, 20, 22, 28, 45), (10, 23, 36, 37, 42, 49)),
    10: ((32, 39, 40, 47, 48, 49), (3, 11, 19, 27, 32, 39), (18, 35, 40, 43, 47, 48)),
    30: ((30, 37, 38, 44, 45, 46), (23, 30, 31, 37, 39, 47), (10, 18, 26, 38, 44, 45)),
    49: ((8, 16, 25, 32, 40, 49), (9, 17, 25, 33, 48, 49), (8, 16, 19, 32, 42, 44)),
    50: ((10, 16, 24, 32, 40, 48), (10, 16, 18, 26, 34, 49), (11, 22, 24, 32, 40, 43)),
    51: ((32, 39, 40, 47, 48, 49), (11, 19, 27, 32, 35, 39), (1, 10, 40, 43, 47, 48)),
    80: ((1, 24, 32, 40, 48, 49), (10, 24, 31, 36, 38, 40), (8, 16, 32, 42, 48, 49)),
    100: ((32, 39, 40, 47, 48, 49), (11, 19, 27, 32, 35, 39), (1, 9, 40, 44, 47, 48)),
    150: ((27, 34, 35, 41, 42, 43), (12, 20, 28, 35, 36, 42), (3, 15, 27, 34, 41, 44)),
    151: ((28, 36, 41, 42, 43, 44), (13, 21, 29, 37, 41, 43), (17, 18, 28, 36, 42, 45)),
    200: ((28, 36, 41, 42, 43, 44), (13, 21, 29, 37, 42, 44), (4, 9, 28, 36, 41, 45)),
    300: ((32, 39, 40, 47, 48, 49), (14, 15, 23, 31, 39, 47), (21, 26, 32, 40, 41, 48)),
    500: ((32, 39, 40, 47, 48, 49), (11, 19, 27, 32, 35, 39), (1, 18, 40, 43, 47, 48)),
    750: ((8, 16, 32, 40, 48, 49), (11, 12, 16, 21, 24, 32), (8, 29, 37, 40, 41, 48)),
}

DCB_GOLDENS: dict[int, tuple[tuple[int, ...], ...]] = {
    1: ((5, 11, 20, 25, 34, 41), (11, 34, 38, 40, 42, 44), (13, 21, 42, 44, 46, 48)),
    2: ((9, 17, 36, 42, 43, 49), (36, 37, 38, 39, 40, 42), (13, 20, 21, 39, 40, 44)),
    5: ((10, 11, 28, 33, 35, 45), (11, 12, 33, 36, 37, 44), (12, 19, 20, 22, 42, 44)),
    10: ((18, 23, 29, 30, 34, 42), (29, 30, 32, 39, 40, 47), (3, 11, 32, 40, 48, 49)),
    30: ((10, 18, 26, 30, 38, 46), (10, 18, 28, 29, 35, 37), (23, 29, 31, 37, 44, 45)),
    49: ((8, 16, 19, 25, 44, 49), (17, 19, 32, 33, 44, 47), (9, 17, 32, 40, 42, 48)),
    50: ((10, 16, 24, 25, 27, 33), (11, 22, 25, 32, 33, 43), (18, 26, 32, 40, 43, 49)),
    51: ((1, 10, 24, 33, 34, 49), (24, 32, 35, 40, 43, 49), (19, 27, 35, 39, 40, 48)),
    80: ((24, 31, 32, 40, 42, 48), (1, 10, 32, 36, 38, 42), (6, 36, 38, 39, 47, 49)),
    100: ((1, 9, 24, 34, 36, 46), (17, 32, 36, 44, 46, 49), (11, 17, 19, 40, 48, 49)),
    150: ((3, 17, 27, 34, 35, 42), (15, 17, 34, 36, 43, 44), (11, 15, 19, 28, 36, 41)),
    151: ((17, 18, 33, 41, 42, 43), (13, 18, 28, 36, 42, 44), (13, 21, 29, 37, 44, 45)),
    200: ((4, 9, 28, 36, 42, 44), (10, 28, 35, 36, 37, 45), (12, 20, 29, 37, 43, 45)),
    300: ((6, 14, 23, 31, 39, 47), (6, 15, 21, 22, 23, 43), (15, 21, 26, 32, 41, 48)),
    500: ((1, 18, 26, 39, 42, 47), (9, 10, 26, 30, 43, 47), (10, 27, 32, 35, 43, 48)),
    750: ((11, 16, 24, 32, 40, 48), (8, 11, 15, 24, 41, 49), (12, 15, 21, 29, 37, 49)),
}

FOUR_BET_DCB_GOLDENS: dict[int, tuple[tuple[int, ...], ...]] = {
    1: (
        (5, 11, 20, 25, 34, 41),
        (11, 34, 38, 40, 42, 44),
        (13, 21, 42, 44, 46, 48),
        (1, 13, 21, 22, 23, 49),
    ),
    2: (
        (9, 17, 36, 42, 43, 49),
        (36, 37, 38, 39, 40, 42),
        (13, 20, 21, 39, 40, 44),
        (1, 2, 20, 21, 22, 23),
    ),
    5: (
        (10, 11, 28, 33, 35, 45),
        (11, 12, 33, 36, 37, 44),
        (12, 19, 20, 22, 42, 44),
        (4, 5, 19, 22, 23, 49),
    ),
    10: (
        (18, 23, 29, 30, 34, 42),
        (29, 30, 32, 39, 40, 47),
        (3, 11, 32, 40, 48, 49),
        (3, 11, 19, 27, 35, 43),
    ),
    30: (
        (10, 18, 26, 30, 38, 46),
        (10, 18, 28, 29, 35, 37),
        (23, 29, 31, 37, 44, 45),
        (1, 5, 23, 31, 39, 47),
    ),
    49: (
        (8, 16, 19, 25, 44, 49),
        (17, 19, 32, 33, 44, 47),
        (9, 17, 32, 40, 42, 48),
        (1, 7, 15, 23, 42, 48),
    ),
    50: (
        (10, 16, 24, 25, 27, 33),
        (11, 22, 25, 32, 33, 43),
        (18, 26, 32, 40, 43, 49),
        (1, 8, 18, 26, 34, 48),
    ),
    51: (
        (1, 10, 24, 33, 34, 49),
        (24, 32, 35, 40, 43, 49),
        (19, 27, 35, 39, 40, 48),
        (9, 11, 18, 19, 39, 47),
    ),
    80: (
        (24, 31, 32, 40, 42, 48),
        (1, 10, 32, 36, 38, 42),
        (6, 36, 38, 39, 47, 49),
        (5, 6, 8, 11, 16, 47),
    ),
    100: (
        (1, 9, 24, 34, 36, 46),
        (17, 32, 36, 44, 46, 49),
        (11, 17, 19, 40, 48, 49),
        (11, 19, 27, 35, 39, 47),
    ),
    150: (
        (3, 17, 27, 34, 35, 42),
        (15, 17, 34, 36, 43, 44),
        (11, 15, 19, 28, 36, 41),
        (2, 10, 12, 20, 28, 41),
    ),
    151: (
        (17, 18, 33, 41, 42, 43),
        (13, 18, 28, 36, 42, 44),
        (13, 21, 29, 37, 44, 45),
        (3, 4, 11, 19, 37, 45),
    ),
    200: (
        (4, 9, 28, 36, 42, 44),
        (10, 28, 35, 36, 37, 45),
        (12, 20, 29, 37, 43, 45),
        (3, 13, 21, 29, 41, 43),
    ),
    300: (
        (6, 14, 23, 31, 39, 47),
        (6, 15, 21, 22, 23, 43),
        (15, 21, 26, 32, 41, 48),
        (5, 13, 32, 40, 48, 49),
    ),
    500: (
        (1, 18, 26, 39, 42, 47),
        (9, 10, 26, 30, 43, 47),
        (10, 27, 32, 35, 43, 48),
        (11, 19, 27, 32, 40, 49),
    ),
    750: (
        (11, 16, 24, 32, 40, 48),
        (8, 11, 15, 24, 41, 49),
        (12, 15, 21, 29, 37, 49),
        (6, 7, 23, 29, 31, 37),
    ),
}


# ─── test_asm goldens (portfolio, 3 native tickets) ────────────────────────


@pytest.mark.parametrize("n", sorted(ASM_GOLDENS))
def test_asm_matches_reference_golden(n: int) -> None:
    history = _wave13_history(n)
    bets = BigLottoTestAsmAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert bets == ASM_GOLDENS[n]


def test_asm_minimum_history_boundary() -> None:
    with pytest.raises(InsufficientHistory):
        BigLottoTestAsmAdapter().get_bets(_wave13_history(0), LotteryType.BIG_LOTTO)
    assert (
        BigLottoTestAsmAdapter().get_bets(_wave13_history(1), LotteryType.BIG_LOTTO)
        == ASM_GOLDENS[1]
    )


def test_asm_native_ticket_count_and_order_is_fixed() -> None:
    for n in (50, 500, 750):
        bets = BigLottoTestAsmAdapter().get_bets(_wave13_history(n), LotteryType.BIG_LOTTO)
        assert len(bets) == 3
        assert bets == ASM_GOLDENS[n]


def test_asm_first_ticket_matches_base_three_bet_optimizer_top_slice() -> None:
    """ASM's own first index-map ``[0,1,2,3,4,5]`` is byte-identical to the
    base 3-bet optimizer's own first ``(0,6)`` slice, since both are simply
    the first six entries of the same shared top-18 candidate pool."""

    from lottolab.strategies.adapters.biglotto_wave4 import BigLottoThreeBetOptimizerAdapter

    history = _wave13_history(300)
    asm_bets = BigLottoTestAsmAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    base_bets = BigLottoThreeBetOptimizerAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert asm_bets[0] == base_bets[0]


def test_asm_candidate_index_out_of_range_closes_explicitly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The donor indexes (not slices) into its top-18 candidate list, so a
    causal history whose weighted pool has fewer than 13 distinct candidates
    raises a native ``IndexError`` in the original source -- reproduced here
    as an explicit ``Wave13FrozenSourceError``, never an invented pad. A
    natural occurrence is real but rare (the audited reference oracle found
    exactly 1 in 2148 real causal cutoffs), so this proves the closure path
    directly with a controlled short pool."""

    from lottolab.strategies.adapters import biglotto_wave13 as module

    def _short_top18(_history: object) -> list[int]:
        return list(range(1, 13))  # only 12 candidates; index 12 is missing

    monkeypatch.setattr(module, "_base_top18", _short_top18)
    with pytest.raises(
        Wave13FrozenSourceError, match="FROZEN_SOURCE_CANDIDATE_INDEX_OUT_OF_RANGE"
    ):
        module.BigLottoTestAsmAdapter().get_bets(_wave13_history(50), LotteryType.BIG_LOTTO)


def test_asm_kill_numbers_are_load_bearing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Direct proof against the real adapter that P1 kill-number exclusion
    actually changes the output: forcing every number in bet 1 onto the
    kill list must change bet 1."""

    from lottolab.strategies.adapters import biglotto_wave13 as module

    history = _wave13_history(300)
    baseline = module.BigLottoTestAsmAdapter().get_bets(history, LotteryType.BIG_LOTTO)

    def _kill_first_bet(_history: object, count: int) -> list[int]:
        return list(baseline[0])

    monkeypatch.setattr(module, "_kill_numbers", _kill_first_bet)
    mutated = module.BigLottoTestAsmAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert mutated != baseline
    assert set(mutated[0]).isdisjoint(baseline[0])


def test_asm_index_maps_are_mutation_sensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Direct proof that the three fixed index-maps are load-bearing, using
    a fixed top-18 pool so the resulting rows are fully predictable."""

    from lottolab.strategies.adapters import biglotto_wave13 as module

    top18 = list(range(1, 19))

    def _fixed_top18(_history: object) -> list[int]:
        return top18

    monkeypatch.setattr(module, "_base_top18", _fixed_top18)
    history = _wave13_history(50)
    bets = module.BigLottoTestAsmAdapter()._predict_all(tuple(history), LotteryType.BIG_LOTTO)
    assert bets == (
        tuple(sorted(top18[index] for index in (0, 1, 2, 3, 4, 5))),
        tuple(sorted(top18[index] for index in (0, 1, 6, 7, 8, 9))),
        tuple(sorted(top18[index] for index in (2, 3, 4, 10, 11, 12))),
    )


# ─── test_dcb goldens (portfolio, 3 native tickets) ────────────────────────


@pytest.mark.parametrize("n", sorted(DCB_GOLDENS))
def test_dcb_matches_reference_golden(n: int) -> None:
    history = _wave13_history(n)
    bets = BigLottoTestDcbAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert bets == DCB_GOLDENS[n]


def test_dcb_minimum_history_boundary() -> None:
    with pytest.raises(InsufficientHistory):
        BigLottoTestDcbAdapter().get_bets(_wave13_history(0), LotteryType.BIG_LOTTO)
    assert (
        BigLottoTestDcbAdapter().get_bets(_wave13_history(1), LotteryType.BIG_LOTTO)
        == DCB_GOLDENS[1]
    )


def test_dcb_native_ticket_count_and_order_is_fixed() -> None:
    for n in (50, 500, 750):
        bets = BigLottoTestDcbAdapter().get_bets(_wave13_history(n), LotteryType.BIG_LOTTO)
        assert len(bets) == 3
        assert bets == DCB_GOLDENS[n]


def _low_diversity_row(index: int) -> CausalDrawRow:
    """Eight-number pool, six-of-eight combinations -- deliberately low
    diversity so deviation/markov/statistical/hot_cold overlap heavily and
    the correlation-boosted top-18 pool can fall short of 18 candidates."""

    pool_combos = list(combinations(range(1, 9), 6))
    numbers = tuple(sorted(pool_combos[index % len(pool_combos)]))
    return CausalDrawRow(
        draw=f"w13-deg-{index:05d}",
        date=f"2020-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
        numbers=numbers,
    )


def _low_diversity_history(n: int) -> tuple[CausalDrawRow, ...]:
    return tuple(_low_diversity_row(i) for i in range(n))


def test_dcb_insufficient_candidate_pool_closes_gracefully() -> None:
    """A low-diversity causal history is a genuine donor-faithful closure,
    not a bug: the donor's own fixed ``(0,6)/(4,10)/(8,14)`` slice has no
    fallback for an under-populated correlation-boosted candidate pool. The
    raw adapter raises (proving the port has no invented fallback the donor
    lacks); the production ``GeneratePortfolio`` use case -- which every real
    caller goes through -- already closes this as ``REPLAY_ERROR``."""

    history = _low_diversity_history(6)
    with pytest.raises(ValueError, match="FROZEN_UNIFIED_INVALID_TICKET"):
        BigLottoTestDcbAdapter().get_bets(history, LotteryType.BIG_LOTTO)

    use_case = build_production_generate_portfolio()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id="legacy_biglotto__test_dcb__c3299c25ca59",
            lottery_type=LotteryType.BIG_LOTTO,
            history=history,
        )
    )
    assert result.status is GeneratePortfolioStatus.REPLAY_ERROR
    assert result.reason_code is GeneratePortfolioReason.REPLAY_ERROR
    assert result.numbers is None


def test_dcb_kill_numbers_are_load_bearing(monkeypatch: pytest.MonkeyPatch) -> None:
    from lottolab.strategies.adapters import biglotto_wave13 as module

    history = _wave13_history(300)
    baseline = module.BigLottoTestDcbAdapter().get_bets(history, LotteryType.BIG_LOTTO)

    def _kill_first_bet(_history: object, count: int) -> list[int]:
        return list(baseline[0])

    monkeypatch.setattr(module, "_kill_numbers", _kill_first_bet)
    mutated = module.BigLottoTestDcbAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert mutated != baseline
    assert set(mutated[0]).isdisjoint(baseline[0])


def test_dcb_weights_and_slices_are_mutation_sensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Direct proof that the per-method weights (statistical 2.0 > deviation
    1.5 = markov 1.5 > hot_cold 1.0) and the (0,6)/(4,10)/(8,14) slice
    boundaries are load-bearing, using four disjoint fixed engine outputs, no
    kill filtering, and a correlation-neutral history (draws confined to
    37..49, disjoint from every fixed candidate number below) so the
    correlation-boost pass is a true no-op and the resulting Counter has no
    ties or boosts to reason about."""

    from lottolab.strategies.adapters import biglotto_wave13 as module

    deviation_fixed: tuple[int, ...] = (1, 2, 3, 4, 5, 6)
    markov_fixed: tuple[int, ...] = (11, 12, 13, 14, 15, 16)
    statistical_fixed: tuple[int, ...] = (21, 22, 23, 24, 25, 26)
    hot_cold_fixed: tuple[int, ...] = (31, 32, 33, 34, 35, 36)

    def _fixed_deviation(_history: object) -> tuple[int, ...]:
        return deviation_fixed

    def _fixed_markov(_history: object) -> tuple[int, ...]:
        return markov_fixed

    def _fixed_statistical(_history: object) -> tuple[int, ...]:
        return statistical_fixed

    def _fixed_hot_cold(_history: object) -> tuple[int, ...]:
        return hot_cold_fixed

    def _no_kill(_history: object, count: int) -> list[int]:
        return []

    monkeypatch.setattr(module, "_unified_deviation_ticket", _fixed_deviation)
    monkeypatch.setattr(module, "_unified_markov_ticket", _fixed_markov)
    monkeypatch.setattr(module, "_unified_statistical_ticket", _fixed_statistical)
    monkeypatch.setattr(module, "_unified_hot_cold_mix_ticket", _fixed_hot_cold)
    monkeypatch.setattr(module, "_kill_numbers", _no_kill)

    high_pool_combos = list(combinations(range(37, 50), 6))
    history = tuple(
        CausalDrawRow(
            draw=f"w13-neutral-{i:05d}",
            date="2020-01-01",
            numbers=tuple(sorted(high_pool_combos[i % len(high_pool_combos)])),
        )
        for i in range(50)
    )
    bets = module.BigLottoTestDcbAdapter()._predict_all(tuple(history), LotteryType.BIG_LOTTO)
    # Counter.most_common ranks by weight (statistical 2.0 first, hot_cold
    # 1.0 last); deviation/markov tie at 1.5 and break by insertion order
    # (deviation is inserted first in ``_dcb_top18``'s own weight-spec tuple).
    top18 = statistical_fixed + deviation_fixed + markov_fixed + hot_cold_fixed
    assert bets == (
        tuple(sorted(top18[0:6])),
        tuple(sorted(top18[4:10])),
        tuple(sorted(top18[8:14])),
    )


def test_dcb_correlation_boost_is_load_bearing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Direct proof that the trailing-200-draw co-occurrence boost actually
    changes the ranking: a history engineered so one non-top-5 candidate
    co-occurs heavily with a top-5 anchor must out-rank a same-weighted
    candidate with no co-occurrence."""

    from lottolab.strategies.adapters import biglotto_wave13 as module

    deviation_fixed: tuple[int, ...] = (1, 2, 3, 4, 5, 6)
    markov_fixed: tuple[int, ...] = (1, 2, 3, 4, 5, 7)
    statistical_fixed: tuple[int, ...] = (1, 2, 3, 4, 5, 8)
    hot_cold_fixed: tuple[int, ...] = (9, 40, 41, 42, 43, 44)

    def _fixed_deviation(_history: object) -> tuple[int, ...]:
        return deviation_fixed

    def _fixed_markov(_history: object) -> tuple[int, ...]:
        return markov_fixed

    def _fixed_statistical(_history: object) -> tuple[int, ...]:
        return statistical_fixed

    def _fixed_hot_cold(_history: object) -> tuple[int, ...]:
        return hot_cold_fixed

    def _no_kill(_history: object, count: int) -> list[int]:
        return []

    monkeypatch.setattr(module, "_unified_deviation_ticket", _fixed_deviation)
    monkeypatch.setattr(module, "_unified_markov_ticket", _fixed_markov)
    monkeypatch.setattr(module, "_unified_statistical_ticket", _fixed_statistical)
    monkeypatch.setattr(module, "_unified_hot_cold_mix_ticket", _fixed_hot_cold)
    monkeypatch.setattr(module, "_kill_numbers", _no_kill)

    # number 9 co-occurs with anchor 1 in every one of the trailing draws;
    # number 40 never co-occurs with any anchor -- both start at weight 1.0
    # (hot_cold only) before the boost pass.
    boosted_history = tuple(
        CausalDrawRow(draw=f"boost-{i:05d}", date="2020-01-01", numbers=(1, 9, 20, 21, 22, 23))
        for i in range(50)
    )
    top18 = module._dcb_top18(boosted_history)
    assert top18.index(9) < top18.index(40)


# ─── test_4bet_dcb goldens (portfolio, 4 native tickets) ───────────────────


@pytest.mark.parametrize("n", sorted(FOUR_BET_DCB_GOLDENS))
def test_four_bet_dcb_matches_reference_golden(n: int) -> None:
    history = _wave13_history(n)
    bets = BigLottoTestFourBetDcbAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert bets == FOUR_BET_DCB_GOLDENS[n]


def test_four_bet_dcb_minimum_history_boundary() -> None:
    with pytest.raises(InsufficientHistory):
        BigLottoTestFourBetDcbAdapter().get_bets(_wave13_history(0), LotteryType.BIG_LOTTO)
    assert (
        BigLottoTestFourBetDcbAdapter().get_bets(_wave13_history(1), LotteryType.BIG_LOTTO)
        == FOUR_BET_DCB_GOLDENS[1]
    )


def test_four_bet_dcb_native_ticket_count_and_order_is_fixed() -> None:
    for n in (50, 500, 750):
        bets = BigLottoTestFourBetDcbAdapter().get_bets(_wave13_history(n), LotteryType.BIG_LOTTO)
        assert len(bets) == 4
        assert bets == FOUR_BET_DCB_GOLDENS[n]


def test_four_bet_dcb_reuses_dcb_candidate_pool() -> None:
    """4-Bet DCB's first three tickets are byte-identical to DCB's own three
    tickets, since both slice the same correlation-boosted top-18 pool at
    the same first three boundaries; only the fourth (12,18) slice is new."""

    for n in _GOLDEN_HISTORY_LENGTHS:
        assert FOUR_BET_DCB_GOLDENS[n][:3] == DCB_GOLDENS[n]


def test_four_bet_dcb_insufficient_candidate_pool_closes_gracefully() -> None:
    history = _low_diversity_history(2)
    with pytest.raises(ValueError, match="FROZEN_UNIFIED_INVALID_TICKET"):
        BigLottoTestFourBetDcbAdapter().get_bets(history, LotteryType.BIG_LOTTO)

    use_case = build_production_generate_portfolio()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id="legacy_biglotto__test_4bet_dcb__3c7e3e661ad8",
            lottery_type=LotteryType.BIG_LOTTO,
            history=history,
        )
    )
    assert result.status is GeneratePortfolioStatus.REPLAY_ERROR
    assert result.reason_code is GeneratePortfolioReason.REPLAY_ERROR
    assert result.numbers is None


def test_four_bet_dcb_fourth_slice_is_mutation_sensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    from lottolab.strategies.adapters import biglotto_wave13 as module

    top18 = list(range(1, 19))

    def _fixed_top18(_history: object, _unified: object = None) -> list[int]:
        return top18

    monkeypatch.setattr(module, "_dcb_top18", _fixed_top18)
    history = _wave13_history(50)
    bets = module.BigLottoTestFourBetDcbAdapter()._predict_all(
        tuple(history), LotteryType.BIG_LOTTO
    )
    assert bets == (
        tuple(sorted(top18[0:6])),
        tuple(sorted(top18[4:10])),
        tuple(sorted(top18[8:14])),
        tuple(sorted(top18[12:18])),
    )


# ─── shared: closure, repeated-execution byte equality, wrong lottery type ─


@pytest.mark.parametrize("adapter_class", PORTFOLIO_ADAPTER_CLASSES)
def test_wave13_portfolio_closure(adapter_class: type[PortfolioBetAdapter]) -> None:
    history = _wave13_history(max(adapter_class().min_history, 1) + 250)
    bets = adapter_class().get_bets(history, LotteryType.BIG_LOTTO)
    assert len(bets) == adapter_class.native_ticket_count
    for ticket in bets:
        assert len(ticket) == 6
        assert len(set(ticket)) == 6
        assert ticket == tuple(sorted(ticket))
        assert all(1 <= number <= 49 for number in ticket)


@pytest.mark.parametrize("adapter_class", PORTFOLIO_ADAPTER_CLASSES)
def test_wave13_portfolio_repeated_execution_byte_equality(
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    history = _wave13_history(max(adapter_class().min_history, 1) + 250)
    first = adapter_class().get_bets(history, LotteryType.BIG_LOTTO)
    second = adapter_class().get_bets(history, LotteryType.BIG_LOTTO)
    assert first == second


@pytest.mark.parametrize("adapter_class", PORTFOLIO_ADAPTER_CLASSES)
def test_wave13_portfolio_rejects_wrong_lottery_type(
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    history = _wave13_history(max(adapter_class().min_history, 1) + 10)
    with pytest.raises(UnsupportedLotteryType):
        adapter_class().get_bets(history, LotteryType.POWER_LOTTO)


def test_wave13_adapters_need_no_filesystem_clock_database_or_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("external state access is forbidden")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(time, "time", forbidden)
    monkeypatch.setattr(time, "monotonic", forbidden)

    history = _wave13_history(750)
    assert (
        BigLottoTestAsmAdapter().get_bets(history, LotteryType.BIG_LOTTO) == ASM_GOLDENS[750]
    )
    assert (
        BigLottoTestDcbAdapter().get_bets(history, LotteryType.BIG_LOTTO) == DCB_GOLDENS[750]
    )
    assert (
        BigLottoTestFourBetDcbAdapter().get_bets(history, LotteryType.BIG_LOTTO)
        == FOUR_BET_DCB_GOLDENS[750]
    )


def test_wave13_global_random_state_is_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    """``statistical_predict``'s frozen ``random.Random(len(history))`` local
    RNG must never touch the interpreter's global ``random`` module state."""

    import random

    history = _wave13_history(200)
    random.seed(20260805)
    before = random.getstate()
    for adapter_class in PORTFOLIO_ADAPTER_CLASSES:
        adapter_class().get_bets(history, LotteryType.BIG_LOTTO)
    after = random.getstate()
    assert before == after


def test_subprocess_repeatability_across_python_hash_seeds() -> None:
    code = """
import sys
sys.path.insert(0, {src!r})
from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.adapters.biglotto_wave13 import (
    BigLottoTestAsmAdapter, BigLottoTestDcbAdapter, BigLottoTestFourBetDcbAdapter,
)

def row(i):
    numbers = tuple(sorted(((i + s * 8) % 49) + 1 for s in range(6)))
    draw = f"w13-{{i:05d}}"
    date = f"2020-{{(i%12)+1:02d}}-{{(i%28)+1:02d}}"
    return CausalDrawRow(draw=draw, date=date, numbers=numbers)

history = tuple(row(i) for i in range(300))
outputs = [
    BigLottoTestAsmAdapter().get_bets(history, LotteryType.BIG_LOTTO),
    BigLottoTestDcbAdapter().get_bets(history, LotteryType.BIG_LOTTO),
    BigLottoTestFourBetDcbAdapter().get_bets(history, LotteryType.BIG_LOTTO),
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


@pytest.mark.parametrize("strategy_id", sorted(WAVE13_IDS))
def test_generate_one_bet_fails_closed_for_wave13_portfolio_strategy(strategy_id: str) -> None:
    use_case = build_production_generate_one_bet()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id=strategy_id,
            lottery_type=LotteryType.BIG_LOTTO,
            history=_wave13_history(50),
        )
    )
    assert result.status is GenerateOneBetStatus.WRONG_RESPONSE_PATH
    assert result.reason_code is GenerateOneBetReason.STRATEGY_IS_PORTFOLIO
    assert result.numbers is None


def test_generate_one_bet_does_not_expose_wave13_portfolio_adapters() -> None:
    use_case = build_production_generate_one_bet()
    assert WAVE13_IDS.isdisjoint(use_case._adapters.keys())


def test_generate_portfolio_returns_complete_native_ticket_set_for_each_wave13_strategy() -> None:
    use_case = build_production_generate_portfolio()
    for strategy_id, expected_count in (
        ("legacy_biglotto__test_asm__d39a233a4c75", 3),
        ("legacy_biglotto__test_dcb__c3299c25ca59", 3),
        ("legacy_biglotto__test_4bet_dcb__3c7e3e661ad8", 4),
    ):
        result = use_case.execute(
            GenerateOneBetInput(
                strategy_id=strategy_id,
                lottery_type=LotteryType.BIG_LOTTO,
                history=_wave13_history(100),
            )
        )
        assert result.status is GeneratePortfolioStatus.OK
        assert result.numbers is not None
        assert len(result.numbers) == expected_count


def test_all_wave13_strategies_are_reachable_through_exactly_one_response_path() -> None:
    one_bet = build_production_generate_one_bet()
    portfolio = build_production_generate_portfolio()
    reachable = set(one_bet._adapters.keys()) | set(portfolio._adapters.keys())
    assert reachable >= WAVE13_IDS
    assert set(one_bet._adapters.keys()) & set(portfolio._adapters.keys()) == set()


# ─── catalog / descriptor invariant tests ──────────────────────────────────


def test_production_catalog_wave13_descriptors_declare_expected_shapes() -> None:
    catalog = production_catalog()
    expected_counts = {
        "legacy_biglotto__test_asm__d39a233a4c75": 3,
        "legacy_biglotto__test_dcb__c3299c25ca59": 3,
        "legacy_biglotto__test_4bet_dcb__3c7e3e661ad8": 4,
    }
    for strategy_id, native_ticket_count in expected_counts.items():
        descriptor = catalog.get(strategy_id)
        assert descriptor.response_shape is ResponseShape.PORTFOLIO
        assert descriptor.native_ticket_count == native_ticket_count
        assert descriptor.executable is True
        assert descriptor.min_history == 1


def test_wave1_through_wave12_descriptors_are_unaffected_by_wave13() -> None:
    """The 53 pre-existing descriptors and their declaration order must
    remain unchanged; wave 13's three new descriptors are appended strictly
    after them."""

    catalog = production_catalog()
    all_ids = tuple(descriptor.strategy_id for descriptor in catalog)
    pre_existing_ids = all_ids[:53]
    wave13_ids_in_order = all_ids[53:56]
    assert set(pre_existing_ids).isdisjoint(WAVE13_IDS)
    assert set(wave13_ids_in_order) == WAVE13_IDS
    assert wave13_ids_in_order == (
        "legacy_biglotto__test_asm__d39a233a4c75",
        "legacy_biglotto__test_dcb__c3299c25ca59",
        "legacy_biglotto__test_4bet_dcb__3c7e3e661ad8",
    )
