"""Synthetic acceptance tests for the frozen Big Lotto L2 candidate."""

from __future__ import annotations

import itertools
from collections.abc import Sequence

import pytest

from lottolab.research import biglotto_l2_pairwise_marked_matrix_profile as candidate


def _synthetic_draws(count: int = 256) -> list[tuple[int, ...]]:
    """Build valid hand-generated draws without reading any historical data."""

    return [
        tuple(((draw_index * 11 + offset * 7) % 49) + 1 for offset in range(6))
        for draw_index in range(count)
    ]


class _ReadSpy:
    def __init__(self, values: Sequence[object], *, reject_from: int | None = None) -> None:
        self.values = values
        self.read_indices: list[int] = []
        self.reject_from = reject_from

    def __len__(self) -> int:
        return len(self.values)

    def __getitem__(self, index: int) -> object:
        self.read_indices.append(index)
        if self.reject_from is not None and index >= self.reject_from:
            raise AssertionError(f"forbidden history index read: {index}")
        return self.values[index]


class _NeverRead:
    def __init__(self, length: int) -> None:
        self.length = length
        self.read_count = 0

    def __len__(self) -> int:
        return self.length

    def __getitem__(self, index: int) -> object:
        self.read_count += 1
        raise AssertionError(f"history element {index} must not be read")


def _event_times_from_gaps(gaps: list[int]) -> list[int]:
    tau = -1
    times: list[int] = []
    for gap in gaps:
        tau += gap
        times.append(tau)
    return times


def _events(times: list[int], marks: list[str]) -> tuple[tuple[int, str], ...]:
    return tuple(zip(times, marks, strict=True))


def _all_pair_weights(value: int = 0) -> dict[tuple[int, int], int]:
    return {
        (i, j): value
        for i in range(1, 50)
        for j in range(i + 1, 50)
    }


def _patch_ticket_constructor(
    monkeypatch: pytest.MonkeyPatch,
    ticket: tuple[int, ...] = (1, 2, 3, 4, 5, 6),
) -> None:
    def replacement(_matrix: object) -> tuple[int, ...]:
        return ticket

    monkeypatch.setattr(candidate, "construct_exact_six_ticket", replacement)


def test_min_history_minus_one_is_a_no_read_fallback() -> None:
    history = _NeverRead(255)
    result = candidate.analyze(history, 255)

    assert history.read_count == 0
    assert result.status == candidate.STATUS_FALLBACK_INSUFFICIENT_HISTORY
    assert len(result.pair_rows) == 1176
    assert all(row.pair_weight_quantum == 0 for row in result.pair_rows)
    assert len(result.number_rank_rows) == 49
    assert [row.rank for row in result.number_rank_rows] == list(range(1, 50))
    assert result.ticket == (1, 2, 3, 4, 5, 6)


def test_min_history_exact_reads_exactly_the_completed_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_ticket_constructor(monkeypatch)
    history = _ReadSpy(_synthetic_draws(), reject_from=256)

    result = candidate.analyze(history, 256)

    assert history.read_indices == list(range(256))
    assert result.status == candidate.STATUS_OK
    assert len(result.pair_rows) == 1176
    assert len(result.number_rank_rows) == 49
    assert result.ticket == (1, 2, 3, 4, 5, 6)


def test_strict_left_causality_and_future_data_invariance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_ticket_constructor(monkeypatch)
    base = _synthetic_draws()
    left = _ReadSpy([*base, *([(1, 2, 3, 4, 5, 6)] * 2)], reject_from=256)
    right = _ReadSpy(
        [*base, (True, 2, 3, 4, 5, 6), (1, 1, 2, 3, 4, 5)], reject_from=256
    )

    left_result = candidate.analyze(left, 256)
    right_result = candidate.analyze(right, 256)

    assert left.read_indices == list(range(256))
    assert right.read_indices == list(range(256))
    assert left_result.to_json() == right_result.to_json()


def test_marked_union_encoding_uses_one_same_draw_both_event() -> None:
    draws: list[tuple[int, ...]] = [
        (1, 49, 2, 3, 4, 5),
        (6, 7, 8, 9, 10, 11),
        (1, 12, 13, 14, 15, 16),
        (17, 18, 19, 20, 21, 49),
        (22, 23, 24, 25, 26, 27),
        (1, 28, 29, 30, 31, 32),
    ]

    events = candidate.encode_pair_union_events(draws, 1, 49)

    assert [(event.tau, event.gap, event.mark) for event in events] == [
        (0, 1, candidate.MARK_BOTH),
        (2, 2, candidate.MARK_I_ONLY),
        (3, 1, candidate.MARK_J_ONLY),
        (5, 2, candidate.MARK_I_ONLY),
    ]


def test_hand_distance_half_mark_mismatch() -> None:
    profile = candidate.pair_profile_from_events(
        _events(
            [0, 1, 2, 6, 10, 14, 15, 16, 17, 21, 25, 29],
            [candidate.MARK_I_ONLY] * 9
            + [candidate.MARK_J_ONLY] * 3,
        )
    )

    assert profile.union_event_count == 12
    assert profile.selected_candidate_start == 0
    assert profile.d2 == "0.250000000000000000000000000000000000"
    assert profile.weight == "0.666666666666666666666666666667"
    assert profile.q == 666666666666666666666666666667


def test_strong_exact_marked_motif_short_circuits_to_zero() -> None:
    profile = candidate.pair_profile_from_events(
        _events(
            [0, 1, 3, 6, 10, 15, 16, 17, 19, 22, 26, 31],
            [
                candidate.MARK_I_ONLY,
                candidate.MARK_J_ONLY,
                candidate.MARK_BOTH,
                candidate.MARK_I_ONLY,
                candidate.MARK_BOTH,
                candidate.MARK_J_ONLY,
            ]
            * 2,
        )
    )

    assert profile.selected_candidate_start == 0
    assert profile.d2 == "0.000000000000000000000000000000000000"
    assert profile.weight == "1.000000000000000000000000000000"
    assert profile.q == 1000000000000000000000000000000


def test_pair_label_symmetry_preserves_every_score_surface() -> None:
    marks = [
        candidate.MARK_I_ONLY,
        candidate.MARK_J_ONLY,
        candidate.MARK_BOTH,
        candidate.MARK_I_ONLY,
        candidate.MARK_BOTH,
        candidate.MARK_J_ONLY,
    ]
    swapped = [
        candidate.MARK_J_ONLY if mark == candidate.MARK_I_ONLY else
        candidate.MARK_I_ONLY if mark == candidate.MARK_J_ONLY else
        candidate.MARK_BOTH
        for mark in marks * 2
    ]
    times = [0, 1, 3, 6, 10, 15, 16, 17, 19, 22, 26, 31]

    original = candidate.pair_profile_from_events(_events(times, marks * 2))
    relabeled = candidate.pair_profile_from_events(_events(times, swapped))

    assert relabeled == original


def test_constant_gap_vectors_are_exact_zero_coordinates() -> None:
    profile = candidate.pair_profile_from_events(
        _events(
            _event_times_from_gaps([1, 1, 1, 1, 1, 1, 7, 7, 7, 7, 7, 7]),
            [candidate.MARK_I_ONLY, candidate.MARK_J_ONLY, candidate.MARK_BOTH] * 4,
        )
    )

    assert profile.d2 == "0.000000000000000000000000000000000000"
    assert profile.weight == "1.000000000000000000000000000000"


def test_maximum_normalized_distance_and_weight_boundary() -> None:
    profile = candidate.pair_profile_from_events(
        _events(
            _event_times_from_gaps([1, 1, 1, 4, 4, 4, 4, 4, 4, 1, 1, 1]),
            [candidate.MARK_I_ONLY] * 6 + [candidate.MARK_J_ONLY] * 6,
        )
    )

    assert profile.d2 == "1.000000000000000000000000000000000000"
    assert profile.weight == "0.500000000000000000000000000000"
    assert profile.q == 500000000000000000000000000000


def test_nearest_neighbor_tie_retains_smallest_strict_left_start() -> None:
    marks = [
        candidate.MARK_I_ONLY,
        candidate.MARK_J_ONLY,
        candidate.MARK_BOTH,
        candidate.MARK_I_ONLY,
        candidate.MARK_BOTH,
        candidate.MARK_J_ONLY,
    ]
    times = [0, 1, 3, 6, 10, 15, 16, 17, 19, 22, 26, 31, 32, 33, 35, 38, 42, 47]
    profile = candidate.pair_profile_from_events(_events(times, marks * 3))

    assert profile.union_event_count == 18
    assert profile.selected_candidate_start == 0
    assert profile.d2_quantum == 0


def test_zero_recurrence_pair_has_a_zero_edge() -> None:
    profile = candidate.pair_profile_from_events(())

    assert profile.status == candidate.STATUS_INSUFFICIENT_PAIR_GEOMETRY
    assert profile.selected_candidate_start is None
    assert profile.d2_quantum is None
    assert profile.weight == "0.000000000000000000000000000000"
    assert profile.q == 0


def test_invalid_input_fails_closed_and_unused_elements_are_not_inspected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_ticket_constructor(monkeypatch)
    valid = _synthetic_draws()
    with pytest.raises(candidate.InvalidCutoffError):
        candidate.analyze(valid, True)
    with pytest.raises(candidate.InvalidCutoffError):
        candidate.analyze(valid, len(valid) + 1)

    duplicate = [(1, 1, 2, 3, 4, 5), *valid[1:]]
    with pytest.raises(candidate.InvalidHistoryError):
        candidate.analyze(duplicate, 256)
    boolean_number = [(True, 2, 3, 4, 5, 6), *valid[1:]]
    with pytest.raises(candidate.InvalidHistoryError):
        candidate.analyze(boolean_number, 256)

    before_cutoff = _ReadSpy([(1, 1, 2, 3, 4, 5), *valid])
    result_before = candidate.analyze(before_cutoff, 257)
    assert 0 not in before_cutoff.read_indices
    assert result_before.status == candidate.STATUS_OK

    future = _ReadSpy([*valid, (True, 2, 3, 4, 5, 6)], reject_from=256)
    result_future = candidate.analyze(future, 256)
    assert future.read_indices == list(range(256))
    assert result_future.status == candidate.STATUS_OK


def test_exact_six_all_zero_matrix_has_lexicographically_first_ticket() -> None:
    assert candidate.construct_exact_six_ticket(_all_pair_weights()) == (1, 2, 3, 4, 5, 6)


def test_number_aggregation_is_exact_and_ranks_ties_by_number() -> None:
    pair_weights = _all_pair_weights()
    pair_weights[1, 49] = 10
    pair_weights[2, 3] = 10

    rows = candidate.aggregate_number_scores(pair_weights)

    assert [(row.number, row.aggregate_score, row.rank) for row in rows[:4]] == [
        (1, 10, 1),
        (2, 10, 2),
        (3, 10, 3),
        (49, 10, 4),
    ]
    assert all(row.aggregate_score == 0 for row in rows[4:])


def test_exact_six_endpoint_fixture_selects_1_and_49() -> None:
    pair_weights = _all_pair_weights()
    target = (1, 2, 3, 4, 5, 49)
    for i, j in itertools.combinations(target, 2):
        pair_weights[i, j] = 1

    assert candidate.construct_exact_six_ticket(pair_weights) == target


def test_exact_six_equal_objective_tie_is_lexicographic() -> None:
    assert candidate.construct_exact_six_ticket(_all_pair_weights(7)) == (1, 2, 3, 4, 5, 6)


def test_output_has_exactly_one_sorted_unique_six_number_ticket() -> None:
    result = candidate.analyze(_NeverRead(0), 0)

    assert len(result.ticket) == 6
    assert len(set(result.ticket)) == 6
    assert tuple(sorted(result.ticket)) == result.ticket
    assert all(1 <= number <= 49 for number in result.ticket)
    assert len(result.pair_rows) == 1176
    assert len(result.number_rank_rows) == 49
    assert result.ticket_objective == 0


def test_repeated_valid_runs_have_byte_identical_serialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_ticket_constructor(monkeypatch)
    first = candidate.analyze(_ReadSpy(_synthetic_draws(), reject_from=256), 256)
    second = candidate.analyze(_ReadSpy(_synthetic_draws(), reject_from=256), 256)

    assert first.to_json() == second.to_json()
    assert first.to_dict() == second.to_dict()


def test_semantic_constants_and_decimal_contract_are_frozen() -> None:
    assert candidate.METHOD_ID == "BMSGV1_L2_PAIRWISE_2e8fb1bb6d0648fa"
    assert candidate.DESIGN_NAME == "CAUSAL_MARKED_UNION_MATRIX_PROFILE_EXACT6_V1"
    assert candidate.SEMANTIC_SIGNATURE == (
        "2e8fb1bb6d0648fa1e226bc78d35b3677833855e3e8d5e2a1ea51acd2504ce4f"
    )
    assert candidate.DECIMAL_CONTEXT.prec == 80
    assert candidate.DECIMAL_CONTEXT.rounding == candidate.ROUND_HALF_EVEN
    assert candidate.compute_semantic_signature({"z": 1, "a": [2, 3]}) == (
        "9c24cd7614ce91d1a480097ac7530c8092a2a7b4b37c90f5364c4d29d15de0a6"
    )
