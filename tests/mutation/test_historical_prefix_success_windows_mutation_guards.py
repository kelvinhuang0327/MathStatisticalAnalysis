"""Independent behavioral guards for success-window mutation checks."""

from __future__ import annotations

from pathlib import Path

from tests.fixtures.historical.success_window_builder import (
    build_success_observations,
    build_success_source,
    build_success_strategy,
)

import lottolab.application.use_cases.evaluate_historical_prefix_success_windows as module
from lottolab.application.historical_prefix_success_windows import (
    HistoricalPrefixExactSuccessRate,
    HistoricalPrefixRateRelation,
    HistoricalPrefixStrategySuccessMatrix,
    HistoricalPrefixStrategySuccessWindowResult,
    HistoricalPrefixSuccessCriterion,
    HistoricalPrefixSuccessWindowSource,
)
from lottolab.application.use_cases.evaluate_historical_prefix_success_windows import (
    EvaluateHistoricalPrefixSuccessWindows,
)
from lottolab.domain.strategy_success_evaluation import WindowEvaluationStatus

IMPORT_IDENTITY = "a" * 64
ROOT = Path(__file__).resolve().parents[2]
USE_CASE = (
    ROOT
    / "src/lottolab/application/use_cases/evaluate_historical_prefix_success_windows.py"
)
READER = (
    ROOT
    / "src/lottolab/infrastructure/persistence/"
    "historical_prefix_success_window_reader.py"
)
MEASUREMENT = ROOT / "src/lottolab/domain/strategy_success_measurement.py"
EVALUATION = ROOT / "src/lottolab/domain/strategy_success_evaluation.py"
API = ROOT / "src/lottolab/interfaces/api/historical_prefix_success_windows.py"


class _Reader:
    def __init__(self, source: HistoricalPrefixSuccessWindowSource) -> None:
        self.source = source
        self.calls = 0

    def load_source(
        self, import_identity_sha256: str
    ) -> HistoricalPrefixSuccessWindowSource:
        assert import_identity_sha256 == IMPORT_IDENTITY
        self.calls += 1
        return self.source


def _evaluate(
    source: HistoricalPrefixSuccessWindowSource,
    *,
    prefix: int = 1,
    criterion: HistoricalPrefixSuccessCriterion = HistoricalPrefixSuccessCriterion.M3_PLUS,
) -> HistoricalPrefixStrategySuccessWindowResult:
    reader = _Reader(source)
    result = EvaluateHistoricalPrefixSuccessWindows(lambda: reader).get_strategy(
        import_identity_sha256=IMPORT_IDENTITY,
        strategy_id=source.strategies[0].identity.strategy_id,
        strategy_version=source.strategies[0].identity.strategy_version,
        replicate=source.strategies[0].identity.replicate,
        prefix_count=prefix,
        criterion=criterion,
    )
    assert reader.calls == 1
    return result


def _matrix(
    source: HistoricalPrefixSuccessWindowSource,
) -> tuple[HistoricalPrefixStrategySuccessMatrix, _Reader]:
    reader = _Reader(source)
    strategy = source.strategies[0].identity
    result = EvaluateHistoricalPrefixSuccessWindows(lambda: reader).get_matrix(
        import_identity_sha256=IMPORT_IDENTITY,
        strategy_id=strategy.strategy_id,
        strategy_version=strategy.strategy_version,
        replicate=strategy.replicate,
    )
    return result, reader


def test_guard_first_n_not_last_n_and_special_requirement_not_ignored() -> None:
    observations = build_success_observations(
        1,
        outcome_factory=lambda _observation, position: (
            (3, False)
            if position == 1
            else (2, True)
            if position == 2
            else (6, False)
            if position == 20
            else (0, False)
        ),
    )
    source = build_success_source(
        (build_success_strategy(observations=observations),)
    )

    first = _evaluate(source, prefix=1)
    first_two_special = _evaluate(
        source,
        prefix=2,
        criterion=HistoricalPrefixSuccessCriterion.M3_PLUS_SPECIAL,
    )

    assert first.windows[0].success_count == 1
    assert first_two_special.windows[0].success_count == 0


def test_guard_atomic_same_ticket_never_aggregates_main_and_special() -> None:
    observations = build_success_observations(
        1,
        outcome_factory=lambda _observation, position: (
            (2, False) if position == 1 else (0, True) if position == 2 else (0, False)
        ),
    )
    source = build_success_source(
        (build_success_strategy(observations=observations),)
    )

    result = _evaluate(
        source,
        prefix=2,
        criterion=HistoricalPrefixSuccessCriterion.M2_PLUS_SPECIAL,
    )

    assert result.windows[0].success_count == 0
    assert result.windows[0].failure_count == 1


def test_guard_exact_alias_effective_id_and_replicate_axes() -> None:
    source = build_success_source(
        (
            build_success_strategy(
                "alias",
                effective_strategy_id="base",
                alias_of_strategy_id="base",
                replicate=3,
                observations=build_success_observations(1),
            ),
        )
    )

    result = _evaluate(source)

    assert result.strategy.strategy_id == "alias"
    assert result.strategy.effective_strategy_id == "base"
    assert result.strategy.alias_of_strategy_id == "base"
    assert result.strategy.replicate == 3
    assert result.selection.strategy_id == "alias"
    assert result.selection.replicate == 3


def test_guard_exact_window_sizes_nested_flag_and_latest_source_slice() -> None:
    observations = build_success_observations(
        751,
        outcome_factory=lambda observation, position: (
            (3, False)
            if position == 1 and (observation == 0 or observation >= 701)
            else (0, False)
        ),
    )
    result = _evaluate(
        build_success_source(
            (build_success_strategy(observations=tuple(reversed(observations))),)
        )
    )

    assert [item.requested_draw_count for item in result.windows] == [None, 750, 300, 50]
    assert [item.source_draw_count for item in result.windows] == [751, 750, 300, 50]
    assert [item.success_count for item in result.windows] == [51, 50, 50, 50]
    assert [item.first_target.draw_number for item in result.windows] == [1, 2, 452, 702]
    assert all(item.nested_windows_independent is False for item in result.windows)


def test_guard_zero_observation_and_incomplete_windows_are_not_upgraded() -> None:
    zero = _evaluate(build_success_source((build_success_strategy(),)))
    short = _evaluate(
        build_success_source(
            (build_success_strategy(observations=build_success_observations(49)),)
        )
    )

    assert zero.status.value == "NO_OBSERVATIONS"
    assert zero.windows == ()
    assert all(
        item.evaluation_status is WindowEvaluationStatus.INSUFFICIENT_DRAWS
        for item in short.windows[1:]
    )
    assert all(item.success_rate.available is False for item in short.windows[1:])
    assert all(
        (item.success_rate.numerator, item.success_rate.denominator) == (0, 0)
        for item in short.windows[1:]
    )


def test_guard_page_preserves_descriptor_order_instead_of_success_rate_sort() -> None:
    losing = build_success_observations(1)
    winning = build_success_observations(
        1,
        outcome_factory=lambda _observation, position: (
            (3, False) if position == 1 else (0, False)
        ),
    )
    source = build_success_source(
        (
            build_success_strategy("losing-first", observations=losing),
            build_success_strategy("winning-second", observations=winning),
        )
    )
    reader = _Reader(source)

    page = EvaluateHistoricalPrefixSuccessWindows(lambda: reader).list_strategies(
        import_identity_sha256=IMPORT_IDENTITY,
        prefix_count=1,
        criterion=HistoricalPrefixSuccessCriterion.M3_PLUS,
    )

    assert [item.strategy.strategy_id for item in page.items] == [
        "losing-first",
        "winning-second",
    ]
    assert [item.windows[0].success_count for item in page.items] == [0, 1]


def test_guard_first_n_source_slice() -> None:
    use_case = USE_CASE.read_text(encoding="utf-8")

    assert "observation.tickets[:prefix_count]" in use_case
    assert "observation.tickets[-prefix_count:]" not in use_case


def test_guard_ticket_tuple_is_not_sorted() -> None:
    use_case = USE_CASE.read_text(encoding="utf-8")
    measurement = use_case.split("def _measurement(", 1)[1].split(
        "def _window_read_model(", 1
    )[0]

    assert "for ticket in selected_tickets" in measurement
    assert "sorted(" not in measurement


def test_guard_duplicate_tickets_are_not_deduplicated() -> None:
    use_case = USE_CASE.read_text(encoding="utf-8")

    assert "dict.fromkeys" not in use_case


def test_guard_effective_strategy_id_is_not_substituted() -> None:
    use_case = USE_CASE.read_text(encoding="utf-8")

    assert use_case.count("strategy_id=strategy.identity.strategy_id") >= 2
    assert "strategy_id=strategy.identity.effective_strategy_id" not in use_case


def test_guard_replicate_is_retained_in_selection() -> None:
    use_case = USE_CASE.read_text(encoding="utf-8")

    assert "replicate=strategy.identity.replicate" in use_case


def test_guard_no_aggregate_main_special_reconstruction() -> None:
    use_case = USE_CASE.read_text(encoding="utf-8")

    assert "maximum_main_hits" not in use_case
    assert "any(ticket.special_hit" not in use_case


def test_guard_all_special_criteria_require_special() -> None:
    use_case = USE_CASE.read_text(encoding="utf-8")

    for name, minimum in (
        ("M2_PLUS_SPECIAL", 2),
        ("M3_PLUS_SPECIAL", 3),
        ("M4_PLUS_SPECIAL", 4),
        ("M5_PLUS_SPECIAL", 5),
    ):
        assert f"HistoricalPrefixSuccessCriterion.{name}: ({minimum}, True)" in use_case


def test_guard_ticket_count_and_max_bet_index_bind_prefix() -> None:
    use_case = USE_CASE.read_text(encoding="utf-8")

    assert use_case.count("ticket_count=prefix_count") >= 2
    assert use_case.count("max_bet_index=prefix_count") >= 2


def test_guard_atomic_portfolio_outcome_type_is_used() -> None:
    use_case = USE_CASE.read_text(encoding="utf-8")

    assert "BigLottoPortfolioOutcomeSignature(" in use_case


def test_guard_exact_750_300_50_defaults() -> None:
    measurement = MEASUREMENT.read_text(encoding="utf-8")

    assert "long_draws: int = 750" in measurement
    assert "medium_draws: int = 300" in measurement
    assert "short_draws: int = 50" in measurement


def test_guard_nested_windows_are_not_independent() -> None:
    measurement = MEASUREMENT.read_text(encoding="utf-8")

    assert "nested_windows_independent: bool = False" in measurement


def test_guard_descriptor_source_order_is_not_reversed() -> None:
    reader = READER.read_text(encoding="utf-8")

    assert "for descriptor in descriptors" in reader
    assert "for descriptor in reversed(descriptors)" not in reader


def test_guard_target_draw_sort_is_numeric_not_lexicographic() -> None:
    use_case = USE_CASE.read_text(encoding="utf-8")

    assert "key=lambda item: (item.target.draw_date, item.target.draw_number)" in use_case
    assert "str(item.target.draw_number)" not in use_case


def test_guard_validation_precedes_reader_factory() -> None:
    use_case = USE_CASE.read_text(encoding="utf-8")
    list_method = use_case.split("def list_strategies(", 1)[1].split(
        "def get_strategy(", 1
    )[0]

    assert list_method.index("_validate_import_identity") < list_method.index(
        "source = self._load"
    )


def test_guard_reader_factory_is_called_once() -> None:
    use_case = USE_CASE.read_text(encoding="utf-8")
    load_method = use_case.split("def _load(", 1)[1].split("def list_strategies(", 1)[0]

    assert load_method.count("self._reader_factory()") == 1


def test_guard_reader_operation_is_called_once() -> None:
    use_case = USE_CASE.read_text(encoding="utf-8")
    load_method = use_case.split("def _load(", 1)[1].split("def list_strategies(", 1)[0]

    assert load_method.count("reader.load_source(import_identity_sha256)") == 1


def test_guard_absent_exact_run_never_falls_back_to_latest() -> None:
    reader = READER.read_text(encoding="utf-8")

    assert "WHERE import_identity_sha256 = ? AND status = 'COMPLETED'" in reader
    assert "ORDER BY completed_at DESC" not in reader


def test_guard_sqlite_connection_is_read_only() -> None:
    reader = READER.read_text(encoding="utf-8")

    assert "open_database(self._database, read_only=True)" in reader


def test_guard_zero_observation_descriptors_are_not_filtered() -> None:
    reader = READER.read_text(encoding="utf-8")

    assert "for descriptor in descriptors" in reader
    assert "if observations_by_descriptor[descriptor.snapshot_id]" not in reader


def test_guard_exact_rate_fields_are_integers_not_float() -> None:
    api = API.read_text(encoding="utf-8")

    assert "numerator: int" in api
    assert "denominator: int" in api
    assert "numerator: float" not in api


def test_guard_incomplete_window_is_not_marked_descriptive() -> None:
    evaluation = EVALUATION.read_text(encoding="utf-8")

    assert "if evaluation_status is WindowEvaluationStatus.COMPLETE:" in evaluation


def test_guard_results_are_not_sorted_by_rate() -> None:
    use_case = USE_CASE.read_text(encoding="utf-8")

    assert "key=lambda item: item.windows[0].success_rate" not in use_case


def test_guard_reader_uses_all_remaining_exact_constructs() -> None:
    use_case = USE_CASE.read_text(encoding="utf-8")
    reader = READER.read_text(encoding="utf-8")

    assert "long_draws" not in use_case
    assert "ORDER BY CAST(draw_number AS INTEGER) ASC" in reader
    assert "status = 'COMPLETED'" in reader
    assert "ORDER BY rowid ASC" in reader


def test_guard_matrix_cell_order_count_one_load_identity_and_comparison_order() -> None:
    matrix, reader = _matrix(
        build_success_source(
            (
                build_success_strategy(
                    "alias",
                    effective_strategy_id="base",
                    alias_of_strategy_id="base",
                    replicate=4,
                    observations=build_success_observations(1),
                ),
            )
        )
    )

    assert reader.calls == 1
    assert matrix.cell_count == len(matrix.cells) == 64
    assert [
        (cell.criterion.criterion.value, cell.prefix_count) for cell in matrix.cells
    ] == [
        (criterion.value, prefix)
        for criterion in HistoricalPrefixSuccessCriterion
        for prefix in (1, 2, 3, 4, 5, 10, 15, 20)
    ]
    assert matrix.strategy.strategy_id == "alias"
    assert matrix.strategy.effective_strategy_id == "base"
    assert matrix.strategy.alias_of_strategy_id == "base"
    assert matrix.strategy.replicate == 4
    assert all(cell.selection.strategy_id == "alias" for cell in matrix.cells)
    assert all(cell.selection.replicate == 4 for cell in matrix.cells)
    assert [
        item.comparison_kind.value for item in matrix.cells[0].comparisons
    ] == [
        "FULL_HISTORY_TO_LONG",
        "LONG_TO_MEDIUM",
        "MEDIUM_TO_SHORT",
        "LONG_TO_SHORT",
    ]


def test_guard_signed_deltas_detect_direction_zero_and_unavailable() -> None:
    higher, higher_relation = module._signed_rate_delta(  # pyright: ignore[reportPrivateUsage]
        HistoricalPrefixExactSuccessRate(1, 4, True),
        HistoricalPrefixExactSuccessRate(2, 4, True),
    )
    lower, lower_relation = module._signed_rate_delta(  # pyright: ignore[reportPrivateUsage]
        HistoricalPrefixExactSuccessRate(3, 4, True),
        HistoricalPrefixExactSuccessRate(1, 2, True),
    )
    equal, equal_relation = module._signed_rate_delta(  # pyright: ignore[reportPrivateUsage]
        HistoricalPrefixExactSuccessRate(1, 2, True),
        HistoricalPrefixExactSuccessRate(2, 4, True),
    )
    unavailable, unavailable_relation = module._signed_rate_delta(  # pyright: ignore[reportPrivateUsage]
        HistoricalPrefixExactSuccessRate(0, 0, False),
        HistoricalPrefixExactSuccessRate(1, 2, True),
    )

    assert (higher.numerator, higher.denominator, higher_relation) == (
        1,
        4,
        HistoricalPrefixRateRelation.HIGHER,
    )
    assert (lower.numerator, lower.denominator, lower_relation) == (
        -1,
        4,
        HistoricalPrefixRateRelation.LOWER,
    )
    assert (equal.numerator, equal.denominator, equal_relation) == (
        0,
        1,
        HistoricalPrefixRateRelation.EQUAL,
    )
    assert (
        unavailable.numerator,
        unavailable.denominator,
        unavailable.available,
        unavailable_relation,
    ) == (0, 0, False, HistoricalPrefixRateRelation.UNAVAILABLE)


def test_guard_matrix_zero_observation_never_fabricates_rates() -> None:
    matrix, _ = _matrix(
        build_success_source((build_success_strategy("zero"),))
    )

    assert len(matrix.cells) == 64
    assert all(cell.windows == () and cell.comparisons == () for cell in matrix.cells)


def test_guard_matrix_source_has_no_per_cell_reader_or_rate_sorting() -> None:
    use_case = USE_CASE.read_text(encoding="utf-8")
    matrix_method = use_case.split("def get_matrix(", 1)[1].split(
        "def get_feature_cohorts(", 1
    )[0]

    assert matrix_method.count("source = self._load(import_identity_sha256)") == 1
    assert matrix_method.count("_find_exact_strategy(") == 1
    assert "for criterion in SUPPORTED_SUCCESS_CRITERIA" in matrix_method
    assert "for prefix_count in SUPPORTED_PREFIX_COUNTS" in matrix_method
    assert "sorted(" not in matrix_method
    assert "success_rate" not in matrix_method


def test_guard_matrix_relation_vocabulary_stays_neutral() -> None:
    source = API.read_text(encoding="utf-8")
    forbidden = ("IMPROVED", "DEGRADED", "WINNER", "PROMOTE", "REJECT")

    assert "HistoricalPrefixRateRelation" in source
    assert all(word not in source for word in forbidden)


def test_guard_walk_forward_snapshot_excludes_current_and_future_targets_before_label() -> None:
    use_case = USE_CASE.read_text(encoding="utf-8")
    cohorts = use_case.split("def _feature_cohorts(", 1)[1].split(
        "def _matrix_cell(", 1
    )[0]

    assert "prior_observations=observations[:index]" in cohorts
    assert "prior_observations=observations[: index + 1]" not in cohorts
    assert "prior_observations=observations[index:]" not in cohorts
    assert cohorts.index("feature_key = _snapshot_feature_key(") < cohorts.index(
        "succeeded = _current_target_succeeded("
    )


def test_guard_walk_forward_assigns_each_target_once_without_rate_sorting() -> None:
    use_case = USE_CASE.read_text(encoding="utf-8")
    cohorts = use_case.split("def _feature_cohorts(", 1)[1].split(
        "def _matrix_cell(", 1
    )[0]

    assert cohorts.count("assignments.setdefault(feature_key, []).append(") == 1
    assert (
        "sum(cohort.observation_count for cohort in cohorts) != baseline_count"
        in cohorts
    )
    assert "sorted(" not in cohorts


def test_guard_walk_forward_canonical_relation_order_and_exact_delta_direction() -> None:
    use_case = USE_CASE.read_text(encoding="utf-8")
    cohorts = use_case.split("def _feature_cohorts(", 1)[1].split(
        "def _matrix_cell(", 1
    )[0]

    long_loop = cohorts.index(
        "for long_to_medium in FEATURE_COHORT_RELATION_ORDER:"
    )
    medium_loop = cohorts.index(
        "for medium_to_short in FEATURE_COHORT_RELATION_ORDER:"
    )
    short_loop = cohorts.index(
        "for long_to_short in FEATURE_COHORT_RELATION_ORDER:"
    )
    assert long_loop < medium_loop < short_loop
    assert "_signed_rate_delta(baseline_rate, cohort_rate)" in cohorts
    assert "_signed_rate_delta(cohort_rate, baseline_rate)" not in cohorts


def test_guard_walk_forward_method_has_one_load_and_one_exact_strategy_lookup() -> None:
    use_case = USE_CASE.read_text(encoding="utf-8")
    method = use_case.split("def get_feature_cohorts(", 1)[1].split(
        '__all__ = ["EvaluateHistoricalPrefixSuccessWindows"]', 1
    )[0]

    assert method.count("source = self._load(import_identity_sha256)") == 1
    assert method.count("_find_exact_strategy(") == 1
    assert "for " not in method.split("source = self._load", 1)[0]


def test_guard_walk_forward_relation_vocabulary_stays_neutral() -> None:
    use_case = USE_CASE.read_text(encoding="utf-8")
    cohorts = use_case.split("def _snapshot_feature_key(", 1)[1].split(
        "def _matrix_cell(", 1
    )[0]

    assert "HistoricalPrefixRateRelation" in cohorts
    assert not any(
        word in cohorts
        for word in (
            "IMPROVED",
            "DEGRADED",
            "GOOD",
            "BAD",
            "PROMOTE",
            "REJECT",
        )
    )
