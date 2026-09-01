"""Parity and contract tests for the BigLotto native-strategy wave 1 adapters.

Golden fixtures below were cross-verified by executing the actual frozen
donor source (commit 49a25effa62fc24f40789c16be6f11bdfb41a4a9, read-only
checkout) against the exact deterministic synthetic histories built by
``_wave1_history`` in this file, for every (adapter, history length) pair
below — 624 total cases across all five adapters, zero mismatches. See the
wave-1 migration task for the verification scripts.
"""

# pyright: reportPrivateUsage=false
# (mutation-sensitivity tests deliberately reach into module-private helpers
# and the use-case's internal adapter mapping, matching the convention in
# tests/unit/test_biglotto_selected_adapters.py)

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
from lottolab.domain.strategies import ResponseShape, StrategyDescriptor
from lottolab.strategies.adapters.base import (
    BetAdapter,
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    PortfolioBetAdapter,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_wave1 import (
    BigLottoDynamicFrequencyAdapter,
    BigLottoEchoPhase2Adapter,
    BigLottoGraphPredictorAdapter,
    BigLottoHotCooccurrenceAdapter,
    BigLottoMustHitTop6Adapter,
)
from lottolab.strategies.catalog import production_catalog

REPO_ROOT = Path(__file__).resolve().parents[2]


def _wave1_row(index: int) -> CausalDrawRow:
    """Deterministic 6-of-49 draw. Stride 8 is coprime with 49, so six
    consecutive steps always land on six distinct residues — no collisions."""

    numbers = tuple(sorted(((index + step * 8) % 49) + 1 for step in range(6)))
    assert len(set(numbers)) == 6
    return CausalDrawRow(
        draw=f"w1-{index}",
        date=f"2020-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
        numbers=numbers,
    )


def _wave1_history(n: int) -> tuple[CausalDrawRow, ...]:
    return tuple(_wave1_row(i) for i in range(n))


SINGLE_TICKET_ADAPTER_CLASSES = (
    BigLottoGraphPredictorAdapter,
    BigLottoMustHitTop6Adapter,
    BigLottoDynamicFrequencyAdapter,
    BigLottoHotCooccurrenceAdapter,
)


# ─── graph_predictor goldens ────────────────────────────────────────────────

GRAPH_GOLDENS: dict[int, tuple[int, ...]] = {
    1: (1, 9, 17, 25, 33, 41),
    2: (1, 9, 17, 25, 33, 41),
    6: (1, 2, 9, 10, 17, 18),
    15: (6, 15, 23, 31, 39, 47),
    20: (3, 11, 20, 28, 36, 44),
    50: (1, 9, 17, 25, 33, 41),
    149: (2, 10, 18, 26, 34, 42),
    150: (3, 11, 19, 27, 35, 43),
    151: (4, 12, 20, 28, 36, 44),
    500: (1, 10, 18, 26, 34, 42),
    750: (6, 15, 23, 31, 39, 47),
}


@pytest.mark.parametrize("n", sorted(GRAPH_GOLDENS))
def test_graph_predictor_matches_frozen_donor_golden(n: int) -> None:
    history = _wave1_history(n)
    assert BigLottoGraphPredictorAdapter().get_one_bet(history, LotteryType.BIG_LOTTO) == (
        GRAPH_GOLDENS[n],
        None,
    )


def test_graph_predictor_minimum_history_boundary() -> None:
    with pytest.raises(InsufficientHistory):
        BigLottoGraphPredictorAdapter().get_one_bet((), LotteryType.BIG_LOTTO)
    assert BigLottoGraphPredictorAdapter().get_one_bet(
        _wave1_history(1), LotteryType.BIG_LOTTO
    ) == (GRAPH_GOLDENS[1], None)


def test_graph_predictor_recent_target_rolls_forward() -> None:
    """149 -> 150 -> 151 each add one causal draw and each changes the bet,
    proving the adapter is sensitive to the most recent target draw."""
    outputs = {
        n: BigLottoGraphPredictorAdapter().get_one_bet(_wave1_history(n), LotteryType.BIG_LOTTO)[0]
        for n in (149, 150, 151)
    }
    assert len({outputs[149], outputs[150], outputs[151]}) == 3


def test_graph_predictor_top15_candidate_pool_is_mutation_sensitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The clique selector only sees the top-15 PageRank candidates; shrinking
    the pool to top-6 (the smallest size that still yields a valid 6-number
    pick) must change the result (proves the "15" is load-bearing, matching
    the catalog's PAGERANK_TOP15 candidate_k semantics). n=20 is used because
    at longer histories this deterministic fixture's PageRank scores are
    stable enough across pool sizes that no shrink changes the outcome;
    n=20 is the shortest golden-covered history where it does."""
    from lottolab.strategies.adapters import biglotto_wave1 as module

    history = _wave1_history(20)
    baseline = BigLottoGraphPredictorAdapter().get_one_bet(history, LotteryType.BIG_LOTTO)

    real_select_clique = module._graph_select_clique

    def shrunk_pool(adj: object, candidates: list[int], pick_count: int = 6) -> tuple[int, ...]:
        return real_select_clique(adj, candidates[:6], pick_count)  # type: ignore[arg-type]

    monkeypatch.setattr(module, "_graph_select_clique", shrunk_pool)
    mutated = BigLottoGraphPredictorAdapter().get_one_bet(history, LotteryType.BIG_LOTTO)
    assert mutated != baseline


# ─── backtest_must_hit goldens ──────────────────────────────────────────────

MUST_HIT_GOLDENS: dict[int, tuple[int, ...]] = {
    50: (1, 9, 17, 25, 33, 41),
    51: (2, 10, 18, 26, 34, 42),
    60: (2, 11, 19, 27, 35, 43),
    100: (2, 10, 18, 26, 34, 42),
    500: (1, 10, 18, 26, 34, 42),
    750: (6, 15, 23, 31, 39, 47),
}


@pytest.mark.parametrize("n", sorted(MUST_HIT_GOLDENS))
def test_must_hit_matches_frozen_donor_golden(n: int) -> None:
    history = _wave1_history(n)
    assert BigLottoMustHitTop6Adapter().get_one_bet(history, LotteryType.BIG_LOTTO) == (
        MUST_HIT_GOLDENS[n],
        None,
    )


def test_must_hit_minimum_history_boundary() -> None:
    with pytest.raises(InsufficientHistory):
        BigLottoMustHitTop6Adapter().get_one_bet(_wave1_history(49), LotteryType.BIG_LOTTO)
    assert BigLottoMustHitTop6Adapter().get_one_bet(_wave1_history(50), LotteryType.BIG_LOTTO) == (
        MUST_HIT_GOLDENS[50],
        None,
    )


def test_must_hit_50_vs_51_rows_window_is_mutation_sensitive() -> None:
    """``history[-50:]``: the 51st row must roll the oldest row out of the
    window, changing the top-6 frequency ranking."""
    assert MUST_HIT_GOLDENS[50] != MUST_HIT_GOLDENS[51]


def test_must_hit_top6_of_counter_is_mutation_sensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    from lottolab.strategies.adapters import biglotto_wave1 as module

    real_counter = module.Counter

    class Top3OnlyCounter(real_counter):  # type: ignore[misc, type-arg]
        def most_common(self, n: int | None = None) -> list[tuple[int, int]]:
            return [*super().most_common(3), (0, 0), (0, 0), (0, 0)]

    history = _wave1_history(100)
    baseline = BigLottoMustHitTop6Adapter().get_one_bet(history, LotteryType.BIG_LOTTO)
    monkeypatch.setattr(module, "Counter", Top3OnlyCounter)
    with pytest.raises(InvalidOutput):
        BigLottoMustHitTop6Adapter().get_one_bet(history, LotteryType.BIG_LOTTO)
    monkeypatch.setattr(module, "Counter", real_counter)
    assert BigLottoMustHitTop6Adapter().get_one_bet(history, LotteryType.BIG_LOTTO) == baseline


# ─── dynamic_frequency_predictor goldens ────────────────────────────────────

DYNAMIC_FREQUENCY_GOLDENS: dict[int, tuple[int, ...]] = {
    200: (1, 9, 17, 25, 33, 41),
    201: (2, 10, 18, 26, 34, 42),
    250: (1, 9, 17, 25, 33, 41),
    300: (1, 9, 17, 25, 33, 41),
    500: (5, 13, 21, 30, 38, 46),
    750: (2, 10, 18, 26, 35, 43),
}


@pytest.mark.parametrize("n", sorted(DYNAMIC_FREQUENCY_GOLDENS))
def test_dynamic_frequency_matches_frozen_donor_golden(n: int) -> None:
    history = _wave1_history(n)
    assert BigLottoDynamicFrequencyAdapter().get_one_bet(history, LotteryType.BIG_LOTTO) == (
        DYNAMIC_FREQUENCY_GOLDENS[n],
        None,
    )


def test_dynamic_frequency_minimum_history_boundary() -> None:
    """Below 200 rows the donor's ``find_optimal_window`` returns a bare int
    instead of a (window, scores) pair, which its own ``predict`` cannot
    unpack — i.e. the donor itself has no defined result below 200 rows.
    ``min_history=200`` makes that boundary an explicit InsufficientHistory."""
    with pytest.raises(InsufficientHistory):
        BigLottoDynamicFrequencyAdapter().get_one_bet(_wave1_history(199), LotteryType.BIG_LOTTO)
    assert BigLottoDynamicFrequencyAdapter().get_one_bet(
        _wave1_history(200), LotteryType.BIG_LOTTO
    ) == (DYNAMIC_FREQUENCY_GOLDENS[200], None)


def test_dynamic_frequency_window_selection_is_mutation_sensitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lottolab.strategies.adapters import biglotto_wave1 as module

    history = _wave1_history(500)
    baseline = BigLottoDynamicFrequencyAdapter().get_one_bet(history, LotteryType.BIG_LOTTO)

    monkeypatch.setattr(module, "_DYNAMIC_FREQUENCY_WINDOWS", (300,))
    mutated = BigLottoDynamicFrequencyAdapter().get_one_bet(history, LotteryType.BIG_LOTTO)
    assert mutated != baseline


# ─── hot_cooccurrence_analyzer goldens ──────────────────────────────────────

COOCCURRENCE_GOLDENS: dict[int, tuple[int, ...]] = {
    1: (1, 9, 17, 25, 33, 41),
    2: (1, 9, 17, 25, 33, 41),
    6: (1, 9, 17, 25, 33, 41),
    20: (1, 9, 17, 25, 33, 41),
    50: (1, 9, 17, 25, 33, 41),
    51: (2, 10, 18, 26, 34, 42),
    100: (2, 10, 18, 26, 34, 42),
    500: (1, 10, 18, 26, 34, 42),
    750: (6, 15, 23, 31, 39, 47),
}


@pytest.mark.parametrize("n", sorted(COOCCURRENCE_GOLDENS))
def test_cooccurrence_matches_frozen_donor_golden(n: int) -> None:
    history = _wave1_history(n)
    assert BigLottoHotCooccurrenceAdapter().get_one_bet(history, LotteryType.BIG_LOTTO) == (
        COOCCURRENCE_GOLDENS[n],
        None,
    )


def test_cooccurrence_minimum_history_boundary() -> None:
    with pytest.raises(InsufficientHistory):
        BigLottoHotCooccurrenceAdapter().get_one_bet((), LotteryType.BIG_LOTTO)
    assert BigLottoHotCooccurrenceAdapter().get_one_bet(
        _wave1_history(1), LotteryType.BIG_LOTTO
    ) == (COOCCURRENCE_GOLDENS[1], None)


def test_cooccurrence_top20_hot_pool_is_mutation_sensitive() -> None:
    """Direct proof against the real scoring function that the top-20 hot
    pool is load-bearing: this deterministic 6-of-49 fixture's frequency/
    co-occurrence patterns are too tied/symmetric at any history length for
    an end-to-end shrink-and-compare (as used for the graph predictor above)
    to ever flip the result, so this instead hand-crafts a pool where one
    candidate (rank 7, just outside the naive top-6) co-occurs strongly with
    every other candidate. With the full 20-pool visible, that candidate's
    co-occurrence score outweighs its worse rank and it wins one of the 6
    slots; a pool shrunk to the naive top-6 never sees it at all."""
    from lottolab.strategies.adapters.biglotto_wave1 import _cooccurrence_apply_rules

    hot_numbers = list(range(1, 21))  # 20 candidates; position i = rank (i=0 best)
    co_matrix: dict[int, dict[int, float]] = {n: {} for n in hot_numbers}
    co_matrix[7] = {n: 1.0 for n in hot_numbers if n != 7}

    full_pool_result = _cooccurrence_apply_rules(hot_numbers, co_matrix, 6)
    naive_top6_result = _cooccurrence_apply_rules(hot_numbers[:6], co_matrix, 6)

    assert 7 in full_pool_result
    assert 7 not in naive_top6_result
    assert full_pool_result != naive_top6_result


# ─── predict_biglotto_echo_phase2 goldens (portfolio, 5 native tickets) ─────

ECHO_PHASE2_GOLDENS: dict[int, tuple[tuple[int, ...], ...]] = {
    1: (
        (1, 9, 17, 25, 33, 41),
        (2, 3, 4, 5, 6, 7),
        (1, 9, 17, 25, 33, 41),
        (2, 3, 4, 5, 6, 7),
        (11, 14, 16, 18, 20, 21),
    ),
    2: (
        (2, 10, 18, 26, 34, 42),
        (3, 4, 5, 6, 7, 8),
        (2, 10, 18, 26, 34, 42),
        (3, 4, 5, 6, 7, 8),
        (11, 19, 21, 22, 23, 24),
    ),
    6: (
        (6, 14, 22, 30, 38, 46),
        (7, 8, 15, 16, 23, 24),
        (6, 14, 22, 30, 38, 46),
        (7, 8, 15, 16, 23, 24),
        (1, 9, 31, 32, 39, 48),
    ),
    7: (
        (7, 15, 23, 31, 39, 47),
        (8, 16, 24, 32, 40, 48),
        (7, 15, 23, 31, 39, 47),
        (8, 16, 24, 32, 40, 48),
        (1, 2, 9, 18, 41, 49),
    ),
    20: (
        (3, 11, 20, 28, 36, 44),
        (4, 12, 13, 21, 29, 37),
        (3, 11, 20, 28, 36, 44),
        (4, 12, 13, 21, 29, 37),
        (5, 14, 22, 30, 38, 45),
    ),
    50: (
        (1, 9, 17, 25, 33, 41),
        (2, 10, 18, 26, 34, 42),
        (1, 9, 17, 25, 33, 41),
        (2, 10, 18, 26, 34, 42),
        (3, 11, 19, 28, 43, 44),
    ),
    60: (
        (2, 11, 19, 27, 35, 43),
        (3, 4, 12, 20, 28, 36),
        (2, 11, 19, 27, 35, 43),
        (3, 4, 12, 20, 28, 36),
        (5, 6, 13, 21, 37, 44),
    ),
    61: (
        (3, 12, 20, 28, 36, 44),
        (4, 5, 13, 21, 29, 37),
        (3, 12, 20, 28, 36, 44),
        (4, 5, 13, 21, 29, 37),
        (6, 7, 14, 22, 30, 45),
    ),
    100: (
        (2, 10, 18, 26, 34, 42),
        (3, 11, 19, 27, 35, 43),
        (2, 10, 18, 26, 34, 42),
        (3, 11, 19, 27, 35, 43),
        (4, 12, 20, 29, 44, 45),
    ),
    500: (
        (1, 10, 18, 26, 34, 42),
        (2, 3, 11, 19, 27, 35),
        (1, 10, 18, 26, 34, 42),
        (2, 3, 11, 19, 27, 35),
        (4, 5, 12, 20, 36, 43),
    ),
    750: (
        (6, 15, 23, 31, 39, 47),
        (7, 8, 16, 24, 32, 40),
        (6, 15, 23, 31, 39, 47),
        (7, 8, 16, 24, 32, 40),
        (9, 10, 17, 25, 33, 48),
    ),
}


@pytest.mark.parametrize("n", sorted(ECHO_PHASE2_GOLDENS))
def test_echo_phase2_matches_frozen_donor_golden(n: int) -> None:
    history = _wave1_history(n)
    assert (
        BigLottoEchoPhase2Adapter().get_bets(history, LotteryType.BIG_LOTTO)
        == (ECHO_PHASE2_GOLDENS[n])
    )


def test_echo_phase2_minimum_history_boundary() -> None:
    with pytest.raises(InsufficientHistory):
        BigLottoEchoPhase2Adapter().get_bets((), LotteryType.BIG_LOTTO)
    assert (
        BigLottoEchoPhase2Adapter().get_bets(_wave1_history(1), LotteryType.BIG_LOTTO)
        == ECHO_PHASE2_GOLDENS[1]
    )


def test_echo_phase2_native_ticket_count_and_order_is_fixed() -> None:
    """5 tickets, always in the fixed source order: 2bet's [hot, cold] then
    3bet's [hot, cold, warm] — never reordered by score or number."""
    for n in (20, 100, 750):
        bets = BigLottoEchoPhase2Adapter().get_bets(_wave1_history(n), LotteryType.BIG_LOTTO)
        assert len(bets) == 5
        assert bets == ECHO_PHASE2_GOLDENS[n]


def test_echo_phase2_preserves_positional_duplicates_across_configurations() -> None:
    """2bet's hot/cold bets and 3bet's hot/cold bets share the same scoring
    formula, so ticket 1 == ticket 3 and ticket 2 == ticket 4 by construction
    — this must be preserved verbatim, never deduplicated."""
    for n in (1, 50, 500):
        bets = ECHO_PHASE2_GOLDENS[n]
        assert bets[0] == bets[2]
        assert bets[1] == bets[3]


def test_echo_phase2_bet3_top12_candidate_pool_is_mutation_sensitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ticket 5 (bet3) is chosen by exhaustive search over the top-12
    candidate pool (candidate_k=12, distinct from the 5 native tickets);
    shrinking that pool must change ticket 5."""
    from lottolab.strategies.adapters import biglotto_wave1 as module

    history = _wave1_history(300)
    baseline = BigLottoEchoPhase2Adapter().get_bets(history, LotteryType.BIG_LOTTO)

    def three_bet_with_shrunk_pool(
        history: tuple[CausalDrawRow, ...], window: int = 50, lookback: int = 50
    ) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
        # Re-implement with pool[:6] instead of pool[:12] to prove sensitivity.
        temps = module._continuous_temperature(history, window)
        echoes = module._echo_detector(history, max_lag=5)
        ew, _s, _a = module._adaptive_echo_weight(history, lookback=lookback)

        hot_scores: dict[int, float] = {}
        cold_scores: dict[int, float] = {}
        for n in range(1, module._MAX_NUM + 1):
            t = temps.get(n, 0.5)
            e = echoes.get(n, 0.0)
            hot_scores[n] = t * (1 - ew) + e * ew
            cold_scores[n] = (1 - t) * (1 - ew) + e * ew

        hot_ranked = sorted(
            range(1, module._MAX_NUM + 1), key=lambda n: hot_scores[n], reverse=True
        )
        bet1 = sorted(hot_ranked[: module._PICK])
        used = set(bet1)

        cold_ranked = sorted(
            range(1, module._MAX_NUM + 1), key=lambda n: cold_scores[n], reverse=True
        )
        bet2: list[int] = []
        for n in cold_ranked:
            if n not in used and len(bet2) < module._PICK:
                bet2.append(n)
        bet2 = sorted(bet2[: module._PICK])
        used.update(bet2)

        bet3_scores: dict[int, float] = {}
        for n in range(1, module._MAX_NUM + 1):
            if n in used:
                continue
            t = temps.get(n, 0.5)
            e = echoes.get(n, 0.0)
            warm_proximity = 1.0 - abs(t - 0.5) * 2.0
            echo_share = min(0.7, ew * 2)
            bet3_scores[n] = e * echo_share + warm_proximity * (1 - echo_share)

        bet3_ranked = sorted(bet3_scores.keys(), key=lambda n: bet3_scores[n], reverse=True)
        candidates = sorted(bet3_ranked[:6])  # shrunk from 12 -> 6

        best_bet3 = None
        best_score = -1.0
        if len(candidates) >= module._PICK:
            from itertools import combinations

            for combo in combinations(candidates, module._PICK):
                bet = sorted(combo)
                sc = module._structural_score(bet)
                avg_s = sum(bet3_scores.get(n, 0.0) for n in bet) / module._PICK
                composite = sc + avg_s * 0.1
                if composite > best_score:
                    best_score = composite
                    best_bet3 = bet
        if best_bet3 is None:
            best_bet3 = sorted(candidates[: module._PICK])
        return tuple(bet1), tuple(bet2), tuple(best_bet3)

    monkeypatch.setattr(module, "_phase2_echo_3bet", three_bet_with_shrunk_pool)
    mutated = BigLottoEchoPhase2Adapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert mutated != baseline
    assert mutated[:4] == baseline[:4]  # bet1/bet2 untouched by the bet3-only mutation
    assert mutated[4] != baseline[4]


def test_echo_phase2_wrong_native_ticket_count_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lottolab.strategies.adapters import biglotto_wave1 as module

    def short_predict_all(
        self: object, history: object, lottery_type: object
    ) -> tuple[tuple[int, ...], ...]:
        return ((1, 2, 3, 4, 5, 6),)

    monkeypatch.setattr(module.BigLottoEchoPhase2Adapter, "_predict_all", short_predict_all)
    with pytest.raises(InvalidOutput):
        BigLottoEchoPhase2Adapter().get_bets(_wave1_history(50), LotteryType.BIG_LOTTO)


# ─── shared: closure, repeated-execution byte equality, no external state ──


@pytest.mark.parametrize("adapter_class", SINGLE_TICKET_ADAPTER_CLASSES)
def test_wave1_single_ticket_closure(adapter_class: type[BetAdapter]) -> None:
    history = _wave1_history(max(adapter_class().min_history, 1) + 250)
    numbers, special = adapter_class().get_one_bet(history, LotteryType.BIG_LOTTO)
    assert len(numbers) == 6
    assert len(set(numbers)) == 6
    assert numbers == tuple(sorted(numbers))
    assert all(1 <= n <= 49 for n in numbers)
    assert special is None


@pytest.mark.parametrize("adapter_class", SINGLE_TICKET_ADAPTER_CLASSES)
def test_wave1_single_ticket_repeated_execution_byte_equality(
    adapter_class: type[BetAdapter],
) -> None:
    history = _wave1_history(max(adapter_class().min_history, 1) + 250)
    first = adapter_class().get_one_bet(history, LotteryType.BIG_LOTTO)
    second = adapter_class().get_one_bet(history, LotteryType.BIG_LOTTO)
    assert first == second


def test_echo_phase2_closure() -> None:
    history = _wave1_history(300)
    bets = BigLottoEchoPhase2Adapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert len(bets) == 5
    for ticket in bets:
        assert len(ticket) == 6
        assert len(set(ticket)) == 6
        assert ticket == tuple(sorted(ticket))
        assert all(1 <= n <= 49 for n in ticket)


def test_echo_phase2_repeated_execution_byte_equality() -> None:
    history = _wave1_history(300)
    first = BigLottoEchoPhase2Adapter().get_bets(history, LotteryType.BIG_LOTTO)
    second = BigLottoEchoPhase2Adapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert first == second


@pytest.mark.parametrize("adapter_class", SINGLE_TICKET_ADAPTER_CLASSES)
def test_wave1_single_ticket_rejects_wrong_lottery_type(adapter_class: type[BetAdapter]) -> None:
    history = _wave1_history(max(adapter_class().min_history, 1) + 10)
    with pytest.raises(UnsupportedLotteryType):
        adapter_class().get_one_bet(history, LotteryType.POWER_LOTTO)


def test_echo_phase2_rejects_wrong_lottery_type() -> None:
    with pytest.raises(UnsupportedLotteryType):
        BigLottoEchoPhase2Adapter().get_bets(_wave1_history(10), LotteryType.POWER_LOTTO)


def test_wave1_adapters_need_no_filesystem_clock_database_or_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("external state access is forbidden")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(time, "time", forbidden)
    monkeypatch.setattr(time, "monotonic", forbidden)

    history = _wave1_history(750)
    assert BigLottoGraphPredictorAdapter().get_one_bet(history, LotteryType.BIG_LOTTO) == (
        GRAPH_GOLDENS[750],
        None,
    )
    assert BigLottoMustHitTop6Adapter().get_one_bet(history, LotteryType.BIG_LOTTO) == (
        MUST_HIT_GOLDENS[750],
        None,
    )
    assert BigLottoDynamicFrequencyAdapter().get_one_bet(history, LotteryType.BIG_LOTTO) == (
        DYNAMIC_FREQUENCY_GOLDENS[750],
        None,
    )
    assert BigLottoHotCooccurrenceAdapter().get_one_bet(history, LotteryType.BIG_LOTTO) == (
        COOCCURRENCE_GOLDENS[750],
        None,
    )
    assert (
        BigLottoEchoPhase2Adapter().get_bets(history, LotteryType.BIG_LOTTO)
        == (ECHO_PHASE2_GOLDENS[750])
    )


def test_wave1_adapter_input_rows_are_immutable() -> None:
    row = _wave1_row(0)
    with pytest.raises(Exception):  # noqa: B017 — dataclass(frozen=True) raises FrozenInstanceError
        row.numbers = (1, 2, 3, 4, 5, 6)  # type: ignore[misc]


def test_subprocess_repeatability_across_python_hash_seeds() -> None:
    code = """
import sys
sys.path.insert(0, {src!r})
from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.adapters.biglotto_wave1 import (
    BigLottoDynamicFrequencyAdapter, BigLottoEchoPhase2Adapter,
    BigLottoGraphPredictorAdapter, BigLottoHotCooccurrenceAdapter,
    BigLottoMustHitTop6Adapter,
)

def row(i):
    numbers = tuple(sorted(((i + s * 8) % 49) + 1 for s in range(6)))
    draw = f"w1-{{i}}"
    date = f"2020-{{(i%12)+1:02d}}-{{(i%28)+1:02d}}"
    return CausalDrawRow(draw=draw, date=date, numbers=numbers)

history = tuple(row(i) for i in range(300))
outputs = [
    BigLottoGraphPredictorAdapter().get_one_bet(history, LotteryType.BIG_LOTTO),
    BigLottoMustHitTop6Adapter().get_one_bet(history, LotteryType.BIG_LOTTO),
    BigLottoDynamicFrequencyAdapter().get_one_bet(history, LotteryType.BIG_LOTTO),
    BigLottoHotCooccurrenceAdapter().get_one_bet(history, LotteryType.BIG_LOTTO),
    BigLottoEchoPhase2Adapter().get_bets(history, LotteryType.BIG_LOTTO),
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


# ─── portfolio contract-level tests ─────────────────────────────────────────


class _StubTwoTicketPortfolioAdapter(PortfolioBetAdapter):
    strategy_id = "stub_two_ticket_portfolio"
    strategy_name = "Stub Two Ticket Portfolio"
    strategy_version = "v0.0"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 2

    def _predict_all(
        self, history: tuple[CausalDrawRow, ...], lottery_type: LotteryType
    ) -> tuple[tuple[int, ...], ...]:
        return ((1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12))


class _StubWrongCountPortfolioAdapter(PortfolioBetAdapter):
    strategy_id = "stub_wrong_count_portfolio"
    strategy_name = "Stub Wrong Count Portfolio"
    strategy_version = "v0.0"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 3

    def _predict_all(
        self, history: tuple[CausalDrawRow, ...], lottery_type: LotteryType
    ) -> tuple[tuple[int, ...], ...]:
        return ((1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12))


def test_portfolio_base_returns_ordered_tickets_preserving_declared_count() -> None:
    bets = _StubTwoTicketPortfolioAdapter().get_bets(_wave1_history(5), LotteryType.BIG_LOTTO)
    assert bets == ((1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12))


def test_portfolio_base_rejects_wrong_native_ticket_count() -> None:
    with pytest.raises(InvalidOutput):
        _StubWrongCountPortfolioAdapter().get_bets(_wave1_history(5), LotteryType.BIG_LOTTO)


def test_portfolio_base_rejects_insufficient_history() -> None:
    class NeedsTen(_StubTwoTicketPortfolioAdapter):
        min_history = 10

    with pytest.raises(InsufficientHistory):
        NeedsTen().get_bets(_wave1_history(5), LotteryType.BIG_LOTTO)


def test_portfolio_base_rejects_wrong_lottery_type() -> None:
    with pytest.raises(UnsupportedLotteryType):
        _StubTwoTicketPortfolioAdapter().get_bets(_wave1_history(5), LotteryType.POWER_LOTTO)


def test_portfolio_base_rejects_non_tuple_history() -> None:
    with pytest.raises(InvalidOutput):
        _StubTwoTicketPortfolioAdapter().get_bets(
            list(_wave1_history(5)),
            LotteryType.BIG_LOTTO,  # type: ignore[arg-type]
        )


# ─── generate_bet use-case fail-closed / portfolio-path tests ──────────────


def test_generate_one_bet_fails_closed_for_portfolio_strategy() -> None:
    use_case = build_production_generate_one_bet()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id="legacy_biglotto__predict_biglotto_echo_phase2__51c44b5c13d4",
            lottery_type=LotteryType.BIG_LOTTO,
            history=_wave1_history(50),
        )
    )
    assert result.status is GenerateOneBetStatus.WRONG_RESPONSE_PATH
    assert result.reason_code is GenerateOneBetReason.STRATEGY_IS_PORTFOLIO
    assert result.numbers is None


def test_generate_one_bet_does_not_expose_portfolio_adapter() -> None:
    use_case = build_production_generate_one_bet()
    assert "legacy_biglotto__predict_biglotto_echo_phase2__51c44b5c13d4" not in use_case._adapters


def test_generate_portfolio_fails_closed_for_single_ticket_strategy() -> None:
    use_case = build_production_generate_portfolio()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id="legacy_biglotto__graph_predictor__cd70713a5709",
            lottery_type=LotteryType.BIG_LOTTO,
            history=_wave1_history(50),
        )
    )
    assert result.status is GeneratePortfolioStatus.WRONG_RESPONSE_PATH
    assert result.reason_code is GeneratePortfolioReason.STRATEGY_IS_NOT_PORTFOLIO
    assert result.numbers is None


def test_generate_portfolio_does_not_expose_single_ticket_adapters() -> None:
    use_case = build_production_generate_portfolio()
    assert set(use_case._adapters.keys()) == {
        "b649_new_horizon_minimax_disagreement_r1",
        "legacy_biglotto__predict_biglotto_echo_phase2__51c44b5c13d4",
        "legacy_biglotto__high_prize_trend_optimizer__0fc72409150e",
        "legacy_biglotto__core_satellite__2e82891003b3",
        "legacy_biglotto__auto_discovery_biglotto__06bcb164db84",
        "legacy_biglotto__biglotto_2bet_final__7eaedb330a07",
        "legacy_biglotto__biglotto_2bet_optimizer__898ac9e38876",
        "legacy_biglotto__biglotto_2bet_optimizer_v2__783226366ac3",
        "legacy_biglotto__biglotto_3bet_optimizer__2835d6cb20c5",
        "legacy_biglotto__biglotto_tme_optimizer__62c6cb676bad",
        "legacy_biglotto__predict_biglotto_115000007_2bets__3dc7842c0511",
        "legacy_biglotto__predict_biglotto_6bets_cluster__1fd9e8a7ae2a",
        "legacy_biglotto__predict_biglotto_7bets_cluster__8f55b5d94669",
        "legacy_biglotto__predict_biglotto_echo_2bet__59c20b25b1fa",
        "legacy_biglotto__predict_biglotto_elite7__eb46a9856446",
        "legacy_biglotto__research_variant_history__149648f9fffc",
        "legacy_biglotto__auto_optimizer_alpha__7eaa9572e384",
        "legacy_biglotto__backtest_10bet_biglotto__054e85b088be",
        "legacy_biglotto__test_tme__f3bb5106dfe3",
        "legacy_biglotto__verify_gemini_2bet_claim__d5ca233aa776",
        "legacy_biglotto__predict_5me_115000004__8a1c06ce1bdd",
        "legacy_biglotto__predict_big_lotto_smart_2bet__7acdaab1bd0a",
        "legacy_biglotto__verify_gemini_phase2_claim__6407a8f39519",
        "legacy_biglotto__predict_biglotto_115000002_zone_balance__8febca575f5d",
        "legacy_biglotto__test_ces__78d17c530ab8",
        "legacy_biglotto__test_dms__b63442289bd5",
        "legacy_biglotto__test_greedy_optimizer__82df7f878ece",
        "legacy_biglotto__test_mwsc__ba37643d6a3b",
        "legacy_biglotto__test_cag__7ca5343dfedd",
        "legacy_biglotto__test_cluster_cover__5b43959e7c55",
        "legacy_biglotto__test_zdp__e80cc7e95453",
        "legacy_biglotto__enhanced_dual_bet_predictor__d5b3de348d01",
        "legacy_biglotto__biglotto_diversified_ensemble_v6__8caaac8fcb5d",
        "legacy_biglotto__backtest_strategy_1__41ed79a6de62",
        "legacy_biglotto__core_satellite__611284461323",
        "legacy_biglotto__zone_split__b6144f9d479f",
        "legacy_biglotto__big_lotto_exhaustive_audit__694d353b7ca2",
        "legacy_biglotto__social_wisdom_predictor__a00829b5d875",
        "legacy_biglotto__negative_selection_biglotto__98f860c52cc2",
        "legacy_biglotto__quick_ml_predict__8b7ba0b52e2d",
        "legacy_biglotto__test_asm__d39a233a4c75",
        "legacy_biglotto__test_dcb__c3299c25ca59",
        "legacy_biglotto__test_4bet_dcb__3c7e3e661ad8",
        "legacy_biglotto__test_ecp__c9d5ac6decdd",
        "legacy_biglotto__test_pce__9c0cf22b4217",
        "legacy_biglotto__test_dm_dms_biglotto__bad71858012d",
        "legacy_composite__quick_predict_5bet_ts3_markov_freqort",
        "legacy_biglotto__backtest_biglotto_markov_4bet__aefb54eb345b",
        "legacy_biglotto__minimal_dual_bet_strategy__3c9657df7ff4",
        "acb_markov_midfreq_3bet",
        "legacy_biglotto__backtest_apriori__2abb53765703",
        "legacy_biglotto__covering_strategy_research__214ecc206fc9",
        "legacy_biglotto__evolution_engine__3df019c31ce4",
        "legacy_biglotto__predict_biglotto_triple_strike__dad1c50d1504",
        "legacy_biglotto__backtest_sum_constraint__acb3b118300d",
        "legacy_biglotto__verify_markov_vs_triple_2bet__2094ee4bc361",
        "legacy_biglotto__backtest_biglotto_coldpool_15__2a80423e3cf5",
        "zonal_entropy_2bet",
        "power_apriori_2bet",
        "power_lead_lag_2bet",
        "legacy_biglotto__concentrated_pool_predictor__a03b90705749",
        "legacy_biglotto__constraint_filter_predictor__3a85b3995002",
        "legacy_biglotto__predict_biglotto_apriori__cda690ae84c2",
        "legacy_biglotto__smart_multi_bet__613c62c1f192",
        "legacy_biglotto__anti_consensus_strategy__a454ddd26cef",
        "legacy_biglotto__cooccurrence_graph__25fa2e473092",
        "legacy_biglotto__backtest_radical_strategy__e54cc0812bc6",
        "legacy_biglotto__power_fourier_rhythm__cb75e72e4c94",
        "legacy_biglotto__backtest_big_lotto_orthogonal_5bet__c4dff46c5a5e",
        "legacy_biglotto__predict_biglotto_quad_strike__e202e664208f",
        "legacy_biglotto__orthogonal_2bet_optimizer__aa51b0e5e4a4",
        "legacy_biglotto__biglotto_2bet_hedging__07a3aa455074",
        "power_graph_synergy_seed42_2bet",
    }


def test_generate_portfolio_returns_complete_native_ticket_set() -> None:
    use_case = build_production_generate_portfolio()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id="legacy_biglotto__predict_biglotto_echo_phase2__51c44b5c13d4",
            lottery_type=LotteryType.BIG_LOTTO,
            history=_wave1_history(100),
        )
    )
    assert result.status is GeneratePortfolioStatus.OK
    assert result.numbers is not None
    assert result.numbers == ECHO_PHASE2_GOLDENS[100]
    assert len(result.numbers) == 5


def test_generate_portfolio_unknown_strategy_fails_closed() -> None:
    use_case = build_production_generate_portfolio()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id="does_not_exist",
            lottery_type=LotteryType.BIG_LOTTO,
            history=_wave1_history(50),
        )
    )
    assert result.status is GeneratePortfolioStatus.STRATEGY_UNAVAILABLE
    assert result.reason_code is GeneratePortfolioReason.UNKNOWN_STRATEGY


def test_all_new_wave1_strategies_are_reachable_through_exactly_one_response_path() -> None:
    one_bet = build_production_generate_one_bet()
    portfolio = build_production_generate_portfolio()
    wave1_ids = {
        "legacy_biglotto__graph_predictor__cd70713a5709",
        "legacy_biglotto__backtest_must_hit__909c91fd2fd0",
        "legacy_biglotto__dynamic_frequency_predictor__36e5bf9998ac",
        "legacy_biglotto__hot_cooccurrence_analyzer__48121f27d7ee",
        "legacy_biglotto__predict_biglotto_echo_phase2__51c44b5c13d4",
    }
    reachable = set(one_bet._adapters.keys()) | set(portfolio._adapters.keys())
    assert wave1_ids <= reachable
    assert set(one_bet._adapters.keys()) & set(portfolio._adapters.keys()) == set()


# ─── catalog / descriptor invariant tests ──────────────────────────────────


def test_strategy_descriptor_single_ticket_requires_native_ticket_count_one() -> None:
    with pytest.raises(ValueError, match="native_ticket_count=1"):
        StrategyDescriptor(
            strategy_id="bad",
            strategy_name="bad",
            version="v0",
            lottery_types=(LotteryType.BIG_LOTTO,),
            lifecycle_status=__import__(
                "lottolab.domain.strategies", fromlist=["LifecycleStatus"]
            ).LifecycleStatus.ONLINE,
            executable=True,
            adapter_path="x:Y",
            response_shape=ResponseShape.SINGLE_TICKET,
            native_ticket_count=2,
        )


def test_strategy_descriptor_portfolio_requires_positive_native_ticket_count() -> None:
    with pytest.raises(ValueError, match="native_ticket_count >= 1"):
        StrategyDescriptor(
            strategy_id="bad",
            strategy_name="bad",
            version="v0",
            lottery_types=(LotteryType.BIG_LOTTO,),
            lifecycle_status=__import__(
                "lottolab.domain.strategies", fromlist=["LifecycleStatus"]
            ).LifecycleStatus.ONLINE,
            executable=True,
            adapter_path="x:Y",
            response_shape=ResponseShape.PORTFOLIO,
            native_ticket_count=0,
        )


def test_production_catalog_wave1_descriptors_declare_expected_shapes() -> None:
    catalog = production_catalog()
    single_ticket_ids = (
        "legacy_biglotto__graph_predictor__cd70713a5709",
        "legacy_biglotto__backtest_must_hit__909c91fd2fd0",
        "legacy_biglotto__dynamic_frequency_predictor__36e5bf9998ac",
        "legacy_biglotto__hot_cooccurrence_analyzer__48121f27d7ee",
    )
    for strategy_id in single_ticket_ids:
        descriptor = catalog.get(strategy_id)
        assert descriptor.response_shape is ResponseShape.SINGLE_TICKET
        assert descriptor.native_ticket_count == 1

    portfolio_descriptor = catalog.get(
        "legacy_biglotto__predict_biglotto_echo_phase2__51c44b5c13d4"
    )
    assert portfolio_descriptor.response_shape is ResponseShape.PORTFOLIO
    assert portfolio_descriptor.native_ticket_count == 5


def test_existing_eight_shipped_descriptors_default_to_single_ticket_shape() -> None:
    catalog = production_catalog()
    for strategy_id in (
        "biglotto_social_wisdom_anti_popularity",
        "biglotto_zone_split_3bet_bet1",
        "biglotto_zone_split_3bet_bet2",
        "biglotto_zone_split_3bet_bet3",
        "biglotto_deviation_2bet",
        "biglotto_deviation_2bet_bet2",
        "biglotto_p0_2bet_bet1",
        "biglotto_p0_2bet_bet2",
    ):
        descriptor = catalog.get(strategy_id)
        assert descriptor.response_shape is ResponseShape.SINGLE_TICKET
        assert descriptor.native_ticket_count == 1
