"""Acceptance tests for the official Taiwan Lottery draw-data provider adapter."""

from __future__ import annotations

import json
from datetime import date

import pytest

from lottolab.application.draw_automation import (
    DrawProviderContractError,
    DrawProviderUnavailableError,
)
from lottolab.domain.draws import LotteryType
from lottolab.infrastructure.taiwan_lottery_draw_provider import (
    API_BASE,
    TaiwanLotteryDrawProvider,
)


def _envelope(result_key: str, rows: list[dict[str, object]]) -> bytes:
    return json.dumps({"rtCode": 0, "rtMsg": "OK", "content": {result_key: rows}}).encode("utf-8")


def _row(period: str, iso_date: str, numbers: list[object]) -> dict[str, object]:
    return {"period": period, "lotteryDate": iso_date, "drawNumberSize": numbers}


class _FakeTransport:
    def __init__(self, response: bytes | Exception) -> None:
        self._response = response
        self.requested_urls: list[str] = []

    def __call__(self, url: str) -> bytes:
        self.requested_urls.append(url)
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def test_never_touches_the_network_by_default_construction() -> None:
    provider = TaiwanLotteryDrawProvider(transport=_FakeTransport(b"unused"))
    assert provider.provider_id
    assert provider.provider_version


def test_fetches_and_normalizes_big_lotto_draws() -> None:
    transport = _FakeTransport(
        _envelope("lotto649Res", [_row("113000060", "2026-07-16", [1, 49, 3, 24, 9, 17, 7])])
    )
    provider = TaiwanLotteryDrawProvider(transport=transport)

    result = provider.fetch_draws(
        lottery_type=LotteryType.BIG_LOTTO,
        date_from=date(2026, 7, 1),
        date_to=date(2026, 7, 31),
    )

    assert result.provider_id == "TAIWAN_LOTTERY_OFFICIAL_API"
    assert len(result.records) == 1
    record = result.records[0]
    assert record.lottery_type is LotteryType.BIG_LOTTO
    assert record.draw_number == "113000060"
    assert record.draw_date == date(2026, 7, 16)
    assert record.main_numbers == (1, 3, 9, 17, 24, 49)
    assert record.special_numbers == (7,)
    assert record.source_reference == "taiwanlottery:/Lottery/Lotto649Result:113000060"
    assert transport.requested_urls[0].startswith(f"{API_BASE}/Lottery/Lotto649Result?")
    assert "startMonth=2026-07" in transport.requested_urls[0]
    assert "endMonth=2026-07" in transport.requested_urls[0]


def test_fetches_power_lotto_from_its_own_endpoint() -> None:
    transport = _FakeTransport(
        _envelope("superLotto638Res", [_row("113000042", "2026-07-10", [2, 4, 6, 8, 10, 12, 5])])
    )
    provider = TaiwanLotteryDrawProvider(transport=transport)

    result = provider.fetch_draws(
        lottery_type=LotteryType.POWER_LOTTO,
        date_from=date(2026, 7, 1),
        date_to=date(2026, 7, 31),
    )

    assert result.records[0].lottery_type is LotteryType.POWER_LOTTO
    assert result.records[0].special_numbers == (5,)
    assert transport.requested_urls[0].startswith(f"{API_BASE}/Lottery/SuperLotto638Result?")


def test_daily_539_has_no_special_number() -> None:
    transport = _FakeTransport(
        _envelope("daily539Res", [_row("113000900", "2026-07-05", [1, 2, 3, 4, 5])])
    )
    provider = TaiwanLotteryDrawProvider(transport=transport)

    result = provider.fetch_draws(
        lottery_type=LotteryType.DAILY_539,
        date_from=date(2026, 7, 1),
        date_to=date(2026, 7, 31),
    )

    assert result.records[0].main_numbers == (1, 2, 3, 4, 5)
    assert result.records[0].special_numbers == ()
    assert transport.requested_urls[0].startswith(f"{API_BASE}/Lottery/Daily539Result?")


def test_filters_rows_outside_the_requested_range() -> None:
    transport = _FakeTransport(
        _envelope(
            "lotto649Res",
            [
                _row("113000059", "2026-06-30", [1, 3, 9, 17, 24, 49, 7]),
                _row("113000060", "2026-07-16", [1, 3, 9, 17, 24, 49, 7]),
                _row("113000061", "2026-08-01", [1, 3, 9, 17, 24, 49, 7]),
            ],
        )
    )
    provider = TaiwanLotteryDrawProvider(transport=transport)

    result = provider.fetch_draws(
        lottery_type=LotteryType.BIG_LOTTO,
        date_from=date(2026, 7, 1),
        date_to=date(2026, 7, 31),
    )

    assert [record.draw_number for record in result.records] == ["113000060"]


def test_raises_contract_error_on_non_json_body() -> None:
    provider = TaiwanLotteryDrawProvider(transport=_FakeTransport(b"not json"))

    with pytest.raises(DrawProviderContractError):
        provider.fetch_draws(
            lottery_type=LotteryType.BIG_LOTTO,
            date_from=date(2026, 7, 1),
            date_to=date(2026, 7, 31),
        )


def test_raises_unavailable_on_nonzero_rt_code() -> None:
    body = json.dumps({"rtCode": 1, "rtMsg": "maintenance", "content": {}}).encode("utf-8")
    provider = TaiwanLotteryDrawProvider(transport=_FakeTransport(body))

    with pytest.raises(DrawProviderUnavailableError):
        provider.fetch_draws(
            lottery_type=LotteryType.BIG_LOTTO,
            date_from=date(2026, 7, 1),
            date_to=date(2026, 7, 31),
        )


def test_raises_unavailable_on_transport_failure() -> None:
    provider = TaiwanLotteryDrawProvider(transport=_FakeTransport(OSError("network down")))

    with pytest.raises(DrawProviderUnavailableError):
        provider.fetch_draws(
            lottery_type=LotteryType.BIG_LOTTO,
            date_from=date(2026, 7, 1),
            date_to=date(2026, 7, 31),
        )


def test_raises_contract_error_on_missing_result_key() -> None:
    body = json.dumps({"rtCode": 0, "rtMsg": "OK", "content": {}}).encode("utf-8")
    provider = TaiwanLotteryDrawProvider(transport=_FakeTransport(body))

    with pytest.raises(DrawProviderContractError):
        provider.fetch_draws(
            lottery_type=LotteryType.BIG_LOTTO,
            date_from=date(2026, 7, 1),
            date_to=date(2026, 7, 31),
        )


def test_raises_contract_error_on_short_number_list() -> None:
    transport = _FakeTransport(
        _envelope("lotto649Res", [_row("113000060", "2026-07-16", [1, 3, 9])])
    )
    provider = TaiwanLotteryDrawProvider(transport=transport)

    with pytest.raises(DrawProviderContractError):
        provider.fetch_draws(
            lottery_type=LotteryType.BIG_LOTTO,
            date_from=date(2026, 7, 1),
            date_to=date(2026, 7, 31),
        )


def test_raises_contract_error_on_non_integer_numbers() -> None:
    transport = _FakeTransport(
        _envelope("lotto649Res", [_row("113000060", "2026-07-16", [1, 3, 9, 17, 24, "x", 7])])
    )
    provider = TaiwanLotteryDrawProvider(transport=transport)

    with pytest.raises(DrawProviderContractError):
        provider.fetch_draws(
            lottery_type=LotteryType.BIG_LOTTO,
            date_from=date(2026, 7, 1),
            date_to=date(2026, 7, 31),
        )
