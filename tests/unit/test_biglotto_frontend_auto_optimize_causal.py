"""Regression checks for causal validation and reproducible RNG streams."""

from __future__ import annotations

import random
from dataclasses import replace

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.adapters.biglotto_frontend_auto_optimize_causal import (
    BigLottoFrontendAutoOptimizeCausalAdapter,
    _seed_for_candidate,
)


def _history(n: int) -> tuple[CausalDrawRow, ...]:
    return tuple(
        CausalDrawRow(
            str(i),
            f"2020-01-{i + 1:02d}",
            tuple(sorted({((i + j * 7) % 49) + 1 for j in range(6)})),
        )
        for i in range(n)
    )


def test_every_validation_prediction_uses_only_earlier_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = _history(30)
    seen: list[tuple[str, tuple[CausalDrawRow, ...]]] = []

    def predict(_self: object, name: str, prefix: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
        seen.append((name, prefix))
        return (1, 2, 3, 4, 5, 6)

    monkeypatch.setattr(BigLottoFrontendAutoOptimizeCausalAdapter, "_candidate_prediction", predict)
    scores = BigLottoFrontendAutoOptimizeCausalAdapter()._scores(history)
    assert len(scores) == 14
    assert len(seen) == 14 * 6
    for _, prefix in seen:
        target_index = len(prefix)
        assert 24 <= target_index <= 29
        assert prefix == history[:target_index]
        assert all(int(row.draw) < int(history[target_index].draw) for row in prefix)


def test_seed_uses_only_candidate_and_available_history() -> None:
    history = _history(30)
    changed_future = (
        *history[:27],
        replace(history[27], numbers=(1, 2, 3, 4, 5, 6)),
        *history[28:],
    )
    assert _seed_for_candidate("montecarlo", history[:27]) == _seed_for_candidate(
        "montecarlo", changed_future[:27]
    )
    assert _seed_for_candidate("montecarlo", history) != _seed_for_candidate(
        "montecarlo", changed_future
    )
    assert _seed_for_candidate("montecarlo", history) != _seed_for_candidate("ml_forest", history)


def test_missing_inner_result_excludes_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    def predict(_self: object, name: str, prefix: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
        if name == "frequency" and len(prefix) == 25:
            raise ValueError("unknown result")
        return (1, 2, 3, 4, 5, 6)

    monkeypatch.setattr(BigLottoFrontendAutoOptimizeCausalAdapter, "_candidate_prediction", predict)
    scores = BigLottoFrontendAutoOptimizeCausalAdapter()._scores(_history(30))
    assert len(scores) == 13
    assert all(score.strategy != "frequency" and score.total_tests == 6 for score in scores)


def test_invalid_inner_ticket_excludes_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    def predict(_self: object, name: str, prefix: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
        del prefix
        return (1, 1, 2, 3, 4, 5) if name == "frequency" else (1, 2, 3, 4, 5, 6)

    monkeypatch.setattr(BigLottoFrontendAutoOptimizeCausalAdapter, "_candidate_prediction", predict)
    scores = BigLottoFrontendAutoOptimizeCausalAdapter()._scores(_history(30))
    assert len(scores) == 13
    assert all(score.strategy != "frequency" for score in scores)


def test_real_stochastic_candidate_repeats_with_unrelated_global_rng_changes() -> None:
    history = _history(30)
    adapter = BigLottoFrontendAutoOptimizeCausalAdapter()
    first = adapter._candidate_prediction("montecarlo", history)
    for _ in range(500):
        random.random()
    second = BigLottoFrontendAutoOptimizeCausalAdapter()._candidate_prediction(
        "montecarlo", history
    )
    assert first == second
    assert len(first) == 6


def test_public_adapter_has_legal_reproducible_output() -> None:
    history = _history(30)
    a = BigLottoFrontendAutoOptimizeCausalAdapter().get_one_bet(history, LotteryType.BIG_LOTTO)
    b = BigLottoFrontendAutoOptimizeCausalAdapter().get_one_bet(history, LotteryType.BIG_LOTTO)
    assert a == b
    assert len(a[0]) == len(set(a[0])) == 6
