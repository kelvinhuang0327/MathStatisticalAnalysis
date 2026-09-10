"""Focused tests for the operational-loop K-bucket portfolio selector."""

from __future__ import annotations

import pytest

from lottolab.application.b649_operational_portfolio_selector import (
    StrategyCandidate,
    build_portfolio,
)


def test_dedupes_and_ranks_by_consensus_then_quality() -> None:
    candidates = [
        StrategyCandidate("a", [(1, 2, 3, 4, 5, 6)]),
        StrategyCandidate("b", [(1, 2, 3, 4, 5, 6)]),
        StrategyCandidate("c", [(7, 8, 9, 10, 11, 12)]),
    ]
    quality = {"a": 0.5, "b": 0.5, "c": 0.9}
    buckets = build_portfolio(candidates, quality, bucket_sizes=(1, 2))
    assert buckets[1] == [(1, 2, 3, 4, 5, 6)]
    assert buckets[2] == [(1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12)]


def test_nested_buckets_are_prefixes() -> None:
    candidates = [
        StrategyCandidate(f"s{i}", [(i, i + 10, i + 20, i + 30, i + 40, i + 45)])
        for i in range(1, 8)
    ]
    quality = {f"s{i}": 1.0 / i for i in range(1, 8)}
    buckets = build_portfolio(candidates, quality, bucket_sizes=(3, 5, 7))
    assert buckets[3] == buckets[5][:3]
    assert buckets[5] == buckets[7][:5]


def test_rejects_malformed_ticket() -> None:
    candidates = [StrategyCandidate("a", [(1, 2, 3, 4, 5)])]
    with pytest.raises(ValueError):
        build_portfolio(candidates, {}, bucket_sizes=(1,))


def test_raises_when_not_enough_distinct_candidates() -> None:
    candidates = [StrategyCandidate("a", [(1, 2, 3, 4, 5, 6)])]
    with pytest.raises(ValueError):
        build_portfolio(candidates, {}, bucket_sizes=(2,))


def test_deterministic_repeat_call() -> None:
    candidates = [
        StrategyCandidate("a", [(5, 4, 3, 2, 1, 6)]),
        StrategyCandidate("b", [(12, 11, 10, 9, 8, 7)]),
    ]
    quality = {"a": 0.3, "b": 0.3}
    first = build_portfolio(candidates, quality, bucket_sizes=(2,))
    second = build_portfolio(candidates, quality, bucket_sizes=(2,))
    assert first == second
