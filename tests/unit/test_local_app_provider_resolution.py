"""Acceptance tests for local_draw_provider's environment-driven resolution."""

from __future__ import annotations

from lottolab.infrastructure.draw_provider import JsonHttpDrawDataProvider
from lottolab.infrastructure.taiwan_lottery_draw_provider import TaiwanLotteryDrawProvider
from lottolab.interfaces.api.local_app import (
    DRAW_PROVIDER_SOURCE_ENV,
    DRAW_PROVIDER_URL_ENV,
    OFFICIAL_TAIWAN_LOTTERY_SOURCE,
    local_draw_provider,
)


def test_defaults_to_none_when_unconfigured() -> None:
    assert local_draw_provider({}) is None


def test_stays_none_on_unrecognized_source_value() -> None:
    assert local_draw_provider({DRAW_PROVIDER_SOURCE_ENV: "SOMETHING_ELSE"}) is None


def test_opts_into_the_official_provider() -> None:
    provider = local_draw_provider({DRAW_PROVIDER_SOURCE_ENV: OFFICIAL_TAIWAN_LOTTERY_SOURCE})
    assert isinstance(provider, TaiwanLotteryDrawProvider)


def test_explicit_url_wins_over_the_official_source_toggle() -> None:
    provider = local_draw_provider(
        {
            DRAW_PROVIDER_URL_ENV: "https://example.test/draws",
            DRAW_PROVIDER_SOURCE_ENV: OFFICIAL_TAIWAN_LOTTERY_SOURCE,
        }
    )
    assert isinstance(provider, JsonHttpDrawDataProvider)


def test_explicit_url_alone_still_resolves_the_json_provider() -> None:
    provider = local_draw_provider({DRAW_PROVIDER_URL_ENV: "https://example.test/draws"})
    assert isinstance(provider, JsonHttpDrawDataProvider)
