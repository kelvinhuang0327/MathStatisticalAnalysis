"""Focused checks for the K20 r=4 dangerous-vector assignment certificate."""

from __future__ import annotations

from collections import Counter
from itertools import combinations, product
from math import comb
from pathlib import Path
from typing import cast

from lottolab.research.b649_k20_r4_anchor_incidence_bound_r6 import (
    anchor_incidence_profiles,
)
from lottolab.research.b649_k20_r4_dangerous_assignment_exact_r8 import (
    DANGEROUS_VECTOR_TYPES,
    analyze_dangerous_assignments,
    balanced_frequency_histogram,
    build_assignment_witness,
    load_prior_dangerous_vectors,
    minimum_component_label_use_by_count,
    minimum_labels_with_pair_overlap_at_most_one,
    pair_mass_from_frequency_histogram,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PRIOR_RESULT_PATH = (
    REPOSITORY_ROOT
    / "docs/research/matrix-native-results/"
    "b649-k20-r4-exact-anchor-realizability-r7-result.json"
)


def test_exact_dangerous_vectors_reload_from_pinned_r7_result() -> None:
    vectors = load_prior_dangerous_vectors(PRIOR_RESULT_PATH)

    assert vectors == DANGEROUS_VECTOR_TYPES
    assert len(vectors) == 3
    assert vectors[0] == (((0, 0, 0, 6), 18),)
    assert vectors[1] == (((0, 0, 0, 6), 17), ((0, 0, 1, 5), 1))
    assert vectors[2] == (((0, 0, 0, 6), 17), ((0, 1, 0, 5), 1))


def test_dangerous_assignment_witnesses_attain_exact_s2_floors() -> None:
    expected = (
        (108, 93, ((2, 15), (3, 26))),
        (107, 91, ((2, 16), (3, 25))),
        (107, 91, ((2, 16), (3, 25))),
    )

    for vector, (incidences, pair_mass, histogram) in zip(
        DANGEROUS_VECTOR_TYPES, expected, strict=True
    ):
        witness = build_assignment_witness(vector)
        assert witness.outside_pair_mass == pair_mass
        assert witness.outside_frequency_histogram == histogram
        assert witness.maximum_outside_pair_overlap <= 4
        assert witness.maximum_full_portfolio_pair_overlap <= 4
        assert witness.all_tickets_have_size_six
        assert witness.anchor_capacities == (4, 2, 2, 41)
        minimum_histogram = balanced_frequency_histogram(incidences, 41)
        assert minimum_histogram == histogram
        assert pair_mass_from_frequency_histogram(minimum_histogram) == pair_mass

    assert build_assignment_witness(DANGEROUS_VECTOR_TYPES[1]).special_anchor_label == 6
    assert build_assignment_witness(DANGEROUS_VECTOR_TYPES[2]).special_anchor_label == 4


def test_label_relabeling_toy_matches_exhaustive_assignment_census() -> None:
    label_count = 4
    ticket_count = 4
    choices = tuple(frozenset(choice) for choice in combinations(range(label_count), 2))
    assignment_classes: set[tuple[tuple[int, ...], ...]] = set()
    minimum_pair_mass: int | None = None
    admissible_assignments = 0

    for tickets in product(choices, repeat=ticket_count):
        if any(len(left & right) > 1 for left, right in combinations(tickets, 2)):
            continue
        admissible_assignments += 1
        frequencies = Counter(label for ticket in tickets for label in ticket)
        pair_mass = sum(comb(frequency, 2) for frequency in frequencies.values())
        minimum_pair_mass = (
            pair_mass
            if minimum_pair_mass is None
            else min(minimum_pair_mass, pair_mass)
        )
        columns = tuple(
            sorted(
                tuple(index for index, ticket in enumerate(tickets) if label in ticket)
                for label in range(label_count)
                if any(label in ticket for ticket in tickets)
            )
        )
        assignment_classes.add(columns)

    assert admissible_assignments == 360
    assert len(assignment_classes) == 15
    assert minimum_pair_mass == 4
    assert minimum_labels_with_pair_overlap_at_most_one(4, 8) == 4
    assert pair_mass_from_frequency_histogram(balanced_frequency_histogram(8, 4)) == 4


def test_component_dp_and_anchor_s3_produce_strict_r4_improvement() -> None:
    result = analyze_dangerous_assignments(PRIOR_RESULT_PATH)
    vectors = cast(list[dict[str, object]], result["DANGEROUS_VECTOR_RESULTS"])

    assert minimum_component_label_use_by_count(False, float("inf")) == (
        (1, 29),
        (2, 35),
        (3, 40),
        (4, 46),
        (5, 51),
        (6, 56),
    )
    assert minimum_component_label_use_by_count(True, float("inf")) == (
        (1, 28),
        (2, 34),
        (3, 39),
        (4, 45),
        (5, 50),
        (6, 55),
    )
    assert result["DANGEROUS_VECTOR_COUNT"] == 3
    assert result["REALIZABLE_VECTOR_COUNT"] == 3
    assert result["ASSIGNMENT_CLASS_COUNT"] == 18
    assert result["MANDATORY_OUTSIDE_PAIR_PENALTY"] == 8_254_694
    assert result["R4_BOUND"] == 354_332_314
    assert result["R4_STATUS"] == "TIGHTENED_OPEN_SUCCESS_B"
    assert result["SUCCESS_A"] is False
    assert result["SUCCESS_B"] is True
    assert result["FAMILY_A_RECOMPUTED_BOUND"] == 354_332_314
    assert result["FAMILY_A_BOTTLENECK_R"] == 4
    assert result["REMAINING_GAP"] == 41_092_653
    assert result["COUNT_VECTOR_CENSUS"] == (
        "REUSED_PINNED_R7_RESULT; 52,360-VECTOR CENSUS NOT RERUN"
    )
    assert [vector["ANCHOR_S3_RECOVERY"] for vector in vectors] == [
        463_680,
        493_780,
        493_780,
    ]
    assert [vector["R4_BOUND"] for vector in vectors] == [
        354_332_314,
        353_896_214,
        353_896_214,
    ]
    assert [vector["LABEL"] for vector in vectors] == [
        "18_GOOD",
        "17_GOOD_PLUS_B_ONLY",
        "17_GOOD_PLUS_A_ONLY",
    ]

    profiles = {profile.signature: profile for profile in anchor_incidence_profiles()}
    assert profiles[(0, 0, 0, 6)].triple_recovery == 25_760
    assert profiles[(0, 0, 1, 5)].triple_recovery == 55_860
    assert profiles[(0, 1, 0, 5)].triple_recovery == 55_860
    component_cases = cast(list[dict[str, object]], result["COMPONENT_CASES"])
    assert [case["PENALTY_FLOOR"] for case in component_cases] == [
        9_413_376,
        8_964_648,
        8_515_920,
        9_152_150,
        8_703_422,
        8_254_694,
    ]


__all__ = [
    "test_component_dp_and_anchor_s3_produce_strict_r4_improvement",
    "test_dangerous_assignment_witnesses_attain_exact_s2_floors",
    "test_exact_dangerous_vectors_reload_from_pinned_r7_result",
    "test_label_relabeling_toy_matches_exhaustive_assignment_census",
]
