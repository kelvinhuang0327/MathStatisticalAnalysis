"""Lazy infrastructure adapter for a bounded JSON draw-data provider."""

from __future__ import annotations

import json
from datetime import date
from typing import cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from lottolab.application.draw_automation import (
    DrawProviderContractError,
    DrawProviderUnavailableError,
    ProviderDrawRecord,
    ProviderFetchResult,
)
from lottolab.domain.draws import LotteryType

MAX_PROVIDER_RESPONSE_BYTES = 2 * 1024 * 1024
PROVIDER_TIMEOUT_SECONDS = 15


class JsonHttpDrawDataProvider:
    """Fetch a caller-bounded range from one explicitly configured HTTPS endpoint.

    The adapter performs no work during construction. The configured endpoint
    owns the JSON transport contract; browser code never receives its URL.
    """

    def __init__(
        self,
        endpoint: str,
        *,
        provider_id: str = "CONFIGURED_JSON_PROVIDER",
        provider_version: str = "lottolab-provider-json-v1",
    ) -> None:
        parsed = urlparse(endpoint)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("draw provider endpoint must be an absolute credential-free HTTPS URL")
        if parsed.fragment:
            raise ValueError("draw provider endpoint must not contain a fragment")
        self._endpoint = endpoint
        self._provider_id = _required_text(provider_id, "provider_id")
        self._provider_version = _required_text(provider_version, "provider_version")

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def provider_version(self) -> str:
        return self._provider_version

    def fetch_draws(
        self,
        *,
        lottery_type: LotteryType,
        date_from: date,
        date_to: date,
    ) -> ProviderFetchResult:
        separator = "&" if "?" in self._endpoint else "?"
        query = urlencode(
            {
                "lottery_type": lottery_type.value,
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
            }
        )
        request = Request(
            f"{self._endpoint}{separator}{query}",
            headers={"Accept": "application/json", "User-Agent": "LottoLab/0.1"},
            method="GET",
        )
        try:
            with urlopen(request, timeout=PROVIDER_TIMEOUT_SECONDS) as response:
                content_type = response.headers.get_content_type()
                if content_type != "application/json":
                    raise DrawProviderContractError("provider response is not JSON")
                body = response.read(MAX_PROVIDER_RESPONSE_BYTES + 1)
        except DrawProviderContractError:
            raise
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise DrawProviderUnavailableError("configured draw provider is unavailable") from exc
        if len(body) > MAX_PROVIDER_RESPONSE_BYTES:
            raise DrawProviderContractError("provider response exceeds the bounded size limit")
        try:
            payload: object = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DrawProviderContractError("provider response is not valid UTF-8 JSON") from exc
        return ProviderFetchResult(
            provider_id=self._provider_id,
            provider_version=self._provider_version,
            records=_records(payload),
        )


def _records(payload: object) -> tuple[ProviderDrawRecord, ...]:
    if not isinstance(payload, dict):
        raise DrawProviderContractError("provider payload must contain only draws")
    mapping = cast(dict[object, object], payload)
    if set(mapping) != {"draws"}:
        raise DrawProviderContractError("provider payload must contain only draws")
    raw_draws = mapping["draws"]
    if not isinstance(raw_draws, list):
        raise DrawProviderContractError("provider draws must be a list")
    return tuple(_record(item) for item in cast(list[object], raw_draws))


def _record(value: object) -> ProviderDrawRecord:
    if not isinstance(value, dict):
        raise DrawProviderContractError("provider draw must be an object")
    mapping = cast(dict[object, object], value)
    required = {
        "lottery_type",
        "draw_number",
        "draw_date",
        "main_numbers",
        "special_numbers",
    }
    if not required <= set(mapping) or not set(mapping) <= required | {"source_reference"}:
        raise DrawProviderContractError("provider draw fields do not match the contract")
    try:
        lottery_type = LotteryType(_required_text(mapping["lottery_type"], "lottery_type"))
        draw_date = date.fromisoformat(_required_text(mapping["draw_date"], "draw_date"))
    except ValueError as exc:
        raise DrawProviderContractError("provider draw identity is invalid") from exc
    return ProviderDrawRecord(
        lottery_type=lottery_type,
        draw_number=_required_text(mapping["draw_number"], "draw_number"),
        draw_date=draw_date,
        main_numbers=_numbers(mapping["main_numbers"], "main_numbers"),
        special_numbers=_numbers(mapping["special_numbers"], "special_numbers"),
        source_reference=(
            None
            if mapping.get("source_reference") is None
            else _required_text(mapping["source_reference"], "source_reference")
        ),
    )


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 255:
        raise DrawProviderContractError(f"provider {label} is invalid")
    if any(ord(character) < 32 for character in value):
        raise DrawProviderContractError(f"provider {label} is invalid")
    return value


def _numbers(value: object, label: str) -> tuple[int, ...]:
    if not isinstance(value, list):
        raise DrawProviderContractError(f"provider {label} is invalid")
    items = cast(list[object], value)
    if any(type(item) is not int for item in items):
        raise DrawProviderContractError(f"provider {label} is invalid")
    return tuple(cast(int, item) for item in items)


__all__ = ["JsonHttpDrawDataProvider"]
