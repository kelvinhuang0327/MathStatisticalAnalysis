"""Architecture and boundary guards for Next-Draw Recommendation (P0)."""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOMAIN = REPO_ROOT / "src" / "lottolab" / "domain" / "next_draw_recommendation.py"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_domain_module_exists() -> None:
    assert DOMAIN.is_file()


def test_domain_imports_no_upper_layer_or_sibling_ranking_authority() -> None:
    imports = _imports(DOMAIN)
    assert not any(
        module.startswith(
            (
                "lottolab.application",
                "lottolab.infrastructure",
                "lottolab.interfaces",
                "lottolab.evidence",
                "lottolab.strategies",
                "lottolab.research",
                # sibling descriptive authorities must never be imported here:
                # this module composes their *output*, one layer up, and
                # never reinterprets their internal ranking logic in-place.
                "lottolab.domain.replay_portfolio_ranking",
            )
        )
        for module in imports
    )


def test_domain_touches_no_persistence_network_or_randomness() -> None:
    imports = _imports(DOMAIN)
    assert imports.isdisjoint({"sqlite3", "httpx", "urllib", "socket", "random", "numpy"})
    source = DOMAIN.read_text(encoding="utf-8")
    assert "Repository" not in source


def test_domain_states_the_recommendation_is_not_a_performance_proof() -> None:
    source = " ".join(DOMAIN.read_text(encoding="utf-8").split())
    assert "not a predictive or future-performance claim" in source
    assert "never a ranking input" in source


def test_protected_recommendation_shapes_are_unchanged() -> None:
    from lottolab.domain.next_draw_recommendation import (
        RecommendationBucketView,
        RecommendationCandidate,
        RecommendationExclusion,
        RecommendationWindowMetric,
    )

    assert tuple(field.name for field in dataclasses.fields(RecommendationWindowMetric)) == (
        "window_kind",
        "eligible_draw_count",
        "window_complete",
        "observed_rate",
        "random_baseline_rate",
        "delta_vs_random",
    )
    assert tuple(field.name for field in dataclasses.fields(RecommendationCandidate)) == (
        "rank",
        "strategy_id",
        "strategy_name",
        "native_ticket_count",
        "windows",
        "cross_window_rank_sum",
    )
    assert tuple(field.name for field in dataclasses.fields(RecommendationExclusion)) == (
        "strategy_id",
        "reason",
        "detail",
    )
    assert tuple(field.name for field in dataclasses.fields(RecommendationBucketView)) == (
        "native_ticket_count",
        "availability",
        "total_candidate_count",
        "ranked",
        "excluded",
    )


def test_no_permanently_null_historical_prize_field_is_published() -> None:
    # The field was removed because it had no evidence authority behind it and
    # was always None; it may only return backed by a real evidence source.
    from lottolab.domain import next_draw_recommendation
    from lottolab.interfaces.api import next_draw_recommendation as api_module

    assert "highest_historical_prize" not in DOMAIN.read_text(encoding="utf-8")
    assert not hasattr(next_draw_recommendation, "highest_historical_prize_label")
    assert "highest_historical_prize" not in (
        REPO_ROOT / "src" / "lottolab" / "interfaces" / "api" / "next_draw_recommendation.py"
    ).read_text(encoding="utf-8")
    assert "highest_historical_prize_label" not in api_module.RecommendationCandidateView.model_fields


def test_this_stage_declares_no_target_lifecycle_vocabulary() -> None:
    # Target binding, pre-draw sealing and outcome join are explicitly out of
    # scope here; the domain must not ship their vocabulary as dead scaffolding.
    source = DOMAIN.read_text(encoding="utf-8")
    for banned in ("TargetEligibilityStatus", "PREDICTIONS_SEALED", "OUTCOME_AVAILABLE"):
        assert banned not in source


def test_api_binds_preview_status_and_unbound_target() -> None:
    from lottolab.interfaces.api.next_draw_recommendation import (
        RECOMMENDATION_STATUS_PREVIEW,
        TARGET_BINDING_UNBOUND,
        NextDrawRecommendationResponse,
    )

    assert RECOMMENDATION_STATUS_PREVIEW == "PREVIEW"
    assert TARGET_BINDING_UNBOUND == "UNBOUND_AS_OF_NOW"
    fields = NextDrawRecommendationResponse.model_fields
    assert "recommendation_status" in fields
    assert "target_binding" in fields
    # A bound future target must not be published by this stage at all.
    assert "target_draw_id" not in fields


def test_native_ticket_count_buckets_are_the_agreed_menu() -> None:
    from lottolab.domain.next_draw_recommendation import NATIVE_TICKET_COUNT_BUCKETS, TOP_N

    assert NATIVE_TICKET_COUNT_BUCKETS == (1, 2, 3, 5, 10, 20)
    assert TOP_N == 3
