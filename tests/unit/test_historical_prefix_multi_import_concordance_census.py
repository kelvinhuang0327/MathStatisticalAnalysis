"""Multi-import confirmation-only concordance census application tests."""

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
    HistoricalPrefixFeatureRelationTriple,
    HistoricalPrefixMultiImportCensusStatus,
    HistoricalPrefixMultiImportCensusSummary,
    HistoricalPrefixRateRelation,
    HistoricalPrefixSuccessCriterion,
    HistoricalPrefixSuccessWindowsContractError,
    HistoricalPrefixSuccessWindowSource,
    HistoricalPrefixSuccessWindowsUnavailableError,
)
from lottolab.application.use_cases.evaluate_historical_prefix_success_windows import (
    EvaluateHistoricalPrefixSuccessWindows,
)

IMPORTS = tuple(character * 64 for character in "abcd")


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
    dataset_sha256: str = "e" * 64,
    source_artifact_sha256: str = "f" * 64,
) -> HistoricalPrefixSuccessWindowSource:
    source = build_success_source(
        (
            build_success_strategy(
                observations=build_success_observations(count),
            ),
        ),
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


def _install_fast_assignments(monkeypatch) -> None:
    monkeypatch.setattr(
        module,
        "_snapshot_feature_key",
        lambda **_kwargs: HistoricalPrefixFeatureRelationTriple(
            long_to_medium=HistoricalPrefixRateRelation.HIGHER,
            medium_to_short=HistoricalPrefixRateRelation.EQUAL,
            long_to_short=HistoricalPrefixRateRelation.LOWER,
        ),
    )
    monkeypatch.setattr(
        module,
        "_current_target_succeeded",
        lambda **kwargs: kwargs["current_target"].target.draw_number % 3 == 0,
    )


def _evaluate(
    factory: _Factory,
    identities: tuple[str, ...],
) -> module.HistoricalPrefixMultiImportConcordanceCensusResult:
    return EvaluateHistoricalPrefixSuccessWindows(
        factory
    ).get_multi_import_concordance_census(
        import_identity_sha256s=identities,
        strategy_id="strategy-a",
        strategy_version="v1",
        replicate=1,
        prefix_count=1,
        criterion=HistoricalPrefixSuccessCriterion.M3_PLUS,
    )


@pytest.mark.parametrize(("import_count", "pair_count"), [(2, 1), (3, 3), (4, 6)])
def test_two_to_four_imports_use_one_reader_and_preserve_canonical_orders(
    monkeypatch,
    import_count: int,
    pair_count: int,
) -> None:
    _install_fast_assignments(monkeypatch)
    identities = IMPORTS[:import_count]
    sources: dict[str, HistoricalPrefixSuccessWindowSource | None] = {
        identity: _source(
            identity,
            1050,
            dataset_sha256=("e" if index % 2 == 0 else "1") * 64,
            source_artifact_sha256=("f" if index < 2 else "2") * 64,
        )
        for index, identity in enumerate(identities)
    }
    factory = _Factory(sources)
    assignment_imports: list[str] = []
    holdout_imports: list[str] = []
    original_assignments = module._build_walk_forward_assignments
    original_holdout = module._temporal_holdout

    def assignment_spy(**kwargs):
        assignment_imports.append(kwargs["source"].metadata.import_identity_sha256)
        return original_assignments(**kwargs)

    def holdout_spy(**kwargs):
        holdout_imports.append(kwargs["source"].metadata.import_identity_sha256)
        assert kwargs["assignments"] is not None
        return original_holdout(**kwargs)

    monkeypatch.setattr(module, "_build_walk_forward_assignments", assignment_spy)
    monkeypatch.setattr(module, "_temporal_holdout", holdout_spy)

    result = _evaluate(factory, identities)

    assert factory.calls == 1
    assert factory.reader.calls == list(identities)
    assert assignment_imports == list(identities)
    assert holdout_imports == list(identities)
    assert tuple(item.metadata.import_identity_sha256 for item in result.imports) == identities
    assert result.census_status is HistoricalPrefixMultiImportCensusStatus.COMPLETE
    assert result.pair_count == pair_count
    assert len(result.pairs) == pair_count
    assert [
        (pair.left_import_index, pair.right_import_index) for pair in result.pairs
    ] == [
        (left, right)
        for left in range(import_count)
        for right in range(left + 1, import_count)
    ]
    assert all(pair.confirmation_target_overlap is not None for pair in result.pairs)
    assert result.cohort_census_count == len(result.cohort_census) == 64
    for cohort_index, row in enumerate(result.cohort_census):
        assert row.cohort_index == cohort_index
        assert len(row.confirmation_diagnostics) == import_count
        assert [
            (item.import_index, item.import_identity_sha256)
            for item in row.confirmation_diagnostics
        ] == list(enumerate(identities))
        assert (
            row.higher_count
            + row.equal_count
            + row.lower_count
            + row.unavailable_count
            == import_count
        )


@pytest.mark.parametrize(
    ("counts", "expected"),
    [
        ((1050, 1049, 1050), HistoricalPrefixMultiImportCensusStatus.PARTIAL_NOT_READY),
        ((1049, 1049, 1049), HistoricalPrefixMultiImportCensusStatus.ALL_NOT_READY),
    ],
)
def test_not_ready_census_never_emits_partial_rows(
    monkeypatch,
    counts: tuple[int, int, int],
    expected: HistoricalPrefixMultiImportCensusStatus,
) -> None:
    _install_fast_assignments(monkeypatch)
    factory = _Factory(
        {
            identity: _source(identity, count)
            for identity, count in zip(IMPORTS[:3], counts, strict=True)
        }
    )

    result = _evaluate(factory, IMPORTS[:3])

    assert result.census_status is expected
    assert result.pair_count == len(result.pairs) == 3
    assert result.cohort_census_count == 0
    assert result.cohort_census == ()


@pytest.mark.parametrize(
    ("counts", "expected"),
    [
        ((3, 3, 0, 0, 0), HistoricalPrefixMultiImportCensusSummary.ALL_AVAILABLE_HIGHER),
        ((3, 0, 3, 0, 0), HistoricalPrefixMultiImportCensusSummary.ALL_AVAILABLE_EQUAL),
        ((3, 0, 0, 3, 0), HistoricalPrefixMultiImportCensusSummary.ALL_AVAILABLE_LOWER),
        ((3, 1, 1, 1, 0), HistoricalPrefixMultiImportCensusSummary.MIXED_AVAILABLE),
        ((3, 1, 1, 0, 1), HistoricalPrefixMultiImportCensusSummary.PARTIAL_AVAILABILITY),
        ((3, 0, 0, 0, 3), HistoricalPrefixMultiImportCensusSummary.NO_AVAILABLE_EFFECT),
    ],
)
def test_neutral_summary_precedence(
    counts: tuple[int, int, int, int, int],
    expected: HistoricalPrefixMultiImportCensusSummary,
) -> None:
    assert (
        module._multi_import_census_summary(
            import_count=counts[0],
            higher_count=counts[1],
            equal_count=counts[2],
            lower_count=counts[3],
            unavailable_count=counts[4],
        )
        is expected
    )


def test_inconsistent_direction_counts_are_rejected() -> None:
    with pytest.raises(HistoricalPrefixSuccessWindowsUnavailableError):
        module._multi_import_census_summary(
            import_count=3,
            higher_count=1,
            equal_count=1,
            lower_count=0,
            unavailable_count=0,
        )


@pytest.mark.parametrize(
    "identities",
    [
        (IMPORTS[0],),
        (*IMPORTS, "e" * 64),
        (IMPORTS[0], IMPORTS[0]),
        ("BAD", IMPORTS[1]),
    ],
)
def test_all_import_validation_precedes_factory(identities: tuple[str, ...]) -> None:
    factory = _Factory({})
    with pytest.raises(HistoricalPrefixSuccessWindowsContractError):
        _evaluate(factory, identities)
    assert factory.calls == 0
    assert factory.reader.calls == []
