"""Focused acceptance coverage for the durable local B649 Goal-C scheduler."""

from __future__ import annotations

import hashlib
import json
import os
import plistlib
import runpy
import ssl
import stat
import subprocess
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
    _forecast_command,  # pyright: ignore[reportPrivateUsage]
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
STREAMS_BY_ID = {
    stream.strategy_id: stream for stream in STRATEGY_STREAMS if stream.enabled
}
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


_FORECAST_CUTOFF_DRAW = "209899999"
_FORECAST_CUTOFF_DATE = "2099-01-01"


def _forecast_prediction(
    target: PredictionTarget,
    strategy_id: str,
    *,
    strategy_version: str | None = None,
    run_suffix: str = "one",
    created_at: datetime,
    temporal_class: str = "PRE_DRAW",
    availability: str = "AVAILABLE",
    history_cutoff_draw: str,
    history_cutoff_date: str,
    ticket_numbers: Sequence[int] = (1, 2, 3, 4, 5, 6),
) -> dict[str, object]:
    """A real 11-stream ``run_strategy_stream`` record shape, forecast-focused.

    Unlike the shared ``_prediction`` fixture above (used by non-forecast
    tests that never look at ``history_cutoff``), this includes it -- the one
    field the existing ``inspect_prediction_inventory`` authority never
    validates and ``forecast`` must independently re-verify.
    """

    stream = STREAMS_BY_ID[strategy_id]
    observed_strategy_version = (
        stream.strategy_version if strategy_version is None else strategy_version
    )
    tickets = (
        [
            {
                "ticket_position": position,
                "predicted_numbers": list(ticket_numbers),
            }
            for position in range(1, stream.native_ticket_count + 1)
        ]
        if availability == "AVAILABLE"
        else []
    )
    return {
        "lottery_type": target.lottery_type,
        "draw_number": target.draw_number,
        "draw_date": target.draw_date,
        "scheduled_at": target.scheduled_at,
        "prediction_created_at": created_at.isoformat(),
        "prediction_temporal_class": temporal_class,
        "strategy_id": strategy_id,
        "strategy_version": observed_strategy_version,
        "prediction_run_id": f"{target.draw_number}-{strategy_id}-{run_suffix}",
        "availability": availability,
        "history_cutoff": {
            "draw_number": history_cutoff_draw,
            "draw_date": history_cutoff_date,
        },
        "native_ticket_count": stream.native_ticket_count,
        "tickets": tickets,
    }


def _write_forecast_prediction(
    root: Path,
    target: PredictionTarget,
    strategy_id: str,
    *,
    strategy_version: str | None = None,
    run_suffix: str = "one",
    created_at: datetime,
    temporal_class: str = "PRE_DRAW",
    availability: str = "AVAILABLE",
    history_cutoff_draw: str,
    history_cutoff_date: str,
    filename: str = "prediction.json",
    ticket_numbers: Sequence[int] = (1, 2, 3, 4, 5, 6),
) -> Path:
    path = root / "predictions" / target.draw_number / strategy_id / filename
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    payload = _forecast_prediction(
        target,
        strategy_id,
        strategy_version=strategy_version,
        run_suffix=run_suffix,
        created_at=created_at,
        temporal_class=temporal_class,
        availability=availability,
        history_cutoff_draw=history_cutoff_draw,
        history_cutoff_date=history_cutoff_date,
        ticket_numbers=ticket_numbers,
    )
    path.write_text(json.dumps(payload), encoding="utf-8")
    path.chmod(0o600)
    return path


def _write_all_streams(
    root: Path,
    target: PredictionTarget,
    strategy_ids: Sequence[str],
    *,
    created_at: datetime = NOW,
    history_cutoff_draw: str = _FORECAST_CUTOFF_DRAW,
    history_cutoff_date: str = _FORECAST_CUTOFF_DATE,
    ticket_numbers: Sequence[int] = (1, 2, 3, 4, 5, 6),
) -> None:
    for strategy_id in strategy_ids:
        _write_forecast_prediction(
            root,
            target,
            strategy_id,
            created_at=created_at,
            history_cutoff_draw=history_cutoff_draw,
            history_cutoff_date=history_cutoff_date,
            ticket_numbers=ticket_numbers,
        )


def _canonical_target() -> PredictionTarget:
    scheduled_at = datetime(2026, 9, 11, 12, 30, tzinfo=UTC)
    return PredictionTarget(
        lottery_type=LOTTERY_TYPE,
        draw_number="115000087",
        draw_date="2026-09-11",
        scheduled_at=scheduled_at.astimezone(scheduler_module.TAIPEI).isoformat(),
    )


def _write_canonical_streams(root: Path, target: PredictionTarget) -> None:
    for strategy_id in STREAM_IDS:
        _write_forecast_prediction(
            root,
            target,
            strategy_id,
            created_at=datetime(2026, 9, 10, 12, 0, tzinfo=UTC),
            history_cutoff_draw="115000086",
            history_cutoff_date="2026-09-08",
        )


def _authority_payload(
    target: PredictionTarget,
    **overrides: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "b649-canonical-forecast-v1",
        "aggregation_method_id": "B649_11_STREAM_EQUAL_WEIGHT_NUMBER_CONSENSUS",
        "aggregation_method_version": "1.0.0",
        "target_draw": {
            "draw_number": target.draw_number,
            "draw_date": target.draw_date,
        },
        "lottery_type": target.lottery_type,
        "stream_count": 11,
        "target_result_used": False,
        "pre_outcome_temporal_integrity": "PASS",
        "weight_policy": "EQUAL_STREAM_WEIGHT",
        "stream_input_manifest_sha256": "d" * 64,
        "final_decision_ranking": [
            {"rank": 1, "number": 4, "support_units": 11},
            {"rank": 2, "number": 12, "support_units": 10},
            {"rank": 3, "number": 24, "support_units": 9},
            {"rank": 4, "number": 25, "support_units": 8},
            {"rank": 5, "number": 26, "support_units": 7},
            {"rank": 6, "number": 29, "support_units": 6},
        ],
        "final_recommended_output": [
            {"ticket_position": 1, "predicted_numbers": [4, 12, 24, 25, 26, 29]}
        ],
    }
    payload.update(overrides)
    return payload


def _install_authority_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target: PredictionTarget,
    **overrides: object,
) -> dict[str, object]:
    payload = _authority_payload(target, **overrides)
    raw = scheduler_module._canonical_json(payload).encode("utf-8") + b"\n"  # pyright: ignore[reportPrivateUsage]
    _install_authority_bytes_fixture(tmp_path, monkeypatch, raw)
    return payload


def _install_authority_bytes_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    raw: bytes,
    *,
    expected_sha256: str | None = None,
) -> Path:
    path = tmp_path / "authority" / "final_forecast_payload.json"
    path.parent.mkdir(mode=0o700)
    path.write_bytes(raw)
    path.chmod(0o600)
    monkeypatch.setattr(scheduler_module, "CANONICAL_FORECAST_AUTHORITY_PATH", path)
    monkeypatch.setattr(
        scheduler_module,
        "CANONICAL_FORECAST_SHA256",
        expected_sha256 or hashlib.sha256(raw).hexdigest(),
    )
    return path


class _ForecastOnlyBackend:
    """Delegate to the real inventory authority; hard-fail on any mutating call.

    ``resolve_target``/``inspect_predictions`` are exactly the two
    ``SchedulerBackend`` methods Section 4 of the Packet names as the
    existing authority ``forecast`` must reuse. The other five methods raise
    instead of acting, so any accidental call from ``_forecast_command``
    surfaces immediately as a test failure rather than a silent write.
    """

    def __init__(self, *, target: PredictionTarget | None, operation_root: Path) -> None:
        self.target = target
        self.operation_root = operation_root
        self.mutating_calls: list[str] = []

    def resolve_target(self) -> PredictionTarget | None:
        return self.target

    def inspect_predictions(self, target: PredictionTarget) -> PredictionInventory:
        return inspect_prediction_inventory(self.operation_root, target)

    def refresh_schedule(self, observed_at: datetime) -> ScheduleRefreshResult:
        self.mutating_calls.append("refresh_schedule")
        raise AssertionError("forecast must never call refresh_schedule")

    def generate_predraw(
        self, target: PredictionTarget, missing_stream_ids: Sequence[str]
    ) -> dict[str, object]:
        self.mutating_calls.append("generate_predraw")
        raise AssertionError("forecast must never call generate_predraw")

    def materialize_predraw_portfolios(
        self, target: PredictionTarget, inventory: PredictionInventory
    ) -> dict[str, object]:
        self.mutating_calls.append("materialize_predraw_portfolios")
        raise AssertionError("forecast must never call materialize_predraw_portfolios")

    def sync_official_outcome(self, target: PredictionTarget) -> dict[str, object]:
        self.mutating_calls.append("sync_official_outcome")
        raise AssertionError("forecast must never call sync_official_outcome")

    def complete_postdraw(
        self, target: PredictionTarget, inventory: PredictionInventory
    ) -> PostDrawResult:
        self.mutating_calls.append("complete_postdraw")
        raise AssertionError("forecast must never call complete_postdraw")


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
        self.materialization_calls: list[tuple[PredictionTarget, PredictionInventory]] = []
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

    def materialize_predraw_portfolios(
        self,
        target: PredictionTarget,
        inventory: PredictionInventory,
    ) -> dict[str, object]:
        assert target == self.target
        assert inventory.ready
        self.materialization_calls.append((target, inventory))
        return {
            "status": "ALREADY_PRESENT",
            "pre_outcome_forecast_status": "COMPLETE",
            "post_outcome_scoring_status": "NOT_DUE",
            "next_draw_rollover_status": "NOT_DUE",
            "k5_status": "COMPLETE",
            "k10_status": "COMPLETE",
            "k20_status": "COMPLETE",
            "outcome_used": "NO",
            "upstream_authority_locator": str(Path.cwd() / "upstream" / target.draw_number),
            "portfolio_authority_locator": str(Path.cwd() / "portfolio" / target.draw_number),
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
    canonical_repository = scheduler_module.CANONICAL_REPOSITORY

    assert config.label == "com.lottolab.b649-goalc-r1"
    assert config.start_interval_seconds == 300
    assert config.stale_after_seconds == 900
    assert config.expected_stream_count == len(STREAM_IDS) == 11
    assert config.canonical_repository == canonical_repository
    assert config.source_worktree == Path(scheduler_module.__file__).resolve().parents[1]
    assert config.script_path == scheduler_module.SCRIPT_PATH
    assert config.operation_root == scheduler_module.GOALC_ROOT
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


def test_production_scheduler_syncs_canonical_schedule_and_ignores_legacy_file(
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

    def schedule_network(
        _request: scheduler_module.Request,
        _context: ssl.SSLContext,
        _timeout: float,
        _limit: int,
    ) -> bytes:
        nonlocal network_calls
        network_calls += 1
        return _schedule_body()

    before = config.announcement.read_bytes()
    backend = ProductionSchedulerBackend(
        config,
        clock=lambda: after_deadline,
        https_client=OfficialHttpsClient(
            transport=schedule_network
        ),
        environ={
            "LOTTOLAB_DRAW_PROVIDER_SOURCE": "OFFICIAL_TAIWAN_LOTTERY",
            "LOTTOLAB_DATA_DIR": str(config.data_root),
        },
    )

    refresh = backend.refresh_schedule(after_deadline)

    assert refresh.status == "REFRESHED"
    assert refresh.source_url == scheduler_module.SCHEDULE_URL
    assert refresh.source_payload_sha256 == hashlib.sha256(_schedule_body()).hexdigest()
    assert refresh.b649_targets == ("209900002",)
    assert refresh.inventory_count == 1
    resolved = backend.resolve_target()
    assert resolved is not None
    assert resolved.draw_number == "209900002"
    assert network_calls == 1
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
    assert inventory.available_prediction_paths == tuple(
        tmp_path / "predictions" / target.draw_number / strategy_id / "prediction.json"
        for strategy_id in STREAM_IDS
    )


def test_production_backend_passes_exact_predraw_paths_to_portfolio_materializer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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
    target = _target()
    candidate_paths = tuple(tmp_path / f"candidate-{index}.json" for index in range(11))
    inventory = replace(_inventory(11), available_prediction_paths=candidate_paths)
    captured: dict[str, object] = {}

    class _Materialized:
        def health_dict(self) -> dict[str, object]:
            return {"status": "CREATED"}

    def fake_materialize(**kwargs: object) -> _Materialized:
        captured.update(kwargs)
        return _Materialized()

    monkeypatch.setattr(scheduler_module, "materialize_portfolios", fake_materialize)
    backend = ProductionSchedulerBackend(
        config,
        clock=lambda: NOW,
        https_client=OfficialHttpsClient(
            transport=lambda _request, _context, _timeout, _limit: b"{}"
        ),
        environ={
            "LOTTOLAB_DRAW_PROVIDER_SOURCE": "OFFICIAL_TAIWAN_LOTTERY",
            "LOTTOLAB_DATA_DIR": str(config.data_root),
        },
    )

    result = backend.materialize_predraw_portfolios(target, inventory)

    assert result == {"status": "CREATED"}
    assert captured["candidate_paths"] == candidate_paths
    assert captured["expected_strategy_ids"] == STREAM_IDS
    assert captured["target_draw_number"] == target.draw_number
    assert captured["target_draw_date"] == target.draw_date
    assert captured["scheduled_at"] == target.scheduled_at
    assert captured["upstream_authority_locator"] == (
        f"{config.operation_root / 'predictions' / target.draw_number}/"
    )
    assert captured["destination"] == scheduler_module.default_portfolio_destination(
        config.operation_root, target.draw_number
    )
    assert callable(captured["pre_outcome_seal_check"])


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
    assert len(backend.materialization_calls) == 1
    assert backend.materialization_calls[0][1].ready is True
    assert result["pre_outcome_forecast_status"] == "COMPLETE"
    assert result["post_outcome_scoring_status"] == "NOT_DUE"
    assert result["next_draw_rollover_status"] == "NOT_DUE"
    assert result["k5_status"] == result["k10_status"] == result["k20_status"] == "COMPLETE"
    assert result["outcome_used"] == "NO"
    assert "forecast_materialization" not in result
    assert result["scoring_status"] == "NOT_DUE"
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


def test_production_cycle_resolves_source_head_from_executing_module(
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
    assert resolved_paths == [Path(scheduler_module.__file__).resolve().parents[1]]
    assert result["source_worktree"] == str(resolved_paths[0])
    assert result["observed_source_head"] == SOURCE_HEAD


@pytest.mark.parametrize("detached", [False, True])
def test_health_reports_loaded_checkout_despite_unrelated_configuration(
    tmp_path: Path,
    detached: bool,
) -> None:
    config = _config(tmp_path)
    repository = config.canonical_repository

    def git(path: Path, *args: str) -> str:
        return subprocess.run(
            ["/usr/bin/git", "-C", str(path), *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    git(repository, "init")
    git(repository, "config", "user.name", "Scheduler Test")
    git(repository, "config", "user.email", "scheduler@example.invalid")
    module_path = repository / "tools/b649_goalc_local_scheduler.py"
    module_path.parent.mkdir()
    module_path.write_text(Path(scheduler_module.__file__).read_text())
    git(repository, "add", "tools/b649_goalc_local_scheduler.py")
    git(repository, "commit", "-m", "runtime fixture")
    runtime_head = git(repository, "rev-parse", "HEAD")
    runtime = tmp_path / "executing-checkout"
    if detached:
        git(repository, "worktree", "add", "--detach", str(runtime), runtime_head)
        assert git(runtime, "rev-parse", "--abbrev-ref", "HEAD") == "HEAD"
    else:
        git(repository, "worktree", "add", "-b", "runtime", str(runtime), runtime_head)
    git(repository, "commit", "--allow-empty", "-m", "unrelated configured head")
    assert git(repository, "rev-parse", "HEAD") != runtime_head
    config = replace(
        config,
        source_worktree=repository,
        script_path=module_path,
    )
    loaded = runpy.run_path(str(runtime / "tools/b649_goalc_local_scheduler.py"))
    backend = _FakeBackend(target=_target(), inventories=(_inventory(11),))
    result = loaded["run_scheduler_cycle"](config, backend, clock=lambda: NOW)
    persisted = json.loads(config.health_path.read_text())

    assert result["source_worktree"] == str(runtime.resolve())
    assert result["observed_source_head"] == runtime_head
    assert persisted["source_worktree"] == result["source_worktree"]
    assert persisted["observed_source_head"] == runtime_head
    assert result["canonical_repository"] == str(repository)
    assert result["schema_version"] == scheduler_module.HEALTH_SCHEMA_VERSION
    assert result["current_status"] == "PREDRAW_READY"
    assert result["expected_stream_count"] == result["actual_available_stream_count"] == 11
    assert result["ready_before_draw"] is True
    assert backend.generation_calls == []


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
    assert len(backend.materialization_calls) == 1


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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)
    backend = _FakeBackend(
        target=_target(),
        inventories=(_inventory(11),),
        postdraw=postdraw,
    )

    def fail_materialization(
        _target: PredictionTarget, _inventory: PredictionInventory
    ) -> dict[str, object]:
        raise AssertionError("post-outcome cycle must not invoke pre-outcome materialization")

    monkeypatch.setattr(backend, "materialize_predraw_portfolios", fail_materialization)

    result = run_scheduler_cycle(
        config,
        backend,
        clock=lambda: SCHEDULED,
        source_head_resolver=lambda _path: SOURCE_HEAD,
    )

    assert result["current_status"] == expected_status
    assert backend.generation_calls == []
    assert backend.materialization_calls == []
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


def test_schedule_sync_warning_keeps_a_valid_database_target_running(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    backend = _FakeBackend(
        target=_target(),
        inventories=(_inventory(11),),
        fail_refresh=OfficialScheduleUnavailableError("temporary official outage"),
    )

    result = run_scheduler_cycle(
        config,
        backend,
        clock=lambda: NOW,
        source_head_resolver=lambda _path: SOURCE_HEAD,
    )

    assert result["current_status"] == "PREDRAW_READY"
    warnings = cast(list[str], result["warnings"])
    assert len(warnings) == 1
    assert warnings[0].startswith("OFFICIAL_SCHEDULE_SYNC_WARNING:")
    announcement = cast(dict[str, object], result["announcement"])
    assert announcement["status"] == "SYNC_WARNING_DB_FALLBACK"
    assert backend.generation_calls == []


def test_scheduler_invariant_is_not_downgraded_to_schedule_sync_warning(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    backend = _FakeBackend(
        target=_target(),
        inventories=(_inventory(11),),
        fail_refresh=SchedulerInvariantError("environment mismatch"),
    )

    result = run_scheduler_cycle(
        config,
        backend,
        clock=lambda: NOW,
        source_head_resolver=lambda _path: SOURCE_HEAD,
    )

    assert result["current_status"] == "ERROR"
    assert result["error_class"] == "SchedulerInvariantError"
    assert result["warnings"] == []


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


# ---------------------------------------------------------------------------
# `forecast` (B649_PRE_OUTCOME_FORECAST_CLI_DELIVERY_R1)
# ---------------------------------------------------------------------------


def test_parser_accepts_all_four_subcommands() -> None:
    parser = scheduler_module._parser()  # pyright: ignore[reportPrivateUsage]
    for command in ("run", "status", "write-plist", "forecast"):
        args = parser.parse_args([command])
        assert args.command == command


def test_forecast_ready_when_all_eleven_streams_are_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance 1: READY exposes the approved full canonical decision."""

    config = _config(tmp_path)
    target = _canonical_target()
    _write_canonical_streams(config.operation_root, target)
    authority = _install_authority_fixture(tmp_path, monkeypatch, target)
    backend = _ForecastOnlyBackend(target=target, operation_root=config.operation_root)

    result, exit_code = _forecast_command(config, backend)

    assert exit_code == 0
    assert result["FORECAST_STATUS"] == "READY"
    assert result["TARGET_DRAW"] == target.draw_number
    assert result["TARGET_DRAW_DATE"] == target.draw_date
    assert result["TARGET_SCHEDULED_AT"] == target.scheduled_at
    assert result["TARGET_RESULT_USED"] == "NO"
    assert result["PRE_OUTCOME_TEMPORAL_INTEGRITY"] == "PASS"
    assert result["EXPECTED_STREAM_COUNT"] == 11
    assert result["AVAILABLE_STREAM_COUNT"] == 11
    assert result["MISSING_STREAM_IDS"] == []
    assert result["ANALYSIS_MAX_DATA_CUTOFF"] == "115000086"
    assert result["TARGET_RESULT_DEPENDENCY"] == "NONE"
    assert result["RANKING_AUTHORITY"] == "B649_11_STREAM_EQUAL_WEIGHT_NUMBER_CONSENSUS"
    assert result["RANKING_AUTHORITY_VERSION"] == "1.0.0"
    assert result["WEIGHT_POLICY"] == "EQUAL_STREAM_WEIGHT"
    assert result["STREAM_INPUT_MANIFEST_SHA256"] == "d" * 64
    assert result["FINAL_DECISION_RANKING"] == authority["final_decision_ranking"]
    assert result["FINAL_RECOMMENDED_TICKET"] == [4, 12, 24, 25, 26, 29]
    assert result["FINAL_RECOMMENDED_OUTPUT"] == [
        {"ticket_position": 1, "predicted_numbers": [4, 12, 24, 25, 26, 29]}
    ]
    streams = cast(list[dict[str, object]], result["STREAMS"])
    assert len(streams) == 11
    assert {cast(str, entry["strategy_id"]) for entry in streams} == set(STREAM_IDS)
    for entry in streams:
        assert entry["history_cutoff_draw"] == "115000086"
        assert entry["tickets"]
        assert {
            "strategy_id",
            "strategy_version",
            "prediction_run_id",
            "prediction_created_at",
            "history_cutoff_draw",
            "tickets",
        } == set(entry)
    assert "CANONICAL_PREDRAW_CONSENSUS" not in result
    assert backend.mutating_calls == []


def test_forecast_reuses_validated_prediction_snapshot_without_second_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path)
    target = _canonical_target()
    _write_canonical_streams(config.operation_root, target)
    prediction_paths = {
        config.operation_root
        / "predictions"
        / target.draw_number
        / strategy_id
        / "prediction.json"
        for strategy_id in STREAM_IDS
    }
    _install_authority_fixture(tmp_path, monkeypatch, target)
    original_iter_prediction_files = scheduler_module.iter_prediction_files
    original_reader = scheduler_module._read_json_object_with_bytes  # pyright: ignore[reportPrivateUsage]
    scan_count = 0
    read_paths: list[Path] = []

    def count_scans(root: Path, draw_number: str) -> object:
        nonlocal scan_count
        scan_count += 1
        return original_iter_prediction_files(root, draw_number)

    def count_reads(path: Path) -> tuple[dict[str, object], bytes]:
        read_paths.append(path)
        return original_reader(path)

    monkeypatch.setattr(scheduler_module, "iter_prediction_files", count_scans)
    monkeypatch.setattr(scheduler_module, "_read_json_object_with_bytes", count_reads)
    backend = _ForecastOnlyBackend(target=target, operation_root=config.operation_root)

    result, exit_code = _forecast_command(config, backend)

    assert exit_code == 0
    assert result["FORECAST_STATUS"] == "READY"
    assert scan_count == 1
    assert len(read_paths) == 11
    assert set(read_paths) == prediction_paths
    assert result["STREAM_INPUT_MANIFEST_SHA256"] == "d" * 64


def test_forecast_115000087_uses_approved_canonical_ticket(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance 2: 115000087 is delivered through the approved authority."""

    config = _config(tmp_path)
    target = _canonical_target()
    created_at = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
    _write_all_streams(
        config.operation_root,
        target,
        STREAM_IDS,
        created_at=created_at,
        history_cutoff_draw="115000086",
        history_cutoff_date="2026-09-08",
        ticket_numbers=(4, 12, 24, 25, 26, 29),
    )
    _install_authority_fixture(tmp_path, monkeypatch, target)

    def fail_legacy_builder(*_args: object, **_kwargs: object) -> object:
        pytest.fail("PR283 builder must not be used by forecast")

    monkeypatch.setattr(
        scheduler_module,
        "build_canonical_consensus",
        fail_legacy_builder,
        raising=False,
    )
    monkeypatch.setattr(
        scheduler_module,
        "build_canonical_predraw_consensus",
        fail_legacy_builder,
        raising=False,
    )
    backend = _ForecastOnlyBackend(target=target, operation_root=config.operation_root)

    result, exit_code = _forecast_command(config, backend)

    assert exit_code == 0
    assert result["FORECAST_STATUS"] == "READY"
    assert result["PRE_OUTCOME_TEMPORAL_INTEGRITY"] == "PASS"
    assert result["ANALYSIS_MAX_DATA_CUTOFF"] == "115000086"
    assert result["RANKING_AUTHORITY"] == "B649_11_STREAM_EQUAL_WEIGHT_NUMBER_CONSENSUS"
    assert result["RANKING_AUTHORITY_VERSION"] == "1.0.0"
    assert result["FINAL_RECOMMENDED_TICKET"] == [4, 12, 24, 25, 26, 29]
    ranking = cast(list[dict[str, object]], result["FINAL_DECISION_RANKING"])
    assert [entry["number"] for entry in ranking[:6]] == [4, 12, 24, 25, 26, 29]


def test_forecast_is_repeatedly_deterministic_for_same_validated_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path)
    target = _canonical_target()
    _write_canonical_streams(config.operation_root, target)
    _install_authority_fixture(tmp_path, monkeypatch, target)
    backend = _ForecastOnlyBackend(target=target, operation_root=config.operation_root)

    first, first_exit_code = _forecast_command(config, backend)
    second, second_exit_code = _forecast_command(config, backend)

    assert first_exit_code == second_exit_code == 0
    assert first == second


def test_forecast_does_not_require_or_read_target_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance 3: the target outcome is neither required nor read."""

    config = _config(tmp_path)
    target = _canonical_target()
    _write_canonical_streams(config.operation_root, target)
    _install_authority_fixture(tmp_path, monkeypatch, target)
    assert not (config.operation_root / "outcomes").exists()
    backend = _ForecastOnlyBackend(target=target, operation_root=config.operation_root)

    result, exit_code = _forecast_command(config, backend)

    assert exit_code == 0
    assert result["FORECAST_STATUS"] == "READY"
    assert result["TARGET_RESULT_USED"] == "NO"
    assert not (config.operation_root / "outcomes").exists()
    assert backend.mutating_calls == []


def test_forecast_incomplete_when_streams_are_missing(tmp_path: Path) -> None:
    """Acceptance 4: missing streams return internal readiness, not blocked."""

    config = _config(tmp_path)
    target = _target()
    available = STREAM_IDS[:7]
    _write_all_streams(config.operation_root, target, available)
    backend = _ForecastOnlyBackend(target=target, operation_root=config.operation_root)

    result, exit_code = _forecast_command(config, backend)

    assert exit_code == 0
    assert result["FORECAST_STATUS"] == "INTERNAL_PREDRAW_READINESS_STATE"
    assert result["EXPECTED_STREAM_COUNT"] == 11
    assert result["AVAILABLE_STREAM_COUNT"] == 7
    assert result["MISSING_STREAM_IDS"] == list(STREAM_IDS[7:])
    assert "STREAMS" not in result
    assert "FINAL_DECISION_RANKING" not in result
    assert "FINAL_RECOMMENDED_TICKET" not in result
    assert "STREAM_INPUT_MANIFEST_SHA256" not in result
    assert backend.mutating_calls == []


def test_forecast_ignores_extra_technical_failure_record_when_inventory_is_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path)
    target = _canonical_target()
    _write_canonical_streams(config.operation_root, target)
    _write_forecast_prediction(
        config.operation_root,
        target,
        STREAM_IDS[0],
        run_suffix="technical-failure",
        filename="technical-failure.json",
        created_at=SCHEDULED + timedelta(hours=1),
        availability="TECHNICAL_FAILURE",
        history_cutoff_draw="115000086",
        history_cutoff_date="2026-09-08",
    )
    _install_authority_fixture(tmp_path, monkeypatch, target)
    backend = _ForecastOnlyBackend(target=target, operation_root=config.operation_root)

    result, exit_code = _forecast_command(config, backend)

    assert exit_code == 0
    assert result["FORECAST_STATUS"] == "READY"
    assert result["AVAILABLE_STREAM_COUNT"] == 11
    assert result["MISSING_STREAM_IDS"] == []
    assert result["FINAL_RECOMMENDED_TICKET"] == [4, 12, 24, 25, 26, 29]


def test_forecast_excludes_post_draw_predictions_from_availability(tmp_path: Path) -> None:
    """Acceptance 5: a POST_DRAW prediction cannot enter forecast authority."""

    config = _config(tmp_path)
    target = _target()
    _write_all_streams(config.operation_root, target, STREAM_IDS[1:])
    _write_forecast_prediction(
        config.operation_root,
        target,
        STREAM_IDS[0],
        created_at=SCHEDULED + timedelta(hours=1),
        temporal_class="POST_DRAW",
        history_cutoff_draw=_FORECAST_CUTOFF_DRAW,
        history_cutoff_date=_FORECAST_CUTOFF_DATE,
    )
    backend = _ForecastOnlyBackend(target=target, operation_root=config.operation_root)

    result, exit_code = _forecast_command(config, backend)

    assert exit_code == 0
    assert result["FORECAST_STATUS"] == "INTERNAL_PREDRAW_READINESS_STATE"
    assert result["MISSING_STREAM_IDS"] == [STREAM_IDS[0]]
    assert result["AVAILABLE_STREAM_COUNT"] == 10


def test_forecast_rejects_predraw_timestamp_at_or_after_deadline(tmp_path: Path) -> None:
    """Acceptance 6: prediction_created_at >= scheduled_at is rejected."""

    config = _config(tmp_path)
    target = _target()
    _write_all_streams(config.operation_root, target, STREAM_IDS[1:])
    _write_forecast_prediction(
        config.operation_root,
        target,
        STREAM_IDS[0],
        created_at=SCHEDULED,
        history_cutoff_draw=_FORECAST_CUTOFF_DRAW,
        history_cutoff_date=_FORECAST_CUTOFF_DATE,
    )
    backend = _ForecastOnlyBackend(target=target, operation_root=config.operation_root)

    result, exit_code = _forecast_command(config, backend)

    assert exit_code != 0
    assert result["FORECAST_STATUS"] == "INVALID_TEMPORAL_AUTHORITY"
    violations = cast(list[str], result["VIOLATIONS"])
    assert violations
    assert "STREAMS" not in result
    assert backend.mutating_calls == []


def test_forecast_treats_malformed_history_cutoff_as_invalid_temporal_authority(
    tmp_path: Path,
) -> None:
    """A stored record missing history_cutoff fails closed, never crashes uncaught."""

    config = _config(tmp_path)
    target = _target()
    _write_all_streams(config.operation_root, target, STREAM_IDS[1:])
    path = _write_forecast_prediction(
        config.operation_root,
        target,
        STREAM_IDS[0],
        created_at=NOW,
        history_cutoff_draw=_FORECAST_CUTOFF_DRAW,
        history_cutoff_date=_FORECAST_CUTOFF_DATE,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    del payload["history_cutoff"]
    path.write_text(json.dumps(payload), encoding="utf-8")
    path.chmod(0o600)
    backend = _ForecastOnlyBackend(target=target, operation_root=config.operation_root)

    result, exit_code = _forecast_command(config, backend)

    assert exit_code != 0
    assert result["FORECAST_STATUS"] == "INVALID_TEMPORAL_AUTHORITY"
    violations = cast(list[str], result["VIOLATIONS"])
    assert any(STREAM_IDS[0] in violation for violation in violations)
    assert "FINAL_DECISION_RANKING" not in result
    assert "FINAL_RECOMMENDED_TICKET" not in result
    assert "STREAM_INPUT_MANIFEST_SHA256" not in result


def test_forecast_never_invokes_mutating_backend_methods(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance 7: forecast never calls scheduler run/generation/outcome sync."""

    config = _config(tmp_path)
    target = _canonical_target()
    _write_canonical_streams(config.operation_root, target)
    _install_authority_fixture(tmp_path, monkeypatch, target)
    backend = _ForecastOnlyBackend(target=target, operation_root=config.operation_root)

    _forecast_command(config, backend)

    assert backend.mutating_calls == []


def test_forecast_projects_immutable_authority_b_payload_and_final_ticket(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """READY output is a mechanical projection of the approved payload."""

    config = _config(tmp_path)
    target = _canonical_target()
    _write_canonical_streams(config.operation_root, target)
    canonical = _install_authority_fixture(tmp_path, monkeypatch, target)
    backend = _ForecastOnlyBackend(target=target, operation_root=config.operation_root)

    result, exit_code = _forecast_command(config, backend)

    assert exit_code == 0
    assert result["FORECAST_STATUS"] == "READY"
    assert result["AUTHORITY_STATUS"] == "CANONICAL"
    assert result["TARGET_RESULT_DEPENDENCY"] == "NONE"
    assert result["RANKING_AUTHORITY"] == canonical["aggregation_method_id"]
    assert result["RANKING_AUTHORITY_VERSION"] == canonical["aggregation_method_version"]
    assert result["WEIGHT_POLICY"] == canonical["weight_policy"]
    assert result["STREAM_INPUT_MANIFEST_SHA256"] == canonical["stream_input_manifest_sha256"]
    assert result["FINAL_DECISION_RANKING"] == canonical["final_decision_ranking"]
    assert result["FINAL_RECOMMENDED_OUTPUT"] == canonical["final_recommended_output"]
    assert result["CANONICAL_FORECAST_AUTHORITY"] == canonical
    assert result["FINAL_RECOMMENDED_TICKET"] == [4, 12, 24, 25, 26, 29]
    assert len(cast(list[dict[str, object]], result["FINAL_DECISION_RANKING"])) == 6
    assert "descriptive_top6" not in json.dumps(result)
    assert "descriptive_top_k" not in json.dumps(result)
    assert backend.mutating_calls == []


def test_forecast_fails_closed_when_authority_b_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path)
    target = _canonical_target()
    _write_canonical_streams(config.operation_root, target)
    _install_authority_bytes_fixture(tmp_path, monkeypatch, b"not-json\n")
    backend = _ForecastOnlyBackend(target=target, operation_root=config.operation_root)

    result, exit_code = _forecast_command(config, backend)

    assert exit_code != 0
    assert result["FORECAST_STATUS"] == "CANONICAL_AUTHORITY_UNAVAILABLE"
    assert result["AUTHORITY_STATUS"] == "NON_SUCCESS"
    assert "AUTHORITY_B_RESULT_INVALID" in cast(str, result["CANONICAL_AUTHORITY_ERROR"])
    assert "FINAL_DECISION_RANKING" not in result
    assert "FINAL_RECOMMENDED_OUTPUT" not in result


def test_forecast_fails_closed_when_authority_b_file_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path)
    target = _canonical_target()
    _write_canonical_streams(config.operation_root, target)
    authority_path = tmp_path / "authority" / "final_forecast_payload.json"
    authority_path.parent.mkdir(mode=0o700)
    monkeypatch.setattr(scheduler_module, "CANONICAL_FORECAST_AUTHORITY_PATH", authority_path)
    monkeypatch.setattr(scheduler_module, "CANONICAL_FORECAST_SHA256", "0" * 64)
    backend = _ForecastOnlyBackend(target=target, operation_root=config.operation_root)

    result, exit_code = _forecast_command(config, backend)

    assert exit_code != 0
    assert result["FORECAST_STATUS"] == "CANONICAL_AUTHORITY_UNAVAILABLE"
    assert result["AUTHORITY_STATUS"] == "NON_SUCCESS"
    assert "AUTHORITY_B_RESULT_UNAVAILABLE" in cast(
        str, result["CANONICAL_AUTHORITY_ERROR"]
    )
    assert "FINAL_DECISION_RANKING" not in result
    assert "FINAL_RECOMMENDED_OUTPUT" not in result


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("schema_version", "wrong-schema"),
        ("aggregation_method_id", "wrong-method"),
        ("aggregation_method_version", "9.9.9"),
    ],
)
def test_forecast_rejects_invalid_authority_schema_method_or_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    invalid_value: str,
) -> None:
    config = _config(tmp_path)
    target = _canonical_target()
    _write_canonical_streams(config.operation_root, target)
    _install_authority_fixture(tmp_path, monkeypatch, target, **{field: invalid_value})
    backend = _ForecastOnlyBackend(target=target, operation_root=config.operation_root)

    result, exit_code = _forecast_command(config, backend)

    assert exit_code != 0
    assert result["FORECAST_STATUS"] == "CANONICAL_AUTHORITY_UNAVAILABLE"
    assert result["AUTHORITY_STATUS"] == "NON_SUCCESS"
    assert "FINAL_DECISION_RANKING" not in result
    assert "FINAL_RECOMMENDED_OUTPUT" not in result
    assert "FINAL_RECOMMENDED_TICKET" not in result
    assert "WEIGHT_POLICY" not in result
    assert result.get("PRE_OUTCOME_TEMPORAL_INTEGRITY") != "PASS"


def test_forecast_fails_closed_when_authority_sha_is_wrong(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path)
    target = _canonical_target()
    _write_canonical_streams(config.operation_root, target)
    _install_authority_fixture(tmp_path, monkeypatch, target)
    monkeypatch.setattr(scheduler_module, "CANONICAL_FORECAST_SHA256", "0" * 64)
    backend = _ForecastOnlyBackend(target=target, operation_root=config.operation_root)

    result, exit_code = _forecast_command(config, backend)

    assert exit_code != 0
    assert result["FORECAST_STATUS"] == "CANONICAL_AUTHORITY_UNAVAILABLE"
    assert result["AUTHORITY_STATUS"] == "NON_SUCCESS"
    assert "digest mismatch" in cast(str, result["CANONICAL_AUTHORITY_ERROR"])
    assert "FINAL_RECOMMENDED_TICKET" not in result
    assert "FINAL_DECISION_RANKING" not in result
    assert result.get("PRE_OUTCOME_TEMPORAL_INTEGRITY") != "PASS"


def test_forecast_fails_closed_when_authority_target_does_not_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path)
    target = _canonical_target()
    _write_canonical_streams(config.operation_root, target)
    _install_authority_fixture(
        tmp_path,
        monkeypatch,
        target,
        target_draw={"draw_number": "115000088", "draw_date": target.draw_date},
    )
    backend = _ForecastOnlyBackend(target=target, operation_root=config.operation_root)

    result, exit_code = _forecast_command(config, backend)

    assert exit_code != 0
    assert result["FORECAST_STATUS"] == "CANONICAL_AUTHORITY_UNAVAILABLE"
    assert "target does not match" in cast(str, result["CANONICAL_AUTHORITY_ERROR"])
    assert "FINAL_RECOMMENDED_OUTPUT" not in result
    assert result.get("PRE_OUTCOME_TEMPORAL_INTEGRITY") != "PASS"


def test_forecast_rejects_descriptive_fields_in_canonical_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path)
    target = _canonical_target()
    _write_canonical_streams(config.operation_root, target)
    _install_authority_fixture(
        tmp_path,
        monkeypatch,
        target,
        descriptive_top6=[{"number": 4}],
    )
    backend = _ForecastOnlyBackend(target=target, operation_root=config.operation_root)

    result, exit_code = _forecast_command(config, backend)

    assert exit_code != 0
    assert result["FORECAST_STATUS"] == "CANONICAL_AUTHORITY_UNAVAILABLE"
    assert "descriptive diagnostics" in cast(str, result["CANONICAL_AUTHORITY_ERROR"])
    assert "FINAL_DECISION_RANKING" not in result
    assert "FINAL_RECOMMENDED_OUTPUT" not in result
    assert result.get("PRE_OUTCOME_TEMPORAL_INTEGRITY") != "PASS"


def test_forecast_directly_calls_domain_authority_and_not_legacy_builder() -> None:
    source = getsource(_forecast_command)

    assert "_load_canonical_forecast_authority" in source
    assert "build_canonical_consensus" not in source
    assert "build_canonical_predraw_consensus" not in source
    assert "compute_number_consensus" not in source
    assert "pairwise_stream_overlap" not in source
    assert "descriptive_top6" not in source
    assert "descriptive_top_k" not in source
    assert "sorted(" not in source


def test_forecast_reports_no_target_resolved_without_reading_predictions(tmp_path: Path) -> None:
    config = _config(tmp_path)
    backend = _ForecastOnlyBackend(target=None, operation_root=config.operation_root)

    result, exit_code = _forecast_command(config, backend)

    assert exit_code != 0
    assert result == {"FORECAST_STATUS": "NO_TARGET_RESOLVED"}
    assert backend.mutating_calls == []


def _snapshot_files(root: Path) -> set[tuple[str, int, int]]:
    entries: set[tuple[str, int, int]] = set()
    for path in root.rglob("*"):
        if path.is_file():
            info = path.stat()
            entries.add((str(path.relative_to(root)), info.st_size, info.st_mtime_ns))
    return entries


def test_forecast_writes_nothing_under_operation_root_or_scheduler_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance (read-only guarantee): no health.json, predictions, scores,
    outcomes, lock, or plist write -- proven by filesystem snapshot, not by
    trusting the implementation's own claims.
    """

    config = _config(tmp_path)
    target = _canonical_target()
    _write_canonical_streams(config.operation_root, target)
    _install_authority_fixture(tmp_path, monkeypatch, target)
    before = _snapshot_files(config.operation_root)
    assert not config.health_path.exists()
    assert not config.lock_path.exists()
    assert not config.plist_path.exists()
    backend = _ForecastOnlyBackend(target=target, operation_root=config.operation_root)

    result, exit_code = _forecast_command(config, backend)

    assert exit_code == 0
    assert result["FORECAST_STATUS"] == "READY"
    assert result["FINAL_RECOMMENDED_OUTPUT"] == [
        {"ticket_position": 1, "predicted_numbers": [4, 12, 24, 25, 26, 29]}
    ]
    after = _snapshot_files(config.operation_root)
    assert after == before
    assert not config.health_path.exists()
    assert not config.lock_path.exists()
    assert not config.plist_path.exists()
