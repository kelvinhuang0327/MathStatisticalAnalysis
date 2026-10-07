"""Focused checks for the 12+8 component-internal F2 rewire search and its sealed result."""

from __future__ import annotations

import json
import random
from collections import Counter
from functools import cache
from pathlib import Path
from typing import Any, cast

import pytest

from lottolab.research import b649_k20_12_8_component_internal_f2_rewire_r1 as search
from lottolab.research.b649_official_any_prize_exact import evaluate_portfolio

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_FILE = REPO_ROOT / search.RESULT_PATH
BASELINE_COUNT = 313_263_888
BASELINE_SHA256 = "eaed652900d101881b678a1515d2a366bff9de6723dbec2ec9c82fe0d0d7844c"


@cache
def _structure() -> search.Structure:
    return search.derive_structure(search.load_authority(REPO_ROOT).portfolio)


@cache
def _family_a() -> search.FamilyASpace:
    return search.build_family_a(_structure())


@cache
def _family_b() -> search.FamilyBSpace:
    return search.build_family_b(_structure())


@cache
def _tables() -> search.DecompositionTables:
    structure = _structure()
    return search.decomposition_tables(structure.twelve.numbers, structure.eight.numbers)


def _result() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(RESULT_FILE.read_text(encoding="utf-8")))


def _f3_supports(portfolio: search.Portfolio) -> dict[int, tuple[int, ...]]:
    supports: dict[int, list[int]] = {}
    for slot, ticket in enumerate(portfolio):
        for number in ticket:
            supports.setdefault(number, []).append(slot)
    return {number: tuple(slots) for number, slots in supports.items() if len(slots) == 3}


def test_baseline_authority_and_canonical_rescore(tmp_path: Path) -> None:
    authority = search.load_authority(REPO_ROOT)
    exact = evaluate_portfolio(authority.portfolio)

    assert authority.count == BASELINE_COUNT
    assert authority.sha256 == BASELINE_SHA256
    assert search.portfolio_sha256(authority.portfolio) == BASELINE_SHA256
    assert exact.official_any_prize_outcome_count == BASELINE_COUNT
    assert _result()["BASELINE"]["M3_PLUS_DRAW_COUNT"] == exact.m3_plus_draw_count

    drifted = cast(
        dict[str, Any], json.loads((REPO_ROOT / search.AUTHORITY_RESULT_PATH).read_text())
    )
    drifted["FINAL_COUNT"] = BASELINE_COUNT + 1
    (tmp_path / search.AUTHORITY_RESULT_PATH).parent.mkdir(parents=True)
    (tmp_path / search.AUTHORITY_RESULT_PATH).write_text(json.dumps(drifted))
    with pytest.raises(search.SourceAuthorityDriftError):
        search.load_authority(tmp_path)


def test_component_derivation_uses_supports_not_ticket_order() -> None:
    structure = _structure()
    assert (len(structure.twelve.slots), len(structure.eight.slots)) == (12, 8)
    assert structure.twelve.numbers == tuple(range(1, 27))
    assert structure.eight.numbers == tuple(range(27, 50))

    shuffled = list(structure.baseline)
    random.Random(649).shuffle(shuffled)
    reordered = search.derive_structure(tuple(shuffled))
    assert set(reordered.twelve.numbers) == set(structure.twelve.numbers)
    assert set(reordered.eight.numbers) == set(structure.eight.numbers)
    assert {number for number, _ in reordered.eight.f3_supports} == {
        number for number, _ in structure.eight.f3_supports
    }

    crossed = [list(ticket) for ticket in structure.baseline]
    twelve_slot, eight_slot = structure.twelve.slots[0], structure.eight.slots[0]
    crossed[twelve_slot][0], crossed[eight_slot][0] = (
        crossed[eight_slot][0],
        crossed[twelve_slot][0],
    )
    with pytest.raises(search.ComponentIdentityMismatchError):
        search.derive_structure(tuple(tuple(sorted(ticket)) for ticket in crossed))


def test_frequency_and_support_inventory() -> None:
    structure = _structure()
    twelve, eight = structure.twelve, structure.eight
    twelve_f3_degree = Counter(slot for _, triple in twelve.f3_supports for slot in triple)
    matched = [slot for edge in twelve.baseline_f2_edges for slot in edge]

    assert len(twelve.f3_supports) == 20
    assert len(twelve.f2_labels) == 6
    assert all(twelve_f3_degree[slot] == 5 for slot in range(12))
    assert sorted(matched) == list(range(12))

    triples = [set(triple) for _, triple in eight.f3_supports]
    assert len(triples) == 2 and not triples[0] & triples[1]
    assert len(eight.f2_labels) == len(set(eight.baseline_f2_edges)) == 21
    assert structure.eight_non_f3_slots == tuple(
        slot for slot in range(8) if slot not in triples[0] | triples[1]
    )
    degrees = search.f2_degrees(8, eight.baseline_f2_edges)
    assert degrees == structure.eight_f2_degree_targets
    assert sorted(degrees) == [5] * 6 + [6] * 2
    profile = Counter(len(slots) for slots in search.number_supports(structure.baseline).values())
    assert profile == Counter({3: 22, 2: 27})


def test_family_a_perfect_matching_count() -> None:
    space = _family_a()
    matchings = search.enumerate_perfect_matchings(12)

    assert space.raw_count == len(matchings) == len(set(matchings)) == 10395
    assert search.odd_double_factorial(12) == 11 * 9 * 7 * 5 * 3 == 10395
    assert all(
        sorted(v for edge in matching for v in edge) == list(range(12)) for matching in matchings
    )
    assert len(space.legal) == 10395 and space.illegal_indices == ()
    assert matchings[space.baseline_index] == _structure().twelve.baseline_f2_edges
    assert search.enumerate_perfect_matchings(4) == (
        ((0, 1), (2, 3)),
        ((0, 2), (1, 3)),
        ((0, 3), (1, 2)),
    )


def test_family_b_raw_graph_count() -> None:
    structure = _structure()
    space = _family_b()

    assert len(space.graphs) == space.brute_force_count == 1072
    assert len(set(space.graphs)) == 1072
    for graph in space.graphs:
        edges = search.mask_to_edges(graph, 8)
        assert len(edges) == 21
        assert search.f2_degrees(8, edges) == structure.eight_f2_degree_targets
    assert space.legal_raw_count == 1072


def test_family_b_automorphism_group_closure() -> None:
    structure = _structure()
    group = _family_b().group
    triples = tuple(triple for _, triple in structure.eight.f3_supports)
    members = set(group)

    assert len(group) == 2 * 2 * 6 * 6 == 144
    assert tuple(range(8)) in members
    assert all(search.compose(first, second) in members for first in group for second in group)
    assert all(search.invert(permutation) in members for permutation in group)
    search.verify_group(group, 8, triples, structure.eight_non_f3_slots)

    bearing, free = triples[0][0], structure.eight_non_f3_slots[0]
    swap = list(range(8))
    swap[bearing], swap[free] = free, bearing
    assert tuple(swap) not in members


def test_exact_orbit_coverage_and_relabel_witnesses() -> None:
    structure = _structure()
    space = _family_b()
    quotient = space.quotient

    assert len(quotient.representatives) == space.burnside_orbit_count == 20
    assert search.verify_quotient(space.graphs, space.group, quotient, 8) == 20
    assert sum(quotient.orbit_sizes) == 1072
    assert all(144 % size == 0 for size in quotient.orbit_sizes)
    for graph, orbit, witness in quotient.assignments:
        bits = search.permutation_pair_bits(witness, 8)
        assert search.permute_mask(bits, graph) == quotient.representatives[orbit]
        search.verify_portfolio_witness(structure, graph, quotient.representatives[orbit], witness)


def test_orbit_coverage_mutation_is_rejected() -> None:
    space = _family_b()
    quotient = space.quotient
    position = next(
        position
        for position, (_, orbit, _) in enumerate(quotient.assignments)
        if quotient.orbit_sizes[orbit] > 1
    )
    graph, orbit, _ = quotient.assignments[position]
    wrong = next(
        permutation
        for permutation in space.group
        if search.permute_mask(search.permutation_pair_bits(permutation, 8), graph)
        != quotient.representatives[orbit]
    )
    assignments = list(quotient.assignments)
    assignments[position] = (graph, orbit, wrong)
    mutated = search.Quotient(quotient.representatives, tuple(assignments), quotient.orbit_sizes)

    with pytest.raises(search.QuotientUnresolvedError):
        search.verify_quotient(space.graphs, space.group, mutated, 8)


def test_candidate_legality_and_rejections() -> None:
    structure = _structure()
    overlapping = next(candidate for candidate in _family_a().legal if candidate.retained == 0)
    profile = search.check_candidate(structure, search.FAMILY_A, overlapping.portfolio)
    assert profile.max_overlap == 2

    portfolio = [list(ticket) for ticket in overlapping.portfolio]
    duplicate = [list(ticket) for ticket in portfolio]
    duplicate[1] = list(duplicate[0])
    eight_slot = structure.eight.slots[0]
    f3_number = structure.eight.f3_supports[0][0]
    f2_number = next(n for n in portfolio[eight_slot] if n != f3_number)
    moved_f3 = [list(ticket) for ticket in portfolio]
    other = next(slot for slot in structure.eight.slots if f3_number not in portfolio[slot])
    moved_f3[eight_slot].remove(f3_number)
    moved_f3[eight_slot].append(next(n for n in portfolio[other] if n not in moved_f3[eight_slot]))
    crossed = [list(ticket) for ticket in portfolio]
    crossed[structure.twelve.slots[0]][0] = f2_number
    for mutation in (duplicate, moved_f3, crossed):
        candidate = tuple(tuple(sorted(ticket)) for ticket in mutation)
        with pytest.raises(search.CandidateInvariantError):
            search.check_candidate(structure, search.FAMILY_A, candidate)


def test_f3_immutability_and_component_separation_for_every_candidate() -> None:
    structure = _structure()
    baseline_f3 = _f3_supports(structure.baseline)
    twelve, eight = set(structure.twelve.slots), set(structure.eight.slots)
    candidates = [(search.FAMILY_A, candidate.portfolio) for candidate in _family_a().legal]
    candidates += [
        (
            search.FAMILY_B,
            search.build_candidate(structure, search.FAMILY_B, search.mask_to_edges(g, 8)),
        )
        for g in _family_b().graphs
    ]
    assert len(candidates) == 10395 + 1072
    for family, portfolio in candidates:
        frozen = eight if family == search.FAMILY_A else twelve
        twelve_numbers = {n for slot in twelve for n in portfolio[slot]}
        eight_numbers = {n for slot in eight for n in portfolio[slot]}
        assert _f3_supports(portfolio) == baseline_f3
        assert not twelve_numbers & eight_numbers
        assert len(twelve_numbers | eight_numbers) == 49
        assert all(portfolio[slot] == structure.baseline[slot] for slot in frozen)
        assert len(set(portfolio)) == 20 and all(len(set(t)) == 6 for t in portfolio)


def test_exact_component_arithmetic() -> None:
    structure = _structure()
    result = _result()
    exact = evaluate_portfolio(structure.baseline)

    assert search.decomposed_score(structure.baseline, _tables()) == (
        exact.official_any_prize_outcome_count,
        exact.m3_plus_draw_count,
    )
    records = [result["BASELINE"], result["FAMILY_A_12_SIDE"]["BEST"]]
    records += [result["FAMILY_B_8_SIDE"]["BEST"], result["OVERALL_BEST"]]
    for record in records:
        count = record["OFFICIAL_ANY_PRIZE_OUTCOME_COUNT"]
        m3_plus = record["M3_PLUS_DRAW_COUNT"]
        assert record["SPECIAL_RESCUE_OUTCOMES"] == count - 43 * m3_plus
        tickets = tuple(tuple(ticket) for ticket in record["TICKETS"])
        assert search.decomposed_score(tickets, _tables()) == (count, m3_plus)
    per_orbit = search.orbit_constant_crosscheck(structure, _family_b(), _tables())
    for orbit in result["FAMILY_B_8_SIDE"]["ORBITS"]:
        assert per_orbit[orbit["ORBIT_INDEX"]] == (
            orbit["OFFICIAL_ANY_PRIZE_OUTCOME_COUNT"],
            orbit["M3_PLUS_DRAW_COUNT"],
        )


def test_result_json_round_trip_and_consistency() -> None:
    text = RESULT_FILE.read_text(encoding="utf-8")
    result = _result()
    family_a, family_b = result["FAMILY_A_12_SIDE"], result["FAMILY_B_8_SIDE"]
    overall = result["OVERALL_BEST"]

    assert search.render_json(result) + "\n" == text
    assert result["TASK_ID"] == search.TASK_ID and result["TASK_STATUS"] == "COMPLETE"
    assert result["BASELINE"]["OFFICIAL_ANY_PRIZE_OUTCOME_COUNT"] == BASELINE_COUNT
    assert result["BASELINE"]["NORMALIZED_SHA256"] == BASELINE_SHA256

    ledger = family_a["LEDGER"]
    codes = [search.matching_partner_code(m) for m in search.enumerate_perfect_matchings(12)]
    assert [row[0] for row in ledger] == list(range(10395))
    assert [row[1] for row in ledger] == codes
    assert family_a["LEDGER_SHA256"] == search.ledger_sha256(ledger)
    assert family_a["RAW_MATCHINGS"] == family_a["LEGAL"] == family_a["SCORED"] == 10395
    assert family_a["BEST_COUNT"] == max(row[2] for row in ledger)
    assert family_a["BASELINE_MATCHING_COUNT"] == BASELINE_COUNT
    assert (
        sum(group["CANDIDATES"] for group in family_a["GROUPS_BY_RETAINED_BASELINE_MATCHING_EDGES"])
        == 10395
    )

    witnesses = family_b["WITNESSES"]
    assert family_b["WITNESSES_SHA256"] == search.ledger_sha256(witnesses)
    assert len(witnesses) == family_b["RAW_GRAPHS"] == 1072
    assert family_b["AUTOMORPHISM_GROUP_ORDER"] == 144
    assert family_b["ORBIT_REPRESENTATIVES"] == family_b["BURNSIDE_ORBIT_COUNT"] == 20
    assert family_b["ORBIT_COVERAGE"] == "PASS"
    assert family_b["BEST_COUNT"] == max(
        o["OFFICIAL_ANY_PRIZE_OUTCOME_COUNT"] for o in family_b["ORBITS"]
    )
    assert family_b["BASELINE_ORBIT_COUNT"] == BASELINE_COUNT

    best_count = max(family_a["BEST_COUNT"], family_b["BEST_COUNT"])
    gain = best_count > BASELINE_COUNT
    assert overall["OFFICIAL_ANY_PRIZE_OUTCOME_COUNT"] == best_count
    assert overall["DELTA_VS_BASELINE"] == best_count - BASELINE_COUNT
    assert result["STRICT_GAIN"] == result["READY_FOR_N1_ASCENT"] == ("YES" if gain else "NO")
    assert result["FAMILY_STATUS"] == (search.GAIN_STATUS if gain else search.NO_GAIN_STATUS)
    assert result["GLOBAL_K20_OPTIMUM_STATUS"] == "UNKNOWN"
    assert (result["PUSH"], result["PR"], result["PRODUCTION_MUTATION"]) == (
        "NOT RUN",
        "NOT CREATED",
        "NONE",
    )


def test_best_candidate_fresh_recount() -> None:
    overall = _result()["OVERALL_BEST"]
    tickets = tuple(tuple(ticket) for ticket in overall["TICKETS"])
    fresh = evaluate_portfolio(tickets)

    assert search.portfolio_sha256(tickets) == overall["NORMALIZED_SHA256"]
    assert fresh.official_any_prize_outcome_count == overall["OFFICIAL_ANY_PRIZE_OUTCOME_COUNT"]
    assert fresh.m3_plus_draw_count == overall["M3_PLUS_DRAW_COUNT"]
    assert search.pair_overlap_profile(tickets).max_overlap == overall["MAX_TICKET_PAIR_OVERLAP"]
