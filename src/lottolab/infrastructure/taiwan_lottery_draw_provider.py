"""Official Taiwan Lottery JSON API adapter for the DrawDataProvider port.

Endpoint contract verified against the legacy donor reference at
``LotteryNewMeraged/_legacy_bruteforce_reference/RUN_20260730_134301/
filesystem_sources/LotteryNew-main/lottery_api/fetcher/taiwan_lottery_fetcher.py``
(``https://api.taiwanlottery.com/TLCAPIWeB``, one JSON endpoint per lottery
type, ``rtCode``/``content`` response envelope). Not a byte-for-byte port:
the donor client is tuned for "give me the N most recent draws" and walks
month pages backwards; this adapter serves LottoLab's bounded
``[date_from, date_to]`` contract instead, so it issues one request sized to
cover the requested calendar months and then filters rows to the exact
requested range before returning them, because ``_validate_fetch`` in
``lottolab.application.use_cases.draw_automation`` rejects any record whose
``draw_date`` falls outside that range.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import NamedTuple, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from lottolab.application.draw_automation import (
    DrawProviderContractError,
    DrawProviderUnavailableError,
    ProviderDrawRecord,
    ProviderFetchResult,
)
from lottolab.domain.draws import LotteryType

API_BASE = "https://api.taiwanlottery.com/TLCAPIWeB"
PROVIDER_ID = "TAIWAN_LOTTERY_OFFICIAL_API"
PROVIDER_VERSION = "taiwan-lottery-tlcapiweb-v1"
FETCH_TIMEOUT_SECONDS = 15
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_PAGE_SIZE = 400
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "LottoLab/0.1 (+draw-sync)",
    "Origin": "https://www.taiwanlottery.com",
    "Referer": "https://www.taiwanlottery.com/",
}


class _SourceConfig(NamedTuple):
    endpoint: str
    result_key: str
    numbers_count: int
    has_special: bool


SOURCE_CONFIG: dict[LotteryType, _SourceConfig] = {
    LotteryType.BIG_LOTTO: _SourceConfig("/Lottery/Lotto649Result", "lotto649Res", 6, True),
    LotteryType.POWER_LOTTO: _SourceConfig(
        "/Lottery/SuperLotto638Result", "superLotto638Res", 6, True
    ),
    LotteryType.DAILY_539: _SourceConfig("/Lottery/Daily539Result", "daily539Res", 5, False),
}

Transport = Callable[[str], bytes]


class TaiwanLotteryDrawProvider:
    """Fetch official draw results directly from api.taiwanlottery.com.

    The endpoint is fixed and official; unlike ``JsonHttpDrawDataProvider``
    this adapter takes no caller-supplied URL. ``transport`` is injectable
    so tests never perform a real network request.
    """

    def __init__(self, *, transport: Transport | None = None) -> None:
        self._transport = transport if transport is not None else _default_transport

    @property
    def provider_id(self) -> str:
        return PROVIDER_ID

    @property
    def provider_version(self) -> str:
        return PROVIDER_VERSION

    def fetch_draws(
        self,
        *,
        lottery_type: LotteryType,
        date_from: date,
        date_to: date,
    ) -> ProviderFetchResult:
        config = SOURCE_CONFIG.get(lottery_type)
        if config is None:
            raise DrawProviderContractError(f"unsupported lottery type: {lottery_type.value}")

        query = urlencode(
            {
                "pageNum": 1,
                "pageSize": MAX_PAGE_SIZE,
                "startMonth": f"{date_from.year:04d}-{date_from.month:02d}",
                "endMonth": f"{date_to.year:04d}-{date_to.month:02d}",
            }
        )
        url = f"{API_BASE}{config.endpoint}?{query}"

        try:
            body = self._transport(url)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise DrawProviderUnavailableError(
                "official Taiwan Lottery API is unavailable"
            ) from exc

        payload = _parse_envelope(body)
        raw_rows = payload.get(config.result_key)
        if not isinstance(raw_rows, list):
            raise DrawProviderContractError("official API response is missing the result list")

        records = tuple(
            record
            for row in cast(list[object], raw_rows)
            if (record := _record(lottery_type, config, row, date_from, date_to)) is not None
        )
        return ProviderFetchResult(
            provider_id=PROVIDER_ID,
            provider_version=PROVIDER_VERSION,
            records=records,
        )


def _default_transport(url: str) -> bytes:
    request = Request(url, headers=HEADERS, method="GET")
    with urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
        body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise DrawProviderContractError("official API response exceeds the bounded size limit")
    return body


def _parse_envelope(body: bytes) -> dict[str, object]:
    import json

    try:
        payload: object = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DrawProviderContractError("official API response is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise DrawProviderContractError("official API response must be a JSON object")
    mapping = cast(dict[str, object], payload)
    if mapping.get("rtCode") != 0:
        raise DrawProviderUnavailableError(
            f"official API reported an error: rtCode={mapping.get('rtCode')!r}"
        )
    content = mapping.get("content")
    if not isinstance(content, dict):
        raise DrawProviderContractError("official API response is missing content")
    return cast(dict[str, object], content)


def _record(
    lottery_type: LotteryType,
    config: _SourceConfig,
    row: object,
    date_from: date,
    date_to: date,
) -> ProviderDrawRecord | None:
    if not isinstance(row, dict):
        raise DrawProviderContractError("official API draw row must be an object")
    mapping = cast(dict[str, object], row)

    draw_number = _required_text(mapping.get("period"), "period")
    draw_date = _required_date(mapping.get("lotteryDate"), "lotteryDate")
    raw_numbers = mapping.get("drawNumberSize")
    if not isinstance(raw_numbers, list):
        raise DrawProviderContractError("official API drawNumberSize is invalid")
    numbers = cast(list[object], raw_numbers)
    if any(type(item) is not int for item in numbers):
        raise DrawProviderContractError("official API drawNumberSize must contain only integers")
    numbers_int = cast(list[int], numbers)
    expected_count = config.numbers_count + (1 if config.has_special else 0)
    if len(numbers_int) != expected_count:
        raise DrawProviderContractError(
            "official API drawNumberSize has an unexpected length"
        )

    main_numbers = tuple(sorted(numbers_int[: config.numbers_count]))
    special_numbers = (numbers_int[config.numbers_count],) if config.has_special else ()

    if not (date_from <= draw_date <= date_to):
        return None

    return ProviderDrawRecord(
        lottery_type=lottery_type,
        draw_number=draw_number,
        draw_date=draw_date,
        main_numbers=main_numbers,
        special_numbers=special_numbers,
        source_reference=f"taiwanlottery:{config.endpoint}:{draw_number}",
    )


def _required_text(value: object, label: str) -> str:
    if type(value) is str and value.strip():
        return value
    # The official Taiwan Lottery result API currently serializes ``period``
    # as a JSON integer.  Canonical draw identities are stored as text, so
    # normalize that provider representation at the adapter boundary.
    if type(value) is int and value >= 0:
        return str(value)
    raise DrawProviderContractError(f"official API {label} is invalid")


def _required_date(value: object, label: str) -> date:
    if not isinstance(value, str) or len(value) < 10:
        raise DrawProviderContractError(f"official API {label} is invalid")
    try:
        return date.fromisoformat(value[:10])
    except ValueError as exc:
        raise DrawProviderContractError(f"official API {label} is invalid") from exc


__all__ = ["TaiwanLotteryDrawProvider"]
