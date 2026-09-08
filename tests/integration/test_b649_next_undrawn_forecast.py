"""Fixture-only sealing, publication races, timing and CLI composition."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal, TypedDict, cast

import pytest
from tests.unit.test_b649_next_undrawn_forecast import (
    DEADLINE,
    LOSE,
    NOW,
    WIN,
    Generator,
    descriptor,
    make_request,
)

from lottolab.application.b649_next_undrawn_forecast import (
    ForecastConflictError,
    ForecastLiveState,
    ForecastRequest,
    ForecastTimingError,
    NextUndrawnForecastService,
    prepare_forecast,
)
from lottolab.application.pre_outcome_target_operational import (
    OperationalRegistrationResult,
    OperationalRegistrationStatus,
)
from lottolab.domain.b649_next_undrawn_forecast import COHORT_ID, ForecastContractError
from lottolab.domain.pre_outcome_target import (
    OutcomePresenceAttestation,
    PreOutcomeTargetRegistration,
    TargetAnnouncement,
    TargetSourceProvenance,
)
from lottolab.domain.prospective_observer import (
    ObservationTarget,
    OutcomePresenceAtPrediction,
    PredictionContext,
    PredictionPhaseRequest,
    PredictionRecord,
    ProducerFingerprint,
)
from lottolab.infrastructure.b649_next_undrawn_forecast import (
    FileSystemForecastBundleStore,
    FixtureRegistration,
    source_producer_fingerprint,
)
from lottolab.infrastructure.prospective_observer_store import FileSystemProspectiveObservationStore


class ServiceState(TypedDict):
    now: datetime
    outcome: bool | None
    scheduled: datetime
    digest: str


class StateChange(TypedDict, total=False):
    now: datetime
    outcome: bool | None
    scheduled: datetime
    digest: str


class FixtureTarget(TypedDict):
    draw_number: str
    draw_date: str
    scheduled_at: str


class FixtureHistoryRow(TypedDict):
    draw_number: str
    draw_date: str
    main_numbers: list[int]
    special_number: int


class FixtureStrategy(TypedDict):
    strategy_id: str
    native_k: int
    generated_tickets: list[list[int]]


class FixtureObservation(TypedDict):
    strategy_id: str
    draw_number: str
    status: str
    tickets: list[list[int]]


class FixtureDocument(TypedDict):
    fixture_only: bool
    now: str
    target: FixtureTarget
    history: list[FixtureHistoryRow]
    strategies: list[FixtureStrategy]
    observations: list[FixtureObservation]


def service_env(
    tmp_path: Path,
    request: ForecastRequest | None = None,
    generator: Generator | None = None,
) -> tuple[
    ForecastRequest,
    NextUndrawnForecastService,
    ServiceState,
    FileSystemForecastBundleStore,
]:
    request = request or make_request()
    source = TargetSourceProvenance(
        "fixture", "fixture-v1", "fixture://schedule", request.schedule_authority_sha256, NOW
    )
    announcement = TargetAnnouncement(request.target, "Asia/Taipei", DEADLINE, source)
    registration = PreOutcomeTargetRegistration.create(
        announcement=announcement,
        absence_attestation=OutcomePresenceAttestation(
            request.target, OutcomePresenceAtPrediction.ABSENT, NOW, source
        ),
        causal_history=request.history_authority,
        registered_at=NOW,
    )
    authority = OperationalRegistrationResult(
        OperationalRegistrationStatus.CREATED,
        announcement,
        request.history_authority,
        registration,
        request.schedule_authority_sha256,
    )
    state: ServiceState = {
        "now": NOW,
        "outcome": False,
        "scheduled": DEADLINE,
        "digest": request.schedule_authority_sha256,
    }
    store = FileSystemForecastBundleStore(tmp_path)
    service = NextUndrawnForecastService(
        FixtureRegistration(authority),
        lambda _target: ForecastLiveState(
            state["scheduled"], state["digest"], cast(bool, state["outcome"])
        ),
        lambda: state["now"],
        generator or Generator(),
        store,
    )
    return request, service, state, store


def snapshot(path: Path) -> tuple[bytes, int, int]:
    return path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_ino


def test_original_generic_record_and_timestamps_survive_restart_and_idempotence(
    tmp_path: Path,
):
    request, service, state, store = service_env(tmp_path)
    first = service.run(request)
    path = store.path_for(request.identity)
    before = snapshot(path)
    with zipfile.ZipFile(path) as archive:
        assert len(archive.namelist()) == 2
        assert "bundle.json" in archive.namelist()
        assert sum(n.endswith("prediction.json") for n in archive.namelist()) == 1
    assert first.prediction.identity.cohort_id == COHORT_ID
    assert first.prediction.identity.cohort_version == request.identity.bundle_id
    assert first.prediction.causal_history == request.history_authority
    assert len(first.prediction.entries) == 6
    state["now"] = NOW + timedelta(hours=1)
    restarted = replace(service, store=FileSystemForecastBundleStore(tmp_path))
    assert restarted.run(request) == first
    assert snapshot(path) == before
    assert list(store.root.iterdir()) == [path]


def test_stale_evidence_fingerprint_cannot_publish_under_new_outer_bundle_identity(
    tmp_path: Path,
):
    request, service, _state, store = service_env(tmp_path)
    first = service.run(request)
    path = store.path_for(request.identity)
    before = snapshot(path)
    changed = replace(
        request,
        producer=ProducerFingerprint.create(
            producer_id=request.producer.producer_id,
            producer_version="new-generator-version",
            dependencies=request.producer.dependencies,
        ),
    )
    assert changed.identity.bundle_id != first.bundle.identity.bundle_id
    with pytest.raises(ForecastContractError, match="REPLAY_HISTORY_OR_GENERATION"):
        service.run(changed)
    assert snapshot(path) == before
    assert list(store.root.iterdir()) == [path]


@pytest.mark.parametrize("change", ["tickets", "evidence"])
def test_same_identity_conflicting_payload_never_overwrites(
    tmp_path: Path, change: Literal["tickets", "evidence"]
):
    request, service, _state, store = service_env(tmp_path)
    first = service.run(request)
    path = store.path_for(request.identity)
    before = snapshot(path)
    if change == "tickets":
        assert isinstance(service.generator, Generator)
        service.generator.tickets["fixture_a"] = (LOSE,)
    else:
        request = replace(
            request,
            observations=(
                replace(request.observations[0], tickets=(LOSE,)),
                *request.observations[1:],
            ),
        )
    assert request.identity == first.bundle.identity
    with pytest.raises(ForecastConflictError, match="conflicting payload"):
        service.run(request)
    assert snapshot(path) == before
    assert list(store.root.iterdir()) == [path]


def test_corrupt_existing_record_is_rejected_and_not_replaced(tmp_path: Path):
    request, service, _state, store = service_env(tmp_path)
    service.run(request)
    path = store.path_for(request.identity)
    path.write_bytes(b"corrupt-fixture")
    before = snapshot(path)
    with pytest.raises(ForecastConflictError, match="corrupt immutable"):
        service.run(request)
    assert snapshot(path) == before


def test_two_equal_writers_reuse_one_complete_durable_record(tmp_path: Path):
    request, first, _state, store = service_env(tmp_path)
    second = replace(first, clock=lambda: NOW + timedelta(seconds=1))
    with ThreadPoolExecutor(max_workers=2) as workers:
        pending = [workers.submit(service.run, request) for service in (first, second)]
        results = [future.result() for future in pending]
    assert results[0] == results[1]
    assert list(store.root.iterdir()) == [store.path_for(request.identity)]


STATE_CHANGES: tuple[tuple[StateChange, str], ...] = (
    ({"outcome": True}, "OUTCOME_PRESENT"),
    ({"outcome": None}, "OUTCOME_PRESENT_OR_UNKNOWN"),
    ({"now": DEADLINE}, "DEADLINE"),
    ({"now": DEADLINE + timedelta(seconds=1)}, "DEADLINE"),
    ({"scheduled": DEADLINE - timedelta(minutes=1)}, "AUTHORITY_DRIFT"),
    ({"digest": "f" * 64}, "AUTHORITY_DRIFT"),
)


@pytest.mark.parametrize("state_change,reason", STATE_CHANGES)
def test_closed_initial_gate_does_not_generate_or_publish(
    tmp_path: Path, state_change: StateChange, reason: str
):
    generator = Generator()
    request, service, state, store = service_env(tmp_path, generator=generator)
    state.update(state_change)
    with pytest.raises(ForecastTimingError, match=reason):
        service.run(request)
    assert not generator.calls
    assert not list(store.root.iterdir())


@pytest.mark.parametrize("change", ["deadline", "outcome", "clock_regression"])
def test_computation_crossing_deadline_or_new_outcome_is_rejected(
    tmp_path: Path, change: Literal["deadline", "outcome", "clock_regression"]
):
    request, service, state, store = service_env(tmp_path)

    def during_generation() -> None:
        if change == "deadline":
            state["now"] = DEADLINE
        elif change == "clock_regression":
            state["now"] = NOW - timedelta(seconds=1)
        else:
            state["outcome"] = True

    generator = Generator(after=during_generation)
    service = replace(service, generator=generator)
    with pytest.raises(ForecastTimingError):
        service.run(request)
    assert len(generator.calls) == 1
    assert not list(store.root.iterdir())


@pytest.mark.parametrize("change", ["deadline", "outcome"])
def test_fresh_gate_after_archive_preparation_before_atomic_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: Literal["deadline", "outcome"]
):
    request, service, state, store = service_env(tmp_path)
    original_close = zipfile.ZipFile.close

    def close(archive: zipfile.ZipFile) -> None:
        original_close(archive)
        if archive.filename and Path(archive.filename).name == "bundle.tmp":
            if change == "deadline":
                state["now"] = DEADLINE
            else:
                state["outcome"] = True

    monkeypatch.setattr(zipfile.ZipFile, "close", close)
    with pytest.raises(ForecastTimingError):
        service.run(request)
    assert not list(store.root.iterdir())


def test_clock_read_after_slow_presence_probe_catches_deadline(tmp_path: Path):
    request, service, state, store = service_env(tmp_path)
    probes = 0

    def read_presence(_target: ObservationTarget) -> ForecastLiveState:
        nonlocal probes
        probes += 1
        if probes == 4:  # The last probe, after the generic record and archive were prepared.
            state["now"] = DEADLINE
        return ForecastLiveState(DEADLINE, request.schedule_authority_sha256, False)

    with pytest.raises(ForecastTimingError, match="DEADLINE"):
        replace(service, read_live_state=read_presence).run(request)
    assert probes == 4 and not list(store.root.iterdir())


def test_outcome_appearing_after_publication_does_not_rewrite_accepted_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    request, service, state, store = service_env(tmp_path)
    original_link = os.link

    def link(
        source: str | os.PathLike[str],
        destination: str | os.PathLike[str],
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> None:
        original_link(
            source,
            destination,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
            follow_symlinks=follow_symlinks,
        )
        if Path(destination).suffix == ".zip":
            state["outcome"] = True
            state["now"] = DEADLINE

    monkeypatch.setattr(os, "link", link)
    stored = service.run(request)
    assert stored.prediction.predicted_at < DEADLINE
    assert store.load(request.identity) == stored


def test_campaign_namespace_and_existing_comparison_fixture_unchanged(tmp_path: Path):
    campaign_source = (
        Path(__file__).resolve().parents[2] / "src/lottolab/application/"
        "b649_prospective_campaign_seal.py"
    )
    source_before = hashlib.sha256(campaign_source.read_bytes()).hexdigest()
    request, service, _state, store = service_env(tmp_path)
    draft = prepare_forecast(request, Generator()).draft
    first = service.run(request)
    campaign_cohort = replace(
        first.prediction.cohort,
        cohort_id="IMMUTABLE_COMPARATIVE_EVIDENCE",
        cohort_version="fixture-086",
    )
    campaign = PredictionRecord.create(
        request=PredictionPhaseRequest(
            PredictionContext(
                request.target, campaign_cohort, request.producer, request.history_authority
            ),
            OutcomePresenceAtPrediction.ABSENT,
        ),
        draft=draft,
        predicted_at=NOW,
    )
    generic = FileSystemProspectiveObservationStore(tmp_path)
    generic.create_prediction(campaign)
    existing_paths = list((tmp_path / "big_lotto").rglob("prediction.json"))
    assert len(existing_paths) == 1
    before = {path: snapshot(path) for path in existing_paths}
    next_producer = ProducerFingerprint.create(
        producer_id=request.producer.producer_id,
        producer_version="fixture-v2",
        dependencies=request.producer.dependencies,
    )
    # A new producer needs newly produced synthetic evidence, not the old rows.
    changed = make_request(producer=next_producer)
    second = service.run(changed)
    assert second.bundle.identity.bundle_id != first.bundle.identity.bundle_id
    assert {path: snapshot(path) for path in existing_paths} == before
    assert generic.get_prediction(campaign.identity) == campaign
    assert hashlib.sha256(campaign_source.read_bytes()).hexdigest() == source_before
    assert len(tuple(store.root.glob("*.zip"))) == 2


def fixture_document() -> FixtureDocument:
    request = make_request((descriptor("fixture_a"), descriptor("fixture_k2", 2)))
    return {
        "fixture_only": True,
        "now": NOW.isoformat(),
        "target": {
            "draw_number": request.target.draw_number,
            "draw_date": request.target.draw_date.isoformat(),
            "scheduled_at": DEADLINE.isoformat(),
        },
        "history": [
            {
                "draw_number": d.draw_number,
                "draw_date": d.draw_date.isoformat(),
                "main_numbers": list(d.main_numbers),
                "special_number": d.special_number,
            }
            for d in request.history
        ],
        "strategies": [
            {
                "strategy_id": d.strategy_id,
                "native_k": d.native_ticket_count,
                "generated_tickets": [list(WIN)] * d.native_ticket_count,
            }
            for d in request.catalog
        ],
        "observations": [
            {
                "strategy_id": o.strategy_id,
                "draw_number": o.draw_number,
                "status": o.status.value,
                "tickets": [list(t) for t in o.tickets],
            }
            for o in request.observations
        ],
    }


def cli(tmp_path: Path, document: FixtureDocument) -> subprocess.CompletedProcess[str]:
    fixture = tmp_path / "synthetic.json"
    fixture.write_text(json.dumps(document), encoding="utf-8")
    return subprocess.run(
        [
            sys.executable,
            "tools/b649_next_undrawn_forecast.py",
            "--fixture",
            str(fixture),
            "--fixture-store",
            str(tmp_path / "fixture-store"),
        ],
        cwd=Path(__file__).resolve().parents[2],
        env={**os.environ, "LOTTOLAB_DATA_DIR": str(tmp_path / "unused-production-data")},
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_uses_only_fixture_store_and_is_reproducible(tmp_path: Path):
    first = cli(tmp_path, fixture_document())
    assert first.returncode == 0, first.stdout + first.stderr
    result = json.loads(first.stdout)
    assert result["fixture_only"] is True and result["forecast"]["fixture_only"] is True
    archives = tuple((tmp_path / "fixture-store").rglob("*.zip"))
    assert len(archives) == 1
    before = snapshot(archives[0])
    second = cli(tmp_path, fixture_document())
    assert second.returncode == 0 and second.stdout == first.stdout
    assert snapshot(archives[0]) == before
    assert not (tmp_path / "unused-production-data").exists()
    assert not tuple(tmp_path.rglob("*.sqlite*"))


@pytest.mark.parametrize("change", ["mode", "strategy"])
def test_cli_rejects_nonfixture_composition_without_creating_store(
    tmp_path: Path, change: Literal["mode", "strategy"]
):
    document = fixture_document()
    if change == "mode":
        document["fixture_only"] = False
    else:
        document["strategies"][0]["strategy_id"] = "real_canonical_strategy"
    result = cli(tmp_path, document)
    assert result.returncode == 2 and "FIXTURE" in result.stderr
    assert not (tmp_path / "fixture-store").exists()


def test_producer_fingerprint_binds_relative_imports_and_bundled_generation_data(
    tmp_path: Path,
):
    files: dict[str, str] = {
        "src/lottolab/application/b649_next_undrawn_forecast.py": "from ..domain import loaded\n",
        "src/lottolab/domain/loaded.py": "VALUE = 1\n",
        "src/lottolab/strategies/catalog.py": "# synthetic catalog\n",
        "src/lottolab/infrastructure/b649_next_undrawn_forecast.py": "# synthetic producer\n",
        "src/lottolab/strategies/data/parameters.json": '{"seed":1}',
        "tools/b649_next_undrawn_forecast.py": "# synthetic composition\n",
    }
    for relative, content in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    first = source_producer_fingerprint(tmp_path, ())
    assert "src/lottolab/domain/loaded.py" in [d.locator for d in first.dependencies]
    assert first == source_producer_fingerprint(tmp_path, ())
    (tmp_path / "src/lottolab/domain/loaded.py").write_text("VALUE = 2\n", encoding="utf-8")
    changed_code = source_producer_fingerprint(tmp_path, ())
    assert changed_code.digest != first.digest
    (tmp_path / "src/lottolab/strategies/data/parameters.json").write_text(
        '{"seed":2}', encoding="utf-8"
    )
    assert source_producer_fingerprint(tmp_path, ()).digest != changed_code.digest
