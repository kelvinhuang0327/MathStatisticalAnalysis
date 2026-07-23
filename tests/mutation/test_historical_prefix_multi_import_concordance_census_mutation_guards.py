"""Mutation guards for the ordered 2-4 import confirmation census."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
USE_CASE = (
    ROOT
    / "src/lottolab/application/use_cases/evaluate_historical_prefix_success_windows.py"
)
API = ROOT / "src/lottolab/interfaces/api/historical_prefix_success_windows.py"


def _method() -> str:
    return USE_CASE.read_text(encoding="utf-8").split(
        "def get_multi_import_concordance_census(",
        1,
    )[1].split('__all__ = ["EvaluateHistoricalPrefixSuccessWindows"]', 1)[0]


def test_guard_all_input_validation_precedes_one_factory_and_ordered_loads() -> None:
    method = _method()

    assert method.index("_validate_import_identities(import_identity_sha256s)") < (
        method.index("reader = self._reader_factory()")
    )
    assert method.count("self._reader_factory()") == 1
    assert method.count("self._load_with_reader(") == 1
    assert "for import_identity_sha256 in import_identity_sha256s" in method
    assert ".sort(" not in method


def test_guard_strategy_assignments_and_holdout_are_once_per_source() -> None:
    method = _method()

    assert method.count("_find_exact_strategy(") == 1
    assert method.count("_build_walk_forward_assignments(") == 1
    assert method.count("_temporal_holdout(") == 1
    assert "for source in sources" in method
    assert "for source, strategy in zip(sources, strategies, strict=True)" in method
    assert "assignments=source_assignments" in method
    assert "load_source(" not in method
    assert "sqlite" not in method.casefold()


def test_guard_pair_matrix_and_census_are_derived_in_memory() -> None:
    source = USE_CASE.read_text(encoding="utf-8")
    pairs = source.split("def _multi_import_pairs(", 1)[1].split(
        "def _multi_import_cohort_census(",
        1,
    )[0]
    census = source.split("def _multi_import_cohort_census(", 1)[1].split(
        "def _matrix_cell(",
        1,
    )[0]

    assert "for left_index in range(len(sources))" in pairs
    assert "for right_index in range(left_index + 1, len(sources))" in pairs
    assert "len(sources) * (len(sources) - 1) // 2" in pairs
    assert "_confirmation_target_overlap(" in pairs
    assert "holdout.confirmation" in census
    assert "for cohort_index in range(64)" in census
    assert "import_identity_sha256=sources[import_index].metadata" in census
    assert "len(diagnostics) != 64" in census
    assert ".sort(" not in pairs
    assert ".sort(" not in census


def test_guard_neutral_summary_precedence_and_no_combined_inference() -> None:
    source = USE_CASE.read_text(encoding="utf-8")
    summary = source.split("def _multi_import_census_summary(", 1)[1].split(
        "def _multi_import_pairs(",
        1,
    )[0]
    method = _method().casefold()
    api = API.read_text(encoding="utf-8")

    for value in (
        "NO_AVAILABLE_EFFECT",
        "PARTIAL_AVAILABILITY",
        "ALL_AVAILABLE_HIGHER",
        "ALL_AVAILABLE_EQUAL",
        "ALL_AVAILABLE_LOWER",
        "MIXED_AVAILABLE",
    ):
        assert value in summary
    assert api.count('"multi-import-concordance-census"') == 1
    assert (
        'operation_id="getHistoricalPrefixStrategyMultiImportConcordanceCensus"'
        in api
    )
    for forbidden in (
        "combined_p_value",
        "meta_analysis",
        "pooled_fisher",
        "pooled_by",
        "rank",
        "winner",
        "promote",
        "prediction",
    ):
        assert forbidden not in method
