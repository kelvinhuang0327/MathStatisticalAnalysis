"""Mutation guards for qualification random-baseline aggregation."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import lottolab.application.historical_success_qualification_random_baseline as aggregate_module
from lottolab.application.historical_success_qualification_random_baseline import (
    QUALIFICATION_RANDOM_WINDOW_ROLES,
    HistoricalSuccessQualificationRandomRole,
    render_multiple_testing_warning,
)
from lottolab.application.use_cases.evaluate_historical_prefix_success_windows import (
    EvaluateHistoricalPrefixSuccessWindows,
)
from lottolab.domain.strategy_success_evaluation import WindowKind

ROOT = Path(__file__).resolve().parents[2]
AGGREGATE = ROOT / "src/lottolab/application/historical_success_qualification_random_baseline.py"
ROUTER = ROOT / "src/lottolab/interfaces/api/historical_prefix_success_windows.py"


def test_window_roles_and_warning_are_exact_and_descriptive_only() -> None:
    assert QUALIFICATION_RANDOM_WINDOW_ROLES == (
        (
            WindowKind.FULL_HISTORY,
            HistoricalSuccessQualificationRandomRole.REFERENCE_ONLY,
        ),
        (
            WindowKind.LONG,
            HistoricalSuccessQualificationRandomRole.PRIMARY_DESCRIPTIVE_COMPARISON,
        ),
        (
            WindowKind.MEDIUM,
            HistoricalSuccessQualificationRandomRole.CONFIRMATION_DESCRIPTIVE_COMPARISON,
        ),
        (
            WindowKind.SHORT,
            HistoricalSuccessQualificationRandomRole.AUDIT_ONLY_NON_BLOCKING,
        ),
    )
    assert render_multiple_testing_warning(12) == (
        "This response evaluated 12 import × window cells. Each READY "  # noqa: RUF001
        "upper_tail_probability is a raw, unadjusted exact descriptive value. No "
        "multiplicity adjustment, threshold, pooled probability, combined decision, "
        "or random-advantage inference is authorized."
    )


def test_exact_negative_warning_is_the_only_threshold_or_combined_policy_text() -> None:
    source = AGGREGATE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    warning_assignments = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "_MULTIPLE_TESTING_WARNING"
            for target in node.targets
        )
    ]
    assert len(warning_assignments) == 1
    assert ast.literal_eval(warning_assignments[0].value).format(
        evaluated_cell_count=12
    ) == render_multiple_testing_warning(12)
    policy_source = ast.unparse(
        ast.Module(
            body=[node for node in tree.body if node is not warning_assignments[0]],
            type_ignores=[],
        )
    ).casefold()

    for forbidden in (
        "alpha",
        "threshold",
        "significance",
        "combined_probability",
        "adjusted_probability",
        "pooled_probability",
        "ranking_score",
        "promotion_status",
        "production_eligible",
    ):
        assert forbidden not in policy_source
    assert "HistoricalSuccessQualificationPrimaryStatus" not in inspect.getsource(aggregate_module)
    assert "HistoricalSuccessQualificationInformationalFlag" not in inspect.getsource(
        aggregate_module
    )


def test_use_case_pins_one_reader_i_windows_and_four_i_baseline_loop() -> None:
    source = inspect.getsource(
        EvaluateHistoricalPrefixSuccessWindows.get_research_qualification_random_baseline_evidence
    )

    assert source.count("self._reader_factory()") == 1
    assert source.count("self._load_with_reader(") == 1
    assert source.count("_find_exact_strategy(") == 1
    assert source.count("_evaluate_strategy(") == 1
    assert source.count("_evaluate_random_baseline_window(") == 1
    assert "for window_kind, _ in QUALIFICATION_RANDOM_WINDOW_ROLES" in source
    assert "get_research_qualification(" not in source
    assert "get_random_null_baseline(" not in source


def test_router_has_one_adjacent_get_and_no_endpoint_to_endpoint_call() -> None:
    source = ROUTER.read_text(encoding="utf-8")

    assert (
        source.count("getHistoricalPrefixStrategyResearchQualificationRandomBaselineEvidence") == 1
    )
    assert source.count("evaluator.get_research_qualification_random_baseline_evidence(") == 1
    assert source.count("random-baseline-evidence") == 1
    assert "httpx" not in source
    assert "requests." not in source
