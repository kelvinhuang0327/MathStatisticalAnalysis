"""Architecture and boundary guards for the Next-Draw Recommendation seal layer."""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SEAL_DOMAIN = REPO_ROOT / "src" / "lottolab" / "domain" / "next_draw_recommendation_seal.py"
PREVIEW_DOMAIN = REPO_ROOT / "src" / "lottolab" / "domain" / "next_draw_recommendation.py"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_seal_domain_module_exists() -> None:
    assert SEAL_DOMAIN.is_file()


def test_seal_domain_imports_no_upper_layer() -> None:
    imports = _imports(SEAL_DOMAIN)
    assert not any(
        module.startswith(
            (
                "lottolab.application",
                "lottolab.infrastructure",
                "lottolab.interfaces",
                "lottolab.evidence",
                "lottolab.strategies",
                "lottolab.research",
            )
        )
        for module in imports
    )


def test_seal_domain_touches_no_persistence_network_or_randomness() -> None:
    imports = _imports(SEAL_DOMAIN)
    assert imports.isdisjoint({"sqlite3", "httpx", "urllib", "socket", "random", "numpy"})
    source = SEAL_DOMAIN.read_text(encoding="utf-8")
    assert "Repository" not in source


def test_seal_domain_never_carries_official_outcome_numbers() -> None:
    # The seal freezes the prediction side only; it must never gain a field
    # for official winning numbers or a prize/score result.
    source = SEAL_DOMAIN.read_text(encoding="utf-8")
    for banned in ("winning_number", "official_outcome", "prize", "OfficialOutcome"):
        assert banned not in source


def test_preview_domain_still_declares_no_target_lifecycle_vocabulary() -> None:
    # The prior-stage guard from the preview domain module must still hold:
    # sealing is a strictly separate, later-layered concern that never leaks
    # its vocabulary back into the outcome-free preview ranking module.
    source = PREVIEW_DOMAIN.read_text(encoding="utf-8")
    for banned in ("TargetEligibilityStatus", "PREDICTIONS_SEALED", "OUTCOME_AVAILABLE"):
        assert banned not in source


def test_seal_domain_reuses_the_existing_target_identity_type() -> None:
    # The seal must bind to the exact same canonical target identity the
    # pre-outcome target authority uses -- never a locally re-derived one.
    imports = _imports(SEAL_DOMAIN)
    assert "lottolab.domain.prospective_observer" in imports


def test_protected_seal_shapes_are_unchanged() -> None:
    from lottolab.domain.next_draw_recommendation_seal import (
        NextDrawRecommendationSeal,
        SealedRecommendationBucket,
        SealedStrategyTickets,
    )

    assert tuple(field.name for field in dataclasses.fields(NextDrawRecommendationSeal)) == (
        "schema_version",
        "target",
        "target_scheduled_at",
        "sealed_at",
        "ranking_policy_id",
        "target_registration_digest",
        "evidence_artifact_sha256",
        "causal_history_sha256",
        "causal_history_draw_count",
        "buckets",
        "seal_digest",
    )
    assert tuple(field.name for field in dataclasses.fields(SealedRecommendationBucket)) == (
        "native_ticket_count",
        "availability",
        "total_candidate_count",
        "ranked_strategy_ids",
        "ranking_projection_sha256",
        "sealed_tickets",
    )
    assert tuple(field.name for field in dataclasses.fields(SealedStrategyTickets)) == (
        "rank",
        "strategy_id",
        "strategy_name",
        "status",
        "tickets",
        "detail",
    )


def test_lifecycle_states_are_the_agreed_closed_set() -> None:
    from lottolab.domain.next_draw_recommendation_seal import (
        NextDrawRecommendationLifecycleState,
    )

    assert [member.value for member in NextDrawRecommendationLifecycleState] == [
        "WAITING_FOR_ELIGIBLE_TARGET",
        "TARGET_AVAILABLE",
        "PREDICTIONS_SEALED",
        "OUTCOME_AVAILABLE",
    ]


def test_get_lifecycle_use_case_never_imports_a_write_capable_target_service() -> None:
    # The read-only lifecycle lookup must not be able to register a target or
    # accept a seal -- it may only depend on read-only ports.
    path = (
        REPO_ROOT
        / "src"
        / "lottolab"
        / "application"
        / "use_cases"
        / "get_next_draw_recommendation_lifecycle.py"
    )
    source = path.read_text(encoding="utf-8")
    for banned in (
        "PreOutcomeTargetRegistrationService",
        "PreOutcomeTargetOperationalService",
        "SealNextDrawRecommendation",
        "create_seal",
        "register_earliest",
    ):
        assert banned not in source


def test_lifecycle_api_route_never_calls_a_seal_or_registration_write_path() -> None:
    path = REPO_ROOT / "src" / "lottolab" / "interfaces" / "api" / "next_draw_recommendation.py"
    source = path.read_text(encoding="utf-8")
    lifecycle_route_start = source.index("def get_next_draw_recommendation_lifecycle")
    lifecycle_route_end = source.index("\n    return router", lifecycle_route_start)
    route_body = source[lifecycle_route_start:lifecycle_route_end]
    for banned in ("create_seal", "register_earliest", "SealNextDrawRecommendation"):
        assert banned not in route_body
