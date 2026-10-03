"""Focused identity, structure, budget, selection, and result-seal checks."""

from __future__ import annotations

import itertools
import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pytest

from lottolab.research import b649_k20_overlap_block_repartition_12_8_exhaustive_r1 as search
from lottolab.research.b649_official_any_prize_exact import ExactPortfolioProbability


def _exact_result(outcome_count: int) -> ExactPortfolioProbability:
    return ExactPortfolioProbability(
        main_draw_count=0,
        special_count=43,
        m3_plus_draw_count=0,
        official_any_prize_outcome_count=outcome_count,
    )


def test_sts13_classes_have_expected_pasch_identity_and_unique_trade_class() -> None:
    classes = search.build_sts13_classes()

    assert search.is_valid_sts13(classes.cyclic)
    assert search.is_valid_sts13(classes.noncyclic)
    assert classes.cyclic_pasch_count == 13
    assert classes.noncyclic_pasch_count == 8
    assert classes.valid_pasch_trade_count == 13
    assert classes.pasch_count_8_trade_result_count == 13
    assert classes.pasch_count_8_isomorphism_class_count == 1
    assert not search.sts13_are_isomorphic(classes.cyclic, classes.noncyclic)
    assert search.build_sts13_classes() == classes


def test_family_has_26_frozen_labeled_portfolios_and_required_structure() -> None:
    candidates = search.build_family_candidates()

    assert len(candidates) == 26
    assert [(candidate.sts_class, candidate.deleted_point) for candidate in candidates] == [
        (sts_class, deleted_point)
        for sts_class in ("CYCLIC", "NONCYCLIC")
        for deleted_point in range(13)
    ]
    expected = {
        "TICKET_COUNT": 20,
        "LEGAL_DISTINCT_TICKETS": True,
        "FREQUENCY_PROFILE": {"2": 27, "3": 22},
        "ALL_NUMBER_FREQUENCIES_ARE_2_OR_3": True,
        "PAIRWISE_OVERLAP_HISTOGRAM": {"0": 97, "1": 93},
        "MAXIMUM_PAIRWISE_OVERLAP": 1,
    }
    assert all(
        search.structural_invariants(candidate.tickets) == expected for candidate in candidates
    )
    assert candidates == search.build_family_candidates()
    expected_first_sha = "c0657150a652fcf0ec7ad0fb024e88f5b839ad6dc42150e96726bdb2ca997024"
    assert candidates[0].sha256 == expected_first_sha
    assert candidates[0].sha256 == search.portfolio_sha256(candidates[0].tickets)


def test_winning_subset_route_matches_a_direct_small_space_count() -> None:
    portfolio = ((1, 2, 3), (3, 4, 5))
    expected = sum(
        any(len(set(ticket).intersection(subset)) >= 2 for ticket in portfolio)
        for subset in itertools.combinations(range(1, 8), 3)
    )

    assert (
        search.count_winning_subsets(
            portfolio,
            pool_size=7,
            subset_size=3,
            minimum_matches=2,
            chunk_size=5,
        )
        == expected
    )


def test_family_scoring_calls_the_official_evaluator_once_for_each_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidates = search.build_family_candidates()
    counts_by_portfolio = {
        candidate.tickets: search.BASELINE_COUNT - 1 for candidate in candidates
    }
    counts_by_portfolio[candidates[0].tickets] = search.KNOWN_CYCLIC_COUNT
    counts_by_portfolio[candidates[13].tickets] = 313_263_900
    calls: list[search.Portfolio] = []

    def fake_draws(_pool_size: int, _draw_size: int) -> search.DrawMasks:
        return np.empty(0, dtype=np.uint64)

    def fake_evaluate(
        portfolio: Sequence[Sequence[int]],
        *,
        draws: search.DrawMasks | None = None,
    ) -> ExactPortfolioProbability:
        del draws
        frozen = tuple(tuple(ticket) for ticket in portfolio)
        calls.append(frozen)
        return _exact_result(counts_by_portfolio[frozen])

    monkeypatch.setattr(search, "all_main_draw_masks", fake_draws)
    monkeypatch.setattr(search, "evaluate_portfolio", fake_evaluate)

    scored = search.score_family_candidates(candidates)

    assert len(scored) == 26
    assert len(calls) == 26
    assert len(set(calls)) == 25
    assert calls.count(candidates[0].tickets) == 2
    assert search.select_winner(scored).candidate.sts_class == "NONCYCLIC"
    assert search.select_winner(scored).candidate.deleted_point == 0


def test_winner_tie_break_uses_the_lowest_sha256() -> None:
    candidates = search.build_family_candidates()
    first = search.ScoredCandidate(
        candidate=search.PortfolioCandidate(
            sts_class=candidates[0].sts_class,
            deleted_point=candidates[0].deleted_point,
            tickets=candidates[0].tickets,
            sha256="f" * 64,
        ),
        official_any_prize_outcome_count=100,
    )
    second = search.ScoredCandidate(
        candidate=search.PortfolioCandidate(
            sts_class=candidates[1].sts_class,
            deleted_point=candidates[1].deleted_point,
            tickets=candidates[1].tickets,
            sha256="0" * 64,
        ),
        official_any_prize_outcome_count=100,
    )

    assert search.select_winner((first, second)) == second


def test_result_artifact_seals_one_fresh_canonical_and_7set_recount(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    candidates = search.build_family_candidates()
    counts_by_portfolio = {
        candidate.tickets: search.BASELINE_COUNT - 1 for candidate in candidates
    }
    counts_by_portfolio[candidates[0].tickets] = search.KNOWN_CYCLIC_COUNT
    counts_by_portfolio[candidates[13].tickets] = 313_263_900
    scored = tuple(
        search.ScoredCandidate(
            candidate=candidate,
            official_any_prize_outcome_count=counts_by_portfolio[candidate.tickets],
        )
        for candidate in candidates
    )
    pid_values = iter((101, 202))
    monkeypatch.setattr(search.os, "getpid", lambda: next(pid_values))
    record = search.build_stage_one_record(scored)
    output_path = tmp_path / "family-result.json"
    output_path.write_text(json.dumps(record), encoding="utf-8")
    winner_count = search.select_winner(scored).official_any_prize_outcome_count
    canonical_calls = 0
    seven_set_calls = 0

    def fake_draws(_pool_size: int, _draw_size: int) -> search.DrawMasks:
        return np.empty(0, dtype=np.uint64)

    def fake_evaluate(
        _portfolio: Sequence[Sequence[int]],
        *,
        draws: search.DrawMasks | None = None,
    ) -> ExactPortfolioProbability:
        nonlocal canonical_calls
        del draws
        canonical_calls += 1
        return _exact_result(winner_count)

    def fake_7set_recount(_portfolio: search.Portfolio) -> int:
        nonlocal seven_set_calls
        seven_set_calls += 1
        return winner_count

    monkeypatch.setattr(search, "all_main_draw_masks", fake_draws)
    monkeypatch.setattr(search, "evaluate_portfolio", fake_evaluate)
    monkeypatch.setattr(search, "independent_7set_recount", fake_7set_recount)

    sealed = search.seal_result(output_path)
    persisted = json.loads(output_path.read_text(encoding="utf-8"))

    assert canonical_calls == 1
    assert seven_set_calls == 1
    assert sealed["FAMILY_EVALUATION_PROCESS_ID"] == 101
    assert sealed["FRESH_CANONICAL_RECOUNT_PROCESS_ID"] == 202
    assert sealed["FRESH_CANONICAL_RECOUNT"] == winner_count
    assert sealed["INDEPENDENT_7SET_RECOUNT"] == winner_count
    assert sealed["CANONICAL_EVALUATION_BUDGET"] == {
        "FAMILY_CANDIDATES": 26,
        "FRESH_WINNER_RECOUNT": 1,
        "TOTAL_USED": 27,
    }
    assert sealed["FAMILY_RESULT"] == "IMPROVEMENT_CONFIRMED"
    assert sealed["READY_FOR_LOCAL_ASCENT"] == "YES"
    assert persisted == sealed
