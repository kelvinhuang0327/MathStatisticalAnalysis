"""Use-case tests for the separate Historical Prefix random baseline operation."""

from __future__ import annotations

import dataclasses

import pytest
from tests.fixtures.historical.success_window_builder import (
    build_success_observations,
    build_success_source,
    build_success_strategy,
)

import lottolab.application.use_cases.evaluate_historical_prefix_success_windows as module
from lottolab.application.historical_prefix_success_windows import (
    HistoricalPrefixSuccessCriterion,
    HistoricalPrefixSuccessSourceObservation,
    HistoricalPrefixSuccessWindowsContractError,
    HistoricalPrefixSuccessWindowSource,
)
from lottolab.application.historical_success_random_baseline import (
    HistoricalSuccessRandomBaselineNotReadyReason,
    HistoricalSuccessRandomBaselineReadiness,
)
from lottolab.application.use_cases.evaluate_historical_prefix_success_windows import (
    EvaluateHistoricalPrefixSuccessWindows,
)
from lottolab.domain.strategy_success_evaluation import WindowKind

IMPORT_IDENTITY = "a" * 64


class _Reader:
    def __init__(self, source: HistoricalPrefixSuccessWindowSource) -> None:
        self.source = source
        self.calls = 0

    def load_source(self, import_identity_sha256: str) -> HistoricalPrefixSuccessWindowSource:
        assert import_identity_sha256 == IMPORT_IDENTITY
        self.calls += 1
        return self.source


class _Factory:
    def __init__(self, source: HistoricalPrefixSuccessWindowSource) -> None:
        self.reader = _Reader(source)
        self.calls = 0

    def __call__(self) -> _Reader:
        self.calls += 1
        return self.reader


def _raw_ticket_numbers(main_hits: int, *, official_special_hit: bool = False) -> tuple[int, ...]:
    values = list(range(1, main_hits + 1))
    if official_special_hit:
        values.append(7)
    filler = 8
    while len(values) < 6:
        values.append(filler)
        filler += 1
    return tuple(sorted(values))


def _with_raw_operands(
    observations: tuple[HistoricalPrefixSuccessSourceObservation, ...],
    *,
    official_special_positions: frozenset[tuple[int, int]] = frozenset(),
) -> tuple[HistoricalPrefixSuccessSourceObservation, ...]:
    return tuple(
        dataclasses.replace(
            observation,
            target_main_numbers=(1, 2, 3, 4, 5, 6),
            target_special_number=7,
            tickets=tuple(
                dataclasses.replace(
                    ticket,
                    main_numbers=_raw_ticket_numbers(
                        ticket.main_hit_count,
                        official_special_hit=(
                            (observation_index, ticket.portfolio_position)
                            in official_special_positions
                        ),
                    ),
                )
                for ticket in observation.tickets
            ),
        )
        for observation_index, observation in enumerate(observations)
    )


def _source(
    observations: tuple[HistoricalPrefixSuccessSourceObservation, ...],
) -> HistoricalPrefixSuccessWindowSource:
    return build_success_source(
        (build_success_strategy(observations=observations),)
    )


def _baseline(
    evaluator: EvaluateHistoricalPrefixSuccessWindows,
    *,
    window_kind: WindowKind,
    criterion: HistoricalPrefixSuccessCriterion = HistoricalPrefixSuccessCriterion.M3_PLUS,
    prefix_count: int = 1,
):
    return evaluator.get_random_null_baseline(
        import_identity_sha256=IMPORT_IDENTITY,
        strategy_id="strategy-a",
        strategy_version="v1",
        replicate=1,
        window_kind=window_kind,
        prefix_count=prefix_count,
        criterion=criterion,
    )


def test_one_operation_uses_one_factory_reader_source_load_strategy_and_window_evaluation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observations = _with_raw_operands(
        build_success_observations(
            1,
            outcome_factory=lambda _observation, position: (
                (3, False) if position == 1 else (0, False)
            ),
        )
    )
    factory = _Factory(_source(observations))
    calls = 0
    original = module._evaluate_strategy  # pyright: ignore[reportPrivateUsage]

    def spy(*args: object, **kwargs: object):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "_evaluate_strategy", spy)
    evaluator = EvaluateHistoricalPrefixSuccessWindows(factory)

    result = _baseline(evaluator, window_kind=WindowKind.FULL_HISTORY)

    assert result.readiness is HistoricalSuccessRandomBaselineReadiness.READY
    assert result.observed_success_count == 1
    assert factory.calls == 1
    assert factory.reader.calls == 1
    assert calls == 1


def test_all_selectors_are_validated_before_factory_creation() -> None:
    factory = _Factory(_source(()))
    evaluator = EvaluateHistoricalPrefixSuccessWindows(factory)

    with pytest.raises(HistoricalPrefixSuccessWindowsContractError):
        evaluator.get_random_null_baseline(
            import_identity_sha256="not-a-hash",
            strategy_id="strategy-a",
            strategy_version="v1",
            replicate=1,
            window_kind=WindowKind.FULL_HISTORY,
            prefix_count=1,
            criterion=HistoricalPrefixSuccessCriterion.M3_PLUS,
        )
    with pytest.raises(HistoricalPrefixSuccessWindowsContractError):
        evaluator.get_random_null_baseline(
            import_identity_sha256=IMPORT_IDENTITY,
            strategy_id="strategy-a",
            strategy_version="v1",
            replicate=1,
            window_kind="FULL_HISTORY",  # type: ignore[arg-type]
            prefix_count=1,
            criterion=HistoricalPrefixSuccessCriterion.M3_PLUS,
        )

    assert factory.calls == 0
    assert factory.reader.calls == 0


def test_full_long_medium_and_short_select_exactly_the_existing_ordered_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    success_indices = {0, 1, 451, 701}
    observations = _with_raw_operands(
        build_success_observations(
            751,
            outcome_factory=lambda observation, position: (
                (3, False)
                if observation in success_indices and position == 1
                else (0, False)
            ),
        )
    )
    factory = _Factory(_source(tuple(reversed(observations))))
    evaluator = EvaluateHistoricalPrefixSuccessWindows(factory)
    evaluations = 0
    original = module._evaluate_strategy  # pyright: ignore[reportPrivateUsage]

    def spy(*args: object, **kwargs: object):
        nonlocal evaluations
        evaluations += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "_evaluate_strategy", spy)
    expected = {
        WindowKind.FULL_HISTORY: (751, 4),
        WindowKind.LONG: (750, 3),
        WindowKind.MEDIUM: (300, 2),
        WindowKind.SHORT: (50, 1),
    }

    results = {
        kind: _baseline(evaluator, window_kind=kind)
        for kind in (
            WindowKind.FULL_HISTORY,
            WindowKind.LONG,
            WindowKind.MEDIUM,
            WindowKind.SHORT,
        )
    }

    assert {
        kind: (result.eligible_observation_count, result.observed_success_count)
        for kind, result in results.items()
    } == expected
    assert all(
        result.readiness is HistoricalSuccessRandomBaselineReadiness.READY
        for result in results.values()
    )
    assert factory.calls == 4
    assert factory.reader.calls == 4
    assert evaluations == 4


def test_special_recomputation_can_differ_without_changing_existing_window_output() -> None:
    observations = _with_raw_operands(
        build_success_observations(
            1,
            outcome_factory=lambda _observation, position: (
                (2, False) if position == 1 else (0, False)
            ),
        ),
        official_special_positions=frozenset({(0, 1)}),
    )
    factory = _Factory(_source(observations))
    evaluator = EvaluateHistoricalPrefixSuccessWindows(factory)
    existing_before = evaluator.get_strategy(
        import_identity_sha256=IMPORT_IDENTITY,
        strategy_id="strategy-a",
        strategy_version="v1",
        replicate=1,
        prefix_count=1,
        criterion=HistoricalPrefixSuccessCriterion.M2_PLUS_SPECIAL,
    )

    baseline = _baseline(
        evaluator,
        window_kind=WindowKind.FULL_HISTORY,
        criterion=HistoricalPrefixSuccessCriterion.M2_PLUS_SPECIAL,
    )
    existing_after = evaluator.get_strategy(
        import_identity_sha256=IMPORT_IDENTITY,
        strategy_id="strategy-a",
        strategy_version="v1",
        replicate=1,
        prefix_count=1,
        criterion=HistoricalPrefixSuccessCriterion.M2_PLUS_SPECIAL,
    )

    assert existing_before == existing_after
    assert existing_before.windows[0].success_count == 0
    assert baseline.readiness is HistoricalSuccessRandomBaselineReadiness.READY
    assert baseline.observed_success_count == 1


def test_no_observations_and_incomplete_selected_window_return_closed_not_ready_results() -> None:
    empty_factory = _Factory(_source(()))
    empty = _baseline(
        EvaluateHistoricalPrefixSuccessWindows(empty_factory),
        window_kind=WindowKind.FULL_HISTORY,
    )
    observations = _with_raw_operands(build_success_observations(1))
    incomplete = _baseline(
        EvaluateHistoricalPrefixSuccessWindows(_Factory(_source(observations))),
        window_kind=WindowKind.LONG,
    )

    assert empty.readiness is HistoricalSuccessRandomBaselineReadiness.NOT_READY
    assert empty.reason_codes == (
        HistoricalSuccessRandomBaselineNotReadyReason.NO_OBSERVATIONS,
    )
    assert incomplete.readiness is HistoricalSuccessRandomBaselineReadiness.NOT_READY
    assert incomplete.reason_codes == (
        HistoricalSuccessRandomBaselineNotReadyReason.WINDOW_INCOMPLETE,
    )


def test_missing_raw_forwarding_fails_closed_without_affecting_existing_operation() -> None:
    observations = build_success_observations(1)
    factory = _Factory(_source(observations))
    evaluator = EvaluateHistoricalPrefixSuccessWindows(factory)

    existing = evaluator.get_strategy(
        import_identity_sha256=IMPORT_IDENTITY,
        strategy_id="strategy-a",
        strategy_version="v1",
        replicate=1,
        prefix_count=1,
        criterion=HistoricalPrefixSuccessCriterion.M3_PLUS,
    )
    baseline = _baseline(evaluator, window_kind=WindowKind.FULL_HISTORY)

    assert existing.windows[0].success_count == 0
    assert baseline.readiness is HistoricalSuccessRandomBaselineReadiness.NOT_READY
    assert baseline.reason_codes == (
        HistoricalSuccessRandomBaselineNotReadyReason.SOURCE_TICKET_SEMANTICS_CONFLICT,
    )
