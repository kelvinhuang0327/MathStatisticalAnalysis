"""Bounded official Taiwan Lottery B649 schedule provider.

The provider owns the network boundary and the response parser.  It returns
only explicit future identities present in the official ``NextDrawDate``
response; it never derives a draw number or manufactures a missing draw.
"""

from __future__ import annotations

import hashlib
import json
import re
import ssl
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, time
from typing import cast
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from lottolab.application.schedule_sync import (
    OfficialScheduleContractError,
    OfficialScheduleFetchResult,
    OfficialScheduleUnavailableError,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.pre_outcome_target import TargetAnnouncement, TargetSourceProvenance
from lottolab.domain.prospective_observer import ObservationTarget
from lottolab.infrastructure.persistence.future_draw_identity_repository import (
    OFFICIAL_SCHEDULE_SOURCE_ID,
    OFFICIAL_SCHEDULE_SOURCE_VERSION,
    SCHEDULE_TIMEZONE,
)

SCHEDULE_URL = "https://api.taiwanlottery.com/TLCAPIWeB/Lottery/NextDrawDate"
SCHEDULE_GAME_CODE = 5118
SCHEDULE_MAX_RESPONSE_BYTES = 1024 * 1024
SCHEDULE_MAX_ANNOUNCEMENTS = 1024
HTTPS_TIMEOUT_SECONDS = 15.0
TAIPEI = ZoneInfo(SCHEDULE_TIMEZONE)
SCHEDULED_DRAW_LOCAL_TIME = time(hour=20, minute=30)

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "LottoLab/0.1 (+schedule-sync)",
    "Origin": "https://www.taiwanlottery.com",
    "Referer": "https://www.taiwanlottery.com/",
}

_OFFICIAL_HTTPS_HOSTS = frozenset(
    {"api.taiwanlottery.com", "www.taiwanlottery.com"}
)
_DRAW_NUMBER = re.compile(r"[0-9]{1,32}", flags=re.ASCII)
_STRICT_CHAIN_MARKERS = (
    "authority key identifier",
    "subject key identifier",
    "basic constraints",
    "key usage extension",
)
_NON_STRICT_CERT_MARKERS = ("hostname", "expired", "not yet valid")

HttpsTransport = Callable[[Request, ssl.SSLContext, float, int], bytes]


class OfficialHttpsClient:
    """Credential-free official-host HTTPS GET with one narrow TLS retry."""

    def __init__(
        self,
        *,
        transport: HttpsTransport | None = None,
        timeout_seconds: float = HTTPS_TIMEOUT_SECONDS,
    ) -> None:
        self._transport = _default_https_transport if transport is None else transport
        self._timeout_seconds = timeout_seconds
        self.strict_tls_fallback_used = False

    def get(
        self,
        url: str,
        *,
        max_response_bytes: int,
        headers: Mapping[str, str] | None = None,
    ) -> bytes:
        _validate_official_https_url(url)
        if type(max_response_bytes) is not int or max_response_bytes <= 0:
            raise OfficialScheduleContractError("response size limit must be positive")
        request = Request(
            url,
            headers=dict(HEADERS if headers is None else headers),
            method="GET",
        )
        context = ssl.create_default_context()
        _require_secure_tls_context(context)
        try:
            body = self._transport(
                request,
                context,
                self._timeout_seconds,
                max_response_bytes,
            )
        except (ssl.SSLCertVerificationError, URLError) as exc:
            verification_error = _certificate_verification_error(exc)
            strict_flag = getattr(ssl, "VERIFY_X509_STRICT", 0)
            if (
                verification_error is None
                or not strict_flag
                or not context.verify_flags & strict_flag
                or not _is_strict_chain_error(verification_error)
            ):
                raise
            fallback = ssl.create_default_context()
            fallback.verify_flags &= ~strict_flag
            _require_secure_tls_context(fallback)
            self.strict_tls_fallback_used = True
            body = self._transport(
                request,
                fallback,
                self._timeout_seconds,
                max_response_bytes,
            )
        if type(body) is not bytes:
            raise OfficialScheduleContractError("official HTTPS transport must return bytes")
        if len(body) > max_response_bytes:
            raise OfficialScheduleContractError(
                "official HTTPS response exceeds the bounded size limit"
            )
        return body


class TaiwanLotteryScheduleProvider:
    """Fetch the official bounded B649 next-draw schedule."""

    def __init__(
        self,
        *,
        https_client: OfficialHttpsClient | None = None,
        source_url: str = SCHEDULE_URL,
    ) -> None:
        _validate_official_https_url(source_url)
        self._https = OfficialHttpsClient() if https_client is None else https_client
        self._source_url = source_url

    @property
    def provider_id(self) -> str:
        return OFFICIAL_SCHEDULE_SOURCE_ID

    @property
    def provider_version(self) -> str:
        return OFFICIAL_SCHEDULE_SOURCE_VERSION

    def fetch_schedule(self, *, observed_at: datetime) -> OfficialScheduleFetchResult:
        observed_utc = _as_utc(observed_at)
        try:
            body = self._https.get(
                self._source_url,
                max_response_bytes=SCHEDULE_MAX_RESPONSE_BYTES,
            )
            announcements = parse_official_b649_schedule(
                body,
                observed_at=observed_utc,
                source_url=self._source_url,
            )
        except OfficialScheduleUnavailableError:
            raise
        except OfficialScheduleContractError:
            raise
        except (URLError, TimeoutError, OSError, ssl.SSLError) as exc:
            raise OfficialScheduleUnavailableError(
                "official Taiwan Lottery schedule is unavailable"
            ) from exc
        except Exception as exc:
            raise OfficialScheduleUnavailableError(
                "official Taiwan Lottery schedule is unavailable"
            ) from exc
        return OfficialScheduleFetchResult(
            provider_id=self.provider_id,
            provider_version=self.provider_version,
            source_url=self._source_url,
            source_payload_sha256=hashlib.sha256(body).hexdigest(),
            observed_at=observed_utc,
            announcements=announcements,
        )


def parse_official_b649_schedule(
    body: bytes,
    *,
    observed_at: datetime,
    source_url: str = SCHEDULE_URL,
) -> tuple[TargetAnnouncement, ...]:
    """Validate the official response and return its explicit future B649 rows."""

    observed_utc = _as_utc(observed_at)
    _validate_official_https_url(source_url)
    if type(body) is not bytes:
        raise OfficialScheduleContractError("official schedule response must be bytes")
    if len(body) > SCHEDULE_MAX_RESPONSE_BYTES:
        raise OfficialScheduleContractError(
            "official schedule response exceeds the bounded size limit"
        )
    try:
        decoded: object = json.loads(
            body.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_json_members,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OfficialScheduleUnavailableError(
            "official schedule response is not valid UTF-8 JSON"
        ) from exc
    if not isinstance(decoded, dict):
        raise OfficialScheduleUnavailableError("official schedule response must be an object")
    payload = cast(dict[str, object], decoded)
    if type(payload.get("rtCode")) is not int or payload.get("rtCode") != 0:
        raise OfficialScheduleUnavailableError("official schedule response reported an error")
    content = payload.get("content")
    if not isinstance(content, dict):
        raise OfficialScheduleUnavailableError("official schedule content is missing")
    rows_value = cast(dict[str, object], content).get("nextDrawDateList")
    if not isinstance(rows_value, list):
        raise OfficialScheduleUnavailableError("official schedule target list is missing")
    rows = cast(list[object], rows_value)
    if len(rows) > SCHEDULE_MAX_ANNOUNCEMENTS:
        raise OfficialScheduleContractError(
            "official schedule target list exceeds the bounded item limit"
        )

    payload_sha256 = hashlib.sha256(body).hexdigest()
    announcements: list[TargetAnnouncement] = []
    identities: set[str] = set()
    for raw in rows:
        if not isinstance(raw, dict):
            raise OfficialScheduleUnavailableError("official schedule row must be an object")
        row = cast(dict[str, object], raw)
        if type(row.get("gameCode")) is not int or row.get("gameCode") != SCHEDULE_GAME_CODE:
            continue
        draw_number_value = row.get("drawTerm")
        if type(draw_number_value) not in {int, str}:
            raise OfficialScheduleUnavailableError("B649 drawTerm is unavailable")
        draw_number = str(draw_number_value)
        if _DRAW_NUMBER.fullmatch(draw_number) is None:
            raise OfficialScheduleUnavailableError("B649 drawTerm is not canonical")
        draw_date_value = row.get("drawDate")
        if type(draw_date_value) is not str or not re.fullmatch(
            r"[0-9]{8}", draw_date_value, flags=re.ASCII
        ):
            raise OfficialScheduleUnavailableError("B649 drawDate is not canonical")
        try:
            draw_date = datetime.strptime(draw_date_value, "%Y%m%d").date()
        except ValueError as exc:
            raise OfficialScheduleUnavailableError("B649 drawDate is invalid") from exc
        scheduled_at = datetime.combine(
            draw_date,
            SCHEDULED_DRAW_LOCAL_TIME,
            tzinfo=TAIPEI,
        ).astimezone(UTC)
        if scheduled_at <= observed_utc:
            continue
        if draw_number in identities:
            raise OfficialScheduleUnavailableError("official B649 target is duplicated")
        identities.add(draw_number)
        announcements.append(
            TargetAnnouncement(
                target=ObservationTarget(
                    lottery_type=LotteryType.BIG_LOTTO,
                    draw_number=draw_number,
                    draw_date=draw_date,
                ),
                schedule_timezone=SCHEDULE_TIMEZONE,
                scheduled_at=scheduled_at,
                source=TargetSourceProvenance(
                    source_id=OFFICIAL_SCHEDULE_SOURCE_ID,
                    source_version=OFFICIAL_SCHEDULE_SOURCE_VERSION,
                    source_locator=source_url,
                    source_sha256=payload_sha256,
                    observed_at=observed_utc,
                ),
            )
        )
    if not announcements:
        raise OfficialScheduleUnavailableError("official schedule has no future B649 target")
    return tuple(sorted(announcements, key=_announcement_sort_key))


def _reject_duplicate_json_members(pairs: list[tuple[str, object]]) -> dict[str, object]:
    mapping: dict[str, object] = {}
    for key, value in pairs:
        if key in mapping:
            raise OfficialScheduleContractError(
                "official schedule response contains duplicate JSON members"
            )
        mapping[key] = value
    return mapping


def _validate_official_https_url(url: str) -> None:
    if type(url) is not str:
        raise OfficialScheduleContractError(
            "official network access must use a credential-free approved HTTPS host"
        )
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise OfficialScheduleContractError(
            "official network access must use a credential-free approved HTTPS host"
        ) from exc
    if (
        not url
        or len(url) > 2048
        or parsed.scheme != "https"
        or parsed.hostname not in _OFFICIAL_HTTPS_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.fragment
    ):
        raise OfficialScheduleContractError(
            "official network access must use a credential-free approved HTTPS host"
        )


def _default_https_transport(
    request: Request,
    context: ssl.SSLContext,
    timeout_seconds: float,
    max_response_bytes: int,
) -> bytes:
    with urlopen(request, timeout=timeout_seconds, context=context) as response:
        body = response.read(max_response_bytes + 1)
    if len(body) > max_response_bytes:
        raise OfficialScheduleContractError(
            "official HTTPS response exceeds the bounded size limit"
        )
    return body


def _require_secure_tls_context(context: ssl.SSLContext) -> None:
    if context.verify_mode is not ssl.CERT_REQUIRED or not context.check_hostname:
        raise OfficialScheduleContractError(
            "TLS certificate and hostname verification must remain enabled"
        )


def _certificate_verification_error(
    exc: ssl.SSLCertVerificationError | URLError,
) -> ssl.SSLCertVerificationError | None:
    if isinstance(exc, ssl.SSLCertVerificationError):
        return exc
    return exc.reason if isinstance(exc.reason, ssl.SSLCertVerificationError) else None


def _is_strict_chain_error(exc: ssl.SSLCertVerificationError) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in _STRICT_CHAIN_MARKERS) and not any(
        marker in message for marker in _NON_STRICT_CERT_MARKERS
    )


def _announcement_sort_key(
    announcement: TargetAnnouncement,
) -> tuple[datetime, int, str]:
    return (
        announcement.scheduled_at,
        int(announcement.target.draw_number),
        announcement.target.draw_number,
    )


def _as_utc(value: datetime) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
    return value.astimezone(UTC)


__all__ = [
    "HEADERS",
    "HTTPS_TIMEOUT_SECONDS",
    "SCHEDULED_DRAW_LOCAL_TIME",
    "SCHEDULE_GAME_CODE",
    "SCHEDULE_MAX_ANNOUNCEMENTS",
    "SCHEDULE_MAX_RESPONSE_BYTES",
    "SCHEDULE_URL",
    "OfficialHttpsClient",
    "TaiwanLotteryScheduleProvider",
    "parse_official_b649_schedule",
]
