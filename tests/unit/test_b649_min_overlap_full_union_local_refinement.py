# pyright: reportPrivateUsage=false
"""Focused checks for the frozen K10 full-union one-swap study."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict
from itertools import combinations
from typing import cast

import pytest
from tools.b649_operational_prediction_loop import StrategyStream
from tools.run_b649_min_overlap_full_union_local_refinement_r1 import (
    PredrawRow,
    _build_full_union,
    _canonical_bytes,
    _load_history_before,
    _project_branch2_predraw_rows,
    render_report,
)

from lottolab.research.b649_min_overlap_full_union_local_refinement import (
    ITERATION_CAP,
    SELECTION_DRAW_COUNT,
    SELECTION_SEED,
    K,
    refine_min_overlap_k10,
)
from lottolab.research.b649_official_any_prize_exact import (
    all_main_draw_masks,
    evaluate_portfolio,
)
from lottolab.strategies.adapters.base import CausalDrawRow


def test_frozen_search_contract_and_known_answer_toy() -> None:
    assert (K, SELECTION_SEED, SELECTION_DRAW_COUNT, ITERATION_CAP) == (
        10,
        20260923,
        65_536,
        4,
    )
    baseline = tuple(combinations(range(1, 7), 3))[:K]
    union = (*baseline, (7, 8, 9), (10, 11, 12))
    draws = all_main_draw_masks(13, 3)
    result = refine_min_overlap_k10(
        union,
        baseline,
        selection_draws=draws,
        pool_size=13,
        draw_size=3,
        outright_matches=2,
    )
    repeat = refine_min_overlap_k10(
        union,
        baseline,
        selection_draws=draws,
        pool_size=13,
        draw_size=3,
        outright_matches=2,
    )
    assert result == repeat
    assert 1 <= result.swap_count <= ITERATION_CAP
    assert len(result.portfolio) == K == len(set(result.portfolio))
    assert set(result.portfolio).issubset(union)
    assert result.final_sample_outcome_count > result.initial_sample_outcome_count
    assert all(gain > 0 for _, _, gain in result.swaps)

    def exact_count(portfolio: tuple[tuple[int, ...], ...]) -> int:
        return evaluate_portfolio(
            portfolio,
            pool_size=13,
            draw_size=3,
            outright_matches=2,
            draws=draws,
        ).official_any_prize_outcome_count

    neighbors = [
        (exact_count((*baseline[:remove], union[add], *baseline[remove + 1 :])), remove, add)
        for remove in range(K)
        for add in range(K, len(union))
    ]
    best_count = max(count for count, _, _ in neighbors)
    expected = min((remove, add) for count, remove, add in neighbors if count == best_count)
    assert result.swaps[0][:2] == (expected[0], expected[1])
    assert result.initial_sample_outcome_count == exact_count(baseline)
    assert result.final_sample_outcome_count == exact_count(result.portfolio)
    if result.stopped_by == "NO_IMPROVING_SWAP":
        assert all(
            exact_count((*result.portfolio[:remove], union[add], *result.portfolio[remove + 1 :]))
            <= result.final_sample_outcome_count
            for remove in range(K)
            for add in range(len(union))
            if union[add] not in result.portfolio
        )


def test_no_regret_when_full_union_equals_baseline() -> None:
    baseline = tuple(combinations(range(1, 7), 3))[:K]
    result = refine_min_overlap_k10(
        baseline,
        baseline,
        selection_draws=all_main_draw_masks(13, 3),
        pool_size=13,
        draw_size=3,
        outright_matches=2,
    )
    assert result.swap_count == 0
    assert result.stopped_by == "NO_IMPROVING_SWAP"
    assert result.portfolio == baseline
    assert result.final_sample_outcome_count == result.initial_sample_outcome_count


def test_baseline_must_be_contained_in_full_union() -> None:
    baseline = tuple(combinations(range(1, 7), 3))[:K]
    union = (*baseline[1:], (7, 8, 9))
    with pytest.raises(ValueError, match="outside the full PRE_DRAW union"):
        refine_min_overlap_k10(
            union,
            baseline,
            selection_draws=all_main_draw_masks(13, 3),
            pool_size=13,
            draw_size=3,
            outright_matches=2,
        )


def test_causal_history_query_never_reads_target_outcome() -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute(
        "CREATE TABLE draws (lottery_type TEXT, draw_number TEXT, "
        "draw_date TEXT, main_numbers_json TEXT)"
    )
    connection.executemany(
        "INSERT INTO draws VALUES (?, ?, ?, ?)",
        [
            ("BIG_LOTTO", "1", "2024-01-01", json.dumps([1, 2, 3, 4, 5, 6])),
            ("BIG_LOTTO", "2", "2024-01-02", "TARGET_OUTCOME_MUST_NOT_PARSE"),
        ],
    )
    prior = CausalDrawRow("1", "2024-01-01", (1, 2, 3, 4, 5, 6))
    row = PredrawRow(
        target_draw="2",
        target_date="2024-01-02",
        cutoff_draw="1",
        cutoff_date="2024-01-01",
        history_count=1,
        history_sha256=hashlib.sha256(_canonical_bytes([asdict(prior)])).hexdigest(),
        pool_sha256="0" * 64,
        candidate_count=20,
    )
    assert _load_history_before(connection, row) == (prior,)
    connection.close()


def test_full_union_deduplicates_native_tickets_before_pruning() -> None:
    history = (CausalDrawRow("1", "2024-01-01", (1, 2, 3, 4, 5, 6)),)

    class StubAdapter:
        strategy_version = "1.0.0"

        def __init__(self, strategy_id: str, ticket: tuple[int, ...]) -> None:
            self.strategy_id = strategy_id
            self.ticket = ticket

        def get_one_bet(
            self, source: tuple[CausalDrawRow, ...], lottery: object
        ) -> tuple[tuple[int, ...], None]:
            assert source == history
            return self.ticket, None

    def stream(name: str, ticket: tuple[int, ...]) -> StrategyStream:
        return cast(
            StrategyStream,
            type(
                "StubStream",
                (),
                {
                    "enabled": True,
                    "strategy_id": name,
                    "strategy_version": "1.0.0",
                    "native_ticket_count": 1,
                    "adapter_factory": staticmethod(lambda: StubAdapter(name, ticket)),
                },
            )(),
        )

    streams = (
        stream("a", (6, 5, 4, 3, 2, 1)),
        stream("b", (1, 2, 3, 4, 5, 6)),
        stream("c", (7, 8, 9, 10, 11, 12)),
    )
    union, pool_hash = _build_full_union(history, streams)
    assert union == ((1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12))
    raw_pool = [
        ("a", ((6, 5, 4, 3, 2, 1),)),
        ("b", ((1, 2, 3, 4, 5, 6),)),
        ("c", ((7, 8, 9, 10, 11, 12),)),
    ]
    assert pool_hash == hashlib.sha256(_canonical_bytes(raw_pool)).hexdigest()


def test_pinned_pre_draw_projection_is_cohort_aligned() -> None:
    rows = _project_branch2_predraw_rows()
    assert len(rows) == 1761
    assert (rows[0].target_draw, rows[-1].target_draw) == ("97000098", "115000089")
    assert {row.candidate_count for row in rows} == {20, 21, 22}
    assert all(row.history_count > 0 for row in rows)


def test_report_uses_exact_result_fields() -> None:
    report = render_report(
        {
            "target_count": 1,
            "full_union": {
                "size_distribution": {21: 1},
                "outside_prior20_distribution": {1: 1},
                "outside_prior20_total": 1,
                "targets_with_outside_tickets": 1,
            },
            "search": {
                "targets_with_any_swap": 1,
                "targets_with_final_portfolio_change": 1,
                "mean_swap_count": "1",
            },
            "evaluation": {
                "min_overlap_mean_probability": "1/4",
                "candidate_mean_probability": "3/10",
                "absolute_delta": "1/20",
                "relative_delta": "1/5",
                "ready_for_branch2_oos": "YES",
                "outside_prior20_subset": {
                    "target_count": 1,
                    "min_overlap_mean_probability": "1/4",
                    "candidate_mean_probability": "3/10",
                    "absolute_delta": "1/20",
                    "relative_delta": "1/5",
                },
            },
        }
    )
    assert "Candidate mean probability | 3/10" in report
    assert "Absolute delta | 1/20" in report
    assert "READY_FOR_BRANCH2_OOS | **YES**" in report
