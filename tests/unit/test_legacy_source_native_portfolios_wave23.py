"""Unit contracts for the twenty-third frozen source-native wave."""

from __future__ import annotations

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave23 import (
    FIVE_ME_METHOD_ID,
    TME_METHOD_ID,
    LegacySourceNativeWave23Error,
    LegacySourceNativeWave23Request,
    generate_legacy_source_native_wave23_portfolio,
)


def _history(count: int) -> tuple[LegacyHistoryDraw, ...]:
    rows: list[LegacyHistoryDraw] = []
    for index in range(count):
        values = sorted(
            ((index * 7 + offset * 5) % 49) + 1
            for offset in range(6)
        )
        rows.append(
            LegacyHistoryDraw(
                draw_number=str(index + 1),
                numbers=(
                    values[0],
                    values[1],
                    values[2],
                    values[3],
                    values[4],
                    values[5],
                ),
            )
        )
    return tuple(rows)


def test_wave23_preserves_5me_and_tme_source_positions() -> None:
    history = _history(50)
    five_me = generate_legacy_source_native_wave23_portfolio(
        LegacySourceNativeWave23Request(
            legacy_method_id=FIVE_ME_METHOD_ID,
            target_draw_number="51",
            history=history,
        )
    )
    tme = generate_legacy_source_native_wave23_portfolio(
        LegacySourceNativeWave23Request(
            legacy_method_id=TME_METHOD_ID,
            target_draw_number="51",
            history=history,
        )
    )

    assert five_me.tickets == (
        (5, 11, 16, 21, 43, 49),
        (3, 10, 17, 31, 38, 45),
        (8, 13, 18, 23, 28, 33),
        (1, 6, 11, 16, 21, 26),
        (1, 6, 11, 16, 21, 26),
    )
    assert tme.tickets == five_me.tickets[:3]
    assert five_me.metadata.native_duplicate_ticket_count == 1
    assert tme.metadata.native_duplicate_ticket_count == 0
    assert five_me.metadata.combination_count is None
    assert tme.metadata.combination_count is None
    assert five_me.metadata.markov_order == 2
    assert five_me.metadata.source_candidate_ticket_counts == (
        20,
        1,
        1,
        1,
        1,
    )


@pytest.mark.parametrize(
    ("history_count", "expected_order"),
    ((1, 1), (49, 1), (50, 2), (149, 2), (150, 3)),
)
def test_wave23_preserves_adaptive_markov_order(
    history_count: int,
    expected_order: int,
) -> None:
    result = generate_legacy_source_native_wave23_portfolio(
        LegacySourceNativeWave23Request(
            legacy_method_id=TME_METHOD_ID,
            target_draw_number=str(history_count + 1),
            history=_history(history_count),
        )
    )

    assert result.metadata.markov_order == expected_order


def test_wave23_statistical_rng_ignores_bookkeeping_seed() -> None:
    history = _history(20)
    first = generate_legacy_source_native_wave23_portfolio(
        LegacySourceNativeWave23Request(
            legacy_method_id=FIVE_ME_METHOD_ID,
            target_draw_number="21",
            history=history,
            user_seed="first",
        )
    )
    second = generate_legacy_source_native_wave23_portfolio(
        LegacySourceNativeWave23Request(
            legacy_method_id=FIVE_ME_METHOD_ID,
            target_draw_number="21",
            history=history,
            user_seed="second",
        )
    )

    assert first.tickets == second.tickets
    assert first.metadata.seed_digest != second.metadata.seed_digest


def test_wave23_rejects_empty_history_and_unknown_method() -> None:
    with pytest.raises(LegacySourceNativeWave23Error):
        generate_legacy_source_native_wave23_portfolio(
            LegacySourceNativeWave23Request(
                legacy_method_id=FIVE_ME_METHOD_ID,
                target_draw_number="1",
                history=(),
            )
        )
    with pytest.raises(LegacySourceNativeWave23Error):
        generate_legacy_source_native_wave23_portfolio(
            LegacySourceNativeWave23Request(
                legacy_method_id="missing",
                target_draw_number="2",
                history=_history(1),
            )
        )
