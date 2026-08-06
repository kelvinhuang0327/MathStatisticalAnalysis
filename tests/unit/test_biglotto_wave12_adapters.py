"""Parity and contract tests for the BigLotto native-strategy wave 12 adapters.

Golden fixtures below were cross-verified by executing this module's own
adapters against the actual, separately-audited application-layer reference
oracles (``lottolab.application.legacy_history_native_portfolios`` for
social-wisdom/quick-ml, ``lottolab.application.legacy_history_native_portfolios_wave3``
for negative-selection) in a throwaway scratch script -- never imported at
runtime by product code, per the layer boundary
``tests/architecture/test_dependency_rules.py`` enforces (see
``biglotto_wave12.py``'s module docstring). 20 samples (social-wisdom) + 20
samples (negative-selection: 8 golden tickets + 12 documented
``InvalidOutput`` closures) + 4 golden ticket samples (quick-ml) + 20
closure-boundary samples (quick-ml, history >= 5) = 64 deterministic
samples across all three strategies; zero mismatches against the oracle.
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
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_wave12 import (
    BigLottoNegativeSelectionBiglottoAdapter,
    BigLottoQuickMlPredictAdapter,
    BigLottoSocialWisdomPredictorAdapter,
    Wave12FrozenSourceError,
    _target_after_causal_cutoff,
)
from lottolab.strategies.catalog import production_catalog

REPO_ROOT = Path(__file__).resolve().parents[2]

WAVE12_IDS = {
    "legacy_biglotto__social_wisdom_predictor__a00829b5d875",
    "legacy_biglotto__negative_selection_biglotto__98f860c52cc2",
    "legacy_biglotto__quick_ml_predict__8b7ba0b52e2d",
}

PORTFOLIO_ADAPTER_CLASSES = (
    BigLottoSocialWisdomPredictorAdapter,
    BigLottoNegativeSelectionBiglottoAdapter,
    BigLottoQuickMlPredictAdapter,
)


def _wave12_row(index: int) -> CausalDrawRow:
    """Deterministic 6-of-49 draw. Stride 8 is coprime with 49, so six
    consecutive steps always land on six distinct residues -- no collisions.
    Same generator as wave 11's own fixtures, for a consistent test style."""

    numbers = tuple(sorted(((index + step * 8) % 49) + 1 for step in range(6)))
    assert len(set(numbers)) == 6
    return CausalDrawRow(
        draw=str(90000000 + index),
        date=f"2020-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
        numbers=numbers,
    )


def _wave12_history(n: int) -> tuple[CausalDrawRow, ...]:
    return tuple(_wave12_row(i) for i in range(n))


# ─── goldens, cross-checked against the reference oracles (see module
#     docstring); keyed by history length. ─────────────────────────────────

SOCIAL_WISDOM_GOLDENS: dict[int, tuple[tuple[int, ...], ...]] = {
    1: (
        (6, 15, 21, 42, 45, 49),
        (3, 16, 35, 43, 46, 48),
        (1, 16, 35, 44, 46, 47),
        (2, 16, 39, 43, 44, 45),
        (1, 12, 18, 28, 40, 43),
        (6, 15, 16, 17, 30, 43),
        (1, 10, 15, 22, 28, 40),
        (2, 3, 8, 9, 15, 48),
    ),
    2: (
        (13, 32, 34, 42, 43, 44),
        (5, 10, 19, 34, 44, 48),
        (14, 27, 32, 36, 45, 48),
        (1, 2, 16, 18, 32, 43),
        (17, 24, 31, 41, 42, 45),
        (6, 10, 13, 41, 47, 49),
        (16, 24, 30, 37, 43, 46),
        (3, 13, 30, 46, 47, 48),
    ),
    3: (
        (15, 36, 38, 40, 41, 44),
        (5, 20, 23, 31, 38, 40),
        (2, 4, 7, 14, 18, 28),
        (2, 15, 24, 34, 39, 41),
        (2, 23, 26, 28, 29, 48),
        (4, 10, 20, 21, 27, 42),
        (2, 8, 19, 28, 30, 31),
        (3, 10, 20, 22, 30, 48),
    ),
    4: (
        (9, 10, 16, 27, 32, 33),
        (6, 19, 30, 31, 45, 46),
        (4, 13, 26, 34, 37, 45),
        (9, 22, 38, 45, 46, 48),
        (4, 7, 8, 28, 35, 44),
        (9, 17, 21, 32, 47, 48),
        (6, 10, 13, 32, 35, 36),
        (9, 24, 26, 32, 37, 41),
    ),
    5: (
        (5, 12, 23, 27, 38, 49),
        (24, 29, 35, 43, 47, 48),
        (15, 16, 18, 27, 46, 47),
        (11, 15, 25, 29, 38, 41),
        (24, 25, 29, 44, 47, 48),
        (10, 22, 37, 39, 40, 42),
        (1, 15, 21, 30, 33, 42),
        (14, 33, 39, 40, 42, 43),
    ),
    6: (
        (3, 6, 30, 37, 47, 49),
        (1, 8, 27, 30, 35, 40),
        (1, 8, 18, 27, 43, 46),
        (12, 30, 33, 35, 40, 45),
        (7, 26, 29, 35, 44, 47),
        (14, 16, 18, 24, 35, 46),
        (1, 9, 17, 28, 29, 44),
        (4, 5, 13, 14, 41, 48),
    ),
    7: (
        (2, 7, 9, 13, 42, 47),
        (5, 25, 29, 30, 44, 47),
        (3, 5, 13, 14, 21, 38),
        (3, 15, 25, 26, 30, 44),
        (4, 8, 18, 22, 27, 47),
        (19, 25, 33, 42, 46, 48),
        (3, 8, 29, 33, 34, 35),
        (5, 9, 44, 46, 48, 49),
    ),
    8: (
        (3, 12, 27, 32, 39, 44),
        (1, 16, 23, 36, 44, 47),
        (2, 15, 30, 38, 39, 46),
        (6, 17, 27, 38, 46, 49),
        (8, 9, 12, 15, 40, 46),
        (6, 8, 9, 30, 36, 43),
        (3, 7, 11, 19, 26, 29),
        (5, 8, 9, 21, 23, 24),
    ),
    9: (
        (1, 6, 23, 33, 35, 45),
        (3, 12, 20, 28, 40, 42),
        (7, 10, 11, 21, 39, 48),
        (3, 6, 22, 28, 30, 31),
        (3, 8, 15, 17, 33, 45),
        (8, 9, 13, 18, 20, 45),
        (12, 13, 35, 41, 44, 45),
        (4, 10, 23, 30, 39, 40),
    ),
    10: (
        (5, 8, 25, 32, 44, 49),
        (3, 5, 17, 19, 34, 41),
        (8, 13, 18, 35, 39, 43),
        (3, 11, 17, 19, 21, 37),
        (3, 8, 10, 11, 30, 35),
        (5, 16, 21, 24, 29, 42),
        (5, 25, 28, 32, 40, 44),
        (8, 13, 22, 28, 39, 45),
    ),
    15: (
        (1, 5, 17, 38, 40, 47),
        (2, 5, 8, 33, 35, 39),
        (3, 4, 9, 31, 42, 48),
        (9, 10, 26, 30, 31, 43),
        (8, 18, 34, 35, 44, 47),
        (9, 16, 17, 19, 34, 45),
        (6, 7, 16, 23, 41, 49),
        (7, 8, 23, 34, 43, 44),
    ),
    20: (
        (1, 10, 11, 12, 46, 49),
        (2, 13, 17, 24, 33, 35),
        (9, 13, 21, 28, 30, 34),
        (8, 15, 19, 32, 37, 39),
        (5, 8, 14, 22, 28, 32),
        (9, 21, 29, 38, 40, 42),
        (10, 26, 32, 33, 41, 48),
        (8, 19, 34, 36, 43, 48),
    ),
    25: (
        (19, 31, 33, 35, 42, 49),
        (1, 13, 21, 23, 39, 41),
        (16, 18, 22, 23, 30, 49),
        (5, 6, 24, 25, 27, 28),
        (7, 23, 29, 36, 38, 44),
        (17, 18, 23, 26, 37, 40),
        (8, 9, 14, 42, 43, 45),
        (1, 11, 21, 40, 41, 46),
    ),
    30: (
        (13, 16, 17, 18, 41, 42),
        (18, 32, 37, 39, 42, 47),
        (1, 6, 18, 19, 37, 48),
        (7, 13, 31, 36, 44, 49),
        (10, 12, 29, 37, 38, 48),
        (15, 25, 26, 34, 39, 43),
        (1, 8, 16, 20, 22, 43),
        (2, 10, 19, 20, 43, 46),
    ),
    40: (
        (4, 5, 7, 9, 19, 30),
        (14, 15, 29, 30, 32, 47),
        (5, 6, 20, 28, 29, 34),
        (6, 21, 24, 35, 37, 40),
        (30, 36, 40, 41, 43, 46),
        (6, 14, 24, 33, 37, 46),
        (4, 12, 14, 35, 43, 48),
        (5, 11, 12, 22, 43, 45),
    ),
    50: (
        (9, 23, 33, 42, 43, 44),
        (2, 13, 25, 32, 43, 47),
        (6, 14, 15, 20, 29, 41),
        (11, 18, 22, 42, 45, 48),
        (1, 9, 17, 44, 45, 47),
        (14, 24, 26, 29, 32, 33),
        (10, 19, 32, 42, 46, 48),
        (5, 15, 25, 34, 41, 49),
    ),
    75: (
        (4, 10, 23, 31, 43, 47),
        (2, 10, 12, 29, 41, 44),
        (23, 27, 29, 35, 41, 45),
        (6, 29, 34, 42, 43, 46),
        (14, 17, 30, 32, 37, 45),
        (15, 20, 34, 38, 44, 49),
        (4, 23, 27, 39, 43, 44),
        (3, 8, 11, 23, 32, 38),
    ),
    100: (
        (6, 22, 36, 43, 47, 49),
        (5, 9, 15, 23, 32, 40),
        (3, 7, 12, 20, 26, 36),
        (5, 9, 11, 19, 33, 38),
        (12, 22, 39, 41, 48, 49),
        (10, 17, 22, 26, 38, 44),
        (6, 9, 36, 38, 44, 47),
        (11, 19, 26, 27, 32, 41),
    ),
    150: (
        (3, 9, 13, 16, 31, 39),
        (11, 21, 32, 33, 38, 42),
        (10, 14, 26, 27, 42, 49),
        (2, 9, 10, 39, 44, 46),
        (3, 9, 16, 22, 32, 36),
        (2, 12, 17, 20, 23, 47),
        (3, 11, 12, 39, 40, 48),
        (10, 11, 21, 24, 32, 37),
    ),
    300: (
        (8, 29, 33, 40, 43, 48),
        (17, 34, 35, 36, 45, 46),
        (2, 9, 13, 16, 32, 34),
        (7, 16, 38, 43, 48, 49),
        (9, 17, 38, 39, 41, 46),
        (23, 27, 35, 38, 44, 45),
        (24, 32, 42, 47, 48, 49),
        (3, 8, 26, 28, 33, 35),
    ),
}

NEGATIVE_SELECTION_GOLDENS: dict[int, tuple[tuple[int, ...], ...]] = {
    20: (
        (3, 9, 17, 20, 34, 41),
        (1, 25, 26, 28, 35, 42),
        (2, 10, 18, 20, 27, 35),
        (11, 18, 28, 34, 43, 44),
        (2, 17, 20, 25, 27, 42),
        (1, 10, 18, 34, 35, 44),
        (1, 9, 18, 26, 34, 42),
        (1, 9, 17, 25, 33, 41),
    ),
    30: (
        (9, 11, 17, 20, 36, 45),
        (1, 27, 31, 32, 46, 47),
        (3, 14, 21, 34, 37, 43),
        (8, 13, 15, 19, 38, 48),
        (6, 11, 17, 26, 35, 38),
        (8, 12, 18, 30, 37, 41),
        (1, 9, 17, 26, 34, 42),
        (1, 9, 17, 25, 33, 41),
    ),
    40: (
        (1, 8, 21, 29, 42, 46),
        (6, 9, 14, 31, 40, 47),
        (4, 15, 22, 27, 43, 44),
        (3, 12, 25, 30, 41, 48),
        (9, 10, 20, 27, 40, 48),
        (15, 25, 26, 29, 35, 38),
        (1, 9, 17, 26, 34, 42),
        (1, 9, 17, 25, 34, 42),
    ),
    50: (
        (3, 21, 23, 28, 43, 48),
        (6, 13, 14, 33, 39, 41),
        (4, 8, 19, 29, 30, 36),
        (15, 18, 22, 37, 40, 44),
        (7, 10, 18, 20, 37, 39),
        (2, 6, 15, 19, 32, 49),
        (1, 9, 17, 25, 34, 42),
        (1, 9, 17, 25, 33, 42),
    ),
    75: (
        (2, 3, 15, 28, 34, 47),
        (10, 12, 19, 32, 39, 48),
        (8, 9, 33, 43, 44, 45),
        (5, 18, 30, 37, 42, 46),
        (1, 20, 21, 41, 42, 43),
        (6, 8, 13, 17, 45, 47),
        (1, 9, 17, 26, 34, 42),
        (1, 9, 17, 25, 33, 42),
    ),
    100: (
        (4, 11, 17, 26, 47, 48),
        (9, 14, 30, 32, 45, 46),
        (2, 7, 10, 25, 41, 44),
        (6, 8, 15, 24, 33, 49),
        (2, 23, 38, 40, 44, 47),
        (5, 7, 26, 27, 32, 34),
        (1, 9, 17, 25, 34, 42),
        (1, 9, 17, 25, 33, 42),
    ),
    150: (
        (6, 23, 24, 35, 40, 48),
        (2, 4, 17, 19, 43, 45),
        (11, 14, 20, 22, 37, 41),
        (10, 28, 29, 32, 38, 39),
        (4, 16, 31, 34, 39, 49),
        (7, 18, 26, 37, 38, 44),
        (2, 10, 18, 26, 35, 43),
        (2, 10, 18, 26, 34, 43),
    ),
    300: (
        (4, 12, 24, 41, 45, 48),
        (5, 7, 13, 27, 30, 40),
        (6, 23, 26, 32, 36, 49),
        (8, 16, 19, 33, 38, 42),
        (2, 21, 29, 31, 35, 46),
        (6, 28, 30, 37, 42, 45),
        (5, 13, 21, 29, 38, 46),
        (5, 13, 21, 29, 37, 46),
    ),
}

# History lengths where this synthetic (pathologically structured, stride-8)
# fixture drives the donor's own dedup down to 7 native tickets -- a
# genuine, donor-faithful, data-dependent closure (see module docstring),
# surfaced by the base adapter's own strict native_ticket_count check.
NEGATIVE_SELECTION_INVALID_OUTPUT_NS = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 25)

QUICK_ML_GOLDENS: dict[int, tuple[tuple[int, ...], ...]] = {
    1: ((1, 9, 17, 25, 33, 41), (1, 2, 3, 4, 9, 17)),
    2: ((1, 9, 17, 25, 33, 41), (1, 2, 3, 4, 10, 18)),
    3: ((1, 9, 17, 25, 33, 41), (3, 4, 5, 11, 17, 19)),
    4: ((1, 9, 17, 25, 33, 41), (4, 5, 6, 12, 18, 20)),
}

QUICK_ML_CLOSURE_NS = tuple(range(5, 25))


# ─── donor-parity: 64 deterministic samples across all three strategies ───


@pytest.mark.parametrize("n", sorted(SOCIAL_WISDOM_GOLDENS))
def test_social_wisdom_matches_golden(n: int) -> None:
    history = _wave12_history(n)
    adapter = BigLottoSocialWisdomPredictorAdapter()
    assert adapter.get_bets(history, LotteryType.BIG_LOTTO) == SOCIAL_WISDOM_GOLDENS[n]


@pytest.mark.parametrize("n", sorted(NEGATIVE_SELECTION_GOLDENS))
def test_negative_selection_matches_golden(n: int) -> None:
    history = _wave12_history(n)
    adapter = BigLottoNegativeSelectionBiglottoAdapter()
    assert adapter.get_bets(history, LotteryType.BIG_LOTTO) == NEGATIVE_SELECTION_GOLDENS[n]


@pytest.mark.parametrize("n", NEGATIVE_SELECTION_INVALID_OUTPUT_NS)
def test_negative_selection_closes_on_short_native_ticket_count(n: int) -> None:
    history = _wave12_history(n)
    with pytest.raises(InvalidOutput):
        BigLottoNegativeSelectionBiglottoAdapter().get_bets(history, LotteryType.BIG_LOTTO)


@pytest.mark.parametrize("n", sorted(QUICK_ML_GOLDENS))
def test_quick_ml_matches_golden(n: int) -> None:
    history = _wave12_history(n)
    adapter = BigLottoQuickMlPredictAdapter()
    assert adapter.get_bets(history, LotteryType.BIG_LOTTO) == QUICK_ML_GOLDENS[n]


@pytest.mark.parametrize("n", QUICK_ML_CLOSURE_NS)
def test_quick_ml_closes_for_history_at_least_five(n: int) -> None:
    history = _wave12_history(n)
    with pytest.raises(Wave12FrozenSourceError) as excinfo:
        BigLottoQuickMlPredictAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert excinfo.value.reason_code == "FROZEN_SOURCE_PATTERN_SLICE_INDEX_ERROR"


def test_wave12_golden_fixture_covers_at_least_sixty_samples() -> None:
    total = (
        len(SOCIAL_WISDOM_GOLDENS)
        + len(NEGATIVE_SELECTION_GOLDENS)
        + len(NEGATIVE_SELECTION_INVALID_OUTPUT_NS)
        + len(QUICK_ML_GOLDENS)
        + len(QUICK_ML_CLOSURE_NS)
    )
    assert total >= 60


# ─── min_history / closure boundary ────────────────────────────────────────


@pytest.mark.parametrize("adapter_cls", PORTFOLIO_ADAPTER_CLASSES)
def test_wave12_adapters_close_below_min_history(adapter_cls: type) -> None:
    with pytest.raises(InsufficientHistory):
        adapter_cls().get_bets((), LotteryType.BIG_LOTTO)


def test_social_wisdom_opens_at_min_history() -> None:
    history = _wave12_history(1)
    assert (
        BigLottoSocialWisdomPredictorAdapter().get_bets(history, LotteryType.BIG_LOTTO)
        == SOCIAL_WISDOM_GOLDENS[1]
    )


def test_quick_ml_opens_at_min_history() -> None:
    history = _wave12_history(1)
    assert (
        BigLottoQuickMlPredictAdapter().get_bets(history, LotteryType.BIG_LOTTO)
        == QUICK_ML_GOLDENS[1]
    )


def test_quick_ml_boundary_four_succeeds_five_closes() -> None:
    assert (
        BigLottoQuickMlPredictAdapter().get_bets(_wave12_history(4), LotteryType.BIG_LOTTO)
        == QUICK_ML_GOLDENS[4]
    )
    with pytest.raises(Wave12FrozenSourceError):
        BigLottoQuickMlPredictAdapter().get_bets(_wave12_history(5), LotteryType.BIG_LOTTO)


def test_target_proxy_changes_with_the_last_draw_identity() -> None:
    a = _target_after_causal_cutoff(_wave12_history(10))
    b = _target_after_causal_cutoff(_wave12_history(11))
    assert a != b


# ─── contract/closure tests parametrized over all three portfolio classes ─


def test_wave12_portfolio_ticket_shape_is_valid() -> None:
    for adapter_cls, n in (
        (BigLottoSocialWisdomPredictorAdapter, 60),
        (BigLottoNegativeSelectionBiglottoAdapter, 100),
        (BigLottoQuickMlPredictAdapter, 4),
    ):
        history = _wave12_history(n)
        bets = adapter_cls().get_bets(history, LotteryType.BIG_LOTTO)
        assert len(bets) == adapter_cls().native_ticket_count
        for ticket in bets:
            assert len(ticket) == 6
            assert len(set(ticket)) == 6
            assert all(1 <= number <= 49 for number in ticket)
            assert list(ticket) == sorted(ticket)


def test_wave12_portfolio_repeated_execution_is_byte_identical() -> None:
    """Proves the exact no-op rerun property: same history in, same tickets out."""

    for adapter_cls, n in (
        (BigLottoSocialWisdomPredictorAdapter, 51),
        (BigLottoNegativeSelectionBiglottoAdapter, 100),
        (BigLottoQuickMlPredictAdapter, 4),
    ):
        history = _wave12_history(n)
        adapter = adapter_cls()
        first = adapter.get_bets(history, LotteryType.BIG_LOTTO)
        second = adapter.get_bets(history, LotteryType.BIG_LOTTO)
        third = adapter_cls().get_bets(history, LotteryType.BIG_LOTTO)
        assert first == second == third


@pytest.mark.parametrize("adapter_cls", PORTFOLIO_ADAPTER_CLASSES)
def test_wave12_portfolio_rejects_unsupported_lottery_type(adapter_cls: type) -> None:
    history = _wave12_history(max(adapter_cls().min_history, 51))
    with pytest.raises(UnsupportedLotteryType):
        adapter_cls().get_bets(history, LotteryType.DAILY_539)


@pytest.mark.parametrize("adapter_cls", PORTFOLIO_ADAPTER_CLASSES)
def test_wave12_portfolio_fails_closed_on_wrong_native_ticket_count(
    adapter_cls: type, monkeypatch: pytest.MonkeyPatch
) -> None:
    def short_predict_all(
        self: object, history: object, lottery_type: object
    ) -> tuple[tuple[int, ...], ...]:
        return ((1, 2, 3, 4, 5, 6),)

    history = _wave12_history(max(adapter_cls().min_history, 4))
    monkeypatch.setattr(adapter_cls, "_predict_all", short_predict_all)
    with pytest.raises(InvalidOutput):
        adapter_cls().get_bets(history, LotteryType.BIG_LOTTO)


def test_wave12_adapters_need_no_filesystem_clock_database_or_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("external state access is forbidden")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(time, "time", forbidden)
    monkeypatch.setattr(time, "monotonic", forbidden)

    history = _wave12_history(300)
    assert (
        BigLottoSocialWisdomPredictorAdapter().get_bets(history, LotteryType.BIG_LOTTO)
        == SOCIAL_WISDOM_GOLDENS[300]
    )
    assert (
        BigLottoNegativeSelectionBiglottoAdapter().get_bets(history, LotteryType.BIG_LOTTO)
        == NEGATIVE_SELECTION_GOLDENS[300]
    )
    with pytest.raises(Wave12FrozenSourceError):
        BigLottoQuickMlPredictAdapter().get_bets(history, LotteryType.BIG_LOTTO)


def test_subprocess_repeatability_across_python_hash_seeds() -> None:
    code = """
import sys
sys.path.insert(0, {src!r})
from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.adapters.biglotto_wave12 import (
    BigLottoSocialWisdomPredictorAdapter,
    BigLottoNegativeSelectionBiglottoAdapter,
    BigLottoQuickMlPredictAdapter,
)

def row(i):
    numbers = tuple(sorted(((i + s * 8) % 49) + 1 for s in range(6)))
    date = f"2020-{{(i%12)+1:02d}}-{{(i%28)+1:02d}}"
    return CausalDrawRow(draw=str(90000000 + i), date=date, numbers=numbers)

history = tuple(row(i) for i in range(300))
outputs = [
    BigLottoSocialWisdomPredictorAdapter().get_bets(history, LotteryType.BIG_LOTTO),
    BigLottoNegativeSelectionBiglottoAdapter().get_bets(history, LotteryType.BIG_LOTTO),
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


@pytest.mark.parametrize("strategy_id", sorted(WAVE12_IDS))
def test_generate_one_bet_fails_closed_for_wave12_portfolio_strategy(strategy_id: str) -> None:
    use_case = build_production_generate_one_bet()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id=strategy_id,
            lottery_type=LotteryType.BIG_LOTTO,
            history=_wave12_history(51),
        )
    )
    assert result.status is GenerateOneBetStatus.WRONG_RESPONSE_PATH
    assert result.reason_code is GenerateOneBetReason.STRATEGY_IS_PORTFOLIO
    assert result.numbers is None


def test_generate_one_bet_does_not_expose_wave12_portfolio_adapters() -> None:
    use_case = build_production_generate_one_bet()
    assert WAVE12_IDS.isdisjoint(use_case._adapters.keys())


def test_generate_portfolio_returns_complete_native_ticket_set_for_each_wave12_strategy() -> None:
    use_case = build_production_generate_portfolio()
    expected_counts = {
        "legacy_biglotto__social_wisdom_predictor__a00829b5d875": 8,
        "legacy_biglotto__negative_selection_biglotto__98f860c52cc2": 8,
    }
    for strategy_id, expected_count in expected_counts.items():
        result = use_case.execute(
            GenerateOneBetInput(
                strategy_id=strategy_id,
                lottery_type=LotteryType.BIG_LOTTO,
                history=_wave12_history(100),
            )
        )
        assert result.status is GeneratePortfolioStatus.OK
        assert result.numbers is not None
        assert len(result.numbers) == expected_count

    quick_ml_result = use_case.execute(
        GenerateOneBetInput(
            strategy_id="legacy_biglotto__quick_ml_predict__8b7ba0b52e2d",
            lottery_type=LotteryType.BIG_LOTTO,
            history=_wave12_history(4),
        )
    )
    assert quick_ml_result.status is GeneratePortfolioStatus.OK
    assert quick_ml_result.numbers is not None
    assert len(quick_ml_result.numbers) == 2

    quick_ml_closed = use_case.execute(
        GenerateOneBetInput(
            strategy_id="legacy_biglotto__quick_ml_predict__8b7ba0b52e2d",
            lottery_type=LotteryType.BIG_LOTTO,
            history=_wave12_history(100),
        )
    )
    assert quick_ml_closed.status is GeneratePortfolioStatus.REPLAY_ERROR
    assert quick_ml_closed.reason_code is GeneratePortfolioReason.REPLAY_ERROR
    assert quick_ml_closed.numbers is None


def test_all_wave12_strategies_are_reachable_through_exactly_one_response_path() -> None:
    one_bet = build_production_generate_one_bet()
    portfolio = build_production_generate_portfolio()
    reachable = set(one_bet._adapters.keys()) | set(portfolio._adapters.keys())
    assert reachable >= WAVE12_IDS
    assert set(one_bet._adapters.keys()) & set(portfolio._adapters.keys()) == set()


# ─── catalog / descriptor invariant tests ──────────────────────────────────


def test_production_catalog_wave12_descriptors_declare_expected_shapes() -> None:
    catalog = production_catalog()
    expected = {
        "legacy_biglotto__social_wisdom_predictor__a00829b5d875": 8,
        "legacy_biglotto__negative_selection_biglotto__98f860c52cc2": 8,
        "legacy_biglotto__quick_ml_predict__8b7ba0b52e2d": 2,
    }
    for strategy_id, native_ticket_count in expected.items():
        descriptor = catalog.get(strategy_id)
        assert descriptor.response_shape is ResponseShape.PORTFOLIO
        assert descriptor.native_ticket_count == native_ticket_count
        assert descriptor.executable is True
        assert descriptor.min_history == 1


def test_production_catalog_now_has_fifty_three_descriptors() -> None:
    """Name pinned at the Wave 12 landing point; later waves append only."""
    catalog = production_catalog()
    assert len(catalog) == 59


def test_wave12_social_wisdom_is_not_an_alias_of_the_pre_existing_strategy() -> None:
    """Shares a family name with the pre-existing, unrelated
    ``biglotto_social_wisdom_anti_popularity`` (ported from
    ``lottery_api/models/replay_strategy_registry.py``, task P541F_R2) --
    confirm this is a genuinely distinct catalog entry, not a duplicate,
    per ``biglotto_full_strategy_catalog_v1.json``'s own non-``DUPLICATE_ALIAS``
    classification for ``lottery_api/models/social_wisdom_predictor.py``."""

    catalog = production_catalog()
    new_entry = catalog.get("legacy_biglotto__social_wisdom_predictor__a00829b5d875")
    old_entry = catalog.get("biglotto_social_wisdom_anti_popularity")
    assert new_entry.adapter_path != old_entry.adapter_path
    assert new_entry.response_shape is ResponseShape.PORTFOLIO
    assert old_entry.response_shape is ResponseShape.SINGLE_TICKET
    assert any(
        "lottery_api/models/social_wisdom_predictor.py" in entry for entry in new_entry.provenance
    )
    assert not any(
        "lottery_api/models/social_wisdom_predictor.py" in entry for entry in old_entry.provenance
    )


def test_wave1_through_wave11_descriptors_are_unaffected_by_wave12() -> None:
    """Existing 50 adapters must remain unchanged."""
    catalog = production_catalog()
    pre_existing_single_ticket_ids = (
        "biglotto_social_wisdom_anti_popularity",
        "biglotto_zone_split_3bet_bet1",
        "legacy_biglotto__graph_predictor__cd70713a5709",
        "legacy_biglotto__backtest_must_hit__909c91fd2fd0",
    )
    for strategy_id in pre_existing_single_ticket_ids:
        descriptor = catalog.get(strategy_id)
        assert descriptor.response_shape is ResponseShape.SINGLE_TICKET
        assert descriptor.native_ticket_count == 1
    pre_existing_portfolio_ids = {
        "legacy_biglotto__core_satellite__611284461323": 3,
        "legacy_biglotto__zone_split__b6144f9d479f": 3,
        "legacy_biglotto__big_lotto_exhaustive_audit__694d353b7ca2": 3,
        "legacy_biglotto__core_satellite__2e82891003b3": 12,
        "legacy_biglotto__auto_discovery_biglotto__06bcb164db84": 54,
    }
    for strategy_id, native_ticket_count in pre_existing_portfolio_ids.items():
        descriptor = catalog.get(strategy_id)
        assert descriptor.response_shape is ResponseShape.PORTFOLIO
        assert descriptor.native_ticket_count == native_ticket_count
