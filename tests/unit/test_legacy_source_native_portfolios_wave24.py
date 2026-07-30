"""Unit contracts for the twenty-fourth frozen source-native wave."""

from __future__ import annotations

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave24 import (
    ASM_METHOD_ID,
    DCB_METHOD_ID,
    ECP_METHOD_ID,
    FOUR_BET_DCB_METHOD_ID,
    THREE_BET_OPTIMIZER_METHOD_ID,
    TWO_BET_FINAL_METHOD_ID,
    LegacySourceNativeWave24Error,
    LegacySourceNativeWave24Request,
    frozen_tools_kill_numbers,
    generate_legacy_source_native_wave24_portfolio,
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


def _generate(
    method_id: str,
    *,
    history_count: int = 50,
    user_seed: str = "seed",
):
    return generate_legacy_source_native_wave24_portfolio(
        LegacySourceNativeWave24Request(
            legacy_method_id=method_id,
            target_draw_number=str(history_count + 1),
            history=_history(history_count),
            user_seed=user_seed,
        )
    )


def test_wave24_preserves_all_six_native_ticket_mappings() -> None:
    expected = {
        TWO_BET_FINAL_METHOD_ID: (
            (3, 10, 17, 31, 38, 45),
            (8, 13, 18, 31, 38, 45),
        ),
        THREE_BET_OPTIMIZER_METHOD_ID: (
            (3, 10, 17, 31, 38, 45),
            (13, 18, 23, 28, 38, 45),
            (11, 16, 21, 23, 28, 33),
        ),
        ASM_METHOD_ID: (
            (3, 10, 17, 31, 38, 45),
            (3, 10, 13, 18, 23, 28),
            (11, 16, 17, 31, 33, 38),
        ),
        DCB_METHOD_ID: (
            (1, 11, 16, 21, 43, 49),
            (1, 3, 6, 10, 26, 49),
            (3, 10, 17, 31, 38, 45),
        ),
        FOUR_BET_DCB_METHOD_ID: (
            (1, 11, 16, 21, 43, 49),
            (1, 3, 6, 10, 26, 49),
            (3, 10, 17, 31, 38, 45),
            (13, 18, 23, 28, 38, 45),
        ),
        ECP_METHOD_ID: (
            (11, 13, 16, 21, 43, 49),
            (13, 18, 23, 28, 33, 49),
            (3, 10, 17, 28, 31, 33),
        ),
    }

    results = {
        method_id: _generate(method_id) for method_id in expected
    }

    assert {
        method_id: result.tickets
        for method_id, result in results.items()
    } == expected
    assert (
        results[TWO_BET_FINAL_METHOD_ID].metadata.candidate_pool_size
        == 15
    )
    assert all(
        result.metadata.candidate_pool_size == 18
        for method_id, result in results.items()
        if method_id != TWO_BET_FINAL_METHOD_ID
    )
    assert (
        results[
            TWO_BET_FINAL_METHOD_ID
        ].metadata.source_method_combination_count
        == 3
    )
    assert results[DCB_METHOD_ID].metadata.source_method_combination_count == 4
    assert results[FOUR_BET_DCB_METHOD_ID].metadata.native_ticket_count == 4
    assert results[ECP_METHOD_ID].metadata.statistical_call_count == 50


def test_wave24_preserves_dynamic_kill_threshold_and_order() -> None:
    assert frozen_tools_kill_numbers(_history(29)) == ()
    assert frozen_tools_kill_numbers(_history(30)) == (
        2,
        4,
        5,
        7,
        9,
    )

    result = _generate(THREE_BET_OPTIMIZER_METHOD_ID, history_count=30)

    assert result.metadata.kill_numbers == (2, 4, 5, 7, 9)
    assert result.metadata.candidate_pool == (
        35,
        3,
        10,
        17,
        31,
        38,
        45,
        15,
        20,
        25,
        30,
        40,
        1,
        6,
        26,
        48,
        4,
        2,
    )


def test_wave24_statistical_rng_ignores_bookkeeping_seed() -> None:
    first = _generate(ECP_METHOD_ID, history_count=20, user_seed="first")
    second = _generate(ECP_METHOD_ID, history_count=20, user_seed="second")

    assert first.tickets == second.tickets
    assert first.metadata.seed_digest != second.metadata.seed_digest
    assert first.metadata.statistical_call_count == 50


def test_wave24_rejects_empty_history_and_unknown_method() -> None:
    with pytest.raises(LegacySourceNativeWave24Error):
        generate_legacy_source_native_wave24_portfolio(
            LegacySourceNativeWave24Request(
                legacy_method_id=TWO_BET_FINAL_METHOD_ID,
                target_draw_number="1",
                history=(),
            )
        )
    with pytest.raises(LegacySourceNativeWave24Error):
        generate_legacy_source_native_wave24_portfolio(
            LegacySourceNativeWave24Request(
                legacy_method_id="missing",
                target_draw_number="2",
                history=_history(1),
            )
        )
