"""Map the validated Taiwan Lottery schedule Provider record to Native fields.

This is a task-local candidate. Its OFFICIAL_AUTHORITY evidence label is
deliberately incompatible with the current Native candidate's SYNTHETIC-only
gate; this module does not enable or invoke that runtime.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from lottolab.application.future_draw_identity import normalized_announcement_sha256
from lottolab.application.schedule_sync import OfficialScheduleFetchResult
from lottolab.domain.draws import LotteryType
from lottolab.domain.pre_outcome_target import TargetAnnouncement, TargetSourceProvenance
from lottolab.domain.prospective_observer import ObservationTarget
from lottolab.infrastructure.taiwan_lottery_schedule_provider import (
    OfficialScheduleContractError,
    OfficialScheduleUnavailableError,
    TaiwanLotteryScheduleProvider,
)

EXPECTED_PROVIDER_ID = "TAIWAN_LOTTERY_OFFICIAL_SCHEDULE"
EXPECTED_PROVIDER_VERSION = "taiwan-lottery-official-schedule-v1"
EXPECTED_SOURCE_URL = "https://api.taiwanlottery.com/TLCAPIWeB/Lottery/NextDrawDate"
EXPECTED_TIMEZONE = "Asia/Taipei"
_TAIPEI = ZoneInfo(EXPECTED_TIMEZONE)
_DRAW_NUMBER = re.compile(r"[0-9]{1,32}", flags=re.ASCII)
_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)


class ScheduleAuthorityMappingError(ValueError):
    """The Provider result cannot establish one unambiguous Native binding."""


def _aware_utc(value: Any, label: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ScheduleAuthorityMappingError(f"{label} must be timezone-aware")
    return value.astimezone(UTC)


def _required_attr(value: Any, name: str, label: str) -> Any:
    try:
        result = getattr(value, name)
    except AttributeError as exc:
        raise ScheduleAuthorityMappingError(f"{label} is missing {name}") from exc
    if result is None:
        raise ScheduleAuthorityMappingError(f"{label} is missing {name}")
    return result


def _binding_identity_sha256(binding: dict[str, object]) -> str:
    encoded = json.dumps(
        binding,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def map_official_schedule(
    provider: TaiwanLotteryScheduleProvider,
    *,
    as_of: datetime,
) -> tuple[dict[str, object], ...]:
    """Fetch through the named Provider and map explicit B649 announcements.

    Callers cannot establish official admission with a self-built result or
    JSON label: the exact pinned Provider instance must perform the fetch and
    parse. ``as_of`` is the scheduler decision time. No target identity is
    derived from dates, sequence arithmetic, or outcome data.
    """

    if type(provider) is not TaiwanLotteryScheduleProvider:
        raise ScheduleAuthorityMappingError("input must be the named Taiwan Lottery Provider")
    decision_at = _aware_utc(as_of, "as_of")
    try:
        result = provider.fetch_schedule(observed_at=decision_at)
    except (OfficialScheduleContractError, OfficialScheduleUnavailableError) as exc:
        raise ScheduleAuthorityMappingError(
            "the official Provider did not validate a schedule"
        ) from exc
    if type(result) is not OfficialScheduleFetchResult:
        raise ScheduleAuthorityMappingError("Provider did not return OfficialScheduleFetchResult")

    provider_id = _required_attr(result, "provider_id", "Provider result")
    provider_version = _required_attr(result, "provider_version", "Provider result")
    source_url = _required_attr(result, "source_url", "Provider result")
    payload_sha256 = _required_attr(result, "source_payload_sha256", "Provider result")
    observed_at = _aware_utc(
        _required_attr(result, "observed_at", "Provider result"),
        "Provider observed_at",
    )
    announcements = _required_attr(result, "announcements", "Provider result")

    if provider_id != EXPECTED_PROVIDER_ID:
        raise ScheduleAuthorityMappingError("Provider identity does not match official authority")
    if provider_version != EXPECTED_PROVIDER_VERSION:
        raise ScheduleAuthorityMappingError("Provider version does not match official authority")
    if source_url != EXPECTED_SOURCE_URL:
        raise ScheduleAuthorityMappingError("Provider URL does not match official endpoint")
    if type(payload_sha256) is not str or _SHA256.fullmatch(payload_sha256) is None:
        raise ScheduleAuthorityMappingError("Provider source digest is missing or invalid")
    if observed_at != decision_at:
        raise ScheduleAuthorityMappingError("Provider observation does not match the decision time")
    if type(announcements) is not tuple or not announcements:
        raise ScheduleAuthorityMappingError("Provider announcements must be a non-empty tuple")

    mapped: list[dict[str, object]] = []
    seen: dict[tuple[str, str], dict[str, object]] = {}
    for index, announcement in enumerate(announcements):
        label = f"announcement[{index}]"
        if type(announcement) is not TargetAnnouncement:
            raise ScheduleAuthorityMappingError(f"{label} must be a TargetAnnouncement")

        target = _required_attr(announcement, "target", label)
        if type(target) is not ObservationTarget:
            raise ScheduleAuthorityMappingError(f"{label}.target must be an ObservationTarget")
        lottery_type = _required_attr(target, "lottery_type", f"{label}.target")
        draw_number = _required_attr(target, "draw_number", f"{label}.target")
        draw_date = _required_attr(target, "draw_date", f"{label}.target")
        if lottery_type is not LotteryType.BIG_LOTTO:
            raise ScheduleAuthorityMappingError(f"{label} is not an explicit BIG_LOTTO target")
        if type(draw_number) is not str or _DRAW_NUMBER.fullmatch(draw_number) is None:
            raise ScheduleAuthorityMappingError(f"{label} draw number is not canonical")
        if type(draw_date) is not date:
            raise ScheduleAuthorityMappingError(f"{label} draw date is missing or invalid")

        timezone = _required_attr(announcement, "schedule_timezone", label)
        if timezone != EXPECTED_TIMEZONE:
            raise ScheduleAuthorityMappingError(f"{label} timezone is not {EXPECTED_TIMEZONE}")
        scheduled_at = _aware_utc(
            _required_attr(announcement, "scheduled_at", label),
            f"{label}.scheduled_at",
        )
        if scheduled_at <= decision_at:
            raise ScheduleAuthorityMappingError(f"{label} schedule has expired")
        if scheduled_at.astimezone(_TAIPEI).date() != draw_date:
            raise ScheduleAuthorityMappingError(f"{label} draw date conflicts with scheduled time")

        source = _required_attr(announcement, "source", label)
        if type(source) is not TargetSourceProvenance:
            raise ScheduleAuthorityMappingError(f"{label}.source must be TargetSourceProvenance")
        source_fields = {
            "source_id": _required_attr(source, "source_id", f"{label}.source"),
            "source_version": _required_attr(source, "source_version", f"{label}.source"),
            "source_locator": _required_attr(source, "source_locator", f"{label}.source"),
            "source_sha256": _required_attr(source, "source_sha256", f"{label}.source"),
            "observed_at": _aware_utc(
                _required_attr(source, "observed_at", f"{label}.source"),
                f"{label}.source.observed_at",
            ),
        }
        if (
            source_fields["source_id"] != provider_id
            or source_fields["source_version"] != provider_version
            or source_fields["source_locator"] != source_url
            or source_fields["source_sha256"] != payload_sha256
            or source_fields["observed_at"] != observed_at
        ):
            raise ScheduleAuthorityMappingError(
                f"{label} source provenance conflicts with the Provider response"
            )
        normalized_sha256 = normalized_announcement_sha256(announcement)
        if normalized_sha256 == payload_sha256:
            raise ScheduleAuthorityMappingError(
                f"{label} normalized schedule identity conflicts with the source digest"
            )

        target_key = (lottery_type.value, draw_number)
        identity = {
            "lottery_type": lottery_type.value,
            "target_draw_number": draw_number,
            "target_draw_date": draw_date.isoformat(),
            "scheduled_at": scheduled_at.astimezone(_TAIPEI).isoformat(timespec="seconds"),
            "timezone": timezone,
        }
        previous = seen.get(target_key)
        if previous is not None:
            if previous != identity:
                raise ScheduleAuthorityMappingError(
                    f"conflicting duplicate target {lottery_type.value}/{draw_number}"
                )
            raise ScheduleAuthorityMappingError(
                f"duplicate target {lottery_type.value}/{draw_number}"
            )
        seen[target_key] = identity

        binding: dict[str, object] = {
            "evidence_label": "OFFICIAL_AUTHORITY",
            "authority_name": provider_id,
            "provider_version": provider_version,
            "source_url": source_url,
            "source_payload_sha256": payload_sha256,
            "normalized_announcement_sha256": normalized_sha256,
            "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
            **identity,
            # Existing Native consumer binds this field to the normalized
            # TargetAnnouncement identity, not to the raw response digest.
            "schedule_authority_sha256": normalized_sha256,
        }
        binding["binding_identity_sha256"] = _binding_identity_sha256(binding)
        mapped.append(binding)

    return tuple(mapped)


def validate_official_schedule_binding(binding: dict[str, object]) -> None:
    """Check the mapper's normalized binding before Scheduler admission."""

    if type(binding) is not dict:
        raise ScheduleAuthorityMappingError("official schedule binding must be a dictionary")
    expected_keys = {
        "evidence_label",
        "authority_name",
        "provider_version",
        "source_url",
        "source_payload_sha256",
        "normalized_announcement_sha256",
        "observed_at",
        "lottery_type",
        "target_draw_number",
        "target_draw_date",
        "scheduled_at",
        "timezone",
        "schedule_authority_sha256",
        "binding_identity_sha256",
    }
    if set(binding) != expected_keys:
        raise ScheduleAuthorityMappingError("official schedule binding fields do not match")
    if (
        binding["evidence_label"] != "OFFICIAL_AUTHORITY"
        or binding["authority_name"] != EXPECTED_PROVIDER_ID
        or binding["provider_version"] != EXPECTED_PROVIDER_VERSION
        or binding["source_url"] != EXPECTED_SOURCE_URL
        or binding["lottery_type"] != LotteryType.BIG_LOTTO.value
        or binding["timezone"] != EXPECTED_TIMEZONE
    ):
        raise ScheduleAuthorityMappingError("official schedule binding identity does not match")

    source_sha256 = binding["source_payload_sha256"]
    normalized_sha256 = binding["normalized_announcement_sha256"]
    if type(source_sha256) is not str or _SHA256.fullmatch(source_sha256) is None:
        raise ScheduleAuthorityMappingError("source payload digest is invalid")
    if type(normalized_sha256) is not str or _SHA256.fullmatch(normalized_sha256) is None:
        raise ScheduleAuthorityMappingError("normalized announcement digest is invalid")
    if binding["schedule_authority_sha256"] != normalized_sha256:
        raise ScheduleAuthorityMappingError("schedule authority digest is not normalized digest")

    draw_number = binding["target_draw_number"]
    draw_date = binding["target_draw_date"]
    scheduled_at_text = binding["scheduled_at"]
    observed_at_text = binding["observed_at"]
    if type(draw_number) is not str or _DRAW_NUMBER.fullmatch(draw_number) is None:
        raise ScheduleAuthorityMappingError("target draw number is invalid")
    if type(draw_date) is not str:
        raise ScheduleAuthorityMappingError("target draw date is invalid")
    try:
        parsed_date = date.fromisoformat(draw_date)
        scheduled_at = _aware_utc(datetime.fromisoformat(str(scheduled_at_text)), "scheduled_at")
        observed_at = _aware_utc(
            datetime.fromisoformat(str(observed_at_text).replace("Z", "+00:00")),
            "observed_at",
        )
    except (TypeError, ValueError) as exc:
        raise ScheduleAuthorityMappingError("schedule binding time fields are invalid") from exc
    if (
        parsed_date.isoformat() != draw_date
        or scheduled_at.astimezone(_TAIPEI).date() != parsed_date
    ):
        raise ScheduleAuthorityMappingError("target date conflicts with scheduled time")
    if scheduled_at <= observed_at:
        raise ScheduleAuthorityMappingError("schedule binding has expired")

    unsigned_binding = {
        key: value for key, value in binding.items() if key != "binding_identity_sha256"
    }
    expected_identity_sha256 = _binding_identity_sha256(unsigned_binding)
    identity_sha256 = binding["binding_identity_sha256"]
    if type(identity_sha256) is not str or identity_sha256 != expected_identity_sha256:
        raise ScheduleAuthorityMappingError(
            "official schedule binding content digest does not match"
        )
