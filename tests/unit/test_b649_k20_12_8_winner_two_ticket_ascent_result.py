"""Focused contract checks for the sealed 12+8 two-ticket ascent result."""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from itertools import combinations
from math import comb
from pathlib import Path
from typing import Any, cast

RESULT_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs/research/matrix-native-results"
    / "b649-k20-12-8-winner-two-ticket-ascent-r1-result.json"
)
START_COUNT = 313_263_888
START_ARTIFACT_SHA256 = "10d4ef5102ad824fb2c96503501694bef3f878504c8c164698c86f2f1ce35a3b"
START_NORMALIZED_SHA256 = "eaed652900d101881b678a1515d2a366bff9de6723dbec2ec9c82fe0d0d7844c"


def _load_result() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(RESULT_PATH.read_text(encoding="utf-8")))


def _compact_sha256(tickets: list[list[int]]) -> str:
    payload = json.dumps(tickets, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def test_start_artifact_hashes_and_ticket_multiset_are_preserved() -> None:
    result = _load_result()
    start_tickets = result["START_TICKETS"]
    search_tickets = result["SEARCH_START_TICKETS"]

    assert result["START_COUNT"] == START_COUNT
    assert result["START_ARTIFACT_SHA256"] == START_ARTIFACT_SHA256
    assert result["START_NORMALIZED_ENGINE_SHA256"] == START_NORMALIZED_SHA256
    assert result["START_TICKET_MULTISET_IDENTITY"] == "PASS"
    assert len(start_tickets) == len(search_tickets) == 20
    assert len({tuple(ticket) for ticket in start_tickets}) == 20
    assert {tuple(ticket) for ticket in start_tickets} == {
        tuple(ticket) for ticket in search_tickets
    }
    assert _compact_sha256(start_tickets) == START_ARTIFACT_SHA256
    assert _compact_sha256(search_tickets) == START_NORMALIZED_SHA256


def test_terminal_neighborhood_accounts_for_every_slot_pair() -> None:
    result = _load_result()
    accounting = result["TERMINAL_190_PAIR_ACCOUNTING"]
    pairs = accounting["TERMINAL_PAIRS"]
    expected_pairs = set(combinations(range(20), 2))
    observed_pairs = {tuple(pair["SLOT_PAIR"]) for pair in pairs}

    assert accounting["STATUS"] == "PASS"
    assert accounting["EXPECTED_PAIR_COUNT"] == 190
    assert accounting["COMPLETE_PAIR_COUNT"] == 190
    assert accounting["PENDING_PAIRS"] == []
    assert accounting["UNKNOWN_PAIRS"] == []
    assert len(pairs) == len(observed_pairs) == 190
    assert observed_pairs == expected_pairs
    assert accounting["BEST_DELTA"] <= 0
    assert max(pair["BEST_DELTA"] for pair in pairs) == accounting["BEST_DELTA"]
    assert all(pair["ACCOUNTING"] == "PASS" for pair in pairs)
    assert all(pair["TICKET_INVARIANT"] == "PASS" for pair in pairs)
    assert all(pair["PAIR_INVARIANT"] == "PASS" for pair in pairs)


def test_move_arithmetic_final_hash_and_classification_are_consistent() -> None:
    result = _load_result()
    current_count = START_COUNT
    moves = result["ACCEPTED_MOVES"]

    for move in moves:
        assert move["OLD_COUNT"] == current_count
        assert move["DELTA"] > 0
        assert move["NEW_COUNT"] == current_count + move["DELTA"]
        assert move["G2_CANONICAL_RECOMPUTE"] == "PASS"
        current_count = move["NEW_COUNT"]

    final_tickets = result["FINAL_TICKETS"]
    assert current_count == result["FINAL_COUNT"]
    assert result["TOTAL_DELTA"] == current_count - START_COUNT
    assert result["TOTAL_DELTA"] == sum(move["DELTA"] for move in moves)
    assert len(final_tickets) == len({tuple(ticket) for ticket in final_tickets}) == 20
    assert all(len(ticket) == len(set(ticket)) == 6 for ticket in final_tickets)
    assert all(ticket == sorted(ticket) for ticket in final_tickets)
    assert all(1 <= number <= 49 for ticket in final_tickets for number in ticket)
    assert result["FINAL_SHA256"] == _compact_sha256(final_tickets)
    assert result["FINAL_ENGINE_NORMALIZED_SHA256"] == result["FINAL_SHA256"]
    expected_fraction = Fraction(current_count, comb(49, 6) * (49 - 6))
    assert result["FINAL_EXACT_FRACTION"] == str(expected_fraction)
    assert result["TWO_TICKET_LOCAL_OPTIMUM_STATUS"] == (
        "PROVEN_FOR_VALIDATED_EXACT_TWO_TICKET_NEIGHBORHOOD"
    )
    if moves:
        assert result["N1_N2_COMBINED_LOCAL_STATUS"] == "NOT_ESTABLISHED"
        assert result["READY_FOR_SINGLE_TICKET_RECHECK"] == "YES"
    else:
        assert result["N1_N2_COMBINED_LOCAL_STATUS"] == (
            "PROVEN_FOR_VALIDATED_N1_AND_N2_NEIGHBORHOODS"
        )
        assert result["READY_FOR_SINGLE_TICKET_RECHECK"] == "NO"
