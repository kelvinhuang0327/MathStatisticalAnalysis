"""Focused adversarial tests for selector lineage-diversity attribution R2."""

from __future__ import annotations

import copy
import hashlib
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
from tools import analyze_selector_lineage_diversity_attribution as attribution

R1_ARTIFACT_HASHES = {
    "docs/research/matrix-native-results/selector-lineage-diversity-attribution-r1-result.json": (
        "cbfc8a52442eadeaa54b462020d9abb3f723644f8f84f4a0ba146c534cd3ad81"
    ),
    "docs/research/selector-lineage-diversity-attribution-r1.md": (
        "20e00eb7aa2513c5a9b04228a649fb3a57be56e2117b1b9fdd72e68117540002"
    ),
}


@pytest.fixture(scope="module")
def frozen_artifacts() -> dict[str, attribution.LoadedArtifact]:
    return attribution.load_all_frozen_artifacts()


@pytest.fixture(scope="module")
def analysis_result() -> tuple[dict[str, Any], bytes, bytes]:
    return attribution.run_analysis()


@pytest.fixture(scope="module")
def frozen_payload(
    analysis_result: tuple[dict[str, Any], bytes, bytes],
) -> dict[str, Any]:
    return analysis_result[0]


@pytest.fixture(scope="module")
def qualified_lineage(
    frozen_artifacts: dict[str, attribution.LoadedArtifact],
) -> tuple[
    dict[attribution.QualifiedIdentityKey, attribution.QualifiedLineageIdentity],
    dict[str, Any],
]:
    production, production_summary = attribution.merge_lineage_authorities(
        frozen_artifacts["base_lineage"].payload,
        frozen_artifacts["wave26_supplement"].payload,
    )
    return attribution.merge_authority_qualified_lineage(
        frozen_artifacts["selector_universe_lineage"].payload,
        frozen_artifacts["base_lineage"].payload,
        frozen_artifacts["wave26_supplement"].payload,
        production,
        production_summary,
    )


def _answer(payload: dict[str, Any], question_id: int) -> dict[str, Any]:
    answers = cast(list[dict[str, Any]], payload["required_answers"])
    row = next(item for item in answers if item["question_id"] == question_id)
    return cast(dict[str, Any], row["answer"])


def _test_key(
    strategy_id: str,
    *,
    version: str = "test-v1",
) -> attribution.QualifiedIdentityKey:
    return ("TEST_AUTHORITY", "B649", strategy_id, version)


def _identity(
    key: attribution.QualifiedIdentityKey,
    *,
    binding_identity: str,
    callable_identity: str,
) -> attribution.QualifiedLineageIdentity:
    binding_digest = hashlib.sha256(binding_identity.encode()).hexdigest()
    source_digest = hashlib.sha256(("source:" + key[2]).encode()).hexdigest()
    return attribution.QualifiedLineageIdentity(
        authority_qualified_identity_key=key,
        source_authority_id=key[0],
        lottery_id=key[1],
        strategy_id=key[2],
        strategy_version=key[3],
        source_authority="TEST",
        source_classification="RESOLVED_REPLAY_BINDING",
        binding_fingerprint_sha256=binding_digest,
        binding_identity=binding_identity,
        callable_identity=callable_identity,
        callable_family_label=callable_identity,
        implementation_identity=f"test.module:{key[2]}",
        structural_source_digest_sha256=source_digest,
        donor_identity_alias=False,
        combined_classification="DISTINCT_BINDING",
    )


def test_exact_five_source_authorities_are_verified(
    frozen_artifacts: dict[str, attribution.LoadedArtifact],
    frozen_payload: dict[str, Any],
) -> None:
    expected = {
        "base_lineage": (
            "b78eda6a2c9858413c6d1a4cb182ac1083fe9454",
            "2656632e9681e075151a6687414a02a84440bfa3",
            "f2f7d1fd5e08083124aaeb43dfe889f96012f6020b9daafae49f6368f832bfad",
            389466,
        ),
        "rolling_decomposition": (
            "cc9bd1088a9f871618725d0910874283e0318459",
            "7d05638845dc553fa20d793ceba8ce1aceff71ee",
            "92ffb4d5678d403322791de1e3cb133d3bdb91c9c911142f67f4f3f4ee8979c9",
            112094,
        ),
        "rolling_selector": (
            "abc367bd6d8b59d01ecc4d79e56c787bbc03cd20",
            "bf430efd66b7ce1ac38ee04fb0052e8c55cc972c",
            "04df0bfdffcf4ecc05d4f2ac3f58cfa1fa301061c5f1c30e549ddc3b5b174157",
            235086,
        ),
        "selector_universe_lineage": (
            "39592593126325533d664b57097be280682fe2ab",
            "9abc5d50ed9ecbe3dbab4a7e1a6c4bf7fe8a2ee3",
            "461afd3bd0b7eeca93546562330d03234ad57aa2aa4dff25d4432cc254795f37",
            665339,
        ),
        "wave26_supplement": (
            "139b3aae0ec52ef947796ee7db68cd38a9bf9f5c",
            "8467da3725fb323d21fc647b7d6d02ea953a68a6",
            "193b9301640e5561cb495903ce0d6710c47886b72b5f603542505a82f9218db3",
            28165,
        ),
    }

    assert set(frozen_artifacts) == set(expected)
    source_identities = cast(dict[str, dict[str, Any]], frozen_payload["source_identities"])
    for key, (commit, tree, digest, size_bytes) in expected.items():
        artifact = frozen_artifacts[key]
        assert artifact.spec.commit == commit
        assert artifact.spec.tree == tree
        assert artifact.spec.sha256 == digest
        assert artifact.size_bytes == size_bytes
        assert source_identities[key] == artifact.identity_payload()


def test_source_authority_drift_stops_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    bad_selector = replace(attribution.SELECTOR_ARTIFACT, sha256="0" * 64)
    monkeypatch.setattr(
        attribution,
        "ARTIFACT_SPECS",
        (bad_selector, *attribution.ARTIFACT_SPECS[1:]),
    )

    with pytest.raises(
        attribution.AttributionDataError,
        match=r"^SOURCE_AUTHORITY_DRIFT: FROZEN_ARTIFACT_SHA256_MISMATCH",
    ):
        attribution.load_all_frozen_artifacts()


def test_authority_qualified_merge_accounts_for_25_plus_110(
    qualified_lineage: tuple[
        dict[attribution.QualifiedIdentityKey, attribution.QualifiedLineageIdentity],
        dict[str, Any],
    ],
) -> None:
    identities, summary = qualified_lineage

    assert len(identities) == 135
    assert summary["qualified_selector_identity_count"] == 135
    assert summary["raw_selector_label_count"] == 134
    assert summary["production_exact_join_count"] == 25
    assert summary["selector_supplement_row_count"] == 110
    assert summary["total_structurally_accounted"] == 135
    assert summary["complete_135_qualified_identity_coverage"] is True
    assert summary["production_exact_join_source_counts"] == {
        "PRODUCTION_EXACT_JOIN_STATIC_LINEAGE": 22,
        "PRODUCTION_EXACT_JOIN_WAVE26": 3,
    }
    assert summary["unique_binding_fingerprint_count"] == 135
    assert len(cast(list[dict[str, Any]], summary["records"])) == 135


def test_cross_lottery_raw_label_collision_remains_two_qualified_identities(
    qualified_lineage: tuple[
        dict[attribution.QualifiedIdentityKey, attribution.QualifiedLineageIdentity],
        dict[str, Any],
    ],
) -> None:
    identities, summary = qualified_lineage
    collision = {key for key in identities if key[2] == "midfreq_fourier_2bet"}

    assert collision == {
        (
            "P638_CURRENT_REPLAY_AND_RANKING",
            "P638",
            "midfreq_fourier_2bet",
            "v0.1-p638-wave1",
        ),
        (
            "T539_HISTORICAL_SQLITE",
            "T539",
            "midfreq_fourier_2bet",
            "v0.1",
        ),
    }
    assert {
        tuple(key)
        for key in cast(
            list[list[str]],
            summary["cross_lottery_raw_label_collision_identity_keys"],
        )
    } == collision


def test_donor_provenance_is_never_promoted_to_identity_alias(
    frozen_artifacts: dict[str, attribution.LoadedArtifact],
    qualified_lineage: tuple[
        dict[attribution.QualifiedIdentityKey, attribution.QualifiedLineageIdentity],
        dict[str, Any],
    ],
) -> None:
    identities, summary = qualified_lineage
    assert summary["donor_identity_alias_count"] == 0
    assert all(not identity.donor_identity_alias for identity in identities.values())

    supplement = copy.deepcopy(frozen_artifacts["selector_universe_lineage"].payload)
    rows = cast(list[dict[str, Any]], supplement["supplement_rows"])
    provenance = cast(dict[str, Any], rows[0]["donor_provenance_references"])
    provenance["donor_identity_alias"] = True
    production, production_summary = attribution.merge_lineage_authorities(
        frozen_artifacts["base_lineage"].payload,
        frozen_artifacts["wave26_supplement"].payload,
    )

    with pytest.raises(
        attribution.AttributionDataError,
        match="DONOR_IDENTITY_ALIAS_FORBIDDEN",
    ):
        attribution.merge_authority_qualified_lineage(
            supplement,
            frozen_artifacts["base_lineage"].payload,
            frozen_artifacts["wave26_supplement"].payload,
            production,
            production_summary,
            enforce_sealed_shape=False,
        )


def test_all_selected_identities_resolve_and_all_experiments_are_classified(
    frozen_payload: dict[str, Any],
) -> None:
    quality = cast(dict[str, Any], frozen_payload["source_data_quality"])
    aggregates = cast(dict[str, Any], frozen_payload["aggregates"])
    experiments = cast(list[dict[str, Any]], frozen_payload["experiments"])
    available = [row for row in experiments if cast(bool, row["available"])]

    assert quality["qualified_selected_identity_count"] == 135
    assert quality["raw_selected_strategy_label_count"] == 134
    assert quality["selected_qualified_identities_absent_from_combined_lineage_count"] == 0
    assert quality["lineage_attribution_complete_available_experiment_count"] == 62
    assert quality["lineage_source_inconsistent_available_experiment_count"] == 0
    assert aggregates["experiment_count"] == 66
    assert aggregates["available_experiment_count"] == 62
    assert aggregates["switching_active_experiment_count"] == 32
    assert aggregates["diversity_class_counts"] == {
        "DISTINCT_BINDING_DIVERSITY": 18,
        "INCONCLUSIVE": 4,
        "LINEAGE_SOURCE_INCONSISTENT": 0,
        "MIXED_DIVERSITY": 12,
        "NO_SWITCH": 30,
        "PARAMETER_SIBLING_DIVERSITY_ONLY": 2,
    }
    assert len(available) == 62
    assert all(row["lineage_attribution_complete"] is True for row in available)
    assert all(row["diversity_class"] != "LINEAGE_SOURCE_INCONSISTENT" for row in available)


def test_experiment_level_structural_diversity_classes() -> None:
    key_a = _test_key("a")
    key_b = _test_key("b")
    key_c = _test_key("c")
    same_binding = {
        key_a: _identity(
            key_a,
            binding_identity="binding:same",
            callable_identity="callable:same",
        ),
        key_b: _identity(
            key_b,
            binding_identity="binding:same",
            callable_identity="callable:same",
        ),
    }
    siblings = {
        key_a: _identity(
            key_a,
            binding_identity="binding:a",
            callable_identity="callable:shared",
        ),
        key_b: _identity(
            key_b,
            binding_identity="binding:b",
            callable_identity="callable:shared",
        ),
    }
    distinct = {
        key_a: _identity(
            key_a,
            binding_identity="binding:a",
            callable_identity="callable:a",
        ),
        key_b: _identity(
            key_b,
            binding_identity="binding:b",
            callable_identity="callable:b",
        ),
    }
    mixed = {
        **siblings,
        key_c: _identity(
            key_c,
            binding_identity="binding:c",
            callable_identity="callable:c",
        ),
    }

    assert attribution.attribute_selection_diversity(
        {key_a: 2, key_b: 3},
        switch_count=2,
        lottery_id="B649",
        identities=same_binding,
    )["diversity_class"] == "NO_SWITCH"
    assert attribution.attribute_selection_diversity(
        {key_a: 2, key_b: 3},
        switch_count=2,
        lottery_id="B649",
        identities=siblings,
    )["diversity_class"] == "PARAMETER_SIBLING_DIVERSITY_ONLY"
    assert attribution.attribute_selection_diversity(
        {key_a: 2, key_b: 3},
        switch_count=2,
        lottery_id="B649",
        identities=distinct,
    )["diversity_class"] == "DISTINCT_BINDING_DIVERSITY"
    assert attribution.attribute_selection_diversity(
        {key_a: 2, key_b: 3, key_c: 4},
        switch_count=2,
        lottery_id="B649",
        identities=mixed,
    )["diversity_class"] == "MIXED_DIVERSITY"
    assert attribution.attribute_selection_diversity(
        {},
        switch_count=0,
        lottery_id="B649",
        identities={},
        available=False,
    )["diversity_class"] == "INCONCLUSIVE"


def test_missing_qualified_identity_fails_closed_without_inventing_counts() -> None:
    key_a = _test_key("a")
    missing_key = _test_key("missing")
    identities = {
        key_a: _identity(
            key_a,
            binding_identity="binding:a",
            callable_identity="callable:a",
        )
    }

    result = attribution.attribute_selection_diversity(
        {key_a: 2, missing_key: 3},
        switch_count=1,
        lottery_id="B649",
        identities=identities,
    )

    assert result["diversity_class"] == "LINEAGE_SOURCE_INCONSISTENT"
    assert result["lineage_attribution_complete"] is False
    assert result["structurally_unresolved_authority_qualified_identity_keys"] == [
        list(missing_key)
    ]
    assert result["structurally_unresolved_selected_strategy_ids"] == ["missing"]
    assert result["unique_binding_fingerprint_count"] is None
    assert result["unique_callable_identity_count"] is None
    assert result["more_than_one_distinct_binding_identity_selected"] is None


def test_all_66_sealed_outcomes_are_preserved_exactly(
    frozen_artifacts: dict[str, attribution.LoadedArtifact],
    frozen_payload: dict[str, Any],
) -> None:
    selector_cells = cast(
        list[dict[str, Any]], frozen_artifacts["rolling_selector"].payload["cells"]
    )
    decomposition_cells = cast(
        list[dict[str, Any]],
        frozen_artifacts["rolling_decomposition"].payload["cells"],
    )
    result_experiments = cast(list[dict[str, Any]], frozen_payload["experiments"])
    result_index = {
        (cast(str, row["cell_id"]), cast(int, row["window"])): row
        for row in result_experiments
    }
    decomposition_index = {
        (cast(str, cell["cell_id"]), cast(int, window["window"])): window
        for cell in decomposition_cells
        for window in cast(list[dict[str, Any]], cell["windows"])
    }
    source_labels = {50: "SHORT", 300: "MEDIUM", 750: "LONG"}

    observed = 0
    for cell in selector_cells:
        cell_id = cast(str, cell["cell_id"])
        source_experiments = cast(dict[str, dict[str, Any]], cell["experiments"])
        for window, source_label in source_labels.items():
            source = source_experiments[source_label]
            result = result_index[(cell_id, window)]
            decomposition = decomposition_index[(cell_id, window)]
            frequencies = cast(dict[str, int], source["rolling_selection_frequency"])
            expected_frequency_rows = [
                {"selection_count": frequencies[strategy_id], "strategy_id": strategy_id}
                for strategy_id in sorted(frequencies)
            ]

            assert result["original_sign"] == decomposition["classification"]
            assert result["historical_sign"] == decomposition["classification"]
            assert result["original_absolute_paired_delta"] == source["absolute_paired_delta"]
            assert result["original_exact_delta"] == source["absolute_paired_delta"]
            assert result["original_relative_paired_delta"] == source["relative_paired_delta"]
            assert result["original_eligible_target_count"] == source["eligible_target_count"]
            assert result["original_switch_count"] == source["rolling_strategy_switch_count"]
            assert result["switch_count"] == decomposition["switch_count"]
            assert result["frozen_baseline_strategy_id"] == source["frozen_baseline_strategy"]
            assert result["frozen_baseline_strategy_id"] == decomposition[
                "frozen_strategy_identity"
            ]
            assert result["selection_frequency_by_strategy_id"] == expected_frequency_rows
            assert result["selection_target_count"] == decomposition[
                "rolling_selection_target_count"
            ]
            assert result["selection_trace_sha256"] == source["selection_trace_sha256"]
            observed += 1

    assert observed == 66
    assert len(result_index) == 66


def test_output_has_required_per_experiment_fields(
    frozen_payload: dict[str, Any],
) -> None:
    required = {
        "lottery_id",
        "k",
        "window_label",
        "original_sign",
        "original_exact_delta",
        "original_eligible_target_count",
        "original_switch_count",
        "frozen_baseline_strategy_id",
        "selection_frequency_by_strategy_id",
        "selected_authority_qualified_identities",
        "unique_binding_fingerprints",
        "unique_callable_identities",
        "parameter_sibling_families_involved",
        "diversity_class",
    }

    for experiment in cast(list[dict[str, Any]], frozen_payload["experiments"]):
        assert required <= set(experiment)


def test_no_ordered_transition_inference_is_made(
    analysis_result: tuple[dict[str, Any], bytes, bytes],
) -> None:
    payload, _json_bytes, report_bytes = analysis_result
    boundaries = cast(dict[str, Any], payload["boundaries"])
    experiments = cast(list[dict[str, Any]], payload["experiments"])
    report = report_bytes.decode()

    assert boundaries["ordered_transition_attribution"] == "NOT_AVAILABLE"
    assert boundaries["transition_order"] == (
        "NOT_AVAILABLE; SOURCE_CONTAINS_FREQUENCIES_AND_TRACE_HASH_ONLY"
    )
    assert all(row["selection_trace_order_available"] is False for row in experiments)
    assert "ordered transition endpoints" in report.lower()
    assert "trace hash" in report.lower()
    assert "exact transition-level lineage counts are not inferred" in report.lower()


def test_r1_artifacts_remain_byte_immutable() -> None:
    for relative_path, expected_digest in R1_ARTIFACT_HASHES.items():
        path = attribution.REPOSITORY_ROOT / relative_path
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected_digest

    assert "r2-result.json" in attribution.DEFAULT_OUTPUT_JSON.name
    assert "r2.md" in attribution.DEFAULT_OUTPUT_REPORT.name
    assert all(
        path not in {attribution.DEFAULT_OUTPUT_JSON, attribution.DEFAULT_OUTPUT_REPORT}
        for path in (attribution.REPOSITORY_ROOT / item for item in R1_ARTIFACT_HASHES)
    )


def test_required_descriptive_answers_are_sealed(
    frozen_payload: dict[str, Any],
) -> None:
    first = _answer(frozen_payload, 1)
    assert first["switching_active_experiment_count"] == 32
    assert first["actual_distinct_binding_diversity_historical_sign_counts"] == {
        "NEGATIVE": 14,
        "POSITIVE": 15,
        "ZERO": 1,
    }
    assert first["parameter_sibling_diversity_only_historical_sign_counts"] == {
        "NEGATIVE": 2,
        "POSITIVE": 0,
        "ZERO": 0,
    }

    repeated = cast(list[dict[str, Any]], _answer(frozen_payload, 2)["cells"])
    assert [row["cell_id"] for row in repeated] == list(
        attribution.REPEATED_POSITIVE_CELL_IDS
    )
    assert all(
        row["positive_windows_all_use_actual_distinct_binding_diversity"] is True
        for row in repeated
    )

    bridge = _answer(frozen_payload, 3)
    assert bridge["overall_p638_selection_count"] == 42529
    assert bridge["overall_p638_bridge_selection_count"] == 815
    assert bridge["overall_p638_selection_share"] == {
        "decimal_6": "0.019163",
        "exact": "815/42529",
    }
    assert bridge["p638_k1_selection_share"] == {
        "decimal_6": "0.512256",
        "exact": "815/1591",
    }
    assert bridge["transition_order_available"] is False

    positive = _answer(frozen_payload, 4)
    assert positive["positive_experiment_count"] == 15
    assert positive["positive_counts_by_diversity_class"]["DISTINCT_BINDING_DIVERSITY"] == 8
    assert positive["positive_counts_by_diversity_class"]["MIXED_DIVERSITY"] == 7
    assert positive["largest_positive_diversity_classes"] == [
        "DISTINCT_BINDING_DIVERSITY"
    ]

    reversal = _answer(frozen_payload, 5)
    expected_reversal_ids = [
        "B649:K3",
        "P638:K1",
        "P638:K2",
        "P638:K3",
        "P638:K4",
        "P638:K7",
        "T539:K1",
        "T539:K2",
        "T539:K3",
        "T539:K5",
    ]
    assert reversal["same_exact_structural_diversity_class_cell_ids"] == expected_reversal_ids
    assert reversal["same_actual_distinct_binding_presence_cell_ids"] == expected_reversal_ids


def test_wave26_ces_dms_greedy_mwsc_findings_are_exact(
    frozen_payload: dict[str, Any],
) -> None:
    wave = _answer(frozen_payload, 6)
    rows = cast(list[dict[str, Any]], wave["strategies"])
    by_id = {cast(str, row["strategy_id"]): row for row in rows}
    expected = {
        "legacy_biglotto__test_ces__78d17c530ab8": (
            True,
            "binding-sha256:f46ad35a3e0d187dbff06c263695830f6d8218663d02637bb06204f59912af92",
            "wave26-structural-sha256:1e28a4b57f88a0109fbca62fc40c1e9f35967ef6effae6b6de211c08178beeb6",
        ),
        "legacy_biglotto__test_dms__b63442289bd5": (
            True,
            "binding-sha256:416b774564574798d961188b0968af43b39b4721a280b9c784de65d4ff2ee25f",
            "wave26-structural-sha256:e208ad41afb8cba2efd6d285928c173ab6b209a9db461e80dafa274a3e1c32f1",
        ),
        "legacy_biglotto__test_greedy_optimizer__82df7f878ece": (
            False,
            "binding-sha256:057b47024f8fa6e65d3f8aed1ca445aade1c5e8d920468a367ab460fbdf75600",
            "wave26-structural-sha256:dd79e07ca29acb7757de688b1c43716ce3224ba2e6834e41e7eba9ea8a9365b0",
        ),
        "legacy_biglotto__test_mwsc__ba37643d6a3b": (
            True,
            "binding-sha256:8d7b4cc6d782d741719373280526a2c544d299763a86a262e36582b06c18731d",
            "wave26-structural-sha256:51d3b444f45840125e3668b6d6a0b9eeb51db7b0391e506612b829f5d4842f3e",
        ),
    }

    assert wave["appears_in_selector_universe_count"] == 4
    assert wave["appears_in_selection_count"] == 3
    assert set(by_id) == set(expected)
    for strategy_id, (selected, binding_identity, callable_identity) in expected.items():
        row = by_id[strategy_id]
        assert row["in_selector_universe"] is True
        assert row["selected"] is selected
        assert row["contributes_to_selected_qualified_lineage"] is selected
        assert row["binding_identity"] == binding_identity
        assert row["callable_identity"] == callable_identity


def test_output_is_deterministic_and_matches_checked_in_artifacts() -> None:
    first_payload, first_json, first_report = attribution.run_analysis()
    second_payload, second_json, second_report = attribution.run_analysis()

    assert first_payload == second_payload
    assert first_json == second_json
    assert first_report == second_report
    assert attribution.DEFAULT_OUTPUT_JSON.read_bytes() == first_json
    assert attribution.DEFAULT_OUTPUT_REPORT.read_bytes() == first_report
    assert first_json.endswith(b"\n")
    assert first_report.endswith(b"\n")

    experiments = cast(list[dict[str, Any]], first_payload["experiments"])
    observed_order = [
        (cast(str, row["lottery_id"]), cast(int, row["k"]), cast(int, row["window"]))
        for row in experiments
    ]
    assert observed_order == sorted(observed_order)


def test_only_r2_output_paths_are_selected() -> None:
    expected = {
        Path(
            "docs/research/matrix-native-results/"
            "selector-lineage-diversity-attribution-r2-result.json"
        ),
        Path("docs/research/selector-lineage-diversity-attribution-r2.md"),
    }
    observed = {
        attribution.DEFAULT_OUTPUT_JSON.relative_to(attribution.REPOSITORY_ROOT),
        attribution.DEFAULT_OUTPUT_REPORT.relative_to(attribution.REPOSITORY_ROOT),
    }

    assert observed == expected
