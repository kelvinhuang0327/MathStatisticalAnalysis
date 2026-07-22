"""Architecture and protected-shape guards for Replay portfolio ranking."""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src" / "lottolab"
PATHS = {
    "domain": SRC / "domain" / "replay_portfolio_ranking.py",
    "use_case": SRC / "application" / "use_cases" / "rank_replay_strategy_portfolios.py",
    "artifact": SRC / "evidence" / "replay_portfolio_ranking_artifact.py",
    "query": SRC / "application" / "use_cases" / "query_replay_scoring_projection.py",
    "api": SRC / "interfaces" / "api" / "replay_portfolio_rankings.py",
    "app": SRC / "interfaces" / "api" / "app.py",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_ranking_modules_exist_in_the_declared_layers() -> None:
    assert all(path.is_file() for path in PATHS.values())


def test_ranking_domain_imports_no_upper_layer() -> None:
    imports = _imports(PATHS["domain"])
    assert not any(
        module.startswith(
            (
                "lottolab.application",
                "lottolab.infrastructure",
                "lottolab.interfaces",
                "lottolab.evidence",
                "lottolab.strategies",
            )
        )
        for module in imports
    )


def test_ranking_use_case_imports_no_infrastructure_or_interfaces() -> None:
    imports = _imports(PATHS["use_case"])
    assert not any(
        module.startswith(("lottolab.infrastructure", "lottolab.interfaces"))
        for module in imports
    )


def test_persisted_artifact_query_imports_no_infrastructure_or_interfaces() -> None:
    imports = _imports(PATHS["query"])
    assert not any(
        module.startswith(("lottolab.infrastructure", "lottolab.interfaces"))
        for module in imports
    )


def test_ranking_artifact_imports_no_database_or_transport() -> None:
    imports = _imports(PATHS["artifact"])
    assert "sqlite3" not in imports
    assert not any(
        module.startswith(
            (
                "lottolab.application",
                "lottolab.infrastructure",
                "lottolab.interfaces",
                "httpx",
                "urllib",
            )
        )
        for module in imports
    )


def test_ranking_sources_touch_no_persistence_or_scheduler_concept() -> None:
    forbidden = ("sqlite3", "Repository", "scheduler", "Scheduler")
    for path in (PATHS["domain"], PATHS["use_case"], PATHS["artifact"], PATHS["api"]):
        source = path.read_text(encoding="utf-8")
        assert not any(token in source for token in forbidden), path


def test_ranking_api_declares_no_default_production_provider() -> None:
    source = PATHS["api"].read_text(encoding="utf-8")
    assert "sqlite3" not in source
    assert "Repository" not in source


def test_zero_argument_ranking_provider_is_removed_from_api_wiring() -> None:
    combined_source = "\n".join(
        PATHS[name].read_text(encoding="utf-8") for name in ("api", "app")
    )
    assert "ReplayScoringArtifactProvider" not in combined_source
    assert "scoring_artifact_provider" not in combined_source
    assert "replay_scoring_projection_reader_factory" in PATHS["app"].read_text(
        encoding="utf-8"
    )


def test_protected_ranking_domain_shapes_are_unchanged() -> None:
    from lottolab.domain.replay_portfolio_ranking import (
        PortfolioRankingGroup,
        PortfolioRankingResult,
        RankedPortfolioCandidate,
    )

    assert tuple(field.name for field in dataclasses.fields(RankedPortfolioCandidate)) == (
        "rank",
        "ticket_count",
        "strategy_positions",
        "strategy_ids",
        "strategy_versions",
        "target_count",
        "total_ticket_count",
        "scored_count",
        "history_closed_count",
        "prediction_closed_count",
        "target_outcome_not_found_count",
        "target_identity_mismatch_count",
        "first_prize_count",
        "second_prize_count",
        "third_prize_count",
        "fourth_prize_count",
        "fifth_prize_count",
        "sixth_prize_count",
        "seventh_prize_count",
        "general_prize_count",
        "no_prize_count",
        "winning_ticket_count",
        "candidate_sha256",
    )
    assert tuple(field.name for field in dataclasses.fields(PortfolioRankingGroup)) == (
        "ticket_count",
        "status",
        "total_candidate_count",
        "candidates",
    )
    assert tuple(field.name for field in dataclasses.fields(PortfolioRankingResult)) == (
        "strategy_count",
        "target_count",
        "top_k",
        "groups",
    )


def test_no_frontend_path_references_portfolio_ranking() -> None:
    for path in (REPO_ROOT / "frontend").rglob("*"):
        if path.is_file() and "node_modules" not in path.parts and path.suffix not in {".json"}:
            assert "replay_portfolio_ranking" not in path.read_text(
                encoding="utf-8", errors="ignore"
            )
