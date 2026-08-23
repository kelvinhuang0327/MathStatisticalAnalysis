"""Donor-component parity and production contracts for Orthogonal 5-Bet.

The full-portfolio goldens were produced by executing the byte-identical
``tools/backtest_big_lotto_orthogonal_5bet.py`` blob from commit
``49a25effa62fc24f40789c16be6f11bdfb41a4a9`` under CPython 3.9.6,
NumPy 1.26.2, and SciPy 1.12.0. Only its unused database import was stubbed;
the deterministic LCG histories below were supplied directly to
``generate_big_lotto_orthogonal_5bet``.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import cmath
import math

import pytest

import lottolab.strategies.adapters.biglotto_orthogonal_5bet as orthogonal_module
from lottolab.application.legacy_source_grid_native_portfolios_wave46 import (
    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE46_METHOD,
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE46_METHOD,
    ORTHOGONAL_5BET_METHOD_ID,
    load_legacy_source_grid_native_wave46_ledger_for_verification,
)
from lottolab.application.use_cases.generate_bet import (
    GenerateOneBetInput,
    GenerateOneBetReason,
    GenerateOneBetStatus,
    GeneratePortfolioReason,
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
from lottolab.strategies.adapters.biglotto_orthogonal_5bet import (
    BigLottoOrthogonal5BetAdapter,
)
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

STRATEGY_ID = "legacy_biglotto__backtest_big_lotto_orthogonal_5bet__c4dff46c5a5e"
SOURCE_SHA256 = "c4dff46c5a5eff0621cdfba64a623c0a36ad365a4912355b90d3a9ad1c8a0df0"
SOURCE_BLOB = "5721de1742a46add8c3103ea297510dac3ace451"
WINDOW = 500

DONOR_GOLDENS = {
    (500, 17): (
        (18, 19, 35, 40, 47, 49),
        (14, 15, 17, 29, 42, 45),
        (2, 7, 11, 23, 37, 48),
        (16, 21, 27, 30, 39, 46),
        (8, 10, 13, 20, 22, 25),
    ),
    (500, 97): (
        (26, 29, 31, 33, 36, 46),
        (8, 11, 14, 30, 35, 38),
        (3, 9, 15, 18, 25, 41),
        (7, 13, 23, 24, 34, 40),
        (2, 4, 19, 21, 28, 48),
    ),
    (700, 17): (
        (16, 21, 35, 37, 38, 39),
        (3, 5, 22, 25, 31, 32),
        (2, 7, 12, 18, 20, 34),
        (11, 17, 23, 29, 36, 41),
        (14, 24, 26, 28, 47, 48),
    ),
    (700, 97): (
        (9, 15, 17, 25, 27, 41),
        (8, 22, 28, 33, 36, 37),
        (1, 13, 23, 29, 40, 45),
        (7, 16, 18, 24, 44, 48),
        (4, 6, 10, 11, 20, 46),
    ),
}


def _lcg_history(
    count: int,
    seed: int,
    *,
    draw_offset: int = 0,
) -> tuple[CausalDrawRow, ...]:
    state = seed
    rows: list[CausalDrawRow] = []
    for index in range(count):
        selected: list[int] = []
        while len(selected) < 6:
            state = (1103515245 * state + 12345) % (1 << 31)
            number = state % 49 + 1
            if number not in selected:
                selected.append(number)
        rows.append(
            CausalDrawRow(
                draw=str(draw_offset + index + 1),
                date=f"2026-{index % 12 + 1:02d}-{index % 28 + 1:02d}",
                numbers=tuple(sorted(selected)),
            )
        )
    return tuple(rows)


def test_authoritative_identity_is_unique_cataloged_five_ticket_portfolio() -> None:
    retained = next(
        record
        for record in load_full_strategy_catalog().records
        if record.strategy_id == STRATEGY_ID
    )
    assert retained.legacy_method_id == ORTHOGONAL_5BET_METHOD_ID
    assert retained.source_commit == "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
    assert retained.source_blob_id == SOURCE_BLOB
    assert retained.source_sha256 == SOURCE_SHA256
    assert retained.native_ticket_semantics == (
        "FROZEN_SOURCE_NATIVE_5_SOURCE_POSITIONAL_TICKETS_ACROSS_DECLARED_CONFIGURATION_ORDER"
    )
    assert MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE46_METHOD[ORTHOGONAL_5BET_METHOD_ID] == 500
    assert NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE46_METHOD[ORTHOGONAL_5BET_METHOD_ID] == 5

    catalog = production_catalog()
    descriptor = catalog.get(STRATEGY_ID)
    strategy_ids = tuple(item.strategy_id for item in catalog)
    assert len(strategy_ids) == 114
    assert strategy_ids[-6:] == (
        "legacy_biglotto__backtest_radical_strategy__e54cc0812bc6",
        "legacy_biglotto__power_fourier_rhythm__cb75e72e4c94",
        STRATEGY_ID,
        "legacy_biglotto__predict_biglotto_quad_strike__e202e664208f",
        "legacy_biglotto__frontend_markov_strategy__2fc1cafea55c",
        "legacy_biglotto__orthogonal_2bet_optimizer__aa51b0e5e4a4",
    )
    assert strategy_ids[:-4].count(STRATEGY_ID) == 0
    assert descriptor.lifecycle_status is LifecycleStatus.ONLINE
    assert descriptor.executable is True
    assert descriptor.response_shape is ResponseShape.PORTFOLIO
    assert descriptor.native_ticket_count_bounds == (5, 5)
    assert descriptor.min_history == WINDOW
    assert f"legacy_source_sha256:{SOURCE_SHA256}" in descriptor.provenance
    assert "donor_parity:MECHANISM_COMPONENT_PARITY" in descriptor.provenance
    assert "orthogonality:PAIRWISE_DISJOINT_FIVE_TICKETS_NO_NUMBER_REUSE" in (descriptor.provenance)
    assert "randomness:NONE_DETERMINISTIC" in descriptor.provenance
    assert ExecutableRegistry(catalog).load_adapter(STRATEGY_ID) is (BigLottoOrthogonal5BetAdapter)


def test_retained_donor_ledger_proves_five_positions_and_zero_number_reuse() -> None:
    ledger = load_legacy_source_grid_native_wave46_ledger_for_verification()
    eligible = tuple(
        portfolio
        for portfolio in ledger.tickets_by_method[ORTHOGONAL_5BET_METHOD_ID]
        if portfolio is not None
    )

    assert len(eligible) == 1649
    assert all(len(portfolio) == 5 for portfolio in eligible)
    assert all(
        len({number for ticket in portfolio for number in ticket}) == 30 for portfolio in eligible
    )


def test_fourier_component_matches_independent_direct_dft() -> None:
    history = _lcg_history(WINDOW, 17)
    number = 18
    component = orthogonal_module._fourier_rank_component(history, number)
    series = component.appearance_series
    mean = sum(series) / WINDOW
    centered = tuple(value - mean for value in series)
    spectrum = tuple(
        sum(
            value * cmath.exp(-2j * math.pi * frequency * index / WINDOW)
            for index, value in enumerate(centered)
        )
        for frequency in range(WINDOW // 2)
    )
    dominant_index = max(
        range(1, WINDOW // 2),
        key=lambda index: (abs(spectrum[index]), -index),
    )
    period = WINDOW / dominant_index
    last_hit = max(index for index, value in enumerate(series) if value)
    gap = (WINDOW - 1) - last_hit

    assert component.dominant_frequency_index == dominant_index
    assert component.dominant_amplitude == pytest.approx(abs(spectrum[dominant_index]), abs=1e-8)
    assert component.rhythm_period == period
    assert component.last_hit_gap == gap
    assert component.score == pytest.approx(1.0 / (abs(gap - period) + 1.0), abs=1e-10)


def test_frozen_numpy_quicksort_tie_order_is_preserved() -> None:
    assert orthogonal_module._numpy_126_quicksort_argsort((0.0,) * 50) == (
        0,
        27,
        28,
        29,
        30,
        31,
        32,
        33,
        34,
        35,
        36,
        37,
        38,
        39,
        40,
        41,
        42,
        43,
        44,
        45,
        46,
        47,
        26,
        25,
        24,
        23,
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        8,
        9,
        10,
        48,
        11,
        13,
        14,
        15,
        16,
        17,
        18,
        19,
        20,
        21,
        22,
        12,
        49,
    )
    assert orthogonal_module._numpy_126_quicksort_argsort(
        (0.0, 3.0, 1.0, 1.0, 2.0, 1.0, 3.0, 0.0, 2.0, 1.0)
    ) == (0, 7, 2, 3, 5, 9, 4, 8, 1, 6)


@pytest.mark.parametrize(("count", "seed"), tuple(DONOR_GOLDENS))
def test_complete_portfolio_matches_frozen_donor_golden(count: int, seed: int) -> None:
    actual = BigLottoOrthogonal5BetAdapter().get_bets(
        _lcg_history(count, seed),
        LotteryType.BIG_LOTTO,
    )

    assert actual == DONOR_GOLDENS[(count, seed)]
    assert len({number for ticket in actual for number in ticket}) == 30


def test_each_ticket_position_preserves_rank_echo_cold_and_hot_semantics() -> None:
    history = tuple(
        CausalDrawRow(
            draw=str(index + 1),
            date="2026-01-01",
            numbers=(
                (13, 14, 15, 16, 17, 18)
                if index == 98
                else (38, 39, 40, 41, 42, 43)
                if index == 99
                else (44, 45, 46, 47, 48, 49)
            ),
        )
        for index in range(100)
    )
    rank = (*range(1, 50), 0)

    assert orthogonal_module._tickets_from_rank(history, rank) == (
        (1, 2, 3, 4, 5, 6),
        (7, 8, 9, 10, 11, 12),
        (13, 14, 15, 16, 17, 18),
        (44, 45, 46, 47, 48, 49),
        (38, 39, 40, 41, 42, 43),
    )


def test_lag2_differential_changes_only_the_donor_echo_input() -> None:
    base = list(_lcg_history(100, 211))
    rank = (*range(1, 50), 0)
    base[-2] = CausalDrawRow("99", "2026-01-01", (13, 14, 15, 16, 17, 18))
    changed = list(base)
    changed[-2] = CausalDrawRow("99", "2026-01-01", (19, 20, 21, 22, 23, 24))

    first = orthogonal_module._tickets_from_rank(tuple(base), rank)
    second = orthogonal_module._tickets_from_rank(tuple(changed), rank)

    assert first[:2] == second[:2]
    assert first[2] == (13, 14, 15, 16, 17, 18)
    assert second[2] == (19, 20, 21, 22, 23, 24)
    assert len({number for ticket in first for number in ticket}) == 30
    assert len({number for ticket in second for number in ticket}) == 30


def test_latest_500_is_causal_deterministic_and_older_rows_cannot_change_output() -> None:
    suffix = _lcg_history(WINDOW, 97, draw_offset=1000)
    first_prefix = _lcg_history(75, 307)
    second_prefix = _lcg_history(75, 311)
    adapter = BigLottoOrthogonal5BetAdapter()

    first = adapter.get_bets(first_prefix + suffix, LotteryType.BIG_LOTTO)
    second = adapter.get_bets(second_prefix + suffix, LotteryType.BIG_LOTTO)

    assert first == second == adapter.get_bets(suffix, LotteryType.BIG_LOTTO)
    assert adapter.get_bets(suffix, LotteryType.BIG_LOTTO) == first


def test_invalid_insufficient_and_unsupported_inputs_fail_closed() -> None:
    adapter = BigLottoOrthogonal5BetAdapter()
    with pytest.raises(InsufficientHistory):
        adapter.get_bets(_lcg_history(WINDOW - 1, 17), LotteryType.BIG_LOTTO)
    with pytest.raises(InvalidOutput):
        adapter.get_bets(list(_lcg_history(WINDOW, 17)), LotteryType.BIG_LOTTO)
    duplicate_identity = list(_lcg_history(WINDOW, 17))
    duplicate_identity[-1] = CausalDrawRow(
        draw=duplicate_identity[0].draw,
        date=duplicate_identity[-1].date,
        numbers=duplicate_identity[-1].numbers,
    )
    with pytest.raises(InvalidOutput, match="identities must be unique"):
        adapter.get_bets(tuple(duplicate_identity), LotteryType.BIG_LOTTO)
    with pytest.raises(UnsupportedLotteryType):
        adapter.get_bets(_lcg_history(WINDOW, 17), LotteryType.DAILY_539)


def test_production_dispatch_returns_all_five_positions_and_ignores_seed() -> None:
    history = _lcg_history(WINDOW, 17)
    use_case = build_production_generate_portfolio()
    first = use_case.execute(
        GenerateOneBetInput(STRATEGY_ID, LotteryType.BIG_LOTTO, history, seed=1)
    )
    second = use_case.execute(
        GenerateOneBetInput(STRATEGY_ID, LotteryType.BIG_LOTTO, history, seed=999)
    )
    wrong_path = build_production_generate_one_bet().execute(
        GenerateOneBetInput(STRATEGY_ID, LotteryType.BIG_LOTTO, history)
    )

    assert first.status is GeneratePortfolioStatus.OK
    assert first.numbers == DONOR_GOLDENS[(500, 17)]
    assert second == first
    assert wrong_path.status is GenerateOneBetStatus.WRONG_RESPONSE_PATH
    assert wrong_path.reason_code is GenerateOneBetReason.STRATEGY_IS_PORTFOLIO


def test_broken_orthogonality_closes_without_an_alternate_predictor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def overlapping(
        history: tuple[CausalDrawRow, ...],
    ) -> tuple[tuple[int, ...], ...]:
        del history
        return ((1, 2, 3, 4, 5, 6),) * 5

    monkeypatch.setattr(orthogonal_module, "_orthogonal_5bet_tickets", overlapping)
    history = _lcg_history(WINDOW, 17)

    with pytest.raises(InvalidOutput, match="orthogonality failed"):
        BigLottoOrthogonal5BetAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    result = build_production_generate_portfolio().execute(
        GenerateOneBetInput(STRATEGY_ID, LotteryType.BIG_LOTTO, history)
    )
    assert result.status is GeneratePortfolioStatus.INVALID_OUTPUT
    assert result.reason_code is GeneratePortfolioReason.INVALID_OUTPUT
    assert result.numbers is None
