"""Controlled Fourier(3)+Hot(2) mixed hybrid K5 contracts.

No replay or historical performance evaluation. All Fourier-rank fixtures
that need an exact, hand-derivable downstream outcome use test-local
``monkeypatch`` injection of ``orthogonal._fourier_rank`` (the same technique
the donor's own test suite uses), never a change to production semantics.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import pytest
from tests.unit.test_biglotto_orthogonal_5bet_adapter import DONOR_GOLDENS, _lcg_history

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters import biglotto_fourier_mixed_hybrid_k5 as hybrid_module
from lottolab.strategies.adapters import biglotto_orthogonal_5bet as orthogonal
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    PortfolioBetAdapter,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_fourier_chunk_k import BigLottoFourierChunkK3Adapter
from lottolab.strategies.adapters.biglotto_fourier_mixed_hybrid_k5 import (
    BigLottoFourierMixedHybridK5Adapter,
)
from lottolab.strategies.adapters.biglotto_orthogonal_5bet import BigLottoOrthogonal5BetAdapter
from lottolab.strategies.catalog import production_catalog

WINDOW = 500
FREQUENCY_WINDOW = 100


def _uniform_history(count: int, numbers: tuple[int, ...]) -> tuple[CausalDrawRow, ...]:
    """`count` valid, uniquely-identified rows that all draw the same numbers."""

    return tuple(CausalDrawRow(str(index + 1), "2026-01-01", numbers) for index in range(count))


def _rank_with_prefix_chunks(*chunks: tuple[int, ...]) -> tuple[int, ...]:
    """One valid 0..49 rank permutation whose leading chunks are `chunks`.

    Index 0 holds the sentinel; each 6-number chunk then occupies one
    consecutive block, matching how a real ``_fourier_rank`` output is
    consumed by both the donor and the Fourier chunk-K family. The tail
    filler order never matters to any assertion in this file.
    """

    used = [number for chunk in chunks for number in chunk]
    remainder = [number for number in range(1, 50) if number not in used]
    return (0, *used, *remainder)


def _fixed_rank(rank: tuple[int, ...]) -> Callable[[tuple[CausalDrawRow, ...]], tuple[int, ...]]:
    """A ``_fourier_rank``-compatible stand-in that ignores history entirely."""

    def _rank(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
        del history
        return rank

    return _rank


def _assert_valid_portfolio(tickets: tuple[tuple[int, ...], ...]) -> None:
    assert len(tickets) == 5
    assert all(len(ticket) == len(set(ticket)) == 6 for ticket in tickets)
    assert all(tuple(sorted(ticket)) == ticket for ticket in tickets)
    assert all(
        type(number) is int and 1 <= number <= 49 for ticket in tickets for number in ticket
    )
    assert len({number for ticket in tickets for number in ticket}) == 30


# ---------------------------------------------------------------------------
# 1. Fourier prefix parity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("count", "seed"), tuple(DONOR_GOLDENS))
def test_fourier_prefix_parity_and_determinism(count: int, seed: int) -> None:
    history = _lcg_history(count, seed)
    fourier = BigLottoFourierChunkK3Adapter().get_bets(history, LotteryType.BIG_LOTTO)

    hybrid = BigLottoFourierMixedHybridK5Adapter().get_bets(history, LotteryType.BIG_LOTTO)
    repeated = BigLottoFourierMixedHybridK5Adapter().get_bets(history, LotteryType.BIG_LOTTO)

    assert hybrid[:3] == fourier
    assert repeated == hybrid
    _assert_valid_portfolio(hybrid)


# ---------------------------------------------------------------------------
# 2. Old-strategy parity anchor
# ---------------------------------------------------------------------------


def test_old_strategy_parity_anchor_when_upstream_pool_is_identical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rank = _rank_with_prefix_chunks(
        (1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12), (13, 14, 15, 16, 17, 18)
    )
    monkeypatch.setattr(orthogonal, "_fourier_rank", _fixed_rank(rank))
    # Every row (including the lag-2 echo source) draws only 1..6, so the
    # donor's echo is empty and its cold-fill, like the hybrid's hot-rank,
    # sees uniform (zero) frequency for every number from 13 upward.
    history = _uniform_history(WINDOW, (1, 2, 3, 4, 5, 6))

    old = BigLottoOrthogonal5BetAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    hybrid = BigLottoFourierMixedHybridK5Adapter().get_bets(history, LotteryType.BIG_LOTTO)

    assert (
        old[:3]
        == hybrid[:3]
        == ((1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12), (13, 14, 15, 16, 17, 18))
    )
    assert hybrid[3:] == old[3:] == ((19, 20, 21, 22, 23, 24), (25, 26, 27, 28, 29, 30))
    _assert_valid_portfolio(hybrid)
    _assert_valid_portfolio(old)


# ---------------------------------------------------------------------------
# 3. Conflict fixture
# ---------------------------------------------------------------------------


def test_new_ticket3_conflicts_with_old_ticket5_and_hybrid_recomputes_disjoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rank = _rank_with_prefix_chunks(
        (1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12), (25, 26, 27, 28, 29, 30)
    )
    monkeypatch.setattr(orthogonal, "_fourier_rank", _fixed_rank(rank))
    # Every row draws 13..18, so the donor's lag-2 echo fills its ticket 3
    # outright, and hot frequency favors 13..18 over everything else.
    history = _uniform_history(WINDOW, (13, 14, 15, 16, 17, 18))

    old = BigLottoOrthogonal5BetAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    hybrid = BigLottoFourierMixedHybridK5Adapter().get_bets(history, LotteryType.BIG_LOTTO)

    assert old == (
        (1, 2, 3, 4, 5, 6),
        (7, 8, 9, 10, 11, 12),
        (13, 14, 15, 16, 17, 18),
        (19, 20, 21, 22, 23, 24),
        (25, 26, 27, 28, 29, 30),
    )
    # The hybrid's new ticket 3 is exactly the donor's historical ticket 5.
    assert hybrid[2] == (25, 26, 27, 28, 29, 30) == old[4]
    assert hybrid == (
        (1, 2, 3, 4, 5, 6),
        (7, 8, 9, 10, 11, 12),
        (25, 26, 27, 28, 29, 30),
        (13, 14, 15, 16, 17, 18),
        (19, 20, 21, 22, 23, 24),
    )
    _assert_valid_portfolio(hybrid)


# ---------------------------------------------------------------------------
# 4. Released-old-ticket3 fixture (CTO-defined)
# ---------------------------------------------------------------------------


def test_released_old_ticket3_numbers_reenter_hot_ranking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rank = _rank_with_prefix_chunks(
        (1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12), (31, 32, 33, 34, 35, 36)
    )
    monkeypatch.setattr(orthogonal, "_fourier_rank", _fixed_rank(rank))

    # Frozen fixture design: of the trailing 100 rows, 98 draw 13..18 (97 of
    # them plus the penultimate row), one draws 25..30, and the final row
    # draws 19..24.
    trailing = (
        *((13, 14, 15, 16, 17, 18),) * 97,
        (25, 26, 27, 28, 29, 30),
        (13, 14, 15, 16, 17, 18),
        (19, 20, 21, 22, 23, 24),
    )
    assert len(trailing) == FREQUENCY_WINDOW
    prefix = _lcg_history(WINDOW - FREQUENCY_WINDOW, 71)
    history = prefix + tuple(
        CausalDrawRow(str(len(prefix) + index + 1), "2026-01-01", numbers)
        for index, numbers in enumerate(trailing)
    )
    assert history[-2].numbers == (13, 14, 15, 16, 17, 18)
    assert history[-1].numbers == (19, 20, 21, 22, 23, 24)

    old = BigLottoOrthogonal5BetAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    hybrid = BigLottoFourierMixedHybridK5Adapter().get_bets(history, LotteryType.BIG_LOTTO)

    assert hybrid[:3] == (
        (1, 2, 3, 4, 5, 6),
        (7, 8, 9, 10, 11, 12),
        (31, 32, 33, 34, 35, 36),
    )
    # The donor's own (fixed) downstream identity under this fixture.
    assert old[3] == (19, 20, 21, 22, 23, 24)
    assert old[4] == (25, 26, 27, 28, 29, 30)
    # Releasing 13..18 from ticket 3 lets them re-enter the hot ranking:
    # the hybrid must NOT preserve the donor's fixed T4/T5 identity above.
    assert hybrid[3:] == ((13, 14, 15, 16, 17, 18), (19, 20, 21, 22, 23, 24))
    assert hybrid[3:] != old[3:]
    _assert_valid_portfolio(hybrid)


# ---------------------------------------------------------------------------
# 5. Ranking edge cases
# ---------------------------------------------------------------------------


def test_hot_tail_breaks_frequency_ties_by_ascending_number() -> None:
    history = _uniform_history(FREQUENCY_WINDOW, (19, 21, 23, 37, 39, 41))
    used = frozenset(range(1, 19))

    ticket_four, ticket_five = hybrid_module._hot_tail_tickets(history, used)

    assert ticket_four == (19, 21, 23, 37, 39, 41)
    assert ticket_five == (20, 22, 24, 25, 26, 27)


def test_hot_tail_handles_all_zero_frequency_remaining_numbers() -> None:
    history = _uniform_history(FREQUENCY_WINDOW, (1, 2, 3, 4, 5, 6))
    used = frozenset(range(1, 19))

    ticket_four, ticket_five = hybrid_module._hot_tail_tickets(history, used)

    assert ticket_four == (19, 20, 21, 22, 23, 24)
    assert ticket_five == (25, 26, 27, 28, 29, 30)


def test_hot_tail_slices_are_consecutive_and_mutually_disjoint() -> None:
    history = _uniform_history(FREQUENCY_WINDOW, (20, 22, 24, 26, 28, 30))
    used = frozenset(range(1, 19))

    ticket_four, ticket_five = hybrid_module._hot_tail_tickets(history, used)

    assert ticket_four == (20, 22, 24, 26, 28, 30)
    assert ticket_five == (19, 21, 23, 25, 27, 29)
    assert set(ticket_four).isdisjoint(ticket_five)


@pytest.mark.parametrize(
    "rank",
    (tuple(range(49)), (*range(49), 48), (*range(49), 50)),
)
def test_invalid_fourier_rank_fails_closed_consistent_with_donor(
    rank: tuple[int, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(orthogonal, "_fourier_rank", _fixed_rank(rank))
    history = _lcg_history(WINDOW, 17)

    with pytest.raises(InvalidOutput, match=r"Fourier rank must permute indices 0\.\.49"):
        BigLottoFourierMixedHybridK5Adapter().get_bets(history, LotteryType.BIG_LOTTO)


def test_explicit_cross_ticket_overlap_rejection_is_load_bearing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rank = _rank_with_prefix_chunks(
        (1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12), (13, 14, 15, 16, 17, 18)
    )
    monkeypatch.setattr(orthogonal, "_fourier_rank", _fixed_rank(rank))

    def overlapping_hot_tail(
        history: tuple[CausalDrawRow, ...], used: frozenset[int]
    ) -> tuple[tuple[int, ...], tuple[int, ...]]:
        del history, used
        return (19, 20, 21, 22, 23, 24), (24, 25, 26, 27, 28, 29)

    monkeypatch.setattr(hybrid_module, "_hot_tail_tickets", overlapping_hot_tail)
    history = _uniform_history(WINDOW, (1, 2, 3, 4, 5, 6))

    with pytest.raises(InvalidOutput, match="cross-ticket overlap at ticket 5"):
        BigLottoFourierMixedHybridK5Adapter().get_bets(history, LotteryType.BIG_LOTTO)


# ---------------------------------------------------------------------------
# 6. History / causality contract
# ---------------------------------------------------------------------------


def test_insufficient_history_rejects_before_fourier(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_rank(history: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
        pytest.fail("Fourier must not run before the shared 500-draw warm-up")

    monkeypatch.setattr(orthogonal, "_fourier_rank", unexpected_rank)

    with pytest.raises(InsufficientHistory, match="needs 500 draws, got 499"):
        BigLottoFourierMixedHybridK5Adapter().get_bets(_lcg_history(499, 17), LotteryType.BIG_LOTTO)


def test_exactly_500_rows_is_accepted() -> None:
    hybrid = BigLottoFourierMixedHybridK5Adapter().get_bets(
        _lcg_history(WINDOW, 17), LotteryType.BIG_LOTTO
    )
    _assert_valid_portfolio(hybrid)


def test_only_final_500_rows_affect_the_adapter() -> None:
    suffix = _lcg_history(WINDOW, 97, draw_offset=1000)
    first_prefix = _lcg_history(75, 307)
    second_prefix = _lcg_history(75, 311)
    adapter = BigLottoFourierMixedHybridK5Adapter()

    first = adapter.get_bets(first_prefix + suffix, LotteryType.BIG_LOTTO)
    second = adapter.get_bets(second_prefix + suffix, LotteryType.BIG_LOTTO)

    assert first == second == adapter.get_bets(suffix, LotteryType.BIG_LOTTO)


def test_only_final_100_of_500_affect_hot_tail_once_fourier_rank_is_fixed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rank = _rank_with_prefix_chunks(
        (1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12), (13, 14, 15, 16, 17, 18)
    )
    monkeypatch.setattr(orthogonal, "_fourier_rank", _fixed_rank(rank))

    trailing = _lcg_history(FREQUENCY_WINDOW, 41, draw_offset=400)
    first_prefix = _lcg_history(400, 307)
    second_prefix = _lcg_history(400, 311)
    adapter = BigLottoFourierMixedHybridK5Adapter()

    first = adapter.get_bets(first_prefix + trailing, LotteryType.BIG_LOTTO)
    second = adapter.get_bets(second_prefix + trailing, LotteryType.BIG_LOTTO)

    assert first[3:] == second[3:]
    assert first == second


def test_exclusive_prefix_excludes_target_and_future_rows() -> None:
    rows = _lcg_history(700, 97)
    target_index = 600
    target = rows[target_index]
    causal_history = rows[:target_index]  # Target/future exclusion belongs to the caller.
    expected_window = rows[target_index - WINDOW : target_index]

    adapter = BigLottoFourierMixedHybridK5Adapter()
    first = adapter.get_bets(causal_history, LotteryType.BIG_LOTTO)
    # Alter every excluded row, including target and future results.
    changed = tuple(
        replace(row, numbers=(1, 2, 3, 4, 5, 6))
        if index < target_index - WINDOW or index >= target_index
        else row
        for index, row in enumerate(rows)
    )
    second = adapter.get_bets(changed[:target_index], LotteryType.BIG_LOTTO)

    assert first == second == adapter.get_bets(expected_window, LotteryType.BIG_LOTTO)
    assert all(row.draw != target.draw for row in expected_window)


# ---------------------------------------------------------------------------
# 7. Identity / publication boundary
# ---------------------------------------------------------------------------


def test_research_identity_is_fixed_and_not_production_registered() -> None:
    catalog_ids = {entry.strategy_id for entry in production_catalog()}

    assert BigLottoFourierMixedHybridK5Adapter.strategy_id == "research_biglotto__fourier3_hot2_k5"
    assert BigLottoFourierMixedHybridK5Adapter.strategy_version == "v0.1"
    assert BigLottoFourierMixedHybridK5Adapter.native_ticket_count == 5
    assert BigLottoFourierMixedHybridK5Adapter.native_ticket_count_bounds() == (5, 5)
    assert BigLottoFourierMixedHybridK5Adapter.supported_lottery_types == (LotteryType.BIG_LOTTO,)
    assert issubclass(BigLottoFourierMixedHybridK5Adapter, PortfolioBetAdapter)
    assert BigLottoFourierMixedHybridK5Adapter.strategy_id not in catalog_ids

    with pytest.raises(UnsupportedLotteryType):
        BigLottoFourierMixedHybridK5Adapter().get_bets(
            _lcg_history(WINDOW, 17), LotteryType.DAILY_539
        )
