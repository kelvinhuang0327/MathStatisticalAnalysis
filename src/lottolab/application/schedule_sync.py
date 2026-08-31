"""Application contracts for bounded official schedule synchronization."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from enum import StrEnum
from typing import Protocol
from zoneinfo import ZoneInfo

from lottolab.domain.draws import LotteryType
from lottolab.domain.ingestion import IngestionRunStatus
from lottolab.domain.pre_outcome_target import TargetAnnouncement, TargetSourceProvenance

SCHEDULE_SYNC_PARSER_VERSION = "lottolab-b649-official-schedule-json-v1"
CANONICAL_SCHEDULE_AUTHORITY_PARSER_VERSION = "lottolab-t539-p638-official-schedule-json-v1"
CANONICAL_SCHEDULE_TIMEZONE = "Asia/Taipei"
CANONICAL_NORMAL_DRAW_LOCAL_TIME = time(hour=20, minute=30)
T539_SCHEDULE_GAME_CODE = 5120
P638_SCHEDULE_GAME_CODE = 5134
SUPPORTED_CANONICAL_SCHEDULE_LOTTERIES = frozenset({LotteryType.DAILY_539, LotteryType.POWER_LOTTO})
_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)
_DRAW_NUMBER = re.compile(r"[0-9]{1,32}", flags=re.ASCII)


class OfficialScheduleSyncError(RuntimeError):
    """Base class for sanitized official schedule synchronization failures."""


class OfficialScheduleProviderError(OfficialScheduleSyncError):
    """The official schedule provider could not return a trusted response."""


class OfficialScheduleUnavailableError(OfficialScheduleProviderError):
    """The official response is unavailable or contains no usable B649 target."""


class OfficialScheduleContractError(OfficialScheduleProviderError):
    """The official response violates the bounded schedule contract."""


class ScheduleAuthorityStatus(StrEnum):
    """Per-game result of interpreting one valid shared official envelope."""

    COMPLETE = "COMPLETE"
    INCOMPLETE_AUTHORITY = "INCOMPLETE_AUTHORITY"
    MISSING_SCHEDULE = "MISSING_SCHEDULE"
    OBSERVATION_DEADLINE_EXPIRED = "OBSERVATION_DEADLINE_EXPIRED"
    SOURCE_CONFLICT = "SOURCE_CONFLICT"
    AUTHORITATIVE_VETO = "AUTHORITATIVE_VETO"


class ScheduleExceptionKind(StrEnum):
    """Typed, prevalidated exception boundary; free-form notice text is excluded."""

    CANCELLATION = "CANCELLATION"
    POSTPONEMENT = "POSTPONEMENT"
    TIME_CHANGE = "TIME_CHANGE"


class ScheduleAuthorityApplyStatus(StrEnum):
    """Canonical persistence outcome for one independently isolated game."""

    ACCEPTED = "ACCEPTED"
    NO_AUTHORITY = "NO_AUTHORITY"
    CONFLICT = "CONFLICT"
    VETOED = "VETOED"


def expected_schedule_game_code(lottery_type: LotteryType) -> int:
    """Return the frozen Taiwan Lottery schedule gameCode for T539/P638."""

    if lottery_type is LotteryType.DAILY_539:
        return T539_SCHEDULE_GAME_CODE
    if lottery_type is LotteryType.POWER_LOTTO:
        return P638_SCHEDULE_GAME_CODE
    raise ValueError("canonical schedule authority supports DAILY_539 and POWER_LOTTO")


@dataclass(frozen=True, slots=True)
class CanonicalScheduleFact:
    """One source-independent immutable T539/P638 schedule fact."""

    announcement: TargetAnnouncement
    official_game_code: int
    scheduled_local_time: time
    source_period_identifier: str | None

    def __post_init__(self) -> None:
        if type(self.announcement) is not TargetAnnouncement:
            raise ValueError("announcement must be a TargetAnnouncement")
        target = self.announcement.target
        if target.lottery_type not in SUPPORTED_CANONICAL_SCHEDULE_LOTTERIES:
            raise ValueError("canonical schedule fact supports DAILY_539 and POWER_LOTTO")
        if type(
            self.official_game_code
        ) is not int or self.official_game_code != expected_schedule_game_code(target.lottery_type):
            raise ValueError("official_game_code does not match lottery_type")
        if self.announcement.schedule_timezone != CANONICAL_SCHEDULE_TIMEZONE:
            raise ValueError(f"schedule_timezone must be {CANONICAL_SCHEDULE_TIMEZONE}")
        if (
            type(self.scheduled_local_time) is not time
            or self.scheduled_local_time.tzinfo is not None
            or self.scheduled_local_time.microsecond != 0
        ):
            raise ValueError("scheduled_local_time must be an exact naive whole-second time")
        actual_local_time = (
            self.announcement.scheduled_at.astimezone(ZoneInfo(CANONICAL_SCHEDULE_TIMEZONE))
            .time()
            .replace(tzinfo=None)
        )
        if actual_local_time != self.scheduled_local_time:
            raise ValueError("scheduled_local_time does not match scheduled_at")
        if self.source_period_identifier is not None:
            if (
                type(self.source_period_identifier) is not str
                or _DRAW_NUMBER.fullmatch(self.source_period_identifier) is None
            ):
                raise ValueError("source_period_identifier must be ASCII decimal or None")
            if self.source_period_identifier != target.draw_number:
                raise ValueError("source_period_identifier must equal canonical draw_number")

    def immutable_dict(self) -> dict[str, object]:
        """Return exactly the frozen immutable schedule fact, excluding provenance."""

        target = self.announcement.target
        return {
            "draw_date": target.draw_date.isoformat(),
            "draw_number": target.draw_number,
            "lottery_type": target.lottery_type.value,
            "official_game_code": self.official_game_code,
            "schedule_timezone": self.announcement.schedule_timezone,
            "scheduled_at": self.announcement.scheduled_at.isoformat().replace("+00:00", "Z"),
            "scheduled_local_time": self.scheduled_local_time.isoformat(timespec="seconds"),
            "source_period_identifier": self.source_period_identifier,
        }

    @property
    def immutable_schedule_sha256(self) -> str:
        encoded = json.dumps(
            self.immutable_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class AuthoritativeScheduleVeto:
    """Hash-bound typed notice already validated before provider interpretation."""

    lottery_type: LotteryType
    official_game_code: int
    draw_number: str | None
    exception_kind: ScheduleExceptionKind
    source: TargetSourceProvenance

    def __post_init__(self) -> None:
        if self.lottery_type not in SUPPORTED_CANONICAL_SCHEDULE_LOTTERIES:
            raise ValueError("schedule veto supports DAILY_539 and POWER_LOTTO")
        if type(
            self.official_game_code
        ) is not int or self.official_game_code != expected_schedule_game_code(self.lottery_type):
            raise ValueError("veto official_game_code does not match lottery_type")
        if self.draw_number is not None and (
            type(self.draw_number) is not str or _DRAW_NUMBER.fullmatch(self.draw_number) is None
        ):
            raise ValueError("veto draw_number must be ASCII decimal or None")
        if type(self.exception_kind) is not ScheduleExceptionKind:
            raise ValueError("exception_kind must be a ScheduleExceptionKind")
        if type(self.source) is not TargetSourceProvenance:
            raise ValueError("veto source must be TargetSourceProvenance")


@dataclass(frozen=True, slots=True)
class OfficialGameScheduleAuthority:
    """One game-local interpretation isolated from the other shared-envelope game."""

    lottery_type: LotteryType
    official_game_code: int
    status: ScheduleAuthorityStatus
    schedules: tuple[CanonicalScheduleFact, ...]
    detail_code: str
    evidence_draw_dates: tuple[date, ...] = ()
    vetoes: tuple[AuthoritativeScheduleVeto, ...] = ()

    def __post_init__(self) -> None:
        if self.lottery_type not in SUPPORTED_CANONICAL_SCHEDULE_LOTTERIES:
            raise ValueError("game authority supports DAILY_539 and POWER_LOTTO")
        if type(
            self.official_game_code
        ) is not int or self.official_game_code != expected_schedule_game_code(self.lottery_type):
            raise ValueError("game authority official_game_code is invalid")
        if type(self.status) is not ScheduleAuthorityStatus:
            raise ValueError("status must be a ScheduleAuthorityStatus")
        _require_text(self.detail_code, "detail_code")
        if type(self.schedules) is not tuple or any(
            type(item) is not CanonicalScheduleFact for item in self.schedules
        ):
            raise ValueError("schedules must contain CanonicalScheduleFact values")
        if any(
            item.announcement.target.lottery_type is not self.lottery_type
            or item.official_game_code != self.official_game_code
            for item in self.schedules
        ):
            raise ValueError("schedule fact does not belong to its game authority")
        keys = tuple(
            (item.announcement.target.lottery_type, item.announcement.target.draw_number)
            for item in self.schedules
        )
        if len(keys) != len(set(keys)):
            raise ValueError("game authority schedule identities must be unique")
        if type(self.evidence_draw_dates) is not tuple or any(
            type(item) is not date for item in self.evidence_draw_dates
        ):
            raise ValueError("evidence_draw_dates must contain exact dates")
        if type(self.vetoes) is not tuple or any(
            type(item) is not AuthoritativeScheduleVeto for item in self.vetoes
        ):
            raise ValueError("vetoes must contain AuthoritativeScheduleVeto values")
        if any(item.lottery_type is not self.lottery_type for item in self.vetoes):
            raise ValueError("veto does not belong to its game authority")
        if self.status is ScheduleAuthorityStatus.COMPLETE:
            if not self.schedules or self.vetoes:
                raise ValueError("complete game authority requires schedules and no veto")
        elif self.status is ScheduleAuthorityStatus.AUTHORITATIVE_VETO:
            if self.schedules or not self.vetoes:
                raise ValueError("vetoed game authority requires veto evidence only")
        elif self.schedules or self.vetoes:
            raise ValueError("non-complete game authority cannot carry schedules or vetoes")


@dataclass(frozen=True, slots=True)
class CanonicalScheduleAuthorityFetchResult:
    """One validated shared response with independently classified T539/P638 games."""

    provider_id: str
    provider_version: str
    source_url: str
    source_payload_sha256: str
    observed_at: datetime
    games: tuple[OfficialGameScheduleAuthority, ...]

    def __post_init__(self) -> None:
        _require_text(self.provider_id, "provider_id")
        _require_text(self.provider_version, "provider_version")
        _require_text(self.source_url, "source_url")
        _require_sha256(self.source_payload_sha256, "source_payload_sha256")
        _require_utc(self.observed_at, "observed_at")
        if type(self.games) is not tuple or len(self.games) != 2:
            raise ValueError("games must contain the two canonical game results")
        if {game.lottery_type for game in self.games} != set(
            SUPPORTED_CANONICAL_SCHEDULE_LOTTERIES
        ):
            raise ValueError("games must independently cover DAILY_539 and POWER_LOTTO")
        for game in self.games:
            for fact in game.schedules:
                source = fact.announcement.source
                if (
                    source.source_id != self.provider_id
                    or source.source_version != self.provider_version
                    or source.source_locator != self.source_url
                    or source.source_sha256 != self.source_payload_sha256
                    or source.observed_at != self.observed_at
                ):
                    raise ValueError(
                        "canonical schedule provenance does not match the fetched response"
                    )


@dataclass(frozen=True, slots=True)
class CanonicalScheduleAuthorityGameSyncResult:
    """Audited persistence result for one game-local transaction."""

    run_id: str
    lottery_type: LotteryType
    official_game_code: int
    authority_status: ScheduleAuthorityStatus
    apply_status: ScheduleAuthorityApplyStatus
    target_draw_numbers: tuple[str, ...]
    inserted_count: int
    reobserved_count: int
    conflict_count: int
    evidence_count: int

    def __post_init__(self) -> None:
        _require_text(self.run_id, "run_id")
        if self.lottery_type not in SUPPORTED_CANONICAL_SCHEDULE_LOTTERIES:
            raise ValueError("sync result lottery_type is unsupported")
        if self.official_game_code != expected_schedule_game_code(self.lottery_type):
            raise ValueError("sync result official_game_code is invalid")
        if type(self.authority_status) is not ScheduleAuthorityStatus:
            raise ValueError("authority_status must be a ScheduleAuthorityStatus")
        if type(self.apply_status) is not ScheduleAuthorityApplyStatus:
            raise ValueError("apply_status must be a ScheduleAuthorityApplyStatus")
        if type(self.target_draw_numbers) is not tuple or any(
            type(item) is not str or _DRAW_NUMBER.fullmatch(item) is None
            for item in self.target_draw_numbers
        ):
            raise ValueError("target_draw_numbers must contain ASCII-decimal identities")
        counts = (
            self.inserted_count,
            self.reobserved_count,
            self.conflict_count,
            self.evidence_count,
        )
        if any(type(item) is not int or item < 0 for item in counts):
            raise ValueError("sync result counts must be non-negative exact integers")


@dataclass(frozen=True, slots=True)
class CanonicalScheduleAuthoritySyncResult:
    """Result of applying the two isolated game-local transactions."""

    source_payload_sha256: str
    observed_at: datetime
    game_results: tuple[CanonicalScheduleAuthorityGameSyncResult, ...]

    def __post_init__(self) -> None:
        _require_sha256(self.source_payload_sha256, "source_payload_sha256")
        _require_utc(self.observed_at, "observed_at")
        if type(self.game_results) is not tuple or len(self.game_results) != 2:
            raise ValueError("game_results must contain two isolated results")
        if {item.lottery_type for item in self.game_results} != set(
            SUPPORTED_CANONICAL_SCHEDULE_LOTTERIES
        ):
            raise ValueError("game_results must cover DAILY_539 and POWER_LOTTO")


@dataclass(frozen=True, slots=True)
class OfficialScheduleFetchResult:
    """One validated official response before canonical persistence."""

    provider_id: str
    provider_version: str
    source_url: str
    source_payload_sha256: str
    observed_at: datetime
    announcements: tuple[TargetAnnouncement, ...]

    def __post_init__(self) -> None:
        _require_text(self.provider_id, "provider_id")
        _require_text(self.provider_version, "provider_version")
        _require_text(self.source_url, "source_url")
        _require_sha256(self.source_payload_sha256, "source_payload_sha256")
        _require_utc(self.observed_at, "observed_at")
        if type(self.announcements) is not tuple or not self.announcements:
            raise ValueError("announcements must be a non-empty tuple")
        for announcement in self.announcements:
            if type(announcement) is not TargetAnnouncement:
                raise ValueError("announcements must contain TargetAnnouncement values")
            if announcement.target.lottery_type is not LotteryType.BIG_LOTTO:
                raise ValueError("official schedule synchronization supports BIG_LOTTO only")
            source = announcement.source
            if (
                source.source_id != self.provider_id
                or source.source_version != self.provider_version
                or source.source_locator != self.source_url
                or source.source_sha256 != self.source_payload_sha256
                or source.observed_at != self.observed_at
            ):
                raise ValueError("announcement provenance does not match the fetched response")


@dataclass(frozen=True, slots=True)
class OfficialScheduleSyncResult:
    """Audited result for one atomic canonical schedule synchronization."""

    run_id: str
    status: IngestionRunStatus
    provider_id: str
    provider_version: str
    source_url: str
    source_payload_sha256: str
    observed_at: datetime
    target_draw_numbers: tuple[str, ...]
    total_count: int
    inserted_count: int
    skipped_count: int
    exact_duplicate_count: int
    completed_count: int
    conflict_count: int
    failed_count: int

    def __post_init__(self) -> None:
        _require_text(self.run_id, "run_id")
        if self.status not in {IngestionRunStatus.SUCCESS, IngestionRunStatus.FAILED}:
            raise ValueError("schedule sync result must be terminal")
        _require_text(self.provider_id, "provider_id")
        _require_text(self.provider_version, "provider_version")
        _require_text(self.source_url, "source_url")
        _require_sha256(self.source_payload_sha256, "source_payload_sha256")
        _require_utc(self.observed_at, "observed_at")
        if type(self.target_draw_numbers) is not tuple or any(
            type(value) is not str or not value for value in self.target_draw_numbers
        ):
            raise ValueError("target_draw_numbers must contain non-empty text")
        counts = (
            self.total_count,
            self.inserted_count,
            self.skipped_count,
            self.exact_duplicate_count,
            self.completed_count,
            self.conflict_count,
            self.failed_count,
        )
        if any(type(value) is not int or value < 0 for value in counts):
            raise ValueError("schedule sync counts must be non-negative integers")
        if self.exact_duplicate_count + self.completed_count != self.skipped_count:
            raise ValueError("schedule sync skipped detail counts are inconsistent")
        if self.total_count != (
            self.inserted_count + self.skipped_count + self.conflict_count + self.failed_count
        ):
            raise ValueError("schedule sync counts do not classify every target")
        if len(self.target_draw_numbers) != self.total_count:
            raise ValueError("schedule sync target count does not match total_count")

    @property
    def counts_are_consistent(self) -> bool:
        return self.total_count == (
            self.inserted_count + self.skipped_count + self.conflict_count + self.failed_count
        )


class OfficialScheduleProvider(Protocol):
    """Port for one bounded official B649 schedule response."""

    def fetch_schedule(self, *, observed_at: datetime) -> OfficialScheduleFetchResult: ...


class CanonicalScheduleSyncRepository(Protocol):
    """Atomic persistence port for official schedule identities."""

    def apply_official_schedule_sync(
        self,
        fetched: OfficialScheduleFetchResult,
    ) -> OfficialScheduleSyncResult: ...


class CanonicalScheduleAuthorityProvider(Protocol):
    """Port for one shared, independently classified T539/P638 response."""

    def fetch_authority(
        self,
        *,
        observed_at: datetime,
    ) -> CanonicalScheduleAuthorityFetchResult: ...


class CanonicalScheduleAuthorityRepository(Protocol):
    """Persistence port for isolated T539/P638 schedule-authority decisions."""

    def apply_canonical_schedule_authority(
        self,
        fetched: CanonicalScheduleAuthorityFetchResult,
    ) -> CanonicalScheduleAuthoritySyncResult: ...


class CanonicalScheduleSyncConflictError(OfficialScheduleSyncError):
    """An immutable schedule conflict was audited without partial schedule writes."""

    def __init__(self, result: OfficialScheduleSyncResult) -> None:
        super().__init__("official schedule synchronization conflicts with canonical authority")
        self.result = result


class SynchronizeOfficialSchedule:
    """Fetch and atomically apply one bounded official schedule response."""

    def __init__(
        self,
        provider: OfficialScheduleProvider,
        repository: CanonicalScheduleSyncRepository,
    ) -> None:
        self._provider = provider
        self._repository = repository

    def execute(self, *, observed_at: datetime) -> OfficialScheduleSyncResult:
        _require_utc(observed_at, "observed_at")
        fetched = self._provider.fetch_schedule(observed_at=observed_at)
        if type(fetched) is not OfficialScheduleFetchResult:
            raise OfficialScheduleProviderError(
                "official schedule provider returned an unsupported result"
            )
        return self._repository.apply_official_schedule_sync(fetched)


class SynchronizeCanonicalScheduleAuthority:
    """Fetch and apply T539/P638 authority without coupling game-local outcomes."""

    def __init__(
        self,
        provider: CanonicalScheduleAuthorityProvider,
        repository: CanonicalScheduleAuthorityRepository,
    ) -> None:
        self._provider = provider
        self._repository = repository

    def execute(self, *, observed_at: datetime) -> CanonicalScheduleAuthoritySyncResult:
        _require_utc(observed_at, "observed_at")
        fetched = self._provider.fetch_authority(observed_at=observed_at)
        if type(fetched) is not CanonicalScheduleAuthorityFetchResult:
            raise OfficialScheduleProviderError(
                "canonical schedule authority provider returned an unsupported result"
            )
        return self._repository.apply_canonical_schedule_authority(fetched)


OfficialScheduleSyncUseCase = SynchronizeOfficialSchedule
CanonicalScheduleSyncUseCase = SynchronizeOfficialSchedule


def _require_text(value: object, label: str) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{label} must be canonical non-empty text")


def _require_sha256(value: object, label: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")


def _require_utc(value: object, label: str) -> None:
    if type(value) is not datetime or value.tzinfo is not UTC:
        raise ValueError(f"{label} must be a timezone-aware UTC datetime")


__all__ = [
    "CANONICAL_NORMAL_DRAW_LOCAL_TIME",
    "CANONICAL_SCHEDULE_AUTHORITY_PARSER_VERSION",
    "CANONICAL_SCHEDULE_TIMEZONE",
    "P638_SCHEDULE_GAME_CODE",
    "SCHEDULE_SYNC_PARSER_VERSION",
    "SUPPORTED_CANONICAL_SCHEDULE_LOTTERIES",
    "T539_SCHEDULE_GAME_CODE",
    "AuthoritativeScheduleVeto",
    "CanonicalScheduleAuthorityFetchResult",
    "CanonicalScheduleAuthorityGameSyncResult",
    "CanonicalScheduleAuthorityProvider",
    "CanonicalScheduleAuthorityRepository",
    "CanonicalScheduleAuthoritySyncResult",
    "CanonicalScheduleFact",
    "CanonicalScheduleSyncConflictError",
    "CanonicalScheduleSyncRepository",
    "CanonicalScheduleSyncUseCase",
    "OfficialGameScheduleAuthority",
    "OfficialScheduleContractError",
    "OfficialScheduleFetchResult",
    "OfficialScheduleProvider",
    "OfficialScheduleProviderError",
    "OfficialScheduleSyncError",
    "OfficialScheduleSyncResult",
    "OfficialScheduleSyncUseCase",
    "OfficialScheduleUnavailableError",
    "ScheduleAuthorityApplyStatus",
    "ScheduleAuthorityStatus",
    "ScheduleExceptionKind",
    "SynchronizeCanonicalScheduleAuthority",
    "SynchronizeOfficialSchedule",
    "expected_schedule_game_code",
]
