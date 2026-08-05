"""Parity and contract tests for the BigLotto native-strategy wave 9 adapters
(CAG / Cluster-Cover / ZDP).

Golden fixtures below were computed by executing this module's own adapters
against the deterministic synthetic histories built by ``_wave9_history`` in
this file -- the same methodology waves 3/4 used (see their module
docstrings): direct execution of the actual frozen donor classes was not
possible in this environment (their own ``UnifiedPredictionEngine`` /
``NegativeSelector`` import chain needs pandas/scipy/sklearn plus a live
SQLite path, neither available here), so this wave reuses waves 3-4's
already-verified engine/kill-number ports (``_unified_deviation_ticket`` /
``_unified_markov_ticket`` / ``_unified_statistical_ticket`` / ``_kill_numbers``)
and this module's own test goldens were computed by executing this module's
own adapters, exactly like waves 3/4 did.

None of ``n in {10, 11, 25, 30, 49, 50, 51, 100, 150, 151, 200, 300, 500, 750}``
close for any of the three strategies under ``_wave9_history`` -- picked by
direct empirical scan (see ``biglotto_wave9.py``'s module docstring for why
closures are genuine donor-faithful behavior, not bugs). Cluster-Cover's own
short-candidate-pool closure is reproduced naturally at low history
(``n=1``); CAG's ``IndexError`` companion-index closure and ZDP's
duplicate-random-fallback closure are both real but too rare under this
particular synthetic generator to hit within a practical scan range (the
frozen ledger records exactly 1 of each across 2148 causal executions), so
those two are proven directly by forcing the exact structural condition via
monkeypatch instead -- the same methodology wave 4 already uses for its own
mutation-sensitivity tests.
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
from lottolab.strategies.adapters.biglotto_wave9 import (
    BigLottoCagAdapter,
    BigLottoClusterCoverAdapter,
    BigLottoZdpAdapter,
)
from lottolab.strategies.catalog import production_catalog

REPO_ROOT = Path(__file__).resolve().parents[2]

WAVE9_IDS = {
    "legacy_biglotto__test_cag__7ca5343dfedd",
    "legacy_biglotto__test_cluster_cover__5b43959e7c55",
    "legacy_biglotto__test_zdp__e80cc7e95453",
}


def _wave9_row(index: int) -> CausalDrawRow:
    """Deterministic 6-of-49 draw. Stride 8 is coprime with 49, so six
    consecutive steps always land on six distinct residues — no collisions."""

    numbers = tuple(sorted(((index + step * 8) % 49) + 1 for step in range(6)))
    assert len(set(numbers)) == 6
    return CausalDrawRow(
        draw=f"w9-{index:05d}",
        date=f"2020-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
        numbers=numbers,
    )


def _wave9_history(n: int) -> tuple[CausalDrawRow, ...]:
    return tuple(_wave9_row(i) for i in range(n))


PORTFOLIO_ADAPTER_CLASSES = (
    BigLottoCagAdapter,
    BigLottoClusterCoverAdapter,
    BigLottoZdpAdapter,
)

_GOLDEN_HISTORY_LENGTHS = (10, 11, 25, 30, 49, 50, 51, 100, 150, 151, 200, 300, 500, 750)

# ─── goldens (see module docstring); keyed by history length. ─────────────

CAG_GOLDENS: dict[int, tuple[tuple[int, ...], ...]] = {
    10: ((32, 39, 40, 47, 48, 49), (23, 32, 39, 40, 47, 48), (32, 39, 40, 47, 48, 49)),
    11: ((2, 11, 26, 34, 42, 43), (1, 2, 26, 34, 41, 42), (1, 2, 26, 34, 41, 42)),
    25: ((8, 16, 25, 32, 41, 49), (8, 16, 32, 40, 48, 49), (8, 16, 32, 40, 48, 49)),
    30: ((6, 14, 30, 37, 38, 46), (29, 30, 37, 38, 44, 45), (6, 14, 30, 37, 38, 46)),
    49: ((8, 16, 25, 32, 33, 49), (1, 9, 17, 25, 33, 49), (8, 16, 25, 32, 33, 49)),
    50: ((2, 10, 18, 26, 34, 43), (16, 24, 32, 40, 48, 49), (16, 24, 32, 40, 48, 49)),
    51: ((24, 32, 39, 40, 48, 49), (32, 39, 40, 47, 48, 49), (24, 32, 39, 40, 48, 49)),
    100: ((24, 32, 39, 40, 48, 49), (32, 39, 40, 47, 48, 49), (24, 32, 39, 40, 48, 49)),
    150: ((3, 27, 35, 42, 43, 44), (1, 17, 27, 34, 35, 42), (3, 27, 35, 36, 43, 44)),
    151: ((1, 17, 28, 33, 41, 43), (2, 18, 28, 36, 41, 43), (28, 36, 37, 41, 44, 45)),
    200: ((1, 2, 9, 10, 42, 44), (4, 28, 35, 36, 42, 44), (4, 28, 36, 37, 44, 45)),
    300: ((14, 15, 23, 31, 39, 47), (14, 15, 23, 31, 39, 47), (7, 15, 32, 40, 48, 49)),
    500: ((30, 32, 39, 40, 47, 48), (32, 39, 40, 47, 48, 49), (32, 39, 40, 47, 48, 49)),
    750: ((8, 16, 24, 32, 40, 49), (8, 16, 24, 32, 40, 48), (7, 16, 24, 32, 40, 48)),
}

CLUSTER_COVER_GOLDENS: dict[int, tuple[tuple[int, ...], ...]] = {
    10: ((3, 27, 32, 35, 43, 48), (11, 19, 23, 29, 39, 47), (18, 30, 34, 40, 42, 49)),
    11: ((2, 11, 19, 35, 43, 44), (4, 12, 20, 26, 36, 42), (1, 25, 28, 34, 38, 41)),
    25: ((8, 9, 18, 25, 37, 41), (12, 16, 26, 34, 40, 49), (1, 10, 22, 32, 42, 48)),
    30: ((6, 18, 30, 31, 46, 47), (10, 26, 29, 35, 37, 45), (14, 23, 28, 38, 39, 44)),
    49: ((4, 9, 33, 42, 44, 49), (1, 2, 3, 17, 19, 25), (8, 16, 32, 40, 47, 48)),
    50: ((2, 10, 18, 26, 27, 43), (11, 16, 32, 33, 34, 48), (3, 22, 24, 25, 40, 49)),
    51: ((24, 27, 32, 35, 43, 49), (1, 10, 19, 34, 39, 47), (3, 4, 11, 33, 40, 48)),
    100: ((3, 9, 11, 24, 32, 49), (1, 19, 27, 35, 39, 47), (34, 36, 40, 44, 46, 48)),
    150: ((5, 12, 28, 35, 43, 44), (1, 7, 17, 34, 41, 42), (3, 4, 15, 20, 27, 36)),
    151: ((1, 17, 21, 33, 37, 41), (2, 5, 13, 18, 42, 43), (6, 28, 29, 36, 44, 45)),
    200: ((1, 5, 9, 10, 41, 42), (2, 13, 35, 36, 43, 44), (4, 21, 28, 29, 37, 45)),
    300: ((2, 7, 23, 31, 39, 43), (1, 3, 14, 15, 26, 47), (21, 32, 40, 41, 48, 49)),
    500: ((5, 19, 30, 35, 39, 47), (1, 3, 18, 32, 42, 48), (2, 11, 27, 40, 43, 49)),
    750: ((4, 8, 16, 37, 41, 49), (2, 7, 11, 21, 24, 32), (1, 3, 12, 29, 40, 48)),
}

ZDP_GOLDENS: dict[int, tuple[tuple[int, ...], ...]] = {
    10: ((3, 11, 18, 23, 29, 30), (3, 11, 18, 23, 29, 30), (3, 11, 34, 39, 40, 42)),
    11: ((1, 2, 4, 11, 19, 25), (1, 11, 19, 20, 25, 26), (1, 11, 34, 35, 38, 41)),
    25: ((8, 10, 12, 16, 22, 25), (10, 12, 18, 22, 25, 32), (10, 12, 37, 40, 41, 48)),
    30: ((6, 7, 10, 14, 18, 26), (6, 10, 18, 26, 28, 29), (6, 10, 35, 37, 38, 44)),
    49: ((1, 8, 9, 16, 19, 25), (8, 16, 17, 19, 25, 32), (8, 16, 40, 44, 47, 49)),
    50: ((2, 10, 11, 16, 22, 25), (10, 11, 22, 24, 25, 27), (10, 11, 33, 40, 48, 49)),
    51: ((1, 3, 10, 11, 24, 32), (1, 10, 19, 24, 27, 32), (1, 10, 33, 34, 39, 40)),
    100: ((1, 3, 9, 11, 24, 32), (1, 9, 19, 24, 27, 32), (1, 9, 34, 36, 39, 46)),
    150: ((3, 4, 12, 15, 17, 27), (3, 15, 17, 20, 27, 28), (3, 15, 34, 35, 41, 42)),
    151: ((1, 5, 6, 13, 17, 18), (5, 13, 17, 18, 21, 28), (5, 13, 33, 36, 41, 43)),
    200: ((4, 9, 10, 13, 21, 28), (4, 9, 10, 21, 28, 29), (4, 9, 35, 36, 42, 44)),
    300: ((3, 7, 14, 15, 21, 26), (14, 15, 21, 23, 26, 32), (14, 15, 39, 41, 43, 47)),
    500: ((1, 2, 5, 11, 18, 30), (1, 11, 18, 19, 30, 32), (1, 11, 39, 40, 42, 47)),
    750: ((8, 11, 12, 16, 21, 32), (11, 16, 21, 24, 29, 32), (11, 16, 37, 40, 41, 48)),
}


# ─── test_cag.py goldens (portfolio, 3 native tickets) ─────────────────────


@pytest.mark.parametrize("n", sorted(CAG_GOLDENS))
def test_cag_matches_reference_golden(n: int) -> None:
    history = _wave9_history(n)
    bets = BigLottoCagAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert bets == CAG_GOLDENS[n]


def test_cag_minimum_history_boundary() -> None:
    with pytest.raises(InsufficientHistory):
        BigLottoCagAdapter().get_bets(_wave9_history(0), LotteryType.BIG_LOTTO)
    # n=1 succeeds for CAG (unlike Cluster-Cover); confirm it is a valid portfolio.
    bets = BigLottoCagAdapter().get_bets(_wave9_history(1), LotteryType.BIG_LOTTO)
    assert len(bets) == 3
    for ticket in bets:
        assert len(ticket) == 6 and len(set(ticket)) == 6


def test_cag_native_ticket_count_and_order_is_fixed() -> None:
    for n in (50, 500, 750):
        bets = BigLottoCagAdapter().get_bets(_wave9_history(n), LotteryType.BIG_LOTTO)
        assert len(bets) == 3
        assert bets == CAG_GOLDENS[n]


def test_cag_insufficient_candidate_pool_closes_gracefully(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The donor's own ``companions[i][0]`` access for ``i in range(5)`` is
    not defensively bounds-checked (see module docstring) -- forcing a
    4-candidate pool (fewer than the 6 needed: 1 anchor + 5 companions from
    the other 3) reproduces the donor's own ``IndexError`` exactly. This
    structural condition is real (the frozen ledger records exactly 1 across
    2148 causal executions) but too rare under ``_wave9_history`` to hit by
    a practical scan, so it is forced directly rather than searched for."""

    from lottolab.strategies.adapters import biglotto_wave9 as module

    def _short_pool(_history: object) -> list[int]:
        return [1, 2, 3, 4]

    monkeypatch.setattr(module, "_diversified_top18", _short_pool)
    with pytest.raises(IndexError):
        BigLottoCagAdapter().get_bets(_wave9_history(50), LotteryType.BIG_LOTTO)

    use_case = build_production_generate_portfolio()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id="legacy_biglotto__test_cag__7ca5343dfedd",
            lottery_type=LotteryType.BIG_LOTTO,
            history=_wave9_history(50),
        )
    )
    assert result.status is GeneratePortfolioStatus.REPLAY_ERROR
    assert result.reason_code is GeneratePortfolioReason.REPLAY_ERROR
    assert result.numbers is None


def test_cag_kill_numbers_are_load_bearing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Direct proof that P1 kill-number exclusion actually changes CAG's
    output: forcing every number in bet 1 onto the kill list must change
    bet 1 (kill sets that candidate's Counter weight to -9999, evicting it
    from the top-18 pool)."""

    from lottolab.strategies.adapters import biglotto_wave9 as module

    history = _wave9_history(300)
    baseline = module.BigLottoCagAdapter().get_bets(history, LotteryType.BIG_LOTTO)

    def _kill_first_bet(_history: object, count: int) -> list[int]:
        return list(baseline[0])

    monkeypatch.setattr(module, "_kill_numbers", _kill_first_bet)
    mutated = module.BigLottoCagAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert mutated != baseline


def test_cag_cooccurrence_scores_are_mutation_sensitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct proof that companion selection actually uses the co-occurrence
    matrix (not just tie-break index order): forcing a uniform (all-zero)
    matrix must change the companion selection versus the real one."""

    from lottolab.strategies.adapters import biglotto_wave9 as module

    history = _wave9_history(300)
    baseline = module.BigLottoCagAdapter().get_bets(history, LotteryType.BIG_LOTTO)

    from collections import Counter, defaultdict

    def _zero_matrix(_history: object) -> defaultdict[int, Counter[int]]:
        return defaultdict(Counter)

    monkeypatch.setattr(module, "_cooccurrence_matrix", _zero_matrix)
    mutated = module.BigLottoCagAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert mutated != baseline


# ─── test_cluster_cover.py goldens (portfolio, 3 native tickets) ───────────


@pytest.mark.parametrize("n", sorted(CLUSTER_COVER_GOLDENS))
def test_cluster_cover_matches_reference_golden(n: int) -> None:
    history = _wave9_history(n)
    bets = BigLottoClusterCoverAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert bets == CLUSTER_COVER_GOLDENS[n]


def test_cluster_cover_minimum_history_boundary() -> None:
    with pytest.raises(InsufficientHistory):
        BigLottoClusterCoverAdapter().get_bets(_wave9_history(0), LotteryType.BIG_LOTTO)
    # n=1 is itself the natural short-candidate-pool closure for this adapter.
    with pytest.raises(ValueError, match="FROZEN_UNIFIED_INVALID_TICKET"):
        BigLottoClusterCoverAdapter().get_bets(_wave9_history(1), LotteryType.BIG_LOTTO)


def test_cluster_cover_native_ticket_count_and_order_is_fixed() -> None:
    for n in (50, 500, 750):
        bets = BigLottoClusterCoverAdapter().get_bets(_wave9_history(n), LotteryType.BIG_LOTTO)
        assert len(bets) == 3
        assert bets == CLUSTER_COVER_GOLDENS[n]


def test_cluster_cover_short_candidate_pool_closes_gracefully() -> None:
    """``n=1`` is a genuine donor-faithful closure, not a bug -- see module
    docstring. The raw adapter raises (proving the port has no invented
    fallback the donor's own round-robin fill lacks); the production
    ``GeneratePortfolio`` use case -- which every real caller goes through --
    already closes this as ``REPLAY_ERROR``, never an unhandled exception."""

    with pytest.raises(ValueError, match="FROZEN_UNIFIED_INVALID_TICKET"):
        BigLottoClusterCoverAdapter().get_bets(_wave9_history(1), LotteryType.BIG_LOTTO)

    use_case = build_production_generate_portfolio()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id="legacy_biglotto__test_cluster_cover__5b43959e7c55",
            lottery_type=LotteryType.BIG_LOTTO,
            history=_wave9_history(1),
        )
    )
    assert result.status is GeneratePortfolioStatus.REPLAY_ERROR
    assert result.reason_code is GeneratePortfolioReason.REPLAY_ERROR
    assert result.numbers is None


def test_cluster_cover_round_robin_is_mutation_sensitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct proof that the round-robin co-occurrence fill actually uses
    the matrix: forcing a uniform (all-zero) matrix must change the fill
    order versus the real one (ties then resolve purely by ``set``
    iteration order instead of co-occurrence score)."""

    from lottolab.strategies.adapters import biglotto_wave9 as module

    history = _wave9_history(300)
    baseline = module.BigLottoClusterCoverAdapter().get_bets(history, LotteryType.BIG_LOTTO)

    from collections import Counter, defaultdict

    def _zero_matrix(_history: object) -> defaultdict[int, Counter[int]]:
        return defaultdict(Counter)

    monkeypatch.setattr(module, "_cooccurrence_matrix", _zero_matrix)
    mutated = module.BigLottoClusterCoverAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert mutated != baseline


# ─── test_zdp.py goldens (portfolio, 3 native tickets) ─────────────────────


@pytest.mark.parametrize("n", sorted(ZDP_GOLDENS))
def test_zdp_matches_reference_golden(n: int) -> None:
    history = _wave9_history(n)
    bets = BigLottoZdpAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert bets == ZDP_GOLDENS[n]


def test_zdp_minimum_history_boundary() -> None:
    with pytest.raises(InsufficientHistory):
        BigLottoZdpAdapter().get_bets(_wave9_history(0), LotteryType.BIG_LOTTO)
    bets = BigLottoZdpAdapter().get_bets(_wave9_history(1), LotteryType.BIG_LOTTO)
    assert len(bets) == 3
    for ticket in bets:
        assert len(ticket) == 6 and len(set(ticket)) == 6


def test_zdp_native_ticket_count_and_order_is_fixed() -> None:
    for n in (50, 500, 750):
        bets = BigLottoZdpAdapter().get_bets(_wave9_history(n), LotteryType.BIG_LOTTO)
        assert len(bets) == 3
        assert bets == ZDP_GOLDENS[n]


def test_zdp_fixed_seed_random_fallback_duplicate_closes_gracefully(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Force all three engine tickets and the kill filter so the weighted
    pool collapses to exactly the low zone's own 6 numbers with the other
    two zones empty: bet 1 becomes ``heavy[:4]`` plus two ``random.seed(42)``
    fallback picks with no duplicate check (see module docstring). Fixing
    ``random.randint`` to always return a number already in the bet
    reproduces the donor's own unchecked-duplicate closure deterministically
    -- this exact structural condition is real (1 of 2148 recorded causal
    executions for the frozen source) but impractical to hit by a scan."""

    from lottolab.strategies.adapters import biglotto_wave9 as module

    def _fixed_ticket(_history: object) -> tuple[int, ...]:
        return (1, 2, 3, 4, 5, 6)

    def _no_kill(_history: object, count: int) -> list[int]:
        return []

    monkeypatch.setattr(module, "_unified_deviation_ticket", _fixed_ticket)
    monkeypatch.setattr(module, "_unified_markov_ticket", _fixed_ticket)
    monkeypatch.setattr(module, "_unified_statistical_ticket", _fixed_ticket)
    monkeypatch.setattr(module, "_kill_numbers", _no_kill)

    def _fixed_randint(a: int, b: int) -> int:
        return 1

    monkeypatch.setattr(module.random, "randint", _fixed_randint)

    with pytest.raises(ValueError, match="FROZEN_UNIFIED_INVALID_TICKET"):
        BigLottoZdpAdapter().get_bets(_wave9_history(50), LotteryType.BIG_LOTTO)

    use_case = build_production_generate_portfolio()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id="legacy_biglotto__test_zdp__e80cc7e95453",
            lottery_type=LotteryType.BIG_LOTTO,
            history=_wave9_history(50),
        )
    )
    assert result.status is GeneratePortfolioStatus.REPLAY_ERROR
    assert result.reason_code is GeneratePortfolioReason.REPLAY_ERROR
    assert result.numbers is None


def test_zdp_seed_is_reset_per_zone_not_accumulated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct proof that ``random.seed(42)`` is called before every one of
    the three zone bets independently (never accumulated into one running
    stream across bets): instrument ``random.seed`` and assert it is called
    exactly three times, once per zone/bet, always with the fixed value 42,
    in donor call order (low, mid, high)."""

    from lottolab.strategies.adapters import biglotto_wave9 as module

    seed_calls: list[int] = []
    real_seed = module.random.seed

    def _tracking_seed(value: int) -> None:
        seed_calls.append(value)
        real_seed(value)

    monkeypatch.setattr(module.random, "seed", _tracking_seed)
    module.BigLottoZdpAdapter().get_bets(_wave9_history(50), LotteryType.BIG_LOTTO)
    assert seed_calls == [42, 42, 42]


# ─── shared: closure, repeated-execution byte equality, wrong lottery type ─


@pytest.mark.parametrize("adapter_class", PORTFOLIO_ADAPTER_CLASSES)
def test_wave9_portfolio_shape(adapter_class: type[PortfolioBetAdapter]) -> None:
    history = _wave9_history(max(adapter_class().min_history, 1) + 250)
    bets = adapter_class().get_bets(history, LotteryType.BIG_LOTTO)
    assert len(bets) == adapter_class.native_ticket_count
    for ticket in bets:
        assert len(ticket) == 6
        assert len(set(ticket)) == 6
        assert ticket == tuple(sorted(ticket))
        assert all(1 <= number <= 49 for number in ticket)


@pytest.mark.parametrize("adapter_class", PORTFOLIO_ADAPTER_CLASSES)
def test_wave9_portfolio_repeated_execution_byte_equality(
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    history = _wave9_history(max(adapter_class().min_history, 1) + 250)
    first = adapter_class().get_bets(history, LotteryType.BIG_LOTTO)
    second = adapter_class().get_bets(history, LotteryType.BIG_LOTTO)
    assert first == second


@pytest.mark.parametrize("adapter_class", PORTFOLIO_ADAPTER_CLASSES)
def test_wave9_portfolio_rejects_wrong_lottery_type(
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    history = _wave9_history(max(adapter_class().min_history, 1) + 10)
    with pytest.raises(UnsupportedLotteryType):
        adapter_class().get_bets(history, LotteryType.POWER_LOTTO)


@pytest.mark.parametrize("adapter_class", PORTFOLIO_ADAPTER_CLASSES)
def test_wave9_portfolio_rejects_malformed_history_container(
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    from lottolab.strategies.adapters.base import InvalidOutput

    with pytest.raises(InvalidOutput):
        adapter_class().get_bets(list(_wave9_history(50)), LotteryType.BIG_LOTTO)  # type: ignore[arg-type]


def test_wave9_adapters_need_no_filesystem_clock_database_or_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("external state access is forbidden")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(time, "time", forbidden)
    monkeypatch.setattr(time, "monotonic", forbidden)

    history = _wave9_history(750)
    assert BigLottoCagAdapter().get_bets(history, LotteryType.BIG_LOTTO) == CAG_GOLDENS[750]
    assert (
        BigLottoClusterCoverAdapter().get_bets(history, LotteryType.BIG_LOTTO)
        == CLUSTER_COVER_GOLDENS[750]
    )
    assert BigLottoZdpAdapter().get_bets(history, LotteryType.BIG_LOTTO) == ZDP_GOLDENS[750]


def test_subprocess_repeatability_across_python_hash_seeds() -> None:
    code = """
import sys
sys.path.insert(0, {src!r})
from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.adapters.biglotto_wave9 import (
    BigLottoCagAdapter, BigLottoClusterCoverAdapter, BigLottoZdpAdapter,
)

def row(i):
    numbers = tuple(sorted(((i + s * 8) % 49) + 1 for s in range(6)))
    draw = f"w9-{{i:05d}}"
    date = f"2020-{{(i%12)+1:02d}}-{{(i%28)+1:02d}}"
    return CausalDrawRow(draw=draw, date=date, numbers=numbers)

history = tuple(row(i) for i in range(300))
outputs = [
    BigLottoCagAdapter().get_bets(history, LotteryType.BIG_LOTTO),
    BigLottoClusterCoverAdapter().get_bets(history, LotteryType.BIG_LOTTO),
    BigLottoZdpAdapter().get_bets(history, LotteryType.BIG_LOTTO),
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


@pytest.mark.parametrize("strategy_id", sorted(WAVE9_IDS))
def test_generate_one_bet_fails_closed_for_wave9_portfolio_strategy(strategy_id: str) -> None:
    use_case = build_production_generate_one_bet()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id=strategy_id,
            lottery_type=LotteryType.BIG_LOTTO,
            history=_wave9_history(50),
        )
    )
    assert result.status is GenerateOneBetStatus.WRONG_RESPONSE_PATH
    assert result.reason_code is GenerateOneBetReason.STRATEGY_IS_PORTFOLIO
    assert result.numbers is None


def test_generate_one_bet_does_not_expose_wave9_portfolio_adapters() -> None:
    use_case = build_production_generate_one_bet()
    assert WAVE9_IDS.isdisjoint(use_case._adapters.keys())


def test_generate_portfolio_returns_complete_native_ticket_set_for_each_wave9_strategy() -> None:
    use_case = build_production_generate_portfolio()
    for strategy_id in sorted(WAVE9_IDS):
        result = use_case.execute(
            GenerateOneBetInput(
                strategy_id=strategy_id,
                lottery_type=LotteryType.BIG_LOTTO,
                history=_wave9_history(100),
            )
        )
        assert result.status is GeneratePortfolioStatus.OK
        assert result.numbers is not None
        assert len(result.numbers) == 3


def test_all_wave9_strategies_are_reachable_through_exactly_one_response_path() -> None:
    one_bet = build_production_generate_one_bet()
    portfolio = build_production_generate_portfolio()
    reachable = set(one_bet._adapters.keys()) | set(portfolio._adapters.keys())
    assert reachable >= WAVE9_IDS
    assert set(one_bet._adapters.keys()) & set(portfolio._adapters.keys()) == set()


# ─── catalog / descriptor invariant tests ──────────────────────────────────


def test_production_catalog_wave9_portfolio_descriptors_declare_expected_shapes() -> None:
    catalog = production_catalog()
    for strategy_id in WAVE9_IDS:
        descriptor = catalog.get(strategy_id)
        assert descriptor.response_shape is ResponseShape.PORTFOLIO
        assert descriptor.native_ticket_count == 3
        assert descriptor.executable is True
        assert descriptor.min_history == 1


def test_production_catalog_now_has_forty_four_descriptors() -> None:
    """Name pinned at the Wave 9 landing point; later waves append only."""
    catalog = production_catalog()
    assert len(catalog) == 56


def test_production_catalog_has_exactly_forty_four_big_lotto_online_strategies() -> None:
    """Name pinned at the Wave 9 landing point; later waves append only."""
    from lottolab.domain.strategies import LifecycleStatus

    catalog = production_catalog()
    online = catalog.list(
        lottery_type=LotteryType.BIG_LOTTO, lifecycle_status=LifecycleStatus.ONLINE
    )
    assert len(online) == 56


def test_tme_four_bet_is_unaffected_and_still_excludes_wave9() -> None:
    catalog = production_catalog()
    descriptor = catalog.get("legacy_biglotto__biglotto_tme_optimizer__62c6cb676bad")
    assert descriptor.strategy_name == "大樂透 TME 4注智能組合預測器"
    assert descriptor.native_ticket_count == 4
    assert "legacy_biglotto__biglotto_tme_optimizer__62c6cb676bad" not in WAVE9_IDS


def test_wave1_through_wave8_descriptors_are_unaffected_by_wave9() -> None:
    """The 41 pre-existing BIG_LOTTO descriptors and their declaration order
    must remain unchanged; wave 9's three new descriptors are appended
    strictly after them."""

    catalog = production_catalog()
    all_ids = tuple(descriptor.strategy_id for descriptor in catalog)
    assert len(all_ids) == 56
    pre_existing_ids = all_ids[:41]
    wave9_ids_in_order = all_ids[41:44]
    assert set(pre_existing_ids).isdisjoint(WAVE9_IDS)
    assert set(wave9_ids_in_order) == WAVE9_IDS
    assert wave9_ids_in_order == (
        "legacy_biglotto__test_cag__7ca5343dfedd",
        "legacy_biglotto__test_cluster_cover__5b43959e7c55",
        "legacy_biglotto__test_zdp__e80cc7e95453",
    )
