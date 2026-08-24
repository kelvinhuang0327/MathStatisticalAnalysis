"""Durable local launchd orchestration for the B649 Goal-C forward loop.

This helper owns scheduling mechanics only.  Strategy definitions, prediction
generation, official draw ingestion, outcome binding, scoring, and reporting
remain delegated to the existing LottoLab implementations.
"""

from __future__ import annotations

import argparse
import errno
import fcntl
import hashlib
import json
import os
import plistlib
import re
import ssl
import stat
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from inspect import signature
from pathlib import Path
from typing import Protocol, cast
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lottolab.application.draw_automation import DrawSyncRequest
from lottolab.application.forward_auto_cycle_core import ForwardAutoCycleCore
from lottolab.application.use_cases.draw_automation import ScheduledDrawSync
from lottolab.domain.draw_data_integrity import DrawDataIntegrityStatus
from lottolab.domain.draws import LotteryType
from lottolab.domain.ingestion import IngestionRunStatus
from lottolab.domain.pre_outcome_target import (
    TargetAnnouncement,
    TargetSourceProvenance,
)
from lottolab.domain.prospective_observer import ObservationTarget
from lottolab.infrastructure.imports.csv_draws import parse_draw_csv
from lottolab.infrastructure.persistence.draw_schema import (
    CURRENT_SCHEMA_VERSION,
    LocalDataPaths,
)
from lottolab.infrastructure.persistence.repositories import SQLiteDrawDataRepository
from lottolab.infrastructure.pre_outcome_target_operational import (
    OFFICIAL_SCHEDULE_SOURCE_ID,
    OFFICIAL_SCHEDULE_SOURCE_VERSION,
    OPERATIONAL_ANNOUNCEMENT_SCHEMA_VERSION,
    SCHEDULE_TIMEZONE,
    FileSystemOperationalTargetAnnouncementSource,
    TargetAnnouncementSourceStatus,
)
from lottolab.infrastructure.taiwan_lottery_draw_provider import (
    HEADERS as OFFICIAL_DRAW_HEADERS,
)
from lottolab.infrastructure.taiwan_lottery_draw_provider import (
    MAX_RESPONSE_BYTES as OFFICIAL_DRAW_MAX_RESPONSE_BYTES,
)
from lottolab.infrastructure.taiwan_lottery_draw_provider import (
    TaiwanLotteryDrawProvider,
)
from lottolab.interfaces.api.local_app import (
    DRAW_PROVIDER_SOURCE_ENV,
    OFFICIAL_TAIWAN_LOTTERY_SOURCE,
    local_draw_provider,
)
from lottolab.interfaces.cli.draw_data_integrity import (
    inspect_draw_data_integrity_report,
)
from tools.b649_forward_auto_cycle_adapter import B649ForwardAutoCycleAdapter
from tools.b649_operational_prediction_loop import (
    LOTTERY_TYPE,
    STRATEGY_STREAMS,
    TAIPEI,
    TARGET_SCHEDULED_AT,
    PredictionTarget,
    StrategyStream,
    iter_prediction_files,
    load_canonical_history,
    rescore_draw,
    run_strategy_stream,
    save_strategy_prediction,
)
from tools.b649_pair_rule_forward_shadow import (
    SHADOW_HEALTH_NAMESPACE,
    PairRuleForwardShadow,
    shadow_health_not_run,
)

TASK_VERSION = "B649_GOALC_LOCAL_LAUNCHD_R1"
HEALTH_SCHEMA_VERSION = "b649-goalc-local-scheduler-health-v1"
SCHEDULER_LABEL = "com.lottolab.b649-goalc-r1"
SCHEDULE_URL = "https://api.taiwanlottery.com/TLCAPIWeB/Lottery/NextDrawDate"
SCHEDULE_GAME_CODE = 5118
START_INTERVAL_SECONDS = 300
STALE_AFTER_SECONDS = 900
EXPECTED_STREAM_COUNT = 11
SCHEDULE_MAX_RESPONSE_BYTES = 1024 * 1024
HTTPS_TIMEOUT_SECONDS = 15.0

CANONICAL_REPOSITORY = Path("/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis")
SOURCE_WORKTREE = CANONICAL_REPOSITORY
PYTHON_EXECUTABLE = CANONICAL_REPOSITORY / ".venv/bin/python"
SCRIPT_PATH = CANONICAL_REPOSITORY / "tools/b649_goalc_local_scheduler.py"
GOALC_ROOT = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_OPERATIONAL_PREDICTION_LOOP_R1"
)
DATA_ROOT = Path("/Users/kelvin/Library/Application Support/LottoLab")
DATABASE_PATH = DATA_ROOT / "lottolab.db"
ANNOUNCEMENT_PATH = DATA_ROOT / "pre-outcome-target-announcements-v1.json"
SCHEDULER_ROOT = GOALC_ROOT / "scheduler"
LOCK_PATH = SCHEDULER_ROOT / "b649-goalc.lock"
HEALTH_PATH = SCHEDULER_ROOT / "health.json"
STDOUT_PATH = SCHEDULER_ROOT / "launchd.stdout.log"
STDERR_PATH = SCHEDULER_ROOT / "launchd.stderr.log"
PLIST_PATH = Path.home() / "Library/LaunchAgents/com.lottolab.b649-goalc-r1.plist"

_OFFICIAL_HTTPS_HOSTS = frozenset({"api.taiwanlottery.com", "www.taiwanlottery.com"})
_DRAW_NUMBER = re.compile(r"[0-9]{1,32}", flags=re.ASCII)
_STRICT_CHAIN_MARKERS = (
    "authority key identifier",
    "subject key identifier",
    "basic constraints",
    "key usage extension",
)
_NON_STRICT_CERT_MARKERS = ("hostname", "expired", "not yet valid")
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
_NONBLOCK = getattr(os, "O_NONBLOCK", 0)

Clock = Callable[[], datetime]
SourceHeadResolver = Callable[[Path], str]
HttpsTransport = Callable[[Request, ssl.SSLContext, float, int], bytes]


class GoalCSchedulerError(RuntimeError):
    """Base class for fail-closed scheduler errors."""


class OfficialScheduleUnavailableError(GoalCSchedulerError):
    """The official schedule could not establish a future B649 target."""


class LocalSchedulerSafetyError(GoalCSchedulerError):
    """A local file or runtime identity failed a safety check."""


class SchedulerInvariantError(GoalCSchedulerError):
    """Existing Goal-C state conflicts with the scheduler contract."""


class SchedulerAlreadyRunning(GoalCSchedulerError):
    """A different process currently holds the advisory scheduler lock."""


@dataclass(frozen=True, slots=True)
class SchedulerConfig:
    """All paths and launch policy needed for one scheduler instance."""

    label: str
    version: str
    canonical_repository: Path
    source_worktree: Path
    python_executable: Path
    script_path: Path
    operation_root: Path
    data_root: Path
    database: Path
    announcement: Path
    scheduler_root: Path
    lock_path: Path
    health_path: Path
    stdout_path: Path
    stderr_path: Path
    plist_path: Path
    schedule_url: str = SCHEDULE_URL
    start_interval_seconds: int = START_INTERVAL_SECONDS
    stale_after_seconds: int = STALE_AFTER_SECONDS
    expected_stream_count: int = EXPECTED_STREAM_COUNT

    def __post_init__(self) -> None:
        if not self.label or not self.version:
            raise ValueError("scheduler label and version must be non-empty")
        path_values = (
            self.canonical_repository,
            self.source_worktree,
            self.python_executable,
            self.script_path,
            self.operation_root,
            self.data_root,
            self.database,
            self.announcement,
            self.scheduler_root,
            self.lock_path,
            self.health_path,
            self.stdout_path,
            self.stderr_path,
            self.plist_path,
        )
        if any(not value.is_absolute() for value in path_values):
            raise ValueError("all scheduler paths must be absolute")
        if self.database != self.data_root / "lottolab.db":
            raise ValueError("database must be the canonical file below data_root")
        if self.announcement != self.data_root / self.announcement.name:
            raise ValueError("announcement must be directly below data_root")
        if self.scheduler_root != self.operation_root / "scheduler":
            raise ValueError("scheduler_root must be directly below operation_root")
        if self.lock_path.parent != self.scheduler_root:
            raise ValueError("lock_path must be directly below scheduler_root")
        if self.health_path.parent != self.scheduler_root:
            raise ValueError("health_path must be directly below scheduler_root")
        if self.start_interval_seconds != START_INTERVAL_SECONDS:
            raise ValueError("the launch interval is fixed at 300 seconds")
        if self.stale_after_seconds < self.start_interval_seconds * 2:
            raise ValueError("stale_after_seconds must span at least two cycles")
        if self.expected_stream_count != EXPECTED_STREAM_COUNT:
            raise ValueError("the expected B649 stream count is fixed at 11")


def production_config() -> SchedulerConfig:
    """Return the exact authorized local runtime definition."""

    return SchedulerConfig(
        label=SCHEDULER_LABEL,
        version=TASK_VERSION,
        canonical_repository=CANONICAL_REPOSITORY,
        source_worktree=SOURCE_WORKTREE,
        python_executable=PYTHON_EXECUTABLE,
        script_path=SCRIPT_PATH,
        operation_root=GOALC_ROOT,
        data_root=DATA_ROOT,
        database=DATABASE_PATH,
        announcement=ANNOUNCEMENT_PATH,
        scheduler_root=SCHEDULER_ROOT,
        lock_path=LOCK_PATH,
        health_path=HEALTH_PATH,
        stdout_path=STDOUT_PATH,
        stderr_path=STDERR_PATH,
        plist_path=PLIST_PATH,
    )


@dataclass(frozen=True, slots=True)
class ScheduleRefreshResult:
    """Observable result of one schedule-authority check."""

    status: str
    source_url: str | None
    source_payload_sha256: str | None
    observed_at: datetime
    inventory_count: int
    b649_targets: tuple[str, ...]
    strict_tls_fallback_used: bool

    def health_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "source_url": self.source_url,
            "source_payload_sha256": self.source_payload_sha256,
            "observed_at": _utc_text(self.observed_at),
            "inventory_count": self.inventory_count,
            "b649_targets": list(self.b649_targets),
            "strict_tls_fallback_used": self.strict_tls_fallback_used,
        }


@dataclass(frozen=True, slots=True)
class PredictionInventory:
    """Validated prediction state for exactly one target."""

    expected_stream_ids: tuple[str, ...]
    available_stream_ids: tuple[str, ...]
    observed_stream_ids: tuple[str, ...]
    score_required_run_ids: tuple[str, ...]

    @property
    def missing_stream_ids(self) -> tuple[str, ...]:
        available = frozenset(self.available_stream_ids)
        return tuple(value for value in self.expected_stream_ids if value not in available)

    @property
    def actual_available_count(self) -> int:
        return len(self.available_stream_ids)

    @property
    def ready(self) -> bool:
        return self.available_stream_ids == self.expected_stream_ids

    def health_dict(self) -> dict[str, object]:
        return {
            "expected_stream_ids": list(self.expected_stream_ids),
            "available_stream_ids": list(self.available_stream_ids),
            "observed_stream_ids": list(self.observed_stream_ids),
            "missing_stream_ids": list(self.missing_stream_ids),
        }


@dataclass(frozen=True, slots=True)
class PostDrawResult:
    """Outcome/scoring/reporting state after the bounded official sync."""

    outcome_status: str
    scoring_status: str
    reporting_status: str
    cycle_action: str

    @property
    def outcome_available(self) -> bool:
        return self.outcome_status not in {"WAITING_FOR_OUTCOME", "OUTCOME_PENDING"}


class SchedulerBackend(Protocol):
    """Small boundary used by the orchestration state machine and its tests."""

    def refresh_schedule(self, observed_at: datetime) -> ScheduleRefreshResult: ...

    def resolve_target(self) -> PredictionTarget | None: ...

    def inspect_predictions(self, target: PredictionTarget) -> PredictionInventory: ...

    def generate_predraw(
        self,
        target: PredictionTarget,
        missing_stream_ids: Sequence[str],
    ) -> dict[str, object]: ...

    def sync_official_outcome(self, target: PredictionTarget) -> dict[str, object]: ...

    def complete_postdraw(
        self,
        target: PredictionTarget,
        inventory: PredictionInventory,
    ) -> PostDrawResult: ...


class OfficialHttpsClient:
    """Credential-free official-host HTTPS GET client with one narrow TLS retry.

    The retry is available only for Python/OpenSSL strict-chain failures.  It
    clears ``VERIFY_X509_STRICT`` and retains CA validation, certificate
    requirements, and hostname verification.  Hostname and validity failures
    never use the retry.
    """

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
        request = Request(
            url,
            headers=dict(OFFICIAL_DRAW_HEADERS if headers is None else headers),
            method="GET",
        )
        context = ssl.create_default_context()
        _require_secure_tls_context(context)
        try:
            return self._transport(
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
        return self._transport(
            request,
            fallback,
            self._timeout_seconds,
            max_response_bytes,
        )


class AdvisoryProcessLock:
    """Non-blocking, process-scoped advisory lock with safe file identity checks."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._descriptor: int | None = None

    def __enter__(self) -> AdvisoryProcessLock:
        _ensure_private_directory(self._path.parent)
        created = False
        try:
            descriptor = os.open(
                self._path,
                os.O_RDWR | os.O_CREAT | os.O_EXCL | _NOFOLLOW | _CLOEXEC,
                0o600,
            )
            created = True
        except FileExistsError:
            try:
                descriptor = os.open(
                    self._path,
                    os.O_RDWR | _NOFOLLOW | _CLOEXEC | _NONBLOCK,
                )
            except OSError as exc:
                raise LocalSchedulerSafetyError("cannot open scheduler lock safely") from exc
        except OSError as exc:
            raise LocalSchedulerSafetyError("cannot create scheduler lock safely") from exc

        try:
            if created:
                os.fchmod(descriptor, 0o600)
            _validate_owned_regular_descriptor(descriptor, "scheduler lock", mode=0o600)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                if exc.errno in {errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK}:
                    raise SchedulerAlreadyRunning(
                        "another Goal-C scheduler cycle holds the process lock"
                    ) from exc
                raise LocalSchedulerSafetyError("cannot acquire scheduler lock") from exc
        except BaseException:
            os.close(descriptor)
            raise
        self._descriptor = descriptor
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> None:
        del exc_type, exc_value, traceback
        descriptor = self._descriptor
        self._descriptor = None
        if descriptor is not None:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)


class ProductionSchedulerBackend:
    """Bind the scheduler state machine to existing Goal-C components."""

    def __init__(
        self,
        config: SchedulerConfig,
        *,
        clock: Clock,
        https_client: OfficialHttpsClient | None = None,
        environ: Mapping[str, str] | None = None,
        shadow: PairRuleForwardShadow | None = None,
    ) -> None:
        self._config = config
        self._clock = clock
        self._https = OfficialHttpsClient() if https_client is None else https_client
        self._environ = dict(os.environ if environ is None else environ)
        self._shadow = PairRuleForwardShadow() if shadow is None else shadow

    def refresh_schedule(self, observed_at: datetime) -> ScheduleRefreshResult:
        self._validate_environment()
        observed_utc = _as_utc(observed_at)
        target = self.resolve_target()
        targets = () if target is None else (target.draw_number,)
        return ScheduleRefreshResult(
            status="DB_ONLY_NO_AUTO_SUPPLEMENT",
            source_url=None,
            source_payload_sha256=None,
            observed_at=observed_utc,
            inventory_count=len(targets),
            b649_targets=targets,
            strict_tls_fallback_used=False,
        )

    def resolve_target(self) -> PredictionTarget | None:
        return B649ForwardAutoCycleAdapter(
            self._config.operation_root,
            database=self._config.database,
            clock=self._taipei_now,
        ).resolve_next_target()

    def inspect_predictions(self, target: PredictionTarget) -> PredictionInventory:
        return inspect_prediction_inventory(self._config.operation_root, target)

    def run_shadow_predraw(
        self,
        target: PredictionTarget,
        observed_at: datetime,
        *,
        primary_status: str,
        canonical_source_head: str,
    ) -> dict[str, object]:
        """Run the isolated shadow only after primary 11-stream readiness."""

        history = load_canonical_history(
            self._config.database,
            target_draw_number=target.draw_number,
            target_draw_date=target.draw_date,
        )
        return self._shadow.run_pre_draw(
            target,
            history,
            observed_at=observed_at,
            readiness_deadline=_target_scheduled_at(target),
            primary_status=primary_status,
            canonical_source_head=canonical_source_head,
        )

    def run_shadow_postdraw(
        self,
        target: PredictionTarget,
        observed_at: datetime,
        *,
        primary_status: str,
        canonical_source_head: str,
    ) -> dict[str, object]:
        """Reconcile the shadow from existing official outcome authority only."""

        adapter = B649ForwardAutoCycleAdapter(
            self._config.operation_root,
            database=self._config.database,
            target=target,
            streams=(),
            clock=self._taipei_now,
        )
        official = adapter.resolve_official_outcome(target)
        return self._shadow.run_post_draw(
            target,
            official,
            observed_at=observed_at,
            primary_status=primary_status,
            canonical_source_head=canonical_source_head,
        )

    def generate_predraw(
        self,
        target: PredictionTarget,
        missing_stream_ids: Sequence[str],
    ) -> dict[str, object]:
        deadline = _target_scheduled_at(target)
        expected = {stream.strategy_id: stream for stream in STRATEGY_STREAMS if stream.enabled}
        requested = tuple(missing_stream_ids)
        if len(requested) != len(set(requested)) or any(
            value not in expected for value in requested
        ):
            raise SchedulerInvariantError("requested PRE_DRAW stream set is invalid")
        history = load_canonical_history(
            self._config.database,
            target_draw_number=target.draw_number,
            target_draw_date=target.draw_date,
        )
        created: list[str] = []
        failures: list[dict[str, str]] = []
        for strategy_id in requested:
            observed_at = _as_utc(self._clock())
            if observed_at >= deadline:
                break
            stream = expected[strategy_id]
            run_id = _new_scheduler_prediction_run_id(target, stream, observed_at)
            record = run_strategy_stream(
                stream,
                history,
                target,
                created_at=observed_at.astimezone(TAIPEI),
                prediction_run_id=run_id,
            )
            if _as_utc(self._clock()) >= deadline:
                break
            try:
                saved = save_strategy_prediction(self._config.operation_root, record)
            except Exception as exc:
                failures.append(
                    {
                        "strategy_id": strategy_id,
                        "error_class": type(exc).__name__,
                        "error_message": str(exc),
                    }
                )
            else:
                created.append(str(saved))
        return {
            "requested_stream_ids": list(requested),
            "created_prediction_paths": created,
            "failures": failures,
        }

    def sync_official_outcome(self, target: PredictionTarget) -> dict[str, object]:
        report = inspect_draw_data_integrity_report(self._config.database)
        if (
            report.status is not DrawDataIntegrityStatus.HEALTHY
            or report.schema_version != CURRENT_SCHEMA_VERSION
        ):
            raise SchedulerInvariantError(
                "canonical draw database is not healthy at the current schema"
            )

        selected = local_draw_provider(self._environ)
        if not isinstance(selected, TaiwanLotteryDrawProvider):
            raise SchedulerInvariantError("official Taiwan Lottery provider is not selected")
        provider = TaiwanLotteryDrawProvider(
            transport=lambda url: self._https.get(
                url,
                max_response_bytes=OFFICIAL_DRAW_MAX_RESPONSE_BYTES,
            )
        )
        paths = LocalDataPaths(
            data_directory=self._config.data_root,
            database=self._config.database,
        )
        result = ScheduledDrawSync(
            lambda: provider,
            lambda: SQLiteDrawDataRepository(paths),
            parse_draw_csv,
        ).execute(
            DrawSyncRequest(
                lottery_type=LotteryType.BIG_LOTTO,
                date_from=date.fromisoformat(target.draw_date),
                date_to=date.fromisoformat(target.draw_date),
            )
        )
        ingestion = result.ingestion
        if (
            ingestion.status is not IngestionRunStatus.SUCCESS
            or not ingestion.counts_are_consistent
            or ingestion.conflict_count
            or ingestion.failed_count
        ):
            raise SchedulerInvariantError("official draw sync did not complete cleanly")
        return {
            "status": "SUCCESS",
            "provider_id": result.provider_id,
            "requested_start": result.requested_start.isoformat(),
            "requested_end": result.requested_end.isoformat(),
            "resolved_start": (
                None if result.resolved_start is None else result.resolved_start.isoformat()
            ),
            "resolved_end": (
                None if result.resolved_end is None else result.resolved_end.isoformat()
            ),
            "fetched_count": result.fetched_count,
            "run_id": ingestion.run_id,
            "inserted_count": ingestion.inserted_count,
            "skipped_count": ingestion.skipped_count,
            "strict_tls_fallback_used": self._https.strict_tls_fallback_used,
        }

    def complete_postdraw(
        self,
        target: PredictionTarget,
        inventory: PredictionInventory,
    ) -> PostDrawResult:
        adapter = B649ForwardAutoCycleAdapter(
            self._config.operation_root,
            database=self._config.database,
            target=target,
            streams=(),
            clock=self._taipei_now,
        )
        official = adapter.resolve_official_outcome(target)
        if official is None:
            return PostDrawResult(
                outcome_status="WAITING_FOR_OUTCOME",
                scoring_status="WAITING_FOR_OUTCOME",
                reporting_status="CURRENT",
                cycle_action="WAITING_FOR_OUTCOME",
            )

        current = adapter.read_current_outcome(target)
        missing_scores = _missing_score_run_ids(
            self._config.operation_root,
            target.draw_number,
            inventory.score_required_run_ids,
        )
        reporting_current = _reporting_paths_current(self._config.operation_root)

        if current is not None and adapter.outcomes_equal(current, official):
            if missing_scores:
                rescore_draw(
                    self._config.operation_root,
                    target.draw_number,
                    scored_at=self._taipei_now(),
                )
            if missing_scores or not reporting_current:
                adapter.refresh_reporting()
            remaining = _missing_score_run_ids(
                self._config.operation_root,
                target.draw_number,
                inventory.score_required_run_ids,
            )
            if remaining:
                raise SchedulerInvariantError("existing PRE_DRAW predictions remain unscored")
            return PostDrawResult(
                outcome_status="IDENTICAL_OUTCOME",
                scoring_status="COMPLETE",
                reporting_status="CURRENT",
                cycle_action="NO_OP" if not missing_scores and reporting_current else "REPAIRED",
            )

        cycle = ForwardAutoCycleCore(adapter).run()
        if cycle.outcome_status == "OWNER_OUTCOME_PRESERVED":
            raise SchedulerInvariantError("owner outcome conflicts with the official outcome")
        remaining = _missing_score_run_ids(
            self._config.operation_root,
            target.draw_number,
            inventory.score_required_run_ids,
        )
        if remaining:
            raise SchedulerInvariantError("not every existing PRE_DRAW prediction was scored")
        if not _reporting_paths_current(self._config.operation_root):
            raise SchedulerInvariantError("Goal-C reporting rebuild is incomplete")
        return PostDrawResult(
            outcome_status=cycle.outcome_status,
            scoring_status="COMPLETE",
            reporting_status="REBUILT",
            cycle_action=cycle.next_action,
        )

    def _taipei_now(self) -> datetime:
        return _as_utc(self._clock()).astimezone(TAIPEI)

    def _validate_environment(self) -> None:
        if self._environ.get(DRAW_PROVIDER_SOURCE_ENV) != OFFICIAL_TAIWAN_LOTTERY_SOURCE:
            raise SchedulerInvariantError(
                f"{DRAW_PROVIDER_SOURCE_ENV} must select {OFFICIAL_TAIWAN_LOTTERY_SOURCE}"
            )
        if self._environ.get("LOTTOLAB_DATA_DIR") != str(self._config.data_root):
            raise SchedulerInvariantError("LOTTOLAB_DATA_DIR must name the canonical data root")


def refresh_official_schedule(
    announcement_path: Path,
    *,
    client: OfficialHttpsClient,
    observed_at: datetime,
    source_url: str = SCHEDULE_URL,
) -> ScheduleRefreshResult:
    """Refresh future B649 authority while retaining the latest missed deadline."""

    observed_utc = _as_utc(observed_at)
    _validate_owned_directory(announcement_path.parent, mode=0o700)
    before_identity = _safe_file_identity(announcement_path, missing_ok=True)
    existing = FileSystemOperationalTargetAnnouncementSource(announcement_path).read()
    existing_announcements = (
        ()
        if existing.status is TargetAnnouncementSourceStatus.NOT_CONFIGURED
        else existing.announcements
    )
    non_b649 = tuple(
        item
        for item in existing_announcements
        if item.target.lottery_type is not LotteryType.BIG_LOTTO
    )
    expired_b649 = tuple(
        item
        for item in existing_announcements
        if _is_official_b649_announcement(item, source_url=source_url)
        and item.scheduled_at <= observed_utc
    )
    latest_expired = () if not expired_b649 else (max(expired_b649, key=_announcement_sort_key),)
    preserved = (*non_b649, *latest_expired)
    body = client.get(source_url, max_response_bytes=SCHEDULE_MAX_RESPONSE_BYTES)
    fresh = parse_official_b649_schedule(
        body,
        observed_at=observed_utc,
        source_url=source_url,
    )
    combined = tuple(sorted((*preserved, *fresh), key=_announcement_sort_key))
    encoded = _encode_operational_announcements(combined)
    _atomic_replace_bytes(
        announcement_path,
        encoded,
        expected_identity=before_identity,
        validate=lambda path: FileSystemOperationalTargetAnnouncementSource(path).read(),
    )
    readback = FileSystemOperationalTargetAnnouncementSource(announcement_path).read()
    if (
        readback.status is not TargetAnnouncementSourceStatus.AVAILABLE
        or readback.announcements != combined
    ):
        raise LocalSchedulerSafetyError("announcement readback differs after atomic replace")
    return ScheduleRefreshResult(
        status="REFRESHED",
        source_url=source_url,
        source_payload_sha256=hashlib.sha256(body).hexdigest(),
        observed_at=observed_utc,
        inventory_count=len(combined),
        b649_targets=tuple(
            item.target.draw_number
            for item in combined
            if item.target.lottery_type is LotteryType.BIG_LOTTO
        ),
        strict_tls_fallback_used=client.strict_tls_fallback_used,
    )


def parse_official_b649_schedule(
    body: bytes,
    *,
    observed_at: datetime,
    source_url: str = SCHEDULE_URL,
) -> tuple[TargetAnnouncement, ...]:
    """Validate the official next-draw response and return future B649 targets."""

    observed_utc = _as_utc(observed_at)
    _validate_official_https_url(source_url)
    try:
        decoded: object = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OfficialScheduleUnavailableError(
            "official schedule response is not valid UTF-8 JSON"
        ) from exc
    if not isinstance(decoded, dict):
        raise OfficialScheduleUnavailableError("official schedule response must be an object")
    payload = cast(dict[str, object], decoded)
    if payload.get("rtCode") != 0:
        raise OfficialScheduleUnavailableError("official schedule response reported an error")
    content = payload.get("content")
    if not isinstance(content, dict):
        raise OfficialScheduleUnavailableError("official schedule content is missing")
    rows = cast(dict[str, object], content).get("nextDrawDateList")
    if not isinstance(rows, list):
        raise OfficialScheduleUnavailableError("official schedule target list is missing")

    payload_sha256 = hashlib.sha256(body).hexdigest()
    scheduled_clock = datetime.fromisoformat(TARGET_SCHEDULED_AT).astimezone(TAIPEI).timetz()
    announcements: list[TargetAnnouncement] = []
    identities: set[str] = set()
    for raw in cast(list[object], rows):
        if not isinstance(raw, dict):
            raise OfficialScheduleUnavailableError("official schedule row must be an object")
        row = cast(dict[str, object], raw)
        if row.get("gameCode") != SCHEDULE_GAME_CODE:
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
        scheduled_local = datetime.combine(
            draw_date,
            time(
                hour=scheduled_clock.hour,
                minute=scheduled_clock.minute,
                second=scheduled_clock.second,
            ),
            tzinfo=TAIPEI,
        )
        scheduled_at = scheduled_local.astimezone(UTC)
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


def inspect_prediction_inventory(
    root: Path,
    target: PredictionTarget,
) -> PredictionInventory:
    """Read and validate create-once PRE_DRAW stream coverage for one target."""

    expected = tuple(stream.strategy_id for stream in STRATEGY_STREAMS if stream.enabled)
    if len(expected) != EXPECTED_STREAM_COUNT or len(set(expected)) != EXPECTED_STREAM_COUNT:
        raise SchedulerInvariantError("enabled B649 strategy universe is not exactly 11")
    expected_set = frozenset(expected)
    scheduled_at = _target_scheduled_at(target)
    available: dict[str, str] = {}
    observed: set[str] = set()
    score_required: list[str] = []
    for path in iter_prediction_files(root, target.draw_number):
        prediction = _read_json_object(path)
        if prediction.get("lottery_type") != LOTTERY_TYPE:
            raise SchedulerInvariantError(f"prediction lottery_type conflicts: {path}")
        if prediction.get("draw_number") != target.draw_number:
            raise SchedulerInvariantError(f"prediction draw_number conflicts: {path}")
        strategy_id = _required_text(prediction, "strategy_id", path)
        if strategy_id not in expected_set:
            raise SchedulerInvariantError(f"prediction strategy is outside the 11 streams: {path}")
        observed.add(strategy_id)
        temporal_class = _required_text(prediction, "prediction_temporal_class", path)
        availability = prediction.get("availability", "AVAILABLE")
        created_at = _parse_aware_datetime(
            _required_text(prediction, "prediction_created_at", path),
            "prediction_created_at",
        )
        prediction_scheduled = _parse_aware_datetime(
            _required_text(prediction, "scheduled_at", path),
            "scheduled_at",
        )
        if prediction.get("draw_date") != target.draw_date:
            raise SchedulerInvariantError(f"prediction draw_date conflicts: {path}")
        if prediction_scheduled != scheduled_at:
            raise SchedulerInvariantError(f"prediction scheduled_at conflicts: {path}")
        if temporal_class == "PRE_DRAW":
            if created_at >= scheduled_at:
                raise SchedulerInvariantError(f"PRE_DRAW timestamp is not before deadline: {path}")
            if availability == "AVAILABLE":
                if strategy_id in available:
                    raise SchedulerInvariantError(
                        f"multiple AVAILABLE PRE_DRAW records exist for {strategy_id}"
                    )
                run_id = _required_text(prediction, "prediction_run_id", path)
                tickets = prediction.get("tickets")
                if not isinstance(tickets, list) or not tickets:
                    raise SchedulerInvariantError(f"AVAILABLE prediction has no tickets: {path}")
                available[strategy_id] = run_id
                score_required.append(run_id)
            elif availability not in {"UNAVAILABLE", "TECHNICAL_FAILURE"}:
                raise SchedulerInvariantError(f"prediction availability is invalid: {path}")
        elif temporal_class != "POST_DRAW":
            raise SchedulerInvariantError(f"prediction temporal class is invalid: {path}")
    available_ids = tuple(value for value in expected if value in available)
    observed_ids = tuple(value for value in expected if value in observed)
    return PredictionInventory(
        expected_stream_ids=expected,
        available_stream_ids=available_ids,
        observed_stream_ids=observed_ids,
        score_required_run_ids=tuple(score_required),
    )


def _primary_health_payload(payload: Mapping[str, object]) -> dict[str, object]:
    """Remove the research namespace before persisting primary health."""

    primary = dict(payload)
    primary.pop(SHADOW_HEALTH_NAMESPACE, None)
    return primary


def _run_shadow_hook(
    backend: SchedulerBackend,
    method_name: str,
    target: PredictionTarget,
    observed_at: datetime,
    *,
    primary_status: str,
    canonical_source_head: str,
) -> dict[str, object]:
    hook = getattr(backend, method_name, None)
    if hook is None:
        return shadow_health_not_run(
            "NOT_CONFIGURED",
            target=target,
            primary_status_observed=primary_status,
            canonical_source_head=canonical_source_head,
        )
    try:
        parameters = signature(hook).parameters
        kwargs: dict[str, object] = {}
        if "primary_status" in parameters:
            kwargs["primary_status"] = primary_status
        if "canonical_source_head" in parameters:
            kwargs["canonical_source_head"] = canonical_source_head
        result = hook(target, observed_at, **kwargs)
        if not isinstance(result, dict):
            raise SchedulerInvariantError(
                "research-shadow hook returned a non-object health record"
            )
        return cast(dict[str, object], result)
    except Exception as exc:
        return shadow_health_not_run(
            "ERROR",
            last_error=f"{type(exc).__name__}: {exc}",
            target=target,
            primary_status_observed=primary_status,
            canonical_source_head=canonical_source_head,
        )


def run_scheduler_cycle(
    config: SchedulerConfig,
    backend: SchedulerBackend,
    *,
    clock: Clock = lambda: datetime.now(UTC),
    source_head_resolver: SourceHeadResolver = lambda path: _resolve_source_head(path),
) -> dict[str, object]:
    """Run one locked schedule→primary PRE/POST→isolated shadow→health cycle."""

    try:
        lock = AdvisoryProcessLock(config.lock_path)
        lock.__enter__()
    except SchedulerAlreadyRunning:
        return {
            "schema_version": HEALTH_SCHEMA_VERSION,
            "label": config.label,
            "version": config.version,
            "current_status": "ALREADY_RUNNING",
            "lock_contention": True,
        }

    lock_released = False
    try:
        started_at = _as_utc(clock())
        previous = _read_optional_json_object(config.health_path)
        source_head = source_head_resolver(config.source_worktree)
        running = _base_health(config, started_at, source_head, previous)
        _atomic_health_write(config.health_path, running)
        shadow_summary = shadow_health_not_run(
            "SKIPPED_PRIMARY_NOT_READY", canonical_source_head=source_head
        )
        shadow_hook_name: str | None = None
        shadow_primary_status = "NOT_RUN"
        try:
            announcement = backend.refresh_schedule(started_at)
            target = backend.resolve_target()
            if target is None:
                raise OfficialScheduleUnavailableError(
                    "STOP_OFFICIAL_SCHEDULE_UNAVAILABLE: no target can be resolved"
                )
            inventory = backend.inspect_predictions(target)
            decision_at = _as_utc(clock())
            scheduled_at = _target_scheduled_at(target)
            generation: dict[str, object] = {
                "status": "NOT_DUE",
                "requested_stream_ids": [],
                "created_prediction_paths": [],
                "failures": [],
            }
            official_sync: dict[str, object] = {"status": "NOT_DUE"}
            if decision_at < scheduled_at:
                if inventory.missing_stream_ids:
                    generation = backend.generate_predraw(
                        target,
                        inventory.missing_stream_ids,
                    )
                    generation = {"status": "ATTEMPTED", **generation}
                    inventory = backend.inspect_predictions(target)
                else:
                    generation = {**generation, "status": "NO_OP"}
                postdraw = PostDrawResult(
                    outcome_status="NOT_DUE",
                    scoring_status="NOT_DUE",
                    reporting_status="CURRENT",
                    cycle_action=(
                        "PREDRAW_CREATED"
                        if inventory.ready and generation["status"] == "ATTEMPTED"
                        else "NO_OP"
                        if inventory.ready
                        else "WAITING_FOR_PREDRAW"
                    ),
                )
                terminal_status = "PREDRAW_READY" if inventory.ready else "WAITING_FOR_PREDRAW"
                if inventory.ready:
                    shadow_hook_name = "run_shadow_predraw"
                    shadow_primary_status = "PREDRAW_READY"
                else:
                    shadow_summary = shadow_health_not_run(
                        "SKIPPED_PRIMARY_NOT_READY",
                        target=target,
                        primary_status_observed="WAITING_FOR_PREDRAW",
                        canonical_source_head=source_head,
                    )
            else:
                official_sync = backend.sync_official_outcome(target)
                postdraw = backend.complete_postdraw(target, inventory)
                terminal_status = (
                    "PRE_DRAW_INCOMPLETE"
                    if not inventory.ready
                    else "COMPLETE"
                    if postdraw.outcome_available
                    else "WAITING_FOR_OUTCOME"
                )
                if inventory.ready:
                    shadow_hook_name = "run_shadow_postdraw"
                    shadow_primary_status = (
                        "COMPLETE" if postdraw.outcome_available else "WAITING_FOR_OUTCOME"
                    )
                else:
                    shadow_summary = shadow_health_not_run(
                        "SKIPPED_PRIMARY_NOT_READY",
                        target=target,
                        primary_status_observed="PRE_DRAW_INCOMPLETE",
                        canonical_source_head=source_head,
                    )

            next_target = backend.resolve_target()
            finished_at = _as_utc(clock())
            incomplete = _updated_incomplete_targets(
                previous,
                target=target,
                inventory=inventory,
                scheduled_at=scheduled_at,
                observed_at=decision_at,
            )
            terminal = {
                **running,
                "current_status": terminal_status,
                "finished_at": _utc_text(finished_at),
                "last_success_at": _utc_text(finished_at),
                "current_target": _target_dict(target),
                "next_target": None if next_target is None else _target_dict(next_target),
                "target_draw_date": target.draw_date,
                "readiness_deadline": _utc_text(scheduled_at),
                "expected_stream_count": config.expected_stream_count,
                "actual_available_stream_count": inventory.actual_available_count,
                "ready_before_draw": inventory.ready,
                "prediction_inventory": inventory.health_dict(),
                "prediction_generation": generation,
                "announcement": announcement.health_dict(),
                "official_sync": official_sync,
                "outcome_status": postdraw.outcome_status,
                "scoring_status": postdraw.scoring_status,
                "reporting_status": postdraw.reporting_status,
                "cycle_action": postdraw.cycle_action,
                "lock_contention": False,
                "error_class": None,
                "error_message": None,
                "consecutive_failures": 0,
                "pre_draw_incomplete_targets": incomplete,
            }
            _atomic_health_write(config.health_path, _primary_health_payload(terminal))
            lock.__exit__(None, None, None)
            lock_released = True
            if shadow_hook_name is not None:
                shadow_summary = _run_shadow_hook(
                    backend,
                    shadow_hook_name,
                    target,
                    _as_utc(clock()),
                    primary_status=shadow_primary_status,
                    canonical_source_head=source_head,
                )
            terminal[SHADOW_HEALTH_NAMESPACE] = shadow_summary
            return terminal
        except Exception as exc:
            finished_at = _as_utc(clock())
            failures = _previous_failure_count(previous) + 1
            failed = {
                **running,
                "current_status": "ERROR",
                "finished_at": _utc_text(finished_at),
                "last_success_at": _previous_last_success(previous),
                "lock_contention": False,
                "error_class": type(exc).__name__,
                "error_message": str(exc),
                "consecutive_failures": failures,
                SHADOW_HEALTH_NAMESPACE: shadow_health_not_run(
                    "SKIPPED_PRIMARY_ERROR",
                    last_error=f"primary cycle: {type(exc).__name__}: {exc}",
                    canonical_source_head=source_head,
                ),
            }
            _atomic_health_write(config.health_path, _primary_health_payload(failed))
            return failed
    finally:
        if not lock_released:
            lock.__exit__(None, None, None)


def evaluate_health_status(
    health: Mapping[str, object],
    *,
    now: datetime,
) -> dict[str, object]:
    """Return a deterministic live status, including stale scheduler detection."""

    payload = dict(health)
    recorded = payload.get("current_status")
    payload["recorded_status"] = recorded
    if recorded == "ERROR":
        payload["status"] = "ERROR"
        return payload
    finished = payload.get("finished_at")
    if recorded == "RUNNING" and finished is None:
        finished = payload.get("started_at")
    stale_after = payload.get("stale_after_seconds", STALE_AFTER_SECONDS)
    if type(finished) is not str or type(stale_after) is not int:
        payload["status"] = "ERROR"
        payload["status_error"] = "health record lacks stale-detection fields"
        return payload
    try:
        age = (_as_utc(now) - _parse_utc_text(finished)).total_seconds()
    except (TypeError, ValueError):
        payload["status"] = "ERROR"
        payload["status_error"] = "health record timestamp is invalid"
        return payload
    payload["age_seconds"] = max(0.0, round(age, 3))
    payload["status"] = "STALE" if age > stale_after else recorded
    return payload


def build_launchd_plist(config: SchedulerConfig) -> bytes:
    """Build the exact user LaunchAgent property list."""

    payload: dict[str, object] = {
        "Label": config.label,
        "ProgramArguments": [
            str(config.python_executable),
            str(config.script_path),
            "run",
        ],
        "RunAtLoad": True,
        "StartInterval": config.start_interval_seconds,
        "KeepAlive": False,
        "WorkingDirectory": str(config.canonical_repository),
        "StandardOutPath": str(config.stdout_path),
        "StandardErrorPath": str(config.stderr_path),
        "EnvironmentVariables": {
            DRAW_PROVIDER_SOURCE_ENV: OFFICIAL_TAIWAN_LOTTERY_SOURCE,
            "LOTTOLAB_DATA_DIR": str(config.data_root),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
        },
    }
    return plistlib.dumps(payload, fmt=plistlib.FMT_XML, sort_keys=True)


def write_launchd_plist(config: SchedulerConfig) -> Path:
    """Atomically write and read back only the configured plist path."""

    _ensure_private_directory(config.scheduler_root)
    encoded = build_launchd_plist(config)
    identity = _safe_file_identity(config.plist_path, missing_ok=True)
    _atomic_replace_bytes(
        config.plist_path,
        encoded,
        expected_identity=identity,
        validate=_validate_plist_file,
    )
    if config.plist_path.read_bytes() != encoded:
        raise LocalSchedulerSafetyError("launchd plist readback differs")
    return config.plist_path


def _base_health(
    config: SchedulerConfig,
    started_at: datetime,
    source_head: str,
    previous: Mapping[str, object] | None,
) -> dict[str, object]:
    return {
        "schema_version": HEALTH_SCHEMA_VERSION,
        "label": config.label,
        "version": config.version,
        "canonical_repository": str(config.canonical_repository),
        "source_worktree": str(config.source_worktree),
        "observed_source_head": source_head,
        "started_at": _utc_text(started_at),
        "finished_at": None,
        "last_success_at": _previous_last_success(previous),
        "current_status": "RUNNING",
        "current_target": None,
        "next_target": None,
        "target_draw_date": None,
        "readiness_deadline": None,
        "expected_stream_count": config.expected_stream_count,
        "actual_available_stream_count": 0,
        "ready_before_draw": False,
        "prediction_inventory": None,
        "prediction_generation": None,
        "announcement": None,
        "official_sync": {"status": "NOT_RUN"},
        "outcome_status": "NOT_RUN",
        "scoring_status": "NOT_RUN",
        "reporting_status": "NOT_RUN",
        "cycle_action": "RUNNING",
        "lock_contention": False,
        "error_class": None,
        "error_message": None,
        "consecutive_failures": _previous_failure_count(previous),
        "pre_draw_incomplete_targets": _previous_incomplete_targets(previous),
        "start_interval_seconds": config.start_interval_seconds,
        "stale_after_seconds": config.stale_after_seconds,
    }


def _updated_incomplete_targets(
    previous: Mapping[str, object] | None,
    *,
    target: PredictionTarget,
    inventory: PredictionInventory,
    scheduled_at: datetime,
    observed_at: datetime,
) -> list[dict[str, object]]:
    records = {
        cast(str, item["draw_number"]): dict(item)
        for item in _previous_incomplete_targets(previous)
        if type(item.get("draw_number")) is str
    }
    if observed_at >= scheduled_at and not inventory.ready:
        records[target.draw_number] = {
            "lottery_type": target.lottery_type,
            "draw_number": target.draw_number,
            "draw_date": target.draw_date,
            "scheduled_at": _utc_text(scheduled_at),
            "expected_stream_count": len(inventory.expected_stream_ids),
            "actual_available_stream_count": inventory.actual_available_count,
            "missing_stream_ids": list(inventory.missing_stream_ids),
        }
    return [records[key] for key in sorted(records, key=int)]


def _previous_incomplete_targets(
    previous: Mapping[str, object] | None,
) -> list[dict[str, object]]:
    if previous is None:
        return []
    raw = previous.get("pre_draw_incomplete_targets")
    if not isinstance(raw, list):
        return []
    result: list[dict[str, object]] = []
    for item in cast(list[object], raw):
        if isinstance(item, dict):
            result.append(cast(dict[str, object], item))
    return result


def _previous_last_success(previous: Mapping[str, object] | None) -> object:
    return None if previous is None else previous.get("last_success_at")


def _previous_failure_count(previous: Mapping[str, object] | None) -> int:
    if previous is None:
        return 0
    value = previous.get("consecutive_failures", 0)
    return value if type(value) is int and value >= 0 else 0


def _target_scheduled_at(target: PredictionTarget) -> datetime:
    value = _parse_aware_datetime(target.scheduled_at, "target scheduled_at")
    if value.astimezone(TAIPEI).date().isoformat() != target.draw_date:
        raise SchedulerInvariantError("target scheduled_at local date conflicts")
    return value


def _target_dict(target: PredictionTarget) -> dict[str, object]:
    return {
        "lottery_type": target.lottery_type,
        "draw_number": target.draw_number,
        "draw_date": target.draw_date,
        "scheduled_at": _utc_text(_target_scheduled_at(target)),
    }


def _missing_score_run_ids(
    root: Path,
    draw_number: str,
    required_run_ids: Sequence[str],
) -> tuple[str, ...]:
    return tuple(
        run_id
        for run_id in required_run_ids
        if not (root / "scores" / draw_number / f"{run_id}.json").is_file()
    )


def _reporting_paths_current(root: Path) -> bool:
    return all(
        (root / name).is_file()
        for name in (
            "performance.jsonl",
            "research-summary.json",
            "head_to_head.jsonl",
            "history_freshness.jsonl",
        )
    )


def _new_scheduler_prediction_run_id(
    target: PredictionTarget,
    stream: StrategyStream,
    observed_at: datetime,
) -> str:
    local = observed_at.astimezone(TAIPEI)
    stamp = local.strftime("%Y%m%dT%H%M%S%f%z").replace("+", "p").replace("-", "m")
    return f"{target.draw_number}-{stream.strategy_id}-{stamp}-{uuid4().hex[:8]}"


def _encode_operational_announcements(
    announcements: Sequence[TargetAnnouncement],
) -> bytes:
    rows: list[dict[str, object]] = []
    for announcement in announcements:
        rows.append(
            {
                "schedule_timezone": announcement.schedule_timezone,
                "scheduled_at": _utc_text(announcement.scheduled_at),
                "source": {
                    "observed_at": _utc_text(announcement.source.observed_at),
                    "source_id": announcement.source.source_id,
                    "source_locator": announcement.source.source_locator,
                    "source_payload_sha256": announcement.source.source_sha256,
                    "source_version": announcement.source.source_version,
                },
                "target": announcement.target.canonical_dict(),
            }
        )
    payload = {
        "schema_version": OPERATIONAL_ANNOUNCEMENT_SCHEMA_VERSION,
        "announcements": rows,
    }
    return (_canonical_json(payload) + "\n").encode("utf-8")


def _announcement_sort_key(
    announcement: TargetAnnouncement,
) -> tuple[datetime, str, str, int, str]:
    return (
        announcement.scheduled_at,
        announcement.target.lottery_type.value,
        announcement.target.draw_date.isoformat(),
        int(announcement.target.draw_number),
        announcement.target.draw_number,
    )


def _is_official_b649_announcement(
    announcement: TargetAnnouncement,
    *,
    source_url: str,
) -> bool:
    return (
        announcement.target.lottery_type is LotteryType.BIG_LOTTO
        and announcement.schedule_timezone == SCHEDULE_TIMEZONE
        and announcement.source.source_id == OFFICIAL_SCHEDULE_SOURCE_ID
        and announcement.source.source_version == OFFICIAL_SCHEDULE_SOURCE_VERSION
        and announcement.source.source_locator == source_url
    )


def _validate_official_https_url(url: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in _OFFICIAL_HTTPS_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or parsed.fragment
    ):
        raise GoalCSchedulerError(
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
        raise GoalCSchedulerError("official HTTPS response exceeds the bounded size limit")
    return body


def _require_secure_tls_context(context: ssl.SSLContext) -> None:
    if context.verify_mode is not ssl.CERT_REQUIRED or not context.check_hostname:
        raise GoalCSchedulerError("TLS certificate and hostname verification must remain enabled")


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


@dataclass(frozen=True, slots=True)
class _FileIdentity:
    device: int
    inode: int
    mode: int
    uid: int
    links: int
    size: int
    modified_ns: int


def _safe_file_identity(path: Path, *, missing_ok: bool) -> _FileIdentity | None:
    try:
        metadata = os.lstat(path)
    except FileNotFoundError:
        if missing_ok:
            return None
        raise LocalSchedulerSafetyError(f"required file does not exist: {path}") from None
    if not stat.S_ISREG(metadata.st_mode):
        raise LocalSchedulerSafetyError(f"path must be a regular file: {path}")
    if metadata.st_uid != os.getuid():
        raise LocalSchedulerSafetyError(f"path must be owned by the current user: {path}")
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise LocalSchedulerSafetyError(f"path mode must be exactly 0600: {path}")
    if metadata.st_nlink != 1:
        raise LocalSchedulerSafetyError(f"path must have exactly one hard link: {path}")
    return _FileIdentity(
        device=metadata.st_dev,
        inode=metadata.st_ino,
        mode=metadata.st_mode,
        uid=metadata.st_uid,
        links=metadata.st_nlink,
        size=metadata.st_size,
        modified_ns=metadata.st_mtime_ns,
    )


def _atomic_replace_bytes(
    path: Path,
    encoded: bytes,
    *,
    expected_identity: _FileIdentity | None,
    validate: Callable[[Path], object] | None = None,
) -> None:
    if not path.parent.is_dir():
        raise LocalSchedulerSafetyError(f"destination directory does not exist: {path.parent}")
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    descriptor: int | None = None
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW | _CLOEXEC,
            0o600,
        )
        os.fchmod(descriptor, 0o600)
        _validate_owned_regular_descriptor(descriptor, "temporary file", mode=0o600)
        view = memoryview(encoded)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        if validate is not None:
            validate(temporary)
        if _safe_file_identity(path, missing_ok=True) != expected_identity:
            raise LocalSchedulerSafetyError(f"destination changed during atomic write: {path}")
        os.replace(temporary, path)
        directory_descriptor = os.open(path.parent, os.O_RDONLY | _CLOEXEC)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
        _safe_file_identity(path, missing_ok=False)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        with suppress(FileNotFoundError):
            temporary.unlink()


def _atomic_health_write(path: Path, value: Mapping[str, object]) -> None:
    _ensure_private_directory(path.parent)
    encoded = (_canonical_json(value) + "\n").encode("utf-8")
    identity = _safe_file_identity(path, missing_ok=True)
    _atomic_replace_bytes(path, encoded, expected_identity=identity, validate=_validate_json_file)


def _ensure_private_directory(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    metadata = os.lstat(path)
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        raise LocalSchedulerSafetyError(f"scheduler directory must be owner-only: {path}")


def _validate_owned_directory(path: Path, *, mode: int) -> None:
    try:
        metadata = os.lstat(path)
    except FileNotFoundError as exc:
        raise LocalSchedulerSafetyError(f"required directory does not exist: {path}") from exc
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) != mode
    ):
        raise LocalSchedulerSafetyError(
            f"directory must be current-user owned with mode {mode:04o}: {path}"
        )


def _validate_owned_regular_descriptor(descriptor: int, label: str, *, mode: int) -> None:
    metadata = os.fstat(descriptor)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) != mode
        or metadata.st_nlink != 1
    ):
        raise LocalSchedulerSafetyError(f"{label} has an unsafe filesystem identity")


def _validate_json_file(path: Path) -> None:
    _read_json_object(path)


def _validate_plist_file(path: Path) -> None:
    with path.open("rb") as handle:
        parsed = plistlib.load(handle)
    if not isinstance(parsed, dict):
        raise LocalSchedulerSafetyError("launchd plist must decode to one dictionary")


def _read_optional_json_object(path: Path) -> dict[str, object] | None:
    identity = _safe_file_identity(path, missing_ok=True)
    if identity is None:
        return None
    return _read_json_object(path)


def _read_json_object(path: Path) -> dict[str, object]:
    try:
        parsed: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LocalSchedulerSafetyError(f"JSON file is invalid: {path}") from exc
    if not isinstance(parsed, dict):
        raise LocalSchedulerSafetyError(f"JSON file must contain one object: {path}")
    mapping = cast(dict[object, object], parsed)
    if any(type(key) is not str for key in mapping):
        raise LocalSchedulerSafetyError(f"JSON file must contain one object: {path}")
    return cast(dict[str, object], mapping)


def _required_text(value: Mapping[str, object], key: str, path: Path) -> str:
    result = value.get(key)
    if type(result) is not str or not result:
        raise SchedulerInvariantError(f"{key} must be non-empty text: {path}")
    return result


def _parse_aware_datetime(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise SchedulerInvariantError(f"{label} must be an ISO datetime") from exc
    if parsed.tzinfo is None:
        raise SchedulerInvariantError(f"{label} must be timezone-aware")
    return parsed.astimezone(UTC)


def _parse_utc_text(value: str) -> datetime:
    if not value.endswith("Z"):
        raise ValueError("timestamp must use UTC Z text")
    parsed = datetime.fromisoformat(f"{value[:-1]}+00:00")
    if parsed.tzinfo is not UTC:
        raise ValueError("timestamp must use UTC")
    return parsed


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("scheduler clock must be timezone-aware")
    return value.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return _as_utc(value).isoformat().replace("+00:00", "Z")


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _resolve_source_head(worktree: Path) -> str:
    completed = subprocess.run(
        ["/usr/bin/git", "-C", str(worktree), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    value = completed.stdout.strip()
    if re.fullmatch(r"[0-9a-f]{40}", value, flags=re.ASCII) is None:
        raise SchedulerInvariantError("observed source HEAD is invalid")
    return value


def _status_command(config: SchedulerConfig, *, clock: Clock) -> tuple[dict[str, object], int]:
    health = _read_optional_json_object(config.health_path)
    if health is None:
        return {"status": "NOT_CONFIGURED", "health_path": str(config.health_path)}, 1
    evaluated = evaluate_health_status(health, now=clock())
    return evaluated, 1 if evaluated["status"] in {"ERROR", "STALE"} else 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("run", help="Run one locked scheduler cycle.")
    commands.add_parser("status", help="Report live health, including stale detection.")
    commands.add_parser("write-plist", help="Atomically emit the exact user LaunchAgent plist.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = production_config()
    if args.command == "write-plist":
        path = write_launchd_plist(config)
        print(_canonical_json({"status": "WRITTEN", "plist_path": str(path)}))
        return 0
    if args.command == "status":
        result, exit_code = _status_command(config, clock=lambda: datetime.now(UTC))
        print(_canonical_json(result))
        return exit_code

    def clock() -> datetime:
        return datetime.now(UTC)

    try:
        backend = ProductionSchedulerBackend(config, clock=clock)
        result = run_scheduler_cycle(config, backend, clock=clock)
    except Exception as exc:
        result = {
            "schema_version": HEALTH_SCHEMA_VERSION,
            "label": config.label,
            "version": config.version,
            "current_status": "ERROR",
            "error_class": type(exc).__name__,
            "error_message": str(exc),
        }
    print(_canonical_json(result))
    return 1 if result.get("current_status") == "ERROR" else 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "AdvisoryProcessLock",
    "OfficialHttpsClient",
    "OfficialScheduleUnavailableError",
    "PostDrawResult",
    "PredictionInventory",
    "ProductionSchedulerBackend",
    "ScheduleRefreshResult",
    "SchedulerAlreadyRunning",
    "SchedulerConfig",
    "build_launchd_plist",
    "evaluate_health_status",
    "inspect_prediction_inventory",
    "parse_official_b649_schedule",
    "production_config",
    "refresh_official_schedule",
    "run_scheduler_cycle",
    "write_launchd_plist",
]
