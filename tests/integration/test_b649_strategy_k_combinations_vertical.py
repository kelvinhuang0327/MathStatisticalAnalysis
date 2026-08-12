"""Focused acceptance against the three sealed B649 analytics authorities."""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from lottolab.application.b649_strategy_k_combinations import (
    B649CombinationCriterion,
    B649CombinationProxyMode,
    B649CombinationQuery,
    B649CombinationSort,
    B649CombinationWindow,
    B649StrategyAvailability,
    B649StrategyKCriterion,
    B649StrategyKQuery,
    B649StrategyKSort,
    B649StrategyKWindowKind,
    B649WindowRole,
)
from lottolab.infrastructure.b649_analytics_artifact_reader import (
    COMBINATION_TASK_TREE,
    OBSERVER_TASK_TREE,
    STRATEGY_K_FULL_OUTPUT_TREE,
    STRATEGY_K_TASK_TREE,
    B649AnalyticsAuthorityPaths,
    SealedB649AnalyticsArtifactReader,
)
from lottolab.interfaces.api.app import create_app
from lottolab.interfaces.api.local_app import (
    B649_DEFAULT_TASK_DATA_ROOT,
    create_local_app,
)

PATHS = B649AnalyticsAuthorityPaths(
    strategy_k_root=(
        B649_DEFAULT_TASK_DATA_ROOT / "B649_STRATEGY_K_HISTORICAL_MATRIX_AUTHORITY_R1"
    ),
    combination_root=(B649_DEFAULT_TASK_DATA_ROOT / "B649_COMBINATION_PROJECTION_R1"),
    observer_root=(
        B649_DEFAULT_TASK_DATA_ROOT / "B649_COMBINATION_PROSPECTIVE_FORWARD_OBSERVER_R1"
    ),
)
pytestmark = pytest.mark.skipif(
    not all(
        path.is_dir()
        for path in (
            PATHS.strategy_k_root,
            PATHS.combination_root,
            PATHS.observer_root,
        )
    ),
    reason="sealed B649 analytics authorities are not present locally",
)


@pytest.fixture(scope="module")
def reader() -> SealedB649AnalyticsArtifactReader:
    return SealedB649AnalyticsArtifactReader(PATHS)


def test_strategy_k_parses_sealed_matrix_and_authority_driven_availability(
    reader: SealedB649AnalyticsArtifactReader,
) -> None:
    summary = reader.strategy_k_summary()

    assert summary.authority_task_tree == STRATEGY_K_TASK_TREE
    assert summary.authority_full_output_tree == STRATEGY_K_FULL_OUTPUT_TREE
    assert summary.matrix_row_count == 6624
    assert summary.supported_k_values == (1, 2, 3, 4, 5, 6)
    assert summary.current_executable_strategy_count == 68
    assert summary.matrix_available_strategy_count == 23
    assert summary.matrix_unavailable_strategy_count == 45
    assert summary.historical_accounted_identity_count == 133
    assert summary.measurement_mode == "CANDIDATE_COVERAGE"
    assert summary.nested_windows_independent is False
    assert summary.predictive_advantage_claimed is False
    assert [item.window_role for item in summary.windows] == [
        B649WindowRole.PRIMARY_EVIDENCE,
        B649WindowRole.STABILITY_CONFIRMATION,
        B649WindowRole.DEGRADATION_VETO,
        B649WindowRole.REFERENCE_ONLY,
    ]
    unavailable = [
        item
        for item in summary.strategies
        if item.availability is B649StrategyAvailability.PORTFOLIO_ORDER_AGGREGATION_NOT_DEFINED
    ]
    assert len(unavailable) == 45
    assert all(item.response_shape == "PORTFOLIO" for item in unavailable)


def test_strategy_k_query_preserves_exact_fractions_and_comparable_filters(
    reader: SealedB649AnalyticsArtifactReader,
) -> None:
    page = reader.query_strategy_k(
        B649StrategyKQuery(
            requested_k=6,
            window_kind=B649StrategyKWindowKind.LONG,
            criterion=B649StrategyKCriterion.M2_PLUS,
            sort=B649StrategyKSort.OBSERVED_MINUS_BASELINE_DESC,
            limit=100,
        )
    )

    assert page.total == 23
    assert len(page.items) == 23
    assert page.window_role is B649WindowRole.PRIMARY_EVIDENCE
    assert page.ranking_label == "Historical best under current filters"
    assert all(item.requested_k == 6 for item in page.items)
    assert all(item.criterion is B649StrategyKCriterion.M2_PLUS for item in page.items)
    assert all(item.window_kind is B649StrategyKWindowKind.LONG for item in page.items)
    assert all(item.success_denominator == item.eligible_observation_count for item in page.items)
    assert all(item.random_baseline_denominator > 0 for item in page.items)
    assert all(item.effective_unique_k_counts for item in page.items)


def test_pair_and_triple_combination_queries_are_bounded_and_upstream_ranked(
    reader: SealedB649AnalyticsArtifactReader,
) -> None:
    summary = reader.combination_summary()
    assert summary.authority_task_tree == COMBINATION_TASK_TREE
    assert summary.member_counts == (2, 3)
    assert summary.full_projection_sent_to_browser is False
    assert summary.predictive_advantage_claimed is False

    pair_page = reader.query_combinations(
        B649CombinationQuery(
            proxy_mode=B649CombinationProxyMode.A,
            member_count=2,
            window=B649CombinationWindow.LONG_750,
            criterion=B649CombinationCriterion.M2_PLUS,
            limit=3,
            offset=1,
        )
    )
    assert pair_page.total == 20
    assert [row.sealed_rank for row in pair_page.items] == [2, 3, 4]
    assert all(row.combination_id.startswith("PAIR_") for row in pair_page.items)
    assert all(row.success_denominator == row.eligible_draws for row in pair_page.items)
    assert all(row.exact_random_baseline_denominator > 0 for row in pair_page.items)

    triple_page = reader.query_combinations(
        B649CombinationQuery(
            proxy_mode=B649CombinationProxyMode.C,
            member_count=3,
            window=B649CombinationWindow.MID_300,
            criterion=B649CombinationCriterion.M3_PLUS,
            sort=B649CombinationSort.COMBINATION_ID_ASC,
            limit=5,
        )
    )
    assert triple_page.items
    assert all(row.combination_id.startswith("TRIPLE_") for row in triple_page.items)
    assert [row.combination_id for row in triple_page.items] == sorted(
        row.combination_id for row in triple_page.items
    )
    member = triple_page.items[0].member_strategy_ids[0]
    searched = reader.query_combinations(
        B649CombinationQuery(
            proxy_mode=B649CombinationProxyMode.C,
            member_count=3,
            window=B649CombinationWindow.MID_300,
            criterion=B649CombinationCriterion.M3_PLUS,
            member_search=member,
            limit=100,
        )
    )
    assert searched.items
    assert all(member in row.member_strategy_ids for row in searched.items)


def test_observer_status_is_derived_without_promoting_holdout_evidence(
    reader: SealedB649AnalyticsArtifactReader,
) -> None:
    status = reader.evidence_status()

    assert status.observer_task_tree == OBSERVER_TASK_TREE
    assert status.historical_evidence_status == "AVAILABLE"
    assert status.pre_freeze_date_unseen_holdout_count == 6
    assert status.post_freeze_date_prospective_count == 0
    assert status.checkpoints_reached == ()
    assert status.c_forward_status == "C_PROXY_HORIZON_NOT_FROZEN"
    assert status.holdout_used_to_rerank_historical_results is False
    assert status.predictive_advantage_claimed is False


def test_api_serializes_exact_identity_and_observer_unavailability_is_isolated(
    reader: SealedB649AnalyticsArtifactReader,
) -> None:
    class _ObserverUnavailable:
        def strategy_k_summary(self):
            return reader.strategy_k_summary()

        def query_strategy_k(self, query: B649StrategyKQuery):
            return reader.query_strategy_k(query)

        def combination_summary(self):
            return reader.combination_summary()

        def query_combinations(self, query: B649CombinationQuery):
            return reader.query_combinations(query)

        def evidence_status(self):
            raise FileNotFoundError("observer intentionally unavailable")

    app = create_app(b649_analytics_artifact_reader_factory=_ObserverUnavailable)
    client = TestClient(app)
    strategy_response = client.get(
        "/api/v1/b649-strategy-k-combinations/strategy-k",
        params={
            "requested_k": 1,
            "window_kind": "LONG",
            "criterion": "M1_PLUS",
            "limit": 1,
        },
    )
    assert strategy_response.status_code == 200
    strategy_row = strategy_response.json()["items"][0]
    assert isinstance(strategy_row["success_numerator"], int)
    assert isinstance(strategy_row["success_denominator"], int)
    assert isinstance(strategy_row["random_baseline_numerator"], int)
    assert isinstance(strategy_row["random_baseline_denominator"], int)

    combination_response = client.get(
        "/api/v1/b649-strategy-k-combinations/combinations",
        params={
            "proxy_mode": "A",
            "member_count": 2,
            "window": "LONG_750",
            "criterion": "M2_PLUS",
            "limit": 1,
        },
    )
    assert combination_response.status_code == 200
    assert combination_response.json()["items"][0]["member_count"] == 2
    evidence_response = client.get("/api/v1/b649-strategy-k-combinations/evidence-status")
    assert evidence_response.status_code == 503
    assert evidence_response.json()["error_code"] == ("B649_OBSERVER_AUTHORITY_UNAVAILABLE")


def test_local_runtime_wires_the_pinned_sealed_reader() -> None:
    response = TestClient(create_local_app()).get(
        "/api/v1/b649-strategy-k-combinations/strategy-k/summary"
    )

    assert response.status_code == 200
    assert response.json()["authority_task_tree"] == STRATEGY_K_TASK_TREE
    assert response.json()["matrix_row_count"] == 6624


def test_reader_does_not_modify_consumed_authority_files() -> None:
    paths = (
        PATHS.strategy_k_root / "strategy_k_matrix.jsonl",
        PATHS.strategy_k_root / "strategy_universe.json",
        PATHS.combination_root / "top_candidates.csv",
        PATHS.observer_root / "observer_contract.json",
        *(sorted((PATHS.observer_root / "observations").glob("*.json"))),
    )
    before = {path: (path.stat().st_size, path.stat().st_mtime_ns) for path in paths}

    fresh_reader = SealedB649AnalyticsArtifactReader(PATHS)
    fresh_reader.strategy_k_summary()
    fresh_reader.combination_summary()
    fresh_reader.evidence_status()

    after = {path: (path.stat().st_size, path.stat().st_mtime_ns) for path in paths}
    assert after == before
