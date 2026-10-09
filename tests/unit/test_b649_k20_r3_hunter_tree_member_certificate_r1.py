"""Focused gates for the single-member Hunter spanning-tree certificate."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from lottolab.research import b649_k20_r3_hunter_tree_member_certificate_r1 as hunter
from lottolab.research.b649_k20_r3_frontier_realizability_bound_r8 import (
    _pair_event_correction_table,  # pyright: ignore[reportPrivateUsage]
)

PHI_FLOORS = (102_536, 535_542, 1_588_965, 3_260_138)
HUNTER_CORRECTION = 7_372_190
CERTIFIED_MEMBER_BOUND = 353_516_478
RAW_MEMBER_BOUND = 355_722_668
EXISTING_RATIONAL_BOUND = 355_405_421
SIBLING_THRESHOLD = 355_308_650
NEXT_REGION_THRESHOLD = 355_274_920


def test_residual_definition_and_raw_bound_hold_for_this_member_only() -> None:
    events = hunter.event_decomposition()
    ledger = hunter.r24_ledger_member()
    counts = hunter.dense_counts(hunter.MEMBER_SPARSE)
    result = hunter.build_result()

    assert sum(count for _, count in hunter.MEMBER_SPARSE) == 18
    assert events.residual_sum > 0
    assert "R_C = E_C minus (E_A union E_B)" in result["EVENT_DEFINITION"]["RESIDUAL_EVENT"]
    assert ledger.member_raw_bound == result["R24_LEDGER"]["MEMBER_RAW_BOUND"] == RAW_MEMBER_BOUND
    assert (
        events.raw_union_bound - max(events.r7_forest_floor, events.r7_pair_sum_penalty)
        == RAW_MEMBER_BOUND
    )
    assert hunter.certified_member_bound(hunter.STATE_ID, counts) == CERTIFIED_MEMBER_BOUND
    with pytest.raises(hunter.CertificateScopeError):
        hunter.certified_member_bound("state:other", counts)
    shifted = list(counts)
    shifted[0] -= 1
    with pytest.raises(hunter.CertificateScopeError):
        hunter.certified_member_bound(hunter.STATE_ID, shifted)
    with pytest.raises(AssertionError, match="18"):
        hunter.event_decomposition(((0, 12), (5, 5)))


def test_twenty_pair_rows_match_the_r8_table_and_phi_floors() -> None:
    rows = hunter.independent_pair_rows()
    observed = sorted(
        (row.left_type, row.right_type, *row.overlap, row.residual_intersection) for row in rows
    )
    expected = sorted(
        (left, right, shared, a_only, b_only, outside, value)
        for left, right in hunter.member_type_pairs()
        for shared, a_only, b_only, outside, value, _quadruple in _pair_event_correction_table(
            left, right
        )
    )

    assert len(rows) == len(expected) == 20
    assert observed == expected
    assert hunter.pair_floor_by_overlap(rows) == PHI_FLOORS
    assert hunter.family_pair_overlap_ceiling() == 3
    assert all(row.total_overlap <= hunter.family_pair_overlap_ceiling() for row in rows)
    with pytest.raises(ValueError, match="outside the R3 range"):
        hunter.threshold_edge_counts((4,))


def test_collision_floor_and_threshold_rank_minimum_are_universal() -> None:
    certificate = hunter.build_certificate()
    tree = hunter.minimum_tree_correction(certificate.pair_floors, certificate.collision_floor)

    assert certificate.collision_floor >= 80
    assert tree.census_size > 1
    assert tree.correction == certificate.hunter_correction == HUNTER_CORRECTION
    assert hunter.rank_floor(tree.edge_counts[0]) == tree.rank_floors[0]
    hunter.verify_rank_floor_algebra()
    hunter.verify_certificate(certificate)


def test_max_combines_corrections_and_a_sum_is_rejected() -> None:
    certificate = hunter.build_certificate()
    corrections = {
        "R6_PAIR_SUM": certificate.pair_sum_correction,
        "R5_FOREST": certificate.forest_correction,
        "R14_RATIONAL": certificate.rational_correction,
        "HUNTER_TREE": certificate.hunter_correction,
    }
    summed = sum(corrections.values())

    assert hunter.combine_corrections(corrections) == certificate.certified_correction
    assert certificate.certified_correction == HUNTER_CORRECTION
    assert summed != certificate.certified_correction
    with pytest.raises(AssertionError, match="max"):
        hunter.verify_certificate(replace(certificate, certified_correction=summed))


def test_eighteen_winner_refutes_cap_17_and_stays_above_the_bound() -> None:
    witness = hunter.cap17_witness_analysis()
    certificate = hunter.build_certificate()
    result = hunter.build_result()

    assert witness.residual_multiplicity == 18
    assert witness.exact_rows_match_table is True
    assert witness.exact_tree_weight >= certificate.hunter_correction
    assert witness.floor_tree_weight >= certificate.hunter_correction
    assert witness.collision_mass >= certificate.collision_floor
    with pytest.raises(hunter.MultiplicityCapRefuted):
        hunter.require_multiplicity_cap(17)
    assert hunter.require_multiplicity_cap(18) == 18
    assert result["NU_LE_17"] == "\u03bd <= 17 REFUTED"
    assert "\u03bd <= 17 REFUTED" in hunter.encode(result)
    assert result["CAP17_COUNTEREXAMPLE_STATUS"] == "REPRODUCED_NU_18_CAP17_REFUTED"
    assert result["WITNESS_SOUNDNESS_STATUS"] == "CONSISTENT"
    assert result["R3_BOUND_CLAIM"] == "NONE"
    assert result["STATE_TERM_CLAIM"] == "NONE"


def test_replayed_certificate_crosses_both_thresholds() -> None:
    first = hunter.build_result()
    second = json.loads(hunter.encode(hunter.build_result()))
    bound = first["CERTIFIED_MEMBER_BOUND"]

    assert first == second
    assert bound == CERTIFIED_MEMBER_BOUND
    assert first["HUNTER_CORRECTION"] == HUNTER_CORRECTION
    assert first["EXISTING_RATIONAL_BOUND"] == EXISTING_RATIONAL_BOUND
    assert first["R24_LEDGER"]["MEMBER_RAW_BOUND"] == RAW_MEMBER_BOUND
    assert bound < SIBLING_THRESHOLD
    assert bound < NEXT_REGION_THRESHOLD
    assert bound < first["EXISTING_RATIONAL_BOUND"]
    assert first["ADDITIONAL_REDUCTION"] == first["EXISTING_RATIONAL_BOUND"] - bound
    assert first["ADDITIONAL_REDUCTION"] > 0
    assert first["PAIR_OVERLAP_COVERAGE"]["FAMILY_SOURCE_CEILING"] == 3
    events = hunter.event_decomposition()
    assert bound == events.raw_union_bound - first["HUNTER_CORRECTION"]
    assert bound == RAW_MEMBER_BOUND + first["CORRECTIONS"]["R5_FOREST"] - HUNTER_CORRECTION


def test_result_artifact_replays_the_shipped_entry_point() -> None:
    text = hunter.RESULT_PATH.read_text(encoding="utf-8")
    assert json.loads(text) == hunter.build_result()
    assert text == hunter.encode(hunter.build_result())


@pytest.mark.parametrize(
    "mutated",
    [
        "residual_event_count",
        "raw_union_bound",
        "pair_floors",
        "collision_floor",
        "hunter_correction",
        "summed_correction",
        "state_id",
        "member_sparse",
        "certified_member_bound",
    ],
)
def test_each_bounded_mutation_fails_closed(mutated: str) -> None:
    certificate = hunter.build_certificate()
    if mutated == "residual_event_count":
        changed = replace(certificate, residual_event_count=17)
    elif mutated == "raw_union_bound":
        changed = replace(certificate, raw_union_bound=certificate.raw_union_bound + 1)
    elif mutated == "pair_floors":
        changed = replace(
            certificate,
            pair_floors=(
                certificate.pair_floors[0] + 1,
                certificate.pair_floors[1],
                certificate.pair_floors[2],
                certificate.pair_floors[3],
            ),
        )
    elif mutated == "collision_floor":
        changed = replace(certificate, collision_floor=certificate.collision_floor - 1)
    elif mutated == "hunter_correction":
        changed = replace(certificate, hunter_correction=certificate.hunter_correction - 1)
    elif mutated == "summed_correction":
        changed = replace(
            certificate,
            certified_correction=(
                certificate.pair_sum_correction
                + certificate.forest_correction
                + certificate.rational_correction
                + certificate.hunter_correction
            ),
        )
    elif mutated == "state_id":
        changed = replace(certificate, state_id="state:other")
    elif mutated == "member_sparse":
        changed = replace(certificate, member_sparse=((0, 12), (5, 6)))
    elif mutated == "certified_member_bound":
        changed = replace(
            certificate, certified_member_bound=certificate.certified_member_bound + 1
        )
    else:
        raise AssertionError(mutated)

    with pytest.raises(AssertionError):
        hunter.verify_certificate(changed)
