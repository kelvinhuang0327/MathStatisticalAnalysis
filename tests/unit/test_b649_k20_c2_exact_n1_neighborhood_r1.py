from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from lottolab.research import b649_k20_bonferroni_filtered_exhaustive_2ticket_cross_swap_r1 as u3
from lottolab.research import b649_official_any_prize_exact as canonical

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_PATH = (
    REPO_ROOT
    / "docs"
    / "research"
    / "matrix-native-results"
    / "b649-k20-c2-exact-n1-neighborhood-r1-result.json"
)
C2_SOURCE_PATH = (
    REPO_ROOT
    / "docs"
    / "research"
    / "matrix-native-results"
    / "b649-cell-a-c2-independent-recount-r1.json"
)
START_COUNT = 313_263_888


def load_result() -> dict[str, Any]:
    return json.loads(RESULT_PATH.read_text(encoding="utf-8"))


def compact_sha256(value: object) -> str:
    return hashlib.sha256(json.dumps(value, separators=(",", ":")).encode()).hexdigest()


def test_start_is_the_pinned_c2_portfolio_not_c4() -> None:
    result = load_result()
    start = result["START"]
    source_raw = C2_SOURCE_PATH.read_bytes()
    source = json.loads(source_raw)

    assert (
        hashlib.sha256(source_raw).hexdigest()
        == start["ARTIFACT_FILE_SHA256"]
        == ("0e2391f738ce68782f117b299a393506990014ded77d4b48878f1423f7e4a095")
    )
    tickets: list[list[int]] = start["TICKETS_ORDERED"]
    assert tickets == source["C2"]["full_portfolio"]
    assert (
        compact_sha256(tickets)
        == start["ORDERED_SHA256"]
        == ("6a537ea56c2741e1208dbbb4abf1064bc74508f2d356712920d348d11e3a4a24")
    )
    normalized = u3.normalize_portfolio(tickets, expected_ticket_count=20)
    assert (
        u3.portfolio_sha256(normalized)
        == start["SORTED_SHA256"]
        == ("2372afa39eea13bc3f31788a4e1f11166663da85580c0bd50c8064f2f96929a5")
    )
    assert (
        start["CANONICAL_CLASS_ID"]
        == start["CANONICAL_CLASS_ID_RECOMPUTED"]
        == ("e4b1941183c0583d479c1467d7ce9aadf164190a07734ec592a8cf6f45ee07d7")
    )
    assert start["CANONICAL_CLASS_ID"] != source["C4"]["canonical_id"]
    assert start["CANONICAL_RECOUNT"] == start["ENGINE_RECOUNT"] == START_COUNT


def test_full_unrestricted_neighborhood_is_accounted() -> None:
    result = load_result()
    accounting = result["NEIGHBORHOOD_ACCOUNTING"]
    per_slot = math.comb(49, 6)
    universe = 20 * per_slot

    assert accounting["RAW_REPLACEMENT_UNIVERSE"] == universe == 279_676_320
    assert accounting["EXACTLY_SCORED_CANDIDATES"] == universe
    assert accounting["FULLY_ACCOUNTED_CANDIDATES"] == universe
    assert accounting["SOUNDLY_PRUNED_CANDIDATES"] == 0
    assert accounting["UNFINISHED_CANDIDATES"] == 0
    assert accounting["IDENTITY_MOVES_SCORED_DELTA_ZERO"] == 20
    assert accounting["DUPLICATE_TICKET_MOVES_SCORED_ILLEGAL"] == 380
    assert accounting["LEGAL_NON_IDENTITY_MOVES"] == universe - 400
    positions = result["POSITION_SUMMARIES"]
    assert [row["POSITION"] for row in positions] == list(range(20))
    assert all(row["CANDIDATES_EVALUATED"] == per_slot for row in positions)
    assert sum(row["COUNT_STRICTLY_IMPROVING_MOVES"] for row in positions) == 0
    assert accounting["COUNT_STRICTLY_IMPROVING_MOVES"] == 0


def test_best_delta_and_deterministic_tie_break() -> None:
    result = load_result()
    positions = result["POSITION_SUMMARIES"]
    best_delta = max(row["BEST_DELTA_OUTCOME_COUNT"] for row in positions)
    tied = [row for row in positions if row["BEST_DELTA_OUTCOME_COUNT"] == best_delta]
    chosen = min(tied, key=lambda row: row["TOP_RESULTING_PORTFOLIO_SHA256"])

    assert result["BEST_DELTA"] == best_delta == 0
    assert result["BEST_EXACT_COUNT"] == START_COUNT
    assert result["BEST_IS_GAIN"] is False
    assert result["WINNER"] is None
    assert result["CANONICAL_WINNER_RECOUNT"] == "NOT_APPLICABLE_NO_POSITIVE_DELTA"
    assert result["BEST_POSITION"] == chosen["POSITION"]
    assert result["BEST_ADDED_TICKET"] == chosen["TOP_ADDED_TICKET"]
    assert result["BEST_NORMALIZED_SHA256"] == chosen["TOP_RESULTING_PORTFOLIO_SHA256"]

    # Positions index the normalized (sorted) START portfolio.
    start = u3.normalize_portfolio(result["START"]["TICKETS_ORDERED"], expected_ticket_count=20)
    assert [list(t) for t in start] == result["START"]["TICKETS_NORMALIZED"]
    best_position: int = result["BEST_POSITION"]
    assert list(start[best_position]) == result["BEST_REMOVED_TICKET"]
    neighbor = [
        result["BEST_ADDED_TICKET"] if index == best_position else list(ticket)
        for index, ticket in enumerate(start)
    ]
    assert u3.portfolio_sha256(neighbor) == result["BEST_NORMALIZED_SHA256"]
    draws = canonical.all_main_draw_masks(49, 6)
    score = canonical.evaluate_portfolio(neighbor, draws=draws)
    assert score.official_any_prize_outcome_count == result["BEST_EXACT_COUNT"]


def test_canonical_parity_gates_and_scoped_claims() -> None:
    result = load_result()
    verification = result["VERIFICATION"]
    checks = result["POSITION_TOP_CANONICAL_CHECKS"]

    assert verification["G1"] == "PASS"
    assert verification["G3_OR_POSITION_TOP_CANONICAL"] == "PASS"
    assert len(checks) == 20
    assert all(c["ENGINE_OUTCOME_COUNT"] == c["CANONICAL_OUTCOME_COUNT"] for c in checks)
    sample = verification["G4"]
    assert sample["STATUS"] == "PASS"
    assert sample["SAMPLE_COUNT"] == 200
    assert sample["MISMATCHES"] == 0
    assert (
        hashlib.sha256(sample["RECORDS_COMPACT_JSON"].encode()).hexdigest()
        == (sample["RECORDS_SHA256"])
    )
    records = json.loads(sample["RECORDS_COMPACT_JSON"])
    assert len(records) == 200
    assert all(r["ENGINE_OUTCOME_COUNT"] == r["CANONICAL_OUTCOME_COUNT"] for r in records)

    engine = result["ENGINE_AUTHORITY"]
    assert engine["ENGINE_BINARY_SHA256"] == (
        "808b06595768d1ec59d9f7550217741907ffb9d3f08a2a6db162b37cc8096df2"
    )
    assert engine["EVALUATOR_SHA256"] == (
        "92dcb836254cc6dbcd6c2ad907e619a5eb8cf3917197a8f6de3e5f989825cf66"
    )
    assert engine["C4_CACHED_RESULTS_REUSED"] is False
    assert result["N1_LOCAL_CLOSURE_STATUS"] == (
        "C2_N1_LOCAL_CLOSURE_PROVEN_FOR_EXACT_SINGLE_TICKET_REPLACEMENT_NEIGHBORHOOD_ONLY"
    )
    assert result["ITERATIONS_RUN"] == 1
    assert result["N2_STATUS"] == "NOT_RUN"
    assert result["GLOBAL_K20_OPTIMUM_STATUS"] == "UNKNOWN"
