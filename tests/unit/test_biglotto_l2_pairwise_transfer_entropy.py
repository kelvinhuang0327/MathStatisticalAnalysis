from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from itertools import combinations
from typing import cast, overload

import pytest

from lottolab.research.biglotto_l2_pairwise_transfer_entropy import (
    COMPLETE_STATUS,
    DECIMAL_CONTEXT,
    DECIMAL_OUTPUT_PLACES,
    DESIGN_NAME,
    DRAW_SIZE,
    FALLBACK_STATUS,
    METHOD_ID,
    MIN_HISTORY,
    NUMBER_DOMAIN,
    OUTPUT_QUANTUM,
    PAIR_COUNT,
    PAIR_KEYS,
    PREDICTION_COUNT,
    SEMANTIC_SIGNATURE,
    TICKET_COUNT,
    WINDOW_SIZE,
    AnalysisResult,
    InvalidInputError,
    K,
    L,
    analyze,
    build_conditional_counts,
    build_membership_streams,
    build_prediction_rows,
    conditional_entropy,
    directional_score,
    flatten_state,
    incident_pair_sums,
    optimize_ticket,
    pair_weight,
    ticket_objective,
    transfer_entropy,
    zero_pair_weights,
)

_HAND_CONTEXT = Context(prec=80, rounding=ROUND_HALF_EVEN, Emin=-999_999_999, Emax=999_999_999)


def _quantized(value: Decimal) -> Decimal:
    with localcontext(_HAND_CONTEXT) as context:
        return context.quantize(value, OUTPUT_QUANTUM)


def _hand_mean(left: Decimal, right: Decimal) -> Decimal:
    with localcontext(_HAND_CONTEXT) as context:
        total = context.add(left, right)
        return context.quantize(context.divide(total, context.create_decimal(2)), OUTPUT_QUANTUM)


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


class NeverRead:
    def __iter__(self):
        raise AssertionError("poison history entry was inspected")


def _synthetic_history(length: int) -> tuple[tuple[int, ...], ...]:
    return tuple(
        tuple(((draw_index + offset) % 49) + 1 for offset in range(DRAW_SIZE))
        for draw_index in range(length)
    )


def _repeating_stream(pattern: str, length: int) -> tuple[int, ...]:
    return tuple(int(pattern[index % len(pattern)]) for index in range(length))


def _hand_rows(
    target: Sequence[int], source: Sequence[int]
) -> tuple[tuple[int, tuple[int, ...], tuple[int, ...]], ...]:
    return tuple(
        (target[index], (target[index - 1],), (source[index - 1],))
        for index in range(1, len(target))
    )


def _hand_transfer_entropy(target: Sequence[int], source: Sequence[int]) -> Decimal:
    rows = _hand_rows(target, source)
    triple: Counter[tuple[int, tuple[int, ...], tuple[int, ...]]] = Counter(rows)
    target_source: Counter[tuple[tuple[int, ...], tuple[int, ...]]] = Counter(
        (history, source_history) for _, history, source_history in rows
    )
    target_context: Counter[tuple[int, tuple[int, ...]]] = Counter(
        (value, history) for value, history, _ in rows
    )
    target_history: Counter[tuple[int, ...]] = Counter(history for _, history, _ in rows)

    with localcontext(_HAND_CONTEXT) as context:
        total = context.create_decimal(0)
        sample_size = context.create_decimal(len(rows))
        for (value, history, source_history), count in sorted(triple.items()):
            numerator = count * target_history[history]
            denominator = target_source[(history, source_history)] * target_context[
                (value, history)
            ]
            ratio = context.divide(
                context.create_decimal(numerator), context.create_decimal(denominator)
            )
            probability = context.divide(context.create_decimal(count), sample_size)
            total = context.add(total, context.multiply(probability, context.ln(ratio)))
        return context.quantize(total, OUTPUT_QUANTUM)


def _hand_conditional_entropy(target: Sequence[int]) -> Decimal:
    rows = _hand_rows(target, tuple(0 for _ in target))
    target_context: Counter[tuple[int, tuple[int, ...]]] = Counter(
        (value, history) for value, history, _ in rows
    )
    target_history: Counter[tuple[int, ...]] = Counter(history for _, history, _ in rows)
    with localcontext(_HAND_CONTEXT) as context:
        total = context.create_decimal(0)
        sample_size = context.create_decimal(len(rows))
        for (_value, history), count in sorted(target_context.items()):
            probability = context.divide(context.create_decimal(count), sample_size)
            ratio = context.divide(
                context.create_decimal(count), context.create_decimal(target_history[history])
            )
            total = context.subtract(total, context.multiply(probability, context.ln(ratio)))
        return context.quantize(total, OUTPUT_QUANTUM)


@pytest.fixture(scope="module")
def exact_result_and_history() -> tuple[AnalysisResult, AccessRecordingHistory]:
    draws: list[object] = [*_synthetic_history(257), NeverRead(), NeverRead()]
    history = AccessRecordingHistory(draws, allowed_indices=set(range(257)))
    return analyze(history, 257), history


def test_frozen_identity_and_numeric_constants_are_sealed() -> None:
    assert METHOD_ID == "BMSGV1_L2_PAIRWISE_NF02_TRANSFER_ENTROPY_V1"
    assert DESIGN_NAME == "BIGLOTTO_L2_PAIRWISE_NF02_TRANSFER_ENTROPY_V1"
    assert SEMANTIC_SIGNATURE == (
        "339a4a3e3e3df04db4b6a02461ecd433089ad54b3edd56628d5ded568aea4234"
    )
    assert MIN_HISTORY == 257
    assert WINDOW_SIZE == 256
    assert PREDICTION_COUNT == 256
    assert K == 1
    assert L == 1
    assert PAIR_COUNT == 1176
    assert TICKET_COUNT == 13_983_816
    assert tuple(range(1, 50)) == NUMBER_DOMAIN
    assert len(PAIR_KEYS) == PAIR_COUNT
    assert DECIMAL_CONTEXT.prec == 80
    assert DECIMAL_CONTEXT.rounding == ROUND_HALF_EVEN
    assert DECIMAL_CONTEXT.Emin == -999_999_999
    assert DECIMAL_CONTEXT.Emax == 999_999_999
    assert DECIMAL_OUTPUT_PLACES == 60


def test_min_history_minus_one_is_a_no_read_fallback() -> None:
    history = AccessRecordingHistory(_synthetic_history(300), allowed_indices=set())

    result = analyze(history, 256)

    assert result.status == FALLBACK_STATUS
    assert result.pair_weights.keys() == zero_pair_weights().keys()
    assert set(result.pair_weights.values()) == {Decimal(0)}
    assert result.ticket_objective == Decimal(0)
    assert result.ticket == (1, 2, 3, 4, 5, 6)
    assert history.accessed == []


def test_min_history_exact_reads_257_rows_and_counts_256_predictions(
    exact_result_and_history: tuple[AnalysisResult, AccessRecordingHistory],
) -> None:
    result, history = exact_result_and_history

    assert result.status == COMPLETE_STATUS
    assert len(result.pair_weights) == PAIR_COUNT
    assert tuple(result.pair_weights) == PAIR_KEYS
    assert result.window_size == WINDOW_SIZE
    assert result.prediction_count == PREDICTION_COUNT
    assert history.accessed == list(range(257))


def test_causal_exclusion_never_reads_target_or_future_rows(
    exact_result_and_history: tuple[AnalysisResult, AccessRecordingHistory],
) -> None:
    result, history = exact_result_and_history

    assert result.status == COMPLETE_STATUS
    assert 257 not in history.accessed
    assert all(index < 257 for index in history.accessed)


def test_membership_and_one_step_state_encoding_are_literal_binary_incidence() -> None:
    draws = ((1, 2, 3, 4, 5, 6), (2, 3, 4, 5, 6, 7))
    streams = build_membership_streams(draws)

    assert streams[0] == (1, 0)
    assert streams[1] == (1, 1)
    assert streams[6] == (0, 1)
    assert streams[7] == (0, 0)
    assert flatten_state((0, 1, 0)) == 2
    assert flatten_state((1, 0, 1)) == 5

    rows = build_prediction_rows((0, 1, 0, 1), (1, 0, 1, 0))
    assert rows == (
        (1, (0,), (1,)),
        (0, (1,), (0,)),
        (1, (0,), (1,)),
    )


def test_observed_cell_zero_policy_omits_absent_cells_and_matches_hand_formula() -> None:
    target = (0, 0, 0, 1, 1)
    source = (0, 1, 0, 1, 0)
    counts = build_conditional_counts(target, source)

    assert all(count > 0 for count in counts.triple_counts.values())
    assert transfer_entropy(counts) == _hand_transfer_entropy(target, source)
    assert counts.sample_size == 4


def test_transfer_entropy_and_conditional_entropy_match_independent_hand_calculation() -> None:
    target = (0, 0, 1, 0, 1, 1, 0, 1, 0)
    source = (0, 1, 0, 1, 1, 0, 1, 0, 0)

    assert transfer_entropy(target, source) == _hand_transfer_entropy(target, source)
    assert conditional_entropy(target, source) == _hand_conditional_entropy(target)


def test_delayed_copy_has_frozen_source_to_target_directionality() -> None:
    source = _repeating_stream("0001", 121)
    target = (0, *source[:-1])

    source_to_target = directional_score(target, source)
    target_to_source = directional_score(source, target)

    assert source_to_target.normalized > target_to_source.normalized
    assert source_to_target.normalized == _quantized(Decimal(1))


def test_independent_cartesian_contexts_have_zero_transfer_entropy_both_ways() -> None:
    target = _repeating_stream("0011", 121)
    source = _repeating_stream("011", 121)

    forward = directional_score(target, source)
    reverse = directional_score(source, target)

    assert forward.transfer_entropy == Decimal(0)
    assert reverse.transfer_entropy == Decimal(0)
    assert forward.normalized == Decimal(0)
    assert reverse.normalized == Decimal(0)
    assert pair_weight(target, source) == Decimal(0)


def test_zero_conditional_entropy_skips_normalization_division() -> None:
    target = (1,) * 65
    source = _repeating_stream("01", 65)

    score = directional_score(target, source)

    assert score.conditional_entropy == Decimal(0)
    assert score.transfer_entropy == Decimal(0)
    assert score.normalized == Decimal(0)


def test_pair_weight_is_symmetric_and_averages_directional_scores() -> None:
    left = _repeating_stream("0001", 121)
    right = (0, *left[:-1])
    forward = directional_score(right, left).normalized
    reverse = directional_score(left, right).normalized

    expected = _hand_mean(forward, reverse)
    assert pair_weight(left, right) == expected
    assert pair_weight(right, left) == expected


def test_decimal_serialization_is_fixed_point_and_repeatable() -> None:
    history = _synthetic_history(257)
    first = analyze(history, 257)
    with localcontext() as context:
        context.prec = 9
        context.rounding = ROUND_HALF_EVEN
        second = analyze(history, 257)

    assert first.canonical_bytes() == second.canonical_bytes()
    assert first.canonical_bytes() == first.canonical_json().encode("utf-8")
    payload = first.canonical_dict()
    pair_payload = cast(dict[str, str], payload["pair_weights"])
    assert all(
        "E" not in value and len(value.rsplit(".", maxsplit=1)[1]) == 60
        for value in pair_payload.values()
    )
    assert len(cast(str, payload["ticket_objective"]).rsplit(".", maxsplit=1)[1]) == 60
    assert "-0" not in first.canonical_json()


def test_exact_six_ticket_optimum_uses_all_15_pair_weights() -> None:
    weights = dict(zero_pair_weights())
    target = (10, 11, 12, 13, 14, 15)
    for pair in combinations(target, 2):
        weights[pair] = Decimal(1)

    ticket, objective = optimize_ticket(weights)

    assert ticket == target
    assert objective == _quantized(Decimal(15))
    assert ticket_objective(ticket, weights) == objective
    totals = incident_pair_sums(weights)
    assert totals[10] == _quantized(Decimal(5))


def test_exact_six_ticket_tie_keeps_lexicographically_first_ticket() -> None:
    weights = dict(zero_pair_weights())
    first_clique = (1, 2, 3, 4, 5, 6)
    second_clique = (7, 8, 9, 10, 11, 12)
    for clique in (first_clique, second_clique):
        for pair in combinations(clique, 2):
            weights[pair] = Decimal(1)

    ticket, objective = optimize_ticket(weights)

    assert ticket == first_clique
    assert objective == _quantized(Decimal(15))


def test_exact_six_endpoint_fixture_covers_numbers_one_and_forty_nine() -> None:
    weights = dict(zero_pair_weights())
    target = (1, 2, 3, 4, 5, 49)
    for pair in combinations(target, 2):
        weights[pair] = Decimal(1)

    ticket, objective = optimize_ticket(weights)

    assert ticket == target
    assert objective == _quantized(Decimal(15))


def test_analysis_result_canonical_shape_and_identity() -> None:
    result = AnalysisResult(
        method_id=METHOD_ID,
        design_name=DESIGN_NAME,
        status=FALLBACK_STATUS,
        window_size=WINDOW_SIZE,
        prediction_count=PREDICTION_COUNT,
        pair_weights=zero_pair_weights(),
        ticket_objective=Decimal(0),
        ticket=(1, 2, 3, 4, 5, 6),
    )

    payload = result.canonical_dict()
    assert list(payload) == [
        "method_id",
        "design_name",
        "status",
        "window_size",
        "prediction_count",
        "pair_weights",
        "ticket_objective",
        "ticket",
    ]
    assert result.semantic_signature == SEMANTIC_SIGNATURE
    assert result.canonical_bytes().startswith(b'{"method_id":"BMSGV1_')


def test_invalid_inputs_fail_closed_before_score_construction() -> None:
    history = AccessRecordingHistory(_synthetic_history(300))

    for invalid_cutoff in (True, -1, 301, 1.5, "257"):
        with pytest.raises(InvalidInputError):
            analyze(history, invalid_cutoff)
    assert history.accessed == []

    malformed = list(_synthetic_history(257))
    malformed[0] = (1, 1, 2, 3, 4, 5)
    malformed_history = AccessRecordingHistory(malformed)
    with pytest.raises(InvalidInputError):
        analyze(malformed_history, 257)
    assert malformed_history.accessed == [0]

    with pytest.raises(InvalidInputError):
        analyze(iter(_synthetic_history(257)), 0)
