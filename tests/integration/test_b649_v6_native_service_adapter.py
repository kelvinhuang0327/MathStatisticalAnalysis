from __future__ import annotations

import copy
import json
import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

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
    ProducerDependency,
    ProducerFingerprint,
)
from lottolab.domain.research_live_forecast import (
    NATIVE_STREAM,
    NATIVE_STREAM_VERSION,
    LiveForecastInput,
    canonical_json,
)
from lottolab.infrastructure import b649_live_forecast as live
from lottolab.infrastructure.b649_live_forecast import (
    B649LiveForecastService,
    run_native_input_forecast,
)
from lottolab.infrastructure.b649_v6_native_input_adapter_candidate import (
    adapt_native_input,
)
from lottolab.infrastructure.persistence import research_schema as schema
from lottolab.infrastructure.persistence.draw_schema import LocalDataPaths
from lottolab.infrastructure.persistence.research_repository import (
    LiveForecastCurrentResult,
    ResearchConflictError,
    SQLiteResearchRepository,
)

STRATEGIES = [
    {
        "strategy_id": "legacy_biglotto__backtest_big_lotto_orthogonal_5bet__c4dff46c5a5e",
        "strategy_version": "v0.1",
        "native_k": 5,
        "generator_identity": "fixture.orthogonal:Adapter",
        "tickets": [
            [1, 4, 9, 16, 25, 36],
            [2, 8, 14, 23, 35, 47],
            [3, 10, 17, 24, 33, 48],
            [5, 11, 19, 26, 38, 49],
            [6, 13, 20, 29, 41, 46],
        ],
    },
    {
        "strategy_id": "legacy_composite__quick_predict_5bet_ts3_markov_freqort",
        "strategy_version": "v0.1",
        "native_k": 5,
        "generator_identity": "fixture.composite:Adapter",
        "tickets": [
            [1, 4, 9, 16, 25, 36],
            [1, 7, 13, 22, 34, 45],
            [4, 10, 18, 27, 39, 48],
            [5, 12, 21, 30, 37, 49],
            [6, 15, 23, 32, 40, 46],
        ],
    },
    {
        "strategy_id": "legacy_biglotto__predict_5me_115000004__8a1c06ce1bdd",
        "strategy_version": "v0.1",
        "native_k": 5,
        "generator_identity": "fixture.five_me:Adapter",
        "tickets": [
            [1, 4, 9, 16, 25, 36],
            [2, 11, 17, 24, 33, 45],
            [3, 12, 20, 28, 37, 49],
            [5, 13, 22, 31, 39, 47],
            [6, 14, 23, 30, 41, 48],
        ],
    },
]


def _build_synthetic_fixture() -> tuple[dict[str, object], dict[str, object]]:
    strategy_ids = [str(row["strategy_id"]) for row in STRATEGIES]
    adapter_paths = {
        strategy_id: f"fixture://adapters/{index}"
        for index, strategy_id in enumerate(strategy_ids, start=1)
    }
    adapter_shas = {strategy_id: digest(adapter_paths[strategy_id]) for strategy_id in strategy_ids}

    catalog = [
        {
            "strategy_id": strategy["strategy_id"],
            "version": strategy["strategy_version"],
            "native_k": strategy["native_k"],
            "adapter_source_path": adapter_paths[str(strategy["strategy_id"])],
            "adapter_source_sha256": adapter_shas[str(strategy["strategy_id"])],
        }
        for strategy in STRATEGIES
    ]
    catalog.sort(key=lambda row: str(row["strategy_id"]))

    configs: list[dict[str, object]] = []
    for index, strategy in enumerate(STRATEGIES):
        strategy_id = str(strategy["strategy_id"])
        stochastic = index == 2
        rng = {
            "behavior": "SEEDED_STOCHASTIC" if stochastic else "DETERMINISTIC",
            "seed": 2187 if stochastic else None,
            "rng_source": "fixture.random.Random" if stochastic else "fixture.deterministic",
            "rng_state_rule": "fixture explicit seed" if stochastic else "no RNG state",
            "configuration": "fixture-rng-v1",
            "prestate_dependency": (
                "causal_history_and_explicit_seed" if stochastic else "causal_history_only"
            ),
        }
        configs.append(
            {
                "strategy_id": strategy_id,
                "strategy_version": strategy["strategy_version"],
                "native_k": strategy["native_k"],
                "parameters": {"seed": 2187} if stochastic else {"fixture_mode": "deterministic"},
                "rng_semantics": rng,
            }
        )
        strategy["rng_semantics"] = rng
        strategy["adapter_source_path"] = adapter_paths[strategy_id]
        strategy["adapter_source_sha256"] = adapter_shas[strategy_id]
    configs.sort(key=lambda row: str(row["strategy_id"]))

    history = [
        {
            "lottery_type": "BIG_LOTTO",
            "draw_number": "990000001",
            "draw_date": "2030-01-02",
            "main_numbers": [1, 2, 3, 4, 5, 6],
            "special_number": 7,
        },
        {
            "lottery_type": "BIG_LOTTO",
            "draw_number": "990000002",
            "draw_date": "2030-01-03",
            "main_numbers": [8, 9, 10, 11, 12, 13],
            "special_number": 14,
        },
    ]
    history_sha = digest(history)
    schedule_authority = "6" * 64
    target = {
        "lottery_type": "BIG_LOTTO",
        "target_draw_number": "990000003",
        "target_draw_date": "2030-01-05",
        "scheduled_at": "2030-01-05T20:30:00+08:00",
        "timezone": "Asia/Taipei",
        "data_cutoff": "990000002",
        "forecast_horizon": 1,
        "history_draw_count": 2,
        "causal_history_sha256": history_sha,
        "schedule_authority_sha256": schedule_authority,
    }
    producer = ProducerFingerprint.create(
        producer_id="synthetic-native-input-fixture",
        producer_version="v1",
        dependencies=(
            ProducerDependency(
                "fixture://native-runner",
                "7" * 64,
                "test-only native runner identity",
            ),
        ),
    )
    runtime_material: dict[str, object] = {
        "python": {
            "implementation": "CPython",
            "version": "3.13.8",
            "executable": "/fixture/python",
            "executable_sha256": "8" * 64,
        },
        "os": "fixture-os",
        "architecture": "fixture-arch",
        "dependencies": [
            {
                "name": "fixture-library",
                "locator": "fixture://runtime/library",
                "versions": {"fixture-library": "1"},
                "content_sha256": "9" * 64,
            }
        ],
    }
    runtime = {**runtime_material, "sha256": digest(runtime_material)}
    source_execution = {
        "repository": "fixture://source-repository",
        "commit": "1" * 40,
        "tree": "2" * 40,
        "loaded_code_sha256": "3" * 64,
        "pre_draw_proof_status": "LOCAL_ONLY",
    }
    history_snapshot = {
        "reference": f"research-live-history:sha256:{history_sha}",
        "draws": history,
        "sha256": history_sha,
    }
    effective_rows = [
        {
            "strategy_id": str(config["strategy_id"]),
            "strategy_version": str(config["strategy_version"]),
            "native_k": int(config["native_k"]),
            "parameters_json": canonical_json(config["parameters"]),
            "generation_config_sha256": digest(config),
            "status": "EXECUTED",
            "constructor_defaults": {},
            "instance_state": {},
            "adapter_class": "fixture.adapter:Class",
        }
        for config in configs
    ]
    effective_material = {"strategies": effective_rows}
    effective = {**effective_material, "sha256": digest(effective_material)}
    rng_stages = [
        {
            "strategy_id": str(config["strategy_id"]),
            "stage": "NATIVE_GENERATION",
            "status": "EXECUTED",
            "rng_semantics": config["rng_semantics"],
            "seed_status": (
                "EFFECTIVE_SEED_CAPTURED"
                if config["rng_semantics"]["behavior"] == "SEEDED_STOCHASTIC"
                else "NOT_APPLICABLE"
            ),
            "invocation_identity": "synthetic-run-1",
            "replicate": 1,
        }
        for config in configs
    ]
    observations = [
        {
            "strategy_id": str(config["strategy_id"]),
            "strategy_version": str(config["strategy_version"]),
            "native_k": int(config["native_k"]),
            "draw_number": draw["draw_number"],
            "draw_date": draw["draw_date"],
            "causal_history_sha256": digest(history[:index]),
            "generation_config_sha256": digest(config),
            "status": "EVALUATED",
            "producer_fingerprint": producer.digest,
            "tickets": next(
                row["tickets"] for row in STRATEGIES if row["strategy_id"] == config["strategy_id"]
            ),
        }
        for config in configs
        for index, draw in enumerate(history)
    ]
    observations.sort(key=lambda row: (str(row["strategy_id"]), str(row["draw_number"])))
    evidence_sha = digest(observations)
    ranking = {
        "objective": OBJECTIVE,
        "ranking_policy_version": RANKING_POLICY_VERSION,
        "evaluation_window": "FULL",
        "observations": observations,
        "evidence_payload_sha256": evidence_sha,
    }
    rng_semantics = {
        "stages": rng_stages,
        "reproducibility_boundary": "FIXED_SYNTHETIC_INPUTS_CODE_RUNTIME_CONFIG",
    }
    native_strategies = []
    for rank, strategy in enumerate(STRATEGIES, start=1):
        native_strategies.append(
            {
                "rank": rank,
                "strategy_id": strategy["strategy_id"],
                "strategy_version": strategy["strategy_version"],
                "native_k": strategy["native_k"],
                "generator_identity": strategy["generator_identity"],
                "adapter_source_path": strategy["adapter_source_path"],
                "adapter_source_sha256": strategy["adapter_source_sha256"],
                "rng_semantics": strategy["rng_semantics"],
                "tickets": [
                    {
                        "position": position,
                        "emitted_main_numbers": numbers,
                        "legal_main_numbers": numbers,
                        "predicted_special_number": None,
                    }
                    for position, numbers in enumerate(strategy["tickets"], start=1)
                ],
            }
        )
    native: dict[str, object] = {
        "schema_version": "NUMBER2_9_B649_NATIVE_PREDICTION_V1",
        "task_id": "SYNTHETIC_V6_NATIVE_SERVICE_FIXTURE",
        "prediction_target": target["target_draw_number"],
        "generated_at_local": "2030-01-05T10:00:01+08:00",
        "pre_draw_proof_status": "LOCAL_ONLY",
        "target_106_source_rows_selected": False,
        "target_outcome": "UNOBSERVED_NOT_READ",
        "strategy_count_expected": 3,
        "strategy_count_generated": 3,
        "ticket_count_expected": 15,
        "ticket_count_generated": 15,
        "strategies": native_strategies,
    }
    context: dict[str, object] = {
        "target": target,
        "source_locator": "canonical-next-undrawn",
        "source_execution": source_execution,
        "runtime_manifest": runtime,
        "history_snapshot": history_snapshot,
        "producer": producer.canonical_dict(),
        "catalog": catalog,
        "generation_configs": configs,
        "effective_parameters": effective,
        "rng_semantics": rng_semantics,
        "ranking_evidence": ranking,
        "seeds": {strategy_ids[2]: 2187},
        "generation_started_at": "2030-01-05T10:00:00.000000Z",
        "generation_finished_at": "2030-01-05T10:00:01.000000Z",
    }
    return native, context


def _setup_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    clock_time: datetime,
    target_draw: str = "990000003",
    target_date: date = date(2030, 1, 5),
    scheduled_at: datetime = datetime(2030, 1, 5, 12, 30, tzinfo=UTC),
    schedule_hash: str = "6" * 64,
    outcome_presence: OutcomePresenceAtPrediction = OutcomePresenceAtPrediction.ABSENT,
) -> tuple[B649LiveForecastService, SQLiteResearchRepository]:
    research_dir = (tmp_path / "research").resolve()
    paths = schema.ResearchDataPaths(
        data_directory=research_dir,
        database=research_dir / schema.RESEARCH_DATABASE_FILENAME,
    )
    repo = SQLiteResearchRepository(paths)

    record = SimpleNamespace(
        announcement=SimpleNamespace(
            target=ObservationTarget(LotteryType.BIG_LOTTO, target_draw, target_date),
            scheduled_at=scheduled_at,
        ),
        normalized_announcement_hash=schedule_hash,
        immutable_schedule_sha256=None,
    )

    class StubOutcomeProbe:
        def __init__(self, _paths: object) -> None:
            pass

        def probe(
            self,
            _target: ObservationTarget,
            as_of: datetime,
        ) -> SimpleNamespace:
            return SimpleNamespace(presence=outcome_presence)

    monkeypatch.setattr(live.B649LiveForecastService, "_schedule", lambda _self: record)
    monkeypatch.setattr(live, "SQLiteOfficialOutcomePresenceProbe", StubOutcomeProbe)

    service = B649LiveForecastService(
        repository=repo,
        draw_paths=cast(LocalDataPaths, object()),
        source_repository=Path(__file__).resolve().parents[2],
        clock=lambda: clock_time,
    )

    return service, repo


def test_service_adapter_source_loading_and_identity() -> None:
    """AC01: Service and adopted Adapter can be loaded together in the same repository tree."""
    assert callable(adapt_native_input)
    assert hasattr(B649LiveForecastService, "commit_native_input")
    assert callable(run_native_input_forecast)
    assert hasattr(SQLiteResearchRepository, "commit_live_forecast")
    assert hasattr(SQLiteResearchRepository, "read_current_native")
    assert callable(LiveForecastInput.validate)


def test_valid_commit_fixture_persists_native_version_and_advances_pointer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC02, AC03, AC04, AC07, AC10: Complete synthetic Native input commits through service."""
    clock_time = datetime(2030, 1, 5, 10, 5, 0, tzinfo=UTC)
    service, repo = _setup_service(tmp_path, monkeypatch, clock_time=clock_time)

    native, context = _build_synthetic_fixture()
    result = service.commit_native_input(native, context)

    assert result.version == 1
    assert result.pointer_advanced is True
    assert result.idempotent is False
    assert result.run_id.startswith("live-")

    # Inspect the persisted SQLite database rows directly.
    with sqlite3.connect(f"file:{repo._paths.database}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        versions = conn.execute("SELECT * FROM research_live_forecast_versions").fetchall()
        assert len(versions) == 1
        row = versions[0]
        assert row["version"] == 1
        assert row["pointer_advanced"] == 1
        assert row["provenance_class"] == "NATIVE_GENERATED"
        assert row["forecast_stream_id"] == NATIVE_STREAM
        assert row["forecast_stream_version"] == NATIVE_STREAM_VERSION
        assert row["target_draw_number"] == "990000003"
        assert row["target_draw_date"] == "2030-01-05"
        assert row["generation_started_at"] == "2030-01-05T10:00:00.000000Z"
        assert row["generation_finished_at"] == "2030-01-05T10:00:01.000000Z"
        assert row["committed_at"] == "2030-01-05T10:05:00.000000Z"

        # Verify no issued_at field exists in table schema.
        col_names = [
            col[1]
            for col in conn.execute("PRAGMA table_info(research_live_forecast_versions)").fetchall()
        ]
        assert "issued_at" not in col_names

        # Pointer verification.
        pointers = conn.execute("SELECT * FROM research_live_forecast_current_pointer").fetchall()
        assert len(pointers) == 1
        ptr = pointers[0]
        assert ptr["version"] == 1
        assert ptr["target_draw_number"] == "990000003"
        assert ptr["run_id"] == result.run_id

        # Payload and provenance verification (AC04).
        payload = json.loads(row["payload_bytes"])
        assert payload["evaluation_window"] == "FULL"
        assert payload["source_proof_status"] == "LOCAL_ONLY"
        assert len(payload["native_strategies"]) == 3

        # 3 strategies * 5 tickets = 15 tickets total in order.
        total_tickets = sum(len(s["native_positions"]) for s in payload["native_strategies"])
        assert total_tickets == 15

        # Check K20 structural availability (AC04).
        k20_bucket = next(b for b in payload["buckets"] if b["bucket"] == "K20")
        assert k20_bucket["status"] == "UNAVAILABLE_NO_CANONICAL_NATIVE_K20_STRATEGY"
        assert k20_bucket["selected"] is None
        assert k20_bucket["tickets"] == []


def test_native_readback_retrieves_exact_scope_and_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC09: read_current_native reads the committed version; consensus reader returns None."""
    clock_time = datetime(2030, 1, 5, 10, 5, 0, tzinfo=UTC)
    service, repo = _setup_service(tmp_path, monkeypatch, clock_time=clock_time)

    native, context = _build_synthetic_fixture()
    commit_result = service.commit_native_input(native, context)

    scope = (
        "BIG_LOTTO",
        "990000003",
        "2030-01-05",
        NATIVE_STREAM,
        NATIVE_STREAM_VERSION,
    )
    current: LiveForecastCurrentResult | None = repo.read_current_native(scope)
    assert current is not None
    assert current.version == commit_result.version
    assert current.run_id == commit_result.run_id
    assert current.forecast.payload_sha256 == commit_result.payload_sha256
    assert current.forecast.provenance_class == "NATIVE_GENERATED"
    assert current.forecast.forecast_stream_id == NATIVE_STREAM
    assert current.forecast.forecast_stream_version == NATIVE_STREAM_VERSION
    assert current.committed_at == "2030-01-05T10:05:00.000000Z"

    # Consensus reader must NOT read native target records.
    consensus_scope = (
        "BIG_LOTTO",
        "990000003",
        "2030-01-05",
        "B649_CANONICAL_CONSENSUS",
        "B649_CANONICAL_CONSENSUS_V1",
    )
    assert repo.read_current_consensus(consensus_scope) is None

    # Different undrawn target returns None.
    other_scope = (
        "BIG_LOTTO",
        "990000004",
        "2030-01-08",
        NATIVE_STREAM,
        NATIVE_STREAM_VERSION,
    )
    assert repo.read_current_native(other_scope) is None


def test_idempotent_retry_returns_existing_without_new_row_or_pointer_move(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC08: Identical retry returns existing result without inserting new version."""
    clock_time = datetime(2030, 1, 5, 10, 5, 0, tzinfo=UTC)
    service, repo = _setup_service(tmp_path, monkeypatch, clock_time=clock_time)

    native, context = _build_synthetic_fixture()
    first = service.commit_native_input(native, context)
    assert first.idempotent is False

    # Second call with identical input.
    second = service.commit_native_input(copy.deepcopy(native), copy.deepcopy(context))
    assert second.idempotent is True
    assert second.version == first.version
    assert second.run_id == first.run_id
    assert second.payload_sha256 == first.payload_sha256

    # Verify version count in DB is still 1.
    with sqlite3.connect(f"file:{repo._paths.database}?mode=ro", uri=True) as conn:
        count = conn.execute("SELECT count(*) FROM research_live_forecast_versions").fetchone()[0]
        assert count == 1
        ptr_version = conn.execute(
            "SELECT version FROM research_live_forecast_current_pointer"
        ).fetchone()[0]
        assert ptr_version == 1


def test_request_conflict_same_request_id_different_payload_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC08: Same request_id with differing request_sha256 raises ResearchConflictError."""
    clock_time = datetime(2030, 1, 5, 10, 5, 0, tzinfo=UTC)
    service, repo = _setup_service(tmp_path, monkeypatch, clock_time=clock_time)

    native, context = _build_synthetic_fixture()
    service.commit_native_input(native, context)

    # Alter ranking observations (and their evidence SHA): request_sha256 changes,
    # while bundle identity and therefore request_id stay the same.
    conflicting_context = copy.deepcopy(context)
    ranking = cast(dict[str, object], conflicting_context["ranking_evidence"])
    observations = cast(list[dict[str, object]], ranking["observations"])
    observations[0]["status"] = "EVALUATED_ALTERED"
    ranking["evidence_payload_sha256"] = digest(observations)

    with pytest.raises(
        ResearchConflictError, match="live request id was reused for different inputs"
    ):
        service.commit_native_input(native, conflicting_context)

    # DB remains unchanged: 1 version, pointer at 1.
    with sqlite3.connect(f"file:{repo._paths.database}?mode=ro", uri=True) as conn:
        count = conn.execute("SELECT count(*) FROM research_live_forecast_versions").fetchone()[0]
        assert count == 1
        ptr_version = conn.execute(
            "SELECT version FROM research_live_forecast_current_pointer"
        ).fetchone()[0]
        assert ptr_version == 1


def test_schedule_deadline_exceeded_at_call_time_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC05, AC07: When call time reaches deadline, service rejects and pointer is unchanged."""
    deadline = datetime(2030, 1, 5, 12, 30, tzinfo=UTC)
    late_clock = datetime(2030, 1, 5, 12, 30, 0, tzinfo=UTC)  # Exactly at deadline
    service, repo = _setup_service(
        tmp_path, monkeypatch, clock_time=late_clock, scheduled_at=deadline
    )

    native, context = _build_synthetic_fixture()
    with pytest.raises(ForecastTimingError, match="OUTCOME_PRESENT_OR_DEADLINE_REACHED"):
        service.commit_native_input(native, context)

    with sqlite3.connect(f"file:{repo._paths.database}?mode=ro", uri=True) as conn:
        count = conn.execute("SELECT count(*) FROM research_live_forecast_versions").fetchone()[0]
        assert count == 0
        pointers = conn.execute(
            "SELECT count(*) FROM research_live_forecast_current_pointer"
        ).fetchone()[0]
        assert pointers == 0


def test_generation_finished_after_deadline_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC05, AC07: Inputs generated after schedule deadline are rejected even if called early."""
    deadline = datetime(2030, 1, 5, 12, 30, tzinfo=UTC)
    clock_time = datetime(2030, 1, 5, 10, 5, 0, tzinfo=UTC)
    service, repo = _setup_service(
        tmp_path, monkeypatch, clock_time=clock_time, scheduled_at=deadline
    )

    native, context = _build_synthetic_fixture()
    # Generation times after deadline:
    context["generation_started_at"] = "2030-01-05T12:30:01.000000Z"
    context["generation_finished_at"] = "2030-01-05T12:30:02.000000Z"

    with pytest.raises(ForecastTimingError, match="OUTCOME_PRESENT_OR_DEADLINE_REACHED"):
        service.commit_native_input(native, context)

    with sqlite3.connect(f"file:{repo._paths.database}?mode=ro", uri=True) as conn:
        count = conn.execute("SELECT count(*) FROM research_live_forecast_versions").fetchone()[0]
        assert count == 0
        pointers = conn.execute(
            "SELECT count(*) FROM research_live_forecast_current_pointer"
        ).fetchone()[0]
        assert pointers == 0


def test_official_outcome_present_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC06, AC07: Outcome presence probe returning PRESENT is rejected and pointer unchanged."""
    clock_time = datetime(2030, 1, 5, 10, 5, 0, tzinfo=UTC)
    service, repo = _setup_service(
        tmp_path,
        monkeypatch,
        clock_time=clock_time,
        outcome_presence=OutcomePresenceAtPrediction.PRESENT,
    )

    native, context = _build_synthetic_fixture()
    with pytest.raises(ForecastTimingError, match="OUTCOME_PRESENT_OR_DEADLINE_REACHED"):
        service.commit_native_input(native, context)

    with sqlite3.connect(f"file:{repo._paths.database}?mode=ro", uri=True) as conn:
        count = conn.execute("SELECT count(*) FROM research_live_forecast_versions").fetchone()[0]
        assert count == 0
        pointers = conn.execute(
            "SELECT count(*) FROM research_live_forecast_current_pointer"
        ).fetchone()[0]
        assert pointers == 0


def test_target_draw_number_mismatch_with_schedule_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC05, AC07: Input targeting a different draw number than schedule is rejected."""
    clock_time = datetime(2030, 1, 5, 10, 5, 0, tzinfo=UTC)
    # Schedule announcement says 990000004, but input targets 990000003.
    service, repo = _setup_service(
        tmp_path, monkeypatch, clock_time=clock_time, target_draw="990000004"
    )

    native, context = _build_synthetic_fixture()
    with pytest.raises(ForecastTimingError, match="CANONICAL_TARGET_OR_SCHEDULE_CHANGED"):
        service.commit_native_input(native, context)

    with sqlite3.connect(f"file:{repo._paths.database}?mode=ro", uri=True) as conn:
        count = conn.execute("SELECT count(*) FROM research_live_forecast_versions").fetchone()[0]
        assert count == 0


def test_schedule_authority_sha_mismatch_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC05, AC07: Schedule authority SHA mismatch between announcement and input is rejected."""
    clock_time = datetime(2030, 1, 5, 10, 5, 0, tzinfo=UTC)
    service, repo = _setup_service(
        tmp_path, monkeypatch, clock_time=clock_time, schedule_hash="f" * 64
    )

    native, context = _build_synthetic_fixture()
    with pytest.raises(ForecastTimingError, match="CANONICAL_TARGET_OR_SCHEDULE_CHANGED"):
        service.commit_native_input(native, context)

    with sqlite3.connect(f"file:{repo._paths.database}?mode=ro", uri=True) as conn:
        count = conn.execute("SELECT count(*) FROM research_live_forecast_versions").fetchone()[0]
        assert count == 0


def test_invalid_input_schema_rejected_by_adapter_before_writer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC02, AC07: Unsupported schema_version is rejected before write transaction."""
    clock_time = datetime(2030, 1, 5, 10, 5, 0, tzinfo=UTC)
    service, repo = _setup_service(tmp_path, monkeypatch, clock_time=clock_time)

    native, context = _build_synthetic_fixture()
    native["schema_version"] = "UNSUPPORTED_SCHEMA"

    with pytest.raises(ValueError, match="unsupported native input schema"):
        service.commit_native_input(native, context)

    with sqlite3.connect(f"file:{repo._paths.database}?mode=ro", uri=True) as conn:
        count = conn.execute("SELECT count(*) FROM research_live_forecast_versions").fetchone()[0]
        assert count == 0


def test_commit_clock_predating_generation_is_rejected_by_writer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC07, AC10: Service clock earlier than generation_finished_at is rejected by repository."""
    # generation_finished_at is 10:00:01Z, but clock is 09:59:00Z.
    early_clock = datetime(2030, 1, 5, 9, 59, 0, tzinfo=UTC)
    service, repo = _setup_service(tmp_path, monkeypatch, clock_time=early_clock)

    native, context = _build_synthetic_fixture()
    with pytest.raises(ResearchConflictError, match="commit clock predates native execution"):
        service.commit_native_input(native, context)

    with sqlite3.connect(f"file:{repo._paths.database}?mode=ro", uri=True) as conn:
        count = conn.execute("SELECT count(*) FROM research_live_forecast_versions").fetchone()[0]
        assert count == 0


def test_module_level_run_native_input_forecast_and_service_aliases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC02: Module-level run_native_input_forecast produces identical valid commit."""
    clock_time = datetime(2030, 1, 5, 10, 5, 0, tzinfo=UTC)
    service, _repo = _setup_service(tmp_path, monkeypatch, clock_time=clock_time)

    native, context = _build_synthetic_fixture()
    result = run_native_input_forecast(service, native, context)
    assert result.version == 1
    assert result.pointer_advanced is True

    # Test alias methods point to the exact same callable.
    assert service.adapt_and_commit_native_input == service.commit_native_input
    assert service.repredict_native_input == service.commit_native_input


def test_v5_to_v6_migration_preserves_committed_native_identity_and_pointer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock_time = datetime(2030, 1, 5, 10, 5, 0, tzinfo=UTC)
    service, repo = _setup_service(tmp_path, monkeypatch, clock_time=clock_time)
    native, context = _build_synthetic_fixture()
    committed = service.commit_native_input(native, context)
    database = repo._paths.database
    database_inode = database.stat().st_ino

    def read_committed_state() -> tuple[tuple[tuple[object, ...], ...], ...]:
        with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
            version_rows = tuple(
                tuple(row)
                for row in connection.execute(
                    "SELECT * FROM research_live_forecast_versions ORDER BY version"
                )
            )
            pointer_rows = tuple(
                tuple(row)
                for row in connection.execute(
                    "SELECT * FROM research_live_forecast_current_pointer "
                    "ORDER BY lottery_type, target_draw_number"
                )
            )
            run_rows = tuple(
                tuple(row)
                for row in connection.execute(
                    "SELECT * FROM research_runs WHERE id = ?",
                    (committed.run_id,),
                )
            )
        return version_rows, pointer_rows, run_rows

    existing_state = read_committed_state()
    assert len(existing_state[0]) == 1
    assert len(existing_state[1]) == 1
    assert len(existing_state[2]) == 1
    assert existing_state[1][0][-2:] == (committed.version, committed.run_id)
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        payload_bytes = connection.execute(
            "SELECT payload_bytes FROM research_live_forecast_versions WHERE run_id = ?",
            (committed.run_id,),
        ).fetchone()[0]
    payload = json.loads(payload_bytes)
    assert len(payload["native_strategies"]) == 3
    assert sum(len(row["native_positions"]) for row in payload["native_strategies"]) == 15

    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("BEGIN IMMEDIATE")
        for statement in schema.V6_MIGRATION_STATEMENTS[1:]:
            trigger_name = schema._object_name(statement)
            connection.execute(f'DROP TRIGGER "{trigger_name}"')
        connection.execute("DROP TABLE research_native_ticket_evidence")

        migration_triggers = schema._append_only_trigger_statements("research_schema_migrations")
        for statement in migration_triggers:
            trigger_name = schema._object_name(statement)
            connection.execute(f'DROP TRIGGER "{trigger_name}"')
        connection.execute("DELETE FROM research_schema_migrations WHERE version = 6")
        for statement in migration_triggers:
            connection.execute(statement)

    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        v5_migration = connection.execute(
            """
            SELECT version, name, checksum
            FROM research_schema_migrations
            ORDER BY version DESC LIMIT 1
            """
        ).fetchone()
        v6_table = connection.execute(
            """
            SELECT 1 FROM sqlite_schema
            WHERE type='table' AND name='research_native_ticket_evidence'
            """
        ).fetchone()
    assert v5_migration == (
        5,
        schema.V5_MIGRATION_NAME,
        schema.V5_MIGRATION_CHECKSUM,
    )
    assert v6_table is None
    assert database.stat().st_ino == database_inode

    schema.initialize_schema(repo._paths)

    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        v6_migration = connection.execute(
            """
            SELECT version, name, checksum
            FROM research_schema_migrations
            ORDER BY version DESC LIMIT 1
            """
        ).fetchone()
        evidence_count = connection.execute(
            "SELECT COUNT(*) FROM research_native_ticket_evidence"
        ).fetchone()[0]
    assert v6_migration == (
        schema.CURRENT_SCHEMA_VERSION,
        schema.V6_MIGRATION_NAME,
        schema.V6_MIGRATION_CHECKSUM,
    )
    assert read_committed_state() == existing_state
    assert evidence_count == 0
    assert database.stat().st_ino == database_inode
    assert schema.verify_schema_read_only(repo._paths) is True
