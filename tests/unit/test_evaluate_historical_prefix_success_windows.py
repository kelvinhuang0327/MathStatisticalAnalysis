"""Application tests for persisted Historical Prefix success windows."""

from __future__ import annotations

from dataclasses import fields

import pytest
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
    HistoricalPrefixStrategySuccessMatrixCell,
    HistoricalPrefixStrategySuccessWindowResult,
    HistoricalPrefixSuccessCriterion,
    HistoricalPrefixSuccessEvaluationStatus,
    HistoricalPrefixSuccessImportNotFoundError,
    HistoricalPrefixSuccessStrategyNotFoundError,
    HistoricalPrefixSuccessWindowsContractError,
    HistoricalPrefixSuccessWindowSource,
    HistoricalPrefixWindowRateComparisonKind,
)
from lottolab.application.use_cases.evaluate_historical_prefix_success_windows import (
    EvaluateHistoricalPrefixSuccessWindows,
)
from lottolab.domain.strategy_success_evaluation import (
    SuccessCriterion,
    WindowEvaluationStatus,
    WindowKind,
    WindowSuccessSummary,
)
from lottolab.domain.strategy_success_measurement import (
    BigLottoPortfolioOutcomeSignature,
    EvidenceStatus,
    MeasurementMode,
    StrategySuccessMeasurement,
    WindowRole,
)

IMPORT_IDENTITY = "a" * 64


class _Reader:
    def __init__(self, source: HistoricalPrefixSuccessWindowSource | None) -> None:
        self.source = source
        self.calls: list[str] = []

    def load_source(
        self, import_identity_sha256: str
    ) -> HistoricalPrefixSuccessWindowSource | None:
        self.calls.append(import_identity_sha256)
        return self.source


class _Factory:
    def __init__(self, source: HistoricalPrefixSuccessWindowSource | None) -> None:
        self.reader = _Reader(source)
        self.calls = 0

    def __call__(self) -> _Reader:
        self.calls += 1
        return self.reader


def _evaluator(
    source: HistoricalPrefixSuccessWindowSource | None,
) -> tuple[EvaluateHistoricalPrefixSuccessWindows, _Factory]:
    factory = _Factory(source)
    return EvaluateHistoricalPrefixSuccessWindows(factory), factory


@pytest.mark.parametrize(
    ("criterion", "minimum_main_hits", "require_special_hit"),
    [
        (HistoricalPrefixSuccessCriterion.M3_PLUS, 3, False),
        (HistoricalPrefixSuccessCriterion.M4_PLUS, 4, False),
        (HistoricalPrefixSuccessCriterion.M5_PLUS, 5, False),
        (HistoricalPrefixSuccessCriterion.M6, 6, False),
        (HistoricalPrefixSuccessCriterion.M2_PLUS_SPECIAL, 2, True),
        (HistoricalPrefixSuccessCriterion.M3_PLUS_SPECIAL, 3, True),
        (HistoricalPrefixSuccessCriterion.M4_PLUS_SPECIAL, 4, True),
        (HistoricalPrefixSuccessCriterion.M5_PLUS_SPECIAL, 5, True),
    ],
)
def test_closed_criteria_map_exactly_to_legal_ticket_prize(
    criterion: HistoricalPrefixSuccessCriterion,
    minimum_main_hits: int,
    require_special_hit: bool,
) -> None:
    observations = build_success_observations(
        1,
        outcome_factory=lambda _observation, position: (
            (minimum_main_hits, require_special_hit) if position == 1 else (0, False)
        ),
    )
    source = build_success_source(
        (build_success_strategy(observations=observations),)
    )
    evaluator, _ = _evaluator(source)

    result = evaluator.get_strategy(
        import_identity_sha256=IMPORT_IDENTITY,
        strategy_id="strategy-a",
        strategy_version="v1",
        replicate=1,
        prefix_count=1,
        criterion=criterion,
    )

    assert result.criterion.criterion is criterion
    assert result.criterion.minimum_main_hits == minimum_main_hits
    assert result.criterion.require_special_hit is require_special_hit
    assert result.criterion.measurement_mode is MeasurementMode.LEGAL_TICKET_PRIZE
    assert result.windows[0].success_count == 1


def test_first_n_preserves_ticket_order_duplicates_and_selection_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    signatures = {
        1: (3, False),
        2: (3, False),
        3: (2, True),
        4: (1, False),
        5: (0, False),
        20: (6, False),
    }
    observations = build_success_observations(
        1,
        outcome_factory=lambda _observation, position: signatures.get(position, (0, False)),
    )
    source = build_success_source(
        (build_success_strategy(observations=observations),)
    )
    captured: list[StrategySuccessMeasurement] = []
    original = module.evaluate_strategy_success_windows

    def spy(
        measurements: tuple[StrategySuccessMeasurement, ...], criterion: SuccessCriterion
    ) -> tuple[WindowSuccessSummary, ...]:
        captured.extend(measurements)
        return original(measurements, criterion)

    monkeypatch.setattr(module, "evaluate_strategy_success_windows", spy)
    evaluator, _ = _evaluator(source)
    result = evaluator.get_strategy(
        import_identity_sha256=IMPORT_IDENTITY,
        strategy_id="strategy-a",
        strategy_version="v1",
        replicate=1,
        prefix_count=5,
        criterion=HistoricalPrefixSuccessCriterion.M3_PLUS,
    )

    assert result.windows[0].success_count == 1
    assert result.selection.ticket_count == 5
    assert result.selection.max_bet_index == 5
    outcome = captured[0].outcome_signature
    assert type(outcome) is BigLottoPortfolioOutcomeSignature
    assert [(item.main_hits, item.special_hit) for item in outcome.tickets] == [
        (3, False),
        (3, False),
        (2, True),
        (1, False),
        (0, False),
    ]


def test_special_success_requires_main_and_special_on_the_same_atomic_ticket() -> None:
    observations = build_success_observations(
        1,
        outcome_factory=lambda _observation, position: (
            (2, False) if position == 1 else (0, True) if position == 2 else (0, False)
        ),
    )
    source = build_success_source(
        (build_success_strategy(observations=observations),)
    )
    evaluator, _ = _evaluator(source)

    result = evaluator.get_strategy(
        import_identity_sha256=IMPORT_IDENTITY,
        strategy_id="strategy-a",
        strategy_version="v1",
        replicate=1,
        prefix_count=2,
        criterion=HistoricalPrefixSuccessCriterion.M2_PLUS_SPECIAL,
    )

    assert result.windows[0].success_count == 0
    assert result.windows[0].failure_count == 1


def test_windows_use_latest_750_300_50_observations_and_exact_integer_rates() -> None:
    observations = build_success_observations(
        751,
        outcome_factory=lambda observation, position: (
            (3, False)
            if position == 1 and (observation == 0 or observation >= 701)
            else (0, False)
        ),
    )
    source = build_success_source(
        (build_success_strategy(observations=tuple(reversed(observations))),)
    )
    evaluator, factory = _evaluator(source)

    result = evaluator.get_strategy(
        import_identity_sha256=IMPORT_IDENTITY,
        strategy_id="strategy-a",
        strategy_version="v1",
        replicate=1,
        prefix_count=1,
        criterion=HistoricalPrefixSuccessCriterion.M3_PLUS,
    )

    assert factory.calls == 1
    assert factory.reader.calls == [IMPORT_IDENTITY]
    assert [item.source_draw_count for item in result.windows] == [751, 750, 300, 50]
    assert [item.success_count for item in result.windows] == [51, 50, 50, 50]
    assert [item.success_rate.numerator for item in result.windows] == [51, 50, 50, 50]
    assert [item.success_rate.denominator for item in result.windows] == [751, 750, 300, 50]
    assert [item.first_target.draw_number for item in result.windows] == [1, 2, 452, 702]
    assert [item.last_target.draw_number for item in result.windows] == [751] * 4
    assert [item.window_role for item in result.windows] == [
        WindowRole.REFERENCE_ONLY,
        WindowRole.PRIMARY_EVIDENCE,
        WindowRole.STABILITY_CONFIRMATION,
        WindowRole.DEGRADATION_VETO,
    ]
    assert all(item.nested_windows_independent is False for item in result.windows)
    assert all(item.evidence_status is EvidenceStatus.DESCRIPTIVE_ONLY for item in result.windows)


@pytest.mark.parametrize(
    ("count", "expected_statuses"),
    [
        (
            300,
            (
                WindowEvaluationStatus.COMPLETE,
                WindowEvaluationStatus.INSUFFICIENT_DRAWS,
                WindowEvaluationStatus.COMPLETE,
                WindowEvaluationStatus.COMPLETE,
            ),
        ),
        (
            50,
            (
                WindowEvaluationStatus.COMPLETE,
                WindowEvaluationStatus.INSUFFICIENT_DRAWS,
                WindowEvaluationStatus.INSUFFICIENT_DRAWS,
                WindowEvaluationStatus.COMPLETE,
            ),
        ),
        (
            49,
            (
                WindowEvaluationStatus.COMPLETE,
                WindowEvaluationStatus.INSUFFICIENT_DRAWS,
                WindowEvaluationStatus.INSUFFICIENT_DRAWS,
                WindowEvaluationStatus.INSUFFICIENT_DRAWS,
            ),
        ),
    ],
)
def test_incomplete_fixed_windows_remain_not_ready_with_unavailable_rate(
    count: int,
    expected_statuses: tuple[WindowEvaluationStatus, ...],
) -> None:
    source = build_success_source(
        (
            build_success_strategy(
                observations=build_success_observations(
                    count,
                    outcome_factory=lambda _observation, position: (
                        (3, False) if position == 1 else (0, False)
                    ),
                )
            ),
        )
    )
    evaluator, _ = _evaluator(source)

    result = evaluator.get_strategy(
        import_identity_sha256=IMPORT_IDENTITY,
        strategy_id="strategy-a",
        strategy_version="v1",
        replicate=1,
        prefix_count=1,
        criterion=HistoricalPrefixSuccessCriterion.M3_PLUS,
    )

    assert tuple(item.evaluation_status for item in result.windows) == expected_statuses
    for item in result.windows:
        if item.evaluation_status is WindowEvaluationStatus.COMPLETE:
            assert item.success_rate.available is True
        else:
            assert item.success_rate == module.HistoricalPrefixExactSuccessRate(0, 0, False)
            assert item.evidence_status is EvidenceStatus.NOT_READY


def test_zero_observation_descriptor_stays_visible_without_fabricated_windows() -> None:
    source = build_success_source((build_success_strategy(),))
    evaluator, _ = _evaluator(source)

    page = evaluator.list_strategies(
        import_identity_sha256=IMPORT_IDENTITY,
        prefix_count=20,
        criterion=HistoricalPrefixSuccessCriterion.M6,
    )

    assert page.total_count == 1
    assert page.items[0].status is HistoricalPrefixSuccessEvaluationStatus.NO_OBSERVATIONS
    assert page.items[0].source_observation_count == 0
    assert page.items[0].windows == ()


def test_descriptor_order_aliases_replicates_and_pagination_are_preserved() -> None:
    observations = build_success_observations(1)
    source = build_success_source(
        (
            build_success_strategy("z-first", observations=observations),
            build_success_strategy(
                "alias",
                effective_strategy_id="base",
                alias_of_strategy_id="base",
                observations=observations,
            ),
            build_success_strategy("base", replicate=2, observations=observations),
            build_success_strategy("base", replicate=1, observations=observations),
        )
    )
    evaluator, _ = _evaluator(source)

    page = evaluator.list_strategies(
        import_identity_sha256=IMPORT_IDENTITY,
        prefix_count=1,
        criterion=HistoricalPrefixSuccessCriterion.M3_PLUS,
        limit=2,
        offset=1,
    )

    assert page.total_count == 4
    assert [(item.strategy.strategy_id, item.strategy.replicate) for item in page.items] == [
        ("alias", 1),
        ("base", 2),
    ]
    assert page.items[0].selection.strategy_id == "alias"
    assert page.items[0].strategy.effective_strategy_id == "base"
    assert page.items[1].selection.replicate == 2
    assert not any(field.name in {"rank", "ranking", "promotion"} for field in fields(page))


def test_exact_strategy_and_repeated_results_are_deterministic() -> None:
    source = build_success_source(
        (build_success_strategy(observations=build_success_observations(3)),)
    )
    evaluator, _ = _evaluator(source)
    first = evaluator.get_strategy(
        import_identity_sha256=IMPORT_IDENTITY,
        strategy_id="strategy-a",
        strategy_version="v1",
        replicate=1,
        prefix_count=10,
        criterion=HistoricalPrefixSuccessCriterion.M4_PLUS,
    )
    second = evaluator.get_strategy(
        import_identity_sha256=IMPORT_IDENTITY,
        strategy_id="strategy-a",
        strategy_version="v1",
        replicate=1,
        prefix_count=10,
        criterion=HistoricalPrefixSuccessCriterion.M4_PLUS,
    )

    assert first == second


def test_absent_import_and_missing_exact_descriptor_are_distinct() -> None:
    missing_import, _ = _evaluator(None)
    with pytest.raises(HistoricalPrefixSuccessImportNotFoundError):
        missing_import.list_strategies(
            import_identity_sha256=IMPORT_IDENTITY,
            prefix_count=1,
            criterion=HistoricalPrefixSuccessCriterion.M3_PLUS,
        )

    source = build_success_source((build_success_strategy(),))
    evaluator, _ = _evaluator(source)
    with pytest.raises(HistoricalPrefixSuccessStrategyNotFoundError):
        evaluator.get_strategy(
            import_identity_sha256=IMPORT_IDENTITY,
            strategy_id="missing",
            strategy_version="v1",
            replicate=1,
            prefix_count=1,
            criterion=HistoricalPrefixSuccessCriterion.M3_PLUS,
        )


@pytest.mark.parametrize(
    ("overrides"),
    [
        {"import_identity_sha256": "A" * 64},
        {"import_identity_sha256": f" {'a' * 64}"},
        {"import_identity_sha256": "abc"},
        {"prefix_count": 6},
        {"prefix_count": True},
        {"criterion": "M3_PLUS"},
        {"limit": 0},
        {"limit": True},
        {"offset": -1},
        {"offset": False},
    ],
)
def test_invalid_list_input_is_rejected_before_reader_factory(
    overrides: dict[str, object],
) -> None:
    source = build_success_source((build_success_strategy(),))
    evaluator, factory = _evaluator(source)
    arguments: dict[str, object] = {
        "import_identity_sha256": IMPORT_IDENTITY,
        "prefix_count": 1,
        "criterion": HistoricalPrefixSuccessCriterion.M3_PLUS,
        "limit": 50,
        "offset": 0,
    }
    arguments.update(overrides)

    with pytest.raises(HistoricalPrefixSuccessWindowsContractError):
        evaluator.list_strategies(**arguments)  # pyright: ignore[reportArgumentType]

    assert factory.calls == 0
    assert factory.reader.calls == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"strategy_id": ""},
        {"strategy_id": " padded "},
        {"strategy_version": ""},
        {"strategy_version": " v1"},
        {"replicate": 0},
        {"replicate": True},
    ],
)
def test_invalid_exact_strategy_input_is_rejected_before_reader_factory(
    overrides: dict[str, object],
) -> None:
    source = build_success_source((build_success_strategy(),))
    evaluator, factory = _evaluator(source)
    arguments: dict[str, object] = {
        "import_identity_sha256": IMPORT_IDENTITY,
        "strategy_id": "strategy-a",
        "strategy_version": "v1",
        "replicate": 1,
        "prefix_count": 1,
        "criterion": HistoricalPrefixSuccessCriterion.M3_PLUS,
    }
    arguments.update(overrides)

    with pytest.raises(HistoricalPrefixSuccessWindowsContractError):
        evaluator.get_strategy(**arguments)  # pyright: ignore[reportArgumentType]

    assert factory.calls == 0


def test_result_model_contains_no_ranking_promotion_or_float_rate_fields() -> None:
    forbidden = {"rank", "ranking", "promotion", "score", "prediction", "recommendation"}
    names = {
        field.name
        for model in (HistoricalPrefixStrategySuccessWindowResult,)
        for field in fields(model)
    }

    assert names.isdisjoint(forbidden)


def test_matrix_loads_once_preserves_exact_alias_and_emits_canonical_64_cells() -> None:
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
    evaluator, factory = _evaluator(source)

    matrix = evaluator.get_matrix(
        import_identity_sha256=IMPORT_IDENTITY,
        strategy_id="alias",
        strategy_version="v1",
        replicate=3,
    )

    assert factory.calls == 1
    assert factory.reader.calls == [IMPORT_IDENTITY]
    assert matrix.strategy.strategy_id == "alias"
    assert matrix.strategy.effective_strategy_id == "base"
    assert matrix.strategy.alias_of_strategy_id == "base"
    assert matrix.strategy.replicate == 3
    assert matrix.source_observation_count == 1
    assert matrix.prefix_counts == (1, 2, 3, 4, 5, 10, 15, 20)
    assert tuple(item.criterion for item in matrix.criteria) == tuple(
        HistoricalPrefixSuccessCriterion
    )
    assert matrix.cell_count == len(matrix.cells) == 64
    assert [
        (cell.criterion.criterion, cell.prefix_count) for cell in matrix.cells
    ] == [
        (criterion, prefix)
        for criterion in HistoricalPrefixSuccessCriterion
        for prefix in (1, 2, 3, 4, 5, 10, 15, 20)
    ]
    assert all(cell.selection.strategy_id == "alias" for cell in matrix.cells)
    assert all(cell.selection.replicate == 3 for cell in matrix.cells)
    assert all(
        tuple(window.window_kind for window in cell.windows)
        == (
            WindowKind.FULL_HISTORY,
            WindowKind.LONG,
            WindowKind.MEDIUM,
            WindowKind.SHORT,
        )
        for cell in matrix.cells
    )
    assert all(
        tuple(item.comparison_kind for item in cell.comparisons)
        == tuple(HistoricalPrefixWindowRateComparisonKind)
        for cell in matrix.cells
    )


@pytest.mark.parametrize(
    ("from_rate", "to_rate", "expected"),
    [
        (
            HistoricalPrefixExactSuccessRate(1, 4, True),
            HistoricalPrefixExactSuccessRate(1, 2, True),
            (1, 4, True, HistoricalPrefixRateRelation.HIGHER),
        ),
        (
            HistoricalPrefixExactSuccessRate(3, 4, True),
            HistoricalPrefixExactSuccessRate(1, 2, True),
            (-1, 4, True, HistoricalPrefixRateRelation.LOWER),
        ),
        (
            HistoricalPrefixExactSuccessRate(1, 2, True),
            HistoricalPrefixExactSuccessRate(2, 4, True),
            (0, 1, True, HistoricalPrefixRateRelation.EQUAL),
        ),
        (
            HistoricalPrefixExactSuccessRate(0, 0, False),
            HistoricalPrefixExactSuccessRate(1, 2, True),
            (0, 0, False, HistoricalPrefixRateRelation.UNAVAILABLE),
        ),
    ],
)
def test_signed_rate_delta_is_exact_canonical_and_neutral(
    from_rate: HistoricalPrefixExactSuccessRate,
    to_rate: HistoricalPrefixExactSuccessRate,
    expected: tuple[int, int, bool, HistoricalPrefixRateRelation],
) -> None:
    delta, relation = module._signed_rate_delta(  # pyright: ignore[reportPrivateUsage]
        from_rate, to_rate
    )

    assert (delta.numerator, delta.denominator, delta.available, relation) == expected


def test_zero_observation_matrix_retains_all_cells_without_windows_or_comparisons() -> None:
    evaluator, _ = _evaluator(
        build_success_source((build_success_strategy("zero"),))
    )

    matrix = evaluator.get_matrix(
        import_identity_sha256=IMPORT_IDENTITY,
        strategy_id="zero",
        strategy_version="v1",
        replicate=1,
    )

    assert matrix.cell_count == len(matrix.cells) == 64
    assert matrix.source_observation_count == 0
    assert all(
        cell.status is HistoricalPrefixSuccessEvaluationStatus.NO_OBSERVATIONS
        and cell.source_observation_count == 0
        and cell.windows == ()
        and cell.comparisons == ()
        for cell in matrix.cells
    )


def test_matrix_is_deterministic_and_invalid_identity_is_rejected_before_factory() -> None:
    evaluator, factory = _evaluator(
        build_success_source(
            (
                build_success_strategy(
                    observations=build_success_observations(2),
                ),
            )
        )
    )
    first = evaluator.get_matrix(
        import_identity_sha256=IMPORT_IDENTITY,
        strategy_id="strategy-a",
        strategy_version="v1",
        replicate=1,
    )
    second = evaluator.get_matrix(
        import_identity_sha256=IMPORT_IDENTITY,
        strategy_id="strategy-a",
        strategy_version="v1",
        replicate=1,
    )

    assert first == second
    assert factory.calls == 2
    invalid_evaluator, invalid_factory = _evaluator(
        build_success_source((build_success_strategy(),))
    )
    with pytest.raises(HistoricalPrefixSuccessWindowsContractError):
        invalid_evaluator.get_matrix(
            import_identity_sha256=IMPORT_IDENTITY,
            strategy_id=" padded ",
            strategy_version="v1",
            replicate=1,
        )
    assert invalid_factory.calls == 0


def test_matrix_models_contain_no_ranking_promotion_prediction_or_float_fields() -> None:
    forbidden = {
        "rank",
        "ranking",
        "promotion",
        "score",
        "prediction",
        "recommendation",
        "threshold",
        "confidence",
    }
    names = {
        field.name
        for model in (
            HistoricalPrefixStrategySuccessMatrix,
            HistoricalPrefixStrategySuccessMatrixCell,
        )
        for field in fields(model)
    }

    assert names.isdisjoint(forbidden)
