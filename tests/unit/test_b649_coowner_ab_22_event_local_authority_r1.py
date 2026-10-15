"""Focused replay and fail-closed checks for the 22-event co-owner overlay."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import replace
from typing import Any, cast

import pytest

from lottolab.research import b649_coowner_ab_22_event_local_authority_r1 as integration


@pytest.fixture(scope="module")
def replay() -> Iterator[
    tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]
]:
    result, _frozen, base_rows, after_rows = integration.build_candidate()
    yield result, base_rows, after_rows


def test_only_two_new_full_profile_events_are_added(
    replay: tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]],
) -> None:
    result, base_rows, after_rows = replay
    assert result["PREVIOUS_EVENTS"] == 20
    assert result["NEW_EVENTS"] == 2
    assert result["TOTAL_EVENTS"] == 22
    assert result["ROWS_BEFORE"] == result["ROWS_AFTER"] == 4_647
    assert result["DISTINCT_CHANGED_PROFILES"] == 21
    assert result["UNCHANGED_ROWS_FROM_FROZEN"] == 4_626
    assert result["CHANGED_ROWS_FROM_BASE"] == 2
    assert result["UNCHANGED_ROWS_FROM_BASE"] == 4_645
    assert set(base_rows) == set(after_rows)


def test_donor_rows_bind_to_real_commit_result_and_proof_locators(
    replay: tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]],
) -> None:
    result, _base_rows, after_rows = replay
    identities = cast(Mapping[str, Mapping[str, Any]], result["DONOR_IDENTITIES"])
    for spec in integration.DONORS:
        donor = identities[spec.event_id]
        assert donor["HEAD"] == spec.head
        assert donor["TREE"] == spec.tree
        assert donor["RESULT_SHA256"] == spec.result_sha256
        assert donor["PROOF_SCOPE"] == "FULL_PROFILE"
        assert donor["PROOF_LOCATOR"].startswith(f"git:{spec.head}@{spec.tree}:")
        assert donor["PROOF_LOCATOR"].endswith(f"#PROOF:sha256={donor['PROOF_SHA256']}")
        assert after_rows[spec.profile_id].source == donor["PROOF_LOCATOR"]
    assert result["ALL_NEW_PROOF_LOCATORS_RESOLVE"] == "YES"
    assert result["SOURCE_METADATA_BINDINGS"] == "VERIFIED"


def test_original_judge_identity_and_caveats_are_preserved(
    replay: tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]],
) -> None:
    result, _base_rows, _after_rows = replay
    identities = cast(Mapping[str, Mapping[str, Any]], result["DONOR_IDENTITIES"])
    caveats = cast(Mapping[str, Mapping[str, Any]], result["INHERITED_CAVEATS_PRESERVED"])
    for spec in integration.DONORS:
        donor = identities[spec.event_id]
        judge = donor["FRESH_CONTEXT_JUDGE"]
        assert judge["TASK_ID"] == spec.judge_task_id
        assert judge["SESSION_ID"] == spec.judge_session_id
        assert judge["JUDGE_MODE"] == "FRESH_CONTEXT"
        assert judge["VERDICT"] == "VERIFIED_WITH_CAVEATS"
        assert judge["PROFILE_ID"] == spec.profile_id
        assert judge["DONOR_RESULT_SHA256"] == spec.result_sha256
        assert donor["WORKER_JUDGE_MODE"] == "SELF_CHECK_ONLY"
        assert caveats[spec.event_id]["CAVEAT"] == spec.caveat
        assert caveats[spec.event_id]["JUDGE_REPORT_SHA256"] == spec.judge_report_sha256


def test_family_cursor_and_global_claims_do_not_change(
    replay: tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]],
) -> None:
    result, _base_rows, _after_rows = replay
    assert result["FAMILY_BOUND_BEFORE"] == result["FAMILY_BOUND_AFTER"] == 313_394_584
    assert result["FAMILY_GAIN"] == 0
    assert result["MAX_OWNER"] == "66544333333333332222"
    assert result["MAX_OWNER_TYPE"] == "UNRESOLVED_CURSOR"
    assert result["CURSOR_BOUND"] == 313_394_584
    assert result["CURSOR_COUNT"] == 197
    assert result["NEXT_DISTINCT_BOUND"] == 313_392_308
    assert result["NEXT_COMPETING_OWNERS"] == ["66665555555421000000"]
    assert result["RESOLVED_PROFILES_ABOVE_INCUMBENT"] == 1_364
    assert result["NEW_WINNING_OUTCOMES"] == 0
    assert result["GLOBAL_K20_OPTIMUM"] == "UNKNOWN"
    assert result["FORMAL_AUTHORITY_ACCEPTANCE"] == "NOT_CLAIMED"


@pytest.mark.parametrize(
    "case",
    [
        "WRONG_DONOR_SHA_REJECTED",
        "WRONG_PROFILE_REJECTED",
        "WRONG_CAP_REJECTED",
        "WRONG_BOUND_REJECTED",
        "MISSING_PROOF_REJECTED",
        "DUPLICATE_EVENT_REJECTED",
        "UNRELATED_ROW_CHANGE_REJECTED",
        "CURSOR_OMISSION_REJECTED",
    ],
)
def test_required_negative_mutations_are_rejected(
    replay: tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]], case: str
) -> None:
    result, _base_rows, _after_rows = replay
    negatives = cast(Mapping[str, str], result["NEGATIVE_VALIDATIONS"])
    assert negatives[case] == "PASS"


def test_result_json_is_exact_replay_output(
    replay: tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, base_rows, _after_rows = replay
    result_path = integration.ROOT / integration.RESULT_PATH
    assert result_path.read_bytes() == integration.serialize_result(result)

    with pytest.raises(ValueError, match="pinned 22-event commit or its direct successor"):
        integration.verify_source_identity(integration.ROOT, integration.BASE_HEAD)

    with monkeypatch.context() as patch:
        patch.setattr(integration, "BASE_HEAD", integration.FROZEN_HEAD)
        patch.setattr(integration, "BASE_TREE", integration.FROZEN_TREE)
        with pytest.raises(ValueError, match="pinned 20-event base"):
            integration.verify_source_identity(integration.ROOT, integration.TWENTY_TWO_HEAD)

    with monkeypatch.context() as patch:
        patch.setattr(integration, "TWENTY_TWO_HEAD", integration.FROZEN_HEAD)
        patch.setattr(integration, "TWENTY_TWO_TREE", integration.FROZEN_TREE)
        with pytest.raises(ValueError, match="pinned 20-event base"):
            integration.verify_source_identity(integration.ROOT, integration.FROZEN_HEAD)

    donor = integration.DONORS[0]
    wrong_source = replace(donor, source_sha256="0" * 64)
    with pytest.raises(ValueError, match="donor source SHA256 mismatch"):
        integration.verify_donor_artifact(
            integration.ROOT, base_rows[donor.profile_id], wrong_source
        )
