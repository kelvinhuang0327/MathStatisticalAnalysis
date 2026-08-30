"""Focused tests for sealed selector lineage-diversity attribution."""

from __future__ import annotations

import copy
from typing import Any, cast

import pytest
from tools import analyze_selector_lineage_diversity_attribution as attribution


@pytest.fixture(scope="module")
def frozen_artifacts() -> dict[str, attribution.LoadedArtifact]:
    return attribution.load_all_frozen_artifacts()


@pytest.fixture(scope="module")
def frozen_payload(
    frozen_artifacts: dict[str, attribution.LoadedArtifact],
) -> dict[str, Any]:
    payload, _json_bytes, _report_bytes = attribution.run_analysis()
    assert frozen_artifacts["rolling_selector"].spec.sha256 == (
        attribution.SELECTOR_ARTIFACT.sha256
    )
    return payload


def _identity(
    strategy_id: str,
    *,
    binding_identity: str,
    callable_identity: str,
    combined_classification: str = "DISTINCT_BINDING",
) -> attribution.LineageIdentity:
    return attribution.LineageIdentity(
        strategy_id=strategy_id,
        source_authority="TEST",
        source_classification=combined_classification,
        binding_fingerprint_sha256=(strategy_id.encode().hex() + ("0" * 64))[:64],
        binding_identity=binding_identity,
        callable_identity=callable_identity,
        callable_family_label=callable_identity,
        game_identities=("B649",),
        combined_classification=combined_classification,
    )


def test_base_and_supplement_merge_to_complete_135_id_lineage(
    frozen_artifacts: dict[str, attribution.LoadedArtifact],
) -> None:
    identities, summary = attribution.merge_lineage_authorities(
        frozen_artifacts["base_lineage"].payload,
        frozen_artifacts["wave26_supplement"].payload,
    )

    assert len(identities) == 135
    assert summary["base_record_count"] == 135
    assert summary["base_resolved_record_count"] == 131
    assert summary["base_unresolved_replaced_count"] == 4
    assert summary["supplemental_record_count"] == 4
    assert summary["combined_record_count"] == 135
    assert summary["complete_135_id_coverage"] is True
    assert len(summary["records"]) == 135
    assert set(identities) == {
        cast(str, row["strategy_id"]) for row in cast(list[dict[str, Any]], summary["records"])
    }


def test_lineage_authority_conflict_fails_closed(
    frozen_artifacts: dict[str, attribution.LoadedArtifact],
) -> None:
    base = copy.deepcopy(frozen_artifacts["base_lineage"].payload)
    supplement = copy.deepcopy(frozen_artifacts["wave26_supplement"].payload)
    base_records = cast(list[dict[str, Any]], base["records"])
    resolved_id = next(
        cast(str, row["strategy_id"])
        for row in base_records
        if row["classification"] == "DISTINCT_BINDING"
    )
    supplement_records = cast(list[dict[str, Any]], supplement["records"])
    supplement_records[0]["strategy_id"] = resolved_id

    with pytest.raises(
        attribution.AttributionDataError,
        match="LINEAGE_AUTHORITY_CONFLICT",
    ):
        attribution.merge_lineage_authorities(
            base,
            supplement,
            enforce_sealed_shape=False,
        )


def test_same_binding_collapses_to_no_structural_switch() -> None:
    identities = {
        "a": _identity(
            "a",
            binding_identity="binding:same",
            callable_identity="callable:same",
            combined_classification="IDENTICAL_BINDING",
        ),
        "b": _identity(
            "b",
            binding_identity="binding:same",
            callable_identity="callable:same",
            combined_classification="IDENTICAL_BINDING",
        ),
    }

    result = attribution.attribute_selection_diversity(
        {"a": 2, "b": 3},
        switch_count=2,
        lottery_id="B649",
        identities=identities,
    )

    assert result["diversity_class"] == "NO_SWITCH"
    assert result["unique_strategy_id_count"] == 2
    assert result["unique_binding_fingerprint_count"] == 1
    assert result["unique_callable_identity_count"] == 1
    assert result["any_selected_pair_same_callable_different_binding"] is False


def test_same_callable_different_binding_is_parameter_sibling_only() -> None:
    identities = {
        "a": _identity(
            "a",
            binding_identity="binding:a",
            callable_identity="callable:shared",
            combined_classification="SAME_CALLABLE_DIFFERENT_BINDING",
        ),
        "b": _identity(
            "b",
            binding_identity="binding:b",
            callable_identity="callable:shared",
            combined_classification="SAME_CALLABLE_DIFFERENT_BINDING",
        ),
    }

    result = attribution.attribute_selection_diversity(
        {"a": 4, "b": 5},
        switch_count=1,
        lottery_id="B649",
        identities=identities,
    )

    assert result["diversity_class"] == "PARAMETER_SIBLING_DIVERSITY_ONLY"
    assert result["unique_binding_fingerprint_count"] == 2
    assert result["unique_callable_identity_count"] == 1
    assert result["any_selected_pair_same_callable_different_binding"] is True
    assert result["more_than_one_distinct_binding_identity_selected"] is False


def test_distinct_binding_uses_more_than_one_callable_identity() -> None:
    identities = {
        "a": _identity(
            "a",
            binding_identity="binding:a",
            callable_identity="callable:a",
        ),
        "b": _identity(
            "b",
            binding_identity="binding:b",
            callable_identity="callable:b",
        ),
    }

    result = attribution.attribute_selection_diversity(
        {"a": 7, "b": 2},
        switch_count=3,
        lottery_id="B649",
        identities=identities,
    )

    assert result["diversity_class"] == "DISTINCT_BINDING_DIVERSITY"
    assert result["unique_binding_fingerprint_count"] == 2
    assert result["unique_callable_identity_count"] == 2
    assert result["any_selected_pair_same_callable_different_binding"] is False
    assert result["more_than_one_distinct_binding_identity_selected"] is True


def test_no_switch_experiment_preserves_single_identity_frequency() -> None:
    identities = {
        "a": _identity(
            "a",
            binding_identity="binding:a",
            callable_identity="callable:a",
        )
    }

    result = attribution.attribute_selection_diversity(
        {"a": 12},
        switch_count=0,
        lottery_id="B649",
        identities=identities,
    )

    assert result["diversity_class"] == "NO_SWITCH"
    assert result["unique_strategy_id_count"] == 1
    assert result["unique_binding_fingerprint_count"] == 1
    assert result["unique_callable_identity_count"] == 1
    assert result["selection_frequency_by_binding_identity"] == [
        {
            "identity": "binding:a",
            "selection_count": 12,
            "strategy_ids": ["a"],
        }
    ]


def test_mixed_diversity_contains_siblings_and_distinct_callable() -> None:
    identities = {
        "a": _identity(
            "a",
            binding_identity="binding:a",
            callable_identity="callable:shared",
            combined_classification="SAME_CALLABLE_DIFFERENT_BINDING",
        ),
        "b": _identity(
            "b",
            binding_identity="binding:b",
            callable_identity="callable:shared",
            combined_classification="SAME_CALLABLE_DIFFERENT_BINDING",
        ),
        "c": _identity(
            "c",
            binding_identity="binding:c",
            callable_identity="callable:distinct",
        ),
    }

    result = attribution.attribute_selection_diversity(
        {"a": 2, "b": 2, "c": 2},
        switch_count=4,
        lottery_id="B649",
        identities=identities,
    )

    assert result["diversity_class"] == "MIXED_DIVERSITY"
    assert result["any_selected_pair_same_callable_different_binding"] is True
    assert result["more_than_one_distinct_binding_identity_selected"] is True
    assert result["unique_binding_fingerprint_count"] == 3
    assert result["unique_callable_identity_count"] == 2


def test_missing_selected_lineage_fails_closed_without_inventing_counts() -> None:
    identities = {
        "a": _identity(
            "a",
            binding_identity="binding:a",
            callable_identity="callable:a",
        )
    }

    result = attribution.attribute_selection_diversity(
        {"a": 2, "missing": 3},
        switch_count=1,
        lottery_id="B649",
        identities=identities,
    )

    assert result["diversity_class"] == "LINEAGE_SOURCE_INCONSISTENT"
    assert result["lineage_attribution_complete"] is False
    assert result["structurally_unresolved_selected_strategy_ids"] == ["missing"]
    assert result["unique_binding_fingerprint_count"] is None
    assert result["unique_callable_identity_count"] is None
    assert result["more_than_one_distinct_binding_identity_selected"] is None


def test_sealed_sign_and_deltas_are_preserved_unchanged(
    frozen_artifacts: dict[str, attribution.LoadedArtifact],
    frozen_payload: dict[str, Any],
) -> None:
    selector_cells = cast(
        list[dict[str, Any]], frozen_artifacts["rolling_selector"].payload["cells"]
    )
    selector_cell = next(cell for cell in selector_cells if cell["cell_id"] == "B649:K3")
    selector_experiments = cast(dict[str, dict[str, Any]], selector_cell["experiments"])
    source_experiment = selector_experiments["SHORT"]
    result_experiments = cast(list[dict[str, Any]], frozen_payload["experiments"])
    result_experiment = next(
        row for row in result_experiments if row["cell_id"] == "B649:K3" and row["window"] == 50
    )

    assert result_experiment["historical_sign"] == "POSITIVE"
    assert (
        result_experiment["original_absolute_paired_delta"]
        == source_experiment["absolute_paired_delta"]
    )
    assert (
        result_experiment["original_relative_paired_delta"]
        == source_experiment["relative_paired_delta"]
    )
    assert result_experiment["switch_count"] == source_experiment["rolling_strategy_switch_count"]
    assert (
        result_experiment["frozen_baseline_strategy_id"]
        == source_experiment["frozen_baseline_strategy"]
    )


def test_frozen_result_reports_observed_lineage_coverage_without_alias_inference(
    frozen_payload: dict[str, Any],
) -> None:
    quality = cast(dict[str, Any], frozen_payload["source_data_quality"])
    aggregates = cast(dict[str, Any], frozen_payload["aggregates"])

    assert quality["selected_strategy_id_count"] == 134
    assert quality["selected_strategy_ids_absent_from_combined_lineage_count"] == 109
    assert quality["lineage_attribution_complete_available_experiment_count"] == 2
    assert quality["lineage_source_inconsistent_available_experiment_count"] == 60
    assert aggregates["experiment_count"] == 66
    assert aggregates["available_experiment_count"] == 62


def test_wave26_supplement_resolves_four_and_three_are_selected(
    frozen_payload: dict[str, Any],
) -> None:
    answers = cast(list[dict[str, Any]], frozen_payload["required_answers"])
    wave_answer = cast(dict[str, Any], answers[5]["answer"])
    rows = cast(list[dict[str, Any]], wave_answer["strategies"])

    assert wave_answer["appears_in_selector_universe_count"] == 4
    assert wave_answer["appears_in_selection_count"] == 3
    assert len(rows) == 4
    assert {row["source_resolution_classification"] for row in rows} == {
        "RESOLVED_STATIC_IMPLEMENTATION"
    }
    assert {row["combined_classification"] for row in rows} == {"DISTINCT_BINDING"}


def test_output_is_deterministic_and_experiments_are_ordered() -> None:
    first_payload, first_json, first_report = attribution.run_analysis()
    second_payload, second_json, second_report = attribution.run_analysis()

    assert first_payload == second_payload
    assert first_json == second_json
    assert first_report == second_report
    experiments = cast(list[dict[str, Any]], first_payload["experiments"])
    observed_order = [
        (cast(str, row["lottery_id"]), cast(int, row["k"]), cast(int, row["window"]))
        for row in experiments
    ]
    assert observed_order == sorted(observed_order)
    assert first_json.endswith(b"\n")
