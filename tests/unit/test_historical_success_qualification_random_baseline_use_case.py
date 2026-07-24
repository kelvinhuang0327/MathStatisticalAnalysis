"""Use-case load and ordering tests for qualification random evidence."""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping

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
from lottolab.application.historical_success_qualification_random_baseline import (
    HistoricalSuccessQualificationRandomAvailabilityStatus,
    HistoricalSuccessQualificationRandomRole,
)
from lottolab.application.historical_success_random_baseline import (
    HistoricalSuccessRandomBaselineReadiness,
)
from lottolab.application.use_cases.evaluate_historical_prefix_success_windows import (
    EvaluateHistoricalPrefixSuccessWindows,
)
from lottolab.domain.strategy_success_evaluation import WindowKind

IMPORTS = ("a" * 64, "b" * 64)


class _Reader:
    def __init__(self, sources: Mapping[str, HistoricalPrefixSuccessWindowSource]) -> None:
        self.sources = sources
        self.calls: list[str] = []

    def load_source(self, import_identity_sha256: str) -> HistoricalPrefixSuccessWindowSource:
        self.calls.append(import_identity_sha256)
        return self.sources[import_identity_sha256]


class _Factory:
    def __init__(self, sources: Mapping[str, HistoricalPrefixSuccessWindowSource]) -> None:
        self.reader = _Reader(sources)
        self.calls = 0

    def __call__(self) -> _Reader:
        self.calls += 1
        return self.reader


def _raw_ticket_numbers(main_hits: int) -> tuple[int, ...]:
    values = list(range(1, main_hits + 1))
    filler = 8
    while len(values) < 6:
        values.append(filler)
        filler += 1
    return tuple(sorted(values))


def _with_raw_operands(
    observations: tuple[HistoricalPrefixSuccessSourceObservation, ...],
) -> tuple[HistoricalPrefixSuccessSourceObservation, ...]:
    return tuple(
        dataclasses.replace(
            observation,
            target_main_numbers=(1, 2, 3, 4, 5, 6),
            target_special_number=7,
            tickets=tuple(
                dataclasses.replace(
                    ticket,
                    main_numbers=_raw_ticket_numbers(ticket.main_hit_count),
                )
                for ticket in observation.tickets
            ),
        )
        for observation in observations
    )


def _source(import_identity: str, index: int) -> HistoricalPrefixSuccessWindowSource:
    source = build_success_source(
        (build_success_strategy(observations=_with_raw_operands(build_success_observations(1))),),
        import_identity_sha256=import_identity,
    )
    return dataclasses.replace(
        source,
        metadata=dataclasses.replace(
            source.metadata,
            dataset_sha256=("c" if index == 0 else "d") * 64,
            source_artifact_sha256=("e" if index == 0 else "f") * 64,
        ),
    )


def _evaluate(
    evaluator: EvaluateHistoricalPrefixSuccessWindows,
    imports: tuple[str, ...] = IMPORTS,
):
    return evaluator.get_research_qualification_random_baseline_evidence(
        import_identity_sha256s=imports,
        strategy_id="strategy-a",
        strategy_version="v1",
        replicate=1,
        prefix_count=1,
        criterion=HistoricalPrefixSuccessCriterion.M3_PLUS,
    )


def test_aggregate_uses_one_factory_reader_i_loads_i_lookups_i_windows_and_four_i_baselines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = _Factory(
        {identity: _source(identity, index) for index, identity in enumerate(IMPORTS)}
    )
    counts = {"lookup": 0, "window": 0, "baseline": 0}
    original_lookup = module._find_exact_strategy  # pyright: ignore[reportPrivateUsage]
    original_window = module._evaluate_strategy  # pyright: ignore[reportPrivateUsage]
    original_baseline = module.evaluate_historical_success_random_baseline

    def lookup_spy(*args: object, **kwargs: object):
        counts["lookup"] += 1
        return original_lookup(*args, **kwargs)  # pyright: ignore[reportArgumentType]

    def window_spy(*args: object, **kwargs: object):
        counts["window"] += 1
        return original_window(*args, **kwargs)

    def baseline_spy(*args: object, **kwargs: object):
        counts["baseline"] += 1
        return original_baseline(*args, **kwargs)

    monkeypatch.setattr(module, "_find_exact_strategy", lookup_spy)
    monkeypatch.setattr(module, "_evaluate_strategy", window_spy)
    monkeypatch.setattr(
        module,
        "evaluate_historical_success_random_baseline",
        baseline_spy,
    )

    result = _evaluate(EvaluateHistoricalPrefixSuccessWindows(factory))

    assert factory.calls == 1
    assert factory.reader.calls == list(IMPORTS)
    assert counts == {"lookup": 2, "window": 2, "baseline": 8}
    assert result.ordered_import_identity_sha256s == IMPORTS
    assert [
        (
            cell.import_index,
            cell.window_index,
            cell.baseline.cell.window_kind,
            cell.qualification_random_role,
            cell.baseline.readiness,
        )
        for cell in result.ordered_cells
    ] == [
        (
            import_index,
            window_index,
            window_kind,
            role,
            (
                HistoricalSuccessRandomBaselineReadiness.READY
                if window_kind is WindowKind.FULL_HISTORY
                else HistoricalSuccessRandomBaselineReadiness.NOT_READY
            ),
        )
        for import_index in range(2)
        for window_index, (window_kind, role) in enumerate(
            (
                (
                    WindowKind.FULL_HISTORY,
                    HistoricalSuccessQualificationRandomRole.REFERENCE_ONLY,
                ),
                (
                    WindowKind.LONG,
                    HistoricalSuccessQualificationRandomRole.PRIMARY_DESCRIPTIVE_COMPARISON,
                ),
                (
                    WindowKind.MEDIUM,
                    HistoricalSuccessQualificationRandomRole.CONFIRMATION_DESCRIPTIVE_COMPARISON,
                ),
                (
                    WindowKind.SHORT,
                    HistoricalSuccessQualificationRandomRole.AUDIT_ONLY_NON_BLOCKING,
                ),
            )
        )
    ]
    assert result.availability_summary.availability_status is (
        HistoricalSuccessQualificationRandomAvailabilityStatus.PARTIAL
    )
    assert result.availability_summary.ready_cell_count == 2


@pytest.mark.parametrize(
    "imports",
    [
        (IMPORTS[0],),
        (IMPORTS[0], IMPORTS[0]),
        ("invalid", IMPORTS[1]),
        (*IMPORTS, "c" * 64, "d" * 64, "e" * 64),
    ],
)
def test_all_inputs_are_validated_before_factory_creation(
    imports: tuple[str, ...],
) -> None:
    factory = _Factory({})

    with pytest.raises(HistoricalPrefixSuccessWindowsContractError):
        _evaluate(EvaluateHistoricalPrefixSuccessWindows(factory), imports)

    assert factory.calls == 0
    assert factory.reader.calls == []
