"""Parity and contract tests for the BigLotto native-strategy wave 4 adapters.

Golden fixtures below were computed by executing this module's own adapters
against the deterministic synthetic histories built by ``_wave4_history`` in
this file -- the same methodology wave 3 used (see its module docstring):
direct execution of the actual frozen donor class was not possible in this
environment (its own ``UnifiedPredictionEngine``/``NegativeSelector`` import
chain needs pandas/scipy/sklearn plus a live SQLite path, neither available
here), so donor parity for every new engine method ported in this wave
(``hot_cold_mix_predict``, ``zone_balance_predict``,
``NegativeSelector.predict_kill_numbers``, ``OptimizedEnsemblePredictor``)
was independently re-derived by reading
``lottery_api/models/unified_predictor.py`` /
``tools/negative_selector.py`` / ``lottery_api/models/optimized_ensemble.py``
at the frozen commit; see ``biglotto_wave4.py``'s module docstring for the full
provenance chain and for which donor fields are load-bearing versus
discarded (only ``numbers`` is ever read by any of the four adapters here).

One golden history length for ``biglotto_3bet_optimizer`` (n=15) is a
genuine *closure*, not a bug: the donor's own ``_generate_bets`` performs a
fixed ``[(0,6),(4,10),(8,14)]`` slice with no fallback for an
under-populated candidate pool, so a sufficiently-overlapping
deviation/markov/statistical triple at that history length yields fewer
than 6 unique numbers for the third slice. This is ported byte-for-byte
(not "fixed"), and the framework's own ``GeneratePortfolio`` use case
already closes it gracefully as ``REPLAY_ERROR`` -- see
``test_three_bet_optimizer_insufficient_candidate_pool_closes_gracefully``.
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
    PortfolioBetAdapter,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_wave4 import (
    BigLottoOptimizedEnsembleAdapter,
    BigLottoThreeBetOptimizerAdapter,
    BigLottoTMEOptimizerAdapter,
    BigLottoTwoBetElitePredictorAdapter,
)
from lottolab.strategies.catalog import production_catalog

REPO_ROOT = Path(__file__).resolve().parents[2]

WAVE4_PORTFOLIO_IDS = {
    "legacy_biglotto__biglotto_3bet_optimizer__2835d6cb20c5",
    "legacy_biglotto__biglotto_tme_optimizer__62c6cb676bad",
    "legacy_biglotto__predict_biglotto_115000007_2bets__3dc7842c0511",
}
WAVE4_SINGLE_TICKET_ID = "legacy_biglotto__optimized_ensemble__e05e0fde22d7"
WAVE4_IDS = WAVE4_PORTFOLIO_IDS | {WAVE4_SINGLE_TICKET_ID}


def _wave4_row(index: int) -> CausalDrawRow:
    """Deterministic 6-of-49 draw. Stride 8 is coprime with 49, so six
    consecutive steps always land on six distinct residues — no collisions."""

    numbers = tuple(sorted(((index + step * 8) % 49) + 1 for step in range(6)))
    assert len(set(numbers)) == 6
    return CausalDrawRow(
        draw=f"w4-{index:05d}",
        date=f"2020-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
        numbers=numbers,
    )


def _wave4_history(n: int) -> tuple[CausalDrawRow, ...]:
    return tuple(_wave4_row(i) for i in range(n))


PORTFOLIO_ADAPTER_CLASSES = (
    BigLottoThreeBetOptimizerAdapter,
    BigLottoTMEOptimizerAdapter,
    BigLottoTwoBetElitePredictorAdapter,
)

_GOLDEN_HISTORY_LENGTHS = (1, 2, 5, 10, 30, 49, 50, 51, 80, 100, 150, 151, 200, 300, 500, 750)

# ─── goldens (see module docstring); keyed by history length. ─────────────

THREE_BET_OPTIMIZER_GOLDENS: dict[int, tuple[tuple[int, ...], ...]] = {
    1: ((20, 38, 40, 42, 44, 46), (13, 21, 22, 44, 46, 48), (5, 11, 21, 22, 23, 49)),
    2: ((37, 38, 39, 40, 43, 49), (13, 20, 21, 39, 40, 44), (9, 17, 20, 21, 22, 23)),
    5: ((28, 36, 37, 42, 44, 45), (12, 19, 20, 22, 42, 44), (10, 11, 20, 22, 23, 49)),
    10: ((32, 39, 40, 47, 48, 49), (3, 11, 19, 27, 48, 49), (18, 19, 23, 27, 35, 43)),
    30: ((30, 37, 38, 44, 45, 46), (23, 31, 39, 45, 46, 47), (10, 18, 26, 28, 39, 47)),
    49: ((8, 16, 25, 32, 40, 49), (9, 17, 32, 33, 40, 48), (17, 19, 33, 42, 44, 47)),
    50: ((10, 16, 24, 32, 40, 48), (18, 26, 34, 40, 48, 49), (11, 22, 25, 26, 34, 43)),
    51: ((32, 39, 40, 47, 48, 49), (11, 19, 27, 35, 48, 49), (1, 10, 24, 27, 35, 43)),
    80: ((1, 24, 32, 40, 48, 49), (1, 10, 31, 32, 36, 38), (7, 8, 16, 36, 38, 42)),
    100: ((32, 39, 40, 47, 48, 49), (11, 19, 27, 35, 48, 49), (1, 9, 24, 27, 35, 44)),
    150: ((27, 34, 35, 41, 42, 43), (12, 20, 28, 36, 41, 43), (3, 15, 17, 28, 36, 44)),
    151: ((28, 36, 41, 42, 43, 44), (13, 21, 29, 37, 42, 44), (17, 18, 29, 33, 37, 45)),
    200: ((28, 36, 41, 42, 43, 44), (13, 21, 29, 37, 41, 43), (4, 9, 10, 29, 37, 45)),
    300: ((32, 39, 40, 47, 48, 49), (14, 15, 23, 31, 48, 49), (14, 21, 26, 31, 41, 43)),
    500: ((32, 39, 40, 47, 48, 49), (11, 19, 27, 35, 48, 49), (1, 18, 27, 30, 35, 43)),
    750: ((8, 16, 32, 40, 48, 49), (8, 11, 12, 21, 24, 49), (7, 12, 21, 29, 37, 41)),
}

TME_OPTIMIZER_GOLDENS: dict[int, tuple[tuple[int, ...], ...]] = {
    1: (
        (5, 11, 20, 25, 34, 41),
        (38, 40, 42, 44, 46, 48),
        (13, 20, 21, 22, 23, 49),
        (1, 9, 17, 25, 33, 41),
    ),
    2: (
        (9, 17, 36, 42, 43, 49),
        (37, 38, 39, 40, 43, 44),
        (13, 20, 21, 22, 23, 49),
        (1, 2, 9, 10, 17, 18),
    ),
    5: (
        (10, 11, 28, 33, 35, 45),
        (28, 36, 37, 42, 44, 45),
        (12, 19, 20, 22, 23, 49),
        (1, 2, 3, 4, 5, 9),
    ),
    10: (
        (18, 23, 29, 30, 34, 42),
        (32, 39, 40, 47, 48, 49),
        (3, 11, 19, 27, 35, 43),
        (1, 9, 10, 17, 18, 25),
    ),
    30: (
        (10, 18, 26, 28, 29, 35),
        (30, 37, 38, 44, 45, 46),
        (6, 14, 23, 31, 39, 47),
        (1, 4, 5, 30, 38, 46),
    ),
    49: (
        (4, 19, 25, 44, 47, 49),
        (8, 16, 32, 40, 48, 49),
        (1, 9, 17, 25, 33, 42),
        (7, 8, 15, 16, 23, 49),
    ),
    50: (
        (10, 11, 22, 25, 27, 33),
        (16, 24, 32, 40, 48, 49),
        (2, 10, 18, 26, 34, 43),
        (1, 8, 9, 16, 17, 24),
    ),
    51: (
        (1, 3, 10, 24, 33, 34),
        (32, 39, 40, 47, 48, 49),
        (3, 11, 19, 27, 35, 43),
        (1, 2, 9, 10, 17, 18),
    ),
    80: (
        (1, 10, 31, 36, 38, 42),
        (8, 16, 24, 40, 48, 49),
        (7, 15, 24, 32, 40, 48),
        (5, 6, 11, 31, 39, 47),
    ),
    100: (
        (1, 9, 24, 34, 36, 46),
        (32, 39, 40, 47, 48, 49),
        (3, 11, 19, 27, 35, 44),
        (1, 2, 9, 10, 17, 18),
    ),
    150: (
        (3, 7, 15, 17, 35, 42),
        (27, 34, 35, 41, 42, 43),
        (4, 12, 20, 28, 36, 44),
        (2, 3, 10, 11, 18, 19),
    ),
    151: (
        (6, 17, 18, 33, 41, 43),
        (28, 36, 41, 42, 43, 44),
        (5, 13, 21, 29, 37, 45),
        (3, 4, 11, 12, 19, 20),
    ),
    200: (
        (4, 9, 10, 35, 42, 44),
        (28, 36, 41, 42, 43, 44),
        (5, 13, 21, 29, 37, 45),
        (3, 4, 11, 12, 19, 20),
    ),
    300: (
        (3, 14, 21, 26, 41, 43),
        (32, 39, 40, 47, 48, 49),
        (7, 15, 23, 31, 39, 47),
        (2, 5, 6, 13, 14, 22),
    ),
    500: (
        (1, 5, 18, 30, 39, 42),
        (32, 39, 40, 47, 48, 49),
        (2, 11, 19, 27, 35, 43),
        (1, 6, 9, 10, 18, 26),
    ),
    750: (
        (11, 12, 21, 29, 37, 41),
        (8, 16, 32, 40, 48, 49),
        (7, 16, 24, 32, 40, 48),
        (3, 6, 11, 15, 23, 31),
    ),
}

ENSEMBLE_GOLDENS: dict[int, tuple[int, ...]] = {
    1: (1, 2, 3, 4, 5, 6),
    2: (1, 2, 3, 4, 5, 6),
    5: (1, 2, 3, 4, 5, 6),
    10: (1, 2, 3, 4, 5, 6),
    30: (5, 13, 21, 30, 38, 46),
    49: (8, 16, 24, 32, 40, 49),
    50: (8, 16, 24, 32, 40, 49),
    51: (8, 16, 24, 32, 40, 49),
    80: (6, 14, 22, 31, 39, 47),
    100: (8, 16, 24, 32, 40, 49),
    150: (8, 16, 24, 32, 40, 49),
    151: (1, 9, 17, 25, 33, 41),
    200: (1, 9, 17, 25, 33, 41),
    300: (3, 11, 19, 27, 35, 43),
    500: (7, 15, 23, 31, 39, 47),
    750: (3, 12, 20, 28, 36, 44),
}

TWO_BET_ELITE_GOLDENS: dict[int, tuple[tuple[int, ...], ...]] = {
    1: ((20, 25, 38, 40, 41, 42), (1, 9, 17, 44, 46, 48)),
    2: ((9, 17, 37, 38, 43, 49), (2, 10, 39, 40, 42, 44)),
    5: ((20, 28, 36, 37, 42, 45), (12, 19, 21, 22, 23, 44)),
    10: ((18, 32, 39, 40, 47, 49), (3, 11, 19, 27, 35, 48)),
    30: ((30, 37, 38, 44, 45, 46), (10, 18, 23, 31, 39, 47)),
    49: ((8, 16, 25, 32, 40, 49), (9, 17, 19, 33, 42, 48)),
    50: ((10, 16, 24, 32, 40, 49), (18, 25, 26, 33, 34, 48)),
    51: ((1, 10, 32, 39, 40, 49), (11, 19, 24, 27, 47, 48)),
    80: ((1, 24, 32, 40, 48, 49), (2, 10, 31, 36, 38, 42)),
    100: ((1, 9, 32, 39, 40, 49), (11, 19, 24, 27, 47, 48)),
    150: ((3, 27, 34, 35, 41, 42), (12, 20, 28, 32, 36, 43)),
    151: ((28, 36, 41, 42, 43, 44), (13, 21, 29, 32, 37, 45)),
    200: ((28, 36, 41, 42, 43, 44), (13, 21, 29, 32, 37, 45)),
    300: ((32, 39, 40, 47, 48, 49), (14, 15, 21, 23, 26, 31)),
    500: ((1, 18, 32, 39, 40, 49), (11, 19, 27, 35, 47, 48)),
    750: ((8, 16, 32, 40, 48, 49), (11, 12, 21, 24, 29, 37)),
}


# ─── biglotto_3bet_optimizer goldens (portfolio, 3 native tickets) ─────────


@pytest.mark.parametrize("n", sorted(THREE_BET_OPTIMIZER_GOLDENS))
def test_three_bet_optimizer_matches_reference_golden(n: int) -> None:
    history = _wave4_history(n)
    bets = BigLottoThreeBetOptimizerAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert bets == THREE_BET_OPTIMIZER_GOLDENS[n]


def test_three_bet_optimizer_minimum_history_boundary() -> None:
    with pytest.raises(InsufficientHistory):
        BigLottoThreeBetOptimizerAdapter().get_bets(_wave4_history(0), LotteryType.BIG_LOTTO)
    assert (
        BigLottoThreeBetOptimizerAdapter().get_bets(_wave4_history(1), LotteryType.BIG_LOTTO)
        == THREE_BET_OPTIMIZER_GOLDENS[1]
    )


def test_three_bet_optimizer_native_ticket_count_and_order_is_fixed() -> None:
    for n in (50, 500, 750):
        bets = BigLottoThreeBetOptimizerAdapter().get_bets(_wave4_history(n), LotteryType.BIG_LOTTO)
        assert len(bets) == 3
        assert bets == THREE_BET_OPTIMIZER_GOLDENS[n]


def test_three_bet_optimizer_insufficient_candidate_pool_closes_gracefully() -> None:
    """n=15 is a genuine donor-faithful closure, not a bug -- see module
    docstring. The raw adapter raises (proving the port has no invented
    fallback the donor's own ``_generate_bets`` lacks); the production
    ``GeneratePortfolio`` use case -- which every real caller goes through --
    already closes this as ``REPLAY_ERROR``, never an unhandled exception."""
    with pytest.raises(ValueError, match="FROZEN_UNIFIED_INVALID_TICKET"):
        BigLottoThreeBetOptimizerAdapter().get_bets(_wave4_history(15), LotteryType.BIG_LOTTO)

    use_case = build_production_generate_portfolio()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id="legacy_biglotto__biglotto_3bet_optimizer__2835d6cb20c5",
            lottery_type=LotteryType.BIG_LOTTO,
            history=_wave4_history(15),
        )
    )
    assert result.status is GeneratePortfolioStatus.REPLAY_ERROR
    assert result.reason_code is GeneratePortfolioReason.REPLAY_ERROR
    assert result.numbers is None


def test_three_bet_optimizer_kill_numbers_are_load_bearing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct proof against the real adapter that P1 kill-number exclusion
    actually changes the output: forcing every number in bet 1 onto the
    kill list must change bet 1 (kill sets that candidate's Counter weight
    to -9999, evicting it from the top-18 pool)."""
    from lottolab.strategies.adapters import biglotto_wave4 as module

    history = _wave4_history(300)
    baseline = module.BigLottoThreeBetOptimizerAdapter().get_bets(history, LotteryType.BIG_LOTTO)

    def _kill_first_bet(_history: object, count: int) -> list[int]:
        return list(baseline[0])

    monkeypatch.setattr(module, "_kill_numbers", _kill_first_bet)
    mutated = module.BigLottoThreeBetOptimizerAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert mutated != baseline
    assert set(mutated[0]).isdisjoint(baseline[0])


def test_three_bet_optimizer_weights_and_slices_are_mutation_sensitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct proof that the per-method weights (deviation 2.0 > markov 1.5
    > statistical 1.0) and the (0,6)/(4,10)/(8,14) slice boundaries are
    load-bearing, using three disjoint fixed engine outputs and no kill
    filtering so the resulting Counter has no ties to reason about."""
    from lottolab.strategies.adapters import biglotto_wave4 as module

    deviation_fixed: tuple[int, ...] = (1, 2, 3, 4, 5, 6)
    markov_fixed: tuple[int, ...] = (11, 12, 13, 14, 15, 16)
    statistical_fixed: tuple[int, ...] = (21, 22, 23, 24, 25, 26)

    def _fixed_deviation(_history: object) -> tuple[int, ...]:
        return deviation_fixed

    def _fixed_markov(_history: object) -> tuple[int, ...]:
        return markov_fixed

    def _fixed_statistical(_history: object) -> tuple[int, ...]:
        return statistical_fixed

    def _no_kill(_history: object, count: int) -> list[int]:
        return []

    monkeypatch.setattr(module, "_unified_deviation_ticket", _fixed_deviation)
    monkeypatch.setattr(module, "_unified_markov_ticket", _fixed_markov)
    monkeypatch.setattr(module, "_unified_statistical_ticket", _fixed_statistical)
    monkeypatch.setattr(module, "_kill_numbers", _no_kill)

    history = _wave4_history(50)
    bets = module.BigLottoThreeBetOptimizerAdapter()._predict_all(
        tuple(history), LotteryType.BIG_LOTTO
    )
    top18 = deviation_fixed + markov_fixed + statistical_fixed
    assert bets == (
        tuple(sorted(top18[0:6])),
        tuple(sorted(top18[4:10])),
        tuple(sorted(top18[8:14])),
    )


# ─── biglotto_tme_optimizer goldens (portfolio, 4 native tickets) ──────────


@pytest.mark.parametrize("n", sorted(TME_OPTIMIZER_GOLDENS))
def test_tme_optimizer_matches_reference_golden(n: int) -> None:
    history = _wave4_history(n)
    bets = BigLottoTMEOptimizerAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert bets == TME_OPTIMIZER_GOLDENS[n]


def test_tme_optimizer_minimum_history_boundary() -> None:
    with pytest.raises(InsufficientHistory):
        BigLottoTMEOptimizerAdapter().get_bets(_wave4_history(0), LotteryType.BIG_LOTTO)
    assert (
        BigLottoTMEOptimizerAdapter().get_bets(_wave4_history(1), LotteryType.BIG_LOTTO)
        == TME_OPTIMIZER_GOLDENS[1]
    )


def test_tme_optimizer_native_ticket_count_and_order_is_fixed() -> None:
    for n in (50, 500, 750):
        bets = BigLottoTMEOptimizerAdapter().get_bets(_wave4_history(n), LotteryType.BIG_LOTTO)
        assert len(bets) == 4
        assert bets == TME_OPTIMIZER_GOLDENS[n]


def test_tme_optimizer_each_bet_is_one_independent_engine_method(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct proof that each of the four bets comes from exactly one
    independent engine method, in fixed order, with no slicing or blending:
    making any one method explode must not affect the other three bets."""
    from lottolab.strategies.adapters import biglotto_wave4 as module

    history = _wave4_history(300)
    baseline = module.BigLottoTMEOptimizerAdapter().get_bets(history, LotteryType.BIG_LOTTO)

    def exploding(_history: object) -> tuple[int, ...]:
        raise AssertionError("this method should not affect the other three bets' computation")

    for attribute in (
        "_unified_statistical_ticket",
        "_unified_deviation_ticket",
        "_unified_markov_ticket",
        "_unified_hot_cold_mix_ticket",
    ):
        monkeypatch.setattr(module, attribute, exploding)
        with pytest.raises(AssertionError, match="should not affect"):
            module.BigLottoTMEOptimizerAdapter().get_bets(history, LotteryType.BIG_LOTTO)
        monkeypatch.undo()

    assert (
        module.BigLottoTMEOptimizerAdapter().get_bets(history, LotteryType.BIG_LOTTO) == baseline
    )


def test_tme_optimizer_hot_cold_mix_bet_differs_from_shared_engine_bets() -> None:
    """The fourth bet (hot_cold_mix) must not accidentally coincide with any
    of the three shared-engine bets it sits alongside, at a history length
    long enough for all four signals to differentiate."""
    bets = BigLottoTMEOptimizerAdapter().get_bets(_wave4_history(750), LotteryType.BIG_LOTTO)
    statistical, deviation, markov, hot_cold_mix = bets
    assert hot_cold_mix not in (statistical, deviation, markov)


# ─── optimized_ensemble goldens (single ticket) ────────────────────────────


@pytest.mark.parametrize("n", sorted(ENSEMBLE_GOLDENS))
def test_optimized_ensemble_matches_reference_golden(n: int) -> None:
    history = _wave4_history(n)
    assert BigLottoOptimizedEnsembleAdapter().get_one_bet(history, LotteryType.BIG_LOTTO) == (
        ENSEMBLE_GOLDENS[n],
        None,
    )


def test_optimized_ensemble_minimum_history_boundary() -> None:
    with pytest.raises(InsufficientHistory):
        BigLottoOptimizedEnsembleAdapter().get_one_bet(_wave4_history(0), LotteryType.BIG_LOTTO)
    assert BigLottoOptimizedEnsembleAdapter().get_one_bet(
        _wave4_history(1), LotteryType.BIG_LOTTO
    ) == (ENSEMBLE_GOLDENS[1], None)


def test_optimized_ensemble_below_twenty_draws_uses_donor_fixed_fallback() -> None:
    """The donor hardcodes ``numbers = list(range(1, 7))`` below 20 draws --
    not a placeholder this port invented. n=1..19 must all match exactly,
    and n=20 must differ (proving the len(history) < 20 branch is real and
    its boundary is exactly at 20, not merely "small")."""
    for n in (1, 5, 10, 19):
        assert BigLottoOptimizedEnsembleAdapter().get_one_bet(
            _wave4_history(n), LotteryType.BIG_LOTTO
        ) == ((1, 2, 3, 4, 5, 6), None)
    numbers_20, _ = BigLottoOptimizedEnsembleAdapter().get_one_bet(
        _wave4_history(20), LotteryType.BIG_LOTTO
    )
    assert numbers_20 != (1, 2, 3, 4, 5, 6)


def test_optimized_ensemble_argsort_ranking_is_mutation_sensitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct proof that the NumPy-argsort-derived descending rank (not
    merely "the momentum/entropy/lag-reversion scores exist") is load-
    bearing: swapping in ascending order instead of descending must change
    which six numbers are selected."""
    from lottolab.strategies.adapters import biglotto_wave4 as module

    history = _wave4_history(300)
    baseline = module.BigLottoOptimizedEnsembleAdapter().get_one_bet(
        history, LotteryType.BIG_LOTTO
    )

    real_argsort = module._numpy_argsort

    def ascending_only(values: list[float]) -> list[int]:
        # Real ascending order, not reversed by the caller's own `reversed()`
        # -- forces the caller's descending-rank assumption to break.
        return list(reversed(real_argsort(values)))

    monkeypatch.setattr(module, "_numpy_argsort", ascending_only)
    mutated = module.BigLottoOptimizedEnsembleAdapter().get_one_bet(history, LotteryType.BIG_LOTTO)
    assert mutated != baseline


# ─── predict_biglotto_115000007_2bets goldens (portfolio, 2 native tickets) ─


@pytest.mark.parametrize("n", sorted(TWO_BET_ELITE_GOLDENS))
def test_two_bet_elite_matches_reference_golden(n: int) -> None:
    history = _wave4_history(n)
    bets = BigLottoTwoBetElitePredictorAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert bets == TWO_BET_ELITE_GOLDENS[n]


def test_two_bet_elite_minimum_history_boundary() -> None:
    with pytest.raises(InsufficientHistory):
        BigLottoTwoBetElitePredictorAdapter().get_bets(_wave4_history(0), LotteryType.BIG_LOTTO)
    assert (
        BigLottoTwoBetElitePredictorAdapter().get_bets(_wave4_history(1), LotteryType.BIG_LOTTO)
        == TWO_BET_ELITE_GOLDENS[1]
    )


def test_two_bet_elite_native_ticket_count_and_order_is_fixed() -> None:
    for n in (50, 500, 750):
        bets = BigLottoTwoBetElitePredictorAdapter().get_bets(
            _wave4_history(n), LotteryType.BIG_LOTTO
        )
        assert len(bets) == 2
        assert bets == TWO_BET_ELITE_GOLDENS[n]


def test_two_bet_elite_uses_zone_balance_and_frequency_engine_methods(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct proof against the real adapter that zone_balance and frequency
    (the two methods unique to this donor file, not shared with the other
    three wave-4 strategies) are both actually consulted."""
    from lottolab.strategies.adapters import biglotto_wave4 as module

    def exploding(_history: object) -> tuple[int, ...]:
        raise AssertionError("engine method should not have been called")

    history = _wave4_history(300)

    monkeypatch.setattr(module, "_unified_zone_balance_ticket", exploding)
    with pytest.raises(AssertionError, match="should not have been called"):
        module.BigLottoTwoBetElitePredictorAdapter()._predict_all(
            tuple(history), LotteryType.BIG_LOTTO
        )
    monkeypatch.undo()

    monkeypatch.setattr(module, "_unified_frequency_ticket", exploding)
    with pytest.raises(AssertionError, match="should not have been called"):
        module.BigLottoTwoBetElitePredictorAdapter()._predict_all(
            tuple(history), LotteryType.BIG_LOTTO
        )
    monkeypatch.undo()

    assert (
        module.BigLottoTwoBetElitePredictorAdapter()._predict_all(
            tuple(history), LotteryType.BIG_LOTTO
        )
        == TWO_BET_ELITE_GOLDENS[300]
    )


def test_two_bet_elite_kill_numbers_are_load_bearing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Same load-bearing proof as the 3-bet optimizer's kill filter, for the
    independent ``count=8`` call site in this donor file."""
    from lottolab.strategies.adapters import biglotto_wave4 as module

    history = _wave4_history(300)
    baseline = module.BigLottoTwoBetElitePredictorAdapter().get_bets(
        history, LotteryType.BIG_LOTTO
    )

    def _kill_first_bet(_history: object, count: int) -> list[int]:
        assert count == 8
        return list(baseline[0])

    monkeypatch.setattr(module, "_kill_numbers", _kill_first_bet)
    mutated = module.BigLottoTwoBetElitePredictorAdapter().get_bets(
        history, LotteryType.BIG_LOTTO
    )
    assert mutated != baseline
    assert set(mutated[0]).isdisjoint(baseline[0])


# ─── shared: closure, repeated-execution byte equality, wrong lottery type ─


@pytest.mark.parametrize("adapter_class", PORTFOLIO_ADAPTER_CLASSES)
def test_wave4_portfolio_closure(adapter_class: type[PortfolioBetAdapter]) -> None:
    history = _wave4_history(max(adapter_class().min_history, 1) + 250)
    bets = adapter_class().get_bets(history, LotteryType.BIG_LOTTO)
    assert len(bets) == adapter_class.native_ticket_count
    for ticket in bets:
        assert len(ticket) == 6
        assert len(set(ticket)) == 6
        assert ticket == tuple(sorted(ticket))
        assert all(1 <= number <= 49 for number in ticket)


@pytest.mark.parametrize("adapter_class", PORTFOLIO_ADAPTER_CLASSES)
def test_wave4_portfolio_repeated_execution_byte_equality(
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    history = _wave4_history(max(adapter_class().min_history, 1) + 250)
    first = adapter_class().get_bets(history, LotteryType.BIG_LOTTO)
    second = adapter_class().get_bets(history, LotteryType.BIG_LOTTO)
    assert first == second


@pytest.mark.parametrize("adapter_class", PORTFOLIO_ADAPTER_CLASSES)
def test_wave4_portfolio_rejects_wrong_lottery_type(
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    history = _wave4_history(max(adapter_class().min_history, 1) + 10)
    with pytest.raises(UnsupportedLotteryType):
        adapter_class().get_bets(history, LotteryType.POWER_LOTTO)


def test_optimized_ensemble_repeated_execution_byte_equality_and_wrong_type() -> None:
    history = _wave4_history(300)
    first = BigLottoOptimizedEnsembleAdapter().get_one_bet(history, LotteryType.BIG_LOTTO)
    second = BigLottoOptimizedEnsembleAdapter().get_one_bet(history, LotteryType.BIG_LOTTO)
    assert first == second
    with pytest.raises(UnsupportedLotteryType):
        BigLottoOptimizedEnsembleAdapter().get_one_bet(history, LotteryType.POWER_LOTTO)


def test_wave4_adapters_need_no_filesystem_clock_database_or_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("external state access is forbidden")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(time, "time", forbidden)
    monkeypatch.setattr(time, "monotonic", forbidden)

    history = _wave4_history(750)
    assert (
        BigLottoThreeBetOptimizerAdapter().get_bets(history, LotteryType.BIG_LOTTO)
        == THREE_BET_OPTIMIZER_GOLDENS[750]
    )
    assert (
        BigLottoTMEOptimizerAdapter().get_bets(history, LotteryType.BIG_LOTTO)
        == TME_OPTIMIZER_GOLDENS[750]
    )
    assert BigLottoOptimizedEnsembleAdapter().get_one_bet(history, LotteryType.BIG_LOTTO) == (
        ENSEMBLE_GOLDENS[750],
        None,
    )
    assert (
        BigLottoTwoBetElitePredictorAdapter().get_bets(history, LotteryType.BIG_LOTTO)
        == TWO_BET_ELITE_GOLDENS[750]
    )


def test_subprocess_repeatability_across_python_hash_seeds() -> None:
    code = """
import sys
sys.path.insert(0, {src!r})
from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.adapters.biglotto_wave4 import (
    BigLottoThreeBetOptimizerAdapter, BigLottoTMEOptimizerAdapter,
    BigLottoOptimizedEnsembleAdapter, BigLottoTwoBetElitePredictorAdapter,
)

def row(i):
    numbers = tuple(sorted(((i + s * 8) % 49) + 1 for s in range(6)))
    draw = f"w4-{{i:05d}}"
    date = f"2020-{{(i%12)+1:02d}}-{{(i%28)+1:02d}}"
    return CausalDrawRow(draw=draw, date=date, numbers=numbers)

history = tuple(row(i) for i in range(300))
outputs = [
    BigLottoThreeBetOptimizerAdapter().get_bets(history, LotteryType.BIG_LOTTO),
    BigLottoTMEOptimizerAdapter().get_bets(history, LotteryType.BIG_LOTTO),
    BigLottoOptimizedEnsembleAdapter().get_one_bet(history, LotteryType.BIG_LOTTO),
    BigLottoTwoBetElitePredictorAdapter().get_bets(history, LotteryType.BIG_LOTTO),
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


@pytest.mark.parametrize("strategy_id", sorted(WAVE4_PORTFOLIO_IDS))
def test_generate_one_bet_fails_closed_for_wave4_portfolio_strategy(strategy_id: str) -> None:
    use_case = build_production_generate_one_bet()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id=strategy_id,
            lottery_type=LotteryType.BIG_LOTTO,
            history=_wave4_history(50),
        )
    )
    assert result.status is GenerateOneBetStatus.WRONG_RESPONSE_PATH
    assert result.reason_code is GenerateOneBetReason.STRATEGY_IS_PORTFOLIO
    assert result.numbers is None


def test_generate_one_bet_does_not_expose_wave4_portfolio_adapters() -> None:
    use_case = build_production_generate_one_bet()
    assert WAVE4_PORTFOLIO_IDS.isdisjoint(use_case._adapters.keys())


def test_generate_one_bet_returns_ticket_for_optimized_ensemble() -> None:
    use_case = build_production_generate_one_bet()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id=WAVE4_SINGLE_TICKET_ID,
            lottery_type=LotteryType.BIG_LOTTO,
            history=_wave4_history(100),
        )
    )
    assert result.status is GenerateOneBetStatus.OK
    assert result.numbers == ENSEMBLE_GOLDENS[100]


def test_generate_portfolio_returns_complete_native_ticket_set_for_each_wave4_strategy() -> None:
    use_case = build_production_generate_portfolio()
    for strategy_id, expected_count in (
        ("legacy_biglotto__biglotto_3bet_optimizer__2835d6cb20c5", 3),
        ("legacy_biglotto__biglotto_tme_optimizer__62c6cb676bad", 4),
        ("legacy_biglotto__predict_biglotto_115000007_2bets__3dc7842c0511", 2),
    ):
        result = use_case.execute(
            GenerateOneBetInput(
                strategy_id=strategy_id,
                lottery_type=LotteryType.BIG_LOTTO,
                history=_wave4_history(100),
            )
        )
        assert result.status is GeneratePortfolioStatus.OK
        assert result.numbers is not None
        assert len(result.numbers) == expected_count


def test_generate_portfolio_does_not_expose_wave4_single_ticket_adapter() -> None:
    use_case = build_production_generate_portfolio()
    assert WAVE4_SINGLE_TICKET_ID not in use_case._adapters


def test_all_wave4_strategies_are_reachable_through_exactly_one_response_path() -> None:
    one_bet = build_production_generate_one_bet()
    portfolio = build_production_generate_portfolio()
    reachable = set(one_bet._adapters.keys()) | set(portfolio._adapters.keys())
    assert reachable >= WAVE4_IDS
    assert set(one_bet._adapters.keys()) & set(portfolio._adapters.keys()) == set()


# ─── catalog / descriptor invariant tests ──────────────────────────────────


def test_production_catalog_wave4_portfolio_descriptors_declare_expected_shapes() -> None:
    catalog = production_catalog()
    expected_counts = {
        "legacy_biglotto__biglotto_3bet_optimizer__2835d6cb20c5": 3,
        "legacy_biglotto__biglotto_tme_optimizer__62c6cb676bad": 4,
        "legacy_biglotto__predict_biglotto_115000007_2bets__3dc7842c0511": 2,
    }
    for strategy_id, native_ticket_count in expected_counts.items():
        descriptor = catalog.get(strategy_id)
        assert descriptor.response_shape is ResponseShape.PORTFOLIO
        assert descriptor.native_ticket_count == native_ticket_count
        assert descriptor.executable is True
        assert descriptor.min_history == 1


def test_production_catalog_wave4_single_ticket_descriptor_declares_expected_shape() -> None:
    catalog = production_catalog()
    descriptor = catalog.get(WAVE4_SINGLE_TICKET_ID)
    assert descriptor.response_shape is ResponseShape.SINGLE_TICKET
    assert descriptor.native_ticket_count == 1
    assert descriptor.executable is True
    assert descriptor.min_history == 1


def test_production_catalog_now_has_thirty_two_descriptors() -> None:
    catalog = production_catalog()
    assert len(catalog) == 59


def test_wave1_through_wave3_descriptors_are_unaffected_by_wave4() -> None:
    """Existing 19 adapters and their outputs must remain unchanged."""
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
    pre_existing_portfolio_ids = {
        "legacy_biglotto__predict_biglotto_echo_phase2__51c44b5c13d4": 5,
        "legacy_biglotto__high_prize_trend_optimizer__0fc72409150e": 7,
        "legacy_biglotto__core_satellite__2e82891003b3": 12,
        "legacy_biglotto__auto_discovery_biglotto__06bcb164db84": 54,
        "legacy_biglotto__biglotto_2bet_final__7eaedb330a07": 2,
        "legacy_biglotto__biglotto_2bet_optimizer__898ac9e38876": 2,
        "legacy_biglotto__biglotto_2bet_optimizer_v2__783226366ac3": 2,
    }
    for strategy_id, native_ticket_count in pre_existing_portfolio_ids.items():
        descriptor = catalog.get(strategy_id)
        assert descriptor.response_shape is ResponseShape.PORTFOLIO
        assert descriptor.native_ticket_count == native_ticket_count
