"""Controlled Fourier chunk-K contracts; no replay or performance evaluation."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import json
from dataclasses import replace

import pytest
from tests.unit.test_biglotto_orthogonal_5bet_adapter import DONOR_GOLDENS, _lcg_history

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters import biglotto_orthogonal_5bet as orthogonal
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    PortfolioBetAdapter,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_fourier_chunk_k import (
    BigLottoFourierChunkK2Adapter,
    BigLottoFourierChunkK3Adapter,
    BigLottoFourierChunkK5Adapter,
)
from lottolab.strategies.catalog import production_catalog

ARMS = (
    BigLottoFourierChunkK2Adapter,
    BigLottoFourierChunkK3Adapter,
    BigLottoFourierChunkK5Adapter,
)
WINDOW = 500


def _assert_valid(tickets: tuple[tuple[int, ...], ...], count: int) -> None:
    assert len(tickets) == count
    assert all(len(ticket) == len(set(ticket)) == 6 for ticket in tickets)
    assert all(tuple(sorted(ticket)) == ticket for ticket in tickets)
    assert all(type(number) is int and 1 <= number <= 49 for ticket in tickets for number in ticket)
    assert len({number for ticket in tickets for number in ticket}) == 6 * count


def test_research_identities_have_fixed_counts_and_are_not_production_registered() -> None:
    catalog_ids = {entry.strategy_id for entry in production_catalog()}
    assert tuple(arm.strategy_id for arm in ARMS) == (
        "research_biglotto__fourier_chunk_k2",
        "research_biglotto__fourier_chunk_k3",
        "research_biglotto__fourier_chunk_k5",
    )
    for arm, count in zip(ARMS, (2, 3, 5), strict=True):
        assert issubclass(arm, PortfolioBetAdapter)
        assert arm.native_ticket_count == count
        assert arm.native_ticket_count_bounds() == (count, count)
        assert arm.min_history == WINDOW
        assert arm.supported_lottery_types == (LotteryType.BIG_LOTTO,)
        assert arm.strategy_id not in catalog_ids


@pytest.mark.parametrize(("count", "seed"), tuple(DONOR_GOLDENS))
def test_golden_k2_parity_cross_k_prefix_validity_and_byte_determinism(
    count: int, seed: int
) -> None:
    history = _lcg_history(count, seed)
    old = orthogonal.BigLottoOrthogonal5BetAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    portfolios = tuple(arm().get_bets(history, LotteryType.BIG_LOTTO) for arm in ARMS)
    k2, k3, k5 = portfolios

    # The independent, already-frozen donor fixture anchors both implementations.
    assert k2 == old[:2] == DONOR_GOLDENS[(count, seed)][:2]
    assert k2 == k3[:2]
    assert k3 == k5[:3]
    for arm, tickets, size in zip(ARMS, portfolios, (2, 3, 5), strict=True):
        _assert_valid(tickets, size)
        serialized = json.dumps(tickets, separators=(",", ":")).encode("ascii")
        repeated = arm().get_bets(history, LotteryType.BIG_LOTTO)
        assert json.dumps(repeated, separators=(",", ":")).encode("ascii") == serialized


@pytest.mark.parametrize("single_appearance", (False, True))
def test_sparse_tied_scores_preserve_old_k2_and_cross_k_prefix(single_appearance: bool) -> None:
    history = tuple(
        CausalDrawRow(str(index + 1), "2026-01-01", (1, 2, 3, 4, 5, 6))
        for index in range(WINDOW)
    )
    if single_appearance:
        history = (replace(history[0], numbers=(7, 8, 9, 10, 11, 12)), *history[1:])
    old = orthogonal.BigLottoOrthogonal5BetAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    k2, k3, k5 = (arm().get_bets(history, LotteryType.BIG_LOTTO) for arm in ARMS)

    assert k2 == old[:2] == k3[:2] == k5[:2]
    assert k3 == k5[:3]
    for tickets, size in zip((k2, k3, k5), (2, 3, 5), strict=True):
        _assert_valid(tickets, size)


@pytest.mark.parametrize("zero_position", (0, 6, 12, 18, 24, 30, 49))
def test_every_ticket_is_a_consecutive_fourier_chunk(
    zero_position: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Controlled rank seam, not a historical/golden fixture. Deliberately
    # descending so sorting the entire portfolio or ranking again would fail.
    numbers = tuple(range(49, 0, -1))
    rank = (*numbers[:zero_position], 0, *numbers[zero_position:])
    calls: list[tuple[CausalDrawRow, ...]] = []

    def fixed_rank(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
        calls.append(history)
        return rank

    monkeypatch.setattr(orthogonal, "_fourier_rank", fixed_rank)
    history = _lcg_history(WINDOW, 17)
    expected = (
        (44, 45, 46, 47, 48, 49),
        (38, 39, 40, 41, 42, 43),
        (32, 33, 34, 35, 36, 37),
        (26, 27, 28, 29, 30, 31),
        (20, 21, 22, 23, 24, 25),
    )
    for arm, size in zip(ARMS, (2, 3, 5), strict=True):
        assert arm().get_bets(history, LotteryType.BIG_LOTTO) == expected[:size]
    assert calls == [history] * 3


@pytest.mark.parametrize("arm", ARMS)
def test_exact_500_causal_rows_at_exclusive_target_cutoff(
    arm: type[PortfolioBetAdapter],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = _lcg_history(700, 97)
    target_index = 600
    target = rows[target_index]
    causal_history = rows[:target_index]  # Target/future exclusion belongs to the caller.
    expected_window = rows[target_index - WINDOW : target_index]
    observed: list[tuple[CausalDrawRow, ...]] = []
    original_rank = orthogonal._fourier_rank

    def observe_rank(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
        observed.append(history)
        return original_rank(history)

    monkeypatch.setattr(orthogonal, "_fourier_rank", observe_rank)
    adapter = arm()
    first = adapter.get_bets(causal_history, LotteryType.BIG_LOTTO)
    # Alter every excluded row, including target and future results. Only the
    # same explicitly causal prefix is passed through the existing interface.
    changed = tuple(
        replace(row, numbers=(1, 2, 3, 4, 5, 6))
        if index < target_index - WINDOW or index >= target_index
        else row
        for index, row in enumerate(rows)
    )
    second = adapter.get_bets(changed[:target_index], LotteryType.BIG_LOTTO)
    assert first == second == adapter.get_bets(expected_window, LotteryType.BIG_LOTTO)
    assert observed == [expected_window] * 3
    assert all(len(window) == WINDOW for window in observed)
    assert all(row.draw != target.draw for window in observed for row in window)
    assert observed[0][0] == rows[100]
    assert observed[0][-1] == rows[599]


@pytest.mark.parametrize("arm", ARMS)
@pytest.mark.parametrize("count", (0, 1, 499))
def test_insufficient_history_rejects_before_fourier(
    arm: type[PortfolioBetAdapter], count: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unexpected_rank(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
        pytest.fail("Fourier must not run before the shared 500-draw warm-up")

    monkeypatch.setattr(orthogonal, "_fourier_rank", unexpected_rank)
    with pytest.raises(InsufficientHistory, match=f"needs 500 draws, got {count}"):
        arm().get_bets(_lcg_history(count, 17), LotteryType.BIG_LOTTO)


@pytest.mark.parametrize("arm", ARMS)
def test_existing_input_validation_and_number_canonicalization(
    arm: type[PortfolioBetAdapter],
) -> None:
    history = _lcg_history(WINDOW, 17)
    adapter = arm()
    with pytest.raises(InvalidOutput, match="expected a history tuple"):
        adapter.get_bets(list(history), LotteryType.BIG_LOTTO)
    duplicate = (*history[:-1], replace(history[-1], draw=history[0].draw))
    with pytest.raises(InvalidOutput, match="identities must be unique"):
        adapter.get_bets(duplicate, LotteryType.BIG_LOTTO)
    invalid = (*history[:-1], replace(history[-1], numbers=(0, 1, 2, 3, 4, 5)))
    with pytest.raises(InvalidOutput, match="out of range"):
        adapter.get_bets(invalid, LotteryType.BIG_LOTTO)
    with pytest.raises(UnsupportedLotteryType):
        adapter.get_bets(history, LotteryType.DAILY_539)

    reversed_numbers = tuple(replace(row, numbers=tuple(reversed(row.numbers))) for row in history)
    executions = adapter.get_bets_with_emission(reversed_numbers, LotteryType.BIG_LOTTO)
    actual = tuple(execution.legal_main_numbers for execution in executions)
    assert actual == adapter.get_bets(history, LotteryType.BIG_LOTTO)
    assert all(execution.special_number is None for execution in executions)
    assert all(
        execution.emitted_main_numbers == execution.legal_main_numbers for execution in executions
    )
    # Like the donor, input validation is limited to the consumed suffix.
    assert adapter.get_bets((object(), *history), LotteryType.BIG_LOTTO) == actual


@pytest.mark.parametrize("rank", (tuple(range(49)), (*range(49), 48), (*range(49), 50)))
def test_invalid_rank_fails_closed_for_every_arm(
    rank: tuple[int, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    def invalid_rank(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
        return rank

    monkeypatch.setattr(orthogonal, "_fourier_rank", invalid_rank)
    history = _lcg_history(WINDOW, 17)
    for arm in ARMS:
        with pytest.raises(InvalidOutput, match=r"Fourier rank must permute indices 0\.\.49"):
            arm().get_bets(history, LotteryType.BIG_LOTTO)
