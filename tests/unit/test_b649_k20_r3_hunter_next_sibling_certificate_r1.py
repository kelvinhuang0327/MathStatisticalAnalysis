"""Focused gates for the next-sibling Hunter class-split certificate."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from lottolab.research import b649_k20_r3_hunter_next_sibling_certificate_r1 as sibling
from lottolab.research import b649_k20_r3_hunter_tree_member_certificate_r1 as hunter
from lottolab.research.b649_k20_r3_frontier_realizability_bound_r8 import (
    _pair_event_correction_table,  # pyright: ignore[reportPrivateUsage]
)

RAW_UNION_BOUND = 360_888_220
RAW_MEMBER_BOUND = 355_722_220
RATIONAL_BOUND = 355_308_650
RATIONAL_CORRECTION = 5_579_570
FOREST_CORRECTION = 5_166_000
HOMOGENEOUS_CORRECTION = 7_372_190
CLASS_HUNTER_CORRECTION = 7_790_062
CERTIFIED_MEMBER_BOUND = 353_098_158
R3_DURABLE_BOUND = 355_734_631
OUTSIDE_FLOORS = (107_800, 568_610, 1_667_932, 3_406_165)
CORE_FLOORS = (102_536, 535_542, 1_588_965, 3_260_138)


def test_target_events_replay_the_committed_raw_bound_for_this_member_only() -> None:
    events = sibling.event_decomposition()
    ledger = sibling.r24_ledger_member()
    sizes = dict(events.residual_event_sizes)
    counts = sibling.member_counts()

    assert sibling.member_type_cells()[16] == (1, 0, 0, 5)
    assert sum(count for _, count in sibling.MEMBER_SPARSE) == 18
    assert events.raw_union_bound == RAW_UNION_BOUND
    assert sizes[16] - sizes[5] == -448
    assert ledger.member_raw_bound == ledger.member_final_bound == RAW_MEMBER_BOUND
    assert (
        events.raw_union_bound - max(events.r7_forest_floor, events.r7_pair_sum_penalty)
        == RAW_MEMBER_BOUND
    )
    assert sibling.certified_member_bound(sibling.STATE_ID, counts) == CERTIFIED_MEMBER_BOUND
    with pytest.raises(hunter.CertificateScopeError):
        sibling.certified_member_bound("state:other", counts)
    with pytest.raises(hunter.CertificateScopeError):
        sibling.certified_member_bound(sibling.STATE_ID, hunter.dense_counts(hunter.MEMBER_SPARSE))


def test_twenty_eight_rows_replay_r8_and_type16_never_lowers_a_floor() -> None:
    rows = sibling.independent_pair_rows()
    observed = sorted(
        (row.left_type, row.right_type, *row.overlap, row.residual_intersection) for row in rows
    )
    expected = sorted(
        (left, right, shared, a_only, b_only, outside, value)
        for left, right in sibling.occurring_type_pairs()
        for shared, a_only, b_only, outside, value, _quadruple in _pair_event_correction_table(
            left, right
        )
    )
    effect = sibling.build_result()["TYPE16_EFFECT"]

    assert sibling.occurring_type_pairs() == ((0, 0), (0, 5), (0, 16), (5, 5), (5, 16))
    assert len(rows) == len(expected) == 28
    assert observed == expected
    assert sibling.class_edge_counts() == (143, 10)
    assert sibling.class_pair_floors(rows) == (OUTSIDE_FLOORS, CORE_FLOORS)
    assert sibling.global_pair_floors(rows) == CORE_FLOORS
    assert effect["TYPE16_ROWS_LOWER_A_FLOOR"] is False
    assert effect["TYPE16_FLOOR_TIES"] == ["OUTSIDE_INCIDENT_0"]
    assert effect["MINIMUM_TYPE16_ROW_MARGIN_ABOVE_CLASS_FLOOR"] == 0
    # (16,16) rows are absent; adding them anyway leaves both class floors unchanged.
    extra = sibling.type_pair_rows(16, 16)
    assert sibling.class_pair_floors((*rows, *extra)) == (OUTSIDE_FLOORS, CORE_FLOORS)
    with pytest.raises(ValueError, match="outside the R3 range"):
        hunter.threshold_edge_counts((4,))


def test_collision_floor_class_tree_lemma_and_exact_census() -> None:
    certificate = sibling.build_certificate()
    classes = sibling.member_edge_classes(
        certificate.class_edge_counts, certificate.class_pair_floors
    )
    split = sibling.minimum_class_tree_correction(classes, certificate.collision_floor)
    single = sibling.minimum_class_tree_correction(
        (sibling.EdgeClass("ALL_PAIRS", 153, certificate.global_pair_floors),), 80
    )
    regressions = sibling.tree_rank_regressions(certificate.class_pair_floors)

    assert certificate.cell_incidences == (1, 4, 4, 99)
    assert certificate.cell_collision_floors == (0, 1, 1, 78)
    assert certificate.collision_floor == 80
    assert regressions["CLASS_THRESHOLD_TREE_EXHAUSTIVE_K4_LABELLINGS"] == 5 * 4**6
    assert regressions["EXACT_MASS_REDUCTION_K4_FLOORS_CHECKED"] > 0
    assert split.correction == certificate.class_hunter_correction == CLASS_HUNTER_CORRECTION
    assert sum(map(sum, split.edge_counts)) == certificate.collision_floor
    assert split.census_size > 1
    assert (
        single.correction
        == hunter.minimum_tree_correction(certificate.global_pair_floors, 80).correction
        == certificate.homogeneous_hunter_correction
        == HOMOGENEOUS_CORRECTION
    )
    # Equal to the first member's value only because its floors and Q coincide.
    prior_hunter = sibling.prior_member_record()["HUNTER_CORRECTION"]
    assert certificate.homogeneous_hunter_correction == prior_hunter
    assert sibling.minimum_class_tree_correction(classes, 79).correction <= split.correction
    with pytest.raises(AssertionError, match="nondecreasing"):
        sibling.level_thresholds((sibling.EdgeClass("BAD", 153, (5, 4, 6, 7)),))
    with pytest.raises(ValueError, match="nested"):
        sibling.class_tree_weight_floor(classes, ((0, 1, 0), (0, 0, 0)))


def test_max_combines_corrections_and_r24_correction_is_not_double_counted() -> None:
    certificate = sibling.build_certificate()
    ledger = sibling.r24_ledger_member()
    summed = (
        certificate.pair_sum_correction
        + certificate.forest_correction
        + certificate.rational_correction
        + certificate.homogeneous_hunter_correction
        + certificate.class_hunter_correction
    )

    assert certificate.rational_correction == RATIONAL_CORRECTION
    assert certificate.forest_correction == FOREST_CORRECTION
    assert certificate.certified_correction == CLASS_HUNTER_CORRECTION
    assert certificate.certified_member_bound == RAW_UNION_BOUND - CLASS_HUNTER_CORRECTION
    assert certificate.certified_member_bound == (
        ledger.member_final_bound + FOREST_CORRECTION - CLASS_HUNTER_CORRECTION
    )
    with pytest.raises(AssertionError, match="max"):
        sibling.verify_certificate(replace(certificate, certified_correction=summed))
    with pytest.raises(AssertionError, match="once"):
        sibling.verify_certificate(
            replace(
                certificate,
                certified_member_bound=ledger.member_final_bound - CLASS_HUNTER_CORRECTION,
            )
        )


def test_member_witness_is_not_excluded_by_the_certificate() -> None:
    witness = sibling.witness_analysis()
    certificate = sibling.build_certificate()

    assert witness.member_sparse == sibling.MEMBER_SPARSE
    assert (witness.replaced_type, witness.inserted_type) == (5, 16)
    assert witness.maximum_pair_overlap == witness.anchor_overlap == 3
    assert witness.residual_multiplicity == 18
    assert witness.exact_rows_match_table is True
    assert witness.collision_mass == witness.label_collision_mass
    assert witness.collision_mass >= certificate.collision_floor
    assert (
        witness.exact_tree_weight
        >= witness.floor_tree_weight
        >= witness.census_objective
        >= certificate.class_hunter_correction
    )


def test_replayed_result_strictly_improves_the_rational_bound_without_an_r3_claim() -> None:
    first = sibling.build_result()
    second = json.loads(hunter.encode(sibling.build_result()))
    bound = first["CERTIFIED_MEMBER_BOUND"]

    assert first == second
    assert first["RAW_BOUND"] == RAW_MEMBER_BOUND
    assert first["RATIONAL_BOUND"] == RATIONAL_BOUND == hunter.sibling_rational_bound()
    assert first["HUNTER_CORRECTION"] == CLASS_HUNTER_CORRECTION
    assert bound == CERTIFIED_MEMBER_BOUND
    assert first["ADDITIONAL_REDUCTION_VS_RATIONAL"] == RATIONAL_BOUND - bound > 0
    assert first["R3_DURABLE_BOUND"] == R3_DURABLE_BOUND
    assert first["R3_DURABLE_BOUND_UNCHANGED"] is True
    assert first["R3_BOUND_CLAIM"] == "NONE"
    assert first["STATE_TERM_CLAIM"] == "NONE"
    assert first["ALREADY_CERTIFIED_MEMBER"]["MEMBER_ID"] == "[0,13][5,5]"
    assert first["ALREADY_CERTIFIED_MEMBER"]["RECOMPUTED"] is False
    assert first["WITNESS_SOUNDNESS_STATUS"] == "CONSISTENT"


def test_result_artifact_replays_the_shipped_entry_point() -> None:
    text = sibling.RESULT_PATH.read_text(encoding="utf-8")
    assert json.loads(text) == sibling.build_result()
    assert text == hunter.encode(sibling.build_result())


@pytest.mark.parametrize(
    "mutated",
    [
        "residual_event_count",
        "raw_union_bound",
        "pair_rows_sha256",
        "global_pair_floors",
        "class_edge_counts",
        "outside_floor_raised",
        "outside_floor_lowered",
        "cell_incidences",
        "collision_floor",
        "class_minimizer_counts",
        "homogeneous_hunter_correction",
        "class_hunter_correction",
        "rational_correction",
        "state_id",
        "member_sparse",
        "certified_member_bound",
    ],
)
def test_each_bounded_mutation_fails_closed(mutated: str) -> None:
    certificate = sibling.build_certificate()
    outside, core = certificate.class_pair_floors
    if mutated == "residual_event_count":
        changed = replace(certificate, residual_event_count=17)
    elif mutated == "raw_union_bound":
        changed = replace(certificate, raw_union_bound=certificate.raw_union_bound + 1)
    elif mutated == "pair_rows_sha256":
        changed = replace(certificate, pair_rows_sha256="0" * 64)
    elif mutated == "global_pair_floors":
        changed = replace(certificate, global_pair_floors=outside)
    elif mutated == "class_edge_counts":
        changed = replace(certificate, class_edge_counts=(153, 0))
    elif mutated == "outside_floor_raised":
        changed = replace(
            certificate,
            class_pair_floors=((outside[0] + 1, outside[1], outside[2], outside[3]), core),
        )
    elif mutated == "outside_floor_lowered":
        changed = replace(
            certificate,
            class_pair_floors=((outside[0], outside[1] - 1, outside[2], outside[3]), core),
        )
    elif mutated == "cell_incidences":
        changed = replace(certificate, cell_incidences=(0, 5, 5, 98))
    elif mutated == "collision_floor":
        changed = replace(certificate, collision_floor=certificate.collision_floor + 1)
    elif mutated == "class_minimizer_counts":
        changed = replace(certificate, class_minimizer_counts=((80, 0, 0), (0, 0, 0)))
    elif mutated == "homogeneous_hunter_correction":
        changed = replace(
            certificate,
            homogeneous_hunter_correction=certificate.homogeneous_hunter_correction + 1,
        )
    elif mutated == "class_hunter_correction":
        changed = replace(
            certificate, class_hunter_correction=certificate.class_hunter_correction + 1
        )
    elif mutated == "rational_correction":
        changed = replace(certificate, rational_correction=certificate.rational_correction + 1)
    elif mutated == "state_id":
        changed = replace(certificate, state_id="state:other")
    elif mutated == "member_sparse":
        changed = replace(certificate, member_sparse=hunter.MEMBER_SPARSE)
    elif mutated == "certified_member_bound":
        changed = replace(
            certificate, certified_member_bound=certificate.certified_member_bound - 1
        )
    else:
        raise AssertionError(mutated)

    with pytest.raises(AssertionError):
        sibling.verify_certificate(changed)
