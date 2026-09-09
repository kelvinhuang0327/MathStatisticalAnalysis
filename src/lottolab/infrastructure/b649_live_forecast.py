"""Production next-undrawn composition into the sole SQLite research writer.

Draw access is read-only, target outcomes are presence-only, and no prospective
seal or filesystem bundle store is invoked. Replay evidence is an explicit input;
this entrypoint never launches research or manufactures missing evidence.
"""

from __future__ import annotations

import importlib.metadata
import inspect
import json
import platform
import random
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from types import CodeType, FunctionType, ModuleType
from typing import cast

from lottolab.application.b649_next_undrawn_forecast import (
    CanonicalNativeTicketGenerator,
    ForecastRequest,
    ForecastTimingError,
    native_generation_config,
    prepare_forecast,
)
from lottolab.application.future_draw_identity import (
    FutureDrawIdentityError,
    ScheduledDrawIdentityRecord,
)
from lottolab.application.pre_outcome_target_operational import PreOutcomeTargetOperationalError
from lottolab.domain.b649_next_undrawn_forecast import (
    ReplayObservation,
    catalog_exclusion,
    history_payload,
    history_ref,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.exact_native_replay import Draw
from lottolab.domain.prospective_observer import ObservationTarget, OutcomePresenceAtPrediction
from lottolab.domain.research_live_forecast import (
    LEGACY_HISTORY_SHA256,
    LEGACY_IMPORT_KEY,
    LEGACY_MISSING,
    LEGACY_SHA256,
    LEGACY_STREAM,
    NATIVE_STREAM,
    NATIVE_STREAM_VERSION,
    ORIGINAL_FIELDS,
    LiveForecastInput,
    LiveForecastResult,
    canonical_json,
    digest,
    sha256,
    utc_text,
)
from lottolab.infrastructure.b649_next_undrawn_forecast import source_producer_fingerprint
from lottolab.infrastructure.persistence.draw_schema import LocalDataPaths
from lottolab.infrastructure.persistence.draw_schema import open_database as open_draw_database
from lottolab.infrastructure.persistence.future_draw_identity_repository import (
    SQLiteFutureDrawIdentityReader,
)
from lottolab.infrastructure.persistence.research_repository import SQLiteResearchRepository
from lottolab.infrastructure.pre_outcome_target_operational import (
    SQLiteOfficialOutcomePresenceProbe,
)
from lottolab.strategies.catalog import production_catalog


def _git(repository: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", "--no-optional-locks", "-C", str(repository), *arguments],
        text=True,
    ).strip()


def _compiled_codes(code: CodeType) -> dict[str, CodeType]:
    result = {code.co_qualname: code}
    for constant in code.co_consts:
        if isinstance(constant, CodeType):
            result.update(_compiled_codes(constant))
    return result


def capture_source_execution(repository: Path) -> dict[str, object]:
    """Bind clean executed code and reject a stale or foreign Python import."""
    repository = repository.resolve(strict=True)
    if _git(repository, "rev-parse", "--show-toplevel") != str(repository):
        raise ValueError("source repository must be its Git root")
    if _git(
        repository,
        "status",
        "--porcelain",
        "--untracked-files=all",
        "--",
        "src",
        "tools/b649_next_undrawn_forecast.py",
    ):
        raise ValueError("native/import execution source must be committed before capture")
    loaded: dict[str, str] = {}
    for name, module in sorted(tuple(cast(dict[str, ModuleType | None], sys.modules).items())):
        if not name.startswith("lottolab.") or module is None:
            continue
        filename = getattr(module, "__file__", None)
        if filename is None:
            continue
        path = Path(filename).resolve(strict=True)
        if not path.is_relative_to(repository / "src") or path.suffix != ".py":
            raise ValueError(f"foreign executed source: {name}")
        raw = path.read_bytes()
        code_map = _compiled_codes(
            compile(raw, str(path), "exec", dont_inherit=True, optimize=sys.flags.optimize)
        )
        functions: list[FunctionType] = []
        for value in vars(module).values():
            if isinstance(value, FunctionType) and value.__module__ == name:
                functions.append(value)
            elif isinstance(value, type) and value.__module__ == name:
                for member in vars(value).values():
                    function: object = getattr(member, "__func__", member)
                    if isinstance(function, FunctionType) and function.__module__ == name:
                        functions.append(function)
        for function in functions:
            function = cast(FunctionType, inspect.unwrap(function))
            # Dataclass-generated methods have their own generated source; the
            # dataclass definition and Python runtime are separately bound.
            if function.__code__.co_filename == "<string>":
                continue
            expected = code_map.get(function.__code__.co_qualname)
            if expected is None or function.__code__ != expected:
                raise ValueError(f"loaded source differs from disk: {name}.{function.__qualname__}")
        loaded[path.relative_to(repository).as_posix()] = sha256(raw)
    return {
        "repository": str(repository),
        "commit": _git(repository, "rev-parse", "HEAD"),
        "tree": _git(repository, "rev-parse", "HEAD^{tree}"),
        "loaded_code": loaded,
        "loaded_code_sha256": digest(loaded),
    }


def capture_runtime_manifest() -> dict[str, object]:
    """Record actually loaded file content, installed versions and interpreter."""
    packages = importlib.metadata.packages_distributions()
    dependencies: list[dict[str, object]] = []
    for name, module in sorted(tuple(cast(dict[str, ModuleType | None], sys.modules).items())):
        if module is None or name.startswith("lottolab."):
            continue
        filename = getattr(module, "__file__", None)
        if not isinstance(filename, str):
            continue
        path = Path(filename)
        if not path.is_file():
            continue
        distributions = packages.get(name.split(".")[0], [])
        versions = {dist: importlib.metadata.version(dist) for dist in distributions}
        content_sha = sha256(path.read_bytes())
        dependencies.append(
            {
                "name": name,
                "locator": str(path.resolve()),
                "versions": versions or {"source-content-sha256": content_sha},
                "content_sha256": content_sha,
            }
        )
    manifest: dict[str, object] = {
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "executable": str(Path(sys.executable).resolve()),
            "executable_sha256": sha256(Path(sys.executable).read_bytes()),
        },
        "os": platform.platform(),
        "architecture": platform.machine(),
        "dependencies": dependencies,
    }
    return {**manifest, "sha256": digest(manifest)}


def _parameter_value(value: object) -> object:
    if value is None or type(value) in (str, int, float, bool):
        return value
    if isinstance(value, (tuple, list)):
        return [_parameter_value(item) for item in cast(Sequence[object], value)]
    if isinstance(value, (set, frozenset)):
        return sorted(
            (_parameter_value(item) for item in cast(set[object], value)), key=canonical_json
        )
    if isinstance(value, dict):
        return {
            str(key): _parameter_value(item)
            for key, item in cast(dict[object, object], value).items()
        }
    if isinstance(value, random.Random):
        return {
            "rng_type": "random.Random",
            "pre_execution_state": _parameter_value(value.getstate()),
        }
    if isinstance(value, type):
        return {"type_reference": f"{value.__module__}.{value.__qualname__}"}
    raise ValueError(
        f"uncaptured effective parameter type: {type(value).__module__}.{type(value).__name__}"
    )


class _ExecutionCapture:
    def __init__(self) -> None:
        self.parameters: dict[str, dict[str, object]] = {}
        self.errors: list[str] = []

    def observe(self, strategy_id: str, adapter: object) -> None:
        try:
            cls = type(adapter)
            state: dict[str, object] = {}
            if hasattr(adapter, "__dict__"):
                state.update(vars(adapter))
            for base in cls.__mro__:
                slots = vars(base).get("__slots__", ())
                if isinstance(slots, str):
                    slots = (slots,)
                for slot in slots:
                    if slot not in ("__dict__", "__weakref__") and hasattr(adapter, slot):
                        state[slot] = getattr(adapter, slot)
            defaults = {
                name: _parameter_value(parameter.default)
                for name, parameter in inspect.signature(cls).parameters.items()
                if parameter.default is not inspect.Parameter.empty
            }
            self.parameters[strategy_id] = {
                "strategy_id": strategy_id,
                "status": "EXECUTED",
                "constructor_defaults": defaults,
                "instance_state": _parameter_value(state),
                "adapter_class": f"{cls.__module__}:{cls.__qualname__}",
            }
        except Exception as exc:
            self.errors.append(f"{strategy_id}:{exc}")
            raise


@dataclass(frozen=True, slots=True)
class B649LiveForecastService:
    """Use production schedule/history/catalog and explicit canonical replay evidence."""

    repository: SQLiteResearchRepository
    draw_paths: LocalDataPaths
    source_repository: Path
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)

    def _schedule(self) -> ScheduledDrawIdentityRecord:
        record = SQLiteFutureDrawIdentityReader(self.draw_paths).find_earliest_unpopulated_future(
            LotteryType.BIG_LOTTO,
            self.clock(),
        )
        if record is None or record.immutable_schedule_sha256 is None:
            raise ForecastTimingError("CANONICAL_NEXT_UNDRAWN_SCHEDULE_UNAVAILABLE")
        return record

    def _gate(self, record: ScheduledDrawIdentityRecord) -> bool:
        latest = self._schedule()
        if (
            latest.announcement.target != record.announcement.target
            or latest.announcement.scheduled_at != record.announcement.scheduled_at
            or latest.immutable_schedule_sha256 != record.immutable_schedule_sha256
        ):
            raise ForecastTimingError("CANONICAL_TARGET_OR_SCHEDULE_CHANGED")
        attestation = SQLiteOfficialOutcomePresenceProbe(self.draw_paths).probe(
            record.announcement.target,
            as_of=self.clock(),
        )
        now = self.clock()
        utc_text(now)
        if (
            attestation.presence is not OutcomePresenceAtPrediction.ABSENT
            or now >= record.announcement.scheduled_at
        ):
            raise ForecastTimingError("OUTCOME_PRESENT_OR_DEADLINE_REACHED")
        return True

    def _history(self, target: ObservationTarget) -> tuple[Draw, ...]:
        # Predicates exclude the target before outcome values leave SQLite.
        with open_draw_database(self.draw_paths, read_only=True) as connection:
            rows = connection.execute(
                "SELECT draw_number, draw_date, main_numbers_json, special_numbers_json "
                "FROM draws WHERE lottery_type=? AND draw_date<? "
                "AND CAST(draw_number AS INTEGER)<? "
                "ORDER BY draw_date, CAST(draw_number AS INTEGER)",
                ("BIG_LOTTO", target.draw_date.isoformat(), int(target.draw_number)),
            ).fetchall()
        return tuple(
            Draw(
                str(n),
                date.fromisoformat(str(d)),
                tuple(json.loads(main)),
                int(json.loads(special)[0]),
            )
            for n, d, main, special in rows
        )

    def repredict(
        self,
        *,
        request_id: str,
        observations: tuple[ReplayObservation, ...],
        seeds: Mapping[str, int],
    ) -> LiveForecastResult:
        evidence = [
            asdict(o) | {"draw_date": o.draw_date.isoformat()}
            for o in sorted(observations, key=lambda o: (o.strategy_id, o.draw_number))
        ]
        request_sha = digest(
            {
                "operation": "native-repredict",
                "observations": evidence,
                "seeds": dict(seeds),
                "stream": NATIVE_STREAM_VERSION,
            }
        )
        previous = self.repository.find_live_request(request_id, request_sha)
        if previous is not None:
            return previous
        started = self.clock()
        utc_text(started)
        record = self._schedule()
        self._gate(record)
        target = record.announcement.target
        history = self._history(target)
        if not history:
            raise ValueError("canonical causal history is empty")
        scope = (
            "BIG_LOTTO",
            target.draw_number,
            target.draw_date.isoformat(),
            NATIVE_STREAM,
            NATIVE_STREAM_VERSION,
        )
        expected_version = self.repository.live_current_version(scope)
        catalog = production_catalog()
        descriptors = catalog.list(lottery_type=LotteryType.BIG_LOTTO)
        configs = tuple(
            native_generation_config(d, history, seed=seeds.get(d.strategy_id))
            for d in descriptors
            if catalog_exclusion(d) is None
        )
        producer = source_producer_fingerprint(self.source_repository, descriptors)
        source_before = capture_source_execution(self.source_repository)
        runtime_before = capture_runtime_manifest()
        request = ForecastRequest(
            target,
            history,
            history_ref(history),
            cast(str, record.immutable_schedule_sha256),
            descriptors,
            configs,
            observations,
            producer,
            required_cutoff=history[-1].draw_number,
            fixture_only=False,
        )
        capture = _ExecutionCapture()
        prepared = prepare_forecast(
            request,
            CanonicalNativeTicketGenerator(
                catalog,
                before_execution=capture.observe,
            ),
        )
        finished = self.clock()
        if finished < started:
            raise ForecastTimingError("CLOCK_MOVED_BACKWARDS")
        if capture.errors:
            raise ValueError(
                "NATIVE_EFFECTIVE_PARAMETERS_NOT_CAPTURED: " + ";".join(capture.errors)
            )
        source_after = capture_source_execution(self.source_repository)
        # Newly imported dependencies are recorded too. Previously captured
        # dependencies must retain the same content and version during execution.
        runtime_after = capture_runtime_manifest()
        before_files = {
            d["locator"]: d for d in cast(list[dict[str, object]], runtime_before["dependencies"])
        }
        after_files = {
            d["locator"]: d for d in cast(list[dict[str, object]], runtime_after["dependencies"])
        }
        if (
            any(after_files.get(k) != v for k, v in before_files.items())
            or source_before["commit"] != source_after["commit"]
            or source_before["tree"] != source_after["tree"]
            or source_producer_fingerprint(self.source_repository, descriptors) != producer
        ):
            raise ValueError("EXECUTION_DEPENDENCY_DRIFT")
        payload = cast(dict[str, object], json.loads(prepared.bundle.payload_json))
        configs_by_id = {c.strategy_id: c for c in configs}
        descriptors_by_id = {d.strategy_id: d for d in descriptors}
        parameter_rows: list[dict[str, object]] = []
        rng_rows: list[dict[str, object]] = []
        for config in sorted(configs, key=lambda c: c.strategy_id):
            row = capture.parameters.get(
                config.strategy_id,
                {
                    "strategy_id": config.strategy_id,
                    "status": "NOT_EXECUTED",
                },
            )
            parameter_rows.append(
                {
                    **row,
                    "strategy_version": config.strategy_version,
                    "native_k": config.native_k,
                    "parameters_json": config.parameters_json,
                    "generation_config_sha256": config.sha256,
                }
            )
            rng = cast(dict[str, object], json.loads(config.rng_semantics_json))
            rng_rows.append(
                {
                    "strategy_id": config.strategy_id,
                    "stage": "NATIVE_GENERATION",
                    "status": row["status"],
                    "rng_semantics": rng,
                    "seed_status": "NOT_APPLICABLE"
                    if rng["behavior"] == "DETERMINISTIC"
                    else "EFFECTIVE_SEED_CAPTURED"
                    if rng.get("seed") is not None
                    else "uncaptured_process_global_rng_state",
                    "invocation_identity": request_id,
                    "replicate": 1,
                }
            )
        lineage: list[dict[str, object]] = []
        for bucket in cast(list[dict[str, object]], payload["buckets"]):
            selected = cast(dict[str, object] | None, bucket["selected"])
            strategy_id = None if selected is None else str(selected["strategy_id"])
            descriptor = None if strategy_id is None else descriptors_by_id[strategy_id]
            locator = None if descriptor is None else descriptor.adapter_path
            adapter_source = (
                None
                if not locator
                else self.source_repository
                / "src"
                / (locator.split(":")[0].replace(".", "/") + ".py")
            )
            lineage.append(
                {
                    "native_k": bucket["native_k"],
                    "status": bucket["status"],
                    "tickets": bucket["tickets"],
                    "selected_strategy": strategy_id,
                    "selector_status": "EXECUTED",
                    "selection_rule": NATIVE_STREAM_VERSION,
                    "tie_break": bucket["display_tie_break"],
                    "candidate_binding_sha256": digest(bucket["candidates"]),
                    "evidence_payload_sha256": payload["evidence_payload_sha256"],
                    "constructor_status": "NOT_EXECUTED"
                    if strategy_id not in capture.parameters
                    else "EXECUTED",
                    "adapter_locator": locator,
                    "adapter_version": None if descriptor is None else descriptor.version,
                    "adapter_source_sha256": None
                    if adapter_source is None
                    else sha256(adapter_source.read_bytes()),
                    "generation_config_sha256": None
                    if strategy_id is None
                    else configs_by_id[strategy_id].sha256,
                    "rng_binding_sha256": None
                    if strategy_id is None
                    else digest(json.loads(configs_by_id[strategy_id].rng_semantics_json)),
                }
            )
        parameters_material = {"strategies": parameter_rows}
        history_sha = history_ref(history).history_sha256
        original: dict[str, object] = {
            "producer_json": canonical_json(producer.canonical_dict()),
            "source_execution_json": canonical_json(source_after),
            "runtime_manifest_json": canonical_json(runtime_after),
            "history_snapshot_json": canonical_json(
                {
                    "reference": f"research-live-history:sha256:{history_sha}",
                    "draws": history_payload(history),
                    "sha256": history_sha,
                }
            ),
            "catalog_json": canonical_json(
                {
                    "strategies": payload["catalog"],
                    "catalog_universe_sha256": request.identity.catalog_universe_sha256,
                }
            ),
            "generation_configs_json": canonical_json(
                {
                    "strategies": payload["generation_configs"],
                    "generation_config_sha256": request.identity.generation_config_sha256,
                }
            ),
            "effective_parameters_json": canonical_json(
                {**parameters_material, "sha256": digest(parameters_material)}
            ),
            "rng_semantics_json": canonical_json(
                {
                    "stages": rng_rows,
                    "reproducibility_boundary": (
                        "FIXED_CAPTURED_INPUTS_CODE_RUNTIME_CONFIG; "
                        "UNSEEDED_STATE_NOT_RECONSTRUCTABLE"
                    ),
                }
            ),
            "ranking_evidence_json": canonical_json(
                {
                    "objective": "OFFICIAL_ANY_PRIZE",
                    "ranking_policy_version": NATIVE_STREAM_VERSION,
                    "evaluation_window": "FULL",
                    "observations": evidence,
                    "evidence_payload_sha256": payload["evidence_payload_sha256"],
                }
            ),
            "ticket_lineage_json": canonical_json(
                {"buckets": lineage, "upstream_payload_sha256": prepared.bundle.payload_sha256}
            ),
            "generation_started_at": utc_text(started),
            "generation_finished_at": utc_text(finished),
        }
        target_payload = {
            "lottery_type": "BIG_LOTTO",
            "target_draw_number": target.draw_number,
            "target_draw_date": target.draw_date.isoformat(),
            "scheduled_at": record.announcement.scheduled_at.isoformat(),
            "timezone": "Asia/Taipei",
            "data_cutoff": history[-1].draw_number,
            "forecast_horizon": 1,
            "history_draw_count": len(history),
            "causal_history_sha256": history_sha,
            "schedule_authority_sha256": record.immutable_schedule_sha256,
        }
        forecast = LiveForecastInput(
            request_id,
            request_sha,
            "NATIVE_GENERATED",
            NATIVE_STREAM,
            NATIVE_STREAM_VERSION,
            canonical_json(target_payload),
            prepared.bundle.payload_json.encode(),
            f"canonical-next-undrawn:{prepared.bundle.identity.bundle_id}",
            canonical_json(original),
            "{}",
        )
        return self.repository.commit_live_forecast(
            forecast,
            expected_current_version=expected_version,
            current_eligible=lambda: self._gate(record),
            clock=self.clock,
        )

    def import_legacy(self, payload_path: Path) -> LiveForecastResult:
        payload = payload_path.read_bytes()
        if sha256(payload) != LEGACY_SHA256:
            raise ValueError("only the owner-pinned legacy payload may be imported")
        request_sha = digest(
            {"operation": "legacy-materialized-import", "payload_sha256": LEGACY_SHA256}
        )
        existing = self.repository.find_live_request(LEGACY_IMPORT_KEY, request_sha)
        if existing is not None:
            return existing
        original = dict.fromkeys(ORIGINAL_FIELDS)
        target = {
            "lottery_type": "BIG_LOTTO",
            "target_draw_number": "115000087",
            "target_draw_date": "2026-09-11",
            "scheduled_at": "2026-09-11T20:30:00+08:00",
            "timezone": "Asia/Taipei",
            "data_cutoff": "115000086",
            "forecast_horizon": 1,
            "history_draw_count": 2168,
            "causal_history_sha256": LEGACY_HISTORY_SHA256,
        }
        import_execution = {
            "imported_at": utc_text(self.clock()),
            "producer_id": "B649_LEGACY_MATERIALIZED_IMPORT_V1",
            "source_execution": capture_source_execution(self.source_repository),
            "runtime_manifest": capture_runtime_manifest(),
        }
        forecast = LiveForecastInput(
            LEGACY_IMPORT_KEY,
            request_sha,
            "LEGACY_MATERIALIZED",
            LEGACY_STREAM,
            LEGACY_STREAM,
            canonical_json(target),
            payload,
            str(payload_path.resolve()),
            canonical_json(original),
            canonical_json(LEGACY_MISSING),
            canonical_json(import_execution),
        )

        def eligible() -> bool:
            # An unavailable current gate does not erase a valid historical
            # materialization. It only prevents initialization of its pointer.
            try:
                record = self._schedule()
                if (
                    record.announcement.target.draw_number != "115000087"
                    or record.announcement.target.draw_date != date(2026, 9, 11)
                    or record.announcement.scheduled_at
                    != datetime.fromisoformat(str(target["scheduled_at"]))
                ):
                    return False
                return self._gate(record)
            except (
                ForecastTimingError,
                FutureDrawIdentityError,
                PreOutcomeTargetOperationalError,
                ValueError,
            ):
                return False

        return self.repository.commit_live_forecast(
            forecast,
            expected_current_version=0,
            current_eligible=eligible,
            clock=self.clock,
        )
