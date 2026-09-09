"""Canonical native adapter execution with isolated schedule/runtime authorities."""

from __future__ import annotations

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
from lottolab.domain.b649_next_undrawn_forecast import (
    ObservationStatus,
    ReplayObservation,
    history_ref,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.exact_native_replay import Draw
from lottolab.domain.prospective_observer import (
    ObservationTarget,
    ProducerDependency,
    ProducerFingerprint,
)
from lottolab.domain.research_live_forecast import (
    ORIGINAL_FIELDS,
    LiveForecastInput,
    LiveForecastResult,
    canonical_json,
    digest,
)
from lottolab.infrastructure import b649_live_forecast as live
from lottolab.infrastructure.persistence.draw_schema import LocalDataPaths
from lottolab.infrastructure.persistence.research_repository import SQLiteResearchRepository
from lottolab.infrastructure.persistence.research_schema import ResearchDataPaths
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
        immutable_schedule_sha256=digest("fixture schedule"),
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


def test_stale_writer_retains_history(native: NativeFixture) -> None:
    service, generate, captured = native
    current = generate("newer")
    stale = replace(captured["newer"], request_id="older")
    result = service.repository.commit_live_forecast(
        stale, expected_current_version=0, current_eligible=lambda: True, clock=service.clock
    )
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
