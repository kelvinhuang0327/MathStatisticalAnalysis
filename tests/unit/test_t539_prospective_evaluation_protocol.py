"""Focused acceptance for the T539 prospective evaluation protocol R1."""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from typing import Any, cast

import pytest
import tools.freeze_t539_prospective_evaluation_protocol as protocol


@pytest.fixture(scope="module")
def frozen_authority() -> dict[str, Any]:
    return protocol.load_frozen_authority()


@pytest.fixture(scope="module")
def manifest(frozen_authority: dict[str, Any]) -> dict[str, Any]:
    return protocol.build_protocol(frozen_authority)


@pytest.fixture
def valid_metadata() -> protocol.ProspectiveMetadata:
    return protocol.ProspectiveMetadata(
        target_identity="115000187",
        pretarget_snapshot_exists=True,
        pretarget_snapshot_sealed_before_outcome=True,
        pretarget_snapshot_valid=True,
        snapshot_rule_fingerprint=protocol.EXPECTED_RULE_FINGERPRINT,
        snapshot_target_identity="115000187",
        outcome_authority_available=True,
        outcome_target_identity="115000187",
        complete_experiment_ids=protocol.EXPECTED_EXPERIMENT_IDS,
    )


def _experiments(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    surface = cast(dict[str, Any], manifest["frozen_surface"])
    return cast(list[dict[str, Any]], surface["experiments"])


def test_exact_freeze_sha_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(protocol, "EXPECTED_FREEZE_SHA256", "0" * 64)

    with pytest.raises(protocol.ProtocolContractError, match="freeze SHA-256 mismatch"):
        protocol.load_frozen_authority()


def test_exact_rule_fingerprint_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(protocol, "EXPECTED_RULE_FINGERPRINT", "0" * 64)

    with pytest.raises(protocol.ProtocolContractError, match="rule fingerprint mismatch"):
        protocol.load_frozen_authority()


def test_primary_metric_identity_is_resolved_from_sealed_authority(
    frozen_authority: dict[str, Any], manifest: dict[str, Any]
) -> None:
    assert frozen_authority["selector_contract"]["primary_metric_id"] == (
        "OFFICIAL_ANY_PRIZE_TARGET_RATE"
    )
    assert manifest["measurement_contract"]["primary_metric_id"] == (
        "OFFICIAL_ANY_PRIZE_TARGET_RATE"
    )

    ambiguous = copy.deepcopy(frozen_authority)
    ambiguous["selector_contract"].pop("primary_metric_id")
    with pytest.raises(
        protocol.ProtocolContractError,
        match="PRIMARY_METRIC_AUTHORITY_UNRESOLVED",
    ):
        protocol.validate_frozen_authority(ambiguous)


def test_all_ten_k_cells_three_windows_and_thirty_experiments_are_preserved(
    manifest: dict[str, Any],
) -> None:
    surface = cast(dict[str, Any], manifest["frozen_surface"])
    experiments = _experiments(manifest)

    assert surface["native_ticket_counts"] == list(protocol.EXPECTED_TICKET_COUNTS)
    assert surface["windows"] == [
        {"label": label, "size": size} for label, size in protocol.EXPECTED_WINDOWS
    ]
    assert surface["experiment_count"] == 30
    assert len(experiments) == 30
    assert tuple(item["experiment_id"] for item in experiments) == (
        protocol.EXPECTED_EXPERIMENT_IDS
    )


def test_all_three_frozen_arms_are_preserved_without_rename(
    manifest: dict[str, Any],
) -> None:
    arms = cast(list[dict[str, Any]], manifest["arms"])

    assert [(item["arm_id"], item["frozen_arm_id"]) for item in arms] == list(
        protocol.ARM_BINDINGS
    )
    assert all(item["arm_ids"] == ["A", "B", "C"] for item in _experiments(manifest))


def test_historical_performance_cannot_filter_the_frozen_surface(
    manifest: dict[str, Any],
) -> None:
    assert manifest["selection_guards"]["historical_performance_filtering"] == "FORBIDDEN"
    assert {item["native_ticket_count"] for item in _experiments(manifest)} == set(
        protocol.EXPECTED_TICKET_COUNTS
    )


def test_target_identity_must_be_strictly_after_freeze_boundary() -> None:
    assert protocol.is_prospective_target("115000187") is True
    assert protocol.is_prospective_target("115000186") is False
    assert protocol.is_prospective_target("115000185") is False
    with pytest.raises(protocol.ProtocolContractError, match="ASCII decimal digits"):
        protocol.is_prospective_target("115000187-next")


def test_missed_pretarget_seal_is_never_backfilled(
    valid_metadata: protocol.ProspectiveMetadata,
) -> None:
    missed = replace(
        valid_metadata,
        pretarget_snapshot_sealed_before_outcome=False,
    )

    assert protocol.classify_prospective_metadata(missed) == "MISSED_PRETARGET_SEAL"
    assert protocol.classify_prospective_metadata(valid_metadata) == "VALID_PROSPECTIVE"


def test_performance_dependent_exclusion_is_rejected() -> None:
    with pytest.raises(
        protocol.ProtocolContractError,
        match="performance-dependent exclusion is forbidden",
    ):
        protocol.validate_technical_exclusion(
            "MISSED_PRETARGET_SEAL",
            depends_on_arm_performance=True,
        )
    with pytest.raises(protocol.ProtocolContractError, match="non-technical exclusion"):
        protocol.validate_technical_exclusion("ARM_B_LOST")


def test_every_inclusion_failure_uses_the_frozen_technical_vocabulary(
    valid_metadata: protocol.ProspectiveMetadata,
) -> None:
    cases = [
        (
            replace(valid_metadata, pretarget_snapshot_valid=False),
            "PRETARGET_SNAPSHOT_INVALID",
        ),
        (
            replace(valid_metadata, snapshot_rule_fingerprint="wrong"),
            "RULE_FINGERPRINT_MISMATCH",
        ),
        (
            replace(valid_metadata, snapshot_target_identity="115000188"),
            "TARGET_IDENTITY_MISMATCH",
        ),
        (
            replace(valid_metadata, outcome_authority_available=False),
            "OUTCOME_AUTHORITY_UNAVAILABLE",
        ),
        (
            replace(valid_metadata, complete_experiment_ids=protocol.EXPECTED_EXPERIMENT_IDS[:-1]),
            "INCOMPLETE_FROZEN_EXPERIMENT_SURFACE",
        ),
    ]

    for metadata, expected in cases:
        assert protocol.classify_prospective_metadata(metadata) == expected
        assert expected in protocol.TECHNICAL_EXCLUSIONS


def test_only_b_minus_a_and_b_minus_c_are_defined_without_composite(
    manifest: dict[str, Any],
) -> None:
    measurement = cast(dict[str, Any], manifest["measurement_contract"])
    comparisons = cast(list[dict[str, Any]], measurement["paired_comparisons"])
    guardrails = cast(dict[str, Any], manifest["inferential_guardrails"])

    assert [item["comparison_id"] for item in comparisons] == ["B_MINUS_A", "B_MINUS_C"]
    assert all(
        item["comparison_ids"] == ["B_MINUS_A", "B_MINUS_C"]
        for item in _experiments(manifest)
    )
    assert guardrails["composite_score"] == "NOT_DEFINED"
    assert guardrails["weighted_score"] == "NOT_DEFINED"
    assert manifest["selection_guards"]["cross_k_aggregation"] == "FORBIDDEN"
    assert manifest["selection_guards"]["cross_window_aggregation"] == "FORBIDDEN"


def test_accumulation_requires_exact_counts_deltas_order_and_exclusions(
    manifest: dict[str, Any],
) -> None:
    contract = cast(dict[str, Any], manifest["accumulation_contract"])
    fields = cast(list[str], contract["per_experiment_required_report_fields"])

    assert contract["raw_target_level_outcomes"] == "RETAIN"
    assert contract["chronological_target_order"] == "ASCENDING_NUMERIC_TARGET_IDENTITY"
    assert fields == [
        "valid_target_count",
        "arm_success_counts",
        "exact_arm_rate_numerators_and_denominator",
        "exact_paired_rate_deltas",
        "chronological_target_identities",
        "technical_exclusions",
    ]
    assert contract["technical_exclusions_reported_separately"] is True


def test_artifact_embeds_no_post_freeze_outcome(manifest: dict[str, Any]) -> None:
    integrity = cast(dict[str, Any], manifest["integrity"])
    serialized = protocol.canonical_json_bytes(manifest)

    assert integrity["future_outcome_access"] == "NO"
    assert integrity["prospective_observations"] == 0
    assert integrity["prospective_observation_records"] == []
    assert integrity["post_freeze_outcome_records"] == []
    for forbidden_payload_key in (
        b'"main_numbers"',
        b'"winning_numbers"',
        b'"special_number"',
        b'"outcome_hash"',
        b'"score_hash"',
    ):
        assert forbidden_payload_key not in serialized


def test_two_builds_and_committed_artifacts_are_byte_identical(
    manifest: dict[str, Any],
) -> None:
    first_manifest, first_json, first_markdown = protocol.build_artifact_bytes()
    second_manifest, second_json, second_markdown = protocol.build_artifact_bytes()

    assert first_manifest == second_manifest == manifest
    assert first_json == second_json
    assert first_markdown == second_markdown
    assert json.loads(first_json) == manifest
    assert (protocol.REPOSITORY_ROOT / protocol.JSON_OUTPUT_PATH).read_bytes() == first_json
    assert (protocol.REPOSITORY_ROOT / protocol.MARKDOWN_OUTPUT_PATH).read_bytes() == (
        first_markdown
    )
