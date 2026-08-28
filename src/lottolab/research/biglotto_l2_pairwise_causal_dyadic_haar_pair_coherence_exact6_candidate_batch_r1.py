"""Frozen fifth Level-2 Pairwise Big Lotto research candidate.

This module implements only the sealed causal six-scale Haar pair-coherence
design and its exact maximum-total-pair-weight six-subset constructor.  It is
pure standard-library computation: no persistence, replay, registry, network,
clock, random source, or production service participates in the result.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import (
    ROUND_HALF_EVEN,
    Context,
    Decimal,
    DecimalException,
    DivisionByZero,
    InvalidOperation,
    Overflow,
    localcontext,
)
from itertools import combinations
from typing import cast

METHOD_ID = "BMSGV1_L2_PAIRWISE_96368234e833a391"
DESIGN_NAME = "CAUSAL_DYADIC_HAAR_PAIR_COHERENCE_EXACT6_V1"
SEMANTIC_SIGNATURE = "96368234e833a391f98ebe9d4deaf5adea2b12335a341e80be87cf9a7c4a3ba2"

MIN_HISTORY = 256
TRAILING_WINDOW = 256
SCALES = (1, 2, 3, 4, 5, 6)
BLOCK_LENGTHS = (2, 4, 8, 16, 32, 64)
NUMBER_DOMAIN = tuple(range(1, 50))
TICKET_SIZE = 6
PAIR_COUNT = 1176
EXACT_SIX_SUBSET_COUNT = 13_983_816
QUANTUM_SCALE = 10**30
WEIGHT_QUANTUM = Decimal("1e-30")

STATUS_SUCCESS = "SUCCESS"
STATUS_FALLBACK = "FALLBACK_INSUFFICIENT_HISTORY"

Pair = tuple[int, int]
Draw = tuple[int, ...]
HaarContrastTable = dict[int, dict[int, tuple[int, ...]]]
PairQuanta = dict[Pair, int]
PairWeightStrings = dict[Pair, str]

PAIR_ORDER: tuple[Pair, ...] = tuple(combinations(NUMBER_DOMAIN, 2))
PAIR_SET = frozenset(PAIR_ORDER)

DECIMAL_CONTEXT = Context(
    prec=80,
    rounding=ROUND_HALF_EVEN,
    Emin=-999999,
    Emax=999999,
    capitals=1,
    clamp=0,
    traps=[InvalidOperation, DivisionByZero, Overflow],
)


class InvalidCutoffError(ValueError):
    """The cutoff is not an exact valid boundary for the supplied history."""


class InvalidHistoryError(ValueError):
    """The history container or an accessed draw violates the frozen contract."""


class NumericContractError(ArithmeticError):
    """An exact or Decimal invariant required by the frozen design failed."""


@dataclass(frozen=True, slots=True)
class NumberRank:
    """One exact number aggregate and its deterministic ordinal rank."""

    number: int
    score: int
    rank: int


@dataclass(frozen=True, slots=True)
class HaarPairCoherencePrediction:
    """Complete deterministic result for one cutoff invocation."""

    method_id: str
    design_name: str
    semantic_signature: str
    status: str
    pair_quanta: PairQuanta
    pair_weights: PairWeightStrings
    number_ranks: tuple[NumberRank, ...]
    ticket_objective: int
    ticket: tuple[int, ...]

    def to_canonical_json(self) -> str:
        """Serialize every required output in frozen deterministic order."""

        payload: dict[str, object] = {
            "design_name": self.design_name,
            "method_id": self.method_id,
            "number_ranks": [
                {
                    "number": row.number,
                    "rank": row.rank,
                    "score": str(row.score),
                }
                for row in self.number_ranks
            ],
            "pair_weights": {
                f"{left}-{right}": self.pair_weights[(left, right)] for left, right in PAIR_ORDER
            },
            "semantic_signature": self.semantic_signature,
            "status": self.status,
            "ticket": list(self.ticket),
            "ticket_objective": str(self.ticket_objective),
        }
        return json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )


def _ordered_sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise InvalidHistoryError(f"{label} must be a finite random-access sequence")
    return cast(Sequence[object], value)


def _sequence_length(value: Sequence[object], *, label: str) -> int:
    try:
        length = len(value)
    except (OverflowError, TypeError) as exc:
        raise InvalidHistoryError(f"{label} must expose a finite length") from exc
    if length < 0:  # pragma: no cover - Python's len protocol rejects this first
        raise InvalidHistoryError(f"{label} must expose a nonnegative length")
    return length


def _validated_cutoff(cutoff: object, history_length: int) -> int:
    if type(cutoff) is not int:
        raise InvalidCutoffError("cutoff must be a non-boolean integer")
    validated = cutoff
    if validated < 0 or validated > history_length:
        raise InvalidCutoffError("cutoff must satisfy 0 <= cutoff <= len(history)")
    return validated


def _validated_draw(value: object, *, label: str) -> Draw:
    draw = _ordered_sequence(value, label=label)
    if len(draw) != 6:
        raise InvalidHistoryError(f"{label} must contain exactly six numbers")

    numbers: list[int] = []
    for position in range(6):
        number = draw[position]
        if type(number) is not int:
            raise InvalidHistoryError(f"{label}[{position}] must be a non-boolean integer")
        integer = number
        if integer < 1 or integer > 49:
            raise InvalidHistoryError(f"{label}[{position}] must lie in 1..49")
        numbers.append(integer)
    if len(set(numbers)) != 6:
        raise InvalidHistoryError(f"{label} must contain six distinct numbers")
    return tuple(sorted(numbers))


def _build_haar_contrasts(used_draws: Sequence[Draw]) -> HaarContrastTable:
    table: HaarContrastTable = {}
    for number in NUMBER_DOMAIN:
        prefix = [0]
        for draw in used_draws:
            prefix.append(prefix[-1] + int(number in draw))

        number_scales: dict[int, tuple[int, ...]] = {}
        for scale in SCALES:
            block_length = 1 << scale
            half = block_length >> 1
            block_contrasts: list[int] = []
            for block_start in range(0, TRAILING_WINDOW, block_length):
                midpoint = block_start + half
                block_end = block_start + block_length
                first_half = prefix[midpoint] - prefix[block_start]
                second_half = prefix[block_end] - prefix[midpoint]
                block_contrasts.append(first_half - second_half)
            number_scales[scale] = tuple(block_contrasts)
        table[number] = number_scales
    return table


def compute_haar_contrasts(used_draws: object) -> HaarContrastTable:
    """Validate and encode exactly one aligned 256-draw causal window."""

    supplied = _ordered_sequence(used_draws, label="used_draws")
    if _sequence_length(supplied, label="used_draws") != TRAILING_WINDOW:
        raise InvalidHistoryError("used_draws must contain exactly 256 draws")
    validated = tuple(
        _validated_draw(supplied[index], label=f"used_draws[{index}]")
        for index in range(TRAILING_WINDOW)
    )
    return _build_haar_contrasts(validated)


def _validated_number(number: object, *, label: str) -> int:
    if type(number) is not int:
        raise NumericContractError(f"{label} must be a non-boolean integer")
    validated = number
    if validated < 1 or validated > 49:
        raise NumericContractError(f"{label} must lie in 1..49")
    return validated


def scale_statistics(
    contrast_table: Mapping[int, Mapping[int, Sequence[int]]],
    left: object,
    right: object,
    scale: object,
) -> tuple[int, int, int]:
    """Return exact ``(A, E_left, E_right)`` for one pair and scale."""

    left_number = _validated_number(left, label="left")
    right_number = _validated_number(right, label="right")
    if left_number == right_number:
        raise NumericContractError("pair endpoints must be distinct")
    if type(scale) is not int or scale not in SCALES:
        raise NumericContractError("scale must be one of 1,2,3,4,5,6")
    validated_scale = cast(int, scale)

    try:
        left_values = contrast_table[left_number][validated_scale]
        right_values = contrast_table[right_number][validated_scale]
    except (KeyError, TypeError) as exc:
        raise NumericContractError("contrast table is incomplete") from exc

    expected_length = TRAILING_WINDOW // (1 << validated_scale)
    if len(left_values) != expected_length or len(right_values) != expected_length:
        raise NumericContractError("contrast vector has the wrong complete-block count")

    cross_energy = 0
    left_energy = 0
    right_energy = 0
    for block in range(expected_length):
        left_value = left_values[block]
        right_value = right_values[block]
        if type(left_value) is not int or type(right_value) is not int:
            raise NumericContractError("Haar contrasts must be exact integers")
        cross_energy += left_value * right_value
        left_energy += left_value * left_value
        right_energy += right_value * right_value
    return cross_energy, left_energy, right_energy


def normalized_cross_energy(
    cross_energy: object,
    left_energy: object,
    right_energy: object,
) -> Decimal:
    """Apply the frozen exact shortcuts and 80-digit Decimal normalization."""

    values = (cross_energy, left_energy, right_energy)
    if any(type(value) is not int for value in values):
        raise NumericContractError("cross-energy and energies must be exact integers")
    cross = cast(int, cross_energy)
    energy_left = cast(int, left_energy)
    energy_right = cast(int, right_energy)
    if energy_left < 0 or energy_right < 0:
        raise NumericContractError("energies must be nonnegative")
    if energy_left == 0 or energy_right == 0 or cross == 0:
        return Decimal(0)

    energy_product = energy_left * energy_right
    squared_cross = cross * cross
    if squared_cross > energy_product:
        raise NumericContractError("cross-energy violates the exact Cauchy bound")
    if squared_cross == energy_product:
        return Decimal(1)

    try:
        with localcontext(DECIMAL_CONTEXT) as context:
            denominator = context.sqrt(Decimal(energy_product))
            coherence = context.divide(Decimal(abs(cross)), denominator)
    except DecimalException as exc:
        raise NumericContractError("Decimal normalization failed") from exc
    if coherence < 0 or coherence > 1:
        raise NumericContractError("normalized coherence lies outside [0,1]")
    return coherence


def mean_coherence_quanta(scale_coherences: Sequence[object]) -> int:
    """Sum six scales in order, divide by six, and quantize exactly once."""

    if len(scale_coherences) != len(SCALES):
        raise NumericContractError("exactly six scale coherences are required")
    try:
        with localcontext(DECIMAL_CONTEXT) as context:
            total = Decimal(0)
            for coherence in scale_coherences:
                if not isinstance(coherence, Decimal) or coherence < 0 or coherence > 1:
                    raise NumericContractError("every scale coherence must be Decimal in [0,1]")
                total = context.add(total, coherence)
            mean = context.divide(total, Decimal(len(SCALES)))
            quantized = context.quantize(mean, WEIGHT_QUANTUM)
            scaled = context.multiply(quantized, Decimal(QUANTUM_SCALE))
    except DecimalException as exc:
        raise NumericContractError("Decimal scale aggregation failed") from exc

    quanta = int(scaled)
    if scaled != Decimal(quanta):
        raise NumericContractError("quantized weight is not an exact integer quantum")
    if quanta < 0 or quanta > QUANTUM_SCALE:
        raise NumericContractError("quantized weight lies outside [0,1]")
    return quanta


def compute_pair_weight_quantum(
    contrast_table: Mapping[int, Mapping[int, Sequence[int]]],
    left: object,
    right: object,
) -> int:
    """Compute one unordered pair's final 1e-30 weight quantum."""

    left_number = _validated_number(left, label="left")
    right_number = _validated_number(right, label="right")
    if left_number == right_number:
        raise NumericContractError("pair endpoints must be distinct")

    coherences: list[Decimal] = []
    for scale in SCALES:
        cross, left_energy, right_energy = scale_statistics(
            contrast_table,
            left_number,
            right_number,
            scale,
        )
        coherences.append(normalized_cross_energy(cross, left_energy, right_energy))
    return mean_coherence_quanta(tuple(coherences))


def compute_pair_weight_quanta(
    contrast_table: Mapping[int, Mapping[int, Sequence[int]]],
) -> PairQuanta:
    """Compute all 1176 unordered pair weights in numeric lexicographic order."""

    if set(contrast_table) != set(NUMBER_DOMAIN):
        raise NumericContractError("contrast table must contain exactly numbers 1..49")
    pair_quanta = {pair: compute_pair_weight_quantum(contrast_table, *pair) for pair in PAIR_ORDER}
    if len(pair_quanta) != PAIR_COUNT:  # pragma: no cover - PAIR_ORDER is frozen
        raise NumericContractError("pair matrix does not contain exactly 1176 pairs")
    return pair_quanta


def weight_string_from_quanta(quanta: object) -> str:
    """Serialize one exact quantum as a fixed 30-place decimal string."""

    if type(quanta) is not int:
        raise NumericContractError("pair quantum must be an exact integer")
    value = quanta
    if value < 0 or value > QUANTUM_SCALE:
        raise NumericContractError("pair quantum lies outside [0,10^30]")
    integer_part, fractional_part = divmod(value, QUANTUM_SCALE)
    return f"{integer_part}.{fractional_part:030d}"


def _validate_pair_quanta(pair_quanta: Mapping[Pair, int]) -> None:
    try:
        supplied_pairs = frozenset(pair_quanta)
    except TypeError as exc:
        raise NumericContractError("pair matrix keys must be hashable pairs") from exc
    if supplied_pairs != PAIR_SET:
        raise NumericContractError("pair matrix must contain every unordered pair exactly once")

    for pair in PAIR_ORDER:
        value = pair_quanta[pair]
        if type(value) is not int or value < 0 or value > QUANTUM_SCALE:
            raise NumericContractError(f"invalid pair quantum for {pair}")


def rank_numbers(pair_quanta: Mapping[Pair, int]) -> tuple[NumberRank, ...]:
    """Aggregate all 48 incident pair quanta and rank all 49 numbers exactly."""

    _validate_pair_quanta(pair_quanta)
    scores: dict[int, int] = {}
    for number in NUMBER_DOMAIN:
        score = 0
        for other in NUMBER_DOMAIN:
            if number == other:
                continue
            pair = (number, other) if number < other else (other, number)
            score += pair_quanta[pair]
        scores[number] = score

    ordered_numbers = tuple(sorted(NUMBER_DOMAIN, key=lambda number: (-scores[number], number)))
    return tuple(
        NumberRank(number=number, score=scores[number], rank=rank)
        for rank, number in enumerate(ordered_numbers, start=1)
    )


def construct_exact_ticket(pair_quanta: Mapping[Pair, int]) -> tuple[int, tuple[int, ...]]:
    """Exhaustively maximize all 13,983,816 exact six-subset objectives.

    The nested ranges are lexicographically equivalent to
    ``itertools.combinations(range(1, 50), 6)``.  Replacement occurs only on
    strict improvement, so equal maxima retain the first (smallest) tuple.
    Grouped prefix sums contain the same exact-integer pair terms in frozen
    lexicographic pair order; they do not prune or skip any candidate set.
    """

    _validate_pair_quanta(pair_quanta)
    matrix: list[list[int]] = [[0] * 50 for _ in range(50)]
    for (left, right), value in pair_quanta.items():
        matrix[left][right] = value
        matrix[right][left] = value

    best_objective = -1
    best_ticket = (1, 2, 3, 4, 5, 6)

    for first in range(1, 45):
        first_row = matrix[first]
        for second in range(first + 1, 46):
            second_row = matrix[second]
            first_second = first_row[second]
            for third in range(second + 1, 47):
                third_row = matrix[third]
                first_prefix_3 = first_second + first_row[third]
                second_prefix_3 = second_row[third]
                for fourth in range(third + 1, 48):
                    fourth_row = matrix[fourth]
                    first_prefix_4 = first_prefix_3 + first_row[fourth]
                    second_prefix_4 = second_prefix_3 + second_row[fourth]
                    third_prefix_4 = third_row[fourth]
                    for fifth in range(fourth + 1, 49):
                        fifth_row = matrix[fifth]
                        first_prefix_5 = first_prefix_4 + first_row[fifth]
                        second_prefix_5 = second_prefix_4 + second_row[fifth]
                        third_prefix_5 = third_prefix_4 + third_row[fifth]
                        fourth_prefix_5 = fourth_row[fifth]
                        for sixth in range(fifth + 1, 50):
                            objective = (
                                first_prefix_5
                                + first_row[sixth]
                                + second_prefix_5
                                + second_row[sixth]
                                + third_prefix_5
                                + third_row[sixth]
                                + fourth_prefix_5
                                + fourth_row[sixth]
                                + fifth_row[sixth]
                            )
                            if objective > best_objective:
                                best_objective = objective
                                best_ticket = (
                                    first,
                                    second,
                                    third,
                                    fourth,
                                    fifth,
                                    sixth,
                                )

    if best_objective < 0:  # pragma: no cover - the fixed domain has six-subsets
        raise NumericContractError("exact six-subset enumeration produced no candidate")
    return best_objective, best_ticket


def _result_from_pair_quanta(status: str, pair_quanta: PairQuanta) -> HaarPairCoherencePrediction:
    number_ranks = rank_numbers(pair_quanta)
    ticket_objective, ticket = construct_exact_ticket(pair_quanta)
    pair_weights = {pair: weight_string_from_quanta(pair_quanta[pair]) for pair in PAIR_ORDER}
    return HaarPairCoherencePrediction(
        method_id=METHOD_ID,
        design_name=DESIGN_NAME,
        semantic_signature=SEMANTIC_SIGNATURE,
        status=status,
        pair_quanta=pair_quanta,
        pair_weights=pair_weights,
        number_ranks=number_ranks,
        ticket_objective=ticket_objective,
        ticket=ticket,
    )


def run_design(history: object, cutoff: object) -> HaarPairCoherencePrediction:
    """Run the frozen design at one causal cutoff and return exactly one ticket.

    A valid cutoff below 256 returns the all-zero exact-construction fallback
    without reading any history element.  Otherwise only indices
    ``cutoff-256`` through ``cutoff-1`` are accessed and validated.
    """

    supplied_history = _ordered_sequence(history, label="history")
    history_length = _sequence_length(supplied_history, label="history")
    validated_cutoff = _validated_cutoff(cutoff, history_length)

    if validated_cutoff < MIN_HISTORY:
        zero_quanta = {pair: 0 for pair in PAIR_ORDER}
        return _result_from_pair_quanta(STATUS_FALLBACK, zero_quanta)

    start = validated_cutoff - TRAILING_WINDOW
    used_draws = tuple(
        _validated_draw(supplied_history[index], label=f"history[{index}]")
        for index in range(start, validated_cutoff)
    )
    contrasts = _build_haar_contrasts(used_draws)
    pair_quanta = compute_pair_weight_quanta(contrasts)
    return _result_from_pair_quanta(STATUS_SUCCESS, pair_quanta)
