"""Unit contracts for the wave-65 frozen evolution-engine ledger."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date
from typing import Any, cast

import pytest

import lottolab.application.legacy_evolution_native_portfolios_wave65 as evolution_module
from lottolab.application.legacy_evolution_native_portfolios_wave65 import (
    CLOSED_REASON,
    PINNED_DATASET_SHA256,
    TICKET_SEQUENCE_SHA256,
    LegacyEvolutionNativeWave65Request,
    LegacyEvolutionNativeWave65SourceError,
    generate_legacy_evolution_native_wave65_portfolio,
    load_legacy_evolution_native_wave65_ledger_for_verification,
)
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def test_wave65_first_501_targets_are_explicitly_closed() -> None:
    with pytest.raises(
        LegacyEvolutionNativeWave65SourceError,
        match=CLOSED_REASON,
    ):
        generate_legacy_evolution_native_wave65_portfolio(
            LegacyEvolutionNativeWave65Request(
                target_draw_number="96000001",
                target_draw_date=date(2007, 1, 2),
                history=(),
                dataset_sha256=PINNED_DATASET_SHA256,
            )
        )


def test_wave65_ledger_preserves_full_leaderboard_ticket_sequence() -> None:
    ledger = load_legacy_evolution_native_wave65_ledger_for_verification()

    assert len(ledger.targets) == 2149
    assert ledger.targets[0] == "96000001"
    assert ledger.targets[-1] == "115000073"
    assert Counter(ledger.status) == {
        "CLOSED_INSUFFICIENT_HISTORY": 501,
        "OK": 1648,
    }
    assert Counter(
        len(portfolio)
        for portfolio in ledger.tickets
        if portfolio is not None
    ) == {
        1: 6,
        2: 8,
        3: 10,
        4: 24,
        5: 187,
        6: 194,
        7: 217,
        8: 277,
        9: 273,
        10: 452,
    }
    assert (
        sum(
            len(portfolio)
            for portfolio in ledger.tickets
            if portfolio is not None
        )
        == 12959
    )
    serialized = [
        None
        if portfolio is None
        else [list(ticket) for ticket in portfolio]
        for portfolio in ledger.tickets
    ]
    assert (
        hashlib.sha256(_canonical_bytes(serialized)).hexdigest()
        == TICKET_SEQUENCE_SHA256
    )


def test_wave65_replays_first_executable_leaderboard_without_conflating_counts(
    monkeypatch: Any,
) -> None:
    ledger = load_legacy_evolution_native_wave65_ledger_for_verification()
    history = tuple(
        LegacyHistoryDraw(
            draw_number=f"draw-{index}",
            numbers=(1, 2, 3, 4, 5, 6),
        )
        for index in range(501)
    )

    def fixed_context(
        _history: tuple[LegacyHistoryDraw, ...],
    ) -> str:
        return ledger.context_sha256[501]

    monkeypatch.setattr(
        evolution_module,
        "_context_sha256",
        fixed_context,
    )

    result = generate_legacy_evolution_native_wave65_portfolio(
        LegacyEvolutionNativeWave65Request(
            target_draw_number=ledger.targets[501],
            target_draw_date=date(2011, 9, 2),
            history=history,
            dataset_sha256=PINNED_DATASET_SHA256,
        )
    )

    assert result.tickets == (
        (1, 3, 4, 17, 20, 39),
        (1, 9, 19, 20, 31, 39),
        (1, 3, 9, 19, 39, 46),
        (1, 9, 19, 20, 31, 39),
        (1, 3, 9, 17, 20, 39),
    )
    assert result.metadata.native_duplicate_ticket_count == 1
    assert result.metadata.candidate_k is None
    assert result.metadata.source_candidate_k_values == ()
    assert result.metadata.combination_count is None
    assert result.metadata.driver_population_size == 50
    assert result.metadata.driver_generations == 8
    assert result.metadata.total_strategies_tested == 482
    assert result.metadata.generation_population == (
        57,
        67,
        72,
        85,
        91,
        109,
        125,
        149,
    )
    assert result.metadata.source_random_state_explicit is True
    assert result.metadata.repeatability_parity_passed is True
    assert tuple(
        tuple(cast(list[int], row["numbers"]))
        for row in result.metadata.leaderboard
    ) == result.tickets


def test_wave65_rejects_non_full_prefix_context() -> None:
    ledger = load_legacy_evolution_native_wave65_ledger_for_verification()
    with pytest.raises(
        LegacyEvolutionNativeWave65SourceError,
        match="FROZEN_WAVE65_FULL_PREFIX_CONTEXT_MISMATCH",
    ):
        generate_legacy_evolution_native_wave65_portfolio(
            LegacyEvolutionNativeWave65Request(
                target_draw_number=ledger.targets[501],
                target_draw_date=date(2011, 9, 2),
                history=(),
                dataset_sha256=PINNED_DATASET_SHA256,
            )
        )
