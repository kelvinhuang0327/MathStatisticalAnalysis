"""Mechanism-component parity and runtime contracts for Power Fourier Rhythm."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import cmath
import math
import random

import pytest

import lottolab.strategies.adapters.biglotto_power_fourier_rhythm as fourier_module
from lottolab.application.use_cases.generate_bet import (
    GenerateOneBetInput,
    GenerateOneBetReason,
    GenerateOneBetStatus,
    GeneratePortfolioStatus,
    build_production_generate_one_bet,
    build_production_generate_portfolio,
)
from lottolab.domain.biglotto_full_strategy_catalog import load_full_strategy_catalog
from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import LifecycleStatus, ResponseShape
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_power_fourier_rhythm import (
    BigLottoPowerFourierRhythmAdapter,
)
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

STRATEGY_ID = "legacy_biglotto__power_fourier_rhythm__cb75e72e4c94"
SOURCE_SHA256 = "cb75e72e4c948466a23a432527ca9e5af40e8618c509154f54277ac860d62d59"
SOURCE_BLOB = "8ed6d90393fa175d4f661979d312b8739af21ac8"
WINDOW = 500


def _random_history(
    count: int,
    *,
    seed: int = 4241,
    draw_offset: int = 0,
) -> tuple[CausalDrawRow, ...]:
    rng = random.Random(seed)
    return tuple(
        CausalDrawRow(
            draw=str(draw_offset + index + 1),
            date=f"2026-{index % 12 + 1:02d}-{index % 28 + 1:02d}",
            numbers=tuple(sorted(rng.sample(range(1, 50), 6))),
        )
        for index in range(count)
    )


def _naive_dft(signal: tuple[float, ...]) -> tuple[complex, ...]:
    size = len(signal)
    return tuple(
        sum(
            value * cmath.exp(-2j * math.pi * frequency * index / size)
            for index, value in enumerate(signal)
        )
        for frequency in range(size)
    )


def _oracle_component(
    history: tuple[CausalDrawRow, ...],
    number: int,
) -> tuple[int | None, float, float | None, int | None, float]:
    series = [0.0] * WINDOW
    for index, row in enumerate(history[-WINDOW:]):
        if number in row.numbers:
            series[index] = 1.0
    if sum(series) < 2:
        return None, 0.0, None, None, 0.0
    mean = sum(series) / WINDOW
    spectrum = _naive_dft(tuple(value - mean for value in series))
    dominant_index = max(
        range(1, WINDOW // 2),
        key=lambda index: (abs(spectrum[index]), -index),
    )
    amplitude = abs(spectrum[dominant_index])
    period = WINDOW / dominant_index
    if not 2 < period < WINDOW / 2:
        return dominant_index, amplitude, period, None, 0.0
    last_hit = max(index for index, value in enumerate(series) if value)
    gap = (WINDOW - 1) - last_hit
    return dominant_index, amplitude, period, gap, 1.0 / (abs(gap - period) + 1.0)


def test_authoritative_identity_is_unique_cataloged_fixed_portfolio() -> None:
    retained = next(
        record
        for record in load_full_strategy_catalog().records
        if record.strategy_id == STRATEGY_ID
    )
    assert retained.legacy_method_id == "tools/power_fourier_rhythm.py"
    assert retained.source_commit == "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
    assert retained.source_blob_id == SOURCE_BLOB
    assert retained.source_sha256 == SOURCE_SHA256
    assert retained.native_ticket_semantics == (
        "FROZEN_SOURCE_NATIVE_2_SOURCE_POSITIONAL_TICKETS_ACROSS_DECLARED_CONFIGURATION_ORDER"
    )

    catalog = production_catalog()
    descriptor = catalog.get(STRATEGY_ID)
    strategy_ids = tuple(item.strategy_id for item in catalog)
    assert len(strategy_ids) == 122
    assert strategy_ids[-14:-2] == (
        "legacy_biglotto__backtest_radical_strategy__e54cc0812bc6",
        STRATEGY_ID,
        "legacy_biglotto__backtest_big_lotto_orthogonal_5bet__c4dff46c5a5e",
        "legacy_biglotto__predict_biglotto_quad_strike__e202e664208f",
        "legacy_biglotto__frontend_markov_strategy__2fc1cafea55c",
        "legacy_biglotto__orthogonal_2bet_optimizer__aa51b0e5e4a4",
        "legacy_biglotto__frontend_trend_strategy__a5f4554c80ef",
        "legacy_biglotto__frontend_bayesian_strategy__baa3045817fb",
        "legacy_biglotto__biglotto_2bet_hedging__07a3aa455074",
        "legacy_biglotto__frontend_frequency_strategy__2e3e8febb5f1",
        "legacy_biglotto__frontend_deviation_strategy__3c895052122e",
        "legacy_biglotto__frontend_hot_cold_mix_strategy__92e0540fac02",
    )
    assert strategy_ids[-2] == "legacy_biglotto__frontend_odd_even_balance_strategy__5b7f125437d0"
    assert strategy_ids[-1] == "legacy_biglotto__frontend_sum_range_strategy__4941213e6c46"
    assert strategy_ids[:-13].count(STRATEGY_ID) == 0
    assert descriptor.lifecycle_status is LifecycleStatus.ONLINE
    assert descriptor.executable is True
    assert descriptor.response_shape is ResponseShape.PORTFOLIO
    assert descriptor.native_ticket_count_bounds == (2, 2)
    assert descriptor.min_history == WINDOW
    assert f"legacy_source_sha256:{SOURCE_SHA256}" in descriptor.provenance
    assert "donor_parity:MECHANISM_COMPONENT_PARITY" in descriptor.provenance
    assert "randomness:NONE_DETERMINISTIC" in descriptor.provenance
    assert "phase_rule:NONE" in descriptor.provenance
    assert "harmonic_combination:NONE" in descriptor.provenance

    assert ExecutableRegistry(catalog).load_adapter(STRATEGY_ID) is (
        BigLottoPowerFourierRhythmAdapter
    )


def test_fixed_source_signal_uses_latest_history_and_trailing_zero_padding() -> None:
    history = tuple(
        CausalDrawRow(
            draw=str(index + 1),
            date="2026-01-01",
            numbers=(1, 2, 3, 4, 5, 6) if index % 7 == 0 else (2, 3, 4, 5, 6, 7),
        )
        for index in range(100)
    )

    series = fourier_module._appearance_series(history, 1)

    assert len(series) == WINDOW
    assert series[:100] == tuple(1.0 if index % 7 == 0 else 0.0 for index in range(100))
    assert series[100:] == (0.0,) * 400


def test_transform_frequency_amplitude_period_gap_and_score_match_naive_dft() -> None:
    history = _random_history(WINDOW, seed=7919)
    number = 17
    component = fourier_module._fourier_rhythm_component(history, number)
    oracle = _oracle_component(history, number)

    mean = sum(component.appearance_series) / WINDOW
    expected_detrended = tuple(value - mean for value in component.appearance_series)
    expected_spectrum = _naive_dft(expected_detrended)

    assert component.detrended_series == expected_detrended
    assert component.spectrum == pytest.approx(expected_spectrum, abs=1e-8)
    assert component.dominant_frequency_index == oracle[0]
    assert component.dominant_amplitude == pytest.approx(oracle[1], abs=1e-8)
    assert component.rhythm_period == oracle[2]
    assert component.last_hit_gap == oracle[3]
    assert component.score == pytest.approx(oracle[4], abs=1e-10)


def test_number_ranking_and_ticket_construction_preserve_consecutive_chunks() -> None:
    scores = {number: 0.0 for number in range(1, 50)}
    scores.update(
        {
            49: 9.0,
            2: 9.0,
            18: 8.0,
            7: 8.0,
            30: 7.0,
            11: 7.0,
            48: 6.0,
            3: 6.0,
            17: 5.0,
            8: 5.0,
            29: 4.0,
            12: 4.0,
        }
    )

    assert fourier_module._tickets_from_scores(scores) == (
        (2, 7, 11, 18, 30, 49),
        (3, 8, 12, 17, 29, 48),
    )


def test_complete_mechanism_is_deterministic_legal_and_uses_exactly_two_tickets() -> None:
    history = _random_history(WINDOW, seed=104729)
    adapter = BigLottoPowerFourierRhythmAdapter()

    first = adapter.get_bets(history, LotteryType.BIG_LOTTO)
    second = adapter.get_bets(history, LotteryType.BIG_LOTTO)

    assert second == first
    assert len(first) == 2
    assert len(set(first[0]) | set(first[1])) == 12
    assert set(first[0]).isdisjoint(first[1])
    assert all(
        len(ticket) == 6
        and ticket == tuple(sorted(ticket))
        and all(1 <= number <= 49 for number in ticket)
        for ticket in first
    )


def test_latest_500_window_is_causal_and_older_rows_cannot_change_output() -> None:
    suffix = _random_history(WINDOW, seed=15485863, draw_offset=100)
    first_prefix = _random_history(100, seed=101, draw_offset=0)
    second_prefix = _random_history(100, seed=103, draw_offset=0)
    adapter = BigLottoPowerFourierRhythmAdapter()

    first = adapter.get_bets(first_prefix + suffix, LotteryType.BIG_LOTTO)
    second = adapter.get_bets(second_prefix + suffix, LotteryType.BIG_LOTTO)

    assert first == second == adapter.get_bets(suffix, LotteryType.BIG_LOTTO)


def test_invalid_insufficient_and_unsupported_inputs_fail_closed() -> None:
    adapter = BigLottoPowerFourierRhythmAdapter()
    with pytest.raises(InsufficientHistory):
        adapter.get_bets(_random_history(WINDOW - 1), LotteryType.BIG_LOTTO)
    with pytest.raises(InvalidOutput):
        adapter.get_bets(list(_random_history(WINDOW)), LotteryType.BIG_LOTTO)
    duplicate_identity = list(_random_history(WINDOW))
    duplicate_identity[-1] = CausalDrawRow(
        draw=duplicate_identity[0].draw,
        date=duplicate_identity[-1].date,
        numbers=duplicate_identity[-1].numbers,
    )
    with pytest.raises(InvalidOutput, match="identities must be unique"):
        adapter.get_bets(tuple(duplicate_identity), LotteryType.BIG_LOTTO)
    with pytest.raises(UnsupportedLotteryType):
        adapter.get_bets(_random_history(WINDOW), LotteryType.DAILY_539)


def test_production_generation_dispatches_complete_deterministic_portfolio() -> None:
    history = _random_history(WINDOW, seed=32452843)
    request = GenerateOneBetInput(
        strategy_id=STRATEGY_ID,
        lottery_type=LotteryType.BIG_LOTTO,
        history=history,
    )

    first = build_production_generate_portfolio().execute(request)
    second = build_production_generate_portfolio().execute(request)
    wrong_path = build_production_generate_one_bet().execute(request)

    assert first.status is GeneratePortfolioStatus.OK
    assert first.numbers == BigLottoPowerFourierRhythmAdapter().get_bets(
        history, LotteryType.BIG_LOTTO
    )
    assert second == first
    assert wrong_path.status is GenerateOneBetStatus.WRONG_RESPONSE_PATH
    assert wrong_path.reason_code is GenerateOneBetReason.STRATEGY_IS_PORTFOLIO
