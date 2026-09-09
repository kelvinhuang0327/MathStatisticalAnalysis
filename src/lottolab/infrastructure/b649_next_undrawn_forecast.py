"""Create-once forecast bundles and an explicitly synthetic CLI composition.

A bundle archive contains the complete report and the original filesystem
prospective record. The generic seal is built and verified in a private staging
directory. One hard-link publishes the fsynced archive after the last fresh
gate, so a rejected or interrupted attempt cannot expose a partial forecast.
"""

from __future__ import annotations

import ast
import builtins
import hashlib
import json
import os
import re
import symtable
import tempfile
import zipfile
from collections.abc import Callable
from contextlib import suppress
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast

from lottolab.application.b649_next_undrawn_forecast import (
    ForecastConflictError,
    ForecastLiveState,
    ForecastRequest,
    NextUndrawnForecastService,
    StoredForecast,
    native_generation_config,
    observation_identity,
)
from lottolab.application.pre_outcome_target_operational import (
    OperationalRegistrationResult,
    OperationalRegistrationStatus,
)
from lottolab.application.prospective_observer import ProspectiveObservationStore
from lottolab.domain.b649_next_undrawn_forecast import (
    COHORT_ID,
    ForecastBundle,
    ForecastContractError,
    ForecastIdentity,
    GenerationConfig,
    ObservationStatus,
    ReplayObservation,
    TicketSet,
    canonical_json,
    digest,
    history_ref,
    validate_tickets,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.exact_native_replay import Draw
from lottolab.domain.pre_outcome_target import (
    OutcomePresenceAttestation,
    PreOutcomeTargetRegistration,
    TargetAnnouncement,
    TargetSourceProvenance,
)
from lottolab.domain.prospective_observer import (
    ObservationTarget,
    OutcomePresenceAtPrediction,
    PredictionRecord,
    ProducerDependency,
    ProducerFingerprint,
)
from lottolab.domain.strategies import LifecycleStatus, ResponseShape, StrategyDescriptor
from lottolab.infrastructure.prospective_observer_store import FileSystemProspectiveObservationStore

_RECORD_NAME = re.compile(
    r"record/big_lotto/cohort-[0-9a-f]{32}/target-\d{4}-\d{2}-\d{2}-[0-9a-f]{32}/prediction\.json"
)


class FileSystemForecastBundleStore:
    """An independent namespace; archives are immutable and never overwritten."""

    def __init__(self, root: Path) -> None:
        self.root = root.absolute() / COHORT_ID
        if any(p.is_symlink() for p in (self.root, *self.root.parents)):
            raise ForecastContractError("forecast storage must not traverse symlinks")
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, identity: ForecastIdentity) -> Path:
        return self.root / f"{identity.bundle_id}.zip"

    def load(self, identity: ForecastIdentity) -> StoredForecast | None:
        path = self.path_for(identity)
        if not path.exists() and not path.is_symlink():
            return None
        if path.is_symlink() or not path.is_file():
            raise ForecastConflictError("existing bundle is not a regular file")
        try:
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
                records = [n for n in names if _RECORD_NAME.fullmatch(n)]
                if len(names) != 2 or names.count("bundle.json") != 1 or len(records) != 1:
                    raise ForecastConflictError("invalid bundle archive members")
                bundle = ForecastBundle(identity, archive.read("bundle.json").decode("utf-8"))
                # Decode through the original store, including envelope integrity,
                # canonical record hashes, identity and temporal provenance checks.
                with tempfile.TemporaryDirectory(prefix=".verify-", dir=self.root) as temporary:
                    staging = Path(temporary)
                    record_path = staging / records[0]
                    record_path.parent.mkdir(parents=True)
                    record_path.write_bytes(archive.read(records[0]))
                    store = FileSystemProspectiveObservationStore(staging / "record")
                    record = store.get_prediction(observation_identity(identity))
                    if record is None:
                        raise ForecastConflictError("bundle generic prediction identity mismatch")
            return StoredForecast(bundle, record)
        except ForecastConflictError:
            raise
        except Exception as exc:
            raise ForecastConflictError(f"corrupt immutable bundle: {type(exc).__name__}") from exc

    def publish(
        self,
        bundle: ForecastBundle,
        seal: Callable[[ProspectiveObservationStore], PredictionRecord],
        before_publish: Callable[[], None],
    ) -> StoredForecast:
        existing = self.load(bundle.identity)
        if existing is not None:
            return self._equal(existing, bundle)
        with tempfile.TemporaryDirectory(prefix=".publish-", dir=self.root) as temporary:
            staging = Path(temporary)
            record_root = staging / "record"
            store = FileSystemProspectiveObservationStore(record_root)
            record = seal(store)
            if store.get_prediction(observation_identity(bundle.identity)) != record:
                raise ForecastConflictError("staged generic seal failed read-after-write")
            record_paths = tuple(record_root.rglob("prediction.json"))
            if len(record_paths) != 1:
                raise ForecastConflictError("expected exactly one generic prediction record")
            archive_path = staging / "bundle.tmp"
            with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_STORED) as archive:
                archive.writestr("bundle.json", bundle.payload_json.encode("utf-8"))
                archive.write(record_paths[0], record_paths[0].relative_to(staging).as_posix())
            with archive_path.open("rb") as handle:
                os.fsync(handle.fileno())
            before_publish()
            with suppress(FileExistsError):
                os.link(archive_path, self.path_for(bundle.identity), follow_symlinks=False)
            descriptor = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        persisted = self.load(bundle.identity)
        if persisted is None:
            raise ForecastConflictError("published bundle disappeared")
        return self._equal(persisted, bundle)

    @staticmethod
    def _equal(existing: StoredForecast, bundle: ForecastBundle) -> StoredForecast:
        if existing.bundle != bundle:
            raise ForecastConflictError("same bundle_id with conflicting payload")
        return existing


# A shared aggregator module that mixes this producer's own consumed contracts
# with unrelated ones (e.g. other lotteries' repositories). Listing it here
# switches its handling from whole-file hashing to per-symbol extraction, so
# an unrelated declaration added to it can never perturb this digest.
_CATALOG_MODULE = "lottolab.strategies.catalog"
_SYMBOL_SCOPED_SHARED_MODULES = frozenset({"lottolab.application.ports", _CATALOG_MODULE})


def _catalog_global_references(segment: str) -> set[str]:
    """Resolve method/comprehension locals without mistaking them for helpers."""
    pending = [symtable.symtable(segment, "<catalog-contract>", "exec")]
    references: set[str] = set()
    while pending:
        table = pending.pop()
        references.update(
            symbol.get_name()
            for symbol in table.get_symbols()
            if symbol.is_referenced() and symbol.is_global()
        )
        pending.extend(table.get_children())
    return references


def _resolve_module_path(source: Path, module: str) -> Path | None:
    parts = module.split(".")
    path = source.joinpath(*parts).with_suffix(".py")
    if path.is_file():
        return path
    path = source.joinpath(*parts) / "__init__.py"
    return path if path.is_file() else None


def _module_top_level_bindings(tree: ast.Module) -> tuple[dict[str, ast.stmt], dict[str, str]]:
    """Map each top-level defined name to its statement, and each name this
    module imports from elsewhere to the dotted module it came from."""
    definitions: dict[str, ast.stmt] = {}
    imported_from: dict[str, str] = {}
    for stmt in tree.body:
        if isinstance(stmt, ast.ImportFrom) and stmt.module and not stmt.level:
            for alias in stmt.names:
                imported_from[alias.asname or alias.name] = stmt.module
        elif isinstance(stmt, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            definitions[stmt.name] = stmt
        elif isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    definitions[target.id] = stmt
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            definitions[stmt.target.id] = stmt
        elif isinstance(stmt, ast.TypeAlias):
            definitions[stmt.name.id] = stmt
    return definitions, imported_from


def _source_segment_including_decorators(source_lines: list[str], stmt: ast.stmt) -> str:
    start = stmt.lineno
    for decorator in getattr(stmt, "decorator_list", ()):
        start = min(start, decorator.lineno)
    end = stmt.end_lineno or stmt.lineno
    return "\n".join(source_lines[start - 1 : end])


def _extract_consumed_symbols(
    module_source: str, names: frozenset[str], *, catalog_contract: bool = False
) -> tuple[str, frozenset[str]]:
    """Bind exactly the reachable source for the requested top-level names.

    A shared aggregator module may define many unrelated contracts; this
    returns only ``names`` plus, recursively, every other top-level name in
    the same module their own definitions reference (including decorators) --
    never the whole file. A referenced name the module itself imports from
    elsewhere is returned separately for the caller to resolve as an ordinary
    module dependency. Fails closed (raises) rather than silently omitting a
    name that resolves to neither a local definition nor an import.
    """
    definitions, imported_from = _module_top_level_bindings(ast.parse(module_source))
    source_lines = module_source.splitlines()
    included: dict[str, ast.stmt] = {}
    forwarded: set[str] = set()
    pending_names = set(names)
    while pending_names:
        name = pending_names.pop()
        if name in included:
            continue
        stmt = definitions.get(name)
        # This constructor input is data, represented by the exact caller's
        # descriptors below. Never recursively hash the module-wide tuple.
        if catalog_contract and name == "_PRODUCTION_DESCRIPTORS" and stmt is not None:
            continue
        if stmt is None:
            if hasattr(builtins, name):
                continue
            source_module = imported_from.get(name)
            if source_module is None:
                raise ForecastContractError(
                    f"PRODUCER_FINGERPRINT_REQUIRED_SYMBOL_UNRESOLVED: {name}"
                )
            forwarded.add(source_module)
            continue
        included[name] = stmt
        if catalog_contract:
            pending_names.update(
                _catalog_global_references(_source_segment_including_decorators(source_lines, stmt))
                - included.keys()
            )
            continue
        for node in ast.walk(stmt):
            if (
                isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
                and node.id not in included
            ):
                pending_names.add(node.id)
    ordered = sorted(included.values(), key=lambda stmt: stmt.lineno)
    segments = [_source_segment_including_decorators(source_lines, stmt) for stmt in ordered]
    return "\n\n".join(segments), frozenset(forwarded)


def source_producer_fingerprint(
    repository: Path,
    catalog: tuple[StrategyDescriptor, ...],
    *,
    version: str = "2",
) -> ProducerFingerprint:
    """Bind exactly this producer's own code, adapters, and consumed shared symbols.

    Static import closure from this producer's own modules, plus each selected
    descriptor's explicit adapter module, covers dynamically loaded adapters.
    A module listed in ``_SYMBOL_SCOPED_SHARED_MODULES`` (a shared aggregator
    like ``ports.py`` that mixes causal and unrelated contracts) contributes
    only the specific top-level symbols this producer's own closure actually
    imports from it, plus whatever those symbols themselves reference --
    never its unrelated declarations, so an unrelated subsystem sharing that
    module cannot make its own contract load-bearing here. The catalog's
    constructor data is replaced by the exact passed descriptors, using the
    existing canonical descriptor serialization. Its source-wide descriptor
    universe is not a producer dependency. This producer's
    own modules, the CLI entrypoint, and each selected descriptor's adapter
    module are explicitly required: fingerprint construction fails closed if
    any of them cannot be resolved. No adapter runs and no external evidence
    store or database is opened.
    """
    source = repository / "src"
    entrypoint = repository / "tools" / "b649_next_undrawn_forecast.py"
    if not entrypoint.is_file():
        raise ForecastContractError("PRODUCER_FINGERPRINT_REQUIRED_PATH_MISSING: CLI entrypoint")

    required_seeds = frozenset(
        {
            "lottolab.application.b649_next_undrawn_forecast",
            "lottolab.infrastructure.b649_next_undrawn_forecast",
        }
    )
    adapter_modules = frozenset(
        d.adapter_path.split(":", 1)[0]
        for d in catalog
        if d.adapter_path and d.adapter_path.startswith("lottolab.")
    )
    pending = set(required_seeds) | set(adapter_modules)
    seen: set[str] = set()
    paths = {entrypoint}
    shared_symbol_names: dict[str, set[str]] = {}

    while True:
        while pending:
            module = pending.pop()
            if module in seen or not module.startswith("lottolab"):
                continue
            seen.add(module)
            parts = module.split(".")
            pending.update(".".join(parts[:i]) for i in range(1, len(parts)))
            path = _resolve_module_path(source, module)
            if path is None:
                if module in required_seeds or module in adapter_modules:
                    raise ForecastContractError(
                        f"PRODUCER_FINGERPRINT_REQUIRED_MODULE_MISSING: {module}"
                    )
                continue
            if module in _SYMBOL_SCOPED_SHARED_MODULES:
                continue
            paths.add(path)
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import):
                    pending.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    base = node.module or ""
                    if node.level:
                        package = parts if path.name == "__init__.py" else parts[:-1]
                        base = ".".join(
                            (*package[: len(package) - node.level + 1], *base.split("."))
                        ).rstrip(".")
                    pending.add(base)
                    if base in _SYMBOL_SCOPED_SHARED_MODULES:
                        if any(alias.name == "*" for alias in node.names):
                            raise ForecastContractError(
                                "PRODUCER_FINGERPRINT_WILDCARD_IMPORT_OF_SHARED_MODULE: "
                                f"{base}"
                            )
                        shared_symbol_names.setdefault(base, set()).update(
                            alias.name for alias in node.names
                        )
                    else:
                        # `from package import name` may import a submodule
                        # rather than a symbol defined in package/__init__.py
                        # (e.g. `from ..domain import loaded` importing the
                        # file domain/loaded.py) -- queue that possibility too;
                        # it is a harmless no-op when `name` is really a symbol.
                        pending.update(
                            f"{base}.{alias.name}" for alias in node.names if alias.name != "*"
                        )
        forwarded_any: set[str] = set()
        for shared_module, names in shared_symbol_names.items():
            shared_path = _resolve_module_path(source, shared_module)
            if shared_path is None:
                raise ForecastContractError(
                    f"PRODUCER_FINGERPRINT_REQUIRED_MODULE_MISSING: {shared_module}"
                )
            _, forwarded = _extract_consumed_symbols(
                shared_path.read_text(encoding="utf-8"),
                frozenset(names),
                catalog_contract=shared_module == _CATALOG_MODULE,
            )
            forwarded_any.update(
                m for m in forwarded if m.startswith("lottolab") and m not in seen
            )
        if not forwarded_any:
            break
        pending.update(forwarded_any)

    dependencies = [
        ProducerDependency(
            path.relative_to(repository).as_posix(),
            hashlib.sha256(path.read_bytes()).hexdigest(),
            "canonical producer, native generation, ranking or prospective contract code",
        )
        for path in sorted(paths)
    ]
    for shared_module, names in sorted(shared_symbol_names.items()):
        shared_path = _resolve_module_path(source, shared_module)
        if shared_path is None:
            raise ForecastContractError(
                f"PRODUCER_FINGERPRINT_REQUIRED_MODULE_MISSING: {shared_module}"
            )
        extracted, _ = _extract_consumed_symbols(
            shared_path.read_text(encoding="utf-8"),
            frozenset(names),
            catalog_contract=shared_module == _CATALOG_MODULE,
        )
        locator = f"{shared_path.relative_to(repository).as_posix()}::{','.join(sorted(names))}"
        dependencies.append(
            ProducerDependency(
                locator,
                hashlib.sha256(extracted.encode("utf-8")).hexdigest(),
                "consumed shared-contract symbols from a shared aggregator module",
            )
        )
    if catalog:
        dependencies.append(
            ProducerDependency(
                "catalog-argument://strategy-descriptors",
                digest(sorted((asdict(d) for d in catalog), key=canonical_json)),
                "exact descriptors used to resolve this producer's adapter dependencies",
            )
        )
    dependencies.sort(key=lambda dependency: dependency.locator)
    return ProducerFingerprint.create(
        producer_id="b649_next_undrawn_forecast",
        producer_version=version,
        dependencies=tuple(dependencies),
    )


class FixtureTicketGenerator:
    """Synthetic ticket snapshots only; never resolves an executable adapter."""

    def __init__(self, tickets: dict[str, TicketSet]) -> None:
        self.tickets = dict(tickets)

    def generate(
        self, descriptor: StrategyDescriptor, config: GenerationConfig, history: tuple[Draw, ...]
    ) -> TicketSet:
        if not descriptor.strategy_id.startswith("fixture_"):
            raise ForecastContractError("FIXTURE_STRATEGY_REQUIRED")
        tickets = self.tickets[descriptor.strategy_id]
        validate_tickets(tickets, descriptor.native_ticket_count)
        return tickets


def _object(value: object) -> dict[str, object]:
    if type(value) is not dict:
        raise ForecastContractError("expected JSON object")
    return cast(dict[str, object], value)


def _array(value: object) -> list[object]:
    if type(value) is not list:
        raise ForecastContractError("expected JSON array")
    return cast(list[object], value)


def _text(value: object) -> str:
    if type(value) is not str or not value:
        raise ForecastContractError("expected nonempty string")
    return value


def _integer(value: object) -> int:
    if type(value) is not int:
        raise ForecastContractError("expected exact integer")
    return value


def _tickets(value: object) -> TicketSet:
    return tuple(tuple(_integer(n) for n in _array(t)) for t in _array(value))


def _utc(value: object) -> datetime:
    parsed = datetime.fromisoformat(_text(value))
    if parsed.tzinfo is not UTC:
        raise ForecastContractError("fixture clock must be UTC")
    return parsed


class FixtureRegistration:
    def __init__(self, result: OperationalRegistrationResult) -> None:
        self.result = result

    def register_earliest(self, lottery_type: LotteryType) -> OperationalRegistrationResult:
        if lottery_type is not LotteryType.BIG_LOTTO:
            raise ForecastContractError("BIG_LOTTO_REQUIRED")
        return self.result


def run_fixture(fixture: Path, output_root: Path) -> StoredForecast:
    """The CLI has one composition: explicit synthetic input and caller-owned storage."""
    raw = _object(json.loads(fixture.read_text(encoding="utf-8")))
    if raw.get("fixture_only") is not True:
        raise ForecastContractError("FIXTURE_ONLY_COMPOSITION_REQUIRED")
    now = _utc(raw["now"])
    target_data = _object(raw["target"])
    target = ObservationTarget(
        LotteryType.BIG_LOTTO,
        _text(target_data["draw_number"]),
        date.fromisoformat(_text(target_data["draw_date"])),
    )
    history_rows = [_object(row) for row in _array(raw["history"])]
    history = tuple(
        Draw(
            _text(row["draw_number"]),
            date.fromisoformat(_text(row["draw_date"])),
            tuple(_integer(n) for n in _array(row["main_numbers"])),
            _integer(row["special_number"]),
        )
        for row in history_rows
    )
    descriptors: list[StrategyDescriptor] = []
    tickets: dict[str, TicketSet] = {}
    for value in _array(raw["strategies"]):
        row = _object(value)
        strategy_id = _text(row["strategy_id"])
        if not strategy_id.startswith("fixture_"):
            raise ForecastContractError("FIXTURE_STRATEGY_REQUIRED")
        k = _integer(row["native_k"])
        descriptors.append(
            StrategyDescriptor(
                strategy_id,
                strategy_id,
                "fixture-v1",
                (LotteryType.BIG_LOTTO,),
                LifecycleStatus.ONLINE,
                True,
                "fixture:ticket_snapshot",
                min_history=_integer(row.get("min_history", 1)),
                response_shape=ResponseShape.SINGLE_TICKET if k == 1 else ResponseShape.PORTFOLIO,
                native_ticket_count=k,
            )
        )
        tickets[strategy_id] = _tickets(row["generated_tickets"])
    catalog = tuple(descriptors)
    producer = source_producer_fingerprint(
        Path(__file__).resolve().parents[3], catalog, version="fixture-only-v2"
    )
    configs = tuple(native_generation_config(d, history) for d in catalog)
    config_by_id = {c.strategy_id: c for c in configs}
    descriptor_by_id = {d.strategy_id: d for d in catalog}
    draw_by_id = {d.draw_number: (i, d) for i, d in enumerate(history)}
    observations: list[ReplayObservation] = []
    for value in _array(raw["observations"]):
        row = _object(value)
        config = config_by_id[_text(row["strategy_id"])]
        index, draw = draw_by_id[_text(row["draw_number"])]
        failure_code = row.get("failure_code")
        observations.append(
            ReplayObservation(
                config.strategy_id,
                config.strategy_version,
                config.native_k,
                draw.draw_number,
                draw.draw_date,
                history_ref(history[:index]).history_sha256,
                native_generation_config(
                    descriptor_by_id[config.strategy_id], history[:index]
                ).sha256,
                ObservationStatus(_text(row["status"])),
                _tickets(row.get("tickets", [])),
                None if failure_code is None else _text(failure_code),
                producer_fingerprint=producer.digest,
            )
        )
    scheduled = _utc(target_data["scheduled_at"])
    schedule_digest = digest(target_data)
    source = TargetSourceProvenance(
        "synthetic-forecast", "fixture-v1", "fixture://forecast", schedule_digest, now
    )
    announcement = TargetAnnouncement(target, "Asia/Taipei", scheduled, source)
    authority = history_ref(history)
    registration = PreOutcomeTargetRegistration.create(
        announcement=announcement,
        absence_attestation=OutcomePresenceAttestation(
            target, OutcomePresenceAtPrediction.ABSENT, now, source
        ),
        causal_history=authority,
        registered_at=now,
    )
    operational = OperationalRegistrationResult(
        OperationalRegistrationStatus.CREATED,
        announcement,
        authority,
        registration,
        schedule_digest,
    )
    request = ForecastRequest(
        target,
        history,
        authority,
        schedule_digest,
        catalog,
        configs,
        tuple(observations),
        producer,
        fixture_only=True,
    )
    service = NextUndrawnForecastService(
        FixtureRegistration(operational),
        lambda _: ForecastLiveState(scheduled, schedule_digest, False),
        lambda: now,
        FixtureTicketGenerator(tickets),
        FileSystemForecastBundleStore(output_root),
    )
    return service.run(request)
