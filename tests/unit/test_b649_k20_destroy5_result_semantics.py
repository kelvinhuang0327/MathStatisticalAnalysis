from __future__ import annotations

import pytest

from lottolab.research.b649_k20_destroy5_result_semantics import (
    INITIAL_INCUMBENT_AUTHORITY,
    INITIAL_VERIFIED_INCUMBENT_COUNT,
    INITIAL_VERIFIED_INCUMBENT_SOURCE_COMMIT,
    IncumbentAuthority,
    IncumbentEvidence,
    classify_candidate,
    execution_authority_fields,
    resolve_launch_time_incumbent,
    terminal_scientific_result,
)


@pytest.mark.parametrize(
    ("count", "frozen_delta", "incumbent_delta", "local_gain", "global_gain"),
    [
        (313_239_661, 0, -24_227, "NO", "NO"),
        (313_239_662, 1, -24_226, "YES", "NO"),
        (313_263_888, 24_227, 0, "YES", "NO"),
        (313_263_889, 24_228, 1, "YES", "YES"),
    ],
)
def test_candidate_classification_at_both_thresholds(
    count: int,
    frozen_delta: int,
    incumbent_delta: int,
    local_gain: str,
    global_gain: str,
) -> None:
    assert classify_candidate(count, INITIAL_INCUMBENT_AUTHORITY) == {
        "DELTA_FROM_FROZEN_START": frozen_delta,
        "DELTA_FROM_CURRENT_VERIFIED_INCUMBENT": incumbent_delta,
        "LOCAL_GAIN_VS_FROZEN_START": local_gain,
        "GLOBAL_STRICT_GAIN": global_gain,
    }


@pytest.mark.parametrize("count", [True, -1, 1.5, "313263889"])
def test_invalid_candidate_counts_fail_closed(count: object) -> None:
    with pytest.raises(ValueError, match="candidate count must be a non-negative integer"):
        classify_candidate(count, INITIAL_INCUMBENT_AUTHORITY)


def test_execution_authority_keeps_incumbent_out_of_frozen_manifest() -> None:
    fields = execution_authority_fields(INITIAL_INCUMBENT_AUTHORITY)

    assert fields == {
        "LAUNCH_TIME_CURRENT_VERIFIED_INCUMBENT_COUNT": 313_263_888,
        "LAUNCH_TIME_CURRENT_VERIFIED_INCUMBENT_SHA256": (
            "eaed652900d101881b678a1515d2a366bff9de6723dbec2ec9c82fe0d0d7844c"
        ),
        "LAUNCH_TIME_CURRENT_VERIFIED_INCUMBENT_ARTIFACT_LOCATOR": (
            "git:032ce592c3efd0ac4b5b82a813d157224419c794:"
            "docs/research/matrix-native-results/"
            "b649-k20-12-8-winner-two-ticket-ascent-r1-result.json"
        ),
        "LAUNCH_TIME_CURRENT_VERIFIED_INCUMBENT_SOURCE_COMMIT": (
            "032ce592c3efd0ac4b5b82a813d157224419c794"
        ),
    }


def test_unverified_higher_incumbent_is_rejected() -> None:
    candidate = IncumbentEvidence(
        count=INITIAL_VERIFIED_INCUMBENT_COUNT + 1,
        sha256="0" * 64,
        artifact_locator=f"git:{'b' * 40}:result.json",
        source_commit="b" * 40,
        terminal=True,
        canonical_verified=False,
        directly_comparable=True,
        newer=True,
    )

    with pytest.raises(ValueError, match="CURRENT_INCUMBENT_UNRESOLVED"):
        resolve_launch_time_incumbent([candidate])


def test_verified_newer_comparable_terminal_can_replace_launch_authority() -> None:
    candidate = IncumbentEvidence(
        count=INITIAL_VERIFIED_INCUMBENT_COUNT + 1,
        sha256="a" * 64,
        artifact_locator=f"git:{'b' * 40}:docs/research/result.json",
        source_commit="b" * 40,
        terminal=True,
        canonical_verified=True,
        directly_comparable=True,
        newer=True,
    )

    selected = resolve_launch_time_incumbent([candidate])

    assert selected.count == INITIAL_VERIFIED_INCUMBENT_COUNT + 1
    assert selected.sha256 == "a" * 64
    assert selected.artifact_locator == f"git:{'b' * 40}:docs/research/result.json"
    assert selected.source_commit == "b" * 40


def test_candidate_artifact_source_must_match_source_commit() -> None:
    candidate = IncumbentEvidence(
        count=INITIAL_VERIFIED_INCUMBENT_COUNT + 1,
        sha256="a" * 64,
        artifact_locator=f"git:{'a' * 40}:docs/research/result.json",
        source_commit="b" * 40,
        terminal=True,
        canonical_verified=True,
        directly_comparable=True,
        newer=True,
    )

    with pytest.raises(ValueError, match="CURRENT_INCUMBENT_UNRESOLVED"):
        resolve_launch_time_incumbent([candidate])


@pytest.mark.parametrize(
    "authority",
    [
        None,
        IncumbentAuthority(
            count=INITIAL_VERIFIED_INCUMBENT_COUNT - 1,
            sha256="a" * 64,
            artifact_locator=(
                f"git:{INITIAL_VERIFIED_INCUMBENT_SOURCE_COMMIT}:docs/research/result.json"
            ),
            source_commit=INITIAL_VERIFIED_INCUMBENT_SOURCE_COMMIT,
        ),
        IncumbentAuthority(
            count=INITIAL_VERIFIED_INCUMBENT_COUNT + 1,
            sha256="a" * 64,
            artifact_locator=f"git:{'a' * 40}:docs/research/result.json",
            source_commit="b" * 40,
        ),
    ],
)
def test_invalid_or_wrong_launch_authority_fails_closed(
    authority: object,
) -> None:
    with pytest.raises(ValueError, match="CURRENT_INCUMBENT_UNRESOLVED"):
        classify_candidate(313_263_889, authority)


def test_unverified_claim_above_base_is_rejected_even_after_verified_gain() -> None:
    verified = IncumbentEvidence(
        count=INITIAL_VERIFIED_INCUMBENT_COUNT + 2,
        sha256="a" * 64,
        artifact_locator=f"git:{'c' * 40}:docs/research/newer.json",
        source_commit="c" * 40,
        terminal=True,
        canonical_verified=True,
        directly_comparable=True,
        newer=True,
    )
    unverified = IncumbentEvidence(
        count=INITIAL_VERIFIED_INCUMBENT_COUNT + 1,
        sha256="0" * 64,
        artifact_locator=f"git:{'b' * 40}:docs/research/unresolved.json",
        source_commit="b" * 40,
        terminal=True,
        canonical_verified=False,
        directly_comparable=True,
        newer=True,
    )

    with pytest.raises(ValueError, match="CURRENT_INCUMBENT_UNRESOLVED"):
        resolve_launch_time_incumbent([verified, unverified])


def test_local_gain_does_not_terminate_as_global_success() -> None:
    assert (
        terminal_scientific_result(
            best_canonically_verified_count=313_239_662,
            launch_time_incumbent=INITIAL_INCUMBENT_AUTHORITY,
            sets_completed=1,
            sample_count=2_048,
        )
        is None
    )


def test_campaign_without_global_gain_is_terminal_only_when_complete() -> None:
    assert terminal_scientific_result(
        best_canonically_verified_count=313_263_888,
        launch_time_incumbent=INITIAL_INCUMBENT_AUTHORITY,
        sets_completed=2_047,
        sample_count=2_048,
    ) is None
    assert terminal_scientific_result(
        best_canonically_verified_count=313_263_888,
        launch_time_incumbent=INITIAL_INCUMBENT_AUTHORITY,
        sets_completed=2_048,
        sample_count=2_048,
    ) == "NO_GLOBAL_IMPROVEMENT_IN_V7_DESTROY5_2048_CAMPAIGN"


def test_global_gain_can_terminate_before_all_sets_complete() -> None:
    assert terminal_scientific_result(
        best_canonically_verified_count=313_263_889,
        launch_time_incumbent=INITIAL_INCUMBENT_AUTHORITY,
        sets_completed=1,
        sample_count=2_048,
    ) == "IMPROVED_VS_CURRENT_VERIFIED_INCUMBENT"


@pytest.mark.parametrize(
    ("sets_completed", "sample_count"),
    [(0, 0), (2, 1), (-1, 1), (1, -1)],
)
def test_invalid_campaign_counts_fail_closed(
    sets_completed: int,
    sample_count: int,
) -> None:
    with pytest.raises(ValueError):
        terminal_scientific_result(
            best_canonically_verified_count=INITIAL_VERIFIED_INCUMBENT_COUNT,
            launch_time_incumbent=INITIAL_INCUMBENT_AUTHORITY,
            sets_completed=sets_completed,
            sample_count=sample_count,
        )
