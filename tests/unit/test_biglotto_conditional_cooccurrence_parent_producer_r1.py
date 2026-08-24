from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import (
    biglotto_conditional_cooccurrence_multi_ticket_candidate_batch_r1 as authority,
)
from lottolab.research import (
    biglotto_conditional_cooccurrence_parent_producer_r1 as producer,
)

type Ticket = tuple[int, int, int, int, int, int]
type History = tuple[Ticket, ...]


def _draw(seed: int) -> Ticket:
    numbers = sorted({((seed * 7 + offset * 9) % 49) + 1 for offset in range(6)})
    assert len(numbers) == 6
    return cast(Ticket, tuple(numbers))


def _history(length: int = authority.MINIMUM_HISTORY) -> History:
    return tuple(_draw(index) for index in range(length))


def _canonical(portfolio: tuple[Ticket, ...]) -> bytes:
    return json.dumps(portfolio, separators=(",", ":")).encode("utf-8")


def test_frozen_parent_source_is_the_manifest_pinned_authority() -> None:
    source_path = Path(authority.__file__)

    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == (
        producer.FROZEN_PARENT_SOURCE_SHA256
    )
    assert producer.MINIMUM_HISTORY == 751
    assert producer.SOURCE_WINDOWS == (50, 300, 750)


def test_minimum_history_boundary_fails_closed() -> None:
    with pytest.raises(authority.InsufficientHistoryError, match="at least 751"):
        producer.produce_parent_portfolio(
            _history(750),
            750,
            authority.CONSTRUCTOR_IDS[0],
            5,
        )


def test_each_window_and_number_tie_use_frozen_ordering() -> None:
    tied_history = ((1, 2, 3, 4, 5, 6),) * 751

    for window in producer.SOURCE_WINDOWS:
        ranking = authority.rank_numbers_by_window(tied_history, 751, window)
        assert window == ranking.WINDOW
        assert ranking.ORDERED_NUMBERS[:10] == tuple(range(1, 11))

    fused = authority.calculate_fused_number_ranking(tied_history, 751)
    assert fused.ORDERED_NUMBERS[:10] == tuple(range(1, 11))


def test_adapter_matches_frozen_parent_for_every_configuration() -> None:
    history = _history()

    for constructor_id in authority.CONSTRUCTOR_IDS:
        for budget in authority.TICKET_COUNTS:
            candidate_id = authority.candidate_id_for(constructor_id, budget)
            expected = authority.produce_candidate_portfolio(candidate_id, history, 751)
            first = producer.produce_parent_portfolio(
                history,
                751,
                constructor_id,
                budget,
            )
            second = producer.produce_parent_portfolio(
                history,
                751,
                constructor_id,
                budget,
            )

            assert first == expected
            assert second == expected
            assert _canonical(first) == _canonical(second)
            assert len(first) == budget
            assert len(first) == len(set(first))
            assert all(
                ticket == tuple(sorted(ticket))
                and len(ticket) == 6
                and len(set(ticket)) == 6
                and all(1 <= number <= 49 for number in ticket)
                for ticket in first
            )


def test_target_and_future_rows_are_excluded_by_construction() -> None:
    prior_history = _history()
    history_with_unreadable_target = (*prior_history, object(), ("future",))

    expected = producer.produce_parent_portfolio(
        prior_history,
        751,
        authority.CONSTRUCTOR_IDS[2],
        20,
    )
    actual = producer.produce_parent_portfolio(
        history_with_unreadable_target,
        751,
        authority.CONSTRUCTOR_IDS[2],
        20,
    )

    assert actual == expected
