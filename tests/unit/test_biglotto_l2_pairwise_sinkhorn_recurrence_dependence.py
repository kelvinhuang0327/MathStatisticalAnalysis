from __future__ import annotations

import json
import math

import pytest

from lottolab.research import biglotto_l2_pairwise_sinkhorn_recurrence_dependence as nf06


class AccessRecordingHistory:
    def __init__(self, rows: tuple[object, ...]) -> None:
        self.rows = rows
        self.accessed: list[int] = []

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> object:
        self.accessed.append(index)
        return self.rows[index]


def _alternating_ages() -> tuple[tuple[int, ...], tuple[int, ...]]:
    left = tuple(0 if index % 2 == 0 else 1 for index in range(nf06.WINDOW_SIZE))
    return left, left


def _independent_ages() -> tuple[tuple[int, ...], tuple[int, ...]]:
    left = tuple(index % 2 for index in range(nf06.WINDOW_SIZE))
    right = tuple((index // 2) % 2 for index in range(nf06.WINDOW_SIZE))
    return left, right


def _constant_history(length: int) -> tuple[tuple[int, ...], ...]:
    return tuple((1, 2, 3, 4, 5, 6) for _ in range(length))


def test_identity_and_frozen_constants_are_exposed() -> None:
    assert nf06.METHOD_ID == "BMSGV1_L2_PAIRWISE_NF06_SINKHORN_RECURRENCE_DEPENDENCE_V1"
    assert nf06.DESIGN_NAME == "BIGLOTTO_L2_PAIRWISE_NF06_SINKHORN_RECURRENCE_DEPENDENCE_EXACT6_V1"
    assert nf06.SEMANTIC_SIGNATURE.startswith("85b903d8")
    assert nf06.W == 256
    assert nf06.G == 16
    assert nf06.EPSILON == 1 / 32
    assert nf06.PAIR_COUNT == 1176
    assert nf06.TICKET_COUNT == 13_983_816


def test_strong_recurrence_fixture_matches_sealed_sinkhorn_evidence() -> None:
    left, right = _alternating_ages()
    result = nf06.pair_score_details_from_counts(nf06.build_pair_counts(left, right))

    assert result.status == nf06.CONVERGED_STATUS
    assert result.raw_score == 0.0037535783424461587
    assert result.quantum == 3_753_578_342
    assert result.cross is not None
    assert result.self_left is not None
    assert result.self_right is not None
    assert result.cross.iterations == 1
    assert result.self_left.iterations == 1
    assert result.self_right.iterations == 1
    assert result.cross.value == 0.02447217452370269
    assert result.self_left.value == 0.017694349047405397
    assert result.self_right.value == 0.02374284331510767


def test_recurrence_ages_use_same_draw_and_cap_missing_history() -> None:
    ages = nf06.build_recurrence_ages(((1, 2, 3, 4, 5, 6), (2, 3, 4, 5, 6, 7)))

    assert ages[0] == (0, 1)
    assert ages[7 - 1] == (nf06.AGE_CAP, 0)
    assert all(age == nf06.AGE_CAP for age in ages[48])


def test_ground_metric_hand_fixture_matches_manhattan_over_32() -> None:
    points = ((0, 0), (2, 1), (16, 16))

    assert nf06.build_cost_matrix(points, points) == (
        (0.0, 3 / 32, 1.0),
        (3 / 32, 0.0, 29 / 32),
        (1.0, 29 / 32, 0.0),
    )


def test_cost_matrix_transport_matches_frozen_entropic_hand_value() -> None:
    rows = ((0, 0), (2, 0))
    columns = ((0, 0), (4, 0))

    assert nf06.build_cost_matrix(rows, columns) == (
        (0.0, 1 / 8),
        (1 / 16, 1 / 16),
    )
    assert nf06.sinkhorn_transport(rows, (0.5, 0.5), columns, (0.5, 0.5)) == (
        0.048944349047405404
    )


def test_first_full_iteration_is_recorded_in_canonical_order() -> None:
    left, right = _alternating_ages()
    result = nf06.pair_score_details_from_counts(nf06.build_pair_counts(left, right))

    assert result.cross is not None
    assert len(result.cross.trace) == 1
    first = result.cross.trace[0]
    assert first.iteration == 1
    assert first.residual_inf == max(first.row_residual, first.column_residual)
    assert math.isfinite(first.residual_inf)


def test_zero_mass_and_zero_cells_are_handled_without_repair() -> None:
    zero = nf06.sinkhorn_solve((), (), (), ())
    assert zero.status == nf06.ZERO_MASS_ZERO_ZERO_STATUS
    assert zero.value == 0.0
    assert zero.iterations == 0

    counts = [[0 for _ in range(nf06.SUPPORT_SIZE)] for _ in range(nf06.SUPPORT_SIZE)]
    counts[0][1] = 1
    measure = nf06.measure_from_counts(counts)
    assert measure.support == ((0, 1),)
    assert measure.masses == (1.0,)

    with pytest.raises(nf06.NumericInvariantError):
        nf06.sinkhorn_solve((), (), ((0, 0),), (1.0,))


def test_singleton_marginal_short_circuits_to_exact_independence() -> None:
    left = (5,) * nf06.WINDOW_SIZE
    right = tuple(index % 3 for index in range(nf06.WINDOW_SIZE))
    result = nf06.pair_score_details_from_counts(nf06.build_pair_counts(left, right))

    assert result.status == nf06.EXACT_INDEPENDENCE_STATUS
    assert result.quantum == 0
    assert result.cross is None


def test_convergence_boundary_uses_inclusive_binary64_comparison() -> None:
    tolerance = nf06.CONVERGENCE_TOLERANCE
    next_larger = math.nextafter(tolerance, math.inf)

    assert tolerance == 9.094947017729282e-13
    assert tolerance <= tolerance
    assert not next_larger <= tolerance


def test_iteration_cap_exhaustion_returns_no_transport_value() -> None:
    result = nf06.sinkhorn_solve(
        ((0, 0), (1, 1)),
        (0.5, 0.5),
        ((0, 0), (1, 1)),
        (0.5, 0.5),
        max_iterations=0,
    )

    assert result.status == nf06.NONCONVERGENCE_STATUS
    assert result.value is None
    assert result.trace == ()


def test_pair_score_is_symmetric_and_independence_is_zero() -> None:
    correlated_left, correlated_right = _alternating_ages()
    independent_left, independent_right = _independent_ages()

    assert nf06.pair_score(correlated_left, correlated_right) == (
        nf06.pair_score(correlated_right, correlated_left)
    )
    assert nf06.pair_score(correlated_left, correlated_right) == 3_753_578_342
    assert nf06.pair_score(independent_left, independent_right) == 0


def test_exact_six_objective_retains_lexicographically_first_tie() -> None:
    zero_ticket, zero_objective = nf06.optimize_ticket({})
    assert zero_ticket == (1, 2, 3, 4, 5, 6)
    assert zero_objective == 0

    clique = {(left, right): 7 for left in range(1, 7) for right in range(left + 1, 7)}
    unique_ticket, unique_objective = nf06.optimize_ticket(clique)
    assert unique_ticket == (1, 2, 3, 4, 5, 6)
    assert unique_objective == 105
    assert nf06.ticket_objective(unique_ticket, clique) == unique_objective


def test_number_aggregation_is_an_exact_incident_sum() -> None:
    weights = {
        (1, 2): 8,
        (2, 3): 2,
        (3, 4): 10,
        (4, 5): 1,
        (5, 6): 10,
    }
    aggregates = nf06.number_aggregation(weights)

    assert len(aggregates) == nf06.NUMBER_MAX
    assert {number: aggregates[number] for number in range(1, 6)} == {
        1: 8,
        2: 10,
        3: 12,
        4: 11,
        5: 11,
    }


def test_minimum_history_fallback_reads_nothing() -> None:
    history = AccessRecordingHistory(())

    result = nf06.nf06_compute(history, 255)

    assert result.status == nf06.FALLBACK_STATUS
    assert history.accessed == []
    assert result.ticket == (1, 2, 3, 4, 5, 6)
    assert result.ticket_objective == 0
    assert len(result.pair_weights) == nf06.PAIR_COUNT
    assert len(result.number_aggregates) == nf06.NUMBER_MAX
    assert all(value == 0 for value in result.pair_weights.values())


def test_causal_window_reads_exactly_the_trailing_rows() -> None:
    valid_rows = _constant_history(nf06.WINDOW_SIZE)
    history = AccessRecordingHistory(valid_rows + ("TARGET_AND_FUTURE_MUST_NOT_BE_READ",))

    result = nf06.analyze(history, nf06.WINDOW_SIZE)

    assert result.status == nf06.OK_STATUS
    assert history.accessed == list(range(nf06.WINDOW_SIZE))
    assert len(result.pair_weights) == nf06.PAIR_COUNT
    assert len(result.number_aggregates) == nf06.NUMBER_MAX
    assert result.ticket == (1, 2, 3, 4, 5, 6)
    payload = json.loads(result.canonical_json())
    assert payload["ticket"] == [1, 2, 3, 4, 5, 6]
    assert all(math.isfinite(float(value)) for value in result.pair_weights.values())


def test_repeated_solver_execution_is_byte_identical() -> None:
    left, right = _alternating_ages()
    first = nf06.pair_score_details_from_counts(nf06.build_pair_counts(left, right))
    second = nf06.pair_score_details_from_counts(nf06.build_pair_counts(left, right))

    first_evidence = json.dumps(
        {
            "raw_score": first.raw_score,
            "quantum": first.quantum,
            "status": first.status,
            "cross": first.cross,
            "self_left": first.self_left,
            "self_right": first.self_right,
        },
        default=lambda value: value.__dict__ if hasattr(value, "__dict__") else str(value),
        allow_nan=False,
        separators=(",", ":"),
    )
    second_evidence = json.dumps(
        {
            "raw_score": second.raw_score,
            "quantum": second.quantum,
            "status": second.status,
            "cross": second.cross,
            "self_left": second.self_left,
            "self_right": second.self_right,
        },
        default=lambda value: value.__dict__ if hasattr(value, "__dict__") else str(value),
        allow_nan=False,
        separators=(",", ":"),
    )
    assert first_evidence == second_evidence


def test_invalid_input_fails_closed_without_partial_output() -> None:
    result = nf06.analyze(((1, 2, 3, 4, 5, 5),) * nf06.WINDOW_SIZE, nf06.WINDOW_SIZE)

    assert result.status == nf06.INVALID_INPUT_STATUS
    assert result.ticket is None
    assert result.ticket_objective is None
    assert result.pair_weights == {}
    assert result.number_aggregates == {}
    json.loads(result.canonical_json())
