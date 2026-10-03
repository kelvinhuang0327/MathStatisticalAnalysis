from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from lottolab.research import b649_k20_nonfrequency_221_incidence_bridge_pilot_r1 as pilot

ROOT = Path(__file__).resolve().parents[2]
SOURCE_RESULT = (
    ROOT
    / "docs/research/matrix-native-results/"
    / "b649-k20-exact-two-ticket-joint-replacement-terminal-r1.json"
)
RESULT_ARTIFACT = (
    ROOT
    / "docs/research/matrix-native-results/"
    / "b649-k20-nonfrequency-221-incidence-bridge-pilot-r1-result.json"
)


def start_portfolio() -> pilot.Portfolio:
    source = json.loads(SOURCE_RESULT.read_text(encoding="utf-8"))
    return pilot.normalize_portfolio(source["TICKETS"])


def test_start_identity_and_seven_endpoint_structure() -> None:
    source = json.loads(SOURCE_RESULT.read_text(encoding="utf-8"))
    start = start_portfolio()
    assert source["FINAL_EXACT_COUNT"] == pilot.START_COUNT
    assert source["PORTFOLIO_SHA256"] == pilot.START_SHA256
    assert pilot.portfolio_sha256(start) == pilot.START_SHA256

    candidates = pilot.build_candidates(start)
    assert tuple(candidate.z for candidate in candidates) == pilot.Z_VALUES
    assert len({candidate.sha256 for candidate in candidates}) == 7
    start_frequencies = Counter(number for ticket in start for number in ticket)
    assert Counter(start_frequencies.values()) == pilot.EXPECTED_FREQUENCY_HISTOGRAM
    for candidate in candidates:
        changed = tuple(
            index
            for index, (before, after) in enumerate(
                zip(start, candidate.slot_ordered_portfolio, strict=True)
            )
            if before != after
        )
        assert changed == (0, 1, 3)
        assert candidate.portfolio == tuple(sorted(candidate.slot_ordered_portfolio))
        assert len(candidate.portfolio) == 20
        assert len(set(candidate.portfolio)) == 20
        candidate_frequencies = Counter(
            number for ticket in candidate.portfolio for number in ticket
        )
        assert candidate_frequencies.get(3) == 2
        assert candidate_frequencies.get(candidate.z) == 3
        assert Counter(candidate_frequencies.values()) == pilot.EXPECTED_FREQUENCY_HISTOGRAM


def test_z12_witness_hash_and_tickets() -> None:
    witness = pilot.build_candidates(start_portfolio())[0]
    assert witness.sha256 == "d2003d98e700a30cfafc1b377e85052c9f5d5112dd0865ee8be3a951724eaef5"
    assert witness.slot_ordered_portfolio[0] == (1, 12, 22, 41, 42, 45)
    assert witness.slot_ordered_portfolio[1] == (1, 2, 17, 30, 34, 43)
    assert witness.slot_ordered_portfolio[3] == (4, 10, 15, 26, 27, 33)


def test_canonical_evaluator_uses_official_any_prize_count(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = 81

    def fake_evaluate(_portfolio: pilot.Portfolio, *, draws: np.ndarray) -> SimpleNamespace:
        assert draws.size == 0
        return SimpleNamespace(official_any_prize_outcome_count=expected, proxy=999)

    monkeypatch.setattr(pilot, "evaluate_portfolio", fake_evaluate)
    assert pilot.canonical_exact_count(start_portfolio(), np.array([], dtype=np.uint64)) == expected


def test_strict_improvement_confirms_once_and_stops_at_first_z() -> None:
    start = start_portfolio()
    candidates = pilot.build_candidates(start)
    candidate_counts = {candidate.sha256: pilot.START_COUNT for candidate in candidates}
    candidate_counts[candidates[0].sha256] += 1
    calls: list[str] = []

    def count(portfolio: pilot.Portfolio) -> int:
        sha = pilot.portfolio_sha256(portfolio)
        calls.append(sha)
        if sha == pilot.START_SHA256:
            return pilot.START_COUNT
        return candidate_counts[sha]

    result = pilot.run_pilot(
        start,
        recorded_start_sha256=pilot.START_SHA256,
        recorded_start_count=pilot.START_COUNT,
        source_result_sha256="a" * 64,
        count_portfolio=count,
    )
    assert result.pilot_result == "IMPROVEMENT_FOUND"
    assert result.first_improving_z == 12
    assert result.fresh_recount == "PASS"
    assert result.canonical_exact_evaluations == 3
    assert result.best_count == pilot.START_COUNT + 1
    assert result.best_delta == 1
    assert result.best_portfolio == candidates[0].portfolio
    assert calls == [pilot.START_SHA256, candidates[0].sha256, candidates[0].sha256]
    assert len(result.endpoint_scores) == 1


def test_no_improvement_evaluates_only_the_frozen_seven() -> None:
    start = start_portfolio()
    calls: list[str] = []

    def count(portfolio: pilot.Portfolio) -> int:
        calls.append(pilot.portfolio_sha256(portfolio))
        return pilot.START_COUNT

    result = pilot.run_pilot(
        start,
        recorded_start_sha256=pilot.START_SHA256,
        recorded_start_count=pilot.START_COUNT,
        source_result_sha256="b" * 64,
        count_portfolio=count,
    )
    assert result.pilot_result == "NO_IMPROVEMENT"
    assert result.canonical_exact_evaluations == 8
    assert result.best_count == pilot.START_COUNT
    assert result.best_delta == 0
    assert result.best_portfolio_sha256 == pilot.START_SHA256
    assert result.first_improving_z is None
    assert result.fresh_recount == "NOT_REQUIRED"
    assert result.ready_for_next_expansion_review == "NO"
    assert tuple(score.z for score in result.endpoint_scores) == pilot.Z_VALUES
    assert calls == [pilot.START_SHA256, *(candidate.sha256 for candidate in result.candidates)]


def test_start_mismatch_stops_before_exact_evaluation() -> None:
    calls = 0

    def count(_portfolio: pilot.Portfolio) -> int:
        nonlocal calls
        calls += 1
        return pilot.START_COUNT

    with pytest.raises(ValueError, match="START_IDENTITY_MISMATCH"):
        pilot.run_pilot(
            start_portfolio(),
            recorded_start_sha256="0" * 64,
            recorded_start_count=pilot.START_COUNT,
            source_result_sha256="c" * 64,
            count_portfolio=count,
        )
    assert calls == 0


def test_result_artifact_matches_frozen_evaluation_contract() -> None:
    artifact = json.loads(RESULT_ARTIFACT.read_text(encoding="utf-8"))
    assert hashlib.sha256(SOURCE_RESULT.read_bytes()).hexdigest() == artifact[
        "SOURCE_RESULT_SHA256"
    ]
    assert artifact["TASK_ID"] == pilot.TASK_ID
    assert artifact["START_COUNT"] == pilot.START_COUNT
    assert artifact["START_SHA256"] == pilot.START_SHA256
    assert artifact["LEGAL_ENDPOINTS"] == 7
    assert artifact["Z_ORDER"] == list(pilot.Z_VALUES)
    assert artifact["WITNESS_SHA256"] == pilot.WITNESS_SHA256
    assert artifact["CANONICAL_EXACT_EVALUATIONS"] <= pilot.MAX_CANONICAL_EXACT_EVALUATIONS
    scores = artifact["ENDPOINT_SCORES"]
    candidates = pilot.build_candidates(start_portfolio())
    assert tuple(score["Z"] for score in scores) == tuple(
        z for z in pilot.Z_VALUES[: len(scores)]
    )
    for score, candidate in zip(scores, candidates[: len(scores)], strict=True):
        assert score["SHA256"] == candidate.sha256
        assert score["DELTA"] == score["OFFICIAL_ANY_PRIZE_OUTCOME_COUNT"] - pilot.START_COUNT
    expected_evaluations = 1 + len(scores) + (artifact["FRESH_RECOUNT"] == "PASS")
    assert artifact["CANONICAL_EXACT_EVALUATIONS"] == expected_evaluations
    if artifact["PILOT_RESULT"] == "NO_IMPROVEMENT":
        assert len(scores) == 7
        assert artifact["BEST_COUNT"] == pilot.START_COUNT
        assert artifact["BEST_DELTA"] == 0
        assert artifact["BEST_PORTFOLIO_SHA256"] == pilot.START_SHA256
        assert artifact["FIRST_IMPROVING_Z"] is None
        assert artifact["READY_FOR_NEXT_EXPANSION_REVIEW"] == "NO"
    else:
        assert artifact["PILOT_RESULT"] == "IMPROVEMENT_FOUND"
        best = pilot.normalize_portfolio(artifact["BEST_PORTFOLIO"])
        assert pilot.portfolio_sha256(best) == artifact["BEST_PORTFOLIO_SHA256"]
        assert artifact["BEST_COUNT"] > pilot.START_COUNT
        assert artifact["BEST_DELTA"] == artifact["BEST_COUNT"] - pilot.START_COUNT
        assert artifact["FRESH_RECOUNT"] == "PASS"
        assert artifact["READY_FOR_NEXT_EXPANSION_REVIEW"] == "YES"
