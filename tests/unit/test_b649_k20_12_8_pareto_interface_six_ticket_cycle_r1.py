"""Focused checks for the bounded Pareto-interface six-ticket cycle census."""

from __future__ import annotations

import itertools
import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import replace
from math import comb
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest
from tools import b649_k20_12_8_pareto_interface_six_ticket_cycle_r1 as driver

from lottolab.research.b649_official_any_prize_exact import DrawMasks, ExactPortfolioProbability

RESULT_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs/research/matrix-native-results"
    / "b649-k20-12-8-pareto-interface-six-ticket-cycle-r1-result.json"
)


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(RESULT_PATH.read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def baseline(result: dict[str, Any]) -> driver.Portfolio:
    return driver.parse_tickets(result["BASELINE_TICKETS"])


@pytest.fixture(scope="module")
def raw(baseline: driver.Portfolio) -> tuple[driver.Candidate, ...]:
    return driver.enumerate_candidates(baseline)


def test_baseline_count_hashes_and_slot_identity(
    result: dict[str, Any], baseline: driver.Portfolio
) -> None:
    driver.require_baseline_identity(baseline)
    assert result["BASELINE_COUNT"] == 313263888
    assert (
        driver.portfolio_sha(baseline)
        == ("10d4ef5102ad824fb2c96503501694bef3f878504c8c164698c86f2f1ce35a3b")
        == result["BASELINE_ARTIFACT_SHA"]
    )
    assert (
        driver.portfolio_sha(driver.normalize(baseline))
        == ("eaed652900d101881b678a1515d2a366bff9de6723dbec2ec9c82fe0d0d7844c")
        == result["BASELINE_NORMALIZED_SHA"]
    )
    assert {n: driver.supports(baseline, n) for n in range(21, 29)} == {
        21: (0, 10),
        22: (1, 2),
        23: (3, 9),
        24: (4, 7),
        25: (5, 8),
        26: (6, 11),
        27: (12, 13, 14),
        28: (15, 16, 17),
    }
    assert result["BASELINE_CANONICAL_RESCORE"] == "PASS"


def test_exactly_108_raw_directed_operator_instances(raw: tuple[driver.Candidate, ...]) -> None:
    expected = set(
        itertools.product(
            range(21, 27),
            itertools.combinations((12, 13, 14), 2),
            itertools.combinations((15, 16, 17), 2),
            ("FORWARD", "REVERSE"),
        )
    )
    observed = {(c.y, c.ax, c.az, c.direction) for c in raw}
    assert len(raw) == len(observed) == len(expected) == 108
    assert observed == expected
    assert Counter(c.direction for c in raw) == {"FORWARD": 54, "REVERSE": 54}


def test_cycle_semantics_six_changed_slots_legality_and_frequencies(
    baseline: driver.Portfolio, raw: tuple[driver.Candidate, ...]
) -> None:
    baseline_frequencies = Counter(itertools.chain.from_iterable(baseline))
    for candidate in raw:
        ay = driver.supports(baseline, candidate.y)
        assert len(set(candidate.ax + candidate.az + ay)) == 6
        expected: list[tuple[int, ...]] = []
        forward = candidate.direction == "FORWARD"
        for slot, ticket in enumerate(baseline):
            if slot in candidate.ax:
                old, new = 27, candidate.y if forward else 28
            elif slot in candidate.az:
                old, new = 28, 27 if forward else candidate.y
            elif slot in ay:
                old, new = candidate.y, 28 if forward else 27
            else:
                expected.append(ticket)
                continue
            expected.append(tuple(sorted(new if number == old else number for number in ticket)))
        assert candidate.tickets == tuple(expected)
        changed = {
            i
            for i, (old, new) in enumerate(zip(baseline, candidate.tickets, strict=True))
            if set(old) != set(new)
        }
        assert changed == set(candidate.ax + candidate.az + ay)
        assert len(driver.normalize(candidate.tickets)) == len(set(candidate.tickets)) == 20
        for ticket in candidate.tickets:
            assert len(ticket) == len(set(ticket)) == 6
            assert all(type(number) is int and 1 <= number <= 49 for number in ticket)
        counts = Counter(itertools.chain.from_iterable(candidate.tickets))
        assert counts == baseline_frequencies
        assert (counts[27], counts[28], counts[candidate.y]) == (3, 3, 2)
        driver.require_candidate(baseline, candidate)
    # The defined family admits overlaps above one; these candidates stay in.
    assert any(
        len(set(a) & set(b)) > 1 for c in raw for a, b in itertools.combinations(c.tickets, 2)
    )


def test_dedup_is_exact_normalized_sets_even_with_sha_collision(
    raw: tuple[driver.Candidate, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    first = raw[0]
    reordered = replace(first, tickets=tuple(tuple(reversed(t)) for t in reversed(first.tickets)))
    assert driver.normalize(reordered.tickets) == driver.normalize(first.tickets)
    assert driver.deduplicate((first, reordered, raw[1])) == (first, raw[1])

    def colliding_sha(_tickets: Sequence[Sequence[int]]) -> str:
        return "0" * 64

    monkeypatch.setattr(driver, "portfolio_sha", colliding_sha)
    assert len(driver.deduplicate(raw)) == len({driver.normalize(c.tickets) for c in raw}) == 108


def test_support_mismatch_stops_even_when_normalized_set_is_unchanged(
    baseline: driver.Portfolio,
) -> None:
    changed = list(baseline)
    changed[0], changed[1] = changed[1], changed[0]
    assert driver.normalize(changed) == driver.normalize(baseline)
    with pytest.raises(ValueError, match="PARETO_INTERFACE_IDENTITY_MISMATCH"):
        driver.enumerate_candidates(tuple(changed))


@pytest.mark.parametrize("corruption", ["ticket_duplicate", "number_duplicate", "range", "length"])
def test_illegal_or_duplicate_tickets_are_rejected(
    baseline: driver.Portfolio, corruption: str
) -> None:
    changed = list(baseline)
    if corruption == "ticket_duplicate":
        changed[1] = changed[0]
    elif corruption == "number_duplicate":
        changed[0] = (*changed[0][:-1], changed[0][0])
    elif corruption == "range":
        changed[0] = (*changed[0][:-1], 50)
    else:
        changed.pop()
    with pytest.raises(ValueError, match="LEGALITY_DISTINCT_TICKET_MISMATCH"):
        driver.require_legal(tuple(changed))


def test_difference_and_frequency_guards_reject_corrupted_candidates(
    baseline: driver.Portfolio, raw: tuple[driver.Candidate, ...]
) -> None:
    with pytest.raises(ValueError, match="SIX_TICKET_DIFFERENCE_MISMATCH"):
        driver.require_candidate(baseline, replace(raw[0], tickets=baseline))
    changed = list(raw[0].tickets)
    changed[0] = tuple(sorted(49 if n == 1 else n for n in changed[0]))
    with pytest.raises(ValueError, match="FREQUENCY_PRESERVATION_MISMATCH"):
        driver.require_candidate(baseline, replace(raw[0], tickets=tuple(changed)))


def test_all_recorded_components_and_deterministic_best(
    result: dict[str, Any], raw: tuple[driver.Candidate, ...]
) -> None:
    candidates = driver.deduplicate(raw)
    rows = cast(list[dict[str, Any]], result["CANDIDATE_SCORES"])
    assert (
        result["RAW_CANDIDATES"],
        result["LEGAL_CANDIDATES"],
        result["UNIQUE_NORMALIZED_CANDIDATES"],
    ) == (108, 108, len(candidates))
    assert result["FORWARD_CANDIDATES"] == result["REVERSE_CANDIDATES"] == 54
    assert len(rows) == len(candidates) == 108
    scored: list[driver.ScoredCandidate] = []
    for row, candidate in zip(rows, candidates, strict=True):
        assert {key: row[key] for key in candidate.operator_record()} == candidate.operator_record()
        official, m3, rescue = (
            cast(int, row["OFFICIAL_ANY_PRIZE_OUTCOME_COUNT"]),
            cast(int, row["M3_PLUS_DRAW_COUNT"]),
            cast(int, row["SPECIAL_RESCUE_OUTCOMES"]),
        )
        assert official == 43 * m3 + rescue
        components = driver.Components.from_exact(
            ExactPortfolioProbability(comb(49, 6), 43, m3, official)
        )
        scored.append(driver.ScoredCandidate(candidate, components))
    independent_best = sorted(
        rows, key=lambda r: (-r["OFFICIAL_ANY_PRIZE_OUTCOME_COUNT"], r["NORMALIZED_SHA"])
    )[0]
    best = driver.select_best(scored)
    assert best.candidate.normalized_sha == independent_best["NORMALIZED_SHA"]
    assert result["BEST_NORMALIZED_SHA"] == best.candidate.normalized_sha
    assert driver.parse_tickets(result["BEST_TICKETS"]) == best.candidate.tickets
    assert result["BEST_EXACT_COUNT"] == best.components.official
    assert result["BEST_DELTA"] == best.components.official - 313263888
    for prefix in ("BASELINE", "BEST"):
        count = result["BASELINE_COUNT" if prefix == "BASELINE" else "BEST_EXACT_COUNT"]
        assert (
            count
            == 43 * result[f"{prefix}_M3_PLUS_DRAW_COUNT"]
            + result[f"{prefix}_SPECIAL_RESCUE_OUTCOMES"]
        )
    assert result["BEST_FRESH_CANONICAL_COMPONENTS"] == best.components.record()
    assert result["CANONICAL_RESCORE"] == "PASS"
    assert result["CANONICAL_EVALUATIONS"] == len(candidates) + 2
    assert result["COMPLETE_MAIN_DRAW_COUNT"] == comb(49, 6)
    assert result["SPECIAL_COUNT"] == 43
    gain = best.components.official > 313263888
    assert result["STRICT_GAIN"] == result["READY_FOR_N1_ASCENT"] == ("YES" if gain else "NO")
    assert result["FAMILY_STATUS"] == (driver.GAIN_STATUS if gain else driver.NO_GAIN_STATUS)
    assert result["GLOBAL_K20_OPTIMUM_STATUS"] == "UNKNOWN"


def test_component_guards_reject_incomplete_space_and_negative_rescue() -> None:
    with pytest.raises(ValueError, match="INCOMPLETE_CANONICAL_DRAW_SPACE"):
        driver.Components.from_exact(ExactPortfolioProbability(1, 43, 0, 1))
    with pytest.raises(ValueError, match="EXACT_COMPONENT_ARITHMETIC_MISMATCH"):
        driver.Components.from_exact(ExactPortfolioProbability(comb(49, 6), 43, 1, 42))


@pytest.mark.parametrize("delta", [-1, 1])
def test_orchestration_reuses_draws_and_freshly_calls_canonical_best(
    baseline: driver.Portfolio,
    raw: tuple[driver.Candidate, ...],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    delta: int,
) -> None:
    # This seam tests invocation accounting only; the terminal artifact above
    # comes exclusively from the real complete-space canonical evaluator.
    authority = {
        "TASK_ID": "B649_K20_12_8_WINNER_TWO_TICKET_ASCENT_R1",
        "TASK_STATUS": "COMPLETE",
        "FINAL_COUNT": 313263888,
        "FINAL_ENGINE_NORMALIZED_SHA256": driver.BASELINE_NORMALIZED_SHA,
        "START_ARTIFACT_SHA256": driver.BASELINE_ARTIFACT_SHA,
        "CANONICAL_RESCORE": "PASS",
        "N1_N2_COMBINED_LOCAL_STATUS": "PROVEN_FOR_VALIDATED_N1_AND_N2_NEIGHBORHOODS",
        "START_TICKETS": baseline,
        "FINAL_TICKETS": driver.normalize(baseline),
    }
    authority_path = tmp_path / "authority.json"
    authority_path.write_text(json.dumps(authority), encoding="utf-8")
    # A read-only broadcast keeps the full shape without allocating a draw buffer.
    space = np.broadcast_to(np.array([0], dtype=np.uint64), (comb(49, 6),))
    builds: list[tuple[int, int]] = []
    calls: list[driver.Portfolio] = []

    def fake_draw_space(pool_size: int, draw_size: int) -> DrawMasks:
        builds.append((pool_size, draw_size))
        return space

    def fake_evaluator(
        tickets: Sequence[Sequence[int]],
        *,
        draws: DrawMasks | None = None,
    ) -> ExactPortfolioProbability:
        assert draws is space
        calls.append(tuple(tuple(t) for t in tickets))
        official = 313263888 if len(calls) == 1 else 313263888 + delta
        return ExactPortfolioProbability(comb(49, 6), 43, 6000000, official)

    monkeypatch.setattr(driver, "all_main_draw_masks", fake_draw_space)
    monkeypatch.setattr(driver, "evaluate_portfolio", fake_evaluator)
    output_path = tmp_path / "result.json"
    output = driver.run_research(authority_path, output_path)
    candidates = driver.deduplicate(raw)
    assert builds == [(49, 6)]
    assert len(calls) == 110
    assert calls[0] == baseline
    assert calls[1:-1] == [c.tickets for c in candidates]
    expected_best = min(candidates, key=lambda c: c.normalized_sha)
    assert calls[-1] == expected_best.tickets
    assert output["BEST_NORMALIZED_SHA"] == expected_best.normalized_sha
    assert output["STRICT_GAIN"] == output["READY_FOR_N1_ASCENT"] == ("YES" if delta > 0 else "NO")
    assert json.loads(output_path.read_text(encoding="utf-8")) == output
    with pytest.raises(FileExistsError):
        driver.run_research(authority_path, output_path)
    assert len(calls) == 110


def test_result_json_write_read_round_trip(result: dict[str, Any], tmp_path: Path) -> None:
    assert result["TASK_ID"] == driver.TASK_ID
    assert result["TASK_STATUS"] == "COMPLETE"
    assert result["START_NORMALIZED_SHA"] == driver.BASELINE_NORMALIZED_SHA
    assert result["OPERATOR_SIGNATURE"] == driver.OPERATOR_SIGNATURE
    assert result["JSON_ROUND_TRIP"] == "PASS"
    output = tmp_path / "round-trip.json"
    driver.write_result(result, output)
    assert json.loads(output.read_text(encoding="utf-8")) == result
    with pytest.raises(FileExistsError):
        driver.write_result(result, output)
