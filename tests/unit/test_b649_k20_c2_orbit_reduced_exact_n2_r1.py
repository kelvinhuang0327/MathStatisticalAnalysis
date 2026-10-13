from __future__ import annotations

import copy
import json
import math
from collections import Counter
from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from lottolab.research import b649_k20_c2_orbit_reduced_exact_n2 as orbit
from lottolab.research import b649_official_any_prize_exact as canonical

REPO_ROOT = Path(__file__).resolve().parents[2]
C2_SOURCE_PATH = (
    REPO_ROOT
    / "docs"
    / "research"
    / "matrix-native-results"
    / "b649-cell-a-c2-independent-recount-r1.json"
)
N1_RESULT_PATH = (
    REPO_ROOT
    / "docs"
    / "research"
    / "matrix-native-results"
    / "b649-k20-c2-exact-n1-neighborhood-r1-result.json"
)
RESULT_PATH = (
    REPO_ROOT
    / "docs"
    / "research"
    / "matrix-native-results"
    / "b649-k20-c2-orbit-reduced-exact-n2-r1-result.json"
)
EXPECTED_ORDERED_TO_ENGINE = (0, 1, 3, 6, 2, 7, 11, 4, 5, 9, 10, 8, *range(12, 20))


def c2_tickets() -> list[list[int]]:
    source = json.loads(C2_SOURCE_PATH.read_text(encoding="utf-8"))
    return [list(ticket) for ticket in source["C2"]["full_portfolio"]]


@cache
def c2_group() -> tuple[orbit.Automorphism, ...]:
    return orbit.automorphism_group(c2_tickets())


def c2_rows() -> list[dict[str, Any]]:
    return orbit.build_mapping(c2_tickets())


def n1_tie_neighbor() -> list[list[int]]:
    n1 = json.loads(N1_RESULT_PATH.read_text(encoding="utf-8"))
    position: int = n1["BEST_POSITION"]
    return [
        n1["BEST_ADDED_TICKET"] if index == position else list(ticket)
        for index, ticket in enumerate(n1["START"]["TICKETS_NORMALIZED"])
    ]


def test_module_resolves_inside_this_checkout() -> None:
    assert Path(orbit.__file__).resolve().is_relative_to(REPO_ROOT / "src")


def test_start_identity_is_the_pinned_c2_not_c4_or_the_n1_tie() -> None:
    tickets = c2_tickets()
    source = json.loads(C2_SOURCE_PATH.read_text(encoding="utf-8"))
    orbit.require_c2_start(tickets)
    assert orbit.compact_sha256(tickets) == orbit.C2_ORDERED_SHA256
    assert orbit.compact_sha256(sorted(tickets)) == orbit.C2_SORTED_SHA256
    assert source["C2"]["canonical_id"] == orbit.C2_CANONICAL_CLASS_ID
    assert source["C4"]["canonical_id"] == orbit.C4_CANONICAL_CLASS_ID
    assert orbit.C2_CANONICAL_CLASS_ID != orbit.C4_CANONICAL_CLASS_ID
    assert source["COUNTS"]["canonical_evaluator_count"] == orbit.C2_START_COUNT


def test_ordered_to_engine_slots_is_a_by_value_permutation() -> None:
    tickets = c2_tickets()
    engine = sorted(tickets)
    o2e = orbit.ordered_to_engine_slots(tickets)
    assert o2e == EXPECTED_ORDERED_TO_ENGINE
    assert sorted(o2e) == list(range(20))
    assert all(engine[o2e[slot]] == tickets[slot] for slot in range(20))
    # Positional equality would be wrong: some H slots move under normalization.
    assert any(o2e[slot] != slot for slot in range(12))
    assert orbit.engine_pair(o2e, (2, 4)) == (2, 3)
    assert orbit.engine_pair(o2e, (6, 11)) == (8, 11)


def test_group_is_order_144_and_preserves_all_tickets_and_numbers() -> None:
    tickets = c2_tickets()
    group = c2_group()
    assert len(group) == orbit.EXPECTED_GROUP_ORDER == 144
    for element in group:
        assert orbit.is_automorphism(tickets, element)
        assert sorted(element.numbers) == list(range(1, 50))
        assert all(element.slots[slot] == slot for slot in range(12))
    slot_orbits = {tuple(sorted({g.slots[a] for g in group})) for a in range(20)}
    assert (12, 13, 14, 15, 16, 17) in slot_orbits
    assert (18, 19) in slot_orbits
    assert orbit.burnside_pair_orbit_count(group) == 94


def test_190_slot_pairs_map_to_94_representatives_with_explicit_witnesses() -> None:
    tickets = c2_tickets()
    group = c2_group()
    rows = c2_rows()
    reps = orbit.validate_mapping(tickets, rows, group)
    assert len(rows) == 190
    assert {tuple(row["ORDERED_PAIR"]) for row in rows} == set(orbit.all_slot_pairs())
    assert len(reps) == 94
    assert Counter(row["CLASS"] for row in reps) == Counter(orbit.EXPECTED_CLASS_COUNTS)
    assert Counter(row["ORBIT_SIZE"] for row in reps) == Counter(orbit.EXPECTED_ORBIT_SIZES)
    assert sum(row["ORBIT_SIZE"] for row in reps) == 190
    for row in rows:
        witness = orbit.Automorphism(tuple(row["WITNESS_SLOTS"]), tuple(row["WITNESS_NUMBERS"]))
        pair = (row["ORDERED_PAIR"][0], row["ORDERED_PAIR"][1])
        assert orbit.map_pair(witness, pair) == tuple(row["REPRESENTATIVE_ORDERED_PAIR"])
        untouched = [t for s, t in enumerate(tickets) if s not in pair]
        rep_untouched = sorted(
            tuple(t) for s, t in enumerate(tickets) if s not in row["REPRESENTATIVE_ORDERED_PAIR"]
        )
        mapped = sorted(orbit.apply_numbers(witness.numbers, t) for t in untouched)
        assert mapped == rep_untouched
    assert orbit.mapping_sha256(rows) == orbit.mapping_sha256(c2_rows())


Rows = list[dict[str, Any]]


def _rows_with(mutate: Callable[[Rows], None]) -> Rows:
    rows = copy.deepcopy(c2_rows())
    mutate(rows)
    return rows


def _first(rows: Rows, predicate: Callable[[dict[str, Any]], bool]) -> dict[str, Any]:
    return next(row for row in rows if predicate(row))


def test_mutation_index_swap_is_rejected() -> None:
    def positional(rows: list[dict[str, Any]]) -> None:
        row = _first(rows, lambda r: r["ENGINE_PAIR"] != r["ORDERED_PAIR"])
        row["ENGINE_PAIR"] = list(row["ORDERED_PAIR"])

    def swapped_engine_map(rows: list[dict[str, Any]]) -> None:
        o2e = list(EXPECTED_ORDERED_TO_ENGINE)
        o2e[2], o2e[3] = o2e[3], o2e[2]
        for row in rows:
            row["ENGINE_PAIR"] = list(orbit.engine_pair(o2e, tuple(row["ORDERED_PAIR"])))
            rep = tuple(row["REPRESENTATIVE_ORDERED_PAIR"])
            row["REPRESENTATIVE_ENGINE_PAIR"] = list(orbit.engine_pair(o2e, rep))

    def swapped_witness_slots(rows: list[dict[str, Any]]) -> None:
        row = _first(rows, lambda r: r["WITNESS_SLOTS"][12] != 12)
        slots = row["WITNESS_SLOTS"]
        slots[12], slots[13] = slots[13], slots[12]

    for mutate in (positional, swapped_engine_map, swapped_witness_slots):
        with pytest.raises(ValueError):
            orbit.validate_mapping(c2_tickets(), _rows_with(mutate), c2_group())


def test_mutation_missing_orbit_is_rejected() -> None:
    def drop_orbit(rows: list[dict[str, Any]]) -> None:
        rows[:] = [r for r in rows if r["REPRESENTATIVE_ORDERED_PAIR"] != [12, 13]]

    def drop_representative_row(rows: list[dict[str, Any]]) -> None:
        rows[:] = [r for r in rows if r["ORDERED_PAIR"] != [12, 15]]

    for mutate in (drop_orbit, drop_representative_row):
        with pytest.raises(ValueError):
            orbit.validate_mapping(c2_tickets(), _rows_with(mutate), c2_group())
    with pytest.raises(ValueError):
        orbit.validate_mapping(c2_tickets(), c2_rows(), c2_group(), expected_representatives=95)


def test_mutation_duplicate_orbit_is_rejected() -> None:
    identity = orbit.Automorphism(tuple(range(20)), tuple(range(1, 50)))

    def split_orbit(rows: list[dict[str, Any]]) -> None:
        row = _first(rows, lambda r: r["ORBIT_SIZE"] == 12 and not r["IS_REPRESENTATIVE"])
        row["REPRESENTATIVE_ORDERED_PAIR"] = list(row["ORDERED_PAIR"])
        row["REPRESENTATIVE_ENGINE_PAIR"] = list(row["ENGINE_PAIR"])
        row["IS_REPRESENTATIVE"] = True
        row["ORBIT_INDEX"] = 94
        row["ORBIT_SIZE"] = 1
        row["WITNESS_SLOTS"] = list(identity.slots)
        row["WITNESS_NUMBERS"] = list(identity.numbers)

    def duplicate_row(rows: list[dict[str, Any]]) -> None:
        rows.append(copy.deepcopy(rows[0]))

    def shared_orbit_index(rows: list[dict[str, Any]]) -> None:
        index = _first(rows, lambda r: r["ORDERED_PAIR"] == [18, 19])["ORBIT_INDEX"]
        for row in rows:
            if row["REPRESENTATIVE_ORDERED_PAIR"] == [12, 18]:
                row["ORBIT_INDEX"] = index

    for mutate in (split_orbit, duplicate_row, shared_orbit_index):
        with pytest.raises(ValueError):
            orbit.validate_mapping(c2_tickets(), _rows_with(mutate), c2_group())


def test_mutation_wrong_start_identity_is_rejected() -> None:
    tickets = c2_tickets()
    swapped = [*tickets[1:2], *tickets[0:1], *tickets[2:]]
    for wrong in (swapped, n1_tie_neighbor()):
        with pytest.raises(ValueError):
            orbit.require_c2_start(wrong)
    with pytest.raises(ValueError):
        orbit.validate_mapping(n1_tie_neighbor(), c2_rows(), c2_group())
    with pytest.raises(ValueError):
        orbit.validate_mapping(swapped, c2_rows(), c2_group())


def test_mutation_non_automorphism_witness_or_group_is_rejected() -> None:
    def identity_witness_off_orbit(rows: list[dict[str, Any]]) -> None:
        row = _first(rows, lambda r: not r["IS_REPRESENTATIVE"])
        row["WITNESS_SLOTS"] = list(range(20))
        row["WITNESS_NUMBERS"] = list(range(1, 50))

    with pytest.raises(ValueError):
        orbit.validate_mapping(c2_tickets(), _rows_with(identity_witness_off_orbit), c2_group())
    group = list(c2_group())
    bad = orbit.Automorphism(group[1].slots, group[0].numbers)
    with pytest.raises(ValueError):
        orbit.validate_mapping(c2_tickets(), c2_rows(), [*group[:1], bad, *group[2:]])


def load_result() -> dict[str, Any]:
    return json.loads(RESULT_PATH.read_text(encoding="utf-8"))


def test_result_start_is_the_pinned_c2_held_fixed() -> None:
    result = load_result()
    start = result["START"]
    tickets = c2_tickets()
    assert result["TASK_STATUS"] == "COMPLETE"
    assert start["TICKETS_ORDERED"] == tickets
    assert start["TICKETS_NORMALIZED"] == sorted(tickets)
    assert orbit.compact_sha256(tickets) == start["ORDERED_SHA256"] == orbit.C2_ORDERED_SHA256
    assert orbit.compact_sha256(sorted(tickets)) == start["SORTED_SHA256"] == orbit.C2_SORTED_SHA256
    assert start["CANONICAL_CLASS_ID"] == orbit.C2_CANONICAL_CLASS_ID
    assert start["CANONICAL_CLASS_ID"] != orbit.C4_CANONICAL_CLASS_ID
    assert start["SORTED_SHA256"] != orbit.C2_N1_DELTA0_TIE_SORTED_SHA256
    assert start["CANONICAL_RECOUNT"] == orbit.C2_START_COUNT == 313_263_888
    assert start["HELD_FIXED_FOR_THE_WHOLE_SWEEP"] is True
    assert result["ITERATIONS_RUN"] == 1
    assert result["ASCENT_APPLIED"] is False


def test_result_covers_all_190_slot_pairs_through_94_terminal_representatives() -> None:
    result = load_result()
    rows = c2_rows()
    reps = orbit.validate_mapping(c2_tickets(), rows, c2_group())
    reduction = result["ORBIT_REDUCTION"]
    assert reduction["MAPPING_SHA256"] == orbit.mapping_sha256(rows)
    assert reduction["GROUP_ORDER"] == 144
    assert reduction["BURNSIDE_PAIR_ORBITS"] == reduction["REPRESENTATIVES"] == 94
    assert reduction["RAW_SLOT_PAIRS"] == 190
    assert reduction["ORDERED_TO_ENGINE_SLOTS"] == list(EXPECTED_ORDERED_TO_ENGINE)
    records = {tuple(r["ORDERED_PAIR"]): r for r in result["REPRESENTATIVES"]}
    assert len(records) == len(result["REPRESENTATIVES"]) == 94
    assert set(records) == {tuple(rep["ORDERED_PAIR"]) for rep in reps}
    for rep in reps:
        record = records[tuple(rep["ORDERED_PAIR"])]
        assert record["ENGINE_PAIR"] == rep["ENGINE_PAIR"]
        assert record["CLASS"] == rep["CLASS"]
        assert record["ORBIT_SIZE"] == rep["ORBIT_SIZE"]
    assert result["TERMINAL_REPRESENTATIVES"] == 94
    assert result["MATHEMATICALLY_COVERED_ORIGINAL_PAIRS"] == 190
    assert sum(r["ORBIT_SIZE"] for r in result["REPRESENTATIVES"]) == 190
    assert result["PENDING_REPRESENTATIVES_ENGINE"] == []


def test_result_per_pair_accounting_is_separated_on_the_raw_denominator() -> None:
    result = load_result()
    n6 = math.comb(49, 6)
    raw = math.comb(n6, 2)
    legal = math.comb(n6 - 18, 2)
    records = result["REPRESENTATIVES"]
    for record in records:
        acc = record["ACCOUNTING"]
        assert acc["RAW"] == raw
        assert acc["ILLEGAL_EXCLUDED_R_INVOLVING"] == raw - legal
        assert acc["LEGAL"] == legal == acc["EXACTLY_SCORED"] + acc["SOUNDLY_PRUNED_LEGAL"]
        assert acc["EXACTLY_SCORED"] > 0
        assert acc["DONOR_N_PRUNED_HIST"] == (
            acc["ILLEGAL_EXCLUDED_R_INVOLVING"] + acc["SOUNDLY_PRUNED_LEGAL"]
        )
    totals = result["ACCOUNTING"]["TOTALS_OVER_TERMINAL_REPRESENTATIVES"]
    for field, value in totals.items():
        assert value == sum(record["ACCOUNTING"][field] for record in records)
    assert totals["RAW"] == 94 * raw
    assert "C(C(49,6),2)" in result["ACCOUNTING"]["DENOMINATOR_CONVENTION"]


def test_result_no_strict_n2_gain_and_ties_are_only_recorded() -> None:
    result = load_result()
    records = result["REPRESENTATIVES"]
    assert all(r["ENGINE_BEST_SCORED_DELTA_OUTCOME"] == 0 for r in records)
    assert max(r["BEST_DELTA_OUTCOME"] for r in records) == result["BEST_DELTA"] == 0
    assert result["BEST_IS_GAIN"] is False
    assert result["WINNER"] is None
    assert result["BEST_EXACT_COUNT"] == orbit.C2_START_COUNT
    assert result["BEST_PORTFOLIO_SHA"] == orbit.C2_SORTED_SHA256
    assert result["CANONICAL_GAIN_RECOUNT"] == "NOT_APPLICABLE_NO_POSITIVE_DELTA"
    assert result["N2_LOCAL_CLOSURE_STATUS"] == (
        "C2_N2_LOCAL_CLOSURE_PROVEN_FOR_EXACT_TWO_TICKET_REPLACEMENT_NEIGHBORHOOD_ONLY"
    )
    ties = result["TIES_RECORDED_NOT_PROMOTED"]
    assert len(ties) == 94
    assert all(t["BEST_DELTA_OUTCOME"] == 0 and t["TIE_COUNT_SCORED"] >= 1 for t in ties)
    assert result["GLOBAL_K20_OPTIMUM_STATUS"] == "UNKNOWN"


def test_result_canonical_gates_and_authority() -> None:
    result = load_result()
    verification = result["VERIFICATION"]
    assert verification["G1"] == "PASS"
    for gate, checks in (("G3", 94), ("G4", 376), ("G5", 27)):
        assert verification[gate]["STATUS"] == "PASS"
        assert verification[gate]["CHECKS"] == len(verification[gate]["RECORDS"]) == checks
        assert verification[gate]["MISMATCHES"] == 0
    draws = canonical.all_main_draw_masks(49, 6)
    for record in verification["G3"]["RECORDS"][:3]:
        pair = record["ENGINE_PAIR"]
        normalized = sorted(c2_tickets())
        untouched = [t for slot, t in enumerate(normalized) if slot not in pair]
        portfolio = sorted([*untouched, record["T1"], record["T2"]])
        score = canonical.evaluate_portfolio(portfolio, draws=draws)
        assert score.official_any_prize_outcome_count == record["CANONICAL_OUTCOME_COUNT"]
        assert record["ENGINE_OUTCOME_COUNT"] == record["CANONICAL_OUTCOME_COUNT"]
    authority = result["ENGINE_AUTHORITY"]
    assert authority["ENGINE_BINARY_SHA256"] == (
        "89de3a0f439576a3028f59fb41da8703990a52188df94c0bc33379e1da7fa0cf"
    )
    assert authority["ENGINE_SOURCE_SHA256"] == (
        "ed7c88467a56648c6587aadbbce6b23bc419c9218f840405238019ac7286d4fa"
    )
    assert authority["EVALUATOR_SHA256"] == (
        "92dcb836254cc6dbcd6c2ad907e619a5eb8cf3917197a8f6de3e5f989825cf66"
    )
    assert authority["C4_CACHED_RESULTS_REUSED"] is False
    assert authority["N1_RESULTS_REUSED"] is False
