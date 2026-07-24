"""Closed-policy tests for Historical Success research qualification."""

from __future__ import annotations

import dataclasses

import pytest

from lottolab.application.historical_success_qualification import (
    RANDOM_BASELINE_CAVEAT,
    HistoricalSuccessQualificationCensusStatus,
    HistoricalSuccessQualificationCensusSummary,
    HistoricalSuccessQualificationContractError,
    HistoricalSuccessQualificationEvidenceStatus,
    HistoricalSuccessQualificationIdentity,
    HistoricalSuccessQualificationImportEvidence,
    HistoricalSuccessQualificationInformationalFlag,
    HistoricalSuccessQualificationOverlapRelation,
    HistoricalSuccessQualificationPairInput,
    HistoricalSuccessQualificationPairStatus,
    HistoricalSuccessQualificationPrimaryStatus,
    qualify_historical_success,
)

IMPORTS = tuple(character * 64 for character in "abcd")
DATASETS = tuple(character * 64 for character in "ef12")
ARTIFACTS = tuple(character * 64 for character in "3456")


def _identity() -> HistoricalSuccessQualificationIdentity:
    return HistoricalSuccessQualificationIdentity(
        strategy_id="strategy-a",
        strategy_version="v1",
        replicate=2,
        prefix_count=5,
        criterion="M3_PLUS",
    )


def _import(
    index: int,
    *,
    observation_count: int = 1050,
    window_status: HistoricalSuccessQualificationEvidenceStatus = (
        HistoricalSuccessQualificationEvidenceStatus.COMPLETE
    ),
    holdout_status: HistoricalSuccessQualificationEvidenceStatus = (
        HistoricalSuccessQualificationEvidenceStatus.COMPLETE
    ),
    recent_status: HistoricalSuccessQualificationEvidenceStatus = (
        HistoricalSuccessQualificationEvidenceStatus.COMPLETE
    ),
    recent_differences: int = 0,
    dataset_sha256: str | None = None,
    source_artifact_sha256: str | None = None,
) -> HistoricalSuccessQualificationImportEvidence:
    return HistoricalSuccessQualificationImportEvidence(
        import_index=index,
        import_identity_sha256=IMPORTS[index],
        dataset_sha256=dataset_sha256 or DATASETS[index],
        source_artifact_sha256=source_artifact_sha256 or ARTIFACTS[index],
        source_observation_count=observation_count,
        strategy_window_status=window_status,
        temporal_holdout_status=holdout_status,
        recent_audit_status=recent_status,
        recent_relationship_difference_count=recent_differences,
    )


def _pair(
    left: int,
    right: int,
    *,
    relation: HistoricalSuccessQualificationOverlapRelation = (
        HistoricalSuccessQualificationOverlapRelation.DISJOINT
    ),
) -> HistoricalSuccessQualificationPairInput:
    return HistoricalSuccessQualificationPairInput(
        left_import_index=left,
        right_import_index=right,
        pair_status=HistoricalSuccessQualificationPairStatus.COMPLETE,
        confirmation_overlap_relation=relation,
    )


def _qualify(
    *,
    imports: tuple[HistoricalSuccessQualificationImportEvidence, ...] | None = None,
    pairs: tuple[HistoricalSuccessQualificationPairInput, ...] | None = None,
    census_status: HistoricalSuccessQualificationCensusStatus = (
        HistoricalSuccessQualificationCensusStatus.COMPLETE
    ),
    summaries: tuple[HistoricalSuccessQualificationCensusSummary, ...] | None = None,
):
    selected = imports if imports is not None else (_import(0), _import(1))
    selected_pairs = (
        pairs
        if pairs is not None
        else tuple(
            _pair(left, right)
            for left in range(len(selected))
            for right in range(left + 1, len(selected))
        )
    )
    rows = (
        summaries
        if summaries is not None
        else (HistoricalSuccessQualificationCensusSummary.ALL_AVAILABLE_HIGHER,) * 64
    )
    return qualify_historical_success(
        identity=_identity(),
        imports=selected,
        pairs=selected_pairs,
        census_status=census_status,
        cohort_census_count=len(rows),
        cohort_summaries=rows,
    )


def test_candidate_preserves_exact_identity_order_flags_and_random_caveat() -> None:
    result = _qualify(imports=(_import(0), _import(1, recent_differences=3)))

    assert result.identity == _identity()
    assert tuple(item.import_identity_sha256 for item in result.imports) == IMPORTS[:2]
    assert result.primary_status is (
        HistoricalSuccessQualificationPrimaryStatus.RESEARCH_CANDIDATE
    )
    assert result.informational_flags == (
        HistoricalSuccessQualificationInformationalFlag.HISTORICAL_CONCORDANCE_OBSERVED,
        HistoricalSuccessQualificationInformationalFlag.RECENT_RELATIONSHIP_DIFFERENCE,
    )
    assert result.random_baseline_caveat == RANDOM_BASELINE_CAVEAT
    assert result.comparable_import_count == 2
    assert result.expected_pair_count == result.actual_pair_count == 1
    assert result.cohort_census_count == 64
    assert result.pairs[0].r1_comparable is True
    assert dataclasses.fields(result.identity) == (
        dataclasses.fields(HistoricalSuccessQualificationIdentity)
    )
    assert [field.name for field in dataclasses.fields(result.identity)] == [
        "strategy_id",
        "strategy_version",
        "replicate",
        "prefix_count",
        "criterion",
    ]


@pytest.mark.parametrize(
    "relation",
    [
        HistoricalSuccessQualificationOverlapRelation.PARTIAL_OVERLAP,
        HistoricalSuccessQualificationOverlapRelation.DISJOINT,
    ],
)
def test_non_identical_partial_or_disjoint_pairs_qualify(
    relation: HistoricalSuccessQualificationOverlapRelation,
) -> None:
    result = _qualify(pairs=(_pair(0, 1, relation=relation),))

    assert result.primary_status is (
        HistoricalSuccessQualificationPrimaryStatus.RESEARCH_CANDIDATE
    )
    assert result.pairs[0].r1_comparable is True


@pytest.mark.parametrize(
    ("imports", "pair"),
    [
        (
            (
                _import(0),
                _import(1, dataset_sha256=DATASETS[0]),
            ),
            _pair(0, 1),
        ),
        (
            (
                _import(0),
                _import(1, source_artifact_sha256=ARTIFACTS[0]),
            ),
            _pair(0, 1),
        ),
        (
            (_import(0), _import(1)),
            _pair(
                0,
                1,
                relation=HistoricalSuccessQualificationOverlapRelation.IDENTICAL,
            ),
        ),
    ],
)
def test_same_dataset_artifact_or_identical_targets_remain_descriptive_but_unresolved(
    imports: tuple[HistoricalSuccessQualificationImportEvidence, ...],
    pair: HistoricalSuccessQualificationPairInput,
) -> None:
    result = _qualify(imports=imports, pairs=(pair,))

    assert result.primary_status is (
        HistoricalSuccessQualificationPrimaryStatus.EVIDENCE_INCOMPLETE
    )
    assert result.informational_flags == (
        HistoricalSuccessQualificationInformationalFlag.CROSS_IMPORT_UNRESOLVED,
    )
    assert result.random_baseline_caveat is None
    assert result.pairs[0].r1_comparable is False


@pytest.mark.parametrize(
    "imports",
    [
        (_import(0, observation_count=0), _import(1)),
        (
            _import(
                0,
                window_status=HistoricalSuccessQualificationEvidenceStatus.NOT_READY,
            ),
            _import(1),
        ),
        (
            _import(
                0,
                holdout_status=HistoricalSuccessQualificationEvidenceStatus.NOT_READY,
                recent_status=HistoricalSuccessQualificationEvidenceStatus.NOT_READY,
            ),
            _import(1),
        ),
    ],
)
def test_zero_observations_incomplete_windows_or_holdout_are_not_ready(
    imports: tuple[HistoricalSuccessQualificationImportEvidence, ...],
) -> None:
    result = _qualify(imports=imports)

    assert result.primary_status is HistoricalSuccessQualificationPrimaryStatus.NOT_READY
    assert result.informational_flags == ()
    assert result.random_baseline_caveat is None


@pytest.mark.parametrize(
    ("census_status", "summaries"),
    [
        (
            HistoricalSuccessQualificationCensusStatus.PARTIAL_NOT_READY,
            (),
        ),
        (
            HistoricalSuccessQualificationCensusStatus.COMPLETE,
            (HistoricalSuccessQualificationCensusSummary.ALL_AVAILABLE_HIGHER,) * 63,
        ),
        (
            HistoricalSuccessQualificationCensusStatus.COMPLETE,
            (HistoricalSuccessQualificationCensusSummary.MIXED_AVAILABLE,) * 64,
        ),
        (
            HistoricalSuccessQualificationCensusStatus.COMPLETE,
            (HistoricalSuccessQualificationCensusSummary.PARTIAL_AVAILABILITY,) * 64,
        ),
    ],
)
def test_incomplete_census_missing_or_unavailable_rows_fail_closed(
    census_status: HistoricalSuccessQualificationCensusStatus,
    summaries: tuple[HistoricalSuccessQualificationCensusSummary, ...],
) -> None:
    result = _qualify(census_status=census_status, summaries=summaries)

    assert result.primary_status is (
        HistoricalSuccessQualificationPrimaryStatus.EVIDENCE_INCOMPLETE
    )
    assert (
        HistoricalSuccessQualificationInformationalFlag.CROSS_IMPORT_UNRESOLVED
        in result.informational_flags
    )


@pytest.mark.parametrize(
    "summary",
    [
        HistoricalSuccessQualificationCensusSummary.ALL_AVAILABLE_HIGHER,
        HistoricalSuccessQualificationCensusSummary.ALL_AVAILABLE_EQUAL,
        HistoricalSuccessQualificationCensusSummary.ALL_AVAILABLE_LOWER,
    ],
)
def test_all_available_directions_are_equally_eligible(
    summary: HistoricalSuccessQualificationCensusSummary,
) -> None:
    result = _qualify(summaries=(summary,) * 64)

    assert result.primary_status is (
        HistoricalSuccessQualificationPrimaryStatus.RESEARCH_CANDIDATE
    )


def test_pair_count_mismatch_is_evidence_incomplete() -> None:
    result = _qualify(
        imports=(_import(0), _import(1), _import(2)),
        pairs=(_pair(0, 1), _pair(0, 2)),
    )

    assert result.expected_pair_count == 3
    assert result.actual_pair_count == 2
    assert result.primary_status is (
        HistoricalSuccessQualificationPrimaryStatus.EVIDENCE_INCOMPLETE
    )


def test_recent_difference_is_informational_and_never_changes_primary() -> None:
    unresolved = _qualify(
        imports=(
            _import(0, recent_differences=1),
            _import(1, dataset_sha256=DATASETS[0]),
        )
    )

    assert unresolved.primary_status is (
        HistoricalSuccessQualificationPrimaryStatus.EVIDENCE_INCOMPLETE
    )
    assert unresolved.informational_flags == (
        HistoricalSuccessQualificationInformationalFlag.CROSS_IMPORT_UNRESOLVED,
        HistoricalSuccessQualificationInformationalFlag.RECENT_RELATIONSHIP_DIFFERENCE,
    )

    not_ready = _qualify(
        imports=(
            _import(0, observation_count=0, recent_differences=1),
            _import(1),
        )
    )
    assert not_ready.primary_status is HistoricalSuccessQualificationPrimaryStatus.NOT_READY
    assert not_ready.informational_flags == ()


def test_inconsistent_temporal_and_recent_readiness_is_a_contract_error() -> None:
    with pytest.raises(
        HistoricalSuccessQualificationContractError,
        match="readiness must agree",
    ):
        _import(
            0,
            holdout_status=HistoricalSuccessQualificationEvidenceStatus.COMPLETE,
            recent_status=HistoricalSuccessQualificationEvidenceStatus.NOT_READY,
        )


def test_contradictory_or_out_of_order_flags_are_rejected() -> None:
    candidate = _qualify()

    with pytest.raises(HistoricalSuccessQualificationContractError):
        dataclasses.replace(
            candidate,
            informational_flags=(
                HistoricalSuccessQualificationInformationalFlag.RECENT_RELATIONSHIP_DIFFERENCE,
                HistoricalSuccessQualificationInformationalFlag.HISTORICAL_CONCORDANCE_OBSERVED,
            ),
        )
    with pytest.raises(
        HistoricalSuccessQualificationContractError,
        match="cannot coexist",
    ):
        dataclasses.replace(
            candidate,
            informational_flags=(
                HistoricalSuccessQualificationInformationalFlag.CROSS_IMPORT_UNRESOLVED,
                HistoricalSuccessQualificationInformationalFlag.HISTORICAL_CONCORDANCE_OBSERVED,
            ),
        )


def test_candidate_caveat_is_required_and_forbidden_on_non_candidate() -> None:
    candidate = _qualify()
    incomplete = _qualify(
        imports=(
            _import(0),
            _import(1, dataset_sha256=DATASETS[0]),
        )
    )

    with pytest.raises(HistoricalSuccessQualificationContractError):
        dataclasses.replace(candidate, random_baseline_caveat=None)
    with pytest.raises(HistoricalSuccessQualificationContractError):
        dataclasses.replace(
            incomplete,
            random_baseline_caveat=RANDOM_BASELINE_CAVEAT,
        )


def test_same_inputs_are_immutable_and_deterministically_equal() -> None:
    left = _qualify()
    right = _qualify()

    assert left == right
    assert hash(left) == hash(right)
    with pytest.raises(dataclasses.FrozenInstanceError):
        left.primary_status = HistoricalSuccessQualificationPrimaryStatus.NOT_READY  # type: ignore[misc]
