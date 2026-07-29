"""Exact-mapped replay-backed native ticket reproduction tests."""

from __future__ import annotations

from typing import cast

import pytest

from lottolab.application.replay_backed_native_reproduction import (
    CausalMainDraw,
    ReplayBackedNativeReproductionError,
    reproduce_native_tickets,
)


def _history() -> tuple[CausalMainDraw, ...]:
    return tuple(
        CausalMainDraw(
            str(index),
            cast(
                tuple[int, int, int, int, int, int],
                tuple(
                    sorted(
                        ((index + offset * 7) % 49) + 1
                        for offset in range(6)
                    )
                ),
            ),
        )
        for index in range(1, 121)
    )


def test_triple_strike_preserves_fourier_first_then_reproduces_cold_and_tail() -> None:
    result = reproduce_native_tickets(
        registry_strategy_id="biglotto_triple_strike",
        replay_tickets=((1, 7, 15, 23, 28, 39),),
        causal_history=_history(),
    )

    assert result == (
        (1, 7, 15, 23, 28, 39),
        (12, 13, 14, 16, 17, 18),
        (2, 30, 36, 37, 43, 44),
    )
    assert not (set(result[0]) & set(result[1]))
    assert not (set(result[0]) & set(result[2]))
    assert not (set(result[1]) & set(result[2]))


def test_ts3_markov_preserves_native_order_and_duplicate_positions() -> None:
    tickets = (
        (1, 2, 3, 4, 5, 6),
        (7, 8, 9, 10, 11, 12),
        (1, 2, 3, 4, 5, 6),
        (13, 14, 15, 16, 17, 18),
    )

    assert (
        reproduce_native_tickets(
            registry_strategy_id="biglotto_ts3_markov_4bet_w30",
            replay_tickets=tickets,
            causal_history=(),
        )
        == tickets
    )


@pytest.mark.parametrize(
    ("strategy_id", "tickets"),
    [
        ("biglotto_triple_strike", ()),
        (
            "biglotto_ts3_markov_4bet_w30",
            ((1, 2, 3, 4, 5, 6),),
        ),
        ("unmapped", ((1, 2, 3, 4, 5, 6),)),
    ],
)
def test_closed_input_contract_rejects_unreproducible_rows(
    strategy_id: str,
    tickets: tuple[tuple[int, ...], ...],
) -> None:
    with pytest.raises(ReplayBackedNativeReproductionError):
        reproduce_native_tickets(
            registry_strategy_id=strategy_id,
            replay_tickets=tickets,
            causal_history=_history(),
        )
