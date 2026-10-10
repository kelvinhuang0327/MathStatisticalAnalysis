"""R1 seven-class uniform tail correction: authority, partition, floors, screen, family max."""

from __future__ import annotations

import json
import subprocess
from functools import cache
from itertools import combinations
from math import comb
from typing import Any, cast

import pytest

from lottolab.research import b649_k20_r3_tail_seven_class_uniform_r6_certificate_r1 as r1

L = r1.TAIL_START_LOSS
MINIMIZER = (7, 2, 9, 0, 0, 0, 0)
EXPECTED_FLOORS = (
    (107_800, 88_830, 107_800, 105_560, 107_800, 98_315, 105_560),
    (88_830, 0, 65_520, 42_602, 42_210, 21_623, 19_292),
    (107_800, 65_520, 105_000, 93_380, 105_000, 98_315, 93_380),
    (105_560, 42_602, 93_380, 103_320, 93_380, 96_075, 74_536),
    (107_800, 42_210, 105_000, 93_380, 102_200, 75_005, 90_580),
    (98_315, 21_623, 98_315, 96_075, 75_005, 88_830, 72_765),
    (105_560, 19_292, 93_380, 74_536, 90_580, 72_765, 71_736),
)


@cache
def built() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(r1.encode(r1.build_result())))


def test_exact_r24_base_pins_and_authority() -> None:
    assert r1.verify_upstream_fingerprints() == r1.UPSTREAM_SHA256
    tree = subprocess.run(
        ["git", "-C", str(r1.REPO_ROOT), "rev-parse", f"{r1.BASE_HEAD}^{{tree}}"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert tree.stdout.strip() == r1.BASE_TREE
    assert r1.r24_authority()["NEXT_UNCLASSIFIED_LOSS"] == L == 9_313_997
    assert r1.r24.canonical_primitives()["K20_S1"] - 7_180_012 - L == 355_734_631


def test_source_tampering_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    for relative in r1.UPSTREAM_SHA256:
        monkeypatch.setattr(r1, "UPSTREAM_SHA256", r1.UPSTREAM_SHA256 | {relative: "0" * 64})
        with pytest.raises(AssertionError, match="R24 authority fingerprint mismatch"):
            r1.verify_upstream_fingerprints()
        monkeypatch.undo()
    r1.r24_authority.cache_clear()
    monkeypatch.setattr(r1, "START_STATE_MAX_BOUND", r1.START_STATE_MAX_BOUND + 1)
    with pytest.raises(AssertionError, match="R24 authority differs"):
        r1.r24_authority()
    monkeypatch.undo()
    r1.r24_authority.cache_clear()
    assert r1.r24_authority()["R3_BOUND"] == r1.START_R3_BOUND


def test_partition_covers_every_type_once_and_rejects_bad_partitions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    classes = r1.class_partition()
    assert sorted(index for types in classes for index in types) == list(range(30))
    assert [len(types) for types in classes] == [1, 17, 2, 2, 2, 2, 4]
    rows = list(r1.TYPE_CLASSES)
    zero_name, zero_types = rows[1]
    lost = (rows[0], (zero_name, zero_types[1:]), *rows[2:])
    duplicated = (*rows[:2], (rows[2][0], (*rows[2][1], 7)), *rows[3:])
    good_moved = (("good", (25,)), (zero_name, (0, *zero_types[:-1])), *rows[2:])
    for bad in (lost, duplicated, good_moved, tuple(rows[:-1])):
        monkeypatch.setattr(r1, "TYPE_CLASSES", bad)
        with pytest.raises(AssertionError, match="partition"):
            r1.class_partition()


def test_class_loss_ranges_bracket_every_member_type() -> None:
    losses = r1.r6.local_losses(r1.r5.anchor_incidence_profiles())
    for row in r1.class_bounds():
        members = [losses[index] for index in row.types]
        assert row.minimum_loss == min(members) and row.maximum_loss == max(members)
    assert [(row.minimum_loss, row.maximum_loss) for row in r1.class_bounds()] == [
        (0, 0),
        (2_605_148, 6_267_737),
        (442_890, 442_890),
        (1_541_960, 1_541_960),
        (831_992, 832_440),
        (3_294_935, 3_294_935),
        (1_837_556, 1_870_694),
    ]


def test_class_pair_floors_lower_bound_every_r6_type_pair() -> None:
    floors = r1.class_pair_floors()
    classes = r1.class_partition()
    for left, left_types in enumerate(classes):
        for right, right_types in enumerate(classes):
            values: list[int] = []
            for a in left_types:
                for b in right_types:
                    certificate = r1.r6.type_pair_certificate(a, b)
                    value = 0 if certificate is None else certificate.minimum_residual_intersection
                    assert r1.type_pair_floor(a, b) == value
                    values.append(value)
            assert all(floors[left][right] <= value for value in values)
            assert floors[left][right] in values
    assert floors == EXPECTED_FLOORS


def test_impossible_pairs_have_forced_overlap_and_are_not_load_bearing() -> None:
    rows = r1.impossible_type_pairs()
    assert [(a, b) for a, b, _ in rows] == [
        (7, 15),
        (10, 15),
        (11, 11),
        (11, 14),
        (11, 15),
        (13, 15),
        (14, 14),
        (14, 15),
        (15, 15),
        (15, 24),
    ]
    assert all(forced > r1.MAXIMUM_PAIR_OVERLAP for *_, forced in rows)
    classes = r1.class_partition()
    excluded = tuple(
        tuple(
            min(
                r1.type_pair_floor(a, b)
                for a in left
                for b in right
                if r1.r6.type_pair_certificate(a, b) is not None
            )
            for right in classes
        )
        for left in classes
    )
    assert excluded == r1.class_pair_floors()


def test_forest_identity_ceiling_divisor_and_max_combination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    forest = r1.r6.PRIOR_FOREST_PENALTY_BY_GOOD_COUNT
    assert r1.verify_forest_identity() == forest
    assert r1.r6.PAIR_MULTIPLICITY_DIVISOR == 9
    monkeypatch.setattr(r1.r6, "PRIOR_FOREST_PENALTY_BY_GOOD_COUNT", (*forest[:7], 1, *forest[8:]))
    with pytest.raises(AssertionError, match="forest correction differs"):
        r1.verify_forest_identity()
    monkeypatch.undo()
    monkeypatch.setattr(r1.r6, "PAIR_MULTIPLICITY_DIVISOR", 8)
    with pytest.raises(AssertionError, match="divisor changed"):
        r1.verify_forest_identity()
    monkeypatch.undo()
    row = r1.composition_bound(MINIMIZER)
    hand_mass = 21 * 107_800 + 36 * 105_000 + 14 * 88_830 + 63 * 107_800 + 18 * 65_520
    assert row.pair_floor_mass == hand_mass == 15_258_180
    assert row.pair_correction == 1_695_354 == hand_mass // 9 + 1
    assert row.forest_correction == 1_148_000
    assert row.correction == row.lower_total == 1_695_354
    forest_owned = r1.composition_bound((12, 6, 0, 0, 0, 0, 0))
    assert forest_owned.pair_correction == 1_501_174
    assert forest_owned.correction == forest_owned.forest_correction == 4_592_000
    assert forest_owned.lower_total == 15_630_888 - L + 4_592_000


def test_reachability_screen_drops_only_compositions_below_the_tail() -> None:
    certificate = r1.uniform_certificate()
    assert certificate.composition_count == comb(24, 6) == 134_596
    assert certificate.admitted_count == 133_663
    assert certificate.screened_count == 933
    assert certificate.screened_maximum_loss == 9_313_864 < L
    maxima = [row.maximum_loss for row in r1.class_bounds()]
    minima = [row.minimum_loss for row in r1.class_bounds()]
    unreachable = straddling = 0
    for counts in r1.compositions(18, 7):
        top = sum(count * value for count, value in zip(counts, maxima, strict=True))
        bottom = sum(count * value for count, value in zip(counts, minima, strict=True))
        unreachable += top < L
        straddling += bottom < L <= top
    assert unreachable == 933
    row = r1.composition_bound(MINIMIZER)
    assert straddling > 0 and row.minimum_loss < L <= row.maximum_loss


def test_uniform_minimum_replays_through_independent_stars_and_bars() -> None:
    floors = r1.class_pair_floors()
    bounds = r1.class_bounds()
    forest = r1.r6.PRIOR_FOREST_PENALTY_BY_GOOD_COUNT
    best: int | None = None
    argmins: list[tuple[int, ...]] = []
    for bars in combinations(range(24), 6):
        cuts = (-1, *bars, 24)
        counts = tuple(cuts[k + 1] - cuts[k] - 1 for k in range(7))
        if sum(c * row.maximum_loss for c, row in zip(counts, bounds, strict=True)) < L:
            continue
        mass = sum(
            (comb(counts[a], 2) if a == b else counts[a] * counts[b]) * floors[a][b]
            for a in range(7)
            for b in range(a, 7)
        )
        low = sum(c * row.minimum_loss for c, row in zip(counts, bounds, strict=True))
        value = max(0, low - L) + max(-(-mass // 9), forest[counts[0]])
        if best is None or value < best:
            best, argmins = value, [counts]
        elif value == best:
            argmins.append(counts)
    certificate = r1.uniform_certificate()
    assert best == certificate.minimum == 1_695_354
    assert argmins == [row.counts for row in certificate.minimizers] == [MINIMIZER]


def test_minimizer_family_is_legal_and_never_undercuts_the_uniform_bound() -> None:
    assert built()["MINIMIZER_REALIZATION"] == [
        {
            "class_counts": list(MINIMIZER),
            "type_vectors": 1_530,
            "tail_vectors": 1_520,
            "aggregate_infeasible_tail_vectors": 100,
            "minimum_actual_surplus_plus_correction": 1_803_527,
            "relaxation_gap": 108_173,
            "argmin_vectors": [
                [[0, 7], [4, 9], [20, 1], [25, 1]],
                [[0, 7], [1, 9], [20, 1], [25, 1]],
            ],
            "argmin_support_witness_sha256": (
                "2f3a6d1eb5016bf000dab4ba4efd6b39ee3ea3902256d31827e1cf0cbad04ad5"
            ),
            "argmin_witness_status": "R8_VALIDATED",
        }
    ]
    probe = r1.r24.dense([[0, 7], [4, 9], [20, 1], [25, 1]])
    witness = r1.r12.construct_support_witness(probe)
    assert witness is not None and r1.r8.validate_support_assignment(probe, witness)
    envelope = r1.r6.type_count_envelope(probe)
    assert envelope.local_loss - L + envelope.combined_pair_penalty == 1_803_527


def test_r24_realized_vectors_never_undercut_the_relaxation() -> None:
    assert built()["R24_VECTOR_CROSS_CHECK"] == {
        "checked_vectors": 35_708,
        "eliminated_vectors": 4,
        "violations": 0,
        "tight_vectors": 26_260,
    }


def test_family_max_is_recomputed_from_every_committed_term() -> None:
    result = built()
    assert result["UNIFORM_CORRECTION"] == result["TAIL_DROP"] == 1_695_354
    assert result["FINAL_TAIL_BOUND"] == 372_228_640 - 7_180_012 - L - 1_695_354 == 354_039_277
    assert result["FAMILY_MAX_RECOMPUTATION"] == {
        "STATE_MAX_BOUND": 355_726_896,
        "UNCLASSIFIED_TAIL_BOUND": 354_039_277,
        "MAX_CLASSIFIED_TAIL_VECTOR_BOUND": 355_468_904,
        "R3_BOUND": 355_726_896,
        "OWNER_IDS": ["state:s2-13548976-s3-951748"],
    }
    assert result["FINAL_R3_BOUND"] == 355_726_896 and result["R3_DROP"] == 7_735
    assert result["FINAL_BOUND_OWNER_CLASS"] == "state"
    assert result["REMAINING_GAP"] == 355_726_896 - 313_263_888
    assert (result["STATE_TERM_COUNT"], result["CLASSIFIED_TERM_COUNT"]) == (23, 56_550)
    tail = r1.r24.TAIL_ID
    states = (("state:a", 10), ("state:b", 7))
    classified = (("vector:x", 9),)
    for term, expected_bound, expected_owners in (
        (11, 11, [tail]),
        (5, 10, ["state:a"]),
        (10, 10, ["state:a", tail]),
    ):
        family = r1.family_maximum(term, states, classified)
        assert (family["R3_BOUND"], family["OWNER_IDS"]) == (expected_bound, expected_owners)
    classified_owned = r1.family_maximum(5, (("state:b", 7),), classified)
    assert (classified_owned["R3_BOUND"], classified_owned["OWNER_IDS"]) == (9, ["vector:x"])


def test_stored_result_replays_exactly() -> None:
    stored = r1.RESULT_PATH.read_text(encoding="utf-8")
    assert r1.encode(built()) == stored
    assert json.loads(stored)["TASK_STATUS"] == "CERTIFIED_UNIFORM_TAIL_CORRECTION"
