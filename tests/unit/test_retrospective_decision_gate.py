from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from lottolab.research.exact_statistics import (
    binomial_exact_minimum_detectable_lift,
    binomial_lower_tail,
    binomial_upper_tail,
    holm_step_down_rejections,
)
from lottolab.research.retrospective_decision_gate import (
    MDE_COMPARISON_TOLERANCE_ABS,
    P_VALUE_COMPARISON_TOLERANCE_ABS,
    EndpointObservation,
    RetrospectiveDecisionGateResult,
    compact_result_document,
    default_config_path,
    descriptive_rate_frontier,
    evaluate_metric_matrix,
    evaluate_retrospective_decision_gate,
    load_endpoint_observations_from_seven_candidate_metric_matrix,
    load_retrospective_decision_gate_config,
    write_compact_decision_artifact,
)

_P0 = 7729 / 249711
_WORKSPACE_TASK_DATA = Path("/Users/kelvin/VibeCoding-WorkSpace/.task-data")
_SEVEN_CANDIDATE_ROOT = (
    _WORKSPACE_TASK_DATA / "BIGLOTTO_L2_PAIRWISE_SEVEN_CANDIDATE_CLEAN_EMPIRICAL_COMPARISON_R1"
)
_SIX_CANDIDATE_ROOT = (
    _WORKSPACE_TASK_DATA / "BIGLOTTO_L2_PAIRWISE_SIX_CANDIDATE_CLEAN_EMPIRICAL_COMPARISON_R1"
)
_EIGHTH_CANDIDATE_ROOT = (
    _WORKSPACE_TASK_DATA
    / "BIGLOTTO_L2_PAIRWISE_EIGHTH_CANDIDATE_CLEAN_DATA_EMPIRICAL_VALIDATION_R1"
)
_ORACLE_JSON = (
    _WORKSPACE_TASK_DATA
    / "BIGLOTTO_L2_PAIRWISE_RETROSPECTIVE_DECISION_GATE_ACCEPTANCE_ORACLE_R1"
    / "acceptance_oracle.json"
)
_ORACLE_SHA256 = "e21e139aa4c2e3fbb18674f60b20d3f0de114a2851a4aab40cb3a1583febaede"
_FROZEN_INPUT_HASHES: tuple[tuple[Path, str], ...] = (
    (
        _SEVEN_CANDIDATE_ROOT / "seven_candidate_metric_matrix.csv",
        "0a932841db9fa07a9a375419b74f513fcf463e921e4da824b50cd4663928f3a4",
    ),
    (
        _SEVEN_CANDIDATE_ROOT / "pareto_frontier.json",
        "95b82fa8e97357f5a16b3692e62a5f02faad2f97973571f8ec287c34d95fd508",
    ),
    (
        _SEVEN_CANDIDATE_ROOT / "SHA256SUMS",
        "8fb2d14f46e55af9c18fdeb37728400d3f023f75ba02a3842e997724fe3fe996",
    ),
    (
        _SIX_CANDIDATE_ROOT / "six_candidate_metric_matrix.csv",
        "2e9179585c563a91df402c70f7f3e31d3817ad462d3ef0b977c39bebb5bcf1c3",
    ),
    (
        _SIX_CANDIDATE_ROOT / "full_reference_comparison.json",
        "77a108e412e3c5615841e6c46ae0ffead55b5e1c2d127b96b52abda63d623b76",
    ),
    (
        _EIGHTH_CANDIDATE_ROOT / "final_handoff.json",
        "4e68575f1be299489bebe2aad06e384ef53292bbac11b4df1af1d86921c6e1b3",
    ),
    (
        _EIGHTH_CANDIDATE_ROOT / "SHA256SUMS",
        "ea4685de836545c199e42ee45e89e668b0b784c40011c2d1addd272e6bac27a0",
    ),
)

# Frozen seven-candidate any-prize counts. Values are copied from the sealed
# metric matrix; the gate recomputes p-values rather than trusting a ranking.
_FROZEN_SEVEN_CANDIDATE_HITS: tuple[tuple[str, str, int, int], ...] = (
    ("C1", "750", 750, 30),
    ("C1", "300", 300, 13),
    ("C1", "50", 50, 1),
    ("C1", "FULL_REFERENCE", 1412, 47),
    ("C2", "750", 750, 18),
    ("C2", "300", 300, 7),
    ("C2", "50", 50, 1),
    ("C2", "FULL_REFERENCE", 1412, 40),
    ("C3", "750", 750, 18),
    ("C3", "300", 300, 10),
    ("C3", "50", 50, 2),
    ("C3", "FULL_REFERENCE", 1412, 35),
    ("C4", "750", 750, 20),
    ("C4", "300", 300, 3),
    ("C4", "50", 50, 1),
    ("C4", "FULL_REFERENCE", 1412, 36),
    ("C5", "750", 750, 27),
    ("C5", "300", 300, 8),
    ("C5", "50", 50, 1),
    ("C5", "FULL_REFERENCE", 1412, 47),
    ("C6", "750", 750, 12),
    ("C6", "300", 300, 4),
    ("C6", "50", 50, 1),
    ("C6", "FULL_REFERENCE", 1412, 24),
    ("C8", "750", 750, 27),
    ("C8", "300", 300, 11),
    ("C8", "50", 50, 2),
    ("C8", "FULL_REFERENCE", 1412, 56),
)


def _frozen_observations() -> tuple[EndpointObservation, ...]:
    return tuple(
        EndpointObservation(candidate, endpoint, n, hits)
        for candidate, endpoint, n, hits in _FROZEN_SEVEN_CANDIDATE_HITS
    )


def _gate_result() -> RetrospectiveDecisionGateResult:
    return evaluate_retrospective_decision_gate(
        _frozen_observations(),
        load_retrospective_decision_gate_config(),
    )


def test_frozen_config_family_sizes_and_full_reference_exclusion() -> None:
    config = load_retrospective_decision_gate_config(default_config_path())
    assert config.config_id == "BIGLOTTO_L2_PAIRWISE_RETROSPECTIVE_DECISION_GATE_R1"
    assert config.primary_family_size == 21
    assert config.sensitivity_family_size == 28
    assert "FULL_REFERENCE" not in config.primary_endpoints
    assert "FULL_REFERENCE" in config.sensitivity_endpoints
    assert config.owner_minimum_worthwhile_lift == "UNSET"
    assert config.futility_rule == "UNSET"


def test_holm_ordering_and_step_down_decisions() -> None:
    p_values = (0.01, 0.04, 0.03, 0.005)
    rejected = holm_step_down_rejections(p_values, alpha=0.05)
    assert rejected == (True, False, False, True)


def test_primary_21_and_sensitivity_28_family_separation() -> None:
    result = _gate_result()
    assert len(result.primary_family) == 21
    assert len(result.sensitivity_family) == 28
    assert {record.endpoint for record in result.primary_family} == {"750", "300", "50"}
    assert "FULL_REFERENCE" in {record.endpoint for record in result.sensitivity_family}


def test_full_reference_is_excluded_from_the_primary_family() -> None:
    result = _gate_result()
    assert all(record.endpoint != "FULL_REFERENCE" for record in result.primary_family)
    document = compact_result_document(result)
    assert document["RETROSPECTIVE_PRIMARY_FAMILY_SIZE"] == 21
    assert document["RETROSPECTIVE_SENSITIVITY_FAMILY_SIZE"] == 28


def test_exact_critical_value_and_mde_fixtures_through_the_gate() -> None:
    result = _gate_result()
    single = {entry.n: entry for entry in result.single_test_mde}
    primary = {entry.n: entry for entry in result.primary_holm_first_step_mde}
    sensitivity = {entry.n: entry for entry in result.sensitivity_holm_first_step_mde}
    assert single[50].k_star == 5
    assert single[300].k_star == 15
    assert single[750].k_star == 32
    assert single[1412].k_star == 56
    assert single[50].mde_lift == pytest.approx(4.2250, abs=5e-5)
    assert single[300].mde_lift == pytest.approx(1.9385, abs=5e-5)
    assert single[750].mde_lift == pytest.approx(1.5723, abs=5e-5)
    assert single[1412].mde_lift == pytest.approx(1.4191, abs=5e-5)
    assert primary[50].mde_lift == pytest.approx(5.6831, abs=5e-5)
    assert primary[300].mde_lift == pytest.approx(2.5254, abs=5e-5)
    assert primary[750].mde_lift == pytest.approx(1.8934, abs=5e-5)
    assert 1412 not in primary
    assert sensitivity[50].mde_lift == pytest.approx(5.6831, abs=5e-5)
    assert sensitivity[300].mde_lift == pytest.approx(2.5254, abs=5e-5)
    assert sensitivity[750].mde_lift == pytest.approx(1.8934, abs=5e-5)
    assert sensitivity[1412].mde_lift == pytest.approx(1.6354, abs=5e-5)
    assert all(entry.label == "HOLM_FIRST_STEP_MDE" for entry in result.primary_holm_first_step_mde)


def test_synthetic_strong_lift_passes_superiority() -> None:
    boosted = tuple(
        EndpointObservation("C1", "750", 750, 80) if item.test_id == "C1:750" else item
        for item in _frozen_observations()
    )
    result = evaluate_retrospective_decision_gate(
        boosted, load_retrospective_decision_gate_config()
    )
    assert "C1:750" in result.primary_holm_discoveries
    assert result.primary_holm_discoveries != ()
    p_value = binomial_upper_tail(750, 80, _P0)
    assert p_value <= 0.05 / 21


def test_frozen_seven_candidate_fixture_has_zero_superiority_discoveries() -> None:
    result = _gate_result()
    document = compact_result_document(result)
    assert result.primary_holm_discoveries == ()
    assert result.sensitivity_holm_discoveries == ()
    assert document["RETROSPECTIVE_PRIMARY_HOLM_SUPERIORITY_DISCOVERIES"] == "NONE"
    assert document["RETROSPECTIVE_SENSITIVITY_HOLM_SUPERIORITY_DISCOVERIES"] == "NONE"
    assert document["PROGRAM_LEVEL_CONFIRMATORY_SUPERIORITY_ESTABLISHED"] == "NO"
    assert document["DECISION_GRADE_FRONTIER_AVAILABLE"] == "NO"
    serialized = json.dumps(document)
    assert "SCIENTIFICALLY_MEANINGFUL" not in serialized
    assert "MAX_ANSWERABLE_LIFT" not in serialized
    assert document["NULL_P0"] == "7729/249711"


def test_c6_lower_tail_qc_cannot_appear_as_a_superiority_discovery() -> None:
    result = _gate_result()
    c6_full = next(
        record
        for record in result.sensitivity_family
        if record.candidate == "C6" and record.endpoint == "FULL_REFERENCE"
    )
    lower = binomial_lower_tail(1412, 24, _P0)
    assert lower == pytest.approx(0.000722704, abs=5e-10)
    assert result.c6_qc.two_sided_p == pytest.approx(0.0015487, abs=5e-8)
    assert lower < 0.05 / 21
    assert c6_full.upper_tail_p == pytest.approx(0.999625484963864668, abs=1e-12)
    assert c6_full.rejected is False
    assert "C6:FULL_REFERENCE" not in result.primary_holm_discoveries
    assert "C6:FULL_REFERENCE" not in result.sensitivity_holm_discoveries
    assert result.c6_qc.harm_or_antisignal_qc_flag == "YES"
    assert result.c6_qc.minimal_qc_audit == "CLOSED_NO_DEFECT_FOUND_WITHIN_AUDIT_SCOPE"
    assert result.c6_qc.further_engineering_audit == "NOT_JUSTIFIED"


def test_horizon_50_low_power_annotation_is_derived() -> None:
    result = _gate_result()
    expected = 50 * _P0
    assert expected < 5
    mde = binomial_exact_minimum_detectable_lift(50, _P0, alpha=0.05, power_target=0.80)
    assert mde > 1.5
    assert result.horizon_50.low_expected_count == "YES"
    assert result.horizon_50.low_power_for_moderate_lift == "YES"
    assert result.horizon_50.primary_decision_grade == "NO"
    assert result.horizon_50.descriptive_use_only == "YES"
    document = compact_result_document(result)
    assert document["HORIZON_50_LOW_EXPECTED_COUNT"] == "YES"
    assert document["HORIZON_50_DESCRIPTIVE_USE_ONLY"] == "YES"


def test_descriptive_frontier_with_and_without_horizon_50() -> None:
    observations = _frozen_observations()
    config = load_retrospective_decision_gate_config()
    with_50 = descriptive_rate_frontier(
        observations,
        candidates=config.primary_candidates,
        endpoints=config.primary_endpoints,
    )
    without_50 = descriptive_rate_frontier(
        observations,
        candidates=config.primary_candidates,
        endpoints=("750", "300"),
    )
    result = _gate_result()
    assert with_50 == ("C1", "C8")
    assert without_50 == ("C1",)
    assert result.descriptive_rate_frontier == ("C1", "C8")
    assert result.descriptive_frontier_without_horizon_50 == ("C1",)


def test_unset_owner_threshold_leaves_futility_unknown() -> None:
    result = _gate_result()
    document = compact_result_document(result)
    assert document["OWNER_MINIMUM_WORTHWHILE_LIFT"] == "UNSET"
    assert document["FUTILITY_RULE"] == "UNSET"
    assert document["FUTILITY_ESTABLISHED"] == "UNKNOWN"
    assert document["CANDIDATE_EXPANSION"] == "PAUSE"
    assert document["C7_V3_STATUS"] == "HOLD"
    assert document["C9_STATUS"] == "HOLD"
    assert document["C10_STATUS"] == "HOLD"
    assert document["C11_STATUS"] == "HOLD"


def test_frozen_input_bundles_remain_byte_unchanged() -> None:
    missing = [path for path, _digest in _FROZEN_INPUT_HASHES if not path.is_file()]
    if missing:
        pytest.skip(f"frozen evidence not mounted: {missing[0]}")
    evaluate_retrospective_decision_gate(
        _frozen_observations(), load_retrospective_decision_gate_config()
    )
    for path, digest in _FROZEN_INPUT_HASHES:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


def test_actual_frozen_seven_candidate_csv_matches_embedded_fixture() -> None:
    csv_path = _SEVEN_CANDIDATE_ROOT / "seven_candidate_metric_matrix.csv"
    if not csv_path.is_file():
        pytest.skip("frozen seven-candidate metric matrix is not mounted")
    loaded = load_endpoint_observations_from_seven_candidate_metric_matrix(csv_path)
    embedded = _frozen_observations()
    assert {(item.candidate, item.endpoint, item.n, item.hits) for item in loaded} == {
        (item.candidate, item.endpoint, item.n, item.hits) for item in embedded
    }
    result = evaluate_metric_matrix(csv_path)
    assert result.primary_holm_discoveries == ()
    assert result.sensitivity_holm_discoveries == ()
    assert result.descriptive_rate_frontier == ("C1", "C8")
    assert result.descriptive_frontier_without_horizon_50 == ("C1",)


def test_write_compact_decision_artifact_and_oracle_convergence(tmp_path: Path) -> None:
    csv_path = _SEVEN_CANDIDATE_ROOT / "seven_candidate_metric_matrix.csv"
    if not csv_path.is_file() or not _ORACLE_JSON.is_file():
        pytest.skip("frozen seven-candidate matrix or acceptance oracle is not mounted")
    assert hashlib.sha256(_ORACLE_JSON.read_bytes()).hexdigest() == _ORACLE_SHA256
    result = evaluate_metric_matrix(csv_path)
    artifact = write_compact_decision_artifact(result, tmp_path)
    document = json.loads(artifact.read_text(encoding="utf-8"))
    oracle = json.loads(_ORACLE_JSON.read_text(encoding="utf-8"))
    serialized = json.dumps(document)
    assert "SCIENTIFICALLY_MEANINGFUL" not in serialized
    assert "MAX_ANSWERABLE_LIFT" not in serialized
    assert document["NULL_P0"] == oracle["p0"]["reduced_fraction"]
    assert document["DESCRIPTIVE_RATE_FRONTIER"] == ",".join(
        oracle["descriptive_frontiers"]["with_horizon_50"]["frontier"]
    )
    assert document["DESCRIPTIVE_FRONTIER_WITHOUT_HORIZON_50"] == ",".join(
        oracle["descriptive_frontiers"]["without_horizon_50"]["frontier"]
    )
    assert document["RETROSPECTIVE_PRIMARY_FAMILY_SIZE"] == oracle["primary_superiority_family"][
        "family_size"
    ]
    assert document["RETROSPECTIVE_SENSITIVITY_FAMILY_SIZE"] == oracle[
        "sensitivity_superiority_family"
    ]["family_size"]
    assert document["RETROSPECTIVE_PRIMARY_HOLM_SUPERIORITY_DISCOVERIES"] == oracle[
        "holm_discoveries"
    ]["primary_21"]
    assert document["RETROSPECTIVE_SENSITIVITY_HOLM_SUPERIORITY_DISCOVERIES"] == oracle[
        "holm_discoveries"
    ]["sensitivity_28"]
    _assert_mde_table_matches(
        document["SINGLE_TEST_80PCT_MDE"],
        oracle["exact_mde_table"]["single_test_alpha_0.05"],
    )
    _assert_mde_table_matches(
        document["PRIMARY_HOLM_FIRST_STEP_MDE"],
        oracle["exact_mde_table"]["primary_holm_first_step_alpha_0.05_over_21"],
    )
    _assert_mde_table_matches(
        document["SENSITIVITY_HOLM_FIRST_STEP_MDE"],
        oracle["exact_mde_table"]["sensitivity_holm_first_step_alpha_0.05_over_28"],
    )
    assert document["HORIZON_50_LOW_EXPECTED_COUNT"] == oracle["horizon_50_annotations"][
        "LOW_EXPECTED_COUNT"
    ]
    assert document["HORIZON_50_LOW_POWER_FOR_MODERATE_LIFT"] == oracle["horizon_50_annotations"][
        "LOW_POWER_FOR_MODERATE_LIFT"
    ]
    assert document["HORIZON_50_PRIMARY_DECISION_GRADE"] == "NO"
    assert document["HORIZON_50_DESCRIPTIVE_USE_ONLY"] == "YES"
    assert document["C6_MINIMAL_QC_AUDIT"] == oracle["c6_scoped_qc_state"]["C6_MINIMAL_QC_AUDIT"]
    assert document["C6_FURTHER_ENGINEERING_AUDIT"] == oracle["c6_scoped_qc_state"][
        "C6_FURTHER_ENGINEERING_AUDIT"
    ]
    assert document["CURRENT_AVAILABLE_COMMON_TARGET_COUNT"] == oracle["historical_data_budget"][
        "CURRENT_AVAILABLE_COMMON_TARGET_COUNT"
    ]
    assert document["CURRENT_FROZEN_COMMON_TARGET_HISTORICAL_BUDGET"] == oracle[
        "historical_data_budget"
    ]["CURRENT_FROZEN_COMMON_TARGET_HISTORICAL_BUDGET"]
    assert document["ADDITIONAL_RETROSPECTIVE_COMMON_TARGETS"] == oracle["historical_data_budget"][
        "ADDITIONAL_RETROSPECTIVE_COMMON_TARGETS"
    ]
    assert document["OWNER_MINIMUM_WORTHWHILE_LIFT"] == oracle["futility_and_hold_state"][
        "OWNER_MINIMUM_WORTHWHILE_LIFT"
    ]
    assert document["FUTILITY_ESTABLISHED"] == oracle["futility_and_hold_state"][
        "FUTILITY_ESTABLISHED"
    ]
    assert document["C7_V3_STATUS"] == oracle["futility_and_hold_state"]["C7_V3"]
    assert document["C9_STATUS"] == oracle["futility_and_hold_state"]["C9"]
    assert document["C10_STATUS"] == oracle["futility_and_hold_state"]["C10"]
    assert document["C11_STATUS"] == oracle["futility_and_hold_state"]["C11"]
    assert document["C6_LOWER_TAIL_EXACT_P"] == pytest.approx(
        float(oracle["c6_scoped_qc_state"]["lower_tail_exact_p"]),
        abs=P_VALUE_COMPARISON_TOLERANCE_ABS,
    )
    assert document["C6_TWO_SIDED_EXACT_P"] == pytest.approx(
        float(oracle["c6_scoped_qc_state"]["two_sided_exact_p"]),
        abs=P_VALUE_COMPARISON_TOLERANCE_ABS,
    )


def _assert_mde_table_matches(
    observed: dict[str, dict[str, object]],
    oracle_table: dict[str, dict[str, object]],
) -> None:
    assert set(observed) == set(oracle_table)
    for sample_size, oracle_entry in oracle_table.items():
        assert observed[sample_size]["k_star"] == oracle_entry["k_star"]
        assert observed[sample_size]["mde_lift"] == pytest.approx(
            float(str(oracle_entry["mde_lift"])),
            abs=MDE_COMPARISON_TOLERANCE_ABS,
        )
