"""Application-contract tests for qualification random-baseline evidence."""

from __future__ import annotations

import dataclasses

import pytest

from lottolab.application.historical_prefix_success_windows import (
    HistoricalPrefixSuccessCriterion,
)
from lottolab.application.historical_success_qualification import (
    HistoricalSuccessQualificationIdentity,
)
from lottolab.application.historical_success_qualification_random_baseline import (
    QUALIFICATION_RANDOM_WINDOW_ROLES,
    HistoricalSuccessQualificationRandomAvailabilityStatus,
    HistoricalSuccessQualificationRandomBaselineContractError,
    HistoricalSuccessQualificationRandomRole,
    aggregate_historical_success_qualification_random_baseline_evidence,
    render_multiple_testing_warning,
)
from lottolab.application.historical_success_random_baseline import (
    RANDOM_BASELINE_POLICY_VERSION,
    HistoricalSuccessRandomBaselineCellIdentity,
    HistoricalSuccessRandomBaselineObservationOperand,
    HistoricalSuccessRandomBaselineTicketOperand,
    evaluate_historical_success_random_baseline,
)
from lottolab.domain.strategy_success_evaluation import WindowKind

IMPORTS = ("a" * 64, "b" * 64)
IDENTITY = HistoricalSuccessQualificationIdentity(
    strategy_id="strategy-a",
    strategy_version="v1",
    replicate=1,
    prefix_count=1,
    criterion="M3_PLUS",
)


def _baseline(
    import_identity: str,
    window_kind: WindowKind,
    *,
    ready: bool,
):
    cell = HistoricalSuccessRandomBaselineCellIdentity(
        policy_version=RANDOM_BASELINE_POLICY_VERSION,
        import_identity_sha256=import_identity,
        dataset_sha256=("c" if import_identity == IMPORTS[0] else "d") * 64,
        source_artifact_sha256=("e" if import_identity == IMPORTS[0] else "f") * 64,
        strategy_id=IDENTITY.strategy_id,
        strategy_version=IDENTITY.strategy_version,
        replicate=IDENTITY.replicate,
        window_kind=window_kind,
        window_policy_version="STRATEGY_SUCCESS_WINDOWS_V1",
        prefix_count=IDENTITY.prefix_count,
        criterion=HistoricalPrefixSuccessCriterion(IDENTITY.criterion),
    )
    if not ready:
        return evaluate_historical_success_random_baseline(
            cell=cell,
            observations=(),
            window_complete=False,
            eligible_observation_count=0,
            excluded_observation_count=0,
            legacy_window_success_count=0,
        )
    return evaluate_historical_success_random_baseline(
        cell=cell,
        observations=(
            HistoricalSuccessRandomBaselineObservationOperand(
                target_main_numbers=(1, 2, 3, 4, 5, 6),
                target_special_number=7,
                tickets=(
                    HistoricalSuccessRandomBaselineTicketOperand(
                        main_numbers=(8, 9, 10, 11, 12, 13),
                        persisted_main_hit_count=0,
                        persisted_legacy_special_hit=False,
                    ),
                ),
            ),
        ),
        window_complete=True,
        eligible_observation_count=1,
        excluded_observation_count=0,
        legacy_window_success_count=0,
    )


def _aggregate(readiness: tuple[bool, ...]):
    baselines = tuple(
        _baseline(import_identity, window_kind, ready=readiness[index])
        for index, (import_identity, window_kind) in enumerate(
            (
                (import_identity, window_kind)
                for import_identity in IMPORTS
                for window_kind, _ in QUALIFICATION_RANDOM_WINDOW_ROLES
            )
        )
    )
    return aggregate_historical_success_qualification_random_baseline_evidence(
        qualification_identity=IDENTITY,
        ordered_import_identity_sha256s=IMPORTS,
        ordered_baselines=baselines,
    )


def test_complete_aggregate_pins_import_window_role_order_and_exact_warning() -> None:
    result = _aggregate((True,) * 8)

    assert result.availability_summary.availability_status is (
        HistoricalSuccessQualificationRandomAvailabilityStatus.COMPLETE
    )
    assert result.availability_summary.evaluated_cell_count == 8
    assert result.availability_summary.ready_cell_count == 8
    assert result.availability_summary.raw_upper_tail_probability_count == 8
    assert result.availability_summary.multiple_testing_warning == (
        "This response evaluated 8 import × window cells. Each READY "  # noqa: RUF001
        "upper_tail_probability is a raw, unadjusted exact descriptive value. No "
        "multiplicity adjustment, threshold, pooled probability, combined decision, "
        "or random-advantage inference is authorized."
    )
    assert [
        (
            cell.import_index,
            cell.window_index,
            cell.qualification_random_role,
            cell.baseline.cell.window_kind,
        )
        for cell in result.ordered_cells
    ] == [
        (
            import_index,
            window_index,
            role,
            window_kind,
        )
        for import_index in range(2)
        for window_index, (window_kind, role) in enumerate(QUALIFICATION_RANDOM_WINDOW_ROLES)
    ]
    assert tuple(role for _, role in QUALIFICATION_RANDOM_WINDOW_ROLES) == (
        HistoricalSuccessQualificationRandomRole.REFERENCE_ONLY,
        HistoricalSuccessQualificationRandomRole.PRIMARY_DESCRIPTIVE_COMPARISON,
        HistoricalSuccessQualificationRandomRole.CONFIRMATION_DESCRIPTIVE_COMPARISON,
        HistoricalSuccessQualificationRandomRole.AUDIT_ONLY_NON_BLOCKING,
    )


@pytest.mark.parametrize(
    ("readiness", "expected_status", "ready_count"),
    [
        (
            (True, False, False, False, False, False, False, False),
            HistoricalSuccessQualificationRandomAvailabilityStatus.PARTIAL,
            1,
        ),
        (
            (False,) * 8,
            HistoricalSuccessQualificationRandomAvailabilityStatus.ALL_NOT_READY,
            0,
        ),
    ],
)
def test_partial_and_all_not_ready_availability_are_closed(
    readiness: tuple[bool, ...],
    expected_status: HistoricalSuccessQualificationRandomAvailabilityStatus,
    ready_count: int,
) -> None:
    result = _aggregate(readiness)

    assert result.availability_summary.availability_status is expected_status
    assert result.availability_summary.ready_cell_count == ready_count
    assert result.availability_summary.raw_upper_tail_probability_count == ready_count
    for cell in result.ordered_cells:
        if cell.baseline.readiness.value == "NOT_READY":
            assert cell.baseline.observed_success_count is None
            assert cell.baseline.expected_successes is None
            assert cell.baseline.upper_tail_probability is None


def test_aggregate_rejects_order_identity_summary_and_warning_mutations() -> None:
    result = _aggregate((True,) * 8)

    with pytest.raises(HistoricalSuccessQualificationRandomBaselineContractError):
        dataclasses.replace(
            result,
            ordered_cells=tuple(reversed(result.ordered_cells)),
        )
    with pytest.raises(HistoricalSuccessQualificationRandomBaselineContractError):
        dataclasses.replace(
            result.availability_summary,
            multiple_testing_warning="adjusted result",
        )
    with pytest.raises(HistoricalSuccessQualificationRandomBaselineContractError):
        dataclasses.replace(
            result,
            ordered_import_identity_sha256s=(IMPORTS[1], IMPORTS[0]),
        )
    with pytest.raises(HistoricalSuccessQualificationRandomBaselineContractError):
        render_multiple_testing_warning(0)
