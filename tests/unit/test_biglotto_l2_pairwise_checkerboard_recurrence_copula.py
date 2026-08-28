"""Synthetic contract tests for the frozen NF05 checkerboard constructor."""

from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction

import pytest

from lottolab.research import biglotto_l2_pairwise_checkerboard_recurrence_copula as module

Draw = tuple[int, ...]


def _draw(index: int) -> Draw:
    """Return a deterministic legal six-number draw."""

    return tuple(sorted(((index + 8 * offset) % module.NUMBER_MAX) + 1 for offset in range(6)))


def _history(length: int) -> tuple[Draw, ...]:
    return tuple(_draw(index) for index in range(length))


def _independent_checkerboard_distance(
    count_matrix: Sequence[Sequence[int]],
) -> Fraction:
    """Integrate the frozen checkerboard definition independently for tests."""

    rows = tuple(tuple(row) for row in count_matrix)
    total = sum(sum(row) for row in rows)
    row_counts = tuple(sum(row) for row in rows)
    column_counts = tuple(
        sum(rows[row][column] for row in range(len(rows)))
        for column in range(len(rows[0]))
    )
    active_rows = tuple(index for index, count in enumerate(row_counts) if count)
    active_columns = tuple(index for index, count in enumerate(column_counts) if count)
    if len(active_rows) == 1 or len(active_columns) == 1:
        return Fraction(0)

    result = Fraction(0)
    for row_position, row_index in enumerate(active_rows):
        row_count = row_counts[row_index]
        lower_u = Fraction(sum(row_counts[index] for index in active_rows[:row_position]), total)
        width_u = Fraction(row_count, total)
        for column_position, column_index in enumerate(active_columns):
            column_count = column_counts[column_index]
            lower_v = Fraction(
                sum(column_counts[index] for index in active_columns[:column_position]),
                total,
            )
            width_v = Fraction(column_count, total)
            prefix = sum(
                rows[prior_row][prior_column]
                for prior_row in active_rows[:row_position]
                for prior_column in active_columns[:column_position]
            )
            row_before = sum(
                rows[row_index][prior_column] for prior_column in active_columns[:column_position]
            )
            column_before = sum(
                rows[prior_row][column_index] for prior_row in active_rows[:row_position]
            )
            cell_count = rows[row_index][column_index]
            coefficients = (
                Fraction(prefix, total) - lower_u * lower_v,
                Fraction(row_before, row_count) - lower_v,
                Fraction(column_before, column_count) - lower_u,
                Fraction(cell_count * total, row_count * column_count) - 1,
            )
            monomials = ((0, 0), (1, 0), (0, 1), (1, 1))
            for first_index, (first_u, first_v) in enumerate(monomials):
                for second_index, (second_u, second_v) in enumerate(monomials):
                    u_power = first_u + second_u + 1
                    v_power = first_v + second_v + 1
                    result += (
                        coefficients[first_index]
                        * coefficients[second_index]
                        * width_u**u_power
                        / u_power
                        * width_v**v_power
                        / v_power
                    )
    return result


class RecordingHistory:
    """Indexable history that records exactly which rows the analyzer reads."""

    def __init__(self, rows: tuple[Draw, ...]) -> None:
        self.rows = rows
        self.read_indices: list[int] = []

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> Draw:
        self.read_indices.append(index)
        return self.rows[index]


@pytest.fixture(scope="module")
def complete_case() -> tuple[RecordingHistory, module.AnalysisResult]:
    """Run one complete ordinary slice and reuse it across contract checks."""

    rows = _history(301)
    rows = (*rows[:-1], (1, 1, 2, 3, 4, 5))
    history = RecordingHistory(rows)
    return history, module.analyze(history, 300)


def test_identity_and_cardinality_constants_are_frozen() -> None:
    assert module.METHOD_ID == "BMSGV1_L2_PAIRWISE_NF05_CHECKERBOARD_RECURRENCE_COPULA_V1"
    assert module.DESIGN_NAME == "BIGLOTTO_L2_PAIRWISE_NF05_CHECKERBOARD_RECURRENCE_COPULA_V1"
    assert module.SEMANTIC_SIGNATURE == (
        "949ab011357554942d530666465765446a782526decaee900a00254f801ec96f"
    )
    assert module.MIN_HISTORY == 256
    assert module.WINDOW_SIZE == 256
    assert module.RECURRENCE_CAP == 16
    assert module.SENTINEL_AGE == 17
    assert module.PAIR_COUNT == 1_176
    assert len(module.PAIR_KEYS) == 1_176
    assert module.TICKET_COUNT == 13_983_816


def test_rank_intervals_use_contiguous_tie_blocks() -> None:
    intervals = module.build_rank_intervals((2, 1, 2, 3, 1))
    assert intervals == (
        module.RankInterval(1, Fraction(0), Fraction(2, 5)),
        module.RankInterval(2, Fraction(2, 5), Fraction(4, 5)),
        module.RankInterval(3, Fraction(4, 5), Fraction(1)),
    )
    assert tuple(interval.mass for interval in intervals) == (
        Fraction(2, 5),
        Fraction(2, 5),
        Fraction(1, 5),
    )


def test_checkerboard_mandatory_fixtures_and_zero_width_support() -> None:
    independence_counts = ((64, 64), (64, 64))
    matched_counts = ((128, 0), (0, 128))
    zero_width_counts = ((128, 0, 0), (0, 0, 0), (0, 0, 128))
    independence = module.checkerboard_dependence_from_counts(independence_counts)
    matched_ties = module.checkerboard_dependence_from_counts(matched_counts)
    zero_width_support = module.checkerboard_dependence_from_counts(zero_width_counts)

    assert independence == Fraction(0)
    assert matched_ties == Fraction(1, 144)
    assert zero_width_support == matched_ties
    assert independence == _independent_checkerboard_distance(independence_counts)
    assert matched_ties == _independent_checkerboard_distance(matched_counts)
    assert zero_width_support == _independent_checkerboard_distance(zero_width_counts)
    assert module.checkerboard_distance((0, 0, 1, 1), (0, 0, 1, 1)) == matched_ties
    assert module.checkerboard_dependence_from_counts(((128,), (128,))) == Fraction(0)


def test_checkerboard_rank_labels_are_order_only_and_zero_mass_cells_are_retained() -> None:
    original = module.checkerboard_dependence((0, 0, 1, 1), (0, 0, 1, 1))
    relabeled = module.checkerboard_dependence((10, 10, 20, 20), (100, 100, 300, 300))
    explicit_zero_cell = module.checkerboard_dependence_from_counts(((64, 0, 64), (0, 128, 0)))

    assert original == relabeled == Fraction(1, 144)
    assert explicit_zero_cell == Fraction(1, 576)


def test_recurrence_age_streams_obey_current_prior_and_sentinel_rules() -> None:
    recurring_draws = (
        (1, 2, 3, 4, 5, 6),
        (2, 3, 4, 5, 6, 7),
        (2, 3, 4, 5, 6, 7),
        (1, 2, 3, 4, 5, 6),
    )
    assert module.build_recurrence_age_stream(recurring_draws, 1) == (0, 1, 2, 0)

    absent_draws = ((2, 3, 4, 5, 6, 7),) * 19
    ages = module.build_recurrence_age_stream(absent_draws, 1)
    assert ages == (module.SENTINEL_AGE,) * 19

    capped_draws = ((1, 2, 3, 4, 5, 6), *absent_draws[:18])
    capped_ages = module.build_recurrence_age_stream(capped_draws, 1)
    assert capped_ages == (*tuple(range(17)), 16, 16)
    all_streams = module.build_recurrence_age_streams(capped_draws)
    assert len(all_streams) == module.NUMBER_MAX
    assert all(len(stream) == len(capped_draws) for stream in all_streams)


def test_exact_rounding_and_pair_quantization_contract() -> None:
    assert module.round_half_even_fraction(Fraction(1, 2)) == 0
    assert module.round_half_even_fraction(Fraction(3, 2)) == 2
    assert module.round_half_even_fraction(Fraction(5, 2)) == 2
    assert module.quantize_pair_score(Fraction(1, 144)) == 6_944_444_444_444_444_444_444_444_444

    scores = dict(module.zero_pair_scores())
    scores[(1, 2)] = Fraction(1, 144)
    weights = module.compute_pair_weights(scores)
    assert weights[(1, 2)] == 6_944_444_444_444_444_444_444_444_444
    assert all(isinstance(value, int) and value >= 0 for value in weights.values())

    with pytest.raises(module.NumericInvariantError):
        module.quantize_pair_score(Fraction(-1, 2))


def test_pair_aggregation_objective_and_exhaustive_lexicographic_ticket() -> None:
    weights = dict(module.zero_pair_weights())
    clique = tuple(range(44, 50))
    for left_index, left in enumerate(clique):
        for right in clique[left_index + 1 :]:
            weights[(left, right)] = 7

    assert module.ticket_objective(clique, weights) == 105
    aggregates = module.incident_pair_sums(weights)
    assert aggregates[44] == 35
    assert aggregates[49] == 35
    assert aggregates[1] == 0

    ticket, objective = module.optimize_ticket(weights)
    assert ticket == clique
    assert objective == 105


def test_fallback_is_zeroed_and_does_not_read_history() -> None:
    history = RecordingHistory(_history(300))
    result = module.analyze(history, 255)

    assert result.status == module.FALLBACK_STATUS
    assert result.ticket == (1, 2, 3, 4, 5, 6)
    assert result.ticket_objective == 0
    assert all(value == 0 for value in result.pair_weights.values())
    assert all(value == 0 for value in result.number_aggregates.values())
    assert history.read_indices == []


def test_invalid_input_fail_closes_without_a_ticket() -> None:
    too_short = module.analyze(_history(10), 11)
    invalid_cutoff = module.analyze(_history(256), True)
    invalid_draws = (*_history(256)[:-1], (1, 1, 2, 3, 4, 5))
    invalid_draw = module.analyze(invalid_draws, 256)

    for result in (too_short, invalid_cutoff, invalid_draw):
        assert result.status == module.FAIL_CLOSED_NO_TICKET
        assert result.ticket == (1, 2, 3, 4, 5, 6)
        assert result.ticket_objective == 0
        assert all(value == 0 for value in result.pair_weights.values())


def test_complete_result_has_exact_cardinality_legal_ticket_and_canonical_shape(
    complete_case: tuple[RecordingHistory, module.AnalysisResult],
) -> None:
    _, result = complete_case

    assert result.status == module.COMPLETE_STATUS
    assert result.semantic_signature == module.SEMANTIC_SIGNATURE
    assert result.pair_quanta == result.pair_weights
    assert len(result.pair_scores) == module.PAIR_COUNT
    assert len(result.pair_weights) == module.PAIR_COUNT
    assert len(result.number_level_aggregation) == module.NUMBER_MAX
    assert tuple(sorted(result.ticket)) == result.ticket
    assert len(result.ticket) == module.DRAW_SIZE
    assert len(set(result.ticket)) == module.DRAW_SIZE
    assert all(module.NUMBER_MIN <= value <= module.NUMBER_MAX for value in result.ticket)
    assert result.ticket_objective == module.ticket_objective(result.ticket, result.pair_weights)
    assert dict(result.number_aggregates) == dict(module.incident_pair_sums(result.pair_weights))

    payload = result.canonical_dict()
    assert tuple(payload) == (
        "method_id",
        "design_name",
        "status",
        "window_size",
        "recurrence_cap",
        "sentinel_age",
        "pair_weights",
        "number_aggregates",
        "ticket_objective",
        "ticket",
    )
    assert " " not in result.canonical_json()
    assert all(isinstance(value, int) for value in result.pair_weights.values())


def test_complete_slice_reads_only_the_causal_window_and_repeats_deterministically(
    complete_case: tuple[RecordingHistory, module.AnalysisResult],
) -> None:
    history, result = complete_case
    repeated = module.analyze(history, 300)

    assert result.canonical_bytes() == repeated.canonical_bytes()
    assert set(history.read_indices) == set(range(44, 300))
    assert all(index < 300 for index in history.read_indices)
