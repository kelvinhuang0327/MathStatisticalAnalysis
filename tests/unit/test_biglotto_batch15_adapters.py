"""Parity and contract tests for the BigLotto native-strategy batch 15
adapters (six ``ColdHunterPredictor`` methods, ``GapPressureScorer``, and two
dynamic-method-selection variants: DM-DMS / DMS-solo).

Golden fixtures below were cross-verified by an independent parity script
(never imported by product code) that: (a) for the six ``ColdHunterPredictor``
methods and ``GapPressureScorer``, ran the REAL, byte-identical donor source
files extracted from the pinned commit via ``git show`` (with ``numpy``
stubbed -- only ``np.mean`` is ever called, and only for a discarded
confidence figure) as ground truth; and (b) for DM-DMS/DMS-solo, independently
re-derived the audit/selection control flow in a differently-shaped
transcription built on the already-tested ``_unified_*_ticket`` functions.
189 checks (9 strategies x ~21 history lengths), 0 mismatches, including the
``zone_momentum_predict`` closures matching the donor's own undersized raw
output at those same lengths.

This module also protects Batch 15's frozen nine-descriptor suffix position at
the time of its migration. Later target-native strategies may append after
that slice without changing Batch 15 membership or order.
"""

# pyright: reportPrivateUsage=false

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
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_batch15 import (
    BigLottoColdHunterPredictAdapter,
    BigLottoGapPressureScorerAdapter,
    BigLottoModerateRankPredictAdapter,
    BigLottoPureColdPredictAdapter,
    BigLottoReboundAwarePredictAdapter,
    BigLottoShortWindowDeviationPredictAdapter,
    BigLottoTestDmDmsBiglottoAdapter,
    BigLottoTestDmsBiglottoAdapter,
    BigLottoZoneMomentumPredictAdapter,
)
from lottolab.strategies.catalog import production_catalog

BATCH15_IDS = {
    "legacy_biglotto__cold_hunter_predict__9e89f2b41add",
    "legacy_biglotto__short_window_deviation_predict__9e89f2b41add",
    "legacy_biglotto__rebound_aware_predict__9e89f2b41add",
    "legacy_biglotto__zone_momentum_predict__9e89f2b41add",
    "legacy_biglotto__pure_cold_predict__9e89f2b41add",
    "legacy_biglotto__moderate_rank_predict__9e89f2b41add",
    "legacy_biglotto__gap_pressure_scorer__5e862ef27ee6",
    "legacy_biglotto__test_dm_dms_biglotto__bad71858012d",
    "legacy_biglotto__test_dms_biglotto__10e39919c3a1",
}
BATCH15_PORTFOLIO_IDS = {"legacy_biglotto__test_dm_dms_biglotto__bad71858012d"}
BATCH15_SINGLE_IDS = BATCH15_IDS - BATCH15_PORTFOLIO_IDS

SINGLE_ADAPTER_CLASSES = (
    BigLottoColdHunterPredictAdapter,
    BigLottoShortWindowDeviationPredictAdapter,
    BigLottoReboundAwarePredictAdapter,
    BigLottoZoneMomentumPredictAdapter,
    BigLottoPureColdPredictAdapter,
    BigLottoModerateRankPredictAdapter,
    BigLottoGapPressureScorerAdapter,
    BigLottoTestDmsBiglottoAdapter,
)


def _batch15_row(index: int) -> CausalDrawRow:
    """Deterministic 6-of-49 draw. Stride 11 is coprime with 49, so six
    consecutive steps always land on six distinct residues -- no collisions.
    A different stride/prefix from wave 14's own fixture generator (stride
    8), so this is not the same golden set."""

    numbers = tuple(sorted(((index + step * 11) % 49) + 1 for step in range(6)))
    assert len(set(numbers)) == 6
    return CausalDrawRow(
        draw=f"b15-{index:05d}",
        date=f"2019-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
        numbers=numbers,
    )


def _batch15_history(n: int) -> tuple[CausalDrawRow, ...]:
    return tuple(_batch15_row(i) for i in range(n))


_GOLDEN_HISTORY_LENGTHS = (
    1, 2, 5, 10, 15, 19, 20, 21, 25, 30, 49, 50, 51, 55, 80, 100, 150, 151, 200, 300, 500, 750,
)

COLD_HUNTER_GOLDENS: dict[int, tuple[int, ...]] = {
    1: (1, 2, 3, 4, 7, 12), 2: (2, 3, 4, 5, 8, 13), 5: (5, 6, 11, 16, 17, 18),
    10: (5, 10, 16, 22, 23, 33), 15: (1, 10, 15, 21, 27, 38), 19: (3, 4, 5, 14, 19, 31),
    20: (4, 5, 6, 15, 20, 32), 21: (5, 6, 7, 16, 21, 33), 25: (9, 10, 11, 20, 25, 37),
    30: (3, 4, 5, 14, 15, 25), 49: (6, 11, 12, 13, 22, 23), 50: (1, 7, 12, 13, 14, 24),
    51: (2, 8, 13, 14, 15, 25), 55: (1, 6, 12, 18, 19, 29), 80: (4, 5, 6, 15, 16, 26),
    100: (2, 8, 13, 14, 15, 25), 150: (3, 9, 14, 15, 16, 26), 151: (4, 10, 15, 16, 17, 27),
    200: (4, 10, 15, 16, 17, 27), 300: (1, 6, 12, 18, 19, 29), 500: (5, 10, 16, 22, 23, 33),
    750: (1, 10, 15, 21, 27, 38),
}

SHORT_WINDOW_DEVIATION_GOLDENS: dict[int, tuple[int, ...]] = {
    1: (2, 3, 4, 5, 6, 8), 2: (3, 4, 5, 6, 9, 10), 5: (6, 17, 18, 19, 20, 21),
    10: (22, 23, 33, 34, 44, 45), 15: (27, 28, 29, 38, 39, 49), 19: (31, 32, 33, 42, 43, 44),
    20: (5, 6, 32, 33, 43, 44), 21: (6, 33, 34, 35, 44, 45), 25: (37, 38, 39, 40, 48, 49),
    30: (4, 5, 6, 42, 43, 44), 49: (12, 13, 23, 24, 34, 35), 50: (13, 14, 24, 25, 35, 36),
    51: (14, 15, 25, 26, 36, 37), 55: (18, 19, 29, 30, 40, 41), 80: (5, 6, 16, 17, 43, 44),
    100: (14, 15, 25, 26, 36, 37), 150: (15, 16, 26, 27, 37, 38), 151: (16, 17, 27, 28, 38, 39),
    200: (16, 17, 27, 28, 38, 39), 300: (18, 19, 29, 30, 40, 41), 500: (22, 23, 33, 34, 44, 45),
    750: (1, 27, 28, 38, 39, 49),
}

REBOUND_AWARE_GOLDENS: dict[int, tuple[int, ...]] = {
    1: (1, 7, 12, 26, 34, 45), 2: (2, 8, 13, 34, 35, 46), 5: (5, 6, 17, 27, 28, 29),
    10: (5, 23, 32, 33, 34, 45), 15: (1, 2, 10, 26, 27, 28), 19: (3, 5, 30, 31, 32, 43),
    20: (4, 6, 7, 26, 32, 33), 21: (5, 7, 8, 27, 33, 34), 25: (1, 9, 11, 31, 37, 38),
    30: (3, 5, 16, 30, 42, 43), 49: (6, 13, 24, 33, 34, 35), 50: (1, 14, 25, 34, 35, 36),
    51: (2, 15, 16, 26, 35, 36), 55: (1, 19, 20, 28, 29, 30), 80: (4, 6, 17, 26, 43, 44),
    100: (2, 15, 16, 26, 35, 36), 150: (3, 16, 26, 27, 36, 38), 151: (4, 17, 18, 26, 27, 28),
    200: (4, 17, 18, 26, 27, 28), 300: (1, 19, 20, 28, 29, 30), 500: (5, 23, 32, 33, 34, 45),
    750: (1, 2, 10, 26, 27, 28),
}

# ─── zone_momentum_predict: the donor has no pad/fallback, so if none of the
#     5 zones reach the -0.05 momentum threshold, at most 5 numbers are ever
#     collected -- a genuine donor-exact closure (see module docstring in
#     biglotto_batch15.py). Closed at: 1, 2, 5, 10, 15, 50, 51, 55, 100, 150,
#     151, 200, 300. ───────────────────────────────────────────────────────

ZONE_MOMENTUM_GOLDENS: dict[int, tuple[int, ...]] = {
    19: (4, 5, 10, 20, 31, 42), 20: (5, 6, 10, 21, 32, 43), 21: (6, 7, 10, 22, 33, 44),
    25: (1, 2, 10, 26, 32, 37), 30: (4, 15, 16, 19, 31, 42), 49: (12, 13, 23, 24, 34, 35),
    80: (5, 16, 17, 19, 32, 43), 500: (1, 11, 22, 33, 44, 45), 750: (1, 16, 27, 28, 38, 49),
}
ZONE_MOMENTUM_CLOSED_LENGTHS = (1, 2, 5, 10, 15, 50, 51, 55, 100, 150, 151, 200, 300)

PURE_COLD_GOLDENS: dict[int, tuple[int, ...]] = {
    1: (2, 3, 4, 5, 6, 8), 2: (3, 4, 5, 6, 9, 10), 5: (6, 17, 18, 19, 20, 21),
    10: (22, 23, 33, 34, 44, 45), 15: (1, 27, 28, 38, 39, 49), 19: (4, 5, 31, 32, 42, 43),
    20: (5, 6, 32, 33, 43, 44), 21: (6, 7, 33, 34, 44, 45), 25: (10, 11, 37, 38, 48, 49),
    30: (4, 5, 15, 16, 42, 43), 49: (12, 13, 23, 24, 34, 35), 50: (13, 14, 24, 25, 35, 36),
    51: (14, 15, 25, 26, 36, 37), 55: (18, 19, 29, 30, 40, 41), 80: (5, 6, 16, 17, 43, 44),
    100: (14, 15, 25, 26, 36, 37), 150: (15, 16, 26, 27, 37, 38), 151: (16, 17, 27, 28, 38, 39),
    200: (16, 17, 27, 28, 38, 39), 300: (18, 19, 29, 30, 40, 41), 500: (22, 23, 33, 34, 44, 45),
    750: (1, 27, 28, 38, 39, 49),
}

MODERATE_RANK_GOLDENS: dict[int, tuple[int, ...]] = {
    1: (2, 3, 4, 8, 9, 10), 2: (1, 3, 4, 7, 12, 45), 5: (3, 4, 6, 9, 10, 48),
    10: (3, 8, 22, 25, 33, 42), 15: (3, 8, 13, 27, 38, 47), 19: (1, 4, 7, 12, 31, 40),
    20: (2, 5, 8, 13, 32, 41), 21: (3, 6, 9, 14, 33, 42), 25: (2, 7, 10, 18, 37, 46),
    30: (1, 4, 7, 12, 15, 40), 49: (4, 9, 12, 15, 23, 48), 50: (5, 10, 13, 16, 24, 49),
    51: (6, 11, 14, 17, 25, 45), 55: (4, 10, 18, 21, 29, 49), 80: (2, 5, 8, 13, 16, 41),
    100: (6, 11, 14, 17, 25, 45), 150: (1, 7, 15, 18, 26, 46), 151: (2, 8, 16, 19, 27, 47),
    200: (2, 8, 16, 19, 27, 47), 300: (4, 10, 18, 21, 29, 49), 500: (3, 8, 22, 25, 33, 42),
    750: (3, 8, 13, 27, 38, 47),
}

GAP_PRESSURE_GOLDENS: dict[int, tuple[int, ...]] = {
    1: (2, 3, 4, 5, 6, 8), 2: (3, 4, 5, 6, 9, 10), 5: (6, 17, 18, 19, 20, 21),
    10: (22, 23, 33, 34, 44, 45), 15: (1, 2, 3, 4, 5, 16), 19: (4, 5, 6, 7, 8, 20),
    20: (5, 6, 7, 8, 9, 21), 21: (6, 7, 8, 9, 10, 22), 25: (1, 10, 11, 12, 13, 14),
    30: (4, 5, 15, 16, 17, 18), 49: (12, 13, 23, 24, 34, 35), 50: (13, 14, 24, 25, 35, 36),
    51: (14, 15, 25, 26, 36, 37), 55: (18, 19, 29, 30, 40, 41), 80: (5, 6, 16, 17, 18, 43),
    100: (14, 15, 25, 26, 36, 37), 150: (15, 16, 26, 27, 37, 38), 151: (16, 17, 27, 28, 38, 39),
    200: (16, 17, 27, 28, 38, 39), 300: (18, 19, 29, 30, 40, 41), 500: (22, 23, 33, 34, 44, 45),
    750: (1, 27, 28, 38, 39, 49),
}

DMS_SOLO_GOLDENS: dict[int, tuple[int, ...]] = {
    1: (1, 7, 12, 23, 34, 45), 2: (1, 2, 7, 8, 12, 13), 5: (1, 2, 3, 4, 5, 7),
    10: (1, 2, 3, 4, 5, 7), 15: (7, 8, 9, 10, 12, 13), 19: (11, 12, 13, 14, 16, 17),
    20: (12, 13, 14, 15, 17, 18), 21: (13, 14, 15, 16, 18, 19), 25: (17, 18, 19, 20, 23, 24),
    30: (23, 27, 28, 29, 30, 32), 49: (2, 40, 46, 47, 48, 49), 50: (1, 3, 41, 47, 48, 49),
    51: (3, 9, 14, 25, 36, 47), 55: (2, 7, 13, 18, 29, 40), 80: (5, 16, 27, 32, 38, 43),
    100: (3, 9, 14, 25, 36, 47), 150: (4, 10, 15, 26, 37, 48), 151: (5, 11, 16, 27, 38, 49),
    200: (5, 11, 16, 27, 38, 49), 300: (2, 7, 13, 18, 29, 40), 500: (6, 11, 17, 22, 33, 44),
    750: (11, 16, 22, 27, 38, 49),
}

DM_DMS_GOLDENS: dict[int, tuple[tuple[int, ...], tuple[int, ...]]] = {
    1: ((1, 7, 12, 23, 34, 45), (14, 20, 21, 22, 48, 49)),
    2: ((1, 2, 7, 8, 12, 13), (5, 22, 23, 25, 48, 49)),
    5: ((1, 2, 3, 4, 5, 7), (3, 21, 22, 23, 24, 48)),
    10: ((22, 31, 32, 33, 43, 44), (1, 2, 3, 4, 5, 7)),
    15: ((5, 11, 16, 27, 38, 49), (30, 31, 32, 33, 43, 44)),
    19: ((4, 9, 15, 20, 31, 42), (31, 32, 33, 42, 43, 44)),
    20: ((5, 10, 16, 21, 32, 43), (30, 31, 32, 33, 43, 44)),
    21: ((6, 11, 17, 22, 33, 44), (31, 32, 33, 42, 43, 44)),
    25: ((10, 15, 21, 26, 37, 48), (39, 40, 41, 42, 43, 44)),
    30: ((4, 15, 20, 26, 31, 42), (23, 27, 28, 29, 30, 32)),
    49: ((1, 12, 23, 34, 39, 45), (21, 22, 32, 33, 43, 44)),
    50: ((2, 13, 24, 35, 40, 46), (22, 32, 33, 42, 43, 44)),
    51: ((3, 9, 14, 25, 36, 47), (22, 32, 33, 42, 43, 44)),
    55: ((2, 7, 13, 18, 29, 40), (26, 27, 28, 35, 36, 39)),
    80: ((5, 16, 27, 32, 38, 43), (22, 28, 29, 30, 31, 33)),
    100: ((3, 9, 14, 25, 36, 47), (22, 32, 33, 42, 43, 44)),
    150: ((4, 10, 15, 26, 37, 48), (14, 25, 36, 45, 46, 47)),
    151: ((5, 11, 16, 27, 38, 49), (26, 35, 36, 37, 47, 48)),
    200: ((5, 11, 16, 27, 38, 49), (26, 35, 36, 37, 47, 48)),
    300: ((2, 7, 13, 18, 29, 40), (26, 27, 28, 35, 36, 39)),
    500: ((6, 11, 17, 22, 33, 44), (21, 22, 32, 33, 43, 44)),
    750: ((11, 16, 22, 27, 38, 49), (30, 31, 32, 33, 43, 44)),
}


# ─── golden parity tests ────────────────────────────────────────────────────


@pytest.mark.parametrize("length", _GOLDEN_HISTORY_LENGTHS)
def test_cold_hunter_predict_golden(length: int) -> None:
    history = _batch15_history(length)
    numbers, special = BigLottoColdHunterPredictAdapter().get_one_bet(
        history, LotteryType.BIG_LOTTO
    )
    assert numbers == COLD_HUNTER_GOLDENS[length]
    assert special is None


@pytest.mark.parametrize("length", _GOLDEN_HISTORY_LENGTHS)
def test_short_window_deviation_predict_golden(length: int) -> None:
    history = _batch15_history(length)
    numbers, _ = BigLottoShortWindowDeviationPredictAdapter().get_one_bet(
        history, LotteryType.BIG_LOTTO
    )
    assert numbers == SHORT_WINDOW_DEVIATION_GOLDENS[length]


@pytest.mark.parametrize("length", _GOLDEN_HISTORY_LENGTHS)
def test_rebound_aware_predict_golden(length: int) -> None:
    history = _batch15_history(length)
    numbers, _ = BigLottoReboundAwarePredictAdapter().get_one_bet(history, LotteryType.BIG_LOTTO)
    assert numbers == REBOUND_AWARE_GOLDENS[length]


@pytest.mark.parametrize(
    "length", [n for n in _GOLDEN_HISTORY_LENGTHS if n not in ZONE_MOMENTUM_CLOSED_LENGTHS]
)
def test_zone_momentum_predict_golden(length: int) -> None:
    history = _batch15_history(length)
    numbers, _ = BigLottoZoneMomentumPredictAdapter().get_one_bet(history, LotteryType.BIG_LOTTO)
    assert numbers == ZONE_MOMENTUM_GOLDENS[length]


@pytest.mark.parametrize("length", ZONE_MOMENTUM_CLOSED_LENGTHS)
def test_zone_momentum_predict_closes_when_no_zone_reaches_threshold(length: int) -> None:
    """The donor has no fallback pad in this method: if none of the 5 zones
    reach the -0.05 momentum threshold, each zone contributes only its
    1-number quota and at most 5 numbers are ever collected -- a genuine
    donor-exact closure, not a bug in this port (see module docstring in
    biglotto_batch15.py). Cross-checked against the real donor source at
    the same lengths in the independent parity script."""

    history = _batch15_history(length)
    with pytest.raises(ValueError, match="FROZEN_UNIFIED_INVALID_TICKET"):
        BigLottoZoneMomentumPredictAdapter().get_one_bet(history, LotteryType.BIG_LOTTO)


@pytest.mark.parametrize("length", _GOLDEN_HISTORY_LENGTHS)
def test_pure_cold_predict_golden(length: int) -> None:
    history = _batch15_history(length)
    numbers, _ = BigLottoPureColdPredictAdapter().get_one_bet(history, LotteryType.BIG_LOTTO)
    assert numbers == PURE_COLD_GOLDENS[length]


@pytest.mark.parametrize("length", _GOLDEN_HISTORY_LENGTHS)
def test_moderate_rank_predict_golden(length: int) -> None:
    history = _batch15_history(length)
    numbers, _ = BigLottoModerateRankPredictAdapter().get_one_bet(history, LotteryType.BIG_LOTTO)
    assert numbers == MODERATE_RANK_GOLDENS[length]


@pytest.mark.parametrize("length", _GOLDEN_HISTORY_LENGTHS)
def test_gap_pressure_scorer_golden(length: int) -> None:
    history = _batch15_history(length)
    numbers, _ = BigLottoGapPressureScorerAdapter().get_one_bet(history, LotteryType.BIG_LOTTO)
    assert numbers == GAP_PRESSURE_GOLDENS[length]


@pytest.mark.parametrize("length", _GOLDEN_HISTORY_LENGTHS)
def test_dms_solo_golden(length: int) -> None:
    history = _batch15_history(length)
    numbers, _ = BigLottoTestDmsBiglottoAdapter().get_one_bet(history, LotteryType.BIG_LOTTO)
    assert numbers == DMS_SOLO_GOLDENS[length]


def test_dms_solo_gate_boundary_produces_different_behavior() -> None:
    """History length 50 (<= the audit gate) always defaults to
    hot_cold_mix with no audit; length 51 (> the gate) runs the fast_audit_p
    audit and may pick a different method -- confirm the two golden tickets
    actually differ, proving the gate is load-bearing."""

    assert DMS_SOLO_GOLDENS[50] != DMS_SOLO_GOLDENS[51]


@pytest.mark.parametrize("length", _GOLDEN_HISTORY_LENGTHS)
def test_dm_dms_golden(length: int) -> None:
    history = _batch15_history(length)
    tickets = BigLottoTestDmDmsBiglottoAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert tickets == DM_DMS_GOLDENS[length]


# ─── boundary / contract tests ──────────────────────────────────────────────


@pytest.mark.parametrize("adapter_class", SINGLE_ADAPTER_CLASSES)
def test_batch15_single_ticket_rejects_insufficient_history(
    adapter_class: type[BigLottoColdHunterPredictAdapter],
) -> None:
    with pytest.raises(InsufficientHistory):
        adapter_class().get_one_bet((), LotteryType.BIG_LOTTO)


def test_dm_dms_rejects_insufficient_history() -> None:
    with pytest.raises(InsufficientHistory):
        BigLottoTestDmDmsBiglottoAdapter().get_bets((), LotteryType.BIG_LOTTO)


@pytest.mark.parametrize("adapter_class", SINGLE_ADAPTER_CLASSES)
def test_batch15_single_ticket_rejects_wrong_lottery_type(
    adapter_class: type[BigLottoColdHunterPredictAdapter],
) -> None:
    history = _batch15_history(50)
    with pytest.raises(UnsupportedLotteryType):
        adapter_class().get_one_bet(history, LotteryType.POWER_LOTTO)


def test_dm_dms_rejects_wrong_lottery_type() -> None:
    history = _batch15_history(50)
    with pytest.raises(UnsupportedLotteryType):
        BigLottoTestDmDmsBiglottoAdapter().get_bets(history, LotteryType.POWER_LOTTO)


@pytest.mark.parametrize("adapter_class", SINGLE_ADAPTER_CLASSES)
def test_batch15_single_ticket_repeated_execution_byte_equality(
    adapter_class: type[BigLottoColdHunterPredictAdapter],
) -> None:
    # length 500: one of the golden lengths, confirmed open (not a
    # zone_momentum_predict closure length) for every batch 15 adapter.
    history = _batch15_history(500)
    first = adapter_class().get_one_bet(history, LotteryType.BIG_LOTTO)
    second = adapter_class().get_one_bet(history, LotteryType.BIG_LOTTO)
    assert first == second


def test_dm_dms_repeated_execution_byte_equality() -> None:
    history = _batch15_history(250)
    first = BigLottoTestDmDmsBiglottoAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    second = BigLottoTestDmDmsBiglottoAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert first == second


# ─── catalog / descriptor invariant tests ──────────────────────────────────


def test_production_catalog_descriptors_declare_expected_shapes() -> None:
    catalog = production_catalog()

    for strategy_id in BATCH15_SINGLE_IDS:
        descriptor = catalog.get(strategy_id)
        assert descriptor.response_shape is ResponseShape.SINGLE_TICKET
        assert descriptor.native_ticket_count == 1
        assert descriptor.executable is True
        assert descriptor.min_history == 1

    dm_dms = catalog.get("legacy_biglotto__test_dm_dms_biglotto__bad71858012d")
    assert dm_dms.response_shape is ResponseShape.PORTFOLIO
    assert dm_dms.native_ticket_count == 2
    assert dm_dms.executable is True
    assert dm_dms.min_history == 1


def test_production_catalog_appends_newer_descriptors_after_batch15() -> None:
    """The 68-strategy Batch-15 closure remains an unchanged prefix.

    Total count reflects every descriptor appended after Batch 15 to date:
    ``b649_new_horizon_minimax_disagreement_r1``; PR #149's
    ``legacy_composite__quick_predict_5bet_ts3_markov_freqort``; and, as of
    ``B_BASE_METHOD_UNIVERSE_INTAKE_BATCH01_R1``,
    ``legacy_biglotto__backtest_biglotto_markov_4bet__aefb54eb345b``.
    """

    catalog = production_catalog()
    assert len(catalog) == 71


def test_wave1_through_wave14_descriptors_are_unaffected_by_batch15() -> None:
    """The 59 pre-existing descriptors and their declaration order must
    remain unchanged; batch 15's nine new descriptors are appended strictly
    after them."""

    catalog = production_catalog()
    all_ids = tuple(descriptor.strategy_id for descriptor in catalog)
    assert len(all_ids) == 71
    pre_existing_ids = all_ids[:59]
    batch15_ids_in_order = all_ids[59:68]
    assert set(pre_existing_ids).isdisjoint(BATCH15_IDS)
    assert set(batch15_ids_in_order) == BATCH15_IDS
    assert batch15_ids_in_order == (
        "legacy_biglotto__cold_hunter_predict__9e89f2b41add",
        "legacy_biglotto__short_window_deviation_predict__9e89f2b41add",
        "legacy_biglotto__rebound_aware_predict__9e89f2b41add",
        "legacy_biglotto__zone_momentum_predict__9e89f2b41add",
        "legacy_biglotto__pure_cold_predict__9e89f2b41add",
        "legacy_biglotto__moderate_rank_predict__9e89f2b41add",
        "legacy_biglotto__gap_pressure_scorer__5e862ef27ee6",
        "legacy_biglotto__test_dm_dms_biglotto__bad71858012d",
        "legacy_biglotto__test_dms_biglotto__10e39919c3a1",
    )
    assert all_ids[68:] == (
        "b649_new_horizon_minimax_disagreement_r1",
        "legacy_composite__quick_predict_5bet_ts3_markov_freqort",
        "legacy_biglotto__backtest_biglotto_markov_4bet__aefb54eb345b",
    )


def test_all_batch15_strategies_are_reachable_through_exactly_one_response_path() -> None:
    one_bet = build_production_generate_one_bet()
    portfolio = build_production_generate_portfolio()
    reachable = set(one_bet._adapters.keys()) | set(portfolio._adapters.keys())
    assert reachable >= BATCH15_IDS
    assert BATCH15_PORTFOLIO_IDS.issubset(portfolio._adapters.keys())
    assert BATCH15_PORTFOLIO_IDS.isdisjoint(one_bet._adapters.keys())
    assert BATCH15_SINGLE_IDS.issubset(one_bet._adapters.keys())
    assert BATCH15_SINGLE_IDS.isdisjoint(portfolio._adapters.keys())


# ─── generate_bet use-case fail-closed / response-path tests ───────────────


def test_generate_one_bet_fails_closed_for_dm_dms_portfolio_strategy() -> None:
    use_case = build_production_generate_one_bet()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id="legacy_biglotto__test_dm_dms_biglotto__bad71858012d",
            lottery_type=LotteryType.BIG_LOTTO,
            history=_batch15_history(50),
        )
    )
    assert result.status is GenerateOneBetStatus.WRONG_RESPONSE_PATH
    assert result.reason_code is GenerateOneBetReason.STRATEGY_IS_PORTFOLIO
    assert result.numbers is None


def test_generate_one_bet_returns_ticket_for_cold_hunter() -> None:
    use_case = build_production_generate_one_bet()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id="legacy_biglotto__cold_hunter_predict__9e89f2b41add",
            lottery_type=LotteryType.BIG_LOTTO,
            history=_batch15_history(100),
        )
    )
    assert result.status is GenerateOneBetStatus.OK
    assert result.numbers == COLD_HUNTER_GOLDENS[100]


def test_generate_portfolio_fails_closed_for_dms_solo_single_ticket_strategy() -> None:
    use_case = build_production_generate_portfolio()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id="legacy_biglotto__test_dms_biglotto__10e39919c3a1",
            lottery_type=LotteryType.BIG_LOTTO,
            history=_batch15_history(50),
        )
    )
    assert result.status is GeneratePortfolioStatus.WRONG_RESPONSE_PATH
    assert result.reason_code is GeneratePortfolioReason.STRATEGY_IS_NOT_PORTFOLIO
    assert result.numbers is None


def test_generate_portfolio_returns_complete_native_ticket_set_for_dm_dms() -> None:
    use_case = build_production_generate_portfolio()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id="legacy_biglotto__test_dm_dms_biglotto__bad71858012d",
            lottery_type=LotteryType.BIG_LOTTO,
            history=_batch15_history(100),
        )
    )
    assert result.status is GeneratePortfolioStatus.OK
    assert result.numbers is not None
    assert len(result.numbers) == 2
