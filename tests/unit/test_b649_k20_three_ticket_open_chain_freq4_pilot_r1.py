from __future__ import annotations

import json
from collections.abc import Sequence
from typing import cast

import pytest

from lottolab.research import b649_k20_three_ticket_open_chain_freq4_pilot_r1 as pilot


def test_start_identity_and_all_21_endpoints() -> None:
    start = pilot.load_start_portfolio()
    assert pilot.portfolio_sha256(start) == pilot.START_SHA256

    candidates = pilot.build_candidate_family(start)
    assert tuple(candidate.y for candidate in candidates) == pilot.Y_VALUES
    assert len(candidates) == 21
    assert len({candidate.portfolio_sha256 for candidate in candidates}) == 21
    assert candidates[0].portfolio[0] == (1, 33, 34, 41, 42, 45)
    assert candidates[0].portfolio[1] == (1, 4, 17, 22, 30, 43)
    assert candidates[0].portfolio[3] == (2, 4, 10, 15, 26, 27)
    assert candidates[0].portfolio_sha256 == pilot.WITNESS_SHA256


def test_canonical_score_uses_named_evaluator(monkeypatch: pytest.MonkeyPatch) -> None:
    start = pilot.load_start_portfolio()
    observed: list[Sequence[Sequence[int]]] = []

    class FakeOutcome:
        official_any_prize_outcome_count = 123

    def fake_evaluate(portfolio: Sequence[Sequence[int]]) -> FakeOutcome:
        observed.append(portfolio)
        return FakeOutcome()

    monkeypatch.setattr(pilot, "evaluate_portfolio", fake_evaluate)
    assert pilot.canonical_official_any_prize_count(start) == 123
    assert observed == [start]
    assert pilot.EVALUATOR_AUTHORITY == (
        "src/lottolab/research/b649_official_any_prize_exact.py"
    )


def test_early_stop_and_fresh_recount() -> None:
    start = pilot.load_start_portfolio()
    scores = iter(
        (
            pilot.START_COUNT,
            pilot.START_COUNT - 1,
            pilot.START_COUNT + 7,
            pilot.START_COUNT + 7,
        )
    )
    scored_portfolios: list[str] = []

    def scorer(portfolio: pilot.Portfolio) -> int:
        scored_portfolios.append(pilot.portfolio_sha256(portfolio))
        return next(scores)

    result = pilot.execute_pilot(start, scorer)
    evaluation_rows = cast(list[dict[str, int | str]], result["EVALUATIONS"])
    candidate_rows = [row for row in evaluation_rows if row["KIND"] == "CANDIDATE"]
    assert [row["Y"] for row in candidate_rows] == [4, 6]
    assert [row["KIND"] for row in evaluation_rows] == [
        "START",
        "CANDIDATE",
        "CANDIDATE",
        "FRESH_RECOUNT",
    ]
    assert scored_portfolios[-1] == scored_portfolios[-2]
    assert result["CANONICAL_EXACT_EVALUATIONS"] == 4
    assert result["PILOT_RESULT"] == "IMPROVEMENT_FOUND"
    assert result["FIRST_IMPROVING_Y"] == 6
    assert result["FRESH_RECOUNT"] == "PASS"
    assert result["BEST_COUNT"] == pilot.START_COUNT + 7


def test_no_improvement_result_and_serialized_artifact() -> None:
    start = pilot.load_start_portfolio()
    calls = 0

    def scorer(_: pilot.Portfolio) -> int:
        nonlocal calls
        calls += 1
        return pilot.START_COUNT

    result = pilot.execute_pilot(start, scorer)
    artifact = json.loads(pilot.serialize_result(result))
    assert calls == 22
    assert artifact["CANONICAL_EXACT_EVALUATIONS"] == 22
    assert artifact["PILOT_RESULT"] == "NO_IMPROVEMENT"
    assert artifact["BEST_COUNT"] == pilot.START_COUNT
    assert artifact["BEST_DELTA"] == 0
    assert artifact["BEST_PORTFOLIO_SHA256"] == pilot.START_SHA256
    assert artifact["FIRST_IMPROVING_Y"] is None
    assert artifact["FRESH_RECOUNT"] == "NOT_REQUIRED"
    assert artifact["READY_FOR_NEXT_EXPANSION_REVIEW"] == "NO"
    assert len(artifact["BEST_PORTFOLIO"]) == 20


def test_start_mismatch_stops_before_scoring() -> None:
    start = [*pilot.load_start_portfolio()]
    start[0] = (1, 2, 3, 4, 5, 6)
    calls = 0

    def scorer(_: pilot.Portfolio) -> int:
        nonlocal calls
        calls += 1
        return pilot.START_COUNT

    with pytest.raises(RuntimeError, match="START_IDENTITY_MISMATCH"):
        pilot.execute_pilot(start, scorer)
    assert calls == 0
