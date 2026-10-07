"""Focused check for the sealed F2-rewire winner single-ticket N1 ascent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from lottolab.research.b649_k20_12_8_component_internal_f2_rewire_r1 import (
    portfolio_sha256,
)
from lottolab.research.b649_official_any_prize_exact import evaluate_portfolio

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_FILE = (
    REPO_ROOT
    / "docs/research/matrix-native-results"
    / "b649-k20-f2-rewire-winner-single-ticket-ascent-r1-result.json"
)


def _tickets(record: dict[str, Any]) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(ticket) for ticket in record["TICKETS"])


def test_sealed_n1_result_matches_canonical_evaluator() -> None:
    result = cast(dict[str, Any], json.loads(RESULT_FILE.read_text(encoding="utf-8")))
    start = result["START"]
    final = result["FINAL"]
    start_tickets = _tickets(start)
    final_tickets = _tickets(final)

    assert (
        evaluate_portfolio(start_tickets).official_any_prize_outcome_count
        == start["OFFICIAL_ANY_PRIZE_OUTCOME_COUNT"]
    )
    assert (
        evaluate_portfolio(final_tickets).official_any_prize_outcome_count
        == final["OFFICIAL_ANY_PRIZE_OUTCOME_COUNT"]
    )
    assert portfolio_sha256(start_tickets) == start["NORMALIZED_SHA256"]
    assert portfolio_sha256(final_tickets) == final["NORMALIZED_SHA256"]
    assert result["TERMINAL_BEST_DELTA"] <= 0
    accepted = result["ACCEPTED_MOVE_COUNT"]
    assert result["READY_FOR_TWO_TICKET_ASCENT"] == ("YES" if accepted > 0 else "NO")
    assert result["GLOBAL_K20_OPTIMUM_STATUS"] == "UNKNOWN"
