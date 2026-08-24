"""Focused acceptance coverage for the durable local B649 Goal-C scheduler."""

from __future__ import annotations

import hashlib
import json
import os
import plistlib
import ssl
import stat
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from inspect import getsource
from pathlib import Path
from typing import cast
from urllib.error import URLError

import pytest
import tools.b649_goalc_local_scheduler as scheduler_module
from tools.b649_goalc_local_scheduler import (
    SHADOW_HEALTH_NAMESPACE,
    AdvisoryProcessLock,
    OfficialHttpsClient,
    OfficialScheduleUnavailableError,
    PostDrawResult,
    PredictionInventory,
    ProductionSchedulerBackend,
    SchedulerAlreadyRunning,
    SchedulerConfig,
    ScheduleRefreshResult,
    SchedulerInvariantError,
    build_launchd_plist,
    evaluate_health_status,
    inspect_prediction_inventory,
    parse_official_b649_schedule,
    production_config,
    refresh_official_schedule,
    run_scheduler_cycle,
)
from tools.b649_operational_prediction_loop import (
    LOTTERY_TYPE,
    STRATEGY_STREAMS,
    PredictionTarget,
)

from lottolab.application.pre_outcome_target_operational import (
    TargetAnnouncementSourceStatus,
)
from lottolab.domain.draw_data_integrity import (
    DrawDataIntegrityReport,
    DrawDataIntegrityStatus,
)
from lottolab.domain.draws import LotteryType
from lottolab.infrastructure.pre_outcome_target_operational import (
    OFFICIAL_SCHEDULE_SOURCE_ID,
    OFFICIAL_SCHEDULE_SOURCE_VERSION,
    OPERATIONAL_ANNOUNCEMENT_SCHEMA_VERSION,
    FileSystemOperationalTargetAnnouncementSource,
)

NOW = datetime(2099, 1, 2, 10, 0, tzinfo=UTC)
SCHEDULED = datetime(2099, 1, 2, 12, 30, tzinfo=UTC)
STREAM_IDS = tuple(stream.strategy_id for stream in STRATEGY_STREAMS if stream.enabled)
SOURCE_HEAD = "f" * 40


def _config(tmp_path: Path) -> SchedulerConfig:
    repository = tmp_path / "repo"
    source = tmp_path / "source"
    data = tmp_path / "data"
    operation = tmp_path / "goalc"
    launch_agents = tmp_path / "LaunchAgents"
    for path in (repository, source, data, operation, launch_agents):
        path.mkdir(mode=0o700)
        path.chmod(0o700)
    scheduler = operation / "scheduler"
    return SchedulerConfig(
        label="com.lottolab.b649-goalc-r1",
        version="B649_GOALC_LOCAL_LAUNCHD_R1",
        canonical_repository=repository,
        source_worktree=source,
        python_executable=repository / ".venv/bin/python",
        script_path=source / "tools/b649_goalc_local_scheduler.py",
        operation_root=operation,
        data_root=data,
        database=data / "lottolab.db",
        announcement=data / "pre-outcome-target-announcements-v1.json",
        scheduler_root=scheduler,
        lock_path=scheduler / "b649-goalc.lock",
        health_path=scheduler / "health.json",
        stdout_path=scheduler / "launchd.stdout.log",
        stderr_path=scheduler / "launchd.stderr.log",
        plist_path=launch_agents / "com.lottolab.b649-goalc-r1.plist",
    )


def _target(*, scheduled_at: datetime = SCHEDULED) -> PredictionTarget:
    return PredictionTarget(
        lottery_type=LOTTERY_TYPE,
        draw_number="209900001",
        draw_date=scheduled_at.astimezone(scheduler_module.TAIPEI).date().isoformat(),
        scheduled_at=scheduled_at.astimezone(scheduler_module.TAIPEI).isoformat(),
    )


def _inventory(count: int) -> PredictionInventory:
    return PredictionInventory(
        expected_stream_ids=STREAM_IDS,
        available_stream_ids=STREAM_IDS[:count],
        observed_stream_ids=STREAM_IDS[:count],
        score_required_run_ids=tuple(f"run-{index}" for index in range(count)),
    )


def _schedule_body(
    *,
    draw_date: str = "20990103",
    draw_number: int | str | None = 209900002,
) -> bytes:
    return json.dumps(
        {
            "rtCode": 0,
            "rtMsg": None,
            "content": {
                "nextDrawDateList": [
                    {
                        "gameCode": 5118,
                        "drawDate": draw_date,
                        "drawTerm": draw_number,
                    },
                    {
                        "gameCode": 5134,
                        "drawDate": "20990104",
                        "drawTerm": 209900003,
                    },
                ]
            },
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def _announcement_item(
    lottery_type: LotteryType,
    draw_number: str,
    *,
    draw_date: str,
    scheduled_at: str,
) -> dict[str, object]:
    return {
        "schedule_timezone": "Asia/Taipei",
        "scheduled_at": scheduled_at,
        "source": {
            "observed_at": "2099-01-01T00:00:00Z",
            "source_id": OFFICIAL_SCHEDULE_SOURCE_ID,
            "source_locator": scheduler_module.SCHEDULE_URL,
            "source_payload_sha256": hashlib.sha256(draw_number.encode()).hexdigest(),
            "source_version": OFFICIAL_SCHEDULE_SOURCE_VERSION,
        },
        "target": {
            "lottery_type": lottery_type.value,
            "draw_number": draw_number,
            "draw_date": draw_date,
        },
    }


def _write_announcement(path: Path, *items: dict[str, object]) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": OPERATIONAL_ANNOUNCEMENT_SCHEMA_VERSION,
                "announcements": list(items),
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    path.chmod(0o600)


def _prediction(
    target: PredictionTarget,
    strategy_id: str,
    *,
    run_suffix: str = "one",
    created_at: datetime = NOW,
    temporal_class: str = "PRE_DRAW",
    availability: str = "AVAILABLE",
) -> dict[str, object]:
    return {
        "lottery_type": target.lottery_type,
        "draw_number": target.draw_number,
        "draw_date": target.draw_date,
        "scheduled_at": target.scheduled_at,
        "prediction_created_at": created_at.isoformat(),
        "prediction_temporal_class": temporal_class,
        "strategy_id": strategy_id,
        "prediction_run_id": f"{target.draw_number}-{strategy_id}-{run_suffix}",
        "availability": availability,
        "tickets": (
            [{"ticket_position": 1, "predicted_numbers": [1, 2, 3, 4, 5, 6]}]
            if availability == "AVAILABLE"
            else []
        ),
    }


def _write_prediction(
    root: Path,
    target: PredictionTarget,
    strategy_id: str,
    *,
    run_suffix: str = "one",
    created_at: datetime = NOW,
    temporal_class: str = "PRE_DRAW",
    availability: str = "AVAILABLE",
) -> Path:
    path = root / "predictions" / target.draw_number / strategy_id / "prediction.json"
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    payload = _prediction(
        target,
        strategy_id,
        run_suffix=run_suffix,
        created_at=created_at,
        temporal_class=temporal_class,
        availability=availability,
    )
    path.write_text(json.dumps(payload), encoding="utf-8")
    path.chmod(0o600)
    return path


class _FakeBackend:
    def __init__(
        self,
        *,
        target: PredictionTarget,
        inventories: Sequence[PredictionInventory],
        postdraw: PostDrawResult | None = None,
        fail_refresh: Exception | None = None,
    ) -> None:
        self.target = target
        self.inventories = list(inventories)
        self.postdraw = postdraw or PostDrawResult(
            outcome_status="WAITING_FOR_OUTCOME",
            scoring_status="WAITING_FOR_OUTCOME",
            reporting_status="CURRENT",
            cycle_action="WAITING_FOR_OUTCOME",
        )
        self.fail_refresh = fail_refresh
        self.generation_calls: list[tuple[str, ...]] = []
        self.sync_calls = 0
        self.complete_calls = 0

    def refresh_schedule(self, observed_at: datetime) -> ScheduleRefreshResult:
        if self.fail_refresh is not None:
            raise self.fail_refresh
        return ScheduleRefreshResult(
            status="REFRESHED",
            source_url=scheduler_module.SCHEDULE_URL,
            source_payload_sha256="a" * 64,
            observed_at=observed_at,
            inventory_count=1,
            b649_targets=(self.target.draw_number,),
            strict_tls_fallback_used=False,
        )

    def resolve_target(self) -> PredictionTarget:
        return self.target

    def inspect_predictions(self, target: PredictionTarget) -> PredictionInventory:
        assert target == self.target
        if len(self.inventories) > 1:
            return self.inventories.pop(0)
        return self.inventories[0]

    def generate_predraw(
        self,
        target: PredictionTarget,
        missing_stream_ids: Sequence[str],
    ) -> dict[str, object]:
        assert target == self.target
        call = tuple(missing_stream_ids)
        self.generation_calls.append(call)
        return {
            "requested_stream_ids": list(call),
            "created_prediction_paths": ["fixture.json"],
            "failures": [],
        }

    def sync_official_outcome(self, target: PredictionTarget) -> dict[str, object]:
        assert target == self.target
        self.sync_calls += 1
        return {"status": "SUCCESS", "fetched_count": 0}

    def complete_postdraw(
        self,
        target: PredictionTarget,
        inventory: PredictionInventory,
    ) -> PostDrawResult:
        assert target == self.target
        assert inventory is self.inventories[-1]
        self.complete_calls += 1
        return self.postdraw


class _ShadowHookBackend(_FakeBackend):
    def __init__(
        self,
        *,
        target: PredictionTarget,
        inventories: Sequence[PredictionInventory],
        postdraw: PostDrawResult | None = None,
        fail_refresh: Exception | None = None,
        lock_path: Path | None = None,
    ) -> None:
        super().__init__(
            target=target,
            inventories=inventories,
            postdraw=postdraw,
            fail_refresh=fail_refresh,
        )
        self.shadow_predraw_calls: list[tuple[str, str, str]] = []
        self.shadow_postdraw_calls: list[tuple[str, str, str]] = []
        self.lock_path = lock_path
        self.shadow_lock_available: bool | None = None

    def _probe_primary_lock(self) -> None:
        if self.lock_path is None:
            return
        try:
            with AdvisoryProcessLock(self.lock_path):
                pass
        except SchedulerAlreadyRunning:
            self.shadow_lock_available = False
        else:
            self.shadow_lock_available = True

    def run_shadow_predraw(
        self,
        target: PredictionTarget,
        observed_at: datetime,
        *,
        primary_status: str,
        canonical_source_head: str,
    ) -> dict[str, object]:
        self._probe_primary_lock()
        self.shadow_predraw_calls.append(
            (target.draw_number, primary_status, canonical_source_head)
        )
        return {
            "namespace": SHADOW_HEALTH_NAMESPACE,
            "status": "PREDRAW_COMPLETE",
            "observed_at": observed_at.isoformat(),
        }

    def run_shadow_postdraw(
        self,
        target: PredictionTarget,
        observed_at: datetime,
        *,
        primary_status: str,
        canonical_source_head: str,
    ) -> dict[str, object]:
        self._probe_primary_lock()
        self.shadow_postdraw_calls.append(
            (target.draw_number, primary_status, canonical_source_head)
        )
        return {
            "namespace": SHADOW_HEALTH_NAMESPACE,
            "status": "WAITING_FOR_OUTCOME",
            "observed_at": observed_at.isoformat(),
        }


class _ShadowFailureBackend(_ShadowHookBackend):
    def run_shadow_predraw(
        self,
        target: PredictionTarget,
        observed_at: datetime,
        *,
        primary_status: str,
        canonical_source_head: str,
    ) -> dict[str, object]:
        del target, observed_at, primary_status, canonical_source_head
        raise RuntimeError("shadow fixture failed")


def test_production_config_is_the_exact_authorized_runtime() -> None:
    config = production_config()
    canonical_repository = Path("/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis")

    assert config.label == "com.lottolab.b649-goalc-r1"
    assert config.start_interval_seconds == 300
    assert config.stale_after_seconds == 900
    assert config.expected_stream_count == len(STREAM_IDS) == 11
    assert config.canonical_repository == canonical_repository
    assert config.source_worktree == canonical_repository
    assert config.script_path == (canonical_repository / "tools/b649_goalc_local_scheduler.py")
    assert config.operation_root == Path(
        "/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_OPERATIONAL_PREDICTION_LOOP_R1"
    )
    assert config.health_path == config.operation_root / "scheduler/health.json"


def test_production_launchd_uses_only_canonical_scheduler_authority() -> None:
    config = production_config()
    canonical_script = config.canonical_repository / "tools/b649_goalc_local_scheduler.py"

    encoded = build_launchd_plist(config)
    parsed = plistlib.loads(encoded)

    assert parsed["ProgramArguments"][1] == str(canonical_script)
    assert parsed["WorkingDirectory"] == str(config.canonical_repository)
    assert b"B649_GOALC_LOCAL_LAUNCHD_R1" not in encoded


def test_parse_official_schedule_derives_the_existing_2030_taipei_contract() -> None:
    body = _schedule_body()

    parsed = parse_official_b649_schedule(body, observed_at=NOW)

    assert len(parsed) == 1
    announcement = parsed[0]
    assert announcement.target.lottery_type is LotteryType.BIG_LOTTO
    assert announcement.target.draw_number == "209900002"
    assert announcement.target.draw_date.isoformat() == "2099-01-03"
    assert announcement.scheduled_at == datetime(2099, 1, 3, 12, 30, tzinfo=UTC)
    assert announcement.schedule_timezone == "Asia/Taipei"
    assert announcement.source.source_sha256 == hashlib.sha256(body).hexdigest()


@pytest.mark.parametrize(
    "body",
    [
        b"not-json",
        b'{"rtCode":1,"content":{"nextDrawDateList":[]}}',
        _schedule_body(draw_number=None),
        _schedule_body(draw_date="2099-01-03"),
    ],
)
def test_parse_official_schedule_rejects_unusable_or_malformed_authority(
    body: bytes,
) -> None:
    with pytest.raises(OfficialScheduleUnavailableError):
        parse_official_b649_schedule(body, observed_at=NOW)


def test_schedule_refresh_atomically_replaces_only_b649_and_preserves_mode(
    tmp_path: Path,
) -> None:
    data = tmp_path / "data"
    data.mkdir(mode=0o700)
    path = data / "pre-outcome-target-announcements-v1.json"
    _write_announcement(
        path,
        _announcement_item(
            LotteryType.BIG_LOTTO,
            "209900001",
            draw_date="2099-01-02",
            scheduled_at="2099-01-02T12:30:00Z",
        ),
        _announcement_item(
            LotteryType.POWER_LOTTO,
            "209900099",
            draw_date="2099-01-04",
            scheduled_at="2099-01-04T12:30:00Z",
        ),
    )
    body = _schedule_body()
    client = OfficialHttpsClient(transport=lambda _request, _context, _timeout, _limit: body)

    result = refresh_official_schedule(path, client=client, observed_at=NOW)

    inventory = FileSystemOperationalTargetAnnouncementSource(path).read()
    assert inventory.status is TargetAnnouncementSourceStatus.AVAILABLE
    identities = {
        (item.target.lottery_type, item.target.draw_number) for item in inventory.announcements
    }
    assert identities == {
        (LotteryType.BIG_LOTTO, "209900002"),
        (LotteryType.POWER_LOTTO, "209900099"),
    }
    assert result.b649_targets == ("209900002",)
    assert result.source_payload_sha256 == hashlib.sha256(body).hexdigest()
    metadata = os.lstat(path)
    assert stat.S_ISREG(metadata.st_mode)
    assert stat.S_IMODE(metadata.st_mode) == 0o600
    assert metadata.st_uid == os.getuid()
    assert metadata.st_nlink == 1


def test_production_scheduler_neither_refreshes_nor_selects_legacy_announcement(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    _write_announcement(
        config.announcement,
        _announcement_item(
            LotteryType.BIG_LOTTO,
            "209900000",
            draw_date="2099-01-01",
            scheduled_at="2099-01-01T12:30:00Z",
        ),
        _announcement_item(
            LotteryType.BIG_LOTTO,
            "209900001",
            draw_date="2099-01-02",
            scheduled_at="2099-01-02T12:30:00Z",
        ),
    )
    after_deadline = SCHEDULED + timedelta(minutes=5)
    network_calls = 0

    def reject_network(
        _request: scheduler_module.Request,
        _context: ssl.SSLContext,
        _timeout: float,
        _limit: int,
    ) -> bytes:
        nonlocal network_calls
        network_calls += 1
        raise AssertionError("production schedule selection must not use the network")

    before = config.announcement.read_bytes()
    backend = ProductionSchedulerBackend(
        config,
        clock=lambda: after_deadline,
        https_client=OfficialHttpsClient(
            transport=reject_network
        ),
        environ={
            "LOTTOLAB_DRAW_PROVIDER_SOURCE": "OFFICIAL_TAIWAN_LOTTERY",
            "LOTTOLAB_DATA_DIR": str(config.data_root),
        },
    )

    refresh = backend.refresh_schedule(after_deadline)

    assert refresh.status == "DB_ONLY_NO_AUTO_SUPPLEMENT"
    assert refresh.source_url is None
    assert refresh.source_payload_sha256 is None
    assert refresh.b649_targets == ()
    assert refresh.inventory_count == 0
    assert backend.resolve_target() is None
    assert network_calls == 0
    assert config.announcement.read_bytes() == before
    assert not (config.operation_root / "predictions").exists()


def test_production_scheduler_has_no_automatic_legacy_schedule_wiring() -> None:
    source = getsource(ProductionSchedulerBackend)

    assert "refresh_official_schedule" not in source
    assert "FileSystemOperationalTargetAnnouncementSource" not in source
    assert "_resolve_latest_unrecorded_missed_target" not in source


def test_failed_schedule_validation_leaves_existing_authority_byte_identical(
    tmp_path: Path,
) -> None:
    data = tmp_path / "data"
    data.mkdir(mode=0o700)
    path = data / "pre-outcome-target-announcements-v1.json"
    _write_announcement(
        path,
        _announcement_item(
            LotteryType.BIG_LOTTO,
            "209900001",
            draw_date="2099-01-02",
            scheduled_at="2099-01-02T12:30:00Z",
        ),
    )
    before = path.read_bytes()
    client = OfficialHttpsClient(transport=lambda _request, _context, _timeout, _limit: b"invalid")

    with pytest.raises(OfficialScheduleUnavailableError):
        refresh_official_schedule(path, client=client, observed_at=NOW)

    assert path.read_bytes() == before


def test_schedule_refresh_rejects_symlink_before_network_access(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir(mode=0o700)
    target = data / "target.json"
    target.write_text("{}", encoding="utf-8")
    target.chmod(0o600)
    path = data / "pre-outcome-target-announcements-v1.json"
    path.symlink_to(target)
    calls = 0

    def transport(
        _request: scheduler_module.Request,
        _context: ssl.SSLContext,
        _timeout: float,
        _limit: int,
    ) -> bytes:
        nonlocal calls
        calls += 1
        return _schedule_body()

    with pytest.raises(scheduler_module.LocalSchedulerSafetyError):
        refresh_official_schedule(
            path,
            client=OfficialHttpsClient(transport=transport),
            observed_at=NOW,
        )

    assert calls == 0


@pytest.mark.parametrize(
    "verification_message",
    ["Missing Authority Key Identifier", "Missing Subject Key Identifier"],
)
def test_https_client_allows_only_strict_chain_retry_and_keeps_tls_checks(
    monkeypatch: pytest.MonkeyPatch,
    verification_message: str,
) -> None:
    strict_flag = ssl.VERIFY_X509_STRICT
    original_context = ssl.create_default_context

    def strict_context() -> ssl.SSLContext:
        context = original_context()
        context.verify_flags |= strict_flag
        return context

    monkeypatch.setattr(ssl, "create_default_context", strict_context)
    contexts: list[ssl.SSLContext] = []

    def transport(
        _request: scheduler_module.Request,
        context: ssl.SSLContext,
        _timeout: float,
        _limit: int,
    ) -> bytes:
        contexts.append(context)
        if len(contexts) == 1:
            raise ssl.SSLCertVerificationError(1, verification_message)
        return b"ok"

    client = OfficialHttpsClient(transport=transport)

    assert client.get(scheduler_module.SCHEDULE_URL, max_response_bytes=10) == b"ok"
    assert client.strict_tls_fallback_used is True
    assert len(contexts) == 2
    assert contexts[0].verify_flags & strict_flag
    assert not contexts[1].verify_flags & strict_flag
    assert all(context.verify_mode is ssl.CERT_REQUIRED for context in contexts)
    assert all(context.check_hostname for context in contexts)


def test_https_client_never_retries_hostname_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_context = ssl.create_default_context

    def strict_context() -> ssl.SSLContext:
        context = original_context()
        context.verify_flags |= ssl.VERIFY_X509_STRICT
        return context

    monkeypatch.setattr(ssl, "create_default_context", strict_context)
    calls = 0

    def transport(
        _request: scheduler_module.Request,
        _context: ssl.SSLContext,
        _timeout: float,
        _limit: int,
    ) -> bytes:
        nonlocal calls
        calls += 1
        raise URLError(ssl.SSLCertVerificationError(1, "hostname mismatch"))

    client = OfficialHttpsClient(transport=transport)

    with pytest.raises(URLError):
        client.get(scheduler_module.SCHEDULE_URL, max_response_bytes=10)
    assert calls == 1
    assert client.strict_tls_fallback_used is False


def test_https_client_rejects_unapproved_or_credentialed_urls_before_transport() -> None:
    calls = 0

    def transport(
        _request: scheduler_module.Request,
        _context: ssl.SSLContext,
        _timeout: float,
        _limit: int,
    ) -> bytes:
        nonlocal calls
        calls += 1
        return b"unexpected"

    client = OfficialHttpsClient(transport=transport)
    for url in (
        "http://api.taiwanlottery.com/path",
        "https://user@api.taiwanlottery.com/path",
        "https://example.test/path",
    ):
        with pytest.raises(scheduler_module.GoalCSchedulerError):
            client.get(url, max_response_bytes=10)
    assert calls == 0


def test_prediction_inventory_requires_exactly_one_available_predraw_per_stream(
    tmp_path: Path,
) -> None:
    target = _target()
    for strategy_id in STREAM_IDS:
        _write_prediction(tmp_path, target, strategy_id)

    inventory = inspect_prediction_inventory(tmp_path, target)

    assert inventory.ready is True
    assert inventory.actual_available_count == 11
    assert inventory.available_stream_ids == STREAM_IDS
    assert inventory.missing_stream_ids == ()


def test_prediction_inventory_does_not_count_unavailable_or_postdraw_records(
    tmp_path: Path,
) -> None:
    target = _target()
    _write_prediction(
        tmp_path,
        target,
        STREAM_IDS[0],
        availability="TECHNICAL_FAILURE",
    )
    _write_prediction(
        tmp_path,
        target,
        STREAM_IDS[1],
        temporal_class="POST_DRAW",
        created_at=SCHEDULED,
    )

    inventory = inspect_prediction_inventory(tmp_path, target)

    assert inventory.actual_available_count == 0
    assert inventory.observed_stream_ids == STREAM_IDS[:2]
    assert inventory.missing_stream_ids == STREAM_IDS


def test_prediction_inventory_rejects_duplicate_or_late_predraw(
    tmp_path: Path,
) -> None:
    target = _target()
    first = _write_prediction(tmp_path, target, STREAM_IDS[0])
    duplicate = first.with_name("duplicate.json")
    duplicate.write_text(
        json.dumps(_prediction(target, STREAM_IDS[0], run_suffix="two")),
        encoding="utf-8",
    )
    duplicate.chmod(0o600)

    with pytest.raises(SchedulerInvariantError, match="multiple AVAILABLE"):
        inspect_prediction_inventory(tmp_path, target)

    duplicate.unlink()
    first.write_text(
        json.dumps(_prediction(target, STREAM_IDS[0], created_at=SCHEDULED)),
        encoding="utf-8",
    )
    with pytest.raises(SchedulerInvariantError, match="not before deadline"):
        inspect_prediction_inventory(tmp_path, target)


def test_predraw_cycle_generates_only_missing_then_reports_exact_readiness(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    backend = _FakeBackend(
        target=_target(),
        inventories=(_inventory(10), _inventory(11)),
    )

    result = run_scheduler_cycle(
        config,
        backend,
        clock=lambda: NOW,
        source_head_resolver=lambda _path: SOURCE_HEAD,
    )

    assert result["current_status"] == "PREDRAW_READY"
    assert result["expected_stream_count"] == 11
    assert result["actual_available_stream_count"] == 11
    assert result["ready_before_draw"] is True
    assert result["cycle_action"] == "PREDRAW_CREATED"
    assert backend.generation_calls == [(STREAM_IDS[-1],)]
    assert backend.sync_calls == 0
    persisted = json.loads(config.health_path.read_text())
    assert SHADOW_HEALTH_NAMESPACE not in persisted
    assert persisted == {
        key: value for key, value in result.items() if key != SHADOW_HEALTH_NAMESPACE
    }
    assert stat.S_IMODE(os.lstat(config.health_path).st_mode) == 0o600


def test_shadow_hook_runs_after_ready_primary_and_primary_health_stays_11_stream_schema(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    backend = _ShadowHookBackend(
        target=_target(),
        inventories=(_inventory(10), _inventory(11)),
        lock_path=config.lock_path,
    )

    result = run_scheduler_cycle(
        config,
        backend,
        clock=lambda: NOW,
        source_head_resolver=lambda _path: SOURCE_HEAD,
    )

    assert backend.shadow_predraw_calls == [(_target().draw_number, "PREDRAW_READY", SOURCE_HEAD)]
    assert backend.shadow_postdraw_calls == []
    assert backend.shadow_lock_available is True
    shadow_health = cast(dict[str, object], result[SHADOW_HEALTH_NAMESPACE])
    assert shadow_health["status"] == "PREDRAW_COMPLETE"
    persisted = json.loads(config.health_path.read_text())
    assert SHADOW_HEALTH_NAMESPACE not in persisted
    assert persisted["expected_stream_count"] == 11
    assert persisted["actual_available_stream_count"] == 11
    assert persisted["prediction_inventory"]["missing_stream_ids"] == []


def test_shadow_hook_is_skipped_when_primary_is_incomplete(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    backend = _ShadowHookBackend(
        target=_target(),
        inventories=(_inventory(10),),
    )

    result = run_scheduler_cycle(
        config,
        backend,
        clock=lambda: SCHEDULED,
        source_head_resolver=lambda _path: SOURCE_HEAD,
    )

    assert result["current_status"] == "PRE_DRAW_INCOMPLETE"
    assert backend.shadow_predraw_calls == []
    assert backend.shadow_postdraw_calls == []
    shadow_health = cast(dict[str, object], result[SHADOW_HEALTH_NAMESPACE])
    assert shadow_health["status"] == "SKIPPED_PRIMARY_NOT_READY"


def test_shadow_failure_is_returned_separately_without_changing_primary_status(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    backend = _ShadowFailureBackend(
        target=_target(),
        inventories=(_inventory(11),),
    )

    result = run_scheduler_cycle(
        config,
        backend,
        clock=lambda: NOW,
        source_head_resolver=lambda _path: SOURCE_HEAD,
    )

    assert result["current_status"] == "PREDRAW_READY"
    assert result["expected_stream_count"] == 11
    assert result["actual_available_stream_count"] == 11
    shadow_health = cast(dict[str, object], result[SHADOW_HEALTH_NAMESPACE])
    assert shadow_health["status"] == "ERROR"
    assert "shadow fixture failed" in cast(str, shadow_health["last_error"])
    persisted = json.loads(config.health_path.read_text())
    assert SHADOW_HEALTH_NAMESPACE not in persisted
    assert persisted["current_status"] == "PREDRAW_READY"


def test_production_cycle_resolves_source_head_from_canonical_repository(
    tmp_path: Path,
) -> None:
    temporary = _config(tmp_path)
    config = replace(
        production_config(),
        operation_root=temporary.operation_root,
        scheduler_root=temporary.scheduler_root,
        lock_path=temporary.lock_path,
        health_path=temporary.health_path,
        stdout_path=temporary.stdout_path,
        stderr_path=temporary.stderr_path,
        plist_path=temporary.plist_path,
    )
    backend = _FakeBackend(target=_target(), inventories=(_inventory(11),))
    resolved_paths: list[Path] = []

    def resolve_source_head(path: Path) -> str:
        resolved_paths.append(path)
        return SOURCE_HEAD

    result = run_scheduler_cycle(
        config,
        backend,
        clock=lambda: NOW,
        source_head_resolver=resolve_source_head,
    )

    assert result["current_status"] == "PREDRAW_READY"
    assert resolved_paths == [config.canonical_repository]


def test_ready_predraw_cycle_is_no_op_and_does_not_call_generation(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    backend = _FakeBackend(target=_target(), inventories=(_inventory(11),))

    result = run_scheduler_cycle(
        config,
        backend,
        clock=lambda: NOW,
        source_head_resolver=lambda _path: SOURCE_HEAD,
    )

    assert result["current_status"] == "PREDRAW_READY"
    assert cast(dict[str, object], result["prediction_generation"])["status"] == "NO_OP"
    assert result["cycle_action"] == "NO_OP"
    assert backend.generation_calls == []


def test_deadline_cycle_never_generates_and_keeps_incomplete_target_visible(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    postdraw = PostDrawResult(
        outcome_status="WAITING_FOR_OUTCOME",
        scoring_status="WAITING_FOR_OUTCOME",
        reporting_status="CURRENT",
        cycle_action="WAITING_FOR_OUTCOME",
    )
    backend = _FakeBackend(
        target=_target(),
        inventories=(_inventory(10),),
        postdraw=postdraw,
    )

    result = run_scheduler_cycle(
        config,
        backend,
        clock=lambda: SCHEDULED,
        source_head_resolver=lambda _path: SOURCE_HEAD,
    )

    assert result["current_status"] == "PRE_DRAW_INCOMPLETE"
    assert result["actual_available_stream_count"] == 10
    assert result["ready_before_draw"] is False
    assert backend.generation_calls == []
    assert backend.sync_calls == 1
    incomplete = cast(list[dict[str, object]], result["pre_draw_incomplete_targets"])
    assert incomplete[0]["draw_number"] == "209900001"
    assert incomplete[0]["missing_stream_ids"] == [STREAM_IDS[-1]]


@pytest.mark.parametrize(
    ("postdraw", "expected_status"),
    [
        (
            PostDrawResult(
                "WAITING_FOR_OUTCOME",
                "WAITING_FOR_OUTCOME",
                "CURRENT",
                "WAITING_FOR_OUTCOME",
            ),
            "WAITING_FOR_OUTCOME",
        ),
        (PostDrawResult("NEW_OUTCOME", "COMPLETE", "REBUILT", "COMPLETE"), "COMPLETE"),
    ],
)
def test_ready_postdraw_cycle_reports_waiting_or_complete(
    tmp_path: Path,
    postdraw: PostDrawResult,
    expected_status: str,
) -> None:
    config = _config(tmp_path)
    backend = _FakeBackend(
        target=_target(),
        inventories=(_inventory(11),),
        postdraw=postdraw,
    )

    result = run_scheduler_cycle(
        config,
        backend,
        clock=lambda: SCHEDULED,
        source_head_resolver=lambda _path: SOURCE_HEAD,
    )

    assert result["current_status"] == expected_status
    assert backend.generation_calls == []
    assert backend.sync_calls == 1
    assert backend.complete_calls == 1


def test_cycle_exception_atomically_replaces_running_with_error_and_counts_failures(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    backend = _FakeBackend(
        target=_target(),
        inventories=(_inventory(11),),
        fail_refresh=RuntimeError("synthetic refresh failure"),
    )

    first = run_scheduler_cycle(
        config,
        backend,
        clock=lambda: NOW,
        source_head_resolver=lambda _path: SOURCE_HEAD,
    )
    second = run_scheduler_cycle(
        config,
        backend,
        clock=lambda: NOW + timedelta(minutes=5),
        source_head_resolver=lambda _path: SOURCE_HEAD,
    )

    assert first["current_status"] == "ERROR"
    assert first["consecutive_failures"] == 1
    assert second["current_status"] == "ERROR"
    assert second["consecutive_failures"] == 2
    assert second["error_class"] == "RuntimeError"
    assert "synthetic refresh failure" in cast(str, second["error_message"])
    assert json.loads(config.health_path.read_text())["current_status"] == "ERROR"


def test_advisory_lock_contention_does_not_mutate_existing_health(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config.scheduler_root.mkdir(mode=0o700)
    existing = b'{"sentinel":true}\n'
    config.health_path.write_bytes(existing)
    config.health_path.chmod(0o600)
    backend = _FakeBackend(target=_target(), inventories=(_inventory(11),))

    with AdvisoryProcessLock(config.lock_path):
        result = run_scheduler_cycle(
            config,
            backend,
            clock=lambda: NOW,
            source_head_resolver=lambda _path: SOURCE_HEAD,
        )

    assert result["current_status"] == "ALREADY_RUNNING"
    assert result["lock_contention"] is True
    assert config.health_path.read_bytes() == existing
    assert backend.generation_calls == []
    assert backend.sync_calls == 0


def test_advisory_lock_is_released_by_context_exit(tmp_path: Path) -> None:
    path = tmp_path / "scheduler" / "lock"

    with (
        AdvisoryProcessLock(path),
        pytest.raises(SchedulerAlreadyRunning),
        AdvisoryProcessLock(path),
    ):
        raise AssertionError("unreachable")

    with AdvisoryProcessLock(path):
        assert path.exists()


def test_health_status_reports_stale_and_error_deterministically() -> None:
    health: dict[str, object] = {
        "current_status": "PREDRAW_READY",
        "finished_at": "2099-01-02T10:00:00Z",
        "stale_after_seconds": 900,
    }

    fresh = evaluate_health_status(health, now=NOW + timedelta(seconds=900))
    stale = evaluate_health_status(health, now=NOW + timedelta(seconds=901))
    error = evaluate_health_status(
        {**health, "current_status": "ERROR"},
        now=NOW + timedelta(days=1),
    )

    assert fresh["status"] == "PREDRAW_READY"
    assert stale["status"] == "STALE"
    assert stale["recorded_status"] == "PREDRAW_READY"
    assert error["status"] == "ERROR"


def test_postdraw_composition_uses_empty_stream_set_and_cannot_backfill(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)
    captured_streams: list[tuple[object, ...]] = []

    class FakeAdapter:
        def __init__(self, *_args: object, **kwargs: object) -> None:
            streams = cast(tuple[object, ...], kwargs["streams"])
            captured_streams.append(streams)

        def resolve_official_outcome(self, _target: PredictionTarget) -> None:
            return None

    monkeypatch.setattr(scheduler_module, "B649ForwardAutoCycleAdapter", FakeAdapter)
    backend = ProductionSchedulerBackend(
        config,
        clock=lambda: SCHEDULED,
        https_client=OfficialHttpsClient(
            transport=lambda _request, _context, _timeout, _limit: b"{}"
        ),
        environ={
            "LOTTOLAB_DRAW_PROVIDER_SOURCE": "OFFICIAL_TAIWAN_LOTTERY",
            "LOTTOLAB_DATA_DIR": str(config.data_root),
        },
    )

    result = backend.complete_postdraw(_target(), _inventory(7))

    assert captured_streams == [()]
    assert result.outcome_status == "WAITING_FOR_OUTCOME"


def test_official_sync_refuses_unhealthy_database_before_provider_or_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)
    report = DrawDataIntegrityReport(
        status=DrawDataIntegrityStatus.ABSENT,
        schema_version=None,
        table_counts=(),
        lottery_summaries=(),
        findings=(),
    )

    def inspect_report(_database: Path) -> DrawDataIntegrityReport:
        return report

    monkeypatch.setattr(scheduler_module, "inspect_draw_data_integrity_report", inspect_report)
    backend = ProductionSchedulerBackend(
        config,
        clock=lambda: SCHEDULED,
        https_client=OfficialHttpsClient(
            transport=lambda _request, _context, _timeout, _limit: b"{}"
        ),
        environ={
            "LOTTOLAB_DRAW_PROVIDER_SOURCE": "OFFICIAL_TAIWAN_LOTTERY",
            "LOTTOLAB_DATA_DIR": str(config.data_root),
        },
    )

    with pytest.raises(SchedulerInvariantError, match="not healthy"):
        backend.sync_official_outcome(_target())


def test_launchd_plist_has_exact_trigger_paths_environment_and_no_keepalive(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)

    parsed = plistlib.loads(build_launchd_plist(config))

    assert parsed["Label"] == config.label
    assert parsed["ProgramArguments"] == [
        str(config.python_executable),
        str(config.script_path),
        "run",
    ]
    assert parsed["RunAtLoad"] is True
    assert parsed["StartInterval"] == 300
    assert parsed["KeepAlive"] is False
    assert parsed["WorkingDirectory"] == str(config.canonical_repository)
    assert parsed["StandardOutPath"] == str(config.stdout_path)
    assert parsed["StandardErrorPath"] == str(config.stderr_path)
    assert parsed["EnvironmentVariables"] == {
        "LOTTOLAB_DATA_DIR": str(config.data_root),
        "LOTTOLAB_DRAW_PROVIDER_SOURCE": "OFFICIAL_TAIWAN_LOTTERY",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
    }
    assert "Program" not in parsed
    assert "ShellPath" not in parsed
