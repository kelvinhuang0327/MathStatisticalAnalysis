"""Unit contracts for the twenty-seventh frozen source-native wave."""

from __future__ import annotations

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave27 import (
    GEMINI_2BET_METHOD_ID,
    GEMINI_3BET_METHOD_ID,
    MODEL_V1_METHOD_ID,
    MODEL_V2_METHOD_ID,
    LegacySourceNativeWave27Error,
    LegacySourceNativeWave27Request,
    LegacySourceNativeWave27SourceError,
    generate_legacy_source_native_wave27_portfolio,
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


def _generate(method_id: str, history_count: int = 50):
    return generate_legacy_source_native_wave27_portfolio(
        LegacySourceNativeWave27Request(
            legacy_method_id=method_id,
            target_draw_number=str(history_count + 1),
            history=_history(history_count),
        )
    )


def test_wave27_preserves_all_four_native_ticket_mappings() -> None:
    expected = {
        MODEL_V1_METHOD_ID: (
            (3, 10, 17, 31, 38, 45),
            (8, 13, 18, 31, 38, 45),
        ),
        MODEL_V2_METHOD_ID: (
            (3, 10, 11, 17, 31, 38),
            (8, 11, 16, 21, 38, 45),
        ),
        GEMINI_2BET_METHOD_ID: (
            (3, 10, 17, 31, 38, 45),
            (8, 13, 18, 31, 38, 45),
        ),
        GEMINI_3BET_METHOD_ID: (
            (3, 10, 17, 31, 38, 45),
            (8, 13, 18, 23, 38, 45),
            (5, 11, 18, 23, 28, 33),
        ),
    }
    results = {
        method_id: _generate(method_id) for method_id in expected
    }

    assert {
        method_id: result.tickets
        for method_id, result in results.items()
    } == expected
    assert results[MODEL_V1_METHOD_ID].metadata.candidate_pool_size == 12
    assert results[MODEL_V2_METHOD_ID].metadata.candidate_pool_size == 18
    assert (
        results[GEMINI_2BET_METHOD_ID].metadata.minimum_history_draws
        == 50
    )
    assert (
        results[GEMINI_3BET_METHOD_ID].metadata.native_ticket_count
        == 3
    )
    assert all(
        result.metadata.candidate_k is None
        and result.metadata.combination_count is None
        for result in results.values()
    )


@pytest.mark.parametrize(
    "method_id",
    (GEMINI_2BET_METHOD_ID, GEMINI_3BET_METHOD_ID),
)
def test_wave27_preserves_verifier_minimum_history(
    method_id: str,
) -> None:
    with pytest.raises(
        LegacySourceNativeWave27SourceError,
        match="AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM",
    ):
        _generate(method_id, history_count=49)


def test_wave27_model_and_verifier_v1_remain_distinct_contracts() -> None:
    model = _generate(MODEL_V1_METHOD_ID, history_count=49)

    assert len(model.tickets) == 2
    assert model.metadata.minimum_history_draws == 1
    assert (
        model.metadata.source_sha256
        != "d5ca233aa776d257c12b0f07e6d68205c5126b05759c39cf00e8ce8314062df3"
    )


def test_wave27_preserves_distinct_short_candidate_closures() -> None:
    history = _history(50)
    same_ticket = (1, 2, 3, 4, 5, 6)
    cache = {
        (50, method_name): same_ticket
        for method_name in ("deviation", "markov", "statistical")
    }
    with pytest.raises(
        LegacySourceNativeWave27SourceError,
        match="FROZEN_SOURCE_EMITTED_INVALID_NATIVE_TICKET",
    ):
        generate_legacy_source_native_wave27_portfolio(
            LegacySourceNativeWave27Request(
                legacy_method_id=MODEL_V1_METHOD_ID,
                target_draw_number="51",
                history=history,
            ),
            engine_cache=cache,
        )
    with pytest.raises(
        LegacySourceNativeWave27SourceError,
        match="FROZEN_SOURCE_CANDIDATE_POOL_BELOW_REQUIRED_SLICE",
    ):
        generate_legacy_source_native_wave27_portfolio(
            LegacySourceNativeWave27Request(
                legacy_method_id=GEMINI_2BET_METHOD_ID,
                target_draw_number="51",
                history=history,
            ),
            engine_cache=cache,
        )


def test_wave27_rejects_empty_history_and_unknown_method() -> None:
    with pytest.raises(LegacySourceNativeWave27Error):
        generate_legacy_source_native_wave27_portfolio(
            LegacySourceNativeWave27Request(
                legacy_method_id=MODEL_V1_METHOD_ID,
                target_draw_number="1",
                history=(),
            )
        )
    with pytest.raises(LegacySourceNativeWave27Error):
        generate_legacy_source_native_wave27_portfolio(
            LegacySourceNativeWave27Request(
                legacy_method_id="missing",
                target_draw_number="2",
                history=_history(1),
            )
        )
