"""Mutation-sensitive guards for Historical Success research qualification."""

# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownMemberType=false

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from lottolab.application.historical_success_qualification import (
    INFORMATIONAL_FLAG_ORDER,
    RANDOM_BASELINE_CAVEAT,
    HistoricalSuccessQualificationInformationalFlag,
)
from lottolab.application.use_cases.evaluate_historical_prefix_success_windows import (
    EvaluateHistoricalPrefixSuccessWindows,
)

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "src/lottolab/application/historical_success_qualification.py"
FRONTEND = ROOT / "frontend/src/api/historicalSuccessWindows.ts"
PAGE = (
    ROOT
    / "frontend/src/features/historical-success-windows/"
    "HistoricalSuccessWindowsPage.vue"
)


def test_policy_pins_canonical_flag_order_and_exact_random_baseline_caveat() -> None:
    assert INFORMATIONAL_FLAG_ORDER == (
        HistoricalSuccessQualificationInformationalFlag.CROSS_IMPORT_UNRESOLVED,
        HistoricalSuccessQualificationInformationalFlag.HISTORICAL_CONCORDANCE_OBSERVED,
        HistoricalSuccessQualificationInformationalFlag.RECENT_RELATIONSHIP_DIFFERENCE,
    )
    assert RANDOM_BASELINE_CAVEAT == (
        "Random/null benchmark unavailable; random advantage has not been evaluated."
    )


def test_policy_contains_no_threshold_aggregation_or_superiority_mutation_hook() -> None:
    source = POLICY.read_text(encoding="utf-8").casefold()

    for forbidden in (
        "alpha",
        "threshold",
        "significance",
        "combined_p",
        "aggregate_strategy",
        "strategy_rollup",
        "random superiority",
        "random advantage established",
        "production_eligible",
        "research_supported",
    ):
        assert forbidden not in source
    assert "sorted(flags)" not in source


def test_use_case_reuses_one_assignment_and_holdout_chain_per_source() -> None:
    source = inspect.getsource(
        EvaluateHistoricalPrefixSuccessWindows.get_research_qualification
    )
    tree = ast.parse(inspect.cleandoc(source))
    call_names = [
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]

    assert call_names.count("_build_walk_forward_assignments") == 1
    assert call_names.count("_temporal_holdout") == 1
    assert call_names.count("_recent_50_stability_audit") == 1
    assert "assignments=source_assignments" in source
    assert "temporal_holdout=holdout" in source
    assert source.count("self._reader_factory()") == 1


def test_frontend_has_no_automatic_or_ranked_qualification_path() -> None:
    api = FRONTEND.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")
    qualification_section = page[
        page.index('aria-labelledby="research-qualification-title"') :
        page.index("<aside ")
    ]

    assert "getHistoricalSuccessResearchQualification" in api
    assert "@click=\"evaluateResearchQualification\"" in qualification_section
    assert "Evaluate research qualification" in qualification_section
    assert "sort(" not in qualification_section
    assert "winner" not in qualification_section.casefold()
    assert "score" not in qualification_section.casefold()
    assert "recommended" not in qualification_section.casefold()
    assert "research-state--error" not in qualification_section
