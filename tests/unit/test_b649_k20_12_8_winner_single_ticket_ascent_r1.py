from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from lottolab.research import b649_k20_bonferroni_filtered_exhaustive_2ticket_cross_swap_r1 as u3
from lottolab.research import b649_official_any_prize_exact as canonical

RESULT_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "research"
    / "matrix-native-results"
    / "b649-k20-12-8-winner-single-ticket-ascent-r1-result.json"
)


def load_result() -> dict[str, Any]:
    return json.loads(RESULT_PATH.read_text(encoding="utf-8"))


def compact_sha256(value: object) -> str:
    encoded = json.dumps(value, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def test_start_and_final_portfolio_identities() -> None:
    result = load_result()
    start: list[list[int]] = result["START_TICKETS"]
    search_start: list[list[int]] = result["SEARCH_START_TICKETS"]
    final: list[list[int]] = result["FINAL_TICKETS"]

    assert len(start) == len(set(map(tuple, start))) == 20
    assert all(
        len(ticket) == 6
        and ticket == sorted(set(ticket))
        and all(1 <= number <= 49 for number in ticket)
        for ticket in start
    )
    assert compact_sha256(start) == result["START_SHA256"]
    assert result["START_SHA256"] == (
        "10d4ef5102ad824fb2c96503501694bef3f878504c8c164698c86f2f1ce35a3b"
    )
    assert {tuple(ticket) for ticket in start} == {
        tuple(ticket) for ticket in search_start
    }
    normalized_start = u3.normalize_portfolio(start, expected_ticket_count=20)
    assert u3.portfolio_sha256(normalized_start) == result[
        "START_ENGINE_NORMALIZED_SHA256"
    ]

    assert {tuple(ticket) for ticket in final} == {tuple(ticket) for ticket in start}
    assert compact_sha256(final) == result["FINAL_SHA256"]
    normalized_final = u3.normalize_portfolio(final, expected_ticket_count=20)
    assert u3.portfolio_sha256(normalized_final) == result[
        "FINAL_ENGINE_NORMALIZED_SHA256"
    ]


def test_canonical_terminal_recount_matches_result() -> None:
    result = load_result()
    draws = canonical.all_main_draw_masks(49, 6)
    score = canonical.evaluate_portfolio(result["FINAL_TICKETS"], draws=draws)

    assert score.official_any_prize_outcome_count == result["FINAL_COUNT"]
    assert str(score.official_any_prize) == result["FINAL_EXACT_FRACTION"]
    assert result["CANONICAL_RESCORE"]["STATUS"] == "PASS"
    assert result["CANONICAL_RESCORE"]["TERMINAL_COUNT"] == result["FINAL_COUNT"]


def test_complete_terminal_neighborhood_has_no_positive_move() -> None:
    result = load_result()
    accounting = result["TERMINAL_NEIGHBORHOOD_ACCOUNTING"]
    per_ticket = math.comb(49, 6)
    expected_moves = 20 * per_ticket

    assert result["SINGLE_TICKET_LOCAL_OPTIMUM_STATUS"] == (
        "PROVEN_FOR_VALIDATED_EXACT_SINGLE_TICKET_NEIGHBORHOOD"
    )
    assert accounting["CANDIDATES_PER_SLOT"] == per_ticket
    assert accounting["SLOTS"] == 20
    assert accounting["MOVES_PER_COMPLETE_NEIGHBORHOOD"] == expected_moves
    assert accounting["TOTAL_REPLACEMENT_MOVES_EVALUATED"] == expected_moves
    assert len(accounting["ITERATIONS"]) == result["ITERATIONS_COMPLETED"] == 1

    iteration = accounting["ITERATIONS"][0]
    positions = iteration["POSITION_SUMMARIES"]
    assert iteration["TERMINAL"] is True
    assert iteration["MOVES_EVALUATED"] == expected_moves
    assert iteration["CANDIDATES_EVALUATED"] == expected_moves
    assert iteration["POSITIONS_COMPLETE"] == 20
    assert [row["POSITION"] for row in positions] == list(range(20))
    assert all(row["CANDIDATES_EVALUATED"] == per_ticket for row in positions)
    assert max(row["BEST_DELTA_OUTCOME_COUNT"] for row in positions) == 0
    assert iteration["BEST_DELTA_OUTCOME_COUNT"] == 0


def test_move_accounting_and_canonical_terminal_receipts() -> None:
    result = load_result()
    moves = result["ACCEPTED_MOVES"]
    assert len(moves) == result["ACCEPTED_MOVES_TOTAL"] == 0
    assert result["FINAL_COUNT"] - result["START_COUNT"] == result["TOTAL_DELTA"] == 0

    prior_count = result["START_COUNT"]
    for move in moves:
        assert move["OLD_COUNT"] == prior_count
        assert move["DELTA"] > 0
        assert move["NEW_COUNT"] - move["OLD_COUNT"] == move["DELTA"]
        assert move["CANONICAL_RECOUNT_PARITY"]["STATUS"] == "PASS"
        prior_count = move["NEW_COUNT"]
    assert prior_count == result["FINAL_COUNT"]

    accounting = result["TERMINAL_NEIGHBORHOOD_ACCOUNTING"]
    position_rows = accounting["ITERATIONS"][-1]["POSITION_SUMMARIES"]
    canonical_rows = accounting["TERMINAL_TOP_REPLACEMENT_CANONICAL_CHECKS"]
    assert len(canonical_rows) == 20
    assert all(row["MATCH"] for row in canonical_rows)
    assert {
        row["POSITION"]: row["TOP_ENGINE_OUTCOME_COUNT"] for row in position_rows
    } == {row["POSITION"]: row["ENGINE_OUTCOME_COUNT"] for row in canonical_rows}
    assert all(
        row["ENGINE_OUTCOME_COUNT"] == row["CANONICAL_OUTCOME_COUNT"]
        for row in canonical_rows
    )


def test_engine_identity_tie_break_and_seeded_parity_sample() -> None:
    result = load_result()
    engine = result["ENGINE_AUTHORITY"]
    verification = result["VERIFICATION"]

    assert engine["DRIVER_SHA256"] == (
        "043a0f35a5ff7246d8f9409a8a4250d8f623c9d95f5e290b6c05eabebba59c67"
    )
    assert engine["ENGINE_SOURCE_SHA256"] == (
        "1ef595c57d81b63c56635d3172af66165a978c13edf3eff944466d8a44fd4bec"
    )
    assert engine["ENGINE_BINARY_SHA256"] == (
        "808b06595768d1ec59d9f7550217741907ffb9d3f08a2a6db162b37cc8096df2"
    )
    assert "lowest SHA256" in engine["TIE_BREAK"]
    assert verification["G1"]["STATUS"] == "PASS"
    assert all(verification["G1"]["CHECKS"].values())
    assert verification["G3"]["STATUS"] == "PASS"
    assert verification["G3"]["POSITIONS_CHECKED"] == 20
    sample = verification["G4"]
    assert sample["STATUS"] == "PASS"
    assert sample["SAMPLE_COUNT"] == 200
    assert sample["MISMATCHES"] == 0
    records = json.loads(sample["RECORDS_COMPACT_JSON"])
    assert len(records) == 200
    assert hashlib.sha256(sample["RECORDS_COMPACT_JSON"].encode()).hexdigest() == sample[
        "RECORDS_SHA256"
    ]
    assert all(record["MATCH"] for record in records)
    assert all(
        record["ENGINE_OUTCOME_COUNT"] == record["CANONICAL_OUTCOME_COUNT"]
        for record in records
    )
    assert result["GLOBAL_K20_OPTIMUM_STATUS"] == "UNKNOWN"
