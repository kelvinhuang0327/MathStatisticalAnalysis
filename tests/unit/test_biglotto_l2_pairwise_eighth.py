from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction
from itertools import combinations
from typing import cast, overload

import pytest

from lottolab.research.biglotto_l2_pairwise_eighth import (
    BLOCK_LENGTH,
    COMPLETE_STATUS,
    DESIGN_NAME,
    FALLBACK_STATUS,
    KERNEL_BANDWIDTH_RULE,
    METHOD_ID,
    MIN_HISTORY,
    NUMBER_DOMAIN,
    OBSERVATION_COUNT,
    PAIR_COUNT,
    PAIR_KEYS,
    SEMANTIC_SIGNATURE,
    AnalysisResult,
    InvalidInputError,
    analyze,
    build_gram_matrix,
    build_lag_blocks,
    build_membership_streams,
    center_gram_matrix,
    centering_matrix,
    delta_kernel,
    hsic_from_gram_matrices,
    incident_pair_sums,
    optimize_ticket,
    ticket_objective,
    zero_pair_weights,
)


class AccessRecordingHistory(Sequence[object]):
    def __init__(self, draws: Sequence[object], allowed_indices: set[int] | None = None) -> None:
        self._draws = tuple(draws)
        self.allowed_indices = allowed_indices
        self.accessed: list[int] = []

    def __len__(self) -> int:
        return len(self._draws)

    @overload
    def __getitem__(self, index: int) -> object: ...

    @overload
    def __getitem__(self, index: slice) -> Sequence[object]: ...

    def __getitem__(self, index: int | slice) -> object | Sequence[object]:
        if isinstance(index, slice):
            return self._draws[index]
        self.accessed.append(index)
        if self.allowed_indices is not None and index not in self.allowed_indices:
            raise AssertionError(f"forbidden history index was read: {index}")
        return self._draws[index]


def _synthetic_history(length: int) -> tuple[tuple[int, ...], ...]:
    return tuple(
        tuple(((draw_index + offset) % 49) + 1 for offset in range(6))
        for draw_index in range(length)
    )


def _constant_block(label: int) -> tuple[int, ...]:
    return (label,) * BLOCK_LENGTH


def _direct_hsic(left: Sequence[Sequence[int]], right: Sequence[Sequence[int]]) -> Fraction:
    size = len(left)
    assert size == len(right)
    h = tuple(
        tuple(Fraction(int(row == column)) - Fraction(1, size) for column in range(size))
        for row in range(size)
    )
    trace = Fraction(0)
    for row in range(size):
        for left_column in range(size):
            for right_row in range(size):
                for column in range(size):
                    trace += (
                        Fraction(left[row][left_column])
                        * h[left_column][right_row]
                        * Fraction(right[right_row][column])
                        * h[column][row]
                    )
    return trace / (size * size)


def _matrix_multiply(
    left: Sequence[Sequence[Fraction]], right: Sequence[Sequence[Fraction]]
) -> tuple[tuple[Fraction, ...], ...]:
    size = len(left)
    return tuple(
        tuple(
            sum((left[row][inner] * right[inner][column] for inner in range(size)), Fraction(0))
            for column in range(size)
        )
        for row in range(size)
    )


def test_frozen_identity_and_constants_are_sealed_values() -> None:
    assert METHOD_ID == "BMSGV1_L2_PAIRWISE_NF01_LAG_BLOCK_HSIC_V1"
    assert DESIGN_NAME == "BIGLOTTO_L2_PAIRWISE_NF01_LAG_BLOCK_HSIC_V1"
    assert SEMANTIC_SIGNATURE == "1ce87b2abf6fb55c812d4d09476ba050bab8e8165d08da9b8bf46e19a5a8af6f"
    assert MIN_HISTORY == 256
    assert BLOCK_LENGTH == 8
    assert OBSERVATION_COUNT == 249
    assert PAIR_COUNT == 1176
    assert len(PAIR_KEYS) == PAIR_COUNT


@pytest.mark.parametrize("cutoff", [0, 255])
def test_insufficient_history_returns_no_read_fallback(cutoff: int) -> None:
    history = AccessRecordingHistory(_synthetic_history(300))

    result = analyze(history, cutoff)

    assert result.status == FALLBACK_STATUS
    assert len(result.pair_weights) == PAIR_COUNT
    assert set(result.pair_weights.values()) == {Fraction(0)}
    assert result.ticket_objective == Fraction(0)
    assert result.ticket == (1, 2, 3, 4, 5, 6)
    assert history.accessed == []


def test_sufficient_analysis_reads_only_the_256_draw_causal_window_and_is_deterministic() -> None:
    draws = _synthetic_history(300)
    allowed = set(range(0, 256))
    first_history = AccessRecordingHistory(draws, allowed)
    second_history = AccessRecordingHistory(draws, allowed)

    first = analyze(first_history, 256)
    second = analyze(second_history, 256)

    assert first.status == COMPLETE_STATUS
    assert len(first.pair_weights) == PAIR_COUNT
    assert tuple(first.pair_weights) == PAIR_KEYS
    assert all(value >= 0 for value in first.pair_weights.values())
    assert len(first.ticket) == 6
    assert first.ticket == tuple(sorted(set(first.ticket)))
    assert all(1 <= number <= 49 for number in first.ticket)
    assert first.ticket_objective == ticket_objective(first.ticket, first.pair_weights)
    assert first.canonical_bytes() == second.canonical_bytes()
    assert first_history.accessed == list(range(0, 256))
    assert second_history.accessed == list(range(0, 256))


def test_membership_streams_are_raw_number_indicators() -> None:
    draws = ((1, 2, 3, 4, 5, 6), (2, 3, 4, 5, 6, 7))

    streams = build_membership_streams(draws)

    assert streams[0] == (1, 0)
    assert streams[1] == (1, 1)
    assert streams[6] == (0, 1)
    assert streams[7] == (0, 0)
    assert len(streams) == 49


def test_lag_blocks_are_ordered_overlapping_eight_bit_tuples() -> None:
    stream = (0, 1, 1, 0, 0, 1, 0, 1, 1, 0)

    blocks = build_lag_blocks(stream)

    assert blocks == (
        (0, 1, 1, 0, 0, 1, 0, 1),
        (1, 1, 0, 0, 1, 0, 1, 1),
        (1, 0, 0, 1, 0, 1, 1, 0),
    )


def test_delta_kernel_is_one_only_for_exact_ordered_tuple_equality() -> None:
    left = (0, 1, 0, 1, 0, 1, 0, 1)
    same = (0, 1, 0, 1, 0, 1, 0, 1)
    reordered = (1, 0, 1, 0, 1, 0, 1, 0)

    assert delta_kernel(left, same) == 1
    assert delta_kernel(left, reordered) == 0
    assert KERNEL_BANDWIDTH_RULE == "NOT_APPLICABLE: fixed Kronecker-delta kernel has no bandwidth"


def test_delta_gram_matrix_matches_explicit_label_fixture() -> None:
    blocks = (_constant_block(0), _constant_block(0), _constant_block(1))

    gram = build_gram_matrix(blocks)

    assert gram == ((1, 1, 0), (1, 1, 0), (0, 0, 1))
    assert all(entry in (0, 1) for row in gram for entry in row)


def test_centering_matrix_is_exact_idempotent_and_annihilates_one() -> None:
    expected = (
        (Fraction(2, 3), Fraction(-1, 3), Fraction(-1, 3)),
        (Fraction(-1, 3), Fraction(2, 3), Fraction(-1, 3)),
        (Fraction(-1, 3), Fraction(-1, 3), Fraction(2, 3)),
    )

    centered = centering_matrix(3)

    assert centered == expected
    assert all(sum(row, Fraction(0)) == 0 for row in centered)
    assert _matrix_multiply(centered, centered) == centered


def test_hsic_matches_independent_trace_hand_calculation() -> None:
    left = ((1, 1, 0), (1, 1, 0), (0, 0, 1))
    right = ((1, 0, 0), (0, 1, 1), (0, 1, 1))

    expected = _direct_hsic(left, right)

    assert expected == Fraction(4, 81)
    assert hsic_from_gram_matrices(left, right) == expected
    assert hsic_from_gram_matrices(left, left) == Fraction(16, 81)


def test_zero_dependence_fixture_is_exactly_zero_and_strong_fixture_is_larger() -> None:
    product_left = ((1, 1, 0, 0), (1, 1, 0, 0), (0, 0, 1, 1), (0, 0, 1, 1))
    product_right = ((1, 0, 1, 0), (0, 1, 0, 1), (1, 0, 1, 0), (0, 1, 0, 1))
    strong = ((1, 1, 0), (1, 1, 0), (0, 0, 1))

    zero = hsic_from_gram_matrices(product_left, product_right)
    strong_score = hsic_from_gram_matrices(strong, strong)

    assert zero == Fraction(0)
    assert zero == _direct_hsic(product_left, product_right)
    assert strong_score == Fraction(16, 81)
    assert strong_score > zero


def test_constant_gram_is_degenerate_without_variance_division() -> None:
    constant = ((1, 1, 1), (1, 1, 1), (1, 1, 1))
    varying = ((1, 0, 0), (0, 1, 1), (0, 1, 1))

    assert center_gram_matrix(constant) == (
        (Fraction(0), Fraction(0), Fraction(0)),
        (Fraction(0), Fraction(0), Fraction(0)),
        (Fraction(0), Fraction(0), Fraction(0)),
    )
    assert hsic_from_gram_matrices(constant, varying) == Fraction(0)


def test_invalid_cutoff_fails_closed_without_reading_history() -> None:
    history = AccessRecordingHistory(_synthetic_history(300))

    for invalid_cutoff in (True, -1, 301, 1.5):
        with pytest.raises(InvalidInputError):
            analyze(history, invalid_cutoff)

    assert history.accessed == []


def test_malformed_accessed_draw_fails_closed_before_score_construction() -> None:
    draws = list(_synthetic_history(256))
    draws[0] = (1, 1, 2, 3, 4, 5)
    history = AccessRecordingHistory(draws)

    with pytest.raises(InvalidInputError):
        analyze(history, 256)

    assert history.accessed == [0]


def test_number_level_aggregation_is_exact_diagnostic_only() -> None:
    weights = dict(zero_pair_weights())
    weights[(1, 2)] = Fraction(2, 3)
    weights[(1, 49)] = Fraction(1, 3)
    weights[(2, 49)] = Fraction(1, 7)

    totals = incident_pair_sums(weights)

    assert tuple(totals) == NUMBER_DOMAIN
    assert totals[1] == Fraction(1)
    assert totals[2] == Fraction(17, 21)
    assert totals[49] == Fraction(10, 21)
    assert totals[3] == 0
    assert sum(1 for left, right in PAIR_KEYS if 1 in (left, right)) == 48
    assert sum(1 for left, right in PAIR_KEYS if 49 in (left, right)) == 48


def test_all_zero_pair_score_tie_returns_first_lexicographic_ticket() -> None:
    ticket, objective = optimize_ticket(zero_pair_weights())

    assert ticket == (1, 2, 3, 4, 5, 6)
    assert objective == Fraction(0)


def test_exhaustive_ticket_constructor_finds_unique_known_clique_optimum() -> None:
    weights = dict(zero_pair_weights())
    target = (10, 11, 12, 13, 14, 15)
    for pair in combinations(target, 2):
        weights[pair] = Fraction(1)

    ticket, objective = optimize_ticket(weights)

    assert ticket == target
    assert objective == Fraction(15)
    assert ticket_objective(ticket, weights) == Fraction(15)


def test_exhaustive_ticket_constructor_keeps_lexicographically_smaller_exact_tie() -> None:
    weights = dict(zero_pair_weights())
    first_clique = (1, 2, 3, 4, 5, 6)
    second_clique = (7, 8, 9, 10, 11, 12)
    for clique in (first_clique, second_clique):
        for pair in combinations(clique, 2):
            weights[pair] = Fraction(1)

    ticket, objective = optimize_ticket(weights)

    assert ticket == first_clique
    assert objective == Fraction(15)


def test_analysis_result_canonical_json_has_frozen_key_and_pair_order() -> None:
    result = AnalysisResult(
        method_id=METHOD_ID,
        design_name=DESIGN_NAME,
        status=FALLBACK_STATUS,
        window_size=256,
        block_length=8,
        observation_count=249,
        pair_weights=zero_pair_weights(),
        ticket_objective=Fraction(0),
        ticket=(1, 2, 3, 4, 5, 6),
    )
    payload = result.canonical_dict()
    pair_payload = cast(dict[str, object], payload["pair_weights"])
    first_rational = cast(dict[str, int], pair_payload["1-2"])

    assert list(payload) == [
        "method_id",
        "design_name",
        "status",
        "window_size",
        "block_length",
        "observation_count",
        "pair_weights",
        "ticket_objective",
        "ticket",
    ]
    assert list(pair_payload)[:3] == ["1-2", "1-3", "1-4"]
    assert list(first_rational) == ["numerator", "denominator"]
    assert result.canonical_bytes().startswith(b'{"method_id":"BMSGV1_')
    assert b" " not in result.canonical_bytes()
