"""Application tests for the DB-free Strategy Overview query."""

from __future__ import annotations

import pytest

from lottolab.application.use_cases.query_strategy_overview import (
    MAX_STRATEGY_SEARCH_LENGTH,
    QueryStrategyOverview,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import LifecycleStatus, StrategyDescriptor
from lottolab.strategies.catalog import StrategyCatalog


def descriptor(
    strategy_id: str,
    display_name: str,
    *,
    lottery_types: tuple[LotteryType, ...],
    status: LifecycleStatus,
    executable: bool = False,
) -> StrategyDescriptor:
    return StrategyDescriptor(
        strategy_id=strategy_id,
        strategy_name=display_name,
        version="v1.0",
        lottery_types=lottery_types,
        lifecycle_status=status,
        executable=executable,
        adapter_path="fixtures.adapters:run" if executable else None,
        min_history=12,
        provenance=(f"fixture:{strategy_id}",),
    )


@pytest.fixture
def query() -> QueryStrategyOverview:
    return QueryStrategyOverview(
        StrategyCatalog(
            (
                descriptor(
                    "zeta_daily_retired",
                    "Zeta Daily Archive",
                    lottery_types=(LotteryType.DAILY_539,),
                    status=LifecycleStatus.RETIRED,
                ),
                descriptor(
                    "alpha_multi_online",
                    "Weighted Moon Model",
                    lottery_types=(LotteryType.BIG_LOTTO, LotteryType.POWER_LOTTO),
                    status=LifecycleStatus.ONLINE,
                    executable=True,
                ),
                descriptor(
                    "middle_big_observation",
                    "Social Signal Watch",
                    lottery_types=(LotteryType.BIG_LOTTO,),
                    status=LifecycleStatus.OBSERVATION,
                ),
            )
        )
    )


def test_no_filter_preserves_descriptor_declaration_order(
    query: QueryStrategyOverview,
) -> None:
    response = query.execute()

    assert [item.strategy_id for item in response.items] == [
        "zeta_daily_retired",
        "alpha_multi_online",
        "middle_big_observation",
    ]


@pytest.mark.parametrize(
    ("search", "expected_id"),
    [
        ("  ALPHA_MULTI  ", "alpha_multi_online"),
        ("moon model", "alpha_multi_online"),
        ("social signal", "middle_big_observation"),
    ],
)
def test_text_search_is_trimmed_casefolded_substring_matching(
    query: QueryStrategyOverview,
    search: str,
    expected_id: str,
) -> None:
    assert [item.strategy_id for item in query.execute(q=search).items] == [expected_id]


def test_lottery_type_filter(query: QueryStrategyOverview) -> None:
    assert [
        item.strategy_id
        for item in query.execute(lottery_type=LotteryType.BIG_LOTTO).items
    ] == ["alpha_multi_online", "middle_big_observation"]


def test_lifecycle_filter(query: QueryStrategyOverview) -> None:
    response = query.execute(lifecycle_status=LifecycleStatus.RETIRED)
    assert [item.strategy_id for item in response.items] == ["zeta_daily_retired"]


@pytest.mark.parametrize(
    ("executable", "expected_ids"),
    [
        (True, ["alpha_multi_online"]),
        (False, ["zeta_daily_retired", "middle_big_observation"]),
    ],
)
def test_executable_filter(
    query: QueryStrategyOverview,
    executable: bool,
    expected_ids: list[str],
) -> None:
    assert [
        item.strategy_id for item in query.execute(executable=executable).items
    ] == expected_ids


def test_all_filters_use_and_semantics(query: QueryStrategyOverview) -> None:
    response = query.execute(
        q="weighted",
        lottery_type=LotteryType.POWER_LOTTO,
        lifecycle_status=LifecycleStatus.ONLINE,
        executable=True,
    )
    assert [item.strategy_id for item in response.items] == ["alpha_multi_online"]


def test_filtered_empty_result_has_complete_zero_summary(
    query: QueryStrategyOverview,
) -> None:
    response = query.execute(q="not-present")

    assert response.items == ()
    assert response.summary.total == 0
    assert response.summary.executable_count == 0
    assert response.summary.metadata_only_count == 0
    assert response.summary.lifecycle_counts == {status: 0 for status in LifecycleStatus}
    assert response.summary.lottery_type_counts == {kind: 0 for kind in LotteryType}


def test_summary_counts_only_returned_descriptors(query: QueryStrategyOverview) -> None:
    summary = query.execute().summary

    assert summary.total == 3
    assert summary.executable_count == 1
    assert summary.metadata_only_count == 2
    assert summary.lifecycle_counts == {
        LifecycleStatus.IDEA: 0,
        LifecycleStatus.OBSERVATION: 1,
        LifecycleStatus.ONLINE: 1,
        LifecycleStatus.REJECTED: 0,
        LifecycleStatus.RETIRED: 1,
    }
    assert summary.lottery_type_counts == {
        LotteryType.DAILY_539: 1,
        LotteryType.BIG_LOTTO: 2,
        LotteryType.POWER_LOTTO: 1,
    }


def test_items_expose_descriptor_provenance_without_result_fields(
    query: QueryStrategyOverview,
) -> None:
    item = query.execute(q="alpha_multi").model_dump(mode="json")["items"][0]

    assert item["provenance"] == ["fixture:alpha_multi_online"]
    assert set(item) == {
        "strategy_id",
        "display_name",
        "version",
        "supported_lottery_types",
        "minimum_history",
        "lifecycle_status",
        "executable",
        "provenance",
    }


def test_unregistered_evidence_is_explicitly_unavailable(
    query: QueryStrategyOverview,
) -> None:
    capabilities = query.execute().capabilities.model_dump(mode="json")

    assert capabilities == {
        "evaluation_metrics_available": False,
        "d3_status_available": False,
        "best_strategy_ranking_available": False,
        "unavailable_reason_codes": [
            "NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE"
        ],
    }
    assert set(capabilities) == {
        "evaluation_metrics_available",
        "d3_status_available",
        "best_strategy_ranking_available",
        "unavailable_reason_codes",
    }


@pytest.mark.parametrize("query_text", [" ", "\t\n"])
def test_blank_search_is_rejected_at_the_use_case_boundary(
    query: QueryStrategyOverview,
    query_text: str,
) -> None:
    with pytest.raises(ValueError, match="must not be blank"):
        query.execute(q=query_text)


def test_overlong_search_is_rejected_at_the_use_case_boundary(
    query: QueryStrategyOverview,
) -> None:
    with pytest.raises(ValueError, match="at most"):
        query.execute(q="x" * (MAX_STRATEGY_SEARCH_LENGTH + 1))
