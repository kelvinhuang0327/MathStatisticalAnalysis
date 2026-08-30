"""Focused acceptance for the sealed T539 prospective freeze contract."""

from __future__ import annotations

import copy
import json
from typing import Any, cast

import pytest
import tools.freeze_t539_callable_family_dedup_prospective_shadow as freeze

EXPECTED_BOUNDARY = "115000186"
EXPECTED_TICKET_COUNTS = [1, 2, 3, 4, 5, 7, 10, 11, 12, 25]
EXPECTED_ORIGINAL_COUNT = 62
EXPECTED_CALLABLE_COUNT = 26
EXPECTED_REMOVED_COUNT = 36


@pytest.fixture(scope="module")
def pilot() -> dict[str, Any]:
    return freeze.load_sealed_pilot()


@pytest.fixture(scope="module")
def manifest(pilot: dict[str, Any]) -> dict[str, Any]:
    return freeze.build_manifest(pilot)


def _cells(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], manifest["cells"])


def _source_t539_cell(pilot: dict[str, Any], cell_id: str) -> dict[str, Any]:
    return next(
        cell
        for cell in cast(list[dict[str, Any]], pilot["cells"])
        if cell["cell_id"] == cell_id
    )


def test_exact_pilot_source_identity_and_hash(
    pilot: dict[str, Any], manifest: dict[str, Any]
) -> None:
    source = cast(dict[str, Any], manifest["source_pilot"])

    assert pilot["schema_version"] == freeze.PILOT_SCHEMA_VERSION
    assert source["commit"] == freeze.PILOT_COMMIT
    assert source["tree"] == freeze.PILOT_TREE
    assert source["result_path"] == freeze.PILOT_RESULT_PATH
    assert source["result_sha256"] == freeze.PILOT_RESULT_SHA256
    assert source["result_size_bytes"] == freeze.PILOT_RESULT_SIZE_BYTES
    assert source["supporting_research_locator_policy"] == "SOLE_EMBEDDED_AUTHORITY_MANIFEST"


def test_freeze_boundary_is_derived_from_the_sealed_pilot(
    pilot: dict[str, Any], manifest: dict[str, Any]
) -> None:
    boundary, contributors, reference_count = freeze.derive_freeze_boundary(pilot)
    frozen = cast(dict[str, Any], manifest["freeze_boundary"])

    assert boundary == EXPECTED_BOUNDARY
    assert frozen["target_identity"] == boundary
    assert frozen["contributors"] == contributors
    assert frozen["last_target_reference_count"] == reference_count
    assert frozen["source_field"] == "cells[].experiments[].last_target"


def test_all_and_only_complete_t539_cells_are_included(
    pilot: dict[str, Any], manifest: dict[str, Any]
) -> None:
    source_complete: list[int] = []
    for source_cell in cast(list[dict[str, Any]], pilot["cells"]):
        if source_cell["lottery_id"] != "T539":
            continue
        experiments = cast(list[dict[str, Any]], source_cell["experiments"])
        if {item["window_label"] for item in experiments} != {"W50", "W300", "W750"}:
            continue
        if all(
            item["exclusions"]["original_status"] == "COMPLETE"
            and item["exclusions"]["dedup_status"] == "COMPLETE"
            for item in experiments
        ):
            source_complete.append(cast(int, source_cell["k"]))

    assert source_complete == EXPECTED_TICKET_COUNTS
    assert [cell["native_ticket_count"] for cell in _cells(manifest)] == source_complete
    assert manifest["surface"]["included_cell_count"] == len(EXPECTED_TICKET_COUNTS)
    assert manifest["original_candidate_universe"]["candidate_count_sum_across_cells"] == 62
    assert manifest["callable_reduced_universe"]["representative_count_sum_across_cells"] == 26
    assert manifest["representative_selection"]["removed_sibling_count"] == 36


def test_historically_losing_and_zero_cells_are_not_filtered(
    pilot: dict[str, Any], manifest: dict[str, Any]
) -> None:
    losing = _source_t539_cell(pilot, "T539:K7")
    zero = _source_t539_cell(pilot, "T539:K4")
    included = {cell["cell_id"] for cell in _cells(manifest)}

    assert {item["dedup_vs_original_sign"] for item in losing["experiments"]} == {"NEGATIVE"}
    assert {item["dedup_vs_original_sign"] for item in zero["experiments"]} == {"ZERO"}
    assert {"T539:K7", "T539:K4"} <= included
    serialized = freeze.canonical_json_bytes(manifest)
    assert b"dedup_vs_original_sign" not in serialized
    assert b"dedup_rolling_metric" not in serialized


def test_every_cell_preserves_w50_w300_w750(manifest: dict[str, Any]) -> None:
    expected = [("W50", 50), ("W300", 300), ("W750", 750)]

    assert [
        (item["label"], item["size"]) for item in manifest["surface"]["windows"]
    ] == expected
    for cell in _cells(manifest):
        assert [(item["label"], item["size"]) for item in cell["windows"]] == expected
    assert manifest["selector_contract"]["no_preferred_historical_window"] is True
    assert manifest["selector_contract"]["weighted_windows"] == "FORBIDDEN"


def test_lexicographic_callable_representative_rule_is_exact(manifest: dict[str, Any]) -> None:
    assert manifest["representative_selection"] == {
        "chosen_representative_count": EXPECTED_CALLABLE_COUNT,
        "historical_outcomes_used": False,
        "identity_order": list(freeze.REPRESENTATIVE_IDENTITY_FIELDS),
        "removed_sibling_count": EXPECTED_REMOVED_COUNT,
        "representative_sweep": "NOT_RUN",
        "rule": freeze.REPRESENTATIVE_RULE,
    }
    for cell in _cells(manifest):
        for family in cast(list[dict[str, Any]], cell["callable_families"]):
            members = cast(list[list[str]], family["member_identities"])
            representative = cast(list[str], family["representative_identity"])
            assert representative == min(members, key=tuple)
            assert family["removed_sibling_identities"] == [
                member for member in members if member != representative
            ]


def test_representatives_do_not_depend_on_historical_performance(
    pilot: dict[str, Any], manifest: dict[str, Any]
) -> None:
    counterfactual = copy.deepcopy(pilot)
    for cell in cast(list[dict[str, Any]], counterfactual["cells"]):
        for experiment in cast(list[dict[str, Any]], cell["experiments"]):
            experiment["dedup_vs_original_sign"] = "COUNTERFACTUAL_NOT_USED"
            experiment["dedup_rolling_metric"] = {"counterfactual": True}
            experiment["original_rolling_metric"] = {"counterfactual": True}

    counterfactual_manifest = freeze.build_manifest(counterfactual)
    assert counterfactual_manifest["cells"] == manifest["cells"]
    assert counterfactual_manifest["representative_selection"] == manifest[
        "representative_selection"
    ]


def test_comparator_definitions_are_exact_and_dedup_universes_are_identical(
    manifest: dict[str, Any]
) -> None:
    comparators = cast(list[dict[str, Any]], manifest["comparators"])

    assert [item["id"] for item in comparators] == list(freeze.COMPARATOR_IDS)
    assert comparators[0]["universe_reference"] == "cells[].original_candidate_universe"
    assert comparators[1]["universe_reference"] == comparators[2]["universe_reference"]
    assert comparators[1]["universe_sha256_field"] == comparators[2][
        "universe_sha256_field"
    ]
    for cell in _cells(manifest):
        representative_identities = {
            tuple(family["representative_identity"])
            for family in cast(list[dict[str, Any]], cell["callable_families"])
        }
        assert all(
            tuple(window["callable_family_dedup_frozen_baseline_identity"])
            in representative_identities
            for window in cast(list[dict[str, Any]], cell["windows"])
        )


def test_future_target_must_be_strictly_after_boundary(manifest: dict[str, Any]) -> None:
    boundary = cast(str, manifest["freeze_boundary"]["target_identity"])

    assert freeze.is_future_target_admissible("115000187", boundary) is True
    assert freeze.is_future_target_admissible(boundary, boundary) is False
    assert freeze.is_future_target_admissible("115000185", boundary) is False
    with pytest.raises(freeze.FreezeContractError, match="ASCII decimal digits"):
        freeze.is_future_target_admissible("115000187-next", boundary)
    assert manifest["future_target_admissibility"]["eligible_rule"] == (
        "target_identity > FREEZE_BOUNDARY"
    )
    assert manifest["selector_contract"]["current_target_excluded_from_history"] is True
    assert manifest["selector_contract"]["causal_history_rule"] == (
        "EVERY_SELECTOR_INPUT_TARGET_IS_STRICTLY_BEFORE_TARGET"
    )


def test_artifact_contains_no_post_freeze_outcome_or_observation(manifest: dict[str, Any]) -> None:
    integrity = cast(dict[str, Any], manifest["freeze_integrity"])
    serialized = freeze.canonical_json_bytes(manifest)

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


def test_rule_fingerprint_is_deterministic_and_counterfactual_sensitive(
    pilot: dict[str, Any], manifest: dict[str, Any]
) -> None:
    rebuilt = freeze.build_manifest(pilot)
    observed = cast(dict[str, Any], manifest["immutable_rule_fingerprint"])["sha256"]

    assert rebuilt == manifest
    assert observed == freeze.compute_rule_fingerprint(manifest)
    mutated = copy.deepcopy(manifest)
    mutated["selector_contract"]["weighted_windows"] = "COUNTERFACTUAL"
    assert freeze.compute_rule_fingerprint(mutated) != observed


def test_output_order_and_committed_artifacts_are_byte_deterministic(
    pilot: dict[str, Any], manifest: dict[str, Any]
) -> None:
    rebuilt_manifest, json_bytes, markdown_bytes = freeze.build_artifact_bytes()
    json_path = freeze.REPOSITORY_ROOT / freeze.JSON_OUTPUT_PATH
    markdown_path = freeze.REPOSITORY_ROOT / freeze.MARKDOWN_OUTPUT_PATH

    assert rebuilt_manifest == manifest
    assert [cell["native_ticket_count"] for cell in _cells(manifest)] == sorted(
        EXPECTED_TICKET_COUNTS
    )
    for cell in _cells(manifest):
        families = cast(list[dict[str, Any]], cell["callable_families"])
        observed_order = [
            tuple(item["authority_qualified_callable_identity"]) for item in families
        ]
        assert observed_order == sorted(observed_order)
    assert json.loads(json_bytes) == manifest
    assert json_path.read_bytes() == json_bytes
    assert markdown_path.read_bytes() == markdown_bytes
    assert freeze.build_manifest(pilot) == manifest


def test_expected_counts_are_internally_reconciled(manifest: dict[str, Any]) -> None:
    cells = _cells(manifest)

    assert sum(cast(int, cell["original_candidate_count"]) for cell in cells) == (
        EXPECTED_ORIGINAL_COUNT
    )
    assert sum(cast(int, cell["deduplicated_callable_count"]) for cell in cells) == (
        EXPECTED_CALLABLE_COUNT
    )
    assert sum(cast(int, cell["removed_sibling_count"]) for cell in cells) == (
        EXPECTED_REMOVED_COUNT
    )
    assert EXPECTED_ORIGINAL_COUNT - EXPECTED_REMOVED_COUNT == EXPECTED_CALLABLE_COUNT
    assert cast(str, manifest["source_pilot"]["result_path"]).endswith(".json")
