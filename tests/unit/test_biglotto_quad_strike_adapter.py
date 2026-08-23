"""Exact donor parity and production contracts for Big Lotto Quad Strike.

The ordered portfolio goldens below were produced by executing the frozen
``tools/predict_biglotto_quad_strike.py::generate_quad_strike`` donor under
CPython 3.9.6, NumPy 1.26.2, and SciPy 1.12.0. Only the donor module's unused
database import was stubbed; every algorithm function executed unchanged.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence

import pytest

import lottolab.strategies.adapters.biglotto_quad_strike as quad_module
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
from lottolab.strategies.adapters.biglotto_quad_strike import (
    BigLottoQuadStrikeAdapter,
)
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

STRATEGY_ID = "legacy_biglotto__predict_biglotto_quad_strike__e202e664208f"
SOURCE_SHA256 = "e202e664208faf3f998f93f4992a8e2595fe17f2179345bba8d4587deff48a36"
SOURCE_BLOB = "c3416cb8ae787276a020ab4eeb2f7402612381ae"

# The one-draw case has an exact all-zero Fourier-score tie; the donor's pinned
# NumPy 1.26.2 default quicksort permutation is part of the output semantics.
PORTFOLIO_GOLDENS = {
    (1, 17): (
        (19, 20, 21, 22, 24, 49),
        (1, 2, 3, 4, 5, 6),
        (10, 11, 14, 33, 42, 46),
        (7, 8, 9, 12, 13, 15),
    ),
    (49, 17): (
        (26, 28, 35, 41, 42, 45),
        (5, 13, 20, 27, 37, 43),
        (3, 10, 11, 32, 44, 48),
        (17, 24, 33, 38, 46, 49),
    ),
    (50, 17): (
        (15, 35, 40, 41, 42, 45),
        (5, 13, 20, 27, 37, 43),
        (3, 10, 11, 32, 44, 48),
        (17, 24, 33, 38, 46, 49),
    ),
    (99, 17): (
        (2, 6, 7, 15, 25, 41),
        (1, 5, 24, 27, 37, 40),
        (3, 9, 12, 28, 45, 46),
        (16, 17, 20, 22, 35, 44),
    ),
    (100, 17): (
        (7, 8, 11, 15, 38, 41),
        (1, 5, 24, 27, 37, 40),
        (3, 9, 12, 28, 45, 46),
        (16, 17, 20, 22, 35, 44),
    ),
    (499, 17): (
        (17, 26, 35, 39, 42, 46),
        (2, 9, 11, 31, 33, 36),
        (7, 14, 15, 16, 21, 30),
        (3, 4, 8, 10, 12, 13),
    ),
    (500, 17): (
        (18, 19, 35, 40, 47, 49),
        (2, 9, 11, 31, 33, 42),
        (7, 15, 16, 21, 30, 39),
        (3, 4, 8, 10, 12, 13),
    ),
    (500, 97): (
        (26, 29, 31, 33, 36, 46),
        (3, 5, 17, 38, 42, 47),
        (7, 8, 13, 34, 35, 40),
        (1, 4, 12, 24, 27, 48),
    ),
    (501, 17): (
        (15, 19, 40, 42, 45, 49),
        (2, 9, 11, 31, 33, 36),
        (7, 16, 21, 30, 35, 39),
        (3, 4, 8, 10, 13, 25),
    ),
    (700, 17): (
        (16, 21, 35, 37, 38, 39),
        (2, 8, 12, 32, 34, 44),
        (11, 17, 23, 25, 29, 36),
        (1, 24, 28, 43, 46, 48),
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


def test_authoritative_identity_is_unique_cataloged_four_ticket_portfolio() -> None:
    retained = next(
        record
        for record in load_full_strategy_catalog().records
        if record.strategy_id == STRATEGY_ID
    )
    assert retained.legacy_method_id == "tools/predict_biglotto_quad_strike.py"
    assert retained.source_commit == "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
    assert retained.source_blob_id == SOURCE_BLOB
    assert retained.source_sha256 == SOURCE_SHA256
    assert retained.native_ticket_semantics == (
        "FROZEN_SOURCE_NATIVE_4_SOURCE_POSITIONAL_TICKETS_ACROSS_DECLARED_CONFIGURATION_ORDER"
    )

    catalog = production_catalog()
    descriptor = catalog.get(STRATEGY_ID)
    strategy_ids = tuple(item.strategy_id for item in catalog)
    assert len(strategy_ids) == 113
    assert len(set(strategy_ids)) == 113
    assert strategy_ids[-5:] == (
        "legacy_biglotto__backtest_radical_strategy__e54cc0812bc6",
        "legacy_biglotto__power_fourier_rhythm__cb75e72e4c94",
        "legacy_biglotto__backtest_big_lotto_orthogonal_5bet__c4dff46c5a5e",
        STRATEGY_ID,
        "legacy_biglotto__frontend_markov_strategy__2fc1cafea55c",
    )
    assert strategy_ids[:-2].count(STRATEGY_ID) == 0
    assert descriptor.strategy_name == BigLottoQuadStrikeAdapter.strategy_name
    assert descriptor.version == BigLottoQuadStrikeAdapter.strategy_version
    assert descriptor.lifecycle_status is LifecycleStatus.ONLINE
    assert descriptor.executable is True
    assert descriptor.response_shape is ResponseShape.PORTFOLIO
    assert descriptor.native_ticket_count_bounds == (4, 4)
    assert descriptor.min_history == 1
    assert f"legacy_source_sha256:{SOURCE_SHA256}" in descriptor.provenance
    assert "donor_parity:EXACT_ORDERED_PORTFOLIO_EXECUTION_PARITY" in descriptor.provenance
    assert "randomness:NONE_DETERMINISTIC" in descriptor.provenance
    assert ExecutableRegistry(catalog).load_adapter(STRATEGY_ID) is BigLottoQuadStrikeAdapter


@pytest.mark.parametrize(("count", "seed"), tuple(PORTFOLIO_GOLDENS))
def test_complete_portfolio_matches_frozen_donor_golden(count: int, seed: int) -> None:
    actual = BigLottoQuadStrikeAdapter().get_bets(
        _lcg_history(count, seed),
        LotteryType.BIG_LOTTO,
    )

    assert actual == PORTFOLIO_GOLDENS[(count, seed)]
    assert len(actual) == 4
    assert len({number for ticket in actual for number in ticket}) == 24
    assert all(
        len(ticket) == 6
        and ticket == tuple(sorted(ticket))
        and all(1 <= number <= 49 for number in ticket)
        for ticket in actual
    )


def test_fourier_final_score_tie_uses_pinned_numpy_argsort_order() -> None:
    history = _lcg_history(1, 17)

    assert quad_module._fourier_rhythm_ticket(history) == (19, 20, 21, 22, 24, 49)


def test_pinned_numpy_zero_score_argsort_permutation_is_reproduced() -> None:
    assert quad_module._legacy_numpy_argsort((0.0,) * 49) == (
        0,
        26,
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
        25,
        47,
        24,
        22,
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
        11,
        12,
        13,
        14,
        15,
        16,
        17,
        18,
        19,
        20,
        21,
        23,
        48,
    )


def test_fourier_first_peak_period_arithmetic_and_strict_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    series = (1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0)

    def tied_spectrum(signal: tuple[float, ...]) -> tuple[float, ...]:
        spectrum = [0.0] * len(signal)
        spectrum[2 * 3 - 1] = 5.0
        spectrum[2 * 4 - 1] = 5.0
        return tuple(spectrum)

    monkeypatch.setattr(quad_module, "_pocketfft_real_packed", tied_spectrum)
    donor_period = 1.0 / (3 * (1.0 / len(series)))
    assert quad_module._fourier_rhythm_score(series, range(1, 5)) == 1.0 / (
        donor_period + 1.0
    )

    def boundary_spectrum(signal: tuple[float, ...]) -> tuple[float, ...]:
        spectrum = [0.0] * len(signal)
        spectrum[2 * 2 - 1] = 6.0
        return tuple(spectrum)

    monkeypatch.setattr(quad_module, "_pocketfft_real_packed", boundary_spectrum)
    assert quad_module._fourier_rhythm_score(series, range(1, 5)) == 0.0

    def roundoff_larger_spectrum(signal: tuple[float, ...]) -> tuple[float, ...]:
        spectrum = [0.0] * len(signal)
        spectrum[2 * 3 - 1] = 1.0
        spectrum[2 * 4 - 1] = math.nextafter(1.0, math.inf)
        return tuple(spectrum)

    monkeypatch.setattr(quad_module, "_pocketfft_real_packed", roundoff_larger_spectrum)
    assert quad_module._fourier_rhythm_score(series, range(1, 5)) == 1.0 / (10 / 4 + 1.0)


def test_cold_tail_and_sequential_exclusion_match_donor_positions() -> None:
    history = _lcg_history(100, 17)
    first = quad_module._fourier_rhythm_ticket(history)
    second = quad_module._cold_numbers_ticket(history, frozenset(first))
    third = quad_module._tail_balance_ticket(history, frozenset(first + second))

    assert (first, second, third) == PORTFOLIO_GOLDENS[(100, 17)][:3]
    assert set(first).isdisjoint(second)
    assert set(first + second).isdisjoint(third)
    assert quad_module._cold_numbers_ticket(_lcg_history(1, 17), frozenset(first)) == (
        1,
        2,
        3,
        4,
        5,
        6,
    )


def test_gray_threshold_gap_ties_full_history_scan_and_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert quad_module._is_gray_zone_deviation(-1.5)
    assert quad_module._is_gray_zone_deviation(1.5)
    assert not quad_module._is_gray_zone_deviation(math.nextafter(-1.5, -math.inf))
    assert not quad_module._is_gray_zone_deviation(math.nextafter(1.5, math.inf))

    one_row = (CausalDrawRow("1", "2026-01-01", (19, 20, 21, 22, 23, 24)),)
    assert quad_module._gray_zone_gap_ticket(one_row, frozenset(range(1, 19))) == (
        25,
        26,
        27,
        28,
        29,
        30,
    )

    full_history = (
        CausalDrawRow("0", "2025-12-31", (1, 2, 3, 4, 5, 49)),
        *(
            CausalDrawRow(str(index + 1), "2026-01-01", (1, 2, 3, 4, 5, 6))
            for index in range(50)
        ),
    )
    assert quad_module._full_history_gap(full_history, 49) == 50

    snapshots = [
        Counter({19: 6}),
        Counter({49: 50, 48: 40, 47: 30, 46: 20, 45: 10}),
    ]

    def frozen_frequencies(_rows: Sequence[CausalDrawRow]) -> Counter[int]:
        return snapshots.pop(0)

    monkeypatch.setattr(quad_module, "_frequencies", frozen_frequencies)
    assert quad_module._gray_zone_gap_ticket(
        _lcg_history(50, 17), frozenset(range(1, 19))
    ) == (19, 45, 46, 47, 48, 49)


def test_invalid_insufficient_duplicate_illegal_and_unsupported_inputs_fail_closed() -> None:
    adapter = BigLottoQuadStrikeAdapter()
    with pytest.raises(InsufficientHistory):
        adapter.get_bets((), LotteryType.BIG_LOTTO)
    with pytest.raises(InvalidOutput):
        adapter.get_bets(list(_lcg_history(1, 17)), LotteryType.BIG_LOTTO)

    duplicate_identity = (
        CausalDrawRow("1", "2026-01-01", (1, 2, 3, 4, 5, 6)),
        CausalDrawRow("1", "2026-01-02", (7, 8, 9, 10, 11, 12)),
    )
    with pytest.raises(InvalidOutput, match="identities must be unique"):
        adapter.get_bets(duplicate_identity, LotteryType.BIG_LOTTO)

    illegal = (CausalDrawRow("1", "2026-01-01", (1, 2, 3, 4, 5, 50)),)
    with pytest.raises(InvalidOutput):
        adapter.get_bets(illegal, LotteryType.BIG_LOTTO)
    with pytest.raises(UnsupportedLotteryType):
        adapter.get_bets(_lcg_history(1, 17), LotteryType.DAILY_539)


def test_internal_cardinality_or_disjointness_violation_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repeated = ((1, 2, 3, 4, 5, 6),) * 4

    def invalid_portfolio(
        _history: tuple[CausalDrawRow, ...],
    ) -> tuple[tuple[int, ...], ...]:
        return repeated

    monkeypatch.setattr(quad_module, "quad_strike_tickets", invalid_portfolio)
    with pytest.raises(InvalidOutput, match="invalid Quad Strike portfolio"):
        BigLottoQuadStrikeAdapter().get_bets(_lcg_history(1, 17), LotteryType.BIG_LOTTO)


def test_production_dispatch_is_complete_seed_invariant_and_rejects_single_ticket_path() -> None:
    history = _lcg_history(500, 97)
    portfolio = build_production_generate_portfolio()
    first = portfolio.execute(
        GenerateOneBetInput(
            strategy_id=STRATEGY_ID,
            lottery_type=LotteryType.BIG_LOTTO,
            history=history,
            seed=1,
        )
    )
    second = portfolio.execute(
        GenerateOneBetInput(
            strategy_id=STRATEGY_ID,
            lottery_type=LotteryType.BIG_LOTTO,
            history=history,
            seed=999,
        )
    )
    wrong_path = build_production_generate_one_bet().execute(
        GenerateOneBetInput(
            strategy_id=STRATEGY_ID,
            lottery_type=LotteryType.BIG_LOTTO,
            history=history,
        )
    )

    assert first.status is GeneratePortfolioStatus.OK
    assert first.numbers == PORTFOLIO_GOLDENS[(500, 97)]
    assert second == first
    assert wrong_path.status is GenerateOneBetStatus.WRONG_RESPONSE_PATH
    assert wrong_path.reason_code is GenerateOneBetReason.STRATEGY_IS_PORTFOLIO


def test_production_zero_history_returns_insufficient_history() -> None:
    result = build_production_generate_portfolio().execute(
        GenerateOneBetInput(
            strategy_id=STRATEGY_ID,
            lottery_type=LotteryType.BIG_LOTTO,
            history=(),
        )
    )

    assert result.status is GeneratePortfolioStatus.INSUFFICIENT_HISTORY
    assert result.numbers is None
