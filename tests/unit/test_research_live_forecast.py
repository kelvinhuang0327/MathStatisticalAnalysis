"""Canonical native adapter execution with isolated schedule/runtime authorities."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from tests.integration.test_research_live_forecast import legacy_input as legacy_input
from tests.unit.test_b649_next_undrawn_forecast import (
    FixtureSeededPortfolio,
    descriptor,
    make_request,
)

from lottolab.application import b649_next_undrawn_forecast as app
from lottolab.application.future_draw_identity import (
    ScheduledDrawIdentityRecord,
    normalized_announcement_sha256,
)
from lottolab.domain import research_live_forecast as forecast_domain
from lottolab.domain.b649_next_undrawn_forecast import (
    ObservationStatus,
    ReplayObservation,
    history_ref,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.exact_native_replay import Draw
from lottolab.domain.ingestion import IngestionOperationType, IngestionRunStatus
from lottolab.domain.prospective_observer import (
    ObservationTarget,
    ProducerDependency,
    ProducerFingerprint,
)
from lottolab.domain.research_live_forecast import (
    LEGACY_HISTORY_SHA256,
    LEGACY_MATERIALIZATION_TASK,
    LEGACY_SEAL_SHA256,
    LEGACY_SOURCE_TASK,
    LEGACY_STREAM,
    NATIVE_ARRAY_REQUIRED_PATHS,
    NATIVE_REQUIRED_PATHS,
    ORIGINAL_FIELDS,
    LiveForecastInput,
    LiveForecastResult,
    canonical_json,
    digest,
    sha256,
)
from lottolab.infrastructure import b649_live_forecast as live
from lottolab.infrastructure.imports.csv_draws import parse_draw_csv
from lottolab.infrastructure.persistence.draw_schema import (
    CURRENT_SCHEMA_VERSION,
    DATA_DIRECTORY_ENV,
    LocalDataPaths,
    initialize_schema,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.draw_schema import (
    open_database as open_draw_database,
)
from lottolab.infrastructure.persistence.future_draw_identity_repository import (
    SQLiteManualFutureDrawIdentitySupplementRepository,
)
from lottolab.infrastructure.persistence.repositories import SQLiteDrawDataRepository
from lottolab.infrastructure.persistence.research_repository import SQLiteResearchRepository
from lottolab.infrastructure.persistence.research_schema import ResearchDataPaths
from lottolab.infrastructure.pre_outcome_target_operational import (
    OPERATIONAL_ANNOUNCEMENT_SCHEMA_VERSION,
    parse_owner_certified_future_draw_identity_input,
    select_owner_certified_future_draw_identity,
)
from lottolab.infrastructure.taiwan_lottery_draw_provider import PROVIDER_ID, PROVIDER_VERSION
from lottolab.strategies.catalog import StrategyCatalog, production_catalog

type NativeFixture = tuple[
    live.B649LiveForecastService, Callable[[str], LiveForecastResult], dict[str, LiveForecastInput]
]


@pytest.fixture
def native(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> NativeFixture:
    # Actual canonical adapter/core; deliberately synthetic authority and runtime
    # manifests. These tests make no claim about production execution identity.
    descriptor = production_catalog().get(
        "legacy_biglotto__frontend_frequency_strategy__2e3e8febb5f1"
    )
    catalog = StrategyCatalog((descriptor,))
    monkeypatch.setattr(live, "production_catalog", lambda: catalog)
    monkeypatch.setattr(app, "production_catalog", lambda: catalog)
    history = tuple(
        Draw(str(115000081 + i), date(2026, 9, 1) + timedelta(days=i), (1, 2, 3, 4, 5, 6), 7)
        for i in range(6)
    )
    target = ObservationTarget(LotteryType.BIG_LOTTO, "115000087", date(2026, 9, 11))
    producer = ProducerFingerprint.create(
        producer_id="fixture-producer",
        producer_version="fixture-v1",
        dependencies=(
            ProducerDependency("fixture://frequency", digest("test-code"), "test binding"),
        ),
    )
    observations = tuple(
        ReplayObservation(
            descriptor.strategy_id,
            descriptor.version,
            1,
            draw.draw_number,
            draw.draw_date,
            history_ref(history[:i]).history_sha256,
            app.native_generation_config(descriptor, history[:i]).sha256,
            ObservationStatus.EVALUATED,
            ((1, 2, 3, 4, 5, 6),),
            producer_fingerprint=producer.digest,
        )
        for i, draw in enumerate(history)
        if i >= descriptor.min_history
    )

    def fake_fingerprint(*_args: object) -> ProducerFingerprint:
        return producer

    def fake_source(_root: Path) -> dict[str, object]:
        return {
            "repository": "fixture://source",
            "commit": "a" * 40,
            "tree": "b" * 40,
            "loaded_code_sha256": digest("fixture-code"),
        }

    monkeypatch.setattr(live, "source_producer_fingerprint", fake_fingerprint)
    monkeypatch.setattr(live, "capture_source_execution", fake_source)
    runtime = {
        "python": {
            "implementation": "CPython",
            "version": "fixture",
            "executable": "fixture",
            "executable_sha256": digest("fixture-runtime"),
        },
        "os": "fixture",
        "architecture": "fixture",
        "dependencies": [
            {
                "name": "fixture-runtime",
                "locator": "fixture://runtime",
                "versions": {"fixture": "1"},
                "content_sha256": digest("runtime"),
            }
        ],
    }
    monkeypatch.setattr(
        live, "capture_runtime_manifest", lambda: {**runtime, "sha256": digest(runtime)}
    )
    record = SimpleNamespace(
        announcement=SimpleNamespace(
            target=target, scheduled_at=datetime(2026, 9, 11, 12, 30, tzinfo=UTC)
        ),
        normalized_announcement_hash=digest("fixture announcement"),
        immutable_schedule_sha256=None,
    )

    def fake_schedule(_self: object) -> SimpleNamespace:
        return record

    def fake_history(_self: object, _target: ObservationTarget) -> tuple[Draw, ...]:
        return history

    def fake_gate(_self: object, _record: object) -> bool:
        return True

    monkeypatch.setattr(live.B649LiveForecastService, "_schedule", fake_schedule)
    monkeypatch.setattr(live.B649LiveForecastService, "_history", fake_history)
    monkeypatch.setattr(live.B649LiveForecastService, "_gate", fake_gate)
    directory = tmp_path / "research"
    repo = SQLiteResearchRepository(
        ResearchDataPaths(directory, directory / "lottolab_research.db")
    )
    captured: dict[str, LiveForecastInput] = {}
    original_commit = repo.commit_live_forecast

    def capture_commit(
        forecast: LiveForecastInput,
        *,
        expected_current_version: int,
        current_eligible: Callable[[], bool],
        clock: Callable[[], datetime],
    ) -> LiveForecastResult:
        captured[forecast.request_id] = forecast
        return original_commit(
            forecast,
            expected_current_version=expected_current_version,
            current_eligible=current_eligible,
            clock=clock,
        )

    monkeypatch.setattr(repo, "commit_live_forecast", capture_commit)
    service = live.B649LiveForecastService(
        repo,
        cast(LocalDataPaths, object()),
        Path(__file__).resolve().parents[2],
        lambda: datetime(2026, 9, 9, tzinfo=UTC),
    )
    return (
        service,
        lambda request_id: service.repredict(
            request_id=request_id, observations=observations, seeds={}
        ),
        captured,
    )


def test_different_requests_append_same_content_and_retry_does_not_reset_current(
    native: NativeFixture,
) -> None:
    service, generate, captured = native
    first, second = generate("first"), generate("second")
    assert first.run_id != second.run_id and first.version < second.version
    assert first.payload_sha256 == second.payload_sha256
    assert first.provenance_envelope_sha256 != second.provenance_envelope_sha256
    assert generate("first").run_id == first.run_id
    assert service.repository.live_current_version(captured["first"].scope) == second.version
    params = json.loads(str(captured["first"].original["effective_parameters_json"]))["strategies"]
    assert params[0]["status"] == "EXECUTED" and isinstance(params[0]["instance_state"], dict)
    buckets = json.loads(captured["first"].payload_bytes)["buckets"]
    assert buckets[0]["status"] == "AVAILABLE" and buckets[0]["tickets"] == [[1, 2, 3, 4, 5, 6]]
    assert buckets[-1]["status"] == "UNAVAILABLE_NO_CANONICAL_NATIVE_K20_STRATEGY"


def test_stale_writer_retains_history(
    native: NativeFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, generate, captured = native
    current = generate("newer")

    def old_version(_scope: object) -> int:
        return 0

    # The second real request sees the pre-winner pointer version.
    with monkeypatch.context() as stale_reader:
        stale_reader.setattr(service.repository, "live_current_version", old_version)
        result = generate("older")
    stale = captured["older"]
    assert result.version > current.version and not result.pointer_advanced
    assert service.repository.live_current_version(stale.scope) == current.version
    assert service.repository.find_live_request(stale.request_id, stale.request_sha256) is not None


def test_native_live_version_is_append_only_at_sql_boundary(native: NativeFixture) -> None:
    service, generate, _ = native
    generate("native")
    with sqlite3.connect(service.repository.paths.database) as connection:
        for sql in (
            "UPDATE research_live_forecast_versions SET request_id='changed'",
            "DELETE FROM research_live_forecast_versions",
        ):
            with pytest.raises(sqlite3.IntegrityError, match="append-only"):
                connection.execute(sql)


def test_sql_boundary_rejects_missing_nested_native_provenance(native: NativeFixture) -> None:
    service, generate, _ = native
    generate("native")
    with sqlite3.connect(service.repository.paths.database) as connection:
        connection.row_factory = sqlite3.Row
        run = dict(connection.execute("SELECT * FROM research_runs").fetchone())
        row = dict(connection.execute("SELECT * FROM research_live_forecast_versions").fetchone())
        run["id"] = row["run_id"] = "sql-probe"
        row["request_id"], row["version"], row["pointer_advanced"] = "sql-probe", 2, 0
        rng = json.loads(row["rng_semantics_json"])
        for stage in rng["stages"]:
            stage["invocation_identity"] = "sql-probe"
        row["rng_semantics_json"] = canonical_json(rng)

        def insert(candidate: dict[str, object], *, valid: bool = False) -> None:
            connection.execute("SAVEPOINT direct_sql")
            try:
                connection.execute(
                    f"INSERT INTO research_runs ({','.join(run)}) "
                    f"VALUES ({','.join('?' for _ in run)})",
                    tuple(run.values()),
                )
                sql = (
                    f"INSERT INTO research_live_forecast_versions ({','.join(candidate)}) "
                    f"VALUES ({','.join('?' for _ in candidate)})"
                )
                if valid:
                    connection.execute(sql, tuple(candidate.values()))
                else:
                    with pytest.raises(sqlite3.IntegrityError, match=r"native|CHECK constraint"):
                        connection.execute(sql, tuple(candidate.values()))
            finally:
                connection.execute("ROLLBACK TO direct_sql")
                connection.execute("RELEASE direct_sql")

        # A valid raw-SQL control passes, so negative cases cannot accidentally
        # pass because of run/request uniqueness or an unrelated constraint.
        insert(row, valid=True)
        for column, paths in NATIVE_REQUIRED_PATHS.items():
            for path in paths:
                value = connection.execute(
                    "SELECT json_remove(?, ?)", (row[column], f"$.{path}")
                ).fetchone()[0]
                insert({**row, column: value})
        for inventory, paths in NATIVE_ARRAY_REQUIRED_PATHS.items():
            column, array = inventory.split(".")
            for path in paths:
                value = connection.execute(
                    "SELECT json_remove(?, ?)", (row[column], f"$.{array}[0].{path}")
                ).fetchone()[0]
                insert({**row, column: value})
            if inventory != "ranking_evidence_json.observations":
                value = connection.execute(
                    "SELECT json_set(?, ?, json('[]'))", (row[column], f"$.{array}")
                ).fetchone()[0]
                insert({**row, column: value})
        for path in (
            "scheduled_at",
            "timezone",
            "schedule_authority_sha256",
            "data_cutoff",
            "history_draw_count",
            "causal_history_sha256",
            "forecast_horizon",
        ):
            value = connection.execute(
                "SELECT json_remove(?, ?)", (row["target_json"], f"$.{path}")
            ).fetchone()[0]
            insert({**row, "target_json": value})
        insert(
            {
                **row,
                "runtime_manifest_json": canonical_json(
                    {
                        "python": {},
                        "os": "x",
                        "architecture": "x",
                        "dependencies": [],
                        "sha256": "x",
                    }
                ),
            }
        )
        corruptions: tuple[tuple[str, str, object], ...] = (
            ("runtime_manifest_json", "$.dependencies[0].versions", {}),
            ("runtime_manifest_json", "$.python.executable_sha256", "x"),
            ("source_execution_json", "$.commit", "x"),
            ("effective_parameters_json", "$.strategies[0].instance_state", None),
            ("rng_semantics_json", "$.stages[0].rng_semantics.seed", 0),
            ("ticket_lineage_json", "$.buckets[0].adapter_locator", None),
        )
        for column, path, value in corruptions:
            damaged = connection.execute(
                "SELECT json_set(?, ?, json(?))", (row[column], path, canonical_json(value))
            ).fetchone()[0]
            insert({**row, column: damaged})
        assert connection.execute("SELECT count(*) FROM research_runs").fetchone()[0] == 1
        assert (
            service.repository.live_current_version(
                (
                    row["lottery_type"],
                    row["target_draw_number"],
                    row["target_draw_date"],
                    row["forecast_stream_id"],
                    row["forecast_stream_version"],
                )
            )
            == 1
        )


@pytest.mark.parametrize("missing", ORIGINAL_FIELDS)
def test_missing_native_field_cannot_write(native: NativeFixture, missing: str) -> None:
    service, generate, captured = native
    first = generate("good")
    original = captured["good"].original
    original[missing] = None
    invalid = replace(
        captured["good"], request_id="bad", original_execution_json=canonical_json(original)
    )
    with pytest.raises(ValueError):
        service.repository.commit_live_forecast(
            invalid,
            expected_current_version=first.version,
            current_eligible=lambda: True,
            clock=service.clock,
        )
    assert service.repository.find_live_request("bad", invalid.request_sha256) is None


def test_observer_captures_actual_post_with_seed_adapter() -> None:
    d = replace(
        descriptor("fixture_seeded", 3),
        adapter_path=("tests.unit.test_b649_next_undrawn_forecast:FixtureSeededPortfolio"),
    )
    request = make_request((d,), seed=73)
    seen: list[object] = []
    generator = app.CanonicalNativeTicketGenerator(
        StrategyCatalog((d,)), before_execution=lambda _id, adapter: seen.append(adapter)
    )
    generator.generate(d, request.generation_configs[0], request.history)
    assert len(seen) == 1 and isinstance(seen[0], FixtureSeededPortfolio)
    assert seen[0].seed == 73


def test_loaded_source_capture_detects_code_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    original_git = live._git  # pyright: ignore[reportPrivateUsage]

    # Test code/disk parity on this uncommitted test tree only. Production retains
    # the clean-commit prerequisite; the resulting manifest is not persisted.
    def test_git(root: Path, *args: str) -> str:
        return "" if args[0] == "status" else original_git(root, *args)

    monkeypatch.setattr(live, "_git", test_git)
    root = Path(__file__).resolve().parents[2]
    assert live.capture_source_execution(root)["loaded_code_sha256"]

    def counterfeit(_value: object) -> None:
        return None

    monkeypatch.setattr(app.native_generation_config, "__code__", counterfeit.__code__)
    with pytest.raises(ValueError, match="loaded source differs"):
        live.capture_source_execution(root)


def test_streams_cannot_replace_each_others_current(
    native: NativeFixture,
    legacy_input: LiveForecastInput,
) -> None:
    service, generate, captured = native
    first = generate("native-first")
    imported = service.repository.commit_live_forecast(
        legacy_input, expected_current_version=0, current_eligible=lambda: True, clock=service.clock
    )
    assert captured["native-first"].scope[:3] == legacy_input.scope[:3]
    assert service.repository.live_current_version(captured["native-first"].scope) == first.version
    second = generate("native-second")
    assert second.pointer_advanced
    assert service.repository.live_current_version(legacy_input.scope) == imported.version
    retry = service.repository.commit_live_forecast(
        legacy_input, expected_current_version=0, current_eligible=lambda: True, clock=service.clock
    )
    assert retry.idempotent and retry.run_id == imported.run_id
    assert service.repository.live_current_version(captured["native-first"].scope) == second.version


def test_history_sql_never_selects_target_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with sqlite3.connect(":memory:") as connection:
        connection.execute(
            "CREATE TABLE draws(lottery_type, draw_number, draw_date, "
            "main_numbers_json, special_numbers_json)"
        )
        connection.execute(
            "INSERT INTO draws VALUES ('BIG_LOTTO','115000086','2026-09-08','[1,2,3,4,5,6]','[7]')"
        )
        connection.execute(
            "INSERT INTO draws VALUES ('BIG_LOTTO','115000087','2026-09-11',"
            "'TARGET_MUST_NEVER_BE_READ','TARGET_MUST_NEVER_BE_READ')"
        )

        @contextmanager
        def opener(_paths: object, *, read_only: bool):
            assert read_only
            yield connection

        monkeypatch.setattr(live, "open_draw_database", opener)
        service = live.B649LiveForecastService(
            cast(SQLiteResearchRepository, object()), cast(LocalDataPaths, object()), tmp_path
        )
        read_history = service._history  # pyright: ignore[reportPrivateUsage]
        rows = read_history(
            ObservationTarget(LotteryType.BIG_LOTTO, "115000087", date(2026, 9, 11))
        )
        assert len(rows) == 1 and rows[0].draw_number == "115000086"


_ANNOUNCEMENT_TARGET = ObservationTarget(LotteryType.BIG_LOTTO, "115000087", date(2026, 9, 11))
_ANNOUNCEMENT_CLOCK = datetime(2026, 9, 9, tzinfo=UTC)
_ANNOUNCEMENT_SCHEDULED_AT = datetime(2026, 9, 11, 12, 30, tzinfo=UTC)
_ANNOUNCEMENT_HISTORY = tuple(
    Draw(str(115000081 + i), date(2026, 9, 1) + timedelta(days=i), (1, 2, 3, 4, 5, 6), 7)
    for i in range(6)
)


def _announcement_only_draw_paths(tmp_path: Path) -> LocalDataPaths:
    paths = resolve_local_data_paths(
        environ={DATA_DIRECTORY_ENV: str(tmp_path / "canonical-test-data")}
    )
    initialize_schema(paths)
    history_rows = [
        (
            f"BIG_LOTTO,{draw.draw_number},{draw.draw_date.isoformat()},"
            "1|2|3|4|5|6,7,synthetic-history"
        )
        for draw in _ANNOUNCEMENT_HISTORY
    ]
    parsed = parse_draw_csv(
        "\n".join(
            (
                "lottery_type,draw_number,draw_date,main_numbers,special_numbers,source",
                *history_rows,
                "",
            )
        ),
        filename="synthetic-history.csv",
    )
    assert parsed.is_valid, parsed.errors
    imported = SQLiteDrawDataRepository(paths).apply_valid_import(parsed)
    assert imported.status is IngestionRunStatus.SUCCESS
    assert imported.inserted_count == 6
    document = {
        "announcements": [
            {
                "schedule_timezone": "Asia/Taipei",
                "scheduled_at": "2026-09-11T12:30:00Z",
                "source": {
                    "observed_at": "2026-09-01T00:00:00Z",
                    "source_id": "TAIWAN_LOTTERY_OFFICIAL_SCHEDULE",
                    "source_locator": (
                        "https://www.taiwanlottery.com/schedule/115000087?variant=canonical"
                    ),
                    "source_payload_sha256": hashlib.sha256(b"canonical").hexdigest(),
                    "source_version": "taiwan-lottery-official-schedule-v1",
                },
                "target": {
                    "draw_date": "2026-09-11",
                    "draw_number": "115000087",
                    "lottery_type": "BIG_LOTTO",
                },
            }
        ],
        "schema_version": OPERATIONAL_ANNOUNCEMENT_SCHEMA_VERSION,
    }
    encoded = json.dumps(document, separators=(",", ":"), sort_keys=True).encode()
    parsed_input = parse_owner_certified_future_draw_identity_input(
        encoded,
        source_filename="synthetic-115000087-canonical.json",
    )
    selected = select_owner_certified_future_draw_identity(
        parsed_input,
        lottery_type=LotteryType.BIG_LOTTO,
        draw_number="115000087",
    )
    committed = SQLiteManualFutureDrawIdentitySupplementRepository(
        paths
    ).apply_owner_certified_supplement(parsed_input, selected, parsed_input.input_sha256)
    assert committed.inserted_count == 1
    completed = (
        (_ANNOUNCEMENT_CLOCK - timedelta(hours=1))
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )
    with open_draw_database(paths, read_only=False) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO ingestion_runs (
                id, operation_type, status, lottery_type, source_filename,
                source_sha256, parser_version, total_count, inserted_count,
                skipped_count, conflict_count, failed_count, first_draw_number,
                last_draw_number, started_at, completed_at, error_summary
            ) VALUES (?, ?, ?, 'BIG_LOTTO', 'official-sync.json', ?, 'test-parser-v1',
                      0, 0, 0, 0, 0, NULL, NULL, ?, ?, NULL)
            """,
            (
                "official-presence-audit",
                IngestionOperationType.MANUAL_SYNC.value,
                IngestionRunStatus.SUCCESS.value,
                hashlib.sha256(b"official-presence-audit").hexdigest(),
                completed,
                completed,
            ),
        )
        connection.execute(
            """
            INSERT INTO ingestion_run_context (
                ingestion_run_id, trigger, provider, provider_version,
                requested_start, requested_end, resolved_start, resolved_end,
                fetched_count
            ) VALUES (?, ?, ?, ?, '2026-09-11', '2026-09-11', NULL, NULL, 0)
            """,
            (
                "official-presence-audit",
                IngestionOperationType.MANUAL_SYNC.value,
                PROVIDER_ID,
                PROVIDER_VERSION,
            ),
        )
        connection.commit()
    return paths


def _insert_target_outcome(paths: LocalDataPaths) -> None:
    parsed = parse_draw_csv(
        "\n".join(
            (
                "lottery_type,draw_number,draw_date,main_numbers,special_numbers,source",
                "BIG_LOTTO,115000087,2026-09-11,1|2|3|4|5|6,7,synthetic-outcome",
                "",
            )
        ),
        filename="synthetic-outcome.csv",
    )
    assert parsed.is_valid, parsed.errors
    imported = SQLiteDrawDataRepository(paths).apply_valid_import(parsed)
    assert imported.status is IngestionRunStatus.SUCCESS
    assert imported.inserted_count == 1


def _gate_service(
    paths: LocalDataPaths, clock: Callable[[], datetime]
) -> live.B649LiveForecastService:
    return live.B649LiveForecastService(
        cast(SQLiteResearchRepository, object()),
        paths,
        Path(__file__).resolve().parents[2],
        clock,
    )


def _patch_execution_capture(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_source(_root: Path) -> dict[str, object]:
        return {
            "repository": "fixture://source",
            "commit": "a" * 40,
            "tree": "b" * 40,
            "loaded_code_sha256": digest("fixture-code"),
        }

    monkeypatch.setattr(live, "capture_source_execution", fake_source)
    runtime = {
        "python": {
            "implementation": "CPython",
            "version": "fixture",
            "executable": "fixture",
            "executable_sha256": digest("fixture-runtime"),
        },
        "os": "fixture",
        "architecture": "fixture",
        "dependencies": [
            {
                "name": "fixture-runtime",
                "locator": "fixture://runtime",
                "versions": {"fixture": "1"},
                "content_sha256": digest("runtime"),
            }
        ],
    }
    monkeypatch.setattr(
        live, "capture_runtime_manifest", lambda: {**runtime, "sha256": digest(runtime)}
    )


def _native_sqlite_service(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[
    live.B649LiveForecastService,
    tuple[ReplayObservation, ...],
    dict[str, LiveForecastInput],
    dict[str, app.ForecastRequest],
    LocalDataPaths,
]:
    paths = _announcement_only_draw_paths(tmp_path)
    selected = production_catalog().get(
        "legacy_biglotto__frontend_frequency_strategy__2e3e8febb5f1"
    )
    assert selected is not None
    catalog = StrategyCatalog((selected,))
    monkeypatch.setattr(live, "production_catalog", lambda: catalog)
    monkeypatch.setattr(app, "production_catalog", lambda: catalog)
    producer = ProducerFingerprint.create(
        producer_id="fixture-producer",
        producer_version="fixture-v1",
        dependencies=(
            ProducerDependency("fixture://frequency", digest("test-code"), "test binding"),
        ),
    )
    observations = tuple(
        ReplayObservation(
            selected.strategy_id,
            selected.version,
            1,
            draw.draw_number,
            draw.draw_date,
            history_ref(_ANNOUNCEMENT_HISTORY[:i]).history_sha256,
            app.native_generation_config(selected, _ANNOUNCEMENT_HISTORY[:i]).sha256,
            ObservationStatus.EVALUATED,
            ((1, 2, 3, 4, 5, 6),),
            producer_fingerprint=producer.digest,
        )
        for i, draw in enumerate(_ANNOUNCEMENT_HISTORY)
        if i >= selected.min_history
    )

    def fake_fingerprint(*_args: object) -> ProducerFingerprint:
        return producer

    monkeypatch.setattr(live, "source_producer_fingerprint", fake_fingerprint)
    _patch_execution_capture(monkeypatch)
    directory = tmp_path / "research"
    repo = SQLiteResearchRepository(
        ResearchDataPaths(directory, directory / "lottolab_research.db")
    )
    captured: dict[str, LiveForecastInput] = {}
    original_commit = repo.commit_live_forecast

    def capture_commit(
        forecast: LiveForecastInput,
        *,
        expected_current_version: int,
        current_eligible: Callable[[], bool],
        clock: Callable[[], datetime],
    ) -> LiveForecastResult:
        captured[forecast.request_id] = forecast
        return original_commit(
            forecast,
            expected_current_version=expected_current_version,
            current_eligible=current_eligible,
            clock=clock,
        )

    monkeypatch.setattr(repo, "commit_live_forecast", capture_commit)
    requests: dict[str, app.ForecastRequest] = {}
    original_prepare = live.prepare_forecast

    def capture_prepare(
        request: app.ForecastRequest, generator: app.NativeTicketGenerator
    ) -> app.PreparedForecast:
        requests["current"] = request
        return original_prepare(request, generator)

    monkeypatch.setattr(live, "prepare_forecast", capture_prepare)
    service = live.B649LiveForecastService(
        repo,
        paths,
        Path(__file__).resolve().parents[2],
        lambda: _ANNOUNCEMENT_CLOCK,
    )
    return service, observations, captured, requests, paths


def test_sqlite_v4_announcement_binding_is_shared_by_gate_request_and_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, observations, captured, requests, paths = _native_sqlite_service(tmp_path, monkeypatch)
    with open_draw_database(paths, read_only=True) as connection:
        assert connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone() == (
            CURRENT_SCHEMA_VERSION,
        )
        assert connection.execute("SELECT COUNT(*) FROM draw_schedule_facts").fetchone() == (0,)
    read_schedule = service._schedule  # pyright: ignore[reportPrivateUsage]
    read_gate = service._gate  # pyright: ignore[reportPrivateUsage]
    record = read_schedule()
    assert isinstance(record, ScheduledDrawIdentityRecord)
    assert record.immutable_schedule_sha256 is None
    expected = normalized_announcement_sha256(record.announcement)
    assert record.normalized_announcement_hash == expected
    assert read_gate(record) is True
    result = service.repredict(request_id="binding", observations=observations, seeds={})
    assert result.pointer_advanced
    request = requests["current"]
    forecast = captured["binding"]
    persisted = json.loads(forecast.target_json)
    payload = json.loads(forecast.payload_bytes)
    assert request.schedule_authority_sha256 == expected
    assert persisted["schedule_authority_sha256"] == expected
    assert payload["identity"]["schedule_authority_sha256"] == expected
    assert "immutable_schedule_sha256" not in persisted
    with sqlite3.connect(service.repository.paths.database) as connection:
        stored = json.loads(
            connection.execute(
                "SELECT target_json FROM research_live_forecast_versions"
            ).fetchone()[0]
        )
    assert stored["schedule_authority_sha256"] == expected


@pytest.mark.parametrize("kind", ["target", "date", "time", "hash"])
def test_sqlite_v4_gate_rejects_wrong_target_date_time_or_hash(tmp_path: Path, kind: str) -> None:
    paths = _announcement_only_draw_paths(tmp_path)
    service = _gate_service(paths, lambda: _ANNOUNCEMENT_CLOCK)
    read_schedule = service._schedule  # pyright: ignore[reportPrivateUsage]
    read_gate = service._gate  # pyright: ignore[reportPrivateUsage]
    record = read_schedule()
    if kind == "target":
        mutated = replace(
            record,
            announcement=replace(
                record.announcement,
                target=replace(record.announcement.target, draw_number="115000099"),
            ),
        )
    elif kind == "date":
        mutated = replace(
            record,
            announcement=replace(
                record.announcement,
                target=replace(record.announcement.target, draw_date=date(2026, 9, 12)),
                scheduled_at=datetime(2026, 9, 12, 12, 30, tzinfo=UTC),
            ),
        )
    elif kind == "time":
        mutated = replace(
            record,
            announcement=replace(
                record.announcement,
                scheduled_at=datetime(2026, 9, 11, 11, 30, tzinfo=UTC),
            ),
        )
    else:
        mutated = replace(record, normalized_announcement_hash="a" * 64)
    with pytest.raises(app.ForecastTimingError, match="CANONICAL_TARGET_OR_SCHEDULE_CHANGED"):
        read_gate(mutated)


def test_sqlite_v4_gate_rejects_outcome_present(tmp_path: Path) -> None:
    paths = _announcement_only_draw_paths(tmp_path)
    stable = _gate_service(paths, lambda: _ANNOUNCEMENT_CLOCK)
    record = stable._schedule()  # pyright: ignore[reportPrivateUsage]
    assert stable._gate(record) is True  # pyright: ignore[reportPrivateUsage]
    calls = {"n": 0}

    def present_clock() -> datetime:
        calls["n"] += 1
        if calls["n"] == 2:
            _insert_target_outcome(paths)
        return _ANNOUNCEMENT_CLOCK

    present = _gate_service(paths, present_clock)
    with pytest.raises(app.ForecastTimingError, match="OUTCOME_PRESENT_OR_DEADLINE_REACHED"):
        present._gate(record)  # pyright: ignore[reportPrivateUsage]


def test_sqlite_v4_gate_rejects_deadline(tmp_path: Path) -> None:
    paths = _announcement_only_draw_paths(tmp_path)
    stable = _gate_service(paths, lambda: _ANNOUNCEMENT_CLOCK)
    record = stable._schedule()  # pyright: ignore[reportPrivateUsage]
    remaining = [
        _ANNOUNCEMENT_CLOCK,
        _ANNOUNCEMENT_CLOCK,
        _ANNOUNCEMENT_SCHEDULED_AT,
    ]
    expired = _gate_service(paths, lambda: remaining.pop(0))
    with pytest.raises(app.ForecastTimingError, match="OUTCOME_PRESENT_OR_DEADLINE_REACHED"):
        expired._gate(record)  # pyright: ignore[reportPrivateUsage]
    due = _gate_service(paths, lambda: _ANNOUNCEMENT_SCHEDULED_AT)
    with pytest.raises(
        app.ForecastTimingError, match="CANONICAL_NEXT_UNDRAWN_SCHEDULE_UNAVAILABLE"
    ):
        due._schedule()  # pyright: ignore[reportPrivateUsage]


def test_legacy_import_does_not_request_current_when_native_gate_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _announcement_only_draw_paths(tmp_path)
    _patch_execution_capture(monkeypatch)
    payload = json.dumps(
        {
            "causal_history_sha256": LEGACY_HISTORY_SHA256,
            "data_cutoff": 115000086,
            "forecast_horizon": 1,
            "forecast_target": 115000087,
            "history_draw_count": 2168,
            "materialization_task": LEGACY_MATERIALIZATION_TASK,
            "sealed_forecast_mutated": False,
            "sealed_forecast_sha256": LEGACY_SEAL_SHA256,
            "source_forecast_recomputed": False,
            "source_task": LEGACY_SOURCE_TASK,
            "target_outcome_inspected": False,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    digest_hex = sha256(payload)
    monkeypatch.setattr(live, "LEGACY_SHA256", digest_hex)
    monkeypatch.setattr(forecast_domain, "LEGACY_SHA256", digest_hex)
    payload_path = tmp_path / "legacy-payload.json"
    payload_path.write_bytes(payload)
    directory = tmp_path / "research"
    repo = SQLiteResearchRepository(
        ResearchDataPaths(directory, directory / "lottolab_research.db")
    )
    stored: list[LiveForecastResult] = []

    def fake_find(_request_id: str, _request_sha256: str) -> LiveForecastResult | None:
        return stored[0] if stored else None

    def fake_commit(
        forecast: LiveForecastInput,
        *,
        expected_current_version: int,
        current_eligible: Callable[[], bool],
        clock: Callable[[], datetime],
    ) -> LiveForecastResult:
        assert expected_current_version == 0
        assert current_eligible() is False
        assert forecast.provenance_class == "LEGACY_MATERIALIZED"
        result = LiveForecastResult(
            "legacy-run",
            1,
            False,
            bool(stored),
            digest_hex,
            digest("envelope"),
        )
        stored.append(result)
        return result

    monkeypatch.setattr(repo, "find_live_request", fake_find)
    monkeypatch.setattr(repo, "commit_live_forecast", fake_commit)
    service = live.B649LiveForecastService(
        repo,
        paths,
        Path(__file__).resolve().parents[2],
        lambda: _ANNOUNCEMENT_CLOCK,
    )
    read_schedule = service._schedule  # pyright: ignore[reportPrivateUsage]
    read_gate = service._gate  # pyright: ignore[reportPrivateUsage]
    record = read_schedule()
    assert record.immutable_schedule_sha256 is None
    assert read_gate(record) is True
    first = service.import_legacy(payload_path)
    retry = service.import_legacy(payload_path)
    assert not first.pointer_advanced
    assert retry.run_id == first.run_id
    assert len(stored) == 1
    assert (
        repo.live_current_version(
            ("BIG_LOTTO", "115000087", "2026-09-11", LEGACY_STREAM, LEGACY_STREAM)
        )
        == 0
    )


def test_legacy_import_sqlite_stays_history_only_with_pinned_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    legacy_input: LiveForecastInput,
) -> None:
    paths = _announcement_only_draw_paths(tmp_path)
    _patch_execution_capture(monkeypatch)
    directory = tmp_path / "research"
    repo = SQLiteResearchRepository(
        ResearchDataPaths(directory, directory / "lottolab_research.db")
    )
    service = live.B649LiveForecastService(
        repo,
        paths,
        Path(__file__).resolve().parents[2],
        lambda: _ANNOUNCEMENT_CLOCK,
    )
    read_schedule = service._schedule  # pyright: ignore[reportPrivateUsage]
    read_gate = service._gate  # pyright: ignore[reportPrivateUsage]
    record = read_schedule()
    assert record.immutable_schedule_sha256 is None
    assert read_gate(record) is True
    payload_path = Path(legacy_input.source_locator)
    first = service.import_legacy(payload_path)
    retry = service.import_legacy(payload_path)
    scope = (
        "BIG_LOTTO",
        "115000087",
        "2026-09-11",
        LEGACY_STREAM,
        LEGACY_STREAM,
    )
    assert not first.pointer_advanced
    assert retry.idempotent and retry.run_id == first.run_id
    assert repo.live_current_version(scope) == 0
    with sqlite3.connect(repo.paths.database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM research_runs").fetchone() == (1,)
        assert connection.execute(
            "SELECT COUNT(*) FROM research_live_forecast_current_pointer"
        ).fetchone() == (0,)
        row = connection.execute(
            "SELECT request_id, provenance_class, forecast_stream_id FROM "
            "research_live_forecast_versions"
        ).fetchone()
        assert row == (live.LEGACY_IMPORT_KEY, "LEGACY_MATERIALIZED", LEGACY_STREAM)
