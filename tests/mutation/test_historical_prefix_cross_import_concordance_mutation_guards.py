"""Mutation-sensitive guards for ordered cross-import temporal concordance."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
USE_CASE = (
    ROOT
    / "src/lottolab/application/use_cases/evaluate_historical_prefix_success_windows.py"
)
API = ROOT / "src/lottolab/interfaces/api/historical_prefix_success_windows.py"


def _cross_import_method() -> str:
    return USE_CASE.read_text(encoding="utf-8").split(
        "def get_cross_import_concordance(",
        1,
    )[1].split("def get_multi_import_concordance_census(", 1)[0]


def test_guard_validation_one_factory_two_ordered_exact_loads() -> None:
    method = _cross_import_method()

    assert method.index("_validate_import_identity(left_import_identity_sha256)") < (
        method.index("reader = self._reader_factory()")
    )
    assert method.index("_validate_import_identity(right_import_identity_sha256)") < (
        method.index("reader = self._reader_factory()")
    )
    assert method.index("left_import_identity_sha256 == right_import_identity_sha256") < (
        method.index("reader = self._reader_factory()")
    )
    assert method.count("self._reader_factory()") == 1
    assert method.count("self._load_with_reader(") == 2
    assert method.index("left_source = self._load_with_reader(") < method.index(
        "right_source = self._load_with_reader("
    )


def test_guard_exact_strategy_and_assignments_are_built_once_per_source() -> None:
    method = _cross_import_method()

    assert method.count("_find_exact_strategy(") == 2
    assert method.count("_build_walk_forward_assignments(") == 2
    assert method.count("_temporal_holdout(") == 2
    assert "left_strategy.identity != right_strategy.identity" in method
    assert "assignments=left_assignments" in method
    assert "assignments=right_assignments" in method
    assert "load_source(" not in method
    assert "sqlite" not in method.casefold()


def test_guard_overlap_uses_exact_target_sha_and_fails_duplicate_targets() -> None:
    source = USE_CASE.read_text(encoding="utf-8")
    overlap = source.split("def _confirmation_target_overlap(", 1)[1].split(
        "def _cross_import_comparisons(",
        1,
    )[0]

    assert overlap.count("assignment.target.draw_sha256") == 2
    assert "[-CONFIRMATION_TARGET_COUNT:]" in overlap
    assert "len(set(left_targets)) != CONFIRMATION_TARGET_COUNT" in overlap
    assert "len(set(right_targets)) != CONFIRMATION_TARGET_COUNT" in overlap
    assert "left_set & right_set" in overlap
    assert "left_set == right_set" in overlap
    assert "DISJOINT" in overlap
    assert "PARTIAL_OVERLAP" in overlap
    assert "IDENTICAL" in overlap
    assert "draw_number" not in overlap


def test_guard_confirmation_only_family_preserves_order_and_source_evidence() -> None:
    source = USE_CASE.read_text(encoding="utf-8")
    comparisons = source.split("def _cross_import_comparisons(", 1)[1].split(
        "def _matrix_cell(",
        1,
    )[0]

    assert "left.confirmation.diagnostics" in comparisons
    assert "right.confirmation.diagnostics" in comparisons
    assert "left.discovery" not in comparisons
    assert "right.discovery" not in comparisons
    assert "strict=True" in comparisons
    assert "len(comparisons) != 64" in comparisons
    assert "left_confirmation_diagnostic=left_diagnostic" in comparisons
    assert "right_confirmation_diagnostic=right_diagnostic" in comparisons
    assert "_effect_change(" in comparisons
    assert "left_diagnostic.risk_difference" in comparisons
    assert "right_diagnostic.risk_difference" in comparisons
    assert ".sort(" not in comparisons


def test_guard_no_combined_inference_or_decision_surface() -> None:
    method = _cross_import_method().casefold()
    api = API.read_text(encoding="utf-8")

    assert api.count('"cross-import-concordance"') == 1
    assert 'operation_id="getHistoricalPrefixStrategyCrossImportConcordance"' in api
    for forbidden in (
        "combined_p_value",
        "meta_analysis",
        "pooled_fisher",
        "pooled_by",
        "independence",
        "replication_success",
        "winner",
        "promote",
        "prediction",
    ):
        assert forbidden not in method
