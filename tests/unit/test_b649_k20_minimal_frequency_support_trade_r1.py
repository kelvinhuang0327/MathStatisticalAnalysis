"""Focused legality, operator coverage, exact scoring, and serialization checks."""

from __future__ import annotations

import itertools
import json
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from lottolab.research import b649_k20_minimal_frequency_support_trade_r1 as trade
from lottolab.research.b649_official_any_prize_exact import (
    ExactPortfolioProbability,
    all_main_draw_masks,
)


def synthetic(fx: int, fy: int) -> trade.Portfolio:
    return tuple(
        tuple(sorted((1 if i < fx else 2 if i < fx + fy else 30 + i, 3, 4, 5, 6, 7 + i)))
        for i in range(20)
    )


def test_baseline_identity_and_distinct_hash_conventions() -> None:
    baseline = trade.ordered_portfolio(trade.BASELINE)
    assert len(baseline) == 20
    assert trade.artifact_sha(baseline) == trade.BASELINE_ARTIFACT_SHA
    assert trade.portfolio_sha256(baseline) == trade.BASELINE_NORMALIZED_SHA
    assert trade.BASELINE_ARTIFACT_SHA != trade.BASELINE_NORMALIZED_SHA
    assert Counter(trade.frequencies(baseline)) == {3: 22, 2: 27}


@pytest.mark.parametrize(("fx", "fy", "count", "family"), [(3, 2, 3, "F3_F2"), (3, 3, 9, "F3_F3")])
def test_synthetic_exchanges_change_exactly_four_slots(
    fx: int, fy: int, count: int, family: str
) -> None:
    baseline = synthetic(fx, fy)
    candidates, accounting = trade.enumerate_family(baseline)
    assert count == accounting.RAW_OPERATOR_INSTANTIATIONS
    assert len(candidates) == count
    old_support = trade.supports(baseline)
    for candidate in candidates:
        e = candidate.exchange
        assert e.family == family
        assert (e.x, e.y) == (1, 2)
        assert len(trade.changed_slots(baseline, candidate.portfolio)) == 4
        assert trade.frequencies(candidate.portfolio) == trade.frequencies(baseline)
        assert trade.candidate_acceptance(baseline, candidate.portfolio) == "LEGAL"
        new_support = trade.supports(candidate.portfolio)
        assert set(new_support[e.x]) == (set(old_support[e.x]) - set(e.a)) | set(e.b)
        assert set(new_support[e.y]) == (set(old_support[e.y]) - set(e.b)) | set(e.a)
        assert all(old_support[n] == new_support[n] for n in range(3, 50))
    # These legal synthetic portfolios have overlaps >1, which must not be filtered.
    assert len(set(candidates[0].portfolio[0]) & set(candidates[0].portfolio[1])) > 1


def test_f2_f2_is_excluded() -> None:
    candidates, accounting = trade.enumerate_family(synthetic(2, 2))
    assert not candidates
    assert accounting.RAW_OPERATOR_INSTANTIATIONS == 0


def test_overlapping_number_supports_are_excluded() -> None:
    baseline = list(synthetic(3, 2))
    baseline[0] = (1, 2, 3, 4, 5, 7)
    assert all((e.x, e.y) != (1, 2) for e in trade.iter_exchanges(tuple(baseline)))


@pytest.mark.parametrize("change", [False, True])
def test_inert_and_two_slot_changes_are_rejected(change: bool) -> None:
    baseline = synthetic(3, 2)
    tickets = list(baseline)
    if change:
        tickets[0] = tuple(sorted((set(tickets[0]) - {1}) | {2}))
        tickets[3] = tuple(sorted((set(tickets[3]) - {2}) | {1}))
    candidate = tuple(tickets)
    assert len(trade.changed_slots(baseline, candidate)) in (0, 2)
    assert trade.candidate_acceptance(baseline, candidate) == "N1_N2_EQUIVALENT"


@pytest.mark.parametrize("kind", ["count", "duplicate", "range", "repeat", "size", "bool"])
def test_duplicate_or_illegal_portfolios_fail(kind: str) -> None:
    baseline = synthetic(3, 2)
    tickets = list(trade.enumerate_family(baseline)[0][0].portfolio)
    if kind == "count":
        tickets.pop()
    elif kind == "duplicate":
        tickets[0] = tickets[1]
    elif kind == "range":
        tickets[0] = (*tickets[0][:-1], 50)
    elif kind == "repeat":
        tickets[0] = (*tickets[0][:-1], tickets[0][0])
    elif kind == "size":
        tickets[0] = tickets[0][:-1]
    else:
        tickets[0] = (True, *tickets[0][1:])
    assert trade.candidate_acceptance(baseline, tuple(tickets)) == "ILLEGAL"
    with pytest.raises(ValueError):
        trade.ordered_portfolio(tuple(tickets))


def test_frequency_change_fails_even_when_four_slots_differ() -> None:
    baseline = synthetic(3, 2)
    tickets = list(trade.enumerate_family(baseline)[0][0].portfolio)
    changed = trade.changed_slots(baseline, tuple(tickets))
    slot = changed[0]
    tickets[slot] = tuple(sorted((set(tickets[slot]) - {3}) | {29}))
    candidate = tuple(tickets)
    assert len(trade.changed_slots(baseline, candidate)) == 4
    assert trade.candidate_acceptance(baseline, candidate) == "ILLEGAL"


def test_normalized_dedup_ignores_ticket_and_number_order() -> None:
    candidate = trade.enumerate_family(synthetic(3, 2))[0][0]
    reordered = tuple(tuple(reversed(t)) for t in reversed(candidate.portfolio))
    duplicate = replace(candidate, portfolio=reordered)
    assert trade.portfolio_sha256(reordered) == candidate.normalized_sha
    assert trade.deduplicate_candidates([candidate, duplicate]) == (candidate,)
    wrong_hash = replace(candidate, normalized_sha="0" * 64)
    with pytest.raises(AssertionError, match="identity"):
        trade.deduplicate_candidates([wrong_hash])


def test_actual_family_completeness_and_candidate_invariants() -> None:
    candidates, accounting = trade.enumerate_family(trade.BASELINE)
    assert accounting.RAW_OPERATOR_INSTANTIATIONS == 2511
    assert accounting.F3_F2_RAW_INSTANTIATIONS == 1512
    assert accounting.F3_F3_RAW_INSTANTIATIONS == 999
    assert accounting.LEGAL_CANDIDATES == len(candidates) == 2511
    assert accounting.UNIQUE_NORMALIZED_CANDIDATES == 2511
    assert accounting.EXCLUDED_N1_N2_EQUIVALENT == accounting.EXCLUDED_ILLEGAL == 0
    assert accounting.DUPLICATE_NORMALIZED_CANDIDATES == 0
    assert len({c.normalized_sha for c in candidates}) == len(candidates)
    assert all(
        trade.candidate_acceptance(trade.BASELINE, c.portfolio) == "LEGAL" for c in candidates
    )


def test_best_selection_uses_exact_count_then_normalized_sha() -> None:
    candidates = trade.enumerate_family(synthetic(3, 2))[0]
    equal = [ExactPortfolioProbability(1, 43, 0, 17)] * len(candidates)
    chosen = trade.best_index(candidates, equal)
    assert candidates[chosen].normalized_sha == min(c.normalized_sha for c in candidates)
    scores = list(equal)
    scores[-1] = ExactPortfolioProbability(1, 43, 0, 18)
    assert trade.best_index(candidates, scores) == len(candidates) - 1


def test_canonical_exact_count_parity_against_small_bruteforce() -> None:
    portfolio = ((1, 2, 3, 4, 5, 6), (1, 2, 7, 8, 9, 10))
    draws = all_main_draw_masks(12, 6)
    numbers = set(range(1, 13))
    count = m3 = 0
    for main in itertools.combinations(numbers, 6):
        main_set = set(main)
        hits = [len(set(ticket) & main_set) for ticket in portfolio]
        m3 += any(h >= 3 for h in hits)
        for special in numbers - main_set:
            count += any(
                h >= 3 or (h == 2 and special in ticket)
                for ticket, h in zip(portfolio, hits, strict=True)
            )
    a = trade.canonical_score(portfolio, draws, pool_size=12, chunk_size=17)
    b = trade.canonical_score(portfolio, draws, pool_size=12, chunk_size=101)
    assert a == b
    assert a.official_any_prize_outcome_count == count
    assert a.m3_plus_draw_count == m3
    assert trade.special_rescue(a) == count - m3 * 6 > 0


def test_json_round_trip_and_result_start_operator_gate(tmp_path: Path) -> None:
    path = tmp_path / "result.json"
    data: trade.JsonObject = {
        "TASK_ID": trade.TASK_ID,
        "OPERATOR_SIGNATURE": trade.OPERATOR_SIGNATURE,
        "BASELINE_NORMALIZED_SHA": trade.BASELINE_NORMALIZED_SHA,
        "COUNT": 313_263_888,
        "TICKETS": [list(t) for t in trade.BASELINE],
    }
    trade.write_json(path, data)
    assert trade.load_result(path) == data
    assert json.loads(path.read_text()) == data
    data["OPERATOR_SIGNATURE"] = "wrong"
    trade.write_json(path, data)
    with pytest.raises(ValueError, match="different start/operator"):
        trade.load_result(path)


def test_completed_result_matches_exhaustive_score_checkpoint() -> None:
    root = Path(trade.__file__).resolve().parents[3]
    result = trade.load_result(root / trade.RESULT_RELATIVE_PATH)
    checkpoint = json.loads(
        (root / ".fable" / "checkpoints" / trade.TASK_ID / "application.json").read_text()
    )
    assert result["TASK_STATUS"] in ("EVALUATED_CHECKS_PENDING", "COMPLETE")
    candidates, accounting = trade.enumerate_family(trade.BASELINE)
    rows = checkpoint["SCORE_ROWS"]
    assert len(rows) == result["EXACT_SCORED_CANDIDATES"] == 2511
    assert [row[0] for row in rows] == [c.normalized_sha for c in candidates]
    assert result["UNIQUE_NORMALIZED_CANDIDATES"] == accounting.UNIQUE_NORMALIZED_CANDIDATES
    selected = min(rows, key=lambda row: (-row[1], row[0]))
    assert result["BEST_NORMALIZED_SHA"] == selected[0]
    assert result["BEST_EXACT_COUNT"] == selected[1]
    assert result["BEST_M3_PLUS_DRAW_COUNT"] == selected[2]
    assert result["BEST_DELTA"] == selected[1] - trade.BASELINE_COUNT
    best = tuple(tuple(t) for t in result["BEST_TICKETS"])
    assert trade.candidate_acceptance(trade.BASELINE, best) == "LEGAL"
    assert trade.portfolio_sha256(best) == result["BEST_NORMALIZED_SHA"]
    assert result["BASELINE_CANONICAL_RESCORE"] == result["CANONICAL_RESCORE"] == "PASS"
    for prefix in ("BASELINE", "BEST"):
        assert result[f"{prefix}_SPECIAL_RESCUE_OUTCOMES"] == (
            result[f"{prefix}_COUNT" if prefix == "BASELINE" else "BEST_EXACT_COUNT"]
            - result[f"{prefix}_M3_PLUS_DRAW_COUNT"] * 43
        )
    assert result["STRICT_GAIN"] == ("YES" if selected[1] > trade.BASELINE_COUNT else "NO")
    assert result["READY_FOR_N1_ASCENT"] == result["STRICT_GAIN"]
    assert result["PRODUCTION_MUTATION"] == "NONE"
    assert result["GLOBAL_K20_OPTIMUM_STATUS"] == "UNKNOWN"
