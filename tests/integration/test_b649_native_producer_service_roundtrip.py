"""End-to-end synthetic v6 Native Producer → Service → Store → Reader → HTTP."""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import os
import sqlite3
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from tools import b649_k235_predict as producer

from lottolab.application.b649_next_undrawn_forecast import ForecastTimingError
from lottolab.domain.b649_next_undrawn_forecast import (
    OBJECTIVE,
    RANKING_POLICY_VERSION,
    digest,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.prospective_observer import (
    ObservationTarget,
    OutcomePresenceAtPrediction,
)
from lottolab.domain.research_live_forecast import (
    NATIVE_STREAM,
    NATIVE_STREAM_VERSION,
    LiveForecastInput,
)
from lottolab.infrastructure import b649_live_forecast as live
from lottolab.infrastructure import b649_v6_native_input_adapter_candidate as adapter_module
from lottolab.infrastructure.b649_live_forecast import B649LiveForecastService
from lottolab.infrastructure.b649_v6_native_input_adapter_candidate import (
    adapt_native_input,
)
from lottolab.infrastructure.imports.csv_draws import normalized_draw_record_hash
from lottolab.infrastructure.persistence import research_repository as repository_module
from lottolab.infrastructure.persistence import research_schema as schema
from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataPaths,
    initialize_schema,
)
from lottolab.infrastructure.persistence.research_repository import (
    ResearchConflictError,
    ResearchRepositoryError,
    SQLiteResearchRepository,
)
from lottolab.interfaces.api import app as api_app
from lottolab.interfaces.api import b649_native_forecast

SYNTHETIC_TASK_ID = "SYNTHETIC_NUMBER2_9_NATIVE_PRODUCER_SERVICE_E2E"
SYNTHETIC_CUTOFF = "115000097"
SYNTHETIC_TARGET = "115000098"
SYNTHETIC_TARGET_DATE = "2099-01-01"
SYNTHETIC_AUTHORITY_NAME = "SYNTHETIC_NUMBER2_9_E2E_SCHEDULE_AUTHORITY_V1"
SYNTHETIC_AUTHORITY_SHA256 = hashlib.sha256(SYNTHETIC_AUTHORITY_NAME.encode("utf-8")).hexdigest()
SYNTHETIC_K5_IDS = (
    "legacy_biglotto__backtest_big_lotto_orthogonal_5bet__c4dff46c5a5e",
    "legacy_composite__quick_predict_5bet_ts3_markov_freqort",
    "legacy_biglotto__predict_5me_115000004__8a1c06ce1bdd",
)


def _history_rows() -> list[tuple[str, str, str, str, str]]:
    base_date = dt.date(2025, 1, 1)
    offsets = (0, 7, 14, 21, 28, 35)
    rows = []
    for index in range(505):
        draw_number = str(114999593 + index)
        draw_date = (base_date + dt.timedelta(days=index)).isoformat()
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


def _synthetic_history_digest(rows: list[tuple[str, str, str, str, str]]) -> str:
    draw_rows = [
        {
            "lottery_type": "BIG_LOTTO",
            "draw_number": draw_number,
            "draw_date": draw_date,
            "main_numbers": json.loads(main_json),
            "special_number": int(json.loads(special_json)[0]),
        }
        for draw_number, draw_date, main_json, special_json, _lottery_type in rows
    ]
    return digest(draw_rows)


def _write_synthetic_producer_inputs(root: Path) -> tuple[Path, Path, Path, Path]:
    rows = _history_rows()
    all_rows = [
        *rows,
        (SYNTHETIC_TARGET, SYNTHETIC_TARGET_DATE, "[1,2,3,4,5,6]", "[7]", "BIG_LOTTO"),
        ("115000099", "2099-01-08", "[2,3,4,5,6,7]", "[8]", "BIG_LOTTO"),
    ]
    data_directory = root / "canonical_draw_data"
    database = data_directory / "lottolab.db"
    initialize_schema(LocalDataPaths(data_directory, database))
    with sqlite3.connect(database) as connection:
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
                len(all_rows),
                len(all_rows),
                0,
                0,
                0,
                all_rows[0][0],
                all_rows[-1][0],
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
                for draw_number, draw_date, main_json, special_json, lottery_type in all_rows
            ],
        )

    descriptors = tuple(producer.production_catalog().list(lottery_type=LotteryType.BIG_LOTTO))
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
    descriptor_by_id = {item.strategy_id: item for item in descriptors}
    for rank, strategy_id in enumerate(SYNTHETIC_K5_IDS, start=1):
        descriptor = descriptor_by_id[strategy_id]
        rank_history["hist"]["115000096"]["5"].append([rank, strategy_id])
        rank_history["ids"][strategy_id] = [rank, descriptor.strategy_name]
    rank_history_path = root / "SYNTHETIC_rank_history.json"
    rank_history_path.write_text(json.dumps(rank_history), encoding="utf-8")

    draw_json_by_number = {
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
    for strategy_id in sorted(SYNTHETIC_K5_IDS):
        for draw_number in ("115000095", "115000096", "115000097"):
            end = next(index for index, row in enumerate(rows) if row[0] == draw_number) + 1
            causal_prefix = [draw_json_by_number[row[0]] for row in rows[:end]]
            observations.append(
                {
                    "strategy_id": strategy_id,
                    "strategy_version": descriptor_by_id[strategy_id].version,
                    "native_k": 5,
                    "draw_number": draw_number,
                    "draw_date": draw_json_by_number[draw_number]["draw_date"],
                    "causal_history_sha256": digest(causal_prefix),
                    "generation_config_sha256": "1" * 64,
                    "status": "EVALUATED",
                    "producer_fingerprint": hashlib.sha256(
                        f"SYNTHETIC:{strategy_id}".encode()
                    ).hexdigest(),
                    "tickets": [[1, 2, 3, 4, 5, 6]],
                }
            )
    ranking_evidence = {
        "evidence_label": "SYNTHETIC",
        "history_cutoff_draw": SYNTHETIC_CUTOFF,
        "objective": OBJECTIVE,
        "ranking_policy_version": RANKING_POLICY_VERSION,
        "evaluation_window": "FULL",
        "observations": observations,
        "evidence_payload_sha256": digest(observations),
    }
    ranking_path = root / "SYNTHETIC_ranking_evidence.json"
    ranking_path.write_text(json.dumps(ranking_evidence), encoding="utf-8")

    schedule_binding = {
        "evidence_label": "SYNTHETIC",
        "authority_name": SYNTHETIC_AUTHORITY_NAME,
        "schedule_authority_sha256": SYNTHETIC_AUTHORITY_SHA256,
        "target_draw_number": SYNTHETIC_TARGET,
        "scheduled_at": "2099-01-01T20:30:00+08:00",
        "target_draw_date": SYNTHETIC_TARGET_DATE,
        "timezone": "Asia/Taipei",
    }
    schedule_path = root / "SYNTHETIC_schedule_authority.json"
    schedule_path.write_text(json.dumps(schedule_binding), encoding="utf-8")
    return database, rank_history_path, schedule_path, ranking_path


@pytest.fixture(scope="session")
def producer_bundle(tmp_path_factory: pytest.TempPathFactory) -> Any:
    """Run the real CLI v6 opt-in Producer against an isolated synthetic source DB."""
    root = tmp_path_factory.mktemp("native_v6_e2e") / "producer_cli_run"
    root = root.resolve()
    if root.exists():
        raise RuntimeError(f"refusing to reuse an existing task fixture: {root}")
    root.mkdir(parents=True)
    previous_argv = list(sys.argv)
    original_source_resolver = producer._resolve_source_execution
    base_commit = os.environ.get("NATIVE_CANDIDATE_BASE_COMMIT")
    base_tree = os.environ.get("NATIVE_CANDIDATE_BASE_TREE")
    if base_commit and base_tree:
        source_execution = {
            "repository": str(producer.REPO_ROOT),
            "commit": base_commit,
            "tree": base_tree,
            "loaded_code_sha256": hashlib.sha256(Path(producer.__file__).read_bytes()).hexdigest(),
            "pre_draw_proof_status": "LOCAL_ONLY",
        }
        producer._resolve_source_execution = lambda _override=None: source_execution
    try:
        database, rank_path, schedule_path, ranking_path = _write_synthetic_producer_inputs(root)
        output_dir = root / "SYNTHETIC_producer_output"
        sys.argv = [
            "b649_k235_predict.py",
            "--db-path",
            str(database),
            "--rank-history-path",
            str(rank_path),
            "--cutoff-draw",
            SYNTHETIC_CUTOFF,
            "--target-draw",
            SYNTHETIC_TARGET,
            "--output-dir",
            str(output_dir),
            "--emit-v6-provenance",
            "--schedule-binding-json",
            str(schedule_path),
            "--ranking-evidence-json",
            str(ranking_path),
            "--task-id",
            SYNTHETIC_TASK_ID,
            "--overwrite",
        ]
        producer.main()
        producer._resolve_source_execution = original_source_resolver
        result_path = output_dir / f"v6_native_prediction_{SYNTHETIC_TARGET}.json"
        bundle = json.loads(result_path.read_text(encoding="utf-8"))
        yield root, bundle
    finally:
        sys.argv = previous_argv
        producer._resolve_source_execution = original_source_resolver


def _new_service(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    bundle: dict[str, Any],
) -> tuple[B649LiveForecastService, SQLiteResearchRepository, dict[str, Any]]:
    research_dir = root / "research_store"
    paths = schema.ResearchDataPaths(
        data_directory=research_dir,
        database=research_dir / schema.RESEARCH_DATABASE_FILENAME,
    )
    repository = SQLiteResearchRepository(paths)
    target = bundle["provenance"]["target"]
    scheduled_at = dt.datetime.fromisoformat(target["scheduled_at"])
    observation_target = ObservationTarget(
        LotteryType.BIG_LOTTO,
        target["target_draw_number"],
        dt.date.fromisoformat(target["target_draw_date"]),
    )
    record = SimpleNamespace(
        announcement=SimpleNamespace(target=observation_target, scheduled_at=scheduled_at),
        normalized_announcement_hash=target["schedule_authority_sha256"],
        immutable_schedule_sha256=None,
    )
    state: dict[str, Any] = {
        "clock": dt.datetime.now(dt.UTC) + dt.timedelta(seconds=10),
        "outcome": OutcomePresenceAtPrediction.ABSENT,
        "probe_calls": 0,
    }

    class SyntheticOutcomeProbe:
        def __init__(self, _paths: object) -> None:
            pass

        def probe(
            self,
            _target: ObservationTarget,
            as_of: dt.datetime,
        ) -> SimpleNamespace:
            state["probe_calls"] += 1
            return SimpleNamespace(presence=state["outcome"])

    monkeypatch.setattr(B649LiveForecastService, "_schedule", lambda _self: record)
    monkeypatch.setattr(live, "SQLiteOfficialOutcomePresenceProbe", SyntheticOutcomeProbe)
    service = B649LiveForecastService(
        repository=repository,
        draw_paths=object(),  # type: ignore[arg-type]
        source_repository=producer.REPO_ROOT,
        clock=lambda: state["clock"],
    )
    return service, repository, state


def _store_snapshot(
    repository: SQLiteResearchRepository,
) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
    with sqlite3.connect(f"file:{repository.paths.database}?mode=ro", uri=True) as connection:
        versions = connection.execute(
            "SELECT version, request_id, request_sha256, payload_sha256, committed_at, "
            "pointer_advanced FROM research_live_forecast_versions ORDER BY version"
        ).fetchall()
        pointers = connection.execute(
            "SELECT lottery_type, target_draw_number, target_draw_date, "
            "forecast_stream_id, forecast_stream_version, version, run_id "
            "FROM research_live_forecast_current_pointer ORDER BY version"
        ).fetchall()
    return versions, pointers


def _assert_synthetic_provenance(bundle: dict[str, Any]) -> LiveForecastInput:
    native = bundle["native_result"]
    provenance = bundle["provenance"]
    for module in (
        producer,
        adapter_module,
        live,
        repository_module,
        b649_native_forecast,
        api_app,
    ):
        module_path = Path(module.__file__).resolve()
        assert module_path.is_relative_to(producer.REPO_ROOT)
    source = provenance["source_execution"]
    producer_path = Path(producer.__file__).resolve()
    assert source["repository"] == str(producer.REPO_ROOT)
    assert len(source["commit"]) == 40
    assert len(source["tree"]) == 40
    assert source["loaded_code_sha256"] == hashlib.sha256(producer_path.read_bytes()).hexdigest()

    runtime = provenance["runtime_manifest"]
    assert runtime["python"]["implementation"] == "CPython"
    assert runtime["python"]["version"].startswith("3.13.")
    assert Path(runtime["python"]["executable"]).resolve() == Path(sys.executable).resolve()
    runtime_material = {key: value for key, value in runtime.items() if key != "sha256"}
    assert runtime["sha256"] == digest(runtime_material)

    history = provenance["history_snapshot"]
    assert len(history["draws"]) == 505
    assert history["draws"][-1]["draw_number"] == SYNTHETIC_CUTOFF
    assert history["sha256"] == digest(history["draws"])
    assert provenance["target"]["causal_history_sha256"] == history["sha256"]
    assert provenance["target"]["schedule_authority_sha256"] == SYNTHETIC_AUTHORITY_SHA256
    verified = history["verified_canonical"]
    assert verified["authority"].endswith("open_verified_snapshot")
    assert verified["schema_version"] == "LOTTOLAB_PRE_OUTCOME_CAUSAL_HISTORY_V1"
    assert verified["target"]["draw_number"] == SYNTHETIC_TARGET
    assert verified["target"]["draw_date"] == SYNTHETIC_TARGET_DATE
    assert verified["history_ref"]["draw_count"] == 505
    assert verified["history_ref"]["last_draw_number"] == SYNTHETIC_CUTOFF
    assert verified["history_ref"]["history_sha256"] != history["sha256"]
    assert len(verified["normalized_records"]) == 505
    assert {SYNTHETIC_TARGET, "115000099"}.isdisjoint(
        {row["draw_number"] for row in verified["normalized_records"]}
    )
    last_draw = history["draws"][-1]
    assert verified["normalized_records"][-1] == {
        "draw_number": last_draw["draw_number"],
        "draw_date": last_draw["draw_date"],
        "normalized_record_hash": normalized_draw_record_hash(
            lottery_type=LotteryType.BIG_LOTTO,
            draw_number=last_draw["draw_number"],
            draw_date_value=dt.date.fromisoformat(last_draw["draw_date"]),
            main_numbers=tuple(last_draw["main_numbers"]),
            special_numbers=(int(last_draw["special_number"]),),
        ),
    }
    assert "SYNTHETIC" in native["task_id"]
    assert native["target_outcome"] == "UNOBSERVED_NOT_READ"
    assert native["target_rows_selected"] is False
    assert int(provenance["target"]["data_cutoff"]) < int(native["prediction_target"])
    assert all(
        int(row["draw_number"]) < int(native["prediction_target"]) for row in history["draws"]
    )

    catalog = provenance["catalog"]
    configs = provenance["generation_configs"]
    assert {row["strategy_id"] for row in catalog} == set(SYNTHETIC_K5_IDS)
    assert [row["strategy_id"] for row in catalog] == sorted(SYNTHETIC_K5_IDS)
    assert [row["strategy_id"] for row in configs] == sorted(SYNTHETIC_K5_IDS)
    for catalog_row in catalog:
        adapter_path = Path(catalog_row["adapter_source_path"])
        assert adapter_path.is_file()
        assert (
            hashlib.sha256(adapter_path.read_bytes()).hexdigest()
            == catalog_row["adapter_source_sha256"]
        )
    effective = provenance["effective_parameters"]
    assert effective["sha256"] == digest({"strategies": effective["strategies"]})
    effective_by_id = {row["strategy_id"]: row for row in effective["strategies"]}
    registry = producer.ExecutableRegistry(producer.production_catalog())
    for strategy_id in SYNTHETIC_K5_IDS:
        adapter_class = registry.load_adapter(strategy_id)
        adapter_identity = f"{adapter_class.__module__}:{adapter_class.__qualname__}"
        assert effective_by_id[strategy_id]["adapter_class"] == adapter_identity
        assert (
            next(row for row in catalog if row["strategy_id"] == strategy_id)["adapter_path"]
            == adapter_identity
        )
    assert all(
        effective_by_id[config["strategy_id"]]["generation_config_sha256"] == digest(config)
        for config in configs
    )
    ranking = provenance["ranking_evidence"]
    assert ranking["evidence_label"] == "SYNTHETIC"
    assert ranking["objective"] == OBJECTIVE
    assert ranking["ranking_policy_version"] == RANKING_POLICY_VERSION
    assert ranking["evidence_payload_sha256"] == digest(ranking["observations"])
    started = dt.datetime.fromisoformat(provenance["generation_started_at"])
    finished = dt.datetime.fromisoformat(provenance["generation_finished_at"])
    assert started.tzinfo is not None and finished.tzinfo is not None
    assert started <= finished

    forecast = adapt_native_input(native, provenance)
    assert isinstance(forecast, LiveForecastInput)
    forecast.validate()
    return forecast


def test_native_producer_service_store_reader_and_http_roundtrip(
    producer_bundle: tuple[Path, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Actual CLI output is committed, read back, and served without changing K5 tickets."""
    root, bundle = producer_bundle
    assert schema.CURRENT_SCHEMA_VERSION == 6
    forecast = _assert_synthetic_provenance(bundle)
    native = bundle["native_result"]
    provenance = bundle["provenance"]
    producer_strategies = native["strategies"]
    assert len(producer_strategies) == 3
    assert [row["strategy_id"] for row in producer_strategies] == list(SYNTHETIC_K5_IDS)
    versions_by_id = {row["strategy_id"]: row["version"] for row in provenance["catalog"]}
    assert [row["strategy_version"] for row in producer_strategies] == [
        versions_by_id[row["strategy_id"]] for row in producer_strategies
    ]
    assert sum(len(row["tickets"]) for row in producer_strategies) == 15
    for strategy in producer_strategies:
        assert len(strategy["rng_semantics"]) > 0
        assert [ticket["position"] for ticket in strategy["tickets"]] == [1, 2, 3, 4, 5]

    service, repository, state = _new_service(root / "valid", monkeypatch, bundle)
    assert repository.paths.database.resolve().is_relative_to(root.resolve())
    effective_rows = provenance["effective_parameters"]["strategies"]
    assert len(effective_rows) == 3
    assert all(row["adapter_class"] for row in effective_rows)

    captured_forecasts: list[LiveForecastInput] = []
    original_commit = repository.commit_live_forecast

    def capture_store_input(value: LiveForecastInput, *args: Any, **kwargs: Any) -> Any:
        captured_forecasts.append(value)
        return original_commit(value, *args, **kwargs)

    monkeypatch.setattr(repository, "commit_live_forecast", capture_store_input)
    result = service.commit_native_input(native, provenance)
    assert state["probe_calls"] >= 1
    assert len(captured_forecasts) == 1
    assert captured_forecasts[0].request_id == forecast.request_id
    assert result.version == 1
    assert result.pointer_advanced is True
    assert result.idempotent is False
    versions, pointers = _store_snapshot(repository)
    assert len(versions) == 1
    assert len(pointers) == 1
    assert versions[0][0] == 1
    assert versions[0][1] == forecast.request_id
    assert versions[0][2] == forecast.request_sha256
    assert versions[0][3] == result.payload_sha256
    assert versions[0][5] == 1
    assert pointers[0][0:5] == (
        "BIG_LOTTO",
        SYNTHETIC_TARGET,
        SYNTHETIC_TARGET_DATE,
        NATIVE_STREAM,
        NATIVE_STREAM_VERSION,
    )
    assert pointers[0][5] == 1
    assert pointers[0][6] == result.run_id

    scope = (
        "BIG_LOTTO",
        SYNTHETIC_TARGET,
        SYNTHETIC_TARGET_DATE,
        NATIVE_STREAM,
        NATIVE_STREAM_VERSION,
    )
    readback = repository.read_current_native(scope)
    assert readback is not None
    assert readback.version == result.version
    assert readback.run_id == result.run_id
    assert readback.committed_at == versions[0][4]
    assert readback.forecast.request_id == forecast.request_id
    assert readback.forecast.request_sha256 == forecast.request_sha256
    assert readback.forecast.payload_sha256 == result.payload_sha256

    payload = json.loads(captured_forecasts[0].payload_bytes)
    native_rows = payload["native_strategies"]
    assert len(native_rows) == 3
    assert sum(len(row["native_positions"]) for row in native_rows) == 15
    for producer_row, stored_row in zip(producer_strategies, native_rows, strict=True):
        assert producer_row["strategy_id"] == stored_row["strategy_id"]
        assert producer_row["strategy_version"] == stored_row["strategy_version"]
        assert [item["position"] for item in stored_row["native_positions"]] == [1, 2, 3, 4, 5]
        assert [item["numbers"] for item in stored_row["native_positions"]] == [
            ticket["emitted_main_numbers"] for ticket in producer_row["tickets"]
        ]
    k5_buckets = [row for row in payload["buckets"] if row["native_k"] == 5]
    assert len(k5_buckets) == 1
    k5_bucket = k5_buckets[0]
    assert k5_bucket["bucket"].startswith("K5:")
    rank_first = native_rows[0]
    assert k5_bucket["selected"]["strategy_id"] == rank_first["strategy_id"]
    assert k5_bucket["tickets"] == [row["numbers"] for row in rank_first["native_positions"]]

    assert readback.forecast.payload_bytes == captured_forecasts[0].payload_bytes
    assert readback.forecast.target["target_draw_number"] == SYNTHETIC_TARGET

    repeated = service.commit_native_input(native, provenance)
    assert repeated.idempotent is True
    assert repeated.version == result.version
    assert repeated.run_id == result.run_id
    assert repeated.payload_sha256 == result.payload_sha256
    assert _store_snapshot(repository) == (versions, pointers)

    monkeypatch.setattr(b649_native_forecast, "_default_repository_factory", lambda: repository)
    monkeypatch.delenv("LOTTOLAB_REPLAY_BACKFILL_DB", raising=False)
    monkeypatch.setenv("LOTTOLAB_DATA_DIR", str(root / "SYNTHETIC_api_data"))
    app = api_app.create_app()
    with TestClient(app) as client:
        response = client.get(
            "/api/b649/native-forecast/current",
            params={
                "target_draw_number": SYNTHETIC_TARGET,
                "target_draw_date": SYNTHETIC_TARGET_DATE,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["scope"] == {
            "lottery_type": "BIG_LOTTO",
            "target_draw_number": SYNTHETIC_TARGET,
            "target_draw_date": SYNTHETIC_TARGET_DATE,
            "forecast_stream_id": NATIVE_STREAM,
            "forecast_stream_version": NATIVE_STREAM_VERSION,
        }
        request_identity = body["request_identity"]
        assert request_identity["request_id"] == readback.forecast.request_id
        assert request_identity["request_sha256"] == readback.forecast.request_sha256
        assert request_identity["version"] == readback.version
        assert request_identity["run_id"] == readback.run_id
        assert request_identity["payload_sha256"] == readback.forecast.payload_sha256
        assert request_identity["committed_at"] == readback.committed_at
        assert (
            request_identity["generation_started_at"]
            == readback.forecast.original["generation_started_at"]
        )
        assert (
            request_identity["generation_finished_at"]
            == readback.forecast.original["generation_finished_at"]
        )
        assert body["payload"] == json.loads(readback.forecast.payload_bytes)

        validation_error = client.get(
            "/api/b649/native-forecast/current",
            params={"target_draw_date": SYNTHETIC_TARGET_DATE},
        )
        assert validation_error.status_code == 422
        validation_body = validation_error.json()
        assert validation_body["error_code"] == "REQUEST_VALIDATION_FAILED"
        assert validation_body["message"] == "Request validation failed."
        assert validation_body["fields"]

        invalid_scope = client.get(
            "/api/b649/native-forecast/current",
            params={
                "target_draw_number": SYNTHETIC_TARGET,
                "target_draw_date": "2099-99-99",
            },
        )
        assert invalid_scope.status_code == 422
        assert invalid_scope.json() == {
            "error_code": "B649_NATIVE_FORECAST_INVALID_SCOPE",
            "message": "The requested Native forecast scope is invalid.",
        }

        openapi = client.get("/openapi.json").json()
        schema_422 = openapi["paths"]["/api/b649/native-forecast/current"]["get"]["responses"][
            "422"
        ]["content"]["application/json"]["schema"]
        assert "anyOf" in schema_422
        response_models = {item["$ref"].rsplit("/", 1)[-1] for item in schema_422["anyOf"]}
        assert response_models == {
            "B649NativeForecastApiErrorResponse",
            "ApiValidationErrorResponse",
        }


def test_native_missing_binding_timeout_and_drawn_rejections_are_non_mutating(
    producer_bundle: tuple[Path, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing schedule, elapsed deadline, and present outcome never add a version."""
    root, bundle = producer_bundle
    service, repository, state = _new_service(root / "rejections", monkeypatch, bundle)
    empty_snapshot = _store_snapshot(repository)
    native = bundle["native_result"]
    provenance = bundle["provenance"]

    missing_binding = copy.deepcopy(provenance)
    del missing_binding["target"]["schedule_authority_sha256"]
    with pytest.raises(ValueError, match="schedule_authority_sha256"):
        service.commit_native_input(native, missing_binding)
    assert _store_snapshot(repository) == empty_snapshot

    scheduled_at = dt.datetime.fromisoformat(provenance["target"]["scheduled_at"])
    state["clock"] = scheduled_at.astimezone(dt.UTC)
    with pytest.raises(ForecastTimingError, match="OUTCOME_PRESENT_OR_DEADLINE_REACHED"):
        service.commit_native_input(native, provenance)
    assert _store_snapshot(repository) == empty_snapshot

    state["clock"] = dt.datetime.now(dt.UTC) + dt.timedelta(seconds=10)
    state["outcome"] = OutcomePresenceAtPrediction.PRESENT
    with pytest.raises(ForecastTimingError, match="OUTCOME_PRESENT_OR_DEADLINE_REACHED"):
        service.commit_native_input(native, provenance)
    assert _store_snapshot(repository) == empty_snapshot


def test_native_store_rejects_conflicts_and_incomplete_or_corrupt_inputs(
    producer_bundle: tuple[Path, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Conflicting identities, missing class provenance, and damaged tickets do not mutate."""
    root, bundle = producer_bundle
    forecast = _assert_synthetic_provenance(bundle)
    native = bundle["native_result"]
    provenance = bundle["provenance"]
    service, repository, _state = _new_service(root / "integrity", monkeypatch, bundle)

    empty_snapshot = _store_snapshot(repository)
    assert empty_snapshot == ([], [])

    corrupt_native = copy.deepcopy(native)
    numbers = corrupt_native["strategies"][0]["tickets"][0]["emitted_main_numbers"]
    numbers[1] = numbers[0]
    with pytest.raises(ValueError, match="invalid six-number native ticket"):
        service.commit_native_input(corrupt_native, provenance)
    assert _store_snapshot(repository) == empty_snapshot

    incomplete_provenance = copy.deepcopy(provenance)
    incomplete_rows = incomplete_provenance["effective_parameters"]["strategies"]
    for row in incomplete_rows:
        del row["adapter_class"]
    incomplete_provenance["effective_parameters"]["sha256"] = digest(
        {"strategies": incomplete_rows}
    )
    with pytest.raises(
        ResearchRepositoryError, match="research write violates the store contract"
    ) as rejection:
        service.commit_native_input(native, incomplete_provenance)
    assert str(rejection.value.__cause__) == "incomplete executed native parameters"
    assert _store_snapshot(repository) == empty_snapshot

    first = service.commit_native_input(native, provenance)
    baseline = _store_snapshot(repository)
    assert first.version == 1
    assert len(baseline[0]) == 1
    assert len(baseline[1]) == 1

    conflicting_native = copy.deepcopy(native)
    conflict_numbers = conflicting_native["strategies"][0]["tickets"][0]["emitted_main_numbers"]
    original_number = conflict_numbers[0]
    replacement_number = next(number for number in range(1, 50) if number not in conflict_numbers)
    conflict_numbers[0] = replacement_number
    assert conflict_numbers[0] != original_number
    conflicting_native["strategies"][0]["tickets"][0]["legal_main_numbers"][0] = replacement_number
    conflicting_forecast = adapt_native_input(conflicting_native, provenance)
    assert conflicting_forecast.request_id == forecast.request_id
    assert conflicting_forecast.payload_sha256 != forecast.payload_sha256
    conflicting_forecast = replace(
        conflicting_forecast,
        request_id=forecast.request_id,
        request_sha256=conflicting_forecast.payload_sha256,
    )
    assert conflicting_forecast.request_sha256 != forecast.request_sha256
    monkeypatch.setattr(
        live,
        "adapt_native_input",
        lambda _native, _provenance: conflicting_forecast,
    )
    with pytest.raises(ResearchConflictError, match="live request id was reused"):
        service.commit_native_input(native, provenance)
    assert _store_snapshot(repository) == baseline


def test_native_cli_rejects_tampered_canonical_history_without_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct CLI v6 mode rejects tampered canonical draw rows before emitting any artifact."""
    root = tmp_path / "tampered_cli_run"
    root.mkdir(parents=True)
    database, rank_path, schedule_path, ranking_path = _write_synthetic_producer_inputs(root)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE draws SET main_numbers_json = ? "
            "WHERE lottery_type = 'BIG_LOTTO' AND draw_number = ?",
            ("[1,2,3,4,5,49]", SYNTHETIC_CUTOFF),
        )
    output_dir = root / "SYNTHETIC_producer_output"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "b649_k235_predict.py",
            "--db-path",
            str(database),
            "--rank-history-path",
            str(rank_path),
            "--cutoff-draw",
            SYNTHETIC_CUTOFF,
            "--target-draw",
            SYNTHETIC_TARGET,
            "--output-dir",
            str(output_dir),
            "--emit-v6-provenance",
            "--schedule-binding-json",
            str(schedule_path),
            "--ranking-evidence-json",
            str(ranking_path),
            "--task-id",
            SYNTHETIC_TASK_ID,
            "--overwrite",
        ],
    )
    with pytest.raises(SystemExit) as exit_info:
        producer.main()
    assert exit_info.value.code == 1
    assert list(output_dir.iterdir()) == []
