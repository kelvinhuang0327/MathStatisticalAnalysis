from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from tools import b649_k235_predict as producer

CANDIDATE_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = CANDIDATE_ROOT
FIXTURE_ROOT = Path(os.environ["SCHEDULER_NATIVE_V6_FIXTURE_ROOT"]).resolve()
TASK_ID = "NUMBER2_9_NATIVE_V6_TWO_PATCH_INTEGRATED_ACCEPTANCE_20261124_R1"
TARGET = "115000098"
CUTOFF = "115000097"
TARGET_DATE = "2099-01-01"
SCHEDULED_AT = "2099-01-01T20:30:00+08:00"
AUTHORITY_NAME = "SYNTHETIC_NUMBER2_9_SCHEDULER_NATIVE_V6_AUTHORITY_V1"
AUTHORITY_SHA = hashlib.sha256(AUTHORITY_NAME.encode("utf-8")).hexdigest()
K5_IDS = (
    "legacy_biglotto__backtest_big_lotto_orthogonal_5bet__c4dff46c5a5e",
    "legacy_composite__quick_predict_5bet_ts3_markov_freqort",
    "legacy_biglotto__predict_5me_115000004__8a1c06ce1bdd",
)

sys.path.insert(0, str(CANDIDATE_ROOT))
sys.path.insert(0, str(CANDIDATE_ROOT / "src"))
MAPPER_MODULE_NAME = "lottolab.infrastructure.schedule_authority_mapper_candidate"
MAPPER_PATH = CANDIDATE_ROOT / "src/lottolab/infrastructure/schedule_authority_mapper_candidate.py"
MAPPER_SPEC = importlib.util.spec_from_file_location(MAPPER_MODULE_NAME, MAPPER_PATH)
assert MAPPER_SPEC is not None and MAPPER_SPEC.loader is not None
mapper_module = importlib.util.module_from_spec(MAPPER_SPEC)
sys.modules[MAPPER_SPEC.name] = mapper_module
MAPPER_SPEC.loader.exec_module(mapper_module)
SCHEDULER_PATH = CANDIDATE_ROOT / "tools/b649_goalc_local_scheduler.py"
SPEC = importlib.util.spec_from_file_location("scheduler_native_v6_candidate", SCHEDULER_PATH)
assert SPEC is not None and SPEC.loader is not None
scheduler = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = scheduler
SPEC.loader.exec_module(scheduler)

from lottolab.application.b649_next_undrawn_forecast import ForecastTimingError  # noqa: E402
from lottolab.domain.b649_next_undrawn_forecast import (  # noqa: E402
    OBJECTIVE,
    RANKING_POLICY_VERSION,
    digest,
)
from lottolab.domain.draws import LotteryType  # noqa: E402
from lottolab.domain.prospective_observer import (  # noqa: E402
    ObservationTarget,
    OutcomePresenceAtPrediction,
)
from lottolab.infrastructure import b649_live_forecast as live  # noqa: E402
from lottolab.infrastructure.b649_live_forecast import B649LiveForecastService  # noqa: E402
from lottolab.infrastructure.imports.csv_draws import normalized_draw_record_hash  # noqa: E402
from lottolab.infrastructure.persistence.draw_schema import (  # noqa: E402
    LocalDataPaths,
    initialize_schema,
)
from lottolab.infrastructure.persistence import research_schema as schema  # noqa: E402
from lottolab.infrastructure.persistence.research_repository import (  # noqa: E402
    SQLiteResearchRepository,
)
from lottolab.interfaces.api import b649_native_forecast  # noqa: E402
from lottolab.interfaces.api.app import create_app  # noqa: E402


def _rows() -> list[tuple[str, str, str, str, str]]:
    start_date = dt.date(2025, 1, 1)
    offsets = (0, 7, 14, 21, 28, 35)
    rows = []
    for index in range(505):
        draw_number = str(114999593 + index)
        draw_date = (start_date + dt.timedelta(days=index)).isoformat()
        main_numbers = sorted(((index + offset) % 49) + 1 for offset in offsets)
        special_number = ((index + 42) % 49) + 1
        rows.append(
            (
                draw_number,
                draw_date,
                json.dumps(main_numbers),
                json.dumps([special_number]),
                "BIG_LOTTO",
            )
        )
    return rows


def _write_inputs(root: Path) -> dict[str, Path]:
    root.mkdir(parents=True, exist_ok=True)
    data_directory = root / "canonical_draw_data"
    history_path = data_directory / "lottolab.db"
    initialize_schema(LocalDataPaths(data_directory, history_path))
    rows = _rows()
    rows.extend(
        [
            ("115000098", TARGET_DATE, "[1,2,3,4,5,6]", "[7]", "BIG_LOTTO"),
            ("115000099", "2099-01-08", "[2,3,4,5,6,7]", "[8]", "BIG_LOTTO"),
        ]
    )
    with sqlite3.connect(history_path) as connection:
        connection.execute(
            "INSERT INTO ingestion_runs "
            "(id, operation_type, status, lottery_type, source_filename, source_sha256, "
            "parser_version, total_count, inserted_count, skipped_count, conflict_count, "
            "failed_count, first_draw_number, last_draw_number, started_at, completed_at, "
            "error_summary) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "synthetic-history",
                "SYNTHETIC",
                "SUCCESS",
                "BIG_LOTTO",
                "synthetic.csv",
                "a" * 64,
                "test",
                len(rows),
                len(rows),
                0,
                0,
                0,
                rows[0][0],
                rows[-1][0],
                "2026-11-25T00:00:00Z",
                "2026-11-25T00:00:01Z",
                None,
            ),
        )
        connection.executemany(
            "INSERT INTO draws "
            "(lottery_type, draw_number, draw_date, main_numbers_json, special_numbers_json, "
            "normalized_record_hash, source_name, source_reference, ingestion_run_id, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    lottery_type,
                    draw_number,
                    draw_date,
                    main_json,
                    special_json,
                    normalized_draw_record_hash(
                        lottery_type=LotteryType.BIG_LOTTO,
                        draw_number=draw_number,
                        draw_date_value=dt.date.fromisoformat(draw_date),
                        main_numbers=tuple(json.loads(main_json)),
                        special_numbers=tuple(json.loads(special_json)),
                    ),
                    "synthetic",
                    None,
                    "synthetic-history",
                    "2026-11-25T00:00:00Z",
                    "2026-11-25T00:00:00Z",
                )
                for draw_number, draw_date, main_json, special_json, lottery_type in rows
            ],
        )

    descriptors = tuple(producer.production_catalog().list(lottery_type=LotteryType.BIG_LOTTO))
    descriptor_by_id = {item.strategy_id: item for item in descriptors}
    rank_history: dict[str, Any] = {
        "evidence_label": "SYNTHETIC",
        "hist": {"115000096": {"2": [], "3": [], "5": []}},
        "ids": {},
    }
    for k_value in (2, 3):
        candidates = [item for item in descriptors if item.native_ticket_count == k_value][:3]
        for rank, descriptor in enumerate(candidates, start=1):
            rank_history["hist"]["115000096"][str(k_value)].append([rank, descriptor.strategy_id])
            rank_history["ids"][descriptor.strategy_id] = [rank, descriptor.strategy_name]
    for rank, strategy_id in enumerate(K5_IDS, start=1):
        descriptor = descriptor_by_id[strategy_id]
        rank_history["hist"]["115000096"]["5"].append([rank, strategy_id])
        rank_history["ids"][strategy_id] = [rank, descriptor.strategy_name]
    rank_history_path = root / "SYNTHETIC_rank_history.json"
    rank_history_path.write_text(json.dumps(rank_history), encoding="utf-8")

    draw_by_number = {
        row[0]: {
            "lottery_type": "BIG_LOTTO",
            "draw_number": row[0],
            "draw_date": row[1],
            "main_numbers": json.loads(row[2]),
            "special_number": int(json.loads(row[3])[0]),
        }
        for row in rows
    }
    observations = []
    for strategy_id in sorted(K5_IDS):
        for draw_number in ("115000095", "115000096", "115000097"):
            end = next(index for index, row in enumerate(rows) if row[0] == draw_number) + 1
            causal_prefix = [draw_by_number[row[0]] for row in rows[:end]]
            observations.append(
                {
                    "strategy_id": strategy_id,
                    "strategy_version": descriptor_by_id[strategy_id].version,
                    "native_k": 5,
                    "draw_number": draw_number,
                    "draw_date": draw_by_number[draw_number]["draw_date"],
                    "causal_history_sha256": digest(causal_prefix),
                    "generation_config_sha256": "1" * 64,
                    "status": "EVALUATED",
                    "producer_fingerprint": hashlib.sha256(
                        f"SYNTHETIC:{strategy_id}".encode()
                    ).hexdigest(),
                    "tickets": [[1, 2, 3, 4, 5, 6]],
                }
            )
    ranking = {
        "evidence_label": "SYNTHETIC",
        "history_cutoff_draw": CUTOFF,
        "objective": OBJECTIVE,
        "ranking_policy_version": RANKING_POLICY_VERSION,
        "evaluation_window": "FULL",
        "observations": observations,
        "evidence_payload_sha256": digest(observations),
    }
    ranking_path = root / "SYNTHETIC_ranking_evidence.json"
    ranking_path.write_text(json.dumps(ranking), encoding="utf-8")

    schedule = {
        "evidence_label": "SYNTHETIC",
        "authority_name": AUTHORITY_NAME,
        "schedule_authority_sha256": AUTHORITY_SHA,
        "target_draw_number": TARGET,
        "scheduled_at": SCHEDULED_AT,
        "target_draw_date": TARGET_DATE,
        "timezone": "Asia/Taipei",
    }
    schedule_path = root / "SYNTHETIC_schedule_authority.json"
    schedule_path.write_text(json.dumps(schedule), encoding="utf-8")
    return {
        "root": root,
        "history": history_path,
        "rank_history": rank_history_path,
        "ranking": ranking_path,
        "schedule": schedule_path,
        "output": root / "SYNTHETIC_producer_output",
    }


def _fixture(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> tuple[dict[str, Path], Any, dict[str, Any]]:
    root = FIXTURE_ROOT / name
    if root.exists():
        shutil.rmtree(root)
    paths = _write_inputs(root / "inputs")
    paths["root"] = root
    store_dir = root / "research_store"
    store_paths = schema.ResearchDataPaths(
        data_directory=store_dir,
        database=store_dir / schema.RESEARCH_DATABASE_FILENAME,
    )
    original_guard = schema._reject_git_worktree_path

    def task_fixture_guard(path: Path) -> None:
        resolved = path.resolve()
        if resolved == FIXTURE_ROOT or resolved.is_relative_to(FIXTURE_ROOT):
            return
        original_guard(path)

    monkeypatch.setattr(schema, "_reject_git_worktree_path", task_fixture_guard)
    repository = SQLiteResearchRepository(store_paths)
    state: dict[str, Any] = {
        "clock": dt.datetime.now(dt.UTC) + dt.timedelta(minutes=5),
        "outcome": OutcomePresenceAtPrediction.ABSENT,
        "producer_runs": 0,
    }
    service = B649LiveForecastService(
        repository=repository,
        draw_paths=object(),  # type: ignore[arg-type]
        source_repository=PROJECT_ROOT,
        clock=lambda: state["clock"],
    )
    schedule_at = dt.datetime.fromisoformat(SCHEDULED_AT)
    observation_target = ObservationTarget(
        LotteryType.BIG_LOTTO,
        TARGET,
        dt.date.fromisoformat(TARGET_DATE),
    )
    schedule_record = SimpleNamespace(
        announcement=SimpleNamespace(target=observation_target, scheduled_at=schedule_at),
        normalized_announcement_hash=AUTHORITY_SHA,
        immutable_schedule_sha256=None,
    )

    class SyntheticOutcomeProbe:
        def __init__(self, _paths: object) -> None:
            pass

        def probe(self, _target: object, as_of: dt.datetime) -> SimpleNamespace:
            assert as_of.tzinfo is not None
            return SimpleNamespace(presence=state["outcome"])

    monkeypatch.setattr(B649LiveForecastService, "_schedule", lambda _self: schedule_record)
    monkeypatch.setattr(live, "SQLiteOfficialOutcomePresenceProbe", SyntheticOutcomeProbe)
    return paths, service, state


def _native_caller(paths: dict[str, Path], service: Any) -> Any:
    return scheduler.NativeV6CandidateCaller(
        scheduler.NativeV6CandidateInputs(
            canonical_repository=PROJECT_ROOT,
            evidence_root=paths["root"],
            schedule_binding_path=paths["schedule"],
            ranking_evidence_path=paths["ranking"],
            rank_history_path=paths["rank_history"],
            history_database_path=paths["history"],
            output_directory=paths["output"],
            task_id=TASK_ID,
        ),
        service,
    )


def _target(
    *, number: str = TARGET, draw_date: str = TARGET_DATE, scheduled_at: str = SCHEDULED_AT
) -> Any:
    return scheduler.PredictionTarget("BIG_LOTTO", number, draw_date, scheduled_at)


def _test_only_official_provider(
    *, draw_number: str = "115000120", draw_date: str = "20261205"
) -> tuple[Any, bytes, list[str]]:
    payload = json.dumps(
        {
            "evidence_label": "TEST_ONLY",
            "rtCode": 0,
            "content": {
                "nextDrawDateList": [
                    {
                        "gameCode": scheduler.SCHEDULE_GAME_CODE,
                        "drawTerm": draw_number,
                        "drawDate": draw_date,
                    }
                ]
            },
        },
        separators=(",", ":"),
    ).encode("utf-8")
    requests: list[str] = []

    def transport(request, _context, _timeout, _max_response_bytes):
        requests.append(request.full_url)
        return payload

    provider = scheduler.TaiwanLotteryScheduleProvider(
        https_client=scheduler.OfficialHttpsClient(transport=transport)
    )
    return provider, payload, requests


def test_official_schedule_admission_uses_provider_and_keeps_synthetic_gate_separate() -> None:
    observed_at = dt.datetime(2026, 11, 24, 4, 0, tzinfo=dt.UTC)
    target = _target(
        number="115000120",
        draw_date="2026-12-05",
        scheduled_at="2026-12-05T20:30:00+08:00",
    )
    provider, payload, requests = _test_only_official_provider()

    binding = scheduler.NativeV6CandidateCaller._admit_official_schedule(
        provider, target, observed_at
    )
    test_output = {"evidence_label": "TEST_ONLY", "admission_count": 1}
    assert test_output["evidence_label"] == "TEST_ONLY"
    assert requests == [scheduler.SCHEDULE_URL]
    assert binding["evidence_label"] == "OFFICIAL_AUTHORITY"
    assert binding["source_payload_sha256"] == hashlib.sha256(payload).hexdigest()
    assert binding["target_draw_number"] == target.draw_number
    assert binding["target_draw_date"] == target.draw_date
    assert binding["timezone"] == "Asia/Taipei"

    synthetic = {
        "evidence_label": "SYNTHETIC",
        "scheduled_at": target.scheduled_at,
        "target_draw_number": target.draw_number,
        "target_draw_date": target.draw_date,
        "timezone": "Asia/Taipei",
    }
    scheduler.NativeV6CandidateCaller._validate_schedule_binding(
        synthetic, target, dt.datetime.fromisoformat(target.scheduled_at)
    )
    forged_official_json = {**synthetic, "evidence_label": "OFFICIAL_AUTHORITY"}
    with pytest.raises(scheduler.NativeV6CandidateRejected, match="marked SYNTHETIC"):
        scheduler.NativeV6CandidateCaller._validate_schedule_binding(
            forged_official_json, target, dt.datetime.fromisoformat(target.scheduled_at)
        )


def test_official_schedule_admission_rejects_target_date_mismatch() -> None:
    observed_at = dt.datetime(2026, 11, 24, 4, 0, tzinfo=dt.UTC)
    provider, _payload, requests = _test_only_official_provider()
    conflicting_target = _target(
        number="115000120",
        draw_date="2026-12-06",
        scheduled_at="2026-12-06T20:30:00+08:00",
    )

    with pytest.raises(scheduler.NativeV6CandidateRejected, match="conflicts with resolved target"):
        scheduler.NativeV6CandidateCaller._admit_official_schedule(
            provider, conflicting_target, observed_at
        )
    assert requests == [scheduler.SCHEDULE_URL]


class _SchedulerBackend:
    def __init__(self, target: Any) -> None:
        self.target = target
        self.resolve_calls = 0
        self.materialize_calls = 0

    def refresh_schedule(self, observed_at: dt.datetime) -> Any:
        return scheduler.ScheduleRefreshResult(
            status="REFRESHED",
            source_url="SYNTHETIC",
            source_payload_sha256=AUTHORITY_SHA,
            observed_at=observed_at,
            inventory_count=1,
            b649_targets=(self.target.draw_number,),
            strict_tls_fallback_used=False,
        )

    def resolve_target(self) -> Any:
        self.resolve_calls += 1
        return self.target if self.resolve_calls % 2 == 1 else None

    def inspect_predictions(self, _target: Any) -> Any:
        return scheduler.PredictionInventory((), (), (), ())

    def materialize_forecast(self, *_args: Any, **_kwargs: Any) -> dict[str, object]:
        self.materialize_calls += 1
        return {"status": "WAITING"}

    def materialize_predraw_portfolios(self, *_args: Any, **_kwargs: Any) -> dict[str, object]:
        return {"status": "WAITING"}

    def generate_predraw(self, *_args: Any, **_kwargs: Any) -> dict[str, object]:
        return {"created_prediction_paths": [], "failures": []}

    def sync_official_outcome(self, _target: Any) -> dict[str, object]:
        return {"status": "SYNTHETIC_SYNCED"}

    def complete_postdraw(self, *_args: Any, **_kwargs: Any) -> Any:
        return scheduler.PostDrawResult("OUTCOME_AVAILABLE", "COMPLETE", "CURRENT", "RECONCILED")

    def run_shadow_postdraw(self, *_args: Any, **_kwargs: Any) -> dict[str, object]:
        return {"status": "SYNTHETIC_SHADOW_NOT_RUN"}


def _scheduler_config(root: Path) -> Any:
    source_root = CANDIDATE_ROOT
    operation_root = root / "operation"
    data_root = root / "scheduler_data"
    scheduler_root = operation_root / "scheduler"
    return scheduler.SchedulerConfig(
        label="SYNTHETIC_NATIVE_V6_CANDIDATE",
        version="TASK_LOCAL_R1",
        canonical_repository=PROJECT_ROOT,
        source_worktree=source_root,
        python_executable=Path(sys.executable),
        script_path=source_root / "tools/b649_goalc_local_scheduler.py",
        operation_root=operation_root,
        data_root=data_root,
        database=data_root / "lottolab.db",
        announcement=data_root / "announcement.json",
        scheduler_root=scheduler_root,
        lock_path=scheduler_root / "cycle.lock",
        health_path=scheduler_root / "health.json",
        stdout_path=scheduler_root / "stdout.log",
        stderr_path=scheduler_root / "stderr.log",
        plist_path=root / "candidate.plist",
        start_interval_seconds=scheduler.START_INTERVAL_SECONDS,
        stale_after_seconds=scheduler.STALE_AFTER_SECONDS,
        expected_stream_count=scheduler.EXPECTED_STREAM_COUNT,
    )


def _read_pointer_rows(path: Path) -> tuple[int, int]:
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        connection.execute("PRAGMA query_only=ON")
        versions = connection.execute(
            "SELECT count(*) FROM research_live_forecast_versions"
        ).fetchone()[0]
        pointers = connection.execute(
            "SELECT count(*) FROM research_live_forecast_current_pointer"
        ).fetchone()[0]
    return int(versions), int(pointers)


def test_scheduler_opt_in_executes_real_chain_and_repeat_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, service, state = _fixture("positive", monkeypatch)
    caller = _native_caller(paths, service)
    backend = _SchedulerBackend(_target())
    config = _scheduler_config(paths["root"])
    fixed_now = state["clock"]

    first = scheduler.run_scheduler_cycle(
        config,
        backend,
        clock=lambda: fixed_now,
        source_head_resolver=lambda _path: "fbe51fd2a422e7bcd8cb2ecb3f9bf35089963535",
        native_v6_caller=caller,
    )
    assert first["native_v6"]["status"] == "COMMITTED", first["native_v6"].get("reason")
    assert first["native_v6"]["producer_invoked"] is True
    assert first["native_v6"]["strategy_count"] == 3
    assert first["native_v6"]["ticket_count"] == 15
    output_path = Path(str(first["native_v6"]["output_path"]))
    before_sha = hashlib.sha256(output_path.read_bytes()).hexdigest()
    producer_output = json.loads(output_path.read_text(encoding="utf-8"))
    verified_records = producer_output["provenance"]["history_snapshot"]["verified_canonical"]
    assert verified_records["history_ref"]["last_draw_number"] == CUTOFF
    assert len(verified_records["normalized_records"]) == 505
    assert {"115000098", "115000099"}.isdisjoint(
        {row["draw_number"] for row in verified_records["normalized_records"]}
    )
    assert _read_pointer_rows(service.repository.paths.database) == (1, 1)

    repository = service.repository
    monkeypatch.setattr(b649_native_forecast, "_default_repository_factory", lambda: repository)
    with TestClient(create_app()) as client:
        response = client.get(
            "/api/b649/native-forecast/current",
            params={
                "target_draw_number": TARGET,
                "target_draw_date": TARGET_DATE,
            },
        )
    assert response.status_code == 200
    body = response.json()
    scope = (
        body["scope"]["lottery_type"],
        body["scope"]["target_draw_number"],
        body["scope"]["target_draw_date"],
        body["scope"]["forecast_stream_id"],
        body["scope"]["forecast_stream_version"],
    )
    readback = repository.read_current_native(scope)
    assert readback is not None
    assert body["payload"] == json.loads(readback.forecast.payload_bytes)
    assert body["request_identity"]["version"] == 1
    assert body["request_identity"]["committed_at"] == readback.committed_at

    second = scheduler.run_scheduler_cycle(
        config,
        backend,
        clock=lambda: fixed_now,
        source_head_resolver=lambda _path: "fbe51fd2a422e7bcd8cb2ecb3f9bf35089963535",
        native_v6_caller=caller,
    )
    assert second["native_v6"]["status"] == "ALREADY_COMMITTED"
    assert second["native_v6"]["producer_invoked"] is False
    assert hashlib.sha256(output_path.read_bytes()).hexdigest() == before_sha
    assert _read_pointer_rows(service.repository.paths.database) == (1, 1)


def test_default_path_is_unchanged_and_due_target_is_due_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, service, _state = _fixture("default-and-due", monkeypatch)
    caller = _native_caller(paths, service)
    config = _scheduler_config(paths["root"])
    fixed_now = dt.datetime.now(dt.UTC)
    default_backend = _SchedulerBackend(_target())
    default = scheduler.run_scheduler_cycle(
        config,
        default_backend,
        clock=lambda: fixed_now,
        source_head_resolver=lambda _path: "fbe51fd2a422e7bcd8cb2ecb3f9bf35089963535",
    )
    assert "native_v6" not in default
    assert default_backend.materialize_calls == 1
    assert not paths["output"].exists()

    due_target = _target(
        number="115000097",
        draw_date=fixed_now.astimezone(scheduler.TAIPEI).date().isoformat(),
        scheduled_at=(fixed_now.astimezone(scheduler.TAIPEI) - dt.timedelta(hours=1)).isoformat(),
    )
    due_backend = _SchedulerBackend(due_target)
    due_config = _scheduler_config(paths["root"] / "due")
    due = scheduler.run_scheduler_cycle(
        due_config,
        due_backend,
        clock=lambda: fixed_now,
        source_head_resolver=lambda _path: "fbe51fd2a422e7bcd8cb2ecb3f9bf35089963535",
        native_v6_caller=caller,
    )
    assert due["native_v6"]["status"] == "SKIPPED_DUE_FIRST"
    assert due["native_v6"]["producer_invoked"] is False
    assert not paths["output"].exists()
    assert _read_pointer_rows(service.repository.paths.database) == (0, 0)


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("schedule", "schedule binding conflicts"),
        ("ranking", "ranking cutoff does not match"),
        ("expired", "target deadline has passed"),
    ],
)
def test_invalid_binding_stale_ranking_and_expired_clock_reject_without_commit(
    case: str,
    message: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, service, _state = _fixture(f"negative-{case}", monkeypatch)
    if case == "schedule":
        schedule = json.loads(paths["schedule"].read_text(encoding="utf-8"))
        schedule["scheduled_at"] = "2099-01-01T20:31:00+08:00"
        paths["schedule"].write_text(json.dumps(schedule), encoding="utf-8")
    elif case == "ranking":
        ranking = json.loads(paths["ranking"].read_text(encoding="utf-8"))
        ranking["history_cutoff_draw"] = "115000096"
        paths["ranking"].write_text(json.dumps(ranking), encoding="utf-8")
    caller = _native_caller(paths, service)
    observed_at = (
        dt.datetime(2100, 1, 1, tzinfo=dt.UTC) if case == "expired" else dt.datetime.now(dt.UTC)
    )
    with pytest.raises(scheduler.NativeV6CandidateRejected, match=message):
        caller(_target(), observed_at)
    assert not paths["output"].exists()
    assert _read_pointer_rows(service.repository.paths.database) == (0, 0)


def test_tampered_canonical_history_rejects_before_artifact_or_store_pointer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, service, _state = _fixture("tampered-canonical-history", monkeypatch)
    with sqlite3.connect(paths["history"]) as connection:
        connection.execute(
            "UPDATE draws SET main_numbers_json = ? "
            "WHERE lottery_type = 'BIG_LOTTO' AND draw_number = ?",
            ("[1,2,3,4,5,49]", CUTOFF),
        )

    caller = _native_caller(paths, service)
    with pytest.raises(scheduler.NativeV6CandidateRejected, match="Producer exited"):
        caller(_target(), dt.datetime.now(dt.UTC))
    assert list(paths["output"].iterdir()) == []
    assert _read_pointer_rows(service.repository.paths.database) == (0, 0)


@pytest.mark.parametrize("missing", ["schedule", "ranking", "history"])
def test_missing_required_input_rejects_without_commit(
    missing: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, service, _state = _fixture(f"missing-{missing}", monkeypatch)
    if missing == "schedule":
        paths["schedule"].unlink()
    elif missing == "ranking":
        paths["ranking"].unlink()
    else:
        paths["history"].unlink()
    with pytest.raises(scheduler.NativeV6CandidateRejected, match="unavailable"):
        _native_caller(paths, service)
    assert _read_pointer_rows(service.repository.paths.database) == (0, 0)


def test_real_service_rejects_opened_target_without_store_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, service, state = _fixture("opened-target", monkeypatch)
    state["outcome"] = OutcomePresenceAtPrediction.PRESENT
    caller = _native_caller(paths, service)
    with pytest.raises(ForecastTimingError, match="OUTCOME_PRESENT_OR_DEADLINE_REACHED"):
        caller(_target(), dt.datetime.now(dt.UTC))
    assert (paths["output"] / f"v6_native_prediction_{TARGET}.json").is_file()
    assert _read_pointer_rows(service.repository.paths.database) == (0, 0)


def test_non_fixture_service_database_is_rejected_before_any_read_or_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, _service, _state = _fixture("non-fixture-store", monkeypatch)
    outside_service = SimpleNamespace(
        repository=SimpleNamespace(
            paths=SimpleNamespace(database=PROJECT_ROOT / "data/databases/NO_OPEN_TEST.sqlite3")
        ),
        commit_native_input=lambda *_args: None,
    )
    with pytest.raises(scheduler.NativeV6CandidateRejected, match="inside the task fixture root"):
        _native_caller(paths, outside_service)
