"""Focused checks for the frozen K20 atomic (2,1,1) exchange pilot."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import lottolab.research.b649_k20_three_ticket_atomic_211_exchange_pilot_r1 as pilot
from lottolab.research.b649_official_any_prize_exact import (
    DrawMasks,
    ExactPortfolioProbability,
)
from lottolab.research.b649_official_any_prize_exact import (
    evaluate_portfolio as canonical_evaluate_portfolio,
)

REPOSITORY = Path(__file__).resolve().parents[2]


def _result(count: int) -> ExactPortfolioProbability:
    return ExactPortfolioProbability(
        main_draw_count=1,
        special_count=1,
        m3_plus_draw_count=0,
        official_any_prize_outcome_count=count,
    )


def _small_draws(_pool_size: int, _draw_size: int) -> DrawMasks:
    return np.array([0], dtype=np.uint64)


def test_start_artifact_reproduces_the_frozen_canonical_identity() -> None:
    start = pilot.load_start_portfolio(REPOSITORY)

    assert len(start) == 20
    assert start == tuple(sorted(start))
    assert pilot.canonical_portfolio_sha256(start) == pilot.START_PORTFOLIO_SHA256


def test_family_has_1080_raw_combinations_and_504_legal_unique_endpoints() -> None:
    start = pilot.load_start_portfolio(REPOSITORY)
    family = pilot.generate_candidate_family(start)

    assert family.raw_combinations == 6 * 5 * 6 * 6 == 1080
    assert len(family.candidates) == 504


def test_candidates_change_only_frozen_slots_and_preserve_atomic_move_sizes() -> None:
    start = pilot.load_start_portfolio(REPOSITORY)
    family = pilot.generate_candidate_family(start)
    start_sets = tuple(set(ticket) for ticket in start)

    for candidate in family.candidates:
        slots = candidate.slot_portfolio
        changed_slots = tuple(
            index
            for index, (before, after) in enumerate(zip(start, slots, strict=True))
            if before != after
        )
        assert changed_slots == (0, 1, 2)
        assert slots[3:] == start[3:]
        assert len(start_sets[0] - set(slots[0])) == 2
        assert len(set(slots[0]) - start_sets[0]) == 2
        assert len(start_sets[1] - set(slots[1])) == 1
        assert len(set(slots[1]) - start_sets[1]) == 1
        assert len(start_sets[2] - set(slots[2])) == 1
        assert len(set(slots[2]) - start_sets[2]) == 1
        assert all(
            len(ticket) == 6
            and len(set(ticket)) == 6
            and all(1 <= number <= 49 for number in ticket)
            for ticket in candidate.portfolio
        )
        assert len(candidate.portfolio) == len(set(candidate.portfolio)) == 20


def test_candidate_order_is_deterministic_by_complete_portfolio_identity() -> None:
    start = pilot.load_start_portfolio(REPOSITORY)
    first = pilot.generate_candidate_family(start).candidates
    second = pilot.generate_candidate_family(start).candidates
    identities = tuple(candidate.portfolio for candidate in first)

    assert first == second
    assert identities == tuple(sorted(identities))
    assert len(set(identities)) == 504


def test_canonical_evaluator_is_the_production_exact_authority() -> None:
    assert pilot.evaluate_portfolio is canonical_evaluate_portfolio


def test_start_recount_uses_canonical_evaluator_and_stops_at_first_improvement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[pilot.Portfolio] = []
    draws = np.array([0], dtype=np.uint64)

    def exact_evaluator(portfolio: pilot.Portfolio, *, draws: object) -> ExactPortfolioProbability:
        calls.append(tuple(tuple(ticket) for ticket in portfolio))
        count = pilot.START_EXACT_COUNT if len(calls) == 1 else pilot.START_EXACT_COUNT + 7
        return _result(count)

    def fixture_draws(_pool_size: int, _draw_size: int) -> DrawMasks:
        return draws

    monkeypatch.setattr(pilot, "all_main_draw_masks", fixture_draws)
    monkeypatch.setattr(pilot, "evaluate_portfolio", exact_evaluator)
    outcome = pilot.run_pilot(REPOSITORY)

    assert calls[0] == outcome.start_portfolio
    assert len(calls) == 2
    assert outcome.candidates_evaluated == 1
    assert outcome.pilot_result == "IMPROVEMENT_FOUND"
    assert outcome.best_count == pilot.START_EXACT_COUNT + 7
    assert outcome.best_delta == 7
    assert outcome.first_improving_candidate_ordinal == 1
    assert outcome.best_candidate is not None
    assert calls[1] == outcome.best_candidate.portfolio


def test_start_recount_mismatch_stops_before_candidate_evaluations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def wrong_evaluator(
        _portfolio: pilot.Portfolio, *, draws: object
    ) -> ExactPortfolioProbability:
        nonlocal calls
        calls += 1
        return _result(pilot.START_EXACT_COUNT - 1)

    monkeypatch.setattr(pilot, "all_main_draw_masks", _small_draws)
    monkeypatch.setattr(pilot, "evaluate_portfolio", wrong_evaluator)

    with pytest.raises(pilot.StartCanonicalRecountMismatch):
        pilot.run_pilot(REPOSITORY)

    assert calls == 1


def test_no_improvement_evaluates_all_504_candidates_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def plateau_evaluator(
        _portfolio: pilot.Portfolio, *, draws: object
    ) -> ExactPortfolioProbability:
        nonlocal calls
        calls += 1
        return _result(pilot.START_EXACT_COUNT)

    monkeypatch.setattr(pilot, "all_main_draw_masks", _small_draws)
    monkeypatch.setattr(pilot, "evaluate_portfolio", plateau_evaluator)
    outcome = pilot.run_pilot(REPOSITORY)

    assert calls == 505
    assert outcome.candidates_evaluated == 504
    assert outcome.pilot_result == "NO_IMPROVEMENT"
    assert outcome.best_count == pilot.START_EXACT_COUNT
    assert outcome.best_delta == 0
    assert outcome.best_portfolio_sha256 == pilot.START_PORTFOLIO_SHA256
    assert outcome.first_improving_candidate_ordinal is None
    payload = pilot.result_payload(outcome)
    assert payload["CANONICAL_EXACT_EVALUATIONS"] == 505
    assert payload["READY_FOR_NEXT_EXPANSION_REVIEW"] == "NO"
