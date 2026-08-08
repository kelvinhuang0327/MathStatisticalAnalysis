from __future__ import annotations

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.adapters.daily539_biglotto_portable import (
    DAILY539_BIGLOTTO_PORTABLE_SPECS,
    Daily539BigLottoPortableAdapter,
)
from lottolab.strategies.adapters.powerlotto_biglotto_core import (
    MAXIMUM,
    MINIMUM,
    PICK_COUNT,
)


def _history(length: int) -> tuple[CausalDrawRow, ...]:
    return tuple(
        CausalDrawRow(
            draw=str(90000000 + index),
            date=f"2020-01-{(index % 28) + 1:02d}",
            numbers=tuple(sorted(((index * 7 + offset * 3) % 39) + 1 for offset in range(5))),
        )
        for index in range(1, length + 1)
    )


def test_all_r2_portable_families_are_registered_once() -> None:
    assert len(DAILY539_BIGLOTTO_PORTABLE_SPECS) == 38
    assert len({spec.strategy_id for spec in DAILY539_BIGLOTTO_PORTABLE_SPECS}) == 38
    assert len({spec.source_strategy_id for spec in DAILY539_BIGLOTTO_PORTABLE_SPECS}) == 38


def test_all_r2_portable_families_emit_target_native_positions() -> None:
    history = _history(1_000)
    for spec in DAILY539_BIGLOTTO_PORTABLE_SPECS:
        adapter = Daily539BigLottoPortableAdapter(spec)
        first = adapter.get_bets(history, LotteryType.DAILY_539)
        second = adapter.get_bets(history, LotteryType.DAILY_539)
        assert first == second, spec.strategy_id
        assert len(first) == spec.native_ticket_count, spec.strategy_id
        for ticket in first:
            assert len(ticket) == 5, spec.strategy_id
            assert len(set(ticket)) == 5, spec.strategy_id
            assert ticket == tuple(sorted(ticket)), spec.strategy_id
            assert 1 <= min(ticket) <= max(ticket) <= 39, spec.strategy_id


def test_all_r2_portable_families_emit_at_their_minimum_history() -> None:
    for spec in DAILY539_BIGLOTTO_PORTABLE_SPECS:
        history = _history(spec.min_history)
        tickets = Daily539BigLottoPortableAdapter(spec).get_bets(history, LotteryType.DAILY_539)
        assert len(tickets) == spec.native_ticket_count, spec.strategy_id
        assert all(len(ticket) == 5 and len(set(ticket)) == 5 for ticket in tickets), (
            spec.strategy_id
        )


def test_target_context_restores_p638_defaults() -> None:
    assert (MINIMUM, MAXIMUM, PICK_COUNT) == (1, 38, 6)
