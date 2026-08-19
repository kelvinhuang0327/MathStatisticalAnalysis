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

import json
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
from lottolab.application.draw_metadata import OfficialDrawMetadataRecord
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
    jackpot_assign_key: str
    # True for BIG_LOTTO/POWER_LOTTO, whose *JackpotAssign object has
    # prize/lastPrize keys confirmed (by direct live-API chain
    # reconstruction) to carry a rolling jackpot pool forward across draws
    # with no winner. False for DAILY_539: its d539JackpotAssign object has
    # only winnerCount/perPrize -- no prize/lastPrize -- so it has no
    # rollover jackpot pool to reconstruct.
    jackpot_has_pool: bool


SOURCE_CONFIG: dict[LotteryType, _SourceConfig] = {
    LotteryType.BIG_LOTTO: _SourceConfig(
        "/Lottery/Lotto649Result", "lotto649Res", 6, True, "jackpotAssign", True
    ),
    LotteryType.POWER_LOTTO: _SourceConfig(
        "/Lottery/SuperLotto638Result",
        "superLotto638Res",
        6,
        True,
        "super638JackpotAssign",
        True,
    ),
    LotteryType.DAILY_539: _SourceConfig(
        "/Lottery/Daily539Result", "daily539Res", 5, False, "d539JackpotAssign", False
    ),
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
        config, raw_rows = self._fetch_rows(lottery_type, date_from, date_to)
        records = tuple(
            record
            for row in raw_rows
            if (record := _record(lottery_type, config, row, date_from, date_to)) is not None
        )
        return ProviderFetchResult(
            provider_id=PROVIDER_ID,
            provider_version=PROVIDER_VERSION,
            records=records,
        )

    def fetch_draws_with_metadata(
        self,
        *,
        lottery_type: LotteryType,
        date_from: date,
        date_to: date,
    ) -> tuple[ProviderFetchResult, tuple[OfficialDrawMetadataRecord, ...]]:
        """Fetch the same bounded range as :meth:`fetch_draws`, plus research metadata.

        Issues exactly one request per call (no extra network round-trip vs.
        :meth:`fetch_draws`). The canonical ``ProviderFetchResult`` half is
        identical to what :meth:`fetch_draws` returns for the same arguments;
        the metadata half is additive and never feeds canonical draw
        ingestion.
        """

        config, raw_rows = self._fetch_rows(lottery_type, date_from, date_to)
        records: list[ProviderDrawRecord] = []
        metadata: list[OfficialDrawMetadataRecord] = []
        for row in raw_rows:
            record = _record(lottery_type, config, row, date_from, date_to)
            if record is None:
                continue
            records.append(record)
            metadata.append(_metadata_record(lottery_type, config, row, record))
        return (
            ProviderFetchResult(
                provider_id=PROVIDER_ID,
                provider_version=PROVIDER_VERSION,
                records=tuple(records),
            ),
            tuple(metadata),
        )

    def _fetch_rows(
        self,
        lottery_type: LotteryType,
        date_from: date,
        date_to: date,
    ) -> tuple[_SourceConfig, list[object]]:
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
        return config, cast(list[object], raw_rows)


def _default_transport(url: str) -> bytes:
    request = Request(url, headers=HEADERS, method="GET")
    with urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
        body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise DrawProviderContractError("official API response exceeds the bounded size limit")
    return body


def _parse_envelope(body: bytes) -> dict[str, object]:
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

    draw_number = _required_draw_number(mapping.get("period"), "period")
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


def _required_draw_number(value: object, label: str) -> str:
    """Accept the official API's real ``period`` shape (a JSON integer, e.g.

    ``115000079``) as well as the string form, and normalize both to text.
    ``bool`` is rejected even though it is an ``int`` subclass; ``float``,
    ``None``, and non-scalar values are rejected too.
    """

    if type(value) is int and value >= 0:
        return str(value)
    if type(value) is str and value.strip():
        return value
    raise DrawProviderContractError(f"official API {label} is invalid")


def _required_date(value: object, label: str) -> date:
    if not isinstance(value, str) or len(value) < 10:
        raise DrawProviderContractError(f"official API {label} is invalid")
    try:
        return date.fromisoformat(value[:10])
    except ValueError as exc:
        raise DrawProviderContractError(f"official API {label} is invalid") from exc


def _metadata_record(
    lottery_type: LotteryType,
    config: _SourceConfig,
    row: object,
    record: ProviderDrawRecord,
) -> OfficialDrawMetadataRecord:
    """Build the research-only metadata sidecar for a row ``_record`` already accepted.

    ``draw_number_appear`` preserves ``drawNumberAppear`` verbatim, in source
    order -- it is never sorted or renamed, unlike ``main_numbers``.
    """

    mapping = cast(dict[str, object], row)

    raw_appear = mapping.get("drawNumberAppear")
    draw_number_appear = _required_int_list(raw_appear, "drawNumberAppear")
    expected_count = config.numbers_count + (1 if config.has_special else 0)
    if len(draw_number_appear) != expected_count:
        raise DrawProviderContractError(
            "official API drawNumberAppear has an unexpected length"
        )

    winner_count, per_prize, prize, last_prize = _jackpot_tier(mapping, config)

    return OfficialDrawMetadataRecord(
        lottery_type=lottery_type,
        draw_number=record.draw_number,
        draw_date=record.draw_date,
        draw_number_appear=tuple(draw_number_appear),
        sell_amount=_optional_int(mapping.get("sellAmount")),
        total_amount=_optional_int(mapping.get("totalAmount")),
        jackpot_winner_count=winner_count,
        jackpot_per_prize=per_prize,
        jackpot_prize=prize,
        jackpot_last_prize=last_prize,
        source_reference=record.source_reference
        or f"taiwanlottery:{config.endpoint}:{record.draw_number}",
        raw_json=json.dumps(mapping, ensure_ascii=False, sort_keys=True),
    )


def _jackpot_tier(
    mapping: dict[str, object], config: _SourceConfig
) -> tuple[int | None, int | None, int | None, int | None]:
    """Parse the top prize-tier assign object named by ``config.jackpot_assign_key``.

    Returns ``(winner_count, per_prize, prize, last_prize)``. ``prize`` and
    ``last_prize`` are always ``None`` when ``config.jackpot_has_pool`` is
    ``False`` (DAILY_539's tier has no rollover pool to report), regardless
    of what the row happens to contain.
    """

    tier = mapping.get(config.jackpot_assign_key)
    if tier is None:
        return None, None, None, None
    if not isinstance(tier, dict):
        raise DrawProviderContractError(f"official API {config.jackpot_assign_key} is invalid")
    tier_mapping = cast(dict[str, object], tier)
    winner_count = _required_int(tier_mapping.get("winnerCount"), "winnerCount")
    per_prize = _required_int(tier_mapping.get("perPrize"), "perPrize")
    if not config.jackpot_has_pool:
        return winner_count, per_prize, None, None
    prize = _required_int(tier_mapping.get("prize"), "prize")
    last_prize = _required_int(tier_mapping.get("lastPrize"), "lastPrize")
    return winner_count, per_prize, prize, last_prize


def _required_int_list(value: object, label: str) -> list[int]:
    if not isinstance(value, list):
        raise DrawProviderContractError(f"official API {label} is invalid")
    items = cast(list[object], value)
    if any(type(item) is not int for item in items):
        raise DrawProviderContractError(f"official API {label} must contain only integers")
    return cast(list[int], items)


def _required_int(value: object, label: str) -> int:
    if type(value) is not int:
        raise DrawProviderContractError(f"official API {label} is invalid")
    return value


def _optional_int(value: object) -> int | None:
    return value if type(value) is int else None


__all__ = ["TaiwanLotteryDrawProvider"]
