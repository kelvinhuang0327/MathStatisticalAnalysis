# pyright: reportMissingTypeStubs=false

"""Certified higher-order bounds for the nonlinear K10 p=4..14 families.

The certificate uses the exact local intersection count for each three-ticket
set.  It conditions on the full pair-multiplicity histogram and the exact
number of triple labels occupying each pair-multiplicity class.  Repeated
incidence degrees are relaxed over every ticket degree in 0..6 with total 18;
the stored duals are uniform over those degree profiles.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from fractions import Fraction
from itertools import pairwise
from math import comb
from pathlib import Path
from typing import Any, cast

from lottolab.research.b649_k10_profile_42_3_4_exact_closure_r1 import (
    INCUMBENT_OUTCOME_COUNT,
    S1,
    _triple_event_table,  # pyright: ignore[reportPrivateUsage]
    pair_event_counts,
)

TASK_ID = "B649_K10_NONLINEAR_P4_P14_HIGHER_ORDER_BOUND_R1"
TICKET_COUNT = 10
TICKET_SIZE = 6
OVERLAP_MASS = 15
TRIPLE_LABEL_COUNT = 4
REPEATED_INCIDENCE_COUNT = 18
P_MIN = 4
P_MAX = 14
PREVIOUS_PROFILE_BOUND = 181_947_724
PRIOR_CLOSED_P3_BOUND = 173_828_788
PRIOR_CLOSED_P15_LINEAR_BOUND = 175_977_872
DEFAULT_RESULT_PATH = Path(
    "docs/research/matrix-native-results/"
    "b649-k10-nonlinear-p4-p14-higher-order-bound-r1.json"
)

_EXPECTED_S2_MINIMA = (
    26_563_278,
    21_661_710,
    19_701_990,
    17_742_270,
    16_434_516,
    15_778_728,
    15_122_940,
    14_467_152,
    13_811_364,
    13_155_576,
    12_499_788,
)


def pair_multiplicity_histograms(occupied_pairs: int) -> tuple[tuple[int, ...], ...]:
    """Enumerate all 0..5 pair-multiplicity histograms with mass 15 and p edges."""

    if type(occupied_pairs) is not int or not P_MIN <= occupied_pairs <= P_MAX:
        raise ValueError("occupied-pair count must be in 4..14")

    found: list[tuple[int, ...]] = []

    def visit(multiplicity: int, pairs_left: int, mass_left: int, positive: list[int]) -> None:
        if multiplicity == TICKET_SIZE:
            if pairs_left == 0 and mass_left == 0:
                found.append((comb(TICKET_COUNT, 2) - occupied_pairs, *positive))
            return
        maximum = min(pairs_left, mass_left // multiplicity)
        for count in range(maximum + 1):
            visit(
                multiplicity + 1,
                pairs_left - count,
                mass_left - multiplicity * count,
                [*positive, count],
            )

    visit(1, occupied_pairs, OVERLAP_MASS, [])
    return tuple(found)


def balanced_pair_multiplicity_histogram(occupied_pairs: int) -> tuple[int, ...]:
    """Return the discrete-convex minimizer for S2 at fixed p and overlap mass."""

    if type(occupied_pairs) is not int or not P_MIN <= occupied_pairs <= P_MAX:
        raise ValueError("occupied-pair count must be in 4..14")
    base, remainder = divmod(OVERLAP_MASS, occupied_pairs)
    counts = [0] * TICKET_SIZE
    counts[0] = comb(TICKET_COUNT, 2) - occupied_pairs
    counts[base] = occupied_pairs - remainder
    if remainder:
        counts[base + 1] = remainder
    return tuple(counts)


def minimum_s2_rows() -> tuple[dict[str, object], ...]:
    """Compute the strongest pair-only convex lower bound for each p-family."""

    event_counts = pair_event_counts()
    increments = tuple(
        event_counts[index + 1] - event_counts[index] for index in range(5)
    )
    if any(left > right for left, right in pairwise(increments)):
        raise AssertionError("pair-event counts must be discretely convex")

    result: list[dict[str, object]] = []
    for occupied in range(P_MIN, P_MAX + 1):
        histogram = balanced_pair_multiplicity_histogram(occupied)
        minimum_s2 = sum(
            count * event_counts[multiplicity]
            for multiplicity, count in enumerate(histogram)
        )
        expected = _EXPECTED_S2_MINIMA[occupied - P_MIN]
        if minimum_s2 != expected:
            raise AssertionError("the exact convex S2 table changed")
        result.append(
            {
                "occupied_pairs": occupied,
                "balanced_histogram_n0_to_n5": list(histogram),
                "minimum_s2": minimum_s2,
            }
        )
    return tuple(result)


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return cast(Mapping[str, object], value)


def _integer_list(value: object, field: str, length: int) -> tuple[int, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must contain {length} integers")
    items = cast(list[object], value)
    if len(items) != length:
        raise ValueError(f"{field} must contain {length} integers")
    if any(type(item) is not int for item in items):
        raise ValueError(f"{field} must contain only integers")
    return tuple(cast(list[int], items))


def _fraction_list(value: object, field: str, length: int) -> tuple[Fraction, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must contain {length} rational strings")
    items = cast(list[object], value)
    if len(items) != length:
        raise ValueError(f"{field} must contain {length} rational strings")
    if any(not isinstance(item, str) for item in items):
        raise ValueError(f"{field} must contain rational strings")
    try:
        return tuple(Fraction(cast(str, item)) for item in items)
    except (ValueError, ZeroDivisionError) as error:
        raise ValueError(f"{field} contains an invalid rational") from error


def _local_event_patterns() -> tuple[tuple[tuple[int, int, int], int, int], ...]:
    """Return exact local Venn rows, with pair order quotiented by symmetry."""

    patterns: dict[tuple[tuple[int, int, int], int], int] = {}
    for ab, ac, bc, common, events in _triple_event_table():
        pair_overlaps = cast(tuple[int, int, int], tuple(sorted((ab, ac, bc))))
        key = (pair_overlaps, common)
        previous = patterns.setdefault(key, events)
        if previous != events:
            raise AssertionError("three-ticket intersection counts must be symmetric")
    return tuple(
        (overlaps, common, events)
        for (overlaps, common), events in sorted(patterns.items())
    )


def _dual_parts(dual: Mapping[str, object]) -> tuple[Fraction, ...]:
    row_count = dual.get("row_count")
    common_triples = dual.get("common_triple_labels")
    degree_total = dual.get("degree_vertex_total")
    degree_incidence = dual.get("degree_incidence_total")
    if any(
        not isinstance(value, str)
        for value in (row_count, common_triples, degree_total, degree_incidence)
    ):
        raise ValueError("scalar dual coefficients must be rational strings")
    try:
        scalars = tuple(
            Fraction(cast(str, value))
            for value in (row_count, common_triples, degree_total, degree_incidence)
        )
    except (ValueError, ZeroDivisionError) as error:
        raise ValueError("scalar dual coefficient is invalid") from error
    pair_classes = _fraction_list(
        dual.get("pair_multiplicity_classes"), "pair_multiplicity_classes", 6
    )
    triple_capacities = _fraction_list(
        dual.get("triple_pair_capacity_classes"), "triple_pair_capacity_classes", 6
    )
    degree_classes = _fraction_list(
        dual.get("degree_classes"), "degree_classes", 7
    )
    return (
        scalars[0],
        *pair_classes,
        scalars[1],
        *triple_capacities,
        *degree_classes,
        scalars[2],
        scalars[3],
    )


def _local_degree_floors(
    overlaps: tuple[int, int, int], common: int
) -> tuple[int, int, int]:
    """Minimum repeated-label incidence at each ticket in a local triple."""

    ab, ac, bc = overlaps
    return (ab + ac - common, ab + bc - common, ac + bc - common)


def verify_histogram_certificate(record: Mapping[str, object]) -> dict[str, object]:
    """Verify one exact rational S3 dual and return its derived Bonferroni bound."""

    counts = _integer_list(
        record.get("pair_multiplicity_histogram_n0_to_n5"),
        "pair_multiplicity_histogram_n0_to_n5",
        6,
    )
    occupied = sum(counts[1:])
    if not P_MIN <= occupied <= P_MAX:
        raise ValueError("certificate is outside the p=4..14 family")
    if sum(counts) != comb(TICKET_COUNT, 2) or sum(
        multiplicity * count for multiplicity, count in enumerate(counts)
    ) != OVERLAP_MASS:
        raise ValueError("pair histogram violates the fixed 45-pair, mass-15 profile")

    dual = _mapping(record.get("dual_certificate"), "dual_certificate")
    coefficients = _dual_parts(dual)
    if len(coefficients) != 23:
        raise AssertionError("unexpected degree-conditioned dual width")

    # Equality-slack variables for triple-label pair incidences require these
    # capacity multipliers to be nonnegative.
    triple_capacity_duals = coefficients[8:14]
    if any(value < 0 for value in triple_capacity_duals):
        raise ValueError("triple-pair capacity duals must be nonnegative")

    # A repeated label incident to A and B or A and C contributes at least
    # ab+ac-common repeated incidences at A. The local degree-conditioned
    # majorant is verified uniformly for every allowed degree tuple up to six.
    degree_duals = coefficients[14:21]
    for overlaps, common, events in _local_event_patterns():
        degree_floors = _local_degree_floors(overlaps, common)
        if any(degree < 0 or degree > TICKET_SIZE for degree in degree_floors):
            raise ValueError("local intersection is incompatible with ticket degree 0..6")
        pair_class_counts = tuple(overlaps.count(multiplicity) for multiplicity in range(6))
        left = (
            coefficients[0]
            + sum(
                coefficients[1 + multiplicity] * count
                for multiplicity, count in enumerate(pair_class_counts)
            )
            + coefficients[7] * common
            + sum(
                coefficients[8 + multiplicity] * common * count
                for multiplicity, count in enumerate(pair_class_counts)
            )
        )
        minimum_degree_term = sum(
            min(degree_duals[minimum:]) for minimum in degree_floors
        )
        if left + minimum_degree_term < events:
            raise ValueError("dual certificate fails a degree-conditioned local event row")

    # The degree-class columns use the exact repeated-incidence totals: ten
    # vertices and eighteen incidences, with each ticket degree in 0..6.
    degree_class_duals = coefficients[14:21]
    degree_vertex_dual, degree_incidence_dual = coefficients[21:23]
    degree_column_values = tuple(
        -36 * degree_class_duals[degree]
        + degree_vertex_dual
        + degree * degree_incidence_dual
        for degree in range(7)
    )
    if any(value < 0 for value in degree_column_values):
        raise ValueError("dual certificate fails a repeated-incidence degree column")

    pair_counts = pair_event_counts()
    s2 = sum(counts[multiplicity] * pair_counts[multiplicity] for multiplicity in range(6))
    s3_dual_bound = (
        120 * coefficients[0]
        + sum(
            8 * counts[multiplicity] * coefficients[1 + multiplicity]
            for multiplicity in range(6)
        )
        + TRIPLE_LABEL_COUNT * coefficients[7]
        + sum(
            multiplicity
            * counts[multiplicity]
            * coefficients[8 + multiplicity]
            for multiplicity in range(6)
        )
        + 10 * degree_vertex_dual
        + REPEATED_INCIDENCE_COUNT * degree_incidence_dual
    )
    s3_integer_upper = s3_dual_bound.numerator // s3_dual_bound.denominator
    outcome_upper = S1 - s2 + s3_integer_upper

    expected: dict[str, object] = {
        "occupied_pairs": occupied,
        "s2": s2,
        "s3_upper_rational": str(s3_dual_bound),
        "s3_integer_upper": s3_integer_upper,
        "u3_upper": outcome_upper,
    }
    for key, expected_value in expected.items():
        if record.get(key) != expected_value:
            raise ValueError(f"certificate record has an incorrect {key}")
    return expected


def verify_bound_artifact(payload: object) -> tuple[dict[str, object], ...]:
    """Verify completeness, every exact dual, and every p-family maximum."""

    artifact = _mapping(payload, "artifact")
    if artifact.get("task_id") != TASK_ID:
        raise ValueError("artifact task id does not match")
    certificates_value = artifact.get("histogram_certificates")
    if not isinstance(certificates_value, list):
        raise ValueError("histogram_certificates must be a list")
    raw_certificates = cast(list[object], certificates_value)
    certificates = tuple(
        _mapping(value, "histogram certificate") for value in raw_certificates
    )

    expected_histograms = {
        histogram
        for occupied in range(P_MIN, P_MAX + 1)
        for histogram in pair_multiplicity_histograms(occupied)
    }
    certificates_by_histogram: dict[tuple[int, ...], Mapping[str, object]] = {}
    for certificate in certificates:
        histogram = _integer_list(
            certificate.get("pair_multiplicity_histogram_n0_to_n5"),
            "pair_multiplicity_histogram_n0_to_n5",
            6,
        )
        if histogram in certificates_by_histogram:
            raise ValueError("duplicate pair-multiplicity histogram certificate")
        certificates_by_histogram[histogram] = certificate
        verify_histogram_certificate(certificate)
    if set(certificates_by_histogram) != expected_histograms:
        raise ValueError("histogram certificates are incomplete or out of scope")

    s2_rows_value = artifact.get("p_family_bounds")
    if not isinstance(s2_rows_value, list):
        raise ValueError("p_family_bounds must be a list")
    raw_s2_rows = cast(list[object], s2_rows_value)
    s2_rows = tuple(_mapping(row, "p-family bound") for row in raw_s2_rows)
    if len(s2_rows) != P_MAX - P_MIN + 1:
        raise ValueError("p_family_bounds must cover p=4..14 exactly")

    result: list[dict[str, object]] = []
    expected_s2 = minimum_s2_rows()
    verified = {
        histogram: verify_histogram_certificate(certificate)
        for histogram, certificate in certificates_by_histogram.items()
    }
    for index, occupied in enumerate(range(P_MIN, P_MAX + 1)):
        row = s2_rows[index]
        convex = expected_s2[index]
        histogram = balanced_pair_multiplicity_histogram(occupied)
        if (
            row.get("occupied_pairs") != occupied
            or row.get("minimum_s2") != convex["minimum_s2"]
            or row.get("balanced_histogram_n0_to_n5") != list(histogram)
        ):
            raise ValueError("p-family row has an incorrect convex S2 minimum")
        family_records = [
            (pair_histogram, verified[pair_histogram])
            for pair_histogram in certificates_by_histogram
            if sum(pair_histogram[1:]) == occupied
        ]
        worst_histogram, worst = max(
            family_records, key=lambda item: cast(int, item[1]["u3_upper"])
        )
        family_histogram = _integer_list(
            row.get("maximizing_pair_multiplicity_histogram_n0_to_n5"),
            "maximizing_pair_multiplicity_histogram_n0_to_n5",
            6,
        )
        expected_family = {
            "histograms_examined": len(pair_multiplicity_histograms(occupied)),
            "maximum_u3_upper": worst["u3_upper"],
            "maximizing_pair_multiplicity_histogram_n0_to_n5": list(worst_histogram),
            "s2_at_maximum": worst["s2"],
            "s3_integer_upper_at_maximum": worst["s3_integer_upper"],
            "closed_at_incumbent": cast(int, worst["u3_upper"])
            <= INCUMBENT_OUTCOME_COUNT,
        }
        if family_histogram not in certificates_by_histogram:
            raise ValueError("maximizing histogram lacks a certificate")
        if family_histogram != worst_histogram:
            raise ValueError("p-family row names the wrong maximizing histogram")
        if any(
            row.get(key) != expected_value
            for key, expected_value in expected_family.items()
        ):
            raise ValueError("p-family maximum does not match its certificates")
        if worst["u3_upper"] != max(
            cast(int, item["u3_upper"]) for _, item in family_records
        ):
            raise AssertionError("p-family maximum computation is inconsistent")
        result.append(
            {
                "occupied_pairs": occupied,
                "minimum_s2": convex["minimum_s2"],
                "histograms_examined": expected_family["histograms_examined"],
                "maximum_u3_upper": worst["u3_upper"],
                "maximizing_pair_multiplicity_histogram_n0_to_n5": family_histogram,
                "s2_at_maximum": worst["s2"],
                "s3_integer_upper_at_maximum": worst["s3_integer_upper"],
                "closed_at_incumbent": expected_family["closed_at_incumbent"],
            }
        )

    if any(row.get("closed_at_incumbent") is not True for row in result):
        raise ValueError("one or more nonlinear p-families remain open")

    prior = _mapping(
        artifact.get("prior_closed_profile_families"),
        "prior_closed_profile_families",
    )
    p3_upper = prior.get("p3_upper")
    p15_upper = prior.get("p15_linear_upper")
    if type(p3_upper) is not int or type(p15_upper) is not int:
        raise ValueError("prior closed-family bounds must be integers")
    nonlinear_upper = max(cast(int, row["maximum_u3_upper"]) for row in result)
    profile_upper = max(p3_upper, nonlinear_upper, p15_upper)
    if (
        artifact.get("new_profile_bound") != profile_upper
        or artifact.get("incumbent") != INCUMBENT_OUTCOME_COUNT
        or profile_upper > INCUMBENT_OUTCOME_COUNT
        or artifact.get("global_optimum_status") != "PROVEN"
        or artifact.get("remaining_gap") != 0
    ):
        raise ValueError("profile-level closure summary does not follow from the bounds")
    return tuple(result)


def _degree_local_configurations() -> tuple[tuple[int, ...], ...]:
    """Expand each exact local event row by compatible ticket degrees 0..6."""

    configurations: list[tuple[int, ...]] = []
    for ab, ac, bc, common, _ in _triple_event_table():
        degree_floors = (ab + ac - common, ab + bc - common, ac + bc - common)
        if any(degree < 0 or degree > TICKET_SIZE for degree in degree_floors):
            raise AssertionError("local Venn row violates the ticket incidence cap")
        configurations.extend(
            (ab, ac, bc, common, degree_a, degree_b, degree_c)
            for degree_a in range(degree_floors[0], TICKET_SIZE + 1)
            for degree_b in range(degree_floors[1], TICKET_SIZE + 1)
            for degree_c in range(degree_floors[2], TICKET_SIZE + 1)
        )
    return tuple(dict.fromkeys(configurations))


def _derive_histogram_certificate(histogram: tuple[int, ...]) -> dict[str, object]:
    """Solve one small degree-conditioned S3 LP and retain its exact dual."""

    from ortools.linear_solver import pywraplp

    solver_api = cast(Any, pywraplp)
    solver = solver_api.Solver.CreateSolver("GLOP")
    if solver is None:
        raise RuntimeError("OR-Tools GLOP is unavailable")
    solver.SetNumThreads(1)

    event_counts = {
        (ab, ac, bc, common): events
        for ab, ac, bc, common, events in _triple_event_table()
    }
    local = _degree_local_configurations()
    local_variables = [
        solver.NumVar(0.0, solver.infinity(), f"local_{index}")
        for index in range(len(local))
    ]
    triple_pair_slacks = [
        solver.NumVar(0.0, solver.infinity(), f"triple_pair_slack_{multiplicity}")
        for multiplicity in range(6)
    ]
    degree_histogram = [
        solver.NumVar(0.0, solver.infinity(), f"degree_count_{degree}")
        for degree in range(TICKET_SIZE + 1)
    ]
    constraints: list[Any] = []

    def add_equality(rhs: int, columns: Sequence[tuple[Any, int]]) -> None:
        constraint = solver.Constraint(float(rhs), float(rhs))
        for variable, coefficient in columns:
            if coefficient:
                constraint.SetCoefficient(variable, float(coefficient))
        constraints.append(constraint)

    # There are C(10,3) local ticket triples; each pair appears in eight.
    add_equality(120, [(variable, 1) for variable in local_variables])
    for multiplicity in range(6):
        add_equality(
            8 * histogram[multiplicity],
            [
                (
                    local_variables[index],
                    sum(value == multiplicity for value in configuration[:3]),
                )
                for index, configuration in enumerate(local)
            ],
        )
    add_equality(
        TRIPLE_LABEL_COUNT,
        [
            (local_variables[index], configuration[3])
            for index, configuration in enumerate(local)
        ],
    )

    # For each pair-multiplicity class, triple labels consume no more than the
    # available pair multiplicity. The residual incidences are the three
    # size-two labels. Nonnegative slacks make that capacity explicit.
    for multiplicity in range(6):
        columns = [
            (
                local_variables[index],
                configuration[3]
                * sum(value == multiplicity for value in configuration[:3]),
            )
            for index, configuration in enumerate(local)
        ]
        columns.append((triple_pair_slacks[multiplicity], 1))
        add_equality(multiplicity * histogram[multiplicity], columns)

    # Every vertex occurs in 36 of the 120 ticket triples. Its repeated-label
    # degree lies in 0..6, and the ten degrees sum to 18.
    for degree in range(TICKET_SIZE + 1):
        columns = [
            (
                local_variables[index],
                sum(value == degree for value in configuration[4:]),
            )
            for index, configuration in enumerate(local)
        ]
        columns.append((degree_histogram[degree], -36))
        add_equality(0, columns)
    add_equality(10, [(variable, 1) for variable in degree_histogram])
    add_equality(
        REPEATED_INCIDENCE_COUNT,
        [
            (degree_histogram[degree], degree)
            for degree in range(TICKET_SIZE + 1)
        ],
    )

    objective = solver.Objective()
    for index, configuration in enumerate(local):
        objective.SetCoefficient(
            local_variables[index],
            float(
                event_counts[
                    (
                        configuration[0],
                        configuration[1],
                        configuration[2],
                        configuration[3],
                    )
                ]
            ),
        )
    objective.SetMaximization()
    if solver.Solve() != solver_api.Solver.OPTIMAL:
        raise RuntimeError("degree-conditioned S3 LP did not solve to optimality")

    exact_duals = tuple(
        Fraction(constraint.dual_value()).limit_denominator(1_000_000)
        for constraint in constraints
    )
    if len(exact_duals) != 23:
        raise AssertionError("unexpected degree-conditioned LP row count")
    dual_record: dict[str, object] = {
        "row_count": str(exact_duals[0]),
        "pair_multiplicity_classes": [
            str(value) for value in exact_duals[1:7]
        ],
        "common_triple_labels": str(exact_duals[7]),
        "triple_pair_capacity_classes": [
            str(value) for value in exact_duals[8:14]
        ],
        "degree_classes": [str(value) for value in exact_duals[14:21]],
        "degree_vertex_total": str(exact_duals[21]),
        "degree_incidence_total": str(exact_duals[22]),
    }
    coefficients = _dual_parts(dual_record)
    event_pair_counts = pair_event_counts()
    s2 = sum(
        histogram[multiplicity] * event_pair_counts[multiplicity]
        for multiplicity in range(6)
    )
    s3_bound = (
        120 * coefficients[0]
        + sum(
            8 * histogram[multiplicity] * coefficients[1 + multiplicity]
            for multiplicity in range(6)
        )
        + TRIPLE_LABEL_COUNT * coefficients[7]
        + sum(
            multiplicity
            * histogram[multiplicity]
            * coefficients[8 + multiplicity]
            for multiplicity in range(6)
        )
        + 10 * coefficients[21]
        + REPEATED_INCIDENCE_COUNT * coefficients[22]
    )
    s3_integer_upper = s3_bound.numerator // s3_bound.denominator
    record: dict[str, object] = {
        "occupied_pairs": sum(histogram[1:]),
        "pair_multiplicity_histogram_n0_to_n5": list(histogram),
        "s2": s2,
        "s3_upper_rational": str(s3_bound),
        "s3_integer_upper": s3_integer_upper,
        "u3_upper": S1 - s2 + s3_integer_upper,
        "dual_certificate": dual_record,
    }
    verify_histogram_certificate(record)
    return record


def build_bound_artifact(canonical_base_commit: str) -> dict[str, object]:
    """Build all exact histogram certificates without a CP-SAT search."""

    if len(canonical_base_commit) != 40 or any(
        character not in "0123456789abcdef" for character in canonical_base_commit
    ):
        raise ValueError("canonical base commit must be a full lowercase SHA-1")

    certificates = [
        _derive_histogram_certificate(histogram)
        for occupied in range(P_MIN, P_MAX + 1)
        for histogram in pair_multiplicity_histograms(occupied)
    ]
    rows: list[dict[str, object]] = []
    for convex_row in minimum_s2_rows():
        occupied = cast(int, convex_row["occupied_pairs"])
        family = [
            certificate
            for certificate in certificates
            if certificate["occupied_pairs"] == occupied
        ]
        worst = max(family, key=lambda item: cast(int, item["u3_upper"]))
        rows.append(
            {
                **convex_row,
                "histograms_examined": len(family),
                "maximum_u3_upper": worst["u3_upper"],
                "maximizing_pair_multiplicity_histogram_n0_to_n5": worst[
                    "pair_multiplicity_histogram_n0_to_n5"
                ],
                "s2_at_maximum": worst["s2"],
                "s3_upper_rational_at_maximum": worst["s3_upper_rational"],
                "s3_integer_upper_at_maximum": worst["s3_integer_upper"],
                "closed_at_incumbent": cast(int, worst["u3_upper"])
                <= INCUMBENT_OUTCOME_COUNT,
            }
        )

    nonlinear_upper = max(cast(int, row["maximum_u3_upper"]) for row in rows)
    profile_upper = max(
        PRIOR_CLOSED_P3_BOUND,
        nonlinear_upper,
        PRIOR_CLOSED_P15_LINEAR_BOUND,
    )
    global_status = (
        "PROVEN" if profile_upper <= INCUMBENT_OUTCOME_COUNT else "UNKNOWN"
    )
    artifact: dict[str, object] = {
        "task_id": TASK_ID,
        "canonical_base_commit": canonical_base_commit,
        "profile": {
            "ticket_vertices": 10,
            "singleton_labels": 42,
            "double_labels": 3,
            "triple_labels": 4,
            "overlap_mass": OVERLAP_MASS,
            "pair_count_range": [P_MIN, P_MAX],
        },
        "incumbent": INCUMBENT_OUTCOME_COUNT,
        "previous_profile_bound": PREVIOUS_PROFILE_BOUND,
        "pair_event_counts_overlap_0_to_5": list(pair_event_counts()),
        "convex_s2_formula": (
            "For p occupied pairs, write 15=q*p+r (0<=r<p). Discrete convexity "
            "minimizes S2 with p-r overlaps q and r overlaps q+1; all other "
            "pairs have overlap 0."
        ),
        "s3_relaxation": {
            "local_event": "J(a,b,c,z), the exact three-ticket Venn intersection count",
            "pair_histogram_condition": (
                "For each m=0..5, local triple rows contain 8*n_m pair slots of "
                "multiplicity m, where n_m is fixed by the exact histogram."
            ),
            "triple_double_intersection_condition": (
                "If t_m is the number of triple-label pair incidences on pairs of "
                "multiplicity m, then t_m<=m*n_m; the residual 15-12=3 incidences "
                "are exactly the three double labels. z records triple labels "
                "common to each local ticket triple."
            ),
            "vertex_incidence_degree_condition": {
                "degree_domain": "r_v in 0..6",
                "degree_sum": REPEATED_INCIDENCE_COUNT,
                "degree_histogram_relaxation": (
                    "Each vertex occurs in 36 of the 120 local triples; the LP "
                    "uses nonnegative degree-class counts summing to ten and "
                    "eighteen total incidences."
                ),
                "local_degree_floor": "r_a>=a+b-z; r_b>=a+c-z; r_c>=b+c-z",
                "dual_uniform_over_compatible_degree_profiles": True,
            },
            "integer_histograms_examined": len(certificates),
            "relaxation": "nonnegative LP over local pattern counts and degree classes",
            "solver": "OR-Tools GLOP, single thread; no CP-SAT",
            "certificate": "exact rational dual inequalities checked in Python",
        },
        "p_family_bounds": rows,
        "histogram_certificates": certificates,
        "prior_closed_profile_families": {
            "p3_upper": PRIOR_CLOSED_P3_BOUND,
            "p15_linear_upper": PRIOR_CLOSED_P15_LINEAR_BOUND,
            "source": "same-profile prior exact-closure certificate; not reanalyzed",
        },
        "new_nonlinear_p4_p14_bound": nonlinear_upper,
        "new_profile_bound": profile_upper,
        "responsible_p_for_new_nonlinear_maximum": max(
            rows, key=lambda row: cast(int, row["maximum_u3_upper"])
        )["occupied_pairs"],
        "global_optimum_status": global_status,
        "remaining_gap": 0 if global_status == "PROVEN" else None,
        "optional_s4": "NOT_NEEDED_SUCCESS_A"
        if global_status == "PROVEN"
        else "NOT_RUN",
        "forbidden_searches_started": {
            "cp_sat_long_run": "NO",
            "portfolio_search": "NO",
            "49_number_enumeration": "NO",
            "k20_work": "NO",
        },
    }
    verify_bound_artifact(artifact)
    return artifact


def write_bound_artifact(
    canonical_base_commit: str,
    result_path: str | Path = DEFAULT_RESULT_PATH,
) -> Path:
    """Write the final certificate once to its scoped result path."""

    path = Path(result_path)
    if path.exists():
        raise FileExistsError(f"refusing to replace an existing result: {path}")
    if not path.parent.is_dir():
        raise FileNotFoundError(f"result directory does not exist: {path.parent}")
    artifact = build_bound_artifact(canonical_base_commit)
    path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-artifact", action="store_true")
    parser.add_argument("--canonical-base-commit", required=True)
    arguments = parser.parse_args(argv)
    if not arguments.write_artifact:
        parser.error("--write-artifact is required")
    path = write_bound_artifact(arguments.canonical_base_commit)
    print(f"wrote {path}")
    return 0


__all__ = [
    "INCUMBENT_OUTCOME_COUNT",
    "P_MAX",
    "P_MIN",
    "TASK_ID",
    "balanced_pair_multiplicity_histogram",
    "build_bound_artifact",
    "minimum_s2_rows",
    "pair_multiplicity_histograms",
    "verify_bound_artifact",
    "verify_histogram_certificate",
    "write_bound_artifact",
]


if __name__ == "__main__":
    raise SystemExit(main())
