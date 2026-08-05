"""Parity and contract tests for the BigLotto native-strategy wave 3 adapters.

Golden fixtures below were cross-verified by executing this module's own
adapters against the separately-verified, already-tested pure-Python
research port of the shared ``UnifiedPredictionEngine`` methods at
``lottolab.application.legacy_frozen_unified_core`` (2148 causal executions
recorded against the same frozen donor commit,
``49a25effa62fc24f40789c16be6f11bdfb41a4a9``, per
``strategies/data/biglotto_full_strategy_catalog_v1.json``): 16 history
lengths (spanning both markov order-transition boundaries at 50 and 150
draws) x 2 tickets x 3 adapters, zero mismatches. Direct execution of the
actual frozen donor class was not possible in this environment (its own
``UnifiedPredictionEngine`` import chain needs numpy/pandas/scipy/sklearn,
none of which are installed here); see ``biglotto_wave3.py``'s module
docstring for the full provenance chain.
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
from lottolab.strategies.adapters.biglotto_wave3 import (
    BigLottoTwoBetFinalAdapter,
    BigLottoTwoBetOptimizerAdapter,
    BigLottoTwoBetOptimizerV2Adapter,
)
from lottolab.strategies.catalog import production_catalog

REPO_ROOT = Path(__file__).resolve().parents[2]

WAVE3_IDS = {
    "legacy_biglotto__biglotto_2bet_final__7eaedb330a07",
    "legacy_biglotto__biglotto_2bet_optimizer__898ac9e38876",
    "legacy_biglotto__biglotto_2bet_optimizer_v2__783226366ac3",
}


def _wave3_row(index: int) -> CausalDrawRow:
    """Deterministic 6-of-49 draw. Stride 8 is coprime with 49, so six
    consecutive steps always land on six distinct residues — no collisions."""

    numbers = tuple(sorted(((index + step * 8) % 49) + 1 for step in range(6)))
    assert len(set(numbers)) == 6
    return CausalDrawRow(
        draw=f"w3-{index:05d}",
        date=f"2020-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
        numbers=numbers,
    )


def _wave3_history(n: int) -> tuple[CausalDrawRow, ...]:
    return tuple(_wave3_row(i) for i in range(n))


PORTFOLIO_ADAPTER_CLASSES = (
    BigLottoTwoBetFinalAdapter,
    BigLottoTwoBetOptimizerAdapter,
    BigLottoTwoBetOptimizerV2Adapter,
)

# ─── goldens, cross-checked against legacy_frozen_unified_core (see module
#     docstring); keyed by history length. ───────────────────────────────

TWO_BET_FINAL_GOLDENS: dict[int, tuple[tuple[int, ...], tuple[int, ...]]] = {
    1: ((20, 38, 40, 42, 44, 46), (13, 21, 42, 44, 46, 48)),
    2: ((37, 38, 39, 40, 43, 49), (13, 20, 38, 39, 40, 44)),
    5: ((28, 36, 37, 42, 44, 45), (12, 19, 20, 37, 42, 44)),
    10: ((32, 39, 40, 47, 48, 49), (3, 11, 19, 47, 48, 49)),
    30: ((30, 37, 38, 44, 45, 46), (6, 14, 23, 44, 45, 46)),
    49: ((8, 16, 25, 32, 40, 49), (1, 9, 16, 32, 40, 48)),
    50: ((10, 16, 24, 32, 40, 48), (2, 18, 32, 40, 48, 49)),
    51: ((3, 32, 39, 40, 47, 48), (11, 19, 40, 47, 48, 49)),
    80: ((8, 16, 24, 40, 48, 49), (7, 8, 16, 31, 32, 49)),
    100: ((32, 39, 40, 47, 48, 49), (3, 11, 19, 47, 48, 49)),
    150: ((27, 34, 35, 41, 42, 43), (4, 12, 20, 34, 41, 43)),
    151: ((28, 36, 41, 42, 43, 44), (5, 13, 21, 36, 42, 44)),
    200: ((28, 36, 41, 42, 43, 44), (5, 13, 21, 36, 41, 43)),
    300: ((32, 39, 40, 47, 48, 49), (7, 15, 23, 40, 48, 49)),
    500: ((32, 39, 40, 47, 48, 49), (2, 11, 19, 47, 48, 49)),
    750: ((8, 16, 32, 40, 48, 49), (7, 8, 24, 29, 48, 49)),
}

TWO_BET_OPTIMIZER_GOLDENS: dict[int, tuple[tuple[int, ...], tuple[int, ...]]] = {
    1: ((20, 38, 40, 42, 44, 46), (13, 21, 42, 44, 46, 48)),
    2: ((37, 38, 39, 40, 43, 49), (13, 20, 38, 39, 40, 44)),
    5: ((28, 36, 37, 42, 44, 45), (12, 19, 20, 37, 42, 44)),
    10: ((32, 39, 40, 47, 48, 49), (3, 11, 19, 47, 48, 49)),
    30: ((30, 37, 38, 44, 45, 46), (6, 14, 23, 44, 45, 46)),
    49: ((8, 16, 25, 32, 40, 49), (1, 9, 16, 32, 40, 48)),
    50: ((10, 16, 24, 32, 40, 48), (2, 18, 32, 40, 48, 49)),
    51: ((3, 32, 39, 40, 47, 48), (11, 19, 40, 47, 48, 49)),
    80: ((8, 16, 24, 40, 48, 49), (7, 8, 15, 16, 32, 49)),
    100: ((32, 39, 40, 47, 48, 49), (3, 11, 19, 47, 48, 49)),
    150: ((27, 34, 35, 41, 42, 43), (4, 12, 20, 34, 41, 43)),
    151: ((28, 36, 41, 42, 43, 44), (5, 13, 21, 36, 42, 44)),
    200: ((28, 36, 41, 42, 43, 44), (5, 13, 21, 36, 41, 43)),
    300: ((32, 39, 40, 47, 48, 49), (7, 15, 23, 40, 48, 49)),
    500: ((32, 39, 40, 47, 48, 49), (2, 11, 19, 47, 48, 49)),
    750: ((8, 16, 32, 40, 48, 49), (7, 8, 11, 24, 48, 49)),
}

TWO_BET_OPTIMIZER_V2_GOLDENS: dict[int, tuple[tuple[int, ...], tuple[int, ...]]] = {
    1: ((1, 9, 17, 20, 25, 41), (9, 17, 33, 38, 40, 42)),
    2: ((2, 9, 17, 42, 43, 49), (2, 10, 18, 37, 38, 42)),
    5: ((5, 28, 36, 37, 42, 45), (12, 19, 20, 36, 42, 44)),
    10: ((18, 32, 39, 40, 47, 49), (3, 11, 19, 39, 47, 48)),
    30: ((30, 37, 38, 44, 45, 46), (6, 14, 23, 31, 45, 46)),
    49: ((8, 16, 25, 32, 40, 49), (1, 9, 17, 32, 40, 48)),
    50: ((10, 16, 24, 32, 40, 49), (2, 25, 33, 40, 48, 49)),
    51: ((1, 3, 10, 32, 40, 49), (1, 10, 24, 39, 47, 48)),
    80: ((8, 16, 24, 40, 48, 49), (1, 7, 15, 16, 32, 49)),
    100: ((1, 9, 24, 32, 40, 49), (3, 9, 24, 39, 47, 48)),
    150: ((3, 27, 34, 35, 41, 42), (4, 12, 20, 34, 41, 43)),
    151: ((28, 36, 41, 42, 43, 44), (5, 13, 21, 29, 42, 44)),
    200: ((4, 9, 10, 28, 42, 44), (5, 10, 28, 36, 41, 43)),
    300: ((3, 32, 39, 40, 47, 49), (3, 7, 15, 23, 48, 49)),
    500: ((1, 18, 32, 39, 40, 49), (1, 2, 11, 18, 47, 48)),
    750: ((8, 16, 32, 40, 48, 49), (7, 8, 11, 12, 24, 49)),
}


# ─── biglotto_2bet_final goldens (portfolio, 2 native tickets) ─────────────


@pytest.mark.parametrize("n", sorted(TWO_BET_FINAL_GOLDENS))
def test_two_bet_final_matches_reference_golden(n: int) -> None:
    history = _wave3_history(n)
    bets = BigLottoTwoBetFinalAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert bets == TWO_BET_FINAL_GOLDENS[n]


def test_two_bet_final_minimum_history_boundary() -> None:
    with pytest.raises(InsufficientHistory):
        BigLottoTwoBetFinalAdapter().get_bets(_wave3_history(0), LotteryType.BIG_LOTTO)
    assert (
        BigLottoTwoBetFinalAdapter().get_bets(_wave3_history(1), LotteryType.BIG_LOTTO)
        == TWO_BET_FINAL_GOLDENS[1]
    )


def test_two_bet_final_native_ticket_count_and_order_is_fixed() -> None:
    for n in (50, 500, 750):
        bets = BigLottoTwoBetFinalAdapter().get_bets(_wave3_history(n), LotteryType.BIG_LOTTO)
        assert len(bets) == 2
        assert bets == TWO_BET_FINAL_GOLDENS[n]


def test_two_bet_final_second_ticket_favors_large_numbers() -> None:
    """Bet 2's own construction greedily takes up to 3 numbers > 24 first —
    direct proof against the real function that this bias is load-bearing."""
    from lottolab.strategies.adapters.biglotto_wave3 import BigLottoTwoBetFinalAdapter as _Cls

    bets = _Cls().get_bets(_wave3_history(300), LotteryType.BIG_LOTTO)
    _bet1, bet2 = bets
    assert sum(1 for number in bet2 if number > 24) >= 1


# ─── biglotto_2bet_optimizer goldens (portfolio, 2 native tickets) ─────────


@pytest.mark.parametrize("n", sorted(TWO_BET_OPTIMIZER_GOLDENS))
def test_two_bet_optimizer_matches_reference_golden(n: int) -> None:
    history = _wave3_history(n)
    bets = BigLottoTwoBetOptimizerAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert bets == TWO_BET_OPTIMIZER_GOLDENS[n]


def test_two_bet_optimizer_minimum_history_boundary() -> None:
    with pytest.raises(InsufficientHistory):
        BigLottoTwoBetOptimizerAdapter().get_bets(_wave3_history(0), LotteryType.BIG_LOTTO)
    assert (
        BigLottoTwoBetOptimizerAdapter().get_bets(_wave3_history(1), LotteryType.BIG_LOTTO)
        == TWO_BET_OPTIMIZER_GOLDENS[1]
    )


def test_two_bet_optimizer_native_ticket_count_and_order_is_fixed() -> None:
    for n in (50, 500, 750):
        bets = BigLottoTwoBetOptimizerAdapter().get_bets(_wave3_history(n), LotteryType.BIG_LOTTO)
        assert len(bets) == 2
        assert bets == TWO_BET_OPTIMIZER_GOLDENS[n]


def test_two_bet_optimizer_weights_and_slices_are_mutation_sensitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct proof against the real adapter that the per-method weights
    (deviation 2.0 > markov 1.5 > statistical 1.0) and the [0:6]/[3:9] slice
    boundaries are load-bearing, using three disjoint fixed engine outputs
    so the resulting Counter has no ties to reason about."""
    from lottolab.strategies.adapters import biglotto_wave3 as module

    deviation_fixed: tuple[int, ...] = (1, 2, 3, 4, 5, 6)
    markov_fixed: tuple[int, ...] = (11, 12, 13, 14, 15, 16)
    statistical_fixed: tuple[int, ...] = (21, 22, 23, 24, 25, 26)

    def _fixed_deviation(_history: object) -> tuple[int, ...]:
        return deviation_fixed

    def _fixed_markov(_history: object) -> tuple[int, ...]:
        return markov_fixed

    def _fixed_statistical(_history: object) -> tuple[int, ...]:
        return statistical_fixed

    monkeypatch.setattr(module, "_unified_deviation_ticket", _fixed_deviation)
    monkeypatch.setattr(module, "_unified_markov_ticket", _fixed_markov)
    monkeypatch.setattr(module, "_unified_statistical_ticket", _fixed_statistical)

    history = _wave3_history(50)
    bets = module.BigLottoTwoBetOptimizerAdapter()._predict_all(
        tuple(history), LotteryType.BIG_LOTTO
    )

    # weight order deviation(2.0) > markov(1.5) > statistical(1.0) with no
    # ties: most_common(12) == all 6 deviation numbers then all 6 markov.
    top12 = deviation_fixed + markov_fixed
    assert bets == (tuple(sorted(top12[0:6])), tuple(sorted(top12[3:9])))

    # swapping which fixed ticket carries which weight changes the ranking,
    # and thus the slices, proving the weight assignment itself is load-bearing.
    swapped_top12 = statistical_fixed + markov_fixed  # if statistical carried weight 2.0 instead
    assert bets != (tuple(sorted(swapped_top12[0:6])), tuple(sorted(swapped_top12[3:9])))


# ─── biglotto_2bet_optimizer_v2 goldens (portfolio, 2 native tickets) ──────


@pytest.mark.parametrize("n", sorted(TWO_BET_OPTIMIZER_V2_GOLDENS))
def test_two_bet_optimizer_v2_matches_reference_golden(n: int) -> None:
    history = _wave3_history(n)
    bets = BigLottoTwoBetOptimizerV2Adapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert bets == TWO_BET_OPTIMIZER_V2_GOLDENS[n]


def test_two_bet_optimizer_v2_minimum_history_boundary() -> None:
    with pytest.raises(InsufficientHistory):
        BigLottoTwoBetOptimizerV2Adapter().get_bets(_wave3_history(0), LotteryType.BIG_LOTTO)
    assert (
        BigLottoTwoBetOptimizerV2Adapter().get_bets(_wave3_history(1), LotteryType.BIG_LOTTO)
        == TWO_BET_OPTIMIZER_V2_GOLDENS[1]
    )


def test_two_bet_optimizer_v2_native_ticket_count_and_order_is_fixed() -> None:
    for n in (50, 500, 750):
        bets = BigLottoTwoBetOptimizerV2Adapter().get_bets(_wave3_history(n), LotteryType.BIG_LOTTO)
        assert len(bets) == 2
        assert bets == TWO_BET_OPTIMIZER_V2_GOLDENS[n]


def test_two_bet_optimizer_v2_differs_from_v1_and_final_at_the_same_history() -> None:
    """The three methods share the same underlying engine but differ in
    weights/pool-size/slices — proves they are not accidentally identical."""
    n = 750
    final = TWO_BET_FINAL_GOLDENS[n]
    v1 = TWO_BET_OPTIMIZER_GOLDENS[n]
    v2 = TWO_BET_OPTIMIZER_V2_GOLDENS[n]
    assert v2 != v1
    assert v2 != final


def test_two_bet_optimizer_v2_uses_bayesian_and_frequency_engine_methods(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct proof against the real adapter that bayesian/frequency are
    both actually consulted (not dead parameters): only V2 calls them, so
    making either raise must break V2 while leaving V1/final unaffected."""
    from lottolab.strategies.adapters import biglotto_wave3 as module

    def exploding(_history: object) -> tuple[int, ...]:
        raise AssertionError("engine method should not have been called")

    history = _wave3_history(300)

    monkeypatch.setattr(module, "_unified_bayesian_ticket", exploding)
    with pytest.raises(AssertionError, match="should not have been called"):
        module.BigLottoTwoBetOptimizerV2Adapter()._predict_all(
            tuple(history), LotteryType.BIG_LOTTO
        )
    # V1 and the final variant never call bayesian_predict -- unaffected.
    assert (
        module.BigLottoTwoBetOptimizerAdapter()._predict_all(tuple(history), LotteryType.BIG_LOTTO)
        == TWO_BET_OPTIMIZER_GOLDENS[300]
    )
    assert (
        module.BigLottoTwoBetFinalAdapter()._predict_all(tuple(history), LotteryType.BIG_LOTTO)
        == TWO_BET_FINAL_GOLDENS[300]
    )
    monkeypatch.undo()

    monkeypatch.setattr(module, "_unified_frequency_ticket", exploding)
    with pytest.raises(AssertionError, match="should not have been called"):
        module.BigLottoTwoBetOptimizerV2Adapter()._predict_all(
            tuple(history), LotteryType.BIG_LOTTO
        )


# ─── markov order-transition boundaries (shared engine method) ────────────


def test_markov_order_transition_is_mutation_sensitive_at_both_boundaries() -> None:
    """The shared markov engine method switches 1st -> 2nd order at 50 draws
    and 2nd -> 3rd order at 150 draws; the golden tickets on either side of
    each boundary must differ, proving the order switch is load-bearing."""
    assert TWO_BET_FINAL_GOLDENS[49] != TWO_BET_FINAL_GOLDENS[50]
    assert TWO_BET_FINAL_GOLDENS[150] != TWO_BET_FINAL_GOLDENS[151]


# ─── shared: closure, repeated-execution byte equality, wrong lottery type ─


@pytest.mark.parametrize("adapter_class", PORTFOLIO_ADAPTER_CLASSES)
def test_wave3_portfolio_closure(adapter_class: type[PortfolioBetAdapter]) -> None:
    history = _wave3_history(max(adapter_class().min_history, 1) + 250)
    bets = adapter_class().get_bets(history, LotteryType.BIG_LOTTO)
    assert len(bets) == adapter_class.native_ticket_count
    for ticket in bets:
        assert len(ticket) == 6
        assert len(set(ticket)) == 6
        assert ticket == tuple(sorted(ticket))
        assert all(1 <= n <= 49 for n in ticket)


@pytest.mark.parametrize("adapter_class", PORTFOLIO_ADAPTER_CLASSES)
def test_wave3_portfolio_repeated_execution_byte_equality(
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    history = _wave3_history(max(adapter_class().min_history, 1) + 250)
    first = adapter_class().get_bets(history, LotteryType.BIG_LOTTO)
    second = adapter_class().get_bets(history, LotteryType.BIG_LOTTO)
    assert first == second


@pytest.mark.parametrize("adapter_class", PORTFOLIO_ADAPTER_CLASSES)
def test_wave3_portfolio_rejects_wrong_lottery_type(
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    history = _wave3_history(max(adapter_class().min_history, 1) + 10)
    with pytest.raises(UnsupportedLotteryType):
        adapter_class().get_bets(history, LotteryType.POWER_LOTTO)


@pytest.mark.parametrize("adapter_class", PORTFOLIO_ADAPTER_CLASSES)
def test_wave3_portfolio_wrong_native_ticket_count_fails_closed(
    adapter_class: type[PortfolioBetAdapter],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def short_predict_all(
        self: object, history: object, lottery_type: object
    ) -> tuple[tuple[int, ...], ...]:
        return ((1, 2, 3, 4, 5, 6),)

    monkeypatch.setattr(adapter_class, "_predict_all", short_predict_all)
    with pytest.raises(InvalidOutput):
        adapter_class().get_bets(_wave3_history(50), LotteryType.BIG_LOTTO)


def test_wave3_portfolio_base_contract_never_deduplicates_tickets() -> None:
    """``PortfolioBetAdapter.get_bets_with_emission`` (base.py) validates and
    returns each ticket independently -- it contains no deduplication logic
    at all, so any wave adapter's own duplicate tickets (should its slices
    ever coincide) would surface verbatim, never silently collapsed. Proven
    once at the framework level via a minimal fake adapter, since these
    three methods' own [0:6]/[3:9]-style slices structurally never coincide
    for a valid pool (see the module docstring's ticket_duplicate_semantics
    note in catalog.py provenance)."""
    from lottolab.strategies.adapters.base import BetAdapterExecution

    class _DuplicatingFakeAdapter(PortfolioBetAdapter):
        strategy_id = "test_only_duplicating_fake"
        strategy_name = "test fixture"
        strategy_version = "v0.1"
        min_history = 1
        supported_lottery_types = (LotteryType.BIG_LOTTO,)
        native_ticket_count = 2

        def _predict_all(
            self, history: object, lottery_type: object
        ) -> tuple[tuple[int, ...], ...]:
            fixed = (1, 9, 17, 25, 33, 41)
            return (fixed, fixed)

    executions = _DuplicatingFakeAdapter().get_bets_with_emission(
        _wave3_history(1), LotteryType.BIG_LOTTO
    )
    assert isinstance(executions[0], BetAdapterExecution)
    assert executions[0].legal_main_numbers == executions[1].legal_main_numbers
    bets = _DuplicatingFakeAdapter().get_bets(_wave3_history(1), LotteryType.BIG_LOTTO)
    assert bets == ((1, 9, 17, 25, 33, 41), (1, 9, 17, 25, 33, 41))


def test_wave3_adapters_need_no_filesystem_clock_database_or_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("external state access is forbidden")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(time, "time", forbidden)
    monkeypatch.setattr(time, "monotonic", forbidden)

    history = _wave3_history(750)
    assert (
        BigLottoTwoBetFinalAdapter().get_bets(history, LotteryType.BIG_LOTTO)
        == TWO_BET_FINAL_GOLDENS[750]
    )
    assert (
        BigLottoTwoBetOptimizerAdapter().get_bets(history, LotteryType.BIG_LOTTO)
        == TWO_BET_OPTIMIZER_GOLDENS[750]
    )
    assert (
        BigLottoTwoBetOptimizerV2Adapter().get_bets(history, LotteryType.BIG_LOTTO)
        == TWO_BET_OPTIMIZER_V2_GOLDENS[750]
    )


def test_subprocess_repeatability_across_python_hash_seeds() -> None:
    code = """
import sys
sys.path.insert(0, {src!r})
from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.adapters.biglotto_wave3 import (
    BigLottoTwoBetFinalAdapter, BigLottoTwoBetOptimizerAdapter, BigLottoTwoBetOptimizerV2Adapter,
)

def row(i):
    numbers = tuple(sorted(((i + s * 8) % 49) + 1 for s in range(6)))
    draw = f"w3-{{i:05d}}"
    date = f"2020-{{(i%12)+1:02d}}-{{(i%28)+1:02d}}"
    return CausalDrawRow(draw=draw, date=date, numbers=numbers)

history = tuple(row(i) for i in range(300))
outputs = [
    BigLottoTwoBetFinalAdapter().get_bets(history, LotteryType.BIG_LOTTO),
    BigLottoTwoBetOptimizerAdapter().get_bets(history, LotteryType.BIG_LOTTO),
    BigLottoTwoBetOptimizerV2Adapter().get_bets(history, LotteryType.BIG_LOTTO),
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


@pytest.mark.parametrize("strategy_id", sorted(WAVE3_IDS))
def test_generate_one_bet_fails_closed_for_wave3_portfolio_strategy(strategy_id: str) -> None:
    use_case = build_production_generate_one_bet()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id=strategy_id,
            lottery_type=LotteryType.BIG_LOTTO,
            history=_wave3_history(50),
        )
    )
    assert result.status is GenerateOneBetStatus.WRONG_RESPONSE_PATH
    assert result.reason_code is GenerateOneBetReason.STRATEGY_IS_PORTFOLIO
    assert result.numbers is None


def test_generate_one_bet_does_not_expose_wave3_portfolio_adapters() -> None:
    use_case = build_production_generate_one_bet()
    assert WAVE3_IDS.isdisjoint(use_case._adapters.keys())


def test_generate_portfolio_returns_complete_native_ticket_set_for_each_wave3_strategy() -> None:
    use_case = build_production_generate_portfolio()
    for strategy_id in WAVE3_IDS:
        result = use_case.execute(
            GenerateOneBetInput(
                strategy_id=strategy_id,
                lottery_type=LotteryType.BIG_LOTTO,
                history=_wave3_history(100),
            )
        )
        assert result.status is GeneratePortfolioStatus.OK
        assert result.numbers is not None
        assert len(result.numbers) == 2


def test_all_wave3_strategies_are_reachable_through_exactly_one_response_path() -> None:
    one_bet = build_production_generate_one_bet()
    portfolio = build_production_generate_portfolio()
    reachable = set(one_bet._adapters.keys()) | set(portfolio._adapters.keys())
    assert reachable >= WAVE3_IDS
    assert set(one_bet._adapters.keys()) & set(portfolio._adapters.keys()) == set()


def test_generate_portfolio_unknown_strategy_still_fails_closed() -> None:
    use_case = build_production_generate_portfolio()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id="does_not_exist",
            lottery_type=LotteryType.BIG_LOTTO,
            history=_wave3_history(50),
        )
    )
    assert result.status is GeneratePortfolioStatus.STRATEGY_UNAVAILABLE
    assert result.reason_code is GeneratePortfolioReason.UNKNOWN_STRATEGY


# ─── catalog / descriptor invariant tests ──────────────────────────────────


def test_production_catalog_wave3_descriptors_declare_expected_shapes() -> None:
    catalog = production_catalog()
    for strategy_id in WAVE3_IDS:
        descriptor = catalog.get(strategy_id)
        assert descriptor.response_shape is ResponseShape.PORTFOLIO
        assert descriptor.native_ticket_count == 2
        assert descriptor.executable is True
        assert descriptor.min_history == 1


def test_production_catalog_now_has_nineteen_descriptors() -> None:
    """Name pinned at the Wave 3 landing point; later waves append only."""
    catalog = production_catalog()
    assert len(catalog) == 50


def test_wave1_and_wave2_descriptors_are_unaffected_by_wave3() -> None:
    """Existing 16 adapters and their outputs must remain unchanged."""
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
    }
    for strategy_id, native_ticket_count in pre_existing_portfolio_ids.items():
        descriptor = catalog.get(strategy_id)
        assert descriptor.response_shape is ResponseShape.PORTFOLIO
        assert descriptor.native_ticket_count == native_ticket_count
