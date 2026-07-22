"""HTTP contract coverage for read-only Historical Prefix analytics."""

# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false

from __future__ import annotations

from dataclasses import fields, replace
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from tests.fixtures.historical.prefix_analytics_builder import (
    build_descriptor,
    build_draw,
    build_portfolio,
    build_run_import,
)

from lottolab.domain.historical_prefix_analytics import (
    HistoricalDrawIdentity,
    HistoricalPerDrawPrefixMetrics,
    HistoricalPrefixAnalyticsResult,
    HistoricalStrategyIdentity,
    HistoricalStrategyPrefixSummary,
    analyze_historical_prefixes,
)
from lottolab.domain.historical_results import HistoricalGovernanceStatus
from lottolab.interfaces.api.app import create_app

RANKINGS_PATH = "/api/v1/historical-prefix-analytics/rankings"
OVERVIEW_PATH = "/api/v1/historical-prefix-analytics/strategies"


def _replay_path(
    strategy_id: str = "base",
    strategy_version: str = "v1",
    replicate: int = 1,
) -> str:
    return (
        f"{OVERVIEW_PATH}/{strategy_id}/{strategy_version}/{replicate}/replay"
    )


def _rich_result() -> HistoricalPrefixAnalyticsResult:
    descriptors = (
        build_descriptor("base", strategy_version="v1", replicate=1),
        build_descriptor("base", strategy_version="v1", replicate=2),
        build_descriptor(
            "alias",
            effective_strategy_id="base",
            alias_of_strategy_id="base",
            governance_status=HistoricalGovernanceStatus.RETIRED,
        ),
        build_descriptor("zero", governance_status=HistoricalGovernanceStatus.REJECTED),
    )
    draws = (
        build_draw(1, draw_date="2025-12-31"),
        build_draw(10, draw_date="2026-01-02"),
        build_draw(9, draw_date="2026-01-02"),
    )
    portfolios = (
        build_portfolio(
            "base",
            target_draw_number=10,
            cutoff_draw_number=1,
            hit_counts=(6, 5, 4, 3, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
            special_hits=(
                False,
                True,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
            ),
        ),
        build_portfolio("base", target_draw_number=9, cutoff_draw_number=1),
        build_portfolio("base", replicate=2, target_draw_number=10, cutoff_draw_number=1),
        build_portfolio("alias", target_draw_number=10, cutoff_draw_number=1),
    )
    return analyze_historical_prefixes(
        build_run_import(descriptors=descriptors, draws=draws, portfolios=portfolios)
    )


class _Provider:
    def __init__(
        self,
        result: object,
        *,
        failure: str | None = None,
    ) -> None:
        self.result = result
        self.failure = failure
        self.calls = 0

    def __call__(self) -> HistoricalPrefixAnalyticsResult:
        self.calls += 1
        if self.failure is not None:
            raise RuntimeError(self.failure)
        return cast(HistoricalPrefixAnalyticsResult, self.result)


def _client(
    result: object | None = None,
) -> tuple[TestClient, _Provider]:
    provider = _Provider(_rich_result() if result is None else result)
    return (
        TestClient(
            create_app(historical_prefix_analytics_result_provider=provider)
        ),
        provider,
    )


def _assert_no_float(value: object) -> None:
    if isinstance(value, float):
        raise AssertionError(f"float leaked into exact API response: {value!r}")
    if isinstance(value, dict):
        for item in cast(dict[object, object], value).values():
            _assert_no_float(item)
    elif isinstance(value, list):
        for item in cast(list[object], value):
            _assert_no_float(item)


def test_app_and_openapi_are_lazy_and_expose_only_the_three_exact_get_routes() -> None:
    provider = _Provider(_rich_result())
    app = create_app(historical_prefix_analytics_result_provider=provider)

    document = app.openapi()

    assert provider.calls == 0
    expected = {
        RANKINGS_PATH,
        OVERVIEW_PATH,
        (
            "/api/v1/historical-prefix-analytics/strategies/"
            "{strategy_id}/{strategy_version}/{replicate}/replay"
        ),
    }
    actual = {
        path for path in document["paths"] if path.startswith(
            "/api/v1/historical-prefix-analytics"
        )
    }
    assert actual == expected
    assert all(set(document["paths"][path]) == {"get"} for path in expected)


def test_rankings_preserve_source_order_ranks_identity_and_exact_ratios() -> None:
    result = _rich_result()
    first_group = result.ranking_groups[0]
    reversed_candidates = tuple(
        replace(candidate, rank=rank)
        for rank, candidate in enumerate(reversed(first_group.candidates), start=1)
    )
    result = replace(
        result,
        ranking_groups=(
            replace(first_group, candidates=reversed_candidates),
            *result.ranking_groups[1:],
        ),
    )
    client, provider = _client(result)

    first = client.get(RANKINGS_PATH, params={"top_k": 2})
    second = client.get(RANKINGS_PATH, params={"top_k": 2})

    assert first.status_code == second.status_code == 200
    assert first.content == second.content
    assert provider.calls == 2
    payload = cast(dict[str, Any], first.json())
    assert [group["prefix_count"] for group in payload["groups"]] == [1, 2, 3, 4, 5]
    for source_group, view_group in zip(
        result.ranking_groups, payload["groups"], strict=True
    ):
        expected = source_group.candidates[:2]
        assert [candidate["rank"] for candidate in view_group["candidates"]] == [
            candidate.rank for candidate in expected
        ]
        assert [candidate["identity"]["strategy_id"] for candidate in view_group["candidates"]] == [
            candidate.identity.strategy_id for candidate in expected
        ]
    ratio = payload["groups"][0]["candidates"][0]["summary"][
        "portfolio_success_rate"
    ]
    source_ratio = result.ranking_groups[0].candidates[0].summary.portfolio_success_rate
    assert set(ratio) == {"numerator", "denominator", "is_available"}
    assert ratio["numerator"] == source_ratio.numerator
    assert ratio["denominator"] == source_ratio.denominator
    assert type(ratio["numerator"]) is int
    assert type(ratio["denominator"]) is int
    _assert_no_float(payload)


def test_strategy_overview_preserves_aliases_replicates_zero_summary_and_all_fields() -> None:
    client, provider = _client()

    response = client.get(OVERVIEW_PATH, params={"prefix_count": 20})

    assert response.status_code == 200
    assert provider.calls == 1
    payload = cast(dict[str, Any], response.json())
    identities = [summary["identity"] for summary in payload["summaries"]]
    assert [
        (identity["strategy_id"], identity["strategy_version"], identity["replicate"])
        for identity in identities
    ] == [
        ("alias", "v1", 1),
        ("base", "v1", 1),
        ("base", "v1", 2),
        ("zero", "v1", 1),
    ]
    alias = payload["summaries"][0]
    zero = payload["summaries"][-1]
    assert alias["identity"]["effective_strategy_id"] == "base"
    assert alias["identity"]["alias_of_strategy_id"] == "base"
    assert zero["status"] == "NO_PORTFOLIOS"
    assert zero["max_hit_target"] is None
    assert zero["portfolio_success_rate"] == {
        "numerator": 0,
        "denominator": 0,
        "is_available": False,
    }
    assert set(zero) == {field.name for field in fields(HistoricalStrategyPrefixSummary)}
    assert set(zero["identity"]) == {
        field.name for field in fields(HistoricalStrategyIdentity)
    }


def test_replay_matches_exact_identity_paginates_and_maps_every_per_draw_field() -> None:
    client, provider = _client()

    response = client.get(
        _replay_path(),
        params={"prefix_count": 5, "limit": 1, "offset": 1},
    )

    assert response.status_code == 200
    assert provider.calls == 1
    payload = cast(dict[str, Any], response.json())
    assert payload["strategy"]["strategy_id"] == "base"
    assert payload["strategy"]["strategy_version"] == "v1"
    assert payload["strategy"]["replicate"] == 1
    assert payload["total_count"] == 2
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert type(item["target"]["draw_number"]) is int
    assert item["target"]["draw_number"] == 10
    assert item["included_ticket_positions"] == [1, 2, 3, 4, 5]
    assert set(item) == {field.name for field in fields(HistoricalPerDrawPrefixMetrics)}
    assert set(item["target"]) == {field.name for field in fields(HistoricalDrawIdentity)}
    assert set(item["cutoff"]) == {field.name for field in fields(HistoricalDrawIdentity)}


def test_replay_zero_item_page_is_200_with_complete_exact_identity() -> None:
    client, provider = _client()

    response = client.get(
        _replay_path("zero"),
        params={"prefix_count": 20},
    )

    assert response.status_code == 200
    assert provider.calls == 1
    payload = response.json()
    assert payload["strategy"]["strategy_id"] == "zero"
    assert payload["strategy"]["governance_status"] == "REJECTED"
    assert payload["items"] == []
    assert payload["total_count"] == 0


def test_replay_never_substitutes_effective_id_or_drops_replicate() -> None:
    client, provider = _client()

    alias = client.get(_replay_path("alias"), params={"prefix_count": 1})
    replicate = client.get(_replay_path(replicate=2), params={"prefix_count": 1})

    assert alias.status_code == replicate.status_code == 200
    assert alias.json()["strategy"]["strategy_id"] == "alias"
    assert alias.json()["strategy"]["effective_strategy_id"] == "base"
    assert all(item["identity"]["strategy_id"] == "alias" for item in alias.json()["items"])
    assert replicate.json()["strategy"]["replicate"] == 2
    assert all(item["identity"]["replicate"] == 2 for item in replicate.json()["items"])
    assert provider.calls == 2


@pytest.mark.parametrize(
    ("path", "params"),
    [
        (RANKINGS_PATH, {"top_k": 0}),
        (RANKINGS_PATH, {"top_k": 101}),
        (OVERVIEW_PATH, {}),
        (OVERVIEW_PATH, {"prefix_count": 5}),
        (_replay_path("%20"), {"prefix_count": 1}),
        (_replay_path(strategy_version="%20"), {"prefix_count": 1}),
        (_replay_path(replicate=0), {"prefix_count": 1}),
        (_replay_path(), {"prefix_count": 6}),
        (_replay_path(), {"prefix_count": 1, "limit": 0}),
        (_replay_path(), {"prefix_count": 1, "limit": 201}),
        (_replay_path(), {"prefix_count": 1, "offset": -1}),
    ],
)
def test_invalid_input_is_sanitized_422_before_provider(
    path: str, params: dict[str, int]
) -> None:
    client, provider = _client()

    response = client.get(path, params=params)

    assert response.status_code == 422
    assert response.json()["error_code"] == "REQUEST_VALIDATION_FAILED"
    assert provider.calls == 0


def test_missing_exact_strategy_is_sanitized_404_without_effective_id_fallback() -> None:
    client, provider = _client()

    missing_alias = client.get(
        _replay_path("base", "v2", 1),
        params={"prefix_count": 1},
    )

    assert missing_alias.status_code == 404
    assert missing_alias.json() == {
        "error_code": "HISTORICAL_PREFIX_STRATEGY_NOT_FOUND",
        "message": "Historical prefix strategy was not found.",
    }
    assert provider.calls == 1


@pytest.mark.parametrize("path", [RANKINGS_PATH, OVERVIEW_PATH, _replay_path()])
def test_missing_provider_returns_sanitized_503(path: str) -> None:
    params = {"prefix_count": 10} if path != RANKINGS_PATH else {}

    response = TestClient(create_app()).get(path, params=params)

    assert response.status_code == 503
    assert response.json() == {
        "error_code": "HISTORICAL_PREFIX_ANALYTICS_NOT_CONFIGURED",
        "message": "Historical prefix analytics is not configured.",
    }


@pytest.mark.parametrize("failure_mode", ["provider", "source"])
def test_provider_failure_or_source_mismatch_returns_sanitized_503(
    failure_mode: str,
) -> None:
    private_detail = "private artifact path /tmp/historical-prefix-secret.json"
    if failure_mode == "provider":
        provider = _Provider(_rich_result(), failure=private_detail)
    else:
        provider = _Provider(replace(_rich_result(), result_schema_version=private_detail))
    client = TestClient(
        create_app(historical_prefix_analytics_result_provider=provider)
    )

    response = client.get(RANKINGS_PATH)

    assert response.status_code == 503
    assert response.json() == {
        "error_code": "HISTORICAL_PREFIX_ANALYTICS_UNAVAILABLE",
        "message": "Historical prefix analytics is unavailable.",
    }
    assert private_detail not in response.text
    assert provider.calls == 1


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_routes_are_get_only(method: str) -> None:
    client, provider = _client()

    response = client.request(method, RANKINGS_PATH)

    assert response.status_code == 405
    assert provider.calls == 0


def test_openapi_pins_parameter_locations_requiredness_and_sanitized_errors() -> None:
    paths = create_app().openapi()["paths"]
    replay = paths[
        "/api/v1/historical-prefix-analytics/strategies/"
        "{strategy_id}/{strategy_version}/{replicate}/replay"
    ]["get"]

    assert replay["operationId"] == "listHistoricalPrefixStrategyReplay"
    parameters = {parameter["name"]: parameter for parameter in replay["parameters"]}
    for name in ("strategy_id", "strategy_version", "replicate"):
        assert parameters[name]["in"] == "path"
        assert parameters[name]["required"] is True
    assert parameters["prefix_count"]["in"] == "query"
    assert parameters["prefix_count"]["required"] is True
    assert parameters["limit"]["required"] is False
    assert parameters["offset"]["required"] is False
    assert set(replay["responses"]) == {"200", "404", "422", "503"}
