"""Unit contracts for the thirtieth frozen source-native wave."""

from __future__ import annotations

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave30 import (
    TEN_BET_METHOD_ID,
    LegacySourceNativeWave30Error,
    LegacySourceNativeWave30Request,
    generate_legacy_source_native_wave30_portfolio,
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


def _generate(history_count: int = 200):
    return generate_legacy_source_native_wave30_portfolio(
        LegacySourceNativeWave30Request(
            legacy_method_id=TEN_BET_METHOD_ID,
            target_draw_number=str(history_count + 1),
            history=_history(history_count),
        )
    )


def test_wave30_preserves_engine_then_three_ewma_ticket_order() -> None:
    result = _generate()

    assert result.tickets == (
        (5, 29, 34, 39, 44, 49),
        (10, 12, 13, 14, 15, 17),
        (11, 16, 20, 22, 37, 44),
        (22, 27, 32, 37, 42, 47),
        (3, 10, 17, 24, 31, 38),
        (1, 6, 8, 11, 13, 15),
        (22, 27, 32, 37, 42, 47),
        (22, 27, 32, 37, 42, 47),
        (22, 27, 32, 37, 42, 47),
        (22, 27, 32, 37, 42, 47),
    )
    assert result.metadata.native_duplicate_ticket_count == 4
    assert result.metadata.source_engine_method_count == 7
    assert result.metadata.source_ewma_variant_count == 3
    assert result.metadata.source_ewma_lambdas == ("0.03", "0.10", "0.15")
    assert result.metadata.candidate_pool_size is None
    assert result.metadata.source_method_combination_count == 10


def test_wave30_preserves_numpy_pin_and_history_semantics() -> None:
    result = _generate()

    assert result.metadata.numpy_version_pin == "numpy==1.26.2"
    assert result.metadata.numpy_scalar_exp_reproduction == (
        "SCALAR_NUMPY_EXP_REPRODUCED_WITH_IEEE754_MATH_EXP"
    )
    assert result.metadata.source_history_order == "OLDEST_FIRST"
    assert result.metadata.source_history_first_draw_number == "1"
    assert result.metadata.source_history_last_draw_number == "200"


def test_wave30_rejects_empty_history_and_unknown_method() -> None:
    with pytest.raises(LegacySourceNativeWave30Error):
        generate_legacy_source_native_wave30_portfolio(
            LegacySourceNativeWave30Request(
                legacy_method_id=TEN_BET_METHOD_ID,
                target_draw_number="1",
                history=(),
            )
        )
    with pytest.raises(LegacySourceNativeWave30Error):
        generate_legacy_source_native_wave30_portfolio(
            LegacySourceNativeWave30Request(
                legacy_method_id="missing",
                target_draw_number="2",
                history=_history(1),
            )
        )
