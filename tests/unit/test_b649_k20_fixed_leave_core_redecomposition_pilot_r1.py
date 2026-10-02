"""Focused invariants for the fixed-leave K20 redecomposition pilot."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast

from lottolab.research import (
    b649_k20_fixed_leave_core_redecomposition_pilot_r1 as pilot,
)
from lottolab.research import (
    b649_official_any_prize_exact as exact,
)


def _read_result() -> dict[str, object]:
    return cast(dict[str, object], json.loads(pilot.RESULT_PATH.read_text(encoding="utf-8")))


def test_incumbent_labeling_reconstructs_the_frozen_start_bytes() -> None:
    mapping = pilot.map_labels(pilot.INCUMBENT_DECOMPOSITION)

    assert mapping == pilot.INCUMBENT_LABEL_TRIANGLES
    rebuilt = pilot.reconstruct_portfolio(pilot.INCUMBENT_DECOMPOSITION)
    assert rebuilt == pilot.START_TICKETS
    assert pilot.canonical_portfolio_sha256(rebuilt) == pilot.EXPECTED_START_SHA256


def test_regenerated_combinatorics_and_candidate_order_match_the_result_artifact() -> None:
    combinatorics = pilot.regenerate_combinatorics()
    candidates = pilot.generate_candidates(combinatorics)
    artifact = _read_result()

    assert len(combinatorics.decompositions) == pilot.EXPECTED_DECOMPOSITIONS
    assert len(combinatorics.symmetry_group) == pilot.EXPECTED_SYMMETRY_ORDER
    assert len(combinatorics.representatives) == pilot.EXPECTED_CLASS_COUNT
    assert dict(combinatorics.class_size_histogram) == pilot.EXPECTED_CLASS_SIZE_HISTOGRAM
    assert len(candidates) == pilot.EXPECTED_CANDIDATES
    assert artifact["REGENERATED_TRIANGLE_DECOMPOSITIONS"] == pilot.EXPECTED_DECOMPOSITIONS
    assert artifact["SYMMETRY_GROUP_ORDER"] == pilot.EXPECTED_SYMMETRY_ORDER
    assert artifact["REGENERATED_SYMMETRY_CLASSES"] == pilot.EXPECTED_CLASS_COUNT
    assert artifact["CLASS_SIZE_HISTOGRAM"] == {"240": 6, "480": 14, "960": 242}
    assert artifact["LABELED_NON_INCUMBENT_CLASSES"] == pilot.EXPECTED_CANDIDATES
    assert artifact["FIXED_LEAVE_EDGES"] == [list(edge) for edge in pilot.FIXED_LEAVE_EDGES]
    assert combinatorics.incumbent_representative not in {
        candidate.representative for candidate in candidates
    }
    assert [candidate.representative for candidate in candidates] == sorted(
        candidate.representative for candidate in candidates
    )
    assert len({candidate.portfolio_sha256 for candidate in candidates}) == len(candidates)
    for candidate in candidates:
        assert len(candidate.tickets) == 20
        assert all(
            len(ticket) == 6 and tuple(sorted(set(ticket))) == ticket
            for ticket in candidate.tickets
        )

    score_rows = cast(list[list[object]], artifact["CANDIDATE_SCORES"])
    expected_order = [
        [candidate.representative_sha256, candidate.portfolio_sha256]
        for candidate in candidates
    ]
    assert [row[:2] for row in score_rows] == expected_order
    order_bytes = json.dumps([row[0] for row in score_rows], separators=(",", ":")).encode(
        "utf-8"
    )
    ledger_bytes = json.dumps(score_rows, separators=(",", ":")).encode("utf-8")
    assert artifact["CANDIDATE_ORDER_SHA256"] == hashlib.sha256(order_bytes).hexdigest()
    assert artifact["CANDIDATE_SCORE_LEDGER_SHA256"] == hashlib.sha256(ledger_bytes).hexdigest()


def test_result_decision_and_exact_evaluator_authority_are_consistent() -> None:
    artifact = _read_result()
    assert pilot.evaluate_portfolio is exact.evaluate_portfolio
    assert artifact["CANONICAL_EVALUATOR"] == (
        "lottolab.research.b649_official_any_prize_exact.evaluate_portfolio"
    )
    assert artifact["START_COUNT"] == pilot.EXPECTED_START_COUNT
    assert artifact["START_SHA256"] == pilot.EXPECTED_START_SHA256
    assert artifact["INCUMBENT_BYTE_REPRODUCTION"] == "PASS"
    assert artifact["STRUCTURAL_INVARIANTS"] == "PASS"

    rows = cast(list[list[object]], artifact["CANDIDATE_SCORES"])
    assert len(rows) == pilot.EXPECTED_CANDIDATES
    assert all(len(row) == 3 and type(row[2]) is int for row in rows)
    counts = [cast(int, row[2]) for row in rows]
    highest = max(counts)
    assert artifact["CANONICAL_EXACT_EVALUATIONS"] in (262, 263)
    if highest <= pilot.EXPECTED_START_COUNT:
        assert artifact["PILOT_RESULT"] == "NO_IMPROVEMENT"
        assert artifact["BEST_COUNT"] == pilot.EXPECTED_START_COUNT
        assert artifact["BEST_DELTA"] == 0
        assert artifact["BEST_PORTFOLIO_SHA256"] == pilot.EXPECTED_START_SHA256
        assert artifact["FRESH_RECOUNT"] == "NOT_REQUIRED"
        assert artifact["READY_FOR_NEXT_EXPANSION_REVIEW"] == "NO"
        assert artifact["CANONICAL_EXACT_EVALUATIONS"] == 262
    else:
        winning_sha = min(
            cast(str, row[1]) for row in rows if cast(int, row[2]) == highest
        )
        assert artifact["PILOT_RESULT"] == "IMPROVEMENT_FOUND"
        assert artifact["BEST_COUNT"] == highest
        assert artifact["BEST_DELTA"] == highest - pilot.EXPECTED_START_COUNT
        assert artifact["BEST_PORTFOLIO_SHA256"] == winning_sha
        assert artifact["FRESH_RECOUNT"] == "PASS"
        assert artifact["READY_FOR_NEXT_EXPANSION_REVIEW"] == "YES"
        assert artifact["CANONICAL_EXACT_EVALUATIONS"] == 263


def test_result_artifact_exists_at_the_frozen_output_path() -> None:
    expected_path = (
        Path(__file__).resolve().parents[2]
        / "docs/research/matrix-native-results/"
        "b649-k20-fixed-leave-core-redecomposition-pilot-r1-result.json"
    )
    assert pilot.RESULT_PATH.samefile(expected_path)
    assert pilot.RESULT_PATH.is_file()
