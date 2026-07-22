"""Independent guards used by the Historical Prefix API mutation checks."""

# pyright: reportPrivateUsage=false, reportUnknownArgumentType=false
# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false

from __future__ import annotations

from dataclasses import fields, replace
from typing import Any, cast

from tests.unit.test_historical_prefix_analytics_api import (
    OVERVIEW_PATH,
    RANKINGS_PATH,
    _assert_no_float,
    _client,
    _replay_path,
    _rich_result,
)

from lottolab.domain.historical_prefix_analytics import HistoricalPerDrawPrefixMetrics


def _reversed_ranking_result() -> tuple[object, tuple[object, ...]]:
    result = _rich_result()
    first_group = result.ranking_groups[0]
    reversed_candidates = tuple(
        replace(candidate, rank=rank)
        for rank, candidate in enumerate(reversed(first_group.candidates), start=1)
    )
    return (
        replace(
            result,
            ranking_groups=(
                replace(first_group, candidates=reversed_candidates),
                *result.ranking_groups[1:],
            ),
        ),
        cast(tuple[object, ...], reversed_candidates),
    )


def test_mutation_guard_ratio_numerator_and_denominator() -> None:
    result = _rich_result()
    response = _client(result)[0].get(RANKINGS_PATH)
    source = result.ranking_groups[0].candidates[0].summary.portfolio_success_rate
    ratio = response.json()["groups"][0]["candidates"][0]["summary"][
        "portfolio_success_rate"
    ]

    assert (ratio["numerator"], ratio["denominator"]) == (
        source.numerator,
        source.denominator,
    )


def test_mutation_guard_ratio_never_becomes_float() -> None:
    payload = _client()[0].get(RANKINGS_PATH).json()

    _assert_no_float(payload)


def test_mutation_guard_candidate_order_is_not_sorted_again() -> None:
    result, candidates = _reversed_ranking_result()
    payload = _client(result)[0].get(RANKINGS_PATH).json()

    assert [
        (
            item["identity"]["strategy_id"],
            item["identity"]["strategy_version"],
            item["identity"]["replicate"],
        )
        for item in payload["groups"][0]["candidates"]
    ] == [
        (
            cast(Any, candidate).identity.strategy_id,
            cast(Any, candidate).identity.strategy_version,
            cast(Any, candidate).identity.replicate,
        )
        for candidate in candidates
    ]


def test_mutation_guard_original_ranks_are_not_renumbered() -> None:
    result, candidates = _reversed_ranking_result()
    payload = _client(result)[0].get(RANKINGS_PATH).json()

    assert [item["rank"] for item in payload["groups"][0]["candidates"]] == [
        cast(Any, candidate).rank for candidate in candidates
    ]


def test_mutation_guard_alias_is_not_removed() -> None:
    payload = _client()[0].get(OVERVIEW_PATH, params={"prefix_count": 20}).json()

    assert "alias" in [item["identity"]["strategy_id"] for item in payload["summaries"]]


def test_mutation_guard_zero_portfolio_summary_is_not_removed() -> None:
    payload = _client()[0].get(OVERVIEW_PATH, params={"prefix_count": 20}).json()

    zero = next(
        item for item in payload["summaries"] if item["identity"]["strategy_id"] == "zero"
    )
    assert zero["status"] == "NO_PORTFOLIOS"


def test_mutation_guard_effective_id_is_not_substituted() -> None:
    response = _client()[0].get(_replay_path("alias"), params={"prefix_count": 1})

    assert response.status_code == 200
    assert response.json()["strategy"]["strategy_id"] == "alias"


def test_mutation_guard_replicate_is_not_removed() -> None:
    response = _client()[0].get(_replay_path(replicate=2), params={"prefix_count": 1})

    assert response.status_code == 200
    assert response.json()["strategy"]["replicate"] == 2


def test_mutation_guard_draw_number_remains_numeric() -> None:
    payload = _client()[0].get(_replay_path(), params={"prefix_count": 5}).json()

    assert type(payload["items"][0]["target"]["draw_number"]) is int


def test_mutation_guard_every_per_draw_field_is_present() -> None:
    payload = _client()[0].get(_replay_path(), params={"prefix_count": 5}).json()

    assert set(payload["items"][0]) == {
        field.name for field in fields(HistoricalPerDrawPrefixMetrics)
    }
