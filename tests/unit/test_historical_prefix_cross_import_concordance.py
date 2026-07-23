"""Pairwise exact-import temporal concordance application tests."""

# pyright: reportPrivateUsage=false
# pyright: reportMissingParameterType=false
# pyright: reportUnknownParameterType=false
# pyright: reportUnknownArgumentType=false, reportUnknownLambdaType=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

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
    HistoricalPrefixConfirmationOverlapRelation,
    HistoricalPrefixCrossImportPairStatus,
    HistoricalPrefixFeatureRelationTriple,
    HistoricalPrefixRateRelation,
    HistoricalPrefixSuccessCriterion,
    HistoricalPrefixSuccessStrategyNotFoundError,
    HistoricalPrefixSuccessWindowsContractError,
    HistoricalPrefixSuccessWindowSource,
    HistoricalPrefixTemporalHoldoutStatus,
)
from lottolab.application.use_cases.evaluate_historical_prefix_success_windows import (
    EvaluateHistoricalPrefixSuccessWindows,
)

LEFT_IMPORT = "a" * 64
RIGHT_IMPORT = "b" * 64


class _Reader:
    def __init__(self, sources: dict[str, HistoricalPrefixSuccessWindowSource | None]) -> None:
        self.sources = sources
        self.calls: list[str] = []

    def load_source(
        self, import_identity_sha256: str
    ) -> HistoricalPrefixSuccessWindowSource | None:
        self.calls.append(import_identity_sha256)
        return self.sources.get(import_identity_sha256)


class _Factory:
    def __init__(self, sources: dict[str, HistoricalPrefixSuccessWindowSource | None]) -> None:
        self.reader = _Reader(sources)
        self.calls = 0

    def __call__(self) -> _Reader:
        self.calls += 1
        return self.reader


def _source(
    import_identity: str,
    count: int,
    *,
    draw_number_offset: int = 1,
    dataset_sha256: str = "e" * 64,
    source_artifact_sha256: str = "d" * 64,
    include_strategy: bool = True,
) -> HistoricalPrefixSuccessWindowSource:
    strategies = (
        (
            build_success_strategy(
                observations=build_success_observations(
                    count,
                    draw_number_offset=draw_number_offset,
                )
            ),
        )
        if include_strategy
        else ()
    )
    source = build_success_source(
        strategies,
        import_identity_sha256=import_identity,
    )
    return dataclasses.replace(
        source,
        metadata=dataclasses.replace(
            source.metadata,
            run_id=f"run-{import_identity[0]}",
            dataset_sha256=dataset_sha256,
            source_artifact_sha256=source_artifact_sha256,
        ),
    )


def _constant_feature_key(**_kwargs) -> HistoricalPrefixFeatureRelationTriple:
    return HistoricalPrefixFeatureRelationTriple(
        long_to_medium=HistoricalPrefixRateRelation.HIGHER,
        medium_to_short=HistoricalPrefixRateRelation.EQUAL,
        long_to_short=HistoricalPrefixRateRelation.LOWER,
    )


def _evaluate(
    factory: _Factory,
) -> module.HistoricalPrefixCrossImportConcordanceResult:
    return EvaluateHistoricalPrefixSuccessWindows(factory).get_cross_import_concordance(
        left_import_identity_sha256=LEFT_IMPORT,
        right_import_identity_sha256=RIGHT_IMPORT,
        strategy_id="strategy-a",
        strategy_version="v1",
        replicate=1,
        prefix_count=1,
        criterion=HistoricalPrefixSuccessCriterion.M3_PLUS,
    )


def test_valid_request_uses_one_reader_two_ordered_loads_and_confirmation_only(
    monkeypatch,
) -> None:
    left = _source(LEFT_IMPORT, 1100)
    right = _source(RIGHT_IMPORT, 1100)
    factory = _Factory({LEFT_IMPORT: left, RIGHT_IMPORT: right})
    assignment_imports: list[str] = []
    original_assignments = module._build_walk_forward_assignments

    def assignment_spy(**kwargs):
        assignment_imports.append(kwargs["source"].metadata.import_identity_sha256)
        return original_assignments(**kwargs)

    monkeypatch.setattr(module, "_snapshot_feature_key", _constant_feature_key)
    monkeypatch.setattr(
        module,
        "_current_target_succeeded",
        lambda **kwargs: kwargs["current_target"].target.draw_number % 3 == 0,
    )
    monkeypatch.setattr(module, "_build_walk_forward_assignments", assignment_spy)

    result = _evaluate(factory)

    assert factory.calls == 1
    assert factory.reader.calls == [LEFT_IMPORT, RIGHT_IMPORT]
    assert assignment_imports == [LEFT_IMPORT, RIGHT_IMPORT]
    assert result.metadata.left == left.metadata
    assert result.metadata.right == right.metadata
    assert result.metadata.same_dataset_sha256 is True
    assert result.metadata.same_source_artifact_sha256 is True
    assert result.pair_status is HistoricalPrefixCrossImportPairStatus.COMPLETE
    assert result.left_holdout_status is HistoricalPrefixTemporalHoldoutStatus.COMPLETE
    assert result.right_holdout_status is HistoricalPrefixTemporalHoldoutStatus.COMPLETE
    assert result.confirmation_target_overlap is not None
    assert result.confirmation_target_overlap.relation is (
        HistoricalPrefixConfirmationOverlapRelation.IDENTICAL
    )
    assert result.confirmation_target_overlap.overlap_count == 300
    assert len(result.comparisons) == 64
    assert [comparison.cohort_index for comparison in result.comparisons] == list(range(64))
    assert all(
        comparison.left_confirmation_diagnostic.cohort_index == comparison.cohort_index
        and comparison.right_confirmation_diagnostic.cohort_index == comparison.cohort_index
        for comparison in result.comparisons
    )


@pytest.mark.parametrize(
    ("left_count", "right_count", "expected"),
    [
        (1049, 1100, HistoricalPrefixCrossImportPairStatus.LEFT_NOT_READY),
        (1100, 1049, HistoricalPrefixCrossImportPairStatus.RIGHT_NOT_READY),
        (1049, 1049, HistoricalPrefixCrossImportPairStatus.BOTH_NOT_READY),
    ],
)
def test_not_ready_pair_status_never_emits_partial_family(
    monkeypatch,
    left_count: int,
    right_count: int,
    expected: HistoricalPrefixCrossImportPairStatus,
) -> None:
    factory = _Factory(
        {
            LEFT_IMPORT: _source(LEFT_IMPORT, left_count),
            RIGHT_IMPORT: _source(RIGHT_IMPORT, right_count),
        }
    )
    monkeypatch.setattr(module, "_snapshot_feature_key", _constant_feature_key)
    monkeypatch.setattr(module, "_current_target_succeeded", lambda **_kwargs: False)

    result = _evaluate(factory)

    assert result.pair_status is expected
    assert result.confirmation_target_overlap is None
    assert result.comparisons == ()


@pytest.mark.parametrize(
    ("right_offset", "expected_overlap", "expected_relation"),
    [
        (101, 200, HistoricalPrefixConfirmationOverlapRelation.PARTIAL_OVERLAP),
        (1001, 0, HistoricalPrefixConfirmationOverlapRelation.DISJOINT),
    ],
)
def test_confirmation_overlap_uses_exact_draw_sha_and_discloses_dataset_difference(
    monkeypatch,
    right_offset: int,
    expected_overlap: int,
    expected_relation: HistoricalPrefixConfirmationOverlapRelation,
) -> None:
    factory = _Factory(
        {
            LEFT_IMPORT: _source(LEFT_IMPORT, 1100),
            RIGHT_IMPORT: _source(
                RIGHT_IMPORT,
                1100,
                draw_number_offset=right_offset,
                dataset_sha256="f" * 64,
                source_artifact_sha256="1" * 64,
            ),
        }
    )
    monkeypatch.setattr(module, "_snapshot_feature_key", _constant_feature_key)
    monkeypatch.setattr(module, "_current_target_succeeded", lambda **_kwargs: False)

    result = _evaluate(factory)

    assert result.metadata.same_dataset_sha256 is False
    assert result.metadata.same_source_artifact_sha256 is False
    assert result.confirmation_target_overlap is not None
    assert result.confirmation_target_overlap.overlap_count == expected_overlap
    assert result.confirmation_target_overlap.left_only_count == 300 - expected_overlap
    assert result.confirmation_target_overlap.right_only_count == 300 - expected_overlap
    assert result.confirmation_target_overlap.relation is expected_relation


def test_identical_imports_are_rejected_before_factory() -> None:
    factory = _Factory({})
    with pytest.raises(HistoricalPrefixSuccessWindowsContractError):
        EvaluateHistoricalPrefixSuccessWindows(factory).get_cross_import_concordance(
            left_import_identity_sha256=LEFT_IMPORT,
            right_import_identity_sha256=LEFT_IMPORT,
            strategy_id="strategy-a",
            strategy_version="v1",
            replicate=1,
            prefix_count=1,
            criterion=HistoricalPrefixSuccessCriterion.M3_PLUS,
        )
    assert factory.calls == 0
    assert factory.reader.calls == []


@pytest.mark.parametrize("missing_side", ["left", "right"])
def test_missing_exact_strategy_is_sanitized_per_source(
    monkeypatch,
    missing_side: str,
) -> None:
    left = _source(LEFT_IMPORT, 1, include_strategy=missing_side != "left")
    right = _source(RIGHT_IMPORT, 1, include_strategy=missing_side != "right")
    factory = _Factory({LEFT_IMPORT: left, RIGHT_IMPORT: right})
    monkeypatch.setattr(module, "_snapshot_feature_key", _constant_feature_key)

    with pytest.raises(HistoricalPrefixSuccessStrategyNotFoundError):
        _evaluate(factory)

    assert factory.calls == 1
    assert factory.reader.calls == [LEFT_IMPORT, RIGHT_IMPORT]
